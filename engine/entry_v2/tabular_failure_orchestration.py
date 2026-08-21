"""Measured execution of the pre-registered Entry V2 tabular failure ladder.

This module never converts a failed economic boundary into success.  It binds
each branch to the same exact teachers, chronology, five real seeds, five
matched controls, two rollout rounds, every-second policy, and canonical
replay used by the primary learner.  A branch that still fails returns
``CONTINUE_REQUIRED`` and cannot authorize publication.
"""

from __future__ import annotations

from dataclasses import asdict,dataclass
import json
from pathlib import Path
from types import MappingProxyType
from typing import Final,Mapping,Sequence

import numpy as np
from scipy.stats import spearmanr

from . import common as C
from .confirmation_experiment import AuthoritativeConfirmationSessionSpec
from .contracts import SessionRef
from .exact_delayed_teacher import ExactDelayedTeacherDay
from .tabular_campaign import (
    CachedRecoverySession,CachedTeacherDay,materialize_feature_corpus,
    materialize_outcome_corpus,materialize_teacher_corpus,
)
from .tabular_delayed_corpus import (
    DelayedOutcomeShard,five_minute_extension_trigger,
)
from .tabular_evaluation import (
    DevelopmentEvaluationResult,evaluate_training_teacher_capture,
    load_development_evaluation,run_development_evaluation,
)
from .tabular_experiment import ComponentPredictionTable
from .tabular_fallbacks import (
    FAILURE_BRANCHES,FailureBranchDecision,FailureMeasurements,
    effect_reversal_trigger,identify_unstable_absolute_features,
    select_failure_branch,
)
from .tabular_matrix_store import load_component_matrix
from .tabular_orchestration import (
    TwoRoundCurriculumResult,load_two_round_curriculum,
    run_two_round_curriculum,
)
from .tabular_recovery_contracts import (
    RecoveryChronology,RecoveryConfig,RecoveryRefusal,
)


EXTENSION_SCHEMA:Final="QRE2TABEXTENSIONASSESSMENT1"
BRANCH_EXECUTION_SCHEMA:Final="QRE2TABBRANCHEXECUTION1"
FAILURE_RESOLUTION_SCHEMA:Final="QRE2TABFAILURERESOLUTION1"
FAILURE_INVENTORY_SCHEMA:Final="QRE2TABFAILUREINVENTORY1"

EXECUTABLE_BRANCHES:Final=tuple(
    branch for branch in FAILURE_BRANCHES if branch!="PRIMARY_PASS")


def _sha(value:object)->bool:
    return (isinstance(value,str) and len(value)==64
            and all(char in "0123456789abcdef" for char in value))


def _strict_json(path:Path,value:Mapping[str,object])->str:
    target=C.assert_workspace_output(path);raw=C.canonical_bytes(value)
    if target.is_file():
        if target.read_bytes()!=raw:
            raise RecoveryRefusal("resumed failure-ladder artifact differs")
        return C.file_sha256(target)
    return C.atomic_json(target,value)


def _strict_payload(path:str|Path,schema:str)->tuple[Path,Mapping[str,object]]:
    source=Path(path);C.guard_payload(source)
    try:value=json.loads(source.read_text())
    except (OSError,UnicodeError,json.JSONDecodeError) as exc:
        raise RecoveryRefusal("cannot strict-load failure-ladder artifact") from exc
    core={key:item for key,item in value.items() if key!="receipt_sha256"}
    if (value.get("schema")!=schema or value.get("h2_open_count")!=0
            or C.object_sha256(core)!=value.get("receipt_sha256")):
        raise RecoveryRefusal("failure-ladder artifact identity differs")
    return source,MappingProxyType(value)


def _cached_session(value:Mapping[str,object])->CachedRecoverySession:
    row=dict(value);row["session"]=SessionRef(**row["session"])
    result=CachedRecoverySession(**row);result.__post_init__();return result


@dataclass(frozen=True,slots=True)
class ExtensionAssessment:
    trigger:Mapping[str,object]
    outcomes_600:tuple[CachedRecoverySession,...]
    teachers_600:tuple[CachedTeacherDay,...]
    manifest_path:str
    receipt_sha256:str

    def __post_init__(self)->None:
        trigger_core={key:item for key,item in self.trigger.items()
                      if key!="receipt_sha256"}
        if (self.trigger.get("schema")!="QRE2TAB600TRIGGER1"
                or C.object_sha256(trigger_core)
                   !=self.trigger.get("receipt_sha256")
                or not self.outcomes_600 or not self.teachers_600
                or any(row.session.trading_day>=C.HOLDOUT_START_D8
                       for row in self.outcomes_600)
                or any(row.trading_day>=C.HOLDOUT_START_D8
                       for row in self.teachers_600)
                or not _sha(self.receipt_sha256)):
            raise RecoveryRefusal("extension assessment is malformed")


