"""Capacity-aligned CatBoost probes for rare top-value confirmation candidates.

The candidate rank diagnostic establishes whether causal features contain
cross-sectional value information.  This module tests cheap objectives that
explicitly address the rare top-k tail: a balanced top-k hurdle, a balanced
survival/expected-value stack, and dollar-weighted hard-negative pairs.
Model-family selection uses PLATT only; THRESHOLD is read-only.
"""

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
    CURRENT_TARGET_SCOPE, CandidateRankConfig, _fit_only_feature_columns,
    _probe_bindings, _shuffle_within_groups, candidate_rank_diagnostic,
    candidate_rank_targets, candidate_watch_rows,
)
from .confirmation_stopping import OracleActionLedger


SCHEMA: Final = "QRE2CONFCAPACITYPROBE1"
FAMILIES: Final = (
    "BALANCED_TOPK", "SURVIVAL_EXPECTED_VALUE", "HARD_PAIRLOGIT",
)
GROUP_SCOPE: Final = "ASSET_DAY_WATCH_AGE"


@dataclass(frozen=True, slots=True)
class CapacityProbeConfig:
    watch_age_sec: int = 30
    capacity: int = 4
    feature_set: str = "MAX_W300"
    excluded_feature_names: tuple[str, ...] = ()
    iterations: int = 80
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
                or not self.feature_set
                or len(set(self.excluded_feature_names))
                != len(self.excluded_feature_names)
                or not 20 <= self.iterations <= 500
                or not 3 <= self.depth <= 8
                or not 0 < self.learning_rate <= .3
                or not 0 < self.l2_leaf_reg <= 1_000
                or not 1 <= self.thread_count <= C.MAX_CPU_WORKERS
                or not 5 <= self.early_stopping_rounds < self.iterations
                or thresholds != tuple(sorted(set(thresholds)))
                or not thresholds or thresholds[0] != 0.0
                or not self.survival_cap_usd > thresholds[-1]
                or not 1 <= self.hard_negative_multiple <= 32):
            raise ConfirmationRefusal("capacity-probe configuration is invalid")

    @property
    def receipt_sha256(self) -> str:
        return C.object_sha256({"schema": SCHEMA, **asdict(self)})


def _group_labels(
    dataset: ConfirmationDataset, indices: np.ndarray,
) -> np.ndarray:
    selected = np.asarray(indices, np.int64)
    return np.asarray([
        f"{asset}:{int(day)}"
        for asset, day in zip(
            np.asarray(dataset.asset, str)[selected],
            np.asarray(dataset.day, np.int64)[selected])
    ], str)


