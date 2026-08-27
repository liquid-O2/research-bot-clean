#!/usr/bin/env python3
"""Sweep 14 of the side-resolution mill: the fitted stopping policy.

Sol's blank-slate root cause (``.audit/briefs/mill-side-resolution.md``, section
"Sol's blank-slate root cause: argfirst") says the load-bearing error across the
program is that every executable policy takes the FIRST occurrence clearing a
local predicate and spends the cell - ``argfirst`` where the domain is an
ordered stopping process.  Sweep 13 tested one hand-picked ordinal.  This unit
implements the diagnosis in full: approximate optimal stopping by backward
fitted value iteration over each cell's ordered decision opportunities, so the
occurrence ordinal stops being a constant and becomes fitted policy state.

Machinery is imported, never re-implemented.  Sweep 9's ``build_plane`` IS the
occurrence plane - one row per distinct in-zone CLEAR candidate under identity
dedup - and its counters are this unit's refuse-to-run reproduction gate.
Sweep 8 supplies E1..E5, the arming law, ``_finish`` and ``entries_of``; sweep 1
supplies the outcome law, cash, replay, the block null and the log; sweep 2's
``star`` supplies soft-hit and ``sign(Delta*)`` as diagnostics only; sweep 12
supplies the causally-visible regime states V1/V2/V3; sweep 3 supplies the
adversarial stress line.
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
import context as CTX  # noqa: F401  (sweep 12 reads the day states through it)
import flow as FLOW  # noqa: F401
import flow_zones as ZONES  # noqa: F401
import sweep1 as S1
import sweep2 as S2  # noqa: F401  (star_cell rides inside Cell8; diagnostics only)
import sweep3 as S3
import sweep7a as S7A
import sweep8 as S8
import sweep9_twins as S9
import sweep12 as S12

# --------------------------------------------------------------------------
# The law, registered before anything is read.
# --------------------------------------------------------------------------

SPEC = """QRE2MILLSWEEP14
tier=constructive; EXPLORE-only.  Parent = sweep12-007, the hypothesis-log tail
  at registration.  Family F11-FITSTOP.  Seed 20260827.
DATA LAW.  EXPLORE days only, off the existing mill caches.  No packs, no HOLD,
  no teacher labels, no 2021, no 2025.  ONE ROW IS ONE DISTINCT IN-ZONE CLEAR
  CANDIDATE at its own decision timestamp, built by sweep 9's ``build_plane``
  verbatim: fade-side CLEAR candidate (sweep 1 ``make_entry`` legality), decision
  quote within 0.15*ATR14_prev of the side's running extreme, side extreme age
  >= 300 s, phase time remaining >= 1800 s, tradeable bar, 1800 s window inside
  the phase, identity (side, decision mid2, running-extreme mid2) deduped to its
  FIRST bar.  Sweep 9's plane counters and its certifiable-cell counts
  (138/132/132) are the refuse-to-run gate.
DECISION PROCESS.  Per cell, the ordered stream of deduped occurrences from BOTH
  sides interleaved chronologically by decision bar (ties: side +1 first).  At
  occurrence k the policy may ENTER - fade the side of that occurrence's
  extreme, candidate-anchored entry at its own decision stamp, frozen outcome
  law - or WAIT.  One entry per cell; entering ends the cell; never entering
  scores zero.  ENTER requires >= 1800 s remaining, which the plane's admission
  law already enforces and this unit re-asserts at the decision.
LABELS, EXPLORE-lawful.  Y_k = the exact cert in USD of entering at occurrence
  k, ``rec.cert(side)[bar]``, i.e. the frozen mill outcome law evaluated at that
  stamp.  Training targets only.  This is the mill's standard exploratory use of
  the frozen law; it is not a teacher label and it never enters a feature.
FEATURES, 16, all causal at the occurrence's own stamp: ord_side (in-zone
  ordinal within (cell, side) reset by every same-side new extreme - the
  sweep-13 reset law, taken from sweep 9's ``inzone_ordinal``); ord_cell
  (ordinal within the cell over both sides); E1 quiet-age percentile; E2 tape
  ratio; E3 one-sidedness of the last touch; E4 interarrival stretch; E5
  opposite-side recency; depth_atr (candidate quote from the running extreme in
  ATR); remain_frac (remaining phase time / phase length); phase_1 and phase_2
  one-hots (2 dof, phase 0 the baseline); V1 forecast-variance tercile; V2
  prior-day realized range in ATR14_prev tercile; V3 ATR14_prev tercile;
  range_atr (the cell's running mid range so far in ATR); side sign.  Terciles
  are sweep 12's walk-forward bins coded LOW=-1, MID=0, HIGH=+1, UNSCORED=0.
  Missing continuous fields impute to the fold's TRAINING-set column mean.
THE FIT.  Walk-forward by day per asset: a day is scored only with >= 25 strictly
  prior EXPLORE days for its asset; earlier days are unscored.  The fold's
  training cells are that asset's certifiable cells on strictly earlier EXPLORE
  days.  Backward fitted value iteration over each training cell's occurrence
  sequence: V_{K+1} = 0 per cell; for k = Kmax..1 the rows at position k carry
  continuation target C_k = V_{k+1}, the realized payoff of the fitted policy
  from k+1 on that same cell as decided earlier in this same backward pass.  At
  each step two ridge regressions (lambda 1.0, features standardized, intercept
  unpenalized, pure numpy, closed form) are fitted on the pass's accumulated
  TAIL - every training row at position >= k, which is the set whose downstream
  decisions are already final: Q_enter on (features -> Y) and C on
  (features -> C).  The step's policy is ENTER iff Q_enter(s_k) > max(C(s_k),
  tau) with tau = 0, and V_k is set to Y_k or C_k accordingly.  The pass ends at
  k = 1, where the tail is every training row: those TWO ridges per asset - one
  Q_enter, one C, pooled across phases with the phase one-hots carrying the
  difference - are the fold's frozen coefficients.  A step whose tail holds
  fewer than 50 rows decides WAIT.  Scoring days apply the frozen coefficients
  forward through their own occurrence sequences with NO refit and no target of
  their own, entering at the first k with Q_enter > max(C, 0).
CONTROLS, on the identical scoring cells: FIRST (enter at occurrence 1 - the
  argfirst baseline), RANDOM (50 seeded draws, uniform over the cell's
  occurrences), ORACLE (hindsight argmax_k Y_k - the ceiling of this decision
  process, labelled oracle and never a policy).
STAGE A, no cash beyond the training labels, scoring days only, per asset and
  phase: scored cells, entries, coverage, chosen-ordinal distribution against
  the all-occurrences baseline, postX_1800 at entry, soft-hit, delay from the
  side's true terminal (median and p90), depth, and entered-side agreement with
  sign(Delta*) as a diagnostic.
STAGE B, cash on scoring days: the fitted policy priced with cash/day against
  the rungs on the SCORING-DAY denominators, per-trade, win rate, wall rate, MDD
  in both orderings, engine replay (partial-day label), 2% adversarial stress,
  and the block-permutation null (200 draws, max-stat over the priced lines).
  NKD and SI decide; HG is report-only.  FIRST is priced too, for the head-to-
  head.
DECISION TABLE, pre-registered.  FREEZE-CANDIDATE: on a deciding asset, usd/day
  >= the rung on the scoring-day denominator, MDD < 1000 in both orderings,
  stress usd/day > 0, adjusted null p <= 0.05.  STRONG-SIGNAL: on a deciding
  asset the fitted policy beats FIRST by >= 300 usd/day with wall rate <= 0.20
  and postX_1800 <= 0.30.  KILL otherwise, with the fired bounds and the
  oracle-capture ratio (fitted cash / oracle cash) reported.
MUTANTS, both must turn the selftest red.  QRE2_MILL_S14_MUTANT=
  sweep14_train_includes_today puts the scoring day's own cells in the fold.
  QRE2_MILL_S14_MUTANT=sweep14_label_in_features appends the occurrence's own
  payoff to the feature vector.
