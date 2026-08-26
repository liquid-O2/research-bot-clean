#!/usr/bin/env python3
"""Event-truth columns and native book-quality generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, Sequence

import numpy as np

from .event_pack import EVENT_DTYPE, UNDEF_PRICE
from .diagnostic_bindings import CandidateTruthBinding
from .diagnostic_types import (
    DiagnosticInputRefusal, F_BAD_TS_RECV, F_MAYBE_BAD_BOOK, F_SNAPSHOT,
    MULTIPLIER, RAW_TICK, SENTINEL_HIGH,
)

@dataclass(frozen=True, slots=True)
class BookQualityState:
    generation: np.ndarray
    trusted_message: np.ndarray
    trusted_economic: np.ndarray


def native_book_quality(ts_recv_ns: np.ndarray, flags: np.ndarray,
                        sane_bbo: np.ndarray) -> BookQualityState:
    ts = np.asarray(ts_recv_ns)
    flag = np.asarray(flags, dtype=np.uint8)
    sane = np.asarray(sane_bbo, dtype=np.bool_)
    if ts.ndim != 1 or flag.shape != ts.shape or sane.shape != ts.shape:
        raise DiagnosticInputRefusal("book-quality columns must be equal rank-one arrays")
    n = len(ts)
    generation = np.zeros(n, dtype=np.uint32)
    trusted_message = np.zeros(n, dtype=np.bool_)
    trusted_economic = np.zeros(n, dtype=np.bool_)
    current_generation = 0
    # An ordinary authenticated session starts trusted.  Snapshot or MAYBE_BAD
    # transitions explicitly revoke that trust.
    trusted = True
    tainted = False
    i = 0
    while i < n:
        bits = int(flag[i])
        snapshot = bool(bits & F_SNAPSHOT)
        bad = bool(bits & F_BAD_TS_RECV)
        maybe = bool(bits & F_MAYBE_BAD_BOOK)
        if snapshot:
            if not bad:
                raise DiagnosticInputRefusal("SNAPSHOT row must also carry BAD_TS_RECV")
            stamp = ts[i]
            end = i + 1
            while end < n and ts[end] == stamp and int(flag[end]) & F_SNAPSHOT:
                if not int(flag[end]) & F_BAD_TS_RECV:
                    raise DiagnosticInputRefusal("snapshot block contains non-BAD row")
                end += 1
            current_generation += 1
            generation[i:end] = current_generation
            clean_snapshot = all(
                not (int(flag[row]) & F_MAYBE_BAD_BOOK) for row in range(i, end)
            )
            trusted = False
            tainted = not clean_snapshot
            i = end
            continue
        if bad:
            raise DiagnosticInputRefusal("standalone BAD_TS_RECV should be quarantined")
        if maybe:
            if not tainted:
                current_generation += 1
            tainted = True
            trusted = False
            generation[i] = current_generation
            i += 1
            continue
        generation[i] = current_generation
        if tainted:
            i += 1
            continue
        if not trusted:
            if sane[i]:
                trusted = True       # seed is deliberately not trusted itself
            i += 1
            continue
        trusted_message[i] = True
        trusted_economic[i] = sane[i]
        i += 1
    for value in (generation, trusted_message, trusted_economic):
        value.setflags(write=False)
    return BookQualityState(generation, trusted_message, trusted_economic)


@dataclass(frozen=True, slots=True)
class EventTruthColumns:
    columns: Mapping[str, np.ndarray]
    quality_planes: Mapping[tuple[int, int, int, int], Mapping[str, np.ndarray]] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __getitem__(self, name: str) -> np.ndarray:
        return self.columns[name]

    def quality_key(self, binding: CandidateTruthBinding) -> tuple[int, int, int, int]:
        key = binding.truth_quality_key
        if key not in self.quality_planes:
            raise DiagnosticInputRefusal("candidate truth-quality plane is absent")
        return key

    def candidate_columns(self, binding: CandidateTruthBinding) -> Mapping[str, np.ndarray]:
        plane = self.quality_planes[self.quality_key(binding)]
        return MappingProxyType({**self.columns, **plane})

    def all_arrays(self) -> tuple[np.ndarray, ...]:
        return (tuple(self.columns.values())
                + tuple(value for plane in self.quality_planes.values()
                        for value in plane.values()))

    @property
    def nbytes(self) -> int:
        return sum(int(np.asarray(value).nbytes) for value in self.all_arrays())


def _readonly(value: np.ndarray) -> np.ndarray:
    value.setflags(write=False)
    return value


def _phase_table(bindings: Sequence[CandidateTruthBinding]
                 ) -> tuple[tuple[int, int], ...]:
    found: set[tuple[int, int]] = set()
    for row in bindings:
        found.add((int(row.phase_open_ts_ns), int(row.phase_close_ts_ns)))
    phases = tuple(sorted(found))
    for left, right in zip(phases, phases[1:]):
        if right[0] < left[1]:
            raise DiagnosticInputRefusal("phase interiors overlap")
    return phases


def build_event_truth_columns(rows: np.ndarray, asset: str,
                              bindings: Sequence[CandidateTruthBinding]
                              ) -> EventTruthColumns:
    if rows.dtype != EVENT_DTYPE or asset not in MULTIPLIER:
        raise DiagnosticInputRefusal("outcome rows/schema or asset is invalid")
    ts = rows["ts_recv_ns"]
    missing = ((rows["price"] == UNDEF_PRICE).astype(np.uint8)
               | ((rows["bid_px"] == UNDEF_PRICE).astype(np.uint8) << 1)
               | ((rows["ask_px"] == UNDEF_PRICE).astype(np.uint8) << 2))
    bid, ask = rows["bid_px"], rows["ask_px"]
    defined = ((missing & 6) == 0) & (bid > 0) & (ask > 0)
    ordered = defined & (ask > bid) & (bid < SENTINEL_HIGH) & (ask < SENTINEL_HIGH)
    spread = np.zeros(len(rows), dtype=np.int64)
    spread[ordered] = (ask[ordered] - bid[ordered]).astype(np.int64)
    tick = RAW_TICK[asset]
    sane_base = ordered & (spread % tick == 0)
    phase_owned = np.zeros(len(rows), dtype=np.bool_)
    owner_by_interval: dict[tuple[int, int], np.ndarray] = {}
    for start, close in _phase_table(bindings):
        # Phase close is inclusive.  When adjacent phases share a clock, the
        # entire equal-time batch belongs to the earlier phase; assignment is
        # therefore first-writer-wins over the sorted non-overlapping interiors.
        inside = ((ts >= np.uint64(start)) & (ts <= np.uint64(close))
                  & ~phase_owned)
        # spread USD * 2e9 = raw_spread * multiplier * 2 exactly.
        owned = inside.copy(); owned.setflags(write=False)
        owner_by_interval[(start, close)] = owned
        phase_owned[inside] = True
    quality_planes: dict[tuple[int, int, int, int], Mapping[str, np.ndarray]] = {}
    keys = tuple(sorted({row.truth_quality_key for row in bindings}))
    selected_by_interval: dict[tuple[int, int], tuple[int, int, int, int]] = {}
    default_sane = np.zeros(len(rows), dtype=np.bool_)
    for start, close in _phase_table(bindings):
        local = [key for key in keys if key[:2] == (start, close)]
        if not local:
            continue
        key = min(local, key=lambda value: (value[2], value[3]))
        selected_by_interval[(start, close)] = key
        owner = owner_by_interval[(start, close)]
        max_raw_spread = int(key[2]) // (2 * int(key[3]))
        default_sane[owner] = (sane_base & (spread <= max_raw_spread))[owner]
    for start, close, ceiling_units, multiplier in keys:
        if multiplier != MULTIPLIER[asset]:
            raise DiagnosticInputRefusal("truth-quality multiplier differs from asset")
        owner = owner_by_interval.get((start, close))
        if owner is None:
            raise DiagnosticInputRefusal("truth-quality phase owner is absent")
        # Positive integer division is exactly equivalent to the economic
        # inequality and cannot overflow on sentinel-adjacent raw prices.
        max_raw_spread = int(ceiling_units) // (2 * int(multiplier))
        ceiling_ok = spread <= max_raw_spread
        # Preserve all prior generation/trust transitions using the shared
        # deterministic session plane, then replace only this exact inclusive
        # phase owner with the candidate's own ceiling law.
        candidate_sane = default_sane.copy()
        candidate_sane[owner] = (sane_base & ceiling_ok)[owner]
        quality = native_book_quality(ts, rows["flags"], candidate_sane)
        phase_open = np.where(owner, start, 0).astype(np.int64)
        phase_close = np.where(owner, close, 0).astype(np.int64)
        phase_ceiling = np.where(owner, ceiling_units, 0).astype(np.int64)
        plane = {
            "generation": np.array(quality.generation, copy=True),
            "trusted_message": np.array(quality.trusted_message, copy=True),
            "trusted_economic": np.array(quality.trusted_economic, copy=True),
            "sane": np.array(candidate_sane, copy=True),
            "phase_open_ts_ns": phase_open,
            "phase_close_ts_ns": phase_close,
            "phase_sane_ceiling_units": phase_ceiling,
        }
        for value in plane.values():
            _readonly(value)
        quality_planes[(start, close, ceiling_units, multiplier)] = MappingProxyType(plane)

    # The event-derived feature plane needs one deterministic phase owner.  Use
    # the strictest registered ceiling per interval; atlas/teacher queries never
    # use this convenience view and always select the exact candidate plane.
    phase_open = np.zeros(len(rows), dtype=np.int64)
    phase_close = np.zeros(len(rows), dtype=np.int64)
    phase_ceiling = np.zeros(len(rows), dtype=np.int64)
    for start, close in _phase_table(bindings):
        key = selected_by_interval.get((start, close))
        if key is None:
            continue
        plane = quality_planes[key]; owner = owner_by_interval[(start, close)]
        default_sane[owner] = plane["sane"][owner]
        phase_open[owner] = start; phase_close[owner] = close
        phase_ceiling[owner] = key[2]
    quality = native_book_quality(ts, rows["flags"], default_sane)
    mid2 = np.zeros(len(rows), dtype=np.int64)
    mid2[ordered] = (bid[ordered] + ask[ordered]).astype(np.int64)
    columns: dict[str, np.ndarray] = {
        "ts_recv_ns": ts, "ts_event_ns": rows["ts_event_ns"],
        "ordinal": np.arange(len(rows), dtype=np.uint32),
        # A-007: every raw undefined state is routed independently.  The packed
        # three-bit ``missing_mask`` is an aggregation and may not be the only
        # carrier of the per-field undefined-price states.
        "price_undefined": (rows["price"] == UNDEF_PRICE).astype(np.uint8),
        "bid_px_undefined": (rows["bid_px"] == UNDEF_PRICE).astype(np.uint8),
        "ask_px_undefined": (rows["ask_px"] == UNDEF_PRICE).astype(np.uint8),
        "generation": quality.generation,
        "trusted_message": quality.trusted_message,
        "trusted_economic": quality.trusted_economic,
        "sane": default_sane, "mid2": mid2, "spread": spread,
        "missing_mask": missing, "phase_open_ts_ns": phase_open,
        "phase_close_ts_ns": phase_close,
        "phase_sane_ceiling_units": phase_ceiling,
    }
    for name in ("action", "side", "flags", "depth", "price", "size",
                 "bid_px", "ask_px", "bid_sz", "ask_sz", "bid_ct", "ask_ct",
                 "sequence", "ts_in_delta", "receive_session_sec"):
        columns[name] = rows[name]
    # Nothing returned may retain the mmap/full structured outcome plane.
    columns = {name: np.array(value, copy=True) for name, value in columns.items()}
    for value in columns.values():
        _readonly(value)
        if value.dtype.hasobject:
            raise DiagnosticInputRefusal("truth columns cannot use object dtype")
    return EventTruthColumns(MappingProxyType(columns),
                             MappingProxyType(quality_planes))

