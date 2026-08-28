#!/usr/bin/env python3
"""Sweep 18 - the library-literal episode grammar, priced as an ORDERED ladder.

USER-directed.  The discretionary library does not describe a score; it
describes a SEQUENCE.  Aggressive effort arrives into a zone anchored at a
structural extreme, a passive wall absorbs it INSIDE the zone, the effort is
not paid, volume during the stall says whether someone is there or nobody is
left, the touch is not the first one, opposite aggression arrives, price pulls
away, and the entry is on the retest.  Every prior flow unit in this mill
scored features or composites against terminality timing proxies (sweep 6,
KILLED).  None of them priced hold-versus-break cash under the ordered
conjunction.  Sweep 13 already showed the REPEAT gate alone is causal
(ordinal-2 beat the lateness-matched control, max-adjusted p 0.030 on both
deciding assets).  This unit prices the whole grammar.

WHAT IS NEW HERE, in one line: the gates are applied CUMULATIVELY IN THE
LIBRARY'S ORDER, and each gate reads the window the order gives it - effort and
its reward over the effort phase, the volume fork and the aggression flip over
the stall that follows it - so that a control which applies the same six gates
without the ordering has something to be compared against.

THE 18-TICK LAW, load bearing.  `refill-effect` p10 measures the median
eventual winner dipping 18 ticks past the touch before it works, and p11 prices
the same signals with a market order at the touch (0.81 PF, 27.2% wins) against
a limit resting inside the zone (1.80 PF, 68.8% wins) - the limit fills less
often "precisely because it demands the flush that defines the setup".  The
adverse excursion after the effort is a CONSTITUENT of the setup, never a veto.
So in this unit NO GATE READS PRICE EXCURSION IN THE POST-EFFORT WINDOW.  The
two gates that look at the stall read VOLUME (G4) and AGGRESSOR DIRECTION (G6),
never how far price travelled.  The post-effort adverse excursion is measured
on every rung and reported beside the cash, and the selftest holds a planted
winner with a deep excursion that every gate must pass.  The red mutant is
exactly this error: `gate_reads_post_stamp` extends G3's reward window past the
decision stamp, so the flush that defines the setup is counted as reward and
the planted episode is thrown away.

NO ABSOLUTE CONSTANTS FROM THE LIBRARY PDFS.  The 3-tick and 18-tick numbers
are shapes to re-measure, not thresholds to hard-code.  Every cut in this unit
is a train-day quantile, measured per asset x phase on days STRICTLY BEFORE the
scoring day, minimum 25 prior days, the sweep-14 fold law.  The only literal
numbers in the gate logic are the sign boundary zero (G6: "opposite aggression
appears" is a sign statement, not a magnitude) and the ordinal 2 imported from
sweep 13.

Exploratory tier, EXPLORE only, kill-only, one shot, no fitted weights.  The
killed flow composite stays closed as a policy; this is a pre-registered test of
individual gates in a fixed order.  The sealed R4mem stays closed.
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
from typing import Mapping, Sequence
import warnings

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tools/mill") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools/mill"))

import context as CTX                     # noqa: E402
import flow as FLOW                       # noqa: E402
import mill as M                          # noqa: E402
import sweep1 as S1                       # noqa: E402
import sweep7a as S7A                     # noqa: E402
import sweep8 as S8                       # noqa: E402
import sweep9_twins as S9                 # noqa: E402
import sweep12 as S12                     # noqa: E402
import sweep13 as S13                     # noqa: E402
import sweep14 as S14                     # noqa: E402
from engine.entry_v2.diagnostic_types import RAW_TICK   # noqa: E402


SPEC = """QRE2MILLSWEEP18
THE OBJECT.  The sweep-14 deduped occurrence stream, reproduced exactly: 47402
rows, certifiable cells HG 138 NKD 132 SI 132, candidates_seen 313131,
cells_with_rows 385.  Y is the frozen to-close cert already banked per
occurrence by the outcome law - no new label plane is built here.  Scoring days
are the explore days with at least 25 prior explore days: 41/40/39.

THE EPISODE.  For an occurrence at cell bar b on side s (s=+1 fades the running
LOW, s=-1 fades the running HIGH, the frozen sweep-7a mapping), let m be the bar
that set the standing extreme (the last same-side new-extreme mark at or before
b-1).  The EPISODE is [m, b).  Let p = argmax over [m, b) of the per-minute
aggression TOWARD the extreme (din = -s * delta).  The EFFORT PHASE is [m, p];
the STALL is (p, b).  All flow is read from the minute cache at bars strictly
before b: bar k's data is complete at bar_close_ts_ns[k] = lat[k+1], so bars
0..b-1 are the whole legal history at the stamp and bar b is never read.

THE GATES, library order, each mapped from the sources.
G1 LOCATION VETO.  loc_prev = -s * (extreme - developing_day_mid) /
   prev_session_range_mid2, with the developing day range accumulated across
   the day's phases over bars strictly before the stamp and the prior session
   range served by context.py under its strictly-prior law.  PASS when
   loc_prev >= the train-day upper quartile.  The reject branch is mid-range -
   the library's "not near POC, not inside balance" veto (your-mistakes p6
   labels the full absorption signature at POC "THIS IS NOT ABS", p13 makes it
   a hard checklist gate).  BOTH BRANCHES ARE REPORTED.
G2 EFFORT IN.  effort = sum over the effort phase of attack volume in the bars
   whose aggression pushed toward the extreme.  PASS in the train-day top
   tercile.
G3 NO REWARD.  extension = sum over the effort phase of ticks of fresh
   penetration past the standing extreme bought by that attack (build_flow's
   effort-versus-result pair, recovered as yield * (attack + 1)).  Regress
   extension on effort ON TRAIN DAYS ONLY; PASS when the residual is in the
   train-day bottom tercile.  High effort, low reward is the absorption read.
   The window ENDS AT p.  It never reaches into the stall, because the flush
   into the zone after the effort is the setup, not its refutation.
G4 THE FORK.  vol_ratio = mean volume over the stall / (mean volume over the
   effort phase + 1).  ABSORPTION branch: vol_ratio >= the train-day median
   (heavy volume, no movement, someone is there).  EXHAUSTION branch: below it
   (shrinking volume, nobody is left).  dom-lesson-6 p7 says they point
   opposite ways, so the two branches are carried separately and never
   averaged.  The exhaustion branch is reported as its own line at its rung.
G5 REPEAT.  The sweep-13 gate, imported: the in-zone ordinal with resets on
   every same-side new extreme, >= 2.  One failed push is noise; two at the
   same price is the read (trapped-buyers p5).
G6 OPPOSITE AGGRESSION.  flip = sum over the stall of s * delta, the aggressor
   flow toward the fade side after the effort peak, strictly before the stamp.
   PASS when flip > 0 AND flip >= the train-day median.  your-mistakes p9:
   "then, and only then" - not just an absence of buyers but active selling.

THE LADDER.  R0 all measurable scoring-day occurrences; R1 = G1; R2 = +G2;
R3 = +G3; R4 = +G4 absorption; R5 = +G5; R6 = +G6.  R4X = R3 + G4 exhaustion.
G1REJECT = the mid-range reject branch of G1.  Per rung per asset: n, cells,
coverage of certifiable cells, P(Y>0) with Wilson 95, mean Y, median Y, usd per
asset-day on scoring days, mean post-effort adverse excursion in ticks.

THRESHOLD LAW.  Every cut is a quantile of the TRAIN rows of the same asset x
phase on days strictly before the scoring day, minimum 25 prior days and
minimum 50 train rows.  Terciles for G2/G3, upper quartile for G1, median for
G4/G6.  The G3 regression is fit on train rows only and applied forward.

CONTROLS, pre-registered.
C1 RANDOM SUBSET, matched on asset-day and size.  2000 block draws; within each
   asset-day the day's whole occurrence pool is permuted and the rung's own
   per-day count is drawn from it.  p_own = the share of draws at or above the
   observed statistic.  Asks: does the rung beat random selection at equal
   coverage, on P(Y>0) and on mean Y.
C2 LATENESS MATCH.  The sweep-13 law applied to the final rung: for each
   selected occurrence, donors from the same asset and phase, a DIFFERENT day,
   phase-elapsed within 300 s and remaining within 300 s; one donor drawn per
   occurrence per draw.  Run at the sweep-13 draw count for the law-faithful
   rate and at 2000 draws for the p-value.  Asks: is the ladder more than
   lateness.
C3 SCRAMBLED GATE.  The same six gates as an UNORDERED AND: every window is the
   whole episode [m, b) with no anchoring on the effort peak, so G6 may be read
   before G3 and the volume fork splits the episode at its midpoint instead of
   at p.  Asks: does the ORDER add anything.
C4 BLOCK PERMUTATION MAX-STAT.  The same 2000 asset-day block draws as C1; the
   statistic is the maximum over the whole rung x asset family, so every
   headline carries a family-wise adjusted p.  C1 and C4 share the draw matrix
   by design - the max-statistic must be taken over the same null - which is
   the sweep-13 p_own / p_max_adjusted pattern.

LETTERS, pre-registered.
GRAMMAR-LIVE if on a deciding asset (NKD or SI) the FULL ladder R6 beats C1 and
  C2 on mean Y with max-adjusted p <= 0.05, AND its P(Y>0) lower Wilson bound
  is >= 0.55, AND its coverage of cells is >= 0.15.
PARTIAL-GATE if R6 misses those bounds but a strict subset rung meets them, or
  if R6 meets them while a strict subset rung's mean Y is at least R6's on the
  same asset - the added gates buy nothing.  Name the subset and the deltas.
UNPOWERED if R6's n is under 30 on EVERY deciding asset.  Said plainly.
NONE otherwise.

