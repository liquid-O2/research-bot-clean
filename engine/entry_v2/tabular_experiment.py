"""Chronological five-seed real/control fitting for tabular recovery."""

from __future__ import annotations

from dataclasses import asdict,dataclass
import hashlib
import json
import os
from pathlib import Path
from types import MappingProxyType
from typing import Final, Mapping, Sequence

import numpy as np

from . import common as C
from .exact_delayed_teacher import ExactDelayedTeacherDay
from .tabular_delayed_corpus import CausalFeatureShard
from .tabular_models import (
    ActionModelBundle, ComponentModelBundle, _bounded_row_subset,fit_action_bundle,
    fit_component_bundle, fit_pairwise_action_bundle,
)
from .tabular_model_io import (
    load_action_model,load_component_model,predict_action_regret,
)
from .tabular_recovery_contracts import (
    COMPONENT_STACK_NAMES, CausalFeatureSchema, RecoveryChronology,
    RecoveryConfig, RecoveryRefusal, sha256_row_array,
)
from .tabular_training import (
    ActionTrainingMatrix, ComponentPredictionTable, ComponentTrainingMatrix,
    combine_component_prediction_tables, matched_shuffle_action,
    matched_shuffle_component,
)


EXPERIMENT_SCHEMA: Final="QRE2TABEXPERIMENT4"


def _sha(value:object)->bool:
    return (isinstance(value,str) and len(value)==64
            and all(char in "0123456789abcdef" for char in value))


def _array_sha256(value:np.ndarray)->str:
    array=np.ascontiguousarray(value);digest=hashlib.sha256()
    digest.update(str(array.dtype).encode());digest.update(repr(array.shape).encode())
    digest.update(array.tobytes());return digest.hexdigest()


def _range_mask(day:np.ndarray,bounds:tuple[int,int])->np.ndarray:
    values=np.asarray(day,np.int64);lo,hi=map(int,bounds)
    return (values>=lo)&(values<=hi)


def _folds(chronology:RecoveryChronology,kind:str):
    return chronology.component_folds if kind=="COMPONENT" else chronology.action_folds


@dataclass(frozen=True,slots=True)
class FittedFold:
    kind:str
    learner_backend:str
    name:str
    score_range:tuple[int,int]
    seed:int
    shuffled_labels:bool
    shuffle_seed:int|None
    bundle_path:str
    bundle_receipt_sha256:str
    prediction_path:str|None
    prediction_receipt_sha256:str|None

    def __post_init__(self)->None:
        if (self.kind not in {"COMPONENT","ACTION"}
                or self.learner_backend not in {
                    "CATBOOST","LIGHTGBM","XGBOOST","CAUSAL_EXPERTS"}
                or self.shuffled_labels!=(self.shuffle_seed is not None)
                or self.score_range[0]>self.score_range[1]
                or not _sha(self.bundle_receipt_sha256)
                or (self.kind=="COMPONENT")!=(self.prediction_path is not None)
                or (self.kind=="COMPONENT")!=(self.prediction_receipt_sha256 is not None)
                or (self.prediction_receipt_sha256 is not None
                    and not _sha(self.prediction_receipt_sha256))):
            raise RecoveryRefusal("fitted fold receipt is malformed")


