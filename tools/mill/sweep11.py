#!/usr/bin/env python3
"""Sweep 11 of the side-resolution mill: the grammar automaton.

Exploratory tier.  EXPLORE-day bytes only, can kill, cannot promote.

The charter section this file executes is "The structural diagnosis: score
versus sequence" in ``.audit/briefs/mill-side-resolution.md``.  Its finding: the
sources specify ORDERED EVENT GRAMMARS with hard per-stage vetoes, and every
prior unit collapsed them into a scalar score.  This unit is therefore a
different COMPUTATION CLASS from every unit before it - an automaton with
states, a strict transition order and full resets.  There is no weight, no
average, no composite, and no score anywhere in this file, by construction:
grep it.  A stage either passes or vetoes.

Stage semantics come from ``research/discretionary/DIAGRAM_NOTES_FLOW_2026-08-27.md``
(the consolidated section: two-lane confirmation - a fast lane reading the
transfer of control off delta without waiting for price, and a slow lane
requiring pull-away then a retest that holds) and
``research/discretionary/NEW_DELTA_2026-08-27.md`` (the playbook: the
finished-auction one-sided print at the extreme, and absorption as effort
without result - top-percentile attack against bottom-percentile yield).

Machinery is imported, never re-implemented: sweep 1's ``CellRec`` cache,
``Entry``/``make_entry`` entry law, ``cash_line``, ``asset_mdd_day``/
``asset_mdd_trade``, ``replay_line``, ``block_null``, ``wilson`` and
``append_log``; sweep 2's ``star_cell`` (Delta*) and ``extremes``; sweep 3's
adversarial ``stress_line``; sweep 4's terminal law; sweep 7a's zone geometry
and candidate plane; the mill context store for ATR14_prev; ``mill_flow`` for
the per-minute delta/vol/attack/yield arrays and ``mill_flow_zones`` for the
zone/episode/touch series.

Data: mill caches + mill_context + mill_flow + mill_flow_zones only.  No packs,
no HOLD day, no teacher or late label, no 2021 byte, no 2025 byte.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import datetime as dt
import json
import os
from pathlib import Path
import sys
from typing import Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine.entry_v2.confirmation_types import NANOS_PER_SECOND

import mill as M
import context as CTX
import flow as FLOW
import flow_zones as ZONES
import sweep1 as S1
import sweep2 as S2
import sweep3 as S3
import sweep4 as S4
import sweep7a as S7A

# --------------------------------------------------------------------------
# The law, registered before anything is read.
# --------------------------------------------------------------------------

SPEC = """QRE2MILLSWEEP11
tier=exploratory; explore-only; can kill, cannot promote.  parent trial
  sweep8b-004.  Charter: mill-side-resolution.md "The structural diagnosis:
  score versus sequence".  Computation class: ORDERED AUTOMATON.  No weight,
  no average, no composite score, no swept knob.  Every percentile cutoff
  below is fixed by the charter text, not selected.
AUTOMATON, per (cell, side), advancing on completed 60 s bars, FULL RESET of
  that side on any veto.  Both sides run independent automata.
  S1 ARRIVAL: the bar is in the side's zone (bar mid within 0.15*ATR14_prev of
    the running extreme read strictly before the bar) and its attack volume is
    at or above the (asset, phase) stratum p60, calibrated on strictly-prior
    EXPLORE days (>= 20 of them).  Opens the setup and RECORDS THE ARRIVAL
    EXTREME - every later stage measures against that stamped level, not a
    level that moves under it.
  S2 ABSORPTION, in bars [arrival, arrival+3]: price yield per unit attack at
    or below stratum p40, OR a one-sided print at the extreme (|delta|/vol at
    the touch bar at or above stratum p60).  VETO if a new same-side extreme
    prints more than 0.075*ATR beyond the arrival extreme (the run is still
    going).  VETO when the window closes unsatisfied.
  S3 CONTROL TRANSFER, two lanes, either satisfies.
    FAST: signed per-minute delta flips TOWARD the fade side within 3 bars of
      S2 - a sign change whose flipped bar carries |delta| at or above its
      stratum p40.
    SLOW: price pulls away from the zone (a bar closing more than 0.075*ATR
      toward the interior) and then retests the zone WITHOUT setting a new
      extreme and holds (the retest bar's close back toward the interior).
    VETO on a new same-side extreme.
  S4 HOLD: k = 3 completed bars with no new same-side extreme and price not
    re-entering the zone's outer half (within 0.075*ATR of the arrival
    extreme).  Any breach VETOES and resets.
  S5 ENTRY: the first fade-side CLEAR candidate at or after S4 completion
    whose decision quote sits within 0.15*ATR of the extreme; 15-minute wait
    limit; at least 1800 s remaining at entry; ONE entry per cell (the first
    side to complete wins); an opposite-side new extreme cancels a pending
    entry and RESETS BOTH SIDES.
  No other parameter exists.  p60/p40 are the charter's, never swept.
S3-ENTRY VARIANT (priced beside the base, coordinator addition): identical
  through S3, then entry at the first fade-side CLEAR candidate at or after S3
  completion under the same depth and time laws.  Trades hold-safety for entry
  depth inside the same grammar.  Shares stages 1-3 of the attrition table.
CONTROLS on identical cells: the sweep-8 CONTROL line (receipt numbers imported
  from .audit/mill-sweep8.json, never retyped), and a STAGE-SHUFFLED control -
  the same S1 arrivals with S2-S4 waived, entering at the first candidate after
  arrival + 6 bars.  The shuffle prices exactly what the grammar's ORDERING
  adds beyond arrival detection.
METRICS: the STAGE ATTRITION TABLE is the diagnostic heart - a failure must
  name its stage.  Plus coverage, lane split, wall rate with Wilson CI,
  postX_1800 at entry, soft-hit, side agreement vs sign(Delta*) (diagnostic
  only), delay from the side's true terminal, per-trade cash, cash/day vs
  rungs, win, MDD both orderings.  Every stage-A and priced table is also cut
  by calendar year (2022/2023/2024) per asset - diagnostic columns only, no
  selection on year.
PRICED BATTERY per deciding asset: engine replay (partial-day label), 2%
  adversarial stress, block-permutation null (200 draws, seed 20260827,
  max-stat across all priced lines).
VARIANT priced only if the base line's MDD is its binding miss: the stand-down
  cadence overlay - after any wall, no new entries for the remainder of that
  asset-day plus the next EXPLORE asset-day.
MUTANT QRE2_MILL_S11_MUTANT=stage_order_ignored checks S2/S3/S4 as unordered
  conditions over the same window instead of the strict sequence.  It MUST
  flip a selftest case red: that is the proof the ORDERING, not the stage
  menu, is what this unit implements.
