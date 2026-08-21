"""Crash-resumable orchestration for the Entry V2 tabular recovery campaign.

This module owns the connected corpus -> chronological component stack ->
portfolio-action stack boundary.  It deliberately does not authorize the
long campaign: the production launcher must additionally load a complete real
pre-H2 rehearsal receipt and all economic gates.
"""

from __future__ import annotations

from dataclasses import asdict,dataclass,replace
import json
from pathlib import Path
from types import MappingProxyType
from typing import Final,Mapping,Sequence

import numpy as np

from . import common as C
from .confirmation_experiment import AuthoritativeConfirmationSessionSpec
from .contracts import SessionRef
from .exact_delayed_teacher import ExactDelayedTeacherDay
from .tabular_campaign import (
    FEATURE_CACHE_SCHEMA,ROLLOUT_TEACHER_CACHE_SCHEMA,TEACHER_CACHE_SCHEMA,
    CachedRecoverySession,CachedTeacherDay,_read_manifest,
    materialize_feature_corpus,
    materialize_relation_feature_corpus,materialize_rollout_teacher_corpus,
)
from .tabular_delayed_corpus import CausalFeatureShard
from .tabular_feature_audit_store import (
    load_feature_audit_store,load_or_audit_causal_feature_roster_paths,
)
from .tabular_experiment import (
    ActionPredictionTable,SeedModelRoster,action_prediction_requirements,
    fit_action_seed,fit_component_seed,load_seed_rosters,
    predict_action_oof,predict_component_roster,publish_seed_roster,
)
from .tabular_matrix_store import (
    close_action_matrix,close_component_matrix,
    combine_action_day_stores,combine_component_day_stores,
    load_action_matrix,load_component_matrix,load_existing_action_matrix,
    load_existing_component_matrix,materialize_action_day_stores,
    materialize_component_day_stores,
)
from .tabular_recovery_contracts import (
    CausalFeatureSchema,RecoveryChronology,RecoveryConfig,RecoveryRefusal,
)
from .tabular_training import ComponentPredictionTable


CURRICULUM_SCHEMA:Final="QRE2TABCURRICULUMROUND2"
TWO_ROUND_SCHEMA:Final="QRE2TABTWOROUNDCURRICULUM2"


def _sha(value:object)->bool:
    return (isinstance(value,str) and len(value)==64
            and all(char in "0123456789abcdef" for char in value))


def _strict_json(path:Path,value:Mapping[str,object])->str:
    target=C.assert_workspace_output(path);raw=C.canonical_bytes(value)
    if target.is_file():
        if target.read_bytes()!=raw:
            raise RecoveryRefusal("resumed curriculum artifact differs")
        return C.file_sha256(target)
    return C.atomic_json(target,value)


def _schema_from_mapping(value:Mapping[str,object])->CausalFeatureSchema:
    row=dict(value);row["names"]=tuple(row["names"])
    row["removed_constants"]=tuple(row["removed_constants"])
    row["removed_duplicates"]=tuple(
        tuple(pair) for pair in row["removed_duplicates"])
    row["removed_proven_leaks"]=tuple(row["removed_proven_leaks"])
    row["relation_source_features"]=tuple(
        row.get("relation_source_features",()))
    result=CausalFeatureSchema(**row);result.__post_init__();return result


def _relation_schema_audit(schema:CausalFeatureSchema,
        audit:Mapping[str,object],relation_sources:Sequence[str]
        )->tuple[CausalFeatureSchema,Mapping[str,object]]:
    selected=tuple(map(str,relation_sources))
    if not selected:return schema,audit
    result=replace(schema,relation_source_features=selected)
    result.__post_init__()
    core={"schema":"QRE2TABRELATIONFEATUREAUDIT1",
        "base_audit_receipt_sha256":audit["receipt_sha256"],
        "unstable_absolute_features":selected,
        "feature_schema_receipt_sha256":result.receipt_sha256,
        "runtime_transform":"PREFIX_ONLY_ENCODE_CAUSAL_RELATIONS",
        "h2_open_count":0}
    return result,MappingProxyType({**core,"receipt_sha256":C.object_sha256(core)})


