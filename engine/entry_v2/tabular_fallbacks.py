"""Precommitted failure-directed alternatives for tabular recovery."""

from __future__ import annotations

from dataclasses import dataclass
from bisect import bisect_left
from dataclasses import asdict
from datetime import datetime,timedelta
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
from types import MappingProxyType
from typing import Final, Mapping, Sequence

import numpy as np
import joblib
from scipy.stats import t as student_t

from . import common as C
from .tabular_atomic import atomic_replace_directory
from .tabular_models import (
    ActionModelBundle,ComponentArrayPredictions,_bounded_row_subset,
)
from .tabular_recovery_contracts import RecoveryConfig, RecoveryRefusal
from .tabular_training import (
    ActionTrainingMatrix, ComponentTrainingMatrix, VALUE_SCALE_USD,
    equal_portfolio_day_weights,matched_shuffle_action,
)


HISTOGRAM_BACKENDS: Final=("LIGHTGBM","XGBOOST")
HISTOGRAM_COMPONENT_SCHEMA:Final="QRE2TABHISTCOMP2"
HISTOGRAM_ACTION_SCHEMA:Final="QRE2TABHISTACTION2"
CAUSAL_EXPERT_SCHEMA:Final="QRE2TABCAUSALEXPERT2"
HISTOGRAM_COMPONENT_HEADS: Final=(
    "current_q20","current_q50","current_q80",
    "continuation_q20","continuation_q50","continuation_q80",
    "wall","adverse_q90","occupancy_q50","occupancy_q90")
FAILURE_BRANCHES:Final=("PRIMARY_PASS","PAIRWISE_ACTION","HISTOGRAM_LEARNERS",
    "CAUSAL_RELATION_ENCODING","REGRET_WEIGHTED_IMITATION",
    "STATE_CONDITIONED_CALIBRATION","CAUSAL_TRAILING_EXPERTS",
    "EXTEND_TO_600")


@dataclass(frozen=True,slots=True)
class FailureMeasurements:
    training_teacher_capture:float
    raw_oof_floor_pass:bool
    weakest_real_above_shuffle:bool
    value_ordering_transfers:bool
    action_conversion_retention:float
    calibration_threshold_floor_pass:bool
    conversion_retention:float
    consecutive_era_reversal:bool
    five_minute_incremental_ceiling_fraction:float

    def __post_init__(self)->None:
        values=(self.training_teacher_capture,self.action_conversion_retention,
                self.conversion_retention)
        if (any(not math.isfinite(value) for value in values)
                or not math.isfinite(
                    self.five_minute_incremental_ceiling_fraction)
                or self.five_minute_incremental_ceiling_fraction<0):
            raise RecoveryRefusal("failure-ladder measurements are malformed")


@dataclass(frozen=True,slots=True)
class FailureBranchDecision:
    branch:str
    reason:str
    measurements_receipt_sha256:str
    goal_lowered:bool
    terminal_null_allowed:bool
    receipt_sha256:str

    def __post_init__(self)->None:
        core={"schema":"QRE2TABFAILUREBRANCH1","branch":self.branch,
              "reason":self.reason,
              "measurements":self.measurements_receipt_sha256,
              "goal_lowered":self.goal_lowered,
              "terminal_null_allowed":self.terminal_null_allowed}
        if (self.branch not in FAILURE_BRANCHES or not self.reason
                or self.goal_lowered or self.terminal_null_allowed
                or C.object_sha256(core)!=self.receipt_sha256):
            raise RecoveryRefusal("failure-ladder branch receipt differs")


