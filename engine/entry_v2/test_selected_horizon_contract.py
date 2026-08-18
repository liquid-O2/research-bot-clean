from __future__ import annotations

import unittest

from .selected_horizon_contract import (
    COORDINATES, COVERAGE_LAW_SHA256, MODEL_COORDINATES, SCHEMA_SHA256, WIDTH,
    SelectedHorizonContractRefusal, selected_horizon_contract,
    selected_horizon_coverage_receipt, validate_selected_horizon_coverage,
    validate_selected_horizon_identity,
)


class SelectedHorizonContractTest(unittest.TestCase):
    def test_exact_six_coordinate_identity_round_trips(self) -> None:
        receipt = selected_horizon_contract()
        self.assertEqual(tuple(receipt["coordinates"]), COORDINATES)
        self.assertEqual(MODEL_COORDINATES, (300, 600, 900, 1200, 1800, -1))
        self.assertEqual(receipt["width"], WIDTH)
        validate_selected_horizon_identity(COORDINATES, SCHEMA_SHA256)

    def test_each_coordinate_and_schema_mutation_refuses(self) -> None:
        for index in range(WIDTH):
            changed = list(COORDINATES)
            changed[index] = "FINAL" if index != WIDTH - 1 else 1801
            with self.assertRaises(SelectedHorizonContractRefusal):
                validate_selected_horizon_identity(changed, SCHEMA_SHA256)
        with self.assertRaises(SelectedHorizonContractRefusal):
            validate_selected_horizon_identity(COORDINATES, "0" * 64)

    def test_coverage_is_optional_prefix_then_complete_suffix(self) -> None:
        corpus = [{
            "asset": "HG", "trading_day": 20210528, "session_id": "early",
            "candidate_count": 2, "candidate_ids_sha256": "a" * 64,
            "selected_attached": False,
        }, {
            "asset": "HG", "trading_day": 20210531, "session_id": "fit",
            "candidate_count": 3, "candidate_ids_sha256": "b" * 64,
            "selected_attached": True,
        }]
        diagnostic = [{
            "asset": "HG", "trading_day": 20210531,
            "source_receipt_sha256": "c" * 64,
            "candidate_count": 4, "candidate_ids_sha256": "d" * 64,
            "eligible_ready_count": 3,
            "eligible_ready_ids_sha256": "b" * 64,
        }, {
            "asset": "SI", "trading_day": 20210601,
            "source_receipt_sha256": "e" * 64,
            "candidate_count": 1, "candidate_ids_sha256": "f" * 64,
            "eligible_ready_count": 0,
            "eligible_ready_ids_sha256": "0" * 64,
        }]
        receipt = selected_horizon_coverage_receipt(
            start_d8=20210531, corpus_sessions=corpus,
            diagnostic_sessions=diagnostic,
        )
        validate_selected_horizon_coverage(receipt)
        self.assertEqual(receipt["law_sha256"], COVERAGE_LAW_SHA256)
        self.assertEqual(receipt["prefix_unattached_session_count"], 1)
        self.assertEqual(receipt["suffix_attached_session_count"], 1)
        self.assertEqual(receipt["diagnostic_only_session_count"], 1)

        missing = diagnostic[1:]
        with self.assertRaisesRegex(
                SelectedHorizonContractRefusal, "suffix lacks"):
            selected_horizon_coverage_receipt(
                start_d8=20210531, corpus_sessions=corpus,
                diagnostic_sessions=missing,
            )
        interior_gap = [dict(row) for row in corpus]
        interior_gap[1]["selected_attached"] = False
        with self.assertRaisesRegex(
                SelectedHorizonContractRefusal, "prefix/suffix"):
            selected_horizon_coverage_receipt(
                start_d8=20210531, corpus_sessions=interior_gap,
                diagnostic_sessions=diagnostic,
            )
        omitted_learner = [dict(row) for row in diagnostic]
        omitted_learner[1]["eligible_ready_count"] = 1
        with self.assertRaisesRegex(
                SelectedHorizonContractRefusal, "omitted learner"):
            selected_horizon_coverage_receipt(
                start_d8=20210531, corpus_sessions=corpus,
                diagnostic_sessions=omitted_learner,
            )


class SelectedHorizonAtlasAxesTest(unittest.TestCase):
    """B-21: the six-horizon atlas axes are derived, never a magic literal."""

    def test_axes_are_derived_from_the_atlas_endpoint_roster(self) -> None:
        from engine.entry_v2.causal_label_atlas import HORIZON_SECONDS
        from engine.entry_v2.selected_horizon_contract import (
            ATLAS_AXIS_COUNT, ATLAS_ENDPOINT_AXES, COORDINATES,
            SELECTED_HORIZON_ATLAS_AXES, WIDTH,
        )
        self.assertEqual(ATLAS_AXIS_COUNT, len(HORIZON_SECONDS) + 2)
        self.assertEqual(ATLAS_ENDPOINT_AXES[-2:], ("PHASE", "FINAL"))
        self.assertEqual(len(SELECTED_HORIZON_ATLAS_AXES), WIDTH)
        self.assertEqual(SELECTED_HORIZON_ATLAS_AXES, (3, 4, 5, 6, 7, 11))
        for axis, coordinate in zip(SELECTED_HORIZON_ATLAS_AXES, COORDINATES):
            expected = ("FINAL" if coordinate == "FINAL"
                        else f"{int(coordinate)}s")
            self.assertEqual(ATLAS_ENDPOINT_AXES[axis], expected)

    def test_an_unresolvable_coordinate_refuses_at_derivation(self) -> None:
        from unittest import mock
        from engine.entry_v2 import selected_horizon_contract as contract
        with mock.patch.object(contract, "COORDINATES", (300, 42, "FINAL")):
            with self.assertRaises(contract.SelectedHorizonContractRefusal):
                contract._derive_selected_atlas_axes()


if __name__ == "__main__":
    unittest.main()
