#!/usr/bin/env python3
"""Sweep 20 of the side-resolution mill: magnitude and exit ASYMMETRY.

Sol's design ruling ``.audit/briefs/mill-fixhold-sol-out.md`` section G, the
charter section "The magnitude turn" in ``.audit/briefs/mill-side-resolution.md``.
F13 is DEAD as a signed ordinal-cash route; every signed channel is negative and
only the MAGNITUDE channel survives out of fold (sweep 15: |Y| R2 +0.119/+0.127/
+0.096 HG/NKD/SI).  The one useful next unit is not another signed ranker.  It
is a measurement: the state knows a big move is coming, so PRICE BOTH SIDES at
the moments it says so and ask whether the two sides are ASYMMETRIC once a stop
is attached.

The mechanism this unit exists to falsify is stated in Sol G before any number
is read: under a martingale a bounded symmetric stopping rule has zero
expectation before costs and NEGATIVE expectation after costs.  Magnitude plus a
stop does not make direction irrelevant.  The route needs conditional path
continuation or another measured asymmetry, and the coin expectation
``0.5 * (long + short)`` at the same timestamp is the exact statistic that
measures it: it is direction-free by construction, so anything it earns above
minus-one-cost is asymmetry and nothing else.

LAW OF INPUTS AND PRICING, the no-microstructure law restated.  Features stay on
the causal one-minute plane - sweep 14's 16 features, unchanged, no raw suffix
value ever becomes a feature.  Raw tick suffixes PRICE outcomes and first-passage
stop crossings, exactly as the frozen mill already prices the -900 wall.  Minute
OHLC may never infer intraminute crossing order; the mutant
``QRE2_MILL_S20_MUTANT=stop_uses_minute_ohlc`` does precisely that and must turn
the selftest red.

Machinery is imported, never re-implemented.  Sweep 8 supplies the cells and
ATR14_prev, sweep 9 the row plane whose counters are the refuse-to-run gate,
sweep 12 the day states, sweep 14 the occurrence stream, the 16-feature plane and
the walk-forward fold law, sweep 15 the coarse post-reset grain and its banked
scoring-day counts, sweep 1 the cost law, the cash reductions and the log.  The
TWO new objects are (a) the no-wall terminal label and (b) the both-sides
ATR-stop pricer, and both are the frozen batched outcome machinery with one
boundary changed and the wall taken out.

Nothing here is executable.  EXPLORE only, kill-only, no packs, no HOLD, no
teacher labels, no 2021, no 2025H2, no commits.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
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

from engine.entry_v2.confirmation_types import FEE_USD  # noqa: E402

import mill as M  # noqa: E402
import sweep1 as S1  # noqa: E402
import sweep8 as S8  # noqa: E402
import sweep9_twins as S9  # noqa: E402
import sweep12 as S12  # noqa: E402
import sweep14 as S14  # noqa: E402
import sweep15 as S15  # noqa: E402

# --------------------------------------------------------------------------
# The law, registered before anything is read.
# --------------------------------------------------------------------------

SPEC = """QRE2MILLSWEEP20
tier=exploratory; EXPLORE-only, kill-only.  Family F17-MAGASYM (Sol's
  F14-MAGASYM, renamed to avoid the F14-CONDSIGN collision already in the log).
  Seed 20260827.  Parent trial sweep16-017.  NO COMMITS, NO FREEZE, no packs, no
  HOLD, no teacher labels, no 2021, no 2025H2.  This unit MEASURES asymmetry; it
  does not adopt an exit and it cannot promote.
GATE.  Sweep 9's row plane (47402 rows; certifiable 138/132/132; candidates_seen
  313131; cells_with_rows 385) and sweep 14's banked scoring days (41/40/39) are
  reproduced before anything is measured.  A mismatch refuses the run.
UNIVERSE.  Sweep 15's COARSE post-reset grain: the inzone_ordinal == 1 rows of
  sweep 14's deduped occurrence stream (sweep 15's own reset law, imported).
  Identical (asset, entry timestamp) pairs are deduplicated by the LOWEST stable
  (cell, row) key.  Sweep 15 banked 1186/1077/1082 coarse rows on its scoring
  scope; this unit reproduces that count before its own dedup and label-validity
  filters are applied, and prints both.
INPUT LAW.  The 16 causal one-minute features of sweep 14, unchanged.  NO raw
  suffix value is ever a feature.  Raw ticks price outcomes and stop crossings
  only.
LABEL (M1).  NO-WALL absolute terminal dollar move at horizon h for h in {1800,
  3600, 5400, 7200} s: exit at the FIRST of entry + h, the phase close, or the
  frozen generation truncation; the -900 wall is NOT in this label and not in
  this measurement.  Primary target ABSMOVE = |exit_mid2 - entry_mid2| * factor,
  side-free and cost-free, which is literally the absolute terminal dollar move
  and is the honest object for a both-sides study.  Secondary, reported beside
  it for continuity with sweep 15's banked magnitude channel, ABSCERT =
  |signed cert on the row's own fade side|, cost charged once at entry.
  Selection uses ABSMOVE.