def select_failure_branch(measured:FailureMeasurements,* ,
                          config:RecoveryConfig)->FailureBranchDecision:
    """Select the single precommitted implementation branch from evidence."""

    measured.__post_init__();config.__post_init__()
    measurement_core={"schema":"QRE2TABFAILUREMEASURE1",**{
        name:getattr(measured,name) for name in measured.__dataclass_fields__}}
    measurement_receipt=C.object_sha256(measurement_core)
    if measured.five_minute_incremental_ceiling_fraction>.10:
        branch,reason="EXTEND_TO_600","FIVE_MINUTE_RIGHT_CENSOR_TRIGGER"
    elif measured.training_teacher_capture<config.target_ceiling_capture:
        branch,reason="HISTOGRAM_LEARNERS","TRAINING_TEACHER_CAPTURE_BELOW_90_PERCENT"
    elif not measured.raw_oof_floor_pass:
        if not measured.weakest_real_above_shuffle:
            branch,reason=("CAUSAL_RELATION_ENCODING",
                "OOF_APPROACHES_MATCHED_SHUFFLE")
        else:
            branch,reason=("PAIRWISE_ACTION",
                "RAW_CATBOOST_CEILING_BELOW_FLOOR_WITH_TRAINING_CAPTURE")
    elif (measured.value_ordering_transfers
          and measured.action_conversion_retention
              <config.minimum_conversion_retention):
        branch,reason=("REGRET_WEIGHTED_IMITATION",
            "ENTER_DEFER_PASS_CONVERSION_LOST_ECONOMICS")
    elif (not measured.calibration_threshold_floor_pass
          or measured.conversion_retention<config.minimum_conversion_retention):
        branch,reason=("STATE_CONDITIONED_CALIBRATION",
            "RAW_SCORE_PASSES_BUT_MAPPER_OR_THRESHOLD_FAILS")
    elif measured.consecutive_era_reversal:
        branch,reason=("CAUSAL_TRAILING_EXPERTS",
            "CONSECUTIVE_ERA_EFFECT_REVERSAL")
    else:
        branch,reason="PRIMARY_PASS","ALL_REGISTERED_BOUNDARIES_PASS"
    core={"schema":"QRE2TABFAILUREBRANCH1","branch":branch,"reason":reason,
          "measurements":measurement_receipt,"goal_lowered":False,
          "terminal_null_allowed":False}
    result=FailureBranchDecision(branch,reason,measurement_receipt,False,False,
                                 C.object_sha256(core))
    result.__post_init__();return result


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


@dataclass(frozen=True,slots=True)
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


@dataclass(frozen=True,slots=True)
class ExpertRoutingTable:
    day:tuple[int,...]
    selected_expert:tuple[str,...]
    source_receipt_sha256:str
    receipt_sha256:str

    def __post_init__(self)->None:
        if (not self.day or len(self.day)!=len(self.selected_expert)
                or tuple(sorted(set(self.day)))!=self.day
                or len(self.source_receipt_sha256)!=64
                or len(self.receipt_sha256)!=64
                or any(value not in {"FULL","TRAILING_360","TRAILING_90"}
                       for value in self.selected_expert)):
            raise RecoveryRefusal("expert routing table is malformed")
        core={"schema":"QRE2TABEXPERTROUTER1","day":self.day,
            "selected_expert":self.selected_expert,
            "source":self.source_receipt_sha256,
            "uses_current_or_future_loss":False}
        if C.object_sha256(core)!=self.receipt_sha256:
            raise RecoveryRefusal("expert routing table receipt differs")

    def expert_for_day(self,trading_day:int)->str:
        C.guard_date(int(trading_day))
        point=bisect_left(self.day,int(trading_day))
        if point>=len(self.day) or self.day[point]!=int(trading_day):point-=1
        if point<0:raise RecoveryRefusal("expert router has no strictly prior loss")
        return self.selected_expert[point]


