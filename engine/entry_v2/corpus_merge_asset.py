from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType, SimpleNamespace
from typing import Any, Mapping

from . import common as C
from .contracts import AssetDayRegime, CausalEntryExample, SessionRef
from .corpus import (
    CANDIDATE_FEATURE_SCHEMA,
    CORPUS_WINDOW_LAW_SHA256,
    CORPUS_WINDOW_SCHEMA,
)
from .corpus_session import (
    EntryCorpus,
    EntrySessionSpec,
    RawPrefixFidelityEvidence,
    ReplayCalibrationData,
    TeacherAlignmentEvidence,
    TeacherAlignmentRefusal,
    _CorpusMergeProvenance,
)
from .event_pack import CATEGORY_SIZES
from .corpus_merge_common import (
    validate_receipt_constants,
    validated_receipt_body,
)
from .replay import ReplayOutcome
from .teacher import TeacherPath, build_teacher_store


def _resolve_asset_merge(s: SimpleNamespace) -> None:
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
    if not s.required or not s.required.issubset(C.ASSETS):
        raise C.EntryV2Refusal("invalid required asset set for corpus merge")


def _validate_asset_inputs(s: SimpleNamespace) -> None:
    s.by_asset: dict[str, EntryCorpus] = {}
    for s.corpus in s.corpora:
        s.corpus.raw_prefix_fidelity.validate()
        s.corpus.teacher_alignment.validate()
        s.receipt = validated_receipt_body(s.corpus, "asset corpus receipt mismatch")
        if s.receipt.get("event_category_sizes") != list(CATEGORY_SIZES):
            raise C.EntryV2Refusal("asset corpus receipt category sizes differ from event pack")
        s.assets = {session.asset for session in s.corpus.replay.expected_sessions}
        s.assets.update((spec.asset for spec in s.corpus.sessions))
        if len(s.assets) != 1:
            raise C.EntryV2Refusal("each merge input must contain exactly one asset")
        s.asset = next(iter(s.assets))
        if s.asset in s.by_asset:
            raise C.EntryV2Refusal(f"duplicate asset corpus: {s.asset}")
        if tuple(s.corpus.teacher.expected_sessions) != tuple(s.corpus.replay.expected_sessions):
            raise C.EntryV2Refusal("teacher/replay denominator differs in asset lane")
        s.by_asset[s.asset] = s.corpus
    if set(s.by_asset) != s.required:
        raise C.EntryV2Refusal(f"corpus merge assets must be exactly {sorted(s.required)}")
    s.parts = tuple((s.by_asset[asset] for asset in sorted(s.required)))


def _validate_asset_constants(s: SimpleNamespace) -> None:
    s.constant_keys = (
        "schema",
        "holdout_start_d8",
        "final_exam_permit",
        "candidate_feature_schema",
        "candidate_feature_schema_sha256",
        "forecast_schema",
        "forecast_feature_fields",
        "forecast_receipt_sha256",
        "test_forecast_adapter",
        "prefix_law",
        "prefix_domain_hex",
        "self_supervised_horizon_law",
        "self_supervised_phase_law",
        "horizons_seconds",
        "event_continuous_fields",
        "event_categorical_fields",
        "event_category_sizes",
        "model_arrays_conversion_law_sha256",
        "clock_law_receipt_sha256",
    )
    s.reference = s.parts[0].receipt
    s.reference_window = s.reference.get("corpus_window", {})
    if (
        s.reference_window.get("schema") != CORPUS_WINDOW_SCHEMA
        or s.reference_window.get("law_sha256") != CORPUS_WINDOW_LAW_SHA256
        or s.reference_window.get("maximum_d8") != s.resolved_maximum_d8
        or (s.reference_window.get("minimum_d8_exclusive") != s.resolved_minimum_d8)
    ):
        raise C.EntryV2Refusal("asset corpus window identity is wrong")
    for s.part in s.parts[1:]:
        _validate_asset_constant_part(s)


