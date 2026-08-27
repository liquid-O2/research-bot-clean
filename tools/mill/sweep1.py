#!/usr/bin/env python3
"""Sweep 1 of the side-resolution mill: stability, timing, detectors, price.

Exploratory tier.  Every number here is EXPLORE-only, can kill, and cannot
promote.  Three stages, run in order:

  STAGE M  the labelled stability/timing/coverage/error-budget map (Sol
           reconciliation item 1 and 2: time-indexed preferred side, flip
           counts, ambiguity band, first-stable time, measured error budget).
  STAGE A  detector configuration grids, judged with NO cash (item 4:
           error budget, then coverage floor, then delay, then simplicity).
  STAGE B  the one selected configuration per family plus two sensitivity
           neighbours and one predeclared F4 gate, priced under the frozen
           outcome law, with the selected line pushed through the engine
           replay and every priced line beside its block-permutation null.

Decisions happen only at completed 60 s bar closes.  A bar closing at ``t``
reads the last trusted row with ``ts`` strictly before ``t``; a row stamped at
``t`` is future.  Entry convention, one convention for every family:
declaration at bar close ``T``, entry timestamp ``T``, entry quote the last
trusted row strictly before ``T`` with ``0 < bid < ask``, frozen cost
``(ask-bid)*multiplier/1e9 + FEE_USD`` from that row, outcome from the mill
index including the generation law.  A declaration is legal only if a CLEAR
candidate on the declared side with ``decision_ts_ns <= T`` exists in the cell.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Iterable, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine.entry_v2.confirmation_types import FEE_USD, NANOS_PER_SECOND
from engine.entry_v2.contracts import (
    CausalEntryExample, EntryScore, RawPrefixRef, SessionRef, Side,
)
from engine.entry_v2.corpus_units import ASSET_MULTIPLIER, ASSET_RAW_TICK
from engine.entry_v2.replay import ReplayOutcome, ScoredArrival, _drawdown, replay

import mill as M

# --------------------------------------------------------------------------
# The immutable law this sweep registers before it reads anything.
# --------------------------------------------------------------------------

SPEC = """QRE2MILLSWEEP1
tier=exploratory; explore-only; can kill, cannot promote.
bar: 60s lattice from phase_open; value at close t = last trusted row with
  ts strictly < t; a row at t is future.  lattice index k <-> t = open + 60k s;
  k=0 is the phase-open pseudo-bar, declarations only at completed bars k>=1.
entry: declaration at bar close T; entry_ts = T; entry quote = last trusted row
  strictly before T with 0<bid<ask; frozen cost = (ask-bid)*mult/1e9 + FEE_USD
  from that row; outcome from the mill index (generation law included); one
  entry per cell; entries only inside [phase_open, phase_close).
legality: a CLEAR candidate with side == declared side and decision_ts_ns <= T
  must exist in the cell, else the declaration aborts and the cell abstains
  (counted unavailable).
label: Delta(t) = cert(+1,t) - cert(-1,t) on the 60s lattice; cost(t) is the
  frozen cost at t; W_t = sign(Delta(t)) where |Delta(t)| > 2*cost(t), else
  ambiguous; entry legality is NOT required for the label (labelled bound).
first_stable(cell) = earliest non-ambiguous lattice t such that every later
  non-ambiguous lattice point carries the same sign; flips = sign changes over
  the non-ambiguous subsequence.
features: b[0] = mid2 at the phase-open sample, b[k] = bar-close mid2; running
  max/min/range over b[0..k]; R0 = running range at the first-formation bar,
  floored at 8 price ticks (16 raw ticks in mid2 units); U(t) =
  (runmax-b[0])/R0, D(t) = (b[0]-runmin)/R0; candidate new-extreme events are
  CLEAR formations whose entry_mid2 sets a new running extreme among same-side
  formations (long: new lows, short: new highs), counted with
  decision_ts_ns <= t.
families: FAM-BR S=U-D >= m for p bars (m in .5/1/1.5, p in 2/5/10);
  FAM-XR quiet Q bars since the last strict new extreme, bounce B * running
  range, remaining >= R minutes (Q in 2/5/10/20/30, B in .15/.25/.35/.5,
  R in 30/60/120); FAM-CR one side's cumulative new-extreme count exceeds the
  other by L for k bars (L in 1/2/3, k in 1/3/5).  Declaration is the first
  qualifying bar at or after the first-formation bar; both sides in one bar is
  an abstention for that bar; one declaration per cell.
selection: primary-error Wilson-95 upper bound <= b_a on every asset, then
  coverage >= c_a on every asset, then min pooled median delay, then simplest
  (fewest bars, then smallest grid values).  No cash enters selection.
nulls: fixed seed 20260827; asset-day block permutation of day-sum labels
  within asset, 200 draws, max-statistic across every line sharing the null.
