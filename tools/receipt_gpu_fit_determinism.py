"""DP-2 GPU determinism receipt for the Entry V2 CatBoost fit backend.

Pre-registered in artifacts/entry_v2/tabular_recovery/rehearsal/
FABLE5_SPEED_RESULT.md ADDENDUM v2 R1: fit the SAME frozen config THREE times
on this box's GPU and byte-compare the three model files AND their prediction
vectors on a fixed probe slice. All identical => BITWISE mode. Any byte differs
=> ARTIFACT_PIN mode (fit-once, the model hash is the identity, and the 3-fit
gate-metric spread is the published variance receipt).

The receipt selects the MODE only; per D-105 the GPU heads are used either way.

Beyond the two pre-registered hashes this records two more per repeat, because
the pre-registered pair alone cannot separate "the GPU computed something
different" from "CatBoost stamped a fresh GUID":
  * structure_sha256   - the trees only (CBM JSON minus model_info), i.e. the
                         model's semantic content with GUID/timestamp removed.
  * trajectory_sha256  - the per-iteration eval-metric history CatBoost stores
                         inside the model, the most sensitive drift probe there
                         is; two runs can agree on a truncated best model while
                         their training trajectories differ.

Read-only against the published round-0 E1R artifacts: both fit units are
strict-reconstructed from the published matrices and their reconstructed
receipts are asserted equal to the published bundle manifests' receipts before
any fit runs.

Receipt v2 (finding I6) fixes what the v1 verdict fields asked. The per-head
`bitwise` verdict now reads structure+prediction shas (the .cbm hash is kept as
metadata, because a fresh model_guid per fit makes it unrepeatable by
construction), and `seed_control_ok` reads structures_differ on BOTH heads. The
MODE stays ARTIFACT_PIN: production identity IS the .cbm hash, so semantic
determinism on one head does not license bitwise reproduction. v2 is DERIVED
from the shas v1 already published - no refit - and v1 is immutable.

Run:  nice -n 19 python3 tools/receipt_gpu_fit_determinism.py
Rebuild v2 from the published v1 (no GPU work, no refits):
      python3 tools/receipt_gpu_fit_determinism.py --rebuild-v2
Self-test (no GPU work):  python3 tools/receipt_gpu_fit_determinism.py --selftest
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Final, Mapping, Sequence
import unittest

sys.path.insert(0, "/workspace")

import catboost
from catboost import CatBoostError, CatBoostRegressor
from catboost.utils import eval_metric, get_gpu_device_count
import numpy as np

from engine.entry_v2.tabular_experiment import _range_mask
from engine.entry_v2.tabular_matrix_store import (
    load_action_matrix, load_component_matrix)
from engine.entry_v2.tabular_models import (
    _common_parameters, _config_from_json, _fit_with_early_stop)

GPU_DET_RECEIPT_SCHEMA: Final = "QRE2GPUDET1"
GPU_DET_RECEIPT_V2_SCHEMA: Final = "QRE2GPUDET2"
GPU_DET_ROUND: Final = Path(
    "/workspace/artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/"
    "curriculum/fits/round_0")
GPU_DET_RECEIPT_PATH: Final = Path(
    "/workspace/artifacts/entry_v2/tabular_recovery/diagnostics/"
    "gpu_fit_determinism_20260821.json")
GPU_DET_RECEIPT_V2_PATH: Final = Path(
    "/workspace/artifacts/entry_v2/tabular_recovery/diagnostics/"
    "gpu_fit_determinism_20260821_v2.json")
GPU_DET_SCRATCH: Final = Path("/workspace/artifacts/cache/gpu_det_tmp")
GPU_DET_PROBE_ROWS: Final = 50_000
GPU_DET_REPEATS: Final = 3
GPU_DET_FIRST_REAL_SEED: Final = 20260820
GPU_DET_CONTROL_SEED: Final = 20260821
GPU_DET_GPU_PARAMETERS: Final = {"task_type": "GPU", "devices": "0"}


def gpu_det_head_bitwise(
    structure_shas: Sequence[str], prediction_shas: Sequence[str],
) -> bool:
    """I6 verdict: the same TREES and the same predictions across repeats.

    The .cbm file hash is deliberately not consulted: CatBoost stamps a fresh
    model_guid and train_finish_time into every fit, so that hash can never
    repeat on GPU or CPU and would report drift where none exists. It stays in
    the receipt as metadata (see gpu_det_rebuild_v2).
    """

    if (len(structure_shas) != GPU_DET_REPEATS
            or len(prediction_shas) != GPU_DET_REPEATS):
        raise ValueError(
            f"determinism verdict needs {GPU_DET_REPEATS} repeats, got "
            f"{len(structure_shas)} structure / {len(prediction_shas)} "
            f"prediction shas")
    return len(set(structure_shas)) == 1 and len(set(prediction_shas)) == 1


def gpu_det_seed_control_ok(controls: Sequence[Mapping[str, object]]) -> bool:
    """I6: EVERY head's control must show two seeds producing different TREES.

    Same reasoning as the verdict: differing .cbm files prove nothing, because
    they differ even for identical fits. If two seeds cannot move the trees,
    the comparator is blind and the determinism verdict is inadmissible.
    """

    rows = list(controls)
    if not rows:
        raise ValueError("seed control needs at least one control row")
    return all(bool(row.get("structures_differ")) for row in rows)


def gpu_det_mode(heads: Mapping[str, Mapping[str, object]]) -> str:
    """ARTIFACT_PIN unless every head repeats its published IDENTITY exactly.

    Production identity is the .cbm hash (tabular_models._serialized_model_sha256),
    so BITWISE mode requires model_file_identical too. Semantic determinism on
    its own is recorded per head and changes nothing about the mode.
    """

    return ("BITWISE"
            if heads and all(bool(head.get("bitwise"))
                             and bool(head.get("model_file_identical"))
                             for head in heads.values())
            else "ARTIFACT_PIN")


def gpu_det_rebuild_v2(v1: Mapping[str, object], v1_sha256: str) -> dict:
    """Recompute the v2 verdict fields from the shas v1 already published.

    NO refits: every input is read out of the immutable v1 receipt. v1's own
    numbers are preserved under *_v1_* keys so the two receipts can be read
    side by side.
    """

    payload = json.loads(json.dumps(v1))
    heads = payload.get("heads")
    if not isinstance(heads, dict) or not heads:
        raise ValueError(f"v1 receipt carries no heads to rebuild: {v1_sha256}")
    for name, head in heads.items():
        for key in ("structure_sha256", "prediction_sha256", "model_sha256"):
            if not isinstance(head.get(key), list):
                raise ValueError(
                    f"v1 head {name!r} has no {key} list to rebuild the "
                    f"verdict from; got {head.get(key)!r}")
        head["bitwise_v1_model_file"] = bool(head["bitwise"])
        head["bitwise"] = gpu_det_head_bitwise(
            head["structure_sha256"], head["prediction_sha256"])
        head["bitwise_definition"] = (
            "structure_sha256 identical across repeats AND prediction_sha256 "
            "identical across repeats")
        head["model_sha256_role"] = (
            "metadata: CatBoost stamps a fresh model_guid and "
            "train_finish_time into every fit, so this hash never repeats and "
            "is not part of the determinism verdict")
    controls = [payload[key] for key in ("seed_control", "seed_control_secondary")
                if isinstance(payload.get(key), dict)]
    payload["seed_control_ok_v1_model_sha"] = bool(payload.get("seed_control_ok"))
    payload["seed_control_ok"] = gpu_det_seed_control_ok(controls)
    payload["seed_control_definition"] = (
        "every head's two-seed control shows structures_differ")
    payload["mode_v1"] = payload.get("mode")
    payload["mode"] = gpu_det_mode(heads)
    payload["mode_definition"] = (
        "BITWISE only if every head repeats its published .cbm identity; "
        "semantic determinism alone stays ARTIFACT_PIN (conservative)")
    payload["schema"] = GPU_DET_RECEIPT_V2_SCHEMA
    payload["supersedes"] = {
        "receipt": GPU_DET_RECEIPT_PATH.name,
        "sha256": v1_sha256,
        "immutable": True,
        "relation": (
            "v2 recomputes the verdict fields from v1's published shas; v1 is "
            "unchanged and remains the record of what was measured"),
    }
    payload["refits_performed"] = False
    return payload


def gpu_det_metric_spread(values: Sequence[float]) -> float:
    """max-min of the repeats' gate metric: the ARTIFACT_PIN variance receipt."""

    numbers = [float(value) for value in values]
    if not numbers:
        raise ValueError("metric spread needs at least one repeat value")
    return max(numbers) - min(numbers)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def gpu_det_sha256_array(values: "np.ndarray") -> str:
    """Hash a float array with the byte order PINNED little-endian
    (temporal-15: a native-order sha is a property of the host, not the
    prediction — the receipt must be comparable across byte orders)."""
    pinned = np.ascontiguousarray(np.asarray(values, dtype="<f8"))
    return _sha256_bytes(pinned.tobytes())


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_json(value: object) -> str:
    return _sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def _training_metrics(model: object) -> dict:
    raw = dict(model.get_metadata()).get("training")
    if raw is None:
        raise RuntimeError("fitted model carries no training metadata")
    return json.loads(raw)["metrics"]


