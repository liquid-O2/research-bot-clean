#!/usr/bin/env python3
"""Two cheap no-cash idea screens over the mill's EXPLORE cells (I1 and I4).

Exploratory tier.  EXPLORE-day bytes only, read-only, no packs, no HOLD,
no teacher, no 2021/2025 bytes, no config grid, no selection.  Both screens
are ARITHMETIC: they report tables and write ``.audit/mill-ideascreen.json``.

SCREEN I1 - prior-phase inheritance (side prior).  For every EXPLORE cell
with a defined winner side ``W`` (sweep 2's ``star_cell``: sign of Delta* at
tau = 900 s, LEGAL variant, max(2*cost, 100) ambiguity band; sweep 4's
``winner_side`` law), four causal predictors known at the cell's phase open:

  a  prior completed phase, same day: sign(close mid - open mid) of that
     phase.  Undefined for a day's first phase, and for any cell whose
     previous cell by phase-open does not close at or before this open.
  b  prior locked day: sign(session_close_mid2 - session_open_mid2) of the
     strictly-prior levels row served by ``context.ContextStore``.
  c  overnight gap: sign(this phase's open mid - prior day session close),
     day's first phase only.
  d  prior phase's range position of close: +1 when
     (close - low) / (high - low) > 0.5, else -1, over the prior phase's
     valid bar mids; undefined when high == low.
  a_and_d  the AND-agreement: defined only on cells where a and d are both
     defined AND equal; the shared value is the prediction.

Agreement is ``mean(predictor == W)`` with a Wilson 95% interval
(``sweep1.wilson``).  Rows whose Wilson lower bound exceeds 0.55 are flagged.

SCREEN I4 - both-extremes sequential ORACLE/DIAGNOSTIC arithmetic.  Not a
policy: the ORACLE variant uses the true terminal extreme bars, which are
knowable only in hindsight.  Per cell, on the 60 s cert lattices:

  terminal bar per direction = the last bar setting a new running extreme of
  the bar mid on that direction (``sweep2.extremes``, sweep 4's
  ``terminal_extreme_bar`` law; -1 when the direction never printed one).
  ORACLE leg 1 enters at the earlier of the two terminal bars, on that
  extreme's FADE side (new running minimum -> long, new running maximum ->
  short), under the bar-close entry law (``sweep1.make_entry``: declaration
  at bar close, entry quote the last trusted row strictly before it, frozen
  cost, formed same-side CLEAR candidate required, certifiable).  If leg 1's
  outcome is a wall, leg 2 enters at the OTHER direction's terminal bar when
  that bar's close is strictly later than leg 1's exit; otherwise skipped.
  NAIVE leg 1 enters at the first QUIETED extreme instead: the first bar at
  which some direction has printed no new extreme for 20 minutes (the phase's
  first bar anchors both directions).  After a leg-1 wall, NAIVE leg 2 enters
  at the other direction's first quiet bar whose close is strictly later than
  leg 1's exit.

Selftest (``--selftest``) runs on synthetic lattices only: hand-computed I1
agreement over three synthetic cells, a hand-computed I4 two-leg sequence
(leg 1 walls, leg 2 enters), and the mutant ``QRE2_MILL_IDEA_MUTANT=
screen_peeks`` (predictor ``a`` read from the cell's OWN phase instead of the
prior phase) which must flip an I1 case red.  Zero era bytes are opened.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
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

SCHEMA = "QRE2MILLIDEASCREEN1"
REPORT_PATH = ROOT / ".audit/mill-ideascreen.json"

W_TAU_SECONDS = 900
W_BAR = W_TAU_SECONDS // S1.BAR_SECONDS          # 15
QUIET_SECONDS = 1200
QUIET_BARS = QUIET_SECONDS // S1.BAR_SECONDS     # 20
PORTFOLIO_ENTRY_CAP = 12

MUTANT_ENV = "QRE2_MILL_IDEA_MUTANT"
MUTANT_PEEKS = "screen_peeks"
IDEA_MUTANTS = (MUTANT_PEEKS,)

PREDICTORS = ("a_prior_phase_sign", "b_prior_day_sign", "c_overnight_gap",
              "d_prior_phase_rangepos", "a_and_d")

SPEC = f"""{SCHEMA}
tier=exploratory; explore-only; no-cash screens; can kill, cannot promote.
W(cell) = sign(Delta*(tau=900s)) under sweep2.star_cell(variant=legal,
  band=max2cost100); cells with n<=15 bars or not sharp at bar 15 are dropped.
