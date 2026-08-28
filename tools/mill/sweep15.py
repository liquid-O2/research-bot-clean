#!/usr/bin/env python3
"""Sweep 15 of the side-resolution mill: the oracle noise-ceiling decomposition.

Sweep 14 priced a hindsight per-cell-max oracle at 2564/3670/4434 usd/day and
every fitted policy captured a small fraction of it.  Before another unit spends
itself chasing that ceiling, this one asks whether the ceiling is *collectable*:
how much of it is state-linked structure a policy could in principle find, and
how much is the order-statistic premium of taking a maximum over a large pool of
draws.  A maximum over 100 i.i.d. draws is large whether or not anything is
predictable, so the oracle's height is not on its own evidence of anything.

The method: destroy the link between the outcome and the (cell, occurrence) it
sat on, hold the outcome MARGINAL fixed, and re-take the oracle.  What survives
is premium.  What the real oracle has over that is structure excess.

Nothing here is a policy and nothing here is selected.  Y is read for
measurement only.  Machinery is imported, never re-implemented: sweep 14 owns
the occurrence stream, the 16-feature plane, the per-occurrence label Y_k, the
walk-forward fold law and the ridge; sweep 9 owns the row plane; sweep 1 owns
the outcome law, the rungs and the log.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
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

import mill as M  # noqa: F401  (the loader package the caches hang off)
import context as CTX  # noqa: F401
import sweep1 as S1
import sweep8 as S8
import sweep9_twins as S9
import sweep12 as S12
import sweep14 as S14

# --------------------------------------------------------------------------
# The law, registered before anything is read.
# --------------------------------------------------------------------------

SPEC = """QRE2MILLSWEEP15
tier=exploratory; EXPLORE-only; MEASUREMENT ONLY.  Parent = sweep14-013, the
  hypothesis-log tail at registration.  Family F12-NOISECEIL.  Seed 20260827.
  No policy is selected on anything measured here; Y is read as a label.
DATA LAW.  EXPLORE days only, off the existing mill caches.  No packs, no HOLD,
  no teacher labels, no 2021, no 2025.  The occurrence stream is sweep 14's,
  built by calling its own ``build_streams`` on sweep 9's row plane: one row is
  one distinct in-zone CLEAR candidate at its own decision stamp, and Y_k is
  sweep 14's exact cash label ``make_entry(...).cert_usd``.  Sweep 9's plane
  counters (47402 rows; certifiable 138/132/132) are the refuse-to-run gate, and
  sweep 14's banked per-cell-max oracle on its scoring days
  (2564.1158/3670.0000/4434.0385 usd/day) is a second one.
SCOPES.  ALL = every EXPLORE day carrying a stream; SCORING = sweep 14's
  scoring-day subset, recomputed from its own fold law (day index >= 25 prior
  EXPLORE days for the asset AND a non-empty certifiable census) and asserted
  equal to the day lists banked in .audit/mill-sweep14.json.
GRAINS.  FINE = every occurrence.  COARSE = new-extreme moments only,
  approximated as each (cell, side)'s first occurrence after every ordinal
  reset, i.e. the rows whose sweep-9 ``inzone_ordinal`` is 1 - the historical
  ~6-events-per-cell universe.  The order-statistic premium grows with the
  selection pool, so both grains are reported side by side throughout.
M1 REAL ORACLE.  Per cell, max Y_k over its occurrences; usd/day = the sum of
  per-cell maxima over the scope's day denominator.  Cells with no occurrence
  contribute zero and are still counted in the certifiable-cell coverage.
M2 NOISE CEILING, three schemes, 200 draws each, seed 20260827.  Strata are
  (asset, phase, occurrence-count decile), deciles taken over the cells of that
  asset within the scope and grain.  (a) WITHIN-CELL: permute Y across the
  occurrences of each cell.  The per-cell max is INVARIANT under this by
  construction; it is reported as a tautology check on the machinery, not as a
  null.  (b) CROSS-CELL WITHIN-STRATUM: permute Y across all occurrences pooled
  in a stratum, reassign at each cell's original occurrence count, re-take the
  maxima.  (c) PARAMETRIC: per stratum, draw Y from the stratum's empirical
  marginal with replacement at each cell's original count.  Reported per scheme:
  the draw distribution of the noise-ceiling usd/day (mean, p5, p95), the
  STRUCTURE EXCESS = real oracle - noise-ceiling mean, and the real oracle's
  percentile position in the draws.  A real oracle above the scheme-(b) p95 is
  genuine structure; inside the band it is order-statistic premium.
M3 PREDICTABLE COMPONENT.  Ridge (lambda 1.0, standardised, unpenalised
  intercept - sweep 14's ``Sums``/``Ridge`` verbatim) of Y_k on sweep 14's
  16-feature plane under sweep 14's fold law (``fold_days``: strictly prior
  EXPLORE days, >= 25 of them, training-set column-mean imputation).  In-fold
  and out-of-fold R2 for Y, |Y| and sign(Y), plus the p5-p95 spread of the
  out-of-fold conditional mean E[Y|s] against Y's own p5-p95 spread.
M4 DECOMPOSITION.  real oracle = noise ceiling + structure excess, printed
  beside the E[Y] baseline (the enter-everything expectation), the best causal
  line the program has ever priced (+287 NKD control, +211 NKD primary, sweeps
  8) and the per-trade requirement at full coverage.
DECISION TABLE, pre-registered, evaluated at BOTH grains on the SCORING scope.
  STRUCTURE-EXISTS: on a deciding asset the real oracle exceeds the scheme-(b)
  p95 AND the structure excess >= that asset's rung.  PREMIUM-DOMINATED: the
  real oracle sits inside scheme (b)'s p5-p95 band on BOTH deciding assets.
  PARTIAL otherwise.  NKD and SI decide; HG is report-only.
MUTANT.  QRE2_MILL_S15_MUTANT=shuffle_preserves_cell makes scheme (b) shuffle
  within cells instead of across them, collapsing the noise band onto the real
  oracle; the i.i.d. selftest case must go red.
