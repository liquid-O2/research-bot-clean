"""Cheap FIT-only ranker for zero-preserving delayed path acceptance."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Final, Mapping, Sequence

import catboost
from catboost import CatBoostRanker, Pool
import numpy as np

from . import common as C
from .confirmation import ConfirmationRefusal
from .confirmation_acceptance_mechanism import asset_day_groups
from .confirmation_lawful_value import shuffle_observed_within_asset_day
from .confirmation_lawful_value_model import lawful_value_rank_diagnostic
from .confirmation_path_state import PathStateLandmark


SCHEMA: Final = "QRE2CONFPATHSTATERANK2"
OOF_SCHEMA: Final = "QRE2CONFPATHSTATEOOF1"
SHORTCUT_FEATURES: Final = frozenset({
    "pathstate_phase_index", "pathstate_landmark_delay_sec",
})


@dataclass(frozen=True, slots=True)
class PathStateRankConfig:
    capacity: int = 3
    minimum_train_days: int = 12
    validation_days: int = 6
    fold_count: int = 3
    rolling_train_days: int = 12
    iterations: int = 120
    depth: int = 5
    learning_rate: float = .04
    l2_leaf_reg: float = 20.0
    minimum_dynamic_group_fraction: float = .10
    random_seed: int = 20260820
    thread_count: int = 16
    minimum_oof_capture_gain: float = .03
    minimum_oof_spearman_gain: float = .02
    objective_variant: str = "SIGNED_ORDER"

    def __post_init__(self) -> None:
        if (not 1 <= self.capacity <= 24
                or not 6 <= self.minimum_train_days <= 60
                or not 2 <= self.validation_days <= 20
                or not 1 <= self.fold_count <= 6
                or not self.minimum_train_days <= self.rolling_train_days <= 30
                or not 20 <= self.iterations <= 500
                or not 3 <= self.depth <= 8
                or not 0 < self.learning_rate <= .3
                or not 0 < self.l2_leaf_reg <= 1_000
                or not 0 < self.minimum_dynamic_group_fraction <= 1
                or not 1 <= self.thread_count <= C.MAX_CPU_WORKERS
                or not -1 <= self.minimum_oof_capture_gain <= 1
                or not -1 <= self.minimum_oof_spearman_gain <= 1
                or self.objective_variant not in {
                    "SIGNED_ORDER",
                    "ORDINAL_POSITIVE_TOP3",
                    "QUERY_SOFTMAX_POSITIVE_UTILITY",
                }):
            raise ConfirmationRefusal("path-state rank configuration invalid")

    @property
    def receipt_sha256(self) -> str:
        return C.object_sha256({"schema": SCHEMA, **asdict(self)})


@dataclass(frozen=True, slots=True)
class PathStateRankModels:
    real: CatBoostRanker
    control: CatBoostRanker
    selected_indices: tuple[int, ...]
    selected_feature_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PathStateOofScores:
    real: np.ndarray
    control: np.ndarray
    mask: np.ndarray
    selected_indices: tuple[int, ...]
    selected_feature_names: tuple[str, ...]


def cross_section_state_matrix(
    landmark: PathStateLandmark,
) -> tuple[np.ndarray, np.ndarray]:
    """Centre only within the simultaneous asset-day decision set."""

    matrix = np.asarray(landmark.matrix, np.float64)
    groups = asset_day_groups(landmark.dataset)
    result = np.empty_like(matrix); dynamic = np.zeros(matrix.shape[1])
    for group in np.unique(groups):
        local = np.flatnonzero(groups == group)
        result[local] = matrix[local] - np.mean(matrix[local], axis=0)
        dynamic += np.ptp(matrix[local], axis=0) > 1e-7
    residual = np.vstack([
        np.mean(result[groups == group], axis=0)
        for group in np.unique(groups)])
    tolerance = 1e-10 * (1.0 + np.max(np.abs(result), axis=0))
    if np.any(np.abs(residual) > tolerance[None, :]):
        raise ConfirmationRefusal("path-state cross-section did not centre")
    return result, dynamic / len(np.unique(groups))


def _folds(
    landmark: PathStateLandmark, config: PathStateRankConfig,
) -> tuple[Mapping[str, object], ...]:
    days = np.unique(np.asarray(landmark.dataset.day, np.int64))
    required = (config.minimum_train_days
                + config.validation_days * config.fold_count)
    if len(days) != required:
        raise ConfirmationRefusal("path-state FIT calendar differs")
    return tuple({
        "fold": ordinal + 1,
        "train_days": tuple(map(int, days[max(
            0, config.minimum_train_days + ordinal * config.validation_days
            - config.rolling_train_days):
            config.minimum_train_days + ordinal * config.validation_days])),
        "validation_days": tuple(map(int, days[
            config.minimum_train_days + ordinal * config.validation_days:
            config.minimum_train_days + (ordinal + 1)
            * config.validation_days])),
    } for ordinal in range(config.fold_count))


def _pool(
    matrix: np.ndarray, values: np.ndarray, landmark: PathStateLandmark,
    *, population: np.ndarray, days: Sequence[int] | None = None,
) -> Pool:
    mask = np.asarray(population, bool).copy()
    if mask.shape != (len(matrix),) or not mask.any():
        raise ConfirmationRefusal("path-state rank population differs")
    if days is not None:
        mask &= np.isin(np.asarray(landmark.dataset.day, np.int64),
                        np.asarray(tuple(days), np.int64))
    indices = np.flatnonzero(mask)
    groups = asset_day_groups(landmark.dataset)
    series = np.asarray(landmark.dataset.series_id, str)
    order = np.lexsort((series[indices], groups[indices]))
    indices = indices[order]; ordered_groups = groups[indices]
    if (not len(indices) or not np.all(np.isfinite(values[indices]))
            or np.any(ordered_groups[1:] < ordered_groups[:-1])):
        raise ConfirmationRefusal("path-state rank pool differs")
    return Pool(matrix[indices], label=values[indices],
                group_id=ordered_groups.tolist())


def _group_shifted_relevance(
    values: np.ndarray, landmark: PathStateLandmark, population: np.ndarray,
) -> np.ndarray:
    """Make signed dollars legal for YetiRank without changing query order."""

    source = np.asarray(values, np.float64)
    result = source.copy(); groups = asset_day_groups(landmark.dataset)
    use = np.asarray(population, bool)
    for group in np.unique(groups[use]):
        local = use & (groups == group)
        result[local] = source[local] - float(np.min(source[local]))
    if (not np.all(np.isfinite(result)) or np.any(result[use] < 0.0)):
        raise ConfirmationRefusal("path-state signed relevance transform differs")
    return result


def _objective_relevance(
    values: np.ndarray, landmark: PathStateLandmark, population: np.ndarray,
    config: PathStateRankConfig,
) -> np.ndarray:
    """Encode the choice contract without ordering noisy losing dollars."""

    source = np.asarray(values, np.float64)
    use = np.asarray(population, bool)
    if config.objective_variant == "SIGNED_ORDER":
        return _group_shifted_relevance(source, landmark, use)
    if config.objective_variant == "QUERY_SOFTMAX_POSITIVE_UTILITY":
        result = np.zeros_like(source)
        result[use] = np.log1p(np.maximum(source[use], 0.0) / 25.0)
        if not np.all(np.isfinite(result)):
            raise ConfirmationRefusal(
                "path-state positive utility relevance differs")
        return result

    # The deployment decision is top-capacity acceptance, not a total order
    # over every pair of noisy signed dollar outcomes.  Preserve only the
    # positive top-k choice and give all non-selected candidates relevance 0.
    result = np.zeros_like(source)
    groups = asset_day_groups(landmark.dataset)
    series = np.asarray(landmark.dataset.series_id, str)
    positive_count = 0
    for group in np.unique(groups[use]):
        local = np.flatnonzero(use & (groups == group) & (source > 0.0))
        if not len(local):
            continue
        order = np.lexsort((series[local], -source[local]))
        chosen = local[order[:config.capacity]]
        result[chosen] = np.arange(
            config.capacity, config.capacity - len(chosen), -1,
            dtype=np.float64)
        positive_count += len(chosen)
    if (not positive_count or not np.all(np.isfinite(result))
            or np.any(result < 0.0)):
        raise ConfirmationRefusal("path-state ordinal relevance differs")
    return result


def _shuffle_within_population(
    values: np.ndarray, landmark: PathStateLandmark,
    population: np.ndarray, *, seed: int,
) -> np.ndarray:
    source = np.asarray(values, np.float64)
    use = np.asarray(population, bool)
    groups = asset_day_groups(landmark.dataset); result = source.copy()
    rng = np.random.default_rng(int(seed)); changed = 0
    for group in sorted(set(groups[use].tolist())):
        local = np.flatnonzero(use & (groups == group))
        donor = source[local][rng.permutation(len(local))]
        result[local] = donor
        changed += int(np.sum(source[local] != donor))
    if not changed:
        raise ConfirmationRefusal("path-state roster control changed no labels")
    return result


def _population_dynamic_fraction(
    landmark: PathStateLandmark, population: np.ndarray,
) -> np.ndarray:
    matrix = np.asarray(landmark.matrix, np.float64)
    groups = asset_day_groups(landmark.dataset)
    use = np.asarray(population, bool); dynamic = np.zeros(matrix.shape[1])
    unique = np.unique(groups[use])
    for group in unique:
        local = use & (groups == group)
        dynamic += np.ptp(matrix[local], axis=0) > 1e-7
    return dynamic / len(unique)


def _selected_state_matrix(
    landmark: PathStateLandmark, population: np.ndarray,
    config: PathStateRankConfig,
) -> tuple[np.ndarray, np.ndarray, tuple[str, ...]]:
    dynamic = _population_dynamic_fraction(landmark, population)
    selected = np.flatnonzero(
        (dynamic >= config.minimum_dynamic_group_fraction)
        & ~np.isin(np.asarray(landmark.feature_names, str),
                    tuple(SHORTCUT_FEATURES)))
    if not len(selected):
        raise ConfirmationRefusal("path-state dynamic matrix is empty")
    matrix = np.asarray(landmark.matrix[:, selected], np.float32)
    names = tuple(np.asarray(
        landmark.feature_names, str)[selected].tolist())
    return matrix, selected, names


def _fit(pool: Pool, config: PathStateRankConfig, *, seed: int) \
        -> CatBoostRanker:
    loss_function = (
        "QuerySoftMax"
        if config.objective_variant == "QUERY_SOFTMAX_POSITIVE_UTILITY"
        else f"YetiRankPairwise:mode=NDCG;top={config.capacity}"
    )
    model = CatBoostRanker(
        loss_function=loss_function,
        iterations=config.iterations, depth=config.depth,
        learning_rate=config.learning_rate, l2_leaf_reg=config.l2_leaf_reg,
        random_seed=int(seed), thread_count=config.thread_count,
        allow_writing_files=False, verbose=False)
    model.fit(pool, verbose=False)
    if int(model.tree_count_) != config.iterations:
        raise ConfirmationRefusal("path-state rank tree count differs")
    return model


def _roster_mask(
    landmark: PathStateLandmark, roster: Sequence[str],
) -> np.ndarray:
    values = tuple(map(str, roster))
    mask = np.isin(np.asarray(landmark.dataset.series_id, str), values)
    if not mask.any() or len(set(values)) != len(values):
        raise ConfirmationRefusal("path-state learned roster differs")
    return mask


def fit_path_state_oof_scores(
    fit: PathStateLandmark, *, fit_roster: Sequence[str],
    config: PathStateRankConfig = PathStateRankConfig(),
) -> tuple[PathStateOofScores, Mapping[str, object]]:
    """Fit chronological FIT folds without reading any later role."""

    fit_roster_mask = _roster_mask(fit, fit_roster)
    fit_matrix, selected, selected_names = _selected_state_matrix(
        fit, fit_roster_mask, config)
    fit_values = np.asarray(fit.target.value_usd, np.float64)
    control_values = _shuffle_within_population(
        fit_values, fit, fit_roster_mask, seed=config.random_seed + 10_000)
    fit_relevance = _objective_relevance(
        fit_values, fit, fit_roster_mask, config)
    control_relevance = _objective_relevance(
        control_values, fit, fit_roster_mask, config)
    oof_real = np.zeros(len(fit_matrix), np.float64)
    oof_control = np.zeros(len(fit_matrix), np.float64)
    oof_mask = np.zeros(len(fit_matrix), bool)
    fold_rows = []
    for fold in _folds(fit, config):
        ordinal = int(fold["fold"])
        real = _fit(_pool(
            fit_matrix, fit_relevance, fit, population=fit_roster_mask,
            days=fold["train_days"]), config,
            seed=config.random_seed + 100 * ordinal)
        control = _fit(_pool(
            fit_matrix, control_relevance, fit, population=fit_roster_mask,
            days=fold["train_days"]), config,
            seed=config.random_seed + 100 * ordinal)
        valid = np.isin(np.asarray(fit.dataset.day, np.int64),
                        np.asarray(fold["validation_days"], np.int64))
        oof_real[valid] = np.asarray(
            real.predict(fit_matrix[valid]), np.float64)
        oof_control[valid] = np.asarray(
            control.predict(fit_matrix[valid]), np.float64)
        oof_mask |= valid
        fold_rows.append({
            **fold,
            "real_roster": lawful_value_rank_diagnostic(
                oof_real, fit.target, fit.dataset, capacity=config.capacity,
                mask=valid & fit_roster_mask),
            "control_roster": lawful_value_rank_diagnostic(
                oof_control, fit.target, fit.dataset, capacity=config.capacity,
                mask=valid & fit_roster_mask),
        })
    if (np.any(~np.isfinite(oof_real[oof_mask]))
            or np.any(~np.isfinite(oof_control[oof_mask]))):
        raise ConfirmationRefusal("path-state OOF prediction incomplete")
    real_diag = lawful_value_rank_diagnostic(
        oof_real, fit.target, fit.dataset, capacity=config.capacity,
        mask=oof_mask & fit_roster_mask)
    control_diag = lawful_value_rank_diagnostic(
        oof_control, fit.target, fit.dataset, capacity=config.capacity,
        mask=oof_mask & fit_roster_mask)
    fold_capture_wins = tuple(
        float(row["real_roster"]["top_capacity_lawful_value_capture"])
        > float(row["control_roster"]["top_capacity_lawful_value_capture"])
        for row in fold_rows)
    core = {
        "schema": OOF_SCHEMA, "config": asdict(config),
        "config_sha256": config.receipt_sha256,
        "catboost_version": catboost.__version__,
        "target": "SIGNED_BEST_FULLY_OBSERVED_DELAYED_ENTRY_VALUE",
        "objective_label_transform": config.objective_variant,
        "training_population": "FROZEN_LEARNED_TOP12_ROSTER",
        "evaluation_role": "FIT_CHRONOLOGICAL_OOF_ONLY",
        "selected_dynamic_features": len(selected),
        "selected_indices": tuple(map(int, selected.tolist())),
        "selected_feature_names": selected_names,
        "fit_candidates": int(np.sum(fit_roster_mask)),
        "fit_positive_candidates": int(np.sum(
            (fit_values > 0.0) & fit_roster_mask)),
        "chronological_folds": tuple(fold_rows),
        "fit_oof_real_roster": real_diag,
        "fit_oof_control_roster": control_diag,
        "fold_capture_wins": fold_capture_wins,
        "all_fold_capture_wins": all(fold_capture_wins),
        "platt_open_count": 0, "threshold_open_count": 0,
        "forward_open_count": 0, "h2_open_count": 0,
    }
    scores = PathStateOofScores(
        real=oof_real, control=oof_control, mask=oof_mask,
        selected_indices=tuple(map(int, selected.tolist())),
        selected_feature_names=selected_names)
    return scores, {**core, "receipt_sha256": C.object_sha256(core)}


def fit_path_state_rankers(
    fit: PathStateLandmark, platt: PathStateLandmark, *,
    fit_roster: Sequence[str], platt_roster: Sequence[str],
    config: PathStateRankConfig = PathStateRankConfig(),
) -> tuple[PathStateRankModels, Mapping[str, object]]:
    """Fit one exact delayed-acceptance head and its shuffled-label control."""

    if (fit.feature_names != platt.feature_names
            or fit.landmark_delay_sec != platt.landmark_delay_sec
            or int(np.max(fit.dataset.day)) >= int(np.min(platt.dataset.day))):
        raise ConfirmationRefusal("path-state role identity differs")
    fit_roster_mask = _roster_mask(fit, fit_roster)
    platt_roster_mask = _roster_mask(platt, platt_roster)
    shortcut_names = SHORTCUT_FEATURES
    # Raw path states are causal.  Asset-day centring would use candidates
    # that may arrive later and would train on a population different from the
    # frozen learned roster.
    fit_matrix, selected, selected_names = _selected_state_matrix(
        fit, fit_roster_mask, config)
    platt_matrix = np.asarray(platt.matrix[:, selected], np.float32)
    fit_values = np.asarray(fit.target.value_usd, np.float64)
    platt_values = np.asarray(platt.target.value_usd, np.float64)
    control_values = _shuffle_within_population(
        fit_values, fit, fit_roster_mask, seed=config.random_seed + 10_000)
    fit_relevance = _objective_relevance(
        fit_values, fit, fit_roster_mask, config)
    control_relevance = _objective_relevance(
        control_values, fit, fit_roster_mask, config)
    folds = _folds(fit, config)
    oof_real = np.full(len(fit_matrix), np.nan)
    oof_control = np.full(len(fit_matrix), np.nan)
    oof_mask = np.zeros(len(fit_matrix), bool); fold_rows = []
    for fold in folds:
        real = _fit(_pool(
            fit_matrix, fit_relevance, fit, population=fit_roster_mask,
            days=fold["train_days"]), config,
            seed=config.random_seed + 100 * int(fold["fold"]))
        control = _fit(_pool(
            fit_matrix, control_relevance, fit, population=fit_roster_mask,
            days=fold["train_days"]), config,
            seed=config.random_seed + 100 * int(fold["fold"]))
        valid = np.isin(np.asarray(fit.dataset.day, np.int64),
                        np.asarray(fold["validation_days"], np.int64))
        oof_real[valid] = np.asarray(real.predict(fit_matrix[valid]), np.float64)
        oof_control[valid] = np.asarray(
            control.predict(fit_matrix[valid]), np.float64)
        oof_mask |= valid
        fold_rows.append({
            **fold,
            "real_roster": lawful_value_rank_diagnostic(
                np.nan_to_num(oof_real), fit.target, fit.dataset,
                capacity=config.capacity, mask=valid & fit_roster_mask),
            "control_roster": lawful_value_rank_diagnostic(
                np.nan_to_num(oof_control), fit.target, fit.dataset,
                capacity=config.capacity, mask=valid & fit_roster_mask),
        })
    if (np.any(~np.isfinite(oof_real[oof_mask]))
            or np.any(~np.isfinite(oof_control[oof_mask]))):
        raise ConfirmationRefusal("path-state OOF prediction incomplete")
    oof_real_diag = lawful_value_rank_diagnostic(
        np.nan_to_num(oof_real), fit.target, fit.dataset,
        capacity=config.capacity, mask=oof_mask & fit_roster_mask)
    oof_control_diag = lawful_value_rank_diagnostic(
        np.nan_to_num(oof_control), fit.target, fit.dataset,
        capacity=config.capacity, mask=oof_mask & fit_roster_mask)
    final_days = tuple(map(int, np.unique(np.asarray(
        fit.dataset.day, np.int64))[-config.rolling_train_days:].tolist()))
    final_real = _fit(_pool(
        fit_matrix, fit_relevance, fit, population=fit_roster_mask,
        days=final_days), config,
                      seed=config.random_seed + 1_000)
    final_control = _fit(_pool(
        fit_matrix, control_relevance, fit, population=fit_roster_mask,
        days=final_days), config,
                         seed=config.random_seed + 1_000)
    platt_real_score = np.asarray(
        final_real.predict(platt_matrix), np.float64)
    platt_control_score = np.asarray(
        final_control.predict(platt_matrix), np.float64)
    platt_real_diag = lawful_value_rank_diagnostic(
        platt_real_score, platt.target, platt.dataset,
        capacity=config.capacity, mask=platt_roster_mask)
    platt_control_diag = lawful_value_rank_diagnostic(
        platt_control_score, platt.target, platt.dataset,
        capacity=config.capacity, mask=platt_roster_mask)
    oof_capture_gain = float(
        oof_real_diag["top_capacity_lawful_value_capture"]
        - oof_control_diag["top_capacity_lawful_value_capture"])
    oof_spearman_gain = float(
        oof_real_diag["overall"]["mean_spearman"]
        - oof_control_diag["overall"]["mean_spearman"])
    gate = bool(
        oof_capture_gain >= config.minimum_oof_capture_gain
        and oof_spearman_gain >= config.minimum_oof_spearman_gain
        and platt_real_diag["top_capacity_lawful_value_capture"]
        > platt_control_diag["top_capacity_lawful_value_capture"]
        and platt_real_diag["overall"]["mean_spearman"]
        > platt_control_diag["overall"]["mean_spearman"])
    importance = np.asarray(final_real.get_feature_importance(
        type="PredictionValuesChange"), np.float64)
    top = np.argsort(-importance, kind="stable")[:30]
    core = {
        "schema": SCHEMA, "config": asdict(config),
        "config_sha256": config.receipt_sha256,
        "catboost_version": catboost.__version__,
        "landmark_delay_sec": fit.landmark_delay_sec,
        "target": "SIGNED_BEST_FULLY_OBSERVED_DELAYED_ENTRY_VALUE",
        "objective_label_transform": config.objective_variant,
        "training_population": "FROZEN_LEARNED_TOP12_ROSTER",
        "diagnostic_population": "FROZEN_LEARNED_TOP12_ROSTER",
        "representation": "RAW_CAUSAL_PATH_STATE_NO_ASSET_DAY_CENTERING",
        "excluded_shortcut_features": tuple(sorted(shortcut_names)),
        "final_train_days": final_days,
        "input_features": len(fit.feature_names),
        "selected_dynamic_features": len(selected),
        "selected_indices": tuple(map(int, selected.tolist())),
        "selected_feature_names": selected_names,
        "fit_candidates": int(np.sum(fit_roster_mask)),
        "fit_positive_candidates": int(np.sum(
            (fit_values > 0.0) & fit_roster_mask)),
        "platt_candidates": int(np.sum(platt_roster_mask)),
        "platt_positive_candidates": int(np.sum(
            (platt_values > 0.0) & platt_roster_mask)),
        "chronological_folds": tuple(fold_rows),
        "fit_oof_real_roster": oof_real_diag,
        "fit_oof_control_roster": oof_control_diag,
        "fit_oof_capture_gain": oof_capture_gain,
        "fit_oof_spearman_gain": oof_spearman_gain,
        "platt_real_roster": platt_real_diag,
        "platt_control_roster": platt_control_diag,
        "top_feature_importance": tuple({
            "feature": selected_names[index],
            "importance": float(importance[index]),
        } for index in top if importance[index] > 0.0),
        "model_gate_pass": gate,
        "economics_executed": False,
        "threshold_open_count": 0, "forward_open_count": 0,
        "h2_open_count": 0,
    }
    models = PathStateRankModels(
        real=final_real, control=final_control,
        selected_indices=tuple(map(int, selected.tolist())),
        selected_feature_names=selected_names)
    return models, {**core, "receipt_sha256": C.object_sha256(core)}


def path_state_rank_scores(
    models: PathStateRankModels, landmark: PathStateLandmark,
) -> tuple[np.ndarray, np.ndarray]:
    selected = np.asarray(models.selected_indices, np.int64)
    names = tuple(np.asarray(landmark.feature_names, str)[selected].tolist())
    if names != models.selected_feature_names:
        raise ConfirmationRefusal("path-state prediction schema differs")
    values = np.asarray(landmark.matrix[:, selected], np.float32)
    return (np.asarray(models.real.predict(values), np.float64),
            np.asarray(models.control.predict(values), np.float64))


__all__ = [
    "SCHEMA", "OOF_SCHEMA", "PathStateRankConfig", "PathStateRankModels",
    "PathStateOofScores",
    "cross_section_state_matrix", "fit_path_state_rankers",
    "fit_path_state_oof_scores", "path_state_rank_scores",
]