I1 predictors (all causal at the cell's phase open): a = sign(close mid -
  open mid) of the prior COMPLETED same-day phase (previous cell by
  phase_open whose phase_close <= this phase_open); b = sign(session close -
  session open) of the strictly-prior locked day served by
  context.ContextStore.context_for; c = sign(this phase's open mid - prior
  day session close), day's first phase only; d = +1 when (close-low)/
  (high-low) > 0.5 over the prior phase's valid bar mids else -1, undefined
  at high==low; a_and_d defined only where a and d are both defined and
  equal.  Mids are bar mid2 at valid bars; agreement = mean(pred == W) with a
  Wilson 95% interval; flag = lower bound > 0.55.
I4 ORACLE/DIAGNOSTIC (hindsight-timed, not a policy): terminal bar per
  direction = last bar setting a new running extreme of the bar mid
  (sweep2.extremes); leg 1 at the earlier terminal bar on the fade side
  (new low -> +1, new high -> -1) under the sweep1.make_entry bar-close law;
  on a leg-1 wall, leg 2 at the other direction's terminal bar when its close
  is strictly after leg 1's exit, same law.  NAIVE replaces terminal bars by
  quiet bars: the first bar where a direction has printed no new extreme for
  {QUIET_SECONDS} s (bar 0 anchors both directions); leg 2 at the other
  direction's first quiet bar strictly after leg 1's exit.  One entry per leg,
  at most two legs per cell.  No selection, no config grid, no null.
mutant {MUTANT_PEEKS}: predictor a is read from the cell's OWN phase.
"""

SPEC_SHA = hashlib.sha256(SPEC.encode()).hexdigest()


class IdeaRefusal(RuntimeError):
    pass


def idea_mutant() -> str:
    """The screen mutant name, validated inline on every read."""

    name = os.environ.get(MUTANT_ENV, "")
    if name and name not in IDEA_MUTANTS:
        raise IdeaRefusal(f"unknown idea mutant: {name}")
    return name


def code_sha() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# Cell geometry shared by both screens.
# --------------------------------------------------------------------------

def winner_side(star: S2.Star, rec: S1.CellRec) -> int:
    """Sweep 4's ``W``: 0 when the cell is short or ambiguous at tau=900 s."""

    if rec.n <= W_BAR or not bool(star.sharp[W_BAR]):
        return 0
    return int(star.sign[W_BAR])


def valid_bars(rec: S1.CellRec) -> np.ndarray:
    return np.flatnonzero(np.asarray(rec.bar_ok, bool))


@dataclass(frozen=True, slots=True)
class PhaseShape:
    """Open/close/high/low of one cell's valid bar mids."""

    open_mid: float
    close_mid: float
    high_mid: float
    low_mid: float

    @property
    def sign(self) -> int:
        return int(np.sign(self.close_mid - self.open_mid))

    @property
    def range_position(self) -> float | None:
        span = self.high_mid - self.low_mid
        if span <= 0:
            return None
        return float((self.close_mid - self.low_mid) / span)


def phase_shape(rec: S1.CellRec) -> PhaseShape | None:
    bars = valid_bars(rec)
    if not len(bars):
        return None
    mids = np.asarray(rec.mid, np.float64)[bars]
    return PhaseShape(float(mids[0]), float(mids[-1]),
                      float(mids.max()), float(mids.min()))


def day_order(records: Sequence[S1.CellRec]) -> dict[tuple[str, int], list[int]]:
    """Cell positions per (asset, d8), ordered by phase open (B4 identity)."""

    groups: dict[tuple[str, int], list[int]] = {}
    for position, rec in enumerate(records):
        groups.setdefault((rec.asset, int(rec.d8)), []).append(position)
    for key, positions in groups.items():
        positions.sort(key=lambda p: (int(records[p].phase_open_ts_ns),
                                      records[p].phase))
    return groups


# --------------------------------------------------------------------------
# SCREEN I1
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class I1Row:
    asset: str
    d8: int
    phase: str
    phase_idx: int
    winner: int
    predictors: Mapping[str, int]


def _sign_int(value: float) -> int:
    return int(np.sign(value))


