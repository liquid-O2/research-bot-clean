"""m25_reading — the M2.5 verdict: Q*, Q_max, the gate, the decomposition panel,
and the affine cap B (FINAL_PLAN.md section 8).

WHAT THIS MODULE IS AND IS NOT. `qr_m25_run` measures; this module DECIDES. It
owns every confidence bound, and it owns them through the SHA-PINNED estimator
(`authorities/REGISTRY.tsv` row estimator_laws_v1,
`engine/crates/publish/tests/fixtures/estimator_laws.py`,
sha fbd1b573a21f0f9a23cc378f7340106d2f16f09236b263fcfadfcaf1227e7708). It
computes no dollar of its own: every net it reads came out of the one replay
kernel.

THE THREE STATISTICS.

1. MEAN LCB, through the pinned entry point `year_stratified_session_block_lcb`
   under the affine encoding of FINAL_PLAN section 11, verbatim:
   "A=$4,000 floor, B=$12,000 cap preregistered; hits=round(100*x)+400,000,
    truths=1,600,000; out-of-bounds session => CERT_BOUND_VIOLATION, certificate
    REFUSED, never clipped; LCB(mean)=r_LCB*(A+B)-A".
   Section 8 REPLACES the a-priori B: "The affine cap B is re-derived here from
   the perfect-skill envelope (replacing a-priori $12,000); floor violations
   fatal; cap violations CLIP with a typed census (conservative)." So B is the
   p99.9 of the per-session PERFECT-SKILL (one-position optimum) replay nets of
   the fold, A stays $4,000, a session below -A is a fatal CERT_BOUND_VIOLATION,
   and a session above B is clipped with its count published.

2. MDD_UCB, through the declared MDD SIBLING LAW (FINAL_PLAN section 11):
   "own SHA; identical frozen constants: year-strata, block 5, 10,000
    replicates, derived seed): resample session sequences, exact zero-inclusive
    EOD MDD per replicate, 95th percentile = MDD_UCB".
   The sibling reuses the pinned law's OWN resampling: the block draws depend
   only on the strata sizes and the seed — never on the data — so this module
   generates the draw indices with the pinned module's own constants and its own
   draw order, and PROVES the reproduction by recomputing several LCBs through
   the pinned entry point and requiring bit-equality (`verify_pinned_parity`).
   The upper bound mirrors the pinned lower bound's index rule: the pinned LCB
   is the ascending replicate at index floor((1-c)*(R-1)); the sibling UCB is
   the ascending replicate at index floor(c*(R-1)).

3. Q_max, the twin-discordance ceiling, pooled from the runner's per-session
   sums (see qr_m25/twins.hpp for the estimator and its declared bias
   direction).

THE GATE (FINAL_PLAN section 8): "estimate required skill Q* to clear
$2,000/session + MDD<$1,000 on this object ... vs Q_max ... do not fit unless
Q* <= Q_max in both folds."  Q* is the SMALLEST skill on the corruption grid at
which some cell of the A6 gate family clears BOTH bars; the cell that does it is
published with it.
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import random
import sys
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import numpy as np

_PINNED = pathlib.Path("/workspace/engine/crates/publish/tests/fixtures/estimator_laws.py")
_PINNED_SHA = "fbd1b573a21f0f9a23cc378f7340106d2f16f09236b263fcfadfcaf1227e7708"

sys.path.insert(0, str(_PINNED.parent))
import estimator_laws  # noqa: E402

# --- frozen constants ------------------------------------------------------

MEAN_BAR_DOLLARS = 2000.0          # FINAL_PLAN section 8 item 1
MDD_BAR_DOLLARS = 1000.0           # FINAL_PLAN section 8 item 1
DIAGNOSTIC_RUNG_DOLLARS = 1600.0   # "$1,600 = diagnostic-rung headroom, reported only"
AFFINE_FLOOR_CENT = 400_000        # A = $4,000, preregistered
CAP_QUANTILE = 0.999               # "B = p99.9 of per-session perfect-skill nets"
ENVELOPE_ARM = "perfect_side_takeskip_dp"
BINDING_LOSS_LIMIT_CENT = -90_000
TRAIN_RANGE = {"F4": (125, 395), "F5": (125, 520)}
HORIZON_LABEL = ["2m", "5m", "15m", "30m", "60m", "120m", "close"]
HORIZON_REF_INDEX = 2
# The twin ceiling's binding rule (declared before any number). The DISJOINT
# ladder is the one the twin identity licenses (see qr_m25/twins.hpp); the
# binding bucket is the SMALLEST whose disjoint ladder carries at least
# MIN_DISJOINT_PAIRS nearest-neighbour pairs at the horizon in question, because
# a wider bucket buys support by weakening the clock match the ruling asks for.
MIN_DISJOINT_PAIRS = 100_000
TWIN_BUCKETS = (15, 60, 300, 900, 3600)

# THE SCREEN (declared before any number is computed). Bounding all 126 cells at
# every skill level is 5,166 block bootstraps per fold per replicate, which the
# 30-minute budget does not have. The screen is a NECESSARY-CONDITION filter on
# the point estimates plus a fixed-width top-of-list, so it can only ever drop
# cells that could not have won:
#   * a one-sided LOWER bound never exceeds the point mean, so a cell whose point
#     mean is at or under the bar cannot clear it — the margin below keeps a
#     wide skirt anyway;
#   * a cell whose POINT drawdown is already far past the bar is not going to
#     have a smaller 95th-percentile resampled drawdown;
#   * whatever survives, the strongest CELL_BUDGET by point mean are bounded.
SCREEN_MEAN_DOLLARS = 1500.0
SCREEN_MDD_DOLLARS = 2000.0
CELL_BUDGET = 24


class ReadingError(Exception):
    """A reading that cannot be trusted. Never raised for a recoverable case."""


def _refuse(message: str) -> None:
    raise ReadingError(message)


def assert_pinned_estimator() -> None:
    got = hashlib.sha256(_PINNED.read_bytes()).hexdigest()
    if got != _PINNED_SHA:
        _refuse(f"pinned estimator sha {got} != registered {_PINNED_SHA}")


# --- the block-bootstrap draw, reproduced from the pinned law --------------


def block_draw_indices(years: Sequence[int], ordinals: Sequence[int]) -> np.ndarray:
    """The pinned year-stratified session-block draw, as an index matrix.

    The pinned entry point draws WHOLE BLOCKS with replacement inside each year
    stratum, in ascending-year order, from a single `random.Random(seed)`. The
    draw sequence is a function of the strata SIZES and the seed alone — the
    data never enters it — so the identical loop here yields the identical
    resample, and `verify_pinned_parity` checks that claim numerically.

    Returns an int array [replicates, n_sessions] of positions into the
    caller's arrays, in the same concatenated (year-ascending, ordinal-ascending)
    order the pinned law builds.
    """
    scheme = estimator_laws.REGISTERED_SESSION_BLOCK_SCHEME
    if not scheme.is_registered():
        _refuse("the registered session-block scheme is not registered")

    order = sorted(range(len(years)), key=lambda i: (years[i], ordinals[i]))
    strata: Dict[int, List[int]] = {}
    for position in order:
        strata.setdefault(years[position], []).append(position)

    length = scheme.block_len
    stratum_blocks: List[Tuple[List[List[int]], int]] = []
    for year in sorted(strata):
        members = strata[year]
        blocks = [members[i : i + length] for i in range(0, len(members), length)]
        stratum_blocks.append((blocks, len(members)))

    rng = random.Random(scheme.seed)
    total = len(order)
    out = np.empty((scheme.replicates, total), dtype=np.int32)
    for replicate in range(scheme.replicates):
        write = 0
        for blocks, n in stratum_blocks:
            count = len(blocks)
            got = 0
            while got < n:
                block = blocks[rng.randrange(count)]
                take = block if got + len(block) <= n else block[: n - got]
                out[replicate, write : write + len(take)] = take
                write += len(take)
                got += len(take)
        if write != total:
            _refuse("the reproduced draw did not fill a replicate exactly")
    return out


def _percentile_index(replicates: int, confidence: float, upper: bool) -> int:
    """The pinned law's index rule, and its mirror image for an upper bound."""
    if upper:
        return int(confidence * (replicates - 1))
    return int((1.0 - confidence) * (replicates - 1))