"""

SCHEMA = "QRE2MILLSWEEP11"
SEED = S1.SEED                       # 20260827
BAR_SECONDS = S1.BAR_SECONDS         # 60
ASSETS = S1.ASSETS
DAY_RUNG_USD = S1.DAY_RUNG_USD       # HG 2000 (report-only), NKD 1500, SI 1500
DECIDING = ("NKD", "SI")
MDD_CAP_USD = S1.MDD_CAP_USD         # 1000

# --- the frozen grammar constants.  Every one is charter text. -------------
ZONE_ATR = 0.15                 # S1 zone half-width and the S5 depth band
HALF_ZONE_ATR = 0.075           # S2's run-continues veto and S4's outer half
S2_WINDOW_BARS = 3              # "during or within 3 bars of the arrival"
S3_FAST_BARS = 3                # "within 3 bars of S2"
S4_HOLD_BARS = 3                # k = 3
WAIT_LIMIT_BARS = 15            # "15-minute wait limit"
REMAIN_MIN_S = 1800             # "minimum 1800 s remaining at entry"
SHUFFLE_LAG_BARS = 6            # the stage-shuffled control's S1 + 6 bars

P_ARRIVAL = 60.0                # S1 attack cutoff
P_YIELD = 40.0                  # S2 absorption yield cutoff
P_ONESIDED = 60.0               # S2 one-sided print cutoff
P_FLIP = 40.0                   # S3 fast-lane |delta| cutoff

MIN_PRIOR_DAYS = 20             # the calibration floor, inherited from sweep 8
HORIZON_BARS = REMAIN_MIN_S // BAR_SECONDS      # postX_1800 = 30 bars
NULL_DRAWS = S1.NULL_DRAWS      # 200
STRESS_RATE = S3.STRESS_RATE    # 0.02

# Pre-registered decision-table bounds, printed before stage B runs.
INTERESTING_WALL_CEILING = 0.08
INTERESTING_COVERAGE_FLOOR = 0.30
INTERESTING_USD_DAY = 400.0
INTERESTING_MDD_DAY = 3000.0
NULL_CEILING = 0.05

STRATA_NAMES = ("attack", "yield", "onesided", "absdelta")

# Stage identities and the veto vocabulary.  A failure NAMES one of these.
STAGES = ("S1_ARRIVAL", "S2_ABSORPTION", "S3_TRANSFER", "S4_HOLD", "S5_ENTRY")
VETO_S2_RUN = "S2_run_continues"
VETO_S2_WINDOW = "S2_no_absorption"
VETO_S3_EXTREME = "S3_new_extreme"
VETO_S3_WINDOW = "S3_no_transfer"
VETO_S4_EXTREME = "S4_new_extreme"
VETO_S4_ZONE = "S4_zone_reentry"
VETOES = (VETO_S2_RUN, VETO_S2_WINDOW, VETO_S3_EXTREME, VETO_S3_WINDOW,
          VETO_S4_EXTREME, VETO_S4_ZONE)

MISS_NO_CANDIDATE = "no_candidate"
MISS_NO_DEPTH = "no_candidate_in_depth"
MISS_WAIT = "wait_limit"
MISS_NO_TIME = "under_1800s_remaining"
MISS_CANCELLED = "opposite_extreme_cancelled"
MISS_CELL_TAKEN = "cell_already_entered"
MISS_UNSCORED = "stratum_unscored"
MISSES = (MISS_NO_CANDIDATE, MISS_NO_DEPTH, MISS_WAIT, MISS_NO_TIME,
          MISS_CANCELLED, MISS_CELL_TAKEN, MISS_UNSCORED)

LANE_FAST = "fast"
LANE_SLOW = "slow"

BASE_LINE = "GRAMMAR"
S3_LINE = "GRAMMAR-S3"
SHUFFLE_LINE = "STAGESHUFFLE"
STANDDOWN_LINE = "GRAMMAR-STANDDOWN"
PRICED_LINES = (BASE_LINE, S3_LINE, SHUFFLE_LINE)

FAMILY = "F8-GRAMMAR"
PARENT_TRIAL = "sweep8b-004"
SELECTION_RULE = "none: frozen automaton, pre-registered decision table"

OUT_PATH = ROOT / ".audit/mill-sweep11.json"
LOG_PATH = S1.LOG_PATH
SPLIT_PATH = S1.SPLIT_PATH
SWEEP8_PATH = ROOT / ".audit/mill-sweep8.json"

MUTANT_ENV = "QRE2_MILL_S11_MUTANT"
MUTANT_UNORDERED = "stage_order_ignored"
MUTANTS = (MUTANT_UNORDERED,)


class SweepRefusal(RuntimeError):
    pass


SPEC_SHA = S1._sha_text(SPEC)


def code_sha() -> str:
    return S1._sha_file(Path(__file__).resolve())


def split_sha() -> str:
    return S1.split_sha()


def outcome_law_sha() -> str:
    return S1.outcome_law_sha()


def _mutant() -> str:
    name = os.environ.get(MUTANT_ENV, "")
    if name and name not in MUTANTS:
        raise SweepRefusal(f"unknown sweep-11 mutant: {name}")
    return name


# --------------------------------------------------------------------------
# The automaton.  Pure arrays in, transitions out - so the selftest can drive
# it on a hand-built fixture with no cache, no bytes and no era data.
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Cuts:
    """The four walk-forward cutoffs one bar is tested against.

    ``None`` anywhere means the stratum has not accumulated enough prior days,
    which makes the whole side UNSCORED - an abstain, never a pass.
    """

    attack_p60: float | None
    yield_p40: float | None
    onesided_p60: float | None
    absdelta_p40: float | None

    @property
    def scored(self) -> bool:
        return all(value is not None for value in
                   (self.attack_p60, self.yield_p40, self.onesided_p60,
                    self.absdelta_p40))


@dataclass(frozen=True, slots=True)
class SideInput:
    """One (cell, side): everything the automaton is allowed to read."""

    side: int
    atr: float
    mid: np.ndarray             # bar mid, mid2 units
    prior_ext: np.ndarray       # running extreme over bars strictly before k
    new_ext: np.ndarray         # a new same-side extreme printed at k
    opp_new_ext: np.ndarray     # a new OPPOSITE-side extreme printed at k
    in_zone: np.ndarray         # |mid - prior_ext| <= ZONE_ATR * atr
    attack: np.ndarray          # attack volume into this side's zone
    yield_pa: np.ndarray        # adverse ticks per unit attack volume
    onesided: np.ndarray        # |delta| / vol at the bar (nan where vol == 0)
    delta: np.ndarray           # signed per-minute delta
    absdelta: np.ndarray
    touch: np.ndarray           # the bar sits in the extreme's core band
    cand: np.ndarray            # a legal fade-side CLEAR candidate at k
    remaining_s: np.ndarray     # seconds from bar close to phase close
    tradeable: np.ndarray       # rec.bar_ok

    @property
    def n(self) -> int:
        return int(len(self.mid))


@dataclass(slots=True)
class Attempt:
    """One pass of the automaton for one side: how far it got, and why it died."""

    side: int
    arrival_bar: int
    arrival_ext: float
    reached: str                # the furthest stage entered
    veto: str                   # "" when the attempt completed S4
    s2_bar: int = -1
    s3_bar: int = -1
    s4_bar: int = -1
    lane: str = ""


def _toward_interior(side: int, mid: float, extreme: float) -> float:
    """Signed distance from the faded extreme, positive toward the interior.

    Fading a low (``side > 0``) means the interior is UP, so interior distance
    is ``mid - extreme``; fading a high mirrors it.  Every stage measures
    against the ARRIVAL extreme, stamped at S1 and never refreshed, because a
    level that moves under the automaton would let a still-running move satisfy
    a stage it should have vetoed.
    """

    return float(side) * (float(mid) - float(extreme))


def _s2_ok(inp: SideInput, bar: int, cuts: Cuts) -> bool:
    """Absorption at one bar: effort without result, OR a one-sided print."""

    yield_ok = (np.isfinite(inp.yield_pa[bar])
                and float(inp.yield_pa[bar]) <= float(cuts.yield_p40))
    # The finished-auction read: the one-sided print only counts AT the
    # extreme, which is what the touch flag marks.
    print_ok = (bool(inp.touch[bar]) and np.isfinite(inp.onesided[bar])
                and float(inp.onesided[bar]) >= float(cuts.onesided_p60))
    return bool(yield_ok or print_ok)


def _fast_ok(inp: SideInput, bar: int, cuts: Cuts) -> bool:
    """The fast lane: delta flips TOWARD the fade with size behind the flip."""

    if bar < 1:
        return False
    now = float(inp.delta[bar]) * float(inp.side)
    before = float(inp.delta[bar - 1]) * float(inp.side)
    flipped = now > 0.0 and before <= 0.0
    return bool(flipped
                and float(inp.absdelta[bar]) >= float(cuts.absdelta_p40))


def _s4_hold_ok(inp: SideInput, bar: int, extreme: float) -> bool:
    """One hold bar: no new same-side extreme, and out of the zone's outer half."""

    if bool(inp.new_ext[bar]):
        return False
    return abs(float(inp.mid[bar]) - float(extreme)) > HALF_ZONE_ATR * inp.atr


def run_side(inp: SideInput, cuts: Cuts) -> list[Attempt]:
    """Every pass the automaton makes over one side, in bar order.

    A veto is a FULL RESET: the side returns to idle and may arrive again on a
    later bar.  Attempts accumulate so the attrition table can count
    opportunities entering each stage, not just the one that survived.
    """

    if not cuts.scored:
        return []
    if _mutant() == MUTANT_UNORDERED:
        return _run_side_unordered(inp, cuts)

    attempts: list[Attempt] = []
    bar = 1
    while bar < inp.n:
        if not (bool(inp.in_zone[bar]) and bool(inp.tradeable[bar])
                and np.isfinite(inp.attack[bar])
                and float(inp.attack[bar]) >= float(cuts.attack_p60)):
            bar += 1
            continue
        attempt = _one_attempt(inp, cuts, bar)
        attempts.append(attempt)
        # Restart the scan after whatever bar killed (or completed) the pass,
        # so one arrival cannot be double-counted by the next.
        last = max(attempt.arrival_bar, attempt.s2_bar, attempt.s3_bar,
                   attempt.s4_bar)
        bar = last + 1
    return attempts


def _one_attempt(inp: SideInput, cuts: Cuts, arrival: int) -> Attempt:
    """S2 -> S3 -> S4 from one arrival, in that order, vetoing on the way."""

    extreme = float(inp.prior_ext[arrival])
    out = Attempt(int(inp.side), int(arrival), extreme, "S2_ABSORPTION", "")

    # --- S2 ABSORPTION -----------------------------------------------------
    s2_bar = -1
    stop = min(inp.n, arrival + S2_WINDOW_BARS + 1)
    for bar in range(arrival, stop):
        beyond = -_toward_interior(inp.side, inp.mid[bar], extreme)
        if bool(inp.new_ext[bar]) and beyond > HALF_ZONE_ATR * inp.atr:
            out.veto = VETO_S2_RUN
            out.s2_bar = bar
            return out
        if _s2_ok(inp, bar, cuts):
            s2_bar = bar
            break
    if s2_bar < 0:
        out.veto = VETO_S2_WINDOW
        out.s2_bar = stop - 1
        return out
    out.s2_bar = s2_bar
    out.reached = "S3_TRANSFER"

    # --- S3 CONTROL TRANSFER, two lanes ------------------------------------
    s3_bar, lane = -1, ""
    away = float("nan")
    for bar in range(s2_bar + 1, inp.n):
        if bool(inp.new_ext[bar]):
            out.veto = VETO_S3_EXTREME
            out.s3_bar = bar
            return out
        if bar <= s2_bar + S3_FAST_BARS and _fast_ok(inp, bar, cuts):
            s3_bar, lane = bar, LANE_FAST
            break
        interior = _toward_interior(inp.side, inp.mid[bar], extreme)
        if not np.isfinite(away):
            # Gate one: the displacement away from the level.
            if interior > HALF_ZONE_ATR * inp.atr:
                away = interior
            continue
        # Gate two: a RETURN to the zone that sets no new extreme and still
        # closes toward the interior.  The return must be strictly nearer the
        # level than the pull-away was, or "pull away then come back" collapses
        # into one bar - the 0.075 ATR displacement band and the 0.15 ATR zone
        # overlap, so a bar can satisfy both readings at once and the source's
        # "two waits, not one" would be silently reduced to one.
        if bool(inp.in_zone[bar]) and 0.0 < interior < away:
            s3_bar, lane = bar, LANE_SLOW
            break
    if s3_bar < 0:
        out.veto = VETO_S3_WINDOW
        out.s3_bar = inp.n - 1
        return out
    out.s3_bar, out.lane = s3_bar, lane
    out.reached = "S4_HOLD"

    # --- S4 HOLD -----------------------------------------------------------
    end = s3_bar + S4_HOLD_BARS
    if end >= inp.n:
        out.veto = VETO_S4_EXTREME if bool(
            np.any(inp.new_ext[s3_bar + 1:])) else VETO_S4_ZONE
        out.s4_bar = inp.n - 1
        return out
    for bar in range(s3_bar + 1, end + 1):
        if bool(inp.new_ext[bar]):
            out.veto = VETO_S4_EXTREME
            out.s4_bar = bar
            return out
        if not _s4_hold_ok(inp, bar, extreme):
            out.veto = VETO_S4_ZONE
            out.s4_bar = bar
            return out
    out.s4_bar = end
    out.reached = "S5_ENTRY"
    return out


