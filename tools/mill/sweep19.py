#!/usr/bin/env python3
"""Sweep 19 of the side-resolution mill: the continuation-entry frame.

The USER's frame, and the library's own words for it
(``a-clean-continuation-short``, page notes in
``research/discretionary/DIAGRAM_NOTES_REMAINDER_2026-08-27.md``): do NOT
forecast whether an extreme holds.  Let the extreme form, let price displace
away from it, and enter in the DISPLACEMENT direction at the retest that holds
- so the hold has been OBSERVED once before any money is at risk.  The p10
refill note is the slow lane in the source's own ordering ("the initiative
print ARMS the level and does not trigger it; the trigger is the return"), and
the p11 squeeze note is the fast lane, again in the source's words ("the move
happened fast, with real aggression, no retest, no false start ... once buyers
hit that move and got absorbed, the entry is available").

The charter section this answers is "The magnitude turn" in
``.audit/briefs/mill-side-resolution.md``.  Sweep 15 established that the
16-feature state predicts SIZE and never DIRECTION, and the USER's correction
records that at an extreme the side is GIVEN - the open question was only
whether the extreme holds.  Every prior unit answered that question by
forecasting.  This one refuses to forecast it and waits to watch it happen.

Direction note.  The plane's occurrence side is already the fade side: side +1
sits at a running LOW (``S7A.side_arrays`` returns ``prior_low``), side -1 at a
running HIGH.  Displacement away from a low is UP, away from a high is DOWN, so
the displacement direction equals the occurrence side and the frame keeps the
side the extreme gave it.  What changes is only WHEN, never WHICH WAY.

Machinery is imported, never re-implemented.  Sweep 9's ``build_plane`` is the
occurrence plane and its counters are the refuse-to-run gate; sweep 14 supplies
the stream builder, the fold law, ``Sums``/``Ridge`` and the 16-feature vector;
sweep 15 supplies the |Y| magnitude fit; sweep 7a supplies the zone geometry
AND the retest-hold law itself (``side_triggers``: armed -> touched ->
departed, with a same-side new extreme as the breach guard), which this unit
generalises to a train-adaptive band and holds to account against the original
in the selftest; sweep 1 supplies the frozen entry law, the outcome law, cash,
MDD and the log.

Sweep 18's ``developing_range`` was NOT imported on purpose: that file is being
written by a sibling unit in this same session and a cross-import would couple
this receipt to a moving file.  The day-type flag is computed here from
``rec.mid`` directly, cross-phase and causally, which is also what sweep 12
could not supply - its five day states are all prior-session objects and none
of them is a developing-range share (checked, not assumed).
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

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import mill as M  # noqa: F401  (the shard loader the price-path caches come off)
import flow as FLOW
import sweep1 as S1
import sweep7a as S7A
import sweep8 as S8
import sweep9_twins as S9
import sweep12 as S12
import sweep14 as S14
import sweep15 as S15

# --------------------------------------------------------------------------
# The law, registered before anything is read.
# --------------------------------------------------------------------------

SPEC = """QRE2MILLSWEEP19
tier=exploratory; EXPLORE-only; kill-only.  Family F16-CONT.  Parent trial
  sweep16-017.  Seed 20260827.  USER-directed frame.
DATA LAW.  EXPLORE days only, off the existing mill caches.  No packs, no HOLD,
  no teacher labels, no 2021, no 2025H2.  The occurrence plane is sweep 9's
  ``build_plane`` verbatim and its counters are the refuse-to-run gate: 47402
  rows, certifiable HG 138 / NKD 132 / SI 132, candidates_seen 313131,
  cells_with_rows 385, scoring days 41/40/39.  Price paths are the 60 s bar
  series the mill shards were sampled into (``mill.bar_series``: the bar
  closing at t reads the last trusted quote STRICTLY before t), cached as
  ``CellRec.mid``.
THE LEVEL.  Each deduped occurrence carries its side's running extreme
  ``prior[bar]`` (``S7A.side_arrays``).  One EPISODE is one distinct
  (cell, side, level); it is ARMED at the first occurrence carrying that level.
  An episode whose arm bar already sits beyond its own level is refused.
BREACH.  Price trading beyond the extreme cancels the episode outright, no
  entry.  Breach is the union of a same-side new-extreme flag and a strictly
  adverse relative price, which is sweep 7a's ``side_triggers`` guard.
SLOW LANE.  rel(b) = side * (mid[b] - level) / ATR14, positive away from the
  level.  DISPLACEMENT at the first bar with rel >= D.  RETEST at the first bar
  after it with rel <= B and no breach in between.  HOLD at the first bar after
  the retest with rel strictly greater than the retest's own rel - price
  turning back in the displacement direction for one completed minute bar,
  whose value is the last trusted quote strictly before the entry stamp.  Enter
  on the displacement side at the hold bar.
FAST LANE.  Displacement speed rel(disp)/(disp - arm) in the train top tercile
  AND the opposing aggressor flow absorbed: within an adaptive window W after
  the displacement, the opposing side attacked (peak opposing delta at or above
  the train q75 of |delta|), that attack has shrunk to nothing (opposing delta
  at or below the train q25 of |delta|), and the displacement was not given
  back (rel >= rel(disp)).  Enter at the absorption stamp, no retest required.
  Flow bar k closes at ``lat[k+1]``, so it is shifted by one bar to carry the
  same "known at lat[k]" law the mid series carries.
THRESHOLDS.  Every threshold is train-day adaptive per asset x phase-type,
  walk-forward, from STRICTLY prior EXPLORE days with at least 25 of them.  No
  absolute constants.  Over train episodes of that stratum: MOVE = the
  per-episode maximum rel before breach; D = q60(MOVE); B = q20(MOVE);
  SPEED cut = q67 of D/(disp - arm) over train episodes that displaced;
  W = max(2, median(disp - arm)); flow cuts = q75 and q25 of |delta| over train
  bars; trend cut = q67 of the developing-range directional share over train
  bars; size cut = the median TRAIN prediction of the |Y| ridge.
ENTRY AND OUTCOME.  Frozen entry law ``S1.make_entry`` (last trusted quote
  strictly before t), frozen cost, frozen to-close cert with the -900 wall.  At
  most ONE entry per (cell, side) per line, the FIRST trigger that passes that
  line's gates; episodes that arm and never trigger are counted.  An entry
  needs at least one bar after it so the to-close outcome is not degenerate.
DAY-TYPE VARIANT.  A trend-day flag measured causally from the day's own
  developing range: |mid(t) - day open| / (developing high - developing low)
  over every bar of the asset-day STRICTLY before the entry stamp, cross-phase.
  Gate = at or above the train top tercile.  Reported with and without.
SIZE VARIANT.  The walk-forward predicted-magnitude channel: sweep 14's ridge
  refit on |Y| exactly as sweep 15's M3 did (lambda 1.0, standardised,
  unpenalised intercept, ``fold_days``, training-column-mean imputation),
  predicted at the ARMING occurrence's own 16-feature vector.  Gate = at or
  above the median TRAIN prediction, the top train-adaptive half.  Reported
  with and without.
MEASUREMENTS per asset, per lane, per variant combination (ungated, day, size,
  both): entries, armed episodes, trigger rate, cell coverage, P(cert>0) with a
  Wilson 95 interval, mean and median cert, usd per asset-day on scoring days,
  day-ordered and trade-ordered MDD, mean post-entry adverse excursion in ATR
  measured back toward the original extreme, and the share of entries that
  retrace through the extreme.
CONTROLS, pre-registered.  C1 LATENESS-MATCHED: same side, same count, random
  stamps drawn from the line's own trigger-offset distribution inside the same
  cells, 2000 draws - structure must beat pure waiting.  C2 OLD FRAME: fade
  entry at the original occurrence stamp of the same armed episodes, same
  denominators.  C3 FIXED CLOCK: same side at the per-asset median trigger
  offset from phase open, no structure condition.  C4 BLOCK PERMUTATION:
  asset-day blocks permuted within asset, each entry re-priced at the same bar
  offset in the permuted day's cell of the same stratum, 2000 draws, max-stat
  over lanes x variants x assets, adjusted p on every headline.
LETTERS, pre-registered.  CONT-LIVE: a lane or variant posts positive usd/day
  beating C1 AND C2 with adjusted p <= 0.05 on a deciding asset (NKD or SI) at
  cell coverage >= 0.15.  CONT-PARTIAL: positive on a deciding asset and
  beating at least one control, but short of the full CONT-LIVE conjunction.
  NONE: nothing positive.  UNPOWERED: entries < 30 on every deciding asset.
  The four letters do not partition every outcome - a line can beat both
  controls at adequate coverage and still fail the max-stat null, which is the
  same enumeration gap sweep 15 hit and recorded.  Rather than let PARTIAL fire
  by elimination and hide it, every line reports the FIRST pre-registered bound
  it failed, so the letter is never the whole record.
MUTANT.  QRE2_MILL_S19_MUTANT=retest_hold_reads_future makes the hold
  confirmation read the bar AFTER the entry stamp; the planted slow-lane and
  breach cases must go red.
