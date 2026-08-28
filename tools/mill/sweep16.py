#!/usr/bin/env python3
"""Sweep 16 of the side-resolution mill: fixed-horizon exit feasibility.

USER proposal under test: replace or augment the hold-to-phase-close payoff with
a FIXED holding duration, so the policy predicts the next hour instead of the
phase's end.  The frozen exit law is NOT changed by this unit.  Nothing here is
executable and nothing here licenses a rewrite of the exit; the unit only
measures what the change would buy, on the existing caches, so the decision to
spend engineering on a fixed-hold exit is made against numbers rather than
against the intuition that a shorter hold must be easier to predict.

Machinery is imported, never re-implemented.  Sweep 14 supplies the occurrence
stream, the 16-feature plane and the walk-forward fold law (and, through it,
sweep 9's row plane whose counters are this unit's refuse-to-run gate).  Sweep
13 supplies the FIRST and SECOND entry sets under their own frozen resolvers.
Sweep 1 supplies the outcome law, the cash reductions, the drawdown and the log.
The horizon label plane is the ONE new object: the mill's own outcome machinery
called with the close parameter set per entry.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
import math
import os
from pathlib import Path
import sys
import time
from types import MappingProxyType
from typing import Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine.entry_v2.confirmation_types import FEE_USD, WALL_USD  # noqa: E402

import mill as M  # noqa: E402
import sweep1 as S1  # noqa: E402
import sweep8 as S8  # noqa: E402
import sweep9_twins as S9  # noqa: E402
import sweep12 as S12  # noqa: E402
import sweep13 as S13  # noqa: E402
import sweep14 as S14  # noqa: E402

# --------------------------------------------------------------------------
# The law, registered before anything is read.
# --------------------------------------------------------------------------

SPEC = """QRE2MILLSWEEP16
tier=exploratory; EXPLORE-only.  Family F13-FIXHOLD.  Seed 20260827.  Parent =
  the hypothesis-log tail at registration.  NO COMMITS, NO FREEZE: this unit
  measures a proposal, it does not adopt one.  The frozen exit law is untouched.
DATA LAW.  EXPLORE days only, off the existing mill caches.  No packs, no HOLD,
  no teacher labels, no 2021, no 2025.  The occurrence stream, the 16-feature
  plane and the walk-forward fold law are sweep 14's, imported verbatim; sweep
  9's row-plane counters (47402 rows; certifiable 138/132/132) are the
  refuse-to-run gate.
NEW LABEL PLANE.  For every occurrence k and horizon h in {1800, 3600, 5400,
  7200} s: Y_h(k) = the cert in USD of entering at k's stamp on its fade side and
  exiting at the FIRST of (the -900 wall crossing, entry_time + h, phase close).
  Same entry quote and the same frozen cost law as the mill, cost charged once at
  entry.  Computed through the mill's own outcome machinery with the close
  parameter set to min(entry + h, phase_close) PER ENTRY; the generation
  truncation, the wall boundary and the extrema window are the frozen ones.
  Y_close, the existing to-close label, is carried beside every horizon.
M1 PREDICTABILITY.  Out-of-fold R2 of Y_h on the 16-feature plane under sweep
  14's exact fold law (>= 25 strictly prior EXPLORE days per asset; training
  cells are that asset's earlier EXPLORE days; ridge lambda 1.0, features
  standardised, intercept unpenalised).  Separately R2 of sign(Y_h) and |Y_h|,
  and the same three for Y_close.  R2 is 1 - SSE/SST against the pooled
  out-of-fold target mean.
M2 THE ORDINAL MECHANISM'S CASH VALUE.  Sweep 13's FIRST (the frozen sweep-8
  PRIMARY resolver) and SECOND (the ordinal-2 resolver) entry sets, imported with
  their frozen laws, priced under each Y_h and under Y_close.  Statistic: the
  mean paired asset-day difference SECOND minus FIRST in USD per asset-day.  Null
  is 10000 sign flips over the asset-day blocks, one-sided positive, with a
  max-stat adjustment over the pool of (asset x horizon) lines.
M3 NOISE-CEILING UNDER Y_h.  Per-cell-max oracle over the occurrence stream
  (FINE grain: every occurrence; COARSE grain: the post-reset first occurrence,
  ord_side == 1) against cross-cell within-stratum shuffled ceilings, stratum =
  (asset, phase), 200 draws, cell occurrence counts preserved.  Structure excess
  = real mean per-cell-max minus mean shuffled ceiling; its percentile is the
  share of shuffle draws strictly below the real value.  The result is BANDED in
  three, not two: ABOVE-P95 (the pre-registered structure finding), BELOW-P5 (a
  finding in its own right - the big outcomes cluster inside cells, so
  scattering them RAISES the ceiling; this is what sibling sweep 15 reported on
  the to-close label) and WITHIN-BAND (the null).  The band is reported as its
  own row and is never folded into a registered decision letter by elimination.
M4 THE RUNG ARITHMETIC UNDER SEQUENTIAL CAPACITY.  One position per asset frees
  the seat during the phase, so capacity per asset-day at h is
  sum over the day's cells of floor((span + wait) / (h + wait)) with wait = the
  observed candidate-wait median (median in-cell inter-occurrence gap), capped at
  12 portfolio-wide across 3 assets (4 per asset-day).  Required per-trade at the
  rung = rung / (capacity x coverage) for coverage in {0.4, 0.6}, printed beside
  the observed mean Y_h of the E[Y|s]-top-decile occurrences (fitted on the train
  folds, evaluated out-of-fold) as the honest edge estimate.  A SECOND
  out-of-fold selector ranks by predicted |Y_h| off the M1 magnitude channel's
  own fold fits and reports top-decile mean Y_h, mean |Y_h| and win rate.
CROSS-CHECK.  This unit's Y_close magnitude channel must reproduce sibling sweep
  15's banked out-of-fold |Y| R2 of +0.119/+0.127/+0.096 (HG/NKD/SI) to three
  decimals; the sign and magnitude channels are reported with equal prominence
  at every horizon, because on the to-close label the state predicts magnitude
  and does NOT predict sign, and whether a short hold recovers the SIGN channel
  is the live question this unit exists to answer.
M5 MDD SHAPE.  Day-ordered MDD of the day sums for the M2 SECOND line at each h,
  against the same line's to-close MDD.
DECISION TABLE, pre-registered.  HORIZON-VIABLE if at some h on a deciding asset
  (NKD, SI): out-of-fold R2(Y_h) >= 0.02 OR the M2 SECOND-FIRST dollar delta is
  positive with max-adjusted p <= 0.05; AND M3 shows structure excess above the
  shuffle p95 at either grain; AND M4's required per-trade at 0.6 coverage is
  within 2x of the observed top-decile mean Y_h.  LABEL-ONLY if predictability
  appears but the arithmetic falls short.  DEAD if no horizon moves any of R2,
  the mechanism cash, or the structure excess.
MUTANT.  QRE2_MILL_S16_MUTANT=horizon_reads_past_exit computes the feature plane
  with post-exit rows (range_atr taken through the horizon exit bar instead of
  through the entry bar).  It must turn the selftest red.
