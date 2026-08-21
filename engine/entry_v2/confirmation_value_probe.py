"""Dollar-aligned CatBoost probes for the Entry V2 stopping formulation.

This module is deliberately diagnostic.  It asks whether causal tabular state
can learn three distinct oracle quantities without using replay economics to
tune the learner:

* remaining candidate opportunity, ``Q_optimal``;
* the signed benefit of entering now rather than waiting/passing; and
* the within-candidate ordering of timestamp-specific ``Q_enter``.

Ordinary AUC is not an acceptance criterion here.  The published diagnostics
are dollar correlations, within-candidate ordering, whole-series entry regret,
value capture, and score-band monotonicity.  Canonical replay remains a later,
strictly separate boundary.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Callable, Mapping, Sequence

import catboost
from catboost import CatBoostRanker, CatBoostRegressor, Pool
import numpy as np

from . import common as C
from .confirmation import ConfirmationDataset, ConfirmationRefusal
from .confirmation_diagnostics import registered_feature_sets
from .confirmation_stopping import OracleActionLedger


SCHEMA = "QRE2CONFVALUEPROBE1"


@dataclass(frozen=True, slots=True)
class ValueProbeConfig:
    iterations: int = 60
    depth: int = 5
    learning_rate: float = 0.08
    l2_leaf_reg: float = 10.0
    huber_delta_usd: float = 500.0
    random_seed: int = 20260819
    thread_count: int = 16
    early_stopping_rounds: int = 10

    def __post_init__(self) -> None:
        if (not 10 <= self.iterations <= 500 or not 3 <= self.depth <= 8
                or not 0 < self.learning_rate <= .3
                or not 0 < self.l2_leaf_reg <= 1_000
                or not 10 <= self.huber_delta_usd <= 5_000
                or not 1 <= self.thread_count <= C.MAX_CPU_WORKERS
                or not 5 <= self.early_stopping_rounds < self.iterations):
            raise ConfirmationRefusal("value probe configuration is invalid")

    @property
    def receipt_sha256(self) -> str:
        return C.object_sha256({"schema": SCHEMA, **asdict(self)})


def _series_weights(dataset: ConfirmationDataset) -> np.ndarray:
    series = np.asarray(dataset.series_id, str)
    _, inverse, counts = np.unique(series, return_inverse=True, return_counts=True)
    weight = 1.0 / counts[inverse].astype(np.float64)
    return weight * (len(weight) / weight.sum())


def _series_groups(dataset: ConfirmationDataset) -> tuple[np.ndarray, np.ndarray]:
    """Return one global chronological order and contiguous group boundaries."""

    series = np.asarray(dataset.series_id, str)
    timestamps = np.asarray(dataset.snapshot_ts_ns, np.int64)
    ids = np.asarray(dataset.opportunity_id, str)
    order = np.lexsort((ids, timestamps, series)).astype(np.int64)
    ordered_series = series[order]
    boundaries = np.flatnonzero(np.r_[
        True, ordered_series[1:] != ordered_series[:-1], True])
    return order, boundaries


def _weighted_correlation(
    left: np.ndarray, right: np.ndarray, weight: np.ndarray,
) -> float:
    x = np.asarray(left, np.float64); y = np.asarray(right, np.float64)
    w = np.asarray(weight, np.float64); w = w / w.sum()
    dx = x - np.sum(w * x); dy = y - np.sum(w * y)
    denominator = math.sqrt(float(np.sum(w * dx * dx) * np.sum(w * dy * dy)))
    return 0.0 if denominator == 0 else float(np.sum(w * dx * dy) / denominator)


def _within_series_ordering(
    dataset: ConfirmationDataset, target: np.ndarray, score: np.ndarray,
) -> Mapping[str, object]:
    """Measure ordering inside candidates, excluding all tied comparisons."""

    target = np.asarray(target, np.float64); score = np.asarray(score, np.float64)
    correlations: list[float] = []
    correct = 0; compared = 0
    order, boundaries = _series_groups(dataset)
    for left_bound, right_bound in zip(boundaries[:-1], boundaries[1:]):
        indices = order[left_bound:right_bound]
        truth = target[indices]; prediction = score[indices]
        if np.ptp(truth) > 0 and np.ptp(prediction) > 0:
            value = np.corrcoef(truth, prediction)[0, 1]
            if math.isfinite(float(value)):
                correlations.append(float(value))
        left, right = np.triu_indices(len(indices), 1)
        truth_difference = truth[left] - truth[right]
        score_difference = prediction[left] - prediction[right]
        valid = (truth_difference != 0) & (score_difference != 0)
        compared += int(valid.sum())
        correct += int(np.sum(
            np.sign(truth_difference[valid]) == np.sign(score_difference[valid])))
    return {
        "within_series_correlation_mean": (
            None if not correlations else float(np.mean(correlations))),
        "within_series_correlation_groups": len(correlations),
        "within_series_pairwise_accuracy": (
            None if compared == 0 else float(correct / compared)),
        "within_series_compared_pairs": compared,
    }


def _score_bands(
    score: np.ndarray, realized: np.ndarray, *, band_count: int = 10,
) -> tuple[tuple[Mapping[str, object], ...], int]:
    """Equal-count score bands from low to high; no outcome-chosen cutoffs."""

    order = np.argsort(np.asarray(score, np.float64), kind="stable")
    chunks = tuple(chunk for chunk in np.array_split(order, band_count) if len(chunk))
    bands = []
    means = []
    values = np.asarray(realized, np.float64)
    predictions = np.asarray(score, np.float64)
    for ordinal, indices in enumerate(chunks, 1):
        mean = float(np.mean(values[indices])); means.append(mean)
        bands.append({
            "band": ordinal, "rows": len(indices),
            "score_min": float(np.min(predictions[indices])),
            "score_max": float(np.max(predictions[indices])),
            "realized_q_enter_mean_usd": mean,
            "realized_q_enter_median_usd": float(np.median(values[indices])),
            "realized_positive_rate": float(np.mean(values[indices] > 0.0)),
            "realized_goal_rate": float(np.mean(values[indices] >= 600.0)),
        })
    monotone_steps = int(np.sum(np.diff(np.asarray(means)) >= 0.0))
    return tuple(bands), monotone_steps


def timing_rank_diagnostic(
    dataset: ConfirmationDataset, ledger: OracleActionLedger, score: np.ndarray,
) -> Mapping[str, object]:
    """Evaluate a timestamp score against full-series entry value."""

    dataset.validate(); ledger.validate()
    prediction = np.asarray(score, np.float64)
    if (prediction.shape != (len(dataset.features),)
            or not np.all(np.isfinite(prediction))
            or not np.array_equal(dataset.opportunity_id, ledger.opportunity_id)):
        raise ConfirmationRefusal("timing rank diagnostic inputs differ")
    target = np.asarray(ledger.q_enter_usd, np.float64)
    weights = _series_weights(dataset)
    timestamps = np.asarray(dataset.snapshot_ts_ns, np.int64)
    chosen: list[int] = []; best: list[int] = []
    group_order, boundaries = _series_groups(dataset)
    for left, right in zip(boundaries[:-1], boundaries[1:]):
        indices = group_order[left:right]
        ranked = indices[np.lexsort((timestamps[indices], -prediction[indices]))]
        chosen.append(int(ranked[0]))
        best.append(int(indices[np.argmax(target[indices])]))
    chosen_array = np.asarray(chosen, np.int64)
    best_array = np.asarray(best, np.int64)
    chosen_value = target[chosen_array]; oracle_value = target[best_array]
    regret = oracle_value - chosen_value
    denominator = float(np.maximum(0.0, oracle_value).sum())
    ordering = _within_series_ordering(dataset, target, prediction)
    core = {
        "rows": len(target), "series": len(chosen_array),
        "series_balanced_q_enter_correlation": _weighted_correlation(
            prediction, target, weights),
        **ordering,
        "hindsight_argmax_positive_value_capture": (
            0.0 if denominator == 0 else
            float(np.maximum(0.0, chosen_value).sum() / denominator)),
        "hindsight_argmax_net_value_capture": (
            0.0 if denominator == 0 else float(chosen_value.sum() / denominator)),
        "hindsight_argmax_q_enter_mean_usd": float(np.mean(chosen_value)),
        "hindsight_argmax_goal_rate": float(np.mean(chosen_value >= 600.0)),
        "hindsight_argmax_nearopt_50_rate": float(np.mean(regret <= 50.0)),
        "hindsight_argmax_nearopt_100_rate": float(np.mean(regret <= 100.0)),
        "hindsight_argmax_median_regret_usd": float(np.median(regret)),
        "hindsight_argmax_p90_regret_usd": float(np.quantile(regret, .9)),
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


def value_stack_diagnostic(
    dataset: ConfirmationDataset, ledger: OracleActionLedger, *,
    opportunity_score: np.ndarray, advantage_score: np.ndarray,
    timing_score: np.ndarray,
) -> Mapping[str, object]:
    """Diagnose value, stopping margin, and timing without running economics."""

    dataset.validate(); ledger.validate()
    n = len(dataset.features)
    opportunity = np.asarray(opportunity_score, np.float64)
    advantage = np.asarray(advantage_score, np.float64)
    timing = np.asarray(timing_score, np.float64)
    if (any(value.shape != (n,) for value in (opportunity, advantage, timing))
            or any(not np.all(np.isfinite(value))
                   for value in (opportunity, advantage, timing))
            or not np.array_equal(dataset.opportunity_id, ledger.opportunity_id)):
        raise ConfirmationRefusal("value stack diagnostic inputs differ")
    weights = _series_weights(dataset)
    timing_diagnostic = timing_rank_diagnostic(dataset, ledger, timing)
    timestamps = np.asarray(dataset.snapshot_ts_ns, np.int64)
    chosen = []
    group_order, boundaries = _series_groups(dataset)
    for left, right in zip(boundaries[:-1], boundaries[1:]):
        indices = group_order[left:right]
        order = indices[np.lexsort((timestamps[indices], -timing[indices]))]
        chosen.append(int(order[0]))
    selected = np.asarray(chosen, np.int64)
    realized = np.asarray(ledger.q_enter_usd, np.float64)[selected]
    bands, monotone = _score_bands(opportunity[selected], realized)
    core = {
        "rows": n, "series": len(selected),
        "opportunity_q_optimal_correlation": _weighted_correlation(
            opportunity, ledger.q_optimal_usd, weights),
        "opportunity_q_optimal_rmse_usd": float(np.sqrt(np.average(
            (opportunity - ledger.q_optimal_usd) ** 2, weights=weights))),
        "advantage_correlation": _weighted_correlation(
            advantage, ledger.enter_advantage_usd, weights),
        "advantage_mae_usd": float(np.average(
            np.abs(advantage - ledger.enter_advantage_usd), weights=weights)),
        "selected_opportunity_q_enter_correlation": _weighted_correlation(
            opportunity[selected], realized, np.ones(len(selected))),
        "selected_advantage_correlation": _weighted_correlation(
            advantage[selected], ledger.enter_advantage_usd[selected],
            np.ones(len(selected))),
        "selected_opportunity_score_bands": bands,
        "selected_opportunity_monotone_steps": monotone,
        "selected_opportunity_possible_steps": max(0, len(bands) - 1),
        "timing": timing_diagnostic,
        "economics_executed": False,
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


def _rank_pool(
    dataset: ConfirmationDataset, features: np.ndarray, target: np.ndarray,
) -> Pool:
    series = np.asarray(dataset.series_id, str)
    timestamps = np.asarray(dataset.snapshot_ts_ns, np.int64)
    order = np.lexsort((timestamps, series))
    ordered_series = series[order]
    first = np.r_[True, ordered_series[1:] != ordered_series[:-1]]
    group_id = np.cumsum(first).astype(np.int64) - 1
    _, inverse, counts = np.unique(
        ordered_series, return_inverse=True, return_counts=True)
    group_weight = 1.0 / counts[inverse].astype(np.float64)
    return Pool(
        np.asarray(features, np.float32)[order],
        np.asarray(target, np.float64)[order],
        group_id=group_id, group_weight=group_weight)


def _shuffle_within_series(
    dataset: ConfirmationDataset, target: np.ndarray, *, seed: int,
) -> np.ndarray:
    """Destroy timestamp association while preserving every series' values."""

    rng = np.random.default_rng(seed)
    shuffled = np.asarray(target, np.float64).copy()
    order, boundaries = _series_groups(dataset)
    for left, right in zip(boundaries[:-1], boundaries[1:]):
        indices = order[left:right]
        shuffled[indices] = shuffled[indices][rng.permutation(len(indices))]
    return shuffled


