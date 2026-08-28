#!/usr/bin/env python3
"""Sweep 21: the continuation placement ORACLE MAP.

Sweep 19 priced ONE entry law inside the continuation frame - displacement,
retest, and a holding bar - and found it CONT-PARTIAL: positive on a deciding
asset, beaten by the old frame it was supposed to improve on.  What sweep 19
never did was ask where the frame's CEILING sits.  A single law scoring 0.14 of
rung says nothing about whether the frame is poor or whether that law is the
wrong place to stand inside a rich frame.  This unit maps the placements
first, ceilings included, and prices no letter at all.

The USER's question, in the USER's words: is the retest TOUCH, the confirmation
bar, or the RESUMPTION (price exiting the retest zone in the trend direction)
the better entry, and what does the hindsight-best placement contain?

Eight placements on ONE episode set - sweep 19's 3583 episodes, rebuilt by
importing sweep 19's own arm/displacement/retest machinery so the episodes are
identical objects and not a re-derivation that happens to agree:

  P0  the original occurrence fade entry at its own stamp (the old frame).
  P1  the displacement-detect bar (enter the moment displacement is reached).
  P2  the retest TOUCH bar - the refill paper's resting-inside-the-zone lane.
  P3  the retest-HOLD confirmation bar - sweep 19's exact law, reproduced.
  P4  the RESUMPTION bar - the first close that exits the retest band in the
      trend direction.  The USER's placement.
  P5  ORACLE-BAR: the hindsight-best bar over the episode span, same side.
  P6  ORACLE-BAR-EITHER: hindsight-best bar AND side over the same span.
  P7  the paper's re-entry: where a continuation entry retraces through the
      original extreme, the SECOND retest-hold on the reclaimed level.

Two labels on every one of them, because sweep 16's receipt is that the
to-close label carries session drift that no entry law controls: (a) the frozen
to-close cert with the -900 wall, and (b) the 1800 s fixed hold, exiting at the
first of the wall, entry + 1800 s, and the phase close.  Sweep 16's
``build_horizon_plane`` is imported to produce (b); this file never reimplements
an outcome.

P5 and P6 are CEILINGS, not proposals.  Every line that contains hindsight
prints its hindsight bits, one by one, wherever it appears - the program record
has already been burned once by an oracle line whose bits were left implicit,
and the standing fix is that an oracle never travels without its inventory.

No fitting.  No pass letters.  No verdicts.  One pre-registered decisive
comparison, because the USER asked a three-way question and a map that cannot
answer it is not a map: paired per-episode P2-P3, P4-P3 and P2-P4 on both
labels, per asset, with asset-day block sign-flip intervals and a max-stat
adjusted p over the whole 3 x 2 x 3 grid.  The deltas and their p values are
reported as facts, and nothing is promoted.
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

import mill as M  # noqa: F401  (the shard loader the price paths come off)
import sweep1 as S1
import sweep7a as S7A
import sweep8 as S8
import sweep9_twins as S9
import sweep12 as S12
import sweep14 as S14
import sweep16 as S16
import sweep19 as S19

# --------------------------------------------------------------------------
# The law, registered before anything is read.
# --------------------------------------------------------------------------

SPEC = """QRE2MILLSWEEP21
tier=exploratory; EXPLORE-only; PRICING unit - no fitting, no pass letters, no
  verdict column.  Family F18-CONTORACLE.  Parent trial sweep19-009 (sweep 19's
  ruling row, SLOW/size/SI, CONT-PARTIAL).  Seed 20260827.  USER-directed.
DATA LAW.  EXPLORE days only, off the existing mill caches.  No packs, no HOLD,
  no teacher labels, no 2021, no 2025H2.  Sweep 9's ``build_plane`` is the
  occurrence plane and its counters are the refuse-to-run gate: 47402 rows,
  certifiable HG 138 / NKD 132 / SI 132, scoring days 41/40/39.  Sweep 19's
  episode counters are the SECOND gate: 3583 episodes, 47402 occurrences,
  43819 repeated levels, 0 armed-beyond-level, 0 zero-ATR, 0 no-room.  A run
  that misses either gate is refused before any placement is priced.
EPISODES.  ``S19.build_episodes`` verbatim: one episode per distinct
  (cell, side, level), armed at the first occurrence carrying that level, the
  path truncated at the breach (union of a strictly adverse relative price and
  a same-side new extreme).  The continuation side IS the displacement
  direction, which IS the occurrence side; no placement changes the side except
  P6, which changes it with hindsight and says so.
THRESHOLDS.  ``S19.stratum_cuts`` verbatim, per asset x phase-type,
  walk-forward, from strictly prior EXPLORE days with at least 25 of them:
  D = q60 and B = q20 of the per-episode maximum rel over train episodes.  The
  flow and trend pools are not built here because no placement in this unit
  reads speed, flow or day-type; D and B are functions of the train MOVE pool
  alone, and the P3 reproduction check below is what holds that claim to
  account rather than a comment.
