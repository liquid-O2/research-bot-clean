#!/usr/bin/env python3
"""Derived event-field routes over a frozen truth plane."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType
from typing import Mapping, Optional

import numpy as np

from .diagnostic_event_truth import EventTruthColumns, _readonly
from .diagnostic_types import DiagnosticInputRefusal

# The exact 21-field raw MBP-1 event contract.  ``event_pack`` carries the
# same 21 raw coordinates (16 continuous + 5 categorical) at the model plane.
# A-007: every raw field is routed independently and no aggregate may stand in
# for an independent route, so the three per-field undefined-price states are
# routed beside the packed ``missing_mask`` bitfield rather than only inside it.
RAW_ROUTE_FIELDS = (
    "ts_recv_ns", "ts_event_ns", "price", "bid_px", "ask_px", "size",
    "bid_sz", "ask_sz", "bid_ct", "ask_ct", "sequence", "ts_in_delta",
    "receive_session_sec", "action", "side", "flags", "depth", "missing_mask",
    "price_undefined", "bid_px_undefined", "ask_px_undefined",
)
RAW_ROUTE_FIELD_COUNT = 21
# Exact bit decomposition of the packed ``missing_mask`` undefined-price code.
UNDEFINED_PRICE_ROUTE_BITS = MappingProxyType({
    "price_undefined": 1, "bid_px_undefined": 2, "ask_px_undefined": 4,
})
if len(RAW_ROUTE_FIELDS) != RAW_ROUTE_FIELD_COUNT or len(
        set(RAW_ROUTE_FIELDS)) != RAW_ROUTE_FIELD_COUNT:
    raise DiagnosticInputRefusal(
        "raw route roster must independently route all 21 raw event fields"
    )


@dataclass(frozen=True, slots=True)
class DerivedEventFields:
    raw_routes: Mapping[str, np.ndarray]
    derived_routes: Mapping[str, np.ndarray]
    valid_masks: Mapping[str, np.ndarray]
    constant_mask: Mapping[str, bool]
    schema_sha256: str
    equation_sha256: str


class DerivedEventFieldBuilder:
    VERSION = "ENTRY_V2_DERIVED_EVENT_FIELDS1"
    EQUATIONS = MappingProxyType({
        "receive_gap_ns": "ts_recv[i]-ts_recv[i-1]",
        "event_gap_ns": "ts_event[i]-ts_event[i-1]",
        "signed_latency_ns": "ts_recv-ts_event",
        "sequence_gap": "sequence[i]-sequence[i-1]",
        "mid2": "bid_px+ask_px when defined",
        "spread": "ask_px-bid_px when defined",
        "trusted_deltas": "difference iff adjacent trusted_economic and same generation",
        "size_imbalance": "(bid_sz-ask_sz)/(bid_sz+ask_sz), denominator>0",
        "count_imbalance": "(bid_ct-ask_ct)/(bid_ct+ask_ct), denominator>0",
        "action_side": "uint16(action)*256+uint16(side)",
        "flag_bit_k": "(flags>>k)&1, k=0..7",
        "tape_rate_W": "count(ts_recv in (t-W,t])/W, W=1,10,60,300,900s",
        "clock_parts": "exact quotient/remainder decomposition of receive clock",
        "log_gaps": "sign(gap)*log1p(abs(gap))",
        "flow": "signed size by action/side plus add/cancel/modify/trade masks",
        "ages": "receive_session_sec and ts_recv-phase_open/phase_close",
        "block_clock": "ts_recv at each causal 256-event block end",
    })

    def build(self, truth: EventTruthColumns) -> DerivedEventFields:
        # A-007: the three per-field undefined-price states are independent raw
        # routes.  They are the exact bit decomposition of ``missing_mask`` and
        # are derived here so every producer of the truth plane routes them,
        # whether or not it materialized them as separate columns.
        mask = np.asarray(truth["missing_mask"], np.uint8)
        undefined = {name: ((mask & bit) != 0).astype(np.uint8)
                     for name, bit in UNDEFINED_PRICE_ROUTE_BITS.items()}
        for name, value in undefined.items():
            supplied = truth.columns.get(name)
            if supplied is not None and not np.array_equal(
                    np.asarray(supplied, np.uint8), value):
                raise DiagnosticInputRefusal(
                    f"raw undefined-price route {name} differs from missing_mask"
                )
            _readonly(value)
        raw = {name: (undefined[name] if name in undefined else truth[name])
               for name in RAW_ROUTE_FIELDS}
        n = len(truth["ts_recv_ns"])
        derived: dict[str, np.ndarray] = {}
        masks: dict[str, np.ndarray] = {}
        def gap(name: str, source: np.ndarray) -> None:
            out = np.zeros(n, dtype=np.int64)
            valid = np.zeros(n, dtype=np.bool_)
            if n > 1:
                out[1:] = source[1:].astype(np.int64) - source[:-1].astype(np.int64)
                valid[1:] = True
            derived[name], masks[name] = out, valid
        gap("receive_gap_ns", truth["ts_recv_ns"])
        gap("event_gap_ns", truth["ts_event_ns"])
        gap("sequence_gap", truth["sequence"])
        derived["signed_latency_ns"] = (truth["ts_recv_ns"].astype(np.int64)
                                         - truth["ts_event_ns"].astype(np.int64))
        masks["signed_latency_ns"] = np.ones(n, dtype=np.bool_)
        receive = truth["ts_recv_ns"].astype(np.int64)
        sec, sub = np.divmod(receive, 1_000_000_000)
        micro, nano = np.divmod(sub, 1_000)
        for name, value in (("receive_time_sec", sec),
                            ("receive_time_microsecond", micro),
                            ("receive_time_nanosecond", nano)):
            derived[name] = value.astype(np.int64, copy=False)
            masks[name] = np.ones(n, dtype=np.bool_)
        for source in ("receive_gap_ns", "event_gap_ns"):
            value = derived[source].astype(np.float64)
            derived[f"log_{source}"] = np.sign(value) * np.log1p(np.abs(value))
            masks[f"log_{source}"] = masks[source].copy()
        derived["mid2"] = truth["mid2"].copy()
        derived["spread"] = truth["spread"].copy()
        masks["mid2"] = masks["spread"] = (truth["missing_mask"] & 6) == 0
        same = np.zeros(n, dtype=np.bool_)
        if n > 1:
            same[1:] = (truth["trusted_economic"][1:] &
                        truth["trusted_economic"][:-1] &
                        (truth["generation"][1:] == truth["generation"][:-1]))
        for field in ("price", "bid_px", "ask_px", "size", "bid_sz", "ask_sz",
                      "bid_ct", "ask_ct"):
            out = np.zeros(n, dtype=np.int64)
            source = truth[field].astype(np.int64)
            field_same = same.copy()
            if field in ("price", "bid_px", "ask_px"):
                bit = {"price": 1, "bid_px": 2, "ask_px": 4}[field]
                defined = (truth["missing_mask"] & bit) == 0
                if n > 1:
                    field_same[1:] &= defined[1:] & defined[:-1]
            if n > 1:
                indices = np.flatnonzero(field_same[1:]) + 1
                out[indices] = source[indices] - source[indices - 1]
            derived[f"{field}_delta"] = out
            masks[f"{field}_delta"] = field_same
        for prefix, left, right in (("size", "bid_sz", "ask_sz"),
                                    ("count", "bid_ct", "ask_ct")):
            a, b = truth[left].astype(np.float64), truth[right].astype(np.float64)
            denom = a + b
            valid = denom > 0
            out = np.zeros(n, dtype=np.float64)
            out[valid] = (a[valid] - b[valid]) / denom[valid]
            derived[f"{prefix}_imbalance"], masks[f"{prefix}_imbalance"] = out, valid
        derived["action_side"] = (truth["action"].astype(np.uint16) * 256
                                  + truth["side"].astype(np.uint16))
        masks["action_side"] = np.ones(n, dtype=np.bool_)
        for bit in range(8):
            name = f"flag_bit_{bit}"
            derived[name] = ((truth["flags"] >> bit) & 1).astype(np.uint8)
            masks[name] = np.ones(n, dtype=np.bool_)
        side_sign = np.where(np.isin(truth["side"], (66, ord("B"))), 1.0,
                             np.where(np.isin(truth["side"], (65, ord("A"))), -1.0, 0.0))
        signed_size = side_sign * truth["size"].astype(np.float64)
        action = truth["action"]
        for label, code in (("add", ord("A")), ("cancel", ord("C")),
                            ("modify", ord("M")), ("trade", ord("T"))):
            present = action == code
            derived[f"{label}_flow"] = signed_size * present
            masks[f"{label}_flow"] = truth["trusted_message"].copy()
        derived["receive_session_age_sec"] = truth["receive_session_sec"].astype(np.int64)
        derived["phase_age_ns"] = receive - truth["phase_open_ts_ns"]
        derived["phase_remaining_ns"] = truth["phase_close_ts_ns"] - receive
        masks["receive_session_age_sec"] = np.ones(n, dtype=np.bool_)
        masks["phase_age_ns"] = masks["phase_remaining_ns"] = truth["phase_close_ts_ns"] > 0
        block_clock = np.zeros(n, dtype=np.int64)
        block_mask = np.zeros(n, dtype=np.bool_)
        if n:
            # Only completed causal 256-event blocks are block ends.  The
            # roster endpoint ``n-1`` is an arbitrary slice boundary, not an
            # invariant block boundary; appending it leaks the candidate
            # roster's extent.  The consumer already enforces this law.
            ends = np.arange(255, n, 256, dtype=np.int64)
            block_clock[ends] = receive[ends]
            block_mask[ends] = True
        derived["block_end_receive_ns"] = block_clock
        masks["block_end_receive_ns"] = block_mask
        clocks = truth["ts_recv_ns"]
        for seconds in (1, 10, 60, 300, 900):
            lower = np.maximum(clocks.astype(np.int64)
                               - seconds * 1_000_000_000, 0).astype(np.uint64)
            left = np.searchsorted(clocks, lower, side="right")
            counts = np.arange(1, n + 1, dtype=np.int64) - left
            name = f"tape_rate_{seconds}s"
            derived[name] = counts.astype(np.float64) / seconds
            masks[name] = np.ones(n, dtype=np.bool_)
        for mapping in (derived, masks):
            for value in mapping.values():
                _readonly(value)
        constant = {name: bool(len(value) == 0 or np.all(value == value[0]))
                    for name, value in {**raw, **derived}.items()}
        schema = {"version": self.VERSION, "raw": list(RAW_ROUTE_FIELDS),
                  "derived": sorted(derived),
                  "dtypes": {name: str(value.dtype)
                             for name, value in {**raw, **derived}.items()}}
        schema_hash = hashlib.sha256(json.dumps(schema, sort_keys=True,
                                                separators=(",", ":")).encode()).hexdigest()
        equation_hash = hashlib.sha256(json.dumps(dict(self.EQUATIONS), sort_keys=True,
                                                  separators=(",", ":")).encode()).hexdigest()
        return DerivedEventFields(MappingProxyType(raw), MappingProxyType(derived),
                                  MappingProxyType(masks), MappingProxyType(constant),
                                  schema_hash, equation_hash)

    @staticmethod
    def prefix_summary(fields: DerivedEventFields, cutoff: int,
                       *, receive_clock_ns: Optional[np.ndarray] = None
                       ) -> np.ndarray:
        stop = int(cutoff)
        # Mapping insertion order is not a semantic schema.  Build the row
        # order from the declared route roster so a canonicalized (for example
        # alphabetized) warm reopen produces identical summaries.
        if set(fields.raw_routes) != set(RAW_ROUTE_FIELDS):
            raise DiagnosticInputRefusal(
                "summary raw-route roster differs from the canonical schema")
        arrays = ([fields.raw_routes[name] for name in RAW_ROUTE_FIELDS]
                  + [fields.derived_routes[name]
                     for name in sorted(fields.derived_routes)])
        if stop < 0 or (arrays and stop > len(arrays[0])):
            raise DiagnosticInputRefusal("summary cutoff outside event fields")
        # Every named route receives the same causal multiscale statistics.
        # Event windows capture dense bursts; exact receive windows capture
        # irregular tape speed.  Suffix rows are never inspected.
        clocks = (fields.raw_routes["ts_recv_ns"] if receive_clock_ns is None
                  else np.asarray(receive_clock_ns))
        windows: list[tuple[str, int]] = []
        for width in (1, 16, 64, 256):
            windows.append((f"events_{width}", max(0, stop - width)))
        windows.append(("events_full", 0))
        if stop:
            now = int(clocks[stop - 1])
            for seconds in (1, 10, 60, 300, 900):
                start = int(np.searchsorted(clocks[:stop],
                    np.uint64(max(0, now - seconds * 1_000_000_000)), side="left"))
                windows.append((f"seconds_{seconds}", start))
        else:
            windows.extend((f"seconds_{s}", 0) for s in (1, 10, 60, 300, 900))
        result = np.zeros((len(arrays), len(windows), 6), dtype=np.float64)
        for row, values in enumerate(arrays):
            numeric = values[:stop].astype(np.float64)
            for column, (_, start) in enumerate(windows):
                chunk = numeric[start:]
                if chunk.size:
                    result[row, column] = (chunk[-1], chunk.mean(), chunk.std(),
                                           chunk.min(), chunk.max(), chunk.sum())
        return result

