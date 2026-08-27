#!/usr/bin/env python3
"""Sweep 3 of the side-resolution mill: DEEP-FADE, zero-fit.

Exploratory tier.  EXPLORE-day bytes only, can kill, cannot promote.  Sweep 2
(rows sweep2-001..039, all KILL) proved the gap is entry DEPTH, not side
knowledge: with the oracle Delta* side, terminal entries clear every rung
(REM ceiling 2692/3600/4230 usd per asset-day) while first-adverse-extreme
entries post 745/449/870 with 12-29% walls.  This sweep chases the depth half
with no side model and no fitting.

Per cell, both sides armed simultaneously::

    zone A1(m)  LONG : bar mid <= prior_day_low_mid2  + m * ATR_mid2
                SHORT: bar mid >= prior_day_high_mid2 - m * ATR_mid2
    zone A2(D)  LONG : bar mid <= phase_open_mid2 - D * ATR_mid2
                SHORT: bar mid >= phase_open_mid2 + D * ATR_mid2

    trigger  the first bar T at or after tau0 whose bar mid sets a NEW running
             extreme of the phase on the fade-adverse direction (a new running
             minimum for LONG, a new running maximum for SHORT) AND lies inside
             that side's zone.  The earliest trigger across the two sides wins
             and fixes the entry side to its fade side.
    rebound  r raw ticks over one bar: r=0 enters at T; r>0 enters at the first
             bar T' > T whose mid has recovered r ticks from the extreme, and a
             NEWER extreme printing during that wait resets the wait to itself.
    abstain  when no trigger or no confirmation lands at or before
             phase_close - 1800 s.

ATR is ``atr14_prev_usd`` from the priors table and the anchors are the prior
LOCKED day's session high/low, both served through
``tools/mill/context.py`` ``ContextStore`` under its strictly-prior guard.
USD converts to mid2 units by the frozen outcome factor alone: cert =
side * (exit_mid2 - entry_mid2) * 0.5e-9 * multiplier - cost, so one USD of
price move is ``2e9 / multiplier`` mid2 units.  The conversion is asserted
against a real substrate row's spread before any zone is drawn.

Stages, run in order:

  STAGE O  oracle attribution, before any config is judged.  O1 the location of
           the terminal extreme a perfect fade would enter, per zone family.
           O2 the cash of entering there (the perfect-entry line this family
           chases), reconciled against ``.audit/mill-rem-ceiling.json``.  O3 the
           oracle TIMING variant: enter at the LAST in-zone extreme instead of
           the first, per zone config.
  STAGE A  no cash.  Coverage, availability, median entry time and depth, and
           the entry-time error against sign(Delta*) at the entry bar with a
           Wilson 95% CI, for all 42 configs.  Two configs selected per asset.
  STAGE B  cash on the selected lines plus one F4-gated variant of each asset's
           best: engine replay, 2% adversarial stress, block-permutation nulls.

Laws carried unchanged from sweeps 1 and 2 (imported, never re-implemented):
the 60 s completed-bar sampler, the entry convention (declaration at bar close
T, entry quote the last trusted row strictly before T, frozen cost from that
row), legality (a formed same-side CLEAR candidate by T), one entry per cell,
minimum 1800 s remaining at entry, the Delta*/REM LEGAL law, the cash and
``_drawdown`` reductions, the engine replay shaping, the asset-day
block-permutation null, the Wilson interval, and the 31-column log row.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import datetime as dt
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine.entry_v2.confirmation_types import FEE_USD, NANOS_PER_SECOND
from engine.entry_v2.corpus_units import ASSET_MULTIPLIER, ASSET_RAW_TICK

import context as CTX
import mill as M
import sweep1 as S1
import sweep2 as S2

# --------------------------------------------------------------------------
# The immutable law this sweep registers before it reads anything.
# --------------------------------------------------------------------------

SPEC = """QRE2MILLSWEEP3
tier=exploratory; explore-only; can kill, cannot promote.  parent=sweep2-039.
carried unchanged: 60s completed bars, value at close t = last trusted row
  strictly before t; entry convention (declaration at bar close T, entry_ts=T,
  entry quote the last trusted row strictly before T with 0<bid<ask, frozen
  cost from that row); legality = a CLEAR candidate with the declared side and
  decision_ts_ns <= T exists in the cell; one entry per cell; entries only
  inside [phase_open, phase_close) and at or before phase_close-1800s;
  Delta*(t) = REM(+1,t) - REM(-1,t) under the LEGAL variant with the
  max(2*cost,100) ambiguity band; seed 20260827.
context: ATR_mid2 = atr14_prev_usd * 2e9 / multiplier, priors row of the cell's
  own day (prior-derived by construction); prior_low/prior_high/prior_close =
  session_low_mid2/session_high_mid2/session_close_mid2 of the levels row the
  ContextStore serves for the cell's day (strictly earlier day, its guard);
  phase_open_mid2 = the bar mid at the first lattice point carrying a legal
  quote.  A cell with no ATR or no strictly-prior levels row is skipped.
zones (per cell, per side, causal): A1(m) LONG bar mid <= prior_low + m*ATR,
  SHORT bar mid >= prior_high - m*ATR, m in {+0.25, 0.0, -0.10}; A2(D) LONG
  bar mid <= phase_open - D*ATR, SHORT bar mid >= phase_open + D*ATR, D in
  {0.5, 0.75, 1.0, 1.25}.  Seven zone configs, each applied to both sides.
trigger: at or after tau0 in {900,1800} s since phase open, the first bar T
  whose bar mid sets a new running extreme of the phase on the fade-adverse
  direction (new running minimum for LONG, new running maximum for SHORT) and
  lies inside that side's zone.  Both sides armed simultaneously; the earliest
  trigger wins and fixes the side to its fade side (LONG at deep lows, SHORT
  at deep highs); the losing side is not re-armed.
rebound: r in {0,4,8} raw ticks over k=1 bar, step = r*2*ASSET_RAW_TICK.  r=0
  enters at T.  r>0 enters at the first bar T'>T with side*(mid[T']-mid[T])
  >= step; a newer running extreme on the same adverse direction printing
  after T resets the wait to itself (T := that bar).  No qualifying bar at or
  before phase_close-1800s => abstain.  Grid = 7 zones x 2 tau0 x 3 r = 42.
STAGE O (oracle attribution, no config judged): O1 the terminal extreme (the
  phase argmin for a Delta*-winner LONG, argmax for SHORT) and its zone
  membership; O2 entry at that bar on the fade side under the same legality,
  reconciled against .audit/mill-rem-ceiling.json REM(LEGAL,tau=1800); O3 the
  oracle TIMING variant, entry at the LAST in-zone trigger instead of the
  first, per zone config.  The O3-vs-causal gap is reported cash-free in stage
  O (trigger counts, first==last rate) and in cash only on selected lines.
STAGE A (no cash): coverage=entered/cells, unavailable=triggered but illegal
  or uncertifiable, no-event, median entry seconds since phase open, median
  entry depth = side*(phase_open_mid2 - entry mid)/ATR_mid2, entry-time error
  = fraction of entries whose fade side differs from sign(Delta*(entry bar))
  over entries whose entry bar is non-ambiguous, Wilson 95% CI.
selection (per asset, no cash): minimise the error CI upper bound subject to
  coverage >= 0.30, then minimum median entry time, then simplicity (A1 before
  A2, then smaller |m| or D, then smaller r, then earlier tau0), then key.
  Two configs per asset: the best, and the best config whose anchor family
  differs from it when one qualifies, else the next in the same order.
STAGE B (cash): the selected lines plus one F4-gated variant of each asset's
  best (the per-asset median-R0 running-range gate from mill-sweep1.json),
  each priced on its own asset; the engine replay of each asset's best and of
  the three-asset portfolio of bests; a 2% adversarial stress on each asset's
  best (round(0.02*entries) entries flipped to the opposite side at the same
  bars, choosing the legal flips with the largest cert damage); asset-day
  block-permutation nulls, 200 draws, seed 20260827, max-statistic across
  every priced line, per-asset and pooled-portfolio drawdown p values.
