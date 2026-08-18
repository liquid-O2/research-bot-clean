from __future__ import annotations

from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from engine.entry_v2 import common as C
from engine.entry_v2.neural_sufficiency_production import (
    ExactComponentExecution, ProductionDiagnosticBackends,
    NonSemanticTimingLedger, ProductionDiagnosticRefusal, derive_production_context,
    _current_process_identity_sha256, _validate_fit_only_rehearsal_gate,
)
from engine.entry_v2.neural_sufficiency_runner import (
    ACCEPTANCE_COMPONENTS, run_neural_sufficiency,
)
from engine.entry_v2.neural_sufficiency_stage_persistence import StageBoundaryStore
from engine.entry_v2.neural_sufficiency_source_manifest import (
    held_rehearsal_source_tree_sha256,
)
from engine.entry_v2.test_neural_sufficiency_runner import (
    _details, _held_economics,
)


def _fit_only_rehearsal() -> dict:
    paths = {f"{arm}:{head}": {"status": "ELIGIBLE"}
             for arm in ("C0", "C1", "L0", "L1", "M1")
             for head in ("direct_neural", "catboost")}
    goal_receipts = {
        f"{stage}.{role}.{asset}": "9" * 64
        for stage in ("E1r", "E2r")
        for role in ("THRESHOLD", "FORWARD")
        for asset in C.ASSETS
    }
    core = {
        "schema": "entry-v2-fit-only-held-rehearsal-v1", "status": "PASS",
        "held_launch_permitted": True,
        "minimum_oracle_capture": .8,
        "source_tree_sha256": held_rehearsal_source_tree_sha256(),
        "fit_only_max_d8": 20210930,
        "no_held_labels": True,
        "e1r": {"probe_screen": {"ledger": {
            f"probe-{index:02d}": {} for index in range(44)}}},
        "e2r": {"arm_head_matrix": {"matrix": paths,
            "winner": "M1:direct_neural",
            "diagnostic_path": "M1:direct_neural",
            "selected_objective": "C14P01",
            "selected_learner_objective": "C14P01"}},
        "g7": {"single_real_path": "M1:direct_neural",
               "selected_arm": "M1", "selected_head": "direct_neural",
               "selected_objective": "C14P01",
               "learner_law_sha256": "a" * 64,
               "e1r_checkpoint_sha256": "b" * 64,
               "e2r_checkpoint_sha256": "c" * 64,
               "e1r_fit_wall": 20210709, "e2r_fit_wall": 20210813,
               "same_full_learner_independent_fits": True,
               "all_asset_in_sample": True,
               "all_asset_disjoint_forward": True,
               "candidate_ceiling_all_blocks": True,
                   "minimum_oracle_capture": .8,
                   "goal_recovery_all_blocks": True,
                   "goal_recovery_receipts": goal_receipts,
                   "candidate_ceiling_receipts": {
                       "E1r.THRESHOLD": "1" * 64, "E1r.FORWARD": "2" * 64,
                       "E2r.THRESHOLD": "3" * 64, "E2r.FORWARD": "4" * 64},
                   "twins_counted": False},
    }
    receipt = hashlib.sha256(json.dumps(
        core, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    return {**core, "receipt_sha256": receipt}


class RecordingExecutor:
    def __init__(self): self.calls = []
    def _result(self, component):
        self.calls.append(component)
        details = dict(_details(component))
        if component == "catboost":
            details.update(
                pair_group_count_by_asset={asset: 40 for asset in C.ASSETS},
                pair_accuracy_by_asset={asset: 1.0 for asset in C.ASSETS},
                pair_row_manifest_sha256="7" * 64,
                pair_manifest_sha256_by_asset={
                    asset: "8" * 64 for asset in C.ASSETS},
            )
        if component == "finalize":
            details["held_rehearsal"] = _fit_only_rehearsal()
        return ExactComponentExecution(component, True, True, 20210930,
                                       "e" * 64, "f" * 64,
                                       details)
    def prepare(self): return self._result("one_load")
    def raw_fidelity(self): return self._result("raw_fidelity")
    def train_and_rehearse_arm(self, arm): return self._result(f"arm_{arm}")
    def run_atlas(self): return self._result("atlas_probe_loss")
    def run_direct_head(self): return self._result("direct_head")
    def run_catboost(self): return self._result("catboost")
    def fit_mapper(self): return self._result("mapper")
    def calibrate(self): return self._result("calibration")
    def select_threshold_with_canonical_sweep(self): return self._result("threshold")
    def run_canonical_replay(self): return self._result("canonical_replay")
    def validate_fit_ledger(self): return self._result("fit_ledger")
    def finalize(self): return self._result("finalize")
    def timing_provenance(self):
        return {"load_class": "cold", "warm_corpus_ready": False,
                "verified_session_durable_hit": 0,
                "verified_session_cold_publishes": 1,
                "verified_session_warm_hits": 0,
                "physical_full_pack_opens": 1,
                "model_array_physical_fills": 1,
                "header_revalidations": 0,
                "diagnostic_plane_bytes": 1,
                "truth_bytes_materialized": 1,
                "derived_bytes_materialized": 1,
                "truth_bytes_retained": 1,
                "derived_bytes_retained": 1}
    def execute_stage(self, mode, acceptance_sha256, prior_stage_sha256):
        maximum = {"E1": 20211231, "E2": 20220630, "E3": 20221230}[mode]
        details = {key: True for key in ("frozen_inputs", "frozen_objective",
                                         "frozen_thresholds", "canonical_replay",
                                         "no_h2_open")}
        details.update(acceptance_sha256=acceptance_sha256,
                       prior_stage_sha256=prior_stage_sha256)
        if mode in ("E2", "E3"):
            capacity_authority, held_economics = _held_economics()
            details.update(selected_arm_sha256="1" * 64,
                           selected_objective_sha256="2" * 64,
                           calibrator_sha256="3" * 64, thresholds_sha256="4" * 64,
                           capacity_authority_sha256=capacity_authority)
            details["economics"] = held_economics
        if mode == "E3": details.update(report_only=True, no_selection_mutation=True)
        return ExactComponentExecution(f"execute_{mode.lower()}", True, False,
                                       maximum, "e" * 64, "f" * 64, details)
    def close(self, adoption_sha256):
        self.calls.append("close")
        return ExactComponentExecution("close", True, False, 20221230,
                                       "e" * 64, "f" * 64,
                                       {"resources_closed": True,
                                        "adoption_sha256": adoption_sha256})


class NeuralSufficiencyProductionTest(unittest.TestCase):
    def test_fit_only_boundary_process_identity_changes_only_in_new_process(self):
        local = _current_process_identity_sha256()
        self.assertEqual(local, _current_process_identity_sha256())
        code = (
            "from engine.entry_v2.neural_sufficiency_production import "
            "_current_process_identity_sha256; "
            "print(_current_process_identity_sha256())"
        )
        child = subprocess.run(
            [sys.executable, "-c", code], cwd=C.REPO_ROOT,
            text=True, capture_output=True, timeout=30, check=True,
        ).stdout.strip()
        self.assertEqual(len(child), 64)
        self.assertNotEqual(local, child)

    def test_module_cli_uses_one_canonical_typed_class_identity(self):
        code = r'''
import runpy
import sys
import types

factory_module = types.ModuleType("entry_v2_identity_canary")
def factory(_run_root):
    canonical = sys.modules["engine.entry_v2.neural_sufficiency_production"]
    running = sys.modules["__main__"]
    assert canonical is running
    assert canonical.ExactComponentExecution is running.ExactComponentExecution
    raise SystemExit(0)
factory_module.factory = factory
sys.modules[factory_module.__name__] = factory_module
sys.argv = [
    "neural_sufficiency_production", "--run-root", "/tmp/unused-entry-v2",
    "--executor-factory", "entry_v2_identity_canary:factory",
    "--fit-only-rehearsal",
]
runpy.run_module(
    "engine.entry_v2.neural_sufficiency_production",
    run_name="__main__", alter_sys=True,
)
'''
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=C.REPO_ROOT,
            text=True, capture_output=True, timeout=30, check=False,
        )
        self.assertEqual(
            result.returncode, 0,
            msg=f"stdout={result.stdout}\nstderr={result.stderr}",
        )

    def test_timing_side_receipt_is_monotonic_nonsemantic_and_enforces_ceiling(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch(
                "engine.entry_v2.neural_sufficiency_production.time.monotonic_ns",
                side_effect=[1_000, 1_001, 1_201 * 1_000_000_000 + 1_000]):
            ledger = NonSemanticTimingLedger(Path(directory) / "timing")
            ledger.record("corpus_ready", provenance={"load_class": "cold"})
            with self.assertRaisesRegex(ProductionDiagnosticRefusal,
                                        "timing ceiling exceeded"):
                ledger.record("first_competence")
            receipts = sorted((Path(directory) / "timing").glob("*.json"))
            self.assertEqual(len(receipts), 2)
            self.assertEqual(json.loads(receipts[-1].read_text())["status"], "REFUSED")

    def test_fit_only_rehearsal_is_a_source_bound_launch_gate(self):
        rehearsal = _fit_only_rehearsal()
        with tempfile.TemporaryDirectory() as directory:
            component_root = Path(directory)
            path = component_root / "00.finalize.fixture.json"
            path.write_text(json.dumps(
                {"details": {"held_rehearsal": rehearsal}},
                sort_keys=True, separators=(",", ":")))
            self.assertEqual(
                _validate_fit_only_rehearsal_gate(component_root),
                (rehearsal["receipt_sha256"], "PASS"),
            )
            changed = dict(rehearsal); changed["source_tree_sha256"] = "f" * 64
            changed_core = dict(changed); changed_core.pop("receipt_sha256")
            changed["receipt_sha256"] = hashlib.sha256(json.dumps(
                changed_core, sort_keys=True, separators=(",", ":")
            ).encode()).hexdigest()
            path.write_text(json.dumps(
                {"details": {"held_rehearsal": changed}},
                sort_keys=True, separators=(",", ":")))
            with self.assertRaisesRegex(ProductionDiagnosticRefusal,
                                        "different source bytes"):
                _validate_fit_only_rehearsal_gate(component_root)

    def test_exact_executor_runs_dependency_order_and_persists_chain(self):
        context = derive_production_context(
            corpus_receipt={"semantic_identity_sha256": "c" * 64},
            chronology={"E1_fit_end": 20210930, "corpus_max_day": 20250630,
                        "opened_through_day": 20250630}, one_load_id="one-load-1",
            source_paths=("/verified/pre-h2",), available_host_gib=512,
        )
        executor = RecordingExecutor()
        with tempfile.TemporaryDirectory() as directory:
            backend = ProductionDiagnosticBackends(
                executor, artifact_root=Path(directory) / "components", context=context,
            )
            receipt = run_neural_sufficiency(
                "preheld-fit-only-acceptance", context, backend.callbacks(),
                output_path=Path(directory) / "acceptance.json", production=False,
            )
            self.assertEqual(tuple(executor.calls), ACCEPTANCE_COMPONENTS)
            files = sorted((Path(directory) / "components").glob("*.json"))
            self.assertEqual(len(files), len(ACCEPTANCE_COMPONENTS))
            self.assertEqual(files[0].stat().st_mode & 0o222, 0)
            self.assertEqual(receipt.status, "PASS")
            attempts = sorted((Path(directory) / "components" / "attempts").glob("*.json"))
            self.assertEqual(len(attempts), len(ACCEPTANCE_COMPONENTS))
            self.assertTrue(all(json.loads(path.read_text())["status"] == "STARTED"
                                for path in attempts))

    def test_refusal_persists_typed_failure_without_masking_error(self):
        context = derive_production_context(
            corpus_receipt={"semantic_identity_sha256": "c" * 64},
            chronology={"x": 1, "corpus_max_day": 20250630,
                        "opened_through_day": 20250630},
            one_load_id="one-load-1", source_paths=("/pre-h2",),
            available_host_gib=512,
        )
        executor = RecordingExecutor()
        executor.raw_fidelity = lambda: (_ for _ in ()).throw(
            RuntimeError("typed-canary"))
        with tempfile.TemporaryDirectory() as directory:
            backend = ProductionDiagnosticBackends(
                executor, artifact_root=directory, context=context)
            backend.callbacks()["one_load"](context)
            with self.assertRaisesRegex(RuntimeError, "typed-canary"):
                backend.callbacks()["raw_fidelity"](context)
            failures = list((Path(directory) / "failures").glob("*.json"))
            self.assertEqual(len(failures), 1)
            payload = json.loads(failures[0].read_text())
            self.assertEqual(payload["status"], "REFUSED")
            self.assertEqual(payload["component"], "raw_fidelity")
            self.assertEqual(payload["layer"], "ACCEPTANCE:raw_fidelity")
            self.assertEqual(payload["error_message"], "typed-canary")
            self.assertIsNone(payload["evidence_sha256"])
            self.assertIn("attempts/00.one_load.",
                          "\n".join(payload["outputs"]))
            self.assertEqual(payload["cache_recovery"],
                             "NO_UNRECEIPTED_PROCESS_CACHE_REUSE")

    def test_held_refusal_binds_predecision_evidence_and_blocks_adoption(self):
        context = derive_production_context(
            corpus_receipt={"semantic_identity_sha256": "c" * 64},
            chronology={"x": 1, "corpus_max_day": 20250630,
                        "opened_through_day": 20250630},
            one_load_id="one-load-1", source_paths=("/pre-h2",),
            available_host_gib=512,
        )
        executor = RecordingExecutor()
        directory = tempfile.mkdtemp(prefix="m7_production_", dir=C.CACHE_ROOT)
        try:
            root = Path(directory)
            backend = ProductionDiagnosticBackends(
                executor, artifact_root=root / "components", context=context)
            for component in ACCEPTANCE_COMPONENTS:
                backend.callbacks()[component](context)
            evidence_sha = StageBoundaryStore(
                root / "held-boundaries"
            ).publish_evidence("E1", {
                "outcome.json": json.dumps({
                    "schema": "entry-v2-e1-screen-outcome-v1",
                    "status": "HOLM_SELECTED_NONE",
                }, sort_keys=True, separators=(",", ":")).encode(),
            })
            error = RuntimeError("held-refusal-" + "x" * 3000)
            error.failure_layer = "E1:ENGINE"
            executor.execute_stage = lambda *_: (_ for _ in ()).throw(error)
            callback = backend.held_callback(
                "E1", acceptance_sha256="a" * 64,
                prior_stage_sha256="a" * 64,
            )["execute_e1"]
            with self.assertRaisesRegex(RuntimeError, "held-refusal"):
                callback(context)
            failures = list((root / "components" / "failures").glob("*.json"))
            self.assertEqual(len(failures), 1)
            payload = json.loads(failures[0].read_text())
            self.assertEqual(payload["layer"], "E1:ENGINE")
            self.assertEqual(payload["evidence_sha256"], evidence_sha)
            self.assertLessEqual(len(payload["error_message"].encode()), 2048)
            self.assertTrue(payload["error_message"])
            self.assertIn("held-boundaries/E1.evidence/evidence.json",
                          payload["outputs"])
            self.assertFalse((root / "winner-adoption.json").exists())
        finally:
            root = Path(directory)
            for path in sorted(root.rglob("*"), reverse=True):
                try:
                    path.chmod(0o755 if path.is_dir() else 0o644)
                except FileNotFoundError:
                    pass
            shutil.rmtree(root)

    def test_e3_economic_miss_report_survives_consumer_refusal(self):
        context = derive_production_context(
            corpus_receipt={"semantic_identity_sha256": "c" * 64},
            chronology={"x": 1, "corpus_max_day": 20250630,
                        "opened_through_day": 20250630},
            one_load_id="one-load-1", source_paths=("/pre-h2",),
            available_host_gib=512,
        )
        executor = RecordingExecutor()
        directory = tempfile.mkdtemp(prefix="m7_e3_report_", dir=C.CACHE_ROOT)
        try:
            root = Path(directory)
            backend = ProductionDiagnosticBackends(
                executor, artifact_root=root / "components", context=context)
            for component in ACCEPTANCE_COMPONENTS:
                backend.callbacks()[component](context)
            miss = ExactComponentExecution(
                "execute_e3", False, False, 20221230, "e" * 64, "f" * 64,
                {"report_only": True, "no_selection_mutation": True,
                 "economics_status": "FAIL", "failure_reasons": [
                     "USD_PER_ASSET_DAY_BELOW_ORACLE_REGIME_FLOOR"
                 ]},
            )
            executor.execute_stage = lambda *_: miss
            callback = backend.held_callback(
                "E3", acceptance_sha256="a" * 64,
                prior_stage_sha256="b" * 64,
            )["execute_e3"]
            with self.assertRaisesRegex(ProductionDiagnosticRefusal,
                                        "weak result"):
                callback(context)
            evidence = StageBoundaryStore(root / "held-boundaries").load_evidence("E3")
            report = json.loads(evidence.payloads["report.json"])
            self.assertEqual(report["status"], "REPORTED")
            self.assertIs(report["provider_passed"], False)
            self.assertEqual(report["details"]["economics_status"], "FAIL")
            failure_path = next((root / "components" / "failures").glob("*.json"))
            failure = json.loads(failure_path.read_text())
            self.assertEqual(failure["layer"], "E3:REPORT")
            self.assertEqual(failure["evidence_sha256"], evidence.evidence_sha256)
            self.assertFalse((root / "winner-adoption.json").exists())
        finally:
            root = Path(directory)
            for path in sorted(root.rglob("*"), reverse=True):
                try:
                    path.chmod(0o755 if path.is_dir() else 0o644)
                except FileNotFoundError:
                    pass
            shutil.rmtree(root)

    def test_out_of_order_or_generic_result_refuses(self):
        context = derive_production_context(
            corpus_receipt={"semantic_identity_sha256": "c" * 64},
            chronology={"x": 1, "corpus_max_day": 20250630,
                        "opened_through_day": 20250630},
            one_load_id="one-load-1", source_paths=("/pre-h2",),
            available_host_gib=512,
        )
        executor = RecordingExecutor()
        with tempfile.TemporaryDirectory() as directory:
            backend = ProductionDiagnosticBackends(executor, artifact_root=directory,
                                                   context=context)
            with self.assertRaisesRegex(ProductionDiagnosticRefusal, "expected one_load"):
                backend.callbacks()["raw_fidelity"](context)


if __name__ == "__main__":
    unittest.main()