def i1_rows(records: Sequence[S1.CellRec], stars: Sequence[S2.Star],
            store: CTX.ContextStore | None) -> tuple[list[I1Row], dict[str, int]]:
    """One row per cell with a defined ``W`` and its causal predictors."""

    mutant = idea_mutant()
    groups = day_order(records)
    shapes = [phase_shape(rec) for rec in records]
    rows: list[I1Row] = []
    counts = {"cells": len(records), "winner_defined": 0, "winner_ambiguous": 0,
              "no_shape": 0, "prior_phase_defined": 0, "levels_served": 0,
              "first_phase_cells": 0, "prior_phase_overlaps": 0}
    for key, positions in sorted(groups.items()):
        asset, d8 = key
        context = store.context_for(asset, d8) if store is not None else None
        levels_prev = None if context is None else context.get("levels_prev")
        for order, position in enumerate(positions):
            rec = records[position]
            win = winner_side(stars[position], rec)
            if win == 0:
                counts["winner_ambiguous"] += 1
                continue
            counts["winner_defined"] += 1
            shape = shapes[position]
            if shape is None:
                counts["no_shape"] += 1
                continue
            predictors: dict[str, int] = {}
            prior_shape: PhaseShape | None = None
            if order:
                previous = records[positions[order - 1]]
                if (int(previous.phase_close_ts_ns)
                        <= int(rec.phase_open_ts_ns)):
                    prior_shape = shapes[positions[order - 1]]
                else:
                    counts["prior_phase_overlaps"] += 1
            else:
                counts["first_phase_cells"] += 1
            source = shape if mutant == MUTANT_PEEKS else prior_shape
            if source is not None and source.sign:
                predictors["a_prior_phase_sign"] = source.sign
                if prior_shape is not None:
                    counts["prior_phase_defined"] += 1
            if prior_shape is not None:
                spot = prior_shape.range_position
                if spot is not None:
                    predictors["d_prior_phase_rangepos"] = 1 if spot > 0.5 else -1
            if levels_prev is not None:
                counts["levels_served"] += 1
                move = (float(levels_prev["session_close_mid2"])
                        - float(levels_prev["session_open_mid2"]))
                if _sign_int(move):
                    predictors["b_prior_day_sign"] = _sign_int(move)
                if order == 0:
                    gap = (shape.open_mid
                           - float(levels_prev["session_close_mid2"]))
                    if _sign_int(gap):
                        predictors["c_overnight_gap"] = _sign_int(gap)
            both = (predictors.get("a_prior_phase_sign"),
                    predictors.get("d_prior_phase_rangepos"))
            if both[0] is not None and both[0] == both[1]:
                predictors["a_and_d"] = int(both[0])
            rows.append(I1Row(rec.asset, int(rec.d8), rec.phase,
                              int(rec.phase) if rec.phase.isdigit() else -1,
                              win, predictors))
    return rows, counts


def i1_table(rows: Sequence[I1Row]) -> list[dict[str, object]]:
    """Agreement + Wilson CI per (asset, phase, predictor) and pooled."""

    out: list[dict[str, object]] = []
    assets = sorted({row.asset for row in rows})
    for asset in assets:
        asset_rows = [row for row in rows if row.asset == asset]
        phases: list[str] = sorted({row.phase for row in asset_rows}) + ["all"]
        for phase in phases:
            subset = (asset_rows if phase == "all"
                      else [row for row in asset_rows if row.phase == phase])
            for name in PREDICTORS:
                calls = [(row.predictors[name], row.winner) for row in subset
                         if name in row.predictors]
                total = len(calls)
                hits = int(sum(1 for call, win in calls if call == win))
                low, high = S1.wilson(hits, total)
                out.append({
                    "asset": asset, "phase": phase, "predictor": name,
                    "n": total, "hits": hits,
                    "agreement": (hits / total) if total else 0.0,
                    "ci_low": low, "ci_high": high,
                    "flag_ci_low_gt_055": bool(total and low > 0.55),
                })
    return out


# --------------------------------------------------------------------------
# SCREEN I4
# --------------------------------------------------------------------------

def terminal_bar(ext: S2.Extremes, side: int) -> int:
    """Sweep 4's law: last bar setting the fade side's adverse extreme."""

    flag = ext.new_low if int(side) > 0 else ext.new_high
    found = np.flatnonzero(np.asarray(flag, bool))
    return int(found[-1]) if len(found) else -1


def quiet_bars(ext: S2.Extremes, side: int) -> np.ndarray:
    """Bars at which the fade side's own direction has printed no new extreme
    for ``QUIET_SECONDS``; the phase's first bar anchors both directions."""

    flag = np.asarray(ext.new_low if int(side) > 0 else ext.new_high, bool)
    order = np.arange(len(flag), dtype=np.int64)
    # Bar 0 anchors both directions: it holds the initial running extreme.
    marked = flag.copy()
    if len(marked):
        marked[0] = True
    last = np.maximum.accumulate(np.where(marked, order, -1))
    return (order - last) >= QUIET_BARS


def first_quiet_bar(ext: S2.Extremes, side: int, after_bar: int = 0) -> int:
    flags = quiet_bars(ext, side)
    found = np.flatnonzero(flags[int(after_bar):])
    return -1 if not len(found) else int(after_bar) + int(found[0])


@dataclass(frozen=True, slots=True)
class Sequence2:
    """One cell's two-leg sequence under one variant."""

    position: int
    legs: tuple[S1.Entry, ...]
    leg1_bar: int
    leg2_bar: int
    aborted_leg1: bool
    aborted_leg2: bool
    leg2_skipped_timing: bool