"""

SCHEMA = "QRE2MILLSWEEP3"
SEED = S1.SEED
BAR_SECONDS = S1.BAR_SECONDS
ASSETS = S1.ASSETS
DAY_RUNG_USD = S1.DAY_RUNG_USD
MDD_CAP_USD = S1.MDD_CAP_USD

ZONE_A1_M = (0.25, 0.0, -0.10)
ZONE_A2_D = (0.5, 0.75, 1.0, 1.25)
TAU0_SECONDS = (900, 1800)
REBOUND_TICKS = (0, 4, 8)
REMAIN_SECONDS = 1800
COVERAGE_FLOOR = 0.30
STRESS_RATE = 0.02
NULL_DRAWS = S1.NULL_DRAWS
CEILING_TAU = "1800"

MUTANT_ZONE_CLOSE = "sweep3_zone_uses_close"
PARENT_TRIAL = "sweep2-039"
SELECTION_RULE = "ci_upper>coverage0.30>delay>simplicity"
FAMILY = "F3-DEEPFADE"

OUT_PATH = ROOT / ".audit/mill-sweep3.json"
SWEEP1_PATH = ROOT / ".audit/mill-sweep1.json"
CEILING_PATH = ROOT / ".audit/mill-rem-ceiling.json"
LOG_PATH = S1.LOG_PATH
SPLIT_PATH = S1.SPLIT_PATH


class SweepRefusal(RuntimeError):
    pass


SPEC_SHA = S1._sha_text(SPEC)


def code_sha() -> str:
    return S1._sha_file(Path(__file__).resolve())


def split_sha() -> str:
    return S1.split_sha()


def outcome_law_sha() -> str:
    return S1.outcome_law_sha()


def _sweep_mutant() -> str:
    """The sweep-3 mutant name, validated against the mill's registry."""

    name = os.environ.get("QRE2_MILL_MUTANT", "")
    if name and name not in M.MUTANTS:
        raise SweepRefusal(f"unknown mill mutant: {name}")
    return name


# --------------------------------------------------------------------------
# The one USD -> mid2 conversion, derived from the frozen outcome factor.
# --------------------------------------------------------------------------

def usd_to_mid2(asset: str) -> float:
    """Mid2 units per USD of price move.

    ``cert = side * (exit_mid2 - entry_mid2) * 0.5e-9 * multiplier - cost``, so
    a USD of price move is ``1 / (0.5e-9 * multiplier) = 2e9 / multiplier``
    mid2 units.  The same factor turns the frozen spread cost back into the
    ``ask - bid`` it came from, which is what :func:`conversion_check` asserts.
    """

    return 2e9 / float(ASSET_MULTIPLIER[asset])


def conversion_check(asset: str, d8: int, root: Path) -> dict[str, object]:
    """Assert the conversion against one real substrate row's spread."""

    shard = M.load_shard(asset, int(d8), root=root)
    try:
        index = shard.cell_index(shard.cells[0])
        rows = np.flatnonzero((index.bid > 0) & (index.ask > index.bid))
        if not len(rows):
            raise SweepRefusal(f"{asset}/{d8} carries no two-sided quote")
        row = int(rows[0])
        bid, ask = int(index.bid[row]), int(index.ask[row])
        spread_usd = M.frozen_cost_usd(bid, ask, asset) - FEE_USD
        implied = usd_to_mid2(asset) * spread_usd
        expected = 2.0 * float(ask - bid)
        return {
            "asset": asset, "d8": int(d8), "row": row,
            "multiplier": int(ASSET_MULTIPLIER[asset]),
            "bid": bid, "ask": ask, "ask_minus_bid": ask - bid,
            "entry_spread_usd": spread_usd,
            "usd_to_mid2": usd_to_mid2(asset),
            "spread_usd_in_mid2": implied,
            "two_times_ask_minus_bid": expected,
            "ok": bool(abs(implied - expected) <= 1e-6 * max(1.0, expected)),
        }
    finally:
        shard.close()


# --------------------------------------------------------------------------
# Per-cell causal context.
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Ctx:
    """Everything a zone needs for one cell, all of it strictly causal."""

    atr_usd: float
    atr_mid2: float
    prior_d8: int
    prior_low: float
    prior_high: float
    prior_close: float
    open_mid2: float
    open_bar: int


def cell_context(store: CTX.ContextStore, rec: S1.CellRec) -> Ctx | None:
    """``None`` when the ATR or the strictly-prior levels row is absent."""

    payload = store.context_for(rec.asset, rec.d8)
    priors = payload.get("priors")
    levels = payload.get("levels_prev")
    if priors is None or levels is None:
        return None
    if str(priors.get("atr14_present", "0")) != "1":
        return None
    atr_usd = float(priors["atr14_prev_usd"])
    if not (atr_usd > 0.0):
        return None
    prior_day = int(levels["d8"])
    if prior_day >= int(rec.d8):
        raise SweepRefusal(
            f"context served day {prior_day} to {rec.asset}/{rec.d8}")
    valid = np.flatnonzero(np.asarray(rec.bar_ok, bool))
    if not len(valid):
        return None
    open_bar = int(valid[0])
    return Ctx(
        atr_usd=atr_usd,
        atr_mid2=atr_usd * usd_to_mid2(rec.asset),
        prior_d8=prior_day,
        prior_low=float(levels["session_low_mid2"]),
        prior_high=float(levels["session_high_mid2"]),
        prior_close=float(levels["session_close_mid2"]),
        open_mid2=float(rec.mid[open_bar]),
        open_bar=open_bar)


def contexts_for(records: Sequence[S1.CellRec], store: CTX.ContextStore
                 ) -> list[Ctx | None]:
    return [cell_context(store, rec) for rec in records]


# --------------------------------------------------------------------------
# Zones.
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Zone:
    key: str
    anchor: str          # "A1" prior-day level, "A2" depth from phase open
    param: float


def zone_grid() -> tuple[Zone, ...]:
    zones = [Zone(f"A1m{m:+.2f}", "A1", float(m)) for m in ZONE_A1_M]
    zones += [Zone(f"A2D{d:.2f}", "A2", float(d)) for d in ZONE_A2_D]
    return tuple(zones)


ZONES = zone_grid()
ZONE_BY_KEY = {zone.key: zone for zone in ZONES}


def zone_thresholds(zone: Zone, ctx: Ctx) -> tuple[float, float]:
    """``(long threshold, short threshold)`` in mid2 units.

    LONG fades a low, so its zone is ``mid <= long threshold``; SHORT fades a
    high, so its zone is ``mid >= short threshold``.  A positive ``m`` starts
    the A1 zone above the prior low and, symmetrically, below the prior high.
    """

    if zone.anchor == "A1":
        return (ctx.prior_low + zone.param * ctx.atr_mid2,
                ctx.prior_high - zone.param * ctx.atr_mid2)
    if zone.anchor == "A2":
        return (ctx.open_mid2 - zone.param * ctx.atr_mid2,
                ctx.open_mid2 + zone.param * ctx.atr_mid2)
    raise SweepRefusal(f"unknown zone anchor: {zone.anchor}")


def probe_values(mid: np.ndarray) -> np.ndarray:
    """The bar mid the zone test reads at each bar.

    The law is the CURRENT completed bar's mid.  The mutant
    ``QRE2_MILL_MUTANT=sweep3_zone_uses_close`` reads the NEXT bar's close
    instead, i.e. a future row, which is the one edit that makes this whole
    family non-causal.  Nothing else in this module branches on the mutant.
    """

    values = np.asarray(mid, np.float64)
    if _sweep_mutant() == MUTANT_ZONE_CLOSE:
        if len(values) < 2:
            return values
        return np.concatenate([values[1:], values[-1:]])
    return values


def zone_masks(rec: S1.CellRec, ctx: Ctx, zone: Zone
               ) -> tuple[np.ndarray, np.ndarray]:
    """``(in LONG zone, in SHORT zone)`` per bar."""

    values = probe_values(rec.mid)
    long_thr, short_thr = zone_thresholds(zone, ctx)
    return values <= long_thr, values >= short_thr


# --------------------------------------------------------------------------
# The trigger law.
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Trigger:
    side: int
    trigger_bar: int      # the in-zone extreme that armed the entry
    extreme_bar: int      # the latest extreme the rebound was measured from
    entry_bar: int


def tau_bar(tau0: int) -> int:
    return int(tau0) // BAR_SECONDS


def rebound_step(asset: str, ticks: int) -> float:
    """``r`` raw ticks in mid2 units, sweep 2's EVENT+1 convention."""

    return float(int(ticks) * 2 * ASSET_RAW_TICK[asset])


def in_zone_triggers(rec: S1.CellRec, ext: S2.Extremes,
                     masks: tuple[np.ndarray, np.ndarray], side: int,
                     start: int, stop: int) -> np.ndarray:
    """Bars in ``[start, stop]`` that set an in-zone adverse new extreme."""

    if stop < start:
        return np.zeros(0, np.int64)
    adverse = ext.new_low if int(side) > 0 else ext.new_high
    zone = masks[0] if int(side) > 0 else masks[1]
    window = adverse[start:stop + 1] & zone[start:stop + 1]
    return np.flatnonzero(window).astype(np.int64) + int(start)


