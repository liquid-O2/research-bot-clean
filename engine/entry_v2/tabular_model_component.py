"""CatBoost component model bundle for Entry V2."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import shutil
import tempfile
from types import MappingProxyType
from typing import Final, Mapping

import catboost
from catboost import CatBoostClassifier, CatBoostRegressor
import numpy as np

from . import common as C
from .tabular_atomic import atomic_replace_directory
from .tabular_fit_backends import (
    COMPONENT_HEAD_LOSS_FUNCTIONS, fit_receipt_backend_fields,
    fit_receipt_law_fields,
)
from .tabular_model_fit import (
    _assert_chronological, _bounded_row_subset, _common_parameters,
    _config_from_json, _fixed_fit, _fit_with_early_stop, _head_model, _sha,
    _serialized_model_sha256, catboost_predict_threads,
)
from .tabular_recovery_contracts import (
    RecoveryConfig, RecoveryRefusal, VALUE_SCALE_USD, sha256_row_array,
)
from .tabular_training import (
    COMPONENT_PREDICTION_NAMES, ComponentPredictionTable,
    ComponentTrainingMatrix, equal_portfolio_day_weights,
)

COMPONENT_MODEL_SCHEMA: Final = "QRE2TABCOMPONENTCB3"
COMPONENT_FILES: Final = MappingProxyType({
    "current": "current_multi_quantile.cbm",
    "continuation": "continuation_multi_quantile.cbm",
    "wall": "wall_logloss.cbm",
    "adverse": "adverse_q90.cbm",
    "occupancy": "occupancy_multi_quantile.cbm",
})

@dataclass(frozen=True, slots=True)
class ComponentArrayPredictions:
    values: np.ndarray
    prediction_names: tuple[str, ...] = COMPONENT_PREDICTION_NAMES

    def validate(self) -> None:
        values = np.asarray(self.values, np.float64)
        if (self.prediction_names != COMPONENT_PREDICTION_NAMES
                or values.ndim != 2
                or values.shape[1] != len(COMPONENT_PREDICTION_NAMES)
                or not np.all(np.isfinite(values))
                or np.any(values[:, 6] < 0) or np.any(values[:, 6] > 1)
                or np.any(values[:, 7:] < 0)
                or np.any(values[:, 0] > values[:, 1])
                or np.any(values[:, 1] > values[:, 2])
                or np.any(values[:, 3] > values[:, 4])
                or np.any(values[:, 4] > values[:, 5])
                or np.any(values[:, 8] > values[:, 9])):
            raise RecoveryRefusal("component prediction array is malformed")


class ComponentModelBundle:
    def __init__(
        self, *, config: RecoveryConfig, seed: int,
        feature_names: tuple[str, ...], models: Mapping[str, object],
        train_day_range: tuple[int, int],
        validation_day_range: tuple[int, int],
        train_receipt_sha256: str, validation_receipt_sha256: str,
        shuffled_labels: bool, shuffle_seed: int | None,
        model_file_sha256:Mapping[str,str],
        receipt_sha256: str,
        refit_all_pre_h2:bool=False,
        iteration_selection_receipt_sha256:str|None=None,
    ) -> None:
        config.__post_init__()
        chronology_valid=(
            train_day_range[1] >= validation_day_range[0]
            if refit_all_pre_h2
            else train_day_range[1] < validation_day_range[0])
        if (set(models) != set(COMPONENT_FILES) or not feature_names
                or seed not in config.real_seeds
                or shuffled_labels != (shuffle_seed is not None)
                or (shuffle_seed is not None
                    and shuffle_seed not in config.shuffle_seeds)
                or len(train_day_range) != 2 or len(validation_day_range) != 2
                or train_day_range[0] > train_day_range[1]
                or validation_day_range[0] > validation_day_range[1]
                or not chronology_valid
                or refit_all_pre_h2!=(iteration_selection_receipt_sha256
                                     is not None)
                or (iteration_selection_receipt_sha256 is not None
                    and not _sha(iteration_selection_receipt_sha256))
                or (refit_all_pre_h2 and (
                    shuffled_labels or train_day_range[1]>=C.HOLDOUT_START_D8))
                or set(model_file_sha256)!=set(COMPONENT_FILES)
                or any(not _sha(value) for value in model_file_sha256.values())
                or not all(_sha(value) for value in (
                    train_receipt_sha256, validation_receipt_sha256,
                    receipt_sha256))):
            raise RecoveryRefusal("component bundle contract is malformed")
        self.config = config; self.seed = int(seed)
        self.feature_names = tuple(feature_names)
        self.models = MappingProxyType(dict(models))
        self.train_day_range = tuple(map(int, train_day_range))
        self.validation_day_range = tuple(map(int, validation_day_range))
        for day in self.train_day_range + self.validation_day_range:
            C.guard_date(day)
        self.train_receipt_sha256 = train_receipt_sha256
        self.validation_receipt_sha256 = validation_receipt_sha256
        self.shuffled_labels = bool(shuffled_labels)
        self.shuffle_seed = shuffle_seed
        self.model_file_sha256=MappingProxyType(dict(model_file_sha256))
        self.receipt_sha256 = receipt_sha256
        self.refit_all_pre_h2=bool(refit_all_pre_h2)
        self.iteration_selection_receipt_sha256=(
            iteration_selection_receipt_sha256)

    def predict(self, x: np.ndarray) -> ComponentArrayPredictions:
        matrix = np.asarray(x, np.float32)
        if (matrix.ndim != 2 or matrix.shape[1] != len(self.feature_names)
                or not np.all(np.isfinite(matrix))):
            raise RecoveryRefusal("component prediction feature matrix differs")
        threads=catboost_predict_threads()
        current = np.asarray(self.models["current"].predict(
            matrix,thread_count=threads), np.float64)
        continuation = np.asarray(
            self.models["continuation"].predict(
                matrix,thread_count=threads), np.float64)
        if current.ndim == 1: current = current.reshape((-1, 3))
        if continuation.ndim == 1: continuation = continuation.reshape((-1, 3))
        current = np.sort(np.sinh(np.clip(current, -20, 20))
                          * VALUE_SCALE_USD, axis=1)
        continuation = np.sort(np.sinh(np.clip(continuation, -20, 20))
                               * VALUE_SCALE_USD, axis=1)
        wall = np.asarray(
            self.models["wall"].predict_proba(
                matrix,thread_count=threads), np.float64)[:, 1]
        adverse = np.maximum(0.0, np.asarray(
            self.models["adverse"].predict(
                matrix,thread_count=threads), np.float64).reshape(-1))
        occupancy = np.asarray(
            self.models["occupancy"].predict(
                matrix,thread_count=threads), np.float64)
        if occupancy.ndim == 1: occupancy = occupancy.reshape((-1, 2))
        occupancy = np.maximum(0.0, np.sort(occupancy, axis=1))
        result = ComponentArrayPredictions(np.column_stack((
            current, continuation, wall, adverse, occupancy)))
        result.validate(); return result

    def oof_table(
        self, opportunity_id: np.ndarray, day: np.ndarray, x: np.ndarray, *,
        chronology_receipt_sha256: str,
        source_feature_receipts:tuple[str,...],
    ) -> ComponentPredictionTable:
        days = np.asarray(day, np.int64)
        if (days.shape != (len(x),)
                or int(days.min()) <= self.validation_day_range[1]):
            raise RecoveryRefusal("component OOF target is not after fit information")
        predictions = self.predict(x)
        result = ComponentPredictionTable(
            np.asarray(opportunity_id, str).copy(), days.copy(),
            predictions.values,
            sha256_row_array(self.receipt_sha256,len(days)),
            np.full(len(days), self.validation_day_range[1], np.int64),
            source_feature_receipts,
            COMPONENT_PREDICTION_NAMES, self.receipt_sha256,
            chronology_receipt_sha256, True)
        result.validate(); return result

    def _manifest(self, files: Mapping[str, str]) -> Mapping[str, object]:
        expected={COMPONENT_FILES[name]:self.model_file_sha256[name]
                  for name in COMPONENT_FILES}
        if dict(files)!=expected:
            raise RecoveryRefusal("component serialized model bytes changed")
        return {
            "schema": COMPONENT_MODEL_SCHEMA, "config": asdict(self.config),
            "config_sha256": self.config.receipt_sha256, "seed": self.seed,
            "feature_names": self.feature_names,
            "train_day_range": self.train_day_range,
            "validation_day_range": self.validation_day_range,
            "train_receipt_sha256": self.train_receipt_sha256,
            "validation_receipt_sha256": self.validation_receipt_sha256,
            "shuffled_labels": self.shuffled_labels,
            "shuffle_seed": self.shuffle_seed,
            "model_file_sha256":dict(self.model_file_sha256),
            "refit_all_pre_h2":self.refit_all_pre_h2,
            "iteration_selection_receipt_sha256":
                self.iteration_selection_receipt_sha256,
            "receipt_sha256": self.receipt_sha256,
            "files": dict(files), "catboost_version": catboost.__version__,
            "fit_backend_fields": {
                head: fit_receipt_backend_fields(loss)
                for head, loss in COMPONENT_HEAD_LOSS_FUNCTIONS.items()},
            "numpy_version": np.__version__, "workers": 16,
        }

    def save(self, path: os.PathLike[str] | str) -> str:
        target = C.assert_workspace_output(path)
        if target.exists():
            raise RecoveryRefusal("component bundle target already exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp.", dir=target.parent))
        try:
            hashes = {}
            for name, filename in COMPONENT_FILES.items():
                model_path = stage / filename
                self.models[name].save_model(str(model_path), format="cbm")
                hashes[filename] = C.file_sha256(model_path)
            C.atomic_json(stage / "manifest.json", self._manifest(hashes))
            atomic_replace_directory(stage,target)
        except Exception:
            shutil.rmtree(stage, ignore_errors=True); raise
        return C.file_sha256(target / "manifest.json")

    @classmethod
    def load(cls, path: os.PathLike[str] | str) -> "ComponentModelBundle":
        source = Path(path).resolve(); C.guard_payload(source)
        try:
            manifest = json.loads((source / "manifest.json").read_text())
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RecoveryRefusal("cannot strict-load component manifest") from exc
        if (manifest.get("schema") != COMPONENT_MODEL_SCHEMA
                or manifest.get("catboost_version") != catboost.__version__
                or manifest.get("workers") != 16):
            raise RecoveryRefusal("component runtime/schema differs")
        config = _config_from_json(manifest["config"])
        if config.receipt_sha256 != manifest.get("config_sha256"):
            raise RecoveryRefusal("component config receipt differs")
        models = {}
        for name, filename in COMPONENT_FILES.items():
            model_path = source / filename
            if C.file_sha256(model_path) != manifest["files"].get(filename):
                raise RecoveryRefusal(f"component model hash differs: {filename}")
            model = CatBoostClassifier() if name == "wall" else CatBoostRegressor()
            model.load_model(str(model_path), format="cbm"); models[name] = model
        core = {
            "schema": COMPONENT_MODEL_SCHEMA,
            "config_sha256": config.receipt_sha256,
            "seed": int(manifest["seed"]),
            "feature_names": tuple(manifest["feature_names"]),
            "train_day_range": tuple(manifest["train_day_range"]),
            "validation_day_range": tuple(manifest["validation_day_range"]),
            "train": manifest["train_receipt_sha256"],
            "validation": manifest["validation_receipt_sha256"],
            "model_files":dict(manifest["model_file_sha256"]),
            "refit_all_pre_h2":bool(manifest["refit_all_pre_h2"]),
            "iteration_selection_receipt_sha256":
                manifest["iteration_selection_receipt_sha256"],
            "shuffled_labels": bool(manifest["shuffled_labels"]),
            "shuffle_seed": manifest["shuffle_seed"],
        }
        if C.object_sha256(core) != manifest.get("receipt_sha256"):
            raise RecoveryRefusal("component bundle identity differs")
        stored=manifest.get("fit_backend_fields")
        if stored is not None and {
                head:dict(fields).get("law") for head,fields in stored.items()
                }!={head:fit_receipt_law_fields(loss)
                    for head,loss in COMPONENT_HEAD_LOSS_FUNCTIONS.items()}:
            raise RecoveryRefusal(
                f"published fit backend differs from the D-105 law: {stored}")
        return cls(
            config=config, seed=int(manifest["seed"]),
            feature_names=tuple(manifest["feature_names"]), models=models,
            train_day_range=tuple(manifest["train_day_range"]),
            validation_day_range=tuple(manifest["validation_day_range"]),
            train_receipt_sha256=manifest["train_receipt_sha256"],
            validation_receipt_sha256=manifest["validation_receipt_sha256"],
            shuffled_labels=bool(manifest["shuffled_labels"]),
            shuffle_seed=manifest["shuffle_seed"],
            model_file_sha256=dict(manifest["model_file_sha256"]),
            receipt_sha256=manifest["receipt_sha256"],
            refit_all_pre_h2=bool(manifest["refit_all_pre_h2"]),
            iteration_selection_receipt_sha256=
                manifest["iteration_selection_receipt_sha256"])


def fit_component_bundle(
    train: ComponentTrainingMatrix, validation: ComponentTrainingMatrix, *,
    config: RecoveryConfig, seed: int,
    shuffled_labels: bool = False, shuffle_seed: int | None = None,
) -> ComponentModelBundle:
    train.validate(); validation.validate(); config.__post_init__()
    if train.feature_names != validation.feature_names:
        raise RecoveryRefusal("component train/validation features differ")
    _assert_chronological(train.day, validation.day)
    if (shuffled_labels != (shuffle_seed is not None)
            or (shuffle_seed is not None
                and shuffle_seed not in config.shuffle_seeds)):
        raise RecoveryRefusal("component shuffle identity is incomplete")
    common = _common_parameters(config, seed)
    models: dict[str, object] = {
        "current": _head_model(
            CatBoostRegressor,
            loss_function="MultiQuantile:alpha=0.2,0.5,0.8", common=common),
        "continuation": _head_model(
            CatBoostRegressor,
            loss_function="MultiQuantile:alpha=0.2,0.5,0.8", common=common),
        "wall": _head_model(
            CatBoostClassifier, loss_function="Logloss", common=common),
        "adverse": _head_model(
            CatBoostRegressor, loss_function="Quantile:alpha=0.9",
            common=common),
        "occupancy": _head_model(
            CatBoostRegressor, loss_function="MultiQuantile:alpha=0.5,0.9",
            common=common),
    }
    x = np.asarray(train.x, np.float32); vx = np.asarray(validation.x, np.float32)
    _fit_with_early_stop(models["current"], x, train.current_asinh,
                         train.sample_weight, vx, validation.current_asinh,
                         validation.sample_weight,
                         patience=config.early_stopping_rounds)
    observed = np.asarray(train.continuation_observed, bool)
    vobserved = np.asarray(validation.continuation_observed, bool)
    if not observed.any() or not vobserved.any():
        raise RecoveryRefusal("continuation head lacks uncensored chronological rows")
    with (_bounded_row_subset(x,observed) as observed_x,
          _bounded_row_subset(vx,vobserved) as validation_observed_x):
        _fit_with_early_stop(
            models["continuation"],observed_x,
            train.continuation_asinh[observed],
            equal_portfolio_day_weights(train.day[observed]),
            validation_observed_x,validation.continuation_asinh[vobserved],
            equal_portfolio_day_weights(validation.day[vobserved]),
            patience=config.early_stopping_rounds)
    if len(np.unique(train.wall_target)) != 2 or len(np.unique(validation.wall_target)) != 2:
        raise RecoveryRefusal("wall head needs both classes in train and validation")
    _fit_with_early_stop(models["wall"], x, train.wall_target,
                         train.sample_weight, vx, validation.wall_target,
                         validation.sample_weight,
                         patience=config.early_stopping_rounds)
    _fit_with_early_stop(models["adverse"], x, train.adverse_usd,
                         train.sample_weight, vx, validation.adverse_usd,
                         validation.sample_weight,
                         patience=config.early_stopping_rounds)
    _fit_with_early_stop(models["occupancy"], x, train.occupancy_sec,
                         train.sample_weight, vx, validation.occupancy_sec,
                         validation.sample_weight,
                         patience=config.early_stopping_rounds)
    model_hashes={name:_serialized_model_sha256(model)
                  for name,model in models.items()}
    core = {
        "schema": COMPONENT_MODEL_SCHEMA,
        "config_sha256": config.receipt_sha256, "seed": int(seed),
        "feature_names": train.feature_names, "train": train.receipt_sha256,
        "validation": validation.receipt_sha256,
        "train_day_range": (int(np.min(train.day)), int(np.max(train.day))),
        "validation_day_range": (
            int(np.min(validation.day)), int(np.max(validation.day))),
        "model_files":model_hashes,
        "refit_all_pre_h2":False,
        "iteration_selection_receipt_sha256":None,
        "shuffled_labels": bool(shuffled_labels), "shuffle_seed": shuffle_seed,
    }
    return ComponentModelBundle(
        config=config, seed=seed, feature_names=train.feature_names, models=models,
        train_day_range=(int(np.min(train.day)), int(np.max(train.day))),
        validation_day_range=(
            int(np.min(validation.day)), int(np.max(validation.day))),
        train_receipt_sha256=train.receipt_sha256,
        validation_receipt_sha256=validation.receipt_sha256,
        shuffled_labels=shuffled_labels, shuffle_seed=shuffle_seed,
        model_file_sha256=model_hashes,
        receipt_sha256=C.object_sha256(core))

def fit_all_pre_h2_component_bundle(matrix:ComponentTrainingMatrix,*,
        selection_bundle:ComponentModelBundle,config:RecoveryConfig,seed:int,
        expected_last_training_day:int)->ComponentModelBundle:
    """Refit the accepted component architecture on every pre-H2 row."""

    matrix.validate();config.__post_init__()
    if (selection_bundle.seed!=seed or selection_bundle.shuffled_labels
            or selection_bundle.refit_all_pre_h2
            or selection_bundle.feature_names!=matrix.feature_names
            or int(np.max(matrix.day))!=int(expected_last_training_day)
            or int(expected_last_training_day)>=C.HOLDOUT_START_D8):
        raise RecoveryRefusal("component all-data refit inputs differ/seal opened")
    iterations={name:int(model.tree_count_)
                for name,model in selection_bundle.models.items()}
    if (set(iterations)!=set(COMPONENT_FILES)
            or any(not 0<value<=config.max_iterations
                   for value in iterations.values())):
        raise RecoveryRefusal("component iteration selection differs")
    selection=C.object_sha256({"schema":"QRE2TABREFITITER1",
        "kind":"COMPONENT","selection_model":selection_bundle.receipt_sha256,
        "iterations":iterations,"all_pre_h2":True})
    def parameters(name:str)->dict[str,object]:
        value=_common_parameters(config,seed);value["iterations"]=iterations[name]
        return value
    models={
        "current":_head_model(CatBoostRegressor,
            loss_function="MultiQuantile:alpha=0.2,0.5,0.8",
            common=parameters("current")),
        "continuation":_head_model(CatBoostRegressor,
            loss_function="MultiQuantile:alpha=0.2,0.5,0.8",
            common=parameters("continuation")),
        "wall":_head_model(CatBoostClassifier,loss_function="Logloss",
            common=parameters("wall")),
        "adverse":_head_model(CatBoostRegressor,
            loss_function="Quantile:alpha=0.9",common=parameters("adverse")),
        "occupancy":_head_model(CatBoostRegressor,
            loss_function="MultiQuantile:alpha=0.5,0.9",
            common=parameters("occupancy")),
    }
    x=np.asarray(matrix.x,np.float32)
    _fixed_fit(models["current"],x,matrix.current_asinh,matrix.sample_weight)
    observed=np.asarray(matrix.continuation_observed,bool)
    if not observed.any():
        raise RecoveryRefusal("all-data continuation head has no observed row")
    with _bounded_row_subset(x,observed) as observed_x:
        _fixed_fit(models["continuation"],observed_x,
            matrix.continuation_asinh[observed],
            equal_portfolio_day_weights(matrix.day[observed]))
    if len(np.unique(matrix.wall_target))!=2:
        raise RecoveryRefusal("all-data wall head is one-class")
    _fixed_fit(models["wall"],x,matrix.wall_target,matrix.sample_weight)
    _fixed_fit(models["adverse"],x,matrix.adverse_usd,matrix.sample_weight)
    _fixed_fit(models["occupancy"],x,matrix.occupancy_sec,matrix.sample_weight)
    hashes={name:_serialized_model_sha256(model)
            for name,model in models.items()}
    train_range=(int(np.min(matrix.day)),int(np.max(matrix.day)))
    core={"schema":COMPONENT_MODEL_SCHEMA,
        "config_sha256":config.receipt_sha256,"seed":int(seed),
        "feature_names":matrix.feature_names,"train":matrix.receipt_sha256,
        "validation":selection_bundle.receipt_sha256,
        "train_day_range":train_range,
        "validation_day_range":selection_bundle.validation_day_range,
        "model_files":hashes,"refit_all_pre_h2":True,
        "iteration_selection_receipt_sha256":selection,
        "shuffled_labels":False,"shuffle_seed":None}
    result=ComponentModelBundle(config=config,seed=seed,
        feature_names=matrix.feature_names,models=models,
        train_day_range=train_range,
        validation_day_range=selection_bundle.validation_day_range,
        train_receipt_sha256=matrix.receipt_sha256,
        validation_receipt_sha256=selection_bundle.receipt_sha256,
        shuffled_labels=False,shuffle_seed=None,model_file_sha256=hashes,
        receipt_sha256=C.object_sha256(core),refit_all_pre_h2=True,
        iteration_selection_receipt_sha256=selection)
    return result