def sequence_for(position: int, rec: S1.CellRec, ext: S2.Extremes,
                 variant: str) -> Sequence2:
    """The oracle-timed or naive two-leg sequence for one cell."""

    if variant == "oracle":
        bars = {side: terminal_bar(ext, side) for side in (1, -1)}
    elif variant == "naive":
        bars = {side: first_quiet_bar(ext, side) for side in (1, -1)}
    else:
        raise IdeaRefusal(f"unknown I4 variant: {variant}")
    order = [side for side in (1, -1) if bars[side] >= 0]
    if not order:
        return Sequence2(position, (), -1, -1, False, False, False)
    # Earlier bar first; a tie prefers the long fade, deterministically.
    order.sort(key=lambda side: (bars[side], -side))
    first = order[0]
    other = -first
    leg1 = S1.make_entry(position, rec, bars[first], first)
    if leg1 is None:
        return Sequence2(position, (), bars[first], -1, True, False, False)
    if not leg1.wall:
        return Sequence2(position, (leg1,), bars[first], -1, False, False, False)
    if variant == "oracle":
        bar2 = bars[other]
    else:
        after = int(np.searchsorted(np.asarray(rec.lat, np.int64),
                                    int(leg1.exit_ts_ns), side="right"))
        bar2 = first_quiet_bar(ext, other, after)
    if bar2 < 0 or int(rec.lat[bar2]) <= int(leg1.exit_ts_ns):
        return Sequence2(position, (leg1,), bars[first], -1, False, False, True)
    leg2 = S1.make_entry(position, rec, bar2, other)
    if leg2 is None:
        return Sequence2(position, (leg1,), bars[first], bar2, False, True, False)
    return Sequence2(position, (leg1, leg2), bars[first], bar2, False, False, False)


def i4_variant(records: Sequence[S1.CellRec], exts: Sequence[S2.Extremes],
               days: Mapping[str, int], variant: str
               ) -> tuple[list[Sequence2], list[dict[str, object]]]:
    """Per-asset arithmetic for one variant.  Oracle/diagnostic, not a policy."""

    seqs = [sequence_for(position, rec, exts[position], variant)
            for position, rec in enumerate(records)]
    asset_days: dict[str, set[int]] = {}
    for rec in records:
        asset_days.setdefault(rec.asset, set()).add(int(rec.d8))
    table: list[dict[str, object]] = []
    for asset in S1.ASSETS:
        rows = [seq for seq, rec in zip(seqs, records) if rec.asset == asset]
        legs = [leg for seq in rows for leg in seq.legs]
        leg2 = [seq.legs[1] for seq in rows if len(seq.legs) == 2]
        certs = np.asarray([leg.cert_usd for leg in legs], np.float64)
        n_days = max(1, int(days.get(asset, len(asset_days.get(asset, ())))))
        per_day: dict[int, int] = {d8: 0 for d8 in asset_days.get(asset, ())}
        for leg in legs:
            per_day[int(leg.d8)] = per_day.get(int(leg.d8), 0) + 1
        counts = np.asarray(sorted(per_day.values()), np.float64)
        walled1 = [seq for seq in rows if seq.legs and seq.legs[0].wall]
        table.append({
            "variant": variant, "asset": asset,
            "cells": int(len(rows)),
            "cells_1_leg": int(sum(1 for seq in rows if len(seq.legs) == 1)),
            "cells_2_legs": int(sum(1 for seq in rows if len(seq.legs) == 2)),
            "cells_0_legs": int(sum(1 for seq in rows if not seq.legs)),
            "legs": int(len(legs)),
            "explore_days": int(len(asset_days.get(asset, ()))),
            "total_usd": float(certs.sum()) if len(certs) else 0.0,
            "usd_per_asset_day": float(certs.sum() / n_days) if len(certs) else 0.0,
            "usd_per_trade": float(certs.mean()) if len(certs) else 0.0,
            "win_rate": float((certs > 0).mean()) if len(certs) else 0.0,
            "walls": int(sum(1 for leg in legs if leg.wall)),
            "wall_rate": (float(np.mean([leg.wall for leg in legs]))
                          if legs else 0.0),
            "mdd_day_usd": S1.asset_mdd_day(legs, asset) if legs else 0.0,
            "entries_per_day_p95": (float(np.percentile(counts, 95))
                                    if len(counts) else 0.0),
            "entries_per_day_max": int(counts.max()) if len(counts) else 0,
            "leg1_walls": int(len(walled1)),
            "leg2_entered": int(len(leg2)),
            "leg2_mean_usd_given_leg1_wall": (
                float(np.mean([leg.cert_usd for leg in leg2])) if leg2 else 0.0),
            "leg2_skipped_timing": int(sum(1 for seq in rows
                                           if seq.leg2_skipped_timing)),
            "leg1_aborted": int(sum(1 for seq in rows if seq.aborted_leg1)),
            "leg2_aborted": int(sum(1 for seq in rows if seq.aborted_leg2)),
        })
    # Portfolio-day entry counts, for the 12-entry cap check.
    portfolio: dict[int, int] = {}
    for seq, rec in zip(seqs, records):
        for _leg in seq.legs:
            portfolio[int(rec.d8)] = portfolio.get(int(rec.d8), 0) + 1
    values = np.asarray(sorted(portfolio.values()), np.float64)
    table.append({
        "variant": variant, "asset": "PORTFOLIO",
        "cells": int(len(records)),
        "legs": int(sum(len(seq.legs) for seq in seqs)),
        "portfolio_days_with_entries": int(len(portfolio)),
        "entries_per_day_p95": float(np.percentile(values, 95)) if len(values) else 0.0,
        "entries_per_day_max": int(values.max()) if len(values) else 0,
        "cap": PORTFOLIO_ENTRY_CAP,
        "p95_over_cap": bool(len(values) and float(np.percentile(values, 95))
                             > PORTFOLIO_ENTRY_CAP),
        "days_over_cap": int((values > PORTFOLIO_ENTRY_CAP).sum()) if len(values) else 0,
    })
    return seqs, table


