"""One-open numerical resources for Entry V2 acceptance and held E1/E2/E3.

The bounded 192-row competence clones authorize the architecture only.  They
are discarded before fresh chronological held training, objective selection,
the five-arm/two-head matrix, and report-only primary E3 evaluation.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import copy
import hashlib
import io
import json
import os
import resource
import shutil
import tempfile
import time
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from typing import Any, Mapping, Sequence

import numpy as np
# Must precede the first CUDA context/cuBLAS handle in this process.
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
import torch
from scipy.special import expit
from sklearn.metrics import average_precision_score, log_loss, roc_auc_score

from . import common as C
from .atlas_materializers import (
    materialize_probe_target, permute_probe_target_recipient_fixed,
    stage_global_recipient_fixed_permutation,
)
from .atlas_losses import action_score_for_probe, loss_for_probe
from .atlas_probe_model import (
    AtlasProbeNet, CausalPretextSession, ProbeRows, SharedProbePlane,
    FrozenLogisticBindingMapper, PositiveSlopePlatt, StagePretextCheckpoint,
    encode_stage_pretext,
    action_fit_weights, asset_day_fit_weights, canonical_phase_pair_manifest,
    fit_probe, fit_stage_pretext,
)
from .causal_label_atlas import (
    PADDED_OUTPUT_WIDTH, PNL_UNITS_PER_USD, PROBE_REGISTRY,
    CellAvailability, ProbeSpec, ProbeTarget,
    probe_target_schema_sha256, registry_bytes, shuffled_probe_for,
)
from .context_sources import CONTEXT_TENSOR_WIDTH, CONTEXT_TYPE_ID
from .diagnostic_catboost import (
    CatBoostCompetenceResult, FrozenRepresentationRows,
    _ranker_params, exact_pair_manifest, fit_diagnostic_catboost,
    rehearse_catboost_competence,
)
from .diagnostic_inputs import (
    DerivedEventFieldBuilder, DerivedEventFields, EventTruthColumns,
    F_BAD_TS_RECV, F_SNAPSHOT, RAW_ROUTE_FIELDS, RAW_TICK, SENTINEL_HIGH,
    assert_teacher_schedule_parity, fit_only_rehearsal_windows,
    native_book_quality,
)
from .event_pack import CATEGORY_SIZES, CATEGORICAL_FIELDS, CONTINUOUS_FIELDS
from .model import FullPrefixEntryModel
from .neural_sufficiency_executor import (
    ArmRehearsalResult, AtlasFitResult, DirectHeadResult,
    LoadedFitOnlyResources, PolicyReplayResult, RawFidelityResult,
    RealDataExactNeuralDiagnosticExecutor, RealDiagnosticExecutorRefusal,
)
from .neural_sufficiency_model import (
    CANONICAL_ARMS, CausalMultiresolutionEncoder, CurrentEncoderAdapter,
    EncoderComplexityReceipt,
    EventFieldSchema,
    FrozenRowManifest, LastRowReconstructionProbe, LiTShortMemoryEncoder,
    SharedCandidateDecisionHead, assert_tensor_tree_identical,
    build_five_arm_registry, module_state_bytes, reconstruction_receipt,
)
from .neural_sufficiency_production import derive_production_context
from .capacity_contract import (
    FIT_ONLY_MIN_ORACLE_CAPTURE, SCHEMA as CAPACITY_SCHEMA,
    capacity_eligibility, capacity_regime_from_oracle,
    fit_only_goal_recovery, required_floor_usd, threshold_feasibility,
    validate_capacity_document,
)
from .selected_horizon_contract import (
    COORDINATES as SELECTED_HORIZON_COORDINATES,
    SCHEMA_SHA256 as SELECTED_HORIZON_SCHEMA_SHA256,
    TARGET_LAW_SHA256 as SELECTED_HORIZON_TARGET_LAW_SHA256,
    WIDTH as SELECTED_HORIZON_WIDTH,
    validate_selected_horizon_identity,
)
from .production_runtime import (
    ColdAssetProcessPool,
    PRODUCTION_DISK_CACHE_MEMORY_RESERVE_BYTES,
    build_production_diagnostic_stage,
    effective_memory_available_bytes,
    extend_production_diagnostic_stage,
)
from .durable_store import DurableEntryV2Store
from .contracts import EntryScore
from .replay import ScoredArrival, candidate_ceiling, replay
from .representation_probe import (
    assert_fast_sweep_parity, canonical_replay_adversary_receipt,
    fast_threshold_sweep,
)
from .atlas_statistics import (
    PairedObservationRecord, hierarchical_holm, nonredundant_finalists,
    paired_day_cluster_records, romano_wolf_lower_bounds,
)
from .session_stream import SessionArrayCache
from .train import (
    HORIZONS_SECONDS, MAE_SCALE_USD, MFE_SCALE_USD,
    TIME_TO_PEAK_SCALE_SECONDS, VALUE_BIN_INDEX, VALUE_SCALE_USD,
    _static_context_summary,
)

DECISIONS = ("direct_neural", "catboost")
FIT_ONLY_MAXIMUM_D8 = 20210930


def _rehearsal_bounds(stage: str, role: str) -> tuple[int, int]:
    windows = fit_only_rehearsal_windows(stage)
    try:
        return windows[str(role).upper()]
    except KeyError as exc:
        raise RealDiagnosticExecutorRefusal(
            "unknown fit-only rehearsal chronology role"
        ) from exc


def _rehearsal_mask(days: np.ndarray, stage: str, role: str) -> np.ndarray:
    lo, hi = _rehearsal_bounds(stage, role)
    values = np.asarray(days)
    return (values >= lo) & (values <= hi)

# The frozen native manifests contain 4,093 pre-H2 asset sessions.  Admission
# reserves additional descriptors/VMAs for cache hits, QRE2 validation, held
# representation maps, atomic publication, libraries, and the interpreter.
# This check runs before the cache or run root is created.
PRODUCTION_SESSION_MAPPING_UPPER_BOUND = 4_096
PRODUCTION_NOFILE_REQUIRED = 4 * PRODUCTION_SESSION_MAPPING_UPPER_BOUND
PRODUCTION_VMA_REQUIRED = 16 * PRODUCTION_SESSION_MAPPING_UPPER_BOUND
PRODUCTION_DISK_FREE_REQUIRED_BYTES = 1 * 1024 ** 4
PRODUCTION_FREE_INODES_REQUIRED = 4 * PRODUCTION_SESSION_MAPPING_UPPER_BOUND


def _limit_satisfies(value: int, required: int) -> bool:
    return value == resource.RLIM_INFINITY or value >= required


def _admit_production_resources(parent: Path) -> Mapping[str, Any]:
    """Refuse every countable host-resource shortage before session one."""
    if not parent.is_absolute() or not parent.is_dir():
        raise RealDiagnosticExecutorRefusal(
            "production resource admission requires an existing absolute parent"
        )
    try:
        soft_before, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    except (OSError, ValueError) as exc:
        raise RealDiagnosticExecutorRefusal(
            "cannot inspect the process file-descriptor limit"
        ) from exc
    if not _limit_satisfies(int(hard), PRODUCTION_NOFILE_REQUIRED):
        raise RealDiagnosticExecutorRefusal(
            "hard file-descriptor limit is below the production mapping budget"
        )
    if not _limit_satisfies(int(soft_before), PRODUCTION_NOFILE_REQUIRED):
        try:
            resource.setrlimit(
                resource.RLIMIT_NOFILE, (PRODUCTION_NOFILE_REQUIRED, hard)
            )
        except (OSError, ValueError) as exc:
            raise RealDiagnosticExecutorRefusal(
                "cannot raise the process file-descriptor limit"
            ) from exc
    try:
        soft_after, hard_after = resource.getrlimit(resource.RLIMIT_NOFILE)
        vm_map_limit = int(Path("/proc/sys/vm/max_map_count").read_text().strip())
        disk = shutil.disk_usage(parent)
        statvfs = os.statvfs(parent)
    except (OSError, ValueError) as exc:
        raise RealDiagnosticExecutorRefusal(
            "cannot verify production mapping/disk admission"
        ) from exc
    if (not _limit_satisfies(int(soft_after), PRODUCTION_NOFILE_REQUIRED)
            or int(hard_after) != int(hard)):
        raise RealDiagnosticExecutorRefusal(
            "process file-descriptor admission did not take effect"
        )
    free_inodes = int(statvfs.f_favail)
    if vm_map_limit < PRODUCTION_VMA_REQUIRED:
        raise RealDiagnosticExecutorRefusal(
            "vm.max_map_count is below the production mapping budget"
        )
    if int(disk.free) < PRODUCTION_DISK_FREE_REQUIRED_BYTES:
        raise RealDiagnosticExecutorRefusal(
            "free disk is below the production immutable-cache budget"
        )
    if free_inodes < PRODUCTION_FREE_INODES_REQUIRED:
        raise RealDiagnosticExecutorRefusal(
            "free inodes are below the production immutable-cache budget"
        )
    body = {
        "schema": "entry-v2-production-resource-admission-v1",
        "session_mapping_upper_bound": PRODUCTION_SESSION_MAPPING_UPPER_BOUND,
        "nofile_required": PRODUCTION_NOFILE_REQUIRED,
        "nofile_soft_before": int(soft_before),
        "nofile_soft_after": int(soft_after),
        "nofile_hard": int(hard_after),
        "vm_map_required": PRODUCTION_VMA_REQUIRED,
        "vm_map_limit": vm_map_limit,
        "disk_free_required_bytes": PRODUCTION_DISK_FREE_REQUIRED_BYTES,
        "disk_free_bytes": int(disk.free),
        "free_inodes_required": PRODUCTION_FREE_INODES_REQUIRED,
        "free_inodes": free_inodes,
    }
    body["receipt_sha256"] = _sha(body)
    return MappingProxyType(body)


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha(value: object) -> str:
    return _sha_bytes(json.dumps(
        C.canonical_json_value(value), sort_keys=True, separators=(",", ":"),
        allow_nan=False).encode())


def _is_sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        char in "0123456789abcdef" for char in value)


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(C.canonical_json_value(value),
                      sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode()


def _npz_bytes(values: Mapping[str, np.ndarray]) -> bytes:
    stream = io.BytesIO()
    np.savez_compressed(stream, **{key: np.asarray(value) for key, value in values.items()})
    return stream.getvalue()


def _safetensors_bytes(module: torch.nn.Module) -> bytes:
    from safetensors.torch import save
    return save({name: value.detach().cpu().contiguous()
                 for name, value in module.state_dict().items()})


def _full_learner_checkpoint_sha256(
    model: torch.nn.Module, objective_head: torch.nn.Module,
) -> str:
    """Canonical identity of the deployable neural + selected-objective pair."""
    return _sha({
        "schema": "entry-v2-fit-only-full-learner-checkpoint-v1",
        "model_sha256": _sha_bytes(module_state_bytes(model)),
        "objective_head_sha256": _sha_bytes(module_state_bytes(objective_head)),
    })


def _output_canary_arrays(output: Any) -> Mapping[str, np.ndarray]:
    """Bounded, lossless inference surface used by M8 strict reload."""
    names = (
        "raw_memory", "static_tokens", "context_token", "decision_state",
        "action_logit", "ordinal_logits", "value_distribution_logits",
        "value_quantiles", "expected_value", "top3_logit", "rank_score",
        "mfe_quantiles", "mae_quantiles", "mfe", "mae",
        "wall_logit", "time_to_peak", "horizon_values", "phase_logits",
    )
    result: dict[str, np.ndarray] = {}
    for name in names:
        value = getattr(output, name)
        if value is None:
            result[name] = np.empty((0,), np.float32)
        else:
            result[name] = np.ascontiguousarray(
                value.detach().float().cpu().numpy())
    return MappingProxyType(result)


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray): return value.tolist()
    if isinstance(value, Mapping): return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)): return [_jsonable(v) for v in value]
    if isinstance(value, np.generic): return value.item()
    return value


def _decision_binding(probability: np.ndarray) -> np.ndarray:
    """Frozen scalar-policy to A-004 binding law shared by every stage."""
    value = np.asarray(probability, np.float64).reshape(-1)
    if not np.all(np.isfinite(value)):
        raise RealDiagnosticExecutorRefusal("decision binding probability is non-finite")
    return np.repeat(value[:, None], 128, axis=1)


def _fit_only_full_learner_law_sha256() -> str:
    """Identity shared by the independently fitted E1r/E2r full learner."""
    return _sha({
        "schema": "entry-v2-fit-only-selected-full-learner-law-v1",
        "architecture": "selected-five-arm-shared-cross-attention-v1",
        "base_stage": {"maximum_epochs": 12, "patience": 3,
                       "loss": "all-oracle-plus-field-survival-plus-phase-pairs"},
        "selected_stage": {"epochs": 6, "encoder_frozen": True,
                           "loss": "all-oracle-plus-selected-objective-plus-phase-pairs"},
        "optimizer": {"name": "Adam", "learning_rate": 3e-4,
                      "step_unit": "complete_asset_day_gradient"},
        "validation": "unweighted-complete-fit-tail-days",
        "static_bypass": "selected-stage-L1-M1-only",
        "selected_horizons": SELECTED_HORIZON_SCHEMA_SHA256,
    })


def _selected_horizon_targets(atlas: Any, candidate_ids: Sequence[str],
                              labels: Sequence[Any]) -> tuple[torch.Tensor, torch.Tensor, str]:
    """Exact raw-USD targets for 5m/10m/15m/20m/30m/canonical terminal."""
    validate_selected_horizon_identity(
        SELECTED_HORIZON_COORDINATES, SELECTED_HORIZON_SCHEMA_SHA256)
    if tuple(label.candidate_id for label in labels) != tuple(candidate_ids):
        raise RealDiagnosticExecutorRefusal("selected horizon teacher rows differ")
    index = {cid: i for i, cid in enumerate(atlas.candidate_ids)}
    rows = np.asarray([index[cid] for cid in candidate_ids], np.int64)
    columns = np.asarray((3, 4, 5, 6, 7, 11), np.int64)
    values = (np.asarray(atlas.atoms["vertical_units"], np.int64)[rows][:, columns]
              .astype(np.float64) / PNL_UNITS_PER_USD)
    valid = np.asarray(atlas.atoms["vertical_mask"], bool)[rows][:, columns]
    values[~valid] = 0.0
    terminal = np.asarray([float(label.cert_close_usd) for label in labels], np.float64)
    if (not np.all(valid[:, -1])
            or not np.allclose(values[:, -1], terminal, rtol=0.0, atol=1e-9)):
        raise RealDiagnosticExecutorRefusal(
            "canonical terminal horizon differs from teacher cert_close")
    if values.shape != (len(candidate_ids), SELECTED_HORIZON_WIDTH):
        raise RealDiagnosticExecutorRefusal("selected horizon carrier width differs")
    receipt = _sha({"schema": "entry-v2-selected-horizon-targets-v1",
                    "schema_sha256": SELECTED_HORIZON_SCHEMA_SHA256,
                    "axes": list(SELECTED_HORIZON_COORDINATES),
                    "units": "RAW_USD_UNNORMALIZED",
                    "candidate_ids": list(candidate_ids),
                    "values_sha256": _sha_bytes(values.tobytes()),
                    "valid_sha256": _sha_bytes(valid.tobytes()),
                    "terminal_teacher_parity": True})
    return (torch.from_numpy(values),
            torch.from_numpy(valid), receipt)


def _selected_horizon_targets_from_spec(
    atlas: Any, spec: Any, local: Sequence[int], labels: Sequence[Any],
) -> tuple[torch.Tensor, torch.Tensor, str]:
    """Use atlas targets only after proving the corpus carrier byte-identical."""
    positions = tuple(map(int, local))
    candidate_ids = tuple(spec.candidate_ids[index] for index in positions)
    values, valid, receipt = _selected_horizon_targets(
        atlas, candidate_ids, labels,
    )
    if (spec.selected_horizon_value is None
            or spec.selected_horizon_valid is None
            or spec.selected_horizon_schema_sha256
                != SELECTED_HORIZON_SCHEMA_SHA256):
        raise RealDiagnosticExecutorRefusal(
            "selected horizon corpus carrier is absent")
    index = torch.tensor(positions, dtype=torch.long)
    carried_values = spec.selected_horizon_value[index].detach().cpu()
    carried_valid = spec.selected_horizon_valid[index].detach().cpu().to(torch.bool)
    if (carried_values.dtype != torch.float64
            or carried_values.shape != values.shape
            or carried_valid.shape != valid.shape
            or not torch.equal(carried_values, values)
            or not torch.equal(carried_valid, valid)):
        raise RealDiagnosticExecutorRefusal(
            "selected horizon atlas/corpus carrier differs")
    return values, valid, receipt


def _fit_selected_horizon_normalizer(
    batches: Sequence["_CandidateBatch"], training_days: set[int], *, stage: str,
) -> tuple[tuple["_CandidateBatch", ...], Mapping[str, Any]]:
    """Fit six independent TRAIN-only moments and apply them once everywhere."""
    count = np.zeros(SELECTED_HORIZON_WIDTH, np.int64)
    total = np.zeros(SELECTED_HORIZON_WIDTH, np.float64)
    square = np.zeros(SELECTED_HORIZON_WIDTH, np.float64)
    train_ids = []
    for batch in batches:
        if batch.day not in training_days:
            continue
        value = batch.horizon_targets.numpy().astype(np.float64)
        valid = batch.horizon_valid.numpy().astype(bool)
        count += valid.sum(0); total += np.where(valid, value, 0.0).sum(0)
        square += np.where(valid, value * value, 0.0).sum(0)
        train_ids.extend(batch.candidate_ids)
    if np.any(count < 2):
        raise RealDiagnosticExecutorRefusal(
            f"{stage} selected horizon normalizer lacks coordinate support")
    location = total / count
    variance = np.maximum(square / count - location * location, 0.0)
    scale = np.sqrt(variance)
    if np.any(~np.isfinite(location)) or np.any(scale <= 0):
        raise RealDiagnosticExecutorRefusal(
            f"{stage} selected horizon normalizer is degenerate")
    normalized = []
    for batch in batches:
        value = batch.horizon_targets.numpy().astype(np.float64)
        valid = batch.horizon_valid.numpy().astype(bool)
        transformed = ((value - location) / scale).astype(np.float32)
        transformed[~valid] = 0.0
        normalized.append(replace(batch, horizon_targets=torch.from_numpy(transformed)))
    winner_core = {"schema": "entry-v2-selected-horizon-normalizer-v1",
        "coordinates": list(SELECTED_HORIZON_COORDINATES),
        "target_schema_sha256": SELECTED_HORIZON_SCHEMA_SHA256,
        "target_law_sha256": SELECTED_HORIZON_TARGET_LAW_SHA256,
        "location": location.tolist(), "scale": scale.tolist()}
    receipt = {**winner_core, "receipt_sha256": _sha(winner_core),
        "fit_manifest_sha256": _sha({"stage": stage,
            "training_days": sorted(training_days),
            "training_candidate_ids": train_ids, "count": count.tolist(),
            "validation_weighting": "UNWEIGHTED"})}
    return tuple(normalized), MappingProxyType(receipt)


def _probe_fingerprint(target: ProbeTarget, fit_rows: np.ndarray,
                       recipient: np.ndarray) -> np.ndarray:
    """Comparable full-coordinate fingerprint for E1 nonredundancy."""
    values = np.asarray(target.values, np.float64)
    mask = (np.asarray(target.coordinate_mask, bool)
            & np.asarray(target.validity_mask, bool)[:, None]
            & np.asarray(recipient, bool)[:, None]
            & np.asarray(fit_rows, bool)[:, None])
    plane = np.zeros_like(values, dtype=np.float64)
    for column in range(values.shape[1]):
        selected = mask[:, column]
        if not selected.any():
            continue
        location = float(values[selected, column].mean())
        scale = float(values[selected, column].std())
        if scale < 1e-12:
            scale = 1.0
        plane[selected, column] = (values[selected, column] - location) / scale
    # Fixed streaming sketch uses every coordinate without retaining the
    # N×width plane for all 44 probes.  The independent mask basis keeps a
    # genuine zero distinct from an unavailable coordinate.
    index = np.arange(1, values.shape[1] + 1, dtype=np.float64)
    value_weight = np.sin(index * 1.618033988749895)
    mask_weight = np.cos(index * 2.414213562373095)
    sketch = plane @ value_weight + mask.astype(np.float64) @ mask_weight
    return np.asarray(sketch, np.float64)


def _e1_fit_support_inputs(
    probe: ProbeSpec, target: ProbeTarget, rows: ProbeRows,
    fit_indices: Sequence[int],
):
    """Build every E1 support plane from physical FIT-only row slices."""
    from .atlas_statistics import SupportKind
    from .neural_sufficiency_stage_engine import ProbeSupportInputs

    n = len(target.validity_mask)
    idx = np.asarray(fit_indices, np.int64)
    if (idx.ndim != 1 or not len(idx) or len(set(idx.tolist())) != len(idx)
            or np.any(idx < 0) or np.any(idx >= n)):
        raise RealDiagnosticExecutorRefusal("E1 support fit indices are invalid")
    if any(np.asarray(value).shape != (n,) for value in (
            rows.asset, rows.day, rows.decision_ts_ns)):
        raise RealDiagnosticExecutorRefusal("E1 support source rows are misaligned")
    assets = np.asarray(rows.asset, str)[idx]
    days = np.asarray(rows.day, np.int64)[idx]
    decisions = np.asarray(rows.decision_ts_ns, np.int64)[idx]
    if np.any(days > 20210930):
        raise RealDiagnosticExecutorRefusal("E1 support physical slice crossed FIT")
    fit_valid = np.asarray(target.validity_mask, bool)[idx]
    values = np.asarray(target.values[idx, 0], np.float64)
    additional_support = ()
    support_kind = probe.support_id.removeprefix("support.")
    if support_kind == "exact_time_ranking":
        support = ProbeSupportInputs(
            SupportKind.EXACT_TIME_RANKING, assets, fit_valid,
            group_id=np.asarray(target.group_id)[idx], day=days,
            decision_ts=decisions)
    elif support_kind == "economic_continuous":
        support = ProbeSupportInputs(
            SupportKind.ECONOMIC, assets, fit_valid, day=days)
        additional_support = (ProbeSupportInputs(
            SupportKind.CONTINUOUS, assets, fit_valid, values=values, day=days),)
    elif support_kind == "competing_cause":
        if probe.cell in (10, 24):
            cause = np.asarray(target.values[idx, :24], np.int64).reshape(-1)
            support = ProbeSupportInputs(
                SupportKind.COMPETING_CAUSE, np.repeat(assets, 24),
                (np.asarray(target.coordinate_mask[idx, :24], bool)
                 & fit_valid[:, None]).reshape(-1), values=cause,
                required_levels=(0, 1, 2, 3), day=np.repeat(days, 24))
        else:
            support = ProbeSupportInputs(
                SupportKind.COMPETING_CAUSE, assets, fit_valid, values=values,
                required_levels=(0, 1), day=days)
    elif support_kind == "binary_ordinal":
        support = ProbeSupportInputs(
            SupportKind.BINARY_ORDINAL, assets, fit_valid, values=values,
            required_levels=(0, 1), day=days)
    elif support_kind == "mixed_continuous_ordinal":
        width = max(2, min(target.output_width, 9))
        ordinal = np.argmax(target.values[idx, 1:width], axis=1)
        support = ProbeSupportInputs(
            SupportKind.CONTINUOUS, assets, fit_valid, values=values, day=days)
        additional_support = (ProbeSupportInputs(
            SupportKind.BINARY_ORDINAL, assets, fit_valid, values=ordinal,
            required_levels=tuple(range(width - 1)), day=days),)
    else:
        support = ProbeSupportInputs(
            SupportKind.CONTINUOUS, assets, fit_valid, values=values, day=days)
    coordinate_support = []
    coordinate_mask = np.asarray(target.coordinate_mask, bool)[idx]
    for coordinate in range(target.output_width):
        valid_coordinate = fit_valid & coordinate_mask[:, coordinate]
        coordinate_values = np.asarray(target.values[idx, coordinate], np.float64)
        layout = target.output_layout[coordinate].lower()
        categorical_coordinate = (support_kind in {
            "binary_ordinal", "mixed_continuous_ordinal", "competing_cause"}
            and any(token in layout for token in (
                "cause", "class", "status", "ordinal", "hit", "wall", "bin")))
        coordinate_support.append(ProbeSupportInputs(
            SupportKind.BINARY_ORDINAL if categorical_coordinate
            else SupportKind.CONTINUOUS,
            assets, valid_coordinate, values=coordinate_values,
            required_levels=((0, 1) if categorical_coordinate else ()), day=days))
    result = (support, tuple((*additional_support, *coordinate_support)))
    for item in (result[0], *result[1]):
        item.validate_fit_slice()
    return result


def _probe_variant(spec: Any) -> int:
    return int(spec.probe_id.split("P", 1)[1].split(".", 1)[0])


def _valid_adoption(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        char in "0123456789abcdef" for char in value)


def _configure_deterministic_torch() -> str:
    if os.environ.get("CUBLAS_WORKSPACE_CONFIG") != ":4096:8":
        raise RealDiagnosticExecutorRefusal("deterministic cuBLAS workspace differs")
    torch.use_deterministic_algorithms(True)
    if torch.cuda.is_available():
        torch.backends.cuda.enable_flash_sdp(False)
        torch.backends.cuda.enable_mem_efficient_sdp(False)
        torch.backends.cuda.enable_math_sdp(True)
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
    return _sha({"cublas_workspace": os.environ["CUBLAS_WORKSPACE_CONFIG"],
                 "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
                 "flash_sdp": bool(torch.backends.cuda.flash_sdp_enabled()),
                 "mem_efficient_sdp": bool(torch.backends.cuda.mem_efficient_sdp_enabled()),
                 "math_sdp": bool(torch.backends.cuda.math_sdp_enabled()),
                 "cudnn_benchmark": bool(torch.backends.cudnn.benchmark),
                 "cudnn_deterministic": bool(torch.backends.cudnn.deterministic)})


def _fit_binding_projection(bindings: Sequence[Any], manifest: FrozenRowManifest) -> str:
    """Pure supervised-input projection; excluded bindings cannot affect it."""
    wanted = set(map(str, manifest.candidate_id))
    selected = sorted((row for row in bindings if row.candidate_id in wanted),
                      key=lambda row: str(row.candidate_id))
    if {row.candidate_id for row in selected} != wanted:
        raise RealDiagnosticExecutorRefusal("fit binding projection is incomplete")
    return _sha([{
        "candidate_id": row.candidate_id,
        "asset": row.asset, "day": int(row.trading_day),
        "cutoff": int(row.event_cutoff), "decision": int(row.decision_ts_ns),
        "action_target": bool(row.action_target),
        "action_loss_mask": bool(row.action_loss_mask),
        "compliance": str(row.compliance), "teacher": str(row.teacher_state),
    } for row in selected])


def _component_fit_projection(bindings: Sequence[Any], manifest: FrozenRowManifest,
                              batches: Sequence[Any], *, include_action: bool) -> str:
    """Pure exact pre-fit materialization used by mutation isolation canaries."""
    wanted = set(map(str, manifest.candidate_id))
    rows = {row.candidate_id: row for row in bindings if row.candidate_id in wanted}
    if set(rows) != wanted:
        raise RealDiagnosticExecutorRefusal("component fit projection is incomplete")
    payload: dict[str, Any] = {"manifest": manifest.receipt_sha256, "batches": [{
        "ids": batch.candidate_ids,
        "continuous": _sha_bytes(batch.continuous.numpy().tobytes()),
        "categorical": _sha_bytes(batch.categorical.numpy().tobytes()),
        "cutoffs": _sha_bytes(batch.cutoffs.numpy().tobytes()),
        "contexts": _sha_bytes(batch.context_values.numpy().tobytes()),
    } for batch in batches]}
    if include_action:
        payload["supervision"] = [(
            cid,
            (bool(rows[cid].action_target)
             if bool(rows[cid].action_loss_mask) else None),
            bool(rows[cid].action_loss_mask),
        ) for cid in sorted(rows)]
    return _sha(payload)


def _fit_only_loaded_roster_firewall(
    stage: Any, bindings: Sequence[Any], *, required_candidate_ids: Sequence[str] = (),
) -> str:
    """Prove forbidden post-fit rows are absent from the loaded resource.

    Acceptance is physically capped at 2021-09-30.  A mutation of a detached
    later row is therefore neither possible nor evidence of isolation.  The
    honest proof is the exact loaded corpus/diagnostic window plus a complete
    immutable binding roster, followed separately by a visible-row canary.
    """
    if stage is None:
        raise RealDiagnosticExecutorRefusal("fit-only firewall lacks a loaded stage")
    diagnostic = stage.diagnostic_corpus
    corpus = stage.corpus_stage.corpus
    diagnostic_receipt = diagnostic.receipt
    corpus_receipt = corpus.receipt
    window = corpus_receipt.get("corpus_window", {})
    if (int(window.get("maximum_d8", -1)) != FIT_ONLY_MAXIMUM_D8
            or int(diagnostic_receipt.get("corpus_maximum_d8", -1))
                != FIT_ONLY_MAXIMUM_D8
            or int(diagnostic_receipt.get("truth_end_d8", -1))
                != FIT_ONLY_MAXIMUM_D8
            or int(diagnostic_receipt.get("derived_end_d8", -1))
                != FIT_ONLY_MAXIMUM_D8):
        raise RealDiagnosticExecutorRefusal(
            "fit-only loaded resource is not capped at the September wall")
    roster = tuple(bindings)
    if not roster or any(int(row.trading_day) > FIT_ONLY_MAXIMUM_D8 for row in roster):
        raise RealDiagnosticExecutorRefusal(
            "fit-only loaded binding roster contains a forbidden later row")
    candidate_ids = [str(row.candidate_id) for row in roster]
    if len(set(candidate_ids)) != len(candidate_ids):
        raise RealDiagnosticExecutorRefusal(
            "fit-only loaded binding roster contains duplicate candidate identities")
    required = set(map(str, required_candidate_ids))
    if required and not required.issubset(set(candidate_ids)):
        raise RealDiagnosticExecutorRefusal(
            "fit-only component candidate roster is absent from loaded bindings")
    session_days = [int(session.key[1]) for session in diagnostic.sessions]
    corpus_days = [int(spec.trading_day) for spec in corpus.sessions]
    if (not session_days or not corpus_days
            or any(day > FIT_ONLY_MAXIMUM_D8 for day in session_days)
            or any(day > FIT_ONLY_MAXIMUM_D8 for day in corpus_days)):
        raise RealDiagnosticExecutorRefusal(
            "fit-only loaded session roster crosses the September wall")
    payload = {
        "schema": "entry-v2-fit-only-loaded-roster-firewall-v1",
        "maximum_d8": FIT_ONLY_MAXIMUM_D8,
        "diagnostic_receipt_sha256": diagnostic_receipt["receipt_sha256"],
        "corpus_receipt_sha256": corpus_receipt["receipt_sha256"],
        "corpus_window_sha256": _sha(dict(window)),
        "required_candidate_ids": sorted(required),
        "bindings": sorted((
            str(row.candidate_id), str(row.asset), int(row.trading_day),
            int(row.decision_ts_ns), int(row.event_cutoff),
            str(row.compliance_status), str(row.teacher_status),
            bool(row.action_target), bool(row.action_loss_mask),
        ) for row in roster),
        "diagnostic_sessions": sorted(
            (str(session.key[0]), int(session.key[1]))
            for session in diagnostic.sessions),
        "corpus_sessions": sorted(
            (str(spec.asset), int(spec.trading_day), str(spec.session_id))
            for spec in corpus.sessions),
    }
    return _sha(payload)


def _bounded_supervised_fit_sha(
    features: np.ndarray, target: np.ndarray, recipient: np.ndarray, *, seed: int,
) -> str:
    """Recompute a deterministic real optimizer artifact for isolation canaries."""
    x = torch.from_numpy(np.ascontiguousarray(features, np.float32))
    y = torch.from_numpy(np.asarray(target, np.float32))
    mask = torch.from_numpy(np.asarray(recipient, bool))
    if x.ndim != 2 or x.shape[0] != y.numel() or int(mask.sum()) < 2:
        raise RealDiagnosticExecutorRefusal("bounded isolation fit is unsupported")
    with torch.random.fork_rng():
        torch.manual_seed(seed)
        head = torch.nn.Linear(x.shape[1], 1)
        optimizer = torch.optim.SGD(head.parameters(), lr=.025)
        for _ in range(8):
            optimizer.zero_grad(set_to_none=True)
            logits = head(x).squeeze(1)
            loss = torch.nn.functional.binary_cross_entropy_with_logits(
                logits[mask], y[mask])
            loss.backward(); optimizer.step()
    return _sha({"checkpoint": _sha_bytes(module_state_bytes(head)),
                 "prediction": _sha_bytes(
                     torch.sigmoid(head(x).squeeze(1)).detach().numpy().tobytes()),
                 "mask": _sha_bytes(mask.numpy().tobytes())})


def _quantile_loss(prediction: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    quantiles = prediction.new_tensor((.1, .5, .9))[None]
    error = target[:, None] - prediction
    return torch.maximum(quantiles * error, (quantiles - 1.0) * error).mean()


def _quantile_loss_rows(prediction: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    quantiles = prediction.new_tensor((.1, .5, .9))[None]
    error = target[:, None] - prediction
    return torch.maximum(quantiles * error, (quantiles - 1.0) * error).mean(1)


def _actual_multitask_loss(output: Any, batch: "_CandidateBatch",
                           oracle_fit_weights: Mapping[str, torch.Tensor] | None = None,
                           ) -> tuple[torch.Tensor, Mapping[str, torch.Tensor]]:
    """Declared oracle/self-supervised losses for every shared-head output."""
    device = output.action_logit.device
    oracle = {name: value.to(device) for name, value in batch.oracle_targets.items()}
    selected = batch.action_loss_mask.to(device=device, dtype=torch.bool)
    weighted = oracle_fit_weights is not None
    def reduce_rows(name: str, values: torch.Tensor,
                    valid: torch.Tensor | None = None) -> torch.Tensor:
        row = values.float()
        if row.ndim != 1 or row.shape != batch.targets.shape:
            raise RealDiagnosticExecutorRefusal(f"{name} oracle row loss is misaligned")
        mask = (torch.ones_like(selected) if valid is None else valid.to(
            device=device, dtype=torch.bool))
        if not bool(mask.any()):
            return row.sum() * 0.0
        if not weighted:
            return row[mask].mean()
        assert oracle_fit_weights is not None
        key = name if name in ("action", "top3", "wall") else "base"
        supplied = oracle_fit_weights[key].to(device=device, dtype=torch.float32)
        if (supplied.shape != batch.targets.shape
                or not bool(torch.isfinite(supplied).all())
                or bool((supplied < 0).any())
                or float(supplied[mask].sum()) <= 0):
            raise RealDiagnosticExecutorRefusal(f"{name} oracle fit weights are misaligned")
        return (row[mask] * supplied[mask]).sum()
    rows_by_component = {
        "action": torch.nn.functional.binary_cross_entropy_with_logits(
            output.action_logit.float(), batch.targets.to(device).float(), reduction="none"),
        "ordinal": torch.nn.functional.binary_cross_entropy_with_logits(
            output.ordinal_logits.float(),
            (oracle["value_bin"].long()[:, None]
             >= torch.arange(1, 5, device=device)[None]).float(),
            reduction="none").mean(1),
        "value_distribution": torch.nn.functional.cross_entropy(
            output.value_distribution_logits.float(), oracle["value_bin"].long(),
            reduction="none"),
        "value_quantiles": _quantile_loss_rows(
            output.value_quantiles.float(), oracle["value"]),
        "expected_value": torch.nn.functional.smooth_l1_loss(
            output.expected_value.float(), oracle["value"], reduction="none"),
        "top3": torch.nn.functional.binary_cross_entropy_with_logits(
            output.top3_logit.float(), oracle["top3"], reduction="none"),
        "rank": torch.nn.functional.smooth_l1_loss(
            output.rank_score.float(), oracle["rank"], reduction="none"),
        "mfe_quantiles": _quantile_loss_rows(output.mfe_quantiles.float(), oracle["mfe"]),
        "mae_quantiles": _quantile_loss_rows(output.mae_quantiles.float(), oracle["mae"]),
        "wall": torch.nn.functional.binary_cross_entropy_with_logits(
            output.wall_logit.float(), oracle["wall"], reduction="none"),
        "time_to_peak": torch.nn.functional.smooth_l1_loss(
            output.time_to_peak.float(), oracle["time"], reduction="none"),
    }
    components = {name: reduce_rows(
        name, values, selected if name == "action" else None)
        for name, values in rows_by_component.items()}
    horizon_mask = batch.horizon_valid.to(device=device, dtype=torch.bool)
    horizon_width = batch.horizon_targets.shape[1]
    if horizon_width != 6 or output.horizon_values.shape != batch.horizon_targets.shape:
        raise RealDiagnosticExecutorRefusal(
            "shared-head horizon target/output schema is not exact six-axis")
    horizon_values = torch.nn.functional.smooth_l1_loss(
        output.horizon_values.float(),
        batch.horizon_targets.to(device).float(), reduction="none")
    horizon_count = horizon_mask.sum(1)
    horizon_rows = (horizon_values * horizon_mask).sum(1) / horizon_count.clamp_min(1)
    components["horizons"] = reduce_rows("horizons", horizon_rows,
                                          horizon_count > 0)
    phase_mask = batch.phase_valid.to(device=device, dtype=torch.bool)
    phase_target = batch.phase_targets.to(device).long().clone()
    phase_target[~phase_mask] = 0
    phase_rows = torch.nn.functional.cross_entropy(
        output.phase_logits.float(), phase_target, reduction="none")
    components["phase"] = reduce_rows("phase", phase_rows, phase_mask)
    weights = {"action": 1.0, "ordinal": 1.0, "value_distribution": 1.0,
               "value_quantiles": .5, "expected_value": 1.0, "top3": .5,
               "rank": .35, "mfe_quantiles": .5, "mae_quantiles": .5,
               "wall": .5, "time_to_peak": .25, "horizons": .25, "phase": .25}
    return sum(weights[name] * value for name, value in components.items()), \
        MappingProxyType(components)


def _field_reconstruction_loss(
    decoder: LastRowReconstructionProbe,
    memory: torch.Tensor,
    batch: "_CandidateBatch",
    fit_weight: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Candidate-row reconstruction with the same asset-day weight law.

    Training callers supply the globally fitted per-row base weights, whose
    complete asset-day sum is one. Validation deliberately omits weights and
    receives a plain row mean.
    """
    reconstructed_continuous, reconstructed_categorical = decoder(memory)
    device = memory.device
    continuous_rows = torch.nn.functional.mse_loss(
        reconstructed_continuous.float(),
        batch.last_continuous.to(device).float(), reduction="none",
    ).mean(1)
    categorical_rows = sum(
        torch.nn.functional.cross_entropy(
            logits.float(),
            batch.last_categorical[:, index].to(device).long(),
            reduction="none",
        )
        for index, logits in enumerate(reconstructed_categorical)
    )
    if fit_weight is None:
        continuous = continuous_rows.mean()
        categorical = categorical_rows.mean()
    else:
        weight = fit_weight.to(device=device, dtype=torch.float32)
        if (weight.shape != continuous_rows.shape
                or not bool(torch.isfinite(weight).all())
                or bool((weight < 0).any())):
            raise RealDiagnosticExecutorRefusal(
                "field-reconstruction fit weights are invalid")
        continuous = (continuous_rows * weight).sum()
        categorical = (categorical_rows * weight).sum()
    return continuous + categorical, continuous, categorical


@dataclass
class _CandidateBatch:
    asset: str
    day: int
    session_id: str
    candidate_ids: tuple[str, ...]
    continuous: torch.Tensor
    categorical: torch.Tensor
    clock: torch.Tensor
    cutoffs: torch.Tensor
    decisions: torch.Tensor
    candidate_features: torch.Tensor
    context_values: torch.Tensor
    context_type_ids: torch.Tensor
    context_valid: torch.Tensor
    static_features: torch.Tensor
    targets: torch.Tensor
    action_loss_mask: torch.Tensor
    oracle_targets: Mapping[str, torch.Tensor]
    horizon_targets: torch.Tensor
    horizon_valid: torch.Tensor
    phase_targets: torch.Tensor
    phase_valid: torch.Tensor
    last_continuous: torch.Tensor
    last_categorical: torch.Tensor


@dataclass(frozen=True)
class _HeldContinuousEntry:
    path: Path
    shape: tuple[int, int]
    size_bytes: int
    device: int
    inode: int
    mtime_ns: int
    ctime_ns: int
    normalizer_sha256: str
    schema_sha256: str


@dataclass(frozen=True)
class _HeldMemoryEntry:
    path: Path
    shape: tuple[int, int, int]
    size_bytes: int
    device: int
    inode: int
    mtime_ns: int
    ctime_ns: int
    encoder_sha256: str
    complexity: EncoderComplexityReceipt


@dataclass(frozen=True)
class CompactAtlasHandoff:
    objective_sha256: str
    row_manifest_sha256: str
    candidate_ids: np.ndarray
    target: ProbeTarget
    atlas_aggregate_sha256: str
    materializer_callable_sha256: str
    fit_context_sha256: str
    transform_provenance_sha256: str
    ipcw_provenance_sha256: str
    registry_objective_sha256: str
    fit_day_manifest_sha256: str
    target_candidate_manifest_sha256: str
    target_control_sha256: str
    already_shuffled: bool
    shuffle_receipt: Mapping[str, Any] | None


@dataclass(frozen=True)
class ExpandedEventView:
    continuous: torch.Tensor
    categorical: torch.Tensor
    schema_sha256: str
    transform_law_sha256: str
    base_binding_sha256: str
    normalization: str = "UNNORMALIZED_CANONICAL"


class ExpandedEventTransform:
    """Canonical cached-16+5 to selected encoder plane; never opens QRE2."""
    VERSION = "entry-v2-expanded-cached-event-transform-v1"

    def __init__(self) -> None:
        self.schema_sha256 = "0" * 64
        self.transform_law_sha256 = self.conversion_law_sha256
        self.base_binding_sha256 = "0" * 64
        self.input_contract_sha256 = "0" * 64
        self.category_sizes = tuple(CATEGORY_SIZES)
        self.normalization = "UNNORMALIZED_CANONICAL"
        self._frozen = False
        self._bindings: Mapping[tuple[str, int, str], tuple[Any, ...]] = {}
        # At most one expanded session may be retained, and only when doing so
        # leaves the frozen 320 GiB host reserve.  The all-H1 expanded plane is
        # ~1.5 TiB and is never globally cached.
        self._cache: dict[tuple[str, int, str], ExpandedEventView] = {}
        self._cache_bytes = 0
        self._cache_high_water_bytes = 0

    @property
    def conversion_law_sha256(self) -> str:
        return _sha({"version": self.VERSION, "continuous": CONTINUOUS_FIELDS,
                     "categorical": CATEGORICAL_FIELDS,
                     "derived_equations": dict(DerivedEventFieldBuilder.EQUATIONS)})

    def _array_transform(self, continuous: np.ndarray, categorical: np.ndarray,
                  receive_clock_ns: np.ndarray, *, trusted_message: np.ndarray,
                  trusted_economic: np.ndarray, generation: np.ndarray,
                  phase_open_ts_ns: np.ndarray, phase_close_ts_ns: np.ndarray
                  ) -> tuple[tuple[str, ...], np.ndarray]:
        x = np.asarray(continuous, np.float64); k = np.asarray(categorical)
        clock = np.asarray(receive_clock_ns, np.uint64); n = len(x)
        if (x.shape != (n, len(CONTINUOUS_FIELDS))
                or k.shape != (n, len(CATEGORICAL_FIELDS))
                or any(np.asarray(value).shape != (n,) for value in (
                    trusted_message, trusted_economic, generation,
                    phase_open_ts_ns, phase_close_ts_ns))):
            raise RealDiagnosticExecutorRefusal("expanded cached transform inputs misalign")
        latency = x[:, 3].astype(np.int64) * 1_000 + x[:, 4].astype(np.int64)
        event = clock.astype(np.int64) - latency
        missing = k[:, 4].astype(np.uint8)
        price_names = {"price": 5, "size": 6, "sequence": 7, "bid_px": 8,
                       "ask_px": 9, "bid_sz": 10, "ask_sz": 11,
                       "bid_ct": 12, "ask_ct": 13, "ts_in_delta": 14,
                       "receive_session_sec": 15}
        columns: dict[str, np.ndarray] = {
            "ts_recv_ns": clock, "ts_event_ns": event,
            **{name: x[:, column].astype(np.int64) for name, column in price_names.items()},
            "action": k[:, 0].astype(np.uint8), "side": k[:, 1].astype(np.uint8),
            "flags": k[:, 2].astype(np.uint8), "depth": k[:, 3].astype(np.uint8),
            "missing_mask": missing,
            "trusted_message": np.asarray(trusted_message, bool),
            "trusted_economic": np.asarray(trusted_economic, bool),
            "generation": np.asarray(generation, np.uint32),
            "phase_open_ts_ns": np.asarray(phase_open_ts_ns, np.int64),
            "phase_close_ts_ns": np.asarray(phase_close_ts_ns, np.int64),
        }
        bid, ask = columns["bid_px"], columns["ask_px"]
        ordered = (((missing & 6) == 0) & (bid > 0) & (ask > 0)
                   & (ask > bid) & (bid < SENTINEL_HIGH) & (ask < SENTINEL_HIGH))
        columns["mid2"] = np.zeros(n, np.int64)
        columns["spread"] = np.zeros(n, np.int64)
        columns["mid2"][ordered] = bid[ordered] + ask[ordered]
        columns["spread"][ordered] = ask[ordered] - bid[ordered]
        truth = EventTruthColumns(MappingProxyType(columns))
        return _expanded_columns(DerivedEventFieldBuilder().build(truth), n)

    def transform_with_bindings(self, continuous: np.ndarray, categorical: np.ndarray,
                                receive_clock_ns: np.ndarray, bindings: Sequence[Any],
                                *, asset: str | None = None
                                ) -> tuple[tuple[str, ...], np.ndarray]:
        """Deployment form: reconstruct compact phase/trust metadata."""
        x = np.asarray(continuous); k = np.asarray(categorical)
        clock = np.asarray(receive_clock_ns, np.uint64); n = len(clock)
        phase_open = np.zeros(n, np.int64); phase_close = np.zeros(n, np.int64)
        sane_ceiling = np.zeros(n, np.int64); multiplier = np.zeros(n, np.int64)
        phases = sorted({(int(row.phase_open_ts_ns), int(row.phase_close_ts_ns),
                          int(row.sane_ceiling_units), int(row.multiplier))
                         for row in bindings})
        assets = {str(row.asset) for row in bindings if hasattr(row, "asset")}
        if asset is None:
            if len(assets) != 1:
                raise RealDiagnosticExecutorRefusal("expanded transform requires exact asset")
            asset = next(iter(assets))
        if asset not in RAW_TICK or (assets and assets != {asset}):
            raise RealDiagnosticExecutorRefusal("expanded transform asset/bindings mismatch")
        for opened, closed, ceiling, mult in phases:
            selected = (clock >= opened) & (clock <= closed) & (phase_close == 0)
            # Canonical teacher/atlas law: the prior sorted phase owns its
            # inclusive close when phases share an exact boundary.
            phase_open[selected] = opened; phase_close[selected] = closed
            sane_ceiling[selected] = ceiling; multiplier[selected] = mult
        missing = k[:, 4].astype(np.uint8)
        bid = x[:, 8].astype(np.int64); ask = x[:, 9].astype(np.int64)
        defined = (missing & 6) == 0
        ordered = (defined & (bid > 0) & (ask > 0) & (ask > bid)
                   & (bid < SENTINEL_HIGH) & (ask < SENTINEL_HIGH))
        spread = np.zeros(n, np.int64)
        spread[ordered] = ask[ordered] - bid[ordered]
        sane = ordered & (spread % RAW_TICK[asset] == 0) & (phase_close > 0)
        # Match the authoritative truth plane's overflow-free positive
        # division.  Multiplying a sentinel-adjacent spread can wrap int64.
        denominator = multiplier * 2
        maximum_raw_spread = np.zeros(n, np.int64)
        np.floor_divide(
            sane_ceiling, denominator, out=maximum_raw_spread,
            where=denominator > 0,
        )
        sane &= (denominator > 0) & (spread <= maximum_raw_spread)
        quality = native_book_quality(clock, k[:, 2], sane)
        return self.transform(
            x, k, clock, trusted_message=quality.trusted_message,
            trusted_economic=quality.trusted_economic,
            generation=quality.generation, phase_open_ts_ns=phase_open,
            phase_close_ts_ns=phase_close,
        )

    def freeze(self, *, schema_sha256: str, model_input_binding: Any,
               bindings: Mapping[tuple[str, int, str], tuple[Any, ...]]) -> None:
        if self._frozen:
            raise RealDiagnosticExecutorRefusal("expanded transform already frozen")
        model_input_binding.validate()
        base_binding_sha256 = model_input_binding.binding_sha256
        input_contract_sha256 = model_input_binding.input_contract_sha256
        for digest in (schema_sha256, base_binding_sha256,
                       input_contract_sha256):
            if len(digest) != 64:
                raise RealDiagnosticExecutorRefusal("expanded transform digest invalid")
        self.schema_sha256 = schema_sha256
        self.base_binding_sha256 = base_binding_sha256
        self.input_contract_sha256 = input_contract_sha256
        self._bindings = MappingProxyType(dict(bindings))
        self._frozen = True

    def rebind(self, *, model_input_binding: Any,
               bindings: Mapping[tuple[str, int, str], tuple[Any, ...]]) -> None:
        """Advance exact corpus lineage without changing transform/model law.

        Incremental windows legitimately change ``ModelInputBinding`` lineage.
        The architecture binds the invariant input contract; this live view and
        every fold receipt bind the exact current corpus.  Existing session
        metadata must be an unchanged prefix and the cache is invalidated.
        """
        if not self._frozen:
            raise RealDiagnosticExecutorRefusal("expanded transform is not frozen")
        model_input_binding.validate()
        if model_input_binding.input_contract_sha256 != self.input_contract_sha256:
            raise RealDiagnosticExecutorRefusal(
                "expanded transform input contract changed across corpus windows")
        updated = dict(bindings)
        if (not set(self._bindings).issubset(updated)
                or any(updated[key] != value
                       for key, value in self._bindings.items())):
            raise RealDiagnosticExecutorRefusal(
                "expanded transform prior session metadata changed at extension")
        self.base_binding_sha256 = model_input_binding.binding_sha256
        self._bindings = MappingProxyType(updated)
        self._cache.clear()
        self._cache_bytes = 0

    def transform_batch(self, batch: Any) -> ExpandedEventView:
        if not self._frozen or not getattr(batch, "examples", None):
            raise RealDiagnosticExecutorRefusal("expanded transform is unfrozen or batch empty")
        first = batch.examples[0]
        key = (first.asset, int(first.trading_day), str(first.session_id))
        if key in self._cache:
            return self._cache[key]
        bindings = self._bindings.get(key)
        if not bindings:
            raise RealDiagnosticExecutorRefusal("expanded transform lacks session metadata")
        continuous = batch.event_continuous.detach().cpu().numpy()
        categorical = batch.event_categorical.detach().cpu().numpy()
        clock = batch.receive_clock_ns.detach().cpu().numpy()
        _names, expanded = self.transform_with_bindings(
            continuous, categorical, clock, bindings, asset=first.asset)
        result = ExpandedEventView(
            torch.from_numpy(np.ascontiguousarray(expanded, dtype=np.float64)),
            torch.from_numpy(np.ascontiguousarray(categorical)),
            self.schema_sha256, self.transform_law_sha256,
            self.base_binding_sha256,
        )
        result_bytes = (result.continuous.numel() * result.continuous.element_size()
                        + result.categorical.numel() * result.categorical.element_size())
        self._cache.clear(); self._cache_bytes = 0
        available_after_gib = _available_host_gib() - result_bytes / 1024 ** 3
        if available_after_gib >= 320.0:
            self._cache[key] = result; self._cache_bytes = int(result_bytes)
            self._cache_high_water_bytes = max(self._cache_high_water_bytes,
                                               self._cache_bytes)
        return result

    def release_transient_cache(self) -> Mapping[str, int]:
        before = self._cache_bytes
        self._cache.clear(); self._cache_bytes = 0
        return MappingProxyType({"released_bytes": int(before),
                                 "high_water_bytes": int(self._cache_high_water_bytes),
                                 "retained_entries": len(self._cache)})

    # Winner runtime's fixed callable name.
    def transform(self, *args, **kwargs):
        if len(args) == 1 and not kwargs and hasattr(args[0], "event_continuous"):
            return self.transform_batch(args[0])
        return self._transform_arrays(*args, **kwargs)

    def _transform_arrays(self, continuous: np.ndarray, categorical: np.ndarray,
                          receive_clock_ns: np.ndarray, *, trusted_message: np.ndarray,
                          trusted_economic: np.ndarray, generation: np.ndarray,
                          phase_open_ts_ns: np.ndarray, phase_close_ts_ns: np.ndarray):
        return self._array_transform(continuous, categorical, receive_clock_ns,
            trusted_message=trusted_message, trusted_economic=trusted_economic,
            generation=generation, phase_open_ts_ns=phase_open_ts_ns,
            phase_close_ts_ns=phase_close_ts_ns)


def build_compact_atlas_handoff(
    diagnostic, objective_probe_id: str,
    fit_context_by_session: Mapping[tuple[str, int], Mapping[str, Any]],
    *, selected_objective_sha256: str | None = None,
    fit_days: Sequence[int] = (), control_name: str = "REAL",
    shuffle_receipt: Mapping[str, Any] | None = None,
) -> CompactAtlasHandoff:
    """Materialize one all-pre-H2 objective without reopening raw packs."""
    try:
        spec = next(row for row in PROBE_REGISTRY if row.probe_id == objective_probe_id)
    except StopIteration as exc:
        raise RealDiagnosticExecutorRefusal("selected objective is not registered") from exc
    pieces = []; ids = []
    atlas_hashes = []
    context_hashes = []
    for session in sorted(diagnostic.sessions, key=lambda row: row.key):
        context = fit_context_by_session.get(session.key)
        if context is None:
            raise RealDiagnosticExecutorRefusal("selected objective lacks session fit context")
        target = materialize_probe_target(session.atlas, spec, fit_context=context)
        pieces.append(target); ids.extend(session.atlas.candidate_ids)
        atlas_hashes.append(session.atlas.receipt["receipt_sha256"])
        context_hashes.append(_sha(context))
    combined = _concat_targets(pieces)
    ids_array = np.asarray(ids, dtype=str)
    order = np.argsort(ids_array, kind="stable")
    ids_array = np.ascontiguousarray(ids_array[order]); ids_array.setflags(write=False)
    combined = _target_take(combined, order)
    if len(set(ids_array.tolist())) != len(ids_array):
        raise RealDiagnosticExecutorRefusal("compact handoff candidate IDs duplicate")
    registry = json.loads(registry_bytes())
    materializer_hash = registry["callable_semantics_sha256"][spec.materializer_id]
    fit_context_hash = _sha(context_hashes)
    registry_objective_hash = _sha({
        "spec": spec.canonical(), "registry": _sha_bytes(registry_bytes())})
    objective_hash = selected_objective_sha256 or registry_objective_hash
    if not _valid_adoption(objective_hash):
        raise RealDiagnosticExecutorRefusal("selected objective payload identity is invalid")
    row_manifest_hash = _sha({
        "candidate_ids": ids_array.tolist(),
        "registry_objective_sha256": registry_objective_hash,
        "materializer_callable_sha256": materializer_hash,
        "fit_context_sha256": fit_context_hash,
        "target_schema_sha256": combined.schema_sha256,
    })
    transform = combined.transform_provenance_sha256 or "0" * 64
    ipcw = transform if spec.cell in (10, 24) else "0" * 64
    fit_day_hash = C.object_sha256(sorted(int(day) for day in fit_days))
    candidate_manifest = _sha({"candidate_ids": ids_array.tolist(),
                               "schema": combined.schema_sha256})
    control_hash = _sha({"schema": "entry-v2-selected-target-control-v1",
                         "row_manifest_sha256": row_manifest_hash,
                         "control": str(control_name), "shuffle": shuffle_receipt})
    return CompactAtlasHandoff(
        objective_hash, row_manifest_hash, ids_array, combined,
        _sha(atlas_hashes), materializer_hash, fit_context_hash,
        transform, ipcw, registry_objective_hash, fit_day_hash,
        candidate_manifest, control_hash, shuffle_receipt is not None,
        None if shuffle_receipt is None else MappingProxyType(dict(shuffle_receipt)),
    )


def _available_host_gib() -> float:
    try:
        fields = {line.split(":", 1)[0]: line.split()[1]
                  for line in Path("/proc/meminfo").read_text().splitlines()
                  if ":" in line}
        value = float(fields["MemAvailable"]) / (1024.0 ** 2)
    except (OSError, KeyError, ValueError, IndexError) as exc:
        raise RealDiagnosticExecutorRefusal("cannot measure available host memory") from exc
    if not np.isfinite(value) or value <= 0:
        raise RealDiagnosticExecutorRefusal("available host memory measurement is invalid")
    return value


def _expanded_columns(fields: DerivedEventFields, stop: int) -> tuple[tuple[str, ...], np.ndarray]:
    categorical = set(CATEGORICAL_FIELDS[:-1]) | {"missing_mask"}
    columns: list[np.ndarray] = []; names: list[str] = []
    # Mapping insertion order is not a semantic schema.  The durable store
    # canonicalizes mapping keys, so warm reopening may expose these routes
    # alphabetically.  Restore the declared route order unconditionally.
    if set(fields.raw_routes) != set(RAW_ROUTE_FIELDS):
        raise RealDiagnosticExecutorRefusal(
            "expanded raw-route roster differs from the canonical schema")
    for name in RAW_ROUTE_FIELDS:
        value = fields.raw_routes[name]
        if name in categorical:
            continue
        exact = np.asarray(value[:stop])
        if name in ("ts_recv_ns", "ts_event_ns"):
            seconds, subsecond = np.divmod(exact.astype(np.uint64), 1_000_000_000)
            microseconds, nanoseconds = np.divmod(subsecond, 1_000)
            for suffix, part in (("sec", seconds), ("microsecond", microseconds),
                                 ("nanosecond", nanoseconds)):
                columns.append(part.astype(np.float64)); names.append(f"raw.{name}.{suffix}")
            continue
        canonical = exact.copy()
        if name in ("price", "bid_px", "ask_px"):
            bit = {"price": 1, "bid_px": 2, "ask_px": 4}[name]
            missing = (np.asarray(fields.raw_routes["missing_mask"][:stop], np.uint8) & bit) != 0
            canonical = canonical.astype(np.int64, copy=True); canonical[missing] = 0
        if canonical.dtype.kind not in "iu" or (canonical.size and
                np.max(np.abs(canonical.astype(np.float64))) > 2 ** 53):
            raise RealDiagnosticExecutorRefusal(f"raw route {name} is not exact in float64")
        array = canonical.astype(np.float64)
        if not np.all(array.astype(canonical.dtype) == canonical):
            raise RealDiagnosticExecutorRefusal(f"raw route {name} lost integer precision")
        columns.append(array); names.append(f"raw.{name}")
    for name in sorted(fields.derived_routes):
        raw = np.asarray(fields.derived_routes[name][:stop])
        valid = np.asarray(fields.valid_masks[name][:stop], bool)
        if name == "block_end_receive_ns":
            # The cached learner tensor ends at max(candidate cutoff), not the
            # physical session boundary.  Treating that arbitrary last row as
            # a block end leaks the future candidate roster and differs from
            # slicing the one-open truth.  Shared routes contain only invariant
            # 256-row ends; M1 already handles each candidate's partial block.
            raw = np.zeros(stop, np.int64)
            valid = np.zeros(stop, bool)
            ends = np.arange(255, stop, 256, dtype=np.int64)
            if len(ends):
                raw[ends] = np.asarray(
                    fields.raw_routes["ts_recv_ns"][:stop], np.int64)[ends]
                valid[ends] = True
        if raw.dtype.kind in "iu":
            signed = raw.astype(np.int64, copy=False)
            quotient, remainder = np.divmod(signed, 1_000_000_000)
            for suffix, part in (("quotient_1e9", quotient),
                                 ("remainder_1e9", remainder)):
                array = part.astype(np.float64)
                if not np.all(array.astype(np.int64) == part):
                    raise RealDiagnosticExecutorRefusal(
                        f"derived route {name} exact decomposition failed")
                array[~valid] = 0.0
                coordinate_name = f"derived.{name}.{suffix}"
                columns.append(array); names.append(coordinate_name)
                columns.append(valid.astype(np.float64))
                names.append(f"{coordinate_name}.valid")
        else:
            array = raw.astype(np.float64, copy=True)
            if not np.all(np.isfinite(array[valid])):
                raise RealDiagnosticExecutorRefusal(f"derived route {name} is nonfinite")
            array[~valid] = 0.0
            columns.append(array); names.append(f"derived.{name}")
            columns.append(valid.astype(np.float64)); names.append(f"derived.{name}.valid")
    if not columns:
        raise RealDiagnosticExecutorRefusal("expanded event route is empty")
    return tuple(names), np.stack(columns, axis=1)


def _target_take(target: ProbeTarget, indices: np.ndarray) -> ProbeTarget:
    values = np.ascontiguousarray(target.values[indices])
    cm = np.ascontiguousarray(target.coordinate_mask[indices])
    cr = np.ascontiguousarray(target.coordinate_at_risk[indices])
    cc = np.ascontiguousarray(target.coordinate_censor[indices])
    valid = np.ascontiguousarray(target.validity_mask[indices])
    risk = np.ascontiguousarray(target.at_risk_mask[indices])
    censor = np.ascontiguousarray(target.censor_mask[indices])
    weight = np.ascontiguousarray(target.fit_weight[indices])
    group = np.ascontiguousarray(target.group_id[indices])
    size = np.ascontiguousarray(target.group_size[indices])
    return ProbeTarget(target.probe_id, target.state, values, cm, cr, cc, valid,
                       risk, censor, weight, group, size, target.output_width,
                       target.output_layout, target.direction, target.schema_sha256,
                       target.transform_provenance_sha256,
                       target.prediction_width, target.prediction_layout)


def _concat_targets(parts: Sequence[ProbeTarget]) -> ProbeTarget:
    if not parts:
        raise RealDiagnosticExecutorRefusal("probe target has no selected rows")
    first = parts[0]
    identity = (first.probe_id, first.output_width, first.output_layout,
                first.direction, first.prediction_width, first.prediction_layout,
                first.transform_provenance_sha256)
    if any((p.probe_id, p.output_width, p.output_layout, p.direction,
            p.prediction_width, p.prediction_layout,
            p.transform_provenance_sha256) != identity for p in parts):
        raise RealDiagnosticExecutorRefusal("probe target schemas differ across sessions")
    groups = []; offset = 0
    for part in parts:
        group = np.asarray(part.group_id).copy(); live = group >= 0
        if live.any():
            group[live] += offset; offset = int(group[live].max()) + 1
        groups.append(group)
    state = (CellAvailability.MATERIALIZED
             if any(p.state == CellAvailability.MATERIALIZED for p in parts)
             else parts[0].state)
    cat = lambda name: np.ascontiguousarray(np.concatenate(
        [np.asarray(getattr(p, name)) for p in parts], axis=0))
    return ProbeTarget(
        first.probe_id, state, cat("values"), cat("coordinate_mask"),
        cat("coordinate_at_risk"), cat("coordinate_censor"),
        cat("validity_mask"), cat("at_risk_mask"), cat("censor_mask"),
        cat("fit_weight"), np.ascontiguousarray(np.concatenate(groups)),
        cat("group_size"), first.output_width, first.output_layout,
        first.direction, first.schema_sha256, first.transform_provenance_sha256,
        first.prediction_width, first.prediction_layout,
    )


def _competing_ipcw_observations(target: ProbeTarget) -> tuple[np.ndarray, np.ndarray]:
    """Return the frozen C10/C24 pair-level censoring observations.

    The 72-wide target layout is cause[0:24], pair log-passage[24:48],
    vertical log-time[48:60], and typed vertical status[60:72].  IPCW is
    fitted only on the declared pair passage clocks and their coordinate-level
    censor indicators; vertical clocks are a separate target family.
    """
    if target.output_width != 72 or target.values.shape[1] < 72:
        raise RealDiagnosticExecutorRefusal("competing-risk target is not width 72")
    pair_valid = (np.asarray(target.coordinate_mask[:, :24], bool)
                  & np.asarray(target.coordinate_mask[:, 24:48], bool))
    seconds = np.expm1(np.asarray(target.values[:, 24:48], np.float64))
    censored = np.asarray(target.coordinate_censor[:, 24:48], bool)
    sane = pair_valid & np.isfinite(seconds) & (seconds >= 0)
    return seconds[sane], censored[sane]


def _competing_candidate_ipcw(
    target: ProbeTarget, table_t: np.ndarray, table_s: np.ndarray,
) -> np.ndarray:
    """Evaluate pair-level censor survival and reduce to one row weight."""
    pair_valid = (np.asarray(target.coordinate_mask[:, :24], bool)
                  & np.asarray(target.coordinate_mask[:, 24:48], bool))
    seconds = np.expm1(np.asarray(target.values[:, 24:48], np.float64))
    positions = np.searchsorted(table_t, seconds, side="right") - 1
    survival = np.ones_like(seconds, dtype=np.float64)
    present = positions >= 0
    survival[present] = table_s[np.maximum(positions[present], 0)]
    inverse = np.divide(1.0, survival, out=np.ones_like(survival),
                        where=survival > 0)
    count = pair_valid.sum(1)
    weight = np.divide((inverse * pair_valid).sum(1), count,
                       out=np.ones(len(target.values), np.float64), where=count > 0)
    if np.any(~np.isfinite(weight)) or np.any(weight <= 0):
        raise RealDiagnosticExecutorRefusal("competing-risk IPCW is not finite positive")
    return np.asarray(weight, np.float32)


class ProductionExactDiagnosticResources:
    def __init__(self, run_root: Path, *, device: str | None = None) -> None:
        self.run_root = Path(run_root).resolve()
        self.resource_admission = _admit_production_resources(
            self.run_root.parent
        )
        # Device discovery/configuration is deliberately deferred until the
        # process-isolated CPU corpus producers have completed.  In particular,
        # torch.cuda.is_available() must not precede those spawn boundaries.
        self._requested_device = device
        self.device: torch.device | None = None
        self.determinism_receipt_sha256: str | None = None
        effective_available = effective_memory_available_bytes()
        if effective_available < PRODUCTION_DISK_CACHE_MEMORY_RESERVE_BYTES:
            raise RealDiagnosticExecutorRefusal(
                "effective cgroup/host memory is below the disk-cache resident reserve"
            )
        # This store is attempt-independent within the run parent: a failed
        # process may be restarted without reopening already verified QRE2
        # payloads.  The per-attempt run root never owns or deletes it.
        self.durable_store = DurableEntryV2Store(
            self.run_root.parent / ".entry-v2-durable-store"
        )
        self.cache = SessionArrayCache(
            192 * 1024 ** 3, durable_store=self.durable_store
        )
        self.cold_process_pool = ColdAssetProcessPool()
        self.effective_memory_available_bytes = effective_available
        self.stage = None
        self.loaded = None
        self.batches: tuple[_CandidateBatch, ...] = ()
        # The ranker-depth population is deliberately disjoint from the
        # bounded 192-row arm competence slice.  It contains the frozen
        # 44 phase groups per asset required by A-013 M2.
        self._pairlogit_depth_batches: tuple[_CandidateBatch, ...] = ()
        self._pairlogit_depth_manifest_sha256: str | None = None
        self._fit_only_preflight: Mapping[str, Any] | None = None
        # The M8 boundary is an actual numerical restart bundle.  Bytes are
        # captured at the creation site of every fitted object; the exporter
        # must never manufacture model roles from summary receipts.
        self._m8_payloads: dict[str, bytes] = {}
        self._m8_objective_payloads: dict[str, list[str]] = {}
        self._m8_path_payloads: dict[str, list[str]] = {}
        self._m8_pretext_payloads: list[str] = []
        self._m8_selected_transition_payloads: list[str] = []
        self._m8_arm_payloads: dict[str, dict[str, list[str]]] = {
            arm: {role: [] for role in ("initial", "pointwise", "best", "final")}
            for arm in CANONICAL_ARMS
        }
        self._m8_reload_proof_sha256: str | None = None
        self._fit_only_e1_targets: Mapping[str, ProbeTarget] | None = None
        self.schema: EventFieldSchema | None = None
        self.location: np.ndarray | None = None
        self.scale: np.ndarray | None = None
        self.event_constant: np.ndarray | None = None
        self.normalizer_train_manifest_sha256: str | None = None
        self.normalizer_validation_manifest_sha256: str | None = None
        self.static_normalizer_sha256: str | None = None
        self.static_location: np.ndarray | None = None
        self.static_scale: np.ndarray | None = None
        self.static_constant: np.ndarray | None = None
        self.arm_rows: dict[str, FrozenRepresentationRows] = {}
        self._acceptance_component_evidence: dict[str, bytes] = {}
        self._arms = None
        self._atlas_targets: dict[str, ProbeTarget] = {}
        self._atlas_fit_context_by_probe_session: dict[
            str, dict[tuple[str, int], Mapping[str, Any] | None]] = {}
        self._load_claimed = False
        self.expanded_transform = ExpandedEventTransform()
        self._selected_objective_probe_id: str | None = None
        self._selected_objective_sha256: str | None = None
        self.ownership_transferred = False
        self._resource_closed = False
        self._winner_mapper = None
        self._direct_probability_by_id: dict[str, float] = {}
        self.policy_kind: str | None = None
        self._selected_policy_factory = None
        self._held_engine = None
        self._held_screens = None
        self._held_confirmations = None
        self._held_artifacts = None
        self.mapper_sha256: str | None = None
        self.calibrator_sha256: str | None = None
        self.thresholds_sha256: str | None = None
        self.capacity_authority_sha256: str | None = None
        self._winner_adoption_sha256: str | None = None
        self._loaded_window_id: str | None = None
        self._loaded_maximum_d8 = 20210930
        self._expanded_session_metadata_sha256: str | None = None
        self._held_arm_rows: dict[str, FrozenRepresentationRows] = {}
        self._held_path_receipts: dict[str, str] = {}
        self._held_models = None
        self._held_objective_heads = None
        self._held_normalizer = None
        self._binding_by_id = None
        self._binding_by_session = None
        self._observed_by_session = None
        self._held_continuous_dir = (
            self.run_root.parent / f".{self.run_root.name}.held-continuous-cache"
        )
        self._held_continuous_entries: dict[
            tuple[str, int, str], _HeldContinuousEntry
        ] = {}
        self._held_continuous_hits = 0
        self._held_continuous_misses = 0
        self._held_continuous_bytes = 0
        self._held_memory_dir = (
            self.run_root.parent / f".{self.run_root.name}.held-memory-cache"
        )
        self._held_memory_entries: dict[
            tuple[str, str, int, str], _HeldMemoryEntry
        ] = {}
        self._held_memory_hits = 0
        self._held_memory_misses = 0
        self._held_memory_bytes = 0

    def _initialize_accelerator(self) -> None:
        if self.device is not None:
            return
        self.determinism_receipt_sha256 = _configure_deterministic_torch()
        requested = self._requested_device
        self.device = torch.device(
            requested or ("cuda" if torch.cuda.is_available() else "cpu")
        )

    def _binding_indexes(self):
        if self._binding_by_id is None:
            by_id = {}; by_session = {}
            for row in self.stage.diagnostic_corpus.bindings:
                if row.candidate_id in by_id:
                    raise RealDiagnosticExecutorRefusal("diagnostic binding ID duplicated")
                by_id[row.candidate_id] = row
                by_session.setdefault((row.asset, row.trading_day), []).append(row)
            self._binding_by_id = MappingProxyType(by_id)
            self._binding_by_session = MappingProxyType({
                key: tuple(value) for key, value in by_session.items()})
        return self._binding_by_id, self._binding_by_session

    def _held_population(self, end_d8: int) -> tuple[Any, ...]:
        return tuple(sorted((spec for spec in self.stage.corpus_stage.corpus.sessions
                             if 20210531 <= spec.trading_day <= end_d8),
                            key=lambda spec: (spec.asset, spec.trading_day,
                                              spec.session_id)))

    def _fit_held_normalizers(self) -> Mapping[str, Any]:
        if self._held_normalizer is not None:
            return self._held_normalizer
        assert self.stage is not None and self.schema is not None
        specs = self._held_population(20220311)
        days = sorted({spec.trading_day for spec in specs})
        validation = frozenset(days[-max(1, int(np.ceil(.1 * len(days)))):])
        observed = {session.key: session for session in self.stage.diagnostic_corpus.sessions}
        width = len(self.schema.continuous_fields); static_width = 1865
        count = 0; total = np.zeros(width); square = np.zeros(width)
        static_count = 0; static_total = np.zeros(static_width)
        static_square = np.zeros(static_width)
        for spec in specs:
            if spec.trading_day in validation:
                continue
            obs = observed[(spec.asset, spec.trading_day)].observed
            obs.validate_backing()
            if obs.truth is None or obs.derived is None:
                raise RealDiagnosticExecutorRefusal("held TRAIN route plane is unavailable")
            stop = int(torch.max(spec.candidate_cutoffs))
            names, expanded = _expanded_columns(obs.derived, stop)
            if names != self.schema.continuous_fields or not np.all(np.isfinite(expanded)):
                raise RealDiagnosticExecutorRefusal("held TRAIN expanded plane differs")
            # Sorted session traversal plus float64 sufficient statistics is
            # bounded in memory and never includes validation inputs.
            count += len(expanded); total += expanded.sum(0, dtype=np.float64)
            square += np.square(expanded, dtype=np.float64).sum(0, dtype=np.float64)
            static = np.asarray(_static_context_summary(spec), np.float64)
            static_count += len(static); static_total += static.sum(0, dtype=np.float64)
            static_square += np.square(static, dtype=np.float64).sum(0, dtype=np.float64)
        if not count or not static_count:
            raise RealDiagnosticExecutorRefusal("held TRAIN normalizer population is empty")
        location = total / count
        scale = np.sqrt(np.maximum(0.0, square / count - location * location))
        constant = scale < 1e-8; scale[constant] = 1.0
        static_location = static_total / static_count
        static_scale = np.sqrt(np.maximum(
            0.0, static_square / static_count - static_location * static_location))
        static_constant = static_scale < 1e-8; static_scale[static_constant] = 1.0
        receipt = _sha({"schema": "entry-v2-held-train-streaming-moments-v1",
                        "train_days": [day for day in days if day not in validation],
                        "validation_days": sorted(validation), "event_count": count,
                        "candidate_count": static_count,
                        "event_location": _sha_bytes(location.tobytes()),
                        "event_scale": _sha_bytes(scale.tobytes()),
                        "static_location": _sha_bytes(static_location.tobytes()),
                        "static_scale": _sha_bytes(static_scale.tobytes())})
        self._held_normalizer = MappingProxyType({
            "location": location, "scale": scale, "constant": constant,
            "static_location": static_location, "static_scale": static_scale,
            "static_constant": static_constant, "validation_days": validation,
            "receipt_sha256": receipt})
        return self._held_normalizer

    def _held_continuous(self, spec: Any, observed: Any, stop: int,
                         normalizer: Mapping[str, Any]) -> torch.Tensor:
        """Return one immutable normalized session plane backed by a file map.

        Expanded event routes are deterministic and fit-normalized.  Building
        them again for every arm and epoch was the dominant avoidable CPU and
        allocation cost.  The cache is process-owned, stat-pinned, and contains
        no labels; it therefore changes neither chronology nor learning bytes.
        """
        if self.schema is None:
            raise RealDiagnosticExecutorRefusal("held event schema is unavailable")
        observed.validate_backing()
        key = (str(spec.asset), int(spec.trading_day), str(spec.session_id))
        entry = self._held_continuous_entries.get(key)
        schema_sha256 = self.schema.sha256
        normalizer_sha256 = str(normalizer["receipt_sha256"])
        if entry is None:
            if self._held_continuous_dir.exists() and not self._held_continuous_entries:
                raise RealDiagnosticExecutorRefusal(
                    "held normalized cache existed before this owner"
                )
            self._held_continuous_dir.mkdir(parents=True, exist_ok=True)
            names, expanded = _expanded_columns(observed.derived, stop)
            if names != self.schema.continuous_fields or not np.all(np.isfinite(expanded)):
                raise RealDiagnosticExecutorRefusal("held expanded session plane differs")
            continuous = ((expanded - normalizer["location"])
                          / normalizer["scale"]).astype(np.float32)
            continuous[:, normalizer["constant"]] = 0.0
            if not np.all(np.isfinite(continuous)):
                raise RealDiagnosticExecutorRefusal(
                    "held normalized session plane is nonfinite"
                )
            identity = hashlib.sha256(
                f"{key[0]}:{key[1]}:{key[2]}".encode()
            ).hexdigest()[:24]
            target = self._held_continuous_dir / f"{key[0]}.{key[1]}.{identity}.f32"
            fd, temporary_name = tempfile.mkstemp(
                prefix=f".{target.name}.", dir=self._held_continuous_dir
            )
            temporary = Path(temporary_name)
            try:
                with os.fdopen(fd, "wb", closefd=True) as handle:
                    continuous.tofile(handle)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.chmod(temporary, 0o444)
                os.rename(temporary, target)
                directory_fd = os.open(self._held_continuous_dir, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            except BaseException:
                try:
                    os.close(fd)
                except OSError:
                    pass
                temporary.unlink(missing_ok=True)
                target.unlink(missing_ok=True)
                raise
            stat = target.stat()
            expected_size = int(continuous.size * continuous.dtype.itemsize)
            if stat.st_size != expected_size or stat.st_mode & 0o222:
                target.unlink(missing_ok=True)
                raise RealDiagnosticExecutorRefusal(
                    "held normalized cache publication differs"
                )
            entry = _HeldContinuousEntry(
                target, tuple(map(int, continuous.shape)), expected_size,
                stat.st_dev, stat.st_ino, stat.st_mtime_ns, stat.st_ctime_ns,
                normalizer_sha256, schema_sha256,
            )
            self._held_continuous_entries[key] = entry
            self._held_continuous_misses += 1
            self._held_continuous_bytes += expected_size
            del expanded, continuous
        else:
            self._held_continuous_hits += 1
            if (entry.normalizer_sha256 != normalizer_sha256
                    or entry.schema_sha256 != schema_sha256):
                raise RealDiagnosticExecutorRefusal(
                    "held normalized cache law changed after publication"
                )
        stat = entry.path.stat()
        if ((stat.st_size, stat.st_dev, stat.st_ino, stat.st_mtime_ns,
             stat.st_ctime_ns) != (entry.size_bytes, entry.device, entry.inode,
                                   entry.mtime_ns, entry.ctime_ns)
                or stat.st_mode & 0o222):
            raise RealDiagnosticExecutorRefusal(
                "held normalized cache identity changed before mapping"
            )
        tensor = torch.from_file(
            str(entry.path), shared=False,
            size=entry.shape[0] * entry.shape[1], dtype=torch.float32,
        ).reshape(entry.shape)
        if tensor.shape != (stop, len(self.schema.continuous_fields)):
            raise RealDiagnosticExecutorRefusal("held normalized cache shape differs")
        return tensor

    def _held_autocast(self):
        return torch.autocast(
            device_type="cuda", dtype=torch.bfloat16,
            enabled=self.device.type == "cuda",
        )

    def _held_raw_memory(self, base_arm: str, model: Any,
                         batch: _CandidateBatch
                         ) -> tuple[torch.Tensor, EncoderComplexityReceipt]:
        """Encode one base representation once and reuse it for all objectives.

        C0/C1 share the current raw encoder checkpoint; L0/L1 share the LiT
        checkpoint; M1 is unique.  Objective and static-bypass heads therefore
        consume the same frozen raw-memory bytes instead of replaying the tape
        for every objective epoch.
        """
        if base_arm not in ("C0", "L0", "M1"):
            raise RealDiagnosticExecutorRefusal("raw-memory base arm is invalid")
        key = (base_arm, batch.asset, int(batch.day), batch.session_id)
        encoder_sha256 = self._held_pointwise_hashes[base_arm]
        entry = self._held_memory_entries.get(key)
        if entry is None:
            if self._held_memory_dir.exists() and not self._held_memory_entries:
                raise RealDiagnosticExecutorRefusal(
                    "held memory cache existed before this owner"
                )
            self._held_memory_dir.mkdir(parents=True, exist_ok=True)
            model.encoder.to(self.device); model.encoder.eval()
            with torch.no_grad(), self._held_autocast():
                memory = model.encoder(
                    batch.continuous.to(self.device),
                    batch.categorical.to(self.device),
                    batch.cutoffs.to(self.device),
                    receive_clock_ns=batch.clock.to(self.device),
                    candidate_decision_ts_ns=batch.decisions.to(self.device),
                    asset_idx=C.ASSET_INDEX[batch.asset],
                )
            value = np.ascontiguousarray(memory.float().cpu().numpy(), np.float32)
            if value.shape != (len(batch.candidate_ids), 4, 512) or not np.all(
                    np.isfinite(value)):
                raise RealDiagnosticExecutorRefusal("held raw memory shape is invalid")
            complexity = getattr(model.encoder, "last_complexity_receipt", None)
            if complexity is None and isinstance(model.encoder, CurrentEncoderAdapter):
                cuts = batch.cutoffs.detach().cpu().numpy().astype(np.int64)
                visible = int(cuts.max(initial=0))
                block = int(model.encoder.current.block_size)
                complexity = EncoderComplexityReceipt(
                    events_visible=visible, regular_blocks=visible // block,
                    candidates=len(cuts), recent_window_events=0,
                    partial_block_events=int(np.mod(cuts, block).sum()),
                    band_60_blocks=0, band_300_blocks=0, band_900_blocks=0,
                    regular_block_encodes=visible // block,
                    unique_prefixes=len(np.unique(cuts)),
                    repeated_prefixes_reused=len(cuts) - len(np.unique(cuts)),
                )
            if not isinstance(complexity, EncoderComplexityReceipt):
                raise RealDiagnosticExecutorRefusal(
                    f"{base_arm} encoder emitted no measured complexity receipt"
                )
            identity = hashlib.sha256(
                f"{base_arm}:{batch.asset}:{batch.day}:{batch.session_id}".encode()
            ).hexdigest()[:24]
            target = self._held_memory_dir / (
                f"{base_arm}.{batch.asset}.{batch.day}.{identity}.f32"
            )
            fd, temporary_name = tempfile.mkstemp(
                prefix=f".{target.name}.", dir=self._held_memory_dir
            )
            temporary = Path(temporary_name)
            try:
                with os.fdopen(fd, "wb", closefd=True) as handle:
                    value.tofile(handle)
                    handle.flush(); os.fsync(handle.fileno())
                os.chmod(temporary, 0o444)
                os.rename(temporary, target)
                directory_fd = os.open(self._held_memory_dir, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            except BaseException:
                try:
                    os.close(fd)
                except OSError:
                    pass
                temporary.unlink(missing_ok=True); target.unlink(missing_ok=True)
                raise
            stat = target.stat(); expected_size = int(value.nbytes)
            if stat.st_size != expected_size or stat.st_mode & 0o222:
                target.unlink(missing_ok=True)
                raise RealDiagnosticExecutorRefusal(
                    "held raw-memory cache publication differs"
                )
            entry = _HeldMemoryEntry(
                target, tuple(map(int, value.shape)), expected_size,
                stat.st_dev, stat.st_ino, stat.st_mtime_ns, stat.st_ctime_ns,
                encoder_sha256, complexity,
            )
            self._held_memory_entries[key] = entry
            self._held_memory_misses += 1
            self._held_memory_bytes += expected_size
            del memory, value
        else:
            self._held_memory_hits += 1
            if entry.encoder_sha256 != encoder_sha256:
                raise RealDiagnosticExecutorRefusal(
                    "held raw-memory encoder changed after publication"
                )
        stat = entry.path.stat()
        if ((stat.st_size, stat.st_dev, stat.st_ino, stat.st_mtime_ns,
             stat.st_ctime_ns) != (entry.size_bytes, entry.device, entry.inode,
                                   entry.mtime_ns, entry.ctime_ns)
                or stat.st_mode & 0o222):
            raise RealDiagnosticExecutorRefusal(
                "held raw-memory cache identity changed before mapping"
            )
        tensor = torch.from_file(
            str(entry.path), shared=False,
            size=int(np.prod(entry.shape)), dtype=torch.float32,
        ).reshape(entry.shape)
        return tensor, entry.complexity

    def _held_batch(self, spec: Any) -> _CandidateBatch:
        norm = self._fit_held_normalizers()
        if self._observed_by_session is None:
            self._observed_by_session = MappingProxyType({
                session.key: session for session in self.stage.diagnostic_corpus.sessions})
        observed = self._observed_by_session
        obs = observed[(spec.asset, spec.trading_day)].observed
        obs.validate_backing()
        if obs.truth is None or obs.derived is None:
            raise RealDiagnosticExecutorRefusal("held session route plane is unavailable")
        stop = int(torch.max(spec.candidate_cutoffs))
        continuous = self._held_continuous(spec, obs, stop, norm)
        with obs.source.open_arrays() as (_, categorical):
            categorical_tensor = torch.from_numpy(np.asarray(categorical[:stop], np.uint8))
        raw_static = np.asarray(spec.static_features.detach().cpu(), np.float64)
        static = ((raw_static - norm["static_location"]) / norm["static_scale"]).astype(
            np.float32)
        static[:, norm["static_constant"]] = 0.0
        bindings, _ = self._binding_indexes()
        labels = tuple(label for _, label in
                       self.stage.corpus_stage.corpus.teacher.join_training(spec.examples))
        if tuple(x.candidate_id for x in labels) != tuple(spec.candidate_ids):
            raise RealDiagnosticExecutorRefusal("held teacher join changed row order")
        oracle = MappingProxyType({
            "value_bin": torch.tensor([VALUE_BIN_INDEX[x.value_bin] for x in labels]),
            "value": torch.tensor([x.cert_close_usd / VALUE_SCALE_USD for x in labels]),
            "top3": torch.tensor([x.top3 for x in labels], dtype=torch.float32),
            "rank": torch.tensor([np.log1p(x.rank) for x in labels], dtype=torch.float32),
            "mfe": torch.tensor([x.mfe_usd / MFE_SCALE_USD for x in labels]),
            "mae": torch.tensor([x.mae_usd / MAE_SCALE_USD for x in labels]),
            "wall": torch.tensor([x.wall_hit for x in labels], dtype=torch.float32),
            "time": torch.tensor([x.time_to_peak_sec / TIME_TO_PEAK_SCALE_SECONDS
                                    for x in labels]),
        })
        cuts = spec.candidate_cutoffs.detach().cpu().long(); last = (cuts - 1).clamp_min(0)
        session_atlas = self._observed_by_session[(spec.asset, spec.trading_day)].atlas
        horizon_target, horizon_valid, horizon_receipt = (
            _selected_horizon_targets_from_spec(
                session_atlas, spec, range(len(spec.candidate_ids)), labels)
        )
        self._selected_horizon_receipts = getattr(
            self, "_selected_horizon_receipts", set())
        self._selected_horizon_receipts.add(horizon_receipt)
        batch = _CandidateBatch(
            spec.asset, spec.trading_day, spec.session_id, tuple(spec.candidate_ids),
            continuous, categorical_tensor,
            torch.from_numpy(np.asarray(obs.truth["ts_recv_ns"][:stop], np.int64)), cuts,
            torch.tensor([bindings[cid].decision_ts_ns for cid in spec.candidate_ids]),
            spec.candidate_features.detach().cpu(), spec.context_values.detach().cpu(),
            spec.context_type_ids.detach().cpu(), spec.context_valid.detach().cpu(),
            torch.from_numpy(static), torch.tensor([float(x.take_target) for x in labels]),
            torch.tensor([bool(x.action_loss_mask) for x in labels]), oracle,
            horizon_target, horizon_valid,
            spec.self_supervised.phase_class.detach().cpu(),
            spec.self_supervised.phase_valid.detach().cpu(),
            continuous[last], categorical_tensor[last])
        normalizer = getattr(self, "_held_horizon_normalizer", None)
        if normalizer is not None:
            location = np.asarray(normalizer["location"], np.float64)
            scale = np.asarray(normalizer["scale"], np.float64)
            valid = batch.horizon_valid.numpy().astype(bool)
            value = ((batch.horizon_targets.numpy().astype(np.float64)
                      - location) / scale).astype(np.float32)
            value[~valid] = 0.0
            batch = replace(batch, horizon_targets=torch.from_numpy(value))
        return batch

    def _train_fresh_held_models(self) -> Mapping[str, Any]:
        if self._held_models is not None:
            return self._held_models
        models = self._new_model_registry()
        competence_hashes = {arm: _sha_bytes(module_state_bytes(model))
                             for arm, model in self._models().items()}
        specs = self._held_population(20220311); norm = self._fit_held_normalizers()
        validation_days = norm["validation_days"]
        train_specs = tuple(x for x in specs if x.trading_day not in validation_days)
        val_specs = tuple(x for x in specs if x.trading_day in validation_days)
        train_by_day: dict[tuple[str, int], list[Any]] = {}
        for spec in train_specs:
            train_by_day.setdefault((spec.asset, spec.trading_day), []).append(spec)
        weight_ids = tuple(cid for spec in specs for cid in spec.candidate_ids)
        bindings, _ = self._binding_indexes()
        weight_days = np.asarray([bindings[cid].trading_day for cid in weight_ids], np.int64)
        weight_assets = np.asarray([bindings[cid].asset for cid in weight_ids], str)
        weight_action = np.asarray([bindings[cid].action_target for cid in weight_ids])
        weight_mask = np.asarray([bindings[cid].action_loss_mask for cid in weight_ids], bool)
        training_indices = np.flatnonzero(~np.isin(weight_days, tuple(validation_days)))
        training_indices = training_indices[np.lexsort((
            np.asarray(weight_ids, str)[training_indices],
            np.asarray([bindings[cid].decision_ts_ns for cid in weight_ids], np.int64)[training_indices],
            weight_days[training_indices], weight_assets[training_indices]))]
        local_weight, fit_weight_receipt = action_fit_weights(
            weight_assets[training_indices], weight_days[training_indices],
            weight_action[training_indices], weight_mask[training_indices],
            np.ones(len(training_indices), bool))
        fit_weight = np.zeros(len(weight_ids), np.float32)
        fit_weight[training_indices] = local_weight
        weight_batches = [self._held_batch(spec) for spec in specs]
        normalized_weight_batches, held_horizon_normalizer = \
            _fit_selected_horizon_normalizer(
                weight_batches, {spec.trading_day for spec in specs}
                - set(validation_days), stage="E2_HELD")
        weight_batches = list(normalized_weight_batches)
        self._held_horizon_normalizer = held_horizon_normalizer
        top3_target = np.concatenate([batch.oracle_targets["top3"].numpy()
                                      for batch in weight_batches])
        wall_target = np.concatenate([batch.oracle_targets["wall"].numpy()
                                      for batch in weight_batches])
        def auxiliary_weight(target_values: np.ndarray, class_weight: bool):
            local, receipt = asset_day_fit_weights(
                weight_assets[training_indices], weight_days[training_indices],
                target_values[training_indices],
                np.ones(len(training_indices), bool),
                np.ones(len(training_indices), bool),
                apply_class_weight=class_weight)
            result = np.zeros(len(weight_ids), np.float32)
            result[training_indices] = local
            return result, receipt
        base_weight, base_weight_receipt = auxiliary_weight(
            np.zeros(len(weight_ids), np.float32), False)
        top3_weight, top3_weight_receipt = auxiliary_weight(top3_target, True)
        wall_weight, wall_weight_receipt = auxiliary_weight(wall_target, True)
        weight_by_id = {cid: {"action": float(fit_weight[i]),
            "base": float(base_weight[i]), "top3": float(top3_weight[i]),
            "wall": float(wall_weight[i])} for i, cid in enumerate(weight_ids)}
        self._held_base_action_weight_receipt = fit_weight_receipt.receipt_sha256
        self._held_base_oracle_weight_receipts = MappingProxyType({
            "base": base_weight_receipt.receipt_sha256,
            "top3": top3_weight_receipt.receipt_sha256,
            "wall": wall_weight_receipt.receipt_sha256})
        traces = {}

        def forward(model, arm: str, batch: _CandidateBatch):
            return model(
                event_continuous=batch.continuous.to(self.device),
                event_categorical=batch.categorical.to(self.device),
                receive_clock_ns=batch.clock.to(self.device),
                candidate_cutoffs=batch.cutoffs.to(self.device),
                candidate_decision_ts_ns=batch.decisions.to(self.device),
                candidate_features=batch.candidate_features.to(self.device),
                context_values=batch.context_values.to(self.device),
                context_type_ids=batch.context_type_ids.to(self.device),
                context_valid=batch.context_valid.to(self.device),
                asset_idx=C.ASSET_INDEX[batch.asset],
                # A-013 fair-arm law: no base encoder stage receives the
                # static bypass.  L1/M1 add the identical lossless static
                # plane only in the later shared-head objective stage.
                static_features=None,
            )

        def losses(model, decoder, arm: str, batch: _CandidateBatch, *, weighted: bool):
            out = forward(model, arm, batch)
            action_weight = ({name: torch.tensor([
                weight_by_id[cid][name] for cid in batch.candidate_ids],
                dtype=torch.float32) for name in ("action", "base", "top3", "wall")}
                if weighted else None)
            oracle_loss, components = _actual_multitask_loss(
                out, batch, action_weight)
            reconstructed_continuous, reconstructed_categorical = decoder(out.raw_memory)
            continuous_loss = torch.nn.functional.mse_loss(
                reconstructed_continuous.float(),
                batch.last_continuous.to(self.device).float(),
            )
            categorical_loss = sum(
                torch.nn.functional.cross_entropy(
                    logits.float(),
                    batch.last_categorical[:, index].to(self.device).long(),
                ) for index, logits in enumerate(reconstructed_categorical)
            )
            reconstruction_loss = continuous_loss + categorical_loss
            return (oracle_loss + reconstruction_loss, components,
                    continuous_loss, categorical_loss, oracle_loss,
                    reconstruction_loss)

        def validation_loss(model, decoder, arm: str) -> tuple[float, float, float]:
            totals = []; continuous = []; categorical = []
            model.eval(); decoder.eval()
            with torch.no_grad():
                for spec in val_specs:
                    batch = self._held_batch(spec)
                    with self._held_autocast():
                        total, _, cont, cat, _oracle, _reconstruction = losses(
                            model, decoder, arm, batch, weighted=False)
                    totals.append(float(total)); continuous.append(float(cont))
                    categorical.append(float(cat))
            values = np.asarray([totals, continuous, categorical], np.float64)
            if not totals or not np.all(np.isfinite(values)):
                raise RealDiagnosticExecutorRefusal("held validation loss is unavailable")
            return tuple(float(np.mean(value)) for value in values)

        # Field survival and dense oracle supervision share the same raw pass.
        # Running them as separate full-dataset stages encoded the identical
        # 244M-event fit plane twice per epoch without providing new inputs.
        for arm in ("C0", "L0", "M1"):
            model = models[arm].to(self.device)
            decoder = LastRowReconstructionProbe(
                len(self.schema.continuous_fields), CATEGORY_SIZES).to(self.device)
            optimizer = torch.optim.AdamW(
                [*model.parameters(), *decoder.parameters()], lr=1e-3,
                weight_decay=1e-4,
            )
            best = None; best_loss = np.inf; stale = 0; trace = []
            gradient_census: set[str] = set()
            for epoch in range(12):
                model.train(); decoder.train(); rows = []; epoch_gradient_norm = 0.0
                named = [*model.named_parameters(), *[(f"decoder.{name}", parameter)
                         for name, parameter in decoder.named_parameters()]]
                before = {name: value.detach().cpu().clone() for name, value in named}
                for day_key in sorted(train_by_day):
                    optimizer.zero_grad(set_to_none=True)
                    oracle_parts = []; reconstruction_parts = []; day_rows = []
                    for spec in train_by_day[day_key]:
                        batch = self._held_batch(spec)
                        with self._held_autocast():
                            total, components, cont, cat, oracle_total, reconstruction = losses(
                                model, decoder, arm, batch, weighted=True)
                        oracle_parts.append(oracle_total)
                        reconstruction_parts.append(reconstruction)
                        day_rows.append({**{name: float(value.detach())
                                           for name, value in components.items()},
                            "field_continuous": float(cont.detach()),
                            "field_categorical": float(cat.detach()),
                            "total": float(total.detach())})
                    total = (torch.stack(oracle_parts).sum()
                             + torch.stack(reconstruction_parts).mean())
                    total.backward()
                    gradients = [(name, parameter.grad) for name, parameter in named
                                 if parameter.grad is not None]
                    if (not gradients or any(not bool(torch.isfinite(gradient).all())
                                             for _, gradient in gradients)):
                        raise RealDiagnosticExecutorRefusal(
                            "held joint oracle has missing/nonfinite gradients")
                    for name, gradient in gradients:
                        value = float(torch.linalg.vector_norm(gradient.detach()))
                        epoch_gradient_norm += value
                        if value > 0.0: gradient_census.add(name)
                    optimizer.step(); rows.extend(day_rows)
                validation, val_continuous, val_categorical = validation_loss(
                    model, decoder, arm)
                after = [*model.named_parameters(), *[(f"decoder.{name}", parameter)
                         for name, parameter in decoder.named_parameters()]]
                delta = float(sum(torch.linalg.vector_norm(
                    value.detach().cpu() - before[name]) for name, value in after))
                means = {key: float(np.mean([row[key] for row in rows]))
                         for key in rows[0]}
                checkpoint = _sha({
                    "model": _sha_bytes(module_state_bytes(model)),
                    "decoder": _sha_bytes(module_state_bytes(decoder)),
                })
                trace.append({"epoch": epoch, "components": means,
                    "validation": validation,
                    "validation_field_continuous": val_continuous,
                    "validation_field_categorical": val_categorical,
                    "gradient_norm": epoch_gradient_norm,
                    "parameter_delta": delta, "checkpoint_sha256": checkpoint})
                if validation < best_loss * .999:
                    best_loss = validation; stale = 0
                    best = (copy.deepcopy(model.state_dict()),
                            copy.deepcopy(decoder.state_dict()), checkpoint)
                else:
                    stale += 1
                if epoch >= 1 and stale >= 3:
                    break
            if best is None or len(trace) < 2:
                raise RealDiagnosticExecutorRefusal(
                    "held joint field/dense stage did not converge")
            expected = {name for name, parameter in model.named_parameters()
                        if parameter.requires_grad and not (
                            "static_slot_embedding" in name)}
            missing = expected - gradient_census
            if missing:
                raise RealDiagnosticExecutorRefusal(
                    f"held joint oracle never routed parameters: {sorted(missing)}")
            model.load_state_dict(best[0], strict=True)
            decoder.load_state_dict(best[1], strict=True)
            reload_hash = _sha({
                "model": _sha_bytes(module_state_bytes(model)),
                "decoder": _sha_bytes(module_state_bytes(decoder)),
            })
            if reload_hash != best[2] or min(row["validation"] for row in trace) > best_loss:
                raise RealDiagnosticExecutorRefusal("held joint checkpoint reload differs")
            traces[arm] = {"joint_field_dense": trace,
                           "best_reload_sha256": reload_hash,
                           "gradient_census": sorted(gradient_census)}
            model.cpu(); decoder.cpu()
            if self.device.type == "cuda":
                torch.cuda.empty_cache()
        # C1 and L1 begin the grouped-objective experiment from the exact same
        # independently fitted pointwise checkpoints as their controls.
        models["C1"].load_state_dict(models["C0"].state_dict(), strict=True)
        models["L1"].load_state_dict(models["L0"].state_dict(), strict=True)
        trained_hashes = {arm: _sha_bytes(module_state_bytes(model))
                          for arm, model in models.items()}
        self._held_pointwise_hashes = {arm: _sha_bytes(module_state_bytes(model.encoder))
                                       for arm, model in models.items()}
        if any(trained_hashes[arm] == competence_hashes[arm] for arm in CANONICAL_ARMS):
            raise RealDiagnosticExecutorRefusal("held arm reused a competence checkpoint")
        self._held_training_receipt = _sha({
            "schema": "entry-v2-fresh-held-arm-training-v2",
            "optimization_law": "joint-field-survival-plus-dense-oracle-v1",
            "maximum_epochs": 12, "patience": 3,
            "normalizer": norm["receipt_sha256"], "competence": competence_hashes,
            "action_fit_weight_receipt_sha256": fit_weight_receipt.receipt_sha256,
            "oracle_fit_weight_receipts": {
                "base": base_weight_receipt.receipt_sha256,
                "top3": top3_weight_receipt.receipt_sha256,
                "wall": wall_weight_receipt.receipt_sha256},
            "trained": trained_hashes, "trace": traces,
            "determinism": self.determinism_receipt_sha256,
            "cuda_precision": ("BF16_AUTOCAST_FP32_LOSS" if self.device.type == "cuda"
                               else "FP32"),
            "normalized_session_cache": {
                "schema": "entry-v2-held-normalized-session-cache-v1",
                "disk_backed": True,
                "entries": len(self._held_continuous_entries),
                "logical_bytes": self._held_continuous_bytes,
                "misses": self._held_continuous_misses,
                "hits": self._held_continuous_hits,
            },
            "competence_clones_discarded": True})
        self._held_models = models
        return models

    def _train_grouped_selected_objective(self, probe_id: str, target: ProbeTarget) -> None:
        """Six-epoch selected-objective stage on the actual encoder/shared head."""
        if self._held_objective_heads is not None:
            raise RealDiagnosticExecutorRefusal("grouped objective stage already executed")
        from .atlas_losses import loss_for_probe
        models = self._train_fresh_held_models()
        probe = next(x for x in PROBE_REGISTRY if x.probe_id == probe_id)
        ids = tuple(self._build_held_probe_plane()[1]); position = {
            cid: i for i, cid in enumerate(ids)}
        fit_specs = self._held_population(20220311)
        days = sorted({spec.trading_day for spec in fit_specs})
        validation_days = set(days[-max(1, int(np.ceil(.1 * len(days)))):])
        all_candidate_ids = tuple(cid for spec in fit_specs for cid in spec.candidate_ids)
        fit_position = {cid: i for i, cid in enumerate(all_candidate_ids)}
        all_assets = np.asarray([spec.asset for spec in fit_specs
            for _ in spec.candidate_ids], str)
        all_days = np.asarray([spec.trading_day for spec in fit_specs
            for _ in spec.candidate_ids], np.int64)
        all_phases = np.asarray([example.phase for spec in fit_specs
            for example in spec.examples], str)
        all_decisions = np.asarray([example.decision_ts_ns for spec in fit_specs
            for example in spec.examples], np.int64)
        all_batches = [self._held_batch(spec) for spec in fit_specs]
        all_action = np.concatenate([batch.targets.numpy() for batch in all_batches]) > .5
        all_allowed = np.concatenate([
            batch.action_loss_mask.numpy() for batch in all_batches]).astype(bool)
        phase_manifest = canonical_phase_pair_manifest(
            all_candidate_ids, all_assets, all_days, all_phases, all_decisions,
            all_action, all_allowed, np.arange(len(all_candidate_ids)))
        train_phase_manifest = canonical_phase_pair_manifest(
            all_candidate_ids, all_assets, all_days, all_phases, all_decisions,
            all_action, all_allowed, ~np.isin(all_days, tuple(validation_days)))
        pair_by_day: dict[tuple[str, int], list[tuple[str, str, float]]] = {}
        pair_receipt_rows = []
        for (positive, negative), weight in zip(
                phase_manifest.candidate_id_pairs, phase_manifest.pair_weights):
            row = fit_position[positive]
            pair_by_day.setdefault((str(all_assets[row]), int(all_days[row])), []).append(
                (positive, negative, float(weight)))
            pair_receipt_rows.append((positive, negative, float(weight)))
        spec_by_day: dict[tuple[str, int], list[Any]] = {}
        for spec in fit_specs:
            spec_by_day.setdefault((spec.asset, spec.trading_day), []).append(spec)
        if (not pair_receipt_rows
                or not any(key[1] in validation_days for key in pair_by_day)
                or not any(key[1] not in validation_days for key in pair_by_day)):
            raise RealDiagnosticExecutorRefusal("phase-matched contrast manifest lacks train/validation pairs")
        grouped_train = np.flatnonzero(~np.isin(all_days, tuple(validation_days)))
        grouped_train = grouped_train[np.lexsort((
            np.asarray(all_candidate_ids, str)[grouped_train],
            all_decisions[grouped_train], all_days[grouped_train],
            all_assets[grouped_train]))]
        local_grouped_weight, grouped_weight_receipt = action_fit_weights(
            all_assets[grouped_train], all_days[grouped_train],
            all_action[grouped_train], all_allowed[grouped_train],
            np.ones(len(grouped_train), bool))
        grouped_weight = np.zeros(len(all_days), np.float32)
        grouped_weight[grouped_train] = local_grouped_weight
        def grouped_auxiliary(target_values: np.ndarray, class_weight: bool):
            local, receipt = asset_day_fit_weights(
                all_assets[grouped_train], all_days[grouped_train],
                target_values[grouped_train], np.ones(len(grouped_train), bool),
                np.ones(len(grouped_train), bool), apply_class_weight=class_weight)
            result = np.zeros(len(all_days), np.float32); result[grouped_train] = local
            return result, receipt
        grouped_base, grouped_base_receipt = grouped_auxiliary(
            np.zeros(len(all_days), np.float32), False)
        grouped_top3, grouped_top3_receipt = grouped_auxiliary(
            np.concatenate([batch.oracle_targets["top3"].numpy()
                            for batch in all_batches]), True)
        grouped_wall, grouped_wall_receipt = grouped_auxiliary(
            np.concatenate([batch.oracle_targets["wall"].numpy()
                            for batch in all_batches]), True)
        grouped_weight_by_id = {cid: {
            "action": float(grouped_weight[i]), "base": float(grouped_base[i]),
            "top3": float(grouped_top3[i]), "wall": float(grouped_wall[i])}
            for i, cid in enumerate(all_candidate_ids)}
        self._held_grouped_action_weight_receipt = grouped_weight_receipt.receipt_sha256
        if grouped_weight_receipt.receipt_sha256 != self._held_base_action_weight_receipt:
            raise RealDiagnosticExecutorRefusal(
                "base and grouped action fit-weight receipts differ")
        if self._held_base_oracle_weight_receipts != {
                "base": grouped_base_receipt.receipt_sha256,
                "top3": grouped_top3_receipt.receipt_sha256,
                "wall": grouped_wall_receipt.receipt_sha256}:
            raise RealDiagnosticExecutorRefusal(
                "base and grouped oracle fit-weight receipts differ")
        pair_manifest_sha256 = phase_manifest.receipt_sha256
        self._held_phase_pairs = tuple(
            train_phase_manifest.candidate_id_pairs)
        self._held_phase_pair_weights = MappingProxyType({
            pair: float(weight) for pair, weight in zip(
                train_phase_manifest.candidate_id_pairs,
                train_phase_manifest.pair_weights)})
        heads = {}; traces = {}
        base_by_arm = {"C0": "C0", "C1": "C0", "L0": "L0",
                       "L1": "L0", "M1": "M1"}
        for arm in CANONICAL_ARMS:
            model = models[arm]
            model.head.to(self.device)
            model.encoder.requires_grad_(False)
            torch.manual_seed(20260816 + probe.cell)
            objective = torch.nn.Linear(512, PADDED_OUTPUT_WIDTH).to(self.device)
            if arm == "C0":
                # A0_CURRENT_GROUPING has no atlas projection.  Keep the
                # serialization-only objective head canonical zero while the
                # real shared model trains on pointwise oracle + matched
                # grouping contrast below.
                torch.nn.init.zeros_(objective.weight); torch.nn.init.zeros_(objective.bias)
                objective.requires_grad_(False)
            else:
                torch.nn.init.xavier_uniform_(objective.weight)
                torch.nn.init.zeros_(objective.bias)
            optimizer = torch.optim.AdamW(
                [*model.head.parameters(),
                 *(() if arm == "C0" else objective.parameters())], lr=1e-3,
                weight_decay=1e-4)
            best = None; best_loss = np.inf; stale = 0; trace = []
            for epoch in range(6):
                model.train(); objective.train(); train_losses = []; components = []
                before = {name: value.detach().cpu().clone() for name, value in
                          [*model.named_parameters(), *[(f"objective.{n}", p)
                          for n, p in objective.named_parameters()]]}
                gradient_norm = 0.0
                for day_key in sorted(spec_by_day):
                    if day_key[1] in validation_days: continue
                    optimizer.zero_grad(set_to_none=True)
                    selected_parts = []; oracle_parts = []; logits = {}
                    for spec in spec_by_day[day_key]:
                        batch = self._held_batch(spec); idx = np.asarray(
                            [position[cid] for cid in batch.candidate_ids], np.int64)
                        memory, _ = self._held_raw_memory(
                            base_by_arm[arm], models[base_by_arm[arm]], batch)
                        with self._held_autocast():
                            out = model.head(
                                memory.to(self.device),
                                batch.candidate_features.to(self.device),
                                context_values=batch.context_values.to(self.device),
                                context_type_ids=batch.context_type_ids.to(self.device),
                                context_valid=batch.context_valid.to(self.device),
                                asset_idx=C.ASSET_INDEX[batch.asset],
                                static_features=(batch.static_features.to(self.device)
                                                 if arm in ("L1", "M1") else None))
                            selected_parts.append(out.action_logit.sum() * 0.0
                                if arm == "C0" else loss_for_probe(
                                    probe, objective(out.decision_state),
                                    _target_take(target, idx)))
                            action_weight = {name: torch.tensor([
                                grouped_weight_by_id[cid][name]
                                for cid in batch.candidate_ids], dtype=torch.float32)
                                for name in ("action", "base", "top3", "wall")}
                            oracle_total, oracle_components = _actual_multitask_loss(
                                out, batch, action_weight)
                            oracle_parts.append(oracle_total)
                            logits.update({cid: out.action_logit[i]
                                for i, cid in enumerate(batch.candidate_ids)})
                    pairs = pair_by_day.get(day_key, ())
                    zero = next(iter(logits.values())).sum() * 0.0
                    matched = (torch.stack([weight * torch.nn.functional.softplus(-(
                        logits[positive].float() - logits[negative].float()))
                        for positive, negative, weight in pairs]).sum() if pairs else zero)
                    selected_loss = torch.stack(selected_parts).sum()
                    oracle_loss = torch.stack(oracle_parts).sum()
                    loss = selected_loss + oracle_loss + .5 * matched
                    loss.backward()
                    gradient_norm += sum(float(torch.linalg.vector_norm(p.grad.detach()))
                        for group in optimizer.param_groups for p in group["params"]
                        if p.grad is not None)
                    optimizer.step(); train_losses.append(float(loss.detach()))
                    components.append((float(selected_loss.detach()),
                                       float(oracle_loss.detach()), float(matched.detach())))
                values = []; model.eval(); objective.eval()
                with torch.no_grad():
                    for day_key in sorted(spec_by_day):
                        if day_key[1] not in validation_days: continue
                        selected_parts = []; oracle_parts = []; logits = {}
                        for spec in spec_by_day[day_key]:
                            batch = self._held_batch(spec); idx = np.asarray(
                                [position[cid] for cid in batch.candidate_ids], np.int64)
                            memory, _ = self._held_raw_memory(
                                base_by_arm[arm], models[base_by_arm[arm]], batch)
                            with self._held_autocast():
                                out = model.head(
                                    memory.to(self.device), batch.candidate_features.to(self.device),
                                    context_values=batch.context_values.to(self.device),
                                    context_type_ids=batch.context_type_ids.to(self.device),
                                    context_valid=batch.context_valid.to(self.device),
                                    asset_idx=C.ASSET_INDEX[batch.asset],
                                    static_features=(batch.static_features.to(self.device)
                                                     if arm in ("L1", "M1") else None))
                                selected_parts.append(out.action_logit.sum() * 0.0
                                    if arm == "C0" else loss_for_probe(
                                        probe, objective(out.decision_state),
                                        _target_take(target, idx),
                                        use_fit_weight=False))
                                oracle_parts.append(_actual_multitask_loss(out, batch)[0])
                                logits.update({cid: out.action_logit[i]
                                    for i, cid in enumerate(batch.candidate_ids)})
                        pairs = pair_by_day.get(day_key, ())
                        zero = next(iter(logits.values())).sum() * 0.0
                        matched = (torch.stack([torch.nn.functional.softplus(-(
                            logits[positive].float() - logits[negative].float()))
                            for positive, negative, _weight in pairs]).mean()
                            if pairs else zero)
                        values.append(float(torch.stack(selected_parts).mean()
                            + torch.stack(oracle_parts).mean() + .5 * matched))
                validation = float(np.mean(values))
                after_named = [*model.named_parameters(), *[(f"objective.{n}", p)
                               for n, p in objective.named_parameters()]]
                parameter_delta = sum(float(torch.linalg.vector_norm(
                    value.detach().cpu() - before[name]))
                                      for name, value in after_named)
                trace.append({"epoch": epoch, "train_total": float(np.mean(train_losses)),
                    "train_selected": float(np.mean([x[0] for x in components])),
                    "train_oracle": float(np.mean([x[1] for x in components])),
                    "train_contrast": float(np.mean([x[2] for x in components])),
                    "validation_total": validation, "gradient_norm": gradient_norm,
                    "parameter_delta": parameter_delta,
                    "model_sha256": _sha_bytes(module_state_bytes(model)),
                    "objective_sha256": _sha_bytes(module_state_bytes(objective))})
                if validation < best_loss * .999:
                    best_loss = validation; stale = 0
                    best = (copy.deepcopy(model.state_dict()),
                            copy.deepcopy(objective.state_dict()))
                else: stale += 1
                if epoch >= 1 and stale >= 2: break
            if best is None or len(trace) < 2:
                raise RealDiagnosticExecutorRefusal("grouped selected objective did not converge")
            model.load_state_dict(best[0], strict=True); objective.load_state_dict(best[1])
            model.encoder.requires_grad_(True)
            model.cpu(); heads[arm] = objective.cpu(); traces[arm] = tuple(trace)
            if self.device.type == "cuda":
                torch.cuda.empty_cache()
        self._held_objective_heads = heads
        self._held_grouped_receipt = _sha({"probe_id": probe_id,
            "objective_schema": target.schema_sha256, "traces": traces,
            "c0_objective": "A0_CURRENT_GROUPING",
            "phase_pair_manifest_sha256": pair_manifest_sha256,
            "train_phase_pair_manifest_sha256": train_phase_manifest.receipt_sha256,
            "phase_pair_count": len(pair_receipt_rows),
            "phase_pair_weight_sha256": _sha_bytes(
                np.asarray(phase_manifest.pair_weights, np.float64).tobytes()),
            "action_fit_weight_receipt_sha256": grouped_weight_receipt.receipt_sha256,
            "oracle_fit_weight_receipts": {
                "base": grouped_base_receipt.receipt_sha256,
                "top3": grouped_top3_receipt.receipt_sha256,
                "wall": grouped_wall_receipt.receipt_sha256},
            "validation_weight_law": "row_weight=None,pair_weight=None",
            "frozen_raw_memory": {
                "schema": "entry-v2-frozen-raw-memory-objective-matrix-v1",
                "entries": len(self._held_memory_entries),
                "logical_bytes": self._held_memory_bytes,
                "misses": self._held_memory_misses,
                "hits": self._held_memory_hits,
                "base_by_arm": base_by_arm,
            },
            "fit_end": 20220311, "maximum_epochs": 6, "patience": 2})

    def _produce_held_arm_paths(self, *, end_d8: int = 20221230
                                ) -> Mapping[str, str]:
        """Stream real cached sessions and score all five arm/direct-tree paths."""
        if self._held_path_receipts:
            return MappingProxyType(dict(self._held_path_receipts))
        if (not self.arm_rows
                and not hasattr(self, "_accepted_arm_authorization")):
            raise RealDiagnosticExecutorRefusal("acceptance must authorize architecture first")
        models = self._train_fresh_held_models()
        assert self.stage is not None
        bindings, binding_by_session = self._binding_indexes()
        selected = self._held_population(end_d8)
        if not selected:
            raise RealDiagnosticExecutorRefusal("held arm scorer has no sessions")
        ids = tuple(cid for spec in selected for cid in spec.candidate_ids)
        if len(ids) != len(set(ids)):
            raise RealDiagnosticExecutorRefusal("held arm candidates duplicate")
        work = self.run_root / "held-stage" / "representations"
        work.mkdir(parents=True, exist_ok=True)
        states = {arm: np.memmap(work / f"{arm}.f32", mode="w+", dtype=np.float32,
                                 shape=(len(ids), 512)) for arm in CANONICAL_ARMS}
        probabilities = {arm: np.memmap(work / f"{arm}.prob.f64", mode="w+",
                                        dtype=np.float64, shape=(len(ids),))
                         for arm in CANONICAL_ARMS}
        diagnostic_names = (
            "top3_p", "wall_p_upper", "expected_value_raw",
            "expected_value_lower", "expected_value_upper", "mae_q90",
        )
        diagnostics = {arm: {name: np.memmap(
            work / f"{arm}.{name}.f64", mode="w+", dtype=np.float64,
            shape=(len(ids),)) for name in diagnostic_names}
            for arm in CANONICAL_ARMS}
        phase_groups = [
            f"{spec.asset}:{spec.trading_day}:{example.phase}"
            for spec in selected for example in spec.examples
        ]
        work_counts = {arm: {name: 0 for name in (
            "events_visible", "regular_blocks", "candidates", "recent_window_events",
            "partial_block_events", "band_60_blocks", "band_300_blocks",
            "band_900_blocks", "regular_block_encodes", "regular_block_chunks",
            "candidate_window_chunks",
            "unique_prefixes", "repeated_prefixes_reused")}
                                  for arm in CANONICAL_ARMS}
        complexity_high_water = {arm: {"regular": 0, "candidate": 0}
                                 for arm in CANONICAL_ARMS}
        base_by_arm = {"C0": "C0", "C1": "C0", "L0": "L0",
                       "L1": "L0", "M1": "M1"}
        # One model owns CUDA at a time.  The prior session-major traversal
        # accumulated all five large models on device and could OOM the 96 GiB
        # card.  Arm-major traversal preserves the exact row order while the
        # immutable normalized-session cache removes repeated CPU conversion.
        for arm in CANONICAL_ARMS:
            model = models[arm]; model.head.to(self.device); model.eval()
            offset = 0
            for spec in selected:
                batch = self._held_batch(spec); count = len(spec.candidate_ids)
                sl = slice(offset, offset + count)
                memory, complexity = self._held_raw_memory(
                    base_by_arm[arm], models[base_by_arm[arm]], batch)
                with torch.no_grad():
                    with self._held_autocast():
                        out = model.head(
                            memory.to(self.device), batch.candidate_features.to(self.device),
                            batch.context_values.to(self.device),
                            batch.context_type_ids.to(self.device),
                            batch.context_valid.to(self.device), C.ASSET_INDEX[spec.asset],
                            static_features=(batch.static_features.to(self.device)
                                             if arm in ("L1", "M1") else None))
                states[arm][sl] = out.decision_state.detach().cpu().numpy()
                probabilities[arm][sl] = torch.sigmoid(
                    out.action_logit).detach().cpu().numpy()
                diagnostics[arm]["top3_p"][sl] = torch.sigmoid(
                    out.top3_logit.float()).detach().cpu().numpy()
                diagnostics[arm]["wall_p_upper"][sl] = torch.sigmoid(
                    out.wall_logit.float()).detach().cpu().numpy()
                diagnostics[arm]["expected_value_raw"][sl] = (
                    out.expected_value.float().detach().cpu().numpy()
                    * VALUE_SCALE_USD)
                value_quantiles = out.value_quantiles.float().detach().cpu().numpy()
                diagnostics[arm]["expected_value_lower"][sl] = (
                    value_quantiles[:, 0] * VALUE_SCALE_USD)
                diagnostics[arm]["expected_value_upper"][sl] = (
                    value_quantiles[:, 2] * VALUE_SCALE_USD)
                diagnostics[arm]["mae_q90"][sl] = (
                    out.mae_quantiles[:, 2].float().detach().cpu().numpy()
                    * MAE_SCALE_USD)
                for name in work_counts[arm]:
                    work_counts[arm][name] += int(getattr(complexity, name))
                complexity_high_water[arm]["regular"] = max(
                    complexity_high_water[arm]["regular"],
                    int(complexity.regular_block_chunk_high_water))
                complexity_high_water[arm]["candidate"] = max(
                    complexity_high_water[arm]["candidate"],
                    int(complexity.candidate_window_chunk_high_water))
                offset += count
            if offset != len(ids):
                raise RealDiagnosticExecutorRefusal(
                    f"held {arm} stream did not fill row manifest")
            model.cpu()
            if self.device.type == "cuda":
                torch.cuda.empty_cache()
        for arm in CANONICAL_ARMS:
            states[arm].flush(); probabilities[arm].flush()
            for value in diagnostics[arm].values():
                value.flush()
            rows = FrozenRepresentationRows(
                states[arm], np.asarray(ids),
                np.asarray([bindings[cid].asset for cid in ids]),
                np.asarray([bindings[cid].trading_day for cid in ids], np.int64),
                np.asarray([bindings[cid].decision_ts_ns for cid in ids], np.int64),
                np.asarray([bindings[cid].action_target for cid in ids], np.int8),
                np.asarray([bindings[cid].action_loss_mask for cid in ids], bool),
                np.asarray(phase_groups),
                np.asarray([("VALIDATION" if bindings[cid].trading_day in
                             self._held_normalizer["validation_days"] else "TRAIN")
                            for cid in ids]), "E2",
                eligible_development_days=tuple(sorted({session.trading_day
                    for session in self.stage.corpus_stage.corpus.replay.expected_sessions
                    if 20220314 <= session.trading_day <= 20220609})),
                group_semantics="PHASE")
            rows.validate(); self._held_arm_rows[arm] = rows
            tree = fit_diagnostic_catboost(
                rows, expected_representation_sha256=rows.representation_sha256)
            if tree.action_weight_receipt_sha256 != self._held_grouped_action_weight_receipt:
                raise RealDiagnosticExecutorRefusal(
                    f"{arm} neural/CatBoost action fit-weight receipts differ")
            expected_pairs = {asset: sorted((positive, negative) for positive, negative
                in self._held_phase_pairs if bindings[positive].asset == asset)
                for asset in C.ASSETS}
            for asset in C.ASSETS:
                manifest_pairs = tree.assets[asset].pair_manifest
                selected_ids = np.asarray(ids)[manifest_pairs.indices]
                actual_pairs = sorted((str(selected_ids[p]), str(selected_ids[n]))
                                      for p, n in manifest_pairs.pairs)
                if actual_pairs != expected_pairs[asset]:
                    raise RealDiagnosticExecutorRefusal(
                        f"{arm}/{asset} neural/CatBoost phase-pair manifest differs")
                actual_weights = {pair: float(weight) for pair, weight in zip(
                    ((str(selected_ids[p]), str(selected_ids[n]))
                     for p, n in manifest_pairs.pairs),
                    manifest_pairs.pair_weights)}
                if (set(actual_weights) != set(expected_pairs[asset])
                        or any(not np.isclose(actual_weights[pair],
                            self._held_phase_pair_weights[pair], rtol=0.0, atol=1e-12)
                            for pair in expected_pairs[asset])):
                    raise RealDiagnosticExecutorRefusal(
                        f"{arm}/{asset} neural/CatBoost phase-pair weights differ")
            self._held_path_receipts[f"{arm}:direct_neural"] = _sha({
                "rows": rows.representation_sha256,
                "probability": _sha_bytes(probabilities[arm].tobytes()),
                "fresh_training": self._held_training_receipt,
                "measured_work": work_counts[arm],
                "regular_block_chunk_high_water": complexity_high_water[arm]["regular"],
                "candidate_window_chunk_high_water": complexity_high_water[arm]["candidate"]})
            self._held_path_receipts[f"{arm}:catboost"] = _sha({
                "rows": rows.representation_sha256,
                "fit": tree.receipt_sha256,
                "probability": _sha_bytes(tree.action_probability.tobytes()),
                "fresh_training": self._held_training_receipt,
                "measured_work": work_counts[arm],
                "regular_block_chunk_high_water": complexity_high_water[arm]["regular"],
                "candidate_window_chunk_high_water": complexity_high_water[arm]["candidate"]})
            setattr(self, "_held_catboost", getattr(self, "_held_catboost", {}))
            self._held_catboost[arm] = tree
            setattr(self, "_held_direct_probability", getattr(
                self, "_held_direct_probability", {}))
            self._held_direct_probability[arm] = probabilities[arm]
            setattr(self, "_held_diagnostic_scores", getattr(
                self, "_held_diagnostic_scores", {}))
            self._held_diagnostic_scores[arm] = MappingProxyType(
                dict(diagnostics[arm]))
        return MappingProxyType(dict(self._held_path_receipts))

    def _build_held_probe_plane(self, *, maximum_d8: int = 20221230,
                                pretext_fit_end: int = 20210930):
        """Build a bounded candidate plane with explicitly frozen pretext wall."""
        cache_name = ("_held_probe_plane" if (maximum_d8, pretext_fit_end)
                      == (20221230, 20210930) else
                      f"_probe_plane_{maximum_d8}_{pretext_fit_end}")
        if hasattr(self, cache_name):
            return getattr(self, cache_name)
        assert self.stage is not None
        observed = {session.key: session for session in self.stage.diagnostic_corpus.sessions}
        bindings = {row.candidate_id: row for row in self.stage.diagnostic_corpus.bindings}
        specs = self._held_population(maximum_d8)
        ids = tuple(cid for spec in specs for cid in spec.candidate_ids)
        if not ids or len(ids) != len(set(ids)):
            raise RealDiagnosticExecutorRefusal("held probe candidate roster is invalid")
        position = {cid: i for i, cid in enumerate(ids)}
        n = len(ids); static = np.empty((n, 1865), np.float32)
        session_rows = {}
        for spec in specs:
            obs = observed[(spec.asset, spec.trading_day)].observed
            obs.validate_backing()
            if obs.truth is None or obs.derived is None:
                raise RealDiagnosticExecutorRefusal("through-E3 derived plane is unavailable")
            rows = np.asarray([position[cid] for cid in spec.candidate_ids], np.int64)
            session_rows[(spec.asset, spec.trading_day)] = rows
            static[rows] = np.asarray(_static_context_summary(spec), np.float32)

        def session_factory():
            for spec in specs:
                obs = observed[(spec.asset, spec.trading_day)].observed
                obs.validate_backing()
                stop = int(torch.max(spec.candidate_cutoffs))
                names, expanded = _expanded_columns(obs.derived, stop)
                if names != self.schema.continuous_fields:
                    raise RealDiagnosticExecutorRefusal("held probe expanded schema differs")
                with obs.source.open_arrays() as (_, categorical):
                    categories = np.asarray(categorical[:stop], np.int64).copy()
                yield CausalPretextSession(
                    spec.session_id, spec.asset, str(spec.trading_day), expanded, categories,
                    np.asarray(obs.truth["ts_recv_ns"][:stop], np.int64),
                    spec.candidate_cutoffs.detach().cpu().numpy(),
                    np.asarray([bindings[cid].decision_ts_ns for cid in spec.candidate_ids],
                               np.int64), session_rows[(spec.asset, spec.trading_day)],
                    spec.candidate_ids)
        assets = np.asarray([bindings[cid].asset for cid in ids])
        days = np.asarray([bindings[cid].trading_day for cid in ids], np.int64)
        decisions = np.asarray([bindings[cid].decision_ts_ns for cid in ids], np.int64)
        fit_e1 = np.flatnonzero(days <= pretext_fit_end)

        def contexts_for(fit_end: int):
            fit_ids = {cid for cid, day in zip(ids, days) if day <= fit_end}
            population = _sha({"fit_end": fit_end, "ids": sorted(fit_ids)})
            c1_spec = next(s for s in PROBE_REGISTRY if s.probe_id == "C01P01")
            c1_parts = []; trajectory_parts = []
            c22 = next(s for s in PROBE_REGISTRY if s.cell == 22
                       and _probe_variant(s) == 1)
            censor_parts = {10: [], 24: []}
            for spec in specs:
                session = observed[(spec.asset, spec.trading_day)]
                local_map = {cid: i for i, cid in enumerate(session.atlas.candidate_ids)}
                local = np.asarray([local_map[cid] for cid in spec.candidate_ids], np.int64)
                take_fit = np.asarray([cid in fit_ids for cid in spec.candidate_ids], bool)
                if not take_fit.any(): continue
                preliminary = materialize_probe_target(session.atlas, c1_spec,
                    fit_context={"c1_location": np.zeros(21),
                                 "c1_scale": np.ones(21),
                                 "fit_population_sha256": population})
                supported = preliminary.validity_mask[local] & take_fit
                if supported.any():
                    c1_parts.append(preliminary.values[local][supported][:,
                                    np.r_[0, np.arange(9, 29)]])
                base22 = materialize_probe_target(session.atlas, c22)
                valid22 = base22.validity_mask[local] & take_fit
                if valid22.any():
                    trajectory_parts.append(base22.values[local][valid22,
                                            :base22.output_width])
                for cell in (10, 24):
                    base = next(s for s in PROBE_REGISTRY if s.cell == cell
                                and _probe_variant(s) == 1)
                    target = materialize_probe_target(session.atlas, base)
                    local_target = _target_take(target, local[take_fit])
                    passage, censored = _competing_ipcw_observations(local_target)
                    censor_parts[cell].append((passage, censored))
            if not c1_parts or not trajectory_parts:
                raise RealDiagnosticExecutorRefusal("held fit context population is empty")
            c1 = np.concatenate(c1_parts); c1_loc = c1.mean(0); c1_scale = c1.std(0)
            c1_scale[c1_scale == 0] = 1.0
            trajectory = np.concatenate(trajectory_parts)
            loc = trajectory.mean(0); scale = trajectory.std(0); scale[scale == 0] = 1.0
            lower = np.quantile(trajectory, .01, axis=0)
            upper = np.quantile(trajectory, .99, axis=0)
            upper[lower >= upper] = lower[lower >= upper] + 1.0
            km = {}
            for cell, pieces in censor_parts.items():
                times = np.concatenate([x[0] for x in pieces]); event = np.concatenate(
                    [x[1] for x in pieces]).astype(bool)
                order = np.argsort(times, kind="stable"); times, event = times[order], event[order]
                survival = 1.0; table_t = []; table_s = []
                for timestamp in np.unique(times):
                    risk = int(np.sum(times >= timestamp)); d = int(np.sum(event[times == timestamp]))
                    survival *= 1.0 - d / risk
                    table_t.append(timestamp); table_s.append(max(.05, survival))
                km[cell] = (np.asarray(table_t), np.asarray(table_s))
            result = {}
            for probe in PROBE_REGISTRY:
                by_session = {}
                for session in self.stage.diagnostic_corpus.sessions:
                    context = None
                    variant = _probe_variant(probe)
                    if probe.cell == 1:
                        context = {"c1_location": c1_loc, "c1_scale": c1_scale,
                                   "fit_population_sha256": population}
                    elif probe.cell == 22 and variant in (2, 3, 4, 5, 6):
                        context = {"fit_population_sha256": population}
                        if variant == 2: context |= {"location": loc, "scale": scale}
                        elif variant == 3: context |= {"lower": lower, "upper": upper}
                        elif variant == 4: context |= {"rank_reference": trajectory}
                    elif ((probe.cell == 10 and variant == 4)
                          or (probe.cell == 24 and variant == 2)):
                        base = next(s for s in PROBE_REGISTRY if s.cell == probe.cell
                                    and _probe_variant(s) == 1)
                        target = materialize_probe_target(session.atlas, base)
                        tt, ss = km[probe.cell]
                        context = {"fit_population_sha256": population,
                                   "ipcw_weights": _competing_candidate_ipcw(
                                       target, tt, ss)}
                    by_session[session.key] = context
                result[probe.probe_id] = by_session
            return result

        restored_e1 = (getattr(self, "_restored_stage_payloads", {}).get("E1")
                       if cache_name == "_held_probe_plane" else None)
        if restored_e1 is None:
            contexts_e1 = contexts_for(pretext_fit_end)
        else:
            stored_contexts = json.loads(restored_e1["fit-contexts.json"])
            if stored_contexts.get("schema") != "entry-v2-e1-fit-contexts-v1":
                raise RealDiagnosticExecutorRefusal(
                    "restored E1 fit-context schema differs")
            contexts_e1 = {
                probe: {(key.split(":", 1)[0], int(key.split(":", 1)[1])): value
                        for key, value in by_session.items()}
                for probe, by_session in stored_contexts["contexts"].items()
            }
            if set(contexts_e1) != {spec.probe_id for spec in PROBE_REGISTRY}:
                raise RealDiagnosticExecutorRefusal(
                    "restored E1 fit-context registry differs")
        targets = {}
        for probe in PROBE_REGISTRY:
            pieces = []
            for spec in specs:
                session = observed[(spec.asset, spec.trading_day)]
                local_map = {cid: i for i, cid in enumerate(session.atlas.candidate_ids)}
                local = np.asarray([local_map[cid] for cid in spec.candidate_ids], np.int64)
                target = materialize_probe_target(
                    session.atlas, probe,
                    fit_context=contexts_e1[probe.probe_id][session.key])
                pieces.append(_target_take(target, local))
            targets[probe.probe_id] = _concat_targets(pieces)
        consumers = tuple(s.probe_id for s in PROBE_REGISTRY)
        if restored_e1 is None:
            pretext_stage = ("E1R" if pretext_fit_end
                             == _rehearsal_bounds("E1r", "FIT")[1] else "E1")
            pretexts = [fit_stage_pretext(
                pretext_stage, session_factory, CATEGORY_SIZES,
                next(s for s in PROBE_REGISTRY if s.probe_id == probe_id),
                targets[probe_id], fit_indices=fit_e1, consumer_probe_ids=consumers,
                device=self.device, encode_sessions=False)
                for probe_id in ("C01P01", "C02P01")]
        else:
            pretexts = []
            for probe_id in ("C01P01", "C02P01"):
                with np.load(io.BytesIO(restored_e1[
                        f"pretext/{probe_id}.checkpoint.npz"]),
                        allow_pickle=False) as archive:
                    metadata = tuple(map(str, archive["metadata"].tolist()))
                    checkpoint = StagePretextCheckpoint(
                        metadata[0], metadata[1], int(metadata[2]),
                        tuple(int(x) for x in archive["category_sizes"].tolist()),
                        np.array(archive["location"], copy=True),
                        np.array(archive["scale"], copy=True),
                        np.array(archive["constant_zero_mask"], copy=True),
                        MappingProxyType({key.removeprefix("state/"):
                            np.array(archive[key], copy=True) for key in archive.files
                            if key.startswith("state/")}),
                        metadata[3], metadata[4], metadata[5])
                if checkpoint.category_sizes != tuple(CATEGORY_SIZES):
                    raise RealDiagnosticExecutorRefusal(
                        "restored E1 pretext category schema differs")
                pretexts.append(SimpleNamespace(
                    checkpoint=checkpoint,
                    checkpoint_sha256=checkpoint.checkpoint_sha256,
                    objective_id=probe_id))
        encoded = [encode_stage_pretext(
            pretext.checkpoint, session_factory(), row_count=n, device=self.device)
            for pretext in pretexts]
        rows = ProbeRows(static, np.concatenate(
            [encoded[0].frozen_state, encoded[1].frozen_state], axis=1),
            assets, days, decisions, np.asarray(ids))
        plane = (specs, ids, rows, targets, contexts_e1, tuple(pretexts), fit_e1)
        setattr(self, cache_name, plane)
        if cache_name != "_held_probe_plane":
            # Rehearsal never replaces the production held plane/factory.
            self._rehearsal_context_factory = contexts_for
        else:
            self._held_context_factory = contexts_for
        return plane

    def _fit_e1_probe_funnel(self, score: np.ndarray, *, ids: np.ndarray,
                             assets: np.ndarray, days: np.ndarray,
                             recipient: np.ndarray) -> tuple[Any, str, str]:
        """Fit May-Sep, calibrate/select in Oct, replay only Nov-Dec."""
        from .atlas_probe_model import FrozenLogisticBindingMapper
        bindings, _ = self._binding_indexes()
        action = np.asarray([bindings[str(cid)].action_target for cid in ids], np.int8)
        features = np.repeat(np.asarray(score, np.float64)[:, None], 128, axis=1)
        fit = (days <= 20210930) & recipient
        denominator = self.stage.corpus_stage.corpus.replay
        october_days = sorted({session.trading_day for session in
            denominator.expected_sessions
            if 20211001 <= session.trading_day <= 20211029})
        if len(october_days) != 21:
            raise RealDiagnosticExecutorRefusal(
                "E1 A-013 requires exactly 21 eligible October trading days")
        calibration_day_set = set(october_days[:7])
        threshold_day_set = set(october_days[7:])
        calibration = np.isin(days, list(calibration_day_set)) & recipient
        threshold_rows = np.isin(days, list(threshold_day_set))
        held = (days >= 20211101) & (days <= 20211231)
        action_weights, action_weight_receipt = action_fit_weights(
            assets, days, action, recipient, fit)
        mapper = FrozenLogisticBindingMapper().fit(
            features, action, fit, ids, sample_weight=action_weights,
            weight_receipt_sha256=action_weight_receipt.receipt_sha256)
        mapper.calibrate(features[calibration], action[calibration], ids[calibration],
                         threshold_selection_ids=ids[threshold_rows])
        probability, _ = mapper.predict(features)
        examples = {item.candidate_id: item for spec in
                    self.stage.corpus_stage.corpus.sessions for item in spec.examples}
        outcomes = self.stage.corpus_stage.corpus.replay.outcomes
        arrivals = tuple(ScoredArrival(
            examples[str(cid)], EntryScore(str(cid), str(asset),
                examples[str(cid)].decision_ts_ns, "held-e1-probe", float(p), float(p),
                0.0, 0.0, float(p), 0.0, 0.0, False), outcomes[str(cid)])
            for cid, asset, p in zip(ids, assets, probability))
        thresholds = {}; parity = {}; availability = {}
        for asset in C.ASSETS:
            local = np.flatnonzero(threshold_rows & (assets == asset))
            sessions = denominator.sessions_for(sorted(threshold_day_set), asset=asset)
            sweep = fast_threshold_sweep(tuple(arrivals[i] for i in local),
                                         probability[local], sessions)
            parity[asset] = assert_fast_sweep_parity(
                tuple(arrivals[i] for i in local), probability[local], sessions,
                sweep, samples=len(sweep.thresholds))
            eligibility_days = len({s.trading_day for s in sessions})
            feasibility = tuple(threshold_feasibility(
                trades=int(sweep.trades[i]),
                usd_per_trade=float(sweep.usd_per_trade[i]),
                max_drawdown_usd=float(sweep.max_drawdown_usd[i]),
                days_with_trades=int(sweep.days_with_trades[i]),
                eligible_days=eligibility_days)
                for i in range(len(sweep.thresholds)))
            feasible = np.asarray([row.feasible for row in feasibility], bool)
            choices = np.flatnonzero(feasible)
            if not len(choices):
                thresholds[asset] = float(sweep.thresholds[-1])
                availability[asset] = "NO_FEASIBLE_THRESHOLD"
            else:
                chosen = max(choices, key=lambda i: (
                    float(sweep.usd_per_asset_day[i]), float(sweep.usd_per_trade[i]),
                    -float(sweep.max_drawdown_usd[i]), -float(sweep.drawdown_p90_usd[i]),
                    float(sweep.thresholds[i]), int(sweep.trades[i])))
                thresholds[asset] = float(sweep.thresholds[chosen])
                availability[asset] = "MATERIALIZED"
        scored = tuple(ScoredArrival(row.example, replace(
            row.score, enter=row.score.take_probability >= thresholds[row.example.asset]),
            row.outcome) for row in arrivals)
        held_days = sorted({session.trading_day for session in
            denominator.expected_sessions
            if 20211101 <= session.trading_day <= 20211231})
        evaluation = replay((scored[i] for i in np.flatnonzero(held)),
                            expected_sessions=denominator.sessions_for(held_days))
        receipt = _sha({"fit_ids": ids[fit].tolist(),
                        "calibration_days": sorted(calibration_day_set),
                        "threshold_development_days": sorted(threshold_day_set),
                        "october_inner_split_law":
                            "A-013-first-7-Platt-remaining-14-threshold-v1",
                        "calibration_ids": ids[calibration].tolist(),
                        "threshold_ids": ids[threshold_rows].tolist(),
                        "held_ids": ids[held].tolist(), "thresholds": thresholds,
                        "availability": availability, "parity": parity,
                        "action_fit_weight_receipt_sha256":
                            action_weight_receipt.receipt_sha256,
                        "recipient": _sha_bytes(recipient.tobytes())})
        path_availability = ("MATERIALIZED" if all(
            value == "MATERIALIZED" for value in availability.values())
            else "UNAVAILABLE_NO_FEASIBLE_THRESHOLD")
        return evaluation, receipt, path_availability

    def produce_measured_held_inputs(self) -> None:
        """Run the concrete E1 screen from the live one-open corpus.

        E2/E3 measurements are produced after E1 freezes its finalists by the
        same stage engine; no caller-supplied measurement object is accepted.
        """
        from .atlas_losses import loss_for_probe
        from .atlas_statistics import PairedObservationRecord
        from .neural_sufficiency_stage_engine import (
            ExactHeldStageEngine, MeasuredProbeScreen, ProbeSupportInputs,
        )
        if self._held_engine is not None:
            raise RealDiagnosticExecutorRefusal("held producer already ran")
        specs, ids, rows, targets, _contexts, _pretexts, fit_idx = \
            self._build_held_probe_plane()
        days = np.asarray(rows.day, np.int64); assets = np.asarray(rows.asset, str)
        e1_october_days = tuple(sorted({session.trading_day for session in
            self.stage.corpus_stage.corpus.replay.expected_sessions
            if 20211001 <= session.trading_day <= 20211029}))
        if len(e1_october_days) != 21:
            raise RealDiagnosticExecutorRefusal(
                "E1 producer lacks the exact 7+14 October roster")
        e1_platt_days = e1_october_days[:7]
        held = np.flatnonzero((days >= 20211101) & (days <= 20211231))
        if not len(held):
            raise RealDiagnosticExecutorRefusal("E1 held-forward rows are empty")
        binding_index, _ = self._binding_indexes()
        recipient = np.asarray([binding_index[cid].action_loss_mask for cid in ids], bool)
        fit_row_mask = np.zeros(len(days), bool); fit_row_mask[fit_idx] = True
        permutation = stage_global_recipient_fixed_permutation(
            np.where(days <= 20210930, "FIT", np.where(days <= 20211029, "CAL", "HELD")),
            assets, days, recipient, seed=20260816)
        torch.manual_seed(20260816); initialization = AtlasProbeNet()
        screens = []
        shared_plane = SharedProbePlane.build(rows, fit_idx, stage_id="E1")
        self._held_probe_fit_receipts = {}
        for probe in PROBE_REGISTRY:
            target = targets[probe.probe_id]
            support, additional_support = _e1_fit_support_inputs(
                probe, target, rows, fit_idx)
            support_decisions = tuple(x.measure() for x in (support, *additional_support))
            availability = (target.state if target.state != CellAvailability.MATERIALIZED
                            else (CellAvailability.MATERIALIZED
                                  if all(x.available for x in support_decisions)
                                  else CellAvailability.UNAVAILABLE_LOW_SUPPORT))
            if availability is not CellAvailability.MATERIALIZED:
                vector = _probe_fingerprint(target, fit_row_mask, recipient)
                screens.append(MeasuredProbeScreen(
                    probe.probe_id, f"cell-{probe.cell:02d}", "SHARED_PRETEXT",
                    "shallow_probe", (), support, vector, "0" * 64, "0" * 64,
                    _sha({"ids": np.asarray(ids)[days <= 20211231].tolist(),
                          "stage": "E1"}),
                    e1_platt_days,
                    MappingProxyType({}), additional_support, availability))
                continue
            twin = permute_probe_target_recipient_fixed(target, permutation)
            real = fit_probe(probe, rows, target, fit_indices=fit_idx,
                             initialization=initialization, stage_id="E1",
                             shared_plane=shared_plane, device=self.device)
            twin_spec = shuffled_probe_for(
                probe,
                available=self.stage.diagnostic_corpus.sessions[0].atlas.shuffled_probes,
            )
            twin = replace(twin, probe_id=twin_spec.probe_id,
                schema_sha256=probe_target_schema_sha256(
                    twin_spec.probe_id, twin.output_width, twin.output_layout,
                    twin.direction, twin.transform_provenance_sha256,
                    twin.prediction_width, twin.prediction_layout))
            shuffled = fit_probe(twin_spec, rows, twin, fit_indices=fit_idx,
                                 initialization=initialization, stage_id="E1",
                                 shared_plane=shared_plane, device=self.device)
            self._held_probe_fit_receipts[probe.probe_id] = (
                real.best_checkpoint_sha256, shuffled.best_checkpoint_sha256)
            x_real = torch.from_numpy(shared_plane.normalized)
            x_twin = x_real
            with torch.no_grad():
                prediction_real = real.model(x_real).cpu()
                prediction_twin = shuffled.model(x_twin).cpu()
            real_evaluation, real_funnel, real_path_availability = self._fit_e1_probe_funnel(
                action_score_for_probe(probe, prediction_real, target).numpy(),
                ids=np.asarray(ids), assets=assets, days=days, recipient=recipient)
            twin_evaluation, twin_funnel, twin_path_availability = self._fit_e1_probe_funnel(
                action_score_for_probe(twin_spec, prediction_twin, twin).numpy(),
                ids=np.asarray(ids), assets=assets, days=days, recipient=recipient)
            real_day = {(row.asset, row.trading_day): row.pnl_usd
                        for row in real_evaluation.asset_day_results}
            twin_day = {(row.asset, row.trading_day): row.pnl_usd
                        for row in twin_evaluation.asset_day_results}
            authorized = days <= 20211231
            real_target_hash = _sha({
                "candidate_ids": np.asarray(ids)[authorized].tolist(),
                "schema": target.schema_sha256,
                "values": _sha_bytes(np.ascontiguousarray(
                    target.values[authorized]).tobytes()),
                "valid": _sha_bytes(np.ascontiguousarray(
                    target.validity_mask[authorized]).tobytes())})
            twin_target_hash = _sha({
                "candidate_ids": np.asarray(ids)[authorized].tolist(),
                "schema": twin.schema_sha256,
                "values": _sha_bytes(np.ascontiguousarray(
                    twin.values[authorized]).tobytes()),
                "valid": _sha_bytes(np.ascontiguousarray(
                    twin.validity_mask[authorized]).tobytes())})
            records = []
            calendar = tuple(session for session in
                self.stage.corpus_stage.corpus.replay.expected_sessions
                if 20211101 <= session.trading_day <= 20211231)
            calendar_keys = sorted({(session.asset, session.trading_day)
                                    for session in calendar})
            expected_keys = {(asset, day) for asset in C.ASSETS
                for day in {session.trading_day for session in calendar}
                if C.is_denominator_day(asset, day)}
            if set(calendar_keys) != expected_keys:
                raise RealDiagnosticExecutorRefusal(
                    "E1 paired roster differs from QRE2CAL1 denominator")
            for asset, day in calendar_keys:
                records.append(PairedObservationRecord(
                        f"CALENDAR:{asset}:{day}", asset, str(day), True,
                        real_target_hash, twin_target_hash,
                        float(real_day.get((asset, day), 0.0)),
                        float(twin_day.get((asset, day), 0.0))))
            vector = _probe_fingerprint(target, fit_row_mask, recipient)
            screens.append(MeasuredProbeScreen(
                probe.probe_id, f"cell-{probe.cell:02d}",
                "SHARED_PRETEXT", "shallow_probe",
                tuple(records), support, vector, real.best_checkpoint_sha256,
                shuffled.best_checkpoint_sha256,
                _sha({"ids": np.asarray(ids)[days <= 20211231].tolist(),
                      "stage": "E1"}),
                e1_platt_days,
                MappingProxyType({"real_funnel": real_funnel,
                                  "twin_funnel": twin_funnel}),
                additional_support, "MATERIALIZED",
                # A real path must transport through calibration/threshold/replay
                # on every asset.  The recipient-fixed null is allowed to have
                # no feasible threshold: its exact sentinel threshold and
                # zero-entry replay are the measured null result, not missing
                # evidence.  Requiring the shuffled learner itself to trade
                # would systematically discard the strongest separations.
                ("MATERIALIZED" if real_path_availability == "MATERIALIZED"
                 and twin_path_availability in {
                     "MATERIALIZED", "UNAVAILABLE_NO_FEASIBLE_THRESHOLD"}
                 else "UNAVAILABLE_NO_FEASIBLE_THRESHOLD")))
            del real, shuffled, prediction_real, prediction_twin, x_real, x_twin
        if not screens:
            raise RealDiagnosticExecutorRefusal("E1 producer fitted no supported probes")
        self._held_engine = ExactHeldStageEngine(self.run_root / "held-stage")
        self._held_screens = tuple(screens)

    def _materialize_held_targets(self, probe_ids: Sequence[str], fit_end: int):
        specs, _ids, _rows, _targets, _contexts, _pretexts, _fit = \
            self._build_held_probe_plane()
        observed = {session.key: session for session in self.stage.diagnostic_corpus.sessions}
        contexts = self._held_context_factory(fit_end)
        result = {}
        for probe_id in probe_ids:
            probe = next(s for s in PROBE_REGISTRY if s.probe_id == probe_id)
            pieces = []
            for spec in specs:
                session = observed[(spec.asset, spec.trading_day)]
                local_map = {cid: i for i, cid in enumerate(session.atlas.candidate_ids)}
                local = np.asarray([local_map[cid] for cid in spec.candidate_ids], np.int64)
                target = materialize_probe_target(
                    session.atlas, probe, fit_context=contexts[probe_id][session.key])
                pieces.append(_target_take(target, local))
            result[probe_id] = _concat_targets(pieces)
        return result

    def _freeze_e2_objective(self, oracle_eval: Any) -> str:
        """Refit <=4 real/twins, then freeze one objective before arm training."""
        if self._held_engine is None or self._held_engine.e1 is None:
            raise RealDiagnosticExecutorRefusal("E2 objective freeze requires E1 finalists")
        specs, ids_tuple, rows, _targets, _contexts, _pretexts, _ = \
            self._build_held_probe_plane()
        ids = np.asarray(ids_tuple); days = np.asarray(rows.day, np.int64)
        assets = np.asarray(rows.asset, str); fit_idx = np.flatnonzero(days <= 20220311)
        targets = self._materialize_held_targets(self._held_engine.e1.finalists, 20220311)
        binding, _ = self._binding_indexes()
        recipient = np.asarray([binding[str(cid)].action_loss_mask for cid in ids], bool)
        action = np.asarray([binding[str(cid)].action_target for cid in ids], np.int8)
        split = np.where(days <= 20220311, "FIT", np.where(
            days <= 20220427, "PLATT", np.where(days <= 20220609,
            "THRESHOLD", np.where(days <= 20220630, "SELECTION", "HELD"))))
        permutation = stage_global_recipient_fixed_permutation(
            split, assets, days, recipient, seed=20260816)
        plane = SharedProbePlane.build(rows, fit_idx, stage_id="E2")
        torch.manual_seed(20260816); initialization = AtlasProbeNet()
        selection_days = tuple(sorted({session.trading_day for session in
            self.stage.corpus_stage.corpus.replay.expected_sessions
            if 20220610 <= session.trading_day <= 20220630}))
        oracle_day = {(row.asset, row.trading_day): row.pnl_usd
                      for row in oracle_eval.asset_day_results}
        hypotheses = []; effect_columns = []; capture_columns = []; hypothesis_assets = []
        receipts = {}
        for probe_id in self._held_engine.e1.finalists:
            objective_started = time.perf_counter()
            probe = next(x for x in PROBE_REGISTRY if x.probe_id == probe_id)
            target = targets[probe_id]
            twin = permute_probe_target_recipient_fixed(target, permutation)
            twin_spec = shuffled_probe_for(
                probe,
                available=self.stage.diagnostic_corpus.sessions[0].atlas.shuffled_probes)
            twin = replace(twin, probe_id=twin_spec.probe_id,
                schema_sha256=probe_target_schema_sha256(
                    twin_spec.probe_id, twin.output_width, twin.output_layout,
                    twin.direction, twin.transform_provenance_sha256,
                    twin.prediction_width, twin.prediction_layout))
            real = fit_probe(probe, rows, target, fit_indices=fit_idx,
                initialization=initialization, stage_id="E2", shared_plane=plane,
                device=self.device)
            shuffled = fit_probe(twin_spec, rows, twin, fit_indices=fit_idx,
                initialization=initialization, stage_id="E2", shared_plane=plane,
                device=self.device)
            with torch.no_grad():
                normalized = torch.from_numpy(plane.normalized)
                rp = real.model(normalized).cpu()
                tp = shuffled.model(normalized).cpu()
            real_score = action_score_for_probe(probe, rp, target).numpy()
            twin_score = action_score_for_probe(twin_spec, tp, twin).numpy()
            _, _, real_eval, _, real_receipt = self._fit_policy_branch(
                np.repeat(real_score[:, None], 128, axis=1),
                decision_kind="direct_neural", ids=ids, assets=assets, days=days,
                targets=action)
            real_availability = dict(self._last_policy_availability)
            _, _, twin_eval, _, twin_receipt = self._fit_policy_branch(
                np.repeat(twin_score[:, None], 128, axis=1),
                decision_kind="direct_neural", ids=ids, assets=assets, days=days,
                targets=action)
            twin_availability = dict(self._last_policy_availability)
            real_day = {(row.asset, row.trading_day): row.pnl_usd
                        for row in real_eval.asset_day_results}
            twin_day = {(row.asset, row.trading_day): row.pnl_usd
                        for row in twin_eval.asset_day_results}
            for asset in C.ASSETS:
                hypotheses.append((probe_id, asset)); hypothesis_assets.append(asset)
                dollar = np.asarray([
                    real_day.get((asset, day), 0.0) - twin_day.get((asset, day), 0.0)
                    for day in selection_days], np.float64)
                effect_columns.append(dollar)
                capture_columns.append(np.asarray([
                    dollar[i] / max(1.0, abs(oracle_day.get((asset, day), 0.0)))
                    for i, day in enumerate(selection_days)], np.float64))
            real_by_asset = {row.asset: row for row in real_eval.by_asset}
            receipts[probe_id] = {"real_checkpoint": real.best_checkpoint_sha256,
                "twin_checkpoint": shuffled.best_checkpoint_sha256,
                "real_funnel": real_receipt, "twin_funnel": twin_receipt,
                "oracle_days": _sha(sorted((asset, int(day), float(value))
                                             for (asset, day), value in oracle_day.items())),
                "mean_usd_per_day": float(np.mean([
                    real_by_asset[a].usd_per_asset_day for a in C.ASSETS])),
                "worst_mdd": float(max(real_by_asset[a].max_drawdown_usd
                                        for a in C.ASSETS)),
                "parameter_count": sum(p.numel() for p in real.model.parameters()),
                "real_availability": real_availability,
                "twin_availability": twin_availability}
            self._held_objective_runtime = getattr(
                self, "_held_objective_runtime", {})
            self._held_objective_runtime[probe_id] = time.perf_counter() - objective_started
            del real, shuffled, rp, tp, normalized
        rw = romano_wolf_lower_bounds(np.stack(effect_columns, axis=1),
            hypothesis_ids=[f"{p}:{a}" for p, a in hypotheses],
            hypothesis_assets=hypothesis_assets,
            hypothesis_families=[p for p, _a in hypotheses])
        capture_rw = romano_wolf_lower_bounds(np.stack(capture_columns, axis=1),
            hypothesis_ids=[f"{p}:{a}:capture" for p, a in hypotheses],
            hypothesis_assets=hypothesis_assets,
            hypothesis_families=[p for p, _a in hypotheses])
        eligible = []
        for index, probe_id in enumerate(self._held_engine.e1.finalists):
            lower = tuple(float(x) for x in rw.simultaneous_lower_bounds[
                index * len(C.ASSETS):(index + 1) * len(C.ASSETS)])
            capture_lower = tuple(float(x) for x in capture_rw.simultaneous_lower_bounds[
                index * len(C.ASSETS):(index + 1) * len(C.ASSETS)])
            metric = receipts[probe_id]
            # Romano-Wolf already gives deterministic zero-variance columns
            # their exact lower bound.  A deterministic positive effect is
            # evidence, while a deterministic nonpositive effect has a
            # nonpositive bound and fails below; neither may be dropped from
            # the registered family or rejected merely for having zero SE.
            if (min(lower) > 0 and min(capture_lower) > 0
                    and all(value == "ELIGIBLE" for value in
                            metric["real_availability"].values())):
                eligible.append(((min(lower), min(capture_lower),
                    metric["mean_usd_per_day"], -metric["worst_mdd"],
                    -metric["parameter_count"]), probe_id))
        if not eligible:
            raise RealDiagnosticExecutorRefusal(
                "E2 objective freeze has no all-asset real-beyond-twin survivor")
        best_objective_key = max(item[0] for item in eligible)
        winner = min(item[1] for item in eligible if item[0] == best_objective_key)
        self._held_objective_e2_evidence = MappingProxyType(dict(receipts[winner]))
        self._held_objective_freeze_receipt = _sha({
            "schema": "entry-v2-e2-objective-freeze-v1", "winner": winner,
            "romano_wolf": rw.receipt_sha256,
            "capture_romano_wolf": capture_rw.receipt_sha256,
            "selection_key": "min-dollar-lb,min-capture-lb,mean-dollar,-mdd,-params,probe-id",
            "fit_count": 2 * len(receipts),
            "receipts": {key: _sha(value) for key, value in receipts.items()},
            "selection_days": selection_days})
        return winner

    def _fit_policy_branch(self, features: np.ndarray, *, decision_kind: str,
                           ids: np.ndarray, assets: np.ndarray, days: np.ndarray,
                           targets: np.ndarray,
                           direct_probability: np.ndarray | None = None,
                           diagnostic_scores: Mapping[str, np.ndarray] | None = None,
                           pair_group_ids: np.ndarray | None = None,
                           expected_pair_manifest_by_asset: Mapping[str, str] | None = None):
        from .atlas_probe_model import FrozenLogisticBindingMapper
        from .policy import PolicyConfig, policy_risk_gate, predicted_mae_limit_usd
        from .train import ThresholdFunnel, ThresholdSelection
        bindings, _ = self._binding_indexes()
        recipient = np.asarray([bindings[str(cid)].action_loss_mask for cid in ids], bool)
        fit = (days <= 20220311) & recipient
        development_days = sorted({session.trading_day for session in
            self.stage.corpus_stage.corpus.replay.expected_sessions
            if 20220314 <= session.trading_day <= 20220609})
        platt_days = tuple(day for day in development_days if day <= 20220427)
        threshold_days = tuple(day for day in development_days if day >= 20220428)
        if (not platt_days or not threshold_days
                or set(platt_days) & set(threshold_days)):
            raise RealDiagnosticExecutorRefusal(
                "E2 A-013 development chronology is unavailable")
        calibration = np.isin(days, platt_days) & recipient
        threshold_development = np.isin(days, threshold_days)
        selection = (days >= 20220610) & (days <= 20220630)
        if decision_kind == "catboost":
            groups = np.asarray(pair_group_ids, str) if pair_group_ids is not None else None
            if groups is None or groups.shape != (len(ids),):
                raise RealDiagnosticExecutorRefusal(
                    "CatBoost policy requires the frozen neural phase-pair manifest")
            rows = FrozenRepresentationRows(
                np.asarray(features, np.float32), ids, assets, days,
                np.asarray([bindings[cid].decision_ts_ns for cid in ids], np.int64),
                targets.astype(np.int8), np.asarray([bindings[cid].action_loss_mask
                    for cid in ids], bool), groups,
                np.full(len(ids), "DERIVED"), "E2",
                eligible_development_days=tuple((*platt_days, *threshold_days)),
                group_semantics="PHASE")
            cat = fit_diagnostic_catboost(
                rows, expected_representation_sha256=rows.representation_sha256)
            actual_pair_manifests = {asset:
                cat.assets[asset].pair_manifest.receipt_sha256 for asset in C.ASSETS}
            if (expected_pair_manifest_by_asset is None
                    or dict(expected_pair_manifest_by_asset) != actual_pair_manifests):
                raise RealDiagnosticExecutorRefusal(
                    "CatBoost policy changed the frozen neural phase-pair manifest")
            self._last_catboost_fit = cat
            rank = np.asarray(cat.rank_score, np.float64)
            unavailable_ranker = {asset for asset in C.ASSETS
                if cat.assets[asset].ranker_availability.value != "MATERIALIZED"}
            if unavailable_ranker:
                # Complete the typed-ineligible funnel without substituting
                # classifier probabilities for the declared PairLogit head.
                rank = np.zeros(len(ids), np.float64)
            mapper_features = _decision_binding(expit(rank))
            decision_receipt = _sha({"catboost": cat.receipt_sha256,
                "pair_manifests": {a: cat.assets[a].pair_manifest.receipt_sha256
                                   for a in C.ASSETS},
                "decision_head": "PairLogit", "unavailable": sorted(unavailable_ranker)})
        else:
            unavailable_ranker = set()
            if direct_probability is None:
                if np.asarray(features).shape[1] != 128:
                    raise RealDiagnosticExecutorRefusal(
                        "direct neural policy requires measured shared-head probability")
                direct_probability = np.asarray(features, np.float64)[:, 0]
            direct_probability = np.asarray(direct_probability, np.float64)
            if direct_probability.shape != (len(ids),) or np.any(
                    ~np.isfinite(direct_probability)):
                raise RealDiagnosticExecutorRefusal("direct probability is misaligned")
            mapper_features = np.repeat(direct_probability[:, None], 128, axis=1)
            decision_receipt = _sha_bytes(direct_probability.tobytes())
        fit_indices = np.flatnonzero(fit)
        fit_indices = fit_indices[np.lexsort((ids[fit_indices],
            np.asarray([bindings[str(cid)].decision_ts_ns for cid in ids], np.int64)[fit_indices],
            days[fit_indices], assets[fit_indices]))]
        local_action_weights, action_weight_receipt = action_fit_weights(
            assets[fit_indices], days[fit_indices], targets[fit_indices],
            recipient[fit_indices], np.ones(len(fit_indices), bool))
        action_weights = np.zeros(len(ids), np.float32)
        action_weights[fit_indices] = local_action_weights
        mapper = FrozenLogisticBindingMapper().fit(
            mapper_features, targets, fit, ids,
            sample_weight=action_weights,
            weight_receipt_sha256=action_weight_receipt.receipt_sha256)
        mapper.calibrate(mapper_features[calibration], targets[calibration], ids[calibration],
                         threshold_selection_ids=ids[threshold_development])
        probability, _ = mapper.predict(mapper_features)
        examples = {item.candidate_id: item for spec in
                    self.stage.corpus_stage.corpus.sessions for item in spec.examples}
        outcomes = self.stage.corpus_stage.corpus.replay.outcomes
        arrivals = []
        for cid, p in zip(ids, probability):
            item = examples[cid]
            score = EntryScore(cid, item.asset, item.decision_ts_ns,
                f"held-{decision_kind}", float(p), float(p), 0.0, 0.0,
                float(p), 0.0, 0.0, False)
            arrivals.append(ScoredArrival(item, score, outcomes[cid]))
        thresholds = {}; parity = {}; availability = {}; funnel_receipts = {}
        selections = {}
        if diagnostic_scores is not None:
            required_diagnostics = {
                "top3_p", "wall_p_upper", "expected_value_raw",
                "expected_value_lower", "expected_value_upper", "mae_q90",
            }
            if (set(diagnostic_scores) != required_diagnostics
                    or any(np.asarray(value).shape != (len(ids),)
                           or not np.all(np.isfinite(value))
                           for value in diagnostic_scores.values())):
                raise RealDiagnosticExecutorRefusal(
                    "policy diagnostic score surface is incomplete or misaligned")
        selection_days = sorted({session.trading_day for session in
            self.stage.corpus_stage.corpus.replay.expected_sessions
            if 20220610 <= session.trading_day <= 20220630})
        for asset in C.ASSETS:
            local = np.flatnonzero(threshold_development & (assets == asset))
            local_arrivals = tuple(arrivals[i] for i in local)
            sessions = self.stage.corpus_stage.corpus.replay.sessions_for(
                threshold_days, asset=asset)
            sweep = fast_threshold_sweep(local_arrivals, probability[local], sessions)
            parity[asset] = assert_fast_sweep_parity(
                local_arrivals, probability[local], sessions, sweep,
                samples=len(sweep.thresholds))
            eligibility_days = len({s.trading_day for s in sessions})
            feasibility = tuple(threshold_feasibility(
                trades=int(sweep.trades[i]),
                usd_per_trade=float(sweep.usd_per_trade[i]),
                max_drawdown_usd=float(sweep.max_drawdown_usd[i]),
                days_with_trades=int(sweep.days_with_trades[i]),
                eligible_days=eligibility_days)
                for i in range(len(sweep.thresholds)))
            feasible = np.asarray([row.feasible for row in feasibility], bool)
            if asset in unavailable_ranker:
                feasible[:] = False
            choices = np.flatnonzero(feasible)
            chosen = None
            if not len(choices):
                thresholds[asset] = 1.0
                availability[asset] = ("UNAVAILABLE_PAIRLOGIT_SUPPORT"
                    if asset in unavailable_ranker else "NO_FEASIBLE_THRESHOLD")
            else:
                chosen = max(choices, key=lambda i: (float(sweep.usd_per_asset_day[i]),
                    float(sweep.usd_per_trade[i]), -float(sweep.max_drawdown_usd[i]),
                    -float(sweep.drawdown_p90_usd[i]), float(sweep.thresholds[i]),
                    int(sweep.trades[i])))
                thresholds[asset] = float(sweep.thresholds[chosen])
                availability[asset] = "ELIGIBLE"
            if diagnostic_scores is not None:
                lower = np.asarray(
                    diagnostic_scores["expected_value_lower"], np.float64)[local]
                mae = np.maximum(0.0, np.asarray(
                    diagnostic_scores["mae_q90"], np.float64)[local])
                wall = np.asarray(
                    diagnostic_scores["wall_p_upper"], np.float64)[local]
                value_pass = int(np.count_nonzero(lower >= C.MIN_EXPECTANCY_USD))
                mae_pass = int(np.count_nonzero(
                    mae <= predicted_mae_limit_usd(lower)))
                wall_pass = int(np.count_nonzero(
                    wall <= PolicyConfig().wall_probability_upper_max))
                intersection_pass = int(np.count_nonzero(
                    policy_risk_gate(lower, mae, wall)))
                funnels = []
                for index, threshold in enumerate(sweep.thresholds):
                    reasons = []
                    reasons.extend(feasibility[index].reasons)
                    reason = "FEASIBLE" if not reasons else "+".join(reasons)
                    funnels.append(ThresholdFunnel(
                        threshold=float(threshold),
                        candidate_count=len(local),
                        action_pass=int(sweep.action_pass[index]),
                        diagnostic_value_pass=value_pass,
                        diagnostic_mae_pass=mae_pass,
                        diagnostic_wall_pass=wall_pass,
                        diagnostic_intersection_pass=intersection_pass,
                        replay_trades=int(sweep.trades[index]),
                        replay_total_pnl_usd=float(sweep.total_pnl_usd[index]),
                        replay_usd_per_trade=float(sweep.usd_per_trade[index]),
                        replay_usd_per_asset_day=float(
                            sweep.usd_per_asset_day[index]),
                        replay_chronological_mdd_usd=float(
                            sweep.max_drawdown_usd[index]),
                        feasible=reason == "FEASIBLE",
                        reason=reason,
                    ))
                asset_days = len({session.trading_day for session in sessions})
                if chosen is None:
                    selections[asset] = ThresholdSelection(
                        asset, thresholds[asset], asset_days, 0.0, 0.0,
                        0.0, 0.0, 0, 0, tuple(funnels))
                else:
                    selections[asset] = ThresholdSelection(
                        asset, thresholds[asset], asset_days,
                        float(sweep.usd_per_asset_day[chosen]),
                        float(sweep.usd_per_trade[chosen]),
                        float(sweep.max_drawdown_usd[chosen]),
                        float(sweep.drawdown_p90_usd[chosen]),
                        int(sweep.trades[chosen]), int(np.count_nonzero(feasible)),
                        tuple(funnels))
            funnel_receipts[asset] = _sha({"sweep": sweep.receipt_sha256,
                "parity": parity[asset], "status": availability[asset],
                "threshold": thresholds[asset]})
        scored = tuple(ScoredArrival(row.example, replace(row.score,
            enter=(availability[row.example.asset] == "ELIGIBLE" and
                   row.score.take_probability >= thresholds[row.example.asset])), row.outcome)
            for row in arrivals)
        denominator = self.stage.corpus_stage.corpus.replay.sessions_for(selection_days)
        evaluation = replay((scored[i] for i in np.flatnonzero(selection)),
                            expected_sessions=denominator)
        self._last_policy_availability = MappingProxyType(availability)
        if unavailable_ranker:
            self._last_policy_availability = MappingProxyType({asset:
                ("UNAVAILABLE_PAIRLOGIT_SUPPORT" if asset in unavailable_ranker
                 else availability[asset]) for asset in C.ASSETS})
        self._last_policy_funnel_receipts = MappingProxyType(funnel_receipts)
        self._last_policy_selections = (None if diagnostic_scores is None else
            MappingProxyType(dict(selections)))
        self._last_policy_raw_probability = np.asarray(
            mapper_features[:, 0], np.float64).copy()
        return mapper, thresholds, evaluation, probability, _sha({
            "decision": decision_receipt, "parity": parity,
            "recipient_mask": _sha_bytes(recipient.tobytes()),
            "action_fit_weight_receipt_sha256":
                action_weight_receipt.receipt_sha256,
            "fit_ids": ids[fit].tolist(), "calibration_ids": ids[calibration].tolist(),
            "threshold_development_ids": ids[threshold_development].tolist(),
            "platt_days": platt_days, "threshold_development_days": threshold_days,
            "selection_days": selection_days,
            "mapper": mapper.parameter_sha256,
            "calibrator": mapper.calibrator.parameter_sha256,
            "thresholds": thresholds})

    def _winner_model_payloads(self, arm: str, decision_kind: str, objective_head,
                               objective_payload: bytes, mapper_payload: bytes,
                               calibrator_payload: bytes, thresholds_payload: bytes,
                               capacity_payload: bytes, target_manifest_sha256: str
                               ) -> Mapping[str, bytes]:
        from safetensors.torch import save
        model = self._held_models[arm]
        encoder_bytes = save({name: value.detach().cpu().contiguous()
                              for name, value in model.encoder.state_dict().items()})
        head_bytes = save({name: value.detach().cpu().contiguous()
                           for name, value in model.head.state_dict().items()})
        objective_bytes = save({f"projection.{name}": value.detach().cpu().contiguous()
                                for name, value in objective_head.state_dict().items()})
        architecture = {
            "event_continuous_fields": list(self.schema.continuous_fields),
            "event_categorical_fields": list(self.schema.categorical_fields),
            "event_category_sizes": list(self.schema.category_sizes),
            "conversion_law_sha256": self.schema.conversion_law_sha256,
            "candidate_features": int(self.batches[0].candidate_features.shape[1]),
            "context_continuous": CONTEXT_TENSOR_WIDTH,
            "context_types": len(CONTEXT_TYPE_ID),
            "static_bypass": arm in ("L1", "M1"),
            "n_value_bins": 5, "n_phases": int(model.head.n_phases),
            "decision_head_kind": decision_kind,
            "shared_head_initial_sha256": _sha_bytes(
                model.shared_head_initial_bytes),
            "no_parameter_alias_receipt_sha256": _sha({
                "encoder": [name for name, _ in model.encoder.named_parameters()],
                "head": [name for name, _ in model.head.named_parameters()]}),
            "branch_identity_receipt_sha256": _sha({
                "arm": arm, "encoder": _sha_bytes(encoder_bytes),
                "head": _sha_bytes(head_bytes)}),
            "input_contract_sha256":
                self.expanded_transform.input_contract_sha256,
            "expanded_schema_sha256": self.expanded_transform.schema_sha256,
            "expanded_transform_law_sha256": self.expanded_transform.transform_law_sha256,
            "expanded_transform_output": "UNNORMALIZED_CANONICAL",
            "branch_parameters_nonaliased": True,
            "shared_head_initial_identity": True,
            "grouped_checkpoint_sha256": _sha_bytes(encoder_bytes),
            "selected_horizon_coordinates": list(SELECTED_HORIZON_COORDINATES),
            "selected_horizon_schema_sha256": SELECTED_HORIZON_SCHEMA_SHA256,
            "selected_horizon_target_law_sha256":
                SELECTED_HORIZON_TARGET_LAW_SHA256,
            "selected_horizon_normalizer_sha256":
                self._held_horizon_normalizer["receipt_sha256"],
            "selected_output_schema_sha256": model.head.output_schema_sha256,
            "ordinal_semantics": "P(value_bin>=1..4)",
        }
        architecture.update({
            "current_pointwise_checkpoint_sha256": self._held_pointwise_hashes["C0"],
            "c0_pointwise_checkpoint_sha256": self._held_pointwise_hashes["C0"],
            "c1_pointwise_checkpoint_sha256": self._held_pointwise_hashes["C1"],
            "lit_raw_checkpoint_sha256": self._held_pointwise_hashes["L0"],
            "l0_raw_checkpoint_sha256": self._held_pointwise_hashes["L0"],
            "l1_raw_checkpoint_sha256": self._held_pointwise_hashes["L1"],
            "m1_pointwise_checkpoint_sha256": self._held_pointwise_hashes["M1"],
        })
        arm_payload = _canonical_json_bytes({
            "schema": "entry-v2-selected-neural-arm-v1", "arm": arm,
            "architecture": architecture,
            "encoder_sha256": _sha_bytes(encoder_bytes),
            "head_sha256": _sha_bytes(head_bytes),
            "objective_head_sha256": _sha_bytes(objective_bytes)})
        selected_horizon_normalizer = {
            "schema": "entry-v2-selected-horizon-normalizer-v1",
            "coordinates": list(SELECTED_HORIZON_COORDINATES),
            "target_schema_sha256": SELECTED_HORIZON_SCHEMA_SHA256,
            "target_law_sha256": SELECTED_HORIZON_TARGET_LAW_SHA256,
            "location": list(self._held_horizon_normalizer["location"]),
            "scale": list(self._held_horizon_normalizer["scale"]),
        }
        selected_horizon_normalizer["receipt_sha256"] = _sha(
            selected_horizon_normalizer)
        if (selected_horizon_normalizer["receipt_sha256"]
                != self._held_horizon_normalizer["receipt_sha256"]):
            raise RealDiagnosticExecutorRefusal(
                "selected horizon normalizer payload identity differs")
        normalizers = _canonical_json_bytes({
            "schema": "entry-v2-winner-normalizers-v1",
            "held_train_event_location": self._held_normalizer["location"].tolist(),
            "held_train_event_scale": self._held_normalizer["scale"].tolist(),
            "held_train_event_constant": self._held_normalizer["constant"].tolist(),
            "held_train_static_location": self._held_normalizer["static_location"].tolist(),
            "held_train_static_scale": self._held_normalizer["static_scale"].tolist(),
            "held_train_static_constant": self._held_normalizer["static_constant"].tolist(),
            "selected_horizon": selected_horizon_normalizer,
            "forward_fold_refit_required": True})
        source = _canonical_json_bytes({
            "schema": "entry-v2-winner-source-manifest-v1",
            "diagnostic_corpus_sha256": self.stage.diagnostic_corpus.receipt["receipt_sha256"],
            "one_load_id": self.loaded.one_load_id})
        row = _canonical_json_bytes({
            "schema": "entry-v2-winner-row-manifest-v1",
            "receipt_sha256": target_manifest_sha256,
            "target_row_manifest_sha256": target_manifest_sha256})
        payloads = {
            "arm.json": arm_payload, "objective.json": objective_payload,
            "encoder.safetensors": encoder_bytes, "head.safetensors": head_bytes,
            "objective-head.safetensors": objective_bytes,
            "normalizers.json": normalizers, "mapper.json": mapper_payload,
            "calibrator.json": calibrator_payload, "thresholds.json": thresholds_payload,
            "capacity.json": capacity_payload, "source-manifest.json": source,
            "row-manifest.json": row}
        raw_zero: dict[str, float] = {}
        if decision_kind == "direct_neural":
            payloads["direct-policy.safetensors"] = save({
                name: value.detach().cpu().contiguous()
                for name, value in model.head.action_head.state_dict().items()})
            direct = model.head.action_head.state_dict()
            score = float(np.asarray(direct["bias"].detach().cpu(), np.float64)[0])
            raw_zero = {asset: float(expit(score)) for asset in C.ASSETS}
        else:
            import catboost
            fit = getattr(self, "_last_catboost_fit", None)
            if fit is None or fit.representation_sha256 != self._held_arm_rows[
                    arm].representation_sha256:
                raise RealDiagnosticExecutorRefusal("selected CatBoost fit is not arm-aligned")
            with tempfile.TemporaryDirectory(prefix="entry-v2-held-catboost-") as directory:
                root = Path(directory)
                for asset in C.ASSETS:
                    selected_model = fit.assets[asset].ranker_model
                    if selected_model is None:
                        raise RealDiagnosticExecutorRefusal(
                            f"selected CatBoost {asset} PairLogit is unavailable")
                    cbm = root / f"{asset}.cbm"; native = root / f"{asset}.json"
                    selected_model.save_model(str(cbm), format="cbm")
                    selected_model.save_model(str(native), format="json")
                    payloads[f"catboost-{asset}.cbm"] = cbm.read_bytes()
                    payloads[f"catboost-{asset}.json"] = native.read_bytes()
                    raw = np.asarray(selected_model.predict(
                        np.zeros((1, 512), np.float32),
                        prediction_type="RawFormulaVal"), np.float64).reshape(-1)
                    if raw.shape != (1,) or not np.isfinite(raw[0]):
                        raise RealDiagnosticExecutorRefusal(
                            f"selected CatBoost {asset} zero-row canary is invalid")
                    raw_zero[asset] = float(expit(raw[0]))
            payloads["catboost-config.json"] = _canonical_json_bytes({
                "schema": "entry-v2-catboost-policy-config-v1",
                "feature_width": 512,
                "forward_refit_params": _ranker_params()})
            model_pins = {asset: {
                "cbm_sha256": _sha_bytes(payloads[f"catboost-{asset}.cbm"]),
                "json_sha256": _sha_bytes(payloads[f"catboost-{asset}.json"]),
            } for asset in C.ASSETS}
            payloads["catboost-pins.json"] = _canonical_json_bytes({
                "schema": "entry-v2-catboost-runtime-pins-v1",
                "catboost_version": catboost.__version__,
                "numpy_version": np.__version__, "model_format": "cbm",
                "models": model_pins, "determinism_receipt_sha256":
                self.determinism_receipt_sha256})
            ranker_available = all(
                fit.assets[asset].ranker_availability.value == "MATERIALIZED"
                for asset in C.ASSETS)
            if not ranker_available:
                raise RealDiagnosticExecutorRefusal(
                    "selected CatBoost policy lacks all-asset day/phase ranker")
            payloads["catboost-ranker.json"] = _canonical_json_bytes({
                "schema": "entry-v2-catboost-ranker-v1",
                "loss_function": "PairLogit", "available": ranker_available,
                "availability_by_asset": {asset:
                    fit.assets[asset].ranker_availability.value for asset in C.ASSETS}})
        mapper_doc = json.loads(mapper_payload)
        calibrator_doc = json.loads(calibrator_payload)
        threshold_doc = json.loads(thresholds_payload)
        coef = np.asarray(mapper_doc["coef"], np.float64)
        if coef.shape != (128,):
            raise RealDiagnosticExecutorRefusal("winner mapper canary width differs")
        per_asset = {}
        for asset in C.ASSETS:
            raw = raw_zero[asset]
            binding = _decision_binding(np.asarray([raw]))
            mapped = float(binding[0] @ coef + float(mapper_doc["intercept"]))
            calibrated = float(expit(float(calibrator_doc["slope"]) * mapped
                                     + float(calibrator_doc["intercept"])))
            threshold = float(threshold_doc["thresholds"][asset])
            per_asset[asset] = {"raw_model_score": raw, "mapper_score": mapped,
                "calibrated_probability": calibrated, "threshold": threshold,
                "enter": bool(calibrated >= threshold)}
        payloads["policy-canary.json"] = _canonical_json_bytes({
            "schema": "entry-v2-winner-policy-canary-v1",
            "input": "ZERO_FEATURE_ROW", "per_asset": per_asset})
        return MappingProxyType(payloads)

    def _produce_e2_confirmations(self):
        from .neural_sufficiency_stage_engine import (
            AssetEconomics, MeasuredFinalistConfirmation,
        )
        if self._held_engine is None or self._held_engine.e1 is None:
            raise RealDiagnosticExecutorRefusal("E2 producer requires frozen E1")
        specs, ids_tuple, rows, _old_targets, _old_contexts, _pretexts, _ = \
            self._build_held_probe_plane()
        ids = np.asarray(ids_tuple); assets = np.asarray(rows.asset, str)
        days = np.asarray(rows.day, np.int64)
        fit_idx = np.flatnonzero(days <= 20220311)
        selection_days = tuple(sorted({session.trading_day for session in
            self.stage.corpus_stage.corpus.replay.expected_sessions
            if 20220610 <= session.trading_day <= 20220630}))
        e2_fit_days = tuple(sorted({session.trading_day for session in
            self.stage.corpus_stage.corpus.replay.expected_sessions
            if session.trading_day <= 20220311}))
        e2_platt_days = tuple(sorted({session.trading_day for session in
            self.stage.corpus_stage.corpus.replay.expected_sessions
            if 20220314 <= session.trading_day <= 20220427}))
        e2_threshold_days = tuple(sorted({session.trading_day for session in
            self.stage.corpus_stage.corpus.replay.expected_sessions
            if 20220428 <= session.trading_day <= 20220609}))
        e2_development_days = (*e2_platt_days, *e2_threshold_days)
        targets = self._materialize_held_targets(self._held_engine.e1.finalists, 20220311)
        contexts = self._held_context_factory(20220311)
        confirmations = []
        binding = {row.candidate_id: row for row in self.stage.diagnostic_corpus.bindings}
        action = np.asarray([binding[cid].action_target for cid in ids], np.int8)
        # Capacity is the exact hindsight candidate-set ceiling passed through
        # canonical replay, never a classifier fitted to action labels.
        examples = {item.candidate_id: item for spec in
                    self.stage.corpus_stage.corpus.sessions for item in spec.examples}
        outcomes = self.stage.corpus_stage.corpus.replay.outcomes
        selection_mask = (days >= 20220610) & (days <= 20220630)
        teacher = self.stage.corpus_stage.corpus.teacher
        oracle_arrivals = tuple(ScoredArrival(
            examples[str(cid)], EntryScore(str(cid), str(asset),
                examples[str(cid)].decision_ts_ns, "candidate-ceiling-input", 0.0,
                0.0, 0.0, 0.0, 0.0, 0.0, 0.0, False), outcomes[str(cid)])
            for cid, asset in zip(ids[selection_mask], assets[selection_mask])
            if teacher[str(cid)].cert_close_usd >= C.MIN_EXPECTANCY_USD)
        if not oracle_arrivals:
            raise RealDiagnosticExecutorRefusal(
                "E2 clean candidate ceiling has no >=$600 candidates")
        expected = tuple(session for session in
            self.stage.corpus_stage.corpus.replay.expected_sessions
            if 20220610 <= session.trading_day <= 20220630)
        ceiling = candidate_ceiling(oracle_arrivals, expected_sessions=expected)
        oracle_eval = ceiling.evaluation
        oracle_receipt = _sha({"schema": "entry-v2-candidate-oracle-replay-v1",
                               "eligibility": "cert_close_usd >= MIN_EXPECTANCY_USD",
                               "minimum_expectancy_usd": C.MIN_EXPECTANCY_USD,
                               "schedule": ceiling.schedule_sha256,
                               "selected": ceiling.selected_candidate_ids,
                               "evaluation": [(row.asset, row.asset_days, row.trades,
                                               row.total_pnl_usd, row.max_drawdown_usd)
                                              for row in oracle_eval.by_asset]})
        oracle_by_asset = {row.asset: row for row in oracle_eval.by_asset}
        selected_probe_id = self._freeze_e2_objective(oracle_eval)
        selected_targets = self._materialize_held_targets((selected_probe_id,), 20220311)
        self._train_grouped_selected_objective(
            selected_probe_id, selected_targets[selected_probe_id])
        self._produce_held_arm_paths(end_d8=20220630)
        # The reusable pretext/atlas plane legitimately continues through E3,
        # but the E2 arm/head experiment has one and only one <=20220630 row
        # manifest.  Rebind every downstream learner/economic array to the
        # canonical frozen arm roster rather than comparing it to the longer
        # objective plane.
        matrix_rows = self._held_arm_rows["C0"]
        matrix_ids = tuple(map(str, np.asarray(matrix_rows.candidate_id, str).tolist()))
        if (not matrix_ids or len(matrix_ids) != len(set(matrix_ids))
                or any(tuple(map(str, np.asarray(self._held_arm_rows[arm].candidate_id,
                                                 str).tolist())) != matrix_ids
                       for arm in CANONICAL_ARMS)
                or any(binding[cid].trading_day > 20220630 for cid in matrix_ids)):
            raise RealDiagnosticExecutorRefusal(
                "E2 five-arm matrix does not share one canonical <=20220630 manifest")
        ids = np.asarray(matrix_ids, str)
        assets = np.asarray(matrix_rows.asset, str)
        days = np.asarray(matrix_rows.day, np.int64)
        action = np.asarray([binding[cid].action_target for cid in matrix_ids], np.int8)
        targets = selected_targets
        for probe_id in (selected_probe_id,):
            probe = next(s for s in PROBE_REGISTRY if s.probe_id == probe_id)
            target = targets[probe_id]
            contexts_for_probe = contexts[probe_id]
            preliminary = build_compact_atlas_handoff(
                self.stage.diagnostic_corpus, probe_id,
                {key: ({} if value is None else value)
                 for key, value in contexts_for_probe.items()})
            registry = json.loads(registry_bytes())
            objective_payload = _canonical_json_bytes({
                "schema": "entry-v2-selected-atlas-objective-v1",
                "registry_id": probe_id, "probe_id": probe_id,
                "registry_objective_sha256": preliminary.registry_objective_sha256,
                "target_row_manifest_sha256": preliminary.row_manifest_sha256,
                "materializer_callable_sha256": preliminary.materializer_callable_sha256,
                "fit_context_sha256": preliminary.fit_context_sha256,
                "atlas_aggregate_sha256": preliminary.atlas_aggregate_sha256,
                "transform_provenance_sha256": preliminary.transform_provenance_sha256,
                "ipcw_provenance_sha256": preliminary.ipcw_provenance_sha256,
                "axes_sha256": _sha({"layout": list(target.output_layout),
                                      "width": target.output_width}),
                "loss_callable_sha256": registry["callable_semantics_sha256"][probe.loss_id],
                "materializer_id": probe.materializer_id, "loss_id": probe.loss_id,
                "action_mapper_id": probe.action_mapper_id})
            objective_sha = _sha_bytes(objective_payload)
            for arm in CANONICAL_ARMS:
                arm_objective_payload = objective_payload
                arm_probe_id = probe_id
                if arm == "C0":
                    arm_probe_id = "A0_CURRENT_GROUPING"
                    arm_objective_payload = _canonical_json_bytes({
                        "schema": "entry-v2-selected-atlas-objective-v1",
                        "registry_id": arm_probe_id, "probe_id": arm_probe_id,
                        "registry_objective_sha256": _sha({
                            "objective": arm_probe_id, "law": "pointwise-oracle-matched-phase-v1"}),
                        "target_row_manifest_sha256": preliminary.row_manifest_sha256,
                        "materializer_callable_sha256": _sha({"callable": "A0.none"}),
                        "fit_context_sha256": _sha({"context": "A0.none"}),
                        "atlas_aggregate_sha256": preliminary.atlas_aggregate_sha256,
                        "transform_provenance_sha256": preliminary.transform_provenance_sha256,
                        "ipcw_provenance_sha256": preliminary.ipcw_provenance_sha256,
                        "axes_sha256": _sha({"axis": "current-grouping"}),
                        "loss_callable_sha256": _sha({"loss": "A0.current_grouping"}),
                        "materializer_id": "A0.none", "loss_id": "A0.current_grouping",
                        "action_mapper_id": "A0.current_action"})
                arm_objective_sha = _sha_bytes(arm_objective_payload)
                state = self._held_arm_rows[arm].representation
                if tuple(map(str, self._held_arm_rows[arm].candidate_id)) != matrix_ids:
                    raise RealDiagnosticExecutorRefusal("E2 arm/objective rows differ")
                real_head = self._held_objective_heads[arm]
                real_checkpoint = self._held_objective_e2_evidence["real_checkpoint"]
                twin_checkpoint = self._held_objective_e2_evidence["twin_checkpoint"]
                # The objective already trained the encoder/head. Both
                # decision learners now consume the identical frozen 512-state
                # manifest; no projection plane is substituted for it.
                real_features = np.asarray(state, np.float32)
                for decision_kind in DECISIONS:
                    started = time.perf_counter()
                    mapper, thresholds, evaluation, calibrated_probability, receipt = \
                        self._fit_policy_branch(
                        real_features, decision_kind=decision_kind, ids=ids, assets=assets,
                        days=days, targets=action,
                        direct_probability=(self._held_direct_probability[arm]
                                            if decision_kind == "direct_neural" else None),
                        diagnostic_scores=self._held_diagnostic_scores[arm],
                        pair_group_ids=np.asarray(
                            self._held_arm_rows[arm].exact_time_group_id, str),
                        expected_pair_manifest_by_asset={asset:
                            self._held_catboost[arm].assets[asset].pair_manifest.receipt_sha256
                            for asset in C.ASSETS})
                    threshold_selections = self._last_policy_selections
                    if threshold_selections is None:
                        raise RealDiagnosticExecutorRefusal(
                            "E2 arm path lacks exact threshold selections")
                    decision_model = (None if decision_kind == "direct_neural"
                                      else self._last_catboost_fit)
                    real_day = {(row.asset, row.trading_day): row.pnl_usd
                                for row in evaluation.asset_day_results}
                    oracle_day = {(row.asset, row.trading_day): row.pnl_usd
                                  for row in oracle_eval.asset_day_results}
                    effects = {asset: np.asarray([
                        real_day.get((asset, day), 0.0)
                        for day in selection_days], np.float64) for asset in C.ASSETS}
                    capture = {asset: np.asarray([
                        real_day.get((asset, day), 0.0)
                        / max(1.0, abs(oracle_day.get((asset, day), 0.0)))
                        for day in selection_days], np.float64) for asset in C.ASSETS}
                    by_asset = {row.asset: row for row in evaluation.by_asset}
                    runtime_seconds = time.perf_counter() - started
                    path_parameter_count = sum(p.numel() for p in
                        self._held_models[arm].parameters()) + sum(
                        p.numel() for p in real_head.parameters())
                    if decision_kind == "catboost":
                        path_parameter_count += sum(int(
                            np.asarray(self._last_catboost_fit.assets[
                                a].ranker_model.get_leaf_values()).size)
                            for a in C.ASSETS if
                            self._last_catboost_fit.assets[a].ranker_model is not None)
                    status = ("ELIGIBLE" if all(value == "ELIGIBLE" for value in
                        self._last_policy_availability.values())
                        else "NO_FEASIBLE_THRESHOLD")
                    rejection = dict(self._last_policy_availability)
                    if status == "ELIGIBLE":
                        for asset in C.ASSETS:
                            regime = capacity_regime_from_oracle(
                                oracle_by_asset[asset].usd_per_asset_day)
                            floor = {"FULL": C.TARGET_ASSET_DAY_USD,
                                     "WEAK": C.WEAK_ASSET_DAY_FLOOR_USD,
                                     "LOW": C.LOW_CAPACITY_ASSET_DAY_FLOOR_USD}[regime]
                            capture_value = (by_asset[asset].total_pnl_usd /
                                             oracle_by_asset[asset].total_pnl_usd)
                            days_with_trades = sum(row.asset == asset and row.trades > 0
                                for row in evaluation.asset_day_results)
                            minimum_days = int(np.ceil(len(selection_days) / 3.0))
                            if (by_asset[asset].usd_per_asset_day < floor
                                    or by_asset[asset].trades < 10
                                    or by_asset[asset].usd_per_trade < C.MIN_EXPECTANCY_USD
                                    or by_asset[asset].max_drawdown_usd > C.TARGET_MDD_USD
                                    or days_with_trades < minimum_days
                                    or not 0.0 <= capture_value <= 1.0
                                    or (regime == "LOW" and
                                        by_asset[asset].max_drawdown_usd >= 500.0)):
                                status = "NO_FEASIBLE_THRESHOLD"
                                rejection[asset] = "INELIGIBLE_CANONICAL_ECONOMICS"
                    if status != "ELIGIBLE":
                        loser_funnels = MappingProxyType({asset: _sha({
                            "threshold_funnel": self._last_policy_funnel_receipts[asset],
                            "rejection": rejection[asset]}) for asset in C.ASSETS})
                        refusal_sha = _sha({"status": status,
                            "funnels": dict(loser_funnels),
                            "arm": arm, "head": decision_kind})
                        confirmations.append(MeasuredFinalistConfirmation(
                            arm_probe_id, arm, decision_kind, selection_days,
                            effects, capture, {}, _sha({"arm": arm}), arm_objective_sha,
                            _sha({"calibrator": refusal_sha}), _sha({"threshold": refusal_sha}),
                            _sha({"capacity": refusal_sha}), _sha({"mapper": receipt}),
                            real_checkpoint, twin_checkpoint, path_parameter_count,
                            runtime_seconds, e2_fit_days,
                            e2_development_days, selection_days,
                            status=status,
                            rejection_reason_by_asset=MappingProxyType(rejection),
                            funnel_receipt_by_asset=loser_funnels,
                            platt_days=e2_platt_days,
                            threshold_development_days=e2_threshold_days))
                        continue
                    capacity_payload = {asset: {
                        "included_trading_days": by_asset[asset].asset_days,
                        "trades": by_asset[asset].trades,
                        "total_pnl_usd": by_asset[asset].total_pnl_usd,
                        "usd_per_asset_day": by_asset[asset].usd_per_asset_day,
                        "usd_per_trade": by_asset[asset].usd_per_trade,
                        "oracle_total_pnl_usd": oracle_by_asset[asset].total_pnl_usd,
                        "oracle_usd_per_asset_day":
                            oracle_by_asset[asset].usd_per_asset_day,
                        "oracle_capture": (by_asset[asset].total_pnl_usd /
                            oracle_by_asset[asset].total_pnl_usd),
                        "capacity_regime": capacity_regime_from_oracle(
                            oracle_by_asset[asset].usd_per_asset_day),
                        "chronological_max_drawdown_usd":
                            by_asset[asset].max_drawdown_usd,
                        "drawdown_p90_usd": by_asset[asset].drawdown_p90_usd,
                        "asset_day_denominator": "included_trading_days",
                        "values_clipped": False,
                        "replay_receipt_sha256": receipt,
                        "oracle_replay_receipt_sha256": oracle_receipt,
                        "days_with_trades": sum(
                            row.asset == asset and row.trades > 0
                            for row in evaluation.asset_day_results),
                    } for asset in C.ASSETS}
                    for asset in C.ASSETS:
                        eligibility = capacity_eligibility(capacity_payload[asset])
                        if not eligibility.eligible:
                            raise RealDiagnosticExecutorRefusal(
                                f"{asset} eligible E2 row failed shared capacity law")
                        capacity_payload[asset].update({
                            "threshold_feasibility_sha256":
                                eligibility.threshold_feasibility_sha256,
                            "capacity_eligibility_sha256": eligibility.receipt_sha256,
                            "eligibility": "ELIGIBLE",
                        })
                    capacity_bytes = _canonical_json_bytes({
                        "schema": CAPACITY_SCHEMA, "values_clipped": False,
                        "asset_day_denominator": "included_trading_days",
                        "per_asset": capacity_payload})
                    validate_capacity_document(json.loads(capacity_bytes))
                    capacity_hash = _sha_bytes(capacity_bytes)
                    economics = {asset: AssetEconomics(
                        capacity_regime_from_oracle(oracle_by_asset[asset].usd_per_asset_day),
                        by_asset[asset].asset_days, by_asset[asset].trades,
                        by_asset[asset].total_pnl_usd, by_asset[asset].usd_per_trade,
                        by_asset[asset].usd_per_asset_day,
                        by_asset[asset].max_drawdown_usd, by_asset[asset].drawdown_p90_usd,
                        oracle_by_asset[asset].total_pnl_usd,
                        oracle_by_asset[asset].usd_per_asset_day,
                        by_asset[asset].total_pnl_usd /
                            oracle_by_asset[asset].total_pnl_usd,
                        receipt, oracle_receipt, capacity_hash,
                        capacity_payload[asset]["days_with_trades"],
                        capacity_payload[asset]["threshold_feasibility_sha256"],
                        capacity_payload[asset]["capacity_eligibility_sha256"],
                        "ELIGIBLE") for asset in C.ASSETS}
                    thresholds_payload = _canonical_json_bytes({
                        "schema": "entry-v2-thresholds-v1", "thresholds": thresholds})
                    calibrator_payload = _canonical_json_bytes({
                        "schema": "entry-v2-positive-slope-calibrator-v1",
                        "slope": mapper.calibrator.slope,
                        "intercept": mapper.calibrator.intercept,
                        "fit_ids_sha256": mapper.calibrator.fit_ids_sha256})
                    mapper_payload = _canonical_json_bytes({
                        "schema": "entry-v2-binding-mapper-v1",
                        "coef": mapper.coef_.tolist(), "intercept": mapper.intercept_,
                        "fit_ids_sha256": mapper.fit_ids_sha256})
                    arm_payloads = self._winner_model_payloads(
                        arm, decision_kind, real_head, arm_objective_payload, mapper_payload,
                        calibrator_payload, thresholds_payload, capacity_bytes,
                        preliminary.row_manifest_sha256)
                    confirmations.append(MeasuredFinalistConfirmation(
                        arm_probe_id, arm, decision_kind, selection_days, effects, capture,
                        economics, _sha_bytes(arm_payloads["arm.json"]),
                        arm_objective_sha, _sha_bytes(calibrator_payload),
                        _sha_bytes(thresholds_payload), capacity_hash,
                        _sha_bytes(mapper_payload), real_checkpoint, twin_checkpoint,
                        path_parameter_count, runtime_seconds,
                        e2_fit_days, e2_development_days, selection_days,
                        platt_days=e2_platt_days,
                        threshold_development_days=e2_threshold_days))
                    self._held_candidate_payloads = getattr(
                        self, "_held_candidate_payloads", {})
                    self._held_candidate_payloads[(arm_probe_id, arm, decision_kind)] = {
                        "payloads": arm_payloads, "mapper": mapper,
                        "objective_head": real_head,
                        "target_manifest": preliminary.row_manifest_sha256,
                        "contexts": contexts_for_probe, "economics": economics,
                        "capacity_payload": capacity_payload,
                        "candidate_ids": tuple(map(str, ids.tolist())),
                        "calibrated_probability": np.asarray(
                            calibrated_probability, np.float64).copy(),
                        "raw_decision_probability": np.asarray(
                            self._last_policy_raw_probability, np.float64).copy(),
                        "threshold_selections": threshold_selections,
                        "decision_model": decision_model}
        expected_matrix = tuple((arm, decision) for arm in CANONICAL_ARMS
                                for decision in DECISIONS)
        if (len(confirmations) != 10
                or tuple((row.arm, row.decision_kind) for row in confirmations)
                   != expected_matrix):
            raise RealDiagnosticExecutorRefusal(
                "E2 producer did not emit the exact ordered five-arm/two-head census")
        self._held_confirmations = tuple(confirmations)
        return self._held_confirmations

    def _produce_primary_e3_artifacts(self) -> None:
        """Report the frozen E2 winner on E3 once, without optimizer access."""
        from .neural_sufficiency_stage_engine import HeldWinnerArtifacts
        from .folds import FoldSpec
        from .train import (
            ARM_FULL_PREFIX, FOLD_OOF_SCHEMA, THRESHOLD_FUNNEL_SCHEMA,
            TRUTH_THRESHOLD_GRID_USD, SELECTED_ORDINAL_SEMANTICS_SHA256,
            FoldOOFResult,
            SelectedFoldTrainingReceipt, _EncodedRows, _array_hash,
            _entry_scores, _pre_encoder_action_supervision_census,
            _select_truth_threshold, build_selected_winner_fold_report,
            candidate_oracle_preflight, threshold_candidate_law,
            validate_selected_policy_training_receipt,
        )
        from .policy import entry_gate_contract
        if self._held_engine is None or self._held_engine.e2 is None:
            raise RealDiagnosticExecutorRefusal("primary E3 requires frozen E2")
        winner = self._held_engine.e2
        confirmation = winner.confirmation
        key = (confirmation.probe_id, confirmation.arm, confirmation.decision_kind)
        candidate = self._held_candidate_payloads[key]
        payloads = candidate["payloads"]
        model = self._held_models[confirmation.arm].to(self.device).eval()
        mapper = candidate["mapper"]
        thresholds = json.loads(payloads["thresholds.json"])["thresholds"]
        all_specs = self._held_population(20221230)
        calendar_days = tuple(sorted({session.trading_day for session in
            self.stage.corpus_stage.corpus.replay.expected_sessions
            if 20210531 <= session.trading_day <= 20221230}))
        fit_days = tuple(day for day in calendar_days if day <= 20220311)
        calibration_days = tuple(day for day in calendar_days
                                 if 20220314 <= day <= 20220609)
        selection_days = tuple(day for day in calendar_days
                               if 20220610 <= day <= 20220630)
        test_days = tuple(day for day in calendar_days
                          if 20220701 <= day <= 20221230)
        calibration_blocks = tuple(tuple(int(value) for value in part.tolist())
            for part in np.array_split(np.asarray(calibration_days, np.int64), 4)
            if len(part))
        fold = FoldSpec(
            "E3", min(fit_days), max(selection_days), 20220701, 20221230,
            fit_days, (*calibration_days, *selection_days), test_days,
            (*calibration_blocks, selection_days),
        )
        fold.validate()
        if (len(calibration_blocks) != 4 or not fit_days or not selection_days
                or max(fit_days) != 20220311
                or min(calibration_days) != 20220314
                or max(calibration_days) != 20220609
                or min(selection_days) != 20220610
                or max(selection_days) != 20220630):
            raise RealDiagnosticExecutorRefusal(
                "live calendar does not reproduce the frozen E3 chronology")
        fit_specs = tuple(spec for spec in all_specs
                          if spec.trading_day in set(fold.fit_days))
        inner_specs = tuple(spec for spec in all_specs
                            if spec.trading_day in set(fold.inner_days))
        specs = tuple(spec for spec in all_specs
                      if spec.trading_day in set(fold.test_days))
        if not fit_specs or not inner_specs or not specs:
            raise RealDiagnosticExecutorRefusal("primary E3 candidate population is empty")
        ids = []; assets = []; days = []; states = []
        raw_probability = []; examples = []
        diagnostics: dict[str, list[np.ndarray]] = {name: [] for name in (
            "top3_p", "wall_p_upper", "expected_value_raw",
            "expected_value_lower", "expected_value_upper", "mae_q90",
        )}
        for spec in specs:
            batch = self._held_batch(spec)
            with torch.no_grad(), torch.autocast(
                    device_type="cuda", dtype=torch.bfloat16,
                    enabled=self.device.type == "cuda"):
                output = model(
                    event_continuous=batch.continuous.to(self.device),
                    event_categorical=batch.categorical.to(self.device),
                    receive_clock_ns=batch.clock.to(self.device),
                    candidate_cutoffs=batch.cutoffs.to(self.device),
                    candidate_decision_ts_ns=batch.decisions.to(self.device),
                    candidate_features=batch.candidate_features.to(self.device),
                    context_values=batch.context_values.to(self.device),
                    context_type_ids=batch.context_type_ids.to(self.device),
                    context_valid=batch.context_valid.to(self.device),
                    asset_idx=C.ASSET_INDEX[batch.asset],
                    static_features=(batch.static_features.to(self.device)
                                     if confirmation.arm in ("L1", "M1") else None))
            state = output.decision_state.detach().float().cpu().numpy()
            states.append(state)
            ids.extend(batch.candidate_ids); assets.extend([batch.asset] * len(state))
            days.extend([batch.day] * len(state))
            if confirmation.decision_kind == "direct_neural":
                raw_probability.extend(torch.sigmoid(
                    output.action_logit.float()).cpu().numpy().tolist())
            else:
                decision_model = candidate.get("decision_model")
                if decision_model is None:
                    raise RealDiagnosticExecutorRefusal(
                        "selected E3 PairLogit model was not retained")
                ranker = decision_model.assets[batch.asset].ranker_model
                if ranker is None:
                    raise RealDiagnosticExecutorRefusal("selected E3 PairLogit is unavailable")
                raw = np.asarray(ranker.predict(state), np.float64)
                raw_probability.extend(expit(raw).tolist())
            diagnostics["top3_p"].append(torch.sigmoid(
                output.top3_logit.float()).cpu().numpy())
            diagnostics["wall_p_upper"].append(torch.sigmoid(
                output.wall_logit.float()).cpu().numpy())
            diagnostics["expected_value_raw"].append(
                output.expected_value.float().cpu().numpy() * VALUE_SCALE_USD)
            value_quantiles = output.value_quantiles.float().cpu().numpy()
            diagnostics["expected_value_lower"].append(
                value_quantiles[:, 0] * VALUE_SCALE_USD)
            diagnostics["expected_value_upper"].append(
                value_quantiles[:, 2] * VALUE_SCALE_USD)
            diagnostics["mae_q90"].append(
                output.mae_quantiles[:, 2].float().cpu().numpy() * MAE_SCALE_USD)
            examples.extend(spec.examples)
        ids_tuple = tuple(map(str, ids)); assets_tuple = tuple(map(str, assets))
        day_array = np.asarray(days, np.int64)
        embedding = np.concatenate(states).astype(np.float32, copy=False)
        static = np.empty((len(ids_tuple), 0), np.float32)
        raw_probability_array = np.asarray(raw_probability, np.float64)
        probability, _ = mapper.predict(_decision_binding(raw_probability_array))
        score_arrays = {
            "raw_model_probability": raw_probability_array,
            "calibrated_probability": np.asarray(probability, np.float64),
            "action_p": np.asarray(probability, np.float64),
            **{name: np.concatenate(values).astype(np.float64, copy=False)
               for name, values in diagnostics.items()},
        }
        if (tuple(ids_tuple) != tuple(example.candidate_id for example in examples)
                or any(value.shape != (len(ids_tuple),)
                       or not np.all(np.isfinite(value))
                       for value in score_arrays.values())):
            raise RealDiagnosticExecutorRefusal(
                "primary E3 measured score surface is misaligned or non-finite")
        test_rows = _EncodedRows(
            tuple(examples), ids_tuple, assets_tuple, day_array, embedding,
            MappingProxyType({}),
        )
        outcomes = self.stage.corpus_stage.corpus.replay.outcomes
        denominator = self.stage.corpus_stage.corpus.replay.sessions_for(fold.test_days)
        regimes = self.stage.corpus_stage.corpus.replay.regimes_for(fold.test_days)
        teacher = self.stage.corpus_stage.corpus.teacher
        oracle_preflight = candidate_oracle_preflight(
            all_specs, teacher, self.stage.corpus_stage.corpus.replay,
            fold.test_days)
        action_census = _pre_encoder_action_supervision_census(
            fit_specs, inner_specs, teacher, fold)

        selection_examples = tuple(example for spec in inner_specs
            if spec.trading_day in set(selection_days) for example in spec.examples)
        truth_selections = {}
        for asset in C.ASSETS:
            local_examples = tuple(example for example in selection_examples
                                   if example.asset == asset)
            if not local_examples:
                raise RealDiagnosticExecutorRefusal(
                    f"E3 truth selection has no {asset} candidates")
            local_rows = _EncodedRows(
                local_examples,
                tuple(example.candidate_id for example in local_examples),
                tuple(example.asset for example in local_examples),
                np.asarray([example.trading_day for example in local_examples],
                           np.int64),
                np.zeros((len(local_examples), 1), np.float32),
                MappingProxyType({}),
            )
            truth_selections[asset] = _select_truth_threshold(
                asset, local_rows, teacher,
                self.stage.corpus_stage.corpus.replay, selection_days)
        truth_thresholds = MappingProxyType({
            asset: truth_selections[asset].threshold for asset in C.ASSETS})
        threshold_selections = candidate.get("threshold_selections")
        if (not isinstance(threshold_selections, Mapping)
                or set(threshold_selections) != set(C.ASSETS)
                or any(float(threshold_selections[asset].threshold)
                       != float(thresholds[asset]) for asset in C.ASSETS)):
            raise RealDiagnosticExecutorRefusal(
                "primary E3 thresholds differ from the frozen E2 sweeps")
        selection_sha = _sha(dict(winner.selection_hashes))
        checkpoint_set = C.object_sha256({name: _sha_bytes(payloads[name]) for name in
            ("encoder.safetensors", "head.safetensors", "objective-head.safetensors")})
        chronological = C.object_sha256({"field_dense": self._held_training_receipt,
                                        "grouped": self._held_grouped_receipt})
        training_receipt_sha = _sha({"schema": "entry-v2-selected-held-training-v1",
            "selection": selection_sha, "real_checkpoint": confirmation.real_checkpoint_sha256,
            "checkpoint_set": checkpoint_set, "chronological": chronological})
        selected_training = SelectedFoldTrainingReceipt.freeze(
            training_receipt_sha256=training_receipt_sha,
            normalizers_payload_sha256=_sha_bytes(payloads["normalizers.json"]),
            model_input_binding=self.stage.corpus_stage.corpus.model_input_binding,
            expanded_schema_sha256=self.expanded_transform.schema_sha256,
            expanded_transform_law_sha256=self.expanded_transform.transform_law_sha256,
            e2_frozen_selection_sha256=selection_sha,
            checkpoint_set_sha256=checkpoint_set,
            chronological_stage_receipts_sha256=chronological,
            selected_horizon_schema_sha256=SELECTED_HORIZON_SCHEMA_SHA256,
            selected_horizon_target_law_sha256=
                SELECTED_HORIZON_TARGET_LAW_SHA256,
            selected_horizon_normalizer_sha256=
                self._held_horizon_normalizer["receipt_sha256"],
            selected_output_schema_sha256=model.head.output_schema_sha256,
            selected_ordinal_semantics_sha256=
                SELECTED_ORDINAL_SEMANTICS_SHA256)
        target_manifest = candidate["target_manifest"]
        target_control = _sha({"schema": "entry-v2-selected-target-control-v1",
            "row_manifest_sha256": target_manifest, "control": "PROPHET"})
        winner_receipt = {"legacy_full_prefix": False, "arm": confirmation.arm,
            "bundle_sha256": None,
            "decision_head_kind": confirmation.decision_kind,
            "objective_sha256": confirmation.selected_objective_sha256,
            "target_row_manifest_sha256": target_manifest,
            "target_control_sha256": target_control,
            "e2_frozen_selection_sha256": selection_sha}
        if confirmation.arm != "C0":
            handoff = self.compact_atlas_handoff(
                fold, control_name="PROPHET", shuffle_seed=0)
            target_control_receipt = {
                "schema": "entry-v2-selected-target-control-v1",
                "control": "PROPHET",
                "target_control_sha256": target_control,
                "target_row_manifest_sha256": target_manifest,
                "fit_day_manifest_sha256": handoff.fit_day_manifest_sha256,
                "target_candidate_manifest_sha256":
                    handoff.target_candidate_manifest_sha256,
                "fit_context_sha256": handoff.fit_context_sha256,
            }
            winner_receipt.update({
                "target_control_receipt": target_control_receipt,
                "fit_day_manifest_sha256": handoff.fit_day_manifest_sha256,
                "target_candidate_manifest_sha256":
                    handoff.target_candidate_manifest_sha256,
                "fit_context_sha256": handoff.fit_context_sha256,
            })
        policy_factory_name = (
            "entry_v2_selected_direct_policy_factory"
            if confirmation.decision_kind == "direct_neural"
            else "entry_v2_selected_catboost_policy_factory")
        arrays_for_receipt = {
            "full_prefix_embedding": embedding,
            "static_summary": static,
            **{f"{ARM_FULL_PREFIX}:{name}": value
               for name, value in score_arrays.items()},
        }
        selected_rows = self._held_arm_rows[confirmation.arm]
        selected_ids = np.asarray(selected_rows.candidate_id, str)
        selected_assets = np.asarray(selected_rows.asset, str)
        selected_days = np.asarray(selected_rows.day, np.int64)
        per_asset_training = {}
        for asset in C.ASSETS:
            fit_mask = ((selected_assets == asset)
                        & np.isin(selected_days, fit_days))
            calibration_mask = ((selected_assets == asset)
                                & np.isin(selected_days, calibration_days))
            if confirmation.decision_kind == "catboost":
                pair_manifest = self._held_catboost[confirmation.arm].assets[
                    asset].pair_manifest
                pair_receipt = pair_manifest.receipt_sha256
                pair_count = len(pair_manifest.pairs)
            else:
                pair_receipt = None; pair_count = 0
            per_asset_training[asset] = {
                "schema": "entry-v2-selected-policy-asset-fit-v1",
                "asset": asset,
                "chronology_law": "entry-v2-selected-train-only-policy-v1",
                "optimizer_step_unit": "complete_asset_day_gradient",
                "mapper_weighting": "A013_ACTION_FIT_WEIGHTS",
                "training_rows": int(fit_mask.sum()),
                "calibration_rows": int(calibration_mask.sum()),
                "training_candidate_sha256": _sha(selected_ids[fit_mask].tolist()),
                "calibration_candidate_sha256":
                    _sha(selected_ids[calibration_mask].tolist()),
                "action_fit_weight_receipt_sha256":
                    self._held_grouped_action_weight_receipt,
                "mapper_parameter_sha256": mapper.parameter_sha256,
                "phase_pair_manifest_sha256": pair_receipt,
                "phase_pair_count": pair_count,
            }
        selected_policy_core = {
            "schema": "entry-v2-selected-policy-training-v1",
            "chronology_law": "entry-v2-selected-train-only-policy-v1",
            "action_fit_weight_law": "entry-v2-action-fit-weights-v1",
            "phase_pair_law": "entry-v2-canonical-phase-pairs-v1",
            "decision_head_kind": confirmation.decision_kind,
            "asset_order": list(C.ASSETS),
            "fit_days": list(fit_days),
            "calibration_days": list(calibration_days),
            "selection_days": list(selection_days),
            "per_asset": per_asset_training,
        }
        selected_policy_training = {**selected_policy_core,
            "sha256": C.object_sha256(selected_policy_core)}
        validate_selected_policy_training_receipt(
            selected_policy_training,
            decision_head_kind=confirmation.decision_kind,
            fit_days=fit_days, calibration_days=calibration_days,
            selection_days=selection_days)
        fold_receipt = {"schema": FOLD_OOF_SCHEMA, "fold": "E3",
            "arms": [ARM_FULL_PREFIX], "winner_adoption": winner_receipt,
            "objective_sha256": confirmation.selected_objective_sha256,
            "e2_frozen_selection_sha256": selection_sha,
            "training_receipt_sha256": selected_training.training_receipt_sha256,
            "normalizer_sha256": selected_training.normalizers_payload_sha256,
            "model_input_binding": selected_training.model_input_binding.as_dict(),
            "fit_max_d8": max(fold.fit_days),
            "calibration_min_d8": min(fold.inner_days),
            "calibration_max_d8": max(fold.inner_days),
            "test_min_d8": min(fold.test_days),
            "test_max_d8": max(fold.test_days),
            "test_days_declared": list(fold.test_days),
            "test_candidate_sha256": C.object_sha256(list(ids_tuple)),
            "arrays_sha256": _array_hash(arrays_for_receipt),
            "assets": list(C.ASSETS),
            "static_summary_schema": None,
            "training_control": "PROPHET",
            "policy_factory_dispatch": {ARM_FULL_PREFIX: policy_factory_name},
            "null_control": {
                "schema": "entry-v2-positive-control-v1", "control": "PROPHET"},
            "regime_declarations": [dict(asset=r.asset, trading_day=r.trading_day,
                regime=r.regime, availability_ts_ns=r.availability_ts_ns) for r in regimes],
            "prequential": {
                "blocks": [list(block) for block in fold.prequential_blocks],
                "calibration_days": list(calibration_days),
                "threshold_selection_days": list(selection_days),
                "selected_policy_calibration_days": list(calibration_days),
                "selected_policy_selection_days": list(selection_days),
                "selected_policy_chronology_law":
                    "entry-v2-selected-train-only-policy-v1",
                "selected_policy_fit_excludes_all_inner_labels": True,
                "calibration_and_selection_predictions_disjoint": True,
                "test_predictions_never_used_for_calibration_or_selection": True,
            },
            "arm_thresholds": {ARM_FULL_PREFIX: {
                asset: asdict(threshold_selections[asset]) for asset in C.ASSETS}},
            "truth_inner_thresholds_usd": {
                asset: asdict(truth_selections[asset]) for asset in C.ASSETS},
            "threshold_candidate_law": threshold_candidate_law(),
            "truth_threshold_grid_usd": list(TRUTH_THRESHOLD_GRID_USD),
            "threshold_funnel_schema": THRESHOLD_FUNNEL_SCHEMA,
            "action_supervision_census": dict(action_census),
            "selected_policy_training": selected_policy_training,
            "candidate_oracle_preflight": dict(oracle_preflight),
            "entry_gate_contract": entry_gate_contract(),
            "decision_contract": {
                "proxy_metrics": "diagnostic_only",
                "promotion_basis": [
                    "exact_chronological_asset_day_dollars",
                    "exact_candidate_set_oracle_capture",
                    "chronological_cumulative_per_asset_max_drawdown",
                ],
                "first_failed_boundary": None,
            },
        }
        fold_receipt["sha256"] = C.object_sha256(fold_receipt)
        entry_scores = _entry_scores(
            test_rows, score_arrays, thresholds,
            f"entry-v2:{ARM_FULL_PREFIX}:E3:{fold_receipt['sha256']}")
        arrivals = tuple(ScoredArrival(example, score, outcomes[score.candidate_id])
                         for example, score in zip(examples, entry_scores))
        evaluation = replay(arrivals, expected_sessions=denominator)
        truth_scores = teacher.truth_scores(
            examples, entry_thresholds_usd=truth_thresholds)
        truth_arrivals = tuple(ScoredArrival(
            example, score, outcomes[score.candidate_id])
            for example, score in zip(examples, truth_scores))
        truth_evaluation = replay(truth_arrivals, expected_sessions=denominator)
        ceiling = candidate_ceiling(
            tuple(row for row in truth_arrivals
                  if teacher[row.example.candidate_id].cert_close_usd
                      >= C.MIN_EXPECTANCY_USD),
            expected_sessions=denominator,
        )
        base = FoldOOFResult("E3", ids_tuple, assets_tuple, day_array, embedding, static,
            MappingProxyType({ARM_FULL_PREFIX: MappingProxyType(score_arrays)}),
            MappingProxyType({ARM_FULL_PREFIX: entry_scores}),
            MappingProxyType({ARM_FULL_PREFIX: arrivals}),
            MappingProxyType({ARM_FULL_PREFIX: MappingProxyType(dict(thresholds))}),
            MappingProxyType({ARM_FULL_PREFIX: evaluation}),
            MappingProxyType({ARM_FULL_PREFIX: MappingProxyType({
                "decision_head_kind": confirmation.decision_kind,
                "mapper_sha256": confirmation.mapper_sha256})}),
            truth_scores, truth_arrivals, denominator, truth_thresholds,
            truth_evaluation, ceiling, selected_training,
            MappingProxyType(fold_receipt), "PROPHET", regimes)
        primary = build_selected_winner_fold_report(base,
            selected_arm=confirmation.arm,
            decision_head_kind=confirmation.decision_kind,
            objective_sha256=confirmation.selected_objective_sha256,
            target_row_manifest_sha256=target_manifest,
            target_control_sha256=target_control,
            e2_frozen_selection_sha256=selection_sha)
        self._held_artifacts = HeldWinnerArtifacts(
            payloads, primary, confirmation.probe_id,
            confirmation.decision_kind,
            self.entry_v2_selected_direct_policy_factory if
                confirmation.decision_kind == "direct_neural" else
                self.entry_v2_selected_catboost_policy_factory,
            target_manifest)

    def execute_stage(self, mode: str, acceptance_sha256: str,
                      prior_stage_sha256: str):
        if mode == "E1":
            if self._loaded_maximum_d8 < 20211231:
                predecessor = self._loaded_window_id
                self._extend_held_window(20211231)
                if (self._loaded_maximum_d8 < 20211231
                        or predecessor is None or self._loaded_window_id == predecessor):
                    raise RealDiagnosticExecutorRefusal(
                        "E1 incremental extension did not advance the window identity")
            if self._held_engine is None:
                self.produce_measured_held_inputs()
            return self._held_engine.execute_e1(acceptance_sha256, self._held_screens)
        if mode == "E2":
            if self._loaded_maximum_d8 < 20220630:
                self._extend_held_window(20220630)
                if self._loaded_maximum_d8 < 20220630:
                    raise RealDiagnosticExecutorRefusal(
                        "E2 window extension did not reach the frozen boundary")
            if self._held_engine is None or self._held_engine.e1 is None:
                raise RealDiagnosticExecutorRefusal("E2 requires measured E1")
            if self._held_confirmations is None:
                self._produce_e2_confirmations()
            result = self._held_engine.execute_e2(
                acceptance_sha256, prior_stage_sha256, self._held_confirmations,
                self._held_objective_freeze_receipt)
            winner = self._held_engine.e2
            assert winner is not None
            selected_key = (winner.confirmation.probe_id, winner.confirmation.arm,
                            winner.confirmation.decision_kind)
            selected_candidate = self._held_candidate_payloads[selected_key]
            if winner.confirmation.arm != "C0":
                self._atlas_fit_context_by_probe_session[winner.confirmation.probe_id] = dict(
                    selected_candidate["contexts"])
                self.select_compact_objective(
                    winner.confirmation.probe_id,
                    winner.confirmation.selected_objective_sha256)
            else:
                self._selected_objective_probe_id = "A0_CURRENT_GROUPING"
                self._selected_objective_sha256 = (
                    winner.confirmation.selected_objective_sha256)
            self._winner_mapper = copy.deepcopy(selected_candidate["mapper"])
            self.mapper_sha256 = winner.confirmation.mapper_sha256
            self.calibrator_sha256 = winner.confirmation.calibrator_sha256
            self.thresholds_sha256 = winner.confirmation.thresholds_sha256
            self.capacity_authority_sha256 = winner.confirmation.capacity_authority_sha256
            return result
        if mode == "E3":
            if self._loaded_maximum_d8 < 20221230:
                self._extend_held_window(20221230)
                if self._loaded_maximum_d8 < 20221230:
                    raise RealDiagnosticExecutorRefusal(
                        "E3 window extension did not reach the frozen boundary")
            if self._held_artifacts is None:
                self._produce_primary_e3_artifacts()
            result = self._held_engine.execute_e3(
                acceptance_sha256, prior_stage_sha256, self._held_artifacts)
            self.policy_kind = self._held_artifacts.policy_kind
            return result
        raise RealDiagnosticExecutorRefusal("unknown held stage mode")

    def _extend_held_window(self, new_maximum_d8: int) -> None:
        """Advance the same durable corpus owner by one adjacent held window."""
        if self.stage is None or self.cache.durable_store is not self.durable_store:
            raise RealDiagnosticExecutorRefusal(
                "held window extension lacks the live durable owner")
        old_maximum = self._loaded_maximum_d8
        if int(new_maximum_d8) <= old_maximum:
            raise RealDiagnosticExecutorRefusal(
                "held window extension is not chronologically later")
        extended = extend_production_diagnostic_stage(
            self.stage, new_maximum_d8=int(new_maximum_d8)
        )
        receipt = extended.diagnostic_corpus.receipt
        lifecycle = extended.lifecycle_provenance
        if (int(receipt.get("corpus_maximum_d8", -1)) != int(new_maximum_d8)
                or not isinstance(lifecycle.get(
                    "cumulative_window_identity_sha256"), str)
                or len(lifecycle["cumulative_window_identity_sha256"]) != 64):
            extended.close()
            raise RealDiagnosticExecutorRefusal(
                "held window extension receipt differs from the requested boundary")
        self.stage = extended
        self._loaded_maximum_d8 = int(new_maximum_d8)
        self._loaded_window_id = str(
            lifecycle["cumulative_window_identity_sha256"])
        if self.expanded_transform._frozen:
            expanded_metadata = self._expanded_session_metadata()
            self.expanded_transform.rebind(
                model_input_binding=
                    self.stage.corpus_stage.corpus.model_input_binding,
                bindings=expanded_metadata,
            )
            self._expanded_session_metadata_sha256 = \
                self._expanded_session_metadata_identity(expanded_metadata)
        # Acceptance may have built these fit-only indexes.  Held stages must
        # rebuild them over the extended, still-single-owner corpus.
        self._binding_by_id = None
        self._binding_by_session = None
        self._observed_by_session = None

    def _expanded_session_metadata(
        self,
    ) -> Mapping[tuple[str, int, str], tuple[Any, ...]]:
        """Canonical metadata for every diagnostic/learner session.

        The two session domains are intentionally not equal.  The diagnostic
        corpus retains every candidate-bearing session needed by the atlas,
        including a session whose candidates are all typed ``NO_SANE_SUFFIX``
        or otherwise unavailable to the learner.  ``EntryCorpus.sessions``
        retains only sessions with at least one exact ``CLEAR + READY`` row and
        may additionally contain prefix/context sessions before the diagnostic
        start wall.

        The deployment transform is consumed only by learner batches.  Its
        exact domain is therefore the intersection: every diagnostic session
        with a learner-eligible row must have one corpus session with the exact
        ordered eligible candidate roster; a diagnostic-only session is valid
        only when it has zero learner-eligible rows.  This is the same subset
        law frozen by ``selected_horizon_coverage_receipt``.
        """
        if self.stage is None:
            raise RealDiagnosticExecutorRefusal(
                "expanded transform metadata requires a loaded corpus")
        by_day: dict[tuple[str, int], list[Any]] = {}
        for row in self.stage.diagnostic_corpus.bindings:
            by_day.setdefault((str(row.asset), int(row.trading_day)), []).append(row)
        frozen_by_day = {
            key: tuple(value) for key, value in sorted(by_day.items())
        }
        diagnostic_days = tuple(
            (str(session.key[0]), int(session.key[1]))
            for session in self.stage.diagnostic_corpus.sessions
        )
        if (len(diagnostic_days) != len(set(diagnostic_days))
                or set(diagnostic_days) != set(frozen_by_day)):
            raise RealDiagnosticExecutorRefusal(
                "expanded transform diagnostic session/binding roster differs")
        spec_by_day: dict[tuple[str, int], Any] = {}
        for spec in self.stage.corpus_stage.corpus.sessions:
            day_key = (str(spec.asset), int(spec.trading_day))
            if day_key in spec_by_day:
                raise RealDiagnosticExecutorRefusal(
                    "expanded transform corpus session day is duplicated")
            spec_by_day[day_key] = spec
        metadata: dict[tuple[str, int, str], tuple[Any, ...]] = {}
        for day_key, rows in frozen_by_day.items():
            spec = spec_by_day.get(day_key)
            eligible = tuple(
                str(row.candidate_id) for row in rows
                if (str(row.compliance_status) == "CLEAR"
                    and str(row.teacher_status) == "READY")
            )
            if not eligible:
                if spec is not None:
                    raise RealDiagnosticExecutorRefusal(
                        "expanded transform corpus session has no eligible binding")
                continue
            if spec is None:
                raise RealDiagnosticExecutorRefusal(
                    "expanded transform eligible binding lacks corpus session")
            if tuple(map(str, spec.candidate_ids)) != eligible:
                raise RealDiagnosticExecutorRefusal(
                    "expanded transform learner candidate roster differs")
            key = (str(spec.asset), int(spec.trading_day), str(spec.session_id))
            if key in metadata:
                raise RealDiagnosticExecutorRefusal(
                    "expanded transform session identity is duplicated")
            metadata[key] = rows
        return MappingProxyType(metadata)

    @staticmethod
    def _expanded_session_metadata_identity(
        metadata: Mapping[tuple[str, int, str], tuple[Any, ...]],
    ) -> str:
        """Bind the exact learner/diagnostic intersection and transform atoms."""
        rows = []
        for key in sorted(metadata):
            values = metadata[key]
            rows.append({
                "session": list(key),
                "bindings": [(
                    str(row.candidate_id), str(row.asset),
                    int(row.trading_day), str(row.compliance_status),
                    str(row.teacher_status), int(row.phase_open_ts_ns),
                    int(row.phase_close_ts_ns), int(row.sane_ceiling_units),
                    int(row.multiplier),
                ) for row in values],
            })
        return _sha({
            "schema": "entry-v2-expanded-session-metadata-v1",
            "domain_law": "diagnostic-clear-ready-exact-learner-intersection-v1",
            "sessions": rows,
        })

    def export_acceptance_numerical_artifacts(self) -> Mapping[str, bytes]:
        """Export the accepted architecture authorization, never a warm start.

        These bytes authorize exact arm/schema behavior and permit an
        interrupted acceptance boundary to be audited/restored.  Held E1/E2
        still instantiate fresh production models and cannot consume these
        competence checkpoints as initialization.
        """
        from safetensors.torch import save
        if set(self.arm_rows) != set(CANONICAL_ARMS) or self._arms is None:
            raise RealDiagnosticExecutorRefusal(
                "acceptance arm authorization is not complete")
        expected_evidence = {
            "acceptance/evidence/raw-fidelity.json",
            *(f"acceptance/evidence/arm-{arm}.json" for arm in CANONICAL_ARMS),
        }
        if set(self._acceptance_component_evidence) != expected_evidence:
            raise RealDiagnosticExecutorRefusal(
                "acceptance measured evidence payload census differs")
        payloads: dict[str, bytes] = dict(self._acceptance_component_evidence)
        arms = {}
        for arm in CANONICAL_ARMS:
            raw = save({name: value.detach().cpu().contiguous()
                        for name, value in self._arms[arm].state_dict().items()})
            payloads[f"acceptance/{arm}.competence.safetensors"] = raw
            arms[arm] = {
                "checkpoint_sha256": _sha_bytes(raw),
                "row_manifest_sha256": self.arm_rows[arm].manifest_sha256,
                "representation_sha256": self.arm_rows[arm].representation_sha256,
                "evidence_sha256": _sha_bytes(
                    payloads[f"acceptance/evidence/arm-{arm}.json"]),
            }
        authorization = {
            "schema": "entry-v2-accepted-arm-authorization-v1",
            "arms": arms,
            "canonical_arms": list(CANONICAL_ARMS),
            "event_schema_sha256": self.schema.sha256,
            "selected_horizon_schema_sha256": SELECTED_HORIZON_SCHEMA_SHA256,
            "selected_horizon_target_law_sha256":
                SELECTED_HORIZON_TARGET_LAW_SHA256,
            "raw_fidelity_evidence_sha256": _sha_bytes(
                payloads["acceptance/evidence/raw-fidelity.json"]),
            "competence_only_discard_before_held": True,
        }
        authorization["receipt_sha256"] = _sha(authorization)
        payloads["acceptance/arm-authorization.json"] = _canonical_json_bytes(
            authorization)
        manifest = {"schema": "entry-v2-acceptance-numerical-manifest-v1",
                    "payload_sha256": {name: _sha_bytes(raw)
                                       for name, raw in sorted(payloads.items())}}
        manifest["receipt_sha256"] = _sha(manifest)
        payloads["acceptance/manifest.json"] = _canonical_json_bytes(manifest)
        return MappingProxyType(payloads)

    def restore_acceptance_numerical_artifacts(
            self, payloads: Mapping[str, bytes]) -> None:
        """Strict-load accepted competence evidence without fitting."""
        from safetensors.torch import load as load_safetensors
        required = {f"acceptance/{arm}.competence.safetensors"
                    for arm in CANONICAL_ARMS} | {
                    "acceptance/arm-authorization.json", "acceptance/manifest.json",
                    "acceptance/evidence/raw-fidelity.json",
                    *(f"acceptance/evidence/arm-{arm}.json"
                      for arm in CANONICAL_ARMS),
                    }
        if set(payloads) != required:
            raise RealDiagnosticExecutorRefusal(
                "acceptance numerical payload census differs")
        manifest = json.loads(payloads["acceptance/manifest.json"])
        hashes = {name: _sha_bytes(raw) for name, raw in payloads.items()
                  if name != "acceptance/manifest.json"}
        if manifest.get("payload_sha256") != hashes:
            raise RealDiagnosticExecutorRefusal(
                "acceptance numerical payload hashes differ")
        authorization = json.loads(payloads[
            "acceptance/arm-authorization.json"])
        if (authorization.get("canonical_arms") != list(CANONICAL_ARMS)
                or authorization.get("event_schema_sha256") != self.schema.sha256
                or authorization.get("selected_horizon_schema_sha256")
                != SELECTED_HORIZON_SCHEMA_SHA256):
            raise RealDiagnosticExecutorRefusal(
                "acceptance authorization identity differs")
        models = self._new_model_registry()
        for arm in CANONICAL_ARMS:
            raw = payloads[f"acceptance/{arm}.competence.safetensors"]
            if _sha_bytes(raw) != authorization["arms"][arm]["checkpoint_sha256"]:
                raise RealDiagnosticExecutorRefusal(
                    f"acceptance {arm} checkpoint hash differs")
            models[arm].load_state_dict(load_safetensors(raw), strict=True)
            evidence_name = f"acceptance/evidence/arm-{arm}.json"
            if (_sha_bytes(payloads[evidence_name]) !=
                    authorization["arms"][arm]["evidence_sha256"]):
                raise RealDiagnosticExecutorRefusal(
                    f"acceptance {arm} evidence hash differs")
        if (_sha_bytes(payloads["acceptance/evidence/raw-fidelity.json"])
                != authorization["raw_fidelity_evidence_sha256"]):
            raise RealDiagnosticExecutorRefusal(
                "acceptance raw-fidelity evidence hash differs")
        self._arms = models
        self._acceptance_component_evidence = {
            name: payloads[name] for name in required if "/evidence/" in name}
        self._accepted_arm_authorization = MappingProxyType(authorization)

    def export_stage_evidence(self, stage: str) -> Mapping[str, bytes]:
        """Return complete typed evidence blobs for immutable publication."""
        if stage == "M8":
            receipt = dict(self.rehearse_held_chain())
            e1 = dict(receipt["e1r"]); e2 = dict(receipt["e2r"])
            ledger = dict(e1["probe_screen"]["ledger"])
            matrix = dict(e2["arm_head_matrix"]["matrix"])
            expected_paths = {f"{arm}:{kind}" for arm in CANONICAL_ARMS
                              for kind in DECISIONS}
            if (set(ledger) != {probe.probe_id for probe in PROBE_REGISTRY}
                    or set(matrix) != expected_paths):
                raise RealDiagnosticExecutorRefusal("M8 evidence census differs")
            payloads = dict(self._m8_payloads)
            if (not payloads or any(not name.startswith("M8/")
                                    for name in payloads)):
                raise RealDiagnosticExecutorRefusal(
                    "M8 numerical payload capture is absent or misnamed")
            payloads.update({
                "M8/rehearsal-evidence.json": _canonical_json_bytes(receipt),
                "M8/objective-ledger.json": _canonical_json_bytes({
                    "schema": "entry-v2-m8-objective-ledger-v1",
                    "real_objective_ids": sorted(ledger),
                    "twin_objective_ids": sorted(shuffled_probe_for(
                        probe, available=self.stage.diagnostic_corpus.sessions[0]
                        .atlas.shuffled_probes).probe_id for probe in PROBE_REGISTRY),
                    "rows": ledger,
                    "twin_rows": {shuffled_probe_for(
                        probe, available=self.stage.diagnostic_corpus.sessions[0]
                        .atlas.shuffled_probes).probe_id: {
                            "source_probe_id": probe.probe_id,
                            "checkpoint_sha256": ledger[probe.probe_id].get(
                                "twin_checkpoint"),
                            "path_receipt_sha256": ledger[probe.probe_id].get(
                                "twin_path"),
                            "status": ledger[probe.probe_id]["status"]}
                        for probe in PROBE_REGISTRY}}),
                "M8/path-evidence.json": _canonical_json_bytes({
                    "schema": "entry-v2-m8-five-arm-ten-path-v1",
                    "arms": list(CANONICAL_ARMS), "paths": matrix,
                    "factored_fit": e2["arm_head_matrix"]["factored_fit"],
                    "selected_horizon_normalizer":
                        e2["arm_head_matrix"]["selected_horizon_normalizer"],
                    "validation_roster":
                        e2["arm_head_matrix"]["validation_roster"]}),
                "M8/restart-contract.json": _canonical_json_bytes({
                    "schema": "entry-v2-m8-numerical-restart-contract-v2",
                    "strict_second_process_reload_required": True,
                    "same_selected_full_learner_required": True,
                    "model_formats": ["safetensors", "cbm"],
                    "array_format": "npz",
                    "postprocessor_format": "canonical-json",
                    "source_tree_sha256": receipt["source_tree_sha256"],
                    "diagnostic_semantic_identity_sha256": (
                        None if self.loaded is None else
                        self.loaded.corpus.receipt.get(
                            "semantic_identity_sha256")),
                    "one_load_id": (None if self.loaded is None
                                    else self.loaded.one_load_id),
                }),
            })
            real_ids = sorted(ledger)
            twin_ids = sorted(shuffled_probe_for(
                probe, available=self.stage.diagnostic_corpus.sessions[0]
                .atlas.shuffled_probes).probe_id for probe in PROBE_REGISTRY)
            objective_payloads = {
                objective: list(self._m8_objective_payloads.get(objective, ()))
                for objective in (*real_ids, *twin_ids)
            }
            # A typed unavailable objective has no fitted checkpoint.  Its
            # exact ledger row is nevertheless part of the restart census and
            # is the only honest payload for that slot.
            for objective, names in objective_payloads.items():
                if not names:
                    names.append("M8/objective-ledger.json")
            path_payloads = {
                f"{arm}:{kind}": list(self._m8_path_payloads.get(
                    f"E2r/paths/{arm}/{kind}", ()))
                for arm in CANONICAL_ARMS for kind in DECISIONS
            }
            arm_payloads = {
                arm: {role: list(self._m8_arm_payloads[arm][role])
                      for role in ("initial", "pointwise", "best", "final")}
                for arm in CANONICAL_ARMS
            }
            if (any(not names for names in path_payloads.values())
                    or any(not names for row in arm_payloads.values()
                           for names in row.values())
                    or len(self._m8_pretext_payloads) < 3
                    or not self._m8_selected_transition_payloads):
                raise RealDiagnosticExecutorRefusal(
                    "M8 captured learner/path/pretext census is incomplete")
            manifest = {"schema": "entry-v2-m8-evidence-manifest-v2",
                        "source_tree_sha256": receipt["source_tree_sha256"],
                        "arms": list(CANONICAL_ARMS),
                        "selectable_paths": sorted(expected_paths),
                        "real_objective_ids": real_ids,
                        "twin_objective_ids": twin_ids,
                        "payload_roles": {
                            "rehearsal": ["M8/rehearsal-evidence.json"],
                            "objectives": ["M8/objective-ledger.json"],
                            "arm_head_paths": ["M8/path-evidence.json"],
                            "pretexts": list(self._m8_pretext_payloads),
                            "selected_full_transition": list(dict.fromkeys(
                                self._m8_selected_transition_payloads)),
                            "restart_contract": ["M8/restart-contract.json"]},
                        "arm_checkpoint_payloads": arm_payloads,
                        "path_payloads": path_payloads,
                        "objective_payloads": objective_payloads,
                        "timing_receipt_location": "timing/",
                        "payload_sha256": {name: _sha_bytes(raw)
                                           for name, raw in sorted(payloads.items())}}
            manifest["receipt_sha256"] = _sha(manifest)
            payloads["M8/manifest.json"] = _canonical_json_bytes(manifest)
            return MappingProxyType(payloads)
        artifact = self.export_stage_numerical_artifacts(stage)
        return MappingProxyType(dict(artifact.payloads))

    def restore_fit_only_m8_artifacts(self, payloads: Mapping[str, bytes]) -> str:
        """Strict-load the complete fit-only learner in a fresh process.

        Hash validation alone is insufficient: every PyTorch/CatBoost model is
        reconstructed, every persisted policy postprocessor is executed, and
        the bounded inference canaries must reproduce before held data may be
        opened.
        """
        from safetensors.torch import load as load_safetensors
        from .neural_sufficiency_stage_persistence import _validate_m8_evidence
        from .neural_sufficiency_source_manifest import \
            held_rehearsal_source_tree_sha256
        import catboost

        supplied = dict(payloads)
        _validate_m8_evidence(supplied)
        manifest = json.loads(supplied["M8/manifest.json"])
        rehearsal = json.loads(supplied["M8/rehearsal-evidence.json"])
        restart = json.loads(supplied["M8/restart-contract.json"])
        if (manifest["source_tree_sha256"] != held_rehearsal_source_tree_sha256()
                or rehearsal["source_tree_sha256"] != manifest["source_tree_sha256"]
                or self.loaded is None
                or restart["one_load_id"] != self.loaded.one_load_id
                or restart["diagnostic_semantic_identity_sha256"]
                    != self.loaded.corpus.receipt.get("semantic_identity_sha256")):
            raise RealDiagnosticExecutorRefusal(
                "M8 restart belongs to different source/corpus semantics")

        def archive(name: str) -> dict[str, np.ndarray]:
            with np.load(io.BytesIO(supplied[name]), allow_pickle=False) as value:
                return {key: np.array(value[key], copy=True) for key in value.files}

        # Both E1r pretexts must instantiate from their frozen checkpoints.
        pretext_count = 0
        for name in manifest["payload_roles"]["pretexts"]:
            if not name.endswith("checkpoint.npz"):
                continue
            values = archive(name); metadata = values["metadata"].astype(str).tolist()
            if len(metadata) != 6:
                raise RealDiagnosticExecutorRefusal("M8 pretext metadata differs")
            state = {key.removeprefix("state/"): value for key, value in values.items()
                     if key.startswith("state/")}
            checkpoint = StagePretextCheckpoint(
                metadata[0], metadata[1], int(metadata[2]),
                tuple(map(int, values["category_sizes"].tolist())),
                values["location"], values["scale"],
                values["constant_zero_mask"], MappingProxyType(state),
                metadata[3], metadata[4], metadata[5],
            )
            model, _ = checkpoint.load_model("cpu")
            if any(not np.array_equal(
                    tensor.detach().cpu().numpy(), state[key])
                   for key, tensor in model.state_dict().items()):
                raise RealDiagnosticExecutorRefusal(
                    f"M8 pretext strict reload differs: {name}")
            pretext_count += 1
        if pretext_count != 2:
            raise RealDiagnosticExecutorRefusal("M8 pretext checkpoint census differs")

        # Reload every materialized real/twin objective and execute its saved
        # input/output canary.  Unavailable objectives are typed in the ledger
        # and intentionally own no checkpoint.
        shared_plane_name = next(name for name in
            manifest["payload_roles"]["pretexts"]
            if name.endswith("shared-probe-plane.npz"))
        shared_plane = archive(shared_plane_name)
        objective_models = 0
        for objective, names in manifest["objective_payloads"].items():
            for model_name in (name for name in names
                               if name.endswith(".safetensors")):
                probe_model = AtlasProbeNet()
                probe_model.load_state_dict(load_safetensors(
                    supplied[model_name]), strict=True)
                probe_model.eval()
                canary_name = (model_name.rsplit("/", 1)[0]
                               + "/canary.npz")
                if canary_name not in names:
                    canary_name = None
                if canary_name is None:
                    raise RealDiagnosticExecutorRefusal(
                        f"M8 {objective} objective canary is absent")
                canary = archive(canary_name)
                if "/E1r/" in model_name:
                    x = shared_plane["canary_normalized"]
                else:
                    x = canary["normalized"]
                expected_key = ("twin_output" if model_name.endswith(
                    "/twin.safetensors") else "real_output")
                with torch.no_grad():
                    actual = probe_model(torch.from_numpy(x)).cpu().numpy()
                if not np.array_equal(actual, canary[expected_key]):
                    raise RealDiagnosticExecutorRefusal(
                        f"M8 {objective} objective inference canary differs")
                objective_models += 1
        if objective_models < 2:
            raise RealDiagnosticExecutorRefusal(
                "M8 contains no executable real/twin objective pair")

        canary_input_name = "M8/E2r/arms/canary-input.npz"
        canary_meta_name = "M8/E2r/arms/canary-input.json"
        canary_input = archive(canary_input_name)
        canary_meta = json.loads(supplied[canary_meta_name])
        g7 = rehearsal["g7"]
        arm_matrix = rehearsal["e2r"]["arm_head_matrix"]
        selected_arm = str(g7["selected_arm"])
        selected_head = str(g7["selected_head"])
        models = self._new_model_registry()
        arm_canary_states: dict[str, np.ndarray] = {}
        for arm in CANONICAL_ARMS:
            row = manifest["arm_checkpoint_payloads"][arm]
            # Initial, pointwise and final bytes must all load into the same
            # declared architecture.  The final state is then exercised.
            for role in ("initial", "pointwise", "best", "final"):
                for name in row[role]:
                    if (name.endswith(".safetensors")
                            and not name.endswith("objective-head.safetensors")):
                        models[arm].load_state_dict(
                            load_safetensors(supplied[name]), strict=True)
            objective_name = next(name for name in row["final"]
                                  if name.endswith("objective-head.safetensors"))
            objective_head = torch.nn.Linear(512, PADDED_OUTPUT_WIDTH)
            objective_head.load_state_dict(
                load_safetensors(supplied[objective_name]), strict=True)
            final_name = next(name for name in row["final"]
                              if name.endswith("/final.safetensors"))
            models[arm].load_state_dict(
                load_safetensors(supplied[final_name]), strict=True)
            if (arm == selected_arm
                    and _full_learner_checkpoint_sha256(
                        models[arm], objective_head)
                        != g7["e2r_checkpoint_sha256"]):
                raise RealDiagnosticExecutorRefusal(
                    "M8 selected E2r full checkpoint identity differs")
            model = models[arm].to(self.device).eval()
            with torch.no_grad(), self._held_autocast():
                memory = model.encoder(
                    torch.from_numpy(canary_input["continuous"]).to(self.device),
                    torch.from_numpy(canary_input["categorical"]).to(self.device),
                    torch.from_numpy(canary_input["cutoffs"]).to(self.device),
                    receive_clock_ns=torch.from_numpy(
                        canary_input["clock"]).to(self.device),
                    candidate_decision_ts_ns=torch.from_numpy(
                        canary_input["decisions"]).to(self.device),
                    asset_idx=C.ASSET_INDEX[canary_meta["asset"]],
                )
                output = model.head(
                    memory,
                    torch.from_numpy(canary_input["candidate_features"]).to(self.device),
                    torch.from_numpy(canary_input["context_values"]).to(self.device),
                    torch.from_numpy(canary_input["context_type_ids"]).to(self.device),
                    torch.from_numpy(canary_input["context_valid"]).to(self.device),
                    C.ASSET_INDEX[canary_meta["asset"]],
                    static_features=(torch.from_numpy(
                        canary_input["static_features"]).to(self.device)
                        if arm in ("L1", "M1") else None),
                )
            output_name = next(name for name in row["final"]
                               if name.endswith("canary-output.npz"))
            expected = archive(output_name)
            expected_objective = expected.pop("objective_output", None)
            actual = _output_canary_arrays(output)
            with torch.no_grad():
                actual_objective = objective_head(
                    torch.from_numpy(actual["decision_state"])).float().cpu().numpy()
            if (set(actual) != set(expected)
                    or any(not np.array_equal(actual[key], expected[key])
                           for key in expected)
                    or expected_objective is None
                    or not np.array_equal(actual_objective,
                                          expected_objective)):
                raise RealDiagnosticExecutorRefusal(
                    f"M8 {arm} full-learner inference canary differs")
            arm_canary_states[arm] = np.ascontiguousarray(
                actual["decision_state"], np.float32)
            model.cpu()

        # The selected learner is trained independently at the earlier E1r
        # wall after E2r has frozen arm/head/objective identity.  It is not one
        # of the five E2r arm checkpoints above, so strict-load and execute it
        # explicitly rather than accepting its hashes as transition evidence.
        selected_probe = str(arm_matrix["selected_objective"])
        selected_learner_objective = str(g7["selected_objective"])
        selected_names = list(manifest["payload_roles"][
            "selected_full_transition"])

        def selected_name(suffix: str) -> str:
            matches = [name for name in selected_names if name.endswith(suffix)]
            if len(matches) != 1:
                raise RealDiagnosticExecutorRefusal(
                    f"M8 selected transition {suffix} census differs")
            return matches[0]

        selected_model_name = selected_name("/final.safetensors")
        selected_objective_name = selected_name("/objective-head.safetensors")
        selected_input_name = selected_name("/canary-input.npz")
        selected_output_name = selected_name("/canary-output.npz")
        selected_training_name = selected_name("/training.json")
        selected_training = json.loads(supplied[selected_training_name])
        selected_model = self._new_model_registry()[selected_arm]
        selected_model.load_state_dict(
            load_safetensors(supplied[selected_model_name]), strict=True)
        selected_objective = torch.nn.Linear(512, PADDED_OUTPUT_WIDTH)
        selected_objective.load_state_dict(
            load_safetensors(supplied[selected_objective_name]), strict=True)
        selected_composite = _full_learner_checkpoint_sha256(
            selected_model, selected_objective)
        if (selected_training.get("schema")
                != "entry-v2-fit-only-selected-full-training-v1"
                or selected_training.get("chronology") != "E1r"
                or selected_training.get("fit_wall") != 20210709
                or selected_training.get("arm") != selected_arm
                or selected_training.get("decision_kind") != selected_head
                or selected_training.get("selected_probe") != selected_probe
                or selected_training.get("learner_objective")
                    != selected_learner_objective
                or selected_training.get("learner_law_sha256")
                    != g7["learner_law_sha256"]
                or selected_training.get("final_checkpoint_sha256")
                    != g7["e1r_checkpoint_sha256"]
                or selected_composite != g7["e1r_checkpoint_sha256"]):
            raise RealDiagnosticExecutorRefusal(
                "M8 selected E1r training/checkpoint identity differs")
        selected_input = archive(selected_input_name)
        selected_expected = archive(selected_output_name)
        selected_expected_objective = selected_expected.pop(
            "objective_output", None)
        selected_model = selected_model.to(self.device).eval()
        with torch.no_grad(), self._held_autocast():
            selected_memory = selected_model.encoder(
                torch.from_numpy(selected_input["continuous"]).to(self.device),
                torch.from_numpy(selected_input["categorical"]).to(self.device),
                torch.from_numpy(selected_input["cutoffs"]).to(self.device),
                receive_clock_ns=torch.from_numpy(
                    selected_input["clock"]).to(self.device),
                candidate_decision_ts_ns=torch.from_numpy(
                    selected_input["decisions"]).to(self.device),
                asset_idx=int(selected_input["asset_index"][0]),
            )
            selected_output = selected_model.head(
                selected_memory,
                torch.from_numpy(selected_input[
                    "candidate_features"]).to(self.device),
                torch.from_numpy(selected_input[
                    "context_values"]).to(self.device),
                torch.from_numpy(selected_input[
                    "context_type_ids"]).to(self.device),
                torch.from_numpy(selected_input[
                    "context_valid"]).to(self.device),
                int(selected_input["asset_index"][0]),
                static_features=(torch.from_numpy(selected_input[
                    "static_features"]).to(self.device)
                    if selected_arm in ("L1", "M1") else None),
            )
        selected_actual = _output_canary_arrays(selected_output)
        with torch.no_grad():
            selected_actual_objective = selected_objective(
                torch.from_numpy(selected_actual[
                    "decision_state"])).float().cpu().numpy()
        if (set(selected_actual) != set(selected_expected)
                or any(not np.array_equal(selected_actual[key],
                                          selected_expected[key])
                       for key in selected_expected)
                or selected_expected_objective is None
                or not np.array_equal(selected_actual_objective,
                                      selected_expected_objective)):
            raise RealDiagnosticExecutorRefusal(
                "M8 selected E1r full-learner inference canary differs")
        selected_canary_state = np.ascontiguousarray(
            selected_actual["decision_state"], np.float32)
        selected_model.cpu(); selected_objective.cpu()

        # Native CatBoost bytes are loaded and executed rather than merely
        # checksummed.  Each arm config freezes a cross-asset prediction canary.
        catboost_models = 0
        with tempfile.TemporaryDirectory(prefix="entry-v2-m8-reload-") as directory:
            directory_path = Path(directory)
            for arm in CANONICAL_ARMS:
                config_name = f"M8/E2r/arms/{arm}/catboost/config.json"
                config = json.loads(supplied[config_name])
                if config.get("canary_state_sha256") != _sha_bytes(
                        arm_canary_states[arm].tobytes()):
                    raise RealDiagnosticExecutorRefusal(
                        f"M8 {arm} CatBoost canary state differs")
                for name, digest in config["models"].items():
                    if _sha_bytes(supplied[name]) != digest:
                        raise RealDiagnosticExecutorRefusal(
                            f"M8 CatBoost model hash differs: {name}")
                    path = directory_path / Path(name).name
                    path.write_bytes(supplied[name])
                    family = "action" if name.endswith("-action.cbm") else "pairlogit"
                    model = (catboost.CatBoostClassifier() if family == "action"
                             else catboost.CatBoostRanker())
                    model.load_model(str(path))
                    prediction = (model.predict_proba(arm_canary_states[arm])[:, 1]
                                  if family == "action" else
                                  model.predict(arm_canary_states[arm]))
                    asset = Path(name).stem.split("-", 1)[0]
                    expected = np.asarray(
                        config["canary_predictions"][f"{asset}-{family}"],
                        np.float64)
                    if not np.array_equal(np.asarray(prediction, np.float64), expected):
                        raise RealDiagnosticExecutorRefusal(
                            f"M8 {arm}/{asset}/{family} inference canary differs")
                    catboost_models += 1
            if selected_head == "catboost":
                selected_config_name = selected_name("/catboost/config.json")
                selected_config = json.loads(supplied[selected_config_name])
                if (selected_config.get("schema")
                        != "entry-v2-m8-selected-catboost-model-set-v1"
                        or selected_config.get("arm") != selected_arm
                        or selected_config.get("chronology") != "E1r"
                        or selected_config.get("canary_state_sha256")
                            != _sha_bytes(selected_canary_state.tobytes())):
                    raise RealDiagnosticExecutorRefusal(
                        "M8 selected E1r CatBoost canary identity differs")
                for name, digest in selected_config.get("models", {}).items():
                    if (name not in selected_names
                            or _sha_bytes(supplied[name]) != digest):
                        raise RealDiagnosticExecutorRefusal(
                            f"M8 selected CatBoost model hash differs: {name}")
                    path = directory_path / ("selected-" + Path(name).name)
                    path.write_bytes(supplied[name])
                    ranker = catboost.CatBoostRanker()
                    ranker.load_model(str(path))
                    prediction = np.asarray(
                        ranker.predict(selected_canary_state), np.float64)
                    asset = Path(name).stem.split("-", 1)[0]
                    expected = np.asarray(selected_config[
                        "canary_predictions"][f"{asset}-pairlogit"], np.float64)
                    if not np.array_equal(prediction, expected):
                        raise RealDiagnosticExecutorRefusal(
                            f"M8 selected {asset} PairLogit canary differs")
                    catboost_models += 1
        expected_catboost_models = len(CANONICAL_ARMS) * len(C.ASSETS) * 2
        if selected_head == "catboost":
            expected_catboost_models += len(C.ASSETS)
        if catboost_models != expected_catboost_models:
            raise RealDiagnosticExecutorRefusal(
                "M8 CatBoost model census differs")

        # Reconstruct every mapper + positive-slope calibrator and replay its
        # persisted full score plane.  This proves the executable decision
        # surface, not just the underlying model files.
        def validate_postprocessor(path_key: str, names: Sequence[str]) -> None:
            by_base = {Path(name).name: name for name in names}
            required = {"mapper.json", "calibrator.json", "thresholds.json",
                        "scores.npz", "replay.json"}
            if not required.issubset(by_base):
                raise RealDiagnosticExecutorRefusal(
                    f"M8 {path_key} postprocessor census differs")
            mapper_row = json.loads(supplied[by_base["mapper.json"]])
            calibrator_row = json.loads(supplied[by_base["calibrator.json"]])
            scores = archive(by_base["scores.npz"])
            mapper = FrozenLogisticBindingMapper()
            mapper.coef_ = np.asarray(mapper_row["coef"], np.float64)
            mapper.intercept_ = float(mapper_row["intercept"])
            mapper.fit_ids_sha256 = mapper_row["fit_ids_sha256"]
            mapper.weight_receipt_sha256 = mapper_row["weight_receipt_sha256"]
            mapper.calibrator = PositiveSlopePlatt(
                float(calibrator_row["slope"]),
                float(calibrator_row["intercept"]),
                calibrator_row["fit_ids_sha256"],
                calibrator_row["parameter_sha256"],
            )
            probability, _ = mapper.predict(_decision_binding(scores["raw_score"]))
            if (mapper.parameter_sha256 != mapper_row["parameter_sha256"]
                    or mapper.calibrator.parameter_sha256
                        != calibrator_row["parameter_sha256"]
                    or not np.array_equal(probability, scores["probability"])):
                raise RealDiagnosticExecutorRefusal(
                    f"M8 {path_key} postprocessor inference differs")

        policy_paths = 0
        for path_key, names in manifest["path_payloads"].items():
            validate_postprocessor(path_key, names)
            policy_paths += 1
        if policy_paths != len(CANONICAL_ARMS) * len(DECISIONS):
            raise RealDiagnosticExecutorRefusal("M8 policy path census differs")
        validate_postprocessor(
            f"G7:E1r:{selected_arm}:{selected_head}", selected_names)

        proof = _sha({
            "schema": "entry-v2-m8-strict-reload-proof-v1",
            "manifest_sha256": manifest["receipt_sha256"],
            "source_tree_sha256": manifest["source_tree_sha256"],
            "pretext_checkpoints": pretext_count,
            "objective_models": objective_models,
            "arm_models": len(CANONICAL_ARMS),
            "selected_e1r_full_models": 1,
            "catboost_models": catboost_models,
            "policy_paths": policy_paths,
            "selected_e1r_policy_paths": 1,
            "separate_process_strict_reload": True,
        })
        self._m8_payloads = supplied
        self._m8_reload_proof_sha256 = proof
        return proof

    def export_stage_numerical_artifacts(self, stage: str):
        """Freeze restartable numerical state without refitting/reselection."""
        from .neural_sufficiency_stage_persistence import StageNumericalArtifacts
        if stage == "E1":
            if self._held_engine is None or self._held_engine.e1 is None:
                raise RealDiagnosticExecutorRefusal("E1 numerical state is not frozen")
            pretexts = self._build_held_probe_plane()[5]
            payloads: dict[str, bytes] = {}
            for fit in pretexts:
                checkpoint = fit.checkpoint
                arrays = {f"state/{key}": value for key, value in
                          checkpoint.model_state.items()}
                arrays.update({"location": checkpoint.location,
                    "scale": checkpoint.scale,
                    "constant_zero_mask": checkpoint.constant_zero_mask,
                    "category_sizes": np.asarray(checkpoint.category_sizes, np.int64),
                    "metadata": np.asarray([checkpoint.stage_id, checkpoint.objective_id,
                        str(checkpoint.continuous_width), checkpoint.input_normalizer_sha256,
                        checkpoint.initialization_sha256, checkpoint.checkpoint_sha256])})
                payloads[f"pretext/{checkpoint.objective_id}.checkpoint.npz"] = _npz_bytes(arrays)
            contexts = self._build_held_probe_plane()[4]
            payloads["fit-contexts.json"] = _canonical_json_bytes({
                "schema": "entry-v2-e1-fit-contexts-v1", "contexts": _jsonable({
                    probe: {f"{a}:{d}": value for (a, d), value in rows.items()}
                    for probe, rows in contexts.items()})})
            payloads["fit-ledger.json"] = _canonical_json_bytes({
                "schema": "entry-v2-e1-fit-ledger-v1",
                "screens": {probe: {"availability": row.availability,
                    "path_availability": row.path_availability,
                    "real": row.real_checkpoint_sha256,
                    "twin": row.twin_checkpoint_sha256}
                    for probe, row in self._held_engine.e1.screen_by_probe.items()}})
            payloads["screens.json"] = _canonical_json_bytes({
                "schema": "entry-v2-e1-complete-screen-evidence-v1",
                "registry_probe_ids": [probe.probe_id for probe in PROBE_REGISTRY],
                "screens": _jsonable(self._held_engine.e1.screen_by_probe)})
            hashes = {name: _sha_bytes(raw) for name, raw in payloads.items()}
            payloads["finalists.json"] = _canonical_json_bytes({
                "schema": "entry-v2-e1-finalists-v1",
                "finalists": list(self._held_engine.e1.finalists),
                "finalist_receipt_sha256": self._held_engine.e1.finalist_receipt_sha256,
                "payload_sha256": hashes})
            return StageNumericalArtifacts.freeze("E1", payloads)
        if stage != "E2" or self._held_engine is None or self._held_engine.e2 is None:
            raise RealDiagnosticExecutorRefusal("E2 numerical state is not frozen")
        winner = self._held_engine.e2
        key = (winner.confirmation.probe_id, winner.confirmation.arm,
               winner.confirmation.decision_kind)
        candidate = self._held_candidate_payloads[key]
        source = candidate["payloads"]
        names = {"encoder.safetensors", "head.safetensors",
            "objective-head.safetensors", "mapper.json", "calibrator.json",
            "thresholds.json", "capacity.json"}
        if winner.confirmation.decision_kind == "catboost":
            names |= {name for name in source if name.startswith("catboost-")}
        payloads = {name: source[name] for name in names}
        selected_horizon = json.loads(source["normalizers.json"])["selected_horizon"]
        payloads["selected-horizon-normalizer.json"] = _canonical_json_bytes(
            selected_horizon)
        validation_days = sorted(self._held_normalizer["validation_days"])
        validation_roster = {
            "schema": "entry-v2-e2-validation-roster-v1",
            "days": validation_days,
            "candidate_ids": sorted(cid for cid, day in zip(
                self._held_arm_rows[winner.confirmation.arm].candidate_ids,
                self._held_arm_rows[winner.confirmation.arm].day)
                if int(day) in set(validation_days)),
            "weighting": "UNWEIGHTED_VALID_ROWS",
            "selected_horizon_normalizer_sha256":
                selected_horizon["receipt_sha256"],
        }
        validation_roster["receipt_sha256"] = _sha(validation_roster)
        payloads["validation-roster.json"] = _canonical_json_bytes(validation_roster)
        payloads["arm-authorization.json"] = _canonical_json_bytes({
            "schema": "entry-v2-e2-arm-authorization-v1",
            "selected_arm": winner.confirmation.arm,
            "five_arm_checkpoint_sha256": {
                arm: _sha_bytes(module_state_bytes(self._held_models[arm]))
                for arm in CANONICAL_ARMS},
            "ten_path_receipt_sha256": dict(self._held_path_receipts),
            "base_fit_arms": ["C0", "L0", "M1"],
            "byte_copies": {"C1": "C0", "L1": "L0"},
            "training_receipt_sha256": self._held_training_receipt,
            "grouped_receipt_sha256": self._held_grouped_receipt})
        resume_only = {name: raw.hex() for name, raw in source.items()
                       if name not in names}
        resume_common = {
            "resume_bundle_payload_hex": resume_only,
            "held_training_receipt_sha256": self._held_training_receipt,
            "held_grouped_receipt_sha256": self._held_grouped_receipt,
            "threshold_selections": {
                asset: asdict(candidate["threshold_selections"][asset])
                for asset in C.ASSETS
            },
        }
        if winner.confirmation.arm == "C0":
            payloads["compact-targets.npz"] = _npz_bytes({
                "candidate_ids": np.asarray([], dtype="<U1"),
                "a0_no_target": np.asarray([1], np.uint8)})
            payloads["compact-context.json"] = _canonical_json_bytes({
                "schema": "entry-v2-e2-compact-context-v1",
                "row_manifest_sha256": candidate["target_manifest"],
                "fit_context_sha256": _sha({"context": "A0.none"}),
                **resume_common})
        else:
            handoff = self.compact_atlas_handoff(None, "REAL", 0)
            payloads["compact-targets.npz"] = _npz_bytes({
                "candidate_ids": handoff.candidate_ids, "values": handoff.target.values,
                "coordinate_mask": handoff.target.coordinate_mask,
                "validity_mask": handoff.target.validity_mask})
            payloads["compact-context.json"] = _canonical_json_bytes({
                "schema": "entry-v2-e2-compact-context-v1",
                "row_manifest_sha256": handoff.row_manifest_sha256,
                "fit_context_sha256": handoff.fit_context_sha256,
                **resume_common})
        hashes = {name: _sha_bytes(raw) for name, raw in payloads.items()}
        payloads["selection.json"] = _canonical_json_bytes({
            "schema": "entry-v2-e2-selection-v1", "probe_id": winner.confirmation.probe_id,
            "arm": winner.confirmation.arm,
            "decision_head_kind": winner.confirmation.decision_kind,
            "selection_hashes": dict(winner.selection_hashes),
            "objective_freeze_receipt_sha256": winner.objective_freeze_receipt_sha256,
            "payload_sha256": hashes})
        return StageNumericalArtifacts.freeze("E2", payloads)

    def restore_stage_numerical_artifacts(
            self, engine, numerical: Mapping[str, Any], *,
            acceptance_artifacts: Mapping[str, bytes] | None = None) -> None:
        """Adopt strict-loaded boundary bytes; never invoke a fitter."""
        self._ensure_loaded()
        if self.schema is None:
            manifest = RealDataExactNeuralDiagnosticExecutor._derive_manifest(
                self.loaded.corpus)
            self._prepare(manifest)
        # Numerical restoration must see the same causal corpus window that
        # produced the persisted boundary.  Reopen only the missing adjacent
        # windows through the same durable owner; never refit or rebuild the
        # accepted competence population.
        if "E1" in numerical and self._loaded_maximum_d8 < 20211231:
            self._extend_held_window(20211231)
        if "E2" in numerical and self._loaded_maximum_d8 < 20220630:
            self._extend_held_window(20220630)
        self._held_engine = engine
        if acceptance_artifacts is not None:
            self.restore_acceptance_numerical_artifacts(acceptance_artifacts)
        self._restored_stage_payloads = MappingProxyType({
            stage: MappingProxyType(dict(artifact.payloads))
            for stage, artifact in numerical.items()})
        if "E1" in self._restored_stage_payloads:
            # Recreate only deterministic target materialization and frozen
            # checkpoint encodings.  `_build_held_probe_plane` detects the
            # restored checkpoints above and executes no optimizer.
            self._build_held_probe_plane()
        if "E2" not in self._restored_stage_payloads:
            return
        from safetensors.torch import load as load_safetensors
        from .atlas_probe_model import FrozenLogisticBindingMapper
        from .train import ThresholdFunnel, ThresholdSelection
        restored = self._restored_stage_payloads["E2"]
        selection = json.loads(restored["selection.json"])
        context = json.loads(restored["compact-context.json"])
        arm = str(selection["arm"]); decision_kind = str(
            selection["decision_head_kind"])
        if arm not in CANONICAL_ARMS or decision_kind not in DECISIONS:
            raise RealDiagnosticExecutorRefusal("restored E2 selection is unsupported")
        numerical_evidence_names = {
            "compact-targets.npz", "compact-context.json", "selection.json",
            "selected-horizon-normalizer.json", "validation-roster.json",
            "arm-authorization.json",
        }
        bundle = {name: raw for name, raw in restored.items()
                  if name not in numerical_evidence_names}
        try:
            bundle.update({name: bytes.fromhex(raw) for name, raw in
                           context["resume_bundle_payload_hex"].items()})
        except (KeyError, TypeError, ValueError) as exc:
            raise RealDiagnosticExecutorRefusal(
                "restored E2 bundle continuation bytes are invalid") from exc
        from .neural_winner_artifact import required_payloads_for_head
        if set(bundle) != set(required_payloads_for_head(decision_kind)):
            raise RealDiagnosticExecutorRefusal(
                "restored E2 continuation bundle payload set differs")
        models = self._new_model_registry(); model = models[arm]
        model.encoder.load_state_dict(load_safetensors(bundle["encoder.safetensors"]),
                                      strict=True)
        model.head.load_state_dict(load_safetensors(bundle["head.safetensors"]),
                                   strict=True)
        self._held_models = MappingProxyType({arm: model})
        objective = torch.nn.Linear(512, PADDED_OUTPUT_WIDTH)
        objective_state = {name.removeprefix("projection."): value for name, value in
                           load_safetensors(bundle["objective-head.safetensors"]).items()}
        objective.load_state_dict(objective_state, strict=True); objective.eval()
        self._held_objective_heads = MappingProxyType({arm: objective})
        normalizer = json.loads(bundle["normalizers.json"])
        restored_horizon = json.loads(restored["selected-horizon-normalizer.json"])
        if (restored_horizon != normalizer["selected_horizon"]
                or restored_horizon["target_schema_sha256"]
                != SELECTED_HORIZON_SCHEMA_SHA256
                or restored_horizon["target_law_sha256"]
                != SELECTED_HORIZON_TARGET_LAW_SHA256):
            raise RealDiagnosticExecutorRefusal(
                "restored selected-horizon normalizer differs")
        validation_roster = json.loads(restored["validation-roster.json"])
        if validation_roster.get("weighting") != "UNWEIGHTED_VALID_ROWS":
            raise RealDiagnosticExecutorRefusal(
                "restored validation weighting differs")
        self._held_horizon_normalizer = MappingProxyType({
            "location": np.asarray(restored_horizon["location"], np.float64),
            "scale": np.asarray(restored_horizon["scale"], np.float64),
            "receipt_sha256": restored_horizon["receipt_sha256"],
            "fit_manifest_sha256": restored_horizon.get(
                "fit_manifest_sha256", ""),
        })
        self._held_normalizer = MappingProxyType({
            "location": np.asarray(normalizer["held_train_event_location"], np.float64),
            "scale": np.asarray(normalizer["held_train_event_scale"], np.float64),
            "constant": np.asarray(normalizer["held_train_event_constant"], bool),
            "static_location": np.asarray(
                normalizer["held_train_static_location"], np.float64),
            "static_scale": np.asarray(normalizer["held_train_static_scale"], np.float64),
            "static_constant": np.asarray(
                normalizer["held_train_static_constant"], bool),
            "validation_days": frozenset(validation_roster["days"]),
            "receipt_sha256": _sha_bytes(bundle["normalizers.json"]),
        })
        mapper_doc = json.loads(bundle["mapper.json"])
        calibrator_doc = json.loads(bundle["calibrator.json"])
        mapper = FrozenLogisticBindingMapper()
        mapper.coef_ = np.asarray(mapper_doc["coef"], np.float64)
        mapper.intercept_ = float(mapper_doc["intercept"])
        mapper.fit_ids_sha256 = str(mapper_doc["fit_ids_sha256"])
        mapper.calibrator = PositiveSlopePlatt(
            float(calibrator_doc["slope"]), float(calibrator_doc["intercept"]),
            str(calibrator_doc["fit_ids_sha256"]),
            _sha_bytes(np.asarray([calibrator_doc["slope"],
                                   calibrator_doc["intercept"]], np.float64).tobytes()))
        if _sha_bytes(bundle["mapper.json"]) != engine.e2.confirmation.mapper_sha256:
            raise RealDiagnosticExecutorRefusal("restored E2 mapper hash differs")
        self._winner_mapper = mapper
        self._held_training_receipt = str(context["held_training_receipt_sha256"])
        self._held_grouped_receipt = str(context["held_grouped_receipt_sha256"])
        target_manifest = str(context["row_manifest_sha256"])
        try:
            threshold_selections = MappingProxyType({
                asset: ThresholdSelection(
                    asset=str(context["threshold_selections"][asset]["asset"]),
                    threshold=float(context["threshold_selections"][asset]["threshold"]),
                    asset_days=int(context["threshold_selections"][asset]["asset_days"]),
                    usd_per_asset_day=float(
                        context["threshold_selections"][asset]["usd_per_asset_day"]),
                    usd_per_trade=float(
                        context["threshold_selections"][asset]["usd_per_trade"]),
                    max_drawdown_usd=float(
                        context["threshold_selections"][asset]["max_drawdown_usd"]),
                    drawdown_p90_usd=float(
                        context["threshold_selections"][asset]["drawdown_p90_usd"]),
                    trades=int(context["threshold_selections"][asset]["trades"]),
                    feasible_thresholds=int(
                        context["threshold_selections"][asset]["feasible_thresholds"]),
                    funnel=tuple(ThresholdFunnel(**row) for row in
                        context["threshold_selections"][asset]["funnel"]),
                ) for asset in C.ASSETS
            })
        except (KeyError, TypeError, ValueError) as exc:
            raise RealDiagnosticExecutorRefusal(
                "restored E2 threshold evidence is invalid") from exc
        key = (str(selection["probe_id"]), arm, decision_kind)
        self._held_candidate_payloads = {key: {
            "payloads": MappingProxyType(bundle), "mapper": mapper,
            "objective_head": objective, "target_manifest": target_manifest,
            "contexts": MappingProxyType({}),
            "economics": engine.e2.confirmation.economics,
            "capacity_payload": json.loads(bundle["capacity.json"])["per_asset"],
            "threshold_selections": threshold_selections,
            "decision_model": None,
        }}
        if decision_kind == "catboost":
            import catboost
            rankers = {}
            with tempfile.TemporaryDirectory(prefix="entry-v2-restore-ranker-") as directory:
                for asset in C.ASSETS:
                    path = Path(directory) / f"{asset}.cbm"
                    path.write_bytes(bundle[f"catboost-{asset}.cbm"])
                    ranker = catboost.CatBoostRanker(); ranker.load_model(str(path))
                    rankers[asset] = SimpleNamespace(ranker_model=ranker)
            self._held_catboost = {arm: SimpleNamespace(
                assets=MappingProxyType(rankers))}
            self._held_candidate_payloads[key]["decision_model"] = \
                self._held_catboost[arm]
        self._selected_objective_probe_id = str(selection["probe_id"])
        self._selected_objective_sha256 = engine.e2.confirmation.selected_objective_sha256
        self.policy_kind = decision_kind
        self.mapper_sha256 = engine.e2.confirmation.mapper_sha256
        self.calibrator_sha256 = engine.e2.confirmation.calibrator_sha256
        self.thresholds_sha256 = engine.e2.confirmation.thresholds_sha256
        self.capacity_authority_sha256 = engine.e2.confirmation.capacity_authority_sha256
        if engine.artifacts is not None:
            # A resumed report-only E3 already owns immutable winner/fold
            # bytes, but the same live durable corpus owner must still advance
            # through the exact E3 boundary before the later development
            # extension.  This preserves the receipt-proven E3 prefix without
            # retraining or reading report labels through an E2-sized view.
            if self._loaded_maximum_d8 < 20221230:
                self._extend_held_window(20221230)
            self._held_artifacts = engine.artifacts

    def stage_public_result(self, stage: str):
        if self._held_engine is None:
            raise RealDiagnosticExecutorRefusal("held stage engine is absent")
        return {"E1": self._held_engine.e1, "E2": self._held_engine.e2,
                "E3": self._held_engine.artifacts}[stage]

    def export_winner_bundle_payloads(self, adoption_sha256: str) -> Mapping[str, bytes]:
        if not _valid_adoption(adoption_sha256) or self._held_engine is None:
            raise RealDiagnosticExecutorRefusal("winner bundle adoption identity is invalid")
        if self._winner_adoption_sha256 not in (None, adoption_sha256):
            raise RealDiagnosticExecutorRefusal("winner artifacts cannot be relabeled")
        self._winner_adoption_sha256 = adoption_sha256
        return self._held_engine.export_bundle_payloads()

    def export_primary_e3_fold(self, adoption_sha256: str) -> Path:
        if (not _valid_adoption(adoption_sha256) or self._held_engine is None
                or adoption_sha256 != self._winner_adoption_sha256):
            raise RealDiagnosticExecutorRefusal("primary E3 adoption identity is invalid")
        return self._held_engine.export_primary_e3()

    @property
    def event_transform(self) -> ExpandedEventTransform:
        return self.expanded_transform

    def context_corpus(self, substrate_root: str | Path):
        """Return the already-open corpus stage; a second builder is forbidden."""
        self._ensure_loaded()
        if Path(substrate_root).resolve() != C.CACHE_ROOT.resolve():
            raise RealDiagnosticExecutorRefusal("winner substrate differs from one-load root")
        if self._loaded_maximum_d8 < C.DEVELOPMENT_END_D8:
            self._extend_held_window(C.DEVELOPMENT_END_D8)
            if self._loaded_maximum_d8 != C.DEVELOPMENT_END_D8:
                raise RealDiagnosticExecutorRefusal(
                    "forward corpus extension did not reach the development boundary")
        return self.stage.corpus_stage

    def select_compact_objective(self, probe_id: str,
                                 selected_objective_sha256: str | None = None) -> None:
        if probe_id not in self._atlas_fit_context_by_probe_session:
            raise RealDiagnosticExecutorRefusal("objective has no fitted target authority")
        self._selected_objective_probe_id = probe_id
        self._selected_objective_sha256 = selected_objective_sha256

    def compact_atlas_handoff(self, fold=None, control_name: str = "real",
                              shuffle_seed: int = 0) -> CompactAtlasHandoff:
        if self._selected_objective_probe_id is None:
            raise RealDiagnosticExecutorRefusal("held E2 has not frozen a selected objective")
        fit_days = tuple(sorted(set(getattr(fold, "fit_days", ()))))
        allowed_days = set(fit_days) | set(getattr(fold, "inner_days", ()))
        contexts = (self._held_context_factory(max(fit_days))[
            self._selected_objective_probe_id] if fit_days else
            self._atlas_fit_context_by_probe_session[self._selected_objective_probe_id])
        normalized = {key: ({} if value is None else value)
                      for key, value in contexts.items()}
        handoff = build_compact_atlas_handoff(
            self.stage.diagnostic_corpus, self._selected_objective_probe_id, normalized,
            selected_objective_sha256=self._selected_objective_sha256,
            fit_days=fit_days, control_name="REAL")
        if allowed_days:
            bindings_all = {row.candidate_id: row for row in
                            self.stage.diagnostic_corpus.bindings}
            take = np.asarray([bindings_all[cid].trading_day in allowed_days
                               for cid in handoff.candidate_ids], bool)
            selected = np.flatnonzero(take)
            ids = np.ascontiguousarray(handoff.candidate_ids[selected])
            target = _target_take(handoff.target, selected)
            fit_candidate_ids = [cid for cid in ids.tolist()
                if bindings_all[cid].trading_day in set(fit_days)]
            candidate_manifest = C.object_sha256(fit_candidate_ids)
            row_manifest = _sha({"neutral_atoms": handoff.atlas_aggregate_sha256,
                "fit_context": handoff.fit_context_sha256,
                "fit_days": fit_days, "candidate_manifest": candidate_manifest,
                "objective": handoff.objective_sha256})
            handoff = replace(handoff, candidate_ids=ids, target=target,
                row_manifest_sha256=row_manifest,
                target_candidate_manifest_sha256=candidate_manifest,
                target_control_sha256=_sha({"schema":
                    "entry-v2-selected-target-control-v1",
                    "row_manifest_sha256": row_manifest, "control": "REAL"}))
        if (not fit_days and self._held_artifacts is not None
                and handoff.row_manifest_sha256 !=
                self._held_artifacts.target_row_manifest_sha256):
            raise RealDiagnosticExecutorRefusal(
                "compact target rows differ from frozen winner payload")
        if str(control_name).upper() in {"REAL", "PROPHET"}:
            prophet_control = _sha({"schema": "entry-v2-selected-target-control-v1",
                "row_manifest_sha256": handoff.row_manifest_sha256,
                "control": "PROPHET"})
            handoff = replace(handoff, target_control_sha256=prophet_control)
            receipt = MappingProxyType({
                "schema": "entry-v2-selected-target-control-v2",
                "control": "PROPHET",
                "target_control_sha256": handoff.target_control_sha256,
                "target_candidate_manifest_sha256":
                    handoff.target_candidate_manifest_sha256,
                "marginals_preserved": True})
            return replace(handoff, shuffle_receipt=receipt)
        if not str(control_name).upper().startswith("SHUFFLED"):
            raise RealDiagnosticExecutorRefusal("unknown winner target control")
        bindings = {row.candidate_id: row for row in self.stage.diagnostic_corpus.bindings}
        ids = np.asarray(handoff.candidate_ids, str)
        if any(cid not in bindings for cid in ids):
            raise RealDiagnosticExecutorRefusal("shuffled handoff lacks binding metadata")
        assets = np.asarray([bindings[cid].asset for cid in ids])
        days = np.asarray([bindings[cid].trading_day for cid in ids], np.int64)
        recipient = np.asarray([bindings[cid].action_loss_mask for cid in ids], bool)
        permutation = stage_global_recipient_fixed_permutation(
            np.full(len(ids), "FOLD"), assets, days, recipient,
            seed=int(shuffle_seed),
        )
        shuffled = permute_probe_target_recipient_fixed(handoff.target, permutation)
        permutation_sha = C.object_sha256(permutation.tolist())
        source_sha = _sha_bytes(np.ascontiguousarray(handoff.target.values).tobytes())
        shuffled_sha = _sha_bytes(np.ascontiguousarray(shuffled.values).tobytes())
        strata = [f"{assets[i]}:{days[i]}:{int(recipient[i])}" for i in range(len(ids))]
        supported = permutation >= 0
        zero_row_sha = _sha_bytes(np.zeros_like(shuffled.values[0]).tobytes())
        control_hash = _sha({"schema": "entry-v2-selected-target-control-v1",
            "row_manifest_sha256": handoff.row_manifest_sha256,
            "control": str(control_name), "seed": int(shuffle_seed),
            "permutation_sha256": permutation_sha, "source": source_sha,
            "shuffled": shuffled_sha})
        receipt = {"schema": "entry-v2-selected-target-control-v2",
            "control": "SHUFFLED",
            "training_control": str(control_name).upper(),
            "target_control_sha256": control_hash,
            "target_candidate_manifest_sha256":
                handoff.target_candidate_manifest_sha256,
            "seed": int(shuffle_seed),
            "strata_law": "split-asset-day-recipient-v1",
            "permutation_sha256": permutation_sha,
            "source_content_sha256": source_sha,
            "shuffled_content_sha256": shuffled_sha,
            "recipient_mask_sha256": _sha_bytes(recipient.tobytes()),
            "supported_rows": int(supported.sum()),
            "unsupported_rows": int((~supported).sum()),
            "unsupported_zero_row_sha256": zero_row_sha,
            "marginals_preserved": True,
            "derangement": bool(supported.any() and np.all(
                permutation[supported] != np.flatnonzero(supported))),
            "candidate_ids": ids.tolist(), "permutation": permutation.tolist(),
            "strata": strata, "recipient_mask": recipient.astype(np.uint8).tolist(),
            "source_row_sha256": [_sha_bytes(np.ascontiguousarray(
                handoff.target.values[i]).tobytes()) for i in range(len(ids))],
            "shuffled_row_sha256": [_sha_bytes(np.ascontiguousarray(
                shuffled.values[i]).tobytes()) for i in range(len(ids))]}
        if not receipt["derangement"]:
            raise RealDiagnosticExecutorRefusal("recipient-fixed shuffle is not a derangement")
        return replace(handoff, target=shuffled, target_control_sha256=control_hash,
                       already_shuffled=True,
                       shuffle_receipt=MappingProxyType(receipt))

    @property
    def receipt_sha256(self) -> str:
        loaded = self._ensure_loaded()
        return _sha({"one_load_id": loaded.one_load_id,
                     "transform": self.expanded_transform.transform_law_sha256,
                     "objective": self._selected_objective_probe_id,
                     "policy_kind": self.policy_kind})

    @property
    def target_provider_factory_sha256(self) -> str:
        return _sha({"callable": "compact_atlas_handoff", "version": 1})

    @property
    def policy_factory_sha256(self) -> str | None:
        return getattr(self, "_bundle_policy_factory_sha256", None)

    @property
    def policy_factory(self):
        if self._selected_policy_factory is None:
            raise RealDiagnosticExecutorRefusal("E2 selected policy has not been frozen")
        return (self.entry_v2_selected_direct_policy_factory
                if self.policy_kind == "direct_neural"
                else self.entry_v2_selected_catboost_policy_factory)

    def select_winner_policy(self, kind: str, factory) -> None:
        if kind not in {"direct_neural", "catboost"} or not callable(factory):
            raise RealDiagnosticExecutorRefusal("E2 selected policy authority is invalid")
        if self.policy_kind is not None:
            raise RealDiagnosticExecutorRefusal("E2 selected policy is already frozen")
        self.policy_kind = kind; self._selected_policy_factory = factory

    def install_bundle_policy_factory(self, factory, factory_sha256: str) -> None:
        if (self.policy_kind not in {"direct_neural", "catboost"}
                or not callable(factory) or not _valid_adoption(factory_sha256)):
            raise RealDiagnosticExecutorRefusal("bundle policy factory identity is invalid")
        self._selected_policy_factory = factory
        self._bundle_policy_factory_sha256 = factory_sha256

    def entry_v2_selected_direct_policy_factory(self, *args, **kwargs):
        if self.policy_kind != "direct_neural":
            raise RealDiagnosticExecutorRefusal("direct policy was not selected")
        return self._selected_policy_factory(*args, **kwargs)

    def entry_v2_selected_catboost_policy_factory(self, *args, **kwargs):
        if self.policy_kind != "catboost":
            raise RealDiagnosticExecutorRefusal("CatBoost policy was not selected")
        return self._selected_policy_factory(*args, **kwargs)

    def transfer_winner_resources(self, adoption_sha256: str):
        if self.ownership_transferred or self._resource_closed:
            raise RealDiagnosticExecutorRefusal("winner resource ownership is unavailable")
        if adoption_sha256 != self._winner_adoption_sha256 \
                or self._selected_objective_probe_id is None \
                or self._winner_mapper is None or self.policy_kind is None \
                or not self.expanded_transform._frozen:
            raise RealDiagnosticExecutorRefusal(
                "held selection/policy/transform are not frozen for ownership transfer")
        self.ownership_transferred = True
        return self

    def _fit_only_corpus_preflight(self, stage) -> None:
        """Refuse unattainable rehearsal laws before atlas finalization.

        This is intentionally computed from the already-built causal corpus,
        teacher and replay planes.  It opens no EventPack, initializes no GPU,
        and runs before the expensive candidate-level atlas is assembled.  A
        quota or chronology that the perfect candidate-set ceiling cannot
        satisfy is therefore a construction error, never a paid learner
        failure.
        """
        corpus = stage.corpus
        if int(corpus.receipt["corpus_window"]["maximum_d8"]) != 20210930:
            raise RealDiagnosticExecutorRefusal(
                "fit-only preflight requires the exact September corpus wall")
        examples: dict[str, Any] = {}
        asset: list[str] = []
        day: list[int] = []
        phase: list[str] = []
        decision: list[int] = []
        candidate_id: list[str] = []
        action: list[int] = []
        recipient: list[bool] = []
        close_value: list[float] = []
        for spec in corpus.sessions:
            joined = corpus.teacher.join_training(spec.examples)
            for example, label in joined:
                cid = str(example.candidate_id)
                if cid in examples:
                    raise RealDiagnosticExecutorRefusal(
                        "fit-only preflight candidate identity is duplicated")
                examples[cid] = example
                candidate_id.append(cid); asset.append(str(example.asset))
                day.append(int(example.trading_day)); phase.append(str(example.phase))
                decision.append(int(example.decision_ts_ns))
                action.append(int(bool(label.take_target)))
                recipient.append(bool(label.action_loss_mask))
                close_value.append(float(label.cert_close_usd))
        ids = np.asarray(candidate_id, str)
        assets = np.asarray(asset, str)
        days = np.asarray(day, np.int64)
        phases = np.asarray(phase, str)
        decisions = np.asarray(decision, np.int64)
        actions = np.asarray(action, np.int8)
        recipients = np.asarray(recipient, bool)
        close_values = np.asarray(close_value, np.float64)
        # Replay may legitimately retain diagnostic-only outcomes whose day
        # has no CLEAR+READY learner row.  The learner roster must be covered
        # exactly by replay, but inventing ordinary rows for those extra
        # diagnostic outcomes would violate the A-018 coverage boundary.
        if (not len(ids) or len(set(ids.tolist())) != len(ids)
                or not set(ids).issubset(set(corpus.replay.outcomes))):
            raise RealDiagnosticExecutorRefusal(
                "fit-only preflight learner/outcome candidate census differs")

        def class_census(mask: np.ndarray) -> dict[str, dict[str, int]]:
            return {name: {
                "positive": int(np.sum(mask & recipients & (assets == name)
                                       & (actions == 1))),
                "negative": int(np.sum(mask & recipients & (assets == name)
                                       & (actions == 0))),
            } for name in C.ASSETS}

        # The bounded 192-row architecture rehearsal consumes 12/10/10 rows
        # per class and asset.  Prove every cell before any tensor/atlas work.
        competence = {}
        for name in C.ASSETS:
            competence[name] = {}
            for label in (0, 1):
                counts = []
                for lower, upper, quota in (
                        (20210531, 20210730, 12),
                        (20210801, 20210831, 10),
                        (20210901, 20210930, 10)):
                    count = int(np.sum((assets == name) & recipients
                                       & (actions == label)
                                       & (days >= lower) & (days <= upper)))
                    if count < quota:
                        raise RealDiagnosticExecutorRefusal(
                            f"{name} lacks fit-only competence support before atlas")
                    counts.append(count)
                competence[name][str(label)] = counts

        # Acceptance PairLogit is an explicitly day/phase temporal ranker,
        # never an equal-timestamp choice ranker.  Its independent depth slice
        # requires 44 real pairable groups for each asset over the complete
        # fit-only wall.
        full_fit = (days >= 20210531) & (days <= 20210930)
        depth_groups = {}
        for name in C.ASSETS:
            local = full_fit & (assets == name)
            manifest = canonical_phase_pair_manifest(
                ids, assets, days, phases, decisions, actions, recipients, local)
            depth_groups[name] = int(manifest.group_count)
            if manifest.group_count < 44:
                raise RealDiagnosticExecutorRefusal(
                    f"{name} lacks 44 fit-only day/phase PairLogit groups")

        role_census: dict[str, Any] = {}
        oracle_blocks: dict[str, Any] = {}
        for rehearsal in ("E1r", "E2r"):
            roles = {role: _rehearsal_mask(days, rehearsal, role)
                     for role in ("FIT", "PLATT", "THRESHOLD", "FORWARD")}
            if any(not np.any(mask) for mask in roles.values()) or any(
                    np.any(roles[left] & roles[right])
                    for index, left in enumerate(roles)
                    for right in tuple(roles)[index + 1:]):
                raise RealDiagnosticExecutorRefusal(
                    f"{rehearsal} chronology is empty or overlapping")
            fit_classes = class_census(roles["FIT"])
            platt_classes = class_census(roles["PLATT"])
            if any(min(fit_classes[name].values()) <= 0
                   or min(platt_classes[name].values()) <= 0
                   for name in C.ASSETS):
                raise RealDiagnosticExecutorRefusal(
                    f"{rehearsal} fit/Platt lacks an all-asset binary class")
            role_census[rehearsal] = {
                role: {"candidate_count": int(mask.sum()),
                       "class_by_asset": class_census(mask)}
                for role, mask in roles.items()}

            if rehearsal == "E2r":
                fit_days = sorted(set(map(int, days[roles["FIT"]])))
                validation_count = max(1, int(np.ceil(.1 * len(fit_days))))
                validation_days = set(fit_days[-validation_count:])
                train = roles["FIT"] & ~np.isin(days, tuple(validation_days))
                pair_groups = {}
                for name in C.ASSETS:
                    manifest = canonical_phase_pair_manifest(
                        ids, assets, days, phases, decisions, actions,
                        recipients, train & (assets == name))
                    pair_groups[name] = int(manifest.group_count)
                    if manifest.group_count < 1:
                        raise RealDiagnosticExecutorRefusal(
                            f"E2r {name} has no train-only day/phase pair")
                role_census[rehearsal]["TRAIN_AFTER_VALIDATION"] = {
                    "validation_days": sorted(validation_days),
                    "pair_groups_by_asset": pair_groups,
                }

            for role in ("THRESHOLD", "FORWARD"):
                lower, upper = _rehearsal_bounds(rehearsal, role)
                expected = tuple(session for session in
                    corpus.replay.expected_sessions
                    if lower <= int(session.trading_day) <= upper)
                selected = roles[role] & (close_values >= C.MIN_EXPECTANCY_USD)
                arrivals = tuple(ScoredArrival(
                    examples[str(cid)], EntryScore(
                        str(cid), str(name), examples[str(cid)].decision_ts_ns,
                        f"fit-only-preflight:{rehearsal}:{role}",
                        0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, False),
                    corpus.replay.outcomes[str(cid)])
                    for cid, name in zip(ids[selected], assets[selected]))
                if not arrivals or not expected:
                    raise RealDiagnosticExecutorRefusal(
                        f"{rehearsal} {role} candidate ceiling is empty")
                ceiling = candidate_ceiling(arrivals, expected_sessions=expected)
                by_asset = {row.asset: row for row in ceiling.evaluation.by_asset}
                asset_rows = {}
                for name in C.ASSETS:
                    measured = by_asset.get(name)
                    days_for_asset = tuple(row for row in
                        ceiling.evaluation.asset_day_results if row.asset == name)
                    if measured is None or not days_for_asset:
                        raise RealDiagnosticExecutorRefusal(
                            f"{rehearsal} {role} ceiling lacks {name}")
                    feasibility = threshold_feasibility(
                        trades=measured.trades,
                        usd_per_trade=measured.usd_per_trade,
                        max_drawdown_usd=measured.max_drawdown_usd,
                        days_with_trades=sum(row.trades > 0 for row in days_for_asset),
                        eligible_days=len(days_for_asset))
                    asset_rows[name] = {
                        "trades": measured.trades,
                        "total_pnl_usd": measured.total_pnl_usd,
                        "usd_per_trade": measured.usd_per_trade,
                        "usd_per_asset_day": measured.usd_per_asset_day,
                        "max_drawdown_usd": measured.max_drawdown_usd,
                        "drawdown_p90_usd": measured.drawdown_p90_usd,
                        "days_with_trades": sum(row.trades > 0
                                                for row in days_for_asset),
                        "eligible_days": len(days_for_asset),
                        "feasible": feasibility.feasible,
                        "reasons": list(feasibility.reasons),
                        "feasibility_sha256": feasibility.receipt_sha256,
                    }
                    if not feasibility.feasible:
                        raise RealDiagnosticExecutorRefusal(
                            f"{rehearsal} {role} is unattainable for {name}")
                block = {
                    "schedule_sha256": ceiling.schedule_sha256,
                    "selected_candidate_count": len(ceiling.selected_candidate_ids),
                    "by_asset": asset_rows,
                }
                block["receipt_sha256"] = _sha(block)
                oracle_blocks[f"{rehearsal}.{role}"] = block
        core = {
            "schema": "entry-v2-fit-only-real-corpus-preflight-v1",
            "status": "PASS", "maximum_d8": 20210930,
            "candidate_count": len(ids),
            "candidate_manifest_sha256": _sha(ids.tolist()),
            "pair_semantics": "asset-day-phase",
            "equal_timestamp_claim": False,
            "competence_support": competence,
            "depth_pair_groups_by_asset": depth_groups,
            "chronology": {stage_name: {
                role: list(bounds) for role, bounds in
                fit_only_rehearsal_windows(stage_name).items()}
                for stage_name in ("E1r", "E2r")},
            "role_census": role_census,
            "candidate_ceiling": oracle_blocks,
        }
        core["receipt_sha256"] = _sha(core)
        self._fit_only_preflight = MappingProxyType(core)

    def _ensure_loaded(self) -> LoadedFitOnlyResources:
        if self.stage is not None:
            assert self.loaded is not None
            return self.loaded
        self.stage = build_production_diagnostic_stage(
            C.CACHE_ROOT, array_cache=self.cache,
            maximum_d8=self._loaded_maximum_d8,
            durable_store=self.durable_store,
            cold_process_pool=self.cold_process_pool,
            pre_finalize_validator=self._fit_only_corpus_preflight)
        diagnostic = self.stage.diagnostic_corpus
        receipt = diagnostic.receipt
        preflight_blocks = (self._fit_only_preflight or {}).get(
            "candidate_ceiling", {})
        expected_blocks = {
            "E1r.THRESHOLD", "E1r.FORWARD",
            "E2r.THRESHOLD", "E2r.FORWARD",
        }
        if (not isinstance(preflight_blocks, Mapping)
                or set(preflight_blocks) != expected_blocks
                or any(not isinstance(preflight_blocks[name], Mapping)
                       or set(preflight_blocks[name].get("by_asset", {}))
                            != set(C.ASSETS)
                       or not _is_sha(preflight_blocks[name].get(
                           "receipt_sha256"))
                       for name in expected_blocks)):
            raise RealDiagnosticExecutorRefusal(
                "fit-only preflight candidate-ceiling surface is incomplete")
        self._fit_only_ceiling_rows = MappingProxyType({
            name: MappingProxyType({
                asset: MappingProxyType(dict(preflight_blocks[name]["by_asset"][asset]))
                for asset in C.ASSETS
            }) for name in sorted(expected_blocks)
        })
        self._fit_only_ceiling_receipts = MappingProxyType({
            name: str(preflight_blocks[name]["receipt_sha256"])
            for name in sorted(expected_blocks)
        })
        if (receipt.get("truth_end_d8") != self._loaded_maximum_d8
                or receipt.get("derived_end_d8") != self._loaded_maximum_d8
                or receipt.get("corpus_maximum_d8") != self._loaded_maximum_d8
                or receipt.get("diagnostic_planes_disk_backed") is not True
                or receipt.get("post_e3_truth_released") is not True
                or receipt.get("selected_objective_target_provider_ready") is not True
                or receipt.get("compact_atlas_session_count") != len(diagnostic.sessions)
                or int(receipt.get("candidate_suffix_rows_visited", -1)) != 0):
            raise RealDiagnosticExecutorRefusal(
                "diagnostic retention/handoff receipt differs from production law"
            )
        semantic_identity = diagnostic.receipt.get("semantic_identity_sha256")
        if not _is_sha(semantic_identity):
            raise RealDiagnosticExecutorRefusal(
                "diagnostic semantic restart identity is absent")
        expanded_metadata = self._expanded_session_metadata()
        if not expanded_metadata:
            raise RealDiagnosticExecutorRefusal(
                "expanded learner/diagnostic session intersection is empty")
        expanded_metadata_sha256 = self._expanded_session_metadata_identity(
            expanded_metadata)
        self._expanded_session_metadata_sha256 = expanded_metadata_sha256
        preflight_core = dict(self._fit_only_preflight or {})
        preflight_core.pop("receipt_sha256", None)
        preflight_core["learner_diagnostic_session_algebra_sha256"] = \
            expanded_metadata_sha256
        preflight_core["learner_session_count"] = len(expanded_metadata)
        preflight_core["diagnostic_session_count"] = len(diagnostic.sessions)
        preflight_core["diagnostic_only_session_count"] = (
            len(diagnostic.sessions) - len(expanded_metadata)
        )
        preflight_core["receipt_sha256"] = _sha(preflight_core)
        self._fit_only_preflight = MappingProxyType(preflight_core)
        # Physical opens, durable hits, memory admission and byte counters are
        # intentionally excluded.  They distinguish cold from warm timing,
        # not the learner population that must survive the process boundary.
        one_load_id = _sha({
            "schema": "entry-v2-one-load-semantic-identity-v1",
            "diagnostic_semantic_identity_sha256": semantic_identity,
            "model_input_contract_sha256":
                diagnostic.corpus.model_input_binding.input_contract_sha256,
            "window_maximum_d8": self._loaded_maximum_d8,
            "h2_permit": False,
        })
        self._loaded_window_id = str(self.stage.lifecycle_provenance[
            "cumulative_window_identity_sha256"])
        sources: dict[str, Any] = {}
        for source in (
            *(spec.source for spec in self.stage.corpus_stage.corpus.sessions),
            *(session.observed.source for session in diagnostic.sessions),
        ):
            key = f"{source.asset}:{source.d8}"
            prior = sources.get(key)
            if (prior is not None and prior.receipt.canonical_bytes() != (
                    source.receipt.canonical_bytes())):
                raise RealDiagnosticExecutorRefusal(
                    "one-load source union contains conflicting identities")
            sources[key] = source
        keys = set(sources)
        measured_opens: dict[str, int] = {}
        durable_hit: dict[str, bool] = {}
        for key, source in sources.items():
            measured = source.measurements.snapshot()
            opens = int(measured["physical_full_pack_opens"])
            fills = int(measured["model_array_physical_fills"])
            if (opens, fills) not in ((0, 0), (1, 1)):
                raise RealDiagnosticExecutorRefusal(
                    "one-load source open/fill counters are not exact")
            measured_opens[key] = opens
            durable_hit[key] = opens == 0
        for session in diagnostic.sessions:
            key = f"{session.observed.source.asset}:{session.observed.source.d8}"
            if (int(session.observed.receipt["physical_full_pack_opens"])
                    != measured_opens[key]
                    or bool(session.observed.receipt[
                        "verified_session_durable_hit"]) != durable_hit[key]):
                raise RealDiagnosticExecutorRefusal(
                    "diagnostic/source one-load counters differ")
        if (set(measured_opens) != keys or set(durable_hit) != keys
                or any(measured_opens[key] != (0 if durable_hit[key] else 1)
                       for key in keys)):
            raise RealDiagnosticExecutorRefusal(
                "one-load source union lacks exact measured open counters")
        lifecycle = self.stage.lifecycle_provenance
        timing_keys = (
            "schema", "cold_or_warm", "warm_corpus_ready",
            "physical_full_pack_opens", "model_array_physical_fills",
            "verified_session_durable_hits",
            "verified_session_cold_publishes",
            "diagnostic_plane_durable_hits",
            "diagnostic_plane_bytes_materialized",
            "diagnostic_plane_bytes_reused",
            "corpus_ready_elapsed_milestone_source",
            "cumulative_window_identity_sha256",
        )
        if any(key not in lifecycle for key in timing_keys):
            raise RealDiagnosticExecutorRefusal(
                "diagnostic lifecycle timing provenance is incomplete")
        self._fit_only_timing_provenance = MappingProxyType({
            key: lifecycle[key] for key in timing_keys
        })
        # All source conversion/process publication is now complete for this
        # window.  Only here may the production process initialize CUDA.
        self._initialize_accelerator()
        assert self.device is not None
        assert self.determinism_receipt_sha256 is not None
        self.loaded = LoadedFitOnlyResources(
            diagnostic, one_load_id, 4, True, True, True,
            self.effective_memory_available_bytes, self.cache.capacity_bytes,
            True, True, True, 0,
            MappingProxyType(dict(sorted(measured_opens.items()))),
            self.resource_admission,
            self._fit_only_preflight or MappingProxyType({}),
        )
        return self.loaded

    def load_once(self) -> LoadedFitOnlyResources:
        if self._load_claimed:
            raise RealDiagnosticExecutorRefusal("production diagnostic stage already loaded")
        self._load_claimed = True
        return self._ensure_loaded()

    def fit_only_timing_provenance(self) -> Mapping[str, Any]:
        """Return measured stage-first cold/warm/open/byte counters."""
        self._ensure_loaded()
        return self._fit_only_timing_provenance

    def _select_pairlogit_depth_ids(self) -> tuple[frozenset[str], str]:
        """Freeze the independent 264-row/132-group A-013 depth slice.

        This is intentionally not the 192-row arm-overfit manifest.  A-019
        selects 44 day/phase groups per asset from the complete <=2021-09-30
        fit-only wall.  The former 16/14/14 construction quotas were neither
        learner chronology nor a support law and were impossible for real SI
        (only 12 pairable groups existed in the first block).  Each selected
        group contributes one supervised positive and its nearest-time
        supervised negative.  These are honestly named day/phase pairs; they
        are not represented as equal-timestamp choice groups.
        """
        bindings = {row.candidate_id: row for row in self.stage.diagnostic_corpus.bindings}
        grouped: dict[tuple[str, int, str], list[tuple[int, str, bool]]] = {}
        for spec in self.stage.corpus_stage.corpus.sessions:
            if not 20210531 <= int(spec.trading_day) <= 20210930:
                continue
            for example in spec.examples:
                row = bindings.get(example.candidate_id)
                if row is None or not row.action_loss_mask:
                    continue
                grouped.setdefault((spec.asset, spec.trading_day,
                                    str(example.phase)), []).append(
                    (int(example.decision_ts_ns), example.candidate_id,
                     bool(row.action_target)))
        selected: list[str] = []; receipt_rows = []
        for asset in C.ASSETS:
            candidates = []
            for key, members in grouped.items():
                if key[0] != asset:
                    continue
                positive = sorted((x for x in members if x[2]),
                                  key=lambda x: (x[0], x[1]))
                negative = sorted((x for x in members if not x[2]),
                                  key=lambda x: (x[0], x[1]))
                if not positive or not negative:
                    continue
                pos = positive[0]
                neg = min(negative, key=lambda x: (
                    abs(x[0] - pos[0]), x[0], x[1]))
                candidates.append((key[1], key[2], pos, neg))
            candidates.sort(key=lambda x: (
                x[0], x[1], x[2][0], x[2][1], x[3][1]))
            quota = 44
            if len(candidates) < quota:
                raise RealDiagnosticExecutorRefusal(
                    f"{asset} lacks {quota} fit-only PairLogit day/phase groups")
            # Day-stratified deterministic coverage rather than a clustered
            # first-N slice.  Rounding is stable and duplicate-free because
            # quota <= population.
            positions = np.linspace(
                0, len(candidates) - 1, quota, dtype=np.int64)
            if len(set(map(int, positions))) != quota:
                raise RealDiagnosticExecutorRefusal(
                    "PairLogit quota sampler duplicated a group")
            for index in positions:
                day, phase, pos, neg = candidates[int(index)]
                selected.extend((pos[1], neg[1]))
                receipt_rows.append((asset, int(day), str(phase),
                                     pos[1], neg[1]))
        if len(selected) != 264 or len(set(selected)) != 264:
            raise RealDiagnosticExecutorRefusal("PairLogit depth manifest is not 264 unique rows")
        counts = {asset: sum(row[0] == asset for row in receipt_rows) for asset in C.ASSETS}
        if any(value != 44 for value in counts.values()):
            raise RealDiagnosticExecutorRefusal("PairLogit depth manifest is not 44 groups/asset")
        receipt = _sha({"schema": "entry-v2-pairlogit-depth-manifest-v2",
                        "pair_semantics": "asset-day-phase",
                        "equal_timestamp_claim": False,
                        "fit_window": [20210531, 20210930],
                        "groups_per_asset": 44, "rows": receipt_rows,
                        "candidate_ids": selected})
        return frozenset(selected), receipt

    def _prepare(self, manifest: FrozenRowManifest) -> None:
        if self.batches:
            return
        assert self.stage is not None
        wanted = set(manifest.candidate_id)
        depth_wanted, depth_receipt = self._select_pairlogit_depth_ids()
        self._pairlogit_depth_manifest_sha256 = depth_receipt
        binding = {row.candidate_id: row for row in self.stage.diagnostic_corpus.bindings}
        unique_days = sorted(set(manifest.day)); validation_count = max(
            1, int(np.ceil(.1 * len(unique_days))))
        validation_days = set(unique_days[-validation_count:])
        training_days = set(unique_days) - validation_days
        if not training_days:
            raise RealDiagnosticExecutorRefusal("normalizer training-day population is empty")
        self.normalizer_train_manifest_sha256 = _sha({
            "days": sorted(training_days), "candidate_ids": [cid for cid, day in
            zip(manifest.candidate_id, manifest.day) if day in training_days]})
        self.normalizer_validation_manifest_sha256 = _sha({
            "days": sorted(validation_days), "candidate_ids": [cid for cid, day in
            zip(manifest.candidate_id, manifest.day) if day in validation_days]})
        observed = {session.key: session for session in self.stage.diagnostic_corpus.sessions}
        specs = self.stage.corpus_stage.corpus.sessions
        selected_specs = []
        depth_specs = []
        raw_arrays: dict[tuple[str, int], tuple[tuple[str, ...], np.ndarray, np.ndarray]] = {}
        moments: list[np.ndarray] = []
        for spec in specs:
            local = [i for i, cid in enumerate(spec.candidate_ids) if cid in wanted]
            depth_local = [i for i, cid in enumerate(spec.candidate_ids)
                           if cid in depth_wanted]
            if not local and not depth_local:
                continue
            obs = observed[(spec.asset, spec.trading_day)]
            obs.observed.validate_backing()
            if obs.observed.truth is None or obs.observed.derived is None:
                raise RealDiagnosticExecutorRefusal(
                    "E1-E3 arm diagnostic plane was released prematurely"
                )
            stop = max(binding[spec.candidate_ids[i]].event_cutoff
                       for i in (*local, *depth_local))
            truth = obs.observed.truth
            with obs.observed.source.open_arrays() as (cached_continuous, categorical):
                local_bindings = tuple(row for row in
                    self.stage.diagnostic_corpus.bindings
                    if row.asset == spec.asset and row.trading_day == spec.trading_day)
                names, expanded = self.expanded_transform.transform_with_bindings(
                    cached_continuous[:stop], categorical[:stop],
                    truth["ts_recv_ns"][:stop], local_bindings, asset=spec.asset,
                )
                reference_names, reference = _expanded_columns(obs.observed.derived, stop)
                if names != reference_names or not np.array_equal(expanded, reference):
                    raise RealDiagnosticExecutorRefusal(
                        "cached deployment transform differs from one-open truth transform"
                    )
                cats = np.ascontiguousarray(categorical[:stop], np.int64)
            raw_arrays[(spec.asset, spec.trading_day)] = (names, expanded, cats)
            if local and spec.trading_day in training_days:
                moments.append(expanded)
            if local:
                selected_specs.append((spec, local, obs))
            if depth_local:
                depth_specs.append((spec, depth_local, obs))
        if not selected_specs or set(cid for spec, local, _ in selected_specs
                                     for cid in (spec.candidate_ids[i] for i in local)) != wanted:
            raise RealDiagnosticExecutorRefusal("competence candidates lack exact learner tensors")
        if set(cid for spec, local, _ in depth_specs
               for cid in (spec.candidate_ids[i] for i in local)) != depth_wanted:
            raise RealDiagnosticExecutorRefusal("PairLogit depth candidates lack exact tensors")
        schemas = {value[0] for value in raw_arrays.values()}
        if len(schemas) != 1:
            raise RealDiagnosticExecutorRefusal("expanded event schema varies by session")
        names = next(iter(schemas)); joined = np.concatenate(moments)
        location = joined.mean(0); scale = joined.std(0); constant = scale == 0
        scale[constant] = 1.0
        self.location, self.scale = location, scale
        self.event_constant = constant.copy()
        # The selected schema is the pure unnormalized transformation law.
        # Competence moments are separately receipted above and must never
        # alter the production event-view identity.
        conversion = self.expanded_transform.conversion_law_sha256
        self.schema = EventFieldSchema(names, tuple(CATEGORICAL_FIELDS),
                                       tuple(CATEGORY_SIZES), conversion)
        expanded_metadata = self._expanded_session_metadata()
        if (self._expanded_session_metadata_sha256 is None
                or self._expanded_session_metadata_identity(expanded_metadata)
                    != self._expanded_session_metadata_sha256):
            raise RealDiagnosticExecutorRefusal(
                "expanded session metadata changed after one_load")
        self.expanded_transform.freeze(
            schema_sha256=self.schema.sha256,
            model_input_binding=
                self.stage.corpus_stage.corpus.model_input_binding,
            bindings=expanded_metadata,
        )
        raw_static = {(spec.asset, spec.trading_day): np.asarray(
            _static_context_summary(spec), np.float64)
            for spec, _, _ in (*selected_specs, *depth_specs)}
        static_fit = np.concatenate([
            raw_static[(spec.asset, spec.trading_day)][local]
            for spec, local, _ in selected_specs if spec.trading_day in training_days
        ])
        static_location = static_fit.mean(0); static_scale = static_fit.std(0)
        static_constant = static_scale == 0; static_scale[static_constant] = 1.0
        self.static_location = static_location.copy()
        self.static_scale = static_scale.copy()
        self.static_constant = static_constant.copy()
        self.static_normalizer_sha256 = _sha({
            "train_manifest": self.normalizer_train_manifest_sha256,
            "location": _sha_bytes(static_location.tobytes()),
            "scale": _sha_bytes(static_scale.tobytes()),
            "constant": static_constant.tolist(),
        })
        batches = []
        teacher = self.stage.corpus_stage.corpus.teacher
        def build_batch(spec, local, obs):
            names2, expanded, cats = raw_arrays[(spec.asset, spec.trading_day)]
            normalized = ((expanded - location) / scale).astype(np.float32)
            normalized[:, constant] = 0.0
            index = torch.tensor(local, dtype=torch.long)
            cuts = spec.candidate_cutoffs[index].to(torch.long)
            decisions = torch.tensor([binding[spec.candidate_ids[i]].decision_ts_ns
                                      for i in local], dtype=torch.long)
            clocks = torch.from_numpy(np.asarray(
                obs.observed.truth["ts_recv_ns"][:len(normalized)], np.int64))
            last = (cuts - 1).clamp_min(0)
            static_np = ((raw_static[(spec.asset, spec.trading_day)][local]
                          - static_location) / static_scale).astype(np.float32)
            static_np[:, static_constant] = 0.0
            static = torch.from_numpy(static_np)
            examples = tuple(spec.examples[i] for i in local)
            labels = tuple(label for _, label in teacher.join_training(examples))
            if tuple(label.candidate_id for label in labels) != tuple(
                    spec.candidate_ids[i] for i in local):
                raise RealDiagnosticExecutorRefusal("competence teacher join changed row order")
            oracle = MappingProxyType({
                "value_bin": torch.tensor([VALUE_BIN_INDEX[x.value_bin] for x in labels]),
                "value": torch.tensor([x.cert_close_usd / VALUE_SCALE_USD
                                         for x in labels], dtype=torch.float32),
                "top3": torch.tensor([x.top3 for x in labels], dtype=torch.float32),
                "rank": torch.tensor([np.log1p(x.rank) for x in labels], dtype=torch.float32),
                "mfe": torch.tensor([x.mfe_usd / MFE_SCALE_USD
                                       for x in labels], dtype=torch.float32),
                "mae": torch.tensor([x.mae_usd / MAE_SCALE_USD
                                       for x in labels], dtype=torch.float32),
                "wall": torch.tensor([x.wall_hit for x in labels], dtype=torch.float32),
                "time": torch.tensor([x.time_to_peak_sec / TIME_TO_PEAK_SCALE_SECONDS
                                        for x in labels], dtype=torch.float32),
            })
            horizon_target, horizon_valid, horizon_receipt = (
                _selected_horizon_targets_from_spec(
                    obs.atlas, spec, local, labels)
            )
            self._selected_horizon_receipts = getattr(
                self, "_selected_horizon_receipts", set())
            self._selected_horizon_receipts.add(horizon_receipt)
            return _CandidateBatch(
                spec.asset, spec.trading_day, spec.session_id,
                tuple(spec.candidate_ids[i] for i in local),
                torch.from_numpy(normalized), torch.from_numpy(cats), clocks,
                cuts, decisions, spec.candidate_features[index].detach().cpu(),
                spec.context_values[index].detach().cpu(),
                spec.context_type_ids.detach().cpu(), spec.context_valid[index].detach().cpu(),
                static, torch.tensor([float(binding[spec.candidate_ids[i]].action_target)
                                      for i in local]),
                torch.tensor([bool(binding[spec.candidate_ids[i]].action_loss_mask)
                              for i in local]), oracle,
                horizon_target, horizon_valid,
                spec.self_supervised.phase_class[index].detach().cpu(),
                spec.self_supervised.phase_valid[index].detach().cpu(),
                torch.from_numpy(normalized)[last], torch.from_numpy(cats)[last],
            )
        for spec, local, obs in selected_specs:
            batches.append(build_batch(spec, local, obs))
        ordered_batches = tuple(sorted(batches, key=lambda b: (b.asset, b.day, b.session_id)))
        self.batches, self.selected_horizon_normalizer = \
            _fit_selected_horizon_normalizer(
                ordered_batches, training_days, stage="ACCEPTANCE")
        ordered_depth = tuple(sorted(
            (build_batch(spec, local, obs) for spec, local, obs in depth_specs),
            key=lambda b: (b.asset, b.day, b.session_id)))
        # Depth rows do not optimize auxiliary horizons; keep the exact raw
        # carrier so no competence normalizer is falsely applied to PairLogit.
        self._pairlogit_depth_batches = ordered_depth

    def _build_full_policy_batch(self, spec: Any, local: Sequence[int], obs: Any,
                                 binding: Mapping[str, Any],
                                 normalizer: Mapping[str, np.ndarray] | None = None,
                                 ) -> _CandidateBatch:
        """Build one transient full-population batch with frozen competence moments."""
        if any(value is None for value in (
                self.location, self.scale, self.event_constant,
                self.static_location, self.static_scale, self.static_constant)):
            raise RealDiagnosticExecutorRefusal("full policy normalizers are not frozen")
        stop = max(int(binding[spec.candidate_ids[i]].event_cutoff) for i in local)
        observed = obs.observed
        observed.validate_backing()
        if observed.truth is None or observed.derived is None:
            raise RealDiagnosticExecutorRefusal("full policy truth plane was released")
        local_bindings = tuple(row for row in self.stage.diagnostic_corpus.bindings
                               if row.asset == spec.asset
                               and row.trading_day == spec.trading_day)
        with observed.source.open_arrays() as (continuous, categorical):
            names, expanded = self.expanded_transform.transform_with_bindings(
                continuous[:stop], categorical[:stop],
                observed.truth["ts_recv_ns"][:stop], local_bindings,
                asset=spec.asset)
            reference_names, reference = _expanded_columns(observed.derived, stop)
            if names != reference_names or not np.array_equal(expanded, reference):
                raise RealDiagnosticExecutorRefusal(
                    "full policy transform differs from one-open truth")
            cats = np.ascontiguousarray(categorical[:stop], np.int64)
        event_location = (self.location if normalizer is None
                          else normalizer["event_location"])
        event_scale = self.scale if normalizer is None else normalizer["event_scale"]
        event_constant = (self.event_constant if normalizer is None
                          else normalizer["event_constant"])
        normalized = ((expanded - event_location) / event_scale).astype(np.float32)
        normalized[:, event_constant] = 0.0
        index = torch.tensor(tuple(local), dtype=torch.long)
        cuts = spec.candidate_cutoffs[index].to(torch.long)
        decisions = torch.tensor([binding[spec.candidate_ids[i]].decision_ts_ns
                                  for i in local], dtype=torch.long)
        clock = torch.from_numpy(np.asarray(
            observed.truth["ts_recv_ns"][:stop], np.int64))
        static_raw = np.asarray(_static_context_summary(spec), np.float64)[tuple(local)]
        static_location = (self.static_location if normalizer is None
                           else normalizer["static_location"])
        static_scale = (self.static_scale if normalizer is None
                        else normalizer["static_scale"])
        static_constant = (self.static_constant if normalizer is None
                           else normalizer["static_constant"])
        static = ((static_raw - static_location) / static_scale).astype(np.float32)
        static[:, static_constant] = 0.0
        examples = tuple(spec.examples[i] for i in local)
        labels = tuple(label for _, label in
                       self.stage.corpus_stage.corpus.teacher.join_training(examples))
        if tuple(label.candidate_id for label in labels) != tuple(
                spec.candidate_ids[i] for i in local):
            raise RealDiagnosticExecutorRefusal("full policy teacher join changed order")
        oracle = MappingProxyType({
            "value_bin": torch.tensor([VALUE_BIN_INDEX[x.value_bin] for x in labels]),
            "value": torch.tensor([x.cert_close_usd / VALUE_SCALE_USD for x in labels]),
            "top3": torch.tensor([x.top3 for x in labels], dtype=torch.float32),
            "rank": torch.tensor([np.log1p(x.rank) for x in labels], dtype=torch.float32),
            "mfe": torch.tensor([x.mfe_usd / MFE_SCALE_USD for x in labels]),
            "mae": torch.tensor([x.mae_usd / MAE_SCALE_USD for x in labels]),
            "wall": torch.tensor([x.wall_hit for x in labels], dtype=torch.float32),
            "time": torch.tensor([x.time_to_peak_sec / TIME_TO_PEAK_SCALE_SECONDS
                                    for x in labels], dtype=torch.float32),
        })
        last = (cuts - 1).clamp_min(0)
        normalized_tensor = torch.from_numpy(normalized)
        cats_tensor = torch.from_numpy(cats)
        horizon_target, horizon_valid, horizon_receipt = (
            _selected_horizon_targets_from_spec(
                obs.atlas, spec, local, labels)
        )
        self._selected_horizon_receipts = getattr(
            self, "_selected_horizon_receipts", set())
        self._selected_horizon_receipts.add(horizon_receipt)
        return _CandidateBatch(
            spec.asset, spec.trading_day, spec.session_id,
            tuple(spec.candidate_ids[i] for i in local), normalized_tensor,
            cats_tensor, clock, cuts, decisions,
            spec.candidate_features[index].detach().cpu(),
            spec.context_values[index].detach().cpu(),
            spec.context_type_ids.detach().cpu(),
            spec.context_valid[index].detach().cpu(), torch.from_numpy(static),
            torch.tensor([float(binding[spec.candidate_ids[i]].action_target)
                          for i in local]),
            torch.tensor([bool(binding[spec.candidate_ids[i]].action_loss_mask)
                          for i in local]), oracle,
            horizon_target, horizon_valid,
            spec.self_supervised.phase_class[index].detach().cpu(),
            spec.self_supervised.phase_valid[index].detach().cpu(),
            normalized_tensor[last], cats_tensor[last])

    def _full_fit_only_policy_plane(self) -> tuple[
            FrozenRepresentationRows, np.ndarray, np.ndarray, Mapping[str, Any]]:
        """Score every CLEAR+READY pre-October row; never a sampled competence slice."""
        fitted = getattr(self, "_acceptance_catboost_fit", None)
        direct_head = getattr(self, "_acceptance_direct_head", None)
        if fitted is None or direct_head is None:
            raise RealDiagnosticExecutorRefusal("full policy scoring preceded fitted heads")
        binding = {row.candidate_id: row for row in self.stage.diagnostic_corpus.bindings}
        observed = {session.key: session for session in self.stage.diagnostic_corpus.sessions}
        model = self._models()["M1"].to(self.device).eval()
        direct_head = direct_head.to(self.device).eval()
        ids: list[str] = []; assets: list[str] = []; days: list[int] = []
        decisions: list[int] = []; target: list[int] = []; recipient: list[bool] = []
        phases: list[str] = []; states: list[np.ndarray] = []; direct: list[np.ndarray] = []
        for spec in sorted(self.stage.corpus_stage.corpus.sessions,
                           key=lambda row: (row.asset, row.trading_day, row.session_id)):
            if not 20210531 <= int(spec.trading_day) <= 20210930:
                continue
            local = [i for i, cid in enumerate(spec.candidate_ids)
                     if binding[cid].compliance_status == "CLEAR"
                     and binding[cid].teacher_status == "READY"]
            if not local:
                continue
            batch = self._build_full_policy_batch(
                spec, local, observed[(spec.asset, spec.trading_day)], binding)
            with torch.no_grad():
                with self._held_autocast():
                    memory = model.encoder(
                        batch.continuous.to(self.device), batch.categorical.to(self.device),
                        batch.cutoffs.to(self.device), receive_clock_ns=batch.clock.to(self.device),
                        candidate_decision_ts_ns=batch.decisions.to(self.device),
                        asset_idx=C.ASSET_INDEX[batch.asset])
                    output = model.head(
                        memory, batch.candidate_features.to(self.device),
                        batch.context_values.to(self.device),
                        batch.context_type_ids.to(self.device),
                        batch.context_valid.to(self.device), C.ASSET_INDEX[batch.asset],
                        static_features=batch.static_features.to(self.device))
                state = output.decision_state.float()
                p = torch.sigmoid(direct_head(state).squeeze(1)).float()
            batch_ids = list(batch.candidate_ids)
            ids.extend(batch_ids); assets.extend([batch.asset] * len(batch_ids))
            days.extend([batch.day] * len(batch_ids))
            decisions.extend(int(binding[cid].decision_ts_ns) for cid in batch_ids)
            target.extend(int(binding[cid].action_target) for cid in batch_ids)
            recipient.extend(bool(binding[cid].action_loss_mask) for cid in batch_ids)
            phases.extend(str(spec.examples[i].phase) for i in local)
            states.append(state.cpu().numpy()); direct.append(p.cpu().numpy())
        model.cpu(); direct_head.cpu()
        if not ids or len(set(ids)) != len(ids):
            raise RealDiagnosticExecutorRefusal("full policy roster is empty or duplicate")
        expected = {row.candidate_id for row in self.stage.diagnostic_corpus.bindings
                    if 20210531 <= row.trading_day <= 20210930
                    and row.compliance_status == "CLEAR" and row.teacher_status == "READY"}
        if set(ids) != expected:
            raise RealDiagnosticExecutorRefusal("full policy roster differs from CLEAR+READY")
        representation = np.ascontiguousarray(np.concatenate(states), np.float32)
        direct_probability = np.ascontiguousarray(np.concatenate(direct), np.float64)
        cat_probability = np.full(len(ids), np.nan, np.float64)
        asset_array = np.asarray(assets, str)
        for asset in C.ASSETS:
            local = np.flatnonzero(asset_array == asset)
            ranker = fitted.assets[asset].ranker_model
            if ranker is None:
                raise RealDiagnosticExecutorRefusal(f"{asset} full policy PairLogit unavailable")
            cat_probability[local] = expit(np.asarray(
                ranker.predict(representation[local]), np.float64))
        if not np.all(np.isfinite(cat_probability)):
            raise RealDiagnosticExecutorRefusal("full policy PairLogit prediction incomplete")
        eligible_days = tuple(sorted({session.trading_day for session in
            self.stage.corpus_stage.corpus.replay.expected_sessions
            if 20210531 <= session.trading_day <= 20210930}))
        rows = FrozenRepresentationRows(
            representation, np.asarray(ids, str), asset_array,
            np.asarray(days, np.int64), np.asarray(decisions, np.int64),
            np.asarray(target, np.int8), np.asarray(recipient, bool),
            np.asarray(phases, str), np.full(len(ids), "POLICY_ROSTER"),
            "REHEARSAL_E2", eligible_development_days=eligible_days,
            group_semantics="PHASE")
        rows.validate()
        manifest = _sha({"schema": "entry-v2-full-fit-only-policy-roster-v1",
                         "candidate_ids": ids, "days": days,
                         "recipient_mask_sha256": _sha_bytes(
                             np.asarray(recipient, bool).tobytes()),
                         "representation_sha256": rows.representation_sha256})
        evidence = MappingProxyType({
            "schema": "entry-v2-full-fit-only-policy-roster-v1",
            "candidate_manifest_sha256": manifest, "candidate_count": len(ids),
            "recipient_count": int(np.sum(recipient)), "maximum_d8": max(days),
            "partition_counts": {f"{stage}.{role}": int(np.sum(
                _rehearsal_mask(np.asarray(days), stage, role)))
                for stage in ("E1r", "E2r")
                for role in ("FIT", "PLATT", "THRESHOLD", "FORWARD")}})
        return rows, direct_probability, cat_probability, evidence

    def _fit_rehearsal_input_normalizer(
            self, specs: Sequence[Any], training_days: set[int]) -> Mapping[str, Any]:
        """Stream exact full-population TRAIN moments without retaining event planes."""
        observed = {session.key: session for session in self.stage.diagnostic_corpus.sessions}
        bindings, by_session = self._binding_indexes()
        event_count = 0; event_total = None; event_square = None
        static_count = 0; static_total = None; static_square = None
        session_receipts = []
        for spec in specs:
            if spec.trading_day not in training_days:
                continue
            session = observed[(spec.asset, spec.trading_day)]
            stop = int(torch.max(spec.candidate_cutoffs))
            with session.observed.source.open_arrays() as (continuous, categorical):
                names, expanded = self.expanded_transform.transform_with_bindings(
                    continuous[:stop], categorical[:stop],
                    session.observed.truth["ts_recv_ns"][:stop],
                    by_session[(spec.asset, spec.trading_day)], asset=spec.asset)
            if tuple(names) != tuple(self.schema.continuous_fields):
                raise RealDiagnosticExecutorRefusal("rehearsal event schema differs")
            values = np.asarray(expanded, np.float64)
            total = values.sum(0); square = np.square(values).sum(0)
            event_total = total if event_total is None else event_total + total
            event_square = square if event_square is None else event_square + square
            event_count += len(values)
            static = np.asarray(_static_context_summary(spec), np.float64)
            total = static.sum(0); square = np.square(static).sum(0)
            static_total = total if static_total is None else static_total + total
            static_square = square if static_square is None else static_square + square
            static_count += len(static)
            session_receipts.append((spec.asset, spec.trading_day, spec.session_id,
                                     stop, len(static)))
        if event_count < 2 or static_count < 2:
            raise RealDiagnosticExecutorRefusal("rehearsal input moments are empty")
        event_location = event_total / event_count
        event_scale = np.sqrt(np.maximum(
            event_square / event_count - event_location * event_location, 0.0))
        event_constant = event_scale == 0; event_scale[event_constant] = 1.0
        static_location = static_total / static_count
        static_scale = np.sqrt(np.maximum(
            static_square / static_count - static_location * static_location, 0.0))
        static_constant = static_scale == 0; static_scale[static_constant] = 1.0
        result = {"event_location": event_location, "event_scale": event_scale,
            "event_constant": event_constant, "static_location": static_location,
            "static_scale": static_scale, "static_constant": static_constant,
            "receipt_sha256": _sha({"schema": "entry-v2-rehearsal-input-normalizer-v1",
                "training_days": sorted(training_days), "event_count": event_count,
                "static_count": static_count, "sessions": session_receipts,
                "event_location": _sha_bytes(event_location.tobytes()),
                "event_scale": _sha_bytes(event_scale.tobytes()),
                "static_location": _sha_bytes(static_location.tobytes()),
                "static_scale": _sha_bytes(static_scale.tobytes())})}
        return MappingProxyType(result)

    def audit_raw_fidelity(self, loaded, manifest):
        self._prepare(manifest); assert self.schema is not None
        corpus = self.stage.corpus_stage.corpus
        corpus.raw_prefix_fidelity.validate()
        if not corpus.raw_prefix_fidelity.passed:
            raise RealDiagnosticExecutorRefusal("corpus raw-prefix fidelity failed")
        assert_teacher_schedule_parity(loaded.corpus.bindings, corpus.teacher)
        observed = {session.key: session for session in loaded.corpus.sessions}
        binding = {row.candidate_id: row for row in loaded.corpus.bindings}
        summaries = {}
        book_receipts = []
        cutoff_checks = equal_checks = before_after_checks = 0
        phase_checks = 0
        for batch in self.batches:
            expected = torch.searchsorted(batch.clock, batch.decisions, right=False)
            if not torch.equal(expected, batch.cutoffs):
                raise RealDiagnosticExecutorRefusal("left cutoff differs on real competence row")
            obs = observed[(batch.asset, batch.day)].observed
            obs.validate_backing()
            if obs.truth is None or obs.derived is None:
                raise RealDiagnosticExecutorRefusal("raw audit plane was released")
            truth = obs.truth
            quality = native_book_quality(truth["ts_recv_ns"], truth["flags"], truth["sane"])
            if (not np.array_equal(quality.generation, truth["generation"])
                    or not np.array_equal(quality.trusted_message, truth["trusted_message"])
                    or not np.array_equal(quality.trusted_economic, truth["trusted_economic"])):
                raise RealDiagnosticExecutorRefusal("native book trust reproduction failed")
            book_receipts.append(_sha({"asset": batch.asset, "day": batch.day,
                                       "generations": int(quality.generation.max(initial=0)),
                                       "trusted": int(quality.trusted_message.sum())}))
            for cid, cutoff in zip(batch.candidate_ids, batch.cutoffs.tolist()):
                row = binding[cid]
                if cutoff != row.event_cutoff:
                    raise RealDiagnosticExecutorRefusal("candidate cutoff binding differs")
                if cutoff and int(truth["ts_recv_ns"][cutoff - 1]) >= row.decision_ts_ns:
                    raise RealDiagnosticExecutorRefusal("prefix includes equal/after-time row")
                if cutoff < len(truth["ts_recv_ns"]) and int(
                        truth["ts_recv_ns"][cutoff]) < row.decision_ts_ns:
                    raise RealDiagnosticExecutorRefusal("prefix omitted before-time row")
                cutoff_checks += 1
                equal_checks += int(not np.any(
                    truth["ts_recv_ns"][:cutoff] == row.decision_ts_ns))
                before_after_checks += int(
                    (cutoff == 0 or truth["ts_recv_ns"][cutoff - 1] < row.decision_ts_ns)
                    and (cutoff == len(truth["ts_recv_ns"])
                         or truth["ts_recv_ns"][cutoff] >= row.decision_ts_ns))
                # The summary learner consumes the same lossless canonical
                # expanded plane as the neural arms, never absolute uint64
                # clocks or UNDEF_PRICE sentinels cast to float64.
                _, canonical = _expanded_columns(obs.derived, cutoff)
                if not len(canonical):
                    raise RealDiagnosticExecutorRefusal("raw summary prefix is empty")
                continuous_summary = np.concatenate((
                    canonical[-1], canonical.mean(0), canonical.std(0),
                    canonical.min(0), canonical.max(0),
                ))
                category_summary = []
                for column, size in enumerate(CATEGORY_SIZES):
                    values = np.asarray(batch.categorical[:cutoff, column], np.int64)
                    category_summary.extend(np.bincount(
                        values, minlength=size)[:size] / max(1, cutoff))
                summaries[cid] = np.concatenate((
                    continuous_summary, np.asarray(category_summary, np.float64)))
                if cutoff:
                    phase_age = obs.derived.derived_routes["phase_age_ns"][:cutoff]
                    phase_remaining = obs.derived.derived_routes["phase_remaining_ns"][:cutoff]
                    if (not np.all(phase_age == truth["ts_recv_ns"][:cutoff]
                                   - truth["phase_open_ts_ns"][:cutoff])
                            or not np.all(phase_remaining ==
                                          truth["phase_close_ts_ns"][:cutoff]
                                          - truth["ts_recv_ns"][:cutoff])):
                        raise RealDiagnosticExecutorRefusal("adjacent phase clock differs")
                    phase_checks += 1
                    if not np.all(np.isfinite(canonical)):
                        raise RealDiagnosticExecutorRefusal(
                            "canonical raw prefix contains non-finite values")
        ids = np.asarray(manifest.candidate_id)
        summary = np.asarray([summaries[cid] for cid in ids], np.float32)
        examples_by_id = {example.candidate_id: example
                          for spec in self.stage.corpus_stage.corpus.sessions
                          for example in spec.examples}
        rows = FrozenRepresentationRows(
            summary, ids, np.asarray(manifest.asset), np.asarray(manifest.day, np.int64),
            np.asarray([binding[cid].decision_ts_ns for cid in ids], np.int64),
            np.asarray([binding[cid].action_target for cid in ids], np.int8),
            np.asarray([binding[cid].action_loss_mask for cid in ids], bool),
            np.asarray([examples_by_id[cid].phase for cid in ids], str),
            np.full(len(ids), "FIT"), "E1", group_semantics="PHASE")
        raw_fit = fit_diagnostic_catboost(
            rows, expected_representation_sha256=rows.representation_sha256)
        raw_metrics = {}
        for asset in C.ASSETS:
            local = ((np.asarray(rows.asset, str) == asset)
                     & np.asarray(rows.action_loss_mask, bool))
            target = np.asarray(rows.action_target, np.int8)[local]
            probability = np.asarray(raw_fit.action_probability, np.float64)[local]
            if len(np.unique(target)) != 2:
                raise RealDiagnosticExecutorRefusal(
                    f"raw-summary {asset} competence lacks both classes")
            raw_metrics[asset] = {
                "auroc": float(roc_auc_score(target, probability)),
                "ap": float(average_precision_score(target, probability)),
                "bce": float(log_loss(target, probability, labels=[0, 1])),
            }
        raw_summary_pass = all(
            value["auroc"] >= .995 and value["ap"] >= .995
            and value["bce"] <= .02 for value in raw_metrics.values())
        cutoff_adversary_clock = torch.tensor(
            [99, 100, 100, 101], dtype=torch.int64)
        cutoff_adversary_decision = torch.tensor([100], dtype=torch.int64)
        cutoff_adversary = int(torch.searchsorted(
            cutoff_adversary_clock, cutoff_adversary_decision,
            right=False)[0])
        before_equal_after_pack = (
            cutoff_adversary == 1
            and bool(torch.all(cutoff_adversary_clock[:cutoff_adversary]
                               < cutoff_adversary_decision[0]))
            and bool(torch.all(cutoff_adversary_clock[cutoff_adversary:3]
                               == cutoff_adversary_decision[0]))
            and int(cutoff_adversary_clock[3])
                > int(cutoff_adversary_decision[0])
        )
        cutoff_adversary_receipt = _sha({
            "schema": "entry-v2-left-cutoff-before-equal-after-adversary-v1",
            "clock": cutoff_adversary_clock.tolist(),
            "decision": cutoff_adversary_decision.tolist(),
            "left_cutoff": cutoff_adversary,
            "equal_rows_excluded": before_equal_after_pack,
        })
        snapshot_flags = np.asarray([
            F_SNAPSHOT | F_BAD_TS_RECV,
            F_SNAPSHOT | F_BAD_TS_RECV,
            0,
            0,
        ], np.uint8)
        snapshot_quality = native_book_quality(
            np.asarray([100, 100, 101, 102], np.int64), snapshot_flags,
            np.asarray([False, False, True, True], bool))
        snapshot_seed_exact = (
            np.array_equal(snapshot_quality.generation,
                           np.asarray([1, 1, 1, 1], np.uint32))
            and np.array_equal(snapshot_quality.trusted_message,
                               np.asarray([False, False, False, True]))
            and np.array_equal(snapshot_quality.trusted_economic,
                               np.asarray([False, False, False, True]))
        )
        if not snapshot_seed_exact:
            raise RealDiagnosticExecutorRefusal(
                "snapshot seed/trust adversary differs from the raw law")
        snapshot_adversary_receipt = _sha({
            "schema": "entry-v2-snapshot-seed-adversary-v1",
            "flags": snapshot_flags.tolist(),
            "generation": snapshot_quality.generation.tolist(),
            "trusted_message": snapshot_quality.trusted_message.tolist(),
            "trusted_economic": snapshot_quality.trusted_economic.tolist(),
            "seed_is_untrusted": snapshot_seed_exact,
        })
        raw_categorical = set(CATEGORICAL_FIELDS[:-1]) | {"missing_mask"}
        required_continuous = set()
        for name in RAW_ROUTE_FIELDS:
            if name in raw_categorical:
                continue
            if name in {"ts_recv_ns", "ts_event_ns"}:
                required_continuous.update({
                    f"raw.{name}.sec", f"raw.{name}.microsecond",
                    f"raw.{name}.nanosecond",
                })
            else:
                required_continuous.add(f"raw.{name}")
        if not required_continuous.issubset(self.schema.continuous_fields) \
                or tuple(self.schema.categorical_fields) != tuple(CATEGORICAL_FIELDS):
            raise RealDiagnosticExecutorRefusal("complete raw named schema is absent")
        learner_input_hash = _sha({"schema": self.schema.sha256,
                           "normalizer_train": self.normalizer_train_manifest_sha256,
                           "normalizer_validation": self.normalizer_validation_manifest_sha256,
                           "batches": [(b.asset, b.day, b.candidate_ids,
                                        _sha_bytes(b.continuous.numpy().tobytes()))
                                       for b in self.batches]})
        roster = tuple(loaded.corpus.bindings)
        firewall_sha256 = _fit_only_loaded_roster_firewall(
            self.stage, roster, required_candidate_ids=manifest.candidate_id)
        before = _component_fit_projection(roster, manifest, self.batches,
                                           include_action=False)
        canary_batches = list(self.batches)
        changed = canary_batches[0].continuous.clone(); changed[0, 0] += 1.0
        canary_batches[0] = replace(canary_batches[0], continuous=changed)
        canary_hash = _component_fit_projection(roster, manifest, canary_batches,
                                                include_action=False)
        def raw_refit(authority, features=summary):
            index = {row.candidate_id: row for row in authority}
            target = np.asarray([index[str(cid)].action_target for cid in ids], np.int8)
            allowed = np.asarray([index[str(cid)].action_loss_mask for cid in ids], bool)
            return _bounded_supervised_fit_sha(features, target, allowed, seed=20260815)
        raw_refit_before = raw_refit(roster)
        changed_summary = summary.copy(); changed_summary[0, 0] += 1.0
        raw_refit_canary = raw_refit(roster, changed_summary)
        firewall_exact = (bool(firewall_sha256) and canary_hash != before
                          and raw_refit_canary != raw_refit_before)
        if not firewall_exact:
            raise RealDiagnosticExecutorRefusal(
                "raw fit-only firewall or visible-row canary failed")
        raw_evidence = {"schema": "entry-v2-raw-fidelity-evidence-v1",
                         "manifest": manifest.receipt_sha256,
                         "event_schema_sha256": self.schema.sha256,
                         "raw_summary_competence": raw_fit.receipt_sha256,
                         "raw_summary_metrics": raw_metrics,
                         "cutoff_adversary_sha256": cutoff_adversary_receipt,
                         "snapshot_seed_adversary_sha256":
                             snapshot_adversary_receipt,
                         "book_receipts": book_receipts,
                         "normalizer_train": self.normalizer_train_manifest_sha256,
                         "normalizer_validation": self.normalizer_validation_manifest_sha256,
                         "fit_only_firewall_sha256": firewall_sha256,
                         "learner_input_sha256": learner_input_hash,
                         "fit_input_projection_sha256": before,
                         "visible_canary_sha256": canary_hash,
                         "fit_refit_before": raw_refit_before,
                         "visible_input_refit_canary": raw_refit_canary,
                         "sessions": [(b.asset, b.day, b.session_id,
                                       list(b.candidate_ids)) for b in self.batches]}
        artifact = _sha(raw_evidence)
        self._acceptance_component_evidence[
            "acceptance/evidence/raw-fidelity.json"
        ] = _canonical_json_bytes({**raw_evidence, "receipt_sha256": artifact})
        row_count = len(manifest.candidate_id)
        return RawFidelityResult(
            manifest.receipt_sha256,
            cutoff_checks == row_count,
            equal_checks == row_count,
            bool(corpus.raw_prefix_fidelity.passed),
            required_continuous.issubset(self.schema.continuous_fields)
                and tuple(self.schema.categorical_fields) == tuple(CATEGORICAL_FIELDS),
            before_after_checks == row_count and before_equal_after_pack,
            bool(corpus.raw_prefix_fidelity.passed
                 and cutoff_checks == row_count
                 and equal_checks == row_count
                 and before_after_checks == row_count),
            raw_summary_pass,
            len(book_receipts) == len(self.batches),
            snapshot_seed_exact,
            phase_checks == row_count,
            bool(self.event_constant is not None
                 and self.event_constant.shape == (len(self.schema.continuous_fields),)),
            bool(self.normalizer_train_manifest_sha256
                 and self.normalizer_validation_manifest_sha256),
            firewall_exact, artifact,
        )

    def _models(self):
        if self._arms is not None:
            return self._arms
        self._arms = self._new_model_registry()
        return self._arms

    def _new_model_registry(self):
        """Fresh deterministic arm initialization; never returns competence state."""
        assert self.schema is not None
        width = len(self.schema.continuous_fields)
        candidate_width = int(self.batches[0].candidate_features.shape[1])
        devices = ([self.device.index or 0] if self.device.type == "cuda" else [])
        with torch.random.fork_rng(devices=devices):
            torch.manual_seed(20260816)
            current = FullPrefixEntryModel(
                width, candidate_width, CONTEXT_TENSOR_WIDTH,
                len(CONTEXT_TYPE_ID), event_category_sizes=CATEGORY_SIZES,
            )
            c0 = CurrentEncoderAdapter(current, self.schema)
            c1 = CurrentEncoderAdapter(copy.deepcopy(current), self.schema)
            names = self.schema.continuous_fields
            lit = LiTShortMemoryEncoder(
                width, CATEGORY_SIZES, field_schema=self.schema,
                bid_field_indices=tuple(names.index(name) for name in
                                        ("raw.bid_px", "raw.bid_sz", "raw.bid_ct")),
                ask_field_indices=tuple(names.index(name) for name in
                                        ("raw.ask_px", "raw.ask_sz", "raw.ask_ct")),
            )
            m1 = CausalMultiresolutionEncoder(width, CATEGORY_SIZES,
                                              field_schema=self.schema)
            head = SharedCandidateDecisionHead(
                candidate_width, CONTEXT_TENSOR_WIDTH, len(CONTEXT_TYPE_ID))
            return build_five_arm_registry(c0, c1, lit, m1, head)

    @staticmethod
    def _metrics(rows: FrozenRepresentationRows, probability: np.ndarray,
                 selected: np.ndarray | None = None):
        values = []
        selected = (np.ones(len(probability), bool) if selected is None
                    else np.asarray(selected, bool))
        supervised = np.asarray(rows.action_loss_mask, bool)
        for asset in ("HG", "NKD", "SI"):
            mask = ((np.asarray(rows.asset, str) == asset)
                    & selected & supervised)
            y = np.asarray(rows.action_target, int)[mask]; p = probability[mask]
            if len(y) < 2 or len(np.unique(y)) != 2:
                raise RealDiagnosticExecutorRefusal(
                    f"{asset} competence metric lacks both supervised classes")
            values.append((roc_auc_score(y, p), average_precision_score(y, p),
                           log_loss(y, p, labels=[0, 1])))
        return min(x[0] for x in values), min(x[1] for x in values), max(x[2] for x in values)

    def _encode(self, model, arm: str):
        model.to(self.device)
        decoder = LastRowReconstructionProbe(
            self.batches[0].continuous.shape[1], CATEGORY_SIZES).to(self.device)
        optimizer = torch.optim.AdamW(
            [*model.parameters(), *decoder.parameters()], lr=1e-3)
        unique_days = sorted({b.day for b in self.batches}); validation_days = set(
            unique_days[-max(1, int(np.ceil(.1 * len(unique_days)))):])
        training_batches = tuple(b for b in self.batches if b.day not in validation_days)
        if not training_batches:
            raise RealDiagnosticExecutorRefusal("arm training-day population is empty")
        by_day: dict[tuple[str, int], list[_CandidateBatch]] = {}
        for batch in training_batches:
            by_day.setdefault((batch.asset, batch.day), []).append(batch)
        ids = tuple(cid for batch in training_batches for cid in batch.candidate_ids)
        assets = np.asarray([batch.asset for batch in training_batches
                             for _ in batch.candidate_ids], str)
        days = np.asarray([batch.day for batch in training_batches
                           for _ in batch.candidate_ids], np.int64)
        action = np.concatenate([batch.targets.numpy() for batch in training_batches])
        recipient = np.concatenate([batch.action_loss_mask.numpy()
                                    for batch in training_batches]).astype(bool)
        top3 = np.concatenate([batch.oracle_targets["top3"].numpy()
                               for batch in training_batches])
        wall = np.concatenate([batch.oracle_targets["wall"].numpy()
                               for batch in training_batches])
        order = np.lexsort((np.asarray(ids, str), days, assets))
        def weights_for(target_values, mask_values, class_weight):
            local, receipt = asset_day_fit_weights(
                assets[order], days[order], np.asarray(target_values)[order],
                np.asarray(mask_values)[order], np.ones(len(order), bool),
                apply_class_weight=class_weight)
            full = np.zeros(len(order), np.float32); full[order] = local
            return full, receipt
        action_weight, action_receipt = weights_for(action, recipient, True)
        base_weight, base_receipt = weights_for(
            np.zeros(len(ids)), np.ones(len(ids), bool), False)
        top3_weight, top3_receipt = weights_for(top3, np.ones(len(ids), bool), True)
        wall_weight, wall_receipt = weights_for(wall, np.ones(len(ids), bool), True)
        weights_by_id = {cid: {"action": float(action_weight[i]),
            "base": float(base_weight[i]), "top3": float(top3_weight[i]),
            "wall": float(wall_weight[i])} for i, cid in enumerate(ids)}
        self._competence_weight_receipts = getattr(
            self, "_competence_weight_receipts", {})
        self._competence_weight_receipts[arm] = MappingProxyType({
            "action": action_receipt.receipt_sha256,
            "base": base_receipt.receipt_sha256,
            "top3": top3_receipt.receipt_sha256,
            "wall": wall_receipt.receipt_sha256})
        updates = 0; best = None; best_validation = np.inf; stale = 0; trace = []
        # The bounded competence clone jointly optimizes the actual encoder and
        # shared head. Twelve chronological passes are the frozen dense-stage
        # ceiling; the independent competence ceiling remains 400 updates.
        for epoch in range(12):
            model.train(); decoder.train()
            named = [*model.named_parameters(), *((f"decoder.{name}", parameter)
                     for name, parameter in decoder.named_parameters())]
            before_parameters = {
                name: parameter.detach().cpu().clone() for name, parameter in named}
            epoch_components = []; epoch_gradient_norm = 0.0
            for day_key in sorted(by_day):
                optimizer.zero_grad(set_to_none=True)
                oracle_losses = []; reconstruction_losses = []; component_rows = []
                for batch in by_day[day_key]:
                    static = batch.static_features.to(self.device) if arm in ("L1", "M1") else None
                    out = model(
                        event_continuous=batch.continuous.to(self.device),
                        event_categorical=batch.categorical.to(self.device),
                        receive_clock_ns=batch.clock.to(self.device),
                        candidate_cutoffs=batch.cutoffs.to(self.device),
                        candidate_decision_ts_ns=batch.decisions.to(self.device),
                        candidate_features=batch.candidate_features.to(self.device),
                        context_values=batch.context_values.to(self.device),
                        context_type_ids=batch.context_type_ids.to(self.device),
                        context_valid=batch.context_valid.to(self.device),
                        asset_idx=C.ASSET_INDEX[batch.asset], static_features=static)
                    batch_weights = {name: torch.tensor([
                        weights_by_id[cid][name] for cid in batch.candidate_ids],
                        dtype=torch.float32) for name in ("action", "base", "top3", "wall")}
                    total, components = _actual_multitask_loss(out, batch, batch_weights)
                    reconstruction_loss, continuous_loss, categorical_loss = \
                        _field_reconstruction_loss(
                            decoder, out.raw_memory, batch,
                            batch_weights["base"],
                        )
                    oracle_losses.append(total)
                    reconstruction_losses.append(reconstruction_loss)
                    component_rows.append({**dict(components),
                        "field_continuous": continuous_loss,
                        "field_categorical": categorical_loss})
                loss = (torch.stack(oracle_losses).sum()
                        + torch.stack(reconstruction_losses).sum())
                loss.backward()
                common = [p.grad for p in model.encoder.parameters() if p.grad is not None]
                heads = [p.grad for p in model.head.parameters() if p.grad is not None]
                reconstruction = [p.grad for p in decoder.parameters() if p.grad is not None]
                if (not common or not heads or not reconstruction
                        or sum(float(g.abs().sum()) for g in common) <= 0
                        or sum(float(g.abs().sum()) for g in heads) <= 0
                        or sum(float(g.abs().sum()) for g in reconstruction) <= 0):
                    raise RealDiagnosticExecutorRefusal("action loss did not traverse encoder/head")
                head_groups = {
                    name: sum(float(parameter.grad.abs().sum()) for parameter_name, parameter
                              in model.head.named_parameters()
                              if name in parameter_name and parameter.grad is not None)
                    for name in ("action_head", "ordinal_head", "value_distribution_head",
                                 "value_quantile_head", "expected_value_head", "top3_head",
                                 "rank_head", "mfe_quantile_head", "mae_quantile_head",
                                 "wall_head", "time_to_peak_head", "horizon_head", "phase_head")}
                if any(value <= 0 for value in head_groups.values()) or any(
                        not torch.isfinite(value) for components in component_rows
                        for value in components.values()):
                    raise RealDiagnosticExecutorRefusal(
                        "declared oracle multitask head lacks finite supervised gradient")
                epoch_components.extend({name: float(value.detach())
                    for name, value in components.items()}
                    for components in component_rows)
                epoch_gradient_norm += sum(float(torch.linalg.vector_norm(
                    parameter.grad.detach())) for _name, parameter in named
                    if parameter.grad is not None)
                optimizer.step(); updates += 1
                if updates >= 400: break
            rows_now, _metrics_all, _, _, probabilities_now = self._collect(model, arm)
            p_now = np.asarray([probabilities_now[cid] for cid in rows_now.candidate_id])
            val_mask = (np.isin(np.asarray(rows_now.day), list(validation_days))
                        & np.asarray(rows_now.action_loss_mask, bool))
            y_now = np.asarray(rows_now.action_target, np.float64)
            if not val_mask.any():
                raise RealDiagnosticExecutorRefusal(
                    "arm validation lacks supervised action rows")
            validation_parts = []
            model.eval(); decoder.eval()
            with torch.no_grad():
                for batch in (value for value in self.batches
                              if value.day in validation_days):
                    out = model(
                        event_continuous=batch.continuous.to(self.device),
                        event_categorical=batch.categorical.to(self.device),
                        receive_clock_ns=batch.clock.to(self.device),
                        candidate_cutoffs=batch.cutoffs.to(self.device),
                        candidate_decision_ts_ns=batch.decisions.to(self.device),
                        candidate_features=batch.candidate_features.to(self.device),
                        context_values=batch.context_values.to(self.device),
                        context_type_ids=batch.context_type_ids.to(self.device),
                        context_valid=batch.context_valid.to(self.device),
                        asset_idx=C.ASSET_INDEX[batch.asset],
                        static_features=(batch.static_features.to(self.device)
                                         if arm in ("L1", "M1") else None))
                    oracle_validation, _ = _actual_multitask_loss(out, batch)
                    field_validation, _continuous, _categorical = \
                        _field_reconstruction_loss(
                            decoder, out.raw_memory, batch,
                        )
                    validation_parts.append((
                        float(oracle_validation + field_validation),
                        len(batch.candidate_ids),
                    ))
            if not validation_parts or not np.all(np.isfinite(validation_parts)):
                raise RealDiagnosticExecutorRefusal(
                    "joint arm validation loss is unavailable")
            validation = float(sum(value * count for value, count in validation_parts)
                               / sum(count for _value, count in validation_parts))
            train_metrics = self._metrics(rows_now, p_now, ~val_mask)
            checkpoint = _sha({
                "model": _sha_bytes(module_state_bytes(model)),
                "decoder": _sha_bytes(module_state_bytes(decoder)),
            })
            after_parameters = [*model.named_parameters(), *((f"decoder.{name}", parameter)
                                for name, parameter in decoder.named_parameters())]
            parameter_delta = float(sum(torch.linalg.vector_norm(
                parameter.detach().cpu() - before_parameters[name])
                for name, parameter in after_parameters))
            component_means = ({name: float(np.mean([
                row[name] for row in epoch_components if name in row]))
                for name in sorted({key for row in epoch_components for key in row})}
                if epoch_components else {})
            trace.append({"epoch": epoch, "validation": validation,
                          "train_auroc": train_metrics[0],
                          "train_ap": train_metrics[1],
                          "train_bce": train_metrics[2],
                          "components": component_means,
                          "gradient_norm": epoch_gradient_norm,
                          "parameter_delta": parameter_delta,
                          "checkpoint_sha256": checkpoint})
            if validation < best_validation * .999:
                best_validation = validation; stale = 0
                best = (
                    {name: value.detach().cpu().clone()
                     for name, value in model.state_dict().items()},
                    {name: value.detach().cpu().clone()
                     for name, value in decoder.state_dict().items()},
                    checkpoint,
                )
            else:
                stale += 1
            if epoch >= 1 and (stale >= 3 or updates >= 400):
                break
        if best is None or len(trace) < 2:
            raise RealDiagnosticExecutorRefusal("joint arm training produced no checkpoint")
        model.load_state_dict(best[0], strict=True)
        decoder.load_state_dict(best[1], strict=True)
        reload_sha256 = _sha({
            "model": _sha_bytes(module_state_bytes(model)),
            "decoder": _sha_bytes(module_state_bytes(decoder)),
        })
        if reload_sha256 != best[2]:
            raise RealDiagnosticExecutorRefusal(
                "joint arm/field checkpoint reload differs")
        # A-015/ordinal structural canaries: every selected horizon coordinate
        # and every cumulative boundary must independently alter its own loss
        # and receive a finite nonzero gradient.
        model.train(); model.zero_grad(set_to_none=True)
        for coordinate in range(SELECTED_HORIZON_WIDTH):
            probe_batch = next((batch for batch in self.batches
                                if bool(batch.horizon_valid[:, coordinate].any())), None)
            if probe_batch is None:
                raise RealDiagnosticExecutorRefusal(
                    "selected horizon mutation canary lacks a coordinate")
            probe_out = model(
                event_continuous=probe_batch.continuous.to(self.device),
                event_categorical=probe_batch.categorical.to(self.device),
                receive_clock_ns=probe_batch.clock.to(self.device),
                candidate_cutoffs=probe_batch.cutoffs.to(self.device),
                candidate_decision_ts_ns=probe_batch.decisions.to(self.device),
                candidate_features=probe_batch.candidate_features.to(self.device),
                context_values=probe_batch.context_values.to(self.device),
                context_type_ids=probe_batch.context_type_ids.to(self.device),
                context_valid=probe_batch.context_valid.to(self.device),
                asset_idx=C.ASSET_INDEX[probe_batch.asset],
                static_features=(probe_batch.static_features.to(self.device)
                                 if arm in ("L1", "M1") else None))
            horizon_prediction = probe_out.horizon_values.float()
            horizon_target = probe_batch.horizon_targets.to(self.device).float()
            horizon_valid = probe_batch.horizon_valid.to(self.device).bool()
            valid_coordinate = horizon_valid[:, coordinate]
            original = torch.nn.functional.smooth_l1_loss(
                horizon_prediction[valid_coordinate, coordinate],
                horizon_target[valid_coordinate, coordinate])
            # The perturbed target is deliberately one unit from the detached
            # prediction, guaranteeing a nonzero coordinate-local derivative
            # while the comparison still proves that this target coordinate is
            # consumed by the declared loss.
            detached_prediction = horizon_prediction[
                valid_coordinate, coordinate].detach()
            mutant = detached_prediction + 1.0
            changed = torch.nn.functional.smooth_l1_loss(
                horizon_prediction[valid_coordinate, coordinate], mutant)
            changed_far = torch.nn.functional.smooth_l1_loss(
                horizon_prediction[valid_coordinate, coordinate],
                detached_prediction + 2.0)
            if bool(torch.isclose(original, changed)) and bool(
                    torch.isclose(original, changed_far)):
                raise RealDiagnosticExecutorRefusal(
                    "selected horizon coordinate mutation did not alter loss")
            changed.backward()
        horizon_gradient = model.head.horizon_head.weight.grad
        if (horizon_gradient is None or horizon_gradient.shape[0] != 6
                or torch.any(horizon_gradient.abs().sum(1) <= 0)
                or not torch.isfinite(horizon_gradient).all()):
            raise RealDiagnosticExecutorRefusal(
                "selected horizon head lacks independent coordinate gradients")
        model.zero_grad(set_to_none=True)
        synthetic_state = torch.arange(5 * 512, device=self.device,
            dtype=torch.float32).reshape(5, 512) / (5 * 512)
        ordinal_logits = model.head.ordinal_head(synthetic_state)
        ordinal_target = (torch.arange(5, device=self.device)[:, None]
                          >= torch.arange(1, 5, device=self.device)[None]).float()
        torch.nn.functional.binary_cross_entropy_with_logits(
            ordinal_logits, ordinal_target).backward()
        ordinal_gradient = model.head.ordinal_head.weight.grad
        if (ordinal_gradient is None or torch.any(ordinal_gradient.abs().sum(1) <= 0)
                or not torch.isfinite(ordinal_gradient).all()):
            raise RealDiagnosticExecutorRefusal(
                "cumulative ordinal head lacks all-boundary reachability")
        rows, _all_metrics, memories, states, probabilities = self._collect(model, arm)
        probability = np.asarray([probabilities[cid] for cid in rows.candidate_id])
        metrics = self._metrics(rows, probability,
                                ~np.isin(np.asarray(rows.day), list(validation_days)))
        if metrics[0] < .995 or metrics[1] < .995 or metrics[2] > .02:
            raise RealDiagnosticExecutorRefusal("joint encoder/head competence threshold failed")
        return rows, metrics, memories, decoder, frozenset(validation_days), \
            MappingProxyType({"trace": tuple(trace),
                              "best_validation": best_validation,
                              "best_reload_sha256": reload_sha256,
                              "decoder_sha256": _sha_bytes(module_state_bytes(decoder)),
                              "chronological_validation_only": True,
                              "validation_days": tuple(sorted(validation_days))})

    def _collect(self, model, arm: str):
        model.eval(); states = {}; probabilities = {}; memories = {}
        with torch.no_grad():
            for batch in self.batches:
                memory = model.encoder(
                    batch.continuous.to(self.device), batch.categorical.to(self.device),
                    batch.cutoffs.to(self.device), receive_clock_ns=batch.clock.to(self.device),
                    candidate_decision_ts_ns=batch.decisions.to(self.device),
                    asset_idx=C.ASSET_INDEX[batch.asset])
                out = model.head(
                    memory, batch.candidate_features.to(self.device),
                    batch.context_values.to(self.device), batch.context_type_ids.to(self.device),
                    batch.context_valid.to(self.device), C.ASSET_INDEX[batch.asset],
                    static_features=(batch.static_features.to(self.device)
                                     if arm in ("L1", "M1") else None))
                memories.update(zip(batch.candidate_ids, memory.cpu()))
                states.update(zip(batch.candidate_ids, out.decision_state.cpu().numpy()))
                probabilities.update(zip(batch.candidate_ids,
                                         torch.sigmoid(out.action_logit).cpu().numpy()))
        ids = tuple(sorted(states, key=lambda cid: next(i for i, x in enumerate(
            self._manifest.candidate_id) if x == cid)))
        meta = {cid: (a, d) for cid, a, d in zip(self._manifest.candidate_id,
                                                 self._manifest.asset, self._manifest.day)}
        bindings = {x.candidate_id: x for x in self.stage.diagnostic_corpus.bindings}
        examples = {example.candidate_id: example
                    for spec in self.stage.corpus_stage.corpus.sessions
                    for example in spec.examples}
        rows = FrozenRepresentationRows(
            np.asarray([states[cid] for cid in ids], np.float32), np.asarray(ids),
            np.asarray([meta[cid][0] for cid in ids]),
            np.asarray([meta[cid][1] for cid in ids], np.int64),
            np.asarray([bindings[cid].decision_ts_ns for cid in ids], np.int64),
            np.asarray([bindings[cid].action_target for cid in ids], np.int8),
            np.asarray([bindings[cid].action_loss_mask for cid in ids], bool),
            np.asarray([examples[cid].phase for cid in ids], str),
            np.full(len(ids), "FIT"), "E1", group_semantics="PHASE",
        )
        p = np.asarray([probabilities[cid] for cid in ids], np.float64)
        return rows, self._metrics(rows, p), memories, states, probabilities

    def _pairlogit_depth_rows(self) -> FrozenRepresentationRows:
        """Encode the independent real phase-depth population with frozen M1."""
        if not self._pairlogit_depth_batches or not self._pairlogit_depth_manifest_sha256:
            raise RealDiagnosticExecutorRefusal("PairLogit depth batches were not prepared")
        model = self._models()["M1"].to(self.device)
        model.eval(); states: dict[str, np.ndarray] = {}
        with torch.no_grad():
            for batch in self._pairlogit_depth_batches:
                memory = model.encoder(
                    batch.continuous.to(self.device), batch.categorical.to(self.device),
                    batch.cutoffs.to(self.device), receive_clock_ns=batch.clock.to(self.device),
                    candidate_decision_ts_ns=batch.decisions.to(self.device),
                    asset_idx=C.ASSET_INDEX[batch.asset])
                out = model.head(
                    memory, batch.candidate_features.to(self.device),
                    batch.context_values.to(self.device), batch.context_type_ids.to(self.device),
                    batch.context_valid.to(self.device), C.ASSET_INDEX[batch.asset],
                    static_features=batch.static_features.to(self.device))
                states.update(zip(batch.candidate_ids,
                                  out.decision_state.float().cpu().numpy()))
        model.cpu()
        bindings = {row.candidate_id: row for row in self.stage.diagnostic_corpus.bindings}
        examples = {example.candidate_id: example
                    for spec in self.stage.corpus_stage.corpus.sessions
                    for example in spec.examples}
        ids = tuple(cid for batch in self._pairlogit_depth_batches
                    for cid in batch.candidate_ids)
        if len(ids) != 264 or set(ids) != set(states):
            raise RealDiagnosticExecutorRefusal("PairLogit depth encoding coverage differs")
        rows = FrozenRepresentationRows(
            np.asarray([states[cid] for cid in ids], np.float32), np.asarray(ids, str),
            np.asarray([bindings[cid].asset for cid in ids], str),
            np.asarray([bindings[cid].trading_day for cid in ids], np.int64),
            np.asarray([bindings[cid].decision_ts_ns for cid in ids], np.int64),
            np.asarray([bindings[cid].action_target for cid in ids], np.int8),
            np.asarray([bindings[cid].action_loss_mask for cid in ids], bool),
            np.asarray([examples[cid].phase for cid in ids], str),
            np.full(len(ids), "PAIR_FIT"), "E1", group_semantics="PHASE")
        counts = {asset: exact_pair_manifest(rows, asset).group_count for asset in C.ASSETS}
        if any(value != 44 for value in counts.values()):
            raise RealDiagnosticExecutorRefusal(
                f"PairLogit encoded phase census differs: {counts}")
        return rows

    def fit_catboost_competence(
        self, rows: FrozenRepresentationRows,
    ) -> CatBoostCompetenceResult:
        """Fit action attribution on 192 rows and PairLogit on 264 depth rows."""
        depth = self._pairlogit_depth_rows()
        fitted = fit_diagnostic_catboost(
            rows, expected_representation_sha256=rows.representation_sha256,
            pair_rows=depth)
        result = rehearse_catboost_competence(
            rows, expected_representation_sha256=rows.representation_sha256,
            pair_rows=depth, fitted=fitted)
        if any(result.pair_group_count_by_asset[asset] != 44 for asset in C.ASSETS):
            raise RealDiagnosticExecutorRefusal("PairLogit result lost frozen depth groups")
        self._pairlogit_depth_rows_sha256 = depth.representation_sha256
        # Retain the exact fitted PairLogit rankers for the full-population G7
        # deployment-depth rehearsal.  The 264 rows authorize the ranker fit;
        # they are never used as the mapper/replay population.
        self._acceptance_catboost_fit = fitted
        return result

    def _route_and_suffix(self, model, arm: str) -> Mapping[str, Any]:
        """Measure every input route and the exact causal suffix boundary."""
        encoder = model.encoder
        model.eval(); model.zero_grad(set_to_none=True)
        batch = max(self.batches, key=lambda b: len(b.continuous))
        n = min(len(batch.continuous), 96); cutoff = min(64, n)
        if cutoff <= 0:
            raise RealDiagnosticExecutorRefusal("route gate has an empty real prefix")
        x = batch.continuous[:n].to(self.device).clone().requires_grad_(True)
        k = batch.categorical[:n].to(self.device)
        clock = batch.clock[:n].to(self.device)
        cut = torch.tensor([cutoff], device=self.device)
        decision = torch.tensor([int(clock[cutoff - 1]) + 1], device=self.device)
        memory = encoder(x, k, cut, receive_clock_ns=clock,
                         candidate_decision_ts_ns=decision, asset_idx=0)
        static = (batch.static_features[:1].to(self.device)
                  if arm in ("L1", "M1") else None)

        def decide(raw):
            return model.head(
                raw, batch.candidate_features[:1].to(self.device),
                batch.context_values[:1].to(self.device),
                batch.context_type_ids.to(self.device),
                batch.context_valid[:1].to(self.device),
                C.ASSET_INDEX[batch.asset], static_features=static,
            )

        base = decide(memory)
        base.action_logit.sum().backward()
        if x.grad is None or not all(bool(x.grad[:, i].abs().sum() > 0)
                                     for i in range(x.shape[1])):
            raise RealDiagnosticExecutorRefusal("continuous route gradient failed")
        embeddings = ([*encoder.current.local.category_embeddings]
                      if isinstance(encoder, CurrentEncoderAdapter)
                      else ([*encoder.stem.category_embeddings]
                            if hasattr(encoder, "stem")
                            else [*encoder.category_embeddings]))
        if any(e.weight.grad is None or not bool(e.weight.grad.abs().sum() > 0)
               for e in embeddings):
            raise RealDiagnosticExecutorRefusal("categorical route gradient failed")

        route_delta = {}; suffix_checks = []
        with torch.no_grad():
            # Every expanded continuous and every exact categorical route must
            # alter both raw memory and the deployed action path independently.
            row = min(cutoff - 1, 3)
            for field, name in enumerate(self.schema.continuous_fields):
                mutant = x.detach().clone(); mutant[row, field] += 1.25
                changed_memory = encoder(
                    mutant, k, cut, receive_clock_ns=clock,
                    candidate_decision_ts_ns=decision, asset_idx=0)
                changed = decide(changed_memory)
                memory_delta = float((changed_memory - memory.detach()).abs().max())
                action_delta = float(
                    (changed.action_logit - base.action_logit.detach()).abs().max())
                if memory_delta <= 1e-6 or action_delta <= 1e-6:
                    raise RealDiagnosticExecutorRefusal(
                        f"continuous route did not reach action: {name}")
                route_delta[name] = (memory_delta, action_delta)
            for field, (name, size) in enumerate(zip(CATEGORICAL_FIELDS,
                                                       CATEGORY_SIZES)):
                mutant = k.clone()
                mutant[row, field] = (mutant[row, field] + 1) % size
                changed_memory = encoder(
                    x.detach(), mutant, cut, receive_clock_ns=clock,
                    candidate_decision_ts_ns=decision, asset_idx=0)
                changed = decide(changed_memory)
                memory_delta = float((changed_memory - memory.detach()).abs().max())
                action_delta = float(
                    (changed.action_logit - base.action_logit.detach()).abs().max())
                if memory_delta <= 1e-6 or action_delta <= 1e-6:
                    raise RealDiagnosticExecutorRefusal(
                        f"categorical route did not reach action: {name}")
                route_delta[name] = (memory_delta, action_delta)

            # Undefined-price handling has two separate observable routes:
            # mask-only, and a semantically consistent price-plus-mask change.
            price_column = self.schema.continuous_fields.index("raw.price")
            missing_column = CATEGORICAL_FIELDS.index("price_undef_mask")
            mask_only = k.clone(); mask_only[row, missing_column] ^= 1
            mask_memory = encoder(
                x.detach(), mask_only, cut, receive_clock_ns=clock,
                candidate_decision_ts_ns=decision, asset_idx=0)
            mask_output = decide(mask_memory)
            consistent_x = x.detach().clone(); consistent_k = k.clone()
            consistent_k[row, missing_column] ^= 1
            if int(consistent_k[row, missing_column]) & 1:
                zero_normalized = ((0.0 - float(self.location[price_column]))
                                   / float(self.scale[price_column]))
                if bool(self.event_constant[price_column]):
                    zero_normalized = 0.0
                consistent_x[row, price_column] = zero_normalized
            else:
                consistent_x[row, price_column] += 1.25
            consistent_memory = encoder(
                consistent_x, consistent_k, cut, receive_clock_ns=clock,
                candidate_decision_ts_ns=decision, asset_idx=0)
            consistent_output = decide(consistent_memory)
            undefined_deltas = {
                "mask_only_memory": float((mask_memory - memory.detach()).abs().max()),
                "mask_only_action": float((mask_output.action_logit
                    - base.action_logit.detach()).abs().max()),
                "price_plus_mask_memory": float((consistent_memory
                    - memory.detach()).abs().max()),
                "price_plus_mask_action": float((consistent_output.action_logit
                    - base.action_logit.detach()).abs().max()),
            }
            if any(value <= 1e-6 for value in undefined_deltas.values()):
                raise RealDiagnosticExecutorRefusal(
                    "undefined-price mask/price routes did not reach action")

            def assert_suffix(candidate_x, candidate_k, candidate_clock,
                              label: str) -> None:
                other_memory = encoder(
                    candidate_x, candidate_k, cut,
                    receive_clock_ns=candidate_clock,
                    candidate_decision_ts_ns=decision, asset_idx=0)
                if not torch.equal(memory.detach(), other_memory):
                    raise RealDiagnosticExecutorRefusal(
                        f"suffix changed raw memory: {label}")
                assert_tensor_tree_identical(base, decide(other_memory))
                suffix_checks.append(label)

            # Mutate each already-present post-cutoff coordinate independently.
            if cutoff < n:
                for field, name in enumerate(self.schema.continuous_fields):
                    mutant = x.detach().clone(); mutant[cutoff, field] += 1.25
                    assert_suffix(mutant, k, clock, f"mutate-continuous:{name}")
                for field, (name, size) in enumerate(zip(CATEGORICAL_FIELDS,
                                                          CATEGORY_SIZES)):
                    mutant = k.clone()
                    mutant[cutoff, field] = (mutant[cutoff, field] + 1) % size
                    assert_suffix(x.detach(), mutant, clock,
                                  f"mutate-categorical:{name}")

            # Append every field independently both exactly at the decision
            # clock and strictly after it.  The cutoff is a left searchsorted
            # boundary, so neither suffix is ever visible.
            append_clocks = {
                "equal": torch.cat((clock, decision.to(dtype=clock.dtype))),
                "after": torch.cat((clock, torch.tensor(
                    [max(int(clock[-1]), int(decision[0])) + 1],
                    device=self.device, dtype=clock.dtype))),
            }
            base_append_x = torch.cat((x.detach(), x.detach()[-1:].clone()), 0)
            base_append_k = torch.cat((k, k[-1:].clone()), 0)
            for clock_kind, append_clock in append_clocks.items():
                for field, name in enumerate(self.schema.continuous_fields):
                    mutant = base_append_x.clone(); mutant[-1, field] += 1.25
                    assert_suffix(mutant, base_append_k, append_clock,
                                  f"append-{clock_kind}-continuous:{name}")
                for field, (name, size) in enumerate(zip(CATEGORICAL_FIELDS,
                                                          CATEGORY_SIZES)):
                    mutant = base_append_k.clone()
                    mutant[-1, field] = (mutant[-1, field] + 1) % size
                    assert_suffix(base_append_x, mutant, append_clock,
                                  f"append-{clock_kind}-categorical:{name}")

            occluded = decide(torch.zeros_like(memory))
            occlusion_delta = float(
                (occluded.action_logit - base.action_logit).abs().max())
            if occlusion_delta <= 1e-6:
                raise RealDiagnosticExecutorRefusal(
                    "decision ignores raw event memory")

        # Five independent real-clock signatures: recent raw block, 0-60s,
        # 60-300s, 300-900s and older history.
        routed = False; band_deltas = {}
        for candidate_batch in sorted(
                self.batches, key=lambda value: len(value.continuous), reverse=True):
            for local, cutoff_value in enumerate(candidate_batch.cutoffs.tolist()):
                if cutoff_value < 5:
                    continue
                now = int(candidate_batch.decisions[local])
                clocks = candidate_batch.clock[:cutoff_value]
                ages = now - clocks
                recent_pool = torch.arange(cutoff_value) >= max(0, cutoff_value - 64)
                band60 = (ages >= 0) & (ages < 60_000_000_000)
                band300 = ((ages >= 60_000_000_000)
                           & (ages < 300_000_000_000))
                band900 = ((ages >= 300_000_000_000)
                           & (ages < 900_000_000_000))
                older = ages >= 900_000_000_000
                if not all(bool(mask.any()) for mask in
                           (recent_pool, band60, band300, band900, older)):
                    continue
                recent_index = int(torch.nonzero(recent_pool, as_tuple=False)[-1])
                minute_candidates = torch.nonzero(
                    band60 & (torch.arange(cutoff_value) != recent_index),
                    as_tuple=False).flatten()
                if not len(minute_candidates):
                    continue
                indices = {
                    "recent": recent_index,
                    "0_60": int(minute_candidates[-1]),
                    "60_300": int(torch.nonzero(band300, as_tuple=False)[-1]),
                    "300_900": int(torch.nonzero(band900, as_tuple=False)[-1]),
                    "older": int(torch.nonzero(older, as_tuple=False)[-1]),
                }
                designated = {"recent": 0, "0_60": 1, "60_300": 2,
                              "300_900": 3, "older": 3}
                bx = candidate_batch.continuous.to(self.device)
                bk = candidate_batch.categorical.to(self.device)
                bc = candidate_batch.clock.to(self.device)
                bcut = candidate_batch.cutoffs[local:local + 1].to(self.device)
                bd = candidate_batch.decisions[local:local + 1].to(self.device)
                with torch.no_grad():
                    reference = encoder(
                        bx, bk, bcut, receive_clock_ns=bc,
                        candidate_decision_ts_ns=bd,
                        asset_idx=C.ASSET_INDEX[candidate_batch.asset])
                    for band_name, index in indices.items():
                        mutant = bx.clone(); mutant[index, 0] += 1.25
                        changed = encoder(
                            mutant, bk, bcut, receive_clock_ns=bc,
                            candidate_decision_ts_ns=bd,
                            asset_idx=C.ASSET_INDEX[candidate_batch.asset])
                        token = designated[band_name] if arm == "M1" else slice(None)
                        delta = float((changed[:, token]
                                       - reference[:, token]).abs().max())
                        expected_change = (index >= cutoff_value - 64
                                           if arm in ("L0", "L1") else True)
                        if expected_change != (delta > 1e-6):
                            raise RealDiagnosticExecutorRefusal(
                                f"arm-specific real time-band signature differs: {band_name}")
                        band_deltas[band_name] = {
                            "index": index, "delta": delta,
                            "expected_change": expected_change,
                            "designated_token": (designated[band_name]
                                                 if arm == "M1" else "ALL"),
                        }
                routed = True
                break
            if routed:
                break
        if not routed or set(band_deltas) != {
                "recent", "0_60", "60_300", "300_900", "older"}:
            raise RealDiagnosticExecutorRefusal(
                "competence slice lacks five independent real time bands")
        evidence = {
            "schema": "entry-v2-arm-route-suffix-evidence-v1",
            "arm": arm, "continuous_route_count": len(self.schema.continuous_fields),
            "categorical_route_count": len(CATEGORICAL_FIELDS),
            "route_delta": route_delta, "undefined_price": undefined_deltas,
            "suffix_checks": suffix_checks, "suffix_check_count": len(suffix_checks),
            "five_time_bands": band_deltas,
            "raw_memory_occlusion_action_delta": occlusion_delta,
        }
        evidence["receipt_sha256"] = _sha(evidence)
        return MappingProxyType(evidence)

    def _token_occlusion_evidence(
            self, model, arm: str, rows: FrozenRepresentationRows,
    ) -> Mapping[str, Any]:
        """Measure each frozen raw token without retraining any parameter."""
        model.eval()
        probability_by_surface: dict[str, dict[str, float]] = {
            "BASE": {}, "TOKEN_0": {}, "TOKEN_1": {},
            "TOKEN_2": {}, "TOKEN_3": {},
        }
        with torch.no_grad():
            for batch in self.batches:
                memory = model.encoder(
                    batch.continuous.to(self.device),
                    batch.categorical.to(self.device),
                    batch.cutoffs.to(self.device),
                    receive_clock_ns=batch.clock.to(self.device),
                    candidate_decision_ts_ns=batch.decisions.to(self.device),
                    asset_idx=C.ASSET_INDEX[batch.asset],
                )
                if memory.ndim != 3 or memory.shape[1] != 4:
                    raise RealDiagnosticExecutorRefusal(
                        "token occlusion requires the exact four-token raw memory")
                static = (batch.static_features.to(self.device)
                          if arm in ("L1", "M1") else None)

                def score(candidate_memory: torch.Tensor) -> np.ndarray:
                    output = model.head(
                        candidate_memory,
                        batch.candidate_features.to(self.device),
                        batch.context_values.to(self.device),
                        batch.context_type_ids.to(self.device),
                        batch.context_valid.to(self.device),
                        C.ASSET_INDEX[batch.asset], static_features=static,
                    )
                    return torch.sigmoid(output.action_logit).float().cpu().numpy()

                surfaces = {"BASE": score(memory)}
                for token in range(4):
                    occluded = memory.clone(); occluded[:, token] = 0
                    surfaces[f"TOKEN_{token}"] = score(occluded)
                for surface, values in surfaces.items():
                    probability_by_surface[surface].update(
                        (candidate_id, float(value)) for candidate_id, value
                        in zip(batch.candidate_ids, values))

        expected_ids = tuple(map(str, rows.candidate_id))
        if any(set(values) != set(expected_ids)
               for values in probability_by_surface.values()):
            raise RealDiagnosticExecutorRefusal(
                "token occlusion candidate coverage differs")
        examples = {example.candidate_id: example
                    for spec in self.stage.corpus_stage.corpus.sessions
                    for example in spec.examples}
        outcomes = self.stage.corpus_stage.corpus.replay.outcomes
        days = tuple(sorted(set(map(int, rows.day))))
        denominator = self.stage.corpus_stage.corpus.replay.sessions_for(days)

        def replay_surface(surface: str) -> tuple[Mapping[str, Any], tuple[float, ...]]:
            probability = np.asarray(
                [probability_by_surface[surface][candidate_id]
                 for candidate_id in expected_ids], np.float64)
            metrics = tuple(map(float, self._metrics(rows, probability)))
            arrivals = tuple(ScoredArrival(
                examples[candidate_id], EntryScore(
                    candidate_id, examples[candidate_id].asset,
                    examples[candidate_id].decision_ts_ns,
                    f"competence-occlusion-{arm}-{surface}",
                    float(value), float(value), 0.0, 0.0, 0.0, 0.0, 0.0,
                    bool(value >= .5),
                ), outcomes[candidate_id],
            ) for candidate_id, value in zip(expected_ids, probability))
            evaluation = replay(arrivals, expected_sessions=denominator)
            summary = {
                "trades": evaluation.trades,
                "total_pnl_usd": evaluation.total_pnl_usd,
                "usd_per_asset_day": evaluation.usd_per_asset_day,
                "usd_per_trade": evaluation.usd_per_trade,
                "max_drawdown_usd": evaluation.max_drawdown_usd,
                "drawdown_p90_usd": evaluation.drawdown_p90_usd,
                "asset_days": evaluation.asset_days,
                "trade_ids_sha256": _sha(
                    [trade.candidate_id for trade in evaluation.trade_results]),
            }
            return summary, metrics

        baseline_replay, baseline_metrics = replay_surface("BASE")
        baseline_probability = np.asarray(
            [probability_by_surface["BASE"][candidate_id]
             for candidate_id in expected_ids], np.float64)
        token_evidence = {}
        for token in range(4):
            surface = f"TOKEN_{token}"
            measured_replay, measured_metrics = replay_surface(surface)
            measured_probability = np.asarray(
                [probability_by_surface[surface][candidate_id]
                 for candidate_id in expected_ids], np.float64)
            probability_linf = float(np.max(np.abs(
                measured_probability - baseline_probability)))
            if probability_linf <= 1e-6 or not np.isfinite(probability_linf):
                raise RealDiagnosticExecutorRefusal(
                    f"raw token {token} has no deployed no-retrain effect")
            token_evidence[str(token)] = {
                "probability_linf": probability_linf,
                "metrics": {
                    "minimum_auroc": measured_metrics[0],
                    "minimum_ap": measured_metrics[1],
                    "maximum_bce": measured_metrics[2],
                },
                "metric_delta": {
                    "minimum_auroc": measured_metrics[0] - baseline_metrics[0],
                    "minimum_ap": measured_metrics[1] - baseline_metrics[1],
                    "maximum_bce": measured_metrics[2] - baseline_metrics[2],
                },
                "replay": measured_replay,
                "replay_delta": {
                    key: float(measured_replay[key]) - float(baseline_replay[key])
                    for key in ("trades", "total_pnl_usd", "usd_per_asset_day",
                                "usd_per_trade", "max_drawdown_usd",
                                "drawdown_p90_usd")
                },
            }
        evidence = {
            "schema": "entry-v2-no-retrain-token-occlusion-v1",
            "arm": arm, "threshold": .5,
            "candidate_count": len(expected_ids),
            "baseline_metrics": {
                "minimum_auroc": baseline_metrics[0],
                "minimum_ap": baseline_metrics[1],
                "maximum_bce": baseline_metrics[2],
            },
            "baseline_replay": baseline_replay,
            "tokens": token_evidence,
        }
        evidence["receipt_sha256"] = _sha(evidence)
        return MappingProxyType(evidence)

    def train_and_rehearse_arm(self, loaded, manifest, arm):
        self._prepare(manifest); self._manifest = manifest
        model = self._models()[arm]
        if arm == "C1":
            model.encoder.load_state_dict(self._models()["C0"].encoder.state_dict(), strict=True)
        if arm == "L1":
            model.encoder.load_state_dict(self._models()["L0"].encoder.state_dict(), strict=True)
        rows, metrics, memories, decoder, reconstruction_days, field_receipt = \
            self._encode(model, arm)
        route_receipt = self._route_and_suffix(model, arm)
        occlusion_receipt = self._token_occlusion_evidence(model, arm, rows)
        memory = torch.stack([memories[cid] for cid in rows.candidate_id]).to(self.device)
        last_x = torch.cat([b.last_continuous for b in self.batches]).to(self.device)
        last_k = torch.cat([b.last_categorical for b in self.batches]).to(self.device)
        order = [cid for b in self.batches for cid in b.candidate_ids]
        position = {cid: i for i, cid in enumerate(order)}
        take = torch.tensor([position[str(cid)] for cid in rows.candidate_id], device=self.device)
        last_x, last_k = last_x[take], last_k[take]
        validation_take = torch.tensor([int(day) in reconstruction_days
            for day in rows.day], dtype=torch.bool, device=self.device)
        decoder = decoder.to(self.device).eval()
        receipt = reconstruction_receipt(
            decoder, memory[validation_take], last_x[validation_take],
            last_k[validation_take])
        if not receipt.passed:
            raise RealDiagnosticExecutorRefusal("last-row reconstruction competence failed")
        artifact = _sha_bytes(module_state_bytes(model))
        self.arm_rows[arm] = rows
        initial_heads = {value.shared_head_initial_bytes for value in self._models().values()}
        shared_exact = len(initial_heads) == 1
        if not shared_exact:
            raise RealDiagnosticExecutorRefusal("arm shared-head initialization differs")
        roster = tuple(self.stage.diagnostic_corpus.bindings)
        firewall_sha256 = _fit_only_loaded_roster_firewall(
            self.stage, roster, required_candidate_ids=manifest.candidate_id)
        isolation_before = _component_fit_projection(
            roster, manifest, self.batches, include_action=True)
        visible_index = next(i for i, x in enumerate(roster)
                             if x.candidate_id in set(manifest.candidate_id)
                             and x.action_loss_mask)
        canary = list(roster); visible = canary[visible_index]
        canary[visible_index] = replace(visible, action_target=not visible.action_target)
        canary_hash = _component_fit_projection(
            canary, manifest, self.batches, include_action=True)
        def refit(authority):
            indexed = {row.candidate_id: row for row in authority}
            target = np.asarray([indexed[str(cid)].action_target
                                 for cid in rows.candidate_id], np.int8)
            recipient = np.asarray([indexed[str(cid)].action_loss_mask
                                    for cid in rows.candidate_id], bool)
            return _bounded_supervised_fit_sha(
                rows.representation, target, recipient, seed=20260816)
        refit_before = refit(roster)
        refit_canary = refit(canary)
        firewall_exact = (bool(firewall_sha256)
                          and canary_hash != isolation_before
                          and refit_canary != refit_before)
        if not firewall_exact:
            raise RealDiagnosticExecutorRefusal(
                "arm fit-only firewall or visible-row canary failed")
        arm_evidence = {"schema": "entry-v2-arm-competence-evidence-v1",
                         "arm": arm, "model": artifact,
                         "joint_field_dense": dict(field_receipt),
                         "route_and_suffix": dict(route_receipt),
                         "no_retrain_token_occlusion": dict(occlusion_receipt),
                         "fit_only_firewall_sha256": firewall_sha256,
                         "fit_refit_before": refit_before,
                         "visible_refit_canary": refit_canary,
                         "selected_horizon_schema_sha256":
                            SELECTED_HORIZON_SCHEMA_SHA256,
                         "selected_horizon_normalizer_sha256":
                            self.selected_horizon_normalizer["receipt_sha256"],
                         "selected_horizon_carrier_receipts_sha256":
                            _sha(sorted(self._selected_horizon_receipts)),
                         "ordinal_law": "FOUR_CUMULATIVE_BCE_GE_1_TO_4"}
        artifact = _sha(arm_evidence)
        self._acceptance_component_evidence[
            f"acceptance/evidence/arm-{arm}.json"
        ] = _canonical_json_bytes({**arm_evidence, "receipt_sha256": artifact})
        return ArmRehearsalResult(
            arm, manifest.receipt_sha256, self.schema.sha256, True, True,
            receipt.continuous_mae, receipt.categorical_accuracy,
            metrics[0], metrics[1], metrics[2], shared_exact, True, True,
            firewall_exact,
            rows, artifact,
        )

    # Atlas fitting is deliberately delegated to the exact registered kernels,
    # but assembled here over the same 192 real candidate rows.
    def fit_atlas(self, loaded, manifest):
        self._prepare(manifest); self._manifest = manifest
        wanted = {cid: i for i, cid in enumerate(manifest.candidate_id)}
        static = np.empty((len(wanted), 1865), np.float32)
        pretext_sessions = []; target_parts: dict[str, list[tuple[np.ndarray, ProbeTarget]]] = {
            spec.probe_id: [] for spec in PROBE_REGISTRY}
        c1_spec = next(spec for spec in PROBE_REGISTRY if spec.probe_id == "C01P01")
        unique_days = sorted(set(map(int, manifest.day)))
        validation_days = set(unique_days[-max(1, int(np.ceil(.1 * len(unique_days)))):])
        c1_raw = []
        for batch in self.batches:
            session = next(s for s in self.stage.diagnostic_corpus.sessions
                           if s.key == (batch.asset, batch.day))
            local_map = {cid: i for i, cid in enumerate(session.atlas.candidate_ids)}
            local = np.asarray([local_map[cid] for cid in batch.candidate_ids], np.int64)
            preliminary = materialize_probe_target(session.atlas, c1_spec, fit_context={
                "c1_location": np.zeros(21), "c1_scale": np.ones(21),
                "fit_population_sha256": manifest.receipt_sha256,
            })
            supported = preliminary.validity_mask[local] & (batch.day not in validation_days)
            if supported.any():
                c1_raw.append(preliminary.values[local][:, np.r_[0, np.arange(9, 29)]][supported])
        if not c1_raw:
            raise RealDiagnosticExecutorRefusal("mixed-event normalizer has no fit rows")
        c1_values = np.concatenate(c1_raw); c1_location = c1_values.mean(0)
        c1_scale = c1_values.std(0); c1_scale[c1_scale == 0] = 1.0
        fit_context = {"c1_location": c1_location, "c1_scale": c1_scale,
                       "fit_population_sha256": manifest.receipt_sha256}
        # C22 transform authorities are fitted once from TRAIN-only raw
        # trajectories, then frozen and shared by real/twin consumers.
        c22_base = next(spec for spec in PROBE_REGISTRY
                        if spec.cell == 22 and _probe_variant(spec) == 1)
        trajectory_fit = []
        censor_fit: dict[int, list[tuple[np.ndarray, np.ndarray]]] = {10: [], 24: []}
        for batch in self.batches:
            session = next(s for s in self.stage.diagnostic_corpus.sessions
                           if s.key == (batch.asset, batch.day))
            local_map = {cid: i for i, cid in enumerate(session.atlas.candidate_ids)}
            local = np.asarray([local_map[cid] for cid in batch.candidate_ids], np.int64)
            if batch.day not in validation_days:
                raw22 = materialize_probe_target(session.atlas, c22_base)
                valid22 = raw22.validity_mask[local]
                if valid22.any():
                    trajectory_fit.append(
                        raw22.values[local][valid22, :raw22.output_width])
                for cell in (10, 24):
                    base = next(spec for spec in PROBE_REGISTRY
                                if spec.cell == cell and _probe_variant(spec) == 1)
                    base_target = materialize_probe_target(session.atlas, base)
                    local_target = _target_take(base_target, local)
                    passage, censored = _competing_ipcw_observations(local_target)
                    censor_fit[cell].append((passage, censored))
        if not trajectory_fit:
            raise RealDiagnosticExecutorRefusal("C22 TRAIN transform population is empty")
        trajectory_reference = np.concatenate(trajectory_fit)
        trajectory_location = trajectory_reference.mean(0)
        trajectory_scale = trajectory_reference.std(0)
        trajectory_scale[trajectory_scale == 0] = 1.0
        trajectory_lower = np.quantile(trajectory_reference, .01, axis=0)
        trajectory_upper = np.quantile(trajectory_reference, .99, axis=0)
        equal = trajectory_lower >= trajectory_upper
        trajectory_upper[equal] = trajectory_lower[equal] + 1.0
        km_tables = {}
        for cell, pieces in censor_fit.items():
            times = np.concatenate([piece[0] for piece in pieces])
            events = np.concatenate([piece[1] for piece in pieces]).astype(bool)
            order = np.argsort(times, kind="stable"); times, events = times[order], events[order]
            survival = 1.0; table_t = []; table_s = []
            for timestamp in np.unique(times):
                at_risk = int(np.sum(times >= timestamp))
                censor_events = int(np.sum(events[times == timestamp]))
                if at_risk:
                    survival *= 1.0 - censor_events / at_risk
                table_t.append(float(timestamp)); table_s.append(max(.05, survival))
            km_tables[cell] = (np.asarray(table_t), np.asarray(table_s))

        def ipcw_for(session, cell: int) -> np.ndarray:
            base = next(spec for spec in PROBE_REGISTRY
                        if spec.cell == cell and _probe_variant(spec) == 1)
            target = materialize_probe_target(session.atlas, base)
            table_t, table_s = km_tables[cell]
            return _competing_candidate_ipcw(target, table_t, table_s)
        fit_contexts: dict[str, dict[tuple[str, int], Mapping[str, Any] | None]] = {}
        for spec in PROBE_REGISTRY:
            by_session = {}
            for session in self.stage.diagnostic_corpus.sessions:
                context: Mapping[str, Any] | None = None
                if spec.cell == 1:
                    context = fit_context
                elif spec.cell == 22 and _probe_variant(spec) in (2, 3, 4, 5, 6):
                    context = {"fit_population_sha256": manifest.receipt_sha256}
                    if _probe_variant(spec) == 2:
                        context = {**context, "location": trajectory_location,
                                   "scale": trajectory_scale}
                    elif _probe_variant(spec) == 3:
                        context = {**context, "lower": trajectory_lower,
                                   "upper": trajectory_upper}
                    elif _probe_variant(spec) == 4:
                        context = {**context, "rank_reference": trajectory_reference}
                elif ((spec.cell == 10 and _probe_variant(spec) == 4)
                      or (spec.cell == 24 and _probe_variant(spec) == 2)):
                    context = {"fit_population_sha256": manifest.receipt_sha256,
                               "ipcw_weights": ipcw_for(session, spec.cell)}
                by_session[session.key] = context
            fit_contexts[spec.probe_id] = by_session
        self._atlas_fit_context_by_probe_session = fit_contexts
        for batch in self.batches:
            rows = np.asarray([wanted[cid] for cid in batch.candidate_ids], np.int64)
            static[rows] = batch.static_features.numpy()
            pretext_sessions.append(CausalPretextSession(
                batch.session_id, batch.asset, str(batch.day), batch.continuous.numpy(),
                batch.categorical.numpy(), batch.clock.numpy(), batch.cutoffs.numpy(),
                batch.decisions.numpy(), rows, batch.candidate_ids,
            ))
            session = next(s for s in self.stage.diagnostic_corpus.sessions
                           if s.key == (batch.asset, batch.day))
            local_map = {cid: i for i, cid in enumerate(session.atlas.candidate_ids)}
            local = np.asarray([local_map[cid] for cid in batch.candidate_ids], np.int64)
            for spec in PROBE_REGISTRY:
                target = materialize_probe_target(session.atlas, spec,
                    fit_context=fit_contexts[spec.probe_id][session.key])
                target_parts[spec.probe_id].append((rows, _target_take(target, local)))
        targets = {}
        for spec in PROBE_REGISTRY:
            ordered = sorted(target_parts[spec.probe_id], key=lambda item: int(item[0].min()))
            targets[spec.probe_id] = _concat_targets([part for _, part in ordered])
        self._atlas_targets = targets
        fit_idx = np.arange(len(manifest.candidate_id), dtype=np.int64)
        pretexts = []
        all_consumers = tuple(spec.probe_id for spec in PROBE_REGISTRY)
        for probe_id in ("C01P01", "C02P01"):
            spec = next(s for s in PROBE_REGISTRY if s.probe_id == probe_id)
            target = targets[probe_id]
            if target.state != CellAvailability.MATERIALIZED:
                raise RealDiagnosticExecutorRefusal("mandatory mixed-event pretext unavailable")
            pretexts.append(fit_stage_pretext(
                "E1", pretext_sessions, CATEGORY_SIZES, spec, target,
                fit_indices=fit_idx, consumer_probe_ids=all_consumers,
            ))
        decisions = np.asarray([next(x.decision_ts_ns for x in
            self.stage.diagnostic_corpus.bindings if x.candidate_id == cid)
            for cid in manifest.candidate_id], np.int64)
        ordered_pretext = np.concatenate(
            (pretexts[0].frozen_state, pretexts[1].frozen_state), axis=1)
        probe_rows = ProbeRows(static, ordered_pretext, np.asarray(manifest.asset),
                               np.asarray(manifest.day), decisions,
                               np.asarray(manifest.candidate_id))
        permutation = stage_global_recipient_fixed_permutation(
            np.full(len(fit_idx), "FIT"), manifest.asset, manifest.day,
            np.asarray([next(x.action_loss_mask for x in self.stage.diagnostic_corpus.bindings
                             if x.candidate_id == cid) for cid in manifest.candidate_id]),
            seed=20260816,
        )
        torch.manual_seed(20260816); initialization = AtlasProbeNet()
        real_hash: dict[str, str | None] = {}; twin_hash: dict[str, str | None] = {}
        learned = 0
        separation = 0
        for spec in PROBE_REGISTRY:
            target = targets[spec.probe_id]
            twin = permute_probe_target_recipient_fixed(target, permutation)
            days = np.asarray(manifest.day); unique = sorted(set(days.tolist()))
            validation = set(unique[-max(1, int(np.ceil(.1 * len(unique)))):])
            train_ok = target.validity_mask[~np.isin(days, list(validation))].any()
            val_ok = target.validity_mask[np.isin(days, list(validation))].any()
            if target.state != CellAvailability.MATERIALIZED or not train_ok or not val_ok \
                    or not twin.validity_mask.any():
                real_hash[spec.probe_id] = twin_hash[spec.probe_id] = None
                continue
            real = fit_probe(spec, probe_rows, target, fit_indices=fit_idx,
                             initialization=initialization)
            twin_spec = shuffled_probe_for(
                spec,
                available=self.stage.diagnostic_corpus.sessions[0].atlas.shuffled_probes,
            )
            twin = replace(twin, probe_id=twin_spec.probe_id,
                           schema_sha256=probe_target_schema_sha256(
                               twin_spec.probe_id, twin.output_width, twin.output_layout,
                               twin.direction, twin.transform_provenance_sha256,
                               twin.prediction_width, twin.prediction_layout))
            shuffled = fit_probe(twin_spec, probe_rows, twin, fit_indices=fit_idx,
                                 initialization=initialization)
            real_hash[spec.probe_id] = real.best_checkpoint_sha256
            twin_hash[spec.probe_id] = shuffled.best_checkpoint_sha256
            learned += int(real.best_validation_loss < real.initial_validation_loss)
            separation += int(real.best_validation_loss < shuffled.best_validation_loss)
        if learned == 0 or separation == 0:
            raise RealDiagnosticExecutorRefusal("atlas learned no real-beyond-twin objective")
        artifact = _sha({"pretext": [p.checkpoint_sha256 for p in pretexts],
                         "real": real_hash, "twin": twin_hash})
        target_digest = _sha({key: _sha_bytes(value.values.tobytes())
                              for key, value in targets.items()})
        roster = tuple(self.stage.diagnostic_corpus.bindings)
        firewall_sha256 = _fit_only_loaded_roster_firewall(
            self.stage, roster, required_candidate_ids=manifest.candidate_id)
        projection = _sha({"inputs": _component_fit_projection(
            roster, manifest, self.batches, include_action=False),
            "targets": target_digest})
        first_key = sorted(targets)[0]
        canary_targets = {key: _sha_bytes(value.values.tobytes())
                          for key, value in targets.items()}
        changed_values = np.asarray(targets[first_key].values).copy()
        changed_values.flat[0] += 1.0
        canary_targets[first_key] = _sha_bytes(changed_values.tobytes())
        visible_target = targets[first_key]
        coordinate = np.asarray(visible_target.coordinate_mask, bool)
        count = coordinate.sum(1)
        scalar = np.divide((np.asarray(visible_target.values, np.float64)
                            * coordinate).sum(1), count,
                           out=np.zeros(len(count), np.float64), where=count > 0)
        target_mask = np.asarray(visible_target.validity_mask, bool) & (count > 0)
        probe_features = np.asarray(probe_rows.joined(), np.float32)
        binary_target = scalar > np.median(scalar[target_mask])
        target_refit_before = _bounded_supervised_fit_sha(
            probe_features, binary_target, target_mask,
            seed=20260820)
        changed_row = int(np.flatnonzero(target_mask)[0])
        changed_target = binary_target.copy(); changed_target[changed_row] = ~changed_target[changed_row]
        target_refit_canary = _bounded_supervised_fit_sha(
            probe_features, changed_target, target_mask,
            seed=20260820)
        firewall_exact = (bool(firewall_sha256) and _sha({"inputs":
            _component_fit_projection(roster, manifest, self.batches,
                                      include_action=False),
            "targets": _sha(canary_targets)}) != projection
            and target_refit_canary != target_refit_before)
        if not firewall_exact:
            raise RealDiagnosticExecutorRefusal(
                "atlas fit-only firewall or visible-target canary failed")
        return AtlasFitResult(
            manifest.receipt_sha256, tuple(p.checkpoint_sha256 for p in pretexts),
            real_hash, twin_hash, separation > 0, firewall_exact,
            _sha({"learned": learned, "real_beyond_twin": separation,
                  "consumer_mapping": [p.consumer_mapping_sha256 for p in pretexts]}),
            _sha({"artifact": artifact,
                  "fit_only_firewall_sha256": firewall_sha256,
                  "fit_refit_before": target_refit_before,
                  "visible_refit_canary": target_refit_canary}),
        )

    def fit_direct_head(self, loaded, manifest, representation):
        rows = self.arm_rows["M1"]
        if rows.representation_sha256 != representation.representation_sha256:
            raise RealDiagnosticExecutorRefusal("direct/M1 representation differs")
        # The M1 shared neural action head produced these states and already
        # passed exact 32/32 metrics; fit a fresh action head on the identical
        # frozen state to isolate downstream head competence.
        x = torch.from_numpy(rows.representation).to(self.device)
        y = torch.from_numpy(np.asarray(rows.action_target, np.float32)).to(self.device)
        supervised = torch.from_numpy(
            np.asarray(rows.action_loss_mask, bool)).to(self.device)
        head = torch.nn.Sequential(torch.nn.LayerNorm(512), torch.nn.Linear(512, 1)).to(self.device)
        optimizer = torch.optim.Adam(head.parameters(), lr=1e-2); gradient = False
        row_assets = np.asarray(rows.asset, str); row_days = np.asarray(rows.day, np.int64)
        fit_weights, fit_weight_receipt = action_fit_weights(
            row_assets, row_days, np.asarray(rows.action_target, np.int8),
            np.asarray(rows.action_loss_mask, bool), np.ones(len(row_days), bool))
        fit_weights_t = torch.from_numpy(np.asarray(fit_weights, np.float32)).to(self.device)
        for _ in range(400):
            optimizer.zero_grad(set_to_none=True); logits = head(x).squeeze(1)
            loss = (torch.nn.functional.binary_cross_entropy_with_logits(
                logits, y, reduction="none") * fit_weights_t).sum()
            loss.backward(); gradient |= bool(head[1].weight.grad.abs().sum() > 0)
            optimizer.step()
            if float(loss) <= .02: break
        p = torch.sigmoid(head(x).squeeze(1)).detach().cpu().numpy()
        self._direct_probability_by_id = {
            str(cid): float(value) for cid, value in zip(rows.candidate_id, p)}
        self._acceptance_direct_head = head.cpu()
        metrics = self._metrics(rows, p)
        roster = tuple(self.stage.diagnostic_corpus.bindings)
        firewall_sha256 = _fit_only_loaded_roster_firewall(
            self.stage, roster, required_candidate_ids=rows.candidate_id)
        row_ids = np.asarray(rows.candidate_id, str)
        def direct_projection(authority) -> str:
            index = {item.candidate_id: item for item in authority}
            target = np.asarray([index[cid].action_target for cid in row_ids], np.int8)
            recipient_mask = np.asarray(
                [index[cid].action_loss_mask for cid in row_ids], bool)
            return _sha({"representation": rows.representation_sha256,
                "target": _sha_bytes(target.tobytes()),
                "recipient": _sha_bytes(recipient_mask.tobytes()),
                "ids": row_ids.tolist()})
        fit_projection = direct_projection(roster)
        visible = next(i for i, item in enumerate(roster)
                       if item.candidate_id in set(row_ids.tolist())
                       and item.action_loss_mask)
        canary = list(roster); canary[visible] = replace(
            canary[visible], action_target=not canary[visible].action_target)
        visible_canary = direct_projection(canary)
        def refit(authority):
            index = {item.candidate_id: item for item in authority}
            target = np.asarray([index[cid].action_target for cid in row_ids], np.int8)
            allowed = np.asarray([index[cid].action_loss_mask for cid in row_ids], bool)
            return _bounded_supervised_fit_sha(
                rows.representation, target, allowed, seed=20260818)
        refit_before = refit(roster)
        refit_canary = refit(canary)
        firewall_exact = (bool(firewall_sha256)
                          and visible_canary != fit_projection
                          and refit_canary != refit_before)
        if not firewall_exact:
            raise RealDiagnosticExecutorRefusal(
                "direct-head fit-only firewall or visible-row canary failed")
        artifact = _sha({"checkpoint": _sha_bytes(module_state_bytes(head)),
                         "action_fit_weight_receipt_sha256":
                            fit_weight_receipt.receipt_sha256,
                         "fit_projection": fit_projection,
                         "visible_canary": visible_canary,
                         "fit_only_firewall_sha256": firewall_sha256,
                         "fit_refit_before": refit_before,
                         "visible_refit_canary": refit_canary})
        return DirectHeadResult(manifest.receipt_sha256, rows, *metrics, gradient,
                                firewall_exact, artifact)

    def fit_policy_and_replay(self, loaded, manifest, rows, catboost: CatBoostCompetenceResult):
        from .atlas_probe_model import FrozenLogisticBindingMapper
        competence_rows = rows
        if (catboost.representation_sha256 != competence_rows.representation_sha256
                or set(np.asarray(catboost.candidate_id, str).tolist())
                != set(np.asarray(competence_rows.candidate_id, str).tolist())):
            raise RealDiagnosticExecutorRefusal(
                "CatBoost competence rows differ before full policy scoring")
        rows, full_direct_probability, full_cat_probability, full_roster = \
            self._full_fit_only_policy_plane()
        ids = np.asarray(rows.candidate_id, str); days = np.asarray(rows.day, int)
        y = np.asarray(rows.action_target, int)
        recipient = np.asarray(rows.action_loss_mask, bool)
        e1_masks = {role: _rehearsal_mask(days, "E1r", role)
                    for role in ("FIT", "PLATT", "THRESHOLD", "FORWARD")}
        e2_masks = {role: _rehearsal_mask(days, "E2r", role)
                    for role in ("FIT", "PLATT", "THRESHOLD", "FORWARD")}
        if any(not bool(mask.any()) for mask in (*e1_masks.values(), *e2_masks.values())):
            raise RealDiagnosticExecutorRefusal("fit-only rehearsal chronology lacks candidates")
        if any(catboost.ranker_availability_by_asset[a] != "MATERIALIZED"
               for a in C.ASSETS):
            raise RealDiagnosticExecutorRefusal(
                "acceptance CatBoost PairLogit decision head is unavailable")
        branch_inputs = {
            "direct_neural": _decision_binding(full_direct_probability),
            "catboost": _decision_binding(full_cat_probability),
        }
        example = {item.candidate_id: item for spec in
                   self.stage.corpus_stage.corpus.sessions for item in spec.examples}
        outcomes = self.stage.corpus_stage.corpus.replay.outcomes
        expected_all = self.stage.corpus_stage.corpus.replay.expected_sessions
        def expected_days(start: int, end: int) -> tuple[int, ...]:
            return tuple(sorted({s.trading_day for s in expected_all
                                 if start <= s.trading_day <= end}))
        e1_days = {role: expected_days(*_rehearsal_bounds("E1r", role))
                   for role in ("THRESHOLD", "FORWARD")}
        e1_platt_days = expected_days(*_rehearsal_bounds("E1r", "PLATT"))
        e2_platt_days = expected_days(*_rehearsal_bounds("E2r", "PLATT"))
        e2_days = {role: expected_days(*_rehearsal_bounds("E2r", role))
                   for role in ("THRESHOLD", "FORWARD")}
        if len(e1_platt_days) != 7 or not all((*e1_days.values(), *e2_days.values(),
                                              e2_platt_days)):
            raise RealDiagnosticExecutorRefusal(
                "fit-only rehearsal eligible-day chronology differs")
        teacher = self.stage.corpus_stage.corpus.teacher
        ceiling_blocks = {
            f"{stage}.{role}" for stage in ("E1r", "E2r")
            for role in ("THRESHOLD", "FORWARD")
        }
        ceiling_receipts = dict(getattr(
            self, "_fit_only_ceiling_receipts", {}))
        if set(ceiling_receipts) != ceiling_blocks:
            raise RealDiagnosticExecutorRefusal(
                "fit-only preflight ceiling receipts were not retained")
        branch_evidence = {}; branch_candidates = {}; qualified = []
        selected = None
        for branch, features in branch_inputs.items():
            branch_stages = {}; branch_ok = True
            for stage_name, masks, threshold_days, forward_mask, forward_days in (
                ("E1r", e1_masks, e1_days["THRESHOLD"], e1_masks["FORWARD"],
                 e1_days["FORWARD"]),
                ("E2r", e2_masks, e2_days["THRESHOLD"], e2_masks["FORWARD"],
                 e2_days["FORWARD"]),
            ):
                fit_mask = masks["FIT"] & recipient
                fit_weight, weight_receipt = action_fit_weights(
                    np.asarray(rows.asset, str), days, y, recipient, fit_mask)
                mapper = FrozenLogisticBindingMapper().fit(
                    features, y, fit_mask, ids, sample_weight=fit_weight,
                    weight_receipt_sha256=weight_receipt.receipt_sha256)
                platt = masks["PLATT"] & recipient
                mapper.calibrate(features[platt], y[platt], ids[platt],
                                 threshold_selection_ids=ids[masks["THRESHOLD"]])
                probability, _ = mapper.predict(features)
                base_arrivals = tuple(ScoredArrival(
                    example[cid], EntryScore(cid, example[cid].asset,
                    example[cid].decision_ts_ns, f"fit-only-{stage_name}-{branch}",
                    float(p), float(p), 0.0, 0.0, float(p), 0.0, 0.0, False),
                    outcomes[cid]) for cid, p in zip(ids, probability))
                if {row.example.candidate_id for row in base_arrivals} != set(ids.tolist()):
                    raise RealDiagnosticExecutorRefusal(
                        "policy arrival roster differs from full CLEAR+READY population")
                thresholds = {}; parity = {}; funnels = {}; asset_ok = {}
                for asset in C.ASSETS:
                    local = np.flatnonzero(masks["THRESHOLD"]
                                           & (np.asarray(rows.asset, str) == asset))
                    expected_partition_ids = set(ids[masks["THRESHOLD"]
                        & (np.asarray(rows.asset, str) == asset)].tolist())
                    sessions = self.stage.corpus_stage.corpus.replay.sessions_for(
                        threshold_days, asset=asset)
                    arrivals = tuple(base_arrivals[i] for i in local)
                    if {row.example.candidate_id for row in arrivals} != expected_partition_ids:
                        raise RealDiagnosticExecutorRefusal(
                            "threshold replay arrivals omit full-roster partition rows")
                    sweep = fast_threshold_sweep(arrivals, probability[local], sessions)
                    parity[asset] = assert_fast_sweep_parity(
                        arrivals, probability[local], sessions, sweep,
                        samples=len(sweep.thresholds))
                    feasible = np.asarray([threshold_feasibility(
                        trades=int(sweep.trades[i]),
                        usd_per_trade=float(sweep.usd_per_trade[i]),
                        max_drawdown_usd=float(sweep.max_drawdown_usd[i]),
                        days_with_trades=int(sweep.days_with_trades[i]),
                        eligible_days=len(sweep.eligible_days)).feasible
                        for i in range(len(sweep.thresholds))], bool)
                    choices = np.flatnonzero(feasible)
                    if not len(choices):
                        thresholds[asset] = 1.0
                        funnels[asset] = {"status": "NO_FEASIBLE_THRESHOLD",
                                          "sweep": sweep.receipt_sha256}
                        asset_ok[asset] = False
                        continue
                    chosen = max(choices, key=lambda i: (
                        float(sweep.usd_per_asset_day[i]),
                        float(sweep.usd_per_trade[i]),
                        -float(sweep.max_drawdown_usd[i]),
                        -float(sweep.drawdown_p90_usd[i]),
                        float(sweep.thresholds[i]), int(sweep.trades[i])))
                    thresholds[asset] = float(sweep.thresholds[chosen])
                    funnels[asset] = {"status": "ELIGIBLE", "selected_index": int(chosen),
                                      "sweep": sweep.receipt_sha256}
                    asset_ok[asset] = True
                forward_ok = {asset: True for asset in C.ASSETS}
                forward_receipt = None
                if forward_mask is not None:
                    forward_scored = tuple(ScoredArrival(row.example, replace(
                        row.score, enter=row.score.take_probability >=
                        thresholds[row.example.asset]), row.outcome)
                        for row in base_arrivals)
                    denominator = self.stage.corpus_stage.corpus.replay.sessions_for(forward_days)
                    forward_eval = replay(
                        (forward_scored[i] for i in np.flatnonzero(forward_mask)),
                        expected_sessions=denominator)
                    by_asset = {row.asset: row for row in forward_eval.by_asset}
                    for asset in C.ASSETS:
                        active_days = sum(row.asset == asset and row.trades > 0
                                          for row in forward_eval.asset_day_results)
                        forward_ok[asset] = threshold_feasibility(
                            trades=by_asset[asset].trades,
                            usd_per_trade=by_asset[asset].usd_per_trade,
                            max_drawdown_usd=by_asset[asset].max_drawdown_usd,
                            days_with_trades=active_days,
                            eligible_days=len(forward_days)).feasible
                    forward_receipt = _sha({"evaluation": [asdict(x)
                        for x in forward_eval.by_asset], "days": forward_days})
                stage_ok = all(asset_ok.values()) and all(forward_ok.values())
                branch_ok &= stage_ok
                stage_status = ("ELIGIBLE" if stage_ok else
                                "NO_FEASIBLE_THRESHOLD" if not all(asset_ok.values()) else
                                "NO_FEASIBLE_FORWARD")
                branch_stages[stage_name] = {"mapper": mapper.parameter_sha256,
                    "calibrator": mapper.calibrator.parameter_sha256,
                    "weight_receipt": weight_receipt.receipt_sha256,
                    "thresholds": thresholds, "parity": parity, "funnels": funnels,
                    "platt_days": (e1_platt_days if stage_name == "E1r"
                                    else e2_platt_days),
                    "threshold_days": threshold_days,
                    "forward_ok": forward_ok, "forward_receipt": forward_receipt,
                    "status": stage_status}
                if stage_name == "E1r":
                    e1_candidate = (mapper, thresholds, probability, base_arrivals)
                    branch_candidates[branch] = e1_candidate
            branch_evidence[branch] = {"stages": branch_stages,
                                       "status": "ELIGIBLE" if branch_ok else "LOSER"}
            if branch_ok:
                qualified.append(branch)
                if selected is None:
                    selected = e1_candidate
        if selected is None:
            # Competence-trained heads are attribution diagnostics only.  They
            # cannot veto M8; the fresh full-population 5x2 rehearsal below is
            # the sole economic launch gate.
            selected_branch = "direct_neural"
            selected = branch_candidates.get(selected_branch)
            if selected is None:
                raise RealDiagnosticExecutorRefusal(
                    "fit-only policy attribution produced no executable mapper")
        mapper, threshold_by_asset, selected_probability, selected_arrivals = selected
        threshold_rows = e1_masks["THRESHOLD"]
        scored = tuple(ScoredArrival(row.example, replace(
            row.score, enter=row.score.take_probability >= threshold_by_asset[row.example.asset]),
            row.outcome) for row in selected_arrivals)
        denominator = self.stage.corpus_stage.corpus.replay.sessions_for(e1_days["THRESHOLD"])
        canonical = replay((scored[i] for i in np.flatnonzero(threshold_rows)),
                           expected_sessions=denominator)
        self._winner_mapper = copy.deepcopy(mapper)
        selected_branch = qualified[0] if qualified else selected_branch
        direct_features = branch_inputs[selected_branch]
        fit_mask = e1_masks["FIT"] & recipient
        direct_fit_probability, _ = mapper.predict(direct_features)
        prevalence = float(np.mean(y[fit_mask]))
        mapper_positive_skill = (log_loss(
            y[fit_mask], direct_fit_probability[fit_mask], labels=[0, 1])
            < log_loss(y[fit_mask], np.full(int(fit_mask.sum()), prevalence),
                       labels=[0, 1]))
        parity_measured = all(bool(value) for evidence in branch_evidence.values()
                              for stage in evidence["stages"].values()
                              for value in stage["parity"].values())
        replay_edge_receipt = canonical_replay_adversary_receipt()
        equal_time_ties = bool(replay_edge_receipt.get("receipt_sha256"))
        reversed_replay = replay(reversed(tuple(
            scored[i] for i in np.flatnonzero(threshold_rows))),
            expected_sessions=denominator)
        canonical_parity = reversed_replay == canonical
        full_denominator = (canonical.asset_days == len({
            (session.asset, session.trading_day) for session in denominator}))
        day_trade_totals: dict[int, int] = {}
        for row in canonical.asset_day_results:
            day_trade_totals[row.trading_day] = (
                day_trade_totals.get(row.trading_day, 0) + row.trades)
        occupancy_caps_cost_wall = (
            bool(replay_edge_receipt.get("receipt_sha256"))
            and all(row.trades <= 3 and np.isfinite(row.pnl_usd)
                    for row in canonical.asset_day_results)
            and all(value <= 9 for value in day_trade_totals.values())
        )
        mdd_exact = (reversed_replay.max_drawdown_usd == canonical.max_drawdown_usd
                     and reversed_replay.drawdown_p90_usd == canonical.drawdown_p90_usd)
        roster = tuple(self.stage.diagnostic_corpus.bindings)
        firewall_sha256 = _fit_only_loaded_roster_firewall(
            self.stage, roster, required_candidate_ids=ids)
        full_ids = set(ids.tolist())
        def full_policy_projection(authority) -> str:
            indexed = {row.candidate_id: row for row in authority}
            return _sha({"full_roster": dict(full_roster),
                         "rows": [(
                             cid,
                             (bool(indexed[cid].action_target)
                              if bool(indexed[cid].action_loss_mask) else None),
                             bool(indexed[cid].action_loss_mask),
                         ) for cid in ids.tolist()]})
        policy_projection = full_policy_projection(roster)
        visible_i = next(i for i, row in enumerate(roster)
                         if row.candidate_id in full_ids
                         and row.action_loss_mask
                         and _rehearsal_bounds("E1r", "FIT")[0]
                             <= row.trading_day
                             <= _rehearsal_bounds("E1r", "FIT")[1])
        canary = list(roster); visible = canary[visible_i]
        canary[visible_i] = replace(visible, action_target=not visible.action_target)
        visible_projection = full_policy_projection(canary)
        def policy_refit(authority):
            index = {item.candidate_id: item for item in authority}
            refit_target = np.asarray([index[cid].action_target for cid in ids], np.int8)
            refit_mask = np.asarray([index[cid].action_loss_mask for cid in ids], bool)
            return _bounded_supervised_fit_sha(
                direct_features, refit_target,
                refit_mask & e1_masks["FIT"], seed=20260819)
        policy_refit_before = policy_refit(roster)
        policy_refit_canary = policy_refit(canary)
        masked_i = next(i for i, row in enumerate(roster)
                        if row.candidate_id in full_ids
                        and not row.action_loss_mask)
        masked_canary = list(roster); masked = masked_canary[masked_i]
        masked_canary[masked_i] = replace(
            masked, action_target=not masked.action_target)
        masked_projection = full_policy_projection(masked_canary)
        masked_refit = policy_refit(masked_canary)
        firewall_exact = (bool(firewall_sha256)
                          and visible_projection != policy_projection
                          and policy_refit_canary != policy_refit_before
                          and masked_projection == policy_projection
                          and masked_refit == policy_refit_before)
        if not firewall_exact:
            raise RealDiagnosticExecutorRefusal(
                "policy fit-only firewall or visible-row canary failed")

        # Mutating a non-FIT auxiliary horizon must not reach the frozen FINAL
        # teacher, model inputs, objective/head score surface, or thresholds.
        # Execute the actual selected M1/direct/PairLogit forward path on one
        # such real row; only the detached auxiliary target is changed.
        binding_by_id = {row.candidate_id: row for row in roster}
        observed_by_day = {
            session.key: session for session in self.stage.diagnostic_corpus.sessions}
        auxiliary_batch = None
        for session_spec in sorted(
                self.stage.corpus_stage.corpus.sessions,
                key=lambda value: (value.trading_day, value.asset, value.session_id)):
            if session_spec.trading_day <= _rehearsal_bounds("E2r", "FIT")[1]:
                continue
            local = [index for index, candidate_id in enumerate(
                session_spec.candidate_ids)
                if candidate_id in full_ids]
            if not local:
                continue
            candidate_batch = self._build_full_policy_batch(
                session_spec, [local[0]],
                observed_by_day[(session_spec.asset, session_spec.trading_day)],
                binding_by_id,
            )
            valid_coordinate = torch.nonzero(
                candidate_batch.horizon_valid[0], as_tuple=False).flatten()
            if len(valid_coordinate):
                auxiliary_batch = (candidate_batch, int(valid_coordinate[0]))
                break
        if auxiliary_batch is None:
            raise RealDiagnosticExecutorRefusal(
                "teacher-isolation canary lacks a non-FIT auxiliary horizon")
        auxiliary_original, auxiliary_coordinate = auxiliary_batch
        changed_horizon = auxiliary_original.horizon_targets.clone()
        changed_horizon[0, auxiliary_coordinate] += 123.0
        auxiliary_mutant = replace(
            auxiliary_original, horizon_targets=changed_horizon)
        if torch.equal(auxiliary_original.horizon_targets,
                       auxiliary_mutant.horizon_targets):
            raise RealDiagnosticExecutorRefusal(
                "teacher-isolation auxiliary target mutation is ineffective")

        def frozen_auxiliary_forward(batch: _CandidateBatch) -> Mapping[str, str]:
            model = self._models()["M1"].to(self.device).eval()
            direct_head = self._acceptance_direct_head.to(self.device).eval()
            with torch.no_grad():
                with self._held_autocast():
                    memory = model.encoder(
                        batch.continuous.to(self.device),
                        batch.categorical.to(self.device),
                        batch.cutoffs.to(self.device),
                        receive_clock_ns=batch.clock.to(self.device),
                        candidate_decision_ts_ns=batch.decisions.to(self.device),
                        asset_idx=C.ASSET_INDEX[batch.asset],
                    )
                    output = model.head(
                        memory, batch.candidate_features.to(self.device),
                        batch.context_values.to(self.device),
                        batch.context_type_ids.to(self.device),
                        batch.context_valid.to(self.device),
                        C.ASSET_INDEX[batch.asset],
                        static_features=batch.static_features.to(self.device),
                    )
                    direct_probability = torch.sigmoid(
                        direct_head(output.decision_state).squeeze(1)).float()
            state = output.decision_state.float().cpu().numpy()
            ranker = self._acceptance_catboost_fit.assets[batch.asset].ranker_model
            if ranker is None:
                raise RealDiagnosticExecutorRefusal(
                    "teacher-isolation PairLogit ranker is unavailable")
            rank_probability = expit(np.asarray(ranker.predict(state), np.float64))
            model.cpu(); direct_head.cpu()
            return MappingProxyType({
                "raw_memory": _sha_bytes(output.raw_memory.float().cpu().numpy().tobytes()),
                "decision_state": _sha_bytes(state.tobytes()),
                "direct_probability": _sha_bytes(
                    direct_probability.cpu().numpy().tobytes()),
                "pairlogit_probability": _sha_bytes(rank_probability.tobytes()),
            })

        auxiliary_before = frozen_auxiliary_forward(auxiliary_original)
        auxiliary_after = frozen_auxiliary_forward(auxiliary_mutant)
        teacher_ids = tuple(sorted(
            candidate_id for candidate_id in full_ids
            if teacher[candidate_id].take_target))
        if auxiliary_before != auxiliary_after:
            raise RealDiagnosticExecutorRefusal(
                "non-FIT auxiliary horizon reached the frozen decision path")
        teacher_isolation = {
            "schema": "entry-v2-teacher-isolation-evidence-v1",
            "masked_candidate_id": masked.candidate_id,
            "masked_action_projection_unchanged": True,
            "masked_action_refit_unchanged": True,
            "auxiliary_candidate_id": auxiliary_original.candidate_ids[0],
            "auxiliary_coordinate": auxiliary_coordinate,
            "auxiliary_target_before_sha256": _sha_bytes(
                auxiliary_original.horizon_targets.numpy().tobytes()),
            "auxiliary_target_after_sha256": _sha_bytes(
                auxiliary_mutant.horizon_targets.numpy().tobytes()),
            "decision_surface_before": dict(auxiliary_before),
            "decision_surface_after": dict(auxiliary_after),
            "final_teacher_store_sha256": teacher.store_hash,
            "final_teacher_ids_sha256": _sha(teacher_ids),
            "post_fit_rows_physically_absent_sha256": firewall_sha256,
            "threshold_artifact_sha256": _sha(branch_evidence),
        }
        teacher_isolation["receipt_sha256"] = _sha(teacher_isolation)
        full_manifest_sha256 = str(full_roster["candidate_manifest_sha256"])
        artifact = _sha({"branches": branch_evidence,
                         "canonical_replay_adversary": replay_edge_receipt,
                         "competence_manifest": manifest.receipt_sha256,
                         "full_policy_roster": dict(full_roster),
                         "fit_only_firewall_sha256": firewall_sha256,
                         "fit_projection": policy_projection,
                         "visible_canary_projection": visible_projection,
                         "fit_refit_before": policy_refit_before,
                         "visible_refit_canary": policy_refit_canary,
                         "teacher_isolation": teacher_isolation})
        from .neural_sufficiency_source_manifest import \
            held_rehearsal_source_tree_sha256
        source_tree = held_rehearsal_source_tree_sha256()
        g7 = {"single_real_path": selected_branch,
                   "all_asset_in_sample": all(
                       branch_evidence[selected_branch]["stages"][stage]["status"]
                       == "ELIGIBLE" for stage in ("E1r", "E2r")),
                   "all_asset_disjoint_forward": all(
                       branch_evidence[selected_branch]["stages"]["E1r"]
                       ["forward_ok"].values()),
                   "candidate_ceiling_all_blocks":
                       set(ceiling_receipts) == set(ceiling_blocks),
                   "candidate_ceiling_receipts": ceiling_receipts,
                   "twins_counted": False}
        from .neural_sufficiency_stage_engine import execute_fit_only_rehearsal
        measured_e1r = self._produce_fit_only_e1r()
        measured_e2r = self._produce_fit_only_e2r(measured_e1r)
        matrix_winner = measured_e2r.get("winner")
        matrix_path = str(matrix_winner or measured_e2r["diagnostic_path"])
        measured_winner = measured_e2r["matrix"][matrix_path]
        # The same selected full architecture/head/objective is independently
        # initialized and trained at both walls.  The shallow 44-objective E1r
        # screen remains label evidence only and is never substituted here.
        selected_probe = str(measured_e2r["selected_objective"])
        selected_e1_full = measured_e2r.get("selected_e1_full_transition")
        if (not isinstance(selected_e1_full, Mapping)
                or selected_e1_full.get("arm") != matrix_path.split(":", 1)[0]
                or selected_e1_full.get("decision_kind")
                    != matrix_path.split(":", 1)[1]
                or selected_e1_full.get("selected_probe") != selected_probe
                or selected_e1_full.get("learner_objective")
                    != measured_e2r.get("selected_learner_objective")
                or selected_e1_full.get("learner_law_sha256")
                    != measured_winner.get("learner_law_sha256")
                or selected_e1_full.get("fit_wall")
                    != _rehearsal_bounds("E1r", "FIT")[1]
                or measured_winner.get("fit_wall")
                    != _rehearsal_bounds("E2r", "FIT")[1]
                or selected_e1_full.get("checkpoint_sha256")
                    == measured_winner.get("checkpoint_sha256")):
            raise RealDiagnosticExecutorRefusal(
                "selected E1r/E2r full learner identity differs")
        e1r_transition = dict(selected_e1_full["transition"])
        e1r_transition["probe_screen"] = measured_e1r
        e2r_transition = dict(measured_winner["e2r_transition"])
        e2r_transition["arm_head_matrix"] = measured_e2r
        selected_branch = matrix_path.split(":", 1)[1]
        g7["single_real_path"] = matrix_path
        g7["selected_arm"] = matrix_path.split(":", 1)[0]
        g7["selected_head"] = selected_branch
        g7["selected_objective"] = measured_e2r[
            "selected_learner_objective"]
        g7["learner_law_sha256"] = selected_e1_full["learner_law_sha256"]
        g7["e1r_checkpoint_sha256"] = selected_e1_full["checkpoint_sha256"]
        g7["e2r_checkpoint_sha256"] = measured_winner["checkpoint_sha256"]
        g7["e1r_fit_wall"] = selected_e1_full["fit_wall"]
        g7["e2r_fit_wall"] = measured_winner["fit_wall"]
        g7["same_full_learner_independent_fits"] = True
        g7["all_asset_in_sample"] = bool(
            matrix_winner is not None
            and e1r_transition["threshold_feasible"]
            and measured_winner["e2r_transition"]["threshold_feasible"])
        g7["all_asset_disjoint_forward"] = bool(
            matrix_winner is not None
            and e1r_transition["forward_feasible"]
            and measured_winner["e2r_transition"]["forward_feasible"])
        g7["minimum_oracle_capture"] = FIT_ONLY_MIN_ORACLE_CAPTURE
        goal_receipts = {}
        for stage_name, transition in (("E1r", e1r_transition),
                                       ("E2r", e2r_transition)):
            for role, field in (("THRESHOLD", "threshold_goal_recovery"),
                                ("FORWARD", "forward_goal_recovery")):
                rows_by_asset = transition.get(field)
                if (not isinstance(rows_by_asset, Mapping)
                        or set(rows_by_asset) != set(C.ASSETS)):
                    raise RealDiagnosticExecutorRefusal(
                        f"{stage_name} goal-recovery evidence is incomplete")
                for asset in C.ASSETS:
                    digest = rows_by_asset[asset].get("receipt_sha256")
                    if not _is_sha(digest):
                        raise RealDiagnosticExecutorRefusal(
                            f"{stage_name}/{role}/{asset} goal receipt is invalid")
                    goal_receipts[f"{stage_name}.{role}.{asset}"] = digest
        g7["goal_recovery_receipts"] = goal_receipts
        g7["goal_recovery_all_blocks"] = bool(
            g7["all_asset_in_sample"] and g7["all_asset_disjoint_forward"])
        self._fit_only_rehearsal_receipt = execute_fit_only_rehearsal(
            e1r=e1r_transition,
            e2r=e2r_transition,
            g7=g7, source_tree_sha256=source_tree)
        parts = tuple(tuple(ids[e1_masks[name]].tolist())
                      for name in ("FIT", "PLATT", "THRESHOLD"))
        return PolicyReplayResult(
            manifest.receipt_sha256, full_manifest_sha256, threshold_by_asset,
            mapper_positive_skill, mapper.calibrator.slope > 0,
            parity_measured, canonical_parity, equal_time_ties,
            occupancy_caps_cost_wall, full_denominator, mdd_exact,
            firewall_exact, bool(teacher_isolation["receipt_sha256"]),
            parts[0], parts[1], parts[2], artifact,
        )

    def _rehearsal_score_path(self, score: np.ndarray, *, ids: np.ndarray,
                              assets: np.ndarray, days: np.ndarray,
                              recipient: np.ndarray, chronology: str,
                              artifact_name: str):
        """Execute one real fit-only mapper→Platt→threshold→forward path."""
        from .atlas_probe_model import FrozenLogisticBindingMapper
        bindings, _ = self._binding_indexes()
        action = np.asarray([bindings[str(cid)].action_target for cid in ids], np.int8)
        if (chronology not in {"E1r", "E2r"} or not artifact_name
                or any(part in {"", ".", ".."}
                       for part in Path(artifact_name).parts)):
            raise RealDiagnosticExecutorRefusal("unknown fit-only rehearsal chronology")
        fit = _rehearsal_mask(days, chronology, "FIT")
        platt = _rehearsal_mask(days, chronology, "PLATT")
        threshold = _rehearsal_mask(days, chronology, "THRESHOLD")
        forward = _rehearsal_mask(days, chronology, "FORWARD")
        forward_lo, forward_hi = _rehearsal_bounds(chronology, "FORWARD")
        forward_days = tuple(sorted({s.trading_day for s in
            self.stage.corpus_stage.corpus.replay.expected_sessions
            if forward_lo <= s.trading_day <= forward_hi}))
        if any(not mask.any() for mask in (fit, platt, threshold, forward)):
            raise RealDiagnosticExecutorRefusal(f"{chronology} score path has an empty block")
        ceiling_surface = getattr(self, "_fit_only_ceiling_rows", None)
        if (not isinstance(ceiling_surface, Mapping)
                or set(ceiling_surface) != {
                    "E1r.THRESHOLD", "E1r.FORWARD",
                    "E2r.THRESHOLD", "E2r.FORWARD"}):
            raise RealDiagnosticExecutorRefusal(
                "fit-only candidate-ceiling economic surface is absent")
        features = _decision_binding(np.asarray(score, np.float64))
        supervised_fit = fit & recipient
        weights, weight_receipt = action_fit_weights(
            assets, days, action, recipient, supervised_fit)
        mapper = FrozenLogisticBindingMapper().fit(
            features, action, supervised_fit, ids, sample_weight=weights,
            weight_receipt_sha256=weight_receipt.receipt_sha256)
        supervised_platt = platt & recipient
        mapper.calibrate(features[supervised_platt], action[supervised_platt],
                         ids[supervised_platt], threshold_selection_ids=ids[threshold])
        probability, _ = mapper.predict(features)
        examples = {item.candidate_id: item for spec in
                    self.stage.corpus_stage.corpus.sessions for item in spec.examples}
        outcomes = self.stage.corpus_stage.corpus.replay.outcomes
        arrivals = tuple(ScoredArrival(
            examples[str(cid)], EntryScore(str(cid), str(asset),
                examples[str(cid)].decision_ts_ns, f"{chronology}-probe",
                float(p), float(p), 0.0, 0.0, float(p), 0.0, 0.0, False),
            outcomes[str(cid)]) for cid, asset, p in zip(ids, assets, probability))
        threshold_lo, threshold_hi = _rehearsal_bounds(chronology, "THRESHOLD")
        platt_lo, platt_hi = _rehearsal_bounds(chronology, "PLATT")
        threshold_days = tuple(sorted({s.trading_day for s in
            self.stage.corpus_stage.corpus.replay.expected_sessions
            if threshold_lo <= s.trading_day <= threshold_hi}))
        platt_days = tuple(sorted({s.trading_day for s in
            self.stage.corpus_stage.corpus.replay.expected_sessions
            if platt_lo <= s.trading_day <= platt_hi}))
        thresholds = {}; funnels = {}; parity = {}; all_feasible = True
        threshold_goal_recovery = {}
        for asset in C.ASSETS:
            local = np.flatnonzero(threshold & (assets == asset))
            sessions = self.stage.corpus_stage.corpus.replay.sessions_for(
                threshold_days, asset=asset)
            selected_arrivals = tuple(arrivals[i] for i in local)
            sweep = fast_threshold_sweep(selected_arrivals, probability[local], sessions)
            parity[asset] = assert_fast_sweep_parity(
                selected_arrivals, probability[local], sessions,
                sweep, samples=len(sweep.thresholds))
            feasible = np.asarray([threshold_feasibility(
                trades=int(sweep.trades[i]), usd_per_trade=float(sweep.usd_per_trade[i]),
                max_drawdown_usd=float(sweep.max_drawdown_usd[i]),
                days_with_trades=int(sweep.days_with_trades[i]),
                eligible_days=len(sweep.eligible_days)).feasible
                for i in range(len(sweep.thresholds))], bool)
            ceiling = ceiling_surface[f"{chronology}.THRESHOLD"][asset]
            oracle_total = float(ceiling["total_pnl_usd"])
            oracle_day = float(ceiling["usd_per_asset_day"])
            regime = capacity_regime_from_oracle(oracle_day)
            floor = required_floor_usd(regime)
            capture = sweep.total_pnl_usd / oracle_total
            goal_feasible = ((sweep.usd_per_asset_day >= floor)
                             & (capture >= FIT_ONLY_MIN_ORACLE_CAPTURE)
                             & (capture <= 1.0))
            if regime == "LOW":
                goal_feasible &= (
                    sweep.max_drawdown_usd < C.LOW_CAPACITY_MAX_DRAWDOWN_USD)
            feasible &= goal_feasible
            choices = np.flatnonzero(feasible)
            if not len(choices):
                thresholds[asset] = 1.0; all_feasible = False
                funnels[asset] = {"status": "NO_FEASIBLE_THRESHOLD",
                                  "sweep": sweep.receipt_sha256}
                best_capture = float(np.max(capture)) if len(capture) else float("-inf")
                failed = {
                    "schema": "entry-v2-fit-only-goal-recovery-failure-v1",
                    "eligible": False,
                    "capacity_regime": regime,
                    "required_floor_usd": floor,
                    "minimum_oracle_capture": FIT_ONLY_MIN_ORACLE_CAPTURE,
                    "maximum_observed_oracle_capture": best_capture,
                    "oracle_total_pnl_usd": oracle_total,
                    "oracle_usd_per_asset_day": oracle_day,
                    "reason": "NO_THRESHOLD_MEETS_FEASIBILITY_AND_GOAL_RECOVERY",
                }
                failed["receipt_sha256"] = _sha(failed)
                threshold_goal_recovery[asset] = failed
                continue
            chosen = max(choices, key=lambda i: (
                float(sweep.usd_per_asset_day[i]), float(sweep.usd_per_trade[i]),
                -float(sweep.max_drawdown_usd[i]), -float(sweep.drawdown_p90_usd[i]),
                float(sweep.thresholds[i]), int(sweep.trades[i])))
            thresholds[asset] = float(sweep.thresholds[chosen])
            funnels[asset] = {"status": "ELIGIBLE", "index": int(chosen),
                              "sweep": sweep.receipt_sha256}
            recovery = fit_only_goal_recovery(
                total_pnl_usd=float(sweep.total_pnl_usd[chosen]),
                usd_per_asset_day=float(sweep.usd_per_asset_day[chosen]),
                chronological_max_drawdown_usd=float(
                    sweep.max_drawdown_usd[chosen]),
                included_trading_days=len(sweep.eligible_days),
                oracle_total_pnl_usd=oracle_total,
                oracle_usd_per_asset_day=oracle_day,
            )
            if not recovery.eligible:
                raise RealDiagnosticExecutorRefusal(
                    "selected fit-only threshold does not reproduce its goal gate")
            threshold_goal_recovery[asset] = asdict(recovery)
        entered = tuple(ScoredArrival(row.example, replace(
            row.score, enter=row.score.take_probability >= thresholds[row.example.asset]),
            row.outcome) for row in arrivals)
        evaluation = replay((entered[i] for i in np.flatnonzero(forward)),
            expected_sessions=self.stage.corpus_stage.corpus.replay.sessions_for(forward_days))
        forward_by_asset = {row.asset: row for row in evaluation.by_asset}
        forward_feasibility = {}
        forward_goal_recovery = {}
        all_forward_feasible = True
        for asset in C.ASSETS:
            asset_days = tuple(
                row for row in evaluation.asset_day_results if row.asset == asset
            )
            measured = forward_by_asset.get(asset)
            if measured is None or len(asset_days) == 0:
                raise RealDiagnosticExecutorRefusal(
                    f"{chronology} forward replay lacks {asset} denominator"
                )
            feasibility = threshold_feasibility(
                trades=measured.trades,
                usd_per_trade=measured.usd_per_trade,
                max_drawdown_usd=measured.max_drawdown_usd,
                days_with_trades=sum(row.trades > 0 for row in asset_days),
                eligible_days=len(asset_days),
            )
            ceiling = ceiling_surface[f"{chronology}.FORWARD"][asset]
            recovery = fit_only_goal_recovery(
                total_pnl_usd=measured.total_pnl_usd,
                usd_per_asset_day=measured.usd_per_asset_day,
                chronological_max_drawdown_usd=measured.max_drawdown_usd,
                included_trading_days=len(asset_days),
                oracle_total_pnl_usd=float(ceiling["total_pnl_usd"]),
                oracle_usd_per_asset_day=float(ceiling["usd_per_asset_day"]),
            )
            forward_goal_recovery[asset] = asdict(recovery)
            forward_feasibility[asset] = {
                "feasible": feasibility.feasible and recovery.eligible,
                "threshold_feasibility": feasibility.feasible,
                "goal_recovery": recovery.eligible,
                "reasons": list((*feasibility.reasons, *recovery.reasons)),
                "receipt_sha256": feasibility.receipt_sha256,
                "goal_recovery_receipt_sha256": recovery.receipt_sha256,
            }
            all_forward_feasible &= feasibility.feasible and recovery.eligible
        receipt = _sha({"chronology": chronology, "fit_ids": ids[fit].tolist(),
                        "platt_ids": ids[platt].tolist(),
                        "threshold_ids": ids[threshold].tolist(),
                        "forward_ids": ids[forward].tolist(), "thresholds": thresholds,
                        "funnels": funnels, "weight": weight_receipt.receipt_sha256,
                        "minimum_oracle_capture": FIT_ONLY_MIN_ORACLE_CAPTURE,
                        "threshold_goal_recovery": threshold_goal_recovery,
                        "forward_feasibility": forward_feasibility,
                        "forward_goal_recovery": forward_goal_recovery,
                        "evaluation": [asdict(row) for row in evaluation.by_asset]})
        status = ("ELIGIBLE" if all_feasible and all_forward_feasible else
                  "NO_FEASIBLE_THRESHOLD" if not all_feasible else
                  "NO_FEASIBLE_FORWARD")
        detail = MappingProxyType({"status": status,
            "mapper": mapper.parameter_sha256,
            "calibrator": mapper.calibrator.parameter_sha256,
            "weight_receipt": weight_receipt.receipt_sha256,
            "thresholds": thresholds,
            "parity": parity,
            "minimum_oracle_capture": FIT_ONLY_MIN_ORACLE_CAPTURE,
            "threshold_goal_recovery": MappingProxyType(threshold_goal_recovery),
            "forward_feasibility": MappingProxyType(forward_feasibility),
            "forward_goal_recovery": MappingProxyType(forward_goal_recovery),
            "threshold_feasible": bool(all_feasible),
            "forward_feasible": bool(all_forward_feasible),
            "fit_days": tuple(sorted(set(map(int, days[fit])))),
            "platt_days": platt_days, "threshold_days": threshold_days,
            "forward_days": forward_days,
            "path_receipt_sha256": receipt})
        prefix = f"M8/paths/{artifact_name}"
        mapper_name = f"{prefix}/mapper.json"
        calibrator_name = f"{prefix}/calibrator.json"
        thresholds_name = f"{prefix}/thresholds.json"
        scores_name = f"{prefix}/scores.npz"
        replay_name = f"{prefix}/replay.json"
        mapper_payload = {
            "schema": "entry-v2-m8-binding-mapper-v1",
            "coef": np.asarray(mapper.coef_, np.float64).tolist(),
            "intercept": float(mapper.intercept_),
            "fit_ids_sha256": mapper.fit_ids_sha256,
            "weight_receipt_sha256": mapper.weight_receipt_sha256,
            "parameter_sha256": mapper.parameter_sha256,
        }
        calibrator_payload = {
            "schema": "entry-v2-m8-positive-platt-v1",
            "slope": float(mapper.calibrator.slope),
            "intercept": float(mapper.calibrator.intercept),
            "fit_ids_sha256": mapper.calibrator.fit_ids_sha256,
            "parameter_sha256": mapper.calibrator.parameter_sha256,
        }
        threshold_payload = {
            "schema": "entry-v2-m8-thresholds-v1",
            "chronology": chronology,
            "thresholds": thresholds,
            "funnels": funnels,
            "path_receipt_sha256": receipt,
        }
        replay_payload = {
            "schema": "entry-v2-m8-replay-v1",
            "chronology": chronology,
            "status": status,
            "evaluation": [asdict(row) for row in evaluation.by_asset],
            "asset_day_results": [asdict(row)
                                  for row in evaluation.asset_day_results],
            "threshold_goal_recovery": threshold_goal_recovery,
            "forward_goal_recovery": forward_goal_recovery,
            "path_receipt_sha256": receipt,
        }
        self._m8_payloads.update({
            mapper_name: _canonical_json_bytes(mapper_payload),
            calibrator_name: _canonical_json_bytes(calibrator_payload),
            thresholds_name: _canonical_json_bytes(threshold_payload),
            scores_name: _npz_bytes({
                "candidate_id": np.asarray(ids, str),
                "asset": np.asarray(assets, str),
                "day": np.asarray(days, np.int64),
                "recipient": np.asarray(recipient, np.bool_),
                "raw_score": np.asarray(score, np.float64),
                "probability": np.asarray(probability, np.float64),
            }),
            replay_name: _canonical_json_bytes(replay_payload),
        })
        self._m8_path_payloads[artifact_name] = [
            mapper_name, calibrator_name, thresholds_name, scores_name,
            replay_name,
        ]
        return evaluation, status, receipt, detail

    def _train_fit_only_selected_full_path(
        self, *, arm: str, decision_kind: str, chronology: str,
        selected_probe: str, selected_target: ProbeTarget,
        target_candidate_ids: Sequence[str], specs: Sequence[Any],
    ) -> Mapping[str, Any]:
        """Fit one identical full learner at a declared fit wall and replay it.

        E2r chooses the arm/head/objective.  This routine is then used only for
        the independently initialized E1r transition; its frozen law is the
        same base + selected-head law used by the five-arm E2r matrix.
        """
        if (arm not in CANONICAL_ARMS or decision_kind not in DECISIONS
                or chronology != "E1r"):
            raise RealDiagnosticExecutorRefusal(
                "selected full-learner transition identity differs")
        objective_spec = next((probe for probe in PROBE_REGISTRY
                               if probe.probe_id == selected_probe), None)
        if objective_spec is None:
            raise RealDiagnosticExecutorRefusal(
                "selected full-learner objective is unregistered")
        learner_objective = ("A0_CURRENT_GROUPING" if arm == "C0"
                             else selected_probe)
        all_specs = tuple(sorted((spec for spec in specs
                                  if spec.trading_day <= FIT_ONLY_MAXIMUM_D8),
                                 key=lambda spec: (spec.asset, spec.trading_day,
                                                   spec.session_id)))
        all_ids = tuple(cid for spec in all_specs for cid in spec.candidate_ids)
        if all_ids != tuple(target_candidate_ids):
            raise RealDiagnosticExecutorRefusal(
                "selected full-learner target/order differs")
        bindings, _ = self._binding_indexes()
        observed = {session.key: session for session in
                    self.stage.diagnostic_corpus.sessions}
        all_days = np.asarray([bindings[cid].trading_day for cid in all_ids], np.int64)
        all_assets = np.asarray([bindings[cid].asset for cid in all_ids], str)
        all_action = np.asarray([bindings[cid].action_target for cid in all_ids], np.int8)
        all_recipient = np.asarray(
            [bindings[cid].action_loss_mask for cid in all_ids], bool)
        fit_mask = _rehearsal_mask(all_days, chronology, "FIT")
        fit_days = sorted(set(map(int, all_days[fit_mask])))
        validation_days = set(fit_days[-max(1, int(np.ceil(.1 * len(fit_days)))):])
        train_mask = fit_mask & ~np.isin(all_days, tuple(validation_days))
        if (not train_mask.any() or not validation_days
                or set(all_action[train_mask & all_recipient]) != {0, 1}):
            raise RealDiagnosticExecutorRefusal(
                "selected full-learner chronology lacks train/validation support")
        train_days = set(fit_days) - validation_days
        normalizer = self._fit_rehearsal_input_normalizer(all_specs, train_days)

        # Six raw-USD coordinates receive TRAIN-only moments and are applied
        # unchanged to validation/Platt/threshold/forward rows.
        horizon_count = np.zeros(SELECTED_HORIZON_WIDTH, np.int64)
        horizon_total = np.zeros(SELECTED_HORIZON_WIDTH, np.float64)
        horizon_square = np.zeros(SELECTED_HORIZON_WIDTH, np.float64)
        for spec in all_specs:
            if spec.trading_day not in train_days:
                continue
            if (spec.selected_horizon_value is None
                    or spec.selected_horizon_valid is None
                    or spec.selected_horizon_schema_sha256
                        != SELECTED_HORIZON_SCHEMA_SHA256):
                raise RealDiagnosticExecutorRefusal(
                    "selected full-learner horizon carrier is absent")
            value = spec.selected_horizon_value.detach().cpu().numpy().astype(np.float64)
            valid = spec.selected_horizon_valid.detach().cpu().numpy().astype(bool)
            horizon_count += valid.sum(0)
            horizon_total += np.where(valid, value, 0.0).sum(0)
            horizon_square += np.where(valid, value * value, 0.0).sum(0)
        if np.any(horizon_count < 2):
            raise RealDiagnosticExecutorRefusal(
                "selected full-learner horizon moments lack support")
        horizon_location = horizon_total / horizon_count
        horizon_scale = np.sqrt(np.maximum(
            horizon_square / horizon_count - horizon_location ** 2, 0.0))
        if np.any(horizon_scale <= 0) or np.any(~np.isfinite(horizon_scale)):
            raise RealDiagnosticExecutorRefusal(
                "selected full-learner horizon moments are degenerate")

        def build_batch(spec: Any) -> _CandidateBatch:
            batch = self._build_full_policy_batch(
                spec, tuple(range(len(spec.candidate_ids))),
                observed[(spec.asset, spec.trading_day)], bindings,
                normalizer=normalizer)
            raw = batch.horizon_targets.numpy().astype(np.float64)
            valid = batch.horizon_valid.numpy().astype(bool)
            normalized = ((raw - horizon_location) / horizon_scale).astype(np.float32)
            normalized[~valid] = 0.0
            return replace(batch, horizon_targets=torch.from_numpy(normalized))

        labels = tuple(label for spec in all_specs for _, label in
                       self.stage.corpus_stage.corpus.teacher.join_training(spec.examples))
        top_target = np.asarray([label.top3 for label in labels], np.int8)
        wall_target = np.asarray([label.wall_hit for label in labels], np.int8)
        action_weight, action_receipt = action_fit_weights(
            all_assets, all_days, all_action, all_recipient, train_mask)
        base_weight, base_receipt = asset_day_fit_weights(
            all_assets, all_days, np.zeros(len(all_ids)), np.ones(len(all_ids), bool),
            train_mask, apply_class_weight=False)
        top_weight, top_receipt = asset_day_fit_weights(
            all_assets, all_days, top_target, np.ones(len(all_ids), bool),
            train_mask, apply_class_weight=True)
        wall_weight, wall_receipt = asset_day_fit_weights(
            all_assets, all_days, wall_target, np.ones(len(all_ids), bool),
            train_mask, apply_class_weight=True)
        position = {cid: index for index, cid in enumerate(all_ids)}
        all_phases = np.asarray([example.phase for spec in all_specs
                                 for example in spec.examples], str)
        all_decisions = np.asarray(
            [bindings[cid].decision_ts_ns for cid in all_ids], np.int64)
        shared_pair_manifest = canonical_phase_pair_manifest(
            np.asarray(all_ids, str), all_assets, all_days, all_phases,
            all_decisions, all_action, all_recipient, train_mask)
        shared_pairs_by_asset: dict[str, dict[tuple[str, str], float]] = {
            asset: {} for asset in C.ASSETS}
        for pair, weight in zip(shared_pair_manifest.candidate_id_pairs,
                                shared_pair_manifest.pair_weights):
            owner = str(all_assets[position[pair[0]]])
            shared_pairs_by_asset[owner][tuple(pair)] = float(weight)
        target_position = {cid: index for index, cid in
                           enumerate(target_candidate_ids)}
        train_by_day: dict[tuple[str, int], list[Any]] = {}
        validation_by_day: dict[tuple[str, int], list[Any]] = {}
        fit_lo, fit_hi = _rehearsal_bounds(chronology, "FIT")
        for spec in all_specs:
            if fit_lo <= spec.trading_day <= fit_hi:
                destination = (validation_by_day if spec.trading_day in validation_days
                               else train_by_day)
                destination.setdefault((spec.asset, spec.trading_day), []).append(spec)
        if not train_by_day or not validation_by_day:
            raise RealDiagnosticExecutorRefusal(
                "selected full-learner asset-day partition is empty")

        model = self._new_model_registry()[arm].to(self.device)
        initial_sha256 = _sha_bytes(module_state_bytes(model))
        torch.manual_seed(20260816)
        objective_head = torch.nn.Linear(512, PADDED_OUTPUT_WIDTH).to(self.device)
        torch.nn.init.xavier_uniform_(objective_head.weight)
        torch.nn.init.zeros_(objective_head.bias)
        if arm == "C0":
            torch.nn.init.zeros_(objective_head.weight)
            torch.nn.init.zeros_(objective_head.bias)
            objective_head.requires_grad_(False)
        decoder = LastRowReconstructionProbe(
            len(self.schema.continuous_fields), CATEGORY_SIZES).to(self.device)

        def supplied_weights(batch: _CandidateBatch) -> Mapping[str, torch.Tensor]:
            rows = np.asarray([position[cid] for cid in batch.candidate_ids], np.int64)
            return {"action": torch.from_numpy(action_weight[rows]),
                    "base": torch.from_numpy(base_weight[rows]),
                    "top3": torch.from_numpy(top_weight[rows]),
                    "wall": torch.from_numpy(wall_weight[rows])}

        def day_pair_loss(logits: Sequence[torch.Tensor], ids: Sequence[str],
                          phases: Sequence[str], decisions: Sequence[int],
                          actions: Sequence[int], recipients: Sequence[bool],
                          asset: str, day: int, *, weighted: bool) -> tuple[torch.Tensor, int, str]:
            manifest = canonical_phase_pair_manifest(
                np.asarray(ids, str), np.full(len(ids), asset),
                np.full(len(ids), day, np.int64), np.asarray(phases, str),
                np.asarray(decisions, np.int64), np.asarray(actions, np.int8),
                np.asarray(recipients, bool), np.ones(len(ids), bool))
            if not len(manifest.pairs):
                return torch.cat(tuple(logits)).sum() * 0.0, 0, manifest.receipt_sha256
            joined = torch.cat(tuple(logits)); pairs = np.asarray(manifest.pairs, np.int64)
            values = torch.nn.functional.softplus(
                -(joined[pairs[:, 0]] - joined[pairs[:, 1]]))
            if weighted:
                values = values * torch.from_numpy(np.asarray(
                    manifest.pair_weights, np.float32)).to(self.device)
                return values.sum(), len(pairs), manifest.receipt_sha256
            return values.mean(), len(pairs), manifest.receipt_sha256

        trace: list[Mapping[str, Any]] = []
        best_base = None; best_base_loss = np.inf; stale = 0
        optimizer = torch.optim.Adam(
            [*model.parameters(), *decoder.parameters()], lr=3e-4)
        for epoch in range(12):
            model.train(); decoder.train(); epoch_losses = []; pair_count = 0
            gradient_norm = 0.0
            for (asset, day), day_specs in sorted(train_by_day.items()):
                optimizer.zero_grad(set_to_none=True); total = None
                logits = []; ids = []; phases = []; decisions = []; actions = []; recipients = []
                for spec in day_specs:
                    batch = build_batch(spec)
                    with self._held_autocast():
                        output = model(
                            event_continuous=batch.continuous.to(self.device),
                            event_categorical=batch.categorical.to(self.device),
                            receive_clock_ns=batch.clock.to(self.device),
                            candidate_cutoffs=batch.cutoffs.to(self.device),
                            candidate_decision_ts_ns=batch.decisions.to(self.device),
                            candidate_features=batch.candidate_features.to(self.device),
                            context_values=batch.context_values.to(self.device),
                            context_type_ids=batch.context_type_ids.to(self.device),
                            context_valid=batch.context_valid.to(self.device),
                            asset_idx=C.ASSET_INDEX[asset], static_features=None)
                        oracle_loss, _ = _actual_multitask_loss(
                            output, batch, supplied_weights(batch))
                        reconstruction, _, _ = _field_reconstruction_loss(
                            decoder, output.raw_memory, batch,
                            supplied_weights(batch)["base"])
                        value = oracle_loss + reconstruction
                    total = value if total is None else total + value
                    logits.append(output.action_logit.float()); ids.extend(batch.candidate_ids)
                    phases.extend(str(item.phase) for item in spec.examples)
                    decisions.extend(int(bindings[cid].decision_ts_ns)
                                     for cid in batch.candidate_ids)
                    actions.extend(int(bindings[cid].action_target)
                                   for cid in batch.candidate_ids)
                    recipients.extend(bool(bindings[cid].action_loss_mask)
                                      for cid in batch.candidate_ids)
                pair, count, _ = day_pair_loss(
                    logits, ids, phases, decisions, actions, recipients,
                    asset, day, weighted=True)
                assert total is not None
                total = total + pair; total.backward(); optimizer.step()
                pair_count += count; epoch_losses.append(float(total.detach()))
                gradient_norm += float(sum(torch.linalg.vector_norm(p.grad.detach())
                    for p in [*model.parameters(), *decoder.parameters()]
                    if p.grad is not None))
            validation = self._fit_only_selected_validation(
                model, objective_head, decoder, arm, objective_spec,
                selected_target, target_position, validation_by_day,
                build_batch, bindings, stage="BASE")
            checkpoint = _sha_bytes(module_state_bytes(model))
            trace.append({"stage": "BASE", "epoch": epoch,
                          "train_loss": float(np.mean(epoch_losses)),
                          "validation_loss": validation,
                          "gradient_norm": gradient_norm,
                          "phase_pair_count": pair_count,
                          "checkpoint_sha256": checkpoint})
            if validation < best_base_loss * .999:
                best_base_loss = validation; stale = 0
                best_base = (copy.deepcopy(model.state_dict()),
                             copy.deepcopy(decoder.state_dict()), checkpoint)
            else:
                stale += 1
            if epoch >= 1 and stale >= 3:
                break
        if best_base is None or len(trace) < 2:
            raise RealDiagnosticExecutorRefusal(
                "selected full-learner base stage did not converge")
        model.load_state_dict(best_base[0], strict=True)
        decoder.load_state_dict(best_base[1], strict=True)
        pointwise_sha256 = _sha_bytes(module_state_bytes(model))
        model.encoder.requires_grad_(False)
        parameters = list(model.head.parameters())
        if arm != "C0":
            parameters += list(objective_head.parameters())
        optimizer = torch.optim.Adam(parameters, lr=3e-4)
        best = None; best_loss = np.inf; stale = 0
        for epoch in range(6):
            model.train(); objective_head.train(); epoch_losses = []; pair_count = 0
            gradient_norm = 0.0
            for (asset, day), day_specs in sorted(train_by_day.items()):
                optimizer.zero_grad(set_to_none=True); total = None
                logits = []; ids = []; phases = []; decisions = []; actions = []; recipients = []
                for spec in day_specs:
                    batch = build_batch(spec)
                    with self._held_autocast():
                        output = model(
                            event_continuous=batch.continuous.to(self.device),
                            event_categorical=batch.categorical.to(self.device),
                            receive_clock_ns=batch.clock.to(self.device),
                            candidate_cutoffs=batch.cutoffs.to(self.device),
                            candidate_decision_ts_ns=batch.decisions.to(self.device),
                            candidate_features=batch.candidate_features.to(self.device),
                            context_values=batch.context_values.to(self.device),
                            context_type_ids=batch.context_type_ids.to(self.device),
                            context_valid=batch.context_valid.to(self.device),
                            asset_idx=C.ASSET_INDEX[asset],
                            static_features=(batch.static_features.to(self.device)
                                if arm in ("L1", "M1") else None))
                        value, _ = _actual_multitask_loss(
                            output, batch, supplied_weights(batch))
                        if arm != "C0":
                            rows = np.asarray([target_position[cid]
                                               for cid in batch.candidate_ids], np.int64)
                            value = value + loss_for_probe(
                                objective_spec,
                                objective_head(output.decision_state.float()),
                                _target_take(selected_target, rows))
                    total = value if total is None else total + value
                    logits.append(output.action_logit.float()); ids.extend(batch.candidate_ids)
                    phases.extend(str(item.phase) for item in spec.examples)
                    decisions.extend(int(bindings[cid].decision_ts_ns)
                                     for cid in batch.candidate_ids)
                    actions.extend(int(bindings[cid].action_target)
                                   for cid in batch.candidate_ids)
                    recipients.extend(bool(bindings[cid].action_loss_mask)
                                      for cid in batch.candidate_ids)
                pair, count, _ = day_pair_loss(
                    logits, ids, phases, decisions, actions, recipients,
                    asset, day, weighted=True)
                assert total is not None
                total = total + pair; total.backward(); optimizer.step()
                pair_count += count; epoch_losses.append(float(total.detach()))
                gradient_norm += float(sum(torch.linalg.vector_norm(p.grad.detach())
                    for p in parameters if p.grad is not None))
            validation = self._fit_only_selected_validation(
                model, objective_head, decoder, arm, objective_spec,
                selected_target, target_position, validation_by_day,
                build_batch, bindings, stage="SELECTED_HEAD")
            checkpoint = _full_learner_checkpoint_sha256(model, objective_head)
            trace.append({"stage": "SELECTED_HEAD", "epoch": epoch,
                          "train_loss": float(np.mean(epoch_losses)),
                          "validation_loss": validation,
                          "gradient_norm": gradient_norm,
                          "phase_pair_count": pair_count,
                          "checkpoint_sha256": checkpoint})
            if validation < best_loss * .999:
                best_loss = validation; stale = 0
                best = (copy.deepcopy(model.state_dict()),
                        copy.deepcopy(objective_head.state_dict()), checkpoint)
            else:
                stale += 1
            if epoch >= 1 and stale >= 2:
                break
        if best is None:
            raise RealDiagnosticExecutorRefusal(
                "selected full-learner objective stage did not converge")
        model.load_state_dict(best[0], strict=True)
        objective_head.load_state_dict(best[1], strict=True)
        final_checkpoint = _full_learner_checkpoint_sha256(
            model, objective_head)
        if final_checkpoint != best[2]:
            raise RealDiagnosticExecutorRefusal(
                "selected full-learner best reload differs")

        # Score the unchanged full learner across all fit-only blocks.
        states = []; direct = []; phases = []
        model.eval(); objective_head.eval()
        canary_batch = None; canary_output = None
        for spec in all_specs:
            batch = build_batch(spec)
            with torch.no_grad(), self._held_autocast():
                output = model(
                    event_continuous=batch.continuous.to(self.device),
                    event_categorical=batch.categorical.to(self.device),
                    receive_clock_ns=batch.clock.to(self.device),
                    candidate_cutoffs=batch.cutoffs.to(self.device),
                    candidate_decision_ts_ns=batch.decisions.to(self.device),
                    candidate_features=batch.candidate_features.to(self.device),
                    context_values=batch.context_values.to(self.device),
                    context_type_ids=batch.context_type_ids.to(self.device),
                    context_valid=batch.context_valid.to(self.device),
                    asset_idx=C.ASSET_INDEX[spec.asset],
                    static_features=(batch.static_features.to(self.device)
                        if arm in ("L1", "M1") else None))
            if canary_batch is None:
                canary_batch, canary_output = batch, output
            states.append(output.decision_state.float().cpu().numpy())
            direct.append(torch.sigmoid(output.action_logit.float()).cpu().numpy())
            phases.extend(str(item.phase) for item in spec.examples)
        if canary_batch is None or canary_output is None:
            raise RealDiagnosticExecutorRefusal(
                "selected full-learner inference canary population is empty")
        representation = np.ascontiguousarray(np.concatenate(states), np.float32)
        probability = np.ascontiguousarray(np.concatenate(direct), np.float64)
        rows = FrozenRepresentationRows(
            representation, np.asarray(all_ids, str), all_assets, all_days,
            np.asarray([bindings[cid].decision_ts_ns for cid in all_ids], np.int64),
            all_action, all_recipient, np.asarray(phases, str),
            np.where(np.isin(all_days, tuple(validation_days)),
                     "VALIDATION", chronology),
            f"REHEARSAL_{chronology[:2]}",
            group_semantics="PHASE")
        rows.validate(); catboost_names: list[str] = []
        if decision_kind == "catboost":
            tree = fit_diagnostic_catboost(
                rows, expected_representation_sha256=rows.representation_sha256,
                minimum_pair_groups_per_asset=1)
            for asset in C.ASSETS:
                pair_manifest = tree.assets[asset].pair_manifest
                selected_ids = np.asarray(all_ids, str)[pair_manifest.indices]
                actual_pairs = {
                    (str(selected_ids[positive]), str(selected_ids[negative])):
                        float(weight)
                    for (positive, negative), weight in zip(
                        pair_manifest.pairs, pair_manifest.pair_weights)}
                if actual_pairs != shared_pairs_by_asset[asset]:
                    raise RealDiagnosticExecutorRefusal(
                        f"selected E1r {asset} neural/CatBoost pairs differ")
            probability = expit(np.asarray(tree.rank_score, np.float64))
            catboost_canary: dict[str, list[float]] = {}
            catboost_model_hashes: dict[str, str] = {}
            canary_state = np.ascontiguousarray(
                canary_output.decision_state.float().cpu().numpy(), np.float32)
            with tempfile.TemporaryDirectory(prefix="entry-v2-m8-g7-") as directory:
                for asset in C.ASSETS:
                    ranker = tree.assets[asset].ranker_model
                    if ranker is None:
                        raise RealDiagnosticExecutorRefusal(
                            f"selected full-learner {asset} PairLogit is absent")
                    path = Path(directory) / f"{asset}.cbm"
                    ranker.save_model(str(path), format="cbm")
                    name = (f"M8/G7/{chronology}/{arm}/{decision_kind}/"
                            f"{asset}-pairlogit.cbm")
                    raw_model = path.read_bytes()
                    self._m8_payloads[name] = raw_model
                    catboost_names.append(name)
                    catboost_model_hashes[name] = _sha_bytes(raw_model)
                    catboost_canary[f"{asset}-pairlogit"] = np.asarray(
                        ranker.predict(canary_state), np.float64).tolist()
            config_name = (f"M8/G7/{chronology}/{arm}/{decision_kind}/"
                           "catboost/config.json")
            self._m8_payloads[config_name] = _canonical_json_bytes({
                "schema": "entry-v2-m8-selected-catboost-model-set-v1",
                "chronology": chronology,
                "arm": arm,
                "fit_receipt_sha256": tree.receipt_sha256,
                "representation_sha256": rows.representation_sha256,
                "pair_manifest_sha256": {
                    asset: tree.assets[asset].pair_manifest.receipt_sha256
                    for asset in C.ASSETS},
                "models": catboost_model_hashes,
                "canary_state_sha256": _sha_bytes(canary_state.tobytes()),
                "canary_predictions": catboost_canary,
            })
            catboost_names.append(config_name)
        evaluation, status, path_receipt, transition = self._rehearsal_score_path(
            probability, ids=np.asarray(all_ids), assets=all_assets, days=all_days,
            recipient=all_recipient, chronology=chronology,
            artifact_name=f"G7/{chronology}/{arm}/{decision_kind}")

        prefix = f"M8/G7/{chronology}/{arm}/{decision_kind}"
        model_name = f"{prefix}/final.safetensors"
        objective_name = f"{prefix}/objective-head.safetensors"
        input_name = f"{prefix}/canary-input.npz"
        output_name = f"{prefix}/canary-output.npz"
        training_name = f"{prefix}/training.json"
        self._m8_payloads[model_name] = _safetensors_bytes(model)
        self._m8_payloads[objective_name] = _safetensors_bytes(objective_head)
        self._m8_payloads[input_name] = _npz_bytes({
            "continuous": canary_batch.continuous.numpy(),
            "categorical": canary_batch.categorical.numpy(),
            "clock": canary_batch.clock.numpy(), "cutoffs": canary_batch.cutoffs.numpy(),
            "decisions": canary_batch.decisions.numpy(),
            "candidate_features": canary_batch.candidate_features.numpy(),
            "context_values": canary_batch.context_values.numpy(),
            "context_type_ids": canary_batch.context_type_ids.numpy(),
            "context_valid": canary_batch.context_valid.numpy(),
            "static_features": canary_batch.static_features.numpy(),
            "asset_index": np.asarray([C.ASSET_INDEX[canary_batch.asset]], np.int64),
        })
        selected_canary_arrays = dict(_output_canary_arrays(canary_output))
        with torch.no_grad():
            selected_canary_arrays["objective_output"] = np.ascontiguousarray(
                objective_head(
                    canary_output.decision_state.float()).float().cpu().numpy())
        self._m8_payloads[output_name] = _npz_bytes(selected_canary_arrays)
        training = {"schema": "entry-v2-fit-only-selected-full-training-v1",
            "chronology": chronology, "fit_wall": fit_hi, "arm": arm,
            "decision_kind": decision_kind, "selected_probe": selected_probe,
            "learner_objective": learner_objective,
            "learner_law_sha256": _fit_only_full_learner_law_sha256(),
            "initial_checkpoint_sha256": initial_sha256,
            "pointwise_checkpoint_sha256": pointwise_sha256,
            "final_checkpoint_sha256": final_checkpoint,
            "action_weight_receipt_sha256": action_receipt.receipt_sha256,
            "base_weight_receipt_sha256": base_receipt.receipt_sha256,
            "top3_weight_receipt_sha256": top_receipt.receipt_sha256,
            "wall_weight_receipt_sha256": wall_receipt.receipt_sha256,
            "phase_pair_manifest_sha256":
                shared_pair_manifest.receipt_sha256,
            "input_normalizer_sha256": normalizer["receipt_sha256"],
            "trace": trace}
        training["receipt_sha256"] = _sha(training)
        self._m8_payloads[training_name] = _canonical_json_bytes(training)
        artifacts = [model_name, objective_name, input_name, output_name,
                     training_name, *catboost_names,
                     *self._m8_path_payloads[f"G7/{chronology}/{arm}/{decision_kind}"]]
        self._m8_selected_transition_payloads.extend(artifacts)
        model.cpu(); objective_head.cpu(); decoder.cpu()
        return MappingProxyType({
            "transition": dict(transition), "status": status,
            "path_receipt_sha256": path_receipt,
            "checkpoint_sha256": final_checkpoint,
            "objective_head_sha256": _sha_bytes(module_state_bytes(objective_head)),
            "learner_law_sha256": _fit_only_full_learner_law_sha256(),
            "fit_wall": fit_hi, "arm": arm, "decision_kind": decision_kind,
            "selected_probe": selected_probe,
            "learner_objective": learner_objective,
            "training_receipt_sha256":
                training["receipt_sha256"],
        })

    def _fit_only_selected_validation(
        self, model: Any, objective_head: torch.nn.Module,
        decoder: LastRowReconstructionProbe, arm: str, objective_spec: ProbeSpec,
        selected_target: ProbeTarget, target_position: Mapping[str, int],
        validation_by_day: Mapping[tuple[str, int], Sequence[Any]],
        build_batch: Any, bindings: Mapping[str, Any], *, stage: str,
    ) -> float:
        """Unweighted validation shared by the full selected E1r learner."""
        values = []; pair_count = 0
        model.eval(); objective_head.eval(); decoder.eval()
        with torch.no_grad():
            for (asset, _day), specs in sorted(validation_by_day.items()):
                logits = []; ids = []; phases = []; decisions = []; actions = []; recipients = []
                row_losses = []
                for spec in specs:
                    batch = build_batch(spec)
                    with self._held_autocast():
                        output = model(
                            event_continuous=batch.continuous.to(self.device),
                            event_categorical=batch.categorical.to(self.device),
                            receive_clock_ns=batch.clock.to(self.device),
                            candidate_cutoffs=batch.cutoffs.to(self.device),
                            candidate_decision_ts_ns=batch.decisions.to(self.device),
                            candidate_features=batch.candidate_features.to(self.device),
                            context_values=batch.context_values.to(self.device),
                            context_type_ids=batch.context_type_ids.to(self.device),
                            context_valid=batch.context_valid.to(self.device),
                            asset_idx=C.ASSET_INDEX[asset],
                            static_features=(batch.static_features.to(self.device)
                                if stage == "SELECTED_HEAD" and arm in ("L1", "M1")
                                else None))
                        value, _ = _actual_multitask_loss(output, batch)
                        if stage == "BASE":
                            reconstruction, _, _ = _field_reconstruction_loss(
                                decoder, output.raw_memory, batch)
                            value = value + reconstruction
                        elif arm != "C0":
                            rows = np.asarray([target_position[cid]
                                               for cid in batch.candidate_ids], np.int64)
                            value = value + loss_for_probe(
                                objective_spec,
                                objective_head(output.decision_state.float()),
                                _target_take(selected_target, rows),
                                use_fit_weight=False)
                    row_losses.append(value); logits.append(output.action_logit.float())
                    ids.extend(batch.candidate_ids)
                    phases.extend(str(item.phase) for item in spec.examples)
                    decisions.extend(int(bindings[cid].decision_ts_ns)
                                     for cid in batch.candidate_ids)
                    actions.extend(int(bindings[cid].action_target)
                                   for cid in batch.candidate_ids)
                    recipients.extend(bool(bindings[cid].action_loss_mask)
                                      for cid in batch.candidate_ids)
                pair = canonical_phase_pair_manifest(
                    np.asarray(ids, str), np.full(len(ids), asset),
                    np.full(len(ids), specs[0].trading_day, np.int64),
                    np.asarray(phases, str), np.asarray(decisions, np.int64),
                    np.asarray(actions, np.int8), np.asarray(recipients, bool),
                    np.ones(len(ids), bool))
                value = torch.stack(row_losses).mean()
                if len(pair.pairs):
                    joined = torch.cat(logits); pairs = np.asarray(pair.pairs, np.int64)
                    value = value + torch.nn.functional.softplus(
                        -(joined[pairs[:, 0]] - joined[pairs[:, 1]])).mean()
                    pair_count += len(pair.pairs)
                values.append(float(value))
        if not values or pair_count <= 0 or not np.all(np.isfinite(values)):
            raise RealDiagnosticExecutorRefusal(
                "selected full-learner validation is incomplete")
        return float(np.mean(values))

    def _produce_fit_only_e1r(self) -> Mapping[str, Any]:
        """Run the real 2+88 rehearsal atlas on the full pre-October population."""
        e1_fit_end = _rehearsal_bounds("E1r", "FIT")[1]
        specs, ids_tuple, rows, targets, _contexts, pretexts, fit_idx = \
            self._build_held_probe_plane(maximum_d8=20210930,
                                         pretext_fit_end=e1_fit_end)
        self._fit_only_e1_targets = MappingProxyType(dict(targets))
        ids = np.asarray(ids_tuple, str); days = np.asarray(rows.day, np.int64)
        assets = np.asarray(rows.asset, str)
        bindings, _ = self._binding_indexes()
        recipient = np.asarray([bindings[cid].action_loss_mask for cid in ids], bool)
        split = np.full(len(days), "E2R", dtype="<U16")
        for role in ("FIT", "PLATT", "THRESHOLD", "FORWARD"):
            split[_rehearsal_mask(days, "E1r", role)] = role
        permutation = stage_global_recipient_fixed_permutation(
            split, assets, days, recipient, seed=20260816)
        shared = SharedProbePlane.build(rows, fit_idx, stage_id="E1R")
        shared_name = "M8/E1r/shared-probe-plane.npz"
        canary_rows = np.arange(min(8, len(shared.normalized)), dtype=np.int64)
        self._m8_payloads[shared_name] = _npz_bytes({
            "location": shared.normalizer.location,
            "scale": shared.normalizer.scale,
            "constant_zero_mask": shared.normalizer.constant_zero_mask,
            "canonical_fit_indices": shared.canonical_fit_indices,
            "train_indices": shared.train_indices,
            "validation_indices": shared.validation_indices,
            "canary_rows": canary_rows,
            "canary_normalized": shared.normalized[canary_rows],
        })
        self._m8_pretext_payloads = [shared_name]
        for pretext in pretexts:
            checkpoint = pretext.checkpoint
            if checkpoint is None:
                raise RealDiagnosticExecutorRefusal(
                    "E1r pretext lacks its numerical checkpoint")
            name = f"M8/E1r/pretext/{checkpoint.objective_id}.checkpoint.npz"
            arrays = {f"state/{key}": value
                      for key, value in checkpoint.model_state.items()}
            arrays.update({
                "location": checkpoint.location,
                "scale": checkpoint.scale,
                "constant_zero_mask": checkpoint.constant_zero_mask,
                "category_sizes": np.asarray(checkpoint.category_sizes, np.int64),
                "metadata": np.asarray([
                    checkpoint.stage_id, checkpoint.objective_id,
                    str(checkpoint.continuous_width),
                    checkpoint.input_normalizer_sha256,
                    checkpoint.initialization_sha256,
                    checkpoint.checkpoint_sha256,
                ]),
            })
            self._m8_payloads[name] = _npz_bytes(arrays)
            self._m8_pretext_payloads.append(name)
        torch.manual_seed(20260816); initialization = AtlasProbeNet()
        forward_lo, forward_hi = _rehearsal_bounds("E1r", "FORWARD")
        calendar = tuple(sorted({(s.asset, s.trading_day) for s in
            self.stage.corpus_stage.corpus.replay.expected_sessions
            if forward_lo <= s.trading_day <= forward_hi}))
        p_values = {}; families = {}; fingerprints = {}; ledger = {}; screens = {}
        optimizer_fits = 2
        for probe in PROBE_REGISTRY:
            target = targets[probe.probe_id]
            support, additional = _e1_fit_support_inputs(probe, target, rows, fit_idx)
            decisions = tuple(item.measure() for item in (support, *additional))
            if (target.state != CellAvailability.MATERIALIZED
                    or not all(item.available for item in decisions)):
                status = (target.state.value
                          if target.state != CellAvailability.MATERIALIZED
                          else CellAvailability.UNAVAILABLE_LOW_SUPPORT.value)
                ledger[probe.probe_id] = {"status": status,
                    "support": [item.receipt_sha256 for item in decisions]}
                twin_id = shuffled_probe_for(
                    probe, available=self.stage.diagnostic_corpus.sessions[0]
                    .atlas.shuffled_probes).probe_id
                self._m8_objective_payloads.setdefault(probe.probe_id, [])
                self._m8_objective_payloads.setdefault(twin_id, [])
                fingerprints[probe.probe_id] = _probe_fingerprint(
                    target, np.isin(np.arange(len(ids)), fit_idx), recipient)
                continue
            twin_target = permute_probe_target_recipient_fixed(target, permutation)
            twin_spec = shuffled_probe_for(
                probe, available=self.stage.diagnostic_corpus.sessions[0].atlas.shuffled_probes)
            twin_target = replace(twin_target, probe_id=twin_spec.probe_id,
                schema_sha256=probe_target_schema_sha256(
                    twin_spec.probe_id, twin_target.output_width,
                    twin_target.output_layout, twin_target.direction,
                    twin_target.transform_provenance_sha256,
                    twin_target.prediction_width, twin_target.prediction_layout))
            real = fit_probe(probe, rows, target, fit_indices=fit_idx,
                initialization=initialization, stage_id="E1R", shared_plane=shared,
                device=self.device)
            twin = fit_probe(twin_spec, rows, twin_target, fit_indices=fit_idx,
                initialization=initialization, stage_id="E1R", shared_plane=shared,
                device=self.device)
            optimizer_fits += 2
            normalized = torch.from_numpy(shared.normalized)
            twin_normalized = normalized
            with torch.no_grad():
                real_output = real.model(normalized).cpu()
                twin_output = twin.model(twin_normalized).cpu()
                real_score = action_score_for_probe(
                    probe, real_output, target).numpy()
                twin_score = action_score_for_probe(
                    twin_spec, twin_output, twin_target).numpy()
            real_model_name = (
                f"M8/E1r/objectives/{probe.probe_id}/real.safetensors")
            twin_model_name = (
                f"M8/E1r/objectives/{probe.probe_id}/twin.safetensors")
            canary_name = f"M8/E1r/objectives/{probe.probe_id}/canary.npz"
            self._m8_payloads[real_model_name] = _safetensors_bytes(real.model)
            self._m8_payloads[twin_model_name] = _safetensors_bytes(twin.model)
            self._m8_payloads[canary_name] = _npz_bytes({
                "rows": canary_rows,
                "real_output": real_output[canary_rows].numpy(),
                "twin_output": twin_output[canary_rows].numpy(),
                "real_score": np.asarray(real_score[canary_rows], np.float64),
                "twin_score": np.asarray(twin_score[canary_rows], np.float64),
            })
            real_eval, real_status, real_path, real_detail = self._rehearsal_score_path(
                real_score, ids=ids, assets=assets, days=days,
                recipient=recipient, chronology="E1r",
                artifact_name=f"E1r/objectives/{probe.probe_id}/real")
            twin_eval, twin_status, twin_path, twin_detail = self._rehearsal_score_path(
                twin_score, ids=ids, assets=assets, days=days,
                recipient=recipient, chronology="E1r",
                artifact_name=f"E1r/objectives/{probe.probe_id}/twin")
            real_day = {(row.asset, row.trading_day): row.pnl_usd
                        for row in real_eval.asset_day_results}
            twin_day = {(row.asset, row.trading_day): row.pnl_usd
                        for row in twin_eval.asset_day_results}
            records = tuple(PairedObservationRecord(
                f"E1r:{asset}:{day}", asset, str(day), True,
                target.schema_sha256, twin_target.schema_sha256,
                float(real_day.get((asset, day), 0.0)),
                float(twin_day.get((asset, day), 0.0))) for asset, day in calendar)
            test = paired_day_cluster_records(records)
            fingerprints[probe.probe_id] = _probe_fingerprint(
                target, np.isin(np.arange(len(ids)), fit_idx), recipient)
            ledger[probe.probe_id] = {"status": "MATERIALIZED",
                "real_checkpoint": real.best_checkpoint_sha256,
                "twin_checkpoint": twin.best_checkpoint_sha256,
                "real_path": real_path, "twin_path": twin_path,
                "real_transition": dict(real_detail),
                "twin_transition": dict(twin_detail),
                "real_status": real_status, "twin_status": twin_status,
                "paired": test.receipt_sha256,
                "support": [item.receipt_sha256 for item in decisions]}
            # Statistical objective screening is independent of whether this
            # shallow E1r policy happens to clear the economic threshold.  A
            # prior version discarded measured real-vs-twin evidence whenever
            # its policy was economically typed as a loser, conflating label
            # learnability with downstream threshold feasibility.
            p_values[probe.probe_id] = test.p_value_one_sided
            families[probe.probe_id] = f"cell-{probe.cell:02d}"
            screens[probe.probe_id] = (real_score, twin_score)
            self._m8_objective_payloads[probe.probe_id] = [
                real_model_name, canary_name,
                *self._m8_path_payloads[
                    f"E1r/objectives/{probe.probe_id}/real"],
            ]
            self._m8_objective_payloads[twin_spec.probe_id] = [
                twin_model_name, canary_name,
                *self._m8_path_payloads[
                    f"E1r/objectives/{probe.probe_id}/twin"],
            ]
            del real, twin, normalized, twin_normalized
        if optimizer_fits > 90 or set(ledger) != {p.probe_id for p in PROBE_REGISTRY}:
            raise RealDiagnosticExecutorRefusal("E1r atlas ledger violates 90-fit census")
        if not p_values or "C14P01" not in p_values:
            raise RealDiagnosticExecutorRefusal(
                "E1r lacks the executable canonical action objective")
        holm = hierarchical_holm(p_values, families)
        screen_status = ("ELIGIBLE" if holm.surviving_probes
                         else "NO_SIGNIFICANT_OBJECTIVE")
        # An empty Holm set is a measured scientific result, not a malformed
        # run.  Continue exactly one diagnostic path through C14/A-004 so the
        # five-arm/two-head matrix can identify whether the limiting layer is
        # objective learnability, representation, or downstream policy.
        ordered = (sorted(holm.surviving_probes,
                          key=lambda probe: (p_values[probe], probe))
                   if holm.surviving_probes else ["C14P01"])
        matrix = np.stack([fingerprints[probe] for probe in ordered])
        correlation = np.eye(len(matrix)) if len(matrix) == 1 else np.corrcoef(matrix)
        finalists = nonredundant_finalists(
            ordered, target_correlation=correlation,
            target_hashes={probe: _sha_bytes(np.ascontiguousarray(
                fingerprints[probe]).tobytes()) for probe in ordered}, maximum=4)
        result = {"schema": "entry-v2-fit-only-e1r-measured-v1",
            "status": screen_status, "candidate_count": len(ids),
            "candidate_manifest_sha256": _sha(ids.tolist()),
            "pretext_checkpoints": [p.checkpoint_sha256 for p in pretexts],
            "optimizer_fit_count": optimizer_fits, "ledger": ledger,
            "holm_receipt_sha256": holm.receipt_sha256,
            "holm_survivor_count": len(holm.surviving_probes),
            "diagnostic_fallback": (None if holm.surviving_probes else "C14P01"),
            "finalists": list(finalists.finalists),
            "finalist_receipt_sha256": finalists.receipt_sha256,
            "fit_only_max_d8": 20210930}
        result["receipt_sha256"] = _sha(result)
        self._fit_only_e1r_plane = (specs, ids, rows, targets, fit_idx, screens)
        return MappingProxyType(result)

    def _produce_fit_only_e2r(self, e1r: Mapping[str, Any]) -> Mapping[str, Any]:
        """Refit one rehearsal objective, then execute a real fresh 5x2 matrix."""
        specs, ids, probe_rows, _old_targets, _fit_idx, _screens = \
            self._fit_only_e1r_plane
        days = np.asarray(probe_rows.day, np.int64); assets = np.asarray(probe_rows.asset, str)
        bindings, _ = self._binding_indexes()
        recipient = np.asarray([bindings[cid].action_loss_mask for cid in ids], bool)
        e2_fit_end = _rehearsal_bounds("E2r", "FIT")[1]
        fit_idx = np.flatnonzero(_rehearsal_mask(days, "E2r", "FIT"))
        contexts = self._rehearsal_context_factory(e2_fit_end)
        observed = {session.key: session for session in self.stage.diagnostic_corpus.sessions}
        targets = {}
        for probe_id in e1r["finalists"]:
            probe = next(item for item in PROBE_REGISTRY if item.probe_id == probe_id)
            pieces = []
            for spec in specs:
                session = observed[(spec.asset, spec.trading_day)]
                local_map = {cid: i for i, cid in enumerate(session.atlas.candidate_ids)}
                local = np.asarray([local_map[cid] for cid in spec.candidate_ids], np.int64)
                pieces.append(_target_take(materialize_probe_target(
                    session.atlas, probe,
                    fit_context=contexts[probe_id][session.key]), local))
            targets[probe_id] = _concat_targets(pieces)
        split = np.full(len(days), "OUTSIDE", dtype="<U16")
        for role in ("FIT", "PLATT", "THRESHOLD", "FORWARD"):
            split[_rehearsal_mask(days, "E2r", role)] = role
        if np.any(split == "OUTSIDE"):
            raise RealDiagnosticExecutorRefusal(
                "E2r probe plane contains a row outside frozen chronology")
        permutation = stage_global_recipient_fixed_permutation(
            split, assets, days, recipient, seed=20260816)
        plane = SharedProbePlane.build(probe_rows, fit_idx, stage_id="E2R")
        torch.manual_seed(20260816); initialization = AtlasProbeNet()
        objective_receipts = {}; eligible_objectives = []
        for probe_id in e1r["finalists"]:
            probe = next(item for item in PROBE_REGISTRY if item.probe_id == probe_id)
            target = targets[probe_id]
            twin_target = permute_probe_target_recipient_fixed(target, permutation)
            twin_spec = shuffled_probe_for(
                probe, available=self.stage.diagnostic_corpus.sessions[0].atlas.shuffled_probes)
            twin_target = replace(twin_target, probe_id=twin_spec.probe_id,
                schema_sha256=probe_target_schema_sha256(
                    twin_spec.probe_id, twin_target.output_width,
                    twin_target.output_layout, twin_target.direction,
                    twin_target.transform_provenance_sha256,
                    twin_target.prediction_width, twin_target.prediction_layout))
            real = fit_probe(probe, probe_rows, target, fit_indices=fit_idx,
                initialization=initialization, stage_id="E2R", shared_plane=plane,
                device=self.device)
            twin = fit_probe(twin_spec, probe_rows, twin_target, fit_indices=fit_idx,
                initialization=initialization, stage_id="E2R", shared_plane=plane,
                device=self.device)
            improvement = ((real.initial_validation_loss - real.best_validation_loss)
                           - (twin.initial_validation_loss - twin.best_validation_loss))
            objective_receipts[probe_id] = {
                "real_checkpoint": real.best_checkpoint_sha256,
                "twin_checkpoint": twin.best_checkpoint_sha256,
                "real_validation": real.best_validation_loss,
                "twin_validation": twin.best_validation_loss,
                "real_beyond_twin": float(improvement)}
            e2_real_name = f"M8/E2r/objectives/{probe_id}/real.safetensors"
            e2_twin_name = f"M8/E2r/objectives/{probe_id}/twin.safetensors"
            e2_canary_name = f"M8/E2r/objectives/{probe_id}/canary.npz"
            e2_canary_rows = np.arange(min(8, len(plane.normalized)), dtype=np.int64)
            with torch.no_grad():
                e2_real_output = real.model(
                    torch.from_numpy(plane.normalized[e2_canary_rows])).cpu().numpy()
                e2_twin_output = twin.model(
                    torch.from_numpy(plane.normalized[e2_canary_rows])).cpu().numpy()
            self._m8_payloads[e2_real_name] = _safetensors_bytes(real.model)
            self._m8_payloads[e2_twin_name] = _safetensors_bytes(twin.model)
            self._m8_payloads[e2_canary_name] = _npz_bytes({
                "rows": e2_canary_rows,
                "normalized": plane.normalized[e2_canary_rows],
                "real_output": e2_real_output,
                "twin_output": e2_twin_output,
            })
            self._m8_objective_payloads.setdefault(probe_id, []).extend(
                [e2_real_name, e2_canary_name])
            self._m8_objective_payloads.setdefault(twin_spec.probe_id, []).extend(
                [e2_twin_name, e2_canary_name])
            if improvement > 0:
                eligible_objectives.append((float(improvement), probe_id))
            del real, twin
        measured_objectives = [
            (float(row["real_beyond_twin"]), probe)
            for probe, row in objective_receipts.items()
        ]
        if not measured_objectives:
            raise RealDiagnosticExecutorRefusal(
                "E2r objective refits produced no measured comparison")
        objective_status = ("ELIGIBLE" if eligible_objectives
                            else "NO_REAL_BEYOND_TWIN")
        selection_pool = eligible_objectives or measured_objectives
        best_improvement = max(value for value, _ in selection_pool)
        selected_probe = min(probe for value, probe in selection_pool
                             if value == best_improvement)
        objective_freeze = _sha({"schema": "entry-v2-fit-only-e2r-objective-freeze-v1",
                                 "selected_probe": selected_probe,
                                 "status": objective_status,
                                 "refits": objective_receipts})

        # Fresh rehearsal encoders: all optimizer steps aggregate a complete
        # asset-day, and all validation losses are unweighted.
        all_specs = tuple(spec for spec in specs if spec.trading_day <= 20210930)
        all_ids = tuple(cid for spec in all_specs for cid in spec.candidate_ids)
        all_days = np.asarray([bindings[cid].trading_day for cid in all_ids], np.int64)
        all_assets = np.asarray([bindings[cid].asset for cid in all_ids], str)
        all_action = np.asarray([bindings[cid].action_target for cid in all_ids], np.int8)
        all_recipient = np.asarray([bindings[cid].action_loss_mask for cid in all_ids], bool)
        e2_fit_mask = _rehearsal_mask(all_days, "E2r", "FIT")
        unique_fit_days = sorted(set(all_days[e2_fit_mask].tolist()))
        validation_days = set(unique_fit_days[-max(1, int(np.ceil(.1 * len(unique_fit_days)))):])
        train_mask = e2_fit_mask & ~np.isin(all_days, tuple(validation_days))
        action_weight, action_receipt = action_fit_weights(
            all_assets, all_days, all_action, all_recipient, train_mask)
        base_weight, base_receipt = asset_day_fit_weights(
            all_assets, all_days, all_action, np.ones(len(all_ids), bool), train_mask,
            apply_class_weight=False)
        # Each binary oracle owns its own capped class factors.  Reusing the
        # action label for top3/wall silently changes their optimization law.
        joined_labels = tuple(label for spec in all_specs for _, label in
            self.stage.corpus_stage.corpus.teacher.join_training(spec.examples))
        top_target = np.asarray([label.top3 for label in joined_labels], np.int8)
        wall_target = np.asarray([label.wall_hit for label in joined_labels], np.int8)
        top_weight, top_receipt = asset_day_fit_weights(
            all_assets, all_days, top_target, np.ones(len(all_ids), bool), train_mask,
            apply_class_weight=True)
        wall_weight, wall_receipt = asset_day_fit_weights(
            all_assets, all_days, wall_target, np.ones(len(all_ids), bool), train_mask,
            apply_class_weight=True)
        all_phase = np.asarray([example.phase for spec in all_specs
                                for example in spec.examples], str)
        all_decision = np.asarray([bindings[cid].decision_ts_ns
                                   for cid in all_ids], np.int64)
        weight_position = {cid: i for i, cid in enumerate(all_ids)}
        shared_pair_manifest = canonical_phase_pair_manifest(
            np.asarray(all_ids, str), all_assets, all_days, all_phase,
            all_decision, all_action, all_recipient, train_mask)
        shared_pairs_by_day: dict[tuple[str, int], dict[tuple[str, str], float]] = {}
        for pair, weight in zip(shared_pair_manifest.candidate_id_pairs,
                                shared_pair_manifest.pair_weights):
            row = weight_position[pair[0]]
            shared_pairs_by_day.setdefault(
                (str(all_assets[row]), int(all_days[row])), {})[tuple(pair)] = float(weight)
        by_day: dict[tuple[str, int], list[Any]] = {}
        validation_by_day: dict[tuple[str, int], list[Any]] = {}
        e2_fit_lo, e2_fit_hi = _rehearsal_bounds("E2r", "FIT")
        for spec in all_specs:
            if (e2_fit_lo <= spec.trading_day <= e2_fit_hi
                    and spec.trading_day not in validation_days):
                by_day.setdefault((spec.asset, spec.trading_day), []).append(spec)
            elif spec.trading_day in validation_days:
                validation_by_day.setdefault((spec.asset, spec.trading_day), []).append(spec)
        rehearsal_input_normalizer = self._fit_rehearsal_input_normalizer(
            all_specs, set(unique_fit_days) - validation_days,
        )
        horizon_count = np.zeros(SELECTED_HORIZON_WIDTH, np.int64)
        horizon_total = np.zeros(SELECTED_HORIZON_WIDTH, np.float64)
        horizon_square = np.zeros(SELECTED_HORIZON_WIDTH, np.float64)
        for spec in all_specs:
            if not (e2_fit_lo <= spec.trading_day <= e2_fit_hi
                    and spec.trading_day not in validation_days):
                continue
            labels = tuple(label for _, label in
                self.stage.corpus_stage.corpus.teacher.join_training(spec.examples))
            session = observed[(spec.asset, spec.trading_day)]
            value_t, valid_t, _ = _selected_horizon_targets_from_spec(
                session.atlas, spec, range(len(spec.candidate_ids)), labels)
            value = value_t.numpy().astype(np.float64); valid = valid_t.numpy().astype(bool)
            horizon_count += valid.sum(0)
            horizon_total += np.where(valid, value, 0.0).sum(0)
            horizon_square += np.where(valid, value * value, 0.0).sum(0)
        if np.any(horizon_count < 2):
            raise RealDiagnosticExecutorRefusal("E2r horizon normalizer lacks support")
        horizon_location = horizon_total / horizon_count
        horizon_scale = np.sqrt(np.maximum(
            horizon_square / horizon_count - horizon_location * horizon_location, 0.0))
        if np.any(horizon_scale <= 0):
            raise RealDiagnosticExecutorRefusal("E2r horizon normalizer is degenerate")
        horizon_normalizer = {
            "schema": "entry-v2-selected-horizon-normalizer-v1",
            "coordinates": list(SELECTED_HORIZON_COORDINATES),
            "target_schema_sha256": SELECTED_HORIZON_SCHEMA_SHA256,
            "target_law_sha256": SELECTED_HORIZON_TARGET_LAW_SHA256,
            "location": horizon_location.tolist(),
            "scale": horizon_scale.tolist()}
        horizon_normalizer["receipt_sha256"] = _sha(horizon_normalizer)
        horizon_normalizer["fit_manifest_sha256"] = _sha({
            "stage": "E2R", "training_days": sorted(
                set(unique_fit_days) - validation_days),
            "training_candidate_ids": [cid for cid, day in zip(all_ids, all_days)
                if e2_fit_lo <= int(day) <= e2_fit_hi
                and int(day) not in validation_days],
            "count": horizon_count.tolist(),
            "validation_weighting": "UNWEIGHTED_VALID_ROWS"})
        validation_roster = {
            "schema": "entry-v2-e2r-validation-roster-v1",
            "days": sorted(validation_days),
            "candidate_ids": [cid for cid, day in zip(all_ids, all_days)
                              if int(day) in validation_days],
            "weighting": "UNWEIGHTED_VALID_ROWS"}
        validation_roster["receipt_sha256"] = _sha(validation_roster)
        def normalize_horizon(batch: _CandidateBatch) -> _CandidateBatch:
            raw = batch.horizon_targets.numpy().astype(np.float64)
            valid = batch.horizon_valid.numpy().astype(bool)
            value = ((raw - horizon_location) / horizon_scale).astype(np.float32)
            value[~valid] = 0.0
            return replace(batch, horizon_targets=torch.from_numpy(value))
        models = self._new_model_registry(); matrix = {}; row_store = {}
        common_initialization = {arm: _sha_bytes(module_state_bytes(models[arm]))
                                 for arm in CANONICAL_ARMS}
        common_head_initialization = {arm: _sha_bytes(
            module_state_bytes(models[arm].head)) for arm in CANONICAL_ARMS}
        for initial_arm in CANONICAL_ARMS:
            name = f"M8/E2r/arms/{initial_arm}/initial.safetensors"
            self._m8_payloads[name] = _safetensors_bytes(models[initial_arm])
            self._m8_arm_payloads[initial_arm]["initial"] = [name]
        if (common_initialization["C0"] != common_initialization["C1"]
                or common_initialization["L0"] != common_initialization["L1"]
                or len(set(common_head_initialization.values())) != 1):
            raise RealDiagnosticExecutorRefusal(
                "E2r common/base-copy initialization differs")
        base_state: dict[str, Mapping[str, Any]] = {}
        base_checkpoint: dict[str, str] = {}
        raw_memory: dict[tuple[str, str, int, str], torch.Tensor] = {}
        raw_memory_hash: dict[tuple[str, str, int, str], str] = {}
        observed_by_day = {session.key: session for session in self.stage.diagnostic_corpus.sessions}
        objective_spec = next(item for item in PROBE_REGISTRY
                              if item.probe_id == selected_probe)
        selected_target = targets[selected_probe]
        target_position = {cid: i for i, cid in enumerate(ids)}
        base_by_arm = {"C0": "C0", "C1": "C0", "L0": "L0",
                       "L1": "L0", "M1": "M1"}
        canary_spec = min(
            all_specs,
            key=lambda item: (int(item.candidate_cutoffs[0]), item.trading_day,
                              item.asset, item.session_id),
        )
        canary_batch = normalize_horizon(self._build_full_policy_batch(
            canary_spec, (0,),
            observed_by_day[(canary_spec.asset, canary_spec.trading_day)],
            bindings, normalizer=rehearsal_input_normalizer))
        canary_input_name = "M8/E2r/arms/canary-input.npz"
        self._m8_payloads[canary_input_name] = _npz_bytes({
            "continuous": canary_batch.continuous.cpu().numpy(),
            "categorical": canary_batch.categorical.cpu().numpy(),
            "clock": canary_batch.clock.cpu().numpy(),
            "cutoffs": canary_batch.cutoffs.cpu().numpy(),
            "decisions": canary_batch.decisions.cpu().numpy(),
            "candidate_features": canary_batch.candidate_features.cpu().numpy(),
            "context_values": canary_batch.context_values.cpu().numpy(),
            "context_type_ids": canary_batch.context_type_ids.cpu().numpy(),
            "context_valid": canary_batch.context_valid.cpu().numpy(),
            "static_features": canary_batch.static_features.cpu().numpy(),
        })
        canary_meta_name = "M8/E2r/arms/canary-input.json"
        self._m8_payloads[canary_meta_name] = _canonical_json_bytes({
            "schema": "entry-v2-m8-arm-canary-input-v1",
            "asset": canary_batch.asset, "day": canary_batch.day,
            "session_id": canary_batch.session_id,
            "candidate_ids": list(canary_batch.candidate_ids),
            "input_npz_sha256": _sha_bytes(self._m8_payloads[canary_input_name]),
        })
        # Base arms must finish before their byte-copy experiment variants.
        for arm in ("C0", "L0", "M1", "C1", "L1"):
            model = models[arm].to(self.device)
            source_arm = base_by_arm[arm]
            if arm in ("C1", "L1"):
                if source_arm not in base_state:
                    raise RealDiagnosticExecutorRefusal("E2r base checkpoint is absent")
                model.load_state_dict(base_state[source_arm], strict=True)
                copied = _sha_bytes(module_state_bytes(model))
                if copied != base_checkpoint[source_arm]:
                    raise RealDiagnosticExecutorRefusal(
                        f"E2r {source_arm}->{arm} byte copy differs")
                pointwise_name = f"M8/E2r/arms/{arm}/pointwise.safetensors"
                self._m8_payloads[pointwise_name] = _safetensors_bytes(model)
                self._m8_arm_payloads[arm]["pointwise"] = [pointwise_name]
            objective_head = torch.nn.Linear(512, PADDED_OUTPUT_WIDTH).to(self.device)
            torch.manual_seed(20260816)
            torch.nn.init.xavier_uniform_(objective_head.weight)
            torch.nn.init.zeros_(objective_head.bias)
            if arm == "C0":
                torch.nn.init.zeros_(objective_head.weight)
                torch.nn.init.zeros_(objective_head.bias)
                objective_head.requires_grad_(False)
            base_decoder = (LastRowReconstructionProbe(
                len(self.schema.continuous_fields), CATEGORY_SIZES).to(self.device)
                if arm in ("C0", "L0", "M1") else None)
            optimizer = None
            epoch_trace = []; best_validation = np.inf; best_state = None
            base_best_validation = np.inf; base_best_state = None
            base_stale = 0; head_stale = 0
            epoch_range = (range(18) if arm in ("C0", "L0", "M1")
                           else range(12, 18))
            for epoch in epoch_range:
                if epoch < 12 and epoch >= 2 and base_stale >= 3:
                    continue
                stage_name = ("BASE" if epoch < 12 else
                              "A0_HEAD" if arm == "C0" else "SELECTED_HEAD")
                if epoch == 0:
                    assert base_decoder is not None
                    optimizer = torch.optim.Adam(
                        [*model.parameters(), *base_decoder.parameters()], lr=3e-4)
                elif epoch == 12:
                    if arm in ("C0", "L0", "M1"):
                        if base_best_state is None or base_decoder is None:
                            raise RealDiagnosticExecutorRefusal(
                                f"E2r {arm} base validation produced no checkpoint")
                        model.load_state_dict(base_best_state[0], strict=True)
                        base_decoder.load_state_dict(base_best_state[1], strict=True)
                        base_state[arm] = {
                            name: value.detach().cpu().clone()
                            for name, value in model.state_dict().items()
                        }
                        base_checkpoint[arm] = _sha_bytes(module_state_bytes(model))
                        pointwise_name = (
                            f"M8/E2r/arms/{arm}/pointwise.safetensors")
                        self._m8_payloads[pointwise_name] = _safetensors_bytes(model)
                        self._m8_arm_payloads[arm]["pointwise"] = [pointwise_name]
                    model.encoder.requires_grad_(False)
                    parameters = list(model.head.parameters())
                    if arm != "C0":
                        parameters += list(objective_head.parameters())
                    optimizer = torch.optim.Adam(parameters, lr=3e-4)
                assert optimizer is not None
                named_parameters = [*model.named_parameters(),
                    *((f"objective_head.{name}", value)
                      for name, value in objective_head.named_parameters()),
                    *((f"base_decoder.{name}", value)
                      for name, value in (() if base_decoder is None
                                          else base_decoder.named_parameters()))]
                before_parameters = {name: value.detach().cpu().clone()
                                     for name, value in named_parameters}
                model.train()
                if base_decoder is not None:
                    base_decoder.train(stage_name == "BASE")
                component_total = {}; gradient_norm = 0.0
                epoch_pair_count = 0; pair_receipts = []
                for key in sorted(by_day):
                    optimizer.zero_grad(set_to_none=True); day_loss = None
                    day_logits = []; day_ids = []; day_phase = []; day_decisions = []
                    day_action = []; day_recipient = []
                    for spec in by_day[key]:
                        local = tuple(range(len(spec.candidate_ids)))
                        batch = normalize_horizon(self._build_full_policy_batch(
                            spec, local,
                            observed_by_day[(spec.asset, spec.trading_day)],
                            bindings, normalizer=rehearsal_input_normalizer)
                        )
                        take = np.asarray([weight_position[cid] for cid in batch.candidate_ids])
                        supplied = {"action": torch.from_numpy(action_weight[take]),
                                    "base": torch.from_numpy(base_weight[take]),
                                    "top3": torch.from_numpy(top_weight[take]),
                                    "wall": torch.from_numpy(wall_weight[take])}
                        with self._held_autocast():
                            memory_key = (source_arm, batch.asset, int(batch.day),
                                          batch.session_id)
                            if stage_name == "BASE":
                                memory = model.encoder(
                                    batch.continuous.to(self.device),
                                    batch.categorical.to(self.device),
                                    batch.cutoffs.to(self.device),
                                    receive_clock_ns=batch.clock.to(self.device),
                                    candidate_decision_ts_ns=batch.decisions.to(self.device),
                                    asset_idx=C.ASSET_INDEX[batch.asset])
                            else:
                                if memory_key not in raw_memory:
                                    with torch.no_grad():
                                        frozen = model.encoder(
                                            batch.continuous.to(self.device),
                                            batch.categorical.to(self.device),
                                            batch.cutoffs.to(self.device),
                                            receive_clock_ns=batch.clock.to(self.device),
                                            candidate_decision_ts_ns=batch.decisions.to(self.device),
                                            asset_idx=C.ASSET_INDEX[batch.asset])
                                    raw_memory[memory_key] = frozen.detach().cpu().contiguous()
                                    raw_memory_hash[memory_key] = _sha_bytes(
                                        raw_memory[memory_key].numpy().tobytes())
                                elif (_sha_bytes(raw_memory[memory_key].numpy().tobytes())
                                      != raw_memory_hash[memory_key]):
                                    raise RealDiagnosticExecutorRefusal(
                                        "E2r immutable raw-memory bytes changed")
                                memory = raw_memory[memory_key].to(self.device)
                            output = model.head(
                                memory, batch.candidate_features.to(self.device),
                                batch.context_values.to(self.device),
                                batch.context_type_ids.to(self.device),
                                batch.context_valid.to(self.device), C.ASSET_INDEX[batch.asset],
                                static_features=(batch.static_features.to(self.device)
                                    if stage_name == "SELECTED_HEAD"
                                    and arm in ("L1", "M1") else None))
                            loss, components = _actual_multitask_loss(output, batch, supplied)
                            if stage_name == "BASE":
                                assert base_decoder is not None
                                reconstruction, field_continuous, field_categorical = \
                                    _field_reconstruction_loss(
                                        base_decoder, memory, batch,
                                        supplied["base"],
                                    )
                                loss = loss + reconstruction
                                components = dict(components)
                                components["field_continuous"] = field_continuous
                                components["field_categorical"] = field_categorical
                            if stage_name == "SELECTED_HEAD":
                                objective_rows = np.asarray(
                                    [target_position[cid] for cid in batch.candidate_ids],
                                    np.int64)
                                objective_loss = loss_for_probe(
                                    objective_spec,
                                    objective_head(output.decision_state.float()),
                                    _target_take(selected_target, objective_rows))
                                loss = loss + objective_loss
                                components = dict(components)
                                components["selected_objective"] = objective_loss
                        day_loss = loss if day_loss is None else day_loss + loss
                        day_logits.append(output.action_logit.float())
                        day_ids.extend(batch.candidate_ids)
                        day_phase.extend(str(item.phase) for item in spec.examples)
                        day_decisions.extend(int(bindings[cid].decision_ts_ns)
                                             for cid in batch.candidate_ids)
                        day_action.extend(int(bindings[cid].action_target)
                                          for cid in batch.candidate_ids)
                        day_recipient.extend(bool(bindings[cid].action_loss_mask)
                                             for cid in batch.candidate_ids)
                        for name, value in components.items():
                            component_total[name] = component_total.get(name, 0.0) + float(value)
                    if day_loss is None:
                        continue
                    pair_manifest = canonical_phase_pair_manifest(
                        np.asarray(day_ids, str), np.full(len(day_ids), key[0]),
                        np.full(len(day_ids), key[1], np.int64),
                        np.asarray(day_phase, str), np.asarray(day_decisions, np.int64),
                        np.asarray(day_action, np.int8), np.asarray(day_recipient, bool),
                        np.ones(len(day_ids), bool))
                    actual_pair_weights = {tuple(pair): float(weight) for pair, weight in
                        zip(pair_manifest.candidate_id_pairs,
                            pair_manifest.pair_weights)}
                    if actual_pair_weights != shared_pairs_by_day.get(key, {}):
                        raise RealDiagnosticExecutorRefusal(
                            "E2r neural phase-pair manifest differs from frozen manifest")
                    if pair_manifest.group_count:
                        epoch_pair_count += len(pair_manifest.pairs)
                        pair_receipts.append(pair_manifest.receipt_sha256)
                        logits = torch.cat(day_logits)
                        pairs = np.asarray(pair_manifest.pairs, np.int64)
                        pair_weight = torch.from_numpy(np.asarray(
                            pair_manifest.pair_weights, np.float32)).to(self.device)
                        contrast = (torch.nn.functional.softplus(
                            -(logits[pairs[:, 0]] - logits[pairs[:, 1]]))
                            * pair_weight).sum()
                        day_loss = day_loss + contrast
                        component_total["phase_pair_contrast"] = (
                            component_total.get("phase_pair_contrast", 0.0)
                            + float(contrast.detach()))
                    day_loss.backward()
                    gradient_norm += float(sum(torch.linalg.vector_norm(p.grad.detach())
                        for group in optimizer.param_groups for p in group["params"]
                        if p.grad is not None))
                    optimizer.step()
                if epoch_pair_count <= 0:
                    raise RealDiagnosticExecutorRefusal(
                        f"E2r {arm} training has no phase-matched contrast pairs")
                model.eval()
                if base_decoder is not None:
                    base_decoder.eval()
                validation_values = []; validation_pair_count = 0
                with torch.no_grad():
                    for key in sorted(validation_by_day):
                        day_outputs = []; day_ids = []; day_phase = []
                        day_decisions = []; day_action = []; day_recipient = []
                        day_value = []
                        for spec in validation_by_day[key]:
                            batch = normalize_horizon(self._build_full_policy_batch(
                                spec, tuple(range(len(spec.candidate_ids))),
                                observed_by_day[(spec.asset, spec.trading_day)],
                                bindings, normalizer=rehearsal_input_normalizer))
                            with self._held_autocast():
                                memory_key = (source_arm, batch.asset, int(batch.day),
                                              batch.session_id)
                                if stage_name == "BASE":
                                    memory = model.encoder(
                                        batch.continuous.to(self.device),
                                        batch.categorical.to(self.device),
                                        batch.cutoffs.to(self.device),
                                        receive_clock_ns=batch.clock.to(self.device),
                                        candidate_decision_ts_ns=batch.decisions.to(self.device),
                                        asset_idx=C.ASSET_INDEX[batch.asset])
                                else:
                                    if memory_key not in raw_memory:
                                        frozen = model.encoder(
                                            batch.continuous.to(self.device),
                                            batch.categorical.to(self.device),
                                            batch.cutoffs.to(self.device),
                                            receive_clock_ns=batch.clock.to(self.device),
                                            candidate_decision_ts_ns=batch.decisions.to(self.device),
                                            asset_idx=C.ASSET_INDEX[batch.asset])
                                        raw_memory[memory_key] = frozen.detach().cpu().contiguous()
                                        raw_memory_hash[memory_key] = _sha_bytes(
                                            raw_memory[memory_key].numpy().tobytes())
                                    elif (_sha_bytes(
                                            raw_memory[memory_key].numpy().tobytes())
                                          != raw_memory_hash[memory_key]):
                                        raise RealDiagnosticExecutorRefusal(
                                            "E2r immutable raw-memory bytes changed")
                                    memory = raw_memory[memory_key].to(self.device)
                                output = model.head(
                                    memory, batch.candidate_features.to(self.device),
                                    batch.context_values.to(self.device),
                                    batch.context_type_ids.to(self.device),
                                    batch.context_valid.to(self.device),
                                    C.ASSET_INDEX[batch.asset],
                                    static_features=(batch.static_features.to(self.device)
                                        if stage_name == "SELECTED_HEAD"
                                        and arm in ("L1", "M1") else None))
                                value, _ = _actual_multitask_loss(output, batch)
                                if stage_name == "BASE":
                                    assert base_decoder is not None
                                    reconstruction, _continuous, _categorical = \
                                        _field_reconstruction_loss(
                                            base_decoder, memory, batch,
                                        )
                                    value = value + reconstruction
                                if stage_name == "SELECTED_HEAD":
                                    objective_rows = np.asarray(
                                        [target_position[cid] for cid in batch.candidate_ids],
                                        np.int64)
                                    value = value + loss_for_probe(
                                        objective_spec,
                                        objective_head(output.decision_state.float()),
                                        _target_take(selected_target, objective_rows),
                                        use_fit_weight=False)
                            day_value.append((value.float(), len(batch.candidate_ids))); day_outputs.append(
                                output.action_logit.float())
                            day_ids.extend(batch.candidate_ids)
                            day_phase.extend(str(item.phase) for item in spec.examples)
                            day_decisions.extend(int(bindings[cid].decision_ts_ns)
                                                 for cid in batch.candidate_ids)
                            day_action.extend(int(bindings[cid].action_target)
                                              for cid in batch.candidate_ids)
                            day_recipient.extend(bool(bindings[cid].action_loss_mask)
                                                 for cid in batch.candidate_ids)
                        pair = canonical_phase_pair_manifest(
                            np.asarray(day_ids, str), np.full(len(day_ids), key[0]),
                            np.full(len(day_ids), key[1], np.int64),
                            np.asarray(day_phase, str), np.asarray(day_decisions, np.int64),
                            np.asarray(day_action, np.int8),
                            np.asarray(day_recipient, bool), np.ones(len(day_ids), bool))
                        # Checkpoint selection is a plain mean over valid rows;
                        # no asset/day or class factor may reach validation.
                        val = sum(value * count for value, count in day_value) / sum(
                            count for _value, count in day_value)
                        if len(pair.pairs):
                            logits = torch.cat(day_outputs)
                            pairs = np.asarray(pair.pairs, np.int64)
                            # Validation is deliberately unweighted.
                            val = val + torch.nn.functional.softplus(
                                -(logits[pairs[:, 0]] - logits[pairs[:, 1]])).mean()
                            validation_pair_count += len(pair.pairs)
                        validation_values.append(float(val))
                if not validation_values or validation_pair_count <= 0:
                    raise RealDiagnosticExecutorRefusal(
                        f"E2r {arm} validation lacks unweighted phase pairs")
                validation_loss = float(np.mean(validation_values))
                checkpoint = (
                    _full_learner_checkpoint_sha256(model, objective_head)
                    if stage_name != "BASE" else _sha({
                        "schema": "entry-v2-fit-only-base-checkpoint-v1",
                        "model_sha256": _sha_bytes(module_state_bytes(model)),
                        "base_decoder_sha256":
                            _sha_bytes(module_state_bytes(base_decoder)),
                    }))
                after_parameters = [*model.named_parameters(),
                    *((f"objective_head.{name}", value)
                      for name, value in objective_head.named_parameters()),
                    *((f"base_decoder.{name}", value)
                      for name, value in (() if base_decoder is None
                                          else base_decoder.named_parameters()))]
                parameter_delta = float(sum(torch.linalg.vector_norm(
                    value.detach().cpu() - before_parameters[name])
                    for name, value in after_parameters))
                epoch_trace.append({"epoch": epoch, "stage": stage_name,
                                    "components": component_total,
                                    "gradient_norm": gradient_norm,
                                    "parameter_delta": parameter_delta,
                                    "validation_loss": validation_loss,
                                    "validation_pair_count": validation_pair_count,
                                    "checkpoint_sha256": checkpoint,
                                    "phase_pair_count": epoch_pair_count,
                                    "phase_pair_manifest_sha256": _sha(pair_receipts),
                                    "optimizer_step_unit": "complete_asset_day_gradient",
                                    "validation_weighting": "UNWEIGHTED"})
                if stage_name == "BASE":
                    if validation_loss < base_best_validation * .999:
                        base_best_validation = validation_loss; base_stale = 0
                        assert base_decoder is not None
                        base_best_state = (
                            {name: value.detach().cpu().clone()
                             for name, value in model.state_dict().items()},
                            {name: value.detach().cpu().clone()
                             for name, value in base_decoder.state_dict().items()},
                        )
                    else:
                        base_stale += 1
                elif validation_loss < best_validation * .999:
                    best_validation = validation_loss; head_stale = 0
                    best_state = (
                        {name: value.detach().cpu().clone()
                         for name, value in model.state_dict().items()},
                        {name: value.detach().cpu().clone()
                         for name, value in objective_head.state_dict().items()},
                    )
                else:
                    head_stale += 1
                if stage_name != "BASE" and epoch >= 13 and head_stale >= 2:
                    break
            if arm in ("C0", "L0", "M1") and arm not in base_state:
                # Two base epochs always complete before the objective stage.
                raise RealDiagnosticExecutorRefusal(f"E2r {arm} base fit is absent")
            if best_state is None:
                raise RealDiagnosticExecutorRefusal(f"E2r {arm} produced no checkpoint")
            model.load_state_dict(best_state[0], strict=True)
            objective_head.load_state_dict(best_state[1], strict=True)
            best_reload_sha256 = _full_learner_checkpoint_sha256(
                model, objective_head)
            if best_reload_sha256 not in {row["checkpoint_sha256"] for row in epoch_trace}:
                raise RealDiagnosticExecutorRefusal(f"E2r {arm} best reload differs")
            final_model_name = f"M8/E2r/arms/{arm}/final.safetensors"
            objective_head_name = (
                f"M8/E2r/arms/{arm}/objective-head.safetensors")
            self._m8_payloads[final_model_name] = _safetensors_bytes(model)
            self._m8_payloads[objective_head_name] = _safetensors_bytes(
                objective_head)
            self._m8_arm_payloads[arm]["best"] = [
                final_model_name, objective_head_name]
            self._m8_arm_payloads[arm]["final"] = [
                final_model_name, objective_head_name]
            with torch.no_grad(), self._held_autocast():
                canary_memory = model.encoder(
                    canary_batch.continuous.to(self.device),
                    canary_batch.categorical.to(self.device),
                    canary_batch.cutoffs.to(self.device),
                    receive_clock_ns=canary_batch.clock.to(self.device),
                    candidate_decision_ts_ns=canary_batch.decisions.to(self.device),
                    asset_idx=C.ASSET_INDEX[canary_batch.asset])
                canary_output = model.head(
                    canary_memory,
                    canary_batch.candidate_features.to(self.device),
                    canary_batch.context_values.to(self.device),
                    canary_batch.context_type_ids.to(self.device),
                    canary_batch.context_valid.to(self.device),
                    C.ASSET_INDEX[canary_batch.asset],
                    static_features=(canary_batch.static_features.to(self.device)
                                     if arm in ("L1", "M1") else None))
            canary_output_name = f"M8/E2r/arms/{arm}/canary-output.npz"
            canary_arrays = dict(_output_canary_arrays(canary_output))
            with torch.no_grad():
                canary_arrays["objective_output"] = np.ascontiguousarray(
                    objective_head(
                        canary_output.decision_state.float()).float().cpu().numpy())
            self._m8_payloads[canary_output_name] = _npz_bytes(canary_arrays)
            for role in ("best", "final"):
                self._m8_arm_payloads[arm][role].extend(
                    [canary_input_name, canary_meta_name, canary_output_name])
            states = []; direct_probability = []; phases = []
            model.eval()
            for spec in all_specs:
                batch = self._build_full_policy_batch(
                    spec, tuple(range(len(spec.candidate_ids))),
                    observed_by_day[(spec.asset, spec.trading_day)], bindings,
                    normalizer=rehearsal_input_normalizer)
                with torch.no_grad(), self._held_autocast():
                    memory_key = (source_arm, batch.asset, int(batch.day), batch.session_id)
                    if memory_key not in raw_memory:
                        # PLATT/THRESHOLD rows were never touched by optimizer
                        # epochs.  Encode each once from the frozen base and
                        # immediately admit it to the same immutable plane.
                        frozen = model.encoder(
                            batch.continuous.to(self.device),
                            batch.categorical.to(self.device),
                            batch.cutoffs.to(self.device),
                            receive_clock_ns=batch.clock.to(self.device),
                            candidate_decision_ts_ns=batch.decisions.to(self.device),
                            asset_idx=C.ASSET_INDEX[batch.asset])
                        raw_memory[memory_key] = frozen.detach().cpu().contiguous()
                        raw_memory_hash[memory_key] = _sha_bytes(
                            raw_memory[memory_key].numpy().tobytes())
                    elif (_sha_bytes(raw_memory[memory_key].numpy().tobytes())
                          != raw_memory_hash[memory_key]):
                        raise RealDiagnosticExecutorRefusal(
                            "E2r immutable raw-memory bytes changed")
                    memory = raw_memory[memory_key].to(self.device)
                    output = model.head(
                        memory, batch.candidate_features.to(self.device),
                        batch.context_values.to(self.device),
                        batch.context_type_ids.to(self.device),
                        batch.context_valid.to(self.device), C.ASSET_INDEX[batch.asset],
                        static_features=(batch.static_features.to(self.device)
                                         if arm in ("L1", "M1") else None))
                states.append(output.decision_state.float().cpu().numpy())
                direct_probability.append(torch.sigmoid(
                    output.action_logit.float()).cpu().numpy())
                phases.extend(str(item.phase) for item in spec.examples)
            representation = np.ascontiguousarray(np.concatenate(states), np.float32)
            direct_probability_array = np.ascontiguousarray(
                np.concatenate(direct_probability), np.float64)
            rows = FrozenRepresentationRows(
                representation, np.asarray(all_ids, str), all_assets, all_days,
                np.asarray([bindings[cid].decision_ts_ns for cid in all_ids], np.int64),
                all_action, all_recipient, np.asarray(phases, str),
                np.where(np.isin(all_days, tuple(validation_days)),
                         "VALIDATION", "E2R"),
                "REHEARSAL_E2", group_semantics="PHASE")
            rows.validate(); tree = fit_diagnostic_catboost(
                rows, expected_representation_sha256=rows.representation_sha256,
                # The frozen 40-group floor belongs to the independent
                # acceptance competence population.  The real E2r arm matrix
                # consumes every chronologically available A-013 day/phase
                # pair (33/52/49 groups after validation in the pinned
                # corpus), and requires a nonempty executable ranker for each
                # asset rather than inventing additional groups.
                minimum_pair_groups_per_asset=1)
            if any(tree.assets[asset].ranker_model is None for asset in C.ASSETS):
                raise RealDiagnosticExecutorRefusal(
                    f"E2r {arm} has no executable day/phase PairLogit ranker")
            for asset in C.ASSETS:
                manifest = tree.assets[asset].pair_manifest
                selected_ids = np.asarray(all_ids, str)[manifest.indices]
                actual = {tuple((str(selected_ids[p]), str(selected_ids[n]))):
                    float(weight) for (p, n), weight in zip(
                        manifest.pairs, manifest.pair_weights)}
                expected = {pair: weight for day_key, pairs in
                    shared_pairs_by_day.items() if day_key[0] == asset
                    for pair, weight in pairs.items()}
                if actual != expected:
                    raise RealDiagnosticExecutorRefusal(
                        f"E2r {arm}/{asset} CatBoost phase pairs differ")
            catboost_names: list[str] = []
            catboost_canary: dict[str, list[float]] = {}
            canary_state = np.ascontiguousarray(
                canary_output.decision_state.float().cpu().numpy(), np.float32)
            with tempfile.TemporaryDirectory(
                    prefix=f"entry-v2-m8-{arm}-catboost-") as directory:
                root = Path(directory)
                for asset in C.ASSETS:
                    for family, fitted_model in (
                            ("action", tree.assets[asset].action_model),
                            ("pairlogit", tree.assets[asset].ranker_model)):
                        if fitted_model is None:
                            raise RealDiagnosticExecutorRefusal(
                                f"E2r {arm}/{asset} {family} model is absent")
                        temporary = root / f"{asset}-{family}.cbm"
                        fitted_model.save_model(str(temporary), format="cbm")
                        name = (f"M8/E2r/arms/{arm}/catboost/"
                                f"{asset}-{family}.cbm")
                        self._m8_payloads[name] = temporary.read_bytes()
                        catboost_names.append(name)
                        prediction = (fitted_model.predict_proba(canary_state)[:, 1]
                                      if family == "action" else
                                      fitted_model.predict(canary_state))
                        catboost_canary[f"{asset}-{family}"] = np.asarray(
                            prediction, np.float64).tolist()
            catboost_config_name = f"M8/E2r/arms/{arm}/catboost/config.json"
            self._m8_payloads[catboost_config_name] = _canonical_json_bytes({
                "schema": "entry-v2-m8-catboost-model-set-v1",
                "arm": arm,
                "fit_receipt_sha256": tree.receipt_sha256,
                "representation_sha256": rows.representation_sha256,
                "pair_manifest_sha256": {
                    asset: tree.assets[asset].pair_manifest.receipt_sha256
                    for asset in C.ASSETS},
                "models": {name: _sha_bytes(self._m8_payloads[name])
                           for name in catboost_names},
                "canary_state_sha256": _sha_bytes(canary_state.tobytes()),
                "canary_predictions": catboost_canary,
            })
            catboost_names.append(catboost_config_name)
            for kind, probability in (("direct_neural", direct_probability_array),
                                      ("catboost", expit(tree.rank_score))):
                evaluation, e2_status, path, e2_detail = self._rehearsal_score_path(
                    probability, ids=np.asarray(all_ids), assets=all_assets,
                    days=all_days, recipient=all_recipient, chronology="E2r",
                    artifact_name=f"E2r/paths/{arm}/{kind}")
                status = e2_status
                by_asset = {row.asset: row for row in evaluation.by_asset}
                matrix[f"{arm}:{kind}"] = {"status": status, "path": path,
                    "e2r_transition": dict(e2_detail),
                    "economics": {asset: asdict(by_asset[asset]) for asset in C.ASSETS},
                    "parameter_count": int(
                        sum(p.numel() for p in model.parameters())
                        + sum(p.numel() for p in objective_head.parameters())
                        + (0 if kind == "direct_neural" else sum(
                            np.asarray(tree.assets[asset].ranker_model
                                .get_leaf_values()).size
                            for asset in C.ASSETS
                            if tree.assets[asset].ranker_model is not None))),
                    "checkpoint_sha256": best_reload_sha256,
                    "model_checkpoint_sha256":
                        _sha_bytes(module_state_bytes(model)),
                    "best_reload_sha256": best_reload_sha256,
                    "representation_sha256": rows.representation_sha256,
                    "epoch_trace": epoch_trace,
                    "learner_law_sha256": _fit_only_full_learner_law_sha256(),
                    "fit_wall": _rehearsal_bounds("E2r", "FIT")[1],
                    "objective_id": ("A0_CURRENT_GROUPING" if arm == "C0"
                                     else selected_probe),
                    "objective_real_checkpoint":
                        (_sha({"objective": "A0_CURRENT_GROUPING",
                               "checkpoint": best_reload_sha256}) if arm == "C0"
                         else objective_receipts[selected_probe]["real_checkpoint"]),
                    "objective_twin_checkpoint":
                        (None if arm == "C0" else
                         objective_receipts[selected_probe]["twin_checkpoint"]),
                    "selected_objective_head_sha256":
                        _sha_bytes(module_state_bytes(objective_head))}
                path_key = f"E2r/paths/{arm}/{kind}"
                if kind == "catboost":
                    self._m8_path_payloads[path_key].extend(catboost_names)
            row_store[arm] = rows.representation_sha256; model.cpu()
        if set(matrix) != {f"{arm}:{kind}" for arm in CANONICAL_ARMS for kind in DECISIONS}:
            raise RealDiagnosticExecutorRefusal("E2r five-arm/two-head census differs")
        eligible = [(min(row["economics"][asset]["usd_per_asset_day"]
                         for asset in C.ASSETS), -row["parameter_count"], key)
                    for key, row in matrix.items() if row["status"] == "ELIGIBLE"]
        diagnostic = [(min(row["economics"][asset]["usd_per_asset_day"]
                           for asset in C.ASSETS), -row["parameter_count"], key)
                      for key, row in matrix.items()]
        if not diagnostic:
            raise RealDiagnosticExecutorRefusal("E2r path matrix is empty")
        path_pool = eligible or diagnostic
        best_key = max((value[0], value[1]) for value in path_pool)
        diagnostic_path = min(value[2] for value in path_pool
                              if value[:2] == best_key)
        deployable = bool(eligible and objective_status == "ELIGIBLE"
                          and e1r.get("status") == "ELIGIBLE")
        winner = diagnostic_path if deployable else None
        selected_path = str(winner or diagnostic_path)
        selected_arm, selected_kind = selected_path.split(":", 1)
        selected_learner_objective = (
            "A0_CURRENT_GROUPING" if selected_arm == "C0" else selected_probe)
        if self._fit_only_e1_targets is None:
            raise RealDiagnosticExecutorRefusal(
                "E1r objective targets were not retained for same-learner proof")
        e1_full_transition = self._train_fit_only_selected_full_path(
            arm=selected_arm, decision_kind=selected_kind,
            chronology="E1r", selected_probe=selected_probe,
            selected_target=self._fit_only_e1_targets[selected_probe],
            target_candidate_ids=ids, specs=specs)
        result = {"schema": "entry-v2-fit-only-e2r-measured-v1",
            "status": ("ELIGIBLE" if deployable
                       else "NO_FIT_ONLY_DEPLOYABLE_DEPTH"),
            "objective_status": objective_status,
            "selected_objective": selected_probe,
            "selected_learner_objective": selected_learner_objective,
            "objective_freeze_receipt_sha256": objective_freeze,
            "objective_refits": objective_receipts, "matrix": matrix,
            "winner": winner, "diagnostic_path": diagnostic_path,
            "selected_e1_full_transition": dict(e1_full_transition),
            "eligible_path_count": len(eligible),
            "action_weight_receipt_sha256": action_receipt.receipt_sha256,
            "base_weight_receipt_sha256": base_receipt.receipt_sha256,
            "top3_weight_receipt_sha256": top_receipt.receipt_sha256,
            "wall_weight_receipt_sha256": wall_receipt.receipt_sha256,
            "selected_horizon_normalizer": horizon_normalizer,
            "selected_horizon_normalizer_sha256":
                horizon_normalizer["receipt_sha256"],
            "input_normalizer_sha256":
                rehearsal_input_normalizer["receipt_sha256"],
            "validation_roster": validation_roster,
            "row_manifests": row_store,
            "factored_fit": {
                "base_fit_arms": ["C0", "L0", "M1"],
                "byte_copies": {"C1": "C0", "L1": "L0"},
                "common_initialization": common_initialization,
                "common_head_initialization": common_head_initialization,
                "base_checkpoints": base_checkpoint,
                "raw_memory_plane_sha256": _sha(sorted(raw_memory_hash.items())),
                "phase_pair_manifest_sha256":
                    shared_pair_manifest.receipt_sha256,
                "raw_memory_immutable": True,
                "objective_encoder_frozen": True,
                "c0_serialization_head": "CANONICAL_ZERO"}}
        result["receipt_sha256"] = _sha(result)
        return MappingProxyType(result)

    def rehearse_held_chain(self) -> Mapping[str, Any]:
        receipt = getattr(self, "_fit_only_rehearsal_receipt", None)
        if receipt is None or receipt.get("status") not in {
                "PASS", "NO_FIT_ONLY_DEPLOYABLE_DEPTH"}:
            raise RealDiagnosticExecutorRefusal(
                "fit-only E1r/E2r rehearsal has not completed")
        return receipt

    def close(self, loaded=None):
        if self._resource_closed:
            return _sha({"state": "ALREADY_CLOSED"})
        if loaded is not None and not self.ownership_transferred:
            return _sha({"one_load_id": loaded.one_load_id,
                         "state": "LIVE_AFTER_ACCEPTANCE"})
        if self.stage is not None:
            self.stage.close()
        self.cold_process_pool.close()
        self.cache.close()
        if self._held_continuous_dir.exists():
            shutil.rmtree(self._held_continuous_dir)
        self._held_continuous_entries.clear()
        if self._held_memory_dir.exists():
            shutil.rmtree(self._held_memory_dir)
        self._held_memory_entries.clear()
        self._resource_closed = True
        return _sha({"state": "CLOSED_AFTER_FORWARD_CAMPAIGN"})

    def close_after_chain(self) -> None:
        if self.ownership_transferred:
            raise RealDiagnosticExecutorRefusal(
                "winner owner must close after the integrated forward campaign")
        self.close()


def entry_v2_production_executor_factory(run_root: str | Path):
    resources = ProductionExactDiagnosticResources(Path(run_root))
    try:
        executor = RealDataExactNeuralDiagnosticExecutor(resources)
        loaded = resources._ensure_loaded()
        chronology = {
            "corpus_max_day": int(loaded.corpus.receipt["observed_end_d8"]),
            "opened_through_day": int(loaded.corpus.receipt["observed_end_d8"]),
            "competence_fit_end": 20210930,
        }
        source_by_key: dict[tuple[str, int], Any] = {}
        for source in (
            *(spec.source for spec in loaded.corpus.corpus.sessions),
            *(session.observed.source for session in loaded.corpus.sessions),
        ):
            key = (source.asset, int(source.d8))
            prior = source_by_key.get(key)
            if (prior is not None and prior.receipt.canonical_bytes() != (
                    source.receipt.canonical_bytes())):
                raise RealDiagnosticExecutorRefusal(
                    "production context source identities conflict")
            source_by_key[key] = source
        context = derive_production_context(
            corpus_receipt=loaded.corpus.receipt, chronology=chronology,
            one_load_id=loaded.one_load_id,
            source_paths=tuple(
                str(source_by_key[key].qre2_path)
                for key in sorted(source_by_key, key=lambda item: (item[1], item[0]))
            ),
            available_host_gib=_available_host_gib(),
        )
        return executor, context
    except BaseException:
        resources.close()
        raise


__all__ = ["CompactAtlasHandoff", "ExpandedEventTransform", "ExpandedEventView",
           "ProductionExactDiagnosticResources", "build_compact_atlas_handoff",
           "entry_v2_production_executor_factory"]
