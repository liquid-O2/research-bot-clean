#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

import numpy as np
import torch
from safetensors.torch import save

from . import common as C
from .capacity_contract import capacity_eligibility
from .causal_label_atlas import (
    CellAvailability, PADDED_OUTPUT_WIDTH, ProbeTarget,
    probe_target_schema_sha256,
)
from .neural_winner_artifact import (
    BundleWinnerPolicyRuntime, FrozenAtlasTargetStore, WinnerArtifactRefusal,
    _ForwardRefitWinnerPolicy,
    load_winner_bundle, load_winner_policy_canary, load_winner_policy_factory,
    publish_winner_bundle,
)
from .policy import ModelInputBinding, PolicyConfig
from .event_pack import CONTINUOUS_FIELDS, CATEGORICAL_FIELDS, CATEGORY_SIZES
from .session_stream import MODEL_ARRAYS_CONVERSION_LAW_SHA256
from .neural_sufficiency_model import SharedCandidateDecisionHead
from .selected_horizon_contract import (
    COORDINATES as SELECTED_HORIZON_COORDINATES,
    SCHEMA_SHA256 as SELECTED_HORIZON_SCHEMA_SHA256,
    TARGET_LAW_SHA256 as SELECTED_HORIZON_TARGET_LAW_SHA256,
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _capacity_document() -> dict:
    rows = {}
    for asset in C.ASSETS:
        row = {
            "capacity_regime": "FULL",
            "included_trading_days": 20,
            "days_with_trades": 20,
            "trades": 40,
            "total_pnl_usd": 42_000.0,
            "usd_per_trade": 1_050.0,
            "usd_per_asset_day": 2_100.0,
            "chronological_max_drawdown_usd": 450.0,
            "drawdown_p90_usd": 300.0,
            "oracle_total_pnl_usd": 60_000.0,
            "oracle_usd_per_asset_day": 3_000.0,
            "oracle_capture": 0.7,
            "asset_day_denominator": "included_trading_days",
            "values_clipped": False,
            "replay_receipt_sha256": "a" * 64,
            "oracle_replay_receipt_sha256": "b" * 64,
        }
        eligibility = capacity_eligibility(row)
        row.update(
            eligibility="ELIGIBLE",
            threshold_feasibility_sha256=eligibility.threshold_feasibility_sha256,
            capacity_eligibility_sha256=eligibility.receipt_sha256,
        )
        rows[asset] = row
    return {
        "schema": "entry-v2-capacity-authority-v2",
        "values_clipped": False,
        "asset_day_denominator": "included_trading_days",
        "per_asset": rows,
    }


class WinnerArtifactTest(unittest.TestCase):
    def setUp(self):
        self.parent = Path(tempfile.mkdtemp(
            prefix="winner_bundle_", dir=C.REPO_ROOT / "artifacts" / "cache"
        ))

    def tearDown(self):
        for path in self.parent.rglob("*"):
            try:
                path.chmod(0o755 if path.is_dir() else 0o644)
            except FileNotFoundError:
                pass
        shutil.rmtree(self.parent)

    def test_preinitialized_cuda_without_prior_cublas_bootstrap_refuses(self):
        script = r'''
import os
os.environ.pop("CUBLAS_WORKSPACE_CONFIG", None)
import torch
if not torch.cuda.is_available():
    raise SystemExit(77)
torch.empty(1, device="cuda")
if not torch.cuda.is_initialized():
    raise SystemExit("CUDA initialization adversary did not initialize CUDA")
from engine.entry_v2.neural_winner_artifact import (
    WinnerArtifactRefusal, enforce_selected_determinism,
)
try:
    enforce_selected_determinism()
except WinnerArtifactRefusal as exc:
    if "CUDA initialized before deterministic CUBLAS bootstrap" not in str(exc):
        raise
else:
    raise SystemExit("unsafe preinitialized CUDA was accepted")
'''
        environment = dict(os.environ)
        environment.pop("CUBLAS_WORKSPACE_CONFIG", None)
        completed = subprocess.run(
            [sys.executable, "-c", script], cwd=C.REPO_ROOT,
            env=environment, capture_output=True, text=True, timeout=30,
        )
        if completed.returncode == 77:
            self.skipTest("CUDA is unavailable for the preinitialized-context adversary")
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_forward_direct_mapper_uses_a013_train_weights_and_disjoint_calibration(self):
        class Auxiliary:
            def __init__(self, *_args, **_kwargs):
                pass

            def fit(self, _x, _targets):
                return self

            def raw_predict(self, x):
                n = len(x)
                return {
                    "action_raw": np.full(n, 0.5),
                    "top3_raw": np.full(n, 0.5),
                    "wall_raw": np.full(n, 0.5),
                    "value_prob": np.full((n, 5), 0.2),
                    "expected_value_raw": np.zeros(n),
                    "expected_value_binned": np.zeros(n),
                    "mae_q90": np.full(n, 100.0),
                }

            def calibrate(self, _raw, _truth):
                return self

            def score_raw(self, raw):
                n = len(raw["action_raw"])
                return {
                    "action_p": np.full(n, 0.5), "top3_p": np.full(n, 0.5),
                    "wall_p_upper": np.full(n, 0.1),
                    "expected_value_raw": np.zeros(n),
                    "expected_value_lower": np.zeros(n),
                    "expected_value_upper": np.zeros(n),
                    "mae_q90": np.full(n, 100.0),
                }

        binding = ModelInputBinding(
            tuple(CONTINUOUS_FIELDS), tuple(CATEGORICAL_FIELDS),
            tuple(CATEGORY_SIZES), MODEL_ARRAYS_CONVERSION_LAW_SHA256,
            "2" * 64, "3" * 64, "4" * 64, "5" * 64,
        )
        n = 120
        targets = {
            "candidate_id": np.asarray([f"fit-{i}" for i in range(n)]),
            "asset": np.asarray(["SI"] * n),
            "trading_day": np.repeat(np.arange(20240101, 20240105), 30),
            "phase": np.asarray([f"P{i % 3}" for i in range(n)]),
            "decision_ts_ns": np.arange(n, dtype=np.int64),
            "take_target": (np.arange(n) % 7 == 0).astype(np.float64),
            "action_loss_mask": np.ones(n, dtype=bool),
        }
        x = np.linspace(-2.0, 2.0, n, dtype=np.float32)[:, None]
        runtime = SimpleNamespace(kind="direct_neural")
        with mock.patch(
            "engine.entry_v2.neural_winner_artifact.AssetPolicy", Auxiliary
        ):
            policy = _ForwardRefitWinnerPolicy(
                "SI", PolicyConfig(), binding, runtime
            ).fit(x, targets)
            mapper_before = policy.mapper_parameter_sha256
            m = 40
            calibration = {
                **{key: np.asarray(value)[:m].copy()
                   for key, value in targets.items()},
                "candidate_id": np.asarray([f"cal-{i}" for i in range(m)]),
                "take_target": (np.arange(m) % 2).astype(np.float64),
                "action_loss_mask": np.ones(m, dtype=bool),
            }
            raw = policy.raw_predict(x[:m])
            policy.calibrate(raw, calibration)
        evidence = policy.selected_training_evidence
        self.assertIsNotNone(evidence)
        self.assertEqual(mapper_before, policy.mapper_parameter_sha256)
        self.assertEqual(
            evidence["optimizer_step_unit"], "complete_asset_day_gradient"
        )
        self.assertEqual(evidence["mapper_weighting"], "A013_ACTION_FIT_WEIGHTS")
        self.assertIsNone(evidence["phase_pair_manifest_sha256"])

    def test_bundle_binds_real_payloads_and_rejects_receipt_only(self):
        binding = ModelInputBinding(
            tuple(CONTINUOUS_FIELDS), tuple(CATEGORICAL_FIELDS), tuple(CATEGORY_SIZES),
            MODEL_ARRAYS_CONVERSION_LAW_SHA256, "2" * 64, "3" * 64,
            "4" * 64, "5" * 64,
        )
        architecture = {
            "event_continuous_fields": list(CONTINUOUS_FIELDS),
            "event_categorical_fields": list(CATEGORICAL_FIELDS),
            "event_category_sizes": list(CATEGORY_SIZES),
            "conversion_law_sha256": MODEL_ARRAYS_CONVERSION_LAW_SHA256,
            "candidate_features": 2, "context_continuous": 2,
            "context_types": 2, "static_bypass": True,
            "n_value_bins": 5, "n_phases": 8,
            "decision_head_kind": "direct_neural",
            "shared_head_initial_sha256": "6" * 64,
            "no_parameter_alias_receipt_sha256": "7" * 64,
            "branch_identity_receipt_sha256": "8" * 64,
            "m1_pointwise_checkpoint_sha256": "9" * 64,
            "input_contract_sha256": binding.input_contract_sha256,
            "expanded_schema_sha256": "a" * 64,
            "expanded_transform_law_sha256": "b" * 64,
            "expanded_transform_output": "UNNORMALIZED_CANONICAL",
            "branch_parameters_nonaliased": True,
            "shared_head_initial_identity": True,
            "selected_horizon_coordinates": list(SELECTED_HORIZON_COORDINATES),
            "selected_horizon_schema_sha256": SELECTED_HORIZON_SCHEMA_SHA256,
            "selected_horizon_target_law_sha256":
                SELECTED_HORIZON_TARGET_LAW_SHA256,
            "selected_output_schema_sha256": SharedCandidateDecisionHead(
                2, 2, 2, n_value_bins=5, n_phases=8,
            ).output_schema_sha256,
            "ordinal_semantics": "P(value_bin>=1..4)",
        }
        horizon_normalizer = {
            "schema": "entry-v2-selected-horizon-normalizer-v1",
            "coordinates": list(SELECTED_HORIZON_COORDINATES),
            "target_schema_sha256": SELECTED_HORIZON_SCHEMA_SHA256,
            "target_law_sha256": SELECTED_HORIZON_TARGET_LAW_SHA256,
            "location": [0.0] * 6, "scale": [1.0] * 6,
        }
        horizon_normalizer["receipt_sha256"] = sha(canonical(horizon_normalizer))
        architecture["selected_horizon_normalizer_sha256"] = (
            horizon_normalizer["receipt_sha256"]
        )
        objective = {
            "schema": "entry-v2-selected-atlas-objective-v1",
            "registry_id": "C14P01", "materializer_id": "materialize.cell14",
            "loss_id": "loss.cell14.v1",
            "action_mapper_id": "action_mapper.cell14.v1",
            **{key: "3" * 64 for key in (
                "axes_sha256", "transform_provenance_sha256",
                "ipcw_provenance_sha256", "loss_callable_sha256",
                "atlas_aggregate_sha256", "materializer_callable_sha256",
                "fit_context_sha256", "target_row_manifest_sha256",
                "registry_objective_sha256",
            )},
        }
        encoder = b"encoder"
        head = save({
            "action_head.weight": torch.zeros((1, 512)),
            "action_head.bias": torch.zeros(1),
        })
        objective_head = b"objective-head"
        arm = canonical({
            "schema": "entry-v2-selected-neural-arm-v1", "arm": "M1",
            "architecture": architecture, "encoder_sha256": sha(encoder),
            "head_sha256": sha(head),
            "objective_head_sha256": sha(objective_head),
        })
        canary_probability = float(1.0 / (1.0 + np.exp(-0.64)))
        payloads = {
            "arm.json": arm, "objective.json": canonical(objective),
            "encoder.safetensors": encoder, "head.safetensors": head,
            "objective-head.safetensors": objective_head,
            "direct-policy.safetensors": save({
                "weight": torch.zeros((1, 512)), "bias": torch.zeros(1),
            }),
            "normalizers.json": canonical({
                "schema": "normalizers", "selected_horizon": horizon_normalizer,
            }),
            "mapper.json": canonical({
                "schema": "entry-v2-binding-mapper-v1",
                "coef": [0.01] * 128, "intercept": 0.0,
                "fit_ids_sha256": "c" * 64,
            }),
            "calibrator.json": canonical({
                "schema": "entry-v2-positive-slope-calibrator-v1",
                "slope": 1.0, "intercept": 0.0,
                "fit_ids_sha256": "d" * 64,
            }),
            "thresholds.json": canonical({
                "schema": "entry-v2-thresholds-v1",
                "thresholds": {asset: .7 for asset in C.ASSETS}
            }),
            "policy-canary.json": canonical({
                "schema": "entry-v2-winner-policy-canary-v1",
                "input": "ZERO_FEATURE_ROW",
                "per_asset": {asset: {
                    "raw_model_score": 0.5,
                    "mapper_score": 0.64,
                    "calibrated_probability": canary_probability,
                    "threshold": 0.7, "enter": False,
                } for asset in C.ASSETS},
            }),
            "capacity.json": canonical(_capacity_document()),
            "source-manifest.json": canonical({"schema": "source"}),
            "row-manifest.json": canonical({
                "schema": "rows", "target_row_manifest_sha256": "3" * 64
            }),
        }
        selection = {
            "selected_arm_sha256": sha(payloads["arm.json"]),
            "selected_objective_sha256": sha(payloads["objective.json"]),
            "calibrator_sha256": sha(payloads["calibrator.json"]),
            "thresholds_sha256": sha(payloads["thresholds.json"]),
            "capacity_authority_sha256": sha(payloads["capacity.json"]),
        }
        adoption = SimpleNamespace(adoption_sha256="a" * 64,
                                   frozen_selection=selection)
        bad_architecture = dict(architecture)
        bad_architecture["selected_horizon_coordinates"] = [
            600, 300, 900, 1200, 1800, "FINAL",
        ]
        with mock.patch(
            "engine.entry_v2.neural_winner_artifact.load_winner_adoption",
            return_value=adoption,
        ):
            with self.assertRaisesRegex(
                    WinnerArtifactRefusal, "horizon/ordinal output contract"):
                publish_winner_bundle(
                    self.parent / "mutated-bundle",
                    adoption_receipt_path=self.parent / "adopt.json",
                    arm="M1", architecture=bad_architecture,
                    objective=objective, model_input_binding=binding,
                    payloads=payloads, primary_e3_fold_sha256="f" * 64,
                )
            bundle = publish_winner_bundle(
                self.parent / "bundle", adoption_receipt_path=self.parent / "adopt.json",
                arm="M1", architecture=architecture, objective=objective,
                model_input_binding=binding, payloads=payloads,
                primary_e3_fold_sha256="f" * 64,
            )
        self.assertEqual(bundle.arm, "M1")
        self.assertEqual(load_winner_bundle(
            bundle.root, expected_adoption_sha256="a" * 64,
            expected_binding=binding,
        ).bundle_sha256, bundle.bundle_sha256)
        first = BundleWinnerPolicyRuntime(bundle).decide(
            np.zeros((2, 512), np.float32), "SI"
        )
        restarted = BundleWinnerPolicyRuntime(load_winner_bundle(bundle.root)).decide(
            np.zeros((2, 512), np.float32), "SI"
        )
        np.testing.assert_array_equal(first.calibrated_probability,
                                      restarted.calibrated_probability)
        self.assertEqual(first.enter.tolist(), [False, False])
        self.assertEqual(load_winner_policy_canary(bundle),
                         load_winner_policy_canary(load_winner_bundle(bundle.root)))
        self.assertEqual(os.environ["CUBLAS_WORKSPACE_CONFIG"], ":4096:8")
        self.assertTrue(torch.are_deterministic_algorithms_enabled())
        self.assertFalse(torch.backends.cuda.flash_sdp_enabled())
        self.assertFalse(torch.backends.cuda.mem_efficient_sdp_enabled())
        self.assertTrue(torch.backends.cuda.math_sdp_enabled())

        class TinyAuxiliary:
            def __init__(self, *_args, **_kwargs): pass
            def fit(self, *_args, **_kwargs): return self
            def raw_predict(self, x): return {}

        x = np.linspace(-2.0, 2.0, 120, dtype=np.float32)[:, None]
        targets = {
            "take_target": (np.arange(120) % 2).astype(float),
            "action_loss_mask": np.ones(120, bool),
            "candidate_id": np.asarray([f"SI:20210104:c{i:03d}"
                                        for i in range(120)]),
            "asset": np.full(120, "SI"),
            "trading_day": np.full(120, 20210104, np.int64),
            "phase": np.full(120, "G1_PHASE_0"),
            "decision_ts_ns": np.arange(120, dtype=np.int64),
        }
        with mock.patch(
            "engine.entry_v2.neural_winner_artifact.AssetPolicy", TinyAuxiliary
        ):
            factory = load_winner_policy_factory(bundle)
            config = SimpleNamespace(workers=1, seed=17)
            first_fit = factory("SI", config, binding).fit(x, targets)
            second_fit = factory("SI", config, binding).fit(x, targets)
        np.testing.assert_array_equal(first_fit.coef_, second_fit.coef_)
        np.testing.assert_array_equal(
            first_fit.raw_predict(x)["winner_mapper_raw"],
            second_fit.raw_predict(x)["winner_mapper_raw"],
        )
        canary_path = bundle.root / "policy-canary.json"
        canary_bytes = canary_path.read_bytes()
        canary_path.chmod(0o644)
        canary_path.write_bytes(canary_bytes.replace(b"0.7", b"0.6"))
        canary_path.chmod(0o444)
        with self.assertRaisesRegex(WinnerArtifactRefusal, "changed after load"):
            load_winner_policy_canary(bundle)
        canary_path.chmod(0o644)
        canary_path.write_bytes(canary_bytes)
        canary_path.chmod(0o444)
        (bundle.root / "head.safetensors").chmod(0o644)
        with self.assertRaisesRegex(WinnerArtifactRefusal, "mutable"):
            load_winner_bundle(bundle.root)

    def test_compact_target_store_vectorized_exact_order(self):
        n = 3
        matrix = np.zeros((n, PADDED_OUTPUT_WIDTH), np.float32)
        coordinates = np.zeros_like(matrix, bool); coordinates[:, 0] = True
        one = np.ones(n, bool); zero = np.zeros(n, bool)
        target = ProbeTarget(
            "C14P01", CellAvailability.MATERIALIZED, matrix, coordinates,
            coordinates, np.zeros_like(coordinates), one, one, zero,
            np.ones(n, np.float32), np.arange(n), np.ones(n, np.int64),
            1, ("action",), 1,
            probe_target_schema_sha256(
                "C14P01", 1, ("action",), 1, None, 1, ("action",)
            ),
            None, 1, ("action",),
        )
        store = FrozenAtlasTargetStore(
            "1" * 64, "2" * 64, np.asarray(["a", "b", "c"]), target,
            "3" * 64, "4" * 64, "5" * 64, "6" * 64, "7" * 64, "8" * 64,
            "9" * 64, "a" * 64, "b" * 64,
            {
                "schema": "entry-v2-selected-target-control-v2",
                "target_control_sha256": "9" * 64,
                "target_candidate_manifest_sha256": "b" * 64,
                "marginals_preserved": True,
            },
        )
        self.assertEqual(
            store.target_for(("c", "a")).values.shape,
            (2, PADDED_OUTPUT_WIDTH),
        )
        with self.assertRaisesRegex(WinnerArtifactRefusal, "lacks"):
            store.target_for(("z",))


if __name__ == "__main__":
    unittest.main()