def _run_side_unordered(inp: SideInput, cuts: Cuts) -> list[Attempt]:
    """THE MUTANT.  Same stage menu, same window, no ordering.

    Stages S2/S3/S4 are checked as unordered CONDITIONS anywhere in the window
    that starts at the arrival, instead of as a strict sequence.  If the
    ordering is not load bearing this changes nothing; the selftest proves it
    changes verdicts, which is the whole point of the unit.
    """

    attempts: list[Attempt] = []
    window = S2_WINDOW_BARS + S3_FAST_BARS + S4_HOLD_BARS + 1
    bar = 1
    while bar < inp.n:
        if not (bool(inp.in_zone[bar]) and bool(inp.tradeable[bar])
                and np.isfinite(inp.attack[bar])
                and float(inp.attack[bar]) >= float(cuts.attack_p60)):
            bar += 1
            continue
        extreme = float(inp.prior_ext[bar])
        stop = min(inp.n, bar + window)
        span = range(bar, stop)
        s2 = [k for k in span if _s2_ok(inp, k, cuts)]
        fast = [k for k in span if _fast_ok(inp, k, cuts)]
        slow = [k for k in span if bool(inp.in_zone[k])
                and _toward_interior(inp.side, inp.mid[k], extreme) > 0.0]
        hold = [k for k in span if _s4_hold_ok(inp, k, extreme)]
        out = Attempt(int(inp.side), int(bar), extreme, "S2_ABSORPTION", "")
        if not s2:
            out.veto = VETO_S2_WINDOW
        elif not (fast or slow):
            out.reached, out.veto = "S3_TRANSFER", VETO_S3_WINDOW
        elif len(hold) < S4_HOLD_BARS:
            out.reached, out.veto = "S4_HOLD", VETO_S4_ZONE
        else:
            out.s2_bar = s2[0]
            out.s3_bar = (fast or slow)[0]
            out.lane = LANE_FAST if fast else LANE_SLOW
            out.s4_bar = hold[S4_HOLD_BARS - 1]
            out.reached = "S5_ENTRY"
        attempts.append(out)
        bar = stop
    return attempts


# --------------------------------------------------------------------------
# S5: entry resolution across both sides of one cell.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Fire:
    """One completed grammar pass resolved into an entry attempt."""

    side: int
    ready_bar: int              # S4 completion (base) or S3 completion (variant)
    lane: str
    entry_bar: int
    depth_atr: float
    miss: str


def _resolve(inputs: Mapping[int, SideInput], ready: Sequence[tuple[int, int, str]]
             ) -> list[Fire]:
    """First side to complete wins; an opposite-side extreme cancels and resets.

    ``ready`` is ``(bar, side, lane)`` for every completed pass on both sides.
    The scan walks them in bar order because "the first side to complete wins"
    is a statement about the joint timeline, not about either side alone.
    """

    fires: list[Fire] = []
    floor = 0
    for ready_bar, side, lane in sorted(ready):
        if ready_bar < floor:
            fires.append(Fire(side, ready_bar, lane, -1, float("nan"),
                              MISS_CANCELLED))
            continue
        inp = inputs[side]
        extreme = float(inp.prior_ext[ready_bar])
        limit = ready_bar + WAIT_LIMIT_BARS
        chosen, depth, miss = -1, float("nan"), MISS_NO_CANDIDATE
        cancel_bar = -1
        for bar in range(ready_bar, min(inp.n, limit + 1)):
            if bool(inp.opp_new_ext[bar]) and bar > ready_bar:
                cancel_bar = bar
                miss = MISS_CANCELLED
                break
            if not bool(inp.cand[bar]):
                continue
            reach = abs(float(inp.mid[bar]) - extreme) / inp.atr
            if reach > ZONE_ATR:
                miss = MISS_NO_DEPTH
                continue
            if float(inp.remaining_s[bar]) < REMAIN_MIN_S:
                miss = MISS_NO_TIME
                continue
            chosen, depth, miss = bar, reach, ""
            break
        if chosen < 0 and miss == MISS_NO_CANDIDATE and limit < inp.n:
            miss = MISS_WAIT
        fires.append(Fire(side, ready_bar, lane, chosen, depth, miss))
        if cancel_bar >= 0:
            # The cancellation resets BOTH sides: nothing that completed at or
            # before the opposite extreme may still enter.
            floor = cancel_bar + 1
            continue
        if chosen >= 0:
            break                       # one entry per cell
    # Everything after the taken entry is a miss for the record, not a trade.
    taken = next((i for i, row in enumerate(fires) if row.entry_bar >= 0), None)
    if taken is not None:
        for row in fires[taken + 1:]:
            row.entry_bar, row.miss = -1, MISS_CELL_TAKEN
    return fires


# --------------------------------------------------------------------------
# Cell assembly: mill cache + context + flow + flow_zones, nothing else.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Cell11:
    position: int
    asset: str
    d8: int
    year: int
    phase: str
    n: int
    rec: S1.CellRec
    geo: S7A.Geo
    star: S2.Star
    atr_mid2: float
    sides: dict[int, SideInput]


def _side_input(rec: S1.CellRec, geo: S7A.Geo, side: int, atr_mid2: float,
                flow_cell: Mapping[str, np.ndarray],
                zside: ZONES.ZoneSide) -> SideInput:
    bars = rec.n
    tag = "low" if int(side) > 0 else "high"
    prior, new_ext, _armed = S7A.side_arrays(geo, side)
    _oprior, opp_new, _oarmed = S7A.side_arrays(geo, -side)
    mid = np.asarray(rec.mid, np.float64)[:bars]
    prior = np.asarray(prior, np.float64)[:bars]
    delta = np.asarray(flow_cell["delta"], np.float64)[:bars]
    vol = np.asarray(flow_cell["vol"], np.float64)[:bars]
    onesided = np.where(vol > 0.0, np.abs(delta) / np.maximum(vol, 1e-12), np.nan)
    stamps = np.asarray(rec.lat, np.int64)[:bars]
    remaining = ((int(rec.phase_close_ts_ns) - stamps)
                 / float(NANOS_PER_SECOND)).astype(np.float64)
    cand = np.zeros(bars, bool)
    cand[S7A.candidate_bars(rec, side)] = True
    return SideInput(
        side=int(side), atr=float(atr_mid2), mid=mid, prior_ext=prior,
        new_ext=np.asarray(new_ext, bool)[:bars],
        opp_new_ext=np.asarray(opp_new, bool)[:bars],
        in_zone=np.abs(mid - prior) <= ZONE_ATR * float(atr_mid2),
        attack=np.asarray(flow_cell[f"attack_{tag}"], np.float64)[:bars],
        yield_pa=np.asarray(flow_cell[f"yield_{tag}"], np.float64)[:bars],
        onesided=onesided, delta=delta, absdelta=np.abs(delta),
        touch=np.asarray(zside.series["touch"], bool)[:bars],
        cand=cand, remaining_s=remaining,
        tradeable=np.asarray(rec.bar_ok, bool)[:bars])


def build_cells(assets: Sequence[str]) -> tuple[list[Cell11], dict[str, int],
                                                dict[str, int],
                                                list[S1.CellRec]]:
    """Every EXPLORE cell carrying an ATR prior plus a flow and a zones shard.

    The FILTERED record list travels out with the cells because ``Entry.cell``
    indexes into it: reloading an unfiltered list downstream would silently
    misalign every entry as soon as ``--assets`` names fewer than three.
    """

    records, days = S1.load_cache()
    records = [rec for rec in records if rec.asset in assets]
    store = CTX.ContextStore()
    cells: list[Cell11] = []
    skipped = {asset: 0 for asset in assets}
    cache: dict[tuple[str, int], tuple[dict, dict]] = {}
    for position, rec in enumerate(records):
        payload = store.context_for(rec.asset, rec.d8)
        priors = payload.get("priors")
        if priors is None or str(priors.get("atr14_present", "0")) != "1":
            skipped[rec.asset] += 1
            continue
        atr_usd = float(priors["atr14_prev_usd"])
        if not atr_usd > 0.0:
            skipped[rec.asset] += 1
            continue
        atr_mid2 = atr_usd * S7A.usd_to_mid2(rec.asset)
        key = (rec.asset, rec.d8)
        if key not in cache:
            cache[key] = (FLOW.load_flow(rec.asset, rec.d8),
                          ZONES.load_zones(rec.asset, rec.d8))
        flow_day, zones_day = cache[key]
        cell_key = (rec.phase, int(rec.phase_open_ts_ns))
        if cell_key not in flow_day or cell_key not in zones_day:
            skipped[rec.asset] += 1
            continue
        flow_cell = flow_day[cell_key]
        if len(flow_cell["vol"]) < rec.n:
            skipped[rec.asset] += 1
            continue
        zcell = zones_day[cell_key]
        if zcell.bars < rec.n:
            skipped[rec.asset] += 1
            continue
        geo = S7A.geometry(rec, atr_mid2)
        star = S2.star_cell(rec, S7A.W_VARIANT, S7A.W_BAND)
        sides = {side: _side_input(rec, geo, side, atr_mid2, flow_cell,
                                   zcell.sides[side]) for side in (1, -1)}
        cells.append(Cell11(position, rec.asset, int(rec.d8),
                            int(rec.d8) // 10000, rec.phase, rec.n, rec, geo,
                            star, float(atr_mid2), sides))
    return (cells, {k: int(v) for k, v in days.items() if k in assets},
            skipped, records)


# --------------------------------------------------------------------------
# The walk-forward stratum store.  Percentiles only; never a fitted number.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Stratum:
    prior: dict[str, list[float]] = field(
        default_factory=lambda: {name: [] for name in STRATA_NAMES})
    pending: dict[str, list[float]] = field(
        default_factory=lambda: {name: [] for name in STRATA_NAMES})
    prior_days: int = 0
    cache: dict[str, np.ndarray] = field(default_factory=dict)

    def flush(self) -> None:
        for name, values in self.pending.items():
            self.prior[name].extend(values)
            values.clear()
        self.prior_days += 1
        self.cache.clear()

    def sample(self, name: str) -> np.ndarray:
        held = self.cache.get(name)
        if held is None:
            array = np.asarray(self.prior[name], np.float64)
            held = np.sort(array[np.isfinite(array)])
            self.cache[name] = held
        return held

    def cuts(self) -> Cuts:
        if self.prior_days < MIN_PRIOR_DAYS:
            return Cuts(None, None, None, None)

        def mark(name: str, point: float) -> float | None:
            sample = self.sample(name)
            return float(np.percentile(sample, point)) if len(sample) else None

        return Cuts(mark("attack", P_ARRIVAL), mark("yield", P_YIELD),
                    mark("onesided", P_ONESIDED), mark("absdelta", P_FLIP))


