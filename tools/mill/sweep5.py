#!/usr/bin/env python3
"""Sweep 5 of the side-resolution mill: the arbiter composition baseline.

Exploratory tier.  EXPLORE-day bytes only, can kill, cannot promote.  Sweep 4
ruled that terminality separates and the delay budget is real, and that the one
missing ingredient is the SIDE: side-blind first-quiet fades reached terminal
hit 0.75-0.82 while side_hit ran 0.36-0.57 and every priced line lost.  This
sweep measures Sol's composition, LATE-MEAN x TERMINAL, at the sweep-4
parameters:

  * the TERMINAL half is sweep 4's detector D(Q,H,k) - imported, not
    reimplemented, zone deleted (sweep-4 O4c: the zone moved false positives by
    at most 0.004);
  * the LATE-MEAN half is the arbiter ``s_arb(t) = sign(bar mid - the running
    session mean of bar mids)`` on completed bars, which decides WHICH extreme's
    quiet counts;
  * a detection is eligible only when its fade side equals ``s_arb`` at the
    DETECTION bar and again at the ENTRY CANDIDATE's bar.  The second read is
    the arrival recheck: disagreement cancels the detection and the state
    machine re-arms, exactly as a newer same-direction extreme does;
  * no entry before ``E`` seconds of session have elapsed (the "late" in
    late-mean), E in {3600, 5400}.

``vs_mean`` never becomes an entry clock: the arbiter only gates, the detector
still picks the time and the candidate plane still picks the fill.

Laws carried unchanged, imported and never re-implemented: the candidate-
anchored entry law and its candidate plane, the per-side detector geometry with
its re-arm/cancel semantics, the terminal/quiet/bounce machinery, the O-table
plumbing, the cash/day and ``_drawdown`` aggregations, the replay shaping, the
asset-day block-permutation null, the Wilson interval and ``append_log``.

Stages:

  STAGE A  no cash.  The per-asset composition grid Q x H x k x E, each with a
           D-ALONE control at the same (Q,H,k) that answers "what did the
           arbiter buy?".  Selection on the Wilson lower bound of JOINT hit
           (terminal AND the fade side equal to sign(Delta*) at the entry bar)
           under the raised per-asset coverage floors, then the per-phase Q
           question by the pooled false-positive rule.
  STAGE B  cash on the selected composition, its D-ALONE control, the runner-up
           and the per-phase-Q variant when the pooled rule keeps it, with
           engine replay, a 2% adversarial stress, block-permutation nulls and
           capture against the delay-matched sweep-4 O4b oracle row.

Every table reports per (asset, phase_idx) as well as per asset.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import datetime as dt
import json
import os
from pathlib import Path
import sys
import time
from typing import Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine.entry_v2.confirmation_types import NANOS_PER_SECOND

import context as CTX
import mill as M
import sweep1 as S1
import sweep2 as S2
import sweep3 as S3
import sweep4 as S4

# --------------------------------------------------------------------------
# The immutable law this sweep registers before it reads anything.
# --------------------------------------------------------------------------

SPEC = """QRE2MILLSWEEP5
tier=exploratory; explore-only; can kill, cannot promote.  parent=sweep4-081.
carried unchanged from sweep 4: 60 s completed bars (value at close t = the last
  trusted row strictly before t); CANDIDATE-ANCHORED entries (entry_ts = the
  candidate's own decision_ts_ns, quote = the last trusted row strictly before
  it, frozen cost from that row, side = the candidate's own side); one entry per
  cell; entry_ts <= phase_close - 1800 s; seed 20260827; W = sign(Delta*(900 s))
  under the LEGAL variant and the max(2*cost,100) band.
ARBITER (new).  s_arb(b) = sign(mid[b] - mean(mid[0..b])) on the cell's 60 s
  completed-bar lattice: the running session mean of bar mids, so every read at
  bar b uses only bars whose closes have passed.  s_arb is 0 while the mid sits
  exactly on its own running mean and no fade side then agrees.
COMPOSITION D(Q,H,k) x s_arb x E.  The detector is sweep 4's, zone DELETED: a
  direction's extreme at bar j becomes DETECTED-terminal at bar T when T-j >= Q
  minutes with no newer same-direction extreme and the retrace
  side*(mid[b]-mid[j])/ATR held >= H for every b in [T-k+1, T].  THE DETECTION
  IS ONE EVENT PER ARMED EXTREME: T is the FIRST bar of that extreme meeting the
  criteria, and the arbiter is read there.  A detection is ELIGIBLE only if the
  fade side equals s_arb at T.  The entry intent is then the first CLEAR
  fade-side candidate with decision_ts >= max(close(T), phase_open + E).
  ARRIVAL RECHECK: that candidate's own bar is floor((decision_ts -
  phase_open)/60 s), the last completed bar at or before the decision, and the
  fade side must equal s_arb there too.  ANY failure - either arbiter read, a
  newer same-direction extreme at or before the candidate, no candidate, or the
  1800 s deadline - CANCELS that detection, and re-arming means the extreme is
  spent: the next detection is the next same-direction extreme's.  This is the
  reading Sol's constraint forces.  Re-reading s_arb on later bars of the SAME
  extreme until it agrees would make the entry fire at the moment the mean call
  flips, i.e. it would make vs_mean the entry clock, which the design forbids.
  That rejected reading is still MEASURED, as the gate=retry control line, so
  the choice is a number and not an assumption.  Earliest surviving
  detection-entry across the two directions wins the cell.
grids (frozen branch table): Q_NKD {10,15,20}, Q_SI {20,30,45}, Q_HG {20,45}
  (HG report-only, USER-deferred); H {0.20,0.30}; k {1,3}; E {3600,5400} s.
  D-ALONE control per (Q,H,k): the same detector with no arbiter and no E floor
  (sweep 4's own law) - the arbiter's no-cash and cash delta.
STAGE A (no cash), per config per asset and per (asset, phase_idx): coverage
  over ALL cells, terminal_hit (no new adverse extreme between entry and phase
  close), side_hit (fade side == sign(Delta*) at the entry bar, 0 when the cell
  is not sharp there), joint_hit = terminal AND side with a Wilson 95% CI,
  median detection delay after the true terminal extreme, median entry time,
  cancel counts split arbiter-disagree vs new-extreme, and the no-candidate
  rate.  SELECTION per asset: maximise the joint_hit Wilson lower bound subject
  to coverage >= 0.40 (NKD), 0.35 (SI), 0.70 (HG, report-only; when unreachable
  the asset is flagged COVERAGE_FAIL and the max-coverage config is taken);
  ties to the smaller median detection delay, then the smaller Q, then the
  smaller E, then the key.
PER-PHASE Q (pooled rule).  The false positive is sweep-4 O4c's: a NON-terminal
  extreme the detector declares terminal.  Denominator = the cell's non-terminal
  extremes on both directions that pass the eligibility guard close(j) + Q <=
  phase_close - 1800 s; numerator = those carrying a D(Q,H,k) detection.  It is
  CELL-WEIGHTED per Sol's ruling: the per-cell rate is the unit, the reported FP
  is the mean over cells and the bound is the cell-block normal 95% upper bound
  mean + 1.96*sem over those per-cell rates (event-weighted pooling is the
  sensitivity, printed beside it).  Per phase the chosen Q is the smallest
  in-grid Q whose bound is <= 0.15; when none qualifies the Q with the smallest
  bound is taken and the phase is flagged.  The per-phase variant is KEPT only
  if the chosen Q's differ by >= 20 minutes AND the asset-pooled FP improves by
  >= 0.10 with a coverage loss <= 0.10; otherwise pooled Q stands.
STAGE B (cash): the selected composition, its D-ALONE control, its gate=retry
  control, the runner-up and the kept per-phase-Q variant, each priced on its
  own asset with the full cash
  table (usd/day against the 2000/1500/1500 rungs, per-trade, win, wall, MDD day-
  and trade-ordered, coverage) per asset and per phase; engine replay of each
  asset's selected line (partial-day label); a 2% adversarial stress (the legal
  opposite-side flips with the largest cert damage); asset-day block-permutation
  nulls, 200 draws, seed 20260827, max-statistic across every priced line; and
  each line's per-trade mean against the sweep-4 O4b oracle row whose d is
  nearest the line's median detection delay, read from .audit/mill-sweep4.json.
MUTANT sweep5_arbiter_peeks: the arrival recheck reads s_arb at the bar AFTER
  the candidate's own decision bar, a bar that has not closed at the decision.
"""

SCHEMA = "QRE2MILLSWEEP5"
SEED = S1.SEED
BAR_SECONDS = S1.BAR_SECONDS
BAR_NS = S1.BAR_NS
ASSETS = S1.ASSETS
DAY_RUNG_USD = S1.DAY_RUNG_USD
REMAIN_NS = S4.REMAIN_NS

# The frozen branch table: each asset's viable quiet window from the sweep-4
# O4b x O4c intersection.  HG is report-only, the USER deferred it.
Q_BY_ASSET: dict[str, tuple[int, ...]] = {
    "HG": (20, 45), "NKD": (10, 15, 20), "SI": (20, 30, 45)}
H_GRID = (0.20, 0.30)
K_GRID = (1, 3)
E_GRID = (3600, 5400)
COVERAGE_FLOOR = {"HG": 0.70, "NKD": 0.40, "SI": 0.35}
REPORT_ONLY = ("HG",)

FP_TARGET = 0.15
PHASE_Q_MIN_GAP_MINUTES = 20
PHASE_Q_FP_GAIN = 0.10
PHASE_Q_COVERAGE_LOSS = 0.10

NULL_DRAWS = S1.NULL_DRAWS
STRESS_RATE = S4.STRESS_RATE
DELAY_MINUTES = S4.DELAY_MINUTES

MUTANT_ARBITER_PEEKS = "sweep5_arbiter_peeks"
PARENT_TRIAL = "sweep4-081"
SELECTION_RULE = "joint_ci_low>coverage_floor>delay>Q>E"
FAMILY = "F2-ARBCOMP"

OUT_PATH = ROOT / ".audit/mill-sweep5.json"
SWEEP4_PATH = ROOT / ".audit/mill-sweep4.json"
LOG_PATH = S1.LOG_PATH
SPLIT_PATH = S1.SPLIT_PATH


class SweepRefusal(RuntimeError):
    pass


SPEC_SHA = S1._sha_text(SPEC)


def code_sha() -> str:
    return S1._sha_file(Path(__file__).resolve())


def _sweep_mutant() -> str:
    """The sweep-5 mutant name, validated against the mill's registry."""

    name = os.environ.get("QRE2_MILL_MUTANT", "")
    if name and name not in M.MUTANTS:
        raise SweepRefusal(f"unknown mill mutant: {name}")
    return name


