"""Day-sharded dense outcomes and sparse causal features for tabular recovery.

The outcome and feature planes are intentionally different durable schemas.
The outcome plane is dense at every receive-second and may contain privileged
future labels.  The feature plane contains causal prefixes only and refuses
every teacher/outcome-shaped feature name at load time.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import math
import os
from pathlib import Path
from types import MappingProxyType
from typing import Final, Iterable, Mapping, Sequence

import numpy as np

from . import common as C
from .confirmation import (
    FEE_USD, NANOS_PER_SECOND, SCHEMA as CONFIRMATION_SCHEMA,
    ConfirmationConfig, ConfirmationDataset, ConfirmationRefusal,
    _OutcomeIndex, _binding_groups, _ceil_second, _simple_object_sha256,
    _stream_receipt, _verify_formation_teachers, re_full_sha,
    training_offsets_seconds,
)
from .corpus import ASSET_MULTIPLIER
from .diagnostic_inputs import (
    build_candidate_truth_bindings, build_event_truth_columns,
)
from .event_pack import EventPack
from .tabular_recovery_contracts import (
    BASE_TRAINING_OFFSETS_SEC, CausalFeatureSchema, RecoveryRefusal,
    validate_model_feature_names,
)


OUTCOME_SCHEMA: Final = "QRE2TABOUTCOME1"
FEATURE_SHARD_SCHEMA: Final = "QRE2TABFEATURESHARD2"
FEATURE_AUDIT_SCHEMA: Final = "QRE2TABFEATUREAUDIT1"
SAMPLE_BASE: Final = 1
SAMPLE_ORACLE: Final = 2
SAMPLE_ORACLE_ADJACENT: Final = 4
SAMPLE_POLICY_CROSSING: Final = 8
SAMPLE_ACTION_CHANGE: Final = 16
SAMPLE_TEACHER_ACTION: Final = 32
SAMPLE_RUNTIME_DENSE: Final = 64
SAMPLE_BITS: Final = (
    SAMPLE_BASE | SAMPLE_ORACLE | SAMPLE_ORACLE_ADJACENT
    | SAMPLE_POLICY_CROSSING | SAMPLE_ACTION_CHANGE | SAMPLE_TEACHER_ACTION
    | SAMPLE_RUNTIME_DENSE)


def _sha(value: object) -> bool:
    return isinstance(value, str) and re_full_sha(value)


def _hash_array(digest: "hashlib._Hash", value: np.ndarray) -> None:
    array = np.ascontiguousarray(value)
    digest.update(str(array.dtype).encode())
    digest.update(repr(array.shape).encode())
    digest.update(array.tobytes())


def _cent_values(values: np.ndarray, name: str) -> np.ndarray:
    source = np.asarray(values, np.float64)
    cents = np.rint(source * 100.0).astype(np.int64)
    if not np.allclose(cents / 100.0, source, atol=1e-7, rtol=0):
        raise RecoveryRefusal(f"{name} is not exact cents")
    return cents


@dataclass(frozen=True, slots=True)
class DelayedOutcomeShard:
    """One portfolio asset-day's dense, privileged delayed outcome plane."""

    opportunity_id: np.ndarray
    series_id: np.ndarray
    candidate_id: np.ndarray
    asset: np.ndarray
    day: np.ndarray
    side: np.ndarray
    phase: np.ndarray
    watch_start_ts_ns: np.ndarray
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
    signed_pnl_usd: np.ndarray
    phase_close_pnl_usd: np.ndarray
    phase_exit_ts_ns: np.ndarray
    mfe_usd: np.ndarray
    mae_usd: np.ndarray
    wall_hit: np.ndarray
    wall_hit_ts_ns: np.ndarray
    wall_pnl_usd: np.ndarray
    exit_ts_ns: np.ndarray
    cost_applied_count: np.ndarray
    event_prefix_receipt_sha256: np.ndarray
    max_delay_sec: int
    config_sha256: str
    source_receipts: tuple[str, ...]

    def validate(self) -> None:
        n = len(self.opportunity_id)
        fields = tuple(getattr(self, name) for name in (
            "series_id", "candidate_id", "asset", "day", "side", "phase",
            "watch_start_ts_ns", "snapshot_ts_ns", "phase_close_ts_ns",
            "event_cutoff", "entry_event_ordinal", "entry_availability_ts_ns",
            "entry_bid_px", "entry_ask_px", "entry_mid2", "entry_spread_usd",
            "frozen_cost_usd", "signed_pnl_usd", "phase_close_pnl_usd",
            "phase_exit_ts_ns", "mfe_usd", "mae_usd", "wall_hit",
            "wall_hit_ts_ns", "wall_pnl_usd", "exit_ts_ns",
            "cost_applied_count", "event_prefix_receipt_sha256"))
        if (n == 0 or any(np.asarray(value).shape != (n,) for value in fields)
                or len(set(np.asarray(self.opportunity_id, str).tolist())) != n
                or len(set(np.asarray(self.asset, str).tolist())) != 1
                or len(set(np.asarray(self.day, np.int64).tolist())) != 1
                or not np.all(np.isin(self.asset, C.ASSETS))
                or not np.all(np.isin(self.side, (-1, 1)))
                or not np.all(np.asarray(self.snapshot_ts_ns)
                              >= np.asarray(self.watch_start_ts_ns))
                or not np.all(np.asarray(self.snapshot_ts_ns)
                              <= np.asarray(self.watch_start_ts_ns)
                              + self.max_delay_sec * NANOS_PER_SECOND)
                or not np.all(np.asarray(self.entry_availability_ts_ns)
                              < np.asarray(self.snapshot_ts_ns))
                or not np.all(np.asarray(self.event_cutoff) > 0)
                or not np.all(np.asarray(self.entry_event_ordinal)
                              < np.asarray(self.event_cutoff))
                or not np.all(np.asarray(self.entry_bid_px) > 0)
                or not np.all(np.asarray(self.entry_ask_px)
                              > np.asarray(self.entry_bid_px))
                or not np.array_equal(
                    np.asarray(self.entry_mid2),
                    np.asarray(self.entry_bid_px) + np.asarray(self.entry_ask_px))
                or not np.all(np.asarray(self.entry_spread_usd) >= 0)
                or not np.all(np.asarray(self.frozen_cost_usd) >= 0)
                or not np.all(np.asarray(self.cost_applied_count) == 1)
                or not np.all(np.asarray(self.exit_ts_ns)
                              >= np.asarray(self.snapshot_ts_ns))
                or not np.all(np.asarray(self.phase_exit_ts_ns)
                              >= np.asarray(self.snapshot_ts_ns))
                or not np.all(np.asarray(self.exit_ts_ns)
                              <= np.asarray(self.phase_exit_ts_ns))
                or not np.all(np.isfinite(self.signed_pnl_usd))
                or not np.all(np.isfinite(self.phase_close_pnl_usd))
                or not np.all(np.asarray(self.mfe_usd) >= 0)
                or not np.all(np.asarray(self.mae_usd) >= 0)
                or self.max_delay_sec not in (300, 600)
                or not _sha(self.config_sha256)
                or any(not _sha(value) for value in self.source_receipts)
                or any(not _sha(value) for value in
                       np.asarray(self.event_prefix_receipt_sha256, str))):
            raise RecoveryRefusal("delayed outcome shard is malformed")
        _cent_values(self.signed_pnl_usd, "signed PnL")
        _cent_values(self.phase_close_pnl_usd, "phase-close PnL")
        wall = np.asarray(self.wall_hit, bool)
        if (np.any(np.asarray(self.wall_hit_ts_ns)[wall]
                  != np.asarray(self.exit_ts_ns)[wall])
                or np.any(np.asarray(self.wall_hit_ts_ns)[~wall] != -1)
                or np.any(np.asarray(self.wall_pnl_usd)[~wall] != 0.0)
                or not np.allclose(
                    np.asarray(self.wall_pnl_usd)[wall],
                    np.asarray(self.signed_pnl_usd)[wall], atol=1e-7, rtol=0)
                or not np.allclose(
                    np.asarray(self.signed_pnl_usd)[~wall],
                    np.asarray(self.phase_close_pnl_usd)[~wall],
                    atol=1e-7, rtol=0)):
            raise RecoveryRefusal("wall/phase outcome identities differ")
        series = np.asarray(self.series_id, str)
        candidate = np.asarray(self.candidate_id, str)
        timestamps = np.asarray(self.snapshot_ts_ns, np.int64)
        mapping: dict[str, set[str]] = {}
        for key, value in zip(series, candidate):
            mapping.setdefault(key, set()).add(value)
        if any(len(values) != 1 for values in mapping.values()):
            raise RecoveryRefusal("one delayed series maps to multiple candidates")
        order = np.lexsort((timestamps, series))
        sorted_series = series[order]; sorted_ts = timestamps[order]
        if np.any((sorted_series[1:] == sorted_series[:-1])
                  & (sorted_ts[1:] <= sorted_ts[:-1])):
            raise RecoveryRefusal("delayed series chronology is not strict")

    @property
    def representation_sha256(self) -> str:
        self.validate()
        digest = hashlib.sha256()
        digest.update(OUTCOME_SCHEMA.encode())
        digest.update(str(self.max_delay_sec).encode())
        digest.update(self.config_sha256.encode())
        digest.update("\n".join(self.source_receipts).encode())
        for name in self.array_fields():
            _hash_array(digest, np.asarray(getattr(self, name)))
        return digest.hexdigest()

    @staticmethod
    def array_fields() -> tuple[str, ...]:
        return (
            "opportunity_id", "series_id", "candidate_id", "asset", "day",
            "side", "phase", "watch_start_ts_ns", "snapshot_ts_ns",
            "phase_close_ts_ns", "event_cutoff", "entry_event_ordinal",
            "entry_availability_ts_ns", "entry_bid_px", "entry_ask_px",
            "entry_mid2", "entry_spread_usd", "frozen_cost_usd",
            "signed_pnl_usd", "phase_close_pnl_usd", "phase_exit_ts_ns",
            "mfe_usd", "mae_usd", "wall_hit", "wall_hit_ts_ns",
            "wall_pnl_usd", "exit_ts_ns", "cost_applied_count",
            "event_prefix_receipt_sha256")

    def subset(self, mask: np.ndarray) -> "DelayedOutcomeShard":
        selected = np.asarray(mask, bool)
        if selected.shape != (len(self.opportunity_id),) or not selected.any():
            raise RecoveryRefusal("delayed outcome subset is empty/malformed")
        result = replace(self, **{
            name: np.asarray(getattr(self, name))[selected]
            for name in self.array_fields()})
        result.validate(); return result

    def save(self, path: os.PathLike[str] | str) -> str:
        self.validate()
        target = C.assert_workspace_output(path)
        if target.suffix != ".npz":
            raise RecoveryRefusal("delayed outcome shard must be .npz")
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + f".tmp.{os.getpid()}")
        with tmp.open("xb") as handle:
            np.savez_compressed(
                handle,
                **{name: np.asarray(getattr(self, name))
                   for name in self.array_fields()},
                schema=np.asarray([OUTCOME_SCHEMA], str),
                max_delay_sec=np.asarray([self.max_delay_sec], np.int16),
                config_sha256=np.asarray([self.config_sha256], str),
                source_receipts=np.asarray(self.source_receipts, str),
                representation_sha256=np.asarray(
                    [self.representation_sha256], str))
            handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, target)
        return C.file_sha256(target)

    @classmethod
    def load(cls, path: os.PathLike[str] | str) -> "DelayedOutcomeShard":
        source = Path(path); C.guard_payload(source)
        try:
            with np.load(source, allow_pickle=False) as values:
                if str(values["schema"][0]) != OUTCOME_SCHEMA:
                    raise RecoveryRefusal("delayed outcome schema differs")
                result = cls(
                    **{name: values[name] for name in cls.array_fields()},
                    max_delay_sec=int(values["max_delay_sec"][0]),
                    config_sha256=str(values["config_sha256"][0]),
                    source_receipts=tuple(
                        values["source_receipts"].astype(str).tolist()))
                expected = str(values["representation_sha256"][0])
        except (OSError, ValueError, KeyError) as exc:
            raise RecoveryRefusal("cannot strict-load delayed outcome shard") from exc
        result.validate()
        if result.representation_sha256 != expected:
            raise RecoveryRefusal("delayed outcome representation differs")
        return result