def contributions(cell: Cell11) -> dict[str, list[float]]:
    """What one cell banks into its stratum once its day is finished with.

    Banking is unconditional on where the automaton fired: a percentile of the
    tape must be a property of the tape, not of the policy's own history.
    """

    out: dict[str, list[float]] = {name: [] for name in STRATA_NAMES}
    for side in (1, -1):
        inp = cell.sides[side]
        zone = inp.in_zone & inp.tradeable
        out["attack"].extend(
            float(v) for v in inp.attack[zone] if np.isfinite(v))
        out["yield"].extend(
            float(v) for v in inp.yield_pa[zone] if np.isfinite(v))
        out["onesided"].extend(
            float(v) for v in inp.onesided[inp.touch[:inp.n]] if np.isfinite(v))
        out["absdelta"].extend(
            float(v) for v in inp.absdelta[inp.tradeable] if np.isfinite(v))
    return out


# --------------------------------------------------------------------------
# The run: one walk-forward pass over the EXPLORE days.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Shot:
    """One counted entry or miss, with everything the tables reduce."""

    cell: int
    asset: str
    d8: int
    year: int
    phase: str
    side: int
    lane: str
    ready_bar: int
    entry_bar: int
    depth_atr: float
    miss: str
    post_extreme: bool = False
    postx1800: bool = False
    postx_full: bool = False
    soft_hit: bool = False
    side_ok: bool | None = None
    delay_s: float = float("nan")
    before_terminal: bool = False
    wait_s: int = -1


def _finish(cell: Cell11, fire: Fire) -> Shot:
    inp = cell.sides[fire.side]
    new_ext = inp.new_ext
    terminal = S7A.terminal_bar(cell.geo, fire.side)
    shot = Shot(cell.position, cell.asset, cell.d8, cell.year, cell.phase,
                fire.side, fire.lane, fire.ready_bar, fire.entry_bar,
                fire.depth_atr, fire.miss)
    if fire.entry_bar < 0:
        return shot
    bar = fire.entry_bar
    stop = bar + 1 + HORIZON_BARS
    rem = cell.star.rem(fire.side)
    sign = int(cell.star.sign[bar])
    shot.post_extreme = bool(np.any(new_ext[bar + 1:]))
    shot.postx1800 = bool(np.any(new_ext[bar + 1:stop]))
    shot.postx_full = bool(stop <= cell.n)
    shot.soft_hit = bool(float(rem[bar]) > 0.0)
    shot.side_ok = None if sign == 0 else bool(int(fire.side) == sign)
    shot.delay_s = (float("nan") if terminal < 0
                    else float((bar - terminal) * BAR_SECONDS))
    shot.before_terminal = bool(terminal >= 0 and bar < terminal)
    shot.wait_s = int((bar - fire.ready_bar) * BAR_SECONDS)
    return shot


@dataclass(slots=True)
class RunOut:
    shots: dict[str, list[Shot]]
    entries: dict[str, list[S1.Entry]]
    attrition: dict[str, dict[str, int]]
    unscored_cells: int
    scored_cells: int


def _blank_attrition() -> dict[str, dict[str, int]]:
    return {"entered": {stage: 0 for stage in STAGES},
            "veto": {name: 0 for name in VETOES},
            "survivors": {stage: 0 for stage in STAGES},
            "lane": {LANE_FAST: 0, LANE_SLOW: 0},
            "miss": {name: 0 for name in MISSES}}


def _count(table: dict[str, dict[str, int]], attempt: Attempt) -> None:
    """One attempt's contribution to the attrition table.

    A stage is ENTERED when the automaton reached it; it SURVIVES when the
    attempt went on to enter the next one, so survivors[k] == entered[k+1] by
    construction and the table reads straight down as a funnel.
    """

    order = list(STAGES)
    reached = order.index(attempt.reached)
    for stage in order[:reached + 1]:
        table["entered"][stage] += 1
    for stage in order[:reached]:
        table["survivors"][stage] += 1
    if attempt.veto:
        table["veto"][attempt.veto] += 1
    elif attempt.lane:
        table["lane"][attempt.lane] += 1


def run(cells: Sequence[Cell11]) -> RunOut:
    """The walk-forward pass: strata calibrate on strictly-prior days only."""

    shots: dict[str, list[Shot]] = {name: [] for name in PRICED_LINES}
    entries: dict[str, list[S1.Entry]] = {name: [] for name in PRICED_LINES}
    attrition = {asset: _blank_attrition() for asset in ASSETS}
    attrition["POOLED"] = _blank_attrition()
    strata: dict[tuple[str, str], Stratum] = {}
    pending: dict[tuple[str, str], list[dict[str, list[float]]]] = {}
    unscored = scored = 0

    by_day: dict[tuple[str, int], list[Cell11]] = {}
    for cell in cells:
        by_day.setdefault((cell.asset, cell.d8), []).append(cell)

    for asset, d8 in sorted(by_day):
        for key, banked in list(pending.items()):
            if key[0] != asset:
                continue
            stratum = strata[key]
            for payload in banked:
                for name, values in payload.items():
                    stratum.pending[name].extend(values)
            stratum.flush()
            pending[key] = []
        for cell in by_day[(asset, d8)]:
            key = (cell.asset, cell.phase)
            stratum = strata.setdefault(key, Stratum())
            cuts = stratum.cuts()
            pending.setdefault(key, []).append(contributions(cell))
            if not cuts.scored:
                unscored += 1
                for name in PRICED_LINES:
                    shots[name].append(Shot(
                        cell.position, cell.asset, cell.d8, cell.year,
                        cell.phase, 0, "", -1, -1, float("nan"), MISS_UNSCORED))
                continue
            scored += 1
            _run_cell(cell, cuts, shots, entries, attrition)
    return RunOut(shots, entries, attrition, unscored, scored)


def _run_cell(cell: Cell11, cuts: Cuts, shots: dict[str, list[Shot]],
                entries: dict[str, list[S1.Entry]],
                attrition: Mapping[str, dict[str, dict[str, int]]]) -> None:
    passes: dict[int, list[Attempt]] = {}
    for side in (1, -1):
        passes[side] = run_side(cell.sides[side], cuts)
        for attempt in passes[side]:
            _count(attrition[cell.asset], attempt)
            _count(attrition["POOLED"], attempt)

    ready_s4 = sorted((a.s4_bar, a.side, a.lane) for side in (1, -1)
                      for a in passes[side] if not a.veto)
    ready_s3 = sorted((a.s3_bar, a.side, a.lane) for side in (1, -1)
                      for a in passes[side] if a.s3_bar >= 0
                      and a.reached in ("S4_HOLD", "S5_ENTRY"))
    # The stage-shuffled control keeps ONLY the arrivals; S2-S4 are waived and
    # the wait is the fixed six bars.  It is the price of the ordering.
    ready_shuffle = sorted((a.arrival_bar + SHUFFLE_LAG_BARS, a.side, "")
                           for side in (1, -1) for a in passes[side])

    for name, ready in ((BASE_LINE, ready_s4), (S3_LINE, ready_s3),
                        (SHUFFLE_LINE, ready_shuffle)):
        fires = _resolve(cell.sides, [row for row in ready
                                      if 0 <= row[0] < cell.n])
        for fire in fires:
            shot = _finish(cell, fire)
            shots[name].append(shot)
            if name == BASE_LINE and fire.miss:
                attrition[cell.asset]["miss"][fire.miss] += 1
                attrition["POOLED"]["miss"][fire.miss] += 1
            if fire.entry_bar < 0:
                continue
            entry = S1.make_entry(cell.position, cell.rec, fire.entry_bar,
                                  fire.side)
            if entry is not None:
                entries[name].append(entry)


# --------------------------------------------------------------------------
# Reductions.
# --------------------------------------------------------------------------

def _rate(hits: int, total: int) -> dict[str, object]:
    low, high = S1.wilson(int(hits), int(total))
    return {"hits": int(hits), "n": int(total),
            "rate": (hits / total) if total else None,
            "ci_low": low if total else None, "ci_high": high if total else None}


def _q(values: Sequence[float], mark: float) -> float | None:
    array = np.asarray([float(v) for v in values], np.float64)
    array = array[np.isfinite(array)]
    return float(np.percentile(array, mark)) if len(array) else None


def shot_table(shots: Sequence[Shot], cells: int) -> dict[str, object]:
    taken = [row for row in shots if row.entry_bar >= 0]
    graded = [row for row in taken if row.side_ok is not None]
    full = [row for row in taken if row.postx_full]
    delays = [row.delay_s for row in taken]
    return {
        "cells": int(cells),
        "entries": len(taken),
        "coverage": (len(taken) / cells) if cells else None,
        "lane_fast": sum(1 for row in taken if row.lane == LANE_FAST),
        "lane_slow": sum(1 for row in taken if row.lane == LANE_SLOW),
        "postx1800": _rate(sum(1 for row in full if row.postx1800), len(full)),
        "postx_censored": len(taken) - len(full),
        "post_extreme_openended": _rate(
            sum(1 for row in taken if row.post_extreme), len(taken)),
        "soft_hit": _rate(sum(1 for row in taken if row.soft_hit), len(taken)),
        "side_agreement": _rate(sum(1 for row in graded if row.side_ok),
                                len(graded)),
        "delay_median_s": _q(delays, 50),
        "delay_p90_s": _q(delays, 90),
        "pre_terminal_fraction": _rate(
            sum(1 for row in taken if row.before_terminal), len(taken)),
        "depth_median_atr": _q([row.depth_atr for row in taken], 50),
        "wait_median_s": _q([row.wait_s for row in taken], 50),
    }


