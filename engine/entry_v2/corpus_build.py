from __future__ import annotations

from threading import Event
from types import SimpleNamespace
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from . import common as C
from .context_sources import CausalContextRepository, ContextTensor
from .contracts import CausalEntryExample, SessionRef
from .replay import ReplayOutcome
from .session_stream import SessionArrayCache
from .teacher import TeacherPath
from .corpus_artifacts import AssetArtifactSet, _sha
from .corpus_forecast import ExplicitForecastRows, ForecastProvider, ForecastRow, _is_test_forecast_provider
from .corpus_session import (
    DiagnosticSessionObserver,
    EntryCorpus,
    RawPrefixFidelityEvidence,
    TeacherAlignmentEvidence,
    TeacherAlignmentRefusal,
)

from .corpus_build_assets import _materialize_assets
from .corpus_build_assemble import _assemble_replay, _assemble_sessions, _finish_corpus


def build_corpus(
    artifacts: Sequence[AssetArtifactSet],
    context_repositories: Mapping[str, CausalContextRepository],
    forecasts: ForecastProvider | Sequence[ForecastRow],
    *,
    require_assets: Iterable[str] = C.ASSETS,
    allow_test_forecast_adapter: bool = False,
    cancel_event: Event | None = None,
    array_cache: SessionArrayCache | None = None,
    diagnostic_observer: DiagnosticSessionObserver | None = None,
    maximum_d8: int | None = None,
    minimum_d8_exclusive: int | None = None,
    require_durable_window: bool = False,
) -> EntryCorpus:
    """Build the verified development corpus without opening any holdout row."""
    s = SimpleNamespace(
        artifacts=artifacts,
        context_repositories=context_repositories,
        forecasts=forecasts,
        require_assets=require_assets,
        allow_test_forecast_adapter=allow_test_forecast_adapter,
        cancel_event=cancel_event,
        array_cache=array_cache,
        diagnostic_observer=diagnostic_observer,
        maximum_d8=maximum_d8,
        minimum_d8_exclusive=minimum_d8_exclusive,
        require_durable_window=require_durable_window,
    )
    _initialize_build(s)
    _materialize_assets(s)
    _assemble_evidence(s)
    _assemble_sessions(s)
    _assemble_replay(s)
    return _finish_corpus(s)


