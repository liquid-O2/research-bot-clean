"""Compact listwise CatBoost learner for action-aligned candidate value."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Final, Mapping, Sequence

import catboost
from catboost import CatBoostRanker, Pool
import numpy as np

from . import common as C
from .confirmation import ConfirmationDataset, ConfirmationRefusal
from .confirmation_acceptance_mechanism import (
    asset_day_groups, cross_section_matrix,
)
from .confirmation_fixed_horizon import _spearman
from .confirmation_lawful_value import (
    CandidateLawfulValueTarget, shuffle_observed_within_asset_day,
)


SCHEMA: Final = "QRE2CONFLAWFULVALUERANK1"


@dataclass(frozen=True, slots=True)
class LawfulValueRankConfig:
    capacity: int = 12
    minimum_train_days: int = 12
    validation_days: int = 6
    fold_count: int = 3
    iterations: int = 160
    depth: int = 5
    learning_rate: float = .04
    l2_leaf_reg: float = 20.0
    random_seed: int = 20260820
    thread_count: int = 16
    minimum_oof_spearman_gain_vs_control: float = .02
    minimum_platt_spearman: float = .03

    def __post_init__(self) -> None:
        if (not 1 <= self.capacity <= 24
                or not 6 <= self.minimum_train_days <= 60
                or not 2 <= self.validation_days <= 20
                or not 1 <= self.fold_count <= 6
                or not 20 <= self.iterations <= 500
                or not 3 <= self.depth <= 8
                or not 0 < self.learning_rate <= .3
                or not 0 < self.l2_leaf_reg <= 1_000
                or not 1 <= self.thread_count <= C.MAX_CPU_WORKERS
                or not -1 <= self.minimum_oof_spearman_gain_vs_control <= 1
                or not -1 <= self.minimum_platt_spearman <= 1):
            raise ConfirmationRefusal("lawful-value rank configuration invalid")

    @property
    def receipt_sha256(self) -> str:
        return C.object_sha256({"schema": SCHEMA, **asdict(self)})


@dataclass(frozen=True, slots=True)
class LawfulValueRankModels:
    real: CatBoostRanker
    control: CatBoostRanker
    feature_names: tuple[str, ...]


def _transform_ledger(
    transform: Sequence[Mapping[str, object]],
    dataset: ConfirmationDataset,
) -> tuple[np.ndarray, tuple[str, ...]]:
    rows = tuple(transform)
    if not rows:
        raise ConfirmationRefusal("lawful-value selected transform is empty")
    columns = np.asarray([int(row["source_column"]) for row in rows], np.int64)
    names = tuple(str(row["feature_name"]) for row in rows)
    direction = np.asarray([int(row["direction"]) for row in rows], np.float64)
    scale = np.asarray([float(row["fit_scale"]) for row in rows], np.float64)
    if (len(set(columns.tolist())) != len(columns)
            or np.any(columns < 0) or np.any(columns >= len(dataset.feature_names))
            or names != tuple(dataset.feature_names[index] for index in columns)
            or np.any(~np.isin(direction, (-1.0, 1.0)))
            or not np.all(np.isfinite(scale)) or np.any(scale <= 0.0)):
        raise ConfirmationRefusal("lawful-value selected transform differs")
    centered, _ = cross_section_matrix(dataset, columns)
    matrix = centered / scale[None, :] * direction[None, :]
    if not np.all(np.isfinite(matrix)):
        raise ConfirmationRefusal("lawful-value model matrix is non-finite")
    return np.asarray(matrix, np.float32), names


def _folds(dataset: ConfirmationDataset, config: LawfulValueRankConfig) \
        -> tuple[Mapping[str, object], ...]:
    days = np.unique(np.asarray(dataset.day, np.int64))
    required = (config.minimum_train_days
                + config.validation_days * config.fold_count)
    if len(days) != required:
        raise ConfirmationRefusal(
            "lawful-value FIT day count does not match frozen folds")
    result = []
    for ordinal in range(config.fold_count):
        split = config.minimum_train_days + ordinal * config.validation_days
        result.append({
            "fold": ordinal + 1,
            "train_days": tuple(map(int, days[:split].tolist())),
            "validation_days": tuple(map(
                int, days[split:split + config.validation_days].tolist())),
        })
    return tuple(result)


def _pool(
    matrix: np.ndarray, values: np.ndarray, observed: np.ndarray,
    dataset: ConfirmationDataset, days: Sequence[int] | None = None,
) -> tuple[Pool, np.ndarray]:
    mask = np.asarray(observed, bool).copy()
    if days is not None:
        mask &= np.isin(np.asarray(dataset.day, np.int64),
                        np.asarray(tuple(days), np.int64))
    indices = np.flatnonzero(mask)
    groups = asset_day_groups(dataset)
    series = np.asarray(dataset.series_id, str)
    order = np.lexsort((series[indices], groups[indices]))
    indices = indices[order]
    ordered_groups = groups[indices]
    if not len(indices) or np.any(~np.isfinite(values[indices])):
        raise ConfirmationRefusal("lawful-value rank pool is empty/non-finite")
    # CatBoost requires every query to be contiguous; lexicographic ordering
    # above is part of the persisted training contract.
    boundaries = np.r_[True, ordered_groups[1:] != ordered_groups[:-1], True]
    if int(np.sum(boundaries)) - 1 != len(set(ordered_groups.tolist())):
        raise ConfirmationRefusal("lawful-value rank groups are not contiguous")
    pool = Pool(matrix[indices], label=values[indices],
                group_id=ordered_groups.tolist())
    return pool, indices


def _fit(
    pool: Pool, config: LawfulValueRankConfig, *, seed: int,
) -> CatBoostRanker:
    model = CatBoostRanker(
        loss_function=f"YetiRankPairwise:mode=NDCG;top={config.capacity}",
        iterations=config.iterations, depth=config.depth,
        learning_rate=config.learning_rate, l2_leaf_reg=config.l2_leaf_reg,
        random_seed=int(seed), thread_count=config.thread_count,
        allow_writing_files=False, verbose=False)
    model.fit(pool, verbose=False)
    if int(model.tree_count_) != config.iterations:
        raise ConfirmationRefusal("lawful-value rank tree count differs")
    return model


def lawful_value_rank_diagnostic(
    score: np.ndarray, target: CandidateLawfulValueTarget,
    dataset: ConfirmationDataset, *, capacity: int,
    mask: np.ndarray | None = None,
) -> Mapping[str, object]:
    prediction = np.asarray(score, np.float64)
    target.validate(dataset)
    if prediction.shape != (len(dataset.features),) \
            or not np.all(np.isfinite(prediction)):
        raise ConfirmationRefusal("lawful-value rank score differs")
    use = np.asarray(target.observed, bool).copy()
    if mask is not None:
        supplied = np.asarray(mask, bool)
        if supplied.shape != use.shape:
            raise ConfirmationRefusal("lawful-value diagnostic mask differs")
        use &= supplied
    values = np.asarray(target.value_usd, np.float64)
    groups = asset_day_groups(dataset); assets = np.asarray(dataset.asset, str)
    series = np.asarray(dataset.series_id, str)
    rows = []; selected = []; oracle = []
    for group in sorted(set(groups[use].tolist())):
        local = np.flatnonzero(use & (groups == group))
        correlation = _spearman(prediction[local], values[local])
        if correlation is not None:
            rows.append((str(assets[local[0]]), correlation))
        selected.extend(local[np.lexsort((series[local], -prediction[local]))]
                        [:capacity].tolist())
        oracle.extend(local[np.lexsort((series[local], -values[local]))]
                      [:capacity].tolist())
    if not rows or not selected or not oracle:
        raise ConfirmationRefusal("lawful-value rank diagnostic is empty")
    selected_value = float(np.sum(values[np.asarray(selected, np.int64)]))
    oracle_value = float(np.sum(values[np.asarray(oracle, np.int64)]))
    correlations = np.asarray([row[1] for row in rows], np.float64)
    row_assets = np.asarray([row[0] for row in rows], str)

    def summarize(use_rows: np.ndarray) -> Mapping[str, object]:
        local = correlations[use_rows]
        return {
            "groups": len(local),
            "mean_spearman": float(np.mean(local)),
            "median_spearman": float(np.median(local)),
            "positive_group_fraction": float(np.mean(local > 0.0)),
        }

    core = {
        "observed_candidates": int(np.sum(use)),
        "overall": summarize(np.ones(len(rows), bool)),
        "by_asset": {asset: summarize(row_assets == asset)
                     for asset in sorted(set(row_assets.tolist()))},
        "capacity": int(capacity),
        "selected_candidates": len(selected),
        "selected_lawful_value_usd": selected_value,
        "oracle_top_capacity_lawful_value_usd": oracle_value,
        "top_capacity_lawful_value_capture": (
            0.0 if oracle_value <= 0 else selected_value / oracle_value),
        "score_standard_deviation": float(np.std(prediction[use])),
        "score_unique_count": int(len(np.unique(prediction[use]))),
        "not_schedule_economics": True,
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


def fit_lawful_value_rankers(
    fit_dataset: ConfirmationDataset, fit_target: CandidateLawfulValueTarget,
    platt_dataset: ConfirmationDataset,
    platt_target: CandidateLawfulValueTarget, *,
    selected_transform: Sequence[Mapping[str, object]],
    audit_receipt_sha256: str,
    config: LawfulValueRankConfig = LawfulValueRankConfig(),
) -> tuple[LawfulValueRankModels, Mapping[str, object]]:
    """Fit FIT-only real/control rankers with frozen chronological OOF."""

    if (fit_dataset.feature_names != platt_dataset.feature_names
            or int(np.max(fit_dataset.day)) >= int(np.min(platt_dataset.day))
            or len(audit_receipt_sha256) != 64):
        raise ConfirmationRefusal("lawful-value rank role identity differs")
    fit_target.validate(fit_dataset); platt_target.validate(platt_dataset)
    fit_matrix, names = _transform_ledger(selected_transform, fit_dataset)
    platt_matrix, platt_names = _transform_ledger(
        selected_transform, platt_dataset)
    if names != platt_names:
        raise ConfirmationRefusal("lawful-value rank transformed schema differs")
    folds = _folds(fit_dataset, config)
    control_values = shuffle_observed_within_asset_day(
        fit_dataset, fit_target, seed=config.random_seed + 10_000)
    fit_values = np.asarray(fit_target.value_usd, np.float64)
    fit_observed = np.asarray(fit_target.observed, bool)
    oof_real = np.full(len(fit_dataset.features), np.nan, np.float64)
    oof_control = np.full(len(fit_dataset.features), np.nan, np.float64)
    oof_mask = np.zeros(len(fit_dataset.features), bool)
    fold_rows = []
    for fold in folds:
        train_pool, _ = _pool(
            fit_matrix, fit_values, fit_observed, fit_dataset,
            fold["train_days"])
        control_pool, _ = _pool(
            fit_matrix, control_values, fit_observed, fit_dataset,
            fold["train_days"])
        real = _fit(train_pool, config,
                    seed=config.random_seed + int(fold["fold"]) * 100)
        control = _fit(control_pool, config,
                       seed=config.random_seed + int(fold["fold"]) * 100)
        valid = (fit_observed & np.isin(
            np.asarray(fit_dataset.day, np.int64),
            np.asarray(fold["validation_days"], np.int64)))
        oof_real[valid] = np.asarray(real.predict(fit_matrix[valid]), np.float64)
        oof_control[valid] = np.asarray(
            control.predict(fit_matrix[valid]), np.float64)
        oof_mask |= valid
        fold_rows.append({
            **fold,
            "real": lawful_value_rank_diagnostic(
                np.nan_to_num(oof_real), fit_target, fit_dataset,
                capacity=config.capacity, mask=valid),
            "control": lawful_value_rank_diagnostic(
                np.nan_to_num(oof_control), fit_target, fit_dataset,
                capacity=config.capacity, mask=valid),
        })
    if (np.any(~np.isfinite(oof_real[oof_mask]))
            or np.any(~np.isfinite(oof_control[oof_mask]))):
        raise ConfirmationRefusal("lawful-value OOF prediction is incomplete")
    oof_real_diag = lawful_value_rank_diagnostic(
        np.nan_to_num(oof_real), fit_target, fit_dataset,
        capacity=config.capacity, mask=oof_mask)
    oof_control_diag = lawful_value_rank_diagnostic(
        np.nan_to_num(oof_control), fit_target, fit_dataset,
        capacity=config.capacity, mask=oof_mask)
    final_pool, _ = _pool(
        fit_matrix, fit_values, fit_observed, fit_dataset)
    final_control_pool, _ = _pool(
        fit_matrix, control_values, fit_observed, fit_dataset)
    real_model = _fit(final_pool, config, seed=config.random_seed + 1_000)
    control_model = _fit(
        final_control_pool, config, seed=config.random_seed + 1_000)
    platt_real_score = np.asarray(
        real_model.predict(platt_matrix), np.float64)
    platt_control_score = np.asarray(
        control_model.predict(platt_matrix), np.float64)
    platt_real_diag = lawful_value_rank_diagnostic(
        platt_real_score, platt_target, platt_dataset,
        capacity=config.capacity)
    platt_control_diag = lawful_value_rank_diagnostic(
        platt_control_score, platt_target, platt_dataset,
        capacity=config.capacity)
    importance = np.asarray(real_model.get_feature_importance(
        type="PredictionValuesChange"), np.float64)
    top = np.argsort(-importance, kind="stable")[:20]
    gate = bool(
        oof_real_diag["overall"]["mean_spearman"]
        - oof_control_diag["overall"]["mean_spearman"]
        >= config.minimum_oof_spearman_gain_vs_control
        and platt_real_diag["overall"]["mean_spearman"]
        >= config.minimum_platt_spearman
        and platt_real_diag["overall"]["mean_spearman"]
        > platt_control_diag["overall"]["mean_spearman"]
        and platt_real_diag["top_capacity_lawful_value_capture"]
        > platt_control_diag["top_capacity_lawful_value_capture"])
    core = {
        "schema": SCHEMA, "config": asdict(config),
        "config_sha256": config.receipt_sha256,
        "catboost_version": catboost.__version__,
        "lawful_value_audit_receipt_sha256": audit_receipt_sha256,
        "objective": f"YetiRankPairwise:mode=NDCG;top={config.capacity}",
        "group_scope": "ASSET_DAY",
        "feature_count": len(names), "feature_names": names,
        "chronological_folds": tuple(fold_rows),
        "fit_oof_real": oof_real_diag,
        "fit_oof_control": oof_control_diag,
        "platt_real": platt_real_diag,
        "platt_control": platt_control_diag,
        "top_feature_importance": tuple({
            "feature": names[index], "importance": float(importance[index]),
        } for index in top if importance[index] > 0.0),
        "model_gate_pass": gate,
        "economics_executed": False,
        "threshold_open_count": 0, "forward_open_count": 0,
        "h2_open_count": 0,
    }
    models = LawfulValueRankModels(
        real=real_model, control=control_model, feature_names=names)
    return models, {**core, "receipt_sha256": C.object_sha256(core)}


def lawful_value_rank_scores(
    models: LawfulValueRankModels,
    dataset: ConfirmationDataset, *,
    selected_transform: Sequence[Mapping[str, object]],
) -> tuple[np.ndarray, np.ndarray]:
    matrix, names = _transform_ledger(selected_transform, dataset)
    if names != models.feature_names:
        raise ConfirmationRefusal("lawful-value prediction schema differs")
    return (np.asarray(models.real.predict(matrix), np.float64),
            np.asarray(models.control.predict(matrix), np.float64))


__all__ = [
    "SCHEMA", "LawfulValueRankConfig", "LawfulValueRankModels",
    "fit_lawful_value_rankers", "lawful_value_rank_diagnostic",
    "lawful_value_rank_scores",
]
