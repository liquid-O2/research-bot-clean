from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType, SimpleNamespace
from typing import Any

import numpy as np
import torch

from . import common as C
from .context_sources import stack_context_tensors
from .contracts import AssetDayRegime
from .event_pack import CATEGORY_SIZES, CATEGORICAL_FIELDS, CONTINUOUS_FIELDS
from .prefix_fidelity import PREFIX_DOMAIN
from .session_stream import MODEL_ARRAYS_CONVERSION_LAW_SHA256, SessionEventSource
from .teacher import build_teacher_store
from .corpus import (
    CANDIDATE_FEATURE_SCHEMA,
    CORPUS_SCHEMA,
    CORPUS_WINDOW_LAW_SHA256,
    CORPUS_WINDOW_SCHEMA,
    _clock_law_receipt_sha256,
    _tensor_hash,
)
from .corpus_artifacts import _sha
from .corpus_forecast import FORECAST_FEATURE_FIELDS, FORECAST_SCHEMA, _is_test_forecast_provider
from .corpus_session import (
    EntryCorpus,
    EntrySessionSpec,
    HORIZONS_SECONDS,
    ReplayCalibrationData,
    SelfSupervisedTargets,
    _CorpusMergeProvenance,
    _static_context_summary,
)


def _assemble_sessions(s: SimpleNamespace):
    s.sessions: list[EntrySessionSpec] = []
    s.session_receipts: list[dict[str, Any]] = []
    for s.session in sorted(s.examples_by_session, key=lambda item: (item.trading_day, item.asset, item.session_id)):
        s.examples = tuple(
            sorted(s.examples_by_session[s.session], key=lambda item: (item.decision_ts_ns, item.candidate_id))
        )
        s.context_items = [s.context_tensor_by_id.pop(example.candidate_id) for example in s.examples]
        s.context_values, s.context_type_ids, s.context_valid = stack_context_tensors(s.context_items)
        s.feature_array = np.asarray(
            [s.feature_by_id[example.candidate_id] for example in s.examples], dtype=np.float64
        )
        s.horizon_value = np.stack([s.target_by_id[example.candidate_id][0] for example in s.examples])
        s.horizon_valid = np.stack([s.target_by_id[example.candidate_id][1] for example in s.examples])
        s.phase = np.asarray([s.target_by_id[example.candidate_id][2] for example in s.examples], dtype=np.int64)
        s.phase_valid = np.asarray([s.target_by_id[example.candidate_id][3] for example in s.examples], dtype=np.bool_)
        s.candidate_cutoffs = torch.tensor(
            [example.raw_prefix_ref.event_count for example in s.examples], dtype=torch.int64
        )
        s.pin = s.event_source_pins.get(s.session)
        if s.pin is None:
            raise C.EntryV2Refusal("candidate session has no verified event-source pin")
        s.current_stat = s.pin["qre2_path"].stat()
        s.current_identity = (
            s.current_stat.st_size,
            s.current_stat.st_dev,
            s.current_stat.st_ino,
            s.current_stat.st_mtime_ns,
            s.current_stat.st_ctime_ns,
        )
        s.pinned_identity = (
            s.pin["source_size_bytes"],
            s.pin["source_device"],
            s.pin["source_inode"],
            s.pin["source_mtime_ns"],
            s.pin["source_ctime_ns"],
        )
        if s.current_identity != s.pinned_identity:
            raise C.EntryV2Refusal("QRE2 source changed after corpus trust-boundary hash")
        if "max_cutoff" not in s.pin:
            raise C.EntryV2Refusal("candidate session source lacks all-candidate cutoff")
        s.source = SessionEventSource(array_cache=s.array_cache, **s.pin)
        s.spec = EntrySessionSpec(
            source=s.source,
            examples=s.examples,
            candidate_cutoffs=s.candidate_cutoffs,
            candidate_features=torch.from_numpy(s.feature_array),
            context_values=s.context_values,
            context_type_ids=s.context_type_ids,
            context_valid=s.context_valid,
            self_supervised=SelfSupervisedTargets(
                torch.from_numpy(s.horizon_value),
                torch.from_numpy(s.horizon_valid),
                torch.from_numpy(s.phase),
                torch.from_numpy(s.phase_valid),
            ),
        )
        s.spec = replace(s.spec, static_features=torch.from_numpy(_static_context_summary(s.spec)))
        s.spec.validate()
        s.sessions.append(s.spec)
        s.session_receipts.append(
            {
                "asset": s.session.asset,
                "d8": s.session.trading_day,
                "session_id": s.session.session_id,
                "candidate_ids": list(s.spec.candidate_ids),
                "stream_receipt_sha256": s.source.receipt.receipt_sha256,
                "tensors_sha256": _tensor_hash(
                    s.candidate_cutoffs.numpy(),
                    s.feature_array,
                    s.context_values.detach().cpu().numpy(),
                    s.context_type_ids.detach().cpu().numpy(),
                    s.context_valid.detach().cpu().numpy(),
                    s.horizon_value,
                    s.horizon_valid,
                    s.phase,
                    s.phase_valid,
                ),
            }
        )
    if s.context_tensor_by_id:
        raise AssertionError("unconsumed candidate context tensors")


