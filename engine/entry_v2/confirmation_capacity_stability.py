"""Forward-blocked objective stability on the durable fixed-watch corpus."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Final, Mapping

import catboost
from catboost import CatBoostClassifier, CatBoostRanker, Pool
import numpy as np

from . import common as C
from .confirmation import ConfirmationDataset, ConfirmationRefusal
from .confirmation_candidate_rank import (
    CURRENT_TARGET_SCOPE, _rank_pool, _shuffle_within_groups,
    candidate_rank_diagnostic,
)
from .confirmation_capacity_probe import (
    GROUP_SCOPE, _balanced_group_class_weights, _pair_pool,
    _require_binary_support, capacity_topk_labels, survival_expected_value,
)
from .confirmation_stopping import OracleActionLedger


SCHEMA: Final = "QRE2CONFCAPACITYSTABILITY2"
FAMILIES: Final = (
    "YETI_RAW_USD", "BALANCED_TOPK", "DOLLAR_MARGIN_TOPK",
    "SOFT_TOPK_RELEVANCE", "SURVIVAL_EXPECTED_VALUE", "HARD_PAIRLOGIT",
)
FAMILY_SEED_OFFSET: Final = {
    "YETI_RAW_USD": 0,
    "BALANCED_TOPK": 100,
    "DOLLAR_MARGIN_TOPK": 200,
    "SOFT_TOPK_RELEVANCE": 300,
    "SURVIVAL_EXPECTED_VALUE": 400,
    "HARD_PAIRLOGIT": 500,
}


@dataclass(frozen=True, slots=True)
class CapacityStabilityConfig:
    watch_age_sec: int = 30
    capacity: int = 4
    minimum_train_days: int = 12
    validation_days: int = 6
    fold_count: int = 3
    fold_iterations: int = 30
    final_iterations: int = 80
    depth: int = 5
    learning_rate: float = .05
    l2_leaf_reg: float = 12.0
    random_seed: int = 20260820
    thread_count: int = 16
    early_stopping_rounds: int = 10
    survival_thresholds_usd: tuple[float, ...] = (
        0.0, 250.0, 500.0, 1_000.0, 1_800.0)
    survival_cap_usd: float = 4_000.0
    hard_negative_multiple: int = 8

    def __post_init__(self) -> None:
        thresholds = tuple(float(value)
                           for value in self.survival_thresholds_usd)
        if (not 0 <= self.watch_age_sec <= 300
                or not 1 <= self.capacity <= 12
                or not 2 <= self.minimum_train_days <= 120
                or not 1 <= self.validation_days <= 30
                or not 2 <= self.fold_count <= 8
                or not 10 <= self.fold_iterations <= 200
                or not 20 <= self.final_iterations <= 500
                or not 3 <= self.depth <= 8
                or not 0 < self.learning_rate <= .3
                or not 0 < self.l2_leaf_reg <= 1_000
                or not 1 <= self.thread_count <= C.MAX_CPU_WORKERS
                or not 5 <= self.early_stopping_rounds < self.final_iterations
                or thresholds != tuple(sorted(set(thresholds)))
                or not thresholds or thresholds[0] != 0.0
                or not self.survival_cap_usd > thresholds[-1]
                or not 1 <= self.hard_negative_multiple <= 32):
            raise ConfirmationRefusal(
                "capacity-stability configuration is invalid")

    @property
    def receipt_sha256(self) -> str:
        return C.object_sha256({"schema": SCHEMA, **asdict(self)})


def forward_day_folds(
    days: np.ndarray, *, minimum_train_days: int,
    validation_days: int, fold_count: int,
) -> tuple[Mapping[str, object], ...]:
    values = np.asarray(days, np.int64)
    unique = np.unique(values)
    required = minimum_train_days + validation_days * fold_count
    if (values.ndim != 1 or len(unique) != required):
        raise ConfirmationRefusal(
            "capacity-stability FIT day calendar differs")
    result = []
    for ordinal in range(fold_count):
        train_end = minimum_train_days + ordinal * validation_days
        valid_end = train_end + validation_days
        train_days = unique[:train_end]
        validation = unique[train_end:valid_end]
        train_indices = np.flatnonzero(np.isin(values, train_days))
        validation_indices = np.flatnonzero(np.isin(values, validation))
        if (not len(train_indices) or not len(validation_indices)
                or int(np.max(values[train_indices]))
                >= int(np.min(values[validation_indices]))):
            raise ConfirmationRefusal(
                "capacity-stability fold chronology differs")
        result.append({
            "fold": ordinal + 1,
            "train_days": tuple(map(int, train_days)),
            "validation_days": tuple(map(int, validation)),
            "train_indices": train_indices,
            "validation_indices": validation_indices,
        })
    return tuple(result)


def _capacity_groups(
    dataset: ConfirmationDataset, indices: np.ndarray,
) -> np.ndarray:
    selected = np.asarray(indices, np.int64)
    return np.asarray([
        f"{asset}:{int(day)}"
        for asset, day in zip(
            np.asarray(dataset.asset, str)[selected],
            np.asarray(dataset.day, np.int64)[selected])
    ], str)


def capacity_soft_relevance(
    dataset: ConfirmationDataset, indices: np.ndarray,
    target: np.ndarray, *, capacity: int,
) -> np.ndarray:
    """Continuous relevance relative to each asset-day's kth value."""

    values = np.asarray(target, np.float64)
    if (values.shape != (len(indices),) or np.any(values < 0.0)
            or not np.all(np.isfinite(values)) or not 1 <= capacity <= 12):
        raise ConfirmationRefusal("capacity soft relevance inputs differ")
    groups = _capacity_groups(dataset, indices)
    result = np.zeros(len(values), np.float64)
    for group in np.unique(groups):
        local = np.flatnonzero(groups == group)
        positive = np.sort(values[local][values[local] > 0.0])[::-1]
        if not len(positive):
            continue
        denominator = float(positive[min(capacity, len(positive)) - 1])
        if denominator <= 0.0:
            raise ConfirmationRefusal(
                "capacity soft relevance denominator is zero")
        result[local] = np.clip(values[local] / denominator, 0.0, 1.0)
    if not np.any((result > 0.0) & (result < 1.0)):
        raise ConfirmationRefusal(
            "capacity soft relevance has no graded support")
    return result


