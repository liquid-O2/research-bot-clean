"""Entry corpus product types and session-level validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

import numpy as np
import torch

from . import common as C
from .context_sources import CONTEXT_TYPE_ID
from .contracts import AssetDayRegime, CausalEntryExample, SessionRef
from .corpus_artifacts import _sha_hex
from .event_pack import EventPack
from .replay import ReplayOutcome
from .session_stream import SessionEventSource
from .teacher import TeacherStore

HORIZONS_SECONDS = (1, 10, 60, 300)


@dataclass(frozen=True, slots=True)
class RawPrefixFidelityEvidence:
    expected_events: int
    observed_events: int
    mismatched_events: int
    source_receipt_sha256: str
    pack_receipt_sha256: str

    def validate(self) -> None:
        expected, observed, mismatched = (
            int(self.expected_events),
            int(self.observed_events),
            int(self.mismatched_events),
        )
        if expected <= 0 or observed < 0 or mismatched < 0:
            raise C.EntryV2Refusal("invalid raw-prefix fidelity counts")
        if mismatched > min(expected, observed):
            raise C.EntryV2Refusal("raw-prefix mismatch count exceeds population")
        if mismatched < abs(expected - observed):
            raise C.EntryV2Refusal("raw-prefix mismatch count omits missing/extra events")
        _sha_hex(self.source_receipt_sha256, "raw source receipt")
        _sha_hex(self.pack_receipt_sha256, "event-pack receipt")

    @property
    def passed(self) -> bool:
        return self.expected_events == self.observed_events and self.mismatched_events == 0


@dataclass(frozen=True, slots=True)
class TeacherAlignmentEvidence:
    expected_candidates: int
    matched_candidates: int
    mismatched_candidates: int
    teacher_receipt_sha256: str
    join_receipt_sha256: str

    def validate(self) -> None:
        expected, matched, mismatched = (
            int(self.expected_candidates),
            int(self.matched_candidates),
            int(self.mismatched_candidates),
        )
        if expected <= 0 or matched < 0 or mismatched < 0:
            raise C.EntryV2Refusal("invalid teacher-alignment counts")
        if matched + mismatched != expected:
            raise C.EntryV2Refusal("teacher matched+mismatched does not equal expected candidates")
        _sha_hex(self.teacher_receipt_sha256, "teacher receipt")
        _sha_hex(self.join_receipt_sha256, "teacher join receipt")

    @property
    def passed(self) -> bool:
        return self.matched_candidates == self.expected_candidates and self.mismatched_candidates == 0


@dataclass(frozen=True)
class SelfSupervisedTargets:
    horizon_value: torch.Tensor
    horizon_valid: torch.Tensor
    phase_class: torch.Tensor
    phase_valid: torch.Tensor

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


@dataclass(frozen=True)
class EntrySessionSpec:
    source: SessionEventSource
    examples: tuple[CausalEntryExample, ...]
    candidate_cutoffs: torch.Tensor
    candidate_features: torch.Tensor
    context_values: torch.Tensor
    context_type_ids: torch.Tensor
    context_valid: torch.Tensor
    self_supervised: SelfSupervisedTargets
    static_features: torch.Tensor | None = None

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
        session_keys = {(item.asset, item.trading_day, item.session_id) for item in self.examples}
        if len(session_keys) != 1:
            raise C.EntryV2Refusal("one session specification must contain exactly one asset-session")
        C.guard_date(self.trading_day)
        if len(set(self.candidate_ids)) != n:
            raise C.EntryV2Refusal("duplicate candidate in session specification")
        if any(self.examples[i].decision_ts_ns > self.examples[i + 1].decision_ts_ns for i in range(n - 1)):
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
            raise C.EntryV2Refusal("candidate cutoff is misaligned with public raw-prefix event_count")
        if int(cutoffs[-1]) > int(self.source.max_cutoff):
            raise C.EntryV2Refusal("session specification cutoff exceeds all-candidate source pin")
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
            self.static_features.shape[0] != n
            or not self.static_features.is_floating_point()
            or not bool(torch.isfinite(self.static_features).all())
        ):
            raise C.EntryV2Refusal("static context summary is misaligned or non-finite")
        self.self_supervised.validate(n)
        if teacher is not None:
            joined = teacher.join_training(self.examples)
            if tuple(label.candidate_id for _, label in joined) != self.candidate_ids:
                raise C.EntryV2Refusal("teacher join changed candidate row order")


@dataclass(frozen=True)
class ReplayCalibrationData:
    outcomes: Mapping[str, ReplayOutcome]
    expected_sessions: tuple[SessionRef, ...]
    regime_declarations: tuple[AssetDayRegime, ...] = ()

    def validate(self, batches: Sequence[EntrySessionSpec]) -> None:
        if not self.expected_sessions or len(self.expected_sessions) != len(set(self.expected_sessions)):
            raise C.EntryV2Refusal("replay denominator is empty or duplicated")
        expected = set(self.expected_sessions)
        asset_days = {(session.asset, session.trading_day) for session in self.expected_sessions}
        regime_keys = {(row.asset, row.trading_day) for row in self.regime_declarations}
        if len(regime_keys) != len(self.regime_declarations):
            raise C.EntryV2Refusal("asset-day regime declarations are duplicated")
        if not regime_keys.issubset(asset_days):
            raise C.EntryV2Refusal("asset-day regime declaration lies outside the denominator")
        for session in self.expected_sessions:
            C.guard_date(session.trading_day)
            if not C.is_denominator_day(session.asset, session.trading_day):
                raise C.EntryV2Refusal("replay denominator contains a QRE2CAL1-excluded asset-day")
        for batch in batches:
            if batch.examples[0].session not in expected:
                raise C.EntryV2Refusal(f"candidate session absent from replay denominator: {batch.session_id}")
            for candidate_id in batch.candidate_ids:
                outcome = self.outcomes.get(candidate_id)
                if outcome is None or outcome.candidate_id != candidate_id:
                    raise C.EntryV2Refusal(f"replay outcome missing/misaligned: {candidate_id}")


def _static_context_summary(spec: EntrySessionSpec) -> np.ndarray:
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
        variance = torch.where(expanded, (x - mean[:, None, :]).square(), torch.zeros_like(x)).sum(dim=1) / denom
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
        stats[:, type_id, :] = torch.cat(
            (
                last,
                mean,
                variance.sqrt(),
                low,
                high,
                (count / mask.shape[1])[:, None],
            ),
            dim=1,
        )
    asset_one_hot = torch.zeros((rows, len(C.ASSETS)), dtype=torch.float64)
    asset_one_hot[:, C.ASSET_INDEX[spec.asset]] = 1.0
    candidate = spec.candidate_features.detach().cpu().to(torch.float64)
    result = torch.cat((candidate, asset_one_hot, stats.flatten(1)), dim=1)
    if not bool(torch.isfinite(result).all()):
        raise C.EntryV2Refusal("static candidate/context summary is non-finite")
    return result.numpy().astype(np.float32, copy=False)


@runtime_checkable
class DiagnosticSessionObserver(Protocol):
    """Consumes one verified session while its sole full mmap is open.

    Implementations must materialize only compact owned truth and must not
    retain ``pack`` or any view sharing its storage.  The learner prefix is
    published to ``source.array_cache`` before this callback runs.
    """

    def observe_session(
        self,
        *,
        source: SessionEventSource,
        pack: EventPack,
        candidates: tuple[Mapping[str, str], ...],
        teachers: tuple[Mapping[str, str], ...],
    ) -> None: ...

    def observe_cached_session(
        self,
        *,
        source: SessionEventSource,
        candidates: tuple[Mapping[str, str], ...],
        teachers: tuple[Mapping[str, str], ...],
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class _CorpusMergeProvenance:
    """Raw receipt inputs retained only until deterministic asset-lane merge."""

    candidate_ids_seen: tuple[str, ...]
    candidate_receipt_hashes: tuple[str, ...]
    teacher_receipt_hashes: tuple[str, ...]
    sidecar_hashes: tuple[str, ...]
    forecast_lineage: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EntryCorpus:
    sessions: tuple[EntrySessionSpec, ...]
    teacher: TeacherStore
    replay: ReplayCalibrationData
    raw_prefix_fidelity: RawPrefixFidelityEvidence
    teacher_alignment: TeacherAlignmentEvidence
    candidate_feature_schema: tuple[str, ...]
    receipt: Mapping[str, Any]
    _merge_provenance: _CorpusMergeProvenance


class TeacherAlignmentRefusal(C.EntryV2Refusal):
    """Production refusal that preserves the exact failed join evidence."""

    def __init__(self, message: str, evidence: TeacherAlignmentEvidence) -> None:
        super().__init__(message)
        self.evidence = evidence
