"""Histogram-learner fallbacks for tabular recovery."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Final, Mapping

import joblib
import numpy as np

from . import common as C
from .tabular_atomic import atomic_replace_directory
from .tabular_models import (
    ActionModelBundle, ComponentArrayPredictions, _bounded_row_subset,
)
from .tabular_recovery_contracts import RecoveryConfig, RecoveryRefusal
from .tabular_training import (
    ActionTrainingMatrix, ComponentTrainingMatrix, VALUE_SCALE_USD,
    equal_portfolio_day_weights, matched_shuffle_action,
)


HISTOGRAM_BACKENDS: Final = ("LIGHTGBM", "XGBOOST")
HISTOGRAM_COMPONENT_SCHEMA: Final = "QRE2TABHISTCOMP2"
HISTOGRAM_ACTION_SCHEMA: Final = "QRE2TABHISTACTION2"
HISTOGRAM_COMPONENT_HEADS: Final = (
    "current_q20", "current_q50", "current_q80",
    "continuation_q20", "continuation_q50", "continuation_q80",
    "wall", "adverse_q90", "occupancy_q50", "occupancy_q90",
)

def _chronology(train:np.ndarray,validation:np.ndarray)->None:
    left=np.asarray(train,np.int64);right=np.asarray(validation,np.int64)
    if not len(left) or not len(right) or int(left.max())>=int(right.min()):
        raise RecoveryRefusal("histogram fallback chronology differs")


def _xgboost():
    pinned="/workspace/artifacts/cache/pylibs"
    if pinned not in sys.path:sys.path.insert(0,pinned)
    try:import xgboost
    except ImportError as exc:
        raise RecoveryRefusal("pinned XGBoost fallback is unavailable") from exc
    if xgboost.__version__!="3.4.0":
        raise RecoveryRefusal("XGBoost fallback version differs from the pin")
    return xgboost


def _config_from_mapping(value:Mapping[str,object])->RecoveryConfig:
    row=dict(value);row["real_seeds"]=tuple(map(int,row["real_seeds"]))
    row["shuffle_seeds"]=tuple(map(int,row["shuffle_seeds"]))
    result=RecoveryConfig(**row);result.__post_init__();return result


def _serialized_joblib_sha256(model:object)->str:
    descriptor,path=tempfile.mkstemp(prefix="entry-v2-hist-",suffix=".joblib")
    os.close(descriptor)
    try:
        joblib.dump(model,path,compress=0,protocol=5)
        return C.file_sha256(path)
    finally:
        try:os.unlink(path)
        except FileNotFoundError:pass


@dataclass(frozen=True,slots=True)
class HistogramComponentBundle:
    backend:str
    feature_names:tuple[str,...]
    models:Mapping[str,object]
    seed:int
    config:RecoveryConfig
    train_day_range:tuple[int,int]
    validation_day_range:tuple[int,int]
    train_receipt_sha256:str
    validation_receipt_sha256:str
    shuffled_labels:bool
    shuffle_seed:int|None
    model_file_sha256:Mapping[str,str]
    receipt_sha256:str
    refit_all_pre_h2:bool=False
    iteration_selection_receipt_sha256:str|None=None

    def __post_init__(self)->None:
        self.config.__post_init__()
        if (self.backend not in HISTOGRAM_BACKENDS
                or set(self.models)!=set(HISTOGRAM_COMPONENT_HEADS)
                or not self.feature_names or self.seed not in self.config.real_seeds
                or self.shuffled_labels!=(self.shuffle_seed is not None)
                or (self.shuffle_seed is not None
                    and self.shuffle_seed not in self.config.shuffle_seeds)
                or ((self.train_day_range[1]>=self.validation_day_range[0])
                    !=self.refit_all_pre_h2)
                or self.refit_all_pre_h2!=(
                    self.iteration_selection_receipt_sha256 is not None)
                or (self.iteration_selection_receipt_sha256 is not None
                    and len(self.iteration_selection_receipt_sha256)!=64)
                or (self.refit_all_pre_h2 and (
                    self.shuffled_labels
                    or self.train_day_range[1]>=C.HOLDOUT_START_D8))
                or set(self.model_file_sha256)!=set(HISTOGRAM_COMPONENT_HEADS)
                or not all(len(value)==64 for value in self.model_file_sha256.values())
                or not all(len(value)==64 for value in (
                    self.train_receipt_sha256,self.validation_receipt_sha256,
                    self.receipt_sha256))):
            raise RecoveryRefusal("histogram component bundle is malformed")
        core={"schema":HISTOGRAM_COMPONENT_SCHEMA,"backend":self.backend,
            "features":self.feature_names,"seed":self.seed,
            "config":self.config.receipt_sha256,
            "train_day_range":self.train_day_range,
            "validation_day_range":self.validation_day_range,
            "train":self.train_receipt_sha256,
            "validation":self.validation_receipt_sha256,
            "shuffled_labels":self.shuffled_labels,
            "shuffle_seed":self.shuffle_seed,
            "model_files":dict(self.model_file_sha256),
            "refit_all_pre_h2":self.refit_all_pre_h2,
            "iteration_selection_receipt_sha256":
                self.iteration_selection_receipt_sha256}
        if C.object_sha256(core)!=self.receipt_sha256:
            raise RecoveryRefusal("histogram component receipt differs")

    def predict(self,x:np.ndarray)->ComponentArrayPredictions:
        matrix=np.asarray(x,np.float32)
        if matrix.ndim!=2 or matrix.shape[1]!=len(self.feature_names):
            raise RecoveryRefusal("histogram component feature schema differs")
        def p(name:str)->np.ndarray:
            return np.asarray(self.models[name].predict(matrix),np.float64).reshape(-1)
        current=np.sort(np.sinh(np.clip(np.column_stack((p("current_q20"),
            p("current_q50"),p("current_q80"))),-20,20))*VALUE_SCALE_USD,axis=1)
        continuation=np.sort(np.sinh(np.clip(np.column_stack((p("continuation_q20"),
            p("continuation_q50"),p("continuation_q80"))),-20,20))*VALUE_SCALE_USD,axis=1)
        wall=np.asarray(self.models["wall"].predict_proba(matrix),np.float64)[:,1]
        occupancy=np.maximum(0,np.sort(np.column_stack((p("occupancy_q50"),
                                                         p("occupancy_q90"))),axis=1))
        result=ComponentArrayPredictions(np.column_stack((current,continuation,wall,
                                                           np.maximum(0,p("adverse_q90")),
                                                           occupancy)))
        result.validate();return result

    def save(self,path:str|Path)->str:
        self.__post_init__();target=C.assert_workspace_output(path)
        if target.exists():raise RecoveryRefusal("histogram component target exists")
        target.parent.mkdir(parents=True,exist_ok=True)
        stage=Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp.",dir=target.parent))
        try:
            files={}
            for name,model in self.models.items():
                model_path=stage/f"{name}.joblib"
                joblib.dump(model,model_path,compress=0,protocol=5)
                files[name]=C.file_sha256(model_path)
            if files!=dict(self.model_file_sha256):
                raise RecoveryRefusal("histogram component serialized bytes changed")
            manifest={"schema":HISTOGRAM_COMPONENT_SCHEMA,"backend":self.backend,
                "feature_names":self.feature_names,"seed":self.seed,
                "config":asdict(self.config),
                "config_sha256":self.config.receipt_sha256,
                "train_day_range":self.train_day_range,
                "validation_day_range":self.validation_day_range,
                "train_receipt_sha256":self.train_receipt_sha256,
                "validation_receipt_sha256":self.validation_receipt_sha256,
                "shuffled_labels":self.shuffled_labels,
                "shuffle_seed":self.shuffle_seed,
                "model_file_sha256":files,
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
    def load(cls,path:str|Path)->"HistogramComponentBundle":
        source=Path(path).resolve();C.guard_payload(source)
        try:value=json.loads((source/"manifest.json").read_text())
        except (OSError,UnicodeError,json.JSONDecodeError) as exc:
            raise RecoveryRefusal("cannot strict-load histogram component") from exc
        if value.get("schema")!=HISTOGRAM_COMPONENT_SCHEMA or value.get("workers")!=16:
            raise RecoveryRefusal("histogram component store schema differs")
        config=_config_from_mapping(value["config"])
        if config.receipt_sha256!=value.get("config_sha256"):
            raise RecoveryRefusal("histogram component config differs")
        models={};hashes=dict(value["model_file_sha256"])
        for name in HISTOGRAM_COMPONENT_HEADS:
            model_path=source/f"{name}.joblib"
            if C.file_sha256(model_path)!=hashes.get(name):
                raise RecoveryRefusal("histogram component model hash differs")
            models[name]=joblib.load(model_path)
        result=cls(str(value["backend"]),tuple(value["feature_names"]),
            MappingProxyType(models),int(value["seed"]),config,
            tuple(map(int,value["train_day_range"])),
            tuple(map(int,value["validation_day_range"])),
            str(value["train_receipt_sha256"]),
            str(value["validation_receipt_sha256"]),
            bool(value["shuffled_labels"]),value["shuffle_seed"],
            MappingProxyType({str(key):str(item) for key,item in hashes.items()}),
            str(value["receipt_sha256"]),bool(value["refit_all_pre_h2"]),
            value["iteration_selection_receipt_sha256"])
        result.__post_init__();return result


def _lgb_reg(config:RecoveryConfig,seed:int,alpha:float):
    import lightgbm as lgb
    return lgb.LGBMRegressor(objective="quantile",alpha=alpha,
        n_estimators=config.max_iterations,max_depth=config.depth,
        num_leaves=2**config.depth,learning_rate=config.learning_rate,
        reg_lambda=config.l2_leaf_reg,random_state=seed,n_jobs=config.workers,
        verbosity=-1)


def _xgb_reg(config:RecoveryConfig,seed:int,alpha:float):
    xgb=_xgboost()
    return xgb.XGBRegressor(objective="reg:quantileerror",quantile_alpha=alpha,
        n_estimators=config.max_iterations,max_depth=config.depth,
        learning_rate=config.learning_rate,reg_lambda=config.l2_leaf_reg,
        random_state=seed,n_jobs=config.workers,tree_method="hist",
        early_stopping_rounds=config.early_stopping_rounds)


def _lgb_l2(config:RecoveryConfig,seed:int):
    import lightgbm as lgb
    return lgb.LGBMRegressor(objective="regression",n_estimators=config.max_iterations,
        max_depth=config.depth,num_leaves=2**config.depth,
        learning_rate=config.learning_rate,reg_lambda=config.l2_leaf_reg,
        random_state=seed,n_jobs=config.workers,verbosity=-1)


def _xgb_l2(config:RecoveryConfig,seed:int):
    xgb=_xgboost()
    return xgb.XGBRegressor(objective="reg:squarederror",
        n_estimators=config.max_iterations,max_depth=config.depth,
        learning_rate=config.learning_rate,reg_lambda=config.l2_leaf_reg,
        random_state=seed,n_jobs=config.workers,tree_method="hist",
        early_stopping_rounds=config.early_stopping_rounds)


def _fit_reg(model:object,backend:str,x:np.ndarray,y:np.ndarray,w:np.ndarray,
             vx:np.ndarray,vy:np.ndarray,vw:np.ndarray,patience:int)->None:
    if backend=="LIGHTGBM":
        import lightgbm as lgb
        model.fit(x,y,sample_weight=w,eval_set=[(vx,vy)],eval_sample_weight=[vw],
                  callbacks=[lgb.early_stopping(patience,verbose=False),
                             lgb.log_evaluation(period=0)])
    else:
        model.fit(x,y,sample_weight=w,eval_set=[(vx,vy)],
                  sample_weight_eval_set=[vw],verbose=False)


def fit_histogram_component_bundle(train:ComponentTrainingMatrix,
        validation:ComponentTrainingMatrix,*,backend:str,config:RecoveryConfig,
        seed:int,shuffled_labels:bool=False,
        shuffle_seed:int|None=None)->HistogramComponentBundle:
    train.validate();validation.validate();config.__post_init__();backend=backend.upper()
    if (backend not in HISTOGRAM_BACKENDS
            or train.feature_names!=validation.feature_names
            or shuffled_labels!=(shuffle_seed is not None)
            or (shuffle_seed is not None
                and shuffle_seed not in config.shuffle_seeds)):
        raise RecoveryRefusal("histogram component backend/schema differs")
    _chronology(train.day,validation.day)
    x=np.asarray(train.x,np.float32);vx=np.asarray(validation.x,np.float32)
    quantiles={"current_q20":.2,"current_q50":.5,"current_q80":.8,
               "continuation_q20":.2,"continuation_q50":.5,"continuation_q80":.8,
               "adverse_q90":.9,"occupancy_q50":.5,"occupancy_q90":.9}
    keep=np.asarray(train.continuation_observed,bool)
    vkeep=np.asarray(validation.continuation_observed,bool)
    if not keep.any() or not vkeep.any():
        raise RecoveryRefusal("histogram continuation censored")
    models={}
    with (_bounded_row_subset(x,keep) as observed_x,
          _bounded_row_subset(vx,vkeep) as validation_observed_x):
        for name,alpha in quantiles.items():
            model=(_lgb_reg(config,seed,alpha) if backend=="LIGHTGBM"
                   else _xgb_reg(config,seed,alpha))
            if name.startswith("current"):
                y=train.current_asinh;vy=validation.current_asinh;tx=x;tvx=vx
                w=train.sample_weight;vw=validation.sample_weight
            elif name.startswith("continuation"):
                y=train.continuation_asinh[keep]
                vy=validation.continuation_asinh[vkeep]
                tx=observed_x;tvx=validation_observed_x
                w=equal_portfolio_day_weights(train.day[keep])
                vw=equal_portfolio_day_weights(validation.day[vkeep])
            elif name.startswith("adverse"):
                y=train.adverse_usd;vy=validation.adverse_usd;tx=x;tvx=vx
                w=train.sample_weight;vw=validation.sample_weight
            else:
                y=train.occupancy_sec;vy=validation.occupancy_sec;tx=x;tvx=vx
                w=train.sample_weight;vw=validation.sample_weight
            _fit_reg(model,backend,tx,y,w,tvx,vy,vw,
                     config.early_stopping_rounds)
            models[name]=model
    if len(np.unique(train.wall_target))!=2:
        raise RecoveryRefusal("histogram wall target is one-class")
    if backend=="LIGHTGBM":
        import lightgbm as lgb
        wall=lgb.LGBMClassifier(objective="binary",n_estimators=config.max_iterations,
            max_depth=config.depth,num_leaves=2**config.depth,
            learning_rate=config.learning_rate,reg_lambda=config.l2_leaf_reg,
            random_state=seed,n_jobs=config.workers,verbosity=-1)
        wall.fit(x,train.wall_target,sample_weight=train.sample_weight,
                 eval_set=[(vx,validation.wall_target)],
                 eval_sample_weight=[validation.sample_weight],
                 callbacks=[lgb.early_stopping(config.early_stopping_rounds,verbose=False),
                            lgb.log_evaluation(period=0)])
    else:
        xgb=_xgboost();wall=xgb.XGBClassifier(objective="binary:logistic",
            n_estimators=config.max_iterations,max_depth=config.depth,
            learning_rate=config.learning_rate,reg_lambda=config.l2_leaf_reg,
            random_state=seed,n_jobs=config.workers,tree_method="hist",
            early_stopping_rounds=config.early_stopping_rounds)
        wall.fit(x,train.wall_target,sample_weight=train.sample_weight,
                 eval_set=[(vx,validation.wall_target)],
                 sample_weight_eval_set=[validation.sample_weight],verbose=False)
    models["wall"]=wall
    hashes={name:_serialized_joblib_sha256(model) for name,model in models.items()}
    train_range=(int(np.min(train.day)),int(np.max(train.day)))
    validation_range=(int(np.min(validation.day)),int(np.max(validation.day)))
    core={"schema":HISTOGRAM_COMPONENT_SCHEMA,"backend":backend,
          "features":train.feature_names,"seed":seed,"config":config.receipt_sha256,
          "train_day_range":train_range,"validation_day_range":validation_range,
          "train":train.receipt_sha256,"validation":validation.receipt_sha256,
          "shuffled_labels":shuffled_labels,"shuffle_seed":shuffle_seed,
          "model_files":hashes,"refit_all_pre_h2":False,
          "iteration_selection_receipt_sha256":None}
    return HistogramComponentBundle(backend,train.feature_names,
        MappingProxyType(models),seed,config,train_range,validation_range,
        train.receipt_sha256,validation.receipt_sha256,shuffled_labels,
        shuffle_seed,MappingProxyType(hashes),C.object_sha256(core))
def _selected_iterations(model:object,config:RecoveryConfig)->int:
    value=getattr(model,"best_iteration_",None)
    if value is None:value=getattr(model,"best_iteration",None)
    if value is None:value=getattr(model,"n_estimators",None)
    count=int(value or 0)
    # XGBoost's best_iteration is zero-based; its configured estimator count is
    # an upper bound and adding one is harmless only for that attribute.
    if hasattr(model,"best_iteration") and not hasattr(model,"best_iteration_"):
        count+=1
    if not 0<count<=config.max_iterations:
        raise RecoveryRefusal("histogram iteration selection differs")
    return count


def _fixed_hist_reg(backend:str,config:RecoveryConfig,seed:int,alpha:float,
                    iterations:int)->object:
    model=(_lgb_reg(config,seed,alpha) if backend=="LIGHTGBM"
           else _xgb_reg(config,seed,alpha))
    model.set_params(n_estimators=iterations,early_stopping_rounds=None)
    return model


def fit_all_pre_h2_histogram_component_bundle(
        matrix:ComponentTrainingMatrix,*,
        selection_bundle:HistogramComponentBundle,config:RecoveryConfig,
        seed:int,expected_last_training_day:int)->HistogramComponentBundle:
    matrix.validate();selection_bundle.__post_init__();config.__post_init__()
    if (selection_bundle.seed!=seed or selection_bundle.shuffled_labels
            or selection_bundle.refit_all_pre_h2
            or selection_bundle.feature_names!=matrix.feature_names
            or int(np.max(matrix.day))!=int(expected_last_training_day)
            or expected_last_training_day>=C.HOLDOUT_START_D8):
        raise RecoveryRefusal("histogram component refit inputs differ/seal opened")
    iterations={name:_selected_iterations(model,config)
                for name,model in selection_bundle.models.items()}
    selection=C.object_sha256({"schema":"QRE2TABHISTREFITITER1",
        "kind":"COMPONENT","selection_model":selection_bundle.receipt_sha256,
        "iterations":iterations,"all_pre_h2":True})
    backend=selection_bundle.backend;models={};x=np.asarray(matrix.x,np.float32)
    quantiles={"current_q20":.2,"current_q50":.5,"current_q80":.8,
        "continuation_q20":.2,"continuation_q50":.5,"continuation_q80":.8,
        "adverse_q90":.9,"occupancy_q50":.5,"occupancy_q90":.9}
    keep=np.asarray(matrix.continuation_observed,bool)
    if not keep.any():raise RecoveryRefusal("histogram continuation censored")
    with _bounded_row_subset(x,keep) as observed_x:
        for name,alpha in quantiles.items():
            model=_fixed_hist_reg(backend,config,seed,alpha,iterations[name])
            if name.startswith("current"):
                tx=x;y=matrix.current_asinh;weight=matrix.sample_weight
            elif name.startswith("continuation"):
                tx=observed_x;y=matrix.continuation_asinh[keep]
                weight=equal_portfolio_day_weights(matrix.day[keep])
            elif name.startswith("adverse"):
                tx=x;y=matrix.adverse_usd;weight=matrix.sample_weight
            else:tx=x;y=matrix.occupancy_sec;weight=matrix.sample_weight
            model.fit(tx,y,sample_weight=weight);models[name]=model
    if len(np.unique(matrix.wall_target))!=2:
        raise RecoveryRefusal("histogram all-data wall target is one-class")
    if backend=="LIGHTGBM":
        import lightgbm as lgb
        wall=lgb.LGBMClassifier(objective="binary",n_estimators=iterations["wall"],
            max_depth=config.depth,num_leaves=2**config.depth,
            learning_rate=config.learning_rate,reg_lambda=config.l2_leaf_reg,
            random_state=seed,n_jobs=config.workers,verbosity=-1)
    else:
        xgb=_xgboost();wall=xgb.XGBClassifier(objective="binary:logistic",
            n_estimators=iterations["wall"],max_depth=config.depth,
            learning_rate=config.learning_rate,reg_lambda=config.l2_leaf_reg,
            random_state=seed,n_jobs=config.workers,tree_method="hist")
    wall.fit(x,matrix.wall_target,sample_weight=matrix.sample_weight);models["wall"]=wall
    hashes={name:_serialized_joblib_sha256(model) for name,model in models.items()}
    train_range=(int(np.min(matrix.day)),int(np.max(matrix.day)))
    core={"schema":HISTOGRAM_COMPONENT_SCHEMA,"backend":backend,
        "features":matrix.feature_names,"seed":seed,"config":config.receipt_sha256,
        "train_day_range":train_range,
        "validation_day_range":selection_bundle.validation_day_range,
        "train":matrix.receipt_sha256,"validation":selection_bundle.receipt_sha256,
        "shuffled_labels":False,"shuffle_seed":None,"model_files":hashes,
        "refit_all_pre_h2":True,
        "iteration_selection_receipt_sha256":selection}
    result=HistogramComponentBundle(backend,matrix.feature_names,
        MappingProxyType(models),seed,config,train_range,
        selection_bundle.validation_day_range,matrix.receipt_sha256,
        selection_bundle.receipt_sha256,False,None,MappingProxyType(hashes),
        C.object_sha256(core),True,selection)
    result.__post_init__();return result