"""

SCHEMA = "QRE2MILLSWEEP1"
SEED = 20260827
BAR_SECONDS = 60
BAR_NS = BAR_SECONDS * NANOS_PER_SECOND
ASSETS = ("HG", "NKD", "SI")
# Day rungs: the frozen per-asset-day targets (the per-trade rungs the frontier
# prints are these over three trades).
DAY_RUNG_USD = {"HG": 2000.0, "NKD": 1500.0, "SI": 1500.0}
MDD_CAP_USD = 1000.0
R0_FLOOR_TICKS = 8
FIXED_REF_SECONDS = (1800, 3600, 7200)
COVERAGE_GRID = (1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4)
RANDOM_COVERAGE_DRAWS = 50
ERROR_RATES = (0.02, 0.05, 0.10, 0.20)
ERROR_SEEDS = 50
NULL_DRAWS = 200
PARENT_TRIAL = "frontier-1"
SELECTION_RULE = "errbudget>coverage>delay>simplicity"

OUT_PATH = ROOT / ".audit/mill-sweep1.json"
LOG_PATH = ROOT / ".audit/mill-hypothesis-log.tsv"
SPLIT_PATH = ROOT / ".audit/mill-split.json"
OUTCOME_LAW_PATH = ROOT / "engine/entry_v2/confirmation_index.py"
CACHE_DIR = Path(os.environ.get(
    "QRE2_SWEEP1_CACHE",
    "/tmp/claude-1001/-workspace/8b35f4bc-0d28-4ded-8a73-e38a7709908c/scratchpad"))
CACHE_NPZ = CACHE_DIR / "sweep1_cells.npz"
CACHE_JSON = CACHE_DIR / "sweep1_cells.json"

BR_GRID = tuple((m, p) for m in (0.5, 1.0, 1.5) for p in (2, 5, 10))
XR_GRID = tuple((q, b, r) for q in (2, 5, 10, 20, 30)
                for b in (0.15, 0.25, 0.35, 0.5) for r in (30, 60, 120))
CR_GRID = tuple((ell, k) for ell in (1, 2, 3) for k in (1, 3, 5))
FAMILIES = ("FAM-BR", "FAM-XR", "FAM-CR")


class SweepRefusal(RuntimeError):
    pass


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _sha_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


SPEC_SHA = _sha_text(SPEC)


def code_sha() -> str:
    return _sha_file(Path(__file__).resolve())


def split_sha() -> str:
    return str(json.loads(SPLIT_PATH.read_text())["split_sha256"])


def outcome_law_sha() -> str:
    return _sha_file(OUTCOME_LAW_PATH)


# --------------------------------------------------------------------------
# Per-cell substrate pass.
# --------------------------------------------------------------------------

CELL_ARRAYS = (
    ("lat", np.int64), ("mid", np.int64), ("bar_ok", np.bool_),
    ("cost", np.float64),
    ("cert_p", np.float64), ("cert_m", np.float64),
    ("ok_p", np.bool_), ("ok_m", np.bool_),
    ("wall_p", np.bool_), ("wall_m", np.bool_),
    ("exit_p", np.int64), ("exit_m", np.int64),
    ("cum_long", np.int32), ("cum_short", np.int32),
    ("raw_cut", np.int64), ("raw_last", np.int64),
)


@dataclass(slots=True)
class CellRec:
    """Every array sweep 1 reads for one cell, sampled on the 60 s lattice."""

    asset: str
    d8: int
    phase: str
    text: str
    phase_open_ts_ns: int
    phase_close_ts_ns: int
    locked_iid: int
    pack_sha256: str
    raw_first: int
    k0: int
    r0_mid2: float
    legal_from_p: int
    legal_from_m: int
    lat: np.ndarray
    mid: np.ndarray
    bar_ok: np.ndarray
    cost: np.ndarray
    cert_p: np.ndarray
    cert_m: np.ndarray
    ok_p: np.ndarray
    ok_m: np.ndarray
    wall_p: np.ndarray
    wall_m: np.ndarray
    exit_p: np.ndarray
    exit_m: np.ndarray
    cum_long: np.ndarray
    cum_short: np.ndarray
    raw_cut: np.ndarray
    raw_last: np.ndarray

    # -- label plane -------------------------------------------------------
    @property
    def n(self) -> int:
        return int(len(self.lat))

    def cert(self, side: int) -> np.ndarray:
        return self.cert_p if side > 0 else self.cert_m

    def ok(self, side: int) -> np.ndarray:
        return self.ok_p if side > 0 else self.ok_m

    def wall(self, side: int) -> np.ndarray:
        return self.wall_p if side > 0 else self.wall_m

    def exit_ts(self, side: int) -> np.ndarray:
        return self.exit_p if side > 0 else self.exit_m

    def legal_from(self, side: int) -> int:
        return self.legal_from_p if side > 0 else self.legal_from_m

    def legal_at(self, side: int, k: int) -> bool:
        start = self.legal_from(side)
        return 0 <= start <= int(k)

    def seconds(self, k: int) -> int:
        return int(k) * BAR_SECONDS

    def fraction(self, k: int) -> float:
        span = max(1, int(self.phase_close_ts_ns) - int(self.phase_open_ts_ns))
        return float(int(self.lat[int(k)]) - int(self.phase_open_ts_ns)) / span


def _run_length(flag: np.ndarray) -> np.ndarray:
    """Length of the True-run ending at each index (0 where False)."""

    order = np.arange(len(flag), dtype=np.int64)
    last_false = np.maximum.accumulate(np.where(~flag, order, -1))
    return (order - last_false) * flag


def _first_at_or_after(flag: np.ndarray, start: int) -> int:
    """Earliest index >= ``start`` where ``flag`` is True, else -1."""

    if start >= len(flag):
        return -1
    found = np.flatnonzero(flag[int(start):])
    return -1 if not len(found) else int(start) + int(found[0])


def _candidate_extremes(entry_mid2: np.ndarray, side: np.ndarray,
                        decision: np.ndarray, lattice: np.ndarray
                        ) -> tuple[np.ndarray, np.ndarray]:
    """Cumulative same-side new-extreme formation counts at each bar close.

    A long formation is an event when its ``entry_mid2`` is strictly below every
    earlier long formation's; a short formation when strictly above every
    earlier short's.  The first formation on a side sets its extreme and counts.
    """

    out: list[np.ndarray] = []
    for want, better in ((1, np.less), (-1, np.greater)):
        rows = np.flatnonzero(side == want)
        stamps: list[int] = []
        extreme: float | None = None
        for row in rows:
            value = float(entry_mid2[row])
            if extreme is None or bool(better(value, extreme)):
                extreme = value
                stamps.append(int(decision[row]))
        marks = np.asarray(sorted(stamps), np.int64)
        out.append(np.searchsorted(marks, lattice, side="right").astype(np.int32))
    return out[0], out[1]


def build_cells(shard: M.Shard) -> list[CellRec]:
    records: list[CellRec] = []
    raw_first = int(shard.raw_ts[0]) if len(shard.raw_ts) else 0
    for cell in shard.cells:
        index = shard.cell_index(cell)
        if not len(index.ts):
            continue
        lat = np.arange(int(cell.phase_open_ts_ns), int(cell.phase_close_ts_ns),
                        BAR_NS, dtype=np.int64)
        if len(lat) < 2:
            continue
        positions, mid, bid, ask = M.bar_series(index, lat)
        quote_ok = (positions >= 0) & (bid > 0) & (ask > bid)
        cost = (ask - bid) * float(index.multiplier) / 1e9 + FEE_USD
        packed: dict[str, np.ndarray] = {}
        for side, tag in ((1, "p"), (-1, "m")):
            grid = index.outcomes_grid(
                lat, side, int(cell.phase_close_ts_ns),
                entry_mid2=mid, cost_usd=cost)
            cert = np.zeros(len(lat), np.float64)
            wall = np.zeros(len(lat), np.bool_)
            exit_ts = np.zeros(len(lat), np.int64)
            ok = np.zeros(len(lat), np.bool_)
            keep = grid["input_index"]
            if len(keep):
                cert[keep] = grid["cert_close_usd"]
                wall[keep] = grid["wall_hit"]
                exit_ts[keep] = grid["exit_ts_ns"]
                ok[keep] = True
            ok &= quote_ok
            packed[f"cert_{tag}"] = cert
            packed[f"wall_{tag}"] = wall
            packed[f"exit_{tag}"] = exit_ts
            packed[f"ok_{tag}"] = ok
        rows = np.asarray(cell.rows, np.int64)
        sides = shard.side[rows]
        decisions = shard.decision_ts_ns[rows].astype(np.int64)
        cum_long, cum_short = _candidate_extremes(
            shard.entry_mid2[rows].astype(np.int64), sides, decisions, lat)
        legal = {}
        for side, tag in ((1, "p"), (-1, "m")):
            same = decisions[sides == side]
            legal[tag] = (-1 if not len(same)
                          else int(np.searchsorted(lat, int(same.min()), side="left")))
            if legal[tag] >= len(lat):
                legal[tag] = -1
        first_formation = int(cell.first_formation_ts_ns)
        k0 = int(np.searchsorted(lat, first_formation, side="left"))
        k0 = max(1, min(k0, len(lat) - 1))
        run_max = np.maximum.accumulate(mid)
        run_min = np.minimum.accumulate(mid)
        floor = float(R0_FLOOR_TICKS * 2 * ASSET_RAW_TICK[shard.asset])
        r0 = max(float(run_max[k0] - run_min[k0]), floor)
        raw_cut = np.searchsorted(
            shard.raw_ts.astype(np.int64), lat, side="left").astype(np.int64)
        raw_index = np.maximum(raw_cut - 1, 0)
        raw_last = shard.raw_ts.astype(np.int64)[raw_index]
        records.append(CellRec(
            asset=shard.asset, d8=shard.d8, phase=cell.phase, text=cell.text,
            phase_open_ts_ns=int(cell.phase_open_ts_ns),
            phase_close_ts_ns=int(cell.phase_close_ts_ns),
            locked_iid=int(shard.locked_iid),
            pack_sha256=str(shard.meta["event_pack_sha256"]),
            raw_first=raw_first, k0=k0, r0_mid2=r0,
            legal_from_p=int(legal["p"]), legal_from_m=int(legal["m"]),
            lat=lat, mid=mid, bar_ok=quote_ok, cost=cost,
            cum_long=cum_long, cum_short=cum_short,
            raw_cut=raw_cut, raw_last=raw_last, **packed))
    return records


def prep(store: M.CellStore) -> tuple[list[CellRec], dict[str, int]]:
    records: list[CellRec] = []
    days: dict[str, set[int]] = {}
    for shard in store.shards():
        days.setdefault(shard.asset, set()).add(shard.d8)
        records.extend(build_cells(shard))
    return records, {asset: len(value) for asset, value in sorted(days.items())}


def save_cache(records: Sequence[CellRec], days: Mapping[str, int]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    offsets = np.cumsum([0] + [rec.n for rec in records]).astype(np.int64)
    payload = {name: np.concatenate([getattr(rec, name) for rec in records])
               .astype(dtype) for name, dtype in CELL_ARRAYS}
    payload["offsets"] = offsets
    with CACHE_NPZ.open("wb") as handle:
        np.savez(handle, **payload)
    CACHE_JSON.write_text(json.dumps({
        "schema": SCHEMA, "spec_sha": SPEC_SHA, "split_sha": split_sha(),
        "asset_days": dict(days),
        "cells": [{"asset": r.asset, "d8": r.d8, "phase": r.phase, "text": r.text,
                   "phase_open_ts_ns": r.phase_open_ts_ns,
                   "phase_close_ts_ns": r.phase_close_ts_ns,
                   "locked_iid": r.locked_iid, "pack_sha256": r.pack_sha256,
                   "raw_first": r.raw_first, "k0": r.k0, "r0_mid2": r.r0_mid2,
                   "legal_from_p": r.legal_from_p, "legal_from_m": r.legal_from_m}
                  for r in records]}, sort_keys=True))


def load_cache() -> tuple[list[CellRec], dict[str, int]]:
    if not (CACHE_NPZ.is_file() and CACHE_JSON.is_file()):
        raise SweepRefusal("prep cache is absent; run `sweep1.py prep` first")
    meta = json.loads(CACHE_JSON.read_text())
    if meta.get("spec_sha") != SPEC_SHA or meta.get("split_sha") != split_sha():
        raise SweepRefusal("prep cache was built under a different spec/split")
    data = np.load(CACHE_NPZ)
    offsets = data["offsets"]
    records: list[CellRec] = []
    for position, scalars in enumerate(meta["cells"]):
        lo, hi = int(offsets[position]), int(offsets[position + 1])
        arrays = {name: data[name][lo:hi] for name, _dtype in CELL_ARRAYS}
        records.append(CellRec(**scalars, **arrays))
    return records, {str(k): int(v) for k, v in meta["asset_days"].items()}


# --------------------------------------------------------------------------
# Label plane: Delta, the ambiguity band, first-stable and flips.
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Label:
    valid: np.ndarray          # both sides certifiable at the lattice point
    sharp: np.ndarray          # valid and outside the ambiguity band
    sign: np.ndarray           # W_t where sharp, 0 elsewhere
    first_stable: int          # lattice index, -1 when no sharp point exists
    flips: int
    stable_side: int           # sign at the final sharp point, 0 when none


def label_cell(rec: CellRec) -> Label:
    valid = rec.ok_p & rec.ok_m
    delta = np.where(valid, rec.cert_p - rec.cert_m, 0.0)
    sharp = valid & (np.abs(delta) > 2.0 * rec.cost)
    sign = np.where(sharp, np.sign(delta), 0.0).astype(np.int64)
    idx = np.flatnonzero(sharp)
    if not len(idx):
        return Label(valid, sharp, sign, -1, 0, 0)
    series = sign[idx]
    flips = int(np.count_nonzero(series[1:] != series[:-1]))
    differs = np.flatnonzero(series != series[-1])
    position = 0 if not len(differs) else int(differs[-1]) + 1
    return Label(valid, sharp, sign, int(idx[position]), flips, int(series[-1]))


def labels_for(records: Sequence[CellRec]) -> list[Label]:
    return [label_cell(rec) for rec in records]


# --------------------------------------------------------------------------
# Entry plane: the one legal entry convention.
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Entry:
    cell: int          # index into the record list
    asset: str
    d8: int
    bar: int
    ts_ns: int
    side: int
    cert_usd: float
    wall: bool
    exit_ts_ns: int
    text: str


def make_entry(position: int, rec: CellRec, bar: int, side: int) -> Entry | None:
    """The legal entry, or ``None`` when the declaration aborts."""

    if not 1 <= int(bar) < rec.n or int(side) not in (1, -1):
        return None
    if not rec.legal_at(side, bar) or not bool(rec.ok(side)[bar]):
        return None
    return Entry(position, rec.asset, rec.d8, int(bar), int(rec.lat[bar]),
                 int(side), float(rec.cert(side)[bar]), bool(rec.wall(side)[bar]),
                 int(rec.exit_ts(side)[bar]), rec.text)


# --------------------------------------------------------------------------
# Cash reductions.
# --------------------------------------------------------------------------

def day_sums(entries: Sequence[Entry]) -> dict[tuple[str, int], float]:
    out: dict[tuple[str, int], float] = {}
    for row in sorted(entries, key=lambda e: (e.ts_ns, e.text)):
        key = (row.asset, row.d8)
        out[key] = out.get(key, 0.0) + row.cert_usd
    return out


def asset_mdd_day(entries: Sequence[Entry], asset: str) -> float:
    """``_drawdown`` over entry-ordered day-sums for one asset."""

    sums = day_sums([row for row in entries if row.asset == asset])
    return float(_drawdown(sums[key] for key in sorted(sums)))


def asset_mdd_trade(entries: Sequence[Entry], asset: str) -> float:
    rows = sorted((row for row in entries if row.asset == asset),
                  key=lambda e: (e.ts_ns, e.text))
    return float(_drawdown(row.cert_usd for row in rows))


def cash_line(entries: Sequence[Entry], days: Mapping[str, int],
              cells: Mapping[str, int]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for asset in ASSETS:
        rows = [row for row in entries if row.asset == asset]
        certs = np.asarray([row.cert_usd for row in rows], np.float64)
        n_days = max(1, int(days.get(asset, 0)))
        out[asset] = {
            "trades": int(len(rows)),
            "coverage": float(len(rows) / max(1, cells.get(asset, 1))),
            "total_usd": float(certs.sum()) if len(certs) else 0.0,
            "usd_per_asset_day": float(certs.sum() / n_days) if len(certs) else 0.0,
            "usd_per_trade": float(certs.mean()) if len(certs) else 0.0,
            "win_rate": float((certs > 0).mean()) if len(certs) else 0.0,
            "wall_rate": float(np.mean([row.wall for row in rows])) if rows else 0.0,
            "walls": int(sum(row.wall for row in rows)),
            "mdd_day_usd": asset_mdd_day(rows, asset),
            "mdd_trade_usd": asset_mdd_trade(rows, asset),
            "clears_rung": bool(
                (certs.sum() / n_days if len(certs) else 0.0)
                >= DAY_RUNG_USD[asset]),
        }
    return out


def cells_by_asset(records: Sequence[CellRec]) -> dict[str, int]:
    out: dict[str, int] = {}
    for rec in records:
        out[rec.asset] = out.get(rec.asset, 0) + 1
    return out


# --------------------------------------------------------------------------
# STAGE M
# --------------------------------------------------------------------------

def _quantiles(values: Sequence[float], marks=(25, 50, 75)) -> dict[str, float]:
    array = np.asarray(list(values), np.float64)
    if not len(array):
        return {"n": 0}
    out: dict[str, float] = {"n": int(len(array)), "mean": float(array.mean())}
    for mark in marks:
        out[f"p{mark}"] = float(np.percentile(array, mark))
    return out


def m1(records: Sequence[CellRec], labels: Sequence[Label],
       days: Mapping[str, int]) -> dict[str, object]:
    out: dict[str, object] = {}
    for asset in ASSETS:
        rows = [(rec, lab) for rec, lab in zip(records, labels) if rec.asset == asset]
        seconds: list[float] = []
        fractions: list[float] = []
        hist = {"0": 0, "1": 0, "2": 0, "3+": 0}
        amb_close = 0
        miss_close = 0
        certs: list[float] = []
        available = 0
        no_stable = 0
        tau_past_close = 0
        illegal = 0
        for rec, lab in rows:
            hist[str(lab.flips) if lab.flips < 3 else "3+"] += 1
            last = rec.n - 1
            if not bool(lab.valid[last]):
                miss_close += 1
            elif not bool(lab.sharp[last]):
                amb_close += 1
            if lab.first_stable < 0:
                no_stable += 1
                continue
            seconds.append(float(rec.seconds(lab.first_stable)))
            fractions.append(rec.fraction(lab.first_stable))
            tau = lab.first_stable + 1
            if tau >= rec.n:
                tau_past_close += 1
                continue
            side = int(lab.sign[lab.first_stable])
            entry = make_entry(0, rec, tau, side)
            if entry is None:
                illegal += 1
                continue
            available += 1
            certs.append(entry.cert_usd)
        cash = np.asarray(certs, np.float64)
        out[asset] = {
            "cells": len(rows), "asset_days": int(days.get(asset, 0)),
            "first_stable_seconds": _quantiles(seconds),
            "first_stable_fraction": _quantiles(fractions),
            "flip_histogram": hist,
            "flip_fraction": {key: value / max(1, len(rows))
                              for key, value in hist.items()},
            "ambiguous_at_close": amb_close / max(1, len(rows)),
            "missing_at_close": miss_close / max(1, len(rows)),
            "cells_without_stable_side": no_stable,
            "availability": {
                "entered": available, "tau_past_phase_close": tau_past_close,
                "illegal_or_uncertifiable": illegal,
                "rate": available / max(1, len(rows))},
            "cash_at_first_stable_plus_60": {
                "n": int(len(cash)),
                "mean_usd": float(cash.mean()) if len(cash) else 0.0,
                "median_usd": float(np.median(cash)) if len(cash) else 0.0,
                "usd_per_asset_day": (float(cash.sum() / max(1, days.get(asset, 1)))
                                      if len(cash) else 0.0)},
        }
    return out


def _oracle_entries(records: Sequence[CellRec], labels: Sequence[Label],
                    tau_kind: str) -> tuple[list[Entry], dict[str, dict[str, int]]]:
    """Enter every cell at tau on ``W_tau``; ambiguous and unavailable counted."""

    entries: list[Entry] = []
    counts: dict[str, dict[str, int]] = {
        asset: {"cells": 0, "ambiguous": 0, "unavailable": 0, "entered": 0}
        for asset in ASSETS}
    for position, (rec, lab) in enumerate(zip(records, labels)):
        book = counts[rec.asset]
        book["cells"] += 1
        if tau_kind == "first_stable+60":
            if lab.first_stable < 0:
                book["unavailable"] += 1
                continue
            tau = lab.first_stable + 1
        else:
            tau = int(tau_kind) // BAR_SECONDS
        if not 1 <= tau < rec.n:
            book["unavailable"] += 1
            continue
        if not bool(lab.sharp[tau]):
            book["ambiguous"] += 1
            continue
        entry = make_entry(position, rec, tau, int(lab.sign[tau]))
        if entry is None:
            book["unavailable"] += 1
            continue
        book["entered"] += 1
        entries.append(entry)
    return entries, counts


def m2(records: Sequence[CellRec], labels: Sequence[Label],
       days: Mapping[str, int]) -> dict[str, object]:
    cells = cells_by_asset(records)
    out: dict[str, object] = {}
    for tau_kind in ("first_stable+60",) + tuple(str(v) for v in FIXED_REF_SECONDS):
        entries, counts = _oracle_entries(records, labels, tau_kind)
        line = cash_line(entries, days, cells)
        for asset in ASSETS:
            line[asset].update({
                "ambiguous": counts[asset]["ambiguous"],
                "unavailable": counts[asset]["unavailable"],
                "cells": counts[asset]["cells"]})
        out[tau_kind] = line
    return out


def m3(records: Sequence[CellRec], labels: Sequence[Label],
       days: Mapping[str, int]) -> dict[str, object]:
    entries, _counts = _oracle_entries(records, labels, "first_stable+60")
    out: dict[str, object] = {}
    for asset in ASSETS:
        rows = [row for row in entries if row.asset == asset]
        certs = np.asarray([row.cert_usd for row in rows], np.float64)
        n_days = max(1, int(days.get(asset, 0)))
        rung = DAY_RUNG_USD[asset]
        order = np.argsort(-certs) if len(certs) else np.zeros(0, np.int64)
        table: dict[str, dict[str, float]] = {}
        clearing: list[float] = []
        for coverage in COVERAGE_GRID:
            keep = int(round(coverage * len(certs)))
            top = float(certs[order[:keep]].sum()) if keep else 0.0
            draws = []
            for seed in range(RANDOM_COVERAGE_DRAWS):
                if not keep:
                    draws.append(0.0)
                    continue
                pick = np.random.default_rng(SEED + seed).choice(
                    len(certs), size=keep, replace=False)
                draws.append(float(certs[pick].sum()))
            hindsight = top / n_days
            table[f"{coverage:.1f}"] = {
                "entered": keep,
                "hindsight_usd_day": hindsight,
                "hindsight_usd_trade": float(top / keep) if keep else 0.0,
                "random_usd_day": float(np.mean(draws) / n_days),
                "random_usd_trade": (float(np.mean(draws) / keep) if keep else 0.0),
                "required_entered_mean_usd": (
                    float(rung * n_days / keep) if keep else float("inf")),
                "hindsight_clears_rung": bool(hindsight >= rung),
            }
            if hindsight >= rung:
                clearing.append(coverage)
        out[asset] = {
            "entered_cells": int(len(certs)), "asset_days": n_days,
            "day_rung_usd": rung, "coverage_table": table,
            "clearing_coverages": clearing,
            "min_clearing_coverage": (min(clearing) if clearing else None),
        }
    return out


def _flip_cash(rows: Sequence[Entry], records: Sequence[CellRec],
               chosen: Sequence[int]) -> tuple[list[Entry], int]:
    """Replace the chosen entries with their wrong side; illegal ones drop."""

    marked = set(int(value) for value in chosen)
    out: list[Entry] = []
    dropped = 0
    for position, row in enumerate(rows):
        if position not in marked:
            out.append(row)
            continue
        rec = records[row.cell]
        flipped = make_entry(row.cell, rec, row.bar, -row.side)
        if flipped is None:
            dropped += 1
            continue
        out.append(flipped)
    return out, dropped


def m4(records: Sequence[CellRec], labels: Sequence[Label],
       days: Mapping[str, int]) -> dict[str, object]:
    entries, _counts = _oracle_entries(records, labels, "first_stable+60")
    cells = cells_by_asset(records)
    base = cash_line(entries, days, cells)
    out: dict[str, object] = {"base_line": base, "rates": {}}
    per_asset_budget = {"random": {}, "adversarial": {}}
    global_budget = {"random": 0.0, "adversarial": 0.0}
    for placement in ("random", "adversarial"):
        holds_all: dict[float, bool] = {}
        for asset in ASSETS:
            per_asset_budget[placement][asset] = 0.0
        for rate in ERROR_RATES:
            per_asset: dict[str, dict[str, float]] = {}
            for asset in ASSETS:
                rows = [row for row in entries if row.asset == asset]
                if not rows:
                    per_asset[asset] = {"usd_per_asset_day": 0.0, "mdd_day_usd": 0.0,
                                        "flipped": 0, "dropped": 0,
                                        "holds": False}
                    continue
                count = int(round(rate * len(rows)))
                if placement == "adversarial":
                    wrong = []
                    for position, row in enumerate(rows):
                        rec = records[row.cell]
                        other = make_entry(row.cell, rec, row.bar, -row.side)
                        wrong.append((float(other.cert_usd) if other is not None
                                      else float("inf"), position))
                    wrong.sort()
                    picks = [[position for _value, position in wrong][:count]]
                else:
                    picks = [np.random.default_rng(SEED + seed).choice(
                        len(rows), size=count, replace=False).tolist()
                        for seed in range(ERROR_SEEDS)] if count else [[]]
                cash: list[float] = []
                mdds: list[float] = []
                dropped_total = 0
                for pick in picks:
                    flipped, dropped = _flip_cash(rows, records, pick)
                    dropped_total += dropped
                    total = sum(row.cert_usd for row in flipped)
                    cash.append(total / max(1, days.get(asset, 1)))
                    mdds.append(asset_mdd_day(flipped, asset))
                usd = float(np.mean(cash))
                mdd = float(np.mean(mdds))
                per_asset[asset] = {
                    "usd_per_asset_day": usd, "mdd_day_usd": mdd,
                    "flipped": count, "dropped": dropped_total / len(picks),
                    "holds": bool(usd >= DAY_RUNG_USD[asset] and mdd < MDD_CAP_USD)}
                if per_asset[asset]["holds"]:
                    per_asset_budget[placement][asset] = max(
                        per_asset_budget[placement][asset], rate)
            holds = all(per_asset[asset]["holds"] for asset in ASSETS)
            holds_all[rate] = holds
            if holds:
                global_budget[placement] = max(global_budget[placement], rate)
            out["rates"].setdefault(f"{rate:.2f}", {})[placement] = {
                "by_asset": per_asset, "all_rungs_and_mdd_hold": holds}
    out["budget_global"] = global_budget
    out["budget_by_asset"] = per_asset_budget
    out["budget_used"] = {asset: float(per_asset_budget["adversarial"][asset])
                          for asset in ASSETS}
    return out


# --------------------------------------------------------------------------
# STAGE A: detector families.  No cash reaches this stage.
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Declaration:
    cell: int
    bar: int
    side: int


@dataclass(frozen=True, slots=True)
class Geometry:
    """Shared per-cell bar geometry every family reads."""

    b: np.ndarray
    run_max: np.ndarray
    run_min: np.ndarray
    rng: np.ndarray
    u: np.ndarray
    d: np.ndarray
    s: np.ndarray
    last_low: np.ndarray
    last_high: np.ndarray
    remaining_min: np.ndarray
    start: int


def geometry(rec: CellRec) -> Geometry:
    b = rec.mid.astype(np.float64)
    run_max = np.maximum.accumulate(b)
    run_min = np.minimum.accumulate(b)
    span = run_max - run_min
    order = np.arange(len(b), dtype=np.int64)
    new_low = np.zeros(len(b), bool)
    new_high = np.zeros(len(b), bool)
    if len(b) > 1:
        new_low[1:] = b[1:] < run_min[:-1]
        new_high[1:] = b[1:] > run_max[:-1]
    last_low = np.maximum.accumulate(np.where(new_low, order, 0))
    last_high = np.maximum.accumulate(np.where(new_high, order, 0))
    remaining = (float(rec.phase_close_ts_ns) - rec.lat.astype(np.float64)) / (
        60.0 * NANOS_PER_SECOND)
    return Geometry(
        b=b, run_max=run_max, run_min=run_min, rng=span,
        u=(run_max - b[0]) / rec.r0_mid2, d=(b[0] - run_min) / rec.r0_mid2,
        s=((run_max - b[0]) - (b[0] - run_min)) / rec.r0_mid2,
        last_low=last_low, last_high=last_high, remaining_min=remaining,
        start=max(1, int(rec.k0)))


def declare_br(rec: CellRec, geo: Geometry, m: float, p: int) -> Declaration | None:
    up = _run_length(geo.s >= m) >= p
    down = _run_length(geo.s <= -m) >= p
    fire = up ^ down
    bar = _first_at_or_after(fire & rec.bar_ok, geo.start)
    if bar < 0:
        return None
    return Declaration(0, bar, 1 if bool(up[bar]) else -1)


def declare_xr(rec: CellRec, geo: Geometry, q: int, b: float, r: int
               ) -> Declaration | None:
    order = np.arange(len(geo.b), dtype=np.int64)
    remaining = geo.remaining_min >= float(r)
    live = geo.rng > 0.0
    long_ok = ((order - geo.last_low) >= q) & (
        (geo.b - geo.run_min) >= b * geo.rng) & remaining & live
    short_ok = ((order - geo.last_high) >= q) & (
        (geo.run_max - geo.b) >= b * geo.rng) & remaining & live
    fire = long_ok ^ short_ok
    bar = _first_at_or_after(fire & rec.bar_ok, geo.start)
    if bar < 0:
        return None
    return Declaration(0, bar, 1 if bool(long_ok[bar]) else -1)


def declare_cr(rec: CellRec, geo: Geometry, ell: int, k: int) -> Declaration | None:
    diff = rec.cum_long.astype(np.int64) - rec.cum_short.astype(np.int64)
    up = _run_length(diff >= ell) >= k
    down = _run_length(-diff >= ell) >= k
    fire = up ^ down
    bar = _first_at_or_after(fire & rec.bar_ok, geo.start)
    if bar < 0:
        return None
    return Declaration(0, bar, 1 if bool(up[bar]) else -1)


def config_key(family: str, params: tuple) -> str:
    if family == "FAM-BR":
        return f"m{params[0]:g}_p{params[1]}"
    if family == "FAM-XR":
        return f"Q{params[0]}_B{params[1]:g}_R{params[2]}"
    return f"L{params[0]}_k{params[1]}"


def family_grid(family: str) -> tuple[tuple, ...]:
    return {"FAM-BR": BR_GRID, "FAM-XR": XR_GRID, "FAM-CR": CR_GRID}[family]


def simplicity_key(family: str, params: tuple) -> tuple:
    if family == "FAM-BR":
        return (params[1], params[0])
    if family == "FAM-XR":
        return (params[0], params[1], params[2])
    return (params[1], params[0])


def declare(family: str, rec: CellRec, geo: Geometry, params: tuple
            ) -> Declaration | None:
    if family == "FAM-BR":
        return declare_br(rec, geo, *params)
    if family == "FAM-XR":
        return declare_xr(rec, geo, *params)
    return declare_cr(rec, geo, *params)


def wilson(hits: int, total: int, z: float = 1.959963984540054
           ) -> tuple[float, float]:
    if total <= 0:
        return (0.0, 1.0)
    p = hits / total
    denom = 1.0 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def stage_a(records: Sequence[CellRec], labels: Sequence[Label],
            budgets: Mapping[str, float], floors: Mapping[str, float]
            ) -> dict[str, object]:
    geos = [geometry(rec) for rec in records]
    cells = cells_by_asset(records)
    report: dict[str, object] = {"budget_by_asset": dict(budgets),
                                 "coverage_floor_by_asset": dict(floors),
                                 "families": {}}
    for family in FAMILIES:
        rows: dict[str, dict[str, object]] = {}
        for params in family_grid(family):
            key = config_key(family, params)
            per_asset: dict[str, dict[str, object]] = {}
            delays_pool: list[float] = []
            declared_all = 0
            legal_all = 0
            for asset in ASSETS:
                declared = 0
                legal = 0
                unavailable = 0
                delays: list[float] = []
                since_stable: list[float] = []
                primary_hits = 0
                primary_total = 0
                secondary_hits = 0
                secondary_total = 0
                for rec, lab, geo in zip(records, labels, geos):
                    if rec.asset != asset:
                        continue
                    call = declare(family, rec, geo, params)
                    if call is None:
                        continue
                    declared += 1
                    if not rec.legal_at(call.side, call.bar):
                        unavailable += 1
                        continue
                    legal += 1
                    delays.append(float(rec.seconds(call.bar)))
                    if lab.first_stable >= 0:
                        since_stable.append(
                            float((call.bar - lab.first_stable) * BAR_SECONDS))
                    if bool(lab.sharp[call.bar]):
                        primary_total += 1
                        primary_hits += int(int(lab.sign[call.bar]) != call.side)
                    if lab.stable_side:
                        secondary_total += 1
                        secondary_hits += int(lab.stable_side != call.side)
                total_cells = max(1, cells.get(asset, 1))
                low, high = wilson(primary_hits, primary_total)
                per_asset[asset] = {
                    "cells": cells.get(asset, 0), "declared": declared,
                    "legal": legal, "unavailable": unavailable,
                    "coverage": legal / total_cells,
                    "unavailable_rate": unavailable / total_cells,
                    "delay_median_s": (float(np.median(delays)) if delays else None),
                    "delay_since_first_stable_median_s": (
                        float(np.median(since_stable)) if since_stable else None),
                    "primary_error": (primary_hits / primary_total
                                      if primary_total else None),
                    "primary_n": primary_total,
                    "primary_ci95": [low, high],
                    "secondary_error": (secondary_hits / secondary_total
                                        if secondary_total else None),
                    "secondary_n": secondary_total,
                }
                delays_pool.extend(delays)
                declared_all += declared
                legal_all += legal
            rows[key] = {
                "params": list(params), "by_asset": per_asset,
                "coverage_pooled": legal_all / max(1, len(records)),
                "declared_pooled": declared_all,
                "delay_median_pooled_s": (float(np.median(delays_pool))
                                          if delays_pool else None),
                "max_asset_primary_error": max(
                    (per_asset[a]["primary_error"] or 0.0) for a in ASSETS),
                "max_asset_primary_ci_upper": max(
                    per_asset[a]["primary_ci95"][1] for a in ASSETS),
                "simplicity": list(simplicity_key(family, params)),
            }
        report["families"][family] = {
            "configs": rows,
            "selection": select_config(family, rows, budgets, floors),
        }
    return report


def select_config(family: str, rows: Mapping[str, dict], budgets: Mapping[str, float],
                  floors: Mapping[str, float]) -> dict[str, object]:
    def passes_budget(entry: Mapping[str, object]) -> bool:
        return all(entry["by_asset"][a]["primary_ci95"][1] <= budgets.get(a, 0.0)
                   for a in ASSETS)

    def passes_coverage(entry: Mapping[str, object]) -> bool:
        return all(entry["by_asset"][a]["coverage"] >= floors.get(a, 0.0)
                   for a in ASSETS)

    def sort_key(item: tuple[str, Mapping[str, object]]) -> tuple:
        key, entry = item
        delay = entry["delay_median_pooled_s"]
        return (float("inf") if delay is None else float(delay),
                tuple(entry["simplicity"]), key)

    budget_ok = {key: entry for key, entry in rows.items() if passes_budget(entry)}
    both_ok = {key: entry for key, entry in budget_ok.items()
               if passes_coverage(entry)}
    flags: list[str] = []
    if not budget_ok:
        flags.append("BUDGET_FAIL")
        pool = sorted(rows.items(), key=lambda item: (
            item[1]["max_asset_primary_error"], tuple(item[1]["simplicity"]),
            item[0]))
        selected = pool[0][0]
        ordered = [key for key, _entry in pool]
    else:
        if not both_ok:
            flags.append("COVERAGE_FAIL")
            pool = sorted(budget_ok.items(), key=sort_key)
        else:
            pool = sorted(both_ok.items(), key=sort_key)
        selected = pool[0][0]
        ordered = [key for key, _entry in pool]
    return {"selected": selected, "flags": flags,
            "n_pass_budget": len(budget_ok), "n_pass_coverage": len(both_ok),
            "ordered": ordered[:12],
            "neighbors": neighbours(family, selected, rows)}


def sensitive_axis(family: str, selected: str, rows: Mapping[str, dict]) -> int:
    """The axis whose primary error moves most with the others held fixed."""

    params = tuple(rows[selected]["params"])
    best_axis = 0
    best_spread = -1.0
    for axis in range(len(params)):
        values = []
        for other_params in family_grid(family):
            if all(other_params[i] == params[i]
                   for i in range(len(params)) if i != axis):
                values.append(rows[config_key(family, other_params)][
                    "max_asset_primary_error"])
        spread = (max(values) - min(values)) if len(values) > 1 else 0.0
        if spread > best_spread:
            best_spread, best_axis = spread, axis
    return best_axis


def neighbours(family: str, selected: str, rows: Mapping[str, dict]) -> list[str]:
    params = list(rows[selected]["params"])
    axis = sensitive_axis(family, selected, rows)
    ladder = sorted({p[axis] for p in family_grid(family)})
    position = ladder.index(params[axis])
    order = sorted(range(len(ladder)), key=lambda i: (abs(i - position), i))
    picks: list[str] = []
    for i in order:
        if i == position:
            continue
        trial = list(params)
        trial[axis] = ladder[i]
        picks.append(config_key(family, tuple(trial)))
        if len(picks) == 2:
            break
    return picks


# --------------------------------------------------------------------------
# STAGE B: cash on a handful of lines.
# --------------------------------------------------------------------------

def price_config(family: str, params: tuple, records: Sequence[CellRec],
                 geos: Sequence[Geometry], gate: Mapping[str, float] | None = None
                 ) -> tuple[list[Entry], dict[str, int]]:
    entries: list[Entry] = []
    skips = {"declared": 0, "illegal": 0, "gated": 0, "uncertifiable": 0}
    for position, (rec, geo) in enumerate(zip(records, geos)):
        call = declare(family, rec, geo, params)
        if call is None:
            continue
        skips["declared"] += 1
        if gate is not None and float(geo.rng[call.bar]) < float(gate[rec.asset]):
            skips["gated"] += 1
            continue
        if not rec.legal_at(call.side, call.bar):
            skips["illegal"] += 1
            continue
        entry = make_entry(position, rec, call.bar, call.side)
        if entry is None:
            skips["uncertifiable"] += 1
            continue
        entries.append(entry)
    return entries, skips


def r0_gate(records: Sequence[CellRec]) -> dict[str, float]:
    out: dict[str, float] = {}
    for asset in ASSETS:
        values = [rec.r0_mid2 for rec in records if rec.asset == asset]
        out[asset] = float(np.median(values)) if values else 0.0
    return out


def replay_line(entries: Sequence[Entry], records: Sequence[CellRec],
                model_hash: str) -> dict[str, object]:
    """Mirror B5's arrival shaping and push the line through engine replay."""

    sessions: dict[tuple[str, int], SessionRef] = {}
    for rec in records:
        sessions[(rec.asset, rec.d8)] = SessionRef(
            rec.asset, rec.d8, str(rec.locked_iid))
    arrivals: list[ScoredArrival] = []
    for row in sorted(entries, key=lambda e: (e.ts_ns, e.text)):
        rec = records[row.cell]
        cutoff = int(rec.raw_cut[row.bar])
        prefix = RawPrefixRef(
            f"mill/{rec.asset}/{rec.d8}.npz", 0, cutoff, cutoff,
            (rec.raw_first if cutoff else None),
            (int(rec.raw_last[row.bar]) if cutoff else None), rec.pack_sha256)
        opportunity = f"MILL1-{rec.text.replace('/', '-')}-{row.bar}"
        example = CausalEntryExample(
            opportunity, rec.asset, rec.d8, str(rec.locked_iid), row.ts_ns,
            Side.LONG if row.side > 0 else Side.SHORT, rec.phase, rec.locked_iid,
            prefix, {"frozen_rule_snapshot_present": 1.0}, None,
            _sha_text(f"{opportunity}|{model_hash}"))
        score = EntryScore(opportunity, rec.asset, row.ts_ns, model_hash,
                           0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, True)
        outcome = ReplayOutcome(
            opportunity, row.exit_ts_ns, float(row.cert_usd),
            rec.phase_close_ts_ns, float(row.cert_usd),
            row.exit_ts_ns if row.wall else None,
            float(row.cert_usd) if row.wall else -900.0)
        arrivals.append(ScoredArrival(example, score, outcome))
    if not arrivals:
        return {"status": "EMPTY_ARRIVALS"}
    expected = tuple(sorted(sessions.values()))
    evaluation = replay(tuple(sorted(
        arrivals, key=lambda row: (row.example.decision_ts_ns,
                                   row.example.candidate_id))),
        expected_sessions=expected)
    taken = {trade.candidate_id for trade in evaluation.trade_results}
    return {
        "status": "OK", "label": "partial-day (split breaks portfolio days)",
        "asset_days": evaluation.asset_days, "trades": evaluation.trades,
        "usd_per_asset_day": evaluation.usd_per_asset_day,
        "usd_per_trade": evaluation.usd_per_trade,
        "total_usd": evaluation.total_pnl_usd,
        "max_drawdown_usd": evaluation.max_drawdown_usd,
        "drawdown_p90_usd": evaluation.drawdown_p90_usd,
        "drawdown_breach_rate": evaluation.drawdown_breach_rate,
        "worst_asset_day_usd": evaluation.worst_asset_day_usd,
        "by_asset": {row.asset: {
            "asset_days": row.asset_days, "trades": row.trades,
            "usd_per_asset_day": row.usd_per_asset_day,
            "usd_per_trade": row.usd_per_trade,
            "max_drawdown_usd": row.max_drawdown_usd}
            for row in evaluation.by_asset},
        "arrivals": len(arrivals),
        "occupancy_or_cap_skips": len(arrivals) - len(taken),
        "skipped_ids": sorted(
            row.example.candidate_id for row in arrivals
            if row.example.candidate_id not in taken)[:10],
    }