def _cash_and_shots(name: str, out: RunOut, cells_by: Mapping[str, int],
                    days: Mapping[str, int],
                    cells_by_phase: Mapping[str, int]) -> dict[str, object]:
    rows = out.shots[name]
    entries = out.entries[name]
    cash = S1.cash_line(entries, days, cells_by)
    block: dict[str, object] = {"by_asset": {}, "by_phase": {}, "by_year": {},
                                "pooled": {}}
    for asset in ASSETS:
        table = shot_table([r for r in rows if r.asset == asset],
                           cells_by.get(asset, 0))
        table["cash"] = cash[asset]
        block["by_asset"][asset] = table
    for phase in sorted(cells_by_phase):
        block["by_phase"][phase] = shot_table(
            [r for r in rows if r.phase == phase], cells_by_phase[phase])
    # Per-year cuts: diagnostic columns only, never a selection axis.
    for asset in ASSETS:
        for year in sorted({row.year for row in rows if row.asset == asset}):
            subset = [r for r in rows if r.asset == asset and r.year == year]
            cell_count = len({r.cell for r in subset})
            table = shot_table(subset, cell_count)
            sub_entries = [e for e in entries
                           if e.asset == asset and e.d8 // 10000 == year]
            certs = np.asarray([e.cert_usd for e in sub_entries], np.float64)
            n_days = len({e.d8 for e in sub_entries}) or 1
            table["cash"] = {
                "trades": len(sub_entries),
                "usd_per_asset_day": float(certs.sum() / n_days) if len(certs) else 0.0,
                "usd_per_trade": float(certs.mean()) if len(certs) else 0.0,
                "total_usd": float(certs.sum()) if len(certs) else 0.0,
                "win_rate": float((certs > 0).mean()) if len(certs) else None,
                "wall_rate": float(np.mean([e.wall for e in sub_entries]))
                if sub_entries else None,
                "walls": int(sum(e.wall for e in sub_entries)),
                "explore_days_with_a_trade": n_days,
                "mdd_day_usd": S1.asset_mdd_day(sub_entries, asset),
            }
            table["wall_ci"] = _rate(int(sum(e.wall for e in sub_entries)),
                                     len(sub_entries))
            block["by_year"][f"{asset}/{year}"] = table
    block["pooled"] = shot_table(rows, sum(cells_by.values()))
    return block


def year_flags(block: Mapping[str, object]) -> list[str]:
    """Flag (asset, year) cells whose wall CI or cash sign disagrees across years."""

    flags: list[str] = []
    table = block["by_year"]
    for asset in ASSETS:
        keys = sorted(k for k in table if k.startswith(f"{asset}/"))
        for left in range(len(keys)):
            for right in range(left + 1, len(keys)):
                a, b = table[keys[left]], table[keys[right]]
                ca, cb = a["cash"], b["cash"]
                if ca["trades"] < 3 or cb["trades"] < 3:
                    continue
                if (ca["usd_per_asset_day"] > 0.0) != (cb["usd_per_asset_day"] > 0.0):
                    flags.append(f"{keys[left]} vs {keys[right]}: cash sign flips "
                                 f"({ca['usd_per_asset_day']:.0f} vs "
                                 f"{cb['usd_per_asset_day']:.0f})")
                wa, wb = a["wall_ci"], b["wall_ci"]
                if (wa["ci_low"] is not None and wb["ci_high"] is not None
                        and (wa["ci_low"] > wb["ci_high"]
                             or wb["ci_low"] > wa["ci_high"])):
                    flags.append(f"{keys[left]} vs {keys[right]}: wall CIs "
                                 f"disjoint ({wa['rate']:.3f} vs {wb['rate']:.3f})")
    return flags


def standdown(entries: Sequence[S1.Entry],
              explore_days: Mapping[str, list[int]]) -> list[S1.Entry]:
    """After any wall, no new entries that asset-day nor the next EXPLORE day."""

    kept: list[S1.Entry] = []
    blocked: dict[str, set[int]] = {asset: set() for asset in ASSETS}
    for row in sorted(entries, key=lambda e: (e.asset, e.ts_ns, e.text)):
        if row.d8 in blocked[row.asset]:
            continue
        kept.append(row)
        if not row.wall:
            continue
        days = explore_days.get(row.asset, [])
        blocked[row.asset].add(row.d8)
        after = [d for d in sorted(days) if d > row.d8]
        if after:
            blocked[row.asset].add(after[0])
    return kept


def sweep8_control() -> dict[str, object]:
    """The sweep-8 CONTROL line's own receipt numbers, read not retyped."""

    if not SWEEP8_PATH.is_file():
        return {"status": "ABSENT", "path": str(SWEEP8_PATH)}
    payload = json.loads(SWEEP8_PATH.read_text())
    out: dict[str, object] = {"status": "OK", "source": str(SWEEP8_PATH),
                              "line": "CONTROL", "by_asset": {}}
    # Paths per sweep 8's own report layout: stage_a.CONTROL.by_asset.<A> for
    # the no-cash reads, stage_b.lines.CONTROL.<A> for the priced ones.
    stage_a = payload.get("stage_a", {}).get("CONTROL", {}).get("by_asset", {})
    lines = payload.get("stage_b", {}).get("lines", {}).get("CONTROL", {})
    horizons = (payload.get("horizons", {}).get("CONTROL", {})
                .get("by_asset", {}))
    for asset in ASSETS:
        row: dict[str, object] = {}
        block = stage_a.get(asset, {})
        for name in ("coverage", "delay_median_s", "delay_p90_s",
                     "depth_median_atr", "entries"):
            if name in block:
                row[name] = block[name]
        for name in ("post_extension", "soft_hit", "side_agree"):
            value = block.get(name)
            if isinstance(value, Mapping):
                row[name] = value.get("rate")
        window = horizons.get(asset, {})
        if isinstance(window.get("postx1800_entry"), Mapping):
            row["postx1800_entry"] = window["postx1800_entry"].get("rate")
        cash = lines.get(asset)
        if isinstance(cash, Mapping):
            row.update({k: cash.get(k) for k in
                        ("usd_per_asset_day", "usd_per_trade", "win_rate",
                         "wall_rate", "walls", "mdd_day_usd", "mdd_trade_usd",
                         "trades")})
        out["by_asset"][asset] = row
    return out


# --------------------------------------------------------------------------
# Stage B: the priced battery.
# --------------------------------------------------------------------------

def stage_b(out: RunOut, records: Sequence[S1.CellRec], days: Mapping[str, int],
            cells_by: Mapping[str, int],
            explore_days: Mapping[str, list[int]]) -> dict[str, object]:
    priced: dict[str, list[S1.Entry]] = {name: out.entries[name]
                                         for name in PRICED_LINES}
    base_cash = S1.cash_line(priced[BASE_LINE], days, cells_by)
    # The stand-down overlay is priced ONLY when MDD is what the base line
    # misses on: a line already failing on cash gains nothing from a cadence
    # rule that only removes trades.
    binding_mdd = any(
        (base_cash[asset]["mdd_day_usd"] >= MDD_CAP_USD
         or base_cash[asset]["mdd_trade_usd"] >= MDD_CAP_USD)
        and base_cash[asset]["usd_per_asset_day"] > 0.0
        for asset in DECIDING)
    if binding_mdd:
        priced[STANDDOWN_LINE] = standdown(priced[BASE_LINE], explore_days)

    report: dict[str, object] = {
        "standdown_variant_priced": bool(binding_mdd),
        "standdown_reason": ("base MDD is the binding miss on a deciding asset"
                             if binding_mdd else
                             "base MDD is not the binding miss; variant not priced"),
        "cash": {}, "replays": {}, "stress": {}, "lines": sorted(priced)}
    for name, rows in priced.items():
        report["cash"][name] = S1.cash_line(rows, days, cells_by)
        report["stress"][name] = {
            asset: S3.stress_line(rows, records, days, cells_by, asset,
                                  STRESS_RATE)
            for asset in ASSETS}
        report["replays"][name] = S1.replay_line(
            rows, records, f"mill-sweep11:{code_sha()[:16]}:{name}")
    # The null is keyed per (asset, line) exactly as sweep 8 keyed it, so the
    # max-statistic pool spans every priced line INCLUDING the S3 variant.
    pool = {f"{asset}/{name}": [row for row in rows if row.asset == asset]
            for name, rows in priced.items() for asset in ASSETS}
    report["null"] = S1.block_null(pool, explore_days, draws=NULL_DRAWS,
                                   seed=SEED)
    report["null_pool"] = sorted(pool)
    return report


# --------------------------------------------------------------------------
# The pre-registered decision table, printed before stage B runs.
# --------------------------------------------------------------------------

def print_decision_table() -> None:
    print("\n" + "=" * 78)
    print("PRE-REGISTERED DECISION TABLE (printed before stage B reads any cash)")
    print("=" * 78)
    print("FREEZE-CANDIDATE, on a DECIDING asset (NKD, SI), all of:")
    print(f"    cash/day >= its rung (NKD {DAY_RUNG_USD['NKD']:.0f}, "
          f"SI {DAY_RUNG_USD['SI']:.0f})")
    print(f"    MDD both orderings (day and trade) < {MDD_CAP_USD:.0f}")
    print("    2% adversarial stress cash positive")
    print(f"    adjusted block-null p <= {NULL_CEILING}")
    print("INTERESTING, on a DECIDING asset, all of:")
    print(f"    wall rate <= {INTERESTING_WALL_CEILING}")
    print(f"    coverage >= {INTERESTING_COVERAGE_FLOOR}")
    print(f"    cash/day >= {INTERESTING_USD_DAY:.0f}")
    print(f"    MDD_day < {INTERESTING_MDD_DAY:.0f}")
    print("KILL otherwise, reporting every fired bound AND the attrition stage")
    print("    carrying the most loss.  HG is report-only throughout.")
    print("=" * 78)


def decide(report: Mapping[str, object]) -> dict[str, object]:
    stage_a = report["stage_a"][BASE_LINE]["by_asset"]
    cash = report["stage_b"]["cash"][BASE_LINE]
    stress = report["stage_b"]["stress"][BASE_LINE]
    null = report["stage_b"]["null"]["by_line"]
    out: dict[str, object] = {"verdict": "KILL", "by_asset": {},
                              "fired_bounds": [], "worst_stage": worst_stage(
                                  report["attrition"]["POOLED"])}
    for asset in DECIDING:
        line = cash[asset]
        table = stage_a[asset]
        wall = line["wall_rate"]
        cover = table["coverage"] or 0.0
        p_adj = null.get(f"{asset}/{BASE_LINE}", {}).get("p_max_adjusted")
        freeze = bool(
            line["usd_per_asset_day"] >= DAY_RUNG_USD[asset]
            and line["mdd_day_usd"] < MDD_CAP_USD
            and line["mdd_trade_usd"] < MDD_CAP_USD
            and stress[asset]["usd_per_asset_day"] > 0.0
            and p_adj is not None and float(p_adj) <= NULL_CEILING)
        interesting = bool(
            wall <= INTERESTING_WALL_CEILING
            and cover >= INTERESTING_COVERAGE_FLOOR
            and line["usd_per_asset_day"] >= INTERESTING_USD_DAY
            and line["mdd_day_usd"] < INTERESTING_MDD_DAY)
        fired = []
        if line["usd_per_asset_day"] < DAY_RUNG_USD[asset]:
            fired.append(f"{asset} cash/day {line['usd_per_asset_day']:.1f} "
                         f"< rung {DAY_RUNG_USD[asset]:.0f}")
        if line["mdd_day_usd"] >= MDD_CAP_USD:
            fired.append(f"{asset} MDD_day {line['mdd_day_usd']:.0f} >= "
                         f"{MDD_CAP_USD:.0f}")
        if line["mdd_trade_usd"] >= MDD_CAP_USD:
            fired.append(f"{asset} MDD_trade {line['mdd_trade_usd']:.0f} >= "
                         f"{MDD_CAP_USD:.0f}")
        if stress[asset]["usd_per_asset_day"] <= 0.0:
            fired.append(f"{asset} stress cash "
                         f"{stress[asset]['usd_per_asset_day']:.1f} <= 0")
        if p_adj is not None and float(p_adj) > NULL_CEILING:
            fired.append(f"{asset} adjusted null p {float(p_adj):.3f} > "
                         f"{NULL_CEILING}")
        if wall > INTERESTING_WALL_CEILING:
            fired.append(f"{asset} wall {wall:.3f} > {INTERESTING_WALL_CEILING}")
        if cover < INTERESTING_COVERAGE_FLOOR:
            fired.append(f"{asset} coverage {cover:.3f} < "
                         f"{INTERESTING_COVERAGE_FLOOR}")
        out["by_asset"][asset] = {"freeze_candidate": freeze,
                                  "interesting": interesting,
                                  "cash_usd_day": line["usd_per_asset_day"],
                                  "wall_rate": wall, "coverage": cover,
                                  "mdd_day_usd": line["mdd_day_usd"],
                                  "mdd_trade_usd": line["mdd_trade_usd"]}
        out["fired_bounds"].extend(fired)
        if freeze:
            out["verdict"] = "FREEZE-CANDIDATE"
        elif interesting and out["verdict"] == "KILL":
            out["verdict"] = "INTERESTING"
    return out


def worst_stage(table: Mapping[str, dict[str, int]]) -> dict[str, object]:
    """The attrition stage that loses the most opportunities."""

    loss = {"S2_ABSORPTION": table["veto"][VETO_S2_RUN] + table["veto"][VETO_S2_WINDOW],
            "S3_TRANSFER": table["veto"][VETO_S3_EXTREME] + table["veto"][VETO_S3_WINDOW],
            "S4_HOLD": table["veto"][VETO_S4_EXTREME] + table["veto"][VETO_S4_ZONE]}
    entered = max(1, table["entered"]["S1_ARRIVAL"])
    stage = max(loss, key=lambda name: loss[name])
    return {"stage": stage, "vetoes": int(loss[stage]),
            "share_of_arrivals": float(loss[stage] / entered), "by_stage": loss}


# --------------------------------------------------------------------------
# Printing.
# --------------------------------------------------------------------------

def _n(value: object, width: int = 8, digits: int = 2) -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return f"{'-':>{width}s}"
    if isinstance(value, (int, np.integer)) and digits == 0:
        return f"{int(value):{width}d}"
    return f"{float(value):{width}.{digits}f}"


def print_attrition(report: Mapping[str, object]) -> None:
    print("\n" + "=" * 78)
    print("STAGE ATTRITION - the diagnostic heart.  A failure names its stage.")
    print("=" * 78)
    print(f"{'scope':8s} {'S1_arr':>8s} {'S2_ent':>8s} {'S3_ent':>8s} "
          f"{'S4_ent':>8s} {'S5_rdy':>8s} | {'fast':>6s} {'slow':>6s}")
    for scope in list(ASSETS) + ["POOLED"]:
        table = report["attrition"][scope]
        print(f"{scope:8s} " + " ".join(
            _n(table['entered'][stage], 8, 0) for stage in STAGES)
            + f" | {_n(table['lane'][LANE_FAST], 6, 0)} "
              f"{_n(table['lane'][LANE_SLOW], 6, 0)}")
    print(f"\n{'scope':8s} " + " ".join(f"{name:>18s}" for name in VETOES))
    for scope in list(ASSETS) + ["POOLED"]:
        table = report["attrition"][scope]
        print(f"{scope:8s} " + " ".join(
            f"{table['veto'][name]:18d}" for name in VETOES))
    print(f"\n{'scope':8s} " + " ".join(f"{name:>22s}" for name in MISSES))
    for scope in list(ASSETS) + ["POOLED"]:
        table = report["attrition"][scope]
        print(f"{scope:8s} " + " ".join(
            f"{table['miss'][name]:22d}" for name in MISSES))
    worst = report["decision"]["worst_stage"] if "decision" in report else \
        worst_stage(report["attrition"]["POOLED"])
    print(f"\nstage carrying the most loss: {worst['stage']} "
          f"({worst['vetoes']} vetoes, {worst['share_of_arrivals']:.3f} of arrivals)")
    print(f"per-stage veto totals: {worst['by_stage']}")


def print_stage_a(report: Mapping[str, object]) -> None:
    for name in report["stage_a"]:
        block = report["stage_a"][name]
        print("\n" + "-" * 78)
        print(f"STAGE A  line {name}  by asset")
        print(f"{'asset':6s} {'cells':>7s} {'entries':>8s} {'cover':>7s} "
              f"{'fast':>6s} {'slow':>6s} {'postX':>7s} {'ci_lo':>7s} "
              f"{'ci_hi':>7s} {'soft':>7s} {'side':>7s} {'delay_med':>10s} "
              f"{'delay_p90':>10s} {'preterm':>8s} {'depth':>7s}")
        for asset in ASSETS:
            row = block["by_asset"][asset]
            print(f"{asset:6s} {_n(row['cells'], 7, 0)} "
                  f"{_n(row['entries'], 8, 0)} {_n(row['coverage'], 7, 3)} "
                  f"{_n(row['lane_fast'], 6, 0)} {_n(row['lane_slow'], 6, 0)} "
                  f"{_n(row['postx1800']['rate'], 7, 3)} "
                  f"{_n(row['postx1800']['ci_low'], 7, 3)} "
                  f"{_n(row['postx1800']['ci_high'], 7, 3)} "
                  f"{_n(row['soft_hit']['rate'], 7, 3)} "
                  f"{_n(row['side_agreement']['rate'], 7, 3)} "
                  f"{_n(row['delay_median_s'], 10, 0)} "
                  f"{_n(row['delay_p90_s'], 10, 0)} "
                  f"{_n(row['pre_terminal_fraction']['rate'], 8, 3)} "
                  f"{_n(row['depth_median_atr'], 7, 3)}")
        print(f"\nSTAGE A  line {name}  by phase")
        print(f"{'phase':6s} {'entries':>8s} {'postX':>7s} {'soft':>7s} "
              f"{'side':>7s} {'delay_med':>10s}")
        for phase in sorted(block["by_phase"]):
            row = block["by_phase"][phase]
            print(f"{phase:6s} {_n(row['entries'], 8, 0)} "
                  f"{_n(row['postx1800']['rate'], 7, 3)} "
                  f"{_n(row['soft_hit']['rate'], 7, 3)} "
                  f"{_n(row['side_agreement']['rate'], 7, 3)} "
                  f"{_n(row['delay_median_s'], 10, 0)}")
        print(f"\nSTAGE A  line {name}  by YEAR (diagnostic only, no selection)")
        print(f"{'asset/yr':10s} {'cells':>7s} {'entries':>8s} {'cover':>7s} "
              f"{'usd/day':>9s} {'usd/trd':>9s} {'win':>6s} {'wall':>6s} "
              f"{'wall_lo':>8s} {'wall_hi':>8s} {'mdd_day':>9s} {'postX':>7s}")
        for key in sorted(block["by_year"]):
            row = block["by_year"][key]
            cash = row["cash"]
            print(f"{key:10s} {_n(row['cells'], 7, 0)} "
                  f"{_n(row['entries'], 8, 0)} {_n(row['coverage'], 7, 3)} "
                  f"{_n(cash['usd_per_asset_day'], 9, 1)} "
                  f"{_n(cash['usd_per_trade'], 9, 1)} "
                  f"{_n(cash['win_rate'], 6, 3)} {_n(cash['wall_rate'], 6, 3)} "
                  f"{_n(row['wall_ci']['ci_low'], 8, 3)} "
                  f"{_n(row['wall_ci']['ci_high'], 8, 3)} "
                  f"{_n(cash['mdd_day_usd'], 9, 0)} "
                  f"{_n(row['postx1800']['rate'], 7, 3)}")
        flags = report["year_flags"].get(name, [])
        print(f"year-conditioning flags: {len(flags)}")
        for flag in flags:
            print(f"    FLAG {flag}")


def print_stage_b(report: Mapping[str, object]) -> None:
    block = report["stage_b"]
    print("\n" + "=" * 78)
    print("STAGE B  priced lines")
    print("=" * 78)
    print(f"{'line':20s} {'asset':6s} {'trades':>7s} {'cover':>7s} "
          f"{'usd/day':>9s} {'usd/trd':>9s} {'win':>6s} {'wall':>6s} "
          f"{'mdd_day':>9s} {'mdd_trd':>9s} {'rung':>6s}")
    for name in block["lines"]:
        for asset in ASSETS:
            row = block["cash"][name][asset]
            print(f"{name:20s} {asset:6s} {int(row['trades']):7d} "
                  f"{_n(row['coverage'], 7, 3)} "
                  f"{_n(row['usd_per_asset_day'], 9, 1)} "
                  f"{_n(row['usd_per_trade'], 9, 1)} "
                  f"{_n(row['win_rate'], 6, 3)} {_n(row['wall_rate'], 6, 3)} "
                  f"{_n(row['mdd_day_usd'], 9, 0)} "
                  f"{_n(row['mdd_trade_usd'], 9, 0)} "
                  f"{str(bool(row['clears_rung'])):>6s}")
    print("\nSTAGE B  sweep-8 CONTROL line (receipt numbers imported)")
    control = report["controls"]["sweep8_control"]
    print(f"status {control['status']}")
    if control["status"] == "OK":
        print(f"{'asset':6s} " + " ".join(
            f"{k:>16s}" for k in ("usd_per_asset_day", "wall_rate",
                                  "coverage", "mdd_day_usd")))
        for asset in ASSETS:
            row = control["by_asset"][asset]
            print(f"{asset:6s} " + " ".join(
                _n(row.get(k), 16, 3) for k in ("usd_per_asset_day", "wall_rate",
                                                "coverage", "mdd_day_usd")))
    print("\nSTAGE B  engine replay (partial-day label)")
    print(f"{'line':20s} {'status':6s} {'trades':>7s} {'usd/day':>9s} "
          f"{'usd/trd':>9s} {'mdd':>9s} {'skips':>6s}  label")
    for name in block["lines"]:
        row = block["replays"][name]
        print(f"{name:20s} {str(row.get('status')):6s} "
              f"{int(row.get('trades', 0)):7d} "
              f"{_n(row.get('usd_per_asset_day'), 9, 1)} "
              f"{_n(row.get('usd_per_trade'), 9, 1)} "
              f"{_n(row.get('max_drawdown_usd'), 9, 0)} "
              f"{int(row.get('occupancy_or_cap_skips', 0)):6d}  "
              f"{str(row.get('label', ''))}")
    print(f"\nSTAGE B  {STRESS_RATE:.0%} adversarial stress")
    print(f"{'line':20s} {'asset':6s} {'flips':>6s} {'avail':>6s} "
          f"{'usd/day':>9s} {'damage':>10s} {'mdd_day':>9s} {'wall':>6s}")
    for name in block["lines"]:
        for asset in ASSETS:
            row = block["stress"][name][asset]
            print(f"{name:20s} {asset:6s} {int(row['flips_applied']):6d} "
                  f"{int(row['flips_available']):6d} "
                  f"{_n(row['usd_per_asset_day'], 9, 1)} "
                  f"{_n(row['damage_usd'], 10, 1)} "
                  f"{_n(row['mdd_day_usd'], 9, 0)} "
                  f"{_n(row['wall_rate'], 6, 3)}")
    null = block["null"]
    print(f"\nSTAGE B  block-permutation null, {null['draws']} draws, "
          f"seed {null['seed']}, max-stat across priced lines")
    print(f"{'line':20s} {'obs_asset_mdd':>14s} {'null_mean':>10s} "
          f"{'p_own':>7s} {'p_max_adj':>10s} {'p_pooled_adj':>13s}")
    for key in sorted(null["by_line"]):
        row = null["by_line"][key]
        print(f"{key:20s} {_n(row['observed_max_asset_mdd_usd'], 14, 0)} "
              f"{_n(row['null_asset_mdd_mean_usd'], 10, 0)} "
              f"{_n(row['p_own'], 7, 3)} {_n(row['p_max_adjusted'], 10, 3)} "
              f"{_n(row['p_pooled_max_adjusted'], 13, 3)}")
    if null.get("lines_held_out_empty"):
        print(f"held out (no entries): {null['lines_held_out_empty']}")
    print(f"\nstand-down variant priced: {block['standdown_variant_priced']} "
          f"({block['standdown_reason']})")


def print_verdict(report: Mapping[str, object]) -> None:
    block = report["decision"]
    print("\n" + "=" * 78)
    print(f"DECISION: {block['verdict']}")
    print("=" * 78)
    print(f"{'asset':6s} {'freeze':>8s} {'interest':>9s} {'usd/day':>9s} "
          f"{'wall':>6s} {'cover':>7s} {'mdd_day':>9s} {'mdd_trd':>9s}")
    for asset in DECIDING:
        row = block["by_asset"][asset]
        print(f"{asset:6s} {str(row['freeze_candidate']):>8s} "
              f"{str(row['interesting']):>9s} "
              f"{_n(row['cash_usd_day'], 9, 1)} {_n(row['wall_rate'], 6, 3)} "
              f"{_n(row['coverage'], 7, 3)} {_n(row['mdd_day_usd'], 9, 0)} "
              f"{_n(row['mdd_trade_usd'], 9, 0)}")
    print("\nfired bounds:")
    for bound in block["fired_bounds"]:
        print(f"    {bound}")
    worst = block["worst_stage"]
    print(f"\nattrition stage carrying the most loss: {worst['stage']} "
          f"({worst['vetoes']} vetoes = {worst['share_of_arrivals']:.3f} "
          f"of all arrivals)")


# --------------------------------------------------------------------------
# The hypothesis log.
# --------------------------------------------------------------------------

def log_rows(report: Mapping[str, object]) -> list[dict[str, object]]:
    stamp = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    shared = {
        "registered_utc": stamp, "family": FAMILY, "spec_sha": SPEC_SHA,
        "code_sha": report["code_sha"], "split_sha": report["split_sha"],
        "outcome_law_sha": report["outcome_law_sha"], "null_seed": SEED,
        "parent_trial": PARENT_TRIAL, "selection_rule": SELECTION_RULE,
        "verdict": ""}
    rows: list[dict[str, object]] = []
    block = report["stage_b"]
    worst = report["decision"]["worst_stage"]
    for index, name in enumerate(block["lines"], start=1):
        cash = block["cash"][name]
        stage_a = report["stage_a"].get(name, report["stage_a"][BASE_LINE])
        null = block["null"]["by_line"].get(name, {})
        rows.append(dict(shared, **{
            "id": f"sweep11-{index:03d}",
            "rule": f"grammar-automaton/{name}",
            "params": (f"p60/p40 fixed; zone {ZONE_ATR} ATR; k={S4_HOLD_BARS}; "
                       f"wait {WAIT_LIMIT_BARS} bars; remain {REMAIN_MIN_S}s"),
            "days": sum(report["explore_days"].values()),
            "coverage": stage_a["pooled"]["coverage"],
            "delay_med_s": stage_a["pooled"]["delay_median_s"],
            "err_rate_hg": _one_minus(
                stage_a["by_asset"]["HG"]["side_agreement"]["rate"]),
            "err_rate_nkd": _one_minus(
                stage_a["by_asset"]["NKD"]["side_agreement"]["rate"]),
            "err_rate_si": _one_minus(
                stage_a["by_asset"]["SI"]["side_agreement"]["rate"]),
            "walls_hg": cash["HG"]["walls"], "walls_nkd": cash["NKD"]["walls"],
            "walls_si": cash["SI"]["walls"],
            "hg_usd_day": cash["HG"]["usd_per_asset_day"],
            "nkd_usd_day": cash["NKD"]["usd_per_asset_day"],
            "si_usd_day": cash["SI"]["usd_per_asset_day"],
            "mdd_hg": cash["HG"]["mdd_day_usd"],
            "mdd_nkd": cash["NKD"]["mdd_day_usd"],
            "mdd_si": cash["SI"]["mdd_day_usd"],
            "replay_skips": block["replays"][name].get(
                "occupancy_or_cap_skips"),
            "null_margin": null.get("p_max_adjusted"),
            "note": (f"F8-GRAMMAR ordered automaton; worst stage "
                     f"{worst['stage']} ({worst['share_of_arrivals']:.3f} of "
                     f"arrivals); lane fast/slow "
                     f"{stage_a['pooled']['lane_fast']}/"
                     f"{stage_a['pooled']['lane_slow']}"),
        }))
    return rows


def _one_minus(value: object) -> float | None:
    return None if value is None else float(1.0 - float(value))


# --------------------------------------------------------------------------
# SELFTEST.  Synthetic fixtures only; touches zero era bytes.
# --------------------------------------------------------------------------

def _check(name: str, ok: bool, detail: str = "") -> tuple[str, bool, str]:
    return (name, bool(ok), detail)


CUTS = Cuts(attack_p60=100.0, yield_p40=0.5, onesided_p60=0.8, absdelta_p40=50.0)


def _fixture(bars: int = 24) -> dict[str, np.ndarray]:
    """A quiet, in-zone, nothing-happens tape the cases mutate one field of."""

    return {
        "mid": np.full(bars, 1000.0),
        "prior_ext": np.full(bars, 1000.0),
        "new_ext": np.zeros(bars, bool),
        "opp_new_ext": np.zeros(bars, bool),
        "attack": np.zeros(bars),
        "yield_pa": np.full(bars, 9.0),
        "onesided": np.zeros(bars),
        "delta": np.zeros(bars),
        "touch": np.zeros(bars, bool),
        "cand": np.zeros(bars, bool),
    }


def _side(parts: Mapping[str, np.ndarray], side: int = 1, atr: float = 100.0
          ) -> SideInput:
    bars = len(parts["mid"])
    mid = np.asarray(parts["mid"], np.float64)
    prior = np.asarray(parts["prior_ext"], np.float64)
    delta = np.asarray(parts["delta"], np.float64)
    return SideInput(
        side=side, atr=atr, mid=mid, prior_ext=prior,
        new_ext=np.asarray(parts["new_ext"], bool),
        opp_new_ext=np.asarray(parts["opp_new_ext"], bool),
        in_zone=np.abs(mid - prior) <= ZONE_ATR * atr,
        attack=np.asarray(parts["attack"], np.float64),
        yield_pa=np.asarray(parts["yield_pa"], np.float64),
        onesided=np.asarray(parts["onesided"], np.float64),
        delta=delta, absdelta=np.abs(delta),
        touch=np.asarray(parts["touch"], bool),
        cand=np.asarray(parts["cand"], bool),
        remaining_s=np.full(bars, 9000.0),
        tradeable=np.ones(bars, bool))


def _fast_fixture() -> dict[str, np.ndarray]:
    """One complete FAST-lane pass, transitions hand-computed.

    bar 3 arrival (in zone, attack 150 >= p60 100), arrival extreme 1000.
    bar 3 absorption (yield 0.1 <= p40 0.5), so S2 = 3.
    bar 4 delta flips -60 -> +80 toward the fade, |80| >= p40 50, so S3 = 4.
    bars 5,6,7 hold: no new extreme, |mid-1000| = 12 > 0.075*100 = 7.5.
    S4 completes at bar 7; the candidate at bar 8 sits 12/100 = 0.12 ATR
    from the extreme, inside the 0.15 band, so the entry is bar 8.
    """

    parts = _fixture()
    parts["attack"][3] = 150.0
    parts["yield_pa"][3] = 0.1
    parts["delta"][2] = -60.0
    parts["delta"][4] = 80.0
    parts["mid"][4:] = 1012.0
    parts["cand"][8] = True
    return parts


def _slow_fixture() -> dict[str, np.ndarray]:
    """One complete SLOW-lane pass, transitions hand-computed.

    bar 3 arrival + absorption as above but with NO delta flip anywhere.
    bar 5 pulls away: mid 1010, interior 10 > 7.5, gate one.  Bars 6 and 7 sit
      at 1010 too - interior 10 is not NEARER than 10, so neither is a return.
    bar 8 retests: mid 1004 is back in zone (4 <= 15), no new extreme, and
      returns toward the level (0 < 4 < 10), gate two, so S3 = 8, slow lane.
    bars 9,10,11 hold at 1012 (12 > 7.5), S4 completes at bar 11.
    candidate at bar 12, depth 0.12 ATR, entry bar 12.
    """

    parts = _fixture()
    parts["attack"][3] = 150.0
    parts["yield_pa"][3] = 0.1
    parts["mid"][5:8] = 1010.0
    parts["mid"][8] = 1004.0
    parts["mid"][9:] = 1012.0
    parts["cand"][12] = True
    return parts


def selftest() -> int:
    out: list[tuple[str, bool, str]] = []
    mutant = _mutant()

    # --- the two complete passes ------------------------------------------
    fast = run_side(_side(_fast_fixture()), CUTS)
    out.append(_check("FAST lane: one attempt, completes S4",
                      len(fast) == 1 and fast[0].reached == "S5_ENTRY"
                      and not fast[0].veto, f"{fast}"))
    out.append(_check("FAST lane: hand-computed transitions 3/3/4/7",
                      len(fast) == 1 and (fast[0].arrival_bar, fast[0].s2_bar,
                                          fast[0].s3_bar, fast[0].s4_bar)
                      == (3, 3, 4, 7) and fast[0].lane == LANE_FAST,
                      f"{fast[0] if fast else None}"))
    slow = run_side(_side(_slow_fixture()), CUTS)
    out.append(_check("SLOW lane: one attempt, completes S4",
                      len(slow) == 1 and slow[0].reached == "S5_ENTRY"
                      and not slow[0].veto, f"{slow}"))
    out.append(_check("SLOW lane: hand-computed transitions 3/3/8/11",
                      len(slow) == 1 and (slow[0].arrival_bar, slow[0].s2_bar,
                                          slow[0].s3_bar, slow[0].s4_bar)
                      == (3, 3, 8, 11) and slow[0].lane == LANE_SLOW,
                      f"{slow[0] if slow else None}"))

    # --- entry resolution on the fast fixture -----------------------------
    inp = _side(_fast_fixture())
    fires = _resolve({1: inp, -1: inp}, [(7, 1, LANE_FAST)])
    out.append(_check("S5: entry at bar 8, depth 0.12 ATR",
                      len(fires) == 1 and fires[0].entry_bar == 8
                      and abs(fires[0].depth_atr - 0.12) < 1e-9,
                      f"{fires}"))

    # --- one veto-and-reset case per stage --------------------------------
    weak = _fast_fixture()
    weak["attack"][3] = 99.0                    # below the p60 arrival cutoff
    out.append(_check("VETO S1: arrival too weak, no attempt opens",
                      not run_side(_side(weak), CUTS), ""))

    loud = _fast_fixture()
    loud["yield_pa"][3:7] = 9.0                 # yield above p40 for the window
    got = run_side(_side(loud), CUTS)
    out.append(_check("VETO S2: absorption yield too high",
                      len(got) == 1 and got[0].veto == VETO_S2_WINDOW,
                      f"{got}"))

    noflip = _fast_fixture()
    noflip["delta"][:] = 0.0                    # never flips
    noflip["mid"][4:] = 1000.0                  # and never pulls away either
    got = run_side(_side(noflip), CUTS)
    out.append(_check("VETO S3: no flip and no pull-away",
                      len(got) == 1 and got[0].veto == VETO_S3_WINDOW,
                      f"{got}"))

    broken = _fast_fixture()
    broken["new_ext"][6] = True                 # a new extreme inside the hold
    got = run_side(_side(broken), CUTS)
    out.append(_check("VETO S4: hold broken by a new same-side extreme",
                      len(got) == 1 and got[0].veto == VETO_S4_EXTREME
                      and got[0].s4_bar == 6, f"{got}"))

    shallow = _fast_fixture()
    shallow["cand"][8] = False
    shallow["mid"][9:] = 1030.0                 # 0.30 ATR away, outside 0.15
    shallow["cand"][9] = True
    inp = _side(shallow)
    fires = _resolve({1: inp, -1: inp}, [(7, 1, LANE_FAST)])
    out.append(_check("VETO S5: candidate too far from the extreme",
                      len(fires) == 1 and fires[0].entry_bar < 0
                      and fires[0].miss == MISS_NO_DEPTH, f"{fires}"))

    cancel = _fast_fixture()
    cancel["opp_new_ext"][8] = True             # opposite extreme at the entry bar
    inp = _side(cancel)
    # The LONG side is ready at bar 7 and the SHORT side at bar 8; the bar-8
    # opposite extreme must kill both, not just the one that was waiting.
    fires = _resolve({1: inp, -1: inp}, [(7, 1, LANE_FAST), (8, -1, LANE_FAST)])
    out.append(_check("S5: opposite-side extreme cancels and resets both sides",
                      len(fires) == 2
                      and fires[0].miss == MISS_CANCELLED
                      and fires[1].miss == MISS_CANCELLED
                      and all(row.entry_bar < 0 for row in fires), f"{fires}"))

    # --- the reset is real: a vetoed side may arrive again ----------------
    twice = _fast_fixture()
    twice["attack"][3] = 150.0
    twice["yield_pa"][3:7] = 9.0                # first arrival dies at S2
    twice["attack"][12] = 150.0                 # and a second arrival follows
    twice["yield_pa"][12] = 0.1
    twice["mid"][12] = 1000.0
    twice["prior_ext"][12:] = 1000.0
    got = run_side(_side(twice), CUTS)
    out.append(_check("RESET: a vetoed side arrives again later",
                      len(got) == 2 and got[0].veto == VETO_S2_WINDOW
                      and got[1].arrival_bar == 12, f"{got}"))

    # --- THE MUTANT'S TARGET ----------------------------------------------
    # Stages present but OUT OF ORDER: the transfer flip lands at bar 2,
    # BEFORE the arrival at bar 3 and before absorption.  The strict sequence
    # must reject; an unordered menu over the same window accepts.
    disorder = _fixture()
    disorder["delta"][1] = -60.0
    disorder["delta"][2] = 80.0                 # the flip, before the arrival
    disorder["attack"][3] = 150.0
    disorder["yield_pa"][3] = 0.1
    disorder["mid"][4:] = 1012.0
    got = run_side(_side(disorder), CUTS)
    out.append(_check(
        "MUTANT TARGET: transfer BEFORE arrival is not a grammar pass",
        bool(got) and got[0].veto == VETO_S3_WINDOW, f"attempts={got}"))

    print(f"\nSELFTEST  sweep11  mutant={mutant or 'none'}")
    failures = 0
    for name, ok, detail in out:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}"
              + (f"   {detail}" if not ok else ""))
        failures += 0 if ok else 1
    red = [name for name, ok, _d in out if not ok]
    if mutant:
        # Every case states the ORDERED expectation.  The mutant must break at
        # least one; a mutant that leaves them all green is a mutant nothing
        # tests, which would mean the ordering is not load bearing here.
        print(f"  mutant={mutant}: {len(red)}/{len(out)} cases RED")
        for name in red:
            print(f"    RED  {name}")
        if not red:
            print(f"  DEAD: mutant {mutant} left every case green")
        return 1
    print(f"  {len(out) - failures}/{len(out)} green")
    return 1 if failures else 0


