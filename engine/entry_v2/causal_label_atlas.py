#!/usr/bin/env python3
"""Columnar, causal truth materialization for the Entry-V2 label atlas."""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from enum import Enum
import hashlib
import inspect
import json
import math
import dis
import threading
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from . import common as C


DEVELOPMENT_CUTOFF_NS = 1_751_320_800_000_000_000
PNL_UNITS_PER_USD = 2_000_000_000
WALL_UNITS = 900 * PNL_UNITS_PER_USD
HORIZON_SECONDS = (1, 10, 60, 300, 600, 900, 1200, 1800, 3600, 7200)
TREND_SECONDS = (10, 60, 300, 900, 1800)
FAVORABLE_DOLLAR_RUNGS = (300, 600, 1000, 1500, 2000)
ADVERSE_DOLLAR_RUNGS = (300, 600, 900)
PRIOR_SCALE_RUNGS = (0.5, 1.0, 2.0)


class AtlasRefusal(ValueError):
    pass


class BoundaryReason(str, Enum):
    ECONOMIC_EXIT = "ECONOMIC_EXIT"
    WALL = "WALL"
    PHASE = "PHASE"
    SOURCE = "SOURCE"
    GENERATION = "GENERATION"
    DEVELOPMENT = "DEVELOPMENT"
    NO_SANE_SUFFIX = "NO_SANE_SUFFIX"


class EndpointStatus(str, Enum):
    OBSERVED = "OBSERVED"
    CARRIED_FORWARD = "CARRIED_FORWARD"
    RIGHT_CENSORED = "RIGHT_CENSORED"
    UNAVAILABLE = "UNAVAILABLE"


class PassageState(str, Enum):
    ATTAINED = "ATTAINED"
    NOT_ATTAINED = "NOT_ATTAINED"
    CENSORED = "CENSORED"
    SAME_EVENT_TIE = "SAME_EVENT_TIE"
    NOT_AT_RISK = "NOT_AT_RISK"


class CellAvailability(str, Enum):
    MATERIALIZED = "MATERIALIZED"
    UNAVAILABLE_LOW_SUPPORT = "UNAVAILABLE_LOW_SUPPORT"
    UNAVAILABLE_SOURCE_SEMANTICS = "UNAVAILABLE_SOURCE_SEMANTICS"
    UNAVAILABLE_MISSING_PRIOR = "UNAVAILABLE_MISSING_PRIOR"
    PRUNED_BYTE_IDENTICAL = "PRUNED_BYTE_IDENTICAL"
    RIGHT_CENSORED = "RIGHT_CENSORED"
    NO_SANE_SUFFIX = "NO_SANE_SUFFIX"


class ActionMaskCause(str, Enum):
    NONE = "NONE"
    A004_OCCUPANCY = "A004_OCCUPANCY"
    A004_CAP = "A004_CAP"
    A004_ASSET_CAP = "A004_ASSET_CAP"
    A004_PORTFOLIO_CAP = "A004_PORTFOLIO_CAP"
    COMPLIANCE = "COMPLIANCE"
    NO_SANE_SUFFIX = "NO_SANE_SUFFIX"


@dataclass(frozen=True, slots=True)
class CanonicalOutcome:
    status: CellAvailability
    exit_ts_recv_ns: int
    exit_source_ordinal: int
    exit_reason: BoundaryReason
    final_net_units: int
    wall_hit: bool
    mfe_units: int
    mae_units: int


@dataclass(frozen=True, slots=True)
class CandidateAnchor:
    candidate_id: str
    decision_ts_ns: int
    side: int
    entry_mid2: int
    multiplier: int
    frozen_cost_units: int
    phase_close_ts_ns: int
    source_ordinal: int
    generation: int
    economic_exit_ts_ns: int | None = None
    economic_exit_source_ordinal: int = np.iinfo(np.uint32).max
    source_censor_ts_ns: int | None = None
    source_censor_ordinal: int = np.iinfo(np.uint32).max
    sigma_prior_units: int | None = None
    occupancy_masked: bool = False
    cap_masked: bool = False
    action_loss_mask: bool = True
    take_target: bool = False
    exact_time_group_id: str | None = None
    canonical: CanonicalOutcome | None = None
    now_wait_pass_regret_units: tuple[int, int, int] | None = None
    shadow_marginal_regret_units: tuple[int, int] | None = None
    process_utility_units: int | None = None
    prior_location_units: int | None = None
    prior_scale_units: int | None = None
    action_mask_cause: ActionMaskCause = ActionMaskCause.NONE
    payer_target: bool = False
    native_candidate_local: bool = False
    authoritative_teacher_action: bool | None = None
    asset: str = "TEST"
    trading_day: int = 19700101
    phase_open_ts_ns: int | None = None
    sane_ceiling_units: int | None = None

    def __post_init__(self) -> None:
        if not self.candidate_id or self.side not in (-1, 1):
            raise AtlasRefusal("candidate requires id and side in {-1,+1}")
        if self.multiplier <= 0 or self.frozen_cost_units < 0:
            raise AtlasRefusal("candidate economics must be positive/frozen integer units")
        if not self.asset or int(self.trading_day) <= 0:
            raise AtlasRefusal("candidate asset/trading day is required")
        if (self.occupancy_masked or self.cap_masked) and self.action_loss_mask:
            raise AtlasRefusal("occupancy/cap-masked candidate cannot be supervised")
        expected_occupancy = self.action_mask_cause is ActionMaskCause.A004_OCCUPANCY
        expected_cap = self.action_mask_cause in {
            ActionMaskCause.A004_CAP,
            ActionMaskCause.A004_ASSET_CAP,
            ActionMaskCause.A004_PORTFOLIO_CAP,
        }
        if (self.occupancy_masked != expected_occupancy
                or self.cap_masked != expected_cap):
            raise AtlasRefusal("typed A-004 mask cause differs from structural masks")
        if self.action_loss_mask != (self.action_mask_cause is ActionMaskCause.NONE):
            raise AtlasRefusal("action supervision differs from typed availability")
        if self.take_target and not self.action_loss_mask:
            raise AtlasRefusal("positive action target must be supervised")
        if (self.authoritative_teacher_action is not None and self.action_loss_mask
                and self.take_target != self.authoritative_teacher_action):
            raise AtlasRefusal("take target differs from authoritative teacher action")
        for name in ("decision_ts_ns", "entry_mid2", "multiplier", "frozen_cost_units"):
            if not isinstance(getattr(self, name), (int, np.integer)):
                raise AtlasRefusal(f"{name} must be exact integer")
        if (self.decision_ts_ns < 0 or self.decision_ts_ns >= DEVELOPMENT_CUTOFF_NS
                or self.phase_close_ts_ns <= self.decision_ts_ns):
            raise AtlasRefusal("candidate clocks violate the development/phase law")
        phase_metadata = (self.phase_open_ts_ns, self.sane_ceiling_units)
        if (phase_metadata[0] is None) != (phase_metadata[1] is None):
            raise AtlasRefusal("candidate phase query metadata is incomplete")
        if self.phase_open_ts_ns is not None:
            if (not isinstance(self.phase_open_ts_ns, (int, np.integer))
                    or not isinstance(self.sane_ceiling_units, (int, np.integer))
                    or self.phase_open_ts_ns > self.decision_ts_ns
                    or int(self.sane_ceiling_units) <= 0):
                raise AtlasRefusal("candidate phase query metadata is invalid")
        for timestamp in (self.economic_exit_ts_ns, self.source_censor_ts_ns):
            if timestamp is not None and timestamp < self.decision_ts_ns:
                raise AtlasRefusal("candidate terminal cannot precede its decision")
        if self.sigma_prior_units is not None and self.sigma_prior_units <= 0:
            raise AtlasRefusal("strictly-prior scale must be positive")
        if self.canonical is not None:
            if self.canonical.exit_ts_recv_ns < self.decision_ts_ns:
                raise AtlasRefusal("canonical terminal precedes the decision")
            if self.canonical.mfe_units < 0 or self.canonical.mae_units < 0:
                raise AtlasRefusal("canonical MFE/MAE must be nonnegative")
            economic = self.canonical.exit_reason in (
                BoundaryReason.ECONOMIC_EXIT, BoundaryReason.WALL,
                BoundaryReason.PHASE,
            )
            if ((self.canonical.status is CellAvailability.MATERIALIZED) != economic
                    or self.canonical.wall_hit != (
                        self.canonical.exit_reason is BoundaryReason.WALL)):
                raise AtlasRefusal("canonical availability/reason/wall typing is invalid")

    @classmethod
    def from_binding(
        cls, *, candidate_id: str, decision_ts_ns: int, side: int,
        entry_mid2: int, multiplier: int, frozen_cost_units: int,
        phase_close_ts_ns: int, source_ordinal: int, generation_at_cutoff: int,
        canonical_terminal: CanonicalOutcome | None,
        action_mask_cause: ActionMaskCause, prior_scale_units: int | None,
        authoritative_teacher_action: bool, asset: str, trading_day: int,
        **optional: Any,
    ) -> "CandidateAnchor":
        """Cycle-free adapter from a corpus/binding row into exact atlas inputs."""
        occupancy = action_mask_cause is ActionMaskCause.A004_OCCUPANCY
        cap = action_mask_cause in {
            ActionMaskCause.A004_CAP,
            ActionMaskCause.A004_ASSET_CAP,
            ActionMaskCause.A004_PORTFOLIO_CAP,
        }
        available = action_mask_cause is ActionMaskCause.NONE
        return cls(
            candidate_id=candidate_id, decision_ts_ns=decision_ts_ns, side=side,
            entry_mid2=entry_mid2, multiplier=multiplier,
            frozen_cost_units=frozen_cost_units,
            phase_close_ts_ns=phase_close_ts_ns, source_ordinal=source_ordinal,
            generation=generation_at_cutoff, canonical=canonical_terminal,
            sigma_prior_units=prior_scale_units, occupancy_masked=occupancy,
            cap_masked=cap, action_loss_mask=available,
            take_target=bool(authoritative_teacher_action) and available,
            authoritative_teacher_action=bool(authoritative_teacher_action),
            action_mask_cause=action_mask_cause, asset=asset,
            trading_day=trading_day, **optional,
        )


@dataclass(frozen=True, slots=True)
class ProbeSpec:
    probe_id: str
    cell: int
    materializer_id: str
    loss_id: str
    target_schema: str
    mask_id: str
    support_id: str
    shuffle_id: str
    action_mapper_id: str
    required_atoms: tuple[str, ...]
    shuffled_twin: bool = False

    def canonical(self) -> dict[str, Any]:
        return {field.name: getattr(self, field.name) for field in fields(self)}


# The universal head must hold the complete factorized competing-risk plane:
# 24x4 horizontal cause logits, 24 horizontal clocks, 12 vertical clocks and
# 12x4 typed endpoint logits = 180 used coordinates.  Round to 192 without
# silently discarding any registered axis.
PADDED_OUTPUT_WIDTH = 192
E1_PROBE_FIT_BUDGET = 90
MAX_THROUGH_E2_PROBE_FIT_BUDGET = 98


@dataclass(frozen=True, slots=True)
class ProbeTarget:
    """Frozen candidate-aligned numeric target for a universal padded head."""

    probe_id: str
    state: CellAvailability
    values: np.ndarray
    coordinate_mask: np.ndarray
    coordinate_at_risk: np.ndarray
    coordinate_censor: np.ndarray
    validity_mask: np.ndarray
    at_risk_mask: np.ndarray
    censor_mask: np.ndarray
    fit_weight: np.ndarray
    group_id: np.ndarray
    group_size: np.ndarray
    output_width: int
    output_layout: tuple[str, ...]
    direction: int
    schema_sha256: str
    transform_provenance_sha256: str | None = None
    prediction_width: int | None = None
    prediction_layout: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        arrays = (
            self.values, self.coordinate_mask, self.coordinate_at_risk,
            self.coordinate_censor, self.validity_mask, self.at_risk_mask,
            self.censor_mask, self.fit_weight,
            self.group_id, self.group_size,
        )
        if any(np.asarray(value).dtype == object for value in arrays):
            raise AtlasRefusal("ProbeTarget cannot contain object dtype")
        values = np.asarray(self.values)
        if values.dtype.kind not in "biuf":
            raise AtlasRefusal("ProbeTarget values must be numeric")
        n = values.shape[0] if values.ndim == 2 else -1
        if values.shape != (n, PADDED_OUTPUT_WIDTH):
            raise AtlasRefusal("ProbeTarget values must use the universal padded layout")
        if any(np.asarray(value).shape != (n, PADDED_OUTPUT_WIDTH)
               for value in arrays[1:4]):
            raise AtlasRefusal("ProbeTarget coordinate masks must use padded layout")
        if not 1 <= int(self.output_width) <= PADDED_OUTPUT_WIDTH:
            raise AtlasRefusal("ProbeTarget output width is invalid")
        if len(self.output_layout) != self.output_width:
            raise AtlasRefusal("ProbeTarget output layout width differs")
        prediction_width = self.output_width if self.prediction_width is None else int(self.prediction_width)
        prediction_layout = self.output_layout if not self.prediction_layout else self.prediction_layout
        if not 1 <= prediction_width <= PADDED_OUTPUT_WIDTH:
            raise AtlasRefusal("ProbeTarget prediction width is invalid")
        if len(prediction_layout) != prediction_width:
            raise AtlasRefusal("ProbeTarget prediction layout width differs")
        object.__setattr__(self, "prediction_width", prediction_width)
        object.__setattr__(self, "prediction_layout", tuple(prediction_layout))
        for value in arrays[1:]:
            shape = np.asarray(value).shape
            if shape not in ((n,), (n, PADDED_OUTPUT_WIDTH)):
                raise AtlasRefusal("ProbeTarget masks/weights are misaligned")
        if any(np.asarray(value).dtype != np.bool_ for value in arrays[1:7]):
            raise AtlasRefusal("ProbeTarget validity/risk/censor masks must be boolean")
        if np.asarray(self.fit_weight).dtype.kind != "f" or np.any(self.fit_weight < 0):
            raise AtlasRefusal("ProbeTarget fit weights must be nonnegative floating point")
        if any(np.asarray(value).dtype.kind not in "iu" for value in arrays[8:]):
            raise AtlasRefusal("ProbeTarget group structure must be integer")
        if np.any(self.coordinate_mask & ~self.validity_mask[:, None]):
            raise AtlasRefusal("ProbeTarget coordinates cannot outlive row support")
        if np.any(self.coordinate_at_risk & ~self.coordinate_mask):
            raise AtlasRefusal("ProbeTarget at-risk coordinates require validity")
        if not np.all(np.isfinite(values)) or not np.all(np.isfinite(self.fit_weight)):
            raise AtlasRefusal("ProbeTarget contains non-finite numeric data")
        if (self.transform_provenance_sha256 is not None
                and (len(self.transform_provenance_sha256) != 64
                     or any(char not in "0123456789abcdef"
                            for char in self.transform_provenance_sha256))):
            raise AtlasRefusal("ProbeTarget fit provenance must be a sha256")
        expected = probe_target_schema_sha256(
            self.probe_id, self.output_width, self.output_layout, self.direction,
            self.transform_provenance_sha256, prediction_width, prediction_layout,
        )
        if self.schema_sha256 != expected:
            raise AtlasRefusal("ProbeTarget schema hash differs")
        for value in arrays:
            np.asarray(value).setflags(write=False)


