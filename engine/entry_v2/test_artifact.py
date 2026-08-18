#!/usr/bin/env python3
"""Focused frozen-artifact persistence and fail-closed tests."""

from __future__ import annotations

import gc
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

import torch

from . import common as C
from .artifact import (
    _probe_outputs,
    load_frozen_artifact,
    save_frozen_artifact,
)
from .model import FullPrefixEntryModel, model_state_sha256
from .event_pack import CATEGORY_SIZES, CATEGORICAL_FIELDS, CONTINUOUS_FIELDS
from .policy import ModelInputBinding
from .session_stream import MODEL_ARRAYS_CONVERSION_LAW_SHA256
from .train import (
    PassReceipt,
    TrainFoldNormalizer,
    TrainingArtifact,
    TrainingConfig,
    TrainingTrace,
)


def _binding() -> ModelInputBinding:
    return ModelInputBinding(
        tuple(CONTINUOUS_FIELDS), tuple(CATEGORICAL_FIELDS),
        tuple(CATEGORY_SIZES),
        MODEL_ARRAYS_CONVERSION_LAW_SHA256,
        C.object_sha256("artifact-session-stream-receipts"),
        C.object_sha256("artifact-corpus-receipt"),
        C.object_sha256("artifact-corpus-source-lineage"),
        C.object_sha256("artifact-clock-law-receipt"),
    )


def _normalizer(event: int, candidate: int, context: int) -> TrainFoldNormalizer:
    values = {
        "schema": "entry-v2-train-normalizer-v3",
        "event_mean": tuple(0.0 for _ in range(event)),
        "event_scale": tuple(1.0 for _ in range(event)),
        "candidate_mean": tuple(0.0 for _ in range(candidate)),
        "candidate_scale": tuple(1.0 for _ in range(candidate)),
        "context_mean": tuple(0.0 for _ in range(context)),
        "context_scale": tuple(1.0 for _ in range(context)),
        "horizon_mean": (0.0, 0.0, 0.0, 0.0),
        "horizon_scale": (1.0, 1.0, 1.0, 1.0),
        "fit_days": (20240102,),
        "fit_candidate_sha256": C.object_sha256(["synthetic-candidate"]),
        "model_input_binding": _binding().as_dict(),
    }
    return TrainFoldNormalizer(
        event_mean=values["event_mean"],
        event_scale=values["event_scale"],
        candidate_mean=values["candidate_mean"],
        candidate_scale=values["candidate_scale"],
        context_mean=values["context_mean"],
        context_scale=values["context_scale"],
        horizon_mean=values["horizon_mean"],
        horizon_scale=values["horizon_scale"],
        fit_days=values["fit_days"],
        fit_candidate_sha256=values["fit_candidate_sha256"],
        model_input_binding=_binding(),
        receipt_sha256=C.object_sha256(values),
    )


def _trace(
    config: TrainingConfig,
    normalizer: TrainFoldNormalizer,
    state_sha256: str,
) -> TrainingTrace:
    core = {
        "schema": "entry-v2-fixed-staged-training-v2",
        "config_sha256": config.receipt()["sha256"],
        "teacher_sha256": C.object_sha256("synthetic-teacher"),
        "normalizer_sha256": normalizer.receipt_sha256,
        "initial_model_sha256": state_sha256,
        "final_model_sha256": state_sha256,
        "supervision_weights_sha256": C.object_sha256("synthetic-weights"),
        "passes": [
            {"name": name, "rows": 1, "optimizer_steps": 1,
             "mean_loss": 0.125, "model_sha256": state_sha256,
             "matched_pairs": matched, "stage_receipt": None}
            for name, matched in (
                ("fold_causal_self_supervision", 0),
                ("full_population_oracle_multitask", 0),
                ("matched_hard_negative_listwise", 1),
            )
        ],
        "session_order_sha256": C.object_sha256("synthetic-session-order"),
        "model_input_binding": _binding().as_dict(),
    }
    return TrainingTrace(
        config_sha256=core["config_sha256"],
        teacher_sha256=core["teacher_sha256"],
        normalizer_sha256=core["normalizer_sha256"],
        initial_model_sha256=core["initial_model_sha256"],
        final_model_sha256=core["final_model_sha256"],
        supervision_weights_sha256=core["supervision_weights_sha256"],
        passes=tuple(PassReceipt(
            row["name"], row["rows"], row["optimizer_steps"],
            row["mean_loss"], row["model_sha256"], row["matched_pairs"]
        ) for row in core["passes"]),
        session_order_sha256=core["session_order_sha256"],
        model_input_binding=_binding(),
        receipt_sha256=C.object_sha256(core),
    )