"""

ASSETS = S1.ASSETS
DECIDING = ("NKD", "SI")
REPORT_ONLY = ("HG",)
PHASES = S14.PHASES
SEED = 20260827

# Frozen, inherited.  Aliases so a drift upstream fails loudly here.
DAY_RUNG_USD = S1.DAY_RUNG_USD                    # HG 2000, NKD 1500, SI 1500
MIN_PRIOR_DAYS_FIT = S14.MIN_PRIOR_DAYS_FIT       # 25
RIDGE_LAMBDA = S14.RIDGE_LAMBDA                   # 1.0
NFEAT = S14.NFEAT                                 # 16
FEATURES = S14.FEATURES
ORD_SIDE_COL = FEATURES.index("ord_side")

DRAWS = 200
N_DECILES = 10
SCHEMES = ("within_cell", "cross_cell", "parametric")
SCHEME_LABEL = {"within_cell": "(a) within-cell  [TAUTOLOGY]",
                "cross_cell": "(b) cross-cell within-stratum",
                "parametric": "(c) parametric marginal"}
SCOPES = ("all", "scoring")
GRAINS = ("fine", "coarse")

# The refuse-to-run gates.
REPRO_ROWS = S14.REPRO_ROWS                       # 47402
REPRO_CERTIFIABLE = S14.REPRO_CERTIFIABLE         # 138/132/132
BANKED_SWEEP14 = ROOT / ".audit/mill-sweep14.json"
ORACLE_TOL_USD = 0.01

# Context constants, carried with their provenance and never recomputed here.
CAUSAL_BEST_USD_DAY = {"NKD_control_sweep8": 287.0, "NKD_primary_sweep8": 211.0}
PER_TRADE_REQ_BRIEF = {"HG": 654.0, "NKD": 491.0, "SI": 490.0}

FAMILY = "F12-NOISECEIL"
PARENT_TRIAL = "sweep14-013"
SELECTION_RULE = ("none: measurement only, no policy selected; pre-registered "
                  "strata, 200 draws, seed 20260827")

MUTANT_ENV = "QRE2_MILL_S15_MUTANT"
MUTANT_PRESERVE = "shuffle_preserves_cell"
MUTANTS = (MUTANT_PRESERVE,)

OUT_PATH = ROOT / ".audit/mill-sweep15.json"
LOG_PATH = S1.LOG_PATH


class SweepRefusal(RuntimeError):
    pass


SPEC_SHA = S1._sha_text(SPEC)


def code_sha() -> str:
    return S1._sha_file(Path(__file__).resolve())


def _mutant() -> str:
    name = os.environ.get(MUTANT_ENV, "")
    if name and name not in MUTANTS:
        raise SweepRefusal(f"unknown sweep-15 mutant {name!r}; known: {MUTANTS}")
    return name


# --------------------------------------------------------------------------
# The occurrence universe: sweep 14's streams, flattened per (asset, scope,
# grain) into the arrays every measurement below reads.
# --------------------------------------------------------------------------

def coarse_occs(stream: S14.Stream) -> list[S14.Occ]:
    """The new-extreme moments: the first occurrence after every ordinal reset.

    Sweep 9's ``inzone_ordinal`` counts a side's in-zone candidates since that
    side's last NEW EXTREME and restarts at 1 on each one (sweep 14's
    ``side_ordinals`` is the reference implementation).  So ordinal == 1 IS the
    set of reset markers, one per (cell, side, new extreme), and it is the
    coarse universe without re-deriving any extreme.
    """

    return [occ for occ in stream.occs
            if int(round(float(occ.x[ORD_SIDE_COL]))) == 1]


def grain_occs(stream: S14.Stream, grain: str) -> list[S14.Occ]:
    if grain == "fine":
        return list(stream.occs)
    if grain == "coarse":
        return coarse_occs(stream)
    raise SweepRefusal(f"unknown grain {grain!r}")


@dataclass(slots=True)
class Universe:
    """One (asset, scope, grain) slice, flattened for the permutation engine."""

    asset: str
    scope: str
    grain: str
    days: int                      # the usd/day denominator
    certifiable_cells: int         # the coverage denominator
    y: np.ndarray                  # (n,) occurrence payoffs
    cell: np.ndarray               # (n,) compacted cell id
    counts: np.ndarray             # (C,) occurrences per cell, cell-id order
    phase: list[str]               # (C,) per-cell phase
    order: np.ndarray              # (n,) argsort into contiguous cell blocks
    starts: np.ndarray             # (C,) block starts into y[order]
    groups_cell: list[np.ndarray]  # index arrays, one per cell
    groups_stratum: list[np.ndarray]
    stratum_key: list[tuple[str, int]]

    @property
    def n_cells(self) -> int:
        return int(len(self.counts))


def _decile(counts: np.ndarray) -> np.ndarray:
    """Occurrence-count decile per cell, taken over the slice's own cells."""

    if len(counts) == 0:
        return np.zeros(0, np.int64)
    edges = np.quantile(counts.astype(np.float64),
                        [i / N_DECILES for i in range(1, N_DECILES)])
    return np.searchsorted(edges, counts.astype(np.float64), side="left")


def build_universe(streams: Sequence[S14.Stream], asset: str, scope: str,
                   grain: str, days: int, certifiable_cells: int) -> Universe:
    keep: list[tuple[S14.Stream, list[S14.Occ]]] = []
    for stream in streams:
        if stream.asset != asset:
            continue
        occs = grain_occs(stream, grain)
        if occs:
            keep.append((stream, occs))
    y = np.asarray([occ.payoff for _s, occs in keep for occ in occs], np.float64)
    cell = np.asarray([index for index, (_s, occs) in enumerate(keep)
                       for _occ in occs], np.int64)
    counts = np.asarray([len(occs) for _s, occs in keep], np.int64)
    phase = [stream.phase for stream, _o in keep]
    order = np.argsort(cell, kind="stable")
    starts = np.concatenate([[0], np.cumsum(counts)[:-1]]).astype(np.int64) \
        if len(counts) else np.zeros(0, np.int64)
    groups_cell = [np.nonzero(cell == index)[0] for index in range(len(counts))]
    decile = _decile(counts)
    buckets: dict[tuple[str, int], list[int]] = {}
    for index in range(len(counts)):
        buckets.setdefault((phase[index], int(decile[index])), []).append(index)
    stratum_key = sorted(buckets)
    groups_stratum = [
        np.concatenate([groups_cell[c] for c in buckets[key]])
        if buckets[key] else np.zeros(0, np.int64) for key in stratum_key]
    return Universe(asset=asset, scope=scope, grain=grain, days=int(days),
                    certifiable_cells=int(certifiable_cells), y=y, cell=cell,
                    counts=counts, phase=phase, order=order, starts=starts,
                    groups_cell=groups_cell, groups_stratum=groups_stratum,
                    stratum_key=stratum_key)


# --------------------------------------------------------------------------
# The oracle and the three permutation schemes.
# --------------------------------------------------------------------------

def cell_maxima(universe: Universe, y: np.ndarray) -> np.ndarray:
    """Per-cell max, by contiguous-block reduction over the cell ordering."""

    if universe.n_cells == 0:
        return np.zeros(0, np.float64)
    return np.maximum.reduceat(y[universe.order], universe.starts)


def oracle_usd_day(universe: Universe, y: np.ndarray) -> float:
    if universe.days <= 0:
        return float("nan")
    return float(cell_maxima(universe, y).sum()) / float(universe.days)


def _permute_within(rng: np.random.Generator, y: np.ndarray,
                    groups: Sequence[np.ndarray]) -> np.ndarray:
    out = np.empty_like(y)
    for group in groups:
        out[group] = y[group][rng.permutation(len(group))]
    return out


def _resample_within(rng: np.random.Generator, y: np.ndarray,
                     groups: Sequence[np.ndarray]) -> np.ndarray:
    out = np.empty_like(y)
    for group in groups:
        out[group] = y[group][rng.integers(0, len(group), len(group))]
    return out


def scheme_groups(universe: Universe, scheme: str, mutant: str
                  ) -> list[np.ndarray]:
    """Which index blocks a scheme is allowed to move outcomes inside.

    The mutant lives here: it hands scheme (b) the per-cell blocks, so the
    cross-cell shuffle silently becomes the within-cell one and the noise band
    collapses onto the invariant real oracle.
    """

    if scheme == "within_cell":
        return universe.groups_cell
    if scheme in ("cross_cell", "parametric"):
        if scheme == "cross_cell" and mutant == MUTANT_PRESERVE:
            return universe.groups_cell
        return universe.groups_stratum
    raise SweepRefusal(f"unknown scheme {scheme!r}")


def noise_ceiling(universe: Universe, scheme: str, draws: int = DRAWS,
                  seed: int = SEED, mutant: str = "") -> dict[str, object]:
    """The draw distribution of the oracle after the scheme destroys the link."""

    real = oracle_usd_day(universe, universe.y)
    groups = scheme_groups(universe, scheme, mutant)
    rng = np.random.default_rng(seed)
    values = np.empty(draws, np.float64)
    for draw in range(draws):
        if scheme == "parametric":
            shuffled = _resample_within(rng, universe.y, groups)
        else:
            shuffled = _permute_within(rng, universe.y, groups)
        values[draw] = oracle_usd_day(universe, shuffled)
    mean = float(values.mean()) if draws else float("nan")
    p5 = float(np.percentile(values, 5.0)) if draws else float("nan")
    p95 = float(np.percentile(values, 95.0)) if draws else float("nan")
    excess = real - mean
    inside = bool(p5 <= real <= p95)
    return {"scheme": scheme, "draws": int(draws), "real_usd_day": real,
            "noise_mean_usd_day": mean, "noise_p5_usd_day": p5,
            "noise_p95_usd_day": p95, "band_width_usd_day": p95 - p5,
            "structure_excess_usd_day": excess,
            "real_percentile_in_draws": (100.0 * float(np.mean(values <= real))
                                         if draws else float("nan")),
            "share_draws_ge_real": (float(np.mean(values >= real))
                                    if draws else float("nan")),
            "above_p95": bool(real > p95), "below_p5": bool(real < p5),
            "inside_band": inside}