def _initialize_build(s: SimpleNamespace):
    s.resolved_maximum_d8 = C.DEVELOPMENT_END_D8 if s.maximum_d8 is None else int(s.maximum_d8)
    C.guard_date(s.resolved_maximum_d8)
    if s.resolved_maximum_d8 > C.DEVELOPMENT_END_D8:
        raise C.EntryV2Refusal("corpus maximum exceeds the development window")
    s.resolved_minimum_d8 = None if s.minimum_d8_exclusive is None else int(s.minimum_d8_exclusive)
    if s.resolved_minimum_d8 is not None:
        C.guard_date(s.resolved_minimum_d8)
        if s.resolved_minimum_d8 >= s.resolved_maximum_d8:
            raise C.EntryV2Refusal("corpus chronological interval is empty/reversed")
    s.required = {str(asset).upper() for asset in s.require_assets}
    s.by_asset = {item.asset: item for item in s.artifacts}
    if len(s.by_asset) != len(s.artifacts) or set(s.by_asset) != s.required:
        raise C.EntryV2Refusal(f"artifact assets must be exactly {sorted(s.required)}, got {sorted(s.by_asset)}")
    s.provider: ForecastProvider
    if isinstance(s.forecasts, Sequence):
        if not s.allow_test_forecast_adapter:
            raise C.EntryV2Refusal("explicit forecast rows are a test-only adapter; use QRE2ForecastProvider")
        s.provider = ExplicitForecastRows(tuple(s.forecasts))
    elif isinstance(s.forecasts, ForecastProvider):
        if _is_test_forecast_provider(s.forecasts) and (not s.allow_test_forecast_adapter):
            raise C.EntryV2Refusal("explicit forecast rows are a test-only adapter; use QRE2ForecastProvider")
        s.provider = s.forecasts
    else:
        raise C.EntryV2Refusal("a typed forecast provider or explicit rows are required")
    _sha(getattr(s.provider, "receipt_sha256", ""), "forecast receipt")
    if set(getattr(s.provider, "assets", ())) != s.required:
        raise C.EntryV2Refusal(f"forecast provider assets must be exactly {sorted(s.required)}")
    s.examples_by_session: dict[SessionRef, list[CausalEntryExample]] = {}
    s.feature_by_id: dict[str, tuple[float, ...]] = {}
    s.target_by_id: dict[str, tuple[np.ndarray, np.ndarray, int, bool]] = {}
    s.context_tensor_by_id: dict[str, ContextTensor] = {}
    s.audit_context_recorded = False
    s.event_source_pins: dict[SessionRef, dict[str, Any]] = {}
    s.teacher_paths: list[TeacherPath] = []
    s.outcomes: dict[str, ReplayOutcome] = {}
    s.expected_sessions: list[SessionRef] = []
    s.expected_session_open_ns: dict[tuple[str, int], int] = {}
    s.candidate_ids_seen: set[str] = set()
    s.prefix_events = 0
    s.prefix_unique_cutoffs = 0
    s.prefix_bytes_hashed = 0
    s.clear_expected = 0
    s.clear_joined = 0
    s.clear_ready = 0
    s.clear_typed_no_sane_suffix = 0
    s.compliance_counts = {"CLEAR": 0, "PROHIBITED": 0, "COMPLIANCE_UNKNOWN": 0}
    s.sidecar_hashes: list[str] = []
    s.candidate_receipt_hashes: list[str] = []
    s.teacher_receipt_hashes: list[str] = []
    s.context_receipts: dict[str, str] = {}
    s.forecast_lineage: list[str] = []
    s.artifact_receipts: list[dict[str, Any]] = []
    s.observed_manifest_days: list[int] = []
    s.verified_session_warm_hits = 0
    s.verified_session_cold_publishes = 0
    s.model_array_bytes_materialized = 0
    s.model_array_bytes_reused = 0
    s.physical_full_pack_opens = 0
    s.model_array_physical_fills = 0
    s.full_authorities: list[dict[str, Any]] = []
    s.excluded_non_trading_calendar_rows = {asset: 0 for asset in s.required}
    s.excluded_outside_asset_coverage_rows = {asset: 0 for asset in s.required}
    s.excluded_full_closure_rows = {asset: 0 for asset in s.required}
    s.durable_store = None if s.array_cache is None else s.array_cache.durable_store
    if s.require_durable_window and s.durable_store is None:
        raise C.EntryV2Refusal("strict durable corpus reconstruction requires the durable store")


def _assemble_evidence(s: SimpleNamespace):
    s.join_payload = {
        "schema": "entry-v2-teacher-join-v2",
        "expected_clear": s.clear_expected,
        "joined": s.clear_joined,
        "ready": s.clear_ready,
        "typed_no_sane_suffix": s.clear_typed_no_sane_suffix,
        "candidate_ids": sorted((example.candidate_id for rows in s.examples_by_session.values() for example in rows)),
        "candidate_receipts": sorted(s.candidate_receipt_hashes),
        "teacher_receipts": sorted(s.teacher_receipt_hashes),
    }
    s.join_sha = C.object_sha256(s.join_payload)
    s.teacher_receipt_sha = C.object_sha256(sorted(s.teacher_receipt_hashes))
    s.teacher_evidence = TeacherAlignmentEvidence(
        expected_candidates=s.clear_expected,
        matched_candidates=s.clear_joined,
        mismatched_candidates=s.clear_expected - s.clear_joined,
        teacher_receipt_sha256=s.teacher_receipt_sha,
        join_receipt_sha256=s.join_sha,
    )
    s.teacher_evidence.validate()
    if not s.teacher_evidence.passed:
        raise TeacherAlignmentRefusal(
            f"CLEAR teacher identity join failed: {s.clear_joined}/{s.clear_expected}", s.teacher_evidence
        )
    if not s.teacher_paths:
        raise C.EntryV2Refusal("development corpus has no CLEAR READY candidates")
    s.raw_evidence = RawPrefixFidelityEvidence(
        expected_events=s.prefix_events,
        observed_events=s.prefix_events,
        mismatched_events=0,
        source_receipt_sha256=C.object_sha256(sorted(s.candidate_receipt_hashes)),
        pack_receipt_sha256=C.object_sha256(sorted(s.sidecar_hashes)),
    )
    s.raw_evidence.validate()
