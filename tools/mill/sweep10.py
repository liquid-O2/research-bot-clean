#!/usr/bin/env python3
"""Sweep 10 of the side-resolution mill: the range-exhaustion wall immunity screen.

THE MECHANISM.  A wall is an exact 900 USD extension beyond the entry mid.  The
oracle never walls (S0: MDD 192 over 1,732 trades; I4: first-terminal oracle,
zero walls) because it never enters where 900 more dollars of extension are
still available.  A CAUSAL entry can be bought the same immunity from a ruler
the program already owns but has never wired into an entry decision: the day's
REMAINING RANGE BUDGET.

  remaining_budget = max(0, predicted_session_range - realized_range_so_far)

Both terms are causal.  ``predicted_session_range`` comes from the daily
catboost ``forecast_variance`` the vol service already writes walk-forward
out-of-fold, rescaled to dollars by a scalar fitted only on strictly-prior
EXPLORE days.  ``realized_range_so_far`` is the running high-low of this
session's own bar mids, which every bar already knows.

The payoff is NOT capped by the remaining budget.  What pays a fade is the
reversal back across the day's range, which is large exactly when the range is
large; what kills it is the extension past the extreme, which is what the
budget bounds.  So an exhausted-range extreme is an asymmetric moment: capped
downside, open upside.  That asymmetry is the whole hypothesis.

STAGE D (oracle-blind, decides everything).  Take sweep 8's CONTROL line - the
any-candidate entry law, reproduced here cents-exact from the imported sweep-8
machinery as the gate - and bucket its entries by the remaining budget at the
entry bar.  If small remaining budget does not predict low wall rate, the
mechanism is dead no matter what any policy earns.

STAGE E (the admission screen).  A new opportunity law, pre-registered: at any
bar whose session running extreme (either side) is at most 5 bars old and whose
remaining budget is at most theta*900, fade that extreme at the first same-side
CLEAR candidate within 0.15 ATR of it (sweep 8's depth law), 1800 s of phase
remaining, one entry per cell, first admission wins, an opposite new extreme
cancels a pending entry.  theta in {0.5, 0.75, 1.0}, three values, no other
grid.  The marginal value of the budget is read against the SAME law with the
budget condition deleted, and against a phase-time-matched random control.

Nothing here reads a pack, a HOLD day, the teacher, 2021 or 2025.  Every number
comes from the mill caches and ``artifacts/cache/mill_context``.

The mutant ``QRE2_MILL_S10_MUTANT=budget_uses_today`` calibrates the dollar
scalar on a sample that includes the scoring day's own realized range, which is
the one same-day outcome the whole ruler must not see.
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
from typing import Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.entry_v2.confirmation_types import NANOS_PER_SECOND

from tools.mill import context as CTX
from tools.mill import mill as M
from tools.mill import sweep1 as S1
from tools.mill import sweep2 as S2
from tools.mill import sweep3 as S3
from tools.mill import sweep4 as S4
from tools.mill import sweep7a as S7A
from tools.mill import sweep8 as S8

SPEC = """QRE2MILLSWEEP10
D  sweep-8 CONTROL entries bucketed by remaining_budget at the entry bar:
   wall rate, postX_1800, cash/trade by bucket {<0.5,0.5-0.75,0.75-1.0,1.0-1.5,
   >1.5} x 900 USD, per asset, Wilson CIs.  The mechanism question.
E  admission law: session running extreme (either side) set within the last 5
   bars AND remaining_budget <= theta*900, theta in {0.5,0.75,1.0}; enter the
   fade at the first same-side CLEAR candidate within 0.15 ATR of the extreme;
   >= 1800 s remaining; one entry per cell; first admission wins; opposite new
   extreme cancels.  Controls: NOBUDGET (same law, budget condition deleted)
   and a phase-time-matched random control.
F  best theta per deciding asset on wall rate then coverage (no cash in the
   selection): engine replay, 2% adversarial stress, block-permutation null
   (200 draws, seed 20260827, max-stat over the priced pool).
k  predicted_range = k(asset, day) * sqrt(forecast_variance_today), where
   k = median over strictly-prior EXPLORE days with a forecast of
   realized_session_range_usd / sqrt(forecast_variance), >= 20 prior days.
"""

SCHEMA = "QRE2MILLSWEEP10"
ASSETS = S1.ASSETS
DECIDING_ASSETS = S7A.DECIDING_ASSETS          # ("NKD", "SI"); HG is reported
BAR_SECONDS = S1.BAR_SECONDS
SEED = S1.SEED                                 # 20260827
NULL_DRAWS = S1.NULL_DRAWS                     # 200
DAY_RUNG_USD = S1.DAY_RUNG_USD

WALL_BUDGET_USD = 900.0                        # the wall the budget is measured in
THETAS = (0.5, 0.75, 1.0)                      # pre-registered, no other grid
FRESH_BARS = 5                                 # the extreme must be <= 5 bars old
DEPTH_ATR = S8.DEPTH_ATR                       # 0.15, sweep 8's depth law
DEPTH_WINDOW_BARS = S8.DEPTH_WINDOW_BARS       # 15
REMAIN_MIN_S = S8.REMAIN_MIN_S                 # 1800
MIN_CALIB_DAYS = 20                            # calibration floor
BUCKET_EDGES = (0.5, 0.75, 1.0, 1.5)           # in multiples of 900 USD
BUCKET_NAMES = ("<0.5", "0.5-0.75", "0.75-1.0", "1.0-1.5", ">1.5")

RANDOM_DRAWS = S8.RANDOM_DRAWS                 # 50
PHASE_MATCH_WINDOW_S = S8.PHASE_MATCH_WINDOW_S # 300
STRESS_RATE = S3.STRESS_RATE                   # 0.02

# The pre-registered decision bounds.
STAGE_D_WALL_CEILING = 0.10                    # the <0.75x900 buckets must clear this
FREEZE_MDD_CEILING = 1000.0
NULL_CEILING = 0.05
INTERESTING_WALL_CEILING = 0.05
INTERESTING_COVERAGE_FLOOR = 0.25
INTERESTING_MDD_DAY_CEILING = 2000.0

LINE_NOBUDGET = "NOBUDGET"
MISS_NO_ADMISSION = "no_admission"
MISS_NO_BUDGET_DAY = "no_budget"
MISS_NO_CANDIDATE = S8.MISS_NO_CANDIDATE
MISS_NO_DEPTH = S8.MISS_NO_DEPTH
MISS_CANCELLED = S8.MISS_CANCELLED
MISS_BRANCHES = (MISS_NO_ADMISSION, MISS_NO_BUDGET_DAY, MISS_NO_CANDIDATE,
                 MISS_NO_DEPTH, MISS_CANCELLED)

OUT_PATH = ROOT / ".audit/mill-sweep10.json"
LOG_PATH = S1.LOG_PATH
SWEEP8_PATH = S8.OUT_PATH

MUTANT_ENV = "QRE2_MILL_S10_MUTANT"
MUTANT_TODAY = "budget_uses_today"
MUTANTS = (MUTANT_TODAY,)

FAMILY = "F7-RANGEBUDGET"
PARENT_TRIAL = "sweep8b-004"
SELECTION_RULE = "wall_rate>coverage (no cash in selection)"


class SweepRefusal(RuntimeError):
    """Sweep 10 was asked for something its inputs cannot support."""


SPEC_SHA = S1._sha_text(SPEC)


def code_sha() -> str:
    return S1._sha_file(Path(__file__))


def _mutant() -> str:
    name = os.environ.get(MUTANT_ENV, "")
    if name and name not in MUTANTS:
        raise SweepRefusal(f"unknown sweep 10 mutant: {name}")
    return name


# --------------------------------------------------------------------------
# The dollar ruler: predicted range, realized range, remaining budget.
# --------------------------------------------------------------------------

def mid2_to_usd(asset: str) -> float:
    """USD of price move per mid2 unit - sweep 3's frozen conversion, inverted."""

    return 1.0 / S7A.usd_to_mid2(asset)


