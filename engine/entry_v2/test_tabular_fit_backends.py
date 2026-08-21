"""Per-head fit backend law (D-105) + DP-2 ARTIFACT_PIN receipt fields."""

from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

from .tabular_fit_backends import (
    ACTION_OBJECTIVE_LOSS_FUNCTIONS, CATBOOST_CPU, CATBOOST_GPU,
    COMPONENT_HEAD_LOSS_FUNCTIONS, DP2_CATBOOST_VERSION,
    DP2_DETERMINISM_RECEIPT, DP2_DRIVER_VERSION, DP2_MEASURED_LOSS_FUNCTIONS,
    FIT_BACKEND_BY_LOSS_FAMILY, FIT_RECEIPT_LAW_FIELDS,
    PRODUCTION_LOSS_FUNCTIONS, fit_backend_for_loss,
    fit_receipt_backend_fields, fit_receipt_environment_fields,
    fit_receipt_law_fields, gpu_fit_param_overlay, observed_catboost_version,
    observed_driver_version,
)
from .tabular_recovery_contracts import RecoveryConfig, RecoveryRefusal

CPU_LOSSES = ("MultiQuantile:alpha=0.2,0.5,0.8", "MultiQuantile:alpha=0.5,0.9",
              # Flipped 2026-08-21 by the big-fold probe: GPU_DEGENERATE on
              # both folds (gpu_quantile_bigfold_probe.json — tree-ratio
              # clause; even CPU early-stops at 1 tree on FROZEN_Q3_E8).
              "Quantile:alpha=0.9")
GPU_LOSSES = ("Logloss", "MultiRMSE", "MultiClass",
              "PairLogitPairwise")
RECEIPT_SECTIONS = frozenset({"loss_function", "law", "environment"})
LAW_FIELDS = frozenset({
    "fit_backend", "task_type", "devices", "boosting_type",
    "determinism_mode", "determinism_receipt"})
ENVIRONMENT_FIELDS = frozenset({
    "catboost_version", "driver_version", "dp2_reference_catboost",
    "dp2_reference_driver", "determinism_head_measured"})
MODELS_SOURCE = Path(__file__).resolve().parent / "tabular_models.py"
# The probe receipt that licenses Quantile:alpha=0.9 on the GPU (spec §F).
QUANTILE_PROBE_RECEIPT = Path(
    "/workspace/artifacts/entry_v2/tabular_recovery/diagnostics/"
    "gpu_quantile_bigfold_probe.json")


class FitBackendRoutingTest(unittest.TestCase):
    """D-105: MultiQuantile heads fit CPU, the five named losses fit GPU."""

    def test_multiquantile_heads_fit_cpu(self) -> None:
        for loss in CPU_LOSSES:
            with self.subTest(loss=loss):
                self.assertEqual(fit_backend_for_loss(loss), CATBOOST_CPU)

    def test_five_named_losses_fit_gpu(self) -> None:
        for loss in GPU_LOSSES:
            with self.subTest(loss=loss):
                self.assertEqual(fit_backend_for_loss(loss), CATBOOST_GPU)

    def test_unknown_loss_refuses_with_the_offending_value(self) -> None:
        for loss in ("RMSE", "MultiQuantil:alpha=0.5", "", "Quantile:"):
            with self.subTest(loss=loss):
                with self.assertRaises(RecoveryRefusal) as caught:
                    fit_backend_for_loss(loss)
                self.assertIn(repr(loss), str(caught.exception))
                self.assertIn("MultiQuantile", str(caught.exception))

    def test_every_production_loss_resolves(self) -> None:
        for loss in PRODUCTION_LOSS_FUNCTIONS:
            with self.subTest(loss=loss):
                self.assertIn(fit_backend_for_loss(loss),
                              {CATBOOST_CPU, CATBOOST_GPU})

    def test_production_roster_matches_the_fit_code(self) -> None:
        """A head added to tabular_models without a D-105 backend is a defect."""

        found = set(re.findall(r'loss_function="([^"]+)"',
                               MODELS_SOURCE.read_text()))
        self.assertEqual(found, set(PRODUCTION_LOSS_FUNCTIONS))

    def test_component_head_map_covers_the_published_head_set(self) -> None:
        from .tabular_models import COMPONENT_FILES

        self.assertEqual(set(COMPONENT_HEAD_LOSS_FUNCTIONS),
                         set(COMPONENT_FILES))

    def test_continuation_head_is_multiquantile_and_therefore_cpu(self) -> None:
        """D-105 names current/occupancy; continuation is MultiQuantile too."""

        self.assertEqual(COMPONENT_HEAD_LOSS_FUNCTIONS["continuation"],
                         "MultiQuantile:alpha=0.2,0.5,0.8")
        self.assertEqual(
            fit_backend_for_loss(COMPONENT_HEAD_LOSS_FUNCTIONS["continuation"]),
            CATBOOST_CPU)

    def test_action_objectives_are_the_roster_objectives(self) -> None:
        self.assertEqual(set(ACTION_OBJECTIVE_LOSS_FUNCTIONS),
                         {"MultiRMSE", "MultiClass", "PairLogitPairwise"})
        for objective in ACTION_OBJECTIVE_LOSS_FUNCTIONS:
            with self.subTest(objective=objective):
                self.assertEqual(fit_backend_for_loss(objective), CATBOOST_GPU)

    def test_production_roster_is_the_union_of_the_head_maps(self) -> None:
        self.assertEqual(
            set(PRODUCTION_LOSS_FUNCTIONS),
            set(COMPONENT_HEAD_LOSS_FUNCTIONS.values())
            | set(ACTION_OBJECTIVE_LOSS_FUNCTIONS))

    def test_backend_names_are_the_two_lawful_values(self) -> None:
        self.assertEqual(set(FIT_BACKEND_BY_LOSS_FAMILY.values()),
                         {CATBOOST_CPU, CATBOOST_GPU})