"""

ASSETS = S1.ASSETS
DECIDING = ("NKD", "SI")
REPORT_ONLY = ("HG",)
PHASES = S14.PHASES
BAR_SECONDS = S1.BAR_SECONDS
NANOS = 1_000_000_000
SEED = 20260827

HORIZONS = (1800, 3600, 5400, 7200)
CLOSE = "close"
LABELS = tuple(str(h) for h in HORIZONS) + (CLOSE,)

# Frozen, inherited.  Aliases so a drift upstream fails loudly here.
FEATURES = S14.FEATURES
NFEAT = S14.NFEAT
RIDGE_LAMBDA = S14.RIDGE_LAMBDA          # 1.0
MIN_PRIOR_DAYS_FIT = S14.MIN_PRIOR_DAYS_FIT   # 25
MIN_FIT_ROWS = S14.MIN_FIT_ROWS          # 50
REMAIN_MIN_S = S14.REMAIN_MIN_S          # 1800
DAY_RUNG_USD = S1.DAY_RUNG_USD
REPRO_ROWS = S14.REPRO_ROWS              # 47402
REPRO_CERTIFIABLE = S14.REPRO_CERTIFIABLE     # 138/132/132
REPRO_COUNTERS = S14.REPRO_COUNTERS

# The one new law's constants.
HAND_CHECK_ROWS = 20
SHUFFLE_DRAWS = 200
SIGN_FLIPS = 10_000
COVERAGES = (0.4, 0.6)
PORTFOLIO_CAP = 12
TOP_DECILE = 0.10

# Pre-registered decision bounds.
R2_FLOOR = 0.02
P_CEILING = 0.05
ARITHMETIC_FACTOR = 2.0

FAMILY = "F13-FIXHOLD"
SELECTION_RULE = ("none: pre-registered horizon grid, imported fold law, "
                  "imported FIRST/SECOND resolvers, no tuning")

MUTANT_ENV = "QRE2_MILL_S16_MUTANT"
MUTANT_PAST = "horizon_reads_past_exit"
MUTANTS = (MUTANT_PAST,)

OUT_PATH = ROOT / ".audit/mill-sweep16.json"
LOG_PATH = S1.LOG_PATH


class SweepRefusal(RuntimeError):
    pass


SPEC_SHA = S1._sha_text(SPEC)


def code_sha() -> str:
    return S1._sha_file(Path(__file__).resolve())


def _mutant() -> str:
    name = os.environ.get(MUTANT_ENV, "")
    if name and name not in MUTANTS:
        raise SweepRefusal(f"unknown sweep-16 mutant {name!r}; known: {MUTANTS}")
    return name


def parent_trial() -> str:
    """The hypothesis-log tail at registration, read rather than guessed."""

    lines = [row for row in LOG_PATH.read_text().splitlines() if row.strip()]
    if len(lines) < 2:
        raise SweepRefusal("the hypothesis log has no rows to parent from")
    return lines[-1].split("\t")[0]


def _q(values: Sequence[float], mark: float) -> float | None:
    array = np.asarray(list(values), np.float64)
    return None if not len(array) else float(np.percentile(array, mark))


# --------------------------------------------------------------------------
# THE NEW LABEL PLANE: the mill's outcome machinery with a PER-ENTRY close.
# --------------------------------------------------------------------------

def outcomes_grid_capped(index: M.MillIndex, t_ns: np.ndarray, side: int,
                         close_ts_ns: np.ndarray, *,
                         entry_mid2: np.ndarray | None = None,
                         cost_usd: np.ndarray | None = None,
                         ) -> Mapping[str, np.ndarray]:
    """``MillIndex.outcomes_grid`` with the close taken PER ENTRY.

    Line-for-line the frozen batched law (``mill.py`` 211-283) with the single
    scalar ``phase_end`` replaced by a per-entry array.  Everything else - the
    strict-left start, the raw-generation expectation, the generation-end
    truncation, the wall boundary's floor/ceil, the extrema window and the cert
    arithmetic - is the frozen law, unchanged.  This is the only place the
    fixed-hold proposal touches the outcome machinery, and it touches it by
    passing a different close, never by editing the exit.
    """

    snapshots = np.asarray(t_ns, np.int64)
    closes = np.asarray(close_ts_ns, np.int64)
    if snapshots.shape != closes.shape or int(side) not in (-1, 1):
        raise SweepRefusal("capped-grid inputs are invalid")
    empty = M.MillIndex._empty_grid()
    if not len(snapshots) or not len(index.ts):
        return empty
    quote_at = index.positions(snapshots)
    starts_all = np.searchsorted(index.ts, snapshots.astype(np.uint64),
                                 side="left")
    phase_end = np.searchsorted(index.ts, closes.astype(np.uint64), side="right")
    keep = np.flatnonzero((starts_all < phase_end) & (quote_at >= 0))
    if not len(keep):
        return empty
    starts = starts_all[keep]
    entries = (index.mid2[quote_at[keep]] if entry_mid2 is None
               else np.asarray(entry_mid2, np.int64)[keep])
    costs = ((index.ask[quote_at[keep]] - index.bid[quote_at[keep]])
             * index.multiplier / 1e9 + FEE_USD if cost_usd is None
             else np.asarray(cost_usd, np.float64)[keep])
    expected = index.generations_at_snapshots(snapshots[keep])
    ends = np.minimum(phase_end[keep], index._engine.generation_end[starts])
    valid = (index.generation[starts] == expected) & (starts < ends)
    keep = keep[valid]
    if not len(keep):
        return empty
    starts = starts[valid]
    ends = ends[valid]
    entries = np.asarray(entries, np.int64)[valid]
    costs = np.asarray(costs, np.float64)[valid]
    if side > 0:
        threshold = np.floor(entries + (-WALL_USD + costs) / index.factor)
        wall = index.range.first_many(starts, ends, threshold.astype(np.int64),
                                      use_min=True)
    else:
        threshold = np.ceil(entries + (WALL_USD - costs) / index.factor)
        wall = index.range.first_many(starts, ends, threshold.astype(np.int64),
                                      use_min=False)
    exit_position = np.where(wall < 0, ends - 1, wall).astype(np.int64)
    exit_mid = index.mid2[exit_position]
    cert = side * (exit_mid - entries) * index.factor - costs
    low, high = index.range.extrema_many(starts, exit_position + 1)
    low_value = side * (low - entries) * index.factor - costs
    high_value = side * (high - entries) * index.factor - costs
    return MappingProxyType({
        "input_index": keep.astype(np.int64),
        "entry_mid2": entries,
        "frozen_cost_usd": costs,
        "cert_close_usd": cert.astype(np.float64),
        "mfe_usd": np.maximum(0.0, np.maximum(low_value, high_value)),
        "mae_usd": np.maximum(0.0, -np.minimum(low_value, high_value)),
        "wall_hit": wall >= 0,
        "exit_ts_ns": index.ts[exit_position].astype(np.int64),
        "exit_row": exit_position,
    })


@dataclass(slots=True)
class HorizonPlane:
    """Per cell position: Y_h and its exit stamp for both sides, all horizons."""

    cert: dict[tuple[int, int, str], np.ndarray] = field(default_factory=dict)
    ok: dict[tuple[int, int, str], np.ndarray] = field(default_factory=dict)
    wall: dict[tuple[int, int, str], np.ndarray] = field(default_factory=dict)
    exit_ts: dict[tuple[int, int, str], np.ndarray] = field(default_factory=dict)
    exit_row: dict[tuple[int, int, str], np.ndarray] = field(default_factory=dict)
    mid: dict[int, np.ndarray] = field(default_factory=dict)
    counters: dict[str, int] = field(default_factory=dict)

    def y(self, position: int, side: int, label: str, bar: int) -> float:
        return float(self.cert[(int(position), int(side), label)][int(bar)])

    def valid(self, position: int, side: int, label: str, bar: int) -> bool:
        return bool(self.ok[(int(position), int(side), label)][int(bar)])


def build_horizon_plane(records: Sequence[S1.CellRec],
                        horizons: Sequence[int] = HORIZONS,
                        hand_checks: int = HAND_CHECK_ROWS,
                        ) -> tuple[HorizonPlane, list[dict[str, object]]]:
    """Y_h on the 60 s lattice of every cached cell, both sides, per-entry close.

    The batched per-entry-close path is the one that produces the numbers; the
    ``hand`` list re-derives a sample of rows one at a time through the frozen
    scalar ``MillIndex.outcome`` with the same per-entry close, so the batching
    is checked against the shipped single-row law rather than against itself.
    """

    plane = HorizonPlane()
    plane.counters = {"cells": 0, "cells_missing_shard_cell": 0,
                      "grid_calls": 0, "hand_checks": 0}
    hand: list[dict[str, object]] = []
    by_day: dict[tuple[str, int], list[int]] = {}
    for position, rec in enumerate(records):
        by_day.setdefault((rec.asset, rec.d8), []).append(position)
    rng = np.random.default_rng(SEED)
    for (asset, d8) in sorted(by_day):
        shard = M.load_shard(asset, d8)
        try:
            by_text = {cell.text: cell for cell in shard.cells}
            for position in by_day[(asset, d8)]:
                rec = records[position]
                cell = by_text.get(rec.text)
                if cell is None:
                    plane.counters["cells_missing_shard_cell"] += 1
                    continue
                index = shard.cell_index(cell)
                lat = np.asarray(rec.lat, np.int64)
                positions, mid, bid, ask = M.bar_series(index, lat)
                quote_ok = (positions >= 0) & (bid > 0) & (ask > bid)
                cost = (ask - bid) * float(index.multiplier) / 1e9 + FEE_USD
                plane.mid[position] = np.asarray(rec.mid, np.float64)
                close_ns = int(rec.phase_close_ts_ns)
                for side in (1, -1):
                    for h in horizons:
                        label = str(int(h))
                        closes = np.minimum(lat + int(h) * NANOS, close_ns)
                        grid = outcomes_grid_capped(
                            index, lat, side, closes, entry_mid2=mid,
                            cost_usd=cost)
                        plane.counters["grid_calls"] += 1
                        cert = np.zeros(len(lat), np.float64)
                        wall = np.zeros(len(lat), np.bool_)
                        stamp = np.zeros(len(lat), np.int64)
                        row = np.full(len(lat), -1, np.int64)
                        ok = np.zeros(len(lat), np.bool_)
                        take = grid["input_index"]
                        if len(take):
                            cert[take] = grid["cert_close_usd"]
                            wall[take] = grid["wall_hit"]
                            stamp[take] = grid["exit_ts_ns"]
                            row[take] = grid["exit_row"]
                            ok[take] = True
                        ok &= quote_ok
                        key = (position, side, label)
                        plane.cert[key] = cert
                        plane.wall[key] = wall
                        plane.ok[key] = ok
                        plane.exit_ts[key] = stamp
                        plane.exit_row[key] = row
                        # A sample of rows re-derived through the frozen scalar
                        # outcome() with the same per-entry close.
                        if len(hand) < hand_checks and len(take):
                            pick = int(take[int(rng.integers(0, len(take)))])
                            quote = index.current(int(lat[pick]))
                            if quote is not None and 0 < quote[0] < quote[1]:
                                single = index.outcome(
                                    int(lat[pick]), side, int(quote[2]),
                                    M.frozen_cost_usd(quote[0], quote[1], asset),
                                    int(min(int(lat[pick]) + int(h) * NANOS,
                                            close_ns)))
                                hand.append({
                                    "cell": rec.text, "side": int(side),
                                    "horizon_s": int(h), "bar": pick,
                                    "batched_usd": float(cert[pick]),
                                    "scalar_usd": (None if single is None
                                                   else float(single.cert_close_usd)),
                                    "batched_wall": bool(wall[pick]),
                                    "scalar_wall": (None if single is None
                                                    else bool(single.wall_hit)),
                                    "batched_exit_ns": int(stamp[pick]),
                                    "scalar_exit_ns": (None if single is None
                                                       else int(single.exit_ts_ns)),
                                })
                                plane.counters["hand_checks"] += 1
                # Y_close is the cached to-close label, carried unchanged.
                for side in (1, -1):
                    key = (position, side, CLOSE)
                    plane.cert[key] = np.asarray(rec.cert(side), np.float64)
                    plane.wall[key] = np.asarray(rec.wall(side), np.bool_)
                    plane.ok[key] = np.asarray(rec.ok(side), np.bool_)
                    plane.exit_ts[key] = np.asarray(rec.exit_ts(side), np.int64)
                    plane.exit_row[key] = np.full(len(lat), -1, np.int64)
                plane.counters["cells"] += 1
        finally:
            shard.close()
    return plane, hand


def hand_check_verdict(hand: Sequence[Mapping[str, object]]) -> dict[str, object]:
    bad = [row for row in hand
           if row["scalar_usd"] is None
           or abs(float(row["batched_usd"]) - float(row["scalar_usd"])) > 1e-9
           or bool(row["batched_wall"]) != bool(row["scalar_wall"])
           or int(row["batched_exit_ns"]) != int(row["scalar_exit_ns"])]
    return {"rows": len(hand), "mismatches": len(bad),
            "worst_abs_usd": (max(abs(float(r["batched_usd"])
                                      - float(r["scalar_usd"] or 0.0))
                                  for r in hand) if hand else None),
            "ok": bool(hand and not bad),
            "examples": [dict(row) for row in hand[:4]],
            "bad": [dict(row) for row in bad[:4]]}


# --------------------------------------------------------------------------
# The feature plane, with the ONE mutant hook.
# --------------------------------------------------------------------------

RANGE_ATR = FEATURES.index("range_atr")


def features_for_horizon(x: np.ndarray, mid: np.ndarray, atr_mid2: float,
                         bar: int, exit_row_bar: int, mutant: str) -> np.ndarray:
    """Sweep 14's causal vector, or the mutant's post-exit rewrite of it.

    ``range_atr`` is the cell's running mid range SO FAR - the range over bars
    ``[0, bar]``.  ``QRE2_MILL_S16_MUTANT=horizon_reads_past_exit`` recomputes it
    over ``[0, exit_bar]``, i.e. with the rows the fixed hold is about to be paid
    on.  That is the exact leak a horizon study invites, so it is the red case,
    and it runs through this function, which every fitted row goes through.
    """

    if mutant != MUTANT_PAST:
        return x
    out = np.array(x, np.float64, copy=True)
    stop = max(int(bar), int(exit_row_bar))
    if len(mid) and atr_mid2 > 0.0 and stop >= 0:
        window = np.asarray(mid[:min(stop, len(mid) - 1) + 1], np.float64)
        out[RANGE_ATR] = float(window.max() - window.min()) / float(atr_mid2)
    return out


# --------------------------------------------------------------------------
# Ridge, one gram per fold, many targets.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class FoldFit:
    mean: np.ndarray
    sd: np.ndarray
    lhs: np.ndarray
    n: int

    def solve(self, x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float]:
        z = (x - self.mean) / self.sd
        rhs = z.T @ (y - y.mean())
        beta = np.linalg.solve(self.lhs, rhs)
        return beta, float(y.mean())


def fold_fit(x: np.ndarray, lam: float = RIDGE_LAMBDA) -> FoldFit:
    """Sweep 14's standardiser and penalty, factored once per fold."""

    mean = x.mean(axis=0)
    sd = np.sqrt(np.maximum(x.var(axis=0), 0.0))
    sd[sd <= 1e-12] = 1.0
    z = (x - mean) / sd
    lhs = z.T @ z + lam * np.eye(x.shape[1])
    return FoldFit(mean=mean, sd=sd, lhs=lhs, n=int(x.shape[0]))