"""

ASSETS = S1.ASSETS
DECIDING = ("NKD", "SI")
REPORT_ONLY = ("HG",)
PHASES = ("0", "1", "2")
BAR_SECONDS = S1.BAR_SECONDS
SEED = 20260827

# Frozen, inherited.  An alias so a drift upstream fails loudly here.
DEPTH_ATR = S8.DEPTH_ATR                 # 0.15
REMAIN_MIN_S = S8.REMAIN_MIN_S           # 1800
HORIZON_BARS = S8.HORIZON_BARS           # 30 bars of 60 s
DAY_RUNG_USD = S1.DAY_RUNG_USD
MDD_CEILING = S1.MDD_CAP_USD             # 1000
NULL_DRAWS = S1.NULL_DRAWS               # 200
STRESS_RATE = S3.STRESS_RATE             # 0.02

# The one new law.
MIN_PRIOR_DAYS_FIT = 25
RIDGE_LAMBDA = 1.0
TAU = 0.0
MIN_FIT_ROWS = 50
RANDOM_DRAWS = 50

# Pre-registered decision bounds.
STRONG_GAIN_USD = 300.0
STRONG_WALL_CEILING = 0.20
STRONG_POSTX_CEILING = 0.30
NULL_CEILING = 0.05

# The refuse-to-run gate: sweep 9's published plane.
REPRO_CERTIFIABLE = {"HG": 138, "NKD": 132, "SI": 132}
REPRO_ROWS = 47402
REPRO_COUNTERS = {"cancelled": 0, "candidates_seen": 313131, "cells_with_rows": 385,
                  "dropped_eligibility": 49564, "dropped_identity": 74139,
                  "dropped_window": 62, "dropped_zone": 141964}

FEATURES = ("ord_side", "ord_cell", "E1", "E2", "E3", "E4", "E5", "depth_atr",
            "remain_frac", "phase_1", "phase_2", "V1", "V2", "V3", "range_atr",
            "side")
NFEAT = len(FEATURES)
LABEL_FEATURE = "label_payoff"

POLICIES = ("FITTED", "FIRST", "RANDOM", "ORACLE")
PRICED = ("FITTED", "FIRST")

FAMILY = "F11-FITSTOP"
PARENT_TRIAL = "sweep12-007"
SELECTION_RULE = ("none: pre-registered feature set, lambda 1.0, tau 0, "
                  "no threshold tuning, no variant choice")

MUTANT_ENV = "QRE2_MILL_S14_MUTANT"
MUTANT_TODAY = "sweep14_train_includes_today"
MUTANT_LABEL = "sweep14_label_in_features"
MUTANTS = (MUTANT_TODAY, MUTANT_LABEL)

OUT_PATH = ROOT / ".audit/mill-sweep14.json"
LOG_PATH = S1.LOG_PATH

TERCILE_CODE = {"LOW": -1.0, "MID": 0.0, "HIGH": 1.0}


class SweepRefusal(RuntimeError):
    pass


SPEC_SHA = S1._sha_text(SPEC)


def code_sha() -> str:
    return S1._sha_file(Path(__file__).resolve())


def _mutant() -> str:
    name = os.environ.get(MUTANT_ENV, "")
    if name and name not in MUTANTS:
        raise SweepRefusal(f"unknown sweep-14 mutant {name!r}; known: {MUTANTS}")
    return name


def _rate(hits: float, total: float) -> dict[str, object]:
    if total <= 0:
        return {"n": 0, "rate": None, "lo": None, "hi": None}
    lo, hi = S1.wilson(int(round(hits)), int(total))
    return {"n": int(total), "rate": float(hits) / float(total),
            "lo": float(lo), "hi": float(hi)}


def _q(values: Sequence[float], mark: float) -> float | None:
    if not len(values):
        return None
    return float(np.percentile(np.asarray(values, np.float64), mark))


# --------------------------------------------------------------------------
# The occurrence stream: sweep 9's row plane, re-keyed as ordered cell streams.
# --------------------------------------------------------------------------

def side_ordinals(bars: Sequence[int], extreme_bars: Sequence[int]
                  ) -> list[int]:
    """Reference implementation of the sweep-13 reset law, for the selftest.

    The in-zone ordinal counts candidates since the side's last NEW EXTREME and
    restarts at 1 on every one of them.  ``build_plane`` computes exactly this
    as ``inzone_ordinal``; this function exists so the law itself is testable
    without the caches.
    """

    marks = np.asarray(sorted(int(b) for b in extreme_bars), np.int64)
    out: list[int] = []
    ordinal = 0
    last_mark = -1
    for raw in bars:
        bar = int(raw)
        seen = marks[marks <= bar]
        mark = int(seen[-1]) if len(seen) else -1
        if mark != last_mark:
            ordinal = 0
            last_mark = mark
        ordinal += 1
        out.append(ordinal)
    return out


def fold_days(days: Sequence[int], index: int, mutant: str) -> list[int]:
    """The fold's training days: STRICTLY prior to the day being scored.

    The whole walk-forward law is this one slice, so it is a named function the
    selftest can hold to account rather than a subscript buried in the loop.
    """

    if mutant == MUTANT_TODAY:
        # The mutant hands the fold the day it is about to score.
        return [int(day) for day in days[:index + 1]]
    return [int(day) for day in days[:index]]


def feature_vector(values: Sequence[float], payoff: float, mutant: str
                   ) -> np.ndarray:
    """The frozen 16-wide causal vector; the mutant appends the outcome."""

    x = np.asarray(values, np.float64)
    if mutant == MUTANT_LABEL:
        return np.concatenate([x, np.asarray([float(payoff)], np.float64)])
    return x


@dataclass(slots=True)
class Occ:
    """One decision opportunity: a deduped in-zone CLEAR candidate."""

    row: int                    # index into the sweep-9 plane
    cell: int                   # cell position (indexes the record list)
    asset: str
    d8: int
    phase: str
    side: int
    bar: int
    k: int                      # ordinal within the cell, both sides, 1-based
    remaining_s: float
    payoff: float               # Y_k, the exact cert of entering here
    x: np.ndarray               # (NFEAT,) causal features
    # Stage-A diagnostics, never features.
    y1800: int
    soft_hit: bool
    delay_s: float
    depth: float
    side_ok: bool | None
    legal: bool


@dataclass(slots=True)
class Stream:
    """One cell's ordered decision process."""

    cell: int
    asset: str
    d8: int
    phase: str
    occs: list[Occ] = field(default_factory=list)


def _phase_length_s(elapsed: float, remaining: float) -> float:
    total = float(elapsed) + float(remaining)
    return total if total > 0.0 else float("nan")


def build_streams(plane: S9.Plane, cells: Sequence[S8.Cell8],
                  states: Mapping[tuple[str, int], S12.DayState],
                  mutant: str = "") -> tuple[list[Stream], dict[str, int]]:
    """Turn the sweep-9 row plane into per-cell ordered occurrence streams.

    The plane's rows are emitted side by side; the decision process needs them
    interleaved chronologically, so each cell's rows are re-sorted by decision
    bar with side +1 first on a tie.  Everything else is read out of the plane
    exactly as sweep 9 built it - no row is added, dropped or re-derived.
    """

    by_position = {cell.position: cell for cell in cells}
    idx = S9.FIELD_INDEX
    counters = {"rows": int(plane.n), "streams": 0, "occs": 0,
                "illegal_entries": 0, "below_floor": 0, "label_leak_feature": 0}

    order: dict[int, list[int]] = {}
    for row in range(plane.n):
        order.setdefault(int(plane.cell[row]), []).append(row)

    streams: list[Stream] = []
    for position in sorted(order):
        rows = order[position]
        cell = by_position[position]
        # Chronological interleave of the two sides; +1 before -1 at a tie so
        # the stream is a total order that does not depend on dict insertion.
        rows.sort(key=lambda r: (int(plane.bar[r]), -int(plane.side[r])))
        stream = Stream(cell=position, asset=cell.asset, d8=cell.d8,
                        phase=cell.phase)
        state = states.get((cell.asset, cell.d8))
        mid = np.asarray(cell.rec.mid, np.float64)
        run_high = np.maximum.accumulate(mid)
        run_low = np.minimum.accumulate(mid)
        range_atr = ((run_high - run_low) / cell.atr_mid2
                     if cell.atr_mid2 > 0.0 else np.zeros_like(mid))
        for k, row in enumerate(rows, start=1):
            side = int(plane.side[row])
            bar = int(plane.bar[row])
            raw = plane.raw[row]
            remaining = float(plane.remaining[row])
            if remaining < REMAIN_MIN_S:
                # Belt and braces: the plane already refuses these, and the
                # decision gate below refuses them again.
                counters["below_floor"] += 1
            made = S1.make_entry(position, cell.rec, bar, side)
            if made is None:
                counters["illegal_entries"] += 1
            payoff = float(made.cert_usd) if made is not None else 0.0
            terminal = S7A.terminal_bar(cell.geo, side)
            sign = int(cell.star.sign[bar])
            bins = state.bins if state is not None else {}
            x = feature_vector([
                float(raw[idx["inzone_ordinal"]]),
                float(k),
                float(raw[idx["E1"]]), float(raw[idx["E2"]]),
                float(raw[idx["E3"]]), float(raw[idx["E4"]]),
                float(raw[idx["E5"]]),
                float(raw[idx["depth_atr"]]),
                remaining / _phase_length_s(float(plane.elapsed[row]), remaining),
                1.0 if cell.phase == "1" else 0.0,
                1.0 if cell.phase == "2" else 0.0,
                TERCILE_CODE.get(str(bins.get(S12.V1, "")), 0.0),
                TERCILE_CODE.get(str(bins.get(S12.V2, "")), 0.0),
                TERCILE_CODE.get(str(bins.get(S12.V3, "")), 0.0),
                float(range_atr[bar]),
                float(side),
            ], payoff, mutant)
            if len(x) != NFEAT:
                # The mutant reads the outcome the policy is choosing over.
                counters["label_leak_feature"] += 1
            stream.occs.append(Occ(
                row=row, cell=position, asset=cell.asset, d8=cell.d8,
                phase=cell.phase, side=side, bar=bar, k=k,
                remaining_s=remaining, payoff=payoff, x=x,
                y1800=int(plane.y1800[row]),
                soft_hit=bool(float(cell.star.rem(side)[bar]) > 0.0),
                delay_s=float(plane.delay_s[row]),
                depth=float(raw[idx["depth_atr"]]),
                side_ok=None if sign == 0 else bool(side == sign),
                legal=made is not None))
        counters["occs"] += len(stream.occs)
        streams.append(stream)
    counters["streams"] = len(streams)
    if counters["illegal_entries"]:
        raise SweepRefusal("a plane row was not a legal make_entry; the "
                           "occurrence stream and the outcome law disagree")
    if counters["below_floor"]:
        raise SweepRefusal("a plane row sat below the 1800 s remaining floor")
    return streams, counters