def fire(rec: S1.CellRec, ext: S2.Extremes, masks: tuple[np.ndarray, np.ndarray],
         tau0: int, ticks: int) -> Trigger | None:
    """The cell's one trigger under this config, or ``None`` when it abstains."""

    stop = S2.deadline_bar(rec)
    start = max(tau_bar(tau0), 1)
    if stop < start:
        return None
    longs = in_zone_triggers(rec, ext, masks, 1, start, stop)
    shorts = in_zone_triggers(rec, ext, masks, -1, start, stop)
    first_long = int(longs[0]) if len(longs) else -1
    first_short = int(shorts[0]) if len(shorts) else -1
    if first_long < 0 and first_short < 0:
        return None
    if first_short < 0 or (0 <= first_long <= first_short):
        side, mark = 1, first_long
    else:
        side, mark = -1, first_short
    if int(ticks) == 0:
        return Trigger(side, mark, mark, mark)
    step = rebound_step(rec.asset, ticks)
    adverse = ext.new_low if side > 0 else ext.new_high
    mid = np.asarray(rec.mid, np.float64)
    extreme = mark
    bar = mark + 1
    while bar <= stop:
        if bool(adverse[bar]):
            extreme = bar
        elif side * (mid[bar] - mid[extreme]) >= step:
            return Trigger(side, mark, extreme, bar)
        bar += 1
    return None


# --------------------------------------------------------------------------
# Config grid.
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Config:
    key: str
    zone: Zone
    tau0: int
    ticks: int

    @property
    def simplicity(self) -> tuple:
        return (0 if self.zone.anchor == "A1" else 1, abs(self.zone.param),
                self.ticks, self.tau0)

    @property
    def params(self) -> list:
        return [self.zone.anchor, self.zone.param, self.tau0, self.ticks]


def config_grid() -> tuple[Config, ...]:
    out: list[Config] = []
    for zone in ZONES:
        for tau0 in TAU0_SECONDS:
            for ticks in REBOUND_TICKS:
                out.append(Config(f"{zone.key}/t{tau0}/r{ticks}", zone,
                                  int(tau0), int(ticks)))
    return tuple(out)


CONFIGS = config_grid()


# --------------------------------------------------------------------------
# Cell plane: everything the stages share, computed once.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Plane:
    records: list[S1.CellRec]
    ctxs: list[Ctx | None]
    exts: list[S2.Extremes]
    stars: list[S2.Star]
    geos: list[S1.Geometry]
    masks: dict[tuple[int, str], tuple[np.ndarray, np.ndarray]]
    stops: list[int]
    days: dict[str, int]
    cells: dict[str, int]

    def usable(self, position: int) -> bool:
        return self.ctxs[position] is not None


def build_plane(records: Sequence[S1.CellRec], store: CTX.ContextStore,
                days: Mapping[str, int]) -> Plane:
    ctxs = contexts_for(records, store)
    exts = [S2.extremes(rec) for rec in records]
    stars = S2.stars_for(records, "legal", "max2cost100")
    geos = [S1.geometry(rec) for rec in records]
    stops = [S2.deadline_bar(rec) for rec in records]
    masks: dict[tuple[int, str], tuple[np.ndarray, np.ndarray]] = {}
    for position, (rec, ctx) in enumerate(zip(records, ctxs)):
        if ctx is None:
            continue
        for zone in ZONES:
            masks[(position, zone.key)] = zone_masks(rec, ctx, zone)
    return Plane(list(records), ctxs, exts, stars, geos, masks, stops,
                 dict(days), S1.cells_by_asset(records))


def entries_for(plane: Plane, config: Config, asset: str | None = None,
                gate: Mapping[str, float] | None = None
                ) -> tuple[list[S1.Entry], dict[str, int], list[dict]]:
    """The causal line for one config: entries, skip counts, per-entry detail."""

    entries: list[S1.Entry] = []
    detail: list[dict] = []
    counts = {"cells": 0, "no_context": 0, "triggered": 0, "no_event": 0,
              "gated": 0, "illegal": 0, "uncertifiable": 0}
    for position, rec in enumerate(plane.records):
        if asset is not None and rec.asset != asset:
            continue
        counts["cells"] += 1
        ctx = plane.ctxs[position]
        if ctx is None:
            counts["no_context"] += 1
            continue
        shot = fire(rec, plane.exts[position], plane.masks[(position, config.zone.key)],
                    config.tau0, config.ticks)
        if shot is None:
            counts["no_event"] += 1
            continue
        counts["triggered"] += 1
        if gate is not None and float(plane.geos[position].rng[shot.entry_bar]) < float(
                gate[rec.asset]):
            counts["gated"] += 1
            continue
        if not rec.legal_at(shot.side, shot.entry_bar):
            counts["illegal"] += 1
            continue
        entry = S1.make_entry(position, rec, shot.entry_bar, shot.side)
        if entry is None:
            counts["uncertifiable"] += 1
            continue
        entries.append(entry)
        detail.append({
            "position": position, "asset": rec.asset, "d8": rec.d8,
            "side": shot.side, "trigger_bar": shot.trigger_bar,
            "entry_bar": shot.entry_bar,
            "entry_seconds": float(rec.seconds(shot.entry_bar)),
            "trigger_seconds": float(rec.seconds(shot.trigger_bar)),
            "depth_atr": float(shot.side * (ctx.open_mid2 - float(rec.mid[shot.entry_bar]))
                               / ctx.atr_mid2),
            "cert_usd": entry.cert_usd, "wall": entry.wall})
    return entries, counts, detail


# --------------------------------------------------------------------------
# STAGE O.
# --------------------------------------------------------------------------

def terminal_bar(rec: S1.CellRec, side: int, lo: int = 1,
                 hi: int | None = None) -> int:
    """The terminal running extreme on ``side``'s adverse direction.

    For a LONG winner the adverse direction is down, so the perfect fade enters
    at the phase's running minimum: the last bar that set a new running low,
    which is the first bar attaining the minimum mid.
    """

    top = rec.n - 1 if hi is None else int(hi)
    if top < lo:
        return -1
    window = np.asarray(rec.mid[lo:top + 1], np.float64)
    if not len(window):
        return -1
    pick = int(np.argmin(window)) if int(side) > 0 else int(np.argmax(window))
    return lo + pick


def o1(plane: Plane) -> dict[str, object]:
    """Where the terminal extreme lands, per zone family."""

    out: dict[str, object] = {}
    for asset in ASSETS:
        rows = {zone.key: 0 for zone in ZONES}
        any_zone = 0
        eligible = 0
        no_side = 0
        no_ctx = 0
        seconds: list[float] = []
        fractions: list[float] = []
        in_window = 0
        depths: list[float] = []
        for position, rec in enumerate(plane.records):
            if rec.asset != asset:
                continue
            ctx = plane.ctxs[position]
            if ctx is None:
                no_ctx += 1
                continue
            side = int(plane.stars[position].stable_side)
            if not side:
                no_side += 1
                continue
            bar = terminal_bar(rec, side)
            if bar < 0:
                continue
            eligible += 1
            seconds.append(float(rec.seconds(bar)))
            fractions.append(float(rec.fraction(bar)))
            depths.append(float(side * (ctx.open_mid2 - float(rec.mid[bar]))
                                / ctx.atr_mid2))
            if tau_bar(TAU0_SECONDS[0]) <= bar <= plane.stops[position]:
                in_window += 1
            hit = False
            for zone in ZONES:
                masks = plane.masks[(position, zone.key)]
                inside = bool((masks[0] if side > 0 else masks[1])[bar])
                rows[zone.key] += int(inside)
                hit = hit or inside
            any_zone += int(hit)
        denom = max(1, eligible)
        out[asset] = {
            "eligible_cells": eligible, "cells_without_context": no_ctx,
            "cells_without_sharp_side": no_side,
            "in_zone_fraction": {key: value / denom for key, value in rows.items()},
            "in_zone_counts": rows,
            "any_zone_fraction": any_zone / denom, "any_zone_count": any_zone,
            "terminal_seconds": S1._quantiles(seconds),
            "terminal_phase_fraction": S1._quantiles(fractions),
            "terminal_depth_atr": S1._quantiles(depths),
            "in_tradeable_window_fraction": in_window / denom,
        }
    return out


def _oracle_terminal_entries(plane: Plane, windowed: bool
                             ) -> tuple[list[S1.Entry], dict[str, dict[str, int]]]:
    entries: list[S1.Entry] = []
    counts = {asset: {"eligible": 0, "no_context": 0, "no_side": 0,
                      "no_window": 0, "illegal": 0, "uncertifiable": 0}
              for asset in ASSETS}
    for position, rec in enumerate(plane.records):
        book = counts[rec.asset]
        ctx = plane.ctxs[position]
        if ctx is None:
            book["no_context"] += 1
            continue
        side = int(plane.stars[position].stable_side)
        if not side:
            book["no_side"] += 1
            continue
        lo, hi = 1, None
        if windowed:
            lo, hi = max(tau_bar(REMAIN_SECONDS), 1), plane.stops[position]
            if hi < lo:
                book["no_window"] += 1
                continue
        bar = terminal_bar(rec, side, lo, hi)
        if bar < 0:
            continue
        book["eligible"] += 1
        if not rec.legal_at(side, bar):
            book["illegal"] += 1
            continue
        entry = S1.make_entry(position, rec, bar, side)
        if entry is None:
            book["uncertifiable"] += 1
            continue
        entries.append(entry)
    return entries, counts