@dataclass(frozen=True,slots=True)
class CurriculumRoundResult:
    round_index:int
    learner_backend:str
    action_backend:str
    feature_schema:CausalFeatureSchema
    feature_audit_path:str
    feature_audit_receipt_sha256:str
    component_matrix_path:str
    component_matrix_receipt_sha256:str
    component_roster_paths:Mapping[str,str]
    component_oof_paths:Mapping[str,str]
    action_matrix_paths:Mapping[str,str]
    action_roster_paths:Mapping[str,str]
    action_oof_paths:Mapping[str,str]
    teacher_paths:tuple[str,...]
    feature_paths:tuple[str,...]
    chronology_receipt_sha256:str
    config_receipt_sha256:str
    manifest_path:str
    receipt_sha256:str

    def __post_init__(self)->None:
        self.feature_schema.__post_init__()
        expected={f"{lane}:{seed}" for lane in ("real","shuffle")
                  for seed in RecoveryConfig().real_seeds}
        if (self.round_index not in (0,1,2)
                or self.learner_backend not in {
                    "CATBOOST","LIGHTGBM","XGBOOST"}
                or self.action_backend not in {
                    "CATBOOST","LIGHTGBM","XGBOOST","CAUSAL_EXPERTS"}
                or set(self.component_roster_paths)!={"real","shuffle"}
                or set(self.action_roster_paths)!={"real","shuffle"}
                or set(self.component_oof_paths)!=expected
                or set(self.action_matrix_paths)!=expected
                or set(self.action_oof_paths)!=expected
                or not self.feature_audit_path
                or not self.teacher_paths or not self.feature_paths
                or len(self.teacher_paths)!=len(set(self.teacher_paths))
                or len(self.feature_paths)!=len(set(self.feature_paths))
                or not all(_sha(value) for value in (
                    self.feature_audit_receipt_sha256,
                    self.component_matrix_receipt_sha256,
                    self.chronology_receipt_sha256,self.config_receipt_sha256,
                    self.receipt_sha256))):
            raise RecoveryRefusal("curriculum round result is malformed")

    @property
    def component_rosters(self)->Mapping[str,tuple[SeedModelRoster,...]]:
        return MappingProxyType({lane:load_seed_rosters(path)
            for lane,path in self.component_roster_paths.items()})

    @property
    def action_rosters(self)->Mapping[str,tuple[SeedModelRoster,...]]:
        return MappingProxyType({lane:load_seed_rosters(path)
            for lane,path in self.action_roster_paths.items()})


@dataclass(frozen=True,slots=True)
class TwoRoundCurriculumResult:
    """The sole complete 0 -> rollout-1 -> rollout-2 curriculum chain."""

    rounds:tuple[CurriculumRoundResult,...]
    final_teachers:tuple[CachedTeacherDay,...]
    final_features:tuple[CachedRecoverySession,...]
    feature_audit_receipts:tuple[str,...]
    learner_backend:str
    action_backend:str
    relation_source_features:tuple[str,...]
    chronology_receipt_sha256:str
    config_receipt_sha256:str
    manifest_path:str
    receipt_sha256:str

    def __post_init__(self)->None:
        if (tuple(row.round_index for row in self.rounds)!=(0,1,2)
                or self.learner_backend not in {
                    "CATBOOST","LIGHTGBM","XGBOOST"}
                or self.action_backend not in {
                    "CATBOOST","LIGHTGBM","XGBOOST","CAUSAL_EXPERTS"}
                or any(row.learner_backend!=self.learner_backend
                       for row in self.rounds)
                or any(row.action_backend!=self.action_backend
                       for row in self.rounds)
                or len(self.relation_source_features)
                   !=len(set(self.relation_source_features))
                or any(row.feature_schema.relation_source_features
                       !=self.relation_source_features for row in self.rounds)
                or len(self.feature_audit_receipts)!=3
                or not self.final_teachers or not self.final_features
                or tuple(sorted(self.final_teachers,
                    key=lambda row:row.trading_day))!=self.final_teachers
                or len({row.trading_day for row in self.final_teachers})
                   !=len(self.final_teachers)
                or tuple(sorted(self.final_features,
                    key=lambda row:row.session))!=self.final_features
                or len({row.session for row in self.final_features})
                   !=len(self.final_features)
                or any(row.status!="MATERIALIZED"
                       for row in self.final_features)
                or {row.artifact_path for row in self.final_teachers}
                   !=set(self.rounds[-1].teacher_paths)
                or {row.artifact_path for row in self.final_features}
                   !=set(self.rounds[-1].feature_paths)
                or any(row.chronology_receipt_sha256
                       !=self.chronology_receipt_sha256 for row in self.rounds)
                or any(row.config_receipt_sha256
                       !=self.config_receipt_sha256 for row in self.rounds)
                or not all(_sha(value) for value in (
                    *self.feature_audit_receipts,
                    self.chronology_receipt_sha256,
                    self.config_receipt_sha256,self.receipt_sha256))):
            raise RecoveryRefusal("two-round curriculum result is malformed")
        chronology_days=tuple(day for row in self.final_teachers
                              for day in (row.trading_day,))
        if any(day>=C.HOLDOUT_START_D8 for day in chronology_days):
            raise RecoveryRefusal("two-round curriculum attempted to open H2")

    @property
    def final_round(self)->CurriculumRoundResult:
        return self.rounds[-1]


def _lane_key(lane:str,seed:int)->str:
    return f"{lane}:{int(seed)}"


def _feature_and_teacher_paths(
        features:Sequence[CachedRecoverySession],
        teachers:Sequence[CachedTeacherDay])->tuple[tuple[str,...],tuple[str,...]]:
    feature_paths=tuple(sorted(str(row.artifact_path) for row in features
                               if row.status=="MATERIALIZED" and row.artifact_path))
    teacher_paths=tuple(str(row.artifact_path) for row in sorted(
        teachers,key=lambda item:item.trading_day))
    if not feature_paths or not teacher_paths:
        raise RecoveryRefusal("curriculum round has no feature/teacher artifacts")
    feature_days={row.session.trading_day for row in features
                  if row.status=="MATERIALIZED" and row.artifact_path}
    teacher_days={row.trading_day for row in teachers}
    if feature_days!=teacher_days:
        raise RecoveryRefusal("curriculum feature/teacher day rosters differ")
    return feature_paths,teacher_paths