def count_stats(counts: np.ndarray) -> dict[str, object]:
    if not len(counts):
        return {"cells": 0}
    values = counts.astype(np.float64)
    return {"cells": int(len(values)), "occurrences": int(values.sum()),
            "min": int(values.min()), "p25": float(np.percentile(values, 25.0)),
            "median": float(np.median(values)), "mean": float(values.mean()),
            "p75": float(np.percentile(values, 75.0)),
            "p90": float(np.percentile(values, 90.0)), "max": int(values.max())}


def dispersion(universe: Universe) -> dict[str, object]:
    """How much of Y's variance is BETWEEN cells rather than within one.

    This is what decides whether a cell's occurrence count is its real selection
    pool.  If the occurrences inside a cell are near-copies of one another - the
    same move sampled many times - the cell holds far fewer independent draws
    than its count suggests, and a cross-cell shuffle, which mixes independent
    cells into every cell, will raise the maxima rather than lower them.  The
    intraclass correlation is the number that tells you which regime you are in,
    so it is reported next to the oracle rather than left to be inferred.
    """

    if universe.n_cells == 0 or len(universe.y) == 0:
        return {"icc": None}
    means = np.asarray([universe.y[group].mean()
                        for group in universe.groups_cell], np.float64)
    within = np.concatenate([universe.y[group] - universe.y[group].mean()
                             for group in universe.groups_cell])
    within_var = float((within ** 2).sum()) / max(
        len(universe.y) - universe.n_cells, 1)
    between_var = float(np.var(means, ddof=1)) if universe.n_cells > 1 else 0.0
    total = within_var + between_var
    within_sd = [float(universe.y[group].std()) for group in universe.groups_cell]
    return {"within_cell_sd_mean_usd": float(np.mean(within_sd)),
            "between_cell_sd_usd": float(np.sqrt(between_var)),
            "pooled_sd_usd": float(universe.y.std()),
            "icc": (between_var / total) if total > 0.0 else None,
            "effective_draws_per_cell": (
                float(np.mean(universe.counts)) * (within_var / total)
                if total > 0.0 else None)}


def m1_block(universe: Universe) -> dict[str, object]:
    maxima = cell_maxima(universe, universe.y)
    y = universe.y
    # A stratum holding one cell cannot shuffle across cells, so it degenerates
    # into scheme (a).  Report how much of the slice sits in one.
    strata_cells: dict[str, int] = {}
    for index, key in enumerate(universe.stratum_key):
        strata_cells[f"phase{key[0]}/d{key[1]}"] = int(
            np.unique(universe.cell[universe.groups_stratum[index]]).size)
    lone = sum(1 for value in strata_cells.values() if value <= 1)
    return {
        "asset": universe.asset, "scope": universe.scope, "grain": universe.grain,
        "days": universe.days, "certifiable_cells": universe.certifiable_cells,
        "cells_with_occurrences": universe.n_cells,
        "coverage_of_certifiable": (float(universe.n_cells)
                                    / universe.certifiable_cells
                                    if universe.certifiable_cells else None),
        "occurrences": int(len(y)),
        "oracle_usd_day": oracle_usd_day(universe, y),
        "oracle_total_usd": float(maxima.sum()),
        "cell_max_mean_usd": float(maxima.mean()) if len(maxima) else None,
        "cell_max_median_usd": float(np.median(maxima)) if len(maxima) else None,
        "cell_max_p5_usd": float(np.percentile(maxima, 5.0)) if len(maxima) else None,
        "cell_max_p95_usd": float(np.percentile(maxima, 95.0)) if len(maxima) else None,
        "occurrence_counts": count_stats(universe.counts),
        "y_mean_usd": float(y.mean()) if len(y) else None,
        "y_median_usd": float(np.median(y)) if len(y) else None,
        "y_p5_usd": float(np.percentile(y, 5.0)) if len(y) else None,
        "y_p95_usd": float(np.percentile(y, 95.0)) if len(y) else None,
        "y_positive_share": float(np.mean(y > 0.0)) if len(y) else None,
        "strata": len(universe.stratum_key),
        "strata_cells": strata_cells,
        "singleton_strata": int(lone),
        "dispersion": dispersion(universe),
    }


# --------------------------------------------------------------------------
# M3: the predictable component, under sweep 14's fold law and ridge.
# --------------------------------------------------------------------------

TARGETS = ("Y", "absY", "signY")


def _fit_targets(x: np.ndarray, y: np.ndarray) -> dict[str, S14.Ridge]:
    """Three ridges on one design, all through sweep 14's Sums/Ridge."""

    width = x.shape[1]
    pair = S14.Sums(width=width)
    pair.add(x, y, np.abs(y))
    lone = S14.Sums(width=width)
    sign = np.sign(y)
    lone.add(x, sign, sign)
    return {"Y": pair.fit("Y", RIDGE_LAMBDA), "absY": pair.fit("C", RIDGE_LAMBDA),
            "signY": lone.fit("Y", RIDGE_LAMBDA)}


def _target_vector(name: str, y: np.ndarray) -> np.ndarray:
    if name == "Y":
        return y
    if name == "absY":
        return np.abs(y)
    return np.sign(y)


def _r2(truth: np.ndarray, pred: np.ndarray) -> float | None:
    if len(truth) < 2:
        return None
    sst = float(((truth - truth.mean()) ** 2).sum())
    if sst <= 0.0:
        return None
    return 1.0 - float(((truth - pred) ** 2).sum()) / sst


def predictable_component(streams: Sequence[S14.Stream],
                          explore_days: Mapping[str, Sequence[int]],
                          scoring_days: Mapping[str, Sequence[int]]
                          ) -> dict[str, object]:
    """Walk-forward ridge R2 of Y, |Y| and sign(Y) on the 16-feature plane."""

    by_asset_day: dict[tuple[str, int], list[S14.Stream]] = {}
    for stream in streams:
        by_asset_day.setdefault((stream.asset, stream.d8), []).append(stream)
    out: dict[str, object] = {}
    for asset in ASSETS:
        days = sorted(int(day) for day in explore_days[asset])
        score = set(int(day) for day in scoring_days.get(asset, []))
        folds = 0
        infold: dict[str, list[float]] = {name: [] for name in TARGETS}
        oof_truth: dict[str, list[np.ndarray]] = {name: [] for name in TARGETS}
        oof_pred: dict[str, list[np.ndarray]] = {name: [] for name in TARGETS}
        for index, d8 in enumerate(days):
            if d8 not in score:
                continue
            today = by_asset_day.get((asset, d8), [])
            rows_today = [occ for stream in today for occ in stream.occs]
            train: list[S14.Occ] = []
            for day in S14.fold_days(days, index, ""):
                for stream in by_asset_day.get((asset, day), []):
                    train.extend(stream.occs)
            if len(train) < S14.MIN_FIT_ROWS or not rows_today:
                continue
            raw = np.vstack([occ.x for occ in train])
            with np.errstate(invalid="ignore"):
                means = np.nanmean(np.where(np.isfinite(raw), raw, np.nan), axis=0)
            means = np.where(np.isfinite(means), means, 0.0)
            xtr = S14._impute(raw, means)
            ytr = np.asarray([occ.payoff for occ in train], np.float64)
            xte = S14._impute(np.vstack([occ.x for occ in rows_today]), means)
            yte = np.asarray([occ.payoff for occ in rows_today], np.float64)
            fits = _fit_targets(xtr, ytr)
            folds += 1
            for name in TARGETS:
                truth_tr = _target_vector(name, ytr)
                got = _r2(truth_tr, fits[name].predict(xtr))
                if got is not None:
                    infold[name].append(got)
                oof_truth[name].append(_target_vector(name, yte))
                oof_pred[name].append(fits[name].predict(xte))
        block: dict[str, object] = {"folds": folds}
        for name in TARGETS:
            truth = (np.concatenate(oof_truth[name]) if oof_truth[name]
                     else np.zeros(0))
            pred = (np.concatenate(oof_pred[name]) if oof_pred[name]
                    else np.zeros(0))
            block[name] = {
                "in_fold_r2_mean": (float(np.mean(infold[name]))
                                    if infold[name] else None),
                "in_fold_r2_final": (float(infold[name][-1])
                                     if infold[name] else None),
                "oof_r2_pooled": _r2(truth, pred),
                "oof_rows": int(len(truth)),
            }
        truth = (np.concatenate(oof_truth["Y"]) if oof_truth["Y"] else np.zeros(0))
        pred = (np.concatenate(oof_pred["Y"]) if oof_pred["Y"] else np.zeros(0))
        if len(truth) > 1:
            fit_lo, fit_hi = (float(np.percentile(pred, 5.0)),
                              float(np.percentile(pred, 95.0)))
            y_lo, y_hi = (float(np.percentile(truth, 5.0)),
                          float(np.percentile(truth, 95.0)))
            block["conditional_mean_band"] = {
                "fitted_p5_usd": fit_lo, "fitted_p95_usd": fit_hi,
                "fitted_spread_usd": fit_hi - fit_lo,
                "y_p5_usd": y_lo, "y_p95_usd": y_hi,
                "y_spread_usd": y_hi - y_lo,
                "spread_ratio": ((fit_hi - fit_lo) / (y_hi - y_lo)
                                 if (y_hi - y_lo) != 0.0 else None),
                "fitted_sd_usd": float(pred.std()),
                "y_sd_usd": float(truth.std()),
                "y_mean_usd": float(truth.mean()),
                "fitted_max_usd": float(pred.max()),
            }
        else:
            block["conditional_mean_band"] = None
        out[asset] = block
    return out