def assess_five_minute_extension(*,
        specs:Sequence[AuthoritativeConfirmationSessionSpec],
        outcomes_300:Sequence[CachedRecoverySession],
        teachers_300:Sequence[CachedTeacherDay],
        all_sessions:Sequence[SessionRef],cache_root:str|Path,
        output_path:str|Path,workers:int=16)->ExtensionAssessment:
    """Measure the exact 300-vs-600 second candidate ceiling once."""

    config=RecoveryConfig();config.__post_init__()
    if workers!=config.workers:
        raise RecoveryRefusal("extension assessment worker count differs")
    if any(row.session.trading_day>=C.HOLDOUT_START_D8
           for row in outcomes_300):
        raise RecoveryRefusal("extension assessment attempted to open H2")
    outcomes_600=materialize_outcome_corpus(specs,cache_root,
        max_delay_sec=config.dormant_max_delay_sec,workers=workers)
    teachers_600=materialize_teacher_corpus(outcomes_600,
        all_sessions=all_sessions,cache_root=cache_root,workers=workers)
    by_300={row.trading_day:row for row in teachers_300}
    by_600={row.trading_day:row for row in teachers_600}
    if (set(by_300)!=set(by_600)
            or sum(row.candidate_rows for row in outcomes_300)
               !=sum(row.candidate_rows for row in outcomes_600)
            or any(by_600[day].exact_objective_cents
                   <by_300[day].exact_objective_cents for day in by_300)):
        raise RecoveryRefusal("extension exact-ceiling day roster differs")
    receipt_300=C.object_sha256({"schema":"QRE2TAB300CEILINGROSTER1",
        "teachers":tuple(row.receipt_sha256 for row in teachers_300)})
    receipt_600=C.object_sha256({"schema":"QRE2TAB600CEILINGROSTER1",
        "teachers":tuple(row.receipt_sha256 for row in teachers_600)})
    trigger=five_minute_extension_trigger(
        ceiling_300_usd=sum(row.exact_objective_cents
                            for row in teachers_300)/100.0,
        ceiling_600_usd=sum(row.exact_objective_cents
                            for row in teachers_600)/100.0,
        receipt_300_sha256=receipt_300,receipt_600_sha256=receipt_600)
    core={"schema":EXTENSION_SCHEMA,"trigger":dict(trigger),
        "outcomes_600":tuple(asdict(row) for row in outcomes_600),
        "teachers_600":tuple(asdict(row) for row in teachers_600),
        "candidate_count_equal":True,"per_day_ceiling_monotone":True,
        "features_600_materialized":False,"workers":16,"h2_open_count":0}
    artifact={**core,"receipt_sha256":C.object_sha256(core)}
    target=Path(output_path);_strict_json(target,artifact)
    result=ExtensionAssessment(trigger,tuple(outcomes_600),
        tuple(teachers_600),str(target),str(artifact["receipt_sha256"]))
    result.__post_init__();return result


def load_extension_assessment(path:str|Path)->ExtensionAssessment:
    source,value=_strict_payload(path,EXTENSION_SCHEMA)
    outcomes=tuple(_cached_session(row) for row in value["outcomes_600"])
    teachers=tuple(CachedTeacherDay(**row) for row in value["teachers_600"])
    for row in outcomes:
        if row.status=="MATERIALIZED":
            shard=DelayedOutcomeShard.load(row.artifact_path)
            if shard.representation_sha256!=row.representation_sha256:
                raise RecoveryRefusal("extension outcome artifact differs")
    for row in teachers:
        teacher=ExactDelayedTeacherDay.load(row.artifact_path)
        if teacher.representation_sha256!=row.representation_sha256:
            raise RecoveryRefusal("extension teacher artifact differs")
    result=ExtensionAssessment(MappingProxyType(dict(value["trigger"])),
        outcomes,teachers,str(source),str(value["receipt_sha256"]))
    result.__post_init__();return result


