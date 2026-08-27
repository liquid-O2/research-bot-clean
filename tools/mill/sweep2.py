#!/usr/bin/env python3
"""Sweep 2 of the side-resolution mill: the remaining-best side, then a caller.

Exploratory tier.  EXPLORE-day bytes only, can kill, cannot promote.  Sweep 1
(rows sweep1-001..090) proved the enter-now label was the wrong stability
object: Delta(t) = cert(+1,t) - cert(-1,t) decays to noise as t approaches the
phase close, so "first stable" landed at 92-94% of the phase and its oracle
line was crumbs.  This sweep replaces it with the REMAINING-BEST difference.

Per cell and side, on the 60 s lattice::

    REM(s,t) = max over lattice tau >= t of cert(s,tau)      (reverse cummax)
    Delta*(t) = REM(+1,t) - REM(-1,t)

in two variants: UNRESTRICTED (all lattice points) and LEGAL (only lattice
points tau carrying a formed side-s CLEAR candidate by tau).  LEGAL is primary
everywhere.  Where no admissible tau remains, REM is the ``-cost(t)`` sentinel.

Stages, run in order:

  STAGE N  measurements.  N1 the stability map on sign(Delta*), N2 the oracle
           prize under the two-stage law (side at tau, entry on an adverse
           extreme), N3 value-coverage and the measured error budget ON the
           best N2 event line (sweep 1 ran M3/M4 on the crumbs line), N4 the
           relabel of sweep 1's 78 zero-fit detector configs against
           sign(Delta*).
  STAGE F  F6-lite, the first fitted family: 13 causal features, per-day
           walk-forward L2 logistic, selective call at a training-calibrated
           margin with one-bar persistence.  Selected with NO cash.
  STAGE B  three priced policies (P1 caller+EVENT, P2 +F4 gate, P3 EVENT+1),
           the engine replay of P1, and the shared block-permutation null.

Laws carried unchanged from sweep 1 (imported, never re-implemented): the 60 s
completed-bar sampler, the entry convention (declaration at bar close T, entry
quote the last trusted row strictly before T, frozen cost from that row), the
legality check (a formed same-side CLEAR candidate by T), one entry per cell,
seed 20260827, the asset-day block-permutation null with a max-statistic
across priced lines, and the 31-column hypothesis-log row.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
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
from engine.entry_v2.corpus_units import ASSET_RAW_TICK

import mill as M
import sweep1 as S1

# --------------------------------------------------------------------------
# The immutable law this sweep registers before it reads anything.
# --------------------------------------------------------------------------

SPEC = """QRE2MILLSWEEP2
tier=exploratory; explore-only; can kill, cannot promote.  parent=sweep1-090.
carried from sweep 1 unchanged: 60s completed bars, value at close t = last
  trusted row strictly before t; entry convention (declaration at bar close T,
  entry_ts=T, entry quote the last trusted row strictly before T with
  0<bid<ask, frozen cost from that row); legality = a CLEAR candidate with the
  declared side and decision_ts_ns <= T exists in the cell; one entry per cell;
  entries only inside [phase_open, phase_close); seed 20260827.
label: REM(s,t) = max over lattice tau >= t of cert(s,tau), reverse running
  max.  LEGAL variant restricts tau to points with a formed side-s CLEAR
  candidate by tau; UNRESTRICTED uses every lattice point; both drop points
  whose entry is not certifiable.  No admissible tau left => REM = -cost(t).
  Delta*(t) = REM(+1,t) - REM(-1,t).  LEGAL is primary.
ambiguity: |Delta*(t)| <= max(2*cost(t), 100.0) usd is ambiguous; the
  2*cost-only band is reported as sensitivity.  first_stable = earliest
  non-ambiguous t whose sign every later non-ambiguous point repeats; flips =
  sign changes over the non-ambiguous subsequence.
N2 entries at tau in {900,1800,2700,3600}, side = sign(Delta*(tau)):
  AT-TAU enter at tau; EVENT enter at the first bar T >= tau whose bar mid sets
  a new running extreme ADVERSE to the side (s=+1 new running minimum, s=-1 new
  running maximum); EVENT+1 the same but enter at T+1 only when the mid has
  moved >= 4 price ticks back toward s, else keep waiting for the next event.
  Abstain when no qualifying event bar exists at or before phase_close-1800s.
  Legality and certifiability are checked at the actual entry bar.
N3 runs the coverage curves and the error-injection budget on the highest
  usd/day EVENT-family line per asset; adversarial = worst wrong-side cert at
  the same entry; budget = largest rate keeping every rung and MDD<1000.
F6-lite features (13, causal, completed bars only, standardized per fit on the
  training rows): excursion difference U-D in R0 units over 5/15/30/60 min;
  window-mean mid vs phase-open mid and bar mid vs window-mean mid, R0 units,
  15/60 min; candidate new-extreme count difference (long-short) and its
  last-15-min difference; log-seconds since the last new running low minus the
  same for the last new running high; running range / R0; phase fraction.
F6-lite fit: L2 logistic (lambda 1.0, intercept unpenalised, 100 IRLS iters,
  no tuning) per asset per tau in {1800,2700,3600}; walk-forward over that
  asset's chronological EXPLORE days, target day i trained on days < i, at
  least 20 training days, refit per day, labels = sign(Delta*(tau)) LEGAL on
  non-ambiguous cells only.
F6-lite call: |p-0.5| >= m_e with m_e the smallest training margin whose
  training conditional error is <= e, e in {0.01,0.025,0.05,0.10}, and the same
  call repeated at the next completed bar; otherwise abstain.
selection (no cash): CI upper bound <= the N3 adversarial budget if any
  qualifies, else <= the N3 random budget, else min CI upper (BUDGET_FAIL);
  then max coverage; then earliest tau.
nulls: asset-day block permutation of day-sum labels within asset, 200 draws,
  seed 20260827, max-statistic across every priced line.
"""

SCHEMA = "QRE2MILLSWEEP2"
SEED = S1.SEED
BAR_SECONDS = S1.BAR_SECONDS
ASSETS = S1.ASSETS
DAY_RUNG_USD = S1.DAY_RUNG_USD
MDD_CAP_USD = S1.MDD_CAP_USD

AMBIGUITY_FLOOR_USD = 100.0
BANDS = ("max2cost100", "2cost")
VARIANTS = ("legal", "unrestricted")
N1_TAUS = (900, 1800, 2700, 3600)
N2_TAUS = (900, 1800, 2700, 3600)
ENTRY_LAWS = ("AT-TAU", "EVENT", "EVENT+1")
EVENT_DEADLINE_SECONDS = 1800
EVENT_PLUS_TICKS = 4
N3_COVERAGE_GRID = (1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4)
N3_RANDOM_DRAWS = 50
N3_ERROR_RATES = (0.01, 0.02, 0.05, 0.10)
N3_ERROR_SEEDS = 50

FEATURE_NAMES = (
    "exc_d5", "exc_d15", "exc_d30", "exc_d60",
    "disp_open15", "disp_open60", "disp_mean15", "disp_mean60",
    "cand_diff", "cand_diff15", "extreme_age_diff", "range_r0", "phase_frac")
N_FEATURES = 13
EXC_WINDOWS = (5, 15, 30, 60)
DISP_WINDOWS = (15, 60)
CAND_WINDOW = 15
F_TAUS = (1800, 2700, 3600)
E_GRID = (0.01, 0.025, 0.05, 0.10)
MIN_TRAIN_DAYS = 20
RIDGE_LAMBDA = 1.0
IRLS_ITERS = 100
MUTANT_TRAIN_TODAY = "sweep2_train_includes_today"

PARENT_TRIAL = "sweep1-090"
SELECTION_RULE = "n3budget>coverage>earliest_tau"
OUT_PATH = ROOT / ".audit/mill-sweep2.json"
SWEEP1_PATH = ROOT / ".audit/mill-sweep1.json"
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
    """The sweep-2 mutant name, validated against the mill's registry."""

    name = os.environ.get("QRE2_MILL_MUTANT", "")
    if name and name not in M.MUTANTS:
        raise SweepRefusal(f"unknown mill mutant: {name}")
    return name


# --------------------------------------------------------------------------
# The Delta* label plane.
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Star:
    """``Delta*`` and its stability summary for one cell, one variant/band."""

    variant: str
    band: str
    rem_p: np.ndarray
    rem_m: np.ndarray
    delta: np.ndarray
    defined: np.ndarray
    sharp: np.ndarray
    sign: np.ndarray
    first_stable: int
    flips: int
    stable_side: int

    def rem(self, side: int) -> np.ndarray:
        return self.rem_p if int(side) > 0 else self.rem_m


def _reverse_cummax(values: np.ndarray, admissible: np.ndarray,
                    sentinel: np.ndarray) -> np.ndarray:
    """``max`` over lattice points at or after each index, with a sentinel."""

    masked = np.where(admissible, values.astype(np.float64), -np.inf)
    running = np.maximum.accumulate(masked[::-1])[::-1]
    return np.where(np.isneginf(running), sentinel, running)


def rem_side(rec: S1.CellRec, side: int, variant: str) -> np.ndarray:
    """``REM(side, t)`` on the cell lattice for one variant."""

    admissible = np.asarray(rec.ok(side), bool).copy()
    if variant == "legal":
        start = rec.legal_from(side)
        if start < 0:
            admissible[:] = False
        else:
            admissible[:int(start)] = False
    elif variant != "unrestricted":
        raise SweepRefusal(f"unknown REM variant: {variant}")
    return _reverse_cummax(rec.cert(side), admissible, -rec.cost)


def band_width(rec: S1.CellRec, band: str) -> np.ndarray:
    if band == "2cost":
        return 2.0 * rec.cost
    if band == "max2cost100":
        return np.maximum(2.0 * rec.cost, AMBIGUITY_FLOOR_USD)
    raise SweepRefusal(f"unknown ambiguity band: {band}")