# --------------------------------------------------------------------------
# CLI.
# --------------------------------------------------------------------------

def _explore_days(assets: Sequence[str]) -> dict[str, list[int]]:
    payload = json.loads(SPLIT_PATH.read_text())
    return {asset: sorted(int(d) for d in payload["explore"][asset])
            for asset in assets}


def _json_default(value: object) -> object:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"unserialisable: {type(value)}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--log", action="store_true")
    parser.add_argument("--assets", nargs="*", default=list(ASSETS))
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()

    assets = tuple(args.assets)
    cells, days, skipped, records = build_cells(assets)
    if not cells:
        raise SweepRefusal("no EXPLORE cell carried flow, zones and an ATR prior")
    explore_days = _explore_days(assets)
    cells_by = {asset: sum(1 for cell in cells if cell.asset == asset)
                for asset in ASSETS}
    cells_by_phase: dict[str, int] = {}
    for cell in cells:
        cells_by_phase[cell.phase] = cells_by_phase.get(cell.phase, 0) + 1

    print_decision_table()

    out = run(cells)
    report: dict[str, object] = {
        "schema": SCHEMA, "spec": SPEC, "spec_sha": SPEC_SHA,
        "code_sha": code_sha(), "split_sha": split_sha(),
        "outcome_law_sha": outcome_law_sha(), "seed": SEED,
        "family": FAMILY, "parent_trial": PARENT_TRIAL,
        "selection_rule": SELECTION_RULE,
        "tier": "exploratory: can kill, cannot promote",
        "assets": list(assets), "cells": cells_by,
        "explore_days": {k: len(v) for k, v in explore_days.items()},
        "cells_skipped_no_substrate": skipped,
        "cells_unscored_stratum": out.unscored_cells,
        "cells_scored": out.scored_cells,
        "attrition": out.attrition,
        "stage_a": {}, "year_flags": {}, "controls": {}}
    for name in PRICED_LINES:
        report["stage_a"][name] = _cash_and_shots(name, out, cells_by, days,
                                                  cells_by_phase)
        report["year_flags"][name] = year_flags(report["stage_a"][name])
    report["controls"]["sweep8_control"] = sweep8_control()
    report["controls"]["stage_shuffled"] = {
        "line": SHUFFLE_LINE,
        "law": (f"same S1 arrivals, S2-S4 waived, entry at the first candidate "
                f"after arrival + {SHUFFLE_LAG_BARS} bars"),
        "prices": "what the grammar's ORDERING adds beyond arrival detection"}

    print_attrition(report)
    print_stage_a(report)

    report["stage_b"] = stage_b(out, records, days, cells_by, explore_days)
    report["decision"] = decide(report)
    print_stage_b(report)
    print_verdict(report)

    OUT_PATH.write_text(json.dumps(report, indent=2, default=_json_default,
                                   sort_keys=True) + "\n")
    print(f"\nwrote {OUT_PATH}")
    if args.log:
        rows = log_rows(report)
        written = S1.append_log(rows)
        print(f"appended {written} rows to {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
