#!/usr/bin/env python3
"""Zero-copy reader and tensorizer for causal ``QRE2EVT2`` event packs.

The C++ substrate writes one little-endian, packed file per asset-session.  A
reader authorizes the date from the basename *before opening the payload*, then
checks the on-disk header, row layout, monotone receive timestamps and sidecar
lineage.  Candidate cutoffs are always
``lower_bound(ts_recv_ns, decision_ts_ns)``; an availability timestamp exactly
at the decision is therefore future data.  Exchange time is retained as an
exact feature but never controls causal visibility.

No aggregation happens here.  ``model_arrays`` exposes every row.  Absolute
epoch nanoseconds remain uint64 in ``rows``; the floating model view
losslessly splits relative time into GPU-safe second/microsecond/nanosecond
components.  Contemporary epoch nanoseconds are not exactly representable in
float64, and a large relative-nanosecond scalar would lose one-nanosecond
differences after float32/BF16 normalization.  Categorical bytes remain exact.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import struct
from typing import Mapping, Sequence

import numpy as np

from . import common as C


MAGIC = b"QRE2EVT2"
VERSION = 2
HEADER_BYTES = 60
ROW_BYTES = 76
HEADER = struct.Struct("<8sIB3xiqqqQII")

EVENT_DTYPE = np.dtype({
    "names": (
        "ts_recv_ns", "ts_event_ns", "price", "bid_px", "ask_px", "size",
        "bid_sz", "ask_sz", "bid_ct", "ask_ct", "sequence",
        "ts_in_delta", "receive_session_sec", "action", "side", "flags", "depth",
    ),
    "formats": (
        "<u8", "<u8", "<i8", "<i8", "<i8", "<u4", "<u4", "<u4",
        "<u4", "<u4", "<u4", "<i4", "<i4", "u1", "u1", "u1", "u1",
    ),
    "offsets": (0, 8, 16, 24, 32, 40, 44, 48, 52, 56, 60, 64, 68,
                72, 73, 74, 75),
    "itemsize": ROW_BYTES,
})

CONTINUOUS_FIELDS = (
    "receive_time_sec", "receive_time_microsecond", "receive_time_nanosecond",
    "recv_minus_event_microsecond", "recv_minus_event_nanosecond",
    "price", "size", "sequence", "bid_px", "ask_px",
    "bid_sz", "ask_sz", "bid_ct", "ask_ct", "ts_in_delta",
    "receive_session_sec",
)
UNDEF_PRICE = np.iinfo(np.int64).max
CATEGORICAL_FIELDS = (
    "action", "side", "flags", "depth", "price_undef_mask",
)
CATEGORY_SIZES = (256, 256, 256, 256, 8)


@dataclass(frozen=True, slots=True)
class EventPackHeader:
    asset: str
    d8: int
    locked_iid: int
    open_utc: int
    close_utc: int
    n_events: int
    row_bytes: int

    @property
    def open_ns(self) -> int:
        return self.open_utc * 1_000_000_000

    @property
    def close_ns(self) -> int:
        return self.close_utc * 1_000_000_000


class EventPack:
    """Validated memory-mapped event pack.

    The memmap deliberately stays structured: callers can build a session
    batch without copying the 40--100 MB source pack.  ``verify_hash=True`` is
    intended for stage boundaries; repeated training epochs rely on the
    already-pinned sidecar hash rather than re-hashing the file.
    """

    def __init__(self, path: os.PathLike[str] | str, *,
                 permit: C.FinalExamPermit | None = None,
                 verify_hash: bool = False,
                 require_sidecar: bool = True) -> None:
        self.path = Path(path).resolve()
        dates = C.dates_in_basename(self.path)
        if len(dates) != 1:
            raise C.EntryV2Refusal(
                f"event pack basename must contain exactly one guarded YYYYMMDD: {self.path}")
        C.guard_date(dates[0], permit)
        if not self.path.is_file():
            raise C.EntryV2Refusal(f"event pack missing: {self.path}")

        with self.path.open("rb") as fh:
            raw = fh.read(HEADER_BYTES)
        if len(raw) != HEADER_BYTES:
            raise C.EntryV2Refusal(f"truncated event header: {self.path}")
        (magic, version, asset_idx, d8, iid, open_utc, close_utc,
         n_events, row_bytes, reserved) = HEADER.unpack(raw)
        if magic != MAGIC or version != VERSION or reserved != 0:
            raise C.EntryV2Refusal(
                f"unknown/corrupt event pack header: magic={magic!r} version={version}")
        if not 0 <= asset_idx < len(C.ASSETS):
            raise C.EntryV2Refusal(f"event pack asset index invalid: {asset_idx}")
        asset = C.ASSETS[asset_idx]
        if int(d8) != dates[0]:
            raise C.EntryV2Refusal(
                f"event pack date/header mismatch: basename={dates[0]} header={d8}")
        C.guard_date(int(d8), permit)
        if row_bytes != ROW_BYTES or iid < 0 or open_utc <= 0 or close_utc <= open_utc:
            raise C.EntryV2Refusal("event pack schema/session fields are invalid")
        expected = HEADER_BYTES + int(n_events) * ROW_BYTES
        actual = self.path.stat().st_size
        if actual != expected:
            raise C.EntryV2Refusal(
                f"event pack length mismatch: expected={expected} actual={actual}")
        self.header = EventPackHeader(asset, int(d8), int(iid), int(open_utc),
                                      int(close_utc), int(n_events), int(row_bytes))
        self.rows = np.memmap(self.path, mode="r", dtype=EVENT_DTYPE,
                              offset=HEADER_BYTES, shape=(int(n_events),))
        self.sidecar = self._load_sidecar(require_sidecar)
        self._validate_rows()
        if verify_hash:
            expected_hash = str(self.sidecar.get("event_pack_sha256", ""))
            if not expected_hash:
                expected_hash = str(self.sidecar.get("output_sha256", ""))
            got = C.file_sha256(self.path)
            if expected_hash != got:
                raise C.EntryV2Refusal(
                    f"event pack hash mismatch: expected={expected_hash!r} got={got}")

    def _sidecar_path(self) -> Path:
        # Production writes ``YYYYMMDD.qre2.json`` beside ``YYYYMMDD.qre2``.
        return self.path.with_suffix(self.path.suffix + ".json")

    def _load_sidecar(self, required: bool) -> Mapping[str, object]:
        p = self._sidecar_path()
        if not p.is_file():
            alt = self.path.with_suffix(".json")
            p = alt if alt.is_file() else p
        if not p.is_file():
            if required:
                raise C.EntryV2Refusal(f"event pack sidecar missing: {p}")
            return {}
        C.guard_payload(p)
        obj = json.loads(p.read_text())
        if obj.get("schema") != "QRE2EVENTMETA2":
            raise C.EntryV2Refusal("event sidecar schema is not QRE2EVENTMETA2")
        for key, expected in (("asset", self.header.asset),
                              ("d8", self.header.d8),
                              ("locked_iid", self.header.locked_iid),
                              ("event_count", self.header.n_events)):
            if key in obj and obj[key] != expected:
                raise C.EntryV2Refusal(
                    f"event sidecar mismatch for {key}: {obj[key]!r} != {expected!r}")
        clock_contract = {
            "session_assignment_clock": "ts_recv",
            "symbology_date_clock": "floor_utc(ts_recv)",
            "causal_visibility_clock": "IndexTs/ts_recv",
            "exchange_feature_clock": "ts_event",
            "equal_receive_time": "future",
            "tie_order": "ordered_input_manifest_then_dbn_decode_ordinal",
        }
        for key, expected in clock_contract.items():
            if obj.get(key) != expected:
                raise C.EntryV2Refusal(
                    f"event sidecar clock law mismatch for {key}"
                )
        return obj

    def _validate_rows(self) -> None:
        r = self.rows
        if r.size == 0:
            return
        ts = r["ts_recv_ns"]
        if int(ts[0]) < self.header.open_ns or int(ts[-1]) >= self.header.close_ns:
            raise C.EntryV2Refusal(
                "event receive timestamps fall outside [session open, close)"
            )
        if bool(np.any(ts[1:] < ts[:-1])):
            raise C.EntryV2Refusal(
                "event receive timestamps are not nondecreasing"
            )
        sec = r["receive_session_sec"]
        if int(sec.min()) < 0 or int(sec.max()) >= self.header.close_utc - self.header.open_utc:
            raise C.EntryV2Refusal("receive_session_sec outside session clock")
        expected_sec = (
            (ts.astype(np.uint64, copy=False) - np.uint64(self.header.open_ns))
            // np.uint64(1_000_000_000)
        ).astype(np.int64, copy=False)
        if not np.array_equal(sec.astype(np.int64, copy=False), expected_sec):
            raise C.EntryV2Refusal(
                "receive_session_sec does not equal floor((ts_recv-open)/1s)"
            )

    def cutoff(self, decision_ts_ns: int) -> int:
        decision = int(decision_ts_ns)
        if not self.header.open_ns <= decision <= self.header.close_ns:
            raise C.EntryV2Refusal(
                f"decision outside session: {decision} not in "
                f"[{self.header.open_ns},{self.header.close_ns}]")
        # NumPy promotes a Python/int64 scalar against uint64 through float64
        # on this build, losing nanoseconds at contemporary epoch magnitudes.
        # The explicit uint64 cast is therefore part of the exact clock law.
        return int(np.searchsorted(self.rows["ts_recv_ns"], np.uint64(decision),
                                   side="left"))

    def cutoffs(self, decision_ts_ns: Sequence[int] | np.ndarray) -> np.ndarray:
        decisions = np.asarray(decision_ts_ns, dtype=np.int64)
        if decisions.ndim != 1:
            raise C.EntryV2Refusal("decision timestamps must be rank one")
        if decisions.size and (int(decisions.min()) < self.header.open_ns
                               or int(decisions.max()) > self.header.close_ns):
            raise C.EntryV2Refusal("a decision timestamp lies outside the session")
        return np.searchsorted(self.rows["ts_recv_ns"], decisions.astype(np.uint64),
                               side="left").astype(
            np.int64, copy=False)

    def model_arrays(self, stop: int | None = None) -> tuple[np.ndarray, np.ndarray]:
        """Return every row as exact-relative float64 + exact uint8 categories.

        Scaling/centering belongs to a fitted training fold.  Keeping raw
        integer magnitudes here prevents a global-statistics lookahead.  The
        clock columns decompose ``ts_recv_ns-open_ns`` into seconds,
        microseconds, and nanoseconds, and ``ts_recv_ns-ts_event_ns`` into
        signed microseconds plus a non-negative nanosecond remainder.  The
        structured memmap remains the authority for both absolute uint64
        clocks.
        """
        end = self.header.n_events if stop is None else int(stop)
        if not 0 <= end <= self.header.n_events:
            raise C.EntryV2Refusal(f"event stop outside [0,{self.header.n_events}]: {end}")
        r = self.rows[:end]
        continuous = np.empty((end, len(CONTINUOUS_FIELDS)), dtype=np.float64)
        receive_time = (r["ts_recv_ns"].astype(np.uint64, copy=False)
                        - np.uint64(self.header.open_ns)).astype(
                            np.int64, copy=False
                        )
        signed_max = np.uint64(np.iinfo(np.int64).max)
        if (bool(np.any(r["ts_recv_ns"] > signed_max))
                or bool(np.any(r["ts_event_ns"] > signed_max))):
            raise C.EntryV2Refusal(
                "event clock exceeds signed exact-delta domain"
            )
        recv_minus_event = (r["ts_recv_ns"].astype(np.int64, copy=False)
                            - r["ts_event_ns"].astype(np.int64, copy=False))
        receive_sec, receive_subsec = np.divmod(receive_time, 1_000_000_000)
        receive_micro, receive_nano = np.divmod(receive_subsec, 1_000)
        delta_micro, delta_nano = np.divmod(recv_minus_event, 1_000)
        clock_columns = (
            ("receive_time_sec", receive_sec),
            ("receive_time_microsecond", receive_micro),
            ("receive_time_nanosecond", receive_nano),
            ("recv_minus_event_microsecond", delta_micro),
            ("recv_minus_event_nanosecond", delta_nano),
        )
        exact_limit = 1 << 53
        for name, values in clock_columns:
            if values.size and (int(values.min()) < -exact_limit
                                or int(values.max()) > exact_limit):
                raise C.EntryV2Refusal(
                    f"{name} exceeds float64 exact-integer range")
        for column, (_name, values) in enumerate(clock_columns):
            continuous[:, column] = values
        price_undefined = {
            "price": r["price"] == UNDEF_PRICE,
            "bid_px": r["bid_px"] == UNDEF_PRICE,
            "ask_px": r["ask_px"] == UNDEF_PRICE,
        }
        for column, name in enumerate(CONTINUOUS_FIELDS[5:], start=5):
            values = r[name]
            undefined = price_undefined.get(name)
            checked = values if undefined is None else values[~undefined]
            if undefined is not None:
                # Canonicalize only raw INT64_MAX sentinel cells before the
                # exact-integer range check.  Non-sentinel cells remain
                # unassigned until their lossless float64 conversion is
                # authorized below.
                continuous[undefined, column] = 0.0
            if checked.size and checked.dtype.kind in "iu":
                lo, hi = int(checked.min()), int(checked.max())
                if lo < -exact_limit or hi > exact_limit:
                    raise C.EntryV2Refusal(
                        f"{name} exceeds float64 exact-integer range")
            if undefined is None:
                continuous[:, column] = values
            else:
                continuous[~undefined, column] = checked
        categorical = np.empty((end, len(CATEGORICAL_FIELDS)), dtype=np.uint8)
        for column, name in enumerate(CATEGORICAL_FIELDS[:-1]):
            categorical[:, column] = r[name]
        categorical[:, 4] = (
            price_undefined["price"].astype(np.uint8)
            | (price_undefined["bid_px"].astype(np.uint8) << 1)
            | (price_undefined["ask_px"].astype(np.uint8) << 2)
        )
        return continuous, categorical

    def close(self) -> None:
        mmap = getattr(self.rows, "_mmap", None)
        if mmap is not None:
            mmap.close()

    def __enter__(self) -> "EventPack":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def raw_prefix_equal(left: EventPack, right: EventPack, cutoff: int) -> bool:
    """Byte-exact helper for the consolidated future-mutation audit."""
    n = int(cutoff)
    if not 0 <= n <= min(left.header.n_events, right.header.n_events):
        raise C.EntryV2Refusal("prefix comparison cutoff outside either pack")
    return bool(left.rows[:n].tobytes() == right.rows[:n].tobytes())