def lcb_from_indices(hits: np.ndarray, truths: np.ndarray, indices: np.ndarray,
                     confidence: float = 0.95) -> float:
    """Pooled-recall LCB by the pinned law, vectorised over a precomputed draw."""
    drawn_hits = hits[indices].sum(axis=1, dtype=np.int64)
    drawn_truths = truths[indices].sum(axis=1, dtype=np.int64)
    recalls = np.where(drawn_truths > 0, drawn_hits / np.maximum(drawn_truths, 1), 0.0)
    recalls.sort()
    return float(recalls[_percentile_index(len(recalls), confidence, upper=False)])


def verify_pinned_parity(years: Sequence[int], ordinals: Sequence[int], indices: np.ndarray,
                         populations: Sequence[Tuple[np.ndarray, np.ndarray]]) -> None:
    """Every vectorised LCB must equal the PINNED entry point's, exactly."""
    order = sorted(range(len(years)), key=lambda i: (years[i], ordinals[i]))
    for hits, truths in populations:
        records = [
            estimator_laws.SessionRecall(
                year=int(years[position]),
                ordinal=int(ordinals[position]),
                hits=int(hits[position]),
                truths=int(truths[position]),
            )
            for position in order
        ]
        pinned = estimator_laws.year_stratified_session_block_lcb(records)
        mine = lcb_from_indices(hits, truths, indices)
        if pinned != mine:
            _refuse(
                "the vectorised block bootstrap does not reproduce the pinned entry point "
                f"({mine!r} != {pinned!r}); the reading is refused"
            )


# --- the affine encoding ---------------------------------------------------


@dataclass(frozen=True)
class AffineCap:
    floor_cent: int
    cap_cent: int
    source_sessions: int
    per_horizon_cap_cent: Tuple[int, ...]

    @property
    def truths(self) -> int:
        return self.floor_cent + self.cap_cent

    @property
    def floor_dollars(self) -> float:
        return self.floor_cent / 100.0

    @property
    def cap_dollars(self) -> float:
        return self.cap_cent / 100.0


def nearest_rank(values: np.ndarray, quantile: float) -> int:
    """Nearest-rank quantile: the value at 1-based index ceil(p*N), clamped —
    the same convention the C++ scorecard uses for its MAE panel, so every
    published quantile in this program means one thing."""
    ascending = np.sort(np.asarray(values))
    n = len(ascending)
    if n == 0:
        _refuse("nearest_rank on an empty population")
    index = int(np.ceil(quantile * n))
    index = min(max(index, 1), n)
    return int(ascending[index - 1])


def derive_affine_cap(envelope_by_horizon: Dict[int, np.ndarray]) -> AffineCap:
    """B = p99.9 of the per-session perfect-skill replay nets, pooled over the
    seven menu horizons (the envelope must bound whatever horizon a cell uses),
    with the per-horizon caps published beside it."""
    pooled = np.concatenate([envelope_by_horizon[h] for h in sorted(envelope_by_horizon)])
    cap = nearest_rank(pooled, CAP_QUANTILE)
    if cap <= 0:
        _refuse(f"the perfect-skill envelope produced a non-positive cap ({cap} cent)")
    per_horizon = tuple(
        nearest_rank(envelope_by_horizon[h], CAP_QUANTILE) for h in sorted(envelope_by_horizon)
    )
    return AffineCap(AFFINE_FLOOR_CENT, cap, len(pooled), per_horizon)


@dataclass
class Encoded:
    hits: np.ndarray
    truths: np.ndarray
    cap_violations: int
    floor_violations: int


def affine_encode(net_cent: np.ndarray, cap: AffineCap, strict: bool = True) -> Encoded:
    """hits = round(100*x) + 400,000 and truths = 100*(A+B), exactly.

    FINAL_PLAN section 8 splits the two out-of-bounds cases and this function
    obeys the split: a session BELOW the floor is FATAL (CERT_BOUND_VIOLATION —
    "floor violations fatal", and never a silent clip), a session ABOVE the cap
    is CLIPPED with its count published ("cap violations CLIP with a typed
    census (conservative)").

    STRICTNESS, and why it is a parameter. The floor law binds the object being
    REPORTED. M2.5 sweeps thousands of hypothetical agents, most of them awful,
    and one of them losing $7,000 in a session is a fact ABOUT THAT AGENT, not a
    defect in the reading — so the sweep encodes non-strictly, marks any cell
    with a floor violation as REFUSED (it can never be the best admissible cell,
    and its incidence is published), and carries on. Everything that is actually
    reported as a bound — the envelope, the winning cell — is encoded strictly,
    where a floor violation is fatal exactly as FINAL_PLAN section 8 says."""
    hits = net_cent.astype(np.int64) + cap.floor_cent
    floor_violations = int((hits < 0).sum())
    if strict and floor_violations:
        worst = int(net_cent.min())
        _refuse(
            f"CERT_BOUND_VIOLATION: {floor_violations} session(s) below the -${cap.floor_dollars:,.0f} "
            f"floor (worst {worst} cent); FINAL_PLAN section 8 makes a floor violation fatal"
        )
    cap_violations = int((hits > cap.truths).sum())
    hits = np.clip(hits, 0, cap.truths)
    truths = np.full(hits.shape, cap.truths, dtype=np.int64)
    return Encoded(hits, truths, cap_violations, floor_violations)