@dataclass(frozen=True,slots=True)
class SeedModelRoster:
    kind:str
    learner_backend:str
    seed:int
    shuffled_labels:bool
    shuffle_seed:int|None
    folds:tuple[FittedFold,...]
    chronology_receipt_sha256:str
    objective:str|None
    component_prediction_receipt_sha256:str|None
    receipt_sha256:str

    def __post_init__(self)->None:
        expected=("BURN_E2_STACK","E3","E4","E5","E6","FROZEN_Q3_E8") \
            if self.kind=="COMPONENT" else ("E3","E4","E5","E6","FROZEN_Q3_E8")
        if (tuple(row.name for row in self.folds)!=expected
                or self.learner_backend not in {
                    "CATBOOST","LIGHTGBM","XGBOOST","CAUSAL_EXPERTS"}
                or (self.kind=="COMPONENT"
                    and self.learner_backend=="CAUSAL_EXPERTS")
                or any(row.kind!=self.kind
                       or row.learner_backend!=self.learner_backend
                       or row.seed!=self.seed
                       or row.shuffled_labels!=self.shuffled_labels
                       or row.shuffle_seed!=self.shuffle_seed for row in self.folds)
                or not _sha(self.chronology_receipt_sha256)
                or self.component_prediction_receipt_sha256 is None
                or not _sha(self.component_prediction_receipt_sha256)
                or (self.kind=="COMPONENT" and self.objective is not None)
                or (self.kind=="ACTION" and self.objective not in {
                    "MultiRMSE","PairLogitPairwise","MultiClass"})):
            raise RecoveryRefusal("seed model roster differs")
        core={"schema":EXPERIMENT_SCHEMA,"kind":self.kind,
              "learner_backend":self.learner_backend,"seed":self.seed,
              "shuffled_labels":self.shuffled_labels,
              "shuffle_seed":self.shuffle_seed,
              "folds":tuple(asdict(row) for row in self.folds),
              "chronology":self.chronology_receipt_sha256,
              "objective":self.objective,
              "component_predictions":self.component_prediction_receipt_sha256}
        if C.object_sha256(core)!=self.receipt_sha256:
            raise RecoveryRefusal("seed model roster receipt differs")

    def bundle_for_day(self,trading_day:int)->FittedFold:
        C.guard_date(int(trading_day))
        matches=[row for row in self.folds
                 if row.score_range[0]<=trading_day<=row.score_range[1]]
        if len(matches)!=1:raise RecoveryRefusal("day has no unique OOF model fold")
        return matches[0]


@dataclass(frozen=True,slots=True)
class ActionPredictionTable:
    matrix_row_index:np.ndarray
    opportunity_id:np.ndarray
    day:np.ndarray
    predicted_regret_usd:np.ndarray
    fold_model_receipt_sha256:np.ndarray
    fold_information_max_day:np.ndarray
    source_matrix_receipt_sha256:str
    model_roster_receipt_sha256:str
    chronology_receipt_sha256:str
    receipt_sha256:str

    def validate(self)->None:
        index=np.asarray(self.matrix_row_index,np.int64);n=len(index)
        regret=np.asarray(self.predicted_regret_usd,np.float64)
        if (not n or len(set(index.tolist()))!=n or np.any(index<0)
                or np.asarray(self.opportunity_id,str).shape!=(n,)
                or np.asarray(self.day,np.int64).shape!=(n,)
                or regret.shape!=(n,3) or np.any(regret<0)
                or not np.all(np.isfinite(regret))
                or np.asarray(self.fold_model_receipt_sha256,str).shape!=(n,)
                or np.asarray(self.fold_information_max_day,np.int64).shape!=(n,)
                or np.any(np.asarray(self.fold_information_max_day,np.int64)
                          >=np.asarray(self.day,np.int64))
                or any(not _sha(value) for value in np.asarray(
                    self.fold_model_receipt_sha256,str))
                or not all(_sha(value) for value in (
                    self.source_matrix_receipt_sha256,
                    self.model_roster_receipt_sha256,
                    self.chronology_receipt_sha256,self.receipt_sha256))):
            raise RecoveryRefusal("action OOF prediction table is malformed")
        core={"schema":"QRE2TABACTIONOOF1","rows":n,
              "matrix_row_index":_array_sha256(index),
              "opportunity_id":_array_sha256(np.asarray(self.opportunity_id,str)),
              "day":_array_sha256(np.asarray(self.day,np.int64)),
              "predicted_regret_usd":_array_sha256(regret),
              "fold_model":_array_sha256(np.asarray(
                  self.fold_model_receipt_sha256,str)),
              "fold_information_max_day":_array_sha256(np.asarray(
                  self.fold_information_max_day,np.int64)),
              "source_matrix":self.source_matrix_receipt_sha256,
              "model_roster":self.model_roster_receipt_sha256,
              "chronology":self.chronology_receipt_sha256}
        if C.object_sha256(core)!=self.receipt_sha256:
            raise RecoveryRefusal("action OOF prediction receipt differs")

    @property
    def raw_advantage_usd(self)->np.ndarray:
        values=np.asarray(self.predicted_regret_usd,np.float64)
        return np.minimum(values[:,1],values[:,2])-values[:,0]

    def save(self,path:str|Path)->str:
        self.validate();target=C.assert_workspace_output(path)
        if target.suffix!=".npz":raise RecoveryRefusal("action OOF path must be .npz")
        target.parent.mkdir(parents=True,exist_ok=True)
        temporary=target.with_name(target.name+f".tmp.{os.getpid()}")
        with temporary.open("xb") as handle:
            np.savez_compressed(handle,schema=np.asarray(["QRE2TABACTIONOOFSTORE1"]),
                matrix_row_index=np.asarray(self.matrix_row_index,np.int64),
                opportunity_id=np.asarray(self.opportunity_id,str),
                day=np.asarray(self.day,np.int64),
                predicted_regret_usd=np.asarray(self.predicted_regret_usd,np.float64),
                fold_model_receipt_sha256=np.asarray(
                    self.fold_model_receipt_sha256,str),
                fold_information_max_day=np.asarray(
                    self.fold_information_max_day,np.int64),
                source_matrix_receipt_sha256=np.asarray(
                    [self.source_matrix_receipt_sha256]),
                model_roster_receipt_sha256=np.asarray(
                    [self.model_roster_receipt_sha256]),
                chronology_receipt_sha256=np.asarray(
                    [self.chronology_receipt_sha256]),
                receipt_sha256=np.asarray([self.receipt_sha256]))
            handle.flush();os.fsync(handle.fileno())
        os.replace(temporary,target);return C.file_sha256(target)

    @classmethod
    def load(cls,path:str|Path)->"ActionPredictionTable":
        source=Path(path);C.guard_payload(source)
        try:
            with np.load(source,allow_pickle=False) as value:
                if str(value["schema"][0])!="QRE2TABACTIONOOFSTORE1":
                    raise RecoveryRefusal("action OOF store schema differs")
                result=cls(value["matrix_row_index"],value["opportunity_id"],
                    value["day"],value["predicted_regret_usd"],
                    value["fold_model_receipt_sha256"],
                    value["fold_information_max_day"],
                    str(value["source_matrix_receipt_sha256"][0]),
                    str(value["model_roster_receipt_sha256"][0]),
                    str(value["chronology_receipt_sha256"][0]),
                    str(value["receipt_sha256"][0]))
        except (OSError,ValueError,KeyError) as exc:
            raise RecoveryRefusal("cannot strict-load action OOF table") from exc
        result.validate();return result


