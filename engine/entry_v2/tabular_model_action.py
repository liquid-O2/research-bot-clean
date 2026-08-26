"""CatBoost portfolio-action model bundle for Entry V2."""

from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Final

import catboost
from catboost import (
    CatBoostClassifier, CatBoostRanker, CatBoostRegressor, Pool,
)
import numpy as np

from . import common as C
from .tabular_atomic import atomic_replace_directory
from .tabular_fit_backends import (
    fit_receipt_backend_fields, fit_receipt_law_fields,
)
from .tabular_model_fit import (
    _assert_chronological, _common_parameters, _config_from_json, _fixed_fit,
    _fit_with_early_stop, _head_model, _sha, _serialized_model_sha256,
    catboost_predict_threads,
)
from .tabular_recovery_contracts import (
    RecoveryConfig, RecoveryRefusal, VALUE_SCALE_USD,
)
from .tabular_training import ActionTrainingMatrix

ACTION_MODEL_SCHEMA: Final = "QRE2TABACTIONCB3"

class ActionModelBundle:
    def __init__(
        self, *, config: RecoveryConfig, seed: int, feature_names: tuple[str, ...],
        model: object, objective: str, train_receipt_sha256: str,
        validation_receipt_sha256: str, component_oof_receipt_sha256: str,
        train_day_range: tuple[int,int],validation_day_range: tuple[int,int],
        shuffled_labels: bool, shuffle_seed: int | None, receipt_sha256: str,
        model_file_sha256:str,
        refit_all_pre_h2:bool=False,
        iteration_selection_receipt_sha256:str|None=None,
    ) -> None:
        config.__post_init__()
        chronology_valid=(
            train_day_range[1]>=validation_day_range[0]
            if refit_all_pre_h2
            else train_day_range[1]<validation_day_range[0])
        if (objective not in {"MultiRMSE", "PairLogitPairwise", "MultiClass"}
                or not feature_names or seed not in config.real_seeds
                or shuffled_labels != (shuffle_seed is not None)
                or (shuffle_seed is not None
                    and shuffle_seed not in config.shuffle_seeds)
                or len(train_day_range)!=2 or len(validation_day_range)!=2
                or train_day_range[0]>train_day_range[1]
                or validation_day_range[0]>validation_day_range[1]
                or not chronology_valid
                or refit_all_pre_h2!=(iteration_selection_receipt_sha256
                                     is not None)
                or (iteration_selection_receipt_sha256 is not None
                    and not _sha(iteration_selection_receipt_sha256))
                or (refit_all_pre_h2 and (
                    shuffled_labels or train_day_range[1]>=C.HOLDOUT_START_D8))
                or not _sha(model_file_sha256)
                or not all(_sha(value) for value in (
                    train_receipt_sha256, validation_receipt_sha256,
                    component_oof_receipt_sha256, receipt_sha256))):
            raise RecoveryRefusal("action bundle contract is malformed")
        self.config=config; self.seed=int(seed); self.feature_names=tuple(feature_names)
        self.model=model; self.objective=objective
        self.train_day_range=tuple(map(int,train_day_range))
        self.validation_day_range=tuple(map(int,validation_day_range))
        for day in self.train_day_range+self.validation_day_range:C.guard_date(day)
        self.train_receipt_sha256=train_receipt_sha256
        self.validation_receipt_sha256=validation_receipt_sha256
        self.component_oof_receipt_sha256=component_oof_receipt_sha256
        self.shuffled_labels=bool(shuffled_labels); self.shuffle_seed=shuffle_seed
        self.model_file_sha256=model_file_sha256
        self.receipt_sha256=receipt_sha256
        self.refit_all_pre_h2=bool(refit_all_pre_h2)
        self.iteration_selection_receipt_sha256=(
            iteration_selection_receipt_sha256)

    def predict_regret_usd(self, x: np.ndarray) -> np.ndarray:
        matrix=np.asarray(x,np.float32)
        if matrix.ndim != 2 or matrix.shape[1] != len(self.feature_names):
            raise RecoveryRefusal("action prediction feature matrix differs")
        threads=catboost_predict_threads()
        if self.objective == "MultiRMSE":
            raw=np.asarray(self.model.predict(
                matrix,thread_count=threads),np.float64).reshape((-1,3))
            return np.maximum(0.0,np.expm1(np.clip(raw,0,40))*VALUE_SCALE_USD)
        if self.objective == "MultiClass":
            probability=np.asarray(self.model.predict_proba(
                matrix,thread_count=threads),np.float64)
            return (1.0-probability)*VALUE_SCALE_USD
        score=np.empty((len(matrix),3),np.float64)
        eye=np.eye(3,dtype=np.float32);columns=matrix.shape[1]
        rows=max(1,4_000_000//max(1,3*(columns+3)))
        for start in range(0,len(matrix),rows):
            stop=min(len(matrix),start+rows)
            expanded=np.empty(((stop-start)*3,columns+3),np.float32)
            expanded[:,:columns]=np.repeat(matrix[start:stop],3,axis=0)
            expanded[:,columns:]=np.tile(eye,(stop-start,1))
            score[start:stop]=np.asarray(
                self.model.predict(expanded,thread_count=threads),np.float64).reshape((-1,3))
        return (score.max(axis=1,keepdims=True)-score)*VALUE_SCALE_USD

    def save(self,path:os.PathLike[str]|str)->str:
        target=C.assert_workspace_output(path)
        if target.exists(): raise RecoveryRefusal("action bundle target already exists")
        target.parent.mkdir(parents=True,exist_ok=True)
        stage=Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp.",dir=target.parent))
        try:
            filename="action.cbm"; model_path=stage/filename
            self.model.save_model(str(model_path),format="cbm")
            if C.file_sha256(model_path)!=self.model_file_sha256:
                raise RecoveryRefusal("action serialized model bytes changed")
            manifest={
                "schema":ACTION_MODEL_SCHEMA,"config":asdict(self.config),
                "config_sha256":self.config.receipt_sha256,"seed":self.seed,
                "feature_names":self.feature_names,"objective":self.objective,
                "train_day_range":self.train_day_range,
                "validation_day_range":self.validation_day_range,
                "train_receipt_sha256":self.train_receipt_sha256,
                "validation_receipt_sha256":self.validation_receipt_sha256,
                "component_oof_receipt_sha256":self.component_oof_receipt_sha256,
                "shuffled_labels":self.shuffled_labels,"shuffle_seed":self.shuffle_seed,
                "model_file_sha256":self.model_file_sha256,
                "refit_all_pre_h2":self.refit_all_pre_h2,
                "iteration_selection_receipt_sha256":
                    self.iteration_selection_receipt_sha256,
                "receipt_sha256":self.receipt_sha256,"file":filename,
                "file_sha256":C.file_sha256(model_path),
                "catboost_version":catboost.__version__,
                "fit_backend_fields":
                    fit_receipt_backend_fields(self.objective),
                "workers":16}
            C.atomic_json(stage/"manifest.json",manifest)
            atomic_replace_directory(stage,target)
        except Exception:
            shutil.rmtree(stage,ignore_errors=True);raise
        return C.file_sha256(target/"manifest.json")

    @classmethod
    def load(cls,path:os.PathLike[str]|str)->"ActionModelBundle":
        source=Path(path).resolve();C.guard_payload(source)
        try: manifest=json.loads((source/"manifest.json").read_text())
        except (OSError,UnicodeError,json.JSONDecodeError) as exc:
            raise RecoveryRefusal("cannot strict-load action manifest") from exc
        if (manifest.get("schema")!=ACTION_MODEL_SCHEMA
                or manifest.get("catboost_version")!=catboost.__version__
                or manifest.get("workers")!=16):
            raise RecoveryRefusal("action runtime/schema differs")
        config=_config_from_json(manifest["config"])
        if config.receipt_sha256!=manifest.get("config_sha256"):
            raise RecoveryRefusal("action config receipt differs")
        objective=str(manifest["objective"]); model_path=source/manifest["file"]
        if C.file_sha256(model_path)!=manifest.get("file_sha256"):
            raise RecoveryRefusal("action model hash differs")
        model=(CatBoostRanker() if objective=="PairLogitPairwise" else
               CatBoostClassifier() if objective=="MultiClass" else CatBoostRegressor())
        model.load_model(str(model_path),format="cbm")
        core={"schema":ACTION_MODEL_SCHEMA,"config_sha256":config.receipt_sha256,
              "seed":int(manifest["seed"]),"feature_names":tuple(manifest["feature_names"]),
              "objective":objective,"train":manifest["train_receipt_sha256"],
              "validation":manifest["validation_receipt_sha256"],
              "train_day_range":tuple(manifest["train_day_range"]),
              "validation_day_range":tuple(manifest["validation_day_range"]),
              "component_oof":manifest["component_oof_receipt_sha256"],
              "model_file_sha256":manifest["model_file_sha256"],
              "refit_all_pre_h2":bool(manifest["refit_all_pre_h2"]),
              "iteration_selection_receipt_sha256":
                  manifest["iteration_selection_receipt_sha256"],
              "shuffled_labels":bool(manifest["shuffled_labels"]),
              "shuffle_seed":manifest["shuffle_seed"]}
        if C.object_sha256(core)!=manifest.get("receipt_sha256"):
            raise RecoveryRefusal("action bundle identity differs")
        stored=manifest.get("fit_backend_fields")
        if (stored is not None and dict(stored).get("law")
                !=fit_receipt_law_fields(objective)):
            raise RecoveryRefusal(
                f"published fit backend differs from the D-105 law: {stored}")
        return cls(config=config,seed=int(manifest["seed"]),
                   feature_names=tuple(manifest["feature_names"]),model=model,
                   objective=objective,train_receipt_sha256=manifest["train_receipt_sha256"],
                   validation_receipt_sha256=manifest["validation_receipt_sha256"],
                   train_day_range=tuple(manifest["train_day_range"]),
                   validation_day_range=tuple(manifest["validation_day_range"]),
                   component_oof_receipt_sha256=manifest["component_oof_receipt_sha256"],
                   shuffled_labels=bool(manifest["shuffled_labels"]),
                   shuffle_seed=manifest["shuffle_seed"],
                   receipt_sha256=manifest["receipt_sha256"],
                   model_file_sha256=manifest["model_file_sha256"],
                   refit_all_pre_h2=bool(manifest["refit_all_pre_h2"]),
                   iteration_selection_receipt_sha256=
                       manifest["iteration_selection_receipt_sha256"])


def _action_core(
    train:ActionTrainingMatrix,validation:ActionTrainingMatrix,
    config:RecoveryConfig,seed:int,objective:str,
    shuffled_labels:bool,shuffle_seed:int|None,model_file_sha256:str,
)->dict[str,object]:
    return {"schema":ACTION_MODEL_SCHEMA,"config_sha256":config.receipt_sha256,
            "seed":int(seed),"feature_names":train.feature_names,"objective":objective,
            "train":train.receipt_sha256,"validation":validation.receipt_sha256,
            "train_day_range":(int(np.min(train.day)),int(np.max(train.day))),
            "validation_day_range":(
                int(np.min(validation.day)),int(np.max(validation.day))),
            "component_oof":train.component_oof_receipt_sha256,
            "model_file_sha256":model_file_sha256,
            "refit_all_pre_h2":False,
            "iteration_selection_receipt_sha256":None,
            "shuffled_labels":bool(shuffled_labels),"shuffle_seed":shuffle_seed}


def fit_action_bundle(
    train:ActionTrainingMatrix,validation:ActionTrainingMatrix,*,
    config:RecoveryConfig,seed:int,objective:str="MultiRMSE",
    shuffled_labels:bool=False,shuffle_seed:int|None=None,
)->ActionModelBundle:
    train.validate();validation.validate();config.__post_init__()
    if (train.feature_names!=validation.feature_names
            or train.component_oof_receipt_sha256!=validation.component_oof_receipt_sha256):
        raise RecoveryRefusal("action train/validation stacking contract differs")
    _assert_chronological(train.day,validation.day)
    if (shuffled_labels!=(shuffle_seed is not None)
            or (shuffle_seed is not None
                and shuffle_seed not in config.shuffle_seeds)):
        raise RecoveryRefusal("action shuffle identity is incomplete")
    common=_common_parameters(config,seed)
    x=np.asarray(train.x,np.float32);vx=np.asarray(validation.x,np.float32)
    if objective=="MultiRMSE":
        model=_head_model(CatBoostRegressor,loss_function="MultiRMSE",
                          common=common)
        _fit_with_early_stop(model,x,train.regret_log_target,train.sample_weight,
                             vx,validation.regret_log_target,validation.sample_weight,
                             patience=config.early_stopping_rounds)
    elif objective=="MultiClass":
        model=_head_model(CatBoostClassifier,loss_function="MultiClass",
                          common=common)
        action_index={value:index for index,value in enumerate(("ENTER","DEFER","PASS"))}
        y=np.asarray([action_index[value] for value in train.optimal_action],np.int8)
        vy=np.asarray([action_index[value] for value in validation.optimal_action],np.int8)
        _fit_with_early_stop(model,x,y,train.sample_weight,vx,vy,validation.sample_weight,
                             patience=config.early_stopping_rounds)
    else:
        raise RecoveryRefusal("use fit_pairwise_action_bundle for PairLogitPairwise")
    model_hash=_serialized_model_sha256(model)
    core=_action_core(train,validation,config,seed,objective,shuffled_labels,
                      shuffle_seed,model_hash)
    return ActionModelBundle(config=config,seed=seed,feature_names=train.feature_names,
        model=model,objective=objective,train_receipt_sha256=train.receipt_sha256,
        validation_receipt_sha256=validation.receipt_sha256,
        train_day_range=(int(np.min(train.day)),int(np.max(train.day))),
        validation_day_range=(
            int(np.min(validation.day)),int(np.max(validation.day))),
        component_oof_receipt_sha256=train.component_oof_receipt_sha256,
        shuffled_labels=shuffled_labels,shuffle_seed=shuffle_seed,
        receipt_sha256=C.object_sha256(core),model_file_sha256=model_hash)


def _pairwise_pool(matrix:ActionTrainingMatrix)->Pool:
    x=np.asarray(matrix.x,np.float32);n=len(x);columns=x.shape[1]
    regret=np.asarray(matrix.regret_cents,np.int64)
    weights=np.asarray(matrix.sample_weight,np.float64);pairs=[];pair_weights=[]
    for winner in range(3):
        for loser in range(3):
            difference=regret[:,loser]-regret[:,winner]
            local=np.flatnonzero(difference>0)
            if not len(local):continue
            pairs.append(np.column_stack((local*3+winner,local*3+loser)))
            pair_weights.append(np.maximum(
                (difference[local]/(VALUE_SCALE_USD*100.0))*weights[local],1e-9))
    if not pairs:raise RecoveryRefusal("pairwise action matrix has no strict preferences")
    pair_array=np.concatenate(pairs).astype(np.int64,copy=False)
    pair_weight=np.concatenate(pair_weights).astype(np.float64,copy=False)
    stage=Path(tempfile.mkdtemp(prefix="entry-v2-pairwise-pool-"));mapping=None
    try:
        mapping=np.lib.format.open_memmap(stage/"x.npy",mode="w+",dtype=np.float32,
            shape=(n*3,columns+3));eye=np.eye(3,dtype=np.float32)
        rows=max(1,4_000_000//max(1,columns))
        for start in range(0,n,rows):
            stop=min(n,start+rows);target=slice(start*3,stop*3)
            mapping[target,:columns]=np.repeat(x[start:stop],3,axis=0)
            mapping[target,columns:]=np.tile(eye,(stop-start,1))
        mapping.flush()
        pool=Pool(mapping,label=np.zeros(n*3),
            group_id=np.repeat(np.arange(n,dtype=np.int64),3),pairs=pair_array,
            pairs_weight=pair_weight)
        return pool
    finally:
        if mapping is not None:
            raw=getattr(mapping,"_mmap",None)
            if raw is not None:raw.close()
        shutil.rmtree(stage,ignore_errors=True)


def fit_pairwise_action_bundle(
    train:ActionTrainingMatrix,validation:ActionTrainingMatrix,*,
    config:RecoveryConfig,seed:int,shuffled_labels:bool=False,
    shuffle_seed:int|None=None,
)->ActionModelBundle:
    train.validate();validation.validate();_assert_chronological(train.day,validation.day)
    if (shuffled_labels != (shuffle_seed is not None)
            or (shuffle_seed is not None
                and shuffle_seed not in config.shuffle_seeds)):
        raise RecoveryRefusal("pairwise action shuffle identity is incomplete")
    common=_common_parameters(config,seed)
    model=_head_model(CatBoostRanker,loss_function="PairLogitPairwise",
                      common=common)
    model.fit(_pairwise_pool(train),eval_set=_pairwise_pool(validation),use_best_model=True,
              early_stopping_rounds=config.early_stopping_rounds)
    model_hash=_serialized_model_sha256(model)
    core=_action_core(train,validation,config,seed,"PairLogitPairwise",
                      shuffled_labels,shuffle_seed,model_hash)
    return ActionModelBundle(config=config,seed=seed,feature_names=train.feature_names,
        model=model,objective="PairLogitPairwise",train_receipt_sha256=train.receipt_sha256,
        validation_receipt_sha256=validation.receipt_sha256,
        train_day_range=(int(np.min(train.day)),int(np.max(train.day))),
        validation_day_range=(
            int(np.min(validation.day)),int(np.max(validation.day))),
        component_oof_receipt_sha256=train.component_oof_receipt_sha256,
        shuffled_labels=shuffled_labels,shuffle_seed=shuffle_seed,
        receipt_sha256=C.object_sha256(core),model_file_sha256=model_hash)

def fit_all_pre_h2_action_bundle(matrix:ActionTrainingMatrix,*,
        selection_bundle:ActionModelBundle,config:RecoveryConfig,seed:int,
        expected_last_training_day:int)->ActionModelBundle:
    """Refit the accepted action objective on the frozen OOF stack."""

    matrix.validate();config.__post_init__()
    if (selection_bundle.seed!=seed or selection_bundle.shuffled_labels
            or selection_bundle.refit_all_pre_h2
            or selection_bundle.feature_names!=matrix.feature_names
            or selection_bundle.component_oof_receipt_sha256
               !=matrix.component_oof_receipt_sha256
            or int(np.max(matrix.day))!=int(expected_last_training_day)
            or int(expected_last_training_day)>=C.HOLDOUT_START_D8):
        raise RecoveryRefusal("action all-data refit inputs differ/seal opened")
    iterations=int(selection_bundle.model.tree_count_)
    if not 0<iterations<=config.max_iterations:
        raise RecoveryRefusal("action iteration selection differs")
    selection=C.object_sha256({"schema":"QRE2TABREFITITER1",
        "kind":"ACTION","selection_model":selection_bundle.receipt_sha256,
        "objective":selection_bundle.objective,"iterations":iterations,
        "all_pre_h2":True})
    common=_common_parameters(config,seed);common["iterations"]=iterations
    objective=selection_bundle.objective
    if objective=="MultiRMSE":
        model=_head_model(CatBoostRegressor,loss_function="MultiRMSE",
                          common=common)
        _fixed_fit(model,matrix.x,matrix.regret_log_target,
                   matrix.sample_weight)
    elif objective=="MultiClass":
        model=_head_model(CatBoostClassifier,loss_function="MultiClass",
                          common=common)
        action_index={value:index for index,value in enumerate(
            ("ENTER","DEFER","PASS"))}
        target=np.asarray([action_index[value]
                           for value in matrix.optimal_action],np.int8)
        _fixed_fit(model,matrix.x,target,matrix.sample_weight)
    elif objective=="PairLogitPairwise":
        model=_head_model(CatBoostRanker,loss_function="PairLogitPairwise",
                          common=common)
        model.fit(_pairwise_pool(matrix))
        if int(model.tree_count_)<=0:
            raise RecoveryRefusal("all-data pairwise refit produced no trees")
    else:raise RecoveryRefusal("all-data action objective is unregistered")
    model_hash=_serialized_model_sha256(model)
    train_range=(int(np.min(matrix.day)),int(np.max(matrix.day)))
    core={"schema":ACTION_MODEL_SCHEMA,"config_sha256":config.receipt_sha256,
        "seed":int(seed),"feature_names":matrix.feature_names,
        "objective":objective,"train":matrix.receipt_sha256,
        "validation":selection_bundle.receipt_sha256,
        "train_day_range":train_range,
        "validation_day_range":selection_bundle.validation_day_range,
        "component_oof":matrix.component_oof_receipt_sha256,
        "model_file_sha256":model_hash,"refit_all_pre_h2":True,
        "iteration_selection_receipt_sha256":selection,
        "shuffled_labels":False,"shuffle_seed":None}
    result=ActionModelBundle(config=config,seed=seed,
        feature_names=matrix.feature_names,model=model,objective=objective,
        train_receipt_sha256=matrix.receipt_sha256,
        validation_receipt_sha256=selection_bundle.receipt_sha256,
        component_oof_receipt_sha256=matrix.component_oof_receipt_sha256,
        train_day_range=train_range,
        validation_day_range=selection_bundle.validation_day_range,
        shuffled_labels=False,shuffle_seed=None,
        receipt_sha256=C.object_sha256(core),model_file_sha256=model_hash,
        refit_all_pre_h2=True,
        iteration_selection_receipt_sha256=selection)
    return result
