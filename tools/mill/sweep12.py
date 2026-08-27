#!/usr/bin/env python3
"""Sweep 12 of the side-resolution mill: the causal-state attribution screen.

Exploratory tier.  EXPLORE-day bytes only, can kill, cannot promote.

Sweep 11's per-year cuts found year-conditional structure that pooling hides:
NKD/2023 posted +263 usd/day at wall 0.152 against NKD/2024's -233 at wall
0.442, Wilson-disjoint, and SI flipped cash sign across every adjacent year
pair.  Calendar year IS causal at trade time, but it is three samples and no
policy can be written on it.  The question this unit answers is narrower and
decidable: IS THE YEAR CONTRAST CARRIED BY A KNOWABLE DAY-STATE VARIABLE - one
readable at the day's open - so that a STATE-GATED policy follows instead of a
YEAR-FITTED one.

No new policy is proposed here.  This is a pure RE-CUT of entry sets that
already exist: sweep 8's PRIMARY/CONTROL, sweep 8b's E1PRIMARY/E1CONTROL, and
sweep 11's GRAMMAR/GRAMMAR-S3/STAGESHUFFLE.  Every line is reproduced by
importing its own module and re-running its own pass, and each reproduction is
gated CENTS-EXACT against the committed report before a single cut is taken.  A
re-cut of an entry set that does not reproduce is a re-cut of nothing.

Machinery is imported, never re-implemented: sweep 1's ``CellRec`` cache,
``Entry``/``make_entry``, ``cash_line``, ``asset_mdd_day``, ``wilson`` and
``append_log``; sweep 8's ``build_cells``/``run_gate``/``entries_of``; sweep
11's ``build_cells``/``run``; the mill context store for every state value.

Data: mill caches + mill_context only.  No packs, no HOLD day, no teacher or
late label, no 2021 byte, no 2025 byte.
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

import mill as M
import context as CTX
import sweep1 as S1
import sweep7a as S7A
import sweep8 as S8
import sweep11 as S11

# --------------------------------------------------------------------------
# The law, registered before anything is read.
# --------------------------------------------------------------------------

SPEC = """QRE2MILLSWEEP12
QUESTION: sweep 11 found the year contrast.  Is it CARRIED by a day-state
variable knowable at the day's open, or is it year-fitted structure with no
causal handle?

LINES: no new policy.  Seven EXISTING entry sets, each reproduced by importing
its own module: sweep8 PRIMARY, sweep8 CONTROL, sweep8b E1PRIMARY, sweep8b
E1CONTROL, sweep11 GRAMMAR, sweep11 GRAMMAR-S3, sweep11 STAGESHUFFLE.

REPRODUCTION GATE, before any cut: per line per asset, total_usd equal to the
committed report to the CENT and trade count equal exactly.  For the sweep 11
lines the per-(asset, year) totals, trade counts and wall counts must match the
committed by_year block too, because those cells ARE the contrast under test.
Any mismatch is a refusal, not a warning.

DAY-STATE VARIABLES, five, pre-named, all causal at the day's open and all read
through ContextStore.context_for so the strictly-prior law is mechanical:
  V1_FVAR          the day's daily catboost forecast_variance, terciled
                   walk-forward on the asset's strictly-prior EXPLORE days.
  V2_PREVRANGE_ATR the prior locked day's realized session range in ATR14_prev
                   units (levels_prev session_range / atr14_prev_usd), terciled
                   walk-forward.
  V3_ATR14         atr14_prev_usd itself, terciled walk-forward.
  V4_PREVCLOSEPOS  the prior locked day's close position in its own range,
                   (close - low) / (high - low), in three FIXED thirds.
  V5_REGIME        the expanding-median regime flag already cached in
                   forecast.tsv (the `selected` column), two bins.
Tercile edges are the 100/3 and 200/3 percentiles of the asset's own STRICTLY
PRIOR explore-day values, and are refused until MIN_PRIOR_DAYS such days exist
(the same 20-day floor sweeps 8 and 11 already run their strata on).  A day
whose value or whose edges are unavailable is UNSCORED and leaves that V's day
universe entirely.  The MIN_PRIOR_DAYS warm-up applies to all five variables,
V4 and V5 included: the lines being cut cannot trade inside their own strata's
warm-up either, so a V that kept those days would carry ~20 forced-zero 2022
days the tercile Vs do not, and would read as diluted rather than different.

CUTS: for every (line, asset, V, bin): n days, n entries, usd/day (day-cash
summed over the BIN's days divided by ALL of the bin's days - an abstained day
counts zero), usd/trade, wall rate with a Wilson 95% interval, win rate, and
MDD over day-sums.  FLAG a (line, asset, V) when two of its bins separate:
Wilson-disjoint wall rates, or opposite usd/day signs, with at least
MIN_FLAG_TRADES trades on each side.

THE DECISIVE TABLE, per (line, asset, V): the joint (year x bin) distribution of
days and entries, then two spreads of usd/day computed on the SAME universe -
  pooled cross-year spread   max over years minus min over years, bins pooled;
  within-bin cross-year spread  per bin, max minus min over years, averaged
                             over bins weighted by the bin's days;
  cross-bin within-year spread  per year, max minus min over bins, averaged
                             over years weighted by the year's days.
A cell enters a spread only with at least MIN_CELL_DAYS days.  Because a bin
can only compare the years it holds cells in, the pooled spread each bin is
measured against is recomputed over THOSE SAME YEARS; the all-years pooled
spread is reported beside it but never used as the denominator, since dividing
a 2023-vs-2024 within-bin spread by a 2022-vs-2023 pooled spread compares two
different contrasts.  If V carries the years, the within-bin cross-year spread
collapses toward zero while the cross-bin spread stays wide.
RATIO = within-bin cross-year / matched-year pooled cross-year, and the number
of bins and days it rests on is printed with it.

COMPOSITE, labelled EXPLORATORY: the best single V per (line, asset) by
separation (widest Wilson-disjoint wall gap, then most sign flips, then name
order), the best bin of that V by usd/day - which is an IN-SAMPLE choice and is
printed as one - and that gated line's usd/day, wall rate and MDD_day with the
denominator still ALL of the asset's explore days, abstained days counting
zero.  Every bin's gated numbers are printed alongside so the width of the
selection is visible.

DECISION, pre-registered:
  STATE-CARRIED  for at least one V on a deciding asset (NKD, SI): ratio < 0.5
                 AND the best-bin gated line posts usd/day > 300 with gated
                 wall <= 0.25 on that asset.
  YEAR-ONLY      the year contrast survives inside every V's bins; name the Vs
                 that came closest.
  NOISE          the sweep 11 year flags fail to reproduce on the reproduced
                 entry sets.

