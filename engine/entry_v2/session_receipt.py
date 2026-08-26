"""Conversion-law constants and session-stream receipts."""

from __future__ import annotations

from dataclasses import dataclass
import threading
from types import MappingProxyType
from typing import Any, Mapping

from . import common as C
from .event_pack import (
    CATEGORY_SIZES,
    CATEGORICAL_FIELDS,
    CONTINUOUS_FIELDS,
    HEADER_BYTES,
    ROW_BYTES,
)


SESSION_STREAM_RECEIPT_SCHEMA = "entry-v2-session-stream-receipt-v3"
SIDECAR_SCHEMA = "QRE2EVENTMETA2"
CUTOFF_RULE = (
    "lower_bound(ts_recv_ns,decision_ts_ns); "
    "equal receive-time batch is future"
)

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
