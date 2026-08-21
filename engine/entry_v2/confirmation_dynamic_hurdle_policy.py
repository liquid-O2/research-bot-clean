"""Conditional post-watch timing/value hurdles for Entry V2.

The deployable candidate ranker is frozen at the exact watch row.  Only paths
selected by that ranker are used to fit the two CatBoost action heads:

* timing: entering now is positive and within $50 of the candidate-local best;
* value: entering now is at least $600 and within $100 of that best.

The heads are deliberately separate.  A single broad ``$600+`` classifier
confounds candidate value, entry timing, and abstention.  Here PLATT selects a
two-dimensional stopping threshold and canonical replay prices its first
joint crossing.  THRESHOLD is read once only when the real PLATT book clears
the absolute trade/expectancy/drawdown/coverage laws.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from pathlib import Path
from typing import Final, Mapping, Sequence

import catboost
from catboost import CatBoostClassifier
import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

from . import common as C
from .confirmation import ConfirmationDataset, ConfirmationRefusal
from .confirmation_action_probe import _balanced_binary_weights
from .confirmation_capacity_corpus import _take_ledger
from .confirmation_capacity_probe import capacity_topk_labels
from .confirmation_diagnostics import (
    PolicyGridEvaluation, score_confirmation_policies,
)
from .confirmation_factorized_policy import select_top_capacity_series
from .confirmation_model import ConfirmationPredictions
from .confirmation_policy import (
    ConfirmationPolicy, _arrival, _nondominated_positive_indices, _solve_day,
    replay_confirmation,
)
from .replay import replay
from .confirmation_stopping import (
    OracleActionLedger, registered_oracle_label_family,
)
from .contracts import EntryEvaluation, SessionRef


SCHEMA: Final = "QRE2CONFDYNHURDLE1"
ROLES: Final = ("FIT", "PLATT", "THRESHOLD")
RANK_KINDS: Final = ("LEARNED", "SHUFFLED", "ORACLE")


@dataclass(frozen=True, slots=True)
class DynamicHurdleConfig:
    watch_age_sec: int = 30
    capacity: int = 4
    timing_label: str = "ENTER_POSITIVE_R50"
    value_label: str = "ENTER_P600_R100"
    iterations: int = 30
    depth: int = 5
    learning_rate: float = .07
    l2_leaf_reg: float = 12.0
    timing_seed: int = 202608201
    value_seed: int = 202608202
    control_seed: int = 20270820
    thread_count: int = 16
    timing_thresholds: tuple[float, ...] = (
        .10, .20, .30, .40, .45, .50, .55, .60, .70, .80, .90,
    )
    value_thresholds: tuple[float, ...] = (
        .10, .20, .30, .40, .45, .50, .55, .60, .70, .80, .90,
    )

    def __post_init__(self) -> None:
        timing = tuple(float(value) for value in self.timing_thresholds)
        value = tuple(float(item) for item in self.value_thresholds)
        if (not 0 <= self.watch_age_sec <= 300
                or not 1 <= self.capacity <= 12
                or not self.timing_label or not self.value_label
                or self.timing_label == self.value_label
                or not 5 <= self.iterations <= 500
                or not 3 <= self.depth <= 8
                or not 0 < self.learning_rate <= .3
                or not 0 < self.l2_leaf_reg <= 1_000
                or not 1 <= self.thread_count <= C.MAX_CPU_WORKERS
                or timing != tuple(sorted(set(timing)))
                or value != tuple(sorted(set(value)))
                or not timing or not value
                or timing[0] <= 0.0 or timing[-1] >= 1.0
                or value[0] <= 0.0 or value[-1] >= 1.0):
            raise ConfirmationRefusal(
                "dynamic-hurdle configuration is invalid")

    @property
    def receipt_sha256(self) -> str:
        return C.object_sha256({"schema": SCHEMA, **asdict(self)})


@dataclass(frozen=True, slots=True)
class DynamicHurdleModels:
    timing: CatBoostClassifier
    value: CatBoostClassifier
    timing_control: CatBoostClassifier
    value_control: CatBoostClassifier
    feature_names: tuple[str, ...]
    timing_model_sha256: str
    value_model_sha256: str
    timing_control_model_sha256: str
    value_control_model_sha256: str


def _validate_roles(
    conditional: Mapping[str, ConfirmationDataset],
    ledgers: Mapping[str, OracleActionLedger],
    fixed: Mapping[str, ConfirmationDataset],
    expected_sessions: Mapping[str, Sequence[SessionRef]],
) -> None:
    roster = set(ROLES)
    if (set(conditional) != roster or set(ledgers) != roster
            or set(fixed) != roster or set(expected_sessions) != roster):
        raise ConfirmationRefusal("dynamic-hurdle role roster differs")
    for role in ROLES:
        dataset = conditional[role]; ledger = ledgers[role]
        dataset.validate(); ledger.validate(); fixed[role].validate()
        if (ledger.source_representation_sha256
                != dataset.representation_sha256
                or not np.array_equal(dataset.opportunity_id,
                                      ledger.opportunity_id)
                or dataset.snapshot_mode != "TRAINING"
                or dataset.max_delay_sec != 300):
            raise ConfirmationRefusal(
                "dynamic-hurdle dataset/ledger identity differs")
        fixed_series = np.asarray(fixed[role].series_id, str)
        path_series = set(np.asarray(dataset.series_id, str).tolist())
        if (len(fixed_series) != len(set(fixed_series.tolist()))
                or not path_series <= set(fixed_series.tolist())):
            raise ConfirmationRefusal(
                "dynamic-hurdle fixed/path series roster differs")
        sessions = tuple(expected_sessions[role])
        if not sessions or len(sessions) != len(set(sessions)):
            raise ConfirmationRefusal(
                "dynamic-hurdle session denominator is malformed")
        session_pairs = {(row.asset, int(row.trading_day)) for row in sessions}
        path_pairs = set(zip(
            np.asarray(dataset.asset, str).tolist(),
            np.asarray(dataset.day, np.int64).tolist()))
        if not path_pairs <= session_pairs:
            raise ConfirmationRefusal(
                "dynamic-hurdle denominator omits a candidate session")
    if (conditional["FIT"].feature_names
            != conditional["PLATT"].feature_names
            or conditional["FIT"].feature_names
               != conditional["THRESHOLD"].feature_names
            or fixed["FIT"].feature_names != fixed["PLATT"].feature_names
            or fixed["FIT"].feature_names != fixed["THRESHOLD"].feature_names
            or int(np.max(conditional["FIT"].day))
               >= int(np.min(conditional["PLATT"].day))
            or int(np.max(conditional["PLATT"].day))
               >= int(np.min(conditional["THRESHOLD"].day))):
        raise ConfirmationRefusal(
            "dynamic-hurdle schema/chronology differs")


def _rank_rosters(
    fixed: Mapping[str, ConfirmationDataset],
    fixed_ledgers: Mapping[str, OracleActionLedger], *,
    rank_model: CatBoostClassifier,
    rank_control_model: CatBoostClassifier,
    capacity: int,
) -> tuple[
    Mapping[str, Mapping[str, tuple[str, ...]]],
    Mapping[str, Mapping[str, int]],
]:
    gates: dict[str, dict[str, tuple[str, ...]]] = {}
    watches: dict[str, dict[str, int]] = {}
    width = len(fixed["FIT"].feature_names)
    # CatBoost's loaded-model ``get_n_features_in`` returns zero in the
    # installed build even though ``feature_names_`` is fully populated.
    # Bundle manifests bind the semantic name tuple; this layer checks the
    # actual model input width exposed by the persisted model.
    if (len(rank_model.feature_names_) != width
            or len(rank_control_model.feature_names_) != width):
        raise ConfirmationRefusal(
            "dynamic-hurdle rank model schema differs")
    for role in ROLES:
        dataset = fixed[role]; ledger = fixed_ledgers[role]
        dataset.validate(); ledger.validate()
        if (ledger.source_representation_sha256
                != dataset.representation_sha256
                or not np.array_equal(dataset.opportunity_id,
                                      ledger.opportunity_id)):
            raise ConfirmationRefusal(
                "dynamic-hurdle fixed ledger identity differs")
        learned_score = np.asarray(
            rank_model.predict_proba(dataset.features)[:, 1], np.float64)
        control_score = np.asarray(
            rank_control_model.predict_proba(dataset.features)[:, 1],
            np.float64)
        oracle_y = capacity_topk_labels(
            dataset, np.arange(len(dataset.features), dtype=np.int64),
            ledger.q_optimal_usd, capacity=capacity)
        gates[role] = {
            "LEARNED": select_top_capacity_series(
                dataset, learned_score, capacity=capacity),
            "SHUFFLED": select_top_capacity_series(
                dataset, control_score, capacity=capacity),
            "ORACLE": tuple(sorted(np.asarray(
                dataset.series_id, str)[oracle_y == 1].tolist())),
        }
        watches[role] = {str(series): int(timestamp)
                         for series, timestamp in zip(
                             dataset.series_id, dataset.snapshot_ts_ns)}
    return gates, watches


def _gated_role(
    dataset: ConfirmationDataset, ledger: OracleActionLedger,
    series_roster: Sequence[str], watch_timestamp: Mapping[str, int],
) -> tuple[ConfirmationDataset, OracleActionLedger]:
    wanted = set(map(str, series_roster))
    series = np.asarray(dataset.series_id, str)
    timestamps = np.asarray(dataset.snapshot_ts_ns, np.int64)
    mask = np.isin(series, tuple(wanted))
    if not mask.any() or set(series[mask].tolist()) != wanted:
        raise ConfirmationRefusal("dynamic-hurdle gate path is incomplete")
    indices = np.flatnonzero(mask)
    for candidate in wanted:
        local = indices[series[indices] == candidate]
        earliest = int(local[np.argmin(timestamps[local])])
        if int(timestamps[earliest]) != int(watch_timestamp[candidate]):
            raise ConfirmationRefusal(
                "dynamic-hurdle path does not start at exact watch row")
    subset = dataset.subset(mask)
    return subset, _take_ledger(ledger, indices, subset)


def _label_support(
    dataset: ConfirmationDataset, ledger: OracleActionLedger,
    config: DynamicHurdleConfig,
) -> Mapping[str, object]:
    family = registered_oracle_label_family(ledger)
    support = {}
    for label in (config.timing_label, config.value_label):
        if label not in family:
            raise ConfirmationRefusal(
                f"dynamic-hurdle label is unknown: {label}")
        target = np.asarray(family[label], np.int8)
        _balanced_binary_weights(dataset, target)
        positive_series = len(set(np.asarray(dataset.series_id, str)[
            target == 1].tolist()))
        negative_series = len(set(np.asarray(dataset.series_id, str)[
            target == 0].tolist()))
        if not positive_series or not negative_series:
            raise ConfirmationRefusal(
                f"dynamic-hurdle label lacks series support: {label}")
        support[label] = {
            "positive_rows": int(np.sum(target == 1)),
            "negative_rows": int(np.sum(target == 0)),
            "positive_series": positive_series,
            "negative_series": negative_series,
        }
    return support


def _threshold_grid(
    config: DynamicHurdleConfig,
) -> tuple[ConfirmationPolicy, ...]:
    # ConfirmationPolicy's expected-PnL slot is intentionally an adapter here:
    # it carries a dimensionless value-head probability used for triggering and
    # replay priority.  No report may call it a dollar forecast.
    return tuple(ConfirmationPolicy(
        min_expected_pnl_usd=float(value_threshold),
        min_pnl_q20_usd=-1.0,
        min_goal_probability=float(timing_threshold),
        max_wall_probability=1.0,
        max_mae_q90_usd=1.0,
        min_alert_age_sec=float(config.watch_age_sec),
        max_alert_age_sec=300.0,
    ) for value_threshold in config.value_thresholds
      for timing_threshold in config.timing_thresholds)


def dynamic_hurdle_preflight(
    conditional: Mapping[str, ConfirmationDataset],
    ledgers: Mapping[str, OracleActionLedger],
    fixed: Mapping[str, ConfirmationDataset],
    fixed_ledgers: Mapping[str, OracleActionLedger],
    expected_sessions: Mapping[str, Sequence[SessionRef]], *,
    rank_model: CatBoostClassifier,
    rank_control_model: CatBoostClassifier,
    config: DynamicHurdleConfig = DynamicHurdleConfig(),
) -> Mapping[str, object]:
    """Execute every cheap identity/support boundary before action fitting."""

    _validate_roles(conditional, ledgers, fixed, expected_sessions)
    gates, watches = _rank_rosters(
        fixed, fixed_ledgers, rank_model=rank_model,
        rank_control_model=rank_control_model, capacity=config.capacity)
    support: dict[str, object] = {}
    control_support = {}
    for role in ROLES:
        gate_report = {}
        for kind in RANK_KINDS:
            dataset, ledger = _gated_role(
                conditional[role], ledgers[role], gates[role][kind],
                watches[role])
            label_support = _label_support(dataset, ledger, config)
            gate_report[kind] = {
                "rows": len(dataset.features),
                "series": len(set(np.asarray(dataset.series_id, str).tolist())),
                "label_support": label_support,
            }
            if role == "FIT" and kind == "LEARNED":
                family = registered_oracle_label_family(ledger)
                for offset, label in enumerate(
                        (config.timing_label, config.value_label), start=1):
                    target = np.asarray(family[label], np.int8)
                    destroyed = _series_position_shuffle(
                        dataset, target, seed=config.control_seed + offset)
                    _balanced_binary_weights(dataset, destroyed)
                    control_support[label] = {
                        "changed_rows": int(np.sum(target != destroyed)),
                        "negative_rows": int(np.sum(destroyed == 0)),
                        "positive_rows": int(np.sum(destroyed == 1)),
                    }
        support[role] = gate_report
    policies = _threshold_grid(config)
    core = {
        "schema": "QRE2CONFDYNHURDLEPREFLIGHT1",
        "config_sha256": config.receipt_sha256,
        "feature_count": len(conditional["FIT"].feature_names),
        "feature_names_sha256": C.object_sha256(
            conditional["FIT"].feature_names),
        "support": support,
        "fit_control_support": control_support,
        "policy_count": len(policies),
        "policy_receipts_unique": (
            len({row.receipt_sha256 for row in policies}) == len(policies)),
        "fit_gate": "DEPLOYABLE_LEARNED_RANK_ONLY",
        "oracle_gate_used_for_training": False,
        "threshold_role_used_for_training_or_selection": False,
        "all_required_training_weights_constructed": True,
        "canonical_replay_import_bound": True,
        "implementation_sha256": C.file_sha256(Path(__file__)),
        "models_executed": False,
        "economics_executed": False,
        "forward_open_count": 0,
        "h2_open_count": 0,
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


def _series_position_shuffle(
    dataset: ConfirmationDataset, target: np.ndarray, *, seed: int,
) -> np.ndarray:
    """Destroy ownership while preserving recipient paths and row positions."""

    values = np.asarray(target, np.int8)
    if values.shape != (len(dataset.features),) or len(np.unique(values)) != 2:
        raise ConfirmationRefusal("dynamic-hurdle control target differs")
    series = np.asarray(dataset.series_id, str)
    asset = np.asarray(dataset.asset, str)
    timestamps = np.asarray(dataset.snapshot_ts_ns, np.int64)
    rng = np.random.default_rng(seed)
    shuffled = values.copy()
    for name in sorted(set(asset.tolist())):
        recipients = np.asarray(sorted(set(series[asset == name].tolist())), str)
        if len(recipients) < 2:
            raise ConfirmationRefusal(
                "dynamic-hurdle control needs two series per asset")
        # A single cyclic shift can accidentally pair paths with identical
        # label sequences.  Search a fixed seeded derangement roster and keep
        # the one that changes the most recipient rows.  Recipients, features,
        # path lengths, and within-path position remain fixed.
        best_donors = None; best_changes = -1
        for _attempt in range(min(128, max(16, 4 * len(recipients)))):
            donors = recipients[rng.permutation(len(recipients))]
            if np.any(recipients == donors):
                continue
            changes = 0
            for recipient, donor in zip(recipients, donors):
                left = np.flatnonzero(series == recipient)
                right = np.flatnonzero(series == donor)
                left = left[np.argsort(timestamps[left])]
                right = right[np.argsort(timestamps[right])]
                positions = np.rint(np.linspace(
                    0, len(right) - 1, len(left))).astype(np.int64)
                changes += int(np.sum(values[left] != values[right[positions]]))
            if changes > best_changes:
                best_changes = changes; best_donors = donors.copy()
        if best_donors is None or best_changes <= 0:
            raise ConfirmationRefusal(
                f"dynamic-hurdle {name} control cannot destroy ownership")
        donors = best_donors
        for recipient, donor in zip(recipients, donors):
            left = np.flatnonzero(series == recipient)
            right = np.flatnonzero(series == donor)
            left = left[np.argsort(timestamps[left])]
            right = right[np.argsort(timestamps[right])]
            positions = np.rint(np.linspace(
                0, len(right) - 1, len(left))).astype(np.int64)
            shuffled[left] = values[right[positions]]
    if np.array_equal(values, shuffled) or len(np.unique(shuffled)) != 2:
        raise ConfirmationRefusal(
            "dynamic-hurdle control shuffle was ineffective")
    return shuffled


def _model_identity(
    name: str, model: CatBoostClassifier, feature_names: Sequence[str],
    config_sha256: str, label: str,
) -> str:
    return C.object_sha256({
        "schema": "QRE2CONFDYNHURDLEMODEL1",
        "name": name, "label": label,
        "config_sha256": config_sha256,
        "tree_count": int(model.tree_count_),
        "feature_names": tuple(feature_names),
        "parameters": model.get_all_params(),
    })


def fit_dynamic_hurdle_models(
    fit_dataset: ConfirmationDataset, fit_ledger: OracleActionLedger, *,
    config: DynamicHurdleConfig = DynamicHurdleConfig(),
) -> DynamicHurdleModels:
    """Fit two deployable action heads and independent target destructions."""

    fit_dataset.validate(); fit_ledger.validate()
    if (fit_ledger.source_representation_sha256
            != fit_dataset.representation_sha256
            or not np.array_equal(fit_dataset.opportunity_id,
                                  fit_ledger.opportunity_id)):
        raise ConfirmationRefusal(
            "dynamic-hurdle FIT identity differs")
    family = registered_oracle_label_family(fit_ledger)
    for label in (config.timing_label, config.value_label):
        if label not in family:
            raise ConfirmationRefusal(
                f"dynamic-hurdle label is unknown: {label}")
    timing_y = np.asarray(family[config.timing_label], np.int8)
    value_y = np.asarray(family[config.value_label], np.int8)
    timing_control_y = _series_position_shuffle(
        fit_dataset, timing_y, seed=config.control_seed + 1)
    value_control_y = _series_position_shuffle(
        fit_dataset, value_y, seed=config.control_seed + 2)
    common = dict(
        loss_function="Logloss", eval_metric="PRAUC:type=Classic",
        iterations=config.iterations, depth=config.depth,
        learning_rate=config.learning_rate, l2_leaf_reg=config.l2_leaf_reg,
        thread_count=config.thread_count, allow_writing_files=False,
        verbose=False)
    specs = (
        ("TIMING", config.timing_label, timing_y, config.timing_seed),
        ("VALUE", config.value_label, value_y, config.value_seed),
        ("TIMING_CONTROL", config.timing_label, timing_control_y,
         config.timing_seed + 10_000),
        ("VALUE_CONTROL", config.value_label, value_control_y,
         config.value_seed + 10_000),
    )
    models: dict[str, CatBoostClassifier] = {}
    identities: dict[str, str] = {}
    x = np.asarray(fit_dataset.features, np.float32)
    for name, label, target, seed in specs:
        weights = _balanced_binary_weights(fit_dataset, target)
        model = CatBoostClassifier(random_seed=seed, **common)
        model.fit(x, target, sample_weight=weights, verbose=False)
        models[name] = model
        identities[name] = _model_identity(
            name, model, fit_dataset.feature_names,
            config.receipt_sha256, label)
    return DynamicHurdleModels(
        timing=models["TIMING"], value=models["VALUE"],
        timing_control=models["TIMING_CONTROL"],
        value_control=models["VALUE_CONTROL"],
        feature_names=fit_dataset.feature_names,
        timing_model_sha256=identities["TIMING"],
        value_model_sha256=identities["VALUE"],
        timing_control_model_sha256=identities["TIMING_CONTROL"],
        value_control_model_sha256=identities["VALUE_CONTROL"],
    )


def _predictions(
    dataset: ConfirmationDataset, value_score: np.ndarray,
    timing_score: np.ndarray, *, model_hash: str,
) -> ConfirmationPredictions:
    value = np.asarray(value_score, np.float64)
    timing = np.asarray(timing_score, np.float64)
    if (value.shape != (len(dataset.features),)
            or timing.shape != value.shape
            or not np.all(np.isfinite(value))
            or not np.all(np.isfinite(timing))
            or np.any(value < 0.0) or np.any(value > 1.0)
            or np.any(timing < 0.0) or np.any(timing > 1.0)):
        raise ConfirmationRefusal(
            "dynamic-hurdle prediction score differs")
    result = ConfirmationPredictions(
        opportunity_id=np.asarray(dataset.opportunity_id, str).copy(),
        # Dimensionless value probability, used only as the adapter's trigger
        # and arrival-priority score.  It is never reported as expected USD.
        expected_pnl_usd=value,
        pnl_q20_usd=np.zeros(len(value), np.float64),
        goal_probability=timing,
        wall_probability=np.zeros(len(value), np.float64),
        mae_q90_usd=np.zeros(len(value), np.float64),
        model_hash=model_hash)
    result.validate(dataset.opportunity_id)
    return result


def _evaluation_summary(
    evaluation: EntryEvaluation, sessions: Sequence[SessionRef],
) -> Mapping[str, object]:
    portfolio_days = len({int(row.trading_day) for row in sessions})
    days_with_trades = sum(row.trades > 0
                           for row in evaluation.asset_day_results)
    per_day = evaluation.total_pnl_usd / portfolio_days
    core = {
        "asset_days": evaluation.asset_days,
        "portfolio_days": portfolio_days,
        "trades": evaluation.trades,
        "days_with_trades": days_with_trades,
        "zero_asset_days": evaluation.zero_asset_days,
        "total_pnl_usd": evaluation.total_pnl_usd,
        "usd_per_asset_day": evaluation.usd_per_asset_day,
        "usd_per_portfolio_day": per_day,
        "usd_per_trade": evaluation.usd_per_trade,
        "max_drawdown_usd": evaluation.max_drawdown_usd,
        "drawdown_p90_usd": evaluation.drawdown_p90_usd,
        "worst_asset_day_usd": evaluation.worst_asset_day_usd,
        "minimum_3000_met": per_day >= 3_000.0,
        "target_6000_met": per_day >= 6_000.0,
        "stretch_8000_met": per_day >= 8_000.0,
        "by_asset": tuple(asdict(row) for row in evaluation.by_asset),
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


def _score_selection(
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
            _evaluation_summary(grid.selected_evaluation, sessions)),
        "scorecards": tuple(asdict(row) for row in grid.all_scorecards),
    }
    return grid, {**core, "receipt_sha256": C.object_sha256(core)}


def _diagnostic_fallback(
    grid: PolicyGridEvaluation, *, eligible_asset_days: int,
) -> tuple[ConfirmationPolicy | None, str]:
    measured = [row for row in grid.all_scorecards
                if row.total_pnl_usd is not None]
    if not measured:
        return None, "NO_NONEMPTY_POLICY"
    minimum_days = math.ceil(eligible_asset_days / 3)
    shaped = [row for row in measured
              if row.trades >= C.MIN_TRADES
              and row.days_with_trades >= minimum_days]
    pool = shaped or measured
    best = min(pool, key=lambda row: (
        -float(row.total_pnl_usd),
        float(row.max_drawdown_usd), row.policy.receipt_sha256))
    return best.policy, (
        "BEST_TRADE_AND_COVERAGE_SHAPED_NONFEASIBLE"
        if shaped else "BEST_NONEMPTY_NONFEASIBLE")


def _replay_fixed(
    dataset: ConfirmationDataset, predictions: ConfirmationPredictions,
    policy: ConfirmationPolicy | None, sessions: Sequence[SessionRef],
) -> Mapping[str, object]:
    if policy is None:
        core = {"status": "NO_DIAGNOSTIC_POLICY"}
        return {**core, "receipt_sha256": C.object_sha256(core)}
    try:
        evaluation = replay_confirmation(
            dataset, predictions, policy, expected_sessions=sessions)
    except ConfirmationRefusal as exc:
        core = {"status": "EMPTY_OR_REFUSED", "reason": str(exc)}
        return {**core, "receipt_sha256": C.object_sha256(core)}
    core = {
        "status": "MEASURED",
        "evaluation": _evaluation_summary(evaluation, sessions),
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


def _sparse_schedule_ceiling(
    dataset: ConfirmationDataset, sessions: Sequence[SessionRef],
) -> Mapping[str, object]:
    """Hindsight upper bound on recorded sparse timestamps, never exact replay."""

    dataset.validate()
    if dataset.snapshot_mode != "TRAINING":
        raise ConfirmationRefusal(
            "sparse schedule ceiling requires the recorded training grid")
    retained = _nondominated_positive_indices(dataset)
    days = np.asarray(dataset.day, np.int64)
    selected: list[int] = []; objective_cents = 0
    for day in sorted(set(days[retained].tolist())):
        chosen, cents = _solve_day(dataset, retained[days[retained] == day])
        selected.extend(chosen.tolist()); objective_cents += cents
    if not selected:
        raise ConfirmationRefusal("sparse schedule ceiling is empty")
    arrivals = tuple(_arrival(
        dataset, index, model_hash="sparse-training-grid-ceiling",
        expected_pnl_usd=float(dataset.cert_close_usd[index]),
        pnl_q20_usd=float(dataset.cert_close_usd[index]),
        goal_probability=float(dataset.cert_close_usd[index] >= 600.0),
        wall_probability=float(dataset.wall_hit[index]),
        mae_q90_usd=float(dataset.mae_usd[index]),
    ) for index in selected)
    evaluation = replay(arrivals, expected_sessions=sessions)
    if abs(evaluation.total_pnl_usd - objective_cents / 100.0) > 1e-7:
        raise ConfirmationRefusal(
            "sparse schedule ceiling did not survive canonical replay")
    core = {
        "scope": "SPARSE_TRAINING_GRID_HINDSIGHT_UPPER_BOUND_NOT_EXACT",
        "dataset_sha256": dataset.representation_sha256,
        "positive_options": int(np.sum(dataset.cert_close_usd > 0.0)),
        "nondominated_options": len(retained),
        "selected_options": len(selected),
        "exact_replay_ceiling": False,
        "evaluation": _evaluation_summary(evaluation, sessions),
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


def _head_metric(
    dataset: ConfirmationDataset, target: np.ndarray, score: np.ndarray,
) -> Mapping[str, object]:
    y = np.asarray(target, np.int8); p = np.asarray(score, np.float64)
    weight = _balanced_binary_weights(dataset, y)
    brier = float(np.average((p - y) ** 2, weights=weight))
    core = {
        "rows": len(y),
        "series": len(set(np.asarray(dataset.series_id, str).tolist())),
        "positive_rows": int(np.sum(y == 1)),
        "roc_auc_series_class_balanced": float(
            roc_auc_score(y, p, sample_weight=weight)),
        "average_precision_series_class_balanced": float(
            average_precision_score(y, p, sample_weight=weight)),
        "brier_series_class_balanced": brier,
        "score_quantiles": tuple(float(value) for value in np.quantile(
            p, (0.0, .1, .25, .5, .75, .9, 1.0))),
        "selection_metric": False,
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


def run_dynamic_hurdle_policy(
    conditional: Mapping[str, ConfirmationDataset],
    ledgers: Mapping[str, OracleActionLedger],
    fixed: Mapping[str, ConfirmationDataset],
    fixed_ledgers: Mapping[str, OracleActionLedger],
    expected_sessions: Mapping[str, Sequence[SessionRef]], *,
    rank_model: CatBoostClassifier,
    rank_control_model: CatBoostClassifier,
    rank_model_sha256: str,
    rank_control_model_sha256: str,
    models: DynamicHurdleModels,
    config: DynamicHurdleConfig = DynamicHurdleConfig(),
) -> Mapping[str, object]:
    """Select on PLATT; run THRESHOLD economics only after a lawful pass."""

    preflight = dynamic_hurdle_preflight(
        conditional, ledgers, fixed, fixed_ledgers, expected_sessions,
        rank_model=rank_model, rank_control_model=rank_control_model,
        config=config)
    if (models.feature_names != conditional["FIT"].feature_names
            or any(len(model.feature_names_) != len(models.feature_names)
                   for model in (models.timing, models.value,
                                 models.timing_control,
                                 models.value_control))):
        raise ConfirmationRefusal(
            "dynamic-hurdle action model schema differs")
    gates, watches = _rank_rosters(
        fixed, fixed_ledgers, rank_model=rank_model,
        rank_control_model=rank_control_model, capacity=config.capacity)
    gated: dict[str, dict[str, tuple[
        ConfirmationDataset, OracleActionLedger]]] = {}
    for role in ROLES:
        gated[role] = {kind: _gated_role(
            conditional[role], ledgers[role], gates[role][kind], watches[role])
            for kind in RANK_KINDS}

    action_models = {
        "TIMING": (models.timing, models.timing_model_sha256),
        "VALUE": (models.value, models.value_model_sha256),
        "TIMING_CONTROL": (
            models.timing_control, models.timing_control_model_sha256),
        "VALUE_CONTROL": (
            models.value_control, models.value_control_model_sha256),
    }

    def score(role: str, rank_kind: str, head: str) -> np.ndarray:
        dataset = gated[role][rank_kind][0]
        model = action_models[head][0]
        return np.asarray(model.predict_proba(dataset.features)[:, 1],
                          np.float64)

    def prediction(
        role: str, rank_kind: str, timing_kind: str, value_kind: str,
    ) -> ConfirmationPredictions:
        dataset, ledger = gated[role][rank_kind]
        family = registered_oracle_label_family(ledger)
        timing = (np.asarray(family[config.timing_label], np.float64)
                  if timing_kind == "ORACLE" else
                  score(role, rank_kind, timing_kind))
        value = (np.asarray(family[config.value_label], np.float64)
                 if value_kind == "ORACLE" else
                 score(role, rank_kind, value_kind))
        return _predictions(
            dataset, value, timing,
            model_hash=C.object_sha256({
                "schema": SCHEMA, "role": role, "rank": rank_kind,
                "timing": timing_kind, "value": value_kind,
                "rank_model": (rank_control_model_sha256
                               if rank_kind == "SHUFFLED"
                               else rank_model_sha256),
                "timing_model": (None if timing_kind == "ORACLE"
                                  else action_models[timing_kind][1]),
                "value_model": (None if value_kind == "ORACLE"
                                 else action_models[value_kind][1]),
            }))

    head_diagnostics: dict[str, object] = {}
    for role in ROLES:
        dataset, ledger = gated[role]["LEARNED"]
        family = registered_oracle_label_family(ledger)
        head_diagnostics[role] = {
            "TIMING": _head_metric(
                dataset, family[config.timing_label],
                score(role, "LEARNED", "TIMING")),
            "TIMING_CONTROL": _head_metric(
                dataset, family[config.timing_label],
                score(role, "LEARNED", "TIMING_CONTROL")),
            "VALUE": _head_metric(
                dataset, family[config.value_label],
                score(role, "LEARNED", "VALUE")),
            "VALUE_CONTROL": _head_metric(
                dataset, family[config.value_label],
                score(role, "LEARNED", "VALUE_CONTROL")),
        }

    policies = _threshold_grid(config)
    platt_dataset = gated["PLATT"]["LEARNED"][0]
    real_platt = prediction("PLATT", "LEARNED", "TIMING", "VALUE")
    selection, selection_report = _score_selection(
        platt_dataset, real_platt,
        sessions=expected_sessions["PLATT"], policies=policies)
    frozen_policy = selection.selected
    selection_basis = "ABSOLUTE_LAWS"
    if frozen_policy is None:
        frozen_policy, selection_basis = _diagnostic_fallback(
            selection, eligible_asset_days=len(expected_sessions["PLATT"]))

    arm_specs = {
        "LEARNED_RANK_LEARNED_BOTH": ("LEARNED", "TIMING", "VALUE"),
        "LEARNED_RANK_SHUFFLED_TIMING": (
            "LEARNED", "TIMING_CONTROL", "VALUE"),
        "LEARNED_RANK_SHUFFLED_VALUE": (
            "LEARNED", "TIMING", "VALUE_CONTROL"),
        "LEARNED_RANK_SHUFFLED_BOTH": (
            "LEARNED", "TIMING_CONTROL", "VALUE_CONTROL"),
        "SHUFFLED_RANK_LEARNED_BOTH": ("SHUFFLED", "TIMING", "VALUE"),
    }

    def fixed_arms(role: str) -> Mapping[str, object]:
        rows = {}
        for name, (rank_kind, timing_kind, value_kind) in arm_specs.items():
            dataset = gated[role][rank_kind][0]
            rows[name] = _replay_fixed(
                dataset, prediction(role, rank_kind, timing_kind, value_kind),
                frozen_policy, expected_sessions[role])
        return rows

    def decomposition(role: str) -> Mapping[str, object]:
        rows = {}
        for name, rank_kind, timing_kind, value_kind in (
            ("LEARNED_RANK_LEARNED_BOTH", "LEARNED", "TIMING", "VALUE"),
            ("LEARNED_RANK_ORACLE_TIMING", "LEARNED", "ORACLE", "VALUE"),
            ("LEARNED_RANK_ORACLE_VALUE", "LEARNED", "TIMING", "ORACLE"),
            ("LEARNED_RANK_ORACLE_BOTH", "LEARNED", "ORACLE", "ORACLE"),
            ("ORACLE_RANK_LEARNED_BOTH", "ORACLE", "TIMING", "VALUE"),
            ("ORACLE_RANK_ORACLE_BOTH", "ORACLE", "ORACLE", "ORACLE"),
        ):
            dataset = gated[role][rank_kind][0]
            rows[name] = _replay_fixed(
                dataset, prediction(role, rank_kind, timing_kind, value_kind),
                frozen_policy, expected_sessions[role])
        return rows

    platt_arms = fixed_arms("PLATT")
    stage_decomposition = {"PLATT": decomposition("PLATT")}
    sparse_ceiling = {"PLATT": {
        kind: _sparse_schedule_ceiling(
            gated["PLATT"][kind][0], expected_sessions["PLATT"])
        for kind in RANK_KINDS
    }}
    threshold_arms = None
    if selection.selected is not None:
        threshold_arms = fixed_arms("THRESHOLD")
        stage_decomposition["THRESHOLD"] = decomposition("THRESHOLD")
        sparse_ceiling["THRESHOLD"] = {
            kind: _sparse_schedule_ceiling(
                gated["THRESHOLD"][kind][0], expected_sessions["THRESHOLD"])
            for kind in RANK_KINDS
        }

    implementation = {
        "dynamic_hurdle": C.file_sha256(Path(__file__)),
        "policy": C.file_sha256(Path(__file__).with_name(
            "confirmation_policy.py")),
        "replay": C.file_sha256(Path(__file__).with_name("replay.py")),
        "stopping_labels": C.file_sha256(Path(__file__).with_name(
            "confirmation_stopping.py")),
    }
    core = {
        "schema": SCHEMA,
        "config": asdict(config),
        "config_sha256": config.receipt_sha256,
        "preflight": preflight,
        "catboost_version": catboost.__version__,
        "model_identity": {
            "rank": rank_model_sha256,
            "rank_control": rank_control_model_sha256,
            "timing": models.timing_model_sha256,
            "value": models.value_model_sha256,
            "timing_control": models.timing_control_model_sha256,
            "value_control": models.value_control_model_sha256,
        },
        "tree_counts": {
            "timing": int(models.timing.tree_count_),
            "value": int(models.value.tree_count_),
            "timing_control": int(models.timing_control.tree_count_),
            "value_control": int(models.value_control.tree_count_),
        },
        "gate_series": {role: {kind: len(gates[role][kind])
                               for kind in RANK_KINDS}
                        for role in ROLES},
        "head_diagnostics_not_selection_metrics": head_diagnostics,
        "platt_selection": selection_report,
        "frozen_policy": (None if frozen_policy is None
                          else asdict(frozen_policy)),
        "frozen_policy_basis": selection_basis,
        "platt_fixed_policy_arms": platt_arms,
        "threshold_fixed_policy_arms": threshold_arms,
        "decomposition": stage_decomposition,
        "sparse_schedule_ceiling": sparse_ceiling,
        "value_score_units": "DIMENSIONLESS_CLASS_PROBABILITY_NOT_USD",
        "threshold_economics_executed": selection.selected is not None,
        "exact_replay_ceiling_executed": False,
        "implementation_sha256": implementation,
        "forward_open_count": 0,
        "h2_open_count": 0,
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


__all__ = [
    "DynamicHurdleConfig", "DynamicHurdleModels", "ROLES", "SCHEMA",
    "dynamic_hurdle_preflight", "fit_dynamic_hurdle_models",
    "run_dynamic_hurdle_policy",
]