def _path_stats(sums: Mapping[tuple[str, int], float],
                order: Mapping[str, Sequence[int]]) -> tuple[float, float]:
    """(worst per-asset day-ordered MDD, pooled portfolio day-ordered MDD)."""

    per_asset = max(float(_drawdown([sums.get((asset, day), 0.0)
                                     for day in order[asset]]))
                    for asset in ASSETS)
    width = max(len(order[asset]) for asset in ASSETS)
    pooled = [sum(sums.get((asset, order[asset][slot]), 0.0)
                  for asset in ASSETS if slot < len(order[asset]))
              for slot in range(width)]
    return per_asset, float(_drawdown(pooled))


def block_null(lines: Mapping[str, Sequence[Entry]],
               explore_days: Mapping[str, list[int]],
               draws: int = NULL_DRAWS, seed: int = SEED) -> dict[str, object]:
    """Asset-day block permutation of day-sum labels, shared across lines.

    Permuting day labels inside an asset is total-preserving by construction,
    so this null cannot move a line's cash: what it moves is the PATH.  Two
    path statistics are tested, both "smaller is better" and both reported as
    ``-statistic`` so larger is better: the worst per-asset day-ordered
    drawdown, and the pooled portfolio day-ordered drawdown (which the null
    moves because it re-pairs the three assets' day sums).  Lines that entered
    no cell carry no statistic and are held out of the max-statistic pool.
    """

    names = sorted(name for name in lines if lines[name])
    empty = sorted(name for name in lines if not lines[name])
    sums = {name: day_sums(lines[name]) for name in names}
    rng = np.random.default_rng(seed)
    observed = {name: _path_stats(sums[name], explore_days) for name in names}
    null_by_line: dict[str, list[tuple[float, float]]] = {name: [] for name in names}
    null_max: list[tuple[float, float]] = []
    for _draw in range(draws):
        permuted = {asset: [int(day) for day in rng.permutation(explore_days[asset])]
                    for asset in ASSETS}
        best = (-float("inf"), -float("inf"))
        for name in names:
            statistic = _path_stats(sums[name], permuted)
            null_by_line[name].append(statistic)
            best = (max(best[0], -statistic[0]), max(best[1], -statistic[1]))
        null_max.append(best)
    out: dict[str, object] = {
        "draws": draws, "seed": seed,
        "statistic": "-asset_day_ordered_mdd and -pooled_day_ordered_mdd",
        "total_cash_invariant_under_this_null": True,
        "lines_held_out_empty": empty, "by_line": {}}
    if not names:
        return out
    max_asset = np.asarray([row[0] for row in null_max], np.float64)
    max_pooled = np.asarray([row[1] for row in null_max], np.float64)
    for name in names:
        own_asset = np.asarray([row[0] for row in null_by_line[name]], np.float64)
        own_pooled = np.asarray([row[1] for row in null_by_line[name]], np.float64)
        seen_asset, seen_pooled = observed[name]
        out["by_line"][name] = {
            "observed_max_asset_mdd_usd": seen_asset,
            "observed_pooled_mdd_usd": seen_pooled,
            "null_asset_mdd_mean_usd": float(own_asset.mean()),
            "null_asset_mdd_p05_usd": float(np.percentile(own_asset, 5)),
            "null_pooled_mdd_mean_usd": float(own_pooled.mean()),
            "p_own": float((1 + int(np.sum(-own_asset >= -seen_asset))) / (1 + draws)),
            "p_max_adjusted": float(
                (1 + int(np.sum(max_asset >= -seen_asset))) / (1 + draws)),
            "p_pooled_own": float(
                (1 + int(np.sum(-own_pooled >= -seen_pooled))) / (1 + draws)),
            "p_pooled_max_adjusted": float(
                (1 + int(np.sum(max_pooled >= -seen_pooled))) / (1 + draws)),
        }
    return out


