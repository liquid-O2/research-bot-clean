from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType
import tempfile
import unittest
from unittest import mock

import numpy as np
import torch

from . import common as C
from .context_sources import CausalContextRepository
from .corpus import (
    _prefix_sha256,
    build_corpus,
)
from .corpus_artifacts import AssetArtifactSet, _read_pinned
from .corpus_forecast import (
    ExplicitForecastRows,
    ForecastQuery,
    ForecastRow,
    ForecastSegmentSnapshot,
    AssetScopedForecastProvider,
    QRE2ForecastArtifactInput,
    QRE2ForecastProvider,
    QRE2_FORECAST_LAW_SHA256,
    _forecast_features,
    _forecast_lineage,
    _forecast_vintage_features,
)
from .corpus_forecast_qre2 import _FORECAST_COLUMNS
from .corpus_merge import (
    merge_asset_corpora,
    merge_chronological_corpora,
)
from .event_pack import EVENT_DTYPE, EventPack, HEADER, MAGIC, ROW_BYTES, VERSION
from .plan_contract import CLOCK_LAW_RECEIPT_FILE_SHA256
from .session_stream import CUTOFF_RULE
from .session_stream import SessionArrayCache
from .durable_store import DurableEntryV2Store


NS = 1_000_000_000
CANDIDATE_COLUMNS = (
    "candidate_id", "asset", "d8", "locked_iid", "selection_basis_d8",
    "confirmation_ts_recv_ns", "confirmation_event_ordinal", "decision_ts_ns",
    "decision_sec", "side", "phase", "rung_mask", "delay", "phase_open_utc",
    "phase_close_utc", "event_cutoff", "prefix_last_event_ordinal",
    "prefix_last_availability_ts_ns", "event_pack_sha256", "prefix_sha256",
    "clock_law_receipt_sha256", "lineage_sha256", "entry_bid_px", "entry_ask_px",
    "entry_mid2", "entry_spread_usd", "frozen_cost_usd",
    "atr14_prev_usd", "spread_prior_present", "spread_prior_usd",
    "sane_ceiling_usd", "compliance_status", "compliance_distance_sec",
    "compliance_artifact_sha256",
)
TEACHER_COLUMNS = (
    "candidate_id", "asset", "d8", "decision_ts_ns", "exit_ts_ns",
    "phase_close_utc", "status", "cert_close_usd", "mfe_usd", "mae_usd",
    "time_to_peak_sec", "wall_hit", "payer", "take_target",
    "compliance_status",
)
CANDIDATE_MANIFEST_COLUMNS = (
    "asset", "d8", "status", "rows", "raw_events", "two_sided_events",
    "sane_events", "candidate_file", "candidate_sha256", "event_pack_sha256",
    "receipt_file", "receipt_sha256",
)
TEACHER_MANIFEST_COLUMNS = (
    "asset", "d8", "rows", "ready", "refused", "teacher_file",
    "teacher_sha256", "candidate_sha256", "event_pack_sha256",
    "receipt_file", "receipt_sha256",
)
LOCK_COLUMNS = (
    "asset", "d8", "status", "locked_iid", "selection_basis_d8",
    "selection_basis_updates", "selection_basis_symbol", "open_utc",
    "close_utc",
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _write(path: Path, raw: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return _sha(raw)


def _tsv(schema: str, columns: tuple[str, ...], rows: list[dict[str, object]],
         *, d8: int | None = None) -> bytes:
    suffix = f" d8={d8}" if d8 is not None else ""
    lines = [
        f"# {schema} start_d8=20250101 end_d8_exclusive=20250104{suffix}",
        "\t".join(columns),
    ]
    lines.extend("\t".join(str(row[name]) for name in columns) for row in rows)
    return ("\n".join(lines) + "\n").encode()


def _json(path: Path, value: dict[str, object]) -> str:
    return _write(path, (json.dumps(value, sort_keys=True,
                                    separators=(",", ":")) + "\n").encode())


class CorpusFixture:
    def __init__(self, root: Path, *, teacher_mode: str = "ready",
                 asset: str = "SI", second_ready: bool = False) -> None:
        self.root = root
        self.asset = asset
        self.no_lock_d8 = 20250101
        self.d8 = 20250102
        self.empty_d8 = 20250103
        self.open_utc = 1_735_776_000
        self.close_utc = self.open_utc + 600
        self.locked_iid = 17
        event_dir = root / "events" / self.asset
        event_dir.mkdir(parents=True, exist_ok=True)
        self.event_path = event_dir / f"{self.d8}.qre2"

        offsets = (10, 100, 200, 201, 210, 250, 251, 260, 310, 500, 550)
        rows = np.zeros(len(offsets), dtype=EVENT_DTYPE)
        rows["ts_recv_ns"] = [
            (self.open_utc + offset) * NS for offset in offsets
        ]
        rows["ts_event_ns"] = rows["ts_recv_ns"] - 50
        base = 25_000_000_000
        rows["bid_px"] = [base + index * 5_000_000 for index in range(len(rows))]
        rows["ask_px"] = rows["bid_px"] + 5_000_000
        rows["price"] = rows["bid_px"]
        rows["size"] = 1
        rows["bid_sz"] = rows["ask_sz"] = 10
        rows["bid_ct"] = rows["ask_ct"] = 1
        rows["sequence"] = np.arange(len(rows), dtype=np.uint32)
        rows["receive_session_sec"] = offsets
        rows["action"] = 65
        header = HEADER.pack(
            MAGIC, VERSION, C.ASSET_INDEX[self.asset], self.d8,
            self.locked_iid, self.open_utc,
            self.close_utc, len(rows), ROW_BYTES, 0)
        event_hash = _write(self.event_path, header + rows.tobytes())
        descriptors = []
        for name in EVENT_DTYPE.names or ():
            dtype, offset = EVENT_DTYPE.fields[name][:2]
            descriptors.append({
                "name": name,
                "dtype": dtype.str.removeprefix("|"),
                "offset_bytes": int(offset),
            })
        _json(self.event_path.with_suffix(".qre2.json"), {
            "schema": "QRE2EVENTMETA2", "status": "READY",
            "asset": self.asset, "asset_idx": C.ASSET_INDEX[self.asset],
            "d8": self.d8,
            "locked_iid": self.locked_iid, "event_count": len(rows),
            "open_utc": self.open_utc, "close_utc": self.close_utc,
            "event_pack_sha256": event_hash,
            "binary_file": f"events/{self.asset}/{self.d8}.qre2",
            "source_hashes": {"event_pack_sha256": event_hash},
            "cutoff_rule": CUTOFF_RULE,
            "session_assignment_clock": "ts_recv",
            "symbology_date_clock": "floor_utc(ts_recv)",
            "causal_visibility_clock": "IndexTs/ts_recv",
            "exchange_feature_clock": "ts_event",
            "equal_receive_time": "future",
            "tie_order": "ordered_input_manifest_then_dbn_decode_ordinal",
            "record_window": {"start_d8": 20250101,
                              "end_d8_exclusive": 20250104},
            "binary_schema": {
                "magic": "QRE2EVT2", "byte_order": "little",
                "header_bytes": HEADER.size, "row_bytes": ROW_BYTES,
                "layout": "packed_array_of_structs", "arrays": descriptors,
            },
        })
        self.event_hash = event_hash

        decisions = ((self.open_utc + 200) * NS, (self.open_utc + 250) * NS)
        cutoffs: list[int] = []
        prefix_hashes: list[str] = []
        with EventPack(self.event_path, verify_hash=True) as pack:
            for decision in decisions:
                cutoff = pack.cutoff(decision)
                cutoffs.append(cutoff)
                prefix_hashes.append(_prefix_sha256(pack, cutoff))
        self.clear_id = f"{self.asset}-20250102-clear"
        self.prohibited_id = f"{self.asset}-20250102-prohibited"
        ids = (self.clear_id, self.prohibited_id)
        compliance = ("CLEAR", "PROHIBITED")
        candidate_rows: list[dict[str, object]] = []
        teacher_rows: list[dict[str, object]] = []
        for index, (candidate_id, decision, cutoff, prefix, status) in enumerate(
                zip(ids, decisions, cutoffs, prefix_hashes, compliance)):
            entry = rows[cutoff - 1]
            candidate_rows.append({
                "candidate_id": candidate_id, "asset": self.asset, "d8": self.d8,
                "locked_iid": self.locked_iid, "selection_basis_d8": 20250101,
                "confirmation_ts_recv_ns": decision - 120 * NS,
                "confirmation_event_ordinal": cutoff - 1,
                "decision_ts_ns": decision,
                "decision_sec": decision // NS - self.open_utc,
                "side": 1 if index == 0 else -1, "phase": index,
                "rung_mask": 3 << index, "delay": "STANDARD_120",
                "phase_open_utc": self.open_utc,
                "phase_close_utc": self.close_utc,
                "event_cutoff": cutoff, "prefix_last_event_ordinal": cutoff - 1,
                "prefix_last_availability_ts_ns": int(
                    rows[cutoff - 1]["ts_recv_ns"]
                ),
                "event_pack_sha256": event_hash,
                "prefix_sha256": prefix,
                "clock_law_receipt_sha256": CLOCK_LAW_RECEIPT_FILE_SHA256,
                "lineage_sha256": str(index + 4) * 64,
                "entry_bid_px": int(entry["bid_px"]),
                "entry_ask_px": int(entry["ask_px"]),
                "entry_mid2": int(entry["bid_px"]) + int(entry["ask_px"]),
                "entry_spread_usd": 25.0, "frozen_cost_usd": 30.0,
                "atr14_prev_usd": 800.0, "spread_prior_present": 1,
                "spread_prior_usd": 25.0, "sane_ceiling_usd": 250.0,
                "compliance_status": status, "compliance_distance_sec": 3600.0,
                "compliance_artifact_sha256": "c" * 64,
            })
            teacher_rows.append({
                "candidate_id": candidate_id, "asset": self.asset, "d8": self.d8,
                "decision_ts_ns": decision, "exit_ts_ns": decision + 300 * NS,
                "phase_close_utc": self.close_utc, "status": "READY",
                "cert_close_usd": 1000.0 + index * 100.0, "mfe_usd": 1200.0,
                "mae_usd": 100.0, "time_to_peak_sec": 100.0, "wall_hit": 0,
                "payer": 1, "take_target": 1, "compliance_status": status,
            })
        if teacher_mode == "reverse":
            teacher_rows.reverse()
        elif teacher_mode == "missing":
            teacher_rows = [teacher_rows[1]]
        elif teacher_mode == "wrong_take":
            teacher_rows[0]["take_target"] = 0
        elif teacher_mode == "refused":
            teacher_rows[0].update({
                "exit_ts_ns": 0, "status": "NO_SANE_SUFFIX",
                "cert_close_usd": 0.0, "mfe_usd": 0.0, "mae_usd": 0.0,
                "time_to_peak_sec": 0.0, "payer": 0, "take_target": 0,
            })

        second_candidates: list[dict[str, object]] = []
        second_teachers: list[dict[str, object]] = []
        second_event_hash = "ABSENT"
        self.second_clear_id = f"{self.asset}-{self.empty_d8}-clear"
        if second_ready:
            self.second_event_path = event_dir / f"{self.empty_d8}.qre2"
            second_header = HEADER.pack(
                MAGIC, VERSION, C.ASSET_INDEX[self.asset], self.empty_d8,
                self.locked_iid, self.open_utc, self.close_utc,
                len(rows), ROW_BYTES, 0,
            )
            second_event_hash = _write(
                self.second_event_path, second_header + rows.tobytes())
            _json(self.second_event_path.with_suffix(".qre2.json"), {
                "schema": "QRE2EVENTMETA2", "status": "READY",
                "asset": self.asset, "asset_idx": C.ASSET_INDEX[self.asset],
                "d8": self.empty_d8, "locked_iid": self.locked_iid,
                "event_count": len(rows), "open_utc": self.open_utc,
                "close_utc": self.close_utc,
                "event_pack_sha256": second_event_hash,
                "binary_file": f"events/{self.asset}/{self.empty_d8}.qre2",
                "source_hashes": {"event_pack_sha256": second_event_hash},
                "cutoff_rule": CUTOFF_RULE,
                "session_assignment_clock": "ts_recv",
                "symbology_date_clock": "floor_utc(ts_recv)",
                "causal_visibility_clock": "IndexTs/ts_recv",
                "exchange_feature_clock": "ts_event",
                "equal_receive_time": "future",
                "tie_order": "ordered_input_manifest_then_dbn_decode_ordinal",
                "record_window": {"start_d8": 20250101,
                                  "end_d8_exclusive": 20250104},
                "binary_schema": {
                    "magic": "QRE2EVT2", "byte_order": "little",
                    "header_bytes": HEADER.size, "row_bytes": ROW_BYTES,
                    "layout": "packed_array_of_structs", "arrays": descriptors,
                },
            })
            with EventPack(self.second_event_path, verify_hash=True) as second_pack:
                second_prefix_hash = _prefix_sha256(
                    second_pack, int(candidate_rows[0]["event_cutoff"]))
            second_candidate = dict(candidate_rows[0])
            second_candidate.update({
                "candidate_id": self.second_clear_id, "d8": self.empty_d8,
                "event_pack_sha256": second_event_hash,
                "prefix_sha256": second_prefix_hash,
                "lineage_sha256": "9" * 64,
            })
            second_teacher = dict(teacher_rows[0])
            second_teacher.update({
                "candidate_id": self.second_clear_id, "d8": self.empty_d8,
            })
            second_candidates = [second_candidate]
            second_teachers = [second_teacher]

        locks_hash = _write(
            root / "locks" / f"{self.asset}.tsv",
            _tsv("QRE2LOCK2", LOCK_COLUMNS, (
                {
                    "asset": self.asset, "d8": self.no_lock_d8,
                    "status": "WARMUP_NO_PREVIOUS", "locked_iid": -1,
                    "selection_basis_d8": -1,
                    "selection_basis_updates": 0,
                    "selection_basis_symbol": "-", "open_utc": self.open_utc,
                    "close_utc": self.close_utc,
                },
                {
                    "asset": self.asset, "d8": self.d8,
                    "status": "LOCKED", "locked_iid": self.locked_iid,
                    "selection_basis_d8": self.no_lock_d8,
                    "selection_basis_updates": 100,
                    "selection_basis_symbol": "SIZ4", "open_utc": self.open_utc,
                    "close_utc": self.close_utc,
                },
                {
                    "asset": self.asset, "d8": self.empty_d8,
                    "status": "LOCKED", "locked_iid": self.locked_iid,
                    "selection_basis_d8": self.d8,
                    "selection_basis_updates": 100,
                    "selection_basis_symbol": "SIZ4", "open_utc": self.open_utc,
                    "close_utc": self.close_utc,
                },
            )),
        )

        session_specs: list[dict[str, object]] = []
        for d8, candidates, teachers, status, pack_hash, raw_events in (
            (self.no_lock_d8, [], [], "NO_LOCK", "ABSENT", 0),
            (self.d8, candidate_rows, teacher_rows, "READY", event_hash, len(rows)),
            (self.empty_d8, second_candidates, second_teachers,
             "READY" if second_ready else "NO_EVENTS",
             second_event_hash, len(rows) if second_ready else 0),
        ):
            candidate_path = root / "g1" / "candidates" / self.asset / f"{d8}.tsv"
            teacher_path = root / "g1" / "teacher" / self.asset / f"{d8}.tsv"
            candidate_hash = _write(candidate_path, _tsv(
                "QRE2G1CAND2", CANDIDATE_COLUMNS, candidates, d8=d8))
            teacher_hash = _write(teacher_path, _tsv(
                "QRE2G1TEACH2", TEACHER_COLUMNS, teachers, d8=d8))
            candidate_receipt_path = (
                root / "g1" / "receipts" / self.asset / f"{d8}.candidates.json")
            teacher_receipt_path = (
                root / "g1" / "receipts" / self.asset / f"{d8}.teacher.json")
            candidate_receipt_hash = _json(candidate_receipt_path, {
                "schema": "QRE2G1CANDRECEIPT2", "asset": self.asset, "d8": d8,
                "start_d8": 20250101, "end_d8_exclusive": 20250104,
                "rows": len(candidates), "raw_events": raw_events,
                "source_hashes": {
                    "event_pack_sha256": (
                        None if pack_hash == "ABSENT" else pack_hash
                    ),
                    "locks_sha256": locks_hash,
                },
                "output_sha256": candidate_hash,
                "holdout_start_d8": C.HOLDOUT_START_D8, "final_exam_permit": False,
            })
            teacher_event_hash = pack_hash if teachers else "ABSENT"
            teacher_receipt_hash = _json(teacher_receipt_path, {
                "schema": "QRE2G1TEACHRECEIPT2", "asset": self.asset, "d8": d8,
                "start_d8": 20250101, "end_d8_exclusive": 20250104,
                "rows": len(teachers), "ready": sum(
                    row["status"] == "READY" for row in teachers),
                "source_hashes": {"candidate_sha256": candidate_hash,
                                  "event_pack_sha256": (
                                      None if teacher_event_hash == "ABSENT"
                                      else teacher_event_hash)},
                "output_sha256": teacher_hash,
                "holdout_start_d8": C.HOLDOUT_START_D8, "final_exam_permit": False,
            })
            session_specs.append({
                "d8": d8, "status": status, "candidate_rows": len(candidates),
                "teacher_rows": len(teachers), "ready": sum(
                    row["status"] == "READY" for row in teachers),
                "candidate_hash": candidate_hash, "teacher_hash": teacher_hash,
                "event_hash": pack_hash, "teacher_event_hash": teacher_event_hash,
                "candidate_receipt_hash": candidate_receipt_hash,
                "teacher_receipt_hash": teacher_receipt_hash,
            })

        candidate_manifest_rows = []
        teacher_manifest_rows = []
        for spec in session_specs:
            d8 = int(spec["d8"])
            candidate_manifest_rows.append({
                "asset": self.asset, "d8": d8, "status": spec["status"],
                "rows": spec["candidate_rows"], "raw_events": (
                    len(rows) if d8 in ({self.d8, self.empty_d8}
                                        if second_ready else {self.d8}) else 0),
                "two_sided_events": len(rows) if d8 in (
                    {self.d8, self.empty_d8} if second_ready else {self.d8}) else 0,
                "sane_events": len(rows) if d8 in (
                    {self.d8, self.empty_d8} if second_ready else {self.d8}) else 0,
                "candidate_file": f"g1/candidates/{self.asset}/{d8}.tsv",
                "candidate_sha256": spec["candidate_hash"],
                "event_pack_sha256": spec["event_hash"],
                "receipt_file": f"g1/receipts/{self.asset}/{d8}.candidates.json",
                "receipt_sha256": spec["candidate_receipt_hash"],
            })
            teacher_manifest_rows.append({
                "asset": self.asset, "d8": d8, "rows": spec["teacher_rows"],
                "ready": spec["ready"],
                "refused": int(spec["teacher_rows"]) - int(spec["ready"]),
                "teacher_file": f"g1/teacher/{self.asset}/{d8}.tsv",
                "teacher_sha256": spec["teacher_hash"],
                "candidate_sha256": spec["candidate_hash"],
                "event_pack_sha256": spec["teacher_event_hash"],
                "receipt_file": f"g1/receipts/{self.asset}/{d8}.teacher.json",
                "receipt_sha256": spec["teacher_receipt_hash"],
            })
        candidate_manifest_path = (
            root / "g1" / "candidates" / self.asset / "manifest.tsv")
        teacher_manifest_path = root / "g1" / "teacher" / self.asset / "manifest.tsv"
        candidate_manifest_hash = _write(candidate_manifest_path, _tsv(
            "QRE2G1CANDMAN2", CANDIDATE_MANIFEST_COLUMNS,
            candidate_manifest_rows))
        teacher_manifest_hash = _write(teacher_manifest_path, _tsv(
            "QRE2G1TEACHMAN2", TEACHER_MANIFEST_COLUMNS, teacher_manifest_rows))
        event_manifest_hash = _write(
            root / "events" / self.asset / "manifest.tsv",
            b"# QRE2EVENTMAN2 test-fixture\n",
        )
        candidate_count = sum(int(row["rows"]) for row in candidate_manifest_rows)
        no_candidate_sessions = sum(
            int(row["rows"]) == 0 for row in candidate_manifest_rows
        )
        teacher_count = sum(int(row["rows"]) for row in teacher_manifest_rows)
        teacher_ready_count = sum(int(row["ready"]) for row in teacher_manifest_rows)
        teacher_refused_count = sum(
            int(row["refused"]) for row in teacher_manifest_rows
        )
        candidate_aggregate_hash = _json(
            root / "g1" / "receipts" / f"{self.asset}.candidates.json", {
                "schema": "QRE2G1CANDRECEIPT2", "stage": "candidates",
                "asset": self.asset, "start_d8": 20250101,
                "end_d8_exclusive": 20250104, "sessions": len(session_specs),
                "candidates": candidate_count,
                "no_candidate_sessions": no_candidate_sessions,
                "manifest_sha256": candidate_manifest_hash,
                "holdout_start_d8": C.HOLDOUT_START_D8,
                "final_exam_permit": False,
            })
        teacher_aggregate_hash = _json(
            root / "g1" / "receipts" / f"{self.asset}.teacher.json", {
                "schema": "QRE2G1TEACHRECEIPT2", "stage": "teacher",
                "asset": self.asset, "start_d8": 20250101,
                "end_d8_exclusive": 20250104, "sessions": len(session_specs),
                "candidates": teacher_count,
                "teacher_ready": teacher_ready_count,
                "teacher_refused": teacher_refused_count,
                "manifest_sha256": teacher_manifest_hash,
                "auxiliary_sha256": hashlib.sha256((
                    candidate_manifest_hash + "\n" + event_manifest_hash
                ).encode()).hexdigest(),
                "holdout_start_d8": C.HOLDOUT_START_D8,
                "final_exam_permit": False,
            })
        self.artifact = AssetArtifactSet(
            root, self.asset, candidate_manifest_hash, teacher_manifest_hash,
            candidate_aggregate_hash, teacher_aggregate_hash)
        forecast_session = ForecastSegmentSnapshot(
            "SESSION", "READY", self.open_utc * NS, 500.0, 900.0,
            (100.0, 200.0, 300.0, 400.0, 500.0), 1.1, "MID", "REGIME",
            "a" * 64)
        forecast_phase = ForecastSegmentSnapshot(
            "TOKYO", "READY", decisions[0] - NS, 400.0, 800.0,
            (80.0, 160.0, 240.0, 320.0, 400.0), None, "NA",
            "UNSCALED_FALLBACK", "b" * 64)
        candidate_forecast = ForecastRow(
            self.clear_id, self.asset, self.d8, decisions[0], 0,
            forecast_session, forecast_phase, "f" * 64)
        self.empty_forecast = ForecastRow(
            f"{self.asset}-{self.empty_d8}-denominator-only",
            self.asset,
            self.empty_d8,
            decisions[0],
            0,
            forecast_session,
            forecast_phase,
            "e" * 64,
        )
        self.forecasts = ExplicitForecastRows((
            candidate_forecast,
            (ForecastRow(
                self.second_clear_id, self.asset, self.empty_d8,
                decisions[0], 0, forecast_session, forecast_phase, "e" * 64,
            ) if second_ready else self.empty_forecast),
        ))
        context_receipt: dict[str, object] = {
            "schema": "entry-v2-test-context-receipt-v1", "asset": self.asset}
        context_receipt["receipt_sha256"] = C.object_sha256(context_receipt)
        self.context = CausalContextRepository(
            self.asset, MappingProxyType({}), MappingProxyType(context_receipt))

    def build(self, *, maximum_d8: int | None = None,
              minimum_d8_exclusive: int | None = None,
              array_cache: SessionArrayCache | None = None,
              require_durable_window: bool = False):
        return build_corpus(
            [self.artifact], {self.asset: self.context}, self.forecasts,
            require_assets=(self.asset,), allow_test_forecast_adapter=True,
            maximum_d8=maximum_d8,
            minimum_d8_exclusive=minimum_d8_exclusive,
            array_cache=array_cache,
            require_durable_window=require_durable_window)


class CorpusBridgeTest(unittest.TestCase):
    def _temporary(self):
        return tempfile.TemporaryDirectory(dir=C.CACHE_ROOT)

    def test_verified_session_cold_then_new_object_warm_avoids_payload_opens(self) -> None:
        with self._temporary() as td:
            fixture = CorpusFixture(Path(td))
            store = DurableEntryV2Store(Path(td) / "durable")
            cold_cache = SessionArrayCache(1 << 20, durable_store=store)
            cold = fixture.build(array_cache=cold_cache)
            self.assertFalse(cold.receipt["warm_corpus_ready"])
            self.assertGreater(cold.receipt["verified_session_cold_publishes"], 0)
            cold_cache.close()
            reopened = DurableEntryV2Store(Path(td) / "durable")
            warm_cache = SessionArrayCache(1 << 20, durable_store=reopened)
            original = _read_pinned

            def authority_only(path, expected, name):
                if name in {"candidate session", "teacher session",
                            "candidate session receipt", "teacher session receipt"}:
                    raise AssertionError(f"warm payload opened: {name}")
                return original(path, expected, name)

            with mock.patch.object(EventPack, "__init__", autospec=True,
                                   side_effect=AssertionError("warm QRE2 opened")), \
                    mock.patch("engine.entry_v2.corpus._read_pinned",
                               side_effect=authority_only):
                warm = fixture.build(array_cache=warm_cache)
            self.assertTrue(warm.receipt["warm_corpus_ready"])
            self.assertEqual(warm.receipt["verified_session_cold_publishes"], 0)
            self.assertEqual(warm.receipt["verified_session_warm_hits"], 3)
            self.assertEqual(
                [(row.candidate_ids, row.self_supervised.horizon_value.tolist())
                 for row in warm.sessions],
                [(row.candidate_ids, row.self_supervised.horizon_value.tolist())
                 for row in cold.sessions],
            )
            warm_cache.close()

    def test_strict_durable_parent_refuses_missing_before_qre_open(self) -> None:
        with self._temporary() as td:
            fixture = CorpusFixture(Path(td))
            store = DurableEntryV2Store(Path(td) / "durable")
            empty_cache = SessionArrayCache(1 << 20, durable_store=store)
            with mock.patch.object(
                    EventPack, "__init__", autospec=True,
                    side_effect=AssertionError("strict parent opened QRE2")):
                with self.assertRaisesRegex(
                        C.EntryV2Refusal, "strict durable corpus session is absent"):
                    fixture.build(
                        array_cache=empty_cache, require_durable_window=True)
            empty_cache.close()

            cold_cache = SessionArrayCache(1 << 20, durable_store=store)
            fixture.build(array_cache=cold_cache)
            cold_cache.close()
            warm_cache = SessionArrayCache(1 << 20, durable_store=store)
            with mock.patch.object(
                    EventPack, "__init__", autospec=True,
                    side_effect=AssertionError("strict warm parent opened QRE2")):
                warm = fixture.build(
                    array_cache=warm_cache, require_durable_window=True)
            self.assertTrue(warm.receipt["warm_corpus_ready"])
            warm_cache.close()

    def test_exact_bridge_excludes_nonclear_and_keeps_empty_denominator(self) -> None:
        with self._temporary() as td:
            fixture = CorpusFixture(Path(td))
            original_sha = C.file_sha256
            qre2_hashes = 0

            def counted_sha(path):
                nonlocal qre2_hashes
                if Path(path).suffix == ".qre2":
                    qre2_hashes += 1
                return original_sha(path)

            with mock.patch.object(C, "file_sha256", side_effect=counted_sha), \
                    mock.patch.object(EventPack, "model_arrays", autospec=True) as arrays:
                corpus = fixture.build()
            arrays.assert_not_called()
            self.assertEqual(qre2_hashes, 1)
            self.assertEqual(len(corpus.sessions), 1)
            self.assertEqual(corpus.sessions[0].candidate_ids, (fixture.clear_id,))
            with corpus.sessions[0].source.open_arrays() as (continuous, _cat):
                self.assertEqual(
                    continuous.shape[0],
                    corpus.sessions[0].source.max_cutoff,
                )
            self.assertEqual(len(corpus.replay.expected_sessions), 2)
            self.assertEqual(corpus.receipt["compliance_counts"], {
                "CLEAR": 1, "PROHIBITED": 1, "COMPLIANCE_UNKNOWN": 0})
            self.assertTrue(corpus.raw_prefix_fidelity.passed)
            self.assertTrue(corpus.teacher_alignment.passed)
            self.assertTrue(bool(corpus.sessions[0].self_supervised.horizon_valid.all()))
            self.assertNotEqual(corpus.sessions[0].examples[0].lineage_hash, "4" * 64)
            self.assertEqual(
                corpus.sessions[0].examples[0].causal_features[
                    "session_forecast_present"], 1.0)
            names = set(corpus.sessions[0].examples[0].causal_features)
            self.assertFalse(any(token in name for name in names
                                 for token in ("cert", "mfe", "mae", "outcome")))

    def test_chronological_window_never_opens_post_window_payload(self) -> None:
        with self._temporary() as td:
            fixture = CorpusFixture(Path(td))
            post_candidate = (
                fixture.root / "g1" / "candidates" / fixture.asset
                / f"{fixture.empty_d8}.tsv"
            )
            post_teacher = (
                fixture.root / "g1" / "teacher" / fixture.asset
                / f"{fixture.empty_d8}.tsv"
            )
            full = fixture.build()
            # The full manifest still pins the original payload hash, but a
            # chronological rehearsal must not discover this later mutation.
            post_candidate.write_bytes(b"deliberately unreadable post-window payload")
            opened: list[Path] = []
            original_read = Path.read_bytes

            def guarded_read(path: Path) -> bytes:
                resolved = Path(path)
                if resolved in {post_candidate, post_teacher}:
                    opened.append(resolved)
                    raise AssertionError("post-window session payload was opened")
                return original_read(path)

            with mock.patch.object(Path, "read_bytes", autospec=True,
                                   side_effect=guarded_read):
                windowed = fixture.build(maximum_d8=fixture.d8)
            self.assertEqual(opened, [])
            self.assertEqual(
                tuple((row.asset, row.trading_day) for row in
                      windowed.replay.expected_sessions),
                ((fixture.asset, fixture.d8),),
            )
            self.assertEqual(windowed.sessions[0].trading_day, fixture.d8)
            self.assertEqual(windowed.receipt["sessions"], 1)
            window = windowed.receipt["corpus_window"]
            self.assertEqual(window["maximum_d8"], fixture.d8)
            self.assertEqual(window["observed_end_d8"], fixture.d8)
            authority = window["full_manifest_authorities"][0]
            self.assertEqual(authority["full_manifest_sessions"], 3)
            self.assertEqual(
                authority["candidate_manifest_sha256"],
                fixture.artifact.candidate_manifest_sha256,
            )

            full_boundary = tuple(
                row for row in full.sessions if row.trading_day <= fixture.d8
            )
            self.assertEqual(
                tuple((row.trading_day, row.candidate_ids,
                       row.self_supervised.horizon_value.tolist(),
                       row.self_supervised.horizon_valid.tolist())
                      for row in windowed.sessions),
                tuple((row.trading_day, row.candidate_ids,
                       row.self_supervised.horizon_value.tolist(),
                       row.self_supervised.horizon_valid.tolist())
                      for row in full_boundary),
            )

    def test_chronological_window_refuses_absent_h2_and_mixed_merge(self) -> None:
        with self._temporary() as td:
            root = Path(td)
            fixture = CorpusFixture(root)
            with self.assertRaisesRegex(C.EntryV2Refusal, "absent from manifest"):
                fixture.build(maximum_d8=20250104)
            with self.assertRaisesRegex(C.EntryV2Refusal, "HOLDOUT"):
                fixture.build(maximum_d8=C.HOLDOUT_START_D8)

        with self._temporary() as td:
            root = Path(td)
            fixtures = tuple(CorpusFixture(root, asset=asset) for asset in C.ASSETS)
            forecasts = ExplicitForecastRows(tuple(
                row for item in fixtures for row in item.forecasts.rows
            ))
            parts = []
            for index, item in enumerate(fixtures):
                parts.append(build_corpus(
                    (item.artifact,), {item.asset: item.context},
                    AssetScopedForecastProvider(forecasts, item.asset),
                    require_assets=(item.asset,),
                    allow_test_forecast_adapter=True,
                    maximum_d8=(item.d8 if index else item.empty_d8),
                ))
            with self.assertRaisesRegex(C.EntryV2Refusal, "window"):
                merge_asset_corpora(parts, maximum_d8=fixtures[0].d8)

    def test_incremental_windows_match_full_semantics_and_refuse_bad_chains(self) -> None:
        with self._temporary() as td:
            root = Path(td)
            fixtures = tuple(CorpusFixture(
                root, asset=asset, second_ready=True
            ) for asset in C.ASSETS)
            artifacts = tuple(item.artifact for item in fixtures)
            contexts = {item.asset: item.context for item in fixtures}
            forecasts = ExplicitForecastRows(tuple(
                row for item in fixtures for row in item.forecasts.rows
            ))
            full = build_corpus(
                artifacts, contexts, forecasts,
                allow_test_forecast_adapter=True,
                maximum_d8=fixtures[0].empty_d8,
            )
            first = build_corpus(
                artifacts, contexts, forecasts,
                allow_test_forecast_adapter=True,
                maximum_d8=fixtures[0].d8,
            )
            second = build_corpus(
                artifacts, contexts, forecasts,
                allow_test_forecast_adapter=True,
                minimum_d8_exclusive=fixtures[0].d8,
                maximum_d8=fixtures[0].empty_d8,
            )
            merged = merge_chronological_corpora((first, second))
            self.assertEqual(
                tuple((row.trading_day, row.asset, row.candidate_ids,
                       row.self_supervised.horizon_value.tolist(),
                       row.self_supervised.horizon_valid.tolist())
                      for row in merged.sessions),
                tuple((row.trading_day, row.asset, row.candidate_ids,
                       row.self_supervised.horizon_value.tolist(),
                       row.self_supervised.horizon_valid.tolist())
                      for row in full.sessions),
            )
            self.assertEqual(merged.teacher.store_hash, full.teacher.store_hash)
            self.assertEqual(merged.replay.expected_sessions,
                             full.replay.expected_sessions)
            self.assertEqual(dict(merged.replay.outcomes), dict(full.replay.outcomes))
            self.assertEqual(
                merged.receipt["corpus_source_lineage_sha256"],
                full.receipt["corpus_source_lineage_sha256"],
            )
            merged_body = dict(merged.receipt)
            full_body = dict(full.receipt)
            merged_body.pop("receipt_sha256")
            full_body.pop("receipt_sha256")
            merged_window = dict(merged_body["corpus_window"])
            self.assertIn("window_chain", merged_window)
            merged_window.pop("window_chain")
            merged_body["corpus_window"] = merged_window
            self.assertEqual(merged_body, full_body)

            with self.assertRaisesRegex(C.EntryV2Refusal, "overlap or gap"):
                merge_chronological_corpora((first, first))
            overlapping = build_corpus(
                artifacts, contexts, forecasts,
                allow_test_forecast_adapter=True,
                minimum_d8_exclusive=fixtures[0].no_lock_d8,
                maximum_d8=fixtures[0].empty_d8,
            )
            with self.assertRaisesRegex(C.EntryV2Refusal, "overlap or gap"):
                merge_chronological_corpora((first, overlapping))

        with self._temporary() as left_td, self._temporary() as right_td:
            left = tuple(CorpusFixture(
                Path(left_td), asset=asset, second_ready=True
            ) for asset in C.ASSETS)
            right = tuple(CorpusFixture(
                Path(right_td), asset=asset, second_ready=True,
                teacher_mode="wrong_take",
            ) for asset in C.ASSETS)
            left_forecasts = ExplicitForecastRows(tuple(
                row for item in left for row in item.forecasts.rows))
            right_forecasts = ExplicitForecastRows(tuple(
                row for item in right for row in item.forecasts.rows))
            first = build_corpus(
                tuple(item.artifact for item in left),
                {item.asset: item.context for item in left}, left_forecasts,
                allow_test_forecast_adapter=True, maximum_d8=left[0].d8,
            )
            second = build_corpus(
                tuple(item.artifact for item in right),
                {item.asset: item.context for item in right}, right_forecasts,
                allow_test_forecast_adapter=True,
                minimum_d8_exclusive=right[0].d8,
                maximum_d8=right[0].empty_d8,
            )
            with self.assertRaisesRegex(C.EntryV2Refusal, "authority"):
                merge_chronological_corpora((first, second))

    def test_asset_lane_merge_is_byte_identical_to_serial_corpus(self) -> None:
        with self._temporary() as td:
            root = Path(td)
            fixtures = tuple(
                CorpusFixture(root, asset=asset) for asset in C.ASSETS
            )
            artifacts = tuple(item.artifact for item in fixtures)
            contexts = {item.asset: item.context for item in fixtures}
            full_forecasts = ExplicitForecastRows(tuple(
                row for item in fixtures for row in item.forecasts.rows
            ))
            serial = build_corpus(
                artifacts, contexts, full_forecasts,
                allow_test_forecast_adapter=True,
            )
            parts = tuple(
                build_corpus(
                    (item.artifact,), {item.asset: item.context},
                    AssetScopedForecastProvider(full_forecasts, item.asset),
                    require_assets=(item.asset,),
                    allow_test_forecast_adapter=True,
                )
                for item in reversed(fixtures)
            )
            merged = merge_asset_corpora(parts)

            self.assertEqual(dict(merged.receipt), dict(serial.receipt))
            self.assertEqual(merged.teacher.store_hash,
                             serial.teacher.store_hash)
            self.assertEqual(merged.replay.expected_sessions,
                             serial.replay.expected_sessions)
            self.assertEqual(merged.replay.regime_declarations,
                             serial.replay.regime_declarations)
            self.assertEqual(dict(merged.replay.outcomes),
                             dict(serial.replay.outcomes))
            self.assertEqual(
                tuple((row.asset, row.trading_day, row.candidate_ids)
                      for row in merged.sessions),
                tuple((row.asset, row.trading_day, row.candidate_ids)
                      for row in serial.sessions),
            )

    def test_native_candidate_threshold_bit_cannot_override_exact_oracle_action(self) -> None:
        with self._temporary() as td:
            fixture = CorpusFixture(Path(td), teacher_mode="wrong_take")
            corpus = fixture.build()
            self.assertTrue(corpus.teacher[fixture.clear_id].take_target)

    def test_equal_time_and_future_bytes_are_outside_strict_prefix(self) -> None:
        with self._temporary() as td:
            fixture = CorpusFixture(Path(td))
            decision = (fixture.open_utc + 200) * NS
            with EventPack(fixture.event_path) as pack:
                cutoff = pack.cutoff(decision)
                original = _prefix_sha256(pack, cutoff)
            raw = bytearray(fixture.event_path.read_bytes())
            equal_price_offset = HEADER.size + cutoff * ROW_BYTES + 16
            raw[equal_price_offset] ^= 1
            fixture.event_path.write_bytes(raw)
            with EventPack(fixture.event_path) as pack:
                self.assertEqual(pack.cutoff(decision), cutoff)
                self.assertEqual(_prefix_sha256(pack, cutoff), original)
            raw = bytearray(fixture.event_path.read_bytes())
            prefix_price_offset = HEADER.size + (cutoff - 1) * ROW_BYTES + 16
            raw[prefix_price_offset] ^= 1
            fixture.event_path.write_bytes(raw)
            with EventPack(fixture.event_path) as pack:
                self.assertNotEqual(_prefix_sha256(pack, cutoff), original)

    def test_hash_mutation_and_missing_forecast_refuse(self) -> None:
        with self._temporary() as td:
            fixture = CorpusFixture(Path(td))
            candidate = (fixture.root / "g1" / "candidates" / "SI" /
                         f"{fixture.d8}.tsv")
            candidate.write_bytes(candidate.read_bytes() + b"\n")
            with self.assertRaisesRegex(C.EntryV2Refusal, "hash mismatch"):
                fixture.build()
        with self._temporary() as td:
            fixture = CorpusFixture(Path(td))
            wrong = ExplicitForecastRows((replace(
                fixture.forecasts.rows[0], candidate_id="absent-candidate"),))
            with self.assertRaisesRegex(C.EntryV2Refusal, "forecast row missing"):
                build_corpus([fixture.artifact], {"SI": fixture.context}, wrong,
                             require_assets=("SI",),
                             allow_test_forecast_adapter=True)

    def test_present_typed_missing_forecast_is_masked_not_dropped(self) -> None:
        with self._temporary() as td:
            fixture = CorpusFixture(Path(td))
            decision = (fixture.open_utc + 200) * NS
            missing_session = ForecastSegmentSnapshot(
                "SESSION", "MISSING", fixture.open_utc * NS, None, None,
                (None,) * 5, None, "NA", "MISSING", "1" * 64)
            missing_phase = ForecastSegmentSnapshot(
                "TOKYO", "MISSING", decision - NS, None, None,
                (None,) * 5, None, "NA", "MISSING", "2" * 64)
            fixture.forecasts = ExplicitForecastRows((ForecastRow(
                fixture.clear_id, "SI", fixture.d8, decision, 0,
                missing_session, missing_phase, "3" * 64), replace(
                    fixture.empty_forecast, session=missing_session,
                )))
            corpus = fixture.build()
            features = corpus.sessions[0].examples[0].causal_features
            self.assertEqual(features["session_forecast_present"], 0.0)
            self.assertEqual(features["phase_forecast_present"], 0.0)
            self.assertEqual(features["session_sigma_hat_usd"], 0.0)

    def test_production_qre2_missing_rows_are_verified_and_joined(self) -> None:
        with self._temporary() as td:
            root = Path(td)
            d8 = 20250102
            availability = 1_735_776_000 * NS
            rows: list[dict[str, str]] = []
            for segment in ("SESSION", "TOKYO", "LONDON", "NY"):
                row = {name: "NA" for name in _FORECAST_COLUMNS}
                row.update({
                    "asset": "SI", "d8": str(d8), "segment": segment,
                    "status": "MISSING", "missing_reason": "MIN_TRAIN",
                    "history_end_d8": "20250101",
                    "availability_ts_ns": str(availability),
                    "fit_month": "202501", "fit_end_range_d8": "20241231",
                    "fit_end_sigma_d8": "20241231", "n_train_range": "100",
                    "rank_range": "12", "n_train_sigma": "100",
                    "rank_sigma": "12", "n_sigma_calibration": "0",
                    "regime_tag": "NA",
                    "ladder_source": "MISSING", "n_calibration": "0",
                    "n_regime_calibration": "0",
                    "phase_profile_sha256": "4" * 64,
                    "model_sha256": "5" * 64,
                    "history_source_sha256": "6" * 64,
                    "lineage_sha256": "0" * 64,
                })
                row["lineage_sha256"] = _forecast_lineage(
                    row, QRE2_FORECAST_LAW_SHA256)
                rows.append(row)
            artifact = (
                f"# QRE2FORECAST4 start_d8=20250101 "
                f"end_d8_exclusive=20250104 asset=SI "
                f"law_sha256={QRE2_FORECAST_LAW_SHA256}\n"
                + "\t".join(_FORECAST_COLUMNS) + "\n"
                + "".join("\t".join(row[name] for name in _FORECAST_COLUMNS) + "\n"
                          for row in rows)
            ).encode()
            artifact_sha = _write(root / "forecast" / "SI.qrf4.tsv", artifact)
            lineage_sha = hashlib.sha256((
                "QRE2FORECASTLINEAGES4" + "".join(
                    f"|{row['lineage_sha256']}" for row in rows)).encode()).hexdigest()
            receipt_sha = _json(root / "forecast" / "SI.qrf4.json", {
                "schema": "QRE2FORECASTRECEIPT4", "asset": "SI",
                "start_d8": 20250101, "end_d8_exclusive": 20250104,
                "forecast_law_sha256": QRE2_FORECAST_LAW_SHA256,
                "sessions": 1, "rows": 4, "ready": 0, "missing": 4,
                "source_hashes": {"event_manifest_sha256": "7" * 64,
                                  "locks_sha256": "8" * 64,
                                  "phase_schedule_sha256": "9" * 64},
                "lineage_aggregate_sha256": lineage_sha,
                "output_sha256": artifact_sha,
                "evaluation": {
                    "schema": "QRE2FORECASTEVAL4", "rows": 4,
                    "valid_rows": 0, "output_sha256": "a" * 64,
                    "consumer_law": "diagnostics-only hindsight plane; live "
                                    "QRE2ForecastProvider must not open it",
                },
                "holdout_start_d8": C.HOLDOUT_START_D8,
                "final_exam_permit": False,
            })
            # The live provider consumes only the causal artifact and receipt;
            # the diagnostics-only hindsight sidecar deliberately does not
            # exist in this fixture.
            self.assertFalse((root / "forecast" / "SI.qrf4.eval.tsv").exists())
            provider = QRE2ForecastProvider((QRE2ForecastArtifactInput(
                root, "SI", artifact_sha, receipt_sha),))
            self.assertFalse((root / "forecast" / "SI.qrf4.eval.tsv").exists())
            joined = provider.forecast(ForecastQuery(
                "candidate", "SI", d8, availability + NS, 0))
            self.assertIsNotNone(joined)
            assert joined is not None
            joined.validate(ForecastQuery(
                "candidate", "SI", d8, availability + NS, 0))
            self.assertEqual(joined.session.status, "MISSING")

    def test_production_qre2_ready_prediction_with_typed_missing_ladder(self) -> None:
        with self._temporary() as td:
            root = Path(td)
            d8 = 20221003
            availability = 1_664_755_200 * NS
            rows: list[dict[str, str]] = []
            for segment in ("SESSION", "TOKYO", "LONDON", "NY"):
                row = {name: "NA" for name in _FORECAST_COLUMNS}
                row.update({
                    "asset": "SI", "d8": str(d8), "segment": segment,
                    "status": "READY", "missing_reason": "NONE",
                    "history_end_d8": "20220930",
                    "availability_ts_ns": str(availability),
                    "fit_month": "202210", "fit_end_range_d8": "20220930",
                    "fit_end_sigma_d8": "20220930", "n_train_range": "250",
                    "rank_range": "12", "n_train_sigma": "250",
                    "rank_sigma": "12", "rv1_usd": "1", "rv5_usd": "2",
                    "rv22_usd": "3", "prior_parkinson_usd": "4",
                    "prior_gk_usd": "5", "prior_rs_usd": "6",
                    "prior_jump_usd": "7", "sigma_raw_hat_usd": "500",
                    "sigma_persistence_usd": "500",
                    "sigma_calibration_ratio": "1",
                    "n_sigma_calibration": "20", "sigma_hat_usd": "500",
                    "range_hat_usd": "900", "rv5_over_rv66": "1.2",
                    "regime_cut_lo": "0.8", "regime_cut_hi": "1.1",
                    "regime_tag": "HIGH", "ladder_source": "MISSING",
                    "n_calibration": "0", "n_regime_calibration": "0",
                    "phase_profile_sha256": "4" * 64,
                    "model_sha256": "5" * 64,
                    "history_source_sha256": "6" * 64,
                    "lineage_sha256": "0" * 64,
                })
                row["lineage_sha256"] = _forecast_lineage(
                    row, QRE2_FORECAST_LAW_SHA256)
                rows.append(row)
            artifact = (
                f"# QRE2FORECAST4 start_d8=20221001 "
                f"end_d8_exclusive=20221004 asset=SI "
                f"law_sha256={QRE2_FORECAST_LAW_SHA256}\n"
                + "\t".join(_FORECAST_COLUMNS) + "\n"
                + "".join("\t".join(row[name] for name in _FORECAST_COLUMNS) + "\n"
                          for row in rows)
            ).encode()
            artifact_sha = _write(root / "forecast" / "SI.qrf4.tsv", artifact)
            lineage_sha = hashlib.sha256((
                "QRE2FORECASTLINEAGES4" + "".join(
                    f"|{row['lineage_sha256']}" for row in rows)).encode()).hexdigest()
            receipt_sha = _json(root / "forecast" / "SI.qrf4.json", {
                "schema": "QRE2FORECASTRECEIPT4", "asset": "SI",
                "start_d8": 20221001, "end_d8_exclusive": 20221004,
                "forecast_law_sha256": QRE2_FORECAST_LAW_SHA256,
                "sessions": 1, "rows": 4, "ready": 4, "missing": 0,
                "source_hashes": {"event_manifest_sha256": "7" * 64,
                                  "locks_sha256": "8" * 64,
                                  "phase_schedule_sha256": "9" * 64},
                "lineage_aggregate_sha256": lineage_sha,
                "output_sha256": artifact_sha,
                "evaluation": {
                    "schema": "QRE2FORECASTEVAL4", "rows": 4,
                    "valid_rows": 4, "output_sha256": "a" * 64,
                    "consumer_law": "diagnostics-only hindsight plane; live "
                                    "QRE2ForecastProvider must not open it",
                },
                "holdout_start_d8": C.HOLDOUT_START_D8,
                "final_exam_permit": False,
            })
            self.assertFalse((root / "forecast" / "SI.qrf4.eval.tsv").exists())
            provider = QRE2ForecastProvider((QRE2ForecastArtifactInput(
                root, "SI", artifact_sha, receipt_sha),))
            self.assertFalse((root / "forecast" / "SI.qrf4.eval.tsv").exists())
            query = ForecastQuery("candidate", "SI", d8, availability + NS, 0)
            joined = provider.forecast(query)
            self.assertIsNotNone(joined)
            assert joined is not None
            joined.validate(query)
            self.assertEqual(joined.session.status, "READY")
            self.assertEqual(joined.session.ladder_source, "MISSING")
            self.assertEqual(joined.session.move_usd, (None,) * 5)
            features, _ = _forecast_features(provider, query)
            self.assertEqual(features["session_forecast_present"], 1.0)
            self.assertEqual(features["session_sigma_hat_usd"], 500.0)
            self.assertEqual(features["session_range_hat_usd"], 900.0)
            self.assertEqual(features["session_move_ladder_present"], 0.0)
            self.assertEqual(features["session_unscaled_fallback_present"], 0.0)
            for quantile in ("q10", "q25", "q50", "q75", "q90"):
                self.assertEqual(features[f"session_move_{quantile}_usd"], 0.0)

    def test_forecast_vintage_dynamics_use_strictly_prior_history(self) -> None:
        def snapshot(value: float, regime: str) -> ForecastSegmentSnapshot:
            return ForecastSegmentSnapshot(
                segment="SESSION", status="READY",
                availability_ts_ns=int(value * NS),
                sigma_hat_usd=value, range_hat_usd=2.0 * value,
                move_usd=(.5 * value, .75 * value, value,
                          1.25 * value, 1.5 * value),
                rv5_over_rv66=value / 100.0, regime=regime,
                ladder_source="REGIME", lineage_sha256="a" * 64)
        history = (snapshot(100.0, "MID"), snapshot(110.0, "HIGH"))
        values = _forecast_vintage_features(snapshot(125.0, "HIGH"), history)
        self.assertEqual(values["vintage_sigma_delta_1_usd"], 15.0)
        self.assertEqual(values["vintage_sigma_acceleration_usd"], 5.0)
        self.assertGreater(values["vintage_sigma_slope_5_usd"], 0.0)
        self.assertEqual(values["vintage_regime_changed"], 0.0)
        self.assertEqual(values["vintage_regime_persistence"], 2.0)

    def test_teacher_permutation_missing_and_typed_refusal_are_distinguished(self) -> None:
        with self._temporary() as td:
            fixture = CorpusFixture(Path(td), teacher_mode="reverse")
            with self.assertRaisesRegex(C.EntryV2Refusal, "missing/permuted"):
                fixture.build()
        with self._temporary() as td:
            fixture = CorpusFixture(Path(td), teacher_mode="missing")
            with self.assertRaisesRegex(C.EntryV2Refusal, "missing/permuted"):
                fixture.build()
        with self._temporary() as td:
            fixture = CorpusFixture(Path(td), teacher_mode="refused")
            with self.assertRaisesRegex(C.EntryV2Refusal, "no CLEAR READY"):
                fixture.build()

    def test_h2_path_and_date_refuse_before_open(self) -> None:
        with self._temporary() as td:
            fixture = CorpusFixture(Path(td))
            with self.assertRaisesRegex(C.EntryV2Refusal, "2025H2 HOLDOUT"):
                AssetArtifactSet(
                    fixture.root / "20250701", "SI",
                    fixture.artifact.candidate_manifest_sha256,
                    fixture.artifact.teacher_manifest_sha256,
                    fixture.artifact.candidate_receipt_sha256,
                    fixture.artifact.teacher_receipt_sha256)
            with self.assertRaisesRegex(C.EntryV2Refusal, "2025H2 HOLDOUT"):
                missing = ForecastSegmentSnapshot(
                    "SESSION", "MISSING", NS, None, None, (None,) * 5,
                    None, "NA", "MISSING", "a" * 64)
                phase = ForecastSegmentSnapshot(
                    "TOKYO", "MISSING", NS, None, None, (None,) * 5,
                    None, "NA", "MISSING", "b" * 64)
                ForecastRow("x", "SI", 20250701, 2 * NS, 0, missing,
                            phase, "c" * 64).validate(
                                ForecastQuery("x", "SI", 20250701, 2 * NS, 0))


if __name__ == "__main__":
    unittest.main()