def _validate_asset_constant_part(s: SimpleNamespace) -> None:
    validate_receipt_constants(
        s.part.receipt,
        s.reference,
        s.constant_keys,
        "asset corpus constant differs during merge",
    )
    s.window = s.part.receipt.get("corpus_window", {})
    identity = (
        s.window.get("schema"),
        s.window.get("law_sha256"),
        s.window.get("maximum_d8"),
        s.window.get("minimum_d8_exclusive"),
    )
    expected = (
        CORPUS_WINDOW_SCHEMA,
        CORPUS_WINDOW_LAW_SHA256,
        s.resolved_maximum_d8,
        s.resolved_minimum_d8,
    )
    if identity != expected:
        raise C.EntryV2Refusal("asset corpora use different corpus windows")
    calendar = s.part.receipt.get("denominator_calendar", {})
    reference_calendar = s.reference.get("denominator_calendar", {})
    if calendar.get("authority_sha256") != reference_calendar.get("authority_sha256"):
        raise C.EntryV2Refusal("asset corpora use different calendar authority")
    regime = s.part.receipt.get("asset_day_regimes", {})
    reference_regime = s.reference.get("asset_day_regimes", {})
    if regime.get("law") != reference_regime.get("law"):
        raise C.EntryV2Refusal("asset corpora use different regime law")


def _initialize_asset_payload(s: SimpleNamespace) -> None:
    s.candidate_ids_seen: set[str] = set()
    s.candidate_receipt_hashes: list[str] = []
    s.teacher_receipt_hashes: list[str] = []
    s.sidecar_hashes: list[str] = []
    s.forecast_lineage: list[str] = []
    s.expected_sessions: list[SessionRef] = []
    s.regime_declarations: list[AssetDayRegime] = []
    s.outcomes: dict[str, ReplayOutcome] = {}
    s.sessions: list[EntrySessionSpec] = []
    s.teacher_paths: list[TeacherPath] = []
    s.audit_context_retained = False


def _collect_asset_payload(s: SimpleNamespace) -> None:
    for s.part in s.parts:
        _collect_asset_part(s)


def _collect_asset_part(s: SimpleNamespace) -> None:
    s.provenance = s.part._merge_provenance
    s.overlap = s.candidate_ids_seen.intersection(s.provenance.candidate_ids_seen)
    if s.overlap:
        raise C.EntryV2Refusal(f"cross-asset candidate id collision: {min(s.overlap)}")
    s.candidate_ids_seen.update(s.provenance.candidate_ids_seen)
    s.candidate_receipt_hashes.extend(s.provenance.candidate_receipt_hashes)
    s.teacher_receipt_hashes.extend(s.provenance.teacher_receipt_hashes)
    s.sidecar_hashes.extend(s.provenance.sidecar_hashes)
    s.forecast_lineage.extend(s.provenance.forecast_lineage)
    s.expected_sessions.extend(s.part.replay.expected_sessions)
    s.regime_declarations.extend(s.part.replay.regime_declarations)
    for s.candidate_id, s.outcome in s.part.replay.outcomes.items():
        if s.candidate_id in s.outcomes:
            raise C.EntryV2Refusal(f"cross-asset replay outcome collision: {s.candidate_id}")
        s.outcomes[s.candidate_id] = s.outcome
    for s.spec in s.part.sessions:
        _collect_asset_spec(s)


def _collect_asset_spec(s: SimpleNamespace) -> None:
    s.merged_examples: list[CausalEntryExample] = []
    s.changed = False
    for s.example in s.spec.examples:
        _collect_asset_example(s)
    s.sessions.append(replace(s.spec, examples=tuple(s.merged_examples)) if s.changed else s.spec)


def _collect_asset_example(s: SimpleNamespace) -> None:
    s.candidate_id = s.example.candidate_id
    s.label = s.part.teacher[s.candidate_id]
    s.outcome = s.part.replay.outcomes.get(s.candidate_id)
    if s.outcome is None or s.outcome.candidate_id != s.candidate_id:
        raise C.EntryV2Refusal(f"asset corpus outcome is missing: {s.candidate_id}")
    s.teacher_paths.append(
        TeacherPath(
            candidate_id=s.candidate_id,
            asset=s.example.asset,
            trading_day=s.example.trading_day,
            decision_ts_ns=s.example.decision_ts_ns,
            exit_ts_ns=s.outcome.close_ts_ns,
            cert_close_usd=s.label.cert_close_usd,
            mfe_usd=s.label.mfe_usd,
            mae_usd=s.label.mae_usd,
            wall_hit=s.label.wall_hit,
            time_to_peak_sec=s.label.time_to_peak_sec,
        )
    )
    if s.example.context is not None:
        if s.audit_context_retained:
            s.example = replace(s.example, context=None)
            s.changed = True
        else:
            s.audit_context_retained = True
    s.merged_examples.append(s.example)


def _order_asset_payload(s: SimpleNamespace) -> None:
    if len(s.expected_sessions) != len(set(s.expected_sessions)):
        raise C.EntryV2Refusal("asset corpus denominators overlap")
    s.regime_keys = {(row.asset, row.trading_day) for row in s.regime_declarations}
    if len(s.regime_keys) != len(s.regime_declarations):
        raise C.EntryV2Refusal("asset corpus regime declarations overlap")
    s.sessions.sort(key=lambda item: (item.trading_day, item.asset, item.session_id))
    s.expected_sessions.sort()
    s.regime_declarations.sort()