def _component_roster_map(
        previous:Mapping[str,Sequence[SeedModelRoster]]|None,
        )->Mapping[str,tuple[SeedModelRoster,...]]|None:
    if previous is None:return None
    if set(previous)!={"real","shuffle"}:
        raise RecoveryRefusal("previous component roster lanes differ")
    output={lane:tuple(sorted(rows,key=lambda row:row.seed))
            for lane,rows in previous.items()}
    config=RecoveryConfig()
    for lane,rows in output.items():
        if (len(rows)!=5 or tuple(row.seed for row in rows)!=config.real_seeds
                or any(row.kind!="COMPONENT" for row in rows)
                or any(row.shuffled_labels!=(lane=="shuffle") for row in rows)):
            raise RecoveryRefusal("previous component five-seed roster differs")
    return MappingProxyType(output)


def fit_curriculum_round(*,round_index:int,
        features:Sequence[CachedRecoverySession],
        teachers:Sequence[CachedTeacherDay],feature_schema:CausalFeatureSchema,
        feature_audit_path:str,feature_audit_receipt_sha256:str,
        chronology:RecoveryChronology,
        config:RecoveryConfig,output_root:str|Path,
        previous_component_rosters:Mapping[
            str,Sequence[SeedModelRoster]]|None=None,
        previous_component_matrix_path:str|None=None,
        action_objective:str="MultiRMSE",
        learner_backend:str="CATBOOST",
        action_backend:str|None=None)->CurriculumRoundResult:
    """Fit or resume all five real and five matched shuffled fold chains."""

    if round_index not in (0,1,2):
        raise RecoveryRefusal("curriculum fit round must be 0, 1, or 2")
    feature_schema.__post_init__();chronology.__post_init__();config.__post_init__()
    learner_backend=str(learner_backend).upper()
    action_backend=(learner_backend if action_backend is None
                    else str(action_backend).upper())
    if learner_backend not in {"CATBOOST","LIGHTGBM","XGBOOST"}:
        raise RecoveryRefusal("curriculum learner backend is unregistered")
    if action_backend not in {
            "CATBOOST","LIGHTGBM","XGBOOST","CAUSAL_EXPERTS"}:
        raise RecoveryRefusal("curriculum action backend is unregistered")
    if not feature_audit_path or not _sha(feature_audit_receipt_sha256):
        raise RecoveryRefusal("curriculum feature audit receipt is malformed")
    previous=_component_roster_map(previous_component_rosters)
    if (previous is None)!=(previous_component_matrix_path is None):
        raise RecoveryRefusal("component reuse matrix/roster inputs are incomplete")
    root=C.assert_workspace_output(output_root)/f"round_{round_index}"
    existing=root/"curriculum_round.json"
    if existing.is_file():
        return load_curriculum_round(existing,chronology=chronology,config=config)
    feature_paths,teacher_paths=_feature_and_teacher_paths(features,teachers)
    requirements=action_prediction_requirements(teacher_paths)

    if previous is None:
        component_matrix=load_existing_component_matrix(
            root/"component_matrix",feature_names=feature_schema.names)
        if component_matrix is None:
            component_days=materialize_component_day_stores(
                feature_paths=feature_paths,teacher_paths=teacher_paths,
                feature_schema=feature_schema,output_root=root/"matrix_days")
            component_matrix=combine_component_day_stores(
                component_days,root/"component_matrix")
    else:
        component_matrix=load_component_matrix(previous_component_matrix_path)
        if component_matrix.feature_names!=feature_schema.names:
            raise RecoveryRefusal(
                "component feature names changed; reuse is not authorized")
    component_matrix_receipt=component_matrix.receipt_sha256
    component_matrix_path=str(Path(component_matrix.x.filename).parent
        if isinstance(component_matrix.x,np.memmap)
        else previous_component_matrix_path or root/"component_matrix")

    component_rosters:dict[str,list[SeedModelRoster]]={"real":[],"shuffle":[]}
    component_tables:dict[str,ComponentPredictionTable]={}
    for lane in ("real","shuffle"):
        for position,seed in enumerate(config.real_seeds):
            key=_lane_key(lane,seed)
            if previous is None:
                shuffle_seed=(config.shuffle_seeds[position]
                              if lane=="shuffle" else None)
                roster,table=fit_component_seed(matrix=component_matrix,
                    feature_paths=feature_paths,feature_schema=feature_schema,
                    required_opportunity_ids_by_day=requirements,
                    chronology=chronology,config=config,seed=seed,
                    output_root=root/"component_models",
                    shuffled_labels=lane=="shuffle",shuffle_seed=shuffle_seed,
                    learner_backend=learner_backend)
            else:
                roster=previous[lane][position]
                if roster.learner_backend!=learner_backend:
                    raise RecoveryRefusal("component reuse backend differs")
                table=predict_component_roster(roster=roster,
                    feature_paths=feature_paths,feature_schema=feature_schema,
                    required_opportunity_ids_by_day=requirements,
                    output_root=root/"component_rescore"/lane/f"seed_{seed}")
            component_rosters[lane].append(roster);component_tables[key]=table

    component_roster_paths={}
    for lane in ("real","shuffle"):
        path=root/f"component_{lane}_roster.json"
        if previous is None:
            publish_seed_roster(path,component_rosters[lane],chronology=chronology)
        else:
            # Publish the unchanged model roster in this round as an explicit
            # dependency; its older OOF path remains historical evidence.
            publish_seed_roster(path,component_rosters[lane],chronology=chronology)
        component_roster_paths[lane]=str(path)
    close_component_matrix(component_matrix)

    action_matrix_receipts={};action_rosters:dict[str,list[SeedModelRoster]]={
        "real":[],"shuffle":[]};action_tables={}
    for lane in ("real","shuffle"):
        for position,seed in enumerate(config.real_seeds):
            key=_lane_key(lane,seed);component_oof=component_tables[key]
            action_target=root/"action_matrices"/lane/f"seed_{seed}"
            matrix=load_existing_action_matrix(action_target)
            if matrix is None:
                day_stores=materialize_action_day_stores(
                    feature_paths=feature_paths,teacher_paths=teacher_paths,
                    component_oof=component_oof,feature_schema=feature_schema,
                    output_root=root/"action_matrix_days"/lane/f"seed_{seed}")
                matrix=combine_action_day_stores(day_stores,action_target)
            try:
                shuffle_seed=(config.shuffle_seeds[position]
                              if lane=="shuffle" else None)
                roster=fit_action_seed(matrix=matrix,chronology=chronology,
                    config=config,seed=seed,output_root=root/"action_models",
                    objective=action_objective,shuffled_labels=lane=="shuffle",
                    shuffle_seed=shuffle_seed,learner_backend=action_backend)
                prediction=predict_action_oof(matrix=matrix,roster=roster,
                    output_path=root/"action_models"/action_backend.lower()/lane/
                        f"seed_{seed}"/
                        "action_oof_all.npz")
                action_matrix_receipts[key]=matrix.receipt_sha256
            finally:close_action_matrix(matrix)
            action_rosters[lane].append(roster)
            action_tables[key]=prediction

    action_roster_paths={}
    for lane in ("real","shuffle"):
        path=root/f"action_{lane}_roster.json"
        publish_seed_roster(path,action_rosters[lane],chronology=chronology)
        action_roster_paths[lane]=str(path)

    core={"schema":CURRICULUM_SCHEMA,"round_index":round_index,
        "learner_backend":learner_backend,
        "action_backend":action_backend,
        "feature_schema":asdict(feature_schema),
        "feature_audit_path":str(Path(feature_audit_path).resolve()),
        "feature_audit_receipt_sha256":feature_audit_receipt_sha256,
        "chronology_receipt_sha256":chronology.receipt_sha256,
        "config_receipt_sha256":config.receipt_sha256,
        "component_matrix_path":component_matrix_path,
        "component_matrix_receipt_sha256":component_matrix_receipt,
        "component_reused":previous is not None,
        "component_roster_paths":component_roster_paths,
        "component_roster_receipts":{
            lane:tuple(row.receipt_sha256 for row in rows)
            for lane,rows in component_rosters.items()},
        "component_oof_paths":{key:str(
            root/"component_rescore"/key.split(":")[0]/f"seed_{key.split(':')[1]}"/
                "component_oof_all.npz") if previous is not None else str(
            root/"component_models"/learner_backend.lower()/key.split(":")[0]/
                f"seed_{key.split(':')[1]}"/
                "component_oof_all.npz") for key in component_tables},
        "component_oof_receipts":{
            key:value.receipt_sha256 for key,value in component_tables.items()},
        "action_matrix_paths":{key:str(root/"action_matrices"/
            key.split(":")[0]/f"seed_{key.split(':')[1]}")
            for key in action_matrix_receipts},
        "action_matrix_receipts":action_matrix_receipts,
        "action_roster_paths":action_roster_paths,
        "action_roster_receipts":{
            lane:tuple(row.receipt_sha256 for row in rows)
            for lane,rows in action_rosters.items()},
        "action_oof_paths":{key:str(root/"action_models"/
            action_backend.lower()/key.split(":")[0]/
            f"seed_{key.split(':')[1]}"/"action_oof_all.npz")
            for key in action_tables},
        "action_oof_receipts":{
            key:value.receipt_sha256 for key,value in action_tables.items()},
        "teacher_paths":teacher_paths,
        "teacher_receipts":tuple(row.representation_sha256 for row in sorted(
            teachers,key=lambda item:item.trading_day)),
        "feature_paths":feature_paths,
        "feature_receipts":tuple({str(row.artifact_path):row.representation_sha256
            for row in features}[path] for path in feature_paths),
        "rollout_rounds_completed":round_index,"required_rollout_rounds":2,
        "five_real_seeds":True,"five_matched_shuffle_controls":True,
        "top_k_roster_filter":False,"h2_open_count":0}
    artifact={**core,"receipt_sha256":C.object_sha256(core)}
    manifest=root/"curriculum_round.json";_strict_json(manifest,artifact)
    result=CurriculumRoundResult(round_index,learner_backend,action_backend,
        feature_schema,str(core["feature_audit_path"]),
        feature_audit_receipt_sha256,
        str(core["component_matrix_path"]),component_matrix_receipt,
        MappingProxyType(component_roster_paths),
        MappingProxyType(dict(core["component_oof_paths"])),
        MappingProxyType(dict(core["action_matrix_paths"])),
        MappingProxyType(action_roster_paths),
        MappingProxyType(dict(core["action_oof_paths"])),teacher_paths,
        feature_paths,chronology.receipt_sha256,config.receipt_sha256,
        str(manifest),artifact["receipt_sha256"])
    result.__post_init__();return result