def run_value_probe_matrix(
    datasets: Mapping[str, ConfirmationDataset],
    ledgers: Mapping[str, OracleActionLedger], *,
    feature_sets: Sequence[str] = ("PLUS_RECLAIM", "MAX_W300"),
    config: ValueProbeConfig = ValueProbeConfig(),
    progress: Callable[[Mapping[str, object]], None] | None = None,
) -> Mapping[str, object]:
    """Fit bounded value/rank probes on FIT, PLATT, then read THRESHOLD."""

    roles = ("FIT", "PLATT", "THRESHOLD")
    if set(datasets) != set(roles) or set(ledgers) != set(roles):
        raise ConfirmationRefusal("value probe role roster is incomplete")
    for role in roles:
        datasets[role].validate(); ledgers[role].validate()
        if (ledgers[role].source_representation_sha256
                != datasets[role].representation_sha256
                or not np.array_equal(
                    ledgers[role].opportunity_id, datasets[role].opportunity_id)):
            raise ConfirmationRefusal("value probe role ledger differs")
    fit = datasets["FIT"]; platt = datasets["PLATT"]
    if (fit.feature_names != platt.feature_names
            or fit.feature_names != datasets["THRESHOLD"].feature_names
            or int(np.max(fit.day)) >= int(np.min(platt.day))
            or int(np.max(platt.day)) >= int(np.min(datasets["THRESHOLD"].day))):
        raise ConfirmationRefusal("value probe schemas/chronology differ")
    masks = registered_feature_sets(fit.feature_names)
    unknown = set(feature_sets) - set(masks)
    if unknown:
        raise ConfirmationRefusal("value probe requested an unknown feature set")
    fit_weight = _series_weights(fit)
    common = dict(
        iterations=config.iterations, depth=config.depth,
        learning_rate=config.learning_rate, l2_leaf_reg=config.l2_leaf_reg,
        random_seed=config.random_seed, thread_count=config.thread_count,
        allow_writing_files=False, verbose=False,
        od_type="Iter", od_wait=config.early_stopping_rounds,
    )
    results = []
    for feature_set in feature_sets:
        columns = np.flatnonzero(masks[feature_set])
        x = {role: np.asarray(
            datasets[role].features[:, columns], np.float32) for role in roles}
        models = {
            "opportunity": CatBoostRegressor(
                loss_function=f"Huber:delta={config.huber_delta_usd:g}",
                eval_metric="RMSE", **common),
            "advantage": CatBoostRegressor(
                loss_function=f"Huber:delta={config.huber_delta_usd:g}",
                eval_metric="RMSE", **common),
        }
        for name, target_name in (
            ("opportunity", "q_optimal_usd"),
            ("advantage", "enter_advantage_usd"),
        ):
            models[name].fit(
                x["FIT"], np.asarray(getattr(ledgers["FIT"], target_name)),
                sample_weight=fit_weight,
                eval_set=(x["PLATT"], np.asarray(
                    getattr(ledgers["PLATT"], target_name))),
                use_best_model=True, verbose=False)
            if progress is not None:
                progress({"feature_set": feature_set, "fit": name,
                          "trees": int(models[name].tree_count_)})
        timing = CatBoostRanker(
            loss_function="YetiRankPairwise", eval_metric="QueryRMSE",
            **common)
        timing.fit(
            _rank_pool(fit, x["FIT"], ledgers["FIT"].q_enter_usd),
            eval_set=_rank_pool(
                platt, x["PLATT"], ledgers["PLATT"].q_enter_usd),
            use_best_model=True, verbose=False)
        if progress is not None:
            progress({"feature_set": feature_set, "fit": "timing_rank",
                      "trees": int(timing.tree_count_)})

        diagnostics = {}
        for role in roles:
            diagnostics[role] = value_stack_diagnostic(
                datasets[role], ledgers[role],
                opportunity_score=np.asarray(
                    models["opportunity"].predict(x[role]), np.float64),
                advantage_score=np.asarray(
                    models["advantage"].predict(x[role]), np.float64),
                timing_score=np.asarray(timing.predict(x[role]), np.float64))
        row_core = {
            "feature_set": feature_set, "feature_count": len(columns),
            "tree_counts": {
                "opportunity": int(models["opportunity"].tree_count_),
                "advantage": int(models["advantage"].tree_count_),
                "timing_rank": int(timing.tree_count_),
            },
            "diagnostics": diagnostics,
        }
        results.append({**row_core, "receipt_sha256": C.object_sha256(row_core)})

        control_target = _shuffle_within_series(
            fit, ledgers["FIT"].q_enter_usd,
            seed=config.random_seed + len(columns))
        control = CatBoostRanker(
            loss_function="YetiRankPairwise", eval_metric="QueryRMSE",
            iterations=config.iterations, depth=config.depth,
            learning_rate=config.learning_rate, l2_leaf_reg=config.l2_leaf_reg,
            random_seed=config.random_seed + 1,
            thread_count=config.thread_count, allow_writing_files=False,
            verbose=False)
        control.fit(_rank_pool(fit, x["FIT"], control_target), verbose=False)
        control_diagnostic = timing_rank_diagnostic(
            datasets["THRESHOLD"], ledgers["THRESHOLD"],
            np.asarray(control.predict(x["THRESHOLD"]), np.float64))
        control_core = {
            "control": "FIT_WITHIN_SERIES_Q_ENTER_SHUFFLE",
            "feature_set": feature_set, "feature_count": len(columns),
            "shuffle_seed": config.random_seed + len(columns),
            "tree_count": int(control.tree_count_),
            "threshold_diagnostic": control_diagnostic,
        }
        results.append({**control_core,
                        "receipt_sha256": C.object_sha256(control_core)})
        if progress is not None:
            progress({"feature_set": feature_set,
                      "fit": "within_series_shuffle_control",
                      "trees": int(control.tree_count_)})
        del x, models, timing, control
    core = {
        "schema": SCHEMA, "config": asdict(config),
        "config_sha256": config.receipt_sha256,
        "catboost_version": catboost.__version__,
        "feature_sets": tuple(feature_sets), "results": tuple(results),
        "economics_executed": False, "forward_open_count": 0,
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


__all__ = [
    "SCHEMA", "ValueProbeConfig", "run_value_probe_matrix",
    "timing_rank_diagnostic", "value_stack_diagnostic",
]
