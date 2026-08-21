"""I5: every arm of a head carries the SAME D-105 backend map, or none does."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from .tabular_fit_backends import (
    COMPONENT_HEAD_LOSS_FUNCTIONS, fit_receipt_backend_fields,
)
from .tabular_fit_roster_homogeneity import (
    assert_head_homogeneous_fit_backends, fit_backend_fields_by_head,
    load_bundle_fit_backend_fields,
)
from .tabular_recovery_contracts import RecoveryRefusal


def _component_fields() -> dict[str, dict]:
    return {head: fit_receipt_backend_fields(loss)
            for head, loss in COMPONENT_HEAD_LOSS_FUNCTIONS.items()}


def _action_fields() -> dict:
    return fit_receipt_backend_fields("MultiRMSE")


class FitBackendFieldsByHeadTest(unittest.TestCase):
    """Both published manifest shapes normalise to one head -> fields map."""

    def test_component_manifest_is_already_a_head_map(self) -> None:
        fields = _component_fields()
        self.assertEqual(
            fit_backend_fields_by_head({"fit_backend_fields": fields}), fields)

    def test_action_manifest_is_keyed_by_its_objective_loss(self) -> None:
        fields = _action_fields()
        self.assertEqual(
            fit_backend_fields_by_head({"fit_backend_fields": fields}),
            {"MultiRMSE": fields})

    def test_a_manifest_without_the_key_carries_nothing(self) -> None:
        self.assertIsNone(fit_backend_fields_by_head({"schema": "whatever"}))

    def test_a_malformed_carried_value_refuses(self) -> None:
        with self.assertRaises(RecoveryRefusal) as caught:
            fit_backend_fields_by_head({"fit_backend_fields": ["not", "a map"]})
        self.assertIn("['not', 'a map']", str(caught.exception))

    def test_a_flat_value_without_a_loss_function_refuses(self) -> None:
        with self.assertRaises(RecoveryRefusal):
            fit_backend_fields_by_head(
                {"fit_backend_fields": {"law": {}, "environment": {}}})


class LoadBundleFitBackendFieldsTest(unittest.TestCase):
    """The call-site helper reads exactly one manifest.json."""

    def test_reads_a_published_manifest(self) -> None:
        fields = _component_fields()
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            (bundle / "manifest.json").write_text(json.dumps(
                {"schema": "QRE2TABCOMPONENTCB3", "fit_backend_fields": fields}))
            self.assertEqual(load_bundle_fit_backend_fields(bundle), fields)

    def test_a_pre_swap_bundle_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            (bundle / "manifest.json").write_text(
                json.dumps({"schema": "QRE2TABCOMPONENTCB3"}))
            self.assertIsNone(load_bundle_fit_backend_fields(bundle))

    def test_an_unreadable_manifest_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RecoveryRefusal) as caught:
                load_bundle_fit_backend_fields(Path(directory))
            self.assertIn(directory, str(caught.exception))


class HeadHomogeneityTest(unittest.TestCase):
    """Fixture pair: the drift it must catch, the shapes it must accept."""

    def test_every_arm_lacking_the_key_is_accepted(self) -> None:
        """Round-0 published bundles all predate the swap; they must load."""

        assert_head_homogeneous_fit_backends(
            {"seed_20260820/E3": None, "seed_20260821/E3": None})

    def test_every_arm_carrying_identical_values_is_accepted(self) -> None:
        arms = {f"seed_2026082{index}/E3": _component_fields()
                for index in range(5)}
        assert_head_homogeneous_fit_backends(arms)

    def test_an_empty_arm_set_is_accepted(self) -> None:
        assert_head_homogeneous_fit_backends({})

    def test_partial_carry_refuses_and_names_the_arms(self) -> None:
        arms = {"seed_20260820/E3": _component_fields(),
                "seed_20260821/E3": None}
        with self.assertRaises(RecoveryRefusal) as caught:
            assert_head_homogeneous_fit_backends(arms)
        message = str(caught.exception)
        self.assertIn("seed_20260821/E3", message)
        self.assertIn("all-carry or all-lack", message)

    def test_a_law_difference_between_arms_refuses(self) -> None:
        good = _component_fields()
        drifted = _component_fields()
        # Flip whatever the live law says, so a D-105 backend re-pin can never
        # turn this mutant into a no-op (it did once, at the Quantile CPU flip).
        drifted["adverse"]["law"]["fit_backend"] = (
            "CATBOOST_GPU"
            if good["adverse"]["law"]["fit_backend"] == "CATBOOST_CPU"
            else "CATBOOST_CPU")
        with self.assertRaises(RecoveryRefusal) as caught:
            assert_head_homogeneous_fit_backends(
                {"seed_20260820/E3": good, "seed_20260821/E3": drifted})
        message = str(caught.exception)
        self.assertIn("adverse", message)
        self.assertIn("CATBOOST_CPU", message)
        self.assertNotIn("environment only", message)

    def test_an_environment_only_difference_refuses_and_says_so(self) -> None:
        """Driver drift is still a refusal, but the reader must not misread it."""

        good = _component_fields()
        drifted = _component_fields()
        drifted["wall"]["environment"]["driver_version"] = "999.99.99"
        with self.assertRaises(RecoveryRefusal) as caught:
            assert_head_homogeneous_fit_backends(
                {"seed_20260820/E3": good, "seed_20260821/E3": drifted})
        message = str(caught.exception)
        self.assertIn("wall", message)
        self.assertIn("environment only", message)

    def test_a_head_missing_from_one_carrying_arm_refuses(self) -> None:
        good = _component_fields()
        short = _component_fields()
        del short["occupancy"]
        with self.assertRaises(RecoveryRefusal) as caught:
            assert_head_homogeneous_fit_backends(
                {"seed_20260820/E3": good, "seed_20260821/E3": short})
        self.assertIn("occupancy", str(caught.exception))

    def test_action_arms_of_one_objective_are_homogeneous(self) -> None:
        arms = {f"seed_2026082{index}/E4": {"MultiRMSE": _action_fields()}
                for index in range(5)}
        assert_head_homogeneous_fit_backends(arms)


if __name__ == "__main__":
    unittest.main()
