#!/usr/bin/env python3
"""Synthetic laws for the one-load diagnostic input boundary."""

from __future__ import annotations

from dataclasses import replace
import unittest
from unittest import mock

import numpy as np

from . import common as C
from .diagnostic_inputs import (
    ActionDecision, ActionMaskReason, CandidateTruthBinding,
    DerivedEventFieldBuilder, DiagnosticInputRefusal, DiagnosticSession,
    OneLoadDiagnosticInput, build_candidate_truth_bindings,
    build_a004_counterfactual_atoms, build_event_truth_columns,
    detailed_a004_schedule, native_book_quality,
    frozen_chronology_split, PRODUCTION_E2, REHEARSAL_E1, REHEARSAL_E2,
    fit_only_rehearsal_windows, resolve_held_chronology,
)
from .event_pack import EVENT_DTYPE, UNDEF_PRICE


NS = 1_000_000_000


def _maps(cid="c0", asset="SI", decision=5 * NS, cutoff=5,
          cert="1000", exit_ts=7 * NS):
    candidate = {
        "candidate_id": cid, "asset": asset, "d8": "20250102",
        "decision_ts_ns": str(decision), "event_cutoff": str(cutoff),
        "prefix_last_event_ordinal": str(cutoff - 1), "phase": "TOKYO",
        "phase_open_utc": "0", "phase_close_utc": "20", "side": "1",
        "entry_bid_px": "1000000000", "entry_ask_px": "1005000000",
        "entry_mid2": "2005000000", "frozen_cost_usd": "30.125",
        "sane_ceiling_usd": "250", "compliance_status": "CLEAR",
    }
    teacher = {
        "candidate_id": cid, "asset": asset, "d8": "20250102",
        "decision_ts_ns": str(decision), "status": "READY",
        "cert_close_usd": cert, "mfe_usd": "1200.25", "mae_usd": "100.5",
        "exit_ts_ns": str(exit_ts), "wall_hit": "0", "payer": "1",
        "take_target": "1",
    }
    return candidate, teacher


def _binding(**kwargs):
    c, t = _maps(**kwargs)
    return CandidateTruthBinding.from_mappings(
        c, t, ActionDecision(False, True, ActionMaskReason.AVAILABLE_EXACT_TIME))


def _rows(n=10):
    rows = np.zeros(n, dtype=EVENT_DTYPE)
    rows["ts_recv_ns"] = np.arange(n, dtype=np.uint64) * NS
    rows["ts_event_ns"] = rows["ts_recv_ns"] - np.minimum(
        rows["ts_recv_ns"], np.uint64(100))
    rows["price"] = 1_000_000_000
    rows["bid_px"] = 1_000_000_000
    rows["ask_px"] = 1_005_000_000
    rows["size"] = 10; rows["bid_sz"] = 12; rows["ask_sz"] = 8
    rows["bid_ct"] = 3; rows["ask_ct"] = 2
    rows["sequence"] = np.arange(n); rows["receive_session_sec"] = np.arange(n)
    rows["action"] = 65; rows["side"] = 66; rows["depth"] = 0
    return rows