def load_curriculum_round(path:str|Path,*,chronology:RecoveryChronology,
                          config:RecoveryConfig)->CurriculumRoundResult:
    source=Path(path);C.guard_payload(source)
    try:value=json.loads(source.read_text())
    except (OSError,UnicodeError,json.JSONDecodeError) as exc:
        raise RecoveryRefusal("cannot strict-load curriculum round") from exc
    core={key:item for key,item in value.items() if key!="receipt_sha256"}
    if (value.get("schema")!=CURRICULUM_SCHEMA
            or C.object_sha256(core)!=value.get("receipt_sha256")
            or value.get("chronology_receipt_sha256")!=chronology.receipt_sha256
            or value.get("config_receipt_sha256")!=config.receipt_sha256):
        raise RecoveryRefusal("curriculum round manifest differs")
    learner_backend=str(value.get("learner_backend",""))
    action_backend=str(value.get("action_backend",""))
    if (learner_backend not in {"CATBOOST","LIGHTGBM","XGBOOST"}
            or action_backend not in {
                "CATBOOST","LIGHTGBM","XGBOOST","CAUSAL_EXPERTS"}):
        raise RecoveryRefusal("curriculum round backend differs")
    schema=_schema_from_mapping(value["feature_schema"])
    component=load_component_matrix(value["component_matrix_path"])
    if component.receipt_sha256!=value["component_matrix_receipt_sha256"]:
        raise RecoveryRefusal("curriculum component matrix differs")
    for lane,path_value in value["component_roster_paths"].items():
        rows=load_seed_rosters(path_value)
        if tuple(row.receipt_sha256 for row in rows)!=tuple(
                value["component_roster_receipts"][lane]):
            raise RecoveryRefusal("curriculum component roster differs")
    for lane,path_value in value["action_roster_paths"].items():
        rows=load_seed_rosters(path_value)
        if tuple(row.receipt_sha256 for row in rows)!=tuple(
                value["action_roster_receipts"][lane]):
            raise RecoveryRefusal("curriculum action roster differs")
    for key,path_value in value["component_oof_paths"].items():
        if ComponentPredictionTable.load(path_value).receipt_sha256!=value[
                "component_oof_receipts"][key]:
            raise RecoveryRefusal("curriculum component OOF differs")
    for key,path_value in value["action_matrix_paths"].items():
        if load_action_matrix(path_value).receipt_sha256!=value[
                "action_matrix_receipts"][key]:
            raise RecoveryRefusal("curriculum action matrix differs")
    for key,path_value in value["action_oof_paths"].items():
        if ActionPredictionTable.load(path_value).receipt_sha256!=value[
                "action_oof_receipts"][key]:
            raise RecoveryRefusal("curriculum action OOF differs")
    if (len(value["teacher_paths"])!=len(value["teacher_receipts"])
            or len(value["feature_paths"])!=len(value["feature_receipts"])):
        raise RecoveryRefusal("curriculum source artifact roster differs")
    for path_value,receipt in zip(value["teacher_paths"],
                                  value["teacher_receipts"]):
        if ExactDelayedTeacherDay.load(path_value).representation_sha256!=receipt:
            raise RecoveryRefusal("curriculum teacher artifact differs")
    for path_value,receipt in zip(value["feature_paths"],
                                  value["feature_receipts"]):
        if CausalFeatureShard.load(path_value).representation_sha256!=receipt:
            raise RecoveryRefusal("curriculum feature artifact differs")
    result=CurriculumRoundResult(int(value["round_index"]),learner_backend,
        action_backend,schema,str(value["feature_audit_path"]),
        str(value["feature_audit_receipt_sha256"]),
        str(value["component_matrix_path"]),
        str(value["component_matrix_receipt_sha256"]),
        MappingProxyType(dict(value["component_roster_paths"])),
        MappingProxyType(dict(value["component_oof_paths"])),
        MappingProxyType(dict(value["action_matrix_paths"])),
        MappingProxyType(dict(value["action_roster_paths"])),
        MappingProxyType(dict(value["action_oof_paths"])),
        tuple(value["teacher_paths"]),tuple(value["feature_paths"]),
        str(value["chronology_receipt_sha256"]),
        str(value["config_receipt_sha256"]),str(source),
        str(value["receipt_sha256"]));result.__post_init__();return result