@dataclass(frozen=True, slots=True)
class CausalFeatureShard:
    """Sparse model plane; no realized outcome can cross this boundary."""

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
    event_cutoff: np.ndarray
    entry_event_ordinal: np.ndarray
    entry_availability_ts_ns: np.ndarray
    watch_age_sec: np.ndarray
    sampling_reason: np.ndarray
    feature_receipt_sha256: np.ndarray
    base_config_sha256: str
    sampling_receipt_sha256: str
    source_receipts: tuple[str, ...]

    def validate(self) -> None:
        names = validate_model_feature_names(self.feature_names)
        matrix = np.asarray(self.features)
        n = len(matrix)
        vectors = tuple(getattr(self, name) for name in self.array_fields()[1:])
        if (matrix.ndim != 2 or matrix.shape[1] != len(names) or n == 0
                or any(np.asarray(value).shape != (n,) for value in vectors)
                or not np.all(np.isfinite(matrix))
                or len(set(np.asarray(self.opportunity_id, str).tolist())) != n
                or len(set(np.asarray(self.asset, str).tolist())) != 1
                or len(set(np.asarray(self.day, np.int64).tolist())) != 1
                or not np.all(np.isin(self.asset, C.ASSETS))
                or not np.all(np.isin(self.side, (-1, 1)))
                or not np.all(np.asarray(self.event_cutoff) > 0)
                or not np.all(np.asarray(self.entry_event_ordinal)
                              < np.asarray(self.event_cutoff))
                or not np.all(np.asarray(self.entry_availability_ts_ns)
                              < np.asarray(self.snapshot_ts_ns))
                or not np.all(np.asarray(self.watch_age_sec) >= 0)
                or np.any(np.asarray(self.sampling_reason, np.int16) <= 0)
                or np.any(np.asarray(self.sampling_reason, np.int16)
                          & ~SAMPLE_BITS)
                or not _sha(self.base_config_sha256)
                or not _sha(self.sampling_receipt_sha256)
                or any(not _sha(value) for value in self.source_receipts)
                or any(not _sha(value) for value in
                       np.asarray(self.feature_receipt_sha256, str))):
            raise RecoveryRefusal("causal feature shard is malformed/leaking")

    @staticmethod
    def array_fields() -> tuple[str, ...]:
        return (
            "features", "opportunity_id", "series_id", "candidate_id",
            "asset", "day", "side", "phase", "snapshot_ts_ns",
            "event_cutoff", "entry_event_ordinal", "entry_availability_ts_ns",
            "watch_age_sec", "sampling_reason", "feature_receipt_sha256")

    @property
    def representation_sha256(self) -> str:
        self.validate()
        digest = hashlib.sha256()
        digest.update(FEATURE_SHARD_SCHEMA.encode())
        digest.update("\n".join(self.feature_names).encode())
        digest.update(self.base_config_sha256.encode())
        digest.update(self.sampling_receipt_sha256.encode())
        digest.update("\n".join(self.source_receipts).encode())
        for name in self.array_fields():
            _hash_array(digest, np.asarray(getattr(self, name)))
        return digest.hexdigest()

    def save(self, path: os.PathLike[str] | str) -> str:
        self.validate()
        target = C.assert_workspace_output(path)
        if target.suffix != ".npz":
            raise RecoveryRefusal("causal feature shard must be .npz")
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + f".tmp.{os.getpid()}")
        with tmp.open("xb") as handle:
            np.savez_compressed(
                handle, feature_names=np.asarray(self.feature_names, str),
                **{name: np.asarray(getattr(self, name))
                   for name in self.array_fields()},
                schema=np.asarray([FEATURE_SHARD_SCHEMA], str),
                base_config_sha256=np.asarray([self.base_config_sha256], str),
                sampling_receipt_sha256=np.asarray(
                    [self.sampling_receipt_sha256], str),
                source_receipts=np.asarray(self.source_receipts, str),
                representation_sha256=np.asarray(
                    [self.representation_sha256], str))
            handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, target)
        return C.file_sha256(target)

    @classmethod
    def load(cls, path: os.PathLike[str] | str) -> "CausalFeatureShard":
        source = Path(path); C.guard_payload(source)
        try:
            with np.load(source, allow_pickle=False) as values:
                if str(values["schema"][0]) != FEATURE_SHARD_SCHEMA:
                    raise RecoveryRefusal("causal feature shard schema differs")
                result = cls(
                    feature_names=tuple(values["feature_names"].astype(str).tolist()),
                    **{name: values[name] for name in cls.array_fields()},
                    base_config_sha256=str(values["base_config_sha256"][0]),
                    sampling_receipt_sha256=str(
                        values["sampling_receipt_sha256"][0]),
                    source_receipts=tuple(
                        values["source_receipts"].astype(str).tolist()))
                expected = str(values["representation_sha256"][0])
        except (OSError, ValueError, KeyError) as exc:
            raise RecoveryRefusal("cannot strict-load causal feature shard") from exc
        result.validate()
        if result.representation_sha256 != expected:
            raise RecoveryRefusal("causal feature representation differs")
        return result

    @classmethod
    def from_confirmation_dataset(
        cls, dataset: ConfirmationDataset, *, sampling_reason: np.ndarray,
        sampling_receipt_sha256: str,
    ) -> "CausalFeatureShard":
        dataset.validate()
        reason = np.asarray(sampling_reason, np.int16)
        if reason.shape != (len(dataset.features),):
            raise RecoveryRefusal("feature sampling reason shape differs")
        result = cls(
            feature_names=validate_model_feature_names(dataset.feature_names),
            features=np.asarray(dataset.features, np.float32).copy(),
            opportunity_id=np.asarray(dataset.opportunity_id, str).copy(),
            series_id=np.asarray(dataset.series_id, str).copy(),
            candidate_id=np.asarray(dataset.candidate_id, str).copy(),
            asset=np.asarray(dataset.asset, str).copy(),
            day=np.asarray(dataset.day, np.int64).copy(),
            side=np.asarray(dataset.side, np.int8).copy(),
            phase=np.asarray(dataset.phase, str).copy(),
            snapshot_ts_ns=np.asarray(dataset.snapshot_ts_ns, np.int64).copy(),
            event_cutoff=np.asarray(dataset.event_cutoff, np.int64).copy(),
            entry_event_ordinal=np.asarray(
                dataset.entry_event_ordinal, np.int64).copy(),
            entry_availability_ts_ns=np.asarray(
                dataset.entry_availability_ts_ns, np.int64).copy(),
            watch_age_sec=np.asarray(dataset.min_alert_age_sec, np.float32).copy(),
            sampling_reason=reason.copy(),
            feature_receipt_sha256=np.asarray(
                dataset.feature_receipt_sha256, str).copy(),
            base_config_sha256=dataset.config_sha256,
            sampling_receipt_sha256=sampling_receipt_sha256,
            source_receipts=tuple(dataset.source_receipts))
        result.validate(); return result


