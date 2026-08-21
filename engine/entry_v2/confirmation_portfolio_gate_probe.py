"""Portfolio-aware Oracle distillation for the 30-second watch gate.

This probe asks whether CatBoost can learn which candidates contribute to the
joint sparse-grid day schedule after asset occupancy and the twelve-entry cap.
It is candidate-gate diagnosis, not learned trading economics: all reported
dollars are hindsight schedule ceilings on a selected roster.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final, Mapping, Sequence

import catboost
from catboost import CatBoostClassifier
import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

from . import common as C
from .confirmation import ConfirmationDataset, ConfirmationRefusal
from .confirmation_dynamic_hurdle_policy import _sparse_schedule_ceiling
from .confirmation_factorized_policy import select_top_capacity_series
from .confirmation_policy import _nondominated_positive_indices, _solve_day
from .confirmation_stopping import OracleActionLedger
from .contracts import SessionRef


SCHEMA: Final = "QRE2CONFPORTGATE1"
ROLES: Final = ("FIT", "PLATT", "THRESHOLD")


@dataclass(frozen=True, slots=True)
class PortfolioGateConfig:
    watch_age_sec: int = 30
    capacity_per_asset_day: int = 12
    iterations: int = 40
    depth: int = 5
    learning_rate: float = .05
    l2_leaf_reg: float = 12.0
    seed: int = 202608204
    control_seed: int = 20270824
    thread_count: int = 16
    folds: tuple[tuple[int, int], ...] = ((12, 6), (18, 6), (24, 6))
    minimum_platt_capture_lift: float = .05
    minimum_control_gap: float = .10
    minimum_selected_ceiling_per_day: float = 3_000.0

    def __post_init__(self) -> None:
        if (not 0 <= self.watch_age_sec <= 300
                or not 1 <= self.capacity_per_asset_day <= 12
                or not 5 <= self.iterations <= 500
                or not 3 <= self.depth <= 8
                or not 0 < self.learning_rate <= .3
                or not 0 < self.l2_leaf_reg <= 1_000
                or not 1 <= self.thread_count <= C.MAX_CPU_WORKERS
                or not self.folds
                or any(train <= 0 or valid <= 0
                       for train, valid in self.folds)
                or tuple(train for train, _valid in self.folds)
                   != tuple(sorted(set(train for train, _valid in self.folds)))
                or not 0 <= self.minimum_platt_capture_lift <= 1
                or not 0 <= self.minimum_control_gap <= 1
                or self.minimum_selected_ceiling_per_day <= 0):
            raise ConfirmationRefusal(
                "portfolio-gate configuration is invalid")

    @property
    def receipt_sha256(self) -> str:
        return C.object_sha256({"schema": SCHEMA, **asdict(self)})


@dataclass(frozen=True, slots=True)
class PortfolioGateModels:
    real: CatBoostClassifier
    control: CatBoostClassifier
    feature_names: tuple[str, ...]
    real_model_sha256: str
    control_model_sha256: str


def _validate_roles(
    paths: Mapping[str, ConfirmationDataset],
    fixed: Mapping[str, ConfirmationDataset],
    expected_sessions: Mapping[str, Sequence[SessionRef]],
) -> None:
    if (set(paths) != set(ROLES) or set(fixed) != set(ROLES)
            or set(expected_sessions) != set(ROLES)):
        raise ConfirmationRefusal("portfolio-gate role roster differs")
    for role in ROLES:
        paths[role].validate(); fixed[role].validate()
        path_series = set(np.asarray(paths[role].series_id, str).tolist())
        fixed_series = np.asarray(fixed[role].series_id, str)
        if (paths[role].snapshot_mode != "TRAINING"
                or paths[role].max_delay_sec != 300
                or len(fixed_series) != len(set(fixed_series.tolist()))
                or path_series != set(fixed_series.tolist())):
            raise ConfirmationRefusal(
                "portfolio-gate requires every watchable candidate path")
        watch = {str(series): int(timestamp) for series, timestamp in zip(
            fixed_series, fixed[role].snapshot_ts_ns)}
        series = np.asarray(paths[role].series_id, str)
        timestamp = np.asarray(paths[role].snapshot_ts_ns, np.int64)
        for candidate in path_series:
            local = np.flatnonzero(series == candidate)
            if int(np.min(timestamp[local])) != watch[candidate]:
                raise ConfirmationRefusal(
                    "portfolio-gate path does not start at exact watch row")
        sessions = tuple(expected_sessions[role])
        if not sessions or len(sessions) != len(set(sessions)):
            raise ConfirmationRefusal(
                "portfolio-gate session denominator is malformed")
    if (paths["FIT"].feature_names != paths["PLATT"].feature_names
            or paths["FIT"].feature_names != paths["THRESHOLD"].feature_names
            or fixed["FIT"].feature_names != fixed["PLATT"].feature_names
            or fixed["FIT"].feature_names != fixed["THRESHOLD"].feature_names
            or int(np.max(paths["FIT"].day))
               >= int(np.min(paths["PLATT"].day))
            or int(np.max(paths["PLATT"].day))
               >= int(np.min(paths["THRESHOLD"].day))):
        raise ConfirmationRefusal(
            "portfolio-gate schemas/chronology differ")


def portfolio_schedule_target(
    paths: ConfirmationDataset, fixed: ConfirmationDataset,
) -> tuple[np.ndarray, Mapping[str, object]]:
    """Mark the candidate series used by the joint sparse day optimizer."""

    paths.validate(); fixed.validate()
    path_series = set(np.asarray(paths.series_id, str).tolist())
    fixed_series = np.asarray(fixed.series_id, str)
    if path_series != set(fixed_series.tolist()):
        raise ConfirmationRefusal(
            "portfolio target needs the complete fixed/path roster")
    retained = _nondominated_positive_indices(paths)
    days = np.asarray(paths.day, np.int64)
    selected_indices: list[int] = []; objective_cents = 0
    for day in sorted(set(days[retained].tolist())):
        chosen, cents = _solve_day(paths, retained[days[retained] == day])
        selected_indices.extend(chosen.tolist()); objective_cents += cents
    selected_series = tuple(sorted(set(np.asarray(
        paths.series_id, str)[selected_indices].tolist())))
    if len(selected_series) != len(selected_indices):
        raise ConfirmationRefusal(
            "portfolio target selected one candidate more than once")
    target = np.isin(fixed_series, selected_series).astype(np.int8)
    if len(np.unique(target)) != 2:
        raise ConfirmationRefusal("portfolio target is one-class")
    selected_day = np.asarray(fixed.day, np.int64)[target == 1]
    core = {
        "scope": "SPARSE_TRAINING_GRID_PORTFOLIO_MEMBERSHIP_NOT_EXACT",
        "path_dataset_sha256": paths.representation_sha256,
        "fixed_dataset_sha256": fixed.representation_sha256,
        "rows": len(target),
        "positive": int(np.sum(target == 1)),
        "negative": int(np.sum(target == 0)),
        "positive_days": len(set(selected_day.tolist())),
        "selected_series_sha256": C.object_sha256(selected_series),
        "objective_cents": objective_cents,
        "exact_replay_ceiling": False,
    }
    return target, {**core, "receipt_sha256": C.object_sha256(core)}


def _weights(dataset: ConfirmationDataset, target: np.ndarray) -> np.ndarray:
    y = np.asarray(target, np.int8)
    if y.shape != (len(dataset.features),) or len(np.unique(y)) != 2:
        raise ConfirmationRefusal("portfolio-gate weights are malformed")
    days = np.asarray(dataset.day, np.int64)
    weight = np.zeros(len(y), np.float64)
    for day in np.unique(days):
        local = days == day
        weight[local] = 1.0 / int(np.sum(local))
    for label in (0, 1):
        total = float(np.sum(weight[y == label]))
        if total <= 0:
            raise ConfirmationRefusal(
                "portfolio-gate class weight is empty")
        weight[y == label] *= .5 / total
    weight *= len(weight) / weight.sum()
    return weight


def _shuffle_within_day(
    dataset: ConfirmationDataset, target: np.ndarray, *, seed: int,
) -> np.ndarray:
    y = np.asarray(target, np.int8)
    days = np.asarray(dataset.day, np.int64)
    rng = np.random.default_rng(seed); result = y.copy()
    for day in np.unique(days):
        local = np.flatnonzero(days == day)
        result[local] = y[rng.permutation(local)]
    if (np.array_equal(result, y) or int(result.sum()) != int(y.sum())):
        raise ConfirmationRefusal(
            "portfolio-gate control shuffle was ineffective")
    return result


def _fit(
    dataset: ConfirmationDataset, target: np.ndarray, *, seed: int,
    config: PortfolioGateConfig,
) -> CatBoostClassifier:
    model = CatBoostClassifier(
        loss_function="Logloss", eval_metric="PRAUC:type=Classic",
        iterations=config.iterations, depth=config.depth,
        learning_rate=config.learning_rate, l2_leaf_reg=config.l2_leaf_reg,
        random_seed=seed, thread_count=config.thread_count,
        allow_writing_files=False, verbose=False)
    model.fit(dataset.features, target,
              sample_weight=_weights(dataset, target), verbose=False)
    return model


def _identity(
    name: str, model: CatBoostClassifier, feature_names: Sequence[str],
    config_sha256: str,
) -> str:
    return C.object_sha256({
        "schema": "QRE2CONFPORTGATEMODEL1", "name": name,
        "config_sha256": config_sha256,
        "tree_count": int(model.tree_count_),
        "feature_names": tuple(feature_names),
        "parameters": model.get_all_params(),
    })


def fit_portfolio_gate_models(
    fit: ConfirmationDataset, target: np.ndarray, *,
    config: PortfolioGateConfig = PortfolioGateConfig(),
) -> PortfolioGateModels:
    control_target = _shuffle_within_day(
        fit, target, seed=config.control_seed)
    real = _fit(fit, target, seed=config.seed, config=config)
    control = _fit(
        fit, control_target, seed=config.seed + 10_000, config=config)
    return PortfolioGateModels(
        real, control, fit.feature_names,
        _identity("PORTFOLIO", real, fit.feature_names,
                  config.receipt_sha256),
        _identity("PORTFOLIO_CONTROL", control, fit.feature_names,
                  config.receipt_sha256))


def _sessions_for_days(
    sessions: Sequence[SessionRef], days: set[int],
) -> tuple[SessionRef, ...]:
    result = tuple(row for row in sessions if int(row.trading_day) in days)
    if not result:
        raise ConfirmationRefusal("portfolio-gate fold session roster is empty")
    return result


def _gate_ceiling(
    paths: ConfirmationDataset, fixed: ConfirmationDataset,
    score: np.ndarray, sessions: Sequence[SessionRef], *, capacity: int,
) -> Mapping[str, object]:
    selected = select_top_capacity_series(fixed, score, capacity=capacity)
    subset = paths.subset(np.isin(paths.series_id, selected))
    ceiling = _sparse_schedule_ceiling(subset, sessions)
    core = {
        "selected_series": len(selected),
        "selected_series_sha256": C.object_sha256(selected),
        "ceiling": ceiling,
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


def _metric(
    dataset: ConfirmationDataset, target: np.ndarray, score: np.ndarray,
) -> Mapping[str, object]:
    y = np.asarray(target, np.int8); p = np.asarray(score, np.float64)
    weight = _weights(dataset, y)
    core = {
        "roc_auc_day_class_balanced": float(
            roc_auc_score(y, p, sample_weight=weight)),
        "average_precision_day_class_balanced": float(
            average_precision_score(y, p, sample_weight=weight)),
        "selection_metric": False,
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


def portfolio_gate_preflight(
    paths: Mapping[str, ConfirmationDataset],
    fixed: Mapping[str, ConfirmationDataset],
    expected_sessions: Mapping[str, Sequence[SessionRef]], *,
    rank_model: CatBoostClassifier, rank_control_model: CatBoostClassifier,
    config: PortfolioGateConfig = PortfolioGateConfig(),
) -> Mapping[str, object]:
    _validate_roles(paths, fixed, expected_sessions)
    if (len(rank_model.feature_names_) != len(fixed["FIT"].feature_names)
            or len(rank_control_model.feature_names_)
               != len(fixed["FIT"].feature_names)):
        raise ConfirmationRefusal("portfolio-gate rank model width differs")
    support = {}; targets = {}
    for role in ROLES:
        target, report = portfolio_schedule_target(paths[role], fixed[role])
        _weights(fixed[role], target)
        targets[role] = target; support[role] = report
    fit_control = _shuffle_within_day(
        fixed["FIT"], targets["FIT"], seed=config.control_seed)
    days = sorted(set(np.asarray(fixed["FIT"].day, np.int64).tolist()))
    fold_report = []
    for train_count, valid_count in config.folds:
        if train_count + valid_count > len(days):
            raise ConfirmationRefusal("portfolio-gate fold exceeds FIT days")
        train_days = set(days[:train_count]); valid_days = set(
            days[train_count:train_count + valid_count])
        train_mask = np.isin(fixed["FIT"].day, tuple(train_days))
        valid_mask = np.isin(fixed["FIT"].day, tuple(valid_days))
        _weights(fixed["FIT"].subset(train_mask), targets["FIT"][train_mask])
        if not np.any(valid_mask):
            raise ConfirmationRefusal("portfolio-gate validation fold is empty")
        fold_report.append({
            "train_days": train_count, "valid_days": valid_count,
            "train_rows": int(np.sum(train_mask)),
            "valid_rows": int(np.sum(valid_mask)),
            "train_positive": int(np.sum(targets["FIT"][train_mask])),
            "valid_positive": int(np.sum(targets["FIT"][valid_mask])),
        })
    core = {
        "schema": "QRE2CONFPORTGATEPREFLIGHT1",
        "config_sha256": config.receipt_sha256,
        "support": support,
        "folds": tuple(fold_report),
        "fit_control_changed": int(np.sum(fit_control != targets["FIT"])),
        "all_watchable_series_present": True,
        "models_executed": False,
        "economics_executed": False,
        "candidate_gate_ceiling_only": True,
        "exact_replay_ceiling_executed": False,
        "implementation_sha256": C.file_sha256(Path(__file__)),
        "forward_open_count": 0,
        "h2_open_count": 0,
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


def run_portfolio_gate_probe(
    paths: Mapping[str, ConfirmationDataset],
    fixed: Mapping[str, ConfirmationDataset],
    expected_sessions: Mapping[str, Sequence[SessionRef]], *,
    rank_model: CatBoostClassifier, rank_control_model: CatBoostClassifier,
    models: PortfolioGateModels,
    config: PortfolioGateConfig = PortfolioGateConfig(),
) -> Mapping[str, object]:
    """Measure FIT-forward and PLATT schedule-ceiling recovery."""

    preflight = portfolio_gate_preflight(
        paths, fixed, expected_sessions, rank_model=rank_model,
        rank_control_model=rank_control_model, config=config)
    if (models.feature_names != fixed["FIT"].feature_names
            or len(models.real.feature_names_) != len(models.feature_names)
            or len(models.control.feature_names_) != len(models.feature_names)):
        raise ConfirmationRefusal("portfolio-gate model schema differs")
    targets = {role: portfolio_schedule_target(
        paths[role], fixed[role])[0] for role in ROLES}
    days = sorted(set(np.asarray(fixed["FIT"].day, np.int64).tolist()))
    fold_rows = []; totals = {name: 0.0 for name in (
        "REAL", "CONTROL", "OLD_RANK", "OLD_RANK_CONTROL", "UNION")}
    for fold, (train_count, valid_count) in enumerate(config.folds, start=1):
        train_days = set(days[:train_count]); valid_days = set(
            days[train_count:train_count + valid_count])
        train_mask = np.isin(fixed["FIT"].day, tuple(train_days))
        valid_mask = np.isin(fixed["FIT"].day, tuple(valid_days))
        train = fixed["FIT"].subset(train_mask)
        valid = fixed["FIT"].subset(valid_mask)
        valid_paths = paths["FIT"].subset(np.isin(
            paths["FIT"].day, tuple(valid_days)))
        sessions = _sessions_for_days(expected_sessions["FIT"], valid_days)
        y_train = targets["FIT"][train_mask]
        real = _fit(train, y_train, seed=config.seed + fold, config=config)
        shuffled = _shuffle_within_day(
            train, y_train, seed=config.control_seed + fold)
        control = _fit(
            train, shuffled, seed=config.seed + 10_000 + fold,
            config=config)
        scores = {
            "REAL": np.asarray(real.predict_proba(valid.features)[:, 1]),
            "CONTROL": np.asarray(control.predict_proba(valid.features)[:, 1]),
            "OLD_RANK": np.asarray(
                rank_model.predict_proba(valid.features)[:, 1]),
            "OLD_RANK_CONTROL": np.asarray(
                rank_control_model.predict_proba(valid.features)[:, 1]),
        }
        union = _sparse_schedule_ceiling(valid_paths, sessions)
        union_total = float(union["evaluation"]["total_pnl_usd"])
        totals["UNION"] += union_total
        gates = {}
        for name, score in scores.items():
            gate = _gate_ceiling(
                valid_paths, valid, score, sessions,
                capacity=config.capacity_per_asset_day)
            gate_total = float(gate["ceiling"]["evaluation"]["total_pnl_usd"])
            totals[name] += gate_total
            gates[name] = {
                **gate, "capture": gate_total / union_total,
            }
        fold_rows.append({
            "fold": fold, "train_days": train_count,
            "valid_days": valid_count, "union_ceiling": union,
            "gates": gates,
        })
    oof = {name: totals[name] / totals["UNION"] for name in (
        "REAL", "CONTROL", "OLD_RANK", "OLD_RANK_CONTROL")}

    role = "PLATT"; sessions = expected_sessions[role]
    target = targets[role]
    scores = {
        "REAL": np.asarray(models.real.predict_proba(
            fixed[role].features)[:, 1]),
        "CONTROL": np.asarray(models.control.predict_proba(
            fixed[role].features)[:, 1]),
        "OLD_RANK": np.asarray(rank_model.predict_proba(
            fixed[role].features)[:, 1]),
        "OLD_RANK_CONTROL": np.asarray(rank_control_model.predict_proba(
            fixed[role].features)[:, 1]),
        "ORACLE_MEMBERSHIP": target.astype(np.float64),
    }
    union = _sparse_schedule_ceiling(paths[role], sessions)
    union_total = float(union["evaluation"]["total_pnl_usd"])
    platt_gates = {}
    for name, score in scores.items():
        gate = _gate_ceiling(
            paths[role], fixed[role], score, sessions,
            capacity=config.capacity_per_asset_day)
        total = float(gate["ceiling"]["evaluation"]["total_pnl_usd"])
        platt_gates[name] = {**gate, "capture": total / union_total}
    real_capture = float(platt_gates["REAL"]["capture"])
    control_capture = float(platt_gates["CONTROL"]["capture"])
    old_capture = float(platt_gates["OLD_RANK"]["capture"])
    real_per_day = float(platt_gates["REAL"]["ceiling"]
                         ["evaluation"]["usd_per_portfolio_day"])
    reasons = []
    if oof["REAL"] < oof["CONTROL"] + config.minimum_control_gap:
        reasons.append("FIT_OOF_CONTROL_GAP_BELOW_MINIMUM")
    if real_capture < old_capture + config.minimum_platt_capture_lift:
        reasons.append("PLATT_CAPTURE_LIFT_BELOW_MINIMUM")
    if real_capture < control_capture + config.minimum_control_gap:
        reasons.append("PLATT_CONTROL_GAP_BELOW_MINIMUM")
    if real_per_day < config.minimum_selected_ceiling_per_day:
        reasons.append("PLATT_SELECTED_CEILING_BELOW_MINIMUM")
    status = "PROMOTE_TO_ALL_PATH_ACTION_TEST" if not reasons else "NO_PROMOTION"

    threshold = None
    if not reasons:
        role = "THRESHOLD"; sessions = expected_sessions[role]
        union_t = _sparse_schedule_ceiling(paths[role], sessions)
        union_t_total = float(union_t["evaluation"]["total_pnl_usd"])
        threshold = {"union_ceiling": union_t, "gates": {}}
        for name, model in (("REAL", models.real),
                            ("CONTROL", models.control),
                            ("OLD_RANK", rank_model),
                            ("OLD_RANK_CONTROL", rank_control_model)):
            score = np.asarray(model.predict_proba(
                fixed[role].features)[:, 1])
            gate = _gate_ceiling(
                paths[role], fixed[role], score, sessions,
                capacity=config.capacity_per_asset_day)
            total = float(gate["ceiling"]["evaluation"]["total_pnl_usd"])
            threshold["gates"][name] = {
                **gate, "capture": total / union_t_total}

    metric_roles = (("FIT", "PLATT", "THRESHOLD")
                    if threshold is not None else ("FIT", "PLATT"))
    metrics = {
        role_name: {
            "REAL": _metric(
                fixed[role_name], targets[role_name],
                models.real.predict_proba(fixed[role_name].features)[:, 1]),
            "CONTROL": _metric(
                fixed[role_name], targets[role_name],
                models.control.predict_proba(fixed[role_name].features)[:, 1]),
        } for role_name in metric_roles
    }
    core = {
        "schema": SCHEMA,
        "config": asdict(config),
        "config_sha256": config.receipt_sha256,
        "preflight": preflight,
        "catboost_version": catboost.__version__,
        "model_identity": {
            "real": models.real_model_sha256,
            "control": models.control_model_sha256,
        },
        "fit_forward_folds": tuple(fold_rows),
        "fit_oof_capture": oof,
        "platt": {"union_ceiling": union, "gates": platt_gates},
        "progression_status": status,
        "progression_reasons": tuple(reasons),
        "threshold": threshold,
        "classification_metrics_not_selection": metrics,
        "roster_conditioned": False,
        "candidate_gate_ceiling_only": True,
        "learned_economics_executed": False,
        "exact_replay_ceiling_executed": False,
        "threshold_ceiling_executed": threshold is not None,
        "implementation_sha256": C.file_sha256(Path(__file__)),
        "forward_open_count": 0,
        "h2_open_count": 0,
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


__all__ = [
    "PortfolioGateConfig", "PortfolioGateModels", "fit_portfolio_gate_models",
    "portfolio_gate_preflight", "portfolio_schedule_target",
    "run_portfolio_gate_probe",
]