def _rollout_covered(day:int,chronology:RecoveryChronology)->bool:
    return any(score_lo<=int(day)<=score_hi for (
        _name,_train_lo,_train_hi,_val_lo,_val_hi,score_lo,score_hi)
        in chronology.action_folds)


def _merge_round_features(*,current:Sequence[CachedRecoverySession],
        replacements:Sequence[CachedRecoverySession],changed_days:set[int],
        outcomes:Sequence[CachedRecoverySession])->tuple[CachedRecoverySession,...]:
    existing={row.session:row for row in current}
    if len(existing)!=len(tuple(current)):
        raise RecoveryRefusal("curriculum feature session repeats")
    updated={row.session:row for row in replacements}
    expected={row.session for row in outcomes
              if row.status=="MATERIALIZED"
              and row.session.trading_day in changed_days}
    if set(updated)!=expected or any(row.status!="MATERIALIZED"
                                     for row in updated.values()):
        raise RecoveryRefusal("rollout feature replacement roster differs")
    existing.update(updated)
    result=tuple(sorted(existing.values(),key=lambda row:row.session))
    if {row.session for row in result}!={row.session for row in outcomes
                                        if row.status=="MATERIALIZED"}:
        raise RecoveryRefusal("merged curriculum feature roster differs")
    return result


