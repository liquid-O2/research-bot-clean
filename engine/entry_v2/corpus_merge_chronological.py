from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType, SimpleNamespace
from typing import Any

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
from .corpus_merge_common import (
    validate_receipt_constants,
    validated_receipt_body,
)
from .replay import ReplayOutcome
from .teacher import TeacherPath, build_teacher_store


def _initialize_chronological_merge(s: SimpleNamespace) -> None:
    s.parts = tuple(s.corpora)
    if len(s.parts) < 2:
        raise C.EntryV2Refusal("chronological corpus merge requires multiple windows")
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
    s.reference_authorities = s.reference.get("corpus_window", {}).get("full_manifest_authorities")
    s.reference_authority_hash = s.reference.get("corpus_window", {}).get("full_manifest_authority_sha256")
    s.prior_maximum: int | None = None
    s.chain_parts: list[dict[str, Any]] = []


def _validate_chronological_parts(s: SimpleNamespace) -> None:
    for s.index, s.part in enumerate(s.parts):
        _validate_chronological_part(s)


def _validate_chronological_part(s: SimpleNamespace) -> None:
    s.part.raw_prefix_fidelity.validate()
    s.part.teacher_alignment.validate()
    s.body = validated_receipt_body(s.part, "chronological corpus receipt binding drift")
    s.claimed = str(s.part.receipt["receipt_sha256"])
    validate_receipt_constants(s.part.receipt, s.reference, s.constant_keys, "chronological corpus constant differs")
    s.window = s.part.receipt.get("corpus_window", {})
    s.minimum = s.window.get("minimum_d8_exclusive")
    s.maximum = int(s.window.get("maximum_d8", 0))
    if (
        s.window.get("schema") != CORPUS_WINDOW_SCHEMA
        or s.window.get("law_sha256") != CORPUS_WINDOW_LAW_SHA256
        or s.window.get("full_manifest_authorities") != s.reference_authorities
        or (s.window.get("full_manifest_authority_sha256") != s.reference_authority_hash)
    ):
        raise C.EntryV2Refusal("chronological corpus authority/window law differs")
    if s.index and s.minimum != s.prior_maximum:
        raise C.EntryV2Refusal("chronological corpus windows overlap or gap")
    if s.index == 0 and s.minimum is not None:
        C.guard_date(int(s.minimum))
    if s.maximum <= (int(s.minimum) if s.minimum is not None else 0):
        raise C.EntryV2Refusal("chronological corpus window is empty/reversed")
    if {session.asset for session in s.part.replay.expected_sessions} != set(C.ASSETS):
        raise C.EntryV2Refusal("chronological corpus window is not all-asset")
    s.prior_maximum = s.maximum
    s.chain_parts.append(
        {
            "receipt_sha256": s.claimed,
            "minimum_d8_exclusive": s.minimum,
            "start_d8_inclusive": int(s.window["start_d8_inclusive"]),
            "maximum_d8": s.maximum,
        }
    )


def _initialize_chronological_payload(s: SimpleNamespace) -> None:
    s.candidate_ids: set[str] = set()
    s.candidate_receipts: list[str] = []
    s.teacher_receipts: list[str] = []
    s.sidecar_hashes: list[str] = []
    s.forecast_lineage: list[str] = []
    s.expected_sessions: list[SessionRef] = []
    s.regimes: list[AssetDayRegime] = []
    s.outcomes: dict[str, ReplayOutcome] = {}
    s.sessions: list[EntrySessionSpec] = []
    s.teacher_paths: list[TeacherPath] = []
    s.audit_context_retained = False


def _collect_chronological_payload(s: SimpleNamespace) -> None:
    for s.part in s.parts:
        _collect_chronological_part(s)


def _collect_chronological_part(s: SimpleNamespace) -> None:
    s.provenance = s.part._merge_provenance
    s.overlap = s.candidate_ids.intersection(s.provenance.candidate_ids_seen)
    if s.overlap:
        raise C.EntryV2Refusal(f"chronological candidate overlap: {min(s.overlap)}")
    s.candidate_ids.update(s.provenance.candidate_ids_seen)
    s.candidate_receipts.extend(s.provenance.candidate_receipt_hashes)
    s.teacher_receipts.extend(s.provenance.teacher_receipt_hashes)
    s.sidecar_hashes.extend(s.provenance.sidecar_hashes)
    s.forecast_lineage.extend(s.provenance.forecast_lineage)
    s.expected_sessions.extend(s.part.replay.expected_sessions)
    s.regimes.extend(s.part.replay.regime_declarations)
    for s.candidate_id, s.outcome in s.part.replay.outcomes.items():
        if s.candidate_id in s.outcomes:
            raise C.EntryV2Refusal(f"chronological replay overlap: {s.candidate_id}")
        s.outcomes[s.candidate_id] = s.outcome
    for s.spec in s.part.sessions:
        _collect_chronological_spec(s)