def _build_asset_teacher_replay(s: SimpleNamespace) -> None:
    s.teacher_store = build_teacher_store(s.teacher_paths, expected_sessions=s.expected_sessions)
    for s.part in s.parts:
        for s.spec in s.part.sessions:
            for s.candidate_id in s.spec.candidate_ids:
                if s.teacher_store[s.candidate_id] != s.part.teacher[s.candidate_id]:
                    raise C.EntryV2Refusal(f"global teacher differs from asset lane: {s.candidate_id}")
    for s.spec in s.sessions:
        s.spec.validate(s.teacher_store)
    s.replay_data = ReplayCalibrationData(
        MappingProxyType(dict(sorted(s.outcomes.items()))), tuple(s.expected_sessions), tuple(s.regime_declarations)
    )
    s.replay_data.validate(s.sessions)


def _build_asset_teacher_evidence(s: SimpleNamespace) -> None:
    s.clear_expected = sum((part.teacher_alignment.expected_candidates for part in s.parts))
    s.clear_joined = sum((part.teacher_alignment.matched_candidates for part in s.parts))
    s.clear_typed_no_sane_suffix = sum((int(part.receipt.get("clear_typed_no_sane_suffix", -1)) for part in s.parts))
    if s.clear_typed_no_sane_suffix < 0:
        raise C.EntryV2Refusal("asset corpus typed-teacher count is invalid")
    s.join_payload = {
        "schema": "entry-v2-teacher-join-v2",
        "expected_clear": s.clear_expected,
        "joined": s.clear_joined,
        "ready": len(s.teacher_paths),
        "typed_no_sane_suffix": s.clear_typed_no_sane_suffix,
        "candidate_ids": sorted((example.candidate_id for spec in s.sessions for example in spec.examples)),
        "candidate_receipts": sorted(s.candidate_receipt_hashes),
        "teacher_receipts": sorted(s.teacher_receipt_hashes),
    }
    s.teacher_evidence = TeacherAlignmentEvidence(
        expected_candidates=s.clear_expected,
        matched_candidates=s.clear_joined,
        mismatched_candidates=s.clear_expected - s.clear_joined,
        teacher_receipt_sha256=C.object_sha256(sorted(s.teacher_receipt_hashes)),
        join_receipt_sha256=C.object_sha256(s.join_payload),
    )
    s.teacher_evidence.validate()
    if not s.teacher_evidence.passed:
        raise TeacherAlignmentRefusal("merged CLEAR teacher identity join failed", s.teacher_evidence)


def _build_asset_raw_evidence(s: SimpleNamespace) -> None:
    s.prefix_events = sum((part.raw_prefix_fidelity.expected_events for part in s.parts))
    s.raw_evidence = RawPrefixFidelityEvidence(
        expected_events=s.prefix_events,
        observed_events=sum((part.raw_prefix_fidelity.observed_events for part in s.parts)),
        mismatched_events=sum((part.raw_prefix_fidelity.mismatched_events for part in s.parts)),
        source_receipt_sha256=C.object_sha256(sorted(s.candidate_receipt_hashes)),
        pack_receipt_sha256=C.object_sha256(sorted(s.sidecar_hashes)),
    )
    s.raw_evidence.validate()


def _collect_asset_receipt_inputs(s: SimpleNamespace) -> None:
    s.ordered_sources = [spec.source for spec in sorted(s.sessions, key=lambda item: (item.trading_day, item.asset, item.session_id))]
    s.stream_receipt_aggregate = C.object_sha256([source.receipt.receipt_sha256 for source in s.ordered_sources])
    s.context_receipts: dict[str, str] = {}
    s.artifact_receipts: list[Mapping[str, Any]] = []
    s.session_receipts: list[Mapping[str, Any]] = []
    s.compliance_counts = {"CLEAR": 0, "PROHIBITED": 0, "COMPLIANCE_UNKNOWN": 0}
    s.excluded_non_trading = {asset: 0 for asset in s.required}
    s.excluded_outside_coverage = {asset: 0 for asset in s.required}
    s.excluded_full_closure = {asset: 0 for asset in s.required}
    s.prefix_unique_cutoffs = 0
    s.prefix_bytes_hashed = 0
    for s.part in s.parts:
        s.context_receipts.update(s.part.receipt["context_receipts"])
        s.artifact_receipts.extend(s.part.receipt["artifacts"])
        s.session_receipts.extend(s.part.receipt["session_specs"])
        for s.name in s.compliance_counts:
            s.compliance_counts[s.name] += int(s.part.receipt["compliance_counts"][s.name])
        s.calendar = s.part.receipt["denominator_calendar"]
        for s.asset, s.value in s.calendar["excluded_non_trading_calendar_rows"].items():
            s.excluded_non_trading[s.asset] += int(s.value)
        for s.asset, s.value in s.calendar["excluded_outside_asset_coverage_rows"].items():
            s.excluded_outside_coverage[s.asset] += int(s.value)
        for s.asset, s.value in s.calendar["excluded_full_closure_rows"].items():
            s.excluded_full_closure[s.asset] += int(s.value)
        s.prefix_unique_cutoffs += int(s.part.receipt["prefix_verification"]["unique_cutoffs"])
        s.prefix_bytes_hashed += int(s.part.receipt["prefix_verification"]["bytes_hashed"])