def assert_causal(streams: Sequence[Stream], plane: S9.Plane | None = None
                  ) -> dict[str, object]:
    """No feature may read the future: the checks that make that concrete."""

    checks: dict[str, object] = {}
    width = {len(occ.x) for stream in streams for occ in stream.occs}
    checks["feature_width"] = sorted(width)
    payoffs: list[float] = []
    columns: list[np.ndarray] = []
    for stream in streams:
        for occ in stream.occs:
            payoffs.append(occ.payoff)
            columns.append(occ.x)
    matrix = np.vstack(columns)
    target = np.asarray(payoffs, np.float64)
    y1800 = np.asarray([occ.y1800 for stream in streams for occ in stream.occs],
                       np.float64)
    worst_payoff = 0.0
    worst_label = 0.0
    for column in range(matrix.shape[1]):
        col = matrix[:, column]
        good = np.isfinite(col)
        if good.sum() < 3 or float(np.std(col[good])) <= 0.0:
            continue
        for series, holder in ((target, "payoff"), (y1800, "label")):
            if float(np.std(series[good])) <= 0.0:
                continue
            with np.errstate(invalid="ignore", divide="ignore"):
                corr = abs(float(np.corrcoef(col[good], series[good])[0, 1]))
            if not math.isfinite(corr):
                continue
            if holder == "payoff":
                worst_payoff = max(worst_payoff, corr)
            else:
                worst_label = max(worst_label, corr)
    checks["max_abs_corr_with_payoff"] = worst_payoff
    checks["max_abs_corr_with_y1800"] = worst_label
    # A feature that IS the outcome shows up as a unit correlation.  Nothing
    # causal can reach 1.0 across 47k rows spanning three assets.
    checks["no_outcome_in_features"] = bool(worst_payoff < 0.999
                                            and worst_label < 0.999)
    checks["remaining_floor_ok"] = bool(all(
        occ.remaining_s >= REMAIN_MIN_S for stream in streams
        for occ in stream.occs))
    bars_ok = True
    for stream in streams:
        bars = [occ.bar for occ in stream.occs]
        if any(bars[i] > bars[i + 1] for i in range(len(bars) - 1)):
            bars_ok = False
    checks["stream_is_chronological"] = bars_ok
    checks["rows_match_plane"] = (True if plane is None else bool(
        sum(len(s.occs) for s in streams) == int(plane.n)))
    return checks


# --------------------------------------------------------------------------
# Ridge regression, closed form, pure numpy.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Ridge:
    """A fitted ridge: standardiser, unpenalised intercept, coefficients."""

    mean: np.ndarray
    sd: np.ndarray
    intercept: float
    beta: np.ndarray
    n: int

    def predict(self, x: np.ndarray) -> np.ndarray:
        z = (np.atleast_2d(x) - self.mean) / self.sd
        return self.intercept + z @ self.beta


@dataclass(slots=True)
class Sums:
    """Running sufficient statistics for the backward pass's tail fits.

    The tail only ever grows as ``k`` walks down, so the two ridges at every
    step come out of these sums with no re-scan of the rows.
    """

    width: int
    n: int = 0
    sx: np.ndarray = field(default=None)         # type: ignore[assignment]
    sxx: np.ndarray = field(default=None)        # type: ignore[assignment]
    sy: float = 0.0
    sxy: np.ndarray = field(default=None)        # type: ignore[assignment]
    sc: float = 0.0
    sxc: np.ndarray = field(default=None)        # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.sx = np.zeros(self.width, np.float64)
        self.sxx = np.zeros((self.width, self.width), np.float64)
        self.sxy = np.zeros(self.width, np.float64)
        self.sxc = np.zeros(self.width, np.float64)

    def add(self, x: np.ndarray, y: np.ndarray, c: np.ndarray) -> None:
        self.n += int(x.shape[0])
        self.sx += x.sum(axis=0)
        self.sxx += x.T @ x
        self.sy += float(y.sum())
        self.sxy += x.T @ y
        self.sc += float(c.sum())
        self.sxc += x.T @ c

    def _standardiser(self) -> tuple[np.ndarray, np.ndarray]:
        mean = self.sx / self.n
        var = np.diag(self.sxx) / self.n - mean * mean
        sd = np.sqrt(np.maximum(var, 0.0))
        sd[sd <= 1e-12] = 1.0          # a constant column contributes nothing
        return mean, sd

    def fit(self, target: str, lam: float = RIDGE_LAMBDA) -> Ridge:
        """Ridge on standardised features with the intercept unpenalised."""

        mean, sd = self._standardiser()
        scale = np.outer(sd, sd)
        gram = (self.sxx - self.n * np.outer(mean, mean)) / scale
        sy, sxy = ((self.sy, self.sxy) if target == "Y" else (self.sc, self.sxc))
        rhs = (sxy - mean * sy) / sd
        lhs = gram + lam * np.eye(self.width)
        beta = np.linalg.solve(lhs, rhs)
        return Ridge(mean=mean, sd=sd, intercept=float(sy / self.n), beta=beta,
                     n=int(self.n))


# --------------------------------------------------------------------------
# The backward fitted value iteration.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Fold:
    """One asset-day's frozen coefficients and the pass that produced them."""

    asset: str
    d8: int
    train_days: list[int]
    train_cells: int
    train_rows: int
    impute: np.ndarray
    q: Ridge | None
    c: Ridge | None
    steps: int
    entered_train: int


def _impute(matrix: np.ndarray, means: np.ndarray) -> np.ndarray:
    out = np.array(matrix, np.float64, copy=True)
    bad = ~np.isfinite(out)
    if bad.any():
        out[bad] = np.take(means, np.nonzero(bad)[1])
    return out


