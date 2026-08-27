#!/usr/bin/env python3
"""Sweep 6: the decisive flow test, run exactly as the charter froze it.

Exploratory tier.  EXPLORE-day bytes only, no cash anywhere, can kill, cannot
promote.  Sweep 5 measured the ``vs_mean`` arbiter composition and sweep 4 before
it isolated the SIDE as the one missing ingredient.  This sweep asks the single
pre-registered question: at a quieted running extreme, does a paired
zone-episode rejection score pick the right extreme better than the detector
alone and better than the arbiter?

Nothing here is searched.  The detector, the score, the percentile strata, the
margin rule, the arms, the null and the decision bounds were all frozen in
``.audit/briefs/mill-side-resolution.md`` (section "The decisive flow test,
frozen") before any label was read.  This module implements that text and
reports the result.

The three arms run on IDENTICAL opportunities:

  ARM-D    sweep 5's D-ALONE control: the detector's first eligible opportunity.
  ARM-M    sweep 5's selected composition at its own E: the ``vs_mean`` arbiter.
  ARM-R5   the first opportunity whose paired margin clears the frozen rule.

Sources: the sweep-1 prep cache, the sweep-4 candidate plane, the zone-episode
cache (``flow_zones.load_zones``) and the context store.  No HOLD day, no
teacher or late label, no cash, no 2021/2025 byte.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import datetime as dt
import json
import math
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
import flow_zones as FZ
import mill as M
import sweep1 as S1
import sweep3 as S3
import sweep4 as S4
import sweep5 as S5

# --------------------------------------------------------------------------
# The immutable law this sweep registers before it reads anything.
# --------------------------------------------------------------------------

SPEC = """QRE2MILLSWEEP6
tier=exploratory; explore-only; no cash; can kill, cannot promote.
parent=sweep5-108.  Charter: mill-side-resolution.md "The decisive flow test,
frozen" (Fable ruling on Sol + playbook, 2026-08-27).
OPPORTUNITIES.  Per asset the frozen sweep-5 SELECTED config's DETECTOR, no
  arbiter and no E floor beyond the detector's own laws: HG Q45/H0.30/k1,
  NKD Q10/H0.20/k1, SI Q30/H0.20/k3, zone deleted (sweep-4 O4c).  One
  opportunity per ARMED EXTREME - sweep 5's graded law, the first bar of each
  anchor run inside detection_bars.
