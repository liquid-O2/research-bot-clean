"""Cheap chronological CatBoost probes for oracle-derived stopping labels.

These probes test whether a representation can express and generalize a label.
They do not select a deployable threshold and do not publish economics.  A
positive result merely authorizes the next, canonical stopping-policy test.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from pathlib import Path
from typing import Mapping, Sequence

from catboost import CatBoostClassifier, Pool
import catboost
import numpy as np
from sklearn.metrics import roc_auc_score

from . import common as C
from .confirmation import ConfirmationDataset, ConfirmationRefusal
from .confirmation_diagnostics import (
    registered_feature_sets, shuffle_confirmation_targets,
)
from .confirmation_stopping import (
    OracleActionLedger, derive_oracle_action_ledger,
    registered_oracle_label_family,
)


SCHEMA = "QRE2CONFACTIONPROBE2"


@dataclass(frozen=True, slots=True)
class ActionProbeConfig:
    iterations: int = 80
    depth: int = 5
    learning_rate: float = 0.08
    l2_leaf_reg: float = 10.0
    random_seed: int = 20260819
    thread_count: int = 16
    early_stopping_rounds: int = 10

    def __post_init__(self) -> None:
        if (not 10 <= self.iterations <= 500 or not 3 <= self.depth <= 8
                or not 0 < self.learning_rate <= .3
                or not 0 < self.l2_leaf_reg <= 1_000
                or not 1 <= self.thread_count <= C.MAX_CPU_WORKERS
                or not 5 <= self.early_stopping_rounds < self.iterations):
            raise ConfirmationRefusal("action probe configuration is invalid")

    @property
    def receipt_sha256(self) -> str:
        return C.object_sha256({"schema": SCHEMA, **asdict(self)})


def _series_weights(dataset: ConfirmationDataset) -> np.ndarray:
    series = np.asarray(dataset.series_id, str)
    _, inverse, counts = np.unique(series, return_inverse=True, return_counts=True)
    weights = 1.0 / counts[inverse].astype(np.float64)
    return weights * (len(weights) / weights.sum())


def _balanced_binary_weights(
    dataset: ConfirmationDataset, target: np.ndarray,
) -> np.ndarray:
    """Give each series equal mass, then give both target classes equal mass."""

    y = np.asarray(target, np.int8)
    if y.shape != (len(dataset.features),) or set(np.unique(y)) != {0, 1}:
        raise ConfirmationRefusal("action probe target is not two-class")
    base = _series_weights(dataset)
    negative = float(base[y == 0].sum())
    positive = float(base[y == 1].sum())
    if negative <= 0.0 or positive <= 0.0:
        raise ConfirmationRefusal("action probe target has zero weighted support")
    weights = base * np.where(y == 1, .5 / positive, .5 / negative)
    return np.asarray(weights * (len(weights) / weights.sum()), np.float64)


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
    left: np.ndarray, right: np.ndarray, weights: np.ndarray,
) -> float:
    x = np.asarray(left, np.float64); y = np.asarray(right, np.float64)
    w = np.asarray(weights, np.float64); w = w / w.sum()
    dx = x - np.sum(w * x); dy = y - np.sum(w * y)
    denominator = math.sqrt(float(np.sum(w * dx * dx) * np.sum(w * dy * dy)))
    return 0.0 if denominator == 0 else float(np.sum(w * dx * dy) / denominator)


def action_probe_diagnostic(
    dataset: ConfirmationDataset, ledger: OracleActionLedger,
    target: np.ndarray, score: np.ndarray,
) -> Mapping[str, object]:
    dataset.validate(); ledger.validate()
    y = np.asarray(target, np.int8); prediction = np.asarray(score, np.float64)
    if (y.shape != (len(dataset.features),) or prediction.shape != y.shape
            or len(np.unique(y)) != 2 or not np.all(np.isfinite(prediction))
            or not np.array_equal(dataset.opportunity_id, ledger.opportunity_id)):
        raise ConfirmationRefusal("action probe diagnostic inputs differ")
    weights = _series_weights(dataset)
    series = np.asarray(dataset.series_id, str)
    within_auc = []
    chosen: list[int] = []
    best_enter: list[int] = []
    best_wait: list[int] = []
    timestamps = np.asarray(dataset.snapshot_ts_ns, np.int64)
    group_order, boundaries = _series_groups(dataset)
    for left, right in zip(boundaries[:-1], boundaries[1:]):
        indices = group_order[left:right]
        if len(np.unique(y[indices])) == 2:
            within_auc.append(float(roc_auc_score(y[indices], prediction[indices])))
        ranked = indices[np.lexsort((timestamps[indices], -prediction[indices]))]
        chosen.append(int(ranked[0]))
        best_enter.append(int(indices[np.argmax(ledger.q_enter_usd[indices])]))
        best_wait.append(int(indices[np.argmax(ledger.q_wait_usd[indices])]))
    chosen_array = np.asarray(chosen, np.int64)
    best_enter_array = np.asarray(best_enter, np.int64)
    best_wait_array = np.asarray(best_wait, np.int64)
    chosen_enter = np.maximum(0.0, ledger.q_enter_usd[chosen_array])
    oracle_enter = np.maximum(0.0, ledger.q_enter_usd[best_enter_array])
    chosen_wait = np.maximum(0.0, ledger.q_wait_usd[chosen_array])
    oracle_wait = np.maximum(0.0, ledger.q_wait_usd[best_wait_array])
    # This diagnostic evaluates a hindsight argmax over the *entire* series.
    # Its regret must therefore use the entire-series best entry, not the
    # ledger's causal best-remaining value at the chosen timestamp.  The
    # latter would forgive a score that selected only after missing the best.
    hindsight_enter_regret = (
        np.asarray(ledger.q_enter_usd, np.float64)[best_enter_array]
        - np.asarray(ledger.q_enter_usd, np.float64)[chosen_array])
    core = {
        "rows": len(y), "series": len(chosen_array),
        "series_balanced_base_rate": float(np.average(y, weights=weights)),
        "global_series_balanced_auc": float(roc_auc_score(
            y, prediction, sample_weight=weights)),
        "within_series_auc_mean": (
            None if not within_auc else float(np.mean(within_auc))),
        "within_series_auc_groups": len(within_auc),
        "score_enter_advantage_correlation": _weighted_correlation(
            prediction, ledger.enter_advantage_usd, weights),
        "hindsight_argmax_q_enter_capture": (
            0.0 if oracle_enter.sum() == 0 else
            float(chosen_enter.sum() / oracle_enter.sum())),
        "hindsight_argmax_q_wait_capture": (
            0.0 if oracle_wait.sum() == 0 else
            float(chosen_wait.sum() / oracle_wait.sum())),
        "hindsight_argmax_nearopt_50_rate": float(np.mean(
            hindsight_enter_regret <= 50.0)),
        "hindsight_argmax_nearopt_100_rate": float(np.mean(
            hindsight_enter_regret <= 100.0)),
        "hindsight_argmax_goal_rate": float(np.mean(
            ledger.q_enter_usd[chosen_array] >= 600.0)),
        "hindsight_argmax_median_enter_regret_usd": float(np.median(
            hindsight_enter_regret)),
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


def run_action_probe_matrix(
    datasets: Mapping[str, ConfirmationDataset],
    ledgers: Mapping[str, OracleActionLedger],
    *, feature_sets: Sequence[str] = (
        "FORMATION_ONLY", "PLUS_RECLAIM", "MAX_W300"),
    labels: Sequence[str] = (
        "EXACT_ENTER", "ENTER_POSITIVE_R50", "ENTER_P600_R100", "WAIT_P600"),
    config: ActionProbeConfig = ActionProbeConfig(),
    shuffled_control_label: str = "ENTER_P600_R100",
) -> Mapping[str, object]:
    """Fit on FIT, early-stop on PLATT, and read untouched THRESHOLD metrics."""

    if set(datasets) != {"FIT", "PLATT", "THRESHOLD"} or set(ledgers) != set(datasets):
        raise ConfirmationRefusal("action probe role roster is incomplete")
    for role in datasets:
        datasets[role].validate(); ledgers[role].validate()
        if (ledgers[role].source_representation_sha256
                != datasets[role].representation_sha256):
            raise ConfirmationRefusal("action probe role ledger differs")
    fit = datasets["FIT"]; platt = datasets["PLATT"]
    if (fit.feature_names != platt.feature_names
            or fit.feature_names != datasets["THRESHOLD"].feature_names
            or int(np.max(fit.day)) >= int(np.min(platt.day))
            or int(np.max(platt.day)) >= int(np.min(datasets["THRESHOLD"].day))):
        raise ConfirmationRefusal("action probe schemas/chronology differ")
    label_values = {
        role: registered_oracle_label_family(ledgers[role]) for role in datasets}
    unknown = set(labels) - set(label_values["FIT"])
    if unknown or shuffled_control_label not in label_values["FIT"]:
        raise ConfirmationRefusal("action probe requested an unknown label")
    masks = registered_feature_sets(fit.feature_names)
    unknown_features = set(feature_sets) - set(masks)
    if unknown_features:
        raise ConfirmationRefusal("action probe requested an unknown feature set")

    rows = []
    shuffle_seed = config.random_seed + 1009
    shuffled_fit = shuffle_confirmation_targets(fit, shuffle_seed)
    shuffled_ledger = derive_oracle_action_ledger(shuffled_fit)
    shuffled_ledger_sha256 = shuffled_ledger.representation_sha256
    shuffled_target = registered_oracle_label_family(
        shuffled_ledger)[shuffled_control_label]
    input_bindings = {
        role: {
            "dataset_sha256": datasets[role].representation_sha256,
            "ledger_sha256": ledgers[role].representation_sha256,
        }
        for role in sorted(datasets)
    }
    directory = Path(__file__).resolve().parent
    implementation_bindings = {
        "action_probe": C.file_sha256(Path(__file__)),
        "diagnostics": C.file_sha256(
            directory / "confirmation_diagnostics.py"),
        "stopping": C.file_sha256(
            directory / "confirmation_stopping.py"),
    }
    for feature_set in feature_sets:
        mask = masks[feature_set]
        columns = np.flatnonzero(mask)
        x = {role: np.asarray(datasets[role].features[:, columns], np.float32)
             for role in datasets}
        for label_name in labels:
            y_fit = label_values["FIT"][label_name]
            y_platt = label_values["PLATT"][label_name]
            fit_weights = _balanced_binary_weights(fit, y_fit)
            platt_weights = _balanced_binary_weights(platt, y_platt)
            model = CatBoostClassifier(
                loss_function="Logloss", eval_metric="AUC",
                iterations=config.iterations, depth=config.depth,
                learning_rate=config.learning_rate,
                l2_leaf_reg=config.l2_leaf_reg,
                random_seed=config.random_seed,
                thread_count=config.thread_count,
                allow_writing_files=False, verbose=False,
                od_type="Iter", od_wait=config.early_stopping_rounds,
            )
            model.fit(
                x["FIT"], y_fit, sample_weight=fit_weights,
                eval_set=Pool(x["PLATT"], y_platt, weight=platt_weights),
                use_best_model=True,
                verbose=False)
            diagnostics = {}
            for role in ("FIT", "PLATT", "THRESHOLD"):
                score = np.asarray(model.predict_proba(x[role])[:, 1], np.float64)
                diagnostics[role] = action_probe_diagnostic(
                    datasets[role], ledgers[role],
                    label_values[role][label_name], score)
            core = {
                "feature_set": feature_set, "feature_count": len(columns),
                "label": label_name, "best_iteration": int(model.get_best_iteration()),
                "tree_count": int(model.tree_count_), "diagnostics": diagnostics,
            }
            rows.append({**core, "receipt_sha256": C.object_sha256(core)})

        # One recipient-fixed, whole-series outcome shuffle validates the
        # instrument without manufacturing an impossible row-wise label path.
        shuffled_weights = _balanced_binary_weights(
            shuffled_fit, shuffled_target)
        control = CatBoostClassifier(
            loss_function="Logloss", eval_metric="AUC",
            iterations=config.iterations, depth=config.depth,
            learning_rate=config.learning_rate, l2_leaf_reg=config.l2_leaf_reg,
            random_seed=config.random_seed + 1,
            thread_count=config.thread_count, allow_writing_files=False,
            verbose=False)
        control.fit(
            x["FIT"], shuffled_target,
            sample_weight=shuffled_weights, verbose=False)
        threshold_score = np.asarray(
            control.predict_proba(x["THRESHOLD"])[:, 1], np.float64)
        diagnostic = action_probe_diagnostic(
            datasets["THRESHOLD"], ledgers["THRESHOLD"],
            label_values["THRESHOLD"][shuffled_control_label], threshold_score)
        control_core = {
            "control": "FIT_RECIPIENT_FIXED_SERIES_TARGET_SHUFFLE",
            "feature_set": feature_set, "feature_count": len(columns),
            "label": shuffled_control_label, "shuffle_seed": shuffle_seed,
            "shuffle_schema": "QRE2CONFSHUF1",
            "shuffled_dataset_sha256": shuffled_fit.representation_sha256,
            "shuffled_ledger_sha256": shuffled_ledger_sha256,
            "diagnostic": diagnostic,
        }
        rows.append({**control_core,
                     "receipt_sha256": C.object_sha256(control_core)})
        del x
    core = {
        "schema": SCHEMA, "config": asdict(config),
        "config_sha256": config.receipt_sha256,
        "catboost_version": catboost.__version__,
        "weighting": "SERIES_BALANCED_THEN_CLASS_BALANCED",
        "inputs": input_bindings,
        "implementation_sha256": implementation_bindings,
        "feature_sets": tuple(feature_sets), "labels": tuple(labels),
        "results": tuple(rows),
        "economics_executed": False, "forward_open_count": 0,
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


__all__ = [
    "ActionProbeConfig", "SCHEMA", "action_probe_diagnostic",
    "run_action_probe_matrix",
]
