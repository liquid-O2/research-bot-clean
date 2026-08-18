#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import replace
import unittest
import numpy as np
import torch

from .atlas_losses import action_score_for_probe, loss_for_probe
from .atlas_materializers import materialize_probe_target
from .causal_label_atlas import (
    AtlasRefusal, PADDED_OUTPUT_WIDTH, PROBE_REGISTRY, SHUFFLED_PROBES,
    reject_placeholder_callable,
)
from .test_causal_label_atlas import _anchor, _index


class AtlasLossTest(unittest.TestCase):
    def test_fit_weights_never_change_validation_loss(self):
        atlas = _index().materialize((
            _anchor("a", exact_time_group_id="fit-weight-group"),
            _anchor("b", entry_mid2=1100,
                    exact_time_group_id="fit-weight-group"),
        ))
        spec = next(x for x in PROBE_REGISTRY
                    if x.cell == 3 and "P01" in x.probe_id)
        target = materialize_probe_target(atlas, spec)
        high_first = np.asarray((100.0, 1.0), np.float32)
        high_second = np.asarray((1.0, 100.0), np.float32)
        high_first.setflags(write=False); high_second.setflags(write=False)
        first = replace(target, fit_weight=high_first)
        second = replace(target, fit_weight=high_second)
        prediction = torch.stack((
            torch.full((PADDED_OUTPUT_WIDTH,), 4.0),
            torch.full((PADDED_OUTPUT_WIDTH,), -0.5),
        ))
        self.assertNotEqual(
            float(loss_for_probe(spec, prediction, first)),
            float(loss_for_probe(spec, prediction, second)),
        )
        self.assertEqual(
            float(loss_for_probe(spec, prediction, first,
                                 use_fit_weight=False)),
            float(loss_for_probe(spec, prediction, second,
                                 use_fit_weight=False)),
        )

    def test_identity_callable_rejected(self):
        def identity(value):
            return value
        with self.assertRaisesRegex(AtlasRefusal, "identity/placeholder"):
            reject_placeholder_callable("bad", identity)
        with self.assertRaisesRegex(AtlasRefusal, "identity/placeholder"):
            reject_placeholder_callable("bad_lambda", lambda value: value)

    def test_all_44_losses_are_finite_scalar_with_nonzero_gradient(self):
        atlas = _index().materialize((
            _anchor("a", exact_time_group_id="g", take_target=True,
                    now_wait_pass_regret_units=(1,2,3),
                    shadow_marginal_regret_units=(1,2),
                    process_utility_units=3),
            _anchor("b", exact_time_group_id="g", entry_mid2=1100,
                    now_wait_pass_regret_units=(3,2,1),
                    shadow_marginal_regret_units=(2,1),
                    process_utility_units=4),
        ))
        fit = {"fit_population_sha256": "b"*64,
               "c1_location": np.zeros(21), "c1_scale": np.ones(21),
               "location": np.zeros(12), "scale": np.ones(12),
               "lower": np.full(12, -1000.0), "upper": np.full(12, 1000.0),
               "rank_reference": np.zeros((3, 12))}
        for spec in (*PROBE_REGISTRY, *SHUFFLED_PROBES):
            with self.subTest(probe=spec.probe_id):
                target = materialize_probe_target(atlas, spec, fit)
                prediction = torch.full(
                    (2, PADDED_OUTPUT_WIDTH), .137, requires_grad=True
                )
                scalar = loss_for_probe(spec, prediction, target)
                self.assertEqual(scalar.ndim, 0)
                self.assertTrue(torch.isfinite(scalar))
                scalar.backward()
                self.assertIsNotNone(prediction.grad)
                self.assertTrue(torch.isfinite(prediction.grad).all())
                self.assertTrue(torch.any(prediction.grad != 0))
                score = action_score_for_probe(spec, prediction.detach(), target)
                self.assertEqual(score.shape, (2,))
                self.assertTrue(torch.isfinite(score).all())

    def test_censor_coordinates_do_not_train_as_zero(self):
        atlas = _index((1000, 1100), ts=(1_000_000_000, 20_000_000_000)).materialize((
            _anchor("censored", exact_time_group_id="g",
                    source_censor_ts_ns=5_000_000_000),
            _anchor("observed", exact_time_group_id="g", entry_mid2=1010),
        ))
        spec = next(x for x in PROBE_REGISTRY if x.cell == 3 and "P01" in x.probe_id)
        target = materialize_probe_target(atlas, spec)
        # The censored row contributes no coordinate at all; the batch stays
        # supported through the observed row, so the objective is measurable.
        self.assertEqual(target.validity_mask.tolist(), [False, True])
        self.assertFalse(target.coordinate_mask[0].any())
        prediction = torch.full((2, PADDED_OUTPUT_WIDTH), .25,
                                requires_grad=True)
        loss_for_probe(spec, prediction, target).backward()
        self.assertTrue(torch.all(prediction.grad[0] == 0))
        self.assertTrue(torch.any(prediction.grad[1] != 0))

    def test_fully_masked_objective_refuses_instead_of_scoring_zero(self):
        # V3: a fully-masked batch previously returned value.sum() * 0.0, the
        # best possible loss, which wins checkpoint selection outright.
        atlas = _index().materialize((_anchor(),))
        spec = next(x for x in PROBE_REGISTRY if x.cell == 16)
        target = materialize_probe_target(atlas, spec)
        self.assertFalse(target.validity_mask.any())
        prediction = torch.zeros((1, PADDED_OUTPUT_WIDTH), requires_grad=True)
        with self.assertRaisesRegex(AtlasRefusal, "UNAVAILABLE"):
            loss_for_probe(spec, prediction, target)

    def test_c6_censored_extreme_times_are_masked_not_zero(self):
        # V5: an unattained favorable/adverse extreme has no passage time.
        # Recording 0.0 trains "occurred instantly" as observed truth.
        atlas = _index((1000, 900, 800), ts=(1_000_000_000, 2_000_000_000,
                                             3_000_000_000)).materialize((
            _anchor(phase_close_ts_ns=3_000_000_000),
        ))
        self.assertIsNone(atlas.atoms["time_to_mfe_ns"][0])
        spec = next(x for x in PROBE_REGISTRY if x.cell == 6)
        target = materialize_probe_target(atlas, spec)
        self.assertFalse(bool(target.coordinate_mask[0, 2]))
        prediction = torch.full((1, PADDED_OUTPUT_WIDTH), .3, requires_grad=True)
        loss_for_probe(spec, prediction, target).backward()
        self.assertEqual(float(prediction.grad[0, 2]), 0.0)
        self.assertNotEqual(float(prediction.grad[0, 1]), 0.0)

    def test_c11_undetermined_slope_is_masked_not_zero(self):
        atlas = _index((1000,), ts=(1_000_000_000,)).materialize((_anchor(),))
        spec = next(x for x in PROBE_REGISTRY if x.cell == 11)
        target = materialize_probe_target(atlas, spec)
        self.assertFalse(bool(target.coordinate_mask[0, 0]))
        prediction = torch.full((1, PADDED_OUTPUT_WIDTH), .3, requires_grad=True)
        loss_for_probe(spec, prediction, target).backward()
        self.assertEqual(float(prediction.grad[0, 0]), 0.0)

    def test_c3_joint_and_fixed_objectives_are_distinct(self):
        atlas = _index().materialize((_anchor(),))
        fixed_spec = next(x for x in PROBE_REGISTRY if x.cell == 3 and "P01" in x.probe_id)
        joint_spec = next(x for x in PROBE_REGISTRY if x.cell == 3 and "P02" in x.probe_id)
        fixed = materialize_probe_target(atlas, fixed_spec)
        joint = materialize_probe_target(atlas, joint_spec)
        prediction = torch.linspace(-1, 1, PADDED_OUTPUT_WIDTH)[None].requires_grad_()
        fixed_loss = loss_for_probe(fixed_spec, prediction, fixed)
        joint_loss = loss_for_probe(joint_spec, prediction, joint)
        self.assertNotEqual(float(fixed_loss), float(joint_loss))

    def test_c9_likelihood_uses_passage_or_censor_time(self):
        spec = next(x for x in PROBE_REGISTRY if x.cell == 9)
        early = _index((1000, 1100), ts=(1_000_000_000, 2_000_000_000)).materialize(
            (_anchor(source_censor_ts_ns=2_000_000_000),))
        late = _index((1000, 1100), ts=(1_000_000_000, 8_000_000_000)).materialize(
            (_anchor(source_censor_ts_ns=8_000_000_000),))
        prediction = torch.zeros((1, PADDED_OUTPUT_WIDTH), requires_grad=True)
        early_loss = loss_for_probe(spec, prediction,
                                    materialize_probe_target(early, spec))
        late_loss = loss_for_probe(spec, prediction,
                                   materialize_probe_target(late, spec))
        self.assertNotEqual(float(early_loss), float(late_loss))

    def test_c20_crps_matches_decreasing_survival_target(self):
        atlas = _index().materialize((_anchor(),))
        spec = next(x for x in PROBE_REGISTRY if x.cell == 20 and "P04" in x.probe_id)
        target = materialize_probe_target(atlas, spec)
        prediction = torch.zeros((1, PADDED_OUTPUT_WIDTH), requires_grad=True)
        scalar = loss_for_probe(spec, prediction, target)
        scalar.backward()
        self.assertTrue(torch.isfinite(scalar))
        self.assertTrue(torch.any(prediction.grad[0, :7] != 0))

    def test_competing_risk_censor_is_not_a_hard_no_event(self):
        atlas = _index((1000, 1000), ts=(1_000_000_000, 2_000_000_000)).materialize((
            _anchor(source_censor_ts_ns=3_000_000_000),
        ))
        hard_spec = next(x for x in PROBE_REGISTRY
                         if x.cell == 10 and "P01" in x.probe_id)
        hard = materialize_probe_target(atlas, hard_spec)
        prediction = torch.zeros((1, PADDED_OUTPUT_WIDTH), requires_grad=True)
        loss_for_probe(hard_spec, prediction, hard).backward()
        self.assertTrue(torch.all(prediction.grad[0, :96] == 0))
        self.assertTrue(torch.any(prediction.grad[0, 96:180] != 0))

        ipcw_spec = next(x for x in PROBE_REGISTRY
                         if x.cell == 10 and "P04" in x.probe_id)
        ipcw = materialize_probe_target(atlas, ipcw_spec, {
            "ipcw_weights": np.asarray([1.0], np.float32),
            "fit_population_sha256": "d" * 64,
        })
        prediction = torch.zeros((1, PADDED_OUTPUT_WIDTH), requires_grad=True)
        loss_for_probe(ipcw_spec, prediction, ipcw).backward()
        self.assertTrue(torch.any(prediction.grad[0, 96:120] != 0))
        self.assertTrue(torch.any(prediction.grad[0, 120:180] != 0))

    def test_every_competing_variant_trains_all_clock_and_endpoint_axes(self):
        atlas = _index().materialize((_anchor(),))
        for spec in (row for row in PROBE_REGISTRY if row.cell in (10, 24)):
            with self.subTest(probe=spec.probe_id):
                target = materialize_probe_target(atlas, spec)
                prediction = torch.full(
                    (1, PADDED_OUTPUT_WIDTH), .137, requires_grad=True
                )
                loss_for_probe(spec, prediction, target).backward()
                self.assertTrue(torch.any(prediction.grad[0, 96:120] != 0))
                self.assertTrue(torch.any(prediction.grad[0, 120:132] != 0))
                self.assertTrue(torch.any(prediction.grad[0, 132:180] != 0))


if __name__ == "__main__":
    unittest.main()