def _build_asset_lineage(s: SimpleNamespace) -> None:
    s.artifact_receipts.sort(key=lambda row: str(row["asset"]))
    s.session_receipts.sort(key=lambda row: (int(row["d8"]), str(row["asset"]), str(row["session_id"])))
    s.forecast_receipt_sha256 = str(s.reference["forecast_receipt_sha256"])
    s.clock_law_receipt_sha256 = str(s.reference["clock_law_receipt_sha256"])
    s.corpus_source_lineage_sha256 = C.object_sha256(
        {
            "event_sources": [[source.asset, source.d8, source.source_sha256, source.sidecar_sha256] for source in s.ordered_sources],
            "candidate_receipts": sorted(s.candidate_receipt_hashes),
            "teacher_receipts": sorted(s.teacher_receipt_hashes),
            "forecast_receipt": s.forecast_receipt_sha256,
            "context_receipts": dict(sorted(s.context_receipts.items())),
            "qre2_calendar_authority": C.QRE2_CALENDAR_SHA256,
            "corpus_window_law_sha256": CORPUS_WINDOW_LAW_SHA256,
            "maximum_d8": s.resolved_maximum_d8,
            "minimum_d8_exclusive": s.resolved_minimum_d8,
            "full_manifest_authorities": sorted(
                (authority for part in s.parts for authority in part.receipt["corpus_window"]["full_manifest_authorities"]),
                key=lambda row: str(row["asset"]),
            ),
        }
    )


def _start_asset_receipt(s: SimpleNamespace) -> None:
    s.receipt = dict(s.reference)
    s.receipt.pop("receipt_sha256", None)


def _update_asset_receipt_0(s: SimpleNamespace) -> None:
    s.receipt.update(
        {
            "artifacts": s.artifact_receipts,
            "sessions": len(s.expected_sessions),
            "verified_session_warm_hits": sum((int(part.receipt["verified_session_warm_hits"]) for part in s.parts)),
            "verified_session_cold_publishes": sum((int(part.receipt["verified_session_cold_publishes"]) for part in s.parts)),
            "model_array_bytes_materialized": sum((int(part.receipt["model_array_bytes_materialized"]) for part in s.parts)),
            "model_array_bytes_reused": sum((int(part.receipt["model_array_bytes_reused"]) for part in s.parts)),
            "physical_full_pack_opens": sum((int(part.receipt["physical_full_pack_opens"]) for part in s.parts)),
            "model_array_physical_fills": sum((int(part.receipt["model_array_physical_fills"]) for part in s.parts)),
        }
    )


def _update_asset_receipt_1(s: SimpleNamespace) -> None:
    s.receipt.update({"warm_corpus_ready": all((part.receipt["warm_corpus_ready"] is True for part in s.parts))})


def _update_asset_receipt_2(s: SimpleNamespace) -> None:
    s.receipt.update(
        {
            "corpus_window": {
                "schema": CORPUS_WINDOW_SCHEMA,
                "law_sha256": CORPUS_WINDOW_LAW_SHA256,
                "maximum_d8": s.resolved_maximum_d8,
                "minimum_d8_exclusive": s.resolved_minimum_d8,
                "start_d8_inclusive": min((int(part.receipt["corpus_window"]["start_d8_inclusive"]) for part in s.parts)),
                "observed_start_d8": min((int(part.receipt["corpus_window"]["observed_start_d8"]) for part in s.parts)),
                "observed_end_d8": max((int(part.receipt["corpus_window"]["observed_end_d8"]) for part in s.parts)),
                "full_manifest_authorities": sorted(
                    (authority for part in s.parts for authority in part.receipt["corpus_window"]["full_manifest_authorities"]),
                    key=lambda row: str(row["asset"]),
                ),
                "full_manifest_authority_sha256": C.object_sha256(
                    sorted(
                        (authority for part in s.parts for authority in part.receipt["corpus_window"]["full_manifest_authorities"]),
                        key=lambda row: str(row["asset"]),
                    )
                ),
            }
        }
    )