@dataclass(frozen=True,slots=True)
class CausalExpertActionEnsemble:
    experts:Mapping[str,ActionModelBundle]
    routing:ExpertRoutingTable
    expert_paths:Mapping[str,str]
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
    receipt_sha256:str
    refit_all_pre_h2:bool=False
    iteration_selection_receipt_sha256:str|None=None

    def __post_init__(self)->None:
        self.config.__post_init__();names={"FULL","TRAILING_360","TRAILING_90"}
        if set(self.experts)!=names:
            raise RecoveryRefusal("causal action expert roster differs")
        if (set(self.expert_paths)!=names or self.seed not in self.config.real_seeds
                or self.objective not in {"MultiRMSE","PairLogitPairwise","MultiClass"}
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
                or not all(len(value)==64 for value in (
                    self.train_receipt_sha256,self.validation_receipt_sha256,
                    self.component_oof_receipt_sha256,self.receipt_sha256))):
            raise RecoveryRefusal("causal expert ensemble metadata differs")
        schemas={value.feature_names for value in self.experts.values()}
        if len(schemas)!=1:raise RecoveryRefusal("causal action expert schemas differ")
        if any(value.seed!=self.seed or value.objective!=self.objective
               or value.shuffled_labels!=self.shuffled_labels
               or value.shuffle_seed!=self.shuffle_seed
               or value.component_oof_receipt_sha256
                  !=self.component_oof_receipt_sha256
               or value.refit_all_pre_h2!=self.refit_all_pre_h2
               for value in self.experts.values()):
            raise RecoveryRefusal("causal expert member identity differs")
        # Paths are publication locations, not model identity.  Only the
        # strictly verified member receipts enter the ensemble identity so an
        # accepted ensemble can be copied into a self-contained policy bundle
        # without changing its predictions or calibration binding.
        core={"schema":CAUSAL_EXPERT_SCHEMA,
            "expert_receipts":{key:value.receipt_sha256
                               for key,value in self.experts.items()},
            "routing":asdict(self.routing),"seed":self.seed,
            "config":self.config.receipt_sha256,"objective":self.objective,
            "train_day_range":self.train_day_range,
            "validation_day_range":self.validation_day_range,
            "train":self.train_receipt_sha256,
            "validation":self.validation_receipt_sha256,
            "component_oof":self.component_oof_receipt_sha256,
            "shuffled_labels":self.shuffled_labels,
            "shuffle_seed":self.shuffle_seed,
            "refit_all_pre_h2":self.refit_all_pre_h2,
            "iteration_selection_receipt_sha256":
                self.iteration_selection_receipt_sha256}
        if C.object_sha256(core)!=self.receipt_sha256:
            raise RecoveryRefusal("causal expert ensemble receipt differs")

    @property
    def day_routed(self)->bool:return True

    @property
    def feature_names(self)->tuple[str,...]:
        return self.experts["FULL"].feature_names

    def predict_regret_usd(self,x:np.ndarray,*,trading_day:int)->np.ndarray:
        name=self.routing.expert_for_day(trading_day)
        return self.experts[name].predict_regret_usd(x)

    def save(self,path:str|Path)->str:
        self.__post_init__();target=C.assert_workspace_output(path)
        if target.exists():raise RecoveryRefusal("causal expert target exists")
        target.parent.mkdir(parents=True,exist_ok=True)
        stage=Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp.",dir=target.parent))
        try:
            stored_paths={}
            for name in ("FULL","TRAILING_360","TRAILING_90"):
                relative=Path("members")/name.lower()
                member_source=Path(self.expert_paths[name]).resolve()
                C.guard_payload(member_source)
                source_model=ActionModelBundle.load(member_source)
                if source_model.receipt_sha256!=self.experts[name].receipt_sha256:
                    raise RecoveryRefusal("causal expert source member differs")
                # CatBoost does not promise byte-identical output when a
                # loaded model is serialized a second time.  Copy the already
                # receipt-verified directory instead of reserializing it.
                shutil.copytree(member_source,stage/relative)
                stored=ActionModelBundle.load(stage/relative)
                if stored.receipt_sha256!=self.experts[name].receipt_sha256:
                    raise RecoveryRefusal("causal expert copied member differs")
                stored_paths[name]=str(relative)
            core={"schema":CAUSAL_EXPERT_SCHEMA,
                "expert_receipts":{key:value.receipt_sha256
                                   for key,value in self.experts.items()},
                "routing":asdict(self.routing),"seed":self.seed,
                "config":self.config.receipt_sha256,"objective":self.objective,
                "train_day_range":self.train_day_range,
                "validation_day_range":self.validation_day_range,
                "train":self.train_receipt_sha256,
                "validation":self.validation_receipt_sha256,
                "component_oof":self.component_oof_receipt_sha256,
                "shuffled_labels":self.shuffled_labels,
                "shuffle_seed":self.shuffle_seed,
                "refit_all_pre_h2":self.refit_all_pre_h2,
                "iteration_selection_receipt_sha256":
                    self.iteration_selection_receipt_sha256}
            C.atomic_json(stage/"manifest.json",{**core,
                "expert_paths":stored_paths,
                "config_detail":asdict(self.config),
                "receipt_sha256":self.receipt_sha256,"workers":16})
            atomic_replace_directory(stage,target)
        except Exception:
            shutil.rmtree(stage,ignore_errors=True);raise
        return C.file_sha256(target/"manifest.json")

    @classmethod
    def load(cls,path:str|Path)->"CausalExpertActionEnsemble":
        source=Path(path).resolve();C.guard_payload(source)
        try:value=json.loads((source/"manifest.json").read_text())
        except (OSError,UnicodeError,json.JSONDecodeError) as exc:
            raise RecoveryRefusal("cannot strict-load causal experts") from exc
        if value.get("schema")!=CAUSAL_EXPERT_SCHEMA or value.get("workers")!=16:
            raise RecoveryRefusal("causal expert store schema differs")
        config=_config_from_mapping(value["config_detail"])
        if config.receipt_sha256!=value.get("config"):
            raise RecoveryRefusal("causal expert config differs")
        raw_paths={str(key):str(item)
                   for key,item in dict(value["expert_paths"]).items()}
        paths={key:str((source/item).resolve()) if not Path(item).is_absolute()
               else str(Path(item).resolve()) for key,item in raw_paths.items()}
        experts={key:ActionModelBundle.load(path_value)
                 for key,path_value in paths.items()}
        if {key:row.receipt_sha256 for key,row in experts.items()}!={
                str(key):str(item) for key,item in
                dict(value["expert_receipts"]).items()}:
            raise RecoveryRefusal("causal expert member receipt differs")
        raw=dict(value["routing"]);raw["day"]=tuple(map(int,raw["day"]))
        raw["selected_expert"]=tuple(map(str,raw["selected_expert"]))
        routing=ExpertRoutingTable(**raw);routing.__post_init__()
        receipt_core={key:item for key,item in value.items()
                      if key not in {"expert_paths","config_detail",
                                     "receipt_sha256","workers"}}
        if C.object_sha256(receipt_core)!=value.get("receipt_sha256"):
            raise RecoveryRefusal("causal expert stored identity differs")
        result=cls(MappingProxyType(experts),routing,MappingProxyType(paths),
            int(value["seed"]),config,str(value["objective"]),
            tuple(map(int,value["train_day_range"])),
            tuple(map(int,value["validation_day_range"])),str(value["train"]),
            str(value["validation"]),str(value["component_oof"]),
            bool(value["shuffled_labels"]),value["shuffle_seed"],
            str(value["receipt_sha256"]),bool(value["refit_all_pre_h2"]),
            value["iteration_selection_receipt_sha256"])
        result.__post_init__();return result