def o2(plane: Plane) -> dict[str, object]:
    """The perfect-entry line: enter at the terminal extreme on the fade side."""

    ceiling = json.loads(CEILING_PATH.read_text())
    out: dict[str, object] = {"ceiling_source": str(CEILING_PATH.name),
                              "ceiling_tau": CEILING_TAU, "lines": {}}
    for name, windowed in (("TERMINAL-ALL", False), ("TERMINAL-WINDOW", True)):
        entries, counts = _oracle_terminal_entries(plane, windowed)
        cash = S1.cash_line(entries, plane.days, plane.cells)
        for asset in ASSETS:
            rung = ceiling.get(asset, {}).get(CEILING_TAU, {})
            cash[asset].update({
                "skips": counts[asset],
                "rem_ceiling_legal_usd_day": rung.get("ceil_l_day"),
                "rem_ceiling_mean_usd_trade": rung.get("mean_rem_l"),
                "rem_ceiling_coverage": rung.get("cov"),
                "capture_of_ceiling": (
                    cash[asset]["usd_per_asset_day"] / float(rung["ceil_l_day"])
                    if rung.get("ceil_l_day") else None)})
        out["lines"][name] = cash
    return out


def o3(plane: Plane) -> dict[str, object]:
    """Oracle TIMING: enter at the LAST in-zone extreme instead of the first."""

    out: dict[str, object] = {}
    for zone in ZONES:
        for tau0 in TAU0_SECONDS:
            key = f"{zone.key}/t{tau0}"
            entries: list[S1.Entry] = []
            stats = {asset: {"triggered": 0, "one_trigger": 0, "n_triggers": [],
                             "illegal": 0, "uncertifiable": 0} for asset in ASSETS}
            for position, rec in enumerate(plane.records):
                ctx = plane.ctxs[position]
                if ctx is None:
                    continue
                masks = plane.masks[(position, zone.key)]
                start = max(tau_bar(tau0), 1)
                stop = plane.stops[position]
                longs = in_zone_triggers(rec, plane.exts[position], masks, 1,
                                         start, stop)
                shorts = in_zone_triggers(rec, plane.exts[position], masks, -1,
                                          start, stop)
                marks = [(int(bar), 1) for bar in longs] + [
                    (int(bar), -1) for bar in shorts]
                if not marks:
                    continue
                marks.sort()
                book = stats[rec.asset]
                book["triggered"] += 1
                book["n_triggers"].append(len(marks))
                book["one_trigger"] += int(len(marks) == 1)
                bar, side = marks[-1]
                if not rec.legal_at(side, bar):
                    book["illegal"] += 1
                    continue
                entry = S1.make_entry(position, rec, bar, side)
                if entry is None:
                    book["uncertifiable"] += 1
                    continue
                entries.append(entry)
            cash = S1.cash_line(entries, plane.days, plane.cells)
            for asset in ASSETS:
                book = stats[asset]
                counts = book.pop("n_triggers")
                cash[asset].update({
                    "triggered_cells": book["triggered"],
                    "first_is_last_fraction": (book["one_trigger"] / book["triggered"]
                                               if book["triggered"] else None),
                    "median_triggers": (float(np.median(counts)) if counts else None),
                    "mean_triggers": (float(np.mean(counts)) if counts else None),
                    "illegal": book["illegal"],
                    "uncertifiable": book["uncertifiable"]})
            out[key] = cash
    return out


def stage_o(plane: Plane, root: Path) -> dict[str, object]:
    asset = plane.records[0].asset
    d8 = plane.records[0].d8
    check = conversion_check(asset, d8, root)
    if not check["ok"]:
        raise SweepRefusal(f"USD->mid2 conversion failed its substrate check: {check}")
    return {"conversion_check": check, "o1": o1(plane), "o2": o2(plane),
            "o3": o3(plane)}


# --------------------------------------------------------------------------
# STAGE A: no cash.
# --------------------------------------------------------------------------

def stage_a(plane: Plane) -> dict[str, object]:
    configs: dict[str, dict[str, object]] = {}
    for config in CONFIGS:
        per_asset: dict[str, dict[str, object]] = {}
        pooled_entries = 0
        pooled_cells = 0
        pooled_seconds: list[float] = []
        for asset in ASSETS:
            entries, counts, detail = entries_for(plane, config, asset)
            total = max(1, plane.cells.get(asset, 1))
            seconds = [row["entry_seconds"] for row in detail]
            depths = [row["depth_atr"] for row in detail]
            hits = 0
            scored = 0
            for row, entry in zip(detail, entries):
                star = plane.stars[row["position"]]
                bar = int(row["entry_bar"])
                if not bool(star.sharp[bar]):
                    continue
                scored += 1
                hits += int(int(star.sign[bar]) != int(entry.side))
            low, high = S1.wilson(hits, scored)
            per_asset[asset] = {
                "cells": plane.cells.get(asset, 0),
                "entered": len(entries),
                "coverage": len(entries) / total,
                "no_context": counts["no_context"],
                "no_event": counts["no_event"],
                "triggered": counts["triggered"],
                "unavailable": counts["illegal"] + counts["uncertifiable"],
                "illegal": counts["illegal"],
                "uncertifiable": counts["uncertifiable"],
                "entry_seconds_median": (float(np.median(seconds)) if seconds else None),
                "depth_atr_median": (float(np.median(depths)) if depths else None),
                "long_fraction": (float(np.mean([e.side > 0 for e in entries]))
                                  if entries else None),
                "error": (hits / scored if scored else None),
                "error_n": scored, "error_hits": hits,
                "ci95": [low, high],
            }
            pooled_entries += len(entries)
            pooled_cells += plane.cells.get(asset, 0)
            pooled_seconds.extend(seconds)
        configs[config.key] = {
            "params": config.params, "simplicity": list(config.simplicity),
            "by_asset": per_asset,
            "coverage_pooled": pooled_entries / max(1, pooled_cells),
            "entered_pooled": pooled_entries,
            "entry_seconds_median_pooled": (float(np.median(pooled_seconds))
                                            if pooled_seconds else None),
        }
    return {"coverage_floor": COVERAGE_FLOOR, "configs": configs,
            "selection": {asset: select_for_asset(configs, asset)
                          for asset in ASSETS}}


def _order_key(configs: Mapping[str, Mapping[str, object]], asset: str, key: str
               ) -> tuple:
    entry = configs[key]
    row = entry["by_asset"][asset]
    seconds = row["entry_seconds_median"]
    return (float(row["ci95"][1]),
            float("inf") if seconds is None else float(seconds),
            tuple(entry["simplicity"]), key)


def select_for_asset(configs: Mapping[str, Mapping[str, object]], asset: str
                     ) -> dict[str, object]:
    """Best and runner-up, no cash: CI upper, then coverage floor, delay, simplicity."""

    passing = [key for key, entry in configs.items()
               if float(entry["by_asset"][asset]["coverage"]) >= COVERAGE_FLOOR]
    flags: list[str] = []
    pool = passing
    if not pool:
        flags.append("COVERAGE_FAIL")
        pool = list(configs)
    ordered = sorted(pool, key=lambda key: _order_key(configs, asset, key))
    best = ordered[0]
    best_anchor = ZONE_BY_KEY[best.split("/")[0]].anchor
    runner = None
    for key in ordered[1:]:
        if ZONE_BY_KEY[key.split("/")[0]].anchor != best_anchor:
            runner = key
            break
    if runner is None:
        flags.append("NO_CROSS_ANCHOR_RUNNERUP")
        runner = ordered[1] if len(ordered) > 1 else None
    return {"best": best, "runner_up": runner, "flags": flags,
            "n_pass_coverage": len(passing), "ordered": ordered[:8]}


# --------------------------------------------------------------------------
# STAGE B: cash.
# --------------------------------------------------------------------------

def replay_asset(entries: Sequence[S1.Entry], records: Sequence[S1.CellRec],
                 assets: Sequence[str], tag: str) -> dict[str, object]:
    """``S1.replay_line`` with the expected-session set cut to ``assets``."""

    keep = [position for position, rec in enumerate(records) if rec.asset in assets]
    remap = {old: new for new, old in enumerate(keep)}
    subset = [records[position] for position in keep]
    rows = [replace(row, cell=remap[row.cell]) for row in entries
            if row.cell in remap]
    return S1.replay_line(rows, subset, f"mill-sweep3:{code_sha()[:16]}:{tag}")