def runtime_dense_feature_shard(dataset:ConfirmationDataset)->CausalFeatureShard:
    """Strip a causal every-second runtime dataset to the model-only plane."""

    dataset.validate()
    expected_mode_receipt=C.object_sha256({
        "schema":"QRE2CONFOUTCOMEMODE1","compute_outcomes":False})
    if (dataset.snapshot_mode!="REPLAY"
            or dataset.source_receipts[-1]!=expected_mode_receipt):
        raise RecoveryRefusal(
            "runtime feature stripping requires causal REPLAY/outcomes-disabled input")
    receipt=C.object_sha256({"schema":"QRE2TABRUNTIMESAMPLING1",
        "dataset":dataset.representation_sha256,"every_receive_second":True,
        "outcomes_computed":False})
    result=CausalFeatureShard.from_confirmation_dataset(
        dataset,sampling_reason=np.full(
            len(dataset.features),SAMPLE_RUNTIME_DENSE,np.int16),
        sampling_receipt_sha256=receipt)
    result.validate();return result


def materialize_delayed_outcome_session(
    pack: EventPack,
    candidates: Iterable[Mapping[str, str]],
    teachers: Iterable[Mapping[str, str]],
    *, max_delay_sec: int = 300,
) -> DelayedOutcomeShard:
    """Build the exact every-second outcome plane without model features."""

    config = ConfirmationConfig(max_delay_sec=max_delay_sec, snapshot_mode="REPLAY")
    candidate_rows = tuple(candidates); teacher_rows = tuple(teachers)
    bindings = build_candidate_truth_bindings(candidate_rows, teacher_rows)
    if ({row.asset for row in bindings} != {pack.header.asset}
            or {row.trading_day for row in bindings} != {pack.header.d8}):
        raise RecoveryRefusal("delayed outcome bindings differ from event session")
    C.guard_date(pack.header.d8)
    raw = np.asarray(pack.rows)
    truth = build_event_truth_columns(raw, pack.header.asset, bindings)
    conservation = _stream_receipt(pack)
    formation_parity = _verify_formation_teachers(
        bindings, truth, raw, pack.header.asset)
    groups = _binding_groups(bindings)
    if not groups:
        raise RecoveryRefusal("delayed outcome session has no learnable candidates")
    fields: dict[str, list[np.ndarray]] = {
        name: [] for name in DelayedOutcomeShard.array_fields()}
    indices: dict[tuple[int, int, int, int], _OutcomeIndex] = {}
    for key, members in sorted(groups.items(), key=lambda item: repr(item[0])):
        (_asset, _day, side, phase, _phase_open, phase_close,
         _ceiling, _multiplier, _native_candidate_id) = key
        member = members[0]
        quality_key = member.truth_quality_key
        index = indices.get(quality_key)
        if index is None:
            index = _OutcomeIndex(
                raw, truth.candidate_columns(member), pack.header.asset)
            indices[quality_key] = index
        series_id = C.object_sha256({"schema": "QRE2CONFSERIES1", "key": key})
        watch_start = _ceil_second(member.decision_ts_ns)
        last = min(
            member.decision_ts_ns + max_delay_sec * NANOS_PER_SECOND,
            member.phase_close_ts_ns - 1)
        if watch_start > last:
            continue
        snapshots = np.arange(
            watch_start, last + 1, NANOS_PER_SECOND, dtype=np.int64)
        positions = np.searchsorted(
            index.ts, snapshots.astype(np.uint64), side="left") - 1
        visible = positions >= 0
        snapshots = snapshots[visible]; positions = positions[visible]
        if not len(snapshots):
            continue
        raw_indices = index.indices[positions]
        bid = raw["bid_px"][raw_indices].astype(np.int64)
        ask = raw["ask_px"][raw_indices].astype(np.int64)
        mid2 = index.mid2[positions]
        spread = ((ask - bid) * 1e-9
                  * ASSET_MULTIPLIER[pack.header.asset])
        costs = spread + FEE_USD
        cutoff = np.searchsorted(
            raw["ts_recv_ns"], snapshots.astype(np.uint64),
            side="left").astype(np.int64)
        outcome = index.outcomes_many(
            snapshot_ts_ns=snapshots, side=int(side),
            phase_close_ts_ns=int(phase_close), entry_mid2=mid2,
            frozen_cost_usd=costs)
        keep = np.asarray(outcome["input_index"], np.int64)
        snapshots = snapshots[keep]; positions = positions[keep]
        raw_indices = raw_indices[keep]; bid = bid[keep]; ask = ask[keep]
        mid2 = mid2[keep]; spread = spread[keep]; costs = costs[keep]
        cutoff = cutoff[keep]

        # Reconstruct the un-walled phase-close value from the same exact
        # generation boundary used by ``_OutcomeIndex.outcomes_many``.
        starts = np.searchsorted(index.ts, snapshots.astype(np.uint64), side="left")
        phase_end = int(np.searchsorted(
            index.ts, np.uint64(phase_close), side="right"))
        ends = np.minimum(phase_end, index.generation_end[starts])
        phase_position = ends - 1
        phase_mid = index.mid2[phase_position]
        phase_pnl = (int(side) * (phase_mid - mid2) * index.factor - costs)
        phase_exit = index.ts[phase_position].astype(np.int64)
        wall = np.asarray(outcome["wall_hit"], bool)
        exit_ts = np.asarray(outcome["exit_ts_ns"], np.int64)
        signed = np.asarray(outcome["cert_close_usd"], np.float64)
        opportunity = np.asarray([_simple_object_sha256({
            "schema": CONFIRMATION_SCHEMA, "series_id": series_id,
            "snapshot_ts_ns": int(snapshot),
            "candidate_ids": (member.candidate_id,),
        }) for snapshot in snapshots], str)
        receipts = np.asarray([_simple_object_sha256({
            "schema": "QRE2TABPREFIX1",
            "stream": conservation.receipt_sha256,
            "formation_parity": formation_parity,
            "config": config.receipt_sha256,
            "series_id": series_id,
            "snapshot_ts_ns": int(snapshot),
            "event_cutoff": int(cut),
            "candidate_id": member.candidate_id,
        }) for snapshot, cut in zip(snapshots, cutoff)], str)
        n = len(snapshots)
        values = {
            "opportunity_id": opportunity,
            "series_id": np.full(n, series_id),
            "candidate_id": np.full(n, member.candidate_id),
            "asset": np.full(n, pack.header.asset),
            "day": np.full(n, pack.header.d8, np.int64),
            "side": np.full(n, side, np.int8),
            "phase": np.full(n, str(phase)),
            "watch_start_ts_ns": np.full(n, watch_start, np.int64),
            "snapshot_ts_ns": snapshots,
            "phase_close_ts_ns": np.full(n, phase_close, np.int64),
            "event_cutoff": cutoff,
            "entry_event_ordinal": raw_indices.astype(np.int64),
            "entry_availability_ts_ns": raw["ts_recv_ns"][raw_indices]
                .astype(np.int64),
            "entry_bid_px": bid,
            "entry_ask_px": ask,
            "entry_mid2": mid2,
            "entry_spread_usd": spread.astype(np.float64),
            "frozen_cost_usd": costs.astype(np.float64),
            "signed_pnl_usd": signed,
            "phase_close_pnl_usd": phase_pnl.astype(np.float64),
            "phase_exit_ts_ns": phase_exit,
            "mfe_usd": np.asarray(outcome["mfe_usd"], np.float64),
            "mae_usd": np.asarray(outcome["mae_usd"], np.float64),
            "wall_hit": wall,
            "wall_hit_ts_ns": np.where(wall, exit_ts, -1).astype(np.int64),
            "wall_pnl_usd": np.where(wall, signed, 0.0).astype(np.float64),
            "exit_ts_ns": exit_ts,
            "cost_applied_count": np.ones(n, np.int8),
            "event_prefix_receipt_sha256": receipts,
        }
        for name, value in values.items():
            fields[name].append(np.asarray(value))
    if not fields["opportunity_id"]:
        raise RecoveryRefusal("delayed outcome materialization produced no rows")
    result = DelayedOutcomeShard(
        **{name: np.concatenate(values) for name, values in fields.items()},
        max_delay_sec=max_delay_sec, config_sha256=config.receipt_sha256,
        source_receipts=(conservation.receipt_sha256, formation_parity))
    result.validate(); return result