SELECTION: none beyond the five pre-named Vs and their fixed bins.  No
cash-based tuning of any edge, bin count or threshold.
"""

SCHEMA = "QRE2MILLSWEEP12"
SEED = S1.SEED
ASSETS = S1.ASSETS
DECIDING = S11.DECIDING                  # ("NKD", "SI")

MIN_PRIOR_DAYS = 20                      # inherited from sweeps 8 and 11
MIN_FLAG_TRADES = 3                      # sweep 11's own flag floor
MIN_CELL_DAYS = 5                        # a (year, bin) cell's denominator floor
RATIO_CARRIED = 0.5                      # "under half the pooled spread"
GATED_USD_DAY = 300.0
GATED_WALL_CEILING = 0.25

LOW_MARK = 100.0 / 3.0
HIGH_MARK = 200.0 / 3.0

TERCILE_BINS = ("LOW", "MID", "HIGH")
V4_BINS = ("LOWER3", "MID3", "UPPER3")
V5_BINS = ("UNSELECTED", "SELECTED")
UNSCORED = "UNSCORED"

V1 = "V1_FVAR"
V2 = "V2_PREVRANGE_ATR"
V3 = "V3_ATR14"
V4 = "V4_PREVCLOSEPOS"
V5 = "V5_REGIME"
TERCILE_VARS = (V1, V2, V3)
VARIABLES = (V1, V2, V3, V4, V5)
BINS_OF = {V1: TERCILE_BINS, V2: TERCILE_BINS, V3: TERCILE_BINS,
           V4: V4_BINS, V5: V5_BINS}

S8_LINES = ("PRIMARY", "CONTROL", "E1PRIMARY", "E1CONTROL")
S11_LINES = (S11.BASE_LINE, S11.S3_LINE, S11.SHUFFLE_LINE)
LINES = S8_LINES + S11_LINES

FAMILY = "F9-STATECUT"
PARENT_TRIAL = "sweep11-004"
SELECTION_RULE = ("none: five pre-named day-state variables, fixed bins, "
                  "no cash-based tuning")

OUT_PATH = ROOT / ".audit/mill-sweep12.json"
LOG_PATH = S1.LOG_PATH
SPLIT_PATH = S1.SPLIT_PATH
SWEEP8_PATH = ROOT / ".audit/mill-sweep8.json"
SWEEP11_PATH = ROOT / ".audit/mill-sweep11.json"

MUTANT_ENV = "QRE2_MILL_S12_MUTANT"
MUTANT_TODAY = "tercile_uses_today"
MUTANTS = (MUTANT_TODAY,)


class SweepRefusal(RuntimeError):
    """The re-cut cannot be taken honestly, so it is not taken."""


SPEC_SHA = S1._sha_text(SPEC)


def code_sha() -> str:
    return S1._sha_file(Path(__file__))


def _mutant() -> str:
    name = os.environ.get(MUTANT_ENV, "")
    if name and name not in MUTANTS:
        raise SweepRefusal(f"unknown mutant {name!r}; known: {MUTANTS}")
    return name


# --------------------------------------------------------------------------
# The five day-state variables.  Read only through ContextStore.context_for.
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class DayState:
    """One asset-day's raw state values and the bins they fell in."""

    asset: str
    d8: int
    year: int
    raw: dict[str, float | None]
    bins: dict[str, str]


def raw_state(store: CTX.ContextStore, asset: str, d8: int
              ) -> dict[str, float | None]:
    """The five raw values for one asset-day, or ``None`` where unavailable.

    Everything comes out of ``context_for``: ``priors`` and ``forecast`` are
    prior-derived by construction and may carry the day's own row, while
    ``levels_prev`` is the store's strictly-prior slice.  Nothing here reads a
    price, a cell, an outcome or a later day.
    """

    payload = store.context_for(asset, int(d8))
    forecast = payload.get("forecast")
    priors = payload.get("priors")
    prev = payload.get("levels_prev")
    out: dict[str, float | None] = {name: None for name in VARIABLES}

    if isinstance(forecast, Mapping):
        text = str(forecast.get("forecast_variance", "")).strip()
        if text:
            value = float(text)
            if np.isfinite(value):
                out[V1] = value
        flag = str(forecast.get("selected", "")).strip()
        if flag in ("0", "1"):
            out[V5] = float(int(flag))

    atr_usd: float | None = None
    if isinstance(priors, Mapping) and str(priors.get("atr14_present", "0")) == "1":
        value = float(priors["atr14_prev_usd"])
        if np.isfinite(value) and value > 0.0:
            atr_usd = value
            out[V3] = value

    if isinstance(prev, Mapping):
        high = float(prev["session_high_mid2"])
        low = float(prev["session_low_mid2"])
        close = float(prev["session_close_mid2"])
        span = high - low
        if atr_usd is not None:
            rng_usd = float(prev["session_range_mid2"]) / S7A.usd_to_mid2(asset)
            if np.isfinite(rng_usd):
                out[V2] = rng_usd / atr_usd
        if span > 0.0:
            out[V4] = (close - low) / span
    return out


def tercile_bin(value: float, prior: Sequence[float]) -> str:
    """Walk-forward tercile: edges from the STRICTLY PRIOR values only.

    ``QRE2_MILL_S12_MUTANT=tercile_uses_today`` is applied by the caller, which
    hands this function a sample with the scoring day's own value already in
    it.  That is the whole causal law of the cut: an edge that has seen today
    is an edge today helped choose.
    """

    sample = np.asarray([v for v in prior if np.isfinite(v)], np.float64)
    if len(sample) < MIN_PRIOR_DAYS:
        return UNSCORED
    low = float(np.percentile(sample, LOW_MARK))
    high = float(np.percentile(sample, HIGH_MARK))
    if value < low:
        return "LOW"
    if value < high:
        return "MID"
    return "HIGH"


def fixed_third(value: float) -> str:
    """V4's three fixed thirds of a 0..1 position.  No sample, no fitting."""

    if value < 1.0 / 3.0:
        return V4_BINS[0]
    if value < 2.0 / 3.0:
        return V4_BINS[1]
    return V4_BINS[2]