def stress_line(entries: Sequence[S1.Entry], records: Sequence[S1.CellRec],
                days: Mapping[str, int], cells: Mapping[str, int],
                asset: str, rate: float = STRESS_RATE) -> dict[str, object]:
    """Flip ``rate`` of the entries to the opposite side at the same bars.

    Adversarial: among the flips that stay legal and certifiable at the same
    bar, the ones with the largest cert damage are the ones taken.
    """

    rows = [row for row in entries if row.asset == asset]
    target = int(round(rate * len(rows)))
    damages: list[tuple[float, int]] = []
    for position, row in enumerate(rows):
        rec = records[row.cell]
        other = -row.side
        if not rec.legal_at(other, row.bar) or not bool(rec.ok(other)[row.bar]):
            continue
        damages.append((row.cert_usd - float(rec.cert(other)[row.bar]), position))
    damages.sort(key=lambda item: (-item[0], item[1]))
    picks = {position for _damage, position in damages[:target]}
    flipped: list[S1.Entry] = []
    for position, row in enumerate(rows):
        if position not in picks:
            flipped.append(row)
            continue
        swap = S1.make_entry(row.cell, records[row.cell], row.bar, -row.side)
        flipped.append(swap if swap is not None else row)
    line = S1.cash_line(flipped, days, cells)[asset]
    line.update({"flips_requested": target, "flips_applied": len(picks),
                 "flips_available": len(damages), "rate": rate,
                 "damage_usd": float(sum(damage for damage, _p in damages[:target]))})
    return line


def stage_b(plane: Plane, explore_days: Mapping[str, list[int]],
            a_report: Mapping[str, object]) -> dict[str, object]:
    gate = S1.r0_gate(plane.records)
    sweep1_gate = json.loads(SWEEP1_PATH.read_text())["stage_b"]["r0_median_gate_mid2"]
    report: dict[str, object] = {
        "r0_median_gate_mid2": gate,
        "r0_gate_matches_sweep1": {asset: bool(
            abs(float(gate[asset]) - float(sweep1_gate[asset])) < 1e-6)
            for asset in ASSETS},
        "lines": {}, "replays": {}, "stress": {}}
    priced: dict[str, list[S1.Entry]] = {}
    best_pool: list[S1.Entry] = []
    selection = a_report["selection"]
    for asset in ASSETS:
        pick = selection[asset]
        plan = [("BEST", pick["best"], None), ("RUNNERUP", pick["runner_up"], None),
                ("BEST+F4", pick["best"], gate)]
        for role, key, gate_used in plan:
            if key is None:
                continue
            config = next(item for item in CONFIGS if item.key == key)
            entries, counts, detail = entries_for(plane, config, asset, gate_used)
            name = f"{asset}/{role}"
            priced[name] = entries
            if role == "BEST":
                best_pool.extend(entries)
            seconds = [row["entry_seconds"] for row in detail]
            depths = [row["depth_atr"] for row in detail]
            line = S1.cash_line(entries, plane.days, plane.cells)[asset]
            line.update({
                "role": role, "config": key, "params": config.params,
                "gate": (float(gate_used[asset]) if gate_used else None),
                "skips": counts,
                "entry_seconds_median": (float(np.median(seconds)) if seconds else None),
                "depth_atr_median": (float(np.median(depths)) if depths else None),
                "line_name": name,
                "rung_usd": DAY_RUNG_USD[asset]})
            report["lines"][name] = line
            if role == "BEST":
                report["replays"][name] = replay_asset(
                    entries, plane.records, (asset,), name.replace("/", "-"))
                report["stress"][name] = stress_line(
                    entries, plane.records, plane.days, plane.cells, asset)
    priced["PORTFOLIO/BEST"] = best_pool
    report["portfolio"] = S1.cash_line(best_pool, plane.days, plane.cells)
    report["replays"]["PORTFOLIO/BEST"] = replay_asset(
        best_pool, plane.records, ASSETS, "PORTFOLIO-BEST")
    report["nulls"] = S1.block_null(priced, explore_days, draws=NULL_DRAWS, seed=SEED)
    report["o3_gap"] = o3_gap(plane, selection)
    return report


def o3_gap(plane: Plane, selection: Mapping[str, Mapping[str, object]]
           ) -> dict[str, object]:
    """Cash of the oracle-timing variant of each asset's selected best line."""

    out: dict[str, object] = {}
    blocks = o3(plane)
    for asset in ASSETS:
        key = selection[asset]["best"]
        zone_key, tau_key, _r = key.split("/")
        block = blocks[f"{zone_key}/{tau_key}"]
        out[asset] = {"config": key, "oracle_timing_line": f"{zone_key}/{tau_key}",
                      "usd_per_asset_day": block[asset]["usd_per_asset_day"],
                      "usd_per_trade": block[asset]["usd_per_trade"],
                      "trades": block[asset]["trades"],
                      "first_is_last_fraction": block[asset]["first_is_last_fraction"]}
    return out


# --------------------------------------------------------------------------
# Hypothesis log.
# --------------------------------------------------------------------------

def log_rows(report: Mapping[str, object]) -> list[dict[str, object]]:
    stamp = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    shared = {
        "registered_utc": stamp, "spec_sha": SPEC_SHA, "code_sha": code_sha(),
        "split_sha": split_sha(), "outcome_law_sha": outcome_law_sha(),
        "null_seed": SEED, "parent_trial": PARENT_TRIAL,
        "selection_rule": SELECTION_RULE, "verdict": "",
        "days": sum(report["asset_days"].values()),
    }
    column = {"HG": "err_rate_hg", "NKD": "err_rate_nkd", "SI": "err_rate_si"}
    usd = {"HG": "hg_usd_day", "NKD": "nkd_usd_day", "SI": "si_usd_day"}
    mdd = {"HG": "mdd_hg", "NKD": "mdd_nkd", "SI": "mdd_si"}
    walls = {"HG": "walls_hg", "NKD": "walls_nkd", "SI": "walls_si"}
    rows: list[dict[str, object]] = []
    counter = 0
    stage = report["stage_a"]
    chosen: dict[str, list[str]] = {}
    for asset in ASSETS:
        pick = stage["selection"][asset]
        for role, key in (("B", pick["best"]), ("R", pick["runner_up"])):
            if key:
                chosen.setdefault(key, []).append(f"{asset}:{role}")
    for key in sorted(stage["configs"]):
        entry = stage["configs"][key]
        counter += 1
        mark = ";SEL " + ",".join(chosen[key]) if key in chosen else ""
        row = {**shared, "id": f"sweep3-{counter:03d}", "family": FAMILY,
               "rule": key, "params": json.dumps(entry["params"]),
               "coverage": entry["coverage_pooled"],
               "delay_med_s": entry["entry_seconds_median_pooled"],
               "note": ("stage-A no-cash" + mark)[:60]}
        for asset in ASSETS:
            row[column[asset]] = entry["by_asset"][asset]["error"]
        rows.append(row)
    if "stage_b" not in report:
        return rows
    nulls = report["stage_b"]["nulls"]["by_line"]
    replays = report["stage_b"]["replays"]
    for name in sorted(report["stage_b"]["lines"]):
        line = report["stage_b"]["lines"][name]
        asset = name.split("/")[0]
        counter += 1
        skips = ""
        if replays.get(name, {}).get("status") == "OK":
            skips = replays[name]["occupancy_or_cap_skips"]
        row = {**shared, "id": f"sweep3-{counter:03d}", "family": FAMILY,
               "rule": name, "params": json.dumps(line["params"]),
               "coverage": line["coverage"],
               "delay_med_s": line["entry_seconds_median"],
               column[asset]: stage["configs"][line["config"]]["by_asset"][asset]["error"],
               walls[asset]: line["walls"], usd[asset]: line["usd_per_asset_day"],
               mdd[asset]: line["mdd_day_usd"], "replay_skips": skips,
               "null_margin": nulls.get(name, {}).get("p_max_adjusted"),
               "note": f"stage-B {line['role']} {line['config']}"[:60]}
        rows.append(row)
    counter += 1
    portfolio = report["stage_b"]["portfolio"]
    null = nulls.get("PORTFOLIO/BEST", {})
    skips = ""
    if replays.get("PORTFOLIO/BEST", {}).get("status") == "OK":
        skips = replays["PORTFOLIO/BEST"]["occupancy_or_cap_skips"]
    rows.append({
        **shared, "id": f"sweep3-{counter:03d}", "family": FAMILY,
        "rule": "PORTFOLIO/BEST",
        "params": json.dumps({asset: stage["selection"][asset]["best"]
                              for asset in ASSETS}),
        "coverage": float(np.mean([portfolio[a]["coverage"] for a in ASSETS])),
        "delay_med_s": None,
        **{column[a]: stage["configs"][stage["selection"][a]["best"]][
            "by_asset"][a]["error"] for a in ASSETS},
        **{walls[a]: portfolio[a]["walls"] for a in ASSETS},
        **{usd[a]: portfolio[a]["usd_per_asset_day"] for a in ASSETS},
        **{mdd[a]: portfolio[a]["mdd_day_usd"] for a in ASSETS},
        "replay_skips": skips,
        "null_margin": null.get("p_pooled_max_adjusted"),
        "note": "stage-B portfolio of the three best lines"[:60]})
    return rows


# --------------------------------------------------------------------------
# Report I/O and printing.
# --------------------------------------------------------------------------

def read_report() -> dict[str, object]:
    if OUT_PATH.is_file():
        return json.loads(OUT_PATH.read_text())
    return {"schema": SCHEMA, "tier": "exploratory",
            "claim": "EXPLORE-day sweep 3 DEEP-FADE; can kill, cannot promote"}