def _collect_chronological_spec(s: SimpleNamespace) -> None:
    s.examples: list[CausalEntryExample] = []
    s.changed = False
    for s.example in s.spec.examples:
        _collect_chronological_example(s)
    s.sessions.append(replace(s.spec, examples=tuple(s.examples)) if s.changed else s.spec)


def _collect_chronological_example(s: SimpleNamespace) -> None:
    s.label = s.part.teacher[s.example.candidate_id]
    s.outcome = s.part.replay.outcomes[s.example.candidate_id]
    s.teacher_paths.append(
        TeacherPath(
            s.example.candidate_id,
            s.example.asset,
            s.example.trading_day,
            s.example.decision_ts_ns,
            s.outcome.close_ts_ns,
            s.label.cert_close_usd,
            s.label.mfe_usd,
            s.label.mae_usd,
            s.label.wall_hit,
            s.label.time_to_peak_sec,
        )
    )
    if s.example.context is not None:
        if s.audit_context_retained:
            s.example = replace(s.example, context=None)
            s.changed = True
        else:
            s.audit_context_retained = True
    s.examples.append(s.example)


def _order_chronological_payload(s: SimpleNamespace) -> None:
    if len(s.expected_sessions) != len(set(s.expected_sessions)):
        raise C.EntryV2Refusal("chronological corpus denominator overlap")
    if len(s.regimes) != len({(row.asset, row.trading_day) for row in s.regimes}):
        raise C.EntryV2Refusal("chronological corpus regime overlap")
    s.sessions.sort(key=lambda item: (item.trading_day, item.asset, item.session_id))
    s.expected_sessions.sort()
    s.regimes.sort()


def _build_chronological_teacher_replay(s: SimpleNamespace) -> None:
    s.teacher_store = build_teacher_store(s.teacher_paths, expected_sessions=s.expected_sessions)
    for s.part in s.parts:
        for s.spec in s.part.sessions:
            for s.candidate_id in s.spec.candidate_ids:
                if s.teacher_store[s.candidate_id] != s.part.teacher[s.candidate_id]:
                    raise C.EntryV2Refusal("chronological teacher semantics changed at window merge")
    for s.spec in s.sessions:
        s.spec.validate(s.teacher_store)
    s.replay = ReplayCalibrationData(
        MappingProxyType(dict(sorted(s.outcomes.items()))), tuple(s.expected_sessions), tuple(s.regimes)
    )
    s.replay.validate(s.sessions)


def _build_chronological_teacher_evidence(s: SimpleNamespace) -> None:
    s.clear_expected = sum((row.teacher_alignment.expected_candidates for row in s.parts))
    s.clear_joined = sum((row.teacher_alignment.matched_candidates for row in s.parts))
    s.typed_no_suffix = sum((int(row.receipt["clear_typed_no_sane_suffix"]) for row in s.parts))
    s.join_payload = {
        "schema": "entry-v2-teacher-join-v2",
        "expected_clear": s.clear_expected,
        "joined": s.clear_joined,
        "ready": len(s.teacher_paths),
        "typed_no_sane_suffix": s.typed_no_suffix,
        "candidate_ids": sorted((example.candidate_id for spec in s.sessions for example in spec.examples)),
        "candidate_receipts": sorted(s.candidate_receipts),
        "teacher_receipts": sorted(s.teacher_receipts),
    }
    s.teacher_evidence = TeacherAlignmentEvidence(
        s.clear_expected,
        s.clear_joined,
        s.clear_expected - s.clear_joined,
        C.object_sha256(sorted(s.teacher_receipts)),
        C.object_sha256(s.join_payload),
    )
    s.teacher_evidence.validate()
    if not s.teacher_evidence.passed:
        raise TeacherAlignmentRefusal("chronological teacher identity join failed", s.teacher_evidence)
    s.raw_evidence = RawPrefixFidelityEvidence(
        sum((row.raw_prefix_fidelity.expected_events for row in s.parts)),
        sum((row.raw_prefix_fidelity.observed_events for row in s.parts)),
        sum((row.raw_prefix_fidelity.mismatched_events for row in s.parts)),
        C.object_sha256(sorted(s.candidate_receipts)),
        C.object_sha256(sorted(s.sidecar_hashes)),
    )
    s.raw_evidence.validate()