def run_two_round_curriculum(*,
        specs:Sequence[AuthoritativeConfirmationSessionSpec],
        outcomes:Sequence[CachedRecoverySession],
        initial_teachers:Sequence[CachedTeacherDay],
        initial_features:Sequence[CachedRecoverySession],
        all_sessions:Sequence[SessionRef],chronology:RecoveryChronology,
        config:RecoveryConfig,cache_root:str|Path,output_root:str|Path,
        workers:int=16,action_objective:str="MultiRMSE",
        learner_backend:str="CATBOOST",
        action_backend:str|None=None,
        relation_source_features:Sequence[str]=(),
        )->TwoRoundCurriculumResult:
    """Fit the initial policy and perform exactly two OOF rollout relabels.

    Each rollout uses only the five real chronological OOF policies.  Shuffled
    controls traverse the identical fitting and replay code, but can never
    create teacher labels.  Newly requested action seconds are rematerialized
    with the production causal feature implementation before the next fit.
    """

    chronology.__post_init__();config.__post_init__()
    learner_backend=str(learner_backend).upper()
    action_backend=(learner_backend if action_backend is None
                    else str(action_backend).upper())
    relation_sources=tuple(map(str,relation_source_features))
    if learner_backend not in {"CATBOOST","LIGHTGBM","XGBOOST"}:
        raise RecoveryRefusal("two-round learner backend is unregistered")
    if action_backend not in {
            "CATBOOST","LIGHTGBM","XGBOOST","CAUSAL_EXPERTS"}:
        raise RecoveryRefusal("two-round action backend is unregistered")
    if len(relation_sources)!=len(set(relation_sources)):
        raise RecoveryRefusal("two-round relation source roster repeats")
    if workers!=config.workers or config.rollout_relabel_rounds!=2:
        raise RecoveryRefusal("curriculum worker/rollout configuration differs")
    spec_rows=tuple(sorted(specs,key=lambda row:row.session))
    outcome_rows=tuple(sorted(outcomes,key=lambda row:row.session))
    teacher_rows=tuple(sorted(initial_teachers,key=lambda row:row.trading_day))
    feature_rows=tuple(sorted(initial_features,key=lambda row:row.session))
    session_rows=tuple(sorted(all_sessions))
    if (not spec_rows or {row.session for row in spec_rows}!=set(session_rows)
            or len(spec_rows)!=len(session_rows)
            or {row.session for row in outcome_rows}!=set(session_rows)
            or len(outcome_rows)!=len(session_rows)
            or any(row.rollout_rounds_completed!=0 for row in teacher_rows)
            or any(row.status!="MATERIALIZED" for row in feature_rows)
            or any(row.session.trading_day>=C.HOLDOUT_START_D8
                   for row in outcome_rows)):
        raise RecoveryRefusal("initial two-round corpus roster differs/seal opened")
    active_sessions={row.session for row in outcome_rows
                     if row.status=="MATERIALIZED"}
    active_days={row.session.trading_day for row in outcome_rows
                 if row.status=="MATERIALIZED"}
    if ({row.session for row in feature_rows}!=active_sessions
            or {row.trading_day for row in teacher_rows}!=active_days
            or len({row.session for row in feature_rows})!=len(feature_rows)
            or len({row.trading_day for row in teacher_rows})!=len(teacher_rows)):
        raise RecoveryRefusal("initial teacher/feature active roster differs")

    root=C.assert_workspace_output(output_root)
    cache=C.assert_workspace_output(cache_root)
    invocation=C.object_sha256({"schema":TWO_ROUND_SCHEMA,
        "specs":tuple(asdict(row) for row in spec_rows),
        "outcomes":tuple(row.receipt_sha256 for row in outcome_rows),
        "initial_teachers":tuple(row.receipt_sha256 for row in teacher_rows),
        "initial_features":tuple(row.receipt_sha256 for row in feature_rows),
        "sessions":tuple(asdict(row) for row in session_rows),
        "chronology":chronology.receipt_sha256,"config":config.receipt_sha256,
        "workers":workers,"action_objective":action_objective,
        "learner_backend":learner_backend,"action_backend":action_backend,
        "relation_source_features":relation_sources})
    manifest=root/"two_round_curriculum.json"
    if manifest.is_file():
        value=_read_manifest(manifest,TWO_ROUND_SCHEMA)
        if value.get("invocation_receipt_sha256")!=invocation:
            raise RecoveryRefusal("resumed two-round curriculum inputs differ")
        return load_two_round_curriculum(manifest,chronology=chronology,
                                         config=config)

    if relation_sources:
        feature_rows=materialize_relation_feature_corpus(feature_rows,
            unstable_absolute_features=relation_sources,
            cache_root=cache/"relations",round_index=0,workers=workers)
    feature_schema,audit,audit_path=load_or_audit_causal_feature_roster_paths(tuple(sorted(
        row.artifact_path for row in feature_rows
        if row.artifact_path is not None)))
    feature_schema,audit=_relation_schema_audit(
        feature_schema,audit,relation_sources)
    rounds=[fit_curriculum_round(round_index=0,features=feature_rows,
        teachers=teacher_rows,feature_schema=feature_schema,
        feature_audit_path=str(audit_path),
        feature_audit_receipt_sha256=str(audit["receipt_sha256"]),
        chronology=chronology,config=config,output_root=root/"fits",
        action_objective=action_objective,learner_backend=learner_backend,
        action_backend=action_backend)]
    audits=[str(audit["receipt_sha256"])]
    current_teachers=teacher_rows;current_features=feature_rows

    for round_index in (1,2):
        prior=rounds[-1]
        updated_teachers=materialize_rollout_teacher_corpus(
            previous_teachers=current_teachers,outcomes=outcome_rows,
            specs=spec_rows,all_sessions=session_rows,
            feature_schema=prior.feature_schema,
            component_rosters=prior.component_rosters["real"],
            action_rosters=prior.action_rosters["real"],
            cache_root=cache/"rollout",round_index=round_index,
            workers=workers)
        changed_days={new.trading_day for old,new in zip(
            current_teachers,updated_teachers)
            if old.artifact_path!=new.artifact_path
            or old.representation_sha256!=new.representation_sha256}
        expected_changed={row.trading_day for row in current_teachers
                          if _rollout_covered(row.trading_day,chronology)}
        if changed_days!=expected_changed:
            raise RecoveryRefusal("rollout did not update every OOF teacher day")
        replacement_features=materialize_feature_corpus(
            tuple(row for row in spec_rows if row.trading_day in changed_days),
            tuple(row for row in outcome_rows
                  if row.session.trading_day in changed_days),
            tuple(row for row in updated_teachers
                  if row.trading_day in changed_days),
            cache_root=cache/"features",round_index=round_index,
            workers=workers)
        if relation_sources:
            replacement_features=materialize_relation_feature_corpus(
                replacement_features,unstable_absolute_features=relation_sources,
                cache_root=cache/"relations",round_index=round_index,
                workers=workers)
        current_features=_merge_round_features(current=current_features,
            replacements=replacement_features,changed_days=changed_days,
            outcomes=outcome_rows)
        current_teachers=tuple(updated_teachers)
        schema,audit,audit_path=load_or_audit_causal_feature_roster_paths(tuple(sorted(
            row.artifact_path for row in current_features
            if row.artifact_path is not None)))
        schema,audit=_relation_schema_audit(schema,audit,relation_sources)
        same_names=schema.names==prior.feature_schema.names
        rounds.append(fit_curriculum_round(round_index=round_index,
            features=current_features,teachers=current_teachers,
            feature_schema=schema,
            feature_audit_path=str(audit_path),
            feature_audit_receipt_sha256=str(audit["receipt_sha256"]),
            chronology=chronology,config=config,output_root=root/"fits",
            previous_component_rosters=(prior.component_rosters
                                        if same_names else None),
            previous_component_matrix_path=(prior.component_matrix_path
                                            if same_names else None),
            action_objective=action_objective,
            learner_backend=learner_backend,action_backend=action_backend))
        audits.append(str(audit["receipt_sha256"]))

    for row in current_teachers:
        expected=2 if _rollout_covered(row.trading_day,chronology) else 0
        if row.rollout_rounds_completed!=expected:
            raise RecoveryRefusal("final teacher has incomplete rollout lineage")
    core={"schema":TWO_ROUND_SCHEMA,
        "invocation_receipt_sha256":invocation,
        "round_manifest_paths":tuple(row.manifest_path for row in rounds),
        "round_receipts":tuple(row.receipt_sha256 for row in rounds),
        "final_teachers":tuple(asdict(row) for row in current_teachers),
        "final_features":tuple(asdict(row) for row in current_features),
        "feature_audit_receipts":tuple(audits),
        "learner_backend":learner_backend,
        "action_backend":action_backend,
        "relation_source_features":relation_sources,
        "chronology_receipt_sha256":chronology.receipt_sha256,
        "config_receipt_sha256":config.receipt_sha256,
        "rollout_rounds_completed":2,"required_rollout_rounds":2,
        "rollout_teacher_lane":"FIVE_REAL_CHRONOLOGICAL_OOF",
        "shuffle_teacher_use":False,"workers":16,
        "top_k_roster_filter":False,"h2_open_count":0}
    artifact={**core,"receipt_sha256":C.object_sha256(core)}
    _strict_json(manifest,artifact)
    return load_two_round_curriculum(manifest,chronology=chronology,
                                     config=config)


