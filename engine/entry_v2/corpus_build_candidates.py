from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import numpy as np
import torch

from . import common as C
from .context_sources import tensorize_context_pack
from .contracts import CausalEntryExample, RawPrefixRef, Side
from .event_pack import EVENT_DTYPE
from .replay import ReplayOutcome
from .session_stream import SessionArrayCache
from .teacher import TeacherPath
from .corpus import (
    CANDIDATE_FEATURE_SCHEMA,
    VERIFIED_SESSION_LAW_SHA256,
    _candidate_features,
    _horizon_targets,
    _tensor_hash,
)
from .corpus_artifacts import _bit, _float, _int, _sha
from .corpus_forecast import ForecastQuery, _forecast_features
from .corpus_session import HORIZONS_SECONDS


def _materialize_session_candidates(s: SimpleNamespace):
    for s.candidate in s.candidate_rows:
        s.candidate_id = s.candidate["candidate_id"]
        if not s.candidate_id or s.candidate_id in s.candidate_ids_seen:
            raise C.EntryV2Refusal("duplicate/empty corpus candidate_id")
        s.candidate_ids_seen.add(s.candidate_id)
        s.teacher = s.teacher_by_id.get(s.candidate_id)
        if s.teacher is not None and (s.teacher["asset"], _int(s.teacher, "d8")) != (s.asset, s.d8):
            raise C.EntryV2Refusal("teacher row identity mismatch")
        if (s.candidate["asset"], _int(s.candidate, "d8")) != (s.asset, s.d8):
            raise C.EntryV2Refusal("candidate row identity mismatch")
        s.decision = _int(s.candidate, "decision_ts_ns")
        s.compliance = s.candidate["compliance_status"]
        if s.compliance not in s.compliance_counts:
            raise C.EntryV2Refusal("unknown candidate compliance status")
        if s.teacher is not None and s.teacher["compliance_status"] != s.compliance:
            raise C.EntryV2Refusal("candidate/teacher compliance mismatch")
        s.compliance_counts[s.compliance] += 1
        if s.teacher is not None and _int(s.teacher, "decision_ts_ns") != s.decision:
            raise C.EntryV2Refusal("teacher decision timestamp is permuted")
        if s.pack is None:
            raise C.EntryV2Refusal("candidate has no open event pack")
        s.cutoff = s.verified_cutoffs[s.candidate_id]
        s.prefix_events += s.cutoff
        _sha(s.candidate["lineage_sha256"], "candidate lineage")
        if s.compliance != "CLEAR":
            continue
        s.clear_expected += 1
        if s.teacher is None:
            continue
        s.clear_joined += 1
        s.teacher_status = s.teacher["status"]
        if s.teacher_status == "NO_SANE_SUFFIX":
            if any((_int(s.teacher, name) != 0 for name in ("exit_ts_ns", "wall_hit", "payer", "take_target"))) or any(
                (
                    float(_float(s.teacher, name)) != 0.0
                    for name in ("cert_close_usd", "mfe_usd", "mae_usd", "time_to_peak_sec")
                )
            ):
                raise C.EntryV2Refusal("typed NO_SANE_SUFFIX teacher carries target values")
            s.clear_typed_no_sane_suffix += 1
            continue
        if s.teacher_status != "READY":
            raise C.EntryV2Refusal("teacher row has an unknown status")
        s.clear_ready += 1
        s.exit_ts = _int(s.teacher, "exit_ts_ns")
        s.cert = float(_float(s.teacher, "cert_close_usd"))
        s.mfe = float(_float(s.teacher, "mfe_usd"))
        s.mae = float(_float(s.teacher, "mae_usd"))
        s.time_peak = float(_float(s.teacher, "time_to_peak_sec"))
        s.wall = _bit(s.teacher, "wall_hit")
        if s.exit_ts < s.decision or _bit(s.teacher, "payer") != (s.cert > 0.0):
            raise C.EntryV2Refusal("teacher exit/payer law mismatch")
        _bit(s.teacher, "take_target")
        if s.wall != (s.cert <= -C.WALL_USD):
            raise C.EntryV2Refusal("teacher wall status/value mismatch")
        s.query = ForecastQuery(s.candidate_id, s.asset, s.d8, s.decision, _int(s.candidate, "phase"))
        s.forecast_features, s.forecast_hash = _forecast_features(s.provider, s.query)
        s.forecast_lineage.append(s.forecast_hash)
        s.features = _candidate_features(s.candidate, s.forecast_features)
        s.context_tensor = s.context_tensor_by_id[s.candidate_id]
        s.context = None
        if not s.audit_context_recorded and bool(s.context_tensor.valid.any()):
            s.context = s.context_repo.pack(s.d8, s.decision)
            s.reference = tensorize_context_pack(s.context)
            if (
                not torch.equal(s.reference.values, s.context_tensor.values)
                or not torch.equal(s.reference.type_ids, s.context_tensor.type_ids)
                or (not torch.equal(s.reference.valid, s.context_tensor.valid))
            ):
                raise C.EntryV2Refusal("batched context differs from causal reference")
            s.audit_context_recorded = True
        s.context_content_hash = _tensor_hash(
            s.context_tensor.values.detach().cpu().numpy(),
            s.context_tensor.type_ids.detach().cpu().numpy(),
            s.context_tensor.valid.detach().cpu().numpy(),
        )
        s.example_lineage = C.object_sha256(
            {
                "schema": "entry-v2-example-input-lineage-v2",
                "candidate_lineage_sha256": s.candidate["lineage_sha256"],
                "forecast_row_lineage_sha256": s.forecast_hash,
                "context_receipt_sha256": s.context_receipts[s.asset],
                "packed_context_sha256": s.context_content_hash,
            }
        )
        s.side = Side.LONG if _int(s.candidate, "side") == 1 else Side.SHORT
        s.raw_ref = RawPrefixRef(
            shard=str(s.pack.path),
            event_start_index=0,
            event_end_index=s.cutoff,
            event_count=s.cutoff,
            first_availability_ts_ns=int(s.pack.rows[0]["ts_recv_ns"]),
            last_availability_ts_ns=int(s.pack.rows[s.cutoff - 1]["ts_recv_ns"]),
            source_hash=s.event_hash,
        )
        s.example = CausalEntryExample(
            candidate_id=s.candidate_id,
            asset=s.asset,
            trading_day=s.d8,
            session_id=s.session.session_id,
            decision_ts_ns=s.decision,
            side=s.side,
            phase=f"G1_PHASE_{_int(s.candidate, 'phase')}",
            locked_iid=_int(s.candidate, "locked_iid"),
            raw_prefix_ref=s.raw_ref,
            causal_features=s.features,
            context=s.context,
            lineage_hash=s.example_lineage,
        )
        if s.verified_hit:
            try:
                s.horizon_value, s.horizon_valid, s.phase_class, s.phase_valid = s.verified_targets[s.candidate_id]
            except KeyError as exc:
                raise C.EntryV2Refusal("verified-session target candidate differs") from s.exc
        else:
            s.horizon_value, s.horizon_valid, s.phase_class, s.phase_valid = _horizon_targets(s.pack, s.candidate)
        s.examples_by_session.setdefault(s.session, []).append(s.example)
        s.feature_by_id[s.candidate_id] = tuple((s.features[name] for name in CANDIDATE_FEATURE_SCHEMA))
        s.target_by_id[s.candidate_id] = (s.horizon_value, s.horizon_valid, s.phase_class, s.phase_valid)
        s.teacher_paths.append(
            TeacherPath(s.candidate_id, s.asset, s.d8, s.decision, s.exit_ts, s.cert, s.mfe, s.mae, s.wall, s.time_peak)
        )
        s.outcomes[s.candidate_id] = ReplayOutcome(
            s.candidate_id,
            s.exit_ts,
            s.cert,
            s.exit_ts,
            s.cert,
            wall_hit_ts_ns=s.exit_ts if s.wall else None,
            wall_pnl_usd=s.cert if s.wall else -C.WALL_USD,
        )
        s.context_tensor.validate()