def _teacher_current_targets(
        teachers:Sequence[CachedTeacherDay])->Mapping[tuple[int,str],float]:
    output={}
    for cached in teachers:
        teacher=ExactDelayedTeacherDay.load(cached.artifact_path)
        for opportunity,target in zip(
                np.asarray(teacher.component_opportunity_id,str),
                np.asarray(teacher.current_entry_usd,np.float64)):
            key=(teacher.trading_day,str(opportunity))
            if key in output:
                raise RecoveryRefusal("component target identity repeats")
            output[key]=float(target)
    return MappingProxyType(output)


def _value_ordering_measurement(*,curriculum:object,
        development:DevelopmentEvaluationResult,
        teachers:Sequence[CachedTeacherDay],chronology:RecoveryChronology
        )->Mapping[str,object]:
    targets=_teacher_current_targets(teachers);detail={}
    for block,lo,hi in chronology.oof_blocks:
        block_rows={}
        for lane in ("real","shuffle"):
            for seed in RecoveryConfig().real_seeds:
                key=f"{lane}:{seed}"
                table=ComponentPredictionTable.load(
                    curriculum.component_oof_paths[key])
                local=(np.asarray(table.day,np.int64)>=lo)&(
                    np.asarray(table.day,np.int64)<=hi)
                positions=np.flatnonzero(local);predicted=[];exact=[]
                for index in positions:
                    target_key=(int(table.day[index]),
                                str(table.opportunity_id[index]))
                    if target_key in targets:
                        predicted.append(float(table.values[index,1]))
                        exact.append(targets[target_key])
                if len(predicted)<3:
                    raise RecoveryRefusal("value-ordering OOF join is too small")
                correlation=float(spearmanr(predicted,exact).statistic)
                if not np.isfinite(correlation):correlation=0.0
                block_rows[key]={"rows":len(predicted),
                                 "spearman_current_q50":correlation}
        weakest=min(block_rows[f"real:{seed}"]["spearman_current_q50"]
                    for seed in RecoveryConfig().real_seeds)
        strongest=max(block_rows[f"shuffle:{seed}"]["spearman_current_q50"]
                      for seed in RecoveryConfig().real_seeds)
        detail[block]={"rows":block_rows,"weakest_real":weakest,
            "strongest_shuffle":strongest,
            "passed":weakest>0 and weakest>strongest}
    passed=all(bool(row["passed"]) for row in detail.values())
    core={"schema":"QRE2TABVALUEORDERING1","blocks":detail,
        "metric":"SPEARMAN_CURRENT_Q50_VS_EXACT_CURRENT_ENTRY",
        "weakest_real_above_strongest_shuffle":True,"passed":passed,
        "curriculum":curriculum.receipt_sha256,
        "development":development.receipt_sha256,"h2_open_count":0}
    return MappingProxyType({**core,"receipt_sha256":C.object_sha256(core)})


def _effect_reversal_measurement(development:DevelopmentEvaluationResult,
        chronology:RecoveryChronology)->Mapping[str,object]:
    effects=[];eras=[]
    for block,_lo,_hi in chronology.oof_blocks:
        rows=development.raw_blocks[block]
        real=[rows[f"real:{seed}"].evidence.daily_pnl
              for seed in RecoveryConfig().real_seeds]
        shuffle=[rows[f"shuffle:{seed}"].evidence.daily_pnl
                 for seed in RecoveryConfig().real_seeds]
        days=tuple(sorted(set.intersection(*(set(row) for row in (*real,*shuffle)))))
        if len(days)<2:
            raise RecoveryRefusal("effect reversal lacks two day clusters per era")
        values=np.asarray([
            np.mean([row[day] for row in real])
            -np.mean([row[day] for row in shuffle]) for day in days],np.float64)
        effects.append(values);eras.append((block,days))
    measured=effect_reversal_trigger(effects)
    core={"schema":"QRE2TABERAEFFECT1","eras":tuple(eras),
        "effect_trigger":dict(measured),"development":development.receipt_sha256,
        "h2_open_count":0}
    return MappingProxyType({**core,"receipt_sha256":C.object_sha256(core)})


