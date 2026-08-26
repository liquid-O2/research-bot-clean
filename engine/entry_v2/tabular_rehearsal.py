"""Real-data engineering and launch gates for the tabular recovery lane."""

from __future__ import annotations

from dataclasses import asdict,dataclass,replace
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
from types import MappingProxyType
from typing import Final,Mapping,Sequence

import numpy as np

from . import common as C
from .confirmation_experiment import AuthoritativeConfirmationSessionSpec
from .contracts import SessionRef
from .event_pack import EventPack,HEADER_BYTES,ROW_BYTES
from .exact_delayed_teacher import (
    ExactDelayedTeacherDay,replay_exact_teacher_day,
    replay_perfect_teacher_actions,
)
from .exact_teacher_types import DayOptionUniverse
from .tabular_action_features import build_action_feature_matrix
from .tabular_campaign import (
    CachedRecoverySession,CachedTeacherDay,
    materialize_runtime_dense_feature_session,
)
from .tabular_delayed_corpus import (
    CausalFeatureShard,DelayedOutcomeShard,
    prepare_runtime_feature_shard,
)
from .tabular_feature_audit_store import (
    load_or_audit_causal_feature_roster_paths,
)
from .tabular_experiment import SeedModelRoster
from .tabular_fit_only import FitOnlyExecutionResult,load_fit_only_execution
from .tabular_evaluation import (
    DevelopmentEvaluationResult,load_development_evaluation,
)
from .tabular_orchestration import TwoRoundCurriculumResult
from .tabular_models import ActionModelBundle,ComponentModelBundle
from .tabular_model_io import (
    load_action_model,load_component_model,predict_action_regret,
)
from .tabular_recovery_contracts import (
    CausalFeatureSchema,RecoveryChronology,RecoveryConfig,RecoveryRefusal,
)


ENGINEERING_AUDIT_SCHEMA:Final="QRE2TABREALENGINEERINGAUDIT1"
FUTURE_MUTATION_SCHEMA:Final="QRE2TABREALFUTUREMUTATION1"
LAUNCH_REHEARSAL_SCHEMA:Final="QRE2TABLAUNCHREHEARSAL1"
PRODUCTION_REHEARSAL_SCHEMA:Final="QRE2TABPRODUCTIONREHEARSAL1"


def _sha(value:object)->bool:
    return (isinstance(value,str) and len(value)==64
            and all(char in "0123456789abcdef" for char in value))


def _strict_json(path:Path,value:Mapping[str,object])->str:
    target=C.assert_workspace_output(path);raw=C.canonical_bytes(value)
    if target.is_file():
        if target.read_bytes()!=raw:
            raise RecoveryRefusal("resumed rehearsal artifact differs")
        return C.file_sha256(target)
    return C.atomic_json(target,value)


def _verified_mapping(value:Mapping[str,object],schema:str)->str:
    core={key:item for key,item in value.items() if key!="receipt_sha256"}
    receipt=value.get("receipt_sha256")
    if (value.get("schema")!=schema or value.get("h2_open_count")!=0
            or C.object_sha256(core)!=receipt or not _sha(receipt)):
        raise RecoveryRefusal(f"rehearsal mapping identity differs: {schema}")
    return str(receipt)