def _assemble_replay(s: SimpleNamespace):
    s.regime_declarations: list[AssetDayRegime] = []
    for s.asset, s.d8 in sorted(s.expected_session_open_ns):
        s.snapshot = s.provider.session_regime(s.asset, s.d8)
        if s.snapshot is None:
            raise C.EntryV2Refusal("asset-day has no causal SESSION forecast row")
        s.open_ns = s.expected_session_open_ns[s.asset, s.d8]
        if s.snapshot.segment != "SESSION" or int(s.snapshot.availability_ts_ns) != s.open_ns:
            raise C.EntryV2Refusal("asset-day regime was not frozen at the actual session open")
        s.regime = (
            s.snapshot.regime
            if s.snapshot.status == "READY" and s.snapshot.regime in {"LOW", "MID", "HIGH"}
            else "UNKNOWN"
        )
        s.regime_declarations.append(AssetDayRegime(s.asset, s.d8, s.regime, s.snapshot.availability_ts_ns))
    s.teacher_store = build_teacher_store(s.teacher_paths, expected_sessions=s.expected_sessions)
    for s.spec in s.sessions:
        s.spec.validate(s.teacher_store)
    s.replay_data = ReplayCalibrationData(
        MappingProxyType(dict(sorted(s.outcomes.items()))),
        tuple(sorted(s.expected_sessions)),
        tuple(s.regime_declarations),
    )
    s.replay_data.validate(s.sessions)