def _load_or_fit_component(path:Path,train:ComponentTrainingMatrix,
        validation:ComponentTrainingMatrix,*,config:RecoveryConfig,seed:int,
        shuffled:bool,shuffle_seed:int|None,learner_backend:str)->object:
    if path.is_dir():
        bundle=load_component_model(path)
        if (bundle.train_receipt_sha256!=train.receipt_sha256
                or bundle.validation_receipt_sha256!=validation.receipt_sha256
                or bundle.config.receipt_sha256!=config.receipt_sha256
                or bundle.seed!=seed
                or bundle.feature_names!=train.feature_names
                or bundle.shuffled_labels!=shuffled
                or bundle.shuffle_seed!=shuffle_seed):
            raise RecoveryRefusal("resumed component fold inputs differ")
        return bundle
    if learner_backend=="CATBOOST":
        bundle=fit_component_bundle(train,validation,config=config,seed=seed,
            shuffled_labels=shuffled,shuffle_seed=shuffle_seed)
    else:
        from .tabular_fallbacks import fit_histogram_component_bundle
        bundle=fit_histogram_component_bundle(train,validation,
            backend=learner_backend,config=config,seed=seed,
            shuffled_labels=shuffled,shuffle_seed=shuffle_seed)
    bundle.save(path)
    reloaded=load_component_model(path)
    if reloaded.receipt_sha256!=bundle.receipt_sha256:
        raise RecoveryRefusal("component fold strict reload differs")
    return reloaded


