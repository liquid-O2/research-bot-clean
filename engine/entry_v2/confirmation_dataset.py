"""Persisted confirmation datasets and dataset combination."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import os
from pathlib import Path
from typing import Sequence

import numpy as np

from . import common as C
from .confirmation_types import ConfirmationRefusal, re_full_sha


@dataclass(frozen=True, slots=True)
class ConfirmationDataset:
    feature_names: tuple[str, ...]
    features: np.ndarray
    opportunity_id: np.ndarray
    series_id: np.ndarray
    candidate_id: np.ndarray
    asset: np.ndarray
    day: np.ndarray
    side: np.ndarray
    phase: np.ndarray
    snapshot_ts_ns: np.ndarray
    phase_close_ts_ns: np.ndarray
    event_cutoff: np.ndarray
    entry_event_ordinal: np.ndarray
    entry_availability_ts_ns: np.ndarray
    entry_bid_px: np.ndarray
    entry_ask_px: np.ndarray
    entry_mid2: np.ndarray
    entry_spread_usd: np.ndarray
    frozen_cost_usd: np.ndarray
    candidate_count: np.ndarray
    min_alert_age_sec: np.ndarray
    max_alert_age_sec: np.ndarray
    cert_close_usd: np.ndarray
    mfe_usd: np.ndarray
    mae_usd: np.ndarray
    wall_hit: np.ndarray
    exit_ts_ns: np.ndarray
    feature_receipt_sha256: np.ndarray
    max_delay_sec: int
    snapshot_mode: str
    config_sha256: str
    source_receipts: tuple[str, ...]

    def validate(self) -> None:
        x = np.asarray(self.features)
        n = len(x)
        vectors = (
            self.opportunity_id, self.series_id, self.candidate_id, self.asset,
            self.day, self.side, self.phase, self.snapshot_ts_ns,
            self.phase_close_ts_ns, self.event_cutoff, self.entry_event_ordinal,
            self.entry_availability_ts_ns,
            self.entry_bid_px, self.entry_ask_px, self.entry_mid2,
            self.entry_spread_usd, self.frozen_cost_usd, self.candidate_count,
            self.min_alert_age_sec, self.max_alert_age_sec, self.cert_close_usd,
            self.mfe_usd, self.mae_usd, self.wall_hit, self.exit_ts_ns,
            self.feature_receipt_sha256,
        )
        if (x.ndim != 2 or x.shape[1] != len(self.feature_names)
                or any(np.asarray(value).shape != (n,) for value in vectors)
                or len(set(self.feature_names)) != len(self.feature_names)
                or len(set(np.asarray(self.opportunity_id, str).tolist())) != n
                or any(not value for value in np.asarray(self.candidate_id, str))
                or not np.all(np.isfinite(x))
                or not np.all(np.isfinite(self.cert_close_usd))
                or not np.all(np.isfinite(self.mfe_usd))
                or not np.all(np.isfinite(self.mae_usd))
                or not np.all(np.isin(self.side, (-1, 1)))
                or not np.all(np.isin(self.asset, C.ASSETS))
                or not np.all(np.asarray(self.candidate_count) == 1)
                or not np.all(np.asarray(self.event_cutoff) > 0)
                or not np.all(np.asarray(self.entry_event_ordinal)
                              < np.asarray(self.event_cutoff))
                or not np.all(np.asarray(self.entry_availability_ts_ns)
                              < np.asarray(self.snapshot_ts_ns))
                or not np.all(np.asarray(self.exit_ts_ns)
                              >= np.asarray(self.snapshot_ts_ns))
                or not np.all(np.asarray(self.entry_bid_px) > 0)
                or not np.all(np.asarray(self.entry_ask_px)
                              > np.asarray(self.entry_bid_px))
                or not np.array_equal(
                    np.asarray(self.entry_mid2),
                    np.asarray(self.entry_bid_px) + np.asarray(self.entry_ask_px))
                or not np.all(np.asarray(self.entry_spread_usd) >= 0)
                or not np.all(np.asarray(self.frozen_cost_usd) >= 0)
                or self.max_delay_sec not in (300, 600)
                or self.snapshot_mode not in {"TRAINING", "REPLAY"}
                or not re_full_sha(self.config_sha256)
                or any(not re_full_sha(value) for value in self.source_receipts)):
            raise ConfirmationRefusal("confirmation dataset schema is invalid")
        series_candidates: dict[str, set[str]] = {}
        for series, candidate in zip(
                np.asarray(self.series_id, str), np.asarray(self.candidate_id, str)):
            series_candidates.setdefault(series, set()).add(candidate)
        if any(len(values) != 1 for values in series_candidates.values()):
            raise ConfirmationRefusal("one confirmation series maps to multiple candidates")

    @property
    def representation_sha256(self) -> str:
        self.validate()
        digest = hashlib.sha256()
        digest.update("\n".join(self.feature_names).encode())
        digest.update(str(self.max_delay_sec).encode())
        digest.update(self.snapshot_mode.encode())
        digest.update(self.config_sha256.encode())
        digest.update("\n".join(self.source_receipts).encode())
        for value in (
            np.asarray(self.features, np.float32),
            np.asarray(self.opportunity_id, str), np.asarray(self.series_id, str),
            np.asarray(self.candidate_id, str), np.asarray(self.asset, str),
            np.asarray(self.day, np.int64), np.asarray(self.side, np.int8),
            np.asarray(self.phase, str), np.asarray(self.snapshot_ts_ns, np.int64),
            np.asarray(self.phase_close_ts_ns, np.int64),
            np.asarray(self.event_cutoff, np.int64),
            np.asarray(self.entry_event_ordinal, np.int64),
            np.asarray(self.entry_availability_ts_ns, np.int64),
            np.asarray(self.entry_bid_px, np.int64),
            np.asarray(self.entry_ask_px, np.int64),
            np.asarray(self.entry_mid2, np.int64),
            np.asarray(self.entry_spread_usd, np.float64),
            np.asarray(self.frozen_cost_usd, np.float64),
            np.asarray(self.candidate_count, np.int16),
            np.asarray(self.min_alert_age_sec, np.float32),
            np.asarray(self.max_alert_age_sec, np.float32),
            np.asarray(self.cert_close_usd, np.float64),
            np.asarray(self.mfe_usd, np.float64),
            np.asarray(self.mae_usd, np.float64),
            np.asarray(self.wall_hit, np.bool_), np.asarray(self.exit_ts_ns, np.int64),
            np.asarray(self.feature_receipt_sha256, str),
        ):
            array = np.ascontiguousarray(value)
            digest.update(str(array.dtype).encode())
            digest.update(repr(array.shape).encode())
            digest.update(array.tobytes())
        return digest.hexdigest()

    def subset(self, mask: np.ndarray) -> "ConfirmationDataset":
        selected = np.asarray(mask, bool)
        if selected.shape != (len(self.features),) or not selected.any():
            raise ConfirmationRefusal("confirmation subset is empty or malformed")
        names = {
            name: np.asarray(getattr(self, name))[selected]
            for name in (
                "features", "opportunity_id", "series_id", "candidate_id",
                "asset", "day", "side", "phase", "snapshot_ts_ns",
                "phase_close_ts_ns", "event_cutoff", "entry_event_ordinal",
                "entry_availability_ts_ns",
                "entry_bid_px", "entry_ask_px", "entry_mid2",
                "entry_spread_usd", "frozen_cost_usd", "candidate_count",
                "min_alert_age_sec", "max_alert_age_sec", "cert_close_usd",
                "mfe_usd", "mae_usd", "wall_hit", "exit_ts_ns",
                "feature_receipt_sha256",
            )
        }
        result = ConfirmationDataset(
            self.feature_names, **names, max_delay_sec=self.max_delay_sec,
            snapshot_mode=self.snapshot_mode, config_sha256=self.config_sha256,
            source_receipts=self.source_receipts)
        result.validate()
        return result
    def select_features(self, mask: np.ndarray) -> "ConfirmationDataset":
        selected = np.asarray(mask, bool)
        if (selected.shape != (len(self.feature_names),) or not selected.any()
                or selected.all()):
            raise ConfirmationRefusal("feature ablation mask is empty, full, or malformed")
        result = replace(
            self,
            feature_names=tuple(np.asarray(self.feature_names, str)[selected].tolist()),
            features=np.asarray(self.features)[:, selected],
        )
        result.validate()
        return result

    def save(self, path: os.PathLike[str] | str) -> str:
        self.validate()
        target = C.assert_workspace_output(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.suffix != ".npz":
            raise ConfirmationRefusal("confirmation dataset path must end in .npz")
        tmp = target.with_name(target.name + f".tmp.{os.getpid()}")
        with tmp.open("xb") as handle:
            np.savez_compressed(
                handle, feature_names=np.asarray(self.feature_names, str),
                features=np.asarray(self.features, np.float32),
                opportunity_id=np.asarray(self.opportunity_id, str),
                series_id=np.asarray(self.series_id, str),
                candidate_id=np.asarray(self.candidate_id, str),
                asset=np.asarray(self.asset, str),
                day=np.asarray(self.day, np.int64), side=np.asarray(self.side, np.int8),
                phase=np.asarray(self.phase, str),
                snapshot_ts_ns=np.asarray(self.snapshot_ts_ns, np.int64),
                phase_close_ts_ns=np.asarray(self.phase_close_ts_ns, np.int64),
                event_cutoff=np.asarray(self.event_cutoff, np.int64),
                entry_event_ordinal=np.asarray(self.entry_event_ordinal, np.int64),
                entry_availability_ts_ns=np.asarray(
                    self.entry_availability_ts_ns, np.int64),
                entry_bid_px=np.asarray(self.entry_bid_px, np.int64),
                entry_ask_px=np.asarray(self.entry_ask_px, np.int64),
                entry_mid2=np.asarray(self.entry_mid2, np.int64),
                entry_spread_usd=np.asarray(self.entry_spread_usd, np.float64),
                frozen_cost_usd=np.asarray(self.frozen_cost_usd, np.float64),
                candidate_count=np.asarray(self.candidate_count, np.int16),
                min_alert_age_sec=np.asarray(self.min_alert_age_sec, np.float32),
                max_alert_age_sec=np.asarray(self.max_alert_age_sec, np.float32),
                cert_close_usd=np.asarray(self.cert_close_usd, np.float64),
                mfe_usd=np.asarray(self.mfe_usd, np.float64),
                mae_usd=np.asarray(self.mae_usd, np.float64),
                wall_hit=np.asarray(self.wall_hit, np.bool_),
                exit_ts_ns=np.asarray(self.exit_ts_ns, np.int64),
                feature_receipt_sha256=np.asarray(self.feature_receipt_sha256, str),
                max_delay_sec=np.asarray([self.max_delay_sec], np.int16),
                snapshot_mode=np.asarray([self.snapshot_mode], str),
                config_sha256=np.asarray([self.config_sha256], str),
                source_receipts=np.asarray(self.source_receipts, str),
                representation_sha256=np.asarray([self.representation_sha256], str),
            )
            handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, target)
        return C.file_sha256(target)

    @classmethod
    def load(cls, path: os.PathLike[str] | str) -> "ConfirmationDataset":
        source = Path(path)
        C.guard_payload(source)
        try:
            with np.load(source, allow_pickle=False) as z:
                result = cls(
                    feature_names=tuple(z["feature_names"].astype(str).tolist()),
                    features=z["features"], opportunity_id=z["opportunity_id"],
                    series_id=z["series_id"], candidate_id=z["candidate_id"],
                    asset=z["asset"], day=z["day"], side=z["side"],
                    phase=z["phase"], snapshot_ts_ns=z["snapshot_ts_ns"],
                    phase_close_ts_ns=z["phase_close_ts_ns"],
                    event_cutoff=z["event_cutoff"],
                    entry_event_ordinal=z["entry_event_ordinal"],
                    entry_availability_ts_ns=z["entry_availability_ts_ns"],
                    entry_bid_px=z["entry_bid_px"], entry_ask_px=z["entry_ask_px"],
                    entry_mid2=z["entry_mid2"],
                    entry_spread_usd=z["entry_spread_usd"],
                    frozen_cost_usd=z["frozen_cost_usd"],
                    candidate_count=z["candidate_count"],
                    min_alert_age_sec=z["min_alert_age_sec"],
                    max_alert_age_sec=z["max_alert_age_sec"],
                    cert_close_usd=z["cert_close_usd"], mfe_usd=z["mfe_usd"],
                    mae_usd=z["mae_usd"], wall_hit=z["wall_hit"],
                    exit_ts_ns=z["exit_ts_ns"],
                    feature_receipt_sha256=z["feature_receipt_sha256"],
                    max_delay_sec=int(z["max_delay_sec"][0]),
                    snapshot_mode=str(z["snapshot_mode"][0]),
                    config_sha256=str(z["config_sha256"][0]),
                    source_receipts=tuple(z["source_receipts"].astype(str).tolist()))
                expected = str(z["representation_sha256"][0])
        except (OSError, ValueError, KeyError) as exc:
            raise ConfirmationRefusal("cannot strict-load confirmation dataset") from exc
        result.validate()
        if result.representation_sha256 != expected:
            raise ConfirmationRefusal("confirmation dataset representation hash differs")
        return result


@dataclass(frozen=True, slots=True)
class ConfirmationOpportunitySet:
    """Lightweight every-second outcome universe for the exact ceiling."""

    opportunity_id: np.ndarray
    series_id: np.ndarray
    candidate_id: np.ndarray
    asset: np.ndarray
    day: np.ndarray
    side: np.ndarray
    phase: np.ndarray
    snapshot_ts_ns: np.ndarray
    phase_close_ts_ns: np.ndarray
    event_cutoff: np.ndarray
    entry_event_ordinal: np.ndarray
    entry_availability_ts_ns: np.ndarray
    cert_close_usd: np.ndarray
    mfe_usd: np.ndarray
    mae_usd: np.ndarray
    wall_hit: np.ndarray
    exit_ts_ns: np.ndarray
    feature_receipt_sha256: np.ndarray
    max_delay_sec: int
    snapshot_mode: str
    config_sha256: str
    source_receipts: tuple[str, ...]

    def validate(self) -> None:
        n = len(self.opportunity_id)
        vectors = tuple(getattr(self, name) for name in (
            "series_id", "candidate_id", "asset", "day", "side", "phase",
            "snapshot_ts_ns", "phase_close_ts_ns", "event_cutoff",
            "entry_event_ordinal", "entry_availability_ts_ns", "cert_close_usd",
            "mfe_usd", "mae_usd", "wall_hit", "exit_ts_ns",
            "feature_receipt_sha256"))
        if (n == 0 or any(np.asarray(value).shape != (n,) for value in vectors)
                or len(set(np.asarray(self.opportunity_id, str).tolist())) != n
                or not np.all(np.isin(self.asset, C.ASSETS))
                or not np.all(np.isin(self.side, (-1, 1)))
                or not np.all(np.asarray(self.event_cutoff) > 0)
                or not np.all(np.asarray(self.entry_event_ordinal)
                              < np.asarray(self.event_cutoff))
                or not np.all(np.asarray(self.entry_availability_ts_ns)
                              < np.asarray(self.snapshot_ts_ns))
                or not np.all(np.asarray(self.exit_ts_ns)
                              >= np.asarray(self.snapshot_ts_ns))
                or not np.all(np.isfinite(self.cert_close_usd))
                or not np.all(np.isfinite(self.mfe_usd))
                or not np.all(np.isfinite(self.mae_usd))
                or self.max_delay_sec not in (300, 600)
                or self.snapshot_mode != "REPLAY"
                or not re_full_sha(self.config_sha256)
                or any(not re_full_sha(value) for value in self.source_receipts)):
            raise ConfirmationRefusal("confirmation opportunity universe is invalid")
        mapping: dict[str, set[str]] = {}
        for series, candidate in zip(self.series_id, self.candidate_id):
            mapping.setdefault(str(series), set()).add(str(candidate))
        if any(len(value) != 1 for value in mapping.values()):
            raise ConfirmationRefusal("opportunity series maps to multiple candidates")

    @property
    def representation_sha256(self) -> str:
        self.validate()
        digest = hashlib.sha256()
        digest.update(str(self.max_delay_sec).encode())
        digest.update(self.snapshot_mode.encode())
        digest.update(self.config_sha256.encode())
        digest.update("\n".join(self.source_receipts).encode())
        for name in (
            "opportunity_id", "series_id", "candidate_id", "asset", "day",
            "side", "phase", "snapshot_ts_ns", "phase_close_ts_ns",
            "event_cutoff", "entry_event_ordinal", "entry_availability_ts_ns",
            "cert_close_usd", "mfe_usd", "mae_usd", "wall_hit", "exit_ts_ns",
            "feature_receipt_sha256",
        ):
            value = np.ascontiguousarray(getattr(self, name))
            digest.update(str(value.dtype).encode())
            digest.update(repr(value.shape).encode())
            digest.update(value.tobytes())
        return digest.hexdigest()

    def save(self, path: os.PathLike[str] | str) -> str:
        self.validate()
        target = C.assert_workspace_output(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.suffix != ".npz":
            raise ConfirmationRefusal("opportunity path must end in .npz")
        tmp = target.with_name(target.name + f".tmp.{os.getpid()}")
        payload = {name: np.asarray(getattr(self, name)) for name in (
            "opportunity_id", "series_id", "candidate_id", "asset", "day",
            "side", "phase", "snapshot_ts_ns", "phase_close_ts_ns",
            "event_cutoff", "entry_event_ordinal", "entry_availability_ts_ns",
            "cert_close_usd", "mfe_usd", "mae_usd", "wall_hit", "exit_ts_ns",
            "feature_receipt_sha256")}
        with tmp.open("xb") as handle:
            np.savez_compressed(
                handle, **payload,
                max_delay_sec=np.asarray([self.max_delay_sec], np.int16),
                snapshot_mode=np.asarray([self.snapshot_mode], str),
                config_sha256=np.asarray([self.config_sha256], str),
                source_receipts=np.asarray(self.source_receipts, str),
                representation_sha256=np.asarray(
                    [self.representation_sha256], str))
            handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, target)
        return C.file_sha256(target)

    @classmethod
    def load(cls, path: os.PathLike[str] | str) -> "ConfirmationOpportunitySet":
        source = Path(path); C.guard_payload(source)
        fields = (
            "opportunity_id", "series_id", "candidate_id", "asset", "day",
            "side", "phase", "snapshot_ts_ns", "phase_close_ts_ns",
            "event_cutoff", "entry_event_ordinal", "entry_availability_ts_ns",
            "cert_close_usd", "mfe_usd", "mae_usd", "wall_hit", "exit_ts_ns",
            "feature_receipt_sha256")
        try:
            with np.load(source, allow_pickle=False) as values:
                result = cls(
                    **{name: values[name] for name in fields},
                    max_delay_sec=int(values["max_delay_sec"][0]),
                    snapshot_mode=str(values["snapshot_mode"][0]),
                    config_sha256=str(values["config_sha256"][0]),
                    source_receipts=tuple(
                        values["source_receipts"].astype(str).tolist()))
                expected = str(values["representation_sha256"][0])
        except (OSError, ValueError, KeyError) as exc:
            raise ConfirmationRefusal("cannot strict-load opportunity universe") from exc
        result.validate()
        if result.representation_sha256 != expected:
            raise ConfirmationRefusal("opportunity universe representation hash differs")
        return result


def combine_confirmation_opportunity_sets(
    datasets: Sequence[ConfirmationOpportunitySet],
) -> ConfirmationOpportunitySet:
    if not datasets:
        raise ConfirmationRefusal("cannot combine an empty opportunity list")
    for dataset in datasets:
        dataset.validate()
    first = datasets[0]
    if any((row.max_delay_sec, row.snapshot_mode, row.config_sha256)
           != (first.max_delay_sec, first.snapshot_mode, first.config_sha256)
           for row in datasets):
        raise ConfirmationRefusal("opportunity universes have incompatible configs")
    fields = (
        "opportunity_id", "series_id", "candidate_id", "asset", "day", "side",
        "phase", "snapshot_ts_ns", "phase_close_ts_ns", "event_cutoff",
        "entry_event_ordinal", "entry_availability_ts_ns", "cert_close_usd",
        "mfe_usd", "mae_usd", "wall_hit", "exit_ts_ns",
        "feature_receipt_sha256",
    )
    values = {name: np.concatenate([
        np.asarray(getattr(row, name)) for row in datasets]) for name in fields}
    result = ConfirmationOpportunitySet(
        **values, max_delay_sec=first.max_delay_sec,
        snapshot_mode=first.snapshot_mode, config_sha256=first.config_sha256,
        source_receipts=tuple(receipt for row in datasets
                              for receipt in row.source_receipts))
    result.validate(); return result


def combine_confirmation_datasets(
    datasets: Sequence[ConfirmationDataset],
) -> ConfirmationDataset:
    if not datasets:
        raise ConfirmationRefusal("cannot combine an empty confirmation dataset list")
    for dataset in datasets:
        dataset.validate()
    first = datasets[0]
    if (any(item.feature_names != first.feature_names for item in datasets)
            or any(item.config_sha256 != first.config_sha256 for item in datasets)
            or any(item.max_delay_sec != first.max_delay_sec for item in datasets)
            or any(item.snapshot_mode != first.snapshot_mode for item in datasets)):
        raise ConfirmationRefusal("confirmation datasets have incompatible schemas/configs")
    fields = (
        "features", "opportunity_id", "series_id", "candidate_id", "asset",
        "day", "side", "phase", "snapshot_ts_ns", "phase_close_ts_ns",
        "event_cutoff", "entry_event_ordinal", "entry_bid_px", "entry_ask_px",
        "entry_availability_ts_ns",
        "entry_mid2", "entry_spread_usd", "frozen_cost_usd", "candidate_count",
        "min_alert_age_sec", "max_alert_age_sec", "cert_close_usd", "mfe_usd",
        "mae_usd", "wall_hit", "exit_ts_ns", "feature_receipt_sha256",
    )
    joined = {name: np.concatenate([np.asarray(getattr(item, name))
                                    for item in datasets], axis=0) for name in fields}
    result = ConfirmationDataset(
        first.feature_names, **joined, max_delay_sec=first.max_delay_sec,
        snapshot_mode=first.snapshot_mode, config_sha256=first.config_sha256,
        source_receipts=tuple(receipt for item in datasets
                              for receipt in item.source_receipts))
    result.validate(); return result