# --------------------------------------------------------------------------
# The scoring-day subset and the reproduction gates.
# --------------------------------------------------------------------------

def sweep14_scoring_days(explore_days: Mapping[str, Sequence[int]],
                         census: Mapping[tuple[str, str, int], int]
                         ) -> dict[str, list[int]]:
    """Sweep 14's scoring-day rule, restated from its own constants.

    A day is scored when its asset has at least ``MIN_PRIOR_DAYS_FIT`` strictly
    earlier EXPLORE days and the day carries a non-empty certifiable census.
    The result is asserted against the day lists sweep 14 banked, so this stays
    a reproduction rather than a re-derivation.
    """

    out: dict[str, list[int]] = {}
    for asset in ASSETS:
        days = sorted(int(day) for day in explore_days[asset])
        keep: list[int] = []
        for index, d8 in enumerate(days):
            if index < MIN_PRIOR_DAYS_FIT:
                continue
            if sum(int(census.get((asset, slot, d8), 0)) for slot in PHASES):
                keep.append(d8)
        out[asset] = keep
    return out


def banked_sweep14() -> dict[str, object]:
    if not BANKED_SWEEP14.exists():
        raise SweepRefusal(f"{BANKED_SWEEP14} is missing; sweep 15 has nothing "
                           "to reproduce its oracle against")
    return json.loads(BANKED_SWEEP14.read_text())


def reproduce(plane: S9.Plane, scoring: Mapping[str, Sequence[int]],
              m1: Mapping[tuple[str, str, str], Mapping[str, object]]
              ) -> dict[str, object]:
    """Both gates: sweep 9's row plane and sweep 14's banked oracle cash."""

    banked = banked_sweep14()
    plane_block = S14.reproduce_sweep9(plane)
    days_ok = all(sorted(int(d) for d in banked["scoring_days"][asset])
                  == sorted(int(d) for d in scoring[asset]) for asset in ASSETS)
    banked_days = banked["stage_b"]["denominators"]["scoring_days"]
    banked_cells = banked["stage_b"]["denominators"]["scored_cells"]
    oracle_live = {asset: float(m1[(asset, "scoring", "fine")]["oracle_usd_day"])
                   for asset in ASSETS}
    oracle_banked = {asset: float(banked["stage_b"]["cash"]["ORACLE"][asset]
                                  ["usd_per_asset_day"]) for asset in ASSETS}
    oracle_ok = all(abs(oracle_live[a] - oracle_banked[a]) <= ORACLE_TOL_USD
                    for a in ASSETS)
    return {
        "plane": plane_block,
        "scoring_days_live": {a: len(scoring[a]) for a in ASSETS},
        "scoring_days_banked": {a: int(banked_days[a]) for a in ASSETS},
        "scoring_days_match": bool(days_ok),
        "scored_cells_banked": {a: int(banked_cells[a]) for a in ASSETS},
        "oracle_live_usd_day": oracle_live,
        "oracle_banked_usd_day": oracle_banked,
        "oracle_match": bool(oracle_ok),
        "matches": bool(plane_block["matches"] and days_ok and oracle_ok),
    }


# --------------------------------------------------------------------------
# M4 and the pre-registered decision table.
# --------------------------------------------------------------------------

def per_trade_requirement(days: int, cells: int, rung: float) -> float | None:
    """The usd/trade a full-coverage line needs to clear the day rung."""

    return (rung * days / cells) if cells else None


def m4_row(asset: str, m1: Mapping[str, object], m2: Mapping[str, object]
           ) -> dict[str, object]:
    rung = float(DAY_RUNG_USD[asset])
    cells = int(m1["cells_with_occurrences"])
    days = int(m1["days"])
    excess = float(m2["structure_excess_usd_day"])
    e_y = m1["y_mean_usd"]
    return {
        "asset": asset, "rung_usd_day": rung,
        "real_oracle_usd_day": float(m1["oracle_usd_day"]),
        "noise_ceiling_usd_day": float(m2["noise_mean_usd_day"]),
        "structure_excess_usd_day": excess,
        "noise_share": (float(m2["noise_mean_usd_day"])
                        / float(m1["oracle_usd_day"])
                        if float(m1["oracle_usd_day"]) != 0.0 else None),
        "excess_share": (excess / float(m1["oracle_usd_day"])
                         if float(m1["oracle_usd_day"]) != 0.0 else None),
        "excess_over_rung": excess / rung if rung else None,
        "excess_clears_rung": bool(excess >= rung),
        "e_y_per_occurrence_usd": e_y,
        "enter_everything_usd_day": (float(e_y) * int(m1["occurrences"]) / days
                                     if e_y is not None and days else None),
        "e_y_one_per_cell_usd_day": (float(e_y) * cells / days
                                     if e_y is not None and days else None),
        "per_trade_req_live_usd": per_trade_requirement(
            days, int(m1["certifiable_cells"]), rung),
        "per_trade_req_brief_usd": PER_TRADE_REQ_BRIEF.get(asset),
        "best_causal_line_usd_day": (CAUSAL_BEST_USD_DAY["NKD_control_sweep8"]
                                     if asset == "NKD" else None),
    }