def calibrate_k(prior_ratios: Sequence[float], today_ratio: float | None
                ) -> float | None:
    """Median range-per-root-variance over strictly-prior days.

    ``QRE2_MILL_S10_MUTANT=budget_uses_today`` appends the scoring day's own
    realized range to the sample.  That single append is the whole causal law
    of this sweep: the day's realized session range is a same-day outcome, and
    a ruler calibrated on it has already seen how far the day went.  This is
    the module's only branch on the mutant.
    """

    sample = [float(v) for v in prior_ratios if np.isfinite(v) and v > 0.0]
    if _mutant() == MUTANT_TODAY and today_ratio is not None:
        if np.isfinite(today_ratio) and today_ratio > 0.0:
            sample.append(float(today_ratio))
    if len(sample) < MIN_CALIB_DAYS:
        return None
    return float(np.median(np.asarray(sample, np.float64)))


@dataclass(frozen=True, slots=True)
class DayBudget:
    """One asset-day's dollar ruler."""

    asset: str
    d8: int
    k: float
    root_var: float
    predicted_range_usd: float
    prior_days: int


def _root_variance(forecast: Mapping[str, str] | None) -> float | None:
    if forecast is None:
        return None
    raw = str(forecast.get("forecast_variance", "")).strip()
    if not raw:
        return None
    value = float(raw)
    return math.sqrt(value) if value > 0.0 else None


def build_budgets(records: Sequence[S1.CellRec], assets: Sequence[str]
                  ) -> tuple[dict[tuple[str, int], DayBudget], dict[str, dict[str, int]]]:
    """The walk-forward dollar ruler for every EXPLORE asset-day in ``records``.

    The lookback is set wide enough to reach every prior levels row the store
    holds, so the calibration sample is "every strictly-prior EXPLORE day with
    a forecast" rather than a truncated window.  ``context_for`` is still the
    only reader, so the strictly-prior guard on levels is the one in
    ``context.py`` and not a copy of it here.
    """

    wanted: dict[str, list[int]] = {}
    for rec in records:
        if rec.asset in assets:
            days = wanted.setdefault(rec.asset, [])
            if not days or days[-1] != int(rec.d8):
                days.append(int(rec.d8))
    store = CTX.ContextStore(lookback=4096)
    explore = {asset: set(S1._explore_days([asset])[asset]) for asset in assets}
    out: dict[tuple[str, int], DayBudget] = {}
    skips: dict[str, dict[str, int]] = {
        asset: {"no_forecast": 0, "few_prior_days": 0} for asset in assets}
    root_cache: dict[int, float | None] = {}

    def root_for(asset: str, day: int) -> float | None:
        if day not in root_cache:
            # forecast.tsv is portfolio-wide and keys on the day alone, so one
            # cache serves every asset.
            root_cache[day] = _root_variance(
                store.context_for(asset, day).get("forecast"))
        return root_cache[day]

    for asset in sorted(wanted):
        factor = mid2_to_usd(asset)
        for day in sorted(set(wanted[asset])):
            payload = store.context_for(asset, day)
            root_today = root_for(asset, day)
            if root_today is None:
                skips[asset]["no_forecast"] += 1
                continue
            ratios: list[float] = []
            today_ratio: float | None = None
            for row in payload.get("levels_lookback") or ():
                prior_day = int(row["d8"])
                if prior_day not in explore[asset]:
                    continue
                root_prior = root_for(asset, prior_day)
                if root_prior is None:
                    continue
                span = float(row["session_range_mid2"]) * factor
                if span > 0.0:
                    ratios.append(span / root_prior)
            if _mutant() == MUTANT_TODAY:
                own = store._levels.get(asset, ((), ()))
                days_all, rows_all = own
                position = int(np.searchsorted(np.asarray(days_all, np.int64), day))
                if position < len(days_all) and int(days_all[position]) == day:
                    today_ratio = (float(rows_all[position]["session_range_mid2"])
                                   * factor / root_today)
            k = calibrate_k(ratios, today_ratio)
            if k is None:
                skips[asset]["few_prior_days"] += 1
                continue
            out[(asset, day)] = DayBudget(
                asset, day, float(k), float(root_today),
                float(k * root_today), len(ratios))
    return out, skips


@dataclass(slots=True)
class CellBudget:
    """Per-bar remaining budget for one cell, in USD and in 900-USD units."""

    predicted_range_usd: float
    realized_usd: np.ndarray
    remaining_usd: np.ndarray
    remaining_x900: np.ndarray


def session_running_range(records: Sequence[S1.CellRec]
                          ) -> dict[int, np.ndarray]:
    """Running session high-low in USD at every bar of every cell.

    The session runs across phases, so the running extremes are accumulated
    over every bar of the asset-day at or before the bar's own close.  Only the
    day's own bar mids are read, and only up to the bar itself, so the series
    is causal at every point.
    """

    by_day: dict[tuple[str, int], list[int]] = {}
    for position, rec in enumerate(records):
        by_day.setdefault((rec.asset, int(rec.d8)), []).append(position)
    out: dict[int, np.ndarray] = {}
    for (asset, _day), positions in by_day.items():
        factor = mid2_to_usd(asset)
        stamps = np.concatenate([np.asarray(records[p].lat, np.int64)
                                 for p in positions])
        values = np.concatenate([np.asarray(records[p].mid, np.float64)
                                 for p in positions])
        order = np.argsort(stamps, kind="stable")
        stamps, values = stamps[order], values[order]
        highs = np.maximum.accumulate(values)
        lows = np.minimum.accumulate(values)
        for position in positions:
            lat = np.asarray(records[position].lat, np.int64)
            # ``right`` includes the bar's own close, whose mid the bar already
            # holds; nothing later than the bar is ever in the slice.
            slot = np.searchsorted(stamps, lat, side="right") - 1
            slot = np.maximum(slot, 0)
            out[position] = ((highs[slot] - lows[slot]) * factor).astype(np.float64)
    return out


def build_cell_budgets(cells: Sequence[S8.Cell8], records: Sequence[S1.CellRec],
                       budgets: Mapping[tuple[str, int], DayBudget]
                       ) -> tuple[dict[int, CellBudget], dict[str, int]]:
    """Attach the ruler to every cell whose day carries one."""

    ranges = session_running_range(records)
    out: dict[int, CellBudget] = {}
    dropped: dict[str, int] = {asset: 0 for asset in ASSETS}
    for cell in cells:
        ruler = budgets.get((cell.asset, cell.d8))
        if ruler is None:
            dropped[cell.asset] = dropped.get(cell.asset, 0) + 1
            continue
        realized = ranges[cell.position][:cell.n].astype(np.float64)
        remaining = np.maximum(0.0, ruler.predicted_range_usd - realized)
        out[cell.position] = CellBudget(
            float(ruler.predicted_range_usd), realized, remaining,
            remaining / WALL_BUDGET_USD)
    return out, dropped


def bucket_of(remaining_x900: float) -> str:
    """The pre-registered remaining-budget bucket, in multiples of 900 USD."""

    value = float(remaining_x900)
    if value < BUCKET_EDGES[0]:
        return BUCKET_NAMES[0]
    if value < BUCKET_EDGES[1]:
        return BUCKET_NAMES[1]
    if value < BUCKET_EDGES[2]:
        return BUCKET_NAMES[2]
    if value < BUCKET_EDGES[3]:
        return BUCKET_NAMES[3]
    return BUCKET_NAMES[4]


# --------------------------------------------------------------------------
# The sweep-8 reproduction gate.
# --------------------------------------------------------------------------

def _cents(value: object) -> int:
    return int(round(float(value) * 100.0))


