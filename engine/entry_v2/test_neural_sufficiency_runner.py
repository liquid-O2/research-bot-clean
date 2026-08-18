from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from engine.entry_v2.capacity_contract import (
    SCHEMA as CAPACITY_SCHEMA, capacity_eligibility,
)
from engine.entry_v2.neural_sufficiency_runner import (
    ACCEPTANCE_COMPONENTS, GateEvidence, NeuralSufficiencyRefusal, RunContext,
    RunnerMode, adopt_e3_winner, capacity_regime_from_oracle,
    load_acceptance_receipt, run_neural_sufficiency,
)


SHA = "a" * 64
MANIFEST = "b" * 64
POLICY_MANIFEST = "e" * 64


def _held_economics() -> tuple[str, dict[str, dict[str, object]]]:
    rows = {
        asset: {
            "capacity_regime": "FULL",
            "included_trading_days": 20,
            "total_pnl_usd": 42_000.0,
            "trades": 60,
            "usd_per_trade": 700.0,
            "usd_per_asset_day": 2_100.0,
            "chronological_max_drawdown_usd": 450.0,
            "drawdown_p90_usd": 100.0,
            "replay_receipt_sha256": "9" * 64,
            "oracle_total_pnl_usd": 50_000.0,
            "oracle_usd_per_asset_day": 2_500.0,
            "oracle_capture": 0.84,
            "oracle_replay_receipt_sha256": "a" * 64,
            "asset_day_denominator": "included_trading_days",
            "values_clipped": False,
            "days_with_trades": 10,
        }
        for asset in ("HG", "NKD", "SI")
    }
    for row in rows.values():
        eligibility = capacity_eligibility(row)
        row.update({"threshold_feasibility_sha256":
                    eligibility.threshold_feasibility_sha256,
                    "capacity_eligibility_sha256": eligibility.receipt_sha256,
                    "eligibility": "ELIGIBLE"})
    document = {
        "schema": CAPACITY_SCHEMA,
        "values_clipped": False,
        "asset_day_denominator": "included_trading_days",
        "per_asset": rows,
    }
    authority = hashlib.sha256(json.dumps(
        document, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()
    return authority, {
        asset: {**row, "capacity_authority_sha256": authority}
        for asset, row in rows.items()
    }


def _context(day: int = 20210930, available: float = 512.0) -> RunContext:
    return RunContext(day, day, ("/verified/pre-h2/source",), available,
                      "c" * 64, "d" * 64, "one-load-1")


def _details(name: str) -> dict[str, object]:
    common = {"candidate_manifest_sha256": POLICY_MANIFEST}
    if name == "one_load":
        return {"one_corpus_build": True, "one_session_cache": True,
                "disk_backed_session_cache": True,
                "effective_memory_available_bytes": 256 * 1024 ** 3,
                "array_cache_capacity_bytes": 192 * 1024 ** 3,
                "four_worker_preload": True, "sequential_gpu": True,
                "catboost_not_overlapped": True, "atomic_boundaries": True,
                "one_load_id": "one-load-1", "h2_open_count": 0,
                "candidate_suffix_rows_visited": 0}
    if name == "raw_fidelity":
        return {key: True for key in (
            "left_searchsorted", "equal_time_excluded", "prefix_hashes_exact",
            "all_21_raw_fields", "before_equal_after_pack", "causal_oracle_pass",
            "raw_summary_learner_pass", "initial_book_trust_exact",
            "snapshot_seed_exact", "adjacent_phase_exact")}
    if name.startswith("arm_"):
        value = {key: True for key in (
            "all_routes_gradient", "suffix_bit_identical", "reconstruction_pass",
            "balanced_oracle_overfit", "shared_head_exact", "real_fit_only_rehearsal",
            "time_band_routing", "no_retrain_occlusion")}
        value.update(continuous_mae=.0001, categorical_accuracy=1.0,
                     minimum_auroc=.999, minimum_ap=.999, maximum_bce=.01,
                     assets=["HG", "NKD", "SI"])
        return value
    if name == "atlas_probe_loss":
        return {"all_44_registered": True, "all_losses_numeric_gradient": True,
                "real_beyond_recipient_fixed_twin": True, "support_typed": True,
                "materialization_end_to_end": True, "registered_e1_slots": 90,
                "maximum_through_e2": 98}
    if name == "direct_head":
        return {"candidate_manifest_sha256": MANIFEST,
                "balanced_oracle_overfit": True, "every_head_gradient": True,
                "identical_representation": True, "representation_sha256": SHA}
    if name == "catboost":
        return {"candidate_manifest_sha256": MANIFEST,
                "balanced_oracle_overfit": True,
                "singleton_action_classifier": True,
                "pairlogit_group_semantics": "asset-day-phase",
                "equal_timestamp_claim": False, "deterministic_cpu": True,
                "pair_group_count_by_asset": {asset: 44
                    for asset in ("HG", "NKD", "SI")},
                "pair_accuracy_by_asset": {asset: 1.0
                    for asset in ("HG", "NKD", "SI")},
                "pair_manifest_sha256_by_asset": {asset: SHA
                    for asset in ("HG", "NKD", "SI")},
                "pair_row_manifest_sha256": SHA,
                "representation_sha256": SHA}
    if name == "mapper":
        return {**common, "a004_mask_exact": True, "fit_only": True,
                "positive_skill": True, "row_ids": ["f1", "f2"]}
    if name == "calibration":
        return {**common, "positive_slope": True, "chronological": True,
                "fit_disjoint": True, "row_ids": ["c1", "c2"]}
    if name == "threshold":
        return {**common, "chronological": True, "calibration_disjoint": True,
                "no_held_labels": True, "canonical_fast_sweep": True,
                "selected_threshold_parity": True, "row_ids": ["t1", "t2"]}
    if name == "canonical_replay":
        return {**common, **{key: True for key in (
            "canonical_parity", "equal_time_ties", "occupancy_caps_cost_wall",
            "full_denominator", "mdd_exact", "fit_only_end_to_end",
            "teacher_isolation_exact")}}
    if name == "fit_ledger":
        return {"all_fits_counted": True, "competence_separate": True,
                "e1_registered_slots": 90, "through_e2_optimizer_fits": 90,
                "discarded_competence_fits": 12}
    if name == "finalize":
        paths = {f"{arm}:{head}": {"status": "ELIGIBLE"}
                 for arm in ("C0", "C1", "L0", "L1", "M1")
                 for head in ("direct_neural", "catboost")}
        goal_receipts = {
            f"{stage}.{role}.{asset}": SHA
            for stage in ("E1r", "E2r")
            for role in ("THRESHOLD", "FORWARD")
            for asset in ("HG", "NKD", "SI")
        }
        return {"all_components_complete": True, "fit_only_boundary_frozen": True,
                "one_load_retained_for_held": True,
                "immutable_chain_complete": True,
                "restart_payload_complete": True,
                "restartable_boundaries": False,
                "m8_reload_proof_sha256": None,
                "one_load_id": "one-load-1", "held_rehearsal": {
                    "schema": "entry-v2-fit-only-held-rehearsal-v1",
                    "status": "PASS", "source_tree_sha256": SHA,
                    "held_launch_permitted": True,
                    "minimum_oracle_capture": .8,
                    "fit_only_max_d8": 20210930, "no_held_labels": True,
                    "e1r": {"receipt": SHA, "probe_screen": {"ledger": {
                        f"probe-{index:02d}": {} for index in range(44)}}},
                    "e2r": {"receipt": SHA, "arm_head_matrix": {
                        "matrix": paths, "winner": "M1:direct_neural",
                        "diagnostic_path": "M1:direct_neural",
                        "selected_objective": "C14P01",
                        "selected_learner_objective": "C14P01"}},
                    "g7": {"single_real_path": "M1:direct_neural",
                        "selected_arm": "M1", "selected_head": "direct_neural",
                        "selected_objective": "C14P01",
                        "learner_law_sha256": SHA,
                        "e1r_checkpoint_sha256": "1" * 64,
                        "e2r_checkpoint_sha256": "2" * 64,
                        "e1r_fit_wall": 20210709,
                        "e2r_fit_wall": 20210813,
                        "same_full_learner_independent_fits": True,
                        "all_asset_in_sample": True,
                        "all_asset_disjoint_forward": True,
                        "candidate_ceiling_all_blocks": True,
                        "minimum_oracle_capture": .8,
                        "goal_recovery_all_blocks": True,
                        "goal_recovery_receipts": goal_receipts,
                        "candidate_ceiling_receipts": {
                            "E1r.THRESHOLD": SHA, "E1r.FORWARD": SHA,
                            "E2r.THRESHOLD": SHA, "E2r.FORWARD": SHA},
                        "twins_counted": False},
                    "receipt_sha256": SHA}}
    raise AssertionError(name)


def _backend(name: str, *, details: dict[str, object] | None = None,
             exact: bool = True, fit_only: bool = True):
    def callback(_context: RunContext) -> GateEvidence:
        payload = dict(_details(name) if details is None else details)
        payload["_visible_max_day"] = 20210930
        payload["_frozen_row_manifest_sha256"] = "f" * 64
        return GateEvidence(name, True, exact, fit_only, 20210930, SHA,
                            payload)
    callback.__name__ = f"test_{name}"
    return callback


def _acceptance_backends():
    return {name: _backend(name) for name in ACCEPTANCE_COMPONENTS}


class NeuralSufficiencyRunnerTest(unittest.TestCase):
    def _accept(self, directory: str):
        path = Path(directory) / "acceptance.json"
        receipt = run_neural_sufficiency(
            RunnerMode.PREHELD_FIT_ONLY_ACCEPTANCE, _context(),
            _acceptance_backends(), output_path=path,
        )
        return path, receipt

    def test_complete_fit_only_acceptance_is_atomic_and_immutable(self):
        with tempfile.TemporaryDirectory() as directory:
            path, receipt = self._accept(directory)
            self.assertEqual(receipt.status, "PASS")
            self.assertEqual(load_acceptance_receipt(path).acceptance_sha256,
                             receipt.acceptance_sha256)
            self.assertEqual(path.stat().st_mode & 0o222, 0)
            with self.assertRaises(NeuralSufficiencyRefusal):
                run_neural_sufficiency(
                    RunnerMode.PREHELD_FIT_ONLY_ACCEPTANCE, _context(),
                    _acceptance_backends(), output_path=path,
                )
            path.chmod(0o644)
            with self.assertRaisesRegex(NeuralSufficiencyRefusal, "mutable"):
                load_acceptance_receipt(path)

    def test_complete_negative_diagnostic_is_persisted_but_cannot_authorize_held(self):
        with tempfile.TemporaryDirectory() as directory:
            details = _details("finalize")
            rehearsal = dict(details["held_rehearsal"])
            rehearsal.update(
                status="NO_FIT_ONLY_DEPLOYABLE_DEPTH",
                held_launch_permitted=False,
            )
            rehearsal["g7"] = {
                **rehearsal["g7"],
                "all_asset_in_sample": False,
                "all_asset_disjoint_forward": False,
            }
            details["held_rehearsal"] = rehearsal
            backends = _acceptance_backends()
            backends["finalize"] = _backend("finalize", details=details)
            path = Path(directory) / "negative.json"
            receipt = run_neural_sufficiency(
                RunnerMode.PREHELD_FIT_ONLY_ACCEPTANCE, _context(), backends,
                output_path=path)
            self.assertEqual(receipt.status, "NO_FIT_ONLY_DEPLOYABLE_DEPTH")
            with self.assertRaises(NeuralSufficiencyRefusal):
                load_acceptance_receipt(path)
            self.assertEqual(
                load_acceptance_receipt(
                    path, allow_diagnostic_fail=True).acceptance_sha256,
                receipt.acceptance_sha256)

    def test_weak_or_cross_representation_evidence_cannot_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            backends = _acceptance_backends()
            backends["raw_fidelity"] = lambda _context: {"passed": True}  # type: ignore[assignment]
            with self.assertRaisesRegex(NeuralSufficiencyRefusal, "weak substitute"):
                run_neural_sufficiency("preheld-fit-only-acceptance", _context(), backends,
                                       output_path=Path(directory) / "weak.json")
            backends = _acceptance_backends()
            bad = _details("catboost"); bad["representation_sha256"] = "e" * 64
            backends["catboost"] = _backend("catboost", details=bad)
            with self.assertRaisesRegex(NeuralSufficiencyRefusal, "identical representations"):
                run_neural_sufficiency("preheld-fit-only-acceptance", _context(), backends,
                                       output_path=Path(directory) / "cross.json")

    def test_held_stage_hard_blocks_without_acceptance_then_runs_frozen(self):
        called = []
        def execute(context: RunContext) -> GateEvidence:
            called.append(context.observed_max_day)
            details = {key: True for key in ("frozen_inputs", "frozen_objective",
                                             "frozen_thresholds", "canonical_replay",
                                             "no_h2_open")}
            details.update(acceptance_sha256=acceptance.acceptance_sha256,
                           _visible_max_day=20211231,
                           _frozen_row_manifest_sha256="f" * 64)
            return GateEvidence(
                "execute_e1", True, True, False, 20211231, SHA,
                details,
            )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(NeuralSufficiencyRefusal, "requires fit-only acceptance"):
                run_neural_sufficiency("E1", _context(20211231), {"execute_e1": execute},
                                       output_path=Path(directory) / "e1.json")
            self.assertEqual(called, [])
            acceptance_path, acceptance = self._accept(directory)
            stage = run_neural_sufficiency(
                "E1", _context(20211231), {"execute_e1": execute},
                output_path=Path(directory) / "e1.json",
                acceptance_receipt_path=acceptance_path,
            )
            self.assertEqual(stage.status, "PASS")
            self.assertEqual(called, [20211231])

    def test_e3_is_report_only_and_memory_h2_guards_precede_callbacks(self):
        with tempfile.TemporaryDirectory() as directory:
            acceptance_path, acceptance = self._accept(directory)
            calls = []
            capacity_authority, held_economics = _held_economics()
            def stage_callback(component, maximum_day, *, prior_sha=None, selection=False):
                def execute(_context: RunContext) -> GateEvidence:
                    details = {key: True for key in (
                        "frozen_inputs", "frozen_objective", "frozen_thresholds",
                        "canonical_replay", "no_h2_open")}
                    details.update(acceptance_sha256=acceptance.acceptance_sha256,
                                   _visible_max_day=maximum_day,
                                   _frozen_row_manifest_sha256="f" * 64)
                    if prior_sha is not None: details["prior_stage_sha256"] = prior_sha
                    if selection:
                        details.update(selected_arm_sha256="1" * 64,
                                       selected_objective_sha256="2" * 64,
                                       calibrator_sha256="3" * 64,
                                       thresholds_sha256="4" * 64,
                                       capacity_authority_sha256=capacity_authority)
                        details["economics"] = held_economics
                    if component == "execute_e3":
                        details.update(report_only=True, no_selection_mutation=True,
                            held_status="PASS",
                            held_reasons_by_asset={asset: ()
                                                   for asset in ("HG", "NKD", "SI")})
                        calls.append(1)
                    return GateEvidence(component, True, True, False, maximum_day, SHA, details)
                return execute
            e1_path = Path(directory) / "e1.json"
            e1 = run_neural_sufficiency(
                "E1", _context(20250630), {"execute_e1": stage_callback("execute_e1", 20211231)},
                output_path=e1_path, acceptance_receipt_path=acceptance_path,
            )
            e2_path = Path(directory) / "e2.json"
            e2 = run_neural_sufficiency(
                "E2", _context(20250630),
                {"execute_e2": stage_callback("execute_e2", 20220630,
                                               prior_sha=e1.stage_sha256, selection=True)},
                output_path=e2_path, acceptance_receipt_path=acceptance_path,
                prior_stage_receipt_path=e1_path,
            )
            def execute(context: RunContext) -> GateEvidence:
                return stage_callback("execute_e3", 20221230,
                                      prior_sha=e2.stage_sha256, selection=True)(context)
            e3_path = Path(directory) / "e3.json"
            run_neural_sufficiency(
                "E3", _context(20250630), {"execute_e3": execute},
                output_path=e3_path,
                acceptance_receipt_path=acceptance_path,
                prior_stage_receipt_path=e2_path,
            )
            winner = adopt_e3_winner(
                acceptance_receipt_path=acceptance_path, e1_receipt_path=e1_path,
                e2_receipt_path=e2_path, e3_receipt_path=e3_path,
                output_path=Path(directory) / "winner.json",
            )
            self.assertEqual(winner.frozen_selection, e2.frozen_selection)
            with self.assertRaisesRegex(NeuralSufficiencyRefusal, "320 GiB"):
                run_neural_sufficiency(
                    "E3", _context(20221230, 319), {"execute_e3": execute},
                    output_path=Path(directory) / "low-memory.json",
                    acceptance_receipt_path=acceptance_path,
                    prior_stage_receipt_path=e2_path,
                )
            h2 = replace(_context(20221230), source_paths=("/sealed/2025H2/data",))
            with self.assertRaisesRegex(NeuralSufficiencyRefusal, "sealed H2"):
                run_neural_sufficiency(
                    "E3", h2, {"execute_e3": execute},
                    output_path=Path(directory) / "h2.json",
                    acceptance_receipt_path=acceptance_path,
                    prior_stage_receipt_path=e2_path,
                )
            self.assertEqual(calls, [1])

    def test_capacity_regime_is_oracle_derived_and_job_folder_is_not_payload(self):
        self.assertEqual(capacity_regime_from_oracle(2500), "FULL")
        self.assertEqual(capacity_regime_from_oracle(2000), "FULL")
        self.assertEqual(capacity_regime_from_oracle(1800), "WEAK")
        self.assertEqual(capacity_regime_from_oracle(1100), "LOW")
        with self.assertRaises(NeuralSufficiencyRefusal):
            capacity_regime_from_oracle(999)
        context = replace(_context(),
                          source_paths=("/workspace/jobs/20260817/provider/source.json",))
        with tempfile.TemporaryDirectory() as directory:
            run_neural_sufficiency(
                "preheld-fit-only-acceptance", context, _acceptance_backends(),
                output_path=Path(directory) / "acceptance.json",
            )
        sealed = replace(_context(), source_paths=("/data/SI.20260102.qre2",))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(NeuralSufficiencyRefusal, "sealed H2"):
                run_neural_sufficiency(
                    "preheld-fit-only-acceptance", sealed, _acceptance_backends(),
                    output_path=Path(directory) / "acceptance.json",
                )


if __name__ == "__main__":
    unittest.main()
