from __future__ import annotations

from dataclasses import replace
import unittest
import numpy as np
import torch

from engine.entry_v2.causal_label_atlas import (
    CellAvailability, ProbeSpec, ProbeTarget, probe_target_schema_sha256,
)
from engine.entry_v2.atlas_probe_model import (
    AtlasProbeNet, AtlasProbeRefusal, CausalPretextSession, FitOnlyNormalizer,
    FrozenLogisticBindingMapper, INPUT_WIDTH, PRETEXT_WIDTH, STAGE_PRETEXT_WIDTH, ProbeRows,
    STATIC_WIDTH, UNIVERSAL_OUTPUT_WIDTH, SharedProbePlane, encode_stage_pretext,
    action_fit_weights, asset_day_fit_weights, canonical_phase_pair_manifest,
    fit_probe, fit_stage_pretext, _probe_validation_loss,
    synthetic_competence,
)


def _spec(probe_id="C14.P01"):
    return ProbeSpec(probe_id, 14, "m", "l", "t", "mask", "support", "shuffle", "action", ())


def _target(y, probe_id="C14.P01"):
    y = np.asarray(y, np.float32); n = len(y)
    values = np.zeros((n, UNIVERSAL_OUTPUT_WIDTH), np.float32); values[:, 0] = y
    valid = np.ones(n, bool); censor = np.zeros(n, bool); weight = np.ones(n, np.float32)
    coordinate = np.zeros_like(values, bool); coordinate[:, 0] = True
    coordinate_censor = np.zeros_like(values, bool)
    return ProbeTarget(probe_id, CellAvailability.MATERIALIZED, values,
                       coordinate, coordinate.copy(), coordinate_censor,
                       valid, valid.copy(), censor, weight,
                       np.full(n, -1, np.int64), np.ones(n, np.int64),
                       1, ("binding_action",), 1,
                       probe_target_schema_sha256(probe_id, 1, ("binding_action",), 1))