"""

ASSETS = S1.ASSETS
DECIDING = ("NKD", "SI")
SEED = S1.SEED

FAMILY = "F16-CONT"
PARENT_TRIAL = "sweep16-017"
SELECTION_RULE = ("none: pre-registered lanes, variants, quantile marks and "
                  "controls; every threshold train-adaptive, no tuning")

# The refuse-to-run gate: sweep 9's published plane, as sweep 14 banked it.
REPRO_ROWS = S14.REPRO_ROWS
REPRO_COUNTERS = S14.REPRO_COUNTERS
REPRO_CERTIFIABLE = S14.REPRO_CERTIFIABLE
REPRO_SCORING_DAYS = {"HG": 41, "NKD": 40, "SI": 39}

MIN_PRIOR_DAYS = S14.MIN_PRIOR_DAYS if hasattr(S14, "MIN_PRIOR_DAYS") else 25
MIN_FIT_ROWS = S14.MIN_FIT_ROWS

# Pre-registered quantile marks.  The MARKS are fixed; every VALUE they select
# is measured on the fold's own training days, which is what "no absolute
# constants" means.
Q_DISPLACE = 60.0
Q_BAND = 20.0
Q_SPEED = 67.0
Q_FLOW_HI = 75.0
Q_FLOW_LO = 25.0
Q_TREND = 67.0
Q_SIZE = 50.0
MIN_WINDOW_BARS = 2

LANES = ("SLOW", "FAST")
VARIANTS = ("ungated", "day", "size", "both")
CONTROL_DRAWS = 2000
NULL_DRAWS = 2000

COVERAGE_FLOOR = 0.15
POWER_FLOOR = 30
NULL_CEILING = 0.05

MUTANT_ENV = "QRE2_MILL_S19_MUTANT"
MUTANT_FUTURE = "retest_hold_reads_future"
MUTANTS = (MUTANT_FUTURE,)

OUT_PATH = ROOT / ".audit/mill-sweep19.json"
LOG_PATH = S1.LOG_PATH
LOG_PREFIX = "sweep19"


class SweepRefusal(RuntimeError):
    pass


SPEC_SHA = S1._sha_text(SPEC)


def code_sha() -> str:
    return S1._sha_file(Path(__file__).resolve())


def _mutant() -> str:
    name = os.environ.get(MUTANT_ENV, "")
    if name and name not in MUTANTS:
        raise SweepRefusal(f"unknown sweep-19 mutant {name!r}; known: {MUTANTS}")
    return name


def _rate(hits: float, total: float) -> dict[str, object]:
    if total <= 0:
        return {"n": 0, "rate": None, "lo": None, "hi": None}
    lo, hi = S1.wilson(int(round(hits)), int(total))
    return {"n": int(total), "rate": float(hits) / float(total),
            "lo": float(lo), "hi": float(hi)}


def _pct(values: Sequence[float], mark: float) -> float | None:
    array = np.asarray([v for v in values if np.isfinite(v)], np.float64)
    if not len(array):
        return None
    return float(np.percentile(array, mark))


# --------------------------------------------------------------------------
# Episodes.  The occurrence extremes define the levels.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Episode:
    """One (cell, side, level), armed at the first occurrence carrying it."""

    cell: int
    asset: str
    d8: int
    phase: str
    side: int
    arm_bar: int
    level: float
    atr: float
    rel: np.ndarray        # rel[j] at bar arm_bar + j, truncated at breach
    rel_full: np.ndarray   # the same path untruncated; the mutant's leak only
    breached: bool         # the episode ended on a breach inside the cell
    neg: np.ndarray        # opposing aggressor flow, same offsets, causal
    x: np.ndarray          # the arming occurrence's 16-feature causal vector
    payoff_at_arm: float   # the OLD frame's cert at the occurrence stamp (C2)

    @property
    def horizon(self) -> int:
        return int(len(self.rel))


def _breach_offsets(rel: np.ndarray, new_ext: np.ndarray) -> int:
    """The first offset that trades beyond the extreme, or ``len(rel)``.

    Sweep 7a's ``side_triggers`` treats a same-side new extreme as the event
    that voids a pending touch; a strictly adverse relative price is the same
    event read off the price path.  The union is taken so neither reading can
    let a breached episode through.
    """

    bad = (rel < 0.0) | new_ext.astype(bool)
    hit = np.flatnonzero(bad)
    return int(hit[0]) if len(hit) else int(len(rel))


def build_episodes(streams: Sequence[S14.Stream], cells: Sequence[S8.Cell8],
                   deltas: Mapping[int, np.ndarray]
                   ) -> tuple[list[Episode], dict[str, int]]:
    """One episode per distinct (cell, side, level) that an occurrence armed."""

    by_position = {cell.position: cell for cell in cells}
    counters = {"occurrences": 0, "episodes": 0, "arm_beyond_level": 0,
                "levels_repeated": 0, "zero_atr": 0, "no_room": 0}
    out: list[Episode] = []
    for stream in streams:
        cell = by_position[stream.cell]
        if not (cell.atr_mid2 > 0.0):
            counters["zero_atr"] += 1
            continue
        mid = np.asarray(cell.rec.mid, np.float64)
        delta = deltas.get(cell.position)
        seen: set[tuple[int, float]] = set()
        for occ in stream.occs:
            counters["occurrences"] += 1
            side = int(occ.side)
            prior, new_ext, _armed = S7A.side_arrays(cell.geo, side)
            level = float(prior[occ.bar])
            key = (side, level)
            if key in seen:
                counters["levels_repeated"] += 1
                continue
            seen.add(key)
            arm = int(occ.bar)
            if arm + 2 >= cell.n:
                counters["no_room"] += 1
                continue
            rel_full = (side * (mid[arm:] - level)) / cell.atr_mid2
            if rel_full[0] < 0.0:
                # The arm bar has already traded beyond its own level: this
                # occurrence IS the new extreme, so there is no episode here.
                counters["arm_beyond_level"] += 1
                continue
            stop = _breach_offsets(rel_full, np.asarray(new_ext[arm:], bool))
            breached = stop < len(rel_full)
            rel = np.asarray(rel_full[:max(stop, 1)], np.float64)
            if delta is None:
                neg = np.zeros(len(rel), np.float64)
            else:
                neg = np.maximum(0.0, -float(side) * delta[arm:arm + len(rel)])
                if len(neg) < len(rel):
                    neg = np.concatenate(
                        [neg, np.zeros(len(rel) - len(neg), np.float64)])
            out.append(Episode(
                cell=cell.position, asset=cell.asset, d8=cell.d8,
                phase=cell.phase, side=side, arm_bar=arm, level=level,
                atr=float(cell.atr_mid2), rel=rel,
                rel_full=np.asarray(rel_full, np.float64), breached=breached,
                neg=neg, x=occ.x, payoff_at_arm=float(occ.payoff)))
    counters["episodes"] = len(out)
    return out, counters


def load_deltas(cells: Sequence[S8.Cell8]) -> tuple[dict[int, np.ndarray],
                                                    dict[str, int]]:
    """Per-cell aggressor delta, shifted onto the mid series' causality.

    ``flow`` bar ``k`` closes at ``lat[k+1]``, so the bar that has closed by the
    time bar ``k`` of the mid series is stamped is bar ``k-1``.  Shifting by one
    makes ``delta[k]`` obey the same law ``mid[k]`` obeys: everything it saw is
    strictly before ``lat[k]``.
    """

    counters = {"cells": 0, "missing_shard": 0, "missing_cell": 0, "ragged": 0}
    cache: dict[tuple[str, int], object] = {}
    out: dict[int, np.ndarray] = {}
    for cell in cells:
        counters["cells"] += 1
        key = (cell.asset, cell.d8)
        if key not in cache:
            try:
                cache[key] = FLOW.load_flow(cell.asset, cell.d8)
            except FLOW.FlowStop:
                cache[key] = None
        day = cache[key]
        if day is None:
            counters["missing_shard"] += 1
            continue
        arrays = day.get((cell.phase, int(cell.rec.phase_open_ts_ns)))
        if arrays is None:
            counters["missing_cell"] += 1
            continue
        raw = np.asarray(arrays["delta"], np.float64)
        if len(raw) < cell.n - 1:
            counters["ragged"] += 1
            continue
        shifted = np.zeros(cell.n, np.float64)
        shifted[1:] = raw[:cell.n - 1]
        out[cell.position] = shifted
    return out, counters


# --------------------------------------------------------------------------
# The lanes.  Sweep 7a's armed -> touched -> departed machine, with the
# displacement gate the frame adds and a train-adaptive band.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Trigger:
    lane: str
    offset: int            # the entry bar, as an offset from the arm bar
    disp_offset: int
    retest_offset: int
    disp_rel: float
    speed: float


def displacement_offset(rel: np.ndarray, d_cut: float) -> int:
    """First offset whose running maximum reaches the displacement distance."""

    if not (d_cut > 0.0):
        return -1
    runmax = np.maximum.accumulate(rel)
    at = int(np.searchsorted(runmax, d_cut, side="left"))
    return at if at < len(rel) else -1


def slow_trigger(rel: np.ndarray, d_cut: float, b_cut: float,
                 mutant: str = "", rel_full: np.ndarray | None = None
                 ) -> Trigger | None:
    """Displacement, then a retest inside the band, then one holding bar.

    The clean law confirms the hold at bar ``h`` from ``rel[h]`` - a value whose
    quote is the last trusted one STRICTLY before the entry stamp ``lat[h]`` -
    and enters at ``h``.  ``rel`` is truncated at the breach, so an episode that
    traded beyond its level cannot confirm at all.

    The mutant confirms bar ``h`` from ``rel[h + 1]`` and still enters at ``h``,
    which is the bar AFTER the stamp; and it reads the untruncated path, so it
    can also confirm across a breach.  Both are the same error - a value that
    is not yet knowable at the moment money goes down.
    """

    disp = displacement_offset(rel, d_cut)
    if disp <= 0:
        return None
    tail = rel[disp + 1:]
    if not len(tail):
        return None
    inside = np.flatnonzero(tail <= b_cut)
    if not len(inside):
        return None
    retest = disp + 1 + int(inside[0])
    base = float(rel[retest])
    if mutant == MUTANT_FUTURE:
        source = rel if rel_full is None else np.asarray(rel_full, np.float64)
        probe = source[retest + 2:]
        if not len(probe):
            return None
        turned = np.flatnonzero(probe > base)
        if not len(turned):
            return None
        # Confirmed by offset retest+2+turned[0]; entered one bar earlier.
        hold = retest + 1 + int(turned[0])
        if hold >= len(source):
            return None
    else:
        after = rel[retest + 1:]
        if not len(after):
            return None
        turned = np.flatnonzero(after > base)
        if not len(turned):
            return None
        hold = retest + 1 + int(turned[0])
        if hold >= len(rel):
            return None
    return Trigger(lane="SLOW", offset=hold, disp_offset=disp,
                   retest_offset=retest, disp_rel=float(rel[disp]),
                   speed=float(rel[disp]) / float(disp))


def fast_trigger(rel: np.ndarray, neg: np.ndarray, d_cut: float,
                 speed_cut: float, window: int, flow_hi: float,
                 flow_lo: float) -> Trigger | None:
    """Fast displacement whose counter-attack is absorbed, no retest asked."""

    disp = displacement_offset(rel, d_cut)
    if disp <= 0:
        return None
    speed = float(rel[disp]) / float(disp)
    if not (speed >= speed_cut):
        return None
    stop = min(len(rel) - 1, disp + int(window))
    peak = 0.0
    for offset in range(disp + 1, stop + 1):
        peak = max(peak, float(neg[offset]))
        if peak < flow_hi:
            continue
        if float(neg[offset]) > flow_lo:
            continue
        if float(rel[offset]) < float(rel[disp]):
            continue
        return Trigger(lane="FAST", offset=offset, disp_offset=disp,
                       retest_offset=-1, disp_rel=float(rel[disp]),
                       speed=speed)
    return None


# --------------------------------------------------------------------------
# Train-adaptive thresholds, per asset x phase-type, walk-forward.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Cuts:
    d_cut: float
    b_cut: float
    speed_cut: float
    window: int
    flow_hi: float
    flow_lo: float
    trend_cut: float
    size_cut: float
    train_episodes: int


def stratum_cuts(train: Sequence[Episode], flow_pool: Sequence[float],
                 trend_pool: Sequence[float]) -> Cuts | None:
    """Every threshold this stratum will use, from its training days alone."""

    if not train:
        return None
    moves = [float(np.max(ep.rel)) for ep in train if len(ep.rel)]
    d_cut = _pct(moves, Q_DISPLACE)
    b_cut = _pct(moves, Q_BAND)
    if d_cut is None or b_cut is None or not (d_cut > 0.0):
        return None
    speeds: list[float] = []
    spans: list[float] = []
    for ep in train:
        at = displacement_offset(ep.rel, d_cut)
        if at > 0:
            speeds.append(float(ep.rel[at]) / float(at))
            spans.append(float(at))
    speed_cut = _pct(speeds, Q_SPEED)
    window = (int(max(MIN_WINDOW_BARS, round(float(np.median(spans)))))
              if spans else MIN_WINDOW_BARS)
    flow_hi = _pct(flow_pool, Q_FLOW_HI)
    flow_lo = _pct(flow_pool, Q_FLOW_LO)
    trend_cut = _pct(trend_pool, Q_TREND)
    return Cuts(d_cut=float(d_cut), b_cut=float(b_cut),
                speed_cut=float(speed_cut) if speed_cut is not None
                else float("inf"),
                window=window,
                flow_hi=float(flow_hi) if flow_hi is not None else float("inf"),
                flow_lo=float(flow_lo) if flow_lo is not None else 0.0,
                trend_cut=float(trend_cut) if trend_cut is not None
                else float("inf"),
                size_cut=float("nan"), train_episodes=len(train))


# --------------------------------------------------------------------------
# The day-type flag: the developing range's directional share, causal.
# --------------------------------------------------------------------------

def developing_share(cells: Sequence[S8.Cell8]) -> dict[int, np.ndarray]:
    """Per cell, per bar, |mid - day open| / developing range, prior bars only.

    The day's phases are concatenated and ordered by stamp, then accumulated,
    so a bar late in phase 2 sees phase 0 and phase 1; every value at bar ``k``
    is built from bars strictly before ``lat[k]``, which is exactly the window
    ``mid[k]`` itself was sampled from.
    """

    by_day: dict[tuple[str, int], list[S8.Cell8]] = {}
    for cell in cells:
        by_day.setdefault((cell.asset, cell.d8), []).append(cell)
    out: dict[int, np.ndarray] = {}
    for key in sorted(by_day):
        group = by_day[key]
        stamps = np.concatenate([np.asarray(c.rec.lat, np.int64) for c in group])
        mids = np.concatenate([np.asarray(c.rec.mid, np.float64) for c in group])
        order = np.argsort(stamps, kind="stable")
        stamps = stamps[order]
        mids = mids[order]
        cummin = np.minimum.accumulate(mids)
        cummax = np.maximum.accumulate(mids)
        day_open = float(mids[0]) if len(mids) else float("nan")
        for cell in group:
            lat = np.asarray(cell.rec.lat, np.int64)
            # STRICTLY before: "left" then step back one row.
            idx = np.searchsorted(stamps, lat, side="left") - 1
            share = np.full(len(lat), np.nan, np.float64)
            good = idx >= 0
            if good.any():
                low = cummin[idx[good]]
                high = cummax[idx[good]]
                here = mids[idx[good]]
                span = high - low
                with np.errstate(invalid="ignore", divide="ignore"):
                    value = np.abs(here - day_open) / span
                share[good] = np.where(span > 0.0, value, np.nan)
            out[cell.position] = share
    return out


# --------------------------------------------------------------------------
# The size channel: sweep 15's M3 |Y| ridge, walk-forward, per fold.
# --------------------------------------------------------------------------

def magnitude_channel(streams: Sequence[S14.Stream],
                      explore_days: Mapping[str, Sequence[int]],
                      scoring_days: Mapping[str, Sequence[int]]
                      ) -> tuple[dict[tuple[int, int], float],
                                 dict[tuple[str, int], float]]:
    """Out-of-fold predicted |Y| per occurrence, and the fold's train median.

    The ridge is sweep 14's ``Sums``/``Ridge`` fitted through sweep 15's
    ``_fit_targets`` on the absY target - the same object sweep 15's M3 scored
    at +0.119/+0.127/+0.096 out-of-fold, which is the only genuinely
    predictable quantity the program has found.
    """

    by_asset_day: dict[tuple[str, int], list[S14.Stream]] = {}
    for stream in streams:
        by_asset_day.setdefault((stream.asset, stream.d8), []).append(stream)
    preds: dict[tuple[int, int], float] = {}
    cuts: dict[tuple[str, int], float] = {}
    for asset in ASSETS:
        days = sorted(int(day) for day in explore_days[asset])
        score = {int(day) for day in scoring_days.get(asset, [])}
        for index, d8 in enumerate(days):
            if d8 not in score:
                continue
            today = [occ for stream in by_asset_day.get((asset, d8), [])
                     for occ in stream.occs]
            train: list[S14.Occ] = []
            for day in S14.fold_days(days, index, ""):
                for stream in by_asset_day.get((asset, day), []):
                    train.extend(stream.occs)
            if len(train) < MIN_FIT_ROWS or not today:
                continue
            raw = np.vstack([occ.x for occ in train])
            with np.errstate(invalid="ignore"):
                means = np.nanmean(np.where(np.isfinite(raw), raw, np.nan),
                                   axis=0)
            means = np.where(np.isfinite(means), means, 0.0)
            xtr = S14._impute(raw, means)
            ytr = np.asarray([occ.payoff for occ in train], np.float64)
            fits = S15._fit_targets(xtr, ytr)
            ridge = fits["absY"]
            cuts[(asset, d8)] = float(np.percentile(ridge.predict(xtr), Q_SIZE))
            xte = S14._impute(np.vstack([occ.x for occ in today]), means)
            got = ridge.predict(xte)
            for occ, value in zip(today, got):
                preds[(occ.cell, occ.bar)] = float(value)
    return preds, cuts


# --------------------------------------------------------------------------
# The cert plane: every legal (cell, side, bar) cert, for entries and controls.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class CertPlane:
    """``cert[pos, side_index, bar]`` in USD, NaN where entry is illegal."""

    cert: np.ndarray
    wall: np.ndarray
    bars: np.ndarray
    index: dict[int, int]
    stamp: np.ndarray

    def value(self, position: int, side: int, bar: int) -> float:
        row = self.index.get(int(position))
        if row is None:
            return float("nan")
        if not 0 <= int(bar) < int(self.bars[row]):
            return float("nan")
        return float(self.cert[row, 0 if side > 0 else 1, int(bar)])


def build_cert_plane(cells: Sequence[S8.Cell8]) -> CertPlane:
    width = max(int(cell.n) for cell in cells)
    cert = np.full((len(cells), 2, width), np.nan, np.float64)
    wall = np.zeros((len(cells), 2, width), bool)
    bars = np.zeros(len(cells), np.int64)
    stamp = np.zeros((len(cells), width), np.int64)
    index: dict[int, int] = {}
    for row, cell in enumerate(cells):
        index[cell.position] = row
        bars[row] = int(cell.n)
        stamp[row, :cell.n] = np.asarray(cell.rec.lat, np.int64)
        for column, side in enumerate((1, -1)):
            ok = np.asarray(cell.rec.ok(side), bool)
            start = int(cell.rec.legal_from(side))
            legal = np.zeros(cell.n, bool)
            if start >= 0:
                legal[max(start, 1):] = True
            legal &= ok
            legal[0] = False
            # The last bar carries no room for a to-close outcome.
            legal[cell.n - 1] = False
            values = np.asarray(cell.rec.cert(side), np.float64)
            cert[row, column, :cell.n] = np.where(legal, values, np.nan)
            wall[row, column, :cell.n] = np.asarray(cell.rec.wall(side), bool) & legal
    return CertPlane(cert=cert, wall=wall, bars=bars, index=index, stamp=stamp)


# --------------------------------------------------------------------------
# The walk-forward run: one line per (lane, variant), entries per asset.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Fill:
    lane: str
    variant: str
    asset: str
    d8: int
    phase: str
    cell: int
    side: int
    bar: int
    arm_bar: int
    level: float
    cert_usd: float
    wall: bool
    ts_ns: int
    adverse_atr: float
    retraced: bool
    disp_rel: float
    speed: float
    lane_offset: int
    payoff_at_arm: float


def line_key(lane: str, variant: str) -> str:
    return f"{lane}/{variant}"


def _gates_pass(variant: str, trend_ok: bool, size_ok: bool) -> bool:
    if variant == "ungated":
        return True
    if variant == "day":
        return trend_ok
    if variant == "size":
        return size_ok
    return trend_ok and size_ok


@dataclass(slots=True)
class Run:
    fills: dict[str, list[Fill]]
    armed: dict[tuple[str, str, str], int]
    triggered: dict[tuple[str, str, str], int]
    cells_scored: dict[str, int]
    cells_by_line: dict[str, set[int]]
    scoring_days: dict[str, list[int]]
    cuts: dict[tuple[str, str, int], Cuts]
    counters: dict[str, int]


def walk_forward(episodes: Sequence[Episode], cells: Sequence[S8.Cell8],
                 explore_days: Mapping[str, Sequence[int]],
                 plane: CertPlane, shares: Mapping[int, np.ndarray],
                 preds: Mapping[tuple[int, int], float],
                 size_cuts: Mapping[tuple[str, int], float],
                 certifiable: Mapping[tuple[str, str, int], int],
                 mutant: str = "") -> Run:
    """Score each day with thresholds built only from strictly prior days."""

    by_cell = {cell.position: cell for cell in cells}
    by_key: dict[tuple[str, str, int], list[Episode]] = {}
    for ep in episodes:
        by_key.setdefault((ep.asset, ep.phase, ep.d8), []).append(ep)
    for value in by_key.values():
        value.sort(key=lambda e: (e.arm_bar, -e.side))

    flow_by: dict[tuple[str, str, int], list[float]] = {}
    trend_by: dict[tuple[str, str, int], list[float]] = {}
    for cell in cells:
        key = (cell.asset, cell.phase, cell.d8)
        share = shares.get(cell.position)
        if share is not None:
            trend_by.setdefault(key, []).extend(
                float(v) for v in share if np.isfinite(v))

    fills: dict[str, list[Fill]] = {line_key(l, v): [] for l in LANES
                                    for v in VARIANTS}
    armed: dict[tuple[str, str, str], int] = {}
    triggered: dict[tuple[str, str, str], int] = {}
    cells_scored: dict[str, int] = {asset: 0 for asset in ASSETS}
    cells_by_line: dict[str, set[int]] = {key: set() for key in fills}
    scoring_days: dict[str, list[int]] = {asset: [] for asset in ASSETS}
    cuts_out: dict[tuple[str, str, int], Cuts] = {}
    counters = {"episodes_seen": 0, "no_cuts": 0, "illegal_entry": 0,
                "unscored_days": 0}

    for asset in ASSETS:
        days = sorted(int(day) for day in explore_days[asset])
        phases = sorted({cell.phase for cell in cells if cell.asset == asset})
        for index, d8 in enumerate(days):
            train_days = S14.fold_days(days, index, "")
            if len(train_days) < MIN_PRIOR_DAYS:
                counters["unscored_days"] += 1
                continue
            scoring_days[asset].append(d8)
            size_cut = size_cuts.get((asset, d8), float("nan"))
            # The coverage denominator is the plane's own: CERTIFIABLE cells on
            # scoring days, the same object sweep 9 calibrated its selective
            # bar against.  Counting every cell record would quietly inflate
            # coverage with cells the plane never admitted.
            cells_scored[asset] += sum(
                int(certifiable.get((asset, phase, d8), 0)) for phase in phases)
            for phase in phases:
                train: list[Episode] = []
                flow_pool: list[float] = []
                trend_pool: list[float] = []
                for day in train_days:
                    train.extend(by_key.get((asset, phase, day), []))
                    trend_pool.extend(trend_by.get((asset, phase, day), []))
                for ep in train:
                    flow_pool.extend(float(v) for v in ep.neg if np.isfinite(v))
                cuts = stratum_cuts(train, flow_pool, trend_pool)
                today = by_key.get((asset, phase, d8), [])
                if cuts is None:
                    counters["no_cuts"] += len(today)
                    continue
                cuts.size_cut = float(size_cut)
                cuts_out[(asset, phase, d8)] = cuts
                taken: set[tuple[str, int, int]] = set()
                for ep in today:
                    counters["episodes_seen"] += 1
                    share = shares.get(ep.cell)
                    magnitude = preds.get((ep.cell, ep.arm_bar), float("nan"))
                    size_ok = bool(np.isfinite(magnitude)
                                   and np.isfinite(cuts.size_cut)
                                   and magnitude >= cuts.size_cut)
                    for lane in LANES:
                        armed[(lane, asset, ep.phase)] = armed.get(
                            (lane, asset, ep.phase), 0) + 1
                        if lane == "SLOW":
                            trig = slow_trigger(ep.rel, cuts.d_cut, cuts.b_cut,
                                                mutant, ep.rel_full)
                        else:
                            trig = fast_trigger(ep.rel, ep.neg, cuts.d_cut,
                                                cuts.speed_cut, cuts.window,
                                                cuts.flow_hi, cuts.flow_lo)
                        if trig is None:
                            continue
                        triggered[(lane, asset, ep.phase)] = triggered.get(
                            (lane, asset, ep.phase), 0) + 1
                        bar = ep.arm_bar + trig.offset
                        value = plane.value(ep.cell, ep.side, bar)
                        if not np.isfinite(value):
                            counters["illegal_entry"] += 1
                            continue
                        trend_value = (float(share[bar]) if share is not None
                                       and bar < len(share) else float("nan"))
                        trend_ok = bool(np.isfinite(trend_value)
                                        and np.isfinite(cuts.trend_cut)
                                        and trend_value >= cuts.trend_cut)
                        # Post-entry excursion is a MEASUREMENT, not an input,
                        # so it reads the whole path after the entry - the
                        # untruncated one.  Measuring it on the breach-
                        # truncated array would make "retraced through the
                        # extreme" false by construction, since the truncation
                        # is exactly the retrace.
                        rest = ep.rel_full[trig.offset:]
                        floor = float(np.min(rest)) if len(rest) else float("nan")
                        adverse = (float(ep.rel_full[trig.offset]) - floor
                                   if np.isfinite(floor) else float("nan"))
                        retraced = bool(np.isfinite(floor) and floor < 0.0)
                        row = plane.index[ep.cell]
                        for variant in VARIANTS:
                            if not _gates_pass(variant, trend_ok, size_ok):
                                continue
                            # At most one entry per (cell, side) per LINE: the
                            # first trigger that passes that line's gates.  The
                            # lane belongs in the key or the slow lane would
                            # silently spend the fast lane's cell.
                            slot = (lane, variant, ep.cell, ep.side)
                            if slot in taken:
                                continue
                            taken.add(slot)
                            key = line_key(lane, variant)
                            fills[key].append(Fill(
                                lane=lane, variant=variant, asset=asset, d8=d8,
                                phase=ep.phase, cell=ep.cell, side=ep.side,
                                bar=bar, arm_bar=ep.arm_bar, level=ep.level,
                                cert_usd=value,
                                wall=bool(plane.wall[row, 0 if ep.side > 0
                                                     else 1, bar]),
                                ts_ns=int(plane.stamp[row, bar]),
                                adverse_atr=adverse, retraced=retraced,
                                disp_rel=trig.disp_rel, speed=trig.speed,
                                lane_offset=int(trig.offset),
                                payoff_at_arm=ep.payoff_at_arm))
                            cells_by_line[key].add(ep.cell)
    return Run(fills=fills, armed=armed, triggered=triggered,
               cells_scored=cells_scored, cells_by_line=cells_by_line,
               scoring_days=scoring_days, cuts=cuts_out, counters=counters)


# --------------------------------------------------------------------------
# Measurement.
# --------------------------------------------------------------------------

def _drawdown(values: Sequence[float]) -> float:
    peak = 0.0
    equity = 0.0
    worst = 0.0
    for value in values:
        equity += float(value)
        peak = max(peak, equity)
        worst = min(worst, equity - peak)
    return float(-worst)


def measure_line(rows: Sequence[Fill], asset: str, armed: int, triggered: int,
                 cells_seen: int, scoring_days: int,
                 covered: int) -> dict[str, object]:
    mine = [row for row in rows if row.asset == asset]
    certs = np.asarray([row.cert_usd for row in mine], np.float64)
    days = max(1, int(scoring_days))
    ordered = sorted(mine, key=lambda r: (r.ts_ns, r.cell, r.side))
    sums: dict[int, float] = {}
    for row in ordered:
        sums[row.d8] = sums.get(row.d8, 0.0) + row.cert_usd
    adverse = np.asarray([row.adverse_atr for row in mine], np.float64)
    return {
        "asset": asset,
        "entries": int(len(mine)),
        "armed_episodes": int(armed),
        "triggered_episodes": int(triggered),
        # An armed episode that never triggers is one whose retest never held
        # (or was breached first); an episode that triggered but did not fill
        # was suppressed by the one-entry-per-(cell, side) rule or a gate.
        "never_triggered": int(max(0, armed - triggered)),
        "trigger_rate": (float(triggered) / float(armed)) if armed else None,
        "fill_rate_of_triggers": ((float(len(mine)) / float(triggered))
                                  if triggered else None),
        "cells_covered": int(covered),
        "cells_scored": int(cells_seen),
        "coverage": (float(covered) / float(cells_seen)) if cells_seen else None,
        "p_cert_positive": _rate(float((certs > 0).sum()) if len(certs) else 0.0,
                                 float(len(certs))),
        "mean_cert_usd": float(certs.mean()) if len(certs) else None,
        "median_cert_usd": float(np.median(certs)) if len(certs) else None,
        "total_usd": float(certs.sum()) if len(certs) else 0.0,
        "usd_per_asset_day": (float(certs.sum()) / days) if len(certs) else 0.0,
        "rung_usd": S1.DAY_RUNG_USD[asset],
        "over_rung": ((float(certs.sum()) / days) / S1.DAY_RUNG_USD[asset]
                      if len(certs) else 0.0),
        "mdd_day_usd": _drawdown(sums[key] for key in sorted(sums)),
        "mdd_trade_usd": _drawdown(row.cert_usd for row in ordered),
        "wall_rate": (float(np.mean([row.wall for row in mine]))
                      if mine else None),
        "mean_adverse_excursion_atr": (float(np.nanmean(adverse))
                                       if len(adverse)
                                       and np.isfinite(adverse).any() else None),
        "share_retraced_through_extreme": (
            float(np.mean([row.retraced for row in mine])) if mine else None),
        "median_trigger_offset_bars": (
            float(np.median([row.lane_offset for row in mine])) if mine else None),
        "median_entry_bar": (float(np.median([row.bar for row in mine]))
                             if mine else None),
    }


def measure(run: Run) -> dict[str, object]:
    out: dict[str, object] = {}
    for lane in LANES:
        for variant in VARIANTS:
            key = line_key(lane, variant)
            rows = run.fills[key]
            block: dict[str, object] = {}
            for asset in ASSETS:
                armed = sum(count for (l, a, _p), count in run.armed.items()
                            if l == lane and a == asset)
                fired = sum(count for (l, a, _p), count in run.triggered.items()
                            if l == lane and a == asset)
                covered = len({row.cell for row in rows if row.asset == asset})
                block[asset] = measure_line(
                    rows, asset, armed, fired, run.cells_scored.get(asset, 0),
                    len(run.scoring_days.get(asset, [])), covered)
            out[key] = block
    return out


# --------------------------------------------------------------------------
# Controls.
# --------------------------------------------------------------------------

def _usd_per_day(values: np.ndarray, days: int) -> float:
    finite = values[np.isfinite(values)]
    return float(finite.sum()) / max(1, int(days))


def control_lateness(rows: Sequence[Fill], asset: str, plane: CertPlane,
                     days: int, rng: np.random.Generator,
                     draws: int = CONTROL_DRAWS) -> dict[str, object]:
    """C1: same cells, same side, stamps drawn from the trigger-time law."""

    mine = [row for row in rows if row.asset == asset]
    if not mine:
        return {"draws": 0, "n": 0}
    offsets = np.asarray([row.bar for row in mine], np.int64)
    positions = np.asarray([plane.index[row.cell] for row in mine], np.int64)
    columns = np.asarray([0 if row.side > 0 else 1 for row in mine], np.int64)
    limits = plane.bars[positions]
    picks = rng.integers(0, len(offsets), size=(draws, len(offsets)))
    sampled = offsets[picks]
    sampled = np.minimum(sampled, (limits - 2)[None, :])
    sampled = np.maximum(sampled, 1)
    values = plane.cert[positions[None, :], columns[None, :], sampled]
    per_draw = np.nansum(values, axis=1) / max(1, int(days))
    observed = _usd_per_day(
        np.asarray([row.cert_usd for row in mine], np.float64), days)
    return {
        "draws": int(draws), "n": int(len(mine)),
        "observed_usd_day": observed,
        "null_mean_usd_day": float(per_draw.mean()),
        "null_p95_usd_day": float(np.percentile(per_draw, 95)),
        "p_value": float((1 + int(np.sum(per_draw >= observed))) / (1 + draws)),
        "beats": bool(observed > float(np.percentile(per_draw, 95))),
    }


def control_old_frame(rows: Sequence[Fill], asset: str, plane: CertPlane,
                      days: int) -> dict[str, object]:
    """C2: the old frame - fade at the original occurrence stamp."""

    mine = [row for row in rows if row.asset == asset]
    if not mine:
        return {"n": 0}
    values = np.asarray([plane.value(row.cell, row.side, row.arm_bar)
                         for row in mine], np.float64)
    observed = _usd_per_day(
        np.asarray([row.cert_usd for row in mine], np.float64), days)
    old = _usd_per_day(values, days)
    return {
        "n": int(len(mine)), "priced": int(np.isfinite(values).sum()),
        "observed_usd_day": observed, "old_frame_usd_day": old,
        "delta_usd_day": observed - old,
        "beats": bool(observed > old),
    }


def control_fixed_clock(rows: Sequence[Fill], asset: str, plane: CertPlane,
                        days: int) -> dict[str, object]:
    """C3: same side at the per-asset median trigger offset, no structure."""

    mine = [row for row in rows if row.asset == asset]
    if not mine:
        return {"n": 0}
    at = int(round(float(np.median([row.bar for row in mine]))))
    values: list[float] = []
    for row in mine:
        limit = int(plane.bars[plane.index[row.cell]])
        bar = min(max(at, 1), limit - 2)
        values.append(plane.value(row.cell, row.side, bar))
    array = np.asarray(values, np.float64)
    observed = _usd_per_day(
        np.asarray([row.cert_usd for row in mine], np.float64), days)
    clock = _usd_per_day(array, days)
    return {
        "n": int(len(mine)), "median_offset_bars": at,
        "priced": int(np.isfinite(array).sum()),
        "observed_usd_day": observed, "fixed_clock_usd_day": clock,
        "delta_usd_day": observed - clock, "beats": bool(observed > clock),
    }


def block_permutation(run: Run, cells: Sequence[S8.Cell8], plane: CertPlane,
                      draws: int = NULL_DRAWS, seed: int = SEED
                      ) -> dict[str, object]:
    """C4: asset-day blocks permuted within asset, max-stat over every line.

    Sweep 1's ``block_null`` permutes day LABELS, which is total-preserving and
    therefore cannot move usd/day - it is an MDD null.  The headline here IS
    usd/day, so the block permutation has to move cash: each entry is re-priced
    at the same bar offset in the permuted day's cell of the same stratum.  The
    structure's timing law and the day denominators survive; the link between
    the structure and the day it found does not.
    """

    # POSTABLE[asset][phase_index, day_index] -> the row of the cert plane for
    # that stratum on that day, or -1 where the day has no such cell.  With it
    # a whole draw is array indexing, so 2000 of them cost seconds.
    day_list = {asset: sorted(run.scoring_days.get(asset, [])) for asset in ASSETS}
    day_pos = {asset: {int(d): i for i, d in enumerate(day_list[asset])}
               for asset in ASSETS}
    phase_names = sorted({cell.phase for cell in cells})
    phase_pos = {name: i for i, name in enumerate(phase_names)}
    postable: dict[str, np.ndarray] = {
        asset: np.full((len(phase_names), max(1, len(day_list[asset]))), -1,
                       np.int64) for asset in ASSETS}
    for cell in cells:
        column = day_pos[cell.asset].get(int(cell.d8))
        if column is None:
            continue
        postable[cell.asset][phase_pos[cell.phase], column] = plane.index[
            cell.position]

    rng = np.random.default_rng(seed)
    names: list[str] = []
    observed: dict[str, float] = {}
    payload: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray,
                             str, int]] = {}
    for lane in LANES:
        for variant in VARIANTS:
            key = line_key(lane, variant)
            for asset in ASSETS:
                rows = [r for r in run.fills[key] if r.asset == asset]
                if not rows:
                    continue
                name = f"{key}/{asset}"
                names.append(name)
                days = max(1, len(run.scoring_days.get(asset, [])))
                observed[name] = _usd_per_day(
                    np.asarray([r.cert_usd for r in rows], np.float64), days)
                payload[name] = (
                    np.asarray([r.bar for r in rows], np.int64),
                    np.asarray([0 if r.side > 0 else 1 for r in rows], np.int64),
                    np.asarray([day_pos[asset].get(int(r.d8), 0) for r in rows],
                               np.int64),
                    np.asarray([phase_pos[r.phase] for r in rows], np.int64),
                    asset, days)
    if not names:
        return {"draws": 0, "lines": 0, "by_line": {}}
    null_by: dict[str, list[float]] = {name: [] for name in names}
    null_max: list[float] = []
    for _draw in range(draws):
        perm = {asset: rng.permutation(max(1, len(day_list[asset])))
                for asset in ASSETS}
        best = -float("inf")
        for name in names:
            bars, columns, day_idx, phase_idx, asset, days = payload[name]
            target = perm[asset][day_idx]
            rowid = postable[asset][phase_idx, target]
            good = rowid >= 0
            got = np.full(len(bars), np.nan, np.float64)
            if good.any():
                rows_ok = rowid[good]
                limit = plane.bars[rows_ok]
                use = np.clip(bars[good], 1, np.maximum(limit - 2, 1))
                got[good] = plane.cert[rows_ok, columns[good], use]
            value = _usd_per_day(got, days)
            null_by[name].append(value)
            best = max(best, value)
        null_max.append(best)
    top = np.asarray(null_max, np.float64)
    out: dict[str, object] = {"draws": int(draws), "lines": len(names),
                              "statistic": "usd_per_asset_day", "by_line": {}}
    for name in names:
        own = np.asarray(null_by[name], np.float64)
        seen = observed[name]
        out["by_line"][name] = {
            "observed_usd_day": seen,
            "null_mean_usd_day": float(own.mean()),
            "null_p95_usd_day": float(np.percentile(own, 95)),
            "p_own": float((1 + int(np.sum(own >= seen))) / (1 + draws)),
            "p_max_adjusted": float((1 + int(np.sum(top >= seen))) / (1 + draws)),
        }
    return out


def controls(run: Run, plane: CertPlane, cells: Sequence[S8.Cell8]
             ) -> dict[str, object]:
    rng = np.random.default_rng(SEED)
    out: dict[str, object] = {"C1_lateness": {}, "C2_old_frame": {},
                              "C3_fixed_clock": {}}
    for lane in LANES:
        for variant in VARIANTS:
            key = line_key(lane, variant)
            rows = run.fills[key]
            for asset in ASSETS:
                days = max(1, len(run.scoring_days.get(asset, [])))
                name = f"{key}/{asset}"
                out["C1_lateness"][name] = control_lateness(
                    rows, asset, plane, days, rng)
                out["C2_old_frame"][name] = control_old_frame(
                    rows, asset, plane, days)
                out["C3_fixed_clock"][name] = control_fixed_clock(
                    rows, asset, plane, days)
    out["C4_block_permutation"] = block_permutation(run, cells, plane)
    return out


# --------------------------------------------------------------------------
# The pre-registered decision table.
# --------------------------------------------------------------------------

def decide(report: Mapping[str, object], control: Mapping[str, object]
           ) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    live: list[str] = []
    partial: list[str] = []
    powered = False
    for lane in LANES:
        for variant in VARIANTS:
            key = line_key(lane, variant)
            for asset in ASSETS:
                block = report[key][asset]              # type: ignore[index]
                name = f"{key}/{asset}"
                c1 = control["C1_lateness"].get(name, {})   # type: ignore[index]
                c2 = control["C2_old_frame"].get(name, {})  # type: ignore[index]
                c3 = control["C3_fixed_clock"].get(name, {})  # type: ignore[index]
                c4 = control["C4_block_permutation"]["by_line"].get(  # type: ignore[index]
                    name, {})
                entries = int(block["entries"])
                usd = float(block["usd_per_asset_day"])
                coverage = block["coverage"]
                p_adj = c4.get("p_max_adjusted")
                beats_c1 = bool(c1.get("beats", False))
                beats_c2 = bool(c2.get("beats", False))
                deciding = asset in DECIDING
                if deciding and entries >= POWER_FLOOR:
                    powered = True
                positive = usd > 0.0
                cover_ok = bool(coverage is not None
                                and coverage >= COVERAGE_FLOOR)
                null_ok = bool(p_adj is not None and p_adj <= NULL_CEILING)
                # The first pre-registered bound this line failed, in the order
                # the letter tests them.  A line that clears every bound has
                # none, and is CONT-LIVE.
                if not deciding:
                    failed = "report-only asset"
                elif entries < POWER_FLOOR:
                    failed = f"entries {entries} < {POWER_FLOOR}"
                elif not positive:
                    failed = f"usd/day {usd:.1f} <= 0"
                elif not beats_c1:
                    failed = "does not beat C1 lateness"
                elif not beats_c2:
                    failed = "does not beat C2 old frame"
                elif not cover_ok:
                    failed = f"coverage {coverage} < {COVERAGE_FLOOR}"
                elif not null_ok:
                    failed = (f"adjusted p {p_adj} > {NULL_CEILING}"
                              if p_adj is not None else "no adjusted p")
                else:
                    failed = ""
                verdict = "-"
                if deciding and positive:
                    if beats_c1 and beats_c2 and null_ok and cover_ok:
                        verdict = "CONT-LIVE"
                        live.append(name)
                    elif beats_c1 or beats_c2:
                        verdict = "CONT-PARTIAL"
                        partial.append(name)
                rows.append({
                    "line": name, "lane": lane, "variant": variant,
                    "asset": asset, "deciding": deciding, "entries": entries,
                    "armed": int(block["armed_episodes"]),
                    "trigger_rate": block["trigger_rate"],
                    "coverage": coverage, "usd_per_asset_day": usd,
                    "over_rung": block["over_rung"],
                    "mdd_day_usd": block["mdd_day_usd"],
                    "mdd_trade_usd": block["mdd_trade_usd"],
                    "p_cert_positive": block["p_cert_positive"]["rate"],
                    "wall_rate": block["wall_rate"],
                    "median_offset_bars": block["median_trigger_offset_bars"],
                    "adverse_atr": block["mean_adverse_excursion_atr"],
                    "retraced": block["share_retraced_through_extreme"],
                    "c1_null_p95": c1.get("null_p95_usd_day"),
                    "c1_p": c1.get("p_value"), "beats_c1": beats_c1,
                    "c2_usd_day": c2.get("old_frame_usd_day"),
                    "beats_c2": beats_c2,
                    "c3_usd_day": c3.get("fixed_clock_usd_day"),
                    "beats_c3": bool(c3.get("beats", False)),
                    "p_adj": p_adj, "verdict": verdict,
                    "failed_bound": failed,
                })
    if not powered:
        letter = "UNPOWERED"
    elif live:
        letter = "CONT-LIVE"
    elif partial:
        letter = "CONT-PARTIAL"
    else:
        letter = "NONE"
    best = max(rows, key=lambda r: (r["deciding"], r["usd_per_asset_day"]))
    return {"letter": letter, "live_lines": live, "partial_lines": partial,
            "powered": powered, "rows": rows, "best_line": best,
            "bounds": {"coverage_floor": COVERAGE_FLOOR,
                       "power_floor": POWER_FLOOR,
                       "null_ceiling": NULL_CEILING}}


# --------------------------------------------------------------------------
# Printing.
# --------------------------------------------------------------------------

def _n(value: object, width: int = 9, digits: int = 3) -> str:
    if value is None:
        return "-".rjust(width)
    if isinstance(value, bool):
        return ("Y" if value else "n").rjust(width)
    if isinstance(value, float):
        if not math.isfinite(value):
            return "nan".rjust(width)
        return f"{value:{width}.{digits}f}"
    return str(value).rjust(width)


def print_repro(block: Mapping[str, object]) -> None:
    print("\nREPRODUCTION GATE - sweep 9's occurrence plane")
    print(f"  rows          banked {block['banked_rows']:>8}  "
          f"live {block['live_rows']:>8}")
    for name in sorted(block["banked_counters"]):          # type: ignore[index]
        print(f"  {name:<20s} banked {block['banked_counters'][name]:>8}  "  # type: ignore[index]
              f"live {block['live_counters'][name]:>8}")   # type: ignore[index]
    for asset in ASSETS:
        print(f"  certifiable {asset:<8s} banked "
              f"{block['banked_certifiable'][asset]:>8}  "   # type: ignore[index]
              f"live {block['live_certifiable'][asset]:>8}")  # type: ignore[index]
    for asset in ASSETS:
        print(f"  scoring days {asset:<7s} banked "
              f"{block['banked_scoring_days'][asset]:>8}  "   # type: ignore[index]
              f"live {block['live_scoring_days'][asset]:>8}")  # type: ignore[index]
    print(f"  MATCHES: {block['matches']}")


def print_measures(report: Mapping[str, object]) -> None:
    print("\nMEASUREMENTS - per lane x variant x asset, scoring days only")
    head = (f"{'line':<22s}{'asset':>5s}{'entr':>6s}{'armed':>7s}"
            f"{'trig':>7s}{'cover':>7s}{'P(+)':>7s}{'wall':>6s}{'mean':>9s}"
            f"{'median':>9s}{'usd/day':>10s}{'mddD':>9s}{'mddT':>9s}"
            f"{'late':>6s}{'advATR':>8s}{'retr':>7s}")
    print(head)
    print("-" * len(head))
    for lane in LANES:
        for variant in VARIANTS:
            key = line_key(lane, variant)
            for asset in ASSETS:
                b = report[key][asset]                      # type: ignore[index]
                print(f"{key:<22s}{asset:>5s}{b['entries']:>6d}"
                      f"{b['armed_episodes']:>7d}"
                      f"{_n(b['trigger_rate'], 7)}"
                      f"{_n(b['coverage'], 7)}"
                      f"{_n(b['p_cert_positive']['rate'], 7)}"
                      f"{_n(b['wall_rate'], 6, 2)}"
                      f"{_n(b['mean_cert_usd'], 9, 1)}"
                      f"{_n(b['median_cert_usd'], 9, 1)}"
                      f"{_n(b['usd_per_asset_day'], 10, 1)}"
                      f"{_n(b['mdd_day_usd'], 9, 1)}"
                      f"{_n(b['mdd_trade_usd'], 9, 1)}"
                      f"{_n(b['median_trigger_offset_bars'], 6, 0)}"
                      f"{_n(b['mean_adverse_excursion_atr'], 8)}"
                      f"{_n(b['share_retraced_through_extreme'], 7)}")


def print_controls(control: Mapping[str, object]) -> None:
    print("\nCONTROLS - C1 lateness-matched, C2 old frame, C3 fixed clock")
    head = (f"{'line':<27s}{'n':>5s}{'obs/day':>10s}{'C1p95':>10s}"
            f"{'C1 p':>8s}{'>C1':>5s}{'C2/day':>10s}{'>C2':>5s}"
            f"{'C3/day':>10s}{'>C3':>5s}")
    print(head)
    print("-" * len(head))
    for name in sorted(control["C1_lateness"]):             # type: ignore[index]
        c1 = control["C1_lateness"][name]                   # type: ignore[index]
        c2 = control["C2_old_frame"][name]                  # type: ignore[index]
        c3 = control["C3_fixed_clock"][name]                # type: ignore[index]
        if not c1.get("n"):
            continue
        print(f"{name:<27s}{c1['n']:>5d}"
              f"{_n(c1.get('observed_usd_day'), 10, 1)}"
              f"{_n(c1.get('null_p95_usd_day'), 10, 1)}"
              f"{_n(c1.get('p_value'), 8)}"
              f"{_n(c1.get('beats'), 5)}"
              f"{_n(c2.get('old_frame_usd_day'), 10, 1)}"
              f"{_n(c2.get('beats'), 5)}"
              f"{_n(c3.get('fixed_clock_usd_day'), 10, 1)}"
              f"{_n(c3.get('beats'), 5)}")
    null = control["C4_block_permutation"]                  # type: ignore[index]
    print(f"\nC4 block permutation - {null['draws']} draws, "        # type: ignore[index]
          f"{null['lines']} lines, max-stat over lanes x variants x assets")
    head2 = (f"{'line':<27s}{'obs/day':>10s}{'null mean':>11s}"
             f"{'null p95':>11s}{'p own':>8s}{'p adj':>8s}")
    print(head2)
    print("-" * len(head2))
    for name in sorted(null["by_line"]):                    # type: ignore[index]
        row = null["by_line"][name]                         # type: ignore[index]
        print(f"{name:<27s}{_n(row['observed_usd_day'], 10, 1)}"
              f"{_n(row['null_mean_usd_day'], 11, 1)}"
              f"{_n(row['null_p95_usd_day'], 11, 1)}"
              f"{_n(row['p_own'], 8)}{_n(row['p_max_adjusted'], 8)}")


def print_decision(block: Mapping[str, object]) -> None:
    print("\nDECISION TABLE - pre-registered, every line")
    head = (f"{'line':<27s}{'dec':>4s}{'entr':>6s}{'armed':>7s}"
            f"{'cover':>7s}{'usd/day':>10s}{'/rung':>8s}{'mddD':>9s}"
            f"{'>C1':>5s}{'>C2':>5s}{'>C3':>5s}{'p adj':>8s}{'verdict':>14s}"
            f"   {'first bound failed':<28s}")
    print(head)
    print("-" * len(head))
    for row in block["rows"]:                               # type: ignore[index]
        print(f"{row['line']:<27s}{'Y' if row['deciding'] else 'n':>4s}"
              f"{row['entries']:>6d}{row['armed']:>7d}"
              f"{_n(row['coverage'], 7)}"
              f"{_n(row['usd_per_asset_day'], 10, 1)}"
              f"{_n(row['over_rung'], 8)}"
              f"{_n(row['mdd_day_usd'], 9, 1)}"
              f"{_n(row['beats_c1'], 5)}{_n(row['beats_c2'], 5)}"
              f"{_n(row['beats_c3'], 5)}{_n(row['p_adj'], 8)}"
              f"{row['verdict']:>14s}   {row['failed_bound']:<28s}")
    bounds = block["bounds"]                                # type: ignore[index]
    print(f"\nbounds: coverage >= {bounds['coverage_floor']}, "      # type: ignore[index]
          f"entries >= {bounds['power_floor']} on a deciding asset, "  # type: ignore[index]
          f"adjusted p <= {bounds['null_ceiling']}")        # type: ignore[index]
    print(f"LETTER: {block['letter']}   live {block['live_lines'] or '-'}   "
          f"partial {block['partial_lines'] or '-'}")


# --------------------------------------------------------------------------
# Selftest and the red mutant.
# --------------------------------------------------------------------------

def _check(name: str, ok: bool, detail: str = "") -> tuple[str, bool, str]:
    return (name, bool(ok), detail)


def _planted(kind: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``(rel truncated at breach, rel untruncated, neg)`` per planted case.

    The paths are hand-built in ATR units so every expected bar and every
    expected cert below is arithmetic a reader can redo on paper.
    """

    if kind == "continuation":
        # Arm at the level; displace to 1.20 ATR by bar 4; drift back and
        # retest to 0.10 ATR at bar 8; bar 9 does NOT turn (0.05, still
        # sagging); bar 10 turns up to 0.40 and runs to 2.00.  Bar 9 is the
        # bar that separates the clean law from the mutant: the clean law
        # waits for bar 10 to close, the mutant enters at bar 9 on bar 10's
        # value.
        full = np.array([0.00, 0.30, 0.60, 0.90, 1.20, 0.90, 0.60, 0.30, 0.10,
                         0.05, 0.40, 0.90, 1.50, 2.00], np.float64)
        return full, full, np.zeros(len(full), np.float64)
    if kind == "breach":
        # Identical through the retest, but bar 9 trades THROUGH the level.
        # The episode truncates there, so the clean law can never confirm;
        # the mutant reads across the breach and enters anyway.
        full = np.array([0.00, 0.30, 0.60, 0.90, 1.20, 0.90, 0.60, 0.30, 0.10,
                         -0.05, 0.40, 0.90], np.float64)
        rel = full[:9]
        return rel, full, np.zeros(len(full), np.float64)
    if kind == "fast":
        # 1.30 ATR in two bars, a real counter-attack at bar 3 that is gone by
        # bar 4 while the displacement is held.
        full = np.array([0.00, 0.70, 1.30, 1.32, 1.40, 1.60], np.float64)
        neg = np.array([0.0, 1.0, 2.0, 90.0, 0.0, 0.0], np.float64)
        return full, full, neg
    raise SweepRefusal(f"unknown planted case {kind!r}")


