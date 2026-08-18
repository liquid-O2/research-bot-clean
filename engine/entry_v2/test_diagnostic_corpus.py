#!/usr/bin/env python3
"""File-backed one-open integration test for the diagnostic corpus bridge."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
import tempfile
import unittest
from unittest import mock

import numpy as np

from . import common as C
from .contracts import SessionRef
from .corpus import (
    CORPUS_WINDOW_LAW_SHA256, CORPUS_WINDOW_SCHEMA, EntryCorpus,
    _CorpusMergeProvenance,
)
from .causal_label_atlas import (
    CellAvailability, PNL_UNITS_PER_USD, PROBE_REGISTRY,
)
from .diagnostic_corpus import (
    DIAGNOSTIC_CORPUS_SCHEMA, LIFECYCLE_COLD,
    LIFECYCLE_PROVENANCE_RECEIPT_KEY, LIFECYCLE_PROVENANCE_SCHEMA,
    CORPUS_READY_MILESTONE_SOURCE, PRIOR_SCALE_CONVERSION_LAW,
    PRIOR_SCALE_CONVERSION_LAW_SHA256, _prior_scale_units_text,
    _selected_horizon_coverage_preflight,
    DiagnosticCorpusObserver, DiagnosticCorpusRefusal,
    finalize_diagnostic_corpus, load_durable_diagnostic_planes,
    merge_diagnostic_corpora,
)
from .durable_store import DurableEntryV2Store
from .diagnostic_inputs import ActionMaskReason
from .event_pack import (
    EVENT_DTYPE, HEADER, MAGIC, ROW_BYTES, VERSION, EventPack,
)
from .session_stream import (
    CUTOFF_RULE, SessionArrayCache, SessionEventSource,
)
from .teacher import TeacherPath, build_teacher_store


class DiagnosticCorpusIntegrationTest(unittest.TestCase):
    def test_selected_coverage_preflight_is_prefix_optional_suffix_exact(self) -> None:
        def spec(day: int, candidate_id: str):
            return SimpleNamespace(
                asset="HG", trading_day=day, session_id=f"HG:{day}",
                candidate_ids=(candidate_id,), selected_horizon_value=None,
                selected_horizon_valid=None,
                selected_horizon_schema_sha256=None,
            )

        prefix = spec(20210528, "early")
        suffix = spec(20210531, "fit")
        corpus = EntryCorpus(
            (prefix, suffix), None, None, None, None, (), {}, None,
            _CorpusMergeProvenance((), (), (), (), ()),
        )
        source = SimpleNamespace(receipt=SimpleNamespace(
            receipt_sha256="a" * 64))
        observed = (SimpleNamespace(
            key=("HG", 20210531), source=source,
            candidates=({"candidate_id": "fit"},),
        ),)
        binding = SimpleNamespace(
            candidate_id="fit", compliance_status="CLEAR",
            teacher_status="READY",
        )
        coverage = _selected_horizon_coverage_preflight(
            corpus, observed, {"fit": binding}, start_d8=20210531,
        )
        self.assertEqual(coverage["prefix_unattached_session_count"], 1)
        self.assertEqual(coverage["suffix_attached_session_count"], 1)

        with self.assertRaisesRegex(
                DiagnosticCorpusRefusal, "coverage preflight"):
            _selected_horizon_coverage_preflight(
                corpus, (), {"fit": binding}, start_d8=20210531,
            )

    def test_fractional_atr_prior_uses_conservative_decimal_ceiling(self) -> None:
        text = "1945.5357142857142"
        converted = _prior_scale_units_text(
            {"atr14_prev_usd": text}, "atr14_prev_usd"
        )
        exact = Decimal(text) * PNL_UNITS_PER_USD
        self.assertGreaterEqual(Decimal(converted), exact)
        self.assertLess(Decimal(converted) - exact, Decimal(1))
        self.assertEqual(
            _prior_scale_units_text(
                {"atr14_prev_usd": "100"}, "atr14_prev_usd"
            ),
            100 * PNL_UNITS_PER_USD,
        )
        for invalid in ("0", "-1", "NaN", "Infinity"):
            with self.subTest(invalid=invalid), self.assertRaises(
                    DiagnosticCorpusRefusal):
                _prior_scale_units_text(
                    {"atr14_prev_usd": invalid}, "atr14_prev_usd"
                )
        with self.assertRaisesRegex(
                DiagnosticCorpusRefusal, "original decimal text"):
            _prior_scale_units_text(
                {"atr14_prev_usd": np.float64(1.25)}, "atr14_prev_usd"
            )

    def test_finalized_window_merge_is_canonical_without_refinalizing_old(self) -> None:
        def corpus_part(minimum, maximum, token):
            receipt = {
                "receipt_sha256": token * 64,
                "corpus_window": {
                    "schema": CORPUS_WINDOW_SCHEMA,
                    "law_sha256": CORPUS_WINDOW_LAW_SHA256,
                    "minimum_d8_exclusive": minimum,
                    "maximum_d8": maximum,
                },
                "corpus_source_lineage_sha256": token * 64,
                "teacher_store_sha256": token * 64,
                "session_stream_receipt_aggregate_sha256": token * 64,
                "clock_law_receipt_sha256": token * 64,
                "model_arrays_conversion_law_sha256": token * 64,
            }
            return SimpleNamespace(
                receipt=receipt,
                model_input_binding=SimpleNamespace(binding_sha256=token * 64),
            )

        def diagnostic_part(corpus, day, token):
            source_receipt = token * 64
            validate = mock.Mock()
            observed = SimpleNamespace(
                source=SimpleNamespace(receipt=SimpleNamespace(
                    receipt_sha256=source_receipt)),
                receipt={
                    "receipt_sha256": (token.upper() if token.isalpha()
                                       else token) * 64,
                    "diagnostic_plane_sha256": token * 64,
                },
                validate_backing=validate,
            )
            row = SimpleNamespace(
                key=("SI", day), observed=observed, bindings=(),
                atlas=SimpleNamespace(receipt={
                    "receipt_sha256": token * 64,
                    "candidate_suffix_rows_visited": 0,
                }),
            )
            body = {
                "schema": DIAGNOSTIC_CORPUS_SCHEMA,
                "source_corpus_receipt_sha256": corpus.receipt["receipt_sha256"],
                "candidate_suffix_rows_visited": 0, "h2_permit": False,
                "truth_quality_index_count": 1,
                "physical_full_pack_opens": 1,
                "model_array_physical_fills": 1,
                "header_revalidations": 1, "array_cache_hits": 1,
                "diagnostic_plane_bytes": 10,
                "truth_bytes_materialized": 4,
                "derived_bytes_materialized": 3,
                "truth_bytes_retained": 4, "derived_bytes_retained": 3,
                "post_e3_session_count": 0, "compact_atlas_session_count": 1,
                "one_open_per_session": True,
                "diagnostic_planes_disk_backed": True,
                "durable_products_ready": True, "warm_corpus_ready": False,
                "truth_start_d8": day, "truth_end_d8": day,
                "derived_end_d8": day, "post_e3_truth_released": True,
                "selected_objective_target_provider_ready": True,
                "prior_scale_conversion_law": PRIOR_SCALE_CONVERSION_LAW,
                "prior_scale_conversion_law_sha256":
                    PRIOR_SCALE_CONVERSION_LAW_SHA256,
                "prior_scale_pnl_units_per_usd": PNL_UNITS_PER_USD,
            }
            body[LIFECYCLE_PROVENANCE_RECEIPT_KEY] = {
                "schema": LIFECYCLE_PROVENANCE_SCHEMA,
                "cold_or_warm": LIFECYCLE_COLD,
                "warm_corpus_ready": False,
                "physical_full_pack_opens": 1,
                "model_array_physical_fills": 1,
                "verified_session_durable_hits": 0,
                "verified_session_cold_publishes": 1,
                "diagnostic_plane_durable_hits": 0,
                "model_array_bytes_materialized": 1,
                "model_array_bytes_reused": 0,
                "diagnostic_plane_bytes_materialized": 10,
                "diagnostic_plane_bytes_reused": 0,
                "corpus_ready_elapsed_milestone_source":
                    CORPUS_READY_MILESTONE_SOURCE,
                "cumulative_window_identity_sha256": token * 64,
            }
            body["receipt_sha256"] = C.object_sha256(body)
            return SimpleNamespace(
                corpus=corpus, sessions=(row,), bindings=(),
                receipt=MappingProxyType(body), validate=validate,
            )

        first_corpus = corpus_part(None, 20211231, "a")
        second_corpus = corpus_part(20211231, 20220630, "b")
        first = diagnostic_part(first_corpus, 20211230, "1")
        second = diagnostic_part(second_corpus, 20220629, "2")
        chain_parts = [
            {"receipt_sha256": first_corpus.receipt["receipt_sha256"],
             "minimum_d8_exclusive": None, "maximum_d8": 20211231},
            {"receipt_sha256": second_corpus.receipt["receipt_sha256"],
             "minimum_d8_exclusive": 20211231, "maximum_d8": 20220630},
        ]
        merged_corpus = SimpleNamespace(
            receipt={
                "receipt_sha256": "c" * 64,
                "corpus_source_lineage_sha256": "c" * 64,
                "teacher_store_sha256": "c" * 64,
                "session_stream_receipt_aggregate_sha256": "c" * 64,
                "clock_law_receipt_sha256": "c" * 64,
                "model_arrays_conversion_law_sha256": "c" * 64,
                "corpus_window": {
                    "schema": CORPUS_WINDOW_SCHEMA,
                    "law_sha256": CORPUS_WINDOW_LAW_SHA256,
                    "maximum_d8": 20220630,
                    "window_chain": {"parts": chain_parts},
                },
            },
            model_input_binding=SimpleNamespace(binding_sha256="d" * 64),
            sessions=tuple(SimpleNamespace(source=row.observed.source)
                           for part in (first, second) for row in part.sessions),
        )
        merged = merge_diagnostic_corpora(
            merged_corpus, (first, second)
        )
        self.assertEqual(tuple(row.key[1] for row in merged.sessions),
                         (20211230, 20220629))
        self.assertEqual(merged.receipt["session_count"], 2)
        self.assertEqual(merged.receipt["physical_full_pack_opens"], 2)
        self.assertEqual(merged.receipt["candidate_suffix_rows_visited"], 0)
        self.assertEqual(first.validate.call_count, 1)
        self.assertEqual(second.validate.call_count, 1)
        wrong_corpus = SimpleNamespace(
            receipt={
                **merged_corpus.receipt,
                "corpus_window": {
                    "maximum_d8": 20220630,
                    "window_chain": {"parts": list(reversed(chain_parts))},
                },
            },
            model_input_binding=merged_corpus.model_input_binding,
            sessions=merged_corpus.sessions,
        )
        with self.assertRaisesRegex(DiagnosticCorpusRefusal, "binding differs"):
            merge_diagnostic_corpora(wrong_corpus, (first, second))

    D8 = 20250102
    IID = 7
    OPEN = 1_700_000_000
    CLOSE = OPEN + 10
    NS = 1_000_000_000

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(dir=C.CACHE_ROOT)
        root = Path(self._tmp.name) / "events" / "SI"
        root.mkdir(parents=True)
        self.path = (root / f"{self.D8}.qre2").resolve()
        rows = np.zeros(4, dtype=EVENT_DTYPE)
        rows["ts_recv_ns"] = (
            np.uint64(self.OPEN) * np.uint64(self.NS)
            + np.arange(1, 5, dtype=np.uint64) * np.uint64(self.NS)
        )
        rows["ts_event_ns"] = rows["ts_recv_ns"] - np.uint64(100)
        rows["price"] = [1_000_000_000, 1_000_000_000,
                         1_200_000_000, 1_200_000_000]
        rows["bid_px"] = [1_000_000_000, 1_000_000_000,
                          1_200_000_000, 1_200_000_000]
        rows["ask_px"] = [1_005_000_000, 1_005_000_000,
                          1_205_000_000, 1_205_000_000]
        rows["size"] = 2
        rows["bid_sz"] = 3
        rows["ask_sz"] = 4
        rows["bid_ct"] = 1
        rows["ask_ct"] = 1
        rows["sequence"] = np.arange(4, dtype=np.uint32)
        rows["receive_session_sec"] = [1, 2, 3, 4]
        rows["action"] = ord("A")
        rows["side"] = ord("B")
        self.rows = rows
        header = HEADER.pack(
            MAGIC, VERSION, C.ASSET_INDEX["SI"], self.D8, self.IID,
            self.OPEN, self.CLOSE, len(rows), ROW_BYTES, 0,
        )
        self.path.write_bytes(header + rows.tobytes())
        source_sha = C.file_sha256(self.path)
        descriptors = []
        for name in EVENT_DTYPE.names or ():
            dtype, offset = EVENT_DTYPE.fields[name][:2]
            descriptors.append({
                "name": name, "dtype": dtype.str.removeprefix("|"),
                "offset_bytes": int(offset),
            })
        sidecar = {
            "schema": "QRE2EVENTMETA2", "status": "READY", "asset": "SI",
            "asset_idx": C.ASSET_INDEX["SI"], "d8": self.D8,
            "record_window": {"start_d8": 20250101,
                              "end_d8_exclusive": 20250103},
            "locked_iid": self.IID, "selection_basis_d8": 20241231,
            "selection_basis_updates": 100, "selection_basis_symbol": "SIF5",
            "open_utc": self.OPEN, "close_utc": self.CLOSE,
            "event_count": len(rows), "event_pack_sha256": source_sha,
            "binary_file": f"events/SI/{self.D8}.qre2",
            "source_hashes": {
                "input_manifest_sha256": "1" * 64, "locks_sha256": "2" * 64,
                "phase_schedule_sha256": "3" * 64,
                "event_pack_sha256": source_sha,
            },
            "cutoff_rule": CUTOFF_RULE,
            "session_assignment_clock": "ts_recv",
            "symbology_date_clock": "floor_utc(ts_recv)",
            "causal_visibility_clock": "IndexTs/ts_recv",
            "exchange_feature_clock": "ts_event", "equal_receive_time": "future",
            "tie_order": "ordered_input_manifest_then_dbn_decode_ordinal",
            "binary_schema": {
                "magic": "QRE2EVT2", "byte_order": "little",
                "header_bytes": 60, "row_bytes": 76,
                "layout": "packed_array_of_structs", "arrays": descriptors,
            },
        }
        sidecar_path = self.path.with_suffix(".qre2.json")
        sidecar_bytes = (json.dumps(sidecar, sort_keys=True,
                                    separators=(",", ":")) + "\n").encode()
        sidecar_path.write_bytes(sidecar_bytes)
        stat = self.path.stat()
        self.cache = SessionArrayCache(1 << 20)
        self.source = SessionEventSource(
            self.path, source_sha, hashlib.sha256(sidecar_bytes).hexdigest(),
            "SI", self.D8, self.IID, self.OPEN, self.CLOSE, len(rows), 3,
            stat.st_size, stat.st_dev, stat.st_ino, stat.st_mtime_ns,
            stat.st_ctime_ns, self.cache,
        )
        self.candidates = (
            self._candidate("a", self.OPEN + 3, 2, 1),
            self._candidate("b", self.OPEN + 3, 2, 1),
            self._candidate("c", self.OPEN + 4, 3, 2),
        )
        self.candidates[1]["sane_ceiling_usd"] = "300"
        self.teachers = (
            self._teacher("a", self.OPEN + 3, "1000", "1000", "0", 1),
            self._teacher("b", self.OPEN + 3, "1000", "1000", "0", 1),
            self._teacher("c", self.OPEN + 4, "0", "0", "0", 0),
        )
        paths = (
            TeacherPath("a", "SI", self.D8, (self.OPEN + 3) * self.NS,
                        (self.OPEN + 4) * self.NS, 1000.0, 1000.0, 0.0, False, 1.0),
            TeacherPath("b", "SI", self.D8, (self.OPEN + 3) * self.NS,
                        (self.OPEN + 4) * self.NS, 1000.0, 1000.0, 0.0, False, 1.0),
            TeacherPath("c", "SI", self.D8, (self.OPEN + 4) * self.NS,
                        (self.OPEN + 4) * self.NS, 0.0, 0.0, 0.0, False, 0.0),
        )
        self.teacher_store = build_teacher_store(
            paths, expected_sessions=(SessionRef("SI", self.D8, "tiny"),)
        )

    def tearDown(self) -> None:
        self.cache.clear()
        self._tmp.cleanup()

    def _candidate(self, cid: str, decision_sec: int, cutoff: int,
                   entry_row: int) -> dict[str, str]:
        row = self.rows[entry_row]
        return {
            "candidate_id": cid, "asset": "SI", "d8": str(self.D8),
            "decision_ts_ns": str(decision_sec * self.NS),
            "event_cutoff": str(cutoff),
            "prefix_last_event_ordinal": str(cutoff - 1), "phase": "0",
            "phase_open_utc": str(self.OPEN),
            "phase_close_utc": str(self.OPEN + 5), "side": "1",
            "entry_bid_px": str(int(row["bid_px"])),
            "entry_ask_px": str(int(row["ask_px"])),
            "entry_mid2": str(int(row["bid_px"]) + int(row["ask_px"])),
            "frozen_cost_usd": "0", "sane_ceiling_usd": "250",
            "atr14_prev_usd": "100", "compliance_status": "CLEAR",
        }

    def _teacher(self, cid: str, decision_sec: int, cert: str, mfe: str,
                 mae: str, payer: int) -> dict[str, str]:
        return {
            "candidate_id": cid, "asset": "SI", "d8": str(self.D8),
            "decision_ts_ns": str(decision_sec * self.NS),
            "status": "READY", "cert_close_usd": cert, "mfe_usd": mfe,
            "mae_usd": mae, "exit_ts_ns": str((self.OPEN + 4) * self.NS),
            "wall_hit": "0", "payer": str(payer), "take_target": "1",
        }

    def test_one_authoritative_open_global_schedule_and_atlas_receipts(self) -> None:
        plane_dir = Path(self._tmp.name) / "diagnostic-planes"
        observer = DiagnosticCorpusObserver(
            "SI", start_d8=self.D8, end_d8_inclusive=self.D8,
            backing_dir=plane_dir,
        )
        with EventPack(self.path, verify_hash=True) as pack:
            mapped = pack.rows._mmap
            self.assertTrue(self.source.publish_from_open_pack(pack))
            self.assertEqual(len(self.cache), 1)
            with mock.patch.object(
                SessionEventSource, "_open_verified_pack",
                side_effect=AssertionError("second physical pack open"),
            ):
                observer.observe_session(
                    source=self.source, pack=pack,
                    candidates=self.candidates, teachers=self.teachers,
                )
            observed = observer.sessions[0]
            self.assertEqual(observed.receipt["physical_full_pack_opens"], 1)
            self.assertEqual(observed.receipt["model_array_physical_fills"], 1)
            self.assertEqual(observed.receipt["header_revalidations"], 1)
            self.assertEqual(observed.receipt["array_cache_hits"], 1)
            self.assertTrue(observed.receipt["one_open_measured"])
            self.assertTrue(observed.receipt["diagnostic_plane_disk_backed"])
            self.assertGreater(observed.receipt["diagnostic_plane_bytes"], 0)
            self.assertIsNotNone(observed.backing)
            self.assertTrue(np.shares_memory(
                observed.truth["ts_recv_ns"], observed.backing.mapping))
            self.assertFalse(observed.truth["ts_recv_ns"].flags.writeable)
            self.assertFalse(any(np.shares_memory(value, pack.rows)
                                 for value in observed.truth.all_arrays()))
        self.assertTrue(mapped.closed)

        observers = {
            "SI": observer,
            "HG": DiagnosticCorpusObserver(
                "HG", start_d8=self.D8, end_d8_inclusive=self.D8),
            "NKD": DiagnosticCorpusObserver(
                "NKD", start_d8=self.D8, end_d8_inclusive=self.D8),
        }
        corpus = SimpleNamespace(
            teacher=self.teacher_store,
            sessions=(SimpleNamespace(source=self.source),),
            receipt={
                "receipt_sha256": "c" * 64,
                "corpus_source_lineage_sha256": "c" * 64,
                "teacher_store_sha256": self.teacher_store.store_hash,
                "session_stream_receipt_aggregate_sha256": "e" * 64,
                "clock_law_receipt_sha256": "f" * 64,
                "model_arrays_conversion_law_sha256": "1" * 64,
                "corpus_window": {
                    "schema": CORPUS_WINDOW_SCHEMA,
                    "law_sha256": CORPUS_WINDOW_LAW_SHA256,
                    "maximum_d8": C.DEVELOPMENT_END_D8,
                },
            },
            model_input_binding=SimpleNamespace(binding_sha256="d" * 64),
        )
        final = finalize_diagnostic_corpus(corpus, observers)
        by_id = {row.candidate_id: row for row in final.bindings}
        self.assertTrue(by_id["a"].action_target)
        self.assertEqual(by_id["a"].action_mask_reason,
                         ActionMaskReason.AVAILABLE_EXACT_TIME)
        self.assertFalse(by_id["b"].action_target)
        self.assertTrue(by_id["b"].action_loss_mask)
        self.assertEqual(by_id["c"].action_mask_reason,
                         ActionMaskReason.OCCUPANCY)
        for cid in by_id:
            label = self.teacher_store[cid]
            self.assertEqual((by_id[cid].action_target, by_id[cid].action_loss_mask),
                             (label.take_target, label.action_loss_mask))
        self.assertEqual(final.receipt["candidate_suffix_rows_visited"], 0)
        self.assertEqual(final.receipt["truth_quality_index_count"], 2)
        self.assertEqual(final.sessions[0].atlas.receipt["truth_quality_key_count"], 2)
        self.assertEqual(final.sessions[0].atlas.candidate_ids, ("a", "b", "c"))
        self.assertEqual(final.receipt["source_model_input_binding_sha256"], "d" * 64)
        self.assertEqual(final.receipt["corpus_maximum_d8"],
                         C.DEVELOPMENT_END_D8)
        self.assertFalse(final.receipt["full_outcome_mmap_retained"])
        self.assertFalse(final.receipt["h2_permit"])
        self.assertFalse(final.receipt["warm_corpus_ready"])
        self.assertTrue(final.receipt["one_open_per_session"])
        self.assertEqual(final.receipt["physical_full_pack_opens"], 1)
        self.assertEqual(final.receipt["model_array_physical_fills"], 1)
        lifecycle = final.receipt[LIFECYCLE_PROVENANCE_RECEIPT_KEY]
        self.assertEqual(lifecycle["cold_or_warm"], LIFECYCLE_COLD)
        self.assertFalse(lifecycle["warm_corpus_ready"])
        self.assertEqual(lifecycle["physical_full_pack_opens"], 1)
        self.assertEqual(lifecycle["model_array_physical_fills"], 1)
        self.assertEqual(len(lifecycle["cumulative_window_identity_sha256"]), 64)
        self.assertTrue(final.receipt["diagnostic_planes_disk_backed"])
        self.assertGreater(final.receipt["diagnostic_plane_bytes"], 0)
        self.assertEqual(final.receipt["source_receipt_union"],
                         [self.source.receipt.receipt_sha256])
        self.assertFalse((plane_dir / f"{self.D8}.planes").exists())
        atlas = final.sessions[0].atlas
        self.assertIsNotNone(atlas.atoms["now_wait_pass_regret_units"][0])
        self.assertIsNotNone(atlas.atoms["shadow_marginal_regret_units"][1])
        self.assertIsNone(atlas.atoms["now_wait_pass_regret_units"][2])
        for cell in (16, 17):
            target = atlas.materialize_probe(
                next(spec for spec in PROBE_REGISTRY if spec.cell == cell)
            )
            self.assertIs(target.state, CellAvailability.MATERIALIZED)
            self.assertEqual(target.validity_mask.tolist(), [True, True, False])
        self.cache.clear()
        observer.close()
        with self.assertRaisesRegex(C.EntryV2Refusal, "second physical full-pack"):
            with self.source.open_arrays():
                pass

    def test_unrelated_shared_cache_growth_and_duplicate_conflicts(self) -> None:
        """A sibling publication cannot invalidate this source-local hit."""
        observer = DiagnosticCorpusObserver(
            "SI", start_d8=self.D8, end_d8_inclusive=self.D8,
        )
        # A distinct receipt key in the same shared cache stands in for a
        # sibling asset lane.  Publish it while this source is performing its
        # own header-verified hit: the global cache cardinality must be
        # irrelevant to the observer's one-open proof.
        sibling = replace(self.source, max_cutoff=2)
        with EventPack(self.path, verify_hash=True) as pack:
            self.assertTrue(self.source.publish_from_open_pack(pack))
            original = SessionEventSource._verify_cached_header
            sibling_published = False

            def interleave(current: SessionEventSource) -> None:
                nonlocal sibling_published
                if current is self.source and not sibling_published:
                    sibling_published = True
                    self.assertTrue(sibling.publish_from_open_pack(pack))
                original(current)

            with mock.patch.object(
                    SessionEventSource, "_verify_cached_header",
                    autospec=True, side_effect=interleave):
                observer.observe_session(
                    source=self.source, pack=pack,
                    candidates=self.candidates, teachers=self.teachers,
                )

            self.assertTrue(sibling_published)
            self.assertEqual(len(self.cache), 2)
            measured = dict(self.source.measurements.snapshot())
            self.assertEqual(measured, {
                "physical_full_pack_opens": 1,
                "model_array_physical_fills": 1,
                "header_revalidations": 1,
                "array_cache_hits": 1,
                "single_full_open_required": True,
            })
            self.assertEqual(dict(sibling.measurements.snapshot()), {
                "physical_full_pack_opens": 1,
                "model_array_physical_fills": 1,
                "header_revalidations": 0,
                "array_cache_hits": 0,
                "single_full_open_required": False,
            })
            receipt_before = dict(observer.sessions[0].receipt)

            with self.assertRaisesRegex(
                    DiagnosticCorpusRefusal, "callback is duplicated exactly"):
                observer.observe_session(
                    source=self.source, pack=pack,
                    candidates=self.candidates, teachers=self.teachers,
                )
            changed_candidates = tuple(dict(row) for row in self.candidates)
            changed_candidates[0]["sane_ceiling_usd"] = "251"
            with self.assertRaisesRegex(
                    DiagnosticCorpusRefusal, "payload conflicts"):
                observer.observe_session(
                    source=self.source, pack=pack,
                    candidates=changed_candidates, teachers=self.teachers,
                )
            with self.assertRaisesRegex(
                    DiagnosticCorpusRefusal, "source identity conflicts"):
                observer.observe_session(
                    source=sibling, pack=pack,
                    candidates=self.candidates, teachers=self.teachers,
                )

            self.assertEqual(dict(self.source.measurements.snapshot()), measured)
            self.assertEqual(dict(observer.sessions[0].receipt), receipt_before)

    def test_durable_plane_reopens_semantic_truth_without_qre2(self) -> None:
        store_root = Path(self._tmp.name) / "durable-products"
        store = DurableEntryV2Store(store_root)
        cache = SessionArrayCache(1 << 20, durable_store=store)
        source = replace(self.source, array_cache=cache)
        observer = DiagnosticCorpusObserver(
            "SI", start_d8=self.D8, end_d8_inclusive=self.D8,
            durable_store=store,
        )
        with EventPack(self.path, verify_hash=True) as pack:
            self.assertTrue(source.publish_from_open_pack(pack))
            observer.observe_session(
                source=source, pack=pack, candidates=self.candidates,
                teachers=self.teachers,
            )
            expected = {
                name: value.copy()
                for name, value in observer.sessions[0].truth.columns.items()
            }
        self.assertFalse(
            observer.sessions[0].receipt["diagnostic_plane_durable_hit"])
        observer.close()
        cache.close()
        self.assertEqual(len(tuple(
            (store_root / "diagnostic-planes").iterdir())), 2)

        reopened = DurableEntryV2Store(store_root)
        with mock.patch.object(EventPack, "__init__", autospec=True,
                               side_effect=AssertionError("QRE2 opened")):
            loaded = load_durable_diagnostic_planes(
                reopened, source, self.candidates, self.teachers,
                include_derived=True,
            )
        self.assertIsNotNone(loaded)
        assert loaded is not None
        truth, derived, backing = loaded
        self.assertIsNotNone(derived)
        for name, value in expected.items():
            np.testing.assert_array_equal(truth.columns[name], value)
        backing.close()
        self.assertTrue(store_root.exists())


if __name__ == "__main__":
    unittest.main()