def _finish_corpus(s: SimpleNamespace):
    s.ordered_sources = [
        spec.source for spec in sorted(s.sessions, key=lambda item: (item.trading_day, item.asset, item.session_id))
    ]
    s.stream_receipt_aggregate = C.object_sha256([source.receipt.receipt_sha256 for source in s.ordered_sources])
    s.forecast_receipt_sha256 = _sha(getattr(s.provider, "receipt_sha256", ""), "forecast receipt")
    s.clock_law_receipt_sha256 = _clock_law_receipt_sha256()
    s.corpus_source_lineage_sha256 = C.object_sha256(
        {
            "event_sources": [
                [source.asset, source.d8, source.source_sha256, source.sidecar_sha256] for source in s.ordered_sources
            ],
            "candidate_receipts": sorted(s.candidate_receipt_hashes),
            "teacher_receipts": sorted(s.teacher_receipt_hashes),
            "forecast_receipt": s.forecast_receipt_sha256,
            "context_receipts": dict(sorted(s.context_receipts.items())),
            "qre2_calendar_authority": C.QRE2_CALENDAR_SHA256,
            "corpus_window_law_sha256": CORPUS_WINDOW_LAW_SHA256,
            "maximum_d8": s.resolved_maximum_d8,
            "minimum_d8_exclusive": s.resolved_minimum_d8,
            "full_manifest_authorities": sorted(s.full_authorities, key=lambda row: str(row["asset"])),
        }
    )
    s.receipt: dict[str, Any] = {
        "schema": CORPUS_SCHEMA,
        "holdout_start_d8": C.HOLDOUT_START_D8,
        "final_exam_permit": False,
        "corpus_window": {
            "schema": CORPUS_WINDOW_SCHEMA,
            "law_sha256": CORPUS_WINDOW_LAW_SHA256,
            "maximum_d8": s.resolved_maximum_d8,
            "minimum_d8_exclusive": s.resolved_minimum_d8,
            "start_d8_inclusive": min(s.observed_manifest_days),
            "observed_start_d8": min(s.observed_manifest_days),
            "observed_end_d8": max(s.observed_manifest_days),
            "full_manifest_authorities": sorted(s.full_authorities, key=lambda row: str(row["asset"])),
            "full_manifest_authority_sha256": C.object_sha256(
                sorted(s.full_authorities, key=lambda row: str(row["asset"]))
            ),
        },
        "artifacts": s.artifact_receipts,
        "sessions": len(s.expected_sessions),
        "verified_session_warm_hits": s.verified_session_warm_hits,
        "verified_session_cold_publishes": s.verified_session_cold_publishes,
        "model_array_bytes_materialized": s.model_array_bytes_materialized,
        "model_array_bytes_reused": s.model_array_bytes_reused,
        "physical_full_pack_opens": s.physical_full_pack_opens,
        "model_array_physical_fills": s.model_array_physical_fills,
        "warm_corpus_ready": bool(
            s.durable_store is not None
            and s.verified_session_cold_publishes == 0
            and (s.verified_session_warm_hits == len(s.observed_manifest_days))
        ),
        "denominator_calendar": {
            "law": "QRE2CAL1 authenticated per-asset source coverage followed by asset-aware Monday-Friday trade dates; only authority-marked FULL_CLOSE rows excluded inside coverage; every other typed empty/refused/outage row retained at zero",
            "authority_sha256": C.QRE2_CALENDAR_SHA256,
            "asset_coverage_start_d8": {asset: C.qre2_asset_coverage_start_d8(asset) for asset in sorted(s.required)},
            "excluded_non_trading_calendar_rows": dict(sorted(s.excluded_non_trading_calendar_rows.items())),
            "excluded_outside_asset_coverage_rows": dict(sorted(s.excluded_outside_asset_coverage_rows.items())),
            "excluded_full_closure_rows": dict(sorted(s.excluded_full_closure_rows.items())),
        },
        "asset_day_regimes": {
            "law": "QRE2 SESSION regime_tag frozen at session-open from strictly-prior data; WEAK=LOW; missing/NA is typed UNKNOWN",
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
        "candidate_feature_schema": list(CANDIDATE_FEATURE_SCHEMA),
        "candidate_feature_schema_sha256": C.object_sha256(list(CANDIDATE_FEATURE_SCHEMA)),
        "forecast_schema": FORECAST_SCHEMA,
        "forecast_feature_fields": list(FORECAST_FEATURE_FIELDS),
        "forecast_receipt_sha256": s.forecast_receipt_sha256,
        "test_forecast_adapter": _is_test_forecast_provider(s.provider),
        "used_forecast_lineage_sha256": C.object_sha256(sorted(s.forecast_lineage)),
        "context_receipts": dict(sorted(s.context_receipts.items())),
        "prefix_law": "lower_bound(ts_recv_ns,decision_ts_ns); equal receive-time batch future",
        "prefix_domain_hex": PREFIX_DOMAIN.hex(),
        "prefix_verification": {
            "law": "one incremental pass per session over sorted unique cutoffs",
            "unique_cutoffs": s.prefix_unique_cutoffs,
            "bytes_hashed": s.prefix_bytes_hashed,
        },
        "self_supervised_horizon_law": "first valid on-tick two-sided BBO at/after decision+h; side midpoint USD change minus frozen candidate cost; target-only mask",
        "self_supervised_phase_law": "60s target-row bits: midpoint_up | spread_wider<<1 | bid_size_dominant<<2; target-only mask",
        "horizons_seconds": list(HORIZONS_SECONDS),
        "event_continuous_fields": list(CONTINUOUS_FIELDS),
        "event_categorical_fields": list(CATEGORICAL_FIELDS),
        "event_category_sizes": list(CATEGORY_SIZES),
        "model_arrays_conversion_law_sha256": MODEL_ARRAYS_CONVERSION_LAW_SHA256,
        "session_stream_receipt_aggregate_sha256": s.stream_receipt_aggregate,
        "corpus_source_lineage_sha256": s.corpus_source_lineage_sha256,
        "clock_law_receipt_sha256": s.clock_law_receipt_sha256,
        "raw_prefix_fidelity": {
            "expected_events": s.raw_evidence.expected_events,
            "observed_events": s.raw_evidence.observed_events,
            "mismatched_events": s.raw_evidence.mismatched_events,
            "source_receipt_sha256": s.raw_evidence.source_receipt_sha256,
            "pack_receipt_sha256": s.raw_evidence.pack_receipt_sha256,
        },
        "teacher_alignment": {
            "expected_candidates": s.teacher_evidence.expected_candidates,
            "matched_candidates": s.teacher_evidence.matched_candidates,
            "mismatched_candidates": s.teacher_evidence.mismatched_candidates,
            "teacher_receipt_sha256": s.teacher_evidence.teacher_receipt_sha256,
            "join_receipt_sha256": s.teacher_evidence.join_receipt_sha256,
        },
        "teacher_store_sha256": s.teacher_store.store_hash,
        "teacher_action_contract": {
            "schema": "entry-v2-exact-oracle-teacher-v3",
            "denominator": "expected_asset_days",
            "expected_asset_days": len({(session.asset, session.trading_day) for session in s.expected_sessions}),
            "minimum_path_pnl_usd": C.MIN_EXPECTANCY_USD,
            "decision_law": "chronological arrival-final; same-asset/same-timestamp highest cert_close_usd clearing $600, candidate_id tie-break",
            "blocked_action_rows": "action_loss_mask=false",
            "future_path_dp": "hindsight_ceiling_only",
            "occupancy": "one_open_position_per_asset",
            "max_entries_per_asset_day": C.MAX_ENTRIES_PER_ASSET_DAY,
            "max_entries_per_portfolio_day": C.MAX_ENTRIES_PORTFOLIO_DAY,
        },
        "session_specs": s.session_receipts,
    }
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