def write_report(report: Mapping[str, object]) -> None:
    payload = {key: value for key, value in report.items()
               if not key.startswith("_")}
    OUT_PATH.write_text(json.dumps(payload, sort_keys=True, indent=1,
                                   default=S1._json_default) + "\n")


def _num(value: object, width: int = 8, digits: int = 2) -> str:
    return S1._num(value, width, digits)


def print_conversion(check: Mapping[str, object]) -> None:
    print("\n== USD -> mid2 conversion, checked against a substrate row")
    print(f"  {check['asset']}/{check['d8']} row {check['row']}: "
          f"bid={check['bid']} ask={check['ask']} ask-bid={check['ask_minus_bid']}")
    print(f"  multiplier={check['multiplier']}  1 usd of price move = "
          f"{check['usd_to_mid2']:.1f} mid2 units")
    print(f"  entry_spread_usd={check['entry_spread_usd']:.6f} -> "
          f"{check['spread_usd_in_mid2']:.1f} mid2 vs 2*(ask-bid)="
          f"{check['two_times_ask_minus_bid']:.1f}  ok={check['ok']}")


def print_o1(block: Mapping[str, object]) -> None:
    print("\n== O1 terminal extreme (Delta*-winner adverse direction) location")
    print(f"{'asset':5s} {'cells':>6s} {'noctx':>6s} {'noside':>6s} {'t_p25':>8s} "
          f"{'t_p50':>8s} {'t_p75':>8s} {'frac50':>7s} {'depth50':>8s} {'inwin':>7s}")
    for asset in ASSETS:
        row = block[asset]
        sec, frac, depth = (row["terminal_seconds"], row["terminal_phase_fraction"],
                            row["terminal_depth_atr"])
        print(f"{asset:5s} {row['eligible_cells']:6d} "
              f"{row['cells_without_context']:6d} {row['cells_without_sharp_side']:6d} "
              f"{_num(sec.get('p25'))} {_num(sec.get('p50'))} {_num(sec.get('p75'))} "
              f"{_num(frac.get('p50'), 7, 3)} {_num(depth.get('p50'), 8, 3)} "
              f"{_num(row['in_tradeable_window_fraction'], 7, 3)}")
    print(f"\n  {'zone':10s} " + " ".join(f"{asset:>8s}" for asset in ASSETS)
          + "    fraction of terminal extremes inside the zone")
    for zone in ZONES:
        print(f"  {zone.key:10s} " + " ".join(
            f"{block[asset]['in_zone_fraction'][zone.key]:8.3f}" for asset in ASSETS))
    print(f"  {'ANY':10s} " + " ".join(
        f"{block[asset]['any_zone_fraction']:8.3f}" for asset in ASSETS))


def print_o2(block: Mapping[str, object]) -> None:
    print("\n== O2 oracle terminal-extreme entry (perfect entry, legality applied)")
    print(f"{'line':16s} {'asset':5s} {'trd':>5s} {'cov':>6s} {'usd/day':>9s} "
          f"{'usd/trd':>9s} {'win':>6s} {'wall':>6s} {'mdd_day':>9s} {'mdd_trd':>9s} "
          f"{'REM_ceil':>9s} {'capture':>8s}")
    for name, line in block["lines"].items():
        for asset in ASSETS:
            row = line[asset]
            print(f"{name:16s} {asset:5s} {row['trades']:5d} "
                  f"{_num(row['coverage'], 6, 3)} {_num(row['usd_per_asset_day'], 9, 1)} "
                  f"{_num(row['usd_per_trade'], 9, 1)} {_num(row['win_rate'], 6, 3)} "
                  f"{_num(row['wall_rate'], 6, 3)} {_num(row['mdd_day_usd'], 9, 1)} "
                  f"{_num(row['mdd_trade_usd'], 9, 1)} "
                  f"{_num(row['rem_ceiling_legal_usd_day'], 9, 1)} "
                  f"{_num(row['capture_of_ceiling'], 8, 3)}")


def print_o3(block: Mapping[str, object]) -> None:
    print("\n== O3 oracle TIMING: entry at the LAST in-zone extreme, per config")
    print(f"{'config':18s} {'asset':5s} {'trd':>5s} {'cov':>6s} {'usd/day':>9s} "
          f"{'usd/trd':>9s} {'wall':>6s} {'mdd_day':>9s} {'trig':>5s} "
          f"{'1trig':>6s} {'medtrg':>7s}")
    for key in sorted(block):
        line = block[key]
        for asset in ASSETS:
            row = line[asset]
            print(f"{key:18s} {asset:5s} {row['trades']:5d} "
                  f"{_num(row['coverage'], 6, 3)} {_num(row['usd_per_asset_day'], 9, 1)} "
                  f"{_num(row['usd_per_trade'], 9, 1)} {_num(row['wall_rate'], 6, 3)} "
                  f"{_num(row['mdd_day_usd'], 9, 1)} {row['triggered_cells']:5d} "
                  f"{_num(row['first_is_last_fraction'], 6, 3)} "
                  f"{_num(row['median_triggers'], 7, 1)}")


def print_stage_a(report: Mapping[str, object], top: int = 5) -> None:
    configs = report["configs"]
    print("\n== STAGE A (no cash): per-asset top configs by selection order")
    for asset in ASSETS:
        pick = report["selection"][asset]
        print(f"\n-- {asset}  floor={COVERAGE_FLOOR:.2f} "
              f"pass={pick['n_pass_coverage']}/{len(configs)} "
              f"flags={','.join(pick['flags']) or '-'}")
        print(f"  {'config':22s} {'cov':>6s} {'ent':>5s} {'noev':>5s} {'unav':>5s} "
              f"{'err':>6s} {'ci_lo':>6s} {'ci_hi':>6s} {'n_err':>6s} "
              f"{'t_med':>7s} {'depth':>7s} {'long':>6s}")
        for key in pick["ordered"][:top]:
            row = configs[key]["by_asset"][asset]
            mark = "*" if key == pick["best"] else ("+" if key == pick["runner_up"] else " ")
            print(f" {mark}{key:22s} {_num(row['coverage'], 6, 3)} "
                  f"{row['entered']:5d} {row['no_event']:5d} {row['unavailable']:5d} "
                  f"{_num(row['error'], 6, 3)} {_num(row['ci95'][0], 6, 3)} "
                  f"{_num(row['ci95'][1], 6, 3)} {row['error_n']:6d} "
                  f"{_num(row['entry_seconds_median'], 7, 0)} "
                  f"{_num(row['depth_atr_median'], 7, 2)} "
                  f"{_num(row['long_fraction'], 6, 2)}")
        print(f"  selected best={pick['best']} runner_up={pick['runner_up']}")


def print_stage_b(block: Mapping[str, object]) -> None:
    print("\n== STAGE B priced lines (exploratory; verdict column left empty)")
    print(f"{'line':18s} {'config':22s} {'trd':>5s} {'cov':>6s} {'usd/day':>9s} "
          f"{'rung':>6s} {'usd/trd':>9s} {'win':>6s} {'wall':>6s} {'mdd_day':>9s} "
          f"{'mdd_trd':>9s} {'t_med':>7s}")
    for name in sorted(block["lines"]):
        row = block["lines"][name]
        print(f"{name:18s} {row['config']:22s} {row['trades']:5d} "
              f"{_num(row['coverage'], 6, 3)} {_num(row['usd_per_asset_day'], 9, 1)} "
              f"{row['rung_usd']:6.0f} {_num(row['usd_per_trade'], 9, 1)} "
              f"{_num(row['win_rate'], 6, 3)} {_num(row['wall_rate'], 6, 3)} "
              f"{_num(row['mdd_day_usd'], 9, 1)} {_num(row['mdd_trade_usd'], 9, 1)} "
              f"{_num(row['entry_seconds_median'], 7, 0)}")
    print("\n-- portfolio of the three BEST lines")
    for asset in ASSETS:
        row = block["portfolio"][asset]
        print(f"  {asset:5s} trades={row['trades']:4d} "
              f"usd/day={row['usd_per_asset_day']:9.1f} "
              f"mdd_day={row['mdd_day_usd']:8.1f} mdd_trade={row['mdd_trade_usd']:8.1f}")
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
    print("\n-- 2% adversarial stress on each asset's BEST line")
    print(f"  {'line':18s} {'flips':>6s} {'avail':>6s} {'usd/day':>9s} "
          f"{'usd/trd':>9s} {'wall':>6s} {'mdd_day':>9s} {'mdd_trd':>9s}")
    for name in sorted(block["stress"]):
        row = block["stress"][name]
        print(f"  {name:18s} {row['flips_applied']:6d} {row['flips_available']:6d} "
              f"{_num(row['usd_per_asset_day'], 9, 1)} "
              f"{_num(row['usd_per_trade'], 9, 1)} {_num(row['wall_rate'], 6, 3)} "
              f"{_num(row['mdd_day_usd'], 9, 1)} {_num(row['mdd_trade_usd'], 9, 1)}")
    print("\n-- O3 oracle-timing cash for the selected configs (gap vs the causal line)")
    for asset in ASSETS:
        row = block["o3_gap"][asset]
        print(f"  {asset:5s} {row['config']:22s} oracle usd/day="
              f"{_num(row['usd_per_asset_day'], 9, 1)} "
              f"usd/trd={_num(row['usd_per_trade'], 9, 1)} "
              f"trades={row['trades']:4d} first_is_last="
              f"{_num(row['first_is_last_fraction'], 6, 3)}")
    nulls = block["nulls"]
    print(f"\n-- block-permutation null, {nulls['draws']} draws, seed {nulls['seed']}, "
          "max-statistic across every priced line")
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
# Selftest: synthetic arrays and a synthetic context store, zero era bytes.
# --------------------------------------------------------------------------