class GpuDetFitProbe:
    """The four hashes plus the trajectory facts for one fitted model."""

    def __init__(self, model: object, probe: np.ndarray, tag: str) -> None:
        GPU_DET_SCRATCH.mkdir(parents=True, exist_ok=True)
        cbm = GPU_DET_SCRATCH / f"{tag}.cbm"
        structure = GPU_DET_SCRATCH / f"{tag}.json"
        try:
            model.save_model(str(cbm), format="cbm")
            model.save_model(str(structure), format="json")
            self.model_sha256 = _sha256_file(cbm)
            payload = json.loads(structure.read_text())
            payload.pop("model_info", None)
            self.structure_sha256 = _sha256_json(payload)
        finally:
            cbm.unlink(missing_ok=True)
            structure.unlink(missing_ok=True)
        self.prediction_sha256 = gpu_det_sha256_array(model.predict(probe))
        metrics = _training_metrics(model)
        self.trajectory_sha256 = _sha256_json(metrics["test_metrics_history"])
        self.best_iteration = int(metrics["best_iteration"])
        self.tree_count = int(model.tree_count_)


def _strict_manifest(path: Path, expected_schema: str) -> dict:
    manifest = json.loads(path.read_text())
    if manifest.get("schema") != expected_schema:
        raise RuntimeError(
            f"published manifest schema differs at {path}: "
            f"{manifest.get('schema')!r} != {expected_schema!r}")
    return manifest