def _publish_and_close_session(s: SimpleNamespace):
    if not s.verified_hit and s.durable_store is not None:
        s.current_target_ids = tuple(
            (row["candidate_id"] for row in s.candidate_rows if row["candidate_id"] in s.target_by_id)
        )
        s.legacy_values = (
            np.stack([s.target_by_id[candidate_id][0] for candidate_id in s.current_target_ids])
            if s.current_target_ids
            else np.empty((0, len(HORIZONS_SECONDS)), np.float64)
        )
        s.legacy_valid = (
            np.stack([s.target_by_id[candidate_id][1] for candidate_id in s.current_target_ids])
            if s.current_target_ids
            else np.empty((0, len(HORIZONS_SECONDS)), np.bool_)
        )
        s.legacy_phase = np.asarray(
            [
                (int(s.target_by_id[candidate_id][2]), int(s.target_by_id[candidate_id][3]))
                for candidate_id in s.current_target_ids
            ],
            dtype=np.int64,
        ).reshape((-1, 2))
        s.prefix_rows = (
            np.asarray(s.pack.rows[: max(s.verified_cutoffs.values())]).copy()
            if s.pack is not None and s.verified_cutoffs
            else np.empty((0,), dtype=EVENT_DTYPE)
        )
        s.source_pin_semantic: dict[str, Any] = {}
        if s.event_hash != "ABSENT":
            s.source_pin_semantic = {
                **s.event_source_pins[s.session],
                "qre2_path": str(s.event_source_pins[s.session]["qre2_path"]),
                "record_start_d8": int(s.pack.sidecar["record_window"]["start_d8"]),
                "record_end_d8_exclusive": int(s.pack.sidecar["record_window"]["end_d8_exclusive"]),
            }
        s.measured = (
            {"physical_full_pack_opens": int(s.pack is not None), "model_array_physical_fills": 0}
            if s.session_source is None
            else s.session_source.measurements.snapshot()
        )
        s.published = s.durable_store.publish(
            "verified-sessions",
            s.verified_identity,
            VERIFIED_SESSION_LAW_SHA256,
            tuple(
                (
                    np.frombuffer(raw, dtype=np.uint8).copy()
                    for raw in (s.candidate_raw, s.teacher_raw, s.candidate_receipt_raw, s.teacher_receipt_raw)
                )
            )
            + (s.prefix_rows.view(np.uint8), s.legacy_values, s.legacy_valid, s.legacy_phase),
            semantic={
                "schema": "entry-v2-verified-session-map-v1",
                "source_pin": s.source_pin_semantic,
                "target_candidate_ids": list(s.current_target_ids),
                "prefix_unique_cutoffs": len(set(s.verified_cutoffs.values())),
            },
            producer={
                "schema": "entry-v2-verified-session-producer-v1",
                "physical_full_pack_opens": int(s.measured["physical_full_pack_opens"]),
                "model_array_physical_fills": int(s.measured["model_array_physical_fills"]),
                "candidate_payload_reads": 1,
                "teacher_payload_reads": 1,
            },
        )
        s.published.close()
        s.verified_session_cold_publishes += 1
    if s.session_source is not None:
        s.model_array_bytes = SessionArrayCache.planned_bytes(s.session_source)
        s.source_measurements = s.session_source.measurements.snapshot()
        if s.verified_hit:
            s.model_array_bytes_reused += s.model_array_bytes
        elif s.source_measurements["model_array_physical_fills"] == 1:
            s.model_array_bytes_materialized += s.model_array_bytes
        s.model_array_physical_fills += int(s.source_measurements["model_array_physical_fills"])
    s.physical_full_pack_opens += int(not s.verified_hit and s.pack is not None)
    if s.pack is not None:
        s.pack.close()
    if s.verified_product is not None:
        s.verified_product.close()