def sampling_reason_for_dataset(
    dataset: ConfirmationDataset, *,
    oracle_timestamps: Mapping[str, Sequence[int]] | None = None,
    teacher_action_timestamps: Mapping[str, Sequence[int]] | None = None,
    policy_crossing_timestamps: Mapping[str, Sequence[int]] | None = None,
    action_change_timestamps: Mapping[str, Sequence[int]] | None = None,
) -> tuple[np.ndarray, str]:
    """Bind sparse base/Oracle/OOF enrichment reasons to materialized rows."""

    dataset.validate()
    series = np.asarray(dataset.series_id, str)
    ts = np.asarray(dataset.snapshot_ts_ns, np.int64)
    reason = np.zeros(len(ts), np.int16)
    registered_offsets = training_offsets_seconds(dataset.max_delay_sec)
    # Sparse snapshots are scheduled from ceil(decision second).  Their age
    # from the native subsecond decision is therefore ``offset + fraction``;
    # flooring recovers the registered integer offset even when the first
    # scheduled row is uncertifiable and absent.
    age = np.floor(np.asarray(dataset.min_alert_age_sec, np.float64)+1e-6).astype(np.int64)
    base = np.isin(age, registered_offsets)
    reason[base] |= SAMPLE_BASE

    def mark(mapping: Mapping[str, Sequence[int]] | None, bit: int,
             *, adjacent: bool = False) -> None:
        if mapping is None:
            return
        for key, raw_values in mapping.items():
            values = {int(value) for value in raw_values}
            if adjacent:
                originals = tuple(values)
                values = {value - NANOS_PER_SECOND for value in originals}
                values |= {value + NANOS_PER_SECOND for value in originals}
            local = (series == str(key)) & np.isin(ts, tuple(values))
            reason[local] |= bit

    mark(oracle_timestamps, SAMPLE_ORACLE)
    mark(oracle_timestamps, SAMPLE_ORACLE_ADJACENT, adjacent=True)
    mark(teacher_action_timestamps, SAMPLE_TEACHER_ACTION)
    mark(policy_crossing_timestamps, SAMPLE_POLICY_CROSSING)
    mark(action_change_timestamps, SAMPLE_ACTION_CHANGE)
    if np.any(reason == 0):
        raise RecoveryRefusal("materialized feature row has no registered sample reason")
    core = {
        "schema": "QRE2TABSAMPLING1",
        "base_offsets_sec": registered_offsets,
        "oracle": None if oracle_timestamps is None else {
            str(key): tuple(map(int, value))
            for key, value in sorted(oracle_timestamps.items())},
        "teacher_action": None if teacher_action_timestamps is None else {
            str(key): tuple(map(int, value))
            for key, value in sorted(teacher_action_timestamps.items())},
        "policy_crossing": None if policy_crossing_timestamps is None else {
            str(key): tuple(map(int, value))
            for key, value in sorted(policy_crossing_timestamps.items())},
        "action_change": None if action_change_timestamps is None else {
            str(key): tuple(map(int, value))
            for key, value in sorted(action_change_timestamps.items())},
    }
    return reason, C.object_sha256(core)