def _published_metric(model: object) -> float:
    """The eval metric the published CPU fit stored inside its own artifact."""

    metrics = _training_metrics(model)
    entry = metrics["test_metrics_history"][int(metrics["best_iteration"])]
    return float(next(iter(entry[0].values())))


class GpuDetUnit:
    """One published (fold, seed) fit unit, strict-reconstructed for refitting."""

    def __init__(
        self, *, head: str, fold: str, loss_function: str, manifest: dict,
        train: object, validation: object, target_field: str,
        published_model_path: Path, fallback_parameters: Mapping[str, object],
    ) -> None:
        self.head = head
        self.fold = fold
        self.loss_function = loss_function
        self.manifest = manifest
        self.train = train
        self.validation = validation
        self.target_field = target_field
        self.published_model_path = published_model_path
        self.fallback_parameters = dict(fallback_parameters)
        self.gpu_default_refusal: str | None = None
        self.applied_parameters = dict(GPU_DET_GPU_PARAMETERS)
        self.config = _config_from_json(manifest["config"])
        if self.config.receipt_sha256 != manifest["config_sha256"]:
            raise RuntimeError(f"{head}: frozen config receipt differs")
        if (train.receipt_sha256 != manifest["train_receipt_sha256"]
                or validation.receipt_sha256
                != manifest["validation_receipt_sha256"]):
            raise RuntimeError(
                f"{head}: reconstructed fit inputs are not the published ones")
        self.x = np.asarray(train.x, np.float32)
        self.vx = np.asarray(validation.x, np.float32)
        # temporal-15: draw the probe from VALIDATION rows — a train-row
        # probe is the least sensitive place to look for prediction drift.
        self.probe = self.vx[:min(GPU_DET_PROBE_ROWS, len(self.vx))]

    def _fit(self, seed: int, extra: Mapping[str, object]) -> tuple[object, float]:
        parameters = {**_common_parameters(self.config, seed), **extra}
        model = CatBoostRegressor(loss_function=self.loss_function, **parameters)
        started = time.perf_counter()
        _fit_with_early_stop(
            model, self.x, getattr(self.train, self.target_field),
            self.train.sample_weight, self.vx,
            getattr(self.validation, self.target_field),
            self.validation.sample_weight,
            patience=self.config.early_stopping_rounds)
        return model, time.perf_counter() - started

    def fit_on_gpu(self, seed: int) -> tuple[object, float]:
        """Fit with task_type/devices only; fall back only if CatBoost refuses.

        A refusal and the knob that unblocked it are recorded in the receipt:
        anything beyond task_type/devices is a deviation the reader must see.
        """

        try:
            return self._fit(seed, self.applied_parameters)
        except CatBoostError as refusal:
            if (self.gpu_default_refusal is not None
                    or not self.fallback_parameters):
                raise
            self.gpu_default_refusal = str(refusal)
            self.applied_parameters = {**GPU_DET_GPU_PARAMETERS,
                                       **self.fallback_parameters}
            print(f"  [{self.head}] GPU refused the task_type/devices-only "
                  f"invocation: {refusal}\n  [{self.head}] retrying with "
                  f"{self.fallback_parameters}", flush=True)
            return self._fit(seed, self.applied_parameters)

    def gate_metric(self, model: object) -> float:
        """The head's own eval-set loss, weighted exactly as the fit weights it."""

        approx = np.asarray(model.predict(self.vx), np.float64)
        label = np.asarray(
            getattr(self.validation, self.target_field), np.float64)
        weight = np.asarray(self.validation.sample_weight, np.float64)
        return float(eval_metric(label, approx, self.loss_function,
                                 weight=weight)[0])

    def cpu_published(self) -> dict:
        model = CatBoostRegressor()
        model.load_model(str(self.published_model_path), format="cbm")
        metrics = _training_metrics(model)
        return {
            "model_sha256": _sha256_file(self.published_model_path),
            "tree_count": int(model.tree_count_),
            "best_iteration": int(metrics["best_iteration"]),
            "metric_from_artifact": _published_metric(model),
            "metric_recomputed_on_validation": self.gate_metric(model),
        }