def audit_real_teacher_chain(*,outcomes:Sequence[CachedRecoverySession],
        teachers:Sequence[CachedTeacherDay],features:Sequence[CachedRecoverySession],
        all_sessions:Sequence[SessionRef],chronology:RecoveryChronology,
        scope:str,require_rollout_rounds:bool,
        output_path:str|Path)->Mapping[str,object]:
    """Replay every supplied real day and audit outcome/feature invariants."""

    chronology.__post_init__();outcome_by_day={};side_by_asset={name:set()
                                                  for name in C.ASSETS}
    active_sessions=set()
    for cached in outcomes:
        if cached.session.trading_day>=C.HOLDOUT_START_D8:
            raise RecoveryRefusal("engineering audit attempted to open H2")
        if cached.status!="MATERIALIZED":continue
        shard=DelayedOutcomeShard.load(cached.artifact_path);shard.validate()
        if not np.all(np.asarray(shard.cost_applied_count,np.int8)==1):
            raise RecoveryRefusal("real outcome charged cost other than once")
        side_by_asset[cached.session.asset].update(
            map(int,np.unique(shard.side)))
        outcome_by_day.setdefault(cached.session.trading_day,[]).append(shard)
        active_sessions.add(cached.session)
    if any(values!={-1,1} for values in side_by_asset.values()):
        raise RecoveryRefusal("real rehearsal lacks independent long/short sides")
    teacher_by_day={row.trading_day:row for row in teachers}
    if set(teacher_by_day)!=set(outcome_by_day):
        raise RecoveryRefusal("real teacher/outcome day algebra differs")
    sessions_by_day={}
    for row in all_sessions:
        if row.trading_day>=C.HOLDOUT_START_D8:
            raise RecoveryRefusal("engineering denominator opened H2")
        sessions_by_day.setdefault(row.trading_day,[]).append(row)
    replay_receipts=[];perfect_receipts=[];objective=0;entries=0
    for day in sorted(teacher_by_day):
        cached=teacher_by_day[day];teacher=ExactDelayedTeacherDay.load(
            cached.artifact_path)
        universe=DayOptionUniverse.from_shards(tuple(outcome_by_day[day]))
        exact=replay_exact_teacher_day(teacher,universe,
            expected_sessions=tuple(sorted(sessions_by_day[day])))
        perfect=replay_perfect_teacher_actions(teacher,universe,
            expected_sessions=tuple(sorted(sessions_by_day[day])))
        cents=int(round(exact.total_pnl_usd*100))
        if (cents!=teacher.exact_objective_cents
                or int(round(perfect.total_pnl_usd*100))!=cents
                or len(teacher.selected_opportunity_ids)>C.MAX_ENTRIES_PORTFOLIO_DAY
                or teacher.representation_sha256!=cached.representation_sha256):
            raise RecoveryRefusal("real exact/perfect teacher replay differs")
        expected_round=(2 if any(row[5]<=day<=row[6]
            for row in chronology.action_folds) else 0)
        if require_rollout_rounds and cached.rollout_rounds_completed!=expected_round:
            raise RecoveryRefusal("real teacher rollout count differs")
        objective+=cents;entries+=len(teacher.selected_opportunity_ids)
        replay_receipts.append(C.object_sha256({"day":day,
            "pnl_usd":exact.total_pnl_usd,
            "trades":tuple(asdict(row) for row in exact.trade_results)}))
        perfect_receipts.append(C.object_sha256({"day":day,
            "pnl_usd":perfect.total_pnl_usd,
            "trades":tuple(asdict(row) for row in perfect.trade_results)}))
    feature_paths=tuple(sorted(row.artifact_path for row in features
                               if row.status=="MATERIALIZED"
                               and row.artifact_path is not None))
    schema,feature_audit,_audit_path=load_or_audit_causal_feature_roster_paths(
        feature_paths)
    feature_sessions={row.session for row in features
                      if row.status=="MATERIALIZED"}
    if feature_sessions!=active_sessions:
        raise RecoveryRefusal("real feature/outcome session algebra differs")
    core={"schema":ENGINEERING_AUDIT_SCHEMA,"scope":str(scope),
        "active_sessions":len(active_sessions),"portfolio_days":len(teachers),
        "candidate_rows":sum(row.candidate_rows for row in outcomes),
        "learnable_rows":sum(row.learnable_rows for row in outcomes),
        "exact_objective_cents":objective,"selected_entries":entries,
        "side_by_asset":{key:tuple(sorted(value))
                         for key,value in side_by_asset.items()},
        "cost_applied_once":True,"canonical_cent_parity_every_day":True,
        "perfect_action_parity_every_day":True,"series_uniqueness":True,
        "closed_interval_k1":True,"portfolio_entry_cap":12,
        "one_mini":True,"conditional_day_denominator":False,
        "replay_receipts":tuple(replay_receipts),
        "perfect_receipts":tuple(perfect_receipts),
        "feature_schema_receipt_sha256":schema.receipt_sha256,
        "feature_audit_receipt_sha256":feature_audit["receipt_sha256"],
        "rollout_rounds_required":require_rollout_rounds,
        "h2_open_count":0}
    artifact={**core,"receipt_sha256":C.object_sha256(core)}
    target=Path(output_path);_strict_json(target,artifact)
    try:stored=json.loads(target.read_text())
    except (OSError,UnicodeError,json.JSONDecodeError) as exc:
        raise RecoveryRefusal("cannot strict-reload engineering audit") from exc
    if stored!=C.canonical_json_value(artifact):
        raise RecoveryRefusal("strict-reloaded engineering audit differs")
    return MappingProxyType(stored)


