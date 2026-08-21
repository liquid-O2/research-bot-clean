"""Robust CatBoost score families for formation-time candidate value.

All families see the same formation rows and causal features.  They differ
only in how the heavy-tailed non-negative candidate opportunity is presented
to the learner.  Model selection is capacity-aligned dollar capture on PLATT;
THRESHOLD is diagnostic-only and never selects a family.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable, Final, Mapping

import catboost
from catboost import CatBoostClassifier, CatBoostRanker, CatBoostRegressor, Pool
import numpy as np

from . import common as C
from .confirmation import ConfirmationDataset, ConfirmationRefusal
from .confirmation_candidate_rank import (
    TARGET_SCOPE, _feature_columns, _rank_pool, _shuffle_within_groups,
    candidate_formation_targets, candidate_rank_diagnostic,
    candidate_watch_rows,
)
from .confirmation_stopping import OracleActionLedger


SCHEMA: Final = "QRE2CONFCANDVALUE1"
FAMILIES: Final = (
    "YETI_RAW_USD", "YETI_LOG1P", "YETI_WINSOR_1800",
    "YETI_ORDINAL", "LOG1P_RMSE", "SURVIVAL_STACK",
)
ORDINAL_THRESHOLDS_USD: Final = (0.0, 100.0, 250.0, 500.0, 1_000.0, 1_800.0)
SURVIVAL_WIDTHS_USD: Final = (100.0, 150.0, 250.0, 500.0, 800.0, 2_200.0)


@dataclass(frozen=True, slots=True)
class CandidateValueConfig:
    feature_set: str = "MAX_PLUS_EPISODE"
    excluded_feature_names: tuple[str, ...] = ("phase_remaining_sec",)
    capacity: int = 12
    iterations: int = 100
    depth: int = 5
    learning_rate: float = 0.05
    l2_leaf_reg: float = 12.0
    random_seed: int = 20260819
    thread_count: int = 16
    early_stopping_rounds: int = 12

    def __post_init__(self) -> None:
        if (not self.feature_set or not 1 <= self.capacity <= 24
                or not 20 <= self.iterations <= 500
                or not 3 <= self.depth <= 8
                or not 0 < self.learning_rate <= .3
                or not 0 < self.l2_leaf_reg <= 1_000
                or not 1 <= self.thread_count <= C.MAX_CPU_WORKERS
                or not 5 <= self.early_stopping_rounds < self.iterations
                or len(set(self.excluded_feature_names))
                != len(self.excluded_feature_names)):
            raise ConfirmationRefusal("candidate-value configuration is invalid")

    @property
    def receipt_sha256(self) -> str:
        return C.object_sha256({"schema": SCHEMA, **asdict(self)})


def candidate_value_transform(family: str, target: np.ndarray) -> np.ndarray:
    values = np.asarray(target, np.float64)
    if np.any(values < 0.0) or not np.all(np.isfinite(values)):
        raise ConfirmationRefusal("candidate-value target is invalid")
    if family == "YETI_RAW_USD":
        return values.copy()
    if family == "YETI_LOG1P" or family == "LOG1P_RMSE":
        return np.log1p(values)
    if family == "YETI_WINSOR_1800":
        return np.minimum(values, 1_800.0)
    if family == "YETI_ORDINAL":
        thresholds = np.asarray(ORDINAL_THRESHOLDS_USD[1:], np.float64)
        return ((values > 0.0).astype(np.float64)
                + np.sum(values[:, None] >= thresholds[None, :], axis=1))
    raise ConfirmationRefusal("candidate-value transform family is unknown")


def survival_expected_score(probabilities: np.ndarray) -> np.ndarray:
    values = np.asarray(probabilities, np.float64)
    if (values.ndim != 2 or values.shape[1] != len(SURVIVAL_WIDTHS_USD)
            or not np.all(np.isfinite(values))
            or np.any(values < 0.0) or np.any(values > 1.0)):
        raise ConfirmationRefusal("candidate survival probabilities are invalid")
    # Project independently trained exceedance heads onto a valid survival
    # curve before integrating E[min(Q, 4000)].
    monotone = np.minimum.accumulate(values, axis=1)
    return monotone @ np.asarray(SURVIVAL_WIDTHS_USD, np.float64)


def _day_weights(dataset: ConfirmationDataset, indices: np.ndarray) -> np.ndarray:
    day = np.asarray(dataset.day, np.int64)[indices]
    _, inverse, counts = np.unique(day, return_inverse=True, return_counts=True)
    weights = 1.0 / counts[inverse].astype(np.float64)
    return weights * (len(weights) / weights.sum())


def _validate_roles(
    datasets: Mapping[str, ConfirmationDataset],
    ledgers: Mapping[str, OracleActionLedger],
) -> None:
    roles = ("FIT", "PLATT", "THRESHOLD")
    if set(datasets) != set(roles) or set(ledgers) != set(roles):
        raise ConfirmationRefusal("candidate-value role roster is incomplete")
    for role in roles:
        datasets[role].validate(); ledgers[role].validate()
        if (ledgers[role].source_representation_sha256
                != datasets[role].representation_sha256
                or not np.array_equal(
                    ledgers[role].opportunity_id,
                    datasets[role].opportunity_id)):
            raise ConfirmationRefusal("candidate-value role identity differs")
    if (datasets["FIT"].feature_names != datasets["PLATT"].feature_names
            or datasets["FIT"].feature_names
            != datasets["THRESHOLD"].feature_names
            or int(np.max(datasets["FIT"].day))
            >= int(np.min(datasets["PLATT"].day))
            or int(np.max(datasets["PLATT"].day))
            >= int(np.min(datasets["THRESHOLD"].day))):
        raise ConfirmationRefusal("candidate-value schemas/chronology differ")


def run_candidate_value_probe(
    datasets: Mapping[str, ConfirmationDataset],
    ledgers: Mapping[str, OracleActionLedger], *,
    config: CandidateValueConfig = CandidateValueConfig(),
    progress: Callable[[Mapping[str, object]], None] | None = None,
) -> Mapping[str, object]:
    """Fit robust formation-value families and evaluate one frozen winner."""

    _validate_roles(datasets, ledgers)
    roles = ("FIT", "PLATT", "THRESHOLD")
    columns, feature_names = _feature_columns(
        datasets["FIT"].feature_names,
        # Structural duck type: both configs bind these two fields.
        config,  # type: ignore[arg-type]
    )
    rows = {role: candidate_watch_rows(
        datasets[role], watch_ages_seconds=(0,), require_complete_grid=True)
        for role in roles}
    all_features = {role: np.asarray(
        datasets[role].features[:, columns], np.float32) for role in roles}
    features = {role: np.asarray(
        all_features[role][rows[role][0]], np.float32)
        for role in roles}
    target = {role: candidate_formation_targets(
        datasets[role], ledgers[role], indices=rows[role][0],
        checkpoints=rows[role][1]) for role in roles}
    weights = {role: _day_weights(datasets[role], rows[role][0])
               for role in roles}
    common = dict(
        depth=config.depth, learning_rate=config.learning_rate,
        l2_leaf_reg=config.l2_leaf_reg, random_seed=config.random_seed,
        thread_count=config.thread_count, allow_writing_files=False,
        verbose=False,
    )

    def rank_family(
        family: str, fit_target: np.ndarray, *,
        fixed_trees: int | None = None,
    ) -> tuple[dict[str, np.ndarray], dict[str, object]]:
        transformed = {
            "FIT": candidate_value_transform(family, fit_target),
            "PLATT": candidate_value_transform(family, target["PLATT"]),
        }
        fit_pool, _ = _rank_pool(
            datasets["FIT"], all_features["FIT"], transformed["FIT"],
            *rows["FIT"])
        kwargs = dict(
            loss_function=f"YetiRankPairwise:mode=NDCG;top={config.capacity}",
            iterations=(config.iterations if fixed_trees is None else fixed_trees),
            **common,
        )
        model = CatBoostRanker(**kwargs)
        if fixed_trees is None:
            platt_pool, _ = _rank_pool(
                datasets["PLATT"], all_features["PLATT"], transformed["PLATT"],
                *rows["PLATT"])
            model.set_params(
                eval_metric=f"NDCG:top={config.capacity}", od_type="Iter",
                od_wait=config.early_stopping_rounds)
            model.fit(
                fit_pool, eval_set=platt_pool, use_best_model=True,
                verbose=False)
        else:
            model.fit(fit_pool, verbose=False)
        scores = {role: np.asarray(
            model.predict(features[role]), np.float64) for role in roles}
        importance = np.asarray(model.get_feature_importance(
            type="PredictionValuesChange"), np.float64)
        top = np.argsort(-importance, kind="stable")[:15]
        return scores, {
            "tree_counts": (int(model.tree_count_),),
            "top_feature_importance": tuple({
                "feature": feature_names[index],
                "importance": float(importance[index]),
            } for index in top if importance[index] > 0.0),
        }

    def regression_family(
        fit_target: np.ndarray, *, fixed_trees: int | None = None,
    ) -> tuple[dict[str, np.ndarray], dict[str, object]]:
        model = CatBoostRegressor(
            loss_function="RMSE",
            iterations=(config.iterations if fixed_trees is None else fixed_trees),
            **common)
        fit_y = candidate_value_transform("LOG1P_RMSE", fit_target)
        if fixed_trees is None:
            model.set_params(
                od_type="Iter", od_wait=config.early_stopping_rounds)
            model.fit(
                features["FIT"], fit_y, sample_weight=weights["FIT"],
                eval_set=(features["PLATT"], candidate_value_transform(
                    "LOG1P_RMSE", target["PLATT"])),
                use_best_model=True, verbose=False)
        else:
            model.fit(
                features["FIT"], fit_y, sample_weight=weights["FIT"],
                verbose=False)
        scores = {role: np.asarray(
            model.predict(features[role]), np.float64) for role in roles}
        importance = np.asarray(model.get_feature_importance(), np.float64)
        top = np.argsort(-importance, kind="stable")[:15]
        return scores, {
            "tree_counts": (int(model.tree_count_),),
            "top_feature_importance": tuple({
                "feature": feature_names[index],
                "importance": float(importance[index]),
            } for index in top if importance[index] > 0.0),
        }

    def survival_family(
        fit_target: np.ndarray, *,
        fixed_trees: tuple[int, ...] | None = None,
    ) -> tuple[dict[str, np.ndarray], dict[str, object]]:
        predictions = {role: [] for role in roles}
        tree_counts = []
        accumulated_importance = np.zeros(len(columns), np.float64)
        thresholds = np.asarray(ORDINAL_THRESHOLDS_USD, np.float64)
        for ordinal, threshold in enumerate(thresholds):
            fit_y = (fit_target > 0.0 if threshold == 0.0
                     else fit_target >= threshold).astype(np.int8)
            platt_y = (target["PLATT"] > 0.0 if threshold == 0.0
                       else target["PLATT"] >= threshold).astype(np.int8)
            if len(np.unique(fit_y)) != 2 or len(np.unique(platt_y)) != 2:
                raise ConfirmationRefusal(
                    "candidate survival threshold lacks both classes")
            iterations = (config.iterations if fixed_trees is None
                          else int(fixed_trees[ordinal]))
            model = CatBoostClassifier(
                loss_function="Logloss", iterations=iterations,
                **{**common, "random_seed": config.random_seed + ordinal})
            if fixed_trees is None:
                model.set_params(
                    od_type="Iter", od_wait=config.early_stopping_rounds)
                model.fit(
                    features["FIT"], fit_y, sample_weight=weights["FIT"],
                    eval_set=(features["PLATT"], platt_y),
                    use_best_model=True, verbose=False)
            else:
                model.fit(
                    features["FIT"], fit_y, sample_weight=weights["FIT"],
                    verbose=False)
            for role in roles:
                predictions[role].append(np.asarray(
                    model.predict_proba(features[role])[:, 1], np.float64))
            tree_counts.append(int(model.tree_count_))
            accumulated_importance += np.asarray(
                model.get_feature_importance(), np.float64)
        scores = {role: survival_expected_score(
            np.column_stack(predictions[role])) for role in roles}
        top = np.argsort(-accumulated_importance, kind="stable")[:15]
        return scores, {
            "tree_counts": tuple(tree_counts),
            "top_feature_importance": tuple({
                "feature": feature_names[index],
                "importance": float(accumulated_importance[index]),
            } for index in top if accumulated_importance[index] > 0.0),
        }

    family_results = []
    score_by_family = {}
    complexity_by_family = {}
    for family in FAMILIES:
        if family.startswith("YETI_"):
            scores, metadata = rank_family(family, target["FIT"])
        elif family == "LOG1P_RMSE":
            scores, metadata = regression_family(target["FIT"])
        else:
            scores, metadata = survival_family(target["FIT"])
        diagnostics = {role: candidate_rank_diagnostic(
            datasets[role], ledgers[role], indices=rows[role][0],
            checkpoints=rows[role][1], score=scores[role],
            capacity=config.capacity, target=target[role],
            target_scope=TARGET_SCOPE) for role in roles}
        row_core = {
            "family": family, **metadata, "diagnostics": diagnostics,
        }
        family_results.append({
            **row_core, "receipt_sha256": C.object_sha256(row_core)})
        score_by_family[family] = scores
        complexity_by_family[family] = metadata["tree_counts"]
        if progress is not None:
            progress({
                "fit": family, "tree_counts": metadata["tree_counts"],
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
        seed=config.random_seed + 10_000)
    trees = tuple(map(int, complexity_by_family[selected_family]))
    if selected_family.startswith("YETI_"):
        control_scores, _ = rank_family(
            selected_family, shuffled, fixed_trees=trees[0])
    elif selected_family == "LOG1P_RMSE":
        control_scores, _ = regression_family(
            shuffled, fixed_trees=trees[0])
    else:
        control_scores, _ = survival_family(
            shuffled, fixed_trees=trees)
    control_diagnostic = candidate_rank_diagnostic(
        datasets["THRESHOLD"], ledgers["THRESHOLD"],
        indices=rows["THRESHOLD"][0], checkpoints=rows["THRESHOLD"][1],
        score=control_scores["THRESHOLD"], capacity=config.capacity,
        target=target["THRESHOLD"], target_scope=TARGET_SCOPE)
    if progress is not None:
        progress({
            "fit": f"{selected_family}_FIT_TARGET_SHUFFLE",
            "tree_counts": trees,
            "threshold_control_capture": control_diagnostic["overall"]
                ["top_capacity_opportunity_capture"],
        })

    core = {
        "schema": SCHEMA, "config": asdict(config),
        "config_sha256": config.receipt_sha256,
        "catboost_version": catboost.__version__,
        "feature_count": len(columns), "feature_names": feature_names,
        "target_scope": TARGET_SCOPE, "families": FAMILIES,
        "family_results": tuple(family_results),
        "selection_role": "PLATT",
        "selection_metric": "top_capacity_opportunity_capture",
        "selected_family": selected_family,
        "selected_threshold_diagnostic": selected["diagnostics"]["THRESHOLD"],
        "selected_negative_control": {
            "name": "FIT_FORMATION_Q_OPTIMAL_SHUFFLED_WITHIN_DAY",
            "seed": config.random_seed + 10_000,
            "tree_counts": trees,
            "threshold_diagnostic": control_diagnostic,
        },
        "economics_executed": False,
        "forward_open_count": 0, "h2_open_count": 0,
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


__all__ = [
    "FAMILIES", "ORDINAL_THRESHOLDS_USD", "SCHEMA",
    "SURVIVAL_WIDTHS_USD", "CandidateValueConfig",
    "candidate_value_transform", "run_candidate_value_probe",
    "survival_expected_score",
]