class GpuOverlayTest(unittest.TestCase):
    """The overlay carries exactly the pinned GPU additions and nothing else."""

    def test_cpu_heads_get_no_overlay(self) -> None:
        for loss in CPU_LOSSES:
            with self.subTest(loss=loss):
                self.assertEqual(gpu_fit_param_overlay(loss), {})

    def test_plain_boosting_is_pinned_only_for_multirmse(self) -> None:
        self.assertEqual(
            gpu_fit_param_overlay("MultiRMSE"),
            {"task_type": "GPU", "devices": "0", "boosting_type": "Plain"})
        for loss in ("Logloss", "MultiClass", "PairLogitPairwise"):
            with self.subTest(loss=loss):
                self.assertEqual(gpu_fit_param_overlay(loss),
                                 {"task_type": "GPU", "devices": "0"})

    def test_overlay_refuses_an_unknown_loss(self) -> None:
        with self.assertRaises(RecoveryRefusal):
            gpu_fit_param_overlay("Huber:delta=1")

    def test_overlay_result_is_an_independent_copy(self) -> None:
        first = gpu_fit_param_overlay("MultiRMSE")
        first["task_type"] = "CPU"
        self.assertEqual(gpu_fit_param_overlay("MultiRMSE")["task_type"], "GPU")

    def test_overlay_is_disjoint_from_the_frozen_common_parameters(self) -> None:
        """I4: the overlay may only ADD knobs, never restate a frozen HP.

        A key present in both would let the overlay silently override a frozen
        hyper-parameter at the `{**common, **overlay}` merge (spec §A0).
        """

        from .tabular_models import _common_parameters

        config = RecoveryConfig()
        frozen = set(_common_parameters(config, config.real_seeds[0]))
        for loss in PRODUCTION_LOSS_FUNCTIONS:
            with self.subTest(loss=loss):
                self.assertEqual(
                    set(gpu_fit_param_overlay(loss)) & frozen, set(),
                    f"overlay for {loss!r} restates a frozen hyper-parameter")


class FitReceiptLawFieldsTest(unittest.TestCase):
    """I4: the LAW half is the only thing the §B3 equality gate compares."""

    def test_law_fields_are_exactly_the_six_gate_fields(self) -> None:
        self.assertEqual(set(FIT_RECEIPT_LAW_FIELDS), LAW_FIELDS)
        for loss in PRODUCTION_LOSS_FUNCTIONS:
            with self.subTest(loss=loss):
                self.assertEqual(set(fit_receipt_law_fields(loss)), LAW_FIELDS)

    def test_gpu_head_law_values(self) -> None:
        law = fit_receipt_law_fields("Logloss")
        self.assertEqual(law["fit_backend"], CATBOOST_GPU)
        self.assertEqual(law["task_type"], "GPU")
        self.assertEqual(law["devices"], "0")
        self.assertIsNone(law["boosting_type"])
        self.assertEqual(law["determinism_mode"], "ARTIFACT_PIN")
        self.assertEqual(law["determinism_receipt"], DP2_DETERMINISM_RECEIPT)

    def test_multirmse_records_the_pinned_plain_boosting(self) -> None:
        self.assertEqual(
            fit_receipt_law_fields("MultiRMSE")["boosting_type"], "Plain")

    def test_cpu_head_law_values(self) -> None:
        law = fit_receipt_law_fields("MultiQuantile:alpha=0.5,0.9")
        self.assertEqual(law["fit_backend"], CATBOOST_CPU)
        self.assertEqual(law["task_type"], "CPU")
        self.assertIsNone(law["devices"])
        self.assertIsNone(law["boosting_type"])
        self.assertEqual(law["determinism_mode"], "ARTIFACT_PIN")

    def test_no_observed_environment_value_reaches_the_law_half(self) -> None:
        """The gate must not fail because a driver was upgraded mid-round."""

        self.assertEqual(LAW_FIELDS & ENVIRONMENT_FIELDS, set())
        for loss in PRODUCTION_LOSS_FUNCTIONS:
            with self.subTest(loss=loss):
                self.assertEqual(
                    set(fit_receipt_law_fields(loss))
                    & set(fit_receipt_environment_fields(loss)), set())

    def test_law_refuses_an_unknown_loss(self) -> None:
        with self.assertRaises(RecoveryRefusal):
            fit_receipt_law_fields("Poisson")