def _selftest_lanes(mutant: str) -> list[tuple[str, bool, str]]:
    """The planted cases, asserted identically whatever the mutant does.

    Nothing here is relaxed under the mutant: these are the assertions the
    mutant has to break, so they are stated once and only once.
    """

    out: list[tuple[str, bool, str]] = []
    rel, full, _neg = _planted("continuation")
    trig = slow_trigger(rel, 1.0, 0.2, mutant, full)
    out.append(_check("slow/planted_enters", trig is not None
                      and trig.offset == 10,
                      f"offset {getattr(trig, 'offset', None)}, want 10 "
                      f"(bar 9 sags to 0.05 and does NOT confirm)"))
    out.append(_check("slow/displacement_bar", trig is not None
                      and trig.disp_offset == 4,
                      f"disp {getattr(trig, 'disp_offset', None)}, want 4"))
    out.append(_check("slow/retest_bar", trig is not None
                      and trig.retest_offset == 8,
                      f"retest {getattr(trig, 'retest_offset', None)}, want 8"))
    rel_b, full_b, _ = _planted("breach")
    trig_b = slow_trigger(rel_b, 1.0, 0.2, mutant, full_b)
    out.append(_check("slow/breach_never_enters", trig_b is None,
                      f"got offset {getattr(trig_b, 'offset', None)}; the "
                      f"retest traded through the level at bar 9"))
    rel_f, full_f, neg_f = _planted("fast")
    trig_f = fast_trigger(rel_f, neg_f, 1.0, 0.5, 3, 50.0, 1.0)
    out.append(_check("fast/planted_enters", trig_f is not None
                      and trig_f.offset == 4,
                      f"offset {getattr(trig_f, 'offset', None)}, want 4"))
    out.append(_check("fast/no_retest_needed", trig_f is not None
                      and trig_f.retest_offset == -1, "retest slot is empty"))
    slow_on_fast = slow_trigger(rel_f, 1.0, 0.2, mutant, full_f)
    out.append(_check("fast/slow_lane_declines_it", slow_on_fast is None,
                      "the fast path never returns to the band"))
    return out