# --------------------------------------------------------------------------
# Printing.
# --------------------------------------------------------------------------

def _f(value: object, width: int = 8, digits: int = 3) -> str:
    if isinstance(value, bool):
        return f"{'yes' if value else '-':>{width}}"
    if isinstance(value, float):
        return f"{value:>{width}.{digits}f}"
    return f"{value:>{width}}"


def print_i1(table: Sequence[Mapping[str, object]],
             counts: Mapping[str, int]) -> None:
    print("\n== SCREEN I1: prior-phase inheritance, agreement with "
          "W = sign(Delta*(900s)) LEGAL band max(2cost,100) ==")
    print("   causal predictors known at the cell's phase open; no cash; "
          "Wilson 95% CI; FLAG = ci_low > 0.55")
    print(f"   cells={counts['cells']} winner_defined={counts['winner_defined']} "
          f"ambiguous={counts['winner_ambiguous']} "
          f"prior_phase_defined={counts['prior_phase_defined']} "
          f"levels_served={counts['levels_served']}")
    head = (f"{'asset':<5} {'phase':<5} {'predictor':<24} {'n':>5} {'hits':>5} "
            f"{'agree':>8} {'ci_low':>8} {'ci_high':>8}  flag")
    print(head)
    print("-" * len(head))
    for row in table:
        print(f"{row['asset']:<5} {str(row['phase']):<5} {row['predictor']:<24} "
              f"{_f(row['n'], 5)} {_f(row['hits'], 5)} {_f(row['agreement'])} "
              f"{_f(row['ci_low'])} {_f(row['ci_high'])}  "
              f"{'FLAG' if row['flag_ci_low_gt_055'] else ''}")


def print_i4(table: Sequence[Mapping[str, object]]) -> None:
    print("\n== SCREEN I4: both-extremes sequential, ORACLE/DIAGNOSTIC "
          "ARITHMETIC (hindsight-timed, NOT a policy, no selection) ==")
    print("   ORACLE legs sit on true terminal extreme bars; NAIVE legs on "
          "20-min quiet bars; frozen bar-close entry law, one entry per leg")
    head = (f"{'variant':<7} {'asset':<9} {'cells':>5} {'1leg':>5} {'2leg':>5} "
            f"{'legs':>5} {'usd/day':>9} {'usd/trade':>10} {'win':>6} "
            f"{'walls':>6} {'wallrt':>7} {'mdd_day':>9} {'p95/d':>6} "
            f"{'leg2|wall':>10}")
    print(head)
    print("-" * len(head))
    for row in table:
        if row["asset"] == "PORTFOLIO":
            continue
        print(f"{row['variant']:<7} {row['asset']:<9} {_f(row['cells'], 5)} "
              f"{_f(row['cells_1_leg'], 5)} {_f(row['cells_2_legs'], 5)} "
              f"{_f(row['legs'], 5)} {_f(row['usd_per_asset_day'], 9, 1)} "
              f"{_f(row['usd_per_trade'], 10, 1)} {_f(row['win_rate'], 6, 3)} "
              f"{_f(row['walls'], 6)} {_f(row['wall_rate'], 7, 3)} "
              f"{_f(row['mdd_day_usd'], 9, 1)} "
              f"{_f(row['entries_per_day_p95'], 6, 1)} "
              f"{_f(row['leg2_mean_usd_given_leg1_wall'], 10, 1)}")
    print("\n   leg accounting and the portfolio cap check")
    head2 = (f"{'variant':<7} {'asset':<9} {'0leg':>5} {'l1wall':>7} "
             f"{'l2ent':>6} {'l2skip_t':>9} {'l1abort':>8} {'l2abort':>8} "
             f"{'p95/day':>8} {'max/day':>8} {'cap':>5}")
    print(head2)
    print("-" * len(head2))
    for row in table:
        if row["asset"] == "PORTFOLIO":
            print(f"{row['variant']:<7} {'PORTFOLIO':<9} {'-':>5} {'-':>7} "
                  f"{'-':>6} {'-':>9} {'-':>8} {'-':>8} "
                  f"{_f(row['entries_per_day_p95'], 8, 1)} "
                  f"{_f(row['entries_per_day_max'], 8)} "
                  f"{_f(row['cap'], 5)}"
                  f"  {'OVER' if row['p95_over_cap'] else 'under'}"
                  f" days_over={row['days_over_cap']}")
            continue
        print(f"{row['variant']:<7} {row['asset']:<9} {_f(row['cells_0_legs'], 5)} "
              f"{_f(row['leg1_walls'], 7)} {_f(row['leg2_entered'], 6)} "
              f"{_f(row['leg2_skipped_timing'], 9)} {_f(row['leg1_aborted'], 8)} "
              f"{_f(row['leg2_aborted'], 8)} "
              f"{_f(row['entries_per_day_p95'], 8, 1)} "
              f"{_f(row['entries_per_day_max'], 8)} {'-':>5}")