def build_causal_expert_routing(day:np.ndarray,loss_by_expert:Mapping[str,np.ndarray],
                                *,source_receipt_sha256:str)->ExpertRoutingTable:
    days=np.asarray(day,np.int64);names=("FULL","TRAILING_360","TRAILING_90")
    if set(loss_by_expert)!=set(names) or len(np.unique(days))!=len(days):
        raise RecoveryRefusal("expert routing loss table differs")
    losses={name:np.asarray(loss_by_expert[name],np.float64) for name in names}
    if any(value.shape!=days.shape or not np.all(np.isfinite(value)) for value in losses.values()):
        raise RecoveryRefusal("expert routing loss vector is malformed")
    order=np.argsort(days);days=days[order];selected=[]
    for index in range(len(days)):
        if index==0:selected.append("FULL");continue
        left=max(0,index-90)
        means={name:float(losses[name][order][left:index].mean()) for name in names}
        selected.append(min(names,key=lambda name:(means[name],names.index(name))))
    core={"schema":"QRE2TABEXPERTROUTER1","day":tuple(map(int,days)),
          "selected_expert":tuple(selected),"source":source_receipt_sha256,
          "uses_current_or_future_loss":False}
    return ExpertRoutingTable(tuple(map(int,days)),tuple(selected),source_receipt_sha256,
                              C.object_sha256(core))