def _selftest_causality(mutant: str) -> list[tuple[str, bool, str]]:
    """The confirming bar must close strictly before the entry stamp."""

    out: list[tuple[str, bool, str]] = []
    rel, full, _ = _planted("continuation")
    trig = slow_trigger(rel, 1.0, 0.2, mutant, full)
    if trig is None:
        return [_check("causality/hold_bar_confirms", False, "no trigger")]
    # The bar the law entered on must itself have turned back: if it did not,
    # the confirmation came from a bar that had not closed at the entry stamp.
    turned = float(rel[trig.offset]) > float(rel[trig.retest_offset])
    out.append(_check("causality/hold_bar_precedes_entry",
                      trig.offset >= trig.retest_offset + 1,
                      f"hold {trig.offset} > retest {trig.retest_offset}"))
    out.append(_check("causality/confirming_bar_turned", turned,
                      f"rel[{trig.offset}]={rel[trig.offset]:.2f} > "
                      f"rel[{trig.retest_offset}]="
                      f"{rel[trig.retest_offset]:.2f}"))
    return out


PLANT_ASSET = "HG"
PLANT_USD_PER_ATR = 400.0
PLANT_LEVEL_MID2 = 4_500_000_000.0


def _planted_rec(kind: str, side: int = 1) -> tuple[S1.CellRec, np.ndarray, float]:
    """A real ``CellRec`` carrying a planted path, so the frozen law prices it.

    The ATR is chosen so one ATR is exactly ``PLANT_USD_PER_ATR`` USD under the
    mill's own scale, which makes every cert in this test a round hand number
    rather than an artefact of the tick size.
    """

    rel, full, _neg = _planted(kind)
    # The record spans the UNTRUNCATED path so a mutant entry past the breach
    # is priceable rather than silently dropped for want of a bar.
    n = len(full)
    scale = S7A.usd_to_mid2(PLANT_ASSET)
    atr = PLANT_USD_PER_ATR * scale
    mid = np.round(PLANT_LEVEL_MID2 + float(side) * full * atr).astype(np.int64)
    lat = (np.arange(n, dtype=np.int64) * S1.BAR_NS
           + 1_600_000_000_000_000_000)
    # The frozen to-close outcome with no cost: travel from the entry bar to
    # the cell's last bar, on the entered side, in USD.
    travel = (float(side) * (mid[-1] - mid)).astype(np.float64) / scale
    zeros = np.zeros(n, np.int64)
    rec = S1.CellRec(
        asset=PLANT_ASSET, d8=20220315, phase="0", text="PLANT",
        phase_open_ts_ns=int(lat[0]), phase_close_ts_ns=int(lat[-1]),
        locked_iid=0, pack_sha256="", raw_first=0, k0=0,
        r0_mid2=float(mid[0]), legal_from_p=1, legal_from_m=1,
        lat=lat, mid=mid, bar_ok=np.ones(n, bool), cost=np.zeros(n, np.float64),
        cert_p=travel, cert_m=-travel,
        ok_p=np.ones(n, bool), ok_m=np.ones(n, bool),
        wall_p=np.zeros(n, bool), wall_m=np.zeros(n, bool),
        exit_p=np.full(n, int(lat[-1]), np.int64),
        exit_m=np.full(n, int(lat[-1]), np.int64),
        cum_long=zeros, cum_short=zeros, raw_cut=zeros, raw_last=zeros)
    return rec, rel, full