def _rows(n=24, seed=4):
    rng = np.random.default_rng(seed)
    static = rng.normal(size=(n, STATIC_WIDTH))
    pretext = rng.normal(size=(n, PRETEXT_WIDTH))
    asset = np.asarray((["HG", "NKD", "SI"] * ((n + 2) // 3))[:n])
    day = np.asarray([f"2021-06-{1 + i // 4:02d}" if i < 20 else "2021-11-01"
                      for i in range(n)])
    decision = np.arange(n, dtype=np.int64)[::-1]
    candidate = np.asarray([f"c{i:03d}" for i in range(n)])
    return ProbeRows(static, pretext, asset, day, decision, candidate)


class AtlasProbeModelTest(unittest.TestCase):
    def test_checkpoint_validation_ignores_fit_weights(self):
        rng = np.random.default_rng(808)
        spec = _spec(); target = _target(np.arange(8) % 2)
        normalized = rng.normal(size=(8, INPUT_WIDTH)).astype(np.float32)
        model = AtlasProbeNet(); indices = np.arange(8, dtype=np.int64)
        first = _probe_validation_loss(
            model, spec, normalized, indices, target, 3, torch.device("cpu"))
        altered = replace(target, fit_weight=np.asarray(
            [1e-6, 900, 2e-5, 700, 3e-5, 500, 4e-5, 300], np.float32))
        second = _probe_validation_loss(
            model, spec, normalized, indices, altered, 3, torch.device("cpu"))
        self.assertEqual(first, second)

    def test_a013_action_weights_and_phase_pairs_are_fit_only(self):
        n = 10
        asset = ["SI"] * n
        day = ["20210701"] * 6 + ["20210702"] * 4
        target = [0] * 8 + [1, "HELD-SENTINEL"]
        mask = [True] * n
        fit = np.arange(9)
        weights, receipt = action_fit_weights(asset, day, target, mask, fit)
        self.assertAlmostEqual(float(weights[:6].sum()), 1.0, places=6)
        self.assertAlmostEqual(float(weights[6:9].sum()), 1.0, places=6)
        self.assertEqual(receipt.class_factors["1"], 4.0)
        self.assertFalse(weights.flags.writeable)
        changed_target = list(target); changed_target[-1] = {"not": "binary"}
        changed_mask = list(mask); changed_mask[-1] = False
        changed, changed_receipt = action_fit_weights(
            asset, day, changed_target, changed_mask, fit)
        np.testing.assert_array_equal(weights, changed)
        self.assertEqual(receipt.receipt_sha256, changed_receipt.receipt_sha256)
        base, base_receipt = action_fit_weights(
            asset, day, target, mask, fit, apply_class_weight=False)
        self.assertEqual(dict(base_receipt.class_factors), {})
        self.assertAlmostEqual(float(base[:6].sum()), 1.0, places=6)
        generic, generic_receipt = asset_day_fit_weights(
            asset, day, target, mask, fit)
        np.testing.assert_array_equal(generic, base)
        self.assertEqual(generic_receipt.receipt_sha256,
                         base_receipt.receipt_sha256)
        self.assertEqual(receipt.optimizer_step_unit,
                         "complete_asset_day_gradient")
        with self.assertRaisesRegex(AtlasProbeRefusal, "self-consistent"):
            replace(receipt, weight_sha256="0" * 64)
        with self.assertRaisesRegex(AtlasProbeRefusal, "duplicates"):
            action_fit_weights(asset, day, target, mask, [0, 0, 1])

        candidate = [f"p{i}" for i in range(n)]
        phase = ["A"] * 3 + ["B"] * 3 + ["A"] * 4
        pair_target = [1, 0, 0, 1, 1, 0, 1, 0, 1, "LATER"]
        timestamps = [10, 8, 14, 30, 35, 33, 50, 60, 70, 80]
        manifest = canonical_phase_pair_manifest(
            candidate, asset, day, phase, timestamps, pair_target, mask, fit)
        self.assertEqual(manifest.candidate_id_pairs,
                         (("p0", "p1"), ("p0", "p2"),
                          ("p3", "p5"), ("p4", "p5"),
                          ("p6", "p7"), ("p8", "p7")))
        self.assertEqual(manifest.candidate_index_pairs,
                         ((0, 1), (0, 2), (3, 5), (4, 5),
                          (6, 7), (8, 7)))
        for value in (manifest.pair_weights[:4].sum(),
                      manifest.pair_weights[4:].sum()):
            self.assertAlmostEqual(float(value), 1.0)
        self.assertEqual(manifest.nearest_time_diagnostic_ids["p0"], ("p1", "p2"))
        pair_changed = list(pair_target); pair_changed[-1] = object()
        mask_changed = list(mask); mask_changed[-1] = False
        isolated = canonical_phase_pair_manifest(
            candidate, asset, day, phase, timestamps, pair_changed, mask_changed, fit)
        self.assertEqual(manifest.receipt_sha256, isolated.receipt_sha256)

    def test_identical_initialization_and_parameter_count(self):
        torch.manual_seed(9); source = AtlasProbeNet()
        a, b = AtlasProbeNet(), AtlasProbeNet()
        a.strict_load_initialization(source); b.strict_load_initialization(source)
        self.assertEqual(a.parameter_count, b.parameter_count)
        self.assertEqual(a.canonical_state_bytes(), b.canonical_state_bytes())
        self.assertEqual(a.canonical_state_sha256, b.canonical_state_sha256)

    def test_fit_only_normalizer_and_held_mutation_isolation(self):
        rows = _rows(); x = rows.joined(); fit = np.arange(20)
        normalizer = FitOnlyNormalizer.fit(x[fit])
        altered = x.copy(); altered[20:] = 1e9
        self.assertEqual(normalizer.receipt_sha256,
                         FitOnlyNormalizer.fit(altered[fit]).receipt_sha256)
        self.assertTrue(np.all(normalizer.transform(x)[:, normalizer.constant_zero_mask] == 0))
        with self.assertRaises(AtlasProbeRefusal):
            normalizer.transform(np.zeros((2, INPUT_WIDTH - 1)))

    def test_real_twin_batch_identity_and_held_labels_do_not_train(self):
        rows = _rows(); y = np.asarray([i % 2 for i in range(24)])
        fit = np.arange(20); torch.manual_seed(3); init = AtlasProbeNet()
        plane = SharedProbePlane.build(rows, fit, stage_id="E1")
        one = fit_probe(_spec(), rows, _target(y), fit_indices=fit,
                        initialization=init, learning_rate=1e-4,
                        shared_plane=plane, device="cpu")
        held_changed = y.copy(); held_changed[20:] = 1 - held_changed[20:]
        two = fit_probe(_spec(), rows, _target(held_changed), fit_indices=fit,
                        initialization=init, learning_rate=1e-4,
                        shared_plane=plane, device="cpu")
        self.assertEqual(one.batch_order_sha256, two.batch_order_sha256)
        self.assertEqual(one.best_checkpoint_sha256, two.best_checkpoint_sha256)
        self.assertEqual(one.normalizer.receipt_sha256, two.normalizer.receipt_sha256)
        self.assertIs(one.normalizer, plane.normalizer)
        self.assertEqual(one.shared_plane_receipt_sha256, plane.receipt.receipt_sha256)
        self.assertEqual((plane.receipt.joined_build_count,
                          plane.receipt.normalizer_fit_count,
                          plane.receipt.transform_count), (1, 1, 1))
        self.assertFalse(plane.receipt.h2_permit)
        np.testing.assert_allclose(
            plane.normalized, plane.normalizer.transform(rows.joined()), rtol=0, atol=0,
        )
        self.assertGreater(max(e.parameter_delta for e in one.epochs), 0)
        self.assertTrue(all(np.isfinite(e.gradient_norm) and e.gradient_norm > 0 for e in one.epochs))
        self.assertTrue(all(not p.requires_grad for module in
                            (one.model.layer_norm, one.model.linear_256, one.model.linear_128)
                            for p in module.parameters()))
        self.assertTrue(all(p.requires_grad for p in one.model.head.parameters()))

        validation_changed = y.copy(); validation_changed[16:20] = 1 - validation_changed[16:20]
        three = fit_probe(_spec(), rows, _target(validation_changed), fit_indices=fit,
                          initialization=init, learning_rate=1e-4,
                          shared_plane=plane, device="cpu")
        self.assertEqual(one.weight_receipt_sha256, three.weight_receipt_sha256)
        with self.assertRaisesRegex(AtlasProbeRefusal, "frozen candidate-day"):
            fit_probe(_spec(), rows, _target(y), fit_indices=np.arange(24),
                      initialization=init, learning_rate=1e-4)
        h2_rows = replace(rows, day=np.asarray([
            *np.asarray(rows.day)[:-1], "2025-07-01"
        ]))
        with self.assertRaisesRegex(AtlasProbeRefusal, "H2"):
            SharedProbePlane.build(h2_rows, fit, stage_id="E1")

    def test_mapper_calibration_split_and_hashes(self):
        rng = np.random.default_rng(8)
        latent = rng.normal(size=(120, 128)); y = (latent[:, 0] > 0).astype(int)
        mapper = FrozenLogisticBindingMapper().fit(latent[:80], y[:80], np.ones(80, bool),
                                                    [f"f{i}" for i in range(80)])
        with self.assertRaises(AtlasProbeRefusal):
            mapper.calibrate(latent[80:100], y[80:100], [f"c{i}" for i in range(20)],
                             threshold_selection_ids=["c3", "t1"])
        cal = mapper.calibrate(latent[80:100], y[80:100], [f"c{i}" for i in range(20)],
                               threshold_selection_ids=[f"t{i}" for i in range(20)])
        self.assertGreater(cal.slope, 0)
        p, hashes = mapper.predict(latent[100:])
        self.assertTrue(np.all((p >= 0) & (p <= 1)))
        self.assertEqual(len(hashes), 4)
        weights, receipt = action_fit_weights(
            ["SI"] * 80, [f"d{i // 8}" for i in range(80)], y[:80],
            np.ones(80, bool), np.arange(80))
        weighted = FrozenLogisticBindingMapper().fit(
            latent[:80], y[:80], np.ones(80, bool),
            [f"f{i}" for i in range(80)], sample_weight=weights,
            weight_receipt_sha256=receipt.receipt_sha256)
        self.assertEqual(weighted.weight_receipt_sha256, receipt.receipt_sha256)
        with self.assertRaisesRegex(AtlasProbeRefusal, "weights"):
            FrozenLogisticBindingMapper().fit(
                latent[:80], y[:80], np.ones(80, bool),
                [f"f{i}" for i in range(80)], sample_weight=-np.ones(80),
                weight_receipt_sha256=receipt.receipt_sha256)

    def test_two_stage_pretext_api(self):
        rng = np.random.default_rng(21); n = 24
        sessions = []
        for day_number in range(6):
            clock = np.arange(8, dtype=np.int64) * 10 + 10
            decisions = np.asarray([20, 40, 60, 90], np.int64)
            start = day_number * 4
            sessions.append(CausalPretextSession(
                f"s{day_number}", ("HG", "NKD", "SI")[day_number % 3],
                (f"2021-07-{day_number + 1:02d}" if day_number < 5
                 else "2021-11-01"), rng.normal(size=(8, 6)),
                np.column_stack((np.arange(8) % 4, np.arange(8) % 3)),
                clock, np.searchsorted(clock, decisions, side="left"), decisions,
                np.arange(start, start + 4, dtype=np.int64),
                tuple(f"p{i}" for i in range(start, start + 4)),
            ))
        values = np.zeros((n, UNIVERSAL_OUTPUT_WIDTH), np.float32)
        values[:, 0] = 1 + np.arange(n) % 2
        values[np.arange(n), 1 + np.arange(n) % 8] = 1
        values[:, 9:29] = rng.normal(size=(n, 20))
        coordinate = np.zeros_like(values, bool); coordinate[:, :29] = True
        valid = np.ones(n, bool); zeros = np.zeros(n, bool)
        layout = tuple(f"mixed_{i}" for i in range(29)); probe_id = "C01P01"
        target = ProbeTarget(
            probe_id, CellAvailability.MATERIALIZED, values, coordinate,
            coordinate.copy(), np.zeros_like(coordinate), valid, valid.copy(),
            zeros, np.ones(n, np.float32), np.full(n, -1, np.int64),
            np.ones(n, np.int64), 29, layout, 1,
            probe_target_schema_sha256(probe_id, 29, layout, 1),
        )
        spec = ProbeSpec(probe_id, 1, "m", "l", "t", "mask", "support", "shuffle", "action", ())
        source_calls = []
        def source():
            source_calls.append(1)
            yield from sorted(sessions, key=lambda row: (
                row.asset, row.day, row.session_id
            ))
        result = fit_stage_pretext("E1", source, (4, 3), spec, target,
                                   fit_indices=np.arange(20), chunk_events=3,
                                   consumer_probe_ids=("C01P01", "C02P01"))
        self.assertEqual(result.frozen_state.shape, (n, STAGE_PRETEXT_WIDTH))
        self.assertEqual(result.fit_count, 1)
        self.assertEqual(result.objective_id, "C01P01")
        self.assertTrue(result.checkpoint_sha256)
        self.assertIsNotNone(result.checkpoint)
        self.assertIsNotNone(result.streaming_receipt)
        self.assertGreater(len(source_calls), 2)
        self.assertLessEqual(result.streaming_receipt.peak_chunk_rows, 3)
        self.assertGreater(result.streaming_receipt.normalizer_event_rows, 0)
        self.assertGreater(result.streaming_receipt.normalizer_chunks, 1)
        self.assertGreater(result.streaming_receipt.train_chunks, 1)
        self.assertFalse(result.streaming_receipt.h2_permit)
        self.assertFalse(result.checkpoint.location.flags.writeable)
        self.assertTrue(all(not value.flags.writeable
                            for value in result.checkpoint.model_state.values()))
        encoded = encode_stage_pretext(
            result.checkpoint, iter(sorted(sessions, key=lambda row: (
                row.asset, row.day, row.session_id
            ))), row_count=n, chunk_events=3,
        )
        np.testing.assert_allclose(encoded.frozen_state, result.frozen_state,
                                   rtol=1e-5, atol=1e-6)
        legacy = np.full_like(result.frozen_state, np.nan)
        model, _ = result.checkpoint.load_model("cpu")
        with torch.no_grad():
            for session in sessions:
                normalized = ((session.event_continuous - result.checkpoint.location)
                              / result.checkpoint.scale)
                normalized[:, result.checkpoint.constant_zero_mask] = 0
                _, state = model(
                    torch.from_numpy(normalized.astype(np.float32)),
                    torch.from_numpy(session.event_categorical.astype(np.int64)),
                    torch.from_numpy(session.candidate_cutoffs.astype(np.int64)),
                )
                legacy[session.candidate_rows] = state.numpy()
        np.testing.assert_allclose(encoded.frozen_state, legacy, rtol=1e-5, atol=1e-6)
        altered_values = values.copy(); altered_values[20:] += 1000
        altered_target = replace(target, values=altered_values)
        isolated = fit_stage_pretext(
            "E1", source, (4, 3), spec, altered_target,
            fit_indices=np.arange(20), chunk_events=3, encode_sessions=False,
            consumer_probe_ids=("C01P01", "C02P01"),
        )
        self.assertEqual(result.checkpoint_sha256, isolated.checkpoint_sha256)
        self.assertEqual(result.input_normalizer_sha256,
                         isolated.input_normalizer_sha256)
        self.assertEqual(result.consumer_probe_ids, ("C01P01", "C02P01"))
        with self.assertRaisesRegex(AtlasProbeRefusal, "two E1"):
            fit_stage_pretext("E2", sessions, (4, 3), spec, target,
                              fit_indices=np.arange(20), consumer_probe_ids=("C01P01",))
        bad = sessions[0]
        bad_cutoff = CausalPretextSession(
            bad.session_id, bad.asset, bad.day, bad.event_continuous,
            bad.event_categorical, bad.receive_clock_ns,
            bad.candidate_cutoffs + np.asarray([1, 0, 0, 0]), bad.candidate_decision_ts_ns,
            bad.candidate_rows, bad.candidate_ids,
        )
        with self.assertRaisesRegex(AtlasProbeRefusal, "exact left searchsorted"):
            fit_stage_pretext("E1", (bad_cutoff, *sessions[1:]), (4, 3), spec, target,
                              fit_indices=np.arange(20), consumer_probe_ids=("C01P01",))
        with self.assertRaisesRegex(AtlasProbeRefusal, "H2"):
            encode_stage_pretext(
                result.checkpoint, (replace(sessions[0], day="2025-07-01"),),
                row_count=4, chunk_events=3,
            )

    def test_synthetic_competence(self):
        result = synthetic_competence()
        self.assertGreaterEqual(min(result.auroc_by_asset.values()), .995)
        self.assertGreaterEqual(min(result.ap_by_asset.values()), .995)
        self.assertLessEqual(result.bce, .02)
        self.assertTrue(result.trunk_gradient_seen and result.head_gradient_seen)
        self.assertLessEqual(result.steps, 400)


if __name__ == "__main__":
    unittest.main()