def _collect_chronological_receipt_inputs(s: SimpleNamespace) -> None:
    s.ordered_sources = [spec.source for spec in s.sessions]
    s.stream_hash = C.object_sha256([source.receipt.receipt_sha256 for source in s.ordered_sources])
    s.context_receipts = dict(s.reference["context_receipts"])
    for s.part in s.parts[1:]:
        if s.part.receipt["context_receipts"] != s.context_receipts:
            raise C.EntryV2Refusal("chronological context authority differs")
    s.artifacts_by_asset: dict[str, dict[str, Any]] = {}
    for s.part in s.parts:
        for s.artifact in s.part.receipt["artifacts"]:
            s.asset = str(s.artifact["asset"])
            s.row = dict(s.artifact)
            s.prior = s.artifacts_by_asset.get(s.asset)
            if s.prior is None:
                s.artifacts_by_asset[s.asset] = s.row
            else:
                for s.key, s.value in s.row.items():
                    if s.key == "sessions":
                        continue
                    if s.prior.get(s.key) != s.value:
                        raise C.EntryV2Refusal("chronological artifact authority differs")
                s.prior["sessions"] = int(s.prior["sessions"]) + int(s.row["sessions"])
    s.session_receipts = sorted(
        (receipt for part in s.parts for receipt in part.receipt["session_specs"]),
        key=lambda row: (int(row["d8"]), str(row["asset"]), str(row["session_id"])),
    )
    s.receipt_by_key = {(str(row["asset"]), int(row["d8"]), str(row["session_id"])): row for row in s.session_receipts}
    if len(s.receipt_by_key) != len(s.session_receipts):
        raise C.EntryV2Refusal("chronological session receipt roster duplicates a session")


def _build_chronological_receipt_aggregates(s: SimpleNamespace) -> None:
    s.compliance = {
        name: sum((int(part.receipt["compliance_counts"][name]) for part in s.parts))
        for name in ("CLEAR", "PROHIBITED", "COMPLIANCE_UNKNOWN")
    }
    s.excluded = {}
    for s.name in (
        "excluded_non_trading_calendar_rows",
        "excluded_outside_asset_coverage_rows",
        "excluded_full_closure_rows",
    ):
        s.excluded[s.name] = {
            asset: sum((int(part.receipt["denominator_calendar"][s.name][asset]) for part in s.parts))
            for asset in C.ASSETS
        }
    s.first_window = s.parts[0].receipt["corpus_window"]
    s.maximum = int(s.parts[-1].receipt["corpus_window"]["maximum_d8"])
    s.minimum = s.first_window["minimum_d8_exclusive"]
    s.chain = {"schema": "entry-v2-corpus-window-chain-v1", "parts": s.chain_parts}
    s.chain["chain_sha256"] = C.object_sha256(s.chain)
    s.source_lineage = C.object_sha256(
        {
            "event_sources": [
                [source.asset, source.d8, source.source_sha256, source.sidecar_sha256] for source in s.ordered_sources
            ],
            "candidate_receipts": sorted(s.candidate_receipts),
            "teacher_receipts": sorted(s.teacher_receipts),
            "forecast_receipt": s.reference["forecast_receipt_sha256"],
            "context_receipts": dict(sorted(s.context_receipts.items())),
            "qre2_calendar_authority": C.QRE2_CALENDAR_SHA256,
            "corpus_window_law_sha256": CORPUS_WINDOW_LAW_SHA256,
            "maximum_d8": s.maximum,
            "minimum_d8_exclusive": s.minimum,
            "full_manifest_authorities": s.reference_authorities,
        }
    )


def _start_chronological_receipt(s: SimpleNamespace) -> None:
    s.receipt = dict(s.reference)
    s.receipt.pop("receipt_sha256", None)