def audit_causal_feature_roster(
    shards: Sequence[CausalFeatureShard], *,
    proven_leaks: Sequence[str] = (),
) -> tuple[CausalFeatureSchema, Mapping[str, object]]:
    """Remove only exact constants, byte-identical columns, and named leaks."""

    rows = tuple(shards)
    if not rows:
        raise RecoveryRefusal("feature roster audit has no shards")
    for shard in rows:
        shard.validate()
    names = rows[0].feature_names
    if any(shard.feature_names != names for shard in rows):
        raise RecoveryRefusal("feature schema drifted across causal shards")
    leak_set = set(map(str, proven_leaks))
    if not leak_set <= set(names):
        raise RecoveryRefusal("named proven leak is absent from feature roster")
    minimum = np.full(len(names), np.inf, np.float64)
    maximum = np.full(len(names), -np.inf, np.float64)
    digests = [hashlib.sha256() for _ in names]
    for shard in rows:
        matrix = np.asarray(shard.features, np.float32)
        minimum = np.minimum(minimum, matrix.min(axis=0))
        maximum = np.maximum(maximum, matrix.max(axis=0))
        for index in range(len(names)):
            digests[index].update(np.ascontiguousarray(matrix[:, index]).tobytes())
    constants = {names[index] for index in np.flatnonzero(minimum == maximum)}
    by_digest: dict[str, list[int]] = {}
    for index, digest in enumerate(digests):
        if names[index] not in constants and names[index] not in leak_set:
            by_digest.setdefault(digest.hexdigest(), []).append(index)
    duplicate_pairs: list[tuple[str, str]] = []
    duplicate_drop: set[str] = set()
    for indices in by_digest.values():
        if len(indices) < 2:
            continue
        canonical = indices[0]
        for other in indices[1:]:
            if all(np.array_equal(
                    np.asarray(shard.features)[:, canonical],
                    np.asarray(shard.features)[:, other]) for shard in rows):
                duplicate_pairs.append((names[canonical], names[other]))
                duplicate_drop.add(names[other])
    retained = tuple(name for name in names
                     if name not in constants | duplicate_drop | leak_set)
    source_schema = C.object_sha256({
        "schema": FEATURE_AUDIT_SCHEMA,
        "source_feature_names": names,
        "source_representations": tuple(
            shard.representation_sha256 for shard in rows),
    })
    schema = CausalFeatureSchema(
        retained, source_schema,
        removed_constants=tuple(sorted(constants)),
        removed_duplicates=tuple(sorted(duplicate_pairs)),
        removed_proven_leaks=tuple(sorted(leak_set)))
    core = {
        "schema": FEATURE_AUDIT_SCHEMA,
        "source_schema_sha256": source_schema,
        "source_features": len(names),
        "retained_features": len(retained),
        "removed_constants": schema.removed_constants,
        "removed_duplicates": schema.removed_duplicates,
        "removed_proven_leaks": schema.removed_proven_leaks,
        "feature_schema_receipt_sha256": schema.receipt_sha256,
        "arbitrary_feature_cap_applied": False,
        "gex_dependency": False,
        "h2_open_count": 0,
    }
    return schema, MappingProxyType({
        **core, "receipt_sha256": C.object_sha256(core)})