MUTANT.  QRE2_MILL_S18_MUTANT=gate_reads_post_stamp extends G3's reward window
past the decision stamp by the episode length, so the post-stamp flush is
counted as reward and the planted absorption episode is thrown away.
"""


# --------------------------------------------------------------------------
# Constants.  Nothing here comes from a library PDF.
# --------------------------------------------------------------------------

ASSETS = S1.ASSETS
DECIDING = ("NKD", "SI")
REPORT_ONLY = ("HG",)
PHASES = ("0", "1", "2")
BAR_SECONDS = S1.BAR_SECONDS
SEED = 20260827
NANOS = 1_000_000_000

DEPTH_ATR = S14.DEPTH_ATR                 # 0.15, frozen
REMAIN_MIN_S = S14.REMAIN_MIN_S           # 1800, frozen
MIN_PRIOR_DAYS = S14.MIN_PRIOR_DAYS_FIT   # 25, the sweep-14 fold law
MIN_TRAIN_ROWS = S14.MIN_FIT_ROWS         # 50

# The sweep-14 stream law.  The unit refuses to run unless these match.
REPRO_ROWS = S14.REPRO_ROWS                       # 47402
REPRO_CERTIFIABLE = S14.REPRO_CERTIFIABLE         # HG 138 NKD 132 SI 132
REPRO_COUNTERS = S14.REPRO_COUNTERS               # candidates_seen 313131 ...
REPRO_SCORING_DAYS = {"HG": 41, "NKD": 40, "SI": 39}
REPRO_CELLS_WITH_ROWS = 385

# Quantile marks.  Terciles and quartiles, the brief's law.
Q_LOCATION = 75.0        # G1 upper quartile: the outer region
Q_EFFORT = 100.0 / 3.0 * 2.0    # G2 top tercile cut (66.67)
Q_REWARD = 100.0 / 3.0          # G3 bottom tercile cut (33.33)
Q_FORK = 50.0            # G4 median
Q_FLIP = 50.0            # G6 median

ORDINAL = S13.ORDINAL                     # 2, imported from the sweep-13 gate

RUNGS = ("R0", "R1", "R2", "R3", "R4", "R5", "R6")
BRANCHES = RUNGS + ("R4X", "G1REJECT", "SCRAMBLE")
LADDER_LABEL = {
    "R0": "all measurable",
    "R1": "G1 location",
    "R2": "+G2 effort in",
    "R3": "+G3 no reward",
    "R4": "+G4 absorption",
    "R5": "+G5 repeat>=2",
    "R6": "+G6 opposite aggression",
    "R4X": "R3 +G4 EXHAUSTION branch",
    "G1REJECT": "G1 reject branch (mid-range)",
    "SCRAMBLE": "C3 six gates, unordered AND",
}
FINAL_RUNG = "R6"
SUBSET_RUNGS = ("R1", "R2", "R3", "R4", "R5", "R4X")

BLOCK_DRAWS = 2000
LATENESS_P_DRAWS = 2000
LATENESS_DRAWS = S13.TIME_MATCH_DRAWS            # 200, the sweep-13 law
LATENESS_WINDOW_S = S13.TIME_MATCH_WINDOW_S      # 300, the sweep-13 law

# Pre-registered letter bounds.
WILSON_FLOOR = 0.55
COVERAGE_FLOOR = 0.15
ADJUSTED_P_CEILING = 0.05
MIN_POWER_N = 30

FIXHOLD_S = 1800

FAMILY = "F15-EPISODE"
PARENT_TRIAL = "sweep13-002"
SELECTION_RULE = ("none: USER-directed pre-registered gates in the library's "
                  "fixed order, no fitted weights, one shot")

MUTANT_ENV = "QRE2_MILL_S18_MUTANT"
MUTANT_POST = "gate_reads_post_stamp"
MUTANTS = (MUTANT_POST,)

OUT_PATH = ROOT / ".audit/mill-sweep18.json"
LOG_PATH = S1.LOG_PATH
SWEEP16_PATH = ROOT / ".audit/mill-sweep16.json"


class SweepRefusal(RuntimeError):
    """The stream, the caches or the fold law did not hold.  Nothing is priced."""


SPEC_SHA = S1._sha_text(SPEC)


def code_sha() -> str:
    return S1._sha_text(Path(__file__).read_text())


def _mutant() -> str:
    name = os.environ.get(MUTANT_ENV, "")
    if name and name not in MUTANTS:
        raise SweepRefusal(f"unknown mutant {name!r}")
    return name


def _q(values: Sequence[float], mark: float) -> float | None:
    good = np.asarray([v for v in values if v is not None and math.isfinite(v)],
                      np.float64)
    if not len(good):
        return None
    return float(np.percentile(good, mark))


def _f(value: object) -> float | None:
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


# --------------------------------------------------------------------------
# Per-occurrence episode measurement.
# --------------------------------------------------------------------------

MEASURE_FIELDS = (
    "loc_prev",        # G1 statistic
    "outerness",       # G1 companion, reported
    "effort_in",       # G2 statistic
    "extension",       # G3 numerator, effort-phase only
    "vol_ratio",       # G4 statistic
    "flip",            # G6 statistic
    "adv_ticks",       # post-effort adverse excursion, REPORTED, never a gate
    "effort_u",        # C3 unordered variants
    "extension_u",
    "vol_ratio_u",
    "flip_u",
    "episode_bars",
    "effort_bars",
    "stall_bars",
)

MISS_NO_FLOW = "no_flow_cell"
MISS_NO_LEVELS = "no_prev_levels"
MISS_SHORT = "episode_too_short"
MISS_NO_STALL = "no_stall_bar"
MISS_NO_TRAIN = "no_train_fold"
MISS_BRANCHES = (MISS_NO_FLOW, MISS_NO_LEVELS, MISS_SHORT, MISS_NO_STALL,
                 MISS_NO_TRAIN)


@dataclass(slots=True)
class Row:
    """One occurrence with everything the ladder, the controls and cash need."""

    index: int
    asset: str
    phase: str
    d8: int
    cell: int
    side: int
    bar: int
    stamp_ns: int
    elapsed_s: float
    remaining_s: float
    inzone_ordinal: int
    y: float
    measured: bool
    miss: str
    values: dict[str, float] = field(default_factory=dict)


def _slope_free_ratio(numer: float, denom: float) -> float:
    return float(numer) / (float(denom) + 1.0)


def measure_cell(cell: S8.Cell8, flow_cell: Mapping[str, np.ndarray],
                 dev_low: np.ndarray, dev_high: np.ndarray,
                 prev_range: float, tick_mid2: float,
                 occs: Sequence[S14.Occ], mutant: str = "",
                 ) -> list[tuple[int, bool, str, dict[str, float]]]:
    """Measure every occurrence of one cell.  Pure function of prior bars.

    Returns ``(occ position in the input list, measured, miss, values)``.  The
    caller owns the Row objects; this function owns the causal law: every array
    is sliced to bars strictly before the decision bar and the effort peak p
    partitions the episode into the effort phase and the stall.
    """

    n = int(cell.n)
    out: list[tuple[int, bool, str, dict[str, float]]] = []
    mid = np.asarray(cell.rec.mid, np.float64)
    per_side: dict[int, dict[str, np.ndarray]] = {}
    for side in (1, -1):
        prior, new_ext, _armed = S7A.side_arrays(cell.geo, side)
        tag_a = "attack_low" if side > 0 else "attack_high"
        tag_y = "yield_low" if side > 0 else "yield_high"
        tag_b = "bar_low_mid2" if side > 0 else "bar_high_mid2"
        attack = np.asarray(flow_cell[tag_a], np.float64)[:n]
        yld = np.asarray(flow_cell[tag_y], np.float64)[:n]
        delta = np.asarray(flow_cell["delta"], np.float64)[:n]
        vol = np.asarray(flow_cell["vol"], np.float64)[:n]
        bext = np.asarray(flow_cell[tag_b], np.float64)[:n]
        din = -float(side) * delta
        dfade = float(side) * delta
        beyond = yld * (attack + 1.0)
        zero = np.zeros(1, np.float64)
        per_side[side] = {
            "prior": np.asarray(prior, np.float64),
            "marks": np.flatnonzero(np.asarray(new_ext, bool)).astype(np.int64),
            "din": din, "vol": vol, "bext": bext,
            "cs_effort": np.concatenate([zero, np.cumsum(
                np.where(din > 0.0, attack, 0.0))]),
            "cs_beyond": np.concatenate([zero, np.cumsum(beyond)]),
            "cs_vol": np.concatenate([zero, np.cumsum(vol)]),
            "cs_fade": np.concatenate([zero, np.cumsum(dfade)]),
        }

    for position, occ in enumerate(occs):
        bar = int(occ.bar)
        side = int(occ.side)
        arr = per_side[side]
        marks = arr["marks"]
        seen = marks[marks <= bar - 1]
        m = int(seen[-1]) if len(seen) else 0
        # The episode must hold an effort phase and a stall of at least one bar
        # each, or there is nothing ordered to measure.
        if bar - m < 3:
            out.append((position, False, MISS_SHORT, {}))
            continue
        # THE TURN.  p is where the CUMULATIVE aggression toward the extreme
        # peaks - the bar the push stopped adding to, "the moment control
        # changes hands" (your-mistakes p11).  The cumulative curve is used
        # rather than the per-bar maximum because a per-bar argmax picks the
        # FIRST of several equal spikes and would cut the effort phase off in
        # the middle of the push.  Ties on the cumulative curve take the LAST
        # bar, so a flat top ends the effort where the flow actually turns.
        cum_din = np.cumsum(arr["din"][m:bar])
        p = m + int(len(cum_din) - 1 - np.argmax(cum_din[::-1]))
        if p > bar - 2:
            # The effort peak IS the last prior bar: no stall has printed yet.
            out.append((position, False, MISS_NO_STALL, {}))
            continue
        extreme = float(arr["prior"][bar])
        # --- G1, the developing day range at the stamp -----------------
        low = float(dev_low[position])
        high = float(dev_high[position])
        span = high - low
        if not (span > 0.0 and prev_range > 0.0):
            out.append((position, False, MISS_NO_LEVELS, {}))
            continue
        dev_mid = 0.5 * (low + high)
        loc_prev = -float(side) * (extreme - dev_mid) / prev_range
        pos_in_range = (extreme - low) / span
        outerness = (1.0 - pos_in_range) if side > 0 else pos_in_range
        # --- G2 effort, G3 reward, both over the EFFORT PHASE [m, p] ---
        cs_e, cs_b = arr["cs_effort"], arr["cs_beyond"]
        effort_in = float(cs_e[p + 1] - cs_e[m])
        if mutant == MUTANT_POST:
            # THE MUTANT.  The reward window runs past the decision stamp by the
            # episode length, so the post-stamp flush into the zone - the very
            # excursion the 18-tick lesson calls a constituent of the setup - is
            # counted as reward for the effort.
            stop = min(n, bar + (bar - m))
            extension = float(cs_b[stop] - cs_b[m])
        else:
            extension = float(cs_b[p + 1] - cs_b[m])
        # --- G4, the fork: volume in the STALL against the effort phase -
        cs_v = arr["cs_vol"]
        eff_bars = float(p + 1 - m)
        stall_bars = float(bar - (p + 1))
        vol_eff = float(cs_v[p + 1] - cs_v[m]) / eff_bars
        vol_stall = float(cs_v[bar] - cs_v[p + 1]) / stall_bars
        vol_ratio = _slope_free_ratio(vol_stall, vol_eff)
        # --- G6, opposite aggression over the STALL --------------------
        cs_f = arr["cs_fade"]
        flip = float(cs_f[bar] - cs_f[p + 1])
        # --- the post-effort adverse excursion.  MEASURED, NEVER A GATE -
        window = arr["bext"][p + 1:bar]
        live = window[window > 0.0]
        if len(live):
            if side > 0:
                adverse = float(np.max(np.maximum(0.0, extreme - live)))
            else:
                adverse = float(np.max(np.maximum(0.0, live - extreme)))
        else:
            adverse = 0.0
        adv_ticks = adverse / tick_mid2 if tick_mid2 > 0.0 else float("nan")
        # --- C3, the unordered variants: whole episode, no p anchor ----
        effort_u = float(cs_e[bar] - cs_e[m])
        extension_u = float(cs_b[bar] - cs_b[m])
        flip_u = float(cs_f[bar] - cs_f[m])
        split = m + (bar - m) // 2
        first_bars = float(max(1, split - m))
        second_bars = float(max(1, bar - split))
        vol_ratio_u = _slope_free_ratio(
            float(cs_v[bar] - cs_v[split]) / second_bars,
            float(cs_v[split] - cs_v[m]) / first_bars)
        out.append((position, True, "", {
            "loc_prev": loc_prev, "outerness": outerness,
            "effort_in": effort_in, "extension": extension,
            "vol_ratio": vol_ratio, "flip": flip, "adv_ticks": adv_ticks,
            "effort_u": effort_u, "extension_u": extension_u,
            "vol_ratio_u": vol_ratio_u, "flip_u": flip_u,
            "episode_bars": float(bar - m), "effort_bars": eff_bars,
            "stall_bars": stall_bars,
        }))
    return out


def developing_range(day_lat: np.ndarray, day_cummin: np.ndarray,
                     day_cummax: np.ndarray, stamps: np.ndarray
                     ) -> tuple[np.ndarray, np.ndarray]:
    """Developing day low/high over every bar of the day STRICTLY before each
    stamp, accumulated across the day's phases."""

    idx = np.searchsorted(day_lat, np.asarray(stamps, np.int64), side="left")
    low = np.where(idx > 0, day_cummin[np.maximum(idx - 1, 0)], np.nan)
    high = np.where(idx > 0, day_cummax[np.maximum(idx - 1, 0)], np.nan)
    return low, high


def build_rows(streams: Sequence[S14.Stream], cells: Sequence[S8.Cell8],
               store: CTX.ContextStore, mutant: str = "",
               ) -> tuple[list[Row], dict[str, int]]:
    """Measure the whole stream.  One flow shard load per asset-day."""

    by_position = {cell.position: cell for cell in cells}
    counters = {name: 0 for name in MISS_BRANCHES}
    counters["measured"] = 0
    counters["rows"] = 0
    rows: list[Row] = []

    by_day: dict[tuple[str, int], list[S14.Stream]] = {}
    for stream in streams:
        by_day.setdefault((stream.asset, stream.d8), []).append(stream)

    index = 0
    for (asset, d8) in sorted(by_day):
        tick_mid2 = 2.0 * float(RAW_TICK[asset])
        payload = store.context_for(asset, int(d8))
        levels = payload.get("levels_prev")
        prev_range = (float(levels["session_range_mid2"])
                      if isinstance(levels, Mapping) else 0.0)
        # The day's whole quote path, all phases, for the developing range.
        lat_parts, mid_parts = [], []
        for stream in by_day[(asset, d8)]:
            cell = by_position[stream.cell]
            lat_parts.append(np.asarray(cell.rec.lat, np.int64))
            mid_parts.append(np.asarray(cell.rec.mid, np.float64))
        day_lat = np.concatenate(lat_parts)
        day_mid = np.concatenate(mid_parts)
        order = np.argsort(day_lat, kind="stable")
        day_lat = day_lat[order]
        day_cummin = np.minimum.accumulate(day_mid[order])
        day_cummax = np.maximum.accumulate(day_mid[order])
        try:
            flow_day = FLOW.load_flow(asset, int(d8))
        except FLOW.FlowStop:
            flow_day = {}
        for stream in by_day[(asset, d8)]:
            cell = by_position[stream.cell]
            key = (cell.rec.phase, int(cell.rec.phase_open_ts_ns))
            flow_cell = flow_day.get(key)
            stamps = np.asarray([int(cell.rec.lat[occ.bar])
                                 for occ in stream.occs], np.int64)
            if flow_cell is None or len(flow_cell["vol"]) < cell.n:
                open_ns = int(cell.rec.phase_open_ts_ns)
                for occ in stream.occs:
                    stamp = int(cell.rec.lat[occ.bar])
                    rows.append(Row(index, cell.asset, cell.phase, int(cell.d8),
                                    cell.position, int(occ.side), int(occ.bar),
                                    stamp, float((stamp - open_ns) / NANOS),
                                    float(occ.remaining_s),
                                    int(round(float(occ.x[0]))),
                                    float(occ.payoff), False, MISS_NO_FLOW))
                    counters[MISS_NO_FLOW] += 1
                    index += 1
                continue
            low, high = developing_range(day_lat, day_cummin, day_cummax, stamps)
            measured = measure_cell(cell, flow_cell, low, high, prev_range,
                                    tick_mid2, stream.occs, mutant)
            open_ns = int(cell.rec.phase_open_ts_ns)
            for position, ok, miss, values in measured:
                occ = stream.occs[position]
                elapsed = float((int(cell.rec.lat[occ.bar]) - open_ns) / NANOS)
                ordinal = int(round(float(occ.x[0])))
                rows.append(Row(index, cell.asset, cell.phase, int(cell.d8),
                                cell.position, int(occ.side), int(occ.bar),
                                int(cell.rec.lat[occ.bar]), elapsed,
                                float(occ.remaining_s), ordinal,
                                float(occ.payoff), bool(ok), miss, values))
                if ok:
                    counters["measured"] += 1
                else:
                    counters[miss] += 1
                index += 1
    counters["rows"] = len(rows)
    return rows, counters