def star_cell(rec: S1.CellRec, variant: str = "legal",
              band: str = "max2cost100") -> Star:
    rem_p = rem_side(rec, 1, variant)
    rem_m = rem_side(rec, -1, variant)
    delta = rem_p - rem_m
    defined = np.asarray(rec.bar_ok, bool)
    sharp = defined & (np.abs(delta) > band_width(rec, band))
    sign = np.where(sharp, np.sign(delta), 0.0).astype(np.int64)
    idx = np.flatnonzero(sharp)
    if not len(idx):
        return Star(variant, band, rem_p, rem_m, delta, defined, sharp, sign,
                    -1, 0, 0)
    series = sign[idx]
    flips = int(np.count_nonzero(series[1:] != series[:-1]))
    differs = np.flatnonzero(series != series[-1])
    position = 0 if not len(differs) else int(differs[-1]) + 1
    return Star(variant, band, rem_p, rem_m, delta, defined, sharp, sign,
                int(idx[position]), flips, int(series[-1]))


def stars_for(records: Sequence[S1.CellRec], variant: str = "legal",
              band: str = "max2cost100") -> list[Star]:
    return [star_cell(rec, variant, band) for rec in records]


# --------------------------------------------------------------------------
# Bar geometry the event law and the features share.
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Extremes:
    new_low: np.ndarray
    new_high: np.ndarray


def extremes(rec: S1.CellRec) -> Extremes:
    """New running extremes of the bar mid (sweep 1 ``geometry`` lines 817-819)."""

    b = rec.mid.astype(np.float64)
    run_max = np.maximum.accumulate(b)
    run_min = np.minimum.accumulate(b)
    new_low = np.zeros(len(b), bool)
    new_high = np.zeros(len(b), bool)
    if len(b) > 1:
        new_low[1:] = b[1:] < run_min[:-1]
        new_high[1:] = b[1:] > run_max[:-1]
    return Extremes(new_low, new_high)


def deadline_bar(rec: S1.CellRec) -> int:
    """Last lattice bar at or before ``phase_close - 1800 s``."""

    cutoff = int(rec.phase_close_ts_ns) - EVENT_DEADLINE_SECONDS * NANOS_PER_SECOND
    found = int(np.searchsorted(rec.lat, cutoff, side="right")) - 1
    return min(found, rec.n - 1)


def entry_bar(rec: S1.CellRec, ext: Extremes, side: int, tau_bar: int,
              law: str) -> int:
    """Entry bar under one entry law, or ``-1`` when the cell abstains."""

    if law == "AT-TAU":
        return int(tau_bar) if 1 <= int(tau_bar) < rec.n else -1
    stop = deadline_bar(rec)
    if int(tau_bar) > stop:
        return -1
    adverse = ext.new_low if int(side) > 0 else ext.new_high
    events = np.flatnonzero(adverse[int(tau_bar):stop + 1]) + int(tau_bar)
    if not len(events):
        return -1
    if law == "EVENT":
        return int(events[0])
    if law != "EVENT+1":
        raise SweepRefusal(f"unknown entry law: {law}")
    step = float(EVENT_PLUS_TICKS * 2 * ASSET_RAW_TICK[rec.asset])
    for mark in events:
        nxt = int(mark) + 1
        if nxt >= rec.n:
            break
        if int(side) * (float(rec.mid[nxt]) - float(rec.mid[mark])) >= step:
            return nxt
    return -1


# --------------------------------------------------------------------------
# STAGE N1: the stability map on sign(Delta*).
# --------------------------------------------------------------------------

def _quantiles(values: Sequence[float]) -> dict[str, float]:
    return S1._quantiles(values)


def n1(records: Sequence[S1.CellRec], stars: Sequence[Star],
       days: Mapping[str, int]) -> dict[str, object]:
    out: dict[str, object] = {}
    for asset in ASSETS:
        rows = [(rec, star) for rec, star in zip(records, stars)
                if rec.asset == asset]
        seconds: list[float] = []
        fractions: list[float] = []
        hist = {"0": 0, "1": 0, "2": 0, "3+": 0}
        rem_at_stable: list[float] = []
        agree = {str(tau): [0, 0] for tau in N1_TAUS}
        rem_at_tau: dict[str, list[float]] = {str(tau): [] for tau in N1_TAUS}
        sharp_at_tau = {str(tau): [0, 0] for tau in N1_TAUS}
        no_stable = 0
        for rec, star in rows:
            hist[str(star.flips) if star.flips < 3 else "3+"] += 1
            if star.first_stable < 0:
                no_stable += 1
            else:
                seconds.append(float(rec.seconds(star.first_stable)))
                fractions.append(rec.fraction(star.first_stable))
                rem_at_stable.append(float(
                    star.rem(star.stable_side)[star.first_stable]))
            for tau in N1_TAUS:
                bar = int(tau) // BAR_SECONDS
                key = str(tau)
                if bar >= rec.n:
                    continue
                sharp_at_tau[key][1] += 1
                if not bool(star.sharp[bar]):
                    continue
                sharp_at_tau[key][0] += 1
                if star.stable_side:
                    agree[key][1] += 1
                    agree[key][0] += int(int(star.sign[bar]) == star.stable_side)
                    rem_at_tau[key].append(
                        float(star.rem(star.stable_side)[bar]))
        total = max(1, len(rows))
        out[asset] = {
            "cells": len(rows), "asset_days": int(days.get(asset, 0)),
            "first_stable_seconds": _quantiles(seconds),
            "first_stable_fraction": _quantiles(fractions),
            "flip_histogram": hist,
            "flip_fraction": {key: value / total for key, value in hist.items()},
            "cells_without_stable_side": no_stable,
            "sign_agrees_with_stable": {
                key: {"n": value[1], "agree": value[0],
                      "fraction": (value[0] / value[1]) if value[1] else None}
                for key, value in agree.items()},
            "sharp_rate_at_tau": {
                key: {"n": value[1], "sharp": value[0],
                      "fraction": (value[0] / value[1]) if value[1] else None}
                for key, value in sharp_at_tau.items()},
            "rem_stable_at_first_stable_usd": _quantiles(rem_at_stable),
            "rem_stable_at_tau_usd": {key: _quantiles(value)
                                      for key, value in rem_at_tau.items()},
        }
    return out


# --------------------------------------------------------------------------
# STAGE N2: the oracle prize under the two-stage law.
# --------------------------------------------------------------------------

def n2_entries(records: Sequence[S1.CellRec], stars: Sequence[Star],
               exts: Sequence[Extremes], tau: int, law: str
               ) -> tuple[list[S1.Entry], dict[str, dict[str, object]]]:
    entries: list[S1.Entry] = []
    counts: dict[str, dict[str, object]] = {
        asset: {"cells": 0, "ambiguous": 0, "unavailable": 0, "entered": 0,
                "no_event": 0, "illegal": 0, "delays": []}
        for asset in ASSETS}
    bar = int(tau) // BAR_SECONDS
    for position, (rec, star, ext) in enumerate(zip(records, stars, exts)):
        book = counts[rec.asset]
        book["cells"] += 1
        if bar >= rec.n or not bool(star.defined[bar]):
            book["unavailable"] += 1
            continue
        if not bool(star.sharp[bar]):
            book["ambiguous"] += 1
            continue
        side = int(star.sign[bar])
        target = entry_bar(rec, ext, side, bar, law)
        if target < 0:
            book["no_event"] += 1
            book["unavailable"] += 1
            continue
        entry = S1.make_entry(position, rec, target, side)
        if entry is None:
            book["illegal"] += 1
            book["unavailable"] += 1
            continue
        book["entered"] += 1
        book["delays"].append(float((target - bar) * BAR_SECONDS))
        entries.append(entry)
    return entries, counts


def n2(records: Sequence[S1.CellRec], stars: Sequence[Star],
       exts: Sequence[Extremes], days: Mapping[str, int]
       ) -> tuple[dict[str, object], dict[str, list[S1.Entry]]]:
    cells = S1.cells_by_asset(records)
    out: dict[str, object] = {}
    lines: dict[str, list[S1.Entry]] = {}
    for tau in N2_TAUS:
        for law in ENTRY_LAWS:
            name = f"{tau}/{law}"
            entries, counts = n2_entries(records, stars, exts, tau, law)
            line = S1.cash_line(entries, days, cells)
            for asset in ASSETS:
                book = counts[asset]
                delays = book.pop("delays")
                line[asset].update({
                    "cells": book["cells"], "ambiguous": book["ambiguous"],
                    "unavailable": book["unavailable"],
                    "no_event": book["no_event"], "illegal": book["illegal"],
                    "mean_entry_delay_s": (float(np.mean(delays))
                                           if delays else None),
                    "median_entry_delay_s": (float(np.median(delays))
                                             if delays else None)})
            out[name] = line
            lines[name] = entries
    return out, lines


# --------------------------------------------------------------------------
# STAGE N3: value-coverage and the error budget on the best event line.
# --------------------------------------------------------------------------

def best_event_line(n2_block: Mapping[str, object]) -> dict[str, str]:
    """Per asset, the highest usd/day line among the two event laws."""

    picks: dict[str, str] = {}
    for asset in ASSETS:
        best = None
        for name, line in n2_block.items():
            if name.split("/", 1)[1] not in ("EVENT", "EVENT+1"):
                continue
            value = float(line[asset]["usd_per_asset_day"])
            if best is None or value > best[0]:
                best = (value, name)
        picks[asset] = best[1] if best else ""
    return picks