def _component_unit() -> GpuDetUnit:
    bundle = (GPU_DET_ROUND / "component_models/catboost/real"
              / f"seed_{GPU_DET_FIRST_REAL_SEED}" / "BURN_E2_STACK"
              / "component_bundle")
    manifest = _strict_manifest(bundle / "manifest.json", "QRE2TABCOMPONENTCB3")
    matrix = load_component_matrix(GPU_DET_ROUND / "component_matrix")
    return GpuDetUnit(
        head="component_adverse_quantile_q90", fold="BURN_E2_STACK",
        loss_function="Quantile:alpha=0.9", manifest=manifest,
        train=matrix.mask(_range_mask(
            matrix.day, tuple(manifest["train_day_range"]))),
        validation=matrix.mask(_range_mask(
            matrix.day, tuple(manifest["validation_day_range"]))),
        target_field="adverse_usd",
        published_model_path=bundle / "adverse_q90.cbm",
        fallback_parameters={})


def _action_unit() -> GpuDetUnit:
    bundle = (GPU_DET_ROUND / "action_models/catboost/real"
              / f"seed_{GPU_DET_FIRST_REAL_SEED}" / "E3" / "action_MultiRMSE")
    manifest = _strict_manifest(bundle / "manifest.json", "QRE2TABACTIONCB3")
    matrix = load_action_matrix(
        GPU_DET_ROUND / "action_matrices/real" / f"seed_{GPU_DET_FIRST_REAL_SEED}")
    return GpuDetUnit(
        head="action_multirmse_regret", fold="E3",
        loss_function="MultiRMSE", manifest=manifest,
        train=matrix.mask(_range_mask(
            matrix.day, tuple(manifest["train_day_range"]))),
        validation=matrix.mask(_range_mask(
            matrix.day, tuple(manifest["validation_day_range"]))),
        target_field="regret_log_target",
        published_model_path=bundle / "action.cbm",
        # CatBoost GPU defaults boosting_type=Ordered on a fold this small and
        # then refuses MultiRMSE outright. CPU resolves Plain, so Plain is the
        # value that keeps the GPU arm on the published algorithm. Recorded as
        # a deviation because it is beyond the permitted task_type/devices.
        fallback_parameters={"boosting_type": "Plain"})