def backward_pass(train: Sequence[Stream], width: int) -> tuple[
        Ridge | None, Ridge | None, np.ndarray, int, int]:
    """Backward fitted value iteration over the training cells' sequences.

    ``V`` holds, per cell, the realised payoff of the fitted policy from k+1
    onward: it starts at 0 (never entering scores zero) and is rewritten at each
    step by the decision this same pass just made.  The ridges at step k are
    fitted on the pass's accumulated TAIL - every training row at position >= k,
    the rows whose downstream decisions are already final - so the pair standing
    at k = 1 is fitted on the whole training set and is what the fold freezes.
    """

    rows_by_k: dict[int, list[tuple[int, np.ndarray, float]]] = {}
    stacked: list[np.ndarray] = []
    for stream in train:
        for position, occ in enumerate(stream.occs, start=1):
            rows_by_k.setdefault(position, []).append(
                (stream.cell, occ.x, occ.payoff))
            stacked.append(occ.x)
    if not stacked:
        return None, None, np.zeros(width, np.float64), 0, 0
    raw = np.vstack(stacked)
    with np.errstate(invalid="ignore"):
        means = np.nanmean(np.where(np.isfinite(raw), raw, np.nan), axis=0)
    means = np.where(np.isfinite(means), means, 0.0)

    value: dict[int, float] = {stream.cell: 0.0 for stream in train}
    sums = Sums(width=width)
    q_fit: Ridge | None = None
    c_fit: Ridge | None = None
    entered = 0
    steps = 0
    for k in sorted(rows_by_k, reverse=True):
        batch = rows_by_k[k]
        cells = [row[0] for row in batch]
        x = _impute(np.vstack([row[1] for row in batch]), means)
        y = np.asarray([row[2] for row in batch], np.float64)
        c = np.asarray([value[cell] for cell in cells], np.float64)
        sums.add(x, y, c)
        steps += 1
        if sums.n >= MIN_FIT_ROWS:
            q_fit = sums.fit("Y")
            c_fit = sums.fit("C")
            enter = q_fit.predict(x) > np.maximum(c_fit.predict(x), TAU)
        else:
            enter = np.zeros(len(batch), bool)
        for position, cell in enumerate(cells):
            if enter[position]:
                value[cell] = float(y[position])
            else:
                value[cell] = float(c[position])
        entered = int(sum(1 for cell in value if value[cell] != 0.0))
    return q_fit, c_fit, means, steps, entered


def apply_forward(stream: Stream, fold: Fold) -> Occ | None:
    """The frozen coefficients walked forward; no refit, no target, no peek."""

    if fold.q is None or fold.c is None:
        return None
    for occ in stream.occs:
        if occ.remaining_s < REMAIN_MIN_S:
            continue                    # after the floor the policy may only WAIT
        x = _impute(occ.x.reshape(1, -1), fold.impute)
        q = float(fold.q.predict(x)[0])
        c = float(fold.c.predict(x)[0])
        if q > max(c, TAU):
            return occ
    return None


@dataclass(slots=True)
class Run:
    """Every scored cell's chosen occurrence, per policy."""

    picks: dict[str, dict[int, Occ | None]] = field(default_factory=dict)
    random_picks: list[dict[int, Occ | None]] = field(default_factory=list)
    scored: list[Stream] = field(default_factory=list)
    folds: list[Fold] = field(default_factory=list)
    scoring_days: dict[str, list[int]] = field(default_factory=dict)
    unscored_days: dict[str, int] = field(default_factory=dict)
    # Sweep 9's certifiable-cell census, (asset, phase, day) -> count.  The
    # coverage and usd/day denominators are certifiable CELLS, which includes
    # the certifiable cells that produced no occurrence at all: those cells are
    # opportunities the policy declined, and dropping them would flatter every
    # coverage number by the size of that set.
    census: dict[tuple[str, str, int], int] = field(default_factory=dict)

    def denominator(self, asset: str | None, phase: str | None) -> int:
        total = 0
        for name in (ASSETS if asset is None else (asset,)):
            for day in self.scoring_days.get(name, []):
                for slot in (PHASES if phase is None else (phase,)):
                    total += int(self.census.get((name, slot, int(day)), 0))
        return total


def walk_forward(streams: Sequence[Stream], explore_days: Mapping[str, list[int]],
                 census: Mapping[tuple[str, str, int], int],
                 mutant: str = "") -> Run:
    """Fit per asset-day on strictly prior EXPLORE days, then score that day."""

    width = NFEAT
    for stream in streams:
        if stream.occs:
            width = len(stream.occs[0].x)
            break
    by_asset_day: dict[tuple[str, int], list[Stream]] = {}
    for stream in streams:
        by_asset_day.setdefault((stream.asset, stream.d8), []).append(stream)

    run = Run()
    run.census = dict(census)
    run.picks = {name: {} for name in POLICIES}
    run.random_picks = [dict() for _ in range(RANDOM_DRAWS)]
    rng = np.random.default_rng(SEED)
    for asset in ASSETS:
        days = [int(day) for day in explore_days[asset]]
        run.scoring_days[asset] = []
        run.unscored_days[asset] = 0
        for index, d8 in enumerate(sorted(days)):
            today = by_asset_day.get((asset, d8), [])
            if index < MIN_PRIOR_DAYS_FIT:
                run.unscored_days[asset] += 1
                continue
            prior = fold_days(sorted(days), index, mutant)
            train: list[Stream] = []
            for day in prior:
                train.extend(by_asset_day.get((asset, day), []))
            q, c, means, steps, entered = backward_pass(train, width)
            fold = Fold(asset=asset, d8=d8, train_days=list(prior),
                        train_cells=len(train),
                        train_rows=sum(len(s.occs) for s in train),
                        impute=means, q=q, c=c, steps=steps,
                        entered_train=entered)
            run.folds.append(fold)
            certifiable = sum(int(census.get((asset, slot, d8), 0))
                              for slot in PHASES)
            if not certifiable:
                continue
            # The day is scored on its certifiable-cell census, not on whether
            # any of those cells happened to produce an occurrence.
            run.scoring_days[asset].append(d8)
            for stream in today:
                run.scored.append(stream)
                run.picks["FITTED"][stream.cell] = apply_forward(stream, fold)
                run.picks["FIRST"][stream.cell] = (stream.occs[0]
                                                   if stream.occs else None)
                if stream.occs:
                    best = max(stream.occs, key=lambda occ: occ.payoff)
                    run.picks["ORACLE"][stream.cell] = best
                    for draw in range(RANDOM_DRAWS):
                        pick = int(rng.integers(0, len(stream.occs)))
                        run.random_picks[draw][stream.cell] = stream.occs[pick]
                else:
                    run.picks["ORACLE"][stream.cell] = None
                    for draw in range(RANDOM_DRAWS):
                        run.random_picks[draw][stream.cell] = None
    run.picks["RANDOM"] = run.random_picks[0] if run.random_picks else {}
    return run


# --------------------------------------------------------------------------
# STAGE A.
# --------------------------------------------------------------------------

def _ordinal_histogram(values: Sequence[int]) -> dict[str, object]:
    if not values:
        return {"n": 0, "median": None, "p90": None, "share_k1": None}
    array = np.asarray(values, np.float64)
    return {"n": int(len(array)), "median": float(np.median(array)),
            "p90": float(np.percentile(array, 90.0)),
            "mean": float(array.mean()),
            "share_k1": float(np.mean(array == 1.0))}


def stage_a_block(picks: Mapping[int, Occ | None], scored: Sequence[Stream],
                  asset: str | None, phase: str | None,
                  cells: int) -> dict[str, object]:
    keep = [s for s in scored
            if (asset is None or s.asset == asset)
            and (phase is None or s.phase == phase)]
    chosen = [picks.get(s.cell) for s in keep]
    taken = [occ for occ in chosen if occ is not None]
    baseline = [occ.k for s in keep for occ in s.occs]
    postx = sum(1 for occ in taken if occ.y1800 == 0)
    soft = sum(1 for occ in taken if occ.soft_hit)
    agree = [occ.side_ok for occ in taken if occ.side_ok is not None]
    delays = [occ.delay_s for occ in taken]
    depths = [occ.depth for occ in taken]
    return {
        "cells": cells, "cells_with_occurrences": len(keep),
        "entries": len(taken),
        "coverage": (float(len(taken)) / cells) if cells else None,
        "chosen_ordinal": _ordinal_histogram([occ.k for occ in taken]),
        "all_occurrence_ordinal": _ordinal_histogram(baseline),
        "occurrences_per_cell": (float(len(baseline)) / cells) if cells else None,
        "postx_1800": _rate(postx, len(taken)),
        "soft_hit": _rate(soft, len(taken)),
        "side_agreement": _rate(sum(1 for ok in agree if ok), len(agree)),
        "delay_med_s": _q(delays, 50.0), "delay_p90_s": _q(delays, 90.0),
        "depth_med": _q(depths, 50.0),
        "payoff_mean_usd": (float(np.mean([occ.payoff for occ in taken]))
                            if taken else None),
    }