def predict(fit: FoldFit, beta: np.ndarray, intercept: float,
            x: np.ndarray) -> np.ndarray:
    return intercept + ((x - fit.mean) / fit.sd) @ beta


def r2(actual: np.ndarray, fitted: np.ndarray) -> float | None:
    y = np.asarray(actual, np.float64)
    if len(y) < 2:
        return None
    sst = float(((y - y.mean()) ** 2).sum())
    if sst <= 0.0:
        return None
    sse = float(((y - np.asarray(fitted, np.float64)) ** 2).sum())
    return 1.0 - sse / sst


# --------------------------------------------------------------------------
# The occurrence stream, carrying every horizon label.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Row:
    """One occurrence with its feature vector and every horizon's payoff."""

    asset: str
    d8: int
    phase: str
    cell: int
    side: int
    bar: int
    k: int
    ord_side: int
    x: np.ndarray
    y: dict[str, float]


ORD_SIDE = FEATURES.index("ord_side")


def build_rows(streams: Sequence[S14.Stream], plane: HorizonPlane,
               cells: Sequence[S8.Cell8], mutant: str
               ) -> tuple[list[Row], dict[str, int]]:
    by_position = {cell.position: cell for cell in cells}
    counters = {"rows": 0, "dropped_label_invalid": 0, "leak_rewritten": 0}
    out: list[Row] = []
    for stream in streams:
        cell8 = by_position[stream.cell]
        mid = plane.mid.get(stream.cell)
        for occ in stream.occs:
            keys = {label: (stream.cell, occ.side, label) for label in LABELS}
            if any(key not in plane.ok for key in keys.values()):
                counters["dropped_label_invalid"] += 1
                continue
            if not all(bool(plane.ok[key][occ.bar]) for key in keys.values()):
                counters["dropped_label_invalid"] += 1
                continue
            exit_row = int(plane.exit_row[keys[str(HORIZONS[-1])]][occ.bar])
            # The exit ROW indexes the tick index, not the 60 s lattice, so the
            # leak is expressed on the lattice: the bar the longest hold ends on.
            exit_bar = occ.bar
            if exit_row >= 0:
                stamp = int(plane.exit_ts[keys[str(HORIZONS[-1])]][occ.bar])
                exit_bar = int(np.searchsorted(
                    np.asarray(cell8.rec.lat, np.int64), stamp, side="right")) - 1
            x = features_for_horizon(occ.x, mid if mid is not None
                                     else np.zeros(0), cell8.atr_mid2, occ.bar,
                                     exit_bar, mutant)
            if mutant == MUTANT_PAST:
                counters["leak_rewritten"] += 1
            out.append(Row(
                asset=stream.asset, d8=stream.d8, phase=stream.phase,
                cell=stream.cell, side=occ.side, bar=occ.bar, k=occ.k,
                ord_side=int(round(float(occ.x[ORD_SIDE]))), x=x,
                y={label: float(plane.cert[keys[label]][occ.bar])
                   for label in LABELS}))
            counters["rows"] += 1
    return out, counters


# --------------------------------------------------------------------------
# M1: out-of-fold R2 under sweep 14's fold law.
# --------------------------------------------------------------------------

TARGETS = ("level", "sign", "abs")


def _target(values: np.ndarray, kind: str) -> np.ndarray:
    if kind == "sign":
        return np.sign(values)
    if kind == "abs":
        return np.abs(values)
    return values


def m1_predictability(rows: Sequence[Row], explore_days: Mapping[str, list[int]]
                      ) -> dict[str, object]:
    """Walk-forward out-of-fold R2, one gram per fold, every label and target."""

    by_asset: dict[str, dict[int, list[Row]]] = {}
    for row in rows:
        by_asset.setdefault(row.asset, {}).setdefault(row.d8, []).append(row)
    report: dict[str, object] = {}
    oof_pred: dict[tuple[str, str], list[float]] = {}
    oof_true: dict[tuple[str, str], list[float]] = {}
    oof_abs: dict[tuple[str, str], list[float]] = {}
    for asset in ASSETS:
        days = sorted(int(day) for day in explore_days[asset])
        table = by_asset.get(asset, {})
        held: dict[tuple[str, str], list[np.ndarray]] = {}
        truth: dict[tuple[str, str], list[np.ndarray]] = {}
        scored_days = 0
        train_rows_last = 0
        for index, d8 in enumerate(days):
            today = table.get(d8, [])
            if index < MIN_PRIOR_DAYS_FIT or not today:
                continue
            train = [row for day in S14.fold_days(days, index, "")
                     for row in table.get(day, [])]
            if len(train) < MIN_FIT_ROWS:
                continue
            scored_days += 1
            train_rows_last = len(train)
            xt = np.vstack([row.x for row in train])
            xs = np.vstack([row.x for row in today])
            means = np.where(np.isfinite(xt), xt, np.nan)
            with np.errstate(invalid="ignore"):
                impute = np.nanmean(means, axis=0)
            impute = np.where(np.isfinite(impute), impute, 0.0)
            xt = S14._impute(xt, impute)
            xs = S14._impute(xs, impute)
            fit = fold_fit(xt)
            for label in LABELS:
                yt_raw = np.asarray([row.y[label] for row in train], np.float64)
                ys_raw = np.asarray([row.y[label] for row in today], np.float64)
                for kind in TARGETS:
                    yt = _target(yt_raw, kind)
                    ys = _target(ys_raw, kind)
                    beta, intercept = fit.solve(xt, yt)
                    key = (label, kind)
                    held.setdefault(key, []).append(predict(fit, beta,
                                                            intercept, xs))
                    truth.setdefault(key, []).append(ys)
        block: dict[str, object] = {"scoring_days": scored_days,
                                    "last_train_rows": train_rows_last}
        for label in LABELS:
            for kind in TARGETS:
                key = (label, kind)
                if key not in truth:
                    block[f"{label}/{kind}"] = {"n": 0, "r2": None,
                                                "mean": None, "sd": None}
                    continue
                actual = np.concatenate(truth[key])
                fitted = np.concatenate(held[key])
                block[f"{label}/{kind}"] = {
                    "n": int(len(actual)), "r2": r2(actual, fitted),
                    "mean": float(actual.mean()),
                    "sd": float(actual.std()),
                    "pred_sd": float(fitted.std())}
                if kind == "level":
                    oof_pred[(asset, label)] = list(fitted)
                    oof_true[(asset, label)] = list(actual)
                if kind == "abs":
                    # The magnitude channel's predictions, kept so M4 can rank
                    # by predicted |Y_h| as well as by predicted Y_h.  The two
                    # channels score the same held-out rows in the same fold
                    # order, so the arrays are row-aligned by construction.
                    oof_abs[(asset, label)] = list(fitted)
        report[asset] = block
    report["_oof"] = {f"{asset}|{label}": {
        "pred": oof_pred[(asset, label)], "true": oof_true[(asset, label)],
        "pred_abs": oof_abs.get((asset, label), [])}
        for (asset, label) in sorted(oof_pred)}
    return report


# Sweep 15's banked to-close magnitude channel, the sibling result this unit's
# Y_close column must reproduce before any horizon column is believed.
S15_CLOSE_ABS_R2 = {"HG": 0.119, "NKD": 0.127, "SI": 0.096}
S15_R2_TOL = 0.001                   # the sibling quotes R2 to three decimals


def sweep15_crosscheck(m1: Mapping[str, object]) -> dict[str, object]:
    live = {asset: m1[asset]["close/abs"]["r2"] for asset in ASSETS}
    worst = 0.0
    for asset in ASSETS:
        if live[asset] is None:
            worst = float("inf")
        else:
            worst = max(worst, abs(float(live[asset]) - S15_CLOSE_ABS_R2[asset]))
    return {"banked_close_abs_r2": dict(S15_CLOSE_ABS_R2),
            "live_close_abs_r2": {a: live[a] for a in ASSETS},
            "tolerance": S15_R2_TOL, "worst_abs_gap": worst,
            "matches": bool(worst <= S15_R2_TOL)}


# --------------------------------------------------------------------------
# M2: sweep 13's FIRST and SECOND, priced under every horizon.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Priced:
    asset: str
    d8: int
    cell: int
    bar: int
    side: int
    y: dict[str, float]


def price_entries(entries: Sequence[S1.Entry], plane: HorizonPlane
                  ) -> tuple[list[Priced], int]:
    out: list[Priced] = []
    dropped = 0
    for row in entries:
        keys = {label: (row.cell, row.side, label) for label in LABELS}
        if not all(key in plane.ok and bool(plane.ok[key][row.bar])
                   for key in keys.values()):
            dropped += 1
            continue
        out.append(Priced(asset=row.asset, d8=row.d8, cell=row.cell,
                          bar=row.bar, side=row.side,
                          y={label: float(plane.cert[keys[label]][row.bar])
                             for label in LABELS}))
    return out, dropped


def day_sums(rows: Sequence[Priced], asset: str, label: str
             ) -> dict[int, float]:
    out: dict[int, float] = {}
    for row in rows:
        if row.asset != asset:
            continue
        out[row.d8] = out.get(row.d8, 0.0) + row.y[label]
    return out


