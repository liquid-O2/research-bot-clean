#!/usr/bin/env python3
"""Deterministic learning and OOF orchestration for entry-v2.

Data-loader contract
--------------------
One :class:`EntrySessionSpec` contains one asset-session's metadata.  Its event
stream is materialized as an :class:`EntrySessionBatch` only inside a bounded
context manager.  Examples, candidate tensors, and target rows have exactly
the same order.  ``candidate_cutoffs[i]`` must equal the public example's
``raw_prefix_ref.event_count``.  Future labels never enter the model inputs:
oracle labels are joined by :class:`~engine.entry_v2.teacher.TeacherStore`, and
the five masked self-supervised targets live in a distinct target-only object.

Fold contract
-------------
The encoder and its normalizer see ``FoldSpec.fit_days`` only.  Training is one
seeded full-population pass; the lossy V1 hard-negative retry is not reused.
Per-asset GBTs fit on fit-day embeddings, calibrate on the later
``inner_days`` raw predictions, and expose only ``test_days`` embeddings and
scores.  Thus no in-sample prediction is ever used for calibration or reported
as OOF.  This module never accepts 2025H2 or sealed-2026 rows.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import nullcontext
from dataclasses import asdict, dataclass, fields, replace
import hashlib
from time import perf_counter
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Callable, Iterable, Mapping, Sequence

import numpy as np
import torch
from torch import Tensor, nn
import torch.nn.functional as F

from . import common as C
from .contracts import (
    AssetDayRegime,
    CausalEntryExample,
    EntryEvaluation,
    EntryScore,
    SessionRef,
)
from .folds import FoldSpec
from .context_sources import CONTEXT_TYPE_ID
from .model import EntryModelOutput, FullPrefixEntryModel, model_state_sha256
from .policy import (
    AssetPolicy,
    ModelInputBinding,
    POOLED_SCOPE,
    PolicyConfig,
    entry_decision_gate,
    entry_gate_contract,
    policy_risk_gate,
    predicted_mae_limit_usd,
)
from .replay import (
    CandidateCeiling,
    ReplayOutcome,
    ScoredArrival,
    candidate_ceiling,
    replay,
)
from .teacher import TeacherLabel, TeacherStore, ValueBin
from .selected_horizon_contract import (
    COORDINATES as SELECTED_HORIZON_COORDINATES,
    SCHEMA_SHA256 as SELECTED_HORIZON_SCHEMA_SHA256,
    WIDTH as SELECTED_HORIZON_WIDTH,
    TARGET_LAW_SHA256 as SELECTED_HORIZON_TARGET_LAW_SHA256,
)

if TYPE_CHECKING:
    from .session_stream import SessionEventSource


HORIZONS_SECONDS = (1, 10, 60, 300)
VALUE_SCALE_USD = 1_000.0
MAE_SCALE_USD = C.WALL_USD
MFE_SCALE_USD = 2_000.0
TIME_TO_PEAK_SCALE_SECONDS = 300.0
ARM_POOLED_STATIC = "pooled_static_gbt"
ARM_PER_ASSET_STATIC = "per_asset_static_gbt"
ARM_FULL_PREFIX = "full_prefix_model"
ARM_NAMES = (ARM_POOLED_STATIC, ARM_PER_ASSET_STATIC, ARM_FULL_PREFIX)
STATIC_SUMMARY_SCHEMA = "entry-v2-static-candidate-context-summary-v1"
VALUE_BIN_INDEX = {
    ValueBin.LOSS: 0,
    ValueBin.ZERO_TO_599: 1,
    ValueBin.SIX_HUNDRED_TO_999: 2,
    ValueBin.ONE_THOUSAND_TO_1999: 3,
    ValueBin.TWO_THOUSAND_PLUS: 4,
}
LOSS_WEIGHTS = MappingProxyType({
    "ordinal": 1.00,
    "value_bins": 1.00,
    "value_quantiles": 0.50,
    "expected_value": 1.00,
    "top3": 0.50,
    "rank": 0.35,
    "mfe_quantiles": 0.50,
    "mae_quantiles": 0.50,
    "wall": 0.50,
    "time_to_peak": 0.25,
    "take_target": 1.00,
    "horizons": 0.25,
    "phase": 0.25,
    "hard_negative": 0.50,
    "listwise": 0.35,
})
TRUTH_THRESHOLD_GRID_USD = tuple(float(value) for value in range(600, 10_001, 50))
FOLD_OOF_SCHEMA = "entry-v2-fold-oof-v5"
THRESHOLD_FUNNEL_SCHEMA = "entry-v2-threshold-funnel-v1"
SELECTED_POLICY_TRAINING_SCHEMA = "entry-v2-selected-policy-training-v1"
SELECTED_POLICY_CHRONOLOGY_LAW = "entry-v2-selected-train-only-policy-v1"
SELECTED_ACTION_FIT_WEIGHT_LAW = "entry-v2-action-fit-weights-v1"
SELECTED_PHASE_PAIR_LAW = "entry-v2-canonical-phase-pairs-v1"
SELECTED_ORDINAL_SEMANTICS = "P(value_bin>=1..4)"
SELECTED_ORDINAL_SEMANTICS_SHA256 = C.object_sha256({
    "semantics": SELECTED_ORDINAL_SEMANTICS,
    "loss": "four-aligned-BCEWithLogits",
    "states": [0, 1, 2, 3, 4],
})


def threshold_candidate_law() -> dict[str, Any]:
    """Canonical learned threshold enumeration law used at every boundary."""

    return {
        "schema": "entry-v2-action-threshold-candidates-v1",
        "source": "INNER_SELECTION_CALIBRATED_ACTION_PROBABILITY_ONLY",
        "candidates": (
            "every distinct finite calibrated action_p plus nextafter(max,+inf) "
            "no-entry sentinel"
        ),
        "comparison": "action_p >= per_asset_threshold",
        "maximum_calibrated_levels": PolicyConfig().venn_bins,
        "test_scores_used": False,
    }


@dataclass(frozen=True)
class TrainingConfig:
    """Frozen knobs; there is no per-fold hyperparameter search."""

    seed: int = 20260816
    workers: int = C.MAX_CPU_WORKERS
    device: str = "cuda"
    bf16: bool = True
    learning_rate: float = 2.0e-4
    weight_decay: float = 1.0e-2
    max_grad_norm: float = 1.0
    n_phase_classes: int = 8

    def __post_init__(self) -> None:
        if self.workers != C.MAX_CPU_WORKERS:
            raise C.EntryV2Refusal(
                f"entry-v2 fixes workers={C.MAX_CPU_WORKERS}, got {self.workers}"
            )
        if self.device not in {"cpu", "cuda"}:
            raise C.EntryV2Refusal("training device must be cpu or cuda")
        if not (self.learning_rate > 0 and self.weight_decay >= 0):
            raise C.EntryV2Refusal("invalid optimizer configuration")
        if self.max_grad_norm <= 0:
            raise C.EntryV2Refusal("invalid clipping configuration")
        if self.n_phase_classes < 2:
            raise C.EntryV2Refusal("at least two self-supervised phases are required")

    def receipt(self) -> dict[str, Any]:
        payload = {
            "schema": "entry-v2-learning-config-v2",
            **asdict(self),
            "horizons_seconds": list(HORIZONS_SECONDS),
            "value_scale_usd": VALUE_SCALE_USD,
            "mae_scale_usd": MAE_SCALE_USD,
            "loss_weights": dict(LOSS_WEIGHTS),
            "passes": [
                "fold_causal_self_supervision",
                "full_population_oracle_multitask",
                "matched_hard_negative_listwise",
            ],
        }
        payload["sha256"] = C.object_sha256(payload)
        return payload


@dataclass(frozen=True)
class SelfSupervisedTargets:
    """Target-only future tape changes and future phase class.

    ``horizon_value`` columns correspond exactly to ``(1, 10, 60, 300)``
    seconds.  Masks are required because candidates near session end do not
    have every horizon.  Invalid cells are ignored and may contain any finite
    placeholder; they are zeroed before a loss is formed.
    """

    horizon_value: Tensor
    horizon_valid: Tensor
    phase_class: Tensor
    phase_valid: Tensor

    def validate(self, rows: int) -> None:
        if self.horizon_value.shape != (rows, len(HORIZONS_SECONDS)):
            raise C.EntryV2Refusal("self-supervised horizon target shape mismatch")
        if self.horizon_valid.shape != self.horizon_value.shape:
            raise C.EntryV2Refusal("self-supervised horizon mask shape mismatch")
        if self.phase_class.shape != (rows,) or self.phase_valid.shape != (rows,):
            raise C.EntryV2Refusal("self-supervised phase target shape mismatch")
        if not self.horizon_value.is_floating_point():
            raise C.EntryV2Refusal("horizon targets must be floating point")
        hv = self.horizon_valid.to(dtype=torch.bool)
        if bool(hv.any()) and not bool(torch.isfinite(self.horizon_value[hv]).all()):
            raise C.EntryV2Refusal("valid horizon targets must be finite")
        if self.phase_class.dtype not in (torch.int32, torch.int64):
            raise C.EntryV2Refusal("phase targets must be integer class ids")

    def to(self, device: torch.device) -> "SelfSupervisedTargets":
        return SelfSupervisedTargets(
            self.horizon_value.to(device),
            self.horizon_valid.to(device),
            self.phase_class.to(device),
            self.phase_valid.to(device),
        )


@dataclass(frozen=True)
class EntrySessionBatch:
    """One shared event stream and aligned candidate-grain rows."""

    examples: tuple[CausalEntryExample, ...]
    event_continuous: Tensor
    event_categorical: Tensor
    candidate_cutoffs: Tensor
    candidate_features: Tensor
    context_values: Tensor
    context_type_ids: Tensor
    context_valid: Tensor
    self_supervised: SelfSupervisedTargets
    # Exact model-plane clocks and the lossless 1,865-vector bypass.  They are
    # optional only for explicit legacy unit fixtures; a selected E3 winner
    # refuses their absence.
    receive_clock_ns: Tensor | None = None
    static_features: Tensor | None = None
    selected_horizon_value: Tensor | None = None
    selected_horizon_valid: Tensor | None = None
    selected_horizon_schema_sha256: str | None = None

    @property
    def rows(self) -> int:
        return len(self.examples)

    @property
    def asset(self) -> str:
        return self.examples[0].asset

    @property
    def trading_day(self) -> int:
        return self.examples[0].trading_day

    @property
    def session_id(self) -> str:
        return self.examples[0].session_id

    @property
    def candidate_ids(self) -> tuple[str, ...]:
        return tuple(item.candidate_id for item in self.examples)

    def validate(self, teacher: TeacherStore | None = None) -> None:
        n = self.rows
        if n == 0:
            raise C.EntryV2Refusal("empty candidate session batch")
        session_keys = {
            (item.asset, item.trading_day, item.session_id) for item in self.examples
        }
        if len(session_keys) != 1:
            raise C.EntryV2Refusal("one batch must contain exactly one asset-session")
        C.guard_date(self.trading_day)
        if len(set(self.candidate_ids)) != n:
            raise C.EntryV2Refusal("duplicate candidate in session batch")
        if any(
            self.examples[i].decision_ts_ns > self.examples[i + 1].decision_ts_ns
            for i in range(n - 1)
        ):
            raise C.EntryV2Refusal("candidate examples are not chronological")
        if self.candidate_cutoffs.shape != (n,) or self.candidate_cutoffs.dtype not in (
            torch.int32,
            torch.int64,
        ):
            raise C.EntryV2Refusal("candidate_cutoffs must be an integer row vector")
        cutoffs = self.candidate_cutoffs.detach().cpu().to(torch.int64)
        if bool((cutoffs[1:] < cutoffs[:-1]).any()):
            raise C.EntryV2Refusal("candidate cutoffs are not chronological")
        expected = torch.tensor(
            [item.raw_prefix_ref.event_count for item in self.examples],
            dtype=torch.int64,
        )
        if not torch.equal(cutoffs, expected):
            raise C.EntryV2Refusal(
                "candidate cutoff is misaligned with public raw-prefix event_count"
            )
        if int(cutoffs[-1]) > int(self.event_continuous.shape[0]):
            raise C.EntryV2Refusal("candidate cutoff exceeds session event tensor")
        if self.event_continuous.ndim != 2 or not self.event_continuous.is_floating_point():
            raise C.EntryV2Refusal("event_continuous must be a floating matrix")
        if self.event_categorical.ndim != 2 or self.event_categorical.shape[0] != self.event_continuous.shape[0]:
            raise C.EntryV2Refusal("categorical event matrix is misaligned")
        if self.candidate_features.ndim != 2 or self.candidate_features.shape[0] != n:
            raise C.EntryV2Refusal("candidate feature matrix is misaligned")
        if not self.candidate_features.is_floating_point():
            raise C.EntryV2Refusal("candidate features must be floating point")
        if self.context_values.ndim != 4 or self.context_values.shape[0] != n:
            raise C.EntryV2Refusal("context tensor is misaligned")
        if not self.context_values.is_floating_point():
            raise C.EntryV2Refusal("context values must be floating point")
        if self.context_valid.shape != self.context_values.shape[:-1]:
            raise C.EntryV2Refusal("context mask is misaligned")
        if self.receive_clock_ns is not None:
            if (self.receive_clock_ns.dtype != torch.int64
                    or self.receive_clock_ns.shape != (self.event_continuous.shape[0],)):
                raise C.EntryV2Refusal("exact receive clock is misaligned")
            if self.receive_clock_ns.numel() > 1 and bool(
                    (self.receive_clock_ns[1:] < self.receive_clock_ns[:-1]).any()):
                raise C.EntryV2Refusal("exact receive clock decreases")
            decisions = torch.tensor(
                [row.decision_ts_ns for row in self.examples], dtype=torch.int64,
                device=self.receive_clock_ns.device,
            )
            if not torch.equal(torch.searchsorted(self.receive_clock_ns, decisions),
                               self.candidate_cutoffs.to(self.receive_clock_ns.device)):
                raise C.EntryV2Refusal("exact receive clock/cutoff complement differs")
        if self.static_features is not None:
            if (self.static_features.shape != (n, 1_865)
                    or not self.static_features.is_floating_point()
                    or not bool(torch.isfinite(self.static_features).all())):
                raise C.EntryV2Refusal("lossless static bypass must be finite [C,1865]")
        selected_horizon = (
            self.selected_horizon_value, self.selected_horizon_valid,
            self.selected_horizon_schema_sha256,
        )
        if any(value is not None for value in selected_horizon):
            if (any(value is None for value in selected_horizon)
                    or self.selected_horizon_value.shape
                        != (n, SELECTED_HORIZON_WIDTH)
                    or self.selected_horizon_valid.shape
                        != (n, SELECTED_HORIZON_WIDTH)
                    or self.selected_horizon_value.dtype != torch.float64
                    or self.selected_horizon_schema_sha256
                        != SELECTED_HORIZON_SCHEMA_SHA256):
                raise C.EntryV2Refusal(
                    "selected horizon carrier/schema is incomplete")
            selected_valid = self.selected_horizon_valid.to(dtype=torch.bool)
            if bool(selected_valid.any()) and not bool(torch.isfinite(
                    self.selected_horizon_value[selected_valid]).all()):
                raise C.EntryV2Refusal("selected horizon target is non-finite")
        devices = {
            tensor.device
            for tensor in (
                self.event_continuous,
                self.event_categorical,
                self.candidate_cutoffs,
                self.candidate_features,
                self.context_values,
                self.context_type_ids,
                self.context_valid,
                self.self_supervised.horizon_value,
                self.self_supervised.horizon_valid,
                self.self_supervised.phase_class,
                self.self_supervised.phase_valid,
            )
        }
        if self.receive_clock_ns is not None:
            devices.add(self.receive_clock_ns.device)
        if self.static_features is not None:
            devices.add(self.static_features.device)
        if self.selected_horizon_value is not None:
            devices.add(self.selected_horizon_value.device)
            devices.add(self.selected_horizon_valid.device)
        if len(devices) != 1:
            raise C.EntryV2Refusal("all tensors in a session batch must share a device")
        self.self_supervised.validate(n)
        if teacher is not None:
            joined = teacher.join_training(self.examples)
            if tuple(label.candidate_id for _, label in joined) != self.candidate_ids:
                raise C.EntryV2Refusal("teacher join changed candidate row order")

    def to(self, device: torch.device) -> "EntrySessionBatch":
        return EntrySessionBatch(
            examples=self.examples,
            event_continuous=self.event_continuous.to(device),
            event_categorical=self.event_categorical.to(device),
            candidate_cutoffs=self.candidate_cutoffs.to(device),
            candidate_features=self.candidate_features.to(device),
            context_values=self.context_values.to(device),
            context_type_ids=self.context_type_ids.to(device),
            context_valid=self.context_valid.to(device),
            self_supervised=self.self_supervised.to(device),
            receive_clock_ns=(None if self.receive_clock_ns is None
                              else self.receive_clock_ns.to(device)),
            static_features=(None if self.static_features is None
                             else self.static_features.to(device)),
            selected_horizon_value=(None if self.selected_horizon_value is None
                                    else self.selected_horizon_value.to(device)),
            selected_horizon_valid=(None if self.selected_horizon_valid is None
                                    else self.selected_horizon_valid.to(device)),
            selected_horizon_schema_sha256=self.selected_horizon_schema_sha256,
        )


@dataclass(frozen=True)
class EntrySessionSpec:
    """Metadata-only asset-session; event tensors exist only while materialized."""

    source: "SessionEventSource"
    examples: tuple[CausalEntryExample, ...]
    candidate_cutoffs: Tensor
    candidate_features: Tensor
    context_values: Tensor
    context_type_ids: Tensor
    context_valid: Tensor
    self_supervised: SelfSupervisedTargets
    static_features: Tensor | None = None
    selected_horizon_value: Tensor | None = None
    selected_horizon_valid: Tensor | None = None
    selected_horizon_schema_sha256: str | None = None

    @property
    def rows(self) -> int:
        return len(self.examples)

    @property
    def asset(self) -> str:
        return self.examples[0].asset

    @property
    def trading_day(self) -> int:
        return self.examples[0].trading_day

    @property
    def session_id(self) -> str:
        return self.examples[0].session_id

    @property
    def candidate_ids(self) -> tuple[str, ...]:
        return tuple(item.candidate_id for item in self.examples)

    def validate(self, teacher: TeacherStore | None = None) -> None:
        n = self.rows
        if n == 0:
            raise C.EntryV2Refusal("empty candidate session specification")
        session_keys = {
            (item.asset, item.trading_day, item.session_id) for item in self.examples
        }
        if len(session_keys) != 1:
            raise C.EntryV2Refusal(
                "one session specification must contain exactly one asset-session"
            )
        C.guard_date(self.trading_day)
        if len(set(self.candidate_ids)) != n:
            raise C.EntryV2Refusal("duplicate candidate in session specification")
        if any(
            self.examples[i].decision_ts_ns > self.examples[i + 1].decision_ts_ns
            for i in range(n - 1)
        ):
            raise C.EntryV2Refusal("candidate examples are not chronological")
        if self.candidate_cutoffs.shape != (n,) or self.candidate_cutoffs.dtype not in (
            torch.int32,
            torch.int64,
        ):
            raise C.EntryV2Refusal("candidate_cutoffs must be an integer row vector")
        cutoffs = self.candidate_cutoffs.detach().cpu().to(torch.int64)
        if bool((cutoffs[1:] < cutoffs[:-1]).any()):
            raise C.EntryV2Refusal("candidate cutoffs are not chronological")
        expected = torch.tensor(
            [item.raw_prefix_ref.event_count for item in self.examples],
            dtype=torch.int64,
        )
        if not torch.equal(cutoffs, expected):
            raise C.EntryV2Refusal(
                "candidate cutoff is misaligned with public raw-prefix event_count"
            )
        if int(cutoffs[-1]) > int(self.source.max_cutoff):
            raise C.EntryV2Refusal(
                "session specification cutoff exceeds all-candidate source pin"
            )
        if any(
            (item.asset, item.trading_day, item.locked_iid)
            != (self.source.asset, self.source.d8, self.source.locked_iid)
            for item in self.examples
        ):
            raise C.EntryV2Refusal("session specification differs from source identity")
        if self.candidate_features.ndim != 2 or self.candidate_features.shape[0] != n:
            raise C.EntryV2Refusal("candidate feature matrix is misaligned")
        if not self.candidate_features.is_floating_point():
            raise C.EntryV2Refusal("candidate features must be floating point")
        if self.context_values.ndim != 4 or self.context_values.shape[0] != n:
            raise C.EntryV2Refusal("context tensor is misaligned")
        if not self.context_values.is_floating_point():
            raise C.EntryV2Refusal("context values must be floating point")
        if self.context_valid.shape != self.context_values.shape[:-1]:
            raise C.EntryV2Refusal("context mask is misaligned")
        if self.static_features is not None and (
                self.static_features.shape != (n, 1_865)
                or not self.static_features.is_floating_point()
                or not bool(torch.isfinite(self.static_features).all())):
            raise C.EntryV2Refusal("lossless static bypass must be finite [C,1865]")
        selected_horizon = (
            self.selected_horizon_value, self.selected_horizon_valid,
            self.selected_horizon_schema_sha256,
        )
        if any(value is not None for value in selected_horizon):
            if (any(value is None for value in selected_horizon)
                    or self.selected_horizon_value.shape
                        != (n, SELECTED_HORIZON_WIDTH)
                    or self.selected_horizon_valid.shape
                        != (n, SELECTED_HORIZON_WIDTH)
                    or self.selected_horizon_value.dtype != torch.float64
                    or self.selected_horizon_schema_sha256
                        != SELECTED_HORIZON_SCHEMA_SHA256):
                raise C.EntryV2Refusal(
                    "selected horizon specification/schema is incomplete")
            selected_valid = self.selected_horizon_valid.to(dtype=torch.bool)
            if bool(selected_valid.any()) and not bool(torch.isfinite(
                    self.selected_horizon_value[selected_valid]).all()):
                raise C.EntryV2Refusal("selected horizon target is non-finite")
        devices = {
            tensor.device
            for tensor in (
                self.candidate_cutoffs,
                self.candidate_features,
                self.context_values,
                self.context_type_ids,
                self.context_valid,
                self.self_supervised.horizon_value,
                self.self_supervised.horizon_valid,
                self.self_supervised.phase_class,
                self.self_supervised.phase_valid,
            )
        }
        if self.static_features is not None:
            devices.add(self.static_features.device)
        if self.selected_horizon_value is not None:
            devices.add(self.selected_horizon_value.device)
            devices.add(self.selected_horizon_valid.device)
        if len(devices) != 1:
            raise C.EntryV2Refusal(
                "all metadata tensors in a session specification must share a device"
            )
        self.self_supervised.validate(n)
        if teacher is not None:
            joined = teacher.join_training(self.examples)
            if tuple(label.candidate_id for _, label in joined) != self.candidate_ids:
                raise C.EntryV2Refusal("teacher join changed candidate row order")


@dataclass(frozen=True)
class ReplayCalibrationData:
    """Target-plane outcomes and the complete all-session denominator.

    Empty/no-candidate sessions still appear in ``expected_sessions``.
    Outcomes are joined by immutable candidate id and never copied into model
    inputs or normalization statistics.
    """

    outcomes: Mapping[str, ReplayOutcome]
    expected_sessions: tuple[SessionRef, ...]
    regime_declarations: tuple[AssetDayRegime, ...] = ()

    def validate(self, batches: Sequence[EntrySessionSpec]) -> None:
        if not self.expected_sessions or len(self.expected_sessions) != len(
            set(self.expected_sessions)
        ):
            raise C.EntryV2Refusal("replay denominator is empty or duplicated")
        expected = set(self.expected_sessions)
        asset_days = {(session.asset, session.trading_day)
                      for session in self.expected_sessions}
        regime_keys = {
            (row.asset, row.trading_day) for row in self.regime_declarations
        }
        if len(regime_keys) != len(self.regime_declarations):
            raise C.EntryV2Refusal("asset-day regime declarations are duplicated")
        if not regime_keys.issubset(asset_days):
            raise C.EntryV2Refusal(
                "asset-day regime declaration lies outside the denominator"
            )
        for session in self.expected_sessions:
            C.guard_date(session.trading_day)
            if not C.is_denominator_day(session.asset, session.trading_day):
                raise C.EntryV2Refusal(
                    "replay denominator contains a QRE2CAL1-excluded asset-day"
                )
        for batch in batches:
            if batch.examples[0].session not in expected:
                raise C.EntryV2Refusal(
                    f"candidate session absent from replay denominator: {batch.session_id}"
                )
            for candidate_id in batch.candidate_ids:
                outcome = self.outcomes.get(candidate_id)
                if outcome is None or outcome.candidate_id != candidate_id:
                    raise C.EntryV2Refusal(
                        f"replay outcome missing/misaligned: {candidate_id}"
                    )

    def sessions_for(
        self, days: Iterable[int], *, asset: str | None = None
    ) -> tuple[SessionRef, ...]:
        allowed = set(int(day) for day in days)
        if not allowed:
            raise C.EntryV2Refusal("fold stage has no declared days")
        selected = tuple(
            session
            for session in self.expected_sessions
            if session.trading_day in allowed
            and (asset is None or session.asset == asset)
        )
        if not selected:
            raise C.EntryV2Refusal("fold stage has no replay denominator sessions")
        expected_keys = {
            (name, day)
            for day in allowed
            for name in ((asset,) if asset is not None else C.ASSETS)
            if C.is_denominator_day(name, day)
        }
        selected_keys = {(session.asset, session.trading_day)
                         for session in selected}
        if selected_keys != expected_keys:
            missing = sorted(expected_keys - selected_keys)
            raise C.EntryV2Refusal(
                "fold denominator omits declared eligible asset-days: "
                f"{missing[:5]}"
            )
        return selected


    def regimes_for(self, days: Iterable[int]) -> tuple[AssetDayRegime, ...]:
        sessions = self.sessions_for(days)
        expected = {(session.asset, session.trading_day) for session in sessions}
        selected = tuple(sorted(
            row for row in self.regime_declarations
            if row.trading_day in {session.trading_day for session in sessions}
        ))
        present = {(row.asset, row.trading_day) for row in selected}
        if present != expected:
            missing = sorted(expected - present)
            raise C.EntryV2Refusal(
                "causal weak-regime declaration unresolved for asset-days: "
                f"{missing[:5]}"
            )
        return selected


class CandidateOraclePreflightRefusal(C.EntryV2Refusal):
    """A failed exact candidate ceiling carrying its complete measured receipt."""

    def __init__(self, message: str, evidence: Mapping[str, Any]) -> None:
        super().__init__(message)
        self.evidence = MappingProxyType(dict(evidence))


class _Moments:
    """Deterministic float64 column moments over a fixed sorted traversal."""

    def __init__(self, width: int) -> None:
        self.count = torch.zeros(width, dtype=torch.float64)
        self.total = torch.zeros(width, dtype=torch.float64)
        self.square = torch.zeros(width, dtype=torch.float64)

    def update(self, value: Tensor, valid: Tensor | None = None) -> None:
        x = value.detach().reshape(-1, value.shape[-1]).to("cpu", torch.float64)
        if valid is None:
            mask = torch.ones_like(x, dtype=torch.bool)
        else:
            mask = valid.detach().reshape(-1, valid.shape[-1]).to("cpu", torch.bool)
            if mask.shape != x.shape:
                raise C.EntryV2Refusal("normalization mask shape mismatch")
        if bool(mask.any()) and not bool(torch.isfinite(x[mask]).all()):
            raise C.EntryV2Refusal("normalization input contains a non-finite value")
        safe = torch.where(mask, x, torch.zeros_like(x))
        self.count += mask.sum(dim=0)
        self.total += safe.sum(dim=0)
        self.square += safe.square().sum(dim=0)

    def finish(self, name: str) -> tuple[tuple[float, ...], tuple[float, ...]]:
        if bool((self.count == 0).any()):
            raise C.EntryV2Refusal(f"{name} normalization has an empty column")
        mean = self.total / self.count
        variance = (self.square / self.count - mean.square()).clamp_min(0.0)
        scale = variance.sqrt()
        scale = torch.where(scale >= 1.0e-8, scale, torch.ones_like(scale))
        return tuple(mean.tolist()), tuple(scale.tolist())


@dataclass(frozen=True)
class TrainFoldNormalizer:
    event_mean: tuple[float, ...]
    event_scale: tuple[float, ...]
    candidate_mean: tuple[float, ...]
    candidate_scale: tuple[float, ...]
    context_mean: tuple[float, ...]
    context_scale: tuple[float, ...]
    horizon_mean: tuple[float, ...]
    horizon_scale: tuple[float, ...]
    fit_days: tuple[int, ...]
    fit_candidate_sha256: str
    model_input_binding: ModelInputBinding
    receipt_sha256: str

    @classmethod
    def fit(
        cls,
        batches: Sequence[EntrySessionSpec],
        fit_days: Iterable[int],
        model_input_binding: ModelInputBinding,
    ) -> "TrainFoldNormalizer":
        model_input_binding.validate()
        allowed = tuple(sorted(set(int(day) for day in fit_days)))
        if not allowed:
            raise C.EntryV2Refusal("normalizer has no fit days")
        for day in allowed:
            C.guard_date(day)
        selected = [batch for batch in batches if batch.trading_day in set(allowed)]
        selected.sort(key=_batch_key)
        if not selected:
            raise C.EntryV2Refusal("normalizer has no fit batches")
        event = _Moments(len(model_input_binding.event_continuous_fields))
        candidate = _Moments(selected[0].candidate_features.shape[-1])
        context = _Moments(selected[0].context_values.shape[-1])
        horizon = _Moments(len(HORIZONS_SECONDS))
        candidate_ids: list[str] = []
        for spec in selected:
            spec.validate()
            candidate.update(spec.candidate_features)
            context_mask = spec.context_valid[..., None].expand_as(spec.context_values)
            context.update(spec.context_values, context_mask)
            horizon.update(
                spec.self_supervised.horizon_value,
                spec.self_supervised.horizon_valid,
            )
            with spec.source.open_batch(spec) as batch:
                batch.validate()
                if (int(batch.event_continuous.shape[-1])
                        != len(model_input_binding.event_continuous_fields)):
                    raise C.EntryV2Refusal(
                        "event continuous width differs from bound V2 field order"
                    )
                if (int(batch.event_categorical.shape[-1])
                        != len(model_input_binding.event_categorical_fields)):
                    raise C.EntryV2Refusal(
                        "event categorical width differs from bound V2 field order"
                    )
                event.update(batch.event_continuous)
            del batch
            candidate_ids.extend(spec.candidate_ids)
        if len(candidate_ids) != len(set(candidate_ids)):
            raise C.EntryV2Refusal("candidate reused while fitting normalizer")
        em, es = event.finish("event")
        cm, cs = candidate.finish("candidate")
        xm, xs = context.finish("context")
        hm, hs = horizon.finish("horizon")
        candidate_hash = C.object_sha256(sorted(candidate_ids))
        payload = {
            "schema": "entry-v2-train-normalizer-v3",
            "event_mean": em,
            "event_scale": es,
            "candidate_mean": cm,
            "candidate_scale": cs,
            "context_mean": xm,
            "context_scale": xs,
            "horizon_mean": hm,
            "horizon_scale": hs,
            "fit_days": allowed,
            "fit_candidate_sha256": candidate_hash,
            "model_input_binding": model_input_binding.as_dict(),
        }
        return cls(
            em, es, cm, cs, xm, xs, hm, hs, allowed, candidate_hash,
            model_input_binding, C.object_sha256(payload)
        )

    def transform(
        self, batch: EntrySessionBatch, device: torch.device
    ) -> EntrySessionBatch:
        def zscore(value: Tensor, mean: tuple[float, ...], scale: tuple[float, ...]) -> Tensor:
            mu = value.new_tensor(mean)
            sigma = value.new_tensor(scale)
            # Raw integer-derived event features may arrive as float64 so the
            # fold subtraction preserves tick differences.  The lossless
            # clock split in event_pack.py makes the normalized result safe to
            # cross the GPU boundary as float32/BF16.
            return ((value - mu) / sigma).to(dtype=torch.float32)

        event = zscore(batch.event_continuous, self.event_mean, self.event_scale)
        candidate = zscore(
            batch.candidate_features, self.candidate_mean, self.candidate_scale
        )
        context = zscore(batch.context_values, self.context_mean, self.context_scale)
        context = torch.where(
            batch.context_valid[..., None], context, torch.zeros_like(context)
        )
        horizon = zscore(
            batch.self_supervised.horizon_value,
            self.horizon_mean,
            self.horizon_scale,
        )
        horizon = torch.where(
            batch.self_supervised.horizon_valid, horizon, torch.zeros_like(horizon)
        )
        normalized = replace(
            batch,
            event_continuous=event,
            candidate_features=candidate,
            context_values=context,
            self_supervised=replace(batch.self_supervised, horizon_value=horizon),
        )
        return normalized.to(device)

    def receipt(self) -> dict[str, Any]:
        return {
            "schema": "entry-v2-train-normalizer-v3",
            "event_mean": self.event_mean,
            "event_scale": self.event_scale,
            "candidate_mean": self.candidate_mean,
            "candidate_scale": self.candidate_scale,
            "context_mean": self.context_mean,
            "context_scale": self.context_scale,
            "horizon_mean": self.horizon_mean,
            "horizon_scale": self.horizon_scale,
            "fit_days": self.fit_days,
            "fit_candidate_sha256": self.fit_candidate_sha256,
            "model_input_binding": self.model_input_binding.as_dict(),
            "receipt_sha256": self.receipt_sha256,
        }


@dataclass(frozen=True)
class SelectedFoldNormalizer:
    """TRAIN-only normalizer over the cached expanded selected-winner view."""
    event_mean: tuple[float, ...]
    event_scale: tuple[float, ...]
    candidate_mean: tuple[float, ...]
    candidate_scale: tuple[float, ...]
    context_mean: tuple[float, ...]
    context_scale: tuple[float, ...]
    horizon_mean: tuple[float, ...]
    horizon_scale: tuple[float, ...]
    static_mean: tuple[float, ...]
    static_scale: tuple[float, ...]
    fit_days: tuple[int, ...]
    fit_candidate_sha256: str
    model_input_binding: ModelInputBinding
    expanded_schema_sha256: str
    expanded_transform_law_sha256: str
    selected_horizon_schema_sha256: str
    use_static: bool
    receipt_sha256: str
    event_transform: Any

    @classmethod
    def fit(cls, batches: Sequence[EntrySessionSpec], fit_days: Iterable[int],
            model_input_binding: ModelInputBinding, event_transform: Any, *,
            use_static: bool,
            ) -> "SelectedFoldNormalizer":
        model_input_binding.validate(); allowed = tuple(sorted(set(map(int, fit_days))))
        selected = sorted((row for row in batches if row.trading_day in set(allowed)),
                          key=_batch_key)
        if not selected:
            raise C.EntryV2Refusal("selected normalizer has no TRAIN rows")
        if event_transform.base_binding_sha256 != model_input_binding.binding_sha256:
            raise C.EntryV2Refusal("expanded transform is not bound to base corpus")
        if event_transform.normalization != "UNNORMALIZED_CANONICAL":
            raise C.EntryV2Refusal("expanded transform must be unnormalized canonical fields")
        event = None
        candidate = _Moments(selected[0].candidate_features.shape[-1])
        context = _Moments(selected[0].context_values.shape[-1])
        horizon = _Moments(SELECTED_HORIZON_WIDTH); static = _Moments(1_865)
        candidate_ids: list[str] = []
        for spec in selected:
            if use_static and spec.static_features is None:
                raise C.EntryV2Refusal("selected normalizer lacks static bypass")
            candidate.update(spec.candidate_features)
            context.update(spec.context_values,
                           spec.context_valid[..., None].expand_as(spec.context_values))
            if (spec.selected_horizon_value is None
                    or spec.selected_horizon_valid is None
                    or spec.selected_horizon_schema_sha256
                        != SELECTED_HORIZON_SCHEMA_SHA256):
                raise C.EntryV2Refusal(
                    "selected normalizer lacks the six-coordinate target")
            horizon.update(spec.selected_horizon_value,
                           spec.selected_horizon_valid)
            if use_static:
                assert spec.static_features is not None
                static.update(spec.static_features)
            with spec.source.open_batch(spec) as batch:
                view = event_transform.transform(batch)
                if (view.schema_sha256 != event_transform.schema_sha256
                        or view.transform_law_sha256 != event_transform.transform_law_sha256
                        or view.base_binding_sha256 != model_input_binding.binding_sha256
                        or view.normalization != "UNNORMALIZED_CANONICAL"
                        or view.continuous.shape[0] != batch.event_continuous.shape[0]
                        or view.categorical.shape[0] != batch.event_categorical.shape[0]):
                    raise C.EntryV2Refusal("expanded event view identity/rows differ")
                if event is None:
                    event = _Moments(view.continuous.shape[-1])
                event.update(view.continuous)
            candidate_ids.extend(spec.candidate_ids)
        assert event is not None
        em, es = event.finish("expanded_event"); cm, cs = candidate.finish("candidate")
        xm, xs = context.finish("context"); hm, hs = horizon.finish("horizon")
        if use_static:
            sm, ss = static.finish("static")
        else:
            sm, ss = tuple([0.0] * 1_865), tuple([1.0] * 1_865)
        candidate_hash = C.object_sha256(sorted(candidate_ids))
        payload = {
            "schema": "entry-v2-selected-fold-normalizer-v1",
            "event_mean": em, "event_scale": es,
            "candidate_mean": cm, "candidate_scale": cs,
            "context_mean": xm, "context_scale": xs,
            "horizon_mean": hm, "horizon_scale": hs,
            "static_mean": sm, "static_scale": ss, "fit_days": allowed,
            "fit_candidate_sha256": candidate_hash,
            "model_input_binding": model_input_binding.as_dict(),
            "expanded_schema_sha256": event_transform.schema_sha256,
            "expanded_transform_law_sha256": event_transform.transform_law_sha256,
            "selected_horizon_schema_sha256": SELECTED_HORIZON_SCHEMA_SHA256,
            "selected_horizon_coordinates": list(SELECTED_HORIZON_COORDINATES),
            "use_static": bool(use_static),
        }
        return cls(em, es, cm, cs, xm, xs, hm, hs, sm, ss, allowed,
                   candidate_hash, model_input_binding,
                   event_transform.schema_sha256, event_transform.transform_law_sha256,
                   SELECTED_HORIZON_SCHEMA_SHA256, bool(use_static),
                   C.object_sha256(payload), event_transform)

    def transform(self, batch: EntrySessionBatch, device: torch.device) -> EntrySessionBatch:
        view = self.event_transform.transform(batch)
        if view.normalization != "UNNORMALIZED_CANONICAL":
            raise C.EntryV2Refusal("expanded event view was pre-normalized")
        if (view.schema_sha256 != self.expanded_schema_sha256
                or view.transform_law_sha256 != self.expanded_transform_law_sha256
                or view.base_binding_sha256 != self.model_input_binding.binding_sha256):
            raise C.EntryV2Refusal("expanded event transform drifted after fit")
        def z(value: Tensor, mean: tuple[float, ...], scale: tuple[float, ...]) -> Tensor:
            return ((value - value.new_tensor(mean)) / value.new_tensor(scale)).float()
        context = z(batch.context_values, self.context_mean, self.context_scale)
        context = torch.where(batch.context_valid[..., None], context,
                              torch.zeros_like(context))
        if (batch.selected_horizon_value is None
                or batch.selected_horizon_valid is None
                or batch.selected_horizon_schema_sha256
                    != self.selected_horizon_schema_sha256):
            raise C.EntryV2Refusal(
                "selected batch lacks the frozen six-coordinate target")
        horizon = z(batch.selected_horizon_value,
                    self.horizon_mean, self.horizon_scale)
        horizon = torch.where(batch.selected_horizon_valid, horizon,
                              torch.zeros_like(horizon))
        if self.use_static and batch.static_features is None:
            raise C.EntryV2Refusal("selected batch lacks static bypass")
        static = (None if not self.use_static else
                  z(batch.static_features, self.static_mean, self.static_scale))
        normalized = replace(
            batch, event_continuous=z(view.continuous, self.event_mean, self.event_scale),
            event_categorical=view.categorical,
            candidate_features=z(batch.candidate_features,
                                 self.candidate_mean, self.candidate_scale),
            context_values=context,
            static_features=static,
            selected_horizon_value=horizon,
            selected_horizon_valid=batch.selected_horizon_valid,
            selected_horizon_schema_sha256=self.selected_horizon_schema_sha256,
        )
        return normalized.to(device)

    def receipt(self) -> dict[str, Any]:
        return {
            "schema": "entry-v2-selected-fold-normalizer-v1",
            "fit_days": self.fit_days,
            "fit_candidate_sha256": self.fit_candidate_sha256,
            "model_input_binding": self.model_input_binding.as_dict(),
            "expanded_schema_sha256": self.expanded_schema_sha256,
            "expanded_transform_law_sha256": self.expanded_transform_law_sha256,
            "selected_horizon_schema_sha256": self.selected_horizon_schema_sha256,
            "selected_horizon_coordinates": list(SELECTED_HORIZON_COORDINATES),
            "selected_horizon_mean": self.horizon_mean,
            "selected_horizon_scale": self.horizon_scale,
            "use_static": self.use_static,
            "receipt_sha256": self.receipt_sha256,
        }


@dataclass
class LearningOutput:
    core: EntryModelOutput
    horizon_value: Tensor
    phase_logits: Tensor
    rank_value: Tensor
    mfe_quantiles: Tensor
    time_to_peak_value: Tensor
    selected_state: Tensor | None = None
    selected_raw_memory: Tensor | None = None
    selected_ordinal_logits: Tensor | None = None


class EntryLearningSystem(nn.Module):
    """Full-prefix encoder plus fixed self-supervised projection heads."""

    def __init__(self, encoder: FullPrefixEntryModel, n_phase_classes: int = 8) -> None:
        super().__init__()
        if encoder.n_value_bins != 5:
            raise C.EntryV2Refusal("entry learning fixes the five oracle value bins")
        if int(n_phase_classes) < 2:
            raise C.EntryV2Refusal("entry learning requires at least two phases")
        self.encoder = encoder
        self.horizon_head = nn.Linear(512, len(HORIZONS_SECONDS))
        self.phase_head = nn.Linear(512, int(n_phase_classes))
        self.rank_head = nn.Linear(512, 1)
        self.mfe_quantile_head = nn.Linear(512, 3)
        self.time_to_peak_head = nn.Linear(512, 1)

    def forward(self, batch: EntrySessionBatch) -> LearningOutput:
        core = self.encoder(
            event_continuous=batch.event_continuous,
            event_categorical=batch.event_categorical,
            candidate_cutoffs=batch.candidate_cutoffs,
            candidate_features=batch.candidate_features,
            context_values=batch.context_values,
            context_type_ids=batch.context_type_ids,
            context_valid=batch.context_valid,
            asset_idx=C.ASSET_INDEX[batch.asset],
        )
        return LearningOutput(
            core=core,
            horizon_value=self.horizon_head(core.embedding),
            phase_logits=self.phase_head(core.embedding),
            rank_value=self.rank_head(core.embedding).squeeze(-1),
            mfe_quantiles=self.mfe_quantile_head(core.embedding),
            time_to_peak_value=self.time_to_peak_head(core.embedding).squeeze(-1),
        )


@dataclass(frozen=True)
class TeacherTargets:
    value_bin: Tensor
    value: Tensor
    top3: Tensor
    rank: Tensor
    mfe: Tensor
    mae: Tensor
    wall: Tensor
    time_to_peak: Tensor
    take_target: Tensor
    action_loss_mask: Tensor


@dataclass(frozen=True)
class SupervisionWeights:
    """Fit-fold-only class balance for rare payers, walls, and top ranks."""

    value_bin: tuple[float, ...]
    top3_pos: float
    wall_pos: float
    take_pos: float

    @property
    def sha256(self) -> str:
        return C.object_sha256(asdict(self))


def _fit_supervision_weights(
    batches: Sequence[EntrySessionSpec], teacher: TeacherStore
) -> SupervisionWeights:
    labels = [label for batch in batches
              for _example, label in teacher.join_training(batch.examples)]
    if not labels:
        raise C.EntryV2Refusal("cannot balance an empty fit teacher")
    bins = np.asarray([VALUE_BIN_INDEX[label.value_bin] for label in labels])
    counts = np.bincount(bins, minlength=5).astype(np.float64)
    value_weight = np.clip(len(labels) / (5.0 * np.maximum(counts, 1.0)),
                           0.25, 20.0)

    def binary(name: str, *, action_only: bool = False) -> float:
        selected = (
            [label for label in labels if label.action_loss_mask]
            if action_only else labels
        )
        if not selected:
            raise C.EntryV2Refusal("fit teacher has no action-supervised rows")
        values = np.asarray([bool(getattr(label, name)) for label in selected], int)
        positive = int(values.sum())
        negative = len(values) - positive
        if positive == 0 or negative == 0:
            return 1.0
        return float(np.clip(negative / positive, 1.0, 50.0))

    return SupervisionWeights(
        tuple(float(value) for value in value_weight),
        binary("top3"),
        binary("wall_hit"),
        binary("take_target", action_only=True),
    )


def teacher_targets(
    batch: EntrySessionBatch, teacher: TeacherStore, device: torch.device
) -> TeacherTargets:
    joined = teacher.join_training(batch.examples)
    labels: tuple[TeacherLabel, ...] = tuple(label for _, label in joined)
    if tuple(label.candidate_id for label in labels) != batch.candidate_ids:
        raise C.EntryV2Refusal("candidate/teacher row alignment failed")
    return TeacherTargets(
        value_bin=torch.tensor(
            [VALUE_BIN_INDEX[label.value_bin] for label in labels],
            dtype=torch.int64,
            device=device,
        ),
        value=torch.tensor(
            [label.cert_close_usd / VALUE_SCALE_USD for label in labels],
            dtype=torch.float32,
            device=device,
        ),
        top3=torch.tensor(
            [label.top3 for label in labels], dtype=torch.float32, device=device
        ),
        rank=torch.tensor(
            [np.log1p(label.rank) for label in labels],
            dtype=torch.float32,
            device=device,
        ),
        mfe=torch.tensor(
            [label.mfe_usd / MFE_SCALE_USD for label in labels],
            dtype=torch.float32,
            device=device,
        ),
        mae=torch.tensor(
            [label.mae_usd / MAE_SCALE_USD for label in labels],
            dtype=torch.float32,
            device=device,
        ),
        wall=torch.tensor(
            [label.wall_hit for label in labels], dtype=torch.float32, device=device
        ),
        time_to_peak=torch.tensor(
            [label.time_to_peak_sec / TIME_TO_PEAK_SCALE_SECONDS
             for label in labels],
            dtype=torch.float32,
            device=device,
        ),
        take_target=torch.tensor(
            [label.take_target for label in labels],
            dtype=torch.float32,
            device=device,
        ),
        action_loss_mask=torch.tensor(
            [label.action_loss_mask for label in labels],
            dtype=torch.bool,
            device=device,
        ),
    )


@dataclass
class LossBreakdown:
    total: Tensor
    components: Mapping[str, Tensor]


def _quantile_loss(prediction: Tensor, target: Tensor) -> Tensor:
    quantiles = prediction.new_tensor((0.1, 0.5, 0.9))[None, :]
    error = target[:, None] - prediction
    return torch.maximum(quantiles * error, (quantiles - 1.0) * error).mean()


def fixed_multitask_loss(
    output: LearningOutput,
    target: TeacherTargets,
    self_supervised: SelfSupervisedTargets,
    supervision_weights: SupervisionWeights,
    selection: Tensor | None = None,
) -> LossBreakdown:
    """Full-population oracle plus fold-causal auxiliary objective.

    The staged trainer calls the two component builders separately so the
    order is fixed.  This public helper remains useful for one-shot numerical
    checks and deliberately excludes the matched third-stage contrast.
    """

    rows = output.core.embedding.shape[0]
    choose = (
        torch.ones(rows, dtype=torch.bool, device=output.core.embedding.device)
        if selection is None
        else selection.to(device=output.core.embedding.device, dtype=torch.bool)
    )
    if choose.shape != (rows,) or not bool(choose.any()):
        raise C.EntryV2Refusal("loss selection is empty or misaligned")
    components = {
        **_oracle_components(
            output, target, supervision_weights, choose
        ),
        **_self_supervised_components(output, self_supervised, choose),
    }
    total = sum(LOSS_WEIGHTS[name] * value for name, value in components.items())
    return LossBreakdown(total=total, components=MappingProxyType(components))


def _oracle_components(
    output: LearningOutput,
    target: TeacherTargets,
    supervision_weights: SupervisionWeights,
    choose: Tensor,
    selected_fit_weights: Mapping[str, Tensor] | None = None,
) -> dict[str, Tensor]:
    core = output.core
    action_choose = choose & target.action_loss_mask.to(dtype=torch.bool)
    if selected_fit_weights is not None:
        required = {
            "ordinal", "value_bins", "value_quantiles", "expected_value", "top3", "rank",
            "mfe_quantiles", "mae_quantiles", "wall", "time_to_peak",
            "take_target",
        }
        rows = int(core.embedding.shape[0])
        if set(selected_fit_weights) != required or any(
            value.shape != (rows,) or not bool(torch.isfinite(value).all())
            or bool((value < 0).any())
            for value in selected_fit_weights.values()
        ):
            raise C.EntryV2Refusal("selected oracle fit weights are incomplete")

        def weighted(name: str, loss: Tensor, mask: Tensor = choose) -> Tensor:
            weight = selected_fit_weights[name][mask].float()
            if loss.shape != weight.shape or not bool(weight.sum() > 0):
                raise C.EntryV2Refusal(
                    f"selected {name} fit weights are empty or misaligned"
                )
            return (loss.float() * weight).sum() / weight.sum()

        action_loss = (
            weighted("take_target", F.binary_cross_entropy_with_logits(
                core.take_logit[action_choose].float(),
                target.take_target[action_choose], reduction="none"), action_choose)
            if bool(action_choose.any()) else core.take_logit.float().sum() * 0.0
        )
        quantiles = core.value_quantiles.new_tensor((0.1, 0.5, 0.9))[None, :]
        value_error = target.value[choose, None] - core.value_quantiles[choose].float()
        mfe_error = target.mfe[choose, None] - output.mfe_quantiles[choose].float()
        mae_error = target.mae[choose, None] - core.mae_quantiles[choose].float()
        quantile_rows = lambda error: torch.maximum(
            quantiles * error, (quantiles - 1.0) * error
        ).mean(dim=1)
        if (output.selected_ordinal_logits is None
                or output.selected_ordinal_logits.shape != (rows, 4)):
            raise C.EntryV2Refusal(
                "selected cumulative ordinal head is absent or misaligned")
        ordinal_target = (
            target.value_bin[choose, None]
            >= torch.arange(1, 5, device=target.value_bin.device)[None, :]
        ).float()
        return {
            "ordinal": weighted("ordinal", F.binary_cross_entropy_with_logits(
                output.selected_ordinal_logits[choose].float(), ordinal_target,
                reduction="none").mean(1)),
            "value_bins": weighted("value_bins", F.cross_entropy(
                core.value_bin_logits[choose].float(), target.value_bin[choose],
                reduction="none")),
            "value_quantiles": weighted(
                "value_quantiles", quantile_rows(value_error)),
            "expected_value": weighted("expected_value", F.smooth_l1_loss(
                core.expected_value[choose].float(), target.value[choose],
                reduction="none")),
            "top3": weighted("top3", F.binary_cross_entropy_with_logits(
                core.top3_logit[choose].float(), target.top3[choose],
                reduction="none")),
            "rank": weighted("rank", F.smooth_l1_loss(
                output.rank_value[choose].float(), target.rank[choose],
                reduction="none")),
            "mfe_quantiles": weighted(
                "mfe_quantiles", quantile_rows(mfe_error)),
            "mae_quantiles": weighted(
                "mae_quantiles", quantile_rows(mae_error)),
            "wall": weighted("wall", F.binary_cross_entropy_with_logits(
                core.wall_logit[choose].float(), target.wall[choose],
                reduction="none")),
            "time_to_peak": weighted("time_to_peak", F.smooth_l1_loss(
                output.time_to_peak_value[choose].float(),
                target.time_to_peak[choose], reduction="none")),
            "take_target": action_loss,
        }
    action_loss = (
        F.binary_cross_entropy_with_logits(
            core.take_logit[action_choose].float(),
            target.take_target[action_choose],
            pos_weight=core.take_logit.new_tensor(
                supervision_weights.take_pos, dtype=torch.float32),
        )
        if bool(action_choose.any())
        else core.take_logit.float().sum() * 0.0
    )
    return {
        "value_bins": F.cross_entropy(
            core.value_bin_logits[choose].float(), target.value_bin[choose],
            weight=core.value_bin_logits.new_tensor(
                supervision_weights.value_bin, dtype=torch.float32),
        ),
        "value_quantiles": _quantile_loss(
            core.value_quantiles[choose].float(), target.value[choose]
        ),
        "expected_value": F.smooth_l1_loss(
            core.expected_value[choose].float(), target.value[choose]
        ),
        "top3": F.binary_cross_entropy_with_logits(
            core.top3_logit[choose].float(), target.top3[choose],
            pos_weight=core.top3_logit.new_tensor(
                supervision_weights.top3_pos, dtype=torch.float32),
        ),
        "rank": F.smooth_l1_loss(
            output.rank_value[choose].float(), target.rank[choose]
        ),
        "mfe_quantiles": _quantile_loss(
            output.mfe_quantiles[choose].float(), target.mfe[choose]
        ),
        "mae_quantiles": _quantile_loss(
            core.mae_quantiles[choose].float(), target.mae[choose]
        ),
        "wall": F.binary_cross_entropy_with_logits(
            core.wall_logit[choose].float(), target.wall[choose],
            pos_weight=core.wall_logit.new_tensor(
                supervision_weights.wall_pos, dtype=torch.float32),
        ),
        "time_to_peak": F.smooth_l1_loss(
            output.time_to_peak_value[choose].float(),
            target.time_to_peak[choose],
        ),
        "take_target": action_loss,
    }


def _selected_horizon_component(
    output: LearningOutput, batch: EntrySessionBatch, row_weights: Tensor,
) -> Tensor:
    """Six-coordinate selected trajectory auxiliary; never the legacy plane."""

    if (batch.selected_horizon_value is None
            or batch.selected_horizon_valid is None
            or batch.selected_horizon_schema_sha256
                != SELECTED_HORIZON_SCHEMA_SHA256
            or output.horizon_value.shape
                != (batch.rows, SELECTED_HORIZON_WIDTH)
            or row_weights.shape != (batch.rows,)):
        raise C.EntryV2Refusal("selected horizon loss identity/shape differs")
    valid = batch.selected_horizon_valid.to(dtype=torch.bool)
    weight = row_weights[:, None].float() * valid.float()
    if not bool(weight.sum() > 0):
        raise C.EntryV2Refusal("selected horizon loss has no weighted target")
    loss = F.smooth_l1_loss(
        output.horizon_value.float(), batch.selected_horizon_value.float(),
        reduction="none",
    )
    return (loss * weight).sum() / weight.sum()


def _self_supervised_components(
    output: LearningOutput,
    self_supervised: SelfSupervisedTargets,
    choose: Tensor,
) -> dict[str, Tensor]:
    components: dict[str, Tensor] = {}
    horizon_mask = self_supervised.horizon_valid.to(dtype=torch.bool) & choose[:, None]
    if bool(horizon_mask.any()):
        components["horizons"] = F.smooth_l1_loss(
            output.horizon_value.float()[horizon_mask],
            self_supervised.horizon_value.float()[horizon_mask],
        )
    else:
        components["horizons"] = output.horizon_value.float().sum() * 0.0
    phase_mask = self_supervised.phase_valid.to(dtype=torch.bool) & choose
    if bool(phase_mask.any()):
        phase_target = self_supervised.phase_class.to(dtype=torch.int64)
        if int(phase_target[phase_mask].min()) < 0 or int(
            phase_target[phase_mask].max()
        ) >= output.phase_logits.shape[1]:
            raise C.EntryV2Refusal("self-supervised phase class is out of range")
        components["phase"] = F.cross_entropy(
            output.phase_logits.float()[phase_mask],
            phase_target[phase_mask],
        )
    else:
        components["phase"] = output.phase_logits.float().sum() * 0.0
    return components


def _matched_hard_listwise_components(
    output: LearningOutput,
    target: TeacherTargets,
    examples: Sequence[CausalEntryExample],
    canonical_pair_ids: Sequence[tuple[str, str]] | None = None,
    canonical_pair_weights: Sequence[float] | None = None,
) -> tuple[dict[str, Tensor], int]:
    """One deterministic winner/near-miss contrast per asset/day/phase.

    The full-population oracle loss is computed separately on every row.  This
    function only adds the matched contrast; it never replaces or subsets the
    population objective.
    """

    if len(examples) != int(output.core.embedding.shape[0]):
        raise C.EntryV2Refusal("hard-negative example/output rows differ")
    if canonical_pair_ids is not None or canonical_pair_weights is not None:
        if (canonical_pair_ids is None or canonical_pair_weights is None
                or len(canonical_pair_ids) != len(canonical_pair_weights)):
            raise C.EntryV2Refusal("canonical hard-pair inputs are misaligned")
        index_by_id = {
            example.candidate_id: index for index, example in enumerate(examples)
        }
        weighted_pairs: list[tuple[int, int, float]] = []
        for ids, raw_weight in zip(canonical_pair_ids, canonical_pair_weights):
            if (len(ids) != 2 or ids[0] not in index_by_id
                    or ids[1] not in index_by_id):
                raise C.EntryV2Refusal("canonical hard pair is outside its asset-day")
            positive, negative = index_by_id[ids[0]], index_by_id[ids[1]]
            weight = float(raw_weight)
            if (not np.isfinite(weight) or weight <= 0
                    or not bool(target.action_loss_mask[positive])
                    or not bool(target.action_loss_mask[negative])
                    or not bool(target.take_target[positive] > .5)
                    or bool(target.take_target[negative] > .5)):
                raise C.EntryV2Refusal("canonical hard pair labels/weight differ")
            weighted_pairs.append((positive, negative, weight))
        zero = output.core.embedding.float().sum() * 0.0
        if not weighted_pairs:
            return {"hard_negative": zero, "listwise": zero}, 0
        weights = output.core.embedding.new_tensor(
            [row[2] for row in weighted_pairs], dtype=torch.float32)
        weights = weights / weights.sum()
        hard_rows, rank_rows = [], []
        for positive, negative, _weight in weighted_pairs:
            gaps = torch.stack((
                output.core.take_logit[positive] - output.core.take_logit[negative],
                output.core.top3_logit[positive] - output.core.top3_logit[negative],
                output.core.expected_value[positive]
                    - output.core.expected_value[negative],
            )).float()
            hard_rows.append(F.softplus(-gaps).mean())
            rank_rows.append(F.softplus(-(
                output.rank_value[negative] - output.rank_value[positive]
            ).float()))
        return ({
            "hard_negative": (torch.stack(hard_rows) * weights).sum(),
            "listwise": (torch.stack(rank_rows) * weights).sum(),
        }, len(weighted_pairs))
    groups: dict[tuple[str, int, str], list[int]] = {}
    for index, example in enumerate(examples):
        groups.setdefault(
            (example.asset, example.trading_day, example.phase), []
        ).append(index)
    pair_losses: list[Tensor] = []
    list_losses: list[Tensor] = []
    for indexes in groups.values():
        if len(indexes) < 2:
            continue
        local = torch.tensor(
            indexes, dtype=torch.int64, device=output.core.embedding.device
        )
        action_valid = (
            target.action_loss_mask[local].to(dtype=torch.bool)
            & torch.isfinite(target.rank[local])
        )
        action_local = local[action_valid]
        if action_local.numel() < 2:
            continue
        actions = target.take_target[action_local] > 0.5
        positives = action_local[actions]
        negatives = action_local[~actions]
        if positives.numel() and negatives.numel():
            winner = positives[target.rank[positives].argmin()]
            near_miss = negatives[target.rank[negatives].argmin()]
            # Three independently useful orderings: action, top-three, value.
            gaps = torch.stack((
                output.core.take_logit[winner] - output.core.take_logit[near_miss],
                output.core.top3_logit[winner] - output.core.top3_logit[near_miss],
                output.core.expected_value[winner]
                    - output.core.expected_value[near_miss],
            )).float()
            pair_losses.append(F.softplus(-gaps).mean())
        # Listwise supervision consumes the exact rank already stored by the
        # teacher; the best-ranked member is the single target for this group.
        supervised_ranks = target.rank[action_local]
        best_local = supervised_ranks.argmin().reshape(1)
        list_losses.append(F.cross_entropy(
            output.core.expected_value[action_local].float()[None, :],
            best_local.to(dtype=torch.int64,
                          device=output.core.embedding.device),
        ))
    zero = output.core.embedding.float().sum() * 0.0
    return ({
        "hard_negative": (
            torch.stack(pair_losses).mean() if pair_losses else zero
        ),
        "listwise": torch.stack(list_losses).mean() if list_losses else zero,
    }, len(pair_losses))


@dataclass(frozen=True)
class PassReceipt:
    name: str
    rows: int
    optimizer_steps: int
    mean_loss: float
    model_sha256: str
    matched_pairs: int = 0
    stage_receipt: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class TrainingTrace:
    config_sha256: str
    teacher_sha256: str
    normalizer_sha256: str
    initial_model_sha256: str
    final_model_sha256: str
    supervision_weights_sha256: str
    passes: tuple[PassReceipt]
    session_order_sha256: str
    model_input_binding: ModelInputBinding
    receipt_sha256: str


@dataclass
class TrainingArtifact:
    system: EntryLearningSystem
    normalizer: TrainFoldNormalizer
    trace: TrainingTrace


@dataclass(frozen=True)
class SelectedFoldTrainingReceipt:
    """Compact real training identity for a selected-only held/forward fold."""
    schema: str
    training_receipt_sha256: str
    normalizers_payload_sha256: str
    model_input_binding: ModelInputBinding
    expanded_schema_sha256: str
    expanded_transform_law_sha256: str
    e2_frozen_selection_sha256: str
    checkpoint_set_sha256: str
    chronological_stage_receipts_sha256: str
    selected_horizon_schema_sha256: str
    selected_horizon_target_law_sha256: str
    selected_horizon_normalizer_sha256: str
    selected_output_schema_sha256: str
    selected_ordinal_semantics_sha256: str
    receipt_sha256: str

    @classmethod
    def freeze(cls, *, training_receipt_sha256: str,
               normalizers_payload_sha256: str,
               model_input_binding: ModelInputBinding,
               expanded_schema_sha256: str,
               expanded_transform_law_sha256: str,
               e2_frozen_selection_sha256: str,
               checkpoint_set_sha256: str,
               chronological_stage_receipts_sha256: str,
               selected_horizon_schema_sha256: str,
               selected_horizon_target_law_sha256: str,
               selected_horizon_normalizer_sha256: str,
               selected_output_schema_sha256: str,
               selected_ordinal_semantics_sha256: str,
               ) -> "SelectedFoldTrainingReceipt":
        core = {
            "schema": "entry-v2-selected-fold-training-receipt-v1",
            "training_receipt_sha256": training_receipt_sha256,
            "normalizers_payload_sha256": normalizers_payload_sha256,
            "model_input_binding": model_input_binding.as_dict(),
            "expanded_schema_sha256": expanded_schema_sha256,
            "expanded_transform_law_sha256": expanded_transform_law_sha256,
            "e2_frozen_selection_sha256": e2_frozen_selection_sha256,
            "checkpoint_set_sha256": checkpoint_set_sha256,
            "chronological_stage_receipts_sha256":
                chronological_stage_receipts_sha256,
            "selected_horizon_schema_sha256": selected_horizon_schema_sha256,
            "selected_horizon_target_law_sha256":
                selected_horizon_target_law_sha256,
            "selected_horizon_normalizer_sha256":
                selected_horizon_normalizer_sha256,
            "selected_output_schema_sha256": selected_output_schema_sha256,
            "selected_ordinal_semantics_sha256":
                selected_ordinal_semantics_sha256,
        }
        hashes = tuple(value for key, value in core.items()
                       if key not in ("schema", "model_input_binding"))
        if any(not isinstance(value, str) or len(value) != 64
               or any(char not in "0123456789abcdef" for char in value)
               for value in hashes):
            raise C.EntryV2Refusal("selected fold training hash is invalid")
        if (selected_horizon_schema_sha256 != SELECTED_HORIZON_SCHEMA_SHA256
                or selected_horizon_target_law_sha256
                    != SELECTED_HORIZON_TARGET_LAW_SHA256
                or selected_ordinal_semantics_sha256
                    != SELECTED_ORDINAL_SEMANTICS_SHA256):
            raise C.EntryV2Refusal(
                "selected fold horizon contract differs from A-015")
        return cls(**{**core, "model_input_binding": model_input_binding,
                      "receipt_sha256": C.object_sha256(core)})

    def validate(self) -> None:
        rebuilt = self.freeze(
            training_receipt_sha256=self.training_receipt_sha256,
            normalizers_payload_sha256=self.normalizers_payload_sha256,
            model_input_binding=self.model_input_binding,
            expanded_schema_sha256=self.expanded_schema_sha256,
            expanded_transform_law_sha256=self.expanded_transform_law_sha256,
            e2_frozen_selection_sha256=self.e2_frozen_selection_sha256,
            checkpoint_set_sha256=self.checkpoint_set_sha256,
            chronological_stage_receipts_sha256=
                self.chronological_stage_receipts_sha256,
            selected_horizon_schema_sha256=self.selected_horizon_schema_sha256,
            selected_horizon_target_law_sha256=
                self.selected_horizon_target_law_sha256,
            selected_horizon_normalizer_sha256=
                self.selected_horizon_normalizer_sha256,
            selected_output_schema_sha256=self.selected_output_schema_sha256,
            selected_ordinal_semantics_sha256=
                self.selected_ordinal_semantics_sha256,
        )
        if rebuilt != self:
            raise C.EntryV2Refusal("selected fold training receipt changed")


@dataclass(frozen=True)
class FoldTrainingIdentity:
    training_receipt_sha256: str
    normalizer_sha256: str
    model_input_binding: ModelInputBinding
    selected_receipt: SelectedFoldTrainingReceipt | None = None


def _batch_key(batch: EntrySessionSpec) -> tuple[int, str, str]:
    return batch.trading_day, batch.asset, batch.session_id


def _validate_dataset(
    batches: Sequence[EntrySessionSpec],
    teacher: TeacherStore,
    *,
    allow_control: bool = False,
) -> tuple[EntrySessionSpec, ...]:
    if teacher.control_name != "PROPHET" and not allow_control:
        raise C.EntryV2Refusal("training requires the exact PROPHET TeacherStore")
    ordered = tuple(sorted(batches, key=_batch_key))
    seen: set[str] = set()
    for batch in ordered:
        # Check the date before looking at any bulk tensor.
        C.guard_date(batch.trading_day)
        batch.validate(teacher)
        overlap = seen.intersection(batch.candidate_ids)
        if overlap:
            raise C.EntryV2Refusal(f"candidate appears in two batches: {min(overlap)}")
        seen.update(batch.candidate_ids)
    return ordered


def _device(config: TrainingConfig) -> torch.device:
    if config.device == "cuda":
        if not torch.cuda.is_available():
            raise C.EntryV2Refusal("CUDA training requested but unavailable")
        if config.bf16 and not torch.cuda.is_bf16_supported():
            raise C.EntryV2Refusal("CUDA device does not support BF16")
    return torch.device(config.device)


def _seed(config: TrainingConfig) -> None:
    np.random.seed(config.seed)
    torch.manual_seed(config.seed)
    torch.set_num_threads(config.workers)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(config.seed)


def _autocast(config: TrainingConfig, device: torch.device):
    if device.type == "cuda" and config.bf16:
        return torch.autocast("cuda", dtype=torch.bfloat16)
    return nullcontext()


def _train_pass(
    name: str,
    system: EntryLearningSystem,
    batches: Sequence[EntrySessionSpec],
    teacher: TeacherStore,
    normalizer: TrainFoldNormalizer,
    supervision_weights: SupervisionWeights,
    config: TrainingConfig,
    device: torch.device,
    objective: str,
) -> PassReceipt:
    optimizer = torch.optim.AdamW(
        system.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay
    )
    system.train()
    if objective not in {"self_supervised", "oracle", "hard_listwise"}:
        raise C.EntryV2Refusal(f"unknown training objective {objective}")
    losses, rows, steps, matched_pairs = [], 0, 0, 0
    for spec in batches:
        with spec.source.open_batch(spec) as batch:
            choose = torch.ones(batch.rows, dtype=torch.bool, device=device)
            normalized = normalizer.transform(batch, device)
            target = teacher_targets(batch, teacher, device)
            optimizer.zero_grad(set_to_none=True)
            with _autocast(config, device):
                output = system(normalized)
                if objective == "self_supervised":
                    components = _self_supervised_components(
                        output, normalized.self_supervised, choose
                    )
                else:
                    components = _oracle_components(
                        output, target, supervision_weights, choose
                    )
                    if objective == "hard_listwise":
                        contrast, pairs = _matched_hard_listwise_components(
                            output, target, batch.examples
                        )
                        components.update(contrast)
                        matched_pairs += pairs
                loss = sum(
                    LOSS_WEIGHTS[key] * value
                    for key, value in components.items()
                )
            if not bool(torch.isfinite(loss)):
                raise C.EntryV2Refusal(f"non-finite {name} loss")
            loss.backward()
            nn.utils.clip_grad_norm_(system.parameters(), config.max_grad_norm)
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
            rows += int(choose.sum())
            steps += 1
            del loss, output, target, normalized, choose
        del batch
    if steps == 0:
        raise C.EntryV2Refusal(f"{name} produced no optimizer step")
    if objective == "hard_listwise" and matched_pairs == 0:
        raise C.EntryV2Refusal(
            "matched hard-negative pass found no same-asset/day/phase pair"
        )
    return PassReceipt(
        name, rows, steps, float(np.mean(losses)),
        model_state_sha256(system), matched_pairs
    )


def _fit_selected_winner(
    system: EntryLearningSystem, ordered: Sequence[EntrySessionSpec],
    fit: Sequence[EntrySessionSpec], teacher: TeacherStore, fold: FoldSpec,
    normalizer: Any, supervision_weights: SupervisionWeights,
    model_input_binding: ModelInputBinding, config: TrainingConfig,
    device: torch.device, initial: str, static_normalizer_sha256: str,
) -> TrainingArtifact:
    """Exact 8/12/6 chronological best-checkpoint path for the selected arm."""
    from .neural_sufficiency_model import FrozenRowManifest, train_chronological_stage

    fit_rows = [row for spec in sorted(fit, key=_batch_key) for row in spec.examples]
    manifest = FrozenRowManifest.build_fit_validation(
        [row.candidate_id for row in fit_rows], [row.asset for row in fit_rows],
        [row.trading_day for row in fit_rows], chronology=fold.test_era,
    )
    from .atlas_probe_model import (
        action_fit_weights, asset_day_fit_weights,
        canonical_phase_pair_manifest,
    )
    joined = teacher.join_training(fit_rows)
    labels = tuple(label for _example, label in joined)
    if (tuple(example.candidate_id for example, _label in joined)
            != tuple(manifest.candidate_id)):
        raise C.EntryV2Refusal("selected fit-weight rows differ from the fold manifest")
    train_indices = np.asarray([
        index for index, split in enumerate(manifest.split) if split == "TRAIN"
    ], np.int64)
    assets = [row.asset for row in fit_rows]
    days = [row.trading_day for row in fit_rows]
    all_valid = np.ones(len(fit_rows), dtype=bool)
    weight_targets: dict[str, tuple[Sequence[Any], Sequence[bool], bool]] = {
        "ordinal": ([VALUE_BIN_INDEX[row.value_bin] for row in labels], all_valid, False),
        "value_bins": ([VALUE_BIN_INDEX[row.value_bin] for row in labels], all_valid, False),
        "value_quantiles": ([row.cert_close_usd for row in labels], all_valid, False),
        "expected_value": ([row.cert_close_usd for row in labels], all_valid, False),
        "top3": ([row.top3 for row in labels], all_valid, True),
        "rank": ([row.rank for row in labels], all_valid, False),
        "mfe_quantiles": ([row.mfe_usd for row in labels], all_valid, False),
        "mae_quantiles": ([row.mae_usd for row in labels], all_valid, False),
        "wall": ([row.wall_hit for row in labels], all_valid, True),
        "time_to_peak": ([row.time_to_peak_sec for row in labels], all_valid, False),
        "take_target": (
            [row.take_target for row in labels],
            [row.action_loss_mask for row in labels], True,
        ),
    }
    fit_weight_by_component: dict[str, Mapping[str, float]] = {}
    fit_weight_receipts: dict[str, str] = {}
    for name, (values, mask, class_weight) in weight_targets.items():
        helper = action_fit_weights if name == "take_target" else asset_day_fit_weights
        weights, receipt = helper(
            assets, days, values, mask, train_indices,
            apply_class_weight=class_weight,
        )
        fit_weight_by_component[name] = MappingProxyType({
            candidate_id: float(weights[index])
            for index, candidate_id in enumerate(manifest.candidate_id)
        })
        fit_weight_receipts[name] = receipt.receipt_sha256
        if receipt.optimizer_step_unit != "complete_asset_day_gradient":
            raise C.EntryV2Refusal("selected fit-weight optimizer unit differs")
    if any(spec.selected_horizon_value is None
           or spec.selected_horizon_valid is None
           or spec.selected_horizon_schema_sha256
                != SELECTED_HORIZON_SCHEMA_SHA256 for spec in sorted(fit, key=_batch_key)):
        raise C.EntryV2Refusal(
            "selected fit population lacks six-coordinate horizon targets")
    raw_selected_horizon = torch.cat([
        spec.selected_horizon_value.detach().cpu()
        for spec in sorted(fit, key=_batch_key)
    ])
    raw_selected_valid = torch.cat([
        spec.selected_horizon_valid.detach().cpu().to(torch.bool)
        for spec in sorted(fit, key=_batch_key)
    ])
    horizon_weights, horizon_weight_receipt = asset_day_fit_weights(
        assets, days, raw_selected_horizon[:, -1].numpy(),
        raw_selected_valid.any(1).numpy(), train_indices,
        apply_class_weight=False,
    )
    horizon_fit_weight_by_id = MappingProxyType({
        candidate_id: float(horizon_weights[index])
        for index, candidate_id in enumerate(manifest.candidate_id)
    })
    fit_weight_receipts["selected_horizons"] = (
        horizon_weight_receipt.receipt_sha256
    )
    phase_pairs = canonical_phase_pair_manifest(
        manifest.candidate_id, assets, days, [row.phase for row in fit_rows],
        [row.decision_ts_ns for row in fit_rows],
        [row.take_target for row in labels],
        [row.action_loss_mask for row in labels], train_indices,
    )
    example_by_id = {row.candidate_id: row for row in fit_rows}
    pairs_by_asset_day: dict[
        tuple[str, int], list[tuple[tuple[str, str], float]]
    ] = {}
    for ids, weight in zip(phase_pairs.candidate_id_pairs,
                           phase_pairs.pair_weights):
        positive = example_by_id[ids[0]]
        pairs_by_asset_day.setdefault(
            (positive.asset, positive.trading_day), []
        ).append((ids, float(weight)))
    train_specs = tuple(spec for spec in sorted(fit, key=_batch_key)
                        if spec.trading_day in {
                            day for day, split in zip(manifest.day, manifest.split)
                            if split == "TRAIN"
                        })
    train_asset_days = [(spec.asset, spec.trading_day) for spec in train_specs]
    if len(set(train_asset_days)) != len(train_asset_days):
        raise C.EntryV2Refusal(
            "selected optimizer cannot step before a complete asset-day gradient"
        )
    fit_weighting_sha256 = C.object_sha256(dict(sorted(fit_weight_receipts.items())))
    setattr(system, "selected_fit_weighting_sha256", fit_weighting_sha256)
    setattr(system, "selected_phase_pair_manifest_sha256",
            phase_pairs.receipt_sha256)
    horizon_normalizer_sha256 = C.object_sha256({
        "mean": normalizer.horizon_mean, "scale": normalizer.horizon_scale,
        "schema_sha256": SELECTED_HORIZON_SCHEMA_SHA256,
    })
    setattr(system, "selected_horizon_schema_sha256",
            SELECTED_HORIZON_SCHEMA_SHA256)
    setattr(system, "selected_horizon_normalizer_sha256",
            horizon_normalizer_sha256)
    setattr(system, "selected_ordinal_semantics", SELECTED_ORDINAL_SEMANTICS)
    provider = getattr(system, "target_provider", None)
    if provider is None and getattr(system, "arm", "") != "C0":
        raise C.EntryV2Refusal("selected winner lacks its atlas target provider")
    # One vectorized coverage check.  This reads only the compact target plane,
    # never an event pack, and proves every expanding-fit row is available.
    if provider is not None:
        expected_candidates = C.object_sha256(list(manifest.candidate_id))
        if provider.target_candidate_manifest_sha256 != expected_candidates:
            raise C.EntryV2Refusal(
                "selected target provider population is not this fold's fit population"
            )
        provider.target_for(manifest.candidate_id)
    split_days = {
        name: {day for day, split in zip(manifest.day, manifest.split) if split == name}
        for name in ("TRAIN", "VALIDATION")
    }
    matched_pair_receipts: dict[str, int] = {}

    def epoch(stage: str, train: bool, optimizer: torch.optim.Optimizer | None) -> Tensor:
        selected = tuple(spec for spec in sorted(fit, key=_batch_key)
                         if spec.trading_day in split_days["TRAIN" if train else "VALIDATION"])
        if not selected:
            raise C.EntryV2Refusal(f"selected {stage} stage has an empty chronological split")
        system.train(train); values: list[Tensor] = []; matched_pairs = 0
        context = nullcontext() if train else torch.no_grad()
        with context:
            for spec in selected:
                with spec.source.open_batch(spec) as batch:
                    normalized = normalizer.transform(batch, device)
                    target = teacher_targets(batch, teacher, device)
                    if train:
                        assert optimizer is not None
                        optimizer.zero_grad(set_to_none=True)
                    with _autocast(config, device):
                        output = system(normalized)
                        batch_fit_weights = None
                        horizon_row_weights = None
                        if stage != "field_survival":
                            batch_fit_weights = MappingProxyType({
                                name: (
                                    torch.tensor(
                                        [rows[candidate_id]
                                         for candidate_id in batch.candidate_ids],
                                        dtype=torch.float32, device=device,
                                    ) if train else torch.ones(
                                        batch.rows, dtype=torch.float32,
                                        device=device,
                                    )
                                )
                                for name, rows in fit_weight_by_component.items()
                            })
                            horizon_row_weights = (
                                torch.tensor([
                                    horizon_fit_weight_by_id[candidate_id]
                                    for candidate_id in batch.candidate_ids
                                ], dtype=torch.float32, device=device)
                                if train else torch.ones(
                                    batch.rows, dtype=torch.float32, device=device)
                            )
                        if stage == "field_survival":
                            loss = system.field_survival_loss(output, normalized)
                        elif stage == "pointwise_dense":
                            components = _oracle_components(
                                output, target, supervision_weights,
                                torch.ones(batch.rows, dtype=torch.bool, device=device),
                                batch_fit_weights,
                            )
                            assert horizon_row_weights is not None
                            components["horizons"] = _selected_horizon_component(
                                output, normalized, horizon_row_weights)
                            loss = sum(LOSS_WEIGHTS[key] * value
                                       for key, value in components.items())
                        else:
                            if getattr(system, "arm", "") == "C0":
                                canonical = pairs_by_asset_day.get(
                                    (batch.asset, batch.trading_day), []) if train else []
                                contrast, pairs = _matched_hard_listwise_components(
                                    output, target, batch.examples,
                                    ([row[0] for row in canonical] if train else None),
                                    ([row[1] for row in canonical] if train else None),
                                )
                                matched_pairs += pairs
                                components = _oracle_components(
                                    output, target, supervision_weights,
                                    torch.ones(batch.rows, dtype=torch.bool, device=device),
                                    batch_fit_weights,
                                )
                                assert horizon_row_weights is not None
                                components["horizons"] = _selected_horizon_component(
                                    output, normalized, horizon_row_weights)
                                components.update(contrast)
                                loss = sum(LOSS_WEIGHTS[key] * value
                                           for key, value in components.items())
                            else:
                                # Every selected arm retains the canonical
                                # full-population oracle law and exactly one
                                # matched hard-negative/listwise pass.  The
                                # selected atlas objective is additive; it
                                # does not replace either proven supervision
                                # path and no second contrast pass is run.
                                canonical = pairs_by_asset_day.get(
                                    (batch.asset, batch.trading_day), []) if train else []
                                contrast, pairs = _matched_hard_listwise_components(
                                    output, target, batch.examples,
                                    ([row[0] for row in canonical] if train else None),
                                    ([row[1] for row in canonical] if train else None),
                                )
                                matched_pairs += pairs
                                components = _oracle_components(
                                    output, target, supervision_weights,
                                    torch.ones(batch.rows, dtype=torch.bool,
                                               device=device),
                                    batch_fit_weights,
                                )
                                assert horizon_row_weights is not None
                                components["horizons"] = _selected_horizon_component(
                                    output, normalized, horizon_row_weights)
                                components.update(contrast)
                                loss = (sum(LOSS_WEIGHTS[key] * value
                                            for key, value in components.items())
                                        + system.selected_objective_loss(
                                            output, batch.candidate_ids,
                                            use_fit_weight=train))
                    if not bool(torch.isfinite(loss)):
                        raise C.EntryV2Refusal(f"non-finite selected {stage} loss")
                    if train:
                        loss.backward()
                        nn.utils.clip_grad_norm_(system.parameters(), config.max_grad_norm)
                        optimizer.step()
                    values.append(loss.detach().float())
        if train and stage == "grouped_atlas" and matched_pairs == 0:
            raise C.EntryV2Refusal(
                "selected matched hard-negative/listwise pass found no pair"
            )
        if train:
            matched_pair_receipts[stage] = matched_pairs
        return torch.stack(values).mean()

    stage_receipts = []
    for stage in ("field_survival", "pointwise_dense", "grouped_atlas"):
        optimizer = torch.optim.AdamW(
            system.parameters(), lr=config.learning_rate,
            weight_decay=config.weight_decay,
        )
        receipt = train_chronological_stage(
            system, optimizer, stage=stage, row_manifest=manifest,
            train_epoch=lambda _model, opt, _manifest, name=stage:
                epoch(name, True, opt),
            validate_epoch=lambda _model, _manifest, name=stage:
                epoch(name, False, None),
        )
        if len(receipt.epochs) < 2 or not receipt.best_reloaded:
            raise C.EntryV2Refusal(f"selected {stage} convergence law did not complete")
        stage_receipts.append(receipt)
    passes = tuple(PassReceipt(
        receipt.spec.name, len(manifest.candidate_id), len(receipt.epochs),
        float(np.mean([row.train_loss for row in receipt.epochs])),
        receipt.best_state_sha256,
        matched_pair_receipts.get(receipt.spec.name, 0), asdict(receipt),
    ) for receipt in stage_receipts)
    final = model_state_sha256(system)
    order_hash = C.object_sha256([
        [spec.trading_day, spec.asset, spec.session_id]
        for spec in sorted(fit, key=_batch_key)
    ])
    payload = {
        "schema": "entry-v2-selected-winner-training-v1",
        "config_sha256": config.receipt()["sha256"],
        "teacher_sha256": teacher.store_hash,
        "normalizer_sha256": normalizer.receipt_sha256,
        "selected_static_normalizer_sha256": static_normalizer_sha256,
        "initial_model_sha256": initial, "final_model_sha256": final,
        "supervision_weights_sha256": supervision_weights.sha256,
        "passes": [asdict(value) for value in passes],
        "session_order_sha256": order_hash,
        "model_input_binding": model_input_binding.as_dict(),
        "winner_bundle_sha256": system.winner_bundle_sha256,
        "selected_arm": system.arm,
        "selected_objective_sha256": system.selected_objective_sha256,
        "target_store_row_manifest_sha256": (
            system.selected_target_row_manifest_sha256 if provider is None
            else provider.row_manifest_sha256
        ),
        "selected_target_control_sha256":
            system.selected_target_control_sha256,
        "selected_target_fit_day_manifest_sha256": (
            None if provider is None else provider.fit_day_manifest_sha256
        ),
        "selected_target_candidate_manifest_sha256": (
            None if provider is None else provider.target_candidate_manifest_sha256
        ),
        "selected_target_fit_context_sha256": (
            None if provider is None else provider.fit_context_sha256
        ),
        "selected_target_shuffle_receipt": (
            None if provider is None else dict(provider.shuffle_receipt)
        ),
        "fold_fit_manifest_sha256": manifest.receipt_sha256,
        "selected_fit_weighting_sha256": fit_weighting_sha256,
        "selected_fit_weight_receipts": dict(sorted(fit_weight_receipts.items())),
        "selected_phase_pair_manifest_sha256": phase_pairs.receipt_sha256,
        "selected_optimizer_step_unit": "complete_asset_day_gradient",
        "selected_validation_weighting": "UNWEIGHTED",
        "selected_horizon_schema_sha256": SELECTED_HORIZON_SCHEMA_SHA256,
        "selected_horizon_coordinates": list(SELECTED_HORIZON_COORDINATES),
        "selected_horizon_normalizer_sha256": horizon_normalizer_sha256,
        "selected_ordinal_semantics": SELECTED_ORDINAL_SEMANTICS,
        "selected_ordinal_semantics_sha256":
            SELECTED_ORDINAL_SEMANTICS_SHA256,
    }
    trace = TrainingTrace(
        config.receipt()["sha256"], teacher.store_hash,
        normalizer.receipt_sha256, initial, final,
        supervision_weights.sha256, passes, order_hash,
        model_input_binding, C.object_sha256(payload),
    )
    return TrainingArtifact(system, normalizer, trace)


def fit_encoder(
    system: EntryLearningSystem,
    batches: Sequence[EntrySessionSpec],
    teacher: TeacherStore,
    fold: FoldSpec,
    model_input_binding: ModelInputBinding,
    config: TrainingConfig = TrainingConfig(),
    *,
    _allow_control: bool = False,
) -> TrainingArtifact:
    """Fit the one frozen three-stage encoder schedule on fold.fit_days."""

    fold.validate()
    ordered = _validate_dataset(batches, teacher, allow_control=_allow_control)
    fit = tuple(batch for batch in ordered if batch.trading_day in set(fold.fit_days))
    if not fit:
        raise C.EntryV2Refusal("fold has no fit candidate batches")
    model_input_binding.validate()
    selected_winner = hasattr(system, "winner_bundle_sha256")
    if selected_winner:
        days = sorted(set(int(day) for day in fold.fit_days))
        validation_count = max(1, int(np.ceil(.10 * len(days))))
        if len(days) <= validation_count:
            raise C.EntryV2Refusal("selected fold lacks chronological TRAIN days")
        train_only_days = days[:-validation_count]
        transform = system.event_transform
        if (system.encoder.field_schema.sha256 != transform.schema_sha256
                or tuple(system.encoder.event_category_sizes)
                    != tuple(transform.category_sizes)):
            raise C.EntryV2Refusal("selected encoder differs from expanded event transform")
        normalizer = SelectedFoldNormalizer.fit(
            ordered, train_only_days, model_input_binding, transform,
            use_static=system.arm in ("L1", "M1"),
        )
    else:
        if (system.encoder.n_event_continuous
                != len(model_input_binding.event_continuous_fields)):
            raise C.EntryV2Refusal(
                "encoder continuous width differs from bound V2 event fields"
            )
        if (tuple(system.encoder.event_category_sizes)
                != model_input_binding.event_category_sizes):
            raise C.EntryV2Refusal(
                "encoder category sizes differ from bound V3 event categories"
            )
        normalizer = TrainFoldNormalizer.fit(
            ordered, fold.fit_days, model_input_binding
        )
    device = _device(config)
    _seed(config)
    selected_static_normalizer_sha256 = (
        normalizer.receipt_sha256 if selected_winner else None
    )
    if system.phase_head.out_features != config.n_phase_classes:
        raise C.EntryV2Refusal("system/config phase class counts differ")
    system.to(device)
    initial = model_state_sha256(system)
    if selected_winner:
        return _fit_selected_winner(
            system, ordered, fit, teacher, fold, normalizer,
            _fit_supervision_weights(fit, teacher), model_input_binding,
            config, device, initial, selected_static_normalizer_sha256,
        )
    # One seeded order is fixed once and reused by all three declared stages.
    rng = np.random.default_rng(config.seed)
    order = rng.permutation(len(fit)).tolist()
    fit_once = tuple(fit[index] for index in order)
    order_hash = C.object_sha256([
        [batch.trading_day, batch.asset, batch.session_id] for batch in fit_once
    ])
    supervision_weights = _fit_supervision_weights(fit, teacher)
    self_supervised_pass = _train_pass(
        "fold_causal_self_supervision", system, fit_once, teacher, normalizer,
        supervision_weights, config, device, "self_supervised"
    )
    oracle_pass = _train_pass(
        "full_population_oracle_multitask", system, fit_once, teacher,
        normalizer, supervision_weights, config, device, "oracle"
    )
    hard_pass = _train_pass(
        "matched_hard_negative_listwise", system, fit_once, teacher,
        normalizer, supervision_weights, config, device, "hard_listwise"
    )
    final = model_state_sha256(system)
    config_hash = config.receipt()["sha256"]
    payload = {
        "schema": "entry-v2-fixed-staged-training-v2",
        "config_sha256": config_hash,
        "teacher_sha256": teacher.store_hash,
        "normalizer_sha256": normalizer.receipt_sha256,
        "initial_model_sha256": initial,
        "final_model_sha256": final,
        "supervision_weights_sha256": supervision_weights.sha256,
        "passes": [
            asdict(self_supervised_pass),
            asdict(oracle_pass),
            asdict(hard_pass),
        ],
        "session_order_sha256": order_hash,
        "model_input_binding": model_input_binding.as_dict(),
        "selected_static_normalizer_sha256": selected_static_normalizer_sha256,
        "selected_objective_sha256": getattr(
            getattr(system, "objective", None), "objective_sha256", None
        ),
    }
    trace = TrainingTrace(
        config_hash,
        teacher.store_hash,
        normalizer.receipt_sha256,
        initial,
        final,
        supervision_weights.sha256,
        (self_supervised_pass, oracle_pass, hard_pass),
        order_hash,
        model_input_binding,
        C.object_sha256(payload),
    )
    return TrainingArtifact(system, normalizer, trace)


@dataclass(frozen=True)
class _EncodedRows:
    examples: tuple[CausalEntryExample, ...]
    candidate_ids: tuple[str, ...]
    assets: tuple[str, ...]
    days: np.ndarray
    embeddings: np.ndarray
    targets: Mapping[str, np.ndarray]


def _encode_rows(
    artifact: TrainingArtifact,
    batches: Sequence[EntrySessionSpec],
    teacher: TeacherStore,
    config: TrainingConfig,
) -> _EncodedRows:
    device = _device(config)
    artifact.system.eval()
    ids: list[str] = []
    examples: list[CausalEntryExample] = []
    assets: list[str] = []
    days: list[int] = []
    embeddings: list[np.ndarray] = []
    target_rows: dict[str, list[Any]] = {
        "take_target": [],
        "action_loss_mask": [],
        "top3": [],
        "rank": [],
        "cert_close_usd": [],
        "mfe_usd": [],
        "wall": [],
        "mae_usd": [],
        "time_to_peak_sec": [],
        "rank_group_id": [],
        "candidate_id": [],
        "asset": [],
        "trading_day": [],
        "phase": [],
        "decision_ts_ns": [],
    }
    with torch.inference_mode():
        for spec in sorted(batches, key=_batch_key):
            with spec.source.open_batch(spec) as batch:
                normalized = artifact.normalizer.transform(batch, device)
                with _autocast(config, device):
                    core = artifact.system(normalized).core
                embeddings.append(core.embedding.float().cpu().numpy())
                for example, label in teacher.join_training(batch.examples):
                    examples.append(example)
                    ids.append(example.candidate_id)
                    assets.append(example.asset)
                    days.append(example.trading_day)
                    target_rows["take_target"].append(float(label.take_target))
                    target_rows["action_loss_mask"].append(
                        float(label.action_loss_mask)
                    )
                    target_rows["top3"].append(float(label.top3))
                    target_rows["rank"].append(float(label.rank))
                    target_rows["rank_group_id"].append(
                        f"{example.asset}:{example.trading_day}:{example.phase}"
                    )
                    target_rows["candidate_id"].append(example.candidate_id)
                    target_rows["asset"].append(example.asset)
                    target_rows["trading_day"].append(example.trading_day)
                    target_rows["phase"].append(example.phase)
                    target_rows["decision_ts_ns"].append(example.decision_ts_ns)
                    target_rows["cert_close_usd"].append(float(label.cert_close_usd))
                    target_rows["mfe_usd"].append(float(label.mfe_usd))
                    target_rows["wall"].append(float(label.wall_hit))
                    target_rows["mae_usd"].append(float(label.mae_usd))
                    target_rows["time_to_peak_sec"].append(
                        float(label.time_to_peak_sec)
                    )
                del core, normalized
            del batch
    if not embeddings:
        raise C.EntryV2Refusal("cannot encode an empty fold stage")
    return _EncodedRows(
        tuple(examples),
        tuple(ids),
        tuple(assets),
        np.asarray(days, dtype=np.int64),
        np.concatenate(embeddings).astype(np.float32, copy=False),
        MappingProxyType({key: np.asarray(value) for key, value in target_rows.items()}),
    )


def _static_context_summary(spec: EntrySessionSpec) -> np.ndarray:
    """Fixed causal summary for the two classical controls.

    Context series are scattered by their global type id so SI/HG/NKD share
    one schema despite different rosters.  Each type/channel contributes last,
    mean, standard deviation, minimum, maximum, and a history-coverage value.
    No event tensor and no teacher field is opened here.
    """

    values = spec.context_values.detach().cpu().to(torch.float64)
    valid = spec.context_valid.detach().cpu().to(torch.bool)
    type_ids = spec.context_type_ids.detach().cpu().to(torch.int64)
    rows, series, _history, width = values.shape
    if valid.shape != values.shape[:-1] or type_ids.shape != (series,):
        raise C.EntryV2Refusal("static context summary received misaligned tensors")
    slots = len(CONTEXT_TYPE_ID)
    if any(int(item) < 0 or int(item) >= slots for item in type_ids):
        raise C.EntryV2Refusal("static context type id is outside the frozen roster")
    stats = torch.zeros((rows, slots, width * 5 + 1), dtype=torch.float64)
    for series_index, type_id_tensor in enumerate(type_ids):
        type_id = int(type_id_tensor)
        mask = valid[:, series_index, :]
        x = values[:, series_index, :, :]
        expanded = mask[..., None]
        count = mask.sum(dim=1).to(torch.float64)
        denom = count.clamp_min(1.0)[:, None]
        safe = torch.where(expanded, x, torch.zeros_like(x))
        mean = safe.sum(dim=1) / denom
        variance = (
            torch.where(expanded, (x - mean[:, None, :]).square(),
                        torch.zeros_like(x)).sum(dim=1) / denom
        )
        high = torch.where(expanded, x, torch.full_like(x, -torch.inf)).amax(dim=1)
        low = torch.where(expanded, x, torch.full_like(x, torch.inf)).amin(dim=1)
        high = torch.where(count[:, None] > 0, high, torch.zeros_like(high))
        low = torch.where(count[:, None] > 0, low, torch.zeros_like(low))
        positions = torch.arange(mask.shape[1], dtype=torch.int64)[None, :]
        last_index = torch.where(mask, positions, -1).amax(dim=1)
        last = torch.zeros((rows, width), dtype=torch.float64)
        present = last_index >= 0
        if bool(present.any()):
            last[present] = x[
                torch.arange(rows, dtype=torch.int64)[present],
                last_index[present],
            ]
        stats[:, type_id, :] = torch.cat((
            last, mean, variance.sqrt(), low, high,
            (count / mask.shape[1])[:, None],
        ), dim=1)
    asset_one_hot = torch.zeros((rows, len(C.ASSETS)), dtype=torch.float64)
    asset_one_hot[:, C.ASSET_INDEX[spec.asset]] = 1.0
    candidate = spec.candidate_features.detach().cpu().to(torch.float64)
    result = torch.cat((candidate, asset_one_hot, stats.flatten(1)), dim=1)
    if not bool(torch.isfinite(result).all()):
        raise C.EntryV2Refusal("static candidate/context summary is non-finite")
    return result.numpy().astype(np.float32, copy=False)


def _static_rows(
    batches: Sequence[EntrySessionSpec], teacher: TeacherStore
) -> _EncodedRows:
    examples: list[CausalEntryExample] = []
    features: list[np.ndarray] = []
    targets: dict[str, list[Any]] = {
        "take_target": [], "action_loss_mask": [], "top3": [], "rank": [],
        "rank_group_id": [],
        "candidate_id": [], "asset": [], "trading_day": [], "phase": [],
        "decision_ts_ns": [],
        "cert_close_usd": [], "mfe_usd": [], "wall": [],
        "mae_usd": [], "time_to_peak_sec": [],
    }
    width: int | None = None
    for spec in sorted(batches, key=_batch_key):
        spec.validate(teacher)
        matrix = _static_context_summary(spec)
        if width is None:
            width = int(matrix.shape[1])
        elif int(matrix.shape[1]) != width:
            raise C.EntryV2Refusal("static summary width changes across sessions")
        features.append(matrix)
        for example, label in teacher.join_training(spec.examples):
            examples.append(example)
            targets["take_target"].append(float(label.take_target))
            targets["action_loss_mask"].append(float(label.action_loss_mask))
            targets["top3"].append(float(label.top3))
            targets["rank"].append(float(label.rank))
            targets["rank_group_id"].append(
                f"{example.asset}:{example.trading_day}:{example.phase}"
            )
            targets["candidate_id"].append(example.candidate_id)
            targets["asset"].append(example.asset)
            targets["trading_day"].append(example.trading_day)
            targets["phase"].append(example.phase)
            targets["decision_ts_ns"].append(example.decision_ts_ns)
            targets["cert_close_usd"].append(float(label.cert_close_usd))
            targets["mfe_usd"].append(float(label.mfe_usd))
            targets["wall"].append(float(label.wall_hit))
            targets["mae_usd"].append(float(label.mae_usd))
            targets["time_to_peak_sec"].append(float(label.time_to_peak_sec))
    if not features:
        raise C.EntryV2Refusal("cannot build an empty static control population")
    return _EncodedRows(
        examples=tuple(examples),
        candidate_ids=tuple(item.candidate_id for item in examples),
        assets=tuple(item.asset for item in examples),
        days=np.asarray([item.trading_day for item in examples], dtype=np.int64),
        embeddings=np.concatenate(features).astype(np.float32, copy=False),
        targets=MappingProxyType({
            key: np.asarray(value) for key, value in targets.items()
        }),
    )


@dataclass
class FoldOOFResult:
    fold: str
    candidate_ids: tuple[str, ...]
    assets: tuple[str, ...]
    days: np.ndarray
    embeddings: np.ndarray
    static_features: np.ndarray
    arm_score_arrays: Mapping[str, Mapping[str, np.ndarray]]
    arm_entry_scores: Mapping[str, tuple[EntryScore, ...]]
    arm_arrivals: Mapping[str, tuple[ScoredArrival, ...]]
    arm_thresholds: Mapping[str, Mapping[str, float]]
    arm_evaluations: Mapping[str, EntryEvaluation]
    arm_policies: Mapping[str, Mapping[str, Any]]
    truth_scores: tuple[EntryScore, ...]
    truth_arrivals: tuple[ScoredArrival, ...]
    expected_sessions: tuple[SessionRef, ...]
    truth_thresholds_usd: Mapping[str, float]
    truth_evaluation: EntryEvaluation
    candidate_ceiling: CandidateCeiling
    training: TrainingArtifact | SelectedFoldTrainingReceipt
    receipt: Mapping[str, Any]
    control_name: str
    regime_declarations: tuple[AssetDayRegime, ...] = ()
    first_failed_boundary: str | None = None
    diagnostic_timings: Mapping[str, Any] | None = None
    store_aggregate_sha256: str | None = None

    # Narrow compatibility accessors for code that has not yet adopted the
    # named arm map.  They do not represent additional campaign arms.
    @property
    def scores(self) -> Mapping[str, np.ndarray]:
        return self.arm_score_arrays[ARM_FULL_PREFIX]

    @property
    def entry_scores(self) -> tuple[EntryScore, ...]:
        return self.arm_entry_scores[ARM_FULL_PREFIX]

    @property
    def scored_arrivals(self) -> tuple[ScoredArrival, ...]:
        return self.arm_arrivals[ARM_FULL_PREFIX]

    @property
    def entry_thresholds(self) -> Mapping[str, float]:
        return self.arm_thresholds[ARM_FULL_PREFIX]

    @property
    def policy_evaluation(self) -> EntryEvaluation:
        return self.arm_evaluations[ARM_FULL_PREFIX]

    @property
    def policies(self) -> Mapping[str, Any]:
        return self.arm_policies[ARM_FULL_PREFIX]

    @property
    def direct_scores(self) -> tuple[EntryScore, ...]:
        return self.arm_entry_scores[ARM_PER_ASSET_STATIC]

    @property
    def direct_arrivals(self) -> tuple[ScoredArrival, ...]:
        return self.arm_arrivals[ARM_PER_ASSET_STATIC]

    @property
    def direct_thresholds(self) -> Mapping[str, float]:
        return self.arm_thresholds[ARM_PER_ASSET_STATIC]

    @property
    def direct_evaluation(self) -> EntryEvaluation:
        return self.arm_evaluations[ARM_PER_ASSET_STATIC]


@dataclass
class SelectedWinnerFoldResult(FoldOOFResult):
    """Post-adoption fold containing exactly the frozen neural winner."""

    @property
    def selected_identity(self) -> Mapping[str, Any]:
        value = self.receipt.get("winner_adoption")
        if (not isinstance(value, Mapping) or value.get("legacy_full_prefix") is not False
                or tuple(self.arm_evaluations) != (ARM_FULL_PREFIX,)):
            raise C.EntryV2Refusal("selected-winner fold identity is incomplete")
        return value


def fold_result_arms(result: FoldOOFResult) -> tuple[str, ...]:
    if isinstance(result, SelectedWinnerFoldResult):
        if tuple(result.arm_evaluations) != (ARM_FULL_PREFIX,):
            raise C.EntryV2Refusal("selected-winner fold contains extra/missing arms")
        return (ARM_FULL_PREFIX,)
    return ARM_NAMES


def fold_training_identity(result: FoldOOFResult) -> FoldTrainingIdentity:
    training = result.training
    winner = result.receipt.get("winner_adoption")
    if isinstance(training, SelectedFoldTrainingReceipt):
        if not isinstance(result, SelectedWinnerFoldResult):
            raise C.EntryV2Refusal("legacy fold cannot use selected training receipt")
        training.validate()
        if (not isinstance(winner, Mapping) or winner.get(
                "e2_frozen_selection_sha256") != training.e2_frozen_selection_sha256):
            raise C.EntryV2Refusal("selected training/E2 identity differs")
        return FoldTrainingIdentity(
            training.training_receipt_sha256,
            training.normalizers_payload_sha256,
            training.model_input_binding,
            training,
        )
    if not isinstance(training, TrainingArtifact) and not (
            hasattr(training, "trace") and hasattr(training, "normalizer")):
        raise C.EntryV2Refusal("fold training identity is unsupported")
    if isinstance(result, SelectedWinnerFoldResult):
        system = training.system
        transform = getattr(system, "event_transform", None)
        receipt = SelectedFoldTrainingReceipt.freeze(
            training_receipt_sha256=training.trace.receipt_sha256,
            normalizers_payload_sha256=training.normalizer.receipt_sha256,
            model_input_binding=training.trace.model_input_binding,
            expanded_schema_sha256=str(getattr(transform, "schema_sha256", "")),
            expanded_transform_law_sha256=str(
                getattr(transform, "transform_law_sha256", "")),
            e2_frozen_selection_sha256=str(
                getattr(system, "e2_frozen_selection_sha256", "")),
            checkpoint_set_sha256=training.trace.final_model_sha256,
            chronological_stage_receipts_sha256=C.object_sha256([
                asdict(value) for value in training.trace.passes
            ]),
            selected_horizon_schema_sha256=str(getattr(
                system, "selected_horizon_schema_sha256", "")),
            selected_horizon_target_law_sha256=
                SELECTED_HORIZON_TARGET_LAW_SHA256,
            selected_horizon_normalizer_sha256=str(getattr(
                system, "selected_horizon_normalizer_sha256", "")),
            selected_output_schema_sha256=str(getattr(
                getattr(system, "model", None), "head", None
            ).output_schema_sha256 if getattr(
                getattr(system, "model", None), "head", None
            ) is not None else ""),
            selected_ordinal_semantics_sha256=
                SELECTED_ORDINAL_SEMANTICS_SHA256,
        )
        if (not isinstance(winner, Mapping) or winner.get(
                "e2_frozen_selection_sha256") != receipt.e2_frozen_selection_sha256):
            raise C.EntryV2Refusal("selected training/E2 identity differs")
        return FoldTrainingIdentity(
            receipt.training_receipt_sha256,
            receipt.normalizers_payload_sha256,
            receipt.model_input_binding,
            receipt,
        )
    return FoldTrainingIdentity(
        training.trace.receipt_sha256,
        training.normalizer.receipt_sha256,
        training.trace.model_input_binding,
    )


def build_selected_winner_fold_report(
    result: FoldOOFResult,
    *,
    selected_arm: str,
    decision_head_kind: str,
    objective_sha256: str,
    target_row_manifest_sha256: str,
    target_control_sha256: str,
    e2_frozen_selection_sha256: str,
) -> SelectedWinnerFoldResult:
    """Promote a measured selected-only report without fabricating controls.

    The producer must already have evaluated exactly the adopted policy.  This
    constructor only validates its immutable identities and changes the result
    type; it never trains, scores, replays, or synthesizes legacy arm maps.
    """

    maps = (
        result.arm_score_arrays, result.arm_entry_scores, result.arm_arrivals,
        result.arm_thresholds, result.arm_evaluations, result.arm_policies,
    )
    if any(tuple(value) != (ARM_FULL_PREFIX,) for value in maps):
        raise C.EntryV2Refusal(
            "selected-winner report must contain exactly one measured policy arm"
        )
    if (not isinstance(result.training, SelectedFoldTrainingReceipt)
            or result.training.e2_frozen_selection_sha256
                != e2_frozen_selection_sha256):
        raise C.EntryV2Refusal(
            "held selected report lacks its real compact training receipt"
        )
    result.training.validate()
    result.training.model_input_binding.validate()
    try:
        receipt_binding = ModelInputBinding.from_mapping(
            result.receipt["model_input_binding"])
    except (KeyError, TypeError, ValueError) as exc:
        raise C.EntryV2Refusal("selected report model binding is absent") from exc
    if (result.receipt.get("training_receipt_sha256")
            != result.training.training_receipt_sha256
            or result.receipt.get("normalizer_sha256")
                != result.training.normalizers_payload_sha256
            or receipt_binding.binding_sha256
                != result.training.model_input_binding.binding_sha256):
        raise C.EntryV2Refusal(
            "selected report training receipt differs from its fold receipt"
        )
    winner = result.receipt.get("winner_adoption")
    expected = {
        "arm": selected_arm,
        "decision_head_kind": decision_head_kind,
        "objective_sha256": objective_sha256,
        "target_row_manifest_sha256": target_row_manifest_sha256,
        "target_control_sha256": target_control_sha256,
        "e2_frozen_selection_sha256": e2_frozen_selection_sha256,
    }
    if (not isinstance(winner, Mapping)
            or winner.get("legacy_full_prefix") is not False
            or any(winner.get(key) != value for key, value in expected.items())
            or tuple(result.receipt.get("arms", ())) != (ARM_FULL_PREFIX,)):
        raise C.EntryV2Refusal(
            "selected-winner report identity differs from its frozen selection"
        )
    policy_training = result.receipt.get("selected_policy_training")
    if not isinstance(policy_training, Mapping):
        raise C.EntryV2Refusal(
            "selected-winner report lacks frozen policy training evidence"
        )
    validate_selected_policy_training_receipt(
        policy_training, decision_head_kind=decision_head_kind,
        fit_days=tuple(policy_training.get("fit_days", ())),
        calibration_days=tuple(policy_training.get("calibration_days", ())),
        selection_days=tuple(policy_training.get("selection_days", ())),
    )
    return SelectedWinnerFoldResult(**{
        field.name: getattr(result, field.name)
        for field in fields(FoldOOFResult)
    })


PolicyFactory = Callable[[str, TrainingConfig, ModelInputBinding], Any]


def _default_policy_factory(
    asset: str, config: TrainingConfig, model_input_binding: ModelInputBinding
) -> AssetPolicy:
    return AssetPolicy(
        asset,
        PolicyConfig(workers=config.workers, seed=config.seed),
        model_input_binding,
    )


def _policy_factory_dispatch(*, selected_winner: bool,
                             selected_factory: PolicyFactory | None
                             ) -> Mapping[str, PolicyFactory]:
    if selected_winner and selected_factory is None:
        raise C.EntryV2Refusal("selected winner lacks its policy factory")
    learned = selected_factory or _default_policy_factory
    baseline = _default_policy_factory if selected_winner else learned
    return MappingProxyType({
        ARM_POOLED_STATIC: baseline,
        ARM_PER_ASSET_STATIC: baseline,
        ARM_FULL_PREFIX: learned,
    })


def _take(rows: _EncodedRows, mask: np.ndarray) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    return rows.embeddings[mask], {key: value[mask] for key, value in rows.targets.items()}


def _subset_rows(rows: _EncodedRows, mask: np.ndarray) -> _EncodedRows:
    choose = np.asarray(mask, dtype=bool)
    if choose.shape != (len(rows.candidate_ids),) or not choose.any():
        raise C.EntryV2Refusal("encoded-row subset is empty or misaligned")
    indexes = np.flatnonzero(choose).tolist()
    return _EncodedRows(
        tuple(rows.examples[index] for index in indexes),
        tuple(rows.candidate_ids[index] for index in indexes),
        tuple(rows.assets[index] for index in indexes),
        rows.days[choose],
        rows.embeddings[choose],
        MappingProxyType({key: value[choose]
                          for key, value in rows.targets.items()}),
    )


def _array_hash(named: Mapping[str, np.ndarray]) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(named.items()):
        x = np.ascontiguousarray(value)
        digest.update(name.encode())
        digest.update(str(x.shape).encode())
        digest.update(str(x.dtype).encode())
        digest.update(x.tobytes())
    return digest.hexdigest()


def _merge_scores(
    destination: dict[str, np.ndarray],
    mask: np.ndarray,
    scored: Mapping[str, np.ndarray],
    rows: int,
    schema: set[str] | None,
    asset: str,
) -> set[str]:
    names = set(scored)
    if schema is not None and names != schema:
        raise C.EntryV2Refusal(f"{asset}: policy output schema differs by asset")
    for name, value in scored.items():
        array = np.asarray(value)
        if array.shape[0] != int(mask.sum()):
            raise C.EntryV2Refusal(f"{asset}: policy output {name} is misaligned")
        if name not in destination:
            destination[name] = np.empty((rows, *array.shape[1:]), dtype=array.dtype)
        destination[name][mask] = array
    return names


def _concat_policy_raw(parts: Sequence[Mapping[str, np.ndarray]]) -> dict[str, np.ndarray]:
    if not parts:
        raise C.EntryV2Refusal("prequential calibration has no raw predictions")
    names = set(parts[0])
    if any(set(part) != names for part in parts):
        raise C.EntryV2Refusal("prequential raw prediction schema changes by block")
    return {
        name: np.concatenate([np.asarray(part[name]) for part in parts])
        for name in sorted(names)
    }


def _concat_targets(parts: Sequence[Mapping[str, np.ndarray]]) -> dict[str, np.ndarray]:
    if not parts:
        raise C.EntryV2Refusal("prequential calibration has no target rows")
    names = set(parts[0])
    if any(set(part) != names for part in parts):
        raise C.EntryV2Refusal("prequential target schema changes by block")
    return {
        name: np.concatenate([np.asarray(part[name]) for part in parts])
        for name in sorted(names)
    }


def _policy_score_raw(policy: Any, raw: Mapping[str, np.ndarray]) -> Mapping[str, np.ndarray]:
    method = getattr(policy, "score_raw", None)
    if method is None:
        raise C.EntryV2Refusal(
            "policy lacks score_raw; honest prequential calibration is impossible"
        )
    return method(raw)


@dataclass(frozen=True)
class _ArmFit:
    scores: Mapping[str, np.ndarray]
    thresholds: Mapping[str, float]
    selections: Mapping[str, ThresholdSelection]
    policies: Mapping[str, Any]
    calibration_days: tuple[int, ...]
    selection_days: tuple[int, ...]
    diagnostic_timings: Mapping[str, Any]


@dataclass(frozen=True, order=True)
class _PolicyTaskKey:
    arm_order: int
    scope_order: int
    fit_order: int
    arm: str
    scope: str
    fit_name: str

    def label(self) -> str:
        return f"{self.arm}/{self.scope}/{self.fit_name}"


@dataclass(frozen=True)
class _PolicyTaskResult:
    policy: Any | None
    raw: Mapping[str, np.ndarray] | None
    wall_seconds: float


@dataclass(frozen=True)
class _PreparedScope:
    scope: str
    test_mask: np.ndarray
    block_rows: tuple[_EncodedRows, ...]
    block_features: tuple[np.ndarray, ...]
    block_targets: tuple[Mapping[str, np.ndarray], ...]
    tasks: tuple[tuple[_PolicyTaskKey, Future[_PolicyTaskResult]], ...]


@dataclass(frozen=True)
class _PreparedArm:
    arm: str
    pooled: bool
    train_only_frozen: bool
    scopes: tuple[_PreparedScope, ...]
    calibration_days: tuple[int, ...]
    selection_days: tuple[int, ...]


def _policy_fit_task(
    factory: PolicyFactory,
    scope: str,
    config: TrainingConfig,
    model_input_binding: ModelInputBinding,
    fit_x: np.ndarray,
    fit_y: Mapping[str, np.ndarray],
    predict_x: np.ndarray | None,
) -> _PolicyTaskResult:
    started = perf_counter()
    policy = factory(scope, config, model_input_binding)
    policy.fit(fit_x, fit_y)
    if predict_x is None:
        return _PolicyTaskResult(policy, None, perf_counter() - started)
    raw = policy.raw_predict(predict_x)
    del policy
    return _PolicyTaskResult(None, raw, perf_counter() - started)


def _prepare_prequential_arm(
    arm: str,
    fit_rows: _EncodedRows,
    inner_rows: _EncodedRows,
    test_rows: _EncodedRows,
    fold: FoldSpec,
    replay_data: ReplayCalibrationData,
    config: TrainingConfig,
    model_input_binding: ModelInputBinding,
    factory: PolicyFactory,
    executor: ThreadPoolExecutor,
) -> _PreparedArm:
    """Prepare and submit independent fits without consuming any result."""

    if arm not in ARM_NAMES:
        raise C.EntryV2Refusal(f"unknown campaign arm {arm}")
    blocks = tuple(tuple(int(day) for day in block)
                   for block in fold.prequential_blocks)
    if len(blocks) < 2:
        raise C.EntryV2Refusal("prequential policy path requires at least two blocks")
    calibration_days = tuple(day for block in blocks[:-1] for day in block)
    selection_days = tuple(blocks[-1])
    if set(calibration_days) & set(selection_days):
        raise C.EntryV2Refusal("calibration and threshold-selection days overlap")

    pooled = arm == ARM_POOLED_STATIC
    train_only_frozen = (
        getattr(factory, "fit_chronology_law", None)
        == SELECTED_POLICY_CHRONOLOGY_LAW
    )
    if train_only_frozen and (arm != ARM_FULL_PREFIX or pooled):
        raise C.EntryV2Refusal(
            "TRAIN-only selected policy may be used only by the full-prefix arm"
        )
    scopes = (POOLED_SCOPE,) if pooled else tuple(C.ASSETS)
    prepared_scopes: list[_PreparedScope] = []

    for scope_order, scope in enumerate(scopes):
        def scope_mask(rows: _EncodedRows) -> np.ndarray:
            if pooled:
                return np.ones(len(rows.candidate_ids), dtype=bool)
            return np.asarray([asset == scope for asset in rows.assets], dtype=bool)

        fit_scope = scope_mask(fit_rows)
        inner_scope = scope_mask(inner_rows)
        test_scope = scope_mask(test_rows)
        if not fit_scope.any() or not inner_scope.any() or not test_scope.any():
            raise C.EntryV2Refusal(f"{arm}/{scope}: missing fit/inner/test rows")

        target_by_block: list[Mapping[str, np.ndarray]] = []
        row_by_block: list[_EncodedRows] = []
        feature_by_block: list[np.ndarray] = []
        tasks: list[tuple[_PolicyTaskKey, Future[_PolicyTaskResult]]] = []
        prior_days: set[int] = set()
        fit_x, fit_y = _take(fit_rows, fit_scope)
        for block_index, block in enumerate(blocks):
            # Build history by concatenating fit with only earlier inner rows.
            prior_mask = scope_mask(inner_rows) & np.isin(
                inner_rows.days, tuple(sorted(prior_days))
            )
            if not train_only_frozen and prior_mask.any():
                prior_x, prior_y = _take(inner_rows, prior_mask)
                history_x = np.concatenate((fit_x, prior_x))
                history_y = {
                    key: np.concatenate((fit_y[key], prior_y[key]))
                    for key in fit_y
                }
            elif not train_only_frozen:
                history_x, history_y = fit_x, fit_y
            block_mask = scope_mask(inner_rows) & np.isin(inner_rows.days, block)
            if not block_mask.any():
                raise C.EntryV2Refusal(
                    f"{arm}/{scope}: prequential block has no candidate rows"
                )
            block_rows = _subset_rows(inner_rows, block_mask)
            block_x, block_y = _take(inner_rows, block_mask)
            if not train_only_frozen:
                key = _PolicyTaskKey(
                    ARM_NAMES.index(arm), scope_order, block_index,
                    arm, scope, f"block-{block_index}",
                )
                tasks.append((key, executor.submit(
                    _policy_fit_task, factory, scope, config, model_input_binding,
                    history_x, history_y, block_x,
                )))
            target_by_block.append(block_y)
            row_by_block.append(block_rows)
            feature_by_block.append(block_x)
            prior_days.update(block)

        final_x, final_y = fit_x, fit_y
        if not train_only_frozen:
            inner_x, inner_y = _take(inner_rows, inner_scope)
            final_x = np.concatenate((fit_x, inner_x))
            final_y = {
                name: np.concatenate((fit_y[name], inner_y[name]))
                for name in fit_y
            }
        key = _PolicyTaskKey(
            ARM_NAMES.index(arm), scope_order, len(blocks),
            arm, scope, ("train-only-frozen" if train_only_frozen else "final"),
        )
        tasks.append((key, executor.submit(
            _policy_fit_task, factory, scope, config, model_input_binding,
            final_x, final_y,
            None,
        )))
        prepared_scopes.append(_PreparedScope(
            scope, test_scope, tuple(row_by_block), tuple(feature_by_block),
            tuple(target_by_block), tuple(tasks),
        ))

    return _PreparedArm(
        arm, pooled, train_only_frozen, tuple(prepared_scopes),
        calibration_days, selection_days
    )


def _fit_prequential_arm(
    prepared: _PreparedArm,
    test_rows: _EncodedRows,
    replay_data: ReplayCalibrationData,
) -> _ArmFit:
    """Consume prepared fits canonically, then calibrate/select serially."""

    arm = prepared.arm
    merged_test: dict[str, np.ndarray] = {}
    schema: set[str] | None = None
    policies: dict[str, Any] = {}
    selections: dict[str, ThresholdSelection] = {}
    task_timings: dict[str, float] = {}
    scope_timings: dict[str, float] = {}
    threshold_test_seconds = 0.0

    for prepared_scope in prepared.scopes:
        scope = prepared_scope.scope
        scope_started = perf_counter()
        results: list[_PolicyTaskResult] = []
        for key, future in prepared_scope.tasks:
            try:
                result = future.result()
            except BaseException as exc:
                if isinstance(exc, C.EntryV2Refusal):
                    raise C.EntryV2Refusal(
                        f"policy task {key.label()} refused: {exc}"
                    ) from exc
                raise C.EntryV2Refusal(
                    f"policy task {key.label()} failed"
                ) from exc
            results.append(result)
            task_timings[key.label()] = result.wall_seconds
        if not results or results[-1].policy is None or results[-1].raw is not None:
            raise C.EntryV2Refusal(
                f"{arm}/{scope}: final task result state is invalid"
            )
        final_policy = results[-1].policy
        if prepared.train_only_frozen:
            if len(results) != 1:
                raise C.EntryV2Refusal(
                    f"{arm}/{scope}: TRAIN-only policy was refitted on held labels"
                )
            raw_by_block = [
                final_policy.raw_predict(features)
                for features in prepared_scope.block_features
            ]
        else:
            historical_results = results[:-1]
            if any(result.policy is not None or result.raw is None
                   for result in historical_results):
                raise C.EntryV2Refusal(
                    f"{arm}/{scope}: historical task result state is invalid"
                )
            raw_by_block = [result.raw for result in historical_results]
        if len(raw_by_block) != len(prepared_scope.block_targets):
            raise C.EntryV2Refusal(
                f"{arm}/{scope}: policy chronology output count differs"
            )
        scoring_started = perf_counter()
        final_policy.calibrate(
            _concat_policy_raw(raw_by_block[:-1]),  # type: ignore[arg-type]
            _concat_targets(prepared_scope.block_targets[:-1]),
        )
        selection_scored = _policy_score_raw(final_policy, raw_by_block[-1])
        selection_rows = prepared_scope.block_rows[-1]
        if prepared.pooled:
            for asset in C.ASSETS:
                asset_mask = np.asarray(
                    [item == asset for item in selection_rows.assets], dtype=bool
                )
                if not asset_mask.any():
                    raise C.EntryV2Refusal(
                        f"{arm}: selection block has no {asset} candidates"
                    )
                selections[asset] = _select_inner_threshold(
                    asset,
                    _subset_rows(selection_rows, asset_mask),
                    {key: np.asarray(value)[asset_mask]
                     for key, value in selection_scored.items()},
                    replay_data,
                    prepared.selection_days,
                )
        else:
            selections[scope] = _select_inner_threshold(
                scope, selection_rows, selection_scored,
                replay_data, prepared.selection_days,
            )
        test_x, _test_y = _take(test_rows, prepared_scope.test_mask)
        test_scored = _policy_score_raw(
            final_policy, final_policy.raw_predict(test_x)
        )
        names = _merge_scores(
            merged_test, prepared_scope.test_mask, test_scored,
            len(test_rows.candidate_ids), schema, scope,
        )
        schema = names
        policies[scope] = final_policy
        threshold_test_seconds += perf_counter() - scoring_started
        scope_timings[scope] = perf_counter() - scope_started

    if set(selections) != set(C.ASSETS):
        raise C.EntryV2Refusal(f"{arm}: thresholds do not cover SI/HG/NKD")
    return _ArmFit(
        scores=MappingProxyType(merged_test),
        thresholds=MappingProxyType({
            asset: selections[asset].threshold for asset in C.ASSETS
        }),
        selections=MappingProxyType(selections),
        policies=MappingProxyType(policies),
        calibration_days=prepared.calibration_days,
        selection_days=prepared.selection_days,
        diagnostic_timings=MappingProxyType({
            "tasks": MappingProxyType(task_timings),
            "scopes": MappingProxyType(scope_timings),
            "aggregate_task_seconds": sum(task_timings.values()),
            "threshold_and_test_scoring_seconds": threshold_test_seconds,
        }),
    )


def validate_selected_policy_training_receipt(
    document: Mapping[str, Any], *, decision_head_kind: str,
    fit_days: Sequence[int], calibration_days: Sequence[int],
    selection_days: Sequence[int],
) -> Mapping[str, Any]:
    """Validate the fold-causal selected policy law without trusting booleans."""

    try:
        core = dict(document)
        declared = core.pop("sha256")
        per_asset = dict(core["per_asset"])
    except (KeyError, TypeError, ValueError) as exc:
        raise C.EntryV2Refusal(
            "selected policy training receipt is incomplete"
        ) from exc
    expected_pair = decision_head_kind == "catboost"
    valid = bool(
        core.get("schema") == SELECTED_POLICY_TRAINING_SCHEMA
        and core.get("chronology_law") == SELECTED_POLICY_CHRONOLOGY_LAW
        and core.get("action_fit_weight_law") == SELECTED_ACTION_FIT_WEIGHT_LAW
        and core.get("phase_pair_law") == SELECTED_PHASE_PAIR_LAW
        and core.get("decision_head_kind") == decision_head_kind
        and tuple(core.get("fit_days", ())) == tuple(int(day) for day in fit_days)
        and tuple(core.get("calibration_days", ()))
            == tuple(int(day) for day in calibration_days)
        and tuple(core.get("selection_days", ()))
            == tuple(int(day) for day in selection_days)
        and not (set(fit_days) & set(calibration_days)
                 or set(fit_days) & set(selection_days)
                 or set(calibration_days) & set(selection_days))
        and tuple(core.get("asset_order", ())) == tuple(C.ASSETS)
        and set(per_asset) == set(C.ASSETS)
        and isinstance(declared, str) and len(declared) == 64
        and C.object_sha256(core) == declared
    )
    if not valid:
        raise C.EntryV2Refusal("selected policy training law differs")
    for asset in C.ASSETS:
        row = per_asset[asset]
        try:
            hashes = (
                row["training_candidate_sha256"],
                row["calibration_candidate_sha256"],
                row["action_fit_weight_receipt_sha256"],
                row["mapper_parameter_sha256"],
            )
            pair_hash = row["phase_pair_manifest_sha256"]
            row_valid = bool(
                row["schema"] == "entry-v2-selected-policy-asset-fit-v1"
                and row["asset"] == asset
                and row["chronology_law"] == SELECTED_POLICY_CHRONOLOGY_LAW
                and row["optimizer_step_unit"]
                    == "complete_asset_day_gradient"
                and row["mapper_weighting"] == "A013_ACTION_FIT_WEIGHTS"
                and int(row["training_rows"]) > 0
                and int(row["calibration_rows"]) > 0
                and all(isinstance(value, str) and len(value) == 64
                        for value in hashes)
                and ((expected_pair and isinstance(pair_hash, str)
                      and len(pair_hash) == 64
                      and int(row["phase_pair_count"]) > 0)
                     or (not expected_pair and pair_hash is None
                         and int(row["phase_pair_count"]) == 0))
            )
        except (KeyError, TypeError, ValueError):
            row_valid = False
        if not row_valid:
            raise C.EntryV2Refusal(
                f"selected policy training evidence differs for {asset}"
            )
    return MappingProxyType(core)


def _selected_policy_training_receipt(
    arm_fit: _ArmFit, fold: FoldSpec, decision_head_kind: str,
) -> Mapping[str, Any]:
    per_asset: dict[str, Mapping[str, Any]] = {}
    for asset in C.ASSETS:
        policy = arm_fit.policies.get(asset)
        evidence = getattr(policy, "selected_training_evidence", None)
        if not isinstance(evidence, Mapping):
            raise C.EntryV2Refusal(
                f"selected policy lacks measured training evidence for {asset}"
            )
        per_asset[asset] = dict(evidence)
    core: dict[str, Any] = {
        "schema": SELECTED_POLICY_TRAINING_SCHEMA,
        "chronology_law": SELECTED_POLICY_CHRONOLOGY_LAW,
        "action_fit_weight_law": SELECTED_ACTION_FIT_WEIGHT_LAW,
        "phase_pair_law": SELECTED_PHASE_PAIR_LAW,
        "decision_head_kind": decision_head_kind,
        "asset_order": list(C.ASSETS),
        "fit_days": [int(day) for day in fold.fit_days],
        "calibration_days": [int(day) for day in arm_fit.calibration_days],
        "selection_days": [int(day) for day in arm_fit.selection_days],
        "per_asset": per_asset,
    }
    document = {**core, "sha256": C.object_sha256(core)}
    validate_selected_policy_training_receipt(
        document, decision_head_kind=decision_head_kind,
        fit_days=fold.fit_days, calibration_days=arm_fit.calibration_days,
        selection_days=arm_fit.selection_days,
    )
    return MappingProxyType(document)


def _entry_scores(
    rows: _EncodedRows,
    scored: Mapping[str, np.ndarray],
    thresholds: Mapping[str, float],
    model_hash: str,
) -> tuple[EntryScore, ...]:
    required = {
        "action_p",
        "top3_p",
        "wall_p_upper",
        "expected_value_raw",
        "expected_value_lower",
        "expected_value_upper",
        "mae_q90",
    }
    missing = required.difference(scored)
    if missing:
        raise C.EntryV2Refusal(f"replay score fields missing: {sorted(missing)}")
    action_thresholds = np.asarray(
        [thresholds[example.asset] for example in rows.examples],
        dtype=np.float64,
    )
    enter = entry_decision_gate(
        scored["action_p"],
        action_thresholds,
        scored["expected_value_lower"],
        np.maximum(0.0, np.asarray(scored["mae_q90"], dtype=np.float64)),
        scored["wall_p_upper"],
        expected_pnl_upper_usd=scored["expected_value_upper"],
    )
    return tuple(
        EntryScore(
            candidate_id=example.candidate_id,
            asset=example.asset,
            decision_ts_ns=example.decision_ts_ns,
            model_hash=model_hash,
            # Calibrated action probability is the sole learned decision and
            # ranking surface.  Value/risk predictions remain diagnostics.
            priority_score=float(scored["action_p"][i]),
            take_probability=float(scored["action_p"][i]),
            expected_pnl_usd=float(scored["expected_value_raw"][i]),
            expected_pnl_lower_usd=float(scored["expected_value_lower"][i]),
            top3_probability=float(scored["top3_p"][i]),
            mae_p90_usd=max(0.0, float(scored["mae_q90"][i])),
            wall_probability=float(scored["wall_p_upper"][i]),
            enter=bool(enter[i]),
        )
        for i, example in enumerate(rows.examples)
    )


def _pre_encoder_action_supervision_census(
    fit: Sequence[EntrySessionSpec],
    inner: Sequence[EntrySessionSpec],
    teacher: TeacherStore,
    fold: FoldSpec,
) -> Mapping[str, Any]:
    """Refuse impossible per-asset action fits/calibration before encoding."""

    calibration_days = {
        int(day) for block in fold.prequential_blocks[:-1] for day in block
    }

    def labels_for(
        batches: Sequence[EntrySessionSpec], asset: str, days: set[int] | None = None
    ) -> tuple[TeacherLabel, ...]:
        return tuple(
            teacher[example.candidate_id]
            for batch in batches
            if days is None or int(batch.trading_day) in days
            for example in batch.examples
            if example.asset == asset
        )

    evidence: dict[str, Any] = {}
    for asset in C.ASSETS:
        fit_labels = labels_for(fit, asset)
        calibration_labels = labels_for(inner, asset, calibration_days)
        fit_supervised = tuple(row for row in fit_labels if row.action_loss_mask)
        calibration_supervised = tuple(
            row for row in calibration_labels if row.action_loss_mask
        )
        fit_classes = sorted({int(row.take_target) for row in fit_supervised})
        calibration_classes = sorted(
            {int(row.take_target) for row in calibration_supervised}
        )
        evidence[asset] = {
            "fit_supervised_rows": len(fit_supervised),
            "fit_action_classes": fit_classes,
            "calibration_supervised_rows": len(calibration_supervised),
            "calibration_action_classes": calibration_classes,
            "calibrator_minimum_rows": 30,
        }
        if not fit_supervised:
            raise C.EntryV2Refusal(
                f"{fold.test_era}/{asset}: no fit action-supervised rows"
            )
        if fit_classes != [0, 1]:
            raise C.EntryV2Refusal(
                f"{fold.test_era}/{asset}: fit action supervision lacks both classes"
            )
        if len(calibration_supervised) < 30:
            raise C.EntryV2Refusal(
                f"{fold.test_era}/{asset}: calibration action supervision has fewer than 30 rows"
            )
        if calibration_classes != [0, 1]:
            raise C.EntryV2Refusal(
                f"{fold.test_era}/{asset}: calibration action supervision lacks both classes"
            )
    return MappingProxyType({
        "schema": "entry-v2-action-supervision-census-v1",
        "per_asset": evidence,
        "passed": True,
    })


@dataclass(frozen=True)
class ThresholdFunnel:
    threshold: float
    candidate_count: int
    action_pass: int
    diagnostic_value_pass: int
    diagnostic_mae_pass: int
    diagnostic_wall_pass: int
    diagnostic_intersection_pass: int
    replay_trades: int
    replay_total_pnl_usd: float
    replay_usd_per_trade: float
    replay_usd_per_asset_day: float
    replay_chronological_mdd_usd: float
    feasible: bool
    reason: str


@dataclass(frozen=True)
class ThresholdSelection:
    asset: str
    threshold: float
    asset_days: int
    usd_per_asset_day: float
    usd_per_trade: float
    max_drawdown_usd: float
    drawdown_p90_usd: float
    trades: int
    feasible_thresholds: int
    funnel: tuple[ThresholdFunnel, ...]


def _threshold_feasibility_reason(result: EntryEvaluation) -> str:
    reasons: list[str] = []
    if result.trades <= 0:
        reasons.append("NO_REPLAY_TRADES")
    if result.trades > 0 and result.usd_per_trade < C.MIN_EXPECTANCY_USD:
        reasons.append("USD_PER_TRADE_BELOW_MIN_EXPECTANCY")
    if result.max_drawdown_usd > C.TARGET_MDD_USD:
        reasons.append("CHRONOLOGICAL_MDD_ABOVE_TARGET")
    return "FEASIBLE" if not reasons else "+".join(reasons)


def _diagnostic_counts(scored: Mapping[str, np.ndarray]) -> tuple[int, int, int, int]:
    lower = np.asarray(scored["expected_value_lower"], dtype=np.float64)
    mae = np.maximum(0.0, np.asarray(scored["mae_q90"], dtype=np.float64))
    wall = np.asarray(scored["wall_p_upper"], dtype=np.float64)
    intersection = policy_risk_gate(lower, mae, wall)
    value_pass = lower >= C.MIN_EXPECTANCY_USD
    mae_pass = mae <= predicted_mae_limit_usd(lower)
    wall_pass = wall <= PolicyConfig().wall_probability_upper_max
    return (
        int(np.count_nonzero(value_pass)),
        int(np.count_nonzero(mae_pass)),
        int(np.count_nonzero(wall_pass)),
        int(np.count_nonzero(intersection)),
    )


def _action_threshold_candidates(action_probability: Any) -> tuple[float, ...]:
    """Exact >= decision sets: each calibrated level plus no-entry sentinel."""

    action = np.asarray(action_probability, dtype=np.float64)
    if (action.ndim != 1 or action.size == 0 or not np.all(np.isfinite(action))
            or np.any((action < 0.0) | (action > 1.0))):
        raise C.EntryV2Refusal("invalid calibrated action threshold surface")
    levels = tuple(float(value) for value in np.unique(action))
    if len(levels) > PolicyConfig().venn_bins:
        raise C.EntryV2Refusal("calibrated action levels exceed frozen Venn bins")
    sentinel = float(np.nextafter(levels[-1], np.inf))
    if not np.isfinite(sentinel) or sentinel <= levels[-1]:
        raise C.EntryV2Refusal("cannot construct action no-entry sentinel")
    return (*levels, sentinel)


def _select_inner_threshold(
    asset: str,
    rows: _EncodedRows,
    scored: Mapping[str, np.ndarray],
    replay_data: ReplayCalibrationData,
    selection_days: Iterable[int],
) -> ThresholdSelection:
    """Select once by exact inner asset-day replay; loss/AUC never participate."""

    if set(rows.assets) != {asset}:
        raise C.EntryV2Refusal("threshold selection must receive one asset only")
    sessions = replay_data.sessions_for(selection_days, asset=asset)
    asset_days = {(session.asset, session.trading_day) for session in sessions}
    candidate_count = len(rows.candidate_ids)
    value_pass, mae_pass, wall_pass, intersection_pass = _diagnostic_counts(scored)
    feasible: list[tuple[float, float, float, float, float, int]] = []
    funnel: list[ThresholdFunnel] = []
    threshold_candidates = _action_threshold_candidates(scored["action_p"])
    for threshold in threshold_candidates:
        scores = _entry_scores(
            rows, scored, {asset: threshold},
            f"inner-threshold-selection:{asset}",
        )
        arrivals = tuple(
            ScoredArrival(
                example,
                score,
                replay_data.outcomes[example.candidate_id],
            )
            for example, score in zip(rows.examples, scores)
        )
        result = replay(arrivals, expected_sessions=sessions)
        usd_per_asset_day = result.total_pnl_usd / len(asset_days)
        reason = _threshold_feasibility_reason(result)
        is_feasible = reason == "FEASIBLE"
        funnel.append(ThresholdFunnel(
            threshold=float(threshold),
            candidate_count=candidate_count,
            action_pass=int(np.count_nonzero(
                np.asarray(scored["action_p"], dtype=np.float64) >= threshold
            )),
            diagnostic_value_pass=value_pass,
            diagnostic_mae_pass=mae_pass,
            diagnostic_wall_pass=wall_pass,
            diagnostic_intersection_pass=intersection_pass,
            replay_trades=int(result.trades),
            replay_total_pnl_usd=float(result.total_pnl_usd),
            replay_usd_per_trade=float(result.usd_per_trade),
            replay_usd_per_asset_day=float(usd_per_asset_day),
            replay_chronological_mdd_usd=float(result.max_drawdown_usd),
            feasible=is_feasible,
            reason=reason,
        ))
        if is_feasible:
            feasible.append(
                (
                    float(usd_per_asset_day),
                    float(result.usd_per_trade),
                    -float(result.max_drawdown_usd),
                    -float(result.drawdown_p90_usd),
                    float(threshold),
                    int(result.trades),
                )
            )
    if not feasible:
        return ThresholdSelection(
            asset=asset,
            threshold=threshold_candidates[-1],
            asset_days=len(asset_days),
            usd_per_asset_day=0.0,
            usd_per_trade=0.0,
            max_drawdown_usd=0.0,
            drawdown_p90_usd=0.0,
            trades=0,
            feasible_thresholds=0,
            funnel=tuple(funnel),
        )
    # Optimize exact dollars per asset-day; remaining fields are deterministic,
    # conservative tie-breaks, including the higher threshold on exact ties.
    best = max(feasible)
    return ThresholdSelection(
        asset=asset,
        threshold=best[4],
        asset_days=len(asset_days),
        usd_per_asset_day=best[0],
        usd_per_trade=best[1],
        max_drawdown_usd=-best[2],
        drawdown_p90_usd=-best[3],
        trades=best[5],
        feasible_thresholds=len(feasible),
        funnel=tuple(funnel),
    )


def _select_truth_threshold(
    asset: str,
    rows: _EncodedRows,
    teacher: TeacherStore,
    replay_data: ReplayCalibrationData,
    selection_days: Iterable[int],
) -> ThresholdSelection:
    """Freeze the exact-oracle control on inner asset-days only."""

    if set(rows.assets) != {asset}:
        raise C.EntryV2Refusal("truth threshold selection must receive one asset")
    sessions = replay_data.sessions_for(selection_days, asset=asset)
    asset_days = {(session.asset, session.trading_day) for session in sessions}
    feasible: list[tuple[float, float, float, float, float, int]] = []
    funnel: list[ThresholdFunnel] = []
    for threshold in TRUTH_THRESHOLD_GRID_USD:
        all_thresholds = {name: threshold for name in C.ASSETS}
        scores = teacher.truth_scores(
            rows.examples, entry_thresholds_usd=all_thresholds)
        arrivals = tuple(ScoredArrival(
            example, score, replay_data.outcomes[example.candidate_id]
        ) for example, score in zip(rows.examples, scores))
        result = replay(arrivals, expected_sessions=sessions)
        usd_per_asset_day = result.total_pnl_usd / len(asset_days)
        reason = _threshold_feasibility_reason(result)
        is_feasible = reason == "FEASIBLE"
        value_pass = sum(
            score.expected_pnl_lower_usd >= C.MIN_EXPECTANCY_USD
            for score in scores
        )
        mae_pass = sum(
            score.mae_p90_usd <= float(predicted_mae_limit_usd(
                score.expected_pnl_lower_usd
            ))
            for score in scores
        )
        wall_pass = sum(
            score.wall_probability <= PolicyConfig().wall_probability_upper_max
            for score in scores
        )
        intersection_pass = sum(
            bool(policy_risk_gate(
                score.expected_pnl_lower_usd,
                score.mae_p90_usd,
                score.wall_probability,
            ))
            for score in scores
        )
        funnel.append(ThresholdFunnel(
            threshold=float(threshold),
            candidate_count=len(rows.candidate_ids),
            action_pass=sum(score.enter for score in scores),
            diagnostic_value_pass=int(value_pass),
            diagnostic_mae_pass=int(mae_pass),
            diagnostic_wall_pass=int(wall_pass),
            diagnostic_intersection_pass=int(intersection_pass),
            replay_trades=int(result.trades),
            replay_total_pnl_usd=float(result.total_pnl_usd),
            replay_usd_per_trade=float(result.usd_per_trade),
            replay_usd_per_asset_day=float(usd_per_asset_day),
            replay_chronological_mdd_usd=float(result.max_drawdown_usd),
            feasible=is_feasible,
            reason=reason,
        ))
        if is_feasible:
            feasible.append((
                float(usd_per_asset_day),
                float(result.usd_per_trade),
                -float(result.max_drawdown_usd),
                -float(result.drawdown_p90_usd),
                float(threshold),
                int(result.trades),
            ))
    if not feasible:
        no_entry = max(
            teacher[candidate_id].cert_close_usd
            for candidate_id in rows.candidate_ids
        ) + 1.0
        return ThresholdSelection(
            asset=asset,
            threshold=no_entry,
            asset_days=len(asset_days),
            usd_per_asset_day=0.0,
            usd_per_trade=0.0,
            max_drawdown_usd=0.0,
            drawdown_p90_usd=0.0,
            trades=0,
            feasible_thresholds=0,
            funnel=tuple(funnel),
        )
    best = max(feasible)
    return ThresholdSelection(
        asset=asset,
        threshold=best[4],
        asset_days=len(asset_days),
        usd_per_asset_day=best[0],
        usd_per_trade=best[1],
        max_drawdown_usd=-best[2],
        drawdown_p90_usd=-best[3],
        trades=best[5],
        feasible_thresholds=len(feasible),
        funnel=tuple(funnel),
    )


def candidate_oracle_preflight(
    batches: Sequence[EntrySessionSpec],
    teacher: TeacherStore,
    replay_data: ReplayCalibrationData,
    days: Iterable[int],
) -> Mapping[str, Any]:
    """Prove clean candidate headroom before any model fitting occurs."""

    allowed = set(int(day) for day in days)
    if not allowed or any(
        not any(C.is_denominator_day(asset, day) for asset in C.ASSETS)
        for day in allowed
    ):
        raise C.EntryV2Refusal(
            "candidate/oracle preflight calendar is not trading-day clean"
        )
    selected = tuple(
        batch for batch in sorted(batches, key=_batch_key)
        if batch.trading_day in allowed
    )
    examples = tuple(example for batch in selected for example in batch.examples)
    if not examples:
        raise C.EntryV2Refusal("candidate/oracle preflight has no candidates")
    sessions = replay_data.sessions_for(allowed)
    scores = teacher.truth_scores(
        examples,
        entry_thresholds_usd={asset: -1.0e300 for asset in C.ASSETS},
    )
    arrivals = tuple(
        ScoredArrival(
            example,
            score,
            replay_data.outcomes[example.candidate_id],
        )
        for example, score in zip(examples, scores)
    )
    eligible_arrivals = tuple(
        row for row in arrivals
        if teacher[row.example.candidate_id].cert_close_usd
            >= C.MIN_EXPECTANCY_USD
    )
    ceiling = candidate_ceiling(
        eligible_arrivals, expected_sessions=sessions
    )
    evaluation_by_asset = {row.asset: row for row in ceiling.evaluation.by_asset}
    asset_days = {
        asset: {
            (session.asset, session.trading_day)
            for session in sessions
            if session.asset == asset
        }
        for asset in C.ASSETS
    }
    if set(evaluation_by_asset) != set(C.ASSETS) or any(
        not asset_days[asset] for asset in C.ASSETS
    ):
        raise C.EntryV2Refusal(
            "candidate/oracle preflight lacks an asset-day denominator"
        )
    per_asset = {
        asset: {
            "asset_days": len(asset_days[asset]),
            "total_pnl_usd": evaluation_by_asset[asset].total_pnl_usd,
            "usd_per_asset_day": (
                evaluation_by_asset[asset].total_pnl_usd
                / len(asset_days[asset])
            ),
            "oracle_capture": 1.0,
        }
        for asset in C.ASSETS
    }
    for asset in C.ASSETS:
        achieved = float(per_asset[asset]["usd_per_asset_day"])
        per_asset[asset]["oracle_replay_receipt_sha256"] = C.object_sha256({
            "schema": "entry-v2-candidate-oracle-replay-v1",
            "asset": asset,
            "evaluation": asdict(evaluation_by_asset[asset]),
            "schedule_sha256": ceiling.schedule_sha256,
        })
        per_asset[asset]["acceptance_floor_usd_per_asset_day"] = (
            C.LOW_CAPACITY_ASSET_DAY_FLOOR_USD
        )
        per_asset[asset]["normal_floor_usd_per_asset_day"] = (
            C.WEAK_ASSET_DAY_FLOOR_USD
        )
        per_asset[asset]["optimization_goal_usd_per_asset_day"] = (
            C.TARGET_ASSET_DAY_USD
        )
        per_asset[asset]["acceptance_floor_headroom_usd_per_asset_day"] = (
            achieved - C.LOW_CAPACITY_ASSET_DAY_FLOOR_USD
        )
        per_asset[asset]["normal_floor_headroom_usd_per_asset_day"] = (
            achieved - C.WEAK_ASSET_DAY_FLOOR_USD
        )
        per_asset[asset]["goal_headroom_usd_per_asset_day"] = (
            achieved - C.TARGET_ASSET_DAY_USD
        )
        per_asset[asset]["risk_exception_required"] = (
            achieved < C.WEAK_ASSET_DAY_FLOOR_USD
        )
        per_asset[asset]["passed"] = (
            achieved >= C.LOW_CAPACITY_ASSET_DAY_FLOOR_USD
        )
    failed = [
        asset for asset in C.ASSETS
        if not bool(per_asset[asset]["passed"])
    ]
    evidence = {
        "schema": "entry-v2-candidate-oracle-preflight-v5",
        "passed": not failed,
        "acceptance_law": (
            "oracle_usd_per_asset_day >= LOW_CAPACITY_ASSET_DAY_FLOOR_USD"
        ),
        "acceptance_floor_usd_per_asset_day":
            C.LOW_CAPACITY_ASSET_DAY_FLOOR_USD,
        "normal_floor_usd_per_asset_day": C.WEAK_ASSET_DAY_FLOOR_USD,
        "risk_exception_contract": (
            "learned era usd_per_asset_day >= LOW_CAPACITY_ASSET_DAY_FLOOR_USD "
            "and chronological max_drawdown_usd < LOW_CAPACITY_MAX_DRAWDOWN_USD"
        ),
        "risk_exception_max_drawdown_usd": C.LOW_CAPACITY_MAX_DRAWDOWN_USD,
        "optimization_goal_usd_per_asset_day": C.TARGET_ASSET_DAY_USD,
        "optimization_target": "full_total_pnl_usd",
        "values_clipped_to_acceptance_floor": False,
        "schedule_sha256": ceiling.schedule_sha256,
        "per_asset": per_asset,
    }
    if failed:
        detail = ", ".join(
            f"{asset}={per_asset[asset]['usd_per_asset_day']:.2f}"
            for asset in sorted(failed)
        )
        raise CandidateOraclePreflightRefusal(
            "candidate/oracle preflight does not meet "
            "$1,000/asset-day independently: "
            + detail,
            evidence,
        )
    return MappingProxyType(evidence)


def run_fold_oof(
    system: EntryLearningSystem,
    batches: Sequence[EntrySessionSpec],
    teacher: TeacherStore,
    fold: FoldSpec,
    replay_data: ReplayCalibrationData,
    model_input_binding: ModelInputBinding,
    config: TrainingConfig = TrainingConfig(),
    policy_factory: PolicyFactory | None = None,
) -> FoldOOFResult:
    """Train one expanding fold and return only its never-seen test rows."""

    return _run_fold_oof(
        system,
        batches,
        teacher,
        teacher,
        fold,
        replay_data,
        model_input_binding,
        config,
        policy_factory,
        allow_control=False,
    )


def _run_fold_oof(
    system: EntryLearningSystem,
    batches: Sequence[EntrySessionSpec],
    training_teacher: TeacherStore,
    prophet_teacher: TeacherStore,
    fold: FoldSpec,
    replay_data: ReplayCalibrationData,
    model_input_binding: ModelInputBinding,
    config: TrainingConfig,
    policy_factory: PolicyFactory | None,
    *,
    allow_control: bool,
) -> FoldOOFResult:
    """Internal common path for PROPHET and explicitly requested null control."""

    total_started = perf_counter()
    timings: dict[str, Any] = {}
    fold.validate()
    model_input_binding.validate()
    if prophet_teacher.control_name != "PROPHET":
        raise C.EntryV2Refusal("candidate-set capture requires exact PROPHET labels")
    replay_data.validate(batches)
    ordered = _validate_dataset(
        batches, training_teacher, allow_control=allow_control
    )
    fit = tuple(batch for batch in ordered if batch.trading_day in set(fold.fit_days))
    inner = tuple(batch for batch in ordered if batch.trading_day in set(fold.inner_days))
    test = tuple(batch for batch in ordered if batch.trading_day in set(fold.test_days))
    if not fit or not inner or not test:
        raise C.EntryV2Refusal("fit, inner calibration, and test batches are all required")
    if max(batch.trading_day for batch in fit) >= min(batch.trading_day for batch in inner):
        raise C.EntryV2Refusal("inner calibration is not chronological")
    if max(batch.trading_day for batch in inner) >= min(batch.trading_day for batch in test):
        raise C.EntryV2Refusal("test stage is not after calibration")

    # The fold calendar, not the candidate population, declares the complete
    # denominator.  This refuses a missing asset/day instead of union-dropping
    # an outage or a later lock failure.  Regimes must be causal declarations
    # frozen at session open for the exact same roster.
    test_sessions = replay_data.sessions_for(fold.test_days)
    test_regimes = replay_data.regimes_for(fold.test_days)

    oracle_preflight = candidate_oracle_preflight(
        ordered, prophet_teacher, replay_data, fold.test_days
    )
    action_supervision_census = _pre_encoder_action_supervision_census(
        fit, inner, training_teacher, fold
    )
    started = perf_counter()
    artifact = fit_encoder(
        system,
        ordered,
        training_teacher,
        fold,
        model_input_binding,
        config,
        _allow_control=allow_control,
    )
    timings["fit_encoder_seconds"] = perf_counter() - started
    started = perf_counter()
    fit_rows = _encode_rows(artifact, fit, training_teacher, config)
    timings["encode_fit_seconds"] = perf_counter() - started
    started = perf_counter()
    inner_rows = _encode_rows(artifact, inner, training_teacher, config)
    timings["encode_inner_seconds"] = perf_counter() - started
    started = perf_counter()
    test_rows = _encode_rows(artifact, test, training_teacher, config)
    timings["encode_test_seconds"] = perf_counter() - started
    selected_winner = hasattr(artifact.system, "winner_bundle_sha256")
    active_arms = (ARM_FULL_PREFIX,) if selected_winner else ARM_NAMES
    static_fit_rows = static_inner_rows = static_test_rows = None
    if not selected_winner:
        started = perf_counter()
        static_fit_rows = _static_rows(fit, training_teacher)
        timings["static_fit_seconds"] = perf_counter() - started
        started = perf_counter()
        static_inner_rows = _static_rows(inner, training_teacher)
        timings["static_inner_seconds"] = perf_counter() - started
        started = perf_counter()
        static_test_rows = _static_rows(test, training_teacher)
        timings["static_test_seconds"] = perf_counter() - started
        for encoded, static, name in (
            (fit_rows, static_fit_rows, "fit"),
            (inner_rows, static_inner_rows, "inner"),
            (test_rows, static_test_rows, "test"),
        ):
            if encoded.candidate_ids != static.candidate_ids:
                raise C.EntryV2Refusal(
                    f"{name}: static/full-prefix candidate populations differ"
                )
    policy_factories = _policy_factory_dispatch(
        selected_winner=selected_winner,
        selected_factory=policy_factory,
    )
    if selected_winner and getattr(
        policy_factories[ARM_FULL_PREFIX], "fit_chronology_law", None
    ) != SELECTED_POLICY_CHRONOLOGY_LAW:
        raise C.EntryV2Refusal(
            "selected winner policy factory does not enforce TRAIN-only fitting"
        )
    executor = ThreadPoolExecutor(
        max_workers=4, thread_name_prefix="entry-v2-policy"
    )
    prepared_arms: dict[str, _PreparedArm] = {}
    try:
        prepared_arms = ({
            ARM_POOLED_STATIC: _prepare_prequential_arm(
            ARM_POOLED_STATIC, static_fit_rows, static_inner_rows,
            static_test_rows, fold, replay_data, config,
            model_input_binding, policy_factories[ARM_POOLED_STATIC], executor,
            ),
            ARM_PER_ASSET_STATIC: _prepare_prequential_arm(
            ARM_PER_ASSET_STATIC, static_fit_rows, static_inner_rows,
            static_test_rows, fold, replay_data, config,
            model_input_binding, policy_factories[ARM_PER_ASSET_STATIC], executor,
            ),
            ARM_FULL_PREFIX: _prepare_prequential_arm(
            ARM_FULL_PREFIX, fit_rows, inner_rows, test_rows, fold,
            replay_data, config, model_input_binding,
            policy_factories[ARM_FULL_PREFIX], executor,
            ),
        } if not selected_winner else {
            ARM_FULL_PREFIX: _prepare_prequential_arm(
                ARM_FULL_PREFIX, fit_rows, inner_rows, test_rows, fold,
                replay_data, config, model_input_binding,
                policy_factories[ARM_FULL_PREFIX], executor,
            ),
        })
        threshold_test_started = perf_counter()
        arm_fits = {
            arm: _fit_prequential_arm(
                prepared_arms[arm],
                static_test_rows if arm != ARM_FULL_PREFIX else test_rows,
                replay_data,
            )
            for arm in active_arms
        }
        timings["threshold_and_test_scoring_seconds"] = (
            perf_counter() - threshold_test_started
        )
    except BaseException:
        for prepared in prepared_arms.values():
            for scope in prepared.scopes:
                for _key, future in scope.tasks:
                    future.cancel()
        executor.shutdown(wait=True, cancel_futures=True)
        raise
    else:
        executor.shutdown(wait=True)
    timings["policy_tasks"] = MappingProxyType({
        arm: arm_fits[arm].diagnostic_timings for arm in active_arms
    })
    if tuple(arm_fits) != active_arms:
        raise C.EntryV2Refusal("campaign arm order differs from frozen contract")

    fit_inner = set(fit_rows.candidate_ids) | set(inner_rows.candidate_ids)
    if fit_inner.intersection(test_rows.candidate_ids):
        raise C.EntryV2Refusal("OOF output contains a fit/calibration candidate")
    selection_days = tuple(fold.prequential_blocks[-1])
    truth_selections: dict[str, ThresholdSelection] = {}
    selection_mask = np.isin(inner_rows.days, selection_days)
    for asset in C.ASSETS:
        asset_mask = selection_mask & np.asarray(
            [item == asset for item in inner_rows.assets], dtype=bool
        )
        if not asset_mask.any():
            raise C.EntryV2Refusal(
                f"truth threshold selection has no {asset} rows"
            )
        truth_selections[asset] = _select_truth_threshold(
            asset, _subset_rows(inner_rows, asset_mask), prophet_teacher,
            replay_data, selection_days,
        )
    truth_thresholds = MappingProxyType({
        asset: selection.threshold
        for asset, selection in truth_selections.items()
    })
    no_feasible_assets = tuple(
        asset for asset in C.ASSETS
        if all(
            arm_fits[arm].selections[asset].feasible_thresholds == 0
            for arm in active_arms
        )
    )
    first_failed_boundary = (
        f"POLICY_NO_FEASIBLE_THRESHOLD:{no_feasible_assets[0]}"
        if no_feasible_assets else None
    )
    selected_policy_training = None
    if selected_winner:
        selected_policy_training = _selected_policy_training_receipt(
            arm_fits[ARM_FULL_PREFIX], fold,
            str(artifact.system.selected_decision_head_kind),
        )
    arrays = {
        "full_prefix_embedding": test_rows.embeddings,
        "static_summary": (np.empty((len(test_rows.candidate_ids), 0), np.float32)
                           if static_test_rows is None else static_test_rows.embeddings),
        **{
            f"{arm}:{key}": value
            for arm, arm_fit in arm_fits.items()
            for key, value in arm_fit.scores.items()
        },
    }
    receipt: dict[str, Any] = {
        "schema": FOLD_OOF_SCHEMA,
        "fold": fold.test_era,
        "training_receipt_sha256": artifact.trace.receipt_sha256,
        "normalizer_sha256": artifact.normalizer.receipt_sha256,
        "model_input_binding": model_input_binding.as_dict(),
        "winner_adoption": ({
            "bundle_sha256": artifact.system.winner_bundle_sha256,
            "e2_frozen_selection_sha256":
                artifact.system.e2_frozen_selection_sha256,
            "arm": artifact.system.arm,
            "objective_sha256": artifact.system.selected_objective_sha256,
            "decision_head_kind": artifact.system.selected_decision_head_kind,
            "target_row_manifest_sha256":
                artifact.system.selected_target_row_manifest_sha256,
            "target_control_sha256":
                artifact.system.selected_target_control_sha256,
            "target_control_receipt":
                artifact.system.selected_target_shuffle_receipt,
            "fit_day_manifest_sha256":
                artifact.system.selected_fit_day_manifest_sha256,
            "target_candidate_manifest_sha256":
                artifact.system.selected_target_candidate_manifest_sha256,
            "fit_context_sha256": artifact.system.selected_fit_context_sha256,
            "legacy_full_prefix": False,
        } if hasattr(artifact.system, "winner_bundle_sha256") else {
            "legacy_full_prefix": True,
        }),
        "fit_max_d8": max(fold.fit_days),
        "calibration_min_d8": min(fold.inner_days),
        "calibration_max_d8": max(fold.inner_days),
        "test_min_d8": min(fold.test_days),
        "test_max_d8": max(fold.test_days),
        "test_days_declared": list(fold.test_days),
        "test_candidate_sha256": C.object_sha256(list(test_rows.candidate_ids)),
        "arrays_sha256": _array_hash(arrays),
        "assets": list(C.ASSETS),
        "arms": list(active_arms),
        "static_summary_schema": (None if selected_winner else STATIC_SUMMARY_SCHEMA),
        "training_control": training_teacher.control_name,
        "policy_factory_dispatch": {
            arm: getattr(policy_factories[arm], "__name__", "")
            for arm in active_arms
        },
        "null_control": (
            dict(training_teacher.control_metadata)
            if allow_control else {
                "schema": "entry-v2-positive-control-v1",
                "control": "PROPHET",
            }
        ),
        "regime_declarations": [
            {
                "asset": row.asset,
                "trading_day": row.trading_day,
                "regime": row.regime,
                "availability_ts_ns": row.availability_ts_ns,
            }
            for row in test_regimes
        ],
        "prequential": {
            "blocks": [list(block) for block in fold.prequential_blocks],
            "calibration_days": list(arm_fits[ARM_FULL_PREFIX].calibration_days),
            "threshold_selection_days": list(
                arm_fits[ARM_FULL_PREFIX].selection_days
            ),
            "calibration_and_selection_predictions_disjoint": True,
            "test_predictions_never_used_for_calibration_or_selection": True,
            "selected_policy_chronology_law": (
                SELECTED_POLICY_CHRONOLOGY_LAW if selected_winner else None
            ),
            "selected_policy_fit_excludes_all_inner_labels": bool(selected_winner),
        },
        "arm_thresholds": {
            arm: {
                asset: asdict(selection)
                for asset, selection in arm_fit.selections.items()
            }
            for arm, arm_fit in arm_fits.items()
        },
        "truth_inner_thresholds_usd": {
            asset: asdict(selection)
            for asset, selection in truth_selections.items()
        },
        "threshold_candidate_law": threshold_candidate_law(),
        "truth_threshold_grid_usd": list(TRUTH_THRESHOLD_GRID_USD),
        "threshold_funnel_schema": THRESHOLD_FUNNEL_SCHEMA,
        "action_supervision_census": dict(action_supervision_census),
        "candidate_oracle_preflight": dict(oracle_preflight),
        "entry_gate_contract": entry_gate_contract(),
        "decision_contract": {
            "proxy_metrics": "diagnostic_only",
            "promotion_basis": [
                "exact_chronological_asset_day_dollars",
                "exact_candidate_set_oracle_capture",
                "chronological_cumulative_per_asset_max_drawdown",
            ],
            "first_failed_boundary": first_failed_boundary,
        },
    }
    if selected_winner:
        receipt.update({
            "selected_fit_weighting_sha256":
                artifact.system.selected_fit_weighting_sha256,
            "selected_phase_pair_manifest_sha256":
                artifact.system.selected_phase_pair_manifest_sha256,
            "selected_optimizer_step_unit": "complete_asset_day_gradient",
            "selected_validation_weighting": "UNWEIGHTED",
            "selected_horizon_schema_sha256":
                artifact.system.selected_horizon_schema_sha256,
            "selected_horizon_coordinates": list(SELECTED_HORIZON_COORDINATES),
            "selected_horizon_normalizer_sha256":
                artifact.system.selected_horizon_normalizer_sha256,
            "selected_ordinal_semantics":
                artifact.system.selected_ordinal_semantics,
            "selected_ordinal_semantics_sha256":
                SELECTED_ORDINAL_SEMANTICS_SHA256,
            "selected_policy_training": dict(selected_policy_training),
        })
    receipt["sha256"] = C.object_sha256(receipt)
    arm_scores = {
        arm: _entry_scores(
            test_rows,
            arm_fit.scores,
            arm_fit.thresholds,
            f"entry-v2:{arm}:{fold.test_era}:{receipt['sha256']}",
        )
        for arm, arm_fit in arm_fits.items()
    }
    truth_scores = prophet_teacher.truth_scores(
        test_rows.examples, entry_thresholds_usd=truth_thresholds
    )
    arm_arrivals = {
        arm: tuple(
            ScoredArrival(
                example,
                score,
                replay_data.outcomes[example.candidate_id],
            )
            for example, score in zip(test_rows.examples, scores)
        )
        for arm, scores in arm_scores.items()
    }
    truth_arrivals = tuple(
        ScoredArrival(
            example,
            score,
            replay_data.outcomes[example.candidate_id],
        )
        for example, score in zip(test_rows.examples, truth_scores)
    )
    arm_evaluations = {
        arm: replay(arrivals, expected_sessions=test_sessions)
        for arm, arrivals in arm_arrivals.items()
    }
    truth_evaluation = replay(truth_arrivals, expected_sessions=test_sessions)
    ceiling = candidate_ceiling(
        tuple(row for row in truth_arrivals
              if prophet_teacher[row.example.candidate_id].cert_close_usd
                  >= C.MIN_EXPECTANCY_USD),
        expected_sessions=test_sessions,
    )
    timings["total_seconds"] = perf_counter() - total_started
    result_type = SelectedWinnerFoldResult if selected_winner else FoldOOFResult
    return result_type(
        fold=fold.test_era,
        candidate_ids=test_rows.candidate_ids,
        assets=test_rows.assets,
        days=test_rows.days,
        embeddings=test_rows.embeddings,
        static_features=(np.empty((len(test_rows.candidate_ids), 0), np.float32)
                         if static_test_rows is None else static_test_rows.embeddings),
        arm_score_arrays=MappingProxyType({
            arm: arm_fit.scores for arm, arm_fit in arm_fits.items()
        }),
        arm_entry_scores=MappingProxyType(arm_scores),
        arm_arrivals=MappingProxyType(arm_arrivals),
        arm_thresholds=MappingProxyType({
            arm: arm_fit.thresholds for arm, arm_fit in arm_fits.items()
        }),
        arm_evaluations=MappingProxyType(arm_evaluations),
        arm_policies=MappingProxyType({
            arm: arm_fit.policies for arm, arm_fit in arm_fits.items()
        }),
        truth_scores=truth_scores,
        truth_arrivals=truth_arrivals,
        expected_sessions=test_sessions,
        regime_declarations=test_regimes,
        truth_thresholds_usd=truth_thresholds,
        truth_evaluation=truth_evaluation,
        candidate_ceiling=ceiling,
        training=artifact,
        receipt=MappingProxyType(receipt),
        diagnostic_timings=MappingProxyType(timings),
        control_name=training_teacher.control_name,
        first_failed_boundary=first_failed_boundary,
    )


def run_shuffled_control_oof(
    system: EntryLearningSystem,
    batches: Sequence[EntrySessionSpec],
    prophet_teacher: TeacherStore,
    fold: FoldSpec,
    replay_data: ReplayCalibrationData,
    shuffle_seed: int,
    model_input_binding: ModelInputBinding,
    config: TrainingConfig = TrainingConfig(),
    policy_factory: PolicyFactory | None = None,
) -> FoldOOFResult:
    """Run the same sealed protocol with one deterministic deranged teacher.

    The result remains paired with the exact PROPHET candidate set so replay
    can attribute whether the first failed boundary is learning, selection, or
    dollar realization.  A control result is tagged and can never be mistaken
    for a production fit.
    """

    if prophet_teacher.control_name != "PROPHET":
        raise C.EntryV2Refusal("shuffled control must derive from PROPHET")
    stage_by_day = {
        **{int(day): "FIT" for day in fold.fit_days},
        **{int(day): "INNER" for day in fold.inner_days},
        **{int(day): "TEST" for day in fold.test_days},
    }
    strata: dict[str, tuple[str, str, int, bool]] = {}
    for batch in batches:
        stage = stage_by_day.get(batch.trading_day)
        if stage is None:
            continue
        for example in batch.examples:
            strata[example.candidate_id] = (
                stage,
                example.asset,
                example.trading_day,
                prophet_teacher[example.candidate_id].action_loss_mask,
            )
    shuffled = prophet_teacher.shuffled(
        int(shuffle_seed), strata=MappingProxyType(strata)
    )
    return _run_fold_oof(
        system,
        batches,
        shuffled,
        prophet_teacher,
        fold,
        replay_data,
        model_input_binding,
        config,
        policy_factory,
        allow_control=True,
    )


def run_ladder_oof(
    folds: Sequence[FoldSpec],
    batches: Sequence[EntrySessionSpec],
    teacher: TeacherStore,
    replay_data: ReplayCalibrationData,
    system_factory: Callable[[], EntryLearningSystem],
    model_input_binding: ModelInputBinding,
    config: TrainingConfig = TrainingConfig(),
    policy_factory: PolicyFactory | None = None,
) -> tuple[FoldOOFResult, ...]:
    """Run independent expanding folds; a candidate can be test exactly once."""

    from .folds import DEVELOPMENT_FOLDS

    if tuple(fold.test_era for fold in folds) != DEVELOPMENT_FOLDS:
        raise C.EntryV2Refusal("OOF ladder must contain E3-E8 exactly once in order")
    results: list[FoldOOFResult] = []
    seen: set[str] = set()
    for fold in folds:
        _seed(config)
        result = run_fold_oof(
            system_factory(),
            batches,
            teacher,
            fold,
            replay_data,
            model_input_binding,
            config,
            policy_factory,
        )
        overlap = seen.intersection(result.candidate_ids)
        if overlap:
            raise C.EntryV2Refusal(f"OOF candidate reused: {min(overlap)}")
        seen.update(result.candidate_ids)
        results.append(result)
    return tuple(results)


__all__ = [
    "EntryLearningSystem",
    "EntrySessionBatch",
    "EntrySessionSpec",
    "CandidateOraclePreflightRefusal",
    "FoldOOFResult",
    "SelectedWinnerFoldResult",
    "SelectedFoldTrainingReceipt",
    "FoldTrainingIdentity",
    "fold_result_arms",
    "fold_training_identity",
    "build_selected_winner_fold_report",
    "HORIZONS_SECONDS",
    "LOSS_WEIGHTS",
    "ARM_NAMES",
    "ARM_POOLED_STATIC",
    "ARM_PER_ASSET_STATIC",
    "ARM_FULL_PREFIX",
    "LearningOutput",
    "LossBreakdown",
    "ModelInputBinding",
    "ReplayCalibrationData",
    "SelfSupervisedTargets",
    "TeacherTargets",
    "TrainFoldNormalizer",
    "TrainingArtifact",
    "TrainingConfig",
    "TrainingTrace",
    "candidate_oracle_preflight",
    "fit_encoder",
    "fixed_multitask_loss",
    "run_fold_oof",
    "run_ladder_oof",
    "run_shuffled_control_oof",
    "teacher_targets",
]