def _fixed_watch_rows(
    dataset: ConfirmationDataset, *, watch_age_sec: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Select one deployable watch row while honoring the shared grid law."""

    ages = (0,) if watch_age_sec == 0 else (0, int(watch_age_sec))
    indices, checkpoints = candidate_watch_rows(
        dataset, watch_ages_seconds=ages, require_complete_grid=True)
    keep = checkpoints == int(watch_age_sec)
    selected = np.asarray(indices[keep], np.int64)
    selected_age = np.asarray(checkpoints[keep], np.int16)
    if (not len(selected) or np.any(selected_age != watch_age_sec)
            or len(set(np.asarray(dataset.series_id, str)[selected].tolist()))
            != len(selected)):
        raise ConfirmationRefusal("capacity fixed-watch selection differs")
    return selected, selected_age


def _require_binary_support(target: np.ndarray, *, name: str) -> None:
    values = np.asarray(target, np.int8)
    if values.ndim != 1 or set(np.unique(values)) != {0, 1}:
        raise ConfirmationRefusal(
            f"capacity label {name} is not two-class")


def capacity_topk_labels(
    dataset: ConfirmationDataset, indices: np.ndarray,
    target: np.ndarray, *, capacity: int,
) -> np.ndarray:
    """Deterministic positive-value top-k membership within asset-day."""

    selected = np.asarray(indices, np.int64)
    values = np.asarray(target, np.float64)
    if (values.shape != (len(selected),) or np.any(values < 0.0)
            or not np.all(np.isfinite(values)) or not 1 <= capacity <= 12):
        raise ConfirmationRefusal("capacity top-k inputs differ")
    groups = _group_labels(dataset, selected)
    ids = np.asarray(dataset.series_id, str)[selected]
    output = np.zeros(len(selected), np.int8)
    for group in np.unique(groups):
        local = np.flatnonzero(groups == group)
        ordered = local[np.lexsort((ids[local], -values[local]))]
        positive = ordered[values[ordered] > 0.0][:capacity]
        output[positive] = 1
    if len(np.unique(output)) != 2:
        raise ConfirmationRefusal("capacity top-k label is one-class")
    return output


def _balanced_group_class_weights(
    dataset: ConfirmationDataset, indices: np.ndarray, target: np.ndarray,
) -> np.ndarray:
    y = np.asarray(target, np.int8)
    if y.shape != (len(indices),) or set(np.unique(y)) != {0, 1}:
        raise ConfirmationRefusal("capacity class target is not two-class")
    groups = _group_labels(dataset, indices)
    _, inverse, counts = np.unique(groups, return_inverse=True,
                                   return_counts=True)
    base = 1.0 / counts[inverse].astype(np.float64)
    negative = float(base[y == 0].sum())
    positive = float(base[y == 1].sum())
    if negative <= 0.0 or positive <= 0.0:
        raise ConfirmationRefusal("capacity weighted class support is zero")
    weights = base * np.where(y == 1, .5 / positive, .5 / negative)
    return weights * (len(weights) / weights.sum())


def survival_expected_value(
    probabilities: np.ndarray, thresholds: tuple[float, ...], cap: float,
) -> np.ndarray:
    values = np.asarray(probabilities, np.float64)
    levels = np.asarray(thresholds, np.float64)
    if (values.ndim != 2 or values.shape[1] != len(levels)
            or not len(levels) or levels[0] != 0.0
            or np.any(np.diff(levels) <= 0.0) or not cap > levels[-1]
            or not np.all(np.isfinite(values))
            or np.any(values < 0.0) or np.any(values > 1.0)):
        raise ConfirmationRefusal("capacity survival probabilities are invalid")
    monotone = np.minimum.accumulate(values, axis=1)
    widths = np.diff(np.r_[levels, float(cap)])
    return monotone @ widths


def _pair_pool(
    dataset: ConfirmationDataset, features: np.ndarray,
    indices: np.ndarray, target: np.ndarray, *, capacity: int,
    hard_negative_multiple: int,
) -> Pool:
    selected = np.asarray(indices, np.int64)
    values = np.asarray(target, np.float64)
    groups = _group_labels(dataset, selected)
    ids = np.asarray(dataset.series_id, str)[selected]
    order = np.lexsort((ids, groups)).astype(np.int64)
    ordered_groups = groups[order]
    first = np.r_[True, ordered_groups[1:] != ordered_groups[:-1]]
    group_id = np.cumsum(first).astype(np.int64) - 1
    inverse = np.empty(len(order), np.int64)
    inverse[order] = np.arange(len(order), dtype=np.int64)
    pairs: list[tuple[int, int]] = []
    pair_weights: list[float] = []
    for group in np.unique(groups):
        local = np.flatnonzero(groups == group)
        ranked = local[np.lexsort((ids[local], -values[local]))]
        winners = ranked[values[ranked] > 0.0][:capacity]
        losers = ranked[len(winners):len(winners)
                        + capacity * hard_negative_multiple]
        for winner in winners:
            for loser in losers:
                gap = float(values[winner] - values[loser])
                if gap <= 0.0:
                    continue
                pairs.append((int(inverse[winner]), int(inverse[loser])))
                pair_weights.append(float(np.log1p(gap / 25.0)))
    if not pairs:
        raise ConfirmationRefusal("capacity hard-negative pair set is empty")
    return Pool(
        np.asarray(features, np.float32)[order], values[order],
        group_id=group_id, pairs=pairs, pairs_weight=pair_weights)


def run_capacity_probe(
    datasets: Mapping[str, ConfirmationDataset],
    ledgers: Mapping[str, OracleActionLedger], *,
    config: CapacityProbeConfig = CapacityProbeConfig(),
    progress: Callable[[Mapping[str, object]], None] | None = None,
) -> Mapping[str, object]:
    roles = ("FIT", "PLATT", "THRESHOLD")
    if set(datasets) != set(roles) or set(ledgers) != set(roles):
        raise ConfirmationRefusal("capacity-probe role roster is incomplete")
    for role in roles:
        datasets[role].validate(); ledgers[role].validate()
        if (ledgers[role].source_representation_sha256
                != datasets[role].representation_sha256
                or not np.array_equal(
                    ledgers[role].opportunity_id,
                    datasets[role].opportunity_id)):
            raise ConfirmationRefusal("capacity-probe role identity differs")
    if (datasets["FIT"].feature_names != datasets["PLATT"].feature_names
            or datasets["FIT"].feature_names
            != datasets["THRESHOLD"].feature_names
            or int(np.max(datasets["FIT"].day))
            >= int(np.min(datasets["PLATT"].day))
            or int(np.max(datasets["PLATT"].day))
            >= int(np.min(datasets["THRESHOLD"].day))):
        raise ConfirmationRefusal("capacity-probe schemas/chronology differ")

    rank_config = CandidateRankConfig(
        feature_set=config.feature_set,
        target_scope=CURRENT_TARGET_SCOPE,
        excluded_feature_names=config.excluded_feature_names,
        watch_ages_seconds=(0,), capacity=config.capacity,
        iterations=config.iterations, depth=config.depth,
        learning_rate=config.learning_rate, l2_leaf_reg=config.l2_leaf_reg,
        random_seed=config.random_seed, thread_count=config.thread_count,
        early_stopping_rounds=config.early_stopping_rounds)
    columns, feature_names, selector = _fit_only_feature_columns(
        datasets["FIT"], rank_config)
    inputs, implementation = _probe_bindings(datasets, ledgers)
    implementation = dict(implementation)
    implementation["capacity_probe"] = C.file_sha256(Path(__file__))
    rows = {role: _fixed_watch_rows(
        datasets[role], watch_age_sec=config.watch_age_sec) for role in roles}
    target = {role: candidate_rank_targets(
        datasets[role], ledgers[role], indices=rows[role][0],
        checkpoints=rows[role][1], target_scope=CURRENT_TARGET_SCOPE)
        for role in roles}
    features = {role: np.asarray(
        datasets[role].features[rows[role][0]][:, columns], np.float32)
        for role in roles}

    # Close all label-support boundaries before fitting the first family.  A
    # bad tail threshold must not be discovered after a successful earlier
    # model has already consumed the diagnostic budget.
    support = {}
    for role in roles:
        topk = capacity_topk_labels(
            datasets[role], rows[role][0], target[role],
            capacity=config.capacity)
        role_support = {
            "BALANCED_TOPK": {
                "negative": int(np.sum(topk == 0)),
                "positive": int(np.sum(topk == 1)),
            },
            "SURVIVAL_EXPECTED_VALUE": {},
        }
        for threshold in config.survival_thresholds_usd:
            binary = np.asarray(
                target[role] > 0.0 if threshold == 0.0
                else target[role] >= threshold, np.int8)
            _require_binary_support(
                binary, name=f"{role}:SURVIVAL:{threshold:g}")
            role_support["SURVIVAL_EXPECTED_VALUE"][str(threshold)] = {
                "negative": int(np.sum(binary == 0)),
                "positive": int(np.sum(binary == 1)),
            }
        support[role] = role_support
    common = dict(
        depth=config.depth, learning_rate=config.learning_rate,
        l2_leaf_reg=config.l2_leaf_reg, random_seed=config.random_seed,
        thread_count=config.thread_count, allow_writing_files=False,
        verbose=False)

    def diagnostic(role: str, score: np.ndarray) -> Mapping[str, object]:
        return candidate_rank_diagnostic(
            datasets[role], ledgers[role], indices=rows[role][0],
            checkpoints=rows[role][1], score=score,
            capacity=config.capacity, group_scope=GROUP_SCOPE,
            target=target[role], target_scope=CURRENT_TARGET_SCOPE)

    def fit_topk(
        fit_target: np.ndarray, *, fixed_trees: int | None = None,
    ) -> tuple[Mapping[str, np.ndarray], tuple[int, ...], tuple[Mapping[str, object], ...]]:
        labels = {role: capacity_topk_labels(
            datasets[role], rows[role][0],
            fit_target if role == "FIT" else target[role],
            capacity=config.capacity) for role in roles}
        model = CatBoostClassifier(
            loss_function="Logloss", eval_metric="PRAUC:type=Classic",
            iterations=(config.iterations if fixed_trees is None else fixed_trees),
            **common)
        fit_weights = _balanced_group_class_weights(
            datasets["FIT"], rows["FIT"][0], labels["FIT"])
        if fixed_trees is None:
            platt_weights = _balanced_group_class_weights(
                datasets["PLATT"], rows["PLATT"][0], labels["PLATT"])
            model.set_params(
                od_type="Iter", od_wait=config.early_stopping_rounds)
            model.fit(
                features["FIT"], labels["FIT"], sample_weight=fit_weights,
                eval_set=Pool(features["PLATT"], labels["PLATT"],
                              weight=platt_weights),
                use_best_model=True, verbose=False)
        else:
            model.fit(features["FIT"], labels["FIT"],
                      sample_weight=fit_weights, verbose=False)
        scores = {role: np.asarray(
            model.predict_proba(features[role])[:, 1], np.float64)
            for role in roles}
        importance = np.asarray(model.get_feature_importance(), np.float64)
        top = np.argsort(-importance, kind="stable")[:15]
        return scores, (int(model.tree_count_),), tuple({
            "feature": feature_names[index],
            "importance": float(importance[index]),
        } for index in top if importance[index] > 0.0)

    def fit_survival(
        fit_target: np.ndarray, *, fixed_trees: tuple[int, ...] | None = None,
    ) -> tuple[Mapping[str, np.ndarray], tuple[int, ...], tuple[Mapping[str, object], ...]]:
        predictions = {role: [] for role in roles}
        tree_counts = []
        importance = np.zeros(len(columns), np.float64)
        for ordinal, threshold in enumerate(config.survival_thresholds_usd):
            labels = {}
            for role in roles:
                values = fit_target if role == "FIT" else target[role]
                labels[role] = np.asarray(
                    values > 0.0 if threshold == 0.0
                    else values >= threshold, np.int8)
                _require_binary_support(
                    labels[role], name=f"{role}:SURVIVAL:{threshold:g}")
            trees = (config.iterations if fixed_trees is None
                     else int(fixed_trees[ordinal]))
            model = CatBoostClassifier(
                loss_function="Logloss", eval_metric="PRAUC:type=Classic",
                iterations=trees,
                **{**common, "random_seed": config.random_seed + ordinal})
            fit_weights = _balanced_group_class_weights(
                datasets["FIT"], rows["FIT"][0], labels["FIT"])
            if fixed_trees is None:
                platt_weights = _balanced_group_class_weights(
                    datasets["PLATT"], rows["PLATT"][0], labels["PLATT"])
                model.set_params(
                    od_type="Iter", od_wait=config.early_stopping_rounds)
                model.fit(
                    features["FIT"], labels["FIT"],
                    sample_weight=fit_weights,
                    eval_set=Pool(features["PLATT"], labels["PLATT"],
                                  weight=platt_weights),
                    use_best_model=True, verbose=False)
            else:
                model.fit(features["FIT"], labels["FIT"],
                          sample_weight=fit_weights, verbose=False)
            for role in roles:
                predictions[role].append(np.asarray(
                    model.predict_proba(features[role])[:, 1], np.float64))
            tree_counts.append(int(model.tree_count_))
            importance += np.asarray(model.get_feature_importance(), np.float64)
        scores = {role: survival_expected_value(
            np.column_stack(predictions[role]),
            config.survival_thresholds_usd, config.survival_cap_usd)
            for role in roles}
        top = np.argsort(-importance, kind="stable")[:15]
        return scores, tuple(tree_counts), tuple({
            "feature": feature_names[index],
            "importance": float(importance[index]),
        } for index in top if importance[index] > 0.0)

    def fit_pairs(
        fit_target: np.ndarray, *, fixed_trees: int | None = None,
    ) -> tuple[Mapping[str, np.ndarray], tuple[int, ...], tuple[Mapping[str, object], ...]]:
        fit_pool = _pair_pool(
            datasets["FIT"], features["FIT"], rows["FIT"][0],
            fit_target, capacity=config.capacity,
            hard_negative_multiple=config.hard_negative_multiple)
        model = CatBoostRanker(
            loss_function="PairLogitPairwise",
            eval_metric=f"NDCG:top={config.capacity}",
            iterations=(config.iterations if fixed_trees is None else fixed_trees),
            **common)
        if fixed_trees is None:
            platt_pool = _pair_pool(
                datasets["PLATT"], features["PLATT"], rows["PLATT"][0],
                target["PLATT"], capacity=config.capacity,
                hard_negative_multiple=config.hard_negative_multiple)
            model.set_params(
                od_type="Iter", od_wait=config.early_stopping_rounds)
            model.fit(fit_pool, eval_set=platt_pool,
                      use_best_model=True, verbose=False)
        else:
            model.fit(fit_pool, verbose=False)
        scores = {role: np.asarray(model.predict(features[role]), np.float64)
                  for role in roles}
        importance = np.asarray(model.get_feature_importance(
            type="PredictionValuesChange"), np.float64)
        top = np.argsort(-importance, kind="stable")[:15]
        return scores, (int(model.tree_count_),), tuple({
            "feature": feature_names[index],
            "importance": float(importance[index]),
        } for index in top if importance[index] > 0.0)

    fitters = {
        "BALANCED_TOPK": fit_topk,
        "SURVIVAL_EXPECTED_VALUE": fit_survival,
        "HARD_PAIRLOGIT": fit_pairs,
    }
    family_results = []
    complexity = {}
    for family in FAMILIES:
        scores, trees, importance = fitters[family](target["FIT"])
        diagnostics = {role: diagnostic(role, scores[role]) for role in roles}
        row_core = {
            "family": family, "tree_counts": trees,
            "top_feature_importance": importance,
            "diagnostics": diagnostics,
        }
        family_results.append({
            **row_core, "receipt_sha256": C.object_sha256(row_core)})
        complexity[family] = trees
        if progress is not None:
            progress({
                "fit": family, "tree_counts": trees,
                "platt_capture": diagnostics["PLATT"]["overall"]
                    ["top_capacity_opportunity_capture"],
            })
    selected = max(family_results, key=lambda row: (
        float(row["diagnostics"]["PLATT"]["overall"]
              ["top_capacity_opportunity_capture"]),
        -FAMILIES.index(str(row["family"]))))
    selected_family = str(selected["family"])
    shuffled = _shuffle_within_groups(
        datasets["FIT"], target["FIT"], *rows["FIT"],
        seed=config.random_seed + 10_000, group_scope=GROUP_SCOPE)
    trees = complexity[selected_family]
    if selected_family == "SURVIVAL_EXPECTED_VALUE":
        control_scores, _, _ = fit_survival(shuffled, fixed_trees=trees)
    elif selected_family == "BALANCED_TOPK":
        control_scores, _, _ = fit_topk(shuffled, fixed_trees=trees[0])
    else:
        control_scores, _, _ = fit_pairs(shuffled, fixed_trees=trees[0])
    control = diagnostic("THRESHOLD", control_scores["THRESHOLD"])
    if progress is not None:
        progress({
            "fit": f"{selected_family}_FIT_TARGET_SHUFFLE",
            "tree_counts": trees,
            "threshold_control_capture": control["overall"]
                ["top_capacity_opportunity_capture"],
        })
    core = {
        "schema": SCHEMA, "config": asdict(config),
        "config_sha256": config.receipt_sha256,
        "catboost_version": catboost.__version__,
        "feature_count": len(columns),
        "feature_names_sha256": C.object_sha256(feature_names),
        "fit_only_selector": {
            "receipt_sha256": selector.receipt_sha256,
            "input_feature_count": len(selector.input_feature_names),
            "selected_feature_count": len(selector.selected_indices),
            "constant_feature_count": len(selector.constant_feature_names),
            "duplicate_alias_count": len(selector.duplicate_aliases),
            "labels_used": False,
        },
        "inputs": inputs, "implementation_sha256": implementation,
        "target_scope": CURRENT_TARGET_SCOPE,
        "group_scope": GROUP_SCOPE, "families": FAMILIES,
        "label_support": support,
        "family_results": tuple(family_results),
        "selection_role": "PLATT",
        "selection_metric": "top_capacity_opportunity_capture",
        "selected_family": selected_family,
        "selected_threshold_diagnostic": selected["diagnostics"]["THRESHOLD"],
        "selected_negative_control": {
            "name": "FIT_CURRENT_Q_OPTIMAL_SHUFFLED_WITHIN_ASSET_DAY",
            "seed": config.random_seed + 10_000,
            "tree_counts": trees,
            "threshold_diagnostic": control,
        },
        "economics_executed": False,
        "forward_open_count": 0, "h2_open_count": 0,
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


__all__ = [
    "FAMILIES", "GROUP_SCOPE", "SCHEMA", "CapacityProbeConfig",
    "capacity_topk_labels", "run_capacity_probe", "survival_expected_value",
]