def reproduction_gate(cash: Mapping[str, Mapping[str, object]]
                      ) -> dict[str, object]:
    """Assert this run's CONTROL line matches the stored sweep-8 one to the cent.

    Stage D reads sweep 8's opportunity set, so the import has to be shown to
    have reproduced it before anything is read off it.  Cash is compared in
    cents and the counts exactly; a mismatch refuses the whole run.
    """

    stored = json.loads(SWEEP8_PATH.read_text())["stage_b"]["lines"]["CONTROL"]
    rows: dict[str, object] = {}
    ok = True
    for asset in ASSETS:
        mine, theirs = cash[asset], stored[asset]
        same = (int(mine["trades"]) == int(theirs["trades"])
                and int(mine["walls"]) == int(theirs["walls"])
                and _cents(mine["total_usd"]) == _cents(theirs["total_usd"])
                and _cents(mine["mdd_day_usd"]) == _cents(theirs["mdd_day_usd"]))
        ok = ok and same
        rows[asset] = {
            "trades": [int(mine["trades"]), int(theirs["trades"])],
            "walls": [int(mine["walls"]), int(theirs["walls"])],
            "total_usd_cents": [_cents(mine["total_usd"]), _cents(theirs["total_usd"])],
            "mdd_day_usd_cents": [_cents(mine["mdd_day_usd"]),
                                  _cents(theirs["mdd_day_usd"])],
            "match": bool(same)}
    return {"match": bool(ok), "by_asset": rows, "source": str(SWEEP8_PATH)}


# --------------------------------------------------------------------------
# STAGE D - the diagnostic.
# --------------------------------------------------------------------------

def _rate(hits: int, total: int) -> dict[str, object]:
    low, high = S1.wilson(int(hits), int(total))
    return {"hits": int(hits), "n": int(total),
            "rate": (hits / total) if total else None,
            "ci_low": low if total else None, "ci_high": high if total else None}


@dataclass(frozen=True, slots=True)
class Priced:
    """One entry with its budget context and its frozen-law outcome."""

    asset: str
    bucket: str
    remaining_usd: float
    remaining_x900: float
    wall: bool
    cert_usd: float
    postx1800: bool
    postx_full: bool


def priced_rows(shots: Sequence[S8.Shot8], cells: Mapping[int, S8.Cell8],
                cell_budgets: Mapping[int, CellBudget],
                records: Sequence[S1.CellRec]) -> tuple[list[Priced], int]:
    """Budget-annotated rows for every shot whose day carries a ruler."""

    out: list[Priced] = []
    skipped = 0
    for shot in shots:
        budget = cell_budgets.get(shot.cell)
        if budget is None:
            skipped += 1
            continue
        entry = S1.make_entry(shot.cell, records[shot.cell], shot.entry_bar,
                              shot.side)
        if entry is None:
            skipped += 1
            continue
        remaining = float(budget.remaining_usd[shot.entry_bar])
        out.append(Priced(
            shot.asset, bucket_of(budget.remaining_x900[shot.entry_bar]),
            remaining, float(budget.remaining_x900[shot.entry_bar]),
            bool(entry.wall), float(entry.cert_usd),
            bool(shot.postx1800_entry), bool(shot.entry_full_window)))
    return out, skipped


def bucket_table(rows: Sequence[Priced]) -> dict[str, object]:
    """Wall rate, postX_1800 and cash per trade by remaining-budget bucket."""

    out: dict[str, object] = {}
    for name in BUCKET_NAMES:
        picked = [row for row in rows if row.bucket == name]
        full = [row for row in picked if row.postx_full]
        certs = np.asarray([row.cert_usd for row in picked], np.float64)
        out[name] = {
            "n": len(picked),
            "wall": _rate(sum(1 for row in picked if row.wall), len(picked)),
            "postx1800": _rate(sum(1 for row in full if row.postx1800), len(full)),
            "usd_per_trade": float(certs.mean()) if len(certs) else None,
            "remaining_median_usd": (
                float(np.median([row.remaining_usd for row in picked]))
                if picked else None),
        }
    return out


def _monotone(rates: Sequence[float | None]) -> bool:
    """Non-decreasing wall rate across the populated buckets, low budget first."""

    seen = [value for value in rates if value is not None]
    return all(seen[i] <= seen[i + 1] + 1e-12 for i in range(len(seen) - 1))


def stage_d(rows: Sequence[Priced], skipped: int) -> dict[str, object]:
    by_asset: dict[str, object] = {}
    verdicts: dict[str, object] = {}
    for asset in ASSETS:
        picked = [row for row in rows if row.asset == asset]
        table = bucket_table(picked)
        rates = [table[name]["wall"]["rate"] for name in BUCKET_NAMES]
        low = [row for row in picked if row.remaining_x900 < BUCKET_EDGES[1]]
        low_wall = _rate(sum(1 for row in low if row.wall), len(low))
        by_asset[asset] = {"entries": len(picked), "buckets": table,
                           "low_budget": low_wall,
                           "monotone": bool(_monotone(rates))}
        verdicts[asset] = {
            "monotone": bool(_monotone(rates)),
            "low_wall_clears": bool(low_wall["rate"] is not None
                                    and low_wall["rate"] <= STAGE_D_WALL_CEILING),
            "n_low": low_wall["n"]}
    confirmed = all(verdicts[asset]["monotone"] and verdicts[asset]["low_wall_clears"]
                    for asset in DECIDING_ASSETS)
    return {"pooled": bucket_table(rows), "by_asset": by_asset,
            "per_asset_verdict": verdicts, "entries_without_ruler": int(skipped),
            "wall_ceiling": STAGE_D_WALL_CEILING,
            "mechanism_confirmed": bool(confirmed)}


# --------------------------------------------------------------------------
# STAGE E - the admission screen.
# --------------------------------------------------------------------------

def fresh_extreme_bars(cell: S8.Cell8, side: int) -> np.ndarray:
    """Bars whose same-side running extreme was set within the last 5 bars.

    ``new_ext`` marks the bar that SET the extreme, so age 0 is the setting bar
    itself and the window admits ages 0..4.  Before the side has any extreme
    the age is undefined and no bar is fresh.
    """

    _prior, new_ext, _armed = S7A.side_arrays(cell.geo, side)
    order = np.arange(cell.n, dtype=np.int64)
    last = np.maximum.accumulate(np.where(np.asarray(new_ext, bool), order, -1))
    age = order - last
    return (last >= 0) & (age < FRESH_BARS)


def admissions(cell: S8.Cell8, budget: CellBudget | None, theta: float | None
               ) -> list[tuple[int, int]]:
    """``(bar, side)`` admissions in bar order, both sides, first wins.

    ``theta is None`` deletes the budget condition, which is the NOBUDGET
    control: the same fresh-extreme fades, chosen by nothing but freshness.
    """

    rows: list[tuple[int, int]] = []
    for side in (1, -1):
        fresh = fresh_extreme_bars(cell, side)
        ok = np.asarray(cell.rec.bar_ok, bool)[:cell.n]
        remaining_s = cell.sides[side].remaining_s
        admit = fresh & ok & (remaining_s >= REMAIN_MIN_S)
        if theta is not None:
            if budget is None:
                continue
            admit = admit & (budget.remaining_x900 <= float(theta))
        for bar in np.flatnonzero(admit):
            if int(bar) >= 1:
                rows.append((int(bar), side))
    rows.sort()
    return rows


def resolve_cell(cell: S8.Cell8, budget: CellBudget | None, theta: float | None
                 ) -> tuple[S8.Shot8 | None, str]:
    """First admission that survives the depth law and the cancel clause."""

    rows = admissions(cell, budget, theta)
    if not rows:
        return None, (MISS_NO_BUDGET_DAY if theta is not None and budget is None
                      else MISS_NO_ADMISSION)
    miss = MISS_NO_ADMISSION
    for bar, side in rows:
        entry_bar, depth, branch = S8.entry_after(cell, side, bar, True)
        if entry_bar < 0:
            miss = branch
            continue
        _oprior, opp_new, _oarmed = S7A.side_arrays(cell.geo, -side)
        if bool(np.any(opp_new[bar + 1: entry_bar + 1])):
            # The opposite side printed a new extreme before the entry landed:
            # the pending entry is cancelled and the cell re-arms.
            miss = MISS_CANCELLED
            continue
        value = (float("nan") if budget is None
                 else float(budget.remaining_x900[bar]))
        return S8._finish(cell, side, bar, entry_bar, value, depth), ""
    return None, miss


