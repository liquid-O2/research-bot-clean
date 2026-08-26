"""Sampling receipts and causal feature-roster audits."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from types import MappingProxyType
from typing import Final, Mapping, Sequence

import numpy as np

from . import common as C
from .confirmation_dataset import ConfirmationDataset
from .confirmation_types import NANOS_PER_SECOND, training_offsets_seconds
from .tabular_delayed_features import (
    CausalFeatureShard, SAMPLE_ACTION_CHANGE, SAMPLE_BASE, SAMPLE_BITS,
    SAMPLE_ORACLE, SAMPLE_ORACLE_ADJACENT, SAMPLE_POLICY_CROSSING,
    SAMPLE_TEACHER_ACTION,
)
from .tabular_recovery_contracts import (
    CausalFeatureSchema, RecoveryRefusal,
)


FEATURE_AUDIT_SCHEMA: Final = "QRE2TABFEATUREAUDIT1"


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


__all__ = [
    'FEATURE_AUDIT_SCHEMA',
    'audit_causal_feature_roster',
    'audit_causal_feature_roster_paths',
    'sampling_reason_for_dataset',
]
