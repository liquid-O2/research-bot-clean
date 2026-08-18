#!/usr/bin/env python3
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from dataclasses import replace
import numpy as np

from engine.entry_v2 import common as C
from engine.entry_v2 import policy as P
from engine.entry_v2.event_pack import (
    CATEGORY_SIZES, CATEGORICAL_FIELDS, CONTINUOUS_FIELDS,
)
from engine.entry_v2.session_stream import MODEL_ARRAYS_CONVERSION_LAW_SHA256


def _binding() -> P.ModelInputBinding:
    return P.ModelInputBinding(
        tuple(CONTINUOUS_FIELDS), tuple(CATEGORICAL_FIELDS),
        tuple(CATEGORY_SIZES),
        MODEL_ARRAYS_CONVERSION_LAW_SHA256,
        C.object_sha256("policy-session-stream-receipts"),
        C.object_sha256("policy-corpus-receipt"),
        C.object_sha256("policy-corpus-source-lineage"),
        C.object_sha256("policy-clock-law-receipt"),
    )


class PolicyTest(unittest.TestCase):
    def test_binding_category_size_mismatch_refuses(self):
        with self.assertRaisesRegex(C.EntryV2Refusal, "category sizes differ"):
            replace(_binding(), event_category_sizes=(256,) * 5).validate()

    def test_venn_intervals_order_and_respond(self):
        rng = np.random.default_rng(7)
        s = rng.normal(size=1000)
        y = (s + rng.normal(scale=.7, size=s.size) > 0).astype(int)
        v = P.BinnedVennAbers(64).fit(s, y)
        lo, hi, p = v.predict_interval(np.array([-2., 0., 2.]))
        self.assertTrue(np.all(lo <= p))
        self.assertTrue(np.all(p <= hi))
        self.assertGreater(p[-1], p[0])

    def test_conformal_contains_declared_fraction(self):
        rng = np.random.default_rng(8)
        y = rng.normal(size=1000)
        pred = y + rng.normal(scale=.5, size=y.size)
        c = P.ConformalValueInterval(.9).fit(pred[:500], y[:500])
        lo, hi = c.interval(pred[500:])
        self.assertGreaterEqual(np.mean((y[500:] >= lo) & (y[500:] <= hi)), .84)

    def test_value_bins(self):
        got = P.value_bin(np.array([-1., 0., 599., 600., 999., 1000., 1999., 2000.]))
        np.testing.assert_array_equal(got, [0, 1, 1, 2, 2, 3, 3, 4])

    def test_action_threshold_is_sole_gate_and_diagnostics_cannot_veto(self):
        enter = P.entry_decision_gate(
            action_probability=np.array([0.79, 0.90, 0.90, 0.90, 0.90]),
            action_threshold=0.80,
            expected_pnl_lower_usd=np.array([1000., -10_000., 600., 1600., 1600.]),
            mae_q90_usd=np.array([100., 100., 301., 501., 500.]),
            wall_probability_upper=np.array([0.1, 0.1, 0.1, 0.1, 0.2]),
            expected_pnl_upper_usd=np.array([1200., -9000., 800., 1800., 1800.]),
        )
        np.testing.assert_array_equal(
            enter,
            np.array([False, True, True, True, True]),
        )
        contract = P.entry_gate_contract()
        self.assertEqual(contract["schema"], "entry-v2-decision-gate-v3")
        self.assertEqual(
            contract["exact_timestamp_ranking"]["within_asset"],
            "(-calibrated_action_priority, candidate_id)",
        )
        self.assertEqual(
            contract["threshold_source"], "ACTION_PROBABILITY_INNER_REPLAY"
        )
        self.assertEqual(contract["hard_veto_surfaces"], [])
        with self.assertRaisesRegex(
            C.EntryV2Refusal, "invalid expected-value conformal interval"
        ):
            P.entry_decision_gate(
                0.9, 0.8, -10_000.0, 100.0, 0.1,
                expected_pnl_upper_usd=float("nan"),
            )

    def test_frozen_roundtrip_is_bit_identical_and_mutations_refuse(self):
        rng = np.random.default_rng(91)

        def population(rows, offset):
            X = rng.normal(size=(rows, 9)).astype(np.float32)
            group = (np.arange(rows) + offset) % 5
            close = np.array([-300., 300., 800., 1400., 2600.])[group]
            close = close + 20.0 * np.tanh(X[:, 0])
            action = ((group >= 3) ^ (X[:, 2] > 1.2)).astype(np.int64)
            top3 = ((group == 4) | ((group == 3) & (X[:, 3] > 0))).astype(np.int64)
            wall = (X[:, 1] > 0.15).astype(np.int64)
            mae = 80.0 + 120.0 * np.abs(X[:, 4])
            targets = {
                # Carry both names so this persistence fixture stays isolated
                # from the separately-owned target-key migration.
                "take_target": action,
                "action_loss_mask": np.ones(rows, dtype=np.uint8),
                "top3": top3,
                "cert_close_usd": close,
                "wall": wall,
                "mae_usd": mae,
            }
            return X, targets

        X_fit, fit = population(250, 0)
        X_cal, cal = population(150, 2)
        X_score, _ = population(41, 4)
        config = P.PolicyConfig(
            n_estimators=12,
            max_depth=2,
            min_child_weight=1.0,
            venn_bins=32,
        )
        policy = P.AssetPolicy("SI", config, _binding()).fit(X_fit, fit)
        policy.calibrate(policy.raw_predict(X_cal), cal)
        before = policy.score(X_score)
        from_raw = policy.score_raw(policy.raw_predict(X_score))
        for name in before:
            np.testing.assert_array_equal(before[name], from_raw[name], err_msg=name)

        C.CACHE_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="policy-freeze-", dir=C.CACHE_ROOT
        ) as scratch:
            directory = Path(scratch) / "SI_policy"
            manifest_file_sha = policy.save(directory)
            self.assertEqual(len(manifest_file_sha), 64)

            manifest_path = directory / "manifest.json"
            manifest_bytes = manifest_path.read_bytes()
            manifest = json.loads(manifest_bytes)
            self.assertEqual(set(manifest["models"]), set(P.MODEL_NAMES))
            self.assertEqual(
                set(manifest["calibration_sha256"]), set(P.CALIBRATION_NAMES)
            )
            runtime_files = {
                item["label"]: item for item in manifest["runtime"]["xgboost_files"]
            }
            self.assertTrue(runtime_files["xgboost_package_init"]["resolved"])
            self.assertTrue(runtime_files["xgboost_native_library"]["resolved"])
            self.assertEqual(
                len(runtime_files["xgboost_native_library"]["sha256"]), 64
            )

            loaded = P.AssetPolicy.load(directory)
            self.assertEqual(loaded.model_input_binding, _binding())
            after = loaded.score(X_score)
            self.assertEqual(set(before), set(after))
            for name in before:
                np.testing.assert_array_equal(before[name], after[name], err_msg=name)

            stale = json.loads(manifest_bytes)
            stale["schema"] = "entry-v2-frozen-policy-manifest-v3"
            manifest_path.write_bytes(C.canonical_bytes(stale))
            with self.assertRaisesRegex(C.EntryV2Refusal, "unknown frozen policy"):
                P.AssetPolicy.load(directory)
            manifest_path.write_bytes(manifest_bytes)

            # Every model is verified before XGBoost is allowed to deserialize.
            model_path = directory / "action.ubj"
            original_model = model_path.read_bytes()
            changed_model = bytearray(original_model)
            changed_model[len(changed_model) // 2] ^= 1
            model_path.write_bytes(changed_model)
            with self.assertRaisesRegex(C.EntryV2Refusal, "model hash mismatch"):
                P.AssetPolicy.load(directory)
            model_path.write_bytes(original_model)

            # policy.json is pinned as bytes, including canonical formatting.
            policy_path = directory / "policy.json"
            original_policy = policy_path.read_bytes()
            policy_path.write_bytes(original_policy + b"\n")
            with self.assertRaisesRegex(C.EntryV2Refusal, "state hash mismatch"):
                P.AssetPolicy.load(directory)
            policy_path.write_bytes(original_policy)

            # Even a coherently re-hashed manifest cannot waive runtime parity.
            changed_manifest = json.loads(manifest_bytes)
            changed_manifest["runtime"]["numpy_version"] = "0.0-mutated"
            changed_manifest["runtime_sha256"] = C.object_sha256(
                changed_manifest["runtime"]
            )
            changed_manifest.pop("manifest_payload_sha256")
            changed_manifest["manifest_payload_sha256"] = C.object_sha256(
                changed_manifest
            )
            manifest_path.write_bytes(C.canonical_bytes(changed_manifest))
            with self.assertRaisesRegex(C.EntryV2Refusal, "runtime/version mismatch"):
                P.AssetPolicy.load(directory)

            with self.assertRaisesRegex(C.EntryV2Refusal, "2025H2 HOLDOUT"):
                P.AssetPolicy.load(Path(scratch) / "policy_20250701")

    def test_action_fit_and_calibration_exclude_masked_rows_only(self):
        class Estimator:
            def __init__(self, **_kwargs):
                pass

            def fit(self, X, y):
                self.fit_rows = len(X)
                self.y = np.asarray(y)
                return self

        rows = 120
        X = np.arange(rows * 3, dtype=np.float32).reshape(rows, 3)
        value = np.resize(np.array([-100., 100., 700., 1200., 2500.]), rows)
        mask = np.zeros(rows, dtype=np.uint8)
        mask[:60] = 1
        targets = {
            "take_target": np.arange(rows) % 2,
            "action_loss_mask": mask,
            "top3": np.arange(rows) % 2,
            "cert_close_usd": value,
            "wall": np.arange(rows) % 2,
            "mae_usd": np.full(rows, 100.0),
        }
        classifiers: list[Estimator] = []
        regressors: list[Estimator] = []

        def classifier(**kwargs):
            item = Estimator(**kwargs)
            classifiers.append(item)
            return item

        def regressor(**kwargs):
            item = Estimator(**kwargs)
            regressors.append(item)
            return item

        with (
            mock.patch.object(P.xgb, "XGBClassifier", side_effect=classifier),
            mock.patch.object(P.xgb, "XGBRegressor", side_effect=regressor),
        ):
            policy = P.AssetPolicy("SI", P.PolicyConfig(), _binding()).fit(
                X, targets
            )
        self.assertEqual(policy.action_.fit_rows, 60)
        np.testing.assert_array_equal(
            policy.action_.y,
            np.asarray(targets["take_target"])[mask.astype(bool)],
        )
        self.assertEqual(policy.top3_.fit_rows, rows)
        self.assertEqual(policy.wall_.fit_rows, rows)
        self.assertTrue(all(item.fit_rows == rows for item in regressors))

        raw = {
            "action_raw": np.linspace(0.0, 1.0, rows),
            "top3_raw": np.linspace(0.0, 1.0, rows),
            "wall_raw": np.linspace(1.0, 0.0, rows),
            "expected_value_raw": value,
        }
        policy.calibrate(raw, targets)
        self.assertEqual(policy.action_cal_.n_, 60)
        self.assertEqual(policy.top3_cal_.n_, rows)
        self.assertEqual(policy.wall_cal_.n_, rows)
        self.assertEqual(policy.value_cal_.n_, rows)
        direct = P.BinnedVennAbers(policy.config.venn_bins).fit(
            raw["action_raw"][mask.astype(bool)],
            targets["take_target"][mask.astype(bool)],
        )
        self.assertEqual(policy.action_cal_.state(), direct.state())


if __name__ == "__main__":
    unittest.main()