def decide(m1: Mapping[tuple[str, str, str], Mapping[str, object]],
           m2: Mapping[tuple[str, str, str, str], Mapping[str, object]],
           scope: str = "scoring") -> dict[str, object]:
    """The pre-registered letters, evaluated at both grains."""

    out: dict[str, object] = {}
    for grain in GRAINS:
        by_asset: dict[str, object] = {}
        for asset in ASSETS:
            one = m1[(asset, scope, grain)]
            two = m2[(asset, scope, grain, "cross_cell")]
            rung = float(DAY_RUNG_USD[asset])
            excess = float(two["structure_excess_usd_day"])
            above = bool(two["above_p95"])
            by_asset[asset] = {
                "deciding": asset in DECIDING,
                "real_usd_day": float(one["oracle_usd_day"]),
                "noise_p5": float(two["noise_p5_usd_day"]),
                "noise_mean": float(two["noise_mean_usd_day"]),
                "noise_p95": float(two["noise_p95_usd_day"]),
                "structure_excess_usd_day": excess,
                "real_percentile_in_draws": float(two["real_percentile_in_draws"]),
                "above_p95": above,
                "below_p5": bool(two["below_p5"]),
                "inside_band": bool(two["inside_band"]),
                "rung_usd_day": rung,
                "excess_clears_rung": bool(excess >= rung),
                "structure_exists": bool(above and excess >= rung),
                "partial": bool(above and excess > 0.0 and excess < rung),
            }
        exists = [a for a in DECIDING if by_asset[a]["structure_exists"]]
        inside = [a for a in DECIDING if by_asset[a]["inside_band"]]
        partial = [a for a in DECIDING if by_asset[a]["partial"]]
        below = [a for a in DECIDING if by_asset[a]["below_p5"]]
        if exists:
            verdict = "STRUCTURE-EXISTS"
        elif len(inside) == len(DECIDING):
            verdict = "PREMIUM-DOMINATED"
        else:
            verdict = "PARTIAL"
        # The pre-registered table enumerates above-p95, inside-band and "otherwise
        # (excess positive and significant but below rung)".  It does not
        # enumerate BELOW p5.  When that is what fired, the residual branch is
        # reported with the gap named rather than dressed up as a PARTIAL.
        residual = None
        if verdict == "PARTIAL" and not partial:
            residual = (
                "PARTIAL fired by elimination with no asset meeting its stated "
                "condition (excess positive and significant): the real oracle "
                f"sat BELOW the scheme-(b) p5 on {below or 'no'} deciding "
                "asset(s), a case the pre-registered table did not enumerate. "
                "No structure is claimed. The excess is negative, so the "
                "ceiling is not merely order-statistic premium - it is LOWER "
                "than a like-for-like re-scatter of the same outcomes yields.")
        out[grain] = {"verdict": verdict, "scope": scope,
                      "structure_assets": exists, "inside_band_assets": inside,
                      "partial_assets": partial, "below_p5_assets": below,
                      "residual_case": residual, "by_asset": by_asset}
    agree = len({out[grain]["verdict"] for grain in GRAINS}) == 1
    return {"by_grain": out, "grains_agree": bool(agree),
            "verdict_fine": out["fine"]["verdict"],
            "verdict_coarse": out["coarse"]["verdict"]}


# --------------------------------------------------------------------------
# Printing.
# --------------------------------------------------------------------------

_n = S14._n


def print_repro(block: Mapping[str, object]) -> None:
    plane = block["plane"]
    print("\nREPRODUCTION GATE 1 - SWEEP-9 ROW PLANE")
    print(f"  rows            banked {plane['banked_rows']}  live {plane['live_rows']}")
    for asset in ASSETS:
        print(f"  certifiable {asset:<4}banked {plane['banked_certifiable'][asset]:>6}"
              f"  live {plane['live_certifiable'][asset]:>6}")
    for name in sorted(S14.REPRO_COUNTERS):
        print(f"  {name:<20}banked {plane['banked_counters'][name]:>7}"
              f"  live {plane['live_counters'][name]:>7}")
    print(f"  plane matches: {plane['matches']}")
    print("\nREPRODUCTION GATE 2 - SWEEP-14 SCORING DAYS AND BANKED ORACLE CASH")
    print("  " + "asset".ljust(8) + "days_live".rjust(11) + "days_bank".rjust(11)
          + "oracle_live".rjust(14) + "oracle_bank".rjust(14) + "delta".rjust(10))
    for asset in ASSETS:
        print("  " + asset.ljust(8) + _n(block["scoring_days_live"][asset], 11)
              + _n(block["scoring_days_banked"][asset], 11)
              + _n(block["oracle_live_usd_day"][asset], 14, 4)
              + _n(block["oracle_banked_usd_day"][asset], 14, 4)
              + _n(block["oracle_live_usd_day"][asset]
                   - block["oracle_banked_usd_day"][asset], 10, 6))
    print(f"  scoring days match: {block['scoring_days_match']}   "
          f"oracle match: {block['oracle_match']}   ALL: {block['matches']}")


def print_m1(m1: Mapping[tuple[str, str, str], Mapping[str, object]]) -> None:
    head = ("days", "cert", "cells", "occ", "occ/cell", "cnt_med", "cnt_max",
            "usd/day", "max_mean", "max_med", "E[Y]", "Y>0", "ICC", "eff_draw")
    for grain in GRAINS:
        print(f"\nM1 REAL PER-CELL-MAX ORACLE - {grain.upper()} GRAIN")
        print("  " + "asset/scope".ljust(16) + "".join(h.rjust(10) for h in head))
        for scope in SCOPES:
            for asset in ASSETS:
                row = m1[(asset, scope, grain)]
                counts = row["occurrence_counts"]
                disp = row["dispersion"]
                print("  " + f"{asset}/{scope}".ljust(16)
                      + _n(row["days"], 10) + _n(row["certifiable_cells"], 10)
                      + _n(row["cells_with_occurrences"], 10)
                      + _n(row["occurrences"], 10)
                      + _n(counts.get("mean"), 10, 1)
                      + _n(counts.get("median"), 10, 1)
                      + _n(counts.get("max"), 10)
                      + _n(row["oracle_usd_day"], 10, 1)
                      + _n(row["cell_max_mean_usd"], 10, 1)
                      + _n(row["cell_max_median_usd"], 10, 1)
                      + _n(row["y_mean_usd"], 10, 2)
                      + _n(row["y_positive_share"], 10)
                      + _n(disp.get("icc"), 10, 3)
                      + _n(disp.get("effective_draws_per_cell"), 10, 1))
    print("\n  ICC = share of Y's variance sitting BETWEEN cells; eff_draw = the "
          "occurrence count discounted")
    print("  by it, i.e. the cell's selection pool once near-duplicate "
          "occurrences are taken out.")


def print_m2(m2: Mapping[tuple[str, str, str, str], Mapping[str, object]],
             scope: str = "scoring") -> None:
    head = ("real", "noise_mean", "p5", "p95", "excess", "pct_pos", "above95",
            "inside")
    for grain in GRAINS:
        print(f"\nM2 NOISE CEILING - {grain.upper()} GRAIN, scope={scope}, "
              f"{DRAWS} draws, seed {SEED}")
        print("  " + "asset/scheme".ljust(34) + "".join(h.rjust(11) for h in head))
        for asset in ASSETS:
            for scheme in SCHEMES:
                row = m2[(asset, scope, grain, scheme)]
                label = f"{asset} {SCHEME_LABEL[scheme]}"
                print("  " + label.ljust(34)
                      + _n(row["real_usd_day"], 11, 1)
                      + _n(row["noise_mean_usd_day"], 11, 1)
                      + _n(row["noise_p5_usd_day"], 11, 1)
                      + _n(row["noise_p95_usd_day"], 11, 1)
                      + _n(row["structure_excess_usd_day"], 11, 1)
                      + _n(row["real_percentile_in_draws"], 11, 1)
                      + _n(row["above_p95"], 11) + _n(row["inside_band"], 11))
    print("\n  scheme (a) is the tautology check: permuting Y inside a cell "
          "cannot move that cell's maximum,")
    print("  so its band must be a point mass on the real oracle and its "
          "excess exactly 0.  It is reported")
    print("  as a check on the permutation machinery, never as a null.")


def print_m3(block: Mapping[str, object]) -> None:
    print("\nM3 PREDICTABLE COMPONENT - ridge on the sweep-14 16-feature plane, "
          "sweep-14 fold law")
    head = ("folds", "oof_rows", "in_R2", "in_R2_end", "oof_R2")
    print("  " + "asset/target".ljust(18) + "".join(h.rjust(12) for h in head))
    for asset in ASSETS:
        row = block[asset]
        for name in TARGETS:
            cell = row[name]
            print("  " + f"{asset}/{name}".ljust(18) + _n(row["folds"], 12)
                  + _n(cell["oof_rows"], 12) + _n(cell["in_fold_r2_mean"], 12, 4)
                  + _n(cell["in_fold_r2_final"], 12, 4)
                  + _n(cell["oof_r2_pooled"], 12, 4))
    print("\n  CONDITIONAL-MEAN BAND (out-of-fold E[Y|s] against Y itself)")
    print("  " + "asset".ljust(10) + "fit_p5".rjust(11) + "fit_p95".rjust(11)
          + "fit_spread".rjust(12) + "Y_p5".rjust(11) + "Y_p95".rjust(11)
          + "Y_spread".rjust(12) + "ratio".rjust(9) + "fit_max".rjust(10))
    for asset in ASSETS:
        band = block[asset]["conditional_mean_band"]
        if band is None:
            continue
        print("  " + asset.ljust(10) + _n(band["fitted_p5_usd"], 11, 1)
              + _n(band["fitted_p95_usd"], 11, 1)
              + _n(band["fitted_spread_usd"], 12, 1)
              + _n(band["y_p5_usd"], 11, 1) + _n(band["y_p95_usd"], 11, 1)
              + _n(band["y_spread_usd"], 12, 1) + _n(band["spread_ratio"], 9, 4)
              + _n(band["fitted_max_usd"], 10, 1))