def _update_asset_receipt_3(s: SimpleNamespace) -> None:
    s.receipt.update(
        {
            "denominator_calendar": {
                "law": s.reference["denominator_calendar"]["law"],
                "authority_sha256": C.QRE2_CALENDAR_SHA256,
                "asset_coverage_start_d8": {asset: C.qre2_asset_coverage_start_d8(asset) for asset in sorted(s.required)},
                "excluded_non_trading_calendar_rows": dict(sorted(s.excluded_non_trading.items())),
                "excluded_outside_asset_coverage_rows": dict(sorted(s.excluded_outside_coverage.items())),
                "excluded_full_closure_rows": dict(sorted(s.excluded_full_closure.items())),
            }
        }
    )


def _update_asset_receipt_4(s: SimpleNamespace) -> None:
    s.receipt.update(
        {
            "asset_day_regimes": {
                "law": s.reference["asset_day_regimes"]["law"],
                "resolved": len(s.regime_declarations),
                "expected": len({(session.asset, session.trading_day) for session in s.expected_sessions}),
                "declarations": [
                    {
                        "asset": row.asset,
                        "trading_day": row.trading_day,
                        "regime": row.regime,
                        "availability_ts_ns": row.availability_ts_ns,
                    }
                    for row in s.regime_declarations
                ],
            },
            "candidate_batches": len(s.sessions),
            "clear_ready_candidates": len(s.teacher_paths),
            "clear_typed_no_sane_suffix": s.clear_typed_no_sane_suffix,
            "compliance_counts": s.compliance_counts,
            "used_forecast_lineage_sha256": C.object_sha256(sorted(s.forecast_lineage)),
            "context_receipts": dict(sorted(s.context_receipts.items())),
        }
    )


def _update_asset_receipt_5(s: SimpleNamespace) -> None:
    s.receipt.update(
        {
            "prefix_verification": {
                "law": s.reference["prefix_verification"]["law"],
                "unique_cutoffs": s.prefix_unique_cutoffs,
                "bytes_hashed": s.prefix_bytes_hashed,
            },
            "session_stream_receipt_aggregate_sha256": s.stream_receipt_aggregate,
            "corpus_source_lineage_sha256": s.corpus_source_lineage_sha256,
            "raw_prefix_fidelity": {
                "expected_events": s.raw_evidence.expected_events,
                "observed_events": s.raw_evidence.observed_events,
                "mismatched_events": s.raw_evidence.mismatched_events,
                "source_receipt_sha256": s.raw_evidence.source_receipt_sha256,
                "pack_receipt_sha256": s.raw_evidence.pack_receipt_sha256,
            },
        }
    )


def _update_asset_receipt_6(s: SimpleNamespace) -> None:
    s.receipt.update(
        {
            "teacher_alignment": {
                "expected_candidates": s.teacher_evidence.expected_candidates,
                "matched_candidates": s.teacher_evidence.matched_candidates,
                "mismatched_candidates": s.teacher_evidence.mismatched_candidates,
                "teacher_receipt_sha256": s.teacher_evidence.teacher_receipt_sha256,
                "join_receipt_sha256": s.teacher_evidence.join_receipt_sha256,
            },
            "teacher_store_sha256": s.teacher_store.store_hash,
            "teacher_action_contract": {
                **s.reference["teacher_action_contract"],
                "expected_asset_days": len({(session.asset, session.trading_day) for session in s.expected_sessions}),
            },
            "session_specs": s.session_receipts,
        }
    )


def _finish_asset_merge(s: SimpleNamespace) -> EntryCorpus:
    s.receipt["receipt_sha256"] = C.object_sha256(s.receipt)
    return EntryCorpus(
        tuple(s.sessions),
        s.teacher_store,
        s.replay_data,
        s.raw_evidence,
        s.teacher_evidence,
        CANDIDATE_FEATURE_SCHEMA,
        MappingProxyType(s.receipt),
        _CorpusMergeProvenance(
            tuple(sorted(s.candidate_ids_seen)),
            tuple(s.candidate_receipt_hashes),
            tuple(s.teacher_receipt_hashes),
            tuple(s.sidecar_hashes),
            tuple(s.forecast_lineage),
        ),
    )