def _load_or_fit_action(path:Path,train:ActionTrainingMatrix,
        validation:ActionTrainingMatrix,*,config:RecoveryConfig,seed:int,
        objective:str,shuffled:bool,shuffle_seed:int|None,
        learner_backend:str)->object:
    if path.is_dir():
        bundle=load_action_model(path)
        if (bundle.train_receipt_sha256!=train.receipt_sha256
                or bundle.validation_receipt_sha256!=validation.receipt_sha256
                or bundle.config.receipt_sha256!=config.receipt_sha256
                or bundle.seed!=seed
                or bundle.feature_names!=train.feature_names
                or bundle.component_oof_receipt_sha256
                   !=train.component_oof_receipt_sha256
                or bundle.objective!=objective or bundle.shuffled_labels!=shuffled
                or bundle.shuffle_seed!=shuffle_seed):
            raise RecoveryRefusal("resumed action fold inputs differ")
        return bundle
    if learner_backend in {"LIGHTGBM","XGBOOST"}:
        if objective!="MultiRMSE":
            raise RecoveryRefusal("histogram action supports the frozen regret objective")
        from .tabular_fallbacks import fit_histogram_action_bundle
        bundle=fit_histogram_action_bundle(train,validation,
            backend=learner_backend,config=config,seed=seed,
            shuffled_labels=shuffled,shuffle_seed=shuffle_seed)
    elif objective=="PairLogitPairwise":
        bundle=fit_pairwise_action_bundle(train,validation,config=config,seed=seed,
            shuffled_labels=shuffled,shuffle_seed=shuffle_seed)
    else:
        bundle=fit_action_bundle(train,validation,config=config,seed=seed,
            objective=objective,shuffled_labels=shuffled,shuffle_seed=shuffle_seed)
    bundle.save(path);reloaded=load_action_model(path)
    if reloaded.receipt_sha256!=bundle.receipt_sha256:
        raise RecoveryRefusal("action fold strict reload differs")
    return reloaded


def predict_component_fold(*,bundle:object,
        feature_paths:Sequence[str|Path],feature_schema:CausalFeatureSchema,
        score_range:tuple[int,int],chronology_receipt_sha256:str,
        required_opportunity_ids_by_day:Mapping[int,Sequence[str]],
        output_path:str|Path)->ComponentPredictionTable:
    output=Path(output_path)
    required={int(day):tuple(sorted(set(map(str,values))))
              for day,values in required_opportunity_ids_by_day.items()
              if score_range[0]<=int(day)<=score_range[1] and values}
    if not required:
        raise RecoveryRefusal("component score fold has no required action states")
    expected_ids={value for values in required.values() for value in values}
    if len(expected_ids)!=sum(map(len,required.values())):
        raise RecoveryRefusal("component action requirements repeat across days")
    if output.is_file():
        table=ComponentPredictionTable.load(output)
        if (table.model_receipt_sha256!=bundle.receipt_sha256
                or table.chronology_receipt_sha256!=chronology_receipt_sha256
                or set(np.asarray(table.opportunity_id,str).tolist())!=expected_ids
                or int(np.min(table.day))<score_range[0]
                or int(np.max(table.day))>score_range[1]):
            raise RecoveryRefusal("resumed component predictions differ")
        return table
    eligible_shards=[];seen=set()
    for raw_path in feature_paths:
        shard=CausalFeatureShard.load(raw_path)
        day=int(np.asarray(shard.day,np.int64)[0])
        if day not in required:continue
        source={name:index for index,name in enumerate(shard.feature_names)}
        if not set(feature_schema.names)<=set(source):
            raise RecoveryRefusal("component prediction feature schema absent")
        local=np.isin(np.asarray(shard.opportunity_id,str),required[day])
        seen.update(np.asarray(shard.opportunity_id,str)[local].tolist())
        eligible_shards.append((shard,local,source))
    if seen!=expected_ids:
        raise RecoveryRefusal("component OOF requirements are absent from causal shards")
    source_receipts=tuple(sorted(row.representation_sha256
                                 for row,_local,_source in eligible_shards))
    ids=[];days=[];values=[]
    for shard,local,source in eligible_shards:
        day=int(np.asarray(shard.day,np.int64)[0])
        if not local.any():continue
        columns=np.asarray([source[name] for name in feature_schema.names],np.int64)
        matrix=np.asarray(shard.features,np.float32)[local][:,columns]
        prediction=bundle.predict(matrix)
        ids.append(np.asarray(shard.opportunity_id,str)[local]);values.append(prediction.values)
        days.append(np.full(len(matrix),day,np.int64))
    if not ids:raise RecoveryRefusal("component score fold has no causal rows")
    opportunity=np.concatenate(ids);day_values=np.concatenate(days)
    order=np.lexsort((opportunity,day_values))
    table=ComponentPredictionTable(opportunity[order],day_values[order],
        np.concatenate(values)[order],
        sha256_row_array(bundle.receipt_sha256,len(order)),
        np.full(len(order),bundle.validation_day_range[1],np.int64),
        source_receipts,
        COMPONENT_STACK_NAMES,bundle.receipt_sha256,
        chronology_receipt_sha256,True)
    table.validate();table.save(output)
    reloaded=ComponentPredictionTable.load(output)
    if reloaded.receipt_sha256!=table.receipt_sha256:
        raise RecoveryRefusal("component prediction strict reload differs")
    return reloaded