class FitReceiptEnvironmentFieldsTest(unittest.TestCase):
    """I4: environment is OBSERVED live; the DP-2 values stay named references."""

    def test_environment_fields_are_the_named_set(self) -> None:
        for loss in PRODUCTION_LOSS_FUNCTIONS:
            with self.subTest(loss=loss):
                self.assertEqual(set(fit_receipt_environment_fields(loss)),
                                 ENVIRONMENT_FIELDS)

    def test_catboost_version_is_the_live_import_not_the_constant(self) -> None:
        import catboost

        environment = fit_receipt_environment_fields("MultiRMSE")
        self.assertEqual(environment["catboost_version"], catboost.__version__)
        self.assertEqual(environment["catboost_version"],
                         observed_catboost_version())

    def test_dp2_constants_are_kept_as_named_references(self) -> None:
        environment = fit_receipt_environment_fields("MultiRMSE")
        self.assertEqual(environment["dp2_reference_catboost"],
                         DP2_CATBOOST_VERSION)
        self.assertEqual(environment["dp2_reference_driver"],
                         DP2_DRIVER_VERSION)

    def test_gpu_head_driver_is_observed_and_cpu_head_carries_none(self) -> None:
        self.assertEqual(
            fit_receipt_environment_fields("MultiRMSE")["driver_version"],
            observed_driver_version())
        self.assertIsNone(
            fit_receipt_environment_fields(
                "MultiQuantile:alpha=0.5,0.9")["driver_version"])

    @unittest.skipUnless(observed_driver_version() is not None,
                         "no nvidia-smi on this box")
    def test_observed_driver_is_a_version_string_on_a_gpu_box(self) -> None:
        driver = observed_driver_version()
        self.assertRegex(driver, r"^\d+(\.\d+)+$")

    def test_determinism_head_measured_only_for_the_two_dp2_heads(self) -> None:
        self.assertEqual(set(DP2_MEASURED_LOSS_FUNCTIONS),
                         {"Quantile:alpha=0.9", "MultiRMSE"})
        for loss in PRODUCTION_LOSS_FUNCTIONS:
            with self.subTest(loss=loss):
                self.assertEqual(
                    fit_receipt_environment_fields(
                        loss)["determinism_head_measured"],
                    loss in {"Quantile:alpha=0.9", "MultiRMSE"})


class FitReceiptBackendFieldsTest(unittest.TestCase):
    """Every fit receipt states its backend law and the environment it ran in."""

    def test_receipt_is_the_law_environment_split(self) -> None:
        for loss in PRODUCTION_LOSS_FUNCTIONS:
            with self.subTest(loss=loss):
                fields = fit_receipt_backend_fields(loss)
                self.assertEqual(set(fields), RECEIPT_SECTIONS)
                self.assertEqual(fields["loss_function"], loss)
                self.assertEqual(fields["law"], fit_receipt_law_fields(loss))
                self.assertEqual(fields["environment"],
                                 fit_receipt_environment_fields(loss))

    def test_receipt_refuses_an_unknown_loss(self) -> None:
        with self.assertRaises(RecoveryRefusal):
            fit_receipt_backend_fields("Poisson")

    def test_determinism_receipt_file_exists(self) -> None:
        receipt = (Path("/workspace/artifacts/entry_v2/tabular_recovery/"
                        "diagnostics") / DP2_DETERMINISM_RECEIPT)
        self.assertTrue(receipt.is_file(), f"missing DP-2 receipt: {receipt}")


class QuantileGpuLicenceTest(unittest.TestCase):
    """I7: Quantile may route to the GPU only with a GPU_OK probe receipt."""

    @unittest.skipUnless(
        QUANTILE_PROBE_RECEIPT.is_file(),
        f"F13: the freeze-window probe has not run yet, so there is no "
        f"receipt to read at {QUANTILE_PROBE_RECEIPT}")
    def test_quantile_gpu_requires_a_gpu_ok_bigfold_receipt(self) -> None:
        if fit_backend_for_loss("Quantile:alpha=0.9") != CATBOOST_GPU:
            self.skipTest("Quantile is routed to CPU; no probe receipt needed")
        receipt = json.loads(QUANTILE_PROBE_RECEIPT.read_text())
        self.assertEqual(receipt.get("verdict"), "GPU_OK",
                         f"probe verdict is not GPU_OK: {receipt.get('verdict')!r}")


if __name__ == "__main__":
    unittest.main()