def _measure_head(unit: GpuDetUnit) -> dict:
    probes: list[GpuDetFitProbe] = []
    wall_seconds: list[float] = []
    metrics: list[float] = []
    for repeat in range(GPU_DET_REPEATS):
        model, wall = unit.fit_on_gpu(GPU_DET_FIRST_REAL_SEED)
        probe = GpuDetFitProbe(model, unit.probe, f"{unit.head}_r{repeat}")
        probes.append(probe)
        wall_seconds.append(round(wall, 3))
        metrics.append(unit.gate_metric(model))
        print(f"  [{unit.head}] repeat {repeat}: {wall:.1f}s "
              f"trees={probe.tree_count} best_iter={probe.best_iteration} "
              f"model={probe.model_sha256[:16]} "
              f"struct={probe.structure_sha256[:16]} "
              f"pred={probe.prediction_sha256[:16]} "
              f"traj={probe.trajectory_sha256[:16]}", flush=True)
    model_shas = [probe.model_sha256 for probe in probes]
    prediction_shas = [probe.prediction_sha256 for probe in probes]
    structure_shas = [probe.structure_sha256 for probe in probes]
    trajectory_shas = [probe.trajectory_sha256 for probe in probes]
    return {
        "loss_function": unit.loss_function,
        "fold": unit.fold,
        "seed": GPU_DET_FIRST_REAL_SEED,
        "published_bundle_receipt_sha256": unit.manifest["receipt_sha256"],
        "frozen_config_sha256": unit.manifest["config_sha256"],
        "train_day_range": unit.manifest["train_day_range"],
        "validation_day_range": unit.manifest["validation_day_range"],
        "train_rows": int(len(unit.x)),
        "validation_rows": int(len(unit.vx)),
        "features": int(unit.x.shape[1]),
        "probe_rows": int(len(unit.probe)),
        "train_receipt_sha256": unit.train.receipt_sha256,
        "validation_receipt_sha256": unit.validation.receipt_sha256,
        "applied_fit_parameters_beyond_frozen_config": unit.applied_parameters,
        "gpu_default_refusal": unit.gpu_default_refusal,
        "model_sha256": model_shas,
        "prediction_sha256": prediction_shas,
        "structure_sha256": structure_shas,
        "trajectory_sha256": trajectory_shas,
        "tree_count": [probe.tree_count for probe in probes],
        "best_iteration": [probe.best_iteration for probe in probes],
        "wall_s": wall_seconds,
        "gate_metric": metrics,
        "cpu_published": unit.cpu_published(),
        "bitwise": gpu_det_head_bitwise(structure_shas, prediction_shas),
        "model_file_identical": len(set(model_shas)) == 1,
        "prediction_identical": len(set(prediction_shas)) == 1,
        "structure_identical": len(set(structure_shas)) == 1,
        "trajectory_identical": len(set(trajectory_shas)) == 1,
        "gate_metric_spread": gpu_det_metric_spread(metrics),
    }


def _seed_control(unit: GpuDetUnit, first_repeat: dict) -> dict:
    """Prove the comparator can SEE a difference: two seeds must not collide."""

    model, wall = unit.fit_on_gpu(GPU_DET_CONTROL_SEED)
    probe = GpuDetFitProbe(model, unit.probe, f"{unit.head}_seedcontrol")
    print(f"  [{unit.head}] seed control {GPU_DET_CONTROL_SEED}: {wall:.1f}s "
          f"model={probe.model_sha256[:16]} "
          f"struct={probe.structure_sha256[:16]}", flush=True)
    return {
        "head": unit.head,
        "seed_a": GPU_DET_FIRST_REAL_SEED,
        "seed_b": GPU_DET_CONTROL_SEED,
        "model_sha256_a": first_repeat["model_sha256"][0],
        "model_sha256_b": probe.model_sha256,
        "structure_sha256_a": first_repeat["structure_sha256"][0],
        "structure_sha256_b": probe.structure_sha256,
        "wall_s_b": round(wall, 3),
        "shas_differ":
            first_repeat["model_sha256"][0] != probe.model_sha256,
        "structures_differ":
            first_repeat["structure_sha256"][0] != probe.structure_sha256,
    }


def _gpu_identity() -> dict:
    query = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,driver_version",
         "--format=csv,noheader"], capture_output=True, text=True, check=True)
    name, driver = (part.strip() for part in query.stdout.strip().split(","))
    return {"gpu_name": name, "driver_version": driver,
            "gpu_device_count": int(get_gpu_device_count())}


