"""Pre-flight: is the Quantile:alpha=0.9 head sane on GPU at real fold size?

DP-2 (artifacts/entry_v2/tabular_recovery/diagnostics/
gpu_fit_determinism_20260821.json) fitted the component adverse head
(Quantile:alpha=0.9) on the GPU on the SMALLEST published component fold
(BURN_E2_STACK, 62,636 train rows) and the fit collapsed to ONE tree
(tree_count [1,1,1], best_iteration [0,0,0]) where the published CPU artifact
carries 5 trees. That is a QUALITY flag, not a determinism flag, and D-105
sends this head to the GPU. So before E2R commits any arm of the head to the
GPU, this probe re-runs the same question ONCE on the LARGEST published
round-0 component fold.

PRE-REGISTERED RULE (fixed before the fit; also written into the receipt):
  per fold, GPU_OK <=> |gpu_metric - cpu_published_metric| /
              cpu_published_metric <= 0.05  AND  gpu_trees >= 2
              AND  gpu_trees >= 0.5 * cpu_published_trees
  and the RUN is GPU_OK only if BOTH the largest and the smallest published
  round-0 component fold are GPU_OK; otherwise GPU_DEGENERATE (exit 1), and
  the adverse head's backend flips to CATBOOST_CPU for every one of its E2R
  arms (head-consistency, D-105).
The metric is the head's own Quantile:alpha=0.9 loss on the published
validation fold, weighted exactly as the fit weights it; lower is better, so
the two-sided 5% band also fails a GPU fit that looks implausibly good. The
tree-ratio clause is there because the >=2 floor alone accepts a fit that
collapsed from hundreds of trees to three.

This is DOCUMENTED CONTEXT for a backend decision. It is never mixed into
rehearsal results: it fits nothing that is published, and it writes only its
own diagnostics receipt.

The CPU side is READ, never refitted: the published artifact is scored through
the SAME _gate_metric path the GPU model is scored through, so the two sides
of the band are the same quantity. The number the artifact stored inside
itself at its best iteration is recorded as context, and a disagreement
between the two beyond float noise refuses the run.

Run (orchestrator, at the freeze window, before the first E2R component fit):
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 nice -n 19 \
      python3 tools/probe_gpu_quantile_bigfold.py
Dry run (validates artifact loading, fits nothing, writes no receipt):
  ... python3 tools/probe_gpu_quantile_bigfold.py --dry-run
Re-audit after a GPU_DEGENERATE flip sent the head to CPU (M4):
  ... python3 tools/probe_gpu_quantile_bigfold.py --force-gpu
Self-test (no artifacts, no GPU):
  ... python3 tools/probe_gpu_quantile_bigfold.py --selftest
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time
from typing import Final, Sequence
import unittest
import unittest.mock

sys.path.insert(0, "/workspace")

import catboost
from catboost import CatBoostRegressor
from catboost.utils import eval_metric
import numpy as np

from engine.entry_v2.tabular_experiment import _range_mask
from engine.entry_v2.tabular_fit_backends import (
    CATBOOST_GPU, GPU_DEVICE_PARAMETERS, fit_backend_for_loss,
    fit_receipt_backend_fields, gpu_fit_param_overlay,
)
from engine.entry_v2.tabular_matrix_store import load_component_matrix
from engine.entry_v2.tabular_models import (
    _common_parameters, _config_from_json, _fit_with_early_stop,
)

BIGFOLD_SCHEMA: Final = "QRE2GPUQUANTILEBIGFOLD1"
BIGFOLD_ROUND: Final = Path(
    "/workspace/artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/"
    "curriculum/fits/round_0")
BIGFOLD_RECEIPT_PATH: Final = Path(
    "/workspace/artifacts/entry_v2/tabular_recovery/diagnostics/"
    "gpu_quantile_bigfold_probe.json")
BIGFOLD_SEED: Final = 20260820          # first frozen real seed, as in DP-2
BIGFOLD_LOSS: Final = "Quantile:alpha=0.9"
BIGFOLD_HEAD_FILE: Final = "adverse_q90.cbm"
BIGFOLD_TARGET_FIELD: Final = "adverse_usd"
BIGFOLD_METRIC_TOLERANCE: Final = 0.05
BIGFOLD_MIN_TREES: Final = 2            # "trees > 1" from the rule above
BIGFOLD_MIN_TREE_RATIO: Final = 0.5     # I7: half the published tree count
# I7: the two CPU paths (the number the artifact stored at its best iteration
# vs the same metric recomputed through _gate_metric) are the SAME quantity.
# DP-2 measured them agreeing to ~4e-16 relative on both heads
# (gpu_fit_determinism_20260821.json: metric_from_artifact vs
# metric_recomputed_on_validation), so anything above float noise means the
# probe is not comparing the GPU fit against the published fit at all.
BIGFOLD_CPU_PATH_EPSILON: Final = 1e-9
BIGFOLD_RULE: Final = (
    "Per fold, GPU_OK iff |gpu_metric - cpu_published_metric| / "
    f"cpu_published_metric <= {BIGFOLD_METRIC_TOLERANCE} AND gpu_trees >= "
    f"{BIGFOLD_MIN_TREES} AND gpu_trees >= {BIGFOLD_MIN_TREE_RATIO} * "
    "cpu_published_trees. The run is GPU_OK only if BOTH the largest and the "
    "smallest published round-0 component fold are GPU_OK; otherwise "
    "GPU_DEGENERATE and the Quantile:alpha=0.9 head fits CATBOOST_CPU for "
    "every E2R arm. Pre-registered before the fit; the metric is the head's "
    "own weighted Quantile:alpha=0.9 loss on the published validation fold, "
    "recomputed through the SAME gate path for the CPU and the GPU model.")


def bigfold_verdict(
    cpu_published_metric: float, gpu_metric: float, gpu_trees: int,
    cpu_published_trees: int,
) -> str:
    """The pre-registered rule, in one place, testable without a GPU."""

    reference = float(cpu_published_metric)
    if not np.isfinite(reference) or reference <= 0.0:
        raise ValueError(
            f"cpu_published_metric must be finite and positive for a relative "
            f"band, got {cpu_published_metric!r}")
    published_trees = int(cpu_published_trees)
    if published_trees < 1:
        raise ValueError(
            f"cpu_published_trees must be at least 1 to scale the tree floor, "
            f"got {cpu_published_trees!r}")
    if not np.isfinite(float(gpu_metric)):
        return "GPU_DEGENERATE"
    relative = abs(float(gpu_metric) - reference) / reference
    trees = int(gpu_trees)
    return ("GPU_OK"
            if relative <= BIGFOLD_METRIC_TOLERANCE
            and trees >= BIGFOLD_MIN_TREES
            and trees >= BIGFOLD_MIN_TREE_RATIO * published_trees
            else "GPU_DEGENERATE")


def bigfold_overall_verdict(verdict_by_fold: dict[str, str]) -> str:
    """One verdict for the run: both probed folds must be GPU_OK."""

    if len(verdict_by_fold) < 2:
        raise ValueError(
            f"the run verdict needs the largest AND the smallest published "
            f"fold, got {sorted(verdict_by_fold)}")
    return ("GPU_OK" if all(value == "GPU_OK"
                            for value in verdict_by_fold.values())
            else "GPU_DEGENERATE")


def assert_cpu_paths_agree(
    fold: str, metric_from_artifact: float, metric_recomputed: float,
) -> None:
    """The gate path and the artifact's own history must be the same number.

    The gate compares the GPU model through _gate_metric, so the CPU side must
    come through _gate_metric too; the artifact number is recorded as context.
    A disagreement means the reconstructed validation fold is not the one the
    published artifact was evaluated on, and no verdict is admissible.
    """

    artifact = float(metric_from_artifact)
    recomputed = float(metric_recomputed)
    if not np.isfinite(artifact) or artifact <= 0.0:
        raise RuntimeError(
            f"{fold}: the published artifact's stored metric is unusable as a "
            f"reference: {metric_from_artifact!r}")
    relative = abs(recomputed - artifact) / artifact
    if not np.isfinite(recomputed) or relative > BIGFOLD_CPU_PATH_EPSILON:
        raise RuntimeError(
            f"{fold}: the two CPU metric paths disagree by {relative!r} "
            f"(> {BIGFOLD_CPU_PATH_EPSILON}): artifact history says "
            f"{artifact!r}, the gate path recomputes {recomputed!r}; the "
            f"reconstructed validation fold is not the published one")


def _strict_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text())
    if manifest.get("schema") != "QRE2TABCOMPONENTCB3":
        raise RuntimeError(
            f"published component manifest schema differs at {path}: "
            f"{manifest.get('schema')!r} != 'QRE2TABCOMPONENTCB3'")
    return manifest


def _training_metrics(model: object) -> dict:
    raw = dict(model.get_metadata()).get("training")
    if raw is None:
        raise RuntimeError("published model carries no training metadata")
    return json.loads(raw)["metrics"]


def _published_metric(model: object) -> float:
    """The eval-set loss the published CPU fit stored inside its artifact."""

    metrics = _training_metrics(model)
    entry = metrics["test_metrics_history"][int(metrics["best_iteration"])]
    return float(next(iter(entry[0].values())))


def _published_bundles() -> dict[str, Path]:
    root = BIGFOLD_ROUND / "component_models/catboost/real" / f"seed_{BIGFOLD_SEED}"
    bundles = {path.parent.name: path
               for path in sorted(root.glob("*/component_bundle"))}
    if not bundles:
        raise RuntimeError(f"no published component bundles under {root}")
    return bundles


def _select_probe_folds(rows_by_fold: dict[str, int]) -> tuple[str, str]:
    """The two folds the rule asks about: most TRAIN rows, then fewest.

    Ties break on fold name so the selection is reproducible.
    """

    if len(rows_by_fold) < 2:
        raise RuntimeError(
            f"the probe needs at least two published folds to ask both ends "
            f"of the size range, got {sorted(rows_by_fold)}")
    names = sorted(rows_by_fold)
    largest = max(names, key=lambda name: rows_by_fold[name])
    smallest = min(names, key=lambda name: rows_by_fold[name])
    if largest == smallest:
        raise RuntimeError(
            f"largest and smallest published fold are the same fold "
            f"({largest!r}); train rows: {rows_by_fold}")
    return largest, smallest


def _fold_train_rows(
    day: np.ndarray, bundles: dict[str, Path],
) -> tuple[dict[str, int], dict[str, dict]]:
    """Train-row count and strict manifest for every published fold."""

    rows: dict[str, int] = {}
    manifests: dict[str, dict] = {}
    for fold, bundle in bundles.items():
        manifest = _strict_manifest(bundle / "manifest.json")
        manifests[fold] = manifest
        rows[fold] = int(_range_mask(
            day, tuple(manifest["train_day_range"])).sum())
    return rows, manifests


def _gate_metric(model: object, vx: np.ndarray, validation: object) -> float:
    approx = np.asarray(model.predict(vx), np.float64)
    label = np.asarray(getattr(validation, BIGFOLD_TARGET_FIELD), np.float64)
    weight = np.asarray(validation.sample_weight, np.float64)
    return float(eval_metric(label, approx, BIGFOLD_LOSS, weight=weight)[0])


def _probe_overlay(*, force_gpu: bool) -> dict[str, object]:
    """The GPU parameters this probe applies, post-flip re-audit included."""

    if fit_backend_for_loss(BIGFOLD_LOSS) == CATBOOST_GPU:
        return gpu_fit_param_overlay(BIGFOLD_LOSS)
    if not force_gpu:
        raise RuntimeError(
            f"D-105 no longer sends {BIGFOLD_LOSS} to the GPU; this probe has "
            "nothing to decide. Re-audit the flip with --force-gpu.")
    return dict(GPU_DEVICE_PARAMETERS)


def _probe_one_fold(
    *, matrix: object, day: np.ndarray, fold: str, manifest: dict, bundle: Path,
    train_rows: int, overlay: dict[str, object], dry_run: bool,
    started: float,
) -> dict:
    """One published fold: reconstruct, read the CPU side, fit GPU, verdict."""

    config = _config_from_json(manifest["config"])
    if config.receipt_sha256 != manifest["config_sha256"]:
        raise RuntimeError(f"{fold}: frozen config receipt differs")
    train = matrix.mask(_range_mask(day, tuple(manifest["train_day_range"])))
    validation = matrix.mask(
        _range_mask(day, tuple(manifest["validation_day_range"])))
    if (train.receipt_sha256 != manifest["train_receipt_sha256"]
            or validation.receipt_sha256
            != manifest["validation_receipt_sha256"]):
        raise RuntimeError(
            f"{fold}: reconstructed fit inputs are not the published ones")
    vx = np.asarray(validation.x, np.float32)
    published_model = CatBoostRegressor()
    published_model.load_model(str(bundle / BIGFOLD_HEAD_FILE), format="cbm")
    cpu_metric_from_artifact = _published_metric(published_model)
    cpu_published_metric = _gate_metric(published_model, vx, validation)
    assert_cpu_paths_agree(fold, cpu_metric_from_artifact, cpu_published_metric)
    cpu_trees = int(published_model.tree_count_)
    print(f"  [{fold}] published CPU artifact: trees={cpu_trees} "
          f"gate_metric={cpu_published_metric!r} "
          f"artifact_metric={cpu_metric_from_artifact!r} "
          f"[{time.perf_counter()-started:.1f}s]", flush=True)

    common = dict(_common_parameters(config, BIGFOLD_SEED))
    result = {
        "fold": fold,
        "train_rows": int(train_rows),
        "validation_rows": int(len(validation.day)),
        "train_day_range": manifest["train_day_range"],
        "validation_day_range": manifest["validation_day_range"],
        "published_bundle_receipt_sha256": manifest["receipt_sha256"],
        "frozen_config_sha256": manifest["config_sha256"],
        "train_receipt_sha256": train.receipt_sha256,
        "validation_receipt_sha256": validation.receipt_sha256,
        "cpu_published_metric": cpu_published_metric,
        "cpu_metric_from_artifact": cpu_metric_from_artifact,
        "cpu_metric_path_relative_difference":
            abs(cpu_published_metric - cpu_metric_from_artifact)
            / cpu_metric_from_artifact,
        "cpu_published_trees": cpu_trees,
    }
    if dry_run:
        result["frozen_fit_parameters"] = common
        return result

    x = np.asarray(train.x, np.float32)
    model = CatBoostRegressor(loss_function=BIGFOLD_LOSS, **{**common, **overlay})
    fit_started = time.perf_counter()
    _fit_with_early_stop(
        model, x, getattr(train, BIGFOLD_TARGET_FIELD), train.sample_weight,
        vx, getattr(validation, BIGFOLD_TARGET_FIELD),
        validation.sample_weight, patience=config.early_stopping_rounds)
    fit_wall = time.perf_counter() - fit_started
    gpu_metric = _gate_metric(model, vx, validation)
    gpu_trees = int(model.tree_count_)
    # F15: the verdict is computed FIRST, so an unusable reference raises the
    # named ValueError instead of a bare ZeroDivisionError from the ratio below.
    verdict = bigfold_verdict(cpu_published_metric, gpu_metric, gpu_trees,
                              cpu_trees)
    result.update({
        "gpu_metric": gpu_metric,
        "gpu_trees": gpu_trees,
        "gpu_best_iteration": int(_training_metrics(model)["best_iteration"]),
        "gpu_fit_wall_s": round(fit_wall, 3),
        "relative_metric_difference":
            abs(gpu_metric - cpu_published_metric) / cpu_published_metric,
        "gpu_to_cpu_tree_ratio": gpu_trees / cpu_trees,
        "verdict": verdict,
    })
    print(f"  [{fold}] GPU: trees={gpu_trees} metric={gpu_metric!r} "
          f"verdict={verdict} [{time.perf_counter()-started:.1f}s]", flush=True)
    return result


def run_probe(*, dry_run: bool, force_gpu: bool = False) -> dict:
    overlay = _probe_overlay(force_gpu=force_gpu)
    started = time.perf_counter()
    print(f"loading component matrix {BIGFOLD_ROUND/'component_matrix'} ...",
          flush=True)
    matrix = load_component_matrix(BIGFOLD_ROUND / "component_matrix")
    day = np.asarray(matrix.day, np.int64)
    bundles = _published_bundles()
    rows_by_fold, manifests = _fold_train_rows(day, bundles)
    largest, smallest = _select_probe_folds(rows_by_fold)
    print(f"  train rows by published fold: {rows_by_fold}", flush=True)
    print(f"  largest={largest} ({rows_by_fold[largest]} rows) "
          f"smallest={smallest} ({rows_by_fold[smallest]} rows) "
          f"[{time.perf_counter()-started:.1f}s]", flush=True)

    receipt = {
        "schema": BIGFOLD_SCHEMA,
        "pre_registered_rule": BIGFOLD_RULE,
        "determinism_receipt": "gpu_fit_determinism_20260821.json",
        "purpose": (
            "documented context for the D-105 backend of the "
            "Quantile:alpha=0.9 head; never mixed into rehearsal results"),
        "source_round": str(BIGFOLD_ROUND),
        "seed": BIGFOLD_SEED,
        "loss_function": BIGFOLD_LOSS,
        "largest_fold": largest,
        "smallest_fold": smallest,
        "train_rows_by_published_fold": rows_by_fold,
        "features": int(np.asarray(matrix.x).shape[1]),
        "gpu_fit_parameters_beyond_frozen_config": dict(overlay),
        "forced_gpu": bool(force_gpu),
        "fit_receipt_backend_fields": fit_receipt_backend_fields(BIGFOLD_LOSS),
        "catboost_version": catboost.__version__,
        "numpy_version": np.__version__,
        "dry_run": bool(dry_run),
    }
    folds = {fold: _probe_one_fold(
        matrix=matrix, day=day, fold=fold, manifest=manifests[fold],
        bundle=bundles[fold], train_rows=rows_by_fold[fold], overlay=overlay,
        dry_run=dry_run, started=started) for fold in (largest, smallest)}
    receipt["folds"] = folds
    if not dry_run:
        receipt["verdict"] = bigfold_overall_verdict(
            {fold: result["verdict"] for fold, result in folds.items()})
    receipt["wall_s"] = round(time.perf_counter() - started, 3)
    return receipt


class BigfoldVerdictTest(unittest.TestCase):
    """Fixture pair per clause of the pre-registered rule."""

    def test_matching_metric_and_many_trees_pass(self) -> None:
        self.assertEqual(bigfold_verdict(51.0, 51.5, 120, 100), "GPU_OK")

    def test_the_dp2_collapse_fails_on_trees(self) -> None:
        """The observed BURN_E2_STACK shape: metric close, ONE tree."""

        self.assertEqual(bigfold_verdict(51.02, 51.24, 1, 5), "GPU_DEGENERATE")

    def test_metric_drift_beyond_the_band_fails(self) -> None:
        self.assertEqual(bigfold_verdict(51.0, 54.0, 120, 100), "GPU_DEGENERATE")

    def test_implausibly_good_metric_also_fails(self) -> None:
        self.assertEqual(bigfold_verdict(51.0, 40.0, 120, 100), "GPU_DEGENERATE")

    def test_band_edges(self) -> None:
        self.assertEqual(bigfold_verdict(100.0, 105.0, 2, 4), "GPU_OK")
        self.assertEqual(bigfold_verdict(100.0, 105.01, 2, 4), "GPU_DEGENERATE")

    def test_non_finite_gpu_metric_fails(self) -> None:
        self.assertEqual(
            bigfold_verdict(51.0, float("nan"), 120, 100), "GPU_DEGENERATE")

    def test_unusable_reference_refuses(self) -> None:
        with self.assertRaises(ValueError):
            bigfold_verdict(0.0, 1.0, 120, 100)

    def test_tree_ratio_clause_catches_a_thin_but_plausible_gpu_fit(self) -> None:
        """I7: half the published trees is the floor, above the >=2 floor."""

        self.assertEqual(bigfold_verdict(51.0, 51.5, 49, 100), "GPU_DEGENERATE")
        self.assertEqual(bigfold_verdict(51.0, 51.5, 50, 100), "GPU_OK")

    def test_absolute_tree_floor_still_binds_on_a_tiny_published_fit(self) -> None:
        """cpu_published_trees=2 would let the ratio pass a ONE-tree GPU fit."""

        self.assertEqual(bigfold_verdict(51.0, 51.5, 1, 2), "GPU_DEGENERATE")
        self.assertEqual(bigfold_verdict(51.0, 51.5, 2, 2), "GPU_OK")

    def test_an_unusable_published_tree_count_refuses(self) -> None:
        with self.assertRaises(ValueError):
            bigfold_verdict(51.0, 51.5, 120, 0)

    def test_a_zero_reference_metric_refuses_before_any_division(self) -> None:
        """F15: the ValueError must beat the ZeroDivisionError."""

        with self.assertRaises(ValueError):
            bigfold_verdict(0.0, 0.0, 120, 100)


class BigfoldCpuPathTest(unittest.TestCase):
    """I7: the artifact number is context; the gate path must agree with it."""

    def test_the_two_cpu_paths_agreeing_is_accepted(self) -> None:
        assert_cpu_paths_agree("FROZEN_Q3_E8", 51.02117468258123,
                               51.02117468258125)

    def test_a_disagreement_beyond_epsilon_refuses(self) -> None:
        with self.assertRaises(RuntimeError) as caught:
            assert_cpu_paths_agree("FROZEN_Q3_E8", 51.0, 51.1)
        message = str(caught.exception)
        self.assertIn("FROZEN_Q3_E8", message)
        self.assertIn("51.1", message)

    def test_a_zero_artifact_metric_refuses_rather_than_dividing(self) -> None:
        with self.assertRaises(RuntimeError):
            assert_cpu_paths_agree("FROZEN_Q3_E8", 0.0, 0.0)


class BigfoldFoldSelectionTest(unittest.TestCase):
    """I7: the probe must ask BOTH the largest and the smallest fold."""

    def test_largest_and_smallest_are_selected(self) -> None:
        rows = {"E3": 100, "E4": 500, "FROZEN_Q3_E8": 900, "BURN_E2_STACK": 60}
        self.assertEqual(_select_probe_folds(rows),
                         ("FROZEN_Q3_E8", "BURN_E2_STACK"))

    def test_ties_break_on_fold_name(self) -> None:
        self.assertEqual(_select_probe_folds({"B": 10, "A": 10, "C": 5}),
                         ("A", "C"))

    def test_a_single_published_fold_refuses(self) -> None:
        with self.assertRaises(RuntimeError):
            _select_probe_folds({"E3": 100})

    def test_an_empty_roster_refuses(self) -> None:
        with self.assertRaises(RuntimeError):
            _select_probe_folds({})


class BigfoldForceGpuTest(unittest.TestCase):
    """I7/M4: the probe stays runnable after the flip sent the head to CPU."""

    def test_the_live_law_supplies_the_overlay_while_the_head_is_gpu(
            self) -> None:
        self.assertEqual(_probe_overlay(force_gpu=False),
                         {"task_type": "GPU", "devices": "0"})

    def test_after_a_flip_the_probe_refuses_without_force_gpu(self) -> None:
        with unittest.mock.patch(f"{__name__}.fit_backend_for_loss",
                                 return_value="CATBOOST_CPU"):
            with self.assertRaises(RuntimeError) as caught:
                _probe_overlay(force_gpu=False)
            self.assertIn("--force-gpu", str(caught.exception))

    def test_force_gpu_re_audits_a_flipped_head(self) -> None:
        with unittest.mock.patch(f"{__name__}.fit_backend_for_loss",
                                 return_value="CATBOOST_CPU"):
            self.assertEqual(_probe_overlay(force_gpu=True),
                             {"task_type": "GPU", "devices": "0"})


class BigfoldOverallVerdictTest(unittest.TestCase):
    """I7: GPU_OK requires GPU_OK on BOTH folds."""

    def test_both_folds_ok_is_ok(self) -> None:
        self.assertEqual(
            bigfold_overall_verdict({"a": "GPU_OK", "b": "GPU_OK"}), "GPU_OK")

    def test_one_degenerate_fold_degrades_the_run(self) -> None:
        self.assertEqual(
            bigfold_overall_verdict({"a": "GPU_OK", "b": "GPU_DEGENERATE"}),
            "GPU_DEGENERATE")

    def test_fewer_than_two_folds_refuses(self) -> None:
        with self.assertRaises(ValueError):
            bigfold_overall_verdict({"a": "GPU_OK"})


def main(argv: Sequence[str]) -> int:
    if "--selftest" in argv:
        result = unittest.main(argv=[argv[0]], exit=False).result
        return 0 if result.wasSuccessful() else 1
    dry_run = "--dry-run" in argv
    receipt = run_probe(dry_run=dry_run, force_gpu="--force-gpu" in argv)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    if dry_run:
        print("\ndry run: artifact loading validated, nothing fitted, "
              "no receipt written")
        return 0
    BIGFOLD_RECEIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    BIGFOLD_RECEIPT_PATH.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(f"\nreceipt -> {BIGFOLD_RECEIPT_PATH}")
    print(f"verdict: {receipt['verdict']}")
    # I7: a degenerate GPU fit must fail the shell, not just print a word.
    return 0 if receipt["verdict"] == "GPU_OK" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