def fit_component_seed(*,matrix:ComponentTrainingMatrix,
        feature_paths:Sequence[str|Path],feature_schema:CausalFeatureSchema,
        required_opportunity_ids_by_day:Mapping[int,Sequence[str]],
        chronology:RecoveryChronology,config:RecoveryConfig,seed:int,
        output_root:str|Path,shuffled_labels:bool=False,
        shuffle_seed:int|None=None,
        learner_backend:str="CATBOOST")->tuple[SeedModelRoster,ComponentPredictionTable]:
    matrix.validate();chronology.__post_init__();config.__post_init__()
    learner_backend=str(learner_backend).upper()
    if (learner_backend not in {"CATBOOST","LIGHTGBM","XGBOOST"}
            or shuffled_labels!=(shuffle_seed is not None)):
        raise RecoveryRefusal("component seed/control identity differs")
    root=C.assert_workspace_output(output_root)
    fitted=[];tables=[]
    for name,train_lo,train_hi,val_lo,val_hi,score_lo,score_hi in chronology.component_folds:
        train=matrix.mask(_range_mask(matrix.day,(train_lo,train_hi)))
        validation=matrix.mask(_range_mask(matrix.day,(val_lo,val_hi)))
        if shuffled_labels:
            assert shuffle_seed is not None
            train=matched_shuffle_component(train,seed=shuffle_seed)
            validation=matched_shuffle_component(validation,seed=shuffle_seed)
        lane="shuffle" if shuffled_labels else "real"
        bundle_path=(root/learner_backend.lower()/lane/f"seed_{seed}"/name/
                     "component_bundle")
        bundle=_load_or_fit_component(bundle_path,train,validation,config=config,
            seed=seed,shuffled=shuffled_labels,shuffle_seed=shuffle_seed,
            learner_backend=learner_backend)
        prediction_path=(root/learner_backend.lower()/lane/f"seed_{seed}"/name/
                         "component_oof.npz")
        table=predict_component_fold(bundle=bundle,feature_paths=feature_paths,
            feature_schema=feature_schema,score_range=(score_lo,score_hi),
            chronology_receipt_sha256=chronology.receipt_sha256,
            required_opportunity_ids_by_day=required_opportunity_ids_by_day,
            output_path=prediction_path)
        fitted.append(FittedFold("COMPONENT",learner_backend,name,
            (score_lo,score_hi),seed,
            shuffled_labels,shuffle_seed,str(bundle_path),bundle.receipt_sha256,
            str(prediction_path),table.receipt_sha256));tables.append(table)
    combined=combine_component_prediction_tables(
        tables,chronology_receipt_sha256=chronology.receipt_sha256)
    combined_path=(root/learner_backend.lower()/
        ("shuffle" if shuffled_labels else "real")/f"seed_{seed}"/
        "component_oof_all.npz")
    if combined_path.is_file():
        stored=ComponentPredictionTable.load(combined_path)
        if stored.receipt_sha256!=combined.receipt_sha256:
            raise RecoveryRefusal("combined component OOF resume differs")
        combined=stored
    else:combined.save(combined_path)
    core={"schema":EXPERIMENT_SCHEMA,"kind":"COMPONENT",
          "learner_backend":learner_backend,"seed":seed,
          "shuffled_labels":shuffled_labels,"shuffle_seed":shuffle_seed,
          "folds":tuple(asdict(row) for row in fitted),
          "chronology":chronology.receipt_sha256,"objective":None,
          "component_predictions":combined.receipt_sha256}
    roster=SeedModelRoster("COMPONENT",learner_backend,seed,
        shuffled_labels,shuffle_seed,
        tuple(fitted),chronology.receipt_sha256,None,
        combined.receipt_sha256,C.object_sha256(core));roster.__post_init__()
    return roster,combined