def _group_equal_weights(
    dataset: ConfirmationDataset, indices: np.ndarray,
) -> np.ndarray:
    groups = _capacity_groups(dataset, indices)
    _, inverse, counts = np.unique(
        groups, return_inverse=True, return_counts=True)
    weights = 1.0 / counts[inverse].astype(np.float64)
    return weights * (len(weights) / weights.sum())


def capacity_dollar_margin_weights(
    dataset: ConfirmationDataset, indices: np.ndarray,
    target: np.ndarray, *, capacity: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Group/class balance with economic distance from the kth boundary."""

    values = np.asarray(target, np.float64)
    labels = capacity_topk_labels(
        dataset, indices, values, capacity=capacity)
    groups = _capacity_groups(dataset, indices)
    ids = np.asarray(dataset.series_id, str)[np.asarray(indices, np.int64)]
    weights = np.zeros(len(values), np.float64)
    for group in np.unique(groups):
        local = np.flatnonzero(groups == group)
        ordered = local[np.lexsort((ids[local], -values[local]))]
        k = min(capacity, len(ordered))
        upper = float(values[ordered[k - 1]])
        lower = (float(values[ordered[k]])
                 if k < len(ordered) else 0.0)
        boundary = .5 * (upper + lower)
        raw = .1 + np.log1p(np.abs(values[local] - boundary) / 25.0)
        positive = labels[local] == 1
        negative = ~positive
        if positive.any() and negative.any():
            weights[local[positive]] = .5 * raw[positive] / raw[positive].sum()
            weights[local[negative]] = .5 * raw[negative] / raw[negative].sum()
        else:
            weights[local] = raw / raw.sum()
    if np.any(weights <= 0.0) or not np.all(np.isfinite(weights)):
        raise ConfirmationRefusal("capacity dollar-margin weights differ")
    return labels, weights * (len(weights) / weights.sum())


def _validate_inputs(
    datasets: Mapping[str, ConfirmationDataset],
    ledgers: Mapping[str, OracleActionLedger],
) -> None:
    roles = ("FIT", "PLATT", "THRESHOLD")
    if set(datasets) != set(roles) or set(ledgers) != set(roles):
        raise ConfirmationRefusal(
            "capacity-stability role roster is incomplete")
    for role in roles:
        datasets[role].validate(); ledgers[role].validate()
        if (ledgers[role].source_representation_sha256
                != datasets[role].representation_sha256
                or not np.array_equal(
                    ledgers[role].opportunity_id,
                    datasets[role].opportunity_id)
                or len(set(np.asarray(
                    datasets[role].series_id, str).tolist()))
                != len(datasets[role].features)):
            raise ConfirmationRefusal(
                "capacity-stability compact identity differs")
    if (datasets["FIT"].feature_names != datasets["PLATT"].feature_names
            or datasets["FIT"].feature_names
            != datasets["THRESHOLD"].feature_names
            or int(np.max(datasets["FIT"].day))
            >= int(np.min(datasets["PLATT"].day))
            or int(np.max(datasets["PLATT"].day))
            >= int(np.min(datasets["THRESHOLD"].day))):
        raise ConfirmationRefusal(
            "capacity-stability schemas/chronology differ")


def capacity_stability_preflight(
    datasets: Mapping[str, ConfirmationDataset],
    ledgers: Mapping[str, OracleActionLedger], *,
    capacity_corpus_receipt_sha256: str,
    config: CapacityStabilityConfig = CapacityStabilityConfig(),
) -> Mapping[str, object]:
    """Execute every real label/pool boundary before any objective fit."""

    _validate_inputs(datasets, ledgers)
    if len(capacity_corpus_receipt_sha256) != 64:
        raise ConfirmationRefusal("capacity corpus receipt is malformed")
    roles = ("FIT", "PLATT", "THRESHOLD")
    folds = forward_day_folds(
        datasets["FIT"].day,
        minimum_train_days=config.minimum_train_days,
        validation_days=config.validation_days,
        fold_count=config.fold_count)
    target = {role: np.asarray(
        ledgers[role].q_optimal_usd, np.float64) for role in roles}
    checkpoints = {role: np.full(
        len(target[role]), config.watch_age_sec, np.int16) for role in roles}

    def support(role: str, indices: np.ndarray) -> Mapping[str, object]:
        values = target[role][indices]
        assets = np.asarray(datasets[role].asset, str)[indices]
        days = np.asarray(datasets[role].day, np.int64)[indices]
        groups = np.asarray([
            f"{asset}:{int(day)}" for asset, day in zip(assets, days)], str)
        topk_positive = sum(
            min(config.capacity, int(np.sum(values[groups == group] > 0.0)))
            for group in np.unique(groups))
        return {
            "rows": len(indices),
            "asset_days": len(np.unique(groups)),
            "topk_negative": int(len(indices) - topk_positive),
            "topk_positive": int(topk_positive),
            "survival": {
                str(threshold): {
                    "negative": int(np.sum(
                        values <= 0.0 if threshold == 0.0
                        else values < threshold)),
                    "positive": int(np.sum(
                        values > 0.0 if threshold == 0.0
                        else values >= threshold)),
                } for threshold in config.survival_thresholds_usd
            },
        }

    fold_support = []
    required_slices = []
    for fold in folds:
        train_indices = np.asarray(fold["train_indices"], np.int64)
        validation_indices = np.asarray(
            fold["validation_indices"], np.int64)
        fold_support.append({
            "fold": fold["fold"],
            "train_days": fold["train_days"],
            "validation_days": fold["validation_days"],
            "train": support("FIT", train_indices),
            "validation": support("FIT", validation_indices),
            "validation_labels_consumed_by_fixed_fit": False,
        })
        required_slices.append((
            f"FOLD{fold['fold']}:TRAIN", "FIT", train_indices))
    all_indices = {role: np.arange(
        len(target[role]), dtype=np.int64) for role in roles}
    required_slices.extend((
        ("FINAL:FIT", "FIT", all_indices["FIT"]),
        ("FINAL:PLATT", "PLATT", all_indices["PLATT"]),
    ))
    for name, role, indices in required_slices:
        values = target[role][indices]
        capacity_topk_labels(
            datasets[role], indices, values, capacity=config.capacity)
        for threshold in config.survival_thresholds_usd:
            binary = np.asarray(
                values > 0.0 if threshold == 0.0
                else values >= threshold, np.int8)
            _require_binary_support(
                binary, name=f"{name}:SURVIVAL:{threshold:g}")
        _rank_pool(
            datasets[role], datasets[role].features, values,
            indices, checkpoints[role][indices], group_scope=GROUP_SCOPE)
        _pair_pool(
            datasets[role], datasets[role].features[indices], indices,
            values, capacity=config.capacity,
            hard_negative_multiple=config.hard_negative_multiple)
        capacity_soft_relevance(
            datasets[role], indices, values, capacity=config.capacity)
        capacity_dollar_margin_weights(
            datasets[role], indices, values, capacity=config.capacity)
    core = {
        "schema": "QRE2CONFCAPACITYSTABILITYPREFLIGHT1",
        "config_sha256": config.receipt_sha256,
        "capacity_corpus_receipt_sha256": capacity_corpus_receipt_sha256,
        "fold_support": tuple(fold_support),
        "final_fit_support": support("FIT", all_indices["FIT"]),
        "final_platt_support": support("PLATT", all_indices["PLATT"]),
        "threshold_diagnostic_support": support(
            "THRESHOLD", all_indices["THRESHOLD"]),
        "required_training_pools_constructed": True,
        "implementation_sha256": C.file_sha256(Path(__file__)),
        "labels_used_for_family_selection": "FIT_FORWARD_OOF_ONLY",
        "economics_executed": False,
        "forward_open_count": 0,
        "h2_open_count": 0,
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


def run_capacity_stability_probe(
    datasets: Mapping[str, ConfirmationDataset],
    ledgers: Mapping[str, OracleActionLedger], *,
    capacity_corpus_receipt_sha256: str,
    config: CapacityStabilityConfig = CapacityStabilityConfig(),
    progress: Callable[[Mapping[str, object]], None] | None = None,
) -> Mapping[str, object]:
    """Select an objective only from expanding FIT out-of-fold dollars."""

    _validate_inputs(datasets, ledgers)
    if len(capacity_corpus_receipt_sha256) != 64:
        raise ConfirmationRefusal("capacity corpus receipt is malformed")
    roles = ("FIT", "PLATT", "THRESHOLD")
    folds = forward_day_folds(
        datasets["FIT"].day,
        minimum_train_days=config.minimum_train_days,
        validation_days=config.validation_days,
        fold_count=config.fold_count)
    preflight = capacity_stability_preflight(
        datasets, ledgers,
        capacity_corpus_receipt_sha256=capacity_corpus_receipt_sha256,
        config=config)
    target = {role: np.asarray(
        ledgers[role].q_optimal_usd, np.float64) for role in roles}
    all_indices = {role: np.arange(
        len(datasets[role].features), dtype=np.int64) for role in roles}
    checkpoints = {role: np.full(
        len(all_indices[role]), config.watch_age_sec, np.int16)
        for role in roles}
    common = dict(
        depth=config.depth, learning_rate=config.learning_rate,
        l2_leaf_reg=config.l2_leaf_reg,
        thread_count=config.thread_count, allow_writing_files=False,
        verbose=False)


    def diagnostic(
        role: str, indices: np.ndarray, score: np.ndarray,
    ) -> Mapping[str, object]:
        chosen = np.asarray(indices, np.int64)
        return candidate_rank_diagnostic(
            datasets[role], ledgers[role], indices=chosen,
            checkpoints=checkpoints[role][chosen], score=score,
            capacity=config.capacity, group_scope=GROUP_SCOPE,
            target=target[role][chosen], target_scope=CURRENT_TARGET_SCOPE)

    def fit_family(
        family: str, train_indices: np.ndarray, train_target: np.ndarray,
        validation_role: str, validation_indices: np.ndarray, *,
        iterations: int | tuple[int, ...], early_stop: bool,
        seed: int,
    ) -> tuple[object, tuple[int, ...], tuple[Mapping[str, object], ...]]:
        train = np.asarray(train_indices, np.int64)
        valid = np.asarray(validation_indices, np.int64)
        x_fit = np.asarray(datasets["FIT"].features[train], np.float32)
        validation_dataset = datasets[validation_role]
        x_valid = np.asarray(validation_dataset.features[valid], np.float32)
        names = datasets["FIT"].feature_names
        accumulated = np.zeros(len(names), np.float64)

        def budget(ordinal: int = 0) -> int:
            if isinstance(iterations, tuple):
                if ordinal >= len(iterations):
                    raise ConfirmationRefusal(
                        "capacity-stability tree roster differs")
                value = int(iterations[ordinal])
            else:
                value = int(iterations)
            if value < 1:
                raise ConfirmationRefusal(
                    "capacity-stability tree budget is invalid")
            return value

        if family == "YETI_RAW_USD":
            train_age = checkpoints["FIT"][train]
            pool, _ = _rank_pool(
                datasets["FIT"], datasets["FIT"].features, train_target,
                train, train_age, group_scope=GROUP_SCOPE)
            model = CatBoostRanker(
                loss_function=(
                    f"YetiRankPairwise:mode=NDCG;top={config.capacity}"),
                eval_metric=f"NDCG:top={config.capacity}",
                iterations=budget(), random_seed=seed, **common)
            if early_stop:
                valid_target = target[validation_role][valid]
                valid_pool, _ = _rank_pool(
                    validation_dataset, validation_dataset.features,
                    valid_target, valid, checkpoints[validation_role][valid],
                    group_scope=GROUP_SCOPE)
                model.set_params(
                    od_type="Iter", od_wait=config.early_stopping_rounds)
                model.fit(pool, eval_set=valid_pool,
                          use_best_model=True, verbose=False)
            else:
                model.fit(pool, verbose=False)
            accumulated = np.asarray(model.get_feature_importance(
                type="PredictionValuesChange"), np.float64)
            models: object = model
            trees = (int(model.tree_count_),)
        elif family in {"BALANCED_TOPK", "DOLLAR_MARGIN_TOPK"}:
            if family == "BALANCED_TOPK":
                train_y = capacity_topk_labels(
                    datasets["FIT"], train, train_target,
                    capacity=config.capacity)
                fit_weight = _balanced_group_class_weights(
                    datasets["FIT"], train, train_y)
            else:
                train_y, fit_weight = capacity_dollar_margin_weights(
                    datasets["FIT"], train, train_target,
                    capacity=config.capacity)
            model = CatBoostClassifier(
                loss_function="Logloss", eval_metric="PRAUC:type=Classic",
                iterations=budget(), random_seed=seed, **common)
            if early_stop:
                if family == "BALANCED_TOPK":
                    valid_y = capacity_topk_labels(
                        validation_dataset, valid,
                        target[validation_role][valid],
                        capacity=config.capacity)
                    valid_weight = _balanced_group_class_weights(
                        validation_dataset, valid, valid_y)
                else:
                    valid_y, valid_weight = capacity_dollar_margin_weights(
                        validation_dataset, valid,
                        target[validation_role][valid],
                        capacity=config.capacity)
                model.set_params(
                    od_type="Iter", od_wait=config.early_stopping_rounds)
                model.fit(
                    x_fit, train_y, sample_weight=fit_weight,
                    eval_set=Pool(x_valid, valid_y, weight=valid_weight),
                    use_best_model=True, verbose=False)
            else:
                model.fit(x_fit, train_y, sample_weight=fit_weight,
                          verbose=False)
            accumulated = np.asarray(
                model.get_feature_importance(), np.float64)
            models = model
            trees = (int(model.tree_count_),)
        elif family == "SOFT_TOPK_RELEVANCE":
            train_y = capacity_soft_relevance(
                datasets["FIT"], train, train_target,
                capacity=config.capacity)
            fit_weight = _group_equal_weights(datasets["FIT"], train)
            model = CatBoostClassifier(
                loss_function="CrossEntropy", eval_metric="CrossEntropy",
                iterations=budget(), random_seed=seed, **common)
            if early_stop:
                valid_y = capacity_soft_relevance(
                    validation_dataset, valid,
                    target[validation_role][valid],
                    capacity=config.capacity)
                valid_weight = _group_equal_weights(
                    validation_dataset, valid)
                model.set_params(
                    od_type="Iter", od_wait=config.early_stopping_rounds)
                model.fit(
                    x_fit, train_y, sample_weight=fit_weight,
                    eval_set=Pool(x_valid, valid_y, weight=valid_weight),
                    use_best_model=True, verbose=False)
            else:
                model.fit(x_fit, train_y, sample_weight=fit_weight,
                          verbose=False)
            accumulated = np.asarray(
                model.get_feature_importance(), np.float64)
            models = model
            trees = (int(model.tree_count_),)
        elif family == "SURVIVAL_EXPECTED_VALUE":
            fitted = []
            trees_list = []
            for ordinal, threshold in enumerate(
                    config.survival_thresholds_usd):
                train_y = np.asarray(
                    train_target > 0.0 if threshold == 0.0
                    else train_target >= threshold, np.int8)
                _require_binary_support(
                    train_y, name=f"FIT_FOLD:SURVIVAL:{threshold:g}")
                model = CatBoostClassifier(
                    loss_function="Logloss",
                    eval_metric="PRAUC:type=Classic", iterations=budget(ordinal),
                    random_seed=seed + ordinal, **common)
                fit_weight = _balanced_group_class_weights(
                    datasets["FIT"], train, train_y)
                if early_stop:
                    valid_values = target[validation_role][valid]
                    valid_y = np.asarray(
                        valid_values > 0.0 if threshold == 0.0
                        else valid_values >= threshold, np.int8)
                    _require_binary_support(
                        valid_y,
                        name=f"{validation_role}:SURVIVAL:{threshold:g}")
                    valid_weight = _balanced_group_class_weights(
                        validation_dataset, valid, valid_y)
                    model.set_params(
                        od_type="Iter", od_wait=config.early_stopping_rounds)
                    model.fit(
                        x_fit, train_y, sample_weight=fit_weight,
                        eval_set=Pool(
                            x_valid, valid_y, weight=valid_weight),
                        use_best_model=True, verbose=False)
                else:
                    model.fit(
                        x_fit, train_y, sample_weight=fit_weight,
                        verbose=False)
                fitted.append(model); trees_list.append(int(model.tree_count_))
                accumulated += np.asarray(
                    model.get_feature_importance(), np.float64)
            models = tuple(fitted)
            trees = tuple(trees_list)
        elif family == "HARD_PAIRLOGIT":
            pool = _pair_pool(
                datasets["FIT"], x_fit, train, train_target,
                capacity=config.capacity,
                hard_negative_multiple=config.hard_negative_multiple)
            model = CatBoostRanker(
                loss_function="PairLogitPairwise",
                eval_metric=f"NDCG:top={config.capacity}",
                iterations=budget(), random_seed=seed, **common)
            if early_stop:
                valid_pool = _pair_pool(
                    validation_dataset, x_valid, valid,
                    target[validation_role][valid], capacity=config.capacity,
                    hard_negative_multiple=config.hard_negative_multiple)
                model.set_params(
                    od_type="Iter", od_wait=config.early_stopping_rounds)
                model.fit(pool, eval_set=valid_pool,
                          use_best_model=True, verbose=False)
            else:
                model.fit(pool, verbose=False)
            accumulated = np.asarray(model.get_feature_importance(
                type="PredictionValuesChange"), np.float64)
            models = model
            trees = (int(model.tree_count_),)
        else:
            raise ConfirmationRefusal("capacity-stability family is unknown")
        top = np.argsort(-accumulated, kind="stable")[:20]
        importance = tuple({
            "feature": names[index], "importance": float(accumulated[index]),
        } for index in top if accumulated[index] > 0.0)
        return models, trees, importance

    def predict_family(
        family: str, models: object, role: str, indices: np.ndarray,
    ) -> np.ndarray:
        x = np.asarray(datasets[role].features[indices], np.float32)
        if family == "SURVIVAL_EXPECTED_VALUE":
            probability = np.column_stack([
                np.asarray(model.predict_proba(x)[:, 1], np.float64)
                for model in models  # type: ignore[union-attr]
            ])
            return survival_expected_value(
                probability, config.survival_thresholds_usd,
                config.survival_cap_usd)
        if family in {
                "BALANCED_TOPK", "DOLLAR_MARGIN_TOPK",
                "SOFT_TOPK_RELEVANCE"}:
            return np.asarray(
                models.predict_proba(x)[:, 1],  # type: ignore[union-attr]
                np.float64)
        return np.asarray(models.predict(x), np.float64)  # type: ignore[union-attr]

    family_results = []
    fold_tree_counts: dict[str, list[tuple[int, ...]]] = {
        family: [] for family in FAMILIES}
    for family in FAMILIES:
        fold_results = []
        oof_indices = []
        oof_scores = []
        for fold in folds:
            train_indices = np.asarray(fold["train_indices"], np.int64)
            validation_indices = np.asarray(
                fold["validation_indices"], np.int64)
            models, trees, importance = fit_family(
                family, train_indices, target["FIT"][train_indices],
                "FIT", validation_indices,
                iterations=config.fold_iterations, early_stop=False,
                seed=config.random_seed + int(fold["fold"]) * 100)
            score = predict_family(
                family, models, "FIT", validation_indices)
            fold_diagnostic = diagnostic("FIT", validation_indices, score)
            fold_results.append({
                "fold": fold["fold"],
                "train_days": fold["train_days"],
                "validation_days": fold["validation_days"],
                "tree_counts": trees,
                "top_feature_importance": importance,
                "diagnostic": fold_diagnostic,
            })
            fold_tree_counts[family].append(trees)
            oof_indices.append(validation_indices); oof_scores.append(score)
        joined_indices = np.concatenate(oof_indices)
        joined_scores = np.concatenate(oof_scores)
        order = np.argsort(joined_indices, kind="stable")
        oof_diagnostic = diagnostic(
            "FIT", joined_indices[order], joined_scores[order])
        final_models, final_trees, final_importance = fit_family(
            family, all_indices["FIT"], target["FIT"],
            "PLATT", all_indices["PLATT"],
            iterations=config.final_iterations, early_stop=True,
            seed=config.random_seed + 1_000 + FAMILY_SEED_OFFSET[family])
        final_diagnostics = {
            role: diagnostic(
                role, all_indices[role], predict_family(
                    family, final_models, role, all_indices[role]))
            for role in ("PLATT", "THRESHOLD")
        }
        row_core = {
            "family": family,
            "fold_results": tuple(fold_results),
            "fit_oof_diagnostic": oof_diagnostic,
            "final_tree_counts": final_trees,
            "final_top_feature_importance": final_importance,
            "final_diagnostics": final_diagnostics,
        }
        family_results.append({
            **row_core, "receipt_sha256": C.object_sha256(row_core)})
        if progress is not None:
            progress({
                "family": family,
                "fit_oof_capture": oof_diagnostic["overall"]
                    ["top_capacity_opportunity_capture"],
                "platt_capture": final_diagnostics["PLATT"]["overall"]
                    ["top_capacity_opportunity_capture"],
                "threshold_capture": final_diagnostics["THRESHOLD"]["overall"]
                    ["top_capacity_opportunity_capture"],
            })

    selected = max(family_results, key=lambda row: (
        float(row["fit_oof_diagnostic"]["overall"]
              ["top_capacity_opportunity_capture"]),
        -FAMILIES.index(str(row["family"]))))
    selected_family = str(selected["family"])

    # Matched OOF control: same folds and fixed complexity, but whole target
    # vectors are permuted only within each training asset-day.
    control_indices = []
    control_scores = []
    for fold, trees in zip(folds, fold_tree_counts[selected_family]):
        train_indices = np.asarray(fold["train_indices"], np.int64)
        validation_indices = np.asarray(fold["validation_indices"], np.int64)
        shuffled = _shuffle_within_groups(
            datasets["FIT"], target["FIT"][train_indices], train_indices,
            checkpoints["FIT"][train_indices],
            seed=config.random_seed + 10_000 + int(fold["fold"]),
            group_scope=GROUP_SCOPE)
        models, _, _ = fit_family(
            selected_family, train_indices, shuffled,
            "FIT", validation_indices, iterations=trees,
            early_stop=False,
            seed=config.random_seed + 20_000 + int(fold["fold"]))
        control_indices.append(validation_indices)
        control_scores.append(predict_family(
            selected_family, models, "FIT", validation_indices))
    joined_control_indices = np.concatenate(control_indices)
    joined_control_scores = np.concatenate(control_scores)
    order = np.argsort(joined_control_indices, kind="stable")
    oof_control = diagnostic(
        "FIT", joined_control_indices[order], joined_control_scores[order])

    final_trees = tuple(int(value) for value in selected["final_tree_counts"])
    shuffled_fit = _shuffle_within_groups(
        datasets["FIT"], target["FIT"], all_indices["FIT"],
        checkpoints["FIT"], seed=config.random_seed + 30_000,
        group_scope=GROUP_SCOPE)
    control_models, _, _ = fit_family(
        selected_family, all_indices["FIT"], shuffled_fit,
        "PLATT", all_indices["PLATT"],
        iterations=final_trees, early_stop=False,
        seed=config.random_seed + 40_000)
    threshold_control = diagnostic(
        "THRESHOLD", all_indices["THRESHOLD"], predict_family(
            selected_family, control_models, "THRESHOLD",
            all_indices["THRESHOLD"]))
    directory = Path(__file__).resolve().parent
    implementation = {
        "capacity_stability": C.file_sha256(Path(__file__)),
        "capacity_probe": C.file_sha256(
            directory / "confirmation_capacity_probe.py"),
        "candidate_rank": C.file_sha256(
            directory / "confirmation_candidate_rank.py"),
        "stopping": C.file_sha256(
            directory / "confirmation_stopping.py"),
    }
    core = {
        "schema": SCHEMA,
        "config": asdict(config),
        "config_sha256": config.receipt_sha256,
        "capacity_corpus_receipt_sha256": capacity_corpus_receipt_sha256,
        "preflight": preflight,
        "catboost_version": catboost.__version__,
        "feature_count": len(datasets["FIT"].feature_names),
        "feature_names_sha256": C.object_sha256(
            datasets["FIT"].feature_names),
        "inputs": {role: {
            "dataset_sha256": datasets[role].representation_sha256,
            "ledger_sha256": ledgers[role].representation_sha256,
        } for role in roles},
        "implementation_sha256": implementation,
        "folds": tuple({
            "fold": fold["fold"],
            "train_days": fold["train_days"],
            "validation_days": fold["validation_days"],
        } for fold in folds),
        "families": FAMILIES,
        "family_results": tuple(family_results),
        "selection_role": "FIT_FORWARD_OOF_ONLY",
        "selection_metric": "top_capacity_opportunity_capture",
        "selected_family": selected_family,
        "selected_platt_diagnostic": selected["final_diagnostics"]["PLATT"],
        "selected_threshold_diagnostic": selected["final_diagnostics"]
            ["THRESHOLD"],
        "selected_negative_control": {
            "name": "Q_OPTIMAL_SHUFFLED_WITHIN_TRAIN_ASSET_DAY",
            "fit_oof_diagnostic": oof_control,
            "threshold_diagnostic": threshold_control,
        },
        "economics_executed": False,
        "forward_open_count": 0,
        "h2_open_count": 0,
    }
    if progress is not None:
        progress({
            "selected_family": selected_family,
            "fit_oof_control_capture": oof_control["overall"]
                ["top_capacity_opportunity_capture"],
            "threshold_control_capture": threshold_control["overall"]
                ["top_capacity_opportunity_capture"],
        })
    return {**core, "receipt_sha256": C.object_sha256(core)}


__all__ = [
    "FAMILIES", "SCHEMA", "CapacityStabilityConfig",
    "capacity_dollar_margin_weights", "capacity_soft_relevance",
    "capacity_stability_preflight", "forward_day_folds",
    "run_capacity_stability_probe",
]
