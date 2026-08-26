"""Bounded process-local, immutable, single-flight session array cache."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
import stat
import threading
from typing import Any, Iterable

import numpy as np

from . import common as C
from .durable_store import DurableEntryV2Store, DurableProduct
from .event_pack import CATEGORICAL_FIELDS, CONTINUOUS_FIELDS
from .session_cache_store import SessionCacheSource, SessionCacheStoreMixin
from .session_stream_io import _exact_int


@dataclass(slots=True)
class _ArrayCacheEntry:
    identity: bytes
    continuous: np.ndarray | None
    categorical: np.ndarray | None
    byte_count: int
    rows: int
    content_sha256: str
    backing_path: Path | None = None
    backing_stat: tuple[int, int, int, int, int, int] | None = None
    durable_product: DurableProduct | None = None


@dataclass(slots=True)
class _ArrayCacheFlight:
    identity: bytes
    byte_count: int
    generation: int
    complete: threading.Event = field(default_factory=threading.Event)
    error: BaseException | None = None


class SessionArrayCache(SessionCacheStoreMixin):
    """Bounded process-local, immutable, single-flight session array cache.

    Production may provide ``backing_dir``.  In that mode the logical cache is
    identical, but each verified pair of arrays is atomically written to one
    read-only file and reopened as read-only memory maps on demand.  This keeps
    the one-physical-open law without pinning the complete pre-H2 array plane
    in anonymous RAM.  The backing directory is process-owned and removed by
    :meth:`close` after its exact entries have been unlinked.
    """

    def __init__(self, capacity_bytes: int, *,
                 backing_dir: os.PathLike[str] | str | None = None,
                 durable_store: DurableEntryV2Store | None = None) -> None:
        capacity = _exact_int(capacity_bytes, "array cache capacity_bytes")
        if capacity < 0:
            raise C.EntryV2Refusal("array cache capacity_bytes must be nonnegative")
        self.capacity_bytes = capacity
        if backing_dir is not None and durable_store is not None:
            raise C.EntryV2Refusal(
                "process-local backing_dir and durable_store are mutually exclusive"
            )
        if durable_store is not None and not isinstance(
                durable_store, DurableEntryV2Store):
            raise C.EntryV2Refusal("durable_store must be a DurableEntryV2Store")
        self.durable_store = durable_store
        self.backing_dir: Path | None = None
        if backing_dir is not None:
            path = Path(backing_dir)
            if (not path.is_absolute() or ".." in path.parts
                    or path.exists() or not path.parent.is_dir()):
                raise C.EntryV2Refusal(
                    "disk-backed session array cache requires a new absolute directory"
                )
            parent = path.parent.resolve(strict=True)
            canonical = parent / path.name
            if canonical != path:
                raise C.EntryV2Refusal(
                    "disk-backed session array cache path is not canonical"
                )
            path.mkdir(mode=0o700)
            self.backing_dir = path
        self._entries: dict[str, _ArrayCacheEntry] = {}
        self._flights: dict[str, _ArrayCacheFlight] = {}
        self._bytes_used = 0
        self._bytes_reserved = 0
        self._generation = 0
        self._closed = False
        self._lock = threading.Lock()

    @staticmethod
    def planned_bytes(source: SessionCacheSource) -> int:
        return source.max_cutoff * (
            len(CONTINUOUS_FIELDS) * np.dtype(np.float64).itemsize
            + len(CATEGORICAL_FIELDS) * np.dtype(np.uint8).itemsize
        )

    @property
    def bytes_used(self) -> int:
        with self._lock:
            return self._bytes_used

    @property
    def disk_backed(self) -> bool:
        return self.backing_dir is not None or self.durable_store is not None

    @property
    def durable(self) -> bool:
        return self.durable_store is not None

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def resident_receipts(self) -> frozenset[str]:
        """Snapshot exact resident keys for cumulative/delta admission."""
        with self._lock:
            if self._closed:
                raise C.EntryV2Refusal("session array cache is closed")
            return frozenset(self._entries)

    def discard_receipts(self, receipts: Iterable[str]) -> None:
        """Rollback only entries admitted by a failed incremental operation."""
        keys = frozenset(str(value) for value in receipts)
        with self._lock:
            if self._flights.keys() & keys:
                raise C.EntryV2Refusal("cannot rollback an in-flight cache entry")
            entries = tuple(
                self._entries.pop(key) for key in keys if key in self._entries
            )
            self._bytes_used -= sum(entry.byte_count for entry in entries)
            if self._bytes_used < 0:
                raise C.EntryV2Refusal("session array rollback accounting drift")
        for entry in entries:
            self._discard_entry(entry)

    @staticmethod
    def _assert_identity(actual: bytes, expected: bytes) -> None:
        if actual != expected:
            raise C.EntryV2Refusal("session array cache receipt-hash collision")

    @staticmethod
    def _byte_view(value: np.ndarray) -> memoryview:
        array = np.asarray(value)
        if array.nbytes == 0:
            return memoryview(b"")
        return memoryview(array).cast("B")

    @staticmethod
    def _content_sha256(continuous: np.ndarray,
        categorical: np.ndarray) -> str:
        digest = hashlib.sha256()
        digest.update(SessionArrayCache._byte_view(continuous))
        digest.update(SessionArrayCache._byte_view(categorical))
        return digest.hexdigest()

    @staticmethod
    def _write_all(handle: Any, value: memoryview) -> None:
        offset = 0
        chunk = 8 * 1024 * 1024
        while offset < len(value):
            written = handle.write(value[offset:offset + chunk])
            if not isinstance(written, int) or written <= 0:
                raise C.EntryV2Refusal(
                    "disk-backed session array cache write was incomplete"
                )
            offset += written

    @staticmethod
    def _stat_identity(path: Path) -> tuple[int, int, int, int, int, int]:
        value = path.stat()
        return (value.st_size, value.st_dev, value.st_ino,
                value.st_mtime_ns, value.st_ctime_ns,
                stat.S_IMODE(value.st_mode))

    def get_or_fill(
        self,
        source: SessionCacheSource,
        fill: Any,
    ) -> tuple[np.ndarray, np.ndarray, bool]:
        key = source.receipt.receipt_sha256
        identity = source.receipt.canonical_bytes()
        planned = self.planned_bytes(source)

        while True:
            owner = False
            with self._lock:
                if self._closed:
                    raise C.EntryV2Refusal("session array cache is closed")
                entry = self._entries.get(key)
                if entry is not None:
                    self._assert_identity(entry.identity, identity)
                    continuous, categorical = self._entry_arrays(entry)
                    return continuous, categorical, True
                flight = self._flights.get(key)
                if flight is not None:
                    self._assert_identity(flight.identity, identity)
                else:
                    if self._bytes_used + self._bytes_reserved + planned > self.capacity_bytes:
                        raise C.EntryV2Refusal(
                            "session array cache capacity is insufficient"
                        )
                    flight = _ArrayCacheFlight(
                        identity, planned, self._generation
                    )
                    self._flights[key] = flight
                    self._bytes_reserved += planned
                    owner = True
            if owner:
                break
            flight.complete.wait()
            if flight.error is not None:
                raise flight.error

        entry: _ArrayCacheEntry | None = None
        inserted = False
        try:
            durable_hit = self._load_durable_entry(source, identity)
            if durable_hit is None:
                continuous, categorical = fill()
            else:
                continuous = durable_hit.continuous
                categorical = durable_hit.categorical
            actual = continuous.nbytes + categorical.nbytes
            if actual != planned:
                raise C.EntryV2Refusal("session array cache byte accounting drift")
            entry = (durable_hit if durable_hit is not None else self._make_entry(
                key, identity, continuous, categorical, source
            ))
            with self._lock:
                if self._closed or flight.generation != self._generation:
                    raise C.EntryV2Refusal("session array cache cleared during fill")
                self._entries[key] = entry
                self._bytes_used += actual
                inserted = True
        except MemoryError as exc:
            error: BaseException = C.EntryV2Refusal(
                "session array cache allocation failed"
            )
            error.__cause__ = exc
            with self._lock:
                flight.error = error
            raise error
        except BaseException as exc:
            if entry is not None and not inserted:
                self._discard_entry(entry)
            with self._lock:
                flight.error = exc
            raise
        finally:
            with self._lock:
                self._bytes_reserved -= planned
                self._flights.pop(key, None)
                flight.complete.set()
        assert entry is not None
        continuous, categorical = self._entry_arrays(entry)
        return continuous, categorical, durable_hit is not None

    def clear(self) -> None:
        with self._lock:
            entries = tuple(self._entries.values())
            self._entries.clear()
            self._bytes_used = 0
            self._generation += 1
        for entry in entries:
            self._discard_entry(entry)

    def close(self) -> None:
        with self._lock:
            entries = tuple(self._entries.values())
            self._entries.clear()
            self._bytes_used = 0
            self._generation += 1
            self._closed = True
        for entry in entries:
            self._discard_entry(entry)
        if self.backing_dir is not None:
            try:
                self.backing_dir.rmdir()
            except OSError as exc:
                raise C.EntryV2Refusal(
                    "disk-backed session array cache directory is not empty"
                ) from exc

    def __enter__(self) -> SessionArrayCache:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
