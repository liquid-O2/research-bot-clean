"""CatBoost fitted optimal-stopping probes for Entry V2 confirmation.

The earlier value probe regressed the *hindsight* best remaining payoff.  That
is useful as an opportunity audit, but it is not the deployable value of
waiting: an online policy does not know which later snapshot will be best.

This module instead fits the two quantities used by an online stopping rule:

* expected certified payoff from entering at the current snapshot; and
* expected realized cashflow produced by the fitted policy after waiting.

The continuation head is initialized from the candidate-local oracle upper
bound, then refitted to the realized downstream cashflow of its own policy.
This is deliberately a bounded fitted-policy-iteration diagnostic.  It does
not run portfolio replay and it does not claim portfolio economics.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from types import MappingProxyType
from typing import Callable, Final, Mapping

import catboost
from catboost import CatBoostClassifier, CatBoostRegressor
import numpy as np

from . import common as C
from .confirmation import ConfirmationDataset, ConfirmationRefusal
from .confirmation_diagnostics import registered_feature_sets
from .confirmation_stopping import (
    ACTION_NAMES, ENTER, PASS, WAIT, OracleActionLedger,
)
from .corpus import ASSET_MULTIPLIER


SCHEMA: Final = "QRE2CONFSNELLPROBE2"
ESTIMATORS: Final = ("DIRECT_MEAN", "HURDLE_MEAN", "FACTORIZED_MEAN")


@dataclass(frozen=True, slots=True)
class SnellProbeConfig:
    feature_set: str = "MAX_PLUS_EPISODE"
    iterations: int = 60
    continuation_iterations: int = 3
    depth: int = 5
    learning_rate: float = 0.06
    l2_leaf_reg: float = 10.0
    random_seed: int = 20260819
    thread_count: int = 16
    early_stopping_rounds: int = 10

    def __post_init__(self) -> None:
        if (not self.feature_set
                or not 20 <= self.iterations <= 500
                or not 1 <= self.continuation_iterations <= 6
                or not 3 <= self.depth <= 8
                or not 0 < self.learning_rate <= .3
                or not 0 < self.l2_leaf_reg <= 1_000
                or not 1 <= self.thread_count <= C.MAX_CPU_WORKERS
                or not 5 <= self.early_stopping_rounds < self.iterations):
            raise ConfirmationRefusal("Snell probe configuration is invalid")

    @property
    def receipt_sha256(self) -> str:
        return C.object_sha256({"schema": SCHEMA, **asdict(self)})


def _series_weights(dataset: ConfirmationDataset) -> np.ndarray:
    series = np.asarray(dataset.series_id, str)
    _, inverse, counts = np.unique(series, return_inverse=True, return_counts=True)
    weight = 1.0 / counts[inverse].astype(np.float64)
    return weight * (len(weight) / weight.sum())


def _series_groups(dataset: ConfirmationDataset) -> tuple[np.ndarray, np.ndarray]:
    series = np.asarray(dataset.series_id, str)
    timestamps = np.asarray(dataset.snapshot_ts_ns, np.int64)
    ids = np.asarray(dataset.opportunity_id, str)
    order = np.lexsort((ids, timestamps, series)).astype(np.int64)
    ordered_series = series[order]
    boundaries = np.flatnonzero(np.r_[
        True, ordered_series[1:] != ordered_series[:-1], True])
    return order, boundaries


def entry_price_offset_usd(dataset: ConfirmationDataset) -> np.ndarray:
    """Return the exact known cost+entry displacement from series formation."""

    dataset.validate()
    n = len(dataset.features)
    offset = np.asarray(dataset.frozen_cost_usd, np.float64).copy()
    side = np.asarray(dataset.side, np.int8)
    mid2 = np.asarray(dataset.entry_mid2, np.int64)
    asset = np.asarray(dataset.asset, str)
    order, boundaries = _series_groups(dataset)
    for left, right in zip(boundaries[:-1], boundaries[1:]):
        indices = order[left:right]
        if (len(set(asset[indices].tolist())) != 1
                or len(set(side[indices].tolist())) != 1):
            raise ConfirmationRefusal("factorized series changes asset or side")
        factor = .5e-9 * float(ASSET_MULTIPLIER[str(asset[indices[0]])])
        offset[indices] += (
            int(side[indices[0]])
            * (mid2[indices] - int(mid2[indices[0]])).astype(np.float64)
            * factor)
    if not np.all(np.isfinite(offset)):
        raise ConfirmationRefusal("entry-price offset is non-finite")
    return offset


def factorized_entry_target(
    dataset: ConfirmationDataset, ledger: OracleActionLedger,
) -> np.ndarray:
    """Terminal move from formation, before the known current-entry offset."""

    if (ledger.source_representation_sha256 != dataset.representation_sha256
            or not np.array_equal(dataset.opportunity_id, ledger.opportunity_id)):
        raise ConfirmationRefusal("factorized entry target identity differs")
    result = (np.asarray(ledger.q_enter_usd, np.float64)
              + entry_price_offset_usd(dataset))
    if not np.all(np.isfinite(result)):
        raise ConfirmationRefusal("factorized entry target is non-finite")
    return result


def factorization_diagnostic(
    dataset: ConfirmationDataset, ledger: OracleActionLedger,
) -> Mapping[str, object]:
    """Measure how much known entry-price algebra removes within-series noise."""

    raw = np.asarray(ledger.q_enter_usd, np.float64)
    latent = factorized_entry_target(dataset, ledger)
    order, boundaries = _series_groups(dataset)
    raw_ranges = []
    latent_ranges = []
    same_exit_ranges = []
    exits = np.asarray(dataset.exit_ts_ns, np.int64)
    for left, right in zip(boundaries[:-1], boundaries[1:]):
        indices = order[left:right]
        raw_ranges.append(float(np.ptp(raw[indices])))
        latent_ranges.append(float(np.ptp(latent[indices])))
        for exit_ts in np.unique(exits[indices]):
            same_exit = indices[exits[indices] == exit_ts]
            if len(same_exit) > 1:
                same_exit_ranges.append(float(np.ptp(latent[same_exit])))
    core = {
        "rows": len(raw), "series": len(raw_ranges),
        "q_enter_within_series_range_median_usd": float(np.median(raw_ranges)),
        "factorized_within_series_range_median_usd": float(
            np.median(latent_ranges)),
        "factorized_within_series_range_p90_usd": float(
            np.quantile(latent_ranges, .9)),
        "factorized_same_exit_range_max_usd": (
            None if not same_exit_ranges else float(np.max(same_exit_ranges))),
        "factorized_constant_series_rate": float(np.mean(
            np.asarray(latent_ranges) <= .011)),
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


def _weighted_correlation(
    left: np.ndarray, right: np.ndarray, weight: np.ndarray,
) -> float:
    x = np.asarray(left, np.float64)
    y = np.asarray(right, np.float64)
    w = np.asarray(weight, np.float64)
    w = w / w.sum()
    dx = x - np.sum(w * x)
    dy = y - np.sum(w * y)
    denominator = math.sqrt(float(np.sum(w * dx * dx) * np.sum(w * dy * dy)))
    return 0.0 if denominator == 0 else float(np.sum(w * dx * dy) / denominator)


def _fit_affine_calibration(
    prediction: np.ndarray, target: np.ndarray, weight: np.ndarray,
) -> tuple[float, float]:
    """Fit a monotone weighted affine calibration on the PLATT role."""

    x = np.asarray(prediction, np.float64)
    y = np.asarray(target, np.float64)
    w = np.asarray(weight, np.float64)
    if (x.shape != y.shape or x.shape != w.shape or not len(x)
            or not np.all(np.isfinite(x)) or not np.all(np.isfinite(y))
            or not np.all(np.isfinite(w)) or np.any(w <= 0)):
        raise ConfirmationRefusal("affine calibration inputs are invalid")
    w = w / w.sum()
    x_mean = float(np.sum(w * x)); y_mean = float(np.sum(w * y))
    variance = float(np.sum(w * (x - x_mean) ** 2))
    covariance = float(np.sum(w * (x - x_mean) * (y - y_mean)))
    # A negative calibration slope reverses model ordering and is therefore a
    # refusal of useful signal, not a permissible calibration transformation.
    slope = 0.0 if variance <= 1e-12 else max(0.0, covariance / variance)
    intercept = y_mean - slope * x_mean
    return float(intercept), float(slope)


def _apply_affine(
    prediction: np.ndarray, calibration: tuple[float, float], *,
    nonnegative: bool = False,
) -> np.ndarray:
    intercept, slope = calibration
    result = intercept + slope * np.asarray(prediction, np.float64)
    if nonnegative:
        result = np.maximum(0.0, result)
    if not np.all(np.isfinite(result)):
        raise ConfirmationRefusal("affine calibration produced non-finite values")
    return result


def _sigmoid(value: np.ndarray) -> np.ndarray:
    x = np.asarray(value, np.float64)
    output = np.empty_like(x)
    positive = x >= 0
    output[positive] = 1.0 / (1.0 + np.exp(-x[positive]))
    exp_x = np.exp(x[~positive])
    output[~positive] = exp_x / (1.0 + exp_x)
    return output


def _fit_platt_calibration(
    raw_score: np.ndarray, target: np.ndarray, weight: np.ndarray,
) -> tuple[float, float]:
    """Two-parameter weighted logistic calibration with a monotone slope."""

    x = np.clip(np.asarray(raw_score, np.float64), -40.0, 40.0)
    y = np.asarray(target, np.float64)
    w = np.asarray(weight, np.float64)
    if (x.shape != y.shape or x.shape != w.shape or not len(x)
            or not np.all(np.isin(y, (0.0, 1.0)))
            or not np.all(np.isfinite(x)) or np.any(w <= 0)):
        raise ConfirmationRefusal("Platt calibration inputs are invalid")
    # CatBoost raw log-odds are already a sensible initialization.  Newton's
    # method only calibrates offset/scale and a tiny ridge prevents singular
    # Hessians without materially changing the solution.
    parameters = np.asarray([0.0, 1.0], np.float64)
    design = np.column_stack((np.ones(len(x), np.float64), x))
    normalized_weight = w / np.mean(w)
    ridge = 1e-8
    for _ in range(50):
        probability = _sigmoid(design @ parameters)
        gradient = design.T @ (normalized_weight * (probability - y))
        curvature = normalized_weight * probability * (1.0 - probability)
        hessian = design.T @ (design * curvature[:, None])
        hessian += np.eye(2) * ridge
        try:
            step = np.linalg.solve(hessian, gradient)
        except np.linalg.LinAlgError as exc:
            raise ConfirmationRefusal("Platt calibration Hessian is singular") from exc
        step = np.clip(step, -2.0, 2.0)
        parameters -= step
        parameters[1] = max(0.0, parameters[1])
        if float(np.max(np.abs(step))) < 1e-9:
            break
    if not np.all(np.isfinite(parameters)):
        raise ConfirmationRefusal("Platt calibration did not converge")
    return float(parameters[0]), float(parameters[1])


def _apply_platt(
    raw_score: np.ndarray, calibration: tuple[float, float],
) -> np.ndarray:
    intercept, slope = calibration
    result = _sigmoid(intercept + slope * np.asarray(raw_score, np.float64))
    if not np.all(np.isfinite(result)):
        raise ConfirmationRefusal("Platt calibration produced non-finite values")
    return result


def _common_parameters(config: SnellProbeConfig) -> Mapping[str, object]:
    return MappingProxyType({
        "iterations": config.iterations,
        "depth": config.depth,
        "learning_rate": config.learning_rate,
        "l2_leaf_reg": config.l2_leaf_reg,
        "random_seed": config.random_seed,
        "thread_count": config.thread_count,
        "allow_writing_files": False,
        "verbose": False,
        "od_type": "Iter",
        "od_wait": config.early_stopping_rounds,
    })


def immediate_value_diagnostic(
    dataset: ConfirmationDataset, ledger: OracleActionLedger,
    score: np.ndarray,
) -> Mapping[str, object]:
    """Proper-dollar and candidate-selection diagnostics for an entry head."""

    dataset.validate(); ledger.validate()
    prediction = np.asarray(score, np.float64)
    target = np.asarray(ledger.q_enter_usd, np.float64)
    if (prediction.shape != target.shape or not np.all(np.isfinite(prediction))
            or not np.array_equal(dataset.opportunity_id, ledger.opportunity_id)):
        raise ConfirmationRefusal("immediate value diagnostic inputs differ")
    weights = _series_weights(dataset)
    order, boundaries = _series_groups(dataset)
    chosen = []
    best = []
    for left, right in zip(boundaries[:-1], boundaries[1:]):
        indices = order[left:right]
        chosen.append(int(indices[np.argmax(prediction[indices])]))
        best.append(int(indices[np.argmax(target[indices])]))
    selected = np.asarray(chosen, np.int64)
    oracle = np.maximum(0.0, target[np.asarray(best, np.int64)])
    realized = target[selected]
    denominator = float(oracle.sum())
    residual = prediction - target
    core = {
        "rows": len(target), "series": len(selected),
        "series_balanced_rmse_usd": float(np.sqrt(np.average(
            residual ** 2, weights=weights))),
        "series_balanced_mae_usd": float(np.average(
            np.abs(residual), weights=weights)),
        "series_balanced_bias_usd": float(np.average(
            residual, weights=weights)),
        "series_balanced_correlation": _weighted_correlation(
            prediction, target, weights),
        # This argmax is intentionally labelled noncausal.  It isolates
        # timestamp ordering from the deployable stopping recursion below.
        "noncausal_argmax_realized_mean_usd": float(np.mean(realized)),
        "noncausal_argmax_realized_median_usd": float(np.median(realized)),
        "noncausal_argmax_goal_rate": float(np.mean(realized >= 600.0)),
        "noncausal_argmax_positive_rate": float(np.mean(realized > 0.0)),
        "noncausal_argmax_net_value_capture": (
            0.0 if denominator == 0 else float(realized.sum() / denominator)),
        "noncausal_argmax_positive_value_capture": (
            0.0 if denominator == 0 else
            float(np.maximum(0.0, realized).sum() / denominator)),
        "economics_executed": False,
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


def _fit_immediate_estimators(
    datasets: Mapping[str, ConfirmationDataset],
    ledgers: Mapping[str, OracleActionLedger],
    features: Mapping[str, np.ndarray], config: SnellProbeConfig,
    progress: Callable[[Mapping[str, object]], None] | None,
) -> tuple[Mapping[str, Mapping[str, np.ndarray]], Mapping[str, object]]:
    roles = ("FIT", "PLATT", "THRESHOLD")
    common = dict(_common_parameters(config))
    fit_weight = _series_weights(datasets["FIT"])
    platt_weight = _series_weights(datasets["PLATT"])
    fit_target = np.asarray(ledgers["FIT"].q_enter_usd, np.float64)
    platt_target = np.asarray(ledgers["PLATT"].q_enter_usd, np.float64)

    direct = CatBoostRegressor(loss_function="RMSE", eval_metric="RMSE", **common)
    direct.fit(
        features["FIT"], fit_target, sample_weight=fit_weight,
        eval_set=(features["PLATT"], platt_target),
        use_best_model=True, verbose=False)
    direct_raw = {role: np.asarray(
        direct.predict(features[role]), np.float64) for role in roles}
    direct_calibration = _fit_affine_calibration(
        direct_raw["PLATT"], platt_target, platt_weight)
    direct_score = {role: _apply_affine(
        direct_raw[role], direct_calibration) for role in roles}
    if progress is not None:
        progress({"fit": "DIRECT_MEAN", "trees": int(direct.tree_count_)})

    fit_positive = fit_target > 0.0
    platt_positive = platt_target > 0.0
    classifier = CatBoostClassifier(
        loss_function="Logloss", eval_metric="Logloss", **common)
    classifier.fit(
        features["FIT"], fit_positive.astype(np.int8),
        sample_weight=fit_weight,
        eval_set=(features["PLATT"], platt_positive.astype(np.int8)),
        use_best_model=True, verbose=False)
    win = CatBoostRegressor(loss_function="RMSE", eval_metric="RMSE", **common)
    win.fit(
        features["FIT"][fit_positive], fit_target[fit_positive],
        sample_weight=fit_weight[fit_positive],
        eval_set=(features["PLATT"][platt_positive],
                  platt_target[platt_positive]),
        use_best_model=True, verbose=False)
    fit_loss = ~fit_positive; platt_loss = ~platt_positive
    loss = CatBoostRegressor(loss_function="RMSE", eval_metric="RMSE", **common)
    loss.fit(
        features["FIT"][fit_loss], -fit_target[fit_loss],
        sample_weight=fit_weight[fit_loss],
        eval_set=(features["PLATT"][platt_loss],
                  -platt_target[platt_loss]),
        use_best_model=True, verbose=False)

    raw_probability = {role: np.asarray(classifier.predict(
        features[role], prediction_type="RawFormulaVal"), np.float64)
        for role in roles}
    raw_win = {role: np.asarray(win.predict(features[role]), np.float64)
               for role in roles}
    raw_loss = {role: np.asarray(loss.predict(features[role]), np.float64)
                for role in roles}
    probability_calibration = _fit_platt_calibration(
        raw_probability["PLATT"], platt_positive.astype(np.float64), platt_weight)
    win_calibration = _fit_affine_calibration(
        raw_win["PLATT"][platt_positive], platt_target[platt_positive],
        platt_weight[platt_positive])
    loss_calibration = _fit_affine_calibration(
        raw_loss["PLATT"][platt_loss], -platt_target[platt_loss],
        platt_weight[platt_loss])
    hurdle_score = {}
    for role in roles:
        probability = _apply_platt(
            raw_probability[role], probability_calibration)
        win_value = _apply_affine(
            raw_win[role], win_calibration, nonnegative=True)
        loss_value = _apply_affine(
            raw_loss[role], loss_calibration, nonnegative=True)
        hurdle_score[role] = (
            probability * win_value - (1.0 - probability) * loss_value)
    if progress is not None:
        progress({
            "fit": "HURDLE_MEAN", "classifier_trees": int(classifier.tree_count_),
            "win_trees": int(win.tree_count_), "loss_trees": int(loss.tree_count_),
        })

    # Offset model: CatBoost forecasts only the unknown terminal move from the
    # series' formation price.  The exact current-entry displacement and cost
    # are subtracted after prediction instead of approximated with tree splits.
    factorized_target = {
        role: factorized_entry_target(datasets[role], ledgers[role])
        for role in roles}
    factorized = CatBoostRegressor(
        loss_function="RMSE", eval_metric="RMSE", **common)
    factorized.fit(
        features["FIT"], factorized_target["FIT"],
        sample_weight=fit_weight,
        eval_set=(features["PLATT"], factorized_target["PLATT"]),
        use_best_model=True, verbose=False)
    factorized_raw = {role: np.asarray(
        factorized.predict(features[role]), np.float64) for role in roles}
    factorized_calibration = _fit_affine_calibration(
        factorized_raw["PLATT"], factorized_target["PLATT"], platt_weight)
    factorized_score = {
        role: (_apply_affine(
            factorized_raw[role], factorized_calibration)
            - entry_price_offset_usd(datasets[role]))
        for role in roles}
    if progress is not None:
        progress({"fit": "FACTORIZED_MEAN",
                  "trees": int(factorized.tree_count_)})

    predictions = MappingProxyType({
        "DIRECT_MEAN": MappingProxyType(direct_score),
        "HURDLE_MEAN": MappingProxyType(hurdle_score),
        "FACTORIZED_MEAN": MappingProxyType(factorized_score),
    })
    meta = {
        "DIRECT_MEAN": {
            "tree_count": int(direct.tree_count_),
            "affine_calibration": direct_calibration,
        },
        "HURDLE_MEAN": {
            "tree_counts": {
                "positive_probability": int(classifier.tree_count_),
                "positive_magnitude": int(win.tree_count_),
                "nonpositive_magnitude": int(loss.tree_count_),
            },
            "probability_platt_calibration": probability_calibration,
            "win_affine_calibration": win_calibration,
            "loss_affine_calibration": loss_calibration,
        },
        "FACTORIZED_MEAN": {
            "tree_count": int(factorized.tree_count_),
            "latent_affine_calibration": factorized_calibration,
            "target": "TERMINAL_MOVE_FROM_FORMATION_MINUS_EXACT_ENTRY_OFFSET",
        },
    }
    return predictions, meta


def fitted_policy_recursion(
    dataset: ConfirmationDataset, ledger: OracleActionLedger, *,
    immediate_score: np.ndarray, continuation_score: np.ndarray,
) -> Mapping[str, np.ndarray]:
    """Apply a causal stopping rule and propagate its realized cashflow."""

    dataset.validate(); ledger.validate()
    enter = np.asarray(immediate_score, np.float64)
    continuation = np.asarray(continuation_score, np.float64)
    realized_enter = np.asarray(ledger.q_enter_usd, np.float64)
    n = len(realized_enter)
    if (enter.shape != (n,) or continuation.shape != (n,)
            or not np.all(np.isfinite(enter))
            or not np.all(np.isfinite(continuation))
            or not np.array_equal(dataset.opportunity_id, ledger.opportunity_id)):
        raise ConfirmationRefusal("fitted policy recursion inputs differ")
    action = np.full(n, PASS, np.int8)
    realized_value = np.zeros(n, np.float64)
    predicted_value = np.zeros(n, np.float64)
    wait_target = np.zeros(n, np.float64)
    selected: list[int] = []
    starts: list[int] = []
    order, boundaries = _series_groups(dataset)
    for left, right in zip(boundaries[:-1], boundaries[1:]):
        indices = order[left:right]
        starts.append(int(indices[0]))
        for position in range(len(indices) - 1, -1, -1):
            index = int(indices[position])
            has_future = position + 1 < len(indices)
            downstream = (float(realized_value[indices[position + 1]])
                          if has_future else 0.0)
            wait_target[index] = downstream
            effective_continuation = (
                float(continuation[index]) if has_future else 0.0)
            if enter[index] > max(0.0, effective_continuation):
                action[index] = ENTER
                realized_value[index] = realized_enter[index]
                predicted_value[index] = enter[index]
            elif has_future and effective_continuation > 0.0:
                action[index] = WAIT
                realized_value[index] = downstream
                predicted_value[index] = effective_continuation
            else:
                action[index] = PASS
                realized_value[index] = 0.0
                predicted_value[index] = 0.0
        for index in indices:
            if action[index] == ENTER:
                selected.append(int(index)); break
            if action[index] == PASS:
                break
    return MappingProxyType({
        "action": action,
        "realized_value": realized_value,
        "predicted_value": predicted_value,
        "continuation_target": wait_target,
        "selected_indices": np.asarray(selected, np.int64),
        "series_start_indices": np.asarray(starts, np.int64),
    })


def fitted_policy_diagnostic(
    dataset: ConfirmationDataset, ledger: OracleActionLedger,
    recursion: Mapping[str, np.ndarray], *, iteration: int,
) -> Mapping[str, object]:
    """Report candidate-local policy value without calling it economics."""

    starts = np.asarray(recursion["series_start_indices"], np.int64)
    selected = np.asarray(recursion["selected_indices"], np.int64)
    realized_state = np.asarray(recursion["realized_value"], np.float64)
    predicted_state = np.asarray(recursion["predicted_value"], np.float64)
    action = np.asarray(recursion["action"], np.int8)
    oracle = np.asarray(ledger.q_optimal_usd, np.float64)[starts]
    realized = realized_state[starts]
    prediction = predicted_state[starts]
    regret = oracle - realized
    denominator = float(np.maximum(0.0, oracle).sum())
    entered = np.asarray(ledger.q_enter_usd, np.float64)[selected]
    true_action = np.asarray(ledger.optimal_action, np.int8)
    confusion = {
        ACTION_NAMES[actual]: {
            ACTION_NAMES[predicted]: int(np.count_nonzero(
                (true_action == actual) & (action == predicted)))
            for predicted in (PASS, WAIT, ENTER)
        } for actual in (PASS, WAIT, ENTER)
    }
    core = {
        "iteration": int(iteration),
        "rows": len(action), "series": len(starts),
        "entry_count": len(selected),
        "entry_rate": float(len(selected) / len(starts)),
        "pass_rate": float(1.0 - len(selected) / len(starts)),
        "candidate_local_net_total_usd": float(realized.sum()),
        "candidate_local_net_mean_usd": float(np.mean(realized)),
        "candidate_local_oracle_total_usd": float(oracle.sum()),
        "candidate_local_net_value_capture": (
            0.0 if denominator == 0 else float(realized.sum() / denominator)),
        "candidate_local_positive_value_capture": (
            0.0 if denominator == 0 else
            float(np.maximum(0.0, realized).sum() / denominator)),
        "candidate_local_regret_median_usd": float(np.median(regret)),
        "candidate_local_regret_p90_usd": float(np.quantile(regret, .9)),
        "candidate_local_missed_positive_rate": float(np.mean(
            (realized <= 0.0) & (oracle > 0.0))),
        "start_value_rmse_usd": float(np.sqrt(np.mean(
            (prediction - realized) ** 2))),
        "start_value_correlation": _weighted_correlation(
            prediction, realized, np.ones(len(starts), np.float64)),
        "entered_realized_mean_usd": (
            None if not len(entered) else float(np.mean(entered))),
        "entered_realized_median_usd": (
            None if not len(entered) else float(np.median(entered))),
        "entered_positive_rate": (
            None if not len(entered) else float(np.mean(entered > 0.0))),
        "entered_goal_rate": (
            None if not len(entered) else float(np.mean(entered >= 600.0))),
        "entered_wall_rate": (
            None if not len(entered) else float(np.mean(entered <= -900.0))),
        "row_action_confusion": confusion,
        "economics_executed": False,
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


def _shuffle_by_context(
    dataset: ConfirmationDataset, target: np.ndarray, *, seed: int,
) -> np.ndarray:
    """Destroy feature association while preserving day/asset/path position."""

    value = np.asarray(target, np.float64)
    if value.shape != (len(dataset.features),):
        raise ConfirmationRefusal("shuffle-control target differs")
    position = np.empty(len(value), np.int16)
    order, boundaries = _series_groups(dataset)
    for left, right in zip(boundaries[:-1], boundaries[1:]):
        indices = order[left:right]
        position[indices] = np.arange(len(indices), dtype=np.int16)
    rng = np.random.default_rng(seed)
    shuffled = value.copy()
    asset = np.asarray(dataset.asset, str)
    day = np.asarray(dataset.day, np.int64)
    context = np.asarray([
        f"{asset[index]}:{int(day[index])}:{int(position[index])}"
        for index in range(len(value))], str)
    for name in np.unique(context):
        indices = np.flatnonzero(context == name)
        shuffled[indices] = value[indices][rng.permutation(len(indices))]
    return shuffled


def run_snell_probe(
    datasets: Mapping[str, ConfirmationDataset],
    ledgers: Mapping[str, OracleActionLedger], *,
    config: SnellProbeConfig = SnellProbeConfig(),
    progress: Callable[[Mapping[str, object]], None] | None = None,
) -> Mapping[str, object]:
    """Fit expected immediate value and self-consistent continuation value."""

    roles = ("FIT", "PLATT", "THRESHOLD")
    if set(datasets) != set(roles) or set(ledgers) != set(roles):
        raise ConfirmationRefusal("Snell probe role roster is incomplete")
    for role in roles:
        datasets[role].validate(); ledgers[role].validate()
        if (ledgers[role].source_representation_sha256
                != datasets[role].representation_sha256
                or not np.array_equal(
                    datasets[role].opportunity_id, ledgers[role].opportunity_id)):
            raise ConfirmationRefusal("Snell probe role identity differs")
    fit = datasets["FIT"]; platt = datasets["PLATT"]
    if (fit.feature_names != platt.feature_names
            or fit.feature_names != datasets["THRESHOLD"].feature_names
            or int(np.max(fit.day)) >= int(np.min(platt.day))
            or int(np.max(platt.day)) >= int(np.min(datasets["THRESHOLD"].day))):
        raise ConfirmationRefusal("Snell probe schemas/chronology differ")
    masks = registered_feature_sets(fit.feature_names)
    if config.feature_set not in masks:
        raise ConfirmationRefusal("Snell probe feature set is not registered")
    columns = np.flatnonzero(masks[config.feature_set])
    features = {role: np.asarray(
        datasets[role].features[:, columns], np.float32) for role in roles}
    immediate, immediate_meta = _fit_immediate_estimators(
        datasets, ledgers, features, config, progress)
    immediate_diagnostics = {
        estimator: {role: immediate_value_diagnostic(
            datasets[role], ledgers[role], scores[role]) for role in roles}
        for estimator, scores in immediate.items()
    }
    # This is the only model-family selection.  It is frozen to the proper
    # expected-dollar score on PLATT; THRESHOLD never participates.
    selected_estimator = min(ESTIMATORS, key=lambda name:
        float(immediate_diagnostics[name]["PLATT"]["series_balanced_rmse_usd"]))
    selected_immediate = immediate[selected_estimator]
    if progress is not None:
        progress({"selected_immediate_estimator": selected_estimator})

    continuation_target = {
        role: np.asarray(ledgers[role].q_wait_usd, np.float64).copy()
        for role in roles}
    policy_iterations = []
    common = dict(_common_parameters(config))
    fit_weight = _series_weights(fit)
    platt_weight = _series_weights(platt)
    continuation_tree_counts = []
    for iteration in range(config.continuation_iterations):
        model = CatBoostRegressor(
            loss_function="RMSE", eval_metric="RMSE",
            **{**common, "random_seed": config.random_seed + 100 + iteration})
        model.fit(
            features["FIT"], continuation_target["FIT"],
            sample_weight=fit_weight,
            eval_set=(features["PLATT"], continuation_target["PLATT"]),
            use_best_model=True, verbose=False)
        raw = {role: np.asarray(model.predict(features[role]), np.float64)
               for role in roles}
        calibration = _fit_affine_calibration(
            raw["PLATT"], continuation_target["PLATT"], platt_weight)
        continuation = {role: _apply_affine(raw[role], calibration)
                        for role in roles}
        recursion = {role: fitted_policy_recursion(
            datasets[role], ledgers[role],
            immediate_score=selected_immediate[role],
            continuation_score=continuation[role]) for role in roles}
        diagnostics = {role: fitted_policy_diagnostic(
            datasets[role], ledgers[role], recursion[role],
            iteration=iteration) for role in roles}
        iteration_core = {
            "iteration": iteration,
            "training_target": (
                "ORACLE_Q_WAIT_WARM_START" if iteration == 0
                else "PRIOR_POLICY_REALIZED_DOWNSTREAM_CASHFLOW"),
            "tree_count": int(model.tree_count_),
            "affine_calibration": calibration,
            "diagnostics": diagnostics,
        }
        policy_iterations.append({
            **iteration_core,
            "receipt_sha256": C.object_sha256(iteration_core),
        })
        continuation_tree_counts.append(int(model.tree_count_))
        continuation_target = {role: np.asarray(
            recursion[role]["continuation_target"], np.float64).copy()
            for role in roles}
        if progress is not None:
            progress({
                "fit": "CONTINUATION", "iteration": iteration,
                "trees": int(model.tree_count_),
                "platt_candidate_local_net_mean_usd": diagnostics["PLATT"]
                    ["candidate_local_net_mean_usd"],
            })

    # A context-preserving target shuffle is a negative control for the
    # immediate-value head.  It is not fed into the policy or model selection.
    shuffled_target = _shuffle_by_context(
        fit, ledgers["FIT"].q_enter_usd, seed=config.random_seed + 10_000)
    control = CatBoostRegressor(
        loss_function="RMSE", eval_metric="RMSE",
        iterations=config.iterations, depth=config.depth,
        learning_rate=config.learning_rate, l2_leaf_reg=config.l2_leaf_reg,
        random_seed=config.random_seed + 10_000,
        thread_count=config.thread_count, allow_writing_files=False,
        verbose=False)
    control.fit(features["FIT"], shuffled_target,
                sample_weight=fit_weight, verbose=False)
    control_score = np.asarray(
        control.predict(features["THRESHOLD"]), np.float64)
    control_diagnostic = immediate_value_diagnostic(
        datasets["THRESHOLD"], ledgers["THRESHOLD"], control_score)
    if progress is not None:
        progress({"fit": "CONTEXT_TARGET_SHUFFLE", "trees": int(control.tree_count_)})

    core = {
        "schema": SCHEMA,
        "config": asdict(config),
        "config_sha256": config.receipt_sha256,
        "catboost_version": catboost.__version__,
        "feature_set": config.feature_set,
        "feature_count": len(columns),
        "factorization_diagnostics": {
            role: factorization_diagnostic(datasets[role], ledgers[role])
            for role in roles
        },
        "immediate_estimators": immediate_meta,
        "immediate_diagnostics": immediate_diagnostics,
        "selected_immediate_estimator": selected_estimator,
        "selection_role": "PLATT",
        "selection_metric": "series_balanced_rmse_usd",
        "continuation_tree_counts": tuple(continuation_tree_counts),
        "policy_iterations": tuple(policy_iterations),
        "negative_control": {
            "name": "FIT_Q_ENTER_SHUFFLED_WITHIN_DAY_ASSET_PATH_POSITION",
            "seed": config.random_seed + 10_000,
            "tree_count": int(control.tree_count_),
            "threshold_diagnostic": control_diagnostic,
        },
        "economics_executed": False,
        "forward_open_count": 0,
        "h2_open_count": 0,
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


__all__ = [
    "ESTIMATORS", "SCHEMA", "SnellProbeConfig", "entry_price_offset_usd",
    "factorization_diagnostic", "factorized_entry_target",
    "fitted_policy_diagnostic", "fitted_policy_recursion",
    "immediate_value_diagnostic", "run_snell_probe",
]