def _event_sidecar(path:Path)->Path:
    preferred=path.with_suffix(path.suffix+".json")
    return preferred if preferred.is_file() else path.with_suffix(".json")


def run_real_future_mutation_adversary(*,
        spec:AuthoritativeConfirmationSessionSpec,
        feature_schema:CausalFeatureSchema,
        component_roster:SeedModelRoster,action_roster:SeedModelRoster,
        output_root:str|Path,max_delay_sec:int=300)->Mapping[str,object]:
    """Mutate an actual future event and recompute causal features/actions."""

    spec.__post_init__();feature_schema.__post_init__()
    if spec.event_path is None or spec.trading_day>=C.HOLDOUT_START_D8:
        raise RecoveryRefusal("future mutation source is unavailable/sealed")
    if max_delay_sec not in (300,600):
        raise RecoveryRefusal("future mutation horizon is unregistered")
    original=materialize_runtime_dense_feature_session(
        spec,max_delay_sec=max_delay_sec)
    timestamps=np.asarray(original.snapshot_ts_ns,np.int64)
    with EventPack(spec.event_path,verify_hash=True) as pack:
        choices=np.flatnonzero((pack.cutoffs(timestamps)>0)
            &(pack.cutoffs(timestamps)<pack.header.n_events))
        if not len(choices):
            raise RecoveryRefusal("real future mutation has no interior prefix")
        chosen=int(choices[len(choices)//2]);decision=int(timestamps[chosen])
        event_index=pack.cutoff(decision)
        mutation_ts=int(pack.rows["ts_recv_ns"][event_index])
    source=Path(spec.event_path);sidecar=_event_sidecar(source)
    root=C.assert_workspace_output(output_root)
    root.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix="future-mutation-",dir=root))
    try:
        mutated_path=stage/source.name;mutated_sidecar=stage/(source.name+".json")
        shutil.copyfile(source,mutated_path)
        with mutated_path.open("r+b") as handle:
            handle.seek(HEADER_BYTES+event_index*ROW_BYTES+40)
            raw=handle.read(4)
            if len(raw)!=4:raise RecoveryRefusal("future mutation row is truncated")
            value=struct.unpack("<I",raw)[0]
            handle.seek(-4,os.SEEK_CUR);handle.write(struct.pack("<I",value^1))
            handle.flush();os.fsync(handle.fileno())
        new_hash=C.file_sha256(mutated_path)
        metadata=json.loads(sidecar.read_text())
        metadata["event_pack_sha256"]=new_hash
        if "output_sha256" in metadata:metadata["output_sha256"]=new_hash
        C.atomic_json(mutated_sidecar,metadata)
        mutated_spec=replace(spec,event_path=str(mutated_path),
                             expected_event_sha256=new_hash)
        mutated=materialize_runtime_dense_feature_session(
            mutated_spec,max_delay_sec=max_delay_sec)
        prefix=np.asarray(original.snapshot_ts_ns,np.int64)<=mutation_ts
        metadata_names=("opportunity_id","series_id","candidate_id","asset",
                        "day","side","phase","snapshot_ts_ns")
        if (not prefix.any() or original.feature_names!=mutated.feature_names
                or any(not np.array_equal(np.asarray(getattr(original,name))[prefix],
                                          np.asarray(getattr(mutated,name))[prefix])
                       for name in metadata_names)
                or not np.array_equal(np.asarray(original.features)[prefix],
                                      np.asarray(mutated.features)[prefix])):
            raise RecoveryRefusal("future event mutation changed a causal prefix")
        prepared=prepare_runtime_feature_shard(original,feature_schema)
        mutated_prepared=prepare_runtime_feature_shard(mutated,feature_schema)
        x=np.asarray(prepared.features,np.float32)[prefix]
        mx=np.asarray(mutated_prepared.features,np.float32)[prefix]
        component_fold=component_roster.bundle_for_day(spec.trading_day)
        action_fold=action_roster.bundle_for_day(spec.trading_day)
        component=load_component_model(component_fold.bundle_path)
        action=load_action_model(action_fold.bundle_path)
        cp=component.predict(x).values;mcp=component.predict(mx).values
        assets=np.asarray(original.asset,str)[prefix]
        phases=np.asarray(original.phase,str)[prefix]
        clocks=np.asarray(original.snapshot_ts_ns,np.int64)[prefix]
        args={"causal_feature_names":feature_schema.names,"asset":assets,
            "snapshot_ts_ns":clocks,"entries_used":np.zeros(len(x),np.int8),
            "open_until_ts_ns":np.full((len(x),len(C.ASSETS)),-1,np.int64),
            "active_watches_by_asset_side":np.zeros((len(x),6),np.int16),
            "phase":phases}
        names,ax=build_action_feature_matrix(causal_matrix=x,
            component_predictions=cp,**args)
        mnames,max_=build_action_feature_matrix(causal_matrix=mx,
            component_predictions=mcp,**args)
        regret=predict_action_regret(action,ax,trading_day=spec.trading_day)
        mregret=predict_action_regret(action,max_,trading_day=spec.trading_day)
        if (names!=mnames or not np.array_equal(cp,mcp)
                or not np.array_equal(ax,max_)
                or not np.array_equal(regret,mregret)):
            raise RecoveryRefusal("future event mutation changed model action")
        core={"schema":FUTURE_MUTATION_SCHEMA,"asset":spec.asset,
            "trading_day":spec.trading_day,"decision_ts_ns":decision,
            "mutated_event_index":event_index,"mutated_event_ts_ns":mutation_ts,
            "original_event_sha256":spec.expected_event_sha256,
            "mutated_event_sha256":new_hash,"prefix_rows":int(prefix.sum()),
            "feature_schema_receipt_sha256":feature_schema.receipt_sha256,
            "component_model_receipt_sha256":component.receipt_sha256,
            "action_model_receipt_sha256":action.receipt_sha256,
            "max_delay_sec":max_delay_sec,
            "causal_features_unchanged":True,"actions_unchanged":True,
            "h2_open_count":0}
        artifact={**core,"receipt_sha256":C.object_sha256(core)}
        _strict_json(root/"future_mutation.json",artifact)
        return MappingProxyType(artifact)
    finally:
        shutil.rmtree(stage,ignore_errors=True)


