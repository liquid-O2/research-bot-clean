"""Small, auditable CatBoost heads for causal Entry V2 confirmation.

This is intentionally tabular-only.  All sequence interpretation happens in
``confirmation.py`` before these heads see a row.  A native candidate receives
equal total training weight regardless of how many causal snapshots survive.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
from types import MappingProxyType
from typing import Mapping

import catboost
from catboost import CatBoostClassifier, CatBoostRegressor
import numpy as np
from sklearn.linear_model import LogisticRegression

from . import common as C
from .confirmation import ConfirmationDataset, ConfirmationRefusal, GOAL_USD


MODEL_SCHEMA = "QRE2CONFCB1"
SELECTOR_SCHEMA = "QRE2CONFFITSELECT1"
HEAD_FILES = MappingProxyType({
    "pnl_mean": "pnl_mean.cbm",
    "pnl_q20": "pnl_q20.cbm",
    "goal": "goal.cbm",
    "wall": "wall.cbm",
    "mae_q90": "mae_q90.cbm",
})


@dataclass(frozen=True, slots=True)
class ConfirmationModelConfig:
    iterations: int = 350
    depth: int = 6
    learning_rate: float = 0.04
    l2_leaf_reg: float = 10.0
    random_seed: int = 20260819
    thread_count: int = 16

    def __post_init__(self) -> None:
        if (not 10 <= self.iterations <= 2_000 or not 3 <= self.depth <= 10
                or not 0 < self.learning_rate <= 0.3
                or not 0 < self.l2_leaf_reg <= 1_000
                or not 1 <= self.thread_count <= C.MAX_CPU_WORKERS):
            raise ConfirmationRefusal("CatBoost confirmation configuration is invalid")

    @property
    def receipt_sha256(self) -> str:
        return C.object_sha256({"schema": MODEL_SCHEMA, **asdict(self)})


@dataclass(frozen=True, slots=True)
class PlattCalibrator:
    slope: float
    intercept: float

    def __post_init__(self) -> None:
        if (not math.isfinite(self.slope) or not math.isfinite(self.intercept)
                or self.slope < 0):
            raise ConfirmationRefusal("Platt calibration coefficients are invalid")

    @classmethod
    def fit(cls, raw_score: np.ndarray, target: np.ndarray,
            weight: np.ndarray) -> "PlattCalibrator":
        x = np.asarray(raw_score, np.float64).reshape(-1, 1)
        y = np.asarray(target, np.int8)
        w = np.asarray(weight, np.float64)
        if (x.shape != (len(y), 1) or w.shape != y.shape
                or len(np.unique(y)) != 2 or np.any(w <= 0)
                or not np.all(np.isfinite(x))):
            raise ConfirmationRefusal("Platt split is empty, one-class, or malformed")
        learner = LogisticRegression(
            C=1_000_000.0, solver="lbfgs", max_iter=2_000,
            random_state=0)
        learner.fit(x, y, sample_weight=w)
        slope = float(learner.coef_[0, 0])
        # Anti-calibration is never an admissible repair.  It normally signals
        # a reversed label/head contract or a catastrophically unstable split.
        if slope < 0:
            raise ConfirmationRefusal("Platt calibration reversed the model ordering")
        return cls(slope=slope, intercept=float(learner.intercept_[0]))

    def predict(self, raw_score: np.ndarray) -> np.ndarray:
        z = np.clip(self.slope * np.asarray(raw_score, np.float64)
                    + self.intercept, -40.0, 40.0)
        return np.clip(1.0 / (1.0 + np.exp(-z)), 1e-9, 1.0 - 1e-9)


@dataclass(frozen=True, slots=True)
class ConfirmationPredictions:
    opportunity_id: np.ndarray
    expected_pnl_usd: np.ndarray
    pnl_q20_usd: np.ndarray
    goal_probability: np.ndarray
    wall_probability: np.ndarray
    mae_q90_usd: np.ndarray
    model_hash: str

    def validate(self, expected_ids: np.ndarray | None = None) -> None:
        n = len(self.opportunity_id)
        vectors = (self.expected_pnl_usd, self.pnl_q20_usd,
                   self.goal_probability, self.wall_probability,
                   self.mae_q90_usd)
        if (any(np.asarray(value).shape != (n,) for value in vectors)
                or any(not np.all(np.isfinite(value)) for value in vectors)
                or np.any(np.asarray(self.goal_probability) < 0)
                or np.any(np.asarray(self.goal_probability) > 1)
                or np.any(np.asarray(self.wall_probability) < 0)
                or np.any(np.asarray(self.wall_probability) > 1)
                or np.any(np.asarray(self.mae_q90_usd) < 0)
                or not self.model_hash):
            raise ConfirmationRefusal("confirmation prediction schema is invalid")
        if expected_ids is not None and not np.array_equal(
                np.asarray(self.opportunity_id, str), np.asarray(expected_ids, str)):
            raise ConfirmationRefusal("prediction rows differ from dataset identity")


@dataclass(frozen=True, slots=True)
class FitOnlyFeatureSelector:
    """Label-blind structural pruning learned only from the FIT matrix."""

    input_feature_names: tuple[str, ...]
    selected_indices: tuple[int, ...]
    constant_feature_names: tuple[str, ...]
    duplicate_aliases: tuple[tuple[str, str], ...]
    fit_representation_sha256: str
    receipt_sha256: str

    def __post_init__(self) -> None:
        width = len(self.input_feature_names)
        if (not width or len(set(self.input_feature_names)) != width
                or not self.selected_indices
                or tuple(sorted(set(self.selected_indices))) != self.selected_indices
                or any(index < 0 or index >= width
                       for index in self.selected_indices)
                or len(self.receipt_sha256) != 64):
            raise ConfirmationRefusal("fit-only feature selector is malformed")

    @classmethod
    def fit(cls, dataset: ConfirmationDataset) -> "FitOnlyFeatureSelector":
        dataset.validate()
        x = np.asarray(dataset.features, np.float32)
        names = tuple(dataset.feature_names)
        nonconstant = np.any(x != x[0], axis=0)
        constant_names = tuple(
            name for name, keep in zip(names, nonconstant) if not keep)
        representatives: dict[str, list[int]] = {}
        selected: list[int] = []
        aliases: list[tuple[str, str]] = []
        for index in np.flatnonzero(nonconstant).tolist():
            values = np.ascontiguousarray(x[:, index], dtype=np.float32)
            signature = hashlib.sha256(values.tobytes()).hexdigest()
            duplicate = None
            for representative in representatives.get(signature, ()):
                if np.array_equal(x[:, representative], x[:, index]):
                    duplicate = representative
                    break
            if duplicate is None:
                selected.append(index)
                representatives.setdefault(signature, []).append(index)
            else:
                aliases.append((names[index], names[duplicate]))
        if not selected:
            raise ConfirmationRefusal(
                "FIT matrix has no nonconstant structural feature")
        core = {
            "schema": SELECTOR_SCHEMA,
            "fit_representation_sha256": dataset.representation_sha256,
            "input_feature_names": names,
            "selected_indices": tuple(selected),
            "constant_feature_names": constant_names,
            "duplicate_aliases": tuple(aliases),
            "labels_used": False,
        }
        return cls(
            names, tuple(selected), constant_names, tuple(aliases),
            dataset.representation_sha256, C.object_sha256(core))

    @property
    def selected_feature_names(self) -> tuple[str, ...]:
        return tuple(self.input_feature_names[index]
                     for index in self.selected_indices)

    def transform(self, dataset: ConfirmationDataset) -> ConfirmationDataset:
        dataset.validate()
        if tuple(dataset.feature_names) != self.input_feature_names:
            raise ConfirmationRefusal(
                "fit-only selector input feature schema differs")
        indices = np.asarray(self.selected_indices, np.int64)
        result = replace(
            dataset,
            feature_names=self.selected_feature_names,
            features=np.asarray(dataset.features, np.float32)[:, indices],
            source_receipts=dataset.source_receipts + (self.receipt_sha256,),
        )
        result.validate()
        return result

    def save(self, path: os.PathLike[str] | str) -> str:
        target = C.assert_workspace_output(path)
        core = {
            "schema": SELECTOR_SCHEMA,
            "input_feature_names": self.input_feature_names,
            "selected_indices": self.selected_indices,
            "constant_feature_names": self.constant_feature_names,
            "duplicate_aliases": self.duplicate_aliases,
            "fit_representation_sha256": self.fit_representation_sha256,
            "labels_used": False,
        }
        if C.object_sha256(core) != self.receipt_sha256:
            raise ConfirmationRefusal("fit-only selector receipt differs")
        C.atomic_json(target, {**core, "receipt_sha256": self.receipt_sha256})
        return C.file_sha256(target)

    @classmethod
    def load(cls, path: os.PathLike[str] | str) -> "FitOnlyFeatureSelector":
        source = Path(path)
        C.guard_payload(source)
        try:
            value = json.loads(source.read_text())
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ConfirmationRefusal("cannot read fit-only selector") from exc
        core = {key: item for key, item in value.items()
                if key != "receipt_sha256"}
        if (value.get("schema") != SELECTOR_SCHEMA
                or value.get("labels_used") is not False
                or C.object_sha256(core) != value.get("receipt_sha256")):
            raise ConfirmationRefusal("fit-only selector identity differs")
        return cls(
            tuple(value["input_feature_names"]),
            tuple(int(item) for item in value["selected_indices"]),
            tuple(value["constant_feature_names"]),
            tuple(tuple(item) for item in value["duplicate_aliases"]),
            str(value["fit_representation_sha256"]),
            str(value["receipt_sha256"]),
        )


def _series_weights(dataset: ConfirmationDataset) -> np.ndarray:
    ids = np.asarray(dataset.series_id, str)
    unique, inverse, counts = np.unique(ids, return_inverse=True, return_counts=True)
    if not len(unique):
        raise ConfirmationRefusal("cannot weight an empty confirmation dataset")
    weights = 1.0 / counts[inverse].astype(np.float64)
    # Normalize only for stable CatBoost regularization scale.
    return weights * (len(weights) / weights.sum())


def _assert_fit_platt_chronology(
    fit: ConfirmationDataset, platt: ConfirmationDataset,
) -> None:
    fit.validate(); platt.validate()
    if (fit.feature_names != platt.feature_names
            or fit.config_sha256 != platt.config_sha256):
        raise ConfirmationRefusal("fit and Platt schemas/configurations differ")
    if fit.snapshot_mode != "TRAINING" or platt.snapshot_mode != "TRAINING":
        raise ConfirmationRefusal("CatBoost fit/Platt require the sparse TRAINING grid")
    if set(np.asarray(fit.series_id, str)) & set(np.asarray(platt.series_id, str)):
        raise ConfirmationRefusal("a confirmation series crosses fit and Platt splits")
    if int(np.max(fit.day)) >= int(np.min(platt.day)):
        raise ConfirmationRefusal("Platt chronology is not strictly after fit")


class ConfirmationModel:
    def __init__(
        self, *, config: ConfirmationModelConfig, feature_names: tuple[str, ...],
        models: Mapping[str, object], calibrators: Mapping[str, PlattCalibrator],
        training_max_delay_sec: int,
        fit_representation_sha256: str, platt_representation_sha256: str,
        model_hash: str,
    ) -> None:
        if set(models) != set(HEAD_FILES) or set(calibrators) != {"goal", "wall"}:
            raise ConfirmationRefusal("confirmation head roster is incomplete")
        self.config = config
        self.feature_names = tuple(feature_names)
        self.models = MappingProxyType(dict(models))
        self.calibrators = MappingProxyType(dict(calibrators))
        if training_max_delay_sec not in (300, 600):
            raise ConfirmationRefusal("model training expiry is invalid")
        self.training_max_delay_sec = int(training_max_delay_sec)
        self.fit_representation_sha256 = fit_representation_sha256
        self.platt_representation_sha256 = platt_representation_sha256
        self.model_hash = model_hash

    def predict(self, dataset: ConfirmationDataset) -> ConfirmationPredictions:
        dataset.validate()
        if tuple(dataset.feature_names) != self.feature_names:
            raise ConfirmationRefusal("prediction feature schema differs from fitted model")
        if dataset.max_delay_sec > self.training_max_delay_sec:
            raise ConfirmationRefusal("prediction expiry exceeds the fitted training horizon")
        x = np.asarray(dataset.features, np.float32)
        goal_raw = np.asarray(self.models["goal"].predict(
            x, prediction_type="RawFormulaVal"), np.float64).reshape(-1)
        wall_raw = np.asarray(self.models["wall"].predict(
            x, prediction_type="RawFormulaVal"), np.float64).reshape(-1)
        result = ConfirmationPredictions(
            opportunity_id=np.asarray(dataset.opportunity_id, str).copy(),
            expected_pnl_usd=np.asarray(
                self.models["pnl_mean"].predict(x), np.float64).reshape(-1),
            pnl_q20_usd=np.asarray(
                self.models["pnl_q20"].predict(x), np.float64).reshape(-1),
            goal_probability=self.calibrators["goal"].predict(goal_raw),
            wall_probability=self.calibrators["wall"].predict(wall_raw),
            mae_q90_usd=np.maximum(0.0, np.asarray(
                self.models["mae_q90"].predict(x), np.float64).reshape(-1)),
            model_hash=self.model_hash,
        )
        result.validate(dataset.opportunity_id)
        return result

    def _manifest(self, file_hashes: Mapping[str, str]) -> dict[str, object]:
        return {
            "schema": MODEL_SCHEMA,
            "config": asdict(self.config),
            "config_sha256": self.config.receipt_sha256,
            "feature_names": self.feature_names,
            "training_max_delay_sec": self.training_max_delay_sec,
            "fit_representation_sha256": self.fit_representation_sha256,
            "platt_representation_sha256": self.platt_representation_sha256,
            "calibrators": {name: asdict(value)
                            for name, value in self.calibrators.items()},
            "model_hash": self.model_hash,
            "files": dict(file_hashes),
            "catboost_version": catboost.__version__,
            "numpy_version": np.__version__,
        }

    def save(self, path: os.PathLike[str] | str) -> str:
        target = C.assert_workspace_output(path)
        if target.exists():
            raise ConfirmationRefusal("confirmation model target already exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(
            prefix=f".{target.name}.tmp.", dir=target.parent))
        try:
            hashes: dict[str, str] = {}
            for name, filename in HEAD_FILES.items():
                model_path = stage / filename
                self.models[name].save_model(str(model_path), format="cbm")
                hashes[filename] = C.file_sha256(model_path)
            manifest = self._manifest(hashes)
            C.atomic_json(stage / "manifest.json", manifest)
            os.replace(stage, target)
        except Exception:
            shutil.rmtree(stage, ignore_errors=True)
            raise
        return C.file_sha256(target / "manifest.json")

    @classmethod
    def load(cls, path: os.PathLike[str] | str) -> "ConfirmationModel":
        source = Path(path).resolve()
        C.guard_payload(source)
        try:
            manifest = json.loads((source / "manifest.json").read_text())
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ConfirmationRefusal("cannot read confirmation model manifest") from exc
        if (manifest.get("schema") != MODEL_SCHEMA
                or manifest.get("catboost_version") != catboost.__version__):
            raise ConfirmationRefusal("confirmation model schema/runtime differs")
        config = ConfirmationModelConfig(**manifest["config"])
        if config.receipt_sha256 != manifest.get("config_sha256"):
            raise ConfirmationRefusal("confirmation model config receipt differs")
        models: dict[str, object] = {}
        for name, filename in HEAD_FILES.items():
            model_path = source / filename
            if C.file_sha256(model_path) != manifest["files"].get(filename):
                raise ConfirmationRefusal(f"confirmation model hash differs: {filename}")
            model = (CatBoostClassifier() if name in {"goal", "wall"}
                     else CatBoostRegressor())
            model.load_model(str(model_path), format="cbm")
            models[name] = model
        calibrators = {name: PlattCalibrator(**manifest["calibrators"][name])
                       for name in ("goal", "wall")}
        expected_hash = C.object_sha256({
            "schema": MODEL_SCHEMA,
            "config_sha256": config.receipt_sha256,
            "feature_names": tuple(manifest["feature_names"]),
            "training_max_delay_sec": int(manifest["training_max_delay_sec"]),
            "fit": manifest["fit_representation_sha256"],
            "platt": manifest["platt_representation_sha256"],
            "calibrators": {name: asdict(value)
                            for name, value in calibrators.items()},
        })
        if expected_hash != manifest.get("model_hash"):
            raise ConfirmationRefusal("confirmation model identity receipt differs")
        return cls(
            config=config, feature_names=tuple(manifest["feature_names"]),
            models=models, calibrators=calibrators,
            training_max_delay_sec=int(manifest["training_max_delay_sec"]),
            fit_representation_sha256=manifest["fit_representation_sha256"],
            platt_representation_sha256=manifest["platt_representation_sha256"],
            model_hash=expected_hash,
        )


def fit_confirmation_model(
    fit: ConfirmationDataset,
    platt: ConfirmationDataset,
    *, config: ConfirmationModelConfig = ConfirmationModelConfig(),
) -> ConfirmationModel:
    """Fit five fixed CatBoost heads on FIT and calibrate only on PLATT."""

    _assert_fit_platt_chronology(fit, platt)
    x = np.asarray(fit.features, np.float32)
    weights = _series_weights(fit)
    goal = np.asarray(fit.cert_close_usd >= GOAL_USD, np.int8)
    wall = np.asarray(fit.wall_hit, np.int8)
    if (len(np.unique(goal)) != 2 or len(np.unique(wall)) != 2
            or np.ptp(np.asarray(fit.cert_close_usd, np.float64)) == 0):
        raise ConfirmationRefusal("FIT targets lack the variation required by all heads")
    common = dict(
        iterations=config.iterations, depth=config.depth,
        learning_rate=config.learning_rate, l2_leaf_reg=config.l2_leaf_reg,
        random_seed=config.random_seed, thread_count=config.thread_count,
        allow_writing_files=False, verbose=False,
    )
    models: dict[str, object] = {
        "pnl_mean": CatBoostRegressor(loss_function="RMSE", **common),
        "pnl_q20": CatBoostRegressor(loss_function="Quantile:alpha=0.2", **common),
        "goal": CatBoostClassifier(loss_function="Logloss",
                                   auto_class_weights="Balanced", **common),
        "wall": CatBoostClassifier(loss_function="Logloss",
                                   auto_class_weights="Balanced", **common),
        "mae_q90": CatBoostRegressor(loss_function="Quantile:alpha=0.9", **common),
    }
    targets = {
        "pnl_mean": np.asarray(fit.cert_close_usd, np.float64),
        "pnl_q20": np.asarray(fit.cert_close_usd, np.float64),
        "goal": goal, "wall": wall,
        "mae_q90": np.asarray(fit.mae_usd, np.float64),
    }
    for name in HEAD_FILES:
        models[name].fit(x, targets[name], sample_weight=weights)

    px = np.asarray(platt.features, np.float32)
    platt_weight = _series_weights(platt)
    calibrators = {
        "goal": PlattCalibrator.fit(
            models["goal"].predict(px, prediction_type="RawFormulaVal"),
            np.asarray(platt.cert_close_usd >= GOAL_USD, np.int8), platt_weight),
        "wall": PlattCalibrator.fit(
            models["wall"].predict(px, prediction_type="RawFormulaVal"),
            np.asarray(platt.wall_hit, np.int8), platt_weight),
    }
    model_hash = C.object_sha256({
        "schema": MODEL_SCHEMA, "config_sha256": config.receipt_sha256,
        "feature_names": fit.feature_names,
        "training_max_delay_sec": fit.max_delay_sec,
        "fit": fit.representation_sha256,
        "platt": platt.representation_sha256,
        "calibrators": {name: asdict(value)
                        for name, value in calibrators.items()},
    })
    return ConfirmationModel(
        config=config, feature_names=fit.feature_names, models=models,
        calibrators=calibrators,
        training_max_delay_sec=fit.max_delay_sec,
        fit_representation_sha256=fit.representation_sha256,
        platt_representation_sha256=platt.representation_sha256,
        model_hash=model_hash,
    )


__all__ = [
    "ConfirmationModel", "ConfirmationModelConfig", "ConfirmationPredictions",
    "FitOnlyFeatureSelector", "PlattCalibrator", "fit_confirmation_model",
]