class DiagnosticInputsTest(unittest.TestCase):
    def test_frozen_chronology_and_portfolio_equal_value_order(self):
        october = (20211001, 20211004, 20211005, 20211006, 20211007,
                   20211008, 20211011, 20211012, 20211013, 20211014,
                   20211015, 20211018, 20211019, 20211020, 20211021,
                   20211022, 20211025, 20211026, 20211027, 20211028,
                   20211029)
        np.testing.assert_array_equal(
            frozen_chronology_split(
                np.array([20210930, 20211001, 20211012, 20211101]), "E1",
                eligible_days=october),
            ["FIT", "PLATT", "THRESHOLD", "FORWARD"])
        np.testing.assert_array_equal(
            frozen_chronology_split(
                np.array([20220311, 20220314, 20220428, 20220610]), "E2"),
            ["FIT", "PLATT", "THRESHOLD", "SELECTION"])
        np.testing.assert_array_equal(
            REHEARSAL_E1.partition(np.array([
                20210709, 20210712, 20210721, 20210809])).labels,
            ["FIT", "PLATT", "THRESHOLD", "FORWARD"])
        np.testing.assert_array_equal(
            REHEARSAL_E2.partition(np.array([
                20210813, 20210816, 20210825, 20210826,
                20210920, 20210921])).labels,
            ["FIT", "PLATT", "PLATT", "THRESHOLD", "THRESHOLD", "FORWARD"])
        self.assertEqual(dict(fit_only_rehearsal_windows("E2r")), {
            "FIT": (20210531, 20210813),
            "PLATT": (20210816, 20210825),
            "THRESHOLD": (20210826, 20210920),
            "FORWARD": (20210921, 20210930),
        })
        with self.assertRaisesRegex(DiagnosticInputRefusal, "eligible trading days"):
            frozen_chronology_split(np.array([20211001]), "E1")
        with self.assertRaisesRegex(DiagnosticInputRefusal, r"exact 7\+14"):
            frozen_chronology_split(
                np.array([20211001]), "E1", eligible_days=october[:-1])
        self.assertIs(resolve_held_chronology("E2"), PRODUCTION_E2)
        altered = replace(PRODUCTION_E2, name="ALTERED_E2", receipt_sha256="")
        with self.assertRaisesRegex(DiagnosticInputRefusal, "not frozen"):
            resolve_held_chronology(altered)
        hg = _binding(cid="z", asset="HG", cert="1000")
        si = _binding(cid="a", asset="SI", cert="1000")
        with mock.patch.object(C, "MAX_ENTRIES_PORTFOLIO_DAY", 1):
            schedule = detailed_a004_schedule((si, hg))
        self.assertTrue(schedule["z"].action_target)  # asset precedes candidate ID
        self.assertEqual(schedule["a"].reason, ActionMaskReason.PORTFOLIO_CAP)
    def test_exact_decimal_conversion_and_float_rejection(self):
        binding = _binding()
        self.assertEqual(binding.frozen_cost_units, 60_250_000_000)
        self.assertEqual(binding.mfe_units, 2_400_500_000_000)
        candidate, teacher = _maps()
        candidate["frozen_cost_usd"] = 30.125
        with self.assertRaises(DiagnosticInputRefusal):
            CandidateTruthBinding.from_mappings(
                candidate, teacher,
                ActionDecision(False, True, ActionMaskReason.AVAILABLE_EXACT_TIME))
        candidate, teacher = _maps()
        teacher["cert_close_usd"] = "0.00000000025"
        with self.assertRaises(DiagnosticInputRefusal):
            CandidateTruthBinding.from_mappings(
                candidate, teacher,
                ActionDecision(False, True, ActionMaskReason.AVAILABLE_EXACT_TIME))

    def test_detailed_schedule_causes_and_parity(self):
        winner = _binding(cid="a", cert="1000", exit_ts=10 * NS)
        loser = _binding(cid="b", cert="900", exit_ts=8 * NS)
        occupied = _binding(cid="c", decision=6 * NS, cutoff=6,
                            cert="2000", exit_ts=12 * NS)
        schedule = detailed_a004_schedule((winner, loser, occupied))
        self.assertTrue(schedule["a"].action_target)
        self.assertTrue(schedule["b"].action_loss_mask)
        self.assertEqual(schedule["c"].reason, ActionMaskReason.OCCUPANCY)
        class Label:
            def __init__(self, take, mask): self.take_target, self.action_loss_mask = take, mask
        store = {key: Label(value.action_target, value.action_loss_mask)
                 for key, value in schedule.items()}
        candidates, teachers = zip(*[_maps(cid="a", cert="1000", exit_ts=10 * NS),
                                     _maps(cid="b", cert="900", exit_ts=8 * NS),
                                     _maps(cid="c", decision=6 * NS, cutoff=6,
                                           cert="2000", exit_ts=12 * NS)])
        bound = build_candidate_truth_bindings(candidates, teachers,
                                               teacher_store=store)
        self.assertEqual([x.action_target for x in bound], [True, False, False])

    def test_a004_counterfactual_atoms_replay_now_wait_pass_and_forced_in(self):
        candidates, teachers = zip(*(
            _maps(cid="a", decision=5 * NS, cutoff=5,
                  cert="1000", exit_ts=10 * NS),
            _maps(cid="b", decision=5 * NS, cutoff=5,
                  cert="900", exit_ts=8 * NS),
            _maps(cid="c", decision=11 * NS, cutoff=11,
                  cert="800", exit_ts=12 * NS),
        ))
        bindings = build_candidate_truth_bindings(candidates, teachers)
        atoms = build_a004_counterfactual_atoms(bindings)
        unit = 2_000_000_000
        self.assertEqual(atoms["a"].now_wait_pass_regret_units,
                         (0, 1000 * unit, 1800 * unit))
        self.assertEqual(atoms["b"].now_wait_pass_regret_units,
                         (0, 900 * unit, 1700 * unit))
        self.assertEqual(atoms["b"].shadow_marginal_regret_units,
                         (100 * unit, 0))

    def test_native_snapshot_seed_one_sided_maybe_and_bad(self):
        ts = np.array([0, 0, 1, 2, 3, 4, 5, 5, 6, 7], dtype=np.int64)
        flags = np.array([40, 40, 0, 0, 0, 4, 0, 40, 0, 0], dtype=np.uint8)
        sane = np.array([0, 1, 1, 1, 0, 1, 1, 1, 1, 0], dtype=bool)
        state = native_book_quality(ts, flags, sane)
        self.assertEqual(state.generation.tolist(), [1, 1, 1, 1, 1, 2, 2, 3, 3, 3])
        self.assertFalse(state.trusted_message[2])  # post-snapshot seed
        self.assertTrue(state.trusted_message[3])
        self.assertTrue(state.trusted_message[4])   # message trusted though one-sided/insane
        self.assertFalse(state.trusted_economic[4])
        self.assertFalse(state.trusted_message[6])  # tainted until snapshot
        self.assertFalse(state.trusted_message[8])  # post-snapshot seed
        self.assertTrue(state.trusted_message[9])
        self.assertFalse(state.trusted_economic[9])
        with self.assertRaises(DiagnosticInputRefusal):
            native_book_quality(np.array([1]), np.array([8], dtype=np.uint8),
                                np.array([True]))

    def test_phase_ceiling_tick_grid_and_no_object_columns(self):
        rows = _rows()
        rows[3,]["ask_px"] = 1_005_000_001  # off SI raw tick
        rows[4,]["ask_px"] = 1_100_000_000  # $500 spread > $250 ceiling
        truth = build_event_truth_columns(rows, "SI", (_binding(),))
        self.assertTrue(truth["sane"][2])
        self.assertFalse(truth["sane"][3])
        self.assertFalse(truth["sane"][4])
        self.assertTrue(all(not x.dtype.hasobject for x in truth.columns.values()))

    def test_shared_close_is_owned_by_prior_phase_with_its_ceiling(self):
        rows = _rows(8)
        rows[6]["ts_recv_ns"] = 5 * NS
        rows[5:7]["ask_px"] = 1_010_000_000  # $50: fails $25, passes $100.

        first_candidate, first_teacher = _maps(
            cid="prior", decision=4 * NS, cutoff=4, exit_ts=5 * NS,
        )
        first_candidate.update({
            "phase": "PRIOR", "phase_open_utc": "0", "phase_close_utc": "5",
            "sane_ceiling_usd": "25",
        })
        second_candidate, second_teacher = _maps(
            cid="next", decision=5 * NS, cutoff=5, exit_ts=7 * NS,
        )
        second_candidate.update({
            "phase": "NEXT", "phase_open_utc": "5", "phase_close_utc": "10",
            "sane_ceiling_usd": "100",
        })
        action = ActionDecision(False, True, ActionMaskReason.AVAILABLE_EXACT_TIME)
        bindings = (
            CandidateTruthBinding.from_mappings(first_candidate, first_teacher, action),
            CandidateTruthBinding.from_mappings(second_candidate, second_teacher, action),
        )
        truth = build_event_truth_columns(rows, "SI", bindings)

        self.assertEqual(truth["phase_open_ts_ns"][5:7].tolist(), [0, 0])
        self.assertEqual(truth["phase_close_ts_ns"][5:7].tolist(), [5 * NS, 5 * NS])
        self.assertEqual(
            truth["phase_sane_ceiling_units"][5:7].tolist(),
            [25 * 2_000_000_000, 25 * 2_000_000_000],
        )
        self.assertEqual(truth["sane"][5:7].tolist(), [False, False])
        self.assertEqual(int(truth["phase_open_ts_ns"][7]), 5 * NS)
        self.assertEqual(int(truth["phase_sane_ceiling_units"][7]),
                         100 * 2_000_000_000)
        self.assertTrue(truth["sane"][7])

    def test_same_phase_candidates_get_exact_cached_ceiling_and_trust_planes(self):
        rows = _rows(8)
        rows[0]["flags"] = 40  # authenticated snapshot; next sane row is a seed
        rows[1:]["ask_px"] = 1_010_000_000  # $50 SI spread
        low_candidate, low_teacher = _maps(
            cid="low", decision=4 * NS, cutoff=4, exit_ts=7 * NS,
        )
        high_candidate, high_teacher = _maps(
            cid="high", decision=5 * NS, cutoff=5, exit_ts=7 * NS,
        )
        low_candidate["sane_ceiling_usd"] = "25"
        high_candidate["sane_ceiling_usd"] = "100"
        action = ActionDecision(False, True, ActionMaskReason.AVAILABLE_EXACT_TIME)
        low = CandidateTruthBinding.from_mappings(low_candidate, low_teacher, action)
        high = CandidateTruthBinding.from_mappings(high_candidate, high_teacher, action)
        truth = build_event_truth_columns(rows, "SI", (low, high))
        low_plane = truth.candidate_columns(low)
        high_plane = truth.candidate_columns(high)

        self.assertEqual(len(truth.quality_planes), 2)
        self.assertFalse(low_plane["sane"][2])
        self.assertTrue(high_plane["sane"][2])
        self.assertFalse(low_plane["trusted_message"][2])
        self.assertTrue(high_plane["trusted_message"][2])
        expected = native_book_quality(
            rows["ts_recv_ns"], rows["flags"], high_plane["sane"]
        )
        np.testing.assert_array_equal(high_plane["generation"],
                                      expected.generation)
        np.testing.assert_array_equal(high_plane["trusted_message"],
                                      expected.trusted_message)
        np.testing.assert_array_equal(high_plane["trusted_economic"],
                                      expected.trusted_economic)
        self.assertEqual(truth.quality_key(high), high.truth_quality_key)

    def test_equal_time_cutoff_complement_and_outcome_not_in_input(self):
        rows = _rows()
        rows[5]["ts_recv_ns"] = 5 * NS
        binding = _binding()
        session = DiagnosticSession.from_array(rows, asset="SI", open_ns=0,
                                               bindings=(binding,))
        self.assertEqual(session.input_continuous.shape[0], 5)
        self.assertEqual(session.receive_clock_ns[-1], 4 * NS)
        self.assertEqual(len(session.truth["ts_recv_ns"]), 10)
        self.assertFalse(hasattr(session, "outcome_rows"))

    def test_raw_routes_mutate_independently_and_prefix_suffix_invariant(self):
        rows = _rows()
        truth = build_event_truth_columns(rows, "SI", (_binding(),))
        builder = DerivedEventFieldBuilder()
        fields = builder.build(truth)
        self.assertEqual(len(fields.raw_routes), 18)
        for name in rows.dtype.names:
            if name not in fields.raw_routes:
                continue
            changed = rows.copy()
            if name in {"ts_recv_ns", "ts_event_ns"}:
                changed[name][3] += 1
            else:
                changed[name][3] += 1
            mutant = builder.build(build_event_truth_columns(changed, "SI", (_binding(),)))
            self.assertFalse(np.array_equal(fields.raw_routes[name],
                                            mutant.raw_routes[name]), name)
        suffix = rows.copy(); suffix[6:]["size"] += 1000
        suffix_fields = builder.build(build_event_truth_columns(suffix, "SI", (_binding(),)))
        self.assertTrue(np.array_equal(builder.prefix_summary(fields, 6),
                                       builder.prefix_summary(suffix_fields, 6)))
        self.assertEqual(len(fields.schema_sha256), 64)
        self.assertEqual(len(fields.equation_sha256), 64)

    def test_price_delta_refuses_undefined_endpoint_without_overflow(self):
        rows = _rows()
        rows[3]["price"] = UNDEF_PRICE
        truth = build_event_truth_columns(rows, "SI", (_binding(),))
        fields = DerivedEventFieldBuilder().build(truth)
        delta = fields.derived_routes["price_delta"]
        valid = fields.valid_masks["price_delta"]
        self.assertEqual((int(delta[3]), int(delta[4])), (0, 0))
        self.assertFalse(valid[3]); self.assertFalse(valid[4])
        self.assertTrue(np.all(np.abs(delta) < 2**53))

    def test_one_physical_open(self):
        rows = _rows()
        binding = _binding()
        class Header:
            asset = "SI"
            open_ns = 0
            close_ns = 20 * NS
        class Pack:
            header = Header()
            def __init__(self): self.rows = rows
            def model_arrays(self, stop): return DiagnosticSession.from_array(
                self.rows, asset="SI", open_ns=0,
                bindings=(binding,)).input_continuous, DiagnosticSession.from_array(
                    self.rows, asset="SI", open_ns=0,
                    bindings=(binding,)).input_categorical
            def cutoff(self, decision): return int(np.searchsorted(
                self.rows["ts_recv_ns"], np.uint64(decision), side="left"))
            def close(self): self.closed = True
        calls = []
        def opener(): calls.append(1); return Pack()
        one = OneLoadDiagnosticInput()
        one.open_once(opener, (binding,))
        self.assertEqual((len(calls), one.receipt.physical_open_count), (1, 1))
        with self.assertRaises(DiagnosticInputRefusal):
            one.open_once(opener, (binding,))
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