SELFTEST_ASSET = "HG"
SELFTEST_ATR_USD = 1000.0
SELFTEST_ATR_MID2 = 80_000_000.0     # 1000 usd * 2e9 / 25000
SELFTEST_PRIOR_LOW = 9_160_000_000.0
SELFTEST_PRIOR_HIGH = 9_240_000_000.0
SELFTEST_OPEN = 9_200_000_000.0


def _cell(mid: Sequence[float], asset: str = SELFTEST_ASSET,
          legal_p: int = 0, legal_m: int = 0) -> S1.CellRec:
    """A synthetic cell whose every bar is legal and certifiable on both sides."""

    n = len(mid)
    lat = np.arange(n, dtype=np.int64) * S1.BAR_NS
    return S1.CellRec(
        asset=asset, d8=20220301, phase="0", text=f"{asset}/20220301/0/0",
        phase_open_ts_ns=0, phase_close_ts_ns=int(n * S1.BAR_NS),
        locked_iid=1, pack_sha256="0" * 64, raw_first=0, k0=1, r0_mid2=100.0,
        legal_from_p=int(legal_p), legal_from_m=int(legal_m),
        lat=lat, mid=np.asarray(mid, np.int64), bar_ok=np.ones(n, bool),
        cost=np.full(n, 20.0), cert_p=np.zeros(n), cert_m=np.zeros(n),
        ok_p=np.ones(n, bool), ok_m=np.ones(n, bool),
        wall_p=np.zeros(n, bool), wall_m=np.zeros(n, bool),
        exit_p=lat.copy(), exit_m=lat.copy(),
        cum_long=np.zeros(n, np.int32), cum_short=np.zeros(n, np.int32),
        raw_cut=np.zeros(n, np.int64), raw_last=np.zeros(n, np.int64))


def _ctx() -> Ctx:
    return Ctx(atr_usd=SELFTEST_ATR_USD, atr_mid2=SELFTEST_ATR_MID2,
               prior_d8=20220228, prior_low=SELFTEST_PRIOR_LOW,
               prior_high=SELFTEST_PRIOR_HIGH, prior_close=SELFTEST_OPEN,
               open_mid2=SELFTEST_OPEN, open_bar=0)


def _selftest_zone() -> list[tuple[str, bool, str]]:
    """Hand-computed zone membership, both anchors, both sides.

    HG's multiplier is 25000, so one USD of price move is 2e9/25000 = 80,000
    mid2 units and an ATR of 1000 usd is 80,000,000 mid2 units by hand.
    prior_low = 9.160e9, prior_high = 9.240e9, phase_open = 9.200e9.

      A1(m=+0.25) LONG  threshold 9.160e9 + 0.25*8e7 = 9.180e9   (mid <= it)
      A1(m=+0.25) SHORT threshold 9.240e9 - 0.25*8e7 = 9.220e9   (mid >= it)
      A1(m=-0.10) LONG  threshold 9.160e9 - 0.10*8e7 = 9.152e9
      A1(m=-0.10) SHORT threshold 9.240e9 + 0.10*8e7 = 9.248e9
      A2(D=0.50)  LONG  threshold 9.200e9 - 0.50*8e7 = 9.160e9
      A2(D=0.50)  SHORT threshold 9.200e9 + 0.50*8e7 = 9.240e9
      A2(D=1.25)  LONG  threshold 9.200e9 - 1.25*8e7 = 9.100e9
      A2(D=1.25)  SHORT threshold 9.200e9 + 1.25*8e7 = 9.300e9

    The six hand bars are 9.150e9, 9.160e9, 9.185e9, 9.230e9, 9.250e9, 9.090e9.
    """

    mid = [9_150_000_000, 9_160_000_000, 9_185_000_000,
           9_230_000_000, 9_250_000_000, 9_090_000_000]
    rec = _cell(mid)
    ctx = _ctx()
    conv = usd_to_mid2(SELFTEST_ASSET)
    checks: list[tuple[str, bool, str]] = [
        ("usd_to_mid2_hand_value", conv == 80_000.0,
         f"1 usd -> {conv} mid2 units, hand value 2e9/25000 = 80000"),
        ("atr_usd_to_mid2_hand_value",
         SELFTEST_ATR_USD * conv == SELFTEST_ATR_MID2,
         f"{SELFTEST_ATR_USD} usd -> {SELFTEST_ATR_USD * conv} mid2, "
         f"hand value {SELFTEST_ATR_MID2}"),
    ]
    want = {
        "A1m+0.25": ((9_180_000_000.0, 9_220_000_000.0),
                     [True, True, False, False, False, True],
                     [False, False, False, True, True, False]),
        "A1m-0.10": ((9_152_000_000.0, 9_248_000_000.0),
                     [True, False, False, False, False, True],
                     [False, False, False, False, True, False]),
        "A2D0.50": ((9_160_000_000.0, 9_240_000_000.0),
                    [True, True, False, False, False, True],
                    [False, False, False, False, True, False]),
        "A2D1.25": ((9_100_000_000.0, 9_300_000_000.0),
                    [False, False, False, False, False, True],
                    [False, False, False, False, False, False]),
    }
    for key, (thresholds, long_hand, short_hand) in want.items():
        zone = ZONE_BY_KEY[key]
        seen = zone_thresholds(zone, ctx)
        long_mask, short_mask = zone_masks(rec, ctx, zone)
        checks.append((f"zone_thresholds_{key}",
                       all(abs(a - b) <= 1e-6 for a, b in zip(seen, thresholds)),
                       f"{seen} expected {thresholds}"))
        checks.append((f"zone_long_membership_{key}",
                       list(map(bool, long_mask)) == long_hand,
                       f"{list(map(bool, long_mask))} expected {long_hand}"))
        checks.append((f"zone_short_membership_{key}",
                       list(map(bool, short_mask)) == short_hand,
                       f"{list(map(bool, short_mask))} expected {short_hand}"))
    return checks


def _trigger_series() -> list[int]:
    """Bars 0..119; the phase is 7200 s so the 1800 s deadline is bar 90."""

    values = [9_200_000_000] * 15
    values += [9_195_000_000, 9_190_000_000, 9_185_000_000, 9_180_000_000,
               9_170_000_000]                                  # bars 15..19
    values += [9_150_000_000, 9_152_000_000, 9_146_000_000,
               9_151_000_000, 9_160_000_000]                   # bars 20..24
    values += [9_160_000_000] * (120 - len(values))
    return values


