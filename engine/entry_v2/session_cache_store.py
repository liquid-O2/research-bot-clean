"""Durable fill and publish methods for SessionArrayCache."""

from __future__ import annotations

import os
import stat
from typing import Any, Mapping, Protocol

import numpy as np

from . import common as C
from .event_pack import CATEGORICAL_FIELDS, CONTINUOUS_FIELDS
from .session_receipt import (
    MODEL_ARRAYS_CONVERSION_LAW_SHA256,
    SessionSourceMeasurements,
    SessionStreamReceipt,
)


class SessionCacheSource(Protocol):
    max_cutoff: int
    measurements: SessionSourceMeasurements

    @property
    def receipt(self) -> SessionStreamReceipt: ...

    def durable_identity(self) -> Mapping[str, Any]: ...


class SessionCacheStoreMixin:
    """Disk and durable-store fill/publish used by SessionArrayCache."""

    def _make_entry(self, key: str, identity: bytes,
                    continuous: np.ndarray,
                    categorical: np.ndarray,
                    source: SessionCacheSource) -> "_ArrayCacheEntry":
        from .session_cache import _ArrayCacheEntry

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
    def _discard_entry(entry: "_ArrayCacheEntry") -> None:
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

    def _entry_arrays(self, entry: "_ArrayCacheEntry") -> tuple[np.ndarray, np.ndarray]:
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

    def _load_durable_entry(
        self, source: SessionCacheSource, identity: bytes,
    ) -> "_ArrayCacheEntry | None":
        from .session_cache import _ArrayCacheEntry

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
        source: SessionCacheSource,
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
        from .session_cache import _ArrayCacheFlight

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
        flight: "_ArrayCacheFlight | None" = None
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