@dataclass(slots=True)
class LineRun:
    """One admission law's shots and misses over every cell."""

    shots: list[S8.Shot8] = field(default_factory=list)
    misses: dict[str, str] = field(default_factory=dict)
    cells: dict[str, int] = field(default_factory=dict)


def run_line(cells: Sequence[S8.Cell8], cell_budgets: Mapping[int, CellBudget],
             theta: float | None) -> LineRun:
    """One admission law over every cell whose day carries a ruler.

    NOBUDGET is held to the same cell set even though it never reads the
    budget: the control's whole job is to price the budget CONDITION, so it has
    to face the same denominator and the same days.
    """

    run = LineRun()
    for cell in cells:
        budget = cell_budgets.get(cell.position)
        if budget is None:
            continue
        tag = f"{cell.asset}/{cell.d8}/{cell.phase}"
        run.cells[cell.asset] = run.cells.get(cell.asset, 0) + 1
        shot, miss = resolve_cell(cell, budget, theta)
        if shot is None:
            run.misses[tag] = miss
        else:
            run.shots.append(shot)
    return run


def line_table(run: LineRun, records: Sequence[S1.CellRec],
               days: Mapping[str, int]) -> dict[str, object]:
    """Per-asset coverage, wall rate, postX_1800, soft hit, cash and MDD."""

    entries = S8.entries_of(run.shots, records)
    cash = S1.cash_line(entries, days, run.cells)
    out: dict[str, object] = {"by_asset": {}, "cells": dict(run.cells)}
    for asset in ASSETS:
        shots = [row for row in run.shots if row.asset == asset]
        rows = [row for row in entries if row.asset == asset]
        graded = [row for row in shots if row.side_ok is not None]
        line = dict(cash[asset])
        line.update({
            "cells": int(run.cells.get(asset, 0)),
            "wall": _rate(sum(1 for row in rows if row.wall), len(rows)),
            "postx1800": S8.horizon_table(shots)["postx1800_entry"],
            "soft_hit": _rate(sum(1 for row in shots if row.soft_hit), len(shots)),
            "side_agree": _rate(sum(1 for row in graded if row.side_ok),
                                len(graded)),
            "delay_median_s": S8._q([row.delay_s for row in shots], 50),
            "delay_p90_s": S8._q([row.delay_s for row in shots], 90),
            "depth_median_atr": S8._q([row.depth for row in shots], 50),
            "rung_usd": DAY_RUNG_USD[asset],
        })
        out["by_asset"][asset] = line
    branches: dict[str, dict[str, int]] = {
        asset: {name: 0 for name in MISS_BRANCHES} for asset in ASSETS}
    for tag, miss in run.misses.items():
        asset = tag.split("/")[0]
        branches[asset][miss] = branches[asset].get(miss, 0) + 1
    out["misses"] = branches
    out["by_phase"] = {}
    for phase in ("0", "1", "2"):
        shots = [row for row in run.shots if row.phase == phase]
        rows = [S1.make_entry(row.cell, records[row.cell], row.entry_bar, row.side)
                for row in shots]
        rows = [row for row in rows if row is not None]
        out["by_phase"][phase] = {
            "entries": len(shots),
            "wall": _rate(sum(1 for row in rows if row.wall), len(rows)),
            "usd_per_trade": (float(np.mean([row.cert_usd for row in rows]))
                              if rows else None)}
    return out


