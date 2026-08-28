#!/usr/bin/env python3
"""Sweep 17 of the side-resolution mill: hold versus break, CONDITIONAL on size.

At an extreme the trade SIDE is given by the extreme; the open question is
whether the extreme HOLDS or BREAKS.  On this fade stream that question is
exactly ``sign(Y)``: Y > 0 is the fade paying (the extreme held), Y < 0 is the
fade losing (the extreme broke).

Sweep 15 measured the two halves separately and got opposite answers.  The
16-feature state PREDICTS |Y| out of fold (R2 +0.119 HG, +0.127 NKD, +0.096 SI)
and does NOT predict sign(Y) unconditionally (out-of-fold R2 -0.092/-0.106/-0.053).
The state knows a big move is coming and does not know which way it resolves.

The USER's hypothesis is that this is an ORDERING, not a dead end: size comes
first, absorption evidence then resolves hold versus break.  If that is right,
sign(Y) is unpredictable POOLED and predictable INSIDE the high-magnitude
subset, and the deciding input there is absorption - heavy aggression into a
level that does not move the level.

Four measurements, all out of fold, nothing selected on anything scored:
  T1  base rates by out-of-fold magnitude decile - does a predicted-big move
      hold more often or less often?  The USER's direct question.
  T2  conditional sign - fit sign(Y) inside the high-m subset only.
  T3  absorption composition - does absorption evidence carry that fit, as a
      model cut and as a discrete present/absent cut.
  T4  antifade pricing - the CONTINUE side priced through the frozen outcome
      law with the flipped side, never by negating Y.

Machinery is imported, never re-implemented: sweep 14 owns the occurrence
stream, the 16-feature plane, the label Y_k, the fold law and the ridge; sweep 9
owns the row plane; sweep 8 owns the cell build and the flow/zone cache load;
sweep 1 owns the outcome law, the rungs and the log.
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

import mill as M  # noqa: F401  (the loader package the caches hang off)
import context as CTX  # noqa: F401
import flow as FLOW
import flow_zones as ZONES
import sweep1 as S1
import sweep8 as S8
import sweep9_twins as S9
import sweep12 as S12
import sweep14 as S14

# --------------------------------------------------------------------------
# The law, registered before anything is read.
# --------------------------------------------------------------------------

SPEC = """QRE2MILLSWEEP17
tier=exploratory; EXPLORE-only; MEASUREMENT ONLY.  Parent = sweep15-016.
  Family F14-CONDSIGN.  Seed 20260827.  USER-directed.  No policy is selected
  on anything measured here; Y is read as a label.  The flow composite as a
  POLICY stays closed - T3 is a measurement of the interaction only.
DATA LAW.  EXPLORE days only, off the existing mill caches.  No packs, no HOLD,
  no teacher labels, no 2021, no 2025H2.  No cache is rebuilt.  The occurrence
  stream is sweep 14's, built by calling its own ``build_streams`` on sweep 9's
  row plane; Y_k is sweep 14's exact cash label ``make_entry(...).cert_usd``.
GATE, refuse to run unless every counter matches exactly: plane rows 47402;
  certifiable cells HG 138 NKD 132 SI 132; candidates_seen 313131;
  cells_with_rows 385; scoring days HG 41 NKD 40 SI 39.
PLANE AND FOLDS.  Sweep 14's 16 features, sweep 14's fold law (per-day folds,
  training days STRICTLY prior, at least 25 prior EXPLORE days, at least 50
  training rows, training-column-mean imputation), ridge lambda 1.0 with the
  intercept unpenalised on standardised features (``S14.Sums``/``S14.Ridge``).
MAGNITUDE SCORE m.  For each scoring day d, ridge on |Y| fitted on the days
  strictly before d, predicted onto day d's rows.  m is OUT OF FOLD on every
  scored row.  SUBSET THRESHOLDS - the quartile and decile cuts of m, and the
  decile edges - are computed on the TRAIN-day m values only, per asset, per
  fold, and never see day d.  The train-day m is in fold and is used for
  NOTHING but the cut.
T1 BASE RATES.  Per asset, per out-of-fold m-decile: n, P(Y>0) with Wilson 95%
  bounds, mean Y, median Y, mean |Y|.  Answers whether extremes hold more or
  less often when a big move is predicted.
T2 CONDITIONAL SIGN.  Restricted to the top-quartile and top-decile m rows.
  Inside the restriction, sign(Y) is fitted walk-forward on the TRAIN-day
  high-m rows and evaluated on day d's high-m rows, ridge on the +/-1 sign and
  logistic (Newton, L2 lambda 1.0, intercept unpenalised).  Reported per asset
  per subset per variant: out-of-fold accuracy against 0.5 and against the
  always-fade base rate P(Y>0), AUC, and the cash cut - mean Y and usd/day of
  the predicted-positive rows against abstain-all (0 usd/day by construction).
  REPORTED BESIDE THE REGISTERED NUMBERS, not substituted for them: the
  MAJORITY-class rate max(P(Y>0), 1-P(Y>0)) and the AUC z.  Where P(Y>0) sits
  far below 0.5 the always-fade comparator is weak - answering "break" on most
  rows clears it without discriminating - so a large excess over the base rate
  beside a negative excess over the majority class and an AUC z near zero is a
  low base rate, not a finding.  The letter below stays as registered; the
  decision table carries a STRICT column that additionally requires beating
  the majority class and AUC > 0.5, so the letter cannot be over-read.
  The UNCONDITIONAL sign fit (all train rows, all day-d rows) is the baseline;
  sweep 15 measured it negative.
T3 ABSORPTION COMPOSITION.  Eight absorption features joined causally to each
  occurrence from the EXISTING flow cache (``flow.load_flow``) and zone cache
  (``flow_zones.load_zones``), at minute grain.  Raw flow bar j closes at
  ``bar_close_ts_ns[j] = phase_open + (j+1)*60 s`` and reads only rows with
  ``ts_recv_ns < bar_close_ts_ns[j]``, so the raw window is ``[bar-10, bar)``
  and its last bar closes exactly AT the stamp.  The ZONE cache is already on
  the mill lattice (``build_flow_zones.to_lattice``: flow bar j-1 closes at
  mill bar j), so its state series are read at ``bar`` itself and cover the
  same minutes.  The run asserts ``max(bar_close[bar-1] - stamp) <= 0`` over
  every row and refuses otherwise.  (a) MODEL CUT: refit T2 on the 16+8
  features; does out-of-fold accuracy and the cash cut improve.  (b) DISCRETE
  CUT: absorption-present versus absent inside the high-m rows, where present
  is the top tercile of the absorption composite, the cut taken on the TRAIN-day
  high-m rows per asset per phase (adaptive; no absolute constants; asset-pooled
  fallback under 30 train rows in a phase).  Reported: P(Y>0) with Wilson bounds
  and mean Y in both cells, per asset.
T4 ANTIFADE PRICING.  On the top-decile and top-quartile m rows, the CONTINUE
  side's cert for every row through the frozen outcome law with the FLIPPED
  side - ``S1.make_entry(position, rec, bar, -side)`` - never by negating Y.
  The -900 wall applies to the held position, so the two sides carry different
  walls and different exits; the run reports how often both sides wall and how
  far the flipped cert sits from -Y.  Ten rows are hand-checked by replaying
  ``MillIndex.outcome()`` off the shard against the batch path.  Reported per
  asset per subset: mean continue-side cert, P(cert > 0) with Wilson bounds,
  and usd/day entering WITH the move on every row of the subset.
