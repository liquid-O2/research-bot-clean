"""Compose the fixed-watch value ranker with a causal entry-timing head.

This is a bounded diagnostic, not a replacement production learner.  The
candidate-quality head sees exactly one row at the frozen watch age.  Its
selected native candidates are then followed on the ordinary causal path and
the timing head may enter only at the first registered threshold crossing.
Every economic number is produced by the canonical arrival replay.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final, Iterable, Mapping, Sequence

import catboost
from catboost import CatBoostClassifier
import numpy as np

from . import common as C
from .confirmation import ConfirmationDataset, ConfirmationRefusal
from .confirmation_action_probe import _balanced_binary_weights
from .confirmation_capacity_probe import (
    _balanced_group_class_weights, capacity_topk_labels,
)
from .confirmation_candidate_rank import (
    CURRENT_TARGET_SCOPE, candidate_rank_diagnostic,
)
from .confirmation_diagnostics import (
    PolicyGridEvaluation, registered_feature_sets, score_confirmation_policies,
)
from .confirmation_model import ConfirmationPredictions
from .confirmation_policy import (
    ConfirmationPolicy, replay_confirmation,
)
from .confirmation_stopping import (
    ENTER, OracleActionLedger, registered_oracle_label_family,
)
from .contracts import EntryEvaluation, SessionRef


SCHEMA: Final = "QRE2CONFFACTPOL1"
ROLES: Final = ("FIT", "PLATT", "THRESHOLD")
DEFAULT_CLOCK_EXCLUSIONS: Final = (
    "phase_remaining_sec",
    "disc_fvol_session_age_now_sec",
    "disc_fvol_session_scope_elapsed_sec",
    "disc_fvol_session_scope_remaining_sec",
    "disc_fvol_phase_age_now_sec",
    "disc_fvol_phase_scope_elapsed_sec",
    "disc_fvol_phase_scope_remaining_sec",
)


@dataclass(frozen=True, slots=True)
class FactorizedPolicyConfig:
    watch_age_sec: int = 30
    capacity: int = 4
    action_feature_set: str = "MAX_W300"
    action_label: str = "EXACT_ENTER"
    excluded_action_features: tuple[str, ...] = DEFAULT_CLOCK_EXCLUSIONS
    rank_iterations: int = 40
    action_iterations: int = 22
    depth: int = 5
    rank_learning_rate: float = .05
    action_learning_rate: float = .08
    rank_l2_leaf_reg: float = 12.0
    action_l2_leaf_reg: float = 10.0
    rank_seed: int = 20261920
    action_seed: int = 20260819
    control_seed: int = 20270820
    thread_count: int = 16
    action_thresholds: tuple[float, ...] = (
        .01, .025, .05, .075, .10, .15, .20, .25, .30, .35, .40,
        .45, .50, .55, .60, .65, .70, .75, .80, .85, .90, .925,
        .95, .975, .99,
    )

    def __post_init__(self) -> None:
        thresholds = tuple(float(value) for value in self.action_thresholds)
        excluded = tuple(str(value) for value in self.excluded_action_features)
        if (not 0 <= self.watch_age_sec <= 300
                or not 1 <= self.capacity <= 12
                or not self.action_feature_set or not self.action_label
                or excluded != self.excluded_action_features
                or len(set(excluded)) != len(excluded)
                or any(not value for value in excluded)
                or not 5 <= self.rank_iterations <= 500
                or not 5 <= self.action_iterations <= 500
                or not 3 <= self.depth <= 8
                or not 0 < self.rank_learning_rate <= .3
                or not 0 < self.action_learning_rate <= .3
                or not 0 < self.rank_l2_leaf_reg <= 1_000
                or not 0 < self.action_l2_leaf_reg <= 1_000
                or not 1 <= self.thread_count <= C.MAX_CPU_WORKERS
                or thresholds != tuple(sorted(set(thresholds)))
                or not thresholds or thresholds[0] <= 0.0
                or thresholds[-1] >= 1.0):
            raise ConfirmationRefusal("factorized-policy configuration is invalid")

    @property
    def receipt_sha256(self) -> str:
        return C.object_sha256({"schema": SCHEMA, **asdict(self)})


@dataclass(frozen=True, slots=True)
class FactorizedModels:
    rank: CatBoostClassifier
    rank_control: CatBoostClassifier
    action: CatBoostClassifier
    action_control: CatBoostClassifier
    action_columns: np.ndarray
    action_feature_names: tuple[str, ...]
    rank_model_sha256: str
    rank_control_model_sha256: str
    action_model_sha256: str
    action_control_model_sha256: str


def _validate_roles(
    full: Mapping[str, ConfirmationDataset],
    full_ledgers: Mapping[str, OracleActionLedger],
    fixed: Mapping[str, ConfirmationDataset],
    fixed_ledgers: Mapping[str, OracleActionLedger],
) -> None:
    if (set(full) != set(ROLES) or set(full_ledgers) != set(ROLES)
            or set(fixed) != set(ROLES) or set(fixed_ledgers) != set(ROLES)):
        raise ConfirmationRefusal("factorized-policy role roster differs")
    for role in ROLES:
        full[role].validate(); full_ledgers[role].validate()
        fixed[role].validate(); fixed_ledgers[role].validate()
        if (full_ledgers[role].source_representation_sha256
                != full[role].representation_sha256
                or fixed_ledgers[role].source_representation_sha256
                != fixed[role].representation_sha256
                or not np.array_equal(
                    full[role].opportunity_id, full_ledgers[role].opportunity_id)
                or not np.array_equal(
                    fixed[role].opportunity_id, fixed_ledgers[role].opportunity_id)):
            raise ConfirmationRefusal("factorized-policy ledger identity differs")
        full_series = set(np.asarray(full[role].series_id, str).tolist())
        fixed_series = np.asarray(fixed[role].series_id, str)
        if (len(fixed_series) != len(set(fixed_series.tolist()))
                or not set(fixed_series.tolist()) <= full_series):
            raise ConfirmationRefusal("fixed-watch/full-path series roster differs")
    if (full["FIT"].feature_names != full["PLATT"].feature_names
            or full["FIT"].feature_names != full["THRESHOLD"].feature_names
            or fixed["FIT"].feature_names != fixed["PLATT"].feature_names
            or fixed["FIT"].feature_names != fixed["THRESHOLD"].feature_names
            or int(np.max(full["FIT"].day)) >= int(np.min(full["PLATT"].day))
            or int(np.max(full["PLATT"].day))
               >= int(np.min(full["THRESHOLD"].day))):
        raise ConfirmationRefusal("factorized-policy schemas/chronology differ")


def select_top_capacity_series(
    dataset: ConfirmationDataset, score: np.ndarray, *, capacity: int,
) -> tuple[str, ...]:
    """Select deterministic top-k native candidates in every asset-day."""

    dataset.validate()
    values = np.asarray(score, np.float64)
    if (values.shape != (len(dataset.features),)
            or not np.all(np.isfinite(values)) or not 1 <= capacity <= 12
            or len(set(np.asarray(dataset.series_id, str).tolist()))
               != len(values)):
        raise ConfirmationRefusal("factorized rank gate inputs differ")
    asset = np.asarray(dataset.asset, str)
    day = np.asarray(dataset.day, np.int64)
    series = np.asarray(dataset.series_id, str)
    selected: list[str] = []
    groups = np.asarray([
        f"{name}:{int(d8)}" for name, d8 in zip(asset, day)], str)
    for group in np.unique(groups):
        local = np.flatnonzero(groups == group)
        ordered = local[np.lexsort((series[local], -values[local]))]
        selected.extend(series[ordered[:capacity]].tolist())
    if not selected or len(selected) != len(set(selected)):
        raise ConfirmationRefusal("factorized rank gate is empty/duplicated")
    return tuple(sorted(selected))


def _shuffle_rank_target(
    dataset: ConfirmationDataset, target: np.ndarray, *, seed: int,
) -> np.ndarray:
    values = np.asarray(target, np.float64)
    if values.shape != (len(dataset.features),):
        raise ConfirmationRefusal("rank-control target differs")
    rng = np.random.default_rng(seed)
    groups = np.asarray([
        f"{asset}:{int(day)}" for asset, day in zip(dataset.asset, dataset.day)
    ], str)
    shuffled = values.copy()
    changed = False
    for group in np.unique(groups):
        indices = np.flatnonzero(groups == group)
        if len(indices) > 1:
            donor = rng.permutation(indices)
            shuffled[indices] = values[donor]
            changed |= not np.array_equal(indices, donor)
    if not changed:
        raise ConfirmationRefusal("rank-control shuffle was ineffective")
    return shuffled


def _model_identity(
    name: str, model: CatBoostClassifier, feature_names: Sequence[str],
    config_sha256: str,
) -> str:
    return C.object_sha256({
        "schema": "QRE2CONFFACTMODEL1", "name": name,
        "config_sha256": config_sha256,
        "tree_count": int(model.tree_count_),
        "feature_names": tuple(feature_names),
        "parameters": model.get_all_params(),
    })


def factorized_policy_preflight(
    full: Mapping[str, ConfirmationDataset],
    full_ledgers: Mapping[str, OracleActionLedger],
    fixed: Mapping[str, ConfirmationDataset],
    fixed_ledgers: Mapping[str, OracleActionLedger],
    expected_sessions: Mapping[str, Sequence[SessionRef]], *,
    config: FactorizedPolicyConfig = FactorizedPolicyConfig(),
) -> Mapping[str, object]:
    """Close every data/support boundary that is knowable before fitting."""

    _validate_roles(full, full_ledgers, fixed, fixed_ledgers)
    if set(expected_sessions) != set(ROLES):
        raise ConfirmationRefusal("factorized preflight session roster differs")
    masks = registered_feature_sets(full["FIT"].feature_names)
    if config.action_feature_set not in masks:
        raise ConfirmationRefusal("factorized preflight feature set is unknown")
    selected_names = np.asarray(full["FIT"].feature_names, str)[
        np.flatnonzero(masks[config.action_feature_set])]
    absent = set(config.excluded_action_features) - set(selected_names.tolist())
    if absent:
        raise ConfirmationRefusal(
            f"factorized preflight exclusions are absent: {sorted(absent)}")
    final_names = tuple(name for name in selected_names.tolist()
                        if name not in set(config.excluded_action_features))
    if not final_names:
        raise ConfirmationRefusal("factorized preflight feature roster is empty")
    support = {}
    for role in ROLES:
        fixed_indices = np.arange(len(fixed[role].features), dtype=np.int64)
        rank_y = capacity_topk_labels(
            fixed[role], fixed_indices, fixed_ledgers[role].q_optimal_usd,
            capacity=config.capacity)
        _balanced_group_class_weights(
            fixed[role], fixed_indices, rank_y)
        labels = registered_oracle_label_family(full_ledgers[role])
        if config.action_label not in labels:
            raise ConfirmationRefusal("factorized preflight action label is unknown")
        action_y = np.asarray(labels[config.action_label], np.int8)
        _balanced_binary_weights(full[role], action_y)
        fixed_series_array = np.asarray(fixed[role].series_id, str)
        fixed_series = set(fixed_series_array.tolist())
        watch_ts = {str(series): int(timestamp) for series, timestamp in zip(
            fixed_series_array, fixed[role].snapshot_ts_ns)}
        watch_id = {str(series): str(opportunity) for series, opportunity in zip(
            fixed_series_array, fixed[role].opportunity_id)}
        full_series = np.asarray(full[role].series_id, str)
        full_age = np.asarray(full[role].min_alert_age_sec, np.float64)
        full_ts = np.asarray(full[role].snapshot_ts_ns, np.int64)
        cutoff = np.asarray([
            watch_ts.get(str(series), np.iinfo(np.int64).max)
            for series in full_series], np.int64)
        eligible = (full_ts >= cutoff) & (full_age <= 300.0)
        if set(full_series[eligible].tolist()) != fixed_series:
            raise ConfirmationRefusal("factorized preflight watched path is incomplete")
        for series in fixed_series:
            local = np.flatnonzero((full_series == series) & eligible)
            earliest = local[np.argmin(full_ts[local])]
            if (int(full_ts[earliest]) != watch_ts[series]
                    or str(full[role].opportunity_id[earliest])
                       != watch_id[series]):
                raise ConfirmationRefusal(
                    "factorized preflight path does not begin at fixed-watch row")
        sessions = tuple(expected_sessions[role])
        if not sessions or len(sessions) != len(set(sessions)):
            raise ConfirmationRefusal("factorized preflight sessions are malformed")
        full_pairs = set(zip(np.asarray(full[role].asset, str).tolist(),
                             np.asarray(full[role].day, np.int64).tolist()))
        session_pairs = {(row.asset, int(row.trading_day)) for row in sessions}
        if not full_pairs <= session_pairs:
            raise ConfirmationRefusal(
                "factorized preflight denominator omits candidate sessions")
        support[role] = {
            "full_rows": len(full[role].features),
            "full_series": len(set(full_series.tolist())),
            "fixed_rows": len(fixed[role].features),
            "watched_path_rows": int(np.sum(eligible)),
            "rank_negative": int(np.sum(rank_y == 0)),
            "rank_positive": int(np.sum(rank_y == 1)),
            "action_negative": int(np.sum(action_y == 0)),
            "action_positive": int(np.sum(action_y == 1)),
            "expected_sessions": len(sessions),
        }
    core = {
        "schema": "QRE2CONFFACTPOLPREFLIGHT1",
        "config_sha256": config.receipt_sha256,
        "rank_feature_count": len(fixed["FIT"].feature_names),
        "action_feature_count": len(final_names),
        "action_feature_names_sha256": C.object_sha256(final_names),
        "support": support,
        "threshold_count": len(_threshold_grid(config)),
        "all_required_training_weights_constructed": True,
        "canonical_replay_import_bound": True,
        "models_executed": False,
        "economics_executed": False,
        "forward_open_count": 0,
        "h2_open_count": 0,
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


def fit_factorized_models(
    full: Mapping[str, ConfirmationDataset],
    full_ledgers: Mapping[str, OracleActionLedger],
    fixed: Mapping[str, ConfirmationDataset],
    fixed_ledgers: Mapping[str, OracleActionLedger], *,
    config: FactorizedPolicyConfig = FactorizedPolicyConfig(),
) -> FactorizedModels:
    """Fit the frozen rank/action heads and their matched target controls."""

    _validate_roles(full, full_ledgers, fixed, fixed_ledgers)
    rank_target = np.asarray(
        fixed_ledgers["FIT"].q_optimal_usd, np.float64)
    rank_y = capacity_topk_labels(
        fixed["FIT"], np.arange(len(rank_target)), rank_target,
        capacity=config.capacity)
    rank_weight = _balanced_group_class_weights(
        fixed["FIT"], np.arange(len(rank_target)), rank_y)
    rank_common = dict(
        loss_function="Logloss", eval_metric="PRAUC:type=Classic",
        iterations=config.rank_iterations, depth=config.depth,
        learning_rate=config.rank_learning_rate,
        l2_leaf_reg=config.rank_l2_leaf_reg,
        thread_count=config.thread_count, allow_writing_files=False,
        verbose=False)
    rank = CatBoostClassifier(random_seed=config.rank_seed, **rank_common)
    rank.fit(fixed["FIT"].features, rank_y,
             sample_weight=rank_weight, verbose=False)

    shuffled_rank_target = _shuffle_rank_target(
        fixed["FIT"], rank_target, seed=config.control_seed)
    shuffled_rank_y = capacity_topk_labels(
        fixed["FIT"], np.arange(len(rank_target)), shuffled_rank_target,
        capacity=config.capacity)
    shuffled_rank_weight = _balanced_group_class_weights(
        fixed["FIT"], np.arange(len(rank_target)), shuffled_rank_y)
    rank_control = CatBoostClassifier(
        random_seed=config.rank_seed + 10_000, **rank_common)
    rank_control.fit(
        fixed["FIT"].features, shuffled_rank_y,
        sample_weight=shuffled_rank_weight, verbose=False)

    masks = registered_feature_sets(full["FIT"].feature_names)
    if config.action_feature_set not in masks:
        raise ConfirmationRefusal("factorized action feature set is unknown")
    action_columns = np.flatnonzero(masks[config.action_feature_set])
    names = np.asarray(full["FIT"].feature_names, str)[action_columns]
    absent = set(config.excluded_action_features) - set(names.tolist())
    if absent:
        raise ConfirmationRefusal(
            f"factorized action exclusions are absent: {sorted(absent)}")
    keep = np.asarray([
        name not in set(config.excluded_action_features) for name in names], bool)
    action_columns = action_columns[keep]
    action_feature_names = tuple(names[keep].tolist())
    if not len(action_columns):
        raise ConfirmationRefusal("factorized action roster is empty")
    label_family = registered_oracle_label_family(full_ledgers["FIT"])
    if config.action_label not in label_family:
        raise ConfirmationRefusal("factorized action label is unknown")
    action_y = np.asarray(label_family[config.action_label], np.int8)
    action_weight = _balanced_binary_weights(full["FIT"], action_y)
    action_x = np.asarray(
        full["FIT"].features[:, action_columns], np.float32)
    action_common = dict(
        loss_function="Logloss", eval_metric="AUC",
        iterations=config.action_iterations, depth=config.depth,
        learning_rate=config.action_learning_rate,
        l2_leaf_reg=config.action_l2_leaf_reg,
        thread_count=config.thread_count, allow_writing_files=False,
        verbose=False)
    action = CatBoostClassifier(random_seed=config.action_seed, **action_common)
    action.fit(action_x, action_y, sample_weight=action_weight, verbose=False)

    # Recipient-fixed whole-path label destruction.  It preserves the feature
    # rows and each native path length while removing outcome ownership.
    series = np.asarray(full["FIT"].series_id, str)
    asset = np.asarray(full["FIT"].asset, str)
    rng = np.random.default_rng(config.control_seed + 1)
    shuffled_action_y = action_y.copy()
    for name in sorted(set(asset.tolist())):
        recipients = np.asarray(sorted(set(series[asset == name].tolist())), str)
        if len(recipients) < 2:
            raise ConfirmationRefusal("action control needs two series per asset")
        donors = np.roll(recipients[rng.permutation(len(recipients))], 1)
        if np.any(recipients == donors):
            donors = np.roll(recipients, 1)
        for recipient, donor in zip(recipients, donors):
            left = np.flatnonzero(series == recipient)
            right = np.flatnonzero(series == donor)
            left = left[np.argsort(full["FIT"].snapshot_ts_ns[left])]
            right = right[np.argsort(full["FIT"].snapshot_ts_ns[right])]
            position = np.rint(np.linspace(
                0, len(right) - 1, len(left))).astype(np.int64)
            shuffled_action_y[left] = action_y[right[position]]
    if (np.array_equal(shuffled_action_y, action_y)
            or len(np.unique(shuffled_action_y)) != 2):
        raise ConfirmationRefusal("action-control shuffle was ineffective")
    control_weight = _balanced_binary_weights(
        full["FIT"], shuffled_action_y)
    action_control = CatBoostClassifier(
        random_seed=config.action_seed + 10_000, **action_common)
    action_control.fit(
        action_x, shuffled_action_y, sample_weight=control_weight,
        verbose=False)
    del action_x

    return FactorizedModels(
        rank=rank, rank_control=rank_control,
        action=action, action_control=action_control,
        action_columns=action_columns,
        action_feature_names=action_feature_names,
        rank_model_sha256=_model_identity(
            "RANK", rank, fixed["FIT"].feature_names,
            config.receipt_sha256),
        rank_control_model_sha256=_model_identity(
            "RANK_CONTROL", rank_control, fixed["FIT"].feature_names,
            config.receipt_sha256),
        action_model_sha256=_model_identity(
            "ACTION", action, action_feature_names,
            config.receipt_sha256),
        action_control_model_sha256=_model_identity(
            "ACTION_CONTROL", action_control, action_feature_names,
            config.receipt_sha256),
    )


def _threshold_grid(config: FactorizedPolicyConfig) -> tuple[ConfirmationPolicy, ...]:
    return tuple(ConfirmationPolicy(
        min_expected_pnl_usd=-1.0,
        min_pnl_q20_usd=-1.0,
        min_goal_probability=float(threshold),
        max_wall_probability=1.0,
        max_mae_q90_usd=1.0,
        min_alert_age_sec=float(config.watch_age_sec),
        max_alert_age_sec=300.0,
    ) for threshold in config.action_thresholds)


def _rank_maps(
    dataset: ConfirmationDataset, score: np.ndarray,
) -> Mapping[str, float]:
    return {str(series): float(value) for series, value in zip(
        dataset.series_id, np.asarray(score, np.float64))}


def _gated_predictions(
    dataset: ConfirmationDataset, *, watched_series: Iterable[str],
    rank_by_series: Mapping[str, float], action_score: np.ndarray,
    watch_snapshot_by_series: Mapping[str, int], model_hash: str,
) -> tuple[ConfirmationDataset, ConfirmationPredictions, np.ndarray]:
    action = np.asarray(action_score, np.float64)
    if (action.shape != (len(dataset.features),)
            or not np.all(np.isfinite(action))
            or np.any(action < 0.0) or np.any(action > 1.0)):
        raise ConfirmationRefusal("factorized action score differs")
    watched = set(map(str, watched_series))
    series = np.asarray(dataset.series_id, str)
    age = np.asarray(dataset.min_alert_age_sec, np.float64)
    timestamps = np.asarray(dataset.snapshot_ts_ns, np.int64)
    cutoff = np.asarray([
        watch_snapshot_by_series.get(str(value), np.iinfo(np.int64).max)
        for value in series], np.int64)
    mask = np.isin(series, tuple(watched)) & (timestamps >= cutoff) & (age <= 300.0)
    if not mask.any() or set(series[mask]) != watched:
        raise ConfirmationRefusal("factorized watched path is incomplete")
    subset = dataset.subset(mask)
    priority = np.asarray([
        rank_by_series[str(value)] for value in subset.series_id], np.float64)
    predictions = ConfirmationPredictions(
        opportunity_id=np.asarray(subset.opportunity_id, str).copy(),
        expected_pnl_usd=priority,
        pnl_q20_usd=np.zeros(len(priority), np.float64),
        goal_probability=action[mask],
        wall_probability=np.zeros(len(priority), np.float64),
        mae_q90_usd=np.zeros(len(priority), np.float64),
        model_hash=model_hash,
    )
    predictions.validate(subset.opportunity_id)
    return subset, predictions, mask


def _evaluation_summary(evaluation: EntryEvaluation) -> Mapping[str, object]:
    portfolio_days = len({row.trading_day for row in evaluation.asset_day_results})
    days_with_trades = sum(row.trades > 0 for row in evaluation.asset_day_results)
    core = {
        "asset_days": evaluation.asset_days,
        "portfolio_days": portfolio_days,
        "trades": evaluation.trades,
        "days_with_trades": days_with_trades,
        "zero_asset_days": evaluation.zero_asset_days,
        "total_pnl_usd": evaluation.total_pnl_usd,
        "usd_per_asset_day": evaluation.usd_per_asset_day,
        "usd_per_portfolio_day": evaluation.total_pnl_usd / portfolio_days,
        "usd_per_trade": evaluation.usd_per_trade,
        "max_drawdown_usd": evaluation.max_drawdown_usd,
        "drawdown_p90_usd": evaluation.drawdown_p90_usd,
        "worst_asset_day_usd": evaluation.worst_asset_day_usd,
        "by_asset": tuple(asdict(row) for row in evaluation.by_asset),
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


def _score_arm(
    dataset: ConfirmationDataset, predictions: ConfirmationPredictions, *,
    sessions: Sequence[SessionRef], policies: Sequence[ConfirmationPolicy],
) -> tuple[PolicyGridEvaluation, Mapping[str, object]]:
    grid = score_confirmation_policies(
        dataset, predictions, expected_sessions=sessions, policies=policies)
    core = {
        "status": grid.status,
        "selection_receipt_sha256": grid.receipt_sha256,
        "selected_policy": (
            None if grid.selected is None else asdict(grid.selected)),
        "selected_evaluation": (
            None if grid.selected_evaluation is None else
            _evaluation_summary(grid.selected_evaluation)),
        "scorecards": tuple(asdict(row) for row in grid.all_scorecards),
    }
    return grid, {**core, "receipt_sha256": C.object_sha256(core)}


def _replay_fixed_policy(
    dataset: ConfirmationDataset, predictions: ConfirmationPredictions,
    policy: ConfirmationPolicy, sessions: Sequence[SessionRef],
) -> Mapping[str, object]:
    try:
        evaluation = replay_confirmation(
            dataset, predictions, policy, expected_sessions=sessions)
    except ConfirmationRefusal as exc:
        core = {"status": "EMPTY_OR_REFUSED", "reason": str(exc)}
        return {**core, "receipt_sha256": C.object_sha256(core)}
    core = {"status": "MEASURED", "evaluation": _evaluation_summary(evaluation)}
    return {**core, "receipt_sha256": C.object_sha256(core)}


def _rank_diagnostic(
    dataset: ConfirmationDataset, ledger: OracleActionLedger,
    score: np.ndarray, *, config: FactorizedPolicyConfig,
) -> Mapping[str, object]:
    indices = np.arange(len(dataset.features), dtype=np.int64)
    checkpoints = np.full(len(indices), config.watch_age_sec, np.int16)
    return candidate_rank_diagnostic(
        dataset, ledger, indices=indices, checkpoints=checkpoints,
        score=np.asarray(score, np.float64), capacity=config.capacity,
        group_scope="ASSET_DAY_WATCH_AGE",
        target=np.asarray(ledger.q_optimal_usd, np.float64),
        target_scope=CURRENT_TARGET_SCOPE)


def run_factorized_policy(
    full: Mapping[str, ConfirmationDataset],
    full_ledgers: Mapping[str, OracleActionLedger],
    fixed: Mapping[str, ConfirmationDataset],
    fixed_ledgers: Mapping[str, OracleActionLedger],
    expected_sessions: Mapping[str, Sequence[SessionRef]], *,
    models: FactorizedModels,
    config: FactorizedPolicyConfig = FactorizedPolicyConfig(),
) -> Mapping[str, object]:
    """Select on PLATT and read one diagnostic THRESHOLD composition."""

    _validate_roles(full, full_ledgers, fixed, fixed_ledgers)
    if set(expected_sessions) != set(ROLES):
        raise ConfirmationRefusal("factorized expected-session roster differs")
    preflight = factorized_policy_preflight(
        full, full_ledgers, fixed, fixed_ledgers, expected_sessions,
        config=config)
    policies = _threshold_grid(config)
    rank_score = {role: np.asarray(models.rank.predict_proba(
        fixed[role].features)[:, 1], np.float64) for role in ROLES}
    rank_control_score = {role: np.asarray(models.rank_control.predict_proba(
        fixed[role].features)[:, 1], np.float64) for role in ROLES}
    action_score = {role: np.asarray(models.action.predict_proba(
        np.asarray(full[role].features[:, models.action_columns], np.float32)
    )[:, 1], np.float64) for role in ROLES}
    action_control_score = {role: np.asarray(models.action_control.predict_proba(
        np.asarray(full[role].features[:, models.action_columns], np.float32)
    )[:, 1], np.float64) for role in ROLES}

    gate: dict[str, dict[str, tuple[str, ...]]] = {}
    rank_maps: dict[str, dict[str, Mapping[str, float]]] = {}
    watch_snapshot = {}
    rank_diagnostics = {"LEARNED": {}, "SHUFFLED": {}}
    for role in ROLES:
        oracle_y = capacity_topk_labels(
            fixed[role], np.arange(len(fixed[role].features)),
            fixed_ledgers[role].q_optimal_usd, capacity=config.capacity)
        oracle_score = np.where(oracle_y == 1, 2.0, 0.0)
        gate[role] = {
            "LEARNED": select_top_capacity_series(
                fixed[role], rank_score[role], capacity=config.capacity),
            "SHUFFLED": select_top_capacity_series(
                fixed[role], rank_control_score[role], capacity=config.capacity),
            "ORACLE": tuple(sorted(np.asarray(
                fixed[role].series_id, str)[oracle_y == 1].tolist())),
        }
        rank_maps[role] = {
            "LEARNED": _rank_maps(fixed[role], rank_score[role]),
            "SHUFFLED": _rank_maps(fixed[role], rank_control_score[role]),
            "ORACLE": _rank_maps(fixed[role], oracle_score),
        }
        watch_snapshot[role] = {str(series): int(timestamp)
                                for series, timestamp in zip(
                                    fixed[role].series_id,
                                    fixed[role].snapshot_ts_ns)}
        rank_diagnostics["LEARNED"][role] = _rank_diagnostic(
            fixed[role], fixed_ledgers[role], rank_score[role], config=config)
        rank_diagnostics["SHUFFLED"][role] = _rank_diagnostic(
            fixed[role], fixed_ledgers[role], rank_control_score[role],
            config=config)

    def predictions(role: str, rank_kind: str, action_kind: str,
                    score: np.ndarray) -> tuple[ConfirmationDataset,
                                                ConfirmationPredictions,
                                                np.ndarray]:
        return _gated_predictions(
            full[role], watched_series=gate[role][rank_kind],
            rank_by_series=rank_maps[role][rank_kind], action_score=score,
            watch_snapshot_by_series=watch_snapshot[role],
            model_hash=C.object_sha256({
                "schema": SCHEMA, "rank": rank_kind,
                "action": action_kind, "role": role,
                "rank_model": models.rank_model_sha256,
                "action_model": models.action_model_sha256,
            }))

    arm_specs = {
        "LEARNED_RANK_LEARNED_TIMING": ("LEARNED", "LEARNED"),
        "SHUFFLED_RANK_LEARNED_TIMING": ("SHUFFLED", "LEARNED"),
        "LEARNED_RANK_SHUFFLED_TIMING": ("LEARNED", "SHUFFLED"),
    }
    arms: dict[str, object] = {}
    selected_policy: ConfirmationPolicy | None = None
    for name, (rank_kind, action_kind) in arm_specs.items():
        platt_action = (action_score["PLATT"] if action_kind == "LEARNED"
                        else action_control_score["PLATT"])
        platt_dataset, platt_prediction, _ = predictions(
            "PLATT", rank_kind, action_kind, platt_action)
        selection, platt_report = _score_arm(
            platt_dataset, platt_prediction,
            sessions=expected_sessions["PLATT"], policies=policies)
        threshold_report = None
        if selection.selected is not None:
            threshold_action = (
                action_score["THRESHOLD"] if action_kind == "LEARNED"
                else action_control_score["THRESHOLD"])
            threshold_dataset, threshold_prediction, _ = predictions(
                "THRESHOLD", rank_kind, action_kind, threshold_action)
            threshold_report = _replay_fixed_policy(
                threshold_dataset, threshold_prediction, selection.selected,
                expected_sessions["THRESHOLD"])
        core = {
            "rank_kind": rank_kind, "action_kind": action_kind,
            "platt_selection": platt_report,
            "threshold_diagnostic": threshold_report,
        }
        arms[name] = {**core, "receipt_sha256": C.object_sha256(core)}
        if name == "LEARNED_RANK_LEARNED_TIMING":
            selected_policy = selection.selected

    decomposition: dict[str, object] = {}
    if selected_policy is not None:
        for role in ("PLATT", "THRESHOLD"):
            oracle_action = np.asarray(
                full_ledgers[role].optimal_action == ENTER, np.float64)
            rows = {}
            for name, rank_kind, score in (
                ("LEARNED_RANK_LEARNED_TIMING", "LEARNED", action_score[role]),
                ("ORACLE_RANK_LEARNED_TIMING", "ORACLE", action_score[role]),
                ("LEARNED_RANK_ORACLE_TIMING", "LEARNED", oracle_action),
                ("ORACLE_RANK_ORACLE_TIMING", "ORACLE", oracle_action),
                ("LEARNED_RANK_IMMEDIATE_30S", "LEARNED",
                 np.ones(len(full[role].features), np.float64)),
            ):
                dataset, prediction, _ = predictions(
                    role, rank_kind,
                    "ORACLE" if "ORACLE_TIMING" in name else
                    ("IMMEDIATE" if "IMMEDIATE" in name else "LEARNED"),
                    score)
                policy = (ConfirmationPolicy(
                    -1.0, -1.0, .5, 1.0, max_mae_q90_usd=1.0,
                    min_alert_age_sec=float(config.watch_age_sec),
                    max_alert_age_sec=300.0)
                    if ("ORACLE_TIMING" in name or "IMMEDIATE" in name)
                    else selected_policy)
                rows[name] = _replay_fixed_policy(
                    dataset, prediction, policy, expected_sessions[role])
            decomposition[role] = rows

    implementation = {
        "factorized_policy": C.file_sha256(Path(__file__)),
        "policy": C.file_sha256(Path(__file__).with_name(
            "confirmation_policy.py")),
        "replay": C.file_sha256(Path(__file__).with_name("replay.py")),
        "capacity_stability": C.file_sha256(Path(__file__).with_name(
            "confirmation_capacity_stability.py")),
        "action_probe": C.file_sha256(Path(__file__).with_name(
            "confirmation_action_probe.py")),
    }
    core = {
        "schema": SCHEMA,
        "config": asdict(config),
        "config_sha256": config.receipt_sha256,
        "preflight": preflight,
        "catboost_version": catboost.__version__,
        "model_identity": {
            "rank": models.rank_model_sha256,
            "rank_control": models.rank_control_model_sha256,
            "action": models.action_model_sha256,
            "action_control": models.action_control_model_sha256,
        },
        "tree_counts": {
            "rank": int(models.rank.tree_count_),
            "rank_control": int(models.rank_control.tree_count_),
            "action": int(models.action.tree_count_),
            "action_control": int(models.action_control.tree_count_),
        },
        "feature_count": {
            "rank": len(fixed["FIT"].feature_names),
            "action": len(models.action_feature_names),
        },
        "inputs": {role: {
            "full_dataset_sha256": full[role].representation_sha256,
            "full_ledger_sha256": full_ledgers[role].representation_sha256,
            "fixed_dataset_sha256": fixed[role].representation_sha256,
            "fixed_ledger_sha256": fixed_ledgers[role].representation_sha256,
            "expected_sessions": len(expected_sessions[role]),
        } for role in ROLES},
        "rank_diagnostics": rank_diagnostics,
        "arms": arms,
        "decomposition": decomposition,
        "selection_role": "PLATT_CANONICAL_REPLAY_ONLY",
        "threshold_role": "DIAGNOSTIC_REUSED_E1R_BLOCK",
        "implementation_sha256": implementation,
        "economics_executed": True,
        "economics_scope": "E1R_SPARSE_TRAINING_GRID_DIAGNOSTIC",
        "exact_replay_ceiling_executed": False,
        "forward_open_count": 0,
        "h2_open_count": 0,
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


__all__ = [
    "DEFAULT_CLOCK_EXCLUSIONS", "FactorizedModels",
    "FactorizedPolicyConfig", "ROLES", "SCHEMA",
    "factorized_policy_preflight", "fit_factorized_models",
    "run_factorized_policy",
    "select_top_capacity_series",
]