def m2_mechanism(first: Sequence[Priced], second: Sequence[Priced],
                 explore_days: Mapping[str, list[int]]) -> dict[str, object]:
    """Paired asset-day SECOND minus FIRST under each label, sign-flip null."""

    rng = np.random.default_rng(SEED)
    diffs: dict[tuple[str, str], np.ndarray] = {}
    lines: dict[str, object] = {}
    for asset in ASSETS:
        for label in LABELS:
            a = day_sums(first, asset, label)
            b = day_sums(second, asset, label)
            days = sorted(set(a) | set(b))
            delta = np.asarray([b.get(day, 0.0) - a.get(day, 0.0)
                                for day in days], np.float64)
            diffs[(asset, label)] = delta
            lines[f"{asset}/{label}"] = {
                "asset": asset, "label": label, "blocks": int(len(delta)),
                "first_usd_per_day": (float(np.mean([a.get(d, 0.0)
                                                     for d in days]))
                                      if days else None),
                "second_usd_per_day": (float(np.mean([b.get(d, 0.0)
                                                      for d in days]))
                                       if days else None),
                "delta_usd_per_day": (float(delta.mean()) if len(delta)
                                      else None),
                "delta_total_usd": float(delta.sum()) if len(delta) else 0.0,
            }
    pool = [(asset, label) for asset in ASSETS for label in LABELS]
    lengths = {key: len(diffs[key]) for key in pool}
    observed = {key: (float(diffs[key].mean()) if lengths[key] else 0.0)
                for key in pool}
    draws = np.zeros((SIGN_FLIPS, len(pool)), np.float64)
    for column, key in enumerate(pool):
        delta = diffs[key]
        if not len(delta):
            continue
        signs = rng.choice(np.asarray([-1.0, 1.0]),
                           size=(SIGN_FLIPS, len(delta)))
        draws[:, column] = (signs * delta).mean(axis=1)
    maxima = draws.max(axis=1)
    for column, key in enumerate(pool):
        name = f"{key[0]}/{key[1]}"
        stat = observed[key]
        raw = float(np.mean(draws[:, column] >= stat)) if lengths[key] else None
        adjusted = float(np.mean(maxima >= stat)) if lengths[key] else None
        lo = _q(draws[:, column], 2.5)
        hi = _q(draws[:, column], 97.5)
        boot = None
        if lengths[key] > 1:
            delta = diffs[key]
            idx = rng.integers(0, len(delta), size=(2000, len(delta)))
            means = delta[idx].mean(axis=1)
            boot = [float(np.percentile(means, 2.5)),
                    float(np.percentile(means, 97.5))]
        lines[name].update({"p_one_sided": raw, "p_max_adjusted": adjusted,
                            "null_ci95": [lo, hi], "block_ci95": boot})
    return {"draws": SIGN_FLIPS, "pool": [f"{a}/{b}" for a, b in pool],
            "by_line": lines}


# --------------------------------------------------------------------------
# M3: the noise ceiling under Y_h.
# --------------------------------------------------------------------------

def m3_ceiling(rows: Sequence[Row], label: str, coarse: bool) -> dict[str, object]:
    """Real per-cell-max oracle against cross-cell within-stratum shuffles."""

    strata: dict[tuple[str, str], dict[int, list[float]]] = {}
    for row in rows:
        if coarse and row.ord_side != 1:
            continue
        strata.setdefault((row.asset, row.phase), {}).setdefault(
            row.cell, []).append(row.y[label])
    rng = np.random.default_rng(SEED + (1 if coarse else 0))
    per_asset: dict[str, object] = {}
    for asset in ASSETS:
        keys = [key for key in sorted(strata) if key[0] == asset]
        real: list[float] = []
        pool_all: list[np.ndarray] = []
        sizes_all: list[np.ndarray] = []
        for key in keys:
            cells = strata[key]
            sizes = np.asarray([len(v) for v in cells.values()], np.int64)
            pool = np.concatenate([np.asarray(v, np.float64)
                                   for v in cells.values()])
            real.extend(float(np.max(v)) for v in cells.values())
            pool_all.append(pool)
            sizes_all.append(sizes)
        if not real:
            per_asset[asset] = {"cells": 0}
            continue
        observed = float(np.mean(real))
        shuffled = np.zeros(SHUFFLE_DRAWS, np.float64)
        for draw in range(SHUFFLE_DRAWS):
            maxima: list[float] = []
            for pool, sizes in zip(pool_all, sizes_all):
                order = rng.permutation(len(pool))
                cut = np.cumsum(sizes)[:-1]
                for chunk in np.split(pool[order], cut):
                    maxima.append(float(chunk.max()))
            shuffled[draw] = float(np.mean(maxima))
        excess = observed - float(shuffled.mean())
        p05 = float(np.percentile(shuffled, 5.0))
        p95 = float(np.percentile(shuffled, 95.0))
        # Three outcomes, not two.  ABOVE-P95 is the pre-registered structure
        # finding.  BELOW-P5 is its own finding and is NOT "no structure": it
        # says the big outcomes CLUSTER inside cells, so scattering them across
        # cells raises the per-cell-max ceiling.  WITHIN-BAND is the null.  The
        # sibling sweep 15 found BELOW-P5 on the to-close label at both grains,
        # so the band is reported rather than collapsed into the letter.
        band = ("ABOVE-P95" if observed > p95
                else "BELOW-P5" if observed < p05 else "WITHIN-BAND")
        per_asset[asset] = {
            "cells": len(real), "occurrences": int(sum(len(p) for p in pool_all)),
            "real_oracle_mean_usd": observed,
            "shuffled_mean_usd": float(shuffled.mean()),
            "shuffled_p05_usd": p05,
            "shuffled_p95_usd": p95,
            "shuffled_sd_usd": float(shuffled.std()),
            "structure_excess_usd": excess,
            "percentile": float(np.mean(shuffled < observed)),
            "above_p95": bool(observed > p95),
            "below_p5": bool(observed < p05),
            "band": band,
        }
    return per_asset


# --------------------------------------------------------------------------
# M4: the rung arithmetic under sequential capacity.
# --------------------------------------------------------------------------

def candidate_wait_median(rows: Sequence[Row], records: Sequence[S1.CellRec]
                          ) -> dict[str, float]:
    """Median in-cell inter-occurrence gap in seconds, per asset."""

    gaps: dict[str, list[float]] = {asset: [] for asset in ASSETS}
    by_cell: dict[int, list[int]] = {}
    for row in rows:
        by_cell.setdefault(row.cell, []).append(row.bar)
    for cell, bars in by_cell.items():
        asset = records[cell].asset
        ordered = sorted(bars)
        gaps[asset].extend(float((b - a) * BAR_SECONDS)
                           for a, b in zip(ordered, ordered[1:]))
    return {asset: (float(np.median(value)) if value else 0.0)
            for asset, value in gaps.items()}


def m4_capacity(rows: Sequence[Row], records: Sequence[S1.CellRec],
                m1: Mapping[str, object]) -> dict[str, object]:
    waits = candidate_wait_median(rows, records)
    spans: dict[tuple[str, int], list[float]] = {}
    for rec in records:
        span = float(int(rec.phase_close_ts_ns) - int(rec.phase_open_ts_ns)) / NANOS
        spans.setdefault((rec.asset, rec.d8), []).append(span)
    per_asset_cap = PORTFOLIO_CAP / float(len(ASSETS))
    out: dict[str, object] = {"candidate_wait_median_s": waits,
                              "portfolio_cap": PORTFOLIO_CAP,
                              "per_asset_day_cap": per_asset_cap}
    for asset in ASSETS:
        wait = float(waits.get(asset, 0.0))
        days = [key for key in spans if key[0] == asset]
        block: dict[str, object] = {}
        for h in HORIZONS:
            label = str(int(h))
            seats = []
            for key in days:
                total = 0
                for span in spans[key]:
                    if span <= 0:
                        continue
                    total += int(math.floor((span + wait) / (float(h) + wait)))
                seats.append(float(total))
            raw = float(np.mean(seats)) if seats else 0.0
            capped = min(raw, per_asset_cap)
            oof = m1["_oof"].get(f"{asset}|{label}")
            top_mean = None
            top_n = 0
            magnitude: dict[str, object] = {"mean_y_usd": None,
                                            "mean_abs_y_usd": None,
                                            "win_rate": None, "n": 0}
            if oof and len(oof["pred"]):
                pred = np.asarray(oof["pred"], np.float64)
                true = np.asarray(oof["true"], np.float64)
                cut = float(np.percentile(pred, 100.0 * (1.0 - TOP_DECILE)))
                mask = pred >= cut
                if mask.any():
                    top_mean = float(true[mask].mean())
                    top_n = int(mask.sum())
                # The second, out-of-fold selector: rank by PREDICTED |Y_h| from
                # the magnitude channel's own fold fits.  Sweep 15 found the
                # magnitude channel is the one that predicts on the to-close
                # label, so a selector built on it is the fair test of whether
                # magnitude skill converts into a signed edge at a fixed hold.
                pred_abs = np.asarray(oof.get("pred_abs") or [], np.float64)
                if len(pred_abs) == len(true) and len(pred_abs):
                    cut_abs = float(np.percentile(
                        pred_abs, 100.0 * (1.0 - TOP_DECILE)))
                    pick = pred_abs >= cut_abs
                    if pick.any():
                        magnitude = {
                            "mean_y_usd": float(true[pick].mean()),
                            "mean_abs_y_usd": float(np.abs(true[pick]).mean()),
                            "win_rate": float((true[pick] > 0.0).mean()),
                            "n": int(pick.sum())}
            required = {f"cov{cov}": (DAY_RUNG_USD[asset] / (capped * cov)
                                      if capped * cov > 0 else None)
                        for cov in COVERAGES}
            ratios = {name: ((value / top_mean)
                             if (value is not None and top_mean
                                 and top_mean > 0) else None)
                      for name, value in required.items()}
            block[label] = {
                "capacity_raw": raw, "capacity_capped": capped,
                "rung_usd": DAY_RUNG_USD[asset],
                "required_per_trade_usd": required,
                "top_decile_mean_usd": top_mean, "top_decile_n": top_n,
                "magnitude_selector": magnitude,
                "required_over_observed": ratios,
                "within_2x_at_cov06": bool(
                    ratios.get("cov0.6") is not None
                    and 0 < ratios["cov0.6"] <= ARITHMETIC_FACTOR),
            }
        out[asset] = block
    return out


# --------------------------------------------------------------------------
# M5: MDD shape.
# --------------------------------------------------------------------------

def m5_mdd(second: Sequence[Priced]) -> dict[str, object]:
    from engine.entry_v2.replay import _drawdown
    out: dict[str, object] = {}
    for asset in ASSETS:
        block: dict[str, object] = {}
        for label in LABELS:
            sums = day_sums(second, asset, label)
            ordered = [sums[day] for day in sorted(sums)]
            block[label] = {
                "days": len(ordered),
                "mdd_day_usd": float(_drawdown(ordered)) if ordered else 0.0,
                "total_usd": float(sum(ordered)),
            }
        base = float(block[CLOSE]["mdd_day_usd"])
        for label in LABELS:
            block[label]["mdd_vs_close"] = (
                float(block[label]["mdd_day_usd"]) / base if base > 0 else None)
        out[asset] = block
    return out


# --------------------------------------------------------------------------
# The pre-registered decision table.
# --------------------------------------------------------------------------