def coverage_curve(certs: np.ndarray, n_days: int, rung: float
                   ) -> dict[str, dict[str, float]]:
    order = np.argsort(-certs) if len(certs) else np.zeros(0, np.int64)
    table: dict[str, dict[str, float]] = {}
    for coverage in N3_COVERAGE_GRID:
        keep = int(round(coverage * len(certs)))
        top = float(certs[order[:keep]].sum()) if keep else 0.0
        draws = []
        for seed in range(N3_RANDOM_DRAWS):
            if not keep:
                draws.append(0.0)
                continue
            pick = np.random.default_rng(SEED + seed).choice(
                len(certs), size=keep, replace=False)
            draws.append(float(certs[pick].sum()))
        hindsight = top / max(1, n_days)
        random_day = float(np.mean(draws) / max(1, n_days))
        table[f"{coverage:.1f}"] = {
            "entered": keep,
            "hindsight_usd_day": hindsight,
            "hindsight_usd_trade": float(top / keep) if keep else 0.0,
            "random_usd_day": random_day,
            "random_usd_trade": (float(np.mean(draws) / keep) if keep else 0.0),
            "required_entered_mean_usd": (float(rung * n_days / keep) if keep
                                          else float("inf")),
            "hindsight_clears_rung": bool(hindsight >= rung),
            "random_clears_rung": bool(random_day >= rung),
        }
    return table


def error_injection(rows: Sequence[S1.Entry], records: Sequence[S1.CellRec],
                    asset: str, n_days: int) -> dict[str, object]:
    """Sweep 1's M4 machinery, run on this asset's own line."""

    out: dict[str, object] = {"random": {}, "adversarial": {}}
    budget = {"random": 0.0, "adversarial": 0.0}
    for placement in ("random", "adversarial"):
        for rate in N3_ERROR_RATES:
            if not rows:
                out[placement][f"{rate:.2f}"] = {
                    "usd_per_asset_day": 0.0, "mdd_day_usd": 0.0,
                    "flipped": 0, "dropped": 0.0, "holds": False}
                continue
            count = int(round(rate * len(rows)))
            if placement == "adversarial":
                wrong = []
                for position, row in enumerate(rows):
                    other = S1.make_entry(row.cell, records[row.cell], row.bar,
                                          -row.side)
                    wrong.append((float(other.cert_usd) if other is not None
                                  else float("inf"), position))
                wrong.sort()
                picks = [[position for _value, position in wrong][:count]]
            else:
                picks = ([np.random.default_rng(SEED + seed).choice(
                    len(rows), size=count, replace=False).tolist()
                    for seed in range(N3_ERROR_SEEDS)] if count else [[]])
            cash: list[float] = []
            mdds: list[float] = []
            dropped_total = 0
            for pick in picks:
                flipped, dropped = S1._flip_cash(rows, records, pick)
                dropped_total += dropped
                cash.append(sum(row.cert_usd for row in flipped) / max(1, n_days))
                mdds.append(S1.asset_mdd_day(flipped, asset))
            usd = float(np.mean(cash))
            mdd = float(np.mean(mdds))
            holds = bool(usd >= DAY_RUNG_USD[asset] and mdd < MDD_CAP_USD)
            out[placement][f"{rate:.2f}"] = {
                "usd_per_asset_day": usd, "mdd_day_usd": mdd, "flipped": count,
                "dropped": dropped_total / len(picks), "holds": holds}
            if holds:
                budget[placement] = max(budget[placement], rate)
    out["budget"] = budget
    return out


def n3(records: Sequence[S1.CellRec], lines: Mapping[str, list[S1.Entry]],
       n2_block: Mapping[str, object], days: Mapping[str, int]
       ) -> dict[str, object]:
    picks = best_event_line(n2_block)
    out: dict[str, object] = {"line_by_asset": picks, "by_asset": {}}
    for asset in ASSETS:
        name = picks[asset]
        rows = [row for row in lines.get(name, []) if row.asset == asset]
        certs = np.asarray([row.cert_usd for row in rows], np.float64)
        n_days = max(1, int(days.get(asset, 0)))
        rung = DAY_RUNG_USD[asset]
        table = coverage_curve(certs, n_days, rung)
        clearing = [float(key) for key, value in table.items()
                    if value["hindsight_clears_rung"]]
        out["by_asset"][asset] = {
            "line": name, "entered_cells": int(len(certs)), "asset_days": n_days,
            "day_rung_usd": rung,
            "base_usd_per_asset_day": float(certs.sum() / n_days) if len(certs) else 0.0,
            "base_mdd_day_usd": S1.asset_mdd_day(rows, asset),
            "coverage_table": table,
            "min_clearing_coverage": (min(clearing) if clearing else None),
            "error_injection": error_injection(rows, records, asset, n_days),
        }
    out["budget_by_asset"] = {
        asset: out["by_asset"][asset]["error_injection"]["budget"]
        for asset in ASSETS}
    return out


# --------------------------------------------------------------------------
# STAGE N4: sweep 1's 78 zero-fit detectors, relabelled against Delta*.
# --------------------------------------------------------------------------

def n4(records: Sequence[S1.CellRec], stars_legal: Sequence[Star],
       stars_unres: Sequence[Star]) -> dict[str, object]:
    geos = [S1.geometry(rec) for rec in records]
    cells = S1.cells_by_asset(records)
    report: dict[str, object] = {"families": {}, "flagged_below_0.45": []}
    for family in S1.FAMILIES:
        rows: dict[str, dict[str, object]] = {}
        for params in S1.family_grid(family):
            key = S1.config_key(family, params)
            per_asset: dict[str, dict[str, object]] = {}
            for asset in ASSETS:
                declared = legal = 0
                hits = total = 0
                un_hits = un_total = 0
                bars: list[float] = []
                for rec, geo, star, un in zip(records, geos, stars_legal,
                                              stars_unres):
                    if rec.asset != asset:
                        continue
                    call = S1.declare(family, rec, geo, params)
                    if call is None:
                        continue
                    declared += 1
                    if not rec.legal_at(call.side, call.bar):
                        continue
                    legal += 1
                    bars.append(float(rec.seconds(call.bar)))
                    if bool(star.sharp[call.bar]):
                        total += 1
                        hits += int(int(star.sign[call.bar]) != call.side)
                    if bool(un.sharp[call.bar]):
                        un_total += 1
                        un_hits += int(int(un.sign[call.bar]) != call.side)
                low, high = S1.wilson(hits, total)
                un_low, un_high = S1.wilson(un_hits, un_total)
                per_asset[asset] = {
                    "cells": cells.get(asset, 0), "declared": declared,
                    "legal": legal, "coverage": legal / max(1, cells.get(asset, 1)),
                    "delay_median_s": float(np.median(bars)) if bars else None,
                    "error_legal": (hits / total) if total else None,
                    "n_legal": total, "ci95_legal": [low, high],
                    "error_unrestricted": (un_hits / un_total) if un_total else None,
                    "n_unrestricted": un_total, "ci95_unrestricted": [un_low, un_high],
                }
            errors = [per_asset[a]["error_legal"] for a in ASSETS]
            uppers = [per_asset[a]["ci95_legal"][1] for a in ASSETS]
            rows[key] = {
                "params": list(params), "by_asset": per_asset,
                "max_asset_error_legal": max((e if e is not None else 1.0)
                                             for e in errors),
                "min_asset_error_legal": min((e if e is not None else 1.0)
                                             for e in errors),
                "max_asset_ci_upper_legal": max(uppers),
                "all_assets_ci_upper_below_0.45": bool(all(u < 0.45 for u in uppers)),
            }
            if rows[key]["all_assets_ci_upper_below_0.45"]:
                report["flagged_below_0.45"].append(f"{family}/{key}")
        ordered = sorted(rows.items(),
                         key=lambda item: (item[1]["max_asset_error_legal"],
                                           item[0]))
        report["families"][family] = {
            "configs": rows, "ordered": [key for key, _row in ordered][:12]}
    return report


# --------------------------------------------------------------------------
# STAGE F: F6-lite features, walk-forward fit, selective call.
# --------------------------------------------------------------------------

def _roll_extreme(values: np.ndarray, window: int, kind: str) -> np.ndarray:
    pad = np.full(window, -np.inf if kind == "max" else np.inf)
    view = np.lib.stride_tricks.sliding_window_view(
        np.concatenate([pad, values]), window + 1)
    return view.max(axis=1) if kind == "max" else view.min(axis=1)


def _roll_mean(values: np.ndarray, window: int) -> np.ndarray:
    cumulative = np.concatenate([[0.0], np.cumsum(values)])
    order = np.arange(len(values), dtype=np.int64)
    start = np.maximum(0, order - window)
    return (cumulative[order + 1] - cumulative[start]) / (order + 1 - start)


def _lagged(values: np.ndarray, window: int) -> np.ndarray:
    order = np.arange(len(values), dtype=np.int64)
    return values[np.maximum(0, order - window)]


def feature_matrix(rec: S1.CellRec) -> np.ndarray:
    """The 13 causal features on every lattice bar of one cell."""

    b = rec.mid.astype(np.float64)
    n = len(b)
    r0 = float(rec.r0_mid2)
    columns: list[np.ndarray] = []
    for window in EXC_WINDOWS:
        base = _lagged(b, window)
        up = (_roll_extreme(b, window, "max") - base) / r0
        down = (base - _roll_extreme(b, window, "min")) / r0
        columns.append(up - down)
    for window in DISP_WINDOWS:
        columns.append((_roll_mean(b, window) - b[0]) / r0)
    for window in DISP_WINDOWS:
        columns.append((b - _roll_mean(b, window)) / r0)
    diff = (rec.cum_long.astype(np.float64) - rec.cum_short.astype(np.float64))
    columns.append(diff)
    columns.append(diff - _lagged(diff, CAND_WINDOW))
    ext = extremes(rec)
    order = np.arange(n, dtype=np.int64)
    last_low = np.maximum.accumulate(np.where(ext.new_low, order, 0))
    last_high = np.maximum.accumulate(np.where(ext.new_high, order, 0))
    age_low = (order - last_low).astype(np.float64) * BAR_SECONDS
    age_high = (order - last_high).astype(np.float64) * BAR_SECONDS
    columns.append(np.log1p(age_low) - np.log1p(age_high))
    run_max = np.maximum.accumulate(b)
    run_min = np.minimum.accumulate(b)
    columns.append((run_max - run_min) / r0)
    span = max(1.0, float(rec.phase_close_ts_ns - rec.phase_open_ts_ns))
    columns.append((rec.lat.astype(np.float64) - float(rec.phase_open_ts_ns)) / span)
    matrix = np.column_stack(columns)
    if matrix.shape[1] != N_FEATURES:
        raise SweepRefusal(
            f"feature count is {matrix.shape[1]}, the spec fixes {N_FEATURES}")
    return np.nan_to_num(matrix, nan=0.0, posinf=0.0, neginf=0.0)