def derive_failure_measurements(*,curriculum:object,
        development:DevelopmentEvaluationResult,
        teachers:Sequence[CachedTeacherDay],chronology:RecoveryChronology,
        extension:ExtensionAssessment)->tuple[FailureMeasurements,Mapping[str,object]]:
    """Derive every branch boundary from replay/teacher artifacts."""

    development.__post_init__();chronology.__post_init__();extension.__post_init__()
    real_keys=tuple(f"real:{seed}" for seed in RecoveryConfig().real_seeds)
    training=min(development.training_captures[key].training_teacher_capture
                 for key in real_keys)
    raw_floor=all(row.gate.floor_pass
        for rows in development.raw_blocks.values()
        for key,row in rows.items() if key.startswith("real:"))
    separation=all(bool(development.seed_control_measurements[name]["passed"])
        for name,_lo,_hi in chronology.oof_blocks)
    raw_capture=min(row.gate.ceiling_capture
        for rows in development.raw_blocks.values()
        for key,row in rows.items() if key.startswith("real:"))
    conversion=min(float(development.conversion_measurements[key]["retention"])
                   for key in real_keys)
    ordering=_value_ordering_measurement(curriculum=curriculum,
        development=development,teachers=teachers,chronology=chronology)
    reversal=_effect_reversal_measurement(development,chronology)
    measured=FailureMeasurements(training,raw_floor,separation,
        bool(ordering["passed"]),raw_capture,
        development.calibration_threshold_pass,conversion,
        bool(reversal["effect_trigger"]["consecutive_excluding_zero_reversal"]),
        float(extension.trigger["incremental_fraction"]))
    measured.__post_init__()
    core={"schema":"QRE2TABFAILUREMEASUREDETAIL1",
        "measurements":asdict(measured),"value_ordering":dict(ordering),
        "era_reversal":dict(reversal),"extension":dict(extension.trigger),
        "curriculum":curriculum.receipt_sha256,
        "development":development.receipt_sha256,"h2_open_count":0}
    detail=MappingProxyType({**core,"receipt_sha256":C.object_sha256(core)})
    return measured,detail


@dataclass(frozen=True,slots=True)
class FailureBranchExecution:
    branch:str
    curriculum:TwoRoundCurriculumResult
    development:DevelopmentEvaluationResult
    diagnostics:Mapping[str,object]
    manifest_path:str
    receipt_sha256:str

    def __post_init__(self)->None:
        if (self.branch not in EXECUTABLE_BRANCHES
                or self.development.status not in {
                    "PASS","FAILURE_BRANCH_REQUIRED"}
                or not self.diagnostics
                or not _sha(self.receipt_sha256)):
            raise RecoveryRefusal("failure branch execution is malformed")


def _run_curriculum_and_evaluation(*,branch:str,
        specs:Sequence[AuthoritativeConfirmationSessionSpec],
        outcomes:Sequence[CachedRecoverySession],
        initial_teachers:Sequence[CachedTeacherDay],
        initial_features:Sequence[CachedRecoverySession],
        all_sessions:Sequence[SessionRef],chronology:RecoveryChronology,
        config:RecoveryConfig,cache_root:Path,output_root:Path,
        action_objective:str="MultiRMSE",learner_backend:str="CATBOOST",
        action_backend:str|None=None,
        relation_source_features:Sequence[str]=()
        )->tuple[TwoRoundCurriculumResult,DevelopmentEvaluationResult]:
    curriculum=run_two_round_curriculum(specs=specs,outcomes=outcomes,
        initial_teachers=initial_teachers,initial_features=initial_features,
        all_sessions=all_sessions,chronology=chronology,config=config,
        cache_root=cache_root/branch.lower(),
        output_root=output_root/branch.lower()/"curriculum",workers=16,
        action_objective=action_objective,learner_backend=learner_backend,
        action_backend=action_backend,
        relation_source_features=relation_source_features)
    development=run_development_evaluation(curriculum=curriculum.final_round,
        outcomes=outcomes,teachers=curriculum.final_teachers,specs=specs,
        chronology=chronology,config=config,
        output_root=output_root/branch.lower()/"evaluation")
    return curriculum,development