def _rewrite_json(path: Path, value: dict) -> None:
    os.chmod(path, 0o644)
    raw = C.canonical_bytes(value)
    with open(path, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(path, 0o444)


class FrozenArtifactTest(unittest.TestCase):
    def test_round_trip_canary_and_fail_closed_mutations(self) -> None:
        torch.manual_seed(20260816)
        encoder = FullPrefixEntryModel(
            len(CONTINUOUS_FIELDS),
            3,
            2,
            4,
            event_category_sizes=CATEGORY_SIZES,
            max_context_history=2,
            dropout=0.0,
        )
        from .train import EntryLearningSystem

        system = EntryLearningSystem(encoder, n_phase_classes=3).cpu().float().eval()
        normalizer = _normalizer(len(CONTINUOUS_FIELDS), 3, 2)
        config = TrainingConfig(device="cpu", bf16=False, n_phase_classes=3)
        state_hash = model_state_sha256(system)
        trace = _trace(config, normalizer, state_hash)
        training = TrainingArtifact(system, normalizer, trace)

        C.CACHE_ROOT.mkdir(parents=True, exist_ok=True)
        container = Path(tempfile.mkdtemp(prefix="artifact_test_", dir=C.CACHE_ROOT))
        target = container / "frozen"
        try:
            manifest = save_frozen_artifact(target, training, config)
            architecture = manifest["architecture"]
            before = _probe_outputs(system, architecture)
            loaded = load_frozen_artifact(target)

            self.assertEqual(model_state_sha256(loaded.system), state_hash)
            self.assertEqual(loaded.normalizer, normalizer)
            self.assertEqual(loaded.config, config)
            self.assertEqual(loaded.trace, trace)
            self.assertEqual(loaded.model_input_binding, _binding())
            self.assertEqual(
                loaded.system.encoder.context.max_history,
                encoder.context.max_history,
            )
            after = _probe_outputs(loaded.system, architecture)
            self.assertEqual(set(before), set(after))
            for name in before:
                self.assertTrue(torch.equal(before[name], after[name]), name)

            # A self-consistent but foreign runtime receipt must fail before
            # state decode, not merely because its outer file hash changed.
            runtime_path = target / "runtime.json"
            manifest_path = target / "manifest.json"
            runtime_original = runtime_path.read_bytes()
            manifest_original = manifest_path.read_bytes()
            runtime = json.loads(runtime_original)
            runtime["versions"]["torch"] = "mutated-runtime"
            runtime_core = dict(runtime)
            runtime_core.pop("receipt_sha256")
            runtime["receipt_sha256"] = C.object_sha256(runtime_core)
            _rewrite_json(runtime_path, runtime)
            foreign = json.loads(manifest_original)
            runtime_bytes = runtime_path.read_bytes()
            foreign["runtime_sha256"] = runtime["receipt_sha256"]
            foreign["files"]["runtime.json"] = {
                "sha256": hashlib.sha256(runtime_bytes).hexdigest(),
                "bytes": len(runtime_bytes),
            }
            foreign_core = dict(foreign)
            foreign_core.pop("receipt_sha256")
            foreign["receipt_sha256"] = C.object_sha256(foreign_core)
            _rewrite_json(manifest_path, foreign)
            with self.assertRaisesRegex(C.EntryV2Refusal, "runtime.*pin mismatch"):
                load_frozen_artifact(target)
            _rewrite_json(runtime_path, json.loads(runtime_original))
            _rewrite_json(manifest_path, json.loads(manifest_original))

            # One changed tensor byte is refused by the raw payload hash before
            # a safetensors header or tensor is decoded.
            model_path = target / "model.safetensors"
            os.chmod(model_path, 0o644)
            with open(model_path, "r+b") as handle:
                handle.seek(-1, os.SEEK_END)
                original_byte = handle.read(1)
                handle.seek(-1, os.SEEK_END)
                handle.write(bytes((original_byte[0] ^ 1,)))
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(model_path, 0o444)
            with self.assertRaisesRegex(C.EntryV2Refusal, "payload changed"):
                load_frozen_artifact(target)
            os.chmod(model_path, 0o644)
            with open(model_path, "r+b") as handle:
                handle.seek(-1, os.SEEK_END)
                handle.write(original_byte)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(model_path, 0o444)

            with self.assertRaisesRegex(C.EntryV2Refusal, "already exists"):
                save_frozen_artifact(target, training, config)
            with self.assertRaisesRegex(C.EntryV2Refusal, "HOLDOUT"):
                save_frozen_artifact(container / "frozen_20250701", training, config)
        finally:
            del training, system
            gc.collect()
            shutil.rmtree(container)


if __name__ == "__main__":
    unittest.main()