def _update_chronological_receipt_0(s: SimpleNamespace) -> None:
    s.receipt.update(
        {
            "artifacts": sorted(s.artifacts_by_asset.values(), key=lambda row: row["asset"]),
            "sessions": len(s.expected_sessions),
            "verified_session_warm_hits": sum((int(part.receipt["verified_session_warm_hits"]) for part in s.parts)),
            "verified_session_cold_publishes": sum(
                (int(part.receipt["verified_session_cold_publishes"]) for part in s.parts)
            ),
            "model_array_bytes_materialized": sum(
                (int(part.receipt["model_array_bytes_materialized"]) for part in s.parts)
            ),
            "model_array_bytes_reused": sum((int(part.receipt["model_array_bytes_reused"]) for part in s.parts)),
            "physical_full_pack_opens": sum((int(part.receipt["physical_full_pack_opens"]) for part in s.parts)),
            "model_array_physical_fills": sum((int(part.receipt["model_array_physical_fills"]) for part in s.parts)),
        }
    )


def _update_chronological_receipt_1(s: SimpleNamespace) -> None:
    s.receipt.update({"warm_corpus_ready": all((part.receipt["warm_corpus_ready"] is True for part in s.parts))})


def _update_chronological_receipt_2(s: SimpleNamespace) -> None:
    s.receipt.update(
        {
            "corpus_window": {
                **dict(s.first_window),
                "maximum_d8": s.maximum,
                "observed_end_d8": max((int(part.receipt["corpus_window"]["observed_end_d8"]) for part in s.parts)),
                "window_chain": s.chain,
            }
        }
    )


def _update_chronological_receipt_3(s: SimpleNamespace) -> None:
    s.receipt.update({"denominator_calendar": {**dict(s.reference["denominator_calendar"]), **s.excluded}})


def _update_chronological_receipt_4(s: SimpleNamespace) -> None:
    s.receipt.update(
        {
            "asset_day_regimes": {
                "law": s.reference["asset_day_regimes"]["law"],
                "resolved": len(s.regimes),
                "expected": len({(row.asset, row.trading_day) for row in s.expected_sessions}),
                "declarations": [
                    {
                        "asset": row.asset,
                        "trading_day": row.trading_day,
                        "regime": row.regime,
                        "availability_ts_ns": row.availability_ts_ns,
                    }
                    for row in s.regimes
                ],
            },
            "candidate_batches": len(s.sessions),
            "clear_ready_candidates": len(s.teacher_paths),
            "clear_typed_no_sane_suffix": s.typed_no_suffix,
            "compliance_counts": s.compliance,
            "used_forecast_lineage_sha256": C.object_sha256(sorted(s.forecast_lineage)),
        }
    )


def _update_chronological_receipt_5(s: SimpleNamespace) -> None:
    s.receipt.update(
        {
            "prefix_verification": {
                "law": s.reference["prefix_verification"]["law"],
                "unique_cutoffs": sum((int(part.receipt["prefix_verification"]["unique_cutoffs"]) for part in s.parts)),
                "bytes_hashed": sum((int(part.receipt["prefix_verification"]["bytes_hashed"]) for part in s.parts)),
            },
            "session_stream_receipt_aggregate_sha256": s.stream_hash,
            "corpus_source_lineage_sha256": s.source_lineage,
            "raw_prefix_fidelity": {
                "expected_events": s.raw_evidence.expected_events,
                "observed_events": s.raw_evidence.observed_events,
                "mismatched_events": s.raw_evidence.mismatched_events,
                "source_receipt_sha256": s.raw_evidence.source_receipt_sha256,
                "pack_receipt_sha256": s.raw_evidence.pack_receipt_sha256,
            },
        }
    )


def _update_chronological_receipt_6(s: SimpleNamespace) -> None:
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
                **dict(s.reference["teacher_action_contract"]),
                "expected_asset_days": len({(row.asset, row.trading_day) for row in s.expected_sessions}),
            },
            "session_specs": s.session_receipts,
        }
    )


def _finish_chronological_merge(s: SimpleNamespace) -> EntryCorpus:
    s.receipt["receipt_sha256"] = C.object_sha256(s.receipt)
    return EntryCorpus(
        tuple(s.sessions),
        s.teacher_store,
        s.replay,
        s.raw_evidence,
        s.teacher_evidence,
        CANDIDATE_FEATURE_SCHEMA,
        MappingProxyType(s.receipt),
        _CorpusMergeProvenance(
            tuple(sorted(s.candidate_ids)),
            tuple(s.candidate_receipts),
            tuple(s.teacher_receipts),
            tuple(s.sidecar_hashes),
            tuple(s.forecast_lineage),
        ),
    )