def irls_logistic(design: np.ndarray, labels: np.ndarray,
                  lam: float = RIDGE_LAMBDA, iters: int = IRLS_ITERS
                  ) -> np.ndarray | None:
    """Plain numpy IRLS for L2 logistic regression; intercept unpenalised."""

    rows, width = design.shape
    if rows < 2 or len(np.unique(labels)) < 2:
        return None
    x = np.column_stack([np.ones(rows), design])
    beta = np.zeros(width + 1)
    penalty = np.eye(width + 1) * (2.0 * lam)
    penalty[0, 0] = 0.0
    for _step in range(iters):
        eta = np.clip(x @ beta, -30.0, 30.0)
        p = 1.0 / (1.0 + np.exp(-eta))
        weights = np.maximum(p * (1.0 - p), 1e-9)
        hessian = x.T @ (x * weights[:, None]) + penalty + np.eye(width + 1) * 1e-9
        gradient = x.T @ (labels - p) - penalty @ beta
        try:
            step = np.linalg.solve(hessian, gradient)
        except np.linalg.LinAlgError:
            return None
        beta = beta + step
        if float(np.max(np.abs(step))) < 1e-10:
            break
    return beta


def predict(beta: np.ndarray, design: np.ndarray) -> np.ndarray:
    x = np.column_stack([np.ones(len(design)), design])
    return 1.0 / (1.0 + np.exp(-np.clip(x @ beta, -30.0, 30.0)))


def calibrate_margin(margins: np.ndarray, wrong: np.ndarray, target: float
                     ) -> float:
    """Smallest training margin whose conditional error is <= ``target``."""

    if not len(margins):
        return float("inf")
    best = float("inf")
    for value in np.unique(margins):
        called = margins >= value
        if not bool(called.any()):
            continue
        if float(wrong[called].mean()) <= target:
            best = float(value)
            break
    return best


def walk_forward(x_tau: np.ndarray, x_next: np.ndarray, y: np.ndarray,
                 day_of_row: np.ndarray, days_sorted: Sequence[int],
                 *, min_train_days: int = MIN_TRAIN_DAYS
                 ) -> dict[str, object]:
    """Per-day refit, calibrate, and selective call.  ``y`` in {0,1}.

    ``QRE2_MILL_MUTANT=sweep2_train_includes_today`` puts the target day into
    its own training set; every other line of this function is untouched, so a
    planted day-local leak collapses the test error only under the mutant.
    """

    mutant = _sweep_mutant() == MUTANT_TRAIN_TODAY
    rows = len(y)
    scored = np.zeros(rows, bool)
    called = {e: np.zeros(rows, bool) for e in E_GRID}
    predicted = {e: np.zeros(rows, np.int64) for e in E_GRID}
    margins_used: dict[float, list[float]] = {e: [] for e in E_GRID}
    fits = 0
    fit_failures = 0
    self_in_train = 0
    train_days_used: list[int] = []
    for position, day in enumerate(days_sorted):
        if position < int(min_train_days):
            continue
        prior = set(int(value) for value in days_sorted[:position])
        if mutant:
            prior.add(int(day))
        self_in_train += int(int(day) in prior)
        test = day_of_row == int(day)
        if not bool(test.any()):
            continue
        train = np.asarray([int(value) in prior for value in day_of_row], bool)
        if int(train.sum()) < 2:
            continue
        fits += 1
        train_days_used.append(len(prior))
        centre = x_tau[train].mean(axis=0)
        spread = np.maximum(x_tau[train].std(axis=0), 1e-12)
        beta = irls_logistic((x_tau[train] - centre) / spread, y[train])
        if beta is None:
            fit_failures += 1
            continue
        scored |= test
        p_train = predict(beta, (x_tau[train] - centre) / spread)
        train_margin = np.abs(p_train - 0.5)
        train_wrong = ((p_train >= 0.5).astype(np.int64)
                       != y[train].astype(np.int64)).astype(np.float64)
        p_tau = predict(beta, (x_tau[test] - centre) / spread)
        p_next = predict(beta, (x_next[test] - centre) / spread)
        side_tau = np.where(p_tau >= 0.5, 1, -1)
        side_next = np.where(p_next >= 0.5, 1, -1)
        margin_tau = np.abs(p_tau - 0.5)
        margin_next = np.abs(p_next - 0.5)
        index = np.flatnonzero(test)
        for e in E_GRID:
            margin = calibrate_margin(train_margin, train_wrong, e)
            margins_used[e].append(margin)
            if not np.isfinite(margin):
                continue
            fire = ((margin_tau >= margin) & (margin_next >= margin)
                    & (side_tau == side_next))
            called[e][index[fire]] = True
            predicted[e][index[fire]] = side_tau[fire]
    return {"scored": scored, "called": called, "predicted": predicted,
            "fits": fits, "fit_failures": fit_failures,
            "self_in_train": self_in_train,
            "margins": {e: [value for value in margins_used[e]
                            if np.isfinite(value)] for e in E_GRID},
            "infinite_margins": {e: int(sum(1 for value in margins_used[e]
                                            if not np.isfinite(value)))
                                 for e in E_GRID},
            "train_days_median": (float(np.median(train_days_used))
                                  if train_days_used else None)}


@dataclass(frozen=True, slots=True)
class FDataset:
    cell: np.ndarray          # index into the record list
    day: np.ndarray
    x_tau: np.ndarray
    x_next: np.ndarray
    y: np.ndarray             # 1 for side +1
    label_side: np.ndarray
    delta: np.ndarray
    bar: int
    ambiguous: int
    short: int


def f_dataset(records: Sequence[S1.CellRec], stars: Sequence[Star],
              features: Sequence[np.ndarray], asset: str, tau: int) -> FDataset:
    bar = int(tau) // BAR_SECONDS
    cell: list[int] = []
    day: list[int] = []
    x_tau: list[np.ndarray] = []
    x_next: list[np.ndarray] = []
    label: list[int] = []
    delta: list[float] = []
    ambiguous = 0
    short = 0
    for position, (rec, star) in enumerate(zip(records, stars)):
        if rec.asset != asset:
            continue
        if bar + 1 >= rec.n or not bool(star.defined[bar]):
            short += 1
            continue
        if not bool(star.sharp[bar]):
            ambiguous += 1
            continue
        cell.append(position)
        day.append(int(rec.d8))
        x_tau.append(features[position][bar])
        x_next.append(features[position][bar + 1])
        label.append(int(star.sign[bar]))
        delta.append(float(star.delta[bar]))
    empty = np.zeros((0, N_FEATURES), np.float64)
    sides = np.asarray(label, np.int64)
    return FDataset(
        np.asarray(cell, np.int64), np.asarray(day, np.int64),
        np.asarray(x_tau, np.float64) if x_tau else empty,
        np.asarray(x_next, np.float64) if x_next else empty,
        (sides > 0).astype(np.float64), sides,
        np.asarray(delta, np.float64), bar, ambiguous, short)


def stage_f(records: Sequence[S1.CellRec], stars: Sequence[Star],
            features: Sequence[np.ndarray], explore_days: Mapping[str, list[int]],
            budgets: Mapping[str, Mapping[str, float]]) -> dict[str, object]:
    report: dict[str, object] = {
        "features": list(FEATURE_NAMES), "n_features": N_FEATURES,
        "min_train_days": MIN_TRAIN_DAYS, "lambda": RIDGE_LAMBDA,
        "irls_iters": IRLS_ITERS, "by_asset": {}, "selection": {}}
    datasets: dict[tuple[str, int], FDataset] = {}
    calls: dict[tuple[str, int, float], dict[str, np.ndarray]] = {}
    for asset in ASSETS:
        block: dict[str, object] = {}
        for tau in F_TAUS:
            data = f_dataset(records, stars, features, asset, tau)
            datasets[(asset, tau)] = data
            result = walk_forward(data.x_tau, data.x_next, data.y, data.day,
                                  explore_days[asset])
            scored = result["scored"]
            for e in E_GRID:
                calls[(asset, tau, e)] = {
                    "scored": scored,
                    "called": result["called"][e] & scored,
                    "predicted": result["predicted"][e]}
            rows: dict[str, object] = {
                "non_ambiguous_cells": int(len(data.y)),
                "ambiguous_cells": data.ambiguous,
                "cells_without_two_bars": data.short,
                "scored_cells": int(scored.sum()),
                "fits": result["fits"], "fit_failures": result["fit_failures"],
                "train_days_median": result["train_days_median"],
                "by_e": {}}
            for e in E_GRID:
                called = result["called"][e] & scored
                predicted = result["predicted"][e]
                wrong = int(np.sum(called & (predicted != data.label_side)))
                total = int(called.sum())
                low, high = S1.wilson(wrong, total)
                abstained = scored & ~called
                margins = result["margins"][e]
                rows["by_e"][f"{e:.3f}"] = {
                    "called": total,
                    "coverage": total / max(1, int(scored.sum())),
                    "error": (wrong / total) if total else None,
                    "errors": wrong, "ci95": [low, high],
                    "mean_abs_delta_called_usd": (
                        float(np.abs(data.delta[called]).mean()) if total else None),
                    "mean_abs_delta_abstained_usd": (
                        float(np.abs(data.delta[abstained]).mean())
                        if int(abstained.sum()) else None),
                    "median_margin": (float(np.median(margins)) if margins
                                      else None),
                    "days_without_margin": result["infinite_margins"][e],
                }
            block[str(tau)] = rows
        report["by_asset"][asset] = block
    for asset in ASSETS:
        report["selection"][asset] = select_config(
            report["by_asset"][asset], budgets[asset])
    report["_datasets"] = datasets
    report["_calls"] = calls
    return report