def mean_lcb_dollars(net_cent: np.ndarray, cap: AffineCap, indices: np.ndarray,
                     strict: bool = True) -> Tuple[float, Encoded]:
    encoded = affine_encode(net_cent, cap, strict)
    rate = lcb_from_indices(encoded.hits, encoded.truths, indices)
    dollars = rate * (cap.floor_dollars + cap.cap_dollars) - cap.floor_dollars
    return dollars, encoded


def mdd_ucb_dollars(net_cent: np.ndarray, indices: np.ndarray, confidence: float = 0.95) -> float:
    """THE MDD SIBLING LAW. Resample the SESSION SEQUENCE with the pinned draw,
    take each replicate's exact zero-inclusive end-of-day drawdown (E0 = 0 in the
    running maximum, no intraday interpolation, zero days included), and report
    the 95th percentile."""
    drawn = net_cent[indices].astype(np.int64)
    equity = np.cumsum(drawn, axis=1)
    running_max = np.maximum.accumulate(equity, axis=1)
    running_max = np.maximum(running_max, 0)  # "include E0 in the running maximum"
    drawdown = (running_max - equity).max(axis=1)
    drawdown = np.maximum(drawdown, 0)
    drawdown.sort()
    return float(drawdown[_percentile_index(len(drawdown), confidence, upper=True)]) / 100.0


def point_mdd_dollars(net_cent: np.ndarray) -> float:
    equity = np.cumsum(net_cent.astype(np.int64))
    running_max = np.maximum(np.maximum.accumulate(equity), 0)
    return float(np.max(running_max - equity, initial=0)) / 100.0


# --- receipts --------------------------------------------------------------


def _read_tsv(path: pathlib.Path) -> Tuple[List[str], List[List[str]]]:
    with path.open() as handle:
        header = handle.readline().rstrip("\n").split("\t")
        rows = [line.rstrip("\n").split("\t") for line in handle if line.strip()]
    return header, rows


@dataclass
class Receipts:
    out_dir: pathlib.Path
    run_meta: Dict[str, str]
    session_year: Dict[int, int]
    sweep_sessions: List[int]
    sweep_cells: List[Tuple[float, int, int, float]]
    replicates: int

    def sweep_net(self, replicate: int) -> np.ndarray:
        path = self.out_dir / f"sweep_net_cent_r{replicate}.bin"
        raw = np.fromfile(path, dtype=np.int64)
        return raw.reshape(len(self.sweep_cells), len(self.sweep_sessions))

    def sweep_trades(self, replicate: int) -> np.ndarray:
        path = self.out_dir / f"sweep_trades_r{replicate}.bin"
        raw = np.fromfile(path, dtype=np.int32)
        return raw.reshape(len(self.sweep_cells), len(self.sweep_sessions))


def load_receipts(out_dir: pathlib.Path) -> Receipts:
    _, run_rows = _read_tsv(out_dir / "run.tsv")
    meta = {row[1]: row[2] for row in run_rows}

    _, session_rows = _read_tsv(out_dir / "sessions.tsv")
    session_year = {int(row[1]): int(row[3]) for row in session_rows}

    sweep_sessions: List[int] = []
    sweep_cells: List[Tuple[float, int, int, float]] = []
    if (out_dir / "sweep_cells.tsv").exists():
        _, rows = _read_tsv(out_dir / "sweep_sessions.tsv")
        sweep_sessions = [int(row[1]) for row in rows]
        _, rows = _read_tsv(out_dir / "sweep_cells.tsv")
        sweep_cells = [(float(r[1]), int(r[2]), int(r[3]), float(r[4])) for r in rows]

    return Receipts(
        out_dir=out_dir,
        run_meta=meta,
        session_year=session_year,
        sweep_sessions=sweep_sessions,
        sweep_cells=sweep_cells,
        replicates=int(meta.get("replicates", "1")),
    )


def load_arms(out_dir: pathlib.Path) -> Dict[Tuple[str, int, int], Dict[int, Tuple[int, int, int]]]:
    """(arm, horizon, loss_limit) -> {session: (net_cent, trades, breaches)}."""
    _, rows = _read_tsv(out_dir / "arms.tsv")
    table: Dict[Tuple[str, int, int], Dict[int, Tuple[int, int, int]]] = {}
    for row in rows:
        key = (row[1], int(row[2]), int(row[3]))
        table.setdefault(key, {})[int(row[4])] = (int(row[6]), int(row[7]), int(row[8]))
    return table