def stage_a(run: Run) -> dict[str, object]:
    out: dict[str, object] = {}
    for name in POLICIES:
        block: dict[str, object] = {}
        picks = run.picks[name]
        for asset in ASSETS:
            block[asset] = {"pooled": stage_a_block(
                picks, run.scored, asset, None, run.denominator(asset, None))}
            for phase in PHASES:
                block[asset][f"phase{phase}"] = stage_a_block(
                    picks, run.scored, asset, phase,
                    run.denominator(asset, phase))
        block["ALL"] = {"pooled": stage_a_block(
            picks, run.scored, None, None, run.denominator(None, None))}
        out[name] = block
    # RANDOM is a 50-draw control: the single draw above is one path, so the
    # coverage and postX it is judged on are the means across the draws.
    spread: dict[str, object] = {}
    for asset in ASSETS:
        rates: list[float] = []
        covers: list[float] = []
        for draw in run.random_picks:
            row = stage_a_block(draw, run.scored, asset, None,
                                run.denominator(asset, None))
            if row["postx_1800"]["rate"] is not None:
                rates.append(float(row["postx_1800"]["rate"]))
            if row["coverage"] is not None:
                covers.append(float(row["coverage"]))
        spread[asset] = {
            "draws": len(run.random_picks),
            "postx_mean": float(np.mean(rates)) if rates else None,
            "postx_p05": _q(rates, 5.0), "postx_p95": _q(rates, 95.0),
            "coverage_mean": float(np.mean(covers)) if covers else None}
    out["RANDOM_DRAWS"] = spread
    return out


# --------------------------------------------------------------------------
# STAGE B: cash on the scoring days.
# --------------------------------------------------------------------------

def entries_for(picks: Mapping[int, Occ | None], records: Sequence[S1.CellRec]
                ) -> list[S1.Entry]:
    """Sweep 1's candidate-anchored entry at each chosen occurrence's stamp."""

    out: list[S1.Entry] = []
    for cell in sorted(picks):
        occ = picks[cell]
        if occ is None:
            continue
        made = S1.make_entry(occ.cell, records[occ.cell], occ.bar, occ.side)
        if made is not None:
            out.append(made)
    return out


def scoring_denominators(run: Run) -> tuple[dict[str, int], dict[str, int]]:
    """Days and cells the coverage and usd/day are measured against."""

    days = {asset: len(run.scoring_days.get(asset, [])) for asset in ASSETS}
    cells = {asset: run.denominator(asset, None) for asset in ASSETS}
    return days, cells


def stage_b(run: Run, records: Sequence[S1.CellRec]) -> dict[str, object]:
    days, cells = scoring_denominators(run)
    explore = {asset: sorted(run.scoring_days.get(asset, [])) for asset in ASSETS}
    lines: dict[str, list[S1.Entry]] = {}
    for name in PRICED:
        lines[name] = entries_for(run.picks[name], records)
    oracle = entries_for(run.picks["ORACLE"], records)

    cash = {name: S1.cash_line(lines[name], days, cells) for name in PRICED}
    cash["ORACLE"] = S1.cash_line(oracle, days, cells)
    replay = {name: S1.replay_line(lines[name], records,
                                   f"sweep14-{name.lower()}:{code_sha()[:16]}")
              for name in PRICED}
    stress = {name: {asset: S3.stress_line(lines[name], records, days, cells,
                                           asset, STRESS_RATE)
                     for asset in ASSETS} for name in PRICED}
    null_lines: dict[str, list[S1.Entry]] = {}
    for name in PRICED:
        for asset in ASSETS:
            null_lines[f"{asset}/{name}"] = [row for row in lines[name]
                                             if row.asset == asset]
    null = S1.block_null(null_lines, explore, NULL_DRAWS, SEED)
    return {"denominators": {"scoring_days": days, "scored_cells": cells},
            "entries": {name: len(lines[name]) for name in PRICED}
            | {"ORACLE": len(oracle)},
            "cash": cash, "replay": replay, "stress": stress, "null": null}


# --------------------------------------------------------------------------
# The pre-registered decision table.
# --------------------------------------------------------------------------

def _bound(name: str, ok: bool, detail: str) -> dict[str, object]:
    return {"bound": name, "ok": bool(ok), "detail": detail}


def decide(stage_a_report: Mapping[str, object],
           stage_b_report: Mapping[str, object]) -> dict[str, object]:
    cash = stage_b_report["cash"]
    stress = stage_b_report["stress"]
    null = stage_b_report["null"]
    by_asset: dict[str, object] = {}
    for asset in ASSETS:
        fitted = cash["FITTED"][asset]
        first = cash["FIRST"][asset]
        oracle = cash["ORACLE"][asset]
        null_row = null["by_line"].get(f"{asset}/FITTED")
        adjusted = float(null_row["p_max_adjusted"]) if null_row else None
        postx = stage_a_report["FITTED"][asset]["pooled"]["postx_1800"]["rate"]
        freeze: list[dict[str, object]] = [
            _bound("rung", float(fitted["usd_per_asset_day"]) >= DAY_RUNG_USD[asset],
                   f"usd/day {fitted['usd_per_asset_day']:.1f} vs rung "
                   f"{DAY_RUNG_USD[asset]:.0f} on {stage_b_report['denominators']['scoring_days'][asset]} scoring days"),
            _bound("mdd_day", float(fitted["mdd_day_usd"]) < MDD_CEILING,
                   f"{fitted['mdd_day_usd']:.0f} vs {MDD_CEILING:.0f}"),
            _bound("mdd_trade", float(fitted["mdd_trade_usd"]) < MDD_CEILING,
                   f"{fitted['mdd_trade_usd']:.0f} vs {MDD_CEILING:.0f}"),
            _bound("stress", float(stress["FITTED"][asset]["usd_per_asset_day"]) > 0.0,
                   f"{stress['FITTED'][asset]['usd_per_asset_day']:.1f} usd/day"),
            _bound("adjusted_null", adjusted is not None and adjusted <= NULL_CEILING,
                   f"p_adj {adjusted}"),
        ]
        gain = float(fitted["usd_per_asset_day"]) - float(first["usd_per_asset_day"])
        strong: list[dict[str, object]] = [
            _bound("beats_first", gain >= STRONG_GAIN_USD,
                   f"{gain:+.1f} usd/day vs FIRST"),
            _bound("wall", float(fitted["wall_rate"]) <= STRONG_WALL_CEILING,
                   f"wall rate {fitted['wall_rate']:.3f} "
                   f"({fitted['walls']} of {fitted['trades']})"),
            _bound("postx", postx is not None and float(postx) <= STRONG_POSTX_CEILING,
                   f"postX_1800 {postx}"),
        ]
        oracle_cash = float(oracle["usd_per_asset_day"])
        by_asset[asset] = {
            "deciding": asset in DECIDING,
            "usd_day_fitted": float(fitted["usd_per_asset_day"]),
            "usd_day_first": float(first["usd_per_asset_day"]),
            "usd_day_oracle": oracle_cash,
            "gain_over_first": gain,
            "oracle_capture": (float(fitted["usd_per_asset_day"]) / oracle_cash
                               if oracle_cash != 0.0 else None),
            "adjusted_null_p": adjusted,
            "freeze_bounds": freeze,
            "freeze_fired": [row["detail"] for row in freeze if not row["ok"]],
            "freeze_ok": all(row["ok"] for row in freeze),
            "strong_bounds": strong,
            "strong_fired": [row["detail"] for row in strong if not row["ok"]],
            "strong_ok": all(row["ok"] for row in strong),
        }
    freeze_hit = [a for a in DECIDING if by_asset[a]["freeze_ok"]]
    strong_hit = [a for a in DECIDING if by_asset[a]["strong_ok"]]
    if freeze_hit:
        verdict = "FREEZE-CANDIDATE"
    elif strong_hit:
        verdict = "STRONG-SIGNAL"
    else:
        verdict = "KILL"
    return {"verdict": verdict, "freeze_assets": freeze_hit,
            "strong_assets": strong_hit, "by_asset": by_asset}


# --------------------------------------------------------------------------
# The reproduction gate.
# --------------------------------------------------------------------------

def reproduce_sweep9(plane: S9.Plane) -> dict[str, object]:
    live_counters = {name: int(plane.counters[name])
                     for name in sorted(REPRO_COUNTERS)}
    live_cells = {asset: int(plane.certifiable.get(asset, 0)) for asset in ASSETS}
    return {"banked_counters": REPRO_COUNTERS, "live_counters": live_counters,
            "banked_certifiable": REPRO_CERTIFIABLE, "live_certifiable": live_cells,
            "banked_rows": REPRO_ROWS, "live_rows": int(plane.n),
            "matches": bool(live_counters == REPRO_COUNTERS
                            and live_cells == REPRO_CERTIFIABLE
                            and int(plane.n) == REPRO_ROWS)}