def audit_causal_feature_roster_paths(
    paths: Sequence[os.PathLike[str] | str], *,
    proven_leaks: Sequence[str] = (),
) -> tuple[CausalFeatureSchema, Mapping[str, object]]:
    """Streaming full-corpus variant; holds only one asset-day in memory."""

    sources=tuple(Path(path) for path in paths)
    if not sources:raise RecoveryRefusal("streaming feature audit has no shards")
    names=None;minimum=None;maximum=None;digests=None;representations=[]
    for path in sources:
        shard=CausalFeatureShard.load(path);matrix=np.asarray(shard.features,np.float32)
        if names is None:
            names=shard.feature_names;minimum=np.full(len(names),np.inf)
            maximum=np.full(len(names),-np.inf);digests=[hashlib.sha256() for _ in names]
        elif shard.feature_names!=names:
            raise RecoveryRefusal("streaming causal feature schema drifted")
        minimum=np.minimum(minimum,matrix.min(axis=0));maximum=np.maximum(maximum,matrix.max(axis=0))
        for index,digest in enumerate(digests):
            digest.update(np.ascontiguousarray(matrix[:,index]).tobytes())
        representations.append(shard.representation_sha256)
    assert names is not None and minimum is not None and maximum is not None and digests is not None
    leak_set=set(map(str,proven_leaks))
    if not leak_set<=set(names):raise RecoveryRefusal("streaming named leak is absent")
    constants={names[index] for index in np.flatnonzero(minimum==maximum)}
    groups={}
    for index,digest in enumerate(digests):
        if names[index] not in constants|leak_set:
            groups.setdefault(digest.hexdigest(),[]).append(index)
    candidates=[indices for indices in groups.values() if len(indices)>1]
    exact={tuple(indices):True for indices in candidates}
    for path in sources:
        if not exact:break
        matrix=np.asarray(CausalFeatureShard.load(path).features,np.float32)
        for indices in tuple(exact):
            if not all(np.array_equal(matrix[:,indices[0]],matrix[:,other])
                       for other in indices[1:]):
                exact.pop(indices)
    duplicate_pairs=[];duplicate_drop=set()
    for indices in exact:
        canonical=indices[0]
        for other in indices[1:]:
            duplicate_pairs.append((names[canonical],names[other]));duplicate_drop.add(names[other])
    retained=tuple(name for name in names if name not in constants|duplicate_drop|leak_set)
    source_schema=C.object_sha256({"schema":FEATURE_AUDIT_SCHEMA,
        "source_feature_names":names,"source_representations":tuple(representations)})
    schema=CausalFeatureSchema(retained,source_schema,
        removed_constants=tuple(sorted(constants)),
        removed_duplicates=tuple(sorted(duplicate_pairs)),
        removed_proven_leaks=tuple(sorted(leak_set)))
    core={"schema":FEATURE_AUDIT_SCHEMA,"source_schema_sha256":source_schema,
          "source_features":len(names),"retained_features":len(retained),
          "removed_constants":schema.removed_constants,
          "removed_duplicates":schema.removed_duplicates,
          "removed_proven_leaks":schema.removed_proven_leaks,
          "feature_schema_receipt_sha256":schema.receipt_sha256,
          "arbitrary_feature_cap_applied":False,"gex_dependency":False,
          "streaming_one_shard_memory":True,"h2_open_count":0}
    return schema,MappingProxyType({**core,"receipt_sha256":C.object_sha256(core)})


