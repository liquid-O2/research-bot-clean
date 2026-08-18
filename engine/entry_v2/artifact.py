#!/usr/bin/env python3
"""Fail-closed persistence for a frozen entry-v2 learning system.

The artifact is a new, atomically published directory.  Tensor payloads use
``safetensors`` exclusively; JSON receipts are canonical, independently
hashed, and small enough to validate before the model payload is decoded.
Loading also reconstructs the declared architecture before accepting any
state, and runs a deterministic CPU/FP32 inference canary bit-for-bit.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import ctypes
import errno
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import sys
import tempfile
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import numpy as np
from safetensors import safe_open
import safetensors
from safetensors.torch import save_file
import torch
from torch import Tensor

from . import common as C
from .model import FullPrefixEntryModel, model_state_sha256
from .train import (
    HORIZONS_SECONDS,
    EntryLearningSystem,
    ModelInputBinding,
    PassReceipt,
    TrainFoldNormalizer,
    TrainingArtifact,
    TrainingConfig,
    TrainingTrace,
)


ARTIFACT_SCHEMA = "entry-v2-frozen-neural-artifact-v2"
ARCHITECTURE_SCHEMA = "entry-v2-learning-system-architecture-v2"
NORMALIZER_DOCUMENT_SCHEMA = "entry-v2-normalizer-artifact-v3"
TRAINING_DOCUMENT_SCHEMA = "entry-v2-training-artifact-v2"
RUNTIME_SCHEMA = "entry-v2-runtime-manifest-v2"
MODEL_FILE = "model.safetensors"
PROBE_FILE = "cpu_fp32_probe.safetensors"
NORMALIZER_FILE = "normalizer.json"
TRAINING_FILE = "training.json"
RUNTIME_FILE = "runtime.json"
MANIFEST_FILE = "manifest.json"
PAYLOAD_FILES = (
    MODEL_FILE,
    PROBE_FILE,
    NORMALIZER_FILE,
    TRAINING_FILE,
    RUNTIME_FILE,
)
_HEX64 = re.compile(r"[0-9a-f]{64}")
_MAX_JSON_BYTES = 8 << 20
_SAFE_DTYPE = {
    torch.bool: "BOOL",
    torch.uint8: "U8",
    torch.int8: "I8",
    torch.int16: "I16",
    torch.int32: "I32",
    torch.int64: "I64",
    torch.float16: "F16",
    torch.bfloat16: "BF16",
    torch.float32: "F32",
    torch.float64: "F64",
}


@dataclass(frozen=True)
class FrozenNeuralArtifact:
    """A verified, CPU/FP32, evaluation-mode artifact."""

    system: EntryLearningSystem
    normalizer: TrainFoldNormalizer
    config: TrainingConfig
    trace: TrainingTrace
    model_input_binding: ModelInputBinding
    manifest: Mapping[str, Any]
    path: Path


@dataclass(frozen=True)
class _ProbeBatch:
    asset: str
    event_continuous: Tensor
    event_categorical: Tensor
    candidate_cutoffs: Tensor
    candidate_features: Tensor
    context_values: Tensor
    context_type_ids: Tensor
    context_valid: Tensor


def _refuse(message: str) -> None:
    raise C.EntryV2Refusal(message)


def _require_keys(value: Any, keys: Sequence[str], name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict) or set(value) != set(keys):
        present = sorted(value) if isinstance(value, dict) else type(value).__name__
        _refuse(f"{name} keys mismatch: {present}")
    return value


def _require_hash(value: Any, name: str) -> str:
    if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
        _refuse(f"invalid {name} sha256")
    return value


def _require_int(value: Any, name: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _refuse(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        _refuse(f"{name} must be at least {minimum}")
    return int(value)


def _require_float(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _refuse(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        _refuse(f"{name} must be finite")
    return result


def _guard_artifact_path(path: os.PathLike[str] | str, *, existing: bool) -> Path:
    original = Path(path).absolute()
    if existing:
        try:
            resolved = original.resolve(strict=True)
        except FileNotFoundError as exc:
            raise C.EntryV2Refusal(f"artifact does not exist: {original}") from exc
    else:
        try:
            parent = original.parent.resolve(strict=True)
        except FileNotFoundError as exc:
            raise C.EntryV2Refusal(
                f"artifact parent must already exist: {original.parent}"
            ) from exc
        resolved = parent / original.name
    resolved = C.assert_workspace_output(resolved)

    # A date hidden in any directory component is still a holdout path.
    for part in resolved.parts:
        for d8 in C.dates_in_basename(part):
            C.guard_date(d8)

    cursor = Path(original.anchor)
    for part in original.parts[1:]:
        cursor /= part
        if cursor.exists() or cursor.is_symlink():
            if cursor.is_symlink():
                _refuse(f"artifact path contains a symlink: {cursor}")
    if existing:
        mode = original.lstat().st_mode
        if not stat.S_ISDIR(mode):
            _refuse(f"artifact target is not a directory: {original}")
    elif original.exists() or original.is_symlink():
        _refuse(f"artifact target already exists: {original}")
    return resolved


def _open_regular(path: Path) -> tuple[int, os.stat_result]:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise C.EntryV2Refusal(f"cannot open artifact file safely: {path}") from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            _refuse(f"artifact payload is not a regular file: {path}")
        return fd, info
    except BaseException:
        os.close(fd)
        raise


def _hash_file(path: Path) -> tuple[str, int]:
    fd, info = _open_regular(path)
    digest = hashlib.sha256()
    try:
        with os.fdopen(fd, "rb", closefd=True) as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                digest.update(block)
    except OSError as exc:
        raise C.EntryV2Refusal(f"cannot hash artifact payload: {path}") from exc
    return digest.hexdigest(), int(info.st_size)


def _read_canonical_json(path: Path) -> Mapping[str, Any]:
    fd, info = _open_regular(path)
    if info.st_size > _MAX_JSON_BYTES:
        os.close(fd)
        _refuse(f"JSON receipt is unexpectedly large: {path}")
    try:
        with os.fdopen(fd, "rb", closefd=True) as handle:
            raw = handle.read(_MAX_JSON_BYTES + 1)
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise C.EntryV2Refusal(f"invalid JSON receipt: {path}") from exc
    if not isinstance(value, dict) or raw != C.canonical_bytes(value):
        _refuse(f"receipt is not canonical JSON: {path}")
    return value


def _write_bytes(path: Path, raw: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb", closefd=True) as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    _write_bytes(path, C.canonical_bytes(value))


def _fsync_file(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_CLOEXEC", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _rename_noreplace(source: Path, target: Path) -> None:
    """Atomically publish a directory without ever replacing an old one."""

    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        _refuse("atomic RENAME_NOREPLACE is unavailable on this runtime")
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    result = renameat2(
        -100,
        os.fsencode(source),
        -100,
        os.fsencode(target),
        1,
    )
    if result == 0:
        return
    error = ctypes.get_errno()
    if error == errno.EEXIST:
        _refuse(f"artifact target appeared during publication: {target}")
    raise C.EntryV2Refusal(
        f"atomic artifact publication failed: {os.strerror(error)}"
    )


def _receipt(core: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(core)
    result["receipt_sha256"] = C.object_sha256(core)
    return result


def _verify_receipt(value: Mapping[str, Any], name: str) -> dict[str, Any]:
    if "receipt_sha256" not in value:
        _refuse(f"{name} has no receipt_sha256")
    core = dict(value)
    claimed = _require_hash(core.pop("receipt_sha256"), f"{name} receipt")
    if C.object_sha256(core) != claimed:
        _refuse(f"{name} receipt hash mismatch")
    return core


def _dropout_of(encoder: FullPrefixEntryModel) -> float:
    layers = tuple(encoder.local.layers) + tuple(encoder.long_layers) + tuple(
        encoder.context.layers
    )
    values = {float(layer.dropout) for layer in layers}
    if len(values) != 1:
        _refuse("encoder has inconsistent attention dropout values")
    value = values.pop()
    if not math.isfinite(value) or not 0.0 <= value < 1.0:
        _refuse("encoder dropout is outside [0, 1)")
    return value


def _architecture(
    system: EntryLearningSystem, model_input_binding: ModelInputBinding
) -> dict[str, Any]:
    model_input_binding.validate()
    encoder = dict(system.encoder.architecture())
    context = dict(encoder["context"])
    context["max_history"] = int(system.encoder.context.max_history)
    encoder["context"] = context
    return {
        "schema": ARCHITECTURE_SCHEMA,
        "encoder": encoder,
        "dropout": _dropout_of(system.encoder),
        "horizon_outputs": int(system.horizon_head.out_features),
        "phase_classes": int(system.phase_head.out_features),
        "model_input_binding": model_input_binding.as_dict(),
    }


def _reconstruct(architecture: Mapping[str, Any]) -> EntryLearningSystem:
    _require_keys(
        architecture,
        (
            "schema",
            "encoder",
            "dropout",
            "horizon_outputs",
            "phase_classes",
            "model_input_binding",
        ),
        "architecture",
    )
    if architecture["schema"] != ARCHITECTURE_SCHEMA:
        _refuse("unknown learning-system architecture schema")
    binding = ModelInputBinding.from_mapping(
        architecture["model_input_binding"]
    )
    encoder = _require_keys(
        architecture["encoder"],
        (
            "event_continuous",
            "event_category_sizes",
            "block_size",
            "local",
            "long",
            "context",
            "assets",
            "candidate_features",
            "value_bins",
        ),
        "encoder architecture",
    )
    context = _require_keys(
        encoder["context"],
        ("continuous", "types", "width", "depth", "heads", "max_history"),
        "context architecture",
    )
    categories = encoder["event_category_sizes"]
    if not isinstance(categories, list) or not categories:
        _refuse("event category sizes must be a non-empty list")
    if _require_int(encoder["event_continuous"], "event width", minimum=1) != len(
        binding.event_continuous_fields
    ):
        _refuse("architecture event width differs from bound V2 field order")
    category_sizes = tuple(
        _require_int(value, f"event category size {index}", minimum=1)
        for index, value in enumerate(categories)
    )
    if category_sizes != binding.event_category_sizes:
        _refuse("architecture category sizes differ from bound V3 categories")
    if _require_int(architecture["horizon_outputs"], "horizon outputs", minimum=1) != len(
        HORIZONS_SECONDS
    ):
        _refuse("artifact horizon-head width changed")
    model = FullPrefixEntryModel(
        _require_int(encoder["event_continuous"], "event width", minimum=1),
        _require_int(encoder["candidate_features"], "candidate width", minimum=1),
        _require_int(context["continuous"], "context width", minimum=1),
        _require_int(context["types"], "context types", minimum=1),
        event_category_sizes=category_sizes,
        n_value_bins=_require_int(encoder["value_bins"], "value bins", minimum=2),
        block_size=_require_int(encoder["block_size"], "block size", minimum=1),
        max_context_history=_require_int(
            context["max_history"], "context max_history", minimum=1
        ),
        dropout=_require_float(architecture["dropout"], "dropout"),
    )
    system = EntryLearningSystem(
        model,
        _require_int(architecture["phase_classes"], "phase classes", minimum=2),
    )
    if _architecture(system, binding) != architecture:
        _refuse("declared architecture is not reconstructible by this code")
    return system


def _finite_tuple(value: Any, name: str, *, positive: bool = False) -> tuple[float, ...]:
    if not isinstance(value, (list, tuple)) or not value:
        _refuse(f"{name} must be a non-empty numeric list")
    result = tuple(_require_float(item, f"{name}[{index}]") for index, item in enumerate(value))
    if positive and any(item <= 0 for item in result):
        _refuse(f"{name} must be strictly positive")
    return result


def _normalizer_document(normalizer: TrainFoldNormalizer) -> dict[str, Any]:
    core = {
        "schema": NORMALIZER_DOCUMENT_SCHEMA,
        "normalizer": normalizer.receipt(),
    }
    return _receipt(core)


def _parse_normalizer(
    document: Mapping[str, Any], architecture: Mapping[str, Any]
) -> TrainFoldNormalizer:
    _require_keys(document, ("schema", "normalizer", "receipt_sha256"), "normalizer document")
    core = _verify_receipt(document, "normalizer document")
    if core["schema"] != NORMALIZER_DOCUMENT_SCHEMA:
        _refuse("unknown normalizer document schema")
    raw = _require_keys(
        core["normalizer"],
        (
            "schema",
            "event_mean",
            "event_scale",
            "candidate_mean",
            "candidate_scale",
            "context_mean",
            "context_scale",
            "horizon_mean",
            "horizon_scale",
            "fit_days",
            "fit_candidate_sha256",
            "model_input_binding",
            "receipt_sha256",
        ),
        "normalizer",
    )
    if raw["schema"] != "entry-v2-train-normalizer-v3":
        _refuse("unknown train-fold normalizer schema")
    receipt_core = dict(raw)
    claimed = _require_hash(receipt_core.pop("receipt_sha256"), "normalizer")
    if C.object_sha256(receipt_core) != claimed:
        _refuse("normalizer receipt hash mismatch")

    days_raw = raw["fit_days"]
    if not isinstance(days_raw, (list, tuple)) or not days_raw:
        _refuse("normalizer fit_days must be non-empty")
    days = tuple(_require_int(day, "normalizer fit day") for day in days_raw)
    if days != tuple(sorted(set(days))):
        _refuse("normalizer fit days are not sorted and unique")
    for day in days:
        C.guard_date(day)

    binding = ModelInputBinding.from_mapping(raw["model_input_binding"])
    architecture_binding = ModelInputBinding.from_mapping(
        architecture["model_input_binding"]
    )
    if binding != architecture_binding:
        _refuse("normalizer/architecture model input binding mismatch")
    normalizer = TrainFoldNormalizer(
        event_mean=_finite_tuple(raw["event_mean"], "event_mean"),
        event_scale=_finite_tuple(raw["event_scale"], "event_scale", positive=True),
        candidate_mean=_finite_tuple(raw["candidate_mean"], "candidate_mean"),
        candidate_scale=_finite_tuple(
            raw["candidate_scale"], "candidate_scale", positive=True
        ),
        context_mean=_finite_tuple(raw["context_mean"], "context_mean"),
        context_scale=_finite_tuple(raw["context_scale"], "context_scale", positive=True),
        horizon_mean=_finite_tuple(raw["horizon_mean"], "horizon_mean"),
        horizon_scale=_finite_tuple(raw["horizon_scale"], "horizon_scale", positive=True),
        fit_days=days,
        fit_candidate_sha256=_require_hash(
            raw["fit_candidate_sha256"], "normalizer candidate-set"
        ),
        model_input_binding=binding,
        receipt_sha256=claimed,
    )
    if C.canonical_bytes(normalizer.receipt()) != C.canonical_bytes(raw):
        _refuse("normalizer did not round-trip exactly")
    encoder = architecture["encoder"]
    expected = {
        "event": int(encoder["event_continuous"]),
        "candidate": int(encoder["candidate_features"]),
        "context": int(encoder["context"]["continuous"]),
        "horizon": len(HORIZONS_SECONDS),
    }
    for name, width in expected.items():
        if len(getattr(normalizer, f"{name}_mean")) != width or len(
            getattr(normalizer, f"{name}_scale")
        ) != width:
            _refuse(f"normalizer {name} width does not match architecture")
    return normalizer


def _trace_core(trace: TrainingTrace) -> dict[str, Any]:
    return {
        "schema": "entry-v2-fixed-staged-training-v2",
        "config_sha256": trace.config_sha256,
        "teacher_sha256": trace.teacher_sha256,
        "normalizer_sha256": trace.normalizer_sha256,
        "initial_model_sha256": trace.initial_model_sha256,
        "final_model_sha256": trace.final_model_sha256,
        "supervision_weights_sha256": trace.supervision_weights_sha256,
        "passes": [{
            "name": item.name,
            "rows": item.rows,
            "optimizer_steps": item.optimizer_steps,
            "mean_loss": item.mean_loss,
            "model_sha256": item.model_sha256,
            "matched_pairs": item.matched_pairs,
            "stage_receipt": (None if item.stage_receipt is None
                              else dict(item.stage_receipt)),
        } for item in trace.passes],
        "session_order_sha256": trace.session_order_sha256,
        "model_input_binding": trace.model_input_binding.as_dict(),
    }


def _training_document(config: TrainingConfig, trace: TrainingTrace) -> dict[str, Any]:
    trace_value = _trace_core(trace)
    trace_value["receipt_sha256"] = trace.receipt_sha256
    core = {
        "schema": TRAINING_DOCUMENT_SCHEMA,
        "config": config.receipt(),
        "trace": trace_value,
    }
    return _receipt(core)


def _parse_training(
    document: Mapping[str, Any], normalizer: TrainFoldNormalizer
) -> tuple[TrainingConfig, TrainingTrace]:
    _require_keys(document, ("schema", "config", "trace", "receipt_sha256"), "training document")
    core = _verify_receipt(document, "training document")
    if core["schema"] != TRAINING_DOCUMENT_SCHEMA:
        _refuse("unknown training document schema")
    config_raw = _require_keys(
        core["config"],
        (
            "schema",
            "seed",
            "workers",
            "device",
            "bf16",
            "learning_rate",
            "weight_decay",
            "max_grad_norm",
            "n_phase_classes",
            "horizons_seconds",
            "value_scale_usd",
            "mae_scale_usd",
            "loss_weights",
            "passes",
            "sha256",
        ),
        "training config receipt",
    )
    if config_raw["schema"] != "entry-v2-learning-config-v2":
        _refuse("unknown training config schema")
    config_hash = _require_hash(config_raw["sha256"], "training config")
    config_hash_core = dict(config_raw)
    config_hash_core.pop("sha256")
    if C.object_sha256(config_hash_core) != config_hash:
        _refuse("training config receipt hash mismatch")
    if not isinstance(config_raw["bf16"], bool) or not isinstance(config_raw["device"], str):
        _refuse("training config scalar types are invalid")
    config = TrainingConfig(
        seed=_require_int(config_raw["seed"], "training seed"),
        workers=_require_int(config_raw["workers"], "training workers"),
        device=config_raw["device"],
        bf16=config_raw["bf16"],
        learning_rate=_require_float(config_raw["learning_rate"], "learning rate"),
        weight_decay=_require_float(config_raw["weight_decay"], "weight decay"),
        max_grad_norm=_require_float(config_raw["max_grad_norm"], "max grad norm"),
        n_phase_classes=_require_int(config_raw["n_phase_classes"], "phase classes", minimum=2),
    )
    if config.receipt() != config_raw:
        _refuse("training config differs from the running training contract")

    trace_raw = _require_keys(
        core["trace"],
        (
            "schema",
            "config_sha256",
            "teacher_sha256",
            "normalizer_sha256",
            "initial_model_sha256",
            "final_model_sha256",
            "supervision_weights_sha256",
            "passes",
            "session_order_sha256",
            "model_input_binding",
            "receipt_sha256",
        ),
        "training trace",
    )
    if trace_raw["schema"] != "entry-v2-fixed-staged-training-v2":
        _refuse("unknown training trace schema")
    trace_receipt = _require_hash(trace_raw["receipt_sha256"], "training trace")
    trace_hash_core = dict(trace_raw)
    trace_hash_core.pop("receipt_sha256")
    if C.object_sha256(trace_hash_core) != trace_receipt:
        _refuse("training trace receipt hash mismatch")
    passes_raw = trace_raw["passes"]
    expected_passes = (
        "fold_causal_self_supervision",
        "full_population_oracle_multitask",
        "matched_hard_negative_listwise",
    )
    if not isinstance(passes_raw, list) or len(passes_raw) != len(expected_passes):
        _refuse("training trace must contain the three frozen stages")
    parsed_passes = []
    for expected_name, raw_pass in zip(expected_passes, passes_raw):
        pass_value = _require_keys(
            raw_pass,
            ("name", "rows", "optimizer_steps", "mean_loss", "model_sha256",
             "matched_pairs", "stage_receipt"),
            "pass receipt",
        )
        if pass_value["name"] != expected_name:
            _refuse("training trace stage order differs from the frozen schedule")
        matched = _require_int(pass_value["matched_pairs"], "matched pairs", minimum=0)
        if expected_name == "matched_hard_negative_listwise" and matched < 1:
            _refuse("matched-listwise stage has no matched pair")
        if expected_name != "matched_hard_negative_listwise" and matched != 0:
            _refuse("non-listwise stage unexpectedly reports matched pairs")
        stage_receipt = pass_value["stage_receipt"]
        if stage_receipt is not None and not isinstance(stage_receipt, Mapping):
            _refuse("pass stage receipt is not an object or null")
        parsed_passes.append(PassReceipt(
            name=expected_name,
            rows=_require_int(pass_value["rows"], "pass rows", minimum=1),
            optimizer_steps=_require_int(
                pass_value["optimizer_steps"], "optimizer steps", minimum=1
            ),
            mean_loss=_require_float(pass_value["mean_loss"], "pass mean loss"),
            model_sha256=_require_hash(pass_value["model_sha256"], "pass model"),
            matched_pairs=matched,
            stage_receipt=(None if stage_receipt is None
                           else MappingProxyType(dict(stage_receipt))),
        ))
    trace_binding = ModelInputBinding.from_mapping(
        trace_raw["model_input_binding"]
    )
    if trace_binding != normalizer.model_input_binding:
        _refuse("training trace/normalizer model input binding mismatch")
    trace = TrainingTrace(
        config_sha256=_require_hash(trace_raw["config_sha256"], "trace config"),
        teacher_sha256=_require_hash(trace_raw["teacher_sha256"], "trace teacher"),
        normalizer_sha256=_require_hash(
            trace_raw["normalizer_sha256"], "trace normalizer"
        ),
        initial_model_sha256=_require_hash(
            trace_raw["initial_model_sha256"], "trace initial model"
        ),
        final_model_sha256=_require_hash(
            trace_raw["final_model_sha256"], "trace final model"
        ),
        supervision_weights_sha256=_require_hash(
            trace_raw["supervision_weights_sha256"], "trace supervision weights"
        ),
        passes=tuple(parsed_passes),
        session_order_sha256=_require_hash(
            trace_raw["session_order_sha256"], "trace session order"
        ),
        model_input_binding=trace_binding,
        receipt_sha256=trace_receipt,
    )
    if trace.config_sha256 != config_hash:
        _refuse("training trace/config hash mismatch")
    if trace.normalizer_sha256 != normalizer.receipt_sha256:
        _refuse("training trace/normalizer hash mismatch")
    if _trace_core(trace) != trace_hash_core:
        _refuse("training trace did not round-trip exactly")
    return config, trace


def _distribution_files(distribution_name: str) -> list[dict[str, Any]]:
    try:
        distribution = importlib.metadata.distribution(distribution_name)
    except importlib.metadata.PackageNotFoundError as exc:
        raise C.EntryV2Refusal(f"runtime distribution is missing: {distribution_name}") from exc
    result: list[dict[str, Any]] = []
    for item in distribution.files or ():
        relative = str(item)
        if not (relative.endswith(".dist-info/METADATA") or relative.endswith(".dist-info/RECORD")):
            continue
        path = Path(distribution.locate_file(item)).resolve()
        digest, size = _hash_file(path)
        result.append({"path": str(path), "sha256": digest, "bytes": size})
    if not result:
        _refuse(f"runtime distribution has no hashable metadata: {distribution_name}")
    return sorted(result, key=lambda value: value["path"])


def _module_file(module_name: str) -> dict[str, Any]:
    module = importlib.import_module(module_name)
    raw_path = getattr(module, "__file__", None)
    if not raw_path:
        _refuse(f"runtime module has no resolvable file: {module_name}")
    path = Path(raw_path).resolve()
    digest, size = _hash_file(path)
    return {"module": module_name, "path": str(path), "sha256": digest, "bytes": size}


def _runtime_manifest() -> dict[str, Any]:
    source_paths = {
        "artifact": Path(__file__).resolve(),
        "common": Path(C.__file__).resolve(),
        "model": Path(sys.modules[FullPrefixEntryModel.__module__].__file__).resolve(),
        "train": Path(sys.modules[TrainingConfig.__module__].__file__).resolve(),
    }
    sources: dict[str, Any] = {}
    for name, path in source_paths.items():
        digest, size = _hash_file(path)
        sources[name] = {"path": str(path), "sha256": digest, "bytes": size}

    executable = Path(sys.executable).resolve()
    executable_hash, executable_size = _hash_file(executable)
    core = {
        "schema": RUNTIME_SCHEMA,
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "version_full": sys.version,
            "executable": str(executable),
            "executable_sha256": executable_hash,
            "executable_bytes": executable_size,
        },
        "versions": {
            "numpy": np.__version__,
            "torch": torch.__version__,
            "cuda": torch.version.cuda,
            "cudnn": torch.backends.cudnn.version(),
            "safetensors": safetensors.__version__,
        },
        "packages": {
            "numpy": {
                "module": _module_file("numpy"),
                "distribution_receipts": _distribution_files("numpy"),
            },
            "torch": {
                "module": _module_file("torch"),
                "distribution_receipts": _distribution_files("torch"),
            },
            "safetensors": {
                "module": _module_file("safetensors"),
                "distribution_receipts": _distribution_files("safetensors"),
            },
        },
        "native_libraries": [
            _module_file("numpy._core._multiarray_umath"),
            _module_file("safetensors._safetensors_rust"),
            _module_file("torch._C"),
        ],
        "source_files": sources,
    }
    return _receipt(core)


def _state_hash(state: Mapping[str, Tensor]) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(state.items()):
        cpu = value.detach().contiguous().cpu()
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(tuple(cpu.shape)).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(cpu.dtype).encode("ascii"))
        digest.update(b"\0")
        digest.update(cpu.reshape(-1).view(torch.uint8).numpy().tobytes())
    return digest.hexdigest()


def _capture_state(system: EntryLearningSystem) -> tuple[dict[str, Tensor], str]:
    before = model_state_sha256(system)
    state: dict[str, Tensor] = {}
    for name, value in system.state_dict().items():
        if value.layout != torch.strided:
            _refuse(f"state tensor is not dense: {name}")
        if value.is_floating_point() and value.dtype != torch.float32:
            _refuse(f"frozen inference requires FP32 state, got {name}={value.dtype}")
        state[name] = value.detach().to(device="cpu").contiguous().clone()
    after = model_state_sha256(system)
    captured = _state_hash(state)
    if before != after or captured != before:
        _refuse("model state changed while the frozen snapshot was captured")
    return state, captured


def _probe_batch(architecture: Mapping[str, Any]) -> _ProbeBatch:
    encoder = architecture["encoder"]
    event_width = int(encoder["event_continuous"])
    categories = len(encoder["event_category_sizes"])
    candidate_width = int(encoder["candidate_features"])
    context_width = int(encoder["context"]["continuous"])
    candidate = torch.arange(candidate_width, dtype=torch.float32)
    candidate = (candidate + 1.0) / float(candidate_width + 1)
    context = torch.arange(context_width, dtype=torch.float32)
    context = (context + 1.0) / float(context_width + 1)
    return _ProbeBatch(
        asset="SI",
        event_continuous=torch.empty((0, event_width), dtype=torch.float32),
        event_categorical=torch.empty((0, categories), dtype=torch.int64),
        candidate_cutoffs=torch.zeros(1, dtype=torch.int64),
        candidate_features=candidate[None, :],
        context_values=context[None, None, None, :],
        context_type_ids=torch.zeros(1, dtype=torch.int64),
        context_valid=torch.ones((1, 1, 1), dtype=torch.bool),
    )


def _probe_outputs(
    system: EntryLearningSystem, architecture: Mapping[str, Any]
) -> dict[str, Tensor]:
    if any(value.device.type != "cpu" for value in system.state_dict().values()):
        _refuse("inference canary requires a CPU system")
    system.eval()
    previous_threads = torch.get_num_threads()
    try:
        torch.set_num_threads(1)
        with torch.inference_mode():
            output = system(_probe_batch(architecture))  # type: ignore[arg-type]
    finally:
        torch.set_num_threads(previous_threads)
    core = output.core
    values = {
        "embedding": core.embedding,
        "prefix_state": core.prefix_state,
        "context_state": core.context_state,
        "value_bin_logits": core.value_bin_logits,
        "value_quantiles": core.value_quantiles,
        "expected_value": core.expected_value,
        "top3_logit": core.top3_logit,
        "mae_quantiles": core.mae_quantiles,
        "wall_logit": core.wall_logit,
        "take_logit": core.take_logit,
        "horizon_value": output.horizon_value,
        "phase_logits": output.phase_logits,
    }
    result: dict[str, Tensor] = {}
    for name, value in values.items():
        cpu = value.detach().to(device="cpu").contiguous()
        if cpu.dtype != torch.float32 or not bool(torch.isfinite(cpu).all()):
            _refuse(f"CPU inference canary is not finite FP32: {name}")
        result[name] = cpu.clone()
    return result


def _validate_safetensor_header(
    path: Path,
    expected: Mapping[str, Tensor],
    metadata: Mapping[str, str],
) -> None:
    try:
        with safe_open(str(path), framework="pt", device="cpu") as handle:
            if handle.metadata() != dict(metadata):
                _refuse(f"safetensors metadata mismatch: {path.name}")
            if set(handle.keys()) != set(expected):
                _refuse(f"safetensors state keys mismatch: {path.name}")
            for name, tensor in expected.items():
                view = handle.get_slice(name)
                dtype = _SAFE_DTYPE.get(tensor.dtype)
                if dtype is None or view.get_dtype() != dtype:
                    _refuse(f"safetensors dtype mismatch for {name}")
                if tuple(view.get_shape()) != tuple(tensor.shape):
                    _refuse(f"safetensors shape mismatch for {name}")
    except C.EntryV2Refusal:
        raise
    except Exception as exc:
        raise C.EntryV2Refusal(f"invalid safetensors header: {path}") from exc


def _load_safetensors(path: Path) -> dict[str, Tensor]:
    try:
        with safe_open(str(path), framework="pt", device="cpu") as handle:
            return {name: handle.get_tensor(name) for name in handle.keys()}
    except Exception as exc:
        raise C.EntryV2Refusal(f"cannot decode safetensors payload: {path}") from exc


def save_frozen_artifact(
    path: os.PathLike[str] | str,
    artifact: TrainingArtifact,
    config: TrainingConfig,
) -> Mapping[str, Any]:
    """Write and atomically publish a new frozen neural artifact directory."""

    target = _guard_artifact_path(path, existing=False)
    binding = artifact.normalizer.model_input_binding
    binding.validate()
    if artifact.trace.model_input_binding != binding:
        _refuse("training artifact has conflicting model input bindings")
    architecture = _architecture(artifact.system, binding)
    architecture_hash = C.object_sha256(architecture)

    # Validate all small, date-bearing receipts before touching model state.
    normalizer_document = _normalizer_document(artifact.normalizer)
    normalizer = _parse_normalizer(normalizer_document, architecture)
    training_document = _training_document(config, artifact.trace)
    parsed_config, trace = _parse_training(training_document, normalizer)
    if parsed_config.n_phase_classes != architecture["phase_classes"]:
        _refuse("training config phase count does not match the model")
    runtime = _runtime_manifest()
    state, state_hash = _capture_state(artifact.system)
    if trace.final_model_sha256 != state_hash:
        _refuse("training trace final model hash does not match the frozen state")

    # Run the reference canary on an independently reconstructed CPU system.
    probe_system = _reconstruct(architecture)
    probe_system.load_state_dict(state, strict=True)
    if model_state_sha256(probe_system) != state_hash:
        _refuse("independent reconstruction changed the frozen model state")
    probe = _probe_outputs(probe_system, architecture)
    del probe_system

    parent = target.parent
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp.", dir=parent))
    published = False
    try:
        model_metadata = {
            "schema": ARTIFACT_SCHEMA,
            "architecture_sha256": architecture_hash,
            "model_state_sha256": state_hash,
            "model_input_binding_sha256": binding.binding_sha256,
        }
        save_file(state, str(temporary / MODEL_FILE), metadata=model_metadata)
        _fsync_file(temporary / MODEL_FILE)
        probe_metadata = {
            "schema": "entry-v2-cpu-fp32-probe-v2",
            "architecture_sha256": architecture_hash,
            "model_state_sha256": state_hash,
            "model_input_binding_sha256": binding.binding_sha256,
        }
        save_file(probe, str(temporary / PROBE_FILE), metadata=probe_metadata)
        _fsync_file(temporary / PROBE_FILE)
        _write_json(temporary / NORMALIZER_FILE, normalizer_document)
        _write_json(temporary / TRAINING_FILE, training_document)
        _write_json(temporary / RUNTIME_FILE, runtime)

        files: dict[str, Any] = {}
        for filename in PAYLOAD_FILES:
            digest, size = _hash_file(temporary / filename)
            files[filename] = {"sha256": digest, "bytes": size}
        manifest_core = {
            "schema": ARTIFACT_SCHEMA,
            "architecture": architecture,
            "architecture_sha256": architecture_hash,
            "model_state_sha256": state_hash,
            "normalizer_receipt_sha256": normalizer.receipt_sha256,
            "config_sha256": config.receipt()["sha256"],
            "training_trace_sha256": trace.receipt_sha256,
            "runtime_sha256": runtime["receipt_sha256"],
            "model_input_binding": binding.as_dict(),
            "model_input_binding_sha256": binding.binding_sha256,
            "files": files,
        }
        manifest = _receipt(manifest_core)
        _write_json(temporary / MANIFEST_FILE, manifest)
        for child in temporary.iterdir():
            os.chmod(child, 0o444)
        _fsync_directory(temporary)
        _rename_noreplace(temporary, target)
        published = True
        _fsync_directory(parent)
        return manifest
    finally:
        if not published and temporary.exists():
            shutil.rmtree(temporary)


def _verify_manifest(directory: Path) -> Mapping[str, Any]:
    manifest = _read_canonical_json(directory / MANIFEST_FILE)
    _require_keys(
        manifest,
        (
            "schema",
            "architecture",
            "architecture_sha256",
            "model_state_sha256",
            "normalizer_receipt_sha256",
            "config_sha256",
            "training_trace_sha256",
            "runtime_sha256",
            "model_input_binding",
            "model_input_binding_sha256",
            "files",
            "receipt_sha256",
        ),
        "artifact manifest",
    )
    core = _verify_receipt(manifest, "artifact manifest")
    if core["schema"] != ARTIFACT_SCHEMA:
        _refuse("unknown frozen artifact schema")
    architecture_hash = _require_hash(
        core["architecture_sha256"], "architecture"
    )
    if C.object_sha256(core["architecture"]) != architecture_hash:
        _refuse("architecture hash mismatch")
    for field in (
        "model_state_sha256",
        "normalizer_receipt_sha256",
        "config_sha256",
        "training_trace_sha256",
        "runtime_sha256",
        "model_input_binding_sha256",
    ):
        _require_hash(core[field], field)
    binding = ModelInputBinding.from_mapping(core["model_input_binding"])
    if binding.binding_sha256 != core["model_input_binding_sha256"]:
        _refuse("artifact manifest model input binding hash mismatch")

    files = _require_keys(core["files"], PAYLOAD_FILES, "artifact file table")
    actual_names = {item.name for item in directory.iterdir()}
    if actual_names != set(PAYLOAD_FILES) | {MANIFEST_FILE}:
        _refuse("artifact directory contains missing or unreceipted files")
    # Hash every payload, including model bytes, before safetensors sees them.
    for filename in PAYLOAD_FILES:
        entry = _require_keys(files[filename], ("sha256", "bytes"), f"file receipt {filename}")
        expected_hash = _require_hash(entry["sha256"], f"file {filename}")
        expected_size = _require_int(entry["bytes"], f"file size {filename}", minimum=1)
        actual_hash, actual_size = _hash_file(directory / filename)
        if (actual_hash, actual_size) != (expected_hash, expected_size):
            _refuse(f"artifact payload changed: {filename}")
    return manifest


def load_frozen_artifact(
    path: os.PathLike[str] | str,
) -> FrozenNeuralArtifact:
    """Verify, reconstruct, and load a frozen artifact on CPU in FP32 eval mode."""

    directory = _guard_artifact_path(path, existing=True)
    manifest = _verify_manifest(directory)

    # Runtime, code, dates, and all receipt relationships precede model decode.
    runtime = _read_canonical_json(directory / RUNTIME_FILE)
    _require_keys(
        runtime,
        (
            "schema",
            "python",
            "versions",
            "packages",
            "native_libraries",
            "source_files",
            "receipt_sha256",
        ),
        "runtime manifest",
    )
    _verify_receipt(runtime, "runtime manifest")
    if runtime["receipt_sha256"] != manifest["runtime_sha256"]:
        _refuse("runtime manifest hash relationship changed")
    if runtime != _runtime_manifest():
        _refuse("runtime, package, native-library, or source-code pin mismatch")

    architecture = manifest["architecture"]
    binding = ModelInputBinding.from_mapping(manifest["model_input_binding"])
    architecture_binding = ModelInputBinding.from_mapping(
        architecture["model_input_binding"]
    )
    if architecture_binding != binding:
        _refuse("manifest/architecture model input binding mismatch")
    system = _reconstruct(architecture)
    normalizer_document = _read_canonical_json(directory / NORMALIZER_FILE)
    normalizer = _parse_normalizer(normalizer_document, architecture)
    if normalizer.receipt_sha256 != manifest["normalizer_receipt_sha256"]:
        _refuse("normalizer/manifest hash mismatch")
    if normalizer.model_input_binding != binding:
        _refuse("normalizer/manifest model input binding mismatch")
    training_document = _read_canonical_json(directory / TRAINING_FILE)
    config, trace = _parse_training(training_document, normalizer)
    if config.receipt()["sha256"] != manifest["config_sha256"]:
        _refuse("config/manifest hash mismatch")
    if trace.receipt_sha256 != manifest["training_trace_sha256"]:
        _refuse("training trace/manifest hash mismatch")
    if trace.model_input_binding != binding:
        _refuse("training trace/manifest model input binding mismatch")
    if config.n_phase_classes != architecture["phase_classes"]:
        _refuse("config/model phase-class mismatch")
    if trace.final_model_sha256 != manifest["model_state_sha256"]:
        _refuse("trace/manifest model-state mismatch")

    expected_state = system.state_dict()
    model_metadata = {
        "schema": ARTIFACT_SCHEMA,
        "architecture_sha256": manifest["architecture_sha256"],
        "model_state_sha256": manifest["model_state_sha256"],
        "model_input_binding_sha256": binding.binding_sha256,
    }
    _validate_safetensor_header(
        directory / MODEL_FILE, expected_state, model_metadata
    )
    state = _load_safetensors(directory / MODEL_FILE)
    for name, tensor in state.items():
        expected = expected_state[name]
        if tensor.shape != expected.shape or tensor.dtype != expected.dtype:
            _refuse(f"decoded state shape/dtype changed: {name}")
    try:
        system.load_state_dict(state, strict=True)
    except RuntimeError as exc:
        raise C.EntryV2Refusal("strict model-state load failed") from exc
    del state
    system.to(device="cpu", dtype=torch.float32)
    system.eval()
    if model_state_sha256(system) != manifest["model_state_sha256"]:
        _refuse("semantic model_state_sha256 mismatch after load")

    actual_probe = _probe_outputs(system, architecture)
    probe_metadata = {
        "schema": "entry-v2-cpu-fp32-probe-v2",
        "architecture_sha256": manifest["architecture_sha256"],
        "model_state_sha256": manifest["model_state_sha256"],
        "model_input_binding_sha256": binding.binding_sha256,
    }
    _validate_safetensor_header(directory / PROBE_FILE, actual_probe, probe_metadata)
    expected_probe = _load_safetensors(directory / PROBE_FILE)
    if set(expected_probe) != set(actual_probe):
        _refuse("CPU inference canary keys changed")
    for name in sorted(actual_probe):
        if not torch.equal(actual_probe[name], expected_probe[name]):
            _refuse(f"CPU FP32 inference is not bit-identical: {name}")

    return FrozenNeuralArtifact(
        system=system,
        normalizer=normalizer,
        config=config,
        trace=trace,
        model_input_binding=binding,
        manifest=manifest,
        path=directory,
    )


# Compact public names for pipeline callers.
save_artifact = save_frozen_artifact
load_artifact = load_frozen_artifact


__all__ = [
    "FrozenNeuralArtifact",
    "load_artifact",
    "load_frozen_artifact",
    "save_artifact",
    "save_frozen_artifact",
]