def predict_component_roster(*,roster:SeedModelRoster,
        feature_paths:Sequence[str|Path],feature_schema:CausalFeatureSchema,
        required_opportunity_ids_by_day:Mapping[int,Sequence[str]],
        output_root:str|Path)->ComponentPredictionTable:
    """Score a new curriculum roster with already-fitted component folds.

    Rollout rounds add causal action seconds but do not alter component labels.
    This boundary therefore reuses the exact persisted component model bytes
    while producing a new, source-bound OOF table for the expanded roster.
    """

    roster.__post_init__();feature_schema.__post_init__()
    if roster.kind!="COMPONENT":
        raise RecoveryRefusal("component rescoring received an action roster")
    root=C.assert_workspace_output(output_root);tables=[]
    for fold in roster.folds:
        bundle=load_component_model(fold.bundle_path)
        if (bundle.receipt_sha256!=fold.bundle_receipt_sha256
                or bundle.seed!=roster.seed
                or bundle.shuffled_labels!=roster.shuffled_labels
                or bundle.shuffle_seed!=roster.shuffle_seed):
            raise RecoveryRefusal("component rescoring fold identity differs")
        table=predict_component_fold(bundle=bundle,feature_paths=feature_paths,
            feature_schema=feature_schema,score_range=fold.score_range,
            chronology_receipt_sha256=roster.chronology_receipt_sha256,
            required_opportunity_ids_by_day=required_opportunity_ids_by_day,
            output_path=root/fold.name/"component_oof.npz")
        tables.append(table)
    combined=combine_component_prediction_tables(
        tables,chronology_receipt_sha256=roster.chronology_receipt_sha256)
    target=root/"component_oof_all.npz"
    if target.is_file():
        stored=ComponentPredictionTable.load(target)
        if stored.receipt_sha256!=combined.receipt_sha256:
            raise RecoveryRefusal("resumed rescored component OOF differs")
        return stored
    combined.save(target);stored=ComponentPredictionTable.load(target)
    if stored.receipt_sha256!=combined.receipt_sha256:
        raise RecoveryRefusal("rescored component OOF strict reload differs")
    return stored


def action_prediction_requirements(
        teacher_paths:Sequence[str|Path])->Mapping[int,tuple[str,...]]:
    """Return the exact round-specific action-state roster for stacking."""

    output={}
    for path in teacher_paths:
        teacher=ExactDelayedTeacherDay.load(path);day=teacher.trading_day
        if day in output:raise RecoveryRefusal("teacher day repeats in action requirements")
        output[day]=tuple(sorted(set(np.asarray(
            teacher.action_opportunity_id,str).tolist())))
    if not output:raise RecoveryRefusal("action prediction requirements are empty")
    return MappingProxyType(dict(sorted(output.items())))


def fit_action_seed(*,matrix:ActionTrainingMatrix,
        chronology:RecoveryChronology,config:RecoveryConfig,seed:int,
        output_root:str|Path,objective:str="MultiRMSE",
        shuffled_labels:bool=False,shuffle_seed:int|None=None,
        learner_backend:str="CATBOOST")->SeedModelRoster:
    matrix.validate();chronology.__post_init__();config.__post_init__()
    learner_backend=str(learner_backend).upper()
    if (learner_backend not in {
            "CATBOOST","LIGHTGBM","XGBOOST","CAUSAL_EXPERTS"}
            or shuffled_labels!=(shuffle_seed is not None)):
        raise RecoveryRefusal("action seed/control identity differs")
    if learner_backend=="CAUSAL_EXPERTS":
        from .tabular_fallbacks import fit_causal_expert_action_seed
        return fit_causal_expert_action_seed(matrix=matrix,
            chronology=chronology,config=config,seed=seed,
            output_root=C.assert_workspace_output(output_root)/
                learner_backend.lower(),objective=objective,
            shuffled_labels=shuffled_labels,shuffle_seed=shuffle_seed)
    root=C.assert_workspace_output(output_root);fitted=[]
    for name,train_lo,train_hi,val_lo,val_hi,score_lo,score_hi in chronology.action_folds:
        train=matrix.mask(_range_mask(matrix.day,(train_lo,train_hi)))
        validation=matrix.mask(_range_mask(matrix.day,(val_lo,val_hi)))
        if shuffled_labels:
            assert shuffle_seed is not None
            train=matched_shuffle_action(train,seed=shuffle_seed)
            validation=matched_shuffle_action(validation,seed=shuffle_seed)
        lane="shuffle" if shuffled_labels else "real"
        bundle_path=(root/learner_backend.lower()/lane/f"seed_{seed}"/name/
                     f"action_{objective}")
        bundle=_load_or_fit_action(bundle_path,train,validation,config=config,
            seed=seed,objective=objective,shuffled=shuffled_labels,
            shuffle_seed=shuffle_seed,learner_backend=learner_backend)
        fitted.append(FittedFold("ACTION",learner_backend,name,
            (score_lo,score_hi),seed,
            shuffled_labels,shuffle_seed,str(bundle_path),bundle.receipt_sha256,
            None,None))
    core={"schema":EXPERIMENT_SCHEMA,"kind":"ACTION",
          "learner_backend":learner_backend,"seed":seed,
          "shuffled_labels":shuffled_labels,"shuffle_seed":shuffle_seed,
          "folds":tuple(asdict(row) for row in fitted),
          "chronology":chronology.receipt_sha256,"objective":objective,
          "component_predictions":matrix.component_oof_receipt_sha256}
    roster=SeedModelRoster("ACTION",learner_backend,seed,
        shuffled_labels,shuffle_seed,
        tuple(fitted),chronology.receipt_sha256,objective,
        matrix.component_oof_receipt_sha256,
        C.object_sha256(core));roster.__post_init__();return roster