def print_m4(m4: Mapping[tuple[str, str], Sequence[Mapping[str, object]]]) -> None:
    head = ("real", "noise", "excess", "noise%", "excess%", "rung",
            "exc/rung", "clears", "E[Y]/occ", "1-per-cell", "req/trade")
    for grain in GRAINS:
        print(f"\nM4 DECOMPOSITION - {grain.upper()} GRAIN, scope=scoring, "
              "scheme (b) as the noise ceiling")
        print("  " + "asset".ljust(8) + "".join(h.rjust(11) for h in head))
        for row in m4[(grain, "scoring")]:
            print("  " + row["asset"].ljust(8)
                  + _n(row["real_oracle_usd_day"], 11, 1)
                  + _n(row["noise_ceiling_usd_day"], 11, 1)
                  + _n(row["structure_excess_usd_day"], 11, 1)
                  + _n(row["noise_share"], 11, 3)
                  + _n(row["excess_share"], 11, 3)
                  + _n(row["rung_usd_day"], 11, 0)
                  + _n(row["excess_over_rung"], 11, 2)
                  + _n(row["excess_clears_rung"], 11)
                  + _n(row["e_y_per_occurrence_usd"], 11, 2)
                  + _n(row["e_y_one_per_cell_usd_day"], 11, 1)
                  + _n(row["per_trade_req_live_usd"], 11, 0))
    print("\n  REFERENCE LINES CARRIED FROM THE RECORD (not recomputed here)")
    print(f"    best causal line ever priced: +{CAUSAL_BEST_USD_DAY['NKD_control_sweep8']:.0f}"
          f" usd/day NKD control, +{CAUSAL_BEST_USD_DAY['NKD_primary_sweep8']:.0f}"
          " usd/day NKD primary (sweeps 8)")
    print("    per-trade requirement at full coverage, brief: "
          + ", ".join(f"{a} {PER_TRADE_REQ_BRIEF[a]:.0f}" for a in ASSETS))
    print("    per-trade requirement at full coverage, live on the sweep-14 "
          "scoring denominators: "
          + ", ".join(f"{row['asset']} {row['per_trade_req_live_usd']:.0f}"
                      for row in m4[("fine", "scoring")]))


def print_decision(block: Mapping[str, object]) -> None:
    print("\nDECISION TABLE (pre-registered), scope=scoring, both grains")
    head = ("real", "noise_p5", "noise_mean", "noise_p95", "excess", "pct",
            "rung", "clears", "letter")
    print("  " + "grain/asset".ljust(16) + "".join(h.rjust(11) for h in head))
    for grain in GRAINS:
        one = block["by_grain"][grain]
        for asset in ASSETS:
            row = one["by_asset"][asset]
            letter = ("STRUCTURE" if row["structure_exists"]
                      else "PARTIAL" if row["partial"]
                      else "INSIDE" if row["inside_band"]
                      else "BELOW-p5" if row["below_p5"] else "-")
            mark = "*" if row["deciding"] else " "
            print("  " + f"{grain}/{asset}{mark}".ljust(16)
                  + _n(row["real_usd_day"], 11, 1) + _n(row["noise_p5"], 11, 1)
                  + _n(row["noise_mean"], 11, 1) + _n(row["noise_p95"], 11, 1)
                  + _n(row["structure_excess_usd_day"], 11, 1)
                  + _n(row["real_percentile_in_draws"], 11, 1)
                  + _n(row["rung_usd_day"], 11, 0)
                  + _n(row["excess_clears_rung"], 11) + letter.rjust(11))
    for grain in GRAINS:
        one = block["by_grain"][grain]
        print(f"  {grain.upper():<8} VERDICT: {one['verdict']}"
              f"   structure {one['structure_assets'] or 'none'}"
              f"   inside-band {one['inside_band_assets'] or 'none'}"
              f"   partial {one['partial_assets'] or 'none'}"
              f"   below-p5 {one['below_p5_assets'] or 'none'}")
        if one["residual_case"]:
            print(f"           NOTE: {one['residual_case']}")
    print(f"  grains agree: {block['grains_agree']}   "
          f"(* marks the deciding assets {DECIDING}; HG is report-only)")


# --------------------------------------------------------------------------
# SELFTEST.
# --------------------------------------------------------------------------

_check = S14._check


def _synthetic_universe(kind: str, cells: int = 200, k: int = 8,
                        seed: int = 11, amplitude: float = 10.0
                        ) -> tuple[Universe, np.ndarray]:
    """Synthetic streams with a known answer, plus the planted lift per cell.

    ``iid``: Y is pure noise, so nothing links an outcome to the cell or to the
    occurrence it sat on and the real oracle must land inside the noise band.
    ``planted``: exactly one occurrence per cell carries a dominant bonus, the
    cleanest possible state-linked component - the good moment exists and it is
    one per cell.
    """

    rng = np.random.default_rng(seed)
    streams: list[S14.Stream] = []
    lift = np.zeros(cells, np.float64)
    for index in range(cells):
        stream = S14.Stream(cell=index, asset="HG", d8=20220101 + index // 5,
                            phase="0")
        base = rng.random(k)
        pays = base.copy()
        if kind == "planted":
            spot = int(rng.integers(0, k))
            pays[spot] += amplitude
        lift[index] = float(pays.max() - base.max())
        for slot in range(k):
            x = np.zeros(NFEAT, np.float64)
            x[ORD_SIDE_COL] = float(slot + 1)
            stream.occs.append(S14.Occ(
                row=index * k + slot, cell=index, asset="HG",
                d8=20220101 + index // 5, phase="0", side=1, bar=slot + 1,
                k=slot + 1, remaining_s=float(S14.REMAIN_MIN_S + 600),
                payoff=float(pays[slot]), x=x, y1800=1, soft_hit=True,
                delay_s=0.0, depth=0.0, side_ok=True, legal=True))
        streams.append(stream)
    universe = build_universe(streams, "HG", "selftest", "fine", days=1,
                              certifiable_cells=cells)
    return universe, lift


def _selftest_engine() -> list[tuple[str, bool, str]]:
    """The per-cell max and the shuffle blocks, against slow references."""

    universe, _lift = _synthetic_universe("iid", cells=40, k=6, seed=3)
    slow = np.asarray([universe.y[universe.cell == index].max()
                       for index in range(universe.n_cells)], np.float64)
    fast = cell_maxima(universe, universe.y)
    out = [_check("engine/blocked per-cell max matches the slow reference",
                  bool(np.allclose(slow, fast)),
                  f"{universe.n_cells} cells, max abs diff "
                  f"{float(np.max(np.abs(slow - fast))):.2e}")]
    rng = np.random.default_rng(1)
    permuted = _permute_within(rng, universe.y, universe.groups_stratum)
    out.append(_check("engine/a shuffle preserves the pooled marginal exactly",
                      bool(np.allclose(np.sort(permuted), np.sort(universe.y))),
                      f"{len(universe.y)} values, sorted multisets equal"))
    counts_after = np.asarray([int((universe.cell == index).sum())
                               for index in range(universe.n_cells)], np.int64)
    out.append(_check("engine/a shuffle preserves every cell's occurrence count",
                      bool(np.array_equal(counts_after, universe.counts)),
                      f"counts unchanged over {universe.n_cells} cells"))
    resampled = _resample_within(rng, universe.y, universe.groups_stratum)
    out.append(_check("engine/the parametric draw stays inside the marginal",
                      bool(np.isin(resampled, universe.y).all()),
                      "every drawn value is a value the stratum actually held"))
    return out