# --------------------------------------------------------------------------
# Selftest: synthetic lattices only, zero era bytes.
# --------------------------------------------------------------------------

def synth_cell(asset: str, d8: int, phase: str, open_bar_ns: int,
               mids: Sequence[float], *, cert_p: Sequence[float] | None = None,
               cert_m: Sequence[float] | None = None,
               wall_p: Sequence[bool] | None = None,
               wall_m: Sequence[bool] | None = None,
               exit_p: Sequence[int] | None = None,
               exit_m: Sequence[int] | None = None) -> S1.CellRec:
    """One synthetic ``CellRec`` on a 60 s lattice.  No bytes are read."""

    n = len(mids)
    lat = (open_bar_ns + np.arange(n, dtype=np.int64) * S1.BAR_NS)
    zeros = np.zeros(n, np.float64)
    ok = np.ones(n, bool)
    ok[0] = False
    return S1.CellRec(
        asset=asset, d8=d8, phase=phase,
        text=f"{asset}/{d8}/{phase}/{open_bar_ns // 10**9}",
        phase_open_ts_ns=int(lat[0]), phase_close_ts_ns=int(lat[-1] + S1.BAR_NS),
        locked_iid=0, pack_sha256="synthetic", raw_first=int(lat[0]), k0=1,
        r0_mid2=1.0, legal_from_p=1, legal_from_m=1,
        lat=lat, mid=np.asarray(mids, np.int64), bar_ok=ok,
        cost=np.full(n, 10.0), cert_p=np.asarray(cert_p if cert_p is not None
                                                 else zeros, np.float64),
        cert_m=np.asarray(cert_m if cert_m is not None else zeros, np.float64),
        ok_p=ok.copy(), ok_m=ok.copy(),
        wall_p=np.asarray(wall_p if wall_p is not None
                          else np.zeros(n, bool), bool),
        wall_m=np.asarray(wall_m if wall_m is not None
                          else np.zeros(n, bool), bool),
        exit_p=np.asarray(exit_p if exit_p is not None
                          else lat + S1.BAR_NS, np.int64),
        exit_m=np.asarray(exit_m if exit_m is not None
                          else lat + S1.BAR_NS, np.int64),
        cum_long=np.zeros(n, np.int32), cum_short=np.zeros(n, np.int32),
        raw_cut=np.zeros(n, np.int64), raw_last=np.zeros(n, np.int64))