def publish_launch_rehearsal(*,e1r:FitOnlyExecutionResult,
        e2r:FitOnlyExecutionResult,engineering_audit:Mapping[str,object],
        future_mutation:Mapping[str,object],
        failure_branch_inventory:Mapping[str,object],
        config:RecoveryConfig,
        output_path:str|Path)->Mapping[str,object]:
    """Authorize the long pre-H2 campaign only after the complete rehearsal."""

    config.__post_init__()
    e1r=load_fit_only_execution(e1r.manifest_path,config=config)
    e2r=load_fit_only_execution(e2r.manifest_path,config=config)
    engineering_receipt=_verified_mapping(
        engineering_audit,ENGINEERING_AUDIT_SCHEMA)
    future_receipt=_verified_mapping(future_mutation,FUTURE_MUTATION_SCHEMA)
    inventory_receipt=_verified_mapping(
        failure_branch_inventory,"QRE2TABFAILUREINVENTORY1")
    if (e1r.name!="E1R" or e2r.name!="E2R"
            or e1r.status!="PASS" or e2r.status!="PASS"
            or e1r.curriculum.receipt_sha256==e2r.curriculum.receipt_sha256
            or e1r.chronology.receipt_sha256==e2r.chronology.receipt_sha256
            or engineering_audit.get("schema")!=ENGINEERING_AUDIT_SCHEMA
            or future_mutation.get("schema")!=FUTURE_MUTATION_SCHEMA
            or failure_branch_inventory.get(
                "all_registered_branches_accounted_for") is not True
            or failure_branch_inventory.get(
                "real_pre_h2_production_paths") is not True
            or any(value.get("h2_open_count")!=0 for value in (
                engineering_audit,future_mutation,
                failure_branch_inventory))):
        raise RecoveryRefusal("long-campaign rehearsal boundary did not pass")
    core={"schema":LAUNCH_REHEARSAL_SCHEMA,"status":"PASS",
        "campaign_permitted":True,"e1r_receipt_sha256":e1r.receipt_sha256,
        "e2r_receipt_sha256":e2r.receipt_sha256,
        "engineering_audit_receipt_sha256":engineering_receipt,
        "future_mutation_receipt_sha256":future_receipt,
        "failure_branch_inventory_receipt_sha256":
            inventory_receipt,
        "same_implementations_as_campaign":True,
        "independent_fit_only_executions":True,
        "strict_reload_and_resume":True,"unit_tests_as_evidence":False,
        "h2_open_count":0}
    artifact={**core,"receipt_sha256":C.object_sha256(core)}
    _strict_json(Path(output_path),artifact);return MappingProxyType(artifact)


