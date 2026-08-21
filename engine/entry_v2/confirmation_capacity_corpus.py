"""Durable fixed-watch corpus for cheap capacity-aligned tabular iteration.

The authoritative confirmation matrices are intentionally wide and contain
every causal watch row.  Re-loading them for each cheap objective diagnostic
is unnecessary and makes defect discovery expensive.  This module projects a
single fixed watch row per candidate, applies the registered FIT-only feature
law twice (full-path and fixed-watch), preserves the exact oracle values from
the original ledger, and publishes strict-reloadable reduced datasets.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Final, Mapping

import numpy as np

from . import common as C
from .confirmation import ConfirmationDataset, ConfirmationRefusal
from .confirmation_candidate_rank import (
    CURRENT_TARGET_SCOPE, CandidateRankConfig, _fit_only_feature_columns,
)
from .confirmation_capacity_probe import _fixed_watch_rows
from .confirmation_model import FitOnlyFeatureSelector
from .confirmation_stopping import OracleActionLedger


SCHEMA: Final = "QRE2CONFCAPACITYCORPUS1"
ROLES: Final = ("FIT", "PLATT", "THRESHOLD")


@dataclass(frozen=True, slots=True)
class CapacityCorpusConfig:
    watch_age_sec: int = 30
    capacity: int = 4
    feature_set: str = "MAX_W300"
    excluded_feature_names: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (not 0 <= self.watch_age_sec <= 300
                or not 1 <= self.capacity <= 12
                or not self.feature_set
                or len(set(self.excluded_feature_names))
                != len(self.excluded_feature_names)
                or any(not value for value in self.excluded_feature_names)):
            raise ConfirmationRefusal("capacity-corpus configuration is invalid")

    @property
    def receipt_sha256(self) -> str:
        return C.object_sha256({"schema": SCHEMA, **asdict(self)})


def _validate_roles(
    datasets: Mapping[str, ConfirmationDataset],
    ledgers: Mapping[str, OracleActionLedger],
) -> None:
    if set(datasets) != set(ROLES) or set(ledgers) != set(ROLES):
        raise ConfirmationRefusal("capacity-corpus role roster is incomplete")
    for role in ROLES:
        datasets[role].validate(); ledgers[role].validate()
        if (ledgers[role].source_representation_sha256
                != datasets[role].representation_sha256
                or not np.array_equal(
                    ledgers[role].opportunity_id,
                    datasets[role].opportunity_id)):
            raise ConfirmationRefusal("capacity-corpus role identity differs")
    if (datasets["FIT"].feature_names != datasets["PLATT"].feature_names
            or datasets["FIT"].feature_names
            != datasets["THRESHOLD"].feature_names
            or int(np.max(datasets["FIT"].day))
            >= int(np.min(datasets["PLATT"].day))
            or int(np.max(datasets["PLATT"].day))
            >= int(np.min(datasets["THRESHOLD"].day))):
        raise ConfirmationRefusal("capacity-corpus schemas/chronology differ")


def _take_dataset(
    dataset: ConfirmationDataset, source_indices: np.ndarray,
    columns: np.ndarray, feature_names: tuple[str, ...],
    *, selector_receipt_sha256: str,
) -> ConfirmationDataset:
    indices = np.asarray(source_indices, np.int64)
    selected_columns = np.asarray(columns, np.int64)
    if (not len(indices) or len(np.unique(indices)) != len(indices)
            or np.any(indices < 0) or np.any(indices >= len(dataset.features))
            or selected_columns.shape != (len(feature_names),)
            or len(np.unique(selected_columns)) != len(selected_columns)
            or np.any(selected_columns < 0)
            or np.any(selected_columns >= len(dataset.feature_names))):
        raise ConfirmationRefusal("capacity-corpus projection is malformed")
    vectors = {
        name: np.asarray(getattr(dataset, name))[indices]
        for name in (
            "opportunity_id", "series_id", "candidate_id", "asset", "day",
            "side", "phase", "snapshot_ts_ns", "phase_close_ts_ns",
            "event_cutoff", "entry_event_ordinal", "entry_availability_ts_ns",
            "entry_bid_px", "entry_ask_px", "entry_mid2", "entry_spread_usd",
            "frozen_cost_usd", "candidate_count", "min_alert_age_sec",
            "max_alert_age_sec", "cert_close_usd", "mfe_usd", "mae_usd",
            "wall_hit", "exit_ts_ns", "feature_receipt_sha256",
        )
    }
    result = ConfirmationDataset(
        feature_names=feature_names,
        features=np.asarray(
            dataset.features[np.ix_(indices, selected_columns)], np.float32),
        **vectors,
        max_delay_sec=dataset.max_delay_sec,
        snapshot_mode=dataset.snapshot_mode,
        config_sha256=dataset.config_sha256,
        source_receipts=(
            *dataset.source_receipts, selector_receipt_sha256),
    )
    result.validate()
    if len(set(np.asarray(result.series_id, str).tolist())) != len(indices):
        raise ConfirmationRefusal(
            "capacity-corpus does not have one row per series")
    return result


def _take_ledger(
    ledger: OracleActionLedger, source_indices: np.ndarray,
    dataset: ConfirmationDataset,
) -> OracleActionLedger:
    indices = np.asarray(source_indices, np.int64)
    one_dimensional = (
        "opportunity_id", "series_id", "snapshot_ts_ns", "q_enter_usd",
        "q_wait_usd", "q_pass_usd", "q_optimal_usd",
        "enter_advantage_usd", "enter_regret_usd", "optimal_action",
        "future_best_snapshot_ts_ns", "future_best_delay_sec",
        "action_run_observations", "action_run_horizon_sec",
        "enter_payoff_class", "optimal_payoff_class",
    )
    values = {name: np.asarray(getattr(ledger, name))[indices]
              for name in one_dimensional}
    result = OracleActionLedger(
        **values,
        payoff_thresholds_usd=ledger.payoff_thresholds_usd,
        enter_ge_threshold=np.asarray(ledger.enter_ge_threshold)[indices],
        optimal_ge_threshold=np.asarray(ledger.optimal_ge_threshold)[indices],
        source_representation_sha256=dataset.representation_sha256,
        scope=ledger.scope,
    )
    result.validate()
    if (not np.array_equal(result.opportunity_id, dataset.opportunity_id)
            or not np.array_equal(result.series_id, dataset.series_id)
            or not np.array_equal(
                result.snapshot_ts_ns, dataset.snapshot_ts_ns)):
        raise ConfirmationRefusal("capacity-corpus reduced ledger differs")
    return result


def prepare_capacity_corpora(
    datasets: Mapping[str, ConfirmationDataset],
    ledgers: Mapping[str, OracleActionLedger], *,
    config: CapacityCorpusConfig = CapacityCorpusConfig(),
) -> tuple[
    Mapping[str, ConfirmationDataset],
    Mapping[str, OracleActionLedger],
    Mapping[str, object],
]:
    """Project and bind all three roles without consulting PLATT labels."""

    _validate_roles(datasets, ledgers)
    rank_config = CandidateRankConfig(
        feature_set=config.feature_set,
        target_scope=CURRENT_TARGET_SCOPE,
        excluded_feature_names=config.excluded_feature_names,
        watch_ages_seconds=(0,), capacity=config.capacity)
    columns, names, path_selector = _fit_only_feature_columns(
        datasets["FIT"], rank_config)
    source_rows = {}
    path_reduced = {}
    for role in ROLES:
        indices, checkpoints = _fixed_watch_rows(
            datasets[role], watch_age_sec=config.watch_age_sec)
        order = np.argsort(indices, kind="stable")
        indices = np.asarray(indices[order], np.int64)
        checkpoints = np.asarray(checkpoints[order], np.int16)
        if np.any(checkpoints != config.watch_age_sec):
            raise ConfirmationRefusal("capacity-corpus watch age differs")
        source_rows[role] = indices
        path_reduced[role] = _take_dataset(
            datasets[role], indices, columns, names,
            selector_receipt_sha256=path_selector.receipt_sha256)

    fixed_selector = FitOnlyFeatureSelector.fit(path_reduced["FIT"])
    reduced_datasets = {
        role: fixed_selector.transform(path_reduced[role]) for role in ROLES}
    reduced_ledgers = {
        role: _take_ledger(
            ledgers[role], source_rows[role], reduced_datasets[role])
        for role in ROLES}
    implementation = {
        "capacity_corpus": C.file_sha256(Path(__file__)),
        "candidate_rank": C.file_sha256(
            Path(__file__).with_name("confirmation_candidate_rank.py")),
        "capacity_probe": C.file_sha256(
            Path(__file__).with_name("confirmation_capacity_probe.py")),
        "feature_selector": C.file_sha256(
            Path(__file__).with_name("confirmation_model.py")),
        "stopping": C.file_sha256(
            Path(__file__).with_name("confirmation_stopping.py")),
    }
    core = {
        "schema": SCHEMA,
        "config": asdict(config),
        "config_sha256": config.receipt_sha256,
        "target_scope": CURRENT_TARGET_SCOPE,
        "labels_used_for_feature_selection": False,
        "path_selector": {
            "receipt_sha256": path_selector.receipt_sha256,
            "input_feature_count": len(path_selector.input_feature_names),
            "selected_feature_count": len(path_selector.selected_indices),
            "constant_feature_count": len(path_selector.constant_feature_names),
            "duplicate_alias_count": len(path_selector.duplicate_aliases),
        },
        "fixed_watch_selector": {
            "receipt_sha256": fixed_selector.receipt_sha256,
            "input_feature_count": len(fixed_selector.input_feature_names),
            "selected_feature_count": len(fixed_selector.selected_indices),
            "constant_feature_count": len(fixed_selector.constant_feature_names),
            "duplicate_alias_count": len(fixed_selector.duplicate_aliases),
        },
        "roles": {
            role: {
                "rows": len(reduced_datasets[role].features),
                "series": len(set(np.asarray(
                    reduced_datasets[role].series_id, str).tolist())),
                "source_dataset_sha256": datasets[role].representation_sha256,
                "source_ledger_sha256": ledgers[role].representation_sha256,
                "dataset_sha256": reduced_datasets[role].representation_sha256,
                "ledger_sha256": reduced_ledgers[role].representation_sha256,
                "min_day": int(np.min(reduced_datasets[role].day)),
                "max_day": int(np.max(reduced_datasets[role].day)),
            } for role in ROLES
        },
        "implementation_sha256": implementation,
        "economics_executed": False,
        "forward_open_count": 0,
        "h2_open_count": 0,
    }
    return (reduced_datasets, reduced_ledgers,
            {**core, "receipt_sha256": C.object_sha256(core)})


__all__ = [
    "ROLES", "SCHEMA", "CapacityCorpusConfig", "prepare_capacity_corpora",
]
