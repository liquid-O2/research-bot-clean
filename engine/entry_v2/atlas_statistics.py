"""Frozen statistical laws for the Entry V2 objective atlas.

The functions in this module deliberately operate on already materialized,
fit-only arrays.  They do not know how to open a corpus and therefore cannot
silently extend the authorized chronology.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from types import MappingProxyType
from typing import Mapping, Sequence

import numpy as np
from scipy.stats import t as student_t


EXACT_ASSETS = ("HG", "NKD", "SI")

# Zero-variance/degenerate columns are typed losers.  They are retained in the
# ledger and in the preregistered hypothesis family, but they never receive a
# numeric p-value and are never eligible for selection.
DEGENERATE_ZERO_VARIANCE = "DEGENERATE_ZERO_VARIANCE"
STOCHASTIC = "STOCHASTIC"


class AtlasStatisticsRefusal(RuntimeError):
    pass


class SupportKind(str, Enum):
    CONTINUOUS = "continuous"
    BINARY_ORDINAL = "binary_ordinal"
    COMPETING_CAUSE = "competing_cause"
    EXACT_TIME_RANKING = "exact_time_ranking"
    ECONOMIC = "economic"


class SupportState(str, Enum):
    MATERIALIZED = "MATERIALIZED"
    UNAVAILABLE_LOW_SUPPORT = "UNAVAILABLE_LOW_SUPPORT"


class PairedTestState(str, Enum):
    """Typed outcome of one paired day-clustered objective test.

    Only ``MATERIALIZED`` carries a numeric p-value.  Every other state is a
    ledger entry that the Holm consumer must skip explicitly.
    """

    MATERIALIZED = "MATERIALIZED"
    DEGENERATE_ZERO_VARIANCE = "DEGENERATE_ZERO_VARIANCE"
    UNAVAILABLE_LOW_SUPPORT = "UNAVAILABLE_LOW_SUPPORT"


@dataclass(frozen=True)
class SupportDecision:
    state: SupportState
    pooled: Mapping[str, int]
    per_asset: Mapping[str, Mapping[str, int]]
    nonzero_iqr: bool | None
    receipt_sha256: str

    @property
    def available(self) -> bool:
        return self.state is SupportState.MATERIALIZED


def _digest(payload: object) -> str:
    return hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    ).encode()).hexdigest()


def support_gate(
    kind: SupportKind | str,
    *,
    asset: Sequence[str],
    valid: Sequence[bool] | None = None,
    values: Sequence[float | int] | None = None,
    required_levels: Sequence[int] | None = None,
    group_id: Sequence[str | int] | None = None,
    day: Sequence[str | int] | None = None,
    decision_ts: Sequence[int] | None = None,
    censored: Sequence[bool] | None = None,
) -> SupportDecision:
    """Apply the exact frozen fit-only support boundary.

    For ranking, ``group_id`` is candidate-aligned; only exact-time groups with
    at least two available candidates count.  Economic support counts unique
    eligible asset-days.  Continuous cells require 500 pooled and 100 per-asset
    *uncensored* observations, so ``censored`` is mandatory for that family:
    a finite right-censored value is not an observation.
    """
    kind = SupportKind(kind)
    a = np.asarray(asset, dtype=str)
    n = len(a)
    v = np.ones(n, dtype=bool) if valid is None else np.asarray(valid, dtype=bool)
    if v.shape != (n,):
        raise AtlasStatisticsRefusal("support validity is misaligned")
    assets = tuple(sorted(set(a.tolist())))
    if assets != EXACT_ASSETS:
        raise AtlasStatisticsRefusal("support census must contain exactly HG/NKD/SI")
    pooled: dict[str, int] = {}
    per: dict[str, dict[str, int]] = {x: {} for x in assets}
    ok = True
    nz_iqr: bool | None = None

    if kind is SupportKind.CONTINUOUS:
        if values is None:
            raise AtlasStatisticsRefusal("continuous support requires values")
        y = np.asarray(values, dtype=np.float64)
        if y.shape != (n,):
            raise AtlasStatisticsRefusal("continuous values are misaligned")
        if censored is None:
            raise AtlasStatisticsRefusal(
                "continuous support requires the candidate-aligned censor mask"
            )
        censor = np.asarray(censored, dtype=bool)
        if censor.shape != (n,):
            raise AtlasStatisticsRefusal("continuous censor mask is misaligned")
        usable = v & np.isfinite(y) & ~censor
        pooled["observations"] = int(usable.sum())
        pooled["censored_excluded"] = int(np.sum(v & np.isfinite(y) & censor))
        nz_iqr = bool(usable.any() and np.subtract(*np.percentile(y[usable], [75, 25])) > 0)
        ok &= pooled["observations"] >= 500 and nz_iqr
        for x in assets:
            m = usable & (a == x)
            count = int(m.sum())
            local_iqr = bool(m.any() and np.subtract(*np.percentile(y[m], [75, 25])) > 0)
            per[x] = {"observations": count, "nonzero_iqr": int(local_iqr)}
            ok &= count >= 100 and local_iqr
    elif kind in (SupportKind.BINARY_ORDINAL, SupportKind.COMPETING_CAUSE):
        if values is None or required_levels is None or not tuple(required_levels):
            raise AtlasStatisticsRefusal("class/cause support requires required levels")
        y = np.asarray(values)
        if y.shape != (n,):
            raise AtlasStatisticsRefusal("class/cause values are misaligned")
        pooled_floor = 200
        asset_floor = 25
        for level in tuple(required_levels):
            key = str(int(level))
            pooled[key] = int(np.sum(v & (y == level)))
            ok &= pooled[key] >= pooled_floor
            for x in assets:
                count = int(np.sum(v & (a == x) & (y == level)))
                per[x][key] = count
                ok &= count >= asset_floor
    elif kind is SupportKind.EXACT_TIME_RANKING:
        if group_id is None or day is None or decision_ts is None:
            raise AtlasStatisticsRefusal(
                "ranking support requires asset/day/decision-time/group identity"
            )
        g = np.asarray(group_id)
        d = np.asarray(day).astype(str)
        t = np.asarray(decision_ts, dtype=np.int64)
        if g.shape != (n,) or d.shape != (n,) or t.shape != (n,):
            raise AtlasStatisticsRefusal("ranking identities are misaligned")
        gs = g.astype(str)
        eligible: set[tuple[str, str, int, str]] = set()
        identities = tuple(zip(a[v].tolist(), d[v].tolist(),
                               t[v].tolist(), gs[v].tolist()))
        for key in set(identities):
            members = v & (a == key[0]) & (d == key[1]) & (t == key[2]) & (gs == key[3])
            if int(np.sum(members)) >= 2:
                eligible.add(key)
        pooled["groups"] = len(eligible)
        ok &= pooled["groups"] >= 200
        for x in assets:
            count = sum(key[0] == x for key in eligible)
            per[x]["groups"] = count
            ok &= count >= 40
    else:
        if day is None:
            raise AtlasStatisticsRefusal("economic support requires day ids")
        d = np.asarray(day)
        if d.shape != (n,):
            raise AtlasStatisticsRefusal("economic day ids are misaligned")
        pooled["asset_days"] = len(set(zip(a[v].tolist(), d[v].tolist())))
        for x in assets:
            count = len(set(d[v & (a == x)].tolist()))
            per[x]["asset_days"] = count
            ok &= count >= 60

    state = SupportState.MATERIALIZED if ok else SupportState.UNAVAILABLE_LOW_SUPPORT
    payload = {"kind": kind.value, "state": state.value, "pooled": pooled,
               "per_asset": per, "nonzero_iqr": nz_iqr}
    return SupportDecision(state, pooled, per, nz_iqr, _digest(payload))


@dataclass(frozen=True)
class PairedClusterResult:
    mean_difference: float
    standard_error: float
    t_statistic: float | None
    p_value_one_sided: float | None
    n_rows: int
    n_day_clusters: int
    receipt_sha256: str
    state: PairedTestState = PairedTestState.MATERIALIZED

    @property
    def available(self) -> bool:
        return self.state is PairedTestState.MATERIALIZED


@dataclass(frozen=True)
class PairedObservationRecord:
    candidate_id: str
    asset: str
    day: str
    recipient_mask: bool
    real_target_sha256: str
    twin_target_sha256: str
    real_value: float
    shuffled_value: float


def paired_day_cluster_test(
    real: Sequence[float], shuffled: Sequence[float], day_cluster: Sequence[str]
) -> PairedClusterResult:
    """Equal-observation real-minus-shuffled day-clustered intercept test.

    Callers that begin with candidate rows must first collapse each asset-day
    to one observation.  This keeps every eligible asset-day at total weight
    one while still clustering the three products that share a calendar day.
    """
    r = np.asarray(real, dtype=np.float64)
    s = np.asarray(shuffled, dtype=np.float64)
    day = np.asarray(day_cluster, dtype=str)
    if r.shape != s.shape or r.shape != day.shape or r.ndim != 1 or not len(r):
        raise AtlasStatisticsRefusal("paired records are empty or misaligned")
    if not np.all(np.isfinite(r)) or not np.all(np.isfinite(s)):
        raise AtlasStatisticsRefusal("paired records contain non-finite values")
    x = r - s
    mu = float(x.mean())
    keys = tuple(sorted(set(day.tolist())))
    g = len(keys)
    if g < 2:
        # A-019: the full ledger must be retained.  A thin day census is a
        # typed unavailable objective, never an exception that aborts the
        # surrounding 44-objective screen from inside its loop.
        payload = {"mean": mu, "se": None, "t": None, "p": None, "n": len(x),
                   "g": g, "state": PairedTestState.UNAVAILABLE_LOW_SUPPORT.value}
        return PairedClusterResult(
            mu, 0.0, None, None, len(x), g, _digest(payload),
            PairedTestState.UNAVAILABLE_LOW_SUPPORT,
        )
    scores = np.asarray([np.sum(x[day == k] - mu) for k in keys], dtype=np.float64)
    se = float(np.sqrt(g / (g - 1) * np.sum(scores * scores)) / len(x))
    if not se > 0:
        # A zero-variance paired column has no sampling uncertainty.  It must
        # never studentize to +/-inf and win Holm at any alpha.
        payload = {"mean": mu, "se": se, "t": None, "p": None, "n": len(x),
                   "g": g, "state": PairedTestState.DEGENERATE_ZERO_VARIANCE.value}
        return PairedClusterResult(
            mu, se, None, None, len(x), g, _digest(payload),
            PairedTestState.DEGENERATE_ZERO_VARIANCE,
        )
    t = mu / se
    # A-013.d frozen resolution: the day-cluster count is the whole sample
    # size of the clustered intercept test, so the reference law is Student-t
    # on G-1 degrees of freedom, never the normal tail.
    p = float(student_t.sf(t, g - 1))
    payload = {"mean": mu, "se": se, "t": t, "p": p, "n": len(x), "g": g,
               "reference": "student-t-day-cluster-df-v1",
               "state": PairedTestState.MATERIALIZED.value}
    return PairedClusterResult(mu, se, float(t), p, len(x), g, _digest(payload),
                               PairedTestState.MATERIALIZED)


def paired_day_cluster_records(records: Sequence[PairedObservationRecord]) -> PairedClusterResult:
    rows = tuple(sorted(records, key=lambda row: (row.asset, row.day, row.candidate_id)))
    if not rows or len({row.candidate_id for row in rows}) != len(rows):
        raise AtlasStatisticsRefusal("paired candidate records are empty or duplicated")
    if tuple(sorted({row.asset for row in rows})) != EXACT_ASSETS:
        raise AtlasStatisticsRefusal("paired records must bind all three assets")
    real_hashes = {row.real_target_sha256 for row in rows}
    twin_hashes = {row.twin_target_sha256 for row in rows}
    if (len(real_hashes) != 1 or len(twin_hashes) != 1
            or any(len(x) != 64 for x in (*real_hashes, *twin_hashes))):
        raise AtlasStatisticsRefusal("paired target hashes are inconsistent")
    if real_hashes == twin_hashes:
        raise AtlasStatisticsRefusal("paired real and shuffled target hashes are identical")
    active = tuple(row for row in rows if row.recipient_mask)
    if not active:
        raise AtlasStatisticsRefusal("paired records have no recipient-supported rows")
    # The authority is explicitly asset-day balanced.  Candidate multiplicity
    # cannot give a busy product/day more influence, so reduce each recipient
    # asset-day to its mean paired difference before the day-clustered test.
    by_asset_day: dict[tuple[str, str], list[float]] = {}
    for row in active:
        by_asset_day.setdefault((row.asset, row.day), []).append(
            float(row.real_value) - float(row.shuffled_value)
        )
    asset_days = tuple(sorted(by_asset_day))
    differences = np.asarray([
        np.mean(by_asset_day[key], dtype=np.float64) for key in asset_days
    ], dtype=np.float64)
    result = paired_day_cluster_test(
        differences, np.zeros_like(differences), [key[1] for key in asset_days]
    )
    binding = {
        "candidate_ids": [row.candidate_id for row in rows],
        "assets": [row.asset for row in rows], "days": [row.day for row in rows],
        "recipient_mask": [row.recipient_mask for row in rows],
        "real_target_sha256": next(iter(real_hashes)),
        "twin_target_sha256": next(iter(twin_hashes)),
        "test_receipt_sha256": result.receipt_sha256,
        "asset_day_count": len(asset_days),
        "asset_day_balance_law": "each-recipient-asset-day-total-weight-one-v1",
        "state": result.state.value,
    }
    return PairedClusterResult(
        result.mean_difference, result.standard_error, result.t_statistic,
        result.p_value_one_sided, result.n_rows, result.n_day_clusters,
        _digest(binding), result.state,
    )


def _split_typed_p_values(
    p_values: Mapping[str, object]
) -> tuple[dict[str, float], dict[str, str]]:
    """Separate numeric p-values from typed non-numeric ledger entries.

    A typed entry (``PairedTestState`` other than ``MATERIALIZED``, a
    non-materialized ``PairedClusterResult``, or ``None``) is skipped
    EXPLICITLY: it never enters the multiplicity count and never receives a
    numeric p-value, but it is returned so the caller retains it in the ledger.
    """
    numeric: dict[str, float] = {}
    skipped: dict[str, str] = {}
    for key, value in p_values.items():
        name = str(key)
        if value is None:
            skipped[name] = PairedTestState.UNAVAILABLE_LOW_SUPPORT.value
        elif isinstance(value, PairedTestState):
            if value is PairedTestState.MATERIALIZED:
                raise AtlasStatisticsRefusal(
                    "a materialized paired test must supply its numeric p-value"
                )
            skipped[name] = value.value
        elif isinstance(value, PairedClusterResult):
            if value.state is PairedTestState.MATERIALIZED \
                    and value.p_value_one_sided is not None:
                numeric[name] = float(value.p_value_one_sided)
            else:
                skipped[name] = value.state.value
        else:
            p = float(value)
            if not np.isfinite(p):
                raise AtlasStatisticsRefusal("Holm p-values must be finite")
            numeric[name] = p
    return numeric, skipped


def holm_rejections_with_ledger(
    p_values: Mapping[str, object], alpha: float = .05
) -> tuple[tuple[str, ...], Mapping[str, str]]:
    numeric, skipped = _split_typed_p_values(p_values)
    if not numeric:
        return (), MappingProxyType(dict(sorted(skipped.items())))
    ordered = sorted(numeric.items(), key=lambda z: (z[1], z[0]))
    if any(not 0 <= p <= 1 for _, p in ordered):
        raise AtlasStatisticsRefusal("Holm p-values must lie in [0,1]")
    accepted: list[str] = []
    m = len(ordered)
    for i, (name, p) in enumerate(ordered):
        if p <= alpha / (m - i):
            accepted.append(name)
        else:
            break
    return tuple(accepted), MappingProxyType(dict(sorted(skipped.items())))


def holm_rejections(p_values: Mapping[str, object], alpha: float = .05) -> tuple[str, ...]:
    return holm_rejections_with_ledger(p_values, alpha)[0]


@dataclass(frozen=True)
class HierarchicalHolmResult:
    surviving_families: tuple[str, ...]
    surviving_probes: tuple[str, ...]
    family_omnibus_p_values: Mapping[str, float]
    probe_p_values: Mapping[str, float]
    alpha: float
    receipt_sha256: str
    excluded_probes: tuple[str, ...] = ()
    excluded_probe_states: Mapping[str, str] = MappingProxyType({})


def hierarchical_holm(
    probe_p: Mapping[str, object], probe_family: Mapping[str, str], alpha: float = .05
) -> HierarchicalHolmResult:
    if set(probe_p) != set(probe_family):
        raise AtlasStatisticsRefusal("probe p-values and family map differ")
    numeric, skipped = _split_typed_p_values(probe_p)
    members: dict[str, dict[str, float]] = {}
    for probe, p in numeric.items():
        members.setdefault(probe_family[probe], {})[probe] = float(p)
    # Frozen Bonferroni-min intersection p-value per family, then Holm.  Typed
    # degenerate/low-support probes are skipped explicitly: they change neither
    # the family census nor the within-family multiplicity.
    family_p = {fam: min(1.0, len(rows) * min(rows.values())) for fam, rows in members.items()}
    families = holm_rejections(family_p, alpha)
    probes: list[str] = []
    for fam in families:
        probes.extend(holm_rejections(members[fam], alpha))
    excluded = tuple(sorted(skipped))
    payload = {"law": "bonferroni-min-family-then-holm-within-v1",
               "family_p": family_p, "probe_p": dict(numeric), "alpha": alpha,
               "families": families, "probes": probes,
               "excluded_probes": excluded,
               "excluded_probe_states": dict(sorted(skipped.items()))}
    return HierarchicalHolmResult(
        tuple(families), tuple(probes), family_p, dict(numeric), alpha,
        _digest(payload), excluded,
        MappingProxyType(dict(sorted(skipped.items()))),
    )


@dataclass(frozen=True)
class FinalistSelectionResult:
    finalists: tuple[str, ...]
    ordered_probe_ids: tuple[str, ...]
    target_hashes: Mapping[str, str]
    correlation_sha256: str
    receipt_sha256: str


def nonredundant_finalists(
    ordered_probe_ids: Sequence[str], *, target_correlation: np.ndarray,
    target_hashes: Mapping[str, str], correlation_limit: float = .999999,
    maximum: int = 4,
) -> FinalistSelectionResult:
    ids = tuple(ordered_probe_ids)
    corr = np.asarray(target_correlation, dtype=np.float64)
    if corr.shape != (len(ids), len(ids)) or not np.all(np.isfinite(corr)):
        raise AtlasStatisticsRefusal("target-correlation matrix is invalid")
    if maximum > 4 or maximum < 0 or set(ids) != set(target_hashes):
        raise AtlasStatisticsRefusal("finalist limit/hash binding is invalid")
    kept: list[int] = []
    seen_hashes: set[str] = set()
    for i, probe in enumerate(ids):
        h = target_hashes[probe]
        if h in seen_hashes or any(abs(corr[i, j]) >= correlation_limit for j in kept):
            continue
        kept.append(i)
        seen_hashes.add(h)
        if len(kept) == maximum:
            break
    finalists = tuple(ids[i] for i in kept)
    correlation_hash = _digest({"dtype": str(corr.dtype), "shape": corr.shape,
                                "bytes_sha256": hashlib.sha256(
                                    np.ascontiguousarray(corr).tobytes()).hexdigest()})
    payload = {"ordered": ids, "finalists": finalists,
               "target_hashes": dict(target_hashes),
               "correlation_sha256": correlation_hash,
               "correlation_limit": correlation_limit, "maximum": maximum}
    return FinalistSelectionResult(finalists, ids, dict(target_hashes),
                                   correlation_hash, _digest(payload))


@dataclass(frozen=True)
class RomanoWolfResult:
    estimates: np.ndarray
    standard_errors: np.ndarray
    simultaneous_lower_bounds: np.ndarray
    max_t_critical_value: float
    seed: int
    resamples: int
    receipt_sha256: str
    hypothesis_ids: tuple[str, ...]
    hypothesis_assets: tuple[str, ...]
    hypothesis_families: tuple[str, ...]
    hypothesis_map_sha256: str
    stochastic_mask: np.ndarray
    eligible_mask: np.ndarray | None = None
    column_states: tuple[str, ...] = ()


def romano_wolf_lower_bounds(
    day_cluster_effects: np.ndarray, *, alpha: float = .05,
    seed: int = 20260816, resamples: int = 4096,
    hypothesis_ids: Sequence[str] | None = None,
    hypothesis_assets: Sequence[str] | None = None,
    hypothesis_families: Sequence[str] | None = None,
) -> RomanoWolfResult:
    """Deterministic one-sided max-t sign-flip simultaneous lower bounds.

    Columns are the preregistered finalist-by-asset hypotheses and rows are
    aligned day clusters.  Missing hypotheses/days must be resolved upstream;
    accepting NaNs here would silently alter multiplicity.
    """
    x = np.asarray(day_cluster_effects, dtype=np.float64)
    if (x.ndim != 2 or x.shape[0] < 2 or x.shape[1] < 3
            or x.shape[1] > 30 or x.shape[1] % 3 != 0
            or not np.all(np.isfinite(x))):
        raise AtlasStatisticsRefusal("max-t input must be a finite day-by-hypothesis matrix")
    if seed != 20260816 or resamples < 1 or not 0 < alpha < 1:
        raise AtlasStatisticsRefusal("max-t seed/alpha/resample law differs")
    ids = tuple(str(x) for x in (hypothesis_ids or ()))
    assets = tuple(str(x) for x in (hypothesis_assets or ()))
    families = tuple(str(x) for x in (hypothesis_families or ()))
    if (len(ids) != x.shape[1] or len(set(ids)) != len(ids)
            or len(assets) != x.shape[1] or set(assets) != set(EXACT_ASSETS)
            or len(families) != x.shape[1] or any(not value for value in families)):
        raise AtlasStatisticsRefusal("max-t hypotheses require an exact finalist/asset map")
    by_finalist: dict[str, set[str]] = {}
    for identifier, asset, finalist in zip(ids, assets, families):
        if asset not in EXACT_ASSETS:
            raise AtlasStatisticsRefusal("max-t hypothesis has unknown asset")
        by_finalist.setdefault(finalist, set()).add(asset)
    if any(value != set(EXACT_ASSETS) for value in by_finalist.values()):
        raise AtlasStatisticsRefusal("every finalist must carry all three asset hypotheses")
    g = x.shape[0]
    estimate = x.mean(axis=0)
    centered = x - estimate
    se = x.std(axis=0, ddof=1) / np.sqrt(g)
    stochastic = se > 0.0
    rng = np.random.default_rng(seed)
    maxima = np.empty(resamples, dtype=np.float64)
    # Chunking fixes memory without changing the RNG stream.
    done = 0
    while done < resamples:
        count = min(256, resamples - done)
        signs = rng.integers(0, 2, size=(count, g), dtype=np.int8) * 2 - 1
        boot = signs.astype(np.float64) @ centered / g
        # Deterministic typed-loser columns remain in the preregistered family
        # and retain their exact estimate, but are not divided by zero or
        # studentized.  They have no sampling uncertainty and therefore do
        # not enlarge the stochastic max-t reference distribution.
        maxima[done:done + count] = (np.max(
            boot[:, stochastic] / se[stochastic], axis=1)
            if np.any(stochastic) else 0.0)
        done += count
    critical = float(np.quantile(maxima, 1 - alpha, method="higher"))
    # A finalist column must be STOCHASTIC (se > 0) to be eligible for
    # selection.  A deterministic column carries no sampling uncertainty, so
    # it cannot be assigned lower = estimate and pass selection with a
    # constant-positive mean; its simultaneous lower bound is -inf and it is
    # marked as a typed loser.  When every column is degenerate the critical
    # value is 0.0, which must still select nothing.
    lower = np.where(stochastic, estimate - critical * se, -np.inf)
    eligible = stochastic.copy()
    column_states = tuple(STOCHASTIC if bool(flag) else DEGENERATE_ZERO_VARIANCE
                          for flag in stochastic.tolist())
    map_hash = _digest({"ids": ids, "assets": assets, "families": families})
    payload = {"shape": x.shape, "estimate": estimate.tolist(), "se": se.tolist(),
               "critical": critical, "lower": lower.tolist(), "seed": seed,
               "resamples": resamples, "hypothesis_map_sha256": map_hash,
               "stochastic_mask": stochastic.tolist(),
               "eligible_mask": eligible.tolist(),
               "column_states": list(column_states),
               "selection_eligibility_law": "stochastic-se-positive-required-v1",
               "deterministic_columns_retained": int(np.count_nonzero(~stochastic))}
    frozen = []
    for value in (estimate, se, lower, stochastic, eligible):
        copy_value = np.ascontiguousarray(value).copy(); copy_value.setflags(write=False)
        frozen.append(copy_value)
    return RomanoWolfResult(frozen[0], frozen[1], frozen[2], critical, seed, resamples,
                            _digest(payload), ids, assets, families, map_hash,
                            frozen[3], frozen[4], column_states)


def e1_fit_count(real_probe_fits: int = 44, twin_probe_fits: int = 44,
                 shared_pretext_fits: int = 2) -> int:
    if (real_probe_fits, twin_probe_fits, shared_pretext_fits) != (44, 44, 2):
        raise AtlasStatisticsRefusal("E1 must contain exactly 44+44+2 fits")
    return 90


def through_e2_fit_count(finalist_count: int, *, base_e1_fits: int = 90) -> int:
    if base_e1_fits != 90 or not 0 <= finalist_count <= 4:
        raise AtlasStatisticsRefusal("E2 permits at most four real/twin finalist pairs")
    total = base_e1_fits + 2 * finalist_count
    if total > 98:
        raise AtlasStatisticsRefusal("hidden or extra optimizer fits detected")
    return total


@dataclass(frozen=True)
class FitLedgerRecord:
    fit_id: str
    category: str
    status: str
    artifact_sha256: str | None = None
    objective_id: str | None = None


@dataclass(frozen=True)
class FitLedgerReceipt:
    e1_registered_slots: int
    e1_optimizer_fits: int
    e2_registered_slots: int
    e2_optimizer_fits: int
    through_e2_optimizer_fits: int
    discarded_competence_fits: int
    unavailable_slots: int
    receipt_sha256: str


def validate_fit_ledger(records: Sequence[FitLedgerRecord], *,
                        finalist_count: int) -> FitLedgerReceipt:
    rows = tuple(records)
    if len({row.fit_id for row in rows}) != len(rows):
        raise AtlasStatisticsRefusal("fit ledger contains duplicate fit ids")
    allowed_categories = {
        "E1_PRETEXT", "E1_REAL", "E1_TWIN", "E2_REAL", "E2_TWIN", "COMPETENCE"
    }
    if any(row.category not in allowed_categories
           or row.status not in {"FIT", "UNAVAILABLE"} for row in rows):
        raise AtlasStatisticsRefusal("fit ledger category/status is invalid")
    if any(row.status == "FIT" and (row.artifact_sha256 is None
            or len(row.artifact_sha256) != 64) for row in rows):
        raise AtlasStatisticsRefusal("executed fit lacks its artifact hash")
    counts = {category: sum(row.category == category for row in rows)
              for category in allowed_categories}
    if (counts["E1_PRETEXT"], counts["E1_REAL"], counts["E1_TWIN"]) != (2, 44, 44):
        raise AtlasStatisticsRefusal("E1 ledger must register exactly 2+44+44 slots")
    pretexts = tuple(row for row in rows if row.category == "E1_PRETEXT")
    if (any(row.status != "FIT" for row in pretexts)
            or {row.objective_id for row in pretexts} != {"C01P01", "C02P01"}):
        raise AtlasStatisticsRefusal("both distinct E1 mixed-event pretext objectives must fit")
    if not 0 <= finalist_count <= 4 or counts["E2_REAL"] != finalist_count \
            or counts["E2_TWIN"] != finalist_count:
        raise AtlasStatisticsRefusal("E2 ledger does not match finalist/twin slots")
    e1 = tuple(row for row in rows if row.category.startswith("E1_"))
    e2 = tuple(row for row in rows if row.category.startswith("E2_"))
    competence = tuple(row for row in rows if row.category == "COMPETENCE")
    e1_fit = sum(row.status == "FIT" for row in e1)
    e2_fit = sum(row.status == "FIT" for row in e2)
    total = e1_fit + e2_fit
    if total > 98:
        raise AtlasStatisticsRefusal("through-E2 optimizer fit ceiling exceeded")
    unavailable = sum(row.status == "UNAVAILABLE" for row in (*e1, *e2))
    payload = {"records": [row.__dict__ for row in rows],
               "finalist_count": finalist_count, "e1_registered": len(e1),
               "e1_optimizer": e1_fit, "e2_registered": len(e2),
               "e2_optimizer": e2_fit, "through_e2_optimizer": total,
               "discarded_competence": sum(row.status == "FIT" for row in competence),
               "unavailable": unavailable}
    return FitLedgerReceipt(
        len(e1), e1_fit, len(e2), e2_fit, total,
        sum(row.status == "FIT" for row in competence), unavailable,
        _digest(payload),
    )


__all__ = [
    "AtlasStatisticsRefusal", "DEGENERATE_ZERO_VARIANCE", "EXACT_ASSETS",
    "FinalistSelectionResult",
    "FitLedgerReceipt", "FitLedgerRecord", "HierarchicalHolmResult",
    "PairedClusterResult", "PairedObservationRecord", "PairedTestState",
    "RomanoWolfResult", "STOCHASTIC",
    "SupportDecision", "SupportKind", "SupportState",
    "e1_fit_count", "hierarchical_holm", "holm_rejections",
    "holm_rejections_with_ledger",
    "nonredundant_finalists", "paired_day_cluster_records", "paired_day_cluster_test",
    "romano_wolf_lower_bounds", "support_gate", "through_e2_fit_count",
    "validate_fit_ledger",
]