def stage_b(records: Sequence[CellRec], days: Mapping[str, int],
            explore_days: Mapping[str, list[int]],
            stage_a_report: Mapping[str, object]) -> dict[str, object]:
    geos = [geometry(rec) for rec in records]
    cells = cells_by_asset(records)
    gate = r0_gate(records)
    priced: dict[str, list[Entry]] = {}
    report: dict[str, object] = {"r0_median_gate_mid2": gate, "families": {}}
    for family in FAMILIES:
        block = stage_a_report["families"][family]
        selected = block["selection"]["selected"]
        picks = [selected] + list(block["selection"]["neighbors"])
        lines: dict[str, object] = {}
        for key in picks:
            params = tuple(block["configs"][key]["params"])
            entries, skips = price_config(family, params, records, geos)
            name = f"{family}/{key}" + ("/SELECTED" if key == selected else "")
            priced[name] = entries
            lines[key] = {
                "params": list(params), "role": (
                    "selected" if key == selected else "neighbor"),
                "skips": skips, "by_asset": cash_line(entries, days, cells),
                "line_name": name}
            if key == selected:
                lines[key]["replay"] = replay_line(
                    entries, records,
                    f"mill-sweep1:{code_sha()[:16]}:{family}:{key}")
        params = tuple(block["configs"][selected]["params"])
        gated, gate_skips = price_config(family, params, records, geos, gate=gate)
        name = f"{family}/{selected}/F4GATE"
        priced[name] = gated
        lines[f"{selected}+F4"] = {
            "params": list(params), "role": "selected+F4",
            "skips": gate_skips, "by_asset": cash_line(gated, days, cells),
            "line_name": name}
        report["families"][family] = {"selected": selected, "lines": lines}
    report["nulls"] = block_null(priced, explore_days)
    return report