def _selftest_trigger() -> list[tuple[str, bool, str]]:
    """Hand-computed trigger, rebound, and the newer-extreme reset.

    Zone A1(m=0.0): LONG threshold = prior_low = 9.160e9.  Every bar from 15
    to 20 sets a new running minimum; bar 19 (9.170e9) is above the threshold
    and bar 20 (9.150e9) is the first new running minimum inside the zone, so
    T = 20 and the side is LONG.  HG's raw tick is 500,000, so r ticks are
    r*2*500,000 = r*1e6 mid2 units.

      r=0  enters at bar 20.
      r=4  step 4e6.  Bar 21 (9.152e9) is +2e6 off the extreme, not enough.
           Bar 22 (9.146e9) is a NEWER running minimum, so the wait resets to
           it and the target becomes 9.146e9 + 4e6 = 9.150e9.  Bar 23
           (9.151e9) clears the reset target and enters.  Without the reset
           the target would still be 9.150e9 + 4e6 = 9.154e9, which bar 23
           misses and bar 24 (9.160e9) meets: the reset moves the entry from
           bar 24 to bar 23.
      r=8  step 8e6 off the reset extreme is 9.154e9: bar 23 misses, bar 24
           meets, entry at bar 24.
    """

    values = _trigger_series()
    rec = _cell(values)
    ctx = _ctx()
    ext = S2.extremes(rec)
    zone = ZONE_BY_KEY["A1m+0.00"]
    masks = zone_masks(rec, ctx, zone)
    step4 = rebound_step(SELFTEST_ASSET, 4)
    shots = {ticks: fire(rec, ext, masks, 900, ticks) for ticks in REBOUND_TICKS}
    checks = [
        ("trigger_deadline_bar_is_phase_close_minus_1800s",
         S2.deadline_bar(rec) == 90, f"deadline={S2.deadline_bar(rec)} expected 90"),
        ("rebound_step_is_r_raw_ticks", step4 == 4_000_000.0,
         f"4 ticks = {step4} mid2, hand value 4*2*500000"),
        ("zone_excludes_the_shallow_extreme",
         not bool(masks[0][19]) and bool(masks[0][20]),
         f"bar19 in zone={bool(masks[0][19])} bar20={bool(masks[0][20])}"),
        ("trigger_bar_is_the_first_in_zone_new_extreme",
         shots[0] is not None and shots[0].trigger_bar == 20 and shots[0].side == 1,
         f"{shots[0]}"),
        ("rebound_zero_enters_at_the_trigger",
         shots[0] is not None and shots[0].entry_bar == 20, f"{shots[0]}"),
        ("newer_extreme_resets_the_wait",
         shots[4] is not None and shots[4].entry_bar == 23
         and shots[4].extreme_bar == 22 and shots[4].trigger_bar == 20,
         f"{shots[4]} expected entry 23 off the bar-22 reset extreme"),
        ("reset_case_discriminates_against_no_reset",
         values[23] < values[20] + step4 <= values[24],
         f"bar23={values[23]} bar24={values[24]} no-reset target="
         f"{values[20] + step4}"),
        ("larger_rebound_waits_longer",
         shots[8] is not None and shots[8].entry_bar == 24, f"{shots[8]}"),
    ]
    # Both sides armed: an earlier in-zone new running MAXIMUM wins the cell.
    both = list(values)
    both[15] = 9_230_000_000
    both[16] = 9_245_000_000
    both[17] = 9_200_000_000
    both[18] = 9_180_000_000
    both[19] = 9_170_000_000
    rec_both = _cell(both)
    shot_both = fire(rec_both, S2.extremes(rec_both),
                     zone_masks(rec_both, ctx, zone), 900, 0)
    checks.append((
        "first_trigger_wins_across_the_two_armed_sides",
        shot_both is not None and shot_both.side == -1
        and shot_both.entry_bar == 16,
        f"{shot_both} expected the bar-16 short trigger to beat the bar-20 long"))
    # tau0 gates the arming window: the same cell abstains under tau0 = 1800 s
    # only if its triggers all sit before bar 30, so check the deadline instead.
    late = [9_200_000_000] * 120
    late[100] = 9_100_000_000
    rec_late = _cell(late)
    checks.append((
        "deadline_blocks_a_late_trigger",
        fire(rec_late, S2.extremes(rec_late), zone_masks(rec_late, ctx, zone),
             900, 0) is None,
        "a trigger past phase_close-1800s was accepted"))
    early = _cell(values)
    checks.append((
        "tau0_gates_the_arming_window",
        fire(early, S2.extremes(early), zone_masks(early, ctx, zone), 1800, 0)
        is None,
        "a trigger before tau0=1800s was accepted"))
    return checks


def _write_context_fixture(root: Path) -> None:
    """A synthetic context store: the three tables the reader requires."""

    def table(path: Path, schema: str, columns: Sequence[str],
              rows: Sequence[Sequence[object]]) -> None:
        lines = [f"# {schema} rows={len(rows)}", "\t".join(columns)]
        lines += ["\t".join(str(value) for value in row) for row in rows]
        path.write_text("\n".join(lines) + "\n")

    root.mkdir(parents=True, exist_ok=True)
    table(root / CTX.PRIORS_NAME, CTX.PRIORS_SCHEMA,
          ("asset", "d8", "atr14_present", "atr14_prev_usd"),
          [("HG", 20220101, 1, 1000.0), ("HG", 20220102, 1, 1100.0),
           ("HG", 20220103, 1, 1200.0)])
    table(root / CTX.FORECAST_NAME, CTX.FORECAST_SCHEMA, ("day", "d8"), [])
    table(root / CTX.LEVELS_NAME, CTX.LEVELS_SCHEMA,
          ("asset", "d8", "session_high_mid2", "session_low_mid2",
           "session_close_mid2"),
          [("HG", 20220101, 9_300_000_000, 9_100_000_000, 9_200_000_000),
           ("HG", 20220102, 9_240_000_000, 9_160_000_000, 9_180_000_000),
           ("HG", 20220103, 1, 2, 3)])


def _selftest_context() -> list[tuple[str, bool, str]]:
    """Integration: the real ContextStore, a synthetic store, the prior guard."""

    checks: list[tuple[str, bool, str]] = []
    with tempfile.TemporaryDirectory() as handle:
        root = Path(handle)
        _write_context_fixture(root)
        store = CTX.ContextStore(root)
        checks.append(("context_cutoff_is_strictly_prior",
                       CTX.levels_cutoff(20220103) == 20220102,
                       f"cutoff={CTX.levels_cutoff(20220103)} for day 20220103"))
        for day in (20220101, 20220102, 20220103):
            payload = store.context_for("HG", day)
            served = sorted(CTX.served_levels_days(payload))
            checks.append((f"context_serves_only_earlier_days_{day}",
                           all(value < day for value in served),
                           f"day {day} was served levels {served}"))
        rec = _cell(_trigger_series())
        rec.d8 = 20220103
        ctx = cell_context(store, rec)
        checks.append(("cell_context_takes_the_prior_day_levels",
                       ctx is not None and ctx.prior_d8 == 20220102
                       and ctx.prior_low == 9_160_000_000.0
                       and ctx.prior_high == 9_240_000_000.0,
                       f"{ctx}"))
        checks.append(("cell_context_uses_its_own_day_atr",
                       ctx is not None
                       and ctx.atr_mid2 == 1200.0 * usd_to_mid2("HG"),
                       f"atr_mid2={None if ctx is None else ctx.atr_mid2}"))
        checks.append(("cell_context_never_reads_its_own_day_levels",
                       ctx is not None and ctx.prior_low != 2.0,
                       "the requesting day's own session low leaked in"))
        first = _cell(_trigger_series())
        first.d8 = 20220101
        checks.append(("cell_without_a_prior_day_is_skipped",
                       cell_context(store, first) is None,
                       "the first day in the store produced a context"))
    return checks


def selftest() -> int:
    mutant = _sweep_mutant()
    checks: list[tuple[str, bool, str]] = [
        ("config_grid_is_7_zones_x_2_tau_x_3_r", len(CONFIGS) == 42,
         f"{len(CONFIGS)} configs from {len(ZONES)} zones"),
    ]
    checks.extend(_selftest_zone())
    checks.extend(_selftest_trigger())
    checks.extend(_selftest_context())
    dead = [(name, why) for name, ok, why in checks if not ok]
    if dead:
        for name, why in dead:
            print(f"DEAD: {name}: {why}")
        print(f"sweep3_selftest_dead mutant={mutant or 'none'} "
              f"cases={len(dead)}/{len(checks)}")
        return 1
    if mutant:
        print(f"DEAD: mutant {mutant} left every sweep-3 case green")
        return 1
    print(f"sweep3_selftest_ok cases={len(checks)}")
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _load(assets: Sequence[str], root: Path
          ) -> tuple[list[S1.CellRec], dict[str, int]]:
    try:
        return S1.load_cache()
    except S1.SweepRefusal:
        store = M.load_store(SPLIT_PATH, assets, root=root)
        records, days = S1.prep(store)
        S1.save_cache(records, days)
        return records, days


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", nargs="?", default="all",
                        choices=("stage-o", "stage-a", "stage-b", "log", "all"))
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
    records, days = _load(assets, Path(args.root))
    explore_days = S1._explore_days(assets)
    store = CTX.ContextStore()
    plane = build_plane(records, store, days)
    report = read_report()
    report.setdefault("spec_sha", SPEC_SHA)
    report["code_sha"] = code_sha()
    report["split_sha"] = split_sha()
    report["outcome_law_sha"] = outcome_law_sha()
    report["parent_trial"] = PARENT_TRIAL
    report["mutant"] = mutant
    report["asset_days"] = dict(days)
    report["cells"] = dict(plane.cells)
    report["cells_without_context"] = int(sum(
        1 for ctx in plane.ctxs if ctx is None))
    report["context_counts"] = dict(store.counts)

    if args.stage in ("stage-o", "all"):
        block = stage_o(plane, Path(args.root))
        report["stage_o"] = block
        print_conversion(block["conversion_check"])
        print_o1(block["o1"])
        print_o2(block["o2"])
        print_o3(block["o3"])
    if args.stage in ("stage-a", "stage-b", "log", "all"):
        if "stage_a" not in report or args.stage in ("stage-a", "all"):
            report["stage_a"] = stage_a(plane)
            print_stage_a(report["stage_a"], args.top)
    if args.stage in ("stage-b", "all"):
        report["stage_b"] = stage_b(plane, explore_days, report["stage_a"])
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
          f"cells={len(records)} spec_sha={SPEC_SHA[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
