"""Fixed-watch candidate value aligned with the causal stopping mechanism.

The old acceptance heads used either broad candidate ``Q_optimal`` or a
binary "ever viable" label.  Neither label prices the decision we actually
make after watching a candidate: enter at a fully observed fixed-horizon local
optimum, or pass.  This module derives one continuous non-negative dollar
target per candidate from exactly that action family and audits whether the
fixed-watch tabular representation orders it across candidates.

Rows whose path never contains a complete future horizon are explicitly
right-censored.  They are not converted into negative examples.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final, Mapping

import numpy as np

from . import common as C
from .confirmation import ConfirmationDataset, ConfirmationRefusal
from .confirmation_acceptance_mechanism import (
    _group_centered_correlation,
    acceptance_feature_indices,
    asset_day_groups,
    cross_section_matrix,
)
from .confirmation_fixed_horizon import (
    _spearman,
    _stable_mask,
    fixed_horizon_target,
    ordered_series_groups,
)
from .confirmation_stopping import OracleActionLedger


SCHEMA: Final = "QRE2CONFLAWFULVALUE1"


@dataclass(frozen=True, slots=True)
class LawfulValueConfig:
    watch_age_sec: int = 30
    horizon_sec: int = 120
    maximum_stop_regret_usd: float = 0.0
    chronological_blocks: int = 3
    minimum_dynamic_group_fraction: float = .10
    stability_floors: tuple[float, ...] = (
        .005, .01, .015, .02, .03, .05,
    )
    strict_stability_floor: float = .05
    maximum_selected_features: int = 128
    control_replicates: int = 8
    control_seed: int = 20260820
    topk_values: tuple[int, ...] = (4, 6, 8, 12)
    minimum_platt_group_spearman: float = .05
    minimum_platt_positive_group_fraction: float = .65

    def __post_init__(self) -> None:
        floors = tuple(map(float, self.stability_floors))
        topk = tuple(map(int, self.topk_values))
        if (not 0 <= self.watch_age_sec < 300
                or not 0 < self.horizon_sec <= 240
                or not 0.0 <= self.maximum_stop_regret_usd <= 250.0
                or not 2 <= self.chronological_blocks <= 6
                or not 0 < self.minimum_dynamic_group_fraction <= 1
                or floors != tuple(sorted(set(floors))) or not floors
                or floors[0] <= 0 or floors[-1] >= 1
                or self.strict_stability_floor not in floors
                or not 1 <= self.maximum_selected_features <= 256
                or not 1 <= self.control_replicates <= 32
                or topk != tuple(sorted(set(topk))) or not topk
                or topk[0] < 1 or topk[-1] > 24
                or not -1 <= self.minimum_platt_group_spearman <= 1
                or not 0 <= self.minimum_platt_positive_group_fraction <= 1):
            raise ConfirmationRefusal("lawful-value configuration is invalid")

    @property
    def receipt_sha256(self) -> str:
        return C.object_sha256({"schema": SCHEMA, **asdict(self)})


@dataclass(frozen=True, slots=True)
class CandidateLawfulValueTarget:
    value_usd: np.ndarray
    observed: np.ndarray
    best_snapshot_ts_ns: np.ndarray
    horizon_sec: int
    maximum_stop_regret_usd: float

    def validate(self, fixed_dataset: ConfirmationDataset) -> None:
        n = len(fixed_dataset.features)
        value = np.asarray(self.value_usd, np.float64)
        observed = np.asarray(self.observed, bool)
        timestamp = np.asarray(self.best_snapshot_ts_ns, np.int64)
        if (value.shape != (n,) or observed.shape != (n,)
                or timestamp.shape != (n,)
                or not 0 < self.horizon_sec <= 240
                or not 0 <= self.maximum_stop_regret_usd <= 250
                or not observed.any()
                or not np.all(np.isfinite(value[observed]))
                or np.any(value[observed] < 0.0)
                or np.any(np.isfinite(value[~observed]))
                or np.any(timestamp[~observed] != -1)
                or np.any(timestamp[observed & (value > 0.0)] < 0)):
            raise ConfirmationRefusal("lawful candidate-value target differs")


def _fixed_watch_identity(
    conditional: ConfirmationDataset, fixed: ConfirmationDataset, *,
    watch_age_sec: int,
) -> tuple[tuple[np.ndarray, ...], Mapping[str, int]]:
    conditional.validate(); fixed.validate()
    fixed_series = np.asarray(fixed.series_id, str)
    if (len(set(fixed_series.tolist())) != len(fixed_series)
            or np.any(np.asarray(fixed.min_alert_age_sec, np.float64)
                      < watch_age_sec)
            or np.any(np.asarray(fixed.min_alert_age_sec, np.float64)
                      >= watch_age_sec + 1)):
        raise ConfirmationRefusal("lawful-value fixed watch identity differs")
    groups = ordered_series_groups(
        conditional.series_id, conditional.snapshot_ts_ns)
    conditional_series = np.asarray(conditional.series_id, str)
    fixed_lookup = {value: index for index, value in enumerate(fixed_series)}
    if set(fixed_lookup) != set(conditional_series.tolist()):
        raise ConfirmationRefusal("lawful-value candidate roster differs")
    conditional_ts = np.asarray(conditional.snapshot_ts_ns, np.int64)
    fixed_ts = np.asarray(fixed.snapshot_ts_ns, np.int64)
    conditional_opp = np.asarray(conditional.opportunity_id, str)
    fixed_opp = np.asarray(fixed.opportunity_id, str)
    for ordered in groups:
        first = int(ordered[0]); index = fixed_lookup[str(conditional_series[first])]
        if (conditional_ts[first] != fixed_ts[index]
                or conditional_opp[first] != fixed_opp[index]):
            raise ConfirmationRefusal("lawful-value watch anchor differs")
    return groups, fixed_lookup


def candidate_lawful_value_target(
    conditional: ConfirmationDataset, ledger: OracleActionLedger,
    fixed: ConfirmationDataset, *, horizon_sec: int = 120,
    maximum_stop_regret_usd: float = 0.0, watch_age_sec: int = 30,
) -> CandidateLawfulValueTarget:
    """Best reachable fixed-horizon entry value for each watched candidate."""

    ledger.validate()
    if (ledger.source_representation_sha256
            != conditional.representation_sha256
            or not np.array_equal(ledger.opportunity_id,
                                  conditional.opportunity_id)):
        raise ConfirmationRefusal("lawful-value ledger identity differs")
    groups, fixed_lookup = _fixed_watch_identity(
        conditional, fixed, watch_age_sec=watch_age_sec)
    horizon = fixed_horizon_target(conditional, ledger, int(horizon_sec))
    regret = float(maximum_stop_regret_usd)
    n = len(fixed.features)
    value = np.full(n, np.nan, np.float64)
    observed = np.zeros(n, bool)
    best_timestamp = np.full(n, -1, np.int64)
    series = np.asarray(conditional.series_id, str)
    q_enter = np.asarray(ledger.q_enter_usd, np.float64)
    timestamp = np.asarray(conditional.snapshot_ts_ns, np.int64)
    for ordered in groups:
        fixed_index = fixed_lookup[str(series[ordered[0]])]
        eligible = np.asarray(horizon.eligible[ordered], bool)
        if not eligible.any():
            continue
        observed[fixed_index] = True
        admissible = eligible & (
            np.asarray(horizon.stop_utility_usd[ordered], np.float64)
            >= -regret)
        if not admissible.any():
            value[fixed_index] = 0.0
            continue
        candidates = ordered[np.flatnonzero(admissible)]
        # np.argmax is deterministic and selects the earliest ordered row on
        # exact dollar ties, matching a causal first-opportunity preference.
        chosen = int(candidates[int(np.argmax(q_enter[candidates]))])
        value[fixed_index] = max(0.0, float(q_enter[chosen]))
        best_timestamp[fixed_index] = int(timestamp[chosen])
    result = CandidateLawfulValueTarget(
        value_usd=value, observed=observed,
        best_snapshot_ts_ns=best_timestamp, horizon_sec=int(horizon_sec),
        maximum_stop_regret_usd=regret)
    result.validate(fixed)
    return result


def shuffle_observed_within_asset_day(
    dataset: ConfirmationDataset, target: CandidateLawfulValueTarget, *,
    seed: int,
) -> np.ndarray:
    """Shuffle only labelled candidates and preserve censoring/group mass."""

    target.validate(dataset)
    values = np.asarray(target.value_usd, np.float64)
    observed = np.asarray(target.observed, bool)
    result = values.copy(); groups = asset_day_groups(dataset)
    rng = np.random.default_rng(int(seed)); changed = 0
    for group in sorted(set(groups[observed].tolist())):
        local = np.flatnonzero(observed & (groups == group))
        if len(local) < 2:
            continue
        donor = values[local][rng.permutation(len(local))]
        result[local] = donor
        if not np.array_equal(np.sort(values[local]), np.sort(donor)):
            raise ConfirmationRefusal("lawful-value control changed group mass")
        changed += int(np.sum(values[local] != donor))
    if not changed or not np.array_equal(np.isnan(result), ~observed):
        raise ConfirmationRefusal("lawful-value control changed no recipients")
    return result


def _chronological_correlations(
    matrix: np.ndarray, target: np.ndarray, observed: np.ndarray,
    dataset: ConfirmationDataset, *, blocks: int,
) -> tuple[np.ndarray, tuple[tuple[int, ...], ...]]:
    days = np.unique(np.asarray(dataset.day, np.int64)[observed])
    if len(days) < blocks:
        raise ConfirmationRefusal("lawful-value FIT calendar is too short")
    day_blocks = tuple(tuple(map(int, block.tolist()))
                       for block in np.array_split(days, blocks))
    groups = asset_day_groups(dataset)
    result = np.vstack([
        _group_centered_correlation(
            matrix, target, groups,
            np.asarray(observed, bool)
            & np.isin(np.asarray(dataset.day, np.int64), block))
        for block in day_blocks
    ])
    return result, day_blocks


def _group_metrics(
    score: np.ndarray, target: CandidateLawfulValueTarget,
    dataset: ConfirmationDataset,
) -> Mapping[str, object]:
    values = np.asarray(target.value_usd, np.float64)
    observed = np.asarray(target.observed, bool)
    groups = asset_day_groups(dataset); assets = np.asarray(dataset.asset, str)
    rows = []
    for group in sorted(set(groups[observed].tolist())):
        local = np.flatnonzero(observed & (groups == group))
        correlation = _spearman(score[local], values[local])
        if correlation is not None:
            rows.append((group, str(assets[local[0]]), correlation))
    if not rows:
        raise ConfirmationRefusal("lawful-value group metrics are empty")
    correlations = np.asarray([row[2] for row in rows], np.float64)
    row_assets = np.asarray([row[1] for row in rows], str)

    def summarize(mask: np.ndarray) -> Mapping[str, object]:
        selected = correlations[mask]
        return {
            "groups": len(selected),
            "mean_spearman": float(np.mean(selected)),
            "median_spearman": float(np.median(selected)),
            "positive_group_fraction": float(np.mean(selected > 0.0)),
            "spearman_quantiles": tuple(float(value) for value in
                np.quantile(selected, (0, .1, .25, .5, .75, .9, 1))),
        }

    return {
        "overall": summarize(np.ones(len(rows), bool)),
        "by_asset": {asset: summarize(row_assets == asset)
                     for asset in sorted(set(row_assets.tolist()))},
    }


def _topk_capture(
    score: np.ndarray, target: CandidateLawfulValueTarget,
    dataset: ConfirmationDataset, topk_values: tuple[int, ...],
) -> Mapping[str, object]:
    values = np.asarray(target.value_usd, np.float64)
    observed = np.asarray(target.observed, bool)
    groups = asset_day_groups(dataset); ids = np.asarray(dataset.series_id, str)
    result = {}
    for topk in topk_values:
        chosen = []; oracle = []
        for group in sorted(set(groups[observed].tolist())):
            local = np.flatnonzero(observed & (groups == group))
            chosen.extend(local[np.lexsort((ids[local], -score[local]))]
                          [:topk].tolist())
            oracle.extend(local[np.lexsort((ids[local], -values[local]))]
                          [:topk].tolist())
        chosen_value = float(np.sum(values[np.asarray(chosen, np.int64)]))
        oracle_value = float(np.sum(values[np.asarray(oracle, np.int64)]))
        result[str(topk)] = {
            "selected_candidates": len(chosen),
            "selected_lawful_value_usd": chosen_value,
            "oracle_topk_lawful_value_usd": oracle_value,
            "capture_of_oracle_topk_lawful_value": (
                0.0 if oracle_value <= 0 else chosen_value / oracle_value),
            "not_schedule_economics": True,
        }
    return result


def _target_summary(
    target: CandidateLawfulValueTarget, dataset: ConfirmationDataset,
) -> Mapping[str, object]:
    observed = np.asarray(target.observed, bool)
    value = np.asarray(target.value_usd, np.float64)[observed]
    assets = np.asarray(dataset.asset, str)[observed]

    def summarize(mask: np.ndarray) -> Mapping[str, object]:
        selected = value[mask]
        return {
            "observed_candidates": len(selected),
            "positive_candidates": int(np.sum(selected > 0.0)),
            "positive_fraction": float(np.mean(selected > 0.0)),
            "total_lawful_value_usd": float(np.sum(selected)),
            "value_quantiles_usd": tuple(float(item) for item in
                np.quantile(selected, (0, .25, .5, .75, .9, .95, .99, 1))),
        }

    return {
        "overall": {
            **summarize(np.ones(len(value), bool)),
            "right_censored_candidates": int(np.sum(~observed)),
        },
        "by_asset": {asset: summarize(assets == asset)
                     for asset in sorted(set(assets.tolist()))},
    }


def run_lawful_value_audit(
    fit_conditional: ConfirmationDataset, fit_ledger: OracleActionLedger,
    fit_fixed: ConfirmationDataset,
    platt_conditional: ConfirmationDataset, platt_ledger: OracleActionLedger,
    platt_fixed: ConfirmationDataset, *,
    config: LawfulValueConfig = LawfulValueConfig(),
) -> Mapping[str, object]:
    """Audit continuous action-aligned candidate value before model fitting."""

    if (fit_fixed.feature_names != platt_fixed.feature_names
            or int(np.max(fit_fixed.day)) >= int(np.min(platt_fixed.day))):
        raise ConfirmationRefusal("lawful-value schema/chronology differs")
    targets = {
        "FIT": candidate_lawful_value_target(
            fit_conditional, fit_ledger, fit_fixed,
            horizon_sec=config.horizon_sec,
            maximum_stop_regret_usd=config.maximum_stop_regret_usd,
            watch_age_sec=config.watch_age_sec),
        "PLATT": candidate_lawful_value_target(
            platt_conditional, platt_ledger, platt_fixed,
            horizon_sec=config.horizon_sec,
            maximum_stop_regret_usd=config.maximum_stop_regret_usd,
            watch_age_sec=config.watch_age_sec),
    }
    datasets = {"FIT": fit_fixed, "PLATT": platt_fixed}
    allowed = acceptance_feature_indices(fit_fixed.feature_names)
    fit_matrix, dynamic_fraction = cross_section_matrix(fit_fixed, allowed)
    platt_matrix, _ = cross_section_matrix(platt_fixed, allowed)
    dynamic = dynamic_fraction >= config.minimum_dynamic_group_fraction
    allowed = allowed[dynamic]; dynamic_fraction = dynamic_fraction[dynamic]
    fit_matrix = fit_matrix[:, dynamic]; platt_matrix = platt_matrix[:, dynamic]
    names = np.asarray(fit_fixed.feature_names, str)[allowed]
    fit_values = np.asarray(targets["FIT"].value_usd, np.float64)
    fit_observed = np.asarray(targets["FIT"].observed, bool)
    real_corr, day_blocks = _chronological_correlations(
        fit_matrix, fit_values, fit_observed, fit_fixed,
        blocks=config.chronological_blocks)
    stable_counts = {str(floor): int(np.sum(_stable_mask(real_corr, floor)))
                     for floor in config.stability_floors}
    controls = []
    for replicate in range(config.control_replicates):
        seed = config.control_seed + replicate
        shuffled = shuffle_observed_within_asset_day(
            fit_fixed, targets["FIT"], seed=seed)
        correlation, blocks = _chronological_correlations(
            fit_matrix, shuffled, fit_observed, fit_fixed,
            blocks=config.chronological_blocks)
        if blocks != day_blocks:
            raise ConfirmationRefusal("lawful-value control chronology differs")
        row = {
            "replicate": replicate + 1, "seed": seed,
            "stable_feature_counts": {
                str(floor): int(np.sum(_stable_mask(correlation, floor)))
                for floor in config.stability_floors},
        }
        controls.append({**row, "receipt_sha256": C.object_sha256(row)})
    strict = _stable_mask(real_corr, config.strict_stability_floor)
    strict_indices = np.flatnonzero(strict)
    if not len(strict_indices):
        raise ConfirmationRefusal("lawful-value strict feature set is empty")
    strength = np.min(np.abs(real_corr[:, strict_indices]), axis=0)
    order = np.lexsort((names[strict_indices], -strength))
    selected = strict_indices[order[:config.maximum_selected_features]]
    direction = np.sign(np.mean(real_corr[:, selected], axis=0))
    scale = np.std(fit_matrix[fit_observed][:, selected], axis=0,
                   dtype=np.float64)
    scale = np.where(scale > 1e-7, scale, 1.0)
    fit_score = np.sum(
        fit_matrix[:, selected] / scale * direction, axis=1
    ) / np.sqrt(len(selected))
    platt_score = np.sum(
        platt_matrix[:, selected] / scale * direction, axis=1
    ) / np.sqrt(len(selected))
    fit_metrics = _group_metrics(fit_score, targets["FIT"], fit_fixed)
    platt_metrics = _group_metrics(platt_score, targets["PLATT"], platt_fixed)
    platt_corr = _group_centered_correlation(
        platt_matrix[:, selected], targets["PLATT"].value_usd,
        asset_day_groups(platt_fixed), targets["PLATT"].observed)
    control_max = {str(floor): max(
        row["stable_feature_counts"][str(floor)] for row in controls)
        for floor in config.stability_floors}
    gate = bool(
        stable_counts[str(config.strict_stability_floor)]
        > control_max[str(config.strict_stability_floor)]
        and platt_metrics["overall"]["mean_spearman"]
        >= config.minimum_platt_group_spearman
        and platt_metrics["overall"]["positive_group_fraction"]
        >= config.minimum_platt_positive_group_fraction)
    selected_transform = tuple({
        "feature_name": str(names[local]),
        "source_column": int(allowed[local]),
        "direction": int(direction[position]),
        "fit_scale": float(scale[position]),
    } for position, local in enumerate(selected))
    feature_ledger = tuple({
        "feature_name": str(names[local]),
        "source_column": int(allowed[local]),
        "dynamic_group_fraction": float(dynamic_fraction[local]),
        "fit_block_correlations": tuple(float(value)
                                         for value in real_corr[:, local]),
        "minimum_absolute_fit_correlation": float(
            np.min(np.abs(real_corr[:, local]))),
        "stable_at_strict_floor": bool(strict[local]),
    } for local in np.argsort(-np.min(np.abs(real_corr), axis=0)))
    core = {
        "schema": SCHEMA,
        "config": asdict(config), "config_sha256": config.receipt_sha256,
        "target": "BEST_NONNEGATIVE_Q_ENTER_AT_FULLY_OBSERVED_FIXED_HORIZON_LOCAL_OPTIMUM",
        "target_units": "USD",
        "right_censoring": "NO_EXACT_HORIZON_ROW_EXCLUDED_NOT_NEGATIVE",
        "fit_conditional_sha256": fit_conditional.representation_sha256,
        "fit_ledger_sha256": fit_ledger.representation_sha256,
        "fit_fixed_sha256": fit_fixed.representation_sha256,
        "platt_conditional_sha256": platt_conditional.representation_sha256,
        "platt_ledger_sha256": platt_ledger.representation_sha256,
        "platt_fixed_sha256": platt_fixed.representation_sha256,
        "representation": "WITHIN_ASSET_DAY_CENTERED_FIXED_WATCH_CAUSAL_FEATURES",
        "target_summaries": {
            role: _target_summary(targets[role], datasets[role])
            for role in ("FIT", "PLATT")},
        "allowed_features": len(acceptance_feature_indices(
            fit_fixed.feature_names)),
        "dynamic_features": len(allowed),
        "chronological_fit_day_blocks": day_blocks,
        "stable_feature_counts": stable_counts,
        "control_replicates": tuple(controls),
        "maximum_control_stable_feature_counts": control_max,
        "selected_feature_names": tuple(map(str, names[selected].tolist())),
        "selected_feature_transform": selected_transform,
        "selected_features": len(selected),
        "selected_platt_direction_agreement_fraction": float(np.mean(
            np.sign(platt_corr) == direction)),
        "fit_group_metrics": fit_metrics,
        "platt_group_metrics": platt_metrics,
        "platt_topk_lawful_value_diagnostics": _topk_capture(
            platt_score, targets["PLATT"], platt_fixed, config.topk_values),
        "feature_ledger": feature_ledger,
        "mechanism_gate_pass": gate,
        "models_executed": False,
        "economics_executed": False,
        "threshold_open_count": 0,
        "forward_open_count": 0,
        "h2_open_count": 0,
        "implementation_sha256": C.file_sha256(Path(__file__)),
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


__all__ = [
    "SCHEMA", "CandidateLawfulValueTarget", "LawfulValueConfig",
    "candidate_lawful_value_target", "run_lawful_value_audit",
    "shuffle_observed_within_asset_day",
]