def project_feature_schema(
    shard: CausalFeatureShard, schema: CausalFeatureSchema,
) -> CausalFeatureShard:
    shard.validate()
    schema.__post_init__()
    source = {name: index for index, name in enumerate(shard.feature_names)}
    if not set(schema.names) <= set(source):
        raise RecoveryRefusal("frozen feature schema is absent from shard")
    columns = np.asarray([source[name] for name in schema.names], np.int64)
    result = replace(
        shard, feature_names=schema.names,
        features=np.asarray(shard.features)[:, columns])
    result.validate(); return result


def encode_causal_relations(
    shard: CausalFeatureShard, *, unstable_absolute_features: Sequence[str],
) -> tuple[CausalFeatureShard, Mapping[str, object]]:
    """Failure-ladder branch 3: prefix-only watch-relative representation.

    The caller must supply the absolute levels whose OOF effect was measured
    unstable.  Those levels are dropped and replaced by causal deltas,
    transitions, slopes, accelerations, expanding z/rank, and recovery
    geometry.  There is no feature-count cap and no future row is consulted.
    """

    shard.validate()
    selected=tuple(map(str,unstable_absolute_features))
    if (not selected or len(selected)!=len(set(selected))
            or not set(selected)<=set(shard.feature_names)):
        raise RecoveryRefusal("relation encoding needs named unstable levels")
    source={name:index for index,name in enumerate(shard.feature_names)}
    series=np.asarray(shard.series_id,str);timestamps=np.asarray(shard.snapshot_ts_ns,np.int64)
    order=np.lexsort((timestamps,series));inverse=np.empty(len(order),np.int64);inverse[order]=np.arange(len(order))
    ordered_series=series[order];ordered_ts=timestamps[order]
    additions=[];addition_names=[]
    import bisect
    for name in selected:
        values=np.asarray(shard.features[:,source[name]],np.float64)[order]
        relative=np.zeros(len(values));delta=np.zeros(len(values));slope=np.zeros(len(values))
        acceleration=np.zeros(len(values));zscore=np.zeros(len(values));rank=np.zeros(len(values))
        from_max=np.zeros(len(values));from_min=np.zeros(len(values));transition=np.zeros(len(values))
        start=0
        while start<len(values):
            end=start+1
            while end<len(values) and ordered_series[end]==ordered_series[start]:end+=1
            seen=[];running_sum=0.0;running_sum2=0.0;running_max=-np.inf;running_min=np.inf
            first=float(values[start]);previous=first;previous_delta=0.0
            for position in range(start,end):
                current=float(values[position]);elapsed=max(0.0,(ordered_ts[position]-ordered_ts[start])/1e9)
                step=current-previous if position>start else 0.0
                relative[position]=current-first;delta[position]=step
                slope[position]=(current-first)/elapsed if elapsed>0 else 0.0
                acceleration[position]=step-previous_delta if position>start else 0.0
                count=position-start
                mean=running_sum/count if count else current
                variance=max(0.0,running_sum2/count-mean*mean) if count else 0.0
                zscore[position]=(current-mean)/math.sqrt(variance) if variance>0 else 0.0
                insertion=bisect.bisect_right(seen,current)
                rank[position]=insertion/(count+1)
                bisect.insort(seen,current)
                running_max=max(running_max,current);running_min=min(running_min,current)
                from_max[position]=current-running_max;from_min[position]=current-running_min
                transition[position]=float(np.sign(step)!=np.sign(previous_delta)) if position>start+1 else 0.0
                running_sum+=current;running_sum2+=current*current
                previous=current;previous_delta=step
            start=end
        derived=(relative,delta,slope,acceleration,zscore,rank,from_max,from_min,transition)
        suffixes=("watch_relative","delta_1","slope","acceleration","trailing_z",
                  "trailing_rank","recovery_from_max","recovery_from_min","state_transition")
        additions.extend(np.asarray(value[inverse],np.float32) for value in derived)
        addition_names.extend(f"relation_{name}_{suffix}" for suffix in suffixes)
    retained=[index for index,name in enumerate(shard.feature_names) if name not in set(selected)]
    output_names=tuple(shard.feature_names[index] for index in retained)+tuple(addition_names)
    matrix=np.column_stack((np.asarray(shard.features)[:,retained],*additions)).astype(np.float32)
    core={"schema":"QRE2TABRELATION1","source":shard.representation_sha256,
          "unstable_absolute_features":selected,"derived_names":tuple(addition_names),
          "causal_prefix_only":True,"arbitrary_feature_cap":False}
    receipt=C.object_sha256(core)
    result=replace(shard,feature_names=output_names,features=matrix,
                   source_receipts=shard.source_receipts+(receipt,))
    result.validate()
    return result,MappingProxyType({**core,"receipt_sha256":receipt})


