#!/usr/bin/env python3
"""Restartable top-level runner for the Entry V2 recovery contract.

No full 908,346-candidate campaign is entered until the real E1R/E2R,
failure-branch inventory, future-mutation, engineering, and strict
reload gates have published a passing launch receipt.  2025H2 has no CLI path.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
from types import MappingProxyType
from typing import Mapping,Sequence

REPO_ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO_ROOT))

if __name__=="__mp_main__":
    # Spawn corpus workers re-import this script BEFORE the pool initializer
    # runs; native pools must be capped before numpy/catboost first load, or
    # each of the 16 workers boots with ~64-thread OpenMP/OpenBLAS pools.
    from engine.entry_v2.native_thread_cap import cap_native_thread_env
    cap_native_thread_env()
    os.environ["ENTRY_V2_PREDICT_THREADS"]="1"

import numpy as np

from engine.entry_v2 import common as C  # noqa:E402
from engine.entry_v2.confirmation_experiment import (  # noqa:E402
    AuthoritativeConfirmationSessionSpec,discover_authoritative_session_specs,
)
from engine.entry_v2.contracts import SessionRef  # noqa:E402
from engine.entry_v2.exact_delayed_teacher import publish_teacher_manifest  # noqa:E402
from engine.entry_v2.tabular_campaign import (  # noqa:E402
    CachedRecoverySession,CachedTeacherDay,discover_full_pre_h2,
    materialize_feature_corpus,materialize_outcome_corpus,
    materialize_teacher_corpus,publish_corpus_manifest,
)
from engine.entry_v2.tabular_delayed_corpus import (  # noqa:E402
    CausalFeatureShard,prepare_runtime_feature_shard,
)
from engine.entry_v2.tabular_evaluation import (  # noqa:E402
    DevelopmentEvaluationResult,run_development_evaluation,
)
from engine.entry_v2.tabular_failure_orchestration import (  # noqa:E402
    EXECUTABLE_BRANCHES,ExtensionAssessment,FailureBranchExecution,
    assess_five_minute_extension,choose_failure_branch,
    publish_failure_branch_inventory,publish_failure_resolution,
    run_failure_branch,
)
from engine.entry_v2.tabular_fallbacks import (  # noqa:E402
    FailureBranchDecision,
)
from engine.entry_v2.tabular_fit_only import (  # noqa:E402
    FitOnlyExecutionResult,run_fit_only_execution,
)
from engine.entry_v2.tabular_matrix_store import load_component_matrix  # noqa:E402
from engine.entry_v2.tabular_orchestration import (  # noqa:E402
    TwoRoundCurriculumResult,run_two_round_curriculum,
)
from engine.entry_v2.tabular_policy import CausalSnapshotInput  # noqa:E402
from engine.entry_v2.tabular_publication import publish_accepted_policy  # noqa:E402
from engine.entry_v2.tabular_recovery_contracts import (  # noqa:E402
    RecoveryChronology,RecoveryConfig,RecoveryRefusal,
)
from engine.entry_v2.tabular_rehearsal import (  # noqa:E402
    audit_real_teacher_chain,publish_launch_rehearsal,
    publish_production_rehearsal,run_real_future_mutation_adversary,
)


REHEARSAL_BOUNDS=(20210531,20210930)


def _strict_mapping(path:Path,schema:str)->Mapping[str,object]:
    C.guard_payload(path)
    try:value=json.loads(path.read_text())
    except (OSError,UnicodeError,json.JSONDecodeError) as exc:
        raise RecoveryRefusal(f"cannot strict-load runner artifact: {path}") from exc
    core={key:item for key,item in value.items() if key!="receipt_sha256"}
    if (value.get("schema")!=schema or value.get("h2_open_count")!=0
            or C.object_sha256(core)!=value.get("receipt_sha256")):
        raise RecoveryRefusal(f"runner artifact identity differs: {path}")
    return MappingProxyType(value)


def _sessions(specs:Sequence[AuthoritativeConfirmationSessionSpec]
              )->tuple[SessionRef,...]:
    rows=tuple(sorted(row.session for row in specs))
    if len(rows)!=len(set(rows)) or any(
            row.trading_day>=C.HOLDOUT_START_D8 for row in rows):
        raise RecoveryRefusal("runner source roster repeats/opens H2")
    return rows


def _materialize(specs:Sequence[AuthoritativeConfirmationSessionSpec],*,
        cache_root:Path,max_delay_sec:int=300)->tuple[
            tuple[CachedRecoverySession,...],tuple[CachedTeacherDay,...],
            tuple[CachedRecoverySession,...]]:
    sessions=_sessions(specs)
    outcomes=materialize_outcome_corpus(specs,cache_root,
        max_delay_sec=max_delay_sec,workers=16)
    teachers=materialize_teacher_corpus(outcomes,all_sessions=sessions,
        cache_root=cache_root,workers=16)
    features=materialize_feature_corpus(specs,outcomes,teachers,
        cache_root=cache_root,round_index=0,workers=16)
    return outcomes,teachers,features


def _subset(*,bounds:tuple[int,int],
        specs:Sequence[AuthoritativeConfirmationSessionSpec],
        outcomes:Sequence[CachedRecoverySession],
        teachers:Sequence[CachedTeacherDay],
        features:Sequence[CachedRecoverySession])->tuple[
            tuple[AuthoritativeConfirmationSessionSpec,...],
            tuple[CachedRecoverySession,...],tuple[CachedTeacherDay,...],
            tuple[CachedRecoverySession,...],tuple[SessionRef,...]]:
    lo,hi=bounds;inside=lambda day:lo<=int(day)<=hi
    spec_rows=tuple(row for row in specs if inside(row.trading_day))
    sessions=_sessions(spec_rows);session_set=set(sessions)
    outcome_rows=tuple(row for row in outcomes if row.session in session_set)
    teacher_rows=tuple(row for row in teachers if inside(row.trading_day))
    feature_rows=tuple(row for row in features if row.session in session_set)
    if ({row.session for row in outcome_rows}!=session_set
            or {row.session for row in feature_rows}!={row.session for row in
                outcome_rows if row.status=="MATERIALIZED"}):
        raise RecoveryRefusal("runner rehearsal subset algebra differs")
    return spec_rows,outcome_rows,teacher_rows,feature_rows,sessions


def _rehearsal_decision(branch:str,measurement_receipt:str
                        )->FailureBranchDecision:
    core={"schema":"QRE2TABFAILUREBRANCH1","branch":branch,
        "reason":"REAL_PRE_H2_BRANCH_EXECUTION_REHEARSAL",
        "measurements":measurement_receipt,"goal_lowered":False,
        "terminal_null_allowed":False}
    result=FailureBranchDecision(branch,str(core["reason"]),
        measurement_receipt,False,False,C.object_sha256(core))
    result.__post_init__();return result


def _fit_kwargs(execution:FailureBranchExecution)->Mapping[str,object]:
    branch=execution.branch
    if branch=="PAIRWISE_ACTION":return {"action_objective":"PairLogitPairwise"}
    if branch=="HISTOGRAM_LEARNERS":return {
        "learner_backend":execution.curriculum.learner_backend,
        "action_backend":execution.curriculum.action_backend}
    if branch=="CAUSAL_RELATION_ENCODING":return {
        "relation_source_features":execution.curriculum.relation_source_features}
    if branch=="REGRET_WEIGHTED_IMITATION":return {
        "action_objective":"MultiClass"}
    if branch=="STATE_CONDITIONED_CALIBRATION":return {
        "state_conditioned_calibration":True}
    if branch=="CAUSAL_TRAILING_EXPERTS":return {
        "action_backend":"CAUSAL_EXPERTS"}
    if branch=="EXTEND_TO_600":return {}
    raise RecoveryRefusal("fit-only failure branch is unregistered")


def _economic_summary(development:DevelopmentEvaluationResult
                      )->Mapping[str,object]:
    rows={}
    for block,values in development.raw_blocks.items():
        rows[f"RAW_{block}"]={key:{
            "usd_per_active_day":value.gate.usd_per_active_portfolio_day,
            "ceiling_capture":value.gate.ceiling_capture,
            "usd_per_trade":value.gate.usd_per_trade,
            "max_drawdown_usd":value.gate.max_drawdown_usd,
            "trades":value.gate.trades,"floor_pass":value.gate.floor_pass}
            for key,value in values.items()}
    rows["FORWARD"]={key:{
        "usd_per_active_day":value.gate.usd_per_active_portfolio_day,
        "ceiling_capture":value.gate.ceiling_capture,
        "usd_per_trade":value.gate.usd_per_trade,
        "max_drawdown_usd":value.gate.max_drawdown_usd,
        "trades":value.gate.trades,"floor_pass":value.gate.floor_pass}
        for key,value in development.forward_blocks.items()}
    return MappingProxyType({"status":development.status,"blocks":rows})


def _future_spec(*,specs:Sequence[AuthoritativeConfirmationSessionSpec],
        outcomes:Sequence[CachedRecoverySession],curriculum:TwoRoundCurriculumResult
        )->AuthoritativeConfirmationSessionSpec:
    active={row.session for row in outcomes if row.status=="MATERIALIZED"}
    action=curriculum.final_round.action_rosters["real"][0]
    for spec in sorted(specs,key=lambda row:row.session):
        if spec.session not in active or spec.event_path is None:continue
        try:action.bundle_for_day(spec.trading_day)
        except RecoveryRefusal:continue
        return spec
    raise RecoveryRefusal("no real action-scored future-mutation session exists")


def _restart_snapshot(curriculum:TwoRoundCurriculumResult)->CausalSnapshotInput:
    final=curriculum.final_round;maximum=int(load_component_matrix(
        final.component_matrix_path).day.max())
    candidates=[]
    for path in final.feature_paths:
        shard=CausalFeatureShard.load(path)
        if int(np.asarray(shard.day,np.int64)[0])==maximum:
            candidates.append(prepare_runtime_feature_shard(
                shard,final.feature_schema))
    if not candidates:raise RecoveryRefusal("publication restart day is absent")
    shard=sorted(candidates,key=lambda row:str(row.asset[0]))[0]
    index=len(shard.features)-1;series=str(shard.series_id[index])
    local=np.asarray(shard.series_id,str)==series
    expiry=int(np.max(np.asarray(shard.snapshot_ts_ns,np.int64)[local]))
    return CausalSnapshotInput(str(shard.candidate_id[index]),series,
        str(shard.asset[index]),int(shard.day[index]),int(shard.side[index]),
        int(shard.snapshot_ts_ns[index]),expiry,final.feature_schema.names,
        tuple(map(float,np.asarray(shard.features,np.float32)[index])),0,(),
        (0,0,0,0,0,0),str(shard.phase[index]))


def run_rehearsal(*,source_root:Path,run_root:Path)->Mapping[str,object]:
    config=RecoveryConfig();specs=discover_authoritative_session_specs(
        source_root,REHEARSAL_BOUNDS);sessions=_sessions(specs)
    cache=run_root/"cache";outcomes,teachers,features=_materialize(
        specs,cache_root=cache,max_delay_sec=300)
    e1r=run_fit_only_execution(name="E1R",specs=specs,outcomes=outcomes,
        initial_teachers=teachers,initial_features=features,
        all_sessions=sessions,config=config,cache_root=cache/"fit_only",
        output_root=run_root/"fit_only",workers=16)
    e2r=run_fit_only_execution(name="E2R",specs=specs,outcomes=outcomes,
        initial_teachers=teachers,initial_features=features,
        all_sessions=sessions,config=config,cache_root=cache/"fit_only",
        output_root=run_root/"fit_only",workers=16)

    e1_bounds=(e1r.chronology.burned[0],e1r.chronology.forward[1])
    (e1_specs,e1_outcomes,e1_teachers,e1_features,
     e1_sessions)=_subset(bounds=e1_bounds,specs=specs,outcomes=outcomes,
        teachers=teachers,features=features)
    extension=assess_five_minute_extension(specs=e1_specs,
        outcomes_300=e1_outcomes,teachers_300=e1_teachers,
        all_sessions=e1_sessions,cache_root=cache/"extension_e1r",
        output_path=run_root/"extension_e1r.json",workers=16)
    base_development=run_development_evaluation(
        curriculum=e1r.curriculum.final_round,outcomes=e1_outcomes,
        teachers=e1r.curriculum.final_teachers,specs=e1_specs,
        chronology=e1r.chronology,config=config,
        output_root=run_root/"e1r_development")
    selected,measurement=choose_failure_branch(
        curriculum=e1r.curriculum.final_round,
        development=base_development,teachers=e1r.curriculum.final_teachers,
        chronology=e1r.chronology,config=config,extension=extension)

    def _branch_execution(branch:str)->FailureBranchExecution:
        decision=(selected if selected.branch==branch else
            _rehearsal_decision(branch,selected.measurements_receipt_sha256))
        return run_failure_branch(decision=decision,
            base_curriculum=e1r.curriculum,specs=e1_specs,
            outcomes=e1_outcomes,initial_teachers=e1_teachers,
            initial_features=e1_features,all_sessions=e1_sessions,
            chronology=e1r.chronology,config=config,extension=extension,
            cache_root=cache/"branch_rehearsal",
            output_root=run_root/"branch_rehearsal")

    # Only the SELECTED branch gates the verdict.  The other executions are
    # launch-inventory evidence: byte-identical whenever they run, consumed
    # only by the PASS path below, so they execute after the verdict instead
    # of burning days of compute in front of a possible CONTINUE_REQUIRED.
    executions={};selected_execution=None
    if selected.branch!="PRIMARY_PASS":
        selected_execution=_branch_execution(selected.branch)
        executions[selected.branch]=selected_execution.manifest_path

    final_e1r,final_e2r=e1r,e2r
    horizon=300
    audit_outcomes=e1_outcomes
    if selected.branch!="PRIMARY_PASS":
        assert selected_execution is not None
        kwargs=dict(_fit_kwargs(selected_execution));fit_outcomes=outcomes
        fit_teachers=teachers;fit_features=features
        if selected.branch=="EXTEND_TO_600":
            union_extension=assess_five_minute_extension(specs=specs,
                outcomes_300=outcomes,teachers_300=teachers,
                all_sessions=sessions,cache_root=cache/"extension_union",
                output_path=run_root/"extension_union.json",workers=16)
            if not union_extension.trigger["extend_to_600"]:
                raise RecoveryRefusal("E1 extension did not transfer to rehearsal union")
            fit_outcomes=union_extension.outcomes_600
            fit_teachers=union_extension.teachers_600
            fit_features=materialize_feature_corpus(specs,fit_outcomes,
                fit_teachers,cache_root=cache/"extension_union_features",
                round_index=0,workers=16);horizon=600
        final_e1r=run_fit_only_execution(name="E1R",specs=specs,
            outcomes=fit_outcomes,initial_teachers=fit_teachers,
            initial_features=fit_features,all_sessions=sessions,config=config,
            cache_root=cache/"selected_fit_only"/selected.branch.lower(),
            output_root=run_root/"selected_fit_only"/selected.branch.lower(),
            workers=16,**kwargs)
        final_e2r=run_fit_only_execution(name="E2R",specs=specs,
            outcomes=fit_outcomes,initial_teachers=fit_teachers,
            initial_features=fit_features,all_sessions=sessions,config=config,
            cache_root=cache/"selected_fit_only"/selected.branch.lower(),
            output_root=run_root/"selected_fit_only"/selected.branch.lower(),
            workers=16,**kwargs)
        (_s,audit_outcomes,_t,_f,_ss)=_subset(bounds=(
            final_e1r.chronology.burned[0],final_e1r.chronology.forward[1]),
            specs=specs,outcomes=fit_outcomes,teachers=fit_teachers,
            features=fit_features)
    if final_e1r.status!="PASS" or final_e2r.status!="PASS":
        core={"schema":"QRE2TABREHEARSALATTEMPT1",
            "status":"CONTINUE_REQUIRED","selected_branch":selected.branch,
            "e1r_receipt_sha256":final_e1r.receipt_sha256,
            "e2r_receipt_sha256":final_e2r.receipt_sha256,
            "economic_goal_lowered":False,"terminal_null":False,
            "h2_open_count":0}
        artifact={**core,"receipt_sha256":C.object_sha256(core)}
        C.atomic_json(run_root/"rehearsal_attempt.json",artifact)
        return MappingProxyType(artifact)

    for branch in EXECUTABLE_BRANCHES:
        if branch in executions:continue
        if branch=="EXTEND_TO_600" and not extension.trigger["extend_to_600"]:
            continue
        executions[branch]=_branch_execution(branch).manifest_path
    inventory=publish_failure_branch_inventory(execution_paths=executions,
        extension=extension,chronology=e1r.chronology,config=config,
        output_path=run_root/"failure_branch_inventory.json")

    final_e1_bounds=(final_e1r.chronology.burned[0],
                     final_e1r.chronology.forward[1])
    final_specs=tuple(row for row in specs
                      if final_e1_bounds[0]<=row.trading_day<=final_e1_bounds[1])
    engineering=audit_real_teacher_chain(outcomes=audit_outcomes,
        teachers=final_e1r.curriculum.final_teachers,
        features=final_e1r.curriculum.final_features,
        all_sessions=_sessions(final_specs),chronology=final_e1r.chronology,
        scope="E1R_REAL_PRODUCTION_PATH",require_rollout_rounds=True,
        output_path=run_root/"engineering_audit.json")
    component=final_e1r.curriculum.final_round.component_rosters["real"][0]
    action=final_e1r.curriculum.final_round.action_rosters["real"][0]
    future_spec=_future_spec(specs=final_specs,outcomes=audit_outcomes,
        curriculum=final_e1r.curriculum)
    mutation=run_real_future_mutation_adversary(spec=future_spec,
        feature_schema=final_e1r.curriculum.final_round.feature_schema,
        component_roster=component,action_roster=action,
        output_root=run_root/"future_mutation",max_delay_sec=horizon)
    launch=publish_launch_rehearsal(e1r=final_e1r,e2r=final_e2r,
        engineering_audit=engineering,future_mutation=mutation,
        failure_branch_inventory=inventory,
        config=config,output_path=run_root/"launch_rehearsal.json")
    return MappingProxyType({"schema":"QRE2TABREHEARSALRUN1",
        "status":"PASS","launch_rehearsal":dict(launch),
        "selected_branch":selected.branch,
        "measurement_receipt_sha256":measurement["receipt_sha256"],
        "e1r_receipt_sha256":final_e1r.receipt_sha256,
        "e2r_receipt_sha256":final_e2r.receipt_sha256,
        "h2_open_count":0})


def run_campaign(*,source_root:Path,run_root:Path,
        rehearsal_root:Path)->Mapping[str,object]:
    config=RecoveryConfig();chronology=RecoveryChronology()
    launch=_strict_mapping(rehearsal_root/"launch_rehearsal.json",
                           "QRE2TABLAUNCHREHEARSAL1")
    if launch.get("campaign_permitted") is not True:
        raise RecoveryRefusal("full campaign lacks passing launch rehearsal")
    specs=discover_full_pre_h2(source_root);sessions=_sessions(specs)
    cache=run_root/"cache";outcomes,teachers,features=_materialize(
        specs,cache_root=cache,max_delay_sec=300)
    primary=run_two_round_curriculum(specs=specs,outcomes=outcomes,
        initial_teachers=teachers,initial_features=features,
        all_sessions=sessions,chronology=chronology,config=config,
        cache_root=cache/"primary",output_root=run_root/"primary",
        workers=16)
    development=run_development_evaluation(curriculum=primary.final_round,
        outcomes=outcomes,teachers=primary.final_teachers,specs=specs,
        chronology=chronology,config=config,
        output_root=run_root/"primary_evaluation")
    extension=assess_five_minute_extension(specs=specs,
        outcomes_300=outcomes,teachers_300=teachers,all_sessions=sessions,
        cache_root=cache/"extension",
        output_path=run_root/"extension_assessment.json",workers=16)
    decision,measurement=choose_failure_branch(curriculum=primary.final_round,
        development=development,teachers=primary.final_teachers,
        chronology=chronology,config=config,extension=extension)
    execution=None
    if decision.branch!="PRIMARY_PASS":
        execution=run_failure_branch(decision=decision,
            base_curriculum=primary,specs=specs,outcomes=outcomes,
            initial_teachers=teachers,initial_features=features,
            all_sessions=sessions,chronology=chronology,config=config,
            extension=extension,cache_root=cache/"failure",
            output_root=run_root/"failure")
    resolution=publish_failure_resolution(decision=decision,
        measurement_detail=measurement,base_curriculum=primary,
        base_development=development,execution=execution,
        output_path=run_root/"failure_resolution.json")
    final_curriculum=primary if execution is None else execution.curriculum
    final_development=development if execution is None else execution.development
    if resolution["status"]!="PASS":
        summary={"schema":"QRE2TABCAMPAIGNATTEMPT1",
            "status":"CONTINUE_REQUIRED","decision":asdict(decision),
            "failure_resolution_receipt_sha256":resolution["receipt_sha256"],
            "economics":dict(_economic_summary(final_development)),
            "economic_goal_lowered":False,"terminal_null":False,
            "h2_open_count":0}
        artifact={**summary,"receipt_sha256":C.object_sha256(summary)}
        C.atomic_json(run_root/"campaign_attempt.json",artifact)
        return MappingProxyType(artifact)

    final_outcomes=(extension.outcomes_600
                    if decision.branch=="EXTEND_TO_600" else outcomes)
    full_audit=audit_real_teacher_chain(outcomes=final_outcomes,
        teachers=final_curriculum.final_teachers,
        features=final_curriculum.final_features,all_sessions=sessions,
        chronology=chronology,scope="ALL_PRE_H2_PRODUCTION_PATH",
        require_rollout_rounds=True,
        output_path=run_root/"full_engineering_audit.json")
    corpus=publish_corpus_manifest(run_root/"corpus_manifest.json",specs=specs,
        outcomes=final_outcomes,teachers=final_curriculum.final_teachers,
        features=final_curriculum.final_features,chronology=chronology,
        rollout_rounds_completed=2)
    teacher_manifest=publish_teacher_manifest(run_root/"teacher_manifest.json",
        day_files={row.trading_day:{"artifact_path":row.artifact_path,
            "representation_sha256":row.representation_sha256,
            "exact_objective_cents":row.exact_objective_cents,
            "receipt_sha256":row.receipt_sha256}
            for row in final_curriculum.final_teachers},
        chronology_sha256=chronology.receipt_sha256,
        corpus_manifest_sha256=corpus["receipt_sha256"],
        canonical_replay_sha256=full_audit["receipt_sha256"],
        rollout_rounds_completed=2)
    production=publish_production_rehearsal(launch_rehearsal=launch,
        development=final_development,curriculum=final_curriculum,
        chronology=chronology,config=config,full_engineering_audit=full_audit,
        failure_resolution=resolution,
        output_path=run_root/"production_rehearsal.json")
    last_day=int(load_component_matrix(
        final_curriculum.final_round.component_matrix_path).day.max())
    publication=publish_accepted_policy(curriculum=final_curriculum.final_round,
        development=final_development,promotion_rehearsal=production,
        chronology=chronology,config=config,
        teacher_manifest_sha256=teacher_manifest["receipt_sha256"],
        restart_snapshot=_restart_snapshot(final_curriculum),
        expected_last_training_day=last_day,
        output_root=run_root/"publication_refit",
        policy_path=run_root/"tabular_policy_bundle")
    core={"schema":"QRE2TABCAMPAIGNRUN1","status":"PASS",
        "decision":asdict(decision),"economics":dict(
            _economic_summary(final_development)),
        "production_rehearsal_receipt_sha256":production["receipt_sha256"],
        "publication_receipt_sha256":publication["receipt_sha256"],
        "policy_bundle_receipt_sha256":publication[
            "policy_bundle_receipt_sha256"],"h2_open_count":0}
    artifact={**core,"receipt_sha256":C.object_sha256(core)}
    C.atomic_json(run_root/"campaign_complete.json",artifact)
    return MappingProxyType(artifact)


def status(*,rehearsal_root:Path,campaign_root:Path)->Mapping[str,object]:
    checks=((rehearsal_root/"launch_rehearsal.json",
             "QRE2TABLAUNCHREHEARSAL1"),
            (campaign_root/"failure_resolution.json",
             "QRE2TABFAILURERESOLUTION1"),
            (campaign_root/"production_rehearsal.json",
             "QRE2TABPRODUCTIONREHEARSAL1"),
            (campaign_root/"campaign_complete.json","QRE2TABCAMPAIGNRUN1"))
    output={}
    for path,schema in checks:
        if not path.is_file():output[path.name]={"present":False};continue
        try:value=_strict_mapping(path,schema);output[path.name]={
            "present":True,"status":value.get("status"),
            "receipt_sha256":value.get("receipt_sha256")}
        except RecoveryRefusal as exc:output[path.name]={
            "present":True,"status":"INVALID","reason":str(exc)}
    return MappingProxyType({"schema":"QRE2TABRUNNERSTATUS1","artifacts":output,
                             "h2_open_count":0})


def arguments()->argparse.Namespace:
    parser=argparse.ArgumentParser()
    parser.add_argument("--phase",choices=("status","rehearsal",
        "campaign","all"),default="status")
    parser.add_argument("--source-root",type=Path,
        default=REPO_ROOT/"artifacts/cache/port/entry_v2")
    parser.add_argument("--rehearsal-root",type=Path,
        default=REPO_ROOT/"artifacts/entry_v2/tabular_recovery/rehearsal")
    parser.add_argument("--campaign-root",type=Path,
        default=REPO_ROOT/"artifacts/entry_v2/tabular_recovery/campaign")
    return parser.parse_args()


def _adopt_legacy_dense_store(store:Path,legacy_roots:Sequence[Path])->int:
    """Hardlink historical per-cache dense sessions into the shared store.

    Identity directories are content-addressed (source+config+implementation),
    so the same identity under two roots is the same bytes; the manifest's
    embedded artifact_path keeps pointing at the original file, which stays
    in place.  Idempotent; returns how many sessions were adopted.
    """

    adopted=0
    for root in legacy_roots:
        if not root.is_dir() or root.resolve()==store.resolve():continue
        for manifest in root.glob("*/*/*.json"):
            relative=manifest.relative_to(root)
            target=store/relative
            if target.is_file():continue
            target.parent.mkdir(parents=True,exist_ok=True)
            for source in (manifest,manifest.with_suffix(".npz")):
                destination=store/source.relative_to(root)
                if destination.is_file():continue
                try:os.link(source,destination)
                except OSError:
                    import shutil;shutil.copy2(source,destination)
            adopted+=1
    return adopted


def main()->int:
    args=arguments()
    store=Path(args.rehearsal_root).parent/"dense_store"
    store.mkdir(parents=True,exist_ok=True)
    os.environ.setdefault("ENTRY_V2_DENSE_STORE",str(store))
    adopted=_adopt_legacy_dense_store(
        Path(os.environ["ENTRY_V2_DENSE_STORE"]),
        (Path(args.rehearsal_root)/"cache/fit_only/e1r/rollout/dense_replay_features",
         Path(args.rehearsal_root)/"cache/fit_only/e2r/rollout/dense_replay_features",
         Path(args.campaign_root)/"cache/primary/rollout/dense_replay_features"))
    print(f"DENSE_STORE {os.environ['ENTRY_V2_DENSE_STORE']} adopted={adopted}",
          flush=True)
    if args.phase=="status":result=status(rehearsal_root=args.rehearsal_root,
                                           campaign_root=args.campaign_root)
    elif args.phase=="rehearsal":result=run_rehearsal(
        source_root=args.source_root,run_root=args.rehearsal_root)
    elif args.phase=="campaign":result=run_campaign(source_root=args.source_root,
        run_root=args.campaign_root,rehearsal_root=args.rehearsal_root)
    else:
        rehearsal=run_rehearsal(source_root=args.source_root,
            run_root=args.rehearsal_root)
        if rehearsal.get("status")!="PASS":result=rehearsal
        else:result=run_campaign(source_root=args.source_root,
            run_root=args.campaign_root,rehearsal_root=args.rehearsal_root)
    print(json.dumps(C.canonical_json_value(result),sort_keys=True))
    status=str(result.get("status","PASS"))
    return 0 if status in {"PASS","RETIRED"} else 2


if __name__=="__main__":raise SystemExit(main())