PLACEMENTS, each priced with the frozen entry law (``S1.make_entry``'s plane:
  last trusted quote strictly before the entry stamp, frozen cost once):
  P0 offset 0 (the arming occurrence's own stamp).
  P1 the first offset whose running maximum rel reaches D.
  P2 the first offset after P1 with rel <= B.
  P3 the first offset after P2 with rel strictly greater than rel(P2), which is
     ``S19.slow_trigger``'s hold bar, imported and called, not restated.
  P4 the first offset after P2 with rel strictly greater than B - the close
     that leaves the band in the trend direction.  P4 >= P3 by construction.
  P5 argmax of that label's cert over legal bars of the episode span
     [arm, min(breach, phase end)), same side.
  P6 the same argmax over bars AND over both sides, in P5's own entry slots.
  P7 after a P3 (else P4) entry that later trades through the original extreme:
     the first bar that reclaims the level, then ``S19.slow_trigger`` again on
     the reclaimed sub-path, and the entry is that second hold bar.
  At most ONE entry per (cell, side) per placement, the first episode that
  produces that placement, which is sweep 19's own slot rule.
LABELS, both reported everywhere.  close = the frozen to-close cert with the
  -900 wall.  1800 = sweep 16's fixed hold, exit at the first of the wall,
  entry + 1800 s and the phase close, built by ``S16.build_horizon_plane`` and
  masked to the to-close plane's own legality so the two labels price exactly
  the same entries.  The oracle is taken per label: P5/P6 maximise the label
  they are the ceiling of.
HINDSIGHT.  P0-P4 and P7 are causal given the episode: every value read closes
  strictly before the entry stamp.  P5 carries ONE bit (bar choice), P6 carries
  TWO (bar and side), and their per-cell-best ceiling rows carry one more
  (which episode in the cell).  P7 carries none at its own entry stamp; its
  SUBSET is conditioned on a retrace that happens after the FIRST entry and
  before the second, so it is post-entry information for P3/P4 and pre-entry
  information for P7.  Every printed oracle line lists its bits.
MEASUREMENTS per asset x placement x label: entries, cells covered, coverage,
  mean and median cert, P(cert>0) with a Wilson 95 interval, usd per asset-day
  on scoring days, day-ordered MDD, wall rate, median lateness from the arm,
  and the share of entries that retrace through the extreme after entry.  P5/P6
  additionally report per-cell-best oracle day sums, the frame ceilings.
DECISIVE COMPARISON, pre-registered, three contrasts x two labels x three
  assets: paired per-episode P2-P3, P4-P3, P2-P4.  Asset-day block sign-flip,
  10000 draws, the same flip shared across contrasts and labels within an
  asset so their correlation survives; per-cell interval from the flipped
  distribution; max-stat adjusted p over all 18 cells on the studentised
  statistic.  No letter is derived from it.
MUTANT.  QRE2_MILL_S21_MUTANT=oracle_uses_entry_bar_quote prices P5/P6 at the
  bar's own close instead of the last trusted quote strictly before the stamp;
  the planted oracle bar and its hand-computed cert must both go red.
"""

ASSETS = S1.ASSETS
DECIDING = ("NKD", "SI")
REPORT_ONLY = ("HG",)
SEED = 20260827

FAMILY = "F18-CONTORACLE"
PARENT_TRIAL = "sweep19-009"
SELECTION_RULE = ("none: pricing unit, pre-registered placements and labels, "
                  "no fitting, no letters, thresholds imported from sweep 19")

# Gate 1: sweep 9's plane, as sweep 14 banked it and sweep 19 re-checked it.
REPRO_ROWS = S19.REPRO_ROWS
REPRO_COUNTERS = S19.REPRO_COUNTERS
REPRO_CERTIFIABLE = S19.REPRO_CERTIFIABLE
REPRO_SCORING_DAYS = S19.REPRO_SCORING_DAYS
# Gate 2: sweep 19's episode counters, from ``.audit/mill-sweep19.json``.
REPRO_EPISODES = {"occurrences": 47402, "episodes": 3583,
                  "arm_beyond_level": 0, "levels_repeated": 43819,
                  "zero_atr": 0, "no_room": 0}
# Gate 3: sweep 19's own SLOW/ungated entry counts, which P3 must reproduce.
REPRO_P3_ENTRIES = {"HG": 113, "NKD": 108, "SI": 105}

MIN_PRIOR_DAYS = S19.MIN_PRIOR_DAYS
BAR_SECONDS = S1.BAR_SECONDS
NANOS = 1_000_000_000
FIXHOLD_S = 1800

CLOSE = "close"
FIXED = str(FIXHOLD_S)
LABELS = (CLOSE, FIXED)

PLACEMENTS = ("P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7")
PLACEMENT_NAME = {
    "P0": "OCCURRENCE (old frame, arm bar)",
    "P1": "DISPLACEMENT-DETECT bar",
    "P2": "RETEST TOUCH bar",
    "P3": "RETEST-HOLD confirmation bar (sweep 19)",
    "P4": "RESUMPTION bar (band exit, trend direction)",
    "P5": "ORACLE-BAR (best bar, same side)",
    "P6": "ORACLE-BAR-EITHER (best bar and side)",
    "P7": "SECOND-VISIT re-entry (reclaimed level)",
}
# Every line's hindsight inventory, printed wherever the line is printed.
HINDSIGHT_BITS: dict[str, tuple[str, ...]] = {
    "P0": (),
    "P1": (),
    "P2": (),
    "P3": (),
    "P4": (),
    "P5": ("bar choice inside the episode span",),
    "P6": ("bar choice inside the episode span", "traded side"),
    "P7": (),
}
HINDSIGHT_CEILING = {
    "P5": ("bar choice inside the episode span",
           "which episode of the (cell, side) is spent"),
    "P6": ("bar choice inside the episode span", "traded side",
           "which episode of the cell is spent"),
}
CAUSAL = tuple(p for p in PLACEMENTS if not HINDSIGHT_BITS[p])
ORACLES = ("P5", "P6")

# The one pre-registered comparison.
CONTRASTS = (("P2", "P3"), ("P4", "P3"), ("P2", "P4"))
FLIP_DRAWS = 10_000

MUTANT_ENV = "QRE2_MILL_S21_MUTANT"
MUTANT_ORACLE = "oracle_uses_entry_bar_quote"
MUTANTS = (MUTANT_ORACLE,)

OUT_PATH = ROOT / ".audit/mill-sweep21.json"
LOG_PATH = S1.LOG_PATH
LOG_PREFIX = "sweep21"

PLANT_ASSET = S19.PLANT_ASSET
PLANT_USD_PER_ATR = S19.PLANT_USD_PER_ATR
PLANT_LEVEL_MID2 = S19.PLANT_LEVEL_MID2


class SweepRefusal(RuntimeError):
    pass


SPEC_SHA = S1._sha_text(SPEC)


def code_sha() -> str:
    return S1._sha_file(Path(__file__).resolve())


def _mutant() -> str:
    name = os.environ.get(MUTANT_ENV, "")
    if name and name not in MUTANTS:
        raise SweepRefusal(f"unknown sweep-21 mutant {name!r}; known: {MUTANTS}")
    return name


def _rate(hits: float, total: float) -> dict[str, object]:
    if total <= 0:
        return {"n": 0, "rate": None, "lo": None, "hi": None}
    lo, hi = S1.wilson(int(round(hits)), int(total))
    return {"n": int(total), "rate": float(hits) / float(total),
            "lo": float(lo), "hi": float(hi)}


# --------------------------------------------------------------------------
# The two label planes.  Both carry exactly the same legality.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class LabelPlane:
    """``cert[row, side_index, bar]`` in USD for one label, NaN where illegal."""

    label: str
    cert: np.ndarray
    wall: np.ndarray
    bars: np.ndarray
    index: dict[int, int]
    stamp: np.ndarray
    unpriced: int = 0

    def value(self, position: int, side: int, bar: int) -> float:
        row = self.index.get(int(position))
        if row is None:
            return float("nan")
        if not 0 <= int(bar) < int(self.bars[row]):
            return float("nan")
        return float(self.cert[row, 0 if side > 0 else 1, int(bar)])

    def is_wall(self, position: int, side: int, bar: int) -> bool:
        row = self.index.get(int(position))
        if row is None or not 0 <= int(bar) < int(self.bars[row]):
            return False
        return bool(self.wall[row, 0 if side > 0 else 1, int(bar)])


def build_close_plane(cells: Sequence[S8.Cell8]) -> LabelPlane:
    """Sweep 19's cert plane, wrapped.  The legality here is the law's own."""

    base = S19.build_cert_plane(cells)
    return LabelPlane(label=CLOSE, cert=base.cert, wall=base.wall,
                      bars=base.bars, index=base.index, stamp=base.stamp)


def build_fixed_plane(cells: Sequence[S8.Cell8], close: LabelPlane
                      ) -> tuple[LabelPlane, list[dict[str, object]],
                                 dict[str, int]]:
    """Sweep 16's 1800 s horizon plane, masked to the to-close legality.

    ``S16.build_horizon_plane`` indexes by the position of the record inside
    the list it is handed, so it is handed this unit's own cell records and the
    positions come back as 0..len(cells)-1.  Nothing about the horizon law is
    restated here: the grid call, the per-entry close, the wall boundary and the
    hand-checks against the frozen scalar ``outcome()`` are sweep 16's.

    A bar is priced under this label only where the to-close plane already
    calls it legal, so a placement's entry SET is identical under both labels
    and the two columns are a like-for-like comparison rather than two
    different populations.
    """

    records = [cell.rec for cell in cells]
    plane16, hand = S16.build_horizon_plane(records, horizons=(FIXHOLD_S,))
    cert = np.full_like(close.cert, np.nan)
    wall = np.zeros_like(close.wall)
    counters = {"cells": 0, "legal_bars": 0, "priced_bars": 0, "unpriced": 0}
    for slot, cell in enumerate(cells):
        row = close.index[cell.position]
        counters["cells"] += 1
        for column, side in enumerate((1, -1)):
            key = (slot, side, FIXED)
            if key not in plane16.cert:
                counters["unpriced"] += int(cell.n)
                continue
            values = np.asarray(plane16.cert[key], np.float64)
            ok = np.asarray(plane16.ok[key], bool)
            hit = np.asarray(plane16.wall[key], bool)
            legal = np.isfinite(close.cert[row, column, :cell.n])
            keep = legal & ok
            cert[row, column, :cell.n] = np.where(keep, values, np.nan)
            wall[row, column, :cell.n] = hit & keep
            counters["legal_bars"] += int(legal.sum())
            counters["priced_bars"] += int(keep.sum())
            counters["unpriced"] += int((legal & ~ok).sum())
    return (LabelPlane(label=FIXED, cert=cert, wall=wall, bars=close.bars,
                       index=close.index, stamp=close.stamp,
                       unpriced=counters["unpriced"]),
            hand, counters)


# --------------------------------------------------------------------------
# The placement marks.  Every offset is measured from the arm bar.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Marks:
    """Where each placement would enter, as offsets from the arm bar."""

    span: int              # bars [0, span) belong to the episode
    disp: int = -1         # P1
    retest: int = -1       # P2
    hold: int = -1         # P3
    resume: int = -1       # P4
    retrace: int = -1      # the trade back through the extreme, after P3/P4
    reclaim: int = -1      # the bar that puts price back on the trend side
    second: int = -1       # P7
    agrees_with_s19: bool = True


def band_touch(rel: np.ndarray, disp: int, b_cut: float) -> int:
    """First offset after the displacement that is back inside the band."""

    if disp <= 0:
        return -1
    tail = rel[disp + 1:]
    if not len(tail):
        return -1
    inside = np.flatnonzero(tail <= b_cut)
    return disp + 1 + int(inside[0]) if len(inside) else -1


def band_exit(rel: np.ndarray, retest: int, b_cut: float) -> int:
    """First offset after the touch whose close leaves the band upward.

    ``rel`` is signed so that positive is away from the level in the trend
    (displacement) direction, so "exits the band in the trend direction" is
    exactly ``rel > B``.  The array is truncated at the breach, so an episode
    that gives the level back before resuming never resumes at all.
    """

    if retest < 0:
        return -1
    after = rel[retest + 1:]
    if not len(after):
        return -1
    out = np.flatnonzero(after > b_cut)
    return retest + 1 + int(out[0]) if len(out) else -1


def second_visit(ep: S19.Episode, cuts: S19.Cuts, new_ext: np.ndarray,
                 first: int) -> tuple[int, int, int]:
    """``(retrace, reclaim, second hold)`` offsets, or -1 where the path stops.

    The paper's re-entry.  ``first`` is the continuation entry that was taken
    (P3 where it exists, else P4).  The retrace is the first bar after that
    entry which trades through the original extreme - sweep 19's breach
    reading, the union of a strictly adverse relative price and a same-side new
    extreme.  The reclaim is the first bar after the retrace that is back on
    the trend side of the level with no live new extreme, and from there sweep
    19's own slow trigger runs again on the reclaimed sub-path, truncated at
    its own next breach.

    Every value the second entry reads closes at or before the second entry's
    own bar, so the entry is causal.  What is NOT causal for the FIRST entry is
    the subset itself: an episode only joins P7 because of a retrace that
    happens after the first entry.  See ``HINDSIGHT_BITS`` and the note printed
    with the P7 line.
    """

    if first < 0:
        return -1, -1, -1
    full = np.asarray(ep.rel_full, np.float64)
    bad = (full < 0.0) | np.asarray(new_ext, bool)[:len(full)]
    ahead = np.flatnonzero(bad[first + 1:])
    if not len(ahead):
        return -1, -1, -1
    retrace = first + 1 + int(ahead[0])
    back = np.flatnonzero(~bad[retrace + 1:])
    if not len(back):
        return retrace, -1, -1
    reclaim = retrace + 1 + int(back[0])
    sub = full[reclaim:]
    if len(sub) < 3:
        return retrace, reclaim, -1
    stop = S19._breach_offsets(sub, np.asarray(new_ext, bool)[reclaim:len(full)])
    rel2 = np.asarray(sub[:max(stop, 1)], np.float64)
    trig = S19.slow_trigger(rel2, cuts.d_cut, cuts.b_cut, "", sub)
    if trig is None:
        return retrace, reclaim, -1
    return retrace, reclaim, reclaim + int(trig.offset)


def episode_marks(ep: S19.Episode, cuts: S19.Cuts, new_ext: np.ndarray
                  ) -> Marks:
    """Every placement's offset for one episode, from sweep 19's primitives."""

    rel = np.asarray(ep.rel, np.float64)
    marks = Marks(span=int(len(rel)))
    marks.disp = int(S19.displacement_offset(rel, cuts.d_cut))
    if marks.disp <= 0:
        marks.disp = -1
    marks.retest = band_touch(rel, marks.disp, cuts.b_cut)
    trig = S19.slow_trigger(rel, cuts.d_cut, cuts.b_cut, "", ep.rel_full)
    if trig is not None:
        marks.hold = int(trig.offset)
        # The scanner above and sweep 19's trigger must be the same machine.
        marks.agrees_with_s19 = bool(trig.disp_offset == marks.disp
                                     and trig.retest_offset == marks.retest)
    marks.resume = band_exit(rel, marks.retest, cuts.b_cut)
    first = marks.hold if marks.hold >= 0 else marks.resume
    marks.retrace, marks.reclaim, marks.second = second_visit(
        ep, cuts, new_ext, first)
    return marks


# --------------------------------------------------------------------------
# The oracle.  A ceiling, and it says so everywhere it is printed.
# --------------------------------------------------------------------------

def oracle_bar(plane: LabelPlane, position: int, side: int, lo: int, hi: int,
               shift: int = 0) -> tuple[int, float]:
    """``(bar, cert)`` of the best legal bar in ``[lo, hi]``, or ``(-1, nan)``.

    ``shift`` is the mutant.  The honest oracle reads the cert whose entry
    quote is the last trusted one STRICTLY BEFORE the bar's own stamp, which is
    the cert this plane stores at that bar.  With ``shift = 1`` it reads the
    cert one bar later - the entry priced at the bar's OWN close, a quote that
    does not exist at the moment the entry is claimed.
    """

    row = plane.index.get(int(position))
    if row is None:
        return -1, float("nan")
    limit = int(plane.bars[row])
    lo = max(1, int(lo))
    hi = min(int(hi), limit - 1)
    if hi < lo:
        return -1, float("nan")
    column = 0 if side > 0 else 1
    bars = np.arange(lo, hi + 1, dtype=np.int64)
    read = bars + int(shift)
    good = read < limit
    if not good.any():
        return -1, float("nan")
    bars = bars[good]
    values = plane.cert[row, column, read[good]]
    if not np.isfinite(values).any():
        return -1, float("nan")
    at = int(np.nanargmax(values))
    return int(bars[at]), float(values[at])


# --------------------------------------------------------------------------
# The walk.  Sweep 19's fold law, its strata, its slot rule, its cuts.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Shot:
    """One priced placement entry, carrying BOTH labels for the same bar."""

    placement: str
    asset: str
    d8: int
    phase: str
    cell: int
    side: int          # the episode's continuation side
    traded: int        # the side actually entered (differs only for P6)
    bar: int
    arm_bar: int
    ts_ns: int
    lateness: int
    retraced: bool
    episode: tuple[int, int, int]
    cert: dict[str, float] = field(default_factory=dict)
    wall: dict[str, bool] = field(default_factory=dict)


@dataclass(slots=True)
class Walk:
    shots: dict[str, list[Shot]]
    ceiling: dict[str, list[Shot]]
    scoring_days: dict[str, list[int]]
    cells_scored: dict[str, int]
    episodes_scored: int
    counters: dict[str, int]


def _price(shot: Shot, planes: Mapping[str, LabelPlane]) -> Shot:
    for label, plane in planes.items():
        shot.cert[label] = plane.value(shot.cell, shot.traded, shot.bar)
        shot.wall[label] = plane.is_wall(shot.cell, shot.traded, shot.bar)
    return shot


def walk_placements(episodes: Sequence[S19.Episode], cells: Sequence[S8.Cell8],
                    explore_days: Mapping[str, Sequence[int]],
                    planes: Mapping[str, LabelPlane],
                    certifiable: Mapping[tuple[str, str, int], int],
                    mutant: str = "") -> Walk:
    """Score each day with thresholds built only from strictly prior days.

    This is sweep 19's ``walk_forward`` skeleton with placements where its
    lanes and variants were: the same fold law, the same 25-prior-day warmup,
    the same per-(asset, phase-type, day) strata, the same
    ``S19.stratum_cuts``, the same episode order, and the same slot rule of one
    entry per (cell, side) per line.  The flow and trend pools are not built:
    no placement here reads speed, flow or day type, and D and B are functions
    of the train MOVE pool alone.  The P3 reproduction check is what proves
    that shortcut did not move a threshold.
    """

    shift = 1 if mutant == MUTANT_ORACLE else 0
    by_key: dict[tuple[str, str, int], list[S19.Episode]] = {}
    for ep in episodes:
        by_key.setdefault((ep.asset, ep.phase, ep.d8), []).append(ep)
    for value in by_key.values():
        value.sort(key=lambda e: (e.arm_bar, -e.side))
    geo_by = {cell.position: cell.geo for cell in cells}
    ext_cache: dict[tuple[int, int], np.ndarray] = {}

    def new_ext_for(ep: S19.Episode) -> np.ndarray:
        key = (ep.cell, ep.side)
        if key not in ext_cache:
            _prior, flags, _armed = S7A.side_arrays(geo_by[ep.cell], ep.side)
            ext_cache[key] = np.asarray(flags, bool)
        return ext_cache[key][ep.arm_bar:]

    shots: dict[str, list[Shot]] = {name: [] for name in PLACEMENTS}
    ceiling: dict[str, list[Shot]] = {name: [] for name in ORACLES}
    best_cell: dict[tuple[str, str, int], Shot] = {}
    scoring_days: dict[str, list[int]] = {asset: [] for asset in ASSETS}
    cells_scored: dict[str, int] = {asset: 0 for asset in ASSETS}
    counters = {"episodes_seen": 0, "no_cuts": 0, "unscored_days": 0,
                "illegal": 0, "slot_taken": 0, "no_placement": 0,
                "s19_disagreements": 0, "unpriced_fixed": 0}
    seen = 0

    for asset in ASSETS:
        days = sorted(int(day) for day in explore_days[asset])
        phases = sorted({cell.phase for cell in cells if cell.asset == asset})
        for index, d8 in enumerate(days):
            train_days = S14.fold_days(days, index, "")
            if len(train_days) < MIN_PRIOR_DAYS:
                counters["unscored_days"] += 1
                continue
            scoring_days[asset].append(d8)
            cells_scored[asset] += sum(
                int(certifiable.get((asset, phase, d8), 0)) for phase in phases)
            for phase in phases:
                train: list[S19.Episode] = []
                for day in train_days:
                    train.extend(by_key.get((asset, phase, day), []))
                cuts = S19.stratum_cuts(train, [], [])
                today = by_key.get((asset, phase, d8), [])
                if cuts is None:
                    counters["no_cuts"] += len(today)
                    continue
                taken: set[tuple[str, int, int]] = set()
                for ep in today:
                    counters["episodes_seen"] += 1
                    seen += 1
                    marks = episode_marks(ep, cuts, new_ext_for(ep))
                    if not marks.agrees_with_s19:
                        counters["s19_disagreements"] += 1
                    offsets = {"P0": 0, "P1": marks.disp, "P2": marks.retest,
                               "P3": marks.hold, "P4": marks.resume,
                               "P7": marks.second}
                    key = (ep.cell, ep.side, ep.arm_bar)
                    for name in PLACEMENTS:
                        slot = (name, ep.cell, ep.side)
                        if name in ORACLES:
                            offset = 0 if marks.span > 1 else -1
                        else:
                            offset = offsets[name]
                        if offset < 0:
                            counters["no_placement"] += 1
                            continue
                        # The causal placements settle their slot here.  The
                        # oracles do not: EVERY episode has to be offered to
                        # the per-cell-best ceiling before the first-episode
                        # rule decides which one fills the reported line, or
                        # the ceiling's "which episode is spent" bit would be
                        # advertised without ever being exercised.
                        if slot in taken and name not in ORACLES:
                            counters["slot_taken"] += 1
                            continue
                        if name in ORACLES:
                            # The oracle is taken PER LABEL: each label's
                            # ceiling is the best bar for THAT label, because
                            # they are ceilings of two different outcomes.
                            lo = ep.arm_bar + 1
                            hi = ep.arm_bar + marks.span - 1
                            sides = ((ep.side,) if name == "P5"
                                     else (ep.side, -ep.side))
                            rows: list[Shot] = []
                            for label in LABELS:
                                for trade in sides:
                                    bar, value = oracle_bar(
                                        planes[label], ep.cell, trade, lo, hi,
                                        shift)
                                    if bar < 0 or not np.isfinite(value):
                                        continue
                                    rows.append(Shot(
                                        placement=f"{name}:{label}",
                                        asset=asset, d8=d8, phase=ep.phase,
                                        cell=ep.cell, side=ep.side,
                                        traded=trade, bar=bar,
                                        arm_bar=ep.arm_bar,
                                        ts_ns=int(planes[label].stamp[
                                            planes[label].index[ep.cell], bar]),
                                        lateness=int(bar - ep.arm_bar),
                                        retraced=bool(np.any(
                                            np.asarray(ep.rel_full)[
                                                bar - ep.arm_bar:] < 0.0)),
                                        episode=key,
                                        cert={label: float(value)},
                                        wall={label: planes[label].is_wall(
                                            ep.cell, trade, bar)}))
                            picked = _pick_oracle(rows)
                            if not picked:
                                counters["illegal"] += 1
                                continue
                            for label in LABELS:
                                _offer_ceiling(best_cell, name, label, picked,
                                               ep, asset, d8)
                            if slot in taken:
                                counters["slot_taken"] += 1
                                continue
                            taken.add(slot)
                            shots[name].append(_merge_oracle(picked, name, ep,
                                                             key, asset, d8))
                            continue
                        bar = ep.arm_bar + int(offset)
                        value = planes[CLOSE].value(ep.cell, ep.side, bar)
                        if not np.isfinite(value):
                            counters["illegal"] += 1
                            continue
                        taken.add(slot)
                        rest = np.asarray(ep.rel_full, np.float64)[offset:]
                        floor = float(np.min(rest)) if len(rest) else float("nan")
                        row = planes[CLOSE].index[ep.cell]
                        shot = _price(Shot(
                            placement=name, asset=asset, d8=d8, phase=ep.phase,
                            cell=ep.cell, side=ep.side, traded=ep.side, bar=bar,
                            arm_bar=ep.arm_bar,
                            ts_ns=int(planes[CLOSE].stamp[row, bar]),
                            lateness=int(offset),
                            retraced=bool(np.isfinite(floor) and floor < 0.0),
                            episode=key), planes)
                        if not np.isfinite(shot.cert.get(FIXED, np.nan)):
                            counters["unpriced_fixed"] += 1
                        shots[name].append(shot)
    for (name, _label, _cell), shot in sorted(best_cell.items(),
                                              key=lambda kv: (kv[0][0], kv[0][1],
                                                              kv[0][2])):
        ceiling[name].append(shot)
    return Walk(shots=shots, ceiling=ceiling, scoring_days=scoring_days,
                cells_scored=cells_scored, episodes_scored=seen,
                counters=counters)


def _pick_oracle(rows: Sequence[Shot]) -> dict[str, Shot]:
    """The best row per label: one oracle bar for the close, one for 1800 s."""

    out: dict[str, Shot] = {}
    for row in rows:
        label = row.placement.split(":")[1]
        value = float(row.cert[label])
        if label not in out or value > float(out[label].cert[label]):
            out[label] = row
    return out


def _merge_oracle(picked: Mapping[str, Shot], name: str, ep: S19.Episode,
                  key: tuple[int, int, int], asset: str, d8: int) -> Shot:
    """One row per placement carrying each label's own oracle bar and cert.

    The two labels do not have to agree on the bar - they are ceilings of
    different outcomes - so the merged row reports the CLOSE label's bar in its
    bar/stamp/lateness fields and carries both certs.  The 1800 s bar is kept
    in ``wall`` order alongside; the per-label bars are reported separately in
    the oracle tables.
    """

    anchor = picked.get(CLOSE) or next(iter(picked.values()))
    shot = Shot(placement=name, asset=asset, d8=d8, phase=anchor.phase,
                cell=anchor.cell, side=ep.side, traded=anchor.traded,
                bar=anchor.bar, arm_bar=ep.arm_bar, ts_ns=anchor.ts_ns,
                lateness=anchor.lateness, retraced=anchor.retraced,
                episode=key)
    for label in LABELS:
        row = picked.get(label)
        shot.cert[label] = (float(row.cert[label]) if row is not None
                            else float("nan"))
        shot.wall[label] = bool(row.wall[label]) if row is not None else False
        shot.cert[f"{label}/bar"] = (float(row.bar) if row is not None
                                     else float("nan"))
        shot.cert[f"{label}/side"] = (float(row.traded) if row is not None
                                      else float("nan"))
    return shot


def _offer_ceiling(store: dict[tuple[str, str, int], Shot], name: str,
                   label: str, picked: Mapping[str, Shot], ep: S19.Episode,
                   asset: str, d8: int) -> None:
    """Per-cell-best: the ceiling that also gets to choose WHICH episode.

    P5's ceiling still keeps the side the extreme gave it, so its slot is the
    (cell, side); P6's ceiling chooses the side too, so its slot is the cell.
    """

    row = picked.get(label)
    if row is None:
        return
    slot = ((name, label, ep.cell) if name == "P6"
            else (name, label, ep.cell * 4 + (0 if ep.side > 0 else 1)))
    held = store.get(slot)
    if held is None or float(row.cert[label]) > float(held.cert[label]):
        keep = Shot(placement=f"{name}:{label}", asset=asset, d8=d8,
                    phase=row.phase, cell=row.cell, side=ep.side,
                    traded=row.traded, bar=row.bar, arm_bar=ep.arm_bar,
                    ts_ns=row.ts_ns, lateness=row.lateness,
                    retraced=row.retraced, episode=(ep.cell, ep.side,
                                                    ep.arm_bar),
                    cert={label: float(row.cert[label])},
                    wall={label: bool(row.wall[label])})
        store[slot] = keep


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


def measure_rows(rows: Sequence[Shot], label: str, asset: str, days: int,
                 cells_seen: int) -> dict[str, object]:
    mine = [row for row in rows
            if row.asset == asset and np.isfinite(row.cert.get(label, np.nan))]
    certs = np.asarray([float(row.cert[label]) for row in mine], np.float64)
    n_days = max(1, int(days))
    sums: dict[int, float] = {}
    for row in sorted(mine, key=lambda r: (r.ts_ns, r.cell, r.traded)):
        sums[row.d8] = sums.get(row.d8, 0.0) + float(row.cert[label])
    covered = len({row.cell for row in mine})
    return {
        "asset": asset, "label": label,
        "n": int(len(mine)),
        "cells_covered": int(covered),
        "cells_scored": int(cells_seen),
        "coverage": (float(covered) / float(cells_seen)) if cells_seen else None,
        "mean_cert_usd": float(certs.mean()) if len(certs) else None,
        "median_cert_usd": float(np.median(certs)) if len(certs) else None,
        "total_usd": float(certs.sum()) if len(certs) else 0.0,
        "usd_per_asset_day": (float(certs.sum()) / n_days) if len(certs) else 0.0,
        "rung_usd": S1.DAY_RUNG_USD[asset],
        "over_rung": ((float(certs.sum()) / n_days) / S1.DAY_RUNG_USD[asset]
                      if len(certs) else 0.0),
        "p_cert_positive": _rate(float((certs > 0).sum()) if len(certs) else 0.0,
                                 float(len(certs))),
        "mdd_day_usd": _drawdown(sums[key] for key in sorted(sums)),
        "wall_rate": (float(np.mean([bool(row.wall.get(label)) for row in mine]))
                      if mine else None),
        "median_lateness_bars": (float(np.median([row.lateness for row in mine]))
                                 if mine else None),
        "median_lateness_s": (float(np.median([row.lateness for row in mine]))
                              * BAR_SECONDS if mine else None),
        "share_retraced_after_entry": (
            float(np.mean([row.retraced for row in mine])) if mine else None),
        "side_flipped": (float(np.mean([row.traded != row.side
                                        for row in mine])) if mine else None),
    }


def measure(walk: Walk) -> dict[str, object]:
    out: dict[str, object] = {}
    for name in PLACEMENTS:
        block: dict[str, object] = {}
        for label in LABELS:
            per_asset: dict[str, object] = {}
            for asset in ASSETS:
                per_asset[asset] = measure_rows(
                    walk.shots[name], label, asset,
                    len(walk.scoring_days.get(asset, [])),
                    walk.cells_scored.get(asset, 0))
            block[label] = per_asset
        out[name] = block
    return out


def measure_ceilings(walk: Walk) -> dict[str, object]:
    out: dict[str, object] = {}
    for name in ORACLES:
        block: dict[str, object] = {}
        for label in LABELS:
            rows = [row for row in walk.ceiling[name]
                    if row.placement == f"{name}:{label}"]
            per_asset: dict[str, object] = {}
            for asset in ASSETS:
                per_asset[asset] = measure_rows(
                    rows, label, asset, len(walk.scoring_days.get(asset, [])),
                    walk.cells_scored.get(asset, 0))
            block[label] = per_asset
        out[name] = block
    return out


def oracle_detail(walk: Walk) -> dict[str, object]:
    """Where the oracle bars sit relative to the causal placements."""

    out: dict[str, object] = {}
    for name in ORACLES:
        block: dict[str, object] = {}
        for label in LABELS:
            rows = [row for row in walk.shots[name]
                    if np.isfinite(row.cert.get(f"{label}/bar", np.nan))]
            per_asset: dict[str, object] = {}
            for asset in ASSETS:
                mine = [row for row in rows if row.asset == asset]
                if not mine:
                    per_asset[asset] = {"n": 0}
                    continue
                late = np.asarray([float(row.cert[f"{label}/bar"]) - row.arm_bar
                                   for row in mine], np.float64)
                flip = np.asarray([float(row.cert[f"{label}/side"]) != row.side
                                   for row in mine], np.float64)
                per_asset[asset] = {
                    "n": int(len(mine)),
                    "median_oracle_lateness_bars": float(np.median(late)),
                    "mean_oracle_lateness_bars": float(late.mean()),
                    "share_side_flipped": float(flip.mean()),
                }
            block[label] = per_asset
        out[name] = block
    return out


# --------------------------------------------------------------------------
# The one pre-registered comparison: paired deltas with block sign flips.
# --------------------------------------------------------------------------

def paired_deltas(walk: Walk, left: str, right: str, label: str, asset: str
                  ) -> tuple[np.ndarray, np.ndarray]:
    """``(delta, day)`` over episodes where BOTH placements priced an entry."""

    def table(name: str) -> dict[tuple[int, int, int], Shot]:
        return {row.episode: row for row in walk.shots[name]
                if row.asset == asset
                and np.isfinite(row.cert.get(label, np.nan))}

    a = table(left)
    b = table(right)
    keys = sorted(set(a) & set(b))
    delta = np.asarray([float(a[k].cert[label]) - float(b[k].cert[label])
                        for k in keys], np.float64)
    day = np.asarray([a[k].d8 for k in keys], np.int64)
    return delta, day


def contrast_grid(walk: Walk, draws: int = FLIP_DRAWS, seed: int = SEED
                  ) -> dict[str, object]:
    """Every contrast x label x asset, one shared block-flip null.

    The blocks are asset-days.  A draw flips whole days, and within an asset the
    SAME flip is used by every contrast and both labels, so the correlation
    between the cells survives into the max-stat.  The statistic is the block
    sum of paired deltas; it is studentised by its own null standard deviation
    before the max is taken, or the biggest-n cell would win every draw.
    """

    rng = np.random.default_rng(seed)
    day_list = {asset: sorted(walk.scoring_days.get(asset, []))
                for asset in ASSETS}
    day_pos = {asset: {int(d): i for i, d in enumerate(day_list[asset])}
               for asset in ASSETS}
    cells: dict[str, dict[str, object]] = {}
    blocks: dict[str, np.ndarray] = {}
    for left, right in CONTRASTS:
        for label in LABELS:
            for asset in ASSETS:
                delta, day = paired_deltas(walk, left, right, label, asset)
                name = f"{left}-{right}/{label}/{asset}"
                width = max(1, len(day_list[asset]))
                totals = np.zeros(width, np.float64)
                for value, d8 in zip(delta, day):
                    totals[day_pos[asset].get(int(d8), 0)] += float(value)
                blocks[name] = totals
                cells[name] = {
                    "contrast": f"{left}-{right}", "label": label,
                    "asset": asset, "n_pairs": int(len(delta)),
                    "n_day_blocks": int((totals != 0.0).sum()),
                    "observed_total_usd": float(delta.sum()) if len(delta) else 0.0,
                    "observed_mean_usd": (float(delta.mean()) if len(delta)
                                          else None),
                    "observed_median_usd": (float(np.median(delta)) if len(delta)
                                            else None),
                    "observed_usd_day": (float(delta.sum()) / max(1, width)),
                    "share_left_wins": (float((delta > 0).mean()) if len(delta)
                                        else None),
                }
    names = [name for name in cells if cells[name]["n_pairs"]]
    if not names:
        return {"draws": 0, "cells": cells}
    null = {name: np.zeros(draws, np.float64) for name in names}
    for draw in range(draws):
        flips = {asset: rng.choice(np.asarray([-1.0, 1.0]),
                                   size=max(1, len(day_list[asset])))
                 for asset in ASSETS}
        for name in names:
            asset = str(cells[name]["asset"])
            null[name][draw] = float(np.dot(blocks[name], flips[asset]))
    scale = {name: float(np.std(null[name])) or 1.0 for name in names}
    zed = np.zeros((len(names), draws), np.float64)
    for row, name in enumerate(names):
        zed[row] = np.abs(null[name]) / scale[name]
    top = zed.max(axis=0)
    for name in names:
        own = null[name]
        seen = float(cells[name]["observed_total_usd"])
        width = max(1, len(day_list[str(cells[name]["asset"])]))
        z = abs(seen) / scale[name]
        cells[name].update({
            "null_sd_usd": scale[name],
            "null_lo_usd_day": float(np.percentile(own, 2.5)) / width,
            "null_hi_usd_day": float(np.percentile(own, 97.5)) / width,
            "z": z,
            "p_own": float((1 + int(np.sum(np.abs(own) >= abs(seen))))
                           / (1 + draws)),
            "p_max_adjusted": float((1 + int(np.sum(top >= z))) / (1 + draws)),
        })
    return {"draws": int(draws), "statistic": "paired block sum, two-sided",
            "cells": cells, "grid": len(names)}


def matched_baseline(walk: Walk) -> dict[str, object]:
    """P0 restricted to each causal placement's own episodes, both labels.

    Sweep 19's C2 control was exactly this object for P3 alone.  Reporting it
    for every placement is what makes "better than the old frame" a per-
    placement fact rather than a claim inherited from one line.
    """

    out: dict[str, object] = {}
    base = {row.episode: row for row in walk.shots["P0"]}
    for name in ("P1", "P2", "P3", "P4", "P7"):
        block: dict[str, object] = {}
        for label in LABELS:
            per_asset: dict[str, object] = {}
            for asset in ASSETS:
                rows = [row for row in walk.shots[name] if row.asset == asset
                        and np.isfinite(row.cert.get(label, np.nan))]
                pairs = [(row, base[row.episode]) for row in rows
                         if row.episode in base
                         and np.isfinite(base[row.episode].cert.get(label,
                                                                    np.nan))]
                days = max(1, len(walk.scoring_days.get(asset, [])))
                if not pairs:
                    per_asset[asset] = {"n": 0}
                    continue
                mine = np.asarray([float(a.cert[label]) for a, _b in pairs],
                                  np.float64)
                old = np.asarray([float(b.cert[label]) for _a, b in pairs],
                                 np.float64)
                per_asset[asset] = {
                    "n": int(len(pairs)),
                    "placement_usd_day": float(mine.sum()) / days,
                    "old_frame_usd_day": float(old.sum()) / days,
                    "delta_usd_day": float(mine.sum() - old.sum()) / days,
                    "beats_old_frame": bool(mine.sum() > old.sum()),
                }
            block[label] = per_asset
        out[name] = block
    return out


def ranking(report: Mapping[str, object], ceilings: Mapping[str, object]
            ) -> list[dict[str, object]]:
    """One consolidated table: placement x label, deciding asset, over rung."""

    rows: list[dict[str, object]] = []
    for name in PLACEMENTS:
        for label in LABELS:
            block = report[name][label]                 # type: ignore[index]
            best_asset = None
            best_value = -float("inf")
            for asset in DECIDING:
                value = float(block[asset]["usd_per_asset_day"])
                if block[asset]["n"] and value > best_value:
                    best_value, best_asset = value, asset
            row = {
                "placement": name, "label": label,
                "name": PLACEMENT_NAME[name],
                "hindsight_bits": list(HINDSIGHT_BITS[name]),
                "n_bits": len(HINDSIGHT_BITS[name]),
                "causal": name in CAUSAL,
                "deciding_asset": best_asset,
                "deciding_usd_day": (best_value if best_asset else None),
                "deciding_over_rung": (
                    best_value / S1.DAY_RUNG_USD[best_asset]
                    if best_asset else None),
                "hg_usd_day": float(block["HG"]["usd_per_asset_day"]),
                "hg_over_rung": float(block["HG"]["over_rung"]),
                "n_nkd": int(block["NKD"]["n"]), "n_si": int(block["SI"]["n"]),
                "n_hg": int(block["HG"]["n"]),
            }
            if name in ORACLES:
                ceil = ceilings[name][label]            # type: ignore[index]
                top_asset, top_value = None, -float("inf")
                for asset in DECIDING:
                    value = float(ceil[asset]["usd_per_asset_day"])
                    if ceil[asset]["n"] and value > top_value:
                        top_value, top_asset = value, asset
                row["ceiling_asset"] = top_asset
                row["ceiling_usd_day"] = top_value if top_asset else None
                row["ceiling_over_rung"] = (
                    top_value / S1.DAY_RUNG_USD[top_asset] if top_asset else None)
                row["ceiling_bits"] = list(HINDSIGHT_CEILING[name])
            rows.append(row)
    return rows


def headline(rank: Sequence[Mapping[str, object]]) -> dict[str, object]:
    causal = [row for row in rank if row["causal"]
              and row["deciding_over_rung"] is not None]
    best = max(causal, key=lambda r: float(r["deciding_over_rung"]))
    p5 = [row for row in rank if row["placement"] == "P5"
          and row["label"] == best["label"]]
    ceiling = p5[0] if p5 else None
    return {
        "best_causal_placement": best["placement"],
        "best_causal_label": best["label"],
        "best_causal_asset": best["deciding_asset"],
        "best_causal_usd_day": best["deciding_usd_day"],
        "best_causal_over_rung": best["deciding_over_rung"],
        "p5_ceiling_asset": (ceiling["deciding_asset"] if ceiling else None),
        "p5_ceiling_usd_day": (ceiling["deciding_usd_day"] if ceiling else None),
        "p5_ceiling_over_rung": (ceiling["deciding_over_rung"] if ceiling
                                 else None),
        "p5_percell_ceiling_over_rung": (ceiling.get("ceiling_over_rung")
                                         if ceiling else None),
    }


# --------------------------------------------------------------------------
# Printing.
# --------------------------------------------------------------------------

def _n(value: object, width: int = 9, digits: int = 3) -> str:
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "-".rjust(width)
    if isinstance(value, float):
        return f"{value:>{width}.{digits}f}"
    return f"{value:>{width}}"


def print_gate(repro: Mapping[str, object], episodes: Mapping[str, object],
               fixed: Mapping[str, object], hand: Mapping[str, object]) -> None:
    print("\nGATE  sweep 9's occurrence plane, sweep 19's episodes, sweep 16's "
          "horizon law")
    print(f"  rows           banked {repro['banked_rows']}  live "
          f"{repro['live_rows']}")
    print(f"  certifiable    banked {repro['banked_certifiable']}  live "
          f"{repro['live_certifiable']}")
    print(f"  scoring days   banked {repro['banked_scoring_days']}  live "
          f"{repro['live_scoring_days']}")
    print(f"  counters match {repro['matches']}")
    for name in sorted(REPRO_EPISODES):
        print(f"  episodes/{name:<18s} banked {REPRO_EPISODES[name]:>7d}  live "
              f"{int(episodes[name]):>7d}  "
              f"{'ok' if int(episodes[name]) == REPRO_EPISODES[name] else 'MISS'}")
    print(f"  1800 s plane   cells {fixed['cells']}, legal bars "
          f"{fixed['legal_bars']}, priced {fixed['priced_bars']}, unpriced "
          f"{fixed['unpriced']}")
    print(f"  1800 s hand-checks vs the frozen scalar outcome(): "
          f"{hand['rows']} rows, {hand['mismatches']} mismatches, worst |d| "
          f"{hand['worst_abs_usd']:.2e} usd -> {'ok' if hand['ok'] else 'RED'}")


def print_placements(report: Mapping[str, object], detail: Mapping[str, object],
                     ceilings: Mapping[str, object]) -> None:
    for name in PLACEMENTS:
        bits = HINDSIGHT_BITS[name]
        tag = ("CAUSAL, no hindsight bits" if not bits
               else f"HINDSIGHT BITS ({len(bits)}): " + "; ".join(bits))
        print(f"\n{name}  {PLACEMENT_NAME[name]}")
        print(f"     {tag}")
        if name == "P7":
            print("     subset note: the entry itself reads nothing after its "
                  "own stamp.  The SUBSET is conditioned on a retrace that "
                  "follows the P3/P4 entry and precedes this one - post-entry "
                  "information for the FIRST entry, pre-entry information for "
                  "this one.")
        print("  label  asset      n   cells    cov     mean   median      "
              "p>0   [   lo,    hi]    usd/day   over_rung     mdd    wall "
              " late_bars  retrace")
        for label in LABELS:
            for asset in ASSETS:
                row = report[name][label][asset]        # type: ignore[index]
                rate = row["p_cert_positive"]
                print(f"  {label:<5s}  {asset:<4s} {_n(row['n'], 6)} "
                      f"{_n(row['cells_covered'], 6)} "
                      f"{_n(row['coverage'], 6, 3)} "
                      f"{_n(row['mean_cert_usd'], 8, 1)} "
                      f"{_n(row['median_cert_usd'], 8, 1)} "
                      f"{_n(rate['rate'], 8, 3)}  "
                      f"[{_n(rate['lo'], 5, 3)},{_n(rate['hi'], 6, 3)}] "
                      f"{_n(row['usd_per_asset_day'], 10, 2)} "
                      f"{_n(row['over_rung'], 11, 4)} "
                      f"{_n(row['mdd_day_usd'], 7, 0)} "
                      f"{_n(row['wall_rate'], 7, 3)} "
                      f"{_n(row['median_lateness_bars'], 9, 1)} "
                      f"{_n(row['share_retraced_after_entry'], 8, 3)}")
        if name in ORACLES:
            print(f"     CEILING rows, per-cell-best.  HINDSIGHT BITS "
                  f"({len(HINDSIGHT_CEILING[name])}): "
                  + "; ".join(HINDSIGHT_CEILING[name]))
            for label in LABELS:
                for asset in ASSETS:
                    row = ceilings[name][label][asset]  # type: ignore[index]
                    print(f"  {label:<5s}  {asset:<4s} {_n(row['n'], 6)} "
                          f"{_n(row['cells_covered'], 6)} "
                          f"{_n(row['coverage'], 6, 3)} "
                          f"{_n(row['mean_cert_usd'], 8, 1)} "
                          f"{_n(row['median_cert_usd'], 8, 1)} "
                          f"{'':>8s}  [{'':>5s},{'':>6s}] "
                          f"{_n(row['usd_per_asset_day'], 10, 2)} "
                          f"{_n(row['over_rung'], 11, 4)}   <- ceiling")
            print("     oracle bar placement")
            for label in LABELS:
                for asset in ASSETS:
                    row = detail[name][label][asset]    # type: ignore[index]
                    if not row.get("n"):
                        continue
                    print(f"  {label:<5s}  {asset:<4s} n {row['n']:>5d}  "
                          f"median lateness "
                          f"{row['median_oracle_lateness_bars']:>7.1f} bars, "
                          f"mean {row['mean_oracle_lateness_bars']:>8.1f}, "
                          f"side flipped {row['share_side_flipped']:.3f}")


def print_ranking(rows: Sequence[Mapping[str, object]]) -> None:
    print("\nCONSOLIDATED RANKING  (deciding assets NKD/SI at rung 1500; HG "
          "report-only at rung 2000)")
    print("  place label   bits  deciding   usd/day  over_rung        hg "
          "usd/day  hg_rung   n_nkd n_si  ceiling usd/day  over_rung")
    order = sorted(rows, key=lambda r: (r["deciding_over_rung"] is None,
                                        -(r["deciding_over_rung"] or 0.0)))
    for row in order:
        ceil_usd = row.get("ceiling_usd_day")
        ceil_rung = row.get("ceiling_over_rung")
        print(f"  {row['placement']:<5s} {row['label']:<5s} "
              f"{row['n_bits']:>5d}  {str(row['deciding_asset'] or '-'):<8s} "
              f"{_n(row['deciding_usd_day'], 9, 2)} "
              f"{_n(row['deciding_over_rung'], 10, 4)}  "
              f"{_n(row['hg_usd_day'], 12, 2)} "
              f"{_n(row['hg_over_rung'], 8, 4)} "
              f"{_n(row['n_nkd'], 7)} {_n(row['n_si'], 4)} "
              f"{_n(ceil_usd, 16, 2)} {_n(ceil_rung, 10, 4)}")
    print("  bits = hindsight bits the line contains; 0 = causal.")


def print_contrasts(block: Mapping[str, object]) -> None:
    print(f"\nDECISIVE COMPARISON  paired per-episode deltas, "
          f"{block.get('draws')} asset-day block sign flips, max-stat adjusted "
          f"over {block.get('grid')} cells")
    print("  contrast label asset   pairs    mean_usd  median_usd   total_usd"
          "    usd/day  [null 95% usd/day]   left_wins    p_own   p_adj")
    cells = block["cells"]                              # type: ignore[index]
    for left, right in CONTRASTS:
        for label in LABELS:
            for asset in ASSETS:
                name = f"{left}-{right}/{label}/{asset}"
                row = cells[name]
                if not row["n_pairs"]:
                    print(f"  {left}-{right} {label:<5s} {asset:<4s} "
                          f"{0:>7d}   no paired episodes")
                    continue
                print(f"  {left}-{right} {label:<5s} {asset:<4s} "
                      f"{row['n_pairs']:>7d} "
                      f"{_n(row['observed_mean_usd'], 11, 2)} "
                      f"{_n(row['observed_median_usd'], 11, 2)} "
                      f"{_n(row['observed_total_usd'], 11, 1)} "
                      f"{_n(row['observed_usd_day'], 10, 2)}  "
                      f"[{_n(row.get('null_lo_usd_day'), 8, 2)},"
                      f"{_n(row.get('null_hi_usd_day'), 8, 2)}] "
                      f"{_n(row['share_left_wins'], 11, 3)} "
                      f"{_n(row.get('p_own'), 8, 4)} "
                      f"{_n(row.get('p_max_adjusted'), 7, 4)}")
    print("  No pass letter is derived from this table; the deltas and their p "
          "values are the record.")


def print_matched(block: Mapping[str, object]) -> None:
    print("\nOLD-FRAME MATCHED BASELINE  each placement against P0 on its own "
          "episodes (sweep 19's C2, generalised)")
    print("  place label asset       n   placement   old frame       delta  "
          "beats")
    for name in ("P1", "P2", "P3", "P4", "P7"):
        for label in LABELS:
            for asset in ASSETS:
                row = block[name][label][asset]         # type: ignore[index]
                if not row.get("n"):
                    continue
                print(f"  {name:<5s} {label:<5s} {asset:<4s} "
                      f"{row['n']:>7d} "
                      f"{_n(row['placement_usd_day'], 11, 2)} "
                      f"{_n(row['old_frame_usd_day'], 11, 2)} "
                      f"{_n(row['delta_usd_day'], 11, 2)}  "
                      f"{'Y' if row['beats_old_frame'] else 'n'}")


def print_counters(walk: Mapping[str, object]) -> None:
    print(f"\nwalk counters {walk}")


# --------------------------------------------------------------------------
# Selftest and the red mutant.
# --------------------------------------------------------------------------

def _check(name: str, ok: bool, detail: str = "") -> tuple[str, bool, str]:
    return (name, bool(ok), detail)


def _plant_path(kind: str) -> np.ndarray:
    """Hand-built rel paths in ATR units.  Every expected bar is arithmetic."""

    if kind in ("continuation", "breach", "fast"):
        _rel, full, _neg = S19._planted(kind)
        return np.asarray(full, np.float64)
    if kind == "resumption":
        # Displace to 1.20 by bar 4, retest to 0.10 at bar 8, TURN at bar 9
        # (0.15, still inside the 0.20 band) and only EXIT the band at bar 11.
        # P3 = 9, P4 = 11: the two placements the USER asked to separate.
        return np.array([0.00, 0.30, 0.60, 0.90, 1.20, 0.90, 0.60, 0.30, 0.10,
                         0.15, 0.18, 0.40, 0.90, 1.50], np.float64)
    if kind == "retrace":
        # The continuation path, then a trade THROUGH the level at bar 12, a
        # reclaim at bar 13, a second displacement to 1.20 at bar 16, a second
        # retest to 0.20 at bar 20 and a second hold at bar 23.
        return np.array([0.00, 0.30, 0.60, 0.90, 1.20, 0.90, 0.60, 0.30, 0.10,
                         0.05, 0.40, 0.20, -0.10, 0.05, 0.40, 0.80, 1.20, 1.20,
                         0.80, 0.40, 0.20, 0.10, 0.05, 0.40, 1.00], np.float64)
    if kind == "long":
        # 40 bars: up for 30, then straight back down.  The 1800 s hold (30
        # bars) exits at the top; the to-close label rides all the way back.
        up = np.linspace(0.0, 1.5, 31)
        down = np.linspace(1.45, 0.0, 9)
        return np.asarray(np.concatenate([up, down]), np.float64)
    raise SweepRefusal(f"unknown planted case {kind!r}")


def _plant_rec(full: np.ndarray, side: int = 1) -> S1.CellRec:
    """Sweep 19's ``_planted_rec`` construction, over an arbitrary rel path.

    Rebuilt rather than imported because sweep 19's builder only knows its own
    three cases; the selftest below asserts this rebuild is byte-identical to
    sweep 19's on the case they share, so it is the same fixture and not a
    look-alike.
    """

    n = len(full)
    scale = S7A.usd_to_mid2(PLANT_ASSET)
    atr = PLANT_USD_PER_ATR * scale
    mid = np.round(PLANT_LEVEL_MID2 + float(side) * full * atr).astype(np.int64)
    lat = (np.arange(n, dtype=np.int64) * S1.BAR_NS + 1_600_000_000_000_000_000)
    travel = (float(side) * (mid[-1] - mid)).astype(np.float64) / scale
    zeros = np.zeros(n, np.int64)
    return S1.CellRec(
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


def _plant_plane(full: np.ndarray, side: int = 1
                 ) -> tuple[LabelPlane, LabelPlane, S1.CellRec]:
    """Both label planes over one planted path, through the frozen machinery.

    The to-close plane is built from the planted ``CellRec`` exactly as
    ``S19.build_cert_plane`` builds it.  The 1800 s plane is priced by
    ``S16.outcomes_grid_capped`` on a synthetic tick index whose ticks sit one
    nanosecond BEFORE each bar stamp, so the quote the entry law reads at bar
    ``b`` is the planted mid at bar ``b`` - the last trusted quote strictly
    before the stamp, which is the whole point of the frozen law.
    """

    rec = _plant_rec(full, side)
    n = rec.n
    width = n
    close = LabelPlane(label=CLOSE, cert=np.full((1, 2, width), np.nan),
                       wall=np.zeros((1, 2, width), bool),
                       bars=np.asarray([n], np.int64), index={0: 0},
                       stamp=np.zeros((1, width), np.int64))
    close.stamp[0, :n] = rec.lat
    for column, trade in enumerate((1, -1)):
        legal = np.zeros(n, bool)
        legal[max(rec.legal_from(trade), 1):] = True
        legal &= np.asarray(rec.ok(trade), bool)
        legal[0] = False
        legal[n - 1] = False
        close.cert[0, column, :n] = np.where(legal,
                                             np.asarray(rec.cert(trade),
                                                        np.float64), np.nan)
    # Sweep 16's synthetic index, with its ticks moved so tick k sits one
    # nanosecond STRICTLY BEFORE bar k's stamp: then the quote the frozen entry
    # law reads at bar k is the planted mid at bar k, and the outcome window
    # opens at bar k+1.
    ticks = np.asarray(rec.lat, np.int64) - 1
    index = M.MillIndex(PLANT_ASSET, ticks, np.asarray(rec.mid, np.int64),
                        np.asarray(rec.mid, np.int64) // 2,
                        np.asarray(rec.mid, np.int64) // 2,
                        np.zeros(n, np.uint32), ticks, np.zeros(n, np.uint32))
    fixed = LabelPlane(label=FIXED, cert=np.full((1, 2, width), np.nan),
                       wall=np.zeros((1, 2, width), bool),
                       bars=np.asarray([n], np.int64), index={0: 0},
                       stamp=close.stamp)
    stamps = np.asarray(rec.lat, np.int64)
    closes = np.minimum(stamps + FIXHOLD_S * NANOS, int(rec.phase_close_ts_ns))
    for column, trade in enumerate((1, -1)):
        grid = S16.outcomes_grid_capped(
            index, stamps, trade, closes,
            entry_mid2=np.asarray(rec.mid, np.int64),
            cost_usd=np.zeros(n, np.float64))
        take = np.asarray(grid["input_index"], np.int64)
        values = np.full(n, np.nan, np.float64)
        hits = np.zeros(n, bool)
        if len(take):
            values[take] = grid["cert_close_usd"]
            hits[take] = grid["wall_hit"]
        legal = np.isfinite(close.cert[0, column, :n])
        fixed.cert[0, column, :n] = np.where(legal & np.isfinite(values),
                                             values, np.nan)
        fixed.wall[0, column, :n] = hits & legal
    return close, fixed, rec


def _plant_marks(full: np.ndarray, d_cut: float = 1.0, b_cut: float = 0.2
                 ) -> tuple[Marks, S19.Episode]:
    rel_stop = S19._breach_offsets(full, np.zeros(len(full), bool))
    rel = np.asarray(full[:max(rel_stop, 1)], np.float64)
    ep = S19.Episode(cell=0, asset=PLANT_ASSET, d8=20220315, phase="0", side=1,
                     arm_bar=0, level=PLANT_LEVEL_MID2, atr=1.0, rel=rel,
                     rel_full=np.asarray(full, np.float64),
                     breached=bool(rel_stop < len(full)),
                     neg=np.zeros(len(rel), np.float64),
                     x=np.zeros(S14.NFEAT, np.float64), payoff_at_arm=0.0)
    cuts = S19.Cuts(d_cut=d_cut, b_cut=b_cut, speed_cut=float("inf"), window=2,
                    flow_hi=float("inf"), flow_lo=0.0, trend_cut=float("inf"),
                    size_cut=float("nan"), train_episodes=1)
    return episode_marks(ep, cuts, np.zeros(len(full), bool)), ep


def _selftest_fixture() -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []
    mine = _plant_rec(_plant_path("continuation"))
    theirs, _rel, _full = S19._planted_rec("continuation")
    same = (np.array_equal(mine.mid, theirs.mid)
            and np.array_equal(mine.lat, theirs.lat)
            and np.allclose(mine.cert_p, theirs.cert_p)
            and np.allclose(mine.cert_m, theirs.cert_m))
    out.append(_check("fixture/rebuild_matches_sweep19", same,
                      "the planted CellRec is sweep 19's, bar for bar"))
    return out


def _selftest_marks() -> list[tuple[str, bool, str]]:
    """Every placement bar on the planted paths, hand-computed."""

    out: list[tuple[str, bool, str]] = []
    marks, _ep = _plant_marks(_plant_path("continuation"))
    out.append(_check("marks/continuation_P1_disp_4", marks.disp == 4,
                      f"P1 {marks.disp}, want 4 (rel reaches 1.20 at bar 4)"))
    out.append(_check("marks/continuation_P2_retest_8", marks.retest == 8,
                      f"P2 {marks.retest}, want 8 (rel 0.10 <= band 0.20)"))
    out.append(_check("marks/continuation_P3_hold_10", marks.hold == 10,
                      f"P3 {marks.hold}, want 10 (bar 9 sags to 0.05)"))
    out.append(_check("marks/continuation_P4_resume_10", marks.resume == 10,
                      f"P4 {marks.resume}, want 10 (first close above 0.20)"))
    out.append(_check("marks/agrees_with_sweep19_trigger",
                      marks.agrees_with_s19,
                      "this unit's disp/retest scan IS S19.slow_trigger's"))
    res, _ep2 = _plant_marks(_plant_path("resumption"))
    out.append(_check("marks/resumption_P3_9", res.hold == 9,
                      f"P3 {res.hold}, want 9 (0.15 turns, inside the band)"))
    out.append(_check("marks/resumption_P4_11", res.resume == 11,
                      f"P4 {res.resume}, want 11 (0.40 is the band exit)"))
    out.append(_check("marks/P4_never_precedes_P3", res.resume >= res.hold,
                      "a band exit is also a turn, so P4 >= P3 always"))
    brc, _ep3 = _plant_marks(_plant_path("breach"))
    out.append(_check("marks/breach_no_P3", brc.hold == -1,
                      f"P3 {brc.hold}: the retest traded through the level"))
    out.append(_check("marks/breach_no_P4", brc.resume == -1,
                      f"P4 {brc.resume}: nothing resumes after a breach"))
    ret, _ep4 = _plant_marks(_plant_path("retrace"))
    out.append(_check("marks/retrace_first_entry_10", ret.hold == 10,
                      f"first entry {ret.hold}, want 10"))
    out.append(_check("marks/retrace_through_extreme_12", ret.retrace == 12,
                      f"retrace {ret.retrace}, want 12 (rel -0.10)"))
    out.append(_check("marks/retrace_reclaim_13", ret.reclaim == 13,
                      f"reclaim {ret.reclaim}, want 13 (rel 0.05 >= 0)"))
    out.append(_check("marks/P7_second_hold_23", ret.second == 23,
                      f"P7 {ret.second}, want 23 (disp 16, retest 20, hold 23)"))
    return out


def _selftest_certs(mutant: str) -> list[tuple[str, bool, str]]:
    """Both labels, hand-computed, on the planted paths."""

    out: list[tuple[str, bool, str]] = []
    usd = PLANT_USD_PER_ATR
    full = _plant_path("continuation")
    close, fixed, rec = _plant_plane(full)
    marks, ep = _plant_marks(full)
    for name, offset, want in (("P1", marks.disp, (2.00 - 1.20) * usd),
                               ("P2", marks.retest, (2.00 - 0.10) * usd),
                               ("P3", marks.hold, (2.00 - 0.40) * usd),
                               ("P4", marks.resume, (2.00 - 0.40) * usd)):
        got = close.value(0, 1, offset)
        out.append(_check(f"cert/close_{name}_hand", abs(got - want) < 1e-6,
                          f"{got:.2f} usd, hand {want:.2f} "
                          f"(bar {offset}, close rel 2.00)"))
        # The plant is 14 bars, so entry + 1800 s is past the phase close and
        # the fixed-hold label MUST equal the to-close label.
        other = fixed.value(0, 1, offset)
        out.append(_check(f"cert/fixed_{name}_equals_close",
                          abs(other - want) < 1e-6,
                          f"{other:.2f} usd, hand {want:.2f} (14-bar plant: "
                          f"1800 s truncates at the phase close)"))
    out.append(_check("cert/P0_arm_bar_is_illegal",
                      S1.make_entry(0, rec, 0, 1) is None
                      and not np.isfinite(close.value(0, 1, 0)),
                      "bar 0 carries no entry under the frozen law"))
    # The 1800 s label is a REAL constraint on a path longer than 30 bars.
    long_path = _plant_path("long")
    lclose, lfixed, _lrec = _plant_plane(long_path)
    top = float(np.max(long_path))
    want_close = (float(long_path[-1]) - float(long_path[1])) * usd
    want_fixed = (float(long_path[31]) - float(long_path[1])) * usd
    out.append(_check("cert/long_close_rides_to_the_close",
                      abs(lclose.value(0, 1, 1) - want_close) < 1e-6,
                      f"{lclose.value(0, 1, 1):.2f} usd, hand {want_close:.2f}"))
    out.append(_check("cert/long_fixed_exits_at_1800s",
                      abs(lfixed.value(0, 1, 1) - want_fixed) < 1e-6,
                      f"{lfixed.value(0, 1, 1):.2f} usd, hand {want_fixed:.2f} "
                      f"(30 bars after bar 1, peak {top:.2f} ATR)"))
    out.append(_check("cert/long_labels_differ",
                      abs(lclose.value(0, 1, 1) - lfixed.value(0, 1, 1)) > 1.0,
                      "the fixed hold is not the to-close label in disguise"))
    # P7 on the retrace plant, priced.
    ret_path = _plant_path("retrace")
    rclose, _rfixed, _rec2 = _plant_plane(ret_path)
    rmarks, _rep = _plant_marks(ret_path)
    want_p7 = (1.00 - 0.40) * usd
    got_p7 = rclose.value(0, 1, rmarks.second)
    out.append(_check("cert/P7_hand", abs(got_p7 - want_p7) < 1e-6,
                      f"{got_p7:.2f} usd, hand {want_p7:.2f} (bar 23 at rel "
                      f"0.40, cell closes at rel 1.00)"))
    del ep, mutant
    return out


def _selftest_oracle(mutant: str) -> list[tuple[str, bool, str]]:
    """The oracle by brute force, and the mutant that has to break it."""

    out: list[tuple[str, bool, str]] = []
    usd = PLANT_USD_PER_ATR
    full = _plant_path("continuation")
    close, fixed, rec = _plant_plane(full)
    marks, ep = _plant_marks(full)
    span_hi = marks.span - 1
    shift = 1 if mutant == MUTANT_ORACLE else 0
    bar, value = oracle_bar(close, 0, 1, 1, span_hi, shift)
    # Brute force, written out: the to-close cert at bar b is (2.00 - rel[b])
    # ATR, so the best bar is the LOWEST rel among the legal bars, which is
    # bar 9 at rel 0.05, worth 1.95 ATR = 780.00 usd.
    brute_bar, brute_value = -1, -float("inf")
    for probe in range(1, rec.n - 1):
        got = close.value(0, 1, probe)
        if np.isfinite(got) and got > brute_value:
            brute_bar, brute_value = probe, float(got)
    out.append(_check("oracle/brute_force_agrees",
                      bar == brute_bar and abs(value - brute_value) < 1e-9,
                      f"oracle bar {bar} at {value:.2f} usd, brute force bar "
                      f"{brute_bar} at {brute_value:.2f} usd"))
    out.append(_check("oracle/planted_bar_is_9", bar == 9,
                      f"bar {bar}, want 9 (rel 0.05, the lowest legal bar)"))
    out.append(_check("oracle/planted_cert_is_780",
                      abs(value - (2.00 - 0.05) * usd) < 1e-6,
                      f"{value:.2f} usd, hand {(2.00 - 0.05) * usd:.2f} "
                      f"(1.95 ATR at {usd:.0f} usd/ATR)"))
    out.append(_check("oracle/quote_is_the_bar_before_the_stamp",
                      abs(value - close.value(0, 1, bar)) < 1e-9,
                      "the oracle's cert IS the plane's cert at its own bar"))
    fbar, fvalue = oracle_bar(fixed, 0, 1, 1, span_hi, shift)
    out.append(_check("oracle/fixed_label_same_bar_on_a_short_plant",
                      fbar == bar and abs(fvalue - value) < 1e-6,
                      f"1800 s oracle bar {fbar} at {fvalue:.2f} usd"))
    # P6 frees the side.  On this path the short side is worth -780 at bar 9
    # and its best bar is bar 4 (rel 1.20 -> 2.00, a 0.80 ATR loss = -320);
    # the long side wins, so P6 must equal P5 here.
    long_bar, long_value = oracle_bar(close, 0, 1, 1, span_hi, shift)
    short_bar, short_value = oracle_bar(close, 0, -1, 1, span_hi, shift)
    out.append(_check("oracle/either_side_picks_the_winner",
                      long_value > short_value,
                      f"long {long_value:.2f} usd at bar {long_bar}, short "
                      f"{short_value:.2f} usd at bar {short_bar}"))
    # The long plant's best bar is the FIRST legal one, so the mutant's shift
    # cannot move the bar - it can only misprice it.  rel[1] = 0.05 and the
    # cell closes at rel 0.00, so the honest oracle is worth -0.05 ATR =
    # -20.00 usd; reading the bar's own close prices it at rel[2] = 0.10 and
    # the CERT goes to -40.00.  This is the mutant's other face.
    lclose, _lfixed, _lrec = _plant_plane(_plant_path("long"))
    lbar, lvalue = oracle_bar(lclose, 0, 1, 1, len(_plant_path("long")) - 1,
                              shift)
    out.append(_check("oracle/long_plant_bar_is_1", lbar == 1,
                      f"bar {lbar}, want 1 (rel 0.05 is the lowest legal bar)"))
    out.append(_check("oracle/long_plant_cert_is_minus_20",
                      abs(lvalue - (0.00 - 0.05) * usd) < 1e-6,
                      f"{lvalue:.2f} usd, hand {(0.00 - 0.05) * usd:.2f} "
                      f"(-0.05 ATR at {usd:.0f} usd/ATR)"))
    del ep
    return out


def _selftest_contrast_math() -> list[tuple[str, bool, str]]:
    """The block sign-flip on a hand-made case with a known answer."""

    out: list[tuple[str, bool, str]] = []
    rng = np.random.default_rng(7)
    blocks = np.asarray([10.0, 10.0, 10.0, 10.0, 10.0, 10.0], np.float64)
    draws = 2000
    null = np.asarray([float(np.dot(blocks, rng.choice([-1.0, 1.0], size=6)))
                       for _ in range(draws)], np.float64)
    seen = float(blocks.sum())
    p = (1 + int(np.sum(np.abs(null) >= abs(seen)))) / (1 + draws)
    # Six identical positive blocks: only the all-plus and all-minus draws can
    # reach |60|, so p is about 2/64 = 0.03125 and must be small but not zero.
    out.append(_check("contrast/six_positive_blocks_p_small",
                      0.005 < p < 0.09, f"p {p:.4f}, expected around 0.031"))
    out.append(_check("contrast/flip_null_is_centred",
                      abs(float(null.mean())) < 5.0,
                      f"null mean {float(null.mean()):.3f}"))
    balanced = np.asarray([10.0, -10.0, 10.0, -10.0], np.float64)
    null2 = np.asarray([float(np.dot(balanced, rng.choice([-1.0, 1.0], size=4)))
                        for _ in range(draws)], np.float64)
    p2 = (1 + int(np.sum(np.abs(null2) >= abs(float(balanced.sum())))))/(1+draws)
    out.append(_check("contrast/a_zero_effect_is_not_significant", p2 > 0.5,
                      f"p {p2:.4f} for a zero block sum"))
    return out


def _selftest_bits() -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []
    out.append(_check("bits/causal_placements_have_none",
                      all(not HINDSIGHT_BITS[p] for p in
                          ("P0", "P1", "P2", "P3", "P4", "P7")),
                      "P0-P4 and P7 enter on information that has closed"))
    out.append(_check("bits/P5_has_one", len(HINDSIGHT_BITS["P5"]) == 1,
                      f"{HINDSIGHT_BITS['P5']}"))
    out.append(_check("bits/P6_has_two", len(HINDSIGHT_BITS["P6"]) == 2,
                      f"{HINDSIGHT_BITS['P6']}"))
    out.append(_check("bits/ceilings_add_the_episode_bit",
                      all(len(HINDSIGHT_CEILING[p]) == len(HINDSIGHT_BITS[p]) + 1
                          for p in ORACLES),
                      "per-cell-best also chooses WHICH episode is spent"))
    out.append(_check("bits/no_verdict_column",
                      "verdict" not in SELECTION_RULE,
                      "this unit registers no letters"))
    return out


def selftest() -> int:
    mutant = _mutant()
    checks: list[tuple[str, bool, str]] = []
    checks.extend(_selftest_fixture())
    checks.extend(_selftest_marks())
    checks.extend(_selftest_certs(mutant))
    checks.extend(_selftest_oracle(mutant))
    checks.extend(_selftest_contrast_math())
    checks.extend(_selftest_bits())
    width = max(len(name) for name, _ok, _detail in checks)
    bad = 0
    print(f"sweep 21 selftest  mutant {mutant or 'none'}")
    for name, ok, detail in checks:
        bad += 0 if ok else 1
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<{width}s}  {detail}")
    print(f"{len(checks) - bad}/{len(checks)} checks passed")
    return 0 if bad == 0 else 1


# --------------------------------------------------------------------------
# The reproduction gate.
# --------------------------------------------------------------------------

def check_episodes(counters: Mapping[str, int]) -> dict[str, object]:
    live = {name: int(counters.get(name, -1)) for name in REPRO_EPISODES}
    return {"banked": dict(REPRO_EPISODES), "live": live,
            "matches": bool(live == dict(REPRO_EPISODES))}


def check_p3(walk: Walk, reference: Sequence[S19.Fill]) -> dict[str, object]:
    """P3 must BE sweep 19's SLOW/ungated line: same count, same stamps."""

    mine: dict[str, set[tuple[int, int, int]]] = {a: set() for a in ASSETS}
    for shot in walk.shots["P3"]:
        mine[shot.asset].add((shot.cell, shot.side, shot.bar))
    theirs: dict[str, set[tuple[int, int, int]]] = {a: set() for a in ASSETS}
    stamps_mine: dict[str, set[int]] = {a: set() for a in ASSETS}
    stamps_theirs: dict[str, set[int]] = {a: set() for a in ASSETS}
    for row in reference:
        theirs[row.asset].add((row.cell, row.side, row.bar))
        stamps_theirs[row.asset].add(int(row.ts_ns))
    for shot in walk.shots["P3"]:
        stamps_mine[shot.asset].add(int(shot.ts_ns))
    counts = {a: len(mine[a]) for a in ASSETS}
    return {
        "banked_counts": dict(REPRO_P3_ENTRIES),
        "live_counts": counts,
        "sweep19_counts": {a: len(theirs[a]) for a in ASSETS},
        "entry_sets_match": bool(all(mine[a] == theirs[a] for a in ASSETS)),
        "stamps_match": bool(all(stamps_mine[a] == stamps_theirs[a]
                                 for a in ASSETS)),
        "counts_match_banked": bool(counts == dict(REPRO_P3_ENTRIES)),
    }


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
        "placements": list(PLACEMENTS), "labels": list(LABELS),
        "fixhold_s": FIXHOLD_S, "flip_draws": FLIP_DRAWS,
        "min_prior_days": MIN_PRIOR_DAYS,
        "q_displace": S19.Q_DISPLACE, "q_band": S19.Q_BAND,
        "contrasts": ["-".join(pair) for pair in CONTRASTS],
    }, sort_keys=True)
    shared = {
        "registered_utc": stamp, "family": FAMILY, "params": params,
        "spec_sha": report["spec_sha"], "code_sha": report["code_sha"],
        "split_sha": report["split_sha"],
        "outcome_law_sha": report["outcome_law_sha"],
        "null_seed": SEED, "parent_trial": PARENT_TRIAL,
        "selection_rule": SELECTION_RULE, "verdict": "",
    }
    rows: list[dict[str, object]] = []
    counter = 0
    measures = report["measurements"]
    ceilings = report["ceilings"]
    for name in PLACEMENTS:
        for label in LABELS:
            for asset in ASSETS:
                counter += 1
                block = measures[name][label][asset]    # type: ignore[index]
                line = dict(shared)
                line["id"] = f"{LOG_PREFIX}-{counter:03d}"
                line["rule"] = f"{name}/{label}/{asset}"
                line["days"] = len(report["scoring_days"][asset])  # type: ignore[index]
                line["coverage"] = block["coverage"]
                line["delay_med_s"] = block["median_lateness_s"]
                for tag in ("hg", "nkd", "si"):
                    line[f"{tag}_usd_day"] = None
                    line[f"mdd_{tag}"] = None
                    line[f"walls_{tag}"] = None
                    line[f"err_rate_{tag}"] = None
                tag = asset.lower()
                line[f"{tag}_usd_day"] = block["usd_per_asset_day"]
                line[f"mdd_{tag}"] = block["mdd_day_usd"]
                line[f"walls_{tag}"] = block["wall_rate"]
                line["replay_skips"] = None
                line["null_margin"] = None
                bits = HINDSIGHT_BITS[name]
                ceiling = ""
                if name in ORACLES:
                    top = ceilings[name][label][asset]  # type: ignore[index]
                    ceiling = (f"; per-cell-best ceiling "
                               f"{_show(top['usd_per_asset_day'])} usd/day = "
                               f"{_show(top['over_rung'])} rung over "
                               f"{top['n']} cells, bits "
                               f"{len(HINDSIGHT_CEILING[name])} "
                               f"({'; '.join(HINDSIGHT_CEILING[name])})")
                line["note"] = (
                    f"{name} {PLACEMENT_NAME[name]}, label {label}, {asset}: "
                    f"n {block['n']}, coverage {_show(block['coverage'])}, "
                    f"mean {_show(block['mean_cert_usd'])} median "
                    f"{_show(block['median_cert_usd'])}, P(cert>0) "
                    f"{_show(block['p_cert_positive']['rate'])} "
                    f"[{_show(block['p_cert_positive']['lo'])}, "
                    f"{_show(block['p_cert_positive']['hi'])}], usd/day "
                    f"{_show(block['usd_per_asset_day'])} = "
                    f"{_show(block['over_rung'])} rung; median lateness "
                    f"{_show(block['median_lateness_bars'])} bars; retraced "
                    f"after entry {_show(block['share_retraced_after_entry'])}; "
                    f"HINDSIGHT BITS {len(bits)}"
                    f"{'' if not bits else ' (' + '; '.join(bits) + ')'}"
                    f"{ceiling}; pricing unit, no verdict")
                rows.append(line)
    contrasts = report["contrasts"]["cells"]            # type: ignore[index]
    for left, right in CONTRASTS:
        for label in LABELS:
            for asset in ASSETS:
                counter += 1
                cell = contrasts[f"{left}-{right}/{label}/{asset}"]
                line = dict(shared)
                line["id"] = f"{LOG_PREFIX}-{counter:03d}"
                line["rule"] = f"{left}-{right}/{label}/{asset}"
                line["days"] = len(report["scoring_days"][asset])  # type: ignore[index]
                line["coverage"] = None
                line["delay_med_s"] = None
                for tag in ("hg", "nkd", "si"):
                    line[f"{tag}_usd_day"] = None
                    line[f"mdd_{tag}"] = None
                    line[f"walls_{tag}"] = None
                    line[f"err_rate_{tag}"] = None
                line[f"{asset.lower()}_usd_day"] = cell["observed_usd_day"]
                line["replay_skips"] = None
                line["null_margin"] = cell.get("p_max_adjusted")
                line["note"] = (
                    f"paired contrast {left} minus {right}, label {label}, "
                    f"{asset}: {cell['n_pairs']} paired episodes, mean "
                    f"{_show(cell['observed_mean_usd'])} usd, median "
                    f"{_show(cell['observed_median_usd'])} usd, usd/day "
                    f"{_show(cell['observed_usd_day'])}, {left} wins "
                    f"{_show(cell['share_left_wins'])}; block sign-flip null "
                    f"95% [{_show(cell.get('null_lo_usd_day'))}, "
                    f"{_show(cell.get('null_hi_usd_day'))}] usd/day, p_own "
                    f"{_show(cell.get('p_own'))}, max-stat adjusted p "
                    f"{_show(cell.get('p_max_adjusted'))} over "
                    f"{report['contrasts'].get('grid')} cells; "  # type: ignore[index]
                    f"reported as a fact, no letter")
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


