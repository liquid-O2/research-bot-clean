"""Durable post-watch paths for cheap factorized action learning."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final, Mapping, Sequence

from catboost import CatBoostClassifier
import numpy as np

from . import common as C
from .confirmation import ConfirmationDataset, ConfirmationRefusal
from .confirmation_capacity_corpus import _take_ledger
from .confirmation_capacity_probe import capacity_topk_labels
from .confirmation_factorized_policy import select_top_capacity_series
from .confirmation_stopping import (
    OracleActionLedger, registered_oracle_label_family,
)
from .contracts import SessionRef


SCHEMA: Final = "QRE2CONFCONDITIONALCORPUS1"
ROLES: Final = ("FIT", "PLATT", "THRESHOLD")


@dataclass(frozen=True, slots=True)
class ConditionalCorpusConfig:
    watch_age_sec: int = 30
    capacity: int = 4
    extra_feature_names: tuple[str, ...] = ("max_alert_age_sec",)
    include_all_watchable_series: bool = False

    def __post_init__(self) -> None:
        if (not isinstance(self.include_all_watchable_series, bool)
                or not 0 <= self.watch_age_sec <= 300
                or not 1 <= self.capacity <= 12
                or len(set(self.extra_feature_names))
                   != len(self.extra_feature_names)
                or any(not value for value in self.extra_feature_names)):
            raise ConfirmationRefusal(
                "conditional-corpus configuration is invalid")

    @property
    def receipt_sha256(self) -> str:
        return C.object_sha256({"schema": SCHEMA, **asdict(self)})


def _project_dataset(
    source: ConfirmationDataset, indices: np.ndarray,
    columns: np.ndarray, names: tuple[str, ...], *, receipt: str,
) -> ConfirmationDataset:
    chosen = np.asarray(indices, np.int64)
    selected_columns = np.asarray(columns, np.int64)
    if (not len(chosen) or len(np.unique(chosen)) != len(chosen)
            or np.any(chosen < 0) or np.any(chosen >= len(source.features))
            or selected_columns.shape != (len(names),)
            or len(np.unique(selected_columns)) != len(selected_columns)):
        raise ConfirmationRefusal("conditional-corpus projection differs")
    vectors = {name: np.asarray(getattr(source, name))[chosen] for name in (
        "opportunity_id", "series_id", "candidate_id", "asset", "day",
        "side", "phase", "snapshot_ts_ns", "phase_close_ts_ns",
        "event_cutoff", "entry_event_ordinal", "entry_availability_ts_ns",
        "entry_bid_px", "entry_ask_px", "entry_mid2", "entry_spread_usd",
        "frozen_cost_usd", "candidate_count", "min_alert_age_sec",
        "max_alert_age_sec", "cert_close_usd", "mfe_usd", "mae_usd",
        "wall_hit", "exit_ts_ns", "feature_receipt_sha256",
    )}
    result = ConfirmationDataset(
        feature_names=names,
        features=np.asarray(
            source.features[np.ix_(chosen, selected_columns)], np.float32),
        **vectors, max_delay_sec=source.max_delay_sec,
        snapshot_mode=source.snapshot_mode,
        config_sha256=source.config_sha256,
        source_receipts=source.source_receipts + (receipt,))
    result.validate()
    return result


def prepare_conditional_role(
    role: str, full: ConfirmationDataset, full_ledger: OracleActionLedger,
    fixed: ConfirmationDataset, fixed_ledger: OracleActionLedger, *,
    rank_model: CatBoostClassifier,
    rank_control_model: CatBoostClassifier,
    expected_sessions: Sequence[SessionRef],
    config: ConditionalCorpusConfig = ConditionalCorpusConfig(),
) -> tuple[ConfirmationDataset, OracleActionLedger, Mapping[str, object]]:
    """Project learned/oracle/control watch paths from one authoritative role."""

    name = str(role).upper()
    if name not in ROLES:
        raise ConfirmationRefusal("conditional-corpus role is unknown")
    full.validate(); full_ledger.validate(); fixed.validate(); fixed_ledger.validate()
    if (full_ledger.source_representation_sha256
            != full.representation_sha256
            or fixed_ledger.source_representation_sha256
            != fixed.representation_sha256
            or not np.array_equal(full.opportunity_id, full_ledger.opportunity_id)
            or not np.array_equal(fixed.opportunity_id, fixed_ledger.opportunity_id)):
        raise ConfirmationRefusal("conditional-corpus role identity differs")
    fixed_series = np.asarray(fixed.series_id, str)
    if (len(fixed_series) != len(set(fixed_series.tolist()))
            or not set(fixed_series.tolist())
               <= set(np.asarray(full.series_id, str).tolist())):
        raise ConfirmationRefusal("conditional-corpus series roster differs")
    rank_score = np.asarray(
        rank_model.predict_proba(fixed.features)[:, 1], np.float64)
    control_score = np.asarray(
        rank_control_model.predict_proba(fixed.features)[:, 1], np.float64)
    learned = set(select_top_capacity_series(
        fixed, rank_score, capacity=config.capacity))
    control = set(select_top_capacity_series(
        fixed, control_score, capacity=config.capacity))
    oracle_y = capacity_topk_labels(
        fixed, np.arange(len(fixed.features), dtype=np.int64),
        fixed_ledger.q_optimal_usd, capacity=config.capacity)
    oracle = set(fixed_series[oracle_y == 1].tolist())
    retained = (set(fixed_series.tolist())
                if config.include_all_watchable_series
                else learned | oracle | control)
    if not retained:
        raise ConfirmationRefusal("conditional-corpus gate union is empty")

    watch_ts = {str(series): int(timestamp) for series, timestamp in zip(
        fixed_series, fixed.snapshot_ts_ns)}
    watch_id = {str(series): str(opportunity) for series, opportunity in zip(
        fixed_series, fixed.opportunity_id)}
    series = np.asarray(full.series_id, str)
    timestamps = np.asarray(full.snapshot_ts_ns, np.int64)
    ages = np.asarray(full.min_alert_age_sec, np.float64)
    cutoff = np.asarray([
        watch_ts.get(str(value), np.iinfo(np.int64).max) for value in series],
        np.int64)
    mask = np.isin(series, tuple(retained)) & (timestamps >= cutoff) & (ages <= 300.0)
    indices = np.flatnonzero(mask)
    if set(series[indices].tolist()) != retained:
        raise ConfirmationRefusal("conditional-corpus retained path is incomplete")
    for candidate in retained:
        local = indices[series[indices] == candidate]
        earliest = int(local[np.argmin(timestamps[local])])
        if (int(timestamps[earliest]) != watch_ts[candidate]
                or str(full.opportunity_id[earliest]) != watch_id[candidate]):
            raise ConfirmationRefusal(
                "conditional-corpus path does not start at fixed watch")

    desired = list(fixed.feature_names)
    for feature in config.extra_feature_names:
        if feature not in full.feature_names:
            raise ConfirmationRefusal(
                f"conditional extra feature is absent: {feature}")
        if feature not in desired:
            desired.append(feature)
    position = {feature: index for index, feature in enumerate(full.feature_names)}
    absent = set(desired) - set(position)
    if absent:
        raise ConfirmationRefusal(
            f"conditional fixed feature is absent: {sorted(absent)}")
    columns = np.asarray([position[feature] for feature in desired], np.int64)
    feature_names = tuple(desired)
    selection_receipt = C.object_sha256({
        "schema": SCHEMA, "role": name,
        "config_sha256": config.receipt_sha256,
        "full_dataset_sha256": full.representation_sha256,
        "fixed_dataset_sha256": fixed.representation_sha256,
        "learned_series": tuple(sorted(learned)),
        "oracle_series": tuple(sorted(oracle)),
        "control_series": tuple(sorted(control)),
        "retained_series": tuple(sorted(retained)),
        "feature_names": feature_names,
    })
    dataset = _project_dataset(
        full, indices, columns, feature_names, receipt=selection_receipt)
    ledger = _take_ledger(full_ledger, indices, dataset)
    labels = registered_oracle_label_family(ledger)
    sessions = tuple(expected_sessions)
    if not sessions or len(sessions) != len(set(sessions)):
        raise ConfirmationRefusal(
            "conditional-corpus expected sessions are malformed")
    core = {
        "schema": SCHEMA, "role": name,
        "config_sha256": config.receipt_sha256,
        "source_dataset_sha256": full.representation_sha256,
        "source_ledger_sha256": full_ledger.representation_sha256,
        "fixed_dataset_sha256": fixed.representation_sha256,
        "fixed_ledger_sha256": fixed_ledger.representation_sha256,
        "selection_receipt_sha256": selection_receipt,
        "rows": len(dataset.features),
        "features": len(feature_names),
        "learned_series": len(learned),
        "oracle_series": len(oracle),
        "control_series": len(control),
        "retained_series": len(retained),
        "retention_mode": ("ALL_WATCHABLE_SERIES"
                           if config.include_all_watchable_series
                           else "LEARNED_ORACLE_CONTROL_UNION"),
        "learned_oracle_overlap": len(learned & oracle),
        "learned_control_overlap": len(learned & control),
        "expected_sessions": tuple(asdict_session(row) for row in sessions),
        "label_support": {label: {
            "negative": int(np.sum(value == 0)),
            "positive": int(np.sum(value == 1)),
        } for label, value in labels.items()},
        "dataset_sha256": dataset.representation_sha256,
        "ledger_sha256": ledger.representation_sha256,
        "forward_open_count": 0,
        "h2_open_count": 0,
    }
    return dataset, ledger, {**core, "receipt_sha256": C.object_sha256(core)}


def asdict_session(session: SessionRef) -> Mapping[str, object]:
    return {
        "asset": session.asset, "trading_day": int(session.trading_day),
        "session_id": session.session_id,
    }


__all__ = [
    "ConditionalCorpusConfig", "ROLES", "SCHEMA",
    "asdict_session", "prepare_conditional_role",
]