NULLS, pre-registered.  Block permutation preserving asset-day blocks, 2000
  draws, seed 20260827, one shared permutation per (draw, asset) so the cells
  of a family move together.  Three families: SIGN (statistic = out-of-fold
  accuracy minus the subset base rate, sign labels permuted), CASH (statistic =
  usd/day of the predicted-positive rows, Y permuted), ANTIFADE (statistic =
  continue-side usd/day on the subset, the continue certs permuted).  The
  family is subsets x assets x variants - a superset of the pre-registered
  subsets x assets, so the adjustment is conservative.  Adjusted p is the
  studentised max-T: every cell is centred and scaled by its own null draws,
  the row-wise max over the family is taken per draw, and adjusted p =
  (1 + #{max >= observed z}) / (1 + draws).  Every headline carries one.
LETTERS, pre-registered.  CONDSIGN fires when T2 or T3(a) accuracy beats the
  base rate with adjusted p <= 0.05 AND the predicted-positive cash cut is
  positive, on a deciding asset (NKD or SI).  ANTIFADE fires when T4 usd/day is
  positive with adjusted p <= 0.05 on a deciding asset.  NONE otherwise.  Both
  letters can fire.  NKD and SI decide; HG is report-only.
MUTANT.  QRE2_MILL_S17_MUTANT=subset_threshold_uses_test_day computes the
  subset thresholds on day d's OWN m values instead of the train days' - the
  maximal violation of "never using day d" - and must flip the planted
  conditional case red.  The weaker pooled form,
  subset_threshold_pools_test_day, appends day d's m to the train pool and is
  reported beside it so the strength of each leak is on the record.
"""

ASSETS = S1.ASSETS
DECIDING = ("NKD", "SI")
REPORT_ONLY = ("HG",)
PHASES = S14.PHASES
SEED = 20260827

# Frozen, inherited.  Aliases so a drift upstream fails loudly here.
DAY_RUNG_USD = S1.DAY_RUNG_USD                    # HG 2000, NKD 1500, SI 1500
MIN_PRIOR_DAYS_FIT = S14.MIN_PRIOR_DAYS_FIT       # 25
MIN_FIT_ROWS = S14.MIN_FIT_ROWS                   # 50
RIDGE_LAMBDA = S14.RIDGE_LAMBDA                   # 1.0
NFEAT = S14.NFEAT                                 # 16
FEATURES = S14.FEATURES

# The refuse-to-run gates, restated from the brief and from sweep 14.
REPRO_ROWS = S14.REPRO_ROWS                       # 47402
REPRO_CERTIFIABLE = S14.REPRO_CERTIFIABLE         # 138/132/132
REPRO_COUNTERS = S14.REPRO_COUNTERS
REPRO_SCORING_DAYS = {"HG": 41, "NKD": 40, "SI": 39}

# Sweep 15's measured out-of-fold R2, carried as context and never recomputed.
SWEEP15_OOF_R2 = {"HG": {"absY": 0.1192, "signY": -0.0915},
                  "NKD": {"absY": 0.1265, "signY": -0.1063},
                  "SI": {"absY": 0.0964, "signY": -0.0525}}

# Subsets.  The cut is a quantile of the TRAIN-day m values.
SUBSETS = ("quartile", "decile")
SUBSET_Q = {"quartile": 0.75, "decile": 0.90}
VARIANTS = ("ridge16", "logit16", "ridge24", "logit24")
BASE_VARIANTS = ("ridge16", "logit16")
ABS_VARIANTS = ("ridge24", "logit24")
N_DECILES = 10

# Absorption: the 10 bars ENDING AT bar-1, so every value closed at or before
# the occurrence stamp.
ABS_WINDOW = 10
ABS_FEATURES = ("attack_share", "yield_per_attack", "reload_per_attack",
                "twoside_share", "onesided", "size_ratio", "held_per_touch",
                "ext_per_attack")
NABS = len(ABS_FEATURES)
NFEAT24 = NFEAT + NABS
# The composite's sign convention: +1 where a HIGHER value means MORE
# absorption, -1 where a higher value means the level is giving way.
ABS_COMPOSITE_SIGN = {"attack_share": 0.0, "yield_per_attack": -1.0,
                      "reload_per_attack": +1.0, "twoside_share": +1.0,
                      "onesided": -1.0, "size_ratio": +1.0,
                      "held_per_touch": +1.0, "ext_per_attack": -1.0}
ABS_TERCILE = 2.0 / 3.0
ABS_MIN_PHASE_ROWS = 30
EPS = 1e-12

NULL_DRAWS = 2000
ALPHA = 0.05
FAMILIES = ("SIGN", "CASH", "ANTIFADE")

LOGIT_ITERS = 40
LOGIT_TOL = 1e-9
ETA_CAP = 30.0

HANDCHECK_ROWS = 10
HANDCHECK_TOL_USD = 1e-6

FAMILY = "F14-CONDSIGN"
PARENT_TRIAL = "sweep15-016"
SELECTION_RULE = ("none: pre-registered subsets, lambda 1.0, thresholds from "
                  "train days only, no threshold tuning, no variant choice")

MUTANT_ENV = "QRE2_MILL_S17_MUTANT"
MUTANT_TESTDAY = "subset_threshold_uses_test_day"
MUTANT_POOLED = "subset_threshold_pools_test_day"
MUTANTS = (MUTANT_TESTDAY, MUTANT_POOLED)

OUT_PATH = ROOT / ".audit/mill-sweep17.json"
LOG_PATH = S1.LOG_PATH


class SweepRefusal(RuntimeError):
    pass


SPEC_SHA = S1._sha_text(SPEC)


def code_sha() -> str:
    return S1._sha_file(Path(__file__).resolve())


def _mutant() -> str:
    name = os.environ.get(MUTANT_ENV, "")
    if name and name not in MUTANTS:
        raise SweepRefusal(f"unknown sweep-17 mutant {name!r}; known: {MUTANTS}")
    return name


_n = S14._n
_check = S14._check


def _f(value: object, digits: int = 4) -> str:
    """Fixed-point text that survives a ``None`` - log notes are not optional."""

    if value is None:
        return "-"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


# --------------------------------------------------------------------------
# Small statistics, all closed form.
# --------------------------------------------------------------------------

def wilson(hits: int, total: int) -> tuple[float | None, float | None]:
    if total <= 0:
        return (None, None)
    lo, hi = S1.wilson(int(hits), int(total))
    return (float(lo), float(hi))


def _rank_average(values: np.ndarray) -> np.ndarray:
    """Ranks with ties averaged, 1-based."""

    order = np.argsort(values, kind="stable")
    ordered = values[order]
    ranks = np.empty(len(values), np.float64)
    start = 0
    for index in range(1, len(ordered) + 1):
        if index == len(ordered) or ordered[index] != ordered[start]:
            ranks[order[start:index]] = 0.5 * (start + index + 1)
            start = index
    return ranks


def auc(labels: np.ndarray, scores: np.ndarray) -> float | None:
    """Mann-Whitney AUC of ``scores`` against the 0/1 ``labels``."""

    good = np.isfinite(scores)
    labels = np.asarray(labels, np.float64)[good]
    scores = np.asarray(scores, np.float64)[good]
    positives = float(labels.sum())
    negatives = float(len(labels) - positives)
    if positives <= 0.0 or negatives <= 0.0:
        return None
    ranks = _rank_average(scores)
    return float((ranks[labels > 0.5].sum() - positives * (positives + 1.0) / 2.0)
                 / (positives * negatives))


def logistic_fit(x: np.ndarray, y01: np.ndarray, lam: float = RIDGE_LAMBDA
                 ) -> tuple[np.ndarray, np.ndarray, float, np.ndarray] | None:
    """Newton-Raphson logistic with L2 on the slopes, intercept unpenalised.

    Standardised exactly the way ``S14.Sums`` standardises, so the ridge and
    the logistic see the same design and the comparison between them is about
    the link and nothing else.
    """

    x = np.asarray(x, np.float64)
    y01 = np.asarray(y01, np.float64)
    if x.ndim != 2 or len(x) < 2:
        return None
    mean = x.mean(axis=0)
    sd = x.std(axis=0)
    sd = np.where(sd <= 1e-12, 1.0, sd)
    z = (x - mean) / sd
    n, width = z.shape
    rate = float(np.clip(y01.mean(), 1e-6, 1.0 - 1e-6))
    intercept = float(math.log(rate / (1.0 - rate)))
    beta = np.zeros(width, np.float64)
    design = np.hstack([np.ones((n, 1), np.float64), z])
    penalty = np.diag(np.concatenate([[0.0], np.full(width, float(lam))]))
    for _ in range(LOGIT_ITERS):
        eta = np.clip(intercept + z @ beta, -ETA_CAP, ETA_CAP)
        mu = 1.0 / (1.0 + np.exp(-eta))
        weight = np.maximum(mu * (1.0 - mu), 1e-6)
        hessian = design.T @ (weight[:, None] * design) + penalty
        gradient = design.T @ (y01 - mu) - penalty @ np.concatenate(
            [[0.0], beta])
        try:
            step = np.linalg.solve(hessian, gradient)
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(hessian, gradient, rcond=None)[0]
        if not np.all(np.isfinite(step)):
            return None
        intercept += float(step[0])
        beta = beta + step[1:]
        if float(np.max(np.abs(step))) < LOGIT_TOL:
            break
    return mean, sd, intercept, beta


def logistic_score(fit: tuple[np.ndarray, np.ndarray, float, np.ndarray],
                   x: np.ndarray) -> np.ndarray:
    """The linear predictor.  Monotone in p, so it ranks and thresholds alike.

    ``eta > 0`` is exactly ``p > 0.5``, so one array serves the accuracy cut and
    the AUC ranking without a second transform.
    """

    mean, sd, intercept, beta = fit
    return intercept + ((np.asarray(x, np.float64) - mean) / sd) @ beta


# --------------------------------------------------------------------------
# The absorption block: joined causally off the existing flow and zone caches.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class AbsorptionJoin:
    """The per-occurrence absorption features and the causality evidence."""

    values: dict[int, np.ndarray]          # plane row -> (NABS,)
    counters: dict[str, int]
    max_close_minus_stamp_ns: int
    worst_row: int


def _window_sum(series: np.ndarray, lo: int, hi: int) -> float:
    """Sum over the HALF-OPEN bar span ``[lo, hi)``; ``hi`` is exclusive."""

    if hi <= lo:
        return 0.0
    return float(np.asarray(series[lo:hi], np.float64).sum())


def absorption_vector(flow: Mapping[str, np.ndarray], zside: object, side: int,
                      bar: int) -> np.ndarray:
    """The eight absorption features at ``bar``, read from bars < ``bar``.

    Every quantity is a RATIO, so nothing here carries an absolute constant and
    nothing needs calibrating before it can be a feature.  The direction of
    each is fixed in ``ABS_COMPOSITE_SIGN``: absorption is heavy aggression into
    a level that does not move the level, so a high attack share with a low
    yield-per-attack, a high reload-per-attack, two-sided tape and few extension
    ticks per unit attack is what "absorbed" looks like.
    """

    tag = "low" if int(side) > 0 else "high"
    lo = max(0, int(bar) - ABS_WINDOW)
    hi = int(bar)                               # exclusive: raw bar-1 is last
    vol = _window_sum(flow["vol"], lo, hi)
    delta = _window_sum(flow["delta"], lo, hi)
    twoside = _window_sum(flow["twoside"], lo, hi)
    attack = _window_sum(flow[f"attack_{tag}"], lo, hi)
    yielded = _window_sum(flow[f"yield_{tag}"], lo, hi)
    reload = _window_sum(flow[f"reload_{tag}"], lo, hi)
    prior_vol = np.asarray(flow["vol"][:hi], np.float64)
    baseline = float(prior_vol.mean()) if len(prior_vol) else 0.0
    span = float(hi - lo)

    # The ZONE cache is already on the mill lattice - ``build_flow_zones``
    # applies ``to_lattice``, so zone index j holds flow bar j-1, the bar that
    # closes AT lat[j].  Reading it at ``bar`` is therefore strictly prior, and
    # it lines up exactly with the raw-flow window ``[bar-W, bar)`` above.
    series = zside.series
    last = int(bar)
    touches = float(series["touches_so_far"][last])
    held = float(series["held_so_far"][last])
    cum_attack = float(series["cum_attack"][last])
    cum_ext = float(series["cum_ext_ticks"][last])

    def ratio(top: float, bottom: float) -> float:
        return float(top / bottom) if bottom > EPS else float("nan")

    return np.asarray([
        ratio(attack, vol),
        ratio(yielded, attack),
        ratio(reload, attack),
        ratio(twoside, vol),
        ratio(abs(delta), vol),
        ratio(vol / span if span > 0.0 else 0.0, baseline),
        ratio(held, touches),
        ratio(cum_ext, cum_attack),
    ], np.float64)


def build_absorption(streams: Sequence[S14.Stream], cells: Sequence[S8.Cell8]
                     ) -> AbsorptionJoin:
    """One pass over the day shards, joining absorption onto every occurrence.

    The flow and zone caches are READ, never rebuilt.  Sweep 8 already refused
    any cell whose day lacked a flow or zone shard, so every stream here has
    one; a miss is still counted rather than assumed away.
    """

    by_position = {cell.position: cell for cell in cells}
    values: dict[int, np.ndarray] = {}
    counters = {"rows": 0, "joined": 0, "missing_cell": 0, "short_arrays": 0,
                "bar_zero": 0, "nonfinite": 0}
    worst = -(1 << 62)
    worst_row = -1
    cache: dict[tuple[str, int], tuple[dict, dict]] = {}
    blank = np.full(NABS, np.nan, np.float64)
    for stream in sorted(streams, key=lambda s: (s.asset, s.d8, s.cell)):
        cell = by_position[stream.cell]
        rec = cell.rec
        key = (cell.asset, int(cell.d8))
        if key not in cache:
            cache.clear()               # one day resident at a time
            cache[key] = (FLOW.load_flow(cell.asset, int(cell.d8)),
                          ZONES.load_zones(cell.asset, int(cell.d8)))
        flow_day, zones_day = cache[key]
        cell_key = (rec.phase, int(rec.phase_open_ts_ns))
        flow = flow_day.get(cell_key)
        zcell = zones_day.get(cell_key)
        for occ in stream.occs:
            counters["rows"] += 1
            if flow is None or zcell is None:
                counters["missing_cell"] += 1
                values[occ.row] = blank
                continue
            bar = int(occ.bar)
            if bar < 1:
                counters["bar_zero"] += 1
                values[occ.row] = blank
                continue
            if len(flow["vol"]) < bar or len(zcell.sides[occ.side].series[
                    "touches_so_far"]) <= bar:
                counters["short_arrays"] += 1
                values[occ.row] = blank
                continue
            # The causal receipt: bar-1 closes at or before the stamp.
            gap = int(flow["bar_close_ts_ns"][bar - 1]) - int(rec.lat[bar])
            if gap > worst:
                worst = gap
                worst_row = int(occ.row)
            vector = absorption_vector(flow, zcell.sides[occ.side], occ.side, bar)
            if not bool(np.all(np.isfinite(vector))):
                counters["nonfinite"] += 1
            values[occ.row] = vector
            counters["joined"] += 1
    return AbsorptionJoin(values=values, counters=counters,
                          max_close_minus_stamp_ns=int(worst),
                          worst_row=int(worst_row))


# --------------------------------------------------------------------------
# The continue side, priced through the frozen law with the flipped side.
# --------------------------------------------------------------------------

def build_continue(streams: Sequence[S14.Stream], cells: Sequence[S8.Cell8]
                   ) -> tuple[dict[int, float], dict[int, bool], dict[str, int]]:
    """``make_entry(..., -side)`` per occurrence: the CONTINUE side's own cert.

    Never ``-Y``.  Sweep 1 built ``cert_p`` and ``cert_m`` from two separate
    ``outcomes_grid`` calls, one per side, each with its own -900 boundary and
    its own first-crossing search, so the two sides carry different walls and
    different exits.  The flipped side can also be ILLEGAL at a bar the faded
    side is legal at, which is counted and never imputed.
    """

    by_position = {cell.position: cell for cell in cells}
    cert: dict[int, float] = {}
    legal: dict[int, bool] = {}
    counters = {"rows": 0, "legal": 0, "illegal": 0}
    for stream in streams:
        rec = by_position[stream.cell].rec
        for occ in stream.occs:
            counters["rows"] += 1
            made = S1.make_entry(stream.cell, rec, int(occ.bar), -int(occ.side))
            if made is None:
                counters["illegal"] += 1
                cert[occ.row] = float("nan")
                legal[occ.row] = False
                continue
            counters["legal"] += 1
            cert[occ.row] = float(made.cert_usd)
            legal[occ.row] = True
    return cert, legal, counters


def handcheck_continue(streams: Sequence[S14.Stream], cells: Sequence[S8.Cell8],
                       cert: Mapping[int, float], rows: int = HANDCHECK_ROWS
                       ) -> dict[str, object]:
    """Replay ``MillIndex.outcome()`` off the shard against the batch path.

    The batch path is sweep 1's vectorised ``outcomes_grid``; this walks the
    scalar ``outcome()`` on the same shard, same stamp, same flipped side, and
    the two must agree to the float.  It is the only place the flipped-side
    price is checked against the engine rather than against a cache.
    """

    by_position = {cell.position: cell for cell in cells}
    picked: list[S14.Occ] = []
    for index, asset in enumerate(ASSETS):
        # Spread the quota evenly and hand the remainder to the first assets,
        # so the check is exactly ``rows`` rows and every asset is represented.
        per_asset = rows // len(ASSETS) + (1 if index < rows % len(ASSETS)
                                           else 0)
        split: list[S14.Occ] = []
        same: list[S14.Occ] = []
        for stream in sorted((s for s in streams if s.asset == asset),
                             key=lambda s: (s.d8, s.cell)):
            rec = by_position[stream.cell].rec
            for occ in stream.occs:
                if not np.isfinite(cert.get(occ.row, float("nan"))):
                    continue
                # Prefer a row where the two sides wall DIFFERENTLY: that is
                # the case negating Y would get wrong, so it is the case worth
                # checking against the engine.
                if bool(rec.wall(occ.side)[occ.bar]) != bool(
                        rec.wall(-occ.side)[occ.bar]):
                    split.append(occ)
                else:
                    same.append(occ)
                break
            if len(split) >= per_asset:
                break
        picked.extend((split + same)[:per_asset])
    picked = picked[:rows]
    checked: list[dict[str, object]] = []
    worst = 0.0
    for occ in picked:
        cell8 = by_position[occ.cell]
        rec = cell8.rec
        shard = M.load_shard(cell8.asset, int(cell8.d8))
        try:
            cellm = shard.cell(rec.phase, int(rec.phase_open_ts_ns))
            live = shard.outcome_at(cellm, -int(occ.side), int(rec.lat[occ.bar]))
        finally:
            shard.close()
        batch = float(cert[occ.row])
        got = float("nan") if live is None else float(live.cert_close_usd)
        delta = abs(got - batch) if np.isfinite(got) else float("inf")
        worst = max(worst, delta)
        checked.append({
            "asset": cell8.asset, "d8": int(cell8.d8), "phase": rec.phase,
            "bar": int(occ.bar), "fade_side": int(occ.side),
            "continue_side": -int(occ.side),
            "stamp_ns": int(rec.lat[occ.bar]),
            "batch_cert_usd": batch, "outcome_call_cert_usd": got,
            "abs_delta_usd": delta,
            "fade_cert_usd": float(occ.payoff),
            "fade_wall": bool(rec.wall(occ.side)[occ.bar]),
            "continue_wall": bool(rec.wall(-occ.side)[occ.bar]),
            "negation_gap_usd": batch + float(occ.payoff),
        })
    return {"rows": len(checked), "max_abs_delta_usd": float(worst),
            "matches": bool(checked and worst <= HANDCHECK_TOL_USD),
            "checked": checked}


# --------------------------------------------------------------------------
# The walk-forward pass: m, the subsets, the sign fits, the absorption cut.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Table:
    """Every out-of-fold scoring row, flattened.  One row is one occurrence."""

    asset: np.ndarray
    d8: np.ndarray
    phase: np.ndarray
    side: np.ndarray
    y: np.ndarray
    m: np.ndarray
    decile: np.ndarray
    subset: dict[str, np.ndarray] = field(default_factory=dict)
    score: dict[tuple[str, str], np.ndarray] = field(default_factory=dict)
    uncond: dict[str, np.ndarray] = field(default_factory=dict)
    absorb_present: dict[str, np.ndarray] = field(default_factory=dict)
    absorb_z: dict[str, np.ndarray] = field(default_factory=dict)
    cont: np.ndarray = field(default=None)      # type: ignore[assignment]

    @property
    def n(self) -> int:
        return int(len(self.y))


def _cut_pool(m_train: np.ndarray, m_test: np.ndarray, mutant: str
              ) -> np.ndarray:
    """The values a threshold may be taken over.

    The law is TRAIN ONLY.  ``subset_threshold_uses_test_day`` swaps in day d's
    own values, the maximal violation; ``subset_threshold_pools_test_day``
    appends them, the weaker pooled form.  Both are reported so the record shows
    which leak is the one with teeth.
    """

    if mutant == MUTANT_TESTDAY:
        return m_test
    if mutant == MUTANT_POOLED:
        return np.concatenate([m_train, m_test])
    return m_train


def _standardise_train(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = matrix.mean(axis=0)
    sd = matrix.std(axis=0)
    return mean, np.where(sd <= 1e-12, 1.0, sd)


def _composite(values: np.ndarray, mean: np.ndarray, sd: np.ndarray
               ) -> np.ndarray:
    """The absorption composite: the signed mean of the standardised parts."""

    weights = np.asarray([ABS_COMPOSITE_SIGN[name] for name in ABS_FEATURES],
                         np.float64)
    z = (np.asarray(values, np.float64) - mean) / sd
    z = np.where(np.isfinite(z), z, 0.0)
    live = float(np.abs(weights).sum())
    return (z @ weights) / live if live > 0.0 else np.zeros(len(z))


def _fit_sign(x: np.ndarray, y: np.ndarray, variant: str):
    """One sign fit.  ``ridge*`` is S14's ridge on +/-1; ``logit*`` is the IRLS."""

    if variant.startswith("ridge"):
        target = np.where(y > 0.0, 1.0, -1.0)
        sums = S14.Sums(width=x.shape[1])
        sums.add(x, target, target)
        return sums.fit("Y", RIDGE_LAMBDA)
    return logistic_fit(x, (y > 0.0).astype(np.float64), RIDGE_LAMBDA)


def _score_sign(fit, x: np.ndarray, variant: str) -> np.ndarray:
    if variant.startswith("ridge"):
        return np.asarray(fit.predict(x), np.float64)
    return logistic_score(fit, x)


def walk_forward(streams: Sequence[S14.Stream],
                 explore_days: Mapping[str, Sequence[int]],
                 scoring_days: Mapping[str, Sequence[int]],
                 absorb: Mapping[int, np.ndarray] | None,
                 cont: Mapping[int, float] | None,
                 mutant: str = "") -> tuple[Table, dict[str, object]]:
    """One pass: the magnitude fit, the subset cuts, every sign fit.

    Sweep 14's fold law verbatim - training days strictly prior, at least 25 of
    them, at least 50 training rows, training-column-mean imputation.  Nothing
    fitted on day d ever sees day d, and no threshold does either.
    """

    by_asset_day: dict[tuple[str, int], list[S14.Stream]] = {}
    for stream in streams:
        by_asset_day.setdefault((stream.asset, stream.d8), []).append(stream)

    chunks: dict[str, list[np.ndarray]] = {}
    text: dict[str, list[list[str]]] = {"asset": [], "phase": []}
    for name in ("d8", "side", "y", "m", "decile", "cont"):
        chunks[name] = []
    subset_bits: dict[str, list[np.ndarray]] = {s: [] for s in SUBSETS}
    score_bits: dict[tuple[str, str], list[np.ndarray]] = {
        (s, v): [] for s in SUBSETS for v in VARIANTS}
    uncond_bits: dict[str, list[np.ndarray]] = {v: [] for v in BASE_VARIANTS}
    present_bits: dict[str, list[np.ndarray]] = {s: [] for s in SUBSETS}
    z_bits: dict[str, list[np.ndarray]] = {s: [] for s in SUBSETS}

    diag = {"folds": 0, "folds_skipped": 0, "rows": 0,
            "subset_fits": {f"{s}/{v}": 0 for s in SUBSETS for v in VARIANTS},
            "subset_fits_skipped": {f"{s}/{v}": 0
                                    for s in SUBSETS for v in VARIANTS},
            "uncond_fits": {v: 0 for v in BASE_VARIANTS},
            "absorb_phase_fallback": 0, "absorb_phase_cuts": 0}

    for asset in sorted({stream.asset for stream in streams}):
        days = sorted(int(day) for day in explore_days[asset])
        score_set = {int(day) for day in scoring_days.get(asset, [])}
        for index, d8 in enumerate(days):
            if d8 not in score_set:
                continue
            today = [occ for stream in by_asset_day.get((asset, d8), [])
                     for occ in stream.occs]
            train: list[S14.Occ] = []
            for day in S14.fold_days(days, index, ""):
                for stream in by_asset_day.get((asset, day), []):
                    train.extend(stream.occs)
            if len(train) < MIN_FIT_ROWS or not today:
                diag["folds_skipped"] += 1
                continue
            diag["folds"] += 1

            raw = np.vstack([occ.x for occ in train])
            with np.errstate(invalid="ignore"):
                means = np.nanmean(np.where(np.isfinite(raw), raw, np.nan), axis=0)
            means = np.where(np.isfinite(means), means, 0.0)
            xtr = S14._impute(raw, means)
            ytr = np.asarray([occ.payoff for occ in train], np.float64)
            xte = S14._impute(np.vstack([occ.x for occ in today]), means)
            yte = np.asarray([occ.payoff for occ in today], np.float64)

            # --- the magnitude score, out of fold on day d -------------------
            mag_sums = S14.Sums(width=NFEAT)
            mag_sums.add(xtr, ytr, np.abs(ytr))
            mag = mag_sums.fit("C", RIDGE_LAMBDA)
            m_train = np.asarray(mag.predict(xtr), np.float64)
            m_test = np.asarray(mag.predict(xte), np.float64)

            # --- the cuts, from the TRAIN-day m values only -------------------
            pool = _cut_pool(m_train, m_test, mutant)
            edges = np.quantile(pool, [k / N_DECILES
                                       for k in range(1, N_DECILES)])
            decile = np.searchsorted(edges, m_test, side="left")

            # --- the wide plane, when the absorption join is available --------
            if absorb is not None:
                atr = np.vstack([absorb[occ.row] for occ in train])
                ate = np.vstack([absorb[occ.row] for occ in today])
                with np.errstate(invalid="ignore"):
                    ameans = np.nanmean(
                        np.where(np.isfinite(atr), atr, np.nan), axis=0)
                ameans = np.where(np.isfinite(ameans), ameans, 0.0)
                wtr = np.hstack([xtr, S14._impute(atr, ameans)])
                wte = np.hstack([xte, S14._impute(ate, ameans)])
            else:
                wtr = wte = None

            # --- the unconditional baseline ----------------------------------
            for variant in BASE_VARIANTS:
                fit = _fit_sign(xtr, ytr, variant)
                if fit is None:
                    uncond_bits[variant].append(np.full(len(today), np.nan))
                    continue
                diag["uncond_fits"][variant] += 1
                uncond_bits[variant].append(_score_sign(fit, xte, variant))

            # --- the conditional fits, one per subset -------------------------
            for subset in SUBSETS:
                cut = float(np.quantile(pool, SUBSET_Q[subset]))
                pick_tr = m_train >= cut
                pick_te = m_test >= cut
                subset_bits[subset].append(pick_te)
                for variant in VARIANTS:
                    design_tr = xtr if variant.endswith("16") else wtr
                    design_te = xte if variant.endswith("16") else wte
                    label = f"{subset}/{variant}"
                    out = np.full(len(today), np.nan, np.float64)
                    if design_tr is None or int(pick_tr.sum()) < MIN_FIT_ROWS \
                            or not bool(pick_te.any()):
                        diag["subset_fits_skipped"][label] += 1
                        score_bits[(subset, variant)].append(out)
                        continue
                    sub_y = ytr[pick_tr]
                    if float(np.std(np.where(sub_y > 0.0, 1.0, -1.0))) <= 0.0:
                        diag["subset_fits_skipped"][label] += 1
                        score_bits[(subset, variant)].append(out)
                        continue
                    fit = _fit_sign(design_tr[pick_tr], sub_y, variant)
                    if fit is None:
                        diag["subset_fits_skipped"][label] += 1
                        score_bits[(subset, variant)].append(out)
                        continue
                    diag["subset_fits"][label] += 1
                    out[pick_te] = _score_sign(fit, design_te[pick_te], variant)
                    score_bits[(subset, variant)].append(out)

                # --- the discrete absorption cut ---------------------------
                present = np.full(len(today), np.nan, np.float64)
                zeta = np.full(len(today), np.nan, np.float64)
                if absorb is not None and bool(pick_tr.any()):
                    phases_tr = np.asarray([occ.phase for occ in train])
                    phases_te = np.asarray([occ.phase for occ in today])
                    hi_tr = atr[pick_tr]
                    hi_ph = phases_tr[pick_tr]
                    pooled_mean, pooled_sd = _standardise_train(
                        np.where(np.isfinite(hi_tr), hi_tr, 0.0))
                    for phase in PHASES:
                        rows_te = np.flatnonzero((phases_te == phase) & pick_te)
                        if not len(rows_te):
                            continue
                        block = hi_tr[hi_ph == phase]
                        if len(block) >= ABS_MIN_PHASE_ROWS:
                            diag["absorb_phase_cuts"] += 1
                            clean = np.where(np.isfinite(block), block, 0.0)
                            pm, ps = _standardise_train(clean)
                        else:
                            diag["absorb_phase_fallback"] += 1
                            clean = np.where(np.isfinite(hi_tr), hi_tr, 0.0)
                            pm, ps = pooled_mean, pooled_sd
                        train_z = _composite(clean, pm, ps)
                        cut_z = float(np.quantile(train_z, ABS_TERCILE))
                        test_z = _composite(ate[rows_te], pm, ps)
                        zeta[rows_te] = test_z
                        present[rows_te] = (test_z >= cut_z).astype(np.float64)
                present_bits[subset].append(present)
                z_bits[subset].append(zeta)

            text["asset"].append([asset] * len(today))
            text["phase"].append([occ.phase for occ in today])
            chunks["d8"].append(np.full(len(today), d8, np.int64))
            chunks["side"].append(np.asarray([occ.side for occ in today],
                                             np.int64))
            chunks["y"].append(yte)
            chunks["m"].append(m_test)
            chunks["decile"].append(decile.astype(np.int64))
            chunks["cont"].append(np.asarray(
                [float(cont[occ.row]) if cont is not None else np.nan
                 for occ in today], np.float64))
            diag["rows"] += len(today)

    def cat(bits: Sequence[np.ndarray], dtype=np.float64) -> np.ndarray:
        return (np.concatenate(bits).astype(dtype) if bits
                else np.zeros(0, dtype))

    table = Table(
        asset=np.asarray([v for block in text["asset"] for v in block]),
        d8=cat(chunks["d8"], np.int64),
        phase=np.asarray([v for block in text["phase"] for v in block]),
        side=cat(chunks["side"], np.int64),
        y=cat(chunks["y"]), m=cat(chunks["m"]),
        decile=cat(chunks["decile"], np.int64),
        cont=cat(chunks["cont"]))
    for subset in SUBSETS:
        table.subset[subset] = cat(subset_bits[subset], bool)
        table.absorb_present[subset] = cat(present_bits[subset])
        table.absorb_z[subset] = cat(z_bits[subset])
    for key, bits in score_bits.items():
        table.score[key] = cat(bits)
    for variant, bits in uncond_bits.items():
        table.uncond[variant] = cat(bits)
    return table, diag


# --------------------------------------------------------------------------
# T1 .. T4, read off the table.
# --------------------------------------------------------------------------

def _cell(y: np.ndarray) -> dict[str, object]:
    """n, P(Y>0) with Wilson bounds, mean Y, median Y, mean |Y|."""

    total = int(len(y))
    if not total:
        return {"n": 0, "p_pos": None, "lo": None, "hi": None, "mean_y": None,
                "median_y": None, "mean_absy": None, "sum_y": 0.0}
    hits = int((y > 0.0).sum())
    lo, hi = wilson(hits, total)
    return {"n": total, "hits": hits, "p_pos": hits / total, "lo": lo, "hi": hi,
            "mean_y": float(y.mean()), "median_y": float(np.median(y)),
            "mean_absy": float(np.abs(y).mean()), "sum_y": float(y.sum())}


def t1_base_rates(table: Table, days: Mapping[str, int]) -> dict[str, object]:
    out: dict[str, object] = {}
    for asset in ASSETS:
        pick = table.asset == asset
        rows: list[dict[str, object]] = []
        for bucket in range(N_DECILES):
            take = pick & (table.decile == bucket)
            entry = _cell(table.y[take])
            entry["decile"] = bucket + 1
            entry["mean_m"] = (float(table.m[take].mean())
                               if int(take.sum()) else None)
            entry["usd_day"] = (entry["sum_y"] / days[asset]
                                if days.get(asset) else None)
            rows.append(entry)
        overall = _cell(table.y[pick])
        top = rows[-1]["p_pos"]
        bottom = rows[0]["p_pos"]
        out[asset] = {
            "days": int(days.get(asset, 0)), "deciles": rows,
            "overall": overall,
            "top_minus_bottom_p_pos": (None if top is None or bottom is None
                                       else float(top - bottom)),
            "spearman_decile_vs_p_pos": _spearman(
                [r["decile"] for r in rows if r["p_pos"] is not None],
                [r["p_pos"] for r in rows if r["p_pos"] is not None]),
            "spearman_decile_vs_mean_absy": _spearman(
                [r["decile"] for r in rows if r["mean_absy"] is not None],
                [r["mean_absy"] for r in rows if r["mean_absy"] is not None]),
        }
    return out


def _spearman(a: Sequence[float], b: Sequence[float]) -> float | None:
    if len(a) < 3:
        return None
    ra = _rank_average(np.asarray(a, np.float64))
    rb = _rank_average(np.asarray(b, np.float64))
    if float(ra.std()) <= 0.0 or float(rb.std()) <= 0.0:
        return None
    return float(np.corrcoef(ra, rb)[0, 1])


def _sign_block(y: np.ndarray, score: np.ndarray, days: int
                ) -> dict[str, object]:
    """Accuracy, AUC and the cash cut of one (asset, subset, variant) cell."""

    good = np.isfinite(score)
    y = y[good]
    score = score[good]
    total = int(len(y))
    if total < 2:
        return {"n": total, "accuracy": None, "base_rate": None, "auc": None,
                "excess_vs_base": None, "excess_vs_half": None,
                "majority_rate": None, "excess_vs_majority": None,
                "auc_z": None, "taken": 0, "taken_share": None,
                "mean_y_taken": None, "usd_day_taken": None,
                "usd_day_all": None}
    positive = y > 0.0
    predicted = score > 0.0
    accuracy = float(np.mean(predicted == positive))
    base = float(positive.mean())
    taken = int(predicted.sum())
    taken_y = y[predicted]
    # The always-fade base rate is the pre-registered comparator, but when
    # P(Y>0) sits far below 0.5 it is a weak one: a model that answers "break"
    # on most rows clears it without discriminating at all.  The MAJORITY-class
    # rate is the honest floor, and the AUC z is the discrimination the
    # accuracy cut cannot see.  Both are reported beside the registered number
    # so the letter is never read as more than it is.
    majority = max(base, 1.0 - base)
    area = auc(positive.astype(np.float64), score)
    hits = float(positive.sum())
    misses = float(total) - hits
    if area is None or hits <= 0.0 or misses <= 0.0:
        area_z = None
    else:
        se = math.sqrt((hits + misses + 1.0) / (12.0 * hits * misses))
        area_z = (area - 0.5) / se if se > 0.0 else None
    return {
        "n": total, "accuracy": accuracy, "base_rate": base,
        "excess_vs_base": accuracy - base, "excess_vs_half": accuracy - 0.5,
        "majority_rate": majority, "excess_vs_majority": accuracy - majority,
        "auc": area, "auc_z": area_z,
        "taken": taken, "taken_share": taken / total,
        "mean_y_taken": float(taken_y.mean()) if taken else None,
        "sum_y_taken": float(taken_y.sum()) if taken else 0.0,
        "usd_day_taken": (float(taken_y.sum()) / days) if days else None,
        "usd_day_all": (float(y.sum()) / days) if days else None,
        "mean_y_all": float(y.mean()),
        "abstain_usd_day": 0.0,
    }


def t2_conditional(table: Table, days: Mapping[str, int], variants=VARIANTS
                   ) -> dict[str, object]:
    out: dict[str, object] = {}
    for asset in ASSETS:
        base = table.asset == asset
        block: dict[str, object] = {}
        for subset in SUBSETS:
            pick = base & table.subset[subset]
            cell: dict[str, object] = {
                "rows": int(pick.sum()),
                "share_of_scored": (float(pick.sum()) / float(base.sum())
                                    if int(base.sum()) else None),
                "mean_m": (float(table.m[pick].mean())
                           if int(pick.sum()) else None),
                "mean_absy": (float(np.abs(table.y[pick]).mean())
                              if int(pick.sum()) else None),
                "marginal": _cell(table.y[pick]),
            }
            for variant in variants:
                cell[variant] = _sign_block(
                    table.y[pick], table.score[(subset, variant)][pick],
                    int(days.get(asset, 0)))
            block[subset] = cell
        block["unconditional"] = {
            variant: _sign_block(table.y[base], table.uncond[variant][base],
                                 int(days.get(asset, 0)))
            for variant in table.uncond}
        block["unconditional"]["marginal"] = _cell(table.y[base])
        out[asset] = block
    return out


def t3_absorption(table: Table, days: Mapping[str, int],
                  t2: Mapping[str, object]) -> dict[str, object]:
    model: dict[str, object] = {}
    for asset in ASSETS:
        block: dict[str, object] = {}
        for subset in SUBSETS:
            row: dict[str, object] = {}
            for narrow, wide in (("ridge16", "ridge24"), ("logit16", "logit24")):
                base = t2[asset][subset][narrow]
                plus = t2[asset][subset][wide]
                row[f"{narrow}->{wide}"] = {
                    "accuracy_16": base["accuracy"],
                    "accuracy_24": plus["accuracy"],
                    "delta_accuracy": (None if base["accuracy"] is None
                                       or plus["accuracy"] is None
                                       else plus["accuracy"] - base["accuracy"]),
                    "auc_16": base["auc"], "auc_24": plus["auc"],
                    "usd_day_16": base["usd_day_taken"],
                    "usd_day_24": plus["usd_day_taken"],
                    "delta_usd_day": (None if base["usd_day_taken"] is None
                                      or plus["usd_day_taken"] is None
                                      else plus["usd_day_taken"]
                                      - base["usd_day_taken"]),
                }
            block[subset] = row
        model[asset] = block

    discrete: dict[str, object] = {}
    for asset in ASSETS:
        base = table.asset == asset
        block: dict[str, object] = {}
        for subset in SUBSETS:
            pick = base & table.subset[subset]
            flag = table.absorb_present[subset]
            known = pick & np.isfinite(flag)
            present = known & (flag > 0.5)
            absent = known & (flag <= 0.5)
            one = _cell(table.y[present])
            zero = _cell(table.y[absent])
            gap = (None if one["p_pos"] is None or zero["p_pos"] is None
                   else float(one["p_pos"] - zero["p_pos"]))
            mean_gap = (None if one["mean_y"] is None or zero["mean_y"] is None
                        else float(one["mean_y"] - zero["mean_y"]))
            block[subset] = {
                "rows_with_composite": int(known.sum()),
                "rows_missing_composite": int(pick.sum() - known.sum()),
                "present": one, "absent": zero,
                "p_pos_gap": gap, "mean_y_gap_usd": mean_gap,
                "wilson_disjoint": bool(
                    one["lo"] is not None and zero["hi"] is not None
                    and (one["lo"] > zero["hi"] or zero["lo"] > one["hi"])),
                "usd_day_present": (one["sum_y"] / days[asset]
                                    if days.get(asset) else None),
                "usd_day_absent": (zero["sum_y"] / days[asset]
                                   if days.get(asset) else None),
            }
        discrete[asset] = block
    return {"model_cut": model, "discrete_cut": discrete}


def t4_antifade(table: Table, days: Mapping[str, int]) -> dict[str, object]:
    out: dict[str, object] = {}
    for asset in ASSETS:
        base = table.asset == asset
        block: dict[str, object] = {}
        for subset in SUBSETS:
            pick = base & table.subset[subset] & np.isfinite(table.cont)
            cont = table.cont[pick]
            fade = table.y[pick]
            total = int(len(cont))
            hits = int((cont > 0.0).sum())
            lo, hi = wilson(hits, total)
            n_days = int(days.get(asset, 0))
            block[subset] = {
                "rows": total,
                "rows_in_subset": int((base & table.subset[subset]).sum()),
                "mean_cont_usd": float(cont.mean()) if total else None,
                "median_cont_usd": float(np.median(cont)) if total else None,
                "p_cont_positive": (hits / total) if total else None,
                "lo": lo, "hi": hi,
                "usd_day_continue": (float(cont.sum()) / n_days
                                     if n_days else None),
                "usd_day_fade": (float(fade.sum()) / n_days
                                 if n_days else None),
                "mean_fade_usd": float(fade.mean()) if total else None,
                "mean_negation_gap_usd": (float(np.mean(cont + fade))
                                          if total else None),
                "mean_abs_negation_gap_usd": (float(np.mean(np.abs(cont + fade)))
                                              if total else None),
                "corr_cont_vs_negfade": (
                    float(np.corrcoef(cont, -fade)[0, 1])
                    if total > 2 and float(cont.std()) > 0.0
                    and float(fade.std()) > 0.0 else None),
                "both_sides_lose_share": (float(np.mean((cont < 0.0)
                                                        & (fade < 0.0)))
                                          if total else None),
                "both_sides_win_share": (float(np.mean((cont > 0.0)
                                                       & (fade > 0.0)))
                                         if total else None),
            }
        out[asset] = block
    return out


# --------------------------------------------------------------------------
# The pre-registered nulls: block permutation, studentised max-T.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class NullCell:
    name: str
    asset: str
    subset: str
    variant: str
    observed: float
    draws: np.ndarray


def _block_permute(rng: np.random.Generator, blocks: np.ndarray) -> np.ndarray:
    """A permutation that never moves a row out of its asset-day block."""

    keys = rng.random(len(blocks))
    return np.lexsort((keys, blocks))


def _null_family(name: str, table: Table, cells_spec: Sequence[dict],
                 draws: int, seed: int) -> list[NullCell]:
    """Draw the whole family under ONE permutation per (draw, asset).

    Sharing the permutation across the cells of an asset is what makes the
    row-wise maximum a real max-T rather than a maximum over independent
    experiments: the cells co-vary under the null the way they co-vary in the
    data.  Each spec names the quantity it wants permuted ("y" or "cont"), a
    boolean mask over the asset's block-ordered rows, and a statistic that sees
    only the permuted values on that mask.
    """

    out: list[NullCell] = []
    by_asset: dict[str, list[dict]] = {}
    for spec in cells_spec:
        by_asset.setdefault(spec["asset"], []).append(spec)
    for position, asset in enumerate(sorted(by_asset)):
        specs = by_asset[asset]
        order = np.flatnonzero(table.asset == asset)
        order = order[np.argsort(table.d8[order], kind="stable")]
        blocks = table.d8[order]
        # A row whose CONTINUE side is illegal pays nothing, so it enters the
        # permutation pool as a 0 rather than being dropped: the null has to be
        # able to hand a draw the same "no trade there" outcome the data has.
        raw_cont = table.cont[order]
        columns = {"y": table.y[order],
                   "cont": np.where(np.isfinite(raw_cont), raw_cont, 0.0)}
        rng = np.random.default_rng(seed + 7919 * (position + 1))
        matrices = {spec["name"]: np.empty(draws, np.float64) for spec in specs}
        for draw in range(draws):
            perm = _block_permute(rng, blocks)
            permuted = {key: values[perm] for key, values in columns.items()}
            for spec in specs:
                matrices[spec["name"]][draw] = spec["stat"](
                    permuted[spec["quantity"]][spec["live"]])
        for spec in specs:
            out.append(NullCell(name=spec["name"], asset=asset,
                                subset=spec["subset"], variant=spec["variant"],
                                observed=float(spec["observed"]),
                                draws=matrices[spec["name"]]))
    return out


def studentised_maxt(cells: Sequence[NullCell]) -> dict[str, object]:
    if not cells:
        return {}
    matrix = np.vstack([cell.draws for cell in cells])
    mean = matrix.mean(axis=1)
    sd = matrix.std(axis=1)
    sd = np.where(sd <= 1e-12, 1.0, sd)
    z_draws = (matrix - mean[:, None]) / sd[:, None]
    observed = np.asarray([cell.observed for cell in cells], np.float64)
    z_obs = (observed - mean) / sd
    top = z_draws.max(axis=0)
    draws = matrix.shape[1]
    out: dict[str, object] = {}
    for index, cell in enumerate(cells):
        raw = (1.0 + float((matrix[index] >= cell.observed).sum())) / (1.0 + draws)
        adjusted = (1.0 + float((top >= z_obs[index]).sum())) / (1.0 + draws)
        out[cell.name] = {
            "asset": cell.asset, "subset": cell.subset, "variant": cell.variant,
            "observed": float(cell.observed), "null_mean": float(mean[index]),
            "null_sd": float(sd[index]), "null_p5": float(
                np.percentile(matrix[index], 5.0)),
            "null_p95": float(np.percentile(matrix[index], 95.0)),
            "z": float(z_obs[index]), "p_raw": raw, "p_adjusted": adjusted,
            "significant": bool(adjusted <= ALPHA),
        }
    return out


def build_nulls(table: Table, days: Mapping[str, int], draws: int = NULL_DRAWS,
                seed: int = SEED) -> dict[str, object]:
    """The three pre-registered families, each with its own permuted quantity."""

    sign_specs: list[dict] = []
    cash_specs: list[dict] = []
    anti_specs: list[dict] = []
    for asset in ASSETS:
        base = table.asset == asset
        n_days = int(days.get(asset, 0))
        order = np.flatnonzero(base)
        order = order[np.argsort(table.d8[order], kind="stable")]
        for subset in SUBSETS:
            pick = base & table.subset[subset]
            for variant in VARIANTS:
                score = table.score[(subset, variant)]
                live = pick & np.isfinite(score)
                if int(live.sum()) < 2:
                    continue
                observed = _sign_block(table.y[live], score[live], n_days)
                if observed["excess_vs_base"] is None:
                    continue
                # ``live`` in the asset's block order, and the predictions in
                # that same order, so a permuted column indexes straight in.
                mask = live[order]
                predicted = (score[order][mask] > 0.0)

                def sign_stat(values, predicted=predicted):
                    labels = values > 0.0
                    return float(np.mean(predicted == labels) - labels.mean())

                sign_specs.append({
                    "name": f"SIGN/{asset}/{subset}/{variant}", "asset": asset,
                    "subset": subset, "variant": variant, "quantity": "y",
                    "live": mask, "observed": observed["excess_vs_base"],
                    "stat": sign_stat})

                if observed["usd_day_taken"] is not None and n_days:
                    def cash_stat(values, predicted=predicted, n_days=n_days):
                        return float(values[predicted].sum()) / n_days

                    cash_specs.append({
                        "name": f"CASH/{asset}/{subset}/{variant}",
                        "asset": asset, "subset": subset, "variant": variant,
                        "quantity": "y", "live": mask,
                        "observed": observed["usd_day_taken"],
                        "stat": cash_stat})

            # ANTIFADE permutes the CONTINUE certs across the asset's whole
            # scored day, so the null asks whether the high-m SELECTION picks
            # better continue-side rows than a same-size random pick would.
            live_cont = base & np.isfinite(table.cont)
            cont_mask = np.ones(len(order), bool)     # the whole scored day
            member = pick[order]
            if not int(member.sum()) or not n_days:
                continue
            observed_usd = float(table.cont[pick & live_cont].sum()) / n_days

            def anti_stat(values, member=member, n_days=n_days):
                return float(values[member].sum()) / n_days

            anti_specs.append({
                "name": f"ANTIFADE/{asset}/{subset}", "asset": asset,
                "subset": subset, "variant": "continue", "quantity": "cont",
                "live": cont_mask, "observed": observed_usd,
                "stat": anti_stat})

    return {
        "draws": int(draws), "seed": int(seed),
        "SIGN": studentised_maxt(_null_family("SIGN", table, sign_specs,
                                              draws, seed)),
        "CASH": studentised_maxt(_null_family("CASH", table, cash_specs,
                                              draws, seed + 1)),
        "ANTIFADE": studentised_maxt(_null_family("ANTIFADE", table, anti_specs,
                                                  draws, seed + 2)),
    }


# --------------------------------------------------------------------------
# The pre-registered decision table.
# --------------------------------------------------------------------------

def decide(t2: Mapping[str, object], nulls: Mapping[str, object]
           ) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for asset in ASSETS:
        for subset in SUBSETS:
            for variant in VARIANTS:
                block = t2[asset][subset][variant]
                sign = nulls["SIGN"].get(f"SIGN/{asset}/{subset}/{variant}")
                cash = nulls["CASH"].get(f"CASH/{asset}/{subset}/{variant}")
                if sign is None:
                    continue
                cash_usd = block["usd_day_taken"]
                beats = bool(block["excess_vs_base"] is not None
                             and block["excess_vs_base"] > 0.0
                             and sign["p_adjusted"] <= ALPHA)
                rows.append({
                    "asset": asset, "subset": subset, "variant": variant,
                    "deciding": asset in DECIDING,
                    "plane": 16 if variant.endswith("16") else 24,
                    "test": "T2" if variant.endswith("16") else "T3a",
                    "n": block["n"], "accuracy": block["accuracy"],
                    "base_rate": block["base_rate"],
                    "excess_vs_base": block["excess_vs_base"],
                    "excess_vs_half": block["excess_vs_half"],
                    "majority_rate": block["majority_rate"],
                    "excess_vs_majority": block["excess_vs_majority"],
                    "auc": block["auc"], "auc_z": block["auc_z"],
                    "beats_majority": bool(
                        block["excess_vs_majority"] is not None
                        and block["excess_vs_majority"] > 0.0),
                    "discriminates": bool(block["auc"] is not None
                                          and block["auc"] > 0.5),
                    "usd_day_taken": cash_usd,
                    "cash_p_adjusted": (None if cash is None
                                        else cash["p_adjusted"]),
                    "sign_p_adjusted": sign["p_adjusted"],
                    "sign_p_raw": sign["p_raw"],
                    "beats_base_significantly": beats,
                    "cash_positive": bool(cash_usd is not None and cash_usd > 0.0),
                    "condsign_cell": bool(beats and cash_usd is not None
                                          and cash_usd > 0.0),
                    # NOT the registered letter: the same cell with the two
                    # things the accuracy cut cannot check - that the model
                    # also beats answering the common class every time, and
                    # that it actually ranks (AUC > 0.5).  Reported so the
                    # letter is never read as more than it is.
                    "condsign_cell_strict": bool(
                        beats and cash_usd is not None and cash_usd > 0.0
                        and block["excess_vs_majority"] is not None
                        and block["excess_vs_majority"] > 0.0
                        and block["auc"] is not None and block["auc"] > 0.5),
                })
    anti_rows: list[dict[str, object]] = []
    for asset in ASSETS:
        for subset in SUBSETS:
            entry = nulls["ANTIFADE"].get(f"ANTIFADE/{asset}/{subset}")
            if entry is None:
                continue
            anti_rows.append({
                "asset": asset, "subset": subset,
                "deciding": asset in DECIDING,
                "usd_day_continue": entry["observed"],
                "p_adjusted": entry["p_adjusted"], "p_raw": entry["p_raw"],
                "null_mean": entry["null_mean"],
                "antifade_cell": bool(entry["observed"] > 0.0
                                      and entry["p_adjusted"] <= ALPHA),
            })

    condsign_hits = [r for r in rows if r["condsign_cell"] and r["deciding"]]
    strict_hits = [r for r in rows if r["condsign_cell_strict"] and r["deciding"]]
    antifade_hits = [r for r in anti_rows if r["antifade_cell"] and r["deciding"]]
    letters = []
    if condsign_hits:
        letters.append("CONDSIGN")
    if antifade_hits:
        letters.append("ANTIFADE")
    return {
        "rows": rows, "antifade_rows": anti_rows,
        "condsign": bool(condsign_hits), "antifade": bool(antifade_hits),
        "condsign_strict": bool(strict_hits),
        "condsign_cells_strict": [f"{r['asset']}/{r['subset']}/{r['variant']}"
                                  for r in strict_hits],
        "condsign_cells": [f"{r['asset']}/{r['subset']}/{r['variant']}"
                           for r in condsign_hits],
        "antifade_cells": [f"{r['asset']}/{r['subset']}"
                           for r in antifade_hits],
        "letters": letters or ["NONE"],
        "verdict": "+".join(letters) if letters else "NONE",
        "alpha": ALPHA, "deciding": list(DECIDING),
    }


# --------------------------------------------------------------------------
# The gate.
# --------------------------------------------------------------------------

def scoring_days(explore_days: Mapping[str, Sequence[int]],
                 census: Mapping[tuple[str, str, int], int]) -> dict[str, list[int]]:
    """Sweep 14's scoring-day rule, restated from its own constants."""

    out: dict[str, list[int]] = {}
    for asset in ASSETS:
        days = sorted(int(day) for day in explore_days[asset])
        keep = [d8 for index, d8 in enumerate(days)
                if index >= MIN_PRIOR_DAYS_FIT
                and sum(int(census.get((asset, slot, d8), 0)) for slot in PHASES)]
        out[asset] = keep
    return out


def gate(plane: S9.Plane, scoring: Mapping[str, Sequence[int]],
         absorb: AbsorptionJoin) -> dict[str, object]:
    block = S14.reproduce_sweep9(plane)
    live_days = {asset: len(scoring[asset]) for asset in ASSETS}
    days_ok = live_days == REPRO_SCORING_DAYS
    causal_ok = absorb.max_close_minus_stamp_ns <= 0
    return {
        **block, "scoring_days_live": live_days,
        "scoring_days_banked": dict(REPRO_SCORING_DAYS),
        "scoring_days_match": bool(days_ok),
        "absorption_max_close_minus_stamp_ns": absorb.max_close_minus_stamp_ns,
        "absorption_strictly_prior": bool(causal_ok),
        "absorption_counters": absorb.counters,
        "matches": bool(block["matches"] and days_ok and causal_ok),
    }


# --------------------------------------------------------------------------
# Printing.
# --------------------------------------------------------------------------

def print_gate(block: Mapping[str, object]) -> None:
    print("\nGATE - SWEEP-9 ROW PLANE, SWEEP-14 SCORING DAYS, CAUSAL JOIN")
    print(f"  rows            banked {block['banked_rows']}  "
          f"live {block['live_rows']}")
    for asset in ASSETS:
        print(f"  certifiable {asset:<4}banked {block['banked_certifiable'][asset]:>6}"
              f"  live {block['live_certifiable'][asset]:>6}")
    for name in sorted(REPRO_COUNTERS):
        print(f"  {name:<20}banked {block['banked_counters'][name]:>7}"
              f"  live {block['live_counters'][name]:>7}")
    for asset in ASSETS:
        print(f"  scoring days {asset:<4}banked "
              f"{block['scoring_days_banked'][asset]:>6}  live "
              f"{block['scoring_days_live'][asset]:>6}")
    counters = block["absorption_counters"]
    print(f"  absorption join   rows {counters['rows']}  joined "
          f"{counters['joined']}  missing_cell {counters['missing_cell']}  "
          f"bar_zero {counters['bar_zero']}  nonfinite {counters['nonfinite']}")
    print(f"  absorption causality  max(bar_close[bar-1] - stamp) = "
          f"{block['absorption_max_close_minus_stamp_ns']} ns  "
          f"strictly prior: {block['absorption_strictly_prior']}")
    print(f"  plane matches {block['matches']}   scoring days match "
          f"{block['scoring_days_match']}")


def print_t1(t1: Mapping[str, object]) -> None:
    print("\nT1 BASE RATES BY OUT-OF-FOLD MAGNITUDE DECILE")
    print("  the USER's question: when the state says a BIG move is coming, "
          "does the extreme hold more or less often?")
    head = ("n", "mean_m", "P(Y>0)", "wil_lo", "wil_hi", "meanY", "medY",
            "mean|Y|", "usd/day")
    for asset in ASSETS:
        block = t1[asset]
        print(f"\n  {asset}  ({block['days']} scoring days, "
              f"{block['overall']['n']} out-of-fold rows, "
              f"pooled P(Y>0) {_f(block['overall']['p_pos'])})")
        print("    " + "decile".ljust(9) + "".join(h.rjust(10) for h in head))
        for row in block["deciles"]:
            print("    " + f"d{row['decile']}".ljust(9) + _n(row["n"], 10)
                  + _n(row["mean_m"], 10, 1) + _n(row["p_pos"], 10, 4)
                  + _n(row["lo"], 10, 4) + _n(row["hi"], 10, 4)
                  + _n(row["mean_y"], 10, 2) + _n(row["median_y"], 10, 2)
                  + _n(row["mean_absy"], 10, 1) + _n(row["usd_day"], 10, 1))
        print(f"    top-minus-bottom P(Y>0) "
              f"{_n(block['top_minus_bottom_p_pos'], 8, 4).strip()}   "
              f"spearman(decile, P(Y>0)) "
              f"{_n(block['spearman_decile_vs_p_pos'], 8, 4).strip()}   "
              f"spearman(decile, mean|Y|) "
              f"{_n(block['spearman_decile_vs_mean_absy'], 8, 4).strip()}")


def print_t2(t2: Mapping[str, object], nulls: Mapping[str, object],
             variants=VARIANTS) -> None:
    print("\nT2 CONDITIONAL SIGN INSIDE THE HIGH-MAGNITUDE SUBSET  "
          "(ridge24/logit24 are T3(a), the 16+8 absorption plane)")
    head = ("n", "acc", "base", "vs_base", "vs_0.5", "major", "vs_maj", "AUC",
            "auc_z", "taken", "meanY_tk", "usd/day", "p_sign", "p_cash")
    for asset in ASSETS:
        print(f"\n  {asset}")
        print("    " + "subset/variant".ljust(24)
              + "".join(h.rjust(10) for h in head))
        for subset in SUBSETS:
            cell = t2[asset][subset]
            print("    " + f"{subset} rows={cell['rows']} "
                  f"share={_n(cell['share_of_scored'], 6, 3).strip()} "
                  f"P(Y>0)={_n(cell['marginal']['p_pos'], 6, 4).strip()} "
                  f"mean|Y|={_n(cell['mean_absy'], 8, 1).strip()}")
            for variant in variants:
                block = cell[variant]
                sign = nulls["SIGN"].get(f"SIGN/{asset}/{subset}/{variant}")
                cash = nulls["CASH"].get(f"CASH/{asset}/{subset}/{variant}")
                print("    " + f"  {subset}/{variant}".ljust(24)
                      + _n(block["n"], 10) + _n(block["accuracy"], 10, 4)
                      + _n(block["base_rate"], 10, 4)
                      + _n(block["excess_vs_base"], 10, 4)
                      + _n(block["excess_vs_half"], 10, 4)
                      + _n(block["majority_rate"], 10, 4)
                      + _n(block["excess_vs_majority"], 10, 4)
                      + _n(block["auc"], 10, 4) + _n(block["auc_z"], 10, 2)
                      + _n(block["taken"], 10)
                      + _n(block["mean_y_taken"], 10, 1)
                      + _n(block["usd_day_taken"], 10, 1)
                      + _n(None if sign is None else sign["p_adjusted"], 10, 4)
                      + _n(None if cash is None else cash["p_adjusted"], 10, 4))
        print("    " + "UNCONDITIONAL BASELINE (all scored rows, "
              "sweep 15 measured this negative)")
        for variant in BASE_VARIANTS:
            block = t2[asset]["unconditional"][variant]
            print("    " + f"  all/{variant}".ljust(24)
                  + _n(block["n"], 10) + _n(block["accuracy"], 10, 4)
                  + _n(block["base_rate"], 10, 4)
                  + _n(block["excess_vs_base"], 10, 4)
                  + _n(block["excess_vs_half"], 10, 4)
                  + _n(block["majority_rate"], 10, 4)
                  + _n(block["excess_vs_majority"], 10, 4)
                  + _n(block["auc"], 10, 4) + _n(block["auc_z"], 10, 2)
                  + _n(block["taken"], 10)
                  + _n(block["mean_y_taken"], 10, 1)
                  + _n(block["usd_day_taken"], 10, 1) + "-".rjust(10)
                  + "-".rjust(10))
    print("\n  major = the MAJORITY-class rate max(P(Y>0), 1-P(Y>0)), the rate a "
          "model gets by answering")
    print("  the common class every time.  vs_base is the pre-registered "
          "comparator; vs_maj is the honest")
    print("  floor, and auc_z is the discrimination, in null standard "
          "deviations.  A large vs_base beside")
    print("  a negative vs_maj and an auc_z near 0 is a low base rate, not a "
          "finding.")


def print_t3(t3: Mapping[str, object]) -> None:
    print("\nT3(a) ABSORPTION AS A MODEL CUT  (16 features -> 16+8)")
    head = ("acc16", "acc24", "d_acc", "auc16", "auc24", "usd16", "usd24",
            "d_usd")
    print("  " + "asset/subset/pair".ljust(34) + "".join(h.rjust(10) for h in head))
    for asset in ASSETS:
        for subset in SUBSETS:
            for pair, row in t3["model_cut"][asset][subset].items():
                print("  " + f"{asset}/{subset}/{pair}".ljust(34)
                      + _n(row["accuracy_16"], 10, 4)
                      + _n(row["accuracy_24"], 10, 4)
                      + _n(row["delta_accuracy"], 10, 4)
                      + _n(row["auc_16"], 10, 4) + _n(row["auc_24"], 10, 4)
                      + _n(row["usd_day_16"], 10, 1)
                      + _n(row["usd_day_24"], 10, 1)
                      + _n(row["delta_usd_day"], 10, 1))
    print("\nT3(b) ABSORPTION AS A DISCRETE CUT  (present = top tercile of the "
          "composite, cut taken on train-day high-m rows per asset per phase)")
    head = ("n_pres", "P>0_pres", "lo", "hi", "meanY_pr", "n_abs", "P>0_abs",
            "lo", "hi", "meanY_ab", "gap_P", "gap_meanY")
    print("  " + "asset/subset".ljust(20) + "".join(h.rjust(10) for h in head))
    for asset in ASSETS:
        for subset in SUBSETS:
            row = t3["discrete_cut"][asset][subset]
            one, zero = row["present"], row["absent"]
            print("  " + f"{asset}/{subset}".ljust(20)
                  + _n(one["n"], 10) + _n(one["p_pos"], 10, 4)
                  + _n(one["lo"], 10, 4) + _n(one["hi"], 10, 4)
                  + _n(one["mean_y"], 10, 2)
                  + _n(zero["n"], 10) + _n(zero["p_pos"], 10, 4)
                  + _n(zero["lo"], 10, 4) + _n(zero["hi"], 10, 4)
                  + _n(zero["mean_y"], 10, 2)
                  + _n(row["p_pos_gap"], 10, 4)
                  + _n(row["mean_y_gap_usd"], 10, 2))


def print_t4(t4: Mapping[str, object], nulls: Mapping[str, object],
             hand: Mapping[str, object]) -> None:
    print("\nT4 ANTIFADE PRICING - the CONTINUE side through the frozen law "
          "with the FLIPPED side")
    head = ("rows", "mean_ct", "med_ct", "P(ct>0)", "lo", "hi", "usd/day_ct",
            "usd/day_fd", "p_adj", "neg_gap", "both_lose")
    print("  " + "asset/subset".ljust(20) + "".join(h.rjust(11) for h in head))
    for asset in ASSETS:
        for subset in SUBSETS:
            row = t4[asset][subset]
            entry = nulls["ANTIFADE"].get(f"ANTIFADE/{asset}/{subset}")
            print("  " + f"{asset}/{subset}".ljust(20)
                  + _n(row["rows"], 11) + _n(row["mean_cont_usd"], 11, 2)
                  + _n(row["median_cont_usd"], 11, 2)
                  + _n(row["p_cont_positive"], 11, 4)
                  + _n(row["lo"], 11, 4) + _n(row["hi"], 11, 4)
                  + _n(row["usd_day_continue"], 11, 1)
                  + _n(row["usd_day_fade"], 11, 1)
                  + _n(None if entry is None else entry["p_adjusted"], 11, 4)
                  + _n(row["mean_abs_negation_gap_usd"], 11, 1)
                  + _n(row["both_sides_lose_share"], 11, 4))
    print(f"\n  FLIPPED-SIDE HAND CHECK  {hand['rows']} rows, "
          f"max |outcome() - batch| = {hand['max_abs_delta_usd']:.2e} usd, "
          f"matches: {hand['matches']}")
    print("  " + "asset/d8/phase/bar".ljust(28) + "fade".rjust(6)
          + "batch_cont".rjust(12) + "outcome()".rjust(12) + "delta".rjust(11)
          + "fade_Y".rjust(11) + "cont+Y".rjust(11) + "walls f/c".rjust(12))
    for row in hand["checked"]:
        print("  " + f"{row['asset']}/{row['d8']}/{row['phase']}/{row['bar']}"
              .ljust(28) + _n(row["fade_side"], 6)
              + _n(row["batch_cert_usd"], 12, 3)
              + _n(row["outcome_call_cert_usd"], 12, 3)
              + f"{row['abs_delta_usd']:.1e}".rjust(11)
              + _n(row["fade_cert_usd"], 11, 3)
              + _n(row["negation_gap_usd"], 11, 3)
              + f"{row['fade_wall']!s:>5}/{row['continue_wall']!s:<6}".rjust(12))
    print("  cont+Y is 0 only if the continue cert WERE the negation of Y; it "
          "is not, because the -900 wall")
    print("  applies to the held position and the two sides therefore wall at "
          "different bars.")


def print_decision(block: Mapping[str, object]) -> None:
    print("\nDECISION TABLE (pre-registered)")
    head = ("n", "acc", "base", "vs_base", "vs_maj", "AUC", "auc_z", "usd/day",
            "p_sign", "p_cash", "beats", "cash+", "cell", "strict")
    print("  " + "test/asset/subset/variant".ljust(34)
          + "".join(h.rjust(10) for h in head))
    for row in block["rows"]:
        mark = "*" if row["deciding"] else " "
        print("  " + f"{row['test']}/{row['asset']}{mark}/{row['subset']}/"
              f"{row['variant']}".ljust(34)
              + _n(row["n"], 10) + _n(row["accuracy"], 10, 4)
              + _n(row["base_rate"], 10, 4) + _n(row["excess_vs_base"], 10, 4)
              + _n(row["excess_vs_majority"], 10, 4)
              + _n(row["auc"], 10, 4) + _n(row["auc_z"], 10, 2)
              + _n(row["usd_day_taken"], 10, 1)
              + _n(row["sign_p_adjusted"], 10, 4)
              + _n(row["cash_p_adjusted"], 10, 4)
              + _n(row["beats_base_significantly"], 10)
              + _n(row["cash_positive"], 10)
              + _n(row["condsign_cell"], 10)
              + _n(row["condsign_cell_strict"], 10))
    print("\n  " + "ANTIFADE/asset/subset".ljust(34)
          + "usd/day".rjust(10) + "null_mean".rjust(12) + "p_raw".rjust(10)
          + "p_adj".rjust(10) + "cell".rjust(10))
    for row in block["antifade_rows"]:
        mark = "*" if row["deciding"] else " "
        print("  " + f"ANTIFADE/{row['asset']}{mark}/{row['subset']}".ljust(34)
              + _n(row["usd_day_continue"], 10, 1)
              + _n(row["null_mean"], 12, 1) + _n(row["p_raw"], 10, 4)
              + _n(row["p_adjusted"], 10, 4) + _n(row["antifade_cell"], 10))
    print(f"\n  CONDSIGN: {block['condsign']}   cells "
          f"{block['condsign_cells'] or 'none'}")
    print(f"  CONDSIGN, strict (also beats the majority class AND ranks, "
          f"AUC > 0.5): {block['condsign_strict']}   cells "
          f"{block['condsign_cells_strict'] or 'none'}")
    print("    strict is NOT the registered letter.  It is the same cell with "
          "the two checks the")
    print("    pre-registered accuracy cut cannot make.  Where the letter "
          "fires and strict does not,")
    print("    the accuracy is coming from a low base rate rather than from "
          "discrimination.")
    print(f"  ANTIFADE: {block['antifade']}   cells "
          f"{block['antifade_cells'] or 'none'}")
    print(f"  VERDICT: {block['verdict']}   (alpha {block['alpha']}, "
          f"* marks the deciding assets {tuple(block['deciding'])}; "
          "HG is report-only)")


# --------------------------------------------------------------------------
# SELFTEST.
# --------------------------------------------------------------------------

def _synth_conditional(days: int = 60, per_day: int = 240, seed: int = 5
                       ) -> tuple[list[S14.Stream], dict[str, list[int]],
                                  dict[str, list[int]]]:
    """Sign predictable ONLY inside the top-m subset, invisible pooled.

    Feature 0 is the size and it drives the magnitude LINEARLY, so the ridge on
    |Y| recovers it and the high-m subset really is the big-move subset.
    Feature 1 drives the sign, but its direction FLIPS between two populations,
    HIGH and LOW.  EVERY DAY carries exactly the same number of each, so every
    training prefix is exactly balanced and feature 1's marginal covariance
    with the sign is exactly zero: the unconditional fit cannot see it.  Inside
    the high-magnitude subset there is no LOW row left to cancel against and
    the same feature is decisive.  That is the USER's ordering, planted.

    Balancing at the ROW level rather than the day level is what makes the
    plant clean.  Making whole days HIGH or LOW - by alternating them or by
    drawing a random half - leaves each fold's training prefix off balance by a
    few days, the fitted coefficient inherits that imbalance, and the pooled
    baseline then reads as strongly ANTI-predictive.  That is a property of the
    schedule, not of the plant, and it would hide what this case is for.

    Days still alternate LOUD and QUIET, but only in SCALE, and the size order
    inside a quiet day is INVERTED: on a loud day the HIGH rows are the big
    ones (size 2-3), on a quiet day the LOW rows are (size 0.4-0.6, against
    0-0.2 for HIGH).  Globally every quiet-day row is smaller than every
    loud-day HIGH row, so a train-day threshold takes only HIGH rows.  A
    threshold computed on a quiet day's OWN values takes that day's top decile,
    which is entirely LOW - the flipped population - and the fitted model is
    then exactly backwards there.  That is the whole difference the mutant
    makes, and it is why it must show up as red rather than as noise.
    """

    rng = np.random.default_rng(seed)
    streams: list[S14.Stream] = []
    day_list: list[int] = []
    position = 0
    for day in range(days):
        d8 = 20220101 + day
        day_list.append(d8)
        loud = day % 2 == 0
        stream = S14.Stream(cell=position, asset="HG", d8=d8, phase="0")
        for slot in range(per_day):
            x = np.zeros(NFEAT, np.float64)
            high = slot % 2 == 0            # exact 50/50 inside every day
            draw = float(rng.random())
            if loud:
                size = (2.0 + draw) if high else draw
            else:
                size = (0.2 * draw) if high else (0.4 + 0.2 * draw)
            edge = float(rng.normal())
            x[0] = size
            x[1] = edge
            x[2:] = rng.normal(size=NFEAT - 2)
            direction = (1.0 if edge > 0.0 else -1.0) * (1.0 if high else -1.0)
            payoff = direction * (40.0 * size + 20.0 + float(rng.normal()))
            stream.occs.append(S14.Occ(
                row=position * 10_000 + slot, cell=position, asset="HG", d8=d8,
                phase="0", side=1, bar=slot + 1, k=slot + 1,
                remaining_s=float(S14.REMAIN_MIN_S + 600), payoff=payoff, x=x,
                y1800=1, soft_hit=True, delay_s=0.0, depth=0.0, side_ok=True,
                legal=True))
        streams.append(stream)
        position += 1
    explore = {"HG": day_list}
    score = {"HG": day_list[MIN_PRIOR_DAYS_FIT:]}
    return streams, explore, score


def _synth_antifade(days: int = 40, per_day: int = 200, seed: int = 9
                    ) -> tuple[list[S14.Stream], dict[str, list[int]],
                               dict[str, list[int]], dict[int, float]]:
    """The continue side pays on the high-magnitude rows, and only there."""

    rng = np.random.default_rng(seed)
    streams: list[S14.Stream] = []
    day_list: list[int] = []
    cont: dict[int, float] = {}
    position = 0
    for day in range(days):
        d8 = 20220101 + day
        day_list.append(d8)
        stream = S14.Stream(cell=position, asset="HG", d8=d8, phase="0")
        for slot in range(per_day):
            x = np.zeros(NFEAT, np.float64)
            size = abs(float(rng.normal()))
            x[0] = size
            x[1:] = rng.normal(size=NFEAT - 1)
            payoff = ((1.0 if rng.random() < 0.5 else -1.0)
                      * (40.0 * size + 20.0))
            row = position * 10_000 + slot
            cont[row] = (300.0 + 40.0 * float(rng.normal()) if size >= 1.5
                         else -60.0 + 40.0 * float(rng.normal()))
            stream.occs.append(S14.Occ(
                row=row, cell=position, asset="HG", d8=d8, phase="0", side=1,
                bar=slot + 1, k=slot + 1,
                remaining_s=float(S14.REMAIN_MIN_S + 600), payoff=payoff, x=x,
                y1800=1, soft_hit=True, delay_s=0.0, depth=0.0, side_ok=True,
                legal=True))
        streams.append(stream)
        position += 1
    return (streams, {"HG": day_list},
            {"HG": day_list[MIN_PRIOR_DAYS_FIT:]}, cont)


def _selftest_conditional() -> list[tuple[str, bool, str]]:
    """T2 must recover the planted conditional sign; the pooled fit must miss."""

    mutant = _mutant()
    streams, explore, score = _synth_conditional()
    table, _diag = walk_forward(streams, explore, score, None, None, mutant)
    days = {"HG": len(score["HG"])}
    t2 = t2_conditional(table, days, BASE_VARIANTS)
    decile = t2["HG"]["decile"]["ridge16"]
    quartile = t2["HG"]["quartile"]["ridge16"]
    pooled = t2["HG"]["unconditional"]["ridge16"]
    got = decile["accuracy"]
    return [
        _check("conditional/the top-decile subset is non-empty",
               decile["n"] > 200, f"{decile['n']} out-of-fold high-m rows"),
        _check("conditional/T2 recovers the planted sign inside the subset",
               got is not None and got >= 0.80,
               f"top-decile accuracy {got if got is None else round(got, 4)} "
               f"against base {round(decile['base_rate'], 4)}"),
        _check("conditional/the quartile subset recovers it too",
               quartile["accuracy"] is not None
               and quartile["accuracy"] >= 0.70,
               f"top-quartile accuracy {round(quartile['accuracy'], 4)}"),
        _check("conditional/the UNCONDITIONAL fit misses it",
               pooled["auc"] is not None and abs(pooled["auc"] - 0.5) < 0.05
               and pooled["excess_vs_base"] <= 0.02,
               f"pooled AUC {round(pooled['auc'], 4)} and excess over the "
               f"always-fade base {round(pooled['excess_vs_base'], 4)} - the "
               "planted signal flips between the two populations, so pooled it "
               "carries no marginal information at all"),
        _check("conditional/the cash cut is positive inside the subset",
               decile["usd_day_taken"] is not None
               and decile["usd_day_taken"] > 0.0,
               f"usd/day {round(decile['usd_day_taken'], 1)} against "
               "abstain-all 0.0"),
    ]


def _selftest_antifade() -> list[tuple[str, bool, str]]:
    """T4 must find the planted continue-side pay on the high-m rows."""

    mutant = _mutant()
    streams, explore, score, cont = _synth_antifade()
    table, _diag = walk_forward(streams, explore, score, None, cont, mutant)
    days = {"HG": len(score["HG"])}
    t4 = t4_antifade(table, days)
    top = t4["HG"]["decile"]
    return [
        _check("antifade/the continue side pays on the top-decile m rows",
               top["mean_cont_usd"] is not None and top["mean_cont_usd"] > 100.0,
               f"mean continue cert {round(top['mean_cont_usd'], 1)} usd over "
               f"{top['rows']} rows"),
        _check("antifade/P(continue cert > 0) is high inside the subset",
               top["p_cont_positive"] is not None
               and top["p_cont_positive"] > 0.90,
               f"P {round(top['p_cont_positive'], 4)} "
               f"[{round(top['lo'], 4)}, {round(top['hi'], 4)}]"),
        _check("antifade/usd/day entering WITH the move is positive",
               top["usd_day_continue"] is not None
               and top["usd_day_continue"] > 0.0,
               f"usd/day {round(top['usd_day_continue'], 1)}"),
    ]


def _wall_index(mids: Sequence[int], asset: str = "HG") -> M.MillIndex:
    """A synthetic one-cell index over a hand-written mid2 path."""

    count = len(mids)
    ts = np.arange(1, count + 1, dtype=np.int64) * 1_000_000_000
    mid2 = np.asarray(mids, np.int64)
    bid = mid2 // 2 - 1
    ask = mid2 // 2 + 1
    generation = np.zeros(count, np.uint32)
    return M.MillIndex(asset, ts, mid2, bid, ask, generation, ts, generation)


def _selftest_wall() -> list[tuple[str, bool, str]]:
    """One path, both sides: the walls differ, so the certs are not negations.

    The path runs hard DOWN from the entry.  A long walls out at -900; a short
    never does and rides to the phase close.  Every number below is computed
    from the law by hand - ``cert = side*(exit_mid - entry_mid2)*factor - cost``
    - and compared against ``MillIndex.outcome()``.
    """

    # A path that runs hard DOWN: the long side crosses its -900 boundary on
    # the first step, the short side never reaches its own +900-shaped one.
    probe = _wall_index([1_000_000, 1_000_001])
    entry = 1_000_000
    step = int(math.ceil(1200.0 / probe.factor))   # one step worth over 900
    mids = [entry, entry - step, entry - 2 * step, entry - 3 * step]
    index = _wall_index(mids)
    factor = index.factor
    stamp = int(index.ts[0]) + 1                 # strictly after row 0
    quote = index.current(stamp)
    assert quote is not None
    entry_mid2 = int(quote[2])
    cost = M.frozen_cost_usd(quote[0], quote[1], "HG")
    close = int(index.ts[-1])
    long_out = index.outcome(stamp, 1, entry_mid2, cost, close)
    short_out = index.outcome(stamp, -1, entry_mid2, cost, close)

    # By hand: the long's boundary is floor(entry + (-900 + cost)/factor); the
    # first row at or below it is the exit.  The short's boundary is
    # ceil(entry + (900 - cost)/factor) and the path never reaches it, so the
    # short exits on the last row at or before the close.
    long_boundary = math.floor(entry_mid2 + (-900.0 + cost) / factor)
    hits = [i for i, mid in enumerate(mids) if i >= 1 and mid <= long_boundary]
    long_exit = hits[0] if hits else len(mids) - 1
    long_cert = (mids[long_exit] - entry_mid2) * factor - cost
    short_boundary = math.ceil(entry_mid2 + (900.0 - cost) / factor)
    short_hits = [i for i, mid in enumerate(mids)
                  if i >= 1 and mid >= short_boundary]
    short_exit = short_hits[0] if short_hits else len(mids) - 1
    short_cert = -(mids[short_exit] - entry_mid2) * factor - cost

    got_long = float(long_out.cert_close_usd)
    got_short = float(short_out.cert_close_usd)
    return [
        _check("wall/the long side walls and the short side does not",
               bool(long_out.wall_hit) and not bool(short_out.wall_hit),
               f"long wall {long_out.wall_hit} at row {long_exit}, short wall "
               f"{short_out.wall_hit} at row {short_exit}"),
        _check("wall/the hand-computed LONG cert matches outcome()",
               abs(got_long - long_cert) < 1e-9,
               f"hand {long_cert:.6f} vs outcome() {got_long:.6f}"),
        _check("wall/the hand-computed SHORT cert matches outcome()",
               abs(got_short - short_cert) < 1e-9,
               f"hand {short_cert:.6f} vs outcome() {got_short:.6f}"),
        _check("wall/the two sides are NOT negations of one another",
               abs(got_long + got_short) > 1.0,
               f"long {got_long:.2f} + short {got_short:.2f} = "
               f"{got_long + got_short:.2f}, not 0 - the walls differ, so "
               "negating Y would misprice the continue side by that much"),
    ]


def _selftest_machinery() -> list[tuple[str, bool, str]]:
    rng = np.random.default_rng(3)
    labels = (rng.random(400) > 0.5).astype(np.float64)
    perfect = labels + 0.01 * rng.random(400)
    out = [
        _check("machinery/AUC is 1 on a perfectly ordered score",
               abs(auc(labels, perfect) - 1.0) < 1e-9,
               f"AUC {auc(labels, perfect):.6f}"),
        _check("machinery/AUC is 0.5 on a constant score",
               abs(auc(labels, np.zeros(400)) - 0.5) < 1e-9,
               f"AUC {auc(labels, np.zeros(400)):.6f}"),
    ]
    x = rng.normal(size=(600, 4))
    y01 = (x[:, 0] + 0.4 * rng.normal(size=600) > 0.0).astype(np.float64)
    fit = logistic_fit(x, y01)
    accuracy = float(np.mean((logistic_score(fit, x) > 0.0) == (y01 > 0.5)))
    out.append(_check("machinery/the logistic recovers a linear boundary",
                      accuracy > 0.85, f"in-sample accuracy {accuracy:.4f}"))
    blocks = np.repeat(np.arange(20), 30)
    perm = _block_permute(np.random.default_rng(7), blocks)
    out.append(_check("machinery/a block permutation never leaves its block",
                      bool(np.array_equal(blocks[perm], blocks)),
                      f"{len(blocks)} rows across {len(set(blocks.tolist()))} "
                      "asset-day blocks"))
    out.append(_check("machinery/a block permutation is a permutation",
                      bool(np.array_equal(np.sort(perm), np.arange(len(blocks)))),
                      "every row used exactly once"))
    lo, hi = wilson(50, 100)
    out.append(_check("machinery/Wilson brackets the point estimate",
                      lo < 0.5 < hi, f"[{lo:.4f}, {hi:.4f}] around 0.5"))
    return out


def _selftest_composite() -> list[tuple[str, bool, str]]:
    """The composite must point the way the absorption story says it points."""

    mean = np.zeros(NABS)
    sd = np.ones(NABS)
    absorbed = np.zeros(NABS)
    giving = np.zeros(NABS)
    for position, name in enumerate(ABS_FEATURES):
        absorbed[position] = ABS_COMPOSITE_SIGN[name]
        giving[position] = -ABS_COMPOSITE_SIGN[name]
    z_absorbed = float(_composite(absorbed.reshape(1, -1), mean, sd)[0])
    z_giving = float(_composite(giving.reshape(1, -1), mean, sd)[0])
    return [
        _check("composite/an absorbed row scores above a giving-way row",
               z_absorbed > z_giving,
               f"absorbed {z_absorbed:.4f} vs giving way {z_giving:.4f}"),
        _check("composite/a row with no evidence scores zero",
               abs(float(_composite(np.zeros((1, NABS)), mean, sd)[0])) < 1e-12,
               "a standardised all-mean row sits at the centre"),
        _check("composite/a non-finite part is dropped, not propagated",
               np.isfinite(float(_composite(
                   np.full((1, NABS), np.nan), mean, sd)[0])),
               "NaN parts contribute 0 rather than poisoning the composite"),
    ]


def _selftest_window() -> list[tuple[str, bool, str]]:
    """The absorption window must end at bar-1 and never touch bar."""

    flow = {name: np.zeros(20, np.float64) for name in
            ("vol", "delta", "twoside", "attack_low", "attack_high",
             "yield_low", "yield_high", "reload_low", "reload_high")}
    flow["vol"][:] = 1.0
    flow["attack_low"][:] = 1.0
    # A pure VOLUME spike on raw bar 10, with no matching attack.  Any window
    # that swallows it drives the attack share from 1.0 to almost nothing, so
    # the feature says plainly whether the bar was in scope.
    flow["vol"][10] = 1000.0

    class _Z:
        series = {"touches_so_far": np.ones(20), "held_so_far": np.ones(20),
                  "cum_attack": np.ones(20), "cum_ext_ticks": np.arange(20.0)}

    at_ten = absorption_vector(flow, _Z(), 1, 10)
    at_eleven = absorption_vector(flow, _Z(), 1, 11)
    share_at_ten = float(at_ten[ABS_FEATURES.index("attack_share")])
    share_at_eleven = float(at_eleven[ABS_FEATURES.index("attack_share")])
    ext_at_ten = float(at_ten[ABS_FEATURES.index("ext_per_attack")])
    return [
        _check("window/an occurrence at bar 10 cannot see raw flow bar 10",
               abs(share_at_ten - 1.0) < 1e-9,
               f"attack_share {share_at_ten:.6f} - raw bar 10 closes at "
               "lat[11], after the stamp, so the window is raw bars 0..9"),
        _check("window/an occurrence at bar 11 does see raw flow bar 10",
               share_at_eleven < 0.05,
               f"attack_share {share_at_eleven:.6f} - raw bar 10 closed at "
               "lat[11] and its volume is now in the window"),
        _check("window/the raw-flow span is half-open and stops at bar",
               _window_sum(np.arange(20.0), 5, 10) == float(sum(range(5, 10))),
               "sum over [5, 10) excludes the occurrence's own raw bar"),
        _check("window/the zone series are read at the lattice bar itself",
               abs(ext_at_ten - 10.0) < 1e-9,
               f"ext_per_attack {ext_at_ten:.3f} reads cum_ext_ticks[10]=10 - "
               "the zone cache is already to_lattice-shifted, so index 10 "
               "holds raw flow bar 9, which closed at lat[10]"),
    ]


def _selftest_threshold_law() -> list[tuple[str, bool, str]]:
    """Which values a threshold may be taken over, and what each mutant does."""

    train = np.arange(100.0)
    test = np.arange(1000.0, 1010.0)
    clean = _cut_pool(train, test, "")
    leaked = _cut_pool(train, test, MUTANT_TESTDAY)
    pooled = _cut_pool(train, test, MUTANT_POOLED)
    return [
        _check("threshold/the clean pool is the train days and nothing else",
               bool(np.array_equal(clean, train)),
               f"{len(clean)} train values, day d contributes none"),
        _check("threshold/uses_test_day swaps in day d's own values",
               bool(np.array_equal(leaked, test)),
               f"{len(leaked)} values, all from the day being scored"),
        _check("threshold/pools_test_day appends day d to the train pool",
               len(pooled) == len(train) + len(test),
               f"{len(pooled)} values = {len(train)} train + {len(test)} test"),
    ]


def selftest() -> int:
    mutant = _mutant()
    print(f"sweep 17 selftest  spec_sha {SPEC_SHA[:16]}  "
          f"code_sha {code_sha()[:16]}  mutant {mutant or 'none'}")
    rows: list[tuple[str, bool, str]] = []
    rows += _selftest_machinery()
    rows += _selftest_window()
    rows += _selftest_composite()
    rows += _selftest_threshold_law()
    rows += _selftest_wall()
    rows += _selftest_conditional()
    rows += _selftest_antifade()
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

def log_rows(report: Mapping[str, object]) -> list[dict[str, object]]:
    params = json.dumps({"lambda": RIDGE_LAMBDA, "features": NFEAT,
                         "absorption_features": NABS,
                         "window_bars": ABS_WINDOW,
                         "min_prior_days": MIN_PRIOR_DAYS_FIT,
                         "subsets": {s: SUBSET_Q[s] for s in SUBSETS},
                         "deciles": N_DECILES, "draws": NULL_DRAWS,
                         "alpha": ALPHA})
    shared = {
        "registered_utc": report["registered_utc"], "family": FAMILY,
        "params": params, "spec_sha": SPEC_SHA, "code_sha": report["code_sha"],
        "split_sha": report["split_sha"],
        "outcome_law_sha": report["outcome_law_sha"], "null_seed": SEED,
        "parent_trial": PARENT_TRIAL, "selection_rule": SELECTION_RULE,
        "verdict": "",
    }
    usd_field = {"HG": "hg_usd_day", "NKD": "nkd_usd_day", "SI": "si_usd_day"}
    rows: list[dict[str, object]] = []
    counter = 0

    for asset in ASSETS:
        block = report["t1"][asset]
        for row in block["deciles"]:
            counter += 1
            rows.append({
                **shared, "id": f"sweep17-{counter:03d}",
                "rule": f"BASERATE/{asset}/d{row['decile']:02d}",
                "days": block["days"], "coverage": (
                    row["n"] / block["overall"]["n"]
                    if block["overall"]["n"] else None),
                usd_field[asset]: row["usd_day"],
                "note": (
                    f"m-decile {row['decile']}: n {row['n']}, P(Y>0) "
                    f"{_f(row['p_pos'])} [{_f(row['lo'])},{_f(row['hi'])}], "
                    f"meanY {_f(row['mean_y'], 2)}, medY "
                    f"{_f(row['median_y'], 2)}, mean|Y| "
                    f"{_f(row['mean_absy'], 1)}, mean m "
                    f"{_f(row['mean_m'], 1)}")[:400],
            })

    for asset in ASSETS:
        counter += 1
        block = report["t2"][asset]["unconditional"]["ridge16"]
        rows.append({
            **shared, "id": f"sweep17-{counter:03d}",
            "rule": f"UNCOND/{asset}",
            "days": report["scoring_day_counts"][asset],
            usd_field[asset]: block["usd_day_taken"],
            "note": (
                f"unconditional sign fit on all {block['n']} scored rows: "
                f"acc {_f(block['accuracy'])} vs base "
                f"{_f(block['base_rate'])} (excess "
                f"{_f(block['excess_vs_base'])}), AUC {_f(block['auc'])}, "
                f"usd/day {_f(block['usd_day_taken'], 1)}; sweep15 oof R2 "
                f"sign {SWEEP15_OOF_R2[asset]['signY']}")[:400],
        })

    for asset in ASSETS:
        for subset in SUBSETS:
            for variant in VARIANTS:
                counter += 1
                block = report["t2"][asset][subset][variant]
                sign = report["nulls"]["SIGN"].get(
                    f"SIGN/{asset}/{subset}/{variant}", {})
                cash = report["nulls"]["CASH"].get(
                    f"CASH/{asset}/{subset}/{variant}", {})
                tag = "CONDSIGN" if variant.endswith("16") else "ABSMODEL"
                rows.append({
                    **shared, "id": f"sweep17-{counter:03d}",
                    "rule": f"{tag}/{subset}/{variant}/{asset}",
                    "days": report["scoring_day_counts"][asset],
                    "coverage": report["t2"][asset][subset]["share_of_scored"],
                    usd_field[asset]: block["usd_day_taken"],
                    "null_margin": sign.get("p_adjusted"),
                    "note": (
                        f"n {block['n']}, acc {_f(block['accuracy'])}, base "
                        f"{_f(block['base_rate'])}, excess "
                        f"{_f(block['excess_vs_base'])}, vs_majority "
                        f"{_f(block['excess_vs_majority'])}, AUC "
                        f"{_f(block['auc'])} (z {_f(block['auc_z'], 2)}), taken "
                        f"{block['taken']}, meanY_taken "
                        f"{block['mean_y_taken']}, usd/day "
                        f"{block['usd_day_taken']} vs abstain 0; p_sign_adj "
                        f"{sign.get('p_adjusted')}, p_cash_adj "
                        f"{cash.get('p_adjusted')}")[:400],
                })

    for asset in ASSETS:
        for subset in SUBSETS:
            row = report["t3"]["discrete_cut"][asset][subset]
            for tag, cell in (("present", row["present"]),
                              ("absent", row["absent"])):
                counter += 1
                rows.append({
                    **shared, "id": f"sweep17-{counter:03d}",
                    "rule": f"ABSORB/{subset}/{asset}/{tag}",
                    "days": report["scoring_day_counts"][asset],
                    usd_field[asset]: (row["usd_day_present"] if tag == "present"
                                       else row["usd_day_absent"]),
                    "note": (
                        f"absorption {tag} inside {subset} high-m: n "
                        f"{cell['n']}, P(Y>0) {cell['p_pos']} "
                        f"[{cell['lo']},{cell['hi']}], meanY {cell['mean_y']}; "
                        f"gap P {row['p_pos_gap']}, gap meanY "
                        f"{row['mean_y_gap_usd']}, wilson disjoint "
                        f"{row['wilson_disjoint']}")[:400],
                })

    for asset in ASSETS:
        for subset in SUBSETS:
            counter += 1
            row = report["t4"][asset][subset]
            entry = report["nulls"]["ANTIFADE"].get(
                f"ANTIFADE/{asset}/{subset}", {})
            rows.append({
                **shared, "id": f"sweep17-{counter:03d}",
                "rule": f"ANTIFADE/{subset}/{asset}",
                "days": report["scoring_day_counts"][asset],
                usd_field[asset]: row["usd_day_continue"],
                "null_margin": entry.get("p_adjusted"),
                "note": (
                    f"continue side on {subset} high-m: n {row['rows']}, mean "
                    f"{row['mean_cont_usd']}, P(>0) {row['p_cont_positive']} "
                    f"[{row['lo']},{row['hi']}], usd/day "
                    f"{row['usd_day_continue']} vs fade "
                    f"{row['usd_day_fade']}; mean|cont+Y| "
                    f"{row['mean_abs_negation_gap_usd']}, p_adj "
                    f"{entry.get('p_adjusted')}")[:400],
            })

    counter += 1
    ruling = report["decision"]
    rows.append({
        **shared, "id": f"sweep17-{counter:03d}", "rule": "RULING",
        "days": sum(report["scoring_day_counts"].values()),
        "note": (
            f"{ruling['verdict']}: CONDSIGN {ruling['condsign']} cells "
            f"{ruling['condsign_cells'] or 'none'} (strict, also beating the "
            f"majority class and ranking: {ruling['condsign_strict']} "
            f"{ruling['condsign_cells_strict'] or 'none'}); ANTIFADE "
            f"{ruling['antifade']} cells {ruling['antifade_cells'] or 'none'}; "
            f"deciding {list(DECIDING)}, alpha {ALPHA}, "
            f"{NULL_DRAWS} block-permutation draws")[:400],
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

    absorb = build_absorption(streams, cells)
    cont, cont_legal, cont_counters = build_continue(streams, cells)
    scoring = scoring_days(explore_days, plane.stratum_day_cells)

    gate_block = gate(plane, scoring, absorb)
    if not gate_block["matches"]:
        raise SweepRefusal(
            "the sweep-14 stream did not reproduce, or the absorption join was "
            "not strictly prior to the stamp; no measurement is believed past "
            f"here: {json.dumps({k: v for k, v in gate_block.items() if k != 'absorption_counters'}, default=str)}")

    hand = handcheck_continue(streams, cells, cont)
    if not hand["matches"]:
        raise SweepRefusal("the flipped-side batch path disagreed with "
                           "MillIndex.outcome(); T4 is not believed")

    table, diag = walk_forward(streams, explore_days, scoring, absorb.values,
                               cont, mutant)
    days = {asset: len(scoring[asset]) for asset in ASSETS}
    t1 = t1_base_rates(table, days)
    t2 = t2_conditional(table, days)
    t3 = t3_absorption(table, days, t2)
    t4 = t4_antifade(table, days)
    nulls = build_nulls(table, days)
    ruling = decide(t2, nulls)

    return {
        "schema": "QRE2MILLSWEEP17", "spec_sha": SPEC_SHA, "code_sha": code_sha(),
        "split_sha": S1.split_sha(), "outcome_law_sha": S1.outcome_law_sha(),
        "seed": SEED, "draws": NULL_DRAWS, "mutant": mutant, "family": FAMILY,
        "parent_trial": PARENT_TRIAL, "selection_rule": SELECTION_RULE,
        "registered_utc": S14.report_stamp(),
        "asset_days": {a: int(asset_days.get(a, 0)) for a in ASSETS},
        "explore_days": {a: len(explore_days[a]) for a in ASSETS},
        "scoring_days": {a: list(scoring[a]) for a in ASSETS},
        "scoring_day_counts": days,
        "gate": gate_block, "stream_counters": counters, "causality": causal,
        "continue_counters": cont_counters,
        "handcheck": hand,
        "fold_diagnostics": diag,
        "sweep15_context": SWEEP15_OOF_R2,
        "t1": t1, "t2": t2, "t3": t3, "t4": t4,
        "nulls": nulls, "decision": ruling,
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
    print(f"sweep 17 spec_sha {SPEC_SHA[:16]} code_sha {code_sha()[:16]} "
          f"seed {SEED} draws {NULL_DRAWS} mutant {report['mutant'] or 'none'}")
    print_gate(report["gate"])
    print(f"\nstreams {report['stream_counters']['streams']} cells, "
          f"{report['stream_counters']['occs']} occurrences; scoring days "
          f"{report['scoring_day_counts']}; folds "
          f"{report['fold_diagnostics']['folds']}; out-of-fold rows "
          f"{report['fold_diagnostics']['rows']}")
    print(f"continue side: {report['continue_counters']['legal']} legal, "
          f"{report['continue_counters']['illegal']} illegal of "
          f"{report['continue_counters']['rows']} rows")
    print_t1(report["t1"])
    print_t2(report["t2"], report["nulls"])
    print_t3(report["t3"])
    print_t4(report["t4"], report["nulls"], report["handcheck"])
    print_decision(report["decision"])
    write_report(report)
    print(f"\nwrote {OUT_PATH} in {report['elapsed_s']} s")
    if args.log:
        written = S1.append_log(log_rows(report))
        print(f"appended {written} hypothesis-log rows to {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
