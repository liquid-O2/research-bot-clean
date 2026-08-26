"""Histogram action-bundle fallbacks for tabular recovery."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Mapping

import numpy as np

from . import common as C
from .tabular_atomic import atomic_replace_directory
from .tabular_histogram import (
    HISTOGRAM_ACTION_SCHEMA, HISTOGRAM_BACKENDS, _chronology,
    _config_from_mapping, _fixed_hist_reg, _selected_iterations, _xgboost,
)
from .tabular_models import ActionModelBundle
from .tabular_recovery_contracts import RecoveryConfig, RecoveryRefusal
from .tabular_training import (
    ActionTrainingMatrix, equal_portfolio_day_weights, matched_shuffle_action,
)


@dataclass(frozen=True, slots=True)
class HistogramActionBundle:
    backend:str
    feature_names:tuple[str,...]
    models:tuple[object,object,object]
    seed:int
    config:RecoveryConfig
    objective:str
    train_day_range:tuple[int,int]
    validation_day_range:tuple[int,int]
    train_receipt_sha256:str
    validation_receipt_sha256:str
    component_oof_receipt_sha256:str
    shuffled_labels:bool
    shuffle_seed:int|None
    model_file_sha256:tuple[str,str,str]
    receipt_sha256:str
    refit_all_pre_h2:bool=False
    iteration_selection_receipt_sha256:str|None=None

    def __post_init__(self)->None:
        self.config.__post_init__()
        if (self.backend not in HISTOGRAM_BACKENDS or not self.feature_names
                or len(self.models)!=3 or self.seed not in self.config.real_seeds
                or self.objective!="MultiRMSE"
                or ((self.train_day_range[1]>=self.validation_day_range[0])
                    !=self.refit_all_pre_h2)
                or self.refit_all_pre_h2!=(
                    self.iteration_selection_receipt_sha256 is not None)
                or (self.iteration_selection_receipt_sha256 is not None
                    and len(self.iteration_selection_receipt_sha256)!=64)
                or (self.refit_all_pre_h2 and (
                    self.shuffled_labels
                    or self.train_day_range[1]>=C.HOLDOUT_START_D8))
                or self.shuffled_labels!=(self.shuffle_seed is not None)
                or (self.shuffle_seed is not None
                    and self.shuffle_seed not in self.config.shuffle_seeds)
                or len(self.model_file_sha256)!=3
                or not all(len(value)==64 for value in (
                    *self.model_file_sha256,self.train_receipt_sha256,
                    self.validation_receipt_sha256,
                    self.component_oof_receipt_sha256,self.receipt_sha256))):
            raise RecoveryRefusal("histogram action bundle is malformed")
        core={"schema":HISTOGRAM_ACTION_SCHEMA,"backend":self.backend,
            "features":self.feature_names,"seed":self.seed,
            "config":self.config.receipt_sha256,"objective":self.objective,
            "train_day_range":self.train_day_range,
            "validation_day_range":self.validation_day_range,
            "train":self.train_receipt_sha256,
            "validation":self.validation_receipt_sha256,
            "component_oof":self.component_oof_receipt_sha256,
            "shuffled_labels":self.shuffled_labels,
            "shuffle_seed":self.shuffle_seed,
            "model_files":self.model_file_sha256,
            "refit_all_pre_h2":self.refit_all_pre_h2,
            "iteration_selection_receipt_sha256":
                self.iteration_selection_receipt_sha256}
        if C.object_sha256(core)!=self.receipt_sha256:
            raise RecoveryRefusal("histogram action receipt differs")

    def predict_regret_usd(self,x:np.ndarray)->np.ndarray:
        matrix=np.asarray(x,np.float32)
        if matrix.ndim!=2 or matrix.shape[1]!=len(self.feature_names):
            raise RecoveryRefusal("histogram action feature schema differs")
        raw=np.column_stack([np.asarray(model.predict(matrix),np.float64)
                             for model in self.models])
        return np.maximum(0,np.expm1(np.clip(raw,0,40))*VALUE_SCALE_USD)

    def save(self,path:str|Path)->str:
        self.__post_init__();target=C.assert_workspace_output(path)
        if target.exists():raise RecoveryRefusal("histogram action target exists")
        target.parent.mkdir(parents=True,exist_ok=True)
        stage=Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp.",dir=target.parent))
        try:
            hashes=[]
            for index,model in enumerate(self.models):
                model_path=stage/f"regret_{index}.joblib"
                joblib.dump(model,model_path,compress=0,protocol=5)
                hashes.append(C.file_sha256(model_path))
            if tuple(hashes)!=self.model_file_sha256:
                raise RecoveryRefusal("histogram action serialized bytes changed")
            manifest={"schema":HISTOGRAM_ACTION_SCHEMA,"backend":self.backend,
                "feature_names":self.feature_names,"seed":self.seed,
                "config":asdict(self.config),
                "config_sha256":self.config.receipt_sha256,
                "objective":self.objective,
                "train_day_range":self.train_day_range,
                "validation_day_range":self.validation_day_range,
                "train_receipt_sha256":self.train_receipt_sha256,
                "validation_receipt_sha256":self.validation_receipt_sha256,
                "component_oof_receipt_sha256":self.component_oof_receipt_sha256,
                "shuffled_labels":self.shuffled_labels,
                "shuffle_seed":self.shuffle_seed,
                "model_file_sha256":tuple(hashes),
                "refit_all_pre_h2":self.refit_all_pre_h2,
                "iteration_selection_receipt_sha256":
                    self.iteration_selection_receipt_sha256,
                "receipt_sha256":self.receipt_sha256,"workers":16}
            C.atomic_json(stage/"manifest.json",manifest)
            atomic_replace_directory(stage,target)
        except Exception:
            shutil.rmtree(stage,ignore_errors=True);raise
        return C.file_sha256(target/"manifest.json")

    @classmethod
    def load(cls,path:str|Path)->"HistogramActionBundle":
        source=Path(path).resolve();C.guard_payload(source)
        try:value=json.loads((source/"manifest.json").read_text())
        except (OSError,UnicodeError,json.JSONDecodeError) as exc:
            raise RecoveryRefusal("cannot strict-load histogram action") from exc
        if value.get("schema")!=HISTOGRAM_ACTION_SCHEMA or value.get("workers")!=16:
            raise RecoveryRefusal("histogram action store schema differs")
        config=_config_from_mapping(value["config"])
        if config.receipt_sha256!=value.get("config_sha256"):
            raise RecoveryRefusal("histogram action config differs")
        hashes=tuple(map(str,value["model_file_sha256"]));models=[]
        for index,expected in enumerate(hashes):
            model_path=source/f"regret_{index}.joblib"
            if C.file_sha256(model_path)!=expected:
                raise RecoveryRefusal("histogram action model hash differs")
            models.append(joblib.load(model_path))
        result=cls(str(value["backend"]),tuple(value["feature_names"]),
            tuple(models),int(value["seed"]),config,str(value["objective"]),
            tuple(map(int,value["train_day_range"])),
            tuple(map(int,value["validation_day_range"])),
            str(value["train_receipt_sha256"]),
            str(value["validation_receipt_sha256"]),
            str(value["component_oof_receipt_sha256"]),
            bool(value["shuffled_labels"]),value["shuffle_seed"],hashes,
            str(value["receipt_sha256"]),bool(value["refit_all_pre_h2"]),
            value["iteration_selection_receipt_sha256"])
        result.__post_init__();return result


def fit_histogram_action_bundle(train:ActionTrainingMatrix,
        validation:ActionTrainingMatrix,*,backend:str,config:RecoveryConfig,
        seed:int,shuffled_labels:bool=False,
        shuffle_seed:int|None=None)->HistogramActionBundle:
    train.validate();validation.validate();backend=backend.upper();_chronology(train.day,validation.day)
    if (backend not in HISTOGRAM_BACKENDS
            or train.feature_names!=validation.feature_names
            or train.component_oof_receipt_sha256
               !=validation.component_oof_receipt_sha256
            or shuffled_labels!=(shuffle_seed is not None)
            or (shuffle_seed is not None
                and shuffle_seed not in config.shuffle_seeds)):
        raise RecoveryRefusal("histogram action backend/schema differs")
    models=[]
    for action in range(3):
        model=(_lgb_l2(config,seed+action) if backend=="LIGHTGBM"
               else _xgb_l2(config,seed+action))
        # Three L2 histogram heads preserve the identical transformed regret
        # targets used by CatBoost MultiRMSE.
        _fit_reg(model,backend,train.x,train.regret_log_target[:,action],
                 train.sample_weight,validation.x,
                 validation.regret_log_target[:,action],validation.sample_weight,
                 config.early_stopping_rounds);models.append(model)
    hashes=tuple(_serialized_joblib_sha256(model) for model in models)
    train_range=(int(np.min(train.day)),int(np.max(train.day)))
    validation_range=(int(np.min(validation.day)),int(np.max(validation.day)))
    core={"schema":HISTOGRAM_ACTION_SCHEMA,"backend":backend,
          "features":train.feature_names,"seed":seed,"config":config.receipt_sha256,
          "objective":"MultiRMSE","train_day_range":train_range,
          "validation_day_range":validation_range,"train":train.receipt_sha256,
          "validation":validation.receipt_sha256,
          "component_oof":train.component_oof_receipt_sha256,
          "shuffled_labels":shuffled_labels,"shuffle_seed":shuffle_seed,
          "model_files":hashes,"refit_all_pre_h2":False,
          "iteration_selection_receipt_sha256":None}
    result=HistogramActionBundle(backend,train.feature_names,tuple(models),seed,
        config,"MultiRMSE",train_range,validation_range,train.receipt_sha256,
        validation.receipt_sha256,train.component_oof_receipt_sha256,
        shuffled_labels,shuffle_seed,hashes,C.object_sha256(core))
    result.__post_init__();return result
def fit_all_pre_h2_histogram_action_bundle(matrix:ActionTrainingMatrix,* ,
        selection_bundle:HistogramActionBundle,config:RecoveryConfig,seed:int,
        expected_last_training_day:int)->HistogramActionBundle:
    matrix.validate();selection_bundle.__post_init__();config.__post_init__()
    if (selection_bundle.seed!=seed or selection_bundle.shuffled_labels
            or selection_bundle.refit_all_pre_h2
            or selection_bundle.feature_names!=matrix.feature_names
            or selection_bundle.component_oof_receipt_sha256
               !=matrix.component_oof_receipt_sha256
            or int(np.max(matrix.day))!=int(expected_last_training_day)
            or expected_last_training_day>=C.HOLDOUT_START_D8):
        raise RecoveryRefusal("histogram action refit inputs differ/seal opened")
    iterations=tuple(_selected_iterations(model,config)
                     for model in selection_bundle.models)
    selection=C.object_sha256({"schema":"QRE2TABHISTREFITITER1",
        "kind":"ACTION","selection_model":selection_bundle.receipt_sha256,
        "iterations":iterations,"all_pre_h2":True})
    models=[]
    for action,count in enumerate(iterations):
        model=(_lgb_l2(config,seed+action) if selection_bundle.backend=="LIGHTGBM"
               else _xgb_l2(config,seed+action))
        model.set_params(n_estimators=count,early_stopping_rounds=None)
        model.fit(matrix.x,matrix.regret_log_target[:,action],
                  sample_weight=matrix.sample_weight);models.append(model)
    hashes=tuple(_serialized_joblib_sha256(model) for model in models)
    train_range=(int(np.min(matrix.day)),int(np.max(matrix.day)))
    core={"schema":HISTOGRAM_ACTION_SCHEMA,"backend":selection_bundle.backend,
        "features":matrix.feature_names,"seed":seed,"config":config.receipt_sha256,
        "objective":"MultiRMSE","train_day_range":train_range,
        "validation_day_range":selection_bundle.validation_day_range,
        "train":matrix.receipt_sha256,"validation":selection_bundle.receipt_sha256,
        "component_oof":matrix.component_oof_receipt_sha256,
        "shuffled_labels":False,"shuffle_seed":None,"model_files":hashes,
        "refit_all_pre_h2":True,
        "iteration_selection_receipt_sha256":selection}
    result=HistogramActionBundle(selection_bundle.backend,matrix.feature_names,
        tuple(models),seed,config,"MultiRMSE",train_range,
        selection_bundle.validation_day_range,matrix.receipt_sha256,
        selection_bundle.receipt_sha256,matrix.component_oof_receipt_sha256,
        False,None,hashes,C.object_sha256(core),True,selection)
    result.__post_init__();return result