def select_config(block: Mapping[str, object], budget: Mapping[str, float]
                  ) -> dict[str, object]:
    """No cash: N3 budget compliance, then max coverage, then earliest tau."""

    pool = [(tau, e, block[str(tau)]["by_e"][f"{e:.3f}"])
            for tau in F_TAUS for e in E_GRID]
    live = [(tau, e, row) for tau, e, row in pool if row["called"] > 0]
    flags: list[str] = []
    chosen = None
    for placement in ("adversarial", "random"):
        limit = float(budget.get(placement, 0.0))
        if limit <= 0.0:
            continue
        qualify = [(tau, e, row) for tau, e, row in live
                   if row["ci95"][1] <= limit]
        if qualify:
            chosen = sorted(qualify, key=lambda item: (-item[2]["coverage"],
                                                       item[0], item[1]))[0]
            flags.append(f"budget={placement}:{limit:.2f}")
            break
    if chosen is None:
        flags.append("BUDGET_FAIL")
        if not live:
            return {"tau": None, "e": None, "flags": flags + ["NO_CALLS"],
                    "budget": dict(budget)}
        chosen = sorted(live, key=lambda item: (item[2]["ci95"][1],
                                                -item[2]["coverage"],
                                                item[0], item[1]))[0]
    tau, e, row = chosen
    return {"tau": int(tau), "e": float(e), "flags": flags,
            "budget": dict(budget), "coverage": row["coverage"],
            "error": row["error"], "ci95": row["ci95"], "called": row["called"]}


# --------------------------------------------------------------------------
# STAGE B: the priced policies.
# --------------------------------------------------------------------------

def policy_entries(records: Sequence[S1.CellRec], exts: Sequence[Extremes],
                   selection: Mapping[str, Mapping[str, object]],
                   datasets: Mapping[tuple[str, int], FDataset],
                   calls: Mapping[tuple[str, int, float], dict[str, np.ndarray]],
                   law: str, gate: Mapping[str, float] | None = None
                   ) -> tuple[list[S1.Entry], dict[str, dict[str, int]]]:
    geos = {}
    entries: list[S1.Entry] = []
    counts = {asset: {"called": 0, "gated": 0, "no_event": 0, "illegal": 0,
                      "entered": 0} for asset in ASSETS}
    for asset in ASSETS:
        pick = selection[asset]
        if pick.get("tau") is None:
            continue
        tau = int(pick["tau"])
        e = float(pick["e"])
        data = datasets[(asset, tau)]
        call = calls[(asset, tau, e)]
        book = counts[asset]
        for row in np.flatnonzero(call["called"]):
            position = int(data.cell[row])
            rec = records[position]
            side = int(call["predicted"][row])
            if side not in (1, -1):
                continue
            book["called"] += 1
            if gate is not None:
                if position not in geos:
                    geos[position] = S1.geometry(rec)
                if float(geos[position].rng[data.bar]) < float(gate[asset]):
                    book["gated"] += 1
                    continue
            target = entry_bar(rec, exts[position], side, data.bar, law)
            if target < 0:
                book["no_event"] += 1
                continue
            entry = S1.make_entry(position, rec, target, side)
            if entry is None:
                book["illegal"] += 1
                continue
            book["entered"] += 1
            entries.append(entry)
    return entries, counts