def _selftest_tautology() -> list[tuple[str, bool, str]]:
    universe, _lift = _synthetic_universe("planted", cells=60, k=6, seed=5)
    block = noise_ceiling(universe, "within_cell", draws=25, mutant=_mutant())
    return [_check("scheme (a)/within-cell shuffle cannot move the maximum",
                   abs(float(block["structure_excess_usd_day"])) < 1e-9
                   and float(block["band_width_usd_day"]) == 0.0,
                   f"excess {block['structure_excess_usd_day']:.2e}, band width "
                   f"{block['band_width_usd_day']:.2e} - a tautology, as stated")]


def _selftest_iid() -> list[tuple[str, bool, str]]:
    """Pure noise: the oracle is order-statistic premium and nothing else.

    The check demands three things at once, and the mutant kills the second: the
    excess must be ~0, the scheme-(b) band must have real width (a cross-cell
    shuffle MOVES the ceiling), and the real oracle must sit inside it.
    """

    mutant = _mutant()
    universe, _lift = _synthetic_universe("iid", cells=200, k=8, seed=11)
    block = noise_ceiling(universe, "cross_cell", draws=200, mutant=mutant)
    real = float(block["real_usd_day"])
    width = float(block["band_width_usd_day"])
    excess = float(block["structure_excess_usd_day"])
    tol = 0.5 * width if width > 0.0 else 0.0
    return [
        _check("iid/the cross-cell band has real width",
               width > 0.0, f"p5 {block['noise_p5_usd_day']:.3f} .. p95 "
               f"{block['noise_p95_usd_day']:.3f}, width {width:.4f}"),
        _check("iid/the real oracle lands inside the noise band",
               width > 0.0 and bool(block["inside_band"]),
               f"real {real:.3f} at percentile "
               f"{block['real_percentile_in_draws']:.1f}"),
        _check("iid/the structure excess is ~0",
               width > 0.0 and abs(excess) <= tol,
               f"excess {excess:.4f} usd vs half-band {tol:.4f}"),
    ]


def _selftest_planted() -> list[tuple[str, bool, str]]:
    """One good moment per cell: the excess must appear, at a known size.

    A cross-cell shuffle keeps the planted bonuses IN THE POOL, so it cannot
    lose all of them: it only loses the cells that end up bonus-free.  With one
    bonus per cell and k occurrences per cell that share is ``(1 - 1/k)^k``, and
    that is exactly the fraction of the plant's oracle lift the excess can
    recover.  The number is a prediction, not a fit - which is what makes this a
    test rather than a description.
    """

    mutant = _mutant()
    k = 8
    universe, lift = _synthetic_universe("planted", cells=400, k=k, seed=17)
    block = noise_ceiling(universe, "cross_cell", draws=200, mutant=mutant)
    real = float(block["real_usd_day"])
    excess = float(block["structure_excess_usd_day"])
    planted = float(lift.sum()) / float(universe.days)
    recovered = excess / planted if planted else float("nan")
    predicted = (1.0 - 1.0 / k) ** k
    return [
        _check("planted/the real oracle clears the noise band",
               bool(block["above_p95"]) and float(block["band_width_usd_day"]) > 0.0,
               f"real {real:.1f} vs p95 {block['noise_p95_usd_day']:.1f}, "
               f"percentile {block['real_percentile_in_draws']:.1f}"),
        _check("planted/the excess is a real fraction of the plant",
               excess > 0.0 and recovered > 0.10,
               f"excess {excess:.1f} of planted oracle lift {planted:.1f} "
               f"= {recovered:.3f} recovered"),
        _check("planted/the recovered fraction matches the analytic (1-1/k)^k",
               abs(recovered - predicted) < 0.06,
               f"recovered {recovered:.3f} vs predicted {predicted:.3f} "
               f"(k={k}); the shortfall is the plant the pool keeps"),
    ]


def _selftest_coarse() -> list[tuple[str, bool, str]]:
    """The coarse grain must be exactly the ordinal-reset markers."""

    stream = S14.Stream(cell=0, asset="HG", d8=20220101, phase="0")
    ordinals = [1, 2, 3, 1, 2, 1, 1, 2]
    for slot, ordinal in enumerate(ordinals):
        x = np.zeros(NFEAT, np.float64)
        x[ORD_SIDE_COL] = float(ordinal)
        stream.occs.append(S14.Occ(
            row=slot, cell=0, asset="HG", d8=20220101, phase="0", side=1,
            bar=slot, k=slot + 1, remaining_s=float(S14.REMAIN_MIN_S + 60),
            payoff=float(slot), x=x, y1800=1, soft_hit=True, delay_s=0.0,
            depth=0.0, side_ok=True, legal=True))
    got = [occ.k for occ in coarse_occs(stream)]
    want = [1, 4, 6, 7]
    reference = S14.side_ordinals([2, 4, 6, 9, 11, 14], [7, 13])
    return [
        _check("coarse/keeps exactly the ordinal-1 reset markers",
               got == want, f"kept k={got}, wanted {want} from {ordinals}"),
        _check("coarse/the reset law it leans on is sweep 14's",
               reference == [1, 2, 3, 1, 2, 1],
               f"side_ordinals reference {reference}"),
        _check("coarse/a fine stream is never smaller than its coarse cut",
               len(coarse_occs(stream)) <= len(stream.occs),
               f"{len(coarse_occs(stream))} of {len(stream.occs)}"),
    ]


def _selftest_strata() -> list[tuple[str, bool, str]]:
    universe, _lift = _synthetic_universe("iid", cells=100, k=8, seed=23)
    covered = np.concatenate(universe.groups_stratum) if universe.groups_stratum \
        else np.zeros(0, np.int64)
    return [
        _check("strata/every occurrence sits in exactly one stratum",
               bool(np.array_equal(np.sort(covered),
                                   np.arange(len(universe.y)))),
               f"{len(covered)} of {len(universe.y)} occurrences, "
               f"{len(universe.stratum_key)} strata"),
        _check("strata/deciles of a constant count collapse to one bin",
               len(universe.stratum_key) == 1,
               f"{len(universe.stratum_key)} stratum for equal-count cells"),
    ]


def selftest() -> int:
    mutant = _mutant()
    print(f"sweep 15 selftest  spec_sha {SPEC_SHA[:16]}  "
          f"code_sha {code_sha()[:16]}  mutant {mutant or 'none'}")
    rows: list[tuple[str, bool, str]] = []
    rows += _selftest_engine()
    rows += _selftest_strata()
    rows += _selftest_coarse()
    rows += _selftest_tautology()
    rows += _selftest_iid()
    rows += _selftest_planted()
    width = max(len(name) for name, _ok, _detail in rows)
    bad = 0
    for name, ok, detail in rows:
        bad += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {name.ljust(width)}  {detail}")
    print(f"\n{len(rows) - bad}/{len(rows)} selftest checks pass")
    return 0 if bad == 0 else 1


# --------------------------------------------------------------------------
# Report and log.
# --------------------------------------------------------------------------

def _key(parts: Sequence[object]) -> str:
    return "/".join(str(part) for part in parts)