# --------------------------------------------------------------------------
# Printing.
# --------------------------------------------------------------------------

def _n(value: object, width: int = 8, digits: int = 3) -> str:
    if value is None:
        return "-".rjust(width)
    if isinstance(value, bool):
        return ("yes" if value else "no").rjust(width)
    if isinstance(value, (int, np.integer)):
        return str(int(value)).rjust(width)
    return f"{float(value):.{digits}f}".rjust(width)


def print_repro(block: Mapping[str, object]) -> None:
    print("\nSWEEP-9 ROW-PLANE REPRODUCTION GATE")
    print(f"  rows            banked {block['banked_rows']}  "
          f"live {block['live_rows']}")
    for asset in ASSETS:
        print(f"  certifiable {asset:<4}banked {block['banked_certifiable'][asset]:>6}"
              f"  live {block['live_certifiable'][asset]:>6}")
    for name in sorted(REPRO_COUNTERS):
        print(f"  {name:<20}banked {block['banked_counters'][name]:>7}"
              f"  live {block['live_counters'][name]:>7}")
    print(f"  matches: {block['matches']}")


def print_causal(block: Mapping[str, object]) -> None:
    print("\nCAUSALITY ASSERTIONS ON THE FEATURE PLANE")
    for name in ("feature_width", "rows_match_plane", "stream_is_chronological",
                 "remaining_floor_ok", "max_abs_corr_with_payoff",
                 "max_abs_corr_with_y1800", "no_outcome_in_features"):
        print(f"  {name:<28}{block[name]}")


def print_stage_a(report: Mapping[str, object]) -> None:
    head = ("cells", "w/occ", "entries", "cover", "ord_med", "ord_p90",
            "k1_share", "postX", "soft", "delay50", "delay90", "depth", "sideOK")
    for name in POLICIES:
        print(f"\nSTAGE A - {name}"
              + ("  (hindsight ceiling, not a policy)" if name == "ORACLE" else ""))
        print("  " + "scope".ljust(14) + "".join(h.rjust(9) for h in head))
        for asset in ASSETS:
            for scope in ("pooled",) + tuple(f"phase{p}" for p in PHASES):
                row = report[name][asset][scope]
                label = f"{asset}/{scope}"
                print("  " + label.ljust(14)
                      + _n(row["cells"], 9) + _n(row["cells_with_occurrences"], 9)
                      + _n(row["entries"], 9)
                      + _n(row["coverage"], 9) + _n(row["chosen_ordinal"]["median"], 9)
                      + _n(row["chosen_ordinal"]["p90"], 9)
                      + _n(row["chosen_ordinal"]["share_k1"], 9)
                      + _n(row["postx_1800"]["rate"], 9)
                      + _n(row["soft_hit"]["rate"], 9)
                      + _n(row["delay_med_s"], 9, 0) + _n(row["delay_p90_s"], 9, 0)
                      + _n(row["depth_med"], 9) + _n(row["side_agreement"]["rate"], 9))
    print("\nALL-OCCURRENCES ORDINAL BASELINE (the stream the policy chose from)")
    print("  " + "asset".ljust(14) + "occ/cell".rjust(10) + "ord_med".rjust(9)
          + "ord_p90".rjust(9) + "ord_mean".rjust(10))
    for asset in ASSETS:
        row = report["FITTED"][asset]["pooled"]
        base = row["all_occurrence_ordinal"]
        print("  " + asset.ljust(14) + _n(row["occurrences_per_cell"], 10, 1)
              + _n(base["median"], 9) + _n(base["p90"], 9) + _n(base["mean"], 10))
    print("\nRANDOM CONTROL, 50 SEEDED DRAWS")
    print("  " + "asset".ljust(14) + "postX_mean".rjust(11) + "p05".rjust(9)
          + "p95".rjust(9) + "cover_mean".rjust(11))
    for asset in ASSETS:
        row = report["RANDOM_DRAWS"][asset]
        print("  " + asset.ljust(14) + _n(row["postx_mean"], 11) + _n(row["postx_p05"], 9)
              + _n(row["postx_p95"], 9) + _n(row["coverage_mean"], 11))


def print_stage_b(report: Mapping[str, object]) -> None:
    den = report["denominators"]
    print("\nSTAGE B DENOMINATORS (scoring days only)")
    print("  " + "asset".ljust(8) + "scoring_days".rjust(14)
          + "scored_cells".rjust(14) + "rung_usd_day".rjust(14))
    for asset in ASSETS:
        print("  " + asset.ljust(8) + _n(den["scoring_days"][asset], 14)
              + _n(den["scored_cells"][asset], 14)
              + _n(DAY_RUNG_USD[asset], 14, 0))
    head = ("trades", "cover", "usd/day", "usd/trade", "win", "wall",
            "mdd_day", "mdd_trade")
    for name in ("FITTED", "FIRST", "ORACLE"):
        print(f"\nSTAGE B CASH - {name}"
              + ("  (ceiling, not priced as a line)" if name == "ORACLE" else ""))
        print("  " + "asset".ljust(8) + "".join(h.rjust(11) for h in head))
        for asset in ASSETS:
            row = report["cash"][name][asset]
            print("  " + asset.ljust(8) + _n(row["trades"], 11)
                  + _n(row.get("coverage"), 11) + _n(row["usd_per_asset_day"], 11, 1)
                  + _n(row.get("usd_per_trade"), 11, 1) + _n(row.get("win_rate"), 11)
                  + _n(row.get("wall_rate"), 11) + _n(row["mdd_day_usd"], 11, 0)
                  + _n(row["mdd_trade_usd"], 11, 0))
    print("\nSTAGE B REPLAY / STRESS / NULL")
    print("  " + "line".ljust(16) + "replay_skips".rjust(13)
          + "stress_usd_day".rjust(16) + "adj_null_p".rjust(12))
    for name in PRICED:
        skips = report["replay"][name].get("occupancy_or_cap_skips")
        for asset in ASSETS:
            row = report["null"]["by_line"].get(f"{asset}/{name}")
            print("  " + f"{asset}/{name}".ljust(16) + _n(skips, 13)
                  + _n(report["stress"][name][asset]["usd_per_asset_day"], 16, 1)
                  + _n(row["p_max_adjusted"] if row else None, 12))
    for name in PRICED:
        label = report["replay"][name].get("label")
        print(f"  replay label {name}: {label}")


def print_decision(block: Mapping[str, object]) -> None:
    print("\nDECISION TABLE (pre-registered)")
    print("  " + "asset".ljust(8) + "deciding".rjust(9) + "fit$/day".rjust(11)
          + "first$/day".rjust(11) + "oracle$/day".rjust(12) + "gain".rjust(10)
          + "capture".rjust(9) + "freeze".rjust(8) + "strong".rjust(8))
    for asset in ASSETS:
        row = block["by_asset"][asset]
        print("  " + asset.ljust(8) + _n(row["deciding"], 9)
              + _n(row["usd_day_fitted"], 11, 1) + _n(row["usd_day_first"], 11, 1)
              + _n(row["usd_day_oracle"], 12, 1) + _n(row["gain_over_first"], 10, 1)
              + _n(row["oracle_capture"], 9) + _n(row["freeze_ok"], 8)
              + _n(row["strong_ok"], 8))
    for asset in ASSETS:
        row = block["by_asset"][asset]
        print(f"  {asset} freeze fired: "
              + ("; ".join(row["freeze_fired"]) or "none"))
        print(f"  {asset} strong fired: "
              + ("; ".join(row["strong_fired"]) or "none"))
    print(f"  VERDICT: {block['verdict']}")


# --------------------------------------------------------------------------
# SELFTEST.
# --------------------------------------------------------------------------

def _check(name: str, ok: bool, detail: str = "") -> tuple[str, bool, str]:
    return (name, bool(ok), detail)


