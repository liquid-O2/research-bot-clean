#!/usr/bin/env python3
"""Bounded, receipt-bearing materialization of one QRE2 asset-session.

``SessionEventSource`` is an immutable reference, not a cache.  It carries the
externally trusted identity of one QRE2 event pack and opens that pack only
inside a context manager.  Every identity check completes before
``EventPack.model_arrays`` is called, only rows ``[0, max_cutoff)`` are
converted, and the underlying memory map is closed on every exit path.

The deterministic receipt binds the full source hash to the exact event-byte
interval consumed by the model conversion.  It also names the conversion law
instead of treating a pair of anonymous NumPy arrays as sufficient lineage.
No module-level collection retains a source, pack, array, or batch.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import threading
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Iterator, Mapping, overload

import numpy as np

from . import common as C
from .event_pack import (
    CATEGORY_SIZES,
    CATEGORICAL_FIELDS,
    CONTINUOUS_FIELDS,
    EVENT_DTYPE,
    HEADER_BYTES,
    HEADER,
    MAGIC,
    ROW_BYTES,
    VERSION,
    EventPack,
)
from .durable_store import DurableEntryV2Store, DurableProduct

if TYPE_CHECKING:
    from .train import EntrySessionBatch, EntrySessionSpec


SESSION_STREAM_RECEIPT_SCHEMA = "entry-v2-session-stream-receipt-v3"
SIDECAR_SCHEMA = "QRE2EVENTMETA2"
CUTOFF_RULE = (
    "lower_bound(ts_recv_ns,decision_ts_ns); "
    "equal receive-time batch is future"
)
_SHA256 = re.compile(r"[0-9a-f]{64}")

# This declarative law is intentionally narrower than a hash of event_pack.py:
# unrelated reader edits do not invalidate receipts, while any change to the
# fields, dtypes, slice, or exact clock conversion necessarily changes the law
# hash.  Tuples keep the exported mapping transitively immutable.
MODEL_ARRAYS_CONVERSION_LAW: Mapping[str, Any] = MappingProxyType({
    "schema": "entry-v2-event-model-arrays-law-v3",
    "producer": "engine.entry_v2.event_pack.EventPack.model_arrays",
    "call": "model_arrays(stop=max_cutoff)",
    "source_rows": "[0,max_cutoff)",
    "source_row_bytes": ROW_BYTES,
    "continuous_dtype": "float64",
    "continuous_fields": tuple(CONTINUOUS_FIELDS),
    "categorical_dtype": "uint8",
    "categorical_fields": tuple(CATEGORICAL_FIELDS),
    "category_sizes": tuple(CATEGORY_SIZES),
    "receive_time_law": (
        "receive_time_ns=uint64(ts_recv_ns)-uint64(open_utc*1000000000); "
        "seconds,subsecond=divmod(receive_time_ns,1000000000); "
        "microseconds,nanoseconds=divmod(subsecond,1000)"
    ),
    "receive_minus_event_law": (
        "delta_ns=int64(ts_recv_ns)-int64(ts_event_ns); "
        "delta_ns=1000*signed_microseconds+nonnegative_nanoseconds; "
        "microseconds,nanoseconds=divmod(delta_ns,1000)"
    ),
    "remaining_continuous_law": (
        "price,bid_px,ask_px: raw int64==INT64_MAX sets respective mask bit "
        "0,1,2 and writes canonical 0.0 in only that continuous cell before "
        "range validation; every other integer is exact integer-to-float64 "
        "copy with abs(value)<=2**53 and no clipping"
    ),
    "categorical_law": (
        "action,side,flags,depth exact uint8 copy; price_undef_mask uint8 is "
        "bit0=(raw price==INT64_MAX)|bit1=(raw bid_px==INT64_MAX)<<1|"
        "bit2=(raw ask_px==INT64_MAX)<<2; category_sizes=(256,256,256,256,8)"
    ),
})
MODEL_ARRAYS_CONVERSION_LAW_SHA256 = C.object_sha256(
    dict(MODEL_ARRAYS_CONVERSION_LAW)
)


def _exact_int(value: object, name: str) -> int:
    if isinstance(value, (bool, np.bool_)):
        raise C.EntryV2Refusal(f"{name} must be an integer, not boolean")
    try:
        out = int(value)  # NumPy integer scalars are accepted deliberately.
    except (TypeError, ValueError, OverflowError) as exc:
        raise C.EntryV2Refusal(f"invalid integer {name}") from exc
    if isinstance(value, (float, np.floating)) and not float(value).is_integer():
        raise C.EntryV2Refusal(f"invalid integer {name}")
    return out


def _sha256(value: object, name: str) -> str:
    out = str(value).lower()
    if _SHA256.fullmatch(out) is None:
        raise C.EntryV2Refusal(f"invalid {name} SHA-256")
    return out


def _guard_path_components(path: Path) -> None:
    """Apply the H2/2026 wall before any filesystem lookup or resolution."""
    for component in path.parts:
        for d8 in C.dates_in_basename(component):
            C.guard_date(d8)


def _canonical_source_path(value: os.PathLike[str] | str, d8: int) -> Path:
    path = Path(value)
    _guard_path_components(path)
    if not path.is_absolute():
        raise C.EntryV2Refusal("pinned QRE2 path must be absolute")
    if ".." in path.parts:
        raise C.EntryV2Refusal("pinned QRE2 path cannot contain parent traversal")
    if path.suffix != ".qre2":
        raise C.EntryV2Refusal("pinned event source is not a .qre2 file")
    dates = C.dates_in_basename(path)
    if dates != (int(d8),):
        raise C.EntryV2Refusal(
            "QRE2 basename must contain exactly the pinned trading day"
        )
    # normpath/abspath are lexical operations; unlike resolve(), they do not
    # follow a symlink or inspect an unauthorized payload.
    normalized = Path(os.path.abspath(os.path.normpath(os.fspath(path))))
    if normalized != path:
        raise C.EntryV2Refusal("pinned QRE2 path is not lexically canonical")
    return path


def _strict_json_object(raw: bytes, name: str) -> Mapping[str, Any]:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in pairs:
            if key in out:
                raise C.EntryV2Refusal(f"duplicate key in {name}: {key}")
            out[key] = value
        return out

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
    except C.EntryV2Refusal:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise C.EntryV2Refusal(f"invalid {name} JSON") from exc
    if not isinstance(value, dict):
        raise C.EntryV2Refusal(f"{name} must be a JSON object")
    return value


def _identity_int(obj: Mapping[str, Any], name: str, expected: int) -> None:
    if name not in obj or _exact_int(obj[name], f"sidecar {name}") != int(expected):
        raise C.EntryV2Refusal(f"event sidecar identity drift: {name}")


def _expected_sidecar_layout() -> frozenset[tuple[str, str, int]]:
    layout: set[tuple[str, str, int]] = set()
    for name in EVENT_DTYPE.names or ():
        dtype, offset = EVENT_DTYPE.fields[name][:2]
        layout.add((name, dtype.str.removeprefix("|"), int(offset)))
    return frozenset(layout)


_SIDECAR_LAYOUT = _expected_sidecar_layout()


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


class SessionArrayCache:
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
    def planned_bytes(source: "SessionEventSource") -> int:
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

    def _make_entry(self, key: str, identity: bytes,
                    continuous: np.ndarray,
                    categorical: np.ndarray,
                    source: "SessionEventSource") -> _ArrayCacheEntry:
        continuous.setflags(write=False)
        categorical.setflags(write=False)
        actual = int(continuous.nbytes + categorical.nbytes)
        content_sha256 = self._content_sha256(continuous, categorical)
        rows = int(continuous.shape[0])
        if self.durable_store is not None:
            measured = source.measurements.snapshot()
            producer = {
                "schema": "entry-v2-session-array-producer-v1",
                "physical_full_pack_opens": int(
                    measured["physical_full_pack_opens"]),
                "model_array_physical_fills": int(
                    measured["model_array_physical_fills"]),
            }
            if (producer["physical_full_pack_opens"],
                    producer["model_array_physical_fills"]) != (1, 1):
                raise C.EntryV2Refusal(
                    "durable array producer did not perform exactly one open/fill"
                )
            product = self.durable_store.publish(
                "session-arrays", source.durable_identity(),
                MODEL_ARRAYS_CONVERSION_LAW_SHA256,
                (continuous, categorical),
                semantic={
                    "schema": "entry-v2-session-array-map-v1",
                    "continuous_fields": list(CONTINUOUS_FIELDS),
                    "categorical_fields": list(CATEGORICAL_FIELDS),
                    "rows": rows,
                },
                producer=producer,
            )
            return _ArrayCacheEntry(
                identity, product.arrays[0], product.arrays[1], actual, rows,
                content_sha256,
                durable_product=product,
            )
        if self.backing_dir is None or actual == 0:
            return _ArrayCacheEntry(
                identity, continuous, categorical, actual, rows, content_sha256
            )

        final = self.backing_dir / f"{key}.arrays"
        temporary = self.backing_dir / f".{key}.tmp"
        if final.exists() or temporary.exists():
            raise C.EntryV2Refusal(
                "disk-backed session array cache path already exists"
            )
        renamed = False
        try:
            with temporary.open("xb", buffering=0) as handle:
                self._write_all(handle, self._byte_view(continuous))
                self._write_all(handle, self._byte_view(categorical))
                os.fsync(handle.fileno())
                os.fchmod(handle.fileno(), 0o444)
                if hasattr(os, "posix_fadvise") and hasattr(
                        os, "POSIX_FADV_DONTNEED"):
                    try:
                        os.posix_fadvise(
                            handle.fileno(), 0, 0, os.POSIX_FADV_DONTNEED
                        )
                    except OSError:
                        # Some network filesystems do not implement fadvise;
                        # the clean file pages remain kernel-reclaimable.
                        pass
            os.replace(temporary, final)
            renamed = True
            actual_stat = self._stat_identity(final)
            if actual_stat[0] != actual or actual_stat[-1] != 0o444:
                raise C.EntryV2Refusal(
                    "disk-backed session array cache file identity drift"
                )
            return _ArrayCacheEntry(
                identity, None, None, actual, rows, content_sha256,
                final, actual_stat,
            )
        except BaseException:
            target = final if renamed else temporary
            try:
                target.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    @staticmethod
    def _discard_entry(entry: _ArrayCacheEntry) -> None:
        if entry.durable_product is not None:
            entry.durable_product.close()
            return
        if entry.backing_path is not None:
            try:
                entry.backing_path.unlink(missing_ok=True)
            except OSError as exc:
                raise C.EntryV2Refusal(
                    "cannot remove disk-backed session array cache entry"
                ) from exc

    def _entry_arrays(self, entry: _ArrayCacheEntry) -> tuple[np.ndarray, np.ndarray]:
        if entry.backing_path is None:
            assert entry.continuous is not None and entry.categorical is not None
            return entry.continuous, entry.categorical
        path = entry.backing_path
        try:
            resolved = path.resolve(strict=True)
            actual_stat = self._stat_identity(path)
        except (OSError, FileNotFoundError) as exc:
            raise C.EntryV2Refusal(
                "disk-backed session array cache entry is missing"
            ) from exc
        if (resolved != path or not stat.S_ISREG(path.stat().st_mode)
                or actual_stat != entry.backing_stat):
            raise C.EntryV2Refusal(
                "disk-backed session array cache entry identity drift"
            )
        continuous_bytes = (
            entry.rows * len(CONTINUOUS_FIELDS) * np.dtype(np.float64).itemsize
        )
        continuous = np.memmap(
            path, dtype=np.float64, mode="r", offset=0,
            shape=(entry.rows, len(CONTINUOUS_FIELDS)), order="C",
        )
        categorical = np.memmap(
            path, dtype=np.uint8, mode="r", offset=continuous_bytes,
            shape=(entry.rows, len(CATEGORICAL_FIELDS)), order="C",
        )
        return continuous, categorical

    def get_or_fill(
        self,
        source: "SessionEventSource",
        fill: "Any",
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

    def _load_durable_entry(
        self, source: "SessionEventSource", identity: bytes,
    ) -> _ArrayCacheEntry | None:
        if self.durable_store is None:
            return None
        product = self.durable_store.load(
            "session-arrays", source.durable_identity(),
            MODEL_ARRAYS_CONVERSION_LAW_SHA256,
        )
        if product is None:
            return None
        semantic = product.receipt.get("semantic")
        producer = product.receipt.get("producer")
        expected_semantic = {
            "schema": "entry-v2-session-array-map-v1",
            "continuous_fields": list(CONTINUOUS_FIELDS),
            "categorical_fields": list(CATEGORICAL_FIELDS),
            "rows": source.max_cutoff,
        }
        if semantic != expected_semantic or producer != {
                "schema": "entry-v2-session-array-producer-v1",
                "physical_full_pack_opens": 1,
                "model_array_physical_fills": 1}:
            product.close()
            raise C.EntryV2Refusal("durable session array semantic/provenance drift")
        if (len(product.arrays) != 2
                or product.arrays[0].shape != (
                    source.max_cutoff, len(CONTINUOUS_FIELDS))
                or product.arrays[0].dtype != np.dtype(np.float64)
                or product.arrays[1].shape != (
                    source.max_cutoff, len(CATEGORICAL_FIELDS))
                or product.arrays[1].dtype != np.dtype(np.uint8)):
            product.close()
            raise C.EntryV2Refusal("durable session array descriptor drift")
        logical_bytes = int(sum(value.nbytes for value in product.arrays))
        return _ArrayCacheEntry(
            identity, product.arrays[0], product.arrays[1],
            logical_bytes, source.max_cutoff,
            self._content_sha256(product.arrays[0], product.arrays[1]),
            durable_product=product,
        )

    def publish_verified(
        self,
        source: "SessionEventSource",
        continuous: np.ndarray,
        categorical: np.ndarray,
    ) -> bool:
        """Publish arrays produced while the authoritative pack is already open.

        The caller must have run :meth:`SessionEventSource._validate_arrays`
        against that exact open pack.  This method performs only immutable
        cache identity/capacity accounting; it never opens or re-hashes the
        source.  ``True`` means this call published the entry and ``False``
        means an identical entry was already present.
        """
        key = source.receipt.receipt_sha256
        identity = source.receipt.canonical_bytes()
        planned = self.planned_bytes(source)
        actual = int(continuous.nbytes + categorical.nbytes)
        if actual != planned:
            raise C.EntryV2Refusal("session array cache byte accounting drift")
        if (continuous.flags.writeable or categorical.flags.writeable
                or type(continuous) is not np.ndarray
                or type(categorical) is not np.ndarray):
            raise C.EntryV2Refusal(
                "published session arrays must be immutable owned ndarrays"
            )
        content_sha256 = self._content_sha256(continuous, categorical)
        flight: _ArrayCacheFlight | None = None
        with self._lock:
            if self._closed:
                raise C.EntryV2Refusal("session array cache is closed")
            entry = self._entries.get(key)
            if entry is not None:
                self._assert_identity(entry.identity, identity)
                self._entry_arrays(entry)
                if (entry.byte_count != actual
                        or entry.content_sha256 != content_sha256):
                    raise C.EntryV2Refusal(
                        "duplicate session array publication changed content"
                    )
                return False
            if key in self._flights:
                raise C.EntryV2Refusal(
                    "cannot publish while a session array fill is in flight"
                )
            if self._bytes_used + self._bytes_reserved + actual > self.capacity_bytes:
                raise C.EntryV2Refusal(
                    "session array cache capacity is insufficient"
                )
            flight = _ArrayCacheFlight(identity, actual, self._generation)
            self._flights[key] = flight
            self._bytes_reserved += actual
        entry = None
        inserted = False
        try:
            entry = self._make_entry(
                key, identity, continuous, categorical, source
            )
            with self._lock:
                if self._closed or flight.generation != self._generation:
                    raise C.EntryV2Refusal(
                        "session array cache cleared during publication"
                    )
                self._entries[key] = entry
                self._bytes_used += actual
                inserted = True
            return True
        except BaseException as exc:
            if entry is not None and not inserted:
                self._discard_entry(entry)
            with self._lock:
                flight.error = exc
            raise
        finally:
            with self._lock:
                self._bytes_reserved -= actual
                self._flights.pop(key, None)
                flight.complete.set()

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

    def __enter__(self) -> "SessionArrayCache":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


class SessionSourceMeasurements:
    """Mutable process-local evidence for physical source work.

    Receipt identity remains immutable: these counters describe execution,
    not source content, and are intentionally excluded from equality/hashing.
    """

    def __init__(self) -> None:
        self._physical_full_pack_opens = 0
        self._model_array_physical_fills = 0
        self._header_revalidations = 0
        self._cache_hits = 0
        self._single_full_open_required = False
        self._lock = threading.Lock()

    def require_single_full_open(self) -> None:
        with self._lock:
            if (self._physical_full_pack_opens != 1
                    or self._model_array_physical_fills != 1):
                raise C.EntryV2Refusal(
                    "one-open source did not arrive from one physical pack/fill"
                )
            self._single_full_open_required = True

    def record_full_pack_open(self) -> None:
        with self._lock:
            if self._single_full_open_required and self._physical_full_pack_opens >= 1:
                raise C.EntryV2Refusal("second physical full-pack open is forbidden")
            self._physical_full_pack_opens += 1

    def assert_full_pack_open_allowed(self) -> None:
        with self._lock:
            if self._single_full_open_required and self._physical_full_pack_opens >= 1:
                raise C.EntryV2Refusal("second physical full-pack open is forbidden")

    def record_model_array_fill(self) -> None:
        with self._lock:
            if (self._single_full_open_required
                    and self._model_array_physical_fills >= 1):
                raise C.EntryV2Refusal("second physical model-array fill is forbidden")
            self._model_array_physical_fills += 1

    def record_cache_hit(self) -> None:
        with self._lock:
            self._cache_hits += 1

    def record_header_revalidation(self) -> None:
        with self._lock:
            self._header_revalidations += 1

    def snapshot(self) -> Mapping[str, int | bool]:
        with self._lock:
            return MappingProxyType({
                "physical_full_pack_opens": self._physical_full_pack_opens,
                "model_array_physical_fills": self._model_array_physical_fills,
                "header_revalidations": self._header_revalidations,
                "array_cache_hits": self._cache_hits,
                "single_full_open_required": self._single_full_open_required,
            })


@dataclass(frozen=True, slots=True)
class SessionStreamReceipt:
    """Canonical, timestamp-free lineage for one bounded conversion."""

    qre2_path: str
    source_sha256: str
    sidecar_path: str
    sidecar_sha256: str
    asset: str
    d8: int
    trading_day: int
    locked_iid: int
    open_utc: int
    close_utc: int
    pack_event_count: int
    materialized_event_count: int
    source_event_byte_start: int
    source_event_byte_end_exclusive: int
    source_event_byte_count: int
    conversion_law_sha256: str

    def __post_init__(self) -> None:
        if self.d8 != self.trading_day:
            raise C.EntryV2Refusal("session-stream receipt trading_day/d8 drift")
        if self.source_event_byte_start != HEADER_BYTES:
            raise C.EntryV2Refusal("session-stream receipt event-byte start drift")
        expected_end = HEADER_BYTES + self.materialized_event_count * ROW_BYTES
        if (self.source_event_byte_end_exclusive != expected_end
                or self.source_event_byte_count != expected_end - HEADER_BYTES):
            raise C.EntryV2Refusal("session-stream receipt event-byte range drift")
        if not 0 <= self.materialized_event_count <= self.pack_event_count:
            raise C.EntryV2Refusal("session-stream receipt event count drift")
        if self.conversion_law_sha256 != MODEL_ARRAYS_CONVERSION_LAW_SHA256:
            raise C.EntryV2Refusal("session-stream receipt conversion-law drift")

    def _payload(self) -> dict[str, Any]:
        return {
            "schema": SESSION_STREAM_RECEIPT_SCHEMA,
            "qre2_path": self.qre2_path,
            "source_sha256": self.source_sha256,
            "sidecar_path": self.sidecar_path,
            "sidecar_sha256": self.sidecar_sha256,
            "asset": self.asset,
            "d8": self.d8,
            "trading_day": self.trading_day,
            "locked_iid": self.locked_iid,
            "open_utc": self.open_utc,
            "close_utc": self.close_utc,
            "pack_event_count": self.pack_event_count,
            "max_cutoff": self.materialized_event_count,
            "materialized_event_count": self.materialized_event_count,
            "source_header_byte_range": [0, HEADER_BYTES],
            "source_event_byte_range": [
                self.source_event_byte_start,
                self.source_event_byte_end_exclusive,
            ],
            "source_event_byte_count": self.source_event_byte_count,
            "row_bytes": ROW_BYTES,
            "conversion_law_schema": MODEL_ARRAYS_CONVERSION_LAW["schema"],
            "conversion_law_sha256": self.conversion_law_sha256,
        }

    @property
    def receipt_sha256(self) -> str:
        return C.object_sha256(self._payload())

    def as_dict(self) -> dict[str, Any]:
        """Return a fresh JSON-compatible receipt with a self-checking hash."""
        payload = self._payload()
        payload["receipt_sha256"] = self.receipt_sha256
        return payload

    def canonical_bytes(self) -> bytes:
        return C.canonical_bytes(self.as_dict())


@dataclass(frozen=True, slots=True)
class SessionEventSource:
    """Immutable external pin for exactly one QRE2 asset-session."""

    qre2_path: Path
    source_sha256: str
    sidecar_sha256: str
    asset: str
    d8: int
    locked_iid: int
    open_utc: int
    close_utc: int
    event_count: int
    max_cutoff: int
    source_size_bytes: int
    source_device: int
    source_inode: int
    source_mtime_ns: int
    source_ctime_ns: int
    array_cache: SessionArrayCache | None = field(
        default=None, compare=False, repr=False
    )
    measurements: SessionSourceMeasurements = field(
        default_factory=SessionSourceMeasurements, init=False,
        compare=False, repr=False
    )

    def __post_init__(self) -> None:
        d8 = _exact_int(self.d8, "d8")
        C.guard_date(d8)
        asset = str(self.asset).upper()
        if asset not in C.ASSET_INDEX:
            raise C.EntryV2Refusal(f"unknown session-stream asset: {self.asset!r}")
        path = _canonical_source_path(self.qre2_path, d8)
        iid = _exact_int(self.locked_iid, "locked_iid")
        open_utc = _exact_int(self.open_utc, "open_utc")
        close_utc = _exact_int(self.close_utc, "close_utc")
        event_count = _exact_int(self.event_count, "event_count")
        max_cutoff = _exact_int(self.max_cutoff, "max_cutoff")
        source_size = _exact_int(self.source_size_bytes, "source_size_bytes")
        source_device = _exact_int(self.source_device, "source_device")
        source_inode = _exact_int(self.source_inode, "source_inode")
        source_mtime = _exact_int(self.source_mtime_ns, "source_mtime_ns")
        source_ctime = _exact_int(self.source_ctime_ns, "source_ctime_ns")
        if self.array_cache is not None and not isinstance(
                self.array_cache, SessionArrayCache):
            raise C.EntryV2Refusal("array_cache must be a SessionArrayCache")
        if not isinstance(self.measurements, SessionSourceMeasurements):
            raise C.EntryV2Refusal("measurements must be SessionSourceMeasurements")
        if iid < 0 or open_utc <= 0 or close_utc <= open_utc:
            raise C.EntryV2Refusal("invalid pinned QRE2 session clock/IID")
        if event_count < 0 or not 0 <= max_cutoff <= event_count:
            raise C.EntryV2Refusal(
                "max_cutoff must lie inside the pinned event count"
            )
        expected_size = HEADER_BYTES + event_count * ROW_BYTES
        if (source_size != expected_size or source_device < 0 or source_inode <= 0
                or source_mtime <= 0 or source_ctime <= 0):
            raise C.EntryV2Refusal("invalid verified QRE2 source stat identity")
        object.__setattr__(self, "qre2_path", path)
        object.__setattr__(self, "source_sha256",
                           _sha256(self.source_sha256, "source"))
        object.__setattr__(self, "sidecar_sha256",
                           _sha256(self.sidecar_sha256, "sidecar"))
        object.__setattr__(self, "asset", asset)
        object.__setattr__(self, "d8", d8)
        object.__setattr__(self, "locked_iid", iid)
        object.__setattr__(self, "open_utc", open_utc)
        object.__setattr__(self, "close_utc", close_utc)
        object.__setattr__(self, "event_count", event_count)
        object.__setattr__(self, "max_cutoff", max_cutoff)
        object.__setattr__(self, "source_size_bytes", source_size)
        object.__setattr__(self, "source_device", source_device)
        object.__setattr__(self, "source_inode", source_inode)
        object.__setattr__(self, "source_mtime_ns", source_mtime)
        object.__setattr__(self, "source_ctime_ns", source_ctime)

    @property
    def trading_day(self) -> int:
        """Explicit asset-day key retained for downstream aggregation."""
        return self.d8

    @property
    def source_hash(self) -> str:
        """Alias matching :class:`RawPrefixRef` terminology."""
        return self.source_sha256

    @property
    def sidecar_path(self) -> Path:
        return self.qre2_path.with_suffix(self.qre2_path.suffix + ".json")

    @property
    def receipt(self) -> SessionStreamReceipt:
        start = HEADER_BYTES
        end = start + self.max_cutoff * ROW_BYTES
        return SessionStreamReceipt(
            qre2_path=str(self.qre2_path),
            source_sha256=self.source_sha256,
            sidecar_path=str(self.sidecar_path),
            sidecar_sha256=self.sidecar_sha256,
            asset=self.asset,
            d8=self.d8,
            trading_day=self.trading_day,
            locked_iid=self.locked_iid,
            open_utc=self.open_utc,
            close_utc=self.close_utc,
            pack_event_count=self.event_count,
            materialized_event_count=self.max_cutoff,
            source_event_byte_start=start,
            source_event_byte_end_exclusive=end,
            source_event_byte_count=end - start,
            conversion_law_sha256=MODEL_ARRAYS_CONVERSION_LAW_SHA256,
        )

    def durable_identity(self) -> Mapping[str, Any]:
        """Exact immutable source identity used by the persistent array key."""
        return MappingProxyType({
            "schema": "entry-v2-durable-session-source-v1",
            "session_stream_receipt": self.receipt.as_dict(),
            "source_stat": {
                "size_bytes": self.source_size_bytes,
                "device": self.source_device,
                "inode": self.source_inode,
                "mtime_ns": self.source_mtime_ns,
                "ctime_ns": self.source_ctime_ns,
            },
        })

    def _verify_canonical_file(self, path: Path, name: str) -> None:
        _guard_path_components(path)
        try:
            resolved = path.resolve(strict=True)
        except (FileNotFoundError, OSError) as exc:
            raise C.EntryV2Refusal(f"missing/unreadable pinned {name}: {path}") from exc
        if resolved != path:
            raise C.EntryV2Refusal(f"pinned {name} path identity drift: {path}")
        if not path.is_file():
            raise C.EntryV2Refusal(f"pinned {name} is not a regular file: {path}")

    def _read_and_verify_sidecar(self) -> Mapping[str, Any]:
        path = self.sidecar_path
        self._verify_canonical_file(path, "QRE2 sidecar")
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise C.EntryV2Refusal(f"cannot read pinned QRE2 sidecar: {path}") from exc
        actual = hashlib.sha256(raw).hexdigest()
        if actual != self.sidecar_sha256:
            raise C.EntryV2Refusal(
                f"event sidecar hash drift: expected={self.sidecar_sha256} actual={actual}"
            )
        obj = _strict_json_object(raw, "event sidecar")
        if obj.get("schema") != SIDECAR_SCHEMA or obj.get("status") != "READY":
            raise C.EntryV2Refusal("event sidecar schema/status identity drift")
        if obj.get("asset") != self.asset:
            raise C.EntryV2Refusal("event sidecar identity drift: asset")
        for name, expected in (
            ("asset_idx", C.ASSET_INDEX[self.asset]),
            ("d8", self.d8),
            ("locked_iid", self.locked_iid),
            ("open_utc", self.open_utc),
            ("close_utc", self.close_utc),
            ("event_count", self.event_count),
        ):
            _identity_int(obj, name, expected)
        if obj.get("event_pack_sha256") != self.source_sha256:
            raise C.EntryV2Refusal("event sidecar source-hash identity drift")
        source_hashes = obj.get("source_hashes")
        if (not isinstance(source_hashes, dict)
                or source_hashes.get("event_pack_sha256") != self.source_sha256):
            raise C.EntryV2Refusal("event sidecar nested source-hash identity drift")

        window = obj.get("record_window")
        if not isinstance(window, dict):
            raise C.EntryV2Refusal("event sidecar record window missing")
        try:
            start = _exact_int(window["start_d8"], "record_window.start_d8")
            end = _exact_int(
                window["end_d8_exclusive"], "record_window.end_d8_exclusive"
            )
        except KeyError as exc:
            raise C.EntryV2Refusal("event sidecar record window incomplete") from exc
        C.guard_decode_window(start, end)
        if not start <= self.d8 < end:
            raise C.EntryV2Refusal("event sidecar window excludes pinned d8")

        binary_file = obj.get("binary_file")
        if not isinstance(binary_file, str) or not binary_file:
            raise C.EntryV2Refusal("event sidecar binary_file missing")
        binary_relative = Path(binary_file)
        _guard_path_components(binary_relative)
        if (binary_relative.is_absolute() or ".." in binary_relative.parts
                or binary_relative.name != self.qre2_path.name
                or len(binary_relative.parts) < 2
                or binary_relative.parts[-2] != self.asset):
            raise C.EntryV2Refusal("event sidecar binary_file identity drift")
        if obj.get("cutoff_rule") != CUTOFF_RULE:
            raise C.EntryV2Refusal("event sidecar cutoff law identity drift")
        clock_contract = {
            "session_assignment_clock": "ts_recv",
            "symbology_date_clock": "floor_utc(ts_recv)",
            "causal_visibility_clock": "IndexTs/ts_recv",
            "exchange_feature_clock": "ts_event",
            "equal_receive_time": "future",
            "tie_order": "ordered_input_manifest_then_dbn_decode_ordinal",
        }
        for name, expected in clock_contract.items():
            if obj.get(name) != expected:
                raise C.EntryV2Refusal(
                    f"event sidecar clock law identity drift: {name}"
                )

        binary_schema = obj.get("binary_schema")
        if not isinstance(binary_schema, dict):
            raise C.EntryV2Refusal("event sidecar binary schema missing")
        expected_schema = {
            "magic": MAGIC.decode("ascii"),
            "byte_order": "little",
            "header_bytes": HEADER_BYTES,
            "row_bytes": ROW_BYTES,
            "layout": "packed_array_of_structs",
        }
        for name, expected in expected_schema.items():
            if binary_schema.get(name) != expected:
                raise C.EntryV2Refusal(
                    f"event sidecar binary schema identity drift: {name}"
                )
        arrays = binary_schema.get("arrays")
        if not isinstance(arrays, list):
            raise C.EntryV2Refusal("event sidecar array layout missing")
        actual_layout: set[tuple[str, str, int]] = set()
        for item in arrays:
            if not isinstance(item, dict) or set(item) != {
                    "name", "dtype", "offset_bytes"}:
                raise C.EntryV2Refusal("event sidecar array descriptor malformed")
            try:
                descriptor = (
                    str(item["name"]),
                    str(item["dtype"]),
                    _exact_int(item["offset_bytes"], "array offset"),
                )
            except KeyError as exc:  # defensive; exact-key check normally catches it
                raise C.EntryV2Refusal(
                    "event sidecar array descriptor incomplete"
                ) from exc
            if descriptor in actual_layout:
                raise C.EntryV2Refusal("duplicate event sidecar array descriptor")
            actual_layout.add(descriptor)
        if frozenset(actual_layout) != _SIDECAR_LAYOUT:
            raise C.EntryV2Refusal("event sidecar array layout identity drift")
        return obj

    def _verify_source_path(self) -> None:
        self._verify_canonical_file(self.qre2_path, "QRE2 source")
        stat = self.qre2_path.stat()
        actual = (
            stat.st_size,
            stat.st_dev,
            stat.st_ino,
            stat.st_mtime_ns,
            stat.st_ctime_ns,
        )
        expected = (
            self.source_size_bytes,
            self.source_device,
            self.source_inode,
            self.source_mtime_ns,
            self.source_ctime_ns,
        )
        if actual != expected:
            raise C.EntryV2Refusal("QRE2 source stat identity drift")

    def _open_verified_pack(self) -> EventPack:
        # The corpus trust boundary already hashed the complete QRE2 once.  A
        # materialization rechecks its immutable path/stat/header/sidecar pins,
        # but never performs another full-file SHA pass.
        self._read_and_verify_sidecar()
        self._verify_source_path()

        # Construct explicitly so even an exception late in EventPack.__init__
        # can close a partially created memmap.  A normal ``EventPack(...)``
        # assignment cannot retain the object when __init__ raises.
        pack = EventPack.__new__(EventPack)
        try:
            EventPack.__init__(pack, self.qre2_path, verify_hash=False,
                               require_sidecar=True)
            header = pack.header
            actual_identity = (
                pack.path,
                header.asset,
                header.d8,
                header.locked_iid,
                header.open_utc,
                header.close_utc,
                header.n_events,
            )
            expected_identity = (
                self.qre2_path,
                self.asset,
                self.d8,
                self.locked_iid,
                self.open_utc,
                self.close_utc,
                self.event_count,
            )
            if actual_identity != expected_identity:
                raise C.EntryV2Refusal("QRE2 header/path identity drift")
            if self.max_cutoff > header.n_events:
                raise C.EntryV2Refusal("max_cutoff exceeds verified QRE2 event count")
            # Re-hash the exact sidecar path loaded by EventPack after its open.
            if C.file_sha256(self.sidecar_path) != self.sidecar_sha256:
                raise C.EntryV2Refusal("event sidecar changed during pack open")
        except BaseException:
            self._close_pack(pack)
            raise
        return pack

    def _verify_cached_header(self) -> None:
        """Recheck the exact 60-byte binary identity without mapping rows."""
        self._read_and_verify_sidecar()
        self._verify_source_path()
        try:
            with self.qre2_path.open("rb") as handle:
                raw = handle.read(HEADER_BYTES)
        except OSError as exc:
            raise C.EntryV2Refusal("cannot read pinned QRE2 header") from exc
        if len(raw) != HEADER_BYTES:
            raise C.EntryV2Refusal("truncated pinned QRE2 header")
        try:
            values = HEADER.unpack(raw)
        except Exception as exc:
            raise C.EntryV2Refusal("invalid pinned QRE2 header") from exc
        actual = values
        expected = (
            MAGIC, VERSION, C.ASSET_INDEX[self.asset], self.d8,
            self.locked_iid, self.open_utc, self.close_utc,
            self.event_count, ROW_BYTES, 0,
        )
        if actual != expected:
            raise C.EntryV2Refusal("QRE2 header/path identity drift")

    @staticmethod
    def _close_pack(pack: EventPack) -> None:
        """Close even a pack whose constructor failed after mapping rows."""
        rows = getattr(pack, "rows", None)
        if rows is not None:
            pack.close()

    @staticmethod
    def _validate_arrays(pack: EventPack, continuous: np.ndarray,
                         categorical: np.ndarray, rows: int) -> None:
        if (type(continuous) is not np.ndarray
                or continuous.shape != (rows, len(CONTINUOUS_FIELDS))
                or continuous.dtype != np.dtype(np.float64)
                or not continuous.flags.c_contiguous):
            raise C.EntryV2Refusal("model continuous array violates conversion law")
        if (type(categorical) is not np.ndarray
                or categorical.shape != (rows, len(CATEGORICAL_FIELDS))
                or categorical.dtype != np.dtype(np.uint8)
                or not categorical.flags.c_contiguous):
            raise C.EntryV2Refusal("model categorical array violates conversion law")
        if (np.shares_memory(continuous, pack.rows)
                or np.shares_memory(categorical, pack.rows)):
            raise C.EntryV2Refusal("model arrays retain the QRE2 memory map")

    def publish_from_open_pack(self, pack: EventPack) -> bool:
        """Convert and cache this bounded prefix from an already-open pack.

        This is the one-open corpus/diagnostic boundary: the same verified
        mmap supplies both the compact truth plane and the learner prefix.
        Later training accesses are cache hits that recheck only the pinned
        sidecar, stat identity, and fixed header.
        """
        if self.array_cache is None:
            return False
        header = pack.header
        if (pack.path, header.asset, header.d8, header.locked_iid,
                header.open_utc, header.close_utc, header.n_events) != (
                self.qre2_path, self.asset, self.d8, self.locked_iid,
                self.open_utc, self.close_utc, self.event_count):
            raise C.EntryV2Refusal(
                "open pack identity differs from session array source"
            )
        self.measurements.record_full_pack_open()
        arrays = pack.model_arrays(stop=self.max_cutoff)
        self.measurements.record_model_array_fill()
        self._validate_arrays(pack, *arrays, self.max_cutoff)
        arrays[0].setflags(write=False)
        arrays[1].setflags(write=False)
        self._verify_source_path()
        return self.array_cache.publish_verified(self, *arrays)

    @contextmanager
    def open_arrays(self) -> Iterator[tuple[np.ndarray, np.ndarray]]:
        """Yield bounded raw NumPy arrays and always close the QRE2 memmap."""
        if self.array_cache is not None:
            def fill() -> tuple[np.ndarray, np.ndarray]:
                pack: EventPack | None = None
                try:
                    self.measurements.assert_full_pack_open_allowed()
                    pack = self._open_verified_pack()
                    self.measurements.record_full_pack_open()
                    arrays = pack.model_arrays(stop=self.max_cutoff)
                    self.measurements.record_model_array_fill()
                    self._validate_arrays(pack, *arrays, self.max_cutoff)
                    self._verify_source_path()
                    return arrays
                finally:
                    if pack is not None:
                        self._close_pack(pack)

            continuous, categorical, hit = self.array_cache.get_or_fill(
                self, fill
            )
            if hit:
                self._verify_cached_header()
                self.measurements.record_header_revalidation()
                self.measurements.record_cache_hit()
            try:
                yield continuous, categorical
            finally:
                if hit:
                    self._verify_source_path()
            return
        pack: EventPack | None = None
        continuous: np.ndarray | None = None
        categorical: np.ndarray | None = None
        try:
            self.measurements.assert_full_pack_open_allowed()
            pack = self._open_verified_pack()
            self.measurements.record_full_pack_open()
            continuous, categorical = pack.model_arrays(stop=self.max_cutoff)
            self.measurements.record_model_array_fill()
            self._validate_arrays(pack, continuous, categorical, self.max_cutoff)
            self._verify_source_path()
            yield continuous, categorical
        finally:
            # Drop the context's own array references before closing.  Returned
            # arrays own their bytes and may legitimately outlive the context.
            continuous = None
            categorical = None
            if pack is not None:
                self._close_pack(pack)

    def _validate_batch_reference(self, batch: "EntrySessionSpec") -> None:
        if not batch.examples:
            raise C.EntryV2Refusal("cannot stream an empty EntrySessionSpec")
        if any((example.asset, example.trading_day, example.locked_iid) != (
                self.asset, self.d8, self.locked_iid) for example in batch.examples):
            raise C.EntryV2Refusal("EntrySessionSpec belongs to another QRE2 session")
        for example in batch.examples:
            ref = example.raw_prefix_ref
            if (ref.shard != str(self.qre2_path)
                    or ref.source_hash != self.source_sha256
                    or ref.event_start_index != 0
                    or ref.event_end_index != ref.event_count
                    or ref.event_count > self.max_cutoff):
                raise C.EntryV2Refusal(
                    "EntrySessionSpec raw-prefix reference differs from stream pin"
                )
        raw_cutoffs = batch.candidate_cutoffs.detach().cpu().numpy()
        if raw_cutoffs.dtype.kind not in "iu":
            raise C.EntryV2Refusal("EntrySessionSpec candidate cutoffs are not integer")
        cutoffs = raw_cutoffs.astype(np.int64, copy=False)
        if cutoffs.shape != (len(batch.examples),):
            raise C.EntryV2Refusal("EntrySessionSpec candidate cutoffs are malformed")
        if cutoffs.size == 0 or int(cutoffs.max()) > self.max_cutoff:
            raise C.EntryV2Refusal(
                "EntrySessionSpec cutoff exceeds all-candidate stream pin"
            )

    @contextmanager
    def open_batch(self, template: "EntrySessionSpec") -> Iterator["EntrySessionBatch"]:
        """Yield one bounded materialized batch from metadata-only input."""
        from .train import EntrySessionBatch, EntrySessionSpec
        import torch

        if not isinstance(template, EntrySessionSpec):
            raise C.EntryV2Refusal("open_batch requires an EntrySessionSpec")
        template.validate()
        self._validate_batch_reference(template)
        materialized: EntrySessionBatch | None = None
        with self.open_arrays() as (continuous, categorical):
            device = template.candidate_features.device
            event_continuous = torch.from_numpy(continuous)
            event_categorical = torch.from_numpy(categorical)
            # The first three frozen QRE2 continuous fields are the exact
            # receive-session second/microsecond/nanosecond decomposition.
            # Recompose int64 absolute clocks before normalization; never infer
            # clocks from rounded GPU tensors.
            if tuple(CONTINUOUS_FIELDS[:3]) != (
                    "receive_time_sec", "receive_time_microsecond",
                    "receive_time_nanosecond"):
                raise C.EntryV2Refusal("frozen receive-clock field order changed")
            relative = (
                continuous[:, 0].astype(np.int64, copy=False) * 1_000_000_000
                + continuous[:, 1].astype(np.int64, copy=False) * 1_000
                + continuous[:, 2].astype(np.int64, copy=False)
            )
            receive_clock_ns = torch.from_numpy(
                relative + np.int64(self.open_utc) * np.int64(1_000_000_000)
            )
            if device.type != "cpu":
                event_continuous = event_continuous.to(device)
                event_categorical = event_categorical.to(device)
                receive_clock_ns = receive_clock_ns.to(device)
            materialized = EntrySessionBatch(
                examples=template.examples,
                event_continuous=event_continuous,
                event_categorical=event_categorical,
                candidate_cutoffs=template.candidate_cutoffs,
                candidate_features=template.candidate_features,
                context_values=template.context_values,
                context_type_ids=template.context_type_ids,
                context_valid=template.context_valid,
                self_supervised=template.self_supervised,
                receive_clock_ns=receive_clock_ns,
                static_features=template.static_features,
                selected_horizon_value=template.selected_horizon_value,
                selected_horizon_valid=template.selected_horizon_valid,
                selected_horizon_schema_sha256=(
                    template.selected_horizon_schema_sha256
                ),
            )
            materialized.validate()
            try:
                yield materialized
            finally:
                materialized = None

    @overload
    def materialize(self, batch: None = None
                    ) -> Iterator[tuple[np.ndarray, np.ndarray]]: ...

    @overload
    def materialize(self, batch: "EntrySessionSpec"
                    ) -> Iterator["EntrySessionBatch"]: ...

    @contextmanager
    def materialize(self, batch: "EntrySessionSpec | None" = None
                    ) -> Iterator[tuple[np.ndarray, np.ndarray] | "EntrySessionBatch"]:
        """Unified context-manager spelling for raw-array or batch consumers."""
        if batch is None:
            with self.open_arrays() as arrays:
                yield arrays
        else:
            with self.open_batch(batch) as materialized:
                yield materialized


__all__ = [
    "CUTOFF_RULE",
    "MODEL_ARRAYS_CONVERSION_LAW",
    "MODEL_ARRAYS_CONVERSION_LAW_SHA256",
    "SESSION_STREAM_RECEIPT_SCHEMA",
    "SessionArrayCache",
    "SessionEventSource",
    "SessionSourceMeasurements",
    "SessionStreamReceipt",
]