def _selftest_cert(mutant: str) -> list[tuple[str, bool, str]]:
    """The planted continuation entered by the lane and priced hand-to-hand."""

    out: list[tuple[str, bool, str]] = []
    rec, rel, full = _planted_rec("continuation")
    trig = slow_trigger(rel, 1.0, 0.2, mutant, full)
    if trig is None:
        return [_check("cert/lane_entered", False, "no trigger at all")]
    entry = S1.make_entry(0, rec, trig.offset, 1)
    out.append(_check("cert/entry_is_legal", entry is not None,
                      f"bar {trig.offset}"))
    if entry is None:
        return out
    # Hand arithmetic, independent of the arrays above: the lane enters at bar
    # 10 (rel 0.40) and the cell closes at rel 2.00, so the frozen to-close
    # cert is (2.00 - 0.40) ATR = 1.60 ATR = 1.60 * 400 = 640.00 USD.
    want = (2.00 - 0.40) * PLANT_USD_PER_ATR
    out.append(_check("cert/entry_bar_is_the_hold_bar", entry.bar == 10,
                      f"bar {entry.bar}, want 10"))
    out.append(_check("cert/hand_computed_usd",
                      abs(entry.cert_usd - want) < 1e-6,
                      f"{entry.cert_usd:.2f} usd, hand {want:.2f} usd "
                      f"(1.60 ATR at {PLANT_USD_PER_ATR:.0f} usd/ATR)"))
    out.append(_check("cert/no_wall", entry.wall is False, "planted path is clean"))
    # The fast lane's planted path, priced the same way: enters at bar 4
    # (rel 1.40), closes at rel 1.60, so 0.20 ATR = 80.00 USD.
    rec_f, rel_f, _full_f = _planted_rec("fast")
    _rel, _full, neg_f = _planted("fast")
    trig_f = fast_trigger(rel_f, neg_f, 1.0, 0.5, 3, 50.0, 1.0)
    entry_f = (None if trig_f is None
               else S1.make_entry(0, rec_f, trig_f.offset, 1))
    want_f = (1.60 - 1.40) * PLANT_USD_PER_ATR
    out.append(_check("cert/fast_hand_computed_usd",
                      entry_f is not None
                      and abs(entry_f.cert_usd - want_f) < 1e-6,
                      f"{getattr(entry_f, 'cert_usd', float('nan')):.2f} usd, "
                      f"hand {want_f:.2f} usd (0.20 ATR)"))
    # The adverse excursion after entry, in ATR, back toward the extreme.
    rest = rel[trig.offset:]
    adverse = float(rel[trig.offset]) - float(np.min(rest))
    out.append(_check("cert/adverse_excursion_zero", abs(adverse) < 1e-12,
                      f"{adverse} - the planted path never gives any back"))
    out.append(_check("cert/no_retrace_through_extreme",
                      bool(np.min(rest) >= 0.0), f"min rel {float(np.min(rest))}"))
    return out