def run_failure_branch(*,decision:FailureBranchDecision,
        base_curriculum:TwoRoundCurriculumResult,
        specs:Sequence[AuthoritativeConfirmationSessionSpec],
        outcomes:Sequence[CachedRecoverySession],
        initial_teachers:Sequence[CachedTeacherDay],
        initial_features:Sequence[CachedRecoverySession],
        all_sessions:Sequence[SessionRef],chronology:RecoveryChronology,
        config:RecoveryConfig,extension:ExtensionAssessment,
        cache_root:str|Path,output_root:str|Path)->FailureBranchExecution:
    """Execute exactly one measured branch through canonical replay."""

    decision.__post_init__();base_curriculum.__post_init__()
    branch=decision.branch
    if branch not in EXECUTABLE_BRANCHES:
        raise RecoveryRefusal("failure branch execution received PRIMARY_PASS")
    cache=C.assert_workspace_output(cache_root);root=C.assert_workspace_output(output_root)
    diagnostics={"decision":asdict(decision)}
    if branch=="PAIRWISE_ACTION":
        curriculum,development=_run_curriculum_and_evaluation(branch=branch,
            specs=specs,outcomes=outcomes,initial_teachers=initial_teachers,
            initial_features=initial_features,all_sessions=all_sessions,
            chronology=chronology,config=config,cache_root=cache,
            output_root=root,action_objective="PairLogitPairwise")
    elif branch=="HISTOGRAM_LEARNERS":
        candidates={};capture_detail={}
        for backend in ("LIGHTGBM","XGBOOST"):
            candidate=run_two_round_curriculum(specs=specs,outcomes=outcomes,
                initial_teachers=initial_teachers,
                initial_features=initial_features,all_sessions=all_sessions,
                chronology=chronology,config=config,
                cache_root=cache/branch.lower()/backend.lower(),
                output_root=root/branch.lower()/backend.lower()/"curriculum",
                workers=16,learner_backend=backend,action_backend=backend)
            final=candidate.final_round;captures={}
            for component,action in zip(final.component_rosters["real"],
                                        final.action_rosters["real"]):
                result=evaluate_training_teacher_capture(
                    component_roster=component,action_roster=action,
                    outcomes=outcomes,teachers=candidate.final_teachers,
                    specs=specs,feature_schema=final.feature_schema,
                    config=config,output_root=root/branch.lower()/backend.lower()/
                        "training_selection")
                captures[f"real:{component.seed}"]=result
            candidates[backend]=candidate
            capture_detail[backend]={"minimum":min(
                row.training_teacher_capture for row in captures.values()),
                "receipts":{key:row.receipt_sha256
                            for key,row in captures.items()},
                "paths":{key:row.manifest_path for key,row in captures.items()}}
        selected=max(("LIGHTGBM","XGBOOST"),key=lambda backend:(
            float(capture_detail[backend]["minimum"]),
            -(("LIGHTGBM","XGBOOST").index(backend))))
        curriculum=candidates[selected]
        development=run_development_evaluation(
            curriculum=curriculum.final_round,outcomes=outcomes,
            teachers=curriculum.final_teachers,specs=specs,
            chronology=chronology,config=config,
            output_root=root/branch.lower()/selected.lower()/"evaluation")
        diagnostics.update({"selection_metric":
            "MINIMUM_FIVE_SEED_TRAINING_TEACHER_CAPTURE",
            "backend_candidates":capture_detail,"selected_backend":selected})
    elif branch=="CAUSAL_RELATION_ENCODING":
        unstable=identify_unstable_absolute_features(load_component_matrix(
            base_curriculum.final_round.component_matrix_path),
            chronology=chronology)
        selected=tuple(map(str,unstable["selected"]))
        curriculum,development=_run_curriculum_and_evaluation(branch=branch,
            specs=specs,outcomes=outcomes,initial_teachers=initial_teachers,
            initial_features=initial_features,all_sessions=all_sessions,
            chronology=chronology,config=config,cache_root=cache,
            output_root=root,relation_source_features=selected)
        diagnostics["unstable_absolute_features"]=dict(unstable)
    elif branch=="REGRET_WEIGHTED_IMITATION":
        curriculum,development=_run_curriculum_and_evaluation(branch=branch,
            specs=specs,outcomes=outcomes,initial_teachers=initial_teachers,
            initial_features=initial_features,all_sessions=all_sessions,
            chronology=chronology,config=config,cache_root=cache,
            output_root=root,action_objective="MultiClass")
    elif branch=="STATE_CONDITIONED_CALIBRATION":
        curriculum=base_curriculum
        development=run_development_evaluation(
            curriculum=curriculum.final_round,outcomes=outcomes,
            teachers=curriculum.final_teachers,specs=specs,
            chronology=chronology,config=config,
            output_root=root/branch.lower()/"evaluation",
            state_conditioned_calibration=True)
        diagnostics.update({"learner_refit":False,
            "unchanged_curriculum_receipt_sha256":curriculum.receipt_sha256,
            "mapper_only":True})
    elif branch=="CAUSAL_TRAILING_EXPERTS":
        curriculum,development=_run_curriculum_and_evaluation(branch=branch,
            specs=specs,outcomes=outcomes,initial_teachers=initial_teachers,
            initial_features=initial_features,all_sessions=all_sessions,
            chronology=chronology,config=config,cache_root=cache,
            output_root=root,action_backend="CAUSAL_EXPERTS")
    elif branch=="EXTEND_TO_600":
        if extension.trigger.get("extend_to_600") is not True:
            raise RecoveryRefusal("600-second branch activated without exact trigger")
        features_600=materialize_feature_corpus(specs,extension.outcomes_600,
            extension.teachers_600,cache_root=cache/branch.lower()/"features",
            round_index=0,workers=16)
        curriculum,development=_run_curriculum_and_evaluation(branch=branch,
            specs=specs,outcomes=extension.outcomes_600,
            initial_teachers=extension.teachers_600,
            initial_features=features_600,all_sessions=all_sessions,
            chronology=chronology,config=config,cache_root=cache,
            output_root=root)
        diagnostics["extension_trigger"]=dict(extension.trigger)
    else:raise RecoveryRefusal("failure branch is not executable")
    core={"schema":BRANCH_EXECUTION_SCHEMA,"branch":branch,
        "decision":asdict(decision),
        "curriculum_manifest_path":curriculum.manifest_path,
        "curriculum_receipt_sha256":curriculum.receipt_sha256,
        "development_manifest_path":development.manifest_path,
        "development_receipt_sha256":development.receipt_sha256,
        "development_status":development.status,
        "diagnostics":diagnostics,"real_pre_h2_data":True,
        "rollout_rounds_completed":2,"five_real_seeds":True,
        "five_matched_shuffles":True,"workers":16,"h2_open_count":0}
    artifact={**core,"receipt_sha256":C.object_sha256(core)}
    manifest=root/branch.lower()/"branch_execution.json"
    _strict_json(manifest,artifact)
    result=FailureBranchExecution(branch,curriculum,development,
        MappingProxyType(diagnostics),str(manifest),str(artifact["receipt_sha256"]))
    result.__post_init__();return result