def _calendar_cutoff(day:int,lookback_days:int)->int:
    stamp=datetime.strptime(str(int(day)),"%Y%m%d").date()-timedelta(
        days=int(lookback_days)-1)
    return int(stamp.strftime("%Y%m%d"))


def _load_or_fit_catboost_action(path:Path,train:ActionTrainingMatrix,
        validation:ActionTrainingMatrix,*,objective:str,config:RecoveryConfig,
        seed:int,shuffled_labels:bool,shuffle_seed:int|None)->ActionModelBundle:
    from .tabular_models import (
        fit_action_bundle,fit_pairwise_action_bundle,
    )
    if path.is_dir():
        result=ActionModelBundle.load(path)
        if (result.train_receipt_sha256!=train.receipt_sha256
                or result.validation_receipt_sha256!=validation.receipt_sha256
                or result.objective!=objective or result.seed!=seed
                or result.shuffled_labels!=shuffled_labels
                or result.shuffle_seed!=shuffle_seed):
            raise RecoveryRefusal("resumed causal expert member differs")
        return result
    result=(fit_pairwise_action_bundle(train,validation,config=config,seed=seed,
                shuffled_labels=shuffled_labels,shuffle_seed=shuffle_seed)
            if objective=="PairLogitPairwise" else
            fit_action_bundle(train,validation,config=config,seed=seed,
                objective=objective,shuffled_labels=shuffled_labels,
                shuffle_seed=shuffle_seed))
    result.save(path);stored=ActionModelBundle.load(path)
    if stored.receipt_sha256!=result.receipt_sha256:
        raise RecoveryRefusal("causal expert member strict reload differs")
    return stored