def predict_action_oof(*,matrix:ActionTrainingMatrix,roster:SeedModelRoster,
                       output_path:str|Path)->ActionPredictionTable:
    matrix.validate();roster.__post_init__()
    if roster.kind!="ACTION":raise RecoveryRefusal("action OOF received component roster")
    selected=np.zeros(len(matrix.x),bool);predictions=[];indices=[];fold_receipts=[];info=[]
    for fold in roster.folds:
        local=_range_mask(matrix.day,fold.score_range)
        if np.any(selected&local):raise RecoveryRefusal("action OOF score folds overlap")
        if not local.any():continue
        bundle=load_action_model(fold.bundle_path)
        if (bundle.receipt_sha256!=fold.bundle_receipt_sha256
                or bundle.feature_names!=matrix.feature_names
                or bundle.component_oof_receipt_sha256
                   !=matrix.component_oof_receipt_sha256
                or bundle.validation_day_range[1]>=int(np.min(matrix.day[local]))):
            raise RecoveryRefusal("action OOF fold bundle/chronology differs")
        row_index=np.flatnonzero(local);selected[local]=True
        local_day=np.asarray(matrix.day,np.int64)[local]
        with _bounded_row_subset(matrix.x,local) as local_x:
            if getattr(bundle,"day_routed",False):
                predicted=np.empty((len(local_x),3),np.float64)
                for day in np.unique(local_day):
                    day_local=local_day==day
                    with _bounded_row_subset(local_x,day_local) as day_x:
                        predicted[day_local]=predict_action_regret(
                            bundle,day_x,trading_day=int(day))
            else:
                predicted=predict_action_regret(bundle,local_x,
                    trading_day=int(local_day[0]))
        predictions.append(predicted)
        indices.append(row_index)
        fold_receipts.append(sha256_row_array(
            bundle.receipt_sha256,len(row_index)))
        info.append(np.full(len(row_index),bundle.validation_day_range[1],np.int64))
    if not indices:raise RecoveryRefusal("action OOF roster scores no matrix rows")
    row_index=np.concatenate(indices);order=np.argsort(row_index);row_index=row_index[order]
    predicted=np.concatenate(predictions)[order]
    folds=np.concatenate(fold_receipts)[order];information=np.concatenate(info)[order]
    opportunity=np.asarray(matrix.opportunity_id,str)[row_index]
    days=np.asarray(matrix.day,np.int64)[row_index]
    core={"schema":"QRE2TABACTIONOOF1","rows":len(row_index),
          "matrix_row_index":_array_sha256(row_index),
          "opportunity_id":_array_sha256(opportunity),
          "day":_array_sha256(days),
          "predicted_regret_usd":_array_sha256(predicted),
          "fold_model":_array_sha256(folds),
          "fold_information_max_day":_array_sha256(information),
          "source_matrix":matrix.receipt_sha256,
          "model_roster":roster.receipt_sha256,
          "chronology":roster.chronology_receipt_sha256}
    result=ActionPredictionTable(row_index,opportunity,days,predicted,folds,
        information,matrix.receipt_sha256,roster.receipt_sha256,
        roster.chronology_receipt_sha256,C.object_sha256(core))
    result.validate();target=Path(output_path)
    if target.is_file():
        stored=ActionPredictionTable.load(target)
        if stored.receipt_sha256!=result.receipt_sha256:
            raise RecoveryRefusal("resumed action OOF predictions differ")
        return stored
    result.save(target);stored=ActionPredictionTable.load(target)
    if stored.receipt_sha256!=result.receipt_sha256:
        raise RecoveryRefusal("action OOF strict reload differs")
    return stored


