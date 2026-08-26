"""Precommitted failure-directed alternatives for tabular recovery."""

from __future__ import annotations

import math
from types import MappingProxyType
from typing import Mapping, Sequence

import numpy as np
from scipy.stats import t as student_t

from . import common as C
from .tabular_causal_expert import (
    CAUSAL_EXPERT_SCHEMA,
    CausalExpertActionEnsemble,
    ExpertRoutingTable,
    build_causal_expert_routing,
    fit_all_pre_h2_causal_expert_action_bundle,
    fit_causal_expert_action_seed,
)
from .tabular_failure_branch import (
    FAILURE_BRANCHES,
    FailureBranchDecision,
    FailureMeasurements,
    select_failure_branch,
)
from .tabular_histogram import (
    HISTOGRAM_COMPONENT_SCHEMA,
    HistogramComponentBundle,
    fit_all_pre_h2_histogram_component_bundle,
    fit_histogram_component_bundle,
)
from .tabular_histogram_action import (
    HISTOGRAM_ACTION_SCHEMA,
    HistogramActionBundle,
    fit_all_pre_h2_histogram_action_bundle,
    fit_histogram_action_bundle,
)
from .tabular_recovery_contracts import RecoveryRefusal
from .tabular_training import ComponentTrainingMatrix


def effect_reversal_trigger(era_effects: Sequence[np.ndarray]) -> Mapping[str, object]:
    if len(era_effects) < 2:
        raise RecoveryRefusal("effect reversal needs two eras")
    intervals = []
    for raw in era_effects:
        values = np.asarray(raw, np.float64)
        if len(values) < 2 or not np.all(np.isfinite(values)):
            raise RecoveryRefusal("era effects lack day clusters")
        half = float(
            student_t.ppf(0.975, len(values) - 1)
            * values.std(ddof=1)
            / math.sqrt(len(values))
        )
        intervals.append((float(values.mean() - half), float(values.mean() + half)))
    reversal = False
    for left, right in zip(intervals, intervals[1:]):
        if (left[0] > 0 and right[1] < 0) or (left[1] < 0 and right[0] > 0):
            reversal = True
    core = {
        "schema": "QRE2TABREVERSAL1",
        "intervals": tuple(intervals),
        "consecutive_excluding_zero_reversal": reversal,
        "activate_causal_experts": reversal,
    }
    return MappingProxyType({**core, "receipt_sha256": C.object_sha256(core)})


def identify_unstable_absolute_features(
    matrix: ComponentTrainingMatrix, *, chronology: object,
) -> Mapping[str, object]:
    """Register every drifting continuous absolute level; never cap the roster."""

    matrix.validate()
    chronology.__post_init__()
    x = np.asarray(matrix.x)
    target = np.asarray(matrix.current_asinh, np.float64)
    days = np.asarray(matrix.day, np.int64)
    categorical_tokens = (
        "mask", "flag", "count", "ordinal", "side", "phase",
        "weekday", "month", "hour", "minute", "second", "age",
    )
    candidates = []
    detail: dict[str, object] = {}
    for column, name in enumerate(matrix.feature_names):
        row = _absolute_feature_detail(
            name, np.asarray(x[:, column], np.float64), target, days, chronology,
            categorical_tokens,
        )
        if row is None:
            continue
        candidates.append(name)
        detail[name] = row
    selected = tuple(candidates)
    if not selected:
        raise RecoveryRefusal(
            "relation branch found no proven unstable absolute level")
    core = {
        "schema": "QRE2TABUNSTABLEABSOLUTE1",
        "matrix": matrix.receipt_sha256,
        "chronology": chronology.receipt_sha256,
        "selection_rule": "MEDIAN_RANGE_GE_ONE_TYPICAL_IQR_OR_EFFECT_SIGN_REVERSAL",
        "selected": selected,
        "detail": detail,
        "feature_cap": None,
        "h2_open_count": 0,
    }
    return MappingProxyType({**core, "receipt_sha256": C.object_sha256(core)})


def _absolute_feature_detail(
    name: str, values: np.ndarray, target: np.ndarray, days: np.ndarray,
    chronology: object, categorical_tokens: tuple[str, ...],
) -> dict[str, object] | None:
    lower = name.lower()
    if (lower.startswith("relation_") or any(token in lower for token in
            categorical_tokens) or len(np.unique(values)) < 50):
        return None
    era_rows = []
    effect_signs = []
    for era, lo, hi in chronology.oof_blocks:
        local = (days >= lo) & (days <= hi)
        if np.count_nonzero(local) < 20 or np.ptp(values[local]) <= 0:
            continue
        era_values = values[local]
        era_target = target[local]
        scale = float(np.subtract(*np.percentile(era_values, [75, 25])))
        covariance = float(np.mean(
            (era_values - era_values.mean()) * (era_target - era_target.mean())))
        effect_signs.append(int(np.sign(covariance)))
        era_rows.append((
            str(era), float(np.median(era_values)), scale, covariance,
        ))
    if len(era_rows) < 2:
        return None
    medians = np.asarray([row[1] for row in era_rows], np.float64)
    scales = np.asarray([row[2] for row in era_rows], np.float64)
    typical = max(
        float(np.median(scales[scales > 0])) if np.any(scales > 0) else 0.0,
        1e-12,
    )
    distribution_drift = float(np.ptp(medians)) / typical
    sign_reversal = 1 in effect_signs and -1 in effect_signs
    if not (distribution_drift >= 1.0 or sign_reversal):
        return None
    return {
        "eras": tuple(era_rows),
        "median_range_over_typical_iqr": distribution_drift,
        "effect_sign_reversal": sign_reversal,
    }


__all__ = [
    "CausalExpertActionEnsemble", "ExpertRoutingTable",
    "CAUSAL_EXPERT_SCHEMA",
    "FAILURE_BRANCHES", "FailureBranchDecision", "FailureMeasurements",
    "HISTOGRAM_ACTION_SCHEMA", "HISTOGRAM_COMPONENT_SCHEMA",
    "HistogramActionBundle", "HistogramComponentBundle",
    "build_causal_expert_routing", "effect_reversal_trigger",
    "fit_causal_expert_action_seed",
    "fit_all_pre_h2_histogram_action_bundle",
    "fit_all_pre_h2_histogram_component_bundle",
    "fit_all_pre_h2_causal_expert_action_bundle",
    "fit_histogram_action_bundle", "fit_histogram_component_bundle",
    "identify_unstable_absolute_features",
]
