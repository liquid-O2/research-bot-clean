#!/usr/bin/env python3
"""Immutable, loadable adoption artifact for the E3-selected neural winner.

The older winner-adoption JSON proves only that a selection chain existed.  It
does not contain a model.  This module binds that chain to the exact selected
arm, atlas objective, checkpoints and deployable policy payloads.  E4--E8 may
consume only a verified :class:`WinnerBundle`; a receipt or a collection of
hash strings is deliberately insufficient.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
# Must be established before torch/CUDA initialization in this production
# module; a conflicting parent process is refused by the runtime helper below.
_CUBLAS_WORKSPACE_REQUIRED = ":4096:8"
_CUBLAS_WAS_VALID_BEFORE_IMPORT = (
    os.environ.get("CUBLAS_WORKSPACE_CONFIG") == _CUBLAS_WORKSPACE_REQUIRED
)
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
from pathlib import Path
import shutil
import stat
import tempfile
from types import MappingProxyType
from typing import Any, Mapping, Protocol, Sequence

import numpy as np
import torch
from torch import Tensor, nn
from safetensors.torch import load, load_file
from scipy.optimize import minimize
from scipy.special import expit

from . import common as C
from .capacity_contract import validate_capacity_document
from .causal_label_atlas import PADDED_OUTPUT_WIDTH, PROBE_REGISTRY, ProbeTarget
from .atlas_losses import loss_for_probe
from .model import EntryModelOutput, FullPrefixEntryModel, partition_event_blocks
from .neural_sufficiency_model import (
    CANONICAL_ARMS, CausalMultiresolutionEncoder, CurrentEncoderAdapter,
    EventFieldSchema, LiTShortMemoryEncoder, NeuralSufficiencyModel,
    SharedCandidateDecisionHead, DEFAULT_HORIZONS,
    module_state_bytes,
)
from .selected_horizon_contract import (
    COORDINATES as SELECTED_HORIZON_COORDINATES,
    MODEL_COORDINATES as SELECTED_HORIZON_MODEL_COORDINATES,
    SCHEMA_SHA256 as SELECTED_HORIZON_SCHEMA_SHA256,
    TARGET_LAW_SHA256 as SELECTED_HORIZON_TARGET_LAW_SHA256,
    WIDTH as SELECTED_HORIZON_WIDTH,
)
from .neural_sufficiency_runner import load_winner_adoption
from .policy import AssetPolicy, ModelInputBinding, PolicyConfig

_CUDA_WAS_INITIALIZED_AT_MODULE_IMPORT = torch.cuda.is_initialized()


SCHEMA = "entry-v2-neural-winner-bundle-v1"
MANIFEST = "winner.json"
BASE_PAYLOADS = (
    "arm.json", "objective.json", "encoder.safetensors", "head.safetensors",
    "objective-head.safetensors",
    "normalizers.json", "mapper.json", "calibrator.json", "thresholds.json",
    "policy-canary.json", "capacity.json",
    "source-manifest.json", "row-manifest.json",
)
DIRECT_POLICY_PAYLOADS = ("direct-policy.safetensors",)
CATBOOST_POLICY_PAYLOADS = tuple(
    item for asset in C.ASSETS for item in
    (f"catboost-{asset}.cbm", f"catboost-{asset}.json")
) + ("catboost-config.json", "catboost-pins.json", "catboost-ranker.json")

DETERMINISTIC_TRAINING_LAW = MappingProxyType({
    "schema": "entry-v2-selected-determinism-v1",
    "cublas_workspace_config": ":4096:8",
    "torch_deterministic_algorithms": True,
    "cudnn_benchmark": False,
    "cudnn_deterministic": True,
    "sdpa_math_only": True,
})


def enforce_selected_determinism() -> str:
    if os.environ.get("CUBLAS_WORKSPACE_CONFIG") != _CUBLAS_WORKSPACE_REQUIRED:
        raise WinnerArtifactRefusal("CUBLAS deterministic workspace law differs")
    if (_CUDA_WAS_INITIALIZED_AT_MODULE_IMPORT
            and not _CUBLAS_WAS_VALID_BEFORE_IMPORT):
        raise WinnerArtifactRefusal(
            "CUDA initialized before deterministic CUBLAS bootstrap"
        )
    torch.use_deterministic_algorithms(True)
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
    cuda_backend = getattr(torch.backends, "cuda", None)
    if cuda_backend is not None:
        cuda_backend.enable_flash_sdp(False)
        cuda_backend.enable_mem_efficient_sdp(False)
        cuda_backend.enable_math_sdp(True)
    return _sha(_canonical(dict(DETERMINISTIC_TRAINING_LAW)))


def required_payloads_for_head(kind: str) -> tuple[str, ...]:
    if kind == "direct_neural":
        return BASE_PAYLOADS + DIRECT_POLICY_PAYLOADS
    if kind == "catboost":
        return BASE_PAYLOADS + CATBOOST_POLICY_PAYLOADS
    raise WinnerArtifactRefusal("winner decision head kind is unsupported")


# Compatibility export for callers that only need the invariant payload core.
REQUIRED_PAYLOADS = BASE_PAYLOADS


class WinnerArtifactRefusal(C.EntryV2Refusal):
    pass


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode()
    except (TypeError, ValueError) as exc:
        raise WinnerArtifactRefusal("winner payload is not canonical JSON") from exc


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _is_sha(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        char in "0123456789abcdef" for char in value
    )


def _read_json(raw: bytes, name: str) -> Mapping[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WinnerArtifactRefusal(f"invalid {name} JSON") from exc
    if not isinstance(value, dict) or _canonical(value) != raw:
        raise WinnerArtifactRefusal(f"{name} must be a canonical JSON object")
    return value


def _validate_capacity_document(document: Mapping[str, Any]) -> None:
    try:
        validate_capacity_document(document)
    except C.EntryV2Refusal as exc:
        raise WinnerArtifactRefusal("winner capacity economics do not reconcile") from exc


def _validate_selected_normalizers(
    document: Mapping[str, Any], architecture: Mapping[str, Any],
) -> None:
    horizon = document.get("selected_horizon")
    if not isinstance(horizon, Mapping):
        raise WinnerArtifactRefusal("winner lacks selected horizon normalizer")
    core = dict(horizon); declared = core.pop("receipt_sha256", None)
    try:
        location = tuple(float(value) for value in horizon["location"])
        scale = tuple(float(value) for value in horizon["scale"])
    except (KeyError, TypeError, ValueError) as exc:
        raise WinnerArtifactRefusal(
            "winner selected horizon moments are invalid") from exc
    if (horizon.get("schema") != "entry-v2-selected-horizon-normalizer-v1"
            or tuple(horizon.get("coordinates", ()))
                != SELECTED_HORIZON_COORDINATES
            or horizon.get("target_schema_sha256")
                != SELECTED_HORIZON_SCHEMA_SHA256
            or horizon.get("target_law_sha256")
                != SELECTED_HORIZON_TARGET_LAW_SHA256
            or len(location) != SELECTED_HORIZON_WIDTH
            or len(scale) != SELECTED_HORIZON_WIDTH
            or any(not np.isfinite(value) for value in (*location, *scale))
            or any(value <= 0 for value in scale)
            or not _is_sha(declared) or _sha(_canonical(core)) != declared
            or architecture.get("selected_horizon_normalizer_sha256")
                != declared):
        raise WinnerArtifactRefusal(
            "winner selected horizon normalizer identity differs")


def _validate_selected_output_contract(architecture: Mapping[str, Any]) -> None:
    if (tuple(architecture.get("selected_horizon_coordinates", ()))
            != SELECTED_HORIZON_COORDINATES
            or architecture.get("selected_horizon_schema_sha256")
                != SELECTED_HORIZON_SCHEMA_SHA256
            or architecture.get("selected_horizon_target_law_sha256")
                != SELECTED_HORIZON_TARGET_LAW_SHA256
            or not _is_sha(architecture.get(
                "selected_horizon_normalizer_sha256"))
            or not _is_sha(architecture.get("selected_output_schema_sha256"))
            or architecture.get("ordinal_semantics") != "P(value_bin>=1..4)"):
        raise WinnerArtifactRefusal(
            "winner horizon/ordinal output contract differs")


@dataclass(frozen=True)
class WinnerBundle:
    root: Path
    arm: str
    architecture: Mapping[str, Any]
    objective: Mapping[str, Any]
    model_input_binding: ModelInputBinding
    thresholds: Mapping[str, float]
    files: Mapping[str, str]
    selection: Mapping[str, str]
    adoption_sha256: str
    primary_e3_fold_sha256: str
    source_manifest_sha256: str
    row_manifest_sha256: str
    bundle_sha256: str

    def payload_path(self, name: str) -> Path:
        if name not in self.files:
            raise WinnerArtifactRefusal(f"unreceipted winner payload: {name}")
        return self.root / name


@dataclass(frozen=True)
class WinnerPolicyDecision:
    """Exact deployable E2 action surface, including the entry threshold."""
    raw_model_score: np.ndarray
    mapper_score: np.ndarray
    calibrated_probability: np.ndarray
    enter: np.ndarray


class BundleWinnerPolicyRuntime:
    """Strict, process-independent mapper -> calibrator -> threshold runtime.

    The selected decision learner emits one scalar probability.  The frozen
    binding law expands that scalar to the 128-coordinate binding plane used
    in E2; this is deliberately explicit so a 512/640-width accident cannot
    silently change the adopted policy.
    """

    BINDING_WIDTH = 128

    def __init__(self, bundle: "WinnerBundle") -> None:
        self.determinism_sha256 = enforce_selected_determinism()
        self.bundle = bundle
        self.kind = str(bundle.architecture["decision_head_kind"])
        for name in required_payloads_for_head(self.kind):
            path = bundle.payload_path(name)
            if (path.is_symlink() or not path.is_file()
                    or stat.S_IMODE(path.stat().st_mode) & 0o222
                    or _sha(path.read_bytes()) != bundle.files[name]):
                raise WinnerArtifactRefusal(f"winner payload changed after load: {name}")
        mapper = _read_json(bundle.payload_path("mapper.json").read_bytes(), "mapper")
        calibrator = _read_json(
            bundle.payload_path("calibrator.json").read_bytes(), "calibrator"
        )
        thresholds = _read_json(
            bundle.payload_path("thresholds.json").read_bytes(), "thresholds"
        )
        try:
            self.coef = np.asarray(mapper["coef"], dtype=np.float64)
            self.mapper_intercept = float(mapper["intercept"])
            self.slope = float(calibrator["slope"])
            self.calibrator_intercept = float(calibrator["intercept"])
            self.thresholds = MappingProxyType({
                asset: float(thresholds["thresholds"][asset]) for asset in C.ASSETS
            })
        except (KeyError, TypeError, ValueError) as exc:
            raise WinnerArtifactRefusal("winner decision postprocessor is incomplete") from exc
        if (mapper.get("schema") != "entry-v2-binding-mapper-v1"
                or calibrator.get("schema") != "entry-v2-positive-slope-calibrator-v1"
                or thresholds.get("schema") != "entry-v2-thresholds-v1"
                or self.coef.shape != (self.BINDING_WIDTH,)
                or not np.all(np.isfinite(self.coef))
                or not all(np.isfinite(value) for value in (
                    self.mapper_intercept, self.slope, self.calibrator_intercept))
                or self.slope <= 0.0
                or any(not 0.0 <= value <= 1.0 for value in self.thresholds.values())
                or not _is_sha(mapper.get("fit_ids_sha256"))
                or not _is_sha(calibrator.get("fit_ids_sha256"))):
            raise WinnerArtifactRefusal("winner decision postprocessor law differs")
        self._direct_state: Mapping[str, Tensor] | None = None
        self._cat_models: dict[str, Any] = {}
        if self.kind == "direct_neural":
            try:
                state = load(bundle.payload_path("direct-policy.safetensors").read_bytes())
            except Exception as exc:
                raise WinnerArtifactRefusal("direct policy payload cannot strict-load") from exc
            if (set(state) != {"weight", "bias"} or state["weight"].shape != (1, 512)
                    or state["bias"].shape != (1,)
                    or not all(bool(torch.isfinite(value).all()) for value in state.values())):
                raise WinnerArtifactRefusal("direct policy state schema differs")
            self._direct_state = state
            self.feature_width = 512
        elif self.kind == "catboost":
            try:
                import catboost
                from catboost import CatBoost
            except ImportError as exc:
                raise WinnerArtifactRefusal("pinned CatBoost runtime is unavailable") from exc
            config = _read_json(bundle.payload_path("catboost-config.json").read_bytes(),
                                "catboost config")
            pins = _read_json(bundle.payload_path("catboost-pins.json").read_bytes(),
                              "catboost pins")
            ranker = _read_json(bundle.payload_path("catboost-ranker.json").read_bytes(),
                                "catboost ranker")
            if (config.get("schema") != "entry-v2-catboost-policy-config-v1"
                    or pins.get("schema") != "entry-v2-catboost-runtime-pins-v1"
                    or ranker.get("schema") != "entry-v2-catboost-ranker-v1"
                    or ranker.get("available") is not True
                    or ranker.get("loss_function") != "PairLogit"
                    or config.get("forward_refit_params", {}).get("loss_function")
                        != "PairLogit"
                    or pins.get("catboost_version") != catboost.__version__
                    or pins.get("numpy_version") != np.__version__
                    or pins.get("model_format") != "cbm"
                    or set(pins.get("models", {})) != set(C.ASSETS)):
                raise WinnerArtifactRefusal("CatBoost config/pins/ranker law differs")
            self.feature_width = int(config.get("feature_width", 0))
            if self.feature_width <= 0:
                raise WinnerArtifactRefusal("CatBoost feature width is invalid")
            for asset in C.ASSETS:
                expected = {
                    "cbm_sha256": bundle.files[f"catboost-{asset}.cbm"],
                    "json_sha256": bundle.files[f"catboost-{asset}.json"],
                }
                if pins["models"].get(asset) != expected:
                    raise WinnerArtifactRefusal(f"CatBoost {asset} pins differ")
                model = CatBoost()
                try:
                    model.load_model(str(bundle.payload_path(f"catboost-{asset}.cbm")),
                                     format="cbm")
                except Exception as exc:
                    raise WinnerArtifactRefusal(
                        f"CatBoost {asset} model cannot strict-load"
                    ) from exc
                self._cat_models[asset] = model
        else:
            raise WinnerArtifactRefusal("winner decision head kind is unsupported")

    def raw_model_probability(self, features: np.ndarray, asset: str) -> np.ndarray:
        x = np.asarray(features, dtype=np.float32)
        if (asset not in C.ASSETS or x.ndim != 2 or x.shape[1] != self.feature_width
                or not np.all(np.isfinite(x))):
            raise WinnerArtifactRefusal("winner policy inference input differs")
        if self.kind == "direct_neural":
            assert self._direct_state is not None
            weight = self._direct_state["weight"].detach().cpu().numpy()
            bias = self._direct_state["bias"].detach().cpu().numpy()
            return expit(x.astype(np.float64) @ weight.T + bias).reshape(-1)
        raw = np.asarray(self._cat_models[asset].predict(
            x, prediction_type="RawFormulaVal"), dtype=np.float64).reshape(-1)
        if raw.shape != (len(x),) or not np.all(np.isfinite(raw)):
            raise WinnerArtifactRefusal("winner CatBoost prediction is invalid")
        return expit(raw)

    def decide(self, features: np.ndarray, asset: str) -> WinnerPolicyDecision:
        raw = self.raw_model_probability(features, asset)
        binding = np.repeat(raw[:, None], self.BINDING_WIDTH, axis=1)
        mapper_score = binding @ self.coef + self.mapper_intercept
        probability = expit(self.slope * mapper_score + self.calibrator_intercept)
        if not np.all(np.isfinite(probability)):
            raise WinnerArtifactRefusal("winner calibrated probability is non-finite")
        return WinnerPolicyDecision(raw, mapper_score, probability,
                                    probability >= self.thresholds[asset])

    @property
    def factory_sha256(self) -> str:
        return _sha(_canonical({
            "schema": "entry-v2-bundle-winner-policy-runtime-v1",
            "kind": self.kind,
            "binding_width": self.BINDING_WIDTH,
            "fit_chronology_law": "entry-v2-selected-train-only-policy-v1",
            "action_fit_weight_law": "entry-v2-action-fit-weights-v1",
            "phase_pair_law": "entry-v2-canonical-phase-pairs-v1",
            "determinism_sha256": self.determinism_sha256,
            "payloads": {name: self.bundle.files[name] for name in sorted(
                set(required_payloads_for_head(self.kind))
                & {"direct-policy.safetensors", "mapper.json", "calibrator.json",
                   "thresholds.json", "policy-canary.json",
                   "catboost-config.json", "catboost-pins.json",
                   "catboost-ranker.json", *CATBOOST_POLICY_PAYLOADS}
            )},
        }))


class _ForwardRefitWinnerPolicy:
    """Fold-causal selected action learner with the standard risk auxiliaries."""

    def __init__(self, asset: str, config: Any, binding: ModelInputBinding,
                 runtime: BundleWinnerPolicyRuntime) -> None:
        if asset not in C.ASSETS:
            raise WinnerArtifactRefusal("selected policy must be per asset")
        self.asset, self.runtime = asset, runtime
        self.auxiliary = AssetPolicy(
            asset, PolicyConfig(workers=int(config.workers), seed=int(config.seed)), binding
        )
        self._cat = None
        self.fit_chronology_law = "entry-v2-selected-train-only-policy-v1"
        self.selected_training_evidence: Mapping[str, Any] | None = None

    @staticmethod
    def _binding(raw_probability: np.ndarray) -> np.ndarray:
        return np.repeat(np.asarray(raw_probability, np.float64)[:, None],
                         BundleWinnerPolicyRuntime.BINDING_WIDTH, axis=1)

    def _decision_probability(self, x: np.ndarray) -> np.ndarray:
        value = np.asarray(x, np.float32)
        if self.runtime.kind == "direct_neural":
            if value.ndim != 2 or value.shape[1] != 1 or not np.all(np.isfinite(value)):
                raise WinnerArtifactRefusal("direct forward refit requires neural action logits")
            return expit(value[:, 0].astype(np.float64))
        if self._cat is None:
            raise WinnerArtifactRefusal("CatBoost forward policy is not fitted")
        raw = np.asarray(self._cat.predict(
            value, prediction_type="RawFormulaVal"), np.float64).reshape(-1)
        return expit(raw)

    def fit(self, X: np.ndarray, targets: Mapping[str, np.ndarray]):
        x = np.asarray(X, np.float32)
        action = np.asarray(targets["take_target"], np.float64)
        mask = np.asarray(targets["action_loss_mask"], bool)
        if (action.shape != (len(x),) or mask.shape != action.shape or not mask.any()
                or set(np.unique(action[mask]).tolist()) != {0.0, 1.0}):
            raise WinnerArtifactRefusal("selected forward mapper fit rows differ")
        try:
            candidate_id = np.asarray(targets["candidate_id"]).astype(str)
            asset = np.asarray(targets["asset"]).astype(str)
            day = np.asarray(targets["trading_day"], np.int64)
            phase = np.asarray(targets["phase"]).astype(str)
            decision_ts = np.asarray(targets["decision_ts_ns"], np.int64)
        except (KeyError, TypeError, ValueError) as exc:
            raise WinnerArtifactRefusal(
                "selected forward fit lacks causal row identity"
            ) from exc
        n = len(x)
        if (any(value.shape != (n,) for value in
                (candidate_id, asset, day, phase, decision_ts))
                or len(set(candidate_id.tolist())) != n
                or np.any(asset != self.asset)
                or np.any(phase == "")):
            raise WinnerArtifactRefusal(
                "selected forward causal row identity is invalid"
            )
        from .atlas_probe_model import (
            action_fit_weights, canonical_phase_pair_manifest,
        )
        fit_rows = np.arange(n, dtype=np.int64)
        action_weight, weight_receipt = action_fit_weights(
            asset, day, action, mask, fit_rows, apply_class_weight=True,
        )
        if weight_receipt.optimizer_step_unit != "complete_asset_day_gradient":
            raise WinnerArtifactRefusal(
                "selected mapper did not use complete asset-day gradients"
            )
        self.action_fit_weight_receipt_sha256 = weight_receipt.receipt_sha256
        self.training_candidate_sha256 = C.object_sha256(candidate_id.tolist())
        self._fit_candidate_ids = tuple(candidate_id.tolist())
        self.training_rows = n
        self.phase_pair_manifest_sha256 = None
        self.phase_pair_count = 0
        self.auxiliary.fit(x, targets)
        if self.runtime.kind == "catboost":
            try:
                from catboost import CatBoostRanker, Pool
                config = _read_json(
                    self.runtime.bundle.payload_path("catboost-config.json").read_bytes(),
                    "catboost config",
                )
                params = dict(config["forward_refit_params"])
            except (ImportError, KeyError, TypeError) as exc:
                raise WinnerArtifactRefusal("CatBoost forward-refit config is absent") from exc
            forbidden = {"cat_features", "text_features", "embedding_features"}
            if forbidden & set(params):
                raise WinnerArtifactRefusal("CatBoost forward-refit config changes feature law")
            pair_manifest = canonical_phase_pair_manifest(
                candidate_id, asset, day, phase, decision_ts,
                action, mask, fit_rows,
            )
            if pair_manifest.group_count < 40 or not pair_manifest.pairs:
                raise WinnerArtifactRefusal(
                    "PairLogit forward refit lacks 40 explicit phase-pair groups")
            selected = pair_manifest.indices
            pool = Pool(
                x[selected], label=action[selected].astype(np.float32),
                group_id=pair_manifest.group_ids.tolist(),
                pairs=list(pair_manifest.pairs),
                pairs_weight=pair_manifest.pair_weights.tolist(),
            )
            self._cat = CatBoostRanker(**params).fit(pool)
            self.phase_pair_manifest_sha256 = pair_manifest.receipt_sha256
            self.phase_pair_count = len(pair_manifest.pairs)
        probability = self._decision_probability(x)
        latent = self._binding(probability)
        y = action[mask]
        z = latent[mask]
        weight = np.asarray(action_weight[mask], np.float64)
        if (weight.shape != y.shape or np.any(weight <= 0)
                or not np.all(np.isfinite(weight))):
            raise WinnerArtifactRefusal("selected mapper fit weights are invalid")

        def objective(theta: np.ndarray):
            score = z @ theta[:-1] + theta[-1]
            loss = weight @ (np.logaddexp(0.0, score) - y * score) \
                + .5 * (theta[:-1] @ theta[:-1])
            error = expit(score) - y
            gradient = np.r_[z.T @ (weight * error) + theta[:-1],
                             weight @ error]
            return float(loss), gradient

        result = minimize(
            objective, np.zeros(BundleWinnerPolicyRuntime.BINDING_WIDTH + 1),
            jac=True, method="L-BFGS-B", options={"maxiter": 100, "ftol": 1e-12},
        )
        if not result.success or not np.all(np.isfinite(result.x)):
            raise WinnerArtifactRefusal("selected forward mapper optimization failed")
        self.coef_ = result.x[:-1].copy()
        self.intercept_ = float(result.x[-1])
        self.mapper_parameter_sha256 = C.object_sha256({
            "coef": self.coef_.tolist(), "intercept": self.intercept_,
            "weight_receipt_sha256": self.action_fit_weight_receipt_sha256,
        })
        return self

    def raw_predict(self, X: np.ndarray) -> Mapping[str, np.ndarray]:
        auxiliary = dict(self.auxiliary.raw_predict(X))
        probability = self._decision_probability(np.asarray(X, np.float32))
        auxiliary["winner_mapper_raw"] = (
            self._binding(probability) @ self.coef_ + self.intercept_
        )
        return auxiliary

    def calibrate(self, raw: Mapping[str, np.ndarray],
                  truth: Mapping[str, np.ndarray]):
        score = np.asarray(raw["winner_mapper_raw"], np.float64)
        action = np.asarray(truth["take_target"], np.float64)
        mask = np.asarray(truth["action_loss_mask"], bool)
        score, action = score[mask], action[mask]
        if len(score) < 2 or set(np.unique(action).tolist()) != {0.0, 1.0}:
            raise WinnerArtifactRefusal("selected forward calibration rows differ")
        try:
            calibration_ids = tuple(
                np.asarray(truth["candidate_id"]).astype(str).tolist()
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise WinnerArtifactRefusal(
                "selected forward calibration lacks row identity"
            ) from exc
        if (len(calibration_ids) != len(np.asarray(truth["take_target"]))
                or len(set(calibration_ids)) != len(calibration_ids)
                or set(calibration_ids) & set(getattr(
                    self, "_fit_candidate_ids", ()) )):
            raise WinnerArtifactRefusal(
                "selected calibration rows overlap or are misaligned"
            )
        self.auxiliary.calibrate(raw, truth)

        def objective(theta: np.ndarray) -> float:
            slope = np.logaddexp(0.0, theta[0])
            value = slope * score + theta[1]
            return float(np.logaddexp(0.0, value).sum() - action @ value)

        result = minimize(objective, np.zeros(2), method="L-BFGS-B",
                          options={"maxiter": 100, "ftol": 1e-12})
        if not result.success or not np.all(np.isfinite(result.x)):
            raise WinnerArtifactRefusal("selected forward calibrator optimization failed")
        self.slope_ = float(np.logaddexp(0.0, result.x[0]))
        self.calibrator_intercept_ = float(result.x[1])
        self.calibration_candidate_sha256 = C.object_sha256(
            list(calibration_ids)
        )
        core = {
            "schema": "entry-v2-selected-policy-asset-fit-v1",
            "asset": self.asset,
            "chronology_law": self.fit_chronology_law,
            "optimizer_step_unit": "complete_asset_day_gradient",
            "mapper_weighting": "A013_ACTION_FIT_WEIGHTS",
            "training_rows": int(self.training_rows),
            "calibration_rows": len(calibration_ids),
            "training_candidate_sha256": self.training_candidate_sha256,
            "calibration_candidate_sha256": self.calibration_candidate_sha256,
            "action_fit_weight_receipt_sha256":
                self.action_fit_weight_receipt_sha256,
            "phase_pair_manifest_sha256": self.phase_pair_manifest_sha256,
            "phase_pair_count": int(self.phase_pair_count),
            "mapper_parameter_sha256": self.mapper_parameter_sha256,
        }
        self.selected_training_evidence = MappingProxyType(core)
        return self

    def score_raw(self, raw: Mapping[str, np.ndarray]) -> Mapping[str, np.ndarray]:
        auxiliary_raw = {key: value for key, value in raw.items()
                         if key != "winner_mapper_raw"}
        scored = dict(self.auxiliary.score_raw(auxiliary_raw))
        probability = expit(self.slope_ * np.asarray(
            raw["winner_mapper_raw"], np.float64) + self.calibrator_intercept_)
        scored.update({"action_p": probability, "action_p_lower": probability,
                       "action_p_upper": probability})
        return scored


class BundleWinnerPolicyFactory:
    """Refittable PolicyFactory reconstructed solely from immutable bundle bytes."""

    def __init__(self, bundle: WinnerBundle) -> None:
        self.runtime = BundleWinnerPolicyRuntime(bundle)
        self.fit_chronology_law = "entry-v2-selected-train-only-policy-v1"
        self.policy_factory_sha256 = self.runtime.factory_sha256
        self.__name__ = (
            "entry_v2_selected_direct_policy_factory"
            if self.runtime.kind == "direct_neural"
            else "entry_v2_selected_catboost_policy_factory"
        )

    def __call__(self, asset: str, config: Any,
                 model_input_binding: ModelInputBinding) -> _ForwardRefitWinnerPolicy:
        if model_input_binding != self.runtime.bundle.model_input_binding:
            raise WinnerArtifactRefusal("winner policy factory binding differs")
        return _ForwardRefitWinnerPolicy(
            asset, config, model_input_binding, self.runtime
        )


def load_winner_policy_factory(bundle: WinnerBundle) -> BundleWinnerPolicyFactory:
    """Public restart seam: no diagnostic resource object participates."""
    return BundleWinnerPolicyFactory(bundle)


@dataclass(frozen=True)
class WinnerIntegrationReceipt:
    schema: str
    status: str
    integration_ready: bool
    pending_adoption_sha256: str
    winner_bundle_sha256: str
    frozen_selection: Mapping[str, str]
    load_canary_sha256: str
    resource_receipt_sha256: str
    target_provider_factory_sha256: str
    expanded_transform_law_sha256: str
    policy_factory_sha256: str
    integration_sha256: str


class SelectedAtlasTargetProvider(Protocol):
    """Fold-causal target plane; implementations are keyed by candidate ID."""

    objective_sha256: str
    row_manifest_sha256: str
    atlas_aggregate_sha256: str
    materializer_callable_sha256: str
    fit_context_sha256: str
    transform_provenance_sha256: str
    ipcw_provenance_sha256: str
    registry_objective_sha256: str
    target_control_sha256: str
    fit_day_manifest_sha256: str
    target_candidate_manifest_sha256: str
    shuffle_receipt: Mapping[str, Any]

    def target_for(self, candidate_ids: Sequence[str]) -> ProbeTarget: ...


@dataclass(frozen=True)
class ExpandedEventView:
    continuous: Tensor
    categorical: Tensor
    schema_sha256: str
    transform_law_sha256: str
    base_binding_sha256: str
    normalization: str


class ExpandedEventTransform(Protocol):
    schema_sha256: str
    transform_law_sha256: str
    base_binding_sha256: str
    input_contract_sha256: str
    category_sizes: tuple[int, ...]
    normalization: str

    def transform(self, batch: Any) -> ExpandedEventView: ...


class CompactWinnerResourceProvider(Protocol):
    """Concrete one-open handoff supplied by the production resource stage."""
    event_transform: ExpandedEventTransform
    policy_kind: str
    context_corpus: Any
    receipt_sha256: str
    target_provider_factory_sha256: str
    policy_factory_sha256: str
    mapper_sha256: str
    calibrator_sha256: str
    thresholds_sha256: str
    capacity_authority_sha256: str
    ownership_transferred: bool

    def compact_atlas_handoff(self, fold: Any, control_name: str,
                              shuffle_seed: int | None) -> Any: ...


@dataclass(frozen=True)
class FrozenAtlasTargetStore:
    """Compact selected-objective plane materialized during the one-open pass.

    It contains no raw events and performs no pack opens.  Candidate lookup is
    vectorized against a sorted string index rather than a Python object per
    candidate.
    """

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
    target_control_sha256: str
    fit_day_manifest_sha256: str
    target_candidate_manifest_sha256: str
    shuffle_receipt: Mapping[str, Any]

    def __post_init__(self) -> None:
        ids = np.asarray(self.candidate_ids, str)
        if (any(not _is_sha(value) for value in (
                self.objective_sha256, self.row_manifest_sha256,
                self.atlas_aggregate_sha256, self.materializer_callable_sha256,
                self.fit_context_sha256, self.transform_provenance_sha256,
                self.ipcw_provenance_sha256, self.registry_objective_sha256,
                self.target_control_sha256, self.fit_day_manifest_sha256,
                self.target_candidate_manifest_sha256))
                or ids.ndim != 1 or len(ids) != len(self.target.values)
                or len(np.unique(ids)) != len(ids)
                or (len(ids) > 1 and bool(np.any(ids[1:] <= ids[:-1])))):
            raise WinnerArtifactRefusal("selected target store identity/order differs")
        receipt = self.shuffle_receipt
        if (not isinstance(receipt, Mapping)
                or receipt.get("schema") != "entry-v2-selected-target-control-v2"
                or receipt.get("target_control_sha256") != self.target_control_sha256
                or receipt.get("target_candidate_manifest_sha256")
                    != self.target_candidate_manifest_sha256
                or receipt.get("marginals_preserved") is not True):
            raise WinnerArtifactRefusal("selected target control receipt differs")

    @classmethod
    def from_handoff(cls, handoff: Any) -> "FrozenAtlasTargetStore":
        required = (
            "objective_sha256", "row_manifest_sha256", "candidate_ids", "target",
            "atlas_aggregate_sha256", "materializer_callable_sha256",
            "fit_context_sha256", "transform_provenance_sha256",
            "ipcw_provenance_sha256", "registry_objective_sha256",
            "target_control_sha256", "fit_day_manifest_sha256",
            "target_candidate_manifest_sha256", "shuffle_receipt",
        )
        if any(not hasattr(handoff, name) for name in required):
            raise WinnerArtifactRefusal("compact atlas handoff is incomplete")
        values = tuple(getattr(handoff, name) for name in required)
        return cls(*values)

    def target_for(self, candidate_ids: Sequence[str]) -> ProbeTarget:
        requested = np.asarray(tuple(candidate_ids), str)
        positions = np.searchsorted(self.candidate_ids, requested)
        if (len(positions) != len(requested) or np.any(positions >= len(self.candidate_ids))
                or np.any(self.candidate_ids[positions] != requested)):
            raise WinnerArtifactRefusal("selected target store lacks a requested candidate")
        t = self.target
        def take(value: np.ndarray) -> np.ndarray:
            result = np.ascontiguousarray(np.asarray(value)[positions])
            result.setflags(write=False)
            return result
        return ProbeTarget(
            t.probe_id, t.state, take(t.values), take(t.coordinate_mask),
            take(t.coordinate_at_risk), take(t.coordinate_censor),
            take(t.validity_mask), take(t.at_risk_mask), take(t.censor_mask),
            take(t.fit_weight), take(t.group_id), take(t.group_size),
            t.output_width, t.output_layout, t.direction, t.schema_sha256,
            t.transform_provenance_sha256, t.prediction_width,
            t.prediction_layout,
        )

class FrozenSelectedObjective(nn.Module):
    """Selected 192-coordinate atlas head plus its exact registered loss."""

    def __init__(self, representation_width: int, registry_id: str,
                 objective_sha256: str) -> None:
        super().__init__()
        matches = tuple(spec for spec in PROBE_REGISTRY if spec.probe_id == registry_id)
        if registry_id == "A0_CURRENT_GROUPING":
            self.spec = None
        elif len(matches) != 1:
            raise WinnerArtifactRefusal("selected atlas registry ID is unknown")
        else:
            self.spec = matches[0]
        self.objective_sha256 = str(objective_sha256)
        self.projection = nn.Linear(int(representation_width), PADDED_OUTPUT_WIDTH)

    def loss(self, state: Tensor, candidate_ids: Sequence[str],
             provider: SelectedAtlasTargetProvider, *,
             use_fit_weight: bool) -> Tensor:
        if (provider.objective_sha256 != self.objective_sha256
                or not _is_sha(provider.row_manifest_sha256)):
            raise WinnerArtifactRefusal("atlas target provider differs from winner")
        if self.spec is None:
            raise WinnerArtifactRefusal("C0 A0 has no atlas target loss")
        target = provider.target_for(candidate_ids)
        if target.probe_id != self.spec.probe_id:
            raise WinnerArtifactRefusal("atlas provider returned another objective")
        validity = np.asarray(target.validity_mask, bool)
        coordinates = np.asarray(target.coordinate_mask, bool)
        weights = np.asarray(target.fit_weight, np.float64)
        if (not validity.any() or np.any(coordinates[~validity])
                or np.any(weights[~validity] != 0)
                or np.any(weights[validity] < 0)):
            raise WinnerArtifactRefusal(
                "selected objective target/mask/fit-weight law differs"
            )
        return loss_for_probe(
            self.spec, self.projection(state), target,
            use_fit_weight=use_fit_weight,
        )


class SelectedWinnerLearningSystem(nn.Module):
    """Adapter from the selected neural contract to the fold trainer output.

    Exact clocks and the static bypass are supplied by ``EntrySessionBatch``;
    this class never reconstructs either from normalized floating tensors.
    """

    def __init__(self, model: NeuralSufficiencyModel,
                 objective: FrozenSelectedObjective, *, arm: str,
                 target_provider: SelectedAtlasTargetProvider | None,
                 event_transform: ExpandedEventTransform) -> None:
        super().__init__()
        if arm not in CANONICAL_ARMS:
            raise WinnerArtifactRefusal("selected learning system arm is invalid")
        if (arm != "C0" and (target_provider is None
                or target_provider.objective_sha256 != objective.objective_sha256)):
            raise WinnerArtifactRefusal("selected target provider objective differs")
        self.model = model
        self.objective = objective
        self.arm = arm
        self.target_provider = target_provider
        self.event_transform = event_transform
        # Compatibility surface used by fit_encoder's schema checks.
        self.encoder = model.encoder
        self.n_phase_classes = model.head.n_phases
        n_continuous = int(model.encoder.n_event_continuous)
        category_sizes = tuple(int(x) for x in model.encoder.event_category_sizes)
        self.survival_continuous = nn.Linear(4 * 512, n_continuous)
        self.survival_categories = nn.ModuleList(
            nn.Linear(4 * 512, size) for size in category_sizes
        )

    @property
    def phase_head(self) -> nn.Linear:
        return self.model.head.phase_head

    def forward(self, batch: Any) -> Any:
        # Import lazily to keep the artifact/model layer free of a train-time
        # import cycle.
        from .train import LearningOutput
        if batch.receive_clock_ns is None:
            raise WinnerArtifactRefusal("selected winner requires exact receive clocks")
        use_static = self.arm in ("L1", "M1")
        if use_static and batch.static_features is None:
            raise WinnerArtifactRefusal("selected winner requires normalized lossless static bypass")
        static = None if not use_static else batch.static_features
        decisions = torch.tensor([row.decision_ts_ns for row in batch.examples],
                                 dtype=torch.int64, device=batch.candidate_cutoffs.device)
        output = self.model(
            event_continuous=batch.event_continuous,
            event_categorical=batch.event_categorical,
            receive_clock_ns=batch.receive_clock_ns,
            candidate_cutoffs=batch.candidate_cutoffs,
            candidate_decision_ts_ns=decisions,
            candidate_features=batch.candidate_features,
            context_values=batch.context_values,
            context_type_ids=batch.context_type_ids,
            context_valid=batch.context_valid,
            asset_idx=C.ASSET_INDEX[batch.asset], static_features=static,
        )
        partition = partition_event_blocks(
            int(batch.candidate_cutoffs.max()) if batch.rows else 0,
            batch.candidate_cutoffs, getattr(self.encoder, "block_size", 256),
        )
        core = EntryModelOutput(
            # Direct-head adoption exposes the trained action logit to its
            # identity/calibration policy adapter.  CatBoost adoption exposes
            # the identical frozen 512 representation used by selection.
            embedding=(output.action_logit[:, None]
                       if self.selected_decision_head_kind == "direct_neural"
                       else output.decision_state),
            prefix_state=output.raw_memory.mean(1),
            context_state=output.context_token[:, 0],
            value_bin_logits=output.value_distribution_logits,
            value_quantiles=output.value_quantiles,
            expected_value=output.expected_value,
            top3_logit=output.top3_logit,
            mae_quantiles=output.mae_quantiles,
            wall_logit=output.wall_logit,
            take_logit=output.action_logit,
            partition=partition,
        )
        learned = LearningOutput(
            core=core, horizon_value=output.horizon_values,
            phase_logits=output.phase_logits, rank_value=output.rank_score,
            mfe_quantiles=output.mfe_quantiles,
            time_to_peak_value=output.time_to_peak,
            selected_state=output.decision_state,
            selected_raw_memory=output.raw_memory,
            selected_ordinal_logits=output.ordinal_logits,
        )
        if learned.horizon_value.shape != (batch.rows, SELECTED_HORIZON_WIDTH):
            raise WinnerArtifactRefusal(
                "selected winner did not expose all six horizon coordinates")
        return learned

    def selected_objective_loss(self, output: Any,
                                candidate_ids: Sequence[str], *,
                                use_fit_weight: bool) -> Tensor:
        return self.objective.loss(output.selected_state, candidate_ids,
                                   self.target_provider,
                                   use_fit_weight=use_fit_weight)

    def field_survival_loss(self, output: Any, batch: Any) -> Tensor:
        memory = output.selected_raw_memory.flatten(1)
        cutoffs = batch.candidate_cutoffs.long()
        valid = cutoffs > 0
        if not bool(valid.any()):
            raise WinnerArtifactRefusal("field-survival batch has no visible last row")
        rows = (cutoffs[valid] - 1).to(batch.event_continuous.device)
        continuous = batch.event_continuous[rows]
        categorical = batch.event_categorical[rows].long()
        prediction = self.survival_continuous(memory[valid])
        loss = torch.nn.functional.smooth_l1_loss(prediction, continuous)
        for index, head in enumerate(self.survival_categories):
            loss = loss + torch.nn.functional.cross_entropy(
                head(memory[valid]), categorical[:, index]
            )
        return loss


def _arm_payload(arm: str, architecture: Mapping[str, Any],
                 encoder_sha256: str, head_sha256: str,
                 objective_head_sha256: str) -> bytes:
    return _canonical({
        "schema": "entry-v2-selected-neural-arm-v1", "arm": arm,
        "architecture": dict(architecture),
        "encoder_sha256": encoder_sha256, "head_sha256": head_sha256,
        "objective_head_sha256": objective_head_sha256,
    })


def publish_winner_bundle(
    path: str | os.PathLike[str], *, adoption_receipt_path: str | os.PathLike[str],
    arm: str, architecture: Mapping[str, Any], objective: Mapping[str, Any],
    model_input_binding: ModelInputBinding, payloads: Mapping[str, bytes],
    primary_e3_fold_sha256: str,
) -> WinnerBundle:
    """Atomically publish the exact selected model and policy payloads."""

    adoption = load_winner_adoption(adoption_receipt_path)
    if not _is_sha(primary_e3_fold_sha256):
        raise WinnerArtifactRefusal("winner lacks the standard primary E3 fold identity")
    if arm not in CANONICAL_ARMS:
        raise WinnerArtifactRefusal("winner arm is not canonical")
    _validate_selected_output_contract(architecture)
    model_input_binding.validate()
    required_payloads = required_payloads_for_head(
        str(architecture.get("decision_head_kind"))
    )
    missing = set(required_payloads) - set(payloads)
    extra = set(payloads) - set(required_payloads)
    if missing or extra:
        raise WinnerArtifactRefusal(
            f"winner payload set differs: missing={sorted(missing)}, extra={sorted(extra)}"
        )
    supplied = dict(payloads)
    encoder_sha, head_sha = _sha(supplied["encoder.safetensors"]), _sha(supplied["head.safetensors"])
    objective_head_sha = _sha(supplied["objective-head.safetensors"])
    expected_arm = _arm_payload(arm, architecture, encoder_sha, head_sha,
                                objective_head_sha)
    if supplied["arm.json"] != expected_arm:
        raise WinnerArtifactRefusal("arm payload does not bind architecture/checkpoints")
    if supplied["objective.json"] != _canonical(dict(objective)):
        raise WinnerArtifactRefusal("objective payload differs from declared objective")
    objective_id = objective.get("registry_id")
    selected_specs = tuple(spec for spec in PROBE_REGISTRY if spec.probe_id == objective_id)
    a0 = arm == "C0" and objective_id == "A0_CURRENT_GROUPING"
    if (objective.get("schema") != "entry-v2-selected-atlas-objective-v1"
            or any(not _is_sha(objective.get(key)) for key in (
                "axes_sha256", "transform_provenance_sha256",
                "ipcw_provenance_sha256", "loss_callable_sha256",
                "atlas_aggregate_sha256", "materializer_callable_sha256",
                "fit_context_sha256", "target_row_manifest_sha256",
                "registry_objective_sha256",
            )) or (not a0 and len(selected_specs) != 1)
            or (not a0 and objective.get("materializer_id") != selected_specs[0].materializer_id)
            or (not a0 and objective.get("loss_id") != selected_specs[0].loss_id)
            or (not a0 and objective.get("action_mapper_id") != selected_specs[0].action_mapper_id)
            or (a0 and objective.get("loss_id") != "A0.current_grouping")):
        raise WinnerArtifactRefusal("selected objective is not an executable registry row")
    selection = dict(adoption.frozen_selection)
    actual_selection = {
        "selected_arm_sha256": _sha(supplied["arm.json"]),
        "selected_objective_sha256": _sha(supplied["objective.json"]),
        "calibrator_sha256": _sha(supplied["calibrator.json"]),
        "thresholds_sha256": _sha(supplied["thresholds.json"]),
        "capacity_authority_sha256": _sha(supplied["capacity.json"]),
    }
    if actual_selection != selection:
        raise WinnerArtifactRefusal("winner bytes differ from E2/E3 frozen selection")
    thresholds_doc = _read_json(supplied["thresholds.json"], "thresholds")
    _validate_selected_normalizers(
        _read_json(supplied["normalizers.json"], "normalizers"), architecture,
    )
    _validate_capacity_document(_read_json(supplied["capacity.json"], "capacity"))
    try:
        thresholds = {asset: float(thresholds_doc["thresholds"][asset]) for asset in C.ASSETS}
    except (KeyError, TypeError, ValueError) as exc:
        raise WinnerArtifactRefusal("winner thresholds do not cover all assets") from exc
    if any(not 0.0 <= value <= 1.0 for value in thresholds.values()):
        raise WinnerArtifactRefusal("winner threshold is outside [0,1]")
    source_doc = _read_json(supplied["source-manifest.json"], "source manifest")
    row_doc = _read_json(supplied["row-manifest.json"], "row manifest")
    source_hash, row_hash = _sha(supplied["source-manifest.json"]), _sha(supplied["row-manifest.json"])
    if source_doc.get("schema") is None or row_doc.get("schema") is None:
        raise WinnerArtifactRefusal("winner source/row manifests lack schemas")
    if (row_doc.get("target_row_manifest_sha256")
            != objective["target_row_manifest_sha256"]):
        raise WinnerArtifactRefusal("winner row manifest differs from selected target plane")
    file_hashes = {name: _sha(supplied[name]) for name in required_payloads}
    core = {
        "schema": SCHEMA, "status": "READY", "arm": arm,
        "adoption_sha256": adoption.adoption_sha256,
        "primary_e3_fold_sha256": primary_e3_fold_sha256,
        "selection": selection, "files": file_hashes,
        "model_input_binding": model_input_binding.as_dict(),
        "source_manifest_sha256": source_hash, "row_manifest_sha256": row_hash,
    }
    bundle_hash = _sha(_canonical(core))
    manifest = _canonical({**core, "bundle_sha256": bundle_hash})
    target = C.assert_workspace_output(path)
    C.guard_payload(target)
    if target.exists():
        return load_winner_bundle(target, expected_adoption_sha256=adoption.adoption_sha256)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.", dir=target.parent))
    try:
        for name, raw in supplied.items():
            (temporary / name).write_bytes(raw); os.chmod(temporary / name, 0o444)
        (temporary / MANIFEST).write_bytes(manifest); os.chmod(temporary / MANIFEST, 0o444)
        os.chmod(temporary, 0o555)
        os.rename(temporary, target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return load_winner_bundle(target, expected_adoption_sha256=adoption.adoption_sha256)


def load_winner_bundle(path: str | os.PathLike[str], *,
                       expected_adoption_sha256: str | None = None,
                       expected_binding: ModelInputBinding | None = None) -> WinnerBundle:
    root = Path(path)
    if (root.is_symlink() or not root.is_dir()
            or stat.S_IMODE(root.stat().st_mode) & 0o222):
        raise WinnerArtifactRefusal("winner bundle is absent or a symlink")
    names = {item.name for item in root.iterdir()}
    if "arm.json" not in names:
        raise WinnerArtifactRefusal("winner bundle lacks its arm payload")
    arm_probe = _read_json((root / "arm.json").read_bytes(), "arm")
    required_payloads = required_payloads_for_head(
        str(dict(arm_probe.get("architecture", {})).get("decision_head_kind"))
    )
    if names != set(required_payloads) | {MANIFEST}:
        raise WinnerArtifactRefusal("winner bundle contains missing/unreceipted files")
    raw_manifest = (root / MANIFEST).read_bytes()
    manifest = _read_json(raw_manifest, "winner manifest")
    try:
        core = dict(manifest); declared = core.pop("bundle_sha256")
        binding = ModelInputBinding.from_mapping(core["model_input_binding"])
        files = dict(core["files"]); selection = dict(core["selection"])
    except (KeyError, TypeError, C.EntryV2Refusal) as exc:
        raise WinnerArtifactRefusal("winner manifest is incomplete") from exc
    if (core.get("schema") != SCHEMA or core.get("status") != "READY"
            or core.get("arm") not in CANONICAL_ARMS
            or not _is_sha(core.get("primary_e3_fold_sha256"))
            or _sha(_canonical(core)) != declared
            or set(files) != set(required_payloads)
            or any(not _is_sha(value) for value in files.values())):
        raise WinnerArtifactRefusal("winner manifest identity differs")
    for name, digest in files.items():
        item = root / name
        if item.is_symlink() or not item.is_file() or stat.S_IMODE(item.stat().st_mode) & 0o222:
            raise WinnerArtifactRefusal(f"mutable/missing winner payload: {name}")
        if _sha(item.read_bytes()) != digest:
            raise WinnerArtifactRefusal(f"winner payload changed: {name}")
        if name.endswith(".json"):
            if name.startswith("catboost-") and name.split("-")[-1][:-5] in C.ASSETS:
                try:
                    document = json.loads(item.read_text())
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise WinnerArtifactRefusal(f"invalid native CatBoost JSON: {name}") from exc
                if not isinstance(document, dict) or not document:
                    raise WinnerArtifactRefusal(f"empty native CatBoost JSON: {name}")
            else:
                document = _read_json(item.read_bytes(), name)
                if not isinstance(document.get("schema"), str):
                    raise WinnerArtifactRefusal(f"winner JSON lacks schema: {name}")
    if expected_adoption_sha256 is not None and core["adoption_sha256"] != expected_adoption_sha256:
        raise WinnerArtifactRefusal("winner bundle belongs to another adoption")
    if expected_binding is not None and binding != expected_binding:
        raise WinnerArtifactRefusal("winner bundle model-input binding differs")
    arm_doc = _read_json((root / "arm.json").read_bytes(), "arm")
    _validate_selected_output_contract(dict(arm_doc.get("architecture", {})))
    objective = _read_json((root / "objective.json").read_bytes(), "objective")
    _validate_selected_normalizers(_read_json(
        (root / "normalizers.json").read_bytes(), "normalizers"
    ), dict(arm_doc["architecture"]))
    thresholds_doc = _read_json((root / "thresholds.json").read_bytes(), "thresholds")
    _validate_capacity_document(_read_json(
        (root / "capacity.json").read_bytes(), "capacity"
    ))
    row_doc = _read_json((root / "row-manifest.json").read_bytes(), "row manifest")
    actual_selection = {
        "selected_arm_sha256": files["arm.json"],
        "selected_objective_sha256": files["objective.json"],
        "calibrator_sha256": files["calibrator.json"],
        "thresholds_sha256": files["thresholds.json"],
        "capacity_authority_sha256": files["capacity.json"],
    }
    if selection != actual_selection or arm_doc.get("arm") != core["arm"]:
        raise WinnerArtifactRefusal("winner selection is receipt-only or mismatched")
    if (not _is_sha(objective.get("target_row_manifest_sha256"))
            or row_doc.get("target_row_manifest_sha256")
                != objective["target_row_manifest_sha256"]):
        raise WinnerArtifactRefusal("winner target row manifest binding differs")
    thresholds = {asset: float(thresholds_doc["thresholds"][asset]) for asset in C.ASSETS}
    return WinnerBundle(
        root.resolve(), str(core["arm"]), MappingProxyType(dict(arm_doc["architecture"])),
        MappingProxyType(dict(objective)), binding, MappingProxyType(thresholds),
        MappingProxyType(files), MappingProxyType(selection), str(core["adoption_sha256"]),
        str(core["primary_e3_fold_sha256"]),
        str(core["source_manifest_sha256"]), str(core["row_manifest_sha256"]), str(declared),
    )


def load_winner_policy_canary(bundle: WinnerBundle) -> str:
    """Strict-load and execute the complete adopted decision surface."""
    runtime = BundleWinnerPolicyRuntime(bundle)
    kind = runtime.kind
    if kind == "direct_neural":
        assert runtime._direct_state is not None
        try:
            head_state = load_file(str(bundle.payload_path("head.safetensors")),
                                   device="cpu")
        except Exception as exc:
            raise WinnerArtifactRefusal("direct policy head cannot strict-load") from exc
        if ("action_head.weight" not in head_state or "action_head.bias" not in head_state
                or not torch.equal(runtime._direct_state["weight"],
                                   head_state["action_head.weight"])
                or not torch.equal(runtime._direct_state["bias"],
                                   head_state["action_head.bias"])):
            raise WinnerArtifactRefusal(
                "direct deployable policy bytes differ from selected neural head"
            )
    if kind == "catboost":
        try:
            from catboost import CatBoost
        except ImportError as exc:  # pragma: no cover - checked by runtime
            raise WinnerArtifactRefusal("pinned CatBoost runtime is unavailable") from exc
        for asset in C.ASSETS:
            json_model = CatBoost()
            try:
                json_model.load_model(
                    str(bundle.payload_path(f"catboost-{asset}.json")),
                    format="json",
                )
                json_raw = np.asarray(json_model.predict(
                    np.zeros((1, runtime.feature_width), np.float32),
                    prediction_type="RawFormulaVal"), np.float64).reshape(-1)
            except Exception as exc:
                raise WinnerArtifactRefusal(f"CatBoost {asset} JSON cannot predict") from exc
            cbm_raw = np.asarray(runtime._cat_models[asset].predict(
                np.zeros((1, runtime.feature_width), np.float32),
                prediction_type="RawFormulaVal"), np.float64).reshape(-1)
            if (json_raw.shape != (1,) or not np.array_equal(cbm_raw, json_raw)):
                raise WinnerArtifactRefusal(f"CatBoost {asset} canary is invalid")
    decisions = {
        asset: runtime.decide(
            np.zeros((1, runtime.feature_width), np.float32), asset
        ) for asset in C.ASSETS
    }
    actual = {
        "schema": "entry-v2-winner-policy-canary-v1",
        "input": "ZERO_FEATURE_ROW",
        "per_asset": {asset: {
            "raw_model_score": float(decisions[asset].raw_model_score[0]),
            "mapper_score": float(decisions[asset].mapper_score[0]),
            "calibrated_probability": float(
                decisions[asset].calibrated_probability[0]),
            "threshold": float(runtime.thresholds[asset]),
            "enter": bool(decisions[asset].enter[0]),
        } for asset in C.ASSETS},
    }
    expected = _read_json(
        bundle.payload_path("policy-canary.json").read_bytes(), "policy canary"
    )
    if expected != actual:
        raise WinnerArtifactRefusal("bundle inference differs from frozen E2 canary")
    return _sha(_canonical({
        "kind": kind,
        "factory_sha256": runtime.factory_sha256,
        "canary": actual,
        "files": dict(bundle.files),
    }))


def build_selected_winner_model(bundle: WinnerBundle) -> tuple[NeuralSufficiencyModel, FrozenSelectedObjective]:
    """Reconstruct and strict-load the selected C0/C1/L0/L1/M1 model."""
    enforce_selected_determinism()
    a = bundle.architecture
    required = ("event_continuous_fields", "event_categorical_fields",
                "event_category_sizes", "conversion_law_sha256",
                "candidate_features", "context_continuous", "context_types",
                "static_bypass", "n_value_bins", "n_phases",
                "decision_head_kind", "shared_head_initial_sha256",
                "no_parameter_alias_receipt_sha256",
                "branch_identity_receipt_sha256", "input_contract_sha256",
                "expanded_schema_sha256", "expanded_transform_law_sha256",
                "expanded_transform_output", "branch_parameters_nonaliased",
                "shared_head_initial_identity")
    required = required + (
        "selected_horizon_coordinates", "selected_horizon_schema_sha256",
        "selected_horizon_target_law_sha256",
        "selected_horizon_normalizer_sha256", "selected_output_schema_sha256",
        "ordinal_semantics",
    )
    if any(key not in a for key in required):
        raise WinnerArtifactRefusal("winner architecture is incomplete")
    schema = EventFieldSchema(tuple(a["event_continuous_fields"]),
                              tuple(a["event_categorical_fields"]),
                              tuple(int(x) for x in a["event_category_sizes"]),
                              str(a["conversion_law_sha256"]), False)
    if (a["input_contract_sha256"]
            != bundle.model_input_binding.input_contract_sha256
            or any(not _is_sha(a[key]) for key in (
                "expanded_schema_sha256", "expanded_transform_law_sha256"))
            or schema.sha256 != a["expanded_schema_sha256"]):
        raise WinnerArtifactRefusal("winner expanded view is not layered on base binding")
    static_expected = bundle.arm in ("L1", "M1")
    if bool(a["static_bypass"]) != static_expected:
        raise WinnerArtifactRefusal("winner static-bypass law differs from arm")
    if a["decision_head_kind"] not in ("direct_neural", "catboost"):
        raise WinnerArtifactRefusal("winner decision head kind is unsupported")
    if (tuple(a["selected_horizon_coordinates"])
            != SELECTED_HORIZON_COORDINATES
            or tuple(DEFAULT_HORIZONS) != SELECTED_HORIZON_MODEL_COORDINATES
            or a["selected_horizon_schema_sha256"]
                != SELECTED_HORIZON_SCHEMA_SHA256
            or a["selected_horizon_target_law_sha256"]
                != SELECTED_HORIZON_TARGET_LAW_SHA256
            or not _is_sha(a["selected_horizon_normalizer_sha256"])
            or not _is_sha(a["selected_output_schema_sha256"])
            or a["ordinal_semantics"] != "P(value_bin>=1..4)"):
        raise WinnerArtifactRefusal(
            "winner horizon/ordinal output contract differs")
    if any(not _is_sha(a[key]) for key in (
            "shared_head_initial_sha256", "no_parameter_alias_receipt_sha256",
            "branch_identity_receipt_sha256")):
        raise WinnerArtifactRefusal("winner branch/shared-head identity is unreceipted")
    if (a["branch_parameters_nonaliased"] is not True
            or a["shared_head_initial_identity"] is not True):
        raise WinnerArtifactRefusal("winner branch aliases or shared-head initialization differs")
    checkpoint_key = ("current_pointwise_checkpoint_sha256"
                      if bundle.arm in ("C0", "C1") else
                      "lit_raw_checkpoint_sha256" if bundle.arm in ("L0", "L1")
                      else "m1_pointwise_checkpoint_sha256")
    if not _is_sha(a.get(checkpoint_key)):
        raise WinnerArtifactRefusal("winner branch source checkpoint is unreceipted")
    if bundle.arm in ("C0", "C1") and (
            a.get("c0_pointwise_checkpoint_sha256")
            != a.get("c1_pointwise_checkpoint_sha256")
            or a.get("c0_pointwise_checkpoint_sha256") != a[checkpoint_key]):
        raise WinnerArtifactRefusal("C0/C1 pointwise checkpoint identity differs")
    if bundle.arm in ("L0", "L1") and (
            a.get("l0_raw_checkpoint_sha256") != a.get("l1_raw_checkpoint_sha256")
            or a.get("l0_raw_checkpoint_sha256") != a[checkpoint_key]):
        raise WinnerArtifactRefusal("L0/L1 raw checkpoint identity differs")
    if bundle.arm in ("C0", "C1"):
        current = FullPrefixEntryModel(
            len(schema.continuous_fields), int(a["candidate_features"]),
            int(a["context_continuous"]), int(a["context_types"]),
            event_category_sizes=schema.category_sizes,
            n_value_bins=int(a["n_value_bins"]),
        )
        encoder: nn.Module = CurrentEncoderAdapter(current, schema)
    elif bundle.arm in ("L0", "L1"):
        encoder = LiTShortMemoryEncoder(len(schema.continuous_fields), schema.category_sizes,
                                        field_schema=schema)
    else:
        encoder = CausalMultiresolutionEncoder(len(schema.continuous_fields),
                                               schema.category_sizes, field_schema=schema)
    head = SharedCandidateDecisionHead(
        int(a["candidate_features"]), int(a["context_continuous"]),
        int(a["context_types"]), n_value_bins=int(a["n_value_bins"]),
        n_phases=int(a["n_phases"]),
    )
    if head.output_schema_sha256 != a["selected_output_schema_sha256"]:
        raise WinnerArtifactRefusal("winner selected output schema differs")
    try:
        encoder.load_state_dict(load_file(str(bundle.payload_path("encoder.safetensors")), device="cpu"), strict=True)
        head.load_state_dict(load_file(str(bundle.payload_path("head.safetensors")), device="cpu"), strict=True)
    except Exception as exc:
        raise WinnerArtifactRefusal("winner checkpoint does not strict-load") from exc
    model = NeuralSufficiencyModel(encoder, head)
    objective = FrozenSelectedObjective(512, str(bundle.objective["registry_id"]),
                                        bundle.selection["selected_objective_sha256"])
    try:
        objective.load_state_dict(load_file(
            str(bundle.payload_path("objective-head.safetensors")), device="cpu"
        ), strict=True)
    except Exception as exc:
        raise WinnerArtifactRefusal("winner objective checkpoint does not strict-load") from exc
    return model, objective


def build_selected_winner_system(
    bundle: WinnerBundle, target_provider: SelectedAtlasTargetProvider | None,
    event_transform: ExpandedEventTransform,
) -> SelectedWinnerLearningSystem:
    if bundle.arm != "C0" and (target_provider is None or
            target_provider.objective_sha256 != bundle.selection["selected_objective_sha256"]):
        raise WinnerArtifactRefusal("target provider is not bound to selected objective")
    if bundle.arm != "C0":
        assert target_provider is not None
        for key in ("materializer_callable_sha256",
                    "transform_provenance_sha256",
                    "ipcw_provenance_sha256", "registry_objective_sha256"):
            if getattr(target_provider, key) != bundle.objective[key]:
                raise WinnerArtifactRefusal(f"target provider {key} differs from winner")
    if (event_transform.schema_sha256
            != bundle.architecture["expanded_schema_sha256"]
            or event_transform.transform_law_sha256
            != bundle.architecture["expanded_transform_law_sha256"]
            or event_transform.input_contract_sha256
            != bundle.architecture["input_contract_sha256"]
            or event_transform.normalization != "UNNORMALIZED_CANONICAL"
            or bundle.architecture.get("expanded_transform_output")
                != "UNNORMALIZED_CANONICAL"):
        raise WinnerArtifactRefusal("expanded event transform differs from winner")
    model, objective = build_selected_winner_model(bundle)
    system = SelectedWinnerLearningSystem(
        model, objective, arm=bundle.arm, target_provider=target_provider,
        event_transform=event_transform,
    )
    system.winner_bundle_sha256 = bundle.bundle_sha256
    system.e2_frozen_selection_sha256 = C.object_sha256(dict(bundle.selection))
    system.selected_objective_sha256 = bundle.selection["selected_objective_sha256"]
    system.selected_target_row_manifest_sha256 = (
        bundle.row_manifest_sha256 if target_provider is None
        else target_provider.row_manifest_sha256
    )
    system.selected_target_control_sha256 = (
        _sha(_canonical({"schema": "entry-v2-selected-target-control-v1",
                         "row_manifest_sha256": bundle.objective[
                             "target_row_manifest_sha256"],
                         "control": "PROPHET"}))
        if target_provider is None else target_provider.target_control_sha256
    )
    system.selected_target_shuffle_receipt = (
        None if target_provider is None else dict(target_provider.shuffle_receipt)
    )
    system.selected_fit_day_manifest_sha256 = (
        None if target_provider is None else target_provider.fit_day_manifest_sha256
    )
    system.selected_target_candidate_manifest_sha256 = (
        None if target_provider is None
        else target_provider.target_candidate_manifest_sha256
    )
    system.selected_fit_context_sha256 = (
        None if target_provider is None else target_provider.fit_context_sha256
    )
    system.selected_decision_head_kind = str(bundle.architecture["decision_head_kind"])
    return system


@dataclass(frozen=True)
class SelectedWinnerRuntimeBridge:
    """Concrete DriverRuntime bridge over Plato/resource handoff objects."""
    resources: CompactWinnerResourceProvider

    def __post_init__(self) -> None:
        if self.resources.policy_kind not in ("direct_neural", "catboost"):
            raise WinnerArtifactRefusal("winner resource policy kind is invalid")

    def system_factory(self, bundle: WinnerBundle, fold: Any,
                       control_name: str, shuffle_seed: int | None
                       ) -> SelectedWinnerLearningSystem:
        if control_name != "PROPHET" and (
                not control_name.startswith("SHUFFLED_") or shuffle_seed is None):
            raise WinnerArtifactRefusal("winner control target request is invalid")
        if self.resources.policy_kind != bundle.architecture["decision_head_kind"]:
            raise WinnerArtifactRefusal("winner resource policy kind differs from bundle")
        provider = None
        if bundle.arm != "C0":
            handoff = self.resources.compact_atlas_handoff(
                fold, control_name, shuffle_seed
            )
            provider = FrozenAtlasTargetStore.from_handoff(handoff)
            receipt = provider.shuffle_receipt
            expected_control = "PROPHET" if control_name == "PROPHET" else "SHUFFLED"
            if (receipt.get("control") != expected_control
                    or (expected_control == "SHUFFLED"
                        and (int(receipt.get("seed", -1)) != int(shuffle_seed)
                             or receipt.get("derangement") is not True
                             or not _is_sha(receipt.get("permutation_sha256"))
                             or not _is_sha(receipt.get("source_content_sha256"))
                             or not _is_sha(receipt.get("shuffled_content_sha256"))
                             or receipt.get("source_content_sha256")
                                == receipt.get("shuffled_content_sha256")))):
                raise WinnerArtifactRefusal("resource target control was not frozen exactly once")
            expected_fit_days = C.object_sha256(list(sorted(int(day) for day in fold.fit_days)))
            if provider.fit_day_manifest_sha256 != expected_fit_days:
                raise WinnerArtifactRefusal("selected target context is not fold-causal")
        return build_selected_winner_system(
            bundle, provider, self.resources.event_transform
        )


def make_selected_winner_system_factory(resources: CompactWinnerResourceProvider):
    bridge = SelectedWinnerRuntimeBridge(resources)
    def entry_v2_selected_winner_system_factory(
        bundle: WinnerBundle, fold: Any, control_name: str,
        shuffle_seed: int | None,
    ) -> SelectedWinnerLearningSystem:
        return bridge.system_factory(bundle, fold, control_name, shuffle_seed)
    return entry_v2_selected_winner_system_factory


def publish_winner_integration(
    path: str | os.PathLike[str], *, pending_adoption_path: str | os.PathLike[str],
    winner_bundle_path: str | os.PathLike[str],
    resources: CompactWinnerResourceProvider,
) -> WinnerIntegrationReceipt:
    """Immutable PENDING_INTEGRATION -> READY transition; never mutates v1."""
    pending = load_winner_adoption(pending_adoption_path)
    if pending.integration_ready or pending.status != "PENDING_INTEGRATION":
        raise WinnerArtifactRefusal("integration transition requires pending v1 adoption")
    bundle = load_winner_bundle(
        winner_bundle_path, expected_adoption_sha256=pending.adoption_sha256
    )
    bridge = SelectedWinnerRuntimeBridge(resources)
    if (not callable(resources.context_corpus)
            or not callable(resources.compact_atlas_handoff)
            or resources.ownership_transferred is not True):
        raise WinnerArtifactRefusal("integration resources lack one-open/target factories")
    required_resource_hashes = (
        getattr(resources, "receipt_sha256", None),
        getattr(resources, "target_provider_factory_sha256", None),
    )
    if any(not _is_sha(value) for value in required_resource_hashes):
        raise WinnerArtifactRefusal("integration resources are not immutable/receipted")
    deployed_policy_payloads = {
        "mapper.json": getattr(resources, "mapper_sha256", None),
        "calibrator.json": getattr(resources, "calibrator_sha256", None),
        "thresholds.json": getattr(resources, "thresholds_sha256", None),
        "capacity.json": getattr(resources, "capacity_authority_sha256", None),
    }
    if any(value != bundle.files[name]
           for name, value in deployed_policy_payloads.items()):
        raise WinnerArtifactRefusal(
            "production policy resources differ from winner policy payload bytes"
        )
    transform = resources.event_transform
    if (transform.normalization != "UNNORMALIZED_CANONICAL"
            or transform.transform_law_sha256
                != bundle.architecture["expanded_transform_law_sha256"]
            or transform.schema_sha256 != bundle.architecture["expanded_schema_sha256"]
            or transform.input_contract_sha256
                != bundle.architecture["input_contract_sha256"]
            or transform.base_binding_sha256 != bundle.model_input_binding.binding_sha256):
        raise WinnerArtifactRefusal("integration transform differs from winner bundle")
    model, objective = build_selected_winner_model(bundle)
    policy_factory = load_winner_policy_factory(bundle)
    if policy_factory.fit_chronology_law != (
        "entry-v2-selected-train-only-policy-v1"
    ):
        raise WinnerArtifactRefusal(
            "bundle policy factory does not enforce TRAIN-only chronology"
        )
    resource_policy_hash = getattr(resources, "policy_factory_sha256", None)
    if resource_policy_hash not in (None, policy_factory.policy_factory_sha256):
        raise WinnerArtifactRefusal(
            "live resource policy differs from bundle-derived restart policy"
        )
    policy_canary = load_winner_policy_canary(bundle)
    canary = _sha(module_state_bytes(model) + module_state_bytes(objective)
                  + policy_canary.encode())
    base = WinnerIntegrationReceipt(
        "entry-v2-neural-winner-integration-v1", "READY", True,
        pending.adoption_sha256, bundle.bundle_sha256,
        dict(pending.frozen_selection), canary,
        str(resources.receipt_sha256), str(resources.target_provider_factory_sha256),
        str(transform.transform_law_sha256), policy_factory.policy_factory_sha256, "",
    )
    value = asdict(base); value.pop("integration_sha256")
    receipt = WinnerIntegrationReceipt(
        **value, integration_sha256=_sha(_canonical(value))
    )
    target = C.assert_workspace_output(path)
    C.guard_payload(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        existing = load_winner_integration(target)
        if (existing.pending_adoption_sha256 != pending.adoption_sha256
                or existing.winner_bundle_sha256 != bundle.bundle_sha256
                or existing.integration_sha256 != receipt.integration_sha256):
            raise WinnerArtifactRefusal("immutable integration receipt differs")
        return existing
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(_canonical(asdict(receipt))); stream.flush(); os.fsync(stream.fileno())
        os.chmod(temporary, 0o444); os.link(temporary, target); os.unlink(temporary)
    except Exception:
        try: os.unlink(temporary)
        except FileNotFoundError: pass
        raise
    return receipt


def load_winner_integration(path: str | os.PathLike[str]) -> WinnerIntegrationReceipt:
    target = Path(path)
    if (not target.is_file() or target.is_symlink()
            or stat.S_IMODE(target.stat().st_mode) & 0o222):
        raise WinnerArtifactRefusal("winner integration receipt is absent/mutable")
    try:
        receipt = WinnerIntegrationReceipt(**json.loads(target.read_text()))
    except Exception as exc:
        raise WinnerArtifactRefusal("winner integration receipt cannot decode") from exc
    value = asdict(receipt); declared = value.pop("integration_sha256")
    if (receipt.schema != "entry-v2-neural-winner-integration-v1"
            or receipt.status != "READY" or receipt.integration_ready is not True
            or _sha(_canonical(value)) != declared
            or any(not _is_sha(value) for value in (
                receipt.pending_adoption_sha256, receipt.winner_bundle_sha256,
                receipt.load_canary_sha256, receipt.resource_receipt_sha256,
                receipt.target_provider_factory_sha256,
                receipt.expanded_transform_law_sha256,
                receipt.policy_factory_sha256,
            ))):
        raise WinnerArtifactRefusal("winner integration receipt is incomplete/altered")
    return receipt


__all__ = [
    "BundleWinnerPolicyFactory", "BundleWinnerPolicyRuntime",
    "CompactWinnerResourceProvider", "ExpandedEventTransform", "ExpandedEventView",
    "FrozenSelectedObjective",
    "SelectedAtlasTargetProvider", "WinnerArtifactRefusal",
    "FrozenAtlasTargetStore", "SelectedWinnerLearningSystem", "WinnerBundle",
    "SelectedWinnerRuntimeBridge", "build_selected_winner_model",
    "build_selected_winner_system", "make_selected_winner_system_factory",
    "load_winner_bundle", "load_winner_integration",
    "load_winner_policy_canary", "load_winner_policy_factory",
    "required_payloads_for_head", "enforce_selected_determinism",
    "publish_winner_integration", "WinnerIntegrationReceipt",
    "publish_winner_bundle",
]
