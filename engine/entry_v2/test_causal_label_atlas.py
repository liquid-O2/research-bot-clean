#!/usr/bin/env python3
"""Mechanical and tiny-oracle tests for the columnar causal label atlas."""

from __future__ import annotations

from dataclasses import replace
import time
import unittest

import numpy as np

from .causal_label_atlas import (
    ActionMaskCause, AtlasRefusal, BoundaryReason, CandidateAnchor, CanonicalOutcome,
    CellAvailability, DEVELOPMENT_CUTOFF_NS, EndpointStatus,
    PNL_UNITS_PER_USD, PROBE_REGISTRY, PassageState, SHUFFLED_PROBES,
    SessionTruthIndex, _WeightedRangeIndex, atlas_receipt_bytes, registry_bytes,
    shuffled_probe_for,
)


SECOND = 1_000_000_000


def _index(mid2=(1000, 1020, 1300, 900, 1600, 500), *,
           ts=None, ordinal=None, generation=None, trusted=None, sane=None,
           message=None, sequence=None, phase=None):
    n = len(mid2)
    ts = np.asarray(ts if ts is not None else np.arange(1, n + 1) * SECOND,
                    dtype=np.uint64)
    columns = dict(
        ts_recv_ns=ts,
        source_ordinal=np.asarray(ordinal if ordinal is not None else np.zeros(n),
                                  dtype=np.uint32),
        trusted_message=np.asarray(
            message if message is not None else np.ones(n), bool
        ),
        trusted_economic=np.asarray(trusted if trusted is not None else np.ones(n), bool),
        sane_bbo=np.asarray(sane if sane is not None else np.ones(n), bool),
        generation=np.asarray(generation if generation is not None else np.ones(n),
                              dtype=np.int64),
        mid2=np.asarray(mid2, dtype=np.int64),
        action=np.arange(n, dtype=np.int16), side=np.resize([-1, 1], n),
        flags=np.arange(n, dtype=np.uint32), depth=np.ones(n, np.int16),
        missing_mask=np.zeros(n, np.uint32), spread_mask=np.zeros(n, np.uint32),
        price=np.asarray(mid2, np.int64), bid_px=np.asarray(mid2, np.int64)-1,
        ask_px=np.asarray(mid2, np.int64)+1, size=np.arange(n, dtype=np.int64)+3,
        bid_size=np.arange(n, dtype=np.int64) + 1,
        ask_size=np.arange(n, dtype=np.int64) + 2,
        bid_count=np.arange(n, dtype=np.int64)+4,
        ask_count=np.arange(n, dtype=np.int64)+5,
        ts_in_delta=np.arange(n, dtype=np.int64)+6,
        receive_session_sec=np.arange(n, dtype=np.int64)+7,
        sequence=np.asarray(sequence if sequence is not None else np.arange(n),
                            dtype=np.int64),
        ts_event_ns=ts.astype(np.int64) - 7,
    )
    if phase is not None:
        phase_open, phase_close, phase_ceiling = phase
        columns.update(
            phase_open_ts_ns=np.asarray(phase_open, dtype=np.int64),
            phase_close_ts_ns=np.asarray(phase_close, dtype=np.int64),
            phase_sane_ceiling_units=np.asarray(phase_ceiling, dtype=np.int64),
        )
    return SessionTruthIndex(**columns)


def _anchor(candidate_id="c", **changes):
    values = dict(
        candidate_id=candidate_id, decision_ts_ns=SECOND, side=1,
        entry_mid2=1000, multiplier=PNL_UNITS_PER_USD,
        frozen_cost_units=0, phase_close_ts_ns=6 * SECOND,
        source_ordinal=0, generation=1,
    )
    values.update(changes)
    return CandidateAnchor(**values)