def log_rows(report: Mapping[str, object]) -> list[dict[str, object]]:
    ruling = report["decision"]
    params = json.dumps({"draws": DRAWS, "deciles": N_DECILES,
                         "lambda": RIDGE_LAMBDA, "features": NFEAT,
                         "min_prior_days": MIN_PRIOR_DAYS_FIT,
                         "schemes": list(SCHEMES), "grains": list(GRAINS)})
    shared = {
        "registered_utc": report["registered_utc"], "family": FAMILY,
        "params": params, "spec_sha": SPEC_SHA, "code_sha": report["code_sha"],
        "split_sha": report["split_sha"],
        "outcome_law_sha": report["outcome_law_sha"], "null_seed": SEED,
        "parent_trial": PARENT_TRIAL, "selection_rule": SELECTION_RULE,
        "verdict": "",
    }
    rows: list[dict[str, object]] = []
    counter = 0
    usd_field = {"HG": "hg_usd_day", "NKD": "nkd_usd_day", "SI": "si_usd_day"}
    for grain in GRAINS:
        for scope in SCOPES:
            for asset in ASSETS:
                counter += 1
                one = report["m1"][_key((asset, scope, grain))]
                b = report["m2"][_key((asset, scope, grain, "cross_cell"))]
                c = report["m2"][_key((asset, scope, grain, "parametric"))]
                rows.append({
                    **shared, "id": f"sweep15-{counter:03d}",
                    "rule": f"CEILING/{grain}/{scope}/{asset}",
                    "days": one["days"],
                    "coverage": one["coverage_of_certifiable"],
                    usd_field[asset]: one["oracle_usd_day"],
                    "null_margin": b["share_draws_ge_real"],
                    "note": (
                        f"real oracle {one['oracle_usd_day']:.1f} usd/day over "
                        f"{one['cells_with_occurrences']} cells, "
                        f"{one['occurrences']} occ ("
                        f"{one['occurrence_counts'].get('mean', 0):.1f}/cell); "
                        f"scheme(b) mean {b['noise_mean_usd_day']:.1f} "
                        f"[{b['noise_p5_usd_day']:.1f},{b['noise_p95_usd_day']:.1f}] "
                        f"excess {b['structure_excess_usd_day']:+.1f} pct "
                        f"{b['real_percentile_in_draws']:.1f}; scheme(c) mean "
                        f"{c['noise_mean_usd_day']:.1f} excess "
                        f"{c['structure_excess_usd_day']:+.1f}")[:400],
                })
    for asset in ASSETS:
        counter += 1
        block = report["m3"][asset]
        band = block["conditional_mean_band"] or {}
        rows.append({
            **shared, "id": f"sweep15-{counter:03d}",
            "rule": f"PREDICTABLE/{asset}",
            "days": block["folds"],
            "note": (
                f"oof R2 Y {block['Y']['oof_r2_pooled']}, |Y| "
                f"{block['absY']['oof_r2_pooled']}, sign(Y) "
                f"{block['signY']['oof_r2_pooled']}; in-fold Y "
                f"{block['Y']['in_fold_r2_mean']}; E[Y|s] p5-p95 spread "
                f"{band.get('fitted_spread_usd')} vs Y spread "
                f"{band.get('y_spread_usd')} over {block['Y']['oof_rows']} "
                f"out-of-fold rows")[:400],
        })
    for grain in GRAINS:
        counter += 1
        one = ruling["by_grain"][grain]
        detail = "; ".join(
            f"{a} real {one['by_asset'][a]['real_usd_day']:.0f} vs p95 "
            f"{one['by_asset'][a]['noise_p95']:.0f} excess "
            f"{one['by_asset'][a]['structure_excess_usd_day']:+.0f} vs rung "
            f"{one['by_asset'][a]['rung_usd_day']:.0f}" for a in DECIDING)
        rows.append({
            **shared, "id": f"sweep15-{counter:03d}",
            "rule": f"RULING/{grain}",
            "days": sum(report["m1"][_key((a, "scoring", grain))]["days"]
                        for a in ASSETS),
            "note": f"{one['verdict']} ({grain} grain, scoring scope): {detail}"[:400],
        })
    return rows


def write_report(report: Mapping[str, object]) -> None:
    OUT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True,
                                   default=S8._json_default) + "\n")


# --------------------------------------------------------------------------
# Entry point.
# --------------------------------------------------------------------------

def run() -> dict[str, object]:
    mutant = _mutant()
    started = time.time()
    cells, asset_days, _skipped = S8.build_cells(ASSETS)
    explore_days = S1._explore_days(ASSETS)
    tape = S9.load_tape(cells)
    forecast = S9.forecast_variance(cells)
    plane = S9.build_plane(cells, forecast, tape)
    states = S12.day_states({asset: explore_days[asset] for asset in ASSETS})
    streams, counters = S14.build_streams(plane, cells, states, "")
    causal = S14.assert_causal(streams, plane)
    if not (causal["no_outcome_in_features"] and causal["rows_match_plane"]
            and causal["stream_is_chronological"]):
        raise SweepRefusal("sweep 14's occurrence stream failed its own "
                           "causality assertions; nothing past here is believed")

    census = plane.stratum_day_cells
    scoring = sweep14_scoring_days(explore_days, census)
    day_sets = {"scoring": scoring,
                "all": {asset: sorted({stream.d8 for stream in streams
                                       if stream.asset == asset})
                        for asset in ASSETS}}

    universes: dict[tuple[str, str, str], Universe] = {}
    m1: dict[tuple[str, str, str], dict[str, object]] = {}
    for scope in SCOPES:
        for asset in ASSETS:
            days = set(int(day) for day in day_sets[scope][asset])
            subset = [s for s in streams if s.asset == asset and s.d8 in days]
            certifiable = sum(int(census.get((asset, slot, day), 0))
                              for day in days for slot in PHASES)
            for grain in GRAINS:
                universe = build_universe(subset, asset, scope, grain,
                                          len(days), certifiable)
                universes[(asset, scope, grain)] = universe
                m1[(asset, scope, grain)] = m1_block(universe)

    repro = reproduce(plane, scoring, m1)
    if not repro["matches"]:
        raise SweepRefusal("the sweep-9 plane or the sweep-14 banked oracle did "
                           "not reproduce; no measurement is believed past here")

    m2: dict[tuple[str, str, str, str], dict[str, object]] = {}
    for key, universe in universes.items():
        for scheme in SCHEMES:
            m2[key + (scheme,)] = noise_ceiling(universe, scheme, DRAWS, SEED,
                                                mutant)

    m3 = predictable_component(streams, explore_days, scoring)

    m4: dict[tuple[str, str], list[dict[str, object]]] = {}
    for grain in GRAINS:
        for scope in SCOPES:
            m4[(grain, scope)] = [
                m4_row(asset, m1[(asset, scope, grain)],
                       m2[(asset, scope, grain, "cross_cell")])
                for asset in ASSETS]

    ruling = decide(m1, m2, "scoring")
    return {
        "schema": "QRE2MILLSWEEP15", "spec_sha": SPEC_SHA, "code_sha": code_sha(),
        "split_sha": S1.split_sha(), "outcome_law_sha": S1.outcome_law_sha(),
        "seed": SEED, "draws": DRAWS, "mutant": mutant, "family": FAMILY,
        "parent_trial": PARENT_TRIAL, "selection_rule": SELECTION_RULE,
        "registered_utc": S14.report_stamp(),
        "asset_days": {a: int(asset_days.get(a, 0)) for a in ASSETS},
        "explore_days": {a: len(explore_days[a]) for a in ASSETS},
        "scoring_days": {a: list(scoring[a]) for a in ASSETS},
        "reproduction": repro, "stream_counters": counters, "causality": causal,
        "m1": {_key(k): v for k, v in m1.items()},
        "m2": {_key(k): v for k, v in m2.items()},
        "m3": m3,
        "m4": {_key(k): v for k, v in m4.items()},
        "decision": ruling,
        "reference_lines": {"causal_best_usd_day": CAUSAL_BEST_USD_DAY,
                            "per_trade_req_brief_usd": PER_TRADE_REQ_BRIEF},
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
    print(f"sweep 15 spec_sha {SPEC_SHA[:16]} code_sha {code_sha()[:16]} "
          f"seed {SEED} draws {DRAWS} mutant {report['mutant'] or 'none'}")
    print_repro(report["reproduction"])
    print(f"\nstreams {report['stream_counters']['streams']} cells, "
          f"{report['stream_counters']['occs']} occurrences; explore days "
          f"{report['explore_days']}; scoring days "
          f"{ {a: len(v) for a, v in report['scoring_days'].items()} }")
    m1 = {tuple(k.split("/")): v for k, v in report["m1"].items()}
    m2 = {tuple(k.split("/")): v for k, v in report["m2"].items()}
    m4 = {tuple(k.split("/")): v for k, v in report["m4"].items()}
    print_m1(m1)
    print_m2(m2, "scoring")
    print_m2(m2, "all")
    print_m3(report["m3"])
    print_m4(m4)
    print_decision(report["decision"])
    write_report(report)
    print(f"\nwrote {OUT_PATH} in {report['elapsed_s']} s")
    if args.log:
        written = S1.append_log(log_rows(report))
        print(f"appended {written} hypothesis-log rows to {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