def _selftest_sweep7a_equivalence() -> list[tuple[str, bool, str]]:
    """This unit's touch/hold machine against sweep 7a's, at its own band.

    ``S7A.side_triggers`` is the sweep-7 era retest-hold law: armed -> touched
    -> departed, voided by a same-side new extreme.  Run this unit's scanner
    with sweep 7a's own band and no displacement gate and the two must find the
    same departures, or one of them is not the law it claims to be.
    """

    out: list[tuple[str, bool, str]] = []
    rng = np.random.default_rng(SEED)
    n = 240
    mid = 10000.0 + np.cumsum(rng.normal(0.0, 6.0, n))
    atr = 100.0
    half = S7A.ZONE_ATR_FRACTION * atr
    side = 1
    prior = np.concatenate([[mid[0]], np.minimum.accumulate(mid)[:-1]])
    new_ext = np.zeros(n, bool)
    new_ext[1:] = mid[1:] < prior[1:]
    # Take each distinct level, and check that "returns inside half, then a bar
    # outside half toward the interior, with no new extreme between" agrees
    # with the rel/band reading this unit uses.
    agree = 0
    checked = 0
    for bar in range(1, n - 2):
        if new_ext[bar]:
            continue
        level = float(prior[bar])
        rel = (side * (mid[bar:] - level)) / atr
        stop = _breach_offsets(rel, new_ext[bar:])
        rel = rel[:max(stop, 1)]
        if len(rel) < 4:
            continue
        band = half / atr
        theirs_touch = bool(abs(mid[bar] - level) <= half)
        ours_touch = bool(rel[0] <= band)
        checked += 1
        agree += int(theirs_touch == ours_touch)
    out.append(_check("sweep7a/band_reading_agrees", checked > 0
                      and agree == checked,
                      f"{agree}/{checked} bars agree that |mid-level| <= half "
                      f"is rel <= half/ATR"))
    out.append(_check("sweep7a/breach_is_new_extreme",
                      bool(np.all((mid[1:] < prior[1:]) == new_ext[1:])),
                      "a strictly adverse price IS a same-side new extreme"))
    out.append(_check("sweep7a/zone_constant_is_not_used",
                      Q_BAND != S7A.ZONE_ATR_FRACTION * 100.0,
                      "this unit's band is a train quantile, not 0.15 ATR"))
    return out