def _mode_rationale(heads: Mapping[str, dict]) -> list[str]:
    notes = []
    for name, head in heads.items():
        if not head["model_file_identical"]:
            notes.append(
                f"{name}: the three .cbm files differ. CatBoost stamps a fresh "
                "model_guid and train_finish_time into every fit, so the .cbm "
                "hash - which is the production identity via "
                "tabular_models._serialized_model_sha256 - can never repeat, on "
                "GPU or CPU. Read structure_sha256 for the semantic answer.")
        if not head["trajectory_identical"]:
            notes.append(
                f"{name}: the per-iteration eval-metric histories differ across "
                "repeats of the SAME seed and data. This is real GPU numeric "
                "nondeterminism in the boosting trajectory, not metadata.")
        if head["structure_identical"] and not head["trajectory_identical"]:
            notes.append(
                f"{name}: the final trees still matched only because "
                f"use_best_model truncated to best_iteration="
                f"{head['best_iteration'][0]}; that agreement is an artifact of "
                "the early stop, not evidence of a deterministic fit.")
        if not head["structure_identical"]:
            notes.append(
                f"{name}: the fitted trees themselves differ across repeats.")
    return notes


def run_receipt() -> dict:
    print("loading component unit ...", flush=True)
    component = _component_unit()
    print(f"  component train={len(component.x)}x{component.x.shape[1]} "
          f"validation={len(component.vx)} probe={len(component.probe)}",
          flush=True)
    component_result = _measure_head(component)
    component_control = _seed_control(component, component_result)
    del component

    print("loading action unit ...", flush=True)
    action = _action_unit()
    print(f"  action train={len(action.x)}x{action.x.shape[1]} "
          f"validation={len(action.vx)} probe={len(action.probe)}", flush=True)
    action_result = _measure_head(action)
    action_control = _seed_control(action, action_result)

    heads = {"component_adverse_quantile_q90": component_result,
             "action_multirmse_regret": action_result}
    mode = gpu_det_mode(heads)
    deviations = [
        f"{name}: required {head['applied_fit_parameters_beyond_frozen_config']}"
        f" because the task_type/devices-only invocation was refused: "
        f"{head['gpu_default_refusal']}"
        for name, head in heads.items() if head["gpu_default_refusal"]]
    return {
        "schema": GPU_DET_RECEIPT_SCHEMA,
        "pre_registration": (
            "artifacts/entry_v2/tabular_recovery/rehearsal/"
            "FABLE5_SPEED_RESULT.md ADDENDUM v2 R1"),
        "catboost_version": catboost.__version__,
        "numpy_version": np.__version__,
        **_gpu_identity(),
        "repeats": GPU_DET_REPEATS,
        "probe_rows_requested": GPU_DET_PROBE_ROWS,
        "gpu_parameters": dict(GPU_DET_GPU_PARAMETERS),
        "gpu_ram_part": "catboost default (not set)",
        "source_round": str(GPU_DET_ROUND),
        "heads": heads,
        "seed_control": component_control,
        "seed_control_secondary": action_control,
        "seed_control_ok": gpu_det_seed_control_ok(
            [component_control, action_control]),
        "mode": mode,
        "mode_rationale": _mode_rationale(heads),
        "deviations_requiring_ruling": deviations,
        "variance_receipt_gate_metric_spread": {
            name: head["gate_metric_spread"] for name, head in heads.items()},
    }


class GpuDetVerdictTest(unittest.TestCase):
    """Fixture pair for the comparator: it must catch drift and accept identity."""

    def test_identical_structure_and_predictions_are_bitwise(self) -> None:
        self.assertTrue(gpu_det_head_bitwise(["a" * 64] * 3, ["b" * 64] * 3))

    def test_structure_drift_is_caught(self) -> None:
        self.assertFalse(gpu_det_head_bitwise(
            ["a" * 64, "a" * 64, "c" * 64], ["b" * 64] * 3))

    def test_prediction_drift_is_caught(self) -> None:
        self.assertFalse(gpu_det_head_bitwise(
            ["a" * 64] * 3, ["b" * 64, "b" * 64, "d" * 64]))

    def test_model_file_drift_alone_is_not_a_determinism_failure(self) -> None:
        """I6: the .cbm hash is metadata - a fresh GUID per fit is not drift."""

        head = {"structure_sha256": ["a" * 64] * 3,
                "prediction_sha256": ["b" * 64] * 3,
                "model_sha256": ["c" * 64, "d" * 64, "e" * 64]}
        self.assertTrue(gpu_det_head_bitwise(head["structure_sha256"],
                                             head["prediction_sha256"]))

    def test_wrong_repeat_count_refuses(self) -> None:
        with self.assertRaises(ValueError):
            gpu_det_head_bitwise(["a" * 64] * 2, ["b" * 64] * 2)

    def test_metric_spread(self) -> None:
        self.assertAlmostEqual(gpu_det_metric_spread([1.5, 1.25, 1.75]), 0.5)
        self.assertEqual(gpu_det_metric_spread([2.0, 2.0, 2.0]), 0.0)