# --------------------------------------------------------------------------
# Hypothesis log.
# --------------------------------------------------------------------------

LOG_FIELDS = (
    "id", "registered_utc", "family", "rule", "params", "spec_sha", "code_sha",
    "split_sha", "outcome_law_sha", "null_seed", "parent_trial",
    "selection_rule", "days", "coverage", "delay_med_s", "err_rate_hg",
    "err_rate_nkd", "err_rate_si", "walls_hg", "walls_nkd", "walls_si",
    "hg_usd_day", "nkd_usd_day", "si_usd_day", "mdd_hg", "mdd_nkd", "mdd_si",
    "replay_skips", "null_margin", "verdict", "note")


def _fmt(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def append_log(rows: Sequence[Mapping[str, object]]) -> int:
    header = LOG_PATH.read_text().splitlines()[0].split("\t")
    if tuple(header) != LOG_FIELDS:
        raise SweepRefusal("hypothesis log header differs from the sweep contract")
    lines = ["\t".join(_fmt(row.get(name)) for name in LOG_FIELDS) for row in rows]
    with LOG_PATH.open("a") as handle:
        handle.write("\n".join(lines) + "\n")
    return len(lines)


def log_rows(report: Mapping[str, object]) -> list[dict[str, object]]:
    stamp = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    shared = {
        "registered_utc": stamp, "spec_sha": SPEC_SHA, "code_sha": code_sha(),
        "split_sha": split_sha(), "outcome_law_sha": outcome_law_sha(),
        "null_seed": SEED, "parent_trial": PARENT_TRIAL,
        "selection_rule": SELECTION_RULE, "verdict": "",
        "days": sum(report["stage_m"]["asset_days"].values()),
    }
    rows: list[dict[str, object]] = []
    counter = 0
    stage = report["stage_a"]
    for family in FAMILIES:
        block = stage["families"][family]
        selected = block["selection"]["selected"]
        for key, entry in sorted(block["configs"].items()):
            counter += 1
            errs = {a: entry["by_asset"][a]["primary_error"] for a in ASSETS}
            rows.append({**shared, "id": f"sweep1-{counter:03d}", "family": family,
                         "rule": key, "params": json.dumps(entry["params"]),
                         "coverage": entry["coverage_pooled"],
                         "delay_med_s": entry["delay_median_pooled_s"],
                         "err_rate_hg": errs["HG"], "err_rate_nkd": errs["NKD"],
                         "err_rate_si": errs["SI"],
                         "note": ("stage-A no-cash"
                                  + (";SELECTED" if key == selected else ""))[:60]})
    if "stage_b" not in report:
        return rows
    nulls = report["stage_b"]["nulls"]["by_line"]
    for family in FAMILIES:
        block = report["stage_b"]["families"][family]
        arow = stage["families"][family]["configs"]
        for key, line in sorted(block["lines"].items()):
            counter += 1
            base = key.split("+")[0]
            entry = arow[base]
            errs = {a: entry["by_asset"][a]["primary_error"] for a in ASSETS}
            cash = line["by_asset"]
            null = nulls.get(line["line_name"], {})
            replay_skips = ""
            if "replay" in line and line["replay"].get("status") == "OK":
                replay_skips = line["replay"]["occupancy_or_cap_skips"]
            rows.append({**shared, "id": f"sweep1-{counter:03d}", "family": family,
                         "rule": key, "params": json.dumps(line["params"]),
                         "coverage": float(np.mean(
                             [cash[a]["coverage"] for a in ASSETS])),
                         "delay_med_s": entry["delay_median_pooled_s"],
                         "err_rate_hg": errs["HG"], "err_rate_nkd": errs["NKD"],
                         "err_rate_si": errs["SI"],
                         "walls_hg": cash["HG"]["walls"],
                         "walls_nkd": cash["NKD"]["walls"],
                         "walls_si": cash["SI"]["walls"],
                         "hg_usd_day": cash["HG"]["usd_per_asset_day"],
                         "nkd_usd_day": cash["NKD"]["usd_per_asset_day"],
                         "si_usd_day": cash["SI"]["usd_per_asset_day"],
                         "mdd_hg": cash["HG"]["mdd_day_usd"],
                         "mdd_nkd": cash["NKD"]["mdd_day_usd"],
                         "mdd_si": cash["SI"]["mdd_day_usd"],
                         "replay_skips": replay_skips,
                         "null_margin": null.get("p_max_adjusted"),
                         "note": f"stage-B {line['role']}"[:60]})
    return rows


# --------------------------------------------------------------------------
# Report I/O and printing.
# --------------------------------------------------------------------------

def _json_default(value: object) -> object:
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"unserialisable sweep value: {type(value)!r}")