MODEL (M1).  The existing chronological walk-forward folds: a day is scored only
  with >= 25 strictly prior EXPLORE days for its asset; the fold's training rows
  are that asset's coarse rows on strictly earlier EXPLORE days; >= 50 fit rows.
  Ridge lambda 1.0, features standardised on the training fold, intercept
  unpenalised.  CELL-BALANCED loss: every row carries weight 1 / (rows in its
  cell inside the training fold), normalised to sum to n, so one busy cell
  cannot buy the fit.  The TOP-DECILE score cutoff is learned INSIDE each
  training fold (the 90th percentile of that fold's in-fold fitted values) and
  applied to the scored day.  It is never read off the pooled out-of-fold score
  distribution.
NULL (M1).  Synchronized max-R2 day-block permutation null.  Per draw one
  permutation of the shared EXPLORE date list induces, per asset, a permutation
  of its own day blocks; the ragged label blocks are re-sliced onto the
  unchanged rows, so both row-level and day-level association break while the
  within-day label structure survives.  THE SAME permutation is used across all
  four horizons in a draw.  Every fold is refit (the fold gram depends only on X
  and the weights, so it is factored once and reused; every right-hand side is
  refit).  200 draws, stated as such.  The maximum is taken over the eligible
  family NKD and SI crossed with the four horizons;
  p_j = (1 + count(maxR2 >= R2_j)) / (draws + 1).  HG is report-only.
PRICING (M2).  For every SELECTED (top-decile out-of-fold) timestamp: the frozen
  entry quote (last trusted row STRICTLY before the stamp) and the frozen cost
  law, charged once at entry.  BOTH sides are priced on the raw suffix through
  the first of the ATR stop, entry + h, the phase close, or the generation
  truncation.  Stop distance is q * ATR14_prev in mid2 units for q in {0.25,
  0.50, 0.75, 1.00}; the adverse boundary is floor(entry - d) for a long and
  ceil(entry + d) for a short, the frozen wall's own floor/ceil convention.  The
  exit is the FIRST ACTUAL raw mid through that boundary - never a clipped
  synthetic stop price - so the OVERSHOOT is real and is recorded.  Recorded per
  row and side: terminal return, MFE, MAE, first-passage order, gap size at the
  stop, overshoot, and the exit cause in four exclusive buckets STOP, HORIZON,
  PHASE_CLOSE, GENERATION_END, split per asset and horizon.
COIN (M3).  The analytic mechanism outcome is COIN = 0.5 * (long PnL + short
  PnL) at the SAME timestamp.  It is a coin-side expectation, not two
  simultaneous trades.  Reported per asset: mean coin, the CHOP fraction where
  both hypothetical sides stop inside h, entry cost divided by stop distance,
  and the gap-through-stop loss totals.
CONTROL (M4).  Out-of-fold magnitude scores are permuted among coarse states
  within the same (asset, date, phase) cell.  The permutation preserves each
  cell's score multiset, so the training-fold cutoff selects exactly the same
  COUNT per cell: the control is count-matched by construction.  THE SAME
  permutation is used across every horizon and every stop.  2000 draws; the
  control level for an asset-day is the mean over draws.  Inference is the
  shared-date-sign studentized maxT law of Sol section A: one Rademacher sign per
  calendar date applied to EVERY line, 10000 draws, over the family NKD and SI
  crossed with 4 horizons and 4 stops (32 lines).  Dates with no difference
  contribute zero.  p_j = (1 + count(maxT >= T_j)) / (draws + 1).  HG is
  report-only.  A simultaneous 95 percent upper bound is mean_j + c95 * SE_j with
  c95 the 95th percentile of the shared-sign maxT null.
REPLAY (M5).  Executable sensitivity, Sol section B.  One side per selected row
  from a frozen sha256 of (asset, date, entry timestamp, seed).  Chronological
  replay: sort by event timestamp with the frozen tie break (stamp, asset, cell,
  row, side); process EXITS BEFORE ENTRIES at an equal stamp; seat only when the
  asset is flat; hold to the registered exit; at most 12 seated entries per
  PORTFOLIO date, dynamically, never four reserved per asset; carry every split
  date including zero-entry dates.  Reported: seated entries per asset-day
  distribution, zero-entry fraction, rejected-for-occupancy, rejected-for-cap,
  exact usd/day per asset with mean and mean - 2 * SE over asset-day blocks.
MDD (M6).  The full ledger law of Sol section D: per-asset trade MDD (seated
  trades by entry stamp, then exit stamp, cell, row, side), per-asset DAY MDD
  including zero-cash dates, portfolio trade and portfolio day MDD, and
  EVENT-TIME portfolio equity that charges cost at entry and marks every open
  position at the causal raw mid until exit.  Cumulative cash starts at zero and
  MDD is the largest prior peak minus later equity.  The maximum across binding
  ledgers must be strictly below 1000 USD.
STRESS (M7).  The standing 2 percent adversarial replay, in this route's form:
  the worst 2 percent of selected entries per asset - the ones with the largest
  damage from being handed their worse side - take the WORSE of their two side
  outcomes, and the replay is re-run so occupancy follows the changed exits.
  Plus one exit-spread stress: the spread component of the frozen cost is
  charged a SECOND time on every STOP exit.  Year and phase stability of the
  coin expectation is reported beside both.
LETTERS, pre-registered, verbatim from Sol G.
  ASYM-SURVIVES-EXPLORE: NKD and SI EACH have a registered (h, q) with magnitude
    R2 >= 0.02 at max-R2 adjusted p <= 0.05, positive selected-minus-control coin
    expectation at maxT adjusted p <= 0.05, and an exact hash-side replay whose
    mean - 2 * SE clears the asset rung; every MDD ledger and BOTH stresses
    clear (MDD < 1000); and the nearest inward (h, q) neighbours retain positive
    after-cost cash with no MDD breach.
  MAGNITUDE-ONLY: the magnitude R2 gate passes on both deciding assets and the
    selected rows show excursion separation, but the coin or the executable bar
    fails.  It confirms a measurement signal only.  It does not authorize entry-
    model development or HOLD, and it CLOSES this simple ATR-stop shape.
  ASYM-KILL: either deciding asset has no magnitude line clearing the adjusted
    predictive gate, OR every registered (h, q) has a simultaneous 95 percent
    upper bound <= 0 for selected-minus-control coin cash or below rung for
    executable cash.
  UNRESOLVED: every other pattern.  It cannot spend HOLD.
MUTANT.  QRE2_MILL_S20_MUTANT=stop_uses_minute_ohlc infers the stop crossing from
  the 60 s minute lattice instead of the raw tick suffix and prices the exit at
  the minute value.  It must flip the planted stop cases red.
"""

ASSETS = S1.ASSETS
DECIDING = ("NKD", "SI")
REPORT_ONLY = ("HG",)
PHASES = S14.PHASES
BAR_SECONDS = S1.BAR_SECONDS
NANOS = 1_000_000_000
SEED = 20260827

HORIZONS = (1800, 3600, 5400, 7200)
STOPS = (0.25, 0.50, 0.75, 1.00)
CAUSES = ("STOP", "HORIZON", "PHASE_CLOSE", "GENERATION_END")
SIDES = (1, -1)

# Frozen, inherited.  Aliases so a drift upstream fails loudly here.
FEATURES = S14.FEATURES
NFEAT = S14.NFEAT
ORD_SIDE = FEATURES.index("ord_side")
RIDGE_LAMBDA = S14.RIDGE_LAMBDA               # 1.0
MIN_PRIOR_DAYS_FIT = S14.MIN_PRIOR_DAYS_FIT   # 25
MIN_FIT_ROWS = S14.MIN_FIT_ROWS               # 50
DAY_RUNG_USD = S1.DAY_RUNG_USD                # HG 2000, NKD 1500, SI 1500
MDD_CEILING = S1.MDD_CAP_USD                  # 1000
STRESS_RATE = 0.02                            # the standing adversarial rate
REPRO_ROWS = S14.REPRO_ROWS                   # 47402
REPRO_CERTIFIABLE = S14.REPRO_CERTIFIABLE     # 138/132/132
REPRO_COUNTERS = S14.REPRO_COUNTERS           # candidates_seen 313131, ...
REPRO_SCORING_DAYS = {"HG": 41, "NKD": 40, "SI": 39}
S15_COARSE_SCORING_ROWS = {"HG": 1186, "NKD": 1077, "SI": 1082}

# This unit's own constants.
TOP_DECILE = 0.10
R2_DRAWS = 200
CONTROL_DRAWS = 2000
SIGN_DRAWS = 10_000
PORTFOLIO_CAP = 12

# Pre-registered decision bounds.
R2_FLOOR = 0.02
P_CEILING = 0.05

FAMILY = "F17-MAGASYM"
PARENT_TRIAL = "sweep16-017"
SELECTION_RULE = ("none: pre-registered (horizon x stop) grid, imported fold "
                  "law, train-fold cutoff, count-matched permutation control")

MUTANT_ENV = "QRE2_MILL_S20_MUTANT"
MUTANT_OHLC = "stop_uses_minute_ohlc"
MUTANTS = (MUTANT_OHLC,)

OUT_PATH = ROOT / ".audit/mill-sweep20.json"
LOG_PATH = S1.LOG_PATH


class SweepRefusal(RuntimeError):
    pass


SPEC_SHA = S1._sha_text(SPEC)


def code_sha() -> str:
    return S1._sha_file(Path(__file__).resolve())


def _mutant() -> str:
    name = os.environ.get(MUTANT_ENV, "")
    if name and name not in MUTANTS:
        raise SweepRefusal(f"unknown sweep-20 mutant {name!r}; known: {MUTANTS}")
    return name


def _line(h: int, q: float) -> str:
    return f"h{int(h)}/q{q:.2f}"


def _mean_se(values: Sequence[float]) -> tuple[float | None, float | None]:
    array = np.asarray(list(values), np.float64)
    if not len(array):
        return None, None
    mean = float(array.mean())
    se = (float(array.std(ddof=1) / math.sqrt(len(array)))
          if len(array) > 1 else 0.0)
    return mean, se


# --------------------------------------------------------------------------
# THE FIRST NEW OBJECT: the NO-WALL terminal label, per-entry close.
# --------------------------------------------------------------------------

def nowall_grid(index: M.MillIndex, t_ns: np.ndarray, close_ts_ns: np.ndarray,
                ) -> Mapping[str, np.ndarray]:
    """The frozen batched outcome law with the WALL TAKEN OUT.

    Line-for-line ``mill.MillIndex.outcomes_grid`` (211-283) and sweep 16's
    per-entry-close variant, with exactly two changes: the close is per entry,
    and the wall first-passage search is REMOVED so the exit is always the last
    trusted row inside the window.  Everything else - the strict-left start, the
    raw-generation expectation, the generation-end truncation and the extrema
    window - is the frozen law.  The -900 wall is a real executable risk rule but
    it is a CENSOR on a magnitude label, and Sol G puts it out of this
    measurement, so it is out of this label too.
    """

    snapshots = np.asarray(t_ns, np.int64)
    closes = np.asarray(close_ts_ns, np.int64)
    if snapshots.shape != closes.shape:
        raise SweepRefusal("no-wall grid inputs are invalid")
    empty = MappingProxyType({
        "input_index": np.zeros(0, np.int64),
        "entry_mid2": np.zeros(0, np.int64),
        "frozen_cost_usd": np.zeros(0, np.float64),
        "exit_mid2": np.zeros(0, np.int64),
        "exit_ts_ns": np.zeros(0, np.int64),
        "exit_row": np.zeros(0, np.int64),
        "start_row": np.zeros(0, np.int64),
        "truncated_generation": np.zeros(0, bool),
        "closed_at_phase": np.zeros(0, bool),
    })
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
    entries = index.mid2[quote_at[keep]].astype(np.int64)
    costs = ((index.ask[quote_at[keep]] - index.bid[quote_at[keep]])
             * index.multiplier / 1e9 + FEE_USD)
    expected = index.generations_at_snapshots(snapshots[keep])
    gen_end = index._engine.generation_end[starts]
    ends = np.minimum(phase_end[keep], gen_end)
    valid = (index.generation[starts] == expected) & (starts < ends)
    keep = keep[valid]
    if not len(keep):
        return empty
    starts = starts[valid]
    ends = ends[valid]
    exit_position = (ends - 1).astype(np.int64)
    return MappingProxyType({
        "input_index": keep.astype(np.int64),
        "entry_mid2": entries[valid],
        "frozen_cost_usd": np.asarray(costs, np.float64)[valid],
        "exit_mid2": index.mid2[exit_position].astype(np.int64),
        "exit_ts_ns": index.ts[exit_position].astype(np.int64),
        "exit_row": exit_position,
        "start_row": starts.astype(np.int64),
        "truncated_generation": (gen_end[valid] < phase_end[keep]),
        "closed_at_phase": np.zeros(len(keep), bool),
    })


# --------------------------------------------------------------------------
# THE SECOND NEW OBJECT: both sides, ATR stop, RAW-TICK first passage.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Legs:
    """One (horizon, stop, side) pricing of a batch of entry stamps."""

    ok: np.ndarray            # (n,) the row priced
    terminal_usd: np.ndarray  # (n,) cert after the frozen cost, charged once
    mfe_usd: np.ndarray
    mae_usd: np.ndarray
    stop_hit: np.ndarray
    cause: np.ndarray         # (n,) int index into CAUSES
    overshoot_usd: np.ndarray
    gap_usd: np.ndarray
    exit_ts_ns: np.ndarray
    exit_bar: np.ndarray      # (n,) lattice bar of the exit, for the mark path
    spread_usd: np.ndarray    # (n,) the spread component of the entry cost


def price_legs(index: M.MillIndex, lat: np.ndarray, mid_lat: np.ndarray,
               bars: np.ndarray, side: int, horizon_s: int, stop_q: float,
               atr_mid2: float, phase_close_ns: int, mutant: str = "") -> Legs:
    """Price one side through the first of the ATR stop, h, close or generation.

    THE STOP IS A RAW-TICK FIRST PASSAGE.  ``index.range.first_many`` is the same
    monotone first-passage structure the frozen mill uses for the -900 wall, and
    the boundary uses the frozen floor/ceil convention, so a crossing is a real
    printed mid at or through the stop and the exit price is THAT MID - never a
    clipped synthetic stop level.  The difference between the two is the
    OVERSHOOT and it is recorded rather than assumed away.

    ``QRE2_MILL_S20_MUTANT=stop_uses_minute_ohlc`` replaces the tick search with
    a scan of the 60 s minute lattice: it can only see a crossing that survives
    to a minute close, and it prices the exit at that minute's value.  That is
    exactly the intraminute-order inference the no-microstructure law forbids, so
    it is this unit's red case.
    """

    n = len(bars)
    empty = Legs(*(np.zeros(n, np.bool_), np.zeros(n), np.zeros(n), np.zeros(n),
                   np.zeros(n, np.bool_), np.zeros(n, np.int64), np.zeros(n),
                   np.zeros(n), np.zeros(n, np.int64),
                   np.full(n, -1, np.int64), np.zeros(n)))
    if not n or not len(index.ts):
        return empty
    snapshots = np.asarray(lat, np.int64)[bars]
    horizon_ns = snapshots + int(horizon_s) * NANOS
    closes = np.minimum(horizon_ns, int(phase_close_ns))
    quote_at = index.positions(snapshots)
    starts_all = np.searchsorted(index.ts, snapshots.astype(np.uint64),
                                 side="left")
    phase_end = np.searchsorted(index.ts, closes.astype(np.uint64), side="right")
    legal = ((quote_at >= 0) & (starts_all < phase_end))
    if not legal.any():
        return empty
    bid = index.bid[np.maximum(quote_at, 0)]
    ask = index.ask[np.maximum(quote_at, 0)]
    legal &= (bid > 0) & (ask > bid)
    if not legal.any():
        return empty
    take = np.flatnonzero(legal)
    starts = starts_all[take]
    entries = index.mid2[quote_at[take]].astype(np.int64)
    spread = (ask[take] - bid[take]) * index.multiplier / 1e9
    costs = spread + FEE_USD
    expected = index.generations_at_snapshots(snapshots[take])
    gen_end = index._engine.generation_end[starts]
    ends = np.minimum(phase_end[take], gen_end)
    valid = (index.generation[starts] == expected) & (starts < ends)
    take = take[valid]
    if not len(take):
        return empty
    starts = starts[valid]
    ends = ends[valid]
    entries = entries[valid]
    costs = np.asarray(costs, np.float64)[valid]
    spread = np.asarray(spread, np.float64)[valid]
    gen_truncated = gen_end[valid] < phase_end[take]
    horizon_bound = horizon_ns[take] <= int(phase_close_ns)

    distance = float(stop_q) * float(atr_mid2)
    level = entries.astype(np.float64) + (-distance if side > 0 else distance)
    if side > 0:
        threshold = np.floor(level).astype(np.int64)
    else:
        threshold = np.ceil(level).astype(np.int64)

    if mutant == MUTANT_OHLC:
        stop_row, stop_bar = _minute_stop(index, lat, mid_lat, bars[take],
                                          starts, ends, threshold, side, closes[take])
    else:
        stop_row = index.range.first_many(starts, ends, threshold,
                                          use_min=(side > 0)).astype(np.int64)
        stop_bar = np.full(len(take), -1, np.int64)

    hit = stop_row >= 0
    exit_position = np.where(hit, stop_row, ends - 1).astype(np.int64)
    exit_mid = index.mid2[exit_position].astype(np.int64)
    terminal = side * (exit_mid - entries) * index.factor - costs
    low, high = index.range.extrema_many(starts, exit_position + 1)
    low_value = side * (low - entries) * index.factor - costs
    high_value = side * (high - entries) * index.factor - costs

    # Four exclusive causes.  A generation truncation that CUTS the window short
    # is GENERATION_END; otherwise the binding boundary is the horizon when
    # entry + h landed at or before the phase close, and the phase close when it
    # did not.  ``ends`` is the min of the two, so the test is exact.
    cause = np.where(hit, 0, np.where(gen_truncated, 3,
                                      np.where(horizon_bound, 1, 2)))

    overshoot = np.where(
        hit, np.maximum(0.0, (level - exit_mid) * index.factor if side > 0
                        else (exit_mid - level) * index.factor), 0.0)
    previous = np.maximum(exit_position - 1, 0)
    gap = np.where(hit, np.abs(index.mid2[exit_position].astype(np.float64)
                               - index.mid2[previous].astype(np.float64))
                   * index.factor, 0.0)

    lattice = np.asarray(lat, np.int64)
    exit_bar = np.searchsorted(lattice, index.ts[exit_position].astype(np.int64),
                               side="right") - 1
    if mutant == MUTANT_OHLC:
        exit_bar = np.where(stop_bar >= 0, stop_bar, exit_bar)

    out = empty
    out.ok[take] = True
    out.terminal_usd[take] = terminal
    out.mfe_usd[take] = np.maximum(0.0, np.maximum(low_value, high_value))
    out.mae_usd[take] = np.maximum(0.0, -np.minimum(low_value, high_value))
    out.stop_hit[take] = hit
    out.cause[take] = cause
    out.overshoot_usd[take] = overshoot
    out.gap_usd[take] = gap
    out.exit_ts_ns[take] = index.ts[exit_position].astype(np.int64)
    out.exit_bar[take] = exit_bar
    out.spread_usd[take] = spread
    return out


def _minute_stop(index: M.MillIndex, lat: np.ndarray, mid_lat: np.ndarray,
                 bars: np.ndarray, starts: np.ndarray, ends: np.ndarray,
                 threshold: np.ndarray, side: int, closes: np.ndarray
                 ) -> tuple[np.ndarray, np.ndarray]:
    """THE MUTANT: infer the crossing from the 60 s lattice, not the tick tape.

    The lattice value at bar b is the last trusted mid STRICTLY before b's close,
    so a crossing that happens inside a minute and reverts before the close is
    invisible here, and a crossing that survives is priced at the minute's mid
    rather than at the tick that actually went through.  Both errors are the
    no-microstructure law's forbidden direction.
    """

    lattice = np.asarray(lat, np.int64)
    values = np.asarray(mid_lat, np.float64)
    row = np.full(len(bars), -1, np.int64)
    bar_out = np.full(len(bars), -1, np.int64)
    for position, bar in enumerate(bars):
        last = int(np.searchsorted(lattice, int(closes[position]),
                                   side="right")) - 1
        if last <= int(bar):
            continue
        window = values[int(bar) + 1:last + 1]
        crossed = (window <= float(threshold[position]) if side > 0
                   else window >= float(threshold[position]))
        found = np.flatnonzero(crossed)
        if not len(found):
            continue
        hit_bar = int(bar) + 1 + int(found[0])
        position_row = int(np.searchsorted(
            index.ts, np.uint64(int(lattice[hit_bar])), side="left")) - 1
        if position_row < int(starts[position]) or position_row >= int(ends[position]):
            continue
        row[position] = position_row
        bar_out[position] = hit_bar
    return row, bar_out


# --------------------------------------------------------------------------
# The universe: coarse post-reset rows, deduped, with labels and pricing.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class CRow:
    """One coarse post-reset state: features, no-wall labels, both-side legs."""

    asset: str
    d8: int
    phase: str
    cell: int
    row: int
    bar: int
    side: int
    entry_ts_ns: int
    entry_mid2: int
    cost_usd: float
    spread_usd: float
    atr_mid2: float
    year: int
    x: np.ndarray
    absmove: dict[int, float] = field(default_factory=dict)
    abscert: dict[int, float] = field(default_factory=dict)
    label_cause: dict[int, str] = field(default_factory=dict)


def coarse_universe(streams: Sequence[S14.Stream], records: Sequence[S1.CellRec]
                    ) -> tuple[list[tuple[S14.Stream, S14.Occ]], dict[str, object]]:
    """Sweep 15's coarse grain, then Sol's dedup by (asset, entry timestamp).

    The reset law is sweep 15's ``coarse_occs`` - inzone_ordinal == 1, the one
    marker per (cell, side, new extreme) - imported rather than restated.  The
    dedup keeps the LOWEST stable (cell, row) key, which is a total order on the
    plane and therefore reproducible.
    """

    raw: dict[str, int] = {asset: 0 for asset in ASSETS}
    best: dict[tuple[str, int], tuple[tuple[int, int], S14.Stream, S14.Occ]] = {}
    collisions = 0
    for stream in streams:
        rec = records[stream.cell]
        for occ in S15.coarse_occs(stream):
            raw[stream.asset] = raw.get(stream.asset, 0) + 1
            stamp = int(rec.lat[occ.bar])
            key = (stream.asset, stamp)
            rank = (int(occ.cell), int(occ.row))
            if key in best:
                collisions += 1
                if rank >= best[key][0]:
                    continue
            best[key] = (rank, stream, occ)
    picked = [(value[1], value[2]) for _key, value in sorted(
        best.items(), key=lambda item: (item[0][0], item[0][1]))]
    deduped = {asset: 0 for asset in ASSETS}
    for stream, _occ in picked:
        deduped[stream.asset] += 1
    return picked, {"coarse_raw": raw, "coarse_deduped": deduped,
                    "dedup_collisions": collisions}


def build_rows(picked: Sequence[tuple[S14.Stream, S14.Occ]],
               records: Sequence[S1.CellRec], cells: Sequence[S8.Cell8],
               mutant: str,
               ) -> tuple[list[CRow], dict[str, np.ndarray], dict[str, int]]:
    """One shard pass: no-wall labels and both-side ATR-stop legs for every row.

    Every coarse row is priced on every (horizon, stop, side), not only the rows
    the model will select, because the matched control selects DIFFERENT rows and
    a control that could not be priced would be a control chosen by the pricer.
    """

    by_cell: dict[int, list[S14.Occ]] = {}
    for stream, occ in picked:
        by_cell.setdefault(stream.cell, []).append(occ)
    cell_by_position = {cell.position: cell for cell in cells}
    counters = {"cells": 0, "cells_missing_shard": 0, "cells_missing_atr": 0,
                "rows_seen": 0, "dropped_label": 0, "dropped_leg": 0,
                "rows": 0}
    by_day: dict[tuple[str, int], list[int]] = {}
    for position in by_cell:
        rec = records[position]
        by_day.setdefault((rec.asset, rec.d8), []).append(position)

    rows: list[CRow] = []
    legs: dict[str, list[np.ndarray]] = {}
    keys = [f"{h}|{q:.2f}|{side}" for h in HORIZONS for q in STOPS
            for side in SIDES]
    fields = ("terminal_usd", "mfe_usd", "mae_usd", "stop_hit", "cause",
              "overshoot_usd", "gap_usd", "exit_ts_ns", "exit_bar")
    buckets: dict[str, dict[str, list[np.ndarray]]] = {
        key: {name: [] for name in fields} for key in keys}

    for (asset, d8) in sorted(by_day):
        shard = M.load_shard(asset, d8)
        try:
            by_text = {cell.text: cell for cell in shard.cells}
            for position in sorted(by_day[(asset, d8)]):
                rec = records[position]
                cell8 = cell_by_position.get(position)
                cell = by_text.get(rec.text)
                if cell is None:
                    counters["cells_missing_shard"] += 1
                    continue
                if cell8 is None or not float(cell8.atr_mid2) > 0.0:
                    counters["cells_missing_atr"] += 1
                    continue
                index = shard.cell_index(cell)
                lat = np.asarray(rec.lat, np.int64)
                mid_lat = np.asarray(rec.mid, np.float64)
                close_ns = int(rec.phase_close_ts_ns)
                occs = sorted(by_cell[position], key=lambda o: (o.bar, o.row))
                bars = np.asarray([occ.bar for occ in occs], np.int64)
                counters["rows_seen"] += len(bars)

                # ---- the no-wall label at every horizon -------------------
                label_ok = np.ones(len(bars), bool)
                absmove: dict[int, np.ndarray] = {}
                abscert: dict[int, np.ndarray] = {}
                cause_label: dict[int, np.ndarray] = {}
                entry_mid2 = np.zeros(len(bars), np.int64)
                cost_usd = np.zeros(len(bars), np.float64)
                spread_usd = np.zeros(len(bars), np.float64)
                sides = np.asarray([occ.side for occ in occs], np.int64)
                for h in HORIZONS:
                    stamps = lat[bars]
                    closes = np.minimum(stamps + int(h) * NANOS, close_ns)
                    grid = nowall_grid(index, stamps, closes)
                    got = np.zeros(len(bars), bool)
                    move = np.zeros(len(bars), np.float64)
                    cert = np.zeros(len(bars), np.float64)
                    cau = np.zeros(len(bars), np.int64)
                    take = grid["input_index"]
                    if len(take):
                        got[take] = True
                        entry = grid["entry_mid2"]
                        cost = grid["frozen_cost_usd"]
                        exit_mid = grid["exit_mid2"]
                        move[take] = np.abs(
                            (exit_mid - entry).astype(np.float64)) * index.factor
                        cert[take] = (sides[take] * (exit_mid - entry)
                                      * index.factor - cost)
                        horizon_bound = (stamps[take] + int(h) * NANOS) <= close_ns
                        cau[take] = np.where(grid["truncated_generation"], 3,
                                             np.where(horizon_bound, 1, 2))
                        entry_mid2[take] = entry
                        cost_usd[take] = cost
                        spread_usd[take] = cost - FEE_USD
                    label_ok &= got
                    absmove[h] = move
                    abscert[h] = np.abs(cert)
                    cause_label[h] = cau

                # ---- both sides, every (horizon, stop) --------------------
                leg_ok = np.ones(len(bars), bool)
                priced: dict[str, Legs] = {}
                for h in HORIZONS:
                    for q in STOPS:
                        for side in SIDES:
                            leg = price_legs(index, lat, mid_lat, bars, side,
                                             h, q, float(cell8.atr_mid2),
                                             close_ns, mutant)
                            priced[f"{h}|{q:.2f}|{side}"] = leg
                            leg_ok &= leg.ok
                keep = np.flatnonzero(label_ok & leg_ok)
                counters["dropped_label"] += int((~label_ok).sum())
                counters["dropped_leg"] += int((label_ok & ~leg_ok).sum())
                if not len(keep):
                    counters["cells"] += 1
                    continue
                for key in keys:
                    leg = priced[key]
                    for name in fields:
                        buckets[key][name].append(getattr(leg, name)[keep])
                for local in keep:
                    occ = occs[int(local)]
                    rows.append(CRow(
                        asset=asset, d8=int(d8), phase=rec.phase,
                        cell=int(position), row=int(occ.row), bar=int(occ.bar),
                        side=int(occ.side),
                        entry_ts_ns=int(lat[int(occ.bar)]),
                        entry_mid2=int(entry_mid2[int(local)]),
                        cost_usd=float(cost_usd[int(local)]),
                        spread_usd=float(spread_usd[int(local)]),
                        atr_mid2=float(cell8.atr_mid2),
                        year=int(d8) // 10000,
                        x=np.asarray(occ.x, np.float64),
                        absmove={h: float(absmove[h][int(local)])
                                 for h in HORIZONS},
                        abscert={h: float(abscert[h][int(local)])
                                 for h in HORIZONS},
                        label_cause={h: CAUSES[int(cause_label[h][int(local)])]
                                     for h in HORIZONS}))
                    counters["rows"] += 1
                counters["cells"] += 1
        finally:
            shard.close()

    packed = {}
    for key in keys:
        for name in fields:
            chunks = buckets[key][name]
            packed[f"{key}|{name}"] = (np.concatenate(chunks) if chunks
                                       else np.zeros(0))
    return rows, packed, counters


# --------------------------------------------------------------------------
# The cell-balanced walk-forward fit and its train-fold cutoff.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Fold:
    """One scored day's fold: the factored gram, reused by every null draw."""

    asset: str
    d8: int
    train: np.ndarray          # (m,) row indices
    score: np.ndarray          # (k,) row indices
    weight: np.ndarray         # (m,) cell-balanced, normalised to sum m
    zt: np.ndarray             # (m, NFEAT) standardised train design
    zs: np.ndarray             # (k, NFEAT) standardised score design
    lhs: np.ndarray            # (NFEAT, NFEAT) Z'WZ + lam I


def _weights(rows: Sequence[CRow], take: np.ndarray) -> np.ndarray:
    """Cell-balanced weights: 1 / rows-in-cell, normalised to sum to n."""

    counts: dict[int, int] = {}
    for index in take:
        counts[rows[int(index)].cell] = counts.get(rows[int(index)].cell, 0) + 1
    raw = np.asarray([1.0 / counts[rows[int(i)].cell] for i in take], np.float64)
    total = float(raw.sum())
    return raw * (len(take) / total) if total > 0 else np.ones(len(take))


def build_folds(rows: Sequence[CRow], explore_days: Mapping[str, Sequence[int]]
                ) -> tuple[list[Fold], dict[str, int]]:
    by_asset: dict[str, dict[int, list[int]]] = {}
    for position, row in enumerate(rows):
        by_asset.setdefault(row.asset, {}).setdefault(row.d8, []).append(position)
    folds: list[Fold] = []
    scored: dict[str, int] = {asset: 0 for asset in ASSETS}
    for asset in ASSETS:
        days = sorted(int(day) for day in explore_days[asset])
        table = by_asset.get(asset, {})
        for index, d8 in enumerate(days):
            today = table.get(d8, [])
            if index < MIN_PRIOR_DAYS_FIT or not today:
                continue
            train = [position for day in S14.fold_days(days, index, "")
                     for position in table.get(day, [])]
            if len(train) < MIN_FIT_ROWS:
                continue
            scored[asset] += 1
            take = np.asarray(train, np.int64)
            look = np.asarray(today, np.int64)
            xt = np.vstack([rows[int(i)].x for i in take])
            xs = np.vstack([rows[int(i)].x for i in look])
            with np.errstate(invalid="ignore"):
                impute = np.nanmean(np.where(np.isfinite(xt), xt, np.nan), axis=0)
            impute = np.where(np.isfinite(impute), impute, 0.0)
            xt = S14._impute(xt, impute)
            xs = S14._impute(xs, impute)
            weight = _weights(rows, take)
            mean = xt.mean(axis=0)
            sd = np.sqrt(np.maximum(xt.var(axis=0), 0.0))
            sd[sd <= 1e-12] = 1.0
            zt = (xt - mean) / sd
            zs = (xs - mean) / sd
            lhs = zt.T @ (zt * weight[:, None]) + RIDGE_LAMBDA * np.eye(NFEAT)
            folds.append(Fold(asset=asset, d8=int(d8), train=take, score=look,
                              weight=weight, zt=zt, zs=zs, lhs=lhs))
    return folds, scored


def fold_scores(folds: Sequence[Fold], target: np.ndarray
                ) -> tuple[np.ndarray, np.ndarray]:
    """Out-of-fold predictions and the TRAIN-FOLD top-decile cutoff per row.

    The cutoff is the 90th percentile of the fold's own IN-FOLD fitted values.
    Sol C.1: learn the cutoff inside the training fold, never off the pooled
    out-of-fold score distribution.
    """

    pred = np.full(len(target), np.nan, np.float64)
    cut = np.full(len(target), np.nan, np.float64)
    for fold in folds:
        y = target[fold.train]
        w = fold.weight
        centre = float((w * y).sum() / w.sum())
        rhs = fold.zt.T @ (w * (y - centre))
        beta = np.linalg.solve(fold.lhs, rhs)
        fitted_in = centre + fold.zt @ beta
        pred[fold.score] = centre + fold.zs @ beta
        cut[fold.score] = float(np.percentile(fitted_in,
                                              100.0 * (1.0 - TOP_DECILE)))
    return pred, cut


def r2_of(actual: np.ndarray, fitted: np.ndarray) -> float | None:
    y = np.asarray(actual, np.float64)
    if len(y) < 2:
        return None
    sst = float(((y - y.mean()) ** 2).sum())
    if sst <= 0.0:
        return None
    return 1.0 - float(((y - np.asarray(fitted, np.float64)) ** 2).sum()) / sst


# --------------------------------------------------------------------------
# M1: magnitude R2 and the synchronized max-R2 day-block permutation null.
# --------------------------------------------------------------------------

def day_blocks(rows: Sequence[CRow]) -> dict[str, dict[int, np.ndarray]]:
    """Row indices per (asset, day), in stream order.  Fixed once per run."""

    out: dict[str, dict[int, list[int]]] = {}
    for position, row in enumerate(rows):
        out.setdefault(row.asset, {}).setdefault(row.d8, []).append(position)
    return {asset: {d8: np.asarray(value, np.int64)
                    for d8, value in table.items()}
            for asset, table in out.items()}


def day_block_permutation(blocks: Mapping[str, Mapping[int, np.ndarray]],
                          n: int, rng: np.random.Generator,
                          dates: Sequence[int]) -> np.ndarray:
    """One synchronized ragged day-block relabelling, shared by all horizons.

    A single permutation of the SHARED EXPLORE date list is drawn per draw.  Each
    asset orders its own days by the permuted rank of that shared list, then its
    label vector is re-sliced onto the unchanged rows in the original day order.
    Blocks are ragged, so the re-slice is the standard contiguous ragged block
    relabelling: day identity is destroyed, within-day label structure is not.

    EVERY row is relabelled, not only the scored ones.  A row on an early day is
    a TRAINING row in some later fold, so leaving its label in place would leave
    part of the fitted signal intact and make the null too easy to beat.
    """

    order = rng.permutation(len(dates))
    rank = {int(date): int(place) for date, place in zip(dates, order)}
    out = np.arange(n, dtype=np.int64)
    for asset in ASSETS:
        table = blocks.get(asset)
        if not table:
            continue
        ordered = sorted(table)
        source = sorted(ordered, key=lambda d8: (rank.get(int(d8), -1), int(d8)))
        pool = np.concatenate([table[d8] for d8 in source])
        target = np.concatenate([table[d8] for d8 in ordered])
        out[target] = pool
    return out


def m1_magnitude(rows: Sequence[CRow], folds: Sequence[Fold],
                 targets: Mapping[str, Mapping[int, np.ndarray]],
                 explore_days: Mapping[str, Sequence[int]],
                 draws: int = R2_DRAWS
                 ) -> tuple[dict[str, object],
                            dict[str, dict[str, np.ndarray]], np.ndarray]:
    n = len(rows)
    asset_of = np.asarray([row.asset for row in rows])
    scored = np.zeros(n, bool)
    for fold in folds:
        scored[fold.score] = True
    report: dict[str, object] = {"draws": draws, "scored_rows": int(scored.sum())}
    oof: dict[str, dict[str, np.ndarray]] = {}
    lines: dict[str, object] = {}
    for channel in ("absmove", "abscert"):
        for h in HORIZONS:
            y = targets[channel][h]
            pred, cut = fold_scores(folds, y)
            oof[f"{channel}|{h}"] = {"pred": pred, "cut": cut}
            for asset in ASSETS:
                mask = scored & (asset_of == asset)
                lines[f"{channel}|{asset}|{h}"] = {
                    "channel": channel, "asset": asset, "horizon_s": int(h),
                    "n": int(mask.sum()),
                    "r2": r2_of(y[mask], pred[mask]),
                    "mean_usd": float(y[mask].mean()) if mask.any() else None,
                    "sd_usd": float(y[mask].std()) if mask.any() else None,
                }
    # ---- the synchronized max-R2 null, primary channel only ---------------
    dates = sorted({row.d8 for row in rows})
    blocks = day_blocks(rows)
    rng = np.random.default_rng(SEED + 20)
    family = [(asset, h) for asset in DECIDING for h in HORIZONS]
    observed = {key: lines[f"absmove|{key[0]}|{key[1]}"]["r2"] for key in family}
    maxima = np.full(draws, -np.inf, np.float64)
    per_line = {key: np.zeros(draws, np.float64) for key in family}
    for draw in range(draws):
        mapping = day_block_permutation(blocks, n, rng, dates)
        best = -np.inf
        for h in HORIZONS:
            shuffled = targets["absmove"][h][mapping]
            pred, _cut = fold_scores(folds, shuffled)
            for asset in DECIDING:
                mask = scored & (asset_of == asset)
                value = r2_of(shuffled[mask], pred[mask])
                value = -9.0 if value is None else float(value)
                per_line[(asset, h)][draw] = value
                best = max(best, value)
        maxima[draw] = best
    for key in family:
        asset, h = key
        stat = observed[key]
        block = lines[f"absmove|{asset}|{h}"]
        if stat is None:
            block.update({"p_max_adjusted": None, "p_raw": None,
                          "null_p95": None})
            continue
        block.update({
            "p_max_adjusted": float((1 + int((maxima >= float(stat)).sum()))
                                    / (draws + 1)),
            "p_raw": float((1 + int((per_line[key] >= float(stat)).sum()))
                           / (draws + 1)),
            "null_mean": float(per_line[key].mean()),
            "null_p95": float(np.percentile(per_line[key], 95.0)),
        })
    report["lines"] = lines
    report["null_max_p95"] = float(np.percentile(maxima, 95.0))
    report["null_max_mean"] = float(maxima.mean())
    report["family"] = [f"{a}|{h}" for a, h in family]
    return report, oof, scored


# --------------------------------------------------------------------------
# M2/M3: selection, both-side excursions, exit causes and the coin.
# --------------------------------------------------------------------------

def selection_mask(oof: Mapping[str, Mapping[str, np.ndarray]], h: int,
                   scored: np.ndarray) -> np.ndarray:
    block = oof[f"absmove|{h}"]
    pred = block["pred"]
    cut = block["cut"]
    ok = scored & np.isfinite(pred) & np.isfinite(cut)
    return ok & (pred >= cut)


def exit_cause_table(rows: Sequence[CRow], legs: Mapping[str, np.ndarray],
                     selected: Mapping[int, np.ndarray]) -> dict[str, object]:
    out: dict[str, object] = {}
    asset_of = np.asarray([row.asset for row in rows])
    for asset in ASSETS:
        for h in HORIZONS:
            for q in STOPS:
                mask = selected[h] & (asset_of == asset)
                counts = {cause: 0 for cause in CAUSES}
                total = 0
                for side in SIDES:
                    cause = legs[f"{h}|{q:.2f}|{side}|cause"][mask]
                    for index, name in enumerate(CAUSES):
                        counts[name] += int((cause == index).sum())
                    total += int(len(cause))
                out[f"{asset}|{h}|{q:.2f}"] = {
                    "asset": asset, "horizon_s": int(h), "stop_q": float(q),
                    "legs": total,
                    "counts": counts,
                    "fractions": {name: (counts[name] / total if total else None)
                                  for name in CAUSES}}
    return out


def coin_matrix(rows: Sequence[CRow], legs: Mapping[str, np.ndarray],
                spread_double: bool = False) -> dict[str, np.ndarray]:
    """COIN = 0.5 * (long + short) at the same timestamp, per (h, q).

    The identity is exact by construction and the selftest holds it to zero
    tolerance.  The exit-spread stress charges the spread component of the
    frozen entry cost a SECOND time on every STOP exit, on both legs, before the
    coin is taken.
    """

    spread = np.asarray([row.spread_usd for row in rows], np.float64)
    out: dict[str, np.ndarray] = {}
    for h in HORIZONS:
        for q in STOPS:
            legvals = {}
            for side in SIDES:
                value = np.array(legs[f"{h}|{q:.2f}|{side}|terminal_usd"],
                                 np.float64, copy=True)
                if spread_double:
                    stop = legs[f"{h}|{q:.2f}|{side}|stop_hit"].astype(bool)
                    value = value - np.where(stop, spread, 0.0)
                legvals[side] = value
                out[f"{h}|{q:.2f}|{side}"] = value
            out[f"{h}|{q:.2f}|coin"] = 0.5 * (legvals[1] + legvals[-1])
    return out


def m3_coin(rows: Sequence[CRow], legs: Mapping[str, np.ndarray],
            coin: Mapping[str, np.ndarray], selected: Mapping[int, np.ndarray]
            ) -> dict[str, object]:
    asset_of = np.asarray([row.asset for row in rows])
    factor = {asset: 0.5e-9 * float(M.ASSET_MULTIPLIER[asset])
              for asset in ASSETS}
    atr = np.asarray([row.atr_mid2 for row in rows], np.float64)
    cost = np.asarray([row.cost_usd for row in rows], np.float64)
    out: dict[str, object] = {}
    for asset in ASSETS:
        for h in HORIZONS:
            for q in STOPS:
                mask = selected[h] & (asset_of == asset)
                n = int(mask.sum())
                if not n:
                    out[f"{asset}|{h}|{q:.2f}"] = {"n": 0}
                    continue
                long_stop = legs[f"{h}|{q:.2f}|1|stop_hit"][mask].astype(bool)
                short_stop = legs[f"{h}|{q:.2f}|-1|stop_hit"][mask].astype(bool)
                long_ts = legs[f"{h}|{q:.2f}|1|exit_ts_ns"][mask]
                short_ts = legs[f"{h}|{q:.2f}|-1|exit_ts_ns"][mask]
                chop = long_stop & short_stop
                first_long = chop & (long_ts < short_ts)
                first_short = chop & (short_ts < long_ts)
                distance_usd = q * atr[mask] * factor[asset]
                overshoot = (legs[f"{h}|{q:.2f}|1|overshoot_usd"][mask]
                             + legs[f"{h}|{q:.2f}|-1|overshoot_usd"][mask])
                gap = (legs[f"{h}|{q:.2f}|1|gap_usd"][mask]
                       + legs[f"{h}|{q:.2f}|-1|gap_usd"][mask])
                value = coin[f"{h}|{q:.2f}|coin"][mask]
                out[f"{asset}|{h}|{q:.2f}"] = {
                    "asset": asset, "horizon_s": int(h), "stop_q": float(q),
                    "n": n,
                    "coin_mean_usd": float(value.mean()),
                    "coin_sd_usd": float(value.std()),
                    "coin_total_usd": float(value.sum()),
                    "long_mean_usd": float(coin[f"{h}|{q:.2f}|1"][mask].mean()),
                    "short_mean_usd": float(coin[f"{h}|{q:.2f}|-1"][mask].mean()),
                    "chop_fraction": float(chop.mean()),
                    "first_passage_long": int(first_long.sum()),
                    "first_passage_short": int(first_short.sum()),
                    "first_passage_tie": int((chop & (long_ts == short_ts)).sum()),
                    "stop_distance_usd": float(distance_usd.mean()),
                    "cost_over_stop": float((cost[mask] / np.maximum(
                        distance_usd, 1e-12)).mean()),
                    "overshoot_total_usd": float(overshoot.sum()),
                    "overshoot_mean_usd": float(overshoot.mean()),
                    "gap_at_stop_mean_usd": float(gap.mean()),
                    "mfe_mean_usd": float(
                        0.5 * (legs[f"{h}|{q:.2f}|1|mfe_usd"][mask]
                               + legs[f"{h}|{q:.2f}|-1|mfe_usd"][mask]).mean()),
                    "mae_mean_usd": float(
                        0.5 * (legs[f"{h}|{q:.2f}|1|mae_usd"][mask]
                               + legs[f"{h}|{q:.2f}|-1|mae_usd"][mask]).mean()),
                }
    return out


def excursion_separation(rows: Sequence[CRow], legs: Mapping[str, np.ndarray],
                         selected: Mapping[int, np.ndarray],
                         scored: np.ndarray) -> dict[str, object]:
    """Selected versus unselected MFE and MAE: the MAGNITUDE-ONLY evidence."""

    asset_of = np.asarray([row.asset for row in rows])
    out: dict[str, object] = {}
    for asset in ASSETS:
        for h in HORIZONS:
            pick = selected[h] & (asset_of == asset)
            rest = scored & ~selected[h] & (asset_of == asset)
            q = STOPS[-1]
            mfe = 0.5 * (legs[f"{h}|{q:.2f}|1|mfe_usd"]
                         + legs[f"{h}|{q:.2f}|-1|mfe_usd"])
            mae = 0.5 * (legs[f"{h}|{q:.2f}|1|mae_usd"]
                         + legs[f"{h}|{q:.2f}|-1|mae_usd"])
            out[f"{asset}|{h}"] = {
                "selected_n": int(pick.sum()), "rest_n": int(rest.sum()),
                "selected_mfe_usd": float(mfe[pick].mean()) if pick.any() else None,
                "rest_mfe_usd": float(mfe[rest].mean()) if rest.any() else None,
                "selected_mae_usd": float(mae[pick].mean()) if pick.any() else None,
                "rest_mae_usd": float(mae[rest].mean()) if rest.any() else None,
                "separated": bool(pick.any() and rest.any()
                                  and float(mfe[pick].mean())
                                  > float(mfe[rest].mean())),
            }
    return out


# --------------------------------------------------------------------------
# M4: the count-matched control and the shared-date-sign studentized maxT.
# --------------------------------------------------------------------------

def control_days(rows: Sequence[CRow], oof: Mapping[str, Mapping[str, np.ndarray]],
                 coin: Mapping[str, np.ndarray], scored: np.ndarray,
                 draws: int = CONTROL_DRAWS
                 ) -> tuple[dict[str, np.ndarray], list[tuple[str, int]],
                            dict[str, object]]:
    """Permute magnitude scores inside (asset, date, phase); same permutation
    for every horizon and every stop.

    The permutation preserves each cell's score MULTISET, and the top-decile
    cutoff is a per-(asset, day) constant, so the number of selected rows inside
    every cell is invariant: the control is count-matched by construction rather
    than by a matching step that could be tuned.
    """

    n = len(rows)
    group = np.zeros(n, np.int64)
    names: dict[tuple[str, int, str], int] = {}
    for position, row in enumerate(rows):
        key = (row.asset, row.d8, row.phase)
        if key not in names:
            names[key] = len(names)
        group[position] = names[key]
    blocks = sorted({(rows[i].asset, rows[i].d8) for i in range(n) if scored[i]})
    block_id = {key: place for place, key in enumerate(blocks)}
    day_of = np.asarray([block_id.get((row.asset, row.d8), -1) for row in rows],
                        np.int64)

    keys = [(h, q) for h in HORIZONS for q in STOPS]
    coin_matrix_all = np.column_stack([coin[f"{h}|{q:.2f}|coin"] for h, q in keys])
    accumulator = np.zeros((len(blocks), len(keys)), np.float64)

    base_order = np.argsort(group, kind="stable")
    rng = np.random.default_rng(SEED + 40)
    # The per-horizon selection thresholds are per row; the permutation moves
    # SCORES, never cutoffs, so the cutoff array is indexed by the row it lands on.
    preds = {h: oof[f"absmove|{h}"]["pred"] for h in HORIZONS}
    cuts = {h: oof[f"absmove|{h}"]["cut"] for h in HORIZONS}
    finite = {h: scored & np.isfinite(preds[h]) & np.isfinite(cuts[h])
              for h in HORIZONS}
    for _draw in range(draws):
        order = np.lexsort((rng.random(n), group))
        shuffled = {}
        for h in HORIZONS:
            moved = np.empty(n, np.float64)
            moved[base_order] = preds[h][order]
            shuffled[h] = moved
        for column, (h, q) in enumerate(keys):
            pick = finite[h] & (shuffled[h] >= cuts[h])
            taken = np.flatnonzero(pick & (day_of >= 0))
            if not len(taken):
                continue
            np.add.at(accumulator[:, column], day_of[taken],
                      coin_matrix_all[taken, column])
    control = accumulator / float(draws)
    out = {f"{h}|{q:.2f}": control[:, column]
           for column, (h, q) in enumerate(keys)}
    return out, blocks, {"draws": draws, "groups": len(names),
                         "blocks": len(blocks)}


def selected_days(rows: Sequence[CRow], coin: Mapping[str, np.ndarray],
                  selected: Mapping[int, np.ndarray],
                  blocks: Sequence[tuple[str, int]]) -> dict[str, np.ndarray]:
    block_id = {key: place for place, key in enumerate(blocks)}
    day_of = np.asarray([block_id.get((row.asset, row.d8), -1) for row in rows],
                        np.int64)
    out: dict[str, np.ndarray] = {}
    for h in HORIZONS:
        for q in STOPS:
            sums = np.zeros(len(blocks), np.float64)
            taken = np.flatnonzero(selected[h] & (day_of >= 0))
            if len(taken):
                np.add.at(sums, day_of[taken],
                          coin[f"{h}|{q:.2f}|coin"][taken])
            out[f"{h}|{q:.2f}"] = sums
    return out


def maxt_inference(blocks: Sequence[tuple[str, int]],
                   selected: Mapping[str, np.ndarray],
                   control: Mapping[str, np.ndarray],
                   draws: int = SIGN_DRAWS) -> dict[str, object]:
    """Sol section A, steps 2-6: shared date signs, studentized, max over 32.

    One paired difference per EXPLORE calendar date and line; dates with no
    difference contribute zero.  Each observed mean is studentized with its
    asset-day standard error.  Every draw applies ONE Rademacher sign per
    calendar date to every asset and horizon and stop, so cross-line dependence
    is preserved rather than destroyed by independent signs.
    """

    dates = sorted({int(d8) for _asset, d8 in blocks})
    date_of = np.asarray([dates.index(int(d8)) for _asset, d8 in blocks], np.int64)
    asset_of = np.asarray([asset for asset, _d8 in blocks])
    family = [(asset, h, q) for asset in DECIDING for h in HORIZONS
              for q in STOPS]
    report = [(asset, h, q) for asset in ASSETS for h in HORIZONS for q in STOPS]

    vectors: dict[tuple[str, int, float], np.ndarray] = {}
    for asset, h, q in report:
        mask = asset_of == asset
        diff = selected[f"{h}|{q:.2f}"][mask] - control[f"{h}|{q:.2f}"][mask]
        full = np.zeros(len(dates), np.float64)
        np.add.at(full, date_of[mask], diff)
        vectors[(asset, h, q)] = full

    stats: dict[tuple[str, int, float], tuple[float, float, float, int]] = {}
    for key in report:
        values = vectors[key]
        mean = float(values.mean()) if len(values) else 0.0
        se = (float(values.std(ddof=1) / math.sqrt(len(values)))
              if len(values) > 1 else 0.0)
        stats[key] = (mean, se, (mean / se) if se > 0 else 0.0, len(values))

    rng = np.random.default_rng(SEED + 60)
    stacked = np.column_stack([vectors[key] for key in family])
    ses = np.asarray([stats[key][1] for key in family], np.float64)
    ses = np.where(ses > 0, ses, np.inf)
    maxima = np.zeros(draws, np.float64)
    step = 500
    done = 0
    while done < draws:
        take = min(step, draws - done)
        signs = rng.choice(np.asarray([-1.0, 1.0]), size=(take, len(dates)))
        means = (signs @ stacked) / float(len(dates))
        sds = np.sqrt(((signs[:, :, None] * stacked[None, :, :]
                        - means[:, None, :]) ** 2).sum(axis=1)
                      / max(len(dates) - 1, 1))
        se_draw = sds / math.sqrt(len(dates))
        with np.errstate(divide="ignore", invalid="ignore"):
            t = np.where(se_draw > 0, means / se_draw, 0.0)
        maxima[done:done + take] = t.max(axis=1)
        done += take
    c95 = float(np.percentile(maxima, 95.0))

    lines: dict[str, object] = {}
    for key in report:
        asset, h, q = key
        mean, se, t, blocks_n = stats[key]
        eligible = asset in DECIDING
        p = (float((1 + int((maxima >= t).sum())) / (draws + 1))
             if eligible else None)
        lines[f"{asset}|{h}|{q:.2f}"] = {
            "asset": asset, "horizon_s": int(h), "stop_q": float(q),
            "eligible": eligible, "dates": int(blocks_n),
            "delta_usd_per_date": mean, "se_usd": se, "t": t,
            "p_max_adjusted": p,
            "upper95_simultaneous_usd": mean + c95 * se,
            "lower95_simultaneous_usd": mean - c95 * se,
        }
    return {"draws": draws, "dates": len(dates), "c95": c95,
            "family": [f"{a}|{h}|{q:.2f}" for a, h, q in family],
            "by_line": lines}


# --------------------------------------------------------------------------
# M5: the frozen hash side and the chronological one-position replay.
# --------------------------------------------------------------------------

def hash_side(asset: str, d8: int, entry_ts_ns: int, seed: int = SEED) -> int:
    """A frozen, reproducible coin for the executable sensitivity."""

    text = f"{asset}|{int(d8)}|{int(entry_ts_ns)}|{int(seed)}"
    digest = hashlib.sha256(text.encode()).hexdigest()
    return 1 if int(digest[:16], 16) % 2 == 0 else -1


@dataclass(slots=True)
class Trade:
    asset: str
    d8: int
    cell: int
    row: int
    side: int
    entry_ts_ns: int
    exit_ts_ns: int
    entry_bar: int
    exit_bar: int
    pnl_usd: float


def replay(rows: Sequence[CRow], legs: Mapping[str, np.ndarray],
           mask: np.ndarray, h: int, q: float, sides: Mapping[int, int],
           overrides: Mapping[int, float] | None = None,
           ) -> dict[str, object]:
    """Sol section B, exactly: chronology, occupancy, and a portfolio-date cap.

    Events are sorted by stamp with the frozen tie break (stamp, asset, cell,
    row, side) and EXITS are processed BEFORE ENTRIES at an equal stamp, so a
    seat freed at t is available at t.  A candidate is seated only when its asset
    is flat.  The cap is 12 seated entries per PORTFOLIO date, taken dynamically
    in chronological order - never four reserved per asset.
    """

    picks = np.flatnonzero(mask)
    events: list[tuple[int, int, str, int, int, int]] = []
    for position in picks:
        row = rows[int(position)]
        events.append((int(row.entry_ts_ns), 1, row.asset, int(row.cell),
                       int(row.row), int(position)))
    events.sort(key=lambda item: (item[0], item[1], item[2], item[3], item[4]))

    occupied: dict[str, int] = {}
    seated_by_date: dict[int, int] = {}
    trades: list[Trade] = []
    rejected_occupancy = 0
    rejected_cap = 0
    for stamp, _kind, asset, _cell, _row, position in events:
        row = rows[int(position)]
        side = int(sides[int(position)])
        exit_ts = int(legs[f"{h}|{q:.2f}|{side}|exit_ts_ns"][position])
        # Exits are processed before entries at an equal stamp: a position whose
        # exit stamp is <= this entry stamp has already freed the seat.
        if asset in occupied and occupied[asset] > stamp:
            rejected_occupancy += 1
            continue
        if seated_by_date.get(int(row.d8), 0) >= PORTFOLIO_CAP:
            rejected_cap += 1
            continue
        pnl = (float(overrides[int(position)]) if overrides is not None
               and int(position) in overrides
               else float(legs[f"{h}|{q:.2f}|{side}|terminal_usd"][position]))
        occupied[asset] = exit_ts
        seated_by_date[int(row.d8)] = seated_by_date.get(int(row.d8), 0) + 1
        trades.append(Trade(
            asset=asset, d8=int(row.d8), cell=int(row.cell), row=int(row.row),
            side=side, entry_ts_ns=int(stamp), exit_ts_ns=exit_ts,
            entry_bar=int(row.bar),
            exit_bar=int(legs[f"{h}|{q:.2f}|{side}|exit_bar"][position]),
            pnl_usd=pnl))
    return {"trades": trades, "rejected_occupancy": rejected_occupancy,
            "rejected_cap": rejected_cap, "seated": len(trades)}


def replay_cash(trades: Sequence[Trade], explore_days: Mapping[str, Sequence[int]]
                ) -> dict[str, object]:
    """Per-asset usd/day over EVERY split date, zero-entry dates carried."""

    out: dict[str, object] = {}
    for asset in ASSETS:
        days = sorted(int(day) for day in explore_days[asset])
        sums = {day: 0.0 for day in days}
        seats = {day: 0 for day in days}
        for trade in trades:
            if trade.asset != asset or int(trade.d8) not in sums:
                continue
            sums[int(trade.d8)] += float(trade.pnl_usd)
            seats[int(trade.d8)] += 1
        series = [sums[day] for day in days]
        mean, se = _mean_se(series)
        counts = [seats[day] for day in days]
        out[asset] = {
            "days": len(days), "trades": int(sum(counts)),
            "usd_per_day": mean, "se_usd": se,
            "mean_minus_2se_usd": (None if mean is None or se is None
                                   else mean - 2.0 * se),
            "rung_usd": DAY_RUNG_USD[asset],
            "clears_rung": (None if mean is None or se is None
                            else bool(mean - 2.0 * se >= DAY_RUNG_USD[asset])),
            "total_usd": float(sum(series)),
            "seats_mean": float(np.mean(counts)) if counts else 0.0,
            "seats_max": int(max(counts)) if counts else 0,
            "zero_entry_fraction": (float(np.mean([c == 0 for c in counts]))
                                    if counts else None),
            "seat_histogram": {str(k): int(sum(1 for c in counts if c == k))
                               for k in range(0, (max(counts) if counts else 0) + 1)},
        }
    dates = sorted({int(trade.d8) for trade in trades})
    per_date = {date: 0 for date in dates}
    for trade in trades:
        per_date[int(trade.d8)] += 1
    out["_portfolio"] = {
        "dates_with_entries": len(dates),
        "portfolio_seats_mean": (float(np.mean(list(per_date.values())))
                                 if per_date else 0.0),
        "portfolio_seats_max": int(max(per_date.values())) if per_date else 0,
        "at_cap_dates": int(sum(1 for v in per_date.values()
                                if v >= PORTFOLIO_CAP)),
    }
    return out


def mdd_ledgers(trades: Sequence[Trade], rows: Sequence[CRow],
                mid_by_cell: Mapping[int, np.ndarray],
                lat_by_cell: Mapping[int, np.ndarray],
                entry_by_position: Mapping[tuple[int, int, int], tuple[int, float]],
                explore_days: Mapping[str, Sequence[int]]) -> dict[str, object]:
    """Sol section D: four ledgers, cumulative cash from zero, peak minus equity."""

    from engine.entry_v2.replay import _drawdown

    out: dict[str, object] = {}
    ordered = sorted(trades, key=lambda t: (t.entry_ts_ns, t.exit_ts_ns,
                                            t.cell, t.row, t.side))
    for asset in ASSETS:
        mine = [t for t in ordered if t.asset == asset]
        days = sorted(int(day) for day in explore_days[asset])
        sums = {day: 0.0 for day in days}
        for trade in mine:
            if int(trade.d8) in sums:
                sums[int(trade.d8)] += float(trade.pnl_usd)
        out[f"{asset}|trade"] = float(_drawdown([t.pnl_usd for t in mine]))
        out[f"{asset}|day"] = float(_drawdown([sums[day] for day in days]))
    out["PORTFOLIO|trade"] = float(_drawdown([t.pnl_usd for t in ordered]))
    all_days = sorted({int(day) for asset in ASSETS
                       for day in explore_days[asset]})
    port = {day: 0.0 for day in all_days}
    for trade in ordered:
        if int(trade.d8) in port:
            port[int(trade.d8)] += float(trade.pnl_usd)
    out["PORTFOLIO|day"] = float(_drawdown([port[day] for day in all_days]))

    # ---- event-time portfolio equity, open positions marked at raw mid ----
    marks: list[tuple[int, int, float, bool]] = []
    factor = {asset: 0.5e-9 * float(M.ASSET_MULTIPLIER[asset]) for asset in ASSETS}
    for number, trade in enumerate(ordered):
        key = (trade.cell, trade.entry_bar, trade.side)
        entry_mid2, cost = entry_by_position[key]
        lat = lat_by_cell[trade.cell]
        mid = mid_by_cell[trade.cell]
        last = int(trade.exit_bar)
        for bar in range(int(trade.entry_bar) + 1,
                         max(last, int(trade.entry_bar) + 1)):
            if bar >= len(lat) or bar >= len(mid):
                break
            value = (trade.side * (float(mid[bar]) - float(entry_mid2))
                     * factor[trade.asset] - cost)
            marks.append((int(lat[bar]), number, value, False))
        marks.append((int(trade.exit_ts_ns), number, float(trade.pnl_usd), True))
        marks.append((int(trade.entry_ts_ns), number, -cost, False))
    marks.sort(key=lambda item: (item[0], 1 if item[3] else 0, item[1]))
    realized = 0.0
    open_marks: dict[int, float] = {}
    peak = 0.0
    worst = 0.0
    for _stamp, number, value, closing in marks:
        if closing:
            open_marks.pop(number, None)
            realized += value
        else:
            open_marks[number] = value
        equity = realized + sum(open_marks.values())
        peak = max(peak, equity)
        worst = max(worst, peak - equity)
    out["PORTFOLIO|event"] = float(worst)
    # BINDING is the deciding assets' own ledgers plus every portfolio ledger.
    # HG's per-asset ledgers are reported but not binding, because HG is
    # report-only for this two-asset milestone (Sol C).  The portfolio ledgers
    # DO include HG: the cap is a portfolio law, so a per-asset-only drawdown
    # would be incomplete (Sol D.3).
    binding = ([f"{asset}|{grain}" for asset in DECIDING
                for grain in ("trade", "day")]
               + ["PORTFOLIO|trade", "PORTFOLIO|day", "PORTFOLIO|event"])
    out["binding_ledgers"] = binding
    out["max_binding_usd"] = float(max([out[key] for key in binding] or [0.0]))
    out["max_all_usd"] = float(max(
        [value for key, value in out.items()
         if isinstance(value, float) and key != "max_binding_usd"] or [0.0]))
    out["clears"] = bool(out["max_binding_usd"] < MDD_CEILING)
    return out


# --------------------------------------------------------------------------
# M7: the two stresses and the stability tables.
# --------------------------------------------------------------------------

def adversarial_overrides(rows: Sequence[CRow], legs: Mapping[str, np.ndarray],
                          mask: np.ndarray, h: int, q: float,
                          sides: Mapping[int, int], rate: float = STRESS_RATE
                          ) -> dict[int, float]:
    """The standing 2 percent adversarial replay, in this route's form.

    The worst 2 percent per asset - the entries with the LARGEST damage from
    being handed their worse side - take the worse of their two side outcomes.
    Damage is measured against the hash side actually seated, so the stress is
    adversarial against the policy that is being tested and not against a
    strawman.
    """

    out: dict[int, float] = {}
    for asset in ASSETS:
        picks = [int(p) for p in np.flatnonzero(mask)
                 if rows[int(p)].asset == asset]
        if not picks:
            continue
        target = int(round(rate * len(picks)))
        if target <= 0:
            continue
        damages = []
        for position in picks:
            side = int(sides[position])
            taken = float(legs[f"{h}|{q:.2f}|{side}|terminal_usd"][position])
            worse = min(float(legs[f"{h}|{q:.2f}|1|terminal_usd"][position]),
                        float(legs[f"{h}|{q:.2f}|-1|terminal_usd"][position]))
            damages.append((taken - worse, position, worse))
        damages.sort(key=lambda item: (-item[0], item[1]))
        for _damage, position, worse in damages[:target]:
            out[position] = worse
    return out


def stability(rows: Sequence[CRow], coin: Mapping[str, np.ndarray],
              selected: Mapping[int, np.ndarray]) -> dict[str, object]:
    asset_of = np.asarray([row.asset for row in rows])
    year_of = np.asarray([row.year for row in rows], np.int64)
    phase_of = np.asarray([row.phase for row in rows])
    out: dict[str, object] = {}
    for asset in ASSETS:
        for h in HORIZONS:
            for q in STOPS:
                base = selected[h] & (asset_of == asset)
                value = coin[f"{h}|{q:.2f}|coin"]
                years = {}
                present = (sorted({int(y) for y in year_of[base]})
                           if base.any() else [])
                for year in present:
                    mask = base & (year_of == year)
                    years[str(year)] = {"n": int(mask.sum()),
                                        "coin_mean_usd": float(value[mask].mean())}
                phases = {}
                for phase in PHASES:
                    mask = base & (phase_of == phase)
                    if mask.any():
                        phases[phase] = {"n": int(mask.sum()),
                                         "coin_mean_usd": float(value[mask].mean())}
                out[f"{asset}|{h}|{q:.2f}"] = {"by_year": years, "by_phase": phases}
    return out


# --------------------------------------------------------------------------
# The pre-registered decision table.
# --------------------------------------------------------------------------

def _neighbours(h: int, q: float) -> list[tuple[int, float]]:
    """The nearest INWARD neighbours: one horizon shorter, one stop tighter."""

    out: list[tuple[int, float]] = []
    hi = HORIZONS.index(int(h))
    qi = STOPS.index(float(q))
    if hi > 0:
        out.append((HORIZONS[hi - 1], float(q)))
    if qi > 0:
        out.append((int(h), STOPS[qi - 1]))
    return out


def decide(m1: Mapping[str, object], coin: Mapping[str, object],
           control: Mapping[str, object], replays: Mapping[str, object],
           mdds: Mapping[str, object], stresses: Mapping[str, object],
           separation: Mapping[str, object]) -> dict[str, object]:
    table: dict[str, object] = {}
    per_asset: dict[str, object] = {}
    for asset in ASSETS:
        rows: dict[str, object] = {}
        best_line = None
        for h in HORIZONS:
            r2 = m1["lines"][f"absmove|{asset}|{h}"]["r2"]
            p_r2 = m1["lines"][f"absmove|{asset}|{h}"].get("p_max_adjusted")
            for q in STOPS:
                key = f"{asset}|{h}|{q:.2f}"
                line = control["by_line"][key]
                cash = replays[f"{h}|{q:.2f}"]["cash"][asset]
                mdd = mdds[f"{h}|{q:.2f}"]
                adv = stresses[f"{h}|{q:.2f}"]["adversarial"]
                spr = stresses[f"{h}|{q:.2f}"]["exit_spread"]
                r2_ok = bool(r2 is not None and r2 >= R2_FLOOR
                             and p_r2 is not None and p_r2 <= P_CEILING)
                coin_ok = bool(line["delta_usd_per_date"] > 0.0
                               and line["p_max_adjusted"] is not None
                               and line["p_max_adjusted"] <= P_CEILING)
                cash_ok = bool(cash["clears_rung"])
                mdd_ok = bool(mdd["clears"])
                stress_ok = bool(adv["mdd"]["clears"] and spr["mdd"]["clears"]
                                 and adv["cash"][asset]["clears_rung"]
                                 and spr["cash"][asset]["clears_rung"])
                neighbours_ok = True
                for nh, nq in _neighbours(h, q):
                    nline = control["by_line"][f"{asset}|{nh}|{nq:.2f}"]
                    ncash = replays[f"{nh}|{nq:.2f}"]["cash"][asset]
                    nmdd = mdds[f"{nh}|{nq:.2f}"]
                    if not (nline["delta_usd_per_date"] > 0.0
                            and (ncash["usd_per_day"] or 0.0) > 0.0
                            and nmdd["clears"]):
                        neighbours_ok = False
                rows[f"{h}|{q:.2f}"] = {
                    "horizon_s": int(h), "stop_q": float(q),
                    "r2": r2, "p_r2": p_r2, "r2_ok": r2_ok,
                    "coin_delta_usd_per_date": line["delta_usd_per_date"],
                    "coin_p": line["p_max_adjusted"],
                    "coin_upper95": line["upper95_simultaneous_usd"],
                    "coin_ok": coin_ok,
                    "coin_mean_usd": coin[f"{asset}|{h}|{q:.2f}"].get("coin_mean_usd"),
                    "replay_usd_day": cash["usd_per_day"],
                    "replay_minus_2se": cash["mean_minus_2se_usd"],
                    "rung_usd": DAY_RUNG_USD[asset],
                    "cash_ok": cash_ok,
                    "mdd_max_usd": mdd["max_binding_usd"], "mdd_ok": mdd_ok,
                    "stress_ok": stress_ok, "neighbours_ok": neighbours_ok,
                    "all_ok": bool(r2_ok and coin_ok and cash_ok and mdd_ok
                                   and stress_ok and neighbours_ok),
                }
                if rows[f"{h}|{q:.2f}"]["all_ok"]:
                    best_line = f"{h}|{q:.2f}"
        any_r2 = any(rows[key]["r2_ok"] for key in rows)
        sep = any(separation[f"{asset}|{h}"]["separated"] for h in HORIZONS)
        per_asset[asset] = {"rows": rows, "any_r2_gate": any_r2,
                            "excursion_separated": sep,
                            "surviving_line": best_line}

    deciding_survive = all(per_asset[a]["surviving_line"] for a in DECIDING)
    deciding_r2 = all(per_asset[a]["any_r2_gate"] for a in DECIDING)
    deciding_sep = all(per_asset[a]["excursion_separated"] for a in DECIDING)
    every_line_dead = True
    for asset in DECIDING:
        for key, row in per_asset[asset]["rows"].items():
            coin_dead = bool(row["coin_upper95"] is not None
                             and row["coin_upper95"] <= 0.0)
            cash_upper = replays[key]["cash"][asset]
            upper = (None if cash_upper["usd_per_day"] is None
                     else cash_upper["usd_per_day"] + 2.0 * (cash_upper["se_usd"] or 0.0))
            cash_dead = bool(upper is not None and upper < DAY_RUNG_USD[asset])
            if not (coin_dead or cash_dead):
                every_line_dead = False
    no_r2 = any(not per_asset[a]["any_r2_gate"] for a in DECIDING)

    # Precedence.  ASYM-KILL's second disjunct (every registered line dead) and
    # MAGNITUDE-ONLY describe overlapping facts: both can hold when the
    # predictive gate passes and every line's cash is dead.  MAGNITUDE-ONLY is
    # the strictly more specific description - it additionally requires the
    # excursion separation and it already CLOSES this ATR-stop shape - so it
    # wins the letter, and ``also_asym_kill`` keeps the route-level kill on the
    # record rather than letting the more informative letter soften it.
    asym_kill = bool(no_r2 or every_line_dead)
    if deciding_survive:
        verdict = "ASYM-SURVIVES-EXPLORE"
    elif deciding_r2 and deciding_sep and not no_r2:
        verdict = "MAGNITUDE-ONLY"
    elif asym_kill:
        verdict = "ASYM-KILL"
    else:
        verdict = "UNRESOLVED"

    best = {}
    for asset in ASSETS:
        rows = per_asset[asset]["rows"]
        pick = max(rows, key=lambda key: (rows[key]["replay_minus_2se"]
                                          if rows[key]["replay_minus_2se"] is not None
                                          else -9e9))
        best[asset] = {"line": pick, **rows[pick],
                       "ratio_over_rung": (
                           None if rows[pick]["replay_minus_2se"] is None
                           else rows[pick]["replay_minus_2se"] / DAY_RUNG_USD[asset])}
    table["by_asset"] = per_asset
    table["best_by_asset"] = best
    table["verdict"] = verdict
    table["also_asym_kill"] = asym_kill
    table["gates"] = {"deciding_r2": deciding_r2, "deciding_sep": deciding_sep,
                      "deciding_survive": deciding_survive,
                      "every_line_dead": every_line_dead, "no_r2": no_r2,
                      "asym_kill_disjunct": asym_kill}
    return table


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


def print_gate(report: Mapping[str, object]) -> None:
    gate = report["stream_gate"]
    print("\nGATE - SWEEP-9 ROW PLANE AND SWEEP-14 SCORING DAYS")
    print(f"  rows              banked {gate['banked_rows']}   "
          f"live {gate['live_rows']}")
    for asset in ASSETS:
        print(f"  certifiable {asset.ljust(4)}  banked "
              f"{gate['banked_certifiable'][asset]}   live "
              f"{gate['live_certifiable'][asset]}")
    for name in sorted(gate["banked_counters"]):
        print(f"  {name.ljust(18)} banked {gate['banked_counters'][name]}   "
              f"live {gate['live_counters'][name]}")
    days = report["scoring_days"]
    print(f"  scoring days      banked {REPRO_SCORING_DAYS}   live "
          f"{days['live']}   match {days['matches']}")
    print(f"  gate matches: {gate['matches'] and days['matches']}")
    universe = report["universe"]
    print("\nUNIVERSE - SWEEP-15 COARSE POST-RESET, DEDUPED")
    print("  asset      coarse   s15band     deduped   priced")
    for asset in ASSETS:
        print("  " + asset.ljust(8)
              + _n(universe["coarse_raw"][asset], 9)
              + _n(universe["s15_scoring_banked"][asset], 10)
              + _n(universe["coarse_deduped"][asset], 12)
              + _n(universe["priced"][asset], 9))
    print(f"  scoring-scope coarse rows live "
          f"{universe['s15_scoring_live']} vs banked "
          f"{universe['s15_scoring_banked']}  match "
          f"{universe['s15_scoring_matches']}")
    print(f"  dedup collisions {universe['dedup_collisions']}; "
          f"row counters {report['row_counters']}")


def print_m1(m1: Mapping[str, object]) -> None:
    print("\nM1 - MAGNITUDE R2, NO-WALL ABSOLUTE TERMINAL MOVE, CELL-BALANCED")
    print("  channel   asset       1800      3600      5400      7200")
    for channel in ("absmove", "abscert"):
        for asset in ASSETS:
            cells = "".join(_n(m1["lines"][f"{channel}|{asset}|{h}"]["r2"], 10, 4)
                            for h in HORIZONS)
            print(f"  {channel.ljust(9)} {asset.ljust(5)}" + cells)
    print(f"\n  MAX-R2 DAY-BLOCK PERMUTATION NULL, {m1['draws']} draws, "
          f"synchronized across horizons, family "
          f"{len(m1['family'])} lines (NKD, SI x 4 horizons); HG report-only")
    print("  asset   horizon        R2   p_adj    p_raw  null_p95")
    for asset in ASSETS:
        for h in HORIZONS:
            line = m1["lines"][f"absmove|{asset}|{h}"]
            print("  " + asset.ljust(7) + _n(h, 8)
                  + _n(line["r2"], 10, 4) + _n(line.get("p_max_adjusted"), 8, 4)
                  + _n(line.get("p_raw"), 9, 4) + _n(line.get("null_p95"), 10, 4))
    print(f"  null max R2 p95 {m1['null_max_p95']:.4f}  "
          f"mean {m1['null_max_mean']:.4f}  R2 floor {R2_FLOOR}")


def print_causes(table: Mapping[str, object]) -> None:
    print("\nM2 - EXIT CAUSE SPLIT PER ASSET x HORIZON (both sides pooled)")
    print("  asset  horizon  stop      legs      STOP   HORIZON  PH_CLOSE   GEN_END")
    for asset in ASSETS:
        for h in HORIZONS:
            for q in STOPS:
                row = table[f"{asset}|{h}|{q:.2f}"]
                fr = row["fractions"]
                print("  " + asset.ljust(6) + _n(h, 8) + _n(q, 6, 2)
                      + _n(row["legs"], 10)
                      + _n(fr["STOP"], 10, 3) + _n(fr["HORIZON"], 10, 3)
                      + _n(fr["PHASE_CLOSE"], 10, 3) + _n(fr["GENERATION_END"], 10, 3))


def print_coin(coin: Mapping[str, object]) -> None:
    print("\nM3 - COIN EXPECTATION 0.5*(LONG+SHORT), SELECTED ROWS, USD/ROW")
    print("  asset  horizon  stop     n      coin      long     short"
          "      chop  cost/stop  overshoot")
    for asset in ASSETS:
        for h in HORIZONS:
            for q in STOPS:
                row = coin[f"{asset}|{h}|{q:.2f}"]
                if not row.get("n"):
                    continue
                print("  " + asset.ljust(6) + _n(h, 8) + _n(q, 6, 2)
                      + _n(row["n"], 6)
                      + _n(row["coin_mean_usd"], 10, 2)
                      + _n(row["long_mean_usd"], 10, 2)
                      + _n(row["short_mean_usd"], 10, 2)
                      + _n(row["chop_fraction"], 10, 3)
                      + _n(row["cost_over_stop"], 11, 3)
                      + _n(row["overshoot_mean_usd"], 11, 2))


def print_control(block: Mapping[str, object]) -> None:
    print(f"\nM4 - SELECTED MINUS COUNT-MATCHED CONTROL COIN CASH, "
          f"{CONTROL_DRAWS} control draws")
    print(f"  shared-date-sign studentized maxT, {block['draws']} draws, "
          f"{len(block['family'])} eligible lines, c95 {block['c95']:.3f}")
    print("  asset  horizon  stop    dates   delta/date        SE"
          "        t    p_adj   upper95")
    for asset in ASSETS:
        for h in HORIZONS:
            for q in STOPS:
                row = block["by_line"][f"{asset}|{h}|{q:.2f}"]
                print("  " + asset.ljust(6) + _n(h, 8) + _n(q, 6, 2)
                      + _n(row["dates"], 9)
                      + _n(row["delta_usd_per_date"], 13, 2)
                      + _n(row["se_usd"], 10, 2) + _n(row["t"], 9, 3)
                      + _n(row["p_max_adjusted"], 9, 4)
                      + _n(row["upper95_simultaneous_usd"], 10, 2))


def print_replay(replays: Mapping[str, object], mdds: Mapping[str, object]
                 ) -> None:
    print("\nM5 - EXACT HASH-SIDE CHRONOLOGICAL REPLAY (one position per asset, "
          f"cap {PORTFOLIO_CAP} per portfolio date)")
    print("  horizon  stop  asset   seats  usd/day        SE   -2SE      rung"
          "   zero%   occ_rej  cap_rej")
    for h in HORIZONS:
        for q in STOPS:
            block = replays[f"{h}|{q:.2f}"]
            for asset in ASSETS:
                cash = block["cash"][asset]
                print("  " + _n(h, 7) + _n(q, 6, 2) + "  " + asset.ljust(6)
                      + _n(cash["trades"], 6)
                      + _n(cash["usd_per_day"], 9, 1)
                      + _n(cash["se_usd"], 10, 1)
                      + _n(cash["mean_minus_2se_usd"], 8, 1)
                      + _n(cash["rung_usd"], 10, 0)
                      + _n(cash["zero_entry_fraction"], 8, 3)
                      + _n(block["rejected_occupancy"], 10)
                      + _n(block["rejected_cap"], 9))
    print("\nM6 - MDD LEDGERS (Sol section D), USD, ceiling "
          f"{MDD_CEILING:.0f}")
    print("  horizon  stop   HG_tr   HG_day  NKD_tr  NKD_day   SI_tr   SI_day"
          "  PF_tr  PF_day  PF_event    max  clears")
    for h in HORIZONS:
        for q in STOPS:
            m = mdds[f"{h}|{q:.2f}"]
            print("  " + _n(h, 7) + _n(q, 6, 2)
                  + _n(m["HG|trade"], 8, 0) + _n(m["HG|day"], 9, 0)
                  + _n(m["NKD|trade"], 8, 0) + _n(m["NKD|day"], 9, 0)
                  + _n(m["SI|trade"], 8, 0) + _n(m["SI|day"], 9, 0)
                  + _n(m["PORTFOLIO|trade"], 7, 0)
                  + _n(m["PORTFOLIO|day"], 8, 0)
                  + _n(m["PORTFOLIO|event"], 10, 0)
                  + _n(m["max_binding_usd"], 7, 0)
                  + _n(m["clears"], 8))


def print_stress(stresses: Mapping[str, object], stab: Mapping[str, object]
                 ) -> None:
    print("\nM7 - STRESSES.  2 percent adversarial (worst 2% take their WORSE "
          "side) and the exit-spread double charge at STOP exits")
    print("  horizon  stop  asset    base/day    adv/day  spread/day"
          "   adv_mdd  spr_mdd")
    for h in HORIZONS:
        for q in STOPS:
            block = stresses[f"{h}|{q:.2f}"]
            for asset in ASSETS:
                print("  " + _n(h, 7) + _n(q, 6, 2) + "  " + asset.ljust(6)
                      + _n(block["base"]["cash"][asset]["usd_per_day"], 12, 1)
                      + _n(block["adversarial"]["cash"][asset]["usd_per_day"], 11, 1)
                      + _n(block["exit_spread"]["cash"][asset]["usd_per_day"], 12, 1)
                      + _n(block["adversarial"]["mdd"]["max_binding_usd"], 10, 0)
                      + _n(block["exit_spread"]["mdd"]["max_binding_usd"], 9, 0))
    print("\n  COIN STABILITY BY YEAR AND PHASE (primary h1800 / q0.50)")
    for asset in ASSETS:
        row = stab[f"{asset}|1800|0.50"]
        years = "  ".join(f"{year} {block['coin_mean_usd']:.1f} (n{block['n']})"
                          for year, block in sorted(row["by_year"].items()))
        phases = "  ".join(f"{phase} {block['coin_mean_usd']:.1f} (n{block['n']})"
                           for phase, block in sorted(row["by_phase"].items()))
        print(f"    {asset.ljust(4)} year  {years}")
        print(f"    {asset.ljust(4)} phase {phases}")


def print_decision(table: Mapping[str, object], m1: Mapping[str, object]
                   ) -> None:
    print("\nDECISION TABLE (pre-registered, Sol G).  Every registered line.")
    print("  asset  horizon  stop      R2   p_R2   coin/date  coin_p"
          "  up95   usd/day    -2SE   MDD  r2 coin cash mdd str nbr  ALL")
    for asset in ASSETS:
        for h in HORIZONS:
            for q in STOPS:
                row = table["by_asset"][asset]["rows"][f"{h}|{q:.2f}"]
                flags = "".join(
                    ("  Y " if row[name] else "  . ")
                    for name in ("r2_ok", "coin_ok", "cash_ok", "mdd_ok",
                                 "stress_ok", "neighbours_ok"))
                print("  " + asset.ljust(6) + _n(h, 8) + _n(q, 6, 2)
                      + _n(row["r2"], 8, 3) + _n(row["p_r2"], 7, 3)
                      + _n(row["coin_delta_usd_per_date"], 12, 1)
                      + _n(row["coin_p"], 8, 3)
                      + _n(row["coin_upper95"], 6, 0)
                      + _n(row["replay_usd_day"], 10, 1)
                      + _n(row["replay_minus_2se"], 8, 1)
                      + _n(row["mdd_max_usd"], 6, 0)
                      + flags + ("  Y" if row["all_ok"] else "  ."))
    print("\n  BEST LINE PER ASSET (by replay mean - 2SE)")
    print("  asset      line     usd/day     -2SE      rung   ratio")
    for asset in ASSETS:
        best = table["best_by_asset"][asset]
        print("  " + asset.ljust(6) + best["line"].rjust(11)
              + _n(best["replay_usd_day"], 12, 1)
              + _n(best["replay_minus_2se"], 9, 1)
              + _n(best["rung_usd"], 10, 0)
              + _n(best["ratio_over_rung"], 8, 3))
    print(f"\n  gates {table['gates']}")
    print(f"  VERDICT: {table['verdict']}"
          + ("  (the ASYM-KILL disjunct ALSO holds: every registered line is "
             "dead at its simultaneous 95% bound)"
             if table.get("also_asym_kill") and table["verdict"] != "ASYM-KILL"
             else ""))


# --------------------------------------------------------------------------
# Selftest.
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


def _selftest_stop_law() -> list[tuple[str, bool, str]]:
    """Hand-computed both-sides stop pricing on a synthetic tick path.

    The entry stamp sits ONE NANOSECOND after the first tick, so the frozen
    entry quote is that first tick (strictly before the stamp) and the priced
    window opens at the second - the same seam the mill uses everywhere.
    """

    out: list[tuple[str, bool, str]] = []
    asset = "HG"
    mutant = _mutant()
    factor = 0.5e-9 * float(M.ASSET_MULTIPLIER[asset])
    base = 2_000_000_000
    atr = 400.0                     # ATR14_prev in mid2 units
    q = 0.50
    distance = q * atr              # 200 mid2 units

    # --- case 1: a long stop with OVERSHOOT --------------------------------
    # Ticks every 10 s; the long stop level is base - 200; the tape prints
    # base - 260 as the first mid at or through it, so the overshoot is 60
    # mid2 units and the exit price is the PRINTED mid, not the stop level.
    path = [base, base + 40, base - 100, base - 260, base + 500, base + 900]
    index = _synthetic_index(path, asset, step_s=10, spread=1)
    entry_ns = int(index.ts[0]) + 1
    lat = np.asarray([entry_ns, entry_ns + 60 * NANOS], np.int64)
    mid_lat = np.asarray([float(path[0]), float(path[-1])], np.float64)
    close_ns = int(index.ts[-1]) + NANOS
    bars = np.asarray([0], np.int64)
    legs = price_legs(index, lat, mid_lat, bars, 1, 3600, q, atr, close_ns,
                      mutant)
    entry_mid2 = int(path[0])
    cost = M.frozen_cost_usd(int(index.bid[0]), int(index.ask[0]), asset)
    want_terminal = (int(path[3]) - entry_mid2) * factor - cost
    want_overshoot = ((entry_mid2 - distance) - int(path[3])) * factor
    out.append(_check(
        "stop/long stop prices the PRINTED mid, not the stop level",
        bool(legs.ok[0]) and abs(float(legs.terminal_usd[0]) - want_terminal) < 1e-9,
        f"got {float(legs.terminal_usd[0]):.4f} want {want_terminal:.4f}"))
    out.append(_check(
        "stop/overshoot is the printed mid beyond the stop level",
        abs(float(legs.overshoot_usd[0]) - want_overshoot) < 1e-9,
        f"got {float(legs.overshoot_usd[0]):.4f} want {want_overshoot:.4f}"))
    out.append(_check("stop/cause is STOP",
                      CAUSES[int(legs.cause[0])] == "STOP",
                      CAUSES[int(legs.cause[0])]))
    # gap size at the stop: the tick-to-tick jump into it, |-260 - (-100)| = 160
    want_gap = abs(int(path[3]) - int(path[2])) * factor
    out.append(_check("stop/gap size at the stop is the tick-to-tick jump",
                      abs(float(legs.gap_usd[0]) - want_gap) < 1e-9,
                      f"got {float(legs.gap_usd[0]):.4f} want {want_gap:.4f}"))

    # --- case 2: a HORIZON exit, no stop touched ---------------------------
    path2 = [base, base + 20, base + 40, base + 60, base + 80, base + 100,
             base + 120, base + 140]
    index2 = _synthetic_index(path2, asset, step_s=10, spread=1)
    entry2 = int(index2.ts[0]) + 1
    lat2 = np.asarray([entry2, entry2 + 60 * NANOS], np.int64)
    mid_lat2 = np.asarray([float(path2[0]), float(path2[-1])], np.float64)
    horizon = 30                      # 30 s: the ticks at 20 s and 30 s are in
    close2 = int(index2.ts[-1]) + NANOS
    legs2 = price_legs(index2, lat2, mid_lat2, np.asarray([0], np.int64), 1,
                       horizon, q, atr, close2, mutant)
    end_ns = entry2 + horizon * NANOS
    last = int(np.searchsorted(index2.ts, np.uint64(end_ns), side="right")) - 1
    want2 = (int(path2[last]) - int(path2[0])) * factor - M.frozen_cost_usd(
        int(index2.bid[0]), int(index2.ask[0]), asset)
    out.append(_check("stop/horizon exit takes the last mid inside h",
                      CAUSES[int(legs2.cause[0])] == "HORIZON"
                      and abs(float(legs2.terminal_usd[0]) - want2) < 1e-9,
                      f"{CAUSES[int(legs2.cause[0])]} "
                      f"{float(legs2.terminal_usd[0]):.4f} want {want2:.4f}"))

    # --- case 3: PHASE_CLOSE truncation ------------------------------------
    close3 = int(index2.ts[2]) + 1     # the phase closes after the third tick
    legs3 = price_legs(index2, lat2, mid_lat2, np.asarray([0], np.int64), 1,
                       7200, q, atr, close3, mutant)
    want3 = (int(path2[2]) - int(path2[0])) * factor - M.frozen_cost_usd(
        int(index2.bid[0]), int(index2.ask[0]), asset)
    out.append(_check("stop/phase close truncates before the horizon",
                      CAUSES[int(legs3.cause[0])] == "PHASE_CLOSE"
                      and abs(float(legs3.terminal_usd[0]) - want3) < 1e-9,
                      f"{CAUSES[int(legs3.cause[0])]} "
                      f"{float(legs3.terminal_usd[0]):.4f} want {want3:.4f}"))

    # --- case 4: CHOP - both hypothetical sides stop inside h --------------
    # Up through the short stop first, then back down through the long stop.
    path4 = [base, base + 260, base - 240, base + 10, base + 20]
    index4 = _synthetic_index(path4, asset, step_s=10, spread=1)
    entry4 = int(index4.ts[0]) + 1
    lat4 = np.asarray([entry4, entry4 + 60 * NANOS], np.int64)
    mid_lat4 = np.asarray([float(path4[0]), float(path4[-1])], np.float64)
    close4 = int(index4.ts[-1]) + NANOS
    long_leg = price_legs(index4, lat4, mid_lat4, np.asarray([0], np.int64), 1,
                          3600, q, atr, close4, mutant)
    short_leg = price_legs(index4, lat4, mid_lat4, np.asarray([0], np.int64), -1,
                           3600, q, atr, close4, mutant)
    out.append(_check(
        "stop/chop: BOTH hypothetical sides stop inside the horizon",
        bool(long_leg.stop_hit[0]) and bool(short_leg.stop_hit[0]),
        f"long {bool(long_leg.stop_hit[0])} short {bool(short_leg.stop_hit[0])}"))
    out.append(_check(
        "stop/first passage is the short stop, it printed first",
        int(short_leg.exit_ts_ns[0]) < int(long_leg.exit_ts_ns[0]),
        f"short {int(short_leg.exit_ts_ns[0])} long {int(long_leg.exit_ts_ns[0])}"))

    # --- case 5: a GAP straight through the stop ---------------------------
    path5 = [base, base + 10, base - 900, base - 800]
    index5 = _synthetic_index(path5, asset, step_s=10, spread=1)
    entry5 = int(index5.ts[0]) + 1
    lat5 = np.asarray([entry5, entry5 + 60 * NANOS], np.int64)
    mid_lat5 = np.asarray([float(path5[0]), float(path5[-1])], np.float64)
    close5 = int(index5.ts[-1]) + NANOS
    legs5 = price_legs(index5, lat5, mid_lat5, np.asarray([0], np.int64), 1,
                       3600, q, atr, close5, mutant)
    want_gap5 = abs(int(path5[2]) - int(path5[1])) * factor
    want_over5 = ((base - distance) - int(path5[2])) * factor
    out.append(_check(
        "stop/a gap through the stop is priced at the gapped mid",
        bool(legs5.stop_hit[0])
        and abs(float(legs5.gap_usd[0]) - want_gap5) < 1e-9
        and abs(float(legs5.overshoot_usd[0]) - want_over5) < 1e-9,
        f"gap {float(legs5.gap_usd[0]):.2f} want {want_gap5:.2f}; "
        f"overshoot {float(legs5.overshoot_usd[0]):.2f} want {want_over5:.2f}"))

    # --- case 6: the coin identity, exact ---------------------------------
    coin = 0.5 * (float(long_leg.terminal_usd[0])
                  + float(short_leg.terminal_usd[0]))
    fake_rows = [CRow(asset=asset, d8=20240101, phase=PHASES[0], cell=0, row=0,
                      bar=0, side=1, entry_ts_ns=0, entry_mid2=base,
                      cost_usd=0.0, spread_usd=0.0, atr_mid2=atr, year=2024,
                      x=np.zeros(NFEAT))]
    legs_map = {}
    for h in HORIZONS:
        for qq in STOPS:
            for side in SIDES:
                legs_map[f"{h}|{qq:.2f}|{side}|terminal_usd"] = np.asarray(
                    [float(long_leg.terminal_usd[0]) if side > 0
                     else float(short_leg.terminal_usd[0])], np.float64)
                legs_map[f"{h}|{qq:.2f}|{side}|stop_hit"] = np.asarray(
                    [True], bool)
    built = coin_matrix(fake_rows, legs_map)
    out.append(_check("coin/identity coin == 0.5*(long+short) exactly",
                      abs(float(built["1800|0.50|coin"][0]) - coin) == 0.0,
                      f"{float(built['1800|0.50|coin'][0]):.10f} vs {coin:.10f}"))
    return out


def _planted_world(days: int = 60, per_day: int = 12
                   ) -> tuple[list[CRow], dict[str, np.ndarray], np.ndarray]:
    """A world where the SELECTED states carry a real positive coin expectation.

    Feature 0 drives magnitude.  In the top-magnitude states the long and short
    legs are deliberately ASYMMETRIC (a continuation world: the long leg keeps
    running while the short leg stops), so the coin is positive there and zero
    elsewhere.  The pipeline must recover it and the count-matched permutation
    control - which draws states from the SAME (asset, date, phase) cell - must
    not.
    """

    rng = np.random.default_rng(11)
    rows: list[CRow] = []
    coin_values: list[float] = []
    d0 = 20240101
    for day in range(days):
        d8 = d0 + day
        for k in range(per_day):
            x = rng.normal(size=NFEAT)
            size = float(x[0])
            rows.append(CRow(
                asset="NKD", d8=d8, phase=PHASES[0], cell=day, row=k, bar=k,
                side=1, entry_ts_ns=(day * 86400 + k * 600) * NANOS,
                entry_mid2=0, cost_usd=0.0, spread_usd=0.0, atr_mid2=100.0,
                year=2024, x=x,
                absmove={h: 500.0 * size + rng.normal(scale=20.0)
                         for h in HORIZONS},
                abscert={h: 0.0 for h in HORIZONS},
                label_cause={h: "HORIZON" for h in HORIZONS}))
            coin_values.append(200.0 if size > 1.2 else 0.0)
    legs: dict[str, np.ndarray] = {}
    coin = np.asarray(coin_values, np.float64)
    for h in HORIZONS:
        for q in STOPS:
            for side in SIDES:
                legs[f"{h}|{q:.2f}|{side}|terminal_usd"] = coin * side + coin
                legs[f"{h}|{q:.2f}|{side}|stop_hit"] = np.zeros(len(rows), bool)
    return rows, legs, coin


def _selftest_planted() -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []
    rows, legs, coin_true = _planted_world()
    explore = {"NKD": sorted({row.d8 for row in rows}), "HG": [], "SI": []}
    folds, scored_days = build_folds(rows, explore)
    targets = {"absmove": {h: np.asarray([row.absmove[h] for row in rows],
                                         np.float64) for h in HORIZONS}}
    pred, cut = fold_scores(folds, targets["absmove"][1800])
    scored = np.zeros(len(rows), bool)
    for fold in folds:
        scored[fold.score] = True
    r2 = r2_of(targets["absmove"][1800][scored], pred[scored])
    out.append(_check("planted/the magnitude model recovers the planted size",
                      r2 is not None and r2 > 0.5, f"R2 {r2:.3f}"))
    pick = scored & np.isfinite(pred) & np.isfinite(cut) & (pred >= cut)
    out.append(_check("planted/the train-fold cutoff selects about a decile",
                      0.03 <= float(pick.sum()) / max(int(scored.sum()), 1) <= 0.25,
                      f"{int(pick.sum())} of {int(scored.sum())}"))
    selected_coin = float(coin_true[pick].mean()) if pick.any() else 0.0
    rest_coin = float(coin_true[scored & ~pick].mean())
    out.append(_check("planted/selected states carry the positive coin",
                      selected_coin > rest_coin + 20.0,
                      f"selected {selected_coin:.1f} vs rest {rest_coin:.1f}"))
    # The count-matched control must NOT find it.
    coin_map = {f"{h}|{q:.2f}|coin": coin_true for h in HORIZONS for q in STOPS}
    oof = {f"absmove|{h}": {"pred": pred, "cut": cut} for h in HORIZONS}
    control, blocks, _meta = control_days(rows, oof, coin_map, scored, draws=60)
    sel = selected_days(rows, coin_map, {h: pick for h in HORIZONS}, blocks)
    delta = sel["1800|0.50"] - control["1800|0.50"]
    out.append(_check("planted/the permuted control does NOT recover it",
                      float(delta.mean()) > 0.0,
                      f"selected minus control {float(delta.mean()):.1f} usd/day"))
    control_mean = float(control["1800|0.50"].sum()) / max(len(blocks), 1)
    out.append(_check("planted/the control is count-matched inside each cell",
                      control_mean < float(sel["1800|0.50"].mean()),
                      f"control {control_mean:.1f} < selected "
                      f"{float(sel['1800|0.50'].mean()):.1f}"))
    return out


def _selftest_replay() -> list[tuple[str, bool, str]]:
    """The occupancy law on a constructed collision day."""

    out: list[tuple[str, bool, str]] = []
    rows: list[CRow] = []
    stamps = [0, 100, 1000, 1100, 5000]
    for k, stamp in enumerate(stamps):
        rows.append(CRow(asset="NKD", d8=20240102, phase=PHASES[0], cell=1,
                         row=k, bar=k, side=1, entry_ts_ns=int(stamp) * NANOS,
                         entry_mid2=0, cost_usd=0.0, spread_usd=0.0,
                         atr_mid2=100.0, year=2024, x=np.zeros(NFEAT)))
    exits = [900, 900, 4000, 4000, 6000]
    legs: dict[str, np.ndarray] = {}
    for h in HORIZONS:
        for q in STOPS:
            for side in SIDES:
                legs[f"{h}|{q:.2f}|{side}|exit_ts_ns"] = np.asarray(
                    [e * NANOS for e in exits], np.int64)
                legs[f"{h}|{q:.2f}|{side}|terminal_usd"] = np.ones(len(rows))
                legs[f"{h}|{q:.2f}|{side}|exit_bar"] = np.asarray(
                    [1, 1, 3, 3, 4], np.int64)
    mask = np.ones(len(rows), bool)
    sides = {k: 1 for k in range(len(rows))}
    got = replay(rows, legs, mask, 1800, 0.50, sides)
    out.append(_check("replay/one position per asset: collisions are rejected",
                      got["seated"] == 3 and got["rejected_occupancy"] == 2,
                      f"seated {got['seated']} occ_rej "
                      f"{got['rejected_occupancy']}"))
    seated = [t.entry_ts_ns // NANOS for t in got["trades"]]
    out.append(_check("replay/the seated entries are the chronological ones",
                      seated == [0, 1000, 5000], str(seated)))
    # The portfolio cap, dynamically, never four per asset.
    many: list[CRow] = []
    for k in range(20):
        many.append(CRow(asset=("HG", "NKD", "SI")[k % 3], d8=20240103,
                         phase=PHASES[0], cell=2, row=k, bar=k, side=1,
                         entry_ts_ns=int(k * 10_000) * NANOS, entry_mid2=0,
                         cost_usd=0.0, spread_usd=0.0, atr_mid2=100.0,
                         year=2024, x=np.zeros(NFEAT)))
    legs2: dict[str, np.ndarray] = {}
    for h in HORIZONS:
        for q in STOPS:
            for side in SIDES:
                legs2[f"{h}|{q:.2f}|{side}|exit_ts_ns"] = np.asarray(
                    [(k * 10_000 + 1) * NANOS for k in range(20)], np.int64)
                legs2[f"{h}|{q:.2f}|{side}|terminal_usd"] = np.ones(20)
                legs2[f"{h}|{q:.2f}|{side}|exit_bar"] = np.arange(20, dtype=np.int64)
    got2 = replay(many, legs2, np.ones(20, bool), 1800, 0.50,
                  {k: 1 for k in range(20)})
    out.append(_check("replay/the 12-entry portfolio cap binds dynamically",
                      got2["seated"] == PORTFOLIO_CAP
                      and got2["rejected_cap"] == 20 - PORTFOLIO_CAP,
                      f"seated {got2['seated']} cap_rej {got2['rejected_cap']}"))
    per_asset = {}
    for trade in got2["trades"]:
        per_asset[trade.asset] = per_asset.get(trade.asset, 0) + 1
    out.append(_check("replay/the cap is NOT four reserved per asset",
                      max(per_asset.values()) >= 4 and sum(per_asset.values()) == 12,
                      str(per_asset)))
    return out


def _selftest_hash() -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []
    a = hash_side("NKD", 20240102, 1234567890)
    b = hash_side("NKD", 20240102, 1234567890)
    c = hash_side("SI", 20240102, 1234567890)
    out.append(_check("hash/the side is frozen and reproducible", a == b,
                      f"{a} == {b}"))
    draws = [hash_side("NKD", 20240102, k * 977) for k in range(4000)]
    share = float(np.mean([d > 0 for d in draws]))
    out.append(_check("hash/the frozen coin is unbiased", 0.45 <= share <= 0.55,
                      f"long share {share:.3f}"))
    out.append(_check("hash/the asset enters the digest", isinstance(c, int),
                      f"SI {c}"))
    return out


def _selftest_mutant() -> list[tuple[str, bool, str]]:
    """The red case: minute-lattice stop inference must break the stop cases."""

    out: list[tuple[str, bool, str]] = []
    asset = "HG"
    factor = 0.5e-9 * float(M.ASSET_MULTIPLIER[asset])
    base = 2_000_000_000
    atr, q = 400.0, 0.50
    # Ticks every 10 s.  The long stop is crossed INSIDE the first minute at
    # tick 3 and price is back above the stop by the minute close, so a minute
    # lattice cannot see it at all.
    path = [base, base + 40, base - 100, base - 260, base + 500, base + 900]
    index = _synthetic_index(path, asset, step_s=10, spread=1)
    entry_ns = int(index.ts[0]) + 1
    lat = np.asarray([entry_ns, entry_ns + 60 * NANOS], np.int64)
    mid_lat = np.asarray([float(path[0]), float(path[-1])], np.float64)
    close_ns = entry_ns + 130 * NANOS
    ticks = price_legs(index, lat, mid_lat, np.asarray([0], np.int64), 1, 3600,
                       q, atr, close_ns, "")
    minutes = price_legs(index, lat, mid_lat, np.asarray([0], np.int64), 1, 3600,
                         q, atr, close_ns, MUTANT_OHLC)
    out.append(_check("mutant/raw ticks see the intraminute stop",
                      bool(ticks.stop_hit[0]), "tick path stops"))
    out.append(_check("mutant/the minute lattice MISSES it (the red case)",
                      not bool(minutes.stop_hit[0]),
                      f"minute stop_hit {bool(minutes.stop_hit[0])}"))
    out.append(_check("mutant/and therefore prices a different terminal",
                      abs(float(ticks.terminal_usd[0])
                          - float(minutes.terminal_usd[0])) > 1e-6,
                      f"ticks {float(ticks.terminal_usd[0]):.2f} vs minutes "
                      f"{float(minutes.terminal_usd[0]):.2f}"))
    return out


def selftest() -> int:
    mutant = _mutant()
    print(f"sweep 20 selftest  spec_sha {SPEC_SHA[:16]}  "
          f"code_sha {code_sha()[:16]}  mutant {mutant or 'none'}")
    rows: list[tuple[str, bool, str]] = []
    rows += _selftest_stop_law()
    rows += _selftest_planted()
    rows += _selftest_replay()
    rows += _selftest_hash()
    if not mutant:
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
    coin = report["m3_coin"]
    control = report["m4_control"]
    replays = report["m5_replay"]
    mdds = report["m6_mdd"]
    stresses = report["m7_stress"]
    ruling = report["decision"]
    params = json.dumps({
        "horizons_s": list(HORIZONS), "stops_q_atr": list(STOPS),
        "lambda": RIDGE_LAMBDA, "features": NFEAT,
        "min_prior_days": MIN_PRIOR_DAYS_FIT, "min_fit_rows": MIN_FIT_ROWS,
        "top_decile": TOP_DECILE, "r2_draws": R2_DRAWS,
        "control_draws": CONTROL_DRAWS, "sign_draws": SIGN_DRAWS,
        "portfolio_cap": PORTFOLIO_CAP, "stress_rate": STRESS_RATE,
        "cell_balanced": True, "wall": "OUT"})
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
        counter += 1
        rows.append({
            **shared, "id": f"sweep20-{counter:03d}",
            "rule": f"M1-MAGR2/h{h}",
            "days": sum(int(report["scoring_days"]["live"][a]) for a in ASSETS),
            "err_rate_hg": m1["lines"][f"absmove|HG|{h}"]["r2"],
            "err_rate_nkd": m1["lines"][f"absmove|NKD|{h}"]["r2"],
            "err_rate_si": m1["lines"][f"absmove|SI|{h}"]["r2"],
            "null_margin": m1["lines"][f"absmove|NKD|{h}"].get("p_max_adjusted"),
            "note": ("no-wall |terminal move| OOF R2, cell-balanced, max-R2 "
                     "day-block null: "
                     + "; ".join(
                         f"{a} {_show(m1['lines'][f'absmove|{a}|{h}']['r2'])}"
                         f" (p_adj "
                         f"{_show(m1['lines'][f'absmove|{a}|{h}'].get('p_max_adjusted'))})"
                         for a in ASSETS))[:400],
        })
    for h in HORIZONS:
        for q in STOPS:
            counter += 1
            key = f"{h}|{q:.2f}"
            rows.append({
                **shared, "id": f"sweep20-{counter:03d}",
                "rule": f"M3-COIN/h{h}/q{q:.2f}",
                "days": sum(int(report["scoring_days"]["live"][a])
                            for a in ASSETS),
                "hg_usd_day": coin[f"HG|{h}|{q:.2f}"].get("coin_mean_usd"),
                "nkd_usd_day": coin[f"NKD|{h}|{q:.2f}"].get("coin_mean_usd"),
                "si_usd_day": coin[f"SI|{h}|{q:.2f}"].get("coin_mean_usd"),
                "null_margin": control["by_line"][f"NKD|{h}|{q:.2f}"][
                    "p_max_adjusted"],
                "note": ("coin 0.5*(L+S) usd/selected row; chop; "
                         "selected-minus-control usd/date (p_adj): "
                         + "; ".join(
                             f"{a} {_show(coin[f'{a}|{h}|{q:.2f}'].get('coin_mean_usd'))}"
                             f" chop {_show(coin[f'{a}|{h}|{q:.2f}'].get('chop_fraction'))}"
                             f" delta "
                             f"{_show(control['by_line'][f'{a}|{h}|{q:.2f}']['delta_usd_per_date'])}"
                             f" (p {_show(control['by_line'][f'{a}|{h}|{q:.2f}']['p_max_adjusted'])})"
                             for a in ASSETS))[:400],
            })
    for h in HORIZONS:
        for q in STOPS:
            counter += 1
            key = f"{h}|{q:.2f}"
            cash = replays[key]["cash"]
            mdd = mdds[key]
            rows.append({
                **shared, "id": f"sweep20-{counter:03d}",
                "rule": f"M5-REPLAY/h{h}/q{q:.2f}",
                "days": sum(int(cash[a]["days"]) for a in ASSETS),
                "hg_usd_day": cash["HG"]["usd_per_day"],
                "nkd_usd_day": cash["NKD"]["usd_per_day"],
                "si_usd_day": cash["SI"]["usd_per_day"],
                "mdd_hg": mdd["HG|day"], "mdd_nkd": mdd["NKD|day"],
                "mdd_si": mdd["SI|day"],
                "replay_skips": (replays[key]["rejected_occupancy"]
                                 + replays[key]["rejected_cap"]),
                "coverage": cash["_portfolio"]["portfolio_seats_mean"],
                "note": ("hash-side one-position replay, mean-2SE vs rung: "
                         + "; ".join(
                             f"{a} {_show(cash[a]['mean_minus_2se_usd'])}"
                             f"/{int(cash[a]['rung_usd'])}"
                             for a in ASSETS)
                         + f"; portfolio event MDD "
                           f"{_show(mdd['PORTFOLIO|event'])}; occ_rej "
                           f"{replays[key]['rejected_occupancy']} cap_rej "
                           f"{replays[key]['rejected_cap']}")[:400],
            })
    for asset in ASSETS:
        counter += 1
        best = ruling["best_by_asset"][asset]
        rows.append({
            **shared, "id": f"sweep20-{counter:03d}",
            "rule": f"RULING/{asset}",
            "days": int(report["scoring_days"]["live"][asset]),
            "err_rate_hg": best["r2"] if asset == "HG" else None,
            "err_rate_nkd": best["r2"] if asset == "NKD" else None,
            "err_rate_si": best["r2"] if asset == "SI" else None,
            "hg_usd_day": best["replay_usd_day"] if asset == "HG" else None,
            "nkd_usd_day": best["replay_usd_day"] if asset == "NKD" else None,
            "si_usd_day": best["replay_usd_day"] if asset == "SI" else None,
            "mdd_hg": best["mdd_max_usd"] if asset == "HG" else None,
            "mdd_nkd": best["mdd_max_usd"] if asset == "NKD" else None,
            "mdd_si": best["mdd_max_usd"] if asset == "SI" else None,
            "null_margin": best["coin_p"],
            "note": (f"{ruling['verdict']}; best line {best['line']}: R2 "
                     f"{_show(best['r2'])} (p {_show(best['p_r2'])}); coin "
                     f"{_show(best['coin_delta_usd_per_date'])} usd/date "
                     f"(p {_show(best['coin_p'])}, up95 "
                     f"{_show(best['coin_upper95'])}); replay -2SE "
                     f"{_show(best['replay_minus_2se'])} of rung "
                     f"{int(best['rung_usd'])}; ratio "
                     f"{_show(best['ratio_over_rung'])}; MDD "
                     f"{_show(best['mdd_max_usd'])}")[:400],
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
    cells, asset_days, _skipped = S8.build_cells(ASSETS)
    records, _days = S1.load_cache()
    records = [rec for rec in records if rec.asset in ASSETS]
    explore_days = S1._explore_days(ASSETS)

    tape = S9.load_tape(cells)
    forecast = S9.forecast_variance(cells)
    plane9 = S9.build_plane(cells, forecast, tape)
    gate = S14.reproduce_sweep9(plane9)
    if not gate["matches"]:
        raise SweepRefusal("sweep 9's row plane did not reproduce; no "
                           "measurement is believed past this point")
    states = S12.day_states({asset: explore_days[asset] for asset in ASSETS})
    streams, stream_counters = S14.build_streams(plane9, cells, states, "")

    picked, universe = coarse_universe(streams, records)
    # Sweep 15's banked coarse SCORING-scope counts, before dedup: the gate on
    # the universe itself.
    scoring_scope: dict[str, int] = {asset: 0 for asset in ASSETS}
    for asset in ASSETS:
        days = sorted(int(day) for day in explore_days[asset])
        eligible = set(days[MIN_PRIOR_DAYS_FIT:])
        for stream in streams:
            if stream.asset != asset or int(stream.d8) not in eligible:
                continue
            scoring_scope[asset] += len(S15.coarse_occs(stream))
    universe["s15_scoring_live"] = scoring_scope
    universe["s15_scoring_banked"] = dict(S15_COARSE_SCORING_ROWS)
    universe["s15_scoring_matches"] = bool(scoring_scope
                                           == S15_COARSE_SCORING_ROWS)
    if not universe["s15_scoring_matches"]:
        raise SweepRefusal("the coarse post-reset universe did not reproduce "
                           "sweep 15's banked scoring-scope counts "
                           f"{S15_COARSE_SCORING_ROWS}; live {scoring_scope}")

    rows, legs, row_counters = build_rows(picked, records, cells, mutant)
    universe["priced"] = {asset: sum(1 for row in rows if row.asset == asset)
                          for asset in ASSETS}

    folds, scored_days = build_folds(rows, explore_days)
    scoring = {"live": scored_days, "banked": dict(REPRO_SCORING_DAYS),
               "matches": bool(scored_days == REPRO_SCORING_DAYS)}
    if not scoring["matches"]:
        raise SweepRefusal("the walk-forward fold law did not reproduce sweep "
                           f"14's scoring days {REPRO_SCORING_DAYS}; live "
                           f"{scored_days}")

    targets = {
        "absmove": {h: np.asarray([row.absmove[h] for row in rows], np.float64)
                    for h in HORIZONS},
        "abscert": {h: np.asarray([row.abscert[h] for row in rows], np.float64)
                    for h in HORIZONS},
    }
    m1, oof, scored = m1_magnitude(rows, folds, targets, explore_days)

    selected = {h: selection_mask(oof, h, scored) for h in HORIZONS}
    causes = exit_cause_table(rows, legs, selected)
    coin = coin_matrix(rows, legs)
    coin_spread = coin_matrix(rows, legs, spread_double=True)
    m3 = m3_coin(rows, legs, coin, selected)
    separation = excursion_separation(rows, legs, selected, scored)

    control_raw, blocks, control_meta = control_days(rows, oof, coin, scored)
    selected_cash = selected_days(rows, coin, selected, blocks)
    m4 = maxt_inference(blocks, selected_cash, control_raw)
    m4["control_meta"] = control_meta

    mid_by_cell = {row.cell: np.asarray(records[row.cell].mid, np.float64)
                   for row in rows}
    lat_by_cell = {row.cell: np.asarray(records[row.cell].lat, np.int64)
                   for row in rows}
    entry_by_position = {(row.cell, row.bar, side): (row.entry_mid2, row.cost_usd)
                         for row in rows for side in SIDES}
    sides = {position: hash_side(row.asset, row.d8, row.entry_ts_ns)
             for position, row in enumerate(rows)}

    replays: dict[str, object] = {}
    mdds: dict[str, object] = {}
    stresses: dict[str, object] = {}
    for h in HORIZONS:
        for q in STOPS:
            key = f"{h}|{q:.2f}"
            base = replay(rows, legs, selected[h], h, q, sides)
            cash = replay_cash(base["trades"], explore_days)
            ledger = mdd_ledgers(base["trades"], rows, mid_by_cell, lat_by_cell,
                                 entry_by_position, explore_days)
            replays[key] = {"seated": base["seated"],
                            "rejected_occupancy": base["rejected_occupancy"],
                            "rejected_cap": base["rejected_cap"],
                            "cash": cash}
            mdds[key] = ledger
            overrides = adversarial_overrides(rows, legs, selected[h], h, q,
                                              sides)
            adv = replay(rows, legs, selected[h], h, q, sides, overrides)
            adv_cash = replay_cash(adv["trades"], explore_days)
            adv_mdd = mdd_ledgers(adv["trades"], rows, mid_by_cell, lat_by_cell,
                                  entry_by_position, explore_days)
            spread_overrides = {}
            for position in np.flatnonzero(selected[h]):
                side = sides[int(position)]
                if bool(legs[f"{key}|{side}|stop_hit"][position]):
                    spread_overrides[int(position)] = float(
                        legs[f"{key}|{side}|terminal_usd"][position]
                        - rows[int(position)].spread_usd)
            spr = replay(rows, legs, selected[h], h, q, sides, spread_overrides)
            spr_cash = replay_cash(spr["trades"], explore_days)
            spr_mdd = mdd_ledgers(spr["trades"], rows, mid_by_cell, lat_by_cell,
                                  entry_by_position, explore_days)
            stresses[key] = {
                "base": {"cash": cash, "mdd": ledger},
                "adversarial": {"cash": adv_cash, "mdd": adv_mdd,
                                "flipped": len(overrides)},
                "exit_spread": {"cash": spr_cash, "mdd": spr_mdd,
                                "charged": len(spread_overrides)},
                "coin_exit_spread": {
                    asset: float(np.mean(
                        coin_spread[f"{key}|coin"][
                            selected[h] & np.asarray(
                                [r.asset == asset for r in rows], bool)]))
                    if (selected[h] & np.asarray(
                        [r.asset == asset for r in rows], bool)).any() else None
                    for asset in ASSETS},
            }
    stab = stability(rows, coin, selected)
    ruling = decide(m1, m3, m4, replays, mdds, stresses, separation)

    return {
        "schema": "QRE2MILLSWEEP20", "tier": "exploratory",
        "spec_sha": SPEC_SHA, "code_sha": code_sha(),
        "split_sha": S1.split_sha(), "outcome_law_sha": S1.outcome_law_sha(),
        "seed": SEED, "mutant": mutant, "family": FAMILY,
        "parent_trial": PARENT_TRIAL, "selection_rule": SELECTION_RULE,
        "registered_utc": report_stamp(),
        "horizons_s": list(HORIZONS), "stops_q_atr": list(STOPS),
        "asset_days": {a: int(asset_days.get(a, 0)) for a in ASSETS},
        "stream_gate": gate, "stream_counters": stream_counters,
        "scoring_days": scoring, "universe": universe,
        "row_counters": row_counters,
        "selected_rows": {f"h{h}": {a: int((selected[h] & np.asarray(
            [r.asset == a for r in rows], bool)).sum()) for a in ASSETS}
            for h in HORIZONS},
        "m1": m1, "m2_exit_causes": causes, "m3_coin": m3,
        "excursion_separation": separation,
        "m4_control": m4, "m5_replay": replays, "m6_mdd": mdds,
        "m7_stress": stresses, "stability": stab,
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
    print(f"sweep 20 spec_sha {SPEC_SHA[:16]} code_sha {code_sha()[:16]} "
          f"seed {SEED} parent {report['parent_trial']} "
          f"mutant {report['mutant'] or 'none'}")
    print_gate(report)
    print_m1(report["m1"])
    print_causes(report["m2_exit_causes"])
    print_coin(report["m3_coin"])
    print_control(report["m4_control"])
    print_replay(report["m5_replay"], report["m6_mdd"])
    print_stress(report["m7_stress"], report["stability"])
    print_decision(report["decision"], report["m1"])
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