# --------------------------------------------------------------------------
# The walk-forward threshold engine.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Fold:
    asset: str
    phase: str
    d8: int
    train_days: int
    train_rows: int
    cuts: dict[str, float]
    fitted: bool


def _ols(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Intercept and slope of ``y ~ x``, flat when x has no spread."""

    good = np.isfinite(x) & np.isfinite(y)
    xs, ys = x[good], y[good]
    if len(xs) < 3:
        return (float(np.mean(ys)) if len(ys) else 0.0), 0.0
    xm, ym = float(np.mean(xs)), float(np.mean(ys))
    var = float(np.sum((xs - xm) ** 2))
    if not var > 0.0:
        return ym, 0.0
    slope = float(np.sum((xs - xm) * (ys - ym)) / var)
    return ym - slope * xm, slope


def _column(rows: Sequence[Row], name: str) -> np.ndarray:
    return np.asarray([row.values.get(name, float("nan")) for row in rows],
                      np.float64)


def build_folds(rows: Sequence[Row], explore_days: Mapping[str, list[int]],
                ) -> tuple[dict[tuple[str, str, int], Fold], dict[str, list[int]]]:
    """One fold per (asset, phase, scoring day): cuts from strictly prior days."""

    scoring_days = {asset: [int(day) for day in days[MIN_PRIOR_DAYS:]]
                    for asset, days in explore_days.items()}
    measured = [row for row in rows if row.measured]
    by_stratum: dict[tuple[str, str], list[Row]] = {}
    for row in measured:
        by_stratum.setdefault((row.asset, row.phase), []).append(row)

    folds: dict[tuple[str, str, int], Fold] = {}
    for (asset, phase), stratum in sorted(by_stratum.items()):
        days = explore_days[asset]
        pool: dict[int, list[Row]] = {}
        for row in stratum:
            pool.setdefault(row.d8, []).append(row)
        history: list[Row] = []
        for position, day in enumerate(days):
            if position >= MIN_PRIOR_DAYS:
                cuts: dict[str, float] = {}
                fitted = len(history) >= MIN_TRAIN_ROWS
                if fitted:
                    loc = _column(history, "loc_prev")
                    eff = _column(history, "effort_in")
                    ext = _column(history, "extension")
                    vr = _column(history, "vol_ratio")
                    fl = _column(history, "flip")
                    eff_u = _column(history, "effort_u")
                    ext_u = _column(history, "extension_u")
                    vr_u = _column(history, "vol_ratio_u")
                    fl_u = _column(history, "flip_u")
                    a, b = _ols(eff, ext)
                    resid = ext - (a + b * eff)
                    au, bu = _ols(eff_u, ext_u)
                    resid_u = ext_u - (au + bu * eff_u)
                    cuts = {
                        "loc_q": float(np.percentile(loc, Q_LOCATION)),
                        "effort_q": float(np.percentile(eff, Q_EFFORT)),
                        "reward_a": a, "reward_b": b,
                        "reward_q": float(np.percentile(resid, Q_REWARD)),
                        "fork_q": float(np.percentile(vr, Q_FORK)),
                        "flip_q": float(np.percentile(fl, Q_FLIP)),
                        "effort_u_q": float(np.percentile(eff_u, Q_EFFORT)),
                        "reward_u_a": au, "reward_u_b": bu,
                        "reward_u_q": float(np.percentile(resid_u, Q_REWARD)),
                        "fork_u_q": float(np.percentile(vr_u, Q_FORK)),
                        "flip_u_q": float(np.percentile(fl_u, Q_FLIP)),
                    }
                folds[(asset, phase, int(day))] = Fold(
                    asset, phase, int(day), position, len(history), cuts, fitted)
            history.extend(pool.get(int(day), []))
    return folds, scoring_days


GATE_NAMES = ("G1", "G2", "G3", "G4A", "G4E", "G5", "G6")


def apply_gates(rows: Sequence[Row], folds: Mapping[tuple[str, str, int], Fold],
                scoring_days: Mapping[str, list[int]],
                ) -> tuple[list[Row], dict[str, np.ndarray], dict[str, int]]:
    """The gate booleans for every scoring-day measurable row."""

    score_set = {asset: set(days) for asset, days in scoring_days.items()}
    live = [row for row in rows
            if row.measured and row.d8 in score_set.get(row.asset, ())]
    keep: list[Row] = []
    flags = {name: [] for name in GATE_NAMES}
    scram = {name: [] for name in ("G2U", "G3U", "G4AU", "G6U")}
    counters = {name: 0 for name in GATE_NAMES}
    counters[MISS_NO_TRAIN] = 0
    for row in live:
        fold = folds.get((row.asset, row.phase, row.d8))
        if fold is None or not fold.fitted:
            counters[MISS_NO_TRAIN] += 1
            continue
        cut = fold.cuts
        v = row.values
        resid = v["extension"] - (cut["reward_a"] + cut["reward_b"] * v["effort_in"])
        resid_u = v["extension_u"] - (cut["reward_u_a"]
                                      + cut["reward_u_b"] * v["effort_u"])
        g1 = bool(v["loc_prev"] >= cut["loc_q"])
        g2 = bool(v["effort_in"] >= cut["effort_q"])
        g3 = bool(resid <= cut["reward_q"])
        g4a = bool(v["vol_ratio"] >= cut["fork_q"])
        g4e = not g4a
        g5 = bool(row.inzone_ordinal >= ORDINAL)
        g6 = bool(v["flip"] > 0.0 and v["flip"] >= cut["flip_q"])
        for name, value in (("G1", g1), ("G2", g2), ("G3", g3), ("G4A", g4a),
                            ("G4E", g4e), ("G5", g5), ("G6", g6)):
            flags[name].append(value)
            counters[name] += int(value)
        scram["G2U"].append(bool(v["effort_u"] >= cut["effort_u_q"]))
        scram["G3U"].append(bool(resid_u <= cut["reward_u_q"]))
        scram["G4AU"].append(bool(v["vol_ratio_u"] >= cut["fork_u_q"]))
        scram["G6U"].append(bool(v["flip_u"] > 0.0
                                 and v["flip_u"] >= cut["flip_u_q"]))
        keep.append(row)
    out = {name: np.asarray(values, bool) for name, values in flags.items()}
    out.update({name: np.asarray(values, bool) for name, values in scram.items()})
    counters["scored_rows"] = len(keep)
    return keep, out, counters


def ladder_masks(gates: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    """The cumulative ladder in the library's order, plus the branches."""

    n = len(gates["G1"])
    masks: dict[str, np.ndarray] = {"R0": np.ones(n, bool)}
    masks["R1"] = gates["G1"]
    masks["R2"] = masks["R1"] & gates["G2"]
    masks["R3"] = masks["R2"] & gates["G3"]
    masks["R4"] = masks["R3"] & gates["G4A"]
    masks["R5"] = masks["R4"] & gates["G5"]
    masks["R6"] = masks["R5"] & gates["G6"]
    masks["R4X"] = masks["R3"] & gates["G4E"]
    masks["G1REJECT"] = ~gates["G1"]
    # C3: the same six gates, unordered AND, every window order-free.
    masks["SCRAMBLE"] = (gates["G1"] & gates["G2U"] & gates["G3U"]
                         & gates["G4AU"] & gates["G5"] & gates["G6U"])
    return masks


# --------------------------------------------------------------------------
# Reporting one selection.
# --------------------------------------------------------------------------

def describe(rows: Sequence[Row], mask: np.ndarray, asset: str,
             scoring_days: int, certifiable: int, reachable: int = 0
             ) -> dict[str, object]:
    """One selection's line for one asset.

    ``coverage`` divides by the asset's whole certifiable-cell count, which
    spans days this unit never scores, so it is the conservative denominator the
    pre-registered floor is read against.  ``coverage_reachable`` divides by the
    cells a scoring day could actually reach, and is reported beside it so the
    ceiling on the first number is visible rather than implied.
    """

    picked = [row for row, take in zip(rows, mask)
              if take and row.asset == asset]
    n = len(picked)
    if not n:
        return {"n": 0, "cells": 0, "coverage": 0.0, "coverage_reachable": 0.0,
                "p_win": None,
                "wilson_low": None, "wilson_high": None, "mean_y": None,
                "median_y": None, "usd_per_asset_day": 0.0, "adv_ticks": None,
                "adv_ticks_med": None, "total_usd": 0.0, "days": scoring_days}
    y = np.asarray([row.y for row in picked], np.float64)
    adv = np.asarray([row.values.get("adv_ticks", float("nan"))
                      for row in picked], np.float64)
    hits = int((y > 0.0).sum())
    low, high = S1.wilson(hits, n)
    cells = len({row.cell for row in picked})
    return {
        "n": n, "cells": cells,
        "coverage": float(cells / certifiable) if certifiable else 0.0,
        "coverage_reachable": float(cells / reachable) if reachable else 0.0,
        "p_win": float(hits / n), "wilson_low": float(low),
        "wilson_high": float(high),
        "mean_y": float(y.mean()), "median_y": float(np.median(y)),
        "total_usd": float(y.sum()),
        "usd_per_asset_day": float(y.sum() / max(1, scoring_days)),
        "adv_ticks": float(np.nanmean(adv)) if np.any(np.isfinite(adv)) else None,
        "adv_ticks_med": (float(np.nanmedian(adv))
                          if np.any(np.isfinite(adv)) else None),
        "days": scoring_days,
    }


def ladder_table(rows: Sequence[Row], masks: Mapping[str, np.ndarray],
                 scoring_days: Mapping[str, list[int]],
                 certifiable: Mapping[str, int]) -> dict[str, object]:
    reachable = {asset: len({row.cell for row in rows if row.asset == asset})
                 for asset in ASSETS}
    table: dict[str, object] = {"reachable_cells": reachable}
    for name in BRANCHES:
        table[name] = {
            "label": LADDER_LABEL[name],
            **{asset: describe(rows, masks[name], asset,
                               len(scoring_days.get(asset, [])),
                               int(certifiable.get(asset, 0)),
                               int(reachable.get(asset, 0)))
               for asset in ASSETS},
        }
    return table


# --------------------------------------------------------------------------
# C1 and C4: block permutation, one draw matrix, own and family-adjusted p.
# --------------------------------------------------------------------------

STATS = ("mean_y", "p_win")


def block_permutation(rows: Sequence[Row], masks: Mapping[str, np.ndarray],
                      draws: int = BLOCK_DRAWS, seed: int = SEED,
                      ) -> dict[str, object]:
    """2000 asset-day block draws shared by C1 (own p) and C4 (max-stat p).

    Within each asset-day the day's whole occurrence pool is permuted, and each
    rung's own per-day count is taken off the front of the permutation.  The
    day composition and every rung's size are therefore held fixed; only WHICH
    occurrences the rung picked is randomised.
    """

    names = [name for name in BRANCHES if name != "R0"]
    cells = [(name, asset) for name in names for asset in ASSETS]
    order = {key: position for position, key in enumerate(cells)}
    sums = {stat: np.zeros((draws, len(cells)), np.float64) for stat in STATS}
    counts = np.zeros((draws, len(cells)), np.float64)
    day_index: dict[tuple[str, int], list[int]] = {}
    for position, row in enumerate(rows):
        day_index.setdefault((row.asset, row.d8), []).append(position)
    rng = np.random.default_rng(seed)
    y_all = np.asarray([row.y for row in rows], np.float64)

    for (asset, _d8), members in sorted(day_index.items()):
        idx = np.asarray(members, np.int64)
        size = len(idx)
        y_day = y_all[idx]
        perm = np.argsort(rng.random((draws, size)), axis=1)
        y_perm = y_day[perm]
        cum_y = np.cumsum(y_perm, axis=1)
        cum_hit = np.cumsum(y_perm > 0.0, axis=1)
        for name in names:
            take = int(masks[name][idx].sum())
            if not take:
                continue
            column = order[(name, asset)]
            sums["mean_y"][:, column] += cum_y[:, take - 1]
            sums["p_win"][:, column] += cum_hit[:, take - 1]
            counts[:, column] += float(take)

    observed: dict[str, dict[str, float]] = {}
    for name in names:
        for asset in ASSETS:
            column = order[(name, asset)]
            picked = [row for row, take in zip(rows, masks[name])
                      if take and row.asset == asset]
            if not picked:
                observed[f"{asset}/{name}"] = {}
                continue
            y = np.asarray([row.y for row in picked], np.float64)
            observed[f"{asset}/{name}"] = {
                "mean_y": float(y.mean()),
                "p_win": float((y > 0.0).mean()),
                "column": float(column),
            }

    out: dict[str, object] = {"draws": draws, "seed": seed,
                              "blocks": len(day_index), "by_line": {}}
    for stat in STATS:
        with np.errstate(invalid="ignore", divide="ignore"):
            draw_stat = np.where(counts > 0, sums[stat] / np.maximum(counts, 1.0),
                                 np.nan)
        with warnings.catch_warnings():
            # A rung that picked nothing anywhere leaves an all-NaN column; it
            # is reported as absent, not as a number.
            warnings.simplefilter("ignore", RuntimeWarning)
            centre = np.nanmean(draw_stat, axis=0)
            spread = np.nanstd(draw_stat, axis=0)
        spread = np.where(spread > 0.0, spread, np.nan)
        z_draw = (draw_stat - centre) / spread
        # The family-wise maximum over every rung x asset cell in one draw.
        live = np.isfinite(z_draw).any(axis=0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            z_max = np.nanmax(np.where(np.isfinite(z_draw), z_draw, -np.inf),
                              axis=1)
        for name in names:
            for asset in ASSETS:
                key = f"{asset}/{name}"
                block = observed.get(key) or {}
                entry = out["by_line"].setdefault(key, {})
                if not block:
                    entry[stat] = None
                    continue
                column = int(block["column"])
                value = float(block[stat])
                column_draws = draw_stat[:, column]
                good = np.isfinite(column_draws)
                if not good.any() or not live[column]:
                    entry[stat] = None
                    continue
                p_own = float((column_draws[good] >= value).sum() + 1) / \
                    float(good.sum() + 1)
                z_obs = ((value - centre[column]) / spread[column]
                         if math.isfinite(spread[column]) else float("nan"))
                if math.isfinite(z_obs):
                    p_adj = float((z_max >= z_obs).sum() + 1) / float(draws + 1)
                else:
                    p_adj = None
                entry[stat] = {
                    "observed": value,
                    "null_mean": float(centre[column]),
                    "null_sd": (float(spread[column])
                                if math.isfinite(spread[column]) else None),
                    "z": float(z_obs) if math.isfinite(z_obs) else None,
                    "p_own": p_own, "p_max_adjusted": p_adj,
                }
    return out


# --------------------------------------------------------------------------
# C2: the sweep-13 lateness-matched control, applied to one selection.
# --------------------------------------------------------------------------

def lateness_control(rows: Sequence[Row], mask: np.ndarray,
                     pool: Sequence[Row], draws: int, seed: int = SEED,
                     ) -> dict[str, object]:
    """The sweep-13 phase-time twin law, carried over to cash.

    For each selected occurrence: donors from the same asset and phase, a
    DIFFERENT day, phase-elapsed within 300 s and remaining within 300 s.  One
    donor is drawn per occurrence per draw; the draw's mean Y and P(Y>0) are the
    null.  Identical to sweep 13's ``time_match`` but reading the banked cert
    instead of the post-entry extension flag.
    """

    buckets: dict[tuple[str, str], tuple[np.ndarray, list[Row]]] = {}
    grouped: dict[tuple[str, str], list[Row]] = {}
    for row in pool:
        grouped.setdefault((row.asset, row.phase), []).append(row)
    for key, members in grouped.items():
        members.sort(key=lambda item: item.elapsed_s)
        buckets[key] = (np.asarray([item.elapsed_s for item in members],
                                   np.float64), members)

    picked = [row for row, take in zip(rows, mask) if take]
    pools: list[np.ndarray] = []
    sizes: list[int] = []
    for row in picked:
        stamps, members = buckets.get((row.asset, row.phase),
                                      (np.zeros(0, np.float64), []))
        low = int(np.searchsorted(stamps, row.elapsed_s - LATENESS_WINDOW_S,
                                  "left"))
        high = int(np.searchsorted(stamps, row.elapsed_s + LATENESS_WINDOW_S,
                                   "right"))
        donors = [item.y for item in members[low:high]
                  if item.d8 != row.d8
                  and abs(item.remaining_s - row.remaining_s) <= LATENESS_WINDOW_S]
        pools.append(np.asarray(donors, np.float64))
        sizes.append(len(donors))

    matched = sum(1 for arr in pools if len(arr))
    if not matched:
        return {"draws": draws, "entries": len(picked), "entries_matched": 0,
                "match_share": 0.0, "mean_y": None, "p_win": None,
                "p_mean_y": None, "p_p_win": None, "pool_median": None}
    rng = np.random.default_rng(seed)
    live = [arr for arr in pools if len(arr)]
    # The ragged donor pools are laid flat with offsets so all the draws are one
    # gather: one donor per matched occurrence per draw, uniform within its own
    # pool, exactly the sweep-13 draw.
    flat = np.concatenate(live)
    lengths = np.asarray([len(arr) for arr in live], np.int64)
    offsets = np.concatenate([[0], np.cumsum(lengths)[:-1]]).astype(np.int64)
    picks = offsets + np.minimum(
        (rng.random((draws, len(live))) * lengths).astype(np.int64), lengths - 1)
    taken = flat[picks]
    draw_mean = taken.mean(axis=1)
    draw_win = (taken > 0.0).mean(axis=1)
    y = np.asarray([row.y for row in picked], np.float64)
    obs_mean = float(y.mean())
    obs_win = float((y > 0.0).mean())
    # Per asset as well as pooled: the ruling is made per asset, so the control
    # it is ruled against has to be per asset too.  The donor law already
    # matches within (asset, phase); this only splits the statistic.
    live_assets = [row.asset for row, arr in zip(picked, pools) if len(arr)]
    by_asset: dict[str, object] = {}
    for asset in ASSETS:
        pick = np.asarray([name == asset for name in live_assets], bool)
        if not pick.any():
            by_asset[asset] = {"n": 0}
            continue
        own = taken[:, pick]
        own_obs = np.asarray([row.y for row, arr in zip(picked, pools)
                              if len(arr) and row.asset == asset], np.float64)
        asset_mean = own.mean(axis=1)
        asset_win = (own > 0.0).mean(axis=1)
        obs_a = float(own_obs.mean())
        obs_w = float((own_obs > 0.0).mean())
        by_asset[asset] = {
            "n": int(pick.sum()), "observed_mean_y": obs_a,
            "observed_p_win": obs_w,
            "mean_y": float(asset_mean.mean()), "p_win": float(asset_win.mean()),
            "mean_y_p05": float(np.percentile(asset_mean, 5)),
            "mean_y_p95": float(np.percentile(asset_mean, 95)),
            "p_mean_y": float((asset_mean >= obs_a).sum() + 1) / float(draws + 1),
            "p_p_win": float((asset_win >= obs_w).sum() + 1) / float(draws + 1),
        }
    return {
        "draws": draws, "entries": len(picked), "entries_matched": matched,
        "match_share": float(matched / max(1, len(picked))),
        "window_s": LATENESS_WINDOW_S,
        "pool_median": _q(sizes, 50), "pool_min": (min(sizes) if sizes else None),
        "observed_mean_y": obs_mean, "observed_p_win": obs_win,
        "mean_y": float(draw_mean.mean()), "p_win": float(draw_win.mean()),
        "mean_y_p05": float(np.percentile(draw_mean, 5)),
        "mean_y_p95": float(np.percentile(draw_mean, 95)),
        "p_mean_y": float((draw_mean >= obs_mean).sum() + 1) / float(draws + 1),
        "p_p_win": float((draw_win >= obs_win).sum() + 1) / float(draws + 1),
        "by_asset": by_asset,
    }


# --------------------------------------------------------------------------
# The sweep-16 fixed-hold cross price, final rung only.
# --------------------------------------------------------------------------

def fixhold_price(rows: Sequence[Row], mask: np.ndarray,
                  records: Sequence[S1.CellRec]) -> dict[str, object]:
    """Y_1800 for the FINAL RUNG ROWS ONLY, through sweep 16's frozen machinery.

    Sweep 16 owns the horizon plane; this never rebuilds it.  Only the selected
    rows are re-priced, one capped grid call per (cell, side), with the per-entry
    close min(entry + 1800 s, phase close) and the frozen -900 wall.
    """

    try:
        import sweep16 as S16
    except Exception as error:                      # pragma: no cover
        return {"available": False, "reason": f"import failed: {error}"}
    if not SWEEP16_PATH.is_file():
        return {"available": False, "reason": "sweep 16 has not landed"}

    picked = [row for row, take in zip(rows, mask) if take]
    if not picked:
        return {"available": True, "n": 0, "by_asset": {}}
    by_cell: dict[int, list[Row]] = {}
    for row in picked:
        by_cell.setdefault(row.cell, []).append(row)
    values: dict[int, float] = {}
    walls = 0
    priced = 0
    by_day: dict[tuple[str, int], list[int]] = {}
    for position in sorted(by_cell):
        rec = records[position]
        by_day.setdefault((rec.asset, rec.d8), []).append(position)
    for (asset, d8) in sorted(by_day):
        shard = M.load_shard(asset, int(d8))
        by_text = {cell.text: cell for cell in shard.cells}
        for position in by_day[(asset, d8)]:
            rec = records[position]
            cell = by_text.get(rec.text)
            if cell is None:
                continue
            index = shard.cell_index(cell)
            lat = np.asarray(rec.lat, np.int64)
            _pos, mid, bid, ask = M.bar_series(index, lat)
            cost = (ask - bid) * float(index.multiplier) / 1e9 + S16.FEE_USD
            close_ns = int(rec.phase_close_ts_ns)
            closes = np.minimum(lat + FIXHOLD_S * NANOS, close_ns)
            for side in (1, -1):
                wanted = [row for row in by_cell[position] if row.side == side]
                if not wanted:
                    continue
                grid = S16.outcomes_grid_capped(index, lat, side, closes,
                                                entry_mid2=mid, cost_usd=cost)
                take = grid["input_index"]
                cert = np.full(len(lat), np.nan, np.float64)
                wall = np.zeros(len(lat), bool)
                if len(take):
                    cert[take] = grid["cert_close_usd"]
                    wall[take] = grid["wall_hit"]
                for row in wanted:
                    value = float(cert[row.bar])
                    if math.isfinite(value):
                        values[row.index] = value
                        walls += int(wall[row.bar])
                        priced += 1
    out: dict[str, object] = {"available": True, "horizon_s": FIXHOLD_S,
                              "n": len(picked), "priced": priced, "walls": walls,
                              "by_asset": {}}
    for asset in ASSETS:
        members = [row for row in picked if row.asset == asset]
        y18 = np.asarray([values[row.index] for row in members
                          if row.index in values], np.float64)
        yc = np.asarray([row.y for row in members if row.index in values],
                        np.float64)
        if not len(y18):
            out["by_asset"][asset] = {"n": 0}
            continue
        hits = int((y18 > 0.0).sum())
        low, high = S1.wilson(hits, len(y18))
        out["by_asset"][asset] = {
            "n": int(len(y18)), "mean_y1800": float(y18.mean()),
            "median_y1800": float(np.median(y18)),
            "p_win_1800": float(hits / len(y18)),
            "wilson_low": float(low), "wilson_high": float(high),
            "mean_y_close": float(yc.mean()),
            "delta_mean": float(y18.mean() - yc.mean()),
        }
    return out


# --------------------------------------------------------------------------
# The decision table.
# --------------------------------------------------------------------------

def _bound(name: str, ok: bool, detail: str) -> dict[str, object]:
    return {"bound": name, "pass": bool(ok), "detail": detail}


def decide(table: Mapping[str, object], nulls: Mapping[str, object],
           lateness: Mapping[str, object]) -> dict[str, object]:
    by_asset: dict[str, object] = {}
    for asset in ASSETS:
        final = table[FINAL_RUNG][asset]
        line = nulls["by_line"].get(f"{asset}/{FINAL_RUNG}", {})
        mean_block = line.get("mean_y") or {}
        win_block = line.get("p_win") or {}
        p_adj = mean_block.get("p_max_adjusted")
        p_own = mean_block.get("p_own")
        # The lateness control is read PER ASSET; the pooled p would let one
        # asset's rows decide another asset's bound.
        late_block = (lateness.get("by_asset") or {}).get(asset) or {}
        p_late = late_block.get("p_mean_y")
        bounds = [
            _bound("A n >= 30", final["n"] >= MIN_POWER_N, f"n {final['n']}"),
            _bound("B coverage >= 0.15",
                   (final["coverage"] or 0.0) >= COVERAGE_FLOOR,
                   f"coverage {final['coverage']:.3f}"),
            _bound("C Wilson lower >= 0.55",
                   (final["wilson_low"] or 0.0) >= WILSON_FLOOR,
                   f"lower {final['wilson_low']}"),
            _bound("D C1 own p (mean Y) <= 0.05",
                   p_own is not None and p_own <= ADJUSTED_P_CEILING,
                   f"p_own {p_own}"),
            _bound("E C4 max-adjusted p (mean Y) <= 0.05",
                   p_adj is not None and p_adj <= ADJUSTED_P_CEILING,
                   f"p_adj {p_adj}"),
            _bound("F C2 lateness p (mean Y) <= 0.05",
                   p_late is not None and p_late <= ADJUSTED_P_CEILING,
                   f"p_lateness {p_late}"),
        ]
        by_asset[asset] = {
            "n": final["n"], "coverage": final["coverage"],
            "mean_y": final["mean_y"], "p_win": final["p_win"],
            "wilson_low": final["wilson_low"],
            "usd_per_asset_day": final["usd_per_asset_day"],
            "adv_ticks": final["adv_ticks"],
            "lateness_donor_mean_y": late_block.get("mean_y"),
            "p_own": p_own, "adjusted_null_p": p_adj, "p_lateness": p_late,
            "p_win_adjusted": win_block.get("p_max_adjusted"),
            "bounds": bounds,
            "bounds_failed": [row["bound"] for row in bounds if not row["pass"]],
            "passes": all(row["pass"] for row in bounds),
        }

    powered = [asset for asset in DECIDING
               if table[FINAL_RUNG][asset]["n"] >= MIN_POWER_N]
    live = [asset for asset in DECIDING if by_asset[asset]["passes"]]

    # PARTIAL-GATE search: a strict subset rung clearing the same bounds, or
    # matching the final rung's mean Y where the final rung does clear them.
    partial: list[dict[str, object]] = []
    for asset in DECIDING:
        final = table[FINAL_RUNG][asset]
        for name in SUBSET_RUNGS:
            block = table[name][asset]
            line = nulls["by_line"].get(f"{asset}/{name}", {})
            mean_block = line.get("mean_y") or {}
            p_adj = mean_block.get("p_max_adjusted")
            clears = bool(
                block["n"] >= MIN_POWER_N
                and (block["coverage"] or 0.0) >= COVERAGE_FLOOR
                and (block["wilson_low"] or 0.0) >= WILSON_FLOOR
                and p_adj is not None and p_adj <= ADJUSTED_P_CEILING)
            carries = bool(
                block["n"] >= MIN_POWER_N and final["n"]
                and block["mean_y"] is not None and final["mean_y"] is not None
                and block["mean_y"] >= final["mean_y"])
            if clears or (live and asset in live and carries):
                partial.append({
                    "asset": asset, "subset": name,
                    "label": LADDER_LABEL[name],
                    "n": block["n"], "coverage": block["coverage"],
                    "mean_y": block["mean_y"], "wilson_low": block["wilson_low"],
                    "p_max_adjusted": p_adj,
                    "delta_mean_y_vs_final": (
                        None if (block["mean_y"] is None
                                 or final["mean_y"] is None)
                        else float(block["mean_y"] - final["mean_y"])),
                    "delta_n_vs_final": int(block["n"] - final["n"]),
                    "reason": "clears the bounds" if clears else "carries the effect",
                })

    if not powered:
        verdict = "UNPOWERED"
    elif live:
        verdict = "PARTIAL-GATE" if partial else "GRAMMAR-LIVE"
    elif partial:
        verdict = "PARTIAL-GATE"
    else:
        verdict = "NONE"
    return {
        "verdict": verdict, "by_asset": by_asset,
        "powered_deciding_assets": powered, "passing_deciding_assets": live,
        "partial_subsets": partial,
        "unpowered_note": ("R6 n is under 30 on every deciding asset; the "
                           "grammar is not measurable at this coverage"
                           if verdict == "UNPOWERED" else ""),
    }


def order_effect(table: Mapping[str, object]) -> dict[str, object]:
    """C3's headline: what the ORDER bought, rung R6 against the scrambled AND."""

    out: dict[str, object] = {}
    for asset in ASSETS:
        ordered = table[FINAL_RUNG][asset]
        scrambled = table["SCRAMBLE"][asset]
        out[asset] = {
            "ordered_n": ordered["n"], "scrambled_n": scrambled["n"],
            "ordered_mean_y": ordered["mean_y"],
            "scrambled_mean_y": scrambled["mean_y"],
            "ordered_p_win": ordered["p_win"],
            "scrambled_p_win": scrambled["p_win"],
            "delta_mean_y": (None if (ordered["mean_y"] is None
                                      or scrambled["mean_y"] is None)
                             else float(ordered["mean_y"] - scrambled["mean_y"])),
            "delta_p_win": (None if (ordered["p_win"] is None
                                     or scrambled["p_win"] is None)
                            else float(ordered["p_win"] - scrambled["p_win"])),
        }
    return out


# --------------------------------------------------------------------------
# The reproduction gate.  The unit refuses to run unless the stream matches.
# --------------------------------------------------------------------------

def reproduce(plane: S9.Plane, counters: Mapping[str, int],
              scoring_days: Mapping[str, list[int]]) -> dict[str, object]:
    live_counters = {name: int(plane.counters[name])
                     for name in sorted(REPRO_COUNTERS)}
    live_cells = {asset: int(plane.certifiable.get(asset, 0)) for asset in ASSETS}
    live_days = {asset: len(scoring_days.get(asset, [])) for asset in ASSETS}
    checks = {
        "rows": (int(plane.n), REPRO_ROWS),
        "certifiable": (live_cells, dict(REPRO_CERTIFIABLE)),
        "counters": (live_counters, dict(REPRO_COUNTERS)),
        "cells_with_rows": (int(counters["streams"]), REPRO_CELLS_WITH_ROWS),
        "scoring_days": (live_days, dict(REPRO_SCORING_DAYS)),
    }
    matches = all(live == banked for live, banked in checks.values())
    return {"checks": {name: {"live": live, "banked": banked,
                              "match": live == banked}
                       for name, (live, banked) in checks.items()},
            "matches": bool(matches)}


# --------------------------------------------------------------------------
# Printing.
# --------------------------------------------------------------------------

def _n(value: object, width: int = 8, digits: int = 3) -> str:
    if value is None:
        return "-".rjust(width)
    if isinstance(value, bool):
        return ("yes" if value else "no").rjust(width)
    if isinstance(value, (int, np.integer)):
        return str(int(value)).rjust(width)
    number = float(value)
    if not math.isfinite(number):
        return "-".rjust(width)
    return f"{number:.{digits}f}".rjust(width)


def print_repro(block: Mapping[str, object]) -> None:
    print("\nSWEEP-14 STREAM REPRODUCTION GATE")
    for name, row in block["checks"].items():
        print(f"  {name:<16}live {str(row['live']):<66} banked "
              f"{str(row['banked'])}")
        print(f"  {'':<16}match: {row['match']}")
    print(f"  matches: {block['matches']}")


def print_measurement(counters: Mapping[str, int],
                      gate_counters: Mapping[str, int],
                      rows: Sequence[Row]) -> None:
    print("\nEPISODE MEASUREMENT")
    print(f"  stream rows          {counters['rows']}")
    print(f"  measured             {counters['measured']}")
    for name in MISS_BRANCHES:
        if name in counters:
            print(f"  dropped {name:<13}{counters[name]}")
    print(f"  dropped {MISS_NO_TRAIN:<13}"
          f"{gate_counters.get(MISS_NO_TRAIN, 0)}  (scoring-day rows without a "
          f"fitted fold)")
    print(f"  scored rows          {gate_counters.get('scored_rows', 0)}")
    if rows:
        for name in ("episode_bars", "effort_bars", "stall_bars", "adv_ticks"):
            column = _column(rows, name)
            print(f"  {name:<20}median {_n(_q(column, 50))}  p90 "
                  f"{_n(_q(column, 90))}")


def print_gate_counters(gates: Mapping[str, np.ndarray]) -> None:
    print("\nGATE COUNTERS (scoring-day measurable rows)")
    total = len(gates["G1"])
    print(f"  {'gate':<6}{'fires':>8}{'share':>8}")
    for name in GATE_NAMES:
        fires = int(gates[name].sum())
        print(f"  {name:<6}{fires:>8}{fires / max(1, total):>8.3f}")
    for name in ("G2U", "G3U", "G4AU", "G6U"):
        fires = int(gates[name].sum())
        print(f"  {name:<6}{fires:>8}{fires / max(1, total):>8.3f}   (C3 "
              f"unordered variant)")
    print(f"  rows  {total:>8}")


def print_ladder(table: Mapping[str, object]) -> None:
    head = (f"  {'rung':<9}{'asset':<5}{'n':>6}{'cells':>7}{'cover':>7}"
            f"{'cvReach':>8}{'P(Y>0)':>8}{'wLow':>7}{'wHigh':>7}{'meanY':>9}"
            f"{'medY':>8}{'usd/day':>9}{'advTk':>7}")
    print(f"\n  reachable cells on scoring days: {table['reachable_cells']} "
          f"(the ceiling on the 'cover' column, whose denominator is every "
          f"certifiable cell {dict(REPRO_CERTIFIABLE)})")
    for name in BRANCHES:
        block = table[name]
        print(f"\nLADDER {name} - {block['label']}")
        print(head)
        for asset in ASSETS:
            row = block[asset]
            print(f"  {name:<9}{asset:<5}{_n(row['n'], 6)}{_n(row['cells'], 7)}"
                  f"{_n(row['coverage'], 7)}{_n(row['coverage_reachable'], 8)}"
                  f"{_n(row['p_win'], 8)}"
                  f"{_n(row['wilson_low'], 7)}{_n(row['wilson_high'], 7)}"
                  f"{_n(row['mean_y'], 9, 2)}{_n(row['median_y'], 8, 2)}"
                  f"{_n(row['usd_per_asset_day'], 9, 1)}"
                  f"{_n(row['adv_ticks'], 7, 1)}")


def print_nulls(nulls: Mapping[str, object]) -> None:
    print(f"\nC1 / C4 BLOCK PERMUTATION  ({nulls['draws']} draws over "
          f"{nulls['blocks']} asset-day blocks, seed {nulls['seed']})")
    print(f"  {'line':<18}{'stat':<8}{'obs':>10}{'null':>10}{'z':>8}"
          f"{'p_own':>8}{'p_adj':>8}")
    for name in BRANCHES:
        if name == "R0":
            continue
        for asset in ASSETS:
            key = f"{asset}/{name}"
            entry = nulls["by_line"].get(key, {})
            for stat in STATS:
                block = entry.get(stat)
                if not block:
                    continue
                print(f"  {key:<18}{stat:<8}{_n(block['observed'], 10, 3)}"
                      f"{_n(block['null_mean'], 10, 3)}{_n(block['z'], 8, 2)}"
                      f"{_n(block['p_own'], 8, 4)}"
                      f"{_n(block['p_max_adjusted'], 8, 4)}")


def print_lateness(law: Mapping[str, object], wide: Mapping[str, object]) -> None:
    print("\nC2 LATENESS-MATCHED CONTROL on the final rung (sweep-13 law)")
    for name, block in (("law-faithful", law), ("p-value", wide)):
        print(f"  {name:<14}draws {block['draws']:<6} entries "
              f"{block['entries']:<5} matched {block['entries_matched']:<5} "
              f"share {_n(block.get('match_share'), 6)}  pool median "
              f"{_n(block.get('pool_median'), 6, 1)}")
        print(f"  {'':<14}observed meanY {_n(block.get('observed_mean_y'), 9, 2)}"
              f"  donor meanY {_n(block.get('mean_y'), 9, 2)}"
              f"  p {_n(block.get('p_mean_y'), 7, 4)}")
        print(f"  {'':<14}observed P(Y>0) {_n(block.get('observed_p_win'), 8, 3)}"
              f"  donor P(Y>0) {_n(block.get('p_win'), 8, 3)}"
              f"  p {_n(block.get('p_p_win'), 7, 4)}")
    print(f"  per asset (the ruling reads these, never the pooled line)")
    print(f"    {'asset':<6}{'n':>6}{'obs meanY':>11}{'donor meanY':>13}"
          f"{'p meanY':>9}{'obs P':>8}{'donor P':>9}{'p P':>8}")
    for asset in ASSETS:
        row = (wide.get("by_asset") or {}).get(asset) or {}
        if not row.get("n"):
            print(f"    {asset:<6}{_n(0, 6)}")
            continue
        print(f"    {asset:<6}{_n(row['n'], 6)}"
              f"{_n(row['observed_mean_y'], 11, 2)}{_n(row['mean_y'], 13, 2)}"
              f"{_n(row['p_mean_y'], 9, 4)}{_n(row['observed_p_win'], 8, 3)}"
              f"{_n(row['p_win'], 9, 3)}{_n(row['p_p_win'], 8, 4)}")


def print_order(block: Mapping[str, object]) -> None:
    print("\nC3 SCRAMBLED-GATE CONTROL: does the ORDER add anything")
    print(f"  {'asset':<6}{'ord n':>7}{'scr n':>7}{'ord meanY':>11}"
          f"{'scr meanY':>11}{'d meanY':>10}{'ord P':>8}{'scr P':>8}{'d P':>8}")
    for asset in ASSETS:
        row = block[asset]
        print(f"  {asset:<6}{_n(row['ordered_n'], 7)}{_n(row['scrambled_n'], 7)}"
              f"{_n(row['ordered_mean_y'], 11, 2)}"
              f"{_n(row['scrambled_mean_y'], 11, 2)}"
              f"{_n(row['delta_mean_y'], 10, 2)}"
              f"{_n(row['ordered_p_win'], 8, 3)}"
              f"{_n(row['scrambled_p_win'], 8, 3)}"
              f"{_n(row['delta_p_win'], 8, 3)}")


def print_fixhold(block: Mapping[str, object]) -> None:
    print("\nSWEEP-16 CROSS PRICE: final rung under the 1800 s fixed hold")
    if not block.get("available"):
        print(f"  skipped: {block.get('reason')}")
        return
    print(f"  priced {block.get('priced')} of {block.get('n')} final-rung rows; "
          f"walls {block.get('walls')}")
    print(f"  {'asset':<6}{'n':>6}{'meanY1800':>11}{'medY1800':>10}"
          f"{'P(Y>0)':>8}{'wLow':>7}{'meanYclose':>12}{'delta':>9}")
    for asset in ASSETS:
        row = block["by_asset"].get(asset, {})
        if not row.get("n"):
            print(f"  {asset:<6}{_n(0, 6)}")
            continue
        print(f"  {asset:<6}{_n(row['n'], 6)}{_n(row['mean_y1800'], 11, 2)}"
              f"{_n(row['median_y1800'], 10, 2)}{_n(row['p_win_1800'], 8, 3)}"
              f"{_n(row['wilson_low'], 7, 3)}{_n(row['mean_y_close'], 12, 2)}"
              f"{_n(row['delta_mean'], 9, 2)}")


def print_decision(block: Mapping[str, object]) -> None:
    print(f"\nDECISION TABLE - {block['verdict']}")
    if block.get("unpowered_note"):
        print(f"  {block['unpowered_note']}")
    for asset in ASSETS:
        row = block["by_asset"][asset]
        tag = "DECIDING" if asset in DECIDING else "report-only"
        print(f"\n  {asset} ({tag})  n {row['n']}  coverage "
              f"{_n(row['coverage'], 6)}  meanY {_n(row['mean_y'], 9, 2)}  "
              f"usd/day {_n(row['usd_per_asset_day'], 9, 1)}  advTk "
              f"{_n(row['adv_ticks'], 7, 1)}")
        for bound in row["bounds"]:
            print(f"    [{'PASS' if bound['pass'] else 'FAIL'}] "
                  f"{bound['bound']:<34}{bound['detail']}")
    if block["partial_subsets"]:
        print("\n  PARTIAL-GATE subsets found:")
        for row in block["partial_subsets"]:
            print(f"    {row['asset']}/{row['subset']:<9}{row['label']:<28}"
                  f"n {row['n']:<5} meanY {_n(row['mean_y'], 9, 2)}  "
                  f"d meanY vs R6 {_n(row['delta_mean_y_vs_final'], 9, 2)}  "
                  f"d n {row['delta_n_vs_final']:<6} p_adj "
                  f"{_n(row['p_max_adjusted'], 7, 4)}  ({row['reason']})")


# --------------------------------------------------------------------------
# Selftest.  A planted episode, a planted exhaustion case, the excursion law.
# --------------------------------------------------------------------------

def _check(name: str, ok: bool, detail: str = "") -> tuple[str, bool, str]:
    return (name, bool(ok), detail)


@dataclass(slots=True)
class Fixture:
    """A hand-built cell with a known episode, sufficient for measure_cell."""

    cell: object
    flow: dict[str, np.ndarray]
    occs: list[object]


class _FakeRec:
    def __init__(self, mid: np.ndarray, lat: np.ndarray) -> None:
        self.mid = mid
        self.lat = lat
        self.phase = "1"
        self.phase_open_ts_ns = int(lat[0])
        self.asset = "NKD"
        self.d8 = 20220101
        self.text = "fixture"


class _FakeGeo:
    def __init__(self, prior_low, new_low, prior_high, new_high) -> None:
        self.prior_low = prior_low
        self.new_low = new_low
        self.prior_high = prior_high
        self.new_high = new_high
        self.arm_low = new_low
        self.arm_high = new_high


class _FakeCell:
    def __init__(self, rec, geo, n) -> None:
        self.rec = rec
        self.geo = geo
        self.n = n
        self.position = 0
        self.asset = "NKD"
        self.d8 = 20220101
        self.phase = "1"


class _FakeOcc:
    def __init__(self, bar: int, side: int) -> None:
        self.bar = bar
        self.side = side


def _fixture(bars: int, decision: int, extreme_bar: int, *,
             effort_bar: int, effort_size: float, beyond_ticks: float,
             stall_vol: float, effort_vol: float, flip_delta: float,
             adverse_ticks: float, post_beyond: float = 0.0,
             tick_mid2: float = 10.0) -> Fixture:
    """One planted long-side episode.  Every knob is a mechanism, not a number.

    ``beyond_ticks`` is the reward the effort bought inside the effort phase;
    ``post_beyond`` is fresh penetration printed AFTER the decision stamp - the
    flush the 18-tick lesson calls a constituent of the setup.  The honest law
    never reads it; the mutant does.
    """

    lat = (np.arange(bars, dtype=np.int64) * 60 * NANOS + 1_600_000_000 * NANOS)
    mid = np.full(bars, 1000.0, np.float64)
    mid[extreme_bar] = 900.0
    mid[extreme_bar + 1:] = 950.0
    prior_low = np.empty(bars, np.float64)
    prior_low[0] = mid[0]
    prior_low[1:] = np.minimum.accumulate(mid)[:-1]
    new_low = np.zeros(bars, bool)
    new_low[extreme_bar] = True
    prior_high = np.maximum.accumulate(mid)
    new_high = np.zeros(bars, bool)
    geo = _FakeGeo(prior_low, new_low, prior_high, new_high)
    rec = _FakeRec(mid, lat)
    cell = _FakeCell(rec, geo, bars)

    attack = np.zeros(bars, np.float64)
    delta = np.zeros(bars, np.float64)
    vol = np.zeros(bars, np.float64)
    beyond = np.zeros(bars, np.float64)
    # The effort phase: heavy selling into the low.
    for bar in range(extreme_bar, effort_bar + 1):
        attack[bar] = effort_size
        delta[bar] = -effort_size
        vol[bar] = effort_vol
    beyond[effort_bar] = beyond_ticks
    # The stall: volume behaviour and the aggression flip.
    for bar in range(effort_bar + 1, decision):
        vol[bar] = stall_vol
        delta[bar] = flip_delta
        attack[bar] = 1.0
    # Post-stamp: fresh penetration the honest law must never see.
    for bar in range(decision, bars):
        vol[bar] = stall_vol
        beyond[bar] = post_beyond
        attack[bar] = effort_size
        delta[bar] = -effort_size
    # yield = beyond_ticks / (attack + 1); measure_cell inverts it exactly.
    yld = beyond / (attack + 1.0)
    extreme = float(prior_low[decision])
    bar_low = np.full(bars, extreme + 100.0, np.float64)
    for bar in range(effort_bar + 1, decision):
        bar_low[bar] = extreme - adverse_ticks * tick_mid2
    flow = {
        "attack_low": attack, "attack_high": np.zeros(bars, np.float64),
        "yield_low": yld, "yield_high": np.zeros(bars, np.float64),
        "delta": delta, "vol": vol,
        "bar_low_mid2": bar_low,
        "bar_high_mid2": np.full(bars, extreme + 500.0, np.float64),
    }
    return Fixture(cell, flow, [_FakeOcc(decision, 1)])


def _measure_fixture(fixture: Fixture, mutant: str | None = None,
                     tick_mid2: float = 10.0) -> dict[str, float]:
    """Measure one fixture.  ``mutant=None`` reads the ambient environment, so
    running the whole selftest under QRE2_MILL_S18_MUTANT turns the planted
    episode's checks red rather than quietly passing."""

    if mutant is None:
        mutant = _mutant()
    bars = fixture.cell.n
    stamps = np.asarray([int(fixture.cell.rec.lat[occ.bar])
                         for occ in fixture.occs], np.int64)
    day_lat = np.asarray(fixture.cell.rec.lat, np.int64)
    day_mid = np.asarray(fixture.cell.rec.mid, np.float64)
    low, high = developing_range(day_lat, np.minimum.accumulate(day_mid),
                                 np.maximum.accumulate(day_mid), stamps)
    del bars
    out = measure_cell(fixture.cell, fixture.flow, low, high, 400.0, tick_mid2,
                       fixture.occs, mutant)
    return out[0][3] if out[0][1] else {}


def _selftest_episode() -> list[tuple[str, bool, str]]:
    """The planted absorption episode: the full ladder must select it."""

    out: list[tuple[str, bool, str]] = []
    absorption = _fixture(60, decision=20, extreme_bar=4, effort_bar=10,
                          effort_size=500.0, beyond_ticks=1.0,
                          stall_vol=400.0, effort_vol=200.0, flip_delta=80.0,
                          adverse_ticks=18.0, post_beyond=60.0)
    values = _measure_fixture(absorption)
    out.append(_check("planted episode is measurable", bool(values),
                      f"keys {len(values)}"))
    if not values:
        return out
    out.append(_check("effort phase ends at the aggression peak",
                      values["effort_bars"] == 7.0,
                      f"effort_bars {values['effort_bars']}"))
    out.append(_check("stall is the window after the peak",
                      values["stall_bars"] == 9.0,
                      f"stall_bars {values['stall_bars']}"))
    out.append(_check("effort in is the summed attack toward the low",
                      values["effort_in"] == 500.0 * 7,
                      f"effort_in {values['effort_in']}"))
    out.append(_check("reward is the effort-phase penetration only",
                      abs(values["extension"] - 1.0) < 1e-9,
                      f"extension {values['extension']}"))
    out.append(_check("G4 sees non-shrinking stall volume",
                      values["vol_ratio"] > 1.0,
                      f"vol_ratio {values['vol_ratio']:.3f}"))
    out.append(_check("G6 sees the aggression flip to the fade side",
                      values["flip"] > 0.0, f"flip {values['flip']}"))
    out.append(_check("the extreme sits in the outer region",
                      values["loc_prev"] > 0.0,
                      f"loc_prev {values['loc_prev']:.4f}"))

    # The planted exhaustion case: same episode, shrinking stall volume.
    exhaustion = _fixture(60, decision=20, extreme_bar=4, effort_bar=10,
                          effort_size=500.0, beyond_ticks=1.0,
                          stall_vol=20.0, effort_vol=400.0, flip_delta=80.0,
                          adverse_ticks=18.0)
    ex_values = _measure_fixture(exhaustion)
    out.append(_check("planted exhaustion case is measurable", bool(ex_values)))
    if ex_values:
        out.append(_check("the absorption branch rejects the exhaustion case",
                          ex_values["vol_ratio"] < values["vol_ratio"],
                          f"exhaustion vol_ratio {ex_values['vol_ratio']:.3f} "
                          f"< absorption {values['vol_ratio']:.3f}"))
        out.append(_check("the fork separates the two branches at the median",
                          ex_values["vol_ratio"] < 1.0 < values["vol_ratio"],
                          f"{ex_values['vol_ratio']:.3f} / "
                          f"{values['vol_ratio']:.3f}"))
    return out


def _selftest_excursion_law() -> list[tuple[str, bool, str]]:
    """THE 18-TICK LAW.  A deep post-effort excursion may not reject anything."""

    out: list[tuple[str, bool, str]] = []
    shallow = _measure_fixture(_fixture(
        60, decision=20, extreme_bar=4, effort_bar=10, effort_size=500.0,
        beyond_ticks=1.0, stall_vol=400.0, effort_vol=200.0, flip_delta=80.0,
        adverse_ticks=1.0, post_beyond=60.0))
    deep = _measure_fixture(_fixture(
        60, decision=20, extreme_bar=4, effort_bar=10, effort_size=500.0,
        beyond_ticks=1.0, stall_vol=400.0, effort_vol=200.0, flip_delta=80.0,
        adverse_ticks=40.0, post_beyond=60.0))
    out.append(_check("both excursion fixtures measure", bool(shallow and deep)))
    if not (shallow and deep):
        return out
    out.append(_check("the deep excursion IS measured",
                      abs(deep["adv_ticks"] - 40.0) < 1e-6,
                      f"adv_ticks {deep['adv_ticks']}"))
    out.append(_check("the shallow excursion IS measured",
                      abs(shallow["adv_ticks"] - 1.0) < 1e-6,
                      f"adv_ticks {shallow['adv_ticks']}"))
    for name in ("loc_prev", "effort_in", "extension", "vol_ratio", "flip"):
        out.append(_check(
            f"excursion depth does not move the {name} gate statistic",
            abs(deep[name] - shallow[name]) < 1e-9,
            f"deep {deep[name]} shallow {shallow[name]}"))
    # The law stated behaviourally: replace the excursion array with garbage and
    # every gate statistic must be bit-identical, while the reported excursion
    # moves.  This is the check that would catch a future gate quietly learning
    # to read the flush.
    poisoned = _fixture(
        60, decision=20, extreme_bar=4, effort_bar=10, effort_size=500.0,
        beyond_ticks=1.0, stall_vol=400.0, effort_vol=200.0, flip_delta=80.0,
        adverse_ticks=40.0, post_beyond=60.0)
    # A deeper flush on every bar: still a live book (positive), so the guard
    # that drops bookless bars cannot mask the change.
    poisoned.flow["bar_low_mid2"] = np.maximum(
        1.0, poisoned.flow["bar_low_mid2"] - 200.0)
    poisoned.flow["bar_high_mid2"] = poisoned.flow["bar_high_mid2"] + 200.0
    wrecked = _measure_fixture(poisoned)
    for name in ("loc_prev", "effort_in", "extension", "vol_ratio", "flip",
                 "effort_u", "extension_u", "vol_ratio_u", "flip_u"):
        out.append(_check(
            f"garbage in the excursion array does not move {name}",
            abs(wrecked[name] - deep[name]) < 1e-9,
            f"clean {deep[name]} wrecked {wrecked[name]}"))
    out.append(_check("garbage in the excursion array DOES move the report",
                      wrecked["adv_ticks"] > deep["adv_ticks"],
                      f"clean {deep['adv_ticks']:.1f} wrecked "
                      f"{wrecked['adv_ticks']:.1f}"))
    # And the law stated as code: the excursion array is read exactly once.
    body = (Path(__file__).read_text().split("def measure_cell", 1)[1]
            .split("\ndef ", 1)[0])
    reads = body.count('arr["bext"]')
    out.append(_check("the excursion array is read exactly once, in the report",
                      reads == 1, f'arr["bext"] read {reads} times'))
    return out


def _selftest_windows() -> list[tuple[str, bool, str]]:
    """The causal law: no gate window may reach the decision bar or past it."""

    out: list[tuple[str, bool, str]] = []
    base = _fixture(60, decision=20, extreme_bar=4, effort_bar=10,
                    effort_size=500.0, beyond_ticks=1.0, stall_vol=400.0,
                    effort_vol=200.0, flip_delta=80.0, adverse_ticks=18.0,
                    post_beyond=60.0)
    values = _measure_fixture(base)
    # Rewriting every bar at or after the decision must not move a statistic.
    poisoned = _fixture(60, decision=20, extreme_bar=4, effort_bar=10,
                        effort_size=500.0, beyond_ticks=1.0, stall_vol=400.0,
                        effort_vol=200.0, flip_delta=80.0, adverse_ticks=18.0,
                        post_beyond=9999.0)
    for name in ("attack_low", "delta", "vol"):
        poisoned.flow[name] = poisoned.flow[name].copy()
        poisoned.flow[name][20:] *= -777.0
    poisoned.flow["yield_low"] = (poisoned.flow["yield_low"].copy())
    poisoned.flow["yield_low"][20:] = 9999.0
    after = _measure_fixture(poisoned)
    out.append(_check("poisoned fixture still measures", bool(after)))
    if after:
        for name in ("loc_prev", "effort_in", "extension", "vol_ratio", "flip",
                     "adv_ticks"):
            out.append(_check(
                f"{name} is blind to bars at or after the stamp",
                abs(after[name] - values[name]) < 1e-9,
                f"honest {values[name]} poisoned {after[name]}"))
    out.append(_check("the ordinal gate is the sweep-13 constant",
                      ORDINAL == 2 and ORDINAL == S13.ORDINAL,
                      f"ordinal {ORDINAL}"))
    bars = [1, 2, 3, 4, 5, 6]
    reference = S14.side_ordinals(bars, [2, 5])
    out.append(_check("the sweep-13 reset law resets on every new extreme",
                      reference == [1, 1, 2, 3, 1, 2], f"{reference}"))
    return out


def _selftest_thresholds() -> list[tuple[str, bool, str]]:
    """The fold law and the quantile marks."""

    out: list[tuple[str, bool, str]] = []
    out.append(_check("min prior days is the sweep-14 fold law",
                      MIN_PRIOR_DAYS == 25 == S14.MIN_PRIOR_DAYS_FIT,
                      f"{MIN_PRIOR_DAYS}"))
    out.append(_check("G2 cut is the top tercile",
                      abs(Q_EFFORT - 200.0 / 3.0) < 1e-9, f"{Q_EFFORT:.4f}"))
    out.append(_check("G3 cut is the bottom tercile",
                      abs(Q_REWARD - 100.0 / 3.0) < 1e-9, f"{Q_REWARD:.4f}"))
    out.append(_check("G1 cut is the upper quartile", Q_LOCATION == 75.0))
    out.append(_check("G4 and G6 cuts are medians",
                      Q_FORK == 50.0 and Q_FLIP == 50.0))
    # The walk-forward slice: a fold may not see its own day.
    rows = []
    for day in (1, 2, 3, 4):
        for k in range(80):
            rows.append(Row(len(rows), "NKD", "1", day, k, 1, 10, 0, 60.0,
                            3600.0, 2, float(k), True, "", {
                                "loc_prev": float(day), "effort_in": float(k),
                                "extension": float(k), "vol_ratio": float(k),
                                "flip": float(k), "effort_u": float(k),
                                "extension_u": float(k), "vol_ratio_u": float(k),
                                "flip_u": float(k), "adv_ticks": 1.0,
                                "outerness": 0.5, "episode_bars": 10.0,
                                "effort_bars": 5.0, "stall_bars": 5.0}))
    saved = globals()["MIN_PRIOR_DAYS"]
    globals()["MIN_PRIOR_DAYS"] = 1
    try:
        folds, scoring = build_folds(rows, {"NKD": [1, 2, 3, 4]})
        fold = folds.get(("NKD", "1", 3))
        out.append(_check("a fold trains only on strictly prior days",
                          fold is not None and fold.train_rows == 160,
                          f"train_rows {fold.train_rows if fold else None}"))
        out.append(_check("the fold's location cut never sees its own day",
                          fold is not None and fold.cuts.get("loc_q", 9.0) < 3.0,
                          f"loc_q {fold.cuts.get('loc_q') if fold else None}"))
        out.append(_check("scoring days honour the minimum prior-day law",
                          scoring["NKD"] == [2, 3, 4], f"{scoring['NKD']}"))
    finally:
        globals()["MIN_PRIOR_DAYS"] = saved
    return out


def _selftest_ladder() -> list[tuple[str, bool, str]]:
    """The ladder is cumulative and the two G4 branches partition R3."""

    out: list[tuple[str, bool, str]] = []
    rng = np.random.default_rng(7)
    n = 400
    gates = {name: rng.random(n) < 0.5 for name in GATE_NAMES}
    gates["G4E"] = ~gates["G4A"]
    for name in ("G2U", "G3U", "G4AU", "G6U"):
        gates[name] = rng.random(n) < 0.5
    masks = ladder_masks(gates)
    for lower, upper in (("R1", "R2"), ("R2", "R3"), ("R3", "R4"),
                         ("R4", "R5"), ("R5", "R6")):
        out.append(_check(f"{upper} is a subset of {lower}",
                          bool(np.all(masks[upper] <= masks[lower])),
                          f"{int(masks[upper].sum())} <= {int(masks[lower].sum())}"))
    out.append(_check("the two G4 branches partition R3",
                      int((masks["R4"] | masks["R4X"]).sum()) == int(masks["R3"].sum())
                      and not bool(np.any(masks["R4"] & masks["R4X"])),
                      f"R3 {int(masks['R3'].sum())} = R4 {int(masks['R4'].sum())}"
                      f" + R4X {int(masks['R4X'].sum())}"))
    out.append(_check("the G1 reject branch is the complement of R1",
                      int((masks["R1"] | masks["G1REJECT"]).sum()) == n
                      and not bool(np.any(masks["R1"] & masks["G1REJECT"])),
                      f"{int(masks['R1'].sum())} + "
                      f"{int(masks['G1REJECT'].sum())} = {n}"))
    out.append(_check("the scrambled selection is not the ordered one",
                      not bool(np.array_equal(masks["SCRAMBLE"], masks["R6"])),
                      f"scramble {int(masks['SCRAMBLE'].sum())} vs R6 "
                      f"{int(masks['R6'].sum())}"))
    return out


def _selftest_stats() -> list[tuple[str, bool, str]]:
    """Wilson, the block null and the lateness donor law on planted data."""

    out: list[tuple[str, bool, str]] = []
    low, high = S1.wilson(55, 100)
    out.append(_check("wilson brackets the point estimate",
                      low < 0.55 < high, f"[{low:.3f}, {high:.3f}]"))
    rng = np.random.default_rng(3)
    rows: list[Row] = []
    for day in range(6):
        for k in range(60):
            # A planted edge: the rows the mask takes are the winners.
            good = k < 12
            rows.append(Row(len(rows), "NKD", "1", 20220100 + day, day * 60 + k,
                            1, 10 + k, int(day * 1e12 + k), float(60 * k),
                            3600.0, 2, 100.0 if good else -20.0, True, "",
                            {"adv_ticks": 5.0}))
    mask = np.asarray([row.y > 0 for row in rows], bool)
    masks = {name: mask for name in BRANCHES}
    masks["R0"] = np.ones(len(rows), bool)
    nulls = block_permutation(rows, masks, draws=200, seed=1)
    line = nulls["by_line"]["NKD/R6"]["mean_y"]
    out.append(_check("the block null rejects a planted edge",
                      line["p_own"] <= 0.01, f"p_own {line['p_own']}"))
    out.append(_check("the block null's family-adjusted p exists",
                      line["p_max_adjusted"] is not None,
                      f"p_adj {line['p_max_adjusted']}"))
    flat = [Row(row.index, row.asset, row.phase, row.d8, row.cell, row.side,
                row.bar, row.stamp_ns, row.elapsed_s, row.remaining_s,
                row.inzone_ordinal, float(rng.normal()), True, "",
                {"adv_ticks": 5.0}) for row in rows]
    flat_null = block_permutation(flat, masks, draws=200, seed=1)
    flat_line = flat_null["by_line"]["NKD/R6"]["mean_y"]
    out.append(_check("the block null does not reject pure noise",
                      flat_line["p_own"] > 0.01,
                      f"p_own {flat_line['p_own']}"))
    late = lateness_control(rows, mask, rows, draws=200, seed=2)
    out.append(_check("the lateness control finds phase-time donors",
                      late["entries_matched"] > 0,
                      f"matched {late['entries_matched']}/{late['entries']}"))
    out.append(_check("the lateness donors come from other days",
                      late["p_mean_y"] is not None
                      and late["observed_mean_y"] > late["mean_y"],
                      f"observed {late['observed_mean_y']:.1f} donor "
                      f"{late['mean_y']:.1f}"))
    return out


def _selftest_mutant() -> list[tuple[str, bool, str]]:
    """The mutant must flip the planted episode red, and only through G3."""

    out: list[tuple[str, bool, str]] = []
    planted = _fixture(60, decision=20, extreme_bar=4, effort_bar=10,
                       effort_size=500.0, beyond_ticks=1.0, stall_vol=400.0,
                       effort_vol=200.0, flip_delta=80.0, adverse_ticks=18.0,
                       post_beyond=60.0)
    honest = _measure_fixture(planted, mutant="")
    red = _measure_fixture(planted, mutant=MUTANT_POST)
    out.append(_check("both readings measure", bool(honest and red)))
    if not (honest and red):
        return out
    out.append(_check("the mutant inflates the reward past the stamp",
                      red["extension"] > honest["extension"] * 10.0,
                      f"honest {honest['extension']:.1f} red "
                      f"{red['extension']:.1f}"))
    # G3 is a residual against a train fit; with the fit held fixed, a reward
    # that large moves the row out of the bottom tercile.  That is the kill.
    a, b = 0.0, 0.0
    cut = 5.0
    honest_pass = (honest["extension"] - (a + b * honest["effort_in"])) <= cut
    red_pass = (red["extension"] - (a + b * red["effort_in"])) <= cut
    out.append(_check("the honest reading passes G3", honest_pass,
                      f"resid {honest['extension']:.1f} <= {cut}"))
    out.append(_check("MUTANT RED: the mutant fails G3 on the planted episode",
                      not red_pass, f"resid {red['extension']:.1f} > {cut}"))
    for name in ("loc_prev", "effort_in", "vol_ratio", "flip", "adv_ticks"):
        out.append(_check(f"the mutant leaves {name} alone",
                          abs(red[name] - honest[name]) < 1e-9,
                          f"{honest[name]} / {red[name]}"))
    out.append(_check("the mutant name is the registered one",
                      MUTANT_POST == "gate_reads_post_stamp", MUTANT_POST))
    return out


def selftest() -> int:
    blocks = (("episode grammar", _selftest_episode()),
              ("18-tick excursion law", _selftest_excursion_law()),
              ("causal windows", _selftest_windows()),
              ("threshold fold law", _selftest_thresholds()),
              ("ladder algebra", _selftest_ladder()),
              ("statistics", _selftest_stats()),
              ("mutant", _selftest_mutant()))
    failures = 0
    total = 0
    for title, checks in blocks:
        print(f"\n-- {title}")
        for name, ok, detail in checks:
            total += 1
            failures += 0 if ok else 1
            mark = "ok  " if ok else "FAIL"
            print(f"  [{mark}] {name}" + (f"   {detail}" if detail else ""))
    print(f"\nselftest {total - failures}/{total} checks pass")
    return 0 if not failures else 1


# --------------------------------------------------------------------------
# The log.
# --------------------------------------------------------------------------

def _show(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def log_rows(report: Mapping[str, object]) -> list[dict[str, object]]:
    table = report["ladder"]
    nulls = report["controls"]["C1_C4"]
    lateness = report["controls"]["C2"]
    ruling = report["decision"]
    days = report["scoring_days"]
    params = json.dumps({
        "q_location": Q_LOCATION, "q_effort": round(Q_EFFORT, 4),
        "q_reward": round(Q_REWARD, 4), "q_fork": Q_FORK, "q_flip": Q_FLIP,
        "ordinal": ORDINAL, "min_prior_days": MIN_PRIOR_DAYS,
        "min_train_rows": MIN_TRAIN_ROWS, "block_draws": BLOCK_DRAWS,
        "lateness_draws": LATENESS_DRAWS, "remain_min_s": REMAIN_MIN_S})
    shared = {
        "registered_utc": report["registered_utc"], "family": FAMILY,
        "params": params, "spec_sha": SPEC_SHA, "code_sha": report["code_sha"],
        "split_sha": report["split_sha"],
        "outcome_law_sha": report["outcome_law_sha"], "null_seed": SEED,
        "parent_trial": PARENT_TRIAL, "selection_rule": SELECTION_RULE,
        "verdict": "",
    }
    rows: list[dict[str, object]] = []
    counter = 0
    for name in BRANCHES:
        counter += 1
        block = table[name]
        pooled_n = sum(block[asset]["n"] for asset in ASSETS)
        pooled_cells = sum(block[asset]["cells"] for asset in ASSETS)
        certifiable = sum(REPRO_CERTIFIABLE[asset] for asset in ASSETS)
        adj = (nulls["by_line"].get(f"NKD/{name}", {}).get("mean_y") or {})
        rows.append({
            **shared, "id": f"sweep18-{counter:03d}",
            "rule": f"LADDER/{name}",
            "days": sum(len(days[asset]) for asset in ASSETS),
            "coverage": float(pooled_cells / certifiable),
            "err_rate_hg": block["HG"]["p_win"],
            "err_rate_nkd": block["NKD"]["p_win"],
            "err_rate_si": block["SI"]["p_win"],
            "hg_usd_day": block["HG"]["usd_per_asset_day"],
            "nkd_usd_day": block["NKD"]["usd_per_asset_day"],
            "si_usd_day": block["SI"]["usd_per_asset_day"],
            "null_margin": adj.get("p_max_adjusted"),
            "note": (f"{block['label']}; n {pooled_n} "
                     f"({block['HG']['n']}/{block['NKD']['n']}/"
                     f"{block['SI']['n']}); meanY "
                     f"{_show(block['HG']['mean_y'])}/"
                     f"{_show(block['NKD']['mean_y'])}/"
                     f"{_show(block['SI']['mean_y'])}; post-effort adverse "
                     f"excursion ticks {_show(block['NKD']['adv_ticks'])} NKD "
                     f"(measured, never a veto)")[:400],
        })
    counter += 1
    order = report["controls"]["C3"]
    rows.append({
        **shared, "id": f"sweep18-{counter:03d}",
        "rule": "CONTROL/C3-SCRAMBLE",
        "days": sum(len(days[asset]) for asset in ASSETS),
        "note": (f"ordered R6 vs unordered AND; delta meanY "
                 f"{_show(order['HG']['delta_mean_y'])}/"
                 f"{_show(order['NKD']['delta_mean_y'])}/"
                 f"{_show(order['SI']['delta_mean_y'])}; n "
                 f"{order['NKD']['ordered_n']} ordered vs "
                 f"{order['NKD']['scrambled_n']} scrambled on NKD")[:400],
    })
    counter += 1
    rows.append({
        **shared, "id": f"sweep18-{counter:03d}",
        "rule": "CONTROL/C2-LATENESS",
        "days": sum(len(days[asset]) for asset in ASSETS),
        "null_margin": lateness.get("p_mean_y"),
        "note": (f"sweep-13 phase-time twin law on R6; matched "
                 f"{lateness.get('entries_matched')}/{lateness.get('entries')}; "
                 f"observed meanY {_show(lateness.get('observed_mean_y'))} vs "
                 f"donor {_show(lateness.get('mean_y'))}; p "
                 f"{_show(lateness.get('p_mean_y'))}")[:400],
    })
    fix = report.get("fixhold") or {}
    counter += 1
    rows.append({
        **shared, "id": f"sweep18-{counter:03d}",
        "rule": "CROSS/FIXHOLD-1800",
        "days": sum(len(days[asset]) for asset in ASSETS),
        "note": ((f"R6 under the 1800 s fixed hold: meanY1800 "
                  f"{_show((fix.get('by_asset') or {}).get('HG', {}).get('mean_y1800'))}/"
                  f"{_show((fix.get('by_asset') or {}).get('NKD', {}).get('mean_y1800'))}/"
                  f"{_show((fix.get('by_asset') or {}).get('SI', {}).get('mean_y1800'))}; "
                  f"priced {fix.get('priced')} of {fix.get('n')}")
                 if fix.get("available")
                 else f"skipped: {fix.get('reason')}")[:400],
    })
    for asset in ASSETS:
        counter += 1
        row = ruling["by_asset"][asset]
        rows.append({
            **shared, "id": f"sweep18-{counter:03d}",
            "rule": f"RULING/{asset}",
            "days": len(days[asset]),
            "coverage": row["coverage"],
            "err_rate_hg": row["p_win"] if asset == "HG" else None,
            "err_rate_nkd": row["p_win"] if asset == "NKD" else None,
            "err_rate_si": row["p_win"] if asset == "SI" else None,
            "hg_usd_day": row["usd_per_asset_day"] if asset == "HG" else None,
            "nkd_usd_day": row["usd_per_asset_day"] if asset == "NKD" else None,
            "si_usd_day": row["usd_per_asset_day"] if asset == "SI" else None,
            "null_margin": row["adjusted_null_p"],
            "note": (f"{ruling['verdict']}; R6 n {row['n']}; failed "
                     + ("; ".join(row["bounds_failed"]) or "none")
                     + f"; subsets {len(ruling['partial_subsets'])}")[:400],
        })
    return rows


def write_report(report: Mapping[str, object]) -> None:
    OUT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True,
                                   default=S8._json_default) + "\n")


# --------------------------------------------------------------------------
# Entry point.
# --------------------------------------------------------------------------

def run() -> dict[str, object]:
    mutant = _mutant()
    started = time.time()
    cells, day_counts, _skipped = S8.build_cells(ASSETS)
    records, _days = S1.load_cache()
    records = [rec for rec in records if rec.asset in ASSETS]
    explore_days = S1._explore_days(ASSETS)
    tape = S9.load_tape(cells)
    forecast = S9.forecast_variance(cells)
    plane = S9.build_plane(cells, forecast, tape)
    states = S12.day_states({asset: explore_days[asset] for asset in ASSETS})
    streams, stream_counters = S14.build_streams(plane, cells, states, "")
    causal = S14.assert_causal(streams, plane)
    if not (causal["no_outcome_in_features"] and causal["remaining_floor_ok"]
            and causal["stream_is_chronological"] and causal["rows_match_plane"]):
        raise SweepRefusal("the sweep-14 occurrence stream failed a causality "
                           "assertion; no measurement is believed past this point")
    scoring_days = {asset: [int(day) for day in days[MIN_PRIOR_DAYS:]]
                    for asset, days in explore_days.items()}
    repro = reproduce(plane, stream_counters, scoring_days)
    if not repro["matches"]:
        raise SweepRefusal("the sweep-14 deduped occurrence stream did not "
                           "reproduce; the gate and stream law refuses the run")

    store = CTX.ContextStore()
    rows, measure_counters = build_rows(streams, cells, store, mutant)
    folds, scoring_days = build_folds(rows, explore_days)
    scored, gates, gate_counters = apply_gates(rows, folds, scoring_days)
    if not scored:
        raise SweepRefusal("no scoring-day row survived the fold law")
    masks = ladder_masks(gates)
    table = ladder_table(scored, masks, scoring_days,
                         {asset: int(plane.certifiable.get(asset, 0))
                          for asset in ASSETS})
    nulls = block_permutation(scored, masks, BLOCK_DRAWS, SEED)
    pool = [row for row in scored]
    lateness_law = lateness_control(scored, masks[FINAL_RUNG], pool,
                                    LATENESS_DRAWS, SEED)
    lateness_wide = lateness_control(scored, masks[FINAL_RUNG], pool,
                                     LATENESS_P_DRAWS, SEED)
    order = order_effect(table)
    ruling = decide(table, nulls, lateness_wide)
    fix = fixhold_price(scored, masks[FINAL_RUNG], records)

    return {
        "schema": "QRE2MILLSWEEP18", "spec_sha": SPEC_SHA,
        "code_sha": code_sha(), "split_sha": S1.split_sha(),
        "outcome_law_sha": S1.outcome_law_sha(), "seed": SEED,
        "mutant": mutant, "family": FAMILY, "parent_trial": PARENT_TRIAL,
        "selection_rule": SELECTION_RULE, "registered_utc": report_stamp(),
        "asset_days": {a: int(day_counts.get(a, 0)) for a in ASSETS},
        "reproduction": repro, "stream_counters": stream_counters,
        "causality": causal, "measurement": measure_counters,
        "gate_counters": {k: int(v) for k, v in gate_counters.items()},
        "gate_fires": {name: int(gates[name].sum()) for name in gates},
        "scoring_days": {a: scoring_days.get(a, []) for a in ASSETS},
        "folds": {"n": len(folds),
                  "fitted": sum(1 for f in folds.values() if f.fitted),
                  "train_rows_median": _q([f.train_rows for f in folds.values()],
                                          50)},
        "window_shape": {
            name: {"median": _q(_column(scored, name), 50),
                   "p90": _q(_column(scored, name), 90)}
            for name in ("episode_bars", "effort_bars", "stall_bars",
                         "adv_ticks")},
        "ladder": table,
        "controls": {"C1_C4": nulls, "C2": lateness_wide,
                     "C2_law_faithful": lateness_law, "C3": order},
        "fixhold": fix,
        "decision": ruling,
        "elapsed_s": round(time.time() - started, 1),
    }


def report_stamp() -> str:
    import datetime as dt
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--log", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    report = run()
    print(f"sweep 18 spec_sha {SPEC_SHA[:16]} code_sha {code_sha()[:16]} "
          f"seed {SEED} mutant {report['mutant'] or 'none'}")
    print_repro(report["reproduction"])
    print_measurement(report["measurement"], report["gate_counters"], [])
    print(f"\nfolds {report['folds']['n']} ({report['folds']['fitted']} fitted), "
          f"median train rows {_n(report['folds']['train_rows_median'], 6, 0)}")
    print("\nWINDOW SHAPE (bars, and the post-effort excursion in ticks)")
    for name, block in report["window_shape"].items():
        print(f"  {name:<16}median {_n(block['median'], 8, 2)}  p90 "
              f"{_n(block['p90'], 8, 2)}")
    print_ladder(report["ladder"])
    print_nulls(report["controls"]["C1_C4"])
    print_lateness(report["controls"]["C2_law_faithful"],
                   report["controls"]["C2"])
    print_order(report["controls"]["C3"])
    print_fixhold(report["fixhold"])
    print_decision(report["decision"])
    write_report(report)
    print(f"\nreport: {OUT_PATH}  ({report['elapsed_s']} s)")
    if args.log:
        if report["mutant"]:
            raise SweepRefusal("a mutant run may never touch the log")
        written = S1.append_log(log_rows(report))
        print(f"log: appended {written} rows to {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