def _synthetic_streams(days: int = 60, cells_per_day: int = 6, k: int = 8,
                       seed: int = SEED, noise: float = 0.0,
                       mutant: str | None = None) -> list[Stream]:
    """Synthetic cells whose optimal ordinal is decided by an observed feature.

    ``depth_atr`` carries an i.i.d. draw at every occurrence and drives the
    payoff, so which occurrence pays flips cell by cell with that feature and
    the only way to score is to stop on a good draw rather than on a fixed
    ordinal.  At ``noise = 0`` the payoff IS the draw and the planted optimum is
    the exact dynamic program on the known law; ``noise > 0`` decouples the two
    so the leak checks run against a payoff no feature equals.
    """

    mutant = _mutant() if mutant is None else mutant
    rng = np.random.default_rng(seed)
    streams: list[Stream] = []
    position = 0
    for day in range(days):
        for _ in range(cells_per_day):
            stream = Stream(cell=position, asset="HG", d8=20220101 + day,
                            phase="0")
            draws = rng.random(k)
            pays = draws + (noise * rng.normal(size=k) if noise > 0.0 else 0.0)
            for index in range(k):
                base = np.zeros(NFEAT, np.float64)
                base[FEATURES.index("ord_side")] = float(index + 1)
                base[FEATURES.index("ord_cell")] = float(index + 1)
                base[FEATURES.index("depth_atr")] = float(draws[index])
                base[FEATURES.index("remain_frac")] = 1.0 - index / (2.0 * k)
                base[FEATURES.index("side")] = 1.0
                x = feature_vector(base, float(pays[index]), mutant)
                stream.occs.append(Occ(
                    row=position * k + index, cell=position, asset="HG",
                    d8=20220101 + day, phase="0", side=1, bar=index + 1,
                    k=index + 1, remaining_s=float(REMAIN_MIN_S + 600),
                    payoff=float(pays[index]), x=x, y1800=1, soft_hit=True,
                    delay_s=0.0, depth=float(draws[index]), side_ok=True,
                    legal=True))
            streams.append(stream)
            position += 1
    return streams


def _planted_optimum(k: int) -> float:
    """The dynamic program's value for the synthetic draw law, analytically.

    Uniform(0,1) draws, ``V_{K+1} = 0``: ``v_j = E[max(d, v_{j+1})]`` and
    ``E[max(d, v)] = (1 + v^2) / 2`` for v in [0, 1].
    """

    value = 0.0
    for _ in range(k):
        value = (1.0 + value * value) / 2.0
    return value


def _selftest_backward() -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []
    k = 8
    streams = _synthetic_streams(k=k)
    split = 40 * 6
    train, held = streams[:split], streams[split:]
    width = len(train[0].occs[0].x)
    q, c, means, steps, _entered = backward_pass(train, width)
    out.append(_check("synthetic/backward pass fits", q is not None and c is not None,
                      f"{steps} steps, {sum(len(s.occs) for s in train)} rows"))
    fold = Fold(asset="HG", d8=0, train_days=[], train_cells=len(train),
                train_rows=sum(len(s.occs) for s in train), impute=means,
                q=q, c=c, steps=steps, entered_train=0)
    fitted = [apply_forward(s, fold) for s in held]
    first = [s.occs[0] for s in held]
    oracle = [max(s.occs, key=lambda o: o.payoff) for s in held]
    fit_pay = float(np.mean([o.payoff if o else 0.0 for o in fitted]))
    first_pay = float(np.mean([o.payoff for o in first]))
    oracle_pay = float(np.mean([o.payoff for o in oracle]))
    planted = _planted_optimum(k)
    out.append(_check("synthetic/recovers the planted optimum",
                      fit_pay >= 0.90 * planted,
                      f"fitted {fit_pay:.3f} vs planted DP {planted:.3f} "
                      f"({fit_pay / planted:.3f} of it)"))
    out.append(_check("synthetic/beats the argfirst baseline",
                      fit_pay > first_pay + 0.05,
                      f"fitted {fit_pay:.3f} vs FIRST {first_pay:.3f}"))
    out.append(_check("synthetic/stays under the hindsight ceiling",
                      fit_pay < oracle_pay,
                      f"fitted {fit_pay:.3f} vs ORACLE {oracle_pay:.3f}"))
    chosen = np.asarray([o.k if o else k for o in fitted], np.float64)
    best = np.asarray([o.k for o in oracle], np.float64)
    corr = float(np.corrcoef(chosen, best)[0, 1])
    out.append(_check("synthetic/chosen ordinal tracks the planted one",
                      corr > 0.30, f"corr(chosen, oracle ordinal) {corr:.3f}"))
    entered = sum(1 for o in fitted if o is not None)
    out.append(_check("synthetic/does not enter every cell at k=1",
                      float(np.mean(chosen == 1.0)) < 0.90,
                      f"share at k=1 {float(np.mean(chosen == 1.0)):.3f}, "
                      f"{entered}/{len(held)} entered"))
    return out


def _selftest_reset_law() -> list[tuple[str, bool, str]]:
    got = side_ordinals([2, 4, 6, 9, 11, 14], [7, 13])
    want = [1, 2, 3, 1, 2, 1]
    out = [_check("reset law/same-side new extreme restarts the ordinal",
                  got == want, f"{got} vs {want}")]
    flat = side_ordinals([2, 4, 6], [])
    out.append(_check("reset law/no extreme means a plain count",
                      flat == [1, 2, 3], str(flat)))
    out.append(_check("reset law/plane carries it as inzone_ordinal",
                      "inzone_ordinal" in S9.FIELD_INDEX,
                      f"index {S9.FIELD_INDEX.get('inzone_ordinal')}"))
    return out


def _selftest_floor() -> list[tuple[str, bool, str]]:
    streams = _synthetic_streams(days=40, cells_per_day=6, k=8)
    train = streams[:180]
    q, c, means, steps, _e = backward_pass(train, len(train[0].occs[0].x))
    fold = Fold(asset="HG", d8=0, train_days=[], train_cells=len(train),
                train_rows=0, impute=means, q=q, c=c, steps=steps,
                entered_train=0)
    cell = streams[-1]
    live = apply_forward(cell, fold)
    for occ in cell.occs:
        occ.remaining_s = float(REMAIN_MIN_S - 60)
    dead = apply_forward(cell, fold)
    return [
        _check("floor/an eligible cell can enter", live is not None,
               f"entered at k={live.k}" if live else "no entry"),
        _check("floor/no ENTER below 1800 s remaining", dead is None,
               "policy waited through every past-floor occurrence"),
    ]


def _selftest_ridge() -> list[tuple[str, bool, str]]:
    rng = np.random.default_rng(7)
    x = rng.normal(size=(400, 3))
    y = 2.0 + 3.0 * x[:, 0] - 1.5 * x[:, 1]
    sums = Sums(width=3)
    sums.add(x, y, y)
    fit = sums.fit("Y")
    pred = fit.predict(x)
    err = float(np.max(np.abs(pred - y)))
    beta_x0 = float(fit.beta[0] / fit.sd[0])
    return [
        _check("ridge/recovers a linear target", err < 0.15, f"max abs err {err:.4f}"),
        _check("ridge/intercept is the unpenalised mean",
               abs(fit.intercept - float(y.mean())) < 1e-9,
               f"{fit.intercept:.6f} vs {float(y.mean()):.6f}"),
        _check("ridge/shrinks toward the truth, never past it",
               0.0 < beta_x0 <= 3.0, f"slope on x0 {beta_x0:.3f} vs 3.0"),
    ]


def _selftest_mutants() -> list[tuple[str, bool, str]]:
    """The two causality laws, asserted through the shipped code paths.

    Each check states what must hold when NO mutant is set, and both mutants
    reach these assertions through ``fold_days`` and ``feature_vector`` - the
    same functions ``walk_forward`` and ``build_streams`` call - so setting
    either env var turns the selftest red rather than exercising a stub.
    """

    mutant = _mutant()
    out: list[tuple[str, bool, str]] = []
    # 1. The fold may only ever see days strictly before the one it scores.
    days = list(range(20220101, 20220101 + 40))
    index = 30
    prior = fold_days(days, index, mutant)
    out.append(_check("law/fold trains on strictly prior days only",
                      bool(prior) and max(prior) < days[index],
                      f"fold max day {max(prior)} vs scoring day {days[index]} "
                      f"({len(prior)} training days)"))
    # 2. No feature may be the outcome the policy is choosing over.
    streams = _synthetic_streams(days=12, cells_per_day=4, k=6, noise=0.25,
                                 mutant=mutant)
    block = assert_causal(streams)
    out.append(_check("law/no feature is the occurrence payoff",
                      bool(block["no_outcome_in_features"]),
                      f"max |corr| {block['max_abs_corr_with_payoff']:.4f} "
                      f"over {block['feature_width']} columns"))
    out.append(_check("law/the feature vector stays the frozen width",
                      block["feature_width"] == [NFEAT],
                      f"{block['feature_width']} vs the frozen [{NFEAT}]"))
    return out