def day_states(days_by_asset: Mapping[str, Sequence[int]],
               store: CTX.ContextStore | None = None
               ) -> dict[tuple[str, int], DayState]:
    """Every explore day's state, assigned strictly walk-forward per asset.

    The tercile sample is the asset's own EXPLORE days before the scoring day -
    HOLD days never enter it, and neither does the scoring day, except under
    the mutant, which banks the day's value BEFORE binning it.
    """

    store = store if store is not None else CTX.ContextStore()
    peeks = _mutant() == MUTANT_TODAY
    out: dict[tuple[str, int], DayState] = {}
    for asset in sorted(days_by_asset):
        prior: dict[str, list[float]] = {name: [] for name in TERCILE_VARS}
        for index, d8 in enumerate(sorted(int(d) for d in days_by_asset[asset])):
            raw = raw_state(store, asset, d8)
            if peeks:
                for name in TERCILE_VARS:
                    if raw[name] is not None:
                        prior[name].append(float(raw[name]))
            # The warm-up is UNIFORM across the five variables.  V4 and V5 need
            # no prior sample of their own, but the lines being cut cannot
            # trade inside their strata's own 20-day warm-up either, so a V
            # that kept those days would carry ~20 forced-zero 2022 days that
            # V1-V3 do not, and its year rows would be diluted rather than
            # different.  One universe, five variables, comparable rows.
            warming = index < MIN_PRIOR_DAYS
            bins: dict[str, str] = {}
            for name in TERCILE_VARS:
                value = raw[name]
                bins[name] = (UNSCORED if value is None or warming
                              else tercile_bin(float(value), prior[name]))
            bins[V4] = (UNSCORED if raw[V4] is None or warming
                        else fixed_third(float(raw[V4])))
            bins[V5] = (UNSCORED if raw[V5] is None or warming
                        else V5_BINS[int(raw[V5])])
            if not peeks:
                for name in TERCILE_VARS:
                    if raw[name] is not None:
                        prior[name].append(float(raw[name]))
            out[(asset, d8)] = DayState(asset, d8, d8 // 10000, raw, bins)
    return out


# --------------------------------------------------------------------------
# Reproduction of the seven existing entry sets, gated cents-exact.
# --------------------------------------------------------------------------

def _cents(value: float) -> int:
    return int(round(float(value) * 100.0))


def reproduce(assets: Sequence[str]) -> tuple[dict[str, list[S1.Entry]],
                                              dict[str, int],
                                              dict[str, object]]:
    """Re-run sweeps 8 and 11 and check every line against its own report."""

    records, days = S1.load_cache()
    filtered = [rec for rec in records if rec.asset in assets]

    lines: dict[str, list[S1.Entry]] = {}
    cells8, _days8, _skipped8 = S8.build_cells(assets)
    run8 = S8.run_gate(cells8)
    for name in S8_LINES:
        lines[name] = S8.entries_of(run8.shots[name], filtered)
    cells11, _days11, _skipped11, records11 = S11.build_cells(assets)
    out11 = S11.run(cells11)
    for name in S11_LINES:
        lines[name] = list(out11.entries[name])

    payload8 = json.loads(SWEEP8_PATH.read_text())
    payload11 = json.loads(SWEEP11_PATH.read_text())
    committed: dict[str, dict[str, Mapping[str, object]]] = {}
    for name in ("PRIMARY", "CONTROL"):
        committed[name] = payload8["stage_b"]["lines"][name]
    for name in ("E1PRIMARY", "E1CONTROL"):
        committed[name] = payload8["sweep8b"]["stage_b"]["lines"][name]
    for name in S11_LINES:
        committed[name] = {asset: payload11["stage_a"][name]["by_asset"][asset]["cash"]
                           for asset in ASSETS}

    gate: dict[str, object] = {"lines": {}, "year_cells": {}, "ok": True}
    for name in LINES:
        rows: dict[str, object] = {}
        for asset in assets:
            mine = [e for e in lines[name] if e.asset == asset]
            theirs = committed[name][asset]
            total_ok = _cents(sum(e.cert_usd for e in mine)) == _cents(theirs["total_usd"])
            trades_ok = len(mine) == int(theirs["trades"])
            rows[asset] = {
                "trades": len(mine), "trades_committed": int(theirs["trades"]),
                "total_usd": float(sum(e.cert_usd for e in mine)),
                "total_usd_committed": float(theirs["total_usd"]),
                "cents_exact": bool(total_ok), "trades_exact": bool(trades_ok)}
            if not (total_ok and trades_ok):
                gate["ok"] = False
        gate["lines"][name] = rows

    # The sweep 11 by_year cells ARE the contrast under test, so they are gated
    # too: cash, trades and walls, per (asset, year), against the report.
    for name in S11_LINES:
        cells: dict[str, object] = {}
        block = payload11["stage_a"][name]["by_year"]
        for key in sorted(block):
            asset, year = key.split("/")
            if asset not in assets:
                continue
            mine = [e for e in lines[name]
                    if e.asset == asset and e.d8 // 10000 == int(year)]
            theirs = block[key]["cash"]
            ok = (_cents(sum(e.cert_usd for e in mine)) == _cents(theirs["total_usd"])
                  and len(mine) == int(theirs["trades"])
                  and int(sum(e.wall for e in mine)) == int(theirs["walls"]))
            cells[key] = {"trades": len(mine), "trades_committed": int(theirs["trades"]),
                          "total_usd": float(sum(e.cert_usd for e in mine)),
                          "total_usd_committed": float(theirs["total_usd"]),
                          "walls": int(sum(e.wall for e in mine)),
                          "walls_committed": int(theirs["walls"]), "exact": bool(ok)}
            if not ok:
                gate["ok"] = False
        gate["year_cells"][name] = cells
    gate["year_flags_committed"] = {name: payload11["year_flags"][name]
                                    for name in S11_LINES}
    return lines, {k: int(v) for k, v in days.items() if k in assets}, gate


# --------------------------------------------------------------------------
# The cuts.
# --------------------------------------------------------------------------

def _rate(hits: int, total: int) -> dict[str, object]:
    low, high = S1.wilson(int(hits), int(total))
    return {"hits": int(hits), "n": int(total),
            "rate": (hits / total) if total else None,
            "ci_low": low if total else None, "ci_high": high if total else None}


def cut_cell(entries: Sequence[S1.Entry], n_days: int,
             asset: str) -> dict[str, object]:
    """One (line, asset, bin) cell.  The denominator is DAYS, not trades."""

    certs = np.asarray([e.cert_usd for e in entries], np.float64)
    walls = int(sum(e.wall for e in entries))
    return {
        "days": int(n_days), "trades": len(entries),
        "total_usd": float(certs.sum()) if len(certs) else 0.0,
        "usd_per_day": (float(certs.sum()) / n_days) if n_days else None,
        "usd_per_trade": float(certs.mean()) if len(certs) else None,
        "win_rate": float((certs > 0).mean()) if len(certs) else None,
        "wall": _rate(walls, len(entries)),
        "mdd_day_usd": S1.asset_mdd_day(list(entries), asset),
    }


def cut_line(entries: Sequence[S1.Entry], states: Mapping[tuple[str, int], DayState],
             asset: str, variable: str) -> dict[str, object]:
    """One (line, asset, V): every bin's cell plus the unscored remainder."""

    universe = [key for key in states if key[0] == asset]
    by_bin: dict[str, list[int]] = {}
    for key in universe:
        by_bin.setdefault(states[key].bins[variable], []).append(key[1])
    rows = [e for e in entries if e.asset == asset]
    out: dict[str, object] = {"bins": {}, "variable": variable, "asset": asset}
    for name in list(BINS_OF[variable]) + [UNSCORED]:
        days = sorted(by_bin.get(name, []))
        if not days and name == UNSCORED:
            continue
        held = set(days)
        out["bins"][name] = cut_cell([e for e in rows if e.d8 in held],
                                     len(days), asset)
    scored_days = sum(len(by_bin.get(name, [])) for name in BINS_OF[variable])
    out["scored_days"] = int(scored_days)
    out["unscored_days"] = len(by_bin.get(UNSCORED, []))
    return out


def flags_for(cut: Mapping[str, object]) -> list[str]:
    """Bin pairs that separate: Wilson-disjoint walls, or opposite cash signs."""

    out: list[str] = []
    names = [n for n in BINS_OF[cut["variable"]] if n in cut["bins"]]
    for left in range(len(names)):
        for right in range(left + 1, len(names)):
            a = cut["bins"][names[left]]
            b = cut["bins"][names[right]]
            if a["trades"] < MIN_FLAG_TRADES or b["trades"] < MIN_FLAG_TRADES:
                continue
            wa, wb = a["wall"], b["wall"]
            if wa["ci_high"] < wb["ci_low"] or wb["ci_high"] < wa["ci_low"]:
                out.append(f"{names[left]} vs {names[right]}: wall CIs disjoint "
                           f"({wa['rate']:.3f} vs {wb['rate']:.3f})")
            if (a["usd_per_day"] > 0.0) != (b["usd_per_day"] > 0.0):
                out.append(f"{names[left]} vs {names[right]}: cash sign flips "
                           f"({a['usd_per_day']:.0f} vs {b['usd_per_day']:.0f})")
    return out


def separation(cut: Mapping[str, object]) -> tuple[float, int]:
    """(widest Wilson-disjoint wall gap, count of cash sign flips)."""

    gap = 0.0
    flips = 0
    names = [n for n in BINS_OF[cut["variable"]] if n in cut["bins"]]
    for left in range(len(names)):
        for right in range(left + 1, len(names)):
            a, b = cut["bins"][names[left]], cut["bins"][names[right]]
            if a["trades"] < MIN_FLAG_TRADES or b["trades"] < MIN_FLAG_TRADES:
                continue
            wa, wb = a["wall"], b["wall"]
            if wa["ci_high"] < wb["ci_low"] or wb["ci_high"] < wa["ci_low"]:
                gap = max(gap, abs(wa["rate"] - wb["rate"]))
            if (a["usd_per_day"] > 0.0) != (b["usd_per_day"] > 0.0):
                flips += 1
    return (gap, flips)


# --------------------------------------------------------------------------
# THE DECISIVE TABLE: does the V's bin structure reproduce the year contrast?
# --------------------------------------------------------------------------

def _spread(values: Sequence[float]) -> float | None:
    finite = [float(v) for v in values if v is not None and np.isfinite(v)]
    return (max(finite) - min(finite)) if len(finite) >= 2 else None


def decisive(entries: Sequence[S1.Entry],
             states: Mapping[tuple[str, int], DayState],
             asset: str, variable: str) -> dict[str, object]:
    """The (year x bin) joint table and the two spreads it decides on.

    Both spreads are computed on this V's OWN scored day universe, so the
    ratio is not contaminated by the days the V cannot bin.
    """

    bins = BINS_OF[variable]
    days: dict[tuple[int, str], list[int]] = {}
    for key, state in states.items():
        if key[0] != asset:
            continue
        name = state.bins[variable]
        if name == UNSCORED:
            continue
        days.setdefault((state.year, name), []).append(key[1])
    years = sorted({year for year, _b in days})
    rows = [e for e in entries if e.asset == asset]
    cash: dict[int, float] = {}
    trades: dict[int, int] = {}
    for row in rows:
        cash[row.d8] = cash.get(row.d8, 0.0) + row.cert_usd
        trades[row.d8] = trades.get(row.d8, 0) + 1

    joint: dict[str, object] = {}
    for year in years:
        for name in bins:
            held = days.get((year, name), [])
            total = sum(cash.get(d, 0.0) for d in held)
            joint[f"{year}/{name}"] = {
                "days": len(held), "entries": sum(trades.get(d, 0) for d in held),
                "total_usd": float(total),
                "usd_per_day": (float(total) / len(held)) if held else None,
                "counted": bool(len(held) >= MIN_CELL_DAYS)}

    def cell(year: int, name: str) -> float | None:
        row = joint[f"{year}/{name}"]
        return row["usd_per_day"] if row["counted"] else None

    # Pooled over bins, per year: the contrast this unit is trying to explain.
    pooled: dict[int, float | None] = {}
    for year in years:
        held = [d for name in bins for d in days.get((year, name), [])]
        pooled[year] = ((sum(cash.get(d, 0.0) for d in held) / len(held))
                        if held else None)
    pooled_spread = _spread([pooled[y] for y in years])

    # A bin can only compare the years it actually has cells in, so the pooled
    # spread it is measured against is recomputed over THOSE SAME YEARS.  The
    # all-years pooled spread stays in the report, but a ratio that divided a
    # 2023-vs-2024 within-bin spread by a 2022-vs-2023 pooled spread would be
    # comparing two different contrasts and would read far too favourably.
    within_bin: dict[str, float | None] = {}
    matched_pooled: dict[str, float | None] = {}
    bin_ratio: dict[str, float | None] = {}
    bin_years: dict[str, list[int]] = {}
    weights_bin: dict[str, int] = {}
    for name in bins:
        seen = [y for y in years if joint[f"{y}/{name}"]["counted"]]
        bin_years[name] = seen
        within_bin[name] = _spread([cell(y, name) for y in seen])
        matched_pooled[name] = _spread([pooled[y] for y in seen])
        bin_ratio[name] = ((within_bin[name] / matched_pooled[name])
                           if (within_bin[name] is not None
                               and matched_pooled[name] not in (None, 0.0))
                           else None)
        weights_bin[name] = sum(len(days.get((y, name), [])) for y in seen)
    within_year: dict[int, float | None] = {}
    weights_year: dict[int, int] = {}
    for year in years:
        within_year[year] = _spread([cell(year, name) for name in bins])
        weights_year[year] = sum(len(days.get((year, name), [])) for name in bins
                                 if joint[f"{year}/{name}"]["counted"])

    def weighted(values: Mapping[object, float | None],
                 weights: Mapping[object, int]) -> float | None:
        num = den = 0.0
        for key, value in values.items():
            if value is None:
                continue
            num += float(value) * float(weights[key])
            den += float(weights[key])
        return (num / den) if den > 0.0 else None

    cross_year = weighted(within_bin, weights_bin)
    cross_bin = weighted(within_year, weights_year)
    matched = weighted(matched_pooled, weights_bin)
    ratio = ((cross_year / matched)
             if (cross_year is not None and matched not in (None, 0.0))
             else None)
    compared = [name for name in bins if within_bin[name] is not None]
    return {
        "variable": variable, "asset": asset, "years": years,
        "joint": joint,
        "pooled_usd_per_day_by_year": {str(y): pooled[y] for y in years},
        "pooled_cross_year_spread": pooled_spread,
        "matched_pooled_cross_year_spread": matched,
        "within_bin_cross_year_spread": {k: v for k, v in within_bin.items()},
        "within_bin_years_compared": {k: list(v) for k, v in bin_years.items()},
        "within_bin_ratio": {k: v for k, v in bin_ratio.items()},
        "cross_bin_within_year_spread": {str(k): v for k, v in within_year.items()},
        "within_bin_cross_year_weighted": cross_year,
        "cross_bin_within_year_weighted": cross_bin,
        "ratio": ratio,
        "bins_compared": compared,
        "days_compared": int(sum(weights_bin[name] for name in compared)),
        "explains_year": bool(ratio is not None and ratio < RATIO_CARRIED),
        "min_cell_days": MIN_CELL_DAYS,
    }


# --------------------------------------------------------------------------
# The composite: gate the line to one bin.  EXPLORATORY, in-sample selected.
# --------------------------------------------------------------------------

def gated(entries: Sequence[S1.Entry], states: Mapping[tuple[str, int], DayState],
          asset: str, variable: str, bin_name: str,
          explore_days: int) -> dict[str, object]:
    """Trade only inside one bin, abstain elsewhere, over ALL explore days."""

    held = {key[1] for key, state in states.items()
            if key[0] == asset and state.bins[variable] == bin_name}
    rows = [e for e in entries if e.asset == asset and e.d8 in held]
    certs = np.asarray([e.cert_usd for e in rows], np.float64)
    walls = int(sum(e.wall for e in rows))
    return {
        "bin": bin_name, "gated_days": len(held), "explore_days": int(explore_days),
        "trades": len(rows),
        "total_usd": float(certs.sum()) if len(certs) else 0.0,
        "usd_per_day_all_explore_days": (float(certs.sum()) / explore_days
                                         if explore_days else None),
        "usd_per_trade": float(certs.mean()) if len(certs) else None,
        "wall": _rate(walls, len(rows)),
        "win_rate": float((certs > 0).mean()) if len(certs) else None,
        "mdd_day_usd": S1.asset_mdd_day(rows, asset),
    }


def best_variable(cuts: Mapping[str, Mapping[str, object]]) -> str:
    """Widest Wilson-disjoint wall gap, then most sign flips, then name order."""

    ranked = sorted(VARIABLES,
                    key=lambda name: (-separation(cuts[name])[0],
                                      -separation(cuts[name])[1], name))
    return ranked[0]


def best_bin(cut: Mapping[str, object]) -> str:
    """Highest usd/day.  This IS an in-sample choice and is labelled as one."""

    names = [n for n in BINS_OF[cut["variable"]] if n in cut["bins"]
             and cut["bins"][n]["days"] > 0]
    return max(names, key=lambda n: (cut["bins"][n]["usd_per_day"], n))


# --------------------------------------------------------------------------
# The pre-registered decision.
# --------------------------------------------------------------------------

def decide(report: Mapping[str, object]) -> dict[str, object]:
    if not report["reproduction"]["ok"]:
        return {"verdict": "NOISE",
                "why": "the reproduced entry sets do not match the committed "
                       "reports, so the year flags are not reproduced either",
                "hits": [], "closest": []}
    if not report["reproduction"]["year_flags_reproduced"]:
        return {"verdict": "NOISE",
                "why": "the sweep 11 year flags did not reproduce on the "
                       "reproduced entry sets",
                "hits": [], "closest": []}
    hits: list[dict[str, object]] = []
    scored: list[tuple[float, str]] = []
    for line in LINES:
        for asset in DECIDING:
            block = report["cuts"][line].get(asset)
            if block is None:
                continue
            for name in VARIABLES:
                table = block["decisive"][name]
                ratio = table["ratio"]
                if ratio is not None:
                    scored.append((float(ratio), f"{line}/{asset}/{name}"))
                if ratio is None or ratio >= RATIO_CARRIED:
                    continue
                pick = block["gated_best_bin_per_variable"][name]
                usd = pick["usd_per_day_all_explore_days"]
                wall = pick["wall"]["rate"]
                if (usd is not None and usd > GATED_USD_DAY
                        and wall is not None and wall <= GATED_WALL_CEILING):
                    hits.append({"line": line, "asset": asset, "variable": name,
                                 "ratio": ratio, "usd_per_day": usd,
                                 "wall": wall, "bin": pick["bin"]})
    closest = [f"{key} ratio {value:.3f}"
               for value, key in sorted(scored)[:8]]
    if hits:
        return {"verdict": "STATE-CARRIED",
                "why": "at least one V collapses the cross-year spread below "
                       "half on a deciding asset AND its best-bin gate clears "
                       "the cash and wall bars",
                "hits": hits, "closest": closest}
    return {"verdict": "YEAR-ONLY",
            "why": "the year contrast survives inside every V's bins on the "
                   "deciding assets, or the V that collapses it does not pay",
            "hits": [], "closest": closest}


# --------------------------------------------------------------------------
# Printing.
# --------------------------------------------------------------------------

def print_decision_table() -> None:
    print("DECISION TABLE (pre-registered, before any number is read)")
    print(f"  STATE-CARRIED  some V on NKD or SI: within-bin cross-year spread "
          f"< {RATIO_CARRIED} x pooled,")
    print(f"                 AND its best-bin gate posts usd/day > "
          f"{GATED_USD_DAY:.0f} at wall <= {GATED_WALL_CEILING:.2f}")
    print("  YEAR-ONLY      the year contrast survives inside every V's bins")
    print("  NOISE          the year flags fail to reproduce")
    print(f"  variables      {', '.join(VARIABLES)}")
    print(f"  floors         prior days {MIN_PRIOR_DAYS}, flag trades "
          f"{MIN_FLAG_TRADES}, cell days {MIN_CELL_DAYS}")


def print_reproduction(report: Mapping[str, object]) -> None:
    gate = report["reproduction"]
    print("\nREPRODUCTION GATE  (cents-exact against the committed reports)")
    for line in LINES:
        parts = []
        for asset in ASSETS:
            row = gate["lines"][line].get(asset)
            if row is None:
                continue
            mark = "OK" if row["cents_exact"] and row["trades_exact"] else "MISMATCH"
            parts.append(f"{asset} {row['total_usd']:+.2f}/{row['total_usd_committed']:+.2f}"
                         f" n={row['trades']}/{row['trades_committed']} {mark}")
        print(f"  {line:14s} " + "  ".join(parts))
    bad = [f"{line}:{key}" for line in gate["year_cells"]
           for key, row in gate["year_cells"][line].items() if not row["exact"]]
    cells = sum(len(gate["year_cells"][line]) for line in gate["year_cells"])
    print(f"  sweep11 by_year cells: {cells - len(bad)}/{cells} exact "
          f"(cash, trades, walls)" + (f"  MISMATCH {bad}" if bad else ""))
    print(f"  year flags reproduced: {gate['year_flags_reproduced']}  "
          f"({gate['year_flags_checked']} flag strings re-derived)")
    print(f"  GATE: {'PASS' if gate['ok'] else 'REFUSE'}")


def _f(value: float | None, spec: str = "+8.1f", blank: str = "       -") -> str:
    return blank if value is None else format(float(value), spec)


def _fmt_cell(row: Mapping[str, object]) -> str:
    wall = row["wall"]
    return (f"days {row['days']:3d}  n {row['trades']:4d}  "
            f"usd/day {_f(row['usd_per_day'])}  "
            f"usd/trade {_f(row['usd_per_trade'], '+7.1f', '      -')}  "
            f"wall {_f(wall['rate'], '.3f', '  -  ')}"
            f" [{_f(wall['ci_low'], '.3f', '  -  ')},"
            f"{_f(wall['ci_high'], '.3f', '  -  ')}]  "
            f"win {_f(row['win_rate'], '.3f', '  -  ')}  "
            f"MDD_day {row['mdd_day_usd']:.0f}")


def print_cuts(report: Mapping[str, object]) -> None:
    print("\nCUT TABLES  (per line x asset x V; flagged rows in full, rest summarised)")
    for line in LINES:
        for asset in ASSETS:
            block = report["cuts"][line].get(asset)
            if block is None:
                continue
            for name in VARIABLES:
                cut = block["cuts"][name]
                marks = cut["flags"]
                head = (f"  {line}/{asset}/{name}  scored days "
                        f"{cut['scored_days']} unscored {cut['unscored_days']}")
                if not marks:
                    counts = "  ".join(
                        f"{b}:{cut['bins'][b]['days']}d/{cut['bins'][b]['trades']}n/"
                        + _f(cut["bins"][b]["usd_per_day"], "+.0f", "-")
                        for b in BINS_OF[name] if b in cut["bins"])
                    print(f"{head}  UNFLAGGED   {counts}")
                    continue
                print(f"{head}   *** {len(marks)} FLAG(S)")
                for b in BINS_OF[name]:
                    if b in cut["bins"]:
                        print(f"      {b:10s} {_fmt_cell(cut['bins'][b])}")
                for mark in marks:
                    print(f"      FLAG  {mark}")


def print_decisive(report: Mapping[str, object]) -> None:
    print("\nDECISIVE TABLE  (does the V's bin structure reproduce the year contrast?)")
    for line in LINES:
        for asset in ASSETS:
            block = report["cuts"][line].get(asset)
            if block is None:
                continue
            print(f"\n  {line} / {asset}")
            for name in VARIABLES:
                table = block["decisive"][name]
                years = table["years"]
                print(f"    {name}   joint (year x bin), days/entries/usd-per-day"
                      f"   [* = under {MIN_CELL_DAYS} days, excluded from spreads]")
                header = "      year   " + "".join(
                    f"{b:>22s}" for b in BINS_OF[name]) + f"{'POOLED':>16s}"
                print(header)
                for year in years:
                    cells = []
                    for b in BINS_OF[name]:
                        row = table["joint"][f"{year}/{b}"]
                        usd = ("      -" if row["usd_per_day"] is None
                               else f"{row['usd_per_day']:+7.0f}")
                        star = " " if row["counted"] else "*"
                        cells.append(f"{row['days']:3d}d/{row['entries']:3d}n/{usd}{star}"
                                     .rjust(22))
                    pooled = table["pooled_usd_per_day_by_year"][str(year)]
                    cells.append(("       -" if pooled is None
                                  else f"{pooled:+15.0f}"))
                    print(f"      {year}   " + "".join(cells))
                ratio = table["ratio"]
                print(f"      pooled cross-year spread (all years) "
                      f"{_num(table['pooled_cross_year_spread'])}   "
                      f"pooled on the MATCHED years "
                      f"{_num(table['matched_pooled_cross_year_spread'])}")
                print(f"      within-bin cross-year "
                      f"{_num(table['within_bin_cross_year_weighted'])}"
                      f"   cross-bin within-year "
                      f"{_num(table['cross_bin_within_year_weighted'])}"
                      f"   per-bin years compared "
                      + ", ".join(f"{b}{table['within_bin_years_compared'][b]}"
                                  for b in BINS_OF[name]))
                print(f"      RATIO {'-' if ratio is None else f'{ratio:.3f}'}"
                      f"   explains_year={table['explains_year']}"
                      f"   (on {len(table['bins_compared'])} bin(s), "
                      f"{table['days_compared']} days)")


def _num(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f}"


def print_composite(report: Mapping[str, object]) -> None:
    print("\nCOMPOSITE  (EXPLORATORY SUBSET NUMBERS; the bin is chosen IN SAMPLE "
          "by usd/day.")
    print("            denominator is ALL explore days - abstained days count zero)")
    for line in LINES:
        for asset in ASSETS:
            block = report["cuts"][line].get(asset)
            if block is None:
                continue
            pick = block["best_variable"]
            print(f"  {line}/{asset}  best V by separation = {pick} "
                  f"(wall gap {block['separation'][pick][0]:.3f}, "
                  f"{block['separation'][pick][1]} sign flips)")
            for name in VARIABLES:
                row = block["gated_best_bin_per_variable"][name]
                mark = " <-- best V" if name == pick else ""
                print(f"      {name:18s} bin {row['bin']:10s} "
                      f"gated days {row['gated_days']:3d}/{row['explore_days']:3d}"
                      f"  n {row['trades']:4d}  "
                      f"usd/day {_f(row['usd_per_day_all_explore_days'], '+8.1f')}"
                      f"  wall {_f(row['wall']['rate'], '.3f', '  -  ')}"
                      f"  MDD_day {row['mdd_day_usd']:8.0f}{mark}")
            widths = block["gate_width"]
            print(f"      selection width across all bins of {pick}: usd/day "
                  f"{widths[pick]}")


def print_verdict(report: Mapping[str, object]) -> None:
    decision = report["decision"]
    print(f"\nVERDICT  {decision['verdict']}")
    print(f"  {decision['why']}")
    for hit in decision["hits"]:
        print(f"  HIT  {hit['line']}/{hit['asset']}/{hit['variable']} bin "
              f"{hit['bin']}: ratio {hit['ratio']:.3f}, usd/day "
              f"{hit['usd_per_day']:.1f}, wall {hit['wall']:.3f}")
    if decision["closest"]:
        print("  closest (smallest within-bin cross-year ratio on a deciding asset):")
        for row in decision["closest"]:
            print(f"    {row}")


# --------------------------------------------------------------------------
# Selftest.
# --------------------------------------------------------------------------

def _check(name: str, ok: bool, detail: str) -> tuple[str, bool, str]:
    return (name, bool(ok), detail)


def _planted_states(assign: Mapping[int, str], variable: str
                    ) -> dict[tuple[str, int], DayState]:
    """A fixture day universe with hand-placed bins.  No context read."""

    out: dict[tuple[str, int], DayState] = {}
    for d8, name in assign.items():
        out[("FIX", d8)] = DayState("FIX", int(d8), int(d8) // 10000,
                                    {v: None for v in VARIABLES},
                                    {v: (name if v == variable else UNSCORED)
                                     for v in VARIABLES})
    return out


def _entry(d8: int, cert: float, wall: bool = False, bar: int = 1) -> S1.Entry:
    return S1.Entry(0, "FIX", int(d8), bar, int(d8) * 1000 + bar, 1,
                    float(cert), bool(wall), 0, "fixture")


def selftest() -> int:
    mutant = _mutant()
    out: list[tuple[str, bool, str]] = []

    # --- 1. THE MUTANT'S TARGET: a hand-computed walk-forward tercile -------
    # Prior sample is 1..20 (exactly the MIN_PRIOR_DAYS floor).  numpy's linear
    # percentile puts the 100/3 edge at 1 + (19 * 1/3) = 7.3333 and the 200/3
    # edge at 1 + (19 * 2/3) = 13.6667.  The scoring day's own value is 7.0,
    # which is BELOW 7.3333, so walk-forward it is LOW.
    #
    # Include the day's own 7.0 in the sample and the 21-point edge lands at
    # exactly 7.0 (the two sevens straddle index 6.667), so 7.0 is no longer
    # strictly below it and the same day reads MID.  That single day is the
    # whole difference between a state cut and a state fit.
    prior = [float(v) for v in range(1, 21)]
    edges = (float(np.percentile(np.asarray(prior), LOW_MARK)),
             float(np.percentile(np.asarray(prior), HIGH_MARK)))
    out.append(_check(
        "tercile edges are the hand-computed 7.3333 / 13.6667",
        abs(edges[0] - 7.333333333333333) < 1e-9
        and abs(edges[1] - 13.666666666666666) < 1e-9, f"{edges}"))

    states = day_states({"FIX": []})       # exercises the empty-asset path
    out.append(_check("an asset with no explore day yields no state",
                      states == {}, f"{states}"))

    # The walk-forward assignment itself, driven through day_states via a stub
    # store so the ordering law (bin, THEN bank) is what is under test.
    stub = _StubStore({("FIX", 20220100 + i): float(i) for i in range(1, 21)}
                      | {("FIX", 20220121): 7.0, ("FIX", 20220122): 7.4})
    got = day_states({"FIX": sorted(d for _a, d in stub.values)}, stub)
    day21 = got[("FIX", 20220121)].bins[V1]
    out.append(_check(
        "MUTANT TARGET: day 21 (value 7.0, prior 1..20) is LOW walk-forward",
        day21 == "LOW", f"bin={day21}"))
    # Day 22's prior is 1..20 plus day 21's 7.0: edges 6.8333 / 13.3333, so 7.4
    # is MID.  This case is the same under the mutant and stays green: the
    # mutant has to be caught by the case above, not by an accident here.
    day22 = got[("FIX", 20220122)].bins[V1]
    out.append(_check("day 22 (value 7.4) is MID under both readings",
                      day22 == "MID", f"bin={day22}"))
    first = got[("FIX", 20220101)].bins[V1]
    out.append(_check(f"the first {MIN_PRIOR_DAYS} days are UNSCORED, not binned",
                      first == UNSCORED, f"bin={first}"))

    # --- 2. a planted V that FULLY explains a planted year contrast ---------
    # Cash depends on the BIN alone (+1000/day in HIGH, -1000/day in LOW) and
    # the years differ only in bin composition, so the pooled year spread is
    # wide while every within-bin cross-year spread is exactly zero.
    # The day universe: 2023 is HIGH-heavy (12 HIGH, 6 LOW), 2024 is LOW-heavy
    # (6 HIGH, 12 LOW).  Every cell clears MIN_CELL_DAYS.  Hand-computed:
    #   pooled 2023 = (12*1000 + 6*-1000)/18 = +333.33, 2024 = -333.33,
    #   so the pooled cross-year spread is 666.67 - a year contrast with no
    #   year term anywhere in the cash.
    #   within-bin cross-year: HIGH is +1000 in both years, LOW is -1000 in
    #   both, so every within-bin spread is 0 and the ratio is 0.
    #   cross-bin within-year: 1000 - -1000 = 2000 in each year.
    assign: dict[int, str] = {}
    for i in range(12):
        assign[20230101 + i] = "HIGH"
        assign[20240201 + i] = "LOW"
    for i in range(6):
        assign[20230201 + i] = "LOW"
        assign[20240101 + i] = "HIGH"
    entries = [_entry(d8, 1000.0 if name == "HIGH" else -1000.0)
               for d8, name in assign.items()]
    planted = _planted_states(assign, V1)
    table = decisive(entries, planted, "FIX", V1)
    out.append(_check(
        "planted-explained: within-bin cross-year spread is exactly zero",
        table["within_bin_cross_year_weighted"] == 0.0,
        f"{table['within_bin_cross_year_weighted']}"))
    out.append(_check(
        "planted-explained: pooled cross-year spread is the hand-computed 666.67",
        abs(float(table["pooled_cross_year_spread"]) - 2000.0 / 3.0) < 1e-9,
        f"{table['pooled_cross_year_spread']}"))
    out.append(_check(
        "planted-explained: the decisive logic recovers explains_year=True",
        table["ratio"] == 0.0 and table["explains_year"] is True,
        f"ratio={table['ratio']}"))
    out.append(_check(
        "planted-explained: cross-bin within-year spread stays wide (2000)",
        abs(float(table["cross_bin_within_year_weighted"]) - 2000.0) < 1e-9,
        f"{table['cross_bin_within_year_weighted']}"))

    # --- 3. a planted V that does NOT explain the year contrast -------------
    # Same bins, same day universe, but cash depends on the YEAR alone.  Then
    # every within-bin cross-year spread equals the pooled one and the ratio
    # pins at 1.0.
    year_entries = [_entry(d8, 1000.0 if d8 // 10000 == 2023 else -1000.0)
                    for d8 in assign]
    table2 = decisive(year_entries, planted, "FIX", V1)
    out.append(_check(
        "planted-unexplained: ratio pins at 1.0, explains_year=False",
        table2["ratio"] is not None and abs(table2["ratio"] - 1.0) < 1e-9
        and table2["explains_year"] is False, f"ratio={table2['ratio']}"))
    out.append(_check(
        "planted-unexplained: cross-bin within-year spread is zero",
        table2["cross_bin_within_year_weighted"] == 0.0,
        f"{table2['cross_bin_within_year_weighted']}"))

    # --- 4. the cut denominator: an abstained day counts zero ---------------
    cut = cut_line([_entry(20230101, 500.0)], planted, "FIX", V1)
    high = cut["bins"]["HIGH"]
    out.append(_check(
        "usd/day divides by the BIN's days, not by the days that traded",
        high["days"] == 18 and high["trades"] == 1
        and abs(high["usd_per_day"] - 500.0 / 18.0) < 1e-9, f"{high}"))

    # --- 5. flags: Wilson-disjoint walls and cash sign flips ----------------
    wallish = [_entry(20230101 + i, 100.0, wall=False) for i in range(9)] \
        + [_entry(20230201 + i, -100.0, wall=True) for i in range(4)]
    wcut = cut_line(wallish, planted, "FIX", V1)
    wcut["variable"] = V1
    marks = flags_for(wcut)
    out.append(_check("flags catch a 0.000 vs 1.000 wall split and a sign flip",
                      any("wall CIs disjoint" in m for m in marks)
                      and any("cash sign flips" in m for m in marks), f"{marks}"))

    # --- 6. fixed thirds and the regime flag are not fitted -----------------
    out.append(_check("V4's thirds are fixed at 1/3 and 2/3",
                      (fixed_third(0.0), fixed_third(0.33), fixed_third(0.34),
                       fixed_third(0.66), fixed_third(0.67), fixed_third(1.0))
                      == ("LOWER3", "LOWER3", "MID3", "MID3", "UPPER3", "UPPER3"),
                      ""))

    # --- 7. the gate divides by ALL explore days ---------------------------
    row = gated([_entry(20230101, 900.0)], planted, "FIX", V1, "HIGH", 30)
    out.append(_check("the gated line's denominator is all explore days",
                      row["gated_days"] == 18 and row["explore_days"] == 30
                      and abs(row["usd_per_day_all_explore_days"] - 30.0) < 1e-9,
                      f"{row}"))

    print(f"\nSELFTEST  sweep12  mutant={mutant or 'none'}")
    failures = 0
    for name, ok, detail in out:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"   {detail}" if not ok else ""))
        failures += 0 if ok else 1
    red = [name for name, ok, _d in out if not ok]
    if mutant:
        print(f"  mutant={mutant}: {len(red)}/{len(out)} cases RED")
        for name in red:
            print(f"    RED  {name}")
        if not red:
            print(f"  DEAD: mutant {mutant} left every case green")
        return 1
    print(f"  {len(out) - failures}/{len(out)} green")
    return 1 if failures else 0


class _StubStore:
    """A ContextStore-shaped stub: one V1 value per asset-day, nothing else.

    The selftest drives the walk-forward ordering through ``day_states`` rather
    than around it, so the case actually covers the code the mutant edits.
    """

    def __init__(self, values: Mapping[tuple[str, int], float]) -> None:
        self.values = dict(values)

    def context_for(self, asset: str, d8: int) -> dict[str, object]:
        value = self.values.get((asset, int(d8)))
        forecast = (None if value is None
                    else {"forecast_variance": repr(float(value)), "selected": "0"})
        return {"asset": asset, "d8": int(d8), "priors": None,
                "forecast": forecast, "levels_prev": None,
                "levels_lookback": [], "levels_prior_days": 0}


# --------------------------------------------------------------------------
# Hypothesis log.
# --------------------------------------------------------------------------

def log_rows(report: Mapping[str, object]) -> list[dict[str, object]]:
    stamp = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    shared = {
        "registered_utc": stamp, "family": FAMILY, "spec_sha": SPEC_SHA,
        "code_sha": report["code_sha"], "split_sha": report["split_sha"],
        "outcome_law_sha": report["outcome_law_sha"], "null_seed": SEED,
        "parent_trial": PARENT_TRIAL, "selection_rule": SELECTION_RULE,
        "verdict": "", "days": sum(report["explore_days"].values())}
    rows: list[dict[str, object]] = []
    verdict = report["decision"]["verdict"]
    for index, line in enumerate(LINES, start=1):
        cash = {asset: report["reproduction"]["lines"][line][asset]
                for asset in ASSETS if asset in report["reproduction"]["lines"][line]}
        picks = {}
        for asset in ASSETS:
            block = report["cuts"][line].get(asset)
            picks[asset] = (None if block is None else
                            block["gated_best_bin_per_variable"][block["best_variable"]])
        best = {asset: (report["cuts"][line][asset]["best_variable"]
                        if asset in report["cuts"][line] else "-")
                for asset in ASSETS}
        ratios = []
        for asset in DECIDING:
            block = report["cuts"][line].get(asset)
            if block is None:
                continue
            value = block["decisive"][best[asset]]["ratio"]
            ratios.append(f"{asset}:{best[asset]}"
                          + (f" ratio {value:.2f}" if value is not None else " ratio -"))
        rows.append(dict(shared, **{
            "id": f"sweep12-{index:03d}",
            "rule": f"state-cut/{line}",
            "params": (f"V1..V5 fixed bins; prior-day floor {MIN_PRIOR_DAYS}; "
                       f"cell floor {MIN_CELL_DAYS} days; no cash tuning"),
            # The share of explore days the reported gate would actually trade
            # on: the cash columns beside it are that subset's, so a coverage
            # of trades-per-day would describe the wrong object.
            "coverage": (sum(row["gated_days"] for row in picks.values()
                             if row is not None)
                         / max(1, sum(report["explore_days"].values()))),
            "walls_hg": _pick(picks, "HG", "wall_hits"),
            "walls_nkd": _pick(picks, "NKD", "wall_hits"),
            "walls_si": _pick(picks, "SI", "wall_hits"),
            "hg_usd_day": _pick(picks, "HG", "usd"),
            "nkd_usd_day": _pick(picks, "NKD", "usd"),
            "si_usd_day": _pick(picks, "SI", "usd"),
            "mdd_hg": _pick(picks, "HG", "mdd"),
            "mdd_nkd": _pick(picks, "NKD", "mdd"),
            "mdd_si": _pick(picks, "SI", "mdd"),
            "note": (f"F9-STATECUT re-cut of {line} (repro cents-exact); "
                     f"{verdict}; cash cols are the EXPLORATORY best-V best-bin "
                     f"GATED subset over all explore days; "
                     + "; ".join(ratios)),
        }))
    return rows


def _pick(picks: Mapping[str, object], asset: str, field_name: str) -> object:
    row = picks.get(asset)
    if row is None:
        return None
    if field_name == "usd":
        return row["usd_per_day_all_explore_days"]
    if field_name == "mdd":
        return row["mdd_day_usd"]
    return row["wall"]["hits"]


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


def _year_flags_reproduce(lines: Mapping[str, Sequence[S1.Entry]],
                          committed: Mapping[str, Sequence[str]]
                          ) -> tuple[bool, int]:
    """Re-derive sweep 11's own year flags from the reproduced entries."""

    ok = True
    checked = 0
    for name in S11_LINES:
        mine = set(S11.year_flags(_year_block(lines[name])))
        theirs = set(committed[name])
        checked += len(theirs)
        if mine != theirs:
            ok = False
    return ok, checked


def _year_block(entries: Sequence[S1.Entry]) -> dict[str, object]:
    """Sweep 11's ``by_year`` shape, rebuilt from entries so its own
    ``year_flags`` can be re-run against it verbatim."""

    table: dict[str, object] = {}
    for asset in ASSETS:
        for year in sorted({e.d8 // 10000 for e in entries if e.asset == asset}):
            rows = [e for e in entries
                    if e.asset == asset and e.d8 // 10000 == year]
            certs = np.asarray([e.cert_usd for e in rows], np.float64)
            n_days = len({e.d8 for e in rows}) or 1
            table[f"{asset}/{year}"] = {
                "cash": {"trades": len(rows),
                         "usd_per_asset_day": float(certs.sum() / n_days)
                         if len(certs) else 0.0,
                         "walls": int(sum(e.wall for e in rows))},
                "wall_ci": _rate(int(sum(e.wall for e in rows)), len(rows))}
    return {"by_year": table}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--log", action="store_true")
    parser.add_argument("--assets", nargs="*", default=list(ASSETS))
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()

    assets = tuple(args.assets)
    print_decision_table()

    lines, days, gate = reproduce(assets)
    explore = _explore_days(assets)
    flags_ok, flags_n = _year_flags_reproduce(lines, gate["year_flags_committed"])
    gate["year_flags_reproduced"] = bool(flags_ok)
    gate["year_flags_checked"] = int(flags_n)
    if not flags_ok:
        gate["ok"] = False

    report: dict[str, object] = {
        "schema": SCHEMA, "spec": SPEC, "spec_sha": SPEC_SHA,
        "code_sha": code_sha(), "split_sha": S1.split_sha(),
        "outcome_law_sha": S1.outcome_law_sha(), "seed": SEED,
        "family": FAMILY, "parent_trial": PARENT_TRIAL,
        "selection_rule": SELECTION_RULE,
        "tier": "exploratory: a re-cut of existing entries; can kill, cannot promote",
        "mutant": _mutant(), "assets": list(assets),
        "explore_days": {k: len(v) for k, v in explore.items()},
        "reproduction": gate, "variables": {}, "cuts": {}}
    print_reproduction(report)
    if not gate["ok"]:
        report["decision"] = decide(report)
        print_verdict(report)
        OUT_PATH.write_text(json.dumps(report, indent=2, default=_json_default,
                                       sort_keys=True) + "\n")
        raise SweepRefusal("reproduction gate failed; no cut was taken")

    states = day_states(explore)
    coverage: dict[str, object] = {}
    for name in VARIABLES:
        rows: dict[str, object] = {}
        for asset in assets:
            counts: dict[str, int] = {}
            for key, state in states.items():
                if key[0] != asset:
                    continue
                label = state.bins[name]
                counts[label] = counts.get(label, 0) + 1
            rows[asset] = counts
        coverage[name] = rows
    report["variables"] = {"bins": {k: list(v) for k, v in BINS_OF.items()},
                           "day_counts": coverage,
                           "min_prior_days": MIN_PRIOR_DAYS}
    print("\nSTATE COVERAGE  (explore days per bin; UNSCORED is the "
          f"{MIN_PRIOR_DAYS}-day walk-forward warm-up)")
    for name in VARIABLES:
        for asset in assets:
            counts = coverage[name][asset]
            body = "  ".join(f"{b}:{counts.get(b, 0)}"
                             for b in list(BINS_OF[name]) + [UNSCORED])
            print(f"  {name:18s} {asset:4s} {body}")

    for line in LINES:
        block: dict[str, object] = {}
        for asset in assets:
            cuts = {name: cut_line(lines[line], states, asset, name)
                    for name in VARIABLES}
            for name in VARIABLES:
                cuts[name]["flags"] = flags_for(cuts[name])
            table = {name: decisive(lines[line], states, asset, name)
                     for name in VARIABLES}
            n_explore = len(explore[asset])
            picks = {name: gated(lines[line], states, asset, name,
                                 best_bin(cuts[name]), n_explore)
                     for name in VARIABLES}
            width = {name: {b: gated(lines[line], states, asset, name, b,
                                     n_explore)["usd_per_day_all_explore_days"]
                            for b in BINS_OF[name] if b in cuts[name]["bins"]}
                     for name in VARIABLES}
            block[asset] = {
                "cuts": cuts, "decisive": table,
                "separation": {name: list(separation(cuts[name]))
                               for name in VARIABLES},
                "best_variable": best_variable(cuts),
                "gated_best_bin_per_variable": picks,
                "gate_width": {name: {k: (None if v is None else round(v, 1))
                                      for k, v in width[name].items()}
                               for name in VARIABLES},
                "flags": {name: cuts[name]["flags"] for name in VARIABLES}}
        block["coverage_pooled"] = (
            len(lines[line]) / max(1, sum(len(v) for v in explore.values())))
        report["cuts"][line] = block

    print_cuts(report)
    print_decisive(report)
    print_composite(report)
    report["decision"] = decide(report)
    print_verdict(report)

    OUT_PATH.write_text(json.dumps(report, indent=2, default=_json_default,
                                   sort_keys=True) + "\n")
    print(f"\nwrote {OUT_PATH}")
    if args.log:
        written = S1.append_log(log_rows(report))
        print(f"appended {written} rows to {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
