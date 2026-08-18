"""Focused tests for the single-invocation adversarial audit receipt."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from engine.entry_v2.audit import (
    BOTTLENECK_ORDER,
    PRODUCTION_HOOK_NAMES,
    REQUIRED_CHECKS,
    _attribute_bottleneck,
    run_audit,
    verify_receipt,
    write_report,
)
from engine.entry_v2.common import ASSETS


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bottlenecks(*, fail_at: str | None = None) -> dict[str, dict[str, object]]:
    rows: dict[str, dict[str, object]] = {
        "candidate_ceiling": {
            "resolved": True, "passed": True,
            "evidence_type": "EXACT_CANDIDATE_ORACLE",
            "per_asset": {asset: {"usd_per_asset_day": 2_500.0,
                                  "capacity_regimes": {"E3": "FULL"},
                                  "capacity_authority_sha256": "a" * 64,
                                  "passed": True}
                          for asset in ASSETS},
        },
        "raw_prefix_fidelity": {
            "resolved": True, "passed": True,
            "evidence_type": "EXACT_PREFIX_HASH_COUNT",
            "matched_events": 100, "mismatched_events": 0,
        },
        "teacher_alignment": {
            "resolved": True, "passed": True,
            "evidence_type": "EXACT_LABEL_JOIN",
            "matched_candidates": 10, "mismatched_candidates": 0,
        },
        "representation_learnability": {
            "resolved": True, "passed": True,
            "evidence_type": "EXACT_DIRECT_HEAD_OOF_REPLAY_DOLLARS",
            "per_asset": {
                asset: {"direct_usd_per_asset_day": 900.0,
                        "shuffled_usd_per_asset_day": 0.0,
                        "arrival_oracle_capture": 0.3}
                for asset in ASSETS
            },
            "diagnostics": {"auc": 0.5, "loss": 0.2},
        },
        "oof_policy": {
            "resolved": True, "passed": True,
            "evidence_type": "EXACT_GBT_OOF_REPLAY_DOLLARS",
            "per_asset": {
                asset: {"usd_per_asset_day": 2_100.0,
                        "usd_per_trade": 700.0,
                        "max_drawdown_usd": 900.0,
                        "drawdown_p90_usd": 900.0,
                        "shuffled_usd_per_asset_day": 0.0,
                        "learned_vs_shuffled_lift_usd_per_asset_day": 2_100.0,
                        "era_capacity_gate": {"E3": {
                            "passed": True,
                            "capacity_authority_sha256": "a" * 64}}}
                for asset in ASSETS
            },
            "diagnostics": {"spearman": 0.0},
        },
        "exact_replay": {
            "resolved": True, "passed": True,
            "evidence_type": "EXACT_ARRIVAL_REPLAY_DOLLARS_AND_ORACLE_CAPTURE",
            "per_asset": {
                asset: {"usd_per_asset_day": 2_100.0,
                        "usd_per_trade": 700.0,
                        "max_drawdown_usd": 900.0,
                        "drawdown_p90_usd": 900.0,
                        "candidate_oracle_capture": 0.92,
                        "era_capacity_gate": {"E3": {
                            "passed": True,
                            "capacity_authority_sha256": "a" * 64}}}
                for asset in ASSETS
            },
        },
    }
    if fail_at is not None:
        rows[fail_at]["resolved"] = False
        rows[fail_at]["passed"] = False
    return rows


def artifact_manifest(root: Path, *, bad_model_hash: bool = False,
                      fail_at: str | None = None) -> dict[str, object]:
    source = root / "source.manifest"
    substrate = root / "substrate.receipt"
    model = root / "model.receipt"
    source.write_bytes(b"source")
    substrate.write_bytes(b"substrate")
    model.write_bytes(b"model")
    source_hash = digest(source.read_bytes())
    substrate_hash = digest(substrate.read_bytes())
    model_hash = digest(model.read_bytes())
    return {
        "schema": "entry-v2-audit-artifacts-v1",
        "source": {
            "name": "source", "path": str(source), "sha256": source_hash,
            "parent_sha256": None,
            "available_min_day": 20210101, "available_max_day": 20261231,
            "development_end_day": 20250630,
            "holdout_start_day": 20250701, "holdout_end_day": 20251231,
            "sealed_start_day": 20260101, "opened_through_day": 20250630,
            "stage": "DEVELOPMENT",
        },
        "artifacts": [{
            "name": "substrate", "path": str(substrate),
            "sha256": substrate_hash, "parent_sha256": source_hash,
        }],
        "model": {
            "name": "model", "path": str(model),
            "sha256": "0" * 64 if bad_model_hash else model_hash,
            "parent_sha256": substrate_hash,
        },
        "history": {
            "locked_iid": [{"session_day": 20250103,
                            "selection_basis_day": 20250102}],
            "phases": [{"effective_from_day": 20250201,
                        "fit_end_day": 20250131}],
        },
        "folds": [{"name": "E5", "train_days": [20250101, 20250102],
                   "validation_days": [20250103],
                   "holdout_days": [20250104]}],
        "bottleneck_boundaries": bottlenecks(fail_at=fail_at),
    }


class AuditHarnessTests(unittest.TestCase):
    def test_synthetic_one_shot_is_complete_and_self_hashed(self) -> None:
        report = run_audit()
        # V7: a fixture-only audit (no artifact manifest) can never publish a
        # PASS.  It runs every check, verifies its own receipt, and reports the
        # typed refusal instead.
        self.assertFalse(report["payload"]["passed"])
        self.assertEqual(report["payload"]["audit_scope"], "SYNTHETIC_BUILTINS")
        attribution_check = next(
            row for row in report["payload"]["checks"]
            if row["name"] == "exact_bottleneck_attribution")
        self.assertEqual(attribution_check["details"]["evidence_scope"],
                         "SYNTHETIC_REGRESSION_ONLY")
        self.assertIn("NO_ARTIFACT_MANIFEST",
                      attribution_check["details"]["refusal"])
        self.assertTrue(verify_receipt(report))
        names = [row["name"] for row in report["payload"]["checks"]]
        # V7: the production-live gate is now REPORTED for a fixture-only run
        # instead of being short-circuited to complete by a missing manifest.
        self.assertEqual(names,
                         [*REQUIRED_CHECKS, "production_live_mutation_gate"])
        gate = next(row for row in report["payload"]["checks"]
                    if row["name"] == "production_live_mutation_gate")
        self.assertFalse(gate["passed"])
        controls = next(row for row in report["payload"]["checks"]
                        if row["name"] == "oracle_and_null_controls")
        # V7: the +/-$1,000 bounds are synthetic-regression-only, labelled so.
        self.assertEqual(controls["details"]["evidence_scope"],
                         "SYNTHETIC_REGRESSION_ONLY")
        self.assertFalse(controls["details"]["economic_evidence"])
        self.assertEqual(controls["details"]["truth_floor_scope"],
                         "SYNTHETIC_REGRESSION_ONLY")
        self.assertEqual(controls["details"]["shuffled_max_scope"],
                         "SYNTHETIC_REGRESSION_ONLY")
        self.assertGreaterEqual(controls["details"]["truth_usd_per_asset_day"],
                                controls["details"]["truth_floor"])
        self.assertLessEqual(controls["details"]["shuffled_usd_per_asset_day"],
                             controls["details"]["shuffled_max"])
        attribution = report["payload"]["bottleneck_attribution"]
        self.assertEqual(attribution["boundary_order"], list(BOTTLENECK_ORDER))
        self.assertIsNone(attribution["first_failed_boundary"])
        self.assertTrue(attribution["promotion"]["promoted"])
        self.assertTrue(attribution["promotion"]["fixture_promoted"])
        self.assertFalse(attribution["promotion"]["project_promoted"])
        self.assertEqual(attribution["promotion"]["scope"],
                         "SYNTHETIC_HARNESS_ONLY")

    def test_real_manifest_requires_live_production_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = artifact_manifest(Path(tmp))
            blocked = run_audit(manifest=manifest)
            self.assertFalse(blocked["payload"]["passed"])
            self.assertFalse(blocked["payload"]["bottleneck_attribution"]
                             ["promotion"]["project_promoted"])

            calls: list[str] = []
            def hook(name: str):
                def run(_context: object) -> dict[str, object]:
                    calls.append(name)
                    return {"evidence_scope": "LIVE_PRODUCTION_OBJECTS",
                            "mutation": "refused"}
                return run

            hooks = tuple((name, hook(name)) for name in PRODUCTION_HOOK_NAMES)
            report = run_audit(manifest=manifest, hooks=hooks)
            self.assertTrue(report["payload"]["passed"])
            self.assertEqual(calls, list(PRODUCTION_HOOK_NAMES))
            self.assertTrue(verify_receipt(report))
            self.assertTrue(report["payload"]["bottleneck_attribution"]
                            ["promotion"]["project_promoted"])

    def test_fail_closed_hash_and_first_boundary_attribution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad_hash = run_audit(manifest=artifact_manifest(root, bad_model_hash=True))
            self.assertFalse(bad_hash["payload"]["passed"])
            failed = {row["name"]: row for row in bad_hash["payload"]["checks"]}
            self.assertFalse(failed["artifact_hash_lineage"]["passed"])
            self.assertIn("hash mismatch", failed["artifact_hash_lineage"]["error"])
            self.assertTrue(verify_receipt(bad_hash))

            drawdown = bottlenecks()
            drawdown["oof_policy"]["per_asset"]["SI"][
                "max_drawdown_usd"
            ] = 1_001.0
            # P90 remains below the wall; only the chronological maximum is
            # promotional.
            drawdown_attribution = _attribute_bottleneck(drawdown)
            self.assertEqual(
                drawdown_attribution["first_failed_boundary"], "oof_policy"
            )
            self.assertIn(
                "drawdown_p90_usd",
                drawdown_attribution["promotion"]["diagnostic_only_metrics"],
            )

            blocked = run_audit(manifest=artifact_manifest(root, fail_at="raw_prefix_fidelity"))
            self.assertFalse(blocked["payload"]["passed"])
            attribution = blocked["payload"]["bottleneck_attribution"]
            self.assertEqual(attribution["first_failed_boundary"], "raw_prefix_fidelity")
            statuses = {row["name"]: row["status"]
                        for row in attribution["boundaries"]}
            self.assertEqual(statuses["raw_prefix_fidelity"], "UNRESOLVED")
            self.assertEqual(statuses["teacher_alignment"], "NOT_REACHED")
            self.assertEqual(statuses["exact_replay"], "NOT_REACHED")
            self.assertFalse(attribution["downstream_generalization_allowed"])
            self.assertFalse(attribution["promotion"]["promoted"])

            output = root / "failed-audit.json"
            write_report(blocked, output)
            loaded = json.loads(output.read_text())
            self.assertTrue(verify_receipt(loaded))


if __name__ == "__main__":
    unittest.main()