def probe_target_schema_sha256(
    probe_id: str, output_width: int, output_layout: Sequence[str], direction: int,
    transform_provenance_sha256: str | None = None,
    prediction_width: int | None = None,
    prediction_layout: Sequence[str] | None = None,
) -> str:
    prediction_width = output_width if prediction_width is None else int(prediction_width)
    prediction_layout = output_layout if prediction_layout is None else prediction_layout
    return hashlib.sha256(json.dumps({
        "schema": "entry-v2-probe-target-v2", "probe_id": probe_id,
        "padded_width": PADDED_OUTPUT_WIDTH, "output_width": int(output_width),
        "output_layout": list(output_layout), "direction": int(direction),
        "prediction_width": prediction_width,
        "prediction_layout": list(prediction_layout),
        "transform_provenance_sha256": transform_provenance_sha256,
    }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class MaterializedAtlas:
    candidate_ids: tuple[str, ...]
    anchors: tuple[CandidateAnchor, ...]
    atoms: Mapping[str, Any]
    probes: tuple[ProbeSpec, ...]
    shuffled_probes: tuple[ProbeSpec, ...]
    shared_encoder_fits: tuple[str, str]
    receipt: Mapping[str, Any]

    @property
    def fit_budget(self) -> int:
        return len(self.probes) + len(self.shuffled_probes) + len(self.shared_encoder_fits)

    @property
    def max_through_e2_fit_budget(self) -> int:
        return MAX_THROUGH_E2_PROBE_FIT_BUDGET

    def materialize_probe(self, spec: ProbeSpec,
                          fit_context: Mapping[str, Any] | None = None) -> ProbeTarget:
        if spec not in self.probes and spec not in self.shuffled_probes:
            raise AtlasRefusal("probe is not registered for this atlas")
        # Local import is deliberate: the truth/type module must remain
        # importable before its numeric consumer modules.  Import-time
        # back-edges previously made ``import atlas_materializers`` fail.
        from .atlas_materializers import materialize_probe_target
        return materialize_probe_target(self, spec, fit_context)


def merge_candidate_truth_atlases(
    candidates: Sequence[CandidateAnchor],
    indexed_parts: Sequence[tuple[Sequence[int], MaterializedAtlas]],
) -> MaterializedAtlas:
    """Merge exact quality-key batches without changing candidate row order."""

    anchors = tuple(candidates); n = len(anchors)
    if not indexed_parts or n == 0:
        raise AtlasRefusal("candidate truth atlas merge is empty")
    filled = np.zeros(n, dtype=np.bool_)
    for positions, _atlas in indexed_parts:
        position = np.asarray(tuple(positions), dtype=np.int64)
        if (len(np.unique(position)) != len(position)
                or np.any(position < 0) or np.any(position >= n)
                or np.any(filled[position])):
            raise AtlasRefusal("candidate truth atlas merge positions overlap/out of range")
        filled[position] = True
    if not bool(filled.all()):
        raise AtlasRefusal("candidate truth atlas merge is incomplete")
    names = tuple(indexed_parts[0][1].atoms)
    merged: dict[str, Any] = {}
    for name in names:
        sample = indexed_parts[0][1].atoms[name]
        if isinstance(sample, np.ndarray):
            shape = (n, *sample.shape[1:])
            destination = np.empty(shape, dtype=sample.dtype)
            for positions, atlas in indexed_parts:
                position = np.asarray(tuple(positions), dtype=np.int64)
                source = np.asarray(atlas.atoms[name])
                if source.shape[0] != len(position):
                    raise AtlasRefusal("candidate truth atlas part is row-misaligned")
                destination[position] = source
            destination.setflags(write=False); merged[name] = destination
        else:
            destination: list[Any] = [None] * n
            for positions, atlas in indexed_parts:
                position = tuple(int(value) for value in positions)
                source = atlas.atoms[name]
                if len(source) != len(position):
                    raise AtlasRefusal("candidate truth atlas tuple part is row-misaligned")
                for row, value in zip(position, source):
                    destination[row] = value
            merged[name] = tuple(destination)
    if any(tuple(part.atoms) != names for _, part in indexed_parts):
        raise AtlasRefusal("candidate truth atlas merge is incomplete")
    component_receipts = [part.receipt["receipt_sha256"] for _, part in indexed_parts]
    event_counts = {int(part.receipt["event_count"]) for _, part in indexed_parts}
    if len(event_counts) != 1:
        raise AtlasRefusal("candidate truth atlas components differ in event count")
    body = {
        "schema": "entry-v2-candidate-quality-atlas-v1",
        "candidate_count": n,
        "candidate_ids": [anchor.candidate_id for anchor in anchors],
        "event_count": next(iter(event_counts)),
        "truth_quality_key_count": len(indexed_parts),
        "component_receipts": component_receipts,
        "component_positions": [list(map(int, positions))
                                for positions, _ in indexed_parts],
        "index_query_count": sum(int(part.receipt["index_query_count"])
                                 for _, part in indexed_parts),
        "index_query_work": sum(int(part.receipt["index_query_work"])
                                for _, part in indexed_parts),
        "candidate_suffix_rows_visited": sum(int(
            part.receipt["candidate_suffix_rows_visited"]
        ) for _, part in indexed_parts),
        "fit_budget": E1_PROBE_FIT_BUDGET,
        "e1_fit_budget": E1_PROBE_FIT_BUDGET,
        "max_through_e2_fit_budget": MAX_THROUGH_E2_PROBE_FIT_BUDGET,
    }
    body["receipt_sha256"] = hashlib.sha256(json.dumps(
        body, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    return MaterializedAtlas(
        tuple(anchor.candidate_id for anchor in anchors), anchors,
        MappingProxyType(merged), PROBE_REGISTRY, SHUFFLED_PROBES,
        ("SHARED_ENCODER_FIT_A", "SHARED_ENCODER_FIT_B"),
        MappingProxyType(body),
    )


class _RangeIndex:
    """One logarithmic min/max segment-tree family for extrema and first hit."""

    def __init__(self, values: np.ndarray) -> None:
        self.values = np.asarray(values, dtype=np.int64)
        self.query_count = 0
        self.node_visits = 0
        n = len(self.values)
        size = 1
        while size < max(n, 1):
            size <<= 1
        self.size = size
        self.max_tree = np.full(2 * size, np.iinfo(np.int64).min, np.int64)
        self.min_tree = np.full(2 * size, np.iinfo(np.int64).max, np.int64)
        self.max_tree[size:size + n] = self.values
        self.min_tree[size:size + n] = self.values
        # Build one complete level at a time.  The former node-at-a-time
        # Python loop performed the same reductions over millions of nodes
        # for every phase-quality index.  Keeping the exact heap layout makes
        # extrema/first traversal, node-visit accounting, and all receipts
        # byte-identical while NumPy performs each level in native code.
        level = size
        while level > 1:
            parent = level // 2
            self.max_tree[parent:level] = np.maximum(
                self.max_tree[level:2 * level:2],
                self.max_tree[level + 1:2 * level:2],
            )
            self.min_tree[parent:level] = np.minimum(
                self.min_tree[level:2 * level:2],
                self.min_tree[level + 1:2 * level:2],
            )
            level = parent

    def extrema(self, left: int, right: int) -> tuple[int, int]:
        self.query_count += 1
        if not 0 <= left < right <= len(self.values):
            raise AtlasRefusal("empty/out-of-range RMQ")
        lo, hi = left + self.size, right + self.size
        maximum = np.iinfo(np.int64).min
        minimum = np.iinfo(np.int64).max
        while lo < hi:
            if lo & 1:
                maximum = max(maximum, int(self.max_tree[lo]))
                minimum = min(minimum, int(self.min_tree[lo]))
                self.node_visits += 1
                lo += 1
            if hi & 1:
                hi -= 1
                maximum = max(maximum, int(self.max_tree[hi]))
                minimum = min(minimum, int(self.min_tree[hi]))
                self.node_visits += 1
            lo //= 2
            hi //= 2
        return int(maximum), int(minimum)

    def first(self, left: int, right: int, threshold: int, above: bool) -> int | None:
        self.query_count += 1
        tree = self.max_tree if above else self.min_tree
        # Iterative left-first DFS is exactly the former recursive traversal:
        # right is pushed first, so left is visited first, and a qualifying
        # leaf returns before its right siblings are touched.  Besides
        # avoiding one closure and recursive Python frame per visited node,
        # this preserves node_visits byte-for-byte in atlas receipts.
        pending = [(1, 0, self.size)]
        while pending:
            node, lo, hi = pending.pop()
            self.node_visits += 1
            value = int(tree[node])
            if (hi <= left or right <= lo
                    or (value < threshold if above else value > threshold)):
                continue
            if hi - lo == 1:
                return lo if lo < len(self.values) else None
            mid = (lo + hi) // 2
            pending.append((node * 2 + 1, mid, hi))
            pending.append((node * 2, lo, mid))
        return None


class _WeightedRangeIndex:
    """Compact weighted wavelet matrix for interval threshold sums."""

    def __init__(self, values: np.ndarray, weights: np.ndarray) -> None:
        values = np.asarray(values, dtype=np.int64)
        weights = np.asarray(weights, dtype=np.float64)
        if values.ndim != 1 or weights.shape != values.shape:
            raise AtlasRefusal("weighted range columns are misaligned")
        self.n = len(values)
        self.query_count = 0
        self.level_visits = 0
        self.unique = np.unique(values)
        ranks = np.searchsorted(self.unique, values).astype(np.uint32, copy=False)
        self.bits = max(1, int(max(0, len(self.unique) - 1)).bit_length())
        self.levels: list[tuple[np.ndarray, np.ndarray, int]] = []
        current_weights = weights.copy()
        for shift in range(self.bits - 1, -1, -1):
            zero = ((ranks >> shift) & 1) == 0
            prefix_count = np.empty(self.n + 1, dtype=np.uint32)
            prefix_count[0] = 0
            np.cumsum(zero, dtype=np.uint32, out=prefix_count[1:])
            prefix_weight = np.empty(self.n + 1, dtype=np.float64)
            prefix_weight[0] = 0.0
            np.cumsum(np.where(zero, current_weights, 0.0),
                      dtype=np.float64, out=prefix_weight[1:])
            zero_count = int(prefix_count[-1])
            self.levels.append((prefix_count, prefix_weight, zero_count))
            order = np.r_[np.flatnonzero(zero), np.flatnonzero(~zero)]
            ranks = ranks[order]
            current_weights = current_weights[order]
        self.total_prefix = np.r_[0.0, np.cumsum(weights, dtype=np.float64)]

    def weight_le(self, left: int, right: int, threshold: int) -> float:
        self.query_count += 1
        if not 0 <= left <= right <= self.n:
            raise AtlasRefusal("weighted range query is out of bounds")
        rank_limit = int(np.searchsorted(self.unique, threshold, side="right"))
        if rank_limit <= 0 or left == right:
            return 0.0
        if rank_limit >= len(self.unique):
            return float(self.total_prefix[right] - self.total_prefix[left])
        lo, hi = int(left), int(right)
        total = 0.0
        for level, (prefix_count, prefix_weight, zero_count) in enumerate(self.levels):
            self.level_visits += 1
            shift = self.bits - 1 - level
            zero_lo, zero_hi = int(prefix_count[lo]), int(prefix_count[hi])
            if (rank_limit >> shift) & 1:
                total += float(prefix_weight[hi] - prefix_weight[lo])
                lo = zero_count + (lo - zero_lo)
                hi = zero_count + (hi - zero_hi)
            else:
                lo, hi = zero_lo, zero_hi
        return total


def _ceil_div(numerator: int, denominator: int) -> int:
    return -((-int(numerator)) // int(denominator))


def _mid_condition(anchor: CandidateAnchor, net_threshold: int,
                   at_least: bool) -> tuple[int, bool]:
    """Return exact integer-mid threshold and whether qualification is >=."""

    rhs = int(net_threshold) + int(anchor.frozen_cost_units)
    multiplier = int(anchor.multiplier)
    entry = int(anchor.entry_mid2)
    if at_least:
        if anchor.side > 0:
            return entry + _ceil_div(rhs, multiplier), True
        return entry + (-(rhs) // multiplier), False
    if anchor.side > 0:
        return entry + (rhs // multiplier), False
    return entry + _ceil_div(-rhs, multiplier), True


def _column(value: Any, dtype: Any, n: int | None = None) -> np.ndarray:
    out = np.ascontiguousarray(value, dtype=dtype)
    if out.ndim != 1 or (n is not None and len(out) != n):
        raise AtlasRefusal("session truth columns must be aligned one-dimensional arrays")
    out.setflags(write=False)
    return out


class SessionTruthIndex:
    """One authorized session indexed once; candidates are materialized in batch."""

    REQUIRED_COLUMNS = (
        "ts_recv_ns", "source_ordinal", "trusted_message", "trusted_economic",
        "sane_bbo",
        "generation", "mid2", "action", "side", "flags", "depth",
        "missing_mask", "spread_mask", "price", "bid_px", "ask_px", "size",
        "bid_size", "ask_size", "bid_count", "ask_count", "ts_in_delta",
        "receive_session_sec", "sequence", "ts_event_ns",
    )
    OPTIONAL_PHASE_COLUMNS = (
        "phase_open_ts_ns", "phase_close_ts_ns", "phase_sane_ceiling_units",
    )

    def __init__(self, **columns: Any) -> None:
        required = set(self.REQUIRED_COLUMNS)
        optional = set(self.OPTIONAL_PHASE_COLUMNS)
        provided_optional = set(columns) - required
        if not required.issubset(columns) or provided_optional not in (set(), optional):
            raise AtlasRefusal("session truth index requires an authorized whole column set")
        phase_indexed = provided_optional == optional
        ts = _column(columns["ts_recv_ns"], np.uint64)
        n = len(ts)
        dtype = {
            "source_ordinal": np.uint32, "trusted_message": np.bool_,
            "trusted_economic": np.bool_,
            "sane_bbo": np.bool_, "generation": np.int64, "mid2": np.int64,
            "action": np.int16, "side": np.int8, "flags": np.uint32,
            "depth": np.int16, "missing_mask": np.uint32,
            "spread_mask": np.uint32, "price": np.int64,
            "bid_px": np.int64, "ask_px": np.int64, "size": np.int64,
            "bid_size": np.int64, "ask_size": np.int64,
            "bid_count": np.int64, "ask_count": np.int64,
            "ts_in_delta": np.int64, "receive_session_sec": np.int64,
            "sequence": np.int64, "ts_event_ns": np.int64,
            "phase_open_ts_ns": np.int64, "phase_close_ts_ns": np.int64,
            "phase_sane_ceiling_units": np.int64,
        }
        authorized_columns = self.REQUIRED_COLUMNS + (
            self.OPTIONAL_PHASE_COLUMNS if phase_indexed else ()
        )
        self.columns = MappingProxyType({
            "ts_recv_ns": ts,
            **{name: _column(columns[name], dtype[name], n)
               for name in authorized_columns if name != "ts_recv_ns"},
        })
        if n and int(ts[-1]) >= DEVELOPMENT_CUTOFF_NS:
            raise AtlasRefusal("post-development/H2 rows cannot be indexed")
        ordinal = self.columns["source_ordinal"]
        if n > 1 and np.any(
            (ts[1:] < ts[:-1])
            | ((ts[1:] == ts[:-1]) & (ordinal[1:] < ordinal[:-1]))
        ):
            raise AtlasRefusal("terminal keys must be ordered by (receive, source ordinal)")
        if n > 1 and np.any(
            (ts[1:] == ts[:-1]) & (ordinal[1:] == ordinal[:-1])
        ):
            raise AtlasRefusal("terminal (receive, source ordinal) keys must be unique")
        self._phase_ranges: Mapping[tuple[int, int, int], tuple[int, int, int, int,
                                                                    int, int]] | None
        self._phase_ranges = None
        if phase_indexed:
            phase_open = self.columns["phase_open_ts_ns"]
            phase_close = self.columns["phase_close_ts_ns"]
            phase_ceiling = self.columns["phase_sane_ceiling_units"]
            active = phase_ceiling > 0
            if np.any((~active) & ((phase_open != 0) | (phase_close != 0))):
                raise AtlasRefusal("unowned truth rows carry phase metadata")
            if np.any(active & (
                (phase_open >= phase_close)
                | (phase_open > ts.astype(np.int64))
                | (phase_close < ts.astype(np.int64))
            )):
                raise AtlasRefusal("truth row falls outside its inclusive phase owner")
        economic = self.columns["trusted_economic"] & self.columns["sane_bbo"]
        self.economic_index = np.flatnonzero(economic).astype(np.int64)
        self.economic_ts = ts[self.economic_index]
        self.economic_ord = self.columns["source_ordinal"][self.economic_index]
        self.economic_mid2 = self.columns["mid2"][self.economic_index]
        self.trusted_index = np.flatnonzero(
            self.columns["trusted_message"]
        ).astype(np.int64)
        self.trusted_ts = ts[self.trusted_index]
        self.trusted_ord = self.columns["source_ordinal"][self.trusted_index]
        if phase_indexed:
            ranges: dict[tuple[int, int, int], tuple[int, int, int, int, int, int]] = {}
            if n:
                phase_open = self.columns["phase_open_ts_ns"]
                phase_close = self.columns["phase_close_ts_ns"]
                phase_ceiling = self.columns["phase_sane_ceiling_units"]
                active = phase_ceiling > 0
                changes = np.flatnonzero(
                    (active[1:] != active[:-1])
                    | (phase_open[1:] != phase_open[:-1])
                    | (phase_close[1:] != phase_close[:-1])
                    | (phase_ceiling[1:] != phase_ceiling[:-1])
                ).astype(np.int64) + 1
                starts = np.r_[0, changes]
                stops = np.r_[changes, n]
                for raw_start, raw_stop in zip(starts, stops):
                    raw_start, raw_stop = int(raw_start), int(raw_stop)
                    if not active[raw_start]:
                        continue
                    key = (int(phase_open[raw_start]), int(phase_close[raw_start]),
                           int(phase_ceiling[raw_start]))
                    if key in ranges:
                        raise AtlasRefusal("phase owner rows must form one contiguous range")
                    ranges[key] = (
                        raw_start, raw_stop,
                        int(np.searchsorted(self.economic_index, raw_start, side="left")),
                        int(np.searchsorted(self.economic_index, raw_stop, side="left")),
                        int(np.searchsorted(self.trusted_index, raw_start, side="left")),
                        int(np.searchsorted(self.trusted_index, raw_stop, side="left")),
                    )
            self._phase_ranges = MappingProxyType(ranges)
        for value in (self.economic_index, self.economic_ts, self.economic_ord,
                      self.economic_mid2, self.trusted_index, self.trusted_ts,
                      self.trusted_ord):
            value.setflags(write=False)
        self._rmq = _RangeIndex(self.economic_mid2)
        generation = self.columns["generation"]
        changes = np.flatnonzero(generation[1:] != generation[:-1]).astype(np.int64) + 1
        positions = np.arange(n, dtype=np.int64)
        lookup = np.searchsorted(changes, positions, side="right")
        self._next_generation_change = np.full(n, n, dtype=np.int64)
        present = lookup < len(changes)
        self._next_generation_change[present] = changes[lookup[present]]
        self._next_generation_change.setflags(write=False)
        t = ((self.economic_ts - self.economic_ts[0]).astype(np.float64) / 1e9
             if len(self.economic_ts) else np.empty(0, np.float64))
        y = self.economic_mid2.astype(np.float64)
        dt = np.diff(np.r_[t, t[-1] if len(t) else 0.0]) if len(t) else np.empty(0)
        self._prefix = MappingProxyType({
            "y": np.r_[0.0, np.cumsum(y)],
            "y2": np.r_[0.0, np.cumsum(y * y)],
            "t": np.r_[0.0, np.cumsum(t)],
            "t2": np.r_[0.0, np.cumsum(t * t)],
            "ty": np.r_[0.0, np.cumsum(t * y)],
            "area_y": np.r_[0.0, np.cumsum(y * dt)],
            "duration": np.r_[0.0, np.cumsum(dt)],
        })
        weights = np.r_[np.diff(t), 0.0] if len(t) else np.empty(0)
        self._occupation = _WeightedRangeIndex(self.economic_mid2, weights)

    @property
    def query_work(self) -> int:
        return int(self._rmq.node_visits + self._occupation.level_visits)

    @property
    def suffix_row_visits(self) -> int:
        """Direct candidate-by-suffix rows visited (the indexed path visits none)."""
        return 0

    @staticmethod
    def pnl_units(anchor: CandidateAnchor, mid2: int) -> int:
        return int(anchor.side) * (int(mid2) - int(anchor.entry_mid2)) * int(
            anchor.multiplier
        ) - int(anchor.frozen_cost_units)

    @staticmethod
    def _lex_search(ts: np.ndarray, ordinals: np.ndarray, ts_ns: int,
                    ordinal: int, side: str) -> int:
        begin = int(np.searchsorted(ts, np.uint64(ts_ns), side="left"))
        end = int(np.searchsorted(ts, np.uint64(ts_ns), side="right"))
        if begin == end:
            return begin
        return begin + int(np.searchsorted(
            ordinals[begin:end], np.uint32(ordinal), side=side
        ))

    def _key_search(self, ts_ns: int, ordinal: int, side: str) -> int:
        return self._lex_search(self.economic_ts, self.economic_ord,
                                ts_ns, ordinal, side)

    def _trusted_key_search(self, ts_ns: int, ordinal: int, side: str) -> int:
        return self._lex_search(self.trusted_ts, self.trusted_ord,
                                ts_ns, ordinal, side)

    def _phase_range(self, anchor: CandidateAnchor) -> tuple[int, int, int, int, int, int]:
        has_anchor_phase = (anchor.phase_open_ts_ns is not None
                            and anchor.sane_ceiling_units is not None)
        if self._phase_ranges is None:
            if has_anchor_phase:
                raise AtlasRefusal("candidate phase query requires an indexed owner plane")
            n = len(self.columns["ts_recv_ns"])
            return 0, n, 0, len(self.economic_index), 0, len(self.trusted_index)
        if not has_anchor_phase:
            raise AtlasRefusal("indexed owner plane requires candidate phase query metadata")
        key = (int(anchor.phase_open_ts_ns), int(anchor.phase_close_ts_ns),
               int(anchor.sane_ceiling_units))
        found = self._phase_ranges.get(key)
        if found is not None:
            return found
        raw = int(np.searchsorted(
            self.columns["ts_recv_ns"], np.uint64(anchor.phase_open_ts_ns), side="left"
        ))
        economic = int(np.searchsorted(self.economic_index, raw, side="left"))
        trusted = int(np.searchsorted(self.trusted_index, raw, side="left"))
        return raw, raw, economic, economic, trusted, trusted

    def _bounds(
        self,
        anchor: CandidateAnchor,
        *,
        phase_range: tuple[int, int, int, int, int, int] | None = None,
        economic_left: int | None = None,
        raw_left_hint: int | None = None,
    ) -> tuple[int, int, BoundaryReason, int, int]:
        if anchor.decision_ts_ns >= DEVELOPMENT_CUTOFF_NS:
            raise AtlasRefusal("candidate opens after the development boundary")
        (phase_raw_left, phase_raw_right, phase_left, phase_right,
         _, _) = (self._phase_range(anchor) if phase_range is None else phase_range)
        left = min(phase_right, max(
            phase_left,
            (self._key_search(anchor.decision_ts_ns, 0, "left")
             if economic_left is None else int(economic_left)),
        ))
        if (anchor.canonical is not None
                and anchor.canonical.status is CellAvailability.NO_SANE_SUFFIX):
            return (left, left, BoundaryReason.NO_SANE_SUFFIX,
                    anchor.canonical.exit_ts_recv_ns,
                    anchor.canonical.exit_source_ordinal)
        candidates = [(DEVELOPMENT_CUTOFF_NS, np.iinfo(np.uint32).max,
                       BoundaryReason.DEVELOPMENT)]
        if anchor.canonical is not None:
            candidates.append((anchor.canonical.exit_ts_recv_ns,
                               anchor.canonical.exit_source_ordinal,
                               anchor.canonical.exit_reason))
        elif anchor.economic_exit_ts_ns is not None:
            candidates.append((anchor.economic_exit_ts_ns,
                               anchor.economic_exit_source_ordinal,
                               BoundaryReason.ECONOMIC_EXIT))
        else:
            candidates.append((anchor.phase_close_ts_ns,
                               np.iinfo(np.uint32).max, BoundaryReason.PHASE))
        if anchor.source_censor_ts_ns is not None:
            candidates.append((anchor.source_censor_ts_ns, anchor.source_censor_ordinal,
                               BoundaryReason.SOURCE))
        raw_left = (
            int(np.searchsorted(self.columns["ts_recv_ns"], anchor.decision_ts_ns,
                                side="left"))
            if raw_left_hint is None else int(raw_left_hint)
        )
        raw_left = min(phase_raw_right, max(phase_raw_left, raw_left))
        if raw_left < phase_raw_right:
            if self.columns["generation"][raw_left] != anchor.generation:
                i = raw_left
            else:
                i = int(self._next_generation_change[raw_left])
            if i < phase_raw_right:
                candidates.append((int(self.columns["ts_recv_ns"][i]),
                                   int(self.columns["source_ordinal"][i]),
                                   BoundaryReason.GENERATION))
        priority = {
            BoundaryReason.WALL: 0, BoundaryReason.ECONOMIC_EXIT: 1,
            BoundaryReason.PHASE: 2, BoundaryReason.SOURCE: 3,
            BoundaryReason.GENERATION: 4, BoundaryReason.DEVELOPMENT: 5,
        }
        terminal_ts, terminal_ord, reason = min(
            candidates, key=lambda row: (int(row[0]), int(row[1]), priority[row[2]])
        )
        include_terminal = reason in (
            BoundaryReason.ECONOMIC_EXIT, BoundaryReason.PHASE, BoundaryReason.WALL
        )
        right = self._key_search(terminal_ts, terminal_ord,
                                 "right" if include_terminal else "left")
        right = min(phase_right, max(phase_left, right))
        if right <= left:
            return left, right, BoundaryReason.NO_SANE_SUFFIX, terminal_ts, terminal_ord
        wall_threshold_mid2, wall_above = _mid_condition(anchor, -WALL_UNITS, False)
        wall = self._rmq.first(left, right, wall_threshold_mid2, above=wall_above)
        if wall is not None and self.pnl_units(anchor, int(self.economic_mid2[wall])) <= -WALL_UNITS:
            wall_key = (int(self.economic_ts[wall]), int(self.economic_ord[wall]))
            if wall_key <= (terminal_ts, terminal_ord):
                right, reason, terminal_ts, terminal_ord = (
                    wall + 1, BoundaryReason.WALL, wall_key[0], wall_key[1]
                )
        return left, right, reason, int(terminal_ts), int(terminal_ord)

    def _trend(
        self,
        anchor: CandidateAnchor,
        left: int,
        right: int,
        *,
        stop_hints: Sequence[int] | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for axis, seconds in enumerate(TREND_SECONDS):
            stop = min(right, (
                int(np.searchsorted(
                    self.economic_ts,
                    anchor.decision_ts_ns + seconds * 1_000_000_000,
                    side="right",
                ))
                if stop_hints is None else int(stop_hints[axis])
            ))
            count = stop - left
            if count < 2:
                result[f"{seconds}s"] = {"slope_units_per_sec": None, "t_stat": None,
                                         "sign": 0, "count": count}
                continue
            sums = {name: float(value[stop] - value[left])
                    for name, value in self._prefix.items()
                    if name in {"y", "y2", "t", "t2", "ty"}}
            denom = count * sums["t2"] - sums["t"] ** 2
            raw_slope = 0.0 if denom == 0 else (
                count * sums["ty"] - sums["t"] * sums["y"]
            ) / denom
            intercept = (sums["y"] - raw_slope * sums["t"]) / count
            sse = max(0.0, sums["y2"] - intercept * sums["y"]
                      - raw_slope * sums["ty"])
            se = math.sqrt(sse / max(1, count - 2) * count / max(denom, 1e-30))
            slope = raw_slope * anchor.side * anchor.multiplier
            result[f"{seconds}s"] = {
                "slope_units_per_sec": slope,
                "t_stat": None if se == 0 else slope / (se * anchor.multiplier),
                "sign": int(np.sign(slope)), "count": count,
            }
        return result

    def _mixed_targets(self, anchor: CandidateAnchor, terminal_ts: int,
                       terminal_ord: int, economic: bool,
                       censor_reason: BoundaryReason, *,
                       phase_range: tuple[int, int, int, int, int, int] | None = None,
                       trusted_left_hint: int | None = None,
                       count_stop_hints: Sequence[int] | None = None,
                       ) -> dict[str, Any]:
        _, _, _, _, phase_trusted_left, phase_trusted_right = (
            self._phase_range(anchor) if phase_range is None else phase_range
        )
        trusted_left = min(phase_trusted_right, max(
            phase_trusted_left,
            (self._trusted_key_search(anchor.decision_ts_ns, 0, "left")
             if trusted_left_hint is None else int(trusted_left_hint)),
        ))
        trusted_right = min(phase_trusted_right, max(
            phase_trusted_left,
            self._trusted_key_search(
                terminal_ts, terminal_ord, "right" if economic else "left"
            ),
        ))
        next_sequence = (None if trusted_left >= trusted_right else int(
            self.columns["sequence"][self.trusted_index[trusted_left]]
        ))
        prior_sequence = (None if trusted_left == phase_trusted_left else int(
            self.columns["sequence"][self.trusted_index[trusted_left - 1]]
        ))
        return {
            "next_event": None if trusted_left >= trusted_right else {
                name: int(self.columns[name][self.trusted_index[trusted_left]])
                for name in (
                    "ts_recv_ns", "ts_event_ns", "sequence", "action", "side",
                    "flags", "depth", "missing_mask", "spread_mask", "price",
                    "bid_px", "ask_px", "size", "bid_size", "ask_size",
                    "bid_count", "ask_count", "ts_in_delta", "receive_session_sec",
                )
            } | ({
                "receive_gap_ns": int(self.columns["ts_recv_ns"][
                    self.trusted_index[trusted_left]]) - anchor.decision_ts_ns,
                "sequence_gap": (0 if prior_sequence is None else
                                 int(next_sequence - prior_sequence)),
                "sequence_gap_valid": prior_sequence is not None,
                "latency_ns": int(self.columns["ts_recv_ns"][
                    self.trusted_index[trusted_left]]) - int(self.columns["ts_event_ns"][
                    self.trusted_index[trusted_left]]),
            } if trusted_left < trusted_right else {}),
            "next_event_valid": trusted_left < trusted_right,
            "counts": {f"{seconds}s": max(
                0, min(trusted_right, (
                    int(np.searchsorted(
                        self.trusted_ts,
                        anchor.decision_ts_ns + seconds * 1_000_000_000,
                        side="right",
                    ))
                    if count_stop_hints is None
                    else int(count_stop_hints[axis])
                )) - trusted_left
            ) for axis, seconds in enumerate(HORIZON_SECONDS)},
            "count_valid": {f"{seconds}s": bool(
                anchor.decision_ts_ns + seconds * 1_000_000_000 < terminal_ts
                or economic
            ) for seconds in HORIZON_SECONDS},
            "censor_reason": None if economic else censor_reason,
        }

    def materialize(self, candidates: Sequence[CandidateAnchor]) -> MaterializedAtlas:
        anchors = tuple(candidates)
        ids = tuple(row.candidate_id for row in anchors)
        if len(ids) != len(set(ids)):
            raise AtlasRefusal("duplicate candidate id")
        groups: dict[tuple[str, int, int], list[CandidateAnchor]] = {}
        for row in anchors:
            groups.setdefault((row.asset, int(row.trading_day),
                               int(row.decision_ts_ns)), []).append(row)
        if any(len(rows) > 1 and (
            any(not row.exact_time_group_id for row in rows)
            or len({row.exact_time_group_id for row in rows}) != 1
        ) for rows in groups.values()):
            raise AtlasRefusal("exact-time candidates require one explicit group id")

        # Every scalar candidate previously repeated the same binary searches
        # over immutable session clocks for ten endpoint horizons, five trend
        # horizons, mixed-event counts, and its decision/phase boundary.
        # Search all candidate keys in one native NumPy call per clock/axis;
        # candidate-specific censor/wall/RMQ semantics remain in the exact
        # scalar state machine below.
        phase_ranges = tuple(self._phase_range(anchor) for anchor in anchors)
        decision_keys = np.asarray(
            [anchor.decision_ts_ns for anchor in anchors], dtype=np.uint64,
        )
        phase_close_keys = np.asarray(
            [anchor.phase_close_ts_ns for anchor in anchors], dtype=np.uint64,
        )
        horizon_offsets = np.asarray(HORIZON_SECONDS, dtype=np.uint64) * np.uint64(
            1_000_000_000
        )
        trend_offsets = np.asarray(TREND_SECONDS, dtype=np.uint64) * np.uint64(
            1_000_000_000
        )
        horizon_keys = decision_keys[:, None] + horizon_offsets[None, :]
        trend_keys = decision_keys[:, None] + trend_offsets[None, :]
        economic_decision_left = np.searchsorted(
            self.economic_ts, decision_keys, side="left",
        )
        raw_decision_left = np.searchsorted(
            self.columns["ts_recv_ns"], decision_keys, side="left",
        )
        trusted_decision_left = np.searchsorted(
            self.trusted_ts, decision_keys, side="left",
        )
        endpoint_left = np.searchsorted(
            self.economic_ts, horizon_keys, side="left",
        )
        trend_right = np.searchsorted(
            self.economic_ts, trend_keys, side="right",
        )
        mixed_count_right = np.searchsorted(
            self.trusted_ts, horizon_keys, side="right",
        )
        phase_endpoint_left = np.searchsorted(
            self.economic_ts, phase_close_keys, side="left",
        )
        bounds = tuple(
            self._bounds(
                anchor, phase_range=phase_ranges[row_index],
                economic_left=int(economic_decision_left[row_index]),
                raw_left_hint=int(raw_decision_left[row_index]),
            )
            for row_index, anchor in enumerate(anchors)
        )

        atoms: dict[str, list[Any]] = {name: [] for name in (
            "availability", "boundary_reason", "terminal_key", "final_units",
            "wall_hit", "mfe_units", "mae_units", "time_to_mfe_ns",
            "time_to_mae_ns", "fixed_endpoints", "trajectory", "rung_touches",
            "mixed_targets", "trends", "reversal_reclaim", "occupation",
            "barriers", "action_loss_mask", "take_target", "exact_time_group_id",
            "now_wait_pass_regret_units", "shadow_marginal_regret_units",
        )}
        for row_index, anchor in enumerate(anchors):
            left, right, reason, terminal_ts, terminal_ord = bounds[row_index]
            if right <= left:
                mixed_economic = bool(
                    (anchor.canonical is not None and
                     anchor.canonical.status is CellAvailability.MATERIALIZED)
                    or anchor.economic_exit_ts_ns is not None
                    or terminal_ts == anchor.phase_close_ts_ns
                )
                row = {name: None for name in atoms}
                row.update({"availability": CellAvailability.NO_SANE_SUFFIX,
                            "boundary_reason": reason,
                            "terminal_key": (terminal_ts, terminal_ord),
                            "wall_hit": False,
                            "action_loss_mask": anchor.action_loss_mask,
                            "take_target": anchor.take_target,
                            "now_wait_pass_regret_units":
                                anchor.now_wait_pass_regret_units,
                            "shadow_marginal_regret_units":
                                anchor.shadow_marginal_regret_units,
                            "exact_time_group_id": (
                                None if anchor.exact_time_group_id is None else
                                (anchor.asset, int(anchor.trading_day),
                                 int(anchor.decision_ts_ns), anchor.exact_time_group_id)
                            ),
                            "mixed_targets": self._mixed_targets(
                                anchor, terminal_ts, terminal_ord,
                                mixed_economic, reason,
                                phase_range=phase_ranges[row_index],
                                trusted_left_hint=int(
                                    trusted_decision_left[row_index]
                                ),
                                count_stop_hints=mixed_count_right[row_index],
                            ),
                            })
                for name in atoms:
                    atoms[name].append(row[name])
                continue
            max_mid2, min_mid2 = self._rmq.extrema(left, right)
            favorable_mid2 = max_mid2 if anchor.side > 0 else min_mid2
            adverse_mid2 = min_mid2 if anchor.side > 0 else max_mid2
            max_net = self.pnl_units(anchor, favorable_mid2)
            min_net = self.pnl_units(anchor, adverse_mid2)
            mfe = max(0, max_net)
            mae = max(0, -min_net)
            final = self.pnl_units(anchor, int(self.economic_mid2[right - 1]))
            mfe_i = (None if mfe == 0 else
                     self._rmq.first(left, right, favorable_mid2, above=anchor.side > 0))
            mae_i = (None if mae == 0 else
                     self._rmq.first(left, right, adverse_mid2, above=anchor.side < 0))
            economic = reason in (
                BoundaryReason.ECONOMIC_EXIT, BoundaryReason.WALL, BoundaryReason.PHASE
            )
            endpoints: dict[str, Any] = {}
            trajectory: list[int | None] = []
            for axis, seconds in enumerate(HORIZON_SECONDS):
                index = max(left, int(endpoint_left[row_index, axis]))
                if index < right:
                    value, status = self.pnl_units(anchor, int(self.economic_mid2[index])), EndpointStatus.OBSERVED
                elif economic:
                    value, status = final, EndpointStatus.CARRIED_FORWARD
                else:
                    value, status = None, EndpointStatus.RIGHT_CENSORED
                endpoints[f"{seconds}s"] = {"value_units": value, "status": status}
                trajectory.append(value)
            endpoints["FINAL"] = {
                "value_units": final if economic else None,
                "status": EndpointStatus.OBSERVED if economic
                else EndpointStatus.RIGHT_CENSORED,
            }
            phase_index = max(left, int(phase_endpoint_left[row_index]))
            if phase_index < right:
                phase_value, phase_status = (
                    self.pnl_units(anchor, int(self.economic_mid2[phase_index])),
                    EndpointStatus.OBSERVED,
                )
            elif economic:
                phase_value, phase_status = final, EndpointStatus.CARRIED_FORWARD
            else:
                phase_value, phase_status = None, EndpointStatus.RIGHT_CENSORED
            endpoints["PHASE"] = {
                "value_units": phase_value, "status": phase_status,
            }
            trajectory.extend((phase_value, endpoints["FINAL"]["value_units"]))
            dollar_rungs = (
                *(value * PNL_UNITS_PER_USD for value in FAVORABLE_DOLLAR_RUNGS),
                *(-value * PNL_UNITS_PER_USD for value in ADVERSE_DOLLAR_RUNGS),
            )
            scale = ((_ceil_div(anchor.sigma_prior_units, 2),
                      int(anchor.sigma_prior_units),
                      int(anchor.sigma_prior_units) * 2)
                     if anchor.sigma_prior_units else ())
            touches: list[dict[str, Any]] = []
            rung_axis: tuple[int | None, ...] = (
                tuple(dollar_rungs) +
                (scale + tuple(-value for value in scale)
                 if scale else (None,) * (2 * len(PRIOR_SCALE_RUNGS)))
            )
            for threshold in rung_axis:
                if threshold is None:
                    touches.append({"threshold_units": None,
                                    "state": PassageState.NOT_AT_RISK,
                                    "event_index": None, "elapsed_ns": None})
                    continue
                favorable = threshold > 0
                mid_threshold, above = _mid_condition(
                    anchor, threshold, at_least=favorable
                )
                hit = self._rmq.first(left, right, mid_threshold, above=above)
                touches.append({
                    "threshold_units": threshold,
                    "state": (PassageState.ATTAINED if hit is not None
                              else PassageState.NOT_ATTAINED if economic
                              else PassageState.CENSORED),
                    "event_index": hit,
                    "elapsed_ns": None if hit is None else int(self.economic_ts[hit]) - anchor.decision_ts_ns,
                })
            mixed = self._mixed_targets(
                anchor, terminal_ts, terminal_ord, economic, reason,
                phase_range=phase_ranges[row_index],
                trusted_left_hint=int(trusted_decision_left[row_index]),
                count_stop_hints=mixed_count_right[row_index],
            )
            duration_sec = max(0.0, (terminal_ts - anchor.decision_ts_ns) / 1e9)
            y_area = float(
                self._prefix["area_y"][right - 1] - self._prefix["area_y"][left]
            )
            edge_covered = float(
                self._prefix["duration"][right - 1] - self._prefix["duration"][left]
            )
            tail = max(0.0, (terminal_ts - int(self.economic_ts[right - 1])) / 1e9)
            prelude = max(0.0, (int(self.economic_ts[left]) - anchor.decision_ts_ns) / 1e9)
            y_area += float(self.economic_mid2[right - 1]) * tail
            covered = edge_covered + tail + prelude
            economic_covered = edge_covered + tail
            area_units = (anchor.side * anchor.multiplier *
                          (y_area - anchor.entry_mid2 * economic_covered)
                          - anchor.frozen_cost_units * (economic_covered + prelude))
            interval_right = max(left, right - 1)
            interval_weight = edge_covered
            if anchor.side > 0:
                positive_cut = anchor.entry_mid2 + anchor.frozen_cost_units // anchor.multiplier
                negative_cut = anchor.entry_mid2 + _ceil_div(
                    anchor.frozen_cost_units, anchor.multiplier
                ) - 1
                adverse = self._occupation.weight_le(left, interval_right, negative_cut)
                favorable = interval_weight - self._occupation.weight_le(
                    left, interval_right, positive_cut
                )
            else:
                favorable_cut = anchor.entry_mid2 - (
                    anchor.frozen_cost_units // anchor.multiplier
                ) - 1
                adverse_cut = anchor.entry_mid2 - _ceil_div(
                    anchor.frozen_cost_units, anchor.multiplier
                ) + 1
                favorable = self._occupation.weight_le(left, interval_right, favorable_cut)
                adverse = interval_weight - self._occupation.weight_le(
                    left, interval_right, adverse_cut - 1
                )
            tail_net = self.pnl_units(anchor, int(self.economic_mid2[right - 1]))
            favorable += tail if tail_net > 0 else 0.0
            adverse += tail if tail_net < 0 else 0.0
            initial_net = -anchor.frozen_cost_units
            favorable += prelude if initial_net > 0 else 0.0
            adverse += prelude if initial_net < 0 else 0.0
            flat = max(0.0, covered - favorable - adverse)
            occupation = {"duration_seconds": duration_sec, "covered_seconds": covered,
                          "signed_area_units_seconds": area_units,
                          "favorable_seconds": favorable,
                          "adverse_seconds": adverse,
                          "flat_seconds": flat,
                          "underwater_seconds": adverse,
                          "terminal_state": int(np.sign(final))}
            zero_mid, zero_above = _mid_condition(anchor, 0, False)
            reversal = self._rmq.first(
                left if mfe_i is None else mfe_i, right, zero_mid, above=zero_above
            )
            reclaim_mid, reclaim_above = _mid_condition(anchor, 0, True)
            reclaim = None if reversal is None else self._rmq.first(
                reversal + 1, right, reclaim_mid, above=reclaim_above
            )
            barriers = {
                "risk_set": right > left,
                "favorable_event": any(t["state"] is PassageState.ATTAINED
                                       for t in touches[:len(FAVORABLE_DOLLAR_RUNGS)]),
                "adverse_event": any(t["state"] is PassageState.ATTAINED
                                     for t in touches[len(FAVORABLE_DOLLAR_RUNGS):8]),
                "cif_mask": reason not in (BoundaryReason.NO_SANE_SUFFIX,),
                "censor_reason": None if economic else reason,
                "fixed_vertical_valid": reason not in (
                    BoundaryReason.SOURCE,
                    BoundaryReason.GENERATION,
                    BoundaryReason.DEVELOPMENT,
                ),
                "event_mask": reason not in (
                    BoundaryReason.SOURCE,
                    BoundaryReason.GENERATION,
                    BoundaryReason.DEVELOPMENT,
                    BoundaryReason.NO_SANE_SUFFIX,
                ),
            }
            favorable_600, favorable_above = _mid_condition(
                anchor, 600 * PNL_UNITS_PER_USD, True
            )
            adverse_900, adverse_above = _mid_condition(
                anchor, -900 * PNL_UNITS_PER_USD, False
            )
            favorable_hit = self._rmq.first(
                left, right, favorable_600, favorable_above
            )
            adverse_hit = self._rmq.first(left, right, adverse_900, adverse_above)
            barriers["competing_state"] = (
                PassageState.SAME_EVENT_TIE
                if favorable_hit is not None and favorable_hit == adverse_hit
                else PassageState.ATTAINED
                if favorable_hit is not None or adverse_hit is not None
                else PassageState.NOT_ATTAINED if economic
                else PassageState.CENSORED
            )
            barriers["distinct_competing_events"] = bool(
                favorable_hit is not None and adverse_hit is not None
                and favorable_hit != adverse_hit
            )
            availability = (
                CellAvailability.MATERIALIZED if economic
                else CellAvailability.RIGHT_CENSORED
            )
            computed = CanonicalOutcome(
                availability, terminal_ts, terminal_ord, reason, final,
                reason is BoundaryReason.WALL, mfe, mae,
            )
            if anchor.canonical is not None:
                typed_match = (
                    anchor.canonical.status is availability
                    and anchor.canonical.exit_reason is reason
                    and anchor.canonical.exit_ts_recv_ns == terminal_ts
                    and anchor.canonical.exit_source_ordinal == terminal_ord
                )
                parity_match = (anchor.canonical == computed) if economic else (
                    not anchor.canonical.wall_hit
                )
                if not typed_match or not parity_match:
                    raise AtlasRefusal(
                        "canonical outcome lacks typed availability/reason byte/unit parity"
                    )
            values = {
                "availability": availability, "boundary_reason": reason,
                "terminal_key": (terminal_ts, terminal_ord),
                "final_units": final if economic else None,
                "wall_hit": reason is BoundaryReason.WALL, "mfe_units": mfe,
                "mae_units": mae,
                # An unattained favorable/adverse extreme has no passage time.
                # ``0`` would publish "occurred instantly" as observed truth,
                # so the atom stays None and becomes a masked coordinate.
                "time_to_mfe_ns": (None if mfe_i is None else
                                    int(self.economic_ts[mfe_i]) - anchor.decision_ts_ns),
                "time_to_mae_ns": (None if mae_i is None else
                                    int(self.economic_ts[mae_i]) - anchor.decision_ts_ns),
                "fixed_endpoints": endpoints, "trajectory": tuple(trajectory),
                "rung_touches": tuple(touches), "mixed_targets": mixed,
                "trends": self._trend(
                    anchor, left, right,
                    stop_hints=trend_right[row_index],
                ),
                "reversal_reclaim": {"reversal_index": reversal, "reclaim_index": reclaim,
                                     "complete": reclaim is not None},
                "occupation": occupation, "barriers": barriers,
                "action_loss_mask": anchor.action_loss_mask,
                "take_target": anchor.take_target,
                "now_wait_pass_regret_units": anchor.now_wait_pass_regret_units,
                "shadow_marginal_regret_units": anchor.shadow_marginal_regret_units,
                "exact_time_group_id": (
                    None if anchor.exact_time_group_id is None else
                    (anchor.asset, int(anchor.trading_day),
                     int(anchor.decision_ts_ns), anchor.exact_time_group_id)
                ),
            }
            for name in atoms:
                atoms[name].append(values[name])
        scalar_dtypes = {
            "wall_hit": np.bool_, "mfe_units": object, "mae_units": object,
            "time_to_mfe_ns": object, "time_to_mae_ns": object,
            "final_units": object, "action_loss_mask": np.bool_,
            "take_target": np.bool_, "exact_time_group_id": object,
            "now_wait_pass_regret_units": object,
            "shadow_marginal_regret_units": object,
            "availability": object, "boundary_reason": object,
        }
        frozen: dict[str, Any] = {}
        for name, values in atoms.items():
            if name in scalar_dtypes:
                if name in {"exact_time_group_id", "now_wait_pass_regret_units",
                            "shadow_marginal_regret_units"}:
                    column = np.empty(len(values), dtype=object)
                    column[:] = values
                else:
                    column = np.asarray(values, dtype=scalar_dtypes[name])
                column.setflags(write=False)
                frozen[name] = column
            elif name == "terminal_key":
                column = np.asarray(values, dtype=object)
                column.setflags(write=False)
                frozen[name] = column
            else:
                frozen[name] = tuple(values)
        axis_count = len(HORIZON_SECONDS) + 2
        vertical_units = np.zeros((len(anchors), axis_count), np.int64)
        vertical_mask = np.zeros((len(anchors), axis_count), bool)
        vertical_status = np.full((len(anchors), axis_count), -1, np.int8)
        endpoint_axes = tuple(f"{seconds}s" for seconds in HORIZON_SECONDS) + (
            "PHASE", "FINAL",
        )
        status_code = {state: index for index, state in enumerate(EndpointStatus)}
        rung_threshold = np.zeros((len(anchors), 14), np.int64)
        rung_threshold_mask = np.zeros((len(anchors), 14), bool)
        rung_time_ns = np.zeros((len(anchors), 14), np.int64)
        rung_event = np.zeros((len(anchors), 14), bool)
        rung_at_risk = np.zeros((len(anchors), 14), bool)
        rung_censor = np.zeros((len(anchors), 14), bool)
        rung_cause = np.zeros((len(anchors), 14), np.int8)
        rung_tie = np.zeros((len(anchors), 14), bool)
        for row, endpoints in enumerate(atoms["fixed_endpoints"]):
            if endpoints:
                for axis, name in enumerate(endpoint_axes):
                    endpoint = endpoints[name]
                    vertical_status[row, axis] = status_code[endpoint["status"]]
                    if endpoint["value_units"] is not None:
                        vertical_units[row, axis] = endpoint["value_units"]
                        vertical_mask[row, axis] = True
            touches = atoms["rung_touches"][row]
            if touches:
                for axis, touch in enumerate(touches):
                    threshold = touch["threshold_units"]
                    if threshold is not None:
                        rung_threshold[row, axis] = threshold
                        rung_threshold_mask[row, axis] = True
                    rung_at_risk[row, axis] = touch["state"] is not PassageState.NOT_AT_RISK
                    rung_event[row, axis] = touch["state"] is PassageState.ATTAINED
                    rung_censor[row, axis] = touch["state"] is PassageState.CENSORED
                    rung_cause[row, axis] = (1 if threshold is not None and threshold > 0
                                             else -1 if threshold is not None else 0)
                    if touch["elapsed_ns"] is not None:
                        rung_time_ns[row, axis] = touch["elapsed_ns"]
            barrier = atoms["barriers"][row]
            if barrier and barrier["competing_state"] is PassageState.SAME_EVENT_TIE:
                rung_tie[row, (1, 7)] = True
        for name, array in {
            "vertical_units": vertical_units, "vertical_mask": vertical_mask,
            "vertical_status": vertical_status,
            "rung_threshold_units": rung_threshold,
            "rung_threshold_mask": rung_threshold_mask,
            "rung_time_ns": rung_time_ns, "rung_event": rung_event,
            "rung_at_risk": rung_at_risk, "rung_censor": rung_censor,
            "rung_cause": rung_cause, "rung_tie": rung_tie,
        }.items():
            array.setflags(write=False)
            frozen[name] = array
        frozen_atoms = MappingProxyType(frozen)
        receipt = atlas_receipt(self, anchors, frozen_atoms)
        return MaterializedAtlas(ids, anchors, frozen_atoms, PROBE_REGISTRY, SHUFFLED_PROBES,
                                 ("SHARED_ENCODER_FIT_A", "SHARED_ENCODER_FIT_B"),
                                 MappingProxyType(receipt))


_PROBE_COUNTS = (1, 1, 2, 2, 1, 1, 1, 1, 1, 4, 1, 1, 1, 1, 3, 1, 1, 2, 2, 4, 2, 6, 2, 2)
_CELL_ATOMS = (
    ("mixed_targets",), ("mixed_targets",), ("fixed_endpoints",),
    ("fixed_endpoints", "availability"), ("trajectory",),
    ("mfe_units", "mae_units", "time_to_mfe_ns", "time_to_mae_ns"),
    ("final_units", "mfe_units", "mae_units"), ("occupation",),
    ("rung_event", "rung_time_ns", "rung_at_risk", "rung_censor"),
    ("rung_touches", "vertical_status", "terminal_key", "barriers"),
    ("trends",), ("reversal_reclaim",),
    ("final_units",), ("take_target", "action_loss_mask"),
    ("final_units", "exact_time_group_id", "action_loss_mask"),
    ("now_wait_pass_regret_units", "action_loss_mask"),
    ("shadow_marginal_regret_units", "action_loss_mask"),
    ("occupation", "final_units"),
    ("final_units",), ("final_units",), ("final_units",),
    ("trajectory",), ("trajectory",),
    ("rung_touches", "vertical_status", "terminal_key", "barriers"),
)

_FIXED_TARGET_WIDTH = {
    1: 29, 2: 18, 3: 12, 4: 5, 5: 12, 6: 6, 7: 4, 8: 7,
    9: 4, 10: 72, 11: 20, 12: 4, 13: 8, 14: 1, 15: 3, 16: 3,
    17: 2, 18: 1, 21: 2, 22: 12, 23: 12, 24: 72,
}


def _probe_dimensions(cell: int, variant: int) -> tuple[int, int]:
    if cell == 4:
        target = (5, 4)[variant - 1]
    elif cell == 19:
        target = (1, 4)[variant - 1]
    elif cell == 20:
        target = (7, 7, 8, 7)[variant - 1]
    elif cell == 21:
        target = (5, 1)[variant - 1]
    else:
        target = _FIXED_TARGET_WIDTH[cell]
    prediction = 180 if cell in (10, 24) else 30 if cell == 11 else target
    return target, prediction


def _nominal_probe_schema(cell: int, variant: int) -> str:
    target, prediction = _probe_dimensions(cell, variant)
    return hashlib.sha256(json.dumps({
        "schema": "entry-v2-probe-numeric-contract-v2", "cell": cell,
        "variant": variant, "padded_width": PADDED_OUTPUT_WIDTH,
        "target_width": target, "prediction_width": prediction,
    }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _build_probes() -> tuple[ProbeSpec, ...]:
    def support_id(cell: int, variant: int) -> str:
        if cell == 15:
            return "support.exact_time_ranking"
        if cell in (9, 10, 24):
            return "support.competing_cause"
        if cell in (1, 2, 11):
            return "support.mixed_continuous_ordinal"
        if (cell in (4, 12, 13, 14, 21)
                or (cell == 19 and variant == 2)
                or (cell == 20 and variant in (2, 3, 4))):
            return "support.binary_ordinal"
        if cell in (16, 17, 18):
            return "support.economic_continuous"
        return "support.continuous"

    rows: list[ProbeSpec] = []
    for cell, count in enumerate(_PROBE_COUNTS, 1):
        for variant in range(count):
            variant_id = variant + 1
            rows.append(ProbeSpec(
                f"C{cell:02d}P{variant_id:02d}", cell,
                f"materialize.cell{cell:02d}", f"loss.cell{cell:02d}.v{variant_id}",
                _nominal_probe_schema(cell, variant_id), "mask.typed_availability",
                support_id(cell, variant_id), "shuffle.stage_global_recipient_fixed",
                f"action_mapper.cell{cell:02d}.v{variant_id}",
                _CELL_ATOMS[cell - 1], False,
            ))
    return tuple(rows)


PROBE_REGISTRY = _build_probes()
SHUFFLED_PROBES = tuple(ProbeSpec(
    f"{row.probe_id}.SHUFFLED", row.cell, row.materializer_id, row.loss_id,
    row.target_schema, row.mask_id, row.support_id, row.shuffle_id,
    row.action_mapper_id, row.required_atoms, True,
) for row in PROBE_REGISTRY)


PROBE_BY_ID = MappingProxyType({row.probe_id: row for row in PROBE_REGISTRY})
SHUFFLED_PROBE_BY_REAL_ID = MappingProxyType({
    real.probe_id: twin for real, twin in zip(PROBE_REGISTRY, SHUFFLED_PROBES)
})
REAL_PROBE_BY_SHUFFLED_ID = MappingProxyType({
    twin.probe_id: real for real, twin in zip(PROBE_REGISTRY, SHUFFLED_PROBES)
})


def shuffled_probe_for(
    real: ProbeSpec, *, available: Sequence[ProbeSpec] | None = None,
) -> ProbeSpec:
    """Resolve one registered real probe to its exact registered null twin.

    Callers never construct or parse a twin identifier.  When a materialized
    atlas roster is supplied, the accessor also proves that the local roster
    contains exactly the canonical twin rather than a same-named substitute.
    """
    canonical_real = PROBE_BY_ID.get(getattr(real, "probe_id", ""))
    if canonical_real is None or real != canonical_real or real.shuffled_twin:
        raise AtlasRefusal("real probe is not an exact registered atlas row")
    twin = SHUFFLED_PROBE_BY_REAL_ID.get(real.probe_id)
    if twin is None:
        raise AtlasRefusal("registered real probe has no shuffled twin")
    if available is not None:
        matches = tuple(row for row in available if row.probe_id == twin.probe_id)
        if matches != (twin,):
            raise AtlasRefusal(
                "materialized atlas does not contain the exact registered shuffled twin"
            )
    return twin


MASK_REGISTRY = MappingProxyType({
    "mask.typed_availability": lambda target: target.validity_mask
})


def _support_descriptor(kind: str, target: ProbeTarget) -> Mapping[str, Any]:
    """Return typed support inputs; the held engine supplies asset/day IDs.

    This is intentionally not an identity mask.  It binds the declared
    support family, row/coordinate masks and target values so the stage engine
    must execute the corresponding frozen census rather than treating every
    development row as supported.
    """
    return MappingProxyType({
        "kind": kind,
        "validity_mask": target.validity_mask,
        "coordinate_mask": target.coordinate_mask,
        # The continuous quota counts UNCENSORED observations, so the censor
        # planes must travel with the support descriptor.  A finite censored
        # value is not an observation and cannot repair low support.
        "censor_mask": target.censor_mask,
        "coordinate_censor": target.coordinate_censor,
        "at_risk_mask": target.at_risk_mask,
        "values": target.values[:, :target.output_width],
        "group_id": target.group_id,
    })


def _support_continuous(target: ProbeTarget) -> Mapping[str, Any]:
    return _support_descriptor("continuous", target)


def _support_binary_ordinal(target: ProbeTarget) -> Mapping[str, Any]:
    return _support_descriptor("binary_ordinal", target)


def _support_competing_cause(target: ProbeTarget) -> Mapping[str, Any]:
    return _support_descriptor("competing_cause", target)


def _support_exact_time_ranking(target: ProbeTarget) -> Mapping[str, Any]:
    return _support_descriptor("exact_time_ranking", target)


def _support_economic_continuous(target: ProbeTarget) -> Mapping[str, Any]:
    return _support_descriptor("economic_continuous", target)


def _support_mixed_continuous_ordinal(target: ProbeTarget) -> Mapping[str, Any]:
    return _support_descriptor("mixed_continuous_ordinal", target)


SUPPORT_REGISTRY = MappingProxyType({
    "support.continuous": _support_continuous,
    "support.binary_ordinal": _support_binary_ordinal,
    "support.competing_cause": _support_competing_cause,
    "support.exact_time_ranking": _support_exact_time_ranking,
    "support.economic_continuous": _support_economic_continuous,
    "support.mixed_continuous_ordinal": _support_mixed_continuous_ordinal,
})


def _runtime_registries() -> tuple[Mapping[str, Any], Mapping[str, Any],
                                   Mapping[str, Any], Mapping[str, Any]]:
    """Load numeric consumers only after this type module is initialized."""
    from .atlas_materializers import (
        MATERIALIZER_REGISTRY, stage_global_recipient_fixed_permutation,
    )
    from .atlas_losses import build_action_registry, build_loss_registry
    return (MATERIALIZER_REGISTRY, build_loss_registry(PROBE_REGISTRY),
            build_action_registry(PROBE_REGISTRY), MappingProxyType({
                "shuffle.stage_global_recipient_fixed":
                    stage_global_recipient_fixed_permutation,
            }))


def materialize_probe_target(*args: Any, **kwargs: Any) -> ProbeTarget:
    from .atlas_materializers import materialize_probe_target as implementation
    return implementation(*args, **kwargs)


def permute_probe_target_recipient_fixed(*args: Any, **kwargs: Any) -> ProbeTarget:
    from .atlas_materializers import permute_probe_target_recipient_fixed as implementation
    return implementation(*args, **kwargs)


def stage_global_recipient_fixed_permutation(*args: Any, **kwargs: Any) -> np.ndarray:
    from .atlas_materializers import stage_global_recipient_fixed_permutation as implementation
    return implementation(*args, **kwargs)


def loss_for_probe(*args: Any, **kwargs: Any) -> Any:
    from .atlas_losses import loss_for_probe as implementation
    return implementation(*args, **kwargs)


def action_score_for_probe(*args: Any, **kwargs: Any) -> Any:
    from .atlas_losses import action_score_for_probe as implementation
    return implementation(*args, **kwargs)


def reject_placeholder_callable(name: str, function: Any) -> None:
    """Cheap static screen.

    This is a first filter only.  Names and bytecode shapes cannot see a
    constant-returning mapper or a C-implemented callable, so the binding
    evidence is the EXECUTED two-plane behaviour check in
    :func:`validate_registry`; this function never stands alone.
    """
    if not callable(function):
        raise AtlasRefusal(f"{name}: registry entry is not callable")
    lowered = getattr(function, "__name__", "").lower()
    if any(token in lowered for token in ("identity", "placeholder", "noop")):
        raise AtlasRefusal(f"{name}: identity/placeholder callable refuses startup")
    code = getattr(function, "__code__", None)
    if code is not None:
        operations = [instruction.opname for instruction in dis.Bytecode(function)
                      if instruction.opname not in ("RESUME", "CACHE", "NOP")]
        if operations == ["LOAD_FAST", "RETURN_VALUE"]:
            raise AtlasRefusal(f"{name}: identity/placeholder callable refuses startup")


SENTINEL_REGISTRY_SHA256 = "0" * 64
_REGISTRY_VALIDATION_STATE = threading.local()


def _registry_validation_active() -> bool:
    return bool(getattr(_REGISTRY_VALIDATION_STATE, "active", False))


def _sentinel_columns(mid2: Sequence[int], seconds: Sequence[int],
                      offset: int = 0) -> dict[str, Any]:
    n = len(mid2)
    ts = np.asarray([int(value) * 1_000_000_000 for value in seconds], np.uint64)
    values = np.asarray(mid2, np.int64)
    return dict(
        ts_recv_ns=ts, source_ordinal=np.zeros(n, np.uint32),
        trusted_message=np.ones(n, bool), trusted_economic=np.ones(n, bool),
        sane_bbo=np.ones(n, bool), generation=np.ones(n, np.int64), mid2=values,
        action=(np.arange(n, dtype=np.int16) + offset).astype(np.int16),
        side=np.resize([-1, 1], n),
        flags=(np.arange(n, dtype=np.int64) + offset).astype(np.uint32),
        depth=np.ones(n, np.int16),
        missing_mask=np.zeros(n, np.uint32), spread_mask=np.zeros(n, np.uint32),
        price=values, bid_px=values - 1, ask_px=values + 1,
        size=np.arange(n, dtype=np.int64) + 3 + offset,
        bid_size=np.arange(n, dtype=np.int64) + 1 + offset,
        ask_size=np.arange(n, dtype=np.int64) + 2 + offset,
        bid_count=np.arange(n, dtype=np.int64) + 4 + offset,
        ask_count=np.arange(n, dtype=np.int64) + 5 + offset,
        ts_in_delta=np.arange(n, dtype=np.int64) + 6 + offset,
        receive_session_sec=np.arange(n, dtype=np.int64) + 7 + offset,
        sequence=np.arange(n, dtype=np.int64) + offset,
        ts_event_ns=ts.astype(np.int64) - 7,
    )


_SENTINEL_PLANES = (
    {
        "mid2": (1000, 1020, 1300, 900, 1600, 500),
        "seconds": (1, 2, 3, 4, 5, 6),
        "offset": 0,
        "anchors": (
            dict(candidate_id="sentinel-a0", side=1, entry_mid2=1000,
                 take_target=True, payer_target=True,
                 native_candidate_local=True,
                 now_wait_pass_regret_units=(1, 2, 3),
                 shadow_marginal_regret_units=(4, 5), process_utility_units=6),
            dict(candidate_id="sentinel-a1", side=1, entry_mid2=1010,
                 take_target=False, payer_target=False,
                 native_candidate_local=False,
                 now_wait_pass_regret_units=(3, 2, 1),
                 shadow_marginal_regret_units=(5, 4), process_utility_units=7),
        ),
    },
    {
        "mid2": (1005, 980, 1900, 1100, 300, 1400),
        "seconds": (1, 3, 4, 5, 6, 7),
        "offset": 3,
        "anchors": (
            dict(candidate_id="sentinel-b0", side=-1, entry_mid2=1005,
                 take_target=False, payer_target=False,
                 native_candidate_local=False,
                 now_wait_pass_regret_units=(9, 8, 7),
                 shadow_marginal_regret_units=(2, 1), process_utility_units=11),
            dict(candidate_id="sentinel-b1", side=1, entry_mid2=700,
                 take_target=True, payer_target=True,
                 native_candidate_local=True,
                 now_wait_pass_regret_units=(4, 6, 8),
                 shadow_marginal_regret_units=(7, 3), process_utility_units=13),
        ),
    },
)


def _sentinel_atlas(plane: int) -> MaterializedAtlas:
    """Build one throwaway two-candidate atlas used only for startup evidence."""
    spec = _SENTINEL_PLANES[plane]
    index = SessionTruthIndex(**_sentinel_columns(
        spec["mid2"], spec["seconds"], int(spec["offset"])))
    anchors = tuple(CandidateAnchor(
        decision_ts_ns=1_000_000_000, multiplier=PNL_UNITS_PER_USD,
        frozen_cost_units=0, phase_close_ts_ns=8 * 1_000_000_000,
        source_ordinal=0, generation=1, sigma_prior_units=100 * PNL_UNITS_PER_USD,
        exact_time_group_id=f"sentinel-group-{plane}", **row
    ) for row in spec["anchors"])
    return index.materialize(anchors)


_SENTINEL_FIT_CONTEXT = MappingProxyType({
    "fit_population_sha256": "a" * 64,
    "c1_location": np.zeros(21), "c1_scale": np.ones(21),
    "location": np.zeros(12), "scale": np.ones(12),
    "lower": np.full(12, -5000.0), "upper": np.full(12, 5000.0),
    "rank_reference": np.zeros((3, 12)),
    "ipcw_weights": np.asarray([1.5, 2.5], np.float32),
})


def _sentinel_probe_target(row: ProbeSpec, plane: int) -> ProbeTarget:
    """Two distinct synthetic label planes for one registered probe."""
    variant = int(row.probe_id.split("P", 1)[1].split(".", 1)[0])
    width, prediction_width = _probe_dimensions(row.cell, variant)
    layout = tuple(f"synthetic_{index}" for index in range(width))
    prediction_layout = tuple(f"synthetic_prediction_{index}"
                              for index in range(prediction_width))
    values = np.zeros((2, PADDED_OUTPUT_WIDTH), np.float32)
    if plane == 0:
        values[0, 0] = 1.0
        values[1, 1] = 1.0
        if row.cell in (10, 24):
            values[:, 28:42] = 1.0
            values[0, 14] = 1.0
            values[1, 15] = 2.0
        if row.cell == 15:
            values[0, 2] = 1.0
        valid = np.ones(2, bool)
        weight = np.ones(2, np.float32)
    else:
        values[:, :width] = 0.5
        values[0, 1] = 2.0
        values[1, 0] = 3.0
        if row.cell in (10, 24):
            values[:, 28:42] = 2.0
            values[0, 14] = 3.0
            values[1, 15] = 1.0
        if row.cell == 15:
            values[1, 2] = 2.0
        valid = np.asarray([True, False])
        weight = np.asarray([2.0, 0.0], np.float32)
    coordinates = np.zeros_like(values, dtype=bool)
    coordinates[:, :width] = valid[:, None]
    return ProbeTarget(
        row.probe_id, CellAvailability.MATERIALIZED, values,
        coordinates, coordinates, np.zeros_like(coordinates),
        valid, valid, np.zeros(2, bool), weight,
        np.asarray([0, 0], np.int64), np.asarray([2, 2], np.int64),
        width, layout, 1,
        probe_target_schema_sha256(row.probe_id, width, layout, 1, None,
                                   prediction_width, prediction_layout),
        None, prediction_width, prediction_layout,
    )


def _sentinel_prediction(plane: int) -> Any:
    import torch
    if plane == 0:
        return torch.linspace(
            -0.2, 0.2, 2 * PADDED_OUTPUT_WIDTH
        ).reshape(2, PADDED_OUTPUT_WIDTH).requires_grad_()
    return torch.linspace(
        0.7, -1.3, 2 * PADDED_OUTPUT_WIDTH
    ).reshape(2, PADDED_OUTPUT_WIDTH).requires_grad_()


def _descriptor_bytes(value: Any) -> bytes:
    digest = hashlib.sha256()
    if isinstance(value, Mapping):
        for name in sorted(value):
            digest.update(str(name).encode())
            digest.update(_descriptor_bytes(value[name]))
        return digest.digest()
    array = np.asarray(value)
    if array.dtype == object:
        return hashlib.sha256(repr(value).encode()).digest()
    digest.update(str(array.dtype).encode()); digest.update(str(array.shape).encode())
    digest.update(np.ascontiguousarray(array).tobytes())
    return digest.digest()


def validate_registry() -> None:
    previous = getattr(_REGISTRY_VALIDATION_STATE, "active", False)
    _REGISTRY_VALIDATION_STATE.active = True
    try:
        _validate_registry_body()
    finally:
        _REGISTRY_VALIDATION_STATE.active = previous


def _validate_registry_body() -> None:
    (materializer_registry, loss_registry, action_mapper_registry,
     shuffle_registry) = _runtime_registries()
    if sum(_PROBE_COUNTS) != 44 or len(PROBE_REGISTRY) != 44:
        raise AtlasRefusal("probe registry must contain exactly 44 executable rows")
    if {row.cell for row in PROBE_REGISTRY} != set(range(1, 25)):
        raise AtlasRefusal("probe registry must cover all 24 cells")
    if (len(PROBE_BY_ID) != 44 or len(SHUFFLED_PROBE_BY_REAL_ID) != 44
            or len(REAL_PROBE_BY_SHUFFLED_ID) != 44
            or tuple(shuffled_probe_for(row) for row in PROBE_REGISTRY)
                != SHUFFLED_PROBES
            or tuple(REAL_PROBE_BY_SHUFFLED_ID[row.probe_id]
                     for row in SHUFFLED_PROBES) != PROBE_REGISTRY):
        raise AtlasRefusal("real/shuffled probe registry map is not bijective")
    for row in (*PROBE_REGISTRY, *SHUFFLED_PROBES):
        if not all((row.materializer_id, row.loss_id, row.target_schema, row.mask_id,
                    row.support_id, row.shuffle_id, row.action_mapper_id,
                    row.required_atoms)):
            raise AtlasRefusal("probe registry row is not executable")
        if len(row.target_schema) != 64 or any(
            char not in "0123456789abcdef" for char in row.target_schema
        ):
            raise AtlasRefusal("probe registry target schema is not a sha256")
        if (
            row.materializer_id not in materializer_registry
            or row.loss_id not in loss_registry
            or row.mask_id not in MASK_REGISTRY
            or row.support_id not in SUPPORT_REGISTRY
            or row.shuffle_id not in shuffle_registry
            or row.action_mapper_id not in action_mapper_registry
        ):
            raise AtlasRefusal("probe registry references an unresolved callable id")
        reject_placeholder_callable(row.materializer_id,
                                    materializer_registry[row.materializer_id])
        reject_placeholder_callable(row.loss_id, loss_registry[row.loss_id])
        reject_placeholder_callable(row.action_mapper_id,
                                    action_mapper_registry[row.action_mapper_id])
    import torch
    # Executed anti-placeholder evidence.  A name/bytecode screen cannot see a
    # constant-returning mapper, a C-implemented callable, or an unguarded
    # mask/support entry, so every registered callable is RUN on two distinct
    # sentinel input planes and must respond where the law says it must.
    sentinel_atlases = tuple(_sentinel_atlas(plane) for plane in (0, 1))
    predictions = tuple(_sentinel_prediction(plane) for plane in (0, 1))
    for row in PROBE_REGISTRY:
        width, prediction_width = _probe_dimensions(row.cell, _variant := int(
            row.probe_id.split("P", 1)[1].split(".", 1)[0]))
        if row.target_schema != _nominal_probe_schema(row.cell, _variant):
            raise AtlasRefusal(f"{row.probe_id}: nominal numeric schema differs")
        planes = tuple(_sentinel_probe_target(row, plane) for plane in (0, 1))
        synthetic = planes[0]
        prediction = predictions[0]
        scalar = loss_registry[row.loss_id](prediction, synthetic)
        scalar.backward()
        if (scalar.ndim != 0 or not bool(torch.isfinite(scalar))
                or prediction.grad is None
                or not bool(torch.isfinite(prediction.grad).all())
                or not bool(torch.any(prediction.grad != 0))):
            raise AtlasRefusal(f"{row.probe_id}: synthetic loss/gradient validation failed")
        action = action_mapper_registry[row.action_mapper_id](prediction, synthetic)
        if action.shape != (2,) or not bool(torch.isfinite(action).all()):
            raise AtlasRefusal(f"{row.probe_id}: action mapper validation failed")

        # (a) the loss must read its labels: two distinct label planes under
        # one prediction plane cannot score identically.
        other = loss_registry[row.loss_id](predictions[0], planes[1]).detach()
        if not bool(torch.isfinite(other)) or float(other) == float(scalar.detach()):
            raise AtlasRefusal(
                f"{row.probe_id}: loss is label-blind on two sentinel planes"
            )
        # (a) the action mapper must read its prediction: two distinct
        # prediction planes cannot produce the same action vector.
        first = action_mapper_registry[row.action_mapper_id](
            predictions[0].detach(), synthetic)
        second = action_mapper_registry[row.action_mapper_id](
            predictions[1].detach(), synthetic)
        if bool(torch.equal(first, second)):
            raise AtlasRefusal(
                f"{row.probe_id}: action mapper is prediction-blind on two sentinel planes"
            )
        # (b) mask and support registries are guarded on the same evidence.
        mask_callable = MASK_REGISTRY[row.mask_id]
        mask_first = np.asarray(mask_callable(planes[0]))
        mask_second = np.asarray(mask_callable(planes[1]))
        if mask_first.shape != (2,) or mask_first.dtype != np.bool_:
            raise AtlasRefusal(f"{row.mask_id}: mask registry entry is not a row mask")
        if np.array_equal(mask_first, mask_second):
            raise AtlasRefusal(
                f"{row.mask_id}: mask registry entry is target-blind on two sentinel planes"
            )
        support_callable = SUPPORT_REGISTRY[row.support_id]
        support_first = support_callable(planes[0])
        support_second = support_callable(planes[1])
        if not isinstance(support_first, Mapping) or "kind" not in support_first:
            raise AtlasRefusal(f"{row.support_id}: support registry entry is not typed")
        if _descriptor_bytes(support_first) == _descriptor_bytes(support_second):
            raise AtlasRefusal(
                f"{row.support_id}: support registry entry is target-blind "
                "on two sentinel planes"
            )
        # (a) the materializer must read its atlas: two distinct sentinel
        # truth planes cannot produce byte-identical labels.
        materializer = materializer_registry[row.materializer_id]
        materialized = tuple(
            materializer(atlas, row, dict(_SENTINEL_FIT_CONTEXT))
            for atlas in sentinel_atlases
        )
        if probe_fit_slice_content_sha256(materialized[0]) == \
                probe_fit_slice_content_sha256(materialized[1]):
            raise AtlasRefusal(
                f"{row.materializer_id}/{row.probe_id}: materializer is "
                "atlas-blind on two sentinel truth planes"
            )

_REGISTRY_CACHE_LOCK = threading.Lock()
_REGISTRY_BYTES_CACHE: bytes | None = None
_REGISTRY_SHA256_CACHE: str | None = None


def _compute_registry_bytes() -> bytes:
    validate_registry()
    (materializer_registry, loss_registry, action_mapper_registry,
     shuffle_registry) = _runtime_registries()
    def callable_digest(function: Any) -> str:
        code = getattr(function, "__code__", None)
        payload = {
            "module": getattr(function, "__module__", None),
            "qualname": getattr(function, "__qualname__", None),
            "source": inspect.getsource(function),
            "bytecode": None if code is None else code.co_code.hex(),
            "constants": None if code is None else repr(code.co_consts),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True,
                                         separators=(",", ":")).encode()).hexdigest()
    callable_hashes = {}
    for row in PROBE_REGISTRY:
        callable_hashes[row.materializer_id] = callable_digest(materializer_registry[row.materializer_id])
        callable_hashes[row.loss_id] = callable_digest(loss_registry[row.loss_id])
        callable_hashes[row.action_mapper_id] = callable_digest(action_mapper_registry[row.action_mapper_id])
        callable_hashes[row.support_id] = callable_digest(SUPPORT_REGISTRY[row.support_id])
    callable_hashes["implementation.materialize_probe_target"] = callable_digest(materialize_probe_target)
    callable_hashes["implementation.loss_for_probe"] = callable_digest(loss_for_probe)
    callable_hashes["implementation.action_score_for_probe"] = callable_digest(action_score_for_probe)
    callable_hashes["implementation.stage_global_shuffle"] = callable_digest(
        shuffle_registry["shuffle.stage_global_recipient_fixed"]
    )
    for name in ("mask.typed_availability",):
        callable_hashes[name] = callable_digest(MASK_REGISTRY[name])
    # The registry rows and the module forwarders are three-line indirections.
    # Bind the IMPLEMENTING module source bytes so a rewritten materializer or
    # loss body cannot keep the registry digest.
    from . import atlas_losses as _losses_module
    from . import atlas_materializers as _materializers_module
    module_sources = {
        module.__name__: hashlib.sha256(
            inspect.getsource(module).encode()).hexdigest()
        for module in (_losses_module, _materializers_module)
    }
    payload = {
        "schema": "entry-v2-causal-label-probe-registry-v3",
        "probes": [row.canonical() for row in PROBE_REGISTRY],
        "shuffled_twins": [row.canonical() for row in SHUFFLED_PROBES],
        "shared_encoder_fits": 2,
        "fit_budget": 90,
        "e1_fit_budget": 90,
        "max_through_e2_fit_budget": 98,
        "callable_semantics_sha256": callable_hashes,
        "implementing_module_source_sha256": module_sources,
    }
    return json.dumps(C.canonical_json_value(payload), sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode()


def registry_bytes() -> bytes:
    """Return the immutable executable-registry snapshot.

    Registry validation includes source inspection, bytecode inspection and
    synthetic loss/gradient execution.  Those checks bind process-global
    immutable callables; repeating them for every session/phase index changes
    neither the bytes nor the evidence.  Serialize and validate exactly once
    under a lock, then reuse the immutable byte string.
    """
    global _REGISTRY_BYTES_CACHE, _REGISTRY_SHA256_CACHE
    cached = _REGISTRY_BYTES_CACHE
    if cached is not None:
        return cached
    with _REGISTRY_CACHE_LOCK:
        cached = _REGISTRY_BYTES_CACHE
        if cached is None:
            cached = _compute_registry_bytes()
            digest = hashlib.sha256(cached).hexdigest()
            _REGISTRY_BYTES_CACHE = cached
            _REGISTRY_SHA256_CACHE = digest
        return cached


def registry_sha256() -> str:
    global _REGISTRY_SHA256_CACHE
    digest = _REGISTRY_SHA256_CACHE
    if digest is None and _registry_validation_active():
        # Startup validation materializes throwaway sentinel atlases, whose
        # receipts ask for this digest while it is still being computed.  The
        # sentinel receipts are discarded, so a typed placeholder is returned
        # instead of re-entering (and deadlocking) the registry computation.
        return SENTINEL_REGISTRY_SHA256
    if digest is None:
        registry_bytes()
        digest = _REGISTRY_SHA256_CACHE
    if digest is None:
        raise AtlasRefusal("registry digest is unavailable after computation")
    return digest


def probe_target_receipt(spec: ProbeSpec, target: ProbeTarget) -> Mapping[str, Any]:
    if target.probe_id != spec.probe_id:
        raise AtlasRefusal("probe target receipt identity differs")
    digest = hashlib.sha256()
    for name in ("values", "coordinate_mask", "coordinate_at_risk",
                 "coordinate_censor", "validity_mask", "at_risk_mask",
                 "censor_mask", "fit_weight", "group_id", "group_size"):
        value = np.ascontiguousarray(getattr(target, name))
        digest.update(name.encode()); digest.update(str(value.dtype).encode())
        digest.update(str(value.shape).encode()); digest.update(value.tobytes())
    body = {
        "schema": "entry-v2-concrete-probe-target-receipt-v1",
        "probe_id": spec.probe_id,
        "registry_sha256": registry_sha256(),
        "nominal_target_law_sha256": spec.target_schema,
        "concrete_target_schema_sha256": target.schema_sha256,
        "target_layout": list(target.output_layout),
        "target_width": target.output_width,
        "prediction_layout": list(target.prediction_layout),
        "prediction_width": target.prediction_width,
        "transform_provenance_sha256": target.transform_provenance_sha256,
        "target_content_sha256": digest.hexdigest(),
    }
    return MappingProxyType({**body, "receipt_sha256": hashlib.sha256(json.dumps(
        body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()})


BYTE_IDENTICAL_FIT_SLICE_SCHEMA = "entry-v2-probe-fit-slice-content-v1"
BYTE_IDENTICAL_CENSUS_SCHEMA = "entry-v2-probe-byte-identical-collapse-census-v1"


def probe_fit_slice_content_sha256(
    target: ProbeTarget, fit_rows: Sequence[int] | None = None
) -> str:
    """Hash one probe's fit-slice label bytes.

    The collapse law is measured on screen-fit data only and over exactly the
    label content a fit consumes: values, row validity and per-coordinate
    validity.  Layout names and identifiers are deliberately excluded, so two
    differently named probes carrying identical labels hash identically.
    """
    rows = slice(None) if fit_rows is None else np.asarray(fit_rows, np.int64)
    if fit_rows is not None and (rows.ndim != 1 or len(np.unique(rows)) != len(rows)
                                 or np.any(rows < 0)
                                 or np.any(rows >= len(target.validity_mask))):
        raise AtlasRefusal("byte-identical fit slice rows are invalid")
    digest = hashlib.sha256()
    digest.update(BYTE_IDENTICAL_FIT_SLICE_SCHEMA.encode())
    for name in ("values", "validity_mask", "coordinate_mask"):
        array = np.ascontiguousarray(np.asarray(getattr(target, name))[rows])
        digest.update(name.encode()); digest.update(str(array.dtype).encode())
        digest.update(str(array.shape).encode()); digest.update(array.tobytes())
    return digest.hexdigest()


def prune_byte_identical_probe_targets(
    targets: Mapping[str, ProbeTarget], fit_rows: Sequence[int] | None = None,
) -> tuple[Mapping[str, ProbeTarget], Mapping[str, Any]]:
    """Collapse true duplicate probes in registry probe-id order.

    The frozen prune key is the triple
    ``(fit-slice label content sha256, loss_id, action_mapper_id)``.  A probe
    is ``PRUNED_BYTE_IDENTICAL`` only when an earlier registered probe matches
    on ALL THREE.  Probes that share label bytes but carry a different
    registered loss or action mapper are lawful objective CONTRAST cells
    (cells 19-24 register exactly such contrasts) and MUST survive; deleting
    them would gut the purpose of A-008/A-011.

    The census therefore carries two sections: ``label_identical_groups`` is
    transparency about which probes share label bytes, and ``pruned`` is the
    actual all-three-identical duplicate set.
    """
    registry_order = tuple(row.probe_id for row in PROBE_REGISTRY)
    unknown = tuple(sorted(set(targets) - set(registry_order)))
    if unknown:
        raise AtlasRefusal(f"byte-identical pass received unregistered probes: {unknown}")
    hashes: dict[str, str] = {}
    keeper_by_key: dict[tuple[str, str, str], str] = {}
    probes_by_hash: dict[str, list[str]] = {}
    pruned: dict[str, str] = {}
    resolved: dict[str, ProbeTarget] = {}
    for probe_id in registry_order:
        target = targets.get(probe_id)
        if target is None:
            continue
        spec = PROBE_BY_ID[probe_id]
        content = probe_fit_slice_content_sha256(target, fit_rows)
        hashes[probe_id] = content
        probes_by_hash.setdefault(content, []).append(probe_id)
        key = (content, spec.loss_id, spec.action_mapper_id)
        keeper = keeper_by_key.get(key)
        if keeper is None:
            keeper_by_key[key] = probe_id
            resolved[probe_id] = target
            continue
        pruned[probe_id] = keeper
        resolved[probe_id] = replace(
            target, state=CellAvailability.PRUNED_BYTE_IDENTICAL)
    label_groups = [
        {
            "fit_slice_sha256": content,
            "probe_ids": list(members),
            "distinct_loss_ids": sorted({PROBE_BY_ID[row].loss_id for row in members}),
            "distinct_action_mapper_ids": sorted(
                {PROBE_BY_ID[row].action_mapper_id for row in members}),
            "surviving_contrast_probe_ids": [row for row in members
                                             if row not in pruned],
        }
        for content, members in sorted(probes_by_hash.items())
        if len(members) > 1
    ]
    body = {
        "schema": BYTE_IDENTICAL_CENSUS_SCHEMA,
        "prune_key_law": "label-content-and-loss-and-mapper-triple-v1",
        "fit_slice_row_count": (None if fit_rows is None else len(tuple(fit_rows))),
        "registered_probe_count": len(hashes),
        "pruned_probe_count": len(pruned),
        "retained_fit_probe_count": len(hashes) - len(pruned),
        "fit_slice_sha256": dict(sorted(hashes.items())),
        "label_identical_groups": label_groups,
        "label_identical_group_count": len(label_groups),
        "label_identical_probe_ids": sorted(
            row for group in label_groups for row in group["probe_ids"]),
        "pruned": [
            {"kept": keeper, "pruned": probe_id,
             "fit_slice_sha256": hashes[probe_id],
             "loss_id": PROBE_BY_ID[probe_id].loss_id,
             "action_mapper_id": PROBE_BY_ID[probe_id].action_mapper_id}
            for probe_id, keeper in sorted(pruned.items())
        ],
        "pruned_probe_ids": sorted(pruned),
    }
    body["receipt_sha256"] = hashlib.sha256(json.dumps(
        body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return MappingProxyType(resolved), MappingProxyType(body)


def bind_byte_identical_census(
    receipt: Mapping[str, Any], census: Mapping[str, Any]
) -> Mapping[str, Any]:
    """Rebind one atlas receipt to its byte-identical collapse census."""
    if census.get("schema") != BYTE_IDENTICAL_CENSUS_SCHEMA:
        raise AtlasRefusal("byte-identical census schema differs")
    body = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    body["byte_identical_census"] = dict(census)
    body["receipt_sha256"] = hashlib.sha256(json.dumps(
        body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return MappingProxyType(body)


def _array_digest(columns: Mapping[str, np.ndarray]) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(columns.items()):
        array = np.ascontiguousarray(value)
        digest.update(name.encode())
        digest.update(str(array.dtype).encode())
        digest.update(str(array.shape).encode())
        digest.update(array.tobytes())
    return digest.hexdigest()


def atlas_receipt(index: SessionTruthIndex, candidates: Sequence[CandidateAnchor],
                  atoms: Mapping[str, Any],
                  byte_identical_census: Mapping[str, Any] | None = None,
                  ) -> dict[str, Any]:
    def encode(value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value
        if hasattr(value, "__dataclass_fields__"):
            return {field.name: encode(getattr(value, field.name))
                    for field in fields(value)}
        if isinstance(value, tuple):
            return [encode(item) for item in value]
        if isinstance(value, np.integer):
            return int(value)
        return value

    body = {
        "schema": "entry-v2-columnar-causal-label-atlas-v3",
        "event_columns_sha256": _array_digest(index.columns),
        "candidate_anchors_sha256": hashlib.sha256(json.dumps(
            [encode(row) for row in candidates], sort_keys=True,
            separators=(",", ":")).encode()).hexdigest(),
        "registry_sha256": registry_sha256(),
        "candidate_count": len(candidates),
        "event_count": len(index.columns["ts_recv_ns"]),
        "index_query_count": index._rmq.query_count + index._occupation.query_count,
        "index_query_work": index.query_work,
        "candidate_suffix_rows_visited": index.suffix_row_visits,
        "fit_budget": 90,
        "e1_fit_budget": 90,
        "max_through_e2_fit_budget": 98,
        # Bound once the probe targets exist; see prune_byte_identical_probe_targets.
        "byte_identical_census": (None if byte_identical_census is None
                                  else dict(byte_identical_census)),
    }
    body["receipt_sha256"] = hashlib.sha256(json.dumps(
        body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return body


def atlas_receipt_bytes(extra: Mapping[str, Any] | None = None) -> bytes:
    payload = {
        "schema": "entry-v2-columnar-causal-label-atlas-v3",
        "development_cutoff_ns": DEVELOPMENT_CUTOFF_NS,
        "pnl_units_per_usd": PNL_UNITS_PER_USD,
        "registry_sha256": registry_sha256(),
    }
    if extra:
        payload["extra"] = dict(extra)
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


__all__ = [
    "ADVERSE_DOLLAR_RUNGS", "ActionMaskCause", "AtlasRefusal",
    "BoundaryReason",
    "CandidateAnchor", "CanonicalOutcome", "CellAvailability",
    "DEVELOPMENT_CUTOFF_NS", "EndpointStatus", "FAVORABLE_DOLLAR_RUNGS",
    "E1_PROBE_FIT_BUDGET", "MAX_THROUGH_E2_PROBE_FIT_BUDGET",
    "HORIZON_SECONDS", "MASK_REGISTRY",
    "MaterializedAtlas", "PNL_UNITS_PER_USD",
    "PADDED_OUTPUT_WIDTH", "PRIOR_SCALE_RUNGS", "PROBE_BY_ID", "PROBE_REGISTRY",
    "REAL_PROBE_BY_SHUFFLED_ID", "SHUFFLED_PROBE_BY_REAL_ID",
    "PassageState", "ProbeSpec", "ProbeTarget",
    "SHUFFLED_PROBES", "SUPPORT_REGISTRY",
    "SessionTruthIndex", "TREND_SECONDS", "WALL_UNITS",
    "BYTE_IDENTICAL_CENSUS_SCHEMA", "BYTE_IDENTICAL_FIT_SLICE_SCHEMA",
    "SENTINEL_REGISTRY_SHA256",
    "action_score_for_probe", "atlas_receipt", "atlas_receipt_bytes",
    "bind_byte_identical_census",
    "loss_for_probe", "materialize_probe_target", "probe_target_schema_sha256",
    "merge_candidate_truth_atlases",
    "probe_fit_slice_content_sha256", "probe_target_receipt",
    "prune_byte_identical_probe_targets",
    "permute_probe_target_recipient_fixed",
    "registry_bytes", "registry_sha256", "reject_placeholder_callable",
    "shuffled_probe_for",
    "stage_global_recipient_fixed_permutation",
    "validate_registry",
]