def fit_causal_expert_action_seed(*,matrix:ActionTrainingMatrix,
        chronology:object,config:RecoveryConfig,seed:int,output_root:str|Path,
        objective:str="MultiRMSE",shuffled_labels:bool=False,
        shuffle_seed:int|None=None)->object:
    """Fit a causal full/360d/90d action ensemble for every OOF fold."""

    from .tabular_experiment import EXPERIMENT_SCHEMA,FittedFold,SeedModelRoster
    matrix.validate();chronology.__post_init__();config.__post_init__()
    if (objective not in {"MultiRMSE","PairLogitPairwise","MultiClass"}
            or shuffled_labels!=(shuffle_seed is not None)):
        raise RecoveryRefusal("causal expert objective/control identity differs")
    root=C.assert_workspace_output(output_root);folds=[]
    lane="shuffle" if shuffled_labels else "real"
    for (name,train_lo,train_hi,val_lo,val_hi,score_lo,score_hi
         ) in chronology.action_folds:
        base_train=matrix.mask((np.asarray(matrix.day)>=train_lo)
                               &(np.asarray(matrix.day)<=train_hi))
        validation=matrix.mask((np.asarray(matrix.day)>=val_lo)
                               &(np.asarray(matrix.day)<=val_hi))
        route=matrix.mask((np.asarray(matrix.day)>=val_lo)
                          &(np.asarray(matrix.day)<=score_hi))
        if shuffled_labels:
            assert shuffle_seed is not None
            base_train=matched_shuffle_action(base_train,seed=shuffle_seed)
            validation=matched_shuffle_action(validation,seed=shuffle_seed)
            route=matched_shuffle_action(route,seed=shuffle_seed)
        member_matrices={"FULL":base_train}
        for expert,lookback in (("TRAILING_360",360),("TRAILING_90",90)):
            cutoff=_calendar_cutoff(train_hi,lookback)
            selected=np.asarray(base_train.day,np.int64)>=cutoff
            if not selected.any():
                raise RecoveryRefusal("causal expert trailing window is empty")
            member_matrices[expert]=base_train.mask(selected)
        experts={};paths={}
        fold_root=root/lane/f"seed_{seed}"/name
        for expert in ("FULL","TRAILING_360","TRAILING_90"):
            member_path=fold_root/"members"/expert.lower()
            experts[expert]=_load_or_fit_catboost_action(member_path,
                member_matrices[expert],validation,objective=objective,
                config=config,seed=seed,shuffled_labels=shuffled_labels,
                shuffle_seed=shuffle_seed)
            paths[expert]=str(member_path)
        route_days=np.unique(np.asarray(route.day,np.int64));losses={}
        exact=np.asarray(route.regret_cents,np.float64)/100.0
        for expert,model in experts.items():
            predicted=np.asarray(model.predict_regret_usd(route.x),np.float64)
            losses[expert]=np.asarray([float(np.average(
                np.mean(np.abs(predicted[np.asarray(route.day)==day]
                               -exact[np.asarray(route.day)==day]),axis=1),
                weights=np.asarray(route.sample_weight)[np.asarray(route.day)==day]))
                for day in route_days],np.float64)
        routing_source=C.object_sha256({"schema":"QRE2TABEXPERTLOSS1",
            "fold":name,"route_matrix":route.receipt_sha256,
            "expert_receipts":{key:value.receipt_sha256
                               for key,value in experts.items()},
            "days":tuple(map(int,route_days)),
            "losses":{key:tuple(map(float,value))
                      for key,value in losses.items()},
            "loss":"DAY_WEIGHTED_MEAN_ABSOLUTE_REGRET_USD",
            "strictly_prior_routing":True})
        routing=build_causal_expert_routing(route_days,losses,
            source_receipt_sha256=routing_source)
        train_receipt=C.object_sha256({"schema":"QRE2TABEXPERTTRAIN1",
            "members":{key:value.receipt_sha256 for key,value in experts.items()}})
        validation_receipt=C.object_sha256({"schema":"QRE2TABEXPERTVALID1",
            "validation":validation.receipt_sha256,"routing":routing.receipt_sha256})
        core={"schema":CAUSAL_EXPERT_SCHEMA,
            "expert_receipts":{key:value.receipt_sha256
                               for key,value in experts.items()},
            "routing":asdict(routing),"seed":seed,
            "config":config.receipt_sha256,"objective":objective,
            "train_day_range":(int(np.min(base_train.day)),
                               int(np.max(base_train.day))),
            "validation_day_range":(int(np.min(validation.day)),
                                    int(np.max(validation.day))),
            "train":train_receipt,"validation":validation_receipt,
            "component_oof":matrix.component_oof_receipt_sha256,
            "shuffled_labels":shuffled_labels,"shuffle_seed":shuffle_seed,
            "refit_all_pre_h2":False,
            "iteration_selection_receipt_sha256":None}
        ensemble=CausalExpertActionEnsemble(MappingProxyType(experts),routing,
            MappingProxyType(paths),seed,config,objective,
            tuple(core["train_day_range"]),tuple(core["validation_day_range"]),
            train_receipt,validation_receipt,matrix.component_oof_receipt_sha256,
            shuffled_labels,shuffle_seed,C.object_sha256(core))
        bundle_path=fold_root/"ensemble";ensemble.save(bundle_path)
        stored=CausalExpertActionEnsemble.load(bundle_path)
        if stored.receipt_sha256!=ensemble.receipt_sha256:
            raise RecoveryRefusal("causal expert ensemble strict reload differs")
        folds.append(FittedFold("ACTION","CAUSAL_EXPERTS",name,
            (score_lo,score_hi),seed,shuffled_labels,shuffle_seed,
            str(bundle_path),stored.receipt_sha256,None,None))
    roster_core={"schema":EXPERIMENT_SCHEMA,"kind":"ACTION",
        "learner_backend":"CAUSAL_EXPERTS","seed":seed,
        "shuffled_labels":shuffled_labels,"shuffle_seed":shuffle_seed,
        "folds":tuple(asdict(row) for row in folds),
        "chronology":chronology.receipt_sha256,"objective":objective,
        "component_predictions":matrix.component_oof_receipt_sha256}
    result=SeedModelRoster("ACTION","CAUSAL_EXPERTS",seed,
        shuffled_labels,shuffle_seed,tuple(folds),chronology.receipt_sha256,
        objective,matrix.component_oof_receipt_sha256,
        C.object_sha256(roster_core))
    result.__post_init__();return result