def decide(m1: Mapping[str, object], m2: Mapping[str, object],
           m3: Mapping[str, object], m4: Mapping[str, object]
           ) -> dict[str, object]:
    by_asset: dict[str, object] = {}
    for asset in ASSETS:
        rows: dict[str, object] = {}
        for h in HORIZONS:
            label = str(int(h))
            r2_level = m1[asset][f"{label}/level"]["r2"]
            line = m2["by_line"][f"{asset}/{label}"]
            delta = line["delta_usd_per_day"]
            p_adj = line["p_max_adjusted"]
            fine = m3["fine"][label][asset]
            coarse = m3["coarse"][label][asset]
            arithmetic = m4[asset][label]
            predictable = bool(r2_level is not None and r2_level >= R2_FLOOR)
            cash = bool(delta is not None and delta > 0.0
                        and p_adj is not None and p_adj <= P_CEILING)
            structure = bool(fine.get("above_p95") or coarse.get("above_p95"))
            arith = bool(arithmetic["within_2x_at_cov06"])
            rows[label] = {
                "r2_level": r2_level, "r2_close": m1[asset]["close/level"]["r2"],
                "r2_sign": m1[asset][f"{label}/sign"]["r2"],
                "r2_abs": m1[asset][f"{label}/abs"]["r2"],
                "delta_usd_per_day": delta, "p_max_adjusted": p_adj,
                "structure_excess_fine": fine.get("structure_excess_usd"),
                "structure_excess_coarse": coarse.get("structure_excess_usd"),
                "band_fine": fine.get("band"), "band_coarse": coarse.get("band"),
                "predictable": predictable, "cash": cash,
                "structure": structure, "arithmetic": arith,
                "viable": bool((predictable or cash) and structure and arith),
                "label_only": bool((predictable or cash) and not (structure
                                                                  and arith)),
            }
        by_asset[asset] = rows
    viable = [(a, h) for a in DECIDING for h in map(str, HORIZONS)
              if by_asset[a][h]["viable"]]
    label_only = [(a, h) for a in DECIDING for h in map(str, HORIZONS)
                  if by_asset[a][h]["label_only"]]
    moved = [(a, h) for a in DECIDING for h in map(str, HORIZONS)
             if by_asset[a][h]["predictable"] or by_asset[a][h]["cash"]
             or by_asset[a][h]["structure"]]
    if viable:
        verdict = "HORIZON-VIABLE"
    elif label_only or moved:
        verdict = "LABEL-ONLY"
    else:
        verdict = "DEAD"
    # The M3 band is reported as its own row.  DEAD by elimination would read as
    # "no structure was found"; BELOW-P5 is a different, positive statement -
    # the real per-cell-max oracle sits UNDER the cross-cell shuffle, i.e. the
    # big outcomes cluster inside cells.  The registered letter above is not
    # allowed to absorb it, so it is counted and named separately.
    bands: dict[str, int] = {}
    for asset in ASSETS:
        for h in map(str, HORIZONS):
            for grain in ("band_fine", "band_coarse"):
                name = by_asset[asset][h][grain] or "UNSCORED"
                bands[name] = bands.get(name, 0) + 1
    below = [f"{a}/{h}/{g[5:]}" for a in ASSETS for h in map(str, HORIZONS)
             for g in ("band_fine", "band_coarse")
             if by_asset[a][h][g] == "BELOW-P5"]
    return {"verdict": verdict,
            "viable": [f"{a}/{h}" for a, h in viable],
            "label_only": [f"{a}/{h}" for a, h in label_only],
            "moved_anything": [f"{a}/{h}" for a, h in moved],
            "m3_band_counts": bands,
            "m3_below_p5_lines": below,
            "by_asset": by_asset}


# --------------------------------------------------------------------------
# Printing.
# --------------------------------------------------------------------------

def _n(value: object, width: int = 9, digits: int = 3) -> str:
    if value is None:
        return "-".rjust(width)
    if isinstance(value, bool):
        return ("yes" if value else "no").rjust(width)
    if isinstance(value, (int, np.integer)):
        return str(int(value)).rjust(width)
    return f"{float(value):.{digits}f}".rjust(width)


def print_gate(block: Mapping[str, object], hand: Mapping[str, object],
               counters: Mapping[str, int], plane: Mapping[str, int]) -> None:
    print("\nSWEEP-14 / SWEEP-9 STREAM GATE")
    print(f"  rows            banked {block['banked_rows']}  "
          f"live {block['live_rows']}")
    for asset in ASSETS:
        print(f"  certifiable {asset:<4}banked {block['banked_certifiable'][asset]:>6}"
              f"  live {block['live_certifiable'][asset]:>6}")
    for name in sorted(REPRO_COUNTERS):
        print(f"  {name:<22}banked {block['banked_counters'][name]:>7}"
              f"  live {block['live_counters'][name]:>7}")
    print(f"  matches: {block['matches']}")
    print("\nHORIZON LABEL PLANE")
    print(f"  cells {plane['cells']}  grid calls {plane['grid_calls']}  "
          f"missing shard cells {plane['cells_missing_shard_cell']}")
    print(f"  hand checks {hand['rows']} rows, {hand['mismatches']} mismatches, "
          f"worst |batched-scalar| {hand['worst_abs_usd']}")
    print(f"  occurrence rows kept {counters['rows']}, dropped for an invalid "
          f"label {counters['dropped_label_invalid']}")


def print_m1(m1: Mapping[str, object]) -> None:
    print("\nM1 PREDICTABILITY - out-of-fold R2 on the frozen 16-feature plane")
    print("  " + "asset".ljust(7) + "label".rjust(8) + "n".rjust(9)
          + "R2_level".rjust(10) + "R2_sign".rjust(10) + "R2_abs".rjust(10)
          + "mean_usd".rjust(11) + "sd_usd".rjust(10) + "pred_sd".rjust(10))
    for asset in ASSETS:
        for label in LABELS:
            row = m1[asset][f"{label}/level"]
            print("  " + asset.ljust(7) + label.rjust(8) + _n(row["n"], 9)
                  + _n(row["r2"], 10, 5)
                  + _n(m1[asset][f"{label}/sign"]["r2"], 10, 5)
                  + _n(m1[asset][f"{label}/abs"]["r2"], 10, 5)
                  + _n(row["mean"], 11, 2) + _n(row["sd"], 10, 2)
                  + _n(row["pred_sd"], 10, 3))
        print(f"  {asset} scoring days {m1[asset]['scoring_days']}, "
              f"last fold train rows {m1[asset]['last_train_rows']}")
    print("\n  SIGN vs MAGNITUDE, the two channels side by side per horizon")
    print("  " + "label".ljust(8) + "".join(f"{a}_sign".rjust(11) for a in ASSETS)
          + "".join(f"{a}_abs".rjust(11) for a in ASSETS))
    for label in LABELS:
        print("  " + label.ljust(8)
              + "".join(_n(m1[a][f"{label}/sign"]["r2"], 11, 5) for a in ASSETS)
              + "".join(_n(m1[a][f"{label}/abs"]["r2"], 11, 5) for a in ASSETS))


def print_crosscheck(block: Mapping[str, object]) -> None:
    print("\n  SWEEP-15 CROSS-CHECK on the shared to-close magnitude channel")
    print("  " + "asset".ljust(8) + "banked".rjust(10) + "live".rjust(11)
          + "gap".rjust(11))
    for asset in ASSETS:
        print("  " + asset.ljust(8)
              + _n(block["banked_close_abs_r2"][asset], 10, 3)
              + _n(block["live_close_abs_r2"][asset], 11, 5)
              + _n(abs(float(block["live_close_abs_r2"][asset])
                       - float(block["banked_close_abs_r2"][asset])), 11, 5))
    print(f"  worst gap {block['worst_abs_gap']:.5f} vs tolerance "
          f"{block['tolerance']}; matches: {block['matches']}")


def print_m2(m2: Mapping[str, object], entries: Mapping[str, object]) -> None:
    print("\nM2 ORDINAL MECHANISM CASH - sweep 13 FIRST vs SECOND under each label")
    print(f"  entries: FIRST {entries['first']} (dropped {entries['first_dropped']}), "
          f"SECOND {entries['second']} (dropped {entries['second_dropped']})")
    print("  " + "asset".ljust(7) + "label".rjust(8) + "blocks".rjust(8)
          + "FIRST$/d".rjust(11) + "SECOND$/d".rjust(11) + "delta$/d".rjust(11)
          + "block_lo".rjust(11) + "block_hi".rjust(11) + "p_one".rjust(9)
          + "p_adj".rjust(9))
    for asset in ASSETS:
        for label in LABELS:
            row = m2["by_line"][f"{asset}/{label}"]
            ci = row.get("block_ci95") or [None, None]
            print("  " + asset.ljust(7) + label.rjust(8) + _n(row["blocks"], 8)
                  + _n(row["first_usd_per_day"], 11, 1)
                  + _n(row["second_usd_per_day"], 11, 1)
                  + _n(row["delta_usd_per_day"], 11, 1)
                  + _n(ci[0], 11, 1) + _n(ci[1], 11, 1)
                  + _n(row["p_one_sided"], 9, 4)
                  + _n(row["p_max_adjusted"], 9, 4))


def print_m3(m3: Mapping[str, object]) -> None:
    print("\nM3 NOISE CEILING UNDER Y_h - per-cell-max oracle vs shuffled ceilings")
    for grain in ("fine", "coarse"):
        print(f"  grain = {grain}"
              + ("  (every occurrence)" if grain == "fine"
                 else "  (post-reset first occurrence)"))
        print("    " + "asset".ljust(7) + "label".rjust(8) + "cells".rjust(8)
              + "occs".rjust(8) + "real$".rjust(10) + "shuf$".rjust(10)
              + "shufp05".rjust(10) + "shufp95".rjust(10) + "excess$".rjust(10)
              + "pctile".rjust(9) + "band".rjust(13))
        for asset in ASSETS:
            for label in LABELS:
                row = m3[grain][label][asset]
                if not row.get("cells"):
                    continue
                print("    " + asset.ljust(7) + label.rjust(8)
                      + _n(row["cells"], 8) + _n(row["occurrences"], 8)
                      + _n(row["real_oracle_mean_usd"], 10, 2)
                      + _n(row["shuffled_mean_usd"], 10, 2)
                      + _n(row["shuffled_p05_usd"], 10, 2)
                      + _n(row["shuffled_p95_usd"], 10, 2)
                      + _n(row["structure_excess_usd"], 10, 2)
                      + _n(row["percentile"], 9, 3)
                      + str(row["band"]).rjust(13))
    print("  BANDS: ABOVE-P95 is the pre-registered structure finding; "
          "BELOW-P5 is its own\n"
          "  finding - the real per-cell-max oracle sits UNDER the cross-cell "
          "shuffle, i.e.\n"
          "  the big outcomes CLUSTER inside cells and scattering them raises "
          "the ceiling.")