class GpuDetArraySerializationTest(unittest.TestCase):
    def test_pinned_little_endian_equality(self) -> None:
        values = np.asarray([1.5, -2.25, 3e12], np.float64)
        big = values.astype(">f8")
        self.assertEqual(gpu_det_sha256_array(values), gpu_det_sha256_array(big))

    def test_matches_explicit_little_endian_bytes(self) -> None:
        values = np.asarray([0.1, 0.2], np.float64)
        expected = hashlib.sha256(
            np.ascontiguousarray(values.astype("<f8")).tobytes()).hexdigest()
        self.assertEqual(gpu_det_sha256_array(values), expected)

    def test_non_contiguous_view_hashes_like_its_copy(self) -> None:
        base = np.arange(20, dtype=np.float64)
        view = base[::2]
        self.assertEqual(gpu_det_sha256_array(view),
                         gpu_det_sha256_array(view.copy()))

    def test_different_values_differ(self) -> None:
        a = np.asarray([1.0, 2.0], np.float64)
        b = np.asarray([1.0, 2.0000000001], np.float64)
        self.assertNotEqual(gpu_det_sha256_array(a), gpu_det_sha256_array(b))


class GpuDetSeedControlTest(unittest.TestCase):
    """I6: the control asks whether the comparator can see a SEMANTIC change."""

    def test_both_controls_must_show_different_structures(self) -> None:
        self.assertTrue(gpu_det_seed_control_ok(
            [{"structures_differ": True}, {"structures_differ": True}]))

    def test_one_control_with_identical_structures_fails(self) -> None:
        self.assertFalse(gpu_det_seed_control_ok(
            [{"structures_differ": True}, {"structures_differ": False}]))

    def test_differing_model_files_alone_do_not_pass_the_control(self) -> None:
        self.assertFalse(gpu_det_seed_control_ok(
            [{"structures_differ": False, "shas_differ": True},
             {"structures_differ": False, "shas_differ": True}]))

    def test_no_controls_refuses(self) -> None:
        with self.assertRaises(ValueError):
            gpu_det_seed_control_ok([])


class GpuDetModeTest(unittest.TestCase):
    """I6: the mode stays conservative - production identity is the .cbm hash."""

    def test_semantic_determinism_alone_stays_artifact_pin(self) -> None:
        heads = {"h": {"bitwise": True, "model_file_identical": False}}
        self.assertEqual(gpu_det_mode(heads), "ARTIFACT_PIN")

    def test_bitwise_needs_repeatable_model_files_on_every_head(self) -> None:
        heads = {"a": {"bitwise": True, "model_file_identical": True},
                 "b": {"bitwise": True, "model_file_identical": True}}
        self.assertEqual(gpu_det_mode(heads), "BITWISE")
        heads["b"]["bitwise"] = False
        self.assertEqual(gpu_det_mode(heads), "ARTIFACT_PIN")