def load_failure_branch_execution(path:str|Path,*,
        chronology:RecoveryChronology,config:RecoveryConfig
        )->FailureBranchExecution:
    source,value=_strict_payload(path,BRANCH_EXECUTION_SCHEMA)
    curriculum=load_two_round_curriculum(value["curriculum_manifest_path"],
        chronology=chronology,config=config)
    development=load_development_evaluation(
        value["development_manifest_path"],curriculum=curriculum.final_round,
        chronology=chronology,config=config)
    if (curriculum.receipt_sha256!=value["curriculum_receipt_sha256"]
            or development.receipt_sha256
               !=value["development_receipt_sha256"]
            or development.status!=value["development_status"]):
        raise RecoveryRefusal("failure branch nested artifacts differ")
    result=FailureBranchExecution(str(value["branch"]),curriculum,development,
        MappingProxyType(dict(value["diagnostics"])),str(source),
        str(value["receipt_sha256"]));result.__post_init__();return result


def publish_failure_resolution(*,decision:FailureBranchDecision,
        measurement_detail:Mapping[str,object],
        base_curriculum:TwoRoundCurriculumResult,
        base_development:DevelopmentEvaluationResult,
        execution:FailureBranchExecution|None,output_path:str|Path
        )->Mapping[str,object]:
    """Publish PASS only when the unchanged evaluated policy actually passes."""

    decision.__post_init__();base_development.__post_init__()
    detail_core={key:item for key,item in measurement_detail.items()
                 if key!="receipt_sha256"}
    measured=dict(measurement_detail.get("measurements",{}))
    measured_receipt=C.object_sha256(
        {"schema":"QRE2TABFAILUREMEASURE1",**measured})
    if (measurement_detail.get("schema")!="QRE2TABFAILUREMEASUREDETAIL1"
            or C.object_sha256(detail_core)
               !=measurement_detail.get("receipt_sha256")
            or measured_receipt!=decision.measurements_receipt_sha256):
        raise RecoveryRefusal("failure resolution measurement lineage differs")
    if decision.branch=="PRIMARY_PASS":
        if base_development.status!="PASS" or execution is not None:
            raise RecoveryRefusal("primary failure resolution status differs")
        final_curriculum=base_curriculum;final_development=base_development
    else:
        if execution is None or execution.branch!=decision.branch:
            raise RecoveryRefusal("failure resolution lacks selected execution")
        final_curriculum=execution.curriculum
        final_development=execution.development
    status=("PASS" if final_development.status=="PASS"
            else "CONTINUE_REQUIRED")
    core={"schema":FAILURE_RESOLUTION_SCHEMA,"status":status,
        "decision":asdict(decision),
        "measurement_detail":dict(measurement_detail),
        "base_curriculum_receipt_sha256":base_curriculum.receipt_sha256,
        "base_development_receipt_sha256":base_development.receipt_sha256,
        "execution_manifest_path":None if execution is None
            else execution.manifest_path,
        "execution_receipt_sha256":None if execution is None
            else execution.receipt_sha256,
        "final_curriculum_manifest_path":final_curriculum.manifest_path,
        "final_curriculum_receipt_sha256":final_curriculum.receipt_sha256,
        "final_development_manifest_path":final_development.manifest_path,
        "final_development_receipt_sha256":final_development.receipt_sha256,
        "economic_goal_lowered":False,"terminal_null":False,
        "publication_permitted":status=="PASS","h2_open_count":0}
    artifact={**core,"receipt_sha256":C.object_sha256(core)}
    _strict_json(Path(output_path),artifact);return MappingProxyType(artifact)


