"""Sparse causal feature shards and runtime transformations."""

from __future__ import annotations

import bisect
from dataclasses import dataclass, replace
import hashlib
import math
import os
from pathlib import Path
from types import MappingProxyType
from typing import Final, Mapping, Sequence

import numpy as np

from . import common as C
from .confirmation_dataset import ConfirmationDataset
from .confirmation_types import re_full_sha
from .tabular_recovery_contracts import (
    CausalFeatureSchema, RecoveryRefusal, validate_model_feature_names,
)


FEATURE_SHARD_SCHEMA: Final = "QRE2TABFEATURESHARD2"
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


__all__ = [
    'CausalFeatureShard',
    'FEATURE_SHARD_SCHEMA',
    'SAMPLE_ACTION_CHANGE',
    'SAMPLE_BASE',
    'SAMPLE_ORACLE',
    'SAMPLE_ORACLE_ADJACENT',
    'SAMPLE_POLICY_CROSSING',
    'SAMPLE_RUNTIME_DENSE',
    'SAMPLE_TEACHER_ACTION',
    'encode_causal_relations',
    'prepare_runtime_feature_shard',
    'project_feature_schema',
    'runtime_dense_feature_shard',
]