def _cached_feature(value:Mapping[str,object])->CachedRecoverySession:
    row=dict(value);row["session"]=SessionRef(**row["session"])
    result=CachedRecoverySession(**row);result.__post_init__();return result


def load_two_round_curriculum(path:str|Path,*,chronology:RecoveryChronology,
                              config:RecoveryConfig)->TwoRoundCurriculumResult:
    source=Path(path);value=_read_manifest(source,TWO_ROUND_SCHEMA)
    if (value.get("chronology_receipt_sha256")!=chronology.receipt_sha256
            or value.get("config_receipt_sha256")!=config.receipt_sha256
            or value.get("rollout_rounds_completed")!=2
            or value.get("required_rollout_rounds")!=2
            or value.get("shuffle_teacher_use") is not False
            or value.get("learner_backend") not in {
                "CATBOOST","LIGHTGBM","XGBOOST"}
            or value.get("action_backend") not in {
                "CATBOOST","LIGHTGBM","XGBOOST","CAUSAL_EXPERTS"}
            or value.get("h2_open_count")!=0):
        raise RecoveryRefusal("two-round curriculum manifest differs")
    rounds=tuple(load_curriculum_round(round_path,chronology=chronology,
        config=config) for round_path in value["round_manifest_paths"])
    if tuple(row.receipt_sha256 for row in rounds)!=tuple(value["round_receipts"]):
        raise RecoveryRefusal("two-round curriculum round lineage differs")
    teachers=tuple(CachedTeacherDay(**row) for row in value["final_teachers"])
    features=tuple(_cached_feature(row) for row in value["final_features"])
    for row in teachers:
        teacher=ExactDelayedTeacherDay.load(row.artifact_path)
        manifest_path=Path(row.artifact_path).with_suffix(".json")
        schema=(ROLLOUT_TEACHER_CACHE_SCHEMA
                if row.rollout_rounds_completed else TEACHER_CACHE_SCHEMA)
        cached=_read_manifest(manifest_path,schema)
        if (teacher.representation_sha256!=row.representation_sha256
                or cached.get("receipt_sha256")!=row.receipt_sha256
                or cached.get("representation_sha256")
                   !=row.representation_sha256):
            raise RecoveryRefusal("final curriculum teacher cache differs")
        expected=2 if _rollout_covered(row.trading_day,chronology) else 0
        if row.rollout_rounds_completed!=expected:
            raise RecoveryRefusal("strict curriculum rollout count differs")
    for row in features:
        shard=CausalFeatureShard.load(row.artifact_path)
        cached=_read_manifest(Path(row.manifest_path),FEATURE_CACHE_SCHEMA)
        if (shard.representation_sha256!=row.representation_sha256
                or cached.get("receipt_sha256")!=row.receipt_sha256
                or cached.get("representation_sha256")
                   !=row.representation_sha256):
            raise RecoveryRefusal("final curriculum feature cache differs")
    audits=tuple(map(str,value["feature_audit_receipts"]))
    relation_sources=tuple(map(str,value.get("relation_source_features",())))
    for index,round_result in enumerate(rounds):
        schema,audit=load_feature_audit_store(
            round_result.feature_audit_path,
            source_paths=round_result.feature_paths)
        schema,audit=_relation_schema_audit(schema,audit,relation_sources)
        if (audit["receipt_sha256"]!=audits[index]
                or audit["receipt_sha256"]
                   !=round_result.feature_audit_receipt_sha256
                or schema.receipt_sha256
                   !=round_result.feature_schema.receipt_sha256):
            raise RecoveryRefusal("strict curriculum feature audit differs")
    result=TwoRoundCurriculumResult(rounds,teachers,features,audits,
        str(value["learner_backend"]),str(value["action_backend"]),
        relation_sources,
        str(value["chronology_receipt_sha256"]),
        str(value["config_receipt_sha256"]),str(source),
        str(value["receipt_sha256"]));result.__post_init__();return result


__all__=["CURRICULUM_SCHEMA","TWO_ROUND_SCHEMA","CurriculumRoundResult",
         "TwoRoundCurriculumResult","fit_curriculum_round",
         "load_curriculum_round","load_two_round_curriculum",
         "run_two_round_curriculum"]