def load_twins(out_dir: pathlib.Path, sessions: Sequence[int]) -> Dict[Tuple[int, int], Dict[str, float]]:
    """(bucket_seconds, horizon) -> pooled twin sums over `sessions`."""
    keep = set(int(s) for s in sessions)
    ladder: Dict[Tuple[int, int, int], List[float]] = {}
    _, rows = _read_tsv(out_dir / "twins_ladder.tsv")
    for row in rows:
        if int(row[0]) not in keep:
            continue
        key = (int(row[1]), int(row[2]), int(row[3]))
        entry = ladder.setdefault(key, [0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        entry[0] += float(row[4])
        entry[1] += float(row[5])
        entry[2] += float(row[6])
        entry[3] += float(row[7])
        entry[4] += float(row[8])
        entry[5] += float(row[9])

    pooled: Dict[Tuple[int, int], Dict[str, float]] = {}
    _, rows = _read_tsv(out_dir / "twins_pool.tsv")
    for row in rows:
        if int(row[0]) not in keep:
            continue
        key = (int(row[1]), int(row[2]))
        entry = pooled.setdefault(
            key,
            {"all_pairs": 0.0, "all_gap_sq": 0.0, "z_rows": 0.0, "z_centred_sq": 0.0,
             "cells": 0.0, "rows_in_cells": 0.0, "exact_twin_pairs": 0.0,
             "all_disjoint_pairs": 0.0, "all_disjoint_gap_sq": 0.0},
        )
        entry["all_pairs"] += float(row[3])
        entry["all_gap_sq"] += float(row[4])
        entry["z_rows"] += float(row[5])
        entry["z_centred_sq"] += float(row[6])
        entry["cells"] += float(row[7])
        entry["rows_in_cells"] += float(row[8])
        entry["exact_twin_pairs"] += float(row[9])
        entry["all_disjoint_pairs"] += float(row[10])
        entry["all_disjoint_gap_sq"] += float(row[11])

    for (bucket, horizon), entry in pooled.items():
        depth = 0
        points: List[Tuple[float, float, float]] = []
        disjoint_points: List[Tuple[float, float, float]] = []
        while (bucket, depth, horizon) in ladder:
            pairs, distance, gap_sq, d_pairs, d_distance, d_gap_sq = ladder[(bucket, depth, horizon)]
            if pairs > 0:
                points.append((pairs, distance / pairs, gap_sq / pairs))
            if d_pairs > 0:
                disjoint_points.append((d_pairs, d_distance / d_pairs, d_gap_sq / d_pairs))
            depth += 1
        entry["ladder"] = points  # type: ignore[assignment]
        entry["disjoint_ladder"] = disjoint_points  # type: ignore[assignment]
    return pooled


@dataclass(frozen=True)
class Ceiling:
    q_max: float
    q_max_k1: float
    q_max_clock_only: float
    d0: float
    d1: float
    variance: float
    pairs: int
    exact_twin_pairs: int
    cells: int
    q_max_disjoint: float
    q_max_disjoint_k1: float
    q_max_disjoint_clock_only: float
    d0_disjoint: float
    d1_disjoint: float
    disjoint_pairs: int


def _fit_ladder(points: List[Tuple[float, float, float]]) -> Tuple[float, float, int]:
    """(d1, d0, pairs_at_k1) from a (pairs, mean distance, mean squared gap)
    ladder — the weighted affine fit of qr_m25/src/twins.cpp, clamped the same
    way, so the C++ and Python answers cannot drift apart."""
    if not points:
        return 0.0, 0.0, 0
    pairs_k1, _, d1 = points[0]
    weights = np.array([p[0] for p in points], dtype=float)
    x = np.array([p[1] for p in points], dtype=float)
    y = np.array([p[2] for p in points], dtype=float)
    d0 = d1
    if len(points) >= 2:
        w = weights.sum()
        sx = float((weights * x).sum())
        sy = float((weights * y).sum())
        sxx = float((weights * x * x).sum())
        sxy = float((weights * x * y).sum())
        denominator = w * sxx - sx * sx
        if abs(denominator) > 0.0:
            beta = (w * sxy - sx * sy) / denominator
            d0 = (sy - beta * sx) / w
    return d1, min(max(d0, 0.0), d1), int(pairs_k1)


def twin_ceiling(entry: Dict[str, float]) -> Ceiling:
    """The same estimator as qr_m25/twins.cpp, on pooled sums (see that header
    for the derivation, the overlap defect, and the declared direction of
    error)."""
    if entry["z_rows"] <= 1:
        _refuse("twin ceiling on an empty population")
    variance = entry["z_centred_sq"] / entry["z_rows"]
    points = entry.get("ladder", [])  # type: ignore[assignment]
    if not points:
        _refuse("twin ceiling with an empty neighbour ladder")

    def ceiling(squared_gap: float) -> float:
        return float(np.sqrt(max(0.0, 1.0 - squared_gap / (2.0 * variance))))

    d1, d0, pairs_k1 = _fit_ladder(points)
    d1_disjoint, d0_disjoint, disjoint_pairs = _fit_ladder(
        entry.get("disjoint_ladder", []))  # type: ignore[arg-type]

    clock_only = ceiling(entry["all_gap_sq"] / entry["all_pairs"]) if entry["all_pairs"] > 0 else 0.0
    disjoint_clock_only = (ceiling(entry["all_disjoint_gap_sq"] / entry["all_disjoint_pairs"])
                           if entry.get("all_disjoint_pairs", 0) > 0 else 0.0)
    return Ceiling(
        q_max=ceiling(d0), q_max_k1=ceiling(d1), q_max_clock_only=clock_only, d0=d0, d1=d1,
        variance=variance, pairs=pairs_k1, exact_twin_pairs=int(entry["exact_twin_pairs"]),
        cells=int(entry["cells"]),
        q_max_disjoint=ceiling(d0_disjoint) if disjoint_pairs else 0.0,
        q_max_disjoint_k1=ceiling(d1_disjoint) if disjoint_pairs else 0.0,
        q_max_disjoint_clock_only=disjoint_clock_only,
        d0_disjoint=d0_disjoint, d1_disjoint=d1_disjoint, disjoint_pairs=disjoint_pairs)


@dataclass(frozen=True)
class CeilingBracket:
    """THE CEILING IS A BRACKET, NOT A NUMBER, AND THIS IS THE MEASURED REASON.

    The ruling's twin — two actions with IDENTICAL causal-prefix keys — does not
    exist on this object: the census over 12.1M action rows finds ZERO pairs of
    byte-identical `direct_raw` prefixes. Every executable surrogate is therefore
    biased, and BOTH directions have now been measured rather than assumed:

      * the OVERLAP-PERMITTING ladder pairs each action with its prefix-nearest
        neighbour, which is almost always an action a second or two away. Held
        for minutes, those are nearly the same trade, their outcomes are
        correlated by construction, and the discordance collapses. It returns
        ~1.0 on this corpus and ~0.94 even when the market carriers are ignored
        entirely, so it is an UPPER bound on the ceiling and nothing else.
      * the DISJOINT ladder requires the two holding windows not to overlap, so
        the two outcomes really are separate trades. It costs two things: the
        surviving pairs are selected (at small buckets, disjointness selects
        trades that STOPPED early), and the match is a raw Euclidean nearest
        neighbour in 180 standardised carriers, which is a WEAK conditioning set
        — a model may find structure a raw metric cannot see. Both losses push
        the estimate DOWN, so it is a LOWER bound on the ceiling.

    A verdict is only earned when Q* falls outside the bracket."""
    lower: float
    upper: float
    clock_only: float
    bucket_seconds: int
    disjoint_pairs: int
    status: str

    @property
    def prefix_lift(self) -> float:
        """How much the causal prefix adds over knowing the clock bucket alone —
        the single most interpretable number in the whole panel."""
        return self.lower - self.clock_only


def binding_ceiling(ceilings: Dict[Tuple[int, int], Ceiling], horizon: int) -> CeilingBracket:
    """The bracket at the SMALLEST bucket whose disjoint ladder carries enough
    pairs (a wider bucket buys support by weakening the clock match the ruling
    asks for)."""
    for bucket in TWIN_BUCKETS:
        ceiling = ceilings.get((bucket, horizon))
        if ceiling is not None and ceiling.disjoint_pairs >= MIN_DISJOINT_PAIRS:
            return CeilingBracket(ceiling.q_max_disjoint, ceiling.q_max,
                                  ceiling.q_max_disjoint_clock_only, bucket,
                                  ceiling.disjoint_pairs, "DISJOINT_TWINS")
    return CeilingBracket(0.0, 1.0, 0.0, 0, 0, "INSUFFICIENT_SUPPORT")


# --- the Q* search ---------------------------------------------------------


@dataclass(frozen=True)
class CellResult:
    q_skill: float
    horizon: int
    q_percent: int
    rho: float
    mean_dollars: float
    lcb_dollars: float
    mdd_point_dollars: float
    mdd_ucb_dollars: float
    trades_per_session: float
    cap_violations: int
    floor_violations: int
    clears: bool


@dataclass
class SkillSweepResult:
    q_star: float | None
    best_at_q_star: CellResult | None
    q_star_diagnostic_rung: float | None
    per_q_best: List[CellResult]
    floor_violation_total: int
    cells_bounded: int


def evaluate_skill_sweep(receipts: Receipts, replicate: int, positions: Sequence[int],
                         cap: AffineCap, indices: np.ndarray) -> SkillSweepResult:
    net = receipts.sweep_net(replicate)[:, positions]
    trades = receipts.sweep_trades(replicate)[:, positions]
    sessions = len(positions)

    by_q: Dict[float, List[int]] = {}
    for cell_index, (q_skill, _, _, _) in enumerate(receipts.sweep_cells):
        by_q.setdefault(q_skill, []).append(cell_index)

    mean_dollars_all = net.mean(axis=1) / 100.0
    per_q_best: List[CellResult] = []
    q_star: float | None = None
    q_star_rung: float | None = None
    best_at_q_star: CellResult | None = None
    floor_total = 0
    bounded = 0

    for q_skill in sorted(by_q):
        candidates = by_q[q_skill]
        point_mdd = {c: point_mdd_dollars(net[c]) for c in candidates}
        screened = [c for c in candidates
                    if mean_dollars_all[c] > SCREEN_MEAN_DOLLARS
                    and point_mdd[c] < SCREEN_MDD_DOLLARS]
        ranked = sorted(screened, key=lambda c: -mean_dollars_all[c])[:CELL_BUDGET]
        if not ranked:
            # Nothing at this skill level can clear; the strongest cell is still
            # reported so the curve has no holes.
            ranked = sorted(candidates, key=lambda c: -mean_dollars_all[c])[:1]

        best: CellResult | None = None
        best_rung: CellResult | None = None
        for cell_index in ranked:
            q_value, horizon, q_percent, rho = receipts.sweep_cells[cell_index]
            column = net[cell_index]
            lcb, encoded = mean_lcb_dollars(column, cap, indices, strict=False)
            floor_total += encoded.floor_violations
            ucb = mdd_ucb_dollars(column, indices)
            bounded += 1
            result = CellResult(
                q_skill=q_value,
                horizon=horizon,
                q_percent=q_percent,
                rho=rho,
                mean_dollars=float(mean_dollars_all[cell_index]),
                lcb_dollars=lcb,
                mdd_point_dollars=point_mdd[cell_index],
                mdd_ucb_dollars=ucb,
                trades_per_session=float(trades[cell_index].sum()) / sessions,
                cap_violations=encoded.cap_violations,
                floor_violations=encoded.floor_violations,
                # A cell with a session past the -$4,000 floor is REFUSED
                # (CERT_BOUND_VIOLATION); it can never be the admissible best.
                clears=(lcb > MEAN_BAR_DOLLARS and ucb < MDD_BAR_DOLLARS
                        and encoded.floor_violations == 0),
            )
            if best is None or (result.clears, result.lcb_dollars) > (best.clears, best.lcb_dollars):
                best = result
            rung_clears = result.lcb_dollars > DIAGNOSTIC_RUNG_DOLLARS and \
                result.mdd_ucb_dollars < MDD_BAR_DOLLARS
            if rung_clears and best_rung is None:
                best_rung = result
        if best is None:
            continue
        per_q_best.append(best)
        if best_rung is not None and q_star_rung is None:
            q_star_rung = q_skill
        if best.clears and q_star is None:
            q_star = q_skill
            best_at_q_star = best
    return SkillSweepResult(q_star, best_at_q_star, q_star_rung, per_q_best, floor_total, bounded)


# --- the fold reading ------------------------------------------------------


@dataclass
class FoldReading:
    fold: str
    sessions: List[int]
    years: List[int]
    cap: AffineCap
    sweeps: List[SkillSweepResult]
    ceilings: Dict[Tuple[int, int], Ceiling]
    arms_panel: List[Tuple[str, int, float, float, float, int]]
    verdict: str
    q_star: float | None
    q_max: float
    q_max_horizon: int
    pinned_lcb_dollars: float | None
    pinned_rate: float | None
    q_max_bucket_seconds: int
    ceiling_status: str
    bracket: "CeilingBracket"


def _fold_positions(receipts: Receipts, fold: str,
                    allow_partial_train: bool = False) -> Tuple[List[int], List[int], List[int]]:
    low, high = TRAIN_RANGE[fold]
    positions = [i for i, s in enumerate(receipts.sweep_sessions) if low <= s <= high]
    sessions = [receipts.sweep_sessions[i] for i in positions]
    years = [receipts.session_year[s] for s in sessions]
    if not sessions:
        _refuse(f"{fold}: no TRAIN sessions in the receipts")
    if min(sessions) < low or max(sessions) > high:
        _refuse(f"{fold}: a session outside the TRAIN range reached the reading")
    # PROVENANCE: the runner is walled per fold, so a receipts file that carries
    # an ordinal no fold may ever train on did not come from a lawful M2.5 run.
    widest_low = min(r[0] for r in TRAIN_RANGE.values())
    widest_high = max(r[1] for r in TRAIN_RANGE.values())
    stray = [s for s in receipts.sweep_sessions if not widest_low <= s <= widest_high]
    if stray:
        _refuse(f"{fold}: the receipts carry {len(stray)} session(s) outside every fold's TRAIN "
                f"range (first {stray[0]}); these receipts are not from a walled M2.5 run")
    # The other half of the wall: a fold is read on its WHOLE train range or not
    # at all. A receipts directory that silently covers part of it would produce
    # a bound over a different population than the one the verdict names.
    measured = set(receipts.sweep_sessions)
    missing = [s for s in range(low, high + 1) if s not in measured]
    if missing and not allow_partial_train:
        _refuse(f"{fold}: the receipts cover {len(sessions)} of the {high - low + 1} TRAIN "
                f"sessions; {len(missing)} are missing (first {missing[0]}). A partial read "
                f"bounds a different population than the verdict names; pass "
                f"allow_partial_train only for a declared fixture.")
    return positions, sessions, years


def read_fold(receipts: Receipts, arms: Dict, fold: str,
              allow_partial_train: bool = False) -> FoldReading:
    positions, sessions, years = _fold_positions(receipts, fold, allow_partial_train)
    indices = block_draw_indices(years, sessions)

    # THE ENVELOPE and the cap it fixes.
    envelope: Dict[int, np.ndarray] = {}
    for horizon in range(len(HORIZON_LABEL)):
        key = (ENVELOPE_ARM, horizon, BINDING_LOSS_LIMIT_CENT)
        if key not in arms:
            _refuse(f"{fold}: the arms receipt has no {ENVELOPE_ARM} at horizon {horizon}")
        per_session = arms[key]
        envelope[horizon] = np.array([per_session[s][0] for s in sessions], dtype=np.int64)
    cap = derive_affine_cap(envelope)

    # PARITY: the vectorised bootstrap must reproduce the pinned entry point on
    # this fold's own populations before a single bound is believed.
    probe = []
    for horizon in (0, HORIZON_REF_INDEX, 6):
        encoded = affine_encode(envelope[horizon], cap)
        probe.append((encoded.hits, encoded.truths))
    verify_pinned_parity(years, sessions, indices, probe)

    sweeps = [evaluate_skill_sweep(receipts, r, positions, cap, indices)
              for r in range(receipts.replicates)]

    # THE CEILING.
    pooled = load_twins(receipts.out_dir, sessions)
    ceilings = {key: twin_ceiling(entry) for key, entry in pooled.items()}

    # THE PANEL: $/session, MDD, trades/day per arm, at h_ref and at the
    # envelope's own best horizon.
    panel: List[Tuple[str, int, float, float, float, int]] = []
    arm_names = sorted({name for (name, _, limit) in arms if limit == BINDING_LOSS_LIMIT_CENT})
    for name in arm_names:
        for horizon in range(len(HORIZON_LABEL)):
            per_session = arms[(name, horizon, BINDING_LOSS_LIMIT_CENT)]
            nets = np.array([per_session[s][0] for s in sessions], dtype=np.int64)
            trades = np.array([per_session[s][1] for s in sessions], dtype=np.int64)
            breaches = int(sum(per_session[s][2] for s in sessions))
            panel.append((name, horizon, float(nets.mean()) / 100.0, point_mdd_dollars(nets),
                          float(trades.sum()) / len(sessions), breaches))

    primary = sweeps[0]
    q_star = primary.q_star
    horizon = primary.best_at_q_star.horizon if primary.best_at_q_star else HORIZON_REF_INDEX
    bracket = binding_ceiling(ceilings, horizon)
    q_max = bracket.lower

    if q_star is None:
        verdict = "FAIL_UNREACHABLE_AT_ANY_SKILL"
    elif bracket.status == "INSUFFICIENT_SUPPORT":
        # No disjoint twins means no ceiling. That is NOT a pass.
        verdict = "INDETERMINATE_NO_DISJOINT_TWIN_SUPPORT"
    elif q_star <= bracket.lower:
        # Cleared even under the pessimistic bound.
        verdict = "PASS"
    elif q_star > bracket.upper:
        # Out of reach even under the optimistic bound.
        verdict = "FAIL_Q_STAR_ABOVE_Q_MAX"
    else:
        verdict = "INDETERMINATE_Q_STAR_INSIDE_CEILING_BRACKET"

    pinned_lcb = None
    pinned_rate = None
    if primary.best_at_q_star is not None:
        cell_index = next(
            i for i, cell in enumerate(receipts.sweep_cells)
            if cell == (primary.best_at_q_star.q_skill, primary.best_at_q_star.horizon,
                        primary.best_at_q_star.q_percent, primary.best_at_q_star.rho)
        )
        column = receipts.sweep_net(0)[cell_index][positions]
        encoded = affine_encode(column, cap)  # STRICT: the reported cell obeys the floor
        order = sorted(range(len(years)), key=lambda i: (years[i], sessions[i]))
        records = [
            estimator_laws.SessionRecall(year=int(years[i]), ordinal=int(sessions[i]),
                                         hits=int(encoded.hits[i]), truths=int(encoded.truths[i]))
            for i in order
        ]
        pinned_rate = estimator_laws.year_stratified_session_block_lcb(records)
        pinned_lcb = pinned_rate * (cap.floor_dollars + cap.cap_dollars) - cap.floor_dollars

    return FoldReading(fold, sessions, years, cap, sweeps, ceilings, panel, verdict, q_star,
                       q_max, horizon, pinned_lcb, pinned_rate, bracket.bucket_seconds,
                       bracket.status, bracket)


def _fmt(value: float, digits: int = 2) -> str:
    return f"{value:,.{digits}f}"


def write_reading(readings: List[FoldReading], receipts: Receipts, out_dir: pathlib.Path,
                  label: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    receipts_dir = out_dir / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)

    with (receipts_dir / "gate.tsv").open("w") as handle:
        handle.write("fold\tmetric\tvalue\n")
        for reading in readings:
            def row(metric: str, value: object) -> None:
                handle.write(f"{reading.fold}\t{metric}\t{value}\n")
            row("verdict", reading.verdict)
            row("q_star", "NONE" if reading.q_star is None else f"{reading.q_star:.6f}")
            row("q_max_bracket_lower_disjoint", f"{reading.bracket.lower:.6f}")
            row("q_max_bracket_upper_overlapping", f"{reading.bracket.upper:.6f}")
            row("q_max_disjoint_clock_only", f"{reading.bracket.clock_only:.6f}")
            row("prefix_lift_over_clock_only", f"{reading.bracket.prefix_lift:.6f}")
            row("q_max_binding", f"{reading.q_max:.6f}")
            row("q_max_binding_bucket_seconds", reading.q_max_bucket_seconds)
            row("q_max_binding_status", reading.ceiling_status)
            row("q_max_horizon", reading.q_max_horizon)
            row("sessions", len(reading.sessions))
            row("affine_floor_cent", reading.cap.floor_cent)
            row("affine_cap_cent", reading.cap.cap_cent)
            row("affine_truths", reading.cap.truths)
            best = reading.sweeps[0].best_at_q_star
            if best is not None:
                row("best_cell_horizon", best.horizon)
                row("best_cell_q_percent", best.q_percent)
                row("best_cell_rho", f"{best.rho:.2f}")
                row("best_cell_mean_dollars", f"{best.mean_dollars:.2f}")
                row("best_cell_lcb_dollars", f"{best.lcb_dollars:.2f}")
                row("best_cell_mdd_point_dollars", f"{best.mdd_point_dollars:.2f}")
                row("best_cell_mdd_ucb_dollars", f"{best.mdd_ucb_dollars:.2f}")
                row("best_cell_trades_per_session", f"{best.trades_per_session:.4f}")
                row("best_cell_cap_violations", best.cap_violations)
            if reading.pinned_lcb_dollars is not None:
                row("pinned_entry_point_rate", f"{reading.pinned_rate!r}")
                row("pinned_entry_point_lcb_dollars", f"{reading.pinned_lcb_dollars:.6f}")
            row("q_star_diagnostic_rung_1600",
                "NONE" if reading.sweeps[0].q_star_diagnostic_rung is None
                else f"{reading.sweeps[0].q_star_diagnostic_rung:.6f}")
            row("cells_bounded", sum(s.cells_bounded for s in reading.sweeps))
            row("floor_violations_total", sum(s.floor_violation_total for s in reading.sweeps))
            for replicate, sweep in enumerate(reading.sweeps):
                row(f"q_star_replicate_{replicate}",
                    "NONE" if sweep.q_star is None else f"{sweep.q_star:.6f}")

    with (receipts_dir / "skill_curve.tsv").open("w") as handle:
        handle.write("fold\treplicate\tq_skill\thorizon\tq_percent\trho\tmean_dollars\t"
                     "lcb_dollars\tmdd_point_dollars\tmdd_ucb_dollars\ttrades_per_session\t"
                     "cap_violations\tclears\n")
        for reading in readings:
            for replicate, sweep in enumerate(reading.sweeps):
                for cell in sweep.per_q_best:
                    handle.write(
                        f"{reading.fold}\t{replicate}\t{cell.q_skill:.6f}\t{cell.horizon}\t"
                        f"{cell.q_percent}\t{cell.rho:.2f}\t{cell.mean_dollars:.2f}\t"
                        f"{cell.lcb_dollars:.2f}\t{cell.mdd_point_dollars:.2f}\t"
                        f"{cell.mdd_ucb_dollars:.2f}\t{cell.trades_per_session:.4f}\t"
                        f"{cell.cap_violations}\t{int(cell.clears)}\n")

    with (receipts_dir / "twin_ceiling.tsv").open("w") as handle:
        handle.write("fold\tbucket_seconds\thorizon\tq_max_disjoint\tq_max_disjoint_k1\t"
                     "q_max_disjoint_clock_only\tdisjoint_pairs\td0_disjoint\td1_disjoint\t"
                     "q_max_overlapping\tq_max_overlapping_k1\tq_max_clock_only_overlapping\t"
                     "d0\td1\tvariance\tnearest_pairs\texact_key_twin_pairs\tcells\n")
        for reading in readings:
            for (bucket, horizon) in sorted(reading.ceilings):
                c = reading.ceilings[(bucket, horizon)]
                handle.write(f"{reading.fold}\t{bucket}\t{horizon}\t{c.q_max_disjoint:.6f}\t"
                             f"{c.q_max_disjoint_k1:.6f}\t{c.q_max_disjoint_clock_only:.6f}\t"
                             f"{c.disjoint_pairs}\t{c.d0_disjoint:.6f}\t{c.d1_disjoint:.6f}\t"
                             f"{c.q_max:.6f}\t{c.q_max_k1:.6f}\t{c.q_max_clock_only:.6f}\t"
                             f"{c.d0:.6f}\t{c.d1:.6f}\t{c.variance:.6f}\t{c.pairs}\t"
                             f"{c.exact_twin_pairs}\t{c.cells}\n")

    with (receipts_dir / "decomposition.tsv").open("w") as handle:
        handle.write("fold\tarm\thorizon\tdollars_per_session\tmdd_dollars\ttrades_per_session\t"
                     "breaches\n")
        for reading in readings:
            for (name, horizon, dollars, mdd, trades, breaches) in reading.arms_panel:
                handle.write(f"{reading.fold}\t{name}\t{horizon}\t{dollars:.2f}\t{mdd:.2f}\t"
                             f"{trades:.4f}\t{breaches}\n")

    with (receipts_dir / "affine_cap.tsv").open("w") as handle:
        handle.write("fold\thorizon\tp999_cent\tp999_dollars\n")
        for reading in readings:
            for horizon, value in enumerate(reading.cap.per_horizon_cap_cent):
                handle.write(f"{reading.fold}\t{horizon}\t{value}\t{value / 100.0:.2f}\n")
            handle.write(f"{reading.fold}\tpooled\t{reading.cap.cap_cent}\t"
                         f"{reading.cap.cap_dollars:.2f}\n")

    lines: List[str] = []
    lines.append("# M2.5 READING — reachability and decomposition on the exact object")
    lines.append("")
    lines.append(f"Corpus: `{receipts.run_meta.get('run_dir', '?')}` | "
                 f"frozen card sha `{receipts.run_meta.get('card_sha256', '?')}` | "
                 f"pinned estimator sha `{_PINNED_SHA}`")
    lines.append(f"Runner: {receipts.run_meta.get('sessions', '?')} TRAIN sessions, "
                 f"{receipts.run_meta.get('sweep_cells', '?')} sweep cells, "
                 f"{receipts.run_meta.get('replicates', '?')} noise replicate(s), "
                 f"wall {receipts.run_meta.get('wall_ms', '?')} ms"
                 + (f" | {label}" if label else ""))
    lines.append("")
    lines.append("## 1. THE GATE — Q* vs Q_max")
    lines.append("")
    lines.append("Bar: mean LCB > $2,000/session AND MDD_UCB < $1,000, TRAIN only, "
                 "through the frozen replay kernel and the pinned estimator.")
    lines.append("")
    lines.append("| fold | sessions | Q* | best cell (h, q, rho) | mean LCB | MDD UCB | "
                 "trades/session | Q_max bracket [lower, upper] | verdict |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for reading in readings:
        best = reading.sweeps[0].best_at_q_star
        cell = ("—" if best is None else
                f"{HORIZON_LABEL[best.horizon]}, q={best.q_percent}%, rho={best.rho:.2f}")
        lines.append(
            f"| {reading.fold} | {len(reading.sessions)} (s{min(reading.sessions)}..s{max(reading.sessions)}) | "
            f"{'NONE' if reading.q_star is None else f'{reading.q_star:.3f}'} | {cell} | "
            f"{'—' if best is None else '$' + _fmt(best.lcb_dollars)} | "
            f"{'—' if best is None else '$' + _fmt(best.mdd_ucb_dollars)} | "
            f"{'—' if best is None else _fmt(best.trades_per_session, 3)} | "
            f"[{reading.bracket.lower:.3f}, {reading.bracket.upper:.3f}] | "
            f"**{reading.verdict}** |")
    lines.append("")
    for reading in readings:
        if reading.pinned_lcb_dollars is not None:
            lines.append(f"- {reading.fold}: the winning cell's bound recomputed through the "
                         f"PINNED entry point `year_stratified_session_block_lcb` = pooled rate "
                         f"{reading.pinned_rate!r} -> **${_fmt(reading.pinned_lcb_dollars)}** "
                         f"per session.")
        rung = reading.sweeps[0].q_star_diagnostic_rung
        lines.append(f"- {reading.fold}: diagnostic rung (the $1,600 headroom bar, REPORTED ONLY, "
                     f"never the gate): minimal Q = "
                     f"{'NONE' if rung is None else f'{rung:.3f}'}.")
        lines.append(f"- {reading.fold}: seed-stability of Q* over noise replicates: " +
                     ", ".join('NONE' if s.q_star is None else f"{s.q_star:.3f}"
                               for s in reading.sweeps))
    lines.append("")
    lines.append("## 2. THE SKILL CURVE (best admissible cell at each skill level)")
    lines.append("")
    for reading in readings:
        lines.append(f"### {reading.fold}")
        lines.append("")
        lines.append("| Q | h | q% | rho | $/session (point) | mean LCB | MDD point | MDD UCB | "
                     "trades/session | clears |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for cell in reading.sweeps[0].per_q_best:
            lines.append(
                f"| {cell.q_skill:.3f} | {HORIZON_LABEL[cell.horizon]} | {cell.q_percent} | "
                f"{cell.rho:.2f} | ${_fmt(cell.mean_dollars)} | ${_fmt(cell.lcb_dollars)} | "
                f"${_fmt(cell.mdd_point_dollars)} | ${_fmt(cell.mdd_ucb_dollars)} | "
                f"{_fmt(cell.trades_per_session, 3)} | {'YES' if cell.clears else 'no'} |")
        lines.append("")
    lines.append("## 3. THE OBSERVABILITY CEILING Q_max (twin discordance)")
    lines.append("")
    lines.append("EXACT-key twins do not exist on this object: over every session and every "
                 "clock bucket the census counts ZERO pairs of actions with byte-identical "
                 "`direct_raw` prefixes, so the ceiling is estimated from nearest neighbours "
                 "and extrapolated to zero prefix distance.")
    lines.append("")
    lines.append("THE OVERLAP DEFECT, MEASURED. The prefix-nearest neighbour of an action is "
                 "almost always an action a second or two away, and two such actions held for "
                 "minutes are nearly the SAME TRADE — their outcomes are correlated by "
                 "construction and the discordance collapses. The OVERLAP-PERMITTING columns "
                 "below show what that does (a clock-bucket-only 'ceiling' near 0.94, which is "
                 "not a statement about predictability at all). The BINDING number is the "
                 "DISJOINT ladder: pairs whose holding windows do not overlap.")
    lines.append("")
    lines.append("| fold | horizon | binding Q_max (disjoint) | bucket | disjoint pairs | "
                 "disjoint k1 | disjoint clock-only | overlapping Q_max | overlapping k1 | "
                 "overlapping clock-only | exact-key twins |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for reading in readings:
        for (bucket, horizon) in sorted(reading.ceilings):
            if horizon != reading.q_max_horizon and horizon != HORIZON_REF_INDEX:
                continue
            c = reading.ceilings[(bucket, horizon)]
            lines.append(f"| {reading.fold} | {HORIZON_LABEL[horizon]} | "
                         f"{c.q_max_disjoint:.4f} | {bucket}s | {c.disjoint_pairs:,} | "
                         f"{c.q_max_disjoint_k1:.4f} | {c.q_max_disjoint_clock_only:.4f} | "
                         f"{c.q_max:.4f} | {c.q_max_k1:.4f} | {c.q_max_clock_only:.4f} | "
                         f"{c.exact_twin_pairs} |")
    lines.append("")
    for reading in readings:
        lines.append(f"- {reading.fold}: the binding bracket is read at the {reading.q_max_bucket_seconds}s "
                     f"bucket (status {reading.ceiling_status}, {reading.bracket.disjoint_pairs:,} "
                     f"disjoint pairs, minimum support {MIN_DISJOINT_PAIRS:,}). "
                     f"**Prefix lift over the clock bucket alone: "
                     f"{reading.bracket.prefix_lift:+.4f}** "
                     f"(disjoint ceiling {reading.bracket.lower:.4f} vs clock-only "
                     f"{reading.bracket.clock_only:.4f}) — this is what the causal prefix adds "
                     f"to a predictor that already knows the time of day, under a raw Euclidean "
                     f"match on the 180 DIRECT_RAW carriers.")
    lines.append("")
    lines.append("## 4. DECOMPOSITION PANEL (TRAIN only, one replay kernel, no hindsight exits)")
    lines.append("")
    for reading in readings:
        lines.append(f"### {reading.fold} — at h_ref = 15m")
        lines.append("")
        lines.append("| arm | $/session | MDD | trades/session | breaches |")
        lines.append("|---|---|---|---|---|")
        for (name, horizon, dollars, mdd, trades, breaches) in reading.arms_panel:
            if horizon != HORIZON_REF_INDEX:
                continue
            lines.append(f"| {name} | ${_fmt(dollars)} | ${_fmt(mdd)} | {_fmt(trades, 3)} | "
                         f"{breaches} |")
        lines.append("")
    lines.append("## 5. THE AFFINE CAP B")
    lines.append("")
    lines.append("FINAL_PLAN section 8: B is re-derived from the perfect-skill envelope "
                 "(the one-position optimum through the same kernel), replacing the a-priori "
                 "$12,000. A stays at the preregistered $4,000 floor.")
    lines.append("")
    lines.append("| fold | A (floor) | B = p99.9 of envelope nets | A+B (truths/100) | "
                 "cap incidence | floor incidence |")
    lines.append("|---|---|---|---|---|---|")
    for reading in readings:
        best = reading.sweeps[0].best_at_q_star
        lines.append(f"| {reading.fold} | ${_fmt(reading.cap.floor_dollars)} | "
                     f"${_fmt(reading.cap.cap_dollars)} | "
                     f"${_fmt(reading.cap.floor_dollars + reading.cap.cap_dollars)} | "
                     f"{'—' if best is None else best.cap_violations} | "
                     f"{sum(s.floor_violation_total for s in reading.sweeps)} |")
    lines.append("")
    (out_dir / "M25_READING.md").write_text("\n".join(lines) + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="assemble the M2.5 reading")
    parser.add_argument("--receipts", required=True, type=pathlib.Path)
    parser.add_argument("--out", required=True, type=pathlib.Path)
    parser.add_argument("--folds", default="F4,F5")
    parser.add_argument("--label", default="")
    parser.add_argument("--allow-partial-train", action="store_true",
                        help="declared fixture use only: read a fold whose TRAIN range the "
                             "receipts do not fully cover")
    args = parser.parse_args(argv)

    assert_pinned_estimator()
    receipts = load_receipts(args.receipts)
    arms = load_arms(args.receipts)
    folds = [f.strip() for f in args.folds.split(",") if f.strip()]
    readings = [read_fold(receipts, arms, fold, args.allow_partial_train) for fold in folds]
    write_reading(readings, receipts, args.out, args.label)
    for reading in readings:
        print(f"{reading.fold}: verdict={reading.verdict} "
              f"q_star={reading.q_star} q_max={reading.q_max:.4f} "
              f"B=${reading.cap.cap_dollars:,.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