def _i1_synthetic() -> list[S1.CellRec]:
    """Four phases of one synthetic day; three carry a prior phase.

    Path per phase (bar 0 is invalid, so the OPEN mid is bar 1's):
      P0  down: 100 -> 90, high 100, low 88     own sign -1, close range pos
                                                (90-88)/(100-88) = 0.167 -> d=-1
      P1  up:   90 -> 110                       own sign +1
      P2  down: 110 -> 100                      own sign -1
      P3  up:   100 -> 120                      own sign +1
    Winner sides are set so the PRIOR-phase sign agrees on all three defined
    cells (3/3) while the OWN-phase sign (the screen_peeks mutant) disagrees
    on all three (0/3).
    """

    base = 1_600_000_000_000_000_000
    span = 40 * S1.BAR_NS
    paths = {
        "0": [95, 100, 96, 88, 92, 90],
        "1": [95, 90, 95, 100, 105, 110],
        "2": [115, 110, 108, 104, 102, 100],
        "3": [95, 100, 105, 112, 118, 120],
    }
    winners = {"0": 1, "1": -1, "2": 1, "3": -1}
    cells: list[S1.CellRec] = []
    for order, (phase, path) in enumerate(sorted(paths.items())):
        mids = list(path) + [path[-1]] * (W_BAR + 2 - len(path))
        rec = synth_cell("HG", 20220301, phase, base + order * span, mids)
        # A sharp Delta* at bar 15: |cert_p - cert_m| >> the 100 usd band.
        win = winners[phase]
        cert = np.zeros(len(mids), np.float64)
        cert[W_BAR:] = 1000.0
        rec = S1.CellRec(**{
            **{field: getattr(rec, field) for field in rec.__slots__},
            "cert_p": cert if win > 0 else np.zeros(len(mids)),
            "cert_m": cert if win < 0 else np.zeros(len(mids))})
        cells.append(rec)
    return cells


def _i4_synthetic() -> tuple[list[S1.CellRec], list[S2.Extremes]]:
    """One cell whose terminal LOW bar precedes its terminal HIGH bar.

    mids: 100, 99, 98, 97, 101, 104, 106, 105 (bar 0 invalid for entries).
    New running lows at bars 1,2,3 (terminal low = bar 3); new running highs
    at bars 4,5,6 (terminal high = bar 6).  Leg 1 fades the low: side +1 at
    bar 3, cert -900, wall, exit inside bar 4.  Bar 6's close is after that
    exit, so leg 2 fades the high: side -1 at bar 6, cert +500, no wall.
    Hand arithmetic: 2 legs, total -400 usd, leg-2-given-wall mean +500.
    """

    mids = [100, 99, 98, 97, 101, 104, 106, 105]
    n = len(mids)
    base = 1_600_000_000_000_000_000
    lat = base + np.arange(n, dtype=np.int64) * S1.BAR_NS
    cert_p = np.zeros(n, np.float64)
    cert_p[3] = -900.0
    wall_p = np.zeros(n, bool)
    wall_p[3] = True
    exit_p = (lat + S1.BAR_NS).copy()
    exit_p[3] = int(lat[4]) + 30 * 10**9        # exits inside bar 4
    cert_m = np.zeros(n, np.float64)
    cert_m[6] = 500.0
    rec = synth_cell("HG", 20220302, "0", base, mids, cert_p=cert_p,
                     cert_m=cert_m, wall_p=wall_p, exit_p=exit_p)
    return [rec], [S2.extremes(rec)]