def read_report() -> dict[str, object]:
    if OUT_PATH.is_file():
        return json.loads(OUT_PATH.read_text())
    return {"schema": SCHEMA, "tier": "exploratory",
            "claim": "EXPLORE-day sweep 1; can kill, cannot promote"}


def write_report(report: Mapping[str, object]) -> None:
    OUT_PATH.write_text(json.dumps(report, sort_keys=True, indent=1,
                                   default=_json_default) + "\n")


def _num(value: object, width: int = 8, digits: int = 2) -> str:
    if value is None:
        return "-".rjust(width)
    return f"{float(value):{width}.{digits}f}"


def print_m1(block: Mapping[str, object]) -> None:
    print("\n== M1 stability (labelled; entry legality reported separately)")
    print(f"{'asset':5s} {'cells':>6s} {'fs_p25':>8s} {'fs_p50':>8s} {'fs_p75':>8s} "
          f"{'frac25':>7s} {'frac50':>7s} {'frac75':>7s} {'f0':>6s} {'f1':>6s} "
          f"{'f2':>6s} {'f3+':>6s} {'amb@cl':>7s} {'mis@cl':>7s} {'avail':>7s} "
          f"{'mean$':>9s} {'med$':>9s}")
    for asset in ASSETS:
        row = block[asset]
        sec, frac, hist = (row["first_stable_seconds"], row["first_stable_fraction"],
                           row["flip_fraction"])
        cash = row["cash_at_first_stable_plus_60"]
        print(f"{asset:5s} {row['cells']:6d} {_num(sec.get('p25'))} "
              f"{_num(sec.get('p50'))} {_num(sec.get('p75'))} "
              f"{_num(frac.get('p25'), 7, 3)} {_num(frac.get('p50'), 7, 3)} "
              f"{_num(frac.get('p75'), 7, 3)} {_num(hist['0'], 6, 3)} "
              f"{_num(hist['1'], 6, 3)} {_num(hist['2'], 6, 3)} "
              f"{_num(hist['3+'], 6, 3)} {_num(row['ambiguous_at_close'], 7, 3)} "
              f"{_num(row['missing_at_close'], 7, 3)} "
              f"{_num(row['availability']['rate'], 7, 3)} "
              f"{_num(cash['mean_usd'], 9, 1)} {_num(cash['median_usd'], 9, 1)}")
    print("  flip columns are fractions of cells; fs_* are seconds since phase open")