# --------------------------------------------------------------------------
# The arbiter: one slow side call per completed bar.
# --------------------------------------------------------------------------

def arbiter_series(rec: S1.CellRec) -> np.ndarray:
    """``s_arb`` per bar: the mid against its own running session mean.

    The mean runs over bars 0..b, the same array the running extremes are read
    from, so the read at bar b consumes exactly the closes that have passed.
    """

    mid = np.asarray(rec.mid, np.float64)
    counts = np.arange(1, len(mid) + 1, dtype=np.float64)
    running = np.cumsum(mid) / counts
    return np.sign(mid - running).astype(np.int8)


def decision_bar(rec: S1.CellRec, stamps: np.ndarray) -> np.ndarray:
    """Bar index of the last completed bar at or before each decision stamp."""

    offset = np.asarray(stamps, np.int64) - int(rec.phase_open_ts_ns)
    return np.clip(offset // BAR_NS, 0, max(0, rec.n - 1)).astype(np.int64)


def arbiter_bar(rec: S1.CellRec, stamps: np.ndarray) -> np.ndarray:
    """Bar the arrival recheck reads.  The mutant peeks one bar into the future.

    ``sweep5_arbiter_peeks`` reads the bar AFTER the candidate's own decision
    bar - a bar whose close has not happened when the candidate decides.  This
    is the one branch in this module.
    """

    shift = 1 if _sweep_mutant() == MUTANT_ARBITER_PEEKS else 0
    return np.clip(decision_bar(rec, stamps) + shift, 0, max(0, rec.n - 1))


def arbiter_accuracy(plane: S4.Plane, arbs: Sequence[np.ndarray],
                     seconds: int) -> dict[str, dict[str, object]]:
    """How often ``s_arb`` at ``seconds`` into the session equals the cell's W.

    Sol's late-mean claim rests on this number (0.59-0.60 on HG); it is a
    diagnostic, never a gate.
    """

    out: dict[str, dict[str, object]] = {}
    for asset in ASSETS:
        agree = 0
        sharp = 0
        zero = 0
        for position, rec in enumerate(plane.records):
            if rec.asset != asset or not plane.winner[position]:
                continue
            bar = int(min(rec.n - 1, seconds // BAR_SECONDS))
            call = int(arbs[position][bar])
            sharp += 1
            zero += int(call == 0)
            agree += int(call == plane.winner[position])
        out[asset] = {"cells": sharp, "agree": agree, "zero_calls": zero,
                      "accuracy": (agree / sharp) if sharp else None}
    return out


# --------------------------------------------------------------------------
# The composition config.
# --------------------------------------------------------------------------

GATE_EPISODE = "episode"
GATE_RETRY = "retry"


@dataclass(frozen=True, slots=True)
class Comp:
    """One composition line: a sweep-4 detector, the arbiter gate, the E floor."""

    key: str
    q: int
    h: float
    k: int
    e: int
    arbiter: bool
    gate: str = GATE_EPISODE

    @property
    def detector(self) -> S4.Detector:
        # zone is DELETED by the sweep-4 O4c ruling; the sweep-4 detector still
        # takes the argument, so it is pinned to "none" here.
        return S4.Detector(self.key, int(self.q), float(self.h), int(self.k),
                           "none")

    @property
    def simplicity(self) -> tuple:
        return (self.q, self.e, self.h, self.k)

    @property
    def params(self) -> list:
        return [self.q, self.h, self.k, self.e, self.arbiter, self.gate]


def comp_key(q: int, h: float, k: int, e: int, arbiter: bool,
             gate: str = GATE_EPISODE) -> str:
    tail = f"E{e}" if arbiter else "DALONE"
    suffix = "" if gate == GATE_EPISODE else f"/{gate}"
    return f"Q{q}/H{h:.2f}/k{k}/{tail}{suffix}"


def comp_grid(asset: str) -> tuple[Comp, ...]:
    """The asset's composition configs, in the frozen branch table's Q set."""

    out: list[Comp] = []
    for q in Q_BY_ASSET[asset]:
        for h in H_GRID:
            for k in K_GRID:
                for e in E_GRID:
                    out.append(Comp(comp_key(q, h, k, e, True), int(q),
                                    float(h), int(k), int(e), True))
    return tuple(out)


def dalone_grid(asset: str) -> tuple[Comp, ...]:
    """The arbiter-free control at every (Q,H,k) the composition grid uses."""

    out: list[Comp] = []
    for q in Q_BY_ASSET[asset]:
        for h in H_GRID:
            for k in K_GRID:
                out.append(Comp(comp_key(q, h, k, 0, False), int(q), float(h),
                                int(k), 0, False))
    return tuple(out)


def dalone_of(comp: Comp) -> Comp:
    """Sweep 4's own line at the same (Q,H,k): no arbiter, no E floor.

    Without the arbiter the two gate readings coincide - the floor and the
    candidate set only tighten on later bars of one extreme - so this control is
    sweep 4's law however the composition beside it is read.
    """

    return Comp(comp_key(comp.q, comp.h, comp.k, 0, False, comp.gate), comp.q,
                comp.h, comp.k, 0, False, comp.gate)


def retry_of(comp: Comp) -> Comp:
    """The rejected reading: re-read s_arb on later bars of the same extreme."""

    return Comp(comp_key(comp.q, comp.h, comp.k, comp.e, comp.arbiter,
                         GATE_RETRY), comp.q, comp.h, comp.k, comp.e,
                comp.arbiter, GATE_RETRY)


# --------------------------------------------------------------------------
# The per-side state machine: detect, gate, arrive, recheck, re-arm.
# --------------------------------------------------------------------------

# Ordered by how far the machine got, so a two-sided abstention reports the
# furthest progress and ``code`` assignment can run lowest-priority first.
REASONS = ("no_context", "no_detection", "arbiter_detect", "no_candidate",
           "new_extreme", "past_deadline", "arbiter_arrival", "entered")
REASON_RANK = {name: rank for rank, name in enumerate(REASONS)}
CODE_ARBITER_DETECT = REASON_RANK["arbiter_detect"]
CODE_NO_CANDIDATE = REASON_RANK["no_candidate"]
CODE_NEW_EXTREME = REASON_RANK["new_extreme"]
CODE_PAST_DEADLINE = REASON_RANK["past_deadline"]
CODE_ARBITER_ARRIVAL = REASON_RANK["arbiter_arrival"]
CODE_ENTERED = REASON_RANK["entered"]


def _episode_starts(anchors: np.ndarray) -> np.ndarray:
    """Positions opening a new anchored extreme in a bar-ordered anchor run."""

    if not len(anchors):
        return np.zeros(0, np.int64)
    return np.flatnonzero(np.concatenate(([True], anchors[1:] != anchors[:-1])))


@dataclass(frozen=True, slots=True)
class Shot:
    """One side's outcome in one cell: the taken entry, or why there is none."""

    bar: int
    row: int
    reason: str
    cancel_arbiter: int
    cancel_extreme: int


def side_shot(plane: S4.Plane, arbs: Sequence[np.ndarray], position: int,
              side: int, comp: Comp) -> Shot:
    """``(detection bar, candidate row)`` of this side's first entry, or none.

    The sweep-4 detection set holds every bar on which a config's criteria stand;
    its anchors are non-decreasing, so its first bar per anchor is that extreme's
    DETECTION and the rest are the same declaration continuing.  Under
    ``gate=episode`` the machine evaluates one detection per extreme and a
    failure spends that extreme: re-arming waits for the next one.  Under
    ``gate=retry`` it walks every bar, which is the reading that would let a
    later s_arb flip resurrect a cancelled detection - measured, not used.
    """

    geometry = plane.geometry[position]
    if geometry is None:
        return Shot(-1, -1, "no_context", 0, 0)
    geo = geometry[side]
    rec = plane.records[position]
    call = arbs[position]
    deadline = plane.deadline_ts(position)
    bars = S4.detection_bars(geo, comp.detector, deadline, rec.lat)
    if not len(bars):
        return Shot(-1, -1, "no_detection", 0, 0)
    if comp.gate == GATE_EPISODE:
        bars = bars[_episode_starts(geo.anchor[bars])]
    elif comp.gate != GATE_RETRY:
        raise SweepRefusal(f"unknown arbiter gate reading: {comp.gate}")
    if not len(geo.cand_ts):
        return Shot(-1, -1, "no_candidate", 0, 0)
    ones = np.ones(len(bars), bool)
    agree_detect = (call[bars] == int(side)) if comp.arbiter else ones
    floor = np.maximum(rec.lat[bars],
                       int(rec.phase_open_ts_ns) + comp.e * NANOS_PER_SECOND)
    slot = np.searchsorted(geo.cand_ts, floor, side="left")
    has_candidate = slot < len(geo.cand_ts)
    stamps = geo.cand_ts[np.minimum(slot, len(geo.cand_ts) - 1)]
    before_stop = stamps < geo.stop_ns[bars]
    inside_deadline = stamps <= deadline
    agree_arrival = ((call[arbiter_bar(rec, stamps)] == int(side))
                     if comp.arbiter else ones)
    code = np.full(len(bars), CODE_ENTERED, np.int64)
    code[~agree_arrival] = CODE_ARBITER_ARRIVAL
    code[~inside_deadline] = CODE_PAST_DEADLINE
    code[~before_stop] = CODE_NEW_EXTREME
    code[~has_candidate] = CODE_NO_CANDIDATE
    code[~agree_detect] = CODE_ARBITER_DETECT
    taken = np.flatnonzero(code == CODE_ENTERED)
    first = int(taken[0]) if len(taken) else len(bars)
    starts = _episode_starts(geo.anchor[bars])
    episodes = code[starts[starts < first]]
    cancel_arbiter = int(np.count_nonzero(
        (episodes == CODE_ARBITER_DETECT) | (episodes == CODE_ARBITER_ARRIVAL)))
    cancel_extreme = int(np.count_nonzero(episodes == CODE_NEW_EXTREME))
    if len(taken):
        return Shot(int(bars[first]), int(geo.cand_row[int(slot[first])]),
                    "entered", cancel_arbiter, cancel_extreme)
    return Shot(-1, -1, REASONS[int(code[starts[-1]])], cancel_arbiter,
                cancel_extreme)


def comp_entry(plane: S4.Plane, arbs: Sequence[np.ndarray], position: int,
               comp: Comp) -> tuple[S4.Entry | None, str, int, int]:
    """The cell's one entry under ``comp``, the reason, and its cancel counts."""

    if plane.geometry[position] is None:
        return None, "no_context", 0, 0
    cell = plane.cands[position]
    shots: list[tuple[int, int, int, int]] = []
    reasons: list[str] = []
    cancel_arbiter = 0
    cancel_extreme = 0
    for side in (1, -1):
        shot = side_shot(plane, arbs, position, side, comp)
        cancel_arbiter += shot.cancel_arbiter
        cancel_extreme += shot.cancel_extreme
        reasons.append(shot.reason)
        if shot.row >= 0:
            shots.append((int(cell.ts[shot.row]), shot.bar, -side, shot.row))
    if not shots:
        reason = max(reasons, key=lambda name: REASON_RANK[name])
        return None, reason, cancel_arbiter, cancel_extreme
    shots.sort()
    _stamp, bar, negated, row = shots[0]
    entry = S4.make_entry(plane, position, row, -negated, bar)
    if entry is None:
        return None, "unavailable", cancel_arbiter, cancel_extreme
    return entry, "entered", cancel_arbiter, cancel_extreme


def _book() -> dict[str, int]:
    keys = list(REASONS) + ["unavailable", "cells", "cancel_arbiter",
                            "cancel_extreme"]
    return {name: 0 for name in keys}


def comp_line(plane: S4.Plane, arbs: Sequence[np.ndarray], comp: Comp,
              asset: str, per_phase_q: Mapping[int, int] | None = None
              ) -> tuple[list[S4.Entry], dict[str, int]]:
    """Price-free pass of one composition over one asset's cells."""

    entries: list[S4.Entry] = []
    book = _book()
    for position, rec in enumerate(plane.records):
        if rec.asset != asset:
            continue
        book["cells"] += 1
        use = comp
        if per_phase_q is not None:
            phase = plane.cands[position].phase_idx
            if phase not in per_phase_q:
                book["no_detection"] += 1
                continue
            q = int(per_phase_q[phase])
            use = Comp(comp_key(q, comp.h, comp.k, comp.e, comp.arbiter,
                                comp.gate), q, comp.h, comp.k, comp.e,
                       comp.arbiter, comp.gate)
        entry, reason, cancel_arbiter, cancel_extreme = comp_entry(
            plane, arbs, position, use)
        book[reason] += 1
        book["cancel_arbiter"] += cancel_arbiter
        book["cancel_extreme"] += cancel_extreme
        if entry is not None:
            entries.append(entry)
    return entries, book


# --------------------------------------------------------------------------
# Hit decomposition: terminal, side, joint, and the anchor's false positive.
# --------------------------------------------------------------------------

def side_hit(plane: S4.Plane, row: S4.Entry) -> bool:
    """The fade side equals ``sign(Delta*)`` at the entry bar (sweep-2 law).

    ``sign`` is 0 where the cell is not sharp at that bar, and an unsharp bar is
    not a hit: the entry took a side the label plane cannot certify.
    """

    rec = plane.records[row.cell]
    bar = int(decision_bar(rec, np.asarray([row.ts_ns], np.int64))[0])
    return int(plane.stars[row.cell].sign[bar]) == int(row.side)


def anchor_false_positive(plane: S4.Plane, row: S4.Entry) -> bool:
    """The detection this entry acted on was anchored on a NON-terminal extreme."""

    geometry = plane.geometry[row.cell]
    if geometry is None or row.detect_bar < 0:
        return False
    geo = geometry[row.side]
    return int(geo.anchor[row.detect_bar]) != int(geo.terminal_bar)


def cell_fp(plane: S4.Plane, position: int, comp: Comp
            ) -> tuple[int, int] | None:
    """``(declared, eligible)`` non-terminal extremes of one cell, both sides.

    This is sweep-4 O4c's false positive - a non-terminal extreme the detector
    calls terminal - measured on the detector that is actually running.  The
    eligibility guard drops extremes whose Q-minute quiet cannot finish before
    the 1800 s-remaining deadline, because those can never be declared and would
    otherwise pad the denominator with free true negatives.
    """

    geometry = plane.geometry[position]
    if geometry is None:
        return None
    rec = plane.records[position]
    deadline = plane.deadline_ts(position)
    guard = int(comp.q) * BAR_SECONDS * NANOS_PER_SECOND
    declared = 0
    eligible = 0
    for side in (1, -1):
        flag = np.asarray(plane.exts[position].new_low if side > 0
                          else plane.exts[position].new_high, bool)
        marks = np.flatnonzero(flag)
        if len(marks) <= 1:
            continue
        keep = marks[:-1][rec.lat[marks[:-1]] + guard <= deadline]
        if not len(keep):
            continue
        geo = geometry[side]
        bars = S4.detection_bars(geo, comp.detector, deadline, rec.lat)
        anchors = (np.unique(geo.anchor[bars]) if len(bars)
                   else np.zeros(0, np.int64))
        declared += int(np.count_nonzero(np.isin(keep, anchors)))
        eligible += int(len(keep))
    return (declared, eligible) if eligible else None


def fp_block(plane: S4.Plane, comp: Comp, asset: str, phase: int | None = None,
             q_by_phase: Mapping[int, int] | None = None) -> dict[str, object]:
    """Cell-weighted FP with its cell-block upper bound, plus the event rate."""

    rates: list[float] = []
    declared = 0
    eligible = 0
    for position, rec in enumerate(plane.records):
        if rec.asset != asset:
            continue
        cell_phase = plane.cands[position].phase_idx
        if phase is not None and cell_phase != phase:
            continue
        use = comp
        if q_by_phase is not None:
            if cell_phase not in q_by_phase:
                continue
            q = int(q_by_phase[cell_phase])
            use = Comp(comp_key(q, comp.h, comp.k, comp.e, comp.arbiter,
                                comp.gate), q, comp.h, comp.k, comp.e,
                       comp.arbiter, comp.gate)
        counts = cell_fp(plane, position, use)
        if counts is None:
            continue
        rates.append(counts[0] / counts[1])
        declared += counts[0]
        eligible += counts[1]
    if not rates:
        return {"cells": 0, "fp": None, "fp_upper": None, "fp_event": None,
                "declared": 0, "eligible": 0}
    values = np.asarray(rates, np.float64)
    mean = float(values.mean())
    # Cell-block bound: each cell is one block, so the spread across cells is
    # the standard error the bound has to cover.
    sem = (float(values.std(ddof=1) / np.sqrt(len(values))) if len(values) > 1
           else float("inf"))
    upper = 1.0 if sem == float("inf") else min(1.0, mean + 1.959963984540054 * sem)
    return {"cells": len(rates), "fp": mean, "fp_upper": upper,
            "fp_event": declared / eligible, "declared": declared,
            "eligible": eligible}


def _stats(entries: Sequence[S4.Entry], plane: S4.Plane, cells: int,
           book: Mapping[str, int]) -> dict[str, object]:
    rows = list(entries)
    terminal = [row.hit for row in rows]
    side = [side_hit(plane, row) for row in rows]
    joint = [bool(a and b) for a, b in zip(terminal, side)]
    hits = int(sum(joint))
    low, high = S1.wilson(hits, len(rows))
    entry_fp = int(sum(anchor_false_positive(plane, row) for row in rows))
    delays = [S4.detect_delay_seconds(plane, row) for row in rows]
    return {
        "cells": cells, "entered": len(rows),
        "coverage": len(rows) / max(1, cells),
        "terminal_hit_rate": (float(np.mean(terminal)) if rows else None),
        "side_hit_rate": (float(np.mean(side)) if rows else None),
        "joint_hits": hits,
        "joint_hit_rate": (hits / len(rows)) if rows else None,
        "ci95": [low, high],
        "entry_anchor_nonterminal_rate": (entry_fp / len(rows)) if rows else None,
        "detect_delay_median_s": S4._median(delays),
        "entry_delay_median_s": S4._median([row.delay_s for row in rows]),
        "entry_seconds_median": S4._median(
            [S4.entry_seconds(plane, row) for row in rows]),
        "long_fraction": (float(np.mean([row.side > 0 for row in rows]))
                          if rows else None),
        "cancel_arbiter": int(book.get("cancel_arbiter", 0)),
        "cancel_extreme": int(book.get("cancel_extreme", 0)),
        "no_context": int(book.get("no_context", 0)),
        "no_detection": int(book.get("no_detection", 0)),
        "arbiter_detect": int(book.get("arbiter_detect", 0)),
        "arbiter_arrival": int(book.get("arbiter_arrival", 0)),
        "no_candidate_rate": (int(book.get("no_candidate", 0))
                              + int(book.get("past_deadline", 0))
                              + int(book.get("unavailable", 0))) / max(1, cells),
    }


def _phase_stats(entries: Sequence[S4.Entry], plane: S4.Plane, asset: str
                 ) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for phase in plane.phases.get(asset, ()):
        rows = [row for row in entries if row.phase_idx == phase]
        out[str(phase)] = _stats(rows, plane,
                                 plane.phase_cells.get((asset, phase), 0), {})
    return out


# --------------------------------------------------------------------------
# STAGE A.
# --------------------------------------------------------------------------

def _order_key(row: Mapping[str, object], comp: Comp) -> tuple:
    delay = row["detect_delay_median_s"]
    return (-float(row["ci95"][0]),
            float("inf") if delay is None else float(delay),
            comp.q, comp.e, comp.h, comp.k, comp.key)


def select_for_asset(configs: Mapping[str, Mapping[str, object]],
                     grid: Mapping[str, Comp], asset: str) -> dict[str, object]:
    floor = COVERAGE_FLOOR[asset]
    passing = [key for key in configs
               if float(configs[key]["by_asset"]["coverage"]) >= floor]
    flags: list[str] = []
    pool = passing
    if not pool:
        flags.append("COVERAGE_FAIL")
        # Nothing reaches the floor: the brief's fallback is the max-coverage
        # config, ties broken by the same joint-hit order.
        best_coverage = max(float(configs[key]["by_asset"]["coverage"])
                            for key in configs)
        pool = [key for key in configs
                if float(configs[key]["by_asset"]["coverage"]) >= best_coverage]
    if asset in REPORT_ONLY:
        flags.append("REPORT_ONLY")
    ordered = sorted(pool, key=lambda key: _order_key(
        configs[key]["by_asset"], grid[key]))
    return {"best": ordered[0], "coverage_floor": floor,
            "runner_up": ordered[1] if len(ordered) > 1 else None,
            "flags": flags, "n_pass_coverage": len(passing),
            "ordered": ordered[:8]}


def stage_a(plane: S4.Plane, arbs: Sequence[np.ndarray]) -> dict[str, object]:
    report: dict[str, object] = {
        "coverage_floor": dict(COVERAGE_FLOOR), "report_only": list(REPORT_ONLY),
        "q_grid": {asset: list(value) for asset, value in Q_BY_ASSET.items()},
        "h_grid": list(H_GRID), "k_grid": list(K_GRID), "e_grid": list(E_GRID),
        "by_asset": {}}
    for asset in ASSETS:
        cells = plane.cells.get(asset, 0)
        controls: dict[str, dict[str, object]] = {}
        for comp in dalone_grid(asset):
            entries, book = comp_line(plane, arbs, comp, asset)
            controls[comp.key] = {
                "params": comp.params, "by_asset": _stats(entries, plane, cells, book),
                "by_phase": _phase_stats(entries, plane, asset)}
        configs: dict[str, dict[str, object]] = {}
        grid: dict[str, Comp] = {}
        for comp in comp_grid(asset):
            entries, book = comp_line(plane, arbs, comp, asset)
            grid[comp.key] = comp
            stats = _stats(entries, plane, cells, book)
            control = controls[dalone_of(comp).key]["by_asset"]
            configs[comp.key] = {
                "params": comp.params, "by_asset": stats,
                "by_phase": _phase_stats(entries, plane, asset),
                "dalone": dalone_of(comp).key,
                "delta_vs_dalone": {
                    "joint_hit": _delta(stats["joint_hit_rate"],
                                        control["joint_hit_rate"]),
                    "ci_low": _delta(stats["ci95"][0], control["ci95"][0]),
                    "terminal_hit": _delta(stats["terminal_hit_rate"],
                                           control["terminal_hit_rate"]),
                    "side_hit": _delta(stats["side_hit_rate"],
                                       control["side_hit_rate"]),
                    "coverage": _delta(stats["coverage"], control["coverage"]),
                    "detect_delay_s": _delta(stats["detect_delay_median_s"],
                                             control["detect_delay_median_s"])}}
        report["by_asset"][asset] = {
            "cells": cells, "configs": configs, "controls": controls,
            "selection": select_for_asset(configs, grid, asset)}
    return report


def _delta(value: object, base: object) -> float | None:
    if value is None or base is None:
        return None
    return float(value) - float(base)


# --------------------------------------------------------------------------
# The per-phase Q question, decided by the pooled false-positive rule.
# --------------------------------------------------------------------------

def phase_q(plane: S4.Plane, arbs: Sequence[np.ndarray], comp: Comp, asset: str
            ) -> dict[str, object]:
    """Smallest in-grid Q per phase whose cell-weighted FP bound clears 0.15."""

    by_q: dict[int, list[S4.Entry]] = {}
    for q in Q_BY_ASSET[asset]:
        probe = Comp(comp_key(q, comp.h, comp.k, comp.e, comp.arbiter,
                              comp.gate), int(q), comp.h, comp.k, comp.e,
                     comp.arbiter, comp.gate)
        by_q[int(q)] = comp_line(plane, arbs, probe, asset)[0]
    chosen: dict[int, int] = {}
    detail: dict[str, object] = {}
    for phase in plane.phases.get(asset, ()):
        cells = plane.phase_cells.get((asset, phase), 0)
        rows: dict[str, object] = {}
        qualified: list[int] = []
        for q in Q_BY_ASSET[asset]:
            probe = Comp(comp_key(q, comp.h, comp.k, comp.e, comp.arbiter,
                                  comp.gate), int(q), comp.h, comp.k, comp.e,
                         comp.arbiter, comp.gate)
            kept = [row for row in by_q[int(q)] if row.phase_idx == phase]
            stats = _stats(kept, plane, cells, {})
            block = fp_block(plane, probe, asset, phase)
            rows[str(q)] = {"coverage": stats["coverage"],
                            "entered": stats["entered"],
                            "joint_hit_rate": stats["joint_hit_rate"],
                            "ci_low": stats["ci95"][0], **block}
            if block["fp_upper"] is not None and block["fp_upper"] <= FP_TARGET:
                qualified.append(int(q))
        if qualified:
            chosen[phase] = min(qualified)
            met = True
        else:
            # Nothing clears the target: take the tightest bound and flag it.
            chosen[phase] = min(
                Q_BY_ASSET[asset],
                key=lambda q: (float(rows[str(q)]["fp_upper"] or 1.0), q))
            met = False
        detail[str(phase)] = {"q": chosen[phase], "fp_target_met": met,
                              "cells": cells, "candidates": rows}
    pooled_entries, pooled_book = comp_line(plane, arbs, comp, asset)
    phase_entries, phase_book = comp_line(plane, arbs, comp, asset, chosen)
    pooled = _stats(pooled_entries, plane, plane.cells.get(asset, 0), pooled_book)
    phased = _stats(phase_entries, plane, plane.cells.get(asset, 0), phase_book)
    pooled_fp = fp_block(plane, comp, asset)
    phased_fp = fp_block(plane, comp, asset, q_by_phase=chosen)
    pooled.update({f"pooled_{key}": value for key, value in pooled_fp.items()})
    phased.update({f"pooled_{key}": value for key, value in phased_fp.items()})
    values = sorted(chosen.values())
    gap = (values[-1] - values[0]) if values else 0
    fp_gain = _delta(pooled_fp["fp"], phased_fp["fp"])
    coverage_loss = _delta(pooled["coverage"], phased["coverage"])
    keep = bool(gap >= PHASE_Q_MIN_GAP_MINUTES
                and fp_gain is not None and fp_gain >= PHASE_Q_FP_GAIN
                and coverage_loss is not None
                and coverage_loss <= PHASE_Q_COVERAGE_LOSS)
    return {"chosen": {str(key): value for key, value in chosen.items()},
            "detail": detail, "q_gap_minutes": gap, "fp_gain": fp_gain,
            "coverage_loss": coverage_loss, "kept": keep,
            "pooled": pooled, "phased": phased, "pooled_fp": pooled_fp,
            "phased_fp": phased_fp,
            "gates": {"min_gap_minutes": PHASE_Q_MIN_GAP_MINUTES,
                      "fp_gain": PHASE_Q_FP_GAIN,
                      "coverage_loss": PHASE_Q_COVERAGE_LOSS,
                      "fp_target": FP_TARGET},
            "_chosen": chosen}


# --------------------------------------------------------------------------
# STAGE B: cash.
# --------------------------------------------------------------------------

def cash_block(entries: Sequence[S4.Entry], plane: S4.Plane, asset: str,
               book: Mapping[str, int]) -> dict[str, object]:
    line = S4.cash_by_asset(entries, plane)[asset]
    stats = _stats(entries, plane, plane.cells.get(asset, 0), book)
    line.update({key: stats[key] for key in (
        "side_hit_rate", "joint_hit_rate", "ci95", "entry_anchor_nonterminal_rate",
        "cancel_arbiter", "cancel_extreme", "no_candidate_rate")})
    phases = S4.cash_by_phase(entries, plane)[asset]
    detail = _phase_stats(entries, plane, asset)
    for key, row in phases.items():
        row.update({name: detail[key][name] for name in (
            "side_hit_rate", "joint_hit_rate")})
    return {"summary": line, "by_phase": phases, "skips": dict(book)}


def o4b_oracle(sweep4: Mapping[str, object], asset: str, seconds: float | None
               ) -> dict[str, object]:
    """The sweep-4 O4b row whose imposed delay is nearest ``seconds``."""

    matched = S4._nearest_delay(seconds)
    row = sweep4["stage_o"]["o4b"]["lines"][str(matched)]["by_asset"][asset]
    return {"matched_delay_minutes": matched,
            "oracle_usd_per_trade": row["usd_per_trade"],
            "oracle_usd_per_asset_day": row["usd_per_asset_day"],
            "oracle_coverage": row["coverage"]}


def stage_b(plane: S4.Plane, arbs: Sequence[np.ndarray],
            explore_days: Mapping[str, list[int]],
            a_report: Mapping[str, object], sweep4: Mapping[str, object]
            ) -> dict[str, object]:
    report: dict[str, object] = {
        "r0_median_gate_mid2": S1.r0_gate(plane.records), "lines": {},
        "replays": {}, "stress": {}, "phase_q": {}, "capture": {},
        "report_only": list(REPORT_ONLY)}
    priced: dict[str, list[S4.Entry]] = {}
    for asset in ASSETS:
        block = a_report["by_asset"][asset]
        pick = block["selection"]
        best = _comp_from_params(block["configs"][pick["best"]]["params"],
                                 pick["best"])
        plan: list[tuple[str, Comp, Mapping[int, int] | None]] = [
            ("BEST", best, None), ("DALONE", dalone_of(best), None),
            ("RETRY", retry_of(best), None)]
        if pick["runner_up"]:
            plan.append(("RUNNERUP", _comp_from_params(
                block["configs"][pick["runner_up"]]["params"],
                pick["runner_up"]), None))
        chosen = phase_q(plane, arbs, best, asset)
        report["phase_q"][asset] = {key: value for key, value in chosen.items()
                                    if not key.startswith("_")}
        if chosen["kept"]:
            plan.append(("BEST+PHASEQ", best, chosen["_chosen"]))
        for role, comp, per_phase in plan:
            entries, book = comp_line(plane, arbs, comp, asset, per_phase)
            name = f"{asset}/{role}"
            priced[name] = entries
            block_out = cash_block(entries, plane, asset, book)
            block_out["summary"].update({
                "role": role, "config": comp.key, "params": comp.params,
                "line_name": name, "report_only": asset in REPORT_ONLY,
                "per_phase_q": (None if per_phase is None
                                else {str(k): v for k, v in per_phase.items()})})
            report["lines"][name] = block_out
            summary = block_out["summary"]
            capture = o4b_oracle(sweep4, asset, summary["detect_delay_median_s"])
            capture.update({
                "line_usd_per_trade": summary["usd_per_trade"],
                "line_usd_per_asset_day": summary["usd_per_asset_day"],
                "capture_ratio": (
                    summary["usd_per_trade"] / capture["oracle_usd_per_trade"]
                    if capture["oracle_usd_per_trade"] else None)})
            report["capture"][name] = capture
            if role == "BEST":
                report["replays"][name] = S4.replay_line(
                    entries, plane.records, (asset,),
                    f"mill-sweep5:{code_sha()[:16]}:{name.replace('/', '-')}")
                report["stress"][name] = S4.stress_line(
                    entries, plane, asset, STRESS_RATE)
        # The arbiter's cash delta is the whole point of the D-ALONE control.
        best_line = report["lines"][f"{asset}/BEST"]["summary"]
        control = report["lines"][f"{asset}/DALONE"]["summary"]
        report["lines"][f"{asset}/BEST"]["arbiter_delta"] = {
            key: _delta(best_line[key], control[key]) for key in (
                "usd_per_asset_day", "usd_per_trade", "coverage", "win_rate",
                "wall_rate", "terminal_hit_rate", "side_hit_rate",
                "joint_hit_rate", "mdd_day_usd", "mdd_trade_usd")}
    report["nulls"] = S1.block_null(priced, explore_days, draws=NULL_DRAWS,
                                    seed=SEED)
    return report


def _comp_from_params(params: Sequence[object], key: str) -> Comp:
    q, h, k, e, arbiter, gate = params
    return Comp(key, int(q), float(h), int(k), int(e), bool(arbiter), str(gate))


# --------------------------------------------------------------------------
# Hypothesis log.
# --------------------------------------------------------------------------

def log_rows(report: Mapping[str, object]) -> list[dict[str, object]]:
    stamp = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    shared = {
        "registered_utc": stamp, "spec_sha": SPEC_SHA, "code_sha": code_sha(),
        "split_sha": S4.split_sha(), "outcome_law_sha": S4.outcome_law_sha(),
        "null_seed": SEED, "parent_trial": PARENT_TRIAL,
        "selection_rule": SELECTION_RULE, "verdict": "",
        "days": sum(report["asset_days"].values()),
    }
    miss = {"HG": "err_rate_hg", "NKD": "err_rate_nkd", "SI": "err_rate_si"}
    usd = {"HG": "hg_usd_day", "NKD": "nkd_usd_day", "SI": "si_usd_day"}
    mdd = {"HG": "mdd_hg", "NKD": "mdd_nkd", "SI": "mdd_si"}
    walls = {"HG": "walls_hg", "NKD": "walls_nkd", "SI": "walls_si"}
    rows: list[dict[str, object]] = []
    counter = 0
    for asset in ASSETS:
        block = report["stage_a"]["by_asset"][asset]
        pick = block["selection"]
        marks = {pick["best"]: "SEL", pick["runner_up"]: "RUN"}
        for tag, table in (("comp", block["configs"]), ("ctrl", block["controls"])):
            for key in sorted(table):
                entry = table[key]
                stats = entry["by_asset"]
                counter += 1
                mark = f";{marks[key]}" if key in marks else ""
                joint = stats["joint_hit_rate"]
                rows.append({
                    **shared, "id": f"sweep5-{counter:03d}", "family": FAMILY,
                    "rule": f"{asset}/{key}", "params": json.dumps(entry["params"]),
                    "coverage": stats["coverage"],
                    "delay_med_s": stats["detect_delay_median_s"],
                    miss[asset]: None if joint is None else 1.0 - float(joint),
                    "note": (f"stage-A {tag} joint-err{mark}")[:60]})
    if "stage_b" not in report:
        return rows
    nulls = report["stage_b"]["nulls"]["by_line"]
    replays = report["stage_b"]["replays"]
    for name in sorted(report["stage_b"]["lines"]):
        line = report["stage_b"]["lines"][name]["summary"]
        asset = name.split("/")[0]
        counter += 1
        skips: object = ""
        if replays.get(name, {}).get("status") == "OK":
            skips = replays[name]["occupancy_or_cap_skips"]
        joint = line["joint_hit_rate"]
        rows.append({
            **shared, "id": f"sweep5-{counter:03d}", "family": FAMILY,
            "rule": name, "params": json.dumps(line["params"]),
            "coverage": line["coverage"],
            "delay_med_s": line["detect_delay_median_s"],
            miss[asset]: None if joint is None else 1.0 - float(joint),
            walls[asset]: line["walls"], usd[asset]: line["usd_per_asset_day"],
            mdd[asset]: line["mdd_day_usd"], "replay_skips": skips,
            "null_margin": nulls.get(name, {}).get("p_max_adjusted"),
            "note": f"stage-B {line['role']} {line['config']}"[:60]})
    return rows


# --------------------------------------------------------------------------
# Report I/O and printing.
# --------------------------------------------------------------------------

def read_report() -> dict[str, object]:
    if OUT_PATH.is_file():
        return json.loads(OUT_PATH.read_text())
    return {"schema": SCHEMA, "tier": "exploratory",
            "claim": "EXPLORE-day sweep 5 arbiter composition baseline "
                     "(LATE-MEAN x TERMINAL); can kill, cannot promote"}


def write_report(report: Mapping[str, object]) -> None:
    payload = {key: value for key, value in report.items()
               if not key.startswith("_")}
    OUT_PATH.write_text(json.dumps(payload, sort_keys=True, indent=1,
                                   default=S1._json_default) + "\n")


def _num(value: object, width: int = 8, digits: int = 2) -> str:
    return S1._num(value, width, digits)


A_HEAD = (f"{'cov':>6s} {'ent':>5s} {'term':>6s} {'side':>6s} {'joint':>6s} "
          f"{'ci_lo':>6s} {'ci_hi':>6s} {'dly50':>7s} {'t_med':>7s} "
          f"{'cxArb':>6s} {'cxExt':>6s} {'nocand':>7s}")


def _a_row(row: Mapping[str, object]) -> str:
    return (f"{_num(row['coverage'], 6, 3)} {row['entered']:5d} "
            f"{_num(row['terminal_hit_rate'], 6, 3)} "
            f"{_num(row['side_hit_rate'], 6, 3)} "
            f"{_num(row['joint_hit_rate'], 6, 3)} "
            f"{_num(row['ci95'][0], 6, 3)} {_num(row['ci95'][1], 6, 3)} "
            f"{_num(row['detect_delay_median_s'], 7, 0)} "
            f"{_num(row['entry_seconds_median'], 7, 0)} "
            f"{row['cancel_arbiter']:6d} {row['cancel_extreme']:6d} "
            f"{_num(row['no_candidate_rate'], 7, 3)}")


def print_arbiter(block: Mapping[str, object]) -> None:
    print("\n== the arbiter alone: s_arb at the E floors vs the cell's W "
          "(diagnostic, never a gate)")
    print(f"  {'asset':6s} {'E_s':>6s} {'cells':>6s} {'agree':>6s} "
          f"{'zero':>6s} {'acc':>6s}")
    for seconds in E_GRID:
        for asset in ASSETS:
            row = block[str(seconds)][asset]
            print(f"  {asset:6s} {seconds:6d} {row['cells']:6d} "
                  f"{row['agree']:6d} {row['zero_calls']:6d} "
                  f"{_num(row['accuracy'], 6, 3)}")


def print_stage_a(report: Mapping[str, object], top: int = 5) -> None:
    print("\n== STAGE A (no cash): LATE-MEAN x TERMINAL, joint hit = terminal "
          "AND side")
    for asset in ASSETS:
        block = report["by_asset"][asset]
        pick = block["selection"]
        print(f"\n-- {asset}  cells={block['cells']}  "
              f"floor={pick['coverage_floor']:.2f}  "
              f"pass={pick['n_pass_coverage']}/{len(block['configs'])}  "
              f"flags={','.join(pick['flags']) or '-'}")
        print(f"  {'config':24s} {A_HEAD} {'dJoint':>7s} {'dCov':>6s}")
        for key in pick["ordered"][:top]:
            row = block["configs"][key]["by_asset"]
            delta = block["configs"][key]["delta_vs_dalone"]
            mark = "*" if key == pick["best"] else ("+" if key == pick["runner_up"]
                                                    else " ")
            print(f" {mark}{key:24s} {_a_row(row)} "
                  f"{_num(delta['joint_hit'], 7, 3)} "
                  f"{_num(delta['coverage'], 6, 3)}")
        print(f"  selected best={pick['best']} runner_up={pick['runner_up']}")
        best = pick["best"]
        control = block["configs"][best]["dalone"]
        print(f"  {'D-ALONE ' + control:24s} "
              f"{_a_row(block['controls'][control]['by_asset'])}")
        delta = block["configs"][best]["delta_vs_dalone"]
        print("  arbiter no-cash delta on the selected: " + "  ".join(
            f"{name}={_num(delta[name], 6, 3)}" for name in (
                "joint_hit", "ci_low", "terminal_hit", "side_hit", "coverage")))
        print("  per-phase for the selected: " + "  ".join(
            f"p{phase}: cov={_num(row['coverage'], 5, 3)} "
            f"joint={_num(row['joint_hit_rate'], 5, 3)} n={row['entered']}"
            for phase, row in sorted(block["configs"][best]["by_phase"].items())))


def print_phase_q(block: Mapping[str, object]) -> None:
    print("\n-- per-phase Q by the pooled FP rule (smallest Q whose cell-block "
          f"upper bound on the O4c false positive is <= {FP_TARGET:.2f}; fp_ev "
          "is the event-weighted sensitivity)")
    for asset in ASSETS:
        row = block[asset]
        print(f"  {asset:5s} chosen=" + ",".join(
            f"p{phase}:Q{value}" for phase, value in sorted(row["chosen"].items()))
            + f"  gap={row['q_gap_minutes']}min "
              f"fp_gain={_num(row['fp_gain'], 6, 3)} "
              f"cov_loss={_num(row['coverage_loss'], 6, 3)} "
              f"KEPT={row['kept']}")
        for phase, detail in sorted(row["detail"].items()):
            for q, cand in sorted(detail["candidates"].items(),
                                  key=lambda item: int(item[0])):
                mark = "*" if int(q) == int(detail["q"]) else " "
                print(f"   {mark}p{phase} Q{q:>3s} cells={detail['cells']:3d} "
                      f"n={cand['entered']:3d} cov={_num(cand['coverage'], 6, 3)} "
                      f"fp={_num(cand['fp'], 6, 3)} "
                      f"fp_up={_num(cand['fp_upper'], 6, 3)} "
                      f"fp_ev={_num(cand['fp_event'], 6, 3)} "
                      f"elig={cand['eligible']:4d} "
                      f"joint={_num(cand['joint_hit_rate'], 6, 3)}")


B_HEAD = (f"{'trd':>5s} {'cov':>6s} {'usd/day':>9s} {'usd/trd':>9s} "
          f"{'win':>6s} {'wall':>6s} {'mdd_day':>9s} {'mdd_trd':>9s} "
          f"{'term':>6s} {'side':>6s} {'joint':>6s} {'t_med':>7s}")


def _b_row(row: Mapping[str, object]) -> str:
    return (f"{row['trades']:5d} {_num(row['coverage'], 6, 3)} "
            f"{_num(row['usd_per_asset_day'], 9, 1)} "
            f"{_num(row['usd_per_trade'], 9, 1)} {_num(row['win_rate'], 6, 3)} "
            f"{_num(row['wall_rate'], 6, 3)} {_num(row['mdd_day_usd'], 9, 1)} "
            f"{_num(row['mdd_trade_usd'], 9, 1)} "
            f"{_num(row['terminal_hit_rate'], 6, 3)} "
            f"{_num(row['side_hit_rate'], 6, 3)} "
            f"{_num(row['joint_hit_rate'], 6, 3)} "
            f"{_num(row['entry_seconds_median'], 7, 0)}")


def print_stage_b(block: Mapping[str, object]) -> None:
    print("\n== STAGE B priced lines (exploratory; verdict column left empty)")
    print(f"{'line':18s} {'config':24s} {'ph':>3s} {B_HEAD} {'rung':>6s}")
    for name in sorted(block["lines"]):
        row = block["lines"][name]["summary"]
        print(f"{name:18s} {row['config']:24s} {'-':>3s} {_b_row(row)} "
              f"{row['rung_usd']:6.0f}")
        for phase, prow in sorted(block["lines"][name]["by_phase"].items()):
            print(f"{'':18s} {'':24s} {phase:>3s} {_b_row(prow)}")
    print("\n-- the arbiter's cash delta (BEST minus its D-ALONE control)")
    print(f"  {'asset':6s} {'d_usd/day':>10s} {'d_usd/trd':>10s} {'d_cov':>7s} "
          f"{'d_win':>7s} {'d_wall':>7s} {'d_term':>7s} {'d_side':>7s} "
          f"{'d_joint':>8s} {'d_mdd_day':>10s}")
    for asset in ASSETS:
        row = block["lines"][f"{asset}/BEST"]["arbiter_delta"]
        print(f"  {asset:6s} {_num(row['usd_per_asset_day'], 10, 1)} "
              f"{_num(row['usd_per_trade'], 10, 1)} "
              f"{_num(row['coverage'], 7, 3)} {_num(row['win_rate'], 7, 3)} "
              f"{_num(row['wall_rate'], 7, 3)} "
              f"{_num(row['terminal_hit_rate'], 7, 3)} "
              f"{_num(row['side_hit_rate'], 7, 3)} "
              f"{_num(row['joint_hit_rate'], 8, 3)} "
              f"{_num(row['mdd_day_usd'], 10, 1)}")
    print_phase_q(block["phase_q"])
    print("\n-- engine replay (partial-day: the split breaks portfolio days)")
    for name in sorted(block["replays"]):
        row = block["replays"][name]
        if row.get("status") != "OK":
            print(f"  {name:18s} {row.get('status')}")
            continue
        print(f"  {name:18s} days={row['asset_days']:4d} trades={row['trades']:4d} "
              f"usd/day={row['usd_per_asset_day']:9.1f} "
              f"usd/trd={row['usd_per_trade']:8.1f} "
              f"mdd={row['max_drawdown_usd']:9.1f} "
              f"breach={row['drawdown_breach_rate']:.3f} "
              f"skips={row['occupancy_or_cap_skips']:3d}")
    print(f"\n-- {STRESS_RATE:.0%} adversarial stress on each asset's BEST line")
    print(f"  {'line':18s} {'flips':>6s} {'avail':>6s} {'usd/day':>9s} "
          f"{'usd/trd':>9s} {'wall':>6s} {'mdd_day':>9s} {'mdd_trd':>9s}")
    for name in sorted(block["stress"]):
        row = block["stress"][name]
        print(f"  {name:18s} {row['flips_applied']:6d} {row['flips_available']:6d} "
              f"{_num(row['usd_per_asset_day'], 9, 1)} "
              f"{_num(row['usd_per_trade'], 9, 1)} {_num(row['wall_rate'], 6, 3)} "
              f"{_num(row['mdd_day_usd'], 9, 1)} {_num(row['mdd_trade_usd'], 9, 1)}")
    print("\n-- capture of the delay-matched sweep-4 O4b oracle")
    print(f"  {'line':18s} {'d_min':>5s} {'line/trd':>9s} {'oracle/trd':>11s} "
          f"{'capture':>8s} {'line/day':>9s} {'oracle/day':>11s} {'orc_cov':>8s}")
    for name in sorted(block["capture"]):
        row = block["capture"][name]
        print(f"  {name:18s} {row['matched_delay_minutes']:5d} "
              f"{_num(row['line_usd_per_trade'], 9, 1)} "
              f"{_num(row['oracle_usd_per_trade'], 11, 1)} "
              f"{_num(row['capture_ratio'], 8, 3)} "
              f"{_num(row['line_usd_per_asset_day'], 9, 1)} "
              f"{_num(row['oracle_usd_per_asset_day'], 11, 1)} "
              f"{_num(row['oracle_coverage'], 8, 3)}")
    nulls = block["nulls"]
    print(f"\n-- block-permutation null, {nulls['draws']} draws, seed "
          f"{nulls['seed']}, max-statistic across every priced line")
    print(f"  {'line':18s} {'obs_mdd':>9s} {'null_mean':>10s} {'p_own':>7s} "
          f"{'p_adj':>7s} {'pool_obs':>9s} {'p_pool':>7s} {'p_pool_adj':>10s}")
    for name in sorted(nulls["by_line"]):
        row = nulls["by_line"][name]
        print(f"  {name:18s} {row['observed_max_asset_mdd_usd']:9.1f} "
              f"{row['null_asset_mdd_mean_usd']:10.1f} {row['p_own']:7.3f} "
              f"{row['p_max_adjusted']:7.3f} {row['observed_pooled_mdd_usd']:9.1f} "
              f"{row['p_pooled_own']:7.3f} {row['p_pooled_max_adjusted']:10.3f}")
    if nulls["lines_held_out_empty"]:
        print(f"  held out (no entries): {', '.join(nulls['lines_held_out_empty'])}")


# --------------------------------------------------------------------------
# Selftest: synthetic arrays only, zero era bytes.
# --------------------------------------------------------------------------

SELFTEST_ASSET = S4.SELFTEST_ASSET
BARS = 120
FLAT = 9_200_000_000
LOW = 9_150_000_000
UP = 9_230_000_000
DIP = 9_160_000_000
HIGH = 9_300_000_000


def _agree_series() -> list[int]:
    """Bars 0-19 flat, bar 20 the only new running low, bars 21+ recovered.

    The mid then sits ABOVE its own running session mean, so the long fade of
    the bar-20 low is the side the arbiter is calling.  Hand values: at bar 30
    the mean is (20*9.200 + 9.150 + 10*9.230)/31 e9 = 9.20806e9 and the mid is
    9.230e9, so s_arb = +1.
    """

    return [FLAT] * 20 + [LOW] + [UP] * (BARS - 21)


def _disagree_series() -> list[int]:
    """The same low, a shallow recovery: the mid stays BELOW its running mean.

    At bar 30 the mean is (20*9.200 + 9.150 + 10*9.170)/31 e9 = 9.18871e9 over a
    9.170e9 mid, so s_arb = -1 and the same long-fade detection is not eligible.
    The retrace is 2.0e7/8.0e7 = 0.25 ATR, so the detector itself still fires.
    """

    return [FLAT] * 20 + [LOW] + [9_170_000_000] * (BARS - 21)


def _recheck_series() -> list[int]:
    """Agreement at the detection bar, disagreement when the candidate arrives.

    Bars 21-40 recover to 9.230e9 (s_arb = +1 at bar 30), bars 41-45 dip to
    9.160e9 (s_arb = -1 at bar 45, the arrival bar of the bar-45 candidate) and
    bars 46+ jump to 9.300e9 (s_arb = +1 again at bar 46).  Nothing prints a new
    running low after bar 20, so the only thing that can cancel the bar-30
    detection is the arrival recheck.  Bar 46 is also the bar the mutant peeks
    at from the bar-45 decision, and it calls +1: that is the flip.
    """

    return ([FLAT] * 20 + [LOW] + [UP] * 20 + [DIP] * 5
            + [HIGH] * (BARS - 46))


def _plane_for(series: Sequence[int], stamps: Sequence[int]
               ) -> tuple[S4.Plane, list[np.ndarray], S1.CellRec, S4.CandCell]:
    rec = S3._cell(list(series))
    cand = S4._cand_cell(rec, [(int(rec.lat[bar]), 1) for bar in stamps])
    plane = S4._selftest_plane([rec], [cand])
    return plane, [arbiter_series(rec)], rec, cand


def _comp(q: int, e: int, arbiter: bool = True,
          gate: str = GATE_EPISODE) -> Comp:
    return Comp(comp_key(q, 0.10, 1, e, arbiter, gate), int(q), 0.10, 1, int(e),
                bool(arbiter), gate)


def _selftest_arbiter() -> list[tuple[str, bool, str]]:
    rec = S3._cell(_agree_series())
    call = arbiter_series(rec)
    mean30 = (20 * FLAT + LOW + 10 * UP) / 31.0
    low = S3._cell(_disagree_series())
    low_call = arbiter_series(low)
    low_mean30 = (20 * FLAT + LOW + 10 * 9_170_000_000) / 31.0
    return [
        ("running_mean_is_the_hand_value_at_bar_30",
         abs(float(np.cumsum(rec.mid.astype(np.float64))[30] / 31.0) - mean30)
         < 1.0, f"mean={float(np.cumsum(rec.mid.astype(np.float64))[30] / 31.0)} "
                f"hand {mean30}"),
        ("s_arb_is_plus_one_when_the_mid_leads_its_running_mean",
         int(call[30]) == 1 and float(rec.mid[30]) > mean30,
         f"s_arb[30]={int(call[30])} mid={int(rec.mid[30])} mean={mean30}"),
        ("s_arb_is_minus_one_when_the_mid_trails_it",
         int(low_call[30]) == -1 and float(low.mid[30]) < low_mean30,
         f"s_arb[30]={int(low_call[30])} mid={int(low.mid[30])} "
         f"mean={low_mean30}"),
        ("s_arb_is_zero_on_the_flat_open_where_mid_equals_its_own_mean",
         int(call[0]) == 0 and int(call[19]) == 0,
         f"s_arb[0]={int(call[0])} s_arb[19]={int(call[19])}"),
        ("decision_bar_is_the_last_completed_bar_at_or_before_the_stamp",
         int(decision_bar(rec, np.asarray([int(rec.lat[45]) + 1], np.int64))[0])
         == 45 and int(decision_bar(rec, np.asarray([int(rec.lat[45])],
                                                    np.int64))[0]) == 45,
         "decision bar of a stamp inside bar 45 is not 45"),
    ]


def _selftest_gate() -> list[tuple[str, bool, str]]:
    """The arbiter flip: same detector, same candidate, opposite side calls."""

    agree, agree_arbs, agree_rec, agree_cand = _plane_for(_agree_series(), (45,))
    dis, dis_arbs, dis_rec, _cand = _plane_for(_disagree_series(), (45,))
    comp = _comp(10, 0)
    control = _comp(10, 0, arbiter=False)
    agree_shot = side_shot(agree, agree_arbs, 0, 1, comp)
    dis_shot = side_shot(dis, dis_arbs, 0, 1, comp)
    dis_control = side_shot(dis, dis_arbs, 0, 1, control)
    fired = S4.detection_bars(dis.geometry[0][1], comp.detector,
                              dis.deadline_ts(0), dis_rec.lat)
    entry, reason, cancels, _extremes = comp_entry(agree, agree_arbs, 0, comp)
    return [
        ("agreeing_side_enters_at_the_first_candidate_after_the_detection",
         agree_shot.row == 0 and agree_shot.bar == 30
         and int(agree_cand.ts[agree_shot.row]) == int(agree_rec.lat[45]),
         f"bar={agree_shot.bar} row={agree_shot.row} reason={agree_shot.reason}"),
        ("agreeing_side_produces_the_cell_entry",
         entry is not None and reason == "entered" and cancels == 0
         and entry.detect_bar == 30, f"{reason} {entry}"),
        ("disagreeing_side_never_enters",
         dis_shot.row == -1 and dis_shot.reason == "arbiter_detect",
         f"bar={dis_shot.bar} row={dis_shot.row} reason={dis_shot.reason}"),
        ("the_detector_alone_would_have_entered_that_disagreeing_cell",
         dis_control.row == 0 and dis_control.bar == 30 and len(fired)
         and int(fired[0]) == 30,
         f"D-ALONE bar={dis_control.bar} row={dis_control.row}; "
         f"detections {list(fired[:3])}"),
        ("the_disagreement_is_counted_as_an_arbiter_cancel",
         dis_shot.cancel_arbiter == 1 and dis_shot.cancel_extreme == 0,
         f"arb={dis_shot.cancel_arbiter} ext={dis_shot.cancel_extreme}"),
    ]


def _selftest_recheck() -> list[tuple[str, bool, str]]:
    """Arrival recheck: the detection is cancelled and the extreme is spent.

    One extreme prints, so nothing but the recheck can cancel the bar-30
    detection, and once it does the cell abstains.  The rejected ``gate=retry``
    reading is measured beside it: it resurrects the detection at bar 46, the
    first bar where the mean call flips back, which is vs_mean acting as the
    entry clock.
    """

    plane, arbs, rec, cand = _plane_for(_recheck_series(), (45, 70))
    call = arbs[0]
    shot = side_shot(plane, arbs, 0, 1, _comp(10, 0))
    retry = side_shot(plane, arbs, 0, 1, _comp(10, 0, gate=GATE_RETRY))
    base = side_shot(plane, arbs, 0, 1, _comp(10, 0, arbiter=False))
    return [
        ("the_detection_bar_agrees_and_the_arrival_bar_does_not",
         int(call[30]) == 1 and int(call[45]) == -1 and int(call[46]) == 1,
         f"s_arb 30/45/46 = {int(call[30])}/{int(call[45])}/{int(call[46])}"),
        ("no_new_extreme_can_be_the_cause",
         S4.terminal_extreme_bar(plane.exts[0], 1) == 20
         and int(np.count_nonzero(plane.exts[0].new_low)) == 1,
         f"new lows at {list(np.flatnonzero(plane.exts[0].new_low))}"),
        ("the_arrival_recheck_rejects_the_bar_45_candidate",
         shot.row == -1 and shot.reason == "arbiter_arrival",
         f"row={shot.row} reason={shot.reason}; the bar-45 candidate at "
         f"{int(cand.ts[0])} must not be taken"),
        ("the_cancelled_extreme_is_spent_not_retried",
         shot.cancel_arbiter == 1 and shot.cancel_extreme == 0,
         f"arb={shot.cancel_arbiter} ext={shot.cancel_extreme}"),
        ("the_rejected_retry_reading_would_enter_when_the_mean_call_flips",
         retry.bar == 46 and retry.row == 1
         and int(cand.ts[retry.row]) == int(rec.lat[70]),
         f"retry bar={retry.bar} stamp="
         f"{None if retry.row < 0 else int(cand.ts[retry.row])}"),
        ("the_detector_alone_would_have_taken_the_rejected_candidate",
         base.row == 0 and base.bar == 30
         and int(cand.ts[base.row]) == int(rec.lat[45]),
         f"D-ALONE bar={base.bar} stamp="
         f"{None if base.row < 0 else int(cand.ts[base.row])}"),
    ]


def _rearm_series() -> list[int]:
    """Two new running lows: bar 20 the false one, bar 46 the terminal one.

    Bars 21-45 hold 9.170e9, a 0.25 ATR retrace off the bar-20 low that the
    detector accepts while the mid stays under its own running mean (mean at bar
    30 = (20*9.200 + 9.150 + 10*9.170)/31 e9 = 9.18871e9), so s_arb = -1 blocks
    that detection.  Bar 46 prints 9.140e9 and bars 47+ recover to 9.300e9, so
    the bar-56 detection on the terminal low is read with s_arb = +1.
    """

    return ([FLAT] * 20 + [LOW] + [9_170_000_000] * 25 + [9_140_000_000]
            + [HIGH] * (BARS - 47))


def _selftest_rearm() -> list[tuple[str, bool, str]]:
    """Re-arming means the NEXT extreme, and it lands on the terminal one."""

    plane, arbs, rec, cand = _plane_for(_rearm_series(), (60,))
    call = arbs[0]
    shot = side_shot(plane, arbs, 0, 1, _comp(10, 0))
    base = side_shot(plane, arbs, 0, 1, _comp(10, 0, arbiter=False))
    entry, reason, cancel_arbiter, cancel_extreme = comp_entry(
        plane, arbs, 0, _comp(10, 0))
    return [
        ("the_two_hand_extremes_are_there",
         list(np.flatnonzero(plane.exts[0].new_low)) == [20, 46]
         and S4.terminal_extreme_bar(plane.exts[0], 1) == 46,
         f"new lows {list(np.flatnonzero(plane.exts[0].new_low))}"),
        ("the_arbiter_blocks_the_detection_on_the_false_extreme",
         int(call[30]) == -1 and int(call[56]) == 1,
         f"s_arb 30/56 = {int(call[30])}/{int(call[56])}"),
        ("the_entry_comes_from_the_detection_on_the_terminal_extreme",
         shot.bar == 56 and shot.row == 0
         and int(cand.ts[shot.row]) == int(rec.lat[60]),
         f"bar={shot.bar} row={shot.row} reason={shot.reason}"),
        ("that_costs_exactly_one_arbiter_cancel",
         shot.cancel_arbiter == 1 and shot.cancel_extreme == 0,
         f"arb={shot.cancel_arbiter} ext={shot.cancel_extreme}"),
        ("the_detector_alone_reaches_it_by_a_new_extreme_cancel_instead",
         base.bar == 56 and base.row == 0 and base.cancel_extreme == 1
         and base.cancel_arbiter == 0,
         f"D-ALONE bar={base.bar} arb={base.cancel_arbiter} "
         f"ext={base.cancel_extreme}"),
        ("the_entry_is_a_terminal_anchored_hit",
         entry is not None and reason == "entered" and entry.hit
         and not anchor_false_positive(plane, entry)
         and cancel_arbiter == 1 and cancel_extreme == 0, f"{reason} {entry}"),
    ]


def _selftest_floor() -> list[tuple[str, bool, str]]:
    """The E floor moves the entry forward and can abstain the cell entirely."""

    plane, arbs, rec, cand = _plane_for(_agree_series(), (45, 70))
    early, early_arbs, early_rec, _cand = _plane_for(_agree_series(), (45,))
    open_ns = int(rec.phase_open_ts_ns)
    shots = {seconds: side_shot(plane, arbs, 0, 1, _comp(10, seconds))
             for seconds in (0, 3600, 5400)}
    blocked = side_shot(early, early_arbs, 0, 1, _comp(10, 3600))
    return [
        ("without_a_floor_the_first_candidate_after_the_detection_is_taken",
         shots[0].row == 0 and int(cand.ts[shots[0].row]) == int(rec.lat[45]),
         f"row={shots[0].row} expected the {int(rec.lat[45])} candidate"),
        ("the_bar_45_candidate_sits_before_the_3600_s_floor",
         int(rec.lat[45]) - open_ns == 2700 * NANOS_PER_SECOND
         and int(rec.lat[70]) - open_ns == 4200 * NANOS_PER_SECOND,
         f"elapsed 45={int(rec.lat[45]) - open_ns} 70="
         f"{int(rec.lat[70]) - open_ns}"),
        ("E3600_skips_it_and_takes_the_first_candidate_past_the_floor",
         shots[3600].row == 1 and int(cand.ts[shots[3600].row]) == int(rec.lat[70]),
         f"row={shots[3600].row} expected the {int(rec.lat[70])} candidate"),
        ("E5400_leaves_nothing_inside_the_1800_s_deadline",
         shots[5400].row == -1 and shots[5400].reason in
         ("no_candidate", "past_deadline"),
         f"row={shots[5400].row} reason={shots[5400].reason}"),
        ("a_cell_whose_only_candidate_is_early_abstains_under_the_floor",
         blocked.row == -1 and blocked.reason == "no_candidate",
         f"row={blocked.row} reason={blocked.reason}"),
    ]


def _selftest_decomposition() -> list[tuple[str, bool, str]]:
    """side_hit reads ``sign(Delta*)`` at the entry bar, joint needs both."""

    plane, arbs, rec, _cand = _plane_for(_agree_series(), (45,))
    entry, _reason, _arb, _ext = comp_entry(plane, arbs, 0, _comp(10, 0))
    star = plane.stars[0]
    bar = int(decision_bar(rec, np.asarray([entry.ts_ns], np.int64))[0])
    stats = _stats([entry], plane, 1, _book())
    return [
        ("side_hit_reads_the_star_sign_at_the_entry_bar", bar == 45
         and side_hit(plane, entry) == (int(star.sign[45]) == entry.side),
         f"bar={bar} sign={int(star.sign[45])} side={entry.side}"),
        ("an_unsharp_bar_is_not_a_side_hit",
         (int(star.sign[bar]) != 0) or not side_hit(plane, entry),
         f"sign={int(star.sign[bar])} side_hit={side_hit(plane, entry)}"),
        ("joint_hit_is_the_conjunction",
         stats["joint_hit_rate"] == float(
             bool(entry.hit) and bool(side_hit(plane, entry))),
         f"joint={stats['joint_hit_rate']} term={entry.hit} "
         f"side={side_hit(plane, entry)}"),
        ("the_anchor_of_this_entry_is_the_terminal_extreme",
         not anchor_false_positive(plane, entry)
         and stats["entry_anchor_nonterminal_rate"] == 0.0,
         f"fp={stats['entry_anchor_nonterminal_rate']}"),
        ("coverage_counts_cells_not_candidates", stats["coverage"] == 1.0
         and stats["entered"] == 1, f"{stats['coverage']}"),
    ]


def _selftest_fp() -> list[tuple[str, bool, str]]:
    """The O4c false positive, hand-counted on the two-extreme series.

    The bar-20 low is the one non-terminal extreme (the bar-47 high is its
    direction's only extreme, so it is terminal and contributes nothing).  Its
    quiet runs 26 bars, so Q=10 declares it - a false positive - and Q=30 never
    does.  The guard drops it once Q pushes the declaration past the deadline:
    close(20) = 1200 s, deadline = 5400 s, so Q=75 leaves no eligible extreme.
    """

    plane, arbs, rec, _cand = _plane_for(_rearm_series(), (60,))
    marks = list(np.flatnonzero(plane.exts[0].new_low))
    highs = list(np.flatnonzero(plane.exts[0].new_high))
    counts = {q: cell_fp(plane, 0, _comp(q, 0, arbiter=False))
              for q in (10, 30, 75)}
    block = fp_block(plane, _comp(10, 0, arbiter=False), SELFTEST_ASSET)
    return [
        ("the_only_non_terminal_extreme_is_the_bar_20_low",
         marks == [20, 46] and highs == [47],
         f"lows {marks} highs {highs}"),
        ("Q10_declares_that_false_extreme_terminal", counts[10] == (1, 1),
         f"{counts[10]} expected (1, 1)"),
        ("Q30_outlasts_its_26_bar_quiet_and_declares_nothing",
         counts[30] == (0, 1), f"{counts[30]} expected (0, 1)"),
        ("the_eligibility_guard_drops_an_extreme_that_cannot_be_declared",
         counts[75] is None
         and int(rec.lat[20]) + 75 * BAR_NS > plane.deadline_ts(0),
         f"{counts[75]} expected None"),
        ("the_cell_block_bound_is_built_from_per_cell_rates",
         block["cells"] == 1 and block["fp"] == 1.0
         and block["fp_event"] == 1.0 and block["fp_upper"] == 1.0,
         f"{block}"),
    ]


def _selftest_grid() -> list[tuple[str, bool, str]]:
    sizes = {asset: len(comp_grid(asset)) for asset in ASSETS}
    controls = {asset: len(dalone_grid(asset)) for asset in ASSETS}
    return [
        ("the_grid_is_the_frozen_branch_table",
         sizes == {"HG": 16, "NKD": 24, "SI": 24}
         and all(value <= 24 for value in sizes.values()),
         f"{sizes} from Q {Q_BY_ASSET}"),
        ("every_graded_config_reads_the_gate_one_detection_per_extreme",
         all(comp.gate == GATE_EPISODE for asset in ASSETS
             for comp in comp_grid(asset) + dalone_grid(asset))
         and retry_of(comp_grid("SI")[0]).gate == GATE_RETRY,
         "a graded config carried the retry reading"),
        ("every_config_has_a_dalone_control_at_the_same_QHk",
         all(dalone_of(comp).key in {c.key for c in dalone_grid(asset)}
             for asset in ASSETS for comp in comp_grid(asset))
         and controls == {"HG": 8, "NKD": 12, "SI": 12}, f"{controls}"),
        ("the_zone_is_deleted_from_every_detector",
         all(comp.detector.zone == "none" for asset in ASSETS
             for comp in comp_grid(asset)), "a config carried a zone"),
        ("coverage_floors_are_the_raised_ones",
         COVERAGE_FLOOR == {"HG": 0.70, "NKD": 0.40, "SI": 0.35},
         f"{COVERAGE_FLOOR}"),
    ]


def selftest() -> int:
    mutant = _sweep_mutant()
    checks: list[tuple[str, bool, str]] = []
    checks.extend(_selftest_grid())
    checks.extend(_selftest_arbiter())
    checks.extend(_selftest_gate())
    checks.extend(_selftest_recheck())
    checks.extend(_selftest_rearm())
    checks.extend(_selftest_floor())
    checks.extend(_selftest_decomposition())
    checks.extend(_selftest_fp())
    dead = [(name, why) for name, ok, why in checks if not ok]
    if dead:
        for name, why in dead:
            print(f"DEAD: {name}: {why}")
        print(f"sweep5_selftest_dead mutant={mutant or 'none'} "
              f"cases={len(dead)}/{len(checks)}")
        return 1
    if mutant:
        print(f"DEAD: mutant {mutant} left every sweep-5 case green")
        return 1
    print(f"sweep5_selftest_ok cases={len(checks)}")
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def load_plane(assets: Sequence[str], root: Path
               ) -> tuple[S4.Plane, list[np.ndarray], dict[str, int]]:
    records, days = S4._load(assets, root)
    # The candidate plane is untouched by this sweep's mutant, so it is always
    # read at the clean cache tag.
    cands = S4.cands_for(records, assets, root, "")
    plane = S4.build_plane(records, cands, CTX.ContextStore(), days)
    return plane, [arbiter_series(rec) for rec in plane.records], days


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", nargs="?", default="all",
                        choices=("stage-a", "stage-b", "log", "all"))
    parser.add_argument("--assets", default="HG,NKD,SI")
    parser.add_argument("--root", default=str(M.MILL_ROOT))
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    mutant = _sweep_mutant()
    assets = tuple(name.strip().upper() for name in args.assets.split(",")
                   if name.strip())
    started = time.monotonic()
    plane, arbs, days = load_plane(assets, Path(args.root))
    explore_days = S1._explore_days(assets)
    sweep4 = json.loads(SWEEP4_PATH.read_text())
    report = read_report()
    report.setdefault("spec_sha", SPEC_SHA)
    report["code_sha"] = code_sha()
    report["split_sha"] = S4.split_sha()
    report["outcome_law_sha"] = S4.outcome_law_sha()
    report["parent_trial"] = PARENT_TRIAL
    report["mutant"] = mutant
    report["sweep4_code_sha"] = sweep4["code_sha"]
    report["asset_days"] = dict(days)
    report["cells"] = dict(plane.cells)
    report["phase_cells"] = {f"{asset}/{phase}": value for (asset, phase), value
                             in sorted(plane.phase_cells.items())}
    report["diagnostics"] = dict(plane.diagnostics)
    report["arbiter"] = {str(seconds): arbiter_accuracy(plane, arbs, seconds)
                         for seconds in E_GRID}
    print_arbiter(report["arbiter"])

    if args.stage in ("stage-a", "stage-b", "log", "all"):
        if "stage_a" not in report or args.stage in ("stage-a", "all"):
            report["stage_a"] = stage_a(plane, arbs)
        print_stage_a(report["stage_a"], args.top)
    if args.stage in ("stage-b", "all"):
        report["stage_b"] = stage_b(plane, arbs, explore_days,
                                    report["stage_a"], sweep4)
        print_stage_b(report["stage_b"])
    if args.stage in ("log", "all"):
        rows = log_rows(report)
        written = S1.append_log(rows)
        report["log"] = {"rows_appended": written,
                         "registered_utc": rows[0]["registered_utc"],
                         "first_id": rows[0]["id"], "last_id": rows[-1]["id"]}
        print(f"\nlog: appended {written} rows to {LOG_PATH}")

    report["wall_seconds"] = round(time.monotonic() - started, 2)
    write_report(report)
    print(f"\nwrote {OUT_PATH} wall={report['wall_seconds']}s "
          f"cells={len(plane.records)} spec_sha={SPEC_SHA[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