def selftest() -> int:
    """Hand-computed I1 and I4 cases plus the mutant.  Zero era bytes."""

    checks: list[tuple[str, bool, str]] = []
    mutant = idea_mutant()
    checks.append((f"idea_mutant_env_checked({mutant or 'none'})",
                   mutant in ("",) + IDEA_MUTANTS, f"mutant={mutant!r}"))
    try:
        os.environ[MUTANT_ENV] = "not_a_mutant"
        idea_mutant()
        rejected = False
    except IdeaRefusal:
        rejected = True
    finally:
        if mutant:
            os.environ[MUTANT_ENV] = mutant
        else:
            os.environ.pop(MUTANT_ENV, None)
    checks.append(("unknown_mutant_refused", rejected, "IdeaRefusal expected"))

    # -- I1 ---------------------------------------------------------------
    cells = _i1_synthetic()
    stars = S2.stars_for(cells, "legal", "max2cost100")
    wins = [winner_side(star, rec) for star, rec in zip(stars, cells)]
    checks.append(("i1_synth_winner_sides", wins == [1, -1, 1, -1], f"W={wins}"))
    rows, counts = i1_rows(cells, stars, None)
    calls = [(row.phase, row.predictors.get("a_prior_phase_sign"), row.winner)
             for row in rows]
    table = i1_table(rows)
    hit = [row for row in table
           if row["asset"] == "HG" and row["phase"] == "all"
           and row["predictor"] == "a_prior_phase_sign"][0]
    # Under the mutant the first phase also gets a predictor (its own sign),
    # so the honest 3-of-3 becomes 0-of-4.
    expect_n, expect_hits = (4, 0) if mutant == MUTANT_PEEKS else (3, 3)
    checks.append((f"i1_hand_agreement_a_is_{expect_hits}_of_{expect_n}",
                   (int(hit["n"]) == expect_n and int(hit["hits"]) == expect_hits),
                   f"n={hit['n']} hits={hit['hits']} calls={calls}"))
    checks.append(("i1_honest_law_agreement_a_is_3_of_3",
                   int(hit["n"]) == 3 and int(hit["hits"]) == 3,
                   f"n={hit['n']} hits={hit['hits']} (RED under {MUTANT_PEEKS})"))
    drow = [row for row in table
            if row["asset"] == "HG" and row["phase"] == "1"
            and row["predictor"] == "d_prior_phase_rangepos"]
    checks.append(("i1_hand_rangepos_phase1_is_minus1",
                   bool(drow) and int(drow[0]["n"]) == 1
                   and drow[0]["ci_low"] >= 0.0,
                   f"row={drow}"))
    d_call = [row.predictors.get("d_prior_phase_rangepos") for row in rows
              if row.phase == "1"]
    checks.append(("i1_hand_rangepos_value", d_call == [-1], f"d={d_call}"))
    checks.append(("i1_first_phase_has_no_prior",
                   all("a_prior_phase_sign" not in row.predictors
                       for row in rows if row.phase == "0")
                   or mutant == MUTANT_PEEKS,
                   f"phase0={[row.predictors for row in rows if row.phase == '0']}"))

    # -- I4 ---------------------------------------------------------------
    recs4, exts4 = _i4_synthetic()
    checks.append(("i4_terminal_bars_3_and_6",
                   (terminal_bar(exts4[0], 1), terminal_bar(exts4[0], -1)) == (3, 6),
                   f"bars={(terminal_bar(exts4[0], 1), terminal_bar(exts4[0], -1))}"))
    seq = sequence_for(0, recs4[0], exts4[0], "oracle")
    legs = [(leg.bar, leg.side, leg.cert_usd, leg.wall) for leg in seq.legs]
    checks.append(("i4_hand_two_legs_wall_then_entry",
                   legs == [(3, 1, -900.0, True), (6, -1, 500.0, False)],
                   f"legs={legs}"))
    _seqs, i4rows = i4_variant(recs4, exts4, {"HG": 1}, "oracle")
    hg = [row for row in i4rows if row["asset"] == "HG"][0]
    checks.append(("i4_hand_total_minus_400_leg2_500",
                   abs(float(hg["total_usd"]) + 400.0) < 1e-9
                   and abs(float(hg["leg2_mean_usd_given_leg1_wall"]) - 500.0) < 1e-9
                   and int(hg["cells_2_legs"]) == 1,
                   f"total={hg['total_usd']} leg2={hg['leg2_mean_usd_given_leg1_wall']}"))

    print(f"selftest mutant={mutant or 'none'}  spec_sha={SPEC_SHA[:12]}")
    failed = 0
    for name, passed, detail in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}"
              f"{'' if passed else '  ' + detail}")
        failed += 0 if passed else 1
    if mutant == MUTANT_PEEKS:
        honest = [passed for name, passed, _ in checks
                  if name == "i1_honest_law_agreement_a_is_3_of_3"]
        red = bool(honest) and not honest[0]
        print(f"  mutant {MUTANT_PEEKS}: "
              f"{'RED as required (I1 case flipped)' if red else 'GREEN - MUTANT IS DEAD'}")
    print(f"selftest {'FAILED' if failed else 'PASSED'} "
          f"({len(checks) - failed}/{len(checks)} checks)")
    return 1 if failed else 0


# --------------------------------------------------------------------------
# Driver.
# --------------------------------------------------------------------------

def run() -> dict[str, object]:
    started = time.monotonic()
    mutant = idea_mutant()
    records, days = S1.load_cache()
    stars = S2.stars_for(records, "legal", "max2cost100")
    exts = [S2.extremes(rec) for rec in records]
    store = CTX.ContextStore()
    rows, counts = i1_rows(records, stars, store)
    table1 = i1_table(rows)
    table4: list[dict[str, object]] = []
    for variant in ("oracle", "naive"):
        _seqs, part = i4_variant(records, exts, days, variant)
        table4.extend(part)
    report = {
        "schema": SCHEMA, "spec": SPEC, "spec_sha": SPEC_SHA,
        "code_sha": code_sha(), "split_sha": S1.split_sha(),
        "outcome_law_sha": S1.outcome_law_sha(), "mutant": mutant,
        "tier": "exploratory", "label": "no-cash screens; I4 is oracle/diagnostic",
        "asset_days": dict(days), "cells": len(records),
        "i1": {"counts": counts, "table": table1,
               "flagged": [row for row in table1 if row["flag_ci_low_gt_055"]]},
        "i4": {"table": table4},
        "context_counts": store.counts,
        "wall_seconds": round(time.monotonic() - started, 2),
    }
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--out", default=str(REPORT_PATH))
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    report = run()
    print_i1(report["i1"]["table"], report["i1"]["counts"])
    print_i4(report["i4"]["table"])
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, sort_keys=True, default=float))
    print(f"\nwrote {out} ({out.stat().st_size} bytes) in "
          f"{report['wall_seconds']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