def phase_matched_control(cells: Sequence[S8.Cell8],
                          cell_budgets: Mapping[int, CellBudget],
                          fires: Sequence[S8.Shot8],
                          draws: int = RANDOM_DRAWS) -> dict[str, object]:
    """Random fresh-extreme fades matched to the real ones on phase-elapsed time.

    The pool is the NOBUDGET admission set, so the control differs from the
    screen in the budget condition and in nothing else; matching within 300 s of
    phase-elapsed removes the clock the budget correlates with.
    """

    pool: dict[int, list[tuple[int, int]]] = {}
    for cell in cells:
        rows = admissions(cell, cell_budgets.get(cell.position), None)
        if rows:
            pool[cell.position] = rows
    by_position = {cell.position: cell for cell in cells}
    targets: dict[str, list[int]] = {}
    for shot in fires:
        targets.setdefault(shot.asset, []).append(int(shot.fire_phase_s))
    rng = np.random.default_rng(SEED)
    per_draw: list[list[S8.Shot8]] = []
    unmatched = 0
    for _draw in range(draws):
        picked: list[S8.Shot8] = []
        for position in sorted(pool):
            cell = by_position[position]
            wanted = targets.get(cell.asset)
            if not wanted:
                continue
            aim = int(wanted[int(rng.integers(len(wanted)))])
            open_ns = int(cell.rec.phase_open_ts_ns)
            near = [row for row in pool[position]
                    if abs(int((int(cell.rec.lat[row[0]]) - open_ns)
                               // NANOS_PER_SECOND) - aim) <= PHASE_MATCH_WINDOW_S]
            if not near:
                unmatched += 1
                continue
            bar, side = near[int(rng.integers(len(near)))]
            entry_bar, depth, _branch = S8.entry_after(cell, side, bar, True)
            if entry_bar < 0:
                continue
            picked.append(S8._finish(cell, side, bar, entry_bar, float("nan"), depth))
        per_draw.append(picked)
    out: dict[str, object] = {"draws": draws, "seed": SEED,
                              "match_window_s": PHASE_MATCH_WINDOW_S,
                              "cells_unmatched": int(unmatched), "by_asset": {}}
    for asset in ASSETS:
        tables = [S8.horizon_table([row for row in rows if row.asset == asset])
                  for rows in per_draw]
        hits = sum(table["postx1800_entry"]["hits"] for table in tables)
        total = sum(table["postx1800_entry"]["n"] for table in tables)
        out["by_asset"][asset] = {
            "entries_mean": float(np.mean([table["n"] for table in tables]))
            if tables else 0.0,
            "postx1800_entry": _rate(hits, total)}
    return out


def random_wall_control(cells: Sequence[S8.Cell8],
                        cell_budgets: Mapping[int, CellBudget],
                        records: Sequence[S1.CellRec],
                        draws: int = RANDOM_DRAWS) -> dict[str, object]:
    """Wall rate of random NOBUDGET admissions - the budget-free wall baseline."""

    pool: dict[int, list[tuple[int, int]]] = {}
    for cell in cells:
        rows = admissions(cell, cell_budgets.get(cell.position), None)
        if rows:
            pool[cell.position] = rows
    by_position = {cell.position: cell for cell in cells}
    rng = np.random.default_rng(SEED)
    hits = {asset: 0 for asset in ASSETS}
    total = {asset: 0 for asset in ASSETS}
    for _draw in range(draws):
        for position in sorted(pool):
            cell = by_position[position]
            bar, side = pool[position][int(rng.integers(len(pool[position])))]
            entry_bar, _depth, _branch = S8.entry_after(cell, side, bar, True)
            if entry_bar < 0:
                continue
            entry = S1.make_entry(position, records[position], entry_bar, side)
            if entry is None:
                continue
            total[cell.asset] += 1
            hits[cell.asset] += int(entry.wall)
    return {"draws": draws, "seed": SEED,
            "by_asset": {asset: _rate(hits[asset], total[asset])
                         for asset in ASSETS}}


# --------------------------------------------------------------------------
# STAGE F - pricing the selected thetas.
# --------------------------------------------------------------------------

def select_theta(stage_e: Mapping[str, object], asset: str) -> str | None:
    """Lowest wall rate, then highest coverage.  Cash never enters."""

    best: tuple[float, float, str] | None = None
    for name in sorted(stage_e):
        line = stage_e[name]["by_asset"][asset]
        if not int(line["trades"]):
            continue
        rate = float(line["wall"]["rate"])
        coverage = float(line["coverage"])
        key = (rate, -coverage, name)
        if best is None or key < best:
            best = key
    return None if best is None else best[2]


def price_lines(runs: Mapping[str, LineRun], records: Sequence[S1.CellRec],
                days: Mapping[str, int], explore_days: Mapping[str, list[int]]
                ) -> dict[str, object]:
    priced: dict[str, list[S1.Entry]] = {}
    out: dict[str, object] = {"replays": {}, "stress": {}, "lines": list(runs)}
    for name, run in runs.items():
        entries = S8.entries_of(run.shots, records)
        for asset in ASSETS:
            priced[f"{asset}/{name}"] = [row for row in entries
                                         if row.asset == asset]
        out["replays"][name] = S1.replay_line(entries, records,
                                              f"sweep10-{name.lower()}")
        out["stress"][name] = {
            asset: S3.stress_line(entries, records, days, run.cells, asset,
                                  STRESS_RATE)
            for asset in ASSETS}
    out["null"] = S1.block_null(priced, explore_days, NULL_DRAWS, SEED)
    return out


def decide(report: Mapping[str, object]) -> dict[str, object]:
    """The pre-registered decision table, honest per asset."""

    stage_d_block = report["stage_d"]
    stage_e = report["stage_e"]["lines"]
    chosen = report["stage_f"]["chosen"]
    stage_f = report["stage_f"]
    out: dict[str, object] = {"by_asset": {}}
    for asset in ASSETS:
        name = chosen.get(asset)
        bounds: list[str] = []
        verdict = "KILL"
        detail: dict[str, object] = {"theta": name}
        d_row = stage_d_block["per_asset_verdict"][asset]
        if not d_row["monotone"]:
            bounds.append("stage-D wall rate not monotone in budget")
        if not d_row["low_wall_clears"]:
            bounds.append(f"stage-D <0.75x900 wall rate > {STAGE_D_WALL_CEILING}")
        if name is None:
            bounds.append("no theta entered a cell")
        else:
            line = stage_e[name]["by_asset"][asset]
            wall = float(line["wall"]["rate"])
            coverage = float(line["coverage"])
            per_day = float(line["usd_per_asset_day"])
            mdd_day = float(line["mdd_day_usd"])
            mdd_trade = float(line["mdd_trade_usd"])
            # Only the deciding assets' chosen thetas are priced, so HG can
            # reach the interesting bar but never the freeze bar.
            priced = name in stage_f["stress"]
            stress = stage_f["stress"].get(name, {}).get(asset, {})
            null_row = stage_f["null"].get("by_line", {}).get(f"{asset}/{name}", {})
            null_p = null_row.get("p_max_adjusted")
            detail.update({
                "wall_rate": wall, "coverage": coverage,
                "usd_per_asset_day": per_day, "rung_usd": DAY_RUNG_USD[asset],
                "mdd_day_usd": mdd_day, "mdd_trade_usd": mdd_trade,
                "priced": bool(priced),
                "stress_usd_per_asset_day": stress.get("usd_per_asset_day"),
                "null_p": null_p})
            freeze = [
                ("rung", per_day >= DAY_RUNG_USD[asset]),
                ("mdd_day", mdd_day < FREEZE_MDD_CEILING),
                ("mdd_trade", mdd_trade < FREEZE_MDD_CEILING),
                ("stress_positive",
                 float(stress.get("usd_per_asset_day") or 0.0) > 0.0),
                ("null", null_p is not None and float(null_p) <= NULL_CEILING)]
            failed = [key for key, ok in freeze if not ok]
            interesting = [
                (wall <= INTERESTING_WALL_CEILING,
                 f"wall {wall:.3f} > {INTERESTING_WALL_CEILING}"),
                (coverage >= INTERESTING_COVERAGE_FLOOR,
                 f"coverage {coverage:.3f} < {INTERESTING_COVERAGE_FLOOR}"),
                (per_day > 0.0, f"usd/day {per_day:.2f} <= 0"),
                (mdd_day < INTERESTING_MDD_DAY_CEILING,
                 f"MDD_day {mdd_day:.0f} >= {INTERESTING_MDD_DAY_CEILING}")]
            if priced and not failed:
                verdict = "FREEZE-CANDIDATE"
            elif all(ok for ok, _text in interesting):
                verdict = "INTERESTING"
            else:
                if not priced:
                    bounds.append("not priced (report-only asset): no freeze bar")
                else:
                    bounds.extend(f"freeze bar failed: {key}" for key in failed)
                bounds.extend(f"interesting bar failed: {text}"
                              for ok, text in interesting if not ok)
        detail["fired_bounds"] = bounds
        detail["verdict"] = verdict
        out["by_asset"][asset] = detail
    out["mechanism"] = ("MECHANISM-CONFIRMED" if stage_d_block["mechanism_confirmed"]
                        else "MECHANISM-DEAD")
    grades = [out["by_asset"][asset]["verdict"] for asset in DECIDING_ASSETS]
    for name in ("FREEZE-CANDIDATE", "INTERESTING"):
        if name in grades:
            out["overall"] = name
            break
    else:
        out["overall"] = "KILL"
    return out


# --------------------------------------------------------------------------
# The hypothesis log.
# --------------------------------------------------------------------------

def log_rows(report: Mapping[str, object]) -> list[dict[str, object]]:
    stamp = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    shared = {
        "registered_utc": stamp, "spec_sha": SPEC_SHA, "code_sha": code_sha(),
        "split_sha": S1.split_sha(), "outcome_law_sha": S1.outcome_law_sha(),
        "null_seed": SEED, "parent_trial": PARENT_TRIAL, "family": FAMILY,
        "selection_rule": SELECTION_RULE, "verdict": ""}
    stage_e = report["stage_e"]["lines"]
    stage_f = report["stage_f"]
    rows: list[dict[str, object]] = []
    for index, name in enumerate(sorted(stage_e), start=1):
        block = stage_e[name]["by_asset"]
        null_block = stage_f["null"].get("by_line", {})
        margins = [null_block.get(f"{asset}/{name}", {}).get("p_max_adjusted")
                   for asset in ASSETS]
        margins = [float(v) for v in margins if v is not None]
        theta = None if name == LINE_NOBUDGET else float(name.split("=")[-1])
        rows.append({
            **shared,
            "id": f"sweep10-{index:03d}",
            "rule": f"STAGE-E/{name}",
            "params": json.dumps([FRESH_BARS, theta, DEPTH_ATR, REMAIN_MIN_S]),
            "days": sum(int(report["asset_days"][asset]) for asset in ASSETS),
            "coverage": float(np.mean([block[asset]["coverage"]
                                       for asset in ASSETS])),
            "delay_med_s": block["NKD"]["delay_median_s"],
            "err_rate_hg": _one_minus(block["HG"]["side_agree"]["rate"]),
            "err_rate_nkd": _one_minus(block["NKD"]["side_agree"]["rate"]),
            "err_rate_si": _one_minus(block["SI"]["side_agree"]["rate"]),
            "walls_hg": int(block["HG"]["walls"]),
            "walls_nkd": int(block["NKD"]["walls"]),
            "walls_si": int(block["SI"]["walls"]),
            "hg_usd_day": block["HG"]["usd_per_asset_day"],
            "nkd_usd_day": block["NKD"]["usd_per_asset_day"],
            "si_usd_day": block["SI"]["usd_per_asset_day"],
            "mdd_hg": block["HG"]["mdd_day_usd"],
            "mdd_nkd": block["NKD"]["mdd_day_usd"],
            "mdd_si": block["SI"]["mdd_day_usd"],
            "replay_skips": stage_f["replays"].get(name, {}).get(
                "occupancy_or_cap_skips"),
            "null_margin": max(margins) if margins else None,
            "note": ("wall %.3f/%.3f/%.3f" % tuple(
                float(block[asset]["wall"]["rate"] or 0.0) for asset in ASSETS)),
        })
    index = len(rows) + 1
    d_block = report["stage_d"]["by_asset"]
    rows.append({
        **shared,
        "id": f"sweep10-{index:03d}",
        "rule": "STAGE-D/BUDGET-DIAGNOSTIC",
        "params": json.dumps(list(BUCKET_EDGES)),
        "days": sum(int(report["asset_days"][asset]) for asset in ASSETS),
        "coverage": None, "delay_med_s": None,
        "err_rate_hg": None, "err_rate_nkd": None, "err_rate_si": None,
        "walls_hg": d_block["HG"]["low_budget"]["hits"],
        "walls_nkd": d_block["NKD"]["low_budget"]["hits"],
        "walls_si": d_block["SI"]["low_budget"]["hits"],
        "hg_usd_day": d_block["HG"]["low_budget"]["rate"],
        "nkd_usd_day": d_block["NKD"]["low_budget"]["rate"],
        "si_usd_day": d_block["SI"]["low_budget"]["rate"],
        "mdd_hg": None, "mdd_nkd": None, "mdd_si": None,
        "replay_skips": None, "null_margin": None,
        "note": "low-budget wall rate in the usd_day columns; %s" % (
            report["decision"]["mechanism"]),
    })
    return rows


def _one_minus(value: object) -> float | None:
    return None if value is None else 1.0 - float(value)


# --------------------------------------------------------------------------
# Printing.
# --------------------------------------------------------------------------

def _n(value: object, width: int = 8, digits: int = 2) -> str:
    if value is None:
        return " " * (width - 1) + "-"
    return f"{float(value):{width}.{digits}f}"


def print_gate(block: Mapping[str, object]) -> None:
    print("\n== SWEEP-8 CONTROL REPRODUCTION GATE (cents-exact)")
    print("asset  trades(mine/stored)  walls  total_usd_cents  mdd_day_cents  match")
    for asset in ASSETS:
        row = block["by_asset"][asset]
        print(f"{asset:5s} {row['trades'][0]:9d}/{row['trades'][1]:<9d} "
              f"{row['walls'][0]:3d}/{row['walls'][1]:<3d} "
              f"{row['total_usd_cents'][0]:9d}/{row['total_usd_cents'][1]:<9d} "
              f"{row['mdd_day_usd_cents'][0]:9d}/{row['mdd_day_usd_cents'][1]:<9d} "
              f"  {'OK' if row['match'] else 'MISMATCH'}")
    print(f"gate: {'PASS' if block['match'] else 'FAIL'}")


def print_stage_d(block: Mapping[str, object]) -> None:
    print("\n== STAGE D  sweep-8 CONTROL entries by remaining budget (x900 USD)")
    print("asset bucket        n   wall  ci_low ci_high   postX  usd/trade  rem_med")
    for asset in ASSETS:
        row = block["by_asset"][asset]
        for name in BUCKET_NAMES:
            cell = row["buckets"][name]
            print(f"{asset:5s} {name:9s} {cell['n']:5d} "
                  f"{_n(cell['wall']['rate'], 6, 3)} {_n(cell['wall']['ci_low'], 7, 3)} "
                  f"{_n(cell['wall']['ci_high'], 7, 3)} "
                  f"{_n(cell['postx1800']['rate'], 7, 3)} "
                  f"{_n(cell['usd_per_trade'], 10, 2)} "
                  f"{_n(cell['remaining_median_usd'], 8, 0)}")
        low = row["low_budget"]
        print(f"{asset:5s} {'<0.75':9s} {low['n']:5d} {_n(low['rate'], 6, 3)} "
              f"{_n(low['ci_low'], 7, 3)} {_n(low['ci_high'], 7, 3)}"
              f"    <- the mechanism question  monotone={row['monotone']}")
    print(f"entries without a ruler: {block['entries_without_ruler']}")
    print(f"MECHANISM: {'CONFIRMED' if block['mechanism_confirmed'] else 'DEAD'} "
          f"(deciding assets {', '.join(DECIDING_ASSETS)}; "
          f"bar: monotone and <0.75x900 wall <= {STAGE_D_WALL_CEILING})")


def print_stage_e(block: Mapping[str, object]) -> None:
    print("\n== STAGE E  admission screen (per line, per asset)")
    print("line          asset cells entries  cover   wall  ci_hi   postX   soft "
          "  usd/day   rung  per_trade    win   mdd_day mdd_trade  delay_med")
    for name in sorted(block["lines"]):
        for asset in ASSETS:
            row = block["lines"][name]["by_asset"][asset]
            print(f"{name:13s} {asset:5s} {row['cells']:5d} {row['trades']:7d} "
                  f"{_n(row['coverage'], 6, 3)} {_n(row['wall']['rate'], 6, 3)} "
                  f"{_n(row['wall']['ci_high'], 6, 3)} "
                  f"{_n(row['postx1800']['rate'], 7, 3)} "
                  f"{_n(row['soft_hit']['rate'], 6, 3)} "
                  f"{_n(row['usd_per_asset_day'], 9, 2)} "
                  f"{row['rung_usd']:6.0f} {_n(row['usd_per_trade'], 10, 2)} "
                  f"{_n(row['win_rate'], 6, 3)} {_n(row['mdd_day_usd'], 9, 0)} "
                  f"{_n(row['mdd_trade_usd'], 9, 0)} "
                  f"{_n(row['delay_median_s'], 10, 0)}")
    print("\n-- miss branches per line (cells that entered nothing)")
    for name in sorted(block["lines"]):
        for asset in ASSETS:
            counts = block["lines"][name]["misses"][asset]
            print(f"{name:13s} {asset:5s} " + "  ".join(
                f"{key}={counts.get(key, 0)}" for key in MISS_BRANCHES))
    print("\n-- phase-time-matched random control (postX_1800 at entry)")
    control = block["phase_matched"]
    for asset in ASSETS:
        row = control["by_asset"][asset]
        print(f"{'PHASEMATCH':13s} {asset:5s} entries_mean={row['entries_mean']:8.1f} "
              f"postX={_n(row['postx1800_entry']['rate'], 6, 3)} "
              f"n={row['postx1800_entry']['n']}")
    print("\n-- random NOBUDGET admission wall baseline")
    for asset in ASSETS:
        row = block["random_wall"]["by_asset"][asset]
        print(f"{'RANDOMWALL':13s} {asset:5s} wall={_n(row['rate'], 6, 3)} "
              f"ci=[{_n(row['ci_low'], 5, 3)},{_n(row['ci_high'], 5, 3)}] n={row['n']}")


def print_stage_f(report: Mapping[str, object]) -> None:
    block = report["stage_f"]
    print("\n== STAGE F  chosen theta per deciding asset (wall rate, then coverage)")
    for asset in ASSETS:
        print(f"  {asset}: {block['chosen'].get(asset)}")
    print("\n-- engine replay (partial-day label)")
    for name in sorted(block["replays"]):
        row = block["replays"][name]
        if row.get("status") != "OK":
            print(f"{name:13s} {row.get('status')}")
            continue
        print(f"{name:13s} {row['label']}  trades={row['trades']} "
              f"usd/asset_day={_n(row['usd_per_asset_day'], 9, 2)} "
              f"mdd={_n(row['max_drawdown_usd'], 9, 0)} "
              f"skips={row['occupancy_or_cap_skips']}")
    print("\n-- 2% adversarial stress")
    for name in sorted(block["stress"]):
        for asset in ASSETS:
            row = block["stress"][name][asset]
            print(f"{name:13s} {asset:5s} flips={row['flips_applied']:3d} "
                  f"usd/day={_n(row['usd_per_asset_day'], 9, 2)} "
                  f"mdd_day={_n(row['mdd_day_usd'], 9, 0)}")
    print("\n-- block-permutation null (200 draws, seed 20260827, max-stat)")
    for key in sorted(block["null"].get("by_line", {})):
        row = block["null"]["by_line"][key]
        print(f"  {key:24s} " + "  ".join(
            f"{name}={_n(row.get(name), 8, 4)}"
            for name in sorted(row) if isinstance(row.get(name), (int, float))))


def print_decision(report: Mapping[str, object]) -> None:
    block = report["decision"]
    print("\n== DECISION TABLE (pre-registered)")
    print(f"mechanism: {block['mechanism']}")
    print("asset  theta          wall  cover   usd/day    rung   mdd_day mdd_trade "
          "  stress   null_p  verdict")
    for asset in ASSETS:
        row = block["by_asset"][asset]
        print(f"{asset:5s} {str(row.get('theta')):14s} "
              f"{_n(row.get('wall_rate'), 6, 3)} {_n(row.get('coverage'), 6, 3)} "
              f"{_n(row.get('usd_per_asset_day'), 9, 2)} "
              f"{_n(row.get('rung_usd'), 7, 0)} {_n(row.get('mdd_day_usd'), 9, 0)} "
              f"{_n(row.get('mdd_trade_usd'), 9, 0)} "
              f"{_n(row.get('stress_usd_per_asset_day'), 8, 2)} "
              f"{_n(row.get('null_p'), 8, 4)}  {row['verdict']}"
              + ("" if asset in DECIDING_ASSETS else "  (report only)"))
        for bound in row["fired_bounds"]:
            print(f"        fired: {bound}")
    print(f"overall (deciding assets only): {block['overall']}")


# --------------------------------------------------------------------------
# Selftest.
# --------------------------------------------------------------------------

def _check(name: str, ok: bool, detail: str = "") -> tuple[str, bool, str]:
    return (name, bool(ok), detail)


@dataclass(slots=True)
class _FakeGeo:
    new_low: np.ndarray
    new_high: np.ndarray


def _fixture_cell(mids: Sequence[float], new_low: Sequence[bool],
                  new_high: Sequence[bool], remaining_s: Sequence[float]
                  ) -> S8.Cell8:
    """A hand-built cell carrying only what the admission law reads."""

    bars = len(mids)
    rec = object.__new__(S1.CellRec)
    rec.asset, rec.d8, rec.phase = "NKD", 20220301, "1"
    rec.text = "NKD/20220301/1/0"
    rec.phase_open_ts_ns = 0
    rec.phase_close_ts_ns = bars * BAR_SECONDS * NANOS_PER_SECOND
    rec.lat = np.arange(bars, dtype=np.int64) * BAR_SECONDS * NANOS_PER_SECOND
    rec.mid = np.asarray(mids, np.int64)
    rec.bar_ok = np.ones(bars, bool)
    geo = S7A.Geo(
        atr_mid2=100.0, half=15.0,
        prior_low=np.asarray(mids, np.float64),
        prior_high=np.asarray(mids, np.float64),
        new_low=np.asarray(new_low, bool), new_high=np.asarray(new_high, bool),
        arm_low=np.zeros(bars, bool), arm_high=np.zeros(bars, bool),
        terminal_low=-1, terminal_high=-1, q_bars=5)
    sides = {}
    for side in (1, -1):
        sides[side] = S8.SideEvidence(
            side, np.zeros(bars), np.zeros(bars), np.zeros(bars),
            np.zeros(bars), np.zeros(bars), np.zeros(bars), [],
            np.ones(bars, bool), np.asarray(remaining_s, np.float64))
    cell = object.__new__(S8.Cell8)
    cell.position, cell.asset, cell.d8, cell.phase = 0, "NKD", 20220301, "1"
    cell.n, cell.rec, cell.geo = bars, rec, geo
    cell.star, cell.atr_mid2, cell.sides = None, 100.0, sides
    return cell


def _selftest_calibration() -> list[tuple[str, bool, str]]:
    """k is the median ratio over strictly-prior days; the mutant adds today.

    The fixture is built so the leak MOVES the answer: ten prior days at ratio
    100 and ten at 300 have median 200, and appending today's own ratio makes
    the sample odd-sized so its median jumps to 300.  A clean run must print
    200; the mutant must print 300, and that is the red case.
    """

    prior = [100.0] * 10 + [300.0] * 10           # median 200 over 20 prior days
    today = 5000.0                                # today's own realized ratio
    k = calibrate_k(prior, today)
    clean = 200.0                                 # (100 + 300) / 2, prior only
    # The expectation is the CLEAN one whatever the environment says, which is
    # what makes this the red case: the mutant returns 300 and fails here.
    ignored = calibrate_k(prior, None)
    short = calibrate_k([100.0] * (MIN_CALIB_DAYS - 1), None)
    return [
        _check("k ignores the scoring day's own realized range",
               k is not None and abs(k - clean) < 1e-9,
               f"k={k} want={clean} mutant={_mutant() or 'none'}"),
        _check("k over prior days alone is the prior median",
               ignored is not None and abs(ignored - clean) < 1e-9, f"k={ignored}"),
        _check("fewer than 20 prior days is skipped", short is None, f"{short}"),
    ]


def _selftest_budget_arithmetic() -> list[tuple[str, bool, str]]:
    """predicted = k*sqrt(var); remaining = max(0, predicted - realized)."""

    k, var = 120.0, 25.0                  # sqrt(var) = 5 -> predicted = 600 USD
    predicted = k * math.sqrt(var)
    realized = np.asarray([0.0, 200.0, 600.0, 900.0], np.float64)
    remaining = np.maximum(0.0, predicted - realized)
    want = np.asarray([600.0, 400.0, 0.0, 0.0], np.float64)
    x900 = remaining / WALL_BUDGET_USD
    return [
        _check("predicted range = k*sqrt(var)", abs(predicted - 600.0) < 1e-9,
               f"{predicted}"),
        _check("remaining budget floors at zero",
               bool(np.allclose(remaining, want)), f"{remaining.tolist()}"),
        _check("remaining in 900-USD units",
               abs(float(x900[1]) - 400.0 / 900.0) < 1e-12, f"{x900[1]}"),
    ]


def _selftest_bucket() -> list[tuple[str, bool, str]]:
    cases = ((0.0, "<0.5"), (0.4999, "<0.5"), (0.5, "0.5-0.75"),
             (0.74, "0.5-0.75"), (0.75, "0.75-1.0"), (0.99, "0.75-1.0"),
             (1.0, "1.0-1.5"), (1.49, "1.0-1.5"), (1.5, ">1.5"), (9.0, ">1.5"))
    bad = [(value, want, bucket_of(value)) for value, want in cases
           if bucket_of(value) != want]
    # 405 USD of budget is 0.45 walls: the lowest bucket.
    one = bucket_of(405.0 / WALL_BUDGET_USD)
    return [
        _check("bucket edges are half-open", not bad, f"{bad}"),
        _check("405 USD of budget buckets at <0.5", one == "<0.5", one),
    ]


def _selftest_admission() -> list[tuple[str, bool, str]]:
    """Freshness window, the theta screen, and the rejection above theta."""

    bars = 12
    mids = list(range(bars))
    new_low = [False] * bars
    new_low[3] = True                     # the low extreme is set at bar 3
    new_high = [False] * bars
    remaining_s = [REMAIN_MIN_S + 1.0] * bars
    cell = _fixture_cell(mids, new_low, new_high, remaining_s)
    fresh = fresh_extreme_bars(cell, 1)
    # Ages 0..4 after bar 3 are bars 3,4,5,6,7; bar 8 is age 5 and stale.
    want_fresh = {3, 4, 5, 6, 7}
    got_fresh = set(int(b) for b in np.flatnonzero(fresh))
    # Immune day: budget 360 USD = 0.4 walls, below every theta.
    immune = CellBudget(360.0, np.zeros(bars), np.full(bars, 360.0),
                        np.full(bars, 360.0 / WALL_BUDGET_USD))
    # Exposed day: budget 1800 USD = 2.0 walls, above every theta.
    exposed = CellBudget(1800.0, np.zeros(bars), np.full(bars, 1800.0),
                         np.full(bars, 2.0))
    admitted = admissions(cell, immune, 0.5)
    rejected = admissions(cell, exposed, 0.5)
    nobudget = admissions(cell, exposed, None)
    short = _fixture_cell(mids, new_low, new_high,
                          [REMAIN_MIN_S - 1.0] * bars)
    no_time = admissions(short, immune, 0.5)
    return [
        _check("freshness window is the last 5 bars", got_fresh == want_fresh,
               f"{sorted(got_fresh)}"),
        _check("budget below theta admits the fresh fade",
               [bar for bar, _s in admitted] == sorted(want_fresh),
               f"{admitted}"),
        _check("budget above theta rejects every bar", rejected == [],
               f"{rejected}"),
        _check("NOBUDGET keeps the same fresh bars",
               [bar for bar, _s in nobudget] == sorted(want_fresh),
               f"{nobudget}"),
        _check("under 1800 s remaining admits nothing", no_time == [], f"{no_time}"),
        _check("the faded side of a new low is long",
               all(side == 1 for _bar, side in admitted), f"{admitted}"),
    ]


def _selftest_session_range() -> list[tuple[str, bool, str]]:
    """Running range spans phases and never reads a later bar."""

    rec_a = object.__new__(S1.CellRec)
    rec_a.asset, rec_a.d8 = "NKD", 20220301
    rec_a.lat = np.asarray([0, 60, 120], np.int64) * NANOS_PER_SECOND
    rec_a.mid = np.asarray([1000, 1100, 900], np.int64)
    rec_b = object.__new__(S1.CellRec)
    rec_b.asset, rec_b.d8 = "NKD", 20220301
    rec_b.lat = np.asarray([180, 240], np.int64) * NANOS_PER_SECOND
    rec_b.mid = np.asarray([1500, 800], np.int64)
    ranges = session_running_range([rec_a, rec_b])
    factor = mid2_to_usd("NKD")
    want_a = np.asarray([0.0, 100.0, 200.0]) * factor
    want_b = np.asarray([600.0, 700.0]) * factor
    return [
        _check("phase 0 running range", bool(np.allclose(ranges[0], want_a)),
               f"{ranges[0].tolist()}"),
        _check("phase 1 carries phase 0's extremes",
               bool(np.allclose(ranges[1], want_b)), f"{ranges[1].tolist()}"),
    ]


def _selftest_conversion() -> list[tuple[str, bool, str]]:
    """mid2 -> USD is sweep 3's frozen conversion, and the mill's own factor."""

    rows = []
    for asset in ASSETS:
        mine = mid2_to_usd(asset)
        engine = 0.5e-9 * float(M.ASSET_MULTIPLIER[asset])
        rows.append(_check(f"mid2->USD matches the mill factor ({asset})",
                           abs(mine - engine) < 1e-18, f"{mine} vs {engine}"))
    return rows


def selftest() -> int:
    rows: list[tuple[str, bool, str]] = []
    rows.extend(_selftest_conversion())
    rows.extend(_selftest_calibration())
    rows.extend(_selftest_budget_arithmetic())
    rows.extend(_selftest_bucket())
    rows.extend(_selftest_admission())
    rows.extend(_selftest_session_range())
    print(f"== SWEEP 10 SELFTEST  mutant={_mutant() or 'none'}")
    failed = 0
    for name, ok, detail in rows:
        failed += 0 if ok else 1
        print(f"  [{'ok' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    print(f"  {len(rows) - failed}/{len(rows)} passed")
    if _mutant() == MUTANT_TODAY:
        red = [name for name, ok, _d in rows if not ok]
        expected = "k ignores the scoring day's own realized range"
        print(f"  mutant expectation: {expected!r} is red -> "
              f"{'HELD' if expected in red else 'BROKEN'}")
        return 0 if expected in red else 1
    return 0 if not failed else 1


# --------------------------------------------------------------------------
# Driver.
# --------------------------------------------------------------------------

def _json_default(value: object) -> object:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.bool_):
        return bool(value)
    raise TypeError(f"unserialisable: {type(value)!r}")


def write_report(report: Mapping[str, object]) -> None:
    OUT_PATH.write_text(json.dumps(report, indent=1, sort_keys=True,
                                   default=_json_default) + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="mill sweep 10")
    parser.add_argument("stage", nargs="?", default="all",
                        choices=("all", "selftest"))
    parser.add_argument("--assets", nargs="*", default=list(ASSETS))
    parser.add_argument("--no-log", action="store_true")
    args = parser.parse_args(argv)
    if args.stage == "selftest":
        return selftest()
    if selftest():
        raise SweepRefusal("selftest failed; refusing to run the sweep")

    assets = tuple(args.assets)
    records, days = S1.load_cache()
    explore_days = S1._explore_days(ASSETS)
    budgets, budget_skips = build_budgets(records, assets)
    cells, cell_days, _skipped = S8.build_cells(assets)
    cell_budgets, dropped = build_cell_budgets(cells, records, budgets)
    by_position = {cell.position: cell for cell in cells}

    # The gate: sweep 8's own walk-forward pass, reproduced here.
    run8 = S8.run_gate(cells)
    control = run8.shots["CONTROL"]
    control_cash = S1.cash_line(
        S8.entries_of(control, records), cell_days,
        {asset: int(run8.scored_cells.get(asset, 0)) for asset in ASSETS})
    gate = reproduction_gate(control_cash)
    if not gate["match"]:
        print_gate(gate)
        raise SweepRefusal("sweep-8 CONTROL line did not reproduce cents-exact")

    rows, unruled = priced_rows(control, by_position, cell_budgets, records)
    stage_d_block = stage_d(rows, unruled)

    runs: dict[str, LineRun] = {}
    for theta in THETAS:
        runs[f"theta={theta}"] = run_line(cells, cell_budgets, theta)
    runs[LINE_NOBUDGET] = run_line(cells, cell_budgets, None)
    lines = {name: line_table(run, records, cell_days)
             for name, run in runs.items()}
    fires = [shot for name in runs if name != LINE_NOBUDGET
             for shot in runs[name].shots]
    stage_e_block = {
        "lines": lines,
        "phase_matched": phase_matched_control(cells, cell_budgets, fires),
        "random_wall": random_wall_control(cells, cell_budgets, records),
        "thetas": list(THETAS), "fresh_bars": FRESH_BARS,
    }

    chosen: dict[str, str | None] = {
        asset: select_theta({k: v for k, v in lines.items()
                             if k != LINE_NOBUDGET}, asset)
        for asset in ASSETS}
    wanted = sorted({name for asset, name in chosen.items()
                     if name is not None and asset in DECIDING_ASSETS})
    stage_f_block = price_lines(
        {name: runs[name] for name in wanted + [LINE_NOBUDGET]},
        records, cell_days, explore_days)
    stage_f_block["chosen"] = chosen

    report: dict[str, object] = {
        "schema": SCHEMA, "spec_sha": SPEC_SHA, "code_sha": code_sha(),
        "split_sha": S1.split_sha(), "outcome_law_sha": S1.outcome_law_sha(),
        "family": FAMILY, "parent_trial": PARENT_TRIAL,
        "selection_rule": SELECTION_RULE, "mutant": _mutant(),
        "asset_days": dict(cell_days), "cells": S1.cells_by_asset(records),
        "budget": {
            "days_with_ruler": len(budgets),
            "skips": budget_skips, "cells_without_ruler": dropped,
            "min_calibration_days": MIN_CALIB_DAYS,
            "predicted_range_median_usd": {
                asset: float(np.median([b.predicted_range_usd
                                        for b in budgets.values()
                                        if b.asset == asset]))
                if any(b.asset == asset for b in budgets.values()) else None
                for asset in ASSETS},
            "k_median": {
                asset: float(np.median([b.k for b in budgets.values()
                                        if b.asset == asset]))
                if any(b.asset == asset for b in budgets.values()) else None
                for asset in ASSETS}},
        "sweep8_gate": gate,
        "stage_d": stage_d_block,
        "stage_e": stage_e_block,
        "stage_f": stage_f_block,
    }
    report["decision"] = decide(report)
    report["log"] = log_rows(report)
    write_report(report)

    print_gate(gate)
    print_stage_d(stage_d_block)
    print_stage_e(stage_e_block)
    print_stage_f(report)
    print_decision(report)
    if not args.no_log:
        written = S1.append_log(report["log"])
        print(f"\nhypothesis log: +{written} rows -> {LOG_PATH}")
    print(f"report: {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