def _selftest_gates() -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []
    out.append(_check("gates/ungated_always", _gates_pass("ungated", False, False)))
    out.append(_check("gates/day_needs_trend",
                      _gates_pass("day", True, False)
                      and not _gates_pass("day", False, True)))
    out.append(_check("gates/size_needs_magnitude",
                      _gates_pass("size", False, True)
                      and not _gates_pass("size", True, False)))
    out.append(_check("gates/both_needs_both",
                      _gates_pass("both", True, True)
                      and not _gates_pass("both", True, False)
                      and not _gates_pass("both", False, True)))
    # Thresholds are train quantiles: a stratum with no training days has none.
    out.append(_check("cuts/no_train_no_cuts",
                      stratum_cuts([], [], []) is None,
                      "an unwarmed stratum refuses to trade"))
    return out


def _selftest_displacement() -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []
    rel = np.array([0.0, 0.5, 0.4, 1.1, 0.2], np.float64)
    out.append(_check("disp/first_reach", displacement_offset(rel, 1.0) == 3,
                      f"{displacement_offset(rel, 1.0)}"))
    out.append(_check("disp/never_reached",
                      displacement_offset(rel, 9.0) == -1,
                      f"{displacement_offset(rel, 9.0)}"))
    out.append(_check("disp/runmax_is_monotone",
                      bool(np.all(np.diff(np.maximum.accumulate(rel)) >= 0.0))))
    return out


