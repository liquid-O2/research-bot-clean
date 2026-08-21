"""No-model candidate-acceptance representation audit.

Acceptance is a cross-sectional question: among candidates visible in the
same asset-day, which retain useful value?  Treating every candidate as an
unrelated global row lets regime and clock baselines dominate.  This module
centres causal features and continuous candidate potential within asset-day,
screens directions across chronological FIT blocks, and tests the frozen
composite on PLATT against within-asset-day permutations.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final, Mapping

import numpy as np

from . import common as C
from .confirmation import ConfirmationDataset, ConfirmationRefusal
from .confirmation_fixed_horizon import (
    _average_ranks, _spearman, _stable_mask,
)
from .confirmation_stopping import OracleActionLedger


SCHEMA: Final = "QRE2CONFACCEPTMECHANISM1"
EXCLUDED_NAME_PARTS: Final = (
    "age_sec", "age_seconds", "elapsed", "remaining", "coverage",
    "min_alert_age", "max_alert_age",
)


@dataclass(frozen=True, slots=True)
class AcceptanceMechanismConfig:
    watch_age_sec: int = 30
    chronological_blocks: int = 3
    minimum_dynamic_group_fraction: float = .10
    stability_floors: tuple[float, ...] = (
        .005, .01, .015, .02, .03, .05,
    )
    strict_stability_floor: float = .05
    maximum_selected_features: int = 32
    control_replicates: int = 8
    control_seed: int = 20260821
    topk_values: tuple[int, ...] = (4, 6, 8, 12)
    minimum_platt_group_spearman: float = .05
    minimum_platt_positive_group_fraction: float = .65

    def __post_init__(self) -> None:
        floors = tuple(map(float, self.stability_floors))
        topk = tuple(map(int, self.topk_values))
        if (not 0 <= self.watch_age_sec < 300
                or not 2 <= self.chronological_blocks <= 6
                or not 0 < self.minimum_dynamic_group_fraction <= 1
                or floors != tuple(sorted(set(floors))) or not floors
                or self.strict_stability_floor not in floors
                or not 1 <= self.maximum_selected_features <= 128
                or not 1 <= self.control_replicates <= 32
                or topk != tuple(sorted(set(topk))) or not topk
                or topk[0] < 1 or topk[-1] > 12
                or not -1 <= self.minimum_platt_group_spearman <= 1
                or not 0 <= self.minimum_platt_positive_group_fraction <= 1):
            raise ConfirmationRefusal(
                "acceptance-mechanism configuration is invalid")

    @property
    def receipt_sha256(self) -> str:
        return C.object_sha256({"schema": SCHEMA, **asdict(self)})


def _validate(
    dataset: ConfirmationDataset, ledger: OracleActionLedger,
    *, watch_age_sec: int,
) -> None:
    dataset.validate(); ledger.validate()
    if (ledger.source_representation_sha256
            != dataset.representation_sha256
            or not np.array_equal(dataset.opportunity_id,
                                  ledger.opportunity_id)
            or not np.array_equal(dataset.series_id, ledger.series_id)
            or len(set(np.asarray(dataset.series_id, str).tolist()))
               != len(dataset.features)):
        raise ConfirmationRefusal(
            "acceptance-mechanism fixed-watch identity differs")
    age = np.asarray(dataset.max_alert_age_sec, np.float64)
    if np.any((age < watch_age_sec) | (age >= watch_age_sec + 1)):
        raise ConfirmationRefusal(
            "acceptance-mechanism row is not the exact watch boundary")


def acceptance_feature_indices(feature_names: tuple[str, ...]) -> np.ndarray:
    names = tuple(map(str, feature_names))
    selected = np.asarray([
        index for index, name in enumerate(names)
        if not any(part in name for part in EXCLUDED_NAME_PARTS)
    ], np.int64)
    if (not len(selected)
            or any(any(part in names[index] for part in EXCLUDED_NAME_PARTS)
                   for index in selected)):
        raise ConfirmationRefusal("acceptance feature exclusion differs")
    return selected


def asset_day_groups(dataset: ConfirmationDataset) -> np.ndarray:
    return np.asarray([
        f"{asset}:{int(day)}" for asset, day in zip(
            np.asarray(dataset.asset, str),
            np.asarray(dataset.day, np.int64))
    ], str)


def cross_section_matrix(
    dataset: ConfirmationDataset, feature_indices: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    selected = np.asarray(feature_indices, np.int64)
    # Several causal count/price features are large enough that subtracting a
    # cross-sectional mean in float32 leaves material residuals.  The centred
    # representation is a learned contract, so construct it in float64.
    matrix = np.asarray(dataset.features[:, selected], np.float64)
    result = np.empty_like(matrix)
    groups = asset_day_groups(dataset); dynamic = np.zeros(len(selected))
    for group in np.unique(groups):
        local = np.flatnonzero(groups == group)
        result[local] = matrix[local] - np.mean(matrix[local], axis=0)
        dynamic += np.ptp(matrix[local], axis=0) > 1e-7
    residual = np.vstack([
        np.mean(result[groups == group], axis=0)
        for group in np.unique(groups)])
    tolerance = 1e-10 * (1.0 + np.max(np.abs(result), axis=0))
    if np.any(np.abs(residual) > tolerance[None, :]):
        raise ConfirmationRefusal("acceptance cross-section did not centre")
    return result, dynamic / len(np.unique(groups))


def _group_centered_correlation(
    matrix: np.ndarray, target: np.ndarray, groups: np.ndarray,
    mask: np.ndarray,
) -> np.ndarray:
    indices = np.flatnonzero(mask)
    x = np.asarray(matrix[indices], np.float64).copy()
    y = np.asarray(target[indices], np.float64).copy()
    local_groups = groups[indices]
    for group in np.unique(local_groups):
        local = np.flatnonzero(local_groups == group)
        x[local] -= np.mean(x[local], axis=0)
        y[local] -= float(np.mean(y[local]))
    denominator = np.sqrt(np.sum(x * x, axis=0) * np.sum(y * y))
    return np.divide(
        x.T @ y, denominator, out=np.zeros(x.shape[1], np.float64),
        where=denominator > 0)


def _chronological_correlations(
    matrix: np.ndarray, target: np.ndarray, dataset: ConfirmationDataset,
    *, blocks: int,
) -> tuple[np.ndarray, tuple[tuple[int, ...], ...]]:
    days = np.unique(np.asarray(dataset.day, np.int64))
    if len(days) < blocks:
        raise ConfirmationRefusal("acceptance FIT calendar is too short")
    day_blocks = tuple(tuple(map(int, value.tolist()))
                       for value in np.array_split(days, blocks))
    groups = asset_day_groups(dataset)
    result = np.vstack([
        _group_centered_correlation(
            matrix, target, groups,
            np.isin(np.asarray(dataset.day, np.int64), block))
        for block in day_blocks
    ])
    return result, day_blocks


def shuffle_within_asset_day(
    dataset: ConfirmationDataset, target: np.ndarray, *, seed: int,
) -> np.ndarray:
    values = np.asarray(target, np.float64)
    if values.shape != (len(dataset.features),):
        raise ConfirmationRefusal("acceptance control target differs")
    groups = asset_day_groups(dataset); result = values.copy()
    rng = np.random.default_rng(seed); changed = 0
    for group in sorted(set(groups.tolist())):
        local = np.flatnonzero(groups == group)
        donor = values[local][rng.permutation(len(local))]
        result[local] = donor
        if not np.array_equal(np.sort(values[local]), np.sort(donor)):
            raise ConfirmationRefusal("acceptance control changed group mass")
        changed += int(np.sum(values[local] != donor))
    if not changed:
        raise ConfirmationRefusal("acceptance control changed no recipients")
    return result


def _group_metrics(
    score: np.ndarray, target: np.ndarray, dataset: ConfirmationDataset,
) -> Mapping[str, object]:
    groups = asset_day_groups(dataset); assets = np.asarray(dataset.asset, str)
    rows = []
    for group in sorted(set(groups.tolist())):
        local = np.flatnonzero(groups == group)
        correlation = _spearman(score[local], target[local])
        if correlation is not None:
            rows.append((group, str(assets[local[0]]), correlation))
    if not rows:
        raise ConfirmationRefusal("acceptance group metrics are empty")
    values = np.asarray([row[2] for row in rows], np.float64)
    row_assets = np.asarray([row[1] for row in rows], str)

    def summary(mask: np.ndarray) -> Mapping[str, object]:
        selected = values[mask]
        return {
            "groups": len(selected),
            "mean_spearman": float(np.mean(selected)),
            "median_spearman": float(np.median(selected)),
            "positive_group_fraction": float(np.mean(selected > 0.0)),
            "spearman_quantiles": tuple(float(value) for value in
                np.quantile(selected, (0, .1, .25, .5, .75, .9, 1))),
        }

    return {
        "overall": summary(np.ones(len(rows), bool)),
        "by_asset": {asset: summary(row_assets == asset)
                     for asset in sorted(set(row_assets.tolist()))},
    }


def _topk_capture(
    score: np.ndarray, target: np.ndarray, dataset: ConfirmationDataset,
    topk_values: tuple[int, ...],
) -> Mapping[str, object]:
    groups = asset_day_groups(dataset); ids = np.asarray(dataset.series_id, str)
    total_candidate_sum = float(np.sum(target)); result = {}
    for topk in topk_values:
        chosen = []; oracle = []
        for group in np.unique(groups):
            local = np.flatnonzero(groups == group)
            ordered = local[np.lexsort((ids[local], -score[local]))]
            chosen.extend(ordered[:topk].tolist())
            oracle_ordered = local[np.lexsort((
                ids[local], -target[local]))]
            oracle.extend(oracle_ordered[:topk].tolist())
        total = float(np.sum(target[np.asarray(chosen, np.int64)]))
        oracle_total = float(np.sum(target[np.asarray(oracle, np.int64)]))
        result[str(topk)] = {
            "selected_candidates": len(chosen),
            "candidate_local_potential_usd": total,
            "oracle_topk_candidate_local_potential_usd": oracle_total,
            "capture_of_oracle_topk_candidate_local_potential": (
                0.0 if oracle_total <= 0 else total / oracle_total),
            "share_of_all_candidate_local_potential": (
                0.0 if total_candidate_sum <= 0
                else total / total_candidate_sum),
            "not_schedule_economics": True,
        }
    return result


def run_acceptance_mechanism_audit(
    fit_dataset: ConfirmationDataset, fit_ledger: OracleActionLedger,
    platt_dataset: ConfirmationDataset, platt_ledger: OracleActionLedger, *,
    config: AcceptanceMechanismConfig = AcceptanceMechanismConfig(),
) -> Mapping[str, object]:
    _validate(fit_dataset, fit_ledger, watch_age_sec=config.watch_age_sec)
    _validate(platt_dataset, platt_ledger, watch_age_sec=config.watch_age_sec)
    if (fit_dataset.feature_names != platt_dataset.feature_names
            or int(np.max(fit_dataset.day)) >= int(np.min(platt_dataset.day))):
        raise ConfirmationRefusal("acceptance schema/chronology differs")
    allowed = acceptance_feature_indices(fit_dataset.feature_names)
    fit_matrix, dynamic_fraction = cross_section_matrix(fit_dataset, allowed)
    platt_matrix, _ = cross_section_matrix(platt_dataset, allowed)
    dynamic = dynamic_fraction >= config.minimum_dynamic_group_fraction
    allowed = allowed[dynamic]; dynamic_fraction = dynamic_fraction[dynamic]
    fit_matrix = fit_matrix[:, dynamic]; platt_matrix = platt_matrix[:, dynamic]
    names = np.asarray(fit_dataset.feature_names, str)[allowed]
    fit_target = np.asarray(fit_ledger.q_optimal_usd, np.float64)
    platt_target = np.asarray(platt_ledger.q_optimal_usd, np.float64)
    real_corr, day_blocks = _chronological_correlations(
        fit_matrix, fit_target, fit_dataset,
        blocks=config.chronological_blocks)
    stable_counts = {str(floor): int(np.sum(_stable_mask(real_corr, floor)))
                     for floor in config.stability_floors}
    controls = []
    for replicate in range(config.control_replicates):
        seed = config.control_seed + replicate
        shuffled = shuffle_within_asset_day(
            fit_dataset, fit_target, seed=seed)
        correlation, blocks = _chronological_correlations(
            fit_matrix, shuffled, fit_dataset,
            blocks=config.chronological_blocks)
        if blocks != day_blocks:
            raise ConfirmationRefusal("acceptance control chronology differs")
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
        raise ConfirmationRefusal("acceptance strict feature set is empty")
    strength = np.min(np.abs(real_corr[:, strict_indices]), axis=0)
    order = np.lexsort((names[strict_indices], -strength))
    selected = strict_indices[order[:config.maximum_selected_features]]
    direction = np.sign(np.mean(real_corr[:, selected], axis=0))
    scale = np.std(fit_matrix[:, selected], axis=0, dtype=np.float64)
    scale = np.where(scale > 1e-7, scale, 1.0)
    fit_score = np.sum(
        fit_matrix[:, selected] / scale * direction, axis=1
    ) / np.sqrt(len(selected))
    platt_score = np.sum(
        platt_matrix[:, selected] / scale * direction, axis=1
    ) / np.sqrt(len(selected))
    fit_metrics = _group_metrics(fit_score, fit_target, fit_dataset)
    platt_metrics = _group_metrics(platt_score, platt_target, platt_dataset)
    platt_corr = _group_centered_correlation(
        platt_matrix[:, selected], platt_target,
        asset_day_groups(platt_dataset),
        np.ones(len(platt_target), bool))
    control_max = {str(floor): max(
        row["stable_feature_counts"][str(floor)] for row in controls)
        for floor in config.stability_floors}
    pass_gate = bool(
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
    feature_ledger = []
    for local in np.argsort(-np.min(np.abs(real_corr), axis=0)):
        feature_ledger.append({
            "feature_name": str(names[local]),
            "source_column": int(allowed[local]),
            "dynamic_group_fraction": float(dynamic_fraction[local]),
            "fit_block_correlations": tuple(float(value)
                                             for value in real_corr[:, local]),
            "minimum_absolute_fit_correlation": float(
                np.min(np.abs(real_corr[:, local]))),
            "stable_at_strict_floor": bool(strict[local]),
        })
    core = {
        "schema": SCHEMA,
        "config": asdict(config), "config_sha256": config.receipt_sha256,
        "fit_dataset_sha256": fit_dataset.representation_sha256,
        "fit_ledger_sha256": fit_ledger.representation_sha256,
        "platt_dataset_sha256": platt_dataset.representation_sha256,
        "platt_ledger_sha256": platt_ledger.representation_sha256,
        "target": "CANDIDATE_LOCAL_Q_OPTIMAL_USD_AT_FIXED_WATCH",
        "representation": "WITHIN_ASSET_DAY_CENTERED_CAUSAL_FEATURES",
        "excluded_name_parts": EXCLUDED_NAME_PARTS,
        "allowed_features": len(acceptance_feature_indices(
            fit_dataset.feature_names)),
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
        "platt_topk_candidate_local_diagnostics": _topk_capture(
            platt_score, platt_target, platt_dataset, config.topk_values),
        "feature_ledger": tuple(feature_ledger),
        "mechanism_gate_pass": pass_gate,
        "models_executed": False,
        "economics_executed": False,
        "threshold_open_count": 0,
        "forward_open_count": 0,
        "h2_open_count": 0,
        "implementation_sha256": C.file_sha256(Path(__file__)),
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}