def fit_all_pre_h2_causal_expert_action_bundle(
        matrix:ActionTrainingMatrix,*,
        selection_bundle:CausalExpertActionEnsemble,config:RecoveryConfig,
        seed:int,expected_last_training_day:int,output_root:str|Path
        )->CausalExpertActionEnsemble:
    """Refit all three fixed experts while preserving the causal OOF router."""

    from .tabular_models import fit_all_pre_h2_action_bundle
    matrix.validate();selection_bundle.__post_init__();config.__post_init__()
    if (selection_bundle.seed!=seed or selection_bundle.shuffled_labels
            or selection_bundle.refit_all_pre_h2
            or selection_bundle.feature_names!=matrix.feature_names
            or selection_bundle.component_oof_receipt_sha256
               !=matrix.component_oof_receipt_sha256
            or int(np.max(matrix.day))!=int(expected_last_training_day)
            or expected_last_training_day>=C.HOLDOUT_START_D8):
        raise RecoveryRefusal("causal expert all-data inputs differ/seal opened")
    member_matrices={"FULL":matrix}
    for expert,lookback in (("TRAILING_360",360),("TRAILING_90",90)):
        cutoff=_calendar_cutoff(expected_last_training_day,lookback)
        selected=np.asarray(matrix.day,np.int64)>=cutoff
        if not selected.any():raise RecoveryRefusal("causal expert refit window empty")
        member_matrices[expert]=matrix.mask(selected)
    root=C.assert_workspace_output(output_root);experts={};paths={}
    for expert in ("FULL","TRAILING_360","TRAILING_90"):
        bundle=fit_all_pre_h2_action_bundle(member_matrices[expert],
            selection_bundle=selection_bundle.experts[expert],config=config,
            seed=seed,expected_last_training_day=expected_last_training_day)
        path=root/expert.lower()
        if path.is_dir():
            stored=ActionModelBundle.load(path)
            if stored.receipt_sha256!=bundle.receipt_sha256:
                raise RecoveryRefusal("resumed causal expert refit differs")
        else:
            bundle.save(path);stored=ActionModelBundle.load(path)
        experts[expert]=stored;paths[expert]=str(path)
    iteration_selection=C.object_sha256({"schema":"QRE2TABEXPERTREFITITER1",
        "selection_ensemble":selection_bundle.receipt_sha256,
        "members":{key:value.iteration_selection_receipt_sha256
                   for key,value in experts.items()},"all_pre_h2":True})
    train_receipt=C.object_sha256({"schema":"QRE2TABEXPERTREFITTRAIN1",
        "members":{key:value.receipt_sha256 for key,value in experts.items()}})
    train_range=(int(np.min(matrix.day)),int(np.max(matrix.day)))
    core={"schema":CAUSAL_EXPERT_SCHEMA,
        "expert_receipts":{key:value.receipt_sha256
                           for key,value in experts.items()},
        "routing":asdict(selection_bundle.routing),"seed":seed,
        "config":config.receipt_sha256,"objective":selection_bundle.objective,
        "train_day_range":train_range,
        "validation_day_range":selection_bundle.validation_day_range,
        "train":train_receipt,"validation":selection_bundle.receipt_sha256,
        "component_oof":matrix.component_oof_receipt_sha256,
        "shuffled_labels":False,"shuffle_seed":None,
        "refit_all_pre_h2":True,
        "iteration_selection_receipt_sha256":iteration_selection}
    result=CausalExpertActionEnsemble(MappingProxyType(experts),
        selection_bundle.routing,MappingProxyType(paths),seed,config,
        selection_bundle.objective,train_range,
        selection_bundle.validation_day_range,train_receipt,
        selection_bundle.receipt_sha256,matrix.component_oof_receipt_sha256,
        False,None,C.object_sha256(core),True,iteration_selection)
    result.__post_init__();return result


def effect_reversal_trigger(era_effects:Sequence[np.ndarray])->Mapping[str,object]:
    if len(era_effects)<2:raise RecoveryRefusal("effect reversal needs two eras")
    intervals=[]
    for raw in era_effects:
        values=np.asarray(raw,np.float64)
        if len(values)<2 or not np.all(np.isfinite(values)):
            raise RecoveryRefusal("era effects lack day clusters")
        half=float(student_t.ppf(.975,len(values)-1)*values.std(ddof=1)/math.sqrt(len(values)))
        intervals.append((float(values.mean()-half),float(values.mean()+half)))
    reversal=False
    for left,right in zip(intervals,intervals[1:]):
        if (left[0]>0 and right[1]<0) or (left[1]<0 and right[0]>0):reversal=True
    core={"schema":"QRE2TABREVERSAL1","intervals":tuple(intervals),
          "consecutive_excluding_zero_reversal":reversal,
          "activate_causal_experts":reversal}
    return MappingProxyType({**core,"receipt_sha256":C.object_sha256(core)})