def print_m4(m4: Mapping[str, object]) -> None:
    print("\nM4 RUNG ARITHMETIC UNDER SEQUENTIAL CAPACITY")
    print("  candidate-wait median s: "
          + "  ".join(f"{a} {m4['candidate_wait_median_s'][a]:.0f}"
                      for a in ASSETS)
          + f"   portfolio cap {m4['portfolio_cap']} "
            f"({m4['per_asset_day_cap']:.1f}/asset-day)")
    print("  " + "asset".ljust(7) + "label".rjust(8) + "cap_raw".rjust(10)
          + "cap_use".rjust(9) + "rung$".rjust(9) + "req@0.4".rjust(10)
          + "req@0.6".rjust(10) + "topdec$".rjust(10) + "topdec_n".rjust(10)
          + "req/obs@.6".rjust(12) + "within2x".rjust(10))
    for asset in ASSETS:
        for h in HORIZONS:
            row = m4[asset][str(h)]
            print("  " + asset.ljust(7) + str(h).rjust(8)
                  + _n(row["capacity_raw"], 10, 2)
                  + _n(row["capacity_capped"], 9, 2)
                  + _n(row["rung_usd"], 9, 0)
                  + _n(row["required_per_trade_usd"]["cov0.4"], 10, 1)
                  + _n(row["required_per_trade_usd"]["cov0.6"], 10, 1)
                  + _n(row["top_decile_mean_usd"], 10, 2)
                  + _n(row["top_decile_n"], 10)
                  + _n(row["required_over_observed"]["cov0.6"], 12, 1)
                  + _n(row["within_2x_at_cov06"], 10))
    print("\n  SECOND SELECTOR, out-of-fold rank by PREDICTED |Y_h| "
          "(the magnitude channel)")
    print("  " + "asset".ljust(7) + "label".rjust(8) + "n".rjust(9)
          + "meanY$".rjust(11) + "mean|Y|$".rjust(11) + "win".rjust(9)
          + "levelY$".rjust(11))
    for asset in ASSETS:
        for h in HORIZONS:
            row = m4[asset][str(h)]
            mag = row["magnitude_selector"]
            print("  " + asset.ljust(7) + str(h).rjust(8) + _n(mag["n"], 9)
                  + _n(mag["mean_y_usd"], 11, 2)
                  + _n(mag["mean_abs_y_usd"], 11, 2)
                  + _n(mag["win_rate"], 9, 3)
                  + _n(row["top_decile_mean_usd"], 11, 2))


def print_m5(m5: Mapping[str, object]) -> None:
    print("\nM5 MDD SHAPE - day-ordered MDD of the SECOND line's day sums")
    print("  " + "asset".ljust(7) + "label".rjust(8) + "days".rjust(7)
          + "total$".rjust(12) + "mdd_day$".rjust(11) + "vs_close".rjust(10))
    for asset in ASSETS:
        for label in LABELS:
            row = m5[asset][label]
            print("  " + asset.ljust(7) + label.rjust(8) + _n(row["days"], 7)
                  + _n(row["total_usd"], 12, 1) + _n(row["mdd_day_usd"], 11, 1)
                  + _n(row["mdd_vs_close"], 10, 3))


def print_decision(block: Mapping[str, object]) -> None:
    print("\nDECISION TABLE (pre-registered)")
    print("  " + "asset".ljust(7) + "dec".rjust(5) + "h".rjust(7)
          + "R2(Y_h)".rjust(10) + "R2sign".rjust(10) + "R2abs".rjust(10)
          + "R2(close)".rjust(11) + "delta$/d".rjust(11)
          + "p_adj".rjust(9) + "exc_fine".rjust(10) + "exc_coarse".rjust(11)
          + "pred".rjust(6) + "cash".rjust(6) + "struct".rjust(8)
          + "arith".rjust(7) + "viable".rjust(8))
    for asset in ASSETS:
        for h in HORIZONS:
            row = block["by_asset"][asset][str(h)]
            print("  " + asset.ljust(7)
                  + ("yes" if asset in DECIDING else "no").rjust(5)
                  + str(h).rjust(7) + _n(row["r2_level"], 10, 5)
                  + _n(row["r2_sign"], 10, 5) + _n(row["r2_abs"], 10, 5)
                  + _n(row["r2_close"], 11, 5)
                  + _n(row["delta_usd_per_day"], 11, 1)
                  + _n(row["p_max_adjusted"], 9, 4)
                  + _n(row["structure_excess_fine"], 10, 2)
                  + _n(row["structure_excess_coarse"], 11, 2)
                  + _n(row["predictable"], 6) + _n(row["cash"], 6)
                  + _n(row["structure"], 8) + _n(row["arithmetic"], 7)
                  + _n(row["viable"], 8))
    print("\n  M3 BAND, reported as its own row and never folded into the letter")
    print("  " + "asset".ljust(7) + "h".rjust(7) + "fine".rjust(14)
          + "coarse".rjust(14))
    for asset in ASSETS:
        for h in HORIZONS:
            row = block["by_asset"][asset][str(h)]
            print("  " + asset.ljust(7) + str(h).rjust(7)
                  + str(row["band_fine"]).rjust(14)
                  + str(row["band_coarse"]).rjust(14))
    print(f"  band counts      : {block['m3_band_counts']}")
    print(f"  BELOW-P5 lines   : {len(block['m3_below_p5_lines'])} of "
          f"{len(ASSETS) * len(HORIZONS) * 2} asset-horizon-grain cells")
    print(f"  viable lines     : {block['viable'] or 'none'}")
    print(f"  label-only lines : {block['label_only'] or 'none'}")
    print(f"  moved anything   : {block['moved_anything'] or 'none'}")
    print(f"  VERDICT: {block['verdict']}  "
          f"(registered letter; the M3 band above is a separate finding)")


# --------------------------------------------------------------------------
# SELFTEST.
# --------------------------------------------------------------------------

def _check(name: str, ok: bool, detail: str = "") -> tuple[str, bool, str]:
    return (name, bool(ok), detail)


def _synthetic_index(mid_path: Sequence[float], asset: str = "HG",
                     step_s: int = 60, spread: int = 0) -> M.MillIndex:
    """A tick index whose mid2 follows ``mid_path`` on a fixed cadence."""

    n = len(mid_path)
    ts = np.arange(1, n + 1, dtype=np.int64) * (step_s * NANOS)
    mid2 = np.asarray([int(round(v)) for v in mid_path], np.int64)
    half = int(spread)
    bid = mid2 // 2 - half
    ask = mid2 // 2 + half
    generation = np.zeros(n, np.uint32)
    return M.MillIndex(asset, ts, mid2, bid, ask, generation, ts, generation)


def _selftest_horizon_law() -> list[tuple[str, bool, str]]:
    """Hand-computed Y_h on a synthetic path: wall, time exit, close truncation."""

    out: list[tuple[str, bool, str]] = []
    asset = "HG"
    factor = 0.5e-9 * float(M.ASSET_MULTIPLIER[asset])
    # A path that dives past the -900 wall at tick 5 and recovers afterwards.
    base = 2_000_000_000
    drop = int(math.ceil((WALL_USD + 5.0) / factor))
    path = [base, base + 10, base - 20, base + 30,
            base - drop, base + 400, base + 900, base + 1500, base + 2000,
            base + 2600, base + 3000, base + 3400]
    index = _synthetic_index(path, asset)
    close_ns = int(index.ts[-1])
    entry_ns = int(index.ts[0])          # entry quote = row 0, window from row 1
    quote = index.current(entry_ns + 1)
    cost = M.frozen_cost_usd(quote[0], quote[1], asset)
    entry_mid2 = quote[2]

    def y(h_s: int) -> tuple[float, bool, int]:
        stop = min(entry_ns + 1 + h_s * NANOS, close_ns)
        grid = outcomes_grid_capped(
            index, np.asarray([entry_ns + 1], np.int64), 1,
            np.asarray([stop], np.int64),
            entry_mid2=np.asarray([entry_mid2], np.int64),
            cost_usd=np.asarray([cost], np.float64))
        return (float(grid["cert_close_usd"][0]), bool(grid["wall_hit"][0]),
                int(grid["exit_ts_ns"][0]))

    # 1. WALL INSIDE THE WINDOW: a 600 s hold reaches tick 5, past the wall.
    cert, wall, stamp = y(600)
    hand_wall = (path[4] - entry_mid2) * factor - cost
    out.append(_check(
        "horizon/wall inside the window exits at the wall",
        wall and abs(cert - hand_wall) < 1e-9 and stamp == int(index.ts[4]),
        f"cert {cert:.4f} vs hand {hand_wall:.4f}, exit tick "
        f"{stamp // (60 * NANOS)}"))
    # 2. TIME EXIT: a 180 s hold stops before the wall, on the last row inside.
    cert, wall, stamp = y(180)
    hand_time = (path[3] - entry_mid2) * factor - cost
    out.append(_check(
        "horizon/time exit takes the last row at or before entry+h",
        (not wall) and abs(cert - hand_time) < 1e-9 and stamp == int(index.ts[3]),
        f"cert {cert:.4f} vs hand {hand_time:.4f}, exit tick "
        f"{stamp // (60 * NANOS)}"))
    # 3. PHASE-CLOSE TRUNCATION: a 7200 s hold runs past the close and is cut.
    #    Path 2 has no wall at all, so the close is the binding exit.
    calm = [base + 10 * i for i in range(12)]
    index2 = _synthetic_index(calm, asset)
    quote2 = index2.current(int(index2.ts[0]) + 1)
    cost2 = M.frozen_cost_usd(quote2[0], quote2[1], asset)
    close2 = int(index2.ts[7])
    grid = outcomes_grid_capped(
        index2, np.asarray([int(index2.ts[0]) + 1], np.int64), 1,
        np.asarray([min(int(index2.ts[0]) + 1 + 7200 * NANOS, close2)], np.int64),
        entry_mid2=np.asarray([quote2[2]], np.int64),
        cost_usd=np.asarray([cost2], np.float64))
    hand_close = (calm[7] - quote2[2]) * factor - cost2
    out.append(_check(
        "horizon/a hold past the phase close truncates at the close",
        abs(float(grid["cert_close_usd"][0]) - hand_close) < 1e-9
        and int(grid["exit_ts_ns"][0]) == close2,
        f"cert {float(grid['cert_close_usd'][0]):.4f} vs hand {hand_close:.4f}"))
    # 4. The horizon is a real constraint: a shorter hold cannot see further.
    long_cert, _w, long_stamp = y(7200)
    short_cert, _w2, short_stamp = y(120)
    out.append(_check(
        "horizon/a shorter hold never exits later than a longer one",
        short_stamp <= long_stamp,
        f"h=120 exits {short_stamp // (60 * NANOS)}, h=7200 exits "
        f"{long_stamp // (60 * NANOS)}"))
    return out


def _selftest_batching() -> list[tuple[str, bool, str]]:
    """The per-entry close batching against the frozen scalar outcome()."""

    asset = "HG"
    rng = np.random.default_rng(11)
    base = 2_000_000_000
    steps = rng.integers(-800, 800, size=400).astype(np.int64)
    path = base + np.cumsum(steps)
    index = _synthetic_index(path, asset)
    close_ns = int(index.ts[-1])
    stamps = np.asarray(index.ts[:200], np.int64) + 1
    out: list[tuple[str, bool, str]] = []
    for side in (1, -1):
        for h in HORIZONS:
            closes = np.minimum(stamps + h * NANOS, close_ns)
            quote_at = index.positions(stamps)
            mids = index.mid2[np.maximum(quote_at, 0)]
            costs = ((index.ask[np.maximum(quote_at, 0)]
                      - index.bid[np.maximum(quote_at, 0)])
                     * index.multiplier / 1e9 + FEE_USD)
            grid = outcomes_grid_capped(index, stamps, side, closes,
                                        entry_mid2=mids, cost_usd=costs)
            worst = 0.0
            mismatched = 0
            for slot, position in enumerate(grid["input_index"]):
                single = index.outcome(
                    int(stamps[position]), side, int(mids[position]),
                    float(costs[position]), int(closes[position]))
                if single is None:
                    mismatched += 1
                    continue
                worst = max(worst, abs(float(single.cert_close_usd)
                                       - float(grid["cert_close_usd"][slot])))
                if (bool(single.wall_hit) != bool(grid["wall_hit"][slot])
                        or int(single.exit_ts_ns)
                        != int(grid["exit_ts_ns"][slot])):
                    mismatched += 1
            out.append(_check(
                f"batching/side {side:+d} h={h} matches the scalar law",
                mismatched == 0 and worst < 1e-9,
                f"{len(grid['input_index'])} rows, worst |d| {worst:.2e}, "
                f"{mismatched} mismatched"))
    return out