def selftest() -> int:
    mutant = _mutant()
    print(f"sweep 14 selftest  spec_sha {SPEC_SHA[:16]}  "
          f"code_sha {code_sha()[:16]}  mutant {mutant or 'none'}")
    rows: list[tuple[str, bool, str]] = []
    rows += _selftest_ridge()
    rows += _selftest_reset_law()
    rows += _selftest_floor()
    rows += _selftest_backward()
    rows += _selftest_mutants()
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

def _show(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def log_rows(report: Mapping[str, object]) -> list[dict[str, object]]:
    stage_a_report = report["stage_a"]
    price = report["stage_b"]
    ruling = report["decision"]
    den = price["denominators"]
    params = json.dumps({
        "lambda": RIDGE_LAMBDA, "tau": TAU, "features": NFEAT,
        "min_prior_days": MIN_PRIOR_DAYS_FIT, "min_fit_rows": MIN_FIT_ROWS,
        "random_draws": RANDOM_DRAWS, "null_draws": NULL_DRAWS,
        "remain_min_s": REMAIN_MIN_S})
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
    for name in POLICIES:
        counter += 1
        block = stage_a_report[name]
        rows.append({
            **shared, "id": f"sweep14-{counter:03d}",
            "rule": f"STAGE-A/{name}",
            "days": sum(den["scoring_days"][asset] for asset in ASSETS),
            "coverage": block["ALL"]["pooled"]["coverage"],
            "delay_med_s": block["ALL"]["pooled"]["delay_med_s"],
            "err_rate_hg": block["HG"]["pooled"]["postx_1800"]["rate"],
            "err_rate_nkd": block["NKD"]["pooled"]["postx_1800"]["rate"],
            "err_rate_si": block["SI"]["pooled"]["postx_1800"]["rate"],
            "note": (f"scoring-day cells {den['scored_cells']}; chosen ordinal "
                     f"median {_show(block['ALL']['pooled']['chosen_ordinal']['median'])}"
                     f" of {_show(block['ALL']['pooled']['occurrences_per_cell'])} "
                     f"per cell")[:400],
        })
    for name in PRICED:
        for asset in ASSETS:
            counter += 1
            line = price["cash"][name][asset]
            null_row = price["null"]["by_line"].get(f"{asset}/{name}")
            rows.append({
                **shared, "id": f"sweep14-{counter:03d}",
                "rule": f"PRICED/{name}/{asset}",
                "days": den["scoring_days"][asset],
                "coverage": line.get("coverage"),
                "walls_hg": line.get("walls") if asset == "HG" else None,
                "walls_nkd": line.get("walls") if asset == "NKD" else None,
                "walls_si": line.get("walls") if asset == "SI" else None,
                "hg_usd_day": line["usd_per_asset_day"] if asset == "HG" else None,
                "nkd_usd_day": line["usd_per_asset_day"] if asset == "NKD" else None,
                "si_usd_day": line["usd_per_asset_day"] if asset == "SI" else None,
                "mdd_hg": line["mdd_day_usd"] if asset == "HG" else None,
                "mdd_nkd": line["mdd_day_usd"] if asset == "NKD" else None,
                "mdd_si": line["mdd_day_usd"] if asset == "SI" else None,
                "replay_skips": price["replay"][name].get("occupancy_or_cap_skips"),
                "null_margin": (null_row["p_max_adjusted"] if null_row else None),
                "note": (f"scoring-day denominator {den['scoring_days'][asset]} days"
                         f"/{den['scored_cells'][asset]} cells; stress "
                         f"{_show(price['stress'][name][asset]['usd_per_asset_day'])}"
                         f" usd/day")[:400],
            })
    for asset in ASSETS:
        counter += 1
        row = ruling["by_asset"][asset]
        rows.append({
            **shared, "id": f"sweep14-{counter:03d}",
            "rule": f"RULING/{asset}",
            "days": den["scoring_days"][asset],
            "coverage": stage_a_report["FITTED"][asset]["pooled"]["coverage"],
            "err_rate_hg": (stage_a_report["FITTED"]["HG"]["pooled"]["postx_1800"]["rate"]
                            if asset == "HG" else None),
            "err_rate_nkd": (stage_a_report["FITTED"]["NKD"]["pooled"]["postx_1800"]["rate"]
                             if asset == "NKD" else None),
            "err_rate_si": (stage_a_report["FITTED"]["SI"]["pooled"]["postx_1800"]["rate"]
                            if asset == "SI" else None),
            "null_margin": row["adjusted_null_p"],
            "note": (f"{ruling['verdict']}; oracle capture "
                     f"{_show(row['oracle_capture'])}; gain over FIRST "
                     f"{_show(row['gain_over_first'])} usd/day; freeze fired: "
                     + ("; ".join(row["freeze_fired"]) or "none"))[:400],
        })
    return rows


def write_report(report: Mapping[str, object]) -> None:
    OUT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True,
                                   default=S8._json_default) + "\n")


# --------------------------------------------------------------------------
# Entry point.
# --------------------------------------------------------------------------

def run(assets: Sequence[str] = ASSETS) -> dict[str, object]:
    mutant = _mutant()
    started = time.time()
    # Entry.cell indexes the FILTERED record list, so the asset set is never
    # subsetted here: doing so would silently misalign every cash number.
    cells, days, _skipped = S8.build_cells(ASSETS)
    records, _days = S1.load_cache()
    records = [rec for rec in records if rec.asset in ASSETS]
    explore_days = S1._explore_days(ASSETS)
    tape = S9.load_tape(cells)
    forecast = S9.forecast_variance(cells)
    plane = S9.build_plane(cells, forecast, tape)
    repro = reproduce_sweep9(plane)
    if not repro["matches"]:
        raise SweepRefusal("sweep 9's row plane did not reproduce; no "
                           "measurement is believed past this point")
    states = S12.day_states({asset: explore_days[asset] for asset in ASSETS})
    streams, counters = build_streams(plane, cells, states, mutant)
    causal = assert_causal(streams, plane)
    if not causal["no_outcome_in_features"] and mutant != MUTANT_LABEL:
        raise SweepRefusal("a feature reads the outcome it is choosing over")
    if not (causal["remaining_floor_ok"] and causal["stream_is_chronological"]
            and causal["rows_match_plane"]):
        raise SweepRefusal("the occurrence stream failed a causality assertion")
    walk = walk_forward(streams, explore_days, plane.stratum_day_cells, mutant)
    a_report = stage_a(walk)
    b_report = stage_b(walk, records)
    ruling = decide(a_report, b_report)
    return {
        "schema": "QRE2MILLSWEEP14", "spec_sha": SPEC_SHA, "code_sha": code_sha(),
        "split_sha": S1.split_sha(), "outcome_law_sha": S1.outcome_law_sha(),
        "seed": SEED, "mutant": mutant, "family": FAMILY,
        "parent_trial": PARENT_TRIAL, "selection_rule": SELECTION_RULE,
        "registered_utc": report_stamp(),
        "asset_days": {asset: int(days.get(asset, 0)) for asset in ASSETS},
        "sweep9_reproduction": repro, "stream_counters": counters,
        "causality": causal,
        "folds": [{"asset": f.asset, "d8": f.d8, "train_days": len(f.train_days),
                   "train_cells": f.train_cells, "train_rows": f.train_rows,
                   "steps": f.steps, "fitted": f.q is not None}
                  for f in walk.folds],
        "scoring_days": {a: walk.scoring_days.get(a, []) for a in ASSETS},
        "unscored_days": walk.unscored_days,
        "stage_a": a_report, "stage_b": b_report, "decision": ruling,
        "elapsed_s": round(time.time() - started, 1),
    }


def report_stamp() -> str:
    import datetime as dt
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--log", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    report = run()
    print(f"sweep 14 spec_sha {SPEC_SHA[:16]} code_sha {code_sha()[:16]} "
          f"seed {SEED} mutant {report['mutant'] or 'none'}")
    print_repro(report["sweep9_reproduction"])
    print_causal(report["causality"])
    print(f"\nstreams {report['stream_counters']['streams']} cells, "
          f"{report['stream_counters']['occs']} occurrences; folds "
          f"{len(report['folds'])}; unscored days {report['unscored_days']}")
    print_stage_a(report["stage_a"])
    print_stage_b(report["stage_b"])
    print_decision(report["decision"])
    write_report(report)
    print(f"\nwrote {OUT_PATH} in {report['elapsed_s']} s")
    if args.log:
        written = S1.append_log(log_rows(report))
        print(f"appended {written} hypothesis-log rows to {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
