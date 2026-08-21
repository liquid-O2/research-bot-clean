"""Direct continuous-utility CatBoost probe on a frozen candidate roster.

The earlier dynamic hurdle split one economic action into two binary events.
This probe instead learns the two dollar-valued quantities needed at every
causal snapshot:

* ``Q_enter`` -- certified dollars from entering now; and
* ``enter_advantage`` -- dollars gained by entering now instead of retaining
  the option to wait or pass.

Both outputs are fitted jointly with ``MultiRMSE`` after a fixed asinh dollar
transform.  A matched control transfers the complete two-output target path
between candidates in the same asset-day while leaving recipient features and
timestamps untouched.  PLATT economics are canonical replay economics.  The
model-score argmax schedules are explicitly non-deployable diagnostics used to
separate score ordering from causal threshold conversion.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final, Mapping, Sequence

import catboost
from catboost import CatBoostRegressor
import numpy as np
from scipy.stats import spearmanr

from . import common as C
from .capacity_contract import threshold_feasibility
from .confirmation import ConfirmationDataset, ConfirmationRefusal
from .confirmation_dynamic_hurdle_policy import (
    ROLES, _arrival, _evaluation_summary, _gated_role, _rank_rosters,
    _sparse_schedule_ceiling, _validate_roles,
)
from .confirmation_policy import confirmation_series_time_order
from .confirmation_stopping import OracleActionLedger
from .contracts import EntryEvaluation, SessionRef
from .replay import replay


SCHEMA: Final = "QRE2CONFDIRECTUTILITY1"
MODEL_SCHEMA: Final = "QRE2CONFDIRECTUTILITYMODEL1"
TARGET_NAMES: Final = ("Q_ENTER_USD", "ENTER_ADVANTAGE_USD")


@dataclass(frozen=True, slots=True)
class DirectUtilityConfig:
    watch_age_sec: int = 30
    capacity: int = 12
    iterations: int = 80
    depth: int = 6
    learning_rate: float = .05
    l2_leaf_reg: float = 12.0
    target_scale_usd: float = 600.0
    seed: int = 202608205
    control_seed: int = 20270825
    thread_count: int = 16
    minimum_roster_capture: float = .80
    minimum_control_gap: float = .10
    enter_thresholds_usd: tuple[float, ...] = (
        -900.0, -600.0, -300.0, -100.0, .01, 100.0, 300.0,
        600.0, 900.0, 1_200.0,
    )
    advantage_thresholds_usd: tuple[float, ...] = (
        -900.0, -600.0, -300.0, -150.0, -75.0, -25.0, .01,
        12.5, 25.0, 50.0, 100.0, 200.0, 400.0,
    )

    def __post_init__(self) -> None:
        enter = tuple(float(value) for value in self.enter_thresholds_usd)
        advantage = tuple(float(value)
                          for value in self.advantage_thresholds_usd)
        if (not 0 <= self.watch_age_sec <= 300
                or not 1 <= self.capacity <= 12
                or not 5 <= self.iterations <= 500
                or not 3 <= self.depth <= 8
                or not 0 < self.learning_rate <= .3
                or not 0 < self.l2_leaf_reg <= 1_000
                or not 0 < self.target_scale_usd <= 10_000
                or not 1 <= self.thread_count <= C.MAX_CPU_WORKERS
                or not 0 < self.minimum_roster_capture <= 1
                or not 0 <= self.minimum_control_gap <= 1
                or not enter or enter != tuple(sorted(set(enter)))
                or not advantage
                or advantage != tuple(sorted(set(advantage)))
                or any(not np.isfinite(value)
                       for value in enter + advantage)):
            raise ConfirmationRefusal(
                "direct-utility configuration is invalid")

    @property
    def receipt_sha256(self) -> str:
        return C.object_sha256({"schema": SCHEMA, **asdict(self)})


@dataclass(frozen=True, slots=True)
class DirectUtilityModels:
    real: CatBoostRegressor
    control: CatBoostRegressor
    feature_names: tuple[str, ...]
    real_model_sha256: str
    control_model_sha256: str


@dataclass(frozen=True, slots=True)
class DirectUtilityPolicy:
    min_q_enter_usd: float
    min_enter_advantage_usd: float

    def __post_init__(self) -> None:
        if not all(np.isfinite((self.min_q_enter_usd,
                                self.min_enter_advantage_usd))):
            raise ConfirmationRefusal("direct-utility policy is invalid")

    @property
    def receipt_sha256(self) -> str:
        return C.object_sha256({
            "schema": "QRE2CONFDIRECTUTILITYPOLICY1",
            **asdict(self),
        })


def _targets(ledger: OracleActionLedger) -> np.ndarray:
    ledger.validate()
    target = np.column_stack((
        np.asarray(ledger.q_enter_usd, np.float64),
        np.asarray(ledger.enter_advantage_usd, np.float64),
    ))
    if target.shape != (len(ledger.opportunity_id), 2) \
            or not np.all(np.isfinite(target)):
        raise ConfirmationRefusal("direct-utility target differs")
    return target


def _transform(target: np.ndarray, scale: float) -> np.ndarray:
    values = np.asarray(target, np.float64)
    if values.ndim != 2 or values.shape[1] != 2 \
            or not np.all(np.isfinite(values)) or scale <= 0:
        raise ConfirmationRefusal("direct-utility transform input differs")
    return np.arcsinh(values / float(scale))


def _inverse(prediction: np.ndarray, scale: float) -> np.ndarray:
    values = np.asarray(prediction, np.float64)
    if values.ndim == 1 and values.shape == (2,):
        values = values.reshape(1, 2)
    if values.ndim != 2 or values.shape[1] != 2 \
            or not np.all(np.isfinite(values)):
        raise ConfirmationRefusal("direct-utility prediction differs")
    # CatBoost predictions far outside the observed transformed target range
    # are extrapolation, not meaningful dollar forecasts.  The broad fixed
    # guard prevents floating overflow without clipping ordinary outcomes.
    return np.sinh(np.clip(values, -5.0, 5.0)) * float(scale)


def _series_weights(dataset: ConfirmationDataset) -> np.ndarray:
    dataset.validate()
    series = np.asarray(dataset.series_id, str)
    unique, inverse, counts = np.unique(
        series, return_inverse=True, return_counts=True)
    if not len(unique) or np.any(counts <= 0):
        raise ConfirmationRefusal("direct-utility series weights differ")
    weights = 1.0 / counts[inverse].astype(np.float64)
    weights *= len(weights) / float(weights.sum())
    if not np.all(np.isfinite(weights)) or np.any(weights <= 0):
        raise ConfirmationRefusal("direct-utility series weights are invalid")
    return weights


def _shuffle_joint_targets(
    dataset: ConfirmationDataset, target: np.ndarray, *, seed: int,
) -> np.ndarray:
    """Transfer whole target paths within asset-day, preserving recipients."""

    dataset.validate(); values = np.asarray(target, np.float64)
    if values.shape != (len(dataset.features), 2) \
            or not np.all(np.isfinite(values)):
        raise ConfirmationRefusal("direct-utility control target differs")
    series = np.asarray(dataset.series_id, str)
    asset = np.asarray(dataset.asset, str)
    day = np.asarray(dataset.day, np.int64)
    timestamp = np.asarray(dataset.snapshot_ts_ns, np.int64)
    rng = np.random.default_rng(seed); shuffled = values.copy()
    changed = 0; groups = np.asarray([
        f"{name}:{int(d8)}" for name, d8 in zip(asset, day)], str)
    for group in sorted(set(groups.tolist())):
        recipients = np.asarray(sorted(set(series[groups == group].tolist())),
                                str)
        if len(recipients) < 2:
            raise ConfirmationRefusal(
                "direct-utility control needs two series per asset-day")
        best: np.ndarray | None = None; best_distance = -1.0
        attempts = min(128, max(16, 4 * len(recipients)))
        for _attempt in range(attempts):
            donors = recipients[rng.permutation(len(recipients))]
            if np.any(donors == recipients):
                continue
            distance = 0.0
            for recipient, donor in zip(recipients, donors):
                left = np.flatnonzero(series == recipient)
                right = np.flatnonzero(series == donor)
                left = left[np.argsort(timestamp[left])]
                right = right[np.argsort(timestamp[right])]
                positions = np.rint(np.linspace(
                    0, len(right) - 1, len(left))).astype(np.int64)
                distance += float(np.sum(np.abs(
                    _transform(values[left], 600.0)
                    - _transform(values[right[positions]], 600.0))))
            if distance > best_distance:
                best_distance = distance; best = donors.copy()
        if best is None or best_distance <= 0:
            raise ConfirmationRefusal(
                f"direct-utility {group} control cannot destroy ownership")
        for recipient, donor in zip(recipients, best):
            left = np.flatnonzero(series == recipient)
            right = np.flatnonzero(series == donor)
            left = left[np.argsort(timestamp[left])]
            right = right[np.argsort(timestamp[right])]
            positions = np.rint(np.linspace(
                0, len(right) - 1, len(left))).astype(np.int64)
            shuffled[left] = values[right[positions]]
            changed += int(np.sum(np.any(
                values[left] != values[right[positions]], axis=1)))
    if not changed or np.array_equal(shuffled, values):
        raise ConfirmationRefusal(
            "direct-utility control shuffle was ineffective")
    return shuffled


def _fit(
    dataset: ConfirmationDataset, target_usd: np.ndarray, *, seed: int,
    config: DirectUtilityConfig,
) -> CatBoostRegressor:
    model = CatBoostRegressor(
        loss_function="MultiRMSE", eval_metric="MultiRMSE",
        iterations=config.iterations, depth=config.depth,
        learning_rate=config.learning_rate, l2_leaf_reg=config.l2_leaf_reg,
        random_seed=seed, thread_count=config.thread_count,
        allow_writing_files=False, verbose=False)
    model.fit(
        np.asarray(dataset.features, np.float32),
        _transform(target_usd, config.target_scale_usd),
        sample_weight=_series_weights(dataset), verbose=False)
    return model


def _model_identity(
    name: str, model: CatBoostRegressor, feature_names: Sequence[str],
    config: DirectUtilityConfig,
) -> str:
    return C.object_sha256({
        "schema": MODEL_SCHEMA, "name": name,
        "config_sha256": config.receipt_sha256,
        "target_names": TARGET_NAMES,
        "target_transform": "ASINH_USD_OVER_FIXED_SCALE",
        "tree_count": int(model.tree_count_),
        "feature_names": tuple(feature_names),
        "parameters": model.get_all_params(),
    })


def fit_direct_utility_models(
    fit_dataset: ConfirmationDataset, fit_ledger: OracleActionLedger, *,
    config: DirectUtilityConfig = DirectUtilityConfig(),
) -> DirectUtilityModels:
    fit_dataset.validate(); fit_ledger.validate()
    if (fit_ledger.source_representation_sha256
            != fit_dataset.representation_sha256
            or not np.array_equal(
                fit_dataset.opportunity_id, fit_ledger.opportunity_id)):
        raise ConfirmationRefusal("direct-utility FIT identity differs")
    target = _targets(fit_ledger)
    control_target = _shuffle_joint_targets(
        fit_dataset, target, seed=config.control_seed)
    real = _fit(fit_dataset, target, seed=config.seed, config=config)
    control = _fit(
        fit_dataset, control_target, seed=config.seed + 10_000,
        config=config)
    return DirectUtilityModels(
        real=real, control=control, feature_names=fit_dataset.feature_names,
        real_model_sha256=_model_identity(
            "REAL", real, fit_dataset.feature_names, config),
        control_model_sha256=_model_identity(
            "CONTROL", control, fit_dataset.feature_names, config),
    )


def _policies(config: DirectUtilityConfig) -> tuple[DirectUtilityPolicy, ...]:
    rows = tuple(DirectUtilityPolicy(enter, advantage)
                 for enter in config.enter_thresholds_usd
                 for advantage in config.advantage_thresholds_usd)
    if not rows or len({row.receipt_sha256 for row in rows}) != len(rows):
        raise ConfirmationRefusal("direct-utility policy grid differs")
    return rows


def _preflight(
    conditional: Mapping[str, ConfirmationDataset],
    ledgers: Mapping[str, OracleActionLedger],
    fixed: Mapping[str, ConfirmationDataset],
    fixed_ledgers: Mapping[str, OracleActionLedger],
    expected_sessions: Mapping[str, Sequence[SessionRef]], *,
    rank_model, rank_control_model,
    config: DirectUtilityConfig,
) -> Mapping[str, object]:
    _validate_roles(conditional, ledgers, fixed, expected_sessions)
    gates, watches = _rank_rosters(
        fixed, fixed_ledgers, rank_model=rank_model,
        rank_control_model=rank_control_model, capacity=config.capacity)
    support = {}; fit_control = None
    for role in ROLES:
        dataset, ledger = _gated_role(
            conditional[role], ledgers[role], gates[role]["LEARNED"],
            watches[role])
        target = _targets(ledger)
        _series_weights(dataset)
        support[role] = {
            "rows": len(dataset.features),
            "series": len(set(np.asarray(dataset.series_id, str).tolist())),
            "q_enter_positive_rows": int(np.sum(target[:, 0] > 0)),
            "advantage_positive_rows": int(np.sum(target[:, 1] > 0)),
            "q_enter_quantiles_usd": tuple(float(value) for value in
                np.quantile(target[:, 0], (0, .1, .25, .5, .75, .9, 1))),
            "advantage_quantiles_usd": tuple(float(value) for value in
                np.quantile(target[:, 1], (0, .1, .25, .5, .75, .9, 1))),
        }
        if role == "FIT":
            destroyed = _shuffle_joint_targets(
                dataset, target, seed=config.control_seed)
            fit_control = {
                "changed_rows": int(np.sum(np.any(
                    destroyed != target, axis=1))),
                "recipient_features_unchanged": True,
                "joint_target_transfer": True,
            }
    core = {
        "schema": "QRE2CONFDIRECTUTILITYPREFLIGHT1",
        "config_sha256": config.receipt_sha256,
        "target_names": TARGET_NAMES,
        "target_units": "USD",
        "target_transform": "ASINH_USD_OVER_FIXED_SCALE",
        "support": support,
        "fit_control": fit_control,
        "policy_count": len(_policies(config)),
        "rank_gate": "DEPLOYABLE_LEARNED_TOP_CAPACITY",
        "oracle_gate_used_for_training": False,
        "platt_used_for_training": False,
        "threshold_used_for_training_or_selection": False,
        "models_executed": False,
        "economics_executed": False,
        "implementation_sha256": C.file_sha256(Path(__file__)),
        "forward_open_count": 0,
        "h2_open_count": 0,
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


def direct_utility_preflight(
    conditional: Mapping[str, ConfirmationDataset],
    ledgers: Mapping[str, OracleActionLedger],
    fixed: Mapping[str, ConfirmationDataset],
    fixed_ledgers: Mapping[str, OracleActionLedger],
    expected_sessions: Mapping[str, Sequence[SessionRef]], *,
    rank_model, rank_control_model,
    config: DirectUtilityConfig = DirectUtilityConfig(),
) -> Mapping[str, object]:
    return _preflight(
        conditional, ledgers, fixed, fixed_ledgers, expected_sessions,
        rank_model=rank_model, rank_control_model=rank_control_model,
        config=config)


def _predict(
    model: CatBoostRegressor, dataset: ConfirmationDataset, *, scale: float,
) -> np.ndarray:
    prediction = model.predict(np.asarray(dataset.features, np.float32))
    result = _inverse(prediction, scale)
    if result.shape != (len(dataset.features), 2):
        raise ConfirmationRefusal("direct-utility prediction width differs")
    return result


def _first_triggers(
    dataset: ConfirmationDataset, prediction: np.ndarray,
    policy: DirectUtilityPolicy,
) -> np.ndarray:
    values = np.asarray(prediction, np.float64)
    if values.shape != (len(dataset.features), 2):
        raise ConfirmationRefusal("direct-utility trigger scores differ")
    passing = ((values[:, 0] >= policy.min_q_enter_usd)
               & (values[:, 1] >= policy.min_enter_advantage_usd))
    order = confirmation_series_time_order(dataset)
    eligible = order[passing[order]]
    if not len(eligible):
        return np.empty(0, np.int64)
    series = np.asarray(dataset.series_id, str)[eligible]
    return eligible[np.r_[True, series[1:] != series[:-1]]]


def _replay_policy(
    dataset: ConfirmationDataset, prediction: np.ndarray,
    policy: DirectUtilityPolicy, sessions: Sequence[SessionRef], *,
    model_hash: str,
) -> EntryEvaluation:
    chosen = _first_triggers(dataset, prediction, policy)
    if not len(chosen):
        raise ConfirmationRefusal("direct-utility policy produced empty book")
    arrivals = tuple(_arrival(
        dataset, int(index), model_hash=model_hash,
        expected_pnl_usd=float(prediction[index, 0]),
        # Diagnostic adapter only.  No report calls this a calibrated q20.
        pnl_q20_usd=float(prediction[index, 0]),
        goal_probability=float(prediction[index, 1]
                               >= policy.min_enter_advantage_usd),
        wall_probability=0.0, mae_q90_usd=0.0,
    ) for index in chosen)
    return replay(arrivals, expected_sessions=sessions)


def _score_grid(
    dataset: ConfirmationDataset, prediction: np.ndarray,
    sessions: Sequence[SessionRef], policies: Sequence[DirectUtilityPolicy], *,
    model_hash: str,
) -> Mapping[str, object]:
    cards = []; evaluations = {}
    for policy in policies:
        try:
            evaluation = _replay_policy(
                dataset, prediction, policy, sessions, model_hash=model_hash)
        except ConfirmationRefusal as exc:
            cards.append({
                "policy": asdict(policy),
                "policy_sha256": policy.receipt_sha256,
                "status": "EMPTY_OR_REFUSED", "reason": str(exc),
            })
            continue
        summary = _evaluation_summary(evaluation, sessions)
        days = sum(row.trades > 0 for row in evaluation.asset_day_results)
        feasibility = threshold_feasibility(
            trades=evaluation.trades,
            usd_per_trade=evaluation.usd_per_trade,
            max_drawdown_usd=evaluation.max_drawdown_usd,
            days_with_trades=days, eligible_days=evaluation.asset_days)
        card = {
            "policy": asdict(policy),
            "policy_sha256": policy.receipt_sha256,
            "status": "MEASURED", "evaluation": summary,
            "feasible": feasibility.feasible,
            "feasibility_reasons": feasibility.reasons,
            "feasibility_sha256": feasibility.receipt_sha256,
        }
        cards.append(card); evaluations[policy.receipt_sha256] = card
    measured = [row for row in cards if row["status"] == "MEASURED"]
    feasible = [row for row in measured if row["feasible"]]
    pool = feasible or measured
    selected = None if not pool else min(pool, key=lambda row: (
        -float(row["evaluation"]["total_pnl_usd"]),
        float(row["evaluation"]["max_drawdown_usd"]),
        row["policy_sha256"]))
    core = {
        "status": ("EMPTY_GRID" if selected is None else
                   ("SELECTED" if feasible else "NO_FEASIBLE_THRESHOLD")),
        "selection_basis": (None if selected is None else
                            ("ABSOLUTE_LAWS" if feasible
                             else "BEST_NONFEASIBLE_DIAGNOSTIC")),
        "selected": selected,
        "scorecards": tuple(cards),
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


def _fixed_policy(
    dataset: ConfirmationDataset, prediction: np.ndarray,
    policy: DirectUtilityPolicy | None, sessions: Sequence[SessionRef], *,
    model_hash: str,
) -> Mapping[str, object]:
    if policy is None:
        return {"status": "NO_POLICY"}
    try:
        value = _replay_policy(
            dataset, prediction, policy, sessions, model_hash=model_hash)
    except ConfirmationRefusal as exc:
        return {"status": "EMPTY_OR_REFUSED", "reason": str(exc)}
    return {"status": "MEASURED",
            "evaluation": _evaluation_summary(value, sessions)}


def _regression_metrics(
    target: np.ndarray, prediction: np.ndarray,
) -> Mapping[str, object]:
    truth = np.asarray(target, np.float64)
    pred = np.asarray(prediction, np.float64)
    rows = {}
    for index, name in enumerate(TARGET_NAMES):
        error = pred[:, index] - truth[:, index]
        correlation = float(spearmanr(
            truth[:, index], pred[:, index]).statistic)
        rows[name] = {
            "mae_usd": float(np.mean(np.abs(error))),
            "rmse_usd": float(np.sqrt(np.mean(error ** 2))),
            "spearman": correlation if np.isfinite(correlation) else None,
            "prediction_quantiles_usd": tuple(float(value) for value in
                np.quantile(pred[:, index], (0, .1, .5, .9, 1))),
            "selection_metric": False,
        }
    return rows


def _argmax_replay(
    dataset: ConfirmationDataset, prediction: np.ndarray, score: np.ndarray,
    sessions: Sequence[SessionRef], *, name: str, model_hash: str,
) -> Mapping[str, object]:
    """Replay one future-argmax row per path without outcome reselection."""

    prediction = np.asarray(prediction, np.float64)
    values = np.asarray(score, np.float64)
    if (prediction.shape != (len(dataset.features), 2)
            or values.shape != (len(dataset.features),)) \
            or not np.all(np.isfinite(values)):
        raise ConfirmationRefusal("direct-utility argmax score differs")
    series = np.asarray(dataset.series_id, str)
    timestamp = np.asarray(dataset.snapshot_ts_ns, np.int64)
    ids = np.asarray(dataset.opportunity_id, str)
    chosen = []
    for key in sorted(set(series.tolist())):
        local = np.flatnonzero(series == key)
        ordered = local[np.lexsort((ids[local], timestamp[local],
                                    -values[local]))]
        chosen.append(int(ordered[0]))
    arrivals = tuple(_arrival(
        dataset, index, model_hash=model_hash,
        # Priority must be the audited score, not future realized PnL.
        expected_pnl_usd=float(values[index]),
        pnl_q20_usd=float(values[index]), goal_probability=1.0,
        wall_probability=0.0, mae_q90_usd=0.0,
    ) for index in chosen)
    evaluation = replay(arrivals, expected_sessions=sessions)
    core = {
        "scope": "MODEL_SCORE_PATH_ARGMAX_CANONICAL_REPLAY_NOT_DEPLOYABLE",
        "score": name, "selected_rows": len(chosen),
        "evaluation": _evaluation_summary(evaluation, sessions),
        "future_path_argmax_used": True,
        "outcome_based_schedule_reselection_used": False,
        "exact_replay_ceiling": False,
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


def run_direct_utility_policy(
    conditional: Mapping[str, ConfirmationDataset],
    ledgers: Mapping[str, OracleActionLedger],
    fixed: Mapping[str, ConfirmationDataset],
    fixed_ledgers: Mapping[str, OracleActionLedger],
    expected_sessions: Mapping[str, Sequence[SessionRef]], *,
    rank_model, rank_control_model,
    models: DirectUtilityModels,
    config: DirectUtilityConfig = DirectUtilityConfig(),
) -> Mapping[str, object]:
    """Measure direct-label learning and causal conversion on PLATT only."""

    preflight = _preflight(
        conditional, ledgers, fixed, fixed_ledgers, expected_sessions,
        rank_model=rank_model, rank_control_model=rank_control_model,
        config=config)
    if (models.feature_names != conditional["FIT"].feature_names
            or len(models.real.feature_names_) != len(models.feature_names)
            or len(models.control.feature_names_) != len(models.feature_names)):
        raise ConfirmationRefusal("direct-utility model schema differs")
    gates, watches = _rank_rosters(
        fixed, fixed_ledgers, rank_model=rank_model,
        rank_control_model=rank_control_model, capacity=config.capacity)
    gated = {role: _gated_role(
        conditional[role], ledgers[role], gates[role]["LEARNED"],
        watches[role]) for role in ROLES}
    predictions = {role: {
        "REAL": _predict(models.real, gated[role][0],
                         scale=config.target_scale_usd),
        "CONTROL": _predict(models.control, gated[role][0],
                            scale=config.target_scale_usd),
        "ORACLE": _targets(gated[role][1]),
    } for role in ROLES}

    metrics = {}
    for role in ("FIT", "PLATT"):
        truth = predictions[role]["ORACLE"]
        metrics[role] = {
            kind: _regression_metrics(truth, predictions[role][kind])
            for kind in ("REAL", "CONTROL")}

    role = "PLATT"; dataset, _ledger = gated[role]
    sessions = expected_sessions[role]; grid = _policies(config)
    selection = _score_grid(
        dataset, predictions[role]["REAL"], sessions, grid,
        model_hash=models.real_model_sha256)
    oracle_selection = _score_grid(
        dataset, predictions[role]["ORACLE"], sessions, grid,
        model_hash="oracle-direct-utility-policy-family")
    selected_row = selection["selected"]
    frozen = (None if selected_row is None else DirectUtilityPolicy(
        **selected_row["policy"]))
    fixed_arms = {
        "REAL": _fixed_policy(
            dataset, predictions[role]["REAL"], frozen, sessions,
            model_hash=models.real_model_sha256),
        "CONTROL": _fixed_policy(
            dataset, predictions[role]["CONTROL"], frozen, sessions,
            model_hash=models.control_model_sha256),
        "ORACLE": _fixed_policy(
            dataset, predictions[role]["ORACLE"], frozen, sessions,
            model_hash="oracle-direct-utility-fixed-policy"),
    }
    roster_ceiling = _sparse_schedule_ceiling(dataset, sessions)
    ceiling_day = float(
        roster_ceiling["evaluation"]["usd_per_portfolio_day"])
    real_day = (0.0 if fixed_arms["REAL"]["status"] != "MEASURED" else
                float(fixed_arms["REAL"]["evaluation"]
                      ["usd_per_portfolio_day"]))
    control_day = (
        0.0 if fixed_arms["CONTROL"]["status"] != "MEASURED" else
        float(fixed_arms["CONTROL"]["evaluation"]
              ["usd_per_portfolio_day"]))
    oracle_best = oracle_selection["selected"]
    oracle_day = (0.0 if oracle_best is None else
                  float(oracle_best["evaluation"]
                        ["usd_per_portfolio_day"]))
    capture = real_day / ceiling_day
    control_capture = control_day / ceiling_day
    oracle_policy_capture = oracle_day / ceiling_day
    reasons = []
    if oracle_policy_capture < config.minimum_roster_capture:
        reasons.append("ORACLE_POLICY_FAMILY_CAPTURE_BELOW_MINIMUM")
    if capture < config.minimum_roster_capture:
        reasons.append("LEARNED_ROSTER_CAPTURE_BELOW_MINIMUM")
    if capture < control_capture + config.minimum_control_gap:
        reasons.append("LEARNED_CONTROL_CAPTURE_GAP_BELOW_MINIMUM")
    progression = ("WITHIN_ROSTER_RECOVERY_PASS_BROADEN_GATE_NEXT"
                   if not reasons else "NO_PROGRESSION")

    argmax = {}
    for kind in ("REAL", "CONTROL", "ORACLE"):
        pred = predictions[role][kind]
        model_hash = ({
            "REAL": models.real_model_sha256,
            "CONTROL": models.control_model_sha256,
            "ORACLE": "oracle-direct-utility-argmax",
        }[kind])
        argmax[kind] = {
            "Q_ENTER": _argmax_replay(
                dataset, pred, pred[:, 0], sessions, name="Q_ENTER",
                model_hash=model_hash),
            "ENTER_ADVANTAGE": _argmax_replay(
                dataset, pred, pred[:, 1], sessions, name="ENTER_ADVANTAGE",
                model_hash=model_hash),
            "JOINT_SUM": _argmax_replay(
                dataset, pred, pred[:, 0] + pred[:, 1], sessions,
                name="Q_ENTER_PLUS_ENTER_ADVANTAGE", model_hash=model_hash),
        }

    importance = np.asarray(models.real.get_feature_importance(), np.float64)
    order = np.argsort(-importance, kind="stable")[:40]
    feature_importance = tuple({
        "feature": models.feature_names[int(index)],
        "importance": float(importance[int(index)]),
    } for index in order)
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
        "target_names": TARGET_NAMES,
        "target_units": "USD",
        "target_transform": "ASINH_USD_OVER_FIXED_SCALE",
        "platt_selection": selection,
        "platt_oracle_policy_family": oracle_selection,
        "frozen_policy": None if frozen is None else asdict(frozen),
        "platt_fixed_policy_arms": fixed_arms,
        "platt_sparse_roster_ceiling": roster_ceiling,
        "platt_capture": {
            "real": capture, "control": control_capture,
            "oracle_policy_family": oracle_policy_capture,
        },
        "platt_model_score_argmax_replay_diagnostics": argmax,
        "regression_metrics_not_selection": metrics,
        "top_feature_importance_fit_only": feature_importance,
        "progression_status": progression,
        "progression_reasons": tuple(reasons),
        "threshold_economics_executed": False,
        "learned_economics_executed": True,
        "economics_scope": "E1R_PLATT_SPARSE_TRAINING_GRID_DIAGNOSTIC",
        "canonical_replay_executed": True,
        "exact_replay_ceiling_executed": False,
        "diagnostic_entry_score_adapter":
            "Q_ENTER_REPEATED_AS_LOWER_FIELD_NOT_A_CALIBRATED_Q20",
        "implementation_sha256": C.file_sha256(Path(__file__)),
        "forward_open_count": 0,
        "h2_open_count": 0,
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


__all__ = [
    "DirectUtilityConfig", "DirectUtilityModels", "DirectUtilityPolicy",
    "direct_utility_preflight", "fit_direct_utility_models",
    "run_direct_utility_policy",
]
