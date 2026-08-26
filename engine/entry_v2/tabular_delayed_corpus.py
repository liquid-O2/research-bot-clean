"""Delayed corpus public interface.

Outcome, feature, and audit implementations live in focused sibling modules.
"""

from __future__ import annotations

import math
from types import MappingProxyType
from typing import Mapping

from . import common as C
from .confirmation_types import re_full_sha
from .tabular_delayed_audit import (
    FEATURE_AUDIT_SCHEMA, audit_causal_feature_roster,
    audit_causal_feature_roster_paths, sampling_reason_for_dataset,
)
from .tabular_delayed_features import (
    FEATURE_SHARD_SCHEMA, SAMPLE_ACTION_CHANGE, SAMPLE_BASE, SAMPLE_ORACLE,
    SAMPLE_ORACLE_ADJACENT, SAMPLE_POLICY_CROSSING, SAMPLE_RUNTIME_DENSE,
    SAMPLE_TEACHER_ACTION, CausalFeatureShard, encode_causal_relations,
    prepare_runtime_feature_shard, project_feature_schema,
    runtime_dense_feature_shard,
)
from .tabular_delayed_outcomes import (
    OUTCOME_SCHEMA, DelayedOutcomeShard, materialize_delayed_outcome_session,
)
from .tabular_recovery_contracts import RecoveryRefusal


def _sha(value: object) -> bool:
    return isinstance(value, str) and re_full_sha(value)


def five_minute_extension_trigger(
    *, ceiling_300_usd: float, ceiling_600_usd: float,
    receipt_300_sha256: str, receipt_600_sha256: str,
) -> Mapping[str, object]:
    if (not all(math.isfinite(value) and value > 0 for value in (
            ceiling_300_usd, ceiling_600_usd))
            or ceiling_600_usd < ceiling_300_usd
            or not _sha(receipt_300_sha256) or not _sha(receipt_600_sha256)):
        raise RecoveryRefusal("five-minute censor comparison is malformed")
    incremental = (ceiling_600_usd - ceiling_300_usd) / ceiling_300_usd
    core = {
        "schema": "QRE2TAB600TRIGGER1",
        "ceiling_300_usd": ceiling_300_usd,
        "ceiling_600_usd": ceiling_600_usd,
        "incremental_fraction": incremental,
        "trigger_threshold": .10,
        "extend_to_600": incremental > .10,
        "receipt_300_sha256": receipt_300_sha256,
        "receipt_600_sha256": receipt_600_sha256,
        "h2_open_count": 0,
    }
    return MappingProxyType({**core, "receipt_sha256": C.object_sha256(core)})


__all__ = [
    "CausalFeatureShard", "DelayedOutcomeShard", "FEATURE_AUDIT_SCHEMA",
    "FEATURE_SHARD_SCHEMA", "OUTCOME_SCHEMA", "SAMPLE_ACTION_CHANGE",
    "SAMPLE_BASE", "SAMPLE_ORACLE", "SAMPLE_ORACLE_ADJACENT",
    "SAMPLE_POLICY_CROSSING", "SAMPLE_RUNTIME_DENSE",
    "SAMPLE_TEACHER_ACTION", "audit_causal_feature_roster",
    "audit_causal_feature_roster_paths", "encode_causal_relations",
    "five_minute_extension_trigger", "materialize_delayed_outcome_session",
    "prepare_runtime_feature_shard", "project_feature_schema",
    "runtime_dense_feature_shard", "sampling_reason_for_dataset",
]