def prepare_runtime_feature_shard(
    shard:CausalFeatureShard,schema:CausalFeatureSchema,
)->CausalFeatureShard:
    """Apply the frozen causal transform, then project its exact roster."""

    shard.validate();schema.__post_init__()
    if set(schema.names)<=set(shard.feature_names):
        return project_feature_schema(shard,schema)
    if not schema.relation_source_features:
        raise RecoveryRefusal("runtime feature shard lacks frozen schema")
    if not set(schema.relation_source_features)<=set(shard.feature_names):
        raise RecoveryRefusal("runtime relation sources are absent")
    transformed,_receipt=encode_causal_relations(shard,
        unstable_absolute_features=schema.relation_source_features)
    return project_feature_schema(transformed,schema)


def five_minute_extension_trigger(*,ceiling_300_usd: float,
        ceiling_600_usd: float, receipt_300_sha256: str,
        receipt_600_sha256: str) -> Mapping[str, object]:
    if (not all(math.isfinite(value) and value>0 for value in (
            ceiling_300_usd,ceiling_600_usd))
            or ceiling_600_usd<ceiling_300_usd
            or not _sha(receipt_300_sha256) or not _sha(receipt_600_sha256)):
        raise RecoveryRefusal("five-minute censor comparison is malformed")
    incremental=(ceiling_600_usd-ceiling_300_usd)/ceiling_300_usd
    core={"schema":"QRE2TAB600TRIGGER1","ceiling_300_usd":ceiling_300_usd,
          "ceiling_600_usd":ceiling_600_usd,"incremental_fraction":incremental,
          "trigger_threshold":.10,"extend_to_600":incremental>.10,
          "receipt_300_sha256":receipt_300_sha256,
          "receipt_600_sha256":receipt_600_sha256,"h2_open_count":0}
    return MappingProxyType({**core,"receipt_sha256":C.object_sha256(core)})


__all__ = [
    "CausalFeatureShard", "DelayedOutcomeShard", "FEATURE_AUDIT_SCHEMA",
    "FEATURE_SHARD_SCHEMA", "OUTCOME_SCHEMA", "SAMPLE_ACTION_CHANGE",
    "SAMPLE_BASE", "SAMPLE_ORACLE", "SAMPLE_ORACLE_ADJACENT",
    "SAMPLE_POLICY_CROSSING", "SAMPLE_TEACHER_ACTION",
    "SAMPLE_RUNTIME_DENSE",
    "audit_causal_feature_roster", "audit_causal_feature_roster_paths",
    "materialize_delayed_outcome_session", "project_feature_schema",
    "sampling_reason_for_dataset", "encode_causal_relations",
    "prepare_runtime_feature_shard",
    "five_minute_extension_trigger",
    "runtime_dense_feature_shard",
]