def print_m2(block: Mapping[str, object]) -> None:
    print("\n== M2 oracle timing line (labelled oracle, legal entries only)")
    print(f"{'tau':18s} {'asset':5s} {'cells':>6s} {'entered':>8s} {'amb':>5s} "
          f"{'unav':>5s} {'cover':>6s} {'usd/day':>10s} {'usd/trade':>10s} "
          f"{'win':>6s} {'wall':>6s} {'mdd_day':>9s} {'mdd_trd':>9s} {'rung':>5s}")
    for tau, line in block.items():
        for asset in ASSETS:
            row = line[asset]
            print(f"{tau:18s} {asset:5s} {row['cells']:6d} {row['trades']:8d} "
                  f"{row['ambiguous']:5d} {row['unavailable']:5d} "
                  f"{_num(row['coverage'], 6, 3)} "
                  f"{_num(row['usd_per_asset_day'], 10, 1)} "
                  f"{_num(row['usd_per_trade'], 10, 1)} "
                  f"{_num(row['win_rate'], 6, 3)} {_num(row['wall_rate'], 6, 3)} "
                  f"{_num(row['mdd_day_usd'], 9, 0)} "
                  f"{_num(row['mdd_trade_usd'], 9, 0)} "
                  f"{'Y' if row['clears_rung'] else 'n':>5s}")


def print_m3(block: Mapping[str, object]) -> None:
    print("\n== M3 value-coverage at tau=first_stable+60s (hindsight = labelled bound)")
    print(f"{'asset':5s} {'cov':>5s} {'n':>5s} {'hind$/day':>10s} "
          f"{'hind$/trd':>10s} {'rand$/day':>10s} {'rand$/trd':>10s} "
          f"{'need$/trd':>10s} {'clears':>7s}")
    for asset in ASSETS:
        row = block[asset]
        for coverage in COVERAGE_GRID:
            cell = row["coverage_table"][f"{coverage:.1f}"]
            print(f"{asset:5s} {coverage:5.1f} {cell['entered']:5d} "
                  f"{_num(cell['hindsight_usd_day'], 10, 1)} "
                  f"{_num(cell['hindsight_usd_trade'], 10, 1)} "
                  f"{_num(cell['random_usd_day'], 10, 1)} "
                  f"{_num(cell['random_usd_trade'], 10, 1)} "
                  f"{_num(cell['required_entered_mean_usd'], 10, 1)} "
                  f"{'Y' if cell['hindsight_clears_rung'] else 'n':>7s}")
        print(f"  {asset}: rung={row['day_rung_usd']:.0f}/day  "
              f"min clearing coverage={row['min_clearing_coverage']}")


def print_m4(block: Mapping[str, object]) -> None:
    print("\n== M4 error budget on the M2 tau=first_stable+60s line")
    print(f"{'rate':>5s} {'place':12s} {'asset':5s} {'flip':>5s} {'drop':>5s} "
          f"{'usd/day':>10s} {'mdd_day':>9s} {'rung':>5s} {'mdd<1k':>7s}")
    for rate in ERROR_RATES:
        for placement in ("random", "adversarial"):
            entry = block["rates"][f"{rate:.2f}"][placement]
            for asset in ASSETS:
                row = entry["by_asset"][asset]
                print(f"{rate:5.2f} {placement:12s} {asset:5s} "
                      f"{int(row['flipped']):5d} {_num(row['dropped'], 5, 1)} "
                      f"{_num(row['usd_per_asset_day'], 10, 1)} "
                      f"{_num(row['mdd_day_usd'], 9, 0)} "
                      f"{'Y' if row['usd_per_asset_day'] >= DAY_RUNG_USD[asset] else 'n':>5s} "
                      f"{'Y' if row['mdd_day_usd'] < MDD_CAP_USD else 'n':>7s}")
    print(f"  budget (all three rungs AND mdd<1000): "
          f"random={block['budget_global']['random']:.2f} "
          f"adversarial={block['budget_global']['adversarial']:.2f}")
    print(f"  per-asset budget (adversarial, used by selection): "
          f"{block['budget_used']}")


def print_stage_a(report: Mapping[str, object], top: int = 5) -> None:
    print("\n== STAGE A detector grids (no cash)")
    print(f"  budget b_a={report['budget_by_asset']}  "
          f"coverage floor c_a={report['coverage_floor_by_asset']}")
    for family in FAMILIES:
        block = report["families"][family]
        selection = block["selection"]
        print(f"\n-- {family}  configs={len(block['configs'])} "
              f"pass_budget={selection['n_pass_budget']} "
              f"pass_coverage={selection['n_pass_coverage']} "
              f"selected={selection['selected']} flags={selection['flags'] or '-'}")
        print(f"  {'rule':16s} {'cov':>6s} {'unav':>6s} {'delay_s':>8s} "
              f"{'dly_fs':>8s} {'e_HG':>6s} {'e_NKD':>6s} {'e_SI':>6s} "
              f"{'ciU_HG':>7s} {'ciU_NKD':>7s} {'ciU_SI':>7s} {'sec_max':>7s}")
        keys = list(selection["ordered"][:top])
        if selection["selected"] not in keys:
            keys.append(selection["selected"])
        for key in keys:
            entry = block["configs"][key]
            per = entry["by_asset"]
            delays = [per[a]["delay_since_first_stable_median_s"] for a in ASSETS]
            valid = [d for d in delays if d is not None]
            secondary = max((per[a]["secondary_error"] or 0.0) for a in ASSETS)
            mark = "*" if key == selection["selected"] else " "
            print(f" {mark}{key:16s} {_num(entry['coverage_pooled'], 6, 3)} "
                  f"{_num(np.mean([per[a]['unavailable_rate'] for a in ASSETS]), 6, 3)} "
                  f"{_num(entry['delay_median_pooled_s'], 8, 0)} "
                  f"{_num(np.median(valid) if valid else None, 8, 0)} "
                  + " ".join(_num(per[a]["primary_error"], 6, 3) for a in ASSETS)
                  + " "
                  + " ".join(_num(per[a]["primary_ci95"][1], 7, 3) for a in ASSETS)
                  + f" {_num(secondary, 7, 3)}")
        print(f"  neighbors priced in stage B: {selection['neighbors']}")


def print_stage_b(report: Mapping[str, object]) -> None:
    print("\n== STAGE B priced lines (frozen outcome law, EXPLORE days)")
    gate = {key: round(float(value))
            for key, value in report["r0_median_gate_mid2"].items()}
    print(f"  F4 gate = per-asset median R0 (mid2 units): {gate}")
    print(f"  {'family':8s} {'rule':18s} {'role':12s} {'asset':5s} {'trd':>5s} "
          f"{'cov':>6s} {'usd/day':>10s} {'usd/trd':>10s} {'win':>6s} "
          f"{'wall':>5s} {'mdd_day':>9s} {'mdd_trd':>9s} {'rung':>5s}")
    for family in FAMILIES:
        for key, line in report["families"][family]["lines"].items():
            for asset in ASSETS:
                row = line["by_asset"][asset]
                print(f"  {family:8s} {key:18s} {line['role']:12s} {asset:5s} "
                      f"{row['trades']:5d} {_num(row['coverage'], 6, 3)} "
                      f"{_num(row['usd_per_asset_day'], 10, 1)} "
                      f"{_num(row['usd_per_trade'], 10, 1)} "
                      f"{_num(row['win_rate'], 6, 3)} {row['walls']:5d} "
                      f"{_num(row['mdd_day_usd'], 9, 0)} "
                      f"{_num(row['mdd_trade_usd'], 9, 0)} "
                      f"{'Y' if row['clears_rung'] else 'n':>5s}")
    print("\n  engine replay (SELECTED lines; partial-day: the split breaks "
          "portfolio days)")
    print(f"  {'family':8s} {'rule':18s} {'stat':28s} {'value':>12s}")
    for family in FAMILIES:
        block = report["families"][family]
        line = block["lines"][block["selected"]]
        rep = line.get("replay", {"status": "ABSENT"})
        if rep.get("status") != "OK":
            print(f"  {family:8s} {block['selected']:18s} status "
                  f"{rep.get('status'):>12s}")
            continue
        for name in ("asset_days", "trades", "usd_per_asset_day", "usd_per_trade",
                     "max_drawdown_usd", "drawdown_p90_usd",
                     "drawdown_breach_rate", "worst_asset_day_usd",
                     "arrivals", "occupancy_or_cap_skips"):
            print(f"  {family:8s} {block['selected']:18s} {name:28s} "
                  f"{_num(rep[name], 12, 3)}")
        for asset, values in sorted(rep["by_asset"].items()):
            print(f"  {family:8s} {block['selected']:18s} "
                  f"{'replay/' + asset:28s} "
                  f"usd_day={values['usd_per_asset_day']:.1f} "
                  f"trades={values['trades']} "
                  f"mdd={values['max_drawdown_usd']:.0f}")
    nulls = report["nulls"]
    print(f"\n  block-permutation null: draws={nulls['draws']} seed={nulls['seed']} "
          f"statistic={nulls['statistic']}")
    print("  (within-asset day-label permutation preserves each line's total cash "
          "exactly; the null moves the path, so the tested statistic is the "
          "day-ordered drawdown)")
    if nulls.get("lines_held_out_empty"):
        print(f"  held out (entered no cell): {nulls['lines_held_out_empty']}")
    print(f"  {'line':34s} {'obs_mdd':>9s} {'null_mean':>10s} {'null_p05':>10s} "
          f"{'p_own':>7s} {'p_maxadj':>9s} {'pool_mdd':>9s} {'p_pool':>7s} "
          f"{'p_pl_adj':>9s}")
    for name, value in sorted(nulls["by_line"].items()):
        print(f"  {name:34s} {_num(value['observed_max_asset_mdd_usd'], 9, 0)} "
              f"{_num(value['null_asset_mdd_mean_usd'], 10, 0)} "
              f"{_num(value['null_asset_mdd_p05_usd'], 10, 0)} "
              f"{_num(value['p_own'], 7, 3)} {_num(value['p_max_adjusted'], 9, 3)} "
              f"{_num(value['observed_pooled_mdd_usd'], 9, 0)} "
              f"{_num(value['p_pooled_own'], 7, 3)} "
              f"{_num(value['p_pooled_max_adjusted'], 9, 3)}")


# --------------------------------------------------------------------------
# Selftest: synthetic bytes only.
# --------------------------------------------------------------------------

SELFTEST_ASSET = "HG"
SELFTEST_D8 = 20220301
SELFTEST_OPEN = 1_600_000_000 * NANOS_PER_SECOND
SELFTEST_BASE_BID = 4_500_000_000
SELFTEST_SPAN = 4800
SELFTEST_BLOCKS = (100, 110, 90, 120, 80, 130, 70)
SELFTEST_CONFIG = (2, 0.25, 30)
SELFTEST_BAR = 8
SELFTEST_SIDE = -1
SELFTEST_MUTANT_BAR = 7


