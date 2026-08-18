#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace

from . import common as C
from . import production_driver as PD
from .policy import entry_gate_contract
from .train import THRESHOLD_FUNNEL_SCHEMA, threshold_candidate_law
from .production_driver import (
    DriverPlan, _authorize_prebuilt_substrate, _guard_run_root,
    _persist_folds, _persist_policy_gate_diagnostic, _validate_fold_adoption,
    prepare_invalid_cache_deletion,
)
from .train import FOLD_OOF_SCHEMA


class ProductionDriverTest(unittest.TestCase):
    @staticmethod
    def _legacy_training(binding):
        return SimpleNamespace(
            trace=SimpleNamespace(
                receipt_sha256="a" * 64,
                model_input_binding=binding,
            ),
            normalizer=SimpleNamespace(
                receipt_sha256="b" * 64,
                model_input_binding=binding,
            ),
        )

    @staticmethod
    def _policy_receipt(*, gate_schema="entry-v2-decision-gate-v3", feasible=1):
        funnel = [{
            "threshold": .9,
            "candidate_count": 10,
            "action_pass": 1 if feasible else 0,
            "replay_trades": 1 if feasible else 0,
            "feasible": bool(feasible),
            "reason": "FEASIBLE" if feasible else "NO_REPLAY_TRADES",
        }]
        selection = {
            "threshold": .9,
            "feasible_thresholds": feasible,
            "trades": 1 if feasible else 0,
            "usd_per_trade": 700.0 if feasible else 0.0,
            "usd_per_asset_day": 700.0 if feasible else 0.0,
            "max_drawdown_usd": 0.0,
            "funnel": funnel,
        }
        arm_thresholds = {
            arm: {asset: dict(selection) for asset in C.ASSETS}
            for arm in PD.ARM_NAMES
        }
        truth_selection = {
            **selection,
            "feasible_thresholds": 1,
            "trades": 1,
            "usd_per_trade": 700.0,
            "usd_per_asset_day": 700.0,
        }
        truth = {asset: dict(truth_selection) for asset in C.ASSETS}
        boundary = None if feasible else "POLICY_NO_FEASIBLE_THRESHOLD:SI"
        return {
            "entry_gate_contract": (
                entry_gate_contract()
                if gate_schema == "entry-v2-decision-gate-v3"
                else {"schema": gate_schema}
            ),
            "threshold_candidate_law": threshold_candidate_law(),
            "threshold_funnel_schema": THRESHOLD_FUNNEL_SCHEMA,
            "arm_thresholds": arm_thresholds,
            "truth_inner_thresholds_usd": truth,
            "decision_contract": {"first_failed_boundary": boundary},
        }

    def test_primary_policy_gate_persists_and_stale_v1_refuses(self) -> None:
        parent = Path(tempfile.mkdtemp(
            prefix="entry_v2_policy_gate_", dir=C.REPO_ROOT / "artifacts" / "cache"
        ))
        try:
            result = SimpleNamespace(
                fold="E3", receipt=self._policy_receipt(),
            )
            diagnostic = _persist_policy_gate_diagnostic(parent, result)
            self.assertTrue(diagnostic["passed"])
            self.assertTrue((parent / "stages" / "policy_gate" / "E3.json").is_file())
            stale = SimpleNamespace(
                fold="E4",
                receipt=self._policy_receipt(
                    gate_schema="entry-v2-decision-gate-v2"
                ),
            )
            with self.assertRaisesRegex(C.EntryV2Refusal, "stale/wrong"):
                _persist_policy_gate_diagnostic(parent, stale)
        finally:
            shutil.rmtree(parent)

    def test_primary_policy_gate_persists_failure_before_raise(self) -> None:
        parent = Path(tempfile.mkdtemp(
            prefix="entry_v2_policy_fail_", dir=C.REPO_ROOT / "artifacts" / "cache"
        ))
        try:
            result = SimpleNamespace(
                fold="E3", receipt=self._policy_receipt(feasible=0),
            )
            with self.assertRaisesRegex(
                C.EntryV2Refusal, "POLICY_NO_FEASIBLE_THRESHOLD:SI"
            ):
                _persist_policy_gate_diagnostic(parent, result)
            persisted = json.loads(
                (parent / "stages" / "policy_gate" / "E3.json").read_text()
            )
            self.assertFalse(persisted["passed"])
            self.assertEqual(
                persisted["first_failed_boundary"],
                "POLICY_NO_FEASIBLE_THRESHOLD:SI",
            )
        finally:
            shutil.rmtree(parent)

    def test_failing_e3_releases_and_never_runs_null_or_e4(self) -> None:
        parent = Path(tempfile.mkdtemp(
            prefix="entry_v2_policy_integrated_", dir=C.REPO_ROOT / "artifacts" / "cache"
        ))
        try:
            binding = mock.Mock()
            binding.as_dict.return_value = {"binding": "current"}
            receipt = self._policy_receipt(feasible=0)
            receipt.update({
                "schema": FOLD_OOF_SCHEMA,
                "model_input_binding": {"binding": "current"},
                "null_control": {
                    "schema": "entry-v2-positive-control-v1",
                    "control": "PROPHET",
                },
            })
            result = SimpleNamespace(
                fold="E3",
                receipt=receipt,
                training=self._legacy_training(binding),
            )
            corpus = SimpleNamespace(
                sessions=(), teacher=object(), replay=object(),
                model_input_binding=binding,
            )
            folds = (SimpleNamespace(test_era="E3"), SimpleNamespace(test_era="E4"))
            with (
                mock.patch.object(PD, "ModelInputBinding") as binding_cls,
                mock.patch.object(PD, "run_fold_oof", return_value=result) as primary,
                mock.patch.object(PD, "run_shuffled_control_oof") as shuffled,
                mock.patch.object(PD, "save_fold"),
                mock.patch.object(PD, "release_fold") as released,
            ):
                binding_cls.from_mapping.return_value = binding
                with self.assertRaisesRegex(
                    C.EntryV2Refusal, "POLICY_NO_FEASIBLE_THRESHOLD:SI"
                ):
                    _persist_folds(
                        parent, SimpleNamespace(
                            system_factory=lambda: object(), config=object(),
                            policy_factory=None,
                        ), corpus, folds, 17,
                    )
            self.assertEqual(primary.call_count, 1)
            shuffled.assert_not_called()
            released.assert_called_once_with(result)
            self.assertTrue(
                (parent / "stages" / "policy_gate" / "E3.json").is_file()
            )
        finally:
            shutil.rmtree(parent)

    def test_fold_adoption_refuses_stale_laws_and_wrong_binding(self) -> None:
        current = object()
        other = object()
        base = self._policy_receipt()
        base.update({
            "schema": FOLD_OOF_SCHEMA,
            "model_input_binding": {"binding": "current"},
            "null_control": {
                "schema": "entry-v2-positive-control-v1", "control": "PROPHET"
            },
        })
        corpus = SimpleNamespace(model_input_binding=current)

        cases = {
            "stale fold schema": {**base, "schema": "entry-v2-fold-oof-v3"},
            "missing threshold law": {
                key: value for key, value in base.items()
                if key != "threshold_candidate_law"
            },
            "wrong ranking contract": {
                **base,
                "entry_gate_contract": {
                    **entry_gate_contract(),
                    "exact_timestamp_ranking": {"wrong": True},
                },
            },
        }
        with mock.patch.object(PD, "ModelInputBinding") as binding_cls:
            binding_cls.from_mapping.return_value = current
            for name, receipt in cases.items():
                with self.subTest(name=name), self.assertRaises(C.EntryV2Refusal):
                    _validate_fold_adoption(
                        SimpleNamespace(
                            fold="E3", receipt=receipt,
                            training=self._legacy_training(current),
                        ), corpus, shuffled=False,
                    )
            binding_cls.from_mapping.return_value = other
            with self.assertRaisesRegex(C.EntryV2Refusal, "binding differs"):
                _validate_fold_adoption(
                    SimpleNamespace(
                        fold="E3", receipt=base,
                        training=self._legacy_training(other),
                    ), corpus, shuffled=False,
                )

    def test_quarantined_default_refuses_and_new_root_is_immutable(self) -> None:
        with self.assertRaisesRegex(C.EntryV2Refusal, "quarantined"):
            _guard_run_root(DriverPlan(C.CACHE_ROOT / "new-run"))
        parent = Path(tempfile.mkdtemp(
            prefix="entry_v2_driver_", dir=C.REPO_ROOT / "artifacts" / "cache"
        ))
        root = parent / "run"
        try:
            plan = DriverPlan(root)
            self.assertEqual(_guard_run_root(plan), root.resolve())
            self.assertEqual(_guard_run_root(plan), root.resolve())
            changed = DriverPlan(root, shuffle_seed=1)
            with self.assertRaisesRegex(C.EntryV2Refusal, "immutable"):
                _guard_run_root(changed)
        finally:
            shutil.rmtree(parent)

    def test_deletion_transition_validates_but_does_not_delete(self) -> None:
        receipt = C.PROVENANCE_ROOT / "test_acceptance.tmp.json"
        receipt.write_text(json.dumps({"passed": True}))
        marker = C.CACHE_ROOT / "NON_AUTHORITATIVE.json"
        try:
            before = marker.exists()
            transition = prepare_invalid_cache_deletion(receipt)
            self.assertEqual(transition["status"], "VERIFIED_NOT_EXECUTED")
            self.assertEqual(marker.exists(), before)
        finally:
            receipt.unlink(missing_ok=True)

    def test_exact_executed_deletion_authorizes_only_clean_rebuilt_root(self) -> None:
        parent = Path(tempfile.mkdtemp(
            prefix="entry_v2_adoption_", dir=C.REPO_ROOT / "artifacts" / "cache"
        ))
        root = parent / "rebuilt"
        root.mkdir()
        manifest = parent / "deletion.tsv"
        deletion = parent / "deletion.json"
        marker = root / "NON_AUTHORITATIVE.json"
        manifest.write_text(
            "schema\tentry-v2-invalid-cache-deletion-manifest-v1\n"
            "status\tNOT_EXECUTED_APPROVAL_REQUIRED\n"
            "action\tDELETE_EXACT_TREE\n"
            f"delete_root\t{root}\n"
            "expected_directory_count\t2\n"
            "expected_file_count\t3\n"
            "expected_total_file_bytes\t5\n"
            "entry_type\tsize_bytes\tsha256\tabsolute_path\n"
        )
        deletion.write_text(json.dumps({
            "schema": "entry-v2-invalid-cache-deletion-receipt-v1",
            "status": "EXECUTED",
            "deleted_root": str(root),
            "deleted_directory_count": 2,
            "deleted_file_count": 3,
            "deleted_total_file_bytes": 5,
            "exact_inventory_matched_before_delete": True,
            "target_absent_after_delete": True,
            "deletion_manifest_sha256": C.file_sha256(manifest),
        }))
        try:
            with (
                mock.patch.object(C, "CACHE_ROOT", root),
                mock.patch.object(PD, "INVALID_MARKER", marker),
                mock.patch.object(PD, "DELETION_MANIFEST", manifest),
                mock.patch.object(PD, "DELETION_RECEIPT", deletion),
            ):
                adopted, evidence = _authorize_prebuilt_substrate(
                    DriverPlan(parent / "run", prebuilt_substrate_root=root)
                )
                self.assertEqual(adopted, root.resolve())
                self.assertTrue(evidence["non_authoritative_marker_absent"])
                marker.write_text("bad")
                with self.assertRaisesRegex(C.EntryV2Refusal, "NON_AUTHORITATIVE"):
                    _authorize_prebuilt_substrate(
                        DriverPlan(parent / "run2", prebuilt_substrate_root=root)
                    )
        finally:
            shutil.rmtree(parent)


if __name__ == "__main__":
    unittest.main()