def scored_days(datasets: Mapping[tuple[str, int], FDataset],
                calls: Mapping[tuple[str, int, float], dict[str, np.ndarray]],
                selection: Mapping[str, Mapping[str, object]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for asset in ASSETS:
        pick = selection[asset]
        if pick.get("tau") is None:
            out[asset] = 0
            continue
        data = datasets[(asset, int(pick["tau"]))]
        mask = calls[(asset, int(pick["tau"]), float(pick["e"]))]["scored"]
        out[asset] = int(len(set(int(day) for day in data.day[mask])))
    return out


def stage_b(records: Sequence[S1.CellRec], exts: Sequence[Extremes],
            days: Mapping[str, int], explore_days: Mapping[str, list[int]],
            f_report: Mapping[str, object],
            calls: Mapping[tuple[str, int, float], dict[str, np.ndarray]]
            ) -> dict[str, object]:
    cells = S1.cells_by_asset(records)
    gate = S1.r0_gate(records)
    selection = f_report["selection"]
    datasets = f_report["_datasets"]
    sweep1_gate = json.loads(SWEEP1_PATH.read_text())["stage_b"][
        "r0_median_gate_mid2"]
    report: dict[str, object] = {
        "r0_median_gate_mid2": gate,
        "r0_gate_matches_sweep1": {asset: bool(
            abs(float(gate[asset]) - float(sweep1_gate[asset])) < 1e-6)
            for asset in ASSETS},
        "scored_days": scored_days(datasets, calls, selection),
        "policies": {}}
    priced: dict[str, list[S1.Entry]] = {}
    plan = (("P1", "EVENT", None), ("P2", "EVENT", gate), ("P3", "EVENT+1", None))
    for name, law, gate_used in plan:
        entries, counts = policy_entries(records, exts, selection, datasets,
                                         calls, law, gate_used)
        priced[name] = entries
        line = S1.cash_line(entries, days, cells)
        for asset in ASSETS:
            n_scored = max(1, report["scored_days"][asset])
            rows = [row for row in entries if row.asset == asset]
            line[asset].update({
                "usd_per_scored_day": float(
                    sum(row.cert_usd for row in rows) / n_scored),
                "scored_days": report["scored_days"][asset],
                **{f"skip_{key}": value for key, value in counts[asset].items()}})
        block: dict[str, object] = {
            "law": law, "gate": (dict(gate_used) if gate_used else None),
            "by_asset": line, "line_name": name}
        if name == "P1":
            block["replay"] = S1.replay_line(
                entries, records, f"mill-sweep2:{code_sha()[:16]}:P1")
        report["policies"][name] = block
    report["nulls"] = S1.block_null(priced, explore_days)
    return report


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
        "days": sum(report["stage_n"]["asset_days"].values()),
    }
    column = {"HG": "err_rate_hg", "NKD": "err_rate_nkd", "SI": "err_rate_si"}
    rows: list[dict[str, object]] = []
    counter = 0
    stage = report["stage_f"]
    for asset in ASSETS:
        pick = stage["selection"][asset]
        for tau in F_TAUS:
            block = stage["by_asset"][asset][str(tau)]
            for e in E_GRID:
                entry = block["by_e"][f"{e:.3f}"]
                counter += 1
                mark = ("SELECTED" if (pick.get("tau") == tau
                                       and pick.get("e") == e) else "")
                rows.append({
                    **shared, "id": f"sweep2-{counter:03d}", "family": "F6-LITE",
                    "rule": f"{asset}/tau{tau}/e{e:g}",
                    "params": json.dumps([asset, tau, e]),
                    "coverage": entry["coverage"], "delay_med_s": tau,
                    column[asset]: entry["error"],
                    "note": (f"stage-F no-cash;ci={entry['ci95'][1]:.3f}"
                             + (f";{mark}" if mark else ""))[:60]})
    if "stage_b" not in report:
        return rows
    nulls = report["stage_b"]["nulls"]["by_line"]
    for name, block in sorted(report["stage_b"]["policies"].items()):
        counter += 1
        cash = block["by_asset"]
        null = nulls.get(name, {})
        skips = ""
        if block.get("replay", {}).get("status") == "OK":
            skips = block["replay"]["occupancy_or_cap_skips"]
        picks = ";".join(f"{a}:{report['stage_f']['selection'][a].get('tau')}"
                         for a in ASSETS)
        rows.append({
            **shared, "id": f"sweep2-{counter:03d}", "family": "F6-LITE",
            "rule": name,
            "params": json.dumps({a: [report["stage_f"]["selection"][a].get("tau"),
                                      report["stage_f"]["selection"][a].get("e")]
                                  for a in ASSETS}),
            "coverage": float(np.mean([cash[a]["coverage"] for a in ASSETS])),
            "delay_med_s": None,
            "err_rate_hg": report["stage_f"]["selection"]["HG"].get("error"),
            "err_rate_nkd": report["stage_f"]["selection"]["NKD"].get("error"),
            "err_rate_si": report["stage_f"]["selection"]["SI"].get("error"),
            "walls_hg": cash["HG"]["walls"], "walls_nkd": cash["NKD"]["walls"],
            "walls_si": cash["SI"]["walls"],
            "hg_usd_day": cash["HG"]["usd_per_asset_day"],
            "nkd_usd_day": cash["NKD"]["usd_per_asset_day"],
            "si_usd_day": cash["SI"]["usd_per_asset_day"],
            "mdd_hg": cash["HG"]["mdd_day_usd"],
            "mdd_nkd": cash["NKD"]["mdd_day_usd"],
            "mdd_si": cash["SI"]["mdd_day_usd"],
            "replay_skips": skips, "null_margin": null.get("p_max_adjusted"),
            "note": f"stage-B {block['law']};tau {picks}"[:60]})
    return rows


# --------------------------------------------------------------------------
# Report I/O and printing.
# --------------------------------------------------------------------------

def read_report() -> dict[str, object]:
    if OUT_PATH.is_file():
        return json.loads(OUT_PATH.read_text())
    return {"schema": SCHEMA, "tier": "exploratory",
            "claim": "EXPLORE-day sweep 2; can kill, cannot promote"}


def write_report(report: Mapping[str, object]) -> None:
    payload = {key: value for key, value in report.items()
               if not key.startswith("_")}
    if "stage_f" in payload:
        payload["stage_f"] = {key: value
                              for key, value in payload["stage_f"].items()
                              if not key.startswith("_")}
    OUT_PATH.write_text(json.dumps(payload, sort_keys=True, indent=1,
                                   default=S1._json_default) + "\n")


def _num(value: object, width: int = 8, digits: int = 2) -> str:
    return S1._num(value, width, digits)


def print_n1(block: Mapping[str, object], band: str) -> None:
    print(f"\n== N1 stability on sign(Delta*) [LEGAL, band={band}]")
    print(f"{'asset':5s} {'cells':>6s} {'fs_p25':>8s} {'fs_p50':>8s} "
          f"{'fs_p75':>8s} {'frac25':>7s} {'frac50':>7s} {'frac75':>7s} "
          f"{'f0':>6s} {'f1':>6s} {'f2':>6s} {'f3+':>6s} {'nostab':>7s}")
    for asset in ASSETS:
        row = block[asset]
        sec, frac, hist = (row["first_stable_seconds"],
                           row["first_stable_fraction"], row["flip_fraction"])
        print(f"{asset:5s} {row['cells']:6d} {_num(sec.get('p25'))} "
              f"{_num(sec.get('p50'))} {_num(sec.get('p75'))} "
              f"{_num(frac.get('p25'), 7, 3)} {_num(frac.get('p50'), 7, 3)} "
              f"{_num(frac.get('p75'), 7, 3)} {_num(hist['0'], 6, 3)} "
              f"{_num(hist['1'], 6, 3)} {_num(hist['2'], 6, 3)} "
              f"{_num(hist['3+'], 6, 3)} {row['cells_without_stable_side']:7d}")
    print(f"  {'asset':5s} {'tau':>5s} {'sharp':>7s} {'n_sharp':>8s} "
          f"{'agree':>7s} {'n_agree':>8s} {'REM_p25':>9s} {'REM_p50':>9s} "
          f"{'REM_p75':>9s}")
    for asset in ASSETS:
        row = block[asset]
        for tau in N1_TAUS:
            key = str(tau)
            sharp = row["sharp_rate_at_tau"][key]
            agree = row["sign_agrees_with_stable"][key]
            rem = row["rem_stable_at_tau_usd"][key]
            print(f"  {asset:5s} {tau:5d} {_num(sharp['fraction'], 7, 3)} "
                  f"{sharp['n']:8d} {_num(agree['fraction'], 7, 3)} "
                  f"{agree['n']:8d} {_num(rem.get('p25'), 9, 1)} "
                  f"{_num(rem.get('p50'), 9, 1)} {_num(rem.get('p75'), 9, 1)}")
        rem = row["rem_stable_at_first_stable_usd"]
        print(f"  {asset:5s} {'@fs':>5s} {'':7s} {rem.get('n', 0):8d} {'':7s} "
              f"{'':8s} {_num(rem.get('p25'), 9, 1)} "
              f"{_num(rem.get('p50'), 9, 1)} {_num(rem.get('p75'), 9, 1)}")


def print_n2(block: Mapping[str, object]) -> None:
    print("\n== N2 oracle prize, two-stage law (labelled oracle side, legal entries)")
    print(f"{'line':16s} {'asset':5s} {'cells':>6s} {'ent':>5s} {'amb':>5s} "
          f"{'unav':>5s} {'noev':>5s} {'cov':>6s} {'usd/day':>10s} "
          f"{'usd/trd':>9s} {'win':>6s} {'wall':>6s} {'mdd_day':>9s} "
          f"{'mdd_trd':>9s} {'dly_s':>7s} {'rung':>4s}")
    for name, line in block.items():
        for asset in ASSETS:
            row = line[asset]
            print(f"{name:16s} {asset:5s} {row['cells']:6d} {row['trades']:5d} "
                  f"{row['ambiguous']:5d} {row['unavailable']:5d} "
                  f"{row['no_event']:5d} {_num(row['coverage'], 6, 3)} "
                  f"{_num(row['usd_per_asset_day'], 10, 1)} "
                  f"{_num(row['usd_per_trade'], 9, 1)} "
                  f"{_num(row['win_rate'], 6, 3)} {_num(row['wall_rate'], 6, 3)} "
                  f"{_num(row['mdd_day_usd'], 9, 0)} "
                  f"{_num(row['mdd_trade_usd'], 9, 0)} "
                  f"{_num(row['mean_entry_delay_s'], 7, 0)} "
                  f"{'Y' if row['clears_rung'] else 'n':>4s}")


def print_n3(block: Mapping[str, object]) -> None:
    print("\n== N3 value-coverage and error budget on the best EVENT line per asset")
    print(f"  lines: {block['line_by_asset']}")
    print(f"  {'asset':5s} {'line':16s} {'cov':>5s} {'n':>5s} {'hind$/day':>10s} "
          f"{'hind$/trd':>10s} {'rand$/day':>10s} {'need$/trd':>10s} {'clr':>4s}")
    for asset in ASSETS:
        row = block["by_asset"][asset]
        for coverage in N3_COVERAGE_GRID:
            cell = row["coverage_table"][f"{coverage:.1f}"]
            print(f"  {asset:5s} {row['line']:16s} {coverage:5.1f} "
                  f"{cell['entered']:5d} {_num(cell['hindsight_usd_day'], 10, 1)} "
                  f"{_num(cell['hindsight_usd_trade'], 10, 1)} "
                  f"{_num(cell['random_usd_day'], 10, 1)} "
                  f"{_num(cell['required_entered_mean_usd'], 10, 1)} "
                  f"{'Y' if cell['hindsight_clears_rung'] else 'n':>4s}")
        print(f"  {asset}: rung={row['day_rung_usd']:.0f}/day base="
              f"{row['base_usd_per_asset_day']:.1f}/day mdd="
              f"{row['base_mdd_day_usd']:.0f} min clearing coverage="
              f"{row['min_clearing_coverage']}")
    print(f"\n  {'asset':5s} {'place':12s} {'rate':>5s} {'flip':>5s} "
          f"{'usd/day':>10s} {'mdd_day':>9s} {'rung':>5s} {'mdd<1k':>7s}")
    for asset in ASSETS:
        injection = block["by_asset"][asset]["error_injection"]
        for placement in ("random", "adversarial"):
            for rate in N3_ERROR_RATES:
                row = injection[placement][f"{rate:.2f}"]
                print(f"  {asset:5s} {placement:12s} {rate:5.2f} "
                      f"{int(row['flipped']):5d} "
                      f"{_num(row['usd_per_asset_day'], 10, 1)} "
                      f"{_num(row['mdd_day_usd'], 9, 0)} "
                      f"{'Y' if row['usd_per_asset_day'] >= DAY_RUNG_USD[asset] else 'n':>5s} "
                      f"{'Y' if row['mdd_day_usd'] < MDD_CAP_USD else 'n':>7s}")
    print(f"  budget by asset (largest rate keeping rung AND mdd<1000): "
          f"{ {a: block['budget_by_asset'][a] for a in ASSETS} }")


def print_n4(block: Mapping[str, object], top: int = 5) -> None:
    print("\n== N4 sweep-1 detectors relabelled against sign(Delta*) (no cash)")
    for family in S1.FAMILIES:
        rows = block["families"][family]
        print(f"\n-- {family}  configs={len(rows['configs'])} "
              f"(top {top} by max-asset error, LEGAL label)")
        print(f"  {'rule':16s} {'cov':>6s} {'dly_s':>7s} "
              f"{'eL_HG':>6s} {'eL_NKD':>6s} {'eL_SI':>6s} "
              f"{'ciU_HG':>7s} {'ciU_NKD':>7s} {'ciU_SI':>7s} "
              f"{'eU_HG':>6s} {'eU_NKD':>6s} {'eU_SI':>6s} {'n_HG':>5s}")
        for key in rows["ordered"][:top]:
            entry = rows["configs"][key]
            per = entry["by_asset"]
            print(f"  {key:16s} "
                  f"{_num(np.mean([per[a]['coverage'] for a in ASSETS]), 6, 3)} "
                  f"{_num(np.median([per[a]['delay_median_s'] or 0.0 for a in ASSETS]), 7, 0)} "
                  + " ".join(_num(per[a]["error_legal"], 6, 3) for a in ASSETS)
                  + " "
                  + " ".join(_num(per[a]["ci95_legal"][1], 7, 3) for a in ASSETS)
                  + " "
                  + " ".join(_num(per[a]["error_unrestricted"], 6, 3)
                             for a in ASSETS)
                  + f" {per['HG']['n_legal']:5d}")
    flagged = block["flagged_below_0.45"]
    print(f"\n  configs with CI upper < 0.45 on EVERY asset: "
          f"{flagged if flagged else 'NONE'}")


def print_stage_f(report: Mapping[str, object]) -> None:
    print("\n== STAGE F  F6-lite selective caller (walk-forward, no cash)")
    print(f"  features={N_FEATURES} lambda={RIDGE_LAMBDA} iters={IRLS_ITERS} "
          f"min_train_days={MIN_TRAIN_DAYS}")
    print(f"  {'asset':5s} {'tau':>5s} {'e':>6s} {'nonamb':>7s} {'scored':>7s} "
          f"{'called':>7s} {'cov':>6s} {'err':>6s} {'ciL':>6s} {'ciU':>6s} "
          f"{'|D*|call':>9s} {'|D*|abst':>9s} {'margin':>7s} {'nomarg':>7s}")
    for asset in ASSETS:
        for tau in F_TAUS:
            block = report["by_asset"][asset][str(tau)]
            for e in E_GRID:
                row = block["by_e"][f"{e:.3f}"]
                print(f"  {asset:5s} {tau:5d} {e:6.3f} "
                      f"{block['non_ambiguous_cells']:7d} "
                      f"{block['scored_cells']:7d} {row['called']:7d} "
                      f"{_num(row['coverage'], 6, 3)} {_num(row['error'], 6, 3)} "
                      f"{_num(row['ci95'][0], 6, 3)} {_num(row['ci95'][1], 6, 3)} "
                      f"{_num(row['mean_abs_delta_called_usd'], 9, 0)} "
                      f"{_num(row['mean_abs_delta_abstained_usd'], 9, 0)} "
                      f"{_num(row['median_margin'], 7, 3)} "
                      f"{row['days_without_margin']:7d}")
    print(f"\n  selection ({SELECTION_RULE})")
    print(f"  {'asset':5s} {'tau':>5s} {'e':>6s} {'cov':>6s} {'err':>6s} "
          f"{'ciU':>6s} {'called':>7s} {'flags':30s}")
    for asset in ASSETS:
        pick = report["selection"][asset]
        print(f"  {asset:5s} {str(pick.get('tau')):>5s} "
              f"{str(pick.get('e')):>6s} {_num(pick.get('coverage'), 6, 3)} "
              f"{_num(pick.get('error'), 6, 3)} "
              f"{_num((pick.get('ci95') or [None, None])[1], 6, 3)} "
              f"{str(pick.get('called')):>7s} {','.join(pick['flags']):30s}")


def print_stage_b(report: Mapping[str, object]) -> None:
    print("\n== STAGE B priced policies (frozen outcome law, EXPLORE days)")
    print(f"  F4 gate = per-asset median R0 (mid2): "
          f"{ {k: round(float(v)) for k, v in report['r0_median_gate_mid2'].items()} }"
          f"  matches sweep1={report['r0_gate_matches_sweep1']}")
    print(f"  scored days per asset (walk-forward burn-in removes the first "
          f"{MIN_TRAIN_DAYS}): {report['scored_days']}")
    print(f"  {'pol':4s} {'law':8s} {'asset':5s} {'call':>5s} {'ent':>5s} "
          f"{'gate':>5s} {'noev':>5s} {'cov':>6s} {'usd/day':>10s} "
          f"{'usd/sday':>10s} {'usd/trd':>9s} {'win':>6s} {'wall':>5s} "
          f"{'mdd_day':>9s} {'mdd_trd':>9s} {'rung':>5s}")
    for name, block in sorted(report["policies"].items()):
        for asset in ASSETS:
            row = block["by_asset"][asset]
            print(f"  {name:4s} {block['law']:8s} {asset:5s} "
                  f"{row['skip_called']:5d} {row['trades']:5d} "
                  f"{row['skip_gated']:5d} {row['skip_no_event']:5d} "
                  f"{_num(row['coverage'], 6, 3)} "
                  f"{_num(row['usd_per_asset_day'], 10, 1)} "
                  f"{_num(row['usd_per_scored_day'], 10, 1)} "
                  f"{_num(row['usd_per_trade'], 9, 1)} "
                  f"{_num(row['win_rate'], 6, 3)} {row['walls']:5d} "
                  f"{_num(row['mdd_day_usd'], 9, 0)} "
                  f"{_num(row['mdd_trade_usd'], 9, 0)} "
                  f"{'Y' if row['clears_rung'] else 'n':>5s}")
    rep = report["policies"]["P1"].get("replay", {"status": "ABSENT"})
    print("\n  engine replay (P1; partial-day: the split breaks portfolio days)")
    if rep.get("status") != "OK":
        print(f"  P1 replay status={rep.get('status')}")
    else:
        for name in ("asset_days", "trades", "usd_per_asset_day", "usd_per_trade",
                     "total_usd", "max_drawdown_usd", "drawdown_p90_usd",
                     "drawdown_breach_rate", "worst_asset_day_usd", "arrivals",
                     "occupancy_or_cap_skips"):
            print(f"  {'P1':4s} {name:28s} {_num(rep[name], 12, 3)}")
        for asset, values in sorted(rep["by_asset"].items()):
            print(f"  {'P1':4s} {'replay/' + asset:28s} "
                  f"usd_day={values['usd_per_asset_day']:.1f} "
                  f"trades={values['trades']} "
                  f"mdd={values['max_drawdown_usd']:.0f}")
    nulls = report["nulls"]
    print(f"\n  block-permutation null: draws={nulls['draws']} "
          f"seed={nulls['seed']} statistic={nulls['statistic']}")
    print("  (within-asset day-label permutation preserves each line's total "
          "cash exactly; the null moves the PATH)")
    if nulls.get("lines_held_out_empty"):
        print(f"  held out (entered no cell): {nulls['lines_held_out_empty']}")
    print(f"  {'line':10s} {'obs_mdd':>9s} {'null_mean':>10s} {'null_p05':>10s} "
          f"{'p_own':>7s} {'p_maxadj':>9s} {'pool_mdd':>9s} {'p_pool':>7s} "
          f"{'p_pl_adj':>9s}")
    for name, value in sorted(nulls["by_line"].items()):
        print(f"  {name:10s} {_num(value['observed_max_asset_mdd_usd'], 9, 0)} "
              f"{_num(value['null_asset_mdd_mean_usd'], 10, 0)} "
              f"{_num(value['null_asset_mdd_p05_usd'], 10, 0)} "
              f"{_num(value['p_own'], 7, 3)} "
              f"{_num(value['p_max_adjusted'], 9, 3)} "
              f"{_num(value['observed_pooled_mdd_usd'], 9, 0)} "
              f"{_num(value['p_pooled_own'], 7, 3)} "
              f"{_num(value['p_pooled_max_adjusted'], 9, 3)}")


# --------------------------------------------------------------------------
# Selftest: synthetic arrays only, zero era bytes.
# --------------------------------------------------------------------------

def _synthetic_cell(mid: Sequence[float], cert_p: Sequence[float],
                    cert_m: Sequence[float], ok_p: Sequence[bool],
                    ok_m: Sequence[bool], legal_p: int, legal_m: int,
                    cost: float = 20.0, asset: str = "HG") -> S1.CellRec:
    n = len(mid)
    lat = np.arange(n, dtype=np.int64) * S1.BAR_NS
    return S1.CellRec(
        asset=asset, d8=20220301, phase="0", text=f"{asset}/20220301/0/0",
        phase_open_ts_ns=0, phase_close_ts_ns=int(n * S1.BAR_NS),
        locked_iid=1, pack_sha256="0" * 64, raw_first=0, k0=1,
        r0_mid2=100.0, legal_from_p=int(legal_p), legal_from_m=int(legal_m),
        lat=lat, mid=np.asarray(mid, np.int64),
        bar_ok=np.ones(n, bool), cost=np.full(n, float(cost)),
        cert_p=np.asarray(cert_p, np.float64), cert_m=np.asarray(cert_m, np.float64),
        ok_p=np.asarray(ok_p, bool), ok_m=np.asarray(ok_m, bool),
        wall_p=np.zeros(n, bool), wall_m=np.zeros(n, bool),
        exit_p=lat.copy(), exit_m=lat.copy(),
        cum_long=np.zeros(n, np.int32), cum_short=np.zeros(n, np.int32),
        raw_cut=np.zeros(n, np.int64), raw_last=np.zeros(n, np.int64))


def _selftest_delta_star() -> list[tuple[str, bool, str]]:
    """Hand lattice: reverse cummax, the LEGAL restriction, the sentinel.

    cert(+1) = [10, 400, 50, 900, 20, (uncertifiable)]
    cert(-1) = [ 5,  60, 700,  40, 10, -50]        cost = 20 => band = 100.

    UNRESTRICTED reverse cummax:
      REM(+1) = [900, 900, 900, 900, 20, -20 sentinel]
      REM(-1) = [700, 700, 700,  40, 10, -50]
      Delta*  = [200, 200, 200, 860, 10,  30]   sharp = [T,T,T,T,F,F], side +1.
    LEGAL with the long side forming only at bar 4 and the short side at bar 1:
      REM(+1) = [ 20,  20,  20,  20, 20, -20 sentinel]
      REM(-1) = [700, 700, 700,  40, 10, -50]
      Delta*  = [-680,-680,-680,-20, 10,  30]   sharp = [T,T,T,F,F,F], side -1.
    The legality restriction therefore FLIPS the labelled side on this cell.
    """

    cert_p = [10.0, 400.0, 50.0, 900.0, 20.0, -30.0]
    cert_m = [5.0, 60.0, 700.0, 40.0, 10.0, -50.0]
    ok_p = [True, True, True, True, True, False]
    ok_m = [True, True, True, True, True, True]
    rec = _synthetic_cell([0] * 6, cert_p, cert_m, ok_p, ok_m,
                          legal_p=4, legal_m=1, cost=20.0)
    un = star_cell(rec, "unrestricted")
    legal = star_cell(rec, "legal")
    checks = [
        ("rem_unrestricted_reverse_cummax",
         list(un.rem_p) == [900.0, 900.0, 900.0, 900.0, 20.0, -20.0]
         and list(un.rem_m) == [700.0, 700.0, 700.0, 40.0, 10.0, -50.0],
         f"REM+={list(un.rem_p)} REM-={list(un.rem_m)}"),
        ("rem_sentinel_when_no_tau_remains", float(un.rem_p[5]) == -20.0,
         f"sentinel={un.rem_p[5]} expected -cost=-20.0"),
        ("delta_star_unrestricted",
         list(un.delta) == [200.0, 200.0, 200.0, 860.0, 10.0, 30.0],
         f"delta={list(un.delta)}"),
        ("ambiguity_band_floor",
         list(un.sharp) == [True, True, True, True, False, False],
         f"sharp={list(un.sharp)} (band=max(2*20,100)=100)"),
        ("stable_sign_and_first_stable",
         un.stable_side == 1 and un.first_stable == 0 and un.flips == 0,
         f"stable={un.stable_side} first={un.first_stable} flips={un.flips}"),
        ("legal_restriction_binds",
         list(legal.rem_p) == [20.0, 20.0, 20.0, 20.0, 20.0, -20.0],
         f"legal REM+={list(legal.rem_p)} expected the bar-4 value only"),
        ("legal_delta_star",
         list(legal.delta) == [-680.0, -680.0, -680.0, -20.0, 10.0, 30.0],
         f"legal delta={list(legal.delta)}"),
        ("legal_label_flips_the_side",
         list(legal.sharp) == [True, True, True, False, False, False]
         and legal.stable_side == -1 and legal.first_stable == 0,
         f"legal sharp={list(legal.sharp)} side={legal.stable_side}"),
    ]
    # A cell whose long side never forms falls to the sentinel everywhere.
    dead = _synthetic_cell([0] * 6, cert_p, cert_m, ok_p, ok_m,
                           legal_p=-1, legal_m=1, cost=20.0)
    star = star_cell(dead, "legal")
    checks.append(("legal_sentinel_when_side_never_forms",
                   list(star.rem_p) == [-20.0] * 6,
                   f"REM+={list(star.rem_p)}"))
    return checks


def _selftest_event_bar() -> list[tuple[str, bool, str]]:
    """Hand event law: the first new running minimum at or after tau.

    Bar mids in price ticks (mid2 = ticks * 2 * raw tick).  The running minimum
    is 100 at bar 0, 90 from bar 2, and the phase runs 60 bars, so the
    ``phase_close - 1800 s`` deadline is bar 30.

    tau = bar 15, side +1 (adverse extreme = a new running MINIMUM):
      bar 20 (85) is the first mid strictly below the running minimum 90
        => EVENT enters at bar 20.
      bar 21 (86) is +1 tick, under the 4-tick confirmation, so EVENT+1 keeps
        waiting; bar 22 (84) is the next new minimum and bar 23 (200) is
        +116 ticks => EVENT+1 enters at bar 23.
    tau = bar 2, side -1 (adverse extreme = a new running MAXIMUM):
      bar 3 (120) is the first mid above the running maximum 110 => bar 3.
    """

    tick = int(ASSET_RAW_TICK["HG"])
    values = ([100, 110, 90, 120, 130, 140, 150, 140, 130, 120] +
              [125, 135, 145, 155, 150, 145, 140, 135, 130, 125] +
              [85, 86, 84, 200, 205] + [205] * 35)
    mid = np.asarray(values, np.int64) * 2 * tick
    rec = _synthetic_cell(mid, [0.0] * len(mid), [0.0] * len(mid),
                          [True] * len(mid), [True] * len(mid), 0, 0)
    ext = extremes(rec)
    tau_bar = 15
    found_event = entry_bar(rec, ext, 1, tau_bar, "EVENT")
    found_plus = entry_bar(rec, ext, 1, tau_bar, "EVENT+1")
    found_short = entry_bar(rec, ext, -1, 2, "EVENT")
    checks = [
        ("event_deadline_bar_is_phase_close_minus_1800s",
         deadline_bar(rec) == 30, f"deadline bar={deadline_bar(rec)} expected 30"),
        ("event_bar_new_running_minimum", found_event == 20,
         f"EVENT bar={found_event} expected 20"),
        ("event_plus_one_waits_for_the_4_tick_move", found_plus == 23,
         f"EVENT+1 bar={found_plus} expected 23"),
        ("at_tau_law_enters_at_tau",
         entry_bar(rec, ext, 1, tau_bar, "AT-TAU") == tau_bar,
         "AT-TAU did not enter at tau"),
        ("short_side_reads_new_running_maximum", found_short == 3,
         f"short EVENT bar={found_short} expected 3"),
    ]
    # A cell whose only new minimum sits past the deadline must abstain.
    late = np.full(60, 100, np.int64)
    late[45] = 50
    late_rec = _synthetic_cell(late * 2 * tick, [0.0] * 60, [0.0] * 60,
                               [True] * 60, [True] * 60, 0, 0)
    checks.append(("event_deadline_blocks_late_entries",
                   entry_bar(late_rec, extremes(late_rec), 1, 15, "EVENT") == -1,
                   "an event past phase_close-1800s was accepted"))
    return checks


def _selftest_walk_forward() -> list[tuple[str, bool, str]]:
    """A planted day-local leak that only a training-set breach can read."""

    rng = np.random.default_rng(SEED)
    days = list(range(20220101, 20220101 + 25))
    per_day = 12
    target = days[-1]
    day_of_row = np.repeat(np.asarray(days, np.int64), per_day)
    rows = len(day_of_row)
    labels = rng.integers(0, 2, rows).astype(np.float64)
    x = rng.normal(size=(rows, N_FEATURES))
    leak = np.where(day_of_row == target, (labels * 2.0 - 1.0) * 8.0, 0.0)
    x[:, 0] = leak
    out = walk_forward(x, x, labels, day_of_row, days, min_train_days=20)
    scored = out["scored"]
    e = E_GRID[-1]
    called = out["called"][e] & scored
    predicted = out["predicted"][e]
    truth = np.where(labels > 0.5, 1, -1)
    error = (float(np.mean(predicted[called] != truth[called]))
             if int(called.sum()) else None)
    checks = [
        ("walk_forward_scores_only_after_burn_in",
         int(scored.sum()) == per_day * (len(days) - 20)
         and not bool(scored[day_of_row == days[0]].any()),
         f"scored={int(scored.sum())} expected {per_day * (len(days) - 20)}"),
        ("walk_forward_fits_one_model_per_scored_day",
         out["fits"] == len(days) - 20, f"fits={out['fits']}"),
        ("walk_forward_target_day_never_trains_on_itself",
         out["self_in_train"] == 0,
         f"{out['self_in_train']} of {out['fits']} fits trained on the target day"),
        ("walk_forward_leak_is_blocked",
         int(called.sum()) == 0 or (error is not None and error > 0.25),
         f"called={int(called.sum())} test error={error} on rows carrying a "
         "day-local planted leak; only a training set holding the target day "
         "can read it"),
    ]
    return checks


def selftest() -> int:
    mutant = os.environ.get("QRE2_MILL_MUTANT", "")
    checks: list[tuple[str, bool, str]] = []
    checks.append(("feature_count_is_13", len(FEATURE_NAMES) == N_FEATURES,
                   f"{len(FEATURE_NAMES)} names for {N_FEATURES} features"))
    checks.extend(_selftest_delta_star())
    checks.extend(_selftest_event_bar())
    checks.extend(_selftest_walk_forward())
    dead = [(name, why) for name, ok, why in checks if not ok]
    if dead:
        for name, why in dead:
            print(f"DEAD: {name}: {why}")
        print(f"sweep2_selftest_dead mutant={mutant or 'none'} "
              f"cases={len(dead)}/{len(checks)}")
        return 1
    if mutant:
        print(f"DEAD: mutant {mutant} left every sweep-2 case green")
        return 1
    print(f"sweep2_selftest_ok cases={len(checks)}")
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


def _collect_calls(f_report: Mapping[str, object],
                   ) -> dict[tuple[str, int, float], dict[str, np.ndarray]]:
    return f_report["_calls"]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", nargs="?", default="all",
                        choices=("n1", "n2", "n3", "n4", "stage-n", "stage-f",
                                 "stage-b", "stage-fb", "log", "all"))
    parser.add_argument("--assets", default="HG,NKD,SI")
    parser.add_argument("--root", default=str(M.MILL_ROOT))
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    assets = tuple(name.strip().upper() for name in args.assets.split(",")
                   if name.strip())
    started = time.monotonic()
    records, days = _load(assets, Path(args.root))
    explore_days = S1._explore_days(assets)
    stars = stars_for(records, "legal", "max2cost100")
    stars_2cost = stars_for(records, "legal", "2cost")
    stars_un = stars_for(records, "unrestricted", "max2cost100")
    exts = [extremes(rec) for rec in records]
    report = read_report()
    report.setdefault("spec_sha", SPEC_SHA)
    report["code_sha"] = code_sha()
    report["split_sha"] = split_sha()
    report["outcome_law_sha"] = outcome_law_sha()
    report["parent_trial"] = PARENT_TRIAL
    stage_n = report.get("stage_n", {})
    stage_n["asset_days"] = days
    stage_n["cells"] = S1.cells_by_asset(records)
    stage_n["bands"] = {"primary": "max(2*cost,100)", "sensitivity": "2*cost"}

    if args.stage in ("n1", "stage-n", "all"):
        stage_n["n1"] = n1(records, stars, days)
        stage_n["n1_2cost"] = n1(records, stars_2cost, days)
        stage_n["n1_unrestricted"] = n1(records, stars_un, days)
        print_n1(stage_n["n1"], "max(2*cost,100)")
        print_n1(stage_n["n1_2cost"], "2*cost [sensitivity]")
    if args.stage in ("n2", "n3", "stage-n", "all"):
        block, lines = n2(records, stars, exts, days)
        stage_n["n2"] = block
        if args.stage in ("n2", "stage-n", "all"):
            print_n2(block)
            sens, _sens_lines = n2(records, stars_2cost, exts, days)
            stage_n["n2_2cost"] = sens
            print("\n-- N2 sensitivity, ambiguity band = 2*cost only "
                  "(coverage and usd/day)")
            print(f"{'line':16s} " + " ".join(f"{a + ' cov':>9s} {a + ' $/day':>10s}"
                                              for a in ASSETS))
            for name, line in sens.items():
                print(f"{name:16s} " + " ".join(
                    f"{line[a]['coverage']:9.3f} "
                    f"{line[a]['usd_per_asset_day']:10.1f}" for a in ASSETS))
    if args.stage in ("n3", "stage-n", "all"):
        stage_n["n3"] = n3(records, lines, stage_n["n2"], days)
        print_n3(stage_n["n3"])
    if args.stage in ("n4", "stage-n", "all"):
        stage_n["n4"] = n4(records, stars, stars_un)
        print_n4(stage_n["n4"], args.top)
    report["stage_n"] = stage_n

    if args.stage in ("stage-f", "stage-b", "stage-fb", "log", "all"):
        if "n3" not in stage_n:
            raise SweepRefusal("stage F needs N3's budget; run stage-n first")
        budgets = {asset: dict(stage_n["n3"]["budget_by_asset"][asset])
                   for asset in ASSETS}
    if args.stage in ("stage-f", "stage-fb", "all"):
        features = [feature_matrix(rec) for rec in records]
        f_report = stage_f(records, stars, features, explore_days, budgets)
        report["stage_f"] = f_report
        print_stage_f(f_report)
    if args.stage in ("stage-b", "stage-fb", "all"):
        if "stage_f" not in report or "_calls" not in report["stage_f"]:
            raise SweepRefusal("stage B needs stage F in the same process")
        report["stage_b"] = stage_b(records, exts, days, explore_days,
                                    report["stage_f"], report["stage_f"]["_calls"])
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