def identify_unstable_absolute_features(matrix:ComponentTrainingMatrix,* ,
        chronology:object)->Mapping[str,object]:
    """Register every drifting continuous absolute level; never cap the roster."""

    matrix.validate();chronology.__post_init__();x=np.asarray(matrix.x)
    target=np.asarray(matrix.current_asinh,np.float64);days=np.asarray(matrix.day,np.int64)
    categorical_tokens=("mask","flag","count","ordinal","side","phase",
                        "weekday","month","hour","minute","second","age")
    candidates=[];detail={}
    for column,name in enumerate(matrix.feature_names):
        lower=name.lower();values=np.asarray(x[:,column],np.float64)
        if (lower.startswith("relation_") or any(token in lower
                for token in categorical_tokens) or len(np.unique(values))<50):
            continue
        era_rows=[];effect_signs=[]
        for era,lo,hi in chronology.oof_blocks:
            local=(days>=lo)&(days<=hi)
            if np.count_nonzero(local)<20 or np.ptp(values[local])<=0:continue
            era_values=values[local];era_target=target[local]
            scale=float(np.subtract(*np.percentile(era_values,[75,25])))
            covariance=float(np.mean((era_values-era_values.mean())*
                                     (era_target-era_target.mean())))
            effect_signs.append(int(np.sign(covariance)))
            era_rows.append((str(era),float(np.median(era_values)),scale,
                             covariance))
        if len(era_rows)<2:continue
        medians=np.asarray([row[1] for row in era_rows],np.float64)
        scales=np.asarray([row[2] for row in era_rows],np.float64)
        typical=max(float(np.median(scales[scales>0])) if np.any(scales>0) else 0.0,
                    1e-12)
        distribution_drift=float(np.ptp(medians))/typical
        sign_reversal=(1 in effect_signs and -1 in effect_signs)
        # This threshold is a registered unitless distribution diagnostic, not
        # a feature-count selector.  Every feature satisfying it is retained as
        # causal relations and its unstable absolute version is removed.
        unstable=distribution_drift>=1.0 or sign_reversal
        if unstable:
            candidates.append(name);detail[name]={"eras":tuple(era_rows),
                "median_range_over_typical_iqr":distribution_drift,
                "effect_sign_reversal":sign_reversal}
    selected=tuple(candidates)
    if not selected:
        raise RecoveryRefusal("relation branch found no proven unstable absolute level")
    core={"schema":"QRE2TABUNSTABLEABSOLUTE1",
        "matrix":matrix.receipt_sha256,"chronology":chronology.receipt_sha256,
        "selection_rule":"MEDIAN_RANGE_GE_ONE_TYPICAL_IQR_OR_EFFECT_SIGN_REVERSAL",
        "selected":selected,"detail":detail,"feature_cap":None,
        "h2_open_count":0}
    return MappingProxyType({**core,"receipt_sha256":C.object_sha256(core)})


__all__=["CausalExpertActionEnsemble","ExpertRoutingTable",
         "CAUSAL_EXPERT_SCHEMA",
         "FAILURE_BRANCHES","FailureBranchDecision","FailureMeasurements",
         "HISTOGRAM_ACTION_SCHEMA","HISTOGRAM_COMPONENT_SCHEMA",
         "HistogramActionBundle","HistogramComponentBundle",
         "build_causal_expert_routing","effect_reversal_trigger",
         "fit_causal_expert_action_seed",
         "fit_all_pre_h2_histogram_action_bundle",
         "fit_all_pre_h2_histogram_component_bundle",
         "fit_all_pre_h2_causal_expert_action_bundle",
         "fit_histogram_action_bundle","fit_histogram_component_bundle",
         "identify_unstable_absolute_features"]