def _selftest_shard(root: Path):
    """A hand-computable FAM-XR fixture.  Touches zero era bytes."""

    import build_substrate as B  # noqa: PLC0415 - sibling module, path pinned

    from engine.entry_v2.event_pack import EVENT_DTYPE
    from decimal import Decimal
    from engine.entry_v2.diagnostic_types import UNITS_PER_USD

    tick = ASSET_RAW_TICK[SELFTEST_ASSET]
    multiplier = ASSET_MULTIPLIER[SELFTEST_ASSET]
    n = SELFTEST_SPAN + 1
    steps = np.full(n, SELFTEST_BLOCKS[-1], np.int64)
    for block in range(n // BAR_SECONDS + 1):
        lo = block * BAR_SECONDS
        value = (SELFTEST_BLOCKS[block] if block < len(SELFTEST_BLOCKS)
                 else SELFTEST_BLOCKS[0])
        steps[lo:lo + BAR_SECONDS] = value
    steps[SELFTEST_SPAN] = SELFTEST_BLOCKS[0]
    rows = np.zeros(n, EVENT_DTYPE)
    ts = SELFTEST_OPEN + np.arange(n, dtype=np.int64) * NANOS_PER_SECOND
    rows["ts_recv_ns"] = ts.astype(np.uint64)
    rows["ts_event_ns"] = ts.astype(np.uint64)
    bid = SELFTEST_BASE_BID + steps * tick
    rows["bid_px"] = bid
    rows["ask_px"] = bid + tick
    rows["price"] = bid
    rows["receive_session_sec"] = np.arange(n, dtype=np.int64)
    close_ns = int(ts[-1])
    units = int(Decimal("25") * UNITS_PER_USD)

    def _candidate(cid: str, second: int, side: int) -> B.MillCandidate:
        row = int(second)
        b_px, a_px = int(rows["bid_px"][row]), int(rows["ask_px"][row])
        return B.MillCandidate(
            cid, SELFTEST_ASSET, SELFTEST_D8, 1,
            int(ts[row]), side, "0", int(ts[0]), close_ns, b_px + a_px, b_px, a_px,
            Decimal(a_px - b_px) * Decimal(multiplier) / Decimal(NANOS_PER_SECOND)
            + Decimal(str(FEE_USD)), units, multiplier, row + 1,
            "0" * 64, "0" * 64, "0" * 64)

    candidates = (_candidate("SWEEP-LONG", 280, 1),
                  _candidate("SWEEP-SHORT", 460, -1))
    for candidate in candidates:
        candidate.validate()
    arrays, sidecar = B.extract_shard(
        SELFTEST_ASSET, SELFTEST_D8, rows, candidates, locked_iid=1,
        open_utc=int(ts[0]) // NANOS_PER_SECOND,
        close_utc=close_ns // NANOS_PER_SECOND, pack_sha256="0" * 64,
        candidates_sha256="0" * 64, candidate_rows=len(candidates))
    B.write_shard(root, SELFTEST_ASSET, SELFTEST_D8, arrays, sidecar)
    return M.load_shard(SELFTEST_ASSET, SELFTEST_D8, root=root)


def selftest() -> int:
    mutant = os.environ.get("QRE2_MILL_MUTANT", "")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        shard = _selftest_shard(root)
        records = build_cells(shard)
        if len(records) != 1:
            print(f"DEAD: synthetic cell count is {len(records)}, expected 1")
            return 1
        rec = records[0]
        geo = geometry(rec)
        hand = ([SELFTEST_BLOCKS[0]] + list(SELFTEST_BLOCKS)
                + [SELFTEST_BLOCKS[0]])
        observed = [int(round((value - 2 * SELFTEST_BASE_BID
                               - ASSET_RAW_TICK[SELFTEST_ASSET])
                              / (2 * ASSET_RAW_TICK[SELFTEST_ASSET])))
                    for value in rec.mid[:len(hand)]]
        checks: list[tuple[str, bool, str]] = []
        checks.append(("bar_series_hand_computed", observed == hand,
                       f"bars {observed} != hand {hand}"))
        checks.append(("first_formation_bar", rec.k0 == 5,
                       f"k0={rec.k0} expected 5"))
        call = declare_xr(rec, geo, *SELFTEST_CONFIG)
        checks.append(("xr_declares", call is not None, "FAM-XR did not declare"))
        if call is not None:
            checks.append(("xr_declaration_bar", call.bar == SELFTEST_BAR,
                           f"declared at bar {call.bar} expected {SELFTEST_BAR}"))
            checks.append(("xr_declaration_side", call.side == SELFTEST_SIDE,
                           f"declared side {call.side} expected {SELFTEST_SIDE}"))
            checks.append((
                "entry_legality_gate",
                rec.legal_at(SELFTEST_SIDE, SELFTEST_BAR)
                and not rec.legal_at(SELFTEST_SIDE, SELFTEST_MUTANT_BAR),
                f"short legal_from={rec.legal_from_m}, expected legal at "
                f"{SELFTEST_BAR} and illegal at {SELFTEST_MUTANT_BAR}"))
            entry = make_entry(0, rec, call.bar, call.side)
            checks.append(("entry_is_legal", entry is not None,
                           "the legal declaration produced no entry"))
            if entry is not None:
                want_ts = int(rec.phase_open_ts_ns + SELFTEST_BAR * BAR_NS)
                index = shard.cell_index(shard.cells[0])
                want_mid = int(index.mid2[SELFTEST_BAR * BAR_SECONDS - 1])
                checks.append(("entry_timestamp", entry.ts_ns == want_ts,
                               f"entry ts {entry.ts_ns} != {want_ts}"))
                checks.append((
                    "entry_quote_row", int(rec.mid[SELFTEST_BAR]) == want_mid,
                    f"entry quote {int(rec.mid[SELFTEST_BAR])} != row "
                    f"{SELFTEST_BAR * BAR_SECONDS - 1} mid {want_mid}"))
        dead = [(name, why) for name, ok, why in checks if not ok]
        if dead:
            for name, why in dead:
                print(f"DEAD: {name}: {why}")
            print(f"sweep1_selftest_dead mutant={mutant or 'none'} "
                  f"cases={len(dead)}/{len(checks)}")
            return 1
    if mutant:
        print(f"DEAD: mutant {mutant} left every sweep-1 case green")
        return 1
    print(f"sweep1_selftest_ok cases={len(checks)}")
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _explore_days(assets: Sequence[str]) -> dict[str, list[int]]:
    table = json.loads(SPLIT_PATH.read_text())["explore"]
    return {asset: sorted(int(day) for day in table[asset]) for asset in assets}


def _need_cache() -> tuple[list[CellRec], list[Label], dict[str, int]]:
    records, days = load_cache()
    return records, labels_for(records), days


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", nargs="?", default="all",
                        choices=("prep", "m1", "m2", "m3", "m4", "stage-m",
                                 "stage-a", "stage-b", "log", "all"))
    parser.add_argument("--assets", default="HG,NKD,SI")
    parser.add_argument("--root", default=str(M.MILL_ROOT))
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    assets = tuple(name.strip().upper() for name in args.assets.split(",")
                   if name.strip())
    started = time.monotonic()
    report = read_report()
    report.setdefault("spec_sha", SPEC_SHA)
    report["code_sha"] = code_sha()
    report["split_sha"] = split_sha()
    report["outcome_law_sha"] = outcome_law_sha()

    if args.stage in ("prep", "all"):
        store = M.load_store(SPLIT_PATH, assets, root=Path(args.root))
        records, days = prep(store)
        save_cache(records, days)
        print(f"prep: cells={len(records)} asset_days={days} "
              f"wall={time.monotonic() - started:.1f}s")
    if args.stage == "prep":
        write_report(report)
        return 0

    records, labels, days = _need_cache()
    explore_days = _explore_days(assets)
    stage_m = report.get("stage_m", {"asset_days": days,
                                     "cells": cells_by_asset(records)})
    stage_m["asset_days"] = days
    stage_m["cells"] = cells_by_asset(records)

    if args.stage in ("m1", "stage-m", "all"):
        stage_m["m1"] = m1(records, labels, days)
        print_m1(stage_m["m1"])
    if args.stage in ("m2", "stage-m", "all"):
        stage_m["m2"] = m2(records, labels, days)
        print_m2(stage_m["m2"])
    if args.stage in ("m3", "stage-m", "all"):
        stage_m["m3"] = m3(records, labels, days)
        print_m3(stage_m["m3"])
    if args.stage in ("m4", "stage-m", "all"):
        stage_m["m4"] = m4(records, labels, days)
        print_m4(stage_m["m4"])
    report["stage_m"] = stage_m

    if args.stage in ("stage-a", "stage-b", "log", "all"):
        if "m3" not in stage_m or "m4" not in stage_m:
            raise SweepRefusal("stage A needs M3 and M4; run stage-m first")
        budgets = {a: float(stage_m["m4"]["budget_used"][a]) for a in ASSETS}
        floors = {a: float(stage_m["m3"][a]["min_clearing_coverage"] or 0.0)
                  for a in ASSETS}
    if args.stage in ("stage-a", "all"):
        report["stage_a"] = stage_a(records, labels, budgets, floors)
        print_stage_a(report["stage_a"], args.top)
    if args.stage in ("stage-b", "all"):
        if "stage_a" not in report:
            raise SweepRefusal("stage B needs stage A; run stage-a first")
        report["stage_b"] = stage_b(records, days, explore_days,
                                    report["stage_a"])
        print_stage_b(report["stage_b"])
    if args.stage in ("log", "all"):
        if "stage_a" not in report:
            raise SweepRefusal("the log needs stage A")
        rows = log_rows(report)
        written = append_log(rows)
        report["log"] = {"rows_appended": written,
                         "registered_utc": rows[0]["registered_utc"]}
        print(f"\nlog: appended {written} rows to {LOG_PATH}")

    report["wall_seconds"] = round(time.monotonic() - started, 2)
    write_report(report)
    print(f"\nwrote {OUT_PATH} wall={report['wall_seconds']}s "
          f"cells={len(records)} spec_sha={SPEC_SHA[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