class CausalLabelAtlasTest(unittest.TestCase):
    def test_real_to_twin_accessor_is_exact_and_roster_validated(self):
        for real, twin in zip(PROBE_REGISTRY, SHUFFLED_PROBES):
            self.assertEqual(shuffled_probe_for(real), twin)
            self.assertEqual(
                shuffled_probe_for(real, available=SHUFFLED_PROBES), twin)
        with self.assertRaisesRegex(AtlasRefusal, "real probe"):
            shuffled_probe_for(SHUFFLED_PROBES[0])
        with self.assertRaisesRegex(AtlasRefusal, "exact registered shuffled twin"):
            shuffled_probe_for(PROBE_REGISTRY[0], available=SHUFFLED_PROBES[1:])
        corrupted = replace(SHUFFLED_PROBES[0], cell=24)
        with self.assertRaisesRegex(AtlasRefusal, "exact registered shuffled twin"):
            shuffled_probe_for(
                PROBE_REGISTRY[0], available=(corrupted, *SHUFFLED_PROBES[1:]))

    def test_binding_adapter_preserves_exact_authoritative_inputs(self):
        anchor = CandidateAnchor.from_binding(
            candidate_id="bound", decision_ts_ns=SECOND, side=-1,
            entry_mid2=1001, multiplier=17, frozen_cost_units=19,
            phase_close_ts_ns=9 * SECOND, source_ordinal=3,
            generation_at_cutoff=7, canonical_terminal=None,
            action_mask_cause=ActionMaskCause.A004_CAP,
            prior_scale_units=23, authoritative_teacher_action=True,
            asset="SI", trading_day=20250102,
        )
        self.assertEqual((anchor.entry_mid2, anchor.multiplier,
                          anchor.frozen_cost_units, anchor.generation),
                         (1001, 17, 19, 7))
        self.assertIs(anchor.action_mask_cause, ActionMaskCause.A004_CAP)
        self.assertTrue(anchor.authoritative_teacher_action)
        self.assertFalse(anchor.action_loss_mask)
        self.assertFalse(anchor.take_target)

    def test_sparse_after_horizon_and_economic_carry_vs_censor(self):
        index = _index((1000, 1100), ts=(SECOND, 3 * SECOND))
        censored = index.materialize((_anchor(phase_close_ts_ns=5 * SECOND),))
        endpoint = censored.atoms["fixed_endpoints"][0]["1s"]
        self.assertEqual(endpoint["value_units"], 100 * PNL_UNITS_PER_USD)
        self.assertIs(endpoint["status"], EndpointStatus.OBSERVED)
        carried = index.materialize((_anchor(
            candidate_id="exit", economic_exit_ts_ns=SECOND,
            phase_close_ts_ns=30 * SECOND,
        ),))
        self.assertIs(
            carried.atoms["fixed_endpoints"][0]["10s"]["status"],
            EndpointStatus.CARRIED_FORWARD,
        )

    def test_equal_clocks_are_ordered_and_phase_is_inclusive(self):
        index = _index((1000, 1010, 1020),
                       ts=(SECOND, 2 * SECOND, 2 * SECOND),
                       ordinal=(0, 1, 2))
        result = index.materialize((_anchor(phase_close_ts_ns=2 * SECOND),))
        self.assertEqual(result.atoms["final_units"][0], 20 * PNL_UNITS_PER_USD)
        self.assertEqual(result.atoms["terminal_key"][0][0], 2 * SECOND)

    def test_candidate_phase_query_has_full_path_and_canonical_parity(self):
        low, high = 25 * PNL_UNITS_PER_USD, 100 * PNL_UNITS_PER_USD
        index = _index(
            (1000, 9999, 9999, 1020, 980),
            ts=(4 * SECOND, 5 * SECOND, 5 * SECOND, 6 * SECOND, 7 * SECOND),
            ordinal=(0, 1, 2, 0, 0), sane=(True, False, False, True, True),
            phase=(
                (0, 0, 0, 5 * SECOND, 5 * SECOND),
                (5 * SECOND, 5 * SECOND, 5 * SECOND, 10 * SECOND, 10 * SECOND),
                (low, low, low, high, high),
            ),
        )
        prior = _anchor(
            "prior", decision_ts_ns=4 * SECOND, phase_close_ts_ns=5 * SECOND,
            phase_open_ts_ns=0, sane_ceiling_units=low,
            canonical=CanonicalOutcome(
                CellAvailability.MATERIALIZED, 4 * SECOND, 0,
                BoundaryReason.PHASE, 0, False, 0, 0,
            ),
        )
        next_phase = _anchor(
            "next", decision_ts_ns=5 * SECOND, phase_close_ts_ns=10 * SECOND,
            phase_open_ts_ns=5 * SECOND, sane_ceiling_units=high,
            canonical=CanonicalOutcome(
                CellAvailability.MATERIALIZED, 7 * SECOND, 0,
                BoundaryReason.PHASE, -20 * PNL_UNITS_PER_USD, False,
                20 * PNL_UNITS_PER_USD, 20 * PNL_UNITS_PER_USD,
            ),
        )
        result = index.materialize((prior, next_phase))

        self.assertEqual(result.atoms["final_units"].tolist(),
                         [0, -20 * PNL_UNITS_PER_USD])
        self.assertEqual(result.atoms["mfe_units"].tolist(),
                         [0, 20 * PNL_UNITS_PER_USD])
        self.assertEqual(result.atoms["mae_units"].tolist(),
                         [0, 20 * PNL_UNITS_PER_USD])
        self.assertEqual(result.atoms["mixed_targets"][1]["next_event"]["sequence"], 3)
        self.assertFalse(result.atoms["mixed_targets"][1]["next_event"][
            "sequence_gap_valid"
        ])
        self.assertEqual(
            result.atoms["fixed_endpoints"][1]["1s"]["value_units"],
            20 * PNL_UNITS_PER_USD,
        )
        self.assertEqual(index.suffix_row_visits, 0)

    def test_phase_query_clamps_generation_and_preserves_source_censor(self):
        ceiling = 25 * PNL_UNITS_PER_USD
        index = _index(
            (1000, 1010, 1020, 1030),
            ts=(SECOND, 2 * SECOND, 3 * SECOND, 4 * SECOND),
            generation=(1, 1, 2, 2),
            phase=(
                (0, 0, 2 * SECOND, 2 * SECOND),
                (2 * SECOND, 2 * SECOND, 5 * SECOND, 5 * SECOND),
                (ceiling, ceiling, ceiling, ceiling),
            ),
        )
        prior = _anchor(
            "prior-generation", phase_close_ts_ns=2 * SECOND,
            phase_open_ts_ns=0, sane_ceiling_units=ceiling, generation=1,
        )
        censored = _anchor(
            "source", decision_ts_ns=2 * SECOND, phase_close_ts_ns=5 * SECOND,
            phase_open_ts_ns=2 * SECOND, sane_ceiling_units=ceiling, generation=2,
            source_censor_ts_ns=4 * SECOND, source_censor_ordinal=0,
        )
        result = index.materialize((prior, censored))

        self.assertIs(result.atoms["boundary_reason"][0], BoundaryReason.PHASE)
        self.assertIs(result.atoms["boundary_reason"][1], BoundaryReason.SOURCE)
        self.assertIs(result.atoms["availability"][1], CellAvailability.RIGHT_CENSORED)
        self.assertIsNone(result.atoms["fixed_endpoints"][1]["FINAL"]["value_units"])
        self.assertEqual(index.suffix_row_visits, 0)

    def test_automatic_wall_and_canonical_byte_unit_parity(self):
        index = _index((1000, 50, 1600))
        base = _anchor()
        result = index.materialize((base,))
        self.assertTrue(result.atoms["wall_hit"][0])
        self.assertIs(result.atoms["boundary_reason"][0], BoundaryReason.WALL)
        correct = CanonicalOutcome(
            CellAvailability.MATERIALIZED, 2 * SECOND, 0, BoundaryReason.WALL,
            -950 * PNL_UNITS_PER_USD, True, 0, 950 * PNL_UNITS_PER_USD,
        )
        index.materialize((replace(base, candidate_id="ok", canonical=correct),))
        with self.assertRaisesRegex(AtlasRefusal, "byte/unit parity"):
            index.materialize((replace(base, candidate_id="bad",
                                       canonical=replace(correct, final_net_units=1)),))

    def test_barriers_censor_masks_and_cif_risk_set(self):
        ready = _index().materialize((_anchor(),))
        barriers = ready.atoms["barriers"][0]
        self.assertTrue(barriers["risk_set"])
        self.assertTrue(barriers["cif_mask"])
        empty = _index((), ts=()).materialize((_anchor(candidate_id="empty"),))
        self.assertIs(empty.atoms["availability"][0], CellAvailability.NO_SANE_SUFFIX)
        self.assertIs(empty.atoms["boundary_reason"][0], BoundaryReason.NO_SANE_SUFFIX)

    def test_mfe_mae_extreme_times_and_fourteen_rungs(self):
        result = _index().materialize((_anchor(),))
        self.assertEqual(result.atoms["mfe_units"][0], 600 * PNL_UNITS_PER_USD)
        self.assertEqual(result.atoms["mae_units"][0], 500 * PNL_UNITS_PER_USD)
        self.assertEqual(result.atoms["time_to_mfe_ns"][0], 4 * SECOND)
        self.assertEqual(result.atoms["time_to_mae_ns"][0], 5 * SECOND)
        scaled = _index().materialize((_anchor(sigma_prior_units=100 * PNL_UNITS_PER_USD),))
        self.assertEqual(len(scaled.atoms["rung_touches"][0]), 14)
        self.assertTrue(any(row["state"] is PassageState.ATTAINED
                            for row in scaled.atoms["rung_touches"][0]))

    def test_hand_path_stats_trends_and_mixed_targets(self):
        result = _index((1000, 1100, 1200, 1300)).materialize((
            _anchor(phase_close_ts_ns=4 * SECOND),
        ))
        occupation = result.atoms["occupation"][0]
        self.assertGreaterEqual(occupation["duration_seconds"], 0)
        self.assertGreater(occupation["signed_area_units_seconds"], 0)
        self.assertGreater(result.atoms["trends"][0]["10s"]["slope_units_per_sec"], 0)
        mixed = result.atoms["mixed_targets"][0]
        self.assertEqual(mixed["next_event"]["sequence"], 0)
        self.assertEqual(mixed["counts"]["10s"], 4)

    def test_sequence_gap_is_relative_and_axes_are_fixed_columnar(self):
        result = _index((1000, 1010, 1020), sequence=(10, 17, 25)).materialize((
            _anchor(decision_ts_ns=2 * SECOND),
        ))
        self.assertEqual(result.atoms["mixed_targets"][0]["next_event"]["sequence_gap"], 7)
        self.assertEqual(result.atoms["vertical_units"].shape, (1, 12))
        self.assertEqual(result.atoms["rung_event"].shape, (1, 14))
        self.assertEqual(result.atoms["rung_at_risk"].shape, (1, 14))

    def test_short_wall_touch_and_right_censor_final_mask(self):
        short = _index((1000, 1950, 500)).materialize((
            _anchor(side=-1),
        ))
        self.assertTrue(short.atoms["wall_hit"][0])
        self.assertTrue(any(
            row["threshold_units"] < 0 and row["state"] is PassageState.ATTAINED
            for row in short.atoms["rung_touches"][0]
        ))
        censored = _index().materialize((_anchor(
            candidate_id="source", source_censor_ts_ns=3 * SECOND,
        ),))
        self.assertIs(censored.atoms["availability"][0], CellAvailability.RIGHT_CENSORED)
        self.assertIsNone(censored.atoms["final_units"][0])
        self.assertIsNone(censored.atoms["fixed_endpoints"][0]["FINAL"]["value_units"])

    def test_trusted_mixed_event_and_exact_occupation(self):
        index = _index(
            (1000, 9999, 1100, 900, 1000),
            ts=(SECOND, SECOND + 1, 2 * SECOND, 3 * SECOND, 4 * SECOND),
            ordinal=(0, 1, 0, 0, 0),
            trusted=(True, False, True, True, True),
        )
        result = index.materialize((_anchor(phase_close_ts_ns=4 * SECOND),))
        mixed = result.atoms["mixed_targets"][0]
        self.assertTrue(mixed["next_event_valid"])
        self.assertEqual(mixed["counts"]["10s"], 5)
        occupation = result.atoms["occupation"][0]
        self.assertEqual(occupation["favorable_seconds"], 1.0)
        self.assertEqual(occupation["adverse_seconds"], 1.0)
        self.assertEqual(occupation["flat_seconds"], 1.0)
        self.assertEqual(occupation["underwater_seconds"], 1.0)
        self.assertEqual(occupation["signed_area_units_seconds"], 0.0)

        one_sided = _index((1000, 1100), sane=(False, False),
                           trusted=(False, False), message=(True, True)).materialize((
            _anchor(candidate_id="one-sided", phase_close_ts_ns=2 * SECOND),
        ))
        self.assertIs(one_sided.atoms["availability"][0],
                      CellAvailability.NO_SANE_SUFFIX)
        self.assertEqual(one_sided.atoms["mixed_targets"][0]["next_event"]["sequence"], 0)
        self.assertEqual(one_sided.atoms["mixed_targets"][0]["counts"]["10s"], 2)
        mixed_probe = next(row for row in PROBE_REGISTRY if row.cell == 1)
        mixed = one_sided.materialize_probe(mixed_probe, {
            "fit_population_sha256": "a" * 64,
            "c1_location": np.zeros(21), "c1_scale": np.ones(21),
        })
        self.assertEqual(mixed.validity_mask.tolist(), [True])

    def test_weighted_wavelet_exact_range_parity(self):
        values = np.asarray((3, 1, 4, 1, 5, 9, 2, 6), dtype=np.int64)
        weights = np.asarray((.5, 1., 1.5, 2., 2.5, 3., 3.5, 4.), dtype=np.float64)
        index = _WeightedRangeIndex(values, weights)
        for left in range(len(values) + 1):
            for right in range(left, len(values) + 1):
                for threshold in range(0, 11):
                    expected = float(weights[left:right][
                        values[left:right] <= threshold
                    ].sum())
                    self.assertEqual(index.weight_le(left, right, threshold), expected)

    def test_registry_44_twins_90_budget_and_all_cells(self):
        self.assertEqual(len(PROBE_REGISTRY), 44)
        self.assertEqual(len(SHUFFLED_PROBES), 44)
        self.assertEqual({row.cell for row in PROBE_REGISTRY}, set(range(1, 25)))
        materialized = _index().materialize((_anchor(),))
        self.assertEqual(materialized.fit_budget, 90)
        self.assertTrue(all(row.required_atoms for row in PROBE_REGISTRY))
        for probe in PROBE_REGISTRY:
            target = materialized.materialize_probe(probe)
            self.assertIsNotNone(target)
            self.assertEqual(target.validity_mask.shape, (1,))
        self.assertEqual(registry_bytes(), registry_bytes())
        self.assertEqual(atlas_receipt_bytes({"b": 2, "a": 1}),
                         atlas_receipt_bytes({"a": 1, "b": 2}))

    def test_exact_time_group_refusal_and_valid_group(self):
        with self.assertRaisesRegex(AtlasRefusal, "exact-time"):
            _index().materialize((_anchor("a"), _anchor("b")))
        result = _index().materialize((
            _anchor("a", exact_time_group_id="g"),
            _anchor("b", exact_time_group_id="g"),
        ))
        self.assertEqual(result.candidate_ids, ("a", "b"))

    def test_h2_preopen_guard_abstraction(self):
        with self.assertRaisesRegex(AtlasRefusal, "H2"):
            _index((1000,), ts=(DEVELOPMENT_CUTOFF_NS,))
        with self.assertRaisesRegex(AtlasRefusal, "H2"):
            _index((1000,), ts=(DEVELOPMENT_CUTOFF_NS + 1,))
        with self.assertRaisesRegex(AtlasRefusal, "development"):
            _index().materialize((_anchor(decision_ts_ns=DEVELOPMENT_CUTOFF_NS + 1),))

    def test_zero_suffix_visits_and_slow_tiny_oracle_parity(self):
        mids = (1000, 1030, 980, 1200, 700, 1400)
        index = _index(mids)
        anchors = tuple(_anchor(
            f"c{i}", entry_mid2=1000 + i, exact_time_group_id="oracle"
        ) for i in range(4))
        result = index.materialize(anchors)
        self.assertGreater(index.query_work, 0)
        for row, anchor in enumerate(anchors):
            brute = [anchor.side * (mid - anchor.entry_mid2) * anchor.multiplier
                     - anchor.frozen_cost_units for mid in mids]
            terminal = next((i for i, value in enumerate(brute)
                             if value <= -900 * PNL_UNITS_PER_USD), len(brute) - 1)
            visible = brute[:terminal + 1]
            self.assertEqual(result.atoms["final_units"][row], visible[-1])
            self.assertEqual(result.atoms["mfe_units"][row], max(0, max(visible)))
            self.assertEqual(result.atoms["mae_units"][row], max(0, -min(visible)))

    def test_n_2n_scaling_is_not_suffix_quadratic(self):
        def elapsed(n):
            index = _index(tuple(1000 + (i % 101) for i in range(n)),
                           ts=tuple((i + 1) * 1000 for i in range(n)))
            anchors = tuple(_anchor(
                f"c{i}", decision_ts_ns=(i + 1) * 1000,
                phase_close_ts_ns=n * 1000,
            ) for i in range(0, n, max(1, n // 64)))
            start = time.perf_counter()
            index.materialize(anchors)
            return time.perf_counter() - start, index.query_work
        t1, visits1 = elapsed(2048)
        t2, visits2 = elapsed(4096)
        self.assertGreater(visits1, 0)
        self.assertGreater(visits2, visits1)
        self.assertLess(visits2, visits1 * 4)
        self.assertLess(t2, max(0.25, t1 * 6.0))


if __name__ == "__main__":
    unittest.main()
