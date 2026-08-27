#!/usr/bin/env python3
"""Two cash-blind side screens over the mill's EXPLORE cells (Sol tests 1/3).

Exploratory tier.  EXPLORE-day bytes only, read-only, no packs, no HOLD, no
teacher, no 2021/2025 bytes, no config grid, no cash anywhere.  Both screens
are ARITHMETIC: they report tables and write ``.audit/mill-sweep7a.json``.

SHARED LAWS.  60 s bars strictly before the decision (``sweep1`` lattice).
``zone(side)`` is every bar whose mid sits within ``0.15 * ATR14_prev`` of the
running session bar-mid extreme on that side, where the running extreme is
taken over bars STRICTLY BEFORE the bar under test (``sweep2.extremes``'s
convention).  Side ``+1`` (fade long) is anchored to the running LOW, side
``-1`` (fade short) to the running HIGH.  ``W(cell)`` is ``sweep2.star_cell``'s
LEGAL sign of Delta* at tau = 900 s under the max(2*cost, 100) band; ``W = 0``
is the hindsight-ambiguous class and is excluded from side error.  The terminal
extreme of a direction is the last bar setting a running extreme on it.
Entries are only ever COUNTED: the next fade-side CLEAR candidate is located
with ``sweep1.make_entry`` and never priced.  Cells without an ATR14_prev
context row are skipped.  Seed 20260827.

SCREEN A - held-retest resolution join (Sol test 1, verbatim).  After a side's
extreme quiets - no new same-direction extreme for the asset's sweep-5 selected
Q (HG 45, NKD 10, SI 30 minutes) - that side's zone is armed.  A side FIRES
when, in order:

  1. price touches the zone again (the bar mid enters it);
  2. that touch sets no new extreme;
  3. a complete bar then closes outside the zone toward the cell interior;
  4. a fade-side CLEAR candidate exists after that bar and before phase close.

Steps 1-3 are the TRIGGER (its bar is the fire bar); step 4 supplies the
counted entry.  Both sides triggering in the same minute abstains the cell.
An opposite-direction new extreme between the trigger and the candidate cancels
that pending fire, and the side re-arms on its next quiet.  A new SAME-
direction extreme relocates the zone and breaks quiet, so it also drops any
pending touch - that is the arming law, not an added rule.  One selection per
cell: the first uncancelled fire wins.

SCREEN B - cross-phase zone memory (Sol test 3).  At each phase close the cell
retains every zone that had a later touch with no extension and an interior
departure before that close (the screen-A triggers).  A held zone's price
interval is its extreme +/- 0.15 * ATR at hold time.  For phase 1 and 2 cells,
every side that is quiet at the cell's first quiet bar gets two causal counts:
the number of distinct earlier same-day phases holding an overlapping zone, and
the held-touch count inside those zones.  The lexicographically larger side is
selected; ties and no-match abstain.  The null shuffles the earlier-phase
registries across asset-days within (asset, target phase), 200 seeded draws,
with the current cell's own price and candidate history fixed.

Selftest (``--selftest``) runs on synthetic lattices only: a hand-computed
held-retest sequence, a same-minute double-trigger abstain, an opposite-
extension cancel, and a hand-computed registry match.  The mutant
``QRE2_MILL_S7A_MUTANT=retest_uses_own_bar`` computes the new-extreme flags
against a running extreme that INCLUDES the tested bar, which no bar can ever
beat, so step 2 becomes impossible to fail and the opposite-extension cancel
can never fire; it must flip a case red.  Zero era bytes are opened.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
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

import mill as M            # noqa: E402
import sweep1 as S1         # noqa: E402
import sweep2 as S2         # noqa: E402
import context as CTX       # noqa: E402

SCHEMA = "QRE2MILLSWEEP7A1"
REPORT_PATH = ROOT / ".audit/mill-sweep7a.json"
LOG_PATH = S1.LOG_PATH

SEED = S1.SEED                                    # 20260827
ASSETS = S1.ASSETS
DECIDING_ASSETS = ("NKD", "SI")                   # HG is reported, never deciding
PHASES = ("0", "1", "2")
MEMORY_PHASES = ("1", "2")

W_TAU_SECONDS = 900
W_BAR = W_TAU_SECONDS // S1.BAR_SECONDS           # 15
W_BAND = "max2cost100"
W_VARIANT = "legal"

ZONE_ATR_FRACTION = 0.15
# Sweep 5's selected quiet window per asset (stage-A branch table pick).
Q_MINUTES: dict[str, int] = {"HG": 45, "NKD": 10, "SI": 30}
# Sol's evaluation-only delay bound.  HG has no bound of its own; it borrows
# SI's purely so the reported-only column exists.
DELAY_BOUND_MINUTES: dict[str, int] = {"HG": 60, "NKD": 45, "SI": 60}

RANDOM_DRAWS = 50
NULL_DRAWS = S1.NULL_DRAWS                        # 200

COVERAGE_FLOOR: dict[str, float] = {"NKD": 0.40, "SI": 0.35}
ERROR_CEILING = 0.02
NULL_MARGIN_FLOOR = 0.05

MUTANT_ENV = "QRE2_MILL_S7A_MUTANT"
MUTANT_OWN_BAR = "retest_uses_own_bar"
S7A_MUTANTS = (MUTANT_OWN_BAR,)

FAMILY = "F3-JOIN"
PARENT_TRIAL = "sweep5-108"
SELECTION_RULE = "no-cash; coverage>side_err>joint_fail>null_margin"

MISS_NO_RETEST = "no_retest"
MISS_NO_DEPARTURE = "no_departure"
MISS_NO_CANDIDATE = "no_candidate"
MISS_CANCELLED = "cancelled"
MISS_DOUBLE = "double_fire_abstain"
MISS_NO_QUIET = "no_quiet"
MISS_BRANCHES = (MISS_NO_RETEST, MISS_NO_DEPARTURE, MISS_NO_CANDIDATE,
                 MISS_CANCELLED, MISS_DOUBLE, MISS_NO_QUIET)


class ScreenRefusal(RuntimeError):
    pass


SPEC_SHA = S1._sha_text(__doc__ or "")


def code_sha() -> str:
    return S1._sha_file(Path(__file__).resolve())


def _mutant() -> str:
    name = os.environ.get(MUTANT_ENV, "")
    if name and name not in S7A_MUTANTS:
        raise ScreenRefusal(f"unknown sweep-7a mutant: {name}")
    return name


def usd_to_mid2(asset: str) -> float:
    """Mid2 units per USD of price move (sweep 3's conversion identity)."""

    return 2e9 / float(M.ASSET_MULTIPLIER[asset])


# --------------------------------------------------------------------------
# Zone geometry: running extremes, arming, and the two zone bands.
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Geo:
    """Every per-bar zone fact one cell needs, for both sides."""

    atr_mid2: float
    half: float
    prior_low: np.ndarray      # running min over bars strictly before k
    prior_high: np.ndarray
    new_low: np.ndarray
    new_high: np.ndarray
    arm_low: np.ndarray
    arm_high: np.ndarray
    terminal_low: int
    terminal_high: int
    q_bars: int


def _prior_running(mid: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Running min/max over bars STRICTLY BEFORE each index."""

    prior_low = np.empty(len(mid), np.float64)
    prior_high = np.empty(len(mid), np.float64)
    values = mid.astype(np.float64)
    prior_low[0] = values[0]
    prior_high[0] = values[0]
    if len(values) > 1:
        prior_low[1:] = np.minimum.accumulate(values)[:-1]
        prior_high[1:] = np.maximum.accumulate(values)[:-1]
    return prior_low, prior_high


def _arm_flags(new_ext: np.ndarray, q_bars: int) -> np.ndarray:
    """Quiet for ``q_bars`` bars: the phase's first bar anchors the direction."""

    order = np.arange(len(new_ext), dtype=np.int64)
    last = np.maximum.accumulate(np.where(new_ext, order, 0))
    return (order - last) >= int(q_bars)


def geometry(rec: S1.CellRec, atr_mid2: float, mutant: str = "") -> Geo:
    values = rec.mid.astype(np.float64)
    prior_low, prior_high = _prior_running(values)
    if mutant == MUTANT_OWN_BAR:
        # The mutant scores a new extreme against a running extreme that
        # INCLUDES the tested bar, which no bar can beat: every flag dies.
        reference_low = np.minimum.accumulate(values)
        reference_high = np.maximum.accumulate(values)
    else:
        reference_low, reference_high = prior_low, prior_high
    new_low = np.zeros(len(values), bool)
    new_high = np.zeros(len(values), bool)
    new_low[1:] = values[1:] < reference_low[1:]
    new_high[1:] = values[1:] > reference_high[1:]
    q_bars = Q_MINUTES[rec.asset] * 60 // S1.BAR_SECONDS
    low_marks = np.flatnonzero(new_low)
    high_marks = np.flatnonzero(new_high)
    return Geo(
        atr_mid2=float(atr_mid2), half=float(ZONE_ATR_FRACTION * atr_mid2),
        prior_low=prior_low, prior_high=prior_high,
        new_low=new_low, new_high=new_high,
        arm_low=_arm_flags(new_low, q_bars), arm_high=_arm_flags(new_high, q_bars),
        terminal_low=int(low_marks[-1]) if len(low_marks) else -1,
        terminal_high=int(high_marks[-1]) if len(high_marks) else -1,
        q_bars=int(q_bars))


def side_arrays(geo: Geo, side: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``(prior extreme, new-extreme flags, armed flags)`` for one side."""

    if int(side) > 0:
        return geo.prior_low, geo.new_low, geo.arm_low
    return geo.prior_high, geo.new_high, geo.arm_high


def terminal_bar(geo: Geo, side: int) -> int:
    return geo.terminal_low if int(side) > 0 else geo.terminal_high


def in_zone(rec: S1.CellRec, geo: Geo, side: int, bar: int) -> bool:
    prior, _new, _arm = side_arrays(geo, side)
    return abs(float(rec.mid[bar]) - float(prior[bar])) <= geo.half


def toward_interior(rec: S1.CellRec, geo: Geo, side: int, bar: int) -> bool:
    """Outside the zone on the cell-interior side of it."""

    prior, _new, _arm = side_arrays(geo, side)
    value = float(rec.mid[bar])
    if int(side) > 0:
        return value > float(prior[bar]) + geo.half
    return value < float(prior[bar]) - geo.half


def candidate_bars(rec: S1.CellRec, side: int) -> np.ndarray:
    """Bars carrying a legal fade-side CLEAR candidate (``sweep1.make_entry``)."""

    start = rec.legal_from(side)
    flags = np.asarray(rec.ok(side), bool).copy()
    if start < 0:
        flags[:] = False
    else:
        flags[:max(1, int(start))] = False
    return np.flatnonzero(flags)


def first_candidate_after(cands: np.ndarray, bar: int) -> int:
    position = int(np.searchsorted(cands, int(bar), side="right"))
    return -1 if position >= len(cands) else int(cands[position])


# --------------------------------------------------------------------------
# The screen-A state machine.
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Trigger:
    side: int
    touch_bar: int
    depart_bar: int
    center: float


@dataclass(frozen=True, slots=True)
class HeldZone:
    side: int
    lo: float
    hi: float
    touches: int


@dataclass(frozen=True, slots=True)
class Fire:
    side: int
    trigger_bar: int
    candidate_bar: int
    touch_bar: int


@dataclass(slots=True)
class Scan:
    """One cell's screen-A machine output plus everything the metrics need."""

    position: int
    asset: str
    d8: int
    phase: str
    n: int
    rec: S1.CellRec
    geo: Geo
    star: S2.Star
    w_side: int
    triggers: tuple[Trigger, ...]
    held: tuple[HeldZone, ...]
    fire: Fire | None
    miss: str
    arm_bar: dict[int, int]
    cands: dict[int, np.ndarray]


def side_triggers(rec: S1.CellRec, geo: Geo, side: int
                  ) -> tuple[list[Trigger], dict[float, int]]:
    """Every step-1..3 completion for one side, and its per-zone touch counts."""

    prior, new_ext, armed = side_arrays(geo, side)
    bar_ok = np.asarray(rec.bar_ok, bool)
    touches: dict[float, int] = {}
    out: list[Trigger] = []
    state = "idle"
    touch_bar = -1
    center = 0.0
    for bar in range(1, rec.n):
        if bool(new_ext[bar]):
            # A same-direction extreme moves the zone and breaks quiet.
            state = "idle"
            continue
        if state == "touched":
            if bool(bar_ok[bar]) and not in_zone(rec, geo, side, bar) \
                    and toward_interior(rec, geo, side, bar):
                out.append(Trigger(int(side), touch_bar, bar, center))
                state = "armed"
            continue
        if bool(armed[bar]):
            state = "armed"
        if state == "armed" and bool(bar_ok[bar]) and in_zone(rec, geo, side, bar):
            state = "touched"
            touch_bar = bar
            center = float(prior[bar])
            touches[center] = touches.get(center, 0) + 1
    return out, touches


def resolve_fire(triggers: Sequence[Trigger], geo: Geo,
                 cands: Mapping[int, np.ndarray], base_miss: str
                 ) -> tuple[Fire | None, str]:
    """Step 4 plus the abstain/cancel clauses over the ordered triggers."""

    miss = MISS_NO_CANDIDATE if triggers else base_miss
    by_bar: dict[int, list[Trigger]] = {}
    for item in triggers:
        by_bar.setdefault(item.depart_bar, []).append(item)
    for bar in sorted(by_bar):
        group = by_bar[bar]
        if len({item.side for item in group}) > 1:
            # Both sides fire in the same minute: the whole cell abstains.
            return None, MISS_DOUBLE
        item = group[0]
        nxt = first_candidate_after(cands[item.side], bar)
        if nxt < 0:
            miss = MISS_NO_CANDIDATE
            continue
        _prior, opp_new, _arm = side_arrays(geo, -item.side)
        if bool(np.any(opp_new[bar + 1:nxt + 1])):
            # The opposite side extended before step 4 completed: re-arm.
            miss = MISS_CANCELLED
            continue
        return Fire(item.side, bar, nxt, item.touch_bar), ""
    return None, miss


def scan_cell(position: int, rec: S1.CellRec, atr_mid2: float,
              mutant: str = "") -> Scan:
    geo = geometry(rec, atr_mid2, mutant)
    star = S2.star_cell(rec, W_VARIANT, W_BAND)
    w_side = int(star.sign[W_BAR]) if rec.n > W_BAR else 0
    cands = {side: candidate_bars(rec, side) for side in (1, -1)}
    arm_bar: dict[int, int] = {}
    triggers: list[Trigger] = []
    touch_book: dict[tuple[int, float], int] = {}
    for side in (1, -1):
        _prior, _new, armed = side_arrays(geo, side)
        marks = np.flatnonzero(armed[1:]) + 1
        arm_bar[side] = int(marks[0]) if len(marks) else -1
        side_out, side_touches = side_triggers(rec, geo, side)
        triggers.extend(side_out)
        for center, count in side_touches.items():
            touch_book[(side, center)] = count
    triggers.sort(key=lambda item: (item.depart_bar, -item.side))

    # The registry keeps only zones that actually completed a departure.
    departed = {(item.side, item.center) for item in triggers}
    held = tuple(sorted(
        (HeldZone(side, center - geo.half, center + geo.half,
                  int(touch_book.get((side, center), 0)))
         for side, center in departed),
        key=lambda z: (z.side, z.lo)))

    base = MISS_NO_QUIET if max(arm_bar.values()) < 0 else MISS_NO_RETEST
    if any(count for count in touch_book.values()):
        base = MISS_NO_DEPARTURE
    fire, miss = resolve_fire(triggers, geo, cands, base)
    return Scan(position=position, asset=rec.asset, d8=int(rec.d8), phase=rec.phase,
                n=rec.n, rec=rec, geo=geo, star=star, w_side=w_side,
                triggers=tuple(triggers), held=held, fire=fire, miss=miss,
                arm_bar=arm_bar, cands=cands)


# --------------------------------------------------------------------------
# Shared per-selection arithmetic.
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Shot:
    """One counted selection: side, bar, and the facts every rate needs."""

    scan_index: int
    asset: str
    phase: str
    side: int
    bar: int
    candidate_bar: int
    side_ok: bool | None       # None when W is ambiguous
    soft_hit: bool
    later_extreme: bool
    delay_s: int
    wait_s: int

    @property
    def joint_fail(self) -> bool:
        """Sweep-5's joint law: terminal AND side, so failure is either."""

        return bool(self.later_extreme or self.side_ok is False)


def make_shot(index: int, scan: Scan, side: int, bar: int,
              candidate_bar: int) -> Shot:
    _prior, new_ext, _arm = side_arrays(scan.geo, side)
    term = terminal_bar(scan.geo, side)
    rem = scan.star.rem(side)
    return Shot(
        scan_index=index, asset=scan.asset, phase=scan.phase, side=int(side),
        bar=int(bar), candidate_bar=int(candidate_bar),
        side_ok=None if scan.w_side == 0 else bool(int(side) == scan.w_side),
        soft_hit=bool(float(rem[bar]) > 0.0),
        later_extreme=bool(np.any(new_ext[bar + 1:])),
        delay_s=int((int(bar) - term) * S1.BAR_SECONDS) if term >= 0 else 0,
        wait_s=int((int(candidate_bar) - int(bar)) * S1.BAR_SECONDS)
        if candidate_bar >= 0 else -1)


def _rate(hits: int, total: int) -> dict[str, object]:
    low, high = S1.wilson(int(hits), int(total))
    return {"hits": int(hits), "n": int(total),
            "rate": (hits / total) if total else None,
            "ci_low": low if total else None, "ci_high": high if total else None}


def _quantile(values: Sequence[float], mark: float) -> float | None:
    array = np.asarray(list(values), np.float64)
    return float(np.percentile(array, mark)) if len(array) else None


def shot_table(shots: Sequence[Shot], cells: int) -> dict[str, object]:
    rows = list(shots)
    graded = [row for row in rows if row.side_ok is not None]
    delays = [row.delay_s for row in rows]
    waits = [row.wait_s for row in rows if row.wait_s >= 0]
    return {
        "cells": int(cells), "selections": len(rows),
        "coverage": (len(rows) / cells) if cells else None,
        "graded": len(graded),
        "side_error": _rate(sum(1 for r in graded if r.side_ok is False), len(graded)),
        "soft_hit": _rate(sum(1 for r in rows if r.soft_hit), len(rows)),
        "post_new_extreme": _rate(sum(1 for r in rows if r.later_extreme), len(rows)),
        "joint_fail": _rate(sum(1 for r in graded if r.joint_fail), len(graded)),
        "joint_hit": _rate(sum(1 for r in graded if not r.joint_fail), len(graded)),
        "next_candidate": _rate(sum(1 for r in rows if r.candidate_bar >= 0), len(rows)),
        "delay_median_s": _quantile(delays, 50), "delay_p90_s": _quantile(delays, 90),
        "wait_median_s": _quantile(waits, 50), "wait_p90_s": _quantile(waits, 90),
    }


# --------------------------------------------------------------------------
# Screen A.
# --------------------------------------------------------------------------

def screen_a_shots(scans: Sequence[Scan]) -> list[Shot]:
    out: list[Shot] = []
    for index, scan in enumerate(scans):
        if scan.fire is None:
            continue
        out.append(make_shot(index, scan, scan.fire.side, scan.fire.trigger_bar,
                             scan.fire.candidate_bar))
    return out


def _bounded(shots: Sequence[Shot], bound_minutes: int) -> list[Shot]:
    limit = int(bound_minutes) * 60
    return [row for row in shots if row.delay_s <= limit]


def control_shots(scans: Sequence[Scan], fired: Sequence[Shot], kind: str,
                  rng: np.random.Generator | None = None) -> list[Shot]:
    """Controls on the identical cells that screen A fired."""

    out: list[Shot] = []
    for row in fired:
        scan = scans[row.scan_index]
        if kind == "side_swapped":
            side, bar = -row.side, row.bar
        elif kind == "first_quiet":
            arms = {side: bar for side, bar in scan.arm_bar.items() if bar >= 0}
            if len(arms) != len(set(arms.values())):
                continue                      # a tie in the quiet race abstains
            side = min(arms, key=lambda s: arms[s])
            bar = arms[side]
        elif kind == "random_eligible":
            eligible = [side for side, bar in scan.arm_bar.items() if bar >= 0]
            if not eligible or rng is None:
                continue
            side = int(eligible[int(rng.integers(len(eligible)))])
            bar = scan.arm_bar[side]
        else:
            raise ScreenRefusal(f"unknown control: {kind}")
        out.append(make_shot(row.scan_index, scan, side, bar,
                             first_candidate_after(scan.cands[side], bar)))
    return out


def screen_a(scans: Sequence[Scan]) -> dict[str, object]:
    shots = screen_a_shots(scans)
    report: dict[str, object] = {"q_minutes": dict(Q_MINUTES),
                                 "delay_bound_minutes": dict(DELAY_BOUND_MINUTES),
                                 "by_asset": {}, "by_phase": {}, "controls": {}}
    for asset in ASSETS:
        cells = [s for s in scans if s.asset == asset]
        rows = [r for r in shots if r.asset == asset]
        block = shot_table(rows, len(cells))
        block["opportunity_coverage"] = (
            sum(1 for s in cells if s.triggers) / len(cells)) if cells else None
        block["entry_available_coverage"] = block["coverage"]
        misses = {name: sum(1 for s in cells if s.miss == name)
                  for name in MISS_BRANCHES}
        block["miss_branches"] = misses
        bounded = _bounded(rows, DELAY_BOUND_MINUTES[asset])
        inside = shot_table(bounded, len(cells))
        inside["excluded_late"] = len(rows) - len(bounded)
        block["delay_bounded"] = inside
        report["by_asset"][asset] = block
        for phase in PHASES:
            pcells = [s for s in cells if s.phase == phase]
            prows = [r for r in rows if r.phase == phase]
            pblock = shot_table(prows, len(pcells))
            pblock["opportunity_coverage"] = (
                sum(1 for s in pcells if s.triggers) / len(pcells)) if pcells else None
            report["by_phase"][f"{asset}/{phase}"] = pblock
    rng = np.random.default_rng(SEED)
    for kind in ("first_quiet", "side_swapped"):
        rows = control_shots(scans, shots, kind)
        report["controls"][kind] = {
            asset: shot_table([r for r in rows if r.asset == asset],
                              sum(1 for s in scans if s.asset == asset))
            for asset in ASSETS}
    draws: list[list[Shot]] = [control_shots(scans, shots, "random_eligible", rng)
                               for _ in range(RANDOM_DRAWS)]
    report["controls"]["random_eligible"] = {
        asset: _draw_summary([[r for r in draw if r.asset == asset] for draw in draws])
        for asset in ASSETS}
    report["controls"]["random_draws"] = RANDOM_DRAWS
    return report


def _draw_summary(draws: Sequence[Sequence[Shot]]) -> dict[str, object]:
    """Mean over seeded draws of the rates a single draw would report."""

    keys = ("side_error", "soft_hit", "joint_fail", "post_new_extreme")
    stacks: dict[str, list[float]] = {name: [] for name in keys}
    counts: list[int] = []
    for draw in draws:
        table = shot_table(draw, 1)
        counts.append(len(draw))
        for name in keys:
            value = table[name]["rate"]
            if value is not None:
                stacks[name].append(float(value))
    return {"selections_mean": float(np.mean(counts)) if counts else 0.0,
            **{name: (float(np.mean(values)) if values else None)
               for name, values in stacks.items()}}


# --------------------------------------------------------------------------
# Screen B: cross-phase zone memory.
# --------------------------------------------------------------------------

def _overlaps(zone: HeldZone, lo: float, hi: float) -> bool:
    return not (zone.hi < lo or hi < zone.lo)


def side_counts(scan: Scan, side: int, bar: int,
                registry: Mapping[str, tuple[HeldZone, ...]]) -> tuple[int, int]:
    """``(distinct earlier phases with an overlapping held zone, held touches)``."""

    prior, _new, _arm = side_arrays(scan.geo, side)
    centre = float(prior[bar])
    lo, hi = centre - scan.geo.half, centre + scan.geo.half
    phases = 0
    touches = 0
    for _phase, zones in sorted(registry.items()):
        matched = [z for z in zones if _overlaps(z, lo, hi)]
        if matched:
            phases += 1
            touches += sum(z.touches for z in matched)
    return phases, touches


@dataclass(frozen=True, slots=True)
class Selection:
    shot: Shot
    provenance: str


def select_memory(index: int, scan: Scan,
                  registry: Mapping[str, tuple[HeldZone, ...]]
                  ) -> Selection | None:
    arms = {side: bar for side, bar in scan.arm_bar.items() if bar >= 0}
    if len(arms) < 2:
        return None
    # "Each current quiet side" needs both sides quiet for the comparison to
    # exist, so the decision bar is the first bar at which both zones are armed.
    bar = max(arms.values())
    scored = {side: side_counts(scan, side, bar, registry) for side in (1, -1)}
    ranked = sorted(scored.items(), key=lambda item: (item[1], item[0]), reverse=True)
    best_side, best = ranked[0]
    if best == (0, 0):
        return None
    if len(ranked) > 1 and ranked[1][1] == best:
        return None                          # a tie abstains
    provenance = "phase_match"
    if len(ranked) > 1 and ranked[1][1][0] == best[0]:
        provenance = "touch_tiebreak"
    shot = make_shot(index, scan, best_side, bar,
                     first_candidate_after(scan.cands[best_side], bar))
    return Selection(shot, provenance)


def registries(scans: Sequence[Scan]) -> dict[tuple[str, int, str],
                                              dict[str, tuple[HeldZone, ...]]]:
    """Per target cell, the held zones of its strictly earlier same-day phases."""

    by_day: dict[tuple[str, int], dict[str, tuple[HeldZone, ...]]] = {}
    for scan in scans:
        by_day.setdefault((scan.asset, scan.d8), {})[scan.phase] = scan.held
    out: dict[tuple[str, int, str], dict[str, tuple[HeldZone, ...]]] = {}
    for scan in scans:
        day = by_day[(scan.asset, scan.d8)]
        out[(scan.asset, scan.d8, scan.phase)] = {
            phase: zones for phase, zones in day.items() if phase < scan.phase}
    return out


def screen_b(scans: Sequence[Scan]) -> dict[str, object]:
    book = registries(scans)
    picks: list[Selection] = []
    for index, scan in enumerate(scans):
        if scan.phase not in MEMORY_PHASES:
            continue
        pick = select_memory(index, scan, book[(scan.asset, scan.d8, scan.phase)])
        if pick is not None:
            picks.append(pick)
    report: dict[str, object] = {"by_asset": {}, "by_asset_phase": {},
                                 "null_draws": NULL_DRAWS, "null": {}}
    for asset in ASSETS:
        cells = [s for s in scans if s.asset == asset and s.phase in MEMORY_PHASES]
        rows = [p for p in picks if p.shot.asset == asset]
        block = shot_table([p.shot for p in rows], len(cells))
        block["provenance"] = {
            name: sum(1 for p in rows if p.provenance == name)
            for name in ("phase_match", "touch_tiebreak")}
        report["by_asset"][asset] = block
        for phase in MEMORY_PHASES:
            pcells = [s for s in cells if s.phase == phase]
            prows = [p for p in rows if p.shot.phase == phase]
            pblock = shot_table([p.shot for p in prows], len(pcells))
            pblock["provenance"] = {
                name: sum(1 for p in prows if p.provenance == name)
                for name in ("phase_match", "touch_tiebreak")}
            report["by_asset_phase"][f"{asset}/{phase}"] = pblock
    report["null"] = screen_b_null(scans, picks)
    return report


def _joint_hit_rate(shots: Sequence[Shot]) -> float | None:
    graded = [row for row in shots if row.side_ok is not None]
    if not graded:
        return None
    return float(sum(1 for row in graded if not row.joint_fail) / len(graded))


def screen_b_null(scans: Sequence[Scan],
                  picks: Sequence[Selection]) -> dict[str, object]:
    """Shuffle earlier-phase registries within (asset, target phase)."""

    book = registries(scans)
    targets: dict[tuple[str, str], list[int]] = {}
    for index, scan in enumerate(scans):
        if scan.phase in MEMORY_PHASES:
            targets.setdefault((scan.asset, scan.phase), []).append(index)
    rng = np.random.default_rng(SEED)
    real = {asset: _joint_hit_rate([p.shot for p in picks if p.shot.asset == asset])
            for asset in ASSETS}
    draws: dict[str, list[float]] = {asset: [] for asset in ASSETS}
    for _draw in range(NULL_DRAWS):
        shots: dict[str, list[Shot]] = {asset: [] for asset in ASSETS}
        for (asset, phase), members in sorted(targets.items()):
            order = rng.permutation(len(members))
            for slot, index in enumerate(members):
                scan = scans[index]
                donor = scans[members[int(order[slot])]]
                pick = select_memory(index, scan,
                                     book[(donor.asset, donor.d8, donor.phase)])
                if pick is not None:
                    shots[asset].append(pick.shot)
        for asset in ASSETS:
            value = _joint_hit_rate(shots[asset])
            if value is not None:
                draws[asset].append(value)
    out: dict[str, object] = {}
    for asset in ASSETS:
        values = draws[asset]
        mean = float(np.mean(values)) if values else None
        out[asset] = {
            "real_joint_hit": real[asset],
            "null_joint_hit_mean": mean,
            "null_joint_hit_p95": _quantile(values, 95),
            "margin": (None if real[asset] is None or mean is None
                       else float(real[asset] - mean)),
            "draws_scored": len(values)}
    return out


# --------------------------------------------------------------------------
# The decision table.
# --------------------------------------------------------------------------

def decision_table(report: Mapping[str, object]) -> dict[str, object]:
    out: dict[str, object] = {}
    for asset in ASSETS:
        deciding = asset in DECIDING_ASSETS
        block = report["screen_a"]["by_asset"][asset]
        fired: list[str] = []
        floor = COVERAGE_FLOOR.get(asset)
        coverage = block["entry_available_coverage"]
        if floor is not None and (coverage is None or coverage < floor):
            fired.append(f"coverage<{floor:.2f}")
        for name in ("side_error", "joint_fail"):
            rate = block[name]["rate"]
            if rate is not None and rate > ERROR_CEILING:
                fired.append(f"{name}>{ERROR_CEILING}")
        out[f"A/{asset}"] = {
            "deciding": deciding, "coverage": coverage,
            "side_error": block["side_error"]["rate"],
            "side_error_ci_high": block["side_error"]["ci_high"],
            "joint_fail": block["joint_fail"]["rate"],
            "joint_fail_ci_high": block["joint_fail"]["ci_high"],
            "bounds_fired": fired,
            "verdict": ("REPORTED" if not deciding
                        else ("KILL" if fired else "SURVIVES"))}
        bblock = report["screen_b"]["by_asset"][asset]
        bfired: list[str] = []
        bcov = bblock["coverage"]
        if floor is not None and (bcov is None or bcov < floor):
            bfired.append(f"coverage<{floor:.2f}")
        for name in ("side_error", "joint_fail"):
            rate = bblock[name]["rate"]
            if rate is not None and rate > ERROR_CEILING:
                bfired.append(f"{name}>{ERROR_CEILING}")
        margin = report["screen_b"]["null"][asset]["margin"]
        if margin is None or margin < NULL_MARGIN_FLOOR:
            bfired.append(f"null_margin<{NULL_MARGIN_FLOOR}")
        out[f"B/{asset}"] = {
            "deciding": deciding, "coverage": bcov,
            "side_error": bblock["side_error"]["rate"],
            "side_error_ci_high": bblock["side_error"]["ci_high"],
            "joint_fail": bblock["joint_fail"]["rate"],
            "joint_fail_ci_high": bblock["joint_fail"]["ci_high"],
            "null_margin": margin, "bounds_fired": bfired,
            "verdict": ("REPORTED" if not deciding
                        else ("KILL" if bfired else "SURVIVES"))}
    return out


# --------------------------------------------------------------------------
# Loading.
# --------------------------------------------------------------------------

def load_scans(assets: Sequence[str], mutant: str = ""
               ) -> tuple[list[Scan], dict[str, int], dict[str, int]]:
    records, days = S1.load_cache()
    records = [rec for rec in records if rec.asset in assets]
    store = CTX.ContextStore()
    scans: list[Scan] = []
    skipped: dict[str, int] = {asset: 0 for asset in assets}
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
        scans.append(scan_cell(position, rec, atr_usd * usd_to_mid2(rec.asset),
                               mutant))
    return scans, {k: int(v) for k, v in days.items() if k in assets}, skipped


# --------------------------------------------------------------------------
# Printing.
# --------------------------------------------------------------------------

def _pct(value: object) -> str:
    return "     -" if value is None else f"{float(value):6.3f}"


def _num(value: object, width: int = 7) -> str:
    return " " * (width - 1) + "-" if value is None else f"{float(value):{width}.0f}"


def print_screen_a(block: Mapping[str, object]) -> None:
    print("\n== SCREEN A held-retest resolution join (per asset)")
    print("asset cells  opp_cov  ent_cov  n  side_err  ci_hi  soft  postX "
          "joint_f  ci_hi  delay_med  delay_p90  wait_med")
    for asset in ASSETS:
        row = block["by_asset"][asset]
        print(f"{asset:5s} {row['cells']:5d}  {_pct(row['opportunity_coverage'])}  "
              f"{_pct(row['entry_available_coverage'])} {row['selections']:3d} "
              f"  {_pct(row['side_error']['rate'])} {_pct(row['side_error']['ci_high'])} "
              f"{_pct(row['soft_hit']['rate'])} {_pct(row['post_new_extreme']['rate'])} "
              f" {_pct(row['joint_fail']['rate'])} {_pct(row['joint_fail']['ci_high'])} "
              f"{_num(row['delay_median_s'], 10)} {_num(row['delay_p90_s'], 10)} "
              f"{_num(row['wait_median_s'], 9)}")
    print("\n-- miss branches (cells)")
    print("asset " + " ".join(f"{name:>18s}" for name in MISS_BRANCHES))
    for asset in ASSETS:
        misses = block["by_asset"][asset]["miss_branches"]
        print(f"{asset:5s} " + " ".join(f"{misses[name]:18d}" for name in MISS_BRANCHES))
    print("\n-- delay-bounded recompute (fires within Sol's bound of the true terminal)")
    print("asset bound_min  excl  n  ent_cov  side_err  soft  joint_f")
    for asset in ASSETS:
        row = block["by_asset"][asset]["delay_bounded"]
        print(f"{asset:5s} {DELAY_BOUND_MINUTES[asset]:9d} {row['excluded_late']:5d} "
              f"{row['selections']:3d}  {_pct(row['coverage'])}  "
              f"{_pct(row['side_error']['rate'])} {_pct(row['soft_hit']['rate'])} "
              f"{_pct(row['joint_fail']['rate'])}")
    print("\n-- per phase")
    print("cell    cells  opp_cov  ent_cov  n  side_err  soft  postX  joint_f")
    for key in sorted(block["by_phase"]):
        row = block["by_phase"][key]
        print(f"{key:7s} {row['cells']:5d}  {_pct(row['opportunity_coverage'])}  "
              f"{_pct(row['coverage'])} {row['selections']:3d}  "
              f"{_pct(row['side_error']['rate'])} {_pct(row['soft_hit']['rate'])} "
              f"{_pct(row['post_new_extreme']['rate'])} "
              f"{_pct(row['joint_fail']['rate'])}")
    print("\n-- controls on the identical fired cells")
    print("control            asset  n  side_err  soft  postX  joint_f")
    for kind in ("first_quiet", "side_swapped"):
        for asset in ASSETS:
            row = block["controls"][kind][asset]
            print(f"{kind:18s} {asset:5s} {row['selections']:3d}  "
                  f"{_pct(row['side_error']['rate'])} {_pct(row['soft_hit']['rate'])} "
                  f"{_pct(row['post_new_extreme']['rate'])} "
                  f"{_pct(row['joint_fail']['rate'])}")
    for asset in ASSETS:
        row = block["controls"]["random_eligible"][asset]
        print(f"{'random_eligible':18s} {asset:5s} "
              f"{row['selections_mean']:5.1f}  {_pct(row['side_error'])} "
              f"{_pct(row['soft_hit'])} {_pct(row['post_new_extreme'])} "
              f"{_pct(row['joint_fail'])}")


def print_screen_b(block: Mapping[str, object]) -> None:
    print("\n== SCREEN B cross-phase zone memory (phases 1-2)")
    print("cell    cells  sel_cov  n  side_err  ci_hi  soft  postX  joint_f  "
          "next_cand  delay_med  phase_match  touch_tb")
    for asset in ASSETS:
        for key in (asset, *(f"{asset}/{phase}" for phase in MEMORY_PHASES)):
            row = (block["by_asset"][asset] if key == asset
                   else block["by_asset_phase"][key])
            prov = row["provenance"]
            print(f"{key:7s} {row['cells']:5d}  {_pct(row['coverage'])} "
                  f"{row['selections']:3d}  {_pct(row['side_error']['rate'])} "
                  f"{_pct(row['side_error']['ci_high'])} "
                  f"{_pct(row['soft_hit']['rate'])} "
                  f"{_pct(row['post_new_extreme']['rate'])} "
                  f"{_pct(row['joint_fail']['rate'])}  "
                  f"{_pct(row['next_candidate']['rate'])} "
                  f"{_num(row['delay_median_s'], 10)} {prov['phase_match']:12d} "
                  f"{prov['touch_tiebreak']:9d}")
    print("\n-- registry-shuffle null (200 seeded draws, within asset x target phase)")
    print("asset  real_joint  null_mean  null_p95  margin  draws")
    for asset in ASSETS:
        row = block["null"][asset]
        print(f"{asset:5s}  {_pct(row['real_joint_hit'])}     "
              f"{_pct(row['null_joint_hit_mean'])}    {_pct(row['null_joint_hit_p95'])} "
              f"{_pct(row['margin'])} {row['draws_scored']:6d}")


def print_decision(block: Mapping[str, object]) -> None:
    print("\n== DECISION TABLE (Sol kill bounds; HG reported, never deciding)")
    print("screen/asset  deciding  coverage  side_err(ci_hi)  joint_f(ci_hi)  "
          "null_margin  verdict  bounds_fired")
    for key in sorted(block):
        row = block[key]
        margin = row.get("null_margin")
        print(f"{key:13s} {str(row['deciding']):9s} {_pct(row['coverage'])}  "
              f"{_pct(row['side_error'])}({_pct(row['side_error_ci_high'])})  "
              f"{_pct(row['joint_fail'])}({_pct(row['joint_fail_ci_high'])})  "
              f"{_pct(margin) if margin is not None else '     -'}  "
              f"{row['verdict']:9s} {','.join(row['bounds_fired']) or '-'}")


# --------------------------------------------------------------------------
# Hypothesis log.
# --------------------------------------------------------------------------

def log_rows(report: Mapping[str, object]) -> list[dict[str, object]]:
    stamp = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    shared = {
        "registered_utc": stamp, "spec_sha": SPEC_SHA, "code_sha": code_sha(),
        "split_sha": S1.split_sha(), "outcome_law_sha": S1.outcome_law_sha(),
        "null_seed": SEED, "parent_trial": PARENT_TRIAL,
        "selection_rule": SELECTION_RULE, "verdict": "",
        "days": sum(report["asset_days"].values()),
    }
    miss = {"HG": "err_rate_hg", "NKD": "err_rate_nkd", "SI": "err_rate_si"}
    rows: list[dict[str, object]] = []
    counter = 0
    for asset in ASSETS:
        a_block = report["screen_a"]["by_asset"][asset]
        counter += 1
        rows.append({
            **shared, "id": f"sweep7a-{counter:03d}", "family": FAMILY,
            "rule": f"{asset}/A-HELD-RETEST",
            "params": json.dumps([Q_MINUTES[asset], ZONE_ATR_FRACTION,
                                  DELAY_BOUND_MINUTES[asset], "join"]),
            "coverage": a_block["entry_available_coverage"],
            "delay_med_s": a_block["delay_median_s"],
            miss[asset]: a_block["joint_fail"]["rate"],
            "note": f"screen-A n={a_block['selections']} "
                    f"soft={a_block['soft_hit']['rate']}"[:60]})
        for kind in ("first_quiet", "side_swapped"):
            control = report["screen_a"]["controls"][kind][asset]
            counter += 1
            rows.append({
                **shared, "id": f"sweep7a-{counter:03d}", "family": FAMILY,
                "rule": f"{asset}/A-CTRL-{kind}",
                "params": json.dumps([Q_MINUTES[asset], ZONE_ATR_FRACTION, kind]),
                "coverage": control["coverage"],
                "delay_med_s": control["delay_median_s"],
                miss[asset]: control["joint_fail"]["rate"],
                "note": f"screen-A control {kind}"[:60]})
        b_block = report["screen_b"]["by_asset"][asset]
        counter += 1
        rows.append({
            **shared, "id": f"sweep7a-{counter:03d}", "family": FAMILY,
            "rule": f"{asset}/B-ZONE-MEMORY",
            "params": json.dumps([Q_MINUTES[asset], ZONE_ATR_FRACTION,
                                  NULL_DRAWS, "p1p2"]),
            "coverage": b_block["coverage"], "delay_med_s": b_block["delay_median_s"],
            miss[asset]: b_block["joint_fail"]["rate"],
            "null_margin": report["screen_b"]["null"][asset]["margin"],
            "note": f"screen-B n={b_block['selections']} "
                    f"soft={b_block['soft_hit']['rate']}"[:60]})
    return rows


# --------------------------------------------------------------------------
# Selftest.
# --------------------------------------------------------------------------

def _cell(mid: Sequence[float], *, d8: int = 20220301, phase: str = "0",
          legal_p: int = 1, legal_m: int = 1, asset: str = "HG",
          ok_from: int = 1) -> S1.CellRec:
    """A synthetic cell on ``sweep2._synthetic_cell``'s shape, day/phase-tagged."""

    n = len(mid)
    ok = [index >= ok_from for index in range(n)]
    rec = S2._synthetic_cell(mid, [10.0] * n, [10.0] * n, ok, ok,
                             legal_p, legal_m, asset=asset)
    return S1.CellRec(**{**{name: getattr(rec, name)
                            for name in rec.__slots__},
                         "d8": int(d8), "phase": str(phase),
                         "text": f"{asset}/{d8}/{phase}/0"})


def _hold_series() -> list[float]:
    """Q=45 (HG).  Low 100 at bar 1; zone half = 15 (ATR 100 -> 0.15*100).

    Bars 2-46 sit at 200 (quiet; armed from bar 46).  Bar 47 retests at 110
    (inside [100, 115], no new low).  Bar 48 departs to 160 (outside, interior).
    The trigger bar is 48 and the next candidate is bar 49.
    """

    return [300.0, 100.0] + [200.0] * 45 + [110.0, 160.0, 160.0, 160.0]


def _two_sided_series() -> list[float]:
    """Both sides complete a trigger, and they cannot land on the same bar.

    Low 100 at bar 1, high 300 at bar 2, bars 3-47 at 200; half = 20.  Bar 48
    retests the low zone [80, 120] at 110 and bar 49 departs to 160, so the low
    trigger is bar 49.  Bar 50 retests the high zone [280, 320] at 290 and bar
    51 departs to 250, so the high trigger is bar 51.  The two departures can
    never coincide: a shared departure bar would have to be above low+half and
    below high-half while the bar before it was inside both bands, which is a
    contradiction.  The same-minute abstain is therefore exercised directly
    against :func:`resolve_fire`.
    """

    return [200.0, 100.0, 300.0] + [200.0] * 45 + [110.0, 160.0, 290.0, 250.0, 250.0]


def _cancel_series() -> list[float]:
    """The hold series, then a new HIGH between the trigger and the candidate.

    Same low-side sequence as ``_hold_series`` (trigger at bar 48), but the
    only candidate bar is 51 and bar 49 prints 400 - a new running high, which
    is the opposite-side extension.  The pending fire is cancelled.
    """

    return [300.0, 100.0] + [200.0] * 45 + [110.0, 160.0, 400.0, 400.0, 400.0]


def selftest() -> int:
    mutant = _mutant()
    cases: list[tuple[str, bool, str]] = []
    atr = 100.0

    hold = _cell(_hold_series())
    scan = scan_cell(0, hold, atr, mutant)
    cases.append((
        "hold_retest_fires_at_the_hand_computed_bar",
        scan.fire is not None and scan.fire.side == 1
        and scan.fire.trigger_bar == 48 and scan.fire.touch_bar == 47
        and scan.fire.candidate_bar == 49,
        f"fire={scan.fire} miss={scan.miss!r} triggers={scan.triggers}"))
    cases.append((
        "hold_retest_registers_one_held_zone",
        len(scan.held) == 1 and scan.held[0].side == 1
        and scan.held[0].lo == 85.0 and scan.held[0].hi == 115.0
        and scan.held[0].touches == 1,
        f"held={scan.held}"))

    both = _cell(_two_sided_series())
    bscan = scan_cell(0, both, 133.33333333333334, mutant)
    bars = {t.side: t.depart_bar for t in bscan.triggers}
    cases.append((
        "two_sided_triggers_land_on_different_bars",
        bars == {1: 49, -1: 51},
        f"triggers={bscan.triggers}"))
    empty = geometry(_cell([100.0] * 4), 1.0, mutant)
    pair = (Trigger(1, 6, 7, 100.0), Trigger(-1, 6, 7, 300.0))
    fire, why = resolve_fire(pair, empty,
                             {1: np.array([8]), -1: np.array([8])},
                             MISS_NO_RETEST)
    cases.append((
        "same_minute_double_trigger_abstains",
        fire is None and why == MISS_DOUBLE,
        f"fire={fire} miss={why!r}"))

    cancel = _cell(_cancel_series(), ok_from=51, legal_p=51, legal_m=51)
    cscan = scan_cell(0, cancel, atr, mutant)
    cases.append((
        "opposite_extension_cancels_the_pending_fire",
        cscan.fire is None and cscan.miss == MISS_CANCELLED
        and any(t.depart_bar == 48 and t.side == 1 for t in cscan.triggers),
        f"fire={cscan.fire} miss={cscan.miss!r} triggers={cscan.triggers}"))

    # Registry: phase 0 holds the low zone [85, 115]; the phase-1 cell's low
    # side quiets with its own zone at [85, 115], which overlaps, so the +1
    # side carries (1 phase, 1 touch) and the -1 side (0, 0).
    early = _cell(_hold_series(), phase="0")
    late = _cell(_hold_series(), phase="1")
    escan, lscan = scan_cell(0, early, atr, mutant), scan_cell(1, late, atr, mutant)
    book = registries([escan, lscan])
    counts_p = side_counts(lscan, 1, lscan.arm_bar[1],
                           book[(late.asset, late.d8, "1")])
    counts_m = side_counts(lscan, -1, lscan.arm_bar[-1],
                           book[(late.asset, late.d8, "1")])
    pick = select_memory(1, lscan, book[(late.asset, late.d8, "1")])
    cases.append((
        "registry_match_selects_the_remembered_side",
        counts_p == (1, 1) and counts_m == (0, 0)
        and pick is not None and pick.shot.side == 1
        and pick.provenance == "phase_match",
        f"counts+={counts_p} counts-={counts_m} pick={pick}"))

    cases.append((
        "wilson_and_rate_plumbing",
        _rate(1, 4)["rate"] == 0.25 and _rate(0, 0)["rate"] is None,
        f"{_rate(1, 4)}"))

    failed = [name for name, ok, _why in cases if not ok]
    for name, ok, why in cases:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  {why}"))
    tag = f" (mutant {mutant})" if mutant else ""
    print(f"\nselftest{tag}: {len(cases) - len(failed)}/{len(cases)} green")
    if mutant and not failed:
        print(f"REFUSED: mutant {mutant} left every case green")
        return 1
    return 1 if failed and not mutant else 0


# --------------------------------------------------------------------------
# Entry point.
# --------------------------------------------------------------------------

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="mill sweep 7a: two side screens")
    parser.add_argument("stage", nargs="?", default="all",
                        choices=("screen-a", "screen-b", "log", "all"))
    parser.add_argument("--assets", default="HG,NKD,SI")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    mutant = _mutant()
    assets = tuple(name.strip().upper() for name in args.assets.split(",")
                   if name.strip())
    started = time.monotonic()
    scans, days, skipped = load_scans(assets, mutant)
    report: dict[str, object] = {
        "schema": SCHEMA, "spec_sha": SPEC_SHA, "code_sha": code_sha(),
        "split_sha": S1.split_sha(), "outcome_law_sha": S1.outcome_law_sha(),
        "parent_trial": PARENT_TRIAL, "mutant": mutant, "seed": SEED,
        "asset_days": dict(days), "skipped_no_atr": dict(skipped),
        "cells": {asset: sum(1 for s in scans if s.asset == asset)
                  for asset in assets},
    }
    report["screen_a"] = screen_a(scans)
    print_screen_a(report["screen_a"])
    report["screen_b"] = screen_b(scans)
    print_screen_b(report["screen_b"])
    report["decision"] = decision_table(report)
    print_decision(report["decision"])
    if args.stage in ("log", "all"):
        rows = log_rows(report)
        written = S1.append_log(rows)
        report["log"] = {"rows_appended": written, "first_id": rows[0]["id"],
                         "last_id": rows[-1]["id"],
                         "registered_utc": rows[0]["registered_utc"]}
        print(f"\nlog: appended {written} rows to {LOG_PATH}")
    report["wall_seconds"] = round(time.monotonic() - started, 2)
    REPORT_PATH.write_text(json.dumps(report, indent=1, sort_keys=True,
                                      default=float) + "\n")
    print(f"\nwrote {REPORT_PATH} wall={report['wall_seconds']}s "
          f"cells={len(scans)} spec_sha={SPEC_SHA[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