def run() -> dict[str, object]:
    mutant = _mutant()
    started = time.time()
    cells, days, _skipped = S8.build_cells(ASSETS)
    explore_days = S1._explore_days(ASSETS)
    tape = S9.load_tape(cells)
    forecast = S9.forecast_variance(cells)
    plane9 = S9.build_plane(cells, forecast, tape)
    scoring = {asset: sorted(int(d) for d in explore_days[asset])[MIN_PRIOR_DAYS:]
               for asset in ASSETS}
    repro = S19.reproduce(plane9, scoring)
    if not repro["matches"]:
        raise SweepRefusal("sweep 9's occurrence plane did not reproduce; no "
                           "placement is priced past this point")
    states = S12.day_states({asset: explore_days[asset] for asset in ASSETS})
    streams, stream_counters = S14.build_streams(plane9, cells, states, "")
    causal = S14.assert_causal(streams, plane9)
    if not causal["no_outcome_in_features"]:
        raise SweepRefusal("a feature reads the outcome it is choosing over")
    deltas, flow_counters = S19.load_deltas(cells)
    episodes, ep_counters = S19.build_episodes(streams, cells, deltas)
    episode_gate = check_episodes(ep_counters)
    if not episode_gate["matches"]:
        raise SweepRefusal(f"sweep 19's episode set did not reproduce: "
                           f"{episode_gate['live']} vs {episode_gate['banked']}")
    close = build_close_plane(cells)
    fixed, hand, fixed_counters = build_fixed_plane(cells, close)
    hand_verdict = S16.hand_check_verdict(hand)
    if not hand_verdict["ok"]:
        raise SweepRefusal("the 1800 s label disagreed with the frozen scalar "
                           "outcome law")
    planes = {CLOSE: close, FIXED: fixed}
    walk = walk_placements(episodes, cells, explore_days, planes,
                           plane9.stratum_day_cells, mutant)
    if walk.counters["s19_disagreements"]:
        raise SweepRefusal("this unit's retest scan disagreed with "
                           "S19.slow_trigger on a live episode")
    reference = S19.walk_forward(episodes, cells, explore_days,
                                 S19.build_cert_plane(cells), {}, {}, {},
                                 plane9.stratum_day_cells, "")
    p3_gate = check_p3(walk, reference.fills["SLOW/ungated"])
    measures = measure(walk)
    ceilings = measure_ceilings(walk)
    detail = oracle_detail(walk)
    contrasts = contrast_grid(walk)
    matched = matched_baseline(walk)
    rank = ranking(measures, ceilings)
    return {
        "schema": "QRE2MILLSWEEP21", "spec_sha": SPEC_SHA,
        "code_sha": code_sha(), "split_sha": S1.split_sha(),
        "outcome_law_sha": S1.outcome_law_sha(), "seed": SEED,
        "mutant": mutant, "family": FAMILY, "parent_trial": PARENT_TRIAL,
        "selection_rule": SELECTION_RULE, "registered_utc": report_stamp(),
        "asset_days": {a: int(days.get(a, 0)) for a in ASSETS},
        "reproduction": repro, "episode_gate": episode_gate,
        "p3_gate": p3_gate, "stream_counters": stream_counters,
        "causality": causal, "flow_counters": flow_counters,
        "episode_counters": ep_counters, "fixed_counters": fixed_counters,
        "fixed_hand_checks": hand_verdict,
        "walk_counters": walk.counters,
        "episodes_scored": walk.episodes_scored,
        "scoring_days": {a: walk.scoring_days.get(a, []) for a in ASSETS},
        "cells_scored": walk.cells_scored,
        "measurements": measures, "ceilings": ceilings,
        "oracle_detail": detail, "contrasts": contrasts,
        "matched_baseline": matched, "ranking": rank,
        "headline": headline(rank),
        "hindsight": {"per_placement": {k: list(v) for k, v
                                        in HINDSIGHT_BITS.items()},
                      "per_ceiling": {k: list(v) for k, v
                                      in HINDSIGHT_CEILING.items()}},
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
    head = report["headline"]
    print(f"sweep 21 MAP: best causal placement {head['best_causal_placement']}"
          f"/{head['best_causal_label']} on {head['best_causal_asset']} at "
          f"{head['best_causal_usd_day']:.1f} usd/day = "
          f"{head['best_causal_over_rung']:.4f} of rung; P5 oracle ceiling "
          f"{head['p5_ceiling_over_rung']:.4f} of rung "
          f"(per-cell-best {head['p5_percell_ceiling_over_rung']:.4f}); "
          f"spec_sha {SPEC_SHA[:16]} code_sha {code_sha()[:16]} seed {SEED} "
          f"mutant {report['mutant'] or 'none'}")
    print_gate(report["reproduction"], report["episode_gate"]["live"],
               report["fixed_counters"], report["fixed_hand_checks"])
    gate = report["p3_gate"]
    print(f"  P3 vs sweep 19 SLOW/ungated: banked {gate['banked_counts']}, "
          f"live {gate['live_counts']}, sweep 19 live {gate['sweep19_counts']}; "
          f"entry sets match {gate['entry_sets_match']}, stamps match "
          f"{gate['stamps_match']}, counts match banked "
          f"{gate['counts_match_banked']}")
    print(f"\nepisodes {report['episode_counters']['episodes']} built, "
          f"{report['episodes_scored']} scored on "
          f"{[len(v) for v in report['scoring_days'].values()]} scoring days")
    print_placements(report["measurements"], report["oracle_detail"],
                     report["ceilings"])
    print_ranking(report["ranking"])
    print_contrasts(report["contrasts"])
    print_matched(report["matched_baseline"])
    print_counters(report["walk_counters"])
    write_report(report)
    print(f"\nwrote {OUT_PATH} in {report['elapsed_s']} s")
    if args.log:
        written = S1.append_log(log_rows(report))
        print(f"appended {written} hypothesis-log rows to {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
