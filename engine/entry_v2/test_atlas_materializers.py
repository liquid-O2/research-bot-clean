#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType
import unittest
import numpy as np

from .atlas_materializers import (
    apply_recipient_fixed_singleton_drop,
    COMPETING_PAIR_AXES, SINGLETON_DROP_REFUSAL_FRACTION,
    materialize_probe_target, permute_probe_target_recipient_fixed,
    recipient_fixed_real_and_twin, singleton_drop_census,
    stage_global_recipient_fixed_permutation,
)
from .causal_label_atlas import (
    AtlasRefusal, CellAvailability, E1_PROBE_FIT_BUDGET,
    MAX_THROUGH_E2_PROBE_FIT_BUDGET,
    PADDED_OUTPUT_WIDTH, PROBE_REGISTRY, SHUFFLED_PROBES, ProbeTarget,
    probe_target_receipt,
)
from .test_causal_label_atlas import _anchor, _index


class AtlasMaterializerTest(unittest.TestCase):
    @staticmethod
    def _fit_context():
        return {"fit_population_sha256": "f" * 64,
                "c1_location": np.zeros(21), "c1_scale": np.ones(21),
                "location": np.zeros(12), "scale": np.ones(12),
                "lower": np.full(12, -1000.0), "upper": np.full(12, 1000.0),
                "rank_reference": np.zeros((3, 12))}

    def _atlas(self):
        return _index().materialize((
            _anchor("a", exact_time_group_id="g", take_target=True,
                    now_wait_pass_regret_units=(1,2,3),
                    shadow_marginal_regret_units=(4,5),
                    process_utility_units=6),
            _anchor("b", exact_time_group_id="g", entry_mid2=1010,
                    now_wait_pass_regret_units=(3,2,1),
                    shadow_marginal_regret_units=(5,4),
                    process_utility_units=7),
        ))

    def _wide_atlas(self, n):
        atlas = self._atlas()
        groups = np.empty(n, dtype=object)
        groups[:] = [("SI", 20250102, row, f"row-{row}") for row in range(n)]
        atoms = MappingProxyType({
            "availability": np.full(n, CellAvailability.MATERIALIZED, object),
            "final_units": np.zeros(n, object),
            "vertical_units": np.zeros((n, 12), object),
            "vertical_mask": np.ones((n, 12), bool),
            "action_loss_mask": np.ones(n, bool),
            "take_target": np.arange(n) % 2 == 0,
            "exact_time_group_id": groups,
        })
        return replace(
            atlas, candidate_ids=tuple(f"candidate-{row}" for row in range(n)),
            anchors=(atlas.anchors[0],) * n, atoms=atoms,
        )

    def test_all_44_numeric_padded_targets_and_golden_masks(self):
        atlas = self._atlas()
        fit = self._fit_context()
        for spec in (*PROBE_REGISTRY, *SHUFFLED_PROBES):
            with self.subTest(probe=spec.probe_id):
                target = materialize_probe_target(atlas, spec, fit)
                self.assertIsInstance(target, ProbeTarget)
                self.assertEqual(target.values.shape, (2, PADDED_OUTPUT_WIDTH))
                self.assertNotEqual(target.values.dtype, object)
                self.assertEqual(target.coordinate_mask.shape, target.values.shape)
                self.assertTrue(np.isfinite(target.values).all())
                self.assertEqual(len(target.schema_sha256), 64)
                if spec.cell == 3:
                    self.assertEqual(target.output_width, 12)
                if spec.cell == 22 and "P01" not in spec.probe_id:
                    self.assertEqual(len(target.transform_provenance_sha256), 64)
                if spec.cell == 11:
                    self.assertEqual(target.prediction_width, 30)
                if spec.cell in (10, 24):
                    self.assertEqual(target.output_width, 72)
                    self.assertEqual(target.prediction_width, 180)
        c14 = materialize_probe_target(
            atlas, next(x for x in PROBE_REGISTRY if x.cell == 14)
        )
        self.assertEqual(c14.values[:, 0].tolist(), [1.0, 0.0])
        self.assertEqual(c14.validity_mask.tolist(), [True, True])

    def test_c16_c17_are_materialized_from_global_schedule_truth(self):
        atlas = self._atlas()
        for cell in (16, 17):
            target = materialize_probe_target(
                atlas, next(x for x in PROBE_REGISTRY if x.cell == cell)
            )
            self.assertIs(target.state, CellAvailability.MATERIALIZED)
            self.assertEqual(target.validity_mask.tolist(), [True, True])
            self.assertTrue(np.isfinite(target.values).all())
        c16 = materialize_probe_target(
            atlas, next(x for x in PROBE_REGISTRY if x.cell == 16)
        )
        np.testing.assert_allclose(
            c16.values[:, :3], np.asarray(((1, 2, 3), (3, 2, 1))) / 2_000_000_000
        )
        unavailable = _index().materialize((_anchor(),))
        for cell in (16, 17):
            target = materialize_probe_target(
                unavailable, next(x for x in PROBE_REGISTRY if x.cell == cell)
            )
            self.assertIs(target.state,
                          CellAvailability.UNAVAILABLE_SOURCE_SEMANTICS)
            self.assertFalse(target.validity_mask.any())

    def test_declared_terminal_states_quantiles_and_modal_are_distinct(self):
        atlas = self._atlas()
        c4_state = materialize_probe_target(
            atlas, next(x for x in PROBE_REGISTRY
                        if x.cell == 4 and "P01" in x.probe_id)
        )
        c4_ordinal = materialize_probe_target(
            atlas, next(x for x in PROBE_REGISTRY
                        if x.cell == 4 and "P02" in x.probe_id)
        )
        self.assertEqual(c4_state.output_layout,
                         ("loss", "zero_to_600", "600_to_1000",
                          "1000_to_2000", "ge_2000"))
        self.assertEqual(c4_ordinal.output_width, 4)
        quantile = materialize_probe_target(
            atlas, next(x for x in PROBE_REGISTRY
                        if x.cell == 20 and "P01" in x.probe_id)
        )
        self.assertEqual(quantile.output_width, 7)
        modal = materialize_probe_target(
            atlas, next(x for x in PROBE_REGISTRY
                        if x.cell == 21 and "P01" in x.probe_id)
        )
        goal = materialize_probe_target(
            atlas, next(x for x in PROBE_REGISTRY
                        if x.cell == 21 and "P02" in x.probe_id)
        )
        self.assertEqual((modal.output_width, goal.output_width), (5, 1))
        self.assertNotEqual(modal.schema_sha256, goal.schema_sha256)

    def test_competing_risk_factorizes_every_horizontal_pair_and_vertical(self):
        self.assertEqual(len(COMPETING_PAIR_AXES), 24)
        self.assertEqual(len(set(COMPETING_PAIR_AXES)), 24)
        atlas = self._atlas()
        for cell in (10, 24):
            target = materialize_probe_target(
                atlas, next(x for x in PROBE_REGISTRY
                            if x.cell == cell and "P01" in x.probe_id)
            )
            self.assertEqual((target.output_width, target.prediction_width),
                             (72, 180))
            self.assertEqual(target.output_layout[0], "pair0_cause")
            self.assertEqual(target.output_layout[24], "pair0_log_time")
            self.assertEqual(target.output_layout[48], "vertical0_log_time")
            self.assertEqual(target.prediction_layout[120], "vertical0_log_time")
            self.assertEqual(target.prediction_layout[132],
                             "vertical0_status_logit0")
            self.assertEqual(target.prediction_layout[179],
                             "vertical11_status_logit3")
            self.assertTrue(target.coordinate_mask[:, :48].any())

    def test_c15_large_singleton_roster_uses_linear_group_index(self):
        n = 4096
        atlas = self._atlas()
        groups = np.empty(n, dtype=object)
        groups[:] = [("SI", 20250102, row, f"singleton-{row}")
                     for row in range(n)]
        atoms = MappingProxyType({
            "availability": np.full(n, CellAvailability.MATERIALIZED, object),
            "final_units": np.zeros(n, object),
            "vertical_units": np.zeros((n, 12), object),
            "vertical_mask": np.ones((n, 12), bool),
            "action_loss_mask": np.ones(n, bool),
            "take_target": np.zeros(n, bool),
            "exact_time_group_id": groups,
        })
        singleton_atlas = replace(
            atlas,
            candidate_ids=tuple(f"candidate-{row}" for row in range(n)),
            anchors=(atlas.anchors[0],) * n,
            atoms=atoms,
        )
        target = materialize_probe_target(
            singleton_atlas, next(x for x in PROBE_REGISTRY if x.cell == 15)
        )
        self.assertIs(target.state, CellAvailability.UNAVAILABLE_LOW_SUPPORT)
        self.assertFalse(target.validity_mask.any())
        self.assertTrue(np.all(target.group_id == -1))

    def test_registry_declares_real_support_families(self):
        self.assertFalse(any(row.support_id == "support.development_only"
                             for row in PROBE_REGISTRY))
        self.assertEqual(
            next(row.support_id for row in PROBE_REGISTRY if row.cell == 15),
            "support.exact_time_ranking",
        )

    def test_global_shuffle_preserves_recipient_mask_and_marginals(self):
        stage = ["FIT"] * 8; asset = ["SI"] * 8
        day = [1,1,2,2,1,1,2,2]; mask = [True]*4 + [False]*4
        permutation = stage_global_recipient_fixed_permutation(
            stage, asset, day, mask, materialized=[True] * 8, seed=17
        )
        self.assertTrue(np.all(permutation != np.arange(8)))
        self.assertEqual(np.asarray(mask)[permutation].tolist(), mask)
        values = np.arange(8)
        self.assertEqual(sorted(values[permutation].tolist()), values.tolist())

        # V13: availability is a stratum key, so every mask/censor/at-risk/
        # weight array a recipient keeps is its own.  A materialized recipient
        # can never receive an unavailable donor's row.
        availability = [True, False, True, False, True, False, True, False]
        typed = stage_global_recipient_fixed_permutation(
            stage, asset, [1] * 8, [True] * 8,
            materialized=availability, seed=17,
        )
        supported = typed >= 0
        self.assertTrue(supported.any())
        self.assertEqual(np.asarray(availability)[typed[supported]].tolist(),
                         np.asarray(availability)[supported].tolist())

        atlas = self._atlas()
        target = materialize_probe_target(
            atlas, next(x for x in PROBE_REGISTRY if x.cell == 14)
        )
        shuffled = permute_probe_target_recipient_fixed(target, [1, 0])
        self.assertEqual(shuffled.values[:, 0].tolist(), [0.0, 1.0])
        for name in ("coordinate_mask", "coordinate_at_risk", "coordinate_censor",
                     "validity_mask", "at_risk_mask", "censor_mask",
                     "fit_weight", "group_id", "group_size"):
            with self.subTest(array=name):
                np.testing.assert_array_equal(getattr(shuffled, name),
                                              getattr(target, name))

        singleton = stage_global_recipient_fixed_permutation(
            ["FIT", "FIT", "FIT"], ["SI"] * 3, [1, 1, 2],
            [True] * 3, materialized=[True] * 3, seed=17,
        )
        self.assertEqual(singleton[2], -1)
        singleton_target = permute_probe_target_recipient_fixed(
            materialize_probe_target(
                self._atlas(), next(x for x in PROBE_REGISTRY if x.cell == 14)
            ), [1, -1],
        )
        self.assertFalse(singleton_target.validity_mask[1])

    def test_singleton_drop_is_symmetric_across_real_and_twin(self):
        # C1: a singleton stratum row is unusable for the twin.  If the REAL
        # target keeps it, the real fits on more supported rows than its twin
        # and real-minus-twin is biased positive by construction.
        atlas = self._atlas()
        spec = next(x for x in PROBE_REGISTRY if x.cell == 14)
        target = materialize_probe_target(atlas, spec)
        self.assertEqual(target.validity_mask.tolist(), [True, True])
        real = apply_recipient_fixed_singleton_drop(target, [1, -1])
        twin = permute_probe_target_recipient_fixed(target, [1, -1])
        self.assertEqual(real.validity_mask.tolist(), twin.validity_mask.tolist())
        self.assertFalse(bool(real.validity_mask[1]))
        self.assertEqual(float(real.fit_weight[1]), 0.0)
        self.assertEqual(float(twin.fit_weight[1]), 0.0)
        self.assertEqual(real.values[1].tolist(), twin.values[1].tolist())
        self.assertEqual(float(real.values[1, 0]), 0.0)
        np.testing.assert_array_equal(real.coordinate_mask[1], False)
        # The real row that survives keeps its own real value.
        self.assertEqual(float(real.values[0, 0]), float(target.values[0, 0]))

        # The paired accessor returns the row-identical triple and receipts the
        # dropped-singleton census.
        wide = self._wide_atlas(100)
        wide_target = materialize_probe_target(wide, spec)
        permutation = np.roll(np.arange(100), 1)
        permutation[:5] = -1
        wide_real, wide_twin, census = recipient_fixed_real_and_twin(
            wide_target, permutation)
        np.testing.assert_array_equal(wide_real.validity_mask,
                                      wide_twin.validity_mask)
        self.assertFalse(bool(wide_real.validity_mask[:5].any()))
        self.assertEqual(census.dropped_singleton_rows, 5)
        self.assertEqual(census.dropped_row_indices, (0, 1, 2, 3, 4))
        self.assertEqual(census.total_rows, 100)
        self.assertEqual(census.refusal_fraction, SINGLETON_DROP_REFUSAL_FRACTION)
        self.assertEqual(SINGLETON_DROP_REFUSAL_FRACTION, 0.05)
        self.assertEqual(census.receipt["dropped_singleton_rows"], 5)
        self.assertEqual(len(census.receipt_sha256), 64)

        # A drop census above the frozen fraction refuses; exactly at the
        # frozen fraction it is retained and receipted.
        with self.assertRaisesRegex(AtlasRefusal, "singleton"):
            singleton_drop_census([-1] * 6 + list(range(6, 100)))
        boundary = singleton_drop_census([-1] * 5 + list(range(5, 100)))
        self.assertEqual(boundary.dropped_singleton_rows, 5)
        self.assertAlmostEqual(boundary.dropped_fraction, 0.05)

    def test_ipcw_requires_external_fit_for_censored_risk(self):
        atlas = _index((1000, 1000), ts=(1_000_000_000, 2_000_000_000)).materialize((_anchor(
            source_censor_ts_ns=3_000_000_000,
        ),))
        for cell, probe in ((10, "P04"), (24, "P02")):
            spec = next(x for x in PROBE_REGISTRY
                        if x.cell == cell and probe in x.probe_id)
            unavailable = materialize_probe_target(atlas, spec)
            self.assertIs(unavailable.state,
                          CellAvailability.UNAVAILABLE_SOURCE_SEMANTICS)
            fitted = materialize_probe_target(atlas, spec, {
                "ipcw_weights": np.asarray([2.5]),
                "fit_population_sha256": "c" * 64,
            })
            self.assertEqual(fitted.fit_weight.tolist(), [2.5])
            self.assertEqual(len(fitted.transform_provenance_sha256), 64)

        survival = materialize_probe_target(
            atlas, next(x for x in PROBE_REGISTRY if x.cell == 9)
        )
        self.assertGreater(survival.values[0, 0], 0)
        self.assertTrue(survival.censor_mask[0])

    def test_columnwise_rank_uses_only_frozen_fit_reference(self):
        atlas = self._atlas()
        spec = next(x for x in PROBE_REGISTRY
                    if x.cell == 22 and "P04" in x.probe_id)
        low = materialize_probe_target(atlas, spec, {
            "fit_population_sha256": "d" * 64,
            "rank_reference": np.full((3, 12), -1e6),
        })
        high = materialize_probe_target(atlas, spec, {
            "fit_population_sha256": "e" * 64,
            "rank_reference": np.full((3, 12), 1e6),
        })
        self.assertTrue(np.all(low.values[:, :12] >= high.values[:, :12]))
        self.assertNotEqual(low.schema_sha256, high.schema_sha256)

    def test_fit_provenance_binds_population_parameters_and_concrete_layout(self):
        atlas = self._atlas(); spec = next(x for x in PROBE_REGISTRY if x.cell == 1)
        base = self._fit_context()
        one = materialize_probe_target(atlas, spec, base)
        changed_population = dict(base, fit_population_sha256="e" * 64)
        two = materialize_probe_target(atlas, spec, changed_population)
        changed_parameter = dict(base, c1_scale=np.full(21, 2.0))
        three = materialize_probe_target(atlas, spec, changed_parameter)
        self.assertNotEqual(one.transform_provenance_sha256,
                            two.transform_provenance_sha256)
        self.assertNotEqual(one.transform_provenance_sha256,
                            three.transform_provenance_sha256)
        receipt = probe_target_receipt(spec, one)
        self.assertEqual(receipt["concrete_target_schema_sha256"], one.schema_sha256)
        self.assertEqual(receipt["prediction_layout"], list(one.prediction_layout))

    def test_exact_budget_accounting(self):
        self.assertEqual(E1_PROBE_FIT_BUDGET, 90)
        self.assertEqual(MAX_THROUGH_E2_PROBE_FIT_BUDGET, 98)
        self.assertEqual(self._atlas().max_through_e2_fit_budget, 98)


if __name__ == "__main__":
    unittest.main()
