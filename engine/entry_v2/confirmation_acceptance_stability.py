"""FIT-forward absolute-value acceptance after the relative rank gate.

The capacity ranker answers *which* candidates deserve a watch slot.  It does
not produce an absolute dollar scale and therefore cannot decide whether a
day's fourth-best candidate should be traded at all.  This module measures a
small conditional hurdle family on the fixed-watch corpus before the timing
path is revisited.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Final, Mapping, Sequence

import catboost
from catboost import CatBoostClassifier
import numpy as np

from . import common as C
from .confirmation import ConfirmationDataset, ConfirmationRefusal
from .confirmation_capacity_probe import (
    _balanced_group_class_weights, capacity_topk_labels,
)
from .confirmation_capacity_stability import forward_day_folds
from .confirmation_factorized_policy import select_top_capacity_series
from .confirmation_stopping import OracleActionLedger


SCHEMA: Final = "QRE2CONFACCEPTSTABILITY1"
ROLES: Final = ("FIT", "PLATT", "THRESHOLD")


@dataclass(frozen=True, slots=True)
class AcceptanceStabilityConfig:
    watch_age_sec: int = 30
    capacity: int = 4
    minimum_train_days: int = 12
    validation_days: int = 6
    fold_count: int = 3
    rank_iterations: int = 30
    acceptance_iterations: int = 30
    depth: int = 5
    rank_learning_rate: float = .05
    acceptance_learning_rate: float = .06
    rank_l2_leaf_reg: float = 12.0
    acceptance_l2_leaf_reg: float = 12.0
    rank_seed: int = 20260820
    acceptance_seed: int = 20261820
    control_seed: int = 20270820
    thread_count: int = 16
    value_hurdles_usd: tuple[float, ...] = (250.0, 400.0, 500.0, 600.0)
    score_thresholds: tuple[float, ...] = (
        .10, .20, .30, .40, .45, .50, .55, .60, .65, .70, .75,
        .80, .85, .90,
    )
    minimum_potential_mean_usd: float = 600.0
    minimum_portfolio_day_usd: float = 3_000.0

    def __post_init__(self) -> None:
        hurdles = tuple(float(value) for value in self.value_hurdles_usd)
        thresholds = tuple(float(value) for value in self.score_thresholds)
        if (not 0 <= self.watch_age_sec <= 300
                or not 1 <= self.capacity <= 12
                or not 2 <= self.minimum_train_days <= 120
                or not 1 <= self.validation_days <= 30
                or not 2 <= self.fold_count <= 8
                or not 5 <= self.rank_iterations <= 200
                or not 5 <= self.acceptance_iterations <= 200
                or not 3 <= self.depth <= 8
                or not 0 < self.rank_learning_rate <= .3
                or not 0 < self.acceptance_learning_rate <= .3
                or not 0 < self.rank_l2_leaf_reg <= 1_000
                or not 0 < self.acceptance_l2_leaf_reg <= 1_000
                or not 1 <= self.thread_count <= C.MAX_CPU_WORKERS
                or hurdles != tuple(sorted(set(hurdles))) or not hurdles
                or hurdles[0] <= 0.0
                or thresholds != tuple(sorted(set(thresholds)))
                or not thresholds or thresholds[0] <= 0.0
                or thresholds[-1] >= 1.0
                or self.minimum_potential_mean_usd <= 0.0
                or self.minimum_portfolio_day_usd <= 0.0):
            raise ConfirmationRefusal(
                "acceptance-stability configuration is invalid")

    @property
    def receipt_sha256(self) -> str:
        return C.object_sha256({"schema": SCHEMA, **asdict(self)})


def _validate(
    datasets: Mapping[str, ConfirmationDataset],
    ledgers: Mapping[str, OracleActionLedger],
) -> None:
    if set(datasets) != set(ROLES) or set(ledgers) != set(ROLES):
        raise ConfirmationRefusal("acceptance-stability role roster differs")
    for role in ROLES:
        datasets[role].validate(); ledgers[role].validate()
        if (ledgers[role].source_representation_sha256
                != datasets[role].representation_sha256
                or not np.array_equal(
                    ledgers[role].opportunity_id, datasets[role].opportunity_id)
                or len(set(np.asarray(datasets[role].series_id, str).tolist()))
                   != len(datasets[role].features)):
            raise ConfirmationRefusal(
                "acceptance-stability fixed-watch identity differs")
    if (datasets["FIT"].feature_names != datasets["PLATT"].feature_names
            or datasets["FIT"].feature_names
            != datasets["THRESHOLD"].feature_names
            or int(np.max(datasets["FIT"].day))
               >= int(np.min(datasets["PLATT"].day))
            or int(np.max(datasets["PLATT"].day))
               >= int(np.min(datasets["THRESHOLD"].day))):
        raise ConfirmationRefusal(
            "acceptance-stability schemas/chronology differ")


def _group_labels(dataset: ConfirmationDataset, indices: np.ndarray) -> np.ndarray:
    chosen = np.asarray(indices, np.int64)
    return np.asarray([
        f"{asset}:{int(day)}" for asset, day in zip(
            np.asarray(dataset.asset, str)[chosen],
            np.asarray(dataset.day, np.int64)[chosen])], str)


def _shuffle_within_asset_day(
    dataset: ConfirmationDataset, target: np.ndarray, *, seed: int,
) -> np.ndarray:
    values = np.asarray(target, np.int8)
    if values.shape != (len(dataset.features),):
        raise ConfirmationRefusal("acceptance control target differs")
    groups = _group_labels(dataset, np.arange(len(values), dtype=np.int64))
    rng = np.random.default_rng(seed)
    result = values.copy(); changed = False
    for group in np.unique(groups):
        indices = np.flatnonzero(groups == group)
        donor = rng.permutation(indices)
        result[indices] = values[donor]
        changed |= not np.array_equal(indices, donor)
    if not changed:
        raise ConfirmationRefusal("acceptance control shuffle was ineffective")
    return result


def acceptance_potential_diagnostic(
    dataset: ConfirmationDataset, target: np.ndarray, *,
    rank_score: np.ndarray, acceptance_score: np.ndarray,
    score_thresholds: Sequence[float], capacity: int,
    minimum_potential_mean_usd: float,
    minimum_portfolio_day_usd: float,
) -> Mapping[str, object]:
    """Measure a causal-score book against remaining-value potential only."""

    dataset.validate()
    q = np.asarray(target, np.float64)
    rank = np.asarray(rank_score, np.float64)
    score = np.asarray(acceptance_score, np.float64)
    if (q.shape != (len(dataset.features),) or rank.shape != q.shape
            or score.shape != q.shape or np.any(q < 0.0)
            or not np.all(np.isfinite(q))
            or not np.all(np.isfinite(rank))
            or not np.all(np.isfinite(score))):
        raise ConfirmationRefusal("acceptance diagnostic inputs differ")
    watched = set(select_top_capacity_series(
        dataset, rank, capacity=capacity))
    series = np.asarray(dataset.series_id, str)
    gate = np.isin(series, tuple(watched))
    groups = _group_labels(dataset, np.arange(len(q), dtype=np.int64))
    gated_groups = set(groups[gate].tolist())
    days = set(np.asarray(dataset.day, np.int64)[gate].tolist())
    if not gated_groups or not days:
        raise ConfirmationRefusal("acceptance diagnostic gate is empty")
    gated_total = float(q[gate].sum())
    rows = []
    for threshold in score_thresholds:
        accepted = gate & (score >= float(threshold))
        count = int(np.sum(accepted))
        covered = len(set(groups[accepted].tolist()))
        total = float(q[accepted].sum())
        mean = 0.0 if count == 0 else total / count
        minimum_groups = int(np.ceil(len(gated_groups) / 3.0))
        reasons = []
        if count < C.MIN_TRADES:
            reasons.append("POTENTIAL_TRADES_BELOW_MINIMUM")
        if mean < minimum_potential_mean_usd:
            reasons.append("POTENTIAL_MEAN_BELOW_MINIMUM")
        if covered < minimum_groups:
            reasons.append("POTENTIAL_DAY_COVERAGE_BELOW_MINIMUM")
        per_day = total / len(days)
        core = {
            "score_threshold": float(threshold),
            "accepted": count,
            "covered_asset_days": covered,
            "eligible_asset_days": len(gated_groups),
            "minimum_covered_asset_days": minimum_groups,
            "portfolio_days": len(days),
            "potential_total_usd": total,
            "potential_mean_usd": mean,
            "potential_usd_per_portfolio_day": per_day,
            "potential_goal_rate": (
                0.0 if count == 0 else float(np.mean(q[accepted] >= 600.0))),
            "gated_potential_capture": (
                0.0 if gated_total == 0.0 else total / gated_total),
            "feasible_laws": not reasons,
            "goal_potential": not reasons
                and per_day >= minimum_portfolio_day_usd,
            "reasons": tuple(reasons),
        }
        rows.append({**core, "receipt_sha256": C.object_sha256(core)})
    feasible = [row for row in rows if row["feasible_laws"]]
    best = (None if not feasible else min(feasible, key=lambda row: (
        -float(row["potential_total_usd"]),
        float(row["score_threshold"]))))
    core = {
        "rows": len(q), "gated_candidates": int(np.sum(gate)),
        "gated_potential_total_usd": gated_total,
        "portfolio_days": len(days),
        "scorecards": tuple(rows),
        "status": "NO_FEASIBLE_POTENTIAL" if best is None else (
            "GOAL_POTENTIAL" if best["goal_potential"]
            else "FEASIBLE_BELOW_GOAL"),
        "selected_score_threshold": (
            None if best is None else best["score_threshold"]),
        "selected_scorecard": best,
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


def acceptance_stability_preflight(
    datasets: Mapping[str, ConfirmationDataset],
    ledgers: Mapping[str, OracleActionLedger], *,
    capacity_corpus_receipt_sha256: str,
    config: AcceptanceStabilityConfig = AcceptanceStabilityConfig(),
) -> Mapping[str, object]:
    _validate(datasets, ledgers)
    if len(capacity_corpus_receipt_sha256) != 64:
        raise ConfirmationRefusal("acceptance corpus receipt is malformed")
    folds = forward_day_folds(
        datasets["FIT"].day,
        minimum_train_days=config.minimum_train_days,
        validation_days=config.validation_days,
        fold_count=config.fold_count)
    target = np.asarray(ledgers["FIT"].q_optimal_usd, np.float64)
    supports = []
    for fold in folds:
        train = np.asarray(fold["train_indices"], np.int64)
        validation = np.asarray(fold["validation_indices"], np.int64)
        rank_y = capacity_topk_labels(
            datasets["FIT"], train, target[train], capacity=config.capacity)
        _balanced_group_class_weights(
            datasets["FIT"], train, rank_y)
        hurdles = {}
        for hurdle in config.value_hurdles_usd:
            y = np.asarray(target[train] >= hurdle, np.int8)
            _balanced_group_class_weights(datasets["FIT"], train, y)
            hurdles[str(hurdle)] = {
                "train_negative": int(np.sum(y == 0)),
                "train_positive": int(np.sum(y == 1)),
                "validation_positive": int(np.sum(target[validation] >= hurdle)),
                "validation_labels_consumed": False,
            }
        supports.append({
            "fold": fold["fold"], "train_days": fold["train_days"],
            "validation_days": fold["validation_days"],
            "rank_positive": int(np.sum(rank_y == 1)),
            "rank_negative": int(np.sum(rank_y == 0)),
            "hurdles": hurdles,
        })
    core = {
        "schema": "QRE2CONFACCEPTSTABILITYPREFLIGHT1",
        "config_sha256": config.receipt_sha256,
        "capacity_corpus_receipt_sha256": capacity_corpus_receipt_sha256,
        "fold_support": tuple(supports),
        "all_required_training_weights_constructed": True,
        "models_executed": False,
        "economics_executed": False,
        "forward_open_count": 0,
        "h2_open_count": 0,
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


def run_acceptance_stability_probe(
    datasets: Mapping[str, ConfirmationDataset],
    ledgers: Mapping[str, OracleActionLedger], *,
    capacity_corpus_receipt_sha256: str,
    final_rank_model: CatBoostClassifier,
    final_rank_model_sha256: str,
    config: AcceptanceStabilityConfig = AcceptanceStabilityConfig(),
    progress: Callable[[Mapping[str, object]], None] | None = None,
) -> Mapping[str, object]:
    """Select the conditional value hurdle from FIT-forward OOF potential."""

    _validate(datasets, ledgers)
    preflight = acceptance_stability_preflight(
        datasets, ledgers,
        capacity_corpus_receipt_sha256=capacity_corpus_receipt_sha256,
        config=config)
    if len(final_rank_model_sha256) != 64:
        raise ConfirmationRefusal("acceptance final rank identity is malformed")
    folds = forward_day_folds(
        datasets["FIT"].day,
        minimum_train_days=config.minimum_train_days,
        validation_days=config.validation_days,
        fold_count=config.fold_count)
    target = {role: np.asarray(ledgers[role].q_optimal_usd, np.float64)
              for role in ROLES}
    common = dict(
        depth=config.depth, thread_count=config.thread_count,
        allow_writing_files=False, verbose=False)
    rank_fold_cache = []
    for fold in folds:
        train = np.asarray(fold["train_indices"], np.int64)
        validation = np.asarray(fold["validation_indices"], np.int64)
        rank_y = capacity_topk_labels(
            datasets["FIT"], train, target["FIT"][train],
            capacity=config.capacity)
        rank_weight = _balanced_group_class_weights(
            datasets["FIT"], train, rank_y)
        rank_model = CatBoostClassifier(
            loss_function="Logloss", eval_metric="PRAUC:type=Classic",
            iterations=config.rank_iterations,
            learning_rate=config.rank_learning_rate,
            l2_leaf_reg=config.rank_l2_leaf_reg,
            random_seed=config.rank_seed + int(fold["fold"]),
            **common)
        rank_model.fit(
            datasets["FIT"].features[train], rank_y,
            sample_weight=rank_weight, verbose=False)
        rank_fold_cache.append((
            fold, train, validation,
            np.asarray(rank_model.predict_proba(
                datasets["FIT"].features[validation])[:, 1], np.float64),
            int(rank_model.tree_count_)))
    family_results = []
    oof_cache = {}
    for family_ordinal, hurdle in enumerate(config.value_hurdles_usd):
        joined_indices = []; rank_scores = []; acceptance_scores = []
        fold_rows = []
        for fold, train, validation, r_score, rank_trees in rank_fold_cache:
            y = np.asarray(target["FIT"][train] >= hurdle, np.int8)
            weight = _balanced_group_class_weights(
                datasets["FIT"], train, y)
            model = CatBoostClassifier(
                loss_function="Logloss", eval_metric="PRAUC:type=Classic",
                iterations=config.acceptance_iterations,
                learning_rate=config.acceptance_learning_rate,
                l2_leaf_reg=config.acceptance_l2_leaf_reg,
                random_seed=(config.acceptance_seed
                             + family_ordinal * 100 + int(fold["fold"])),
                **common)
            model.fit(
                datasets["FIT"].features[train], y,
                sample_weight=weight, verbose=False)
            a_score = np.asarray(model.predict_proba(
                datasets["FIT"].features[validation])[:, 1], np.float64)
            diagnostic = acceptance_potential_diagnostic(
                datasets["FIT"].subset(np.isin(
                    np.arange(len(datasets["FIT"].features)), validation)),
                target["FIT"][validation], rank_score=r_score,
                acceptance_score=a_score,
                score_thresholds=config.score_thresholds,
                capacity=config.capacity,
                minimum_potential_mean_usd=config.minimum_potential_mean_usd,
                minimum_portfolio_day_usd=config.minimum_portfolio_day_usd)
            fold_rows.append({
                "fold": fold["fold"], "diagnostic": diagnostic,
                "rank_tree_count": rank_trees,
                "acceptance_tree_count": int(model.tree_count_),
            })
            joined_indices.append(validation)
            rank_scores.append(r_score); acceptance_scores.append(a_score)
        indices = np.concatenate(joined_indices)
        rank_score = np.concatenate(rank_scores)
        acceptance_score = np.concatenate(acceptance_scores)
        order = np.argsort(indices, kind="stable")
        indices = indices[order]; rank_score = rank_score[order]
        acceptance_score = acceptance_score[order]
        subset_mask = np.isin(
            np.arange(len(datasets["FIT"].features)), indices)
        oof_diagnostic = acceptance_potential_diagnostic(
            datasets["FIT"].subset(subset_mask), target["FIT"][indices],
            rank_score=rank_score, acceptance_score=acceptance_score,
            score_thresholds=config.score_thresholds,
            capacity=config.capacity,
            minimum_potential_mean_usd=config.minimum_potential_mean_usd,
            minimum_portfolio_day_usd=config.minimum_portfolio_day_usd)
        oof_cache[hurdle] = (indices, rank_score, acceptance_score)
        row_core = {
            "value_hurdle_usd": hurdle,
            "fold_results": tuple(fold_rows),
            "fit_oof_diagnostic": oof_diagnostic,
        }
        family_results.append({**row_core,
                               "receipt_sha256": C.object_sha256(row_core)})
        if progress is not None:
            progress({
                "hurdle": hurdle, "status": oof_diagnostic["status"],
                "selected": oof_diagnostic["selected_scorecard"],
            })
    selectable = [row for row in family_results
                  if row["fit_oof_diagnostic"]["selected_scorecard"] is not None]
    if not selectable:
        selected = None
    else:
        selected = min(selectable, key=lambda row: (
            -float(row["fit_oof_diagnostic"]["selected_scorecard"]
                   ["potential_total_usd"]),
            float(row["value_hurdle_usd"])))

    final = None; control = None
    if selected is not None:
        hurdle = float(selected["value_hurdle_usd"])
        score_threshold = float(selected["fit_oof_diagnostic"]
                                ["selected_score_threshold"])
        y = np.asarray(target["FIT"] >= hurdle, np.int8)
        weight = _balanced_group_class_weights(
            datasets["FIT"], np.arange(len(y), dtype=np.int64), y)
        model = CatBoostClassifier(
            loss_function="Logloss", eval_metric="PRAUC:type=Classic",
            iterations=config.acceptance_iterations,
            learning_rate=config.acceptance_learning_rate,
            l2_leaf_reg=config.acceptance_l2_leaf_reg,
            random_seed=config.acceptance_seed + 1_000,
            **common)
        model.fit(datasets["FIT"].features, y,
                  sample_weight=weight, verbose=False)
        rank_score = {role: np.asarray(final_rank_model.predict_proba(
            datasets[role].features)[:, 1], np.float64) for role in ROLES}
        acceptance_score = {role: np.asarray(model.predict_proba(
            datasets[role].features)[:, 1], np.float64) for role in ROLES}
        final = {role: acceptance_potential_diagnostic(
            datasets[role], target[role], rank_score=rank_score[role],
            acceptance_score=acceptance_score[role],
            score_thresholds=(score_threshold,), capacity=config.capacity,
            minimum_potential_mean_usd=config.minimum_potential_mean_usd,
            minimum_portfolio_day_usd=config.minimum_portfolio_day_usd)
            for role in ("PLATT", "THRESHOLD")}

        # Matched control uses the selected hurdle and fixed cutoff.  Family
        # and threshold are never reselected on the shuffled labels.
        control_fold_scores = []
        indices, control_rank, _ = oof_cache[hurdle]
        for fold in folds:
            train = np.asarray(fold["train_indices"], np.int64)
            validation = np.asarray(fold["validation_indices"], np.int64)
            local_y = np.asarray(target["FIT"] >= hurdle, np.int8)
            shuffled = _shuffle_within_asset_day(
                datasets["FIT"].subset(np.isin(
                    np.arange(len(datasets["FIT"].features)), train)),
                local_y[train], seed=config.control_seed + int(fold["fold"]))
            control_weight = _balanced_group_class_weights(
                datasets["FIT"], train, shuffled)
            control_model = CatBoostClassifier(
                loss_function="Logloss", eval_metric="PRAUC:type=Classic",
                iterations=config.acceptance_iterations,
                learning_rate=config.acceptance_learning_rate,
                l2_leaf_reg=config.acceptance_l2_leaf_reg,
                random_seed=config.control_seed + 100 + int(fold["fold"]),
                **common)
            control_model.fit(
                datasets["FIT"].features[train], shuffled,
                sample_weight=control_weight, verbose=False)
            control_fold_scores.append(np.asarray(
                control_model.predict_proba(
                    datasets["FIT"].features[validation])[:, 1], np.float64))
        control_score = np.concatenate(control_fold_scores)
        control_order = np.argsort(np.concatenate([
            np.asarray(fold["validation_indices"], np.int64)
            for fold in folds]), kind="stable")
        control = acceptance_potential_diagnostic(
            datasets["FIT"].subset(np.isin(
                np.arange(len(datasets["FIT"].features)), indices)),
            target["FIT"][indices], rank_score=control_rank,
            acceptance_score=control_score[control_order],
            score_thresholds=(score_threshold,), capacity=config.capacity,
            minimum_potential_mean_usd=config.minimum_potential_mean_usd,
            minimum_portfolio_day_usd=config.minimum_portfolio_day_usd)

    core = {
        "schema": SCHEMA, "config": asdict(config),
        "config_sha256": config.receipt_sha256,
        "capacity_corpus_receipt_sha256": capacity_corpus_receipt_sha256,
        "preflight": preflight,
        "catboost_version": catboost.__version__,
        "final_rank_model_sha256": final_rank_model_sha256,
        "family_results": tuple(family_results),
        "selection_role": "FIT_FORWARD_OOF_ONLY",
        "selection_metric": "MAX_POTENTIAL_DOLLARS_SUBJECT_TO_MEAN_COUNT_COVERAGE",
        "selected_value_hurdle_usd": (
            None if selected is None else selected["value_hurdle_usd"]),
        "selected_score_threshold": (
            None if selected is None else selected["fit_oof_diagnostic"]
            ["selected_score_threshold"]),
        "final_diagnostics": final,
        "selected_negative_control_fit_oof": control,
        "implementation_sha256": C.file_sha256(Path(__file__)),
        "economics_executed": False,
        "diagnostic_scope": "CANDIDATE_REMAINING_OPPORTUNITY_NOT_REPLAY_PNL",
        "forward_open_count": 0,
        "h2_open_count": 0,
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


__all__ = [
    "AcceptanceStabilityConfig", "SCHEMA",
    "acceptance_potential_diagnostic", "acceptance_stability_preflight",
    "run_acceptance_stability_probe",
]