def publish_production_rehearsal(*,launch_rehearsal:Mapping[str,object],
        development:DevelopmentEvaluationResult,
        curriculum:TwoRoundCurriculumResult,
        chronology:RecoveryChronology,config:RecoveryConfig,
        full_engineering_audit:Mapping[str,object],
        failure_resolution:Mapping[str,object],
        output_path:str|Path)->Mapping[str,object]:
    """Bind full-campaign economics to the already-passed launch rehearsal."""

    chronology.__post_init__();config.__post_init__();curriculum.__post_init__()
    development=load_development_evaluation(development.manifest_path,
        curriculum=curriculum.final_round,chronology=chronology,config=config)
    launch_core={key:value for key,value in launch_rehearsal.items()
                 if key!="receipt_sha256"}
    failure_core={key:value for key,value in failure_resolution.items()
                  if key!="receipt_sha256"}
    engineering_receipt=_verified_mapping(
        full_engineering_audit,ENGINEERING_AUDIT_SCHEMA)
    if (launch_rehearsal.get("schema")!=LAUNCH_REHEARSAL_SCHEMA
            or launch_rehearsal.get("status")!="PASS"
            or launch_rehearsal.get("campaign_permitted") is not True
            or C.object_sha256(launch_core)
               !=launch_rehearsal.get("receipt_sha256")
            or development.status!="PASS"
            or full_engineering_audit.get("schema")!=ENGINEERING_AUDIT_SCHEMA
            or failure_resolution.get("schema")
               !="QRE2TABFAILURERESOLUTION1"
            or failure_resolution.get("status")!="PASS"
            or failure_resolution.get("publication_permitted") is not True
            or failure_resolution.get("final_curriculum_receipt_sha256")
               !=curriculum.receipt_sha256
            or failure_resolution.get("final_development_receipt_sha256")
               !=development.receipt_sha256
            or C.object_sha256(failure_core)
               !=failure_resolution.get("receipt_sha256")
            or full_engineering_audit.get("h2_open_count")!=0):
        raise RecoveryRefusal("production rehearsal cannot authorize publication")
    core={"schema":PRODUCTION_REHEARSAL_SCHEMA,"status":"PASS",
        "publication_permitted":True,
        "launch_rehearsal_receipt_sha256":launch_rehearsal["receipt_sha256"],
        "development_receipt_sha256":development.receipt_sha256,
        "full_engineering_audit_receipt_sha256":
            engineering_receipt,
        "failure_resolution_receipt_sha256":failure_resolution["receipt_sha256"],
        "all_economic_gates_pass":True,"all_assets":True,
        "five_real_and_five_shuffle":True,"two_rollout_rounds":True,
        "strict_reload_and_restart":True,"h2_open_count":0}
    artifact={**core,"receipt_sha256":C.object_sha256(core)}
    _strict_json(Path(output_path),artifact);return MappingProxyType(artifact)


__all__=["ENGINEERING_AUDIT_SCHEMA","FUTURE_MUTATION_SCHEMA",
         "LAUNCH_REHEARSAL_SCHEMA","PRODUCTION_REHEARSAL_SCHEMA",
         "audit_real_teacher_chain","publish_launch_rehearsal",
         "publish_production_rehearsal","run_real_future_mutation_adversary"]