SCORE.  At the detection bar T, for BOTH the quieted extreme (the detector's own
  side) and the opposite running extreme, from the zone-episode cache truncated
  at T.  P is the empirical mid-rank percentile in the frozen (asset, phase, Q)
  stratum, computed outcome-blind over the full EXPLORE census of opportunities
  pooled across both extremes so the two sides of a pair share one scale.
    A   = mean(P(episode cumulative attack),
               1 - P(extension per unit attack))
    D   = mean(P(|episode attacking delta|),
               1 - P(extension per unit |attacking delta|))
    F   = mean(P(reversal-aligned delta within 2 bars after the last zone touch),
               P(one-sidedness of the touch print: |delta|/vol at the touch bar))
    S   = P(fade-direction minus continuation-direction signed per-minute delta
            persistence over the trailing 10-30 min window)
    Mem = mean(P(touches so far at this zone), P(held-touches so far),
               P(at-prior-day-level flag: the extreme within 0.15*ATR of the
               prior locked day's session low/high from ContextStore))
  R5 = (A+D+F+S+Mem)/5.  R4mem = (A+D+F+Mem)/4 is computed and stored SEALED
  under "fallback_sealed"; it is not printed and not read.  Reload and iceberg
  proxies never enter either score.  A missing component - no episode yet, no
  touch yet, no context, a trailing window under 10 bars - leaves that extreme
  UNSCORED.
ARMS on identical opportunities.  ARM-D = sweep-5 D-ALONE (detector alone, first
  eligible opportunity enters).  ARM-M = sweep-5's vs_mean arbiter law at the
  asset's selected E.  ARM-R5 = the first opportunity with
  margin = R5(quieted) - R5(opposite) > 0 AND >= the frozen stratum 60th
  percentile of margins; abstain when either side is unscored.  Entry is the
  first fade-side CLEAR candidate after selection (sweep-5 law), one entry per
  cell, earliest surviving detection-entry across the two directions wins.
METRICS, no cash anywhere.  Per asset per arm: eligible cells, entries,
  coverage, missing-pair count, joint hit J (terminal AND fade side ==
  sign(Delta*) at entry, the sweep-2 star_cell law) with Wilson bounds, yield
  Y = joint hits / eligible cells, deltas R5-vs-D and R5-vs-M with paired
  asset-day block 95% CIs, median and p90 delay from the SELECTED EXTREME to the
  decision, per-phase cuts, per-component terminal-vs-non-terminal rank
  separation, and the diagnostic columns: reload, twoside polarity,
  CVD-dies-at-level, shrinkage-pacing, balance-vs-trend regime cut.
NULL.  Within-cell high-low swap: the pair's roles exchange, so the cell's
  margins negate.  10,000 draws, seed 20260827, max-statistic across
  NKD/SI x {R5-D, R5-M}.
BOUNDS (pre-registered, per the charter).  KEEP needs +0.05 on both assets
  against both controls, both pooled paired 95% lower bounds above zero,
  p_adj <= 0.05, coverage >= 0.40 (NKD) / 0.35 (SI), p90 delay <= 20 min (NKD) /
  45 min (SI), and yield above both controls.  SECOND-ITERATION needs every
  delta >= +0.03 with at least one missing +0.05, both p_adj <= 0.10, both
  coverage and delay budgets passing, and A/D/F each carrying the correct rank
  direction on both assets.  KILL on any delta below +0.03, a coverage or delay
  failure, p_adj > 0.10, or the two assets disagreeing in direction.  HG is
  reported and never decides.
MUTANT sweep6_score_peeks_outcome: the percentile census is restricted to
  outcome-conditioned rows (the terminal extremes), so P is calibrated on a
  distribution that already knows the label.
"""

SCHEMA = "QRE2MILLSWEEP6"
SEED = S1.SEED
BAR_SECONDS = S1.BAR_SECONDS
ASSETS = S1.ASSETS
DECIDING = ("NKD", "SI")
REPORT_ONLY = ("HG",)

# The frozen sweep-5 selection, per .audit/mill-sweep5.json stage A.
FROZEN: dict[str, tuple[int, float, int, int]] = {
    "HG": (45, 0.30, 1, 3600),
    "NKD": (10, 0.20, 1, 5400),
    "SI": (30, 0.20, 3, 3600),
}

MARGIN_PERCENTILE = 60.0
SCHEDULE_WINDOW_BARS = 30
SCHEDULE_MIN_BARS = 10
FLUSH_BARS = 2
PRIOR_LEVEL_ATR = 0.15

COVERAGE_FLOOR = {"NKD": 0.40, "SI": 0.35}
DELAY_P90_CAP_S = {"NKD": 20 * 60.0, "SI": 45 * 60.0}
KEEP_DELTA = 0.05
SECOND_DELTA = 0.03
KEEP_P = 0.05
SECOND_P = 0.10

NULL_DRAWS = 10_000
BOOTSTRAP_DRAWS = 2_000

MUTANT_PEEKS = "sweep6_score_peeks_outcome"
PARENT_TRIAL = "sweep5-108"
SELECTION_RULE = "frozen: no selection, pre-registered R5 margin rule"
FAMILY = "F2-ZONESCORE"

OUT_PATH = ROOT / ".audit/mill-sweep6.json"
LOG_PATH = S1.LOG_PATH

ARMS = ("D", "M", "R5")

# The ten raw quantities the score percentiles.  Order is frozen: the census,
# the score assembly and the printed tables all index it.
RAW_NAMES = (
    "a_attack", "a_ext_per_attack", "d_absdelta", "d_ext_per_absdelta",
    "f_reversal", "f_onesided", "s_persist", "m_touches", "m_held", "m_prior",
)
# Diagnostics.  Named by the structure-half ruling; never in any score.
DIAG_NAMES = (
    "reload", "twoside_touch", "cvd_slope", "attack_slope", "touch_interval_slope",
)
COMPONENTS = ("A", "D", "F", "S", "Mem")
RANK_DIRECTION_REQUIRED = ("A", "D", "F")


class SweepRefusal(RuntimeError):
    pass


SPEC_SHA = S1._sha_text(SPEC)


def code_sha() -> str:
    return S1._sha_file(Path(__file__).resolve())


def _sweep_mutant() -> str:
    """The sweep-6 mutant name, validated against the mill's registry."""

    name = os.environ.get("QRE2_MILL_MUTANT", "")
    if name and name not in M.MUTANTS:
        raise SweepRefusal(f"unknown mill mutant: {name}")
    return name


def detector_for(asset: str) -> S4.Detector:
    q, h, k, _e = FROZEN[asset]
    return S4.Detector(f"Q{q}/H{h:.2f}/k{k}/none", int(q), float(h), int(k), "none")


def comp_for(asset: str, *, arbiter: bool) -> S5.Comp:
    q, h, k, e = FROZEN[asset]
    floor = int(e) if arbiter else 0
    return S5.Comp(S5.comp_key(q, h, k, floor, arbiter), int(q), float(h),
                   int(k), floor, bool(arbiter))


# --------------------------------------------------------------------------
# The percentile census.  Outcome-blind by construction; the mutant breaks that.
# --------------------------------------------------------------------------

class Census:
    """Empirical mid-rank percentiles per ``(asset, phase, Q)`` stratum.

    Rows are added with their terminal label attached but the label is NEVER
    consulted while freezing - it exists only so the mutant can be expressed as
    the single line it is, and so the diagnostic rank separations can be
    computed from the same rows AFTER the score is frozen.
    """

    def __init__(self, outcome_conditioned: bool = False) -> None:
        self.outcome_conditioned = bool(outcome_conditioned)
        self._rows: dict[tuple, dict[str, list[float]]] = {}
        self._terminal: dict[tuple, list[bool]] = {}
        self._frozen: dict[tuple, dict[str, np.ndarray]] = {}

    def add(self, stratum: tuple, values: Mapping[str, float], terminal: bool
            ) -> None:
        table = self._rows.setdefault(stratum, {name: [] for name in RAW_NAMES})
        for name in RAW_NAMES:
            table[name].append(float(values[name]))
        self._terminal.setdefault(stratum, []).append(bool(terminal))

    def freeze(self) -> None:
        for stratum, table in self._rows.items():
            labels = np.asarray(self._terminal[stratum], bool)
            keep = labels if self.outcome_conditioned else np.ones(len(labels), bool)
            self._frozen[stratum] = {
                name: np.sort(np.asarray(values, np.float64)[keep])
                for name, values in table.items()}

    def percentile(self, stratum: tuple, name: str, value: float) -> float:
        """Mid-rank empirical CDF, so ties land on one deterministic value."""

        table = self._frozen.get(stratum)
        if table is None:
            raise SweepRefusal(f"census has no stratum {stratum}")
        column = table[name]
        size = len(column)
        if size == 0:
            return 0.5
        below = int(np.searchsorted(column, value, side="left"))
        at_or_below = int(np.searchsorted(column, value, side="right"))
        return (below + at_or_below) / (2.0 * size)

    def counts(self) -> dict[str, int]:
        return {"|".join(str(part) for part in stratum): int(len(table["a_attack"]))
                for stratum, table in self._frozen.items()}


def score_from_percentiles(values: Mapping[str, float]) -> dict[str, float]:
    """The frozen assembly.  ``values`` are already percentiles in [0, 1]."""

    a = 0.5 * (values["a_attack"] + (1.0 - values["a_ext_per_attack"]))
    d = 0.5 * (values["d_absdelta"] + (1.0 - values["d_ext_per_absdelta"]))
    f = 0.5 * (values["f_reversal"] + values["f_onesided"])
    s = float(values["s_persist"])
    mem = (values["m_touches"] + values["m_held"] + values["m_prior"]) / 3.0
    return {"A": a, "D": d, "F": f, "S": s, "Mem": mem,
            "R5": (a + d + f + s + mem) / 5.0,
            "R4mem": (a + d + f + mem) / 4.0}


# --------------------------------------------------------------------------
# Reading one extreme at one bar out of the zone-episode cache.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Look:
    """One extreme read at one detection bar: raw score inputs plus diagnostics."""

    raw: dict[str, float]
    diag: dict[str, float]
    terminal: bool


def look_at(zone: FZ.ZoneSide, shared: Mapping[str, np.ndarray], bar: int,
            side: int, *, prior_low: float, prior_high: float, atr_mid2: float,
            terminal: bool) -> Look | None:
    """The raw component vector for ``side``'s extreme at ``bar``, or ``None``.

    Every read is truncated at ``bar``: the running series carry the episode's
    figures only as far as the bar being scored, so a rule can never see the
    rest of the episode it is standing inside.
    """

    series = zone.series
    index = int(bar)
    if int(series["epi_open"][index]) < 0 or not bool(series["run_ext_valid"][index]):
        return None
    touch_bar = int(series["last_touch_bar"][index])
    if touch_bar < 0:
        return None
    if index + 1 < SCHEDULE_MIN_BARS:
        return None

    direction = 1.0 if int(side) > 0 else -1.0
    attack = float(series["cum_attack"][index])
    extension = float(series["cum_ext_ticks"][index])
    absdelta = abs(float(series["cum_adelta"][index]))
    delta = np.asarray(shared["delta"], np.float64)
    volume = np.asarray(shared["vol"], np.float64)
    twoside = np.asarray(shared["twoside"], np.float64)

    # Flush: the reversal-aligned delta printed in the two bars after the last
    # touch, truncated at the bar being scored.
    stop = min(touch_bar + FLUSH_BARS, index)
    window = delta[touch_bar + 1: stop + 1]
    reversal = direction * float(window.sum()) if len(window) else 0.0
    touch_volume = float(volume[touch_bar])
    onesided = (abs(float(delta[touch_bar])) / touch_volume
                if touch_volume > 0.0 else 0.0)

    # Schedule: signed per-minute delta persistence over the trailing window.
    start = max(0, index + 1 - SCHEDULE_WINDOW_BARS)
    trail = delta[start: index + 1]
    fade = float(np.count_nonzero(direction * trail > 0.0))
    contra = float(np.count_nonzero(direction * trail < 0.0))
    persist = (fade - contra) / float(len(trail))

    extreme = float(series["run_ext_mid2"][index])
    at_level = float(min(abs(extreme - prior_low), abs(extreme - prior_high))
                     <= PRIOR_LEVEL_ATR * atr_mid2)

    raw = {
        "a_attack": attack,
        "a_ext_per_attack": extension / (attack + 1.0),
        "d_absdelta": absdelta,
        "d_ext_per_absdelta": extension / (absdelta + 1.0),
        "f_reversal": reversal,
        "f_onesided": onesided,
        "s_persist": persist,
        "m_touches": float(series["touches_so_far"][index]),
        "m_held": float(series["held_so_far"][index]),
        "m_prior": at_level,
    }

    episode_start = int(series["epi_start"][index])
    span = slice(episode_start, index + 1)
    opposite = np.diff(np.concatenate(
        ([0.0], np.asarray(series["cum_opp_vol"][span], np.float64))))
    touches = np.flatnonzero(np.asarray(series["touch"][span], bool))
    intervals = np.diff(touches).astype(np.float64)
    diag = {
        "reload": float(np.asarray(series["reload"][span], np.float64).sum()),
        "twoside_touch": (float(twoside[touch_bar]) / touch_volume
                          if touch_volume > 0.0 else 0.0),
        "cvd_slope": FZ._slope(opposite),
        "attack_slope": FZ._slope(np.asarray(series["attack"][span], np.float64)),
        "touch_interval_slope": (FZ._slope(intervals) if len(intervals) >= 2
                                 else float("nan")),
    }
    return Look(raw, diag, bool(terminal))


# --------------------------------------------------------------------------
# Opportunities: one per armed extreme, sweep 5's graded law.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Opportunity:
    position: int
    asset: str
    d8: int
    phase_idx: int
    side: int                     # the quieted extreme's fade side
    bar: int                      # the detection bar T
    anchor_bar: int               # the selected extreme's own bar
    stratum: tuple
    quieted: Look | None
    opposite: Look | None
    scores: dict[str, dict[str, float]] = field(default_factory=dict)
    margin: float | None = None
    margin_r4: float | None = None
    regime: float = float("nan")


def opportunity_bars(plane: S4.Plane, position: int, side: int,
                     det: S4.Detector) -> np.ndarray:
    """Detection bars reduced to one per armed extreme (sweep-5 gate=episode)."""

    geometry = plane.geometry[position]
    if geometry is None:
        return np.zeros(0, np.int64)
    geo = geometry[side]
    rec = plane.records[position]
    bars = S4.detection_bars(geo, det, plane.deadline_ts(position), rec.lat)
    if not len(bars):
        return bars
    return bars[S5._episode_starts(geo.anchor[bars])]


def enumerate_opportunities(plane: S4.Plane, zones: Mapping[int, FZ.ZoneCell],
                            assets: Sequence[str]) -> list[Opportunity]:
    out: list[Opportunity] = []
    for position, rec in enumerate(plane.records):
        if rec.asset not in assets or plane.geometry[position] is None:
            continue
        cell = zones.get(position)
        if cell is None:
            continue
        ctx = plane.ctxs[position]
        det = detector_for(rec.asset)
        phase_idx = int(plane.cands[position].phase_idx)
        stratum = (rec.asset, phase_idx, int(det.q))
        mid = np.asarray(rec.mid, np.float64)
        run_high = np.maximum.accumulate(mid)
        run_low = np.minimum.accumulate(mid)
        span = (run_high - run_low) / S3.usd_to_mid2(rec.asset)
        for side in (1, -1):
            geo = plane.geometry[position][side]
            for bar in opportunity_bars(plane, position, side, det):
                index = int(bar)
                looks: dict[int, Look | None] = {}
                for extreme in (side, -side):
                    other = plane.geometry[position][extreme]
                    looks[extreme] = look_at(
                        cell.sides[extreme], cell.shared, index, extreme,
                        prior_low=float(ctx.prior_low),
                        prior_high=float(ctx.prior_high),
                        atr_mid2=float(ctx.atr_mid2),
                        terminal=bool(int(other.anchor[index]) == int(other.terminal_bar)))
                out.append(Opportunity(
                    position=position, asset=rec.asset, d8=int(rec.d8),
                    phase_idx=phase_idx, side=int(side), bar=index,
                    anchor_bar=int(geo.anchor[index]), stratum=stratum,
                    quieted=looks[side], opposite=looks[-side],
                    regime=float(span[index])))
    return out


def build_census(opportunities: Sequence[Opportunity], outcome_conditioned: bool
                 ) -> Census:
    census = Census(outcome_conditioned)
    for opportunity in opportunities:
        for look in (opportunity.quieted, opportunity.opposite):
            if look is not None:
                census.add(opportunity.stratum, look.raw, look.terminal)
    census.freeze()
    return census


def apply_scores(opportunities: Sequence[Opportunity], census: Census) -> None:
    for opportunity in opportunities:
        for role, look in (("quieted", opportunity.quieted),
                           ("opposite", opportunity.opposite)):
            if look is None:
                continue
            percentiles = {name: census.percentile(opportunity.stratum, name,
                                                   look.raw[name])
                           for name in RAW_NAMES}
            scored = score_from_percentiles(percentiles)
            scored.update({f"P_{name}": value
                           for name, value in percentiles.items()})
            opportunity.scores[role] = scored
        if len(opportunity.scores) == 2:
            opportunity.margin = (opportunity.scores["quieted"]["R5"]
                                  - opportunity.scores["opposite"]["R5"])
            opportunity.margin_r4 = (opportunity.scores["quieted"]["R4mem"]
                                     - opportunity.scores["opposite"]["R4mem"])


def margin_thresholds(opportunities: Sequence[Opportunity], key: str = "margin"
                      ) -> dict[tuple, float]:
    """The frozen 60th-percentile margin per stratum.  Not swept, not tuned."""

    buckets: dict[tuple, list[float]] = {}
    for opportunity in opportunities:
        value = getattr(opportunity, key)
        if value is not None:
            buckets.setdefault(opportunity.stratum, []).append(float(value))
    return {stratum: float(np.percentile(np.asarray(values, np.float64),
                                         MARGIN_PERCENTILE))
            for stratum, values in buckets.items()}


# --------------------------------------------------------------------------
# ARM-R5: sweep 5's state machine with the margin rule in the gate's place.
# --------------------------------------------------------------------------

def margin_side_shot(plane: S4.Plane, position: int, side: int,
                     det: S4.Detector, passes: np.ndarray) -> S5.Shot:
    """``(detection bar, candidate row)`` of this side's first R5 entry.

    Identical to ``sweep5.side_shot`` with ``gate=episode`` and no E floor,
    except that the detection gate is the paired margin rule rather than the
    arbiter, and there is no arrival recheck: the margin is a property of the
    detection bar and re-reading it later would make the score an entry clock,
    the same failure sweep 5 refused for ``vs_mean``.
    """

    geometry = plane.geometry[position]
    if geometry is None:
        return S5.Shot(-1, -1, "no_context", 0, 0)
    geo = geometry[side]
    rec = plane.records[position]
    deadline = plane.deadline_ts(position)
    bars = opportunity_bars(plane, position, side, det)
    if not len(bars):
        return S5.Shot(-1, -1, "no_detection", 0, 0)
    if not len(geo.cand_ts):
        return S5.Shot(-1, -1, "no_candidate", 0, 0)
    agree = np.asarray(passes, bool)[bars]
    slot = np.searchsorted(geo.cand_ts, rec.lat[bars], side="left")
    has_candidate = slot < len(geo.cand_ts)
    stamps = geo.cand_ts[np.minimum(slot, len(geo.cand_ts) - 1)]
    before_stop = stamps < geo.stop_ns[bars]
    inside_deadline = stamps <= deadline
    code = np.full(len(bars), S5.CODE_ENTERED, np.int64)
    code[~inside_deadline] = S5.CODE_PAST_DEADLINE
    code[~before_stop] = S5.CODE_NEW_EXTREME
    code[~has_candidate] = S5.CODE_NO_CANDIDATE
    code[~agree] = S5.CODE_ARBITER_DETECT
    taken = np.flatnonzero(code == S5.CODE_ENTERED)
    cancels = int(np.count_nonzero(code[:taken[0]] == S5.CODE_ARBITER_DETECT)
                  if len(taken) else np.count_nonzero(code == S5.CODE_ARBITER_DETECT))
    if len(taken):
        first = int(taken[0])
        return S5.Shot(int(bars[first]), int(geo.cand_row[int(slot[first])]),
                       "entered", cancels, 0)
    return S5.Shot(-1, -1, S5.REASONS[int(code[-1])], cancels, 0)


def margin_entry(plane: S4.Plane, position: int, det: S4.Detector,
                 passes: Mapping[int, np.ndarray]) -> tuple[S4.Entry | None, str]:
    """The cell's one R5 entry: earliest surviving detection-entry, both sides."""

    if plane.geometry[position] is None:
        return None, "no_context"
    cell = plane.cands[position]
    shots: list[tuple[int, int, int, int]] = []
    reasons: list[str] = []
    for side in (1, -1):
        shot = margin_side_shot(plane, position, side, det, passes[side])
        reasons.append(shot.reason)
        if shot.row >= 0:
            shots.append((int(cell.ts[shot.row]), shot.bar, -side, shot.row))
    if not shots:
        return None, max(reasons, key=lambda name: S5.REASON_RANK[name])
    shots.sort()
    _stamp, bar, negated, row = shots[0]
    entry = S4.make_entry(plane, position, row, -negated, bar)
    if entry is None:
        return None, "unavailable"
    return entry, "entered"


def pass_masks(plane: S4.Plane, opportunities: Sequence[Opportunity],
               thresholds: Mapping[tuple, float], *, swap: bool
               ) -> dict[int, dict[int, np.ndarray]]:
    """Per (cell, side) boolean bar masks of opportunities clearing the rule.

    ``swap`` is the null's within-cell high-low exchange: the pair's roles trade
    places, which negates the margin and nothing else.
    """

    out: dict[int, dict[int, np.ndarray]] = {}
    for opportunity in opportunities:
        table = out.setdefault(opportunity.position, {})
        for side in (1, -1):
            if side not in table:
                table[side] = np.zeros(int(plane.records[opportunity.position].n),
                                       bool)
        if opportunity.margin is None:
            continue
        margin = -opportunity.margin if swap else opportunity.margin
        threshold = thresholds.get(opportunity.stratum)
        if threshold is None:
            continue
        if margin > 0.0 and margin >= threshold:
            table[opportunity.side][opportunity.bar] = True
    return out


# --------------------------------------------------------------------------
# Arm lines.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class ArmLine:
    arm: str
    asset: str
    entries: list[S4.Entry]
    book: dict[str, int]
    cells: int
    per_cell: dict[int, tuple[bool, bool]]


def arm_lines(plane: S4.Plane, arbs: Sequence[np.ndarray],
              opportunities: Sequence[Opportunity],
              thresholds: Mapping[tuple, float], asset: str
              ) -> tuple[dict[str, ArmLine], dict[int, tuple[bool, bool]]]:
    """The three arms plus the swapped R5 the null needs, on one asset."""

    det = detector_for(asset)
    clean = pass_masks(plane, [row for row in opportunities
                               if row.asset == asset], thresholds, swap=False)
    swapped = pass_masks(plane, [row for row in opportunities
                                 if row.asset == asset], thresholds, swap=True)
    lines = {arm: ArmLine(arm, asset, [], S5._book(), 0, {}) for arm in ARMS}
    swap_cells: dict[int, tuple[bool, bool]] = {}
    controls = {"D": comp_for(asset, arbiter=False),
                "M": comp_for(asset, arbiter=True)}
    for position, rec in enumerate(plane.records):
        if rec.asset != asset:
            continue
        for arm in ARMS:
            lines[arm].cells += 1
        for arm, comp in controls.items():
            entry, reason, _ca, _ce = S5.comp_entry(plane, arbs, position, comp)
            lines[arm].book[reason] = lines[arm].book.get(reason, 0) + 1
            if entry is not None:
                lines[arm].entries.append(entry)
                lines[arm].per_cell[position] = (True, joint_hit(plane, entry))
            else:
                lines[arm].per_cell[position] = (False, False)
        masks = clean.get(position, {1: np.zeros(rec.n, bool),
                                     -1: np.zeros(rec.n, bool)})
        entry, reason = margin_entry(plane, position, det, masks)
        lines["R5"].book[reason] = lines["R5"].book.get(reason, 0) + 1
        if entry is not None:
            lines["R5"].entries.append(entry)
            lines["R5"].per_cell[position] = (True, joint_hit(plane, entry))
        else:
            lines["R5"].per_cell[position] = (False, False)
        other = swapped.get(position, {1: np.zeros(rec.n, bool),
                                       -1: np.zeros(rec.n, bool)})
        swap_entry, _swap_reason = margin_entry(plane, position, det, other)
        swap_cells[position] = ((False, False) if swap_entry is None
                                else (True, joint_hit(plane, swap_entry)))
    return lines, swap_cells


def joint_hit(plane: S4.Plane, entry: S4.Entry) -> bool:
    """Terminal AND the fade side equals ``sign(Delta*)`` at entry (sweep-2)."""

    return bool(entry.hit and S5.side_hit(plane, entry))


def anchor_delay_seconds(plane: S4.Plane, entry: S4.Entry) -> float:
    """Entry decision minus the close of the SELECTED extreme's own bar."""

    if entry.detect_bar < 0:
        return float("nan")
    geometry = plane.geometry[entry.cell]
    if geometry is None:
        return float("nan")
    anchor = int(geometry[entry.side].anchor[entry.detect_bar])
    if anchor < 0:
        return float("nan")
    rec = plane.records[entry.cell]
    return float(entry.ts_ns - int(rec.lat[anchor])) / NANOS_PER_SECOND


def _quantile(values: Sequence[float], point: float) -> float | None:
    array = np.asarray([float(value) for value in values], np.float64)
    array = array[np.isfinite(array)]
    if not len(array):
        return None
    return float(np.percentile(array, point))


def line_stats(plane: S4.Plane, line: ArmLine, missing_pairs: int,
               opportunities: int) -> dict[str, object]:
    rows = line.entries
    hits = int(sum(joint_hit(plane, row) for row in rows))
    low, high = S1.wilson(hits, len(rows))
    anchor = [anchor_delay_seconds(plane, row) for row in rows]
    terminal = [row.hit for row in rows]
    side = [S5.side_hit(plane, row) for row in rows]
    return {
        "arm": line.arm, "asset": line.asset, "cells": line.cells,
        "entered": len(rows), "coverage": len(rows) / max(1, line.cells),
        "opportunities": int(opportunities), "missing_pairs": int(missing_pairs),
        "joint_hits": hits,
        "joint_hit_rate": (hits / len(rows)) if rows else None,
        "ci95": [low, high], "wilson_low": low,
        "yield": hits / max(1, line.cells),
        "terminal_hit_rate": float(np.mean(terminal)) if rows else None,
        "side_hit_rate": float(np.mean(side)) if rows else None,
        "anchor_delay_median_s": _quantile(anchor, 50.0),
        "anchor_delay_p90_s": _quantile(anchor, 90.0),
        "terminal_delay_median_s": _quantile([row.delay_s for row in rows], 50.0),
        "terminal_delay_p90_s": _quantile([row.delay_s for row in rows], 90.0),
        "detect_delay_median_s": S4._median(
            [S4.detect_delay_seconds(plane, row) for row in rows]),
        "no_detection": int(line.book.get("no_detection", 0)),
        "gate_blocked": int(line.book.get("arbiter_detect", 0)),
        "no_candidate": int(line.book.get("no_candidate", 0)
                            + line.book.get("past_deadline", 0)
                            + line.book.get("unavailable", 0)),
        "new_extreme": int(line.book.get("new_extreme", 0)),
    }


def phase_stats(plane: S4.Plane, line: ArmLine) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for phase in plane.phases.get(line.asset, ()):
        rows = [row for row in line.entries if row.phase_idx == phase]
        cells = plane.phase_cells.get((line.asset, phase), 0)
        hits = int(sum(joint_hit(plane, row) for row in rows))
        low, high = S1.wilson(hits, len(rows))
        out[str(phase)] = {
            "cells": cells, "entered": len(rows),
            "coverage": len(rows) / max(1, cells), "joint_hits": hits,
            "joint_hit_rate": (hits / len(rows)) if rows else None,
            "wilson_low": low, "ci95": [low, high],
            "yield": hits / max(1, cells)}
    return out


# --------------------------------------------------------------------------
# Paired asset-day block confidence intervals on the arm deltas.
# --------------------------------------------------------------------------

def _rate_over_days(entries: Sequence[S4.Entry], plane: S4.Plane,
                    days: Sequence[int]) -> float | None:
    by_day: dict[int, list[S4.Entry]] = {}
    for row in entries:
        by_day.setdefault(int(row.d8), []).append(row)
    hits = 0
    total = 0
    for day in days:
        rows = by_day.get(int(day), [])
        total += len(rows)
        hits += int(sum(joint_hit(plane, row) for row in rows))
    return (hits / total) if total else None


def delta_ci(plane: S4.Plane, treatment: ArmLine, control: ArmLine,
             days: Sequence[int], draws: int = BOOTSTRAP_DRAWS
             ) -> dict[str, object]:
    """Paired asset-day block bootstrap of ``J(treatment) - J(control)``."""

    rng = np.random.default_rng(SEED)
    base_treatment = _rate_over_days(treatment.entries, plane, days)
    base_control = _rate_over_days(control.entries, plane, days)
    point = (None if base_treatment is None or base_control is None
             else base_treatment - base_control)
    sample: list[float] = []
    keys = np.asarray(sorted(days), np.int64)
    for _draw in range(int(draws)):
        picked = keys[rng.integers(0, len(keys), len(keys))]
        left = _rate_over_days(treatment.entries, plane, picked)
        right = _rate_over_days(control.entries, plane, picked)
        if left is None or right is None:
            continue
        sample.append(left - right)
    if not sample:
        return {"delta": point, "ci95": [None, None], "draws_used": 0}
    array = np.asarray(sample, np.float64)
    return {"delta": point,
            "ci95": [float(np.percentile(array, 2.5)),
                     float(np.percentile(array, 97.5))],
            "draws_used": int(len(array))}


# --------------------------------------------------------------------------
# Rank separation and the diagnostic columns.
# --------------------------------------------------------------------------

def auc(values: Sequence[float], labels: Sequence[bool]) -> float | None:
    """Mann-Whitney rank separation of ``values`` by ``labels``, ties at 0.5."""

    array = np.asarray([float(value) for value in values], np.float64)
    flags = np.asarray(list(labels), bool)
    keep = np.isfinite(array)
    array, flags = array[keep], flags[keep]
    positive = int(flags.sum())
    negative = int(len(flags) - positive)
    if positive == 0 or negative == 0:
        return None
    order = np.argsort(array, kind="mergesort")
    ranked = np.empty(len(array), np.float64)
    sorted_values = array[order]
    position = 0
    while position < len(sorted_values):
        stop = position
        while stop + 1 < len(sorted_values) and sorted_values[stop + 1] == sorted_values[position]:
            stop += 1
        ranked[order[position: stop + 1]] = 0.5 * (position + stop) + 1.0
        position = stop + 1
    return float((ranked[flags].sum() - positive * (positive + 1) / 2.0)
                 / (positive * negative))


def separations(opportunities: Sequence[Opportunity], asset: str
                ) -> dict[str, object]:
    """Per-component and per-diagnostic terminal-vs-non-terminal separation."""

    values: dict[str, list[float]] = {
        name: [] for name in (*COMPONENTS, "R5", *RAW_NAMES, *DIAG_NAMES)}
    labels: list[bool] = []
    for opportunity in opportunities:
        if opportunity.asset != asset:
            continue
        for role, look in (("quieted", opportunity.quieted),
                           ("opposite", opportunity.opposite)):
            if look is None or role not in opportunity.scores:
                continue
            scored = opportunity.scores[role]
            for name in (*COMPONENTS, "R5"):
                values[name].append(float(scored[name]))
            for name in RAW_NAMES:
                values[name].append(float(look.raw[name]))
            for name in DIAG_NAMES:
                values[name].append(float(look.diag[name]))
            labels.append(look.terminal)
    return {"n": len(labels), "terminal": int(sum(labels)),
            "auc": {name: auc(column, labels) for name, column in values.items()}}


def regime_cut(plane: S4.Plane, line: ArmLine, opportunities: Sequence[Opportunity],
               forecast: Mapping[int, float]) -> dict[str, object]:
    """Balance-vs-trend: running range against the forecast daily variance."""

    ratios: list[float] = []
    lookup: dict[tuple[int, int, int], float] = {}
    for opportunity in opportunities:
        if opportunity.asset != line.asset:
            continue
        variance = forecast.get(int(opportunity.d8))
        if variance is None or not (variance > 0.0):
            continue
        ratio = float(opportunity.regime) / math.sqrt(float(variance))
        lookup[(opportunity.position, opportunity.side, opportunity.bar)] = ratio
        ratios.append(ratio)
    if len(ratios) < 3:
        return {"terciles": None, "cuts": {}}
    edges = [float(np.percentile(np.asarray(ratios, np.float64), point))
             for point in (100.0 / 3.0, 200.0 / 3.0)]
    buckets: dict[str, list[bool]] = {"balance": [], "middle": [], "trend": []}
    for row in line.entries:
        ratio = lookup.get((row.cell, row.side, row.detect_bar))
        if ratio is None:
            continue
        name = ("balance" if ratio <= edges[0]
                else "middle" if ratio <= edges[1] else "trend")
        buckets[name].append(joint_hit(plane, row))
    return {"terciles": edges,
            "cuts": {name: {"entered": len(flags), "joint_hits": int(sum(flags)),
                            "joint_hit_rate": (float(np.mean(flags)) if flags
                                               else None)}
                     for name, flags in buckets.items()}}


# --------------------------------------------------------------------------
# The within-cell high-low swap null.
# --------------------------------------------------------------------------

def swap_null(clean: Mapping[str, dict[str, ArmLine]],
              swaps: Mapping[str, dict[int, tuple[bool, bool]]],
              assets: Sequence[str], draws: int = NULL_DRAWS) -> dict[str, object]:
    """Max-statistic null over NKD/SI x {R5-D, R5-M}.

    A draw exchanges the two extremes' roles inside a randomly chosen half of
    the cells.  Timestamps, detector states, phase and the two control arms are
    untouched, because neither control reads the margin the swap negates.
    """

    rng = np.random.default_rng(SEED)
    statistics: dict[str, float] = {}
    tables: dict[str, np.ndarray] = {}
    for asset in assets:
        lines = clean[asset]
        positions = sorted(lines["R5"].per_cell)
        entered = np.asarray([lines["R5"].per_cell[p][0] for p in positions], bool)
        hit = np.asarray([lines["R5"].per_cell[p][1] for p in positions], bool)
        swap_entered = np.asarray([swaps[asset][p][0] for p in positions], bool)
        swap_hit = np.asarray([swaps[asset][p][1] for p in positions], bool)
        bits = rng.random((int(draws), len(positions))) < 0.5
        drawn_entered = np.where(bits, swap_entered, entered)
        drawn_hit = np.where(bits, swap_hit, hit)
        totals = drawn_entered.sum(axis=1)
        hits = drawn_hit.sum(axis=1)
        rates = np.where(totals > 0, hits / np.maximum(totals, 1), np.nan)
        for control in ("D", "M"):
            base = lines[control]
            control_rate = (sum(joint_hit_flag for _e, joint_hit_flag
                                in base.per_cell.values())
                            / max(1, len(base.entries)))
            key = f"{asset}/R5-{control}"
            tables[key] = rates - control_rate
            observed = lines["R5"]
            observed_rate = (sum(flag for _e, flag in observed.per_cell.values())
                             / max(1, len(observed.entries)))
            statistics[key] = observed_rate - control_rate
    stacked = np.vstack([tables[key] for key in sorted(tables)])
    maxima = np.nanmax(stacked, axis=0)
    finite = maxima[np.isfinite(maxima)]
    out: dict[str, object] = {"draws": int(draws), "seed": SEED,
                              "draws_used": int(len(finite)),
                              "statistics": statistics}
    out["p_adjusted"] = {
        key: float((1 + int(np.count_nonzero(finite >= value)))
                   / (1 + len(finite)))
        for key, value in statistics.items()}
    out["p_max_adjusted"] = (max(out["p_adjusted"].values())
                             if out["p_adjusted"] else None)
    return out


# --------------------------------------------------------------------------
# The decision table.
# --------------------------------------------------------------------------

def decide(report: Mapping[str, object]) -> dict[str, object]:
    """KEEP / SECOND-ITERATION / KILL exactly per the charter's frozen bounds."""

    per_asset: dict[str, dict[str, object]] = {}
    for asset in DECIDING:
        block = report["by_asset"][asset]
        deltas = {control: block["deltas"][f"R5-{control}"] for control in ("D", "M")}
        values = {control: deltas[control]["delta"] for control in ("D", "M")}
        lows = {control: deltas[control]["ci95"][0] for control in ("D", "M")}
        r5 = block["arms"]["R5"]
        reasons: list[str] = []
        coverage_ok = r5["coverage"] >= COVERAGE_FLOOR[asset]
        if not coverage_ok:
            reasons.append(f"coverage {r5['coverage']:.3f} < {COVERAGE_FLOOR[asset]}")
        p90 = r5["anchor_delay_p90_s"]
        delay_ok = p90 is not None and p90 <= DELAY_P90_CAP_S[asset]
        if not delay_ok:
            reasons.append(f"p90 delay {p90} > {DELAY_P90_CAP_S[asset]}")
        yields_ok = all(r5["yield"] > block["arms"][control]["yield"]
                        for control in ("D", "M"))
        if not yields_ok:
            reasons.append("yield not above both controls")
        sizes = [value for value in values.values() if value is not None]
        keep_delta = bool(sizes) and all(value >= KEEP_DELTA for value in sizes)
        second_delta = bool(sizes) and all(value >= SECOND_DELTA for value in sizes)
        if not second_delta:
            reasons.append("a delta is below +0.03")
        elif not keep_delta:
            reasons.append("a delta is below +0.05")
        lows_ok = all(value is not None and value > 0.0 for value in lows.values())
        if not lows_ok:
            reasons.append("a paired 95% lower bound is not above zero")
        adjusted = {control: report["null"]["p_adjusted"].get(f"{asset}/R5-{control}")
                    for control in ("D", "M")}
        p_ok = all(value is not None and value <= KEEP_P
                   for value in adjusted.values())
        p_second = all(value is not None and value <= SECOND_P
                       for value in adjusted.values())
        if not p_second:
            reasons.append("an adjusted p-value exceeds 0.10")
        elif not p_ok:
            reasons.append("an adjusted p-value exceeds 0.05")
        directions = {name: report["separations"][asset]["auc"].get(name)
                      for name in RANK_DIRECTION_REQUIRED}
        direction_ok = all(value is not None and value > 0.5
                           for value in directions.values())
        if not direction_ok:
            reasons.append("A/D/F rank direction is wrong")
        per_asset[asset] = {
            "deltas": values, "ci_low": lows, "p_adjusted": adjusted,
            "coverage": r5["coverage"], "coverage_ok": coverage_ok,
            "p90_delay_s": p90, "delay_ok": delay_ok, "yield_ok": yields_ok,
            "keep_delta": keep_delta, "second_delta": second_delta,
            "ci_low_ok": lows_ok, "p_keep_ok": p_ok, "p_second_ok": p_second,
            "rank_direction_ok": direction_ok, "rank_auc": directions,
            "reasons": reasons}
    signs = {asset: [value for value in per_asset[asset]["deltas"].values()
                     if value is not None] for asset in DECIDING}
    agree = all(all(value > 0 for value in sizes) for sizes in signs.values() if sizes)
    keep = all(per_asset[asset]["keep_delta"] and per_asset[asset]["ci_low_ok"]
               and per_asset[asset]["p_keep_ok"] and per_asset[asset]["coverage_ok"]
               and per_asset[asset]["delay_ok"] and per_asset[asset]["yield_ok"]
               for asset in DECIDING)
    second = (not keep and agree
              and all(per_asset[asset]["second_delta"]
                      and per_asset[asset]["p_second_ok"]
                      and per_asset[asset]["coverage_ok"]
                      and per_asset[asset]["delay_ok"]
                      and per_asset[asset]["rank_direction_ok"]
                      for asset in DECIDING)
              and any(not per_asset[asset]["keep_delta"] for asset in DECIDING))
    verdict = "KEEP" if keep else ("SECOND-ITERATION" if second else "KILL")
    fired = {asset: ("KEEP" if keep else "SECOND-ITERATION" if second else "KILL")
             for asset in DECIDING}
    kills = {asset: [reason for reason in per_asset[asset]["reasons"]]
             for asset in DECIDING}
    return {"verdict": verdict, "assets_agree_in_direction": agree,
            "per_asset": per_asset, "fired": fired, "kill_reasons": kills,
            "report_only": list(REPORT_ONLY)}


# --------------------------------------------------------------------------
# Log rows.
# --------------------------------------------------------------------------

def log_rows(report: Mapping[str, object]) -> list[dict[str, object]]:
    stamp = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    shared = {
        "registered_utc": stamp, "spec_sha": SPEC_SHA, "code_sha": code_sha(),
        "split_sha": S4.split_sha(), "outcome_law_sha": S4.outcome_law_sha(),
        "null_seed": SEED, "parent_trial": PARENT_TRIAL,
        "selection_rule": SELECTION_RULE, "verdict": "",
        "days": sum(report["asset_days"].values())}
    miss = {"HG": "err_rate_hg", "NKD": "err_rate_nkd", "SI": "err_rate_si"}
    rows: list[dict[str, object]] = []
    counter = 0
    for asset in ASSETS:
        if asset not in report["by_asset"]:
            continue
        block = report["by_asset"][asset]
        for arm in ARMS:
            line = block["arms"][arm]
            counter += 1
            joint = line["joint_hit_rate"]
            note = f"no-cash arm {arm} J={joint if joint is None else round(joint, 4)}"
            rows.append({
                **shared, "id": f"sweep6-{counter:03d}", "family": FAMILY,
                "rule": f"{asset}/ARM-{arm}",
                "params": json.dumps(list(FROZEN[asset]) + [arm]),
                "coverage": line["coverage"],
                "delay_med_s": line["anchor_delay_median_s"],
                miss[asset]: None if joint is None else 1.0 - float(joint),
                "null_margin": (report["null"]["p_adjusted"].get(f"{asset}/R5-D")
                                if arm == "R5" else None),
                "note": note[:60]})
        counter += 1
        r5 = block["arms"]["R5"]
        joint = r5["joint_hit_rate"]
        deltas = block["deltas"]
        rows.append({
            **shared, "id": f"sweep6-{counter:03d}", "family": FAMILY,
            "rule": f"{asset}/PAIRED",
            "params": json.dumps({"q": FROZEN[asset][0], "h": FROZEN[asset][1],
                                  "k": FROZEN[asset][2], "e": FROZEN[asset][3],
                                  "margin_pct": MARGIN_PERCENTILE}),
            "coverage": r5["coverage"], "delay_med_s": r5["anchor_delay_p90_s"],
            miss[asset]: None if joint is None else 1.0 - float(joint),
            "null_margin": report["null"]["p_adjusted"].get(f"{asset}/R5-M"),
            "note": (f"R5-D={deltas['R5-D']['delta']} "
                     f"R5-M={deltas['R5-M']['delta']} "
                     f"{report['decision']['fired'].get(asset, 'report')}")[:60]})
    return rows


# --------------------------------------------------------------------------
# Printing.
# --------------------------------------------------------------------------

def _num(value: object, width: int = 8, digits: int = 3) -> str:
    return S1._num(value, width, digits)


def print_census(report: Mapping[str, object]) -> None:
    print("\n== percentile census (outcome-blind, per asset|phase|Q stratum)")
    print(f"{'stratum':16s} {'rows':>7s}")
    for stratum, count in sorted(report["census"].items()):
        print(f"{stratum:16s} {count:7d}")
    print(f"opportunities={report['opportunities']} "
          f"scored_pairs={report['scored_pairs']} "
          f"missing_pairs={report['missing_pairs']}")
    print("\n== frozen stratum margin thresholds (60th percentile, not swept)")
    for stratum, value in sorted(report["margin_thresholds"].items()):
        print(f"{stratum:16s} {value:10.6f}")


def print_arms(report: Mapping[str, object]) -> None:
    print("\n== arms, no cash (J = joint hit: terminal AND fade side == sign(Delta*))")
    print("   dly = selected extreme -> decision; tdly = terminal extreme -> "
          "decision (sweep-4's budget quantity), both in seconds")
    print(f"{'asset':5s} {'arm':4s} {'cells':>6s} {'entr':>5s} {'cover':>7s} "
          f"{'miss':>5s} {'Jhits':>6s} {'J':>7s} {'wlo':>7s} {'whi':>7s} "
          f"{'Y':>7s} {'term':>7s} {'side':>7s} {'dly50':>8s} {'dly90':>8s} "
          f"{'tdly50':>8s} {'tdly90':>8s} {'note':>12s}")
    for asset in ASSETS:
        if asset not in report["by_asset"]:
            continue
        tag = "report-only" if asset in REPORT_ONLY else "deciding"
        for arm in ARMS:
            row = report["by_asset"][asset]["arms"][arm]
            print(f"{asset:5s} {arm:4s} {row['cells']:6d} {row['entered']:5d} "
                  f"{_num(row['coverage'], 7)} {row['missing_pairs']:5d} "
                  f"{row['joint_hits']:6d} {_num(row['joint_hit_rate'], 7)} "
                  f"{_num(row['ci95'][0], 7)} {_num(row['ci95'][1], 7)} "
                  f"{_num(row['yield'], 7)} {_num(row['terminal_hit_rate'], 7)} "
                  f"{_num(row['side_hit_rate'], 7)} "
                  f"{_num(row['anchor_delay_median_s'], 8, 1)} "
                  f"{_num(row['anchor_delay_p90_s'], 8, 1)} "
                  f"{_num(row['terminal_delay_median_s'], 8, 1)} "
                  f"{_num(row['terminal_delay_p90_s'], 8, 1)} {tag:>12s}")


def print_deltas(report: Mapping[str, object]) -> None:
    print("\n== arm deltas with paired asset-day block 95% CIs")
    print(f"{'asset':5s} {'pair':8s} {'delta':>8s} {'ci_lo':>8s} {'ci_hi':>8s} "
          f"{'p_adj':>8s} {'draws':>7s}")
    for asset in ASSETS:
        if asset not in report["by_asset"]:
            continue
        for control in ("D", "M"):
            block = report["by_asset"][asset]["deltas"][f"R5-{control}"]
            key = f"{asset}/R5-{control}"
            print(f"{asset:5s} {'R5-' + control:8s} {_num(block['delta'], 8)} "
                  f"{_num(block['ci95'][0], 8)} {_num(block['ci95'][1], 8)} "
                  f"{_num(report['null']['p_adjusted'].get(key), 8)} "
                  f"{block['draws_used']:7d}")


def print_phases(report: Mapping[str, object]) -> None:
    print("\n== per-phase cuts")
    print(f"{'asset':5s} {'arm':4s} {'ph':>3s} {'cells':>6s} {'entr':>5s} "
          f"{'cover':>7s} {'J':>7s} {'wlo':>7s} {'Y':>7s}")
    for asset in ASSETS:
        if asset not in report["by_asset"]:
            continue
        for arm in ARMS:
            phases = report["by_asset"][asset]["phases"][arm]
            for phase in sorted(phases):
                row = phases[phase]
                print(f"{asset:5s} {arm:4s} {phase:>3s} {row['cells']:6d} "
                      f"{row['entered']:5d} {_num(row['coverage'], 7)} "
                      f"{_num(row['joint_hit_rate'], 7)} "
                      f"{_num(row['wilson_low'], 7)} {_num(row['yield'], 7)}")


def print_separations(report: Mapping[str, object]) -> None:
    print("\n== univariate rank separation, terminal vs non-terminal (AUC)")
    names = (*COMPONENTS, "R5")
    header = " ".join(f"{name:>8s}" for name in names)
    print(f"{'asset':5s} {'n':>6s} {'term':>6s} {header}")
    for asset in ASSETS:
        if asset not in report["separations"]:
            continue
        block = report["separations"][asset]
        cells = " ".join(_num(block["auc"].get(name), 8) for name in names)
        print(f"{asset:5s} {block['n']:6d} {block['terminal']:6d} {cells}")
    print("\n-- raw inputs")
    header = " ".join(f"{name[:8]:>8s}" for name in RAW_NAMES)
    print(f"{'asset':5s} {header}")
    for asset in ASSETS:
        if asset not in report["separations"]:
            continue
        block = report["separations"][asset]
        cells = " ".join(_num(block["auc"].get(name), 8) for name in RAW_NAMES)
        print(f"{asset:5s} {cells}")


def print_diagnostics(report: Mapping[str, object]) -> None:
    print("\n== diagnostic columns (never in any score); AUC vs terminal")
    header = " ".join(f"{name[:9]:>9s}" for name in DIAG_NAMES)
    print(f"{'asset':5s} {header}  polarity")
    for asset in ASSETS:
        if asset not in report["separations"]:
            continue
        block = report["separations"][asset]
        cells = " ".join(_num(block["auc"].get(name), 9) for name in DIAG_NAMES)
        twoside = block["auc"].get("twoside_touch")
        polarity = ("-" if twoside is None
                    else "two-sided->terminal" if twoside > 0.5
                    else "one-sided->terminal")
        print(f"{asset:5s} {cells}  {polarity}")
    print("\n== balance-vs-trend regime cut (running range / sqrt(forecast var))")
    print(f"{'asset':5s} {'arm':4s} {'tercile':9s} {'entr':>5s} {'Jhits':>6s} "
          f"{'J':>7s}")
    for asset in ASSETS:
        if asset not in report["by_asset"]:
            continue
        for arm in ARMS:
            block = report["by_asset"][asset]["regime"][arm]
            for name in ("balance", "middle", "trend"):
                row = block["cuts"].get(name)
                if row is None:
                    continue
                print(f"{asset:5s} {arm:4s} {name:9s} {row['entered']:5d} "
                      f"{row['joint_hits']:6d} {_num(row['joint_hit_rate'], 7)}")


def print_null(report: Mapping[str, object]) -> None:
    block = report["null"]
    print(f"\n== within-cell high-low swap null: {block['draws']} draws, "
          f"seed {block['seed']}, max-statistic across NKD/SI x {{R5-D, R5-M}}")
    print(f"{'statistic':16s} {'observed':>10s} {'p_adj':>8s}")
    for key in sorted(block["statistics"]):
        print(f"{key:16s} {_num(block['statistics'][key], 10, 4)} "
              f"{_num(block['p_adjusted'][key], 8, 4)}")
    print(f"p_max_adjusted={block['p_max_adjusted']}")


def print_decision(report: Mapping[str, object]) -> None:
    block = report["decision"]
    print("\n== DECISION TABLE (pre-registered bounds; HG reported, never deciding)")
    print(f"{'asset':5s} {'d(R5-D)':>8s} {'d(R5-M)':>8s} {'cover':>7s} "
          f"{'p90dly':>8s} {'+0.05':>6s} {'+0.03':>6s} {'CI>0':>6s} "
          f"{'p<=.05':>7s} {'p<=.10':>7s} {'covOK':>6s} {'dlyOK':>6s} "
          f"{'yldOK':>6s} {'ADF':>5s} {'fired':>16s}")
    for asset in DECIDING:
        row = block["per_asset"][asset]
        print(f"{asset:5s} {_num(row['deltas']['D'], 8)} "
              f"{_num(row['deltas']['M'], 8)} {_num(row['coverage'], 7)} "
              f"{_num(row['p90_delay_s'], 8, 1)} "
              f"{str(row['keep_delta']):>6s} {str(row['second_delta']):>6s} "
              f"{str(row['ci_low_ok']):>6s} {str(row['p_keep_ok']):>7s} "
              f"{str(row['p_second_ok']):>7s} {str(row['coverage_ok']):>6s} "
              f"{str(row['delay_ok']):>6s} {str(row['yield_ok']):>6s} "
              f"{str(row['rank_direction_ok']):>5s} {block['fired'][asset]:>16s}")
    print(f"assets_agree_in_direction={block['assets_agree_in_direction']} "
          f"verdict={block['verdict']}")
    # The p90 delay bound is graded on the selected-extreme reading the charter
    # names; the terminal-extreme reading (sweep 4's own budget quantity) is
    # printed beside it so the bound cannot turn on which one was meant.
    for asset in DECIDING:
        row = report["by_asset"][asset]["arms"]["R5"]
        print(f"  {asset} delay budget {DELAY_P90_CAP_S[asset]:.0f}s: "
              f"selected-extreme p90={_num(row['anchor_delay_p90_s'], 8, 1)} "
              f"terminal-extreme p90={_num(row['terminal_delay_p90_s'], 8, 1)} "
              f"(controls D/M p90 "
              f"{_num(report['by_asset'][asset]['arms']['D']['anchor_delay_p90_s'], 8, 1)}/"
              f"{_num(report['by_asset'][asset]['arms']['M']['anchor_delay_p90_s'], 8, 1)})")
    for asset in DECIDING:
        reasons = block["kill_reasons"][asset]
        print(f"  {asset}: " + ("; ".join(reasons) if reasons else "all bounds pass"))
    for asset in REPORT_ONLY:
        if asset in report["by_asset"]:
            row = report["by_asset"][asset]["arms"]["R5"]
            print(f"  {asset} (report-only, never deciding): J="
                  f"{row['joint_hit_rate']} coverage={row['coverage']:.3f}")
    print("\nfallback: R4mem = (A+D+F+Mem)/4 was computed for every scored "
          "extreme and stored under report['fallback_sealed']; it is SEALED and "
          "openable only under the charter's second-iteration conditions, so no "
          "R4mem number is printed here.")


# --------------------------------------------------------------------------
# Report I/O.
# --------------------------------------------------------------------------

def read_report() -> dict[str, object]:
    if OUT_PATH.is_file():
        return json.loads(OUT_PATH.read_text())
    return {"schema": SCHEMA, "tier": "exploratory",
            "claim": "EXPLORE-day sweep 6, the frozen decisive flow test; "
                     "no cash; can kill, cannot promote"}


def write_report(report: Mapping[str, object]) -> None:
    payload = {key: value for key, value in report.items()
               if not key.startswith("_")}
    OUT_PATH.write_text(json.dumps(payload, sort_keys=True, indent=1,
                                   default=S1._json_default) + "\n")


def load_zone_cells(plane: S4.Plane, assets: Sequence[str]
                    ) -> dict[int, FZ.ZoneCell]:
    """Join the zones cache onto plane positions by ``(phase, phase_open)``."""

    cache: dict[tuple[str, int], dict[tuple[str, int], FZ.ZoneCell]] = {}
    out: dict[int, FZ.ZoneCell] = {}
    for position, rec in enumerate(plane.records):
        if rec.asset not in assets:
            continue
        key = (rec.asset, int(rec.d8))
        if key not in cache:
            cache[key] = FZ.load_zones(rec.asset, int(rec.d8))
        cell = cache[key].get((rec.phase, int(rec.phase_open_ts_ns)))
        if cell is None:
            continue
        if cell.bars != int(rec.n):
            raise SweepRefusal(
                f"zones cell {rec.asset}/{rec.d8}/{rec.phase} has {cell.bars} "
                f"bars, the plane has {rec.n}")
        out[position] = cell
    return out


def forecast_variance(store: CTX.ContextStore, plane: S4.Plane) -> dict[int, float]:
    out: dict[int, float] = {}
    for rec in plane.records:
        day = int(rec.d8)
        if day in out:
            continue
        payload = store.context_for(rec.asset, day)
        row = payload.get("forecast")
        if isinstance(row, Mapping) and row.get("forecast_variance"):
            out[day] = float(row["forecast_variance"])
    return out


def run(plane: S4.Plane, arbs: Sequence[np.ndarray], assets: Sequence[str],
        days: Mapping[str, int], store: CTX.ContextStore) -> dict[str, object]:
    mutant = _sweep_mutant()
    zones = load_zone_cells(plane, assets)
    opportunities = enumerate_opportunities(plane, zones, assets)
    census = build_census(opportunities, mutant == MUTANT_PEEKS)
    apply_scores(opportunities, census)
    thresholds = margin_thresholds(opportunities)
    forecast = forecast_variance(store, plane)
    explore = S1._explore_days(assets)

    report: dict[str, object] = {
        "opportunities": len(opportunities),
        "scored_pairs": int(sum(1 for row in opportunities
                                if row.margin is not None)),
        "missing_pairs": int(sum(1 for row in opportunities
                                 if row.margin is None)),
        "census": census.counts(),
        "margin_thresholds": {"|".join(str(part) for part in stratum): value
                              for stratum, value in thresholds.items()},
        "asset_days": dict(days), "cells": dict(plane.cells),
        "mutant": mutant, "by_asset": {}, "separations": {}}

    clean: dict[str, dict[str, ArmLine]] = {}
    swaps: dict[str, dict[int, tuple[bool, bool]]] = {}
    for asset in assets:
        lines, swap_cells = arm_lines(plane, arbs, opportunities, thresholds, asset)
        clean[asset] = lines
        swaps[asset] = swap_cells
        own = [row for row in opportunities if row.asset == asset]
        missing = int(sum(1 for row in own if row.margin is None))
        block: dict[str, object] = {
            "config": {"q": FROZEN[asset][0], "h": FROZEN[asset][1],
                       "k": FROZEN[asset][2], "e": FROZEN[asset][3]},
            "arms": {arm: line_stats(plane, lines[arm], missing, len(own))
                     for arm in ARMS},
            "phases": {arm: phase_stats(plane, lines[arm]) for arm in ARMS},
            "regime": {arm: regime_cut(plane, lines[arm], opportunities, forecast)
                       for arm in ARMS},
            "deltas": {f"R5-{control}": delta_ci(plane, lines["R5"],
                                                 lines[control], explore[asset])
                       for control in ("D", "M")}}
        report["by_asset"][asset] = block
        report["separations"][asset] = separations(opportunities, asset)

    report["null"] = swap_null(clean, swaps,
                               [asset for asset in DECIDING if asset in clean])
    report["decision"] = decide(report)
    # The fallback rides sealed: stored, never printed, never read by any rule
    # here.  Opening it needs the charter's second-iteration conditions.
    report["fallback_sealed"] = {
        "score": "R4mem = (A+D+F+Mem)/4",
        "margin_thresholds": {
            "|".join(str(part) for part in stratum): value for stratum, value
            in margin_thresholds(opportunities, "margin_r4").items()},
        "margins": [{"asset": row.asset, "d8": row.d8, "phase": row.phase_idx,
                     "side": row.side, "bar": row.bar, "margin": row.margin_r4,
                     "quieted": row.scores.get("quieted", {}).get("R4mem"),
                     "opposite": row.scores.get("opposite", {}).get("R4mem")}
                    for row in opportunities if row.margin_r4 is not None]}
    return report


# --------------------------------------------------------------------------
# Selftest: synthetic fixtures only.  Zero era bytes.
# --------------------------------------------------------------------------

def _fixture_raw(scale: float) -> dict[str, float]:
    return {name: scale for name in RAW_NAMES}


def selftest() -> int:
    mutant = _sweep_mutant()
    failures: list[str] = []

    def _check(name: str, body) -> None:
        try:
            body()
        except Exception as error:  # noqa: BLE001 - a red case is the signal
            failures.append(f"{name}: {type(error).__name__}: {error}")

    stratum = ("NKD", 1, 10)

    def score_assembly() -> None:
        # Percentiles chosen so every term is distinct by hand:
        # A = (0.8 + 1-0.2)/2 = 0.8; D = (0.6 + 1-0.4)/2 = 0.6;
        # F = (0.9 + 0.5)/2 = 0.7; S = 0.3; Mem = (0.6+0.3+1.0)/3 = 0.6333...
        values = {"a_attack": 0.8, "a_ext_per_attack": 0.2, "d_absdelta": 0.6,
                  "d_ext_per_absdelta": 0.4, "f_reversal": 0.9,
                  "f_onesided": 0.5, "s_persist": 0.3, "m_touches": 0.6,
                  "m_held": 0.3, "m_prior": 1.0}
        scored = score_from_percentiles(values)
        assert abs(scored["A"] - 0.8) < 1e-12, f"A={scored['A']}"
        assert abs(scored["D"] - 0.6) < 1e-12, f"D={scored['D']}"
        assert abs(scored["F"] - 0.7) < 1e-12, f"F={scored['F']}"
        assert abs(scored["S"] - 0.3) < 1e-12, f"S={scored['S']}"
        assert abs(scored["Mem"] - 1.9 / 3.0) < 1e-12, f"Mem={scored['Mem']}"
        hand = (0.8 + 0.6 + 0.7 + 0.3 + 1.9 / 3.0) / 5.0
        assert abs(scored["R5"] - hand) < 1e-12, f"R5={scored['R5']} != {hand}"
        hand4 = (0.8 + 0.6 + 0.7 + 1.9 / 3.0) / 4.0
        assert abs(scored["R4mem"] - hand4) < 1e-12, f"R4mem={scored['R4mem']}"

    def percentile_law() -> None:
        # Four rows 1,2,3,4: the mid-rank percentile of 3 is (2 + 3)/(2*4).
        census = Census(False)
        for index, value in enumerate((1.0, 2.0, 3.0, 4.0)):
            census.add(stratum, _fixture_raw(value), index >= 2)
        census.freeze()
        got = census.percentile(stratum, "a_attack", 3.0)
        assert abs(got - 0.625) < 1e-12, f"P(3)={got}"
        assert abs(census.percentile(stratum, "a_attack", 0.0)) < 1e-12, "P(0)"
        assert abs(census.percentile(stratum, "a_attack", 9.0) - 1.0) < 1e-12, "P(9)"

    def census_is_outcome_blind() -> None:
        # The same four rows, but only the last two are terminal.  A census that
        # keeps every row puts 3.0 at 0.625; one restricted to terminal rows puts
        # it at 0.25.  This is the one line the mutant moves.
        rows = ((1.0, False), (2.0, False), (3.0, True), (4.0, True))
        blind = Census(False)
        peeking = Census(True)
        for value, terminal in rows:
            blind.add(stratum, _fixture_raw(value), terminal)
            peeking.add(stratum, _fixture_raw(value), terminal)
        blind.freeze()
        peeking.freeze()
        assert abs(blind.percentile(stratum, "a_attack", 3.0) - 0.625) < 1e-12, (
            f"blind P(3)={blind.percentile(stratum, 'a_attack', 3.0)}")
        live = build_census(
            [Opportunity(0, "NKD", 20220301, 1, 1, 5, 0, stratum,
                         Look(_fixture_raw(value), {}, terminal), None)
             for value, terminal in rows], mutant == MUTANT_PEEKS)
        got = live.percentile(stratum, "a_attack", 3.0)
        assert abs(got - 0.625) < 1e-12, (
            f"the live census is outcome-conditioned: P(3)={got}")

    def margin_rule() -> None:
        # Threshold is the 60th percentile of the stratum's margins.  Only a
        # margin that is BOTH positive and at or above it may fire.
        rows = []
        for index, margin in enumerate((-0.30, -0.10, 0.02, 0.05, 0.40)):
            row = Opportunity(index, "NKD", 20220301, 1, 1, index, 0, stratum,
                              None, None)
            row.margin = margin
            rows.append(row)
        thresholds = margin_thresholds(rows)
        # Five sorted margins, so the 60th percentile sits at position
        # 0.6*(5-1) = 2.4, i.e. 0.02 + 0.4*(0.05-0.02) = 0.032 by hand.
        assert abs(thresholds[stratum] - 0.032) < 1e-12, (
            f"threshold {thresholds[stratum]} != 0.032")
        fires = [bool(row.margin > 0.0 and row.margin >= thresholds[stratum])
                 for row in rows]
        assert fires == [False, False, False, True, True], f"fires {fires}"
        # A margin above the threshold but negative can never fire, whatever the
        # stratum's distribution is.
        negative = Opportunity(9, "NKD", 20220301, 1, 1, 9, 0, stratum, None, None)
        negative.margin = -0.001
        assert not (negative.margin > 0.0
                    and negative.margin >= thresholds[stratum]), "negative fired"

    def swap_case() -> None:
        # The swap exchanges the pair's roles, which negates the margin: a
        # firing opportunity must stop firing when its margin was the only thing
        # carrying it, and a mirrored one must start.
        row = Opportunity(0, "NKD", 20220301, 1, 1, 4, 0, stratum, None, None)
        row.margin = 0.40
        thresholds = {stratum: 0.10}
        assert row.margin > 0.0 and row.margin >= thresholds[stratum], "clean"
        swapped = -row.margin
        assert not (swapped > 0.0 and swapped >= thresholds[stratum]), (
            "the swap left the margin firing")
        mirror = Opportunity(1, "NKD", 20220301, 1, 1, 4, 0, stratum, None, None)
        mirror.margin = -0.40
        assert (-mirror.margin) > 0.0 and (-mirror.margin) >= thresholds[stratum], (
            "the swap did not revive the mirrored margin")

    def auc_law() -> None:
        # Perfect separation is 1.0, reversed is 0.0, all-ties is 0.5.
        assert abs(auc([1.0, 2.0, 3.0, 4.0], [False, False, True, True]) - 1.0) < 1e-12
        assert abs(auc([4.0, 3.0, 2.0, 1.0], [False, False, True, True])) < 1e-12
        assert abs(auc([1.0, 1.0, 1.0, 1.0], [False, False, True, True]) - 0.5) < 1e-12

    _check("score_assembly", score_assembly)
    _check("percentile_law", percentile_law)
    _check("census_is_outcome_blind", census_is_outcome_blind)
    _check("margin_rule", margin_rule)
    _check("swap_case", swap_case)
    _check("auc_law", auc_law)

    expected_red = {MUTANT_PEEKS: "census_is_outcome_blind"}
    if mutant:
        died = {line.split(":", 1)[0] for line in failures}
        target = expected_red.get(mutant)
        if target is None:
            print(f"sweep6_selftest_unknown_mutant {mutant}")
            return 1
        if target not in died:
            print(f"sweep6_selftest_mutant_survived mutant={mutant} case={target}")
            return 1
        print(f"sweep6_selftest_red mutant={mutant} died={sorted(died)}")
        for line in failures:
            print(f"  {line}")
        return 1
    if failures:
        print("sweep6_selftest_red died="
              f"{sorted(line.split(':', 1)[0] for line in failures)}")
        for line in failures:
            print(f"  {line}")
        return 1
    print("sweep6_selftest_ok cases=6")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", nargs="?", default="all",
                        choices=("test", "log", "all"))
    parser.add_argument("--assets", default="HG,NKD,SI")
    parser.add_argument("--root", default=str(M.MILL_ROOT))
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    assets = tuple(name.strip().upper() for name in args.assets.split(",")
                   if name.strip())
    if any(asset not in ASSETS for asset in assets):
        raise SweepRefusal(f"unknown asset in {args.assets!r}")
    started = time.monotonic()
    plane, arbs, days = S5.load_plane(assets, Path(args.root))
    store = CTX.ContextStore()
    report = read_report()
    report.update(run(plane, arbs, assets, days, store))
    report["spec_sha"] = SPEC_SHA
    report["code_sha"] = code_sha()
    report["split_sha"] = S4.split_sha()
    report["outcome_law_sha"] = S4.outcome_law_sha()
    report["parent_trial"] = PARENT_TRIAL
    report["zones_manifest"] = dict(FZ.load_manifest()["totals"])

    print_census(report)
    print_arms(report)
    print_deltas(report)
    print_phases(report)
    print_separations(report)
    print_diagnostics(report)
    print_null(report)
    print_decision(report)

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