def publish_seed_roster(path:str|Path,rosters:Sequence[SeedModelRoster],*,
                        chronology:RecoveryChronology)->Mapping[str,object]:
    rows=tuple(rosters)
    if len(rows)!=5 or len({row.seed for row in rows})!=5:
        raise RecoveryRefusal("published model roster does not have five seeds")
    core={"schema":"QRE2TABSEEDROSTER4","kind":rows[0].kind,
          "learner_backend":rows[0].learner_backend,
          "shuffled_labels":rows[0].shuffled_labels,
          "chronology":chronology.receipt_sha256,
          "rosters":tuple(asdict(row) for row in rows),
          "weakest_real_above_shuffle_required":True,"h2_open_count":0}
    if any(row.kind!=rows[0].kind
           or row.learner_backend!=rows[0].learner_backend
           or row.shuffled_labels!=rows[0].shuffled_labels
           or row.chronology_receipt_sha256!=chronology.receipt_sha256
           or row.objective!=rows[0].objective
           for row in rows):raise RecoveryRefusal("mixed model roster publication")
    artifact=MappingProxyType({**core,"receipt_sha256":C.object_sha256(core)})
    target=C.assert_workspace_output(path)
    if target.is_file():
        try:stored=json.loads(target.read_text())
        except (OSError,UnicodeError,json.JSONDecodeError) as exc:
            raise RecoveryRefusal("cannot resume seed model roster") from exc
        if stored!=C.canonical_json_value(artifact):
            raise RecoveryRefusal("resumed seed model roster differs")
        return MappingProxyType(stored)
    C.atomic_json(target,artifact);return artifact


def load_seed_rosters(path:str|Path)->tuple[SeedModelRoster,...]:
    source=Path(path);C.guard_payload(source)
    try:value=json.loads(source.read_text())
    except (OSError,UnicodeError,json.JSONDecodeError) as exc:
        raise RecoveryRefusal("cannot read seed model roster") from exc
    core={key:item for key,item in value.items() if key!="receipt_sha256"}
    if (value.get("schema")!="QRE2TABSEEDROSTER4"
            or C.object_sha256(core)!=value.get("receipt_sha256")):
        raise RecoveryRefusal("seed model roster artifact differs")
    output=[]
    for raw in value["rosters"]:
        row=dict(raw);folds=[]
        for raw_fold in row["folds"]:
            fold=dict(raw_fold);fold["score_range"]=tuple(fold["score_range"])
            fitted=FittedFold(**fold);fitted.__post_init__()
            bundle=(load_component_model(fitted.bundle_path)
                    if fitted.kind=="COMPONENT" else
                    load_action_model(fitted.bundle_path))
            if (bundle.receipt_sha256!=fitted.bundle_receipt_sha256
                    or bundle.seed!=fitted.seed
                    or bundle.shuffled_labels!=fitted.shuffled_labels
                    or bundle.shuffle_seed!=fitted.shuffle_seed):
                raise RecoveryRefusal("seed roster nested model differs on reload")
            if fitted.kind=="COMPONENT":
                assert fitted.prediction_path is not None
                table=ComponentPredictionTable.load(fitted.prediction_path)
                if (table.receipt_sha256
                        !=fitted.prediction_receipt_sha256
                        or table.model_receipt_sha256
                        !=fitted.bundle_receipt_sha256):
                    raise RecoveryRefusal(
                        "seed roster nested prediction differs on reload")
            folds.append(fitted)
        row["folds"]=tuple(folds)
        roster=SeedModelRoster(**row);roster.__post_init__();output.append(roster)
    rows=tuple(output)
    if (len(rows)!=5 or len({row.seed for row in rows})!=5
            or any(row.kind!=value["kind"]
                   or row.learner_backend!=value["learner_backend"]
                   or row.shuffled_labels!=value["shuffled_labels"] for row in rows)):
        raise RecoveryRefusal("seed model roster publication differs on reload")
    return rows


__all__=["ActionPredictionTable","EXPERIMENT_SCHEMA","FittedFold","SeedModelRoster",
         "action_prediction_requirements",
         "fit_action_seed","fit_component_seed","predict_component_fold",
         "predict_component_roster","predict_action_oof",
         "publish_seed_roster","load_seed_rosters"]