def _planted_rows(days: int = 60, cells_per_day: int = 5, per_cell: int = 6,
                  seed: int = SEED, mutant: str = "") -> list[Row]:
    """Cells where ONLY the 1800 s label is a function of an observed feature.

    ``depth_atr`` drives Y_1800 and nothing else; Y_close is an independent
    draw.  M1 must recover the first and must not manufacture the second.  The
    cell's mid path is built so that the range through the HORIZON EXIT bar
    carries the same signal - that is the row the leak mutant reads, so the
    mutant makes an unpredictable-by-causal-features label predictable.
    """

    rng = np.random.default_rng(seed)
    rows: list[Row] = []
    position = 0
    for day in range(days):
        for _ in range(cells_per_day):
            for index in range(per_cell):
                signal = float(rng.normal())
                x = np.zeros(NFEAT, np.float64)
                x[FEATURES.index("ord_side")] = float(index + 1)
                x[FEATURES.index("ord_cell")] = float(index + 1)
                x[FEATURES.index("depth_atr")] = signal
                x[FEATURES.index("remain_frac")] = 1.0 - index / (2.0 * per_cell)
                x[FEATURES.index("side")] = 1.0
                y_h = 40.0 * signal + 8.0 * float(rng.normal())
                # A second, post-exit-only signal: nothing causal sees it.
                hidden = float(rng.normal())
                y_close = 30.0 * hidden + 20.0 * float(rng.normal())
                if mutant == MUTANT_PAST:
                    # The leak: range_atr recomputed through the exit bar sees
                    # the very move the hold is paid on.
                    x = np.array(x, np.float64, copy=True)
                    x[RANGE_ATR] = hidden
                rows.append(Row(asset="NKD", d8=20220101 + day, phase="0",
                                cell=position, side=1, bar=index + 1,
                                k=index + 1, ord_side=index + 1, x=x,
                                y={"1800": y_h, "3600": y_h, "5400": y_h,
                                   "7200": y_h, CLOSE: y_close}))
            position += 1
    return rows


def _selftest_m1() -> list[tuple[str, bool, str]]:
    mutant = _mutant()
    rows = _planted_rows(mutant=mutant)
    days = {"NKD": sorted({row.d8 for row in rows}), "HG": [], "SI": []}
    m1 = m1_predictability(rows, days)
    r2_h = m1["NKD"]["1800/level"]["r2"]
    r2_c = m1["NKD"]["close/level"]["r2"]
    out = [
        _check("M1/recovers a planted predictable-at-h component",
               r2_h is not None and r2_h >= 0.20,
               f"out-of-fold R2(Y_1800) {r2_h}"),
        _check("M1/does not manufacture predictability in Y_close",
               r2_c is not None and r2_c < 0.05,
               f"out-of-fold R2(Y_close) {r2_c}"),
    ]
    return out


def _selftest_mutant() -> list[tuple[str, bool, str]]:
    """The leak law, asserted through the shipped ``features_for_horizon``."""

    mutant = _mutant()
    out: list[tuple[str, bool, str]] = []
    mid = np.asarray([100.0, 101.0, 99.0, 130.0, 60.0], np.float64)
    x = np.zeros(NFEAT, np.float64)
    x[RANGE_ATR] = (101.0 - 99.0) / 2.0        # the causal range through bar 2
    got = features_for_horizon(x, mid, 2.0, 2, 4, mutant)
    out.append(_check(
        "leak/the feature plane never reads past the horizon exit",
        bool(np.array_equal(got, x)),
        f"range_atr {got[RANGE_ATR]:.3f} vs causal {x[RANGE_ATR]:.3f}"))
    # And the consequence: a label no causal feature can see must stay
    # unpredictable out of fold.
    rows = _planted_rows(days=40, cells_per_day=4, per_cell=5, mutant=mutant)
    days = {"NKD": sorted({row.d8 for row in rows}), "HG": [], "SI": []}
    m1 = m1_predictability(rows, days)
    r2_c = m1["NKD"]["close/level"]["r2"]
    out.append(_check(
        "leak/a post-exit-only label stays unpredictable out of fold",
        r2_c is not None and r2_c < 0.10,
        f"out-of-fold R2(Y_close) {r2_c}"))
    return out


def _selftest_shuffle() -> list[tuple[str, bool, str]]:
    """The M3 shuffle has no structure to find when the cells are exchangeable."""

    rng = np.random.default_rng(3)
    rows: list[Row] = []
    for cell in range(120):
        for index in range(5):
            rows.append(Row(asset="NKD", d8=20220101 + cell // 4, phase="0",
                            cell=cell, side=1, bar=index + 1, k=index + 1,
                            ord_side=index + 1, x=np.zeros(NFEAT),
                            y={label: float(rng.normal()) for label in LABELS}))
    block = m3_ceiling(rows, "1800", coarse=False)["NKD"]
    ok = abs(float(block["structure_excess_usd"])) < 4.0 * float(
        block["shuffled_sd_usd"])
    out = [_check("M3/exchangeable cells show no structure excess", ok,
                  f"excess {block['structure_excess_usd']:.4f} vs shuffle sd "
                  f"{block['shuffled_sd_usd']:.4f}, pctile {block['percentile']}")]
    # Plant real per-cell structure: EXACTLY ONE good occurrence per cell.  A
    # cross-cell shuffle destroys that - it hands some cells two of the good
    # values and others none - so the real per-cell-max oracle must sit above
    # the shuffled ceiling.
    for row in rows:
        if row.bar == 3:
            row.y["1800"] += 5.0
    lifted = m3_ceiling(rows, "1800", coarse=False)["NKD"]
    out.append(_check("M3/planted per-cell structure clears the shuffle p95",
                      bool(lifted["above_p95"])
                      and float(lifted["structure_excess_usd"]) > 0.0,
                      f"excess {lifted['structure_excess_usd']:.3f} usd, "
                      f"real {lifted['real_oracle_mean_usd']:.3f} vs shuffle p95 "
                      f"{lifted['shuffled_p95_usd']:.3f}, "
                      f"pctile {lifted['percentile']}, band {lifted['band']}"))
    out.append(_check("M3/planted spread structure bands as ABOVE-P95",
                      lifted["band"] == "ABOVE-P95", str(lifted["band"])))
    # The opposite planting: pile every good value into a QUARTER of the cells.
    # Scattering them then raises the per-cell-max ceiling, so the real oracle
    # sits under the shuffle - the BELOW-P5 case sweep 15 reported, which must
    # come back named rather than as a bare "no structure".
    clustered: list[Row] = []
    rng2 = np.random.default_rng(5)
    for cell in range(120):
        for index in range(5):
            value = float(rng2.normal())
            if cell % 4 == 0:
                value += 9.0
            clustered.append(Row(asset="NKD", d8=20220101 + cell // 4,
                                 phase="0", cell=cell, side=1, bar=index + 1,
                                 k=index + 1, ord_side=index + 1,
                                 x=np.zeros(NFEAT),
                                 y={label: value for label in LABELS}))
    packed = m3_ceiling(clustered, "1800", coarse=False)["NKD"]
    out.append(_check(
        "M3/planted within-cell clustering bands as BELOW-P5",
        packed["band"] == "BELOW-P5"
        and float(packed["structure_excess_usd"]) < 0.0,
        f"band {packed['band']}, excess {packed['structure_excess_usd']:.3f} usd, "
        f"real {packed['real_oracle_mean_usd']:.3f} vs shuffle p05 "
        f"{packed['shuffled_p05_usd']:.3f}, pctile {packed['percentile']}"))
    return out


def _selftest_capacity() -> list[tuple[str, bool, str]]:
    class Rec:
        pass
    recs = []
    for day in range(4):
        for _ in range(2):
            rec = Rec()
            rec.asset, rec.d8 = "NKD", 20220101 + day
            rec.phase_open_ts_ns = 0
            rec.phase_close_ts_ns = 7200 * NANOS      # a 2 h phase
            recs.append(rec)
    rows = [Row(asset="NKD", d8=20220101, phase="0", cell=0, side=1, bar=b,
                k=b, ord_side=b, x=np.zeros(NFEAT),
                y={label: 0.0 for label in LABELS}) for b in (1, 2, 3)]
    m1 = {"_oof": {}, "NKD": {}}
    block = m4_capacity(rows, recs, m1)
    # wait = 60 s; a 2 h phase at h=3600 fits floor((7200+60)/3660) = 1 per cell,
    # two cells a day, so 2 seats; at h=1800 floor(7260/1860) = 3, so 6 seats.
    got_1800 = block["NKD"]["1800"]["capacity_raw"]
    got_3600 = block["NKD"]["3600"]["capacity_raw"]
    return [
        _check("M4/capacity is the phase span divided by hold plus wait",
               abs(got_1800 - 6.0) < 1e-9 and abs(got_3600 - 2.0) < 1e-9,
               f"h=1800 {got_1800}, h=3600 {got_3600}, wait "
               f"{block['candidate_wait_median_s']['NKD']:.0f} s"),
        _check("M4/the portfolio cap binds at 4 per asset-day",
               abs(block["NKD"]["1800"]["capacity_capped"] - 4.0) < 1e-9,
               f"capped {block['NKD']['1800']['capacity_capped']}"),
    ]


def selftest() -> int:
    mutant = _mutant()
    print(f"sweep 16 selftest  spec_sha {SPEC_SHA[:16]}  "
          f"code_sha {code_sha()[:16]}  mutant {mutant or 'none'}")
    rows: list[tuple[str, bool, str]] = []
    rows += _selftest_horizon_law()
    rows += _selftest_batching()
    rows += _selftest_capacity()
    rows += _selftest_shuffle()
    rows += _selftest_m1()
    rows += _selftest_mutant()
    width = max(len(name) for name, _ok, _detail in rows)
    bad = 0
    for name, ok, detail in rows:
        bad += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {name.ljust(width)}  {detail}")
    print(f"\n{len(rows) - bad}/{len(rows)} selftest checks pass")
    return 0 if bad == 0 else 1


# --------------------------------------------------------------------------
# Report and log.
# --------------------------------------------------------------------------