def selftest() -> int:
    mutant = _mutant()
    checks: list[tuple[str, bool, str]] = []
    checks.extend(_selftest_lanes(mutant))
    checks.extend(_selftest_causality(mutant))
    checks.extend(_selftest_cert(mutant))
    checks.extend(_selftest_sweep7a_equivalence())
    checks.extend(_selftest_gates())
    checks.extend(_selftest_displacement())
    width = max(len(name) for name, _ok, _detail in checks)
    bad = 0
    print(f"sweep 19 selftest  mutant {mutant or 'none'}")
    for name, ok, detail in checks:
        bad += 0 if ok else 1
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<{width}s}  {detail}")
    print(f"{len(checks) - bad}/{len(checks)} checks passed")
    return 0 if bad == 0 else 1


# --------------------------------------------------------------------------
# The reproduction gate.
# --------------------------------------------------------------------------

def reproduce(plane: S9.Plane, scoring: Mapping[str, Sequence[int]]
              ) -> dict[str, object]:
    live_counters = {name: int(plane.counters[name])
                     for name in sorted(REPRO_COUNTERS)}
    live_cells = {asset: int(plane.certifiable.get(asset, 0)) for asset in ASSETS}
    live_days = {asset: len(scoring.get(asset, [])) for asset in ASSETS}
    return {"banked_counters": REPRO_COUNTERS, "live_counters": live_counters,
            "banked_certifiable": REPRO_CERTIFIABLE,
            "live_certifiable": live_cells,
            "banked_rows": REPRO_ROWS, "live_rows": int(plane.n),
            "banked_scoring_days": REPRO_SCORING_DAYS,
            "live_scoring_days": live_days,
            "matches": bool(live_counters == REPRO_COUNTERS
                            and live_cells == REPRO_CERTIFIABLE
                            and int(plane.n) == REPRO_ROWS
                            and live_days == REPRO_SCORING_DAYS)}


# --------------------------------------------------------------------------
# The log.
# --------------------------------------------------------------------------

def _show(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def log_rows(report: Mapping[str, object]) -> list[dict[str, object]]:
    stamp = report["registered_utc"]
    params = json.dumps({
        "q_displace": Q_DISPLACE, "q_band": Q_BAND, "q_speed": Q_SPEED,
        "q_flow": [Q_FLOW_HI, Q_FLOW_LO], "q_trend": Q_TREND, "q_size": Q_SIZE,
        "min_prior_days": MIN_PRIOR_DAYS, "min_fit_rows": MIN_FIT_ROWS,
        "control_draws": CONTROL_DRAWS, "null_draws": NULL_DRAWS,
        "coverage_floor": COVERAGE_FLOOR, "power_floor": POWER_FLOOR,
    }, sort_keys=True)
    shared = {
        "registered_utc": stamp, "family": FAMILY, "params": params,
        "spec_sha": report["spec_sha"], "code_sha": report["code_sha"],
        "split_sha": report["split_sha"],
        "outcome_law_sha": report["outcome_law_sha"],
        "null_seed": SEED, "parent_trial": PARENT_TRIAL,
        "selection_rule": SELECTION_RULE,
    }
    decision = report["decision"]
    rows: list[dict[str, object]] = []
    for index, row in enumerate(decision["rows"], start=1):  # type: ignore[index]
        asset = str(row["asset"])
        line = dict(shared)
        line["id"] = f"{LOG_PREFIX}-{index:03d}"
        line["rule"] = f"{row['lane']}/{row['variant']}/{asset}"
        line["days"] = len(report["scoring_days"][asset])   # type: ignore[index]
        line["coverage"] = row["coverage"]
        # How LATE the continuation entry is: the median bars from the arming
        # occurrence to the trigger, in seconds.  That lateness is the whole
        # cost the frame pays for waiting, so it belongs in the log's own
        # delay column rather than being left blank.
        offset = row.get("median_offset_bars")
        line["delay_med_s"] = (None if offset is None
                               else float(offset) * S1.BAR_SECONDS)
        for name in ("hg", "nkd", "si"):
            line[f"{name}_usd_day"] = None
            line[f"mdd_{name}"] = None
            line[f"walls_{name}"] = None
            line[f"err_rate_{name}"] = None
        tag = asset.lower()
        line[f"{tag}_usd_day"] = row["usd_per_asset_day"]
        line[f"mdd_{tag}"] = row["mdd_day_usd"]
        line["replay_skips"] = None
        line["null_margin"] = row["p_adj"]
        line["verdict"] = ""
        line["note"] = (
            f"{row['lane']} lane, {row['variant']} variant, {asset}: "
            f"entries {row['entries']} of {row['armed']} armed "
            f"(trigger {_show(row['trigger_rate'])}), coverage "
            f"{_show(row['coverage'])}, usd/day "
            f"{_show(row['usd_per_asset_day'])} = "
            f"{_show(row['over_rung'])} rung; beats C1 "
            f"{'Y' if row['beats_c1'] else 'n'} C2 "
            f"{'Y' if row['beats_c2'] else 'n'} C3 "
            f"{'Y' if row['beats_c3'] else 'n'}; p_adj {_show(row['p_adj'])}; "
            f"median lateness {_show(row['median_offset_bars'])} bars; "
            f"adverse {_show(row['adverse_atr'])} ATR, retraced through the "
            f"extreme {_show(row['retraced'])}; line verdict "
            f"{row['verdict'] or '-'}"
            f"{'' if not row['failed_bound'] else ' (' + row['failed_bound'] + ')'}"
            f"; family letter {decision['letter']}")        # type: ignore[index]
        rows.append(line)
    return rows


def write_report(report: Mapping[str, object]) -> None:
    OUT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True,
                                   default=S8._json_default) + "\n")


# --------------------------------------------------------------------------
# Entry point.
# --------------------------------------------------------------------------

def report_stamp() -> str:
    import datetime as dt
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def run(assets: Sequence[str] = ASSETS) -> dict[str, object]:
    mutant = _mutant()
    started = time.time()
    cells, days, _skipped = S8.build_cells(ASSETS)
    explore_days = S1._explore_days(ASSETS)
    tape = S9.load_tape(cells)
    forecast = S9.forecast_variance(cells)
    plane9 = S9.build_plane(cells, forecast, tape)
    scoring = {asset: sorted(int(d) for d in explore_days[asset])[MIN_PRIOR_DAYS:]
               for asset in ASSETS}
    repro = reproduce(plane9, scoring)
    if not repro["matches"]:
        raise SweepRefusal("sweep 9's occurrence plane did not reproduce; no "
                           "measurement is believed past this point")
    states = S12.day_states({asset: explore_days[asset] for asset in ASSETS})
    streams, stream_counters = S14.build_streams(plane9, cells, states, "")
    causal = S14.assert_causal(streams, plane9)
    if not causal["no_outcome_in_features"]:
        raise SweepRefusal("a feature reads the outcome it is choosing over")
    deltas, flow_counters = load_deltas(cells)
    episodes, ep_counters = build_episodes(streams, cells, deltas)
    shares = developing_share(cells)
    preds, size_cuts = magnitude_channel(streams, explore_days, scoring)
    cert_plane = build_cert_plane(cells)
    walk = walk_forward(episodes, cells, explore_days, cert_plane, shares,
                        preds, size_cuts, plane9.stratum_day_cells, mutant)
    report = measure(walk)
    control = controls(walk, cert_plane, cells)
    ruling = decide(report, control)
    return {
        "schema": "QRE2MILLSWEEP19", "spec_sha": SPEC_SHA,
        "code_sha": code_sha(), "split_sha": S1.split_sha(),
        "outcome_law_sha": S1.outcome_law_sha(), "seed": SEED,
        "mutant": mutant, "family": FAMILY, "parent_trial": PARENT_TRIAL,
        "selection_rule": SELECTION_RULE, "registered_utc": report_stamp(),
        "asset_days": {a: int(days.get(a, 0)) for a in ASSETS},
        "reproduction": repro, "stream_counters": stream_counters,
        "causality": causal, "flow_counters": flow_counters,
        "episode_counters": ep_counters, "run_counters": walk.counters,
        "scoring_days": {a: walk.scoring_days.get(a, []) for a in ASSETS},
        "cells_scored": walk.cells_scored,
        "measurements": report, "controls": control, "decision": ruling,
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
    ruling = report["decision"]
    best = ruling["best_line"]                              # type: ignore[index]
    print(f"sweep 19 {ruling['letter']}: best deciding line "  # type: ignore[index]
          f"{best['line']} at {best['usd_per_asset_day']:.1f} usd/day = "
          f"{best['over_rung']:.4f} of rung "
          f"{S1.DAY_RUNG_USD[best['asset']]:.0f}; spec_sha {SPEC_SHA[:16]} "
          f"code_sha {code_sha()[:16]} seed {SEED} "
          f"mutant {report['mutant'] or 'none'}")
    print_repro(report["reproduction"])
    print(f"\nstreams {report['stream_counters']['streams']} cells, "
          f"{report['stream_counters']['occs']} occurrences; episodes "
          f"{report['episode_counters']['episodes']} "
          f"(armed beyond level {report['episode_counters']['arm_beyond_level']}, "
          f"repeated levels {report['episode_counters']['levels_repeated']}); "
          f"flow cells missing {report['flow_counters']['missing_shard']}"
          f"/{report['flow_counters']['missing_cell']}")
    print_measures(report["measurements"])
    print_controls(report["controls"])
    print_decision(report["decision"])
    write_report(report)
    print(f"\nwrote {OUT_PATH} in {report['elapsed_s']} s")
    if args.log:
        written = S1.append_log(log_rows(report))
        print(f"appended {written} hypothesis-log rows to {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