def publish_failure_branch_inventory(*,
        execution_paths:Mapping[str,str],extension:ExtensionAssessment,
        chronology:RecoveryChronology,config:RecoveryConfig,
        output_path:str|Path)->Mapping[str,object]:
    """Bind real-data executions for every non-dormant downstream branch."""

    chronology.__post_init__();config.__post_init__();extension.__post_init__()
    required=set(EXECUTABLE_BRANCHES)-{"EXTEND_TO_600"}
    if set(execution_paths)!=required|(
            {"EXTEND_TO_600"} if extension.trigger["extend_to_600"] else set()):
        raise RecoveryRefusal("failure branch rehearsal inventory is incomplete")
    executions={branch:load_failure_branch_execution(path,
        chronology=chronology,config=config)
        for branch,path in execution_paths.items()}
    if any(row.branch!=branch for branch,row in executions.items()):
        raise RecoveryRefusal("failure branch rehearsal is mislabelled")
    extension_status=("EXECUTED" if extension.trigger["extend_to_600"]
                      else "DORMANT_EXACT_TRIGGER_FALSE")
    core={"schema":FAILURE_INVENTORY_SCHEMA,
        "branches":{branch:{"status":"EXECUTED",
            "execution_receipt_sha256":row.receipt_sha256,
            "development_status":row.development.status}
            for branch,row in sorted(executions.items())},
        "extension_status":extension_status,
        "extension_assessment_receipt_sha256":extension.receipt_sha256,
        "real_pre_h2_production_paths":True,"unit_or_mock_evidence":False,
        "all_registered_branches_accounted_for":True,"workers":16,
        "h2_open_count":0}
    artifact={**core,"receipt_sha256":C.object_sha256(core)}
    _strict_json(Path(output_path),artifact);return MappingProxyType(artifact)


def choose_failure_branch(*,curriculum:object,
        development:DevelopmentEvaluationResult,
        teachers:Sequence[CachedTeacherDay],chronology:RecoveryChronology,
        config:RecoveryConfig,extension:ExtensionAssessment
        )->tuple[FailureBranchDecision,Mapping[str,object]]:
    measured,detail=derive_failure_measurements(curriculum=curriculum,
        development=development,teachers=teachers,chronology=chronology,
        extension=extension)
    return select_failure_branch(measured,config=config),detail


__all__=["BRANCH_EXECUTION_SCHEMA","EXECUTABLE_BRANCHES",
    "EXTENSION_SCHEMA","FAILURE_INVENTORY_SCHEMA","FAILURE_RESOLUTION_SCHEMA",
    "ExtensionAssessment","FailureBranchExecution",
    "assess_five_minute_extension","choose_failure_branch",
    "derive_failure_measurements","load_extension_assessment",
    "load_failure_branch_execution","publish_failure_branch_inventory",
    "publish_failure_resolution","run_failure_branch"]