class GpuDetRebuildV2Test(unittest.TestCase):
    """I6: v2 is DERIVED from the published v1 shas - no refit, v1 untouched."""

    @staticmethod
    def _v1() -> dict:
        return {
            "schema": GPU_DET_RECEIPT_SCHEMA,
            "mode": "ARTIFACT_PIN",
            "seed_control_ok": True,
            "seed_control": {"head": "component", "structures_differ": True,
                             "shas_differ": True},
            "seed_control_secondary": {"head": "action",
                                       "structures_differ": True,
                                       "shas_differ": True},
            "heads": {
                "component": {"bitwise": False,
                              "model_sha256": ["c1" * 32, "c2" * 32, "c3" * 32],
                              "structure_sha256": ["s" * 64] * 3,
                              "prediction_sha256": ["p" * 64] * 3,
                              "model_file_identical": False,
                              "structure_identical": True,
                              "prediction_identical": True},
                "action": {"bitwise": False,
                           "model_sha256": ["a1" * 32, "a2" * 32, "a3" * 32],
                           "structure_sha256": ["x" * 64, "y" * 64, "z" * 64],
                           "prediction_sha256": ["u" * 64, "v" * 64, "w" * 64],
                           "model_file_identical": False,
                           "structure_identical": False,
                           "prediction_identical": False}}}

    def test_semantic_verdict_replaces_the_model_file_verdict(self) -> None:
        v2 = gpu_det_rebuild_v2(self._v1(), "f" * 64)
        self.assertTrue(v2["heads"]["component"]["bitwise"])
        self.assertFalse(v2["heads"]["action"]["bitwise"])
        self.assertFalse(v2["heads"]["component"]["bitwise_v1_model_file"])

    def test_model_sha_is_demoted_to_metadata_but_kept(self) -> None:
        v1 = self._v1()
        v2 = gpu_det_rebuild_v2(v1, "f" * 64)
        for head in ("component", "action"):
            self.assertEqual(v2["heads"][head]["model_sha256"],
                             v1["heads"][head]["model_sha256"])
            self.assertIn("metadata", v2["heads"][head]["model_sha256_role"])

    def test_seed_control_is_recomputed_from_both_structures(self) -> None:
        v1 = self._v1()
        v1["seed_control_secondary"]["structures_differ"] = False
        v2 = gpu_det_rebuild_v2(v1, "f" * 64)
        self.assertFalse(v2["seed_control_ok"])
        self.assertTrue(v2["seed_control_ok_v1_model_sha"])

    def test_mode_stays_artifact_pin(self) -> None:
        self.assertEqual(gpu_det_rebuild_v2(self._v1(), "f" * 64)["mode"],
                         "ARTIFACT_PIN")

    def test_v2_names_the_immutable_v1_it_came_from(self) -> None:
        v2 = gpu_det_rebuild_v2(self._v1(), "f" * 64)
        self.assertEqual(v2["schema"], GPU_DET_RECEIPT_V2_SCHEMA)
        self.assertEqual(v2["supersedes"]["sha256"], "f" * 64)
        self.assertEqual(v2["supersedes"]["receipt"],
                         GPU_DET_RECEIPT_PATH.name)
        self.assertTrue(v2["supersedes"]["immutable"])
        self.assertFalse(v2["refits_performed"])

    def test_rebuild_does_not_mutate_the_v1_payload(self) -> None:
        v1 = self._v1()
        before = json.dumps(v1, sort_keys=True)
        gpu_det_rebuild_v2(v1, "f" * 64)
        self.assertEqual(json.dumps(v1, sort_keys=True), before)

    def test_a_v1_missing_a_head_sha_refuses(self) -> None:
        v1 = self._v1()
        del v1["heads"]["action"]["structure_sha256"]
        with self.assertRaises(ValueError) as caught:
            gpu_det_rebuild_v2(v1, "f" * 64)
        self.assertIn("action", str(caught.exception))


def publish_v2_receipt() -> dict:
    """Write v2 beside the immutable v1, derived from v1's shas. No refits."""

    v1 = json.loads(GPU_DET_RECEIPT_PATH.read_text())
    v2 = gpu_det_rebuild_v2(v1, _sha256_file(GPU_DET_RECEIPT_PATH))
    GPU_DET_RECEIPT_V2_PATH.write_text(
        json.dumps(v2, indent=2, sort_keys=True) + "\n")
    return v2


def main(argv: Sequence[str]) -> int:
    if "--selftest" in argv:
        result = unittest.main(argv=[argv[0]], exit=False).result
        return 0 if result.wasSuccessful() else 1
    if "--rebuild-v2" in argv:
        v2 = publish_v2_receipt()
        print(json.dumps(v2, indent=2, sort_keys=True))
        print(f"\nreceipt -> {GPU_DET_RECEIPT_V2_PATH}")
        print(f"mode: {v2['mode']}  seed_control_ok: {v2['seed_control_ok']}")
        return 0
    started = time.time()
    receipt = run_receipt()
    if not receipt["seed_control_ok"]:
        raise RuntimeError(
            "seed control failed: a head's two seeds produced the same tree "
            "structure - the comparator or the fit plumbing is blind, so the "
            "determinism verdict is not admissible")
    receipt["total_wall_s"] = round(time.time() - started, 3)
    GPU_DET_RECEIPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    GPU_DET_RECEIPT_PATH.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    if GPU_DET_SCRATCH.is_dir() and not any(GPU_DET_SCRATCH.iterdir()):
        GPU_DET_SCRATCH.rmdir()
    print(json.dumps(receipt, indent=2, sort_keys=True))
    print(f"\nreceipt -> {GPU_DET_RECEIPT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