def _show(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def log_rows(report: Mapping[str, object]) -> list[dict[str, object]]:
    m1 = report["m1"]
    m2 = report["m2"]
    m3 = report["m3"]
    m4 = report["m4"]
    m5 = report["m5"]
    ruling = report["decision"]
    params = json.dumps({"horizons_s": list(HORIZONS), "lambda": RIDGE_LAMBDA,
                         "features": NFEAT,
                         "min_prior_days": MIN_PRIOR_DAYS_FIT,
                         "min_fit_rows": MIN_FIT_ROWS,
                         "shuffle_draws": SHUFFLE_DRAWS,
                         "sign_flips": SIGN_FLIPS,
                         "coverages": list(COVERAGES),
                         "portfolio_cap": PORTFOLIO_CAP})
    shared = {
        "registered_utc": report["registered_utc"], "family": FAMILY,
        "params": params, "spec_sha": SPEC_SHA, "code_sha": report["code_sha"],
        "split_sha": report["split_sha"],
        "outcome_law_sha": report["outcome_law_sha"], "null_seed": SEED,
        "parent_trial": report["parent_trial"],
        "selection_rule": SELECTION_RULE, "verdict": "",
    }
    rows: list[dict[str, object]] = []
    counter = 0
    for h in HORIZONS:
        label = str(int(h))
        counter += 1
        rows.append({
            **shared, "id": f"sweep16-{counter:03d}",
            "rule": f"M1-R2/h{label}",
            "days": sum(int(m1[a]["scoring_days"]) for a in ASSETS),
            "err_rate_hg": m1["HG"][f"{label}/level"]["r2"],
            "err_rate_nkd": m1["NKD"][f"{label}/level"]["r2"],
            "err_rate_si": m1["SI"][f"{label}/level"]["r2"],
            "note": ("out-of-fold R2 of Y_h vs Y_close: "
                     + "; ".join(
                         f"{a} {_show(m1[a][f'{label}/level']['r2'])} vs "
                         f"{_show(m1[a]['close/level']['r2'])}"
                         for a in ASSETS))[:400],
        })
    for h in HORIZONS:
        label = str(int(h))
        counter += 1
        line = {a: m2["by_line"][f"{a}/{label}"] for a in ASSETS}
        rows.append({
            **shared, "id": f"sweep16-{counter:03d}",
            "rule": f"M2-SECOND-FIRST/h{label}",
            "days": sum(int(line[a]["blocks"]) for a in ASSETS),
            "hg_usd_day": line["HG"]["delta_usd_per_day"],
            "nkd_usd_day": line["NKD"]["delta_usd_per_day"],
            "si_usd_day": line["SI"]["delta_usd_per_day"],
            "mdd_hg": m5["HG"][label]["mdd_day_usd"],
            "mdd_nkd": m5["NKD"][label]["mdd_day_usd"],
            "mdd_si": m5["SI"][label]["mdd_day_usd"],
            "null_margin": line["NKD"]["p_max_adjusted"],
            "note": ("SECOND-FIRST usd/asset-day, p_adj: "
                     + "; ".join(f"{a} {_show(line[a]['delta_usd_per_day'])} "
                                 f"(p {_show(line[a]['p_max_adjusted'])})"
                                 for a in ASSETS)
                     + f"; to-close delta NKD "
                       f"{_show(m2['by_line']['NKD/close']['delta_usd_per_day'])}")[:400],
        })
    for h in HORIZONS:
        label = str(int(h))
        counter += 1
        rows.append({
            **shared, "id": f"sweep16-{counter:03d}",
            "rule": f"M3-CEILING/h{label}",
            "days": sum(int(m1[a]["scoring_days"]) for a in ASSETS),
            "err_rate_hg": m3["fine"][label]["HG"].get("structure_excess_usd"),
            "err_rate_nkd": m3["fine"][label]["NKD"].get("structure_excess_usd"),
            "err_rate_si": m3["fine"][label]["SI"].get("structure_excess_usd"),
            "note": ("structure excess fine/coarse, above shuffle p95: "
                     + "; ".join(
                         f"{a} {_show(m3['fine'][label][a].get('structure_excess_usd'))}"
                         f"/{_show(m3['coarse'][label][a].get('structure_excess_usd'))} "
                         f"({m3['fine'][label][a].get('band')}"
                         f"/{m3['coarse'][label][a].get('band')})"
                         for a in ASSETS))[:400],
        })
    for h in HORIZONS:
        label = str(int(h))
        counter += 1
        rows.append({
            **shared, "id": f"sweep16-{counter:03d}",
            "rule": f"M4-ARITHMETIC/h{label}",
            "days": sum(int(m1[a]["scoring_days"]) for a in ASSETS),
            "hg_usd_day": m4["HG"][label]["top_decile_mean_usd"],
            "nkd_usd_day": m4["NKD"][label]["top_decile_mean_usd"],
            "si_usd_day": m4["SI"][label]["top_decile_mean_usd"],
            "note": ("required per-trade at 0.6 coverage vs observed top-decile "
                     "mean Y_h: "
                     + "; ".join(
                         f"{a} {_show(m4[a][label]['required_per_trade_usd']['cov0.6'])}"
                         f" vs {_show(m4[a][label]['top_decile_mean_usd'])} "
                         f"(cap {m4[a][label]['capacity_capped']:.2f})"
                         for a in ASSETS))[:400],
        })
    for asset in ASSETS:
        counter += 1
        best = max(HORIZONS, key=lambda h: (
            m1[asset][f"{h}/level"]["r2"] or -9.0))
        row = ruling["by_asset"][asset][str(best)]
        rows.append({
            **shared, "id": f"sweep16-{counter:03d}",
            "rule": f"RULING/{asset}",
            "days": int(m1[asset]["scoring_days"]),
            "err_rate_hg": row["r2_level"] if asset == "HG" else None,
            "err_rate_nkd": row["r2_level"] if asset == "NKD" else None,
            "err_rate_si": row["r2_level"] if asset == "SI" else None,
            "null_margin": row["p_max_adjusted"],
            "verdict": ruling["verdict"],
            "note": (f"{ruling['verdict']}; best horizon {best} s: R2(Y_h) "
                     f"{_show(row['r2_level'])} vs R2(close) "
                     f"{_show(row['r2_close'])}; SECOND-FIRST "
                     f"{_show(row['delta_usd_per_day'])} usd/day p_adj "
                     f"{_show(row['p_max_adjusted'])}; M3 band fine/coarse "
                     f"{row['band_fine']}/{row['band_coarse']}; arithmetic "
                     f"{row['arithmetic']}")[:400],
        })
    return rows


def write_report(report: Mapping[str, object]) -> None:
    OUT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True,
                                    default=S8._json_default) + "\n")


def report_stamp() -> str:
    import datetime as dt
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


# --------------------------------------------------------------------------
# Entry point.
# --------------------------------------------------------------------------

def run() -> dict[str, object]:
    mutant = _mutant()
    started = time.time()
    parent = parent_trial()
    # Entry.cell indexes the FILTERED record list, so the asset set is never
    # subsetted here: doing so would silently misalign every priced number.
    cells, asset_days, _skipped = S8.build_cells(ASSETS)
    records, _days = S1.load_cache()
    records = [rec for rec in records if rec.asset in ASSETS]
    explore_days = S1._explore_days(ASSETS)

    tape = S9.load_tape(cells)
    forecast = S9.forecast_variance(cells)
    plane9 = S9.build_plane(cells, forecast, tape)
    gate = S14.reproduce_sweep9(plane9)
    if not gate["matches"]:
        raise SweepRefusal("sweep 14's occurrence stream did not reproduce; no "
                           "measurement is believed past this point")
    states = S12.day_states({asset: explore_days[asset] for asset in ASSETS})
    streams, stream_counters = S14.build_streams(plane9, cells, states, "")

    horizon, hand = build_horizon_plane(records)
    hand_block = hand_check_verdict(hand)
    if not hand_block["ok"] and mutant != MUTANT_PAST:
        raise SweepRefusal("the per-entry-close batching disagreed with the "
                           "frozen scalar outcome law")

    rows, row_counters = build_rows(streams, horizon, cells, mutant)
    m1 = m1_predictability(rows, explore_days)
    crosscheck = sweep15_crosscheck(m1)

    gate13, book = S13.record_gate(cells)
    receipt = S13.reproduce_first(cells, gate13, book)
    if receipt["verdict"] != "PASS":
        raise SweepRefusal("sweep 13's FIRST reproduction gate failed; the "
                           "ordinal mechanism is not the frozen one")
    idents = S13.build_identities(cells, explore_days)
    second_run = S13.run_second(cells, book, idents, "")
    first_entries = S8.entries_of(gate13.shots["PRIMARY"], records)
    second_entries = S8.entries_of([take.shot for take in second_run.takes],
                                   records)
    first_priced, first_dropped = price_entries(first_entries, horizon)
    second_priced, second_dropped = price_entries(second_entries, horizon)
    m2 = m2_mechanism(first_priced, second_priced, explore_days)

    m3 = {"fine": {label: m3_ceiling(rows, label, coarse=False)
                   for label in LABELS},
          "coarse": {label: m3_ceiling(rows, label, coarse=True)
                     for label in LABELS}}
    m4 = m4_capacity(rows, records, m1)
    m5 = m5_mdd(second_priced)
    ruling = decide(m1, m2, m3, m4)
    slim = {asset: {key: value for key, value in m1[asset].items()}
            for asset in ASSETS}
    return {
        "schema": "QRE2MILLSWEEP16", "tier": "exploratory",
        "spec_sha": SPEC_SHA, "code_sha": code_sha(),
        "split_sha": S1.split_sha(), "outcome_law_sha": S1.outcome_law_sha(),
        "seed": SEED, "mutant": mutant, "family": FAMILY,
        "parent_trial": parent, "selection_rule": SELECTION_RULE,
        "registered_utc": report_stamp(),
        "horizons_s": list(HORIZONS),
        "asset_days": {a: int(asset_days.get(a, 0)) for a in ASSETS},
        "stream_gate": gate, "stream_counters": stream_counters,
        "sweep13_reproduction": receipt,
        "horizon_plane": dict(horizon.counters),
        "hand_checks": hand_block, "row_counters": row_counters,
        "sweep15_crosscheck": crosscheck,
        "entries": {"first": len(first_priced), "second": len(second_priced),
                    "first_dropped": first_dropped,
                    "second_dropped": second_dropped},
        "m1": slim, "m2": m2, "m3": m3, "m4": m4, "m5": m5,
        "decision": ruling,
        "elapsed_s": round(time.time() - started, 1),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--log", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    report = run()
    print(f"sweep 16 spec_sha {SPEC_SHA[:16]} code_sha {code_sha()[:16]} "
          f"seed {SEED} parent {report['parent_trial']} "
          f"mutant {report['mutant'] or 'none'}")
    print_gate(report["stream_gate"], report["hand_checks"],
               report["row_counters"], report["horizon_plane"])
    print_m1(report["m1"])
    print_crosscheck(report["sweep15_crosscheck"])
    print_m2(report["m2"], report["entries"])
    print_m3(report["m3"])
    print_m4(report["m4"])
    print_m5(report["m5"])
    print_decision(report["decision"])
    log = log_rows(report)
    report["log"] = log
    write_report(report)
    print(f"\nwrote {OUT_PATH} in {report['elapsed_s']} s")
    if args.log:
        if report["mutant"]:
            raise SweepRefusal("a mutant run must never touch the hypothesis log")
        written = S1.append_log(log)
        print(f"appended {written} hypothesis-log rows to {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
