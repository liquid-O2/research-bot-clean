"""Independent E1R/E2R fit-only executions for Entry V2 recovery.

Neither execution may borrow a development model, calibration bank, threshold,
or rollout label.  Each starts from the frozen round-zero corpus, fits its own
chronological stacks, performs exactly two solver-in-the-loop relabel rounds,
and measures its frozen THRESHOLD and untouched FORWARD roles through the
production every-second policy and canonical replay.
"""

from __future__ import annotations

from dataclasses import asdict,dataclass
import json
import os
from pathlib import Path
from types import MappingProxyType
from typing import Final,Mapping,Sequence

from . import common as C
from .confirmation_experiment import AuthoritativeConfirmationSessionSpec
from .contracts import SessionRef
from .tabular_calibration import (
    CalibrationBundle,evaluate_economic_gate,
    measure_conversion_retention,measure_seed_control_separation,
)
from .tabular_campaign import (
    DENSE_STORE_ENV,CachedRecoverySession,CachedTeacherDay,
    warm_dense_feature_corpus,
)
from .tabular_evaluation import (
    PolicyBlockResult,ThresholdBankResult,TrainingTeacherCaptureResult,
    evaluate_policy_block,evaluate_training_teacher_capture,
    fit_seed_calibration,load_calibration_bundle,load_policy_block_result,
    load_threshold_bank_result,load_training_teacher_capture,
    select_seed_threshold,
)
from .tabular_orchestration import (
    TwoRoundCurriculumResult,load_two_round_curriculum,run_two_round_curriculum,
)
from .tabular_recovery_contracts import (
    EconomicGateResult,RecoveryChronology,RecoveryConfig,RecoveryRefusal,
    fit_only_recovery_chronology,
)


FIT_ONLY_SCHEMA:Final="QRE2TABFITONLYEXECUTION2"


def _sha(value:object)->bool:
    return (isinstance(value,str) and len(value)==64
            and all(char in "0123456789abcdef" for char in value))


def _strict_json(path:Path,value:Mapping[str,object])->str:
    target=C.assert_workspace_output(path);raw=C.canonical_bytes(value)
    if target.is_file():
        if target.read_bytes()!=raw:
            raise RecoveryRefusal("resumed fit-only artifact differs")
        return C.file_sha256(target)
    return C.atomic_json(target,value)


def _strict_payload(path:str|Path)->tuple[Path,Mapping[str,object]]:
    source=Path(path);C.guard_payload(source)
    try:value=json.loads(source.read_text())
    except (OSError,UnicodeError,json.JSONDecodeError) as exc:
        raise RecoveryRefusal("cannot strict-load fit-only execution") from exc
    core={key:item for key,item in value.items() if key!="receipt_sha256"}
    if (value.get("schema")!=FIT_ONLY_SCHEMA or value.get("h2_open_count")!=0
            or C.object_sha256(core)!=value.get("receipt_sha256")):
        raise RecoveryRefusal("fit-only execution schema/receipt differs")
    return source,MappingProxyType(value)


def _chronology_from_mapping(value:Mapping[str,object])->RecoveryChronology:
    row=dict(value)
    row["burned"]=tuple(map(int,row["burned"]))
    row["oof_blocks"]=tuple((str(name),int(lo),int(hi))
                             for name,lo,hi in row["oof_blocks"])
    for key in ("platt","threshold","forward"):
        row[key]=tuple(map(int,row[key]))
    row["rehearsals"]=tuple((str(name),*(tuple(map(int,bounds))
        for bounds in (fit,platt,threshold,forward)))
        for name,fit,platt,threshold,forward in row["rehearsals"])
    row["component_folds"]=tuple(tuple((str(raw[0]),*map(int,raw[1:])))
                                  for raw in row["component_folds"])
    row["action_folds"]=tuple(tuple((str(raw[0]),*map(int,raw[1:])))
                               for raw in row["action_folds"])
    result=RecoveryChronology(**row);result.__post_init__();return result


@dataclass(frozen=True,slots=True)
class FitOnlyExecutionResult:
    name:str
    chronology:RecoveryChronology
    curriculum:TwoRoundCurriculumResult
    training_captures:Mapping[str,TrainingTeacherCaptureResult]
    calibrations:Mapping[str,CalibrationBundle]
    threshold_banks:Mapping[str,ThresholdBankResult]
    threshold_gates:Mapping[str,EconomicGateResult]
    threshold_raw_blocks:Mapping[str,PolicyBlockResult]
    forward_blocks:Mapping[str,PolicyBlockResult]
    seed_control_measurements:Mapping[str,Mapping[str,object]]
    conversion_measurements:Mapping[str,Mapping[str,object]]
    training_capture_pass:bool
    threshold_pass:bool
    conversion_pass:bool
    forward_pass:bool
    state_conditioned_calibration:bool
    status:str
    manifest_path:str
    receipt_sha256:str

    def __post_init__(self)->None:
        expected={f"{lane}:{seed}" for lane in ("real","shuffle")
                  for seed in RecoveryConfig().real_seeds}
        real={f"real:{seed}" for seed in RecoveryConfig().real_seeds}
        self.chronology.__post_init__();self.curriculum.__post_init__()
        if (self.name not in {"E1R","E2R"}
                or set(self.training_captures)!=real
                or set(self.calibrations)!=expected
                or set(self.threshold_banks)!=expected
                or set(self.threshold_gates)!=expected
                or set(self.threshold_raw_blocks)!=expected
                or set(self.forward_blocks)!=expected
                or set(self.seed_control_measurements)!={"THRESHOLD","FORWARD"}
                or set(self.conversion_measurements)!=expected
                or self.curriculum.final_round.chronology_receipt_sha256
                   !=self.chronology.receipt_sha256
                or self.status not in {"PASS","FAILURE_BRANCH_REQUIRED"}
                or (self.status=="PASS")!=all((self.training_capture_pass,
                    self.threshold_pass,self.conversion_pass,
                    self.forward_pass))
                or any(row.state_conditioned!=self.state_conditioned_calibration
                       for row in self.calibrations.values())
                or not _sha(self.receipt_sha256)):
            raise RecoveryRefusal("fit-only execution result is malformed")


def _window_rows(*,name:str,
        specs:Sequence[AuthoritativeConfirmationSessionSpec],
        outcomes:Sequence[CachedRecoverySession],
        teachers:Sequence[CachedTeacherDay],
        features:Sequence[CachedRecoverySession],
        all_sessions:Sequence[SessionRef],
        base:RecoveryChronology)->tuple[
            tuple[AuthoritativeConfirmationSessionSpec,...],
            tuple[CachedRecoverySession,...],tuple[CachedTeacherDay,...],
            tuple[CachedRecoverySession,...],tuple[SessionRef,...]]:
    fit=base.rehearsal_window(name,"FIT")
    forward=base.rehearsal_window(name,"FORWARD")
    lo,hi=fit[0],forward[1]
    inside=lambda day:lo<=int(day)<=hi
    spec_rows=tuple(sorted((row for row in specs if inside(row.trading_day)),
                           key=lambda row:row.session))
    outcome_rows=tuple(sorted((row for row in outcomes
                               if inside(row.session.trading_day)),
                              key=lambda row:row.session))
    teacher_rows=tuple(sorted((row for row in teachers
                               if inside(row.trading_day)),
                              key=lambda row:row.trading_day))
    feature_rows=tuple(sorted((row for row in features
                               if inside(row.session.trading_day)),
                              key=lambda row:row.session))
    sessions=tuple(sorted(row for row in all_sessions
                          if inside(row.trading_day)))
    if (not spec_rows or {row.session for row in spec_rows}!=set(sessions)
            or {row.session for row in outcome_rows}!=set(sessions)
            or any(row.rollout_rounds_completed!=0 for row in teacher_rows)):
        raise RecoveryRefusal("fit-only frozen source window differs")
    return spec_rows,outcome_rows,teacher_rows,feature_rows,sessions


def _seed_evaluation_worker(args:tuple)->tuple[str,Mapping[str,str]]:
    """One independent (lane, seed) evaluation unit for the 16-worker pool.

    Every artifact is published by the same functions the sequential path
    called; the parent strict-loads them afterwards, so receipts and
    economics are byte-identical — only the execution order changes.
    """

    (kind,name,lane,seed,component_roster_path,action_roster_path,
     action_matrix_path,action_oof_path,outcome_rows,teacher_rows,spec_rows,
     schema,chronology,config,root,state_conditioned)=args
    from .tabular_campaign import _bounded_worker_call
    from .tabular_experiment import load_seed_rosters

    def run()->dict[str,str]:
        component=next(row for row in load_seed_rosters(component_roster_path)
                       if row.seed==seed)
        action=next(row for row in load_seed_rosters(action_roster_path)
                    if row.seed==seed)
        base=Path(root)
        if kind=="TRAINING":
            result=evaluate_training_teacher_capture(
                component_roster=component,action_roster=action,
                outcomes=outcome_rows,teachers=teacher_rows,specs=spec_rows,
                feature_schema=schema,config=config,
                output_root=base/"evaluation")
            return {"training":result.manifest_path}
        calibration_path=(base/"evaluation"/"calibration"/lane/
                          f"seed_{seed}.json")
        calibration=fit_seed_calibration(
            action_matrix_path=action_matrix_path,
            action_oof_path=action_oof_path,action_roster=action,
            chronology=chronology,output_path=calibration_path,
            state_conditioned=state_conditioned)
        threshold=select_seed_threshold(lane=lane,
            component_roster=component,action_roster=action,
            action_matrix_path=action_matrix_path,
            action_oof_path=action_oof_path,calibration=calibration,
            outcomes=outcome_rows,teachers=teacher_rows,specs=spec_rows,
            feature_schema=schema,chronology=chronology,config=config,
            output_root=base/"evaluation")
        raw=evaluate_policy_block(name=f"{name}_raw_THRESHOLD",
            bounds=chronology.threshold,lane=lane,
            component_roster=component,action_roster=action,
            outcomes=outcome_rows,teachers=teacher_rows,specs=spec_rows,
            feature_schema=schema,config=config,
            output_root=base/"evaluation",mode="RAW")
        forward=evaluate_policy_block(name=f"{name}_frozen_FORWARD",
            bounds=chronology.forward,lane=lane,
            component_roster=component,action_roster=action,
            outcomes=outcome_rows,teachers=teacher_rows,specs=spec_rows,
            feature_schema=schema,config=config,
            output_root=base/"evaluation",mode="CALIBRATED",
            calibration=calibration,admission=threshold.admission)
        return {"calibration":str(calibration_path),
                "threshold":threshold.manifest_path,
                "raw":raw.manifest_path,"forward":forward.manifest_path}

    return f"{lane}:{seed}",dict(_bounded_worker_call(run))


def run_fit_only_execution(*,name:str,
        specs:Sequence[AuthoritativeConfirmationSessionSpec],
        outcomes:Sequence[CachedRecoverySession],
        initial_teachers:Sequence[CachedTeacherDay],
        initial_features:Sequence[CachedRecoverySession],
        all_sessions:Sequence[SessionRef],config:RecoveryConfig,
        cache_root:str|Path,output_root:str|Path,workers:int=16,
        action_objective:str="MultiRMSE",
        learner_backend:str="CATBOOST",
        action_backend:str|None=None,
        relation_source_features:Sequence[str]=(),
        state_conditioned_calibration:bool=False)->FitOnlyExecutionResult:
    name=str(name).upper();base=RecoveryChronology();base.__post_init__()
    config.__post_init__()
    if name not in {"E1R","E2R"} or workers!=config.workers:
        raise RecoveryRefusal("fit-only execution name/workers differ")
    (spec_rows,outcome_rows,teacher_rows,feature_rows,
     sessions)=_window_rows(name=name,specs=specs,outcomes=outcomes,
        teachers=initial_teachers,features=initial_features,
        all_sessions=all_sessions,base=base)
    fit_bounds=base.rehearsal_window(name,"FIT")
    active_fit_days=tuple(row.trading_day for row in teacher_rows
                          if fit_bounds[0]<=row.trading_day<=fit_bounds[1])
    chronology=fit_only_recovery_chronology(name,active_fit_days)
    root=C.assert_workspace_output(output_root)/name.lower()
    curriculum=run_two_round_curriculum(specs=spec_rows,
        outcomes=outcome_rows,initial_teachers=teacher_rows,
        initial_features=feature_rows,all_sessions=sessions,
        chronology=chronology,config=config,
        cache_root=C.assert_workspace_output(cache_root)/name.lower(),
        output_root=root/"curriculum",workers=workers,
        action_objective=action_objective,learner_backend=learner_backend,
        action_backend=action_backend,
        relation_source_features=relation_source_features)
    final=curriculum.final_round
    components=final.component_rosters;actions=final.action_rosters

    if os.environ.get(DENSE_STORE_ENV):
        # The evaluation blocks below otherwise materialize ~1h dense
        # sessions one at a time inside this parent process.  Fill the
        # shared store across the 16-worker pool first; every block then
        # strict-loads identical bytes.
        train_lo,train_hi,*_rest=chronology.fit_fold("ACTION","FROZEN_Q3_E8")
        windows=((train_lo,train_hi),chronology.threshold,chronology.forward)
        wanted={row.session for row in outcome_rows
                if row.status=="MATERIALIZED" and any(
                    lo<=row.session.trading_day<=hi for lo,hi in windows)}
        warm_specs=tuple(row for row in spec_rows if row.session in wanted)
        horizons={int(json.loads(Path(row.manifest_path).read_text())
                      ["max_delay_sec"]) for row in outcome_rows
                  if row.status=="MATERIALIZED" and row.session in wanted}
        if len(horizons)!=1:
            raise RecoveryRefusal("fit-only evaluation horizons differ")
        warm_dense_feature_corpus(warm_specs,max_delay_sec=next(iter(horizons)),
            cache_root=C.assert_workspace_output(cache_root)/name.lower()/
                "rollout",workers=workers)

    # The 5 training captures and 20 (lane, seed) evaluation chains are
    # mutually independent and each one walks the every-second production
    # policy over whole windows; sequentially they serialize hundreds of
    # policy-day walks in this one process.  Publish them from the corpus
    # pool and strict-load the identical artifacts here.
    jobs=[]
    for component in components["real"]:
        jobs.append(("TRAINING",name,"real",component.seed,
            final.component_roster_paths["real"],
            final.action_roster_paths["real"],None,None,
            outcome_rows,curriculum.final_teachers,spec_rows,
            final.feature_schema,chronology,config,str(root),
            state_conditioned_calibration))
    for lane in ("real","shuffle"):
        for component in components[lane]:
            key=f"{lane}:{component.seed}"
            jobs.append(("EVAL",name,lane,component.seed,
                final.component_roster_paths[lane],
                final.action_roster_paths[lane],
                final.action_matrix_paths[key],final.action_oof_paths[key],
                outcome_rows,curriculum.final_teachers,spec_rows,
                final.feature_schema,chronology,config,str(root),
                state_conditioned_calibration))
    from .tabular_campaign import _corpus_pool
    from concurrent.futures import as_completed
    artifact_paths:dict[str,dict[str,str]]={}
    with _corpus_pool(workers) as executor:
        futures=[executor.submit(_seed_evaluation_worker,job) for job in jobs]
        for future in as_completed(futures):
            key,paths=future.result()
            artifact_paths.setdefault(key,{}).update(paths)

    training={}
    for component in components["real"]:
        key=f"real:{component.seed}"
        training[key]=load_training_teacher_capture(
            artifact_paths[key]["training"],config=config)

    calibrations={};thresholds={};threshold_gates={};raw_blocks={}
    forward_blocks={};conversion={}
    for lane in ("real","shuffle"):
        for component in components[lane]:
            key=f"{lane}:{component.seed}";paths=artifact_paths[key]
            calibration=load_calibration_bundle(paths["calibration"])
            threshold=load_threshold_bank_result(paths["threshold"],
                                                 config=config)
            raw=load_policy_block_result(paths["raw"],config=config)
            forward=load_policy_block_result(paths["forward"],config=config)
            calibrations[key]=calibration;thresholds[key]=threshold
            threshold_gates[key]=evaluate_economic_gate(
                threshold.selected_evidence,config=config)
            raw_blocks[key]=raw;forward_blocks[key]=forward
            conversion[key]=measure_conversion_retention(
                converted=threshold.selected_evidence,
                raw_score_ceiling=raw.evidence,config=config)

    separations={
        "THRESHOLD":measure_seed_control_separation(
            [threshold_gates[f"real:{seed}"] for seed in config.real_seeds],
            [threshold_gates[f"shuffle:{seed}"] for seed in config.real_seeds]),
        "FORWARD":measure_seed_control_separation(
            [forward_blocks[f"real:{seed}"].gate for seed in config.real_seeds],
            [forward_blocks[f"shuffle:{seed}"].gate for seed in config.real_seeds]),
    }
    training_pass=all(row.passed for row in training.values())
    threshold_pass=(all(threshold_gates[f"real:{seed}"].floor_pass
                        for seed in config.real_seeds)
                    and bool(separations["THRESHOLD"]["passed"]))
    conversion_pass=all(bool(conversion[f"real:{seed}"]["passed"])
                        for seed in config.real_seeds)
    forward_pass=(all(forward_blocks[f"real:{seed}"].gate.floor_pass
                      for seed in config.real_seeds)
                  and bool(separations["FORWARD"]["passed"]))
    passed=all((training_pass,threshold_pass,conversion_pass,forward_pass))
    core={"schema":FIT_ONLY_SCHEMA,"name":name,
        "chronology":asdict(chronology),
        "chronology_receipt_sha256":chronology.receipt_sha256,
        "curriculum_receipt_sha256":curriculum.receipt_sha256,
        "training_captures":{key:value.receipt_sha256
                             for key,value in training.items()},
        "calibrations":{key:value.receipt_sha256
                        for key,value in calibrations.items()},
        "threshold_banks":{key:value.receipt_sha256
                           for key,value in thresholds.items()},
        "threshold_gates":{key:value.receipt_sha256
                           for key,value in threshold_gates.items()},
        "threshold_raw_blocks":{key:value.receipt_sha256
                                for key,value in raw_blocks.items()},
        "forward_blocks":{key:value.receipt_sha256
                          for key,value in forward_blocks.items()},
        "seed_control":{key:value["receipt_sha256"]
                        for key,value in separations.items()},
        "conversion":{key:value["receipt_sha256"]
                      for key,value in conversion.items()},
        "training_capture_pass":training_pass,
        "threshold_pass":threshold_pass,"conversion_pass":conversion_pass,
        "forward_pass":forward_pass,
        "state_conditioned_calibration":state_conditioned_calibration,
        "status":"PASS" if passed else "FAILURE_BRANCH_REQUIRED",
        "independent_models":True,"borrowed_development_artifacts":False,
        "learner_backend":curriculum.learner_backend,
        "action_backend":curriculum.action_backend,
        "relation_source_features":curriculum.relation_source_features,
        "workers":16,"h2_open_count":0}
    detail={**core,
        "artifact_paths":{
            "curriculum":curriculum.manifest_path,
            "training_captures":{key:value.manifest_path
                                  for key,value in training.items()},
            "calibrations":{key:str(root/"evaluation"/"calibration"/
                key.split(":")[0]/f"seed_{key.split(':')[1]}.json")
                for key in calibrations},
            "threshold_banks":{key:value.manifest_path
                               for key,value in thresholds.items()},
            "threshold_raw_blocks":{key:value.manifest_path
                                    for key,value in raw_blocks.items()},
            "forward_blocks":{key:value.manifest_path
                              for key,value in forward_blocks.items()}},
        "training_capture_detail":{key:{
            "capture":value.training_teacher_capture,"passed":value.passed}
            for key,value in training.items()},
        "threshold_gate_detail":{key:asdict(value)
                                 for key,value in threshold_gates.items()},
        "forward_gate_detail":{key:asdict(value.gate)
                               for key,value in forward_blocks.items()}}
    receipt=C.object_sha256(detail);manifest=root/"fit_only_execution.json"
    _strict_json(manifest,{**detail,"receipt_sha256":receipt})
    result=FitOnlyExecutionResult(name,chronology,curriculum,
        MappingProxyType(training),MappingProxyType(calibrations),
        MappingProxyType(thresholds),MappingProxyType(threshold_gates),
        MappingProxyType(raw_blocks),MappingProxyType(forward_blocks),
        MappingProxyType(separations),MappingProxyType(conversion),
        training_pass,threshold_pass,conversion_pass,forward_pass,
        state_conditioned_calibration,
        "PASS" if passed else "FAILURE_BRANCH_REQUIRED",str(manifest),receipt)
    result.__post_init__();return result


def load_fit_only_execution(path:str|Path,*,config:RecoveryConfig
                            )->FitOnlyExecutionResult:
    """Strictly reconstruct an independent E1R/E2R execution."""

    config.__post_init__();source,value=_strict_payload(path)
    chronology=_chronology_from_mapping(value["chronology"])
    if chronology.receipt_sha256!=value["chronology_receipt_sha256"]:
        raise RecoveryRefusal("fit-only chronology receipt differs")
    paths=dict(value["artifact_paths"])
    curriculum=load_two_round_curriculum(paths["curriculum"],
        chronology=chronology,config=config)
    training={key:load_training_teacher_capture(path_value,config=config)
              for key,path_value in dict(paths["training_captures"]).items()}
    calibrations={key:load_calibration_bundle(path_value)
                  for key,path_value in dict(paths["calibrations"]).items()}
    thresholds={key:load_threshold_bank_result(path_value,config=config)
                for key,path_value in dict(paths["threshold_banks"]).items()}
    raw_blocks={key:load_policy_block_result(path_value,config=config)
                for key,path_value in dict(paths["threshold_raw_blocks"]).items()}
    forward={key:load_policy_block_result(path_value,config=config)
             for key,path_value in dict(paths["forward_blocks"]).items()}
    expected={f"{lane}:{seed}" for lane in ("real","shuffle")
              for seed in config.real_seeds}
    real={f"real:{seed}" for seed in config.real_seeds}
    if (set(training)!=real or any(set(rows)!=expected for rows in (
            calibrations,thresholds,raw_blocks,forward))):
        raise RecoveryRefusal("fit-only reload artifact roster differs")
    threshold_gates={key:evaluate_economic_gate(row.selected_evidence,
                                                 config=config)
                     for key,row in thresholds.items()}
    separations={
        "THRESHOLD":measure_seed_control_separation(
            [threshold_gates[f"real:{seed}"] for seed in config.real_seeds],
            [threshold_gates[f"shuffle:{seed}"] for seed in config.real_seeds]),
        "FORWARD":measure_seed_control_separation(
            [forward[f"real:{seed}"].gate for seed in config.real_seeds],
            [forward[f"shuffle:{seed}"].gate for seed in config.real_seeds]),
    }
    conversion={key:measure_conversion_retention(
        converted=thresholds[key].selected_evidence,
        raw_score_ceiling=raw_blocks[key].evidence,config=config)
        for key in expected}
    training_pass=all(row.passed for row in training.values())
    threshold_pass=(all(threshold_gates[f"real:{seed}"].floor_pass
                        for seed in config.real_seeds)
                    and bool(separations["THRESHOLD"]["passed"]))
    conversion_pass=all(bool(conversion[f"real:{seed}"]["passed"])
                        for seed in config.real_seeds)
    forward_pass=(all(forward[f"real:{seed}"].gate.floor_pass
                      for seed in config.real_seeds)
                  and bool(separations["FORWARD"]["passed"]))
    receipt_map=lambda name:{str(key):str(item) for key,item in
                              dict(value[name]).items()}
    if (curriculum.receipt_sha256!=value["curriculum_receipt_sha256"]
            or {key:row.receipt_sha256 for key,row in training.items()}
               !=receipt_map("training_captures")
            or {key:row.receipt_sha256 for key,row in calibrations.items()}
               !=receipt_map("calibrations")
            or {key:row.receipt_sha256 for key,row in thresholds.items()}
               !=receipt_map("threshold_banks")
            or {key:row.receipt_sha256 for key,row in threshold_gates.items()}
               !=receipt_map("threshold_gates")
            or {key:row.receipt_sha256 for key,row in raw_blocks.items()}
               !=receipt_map("threshold_raw_blocks")
            or {key:row.receipt_sha256 for key,row in forward.items()}
               !=receipt_map("forward_blocks")
            or {key:str(row["receipt_sha256"]) for key,row in separations.items()}
               !=receipt_map("seed_control")
            or {key:str(row["receipt_sha256"]) for key,row in conversion.items()}
               !=receipt_map("conversion")):
        raise RecoveryRefusal("fit-only reload receipt graph differs")
    conditioned=bool(value["state_conditioned_calibration"])
    passed=all((training_pass,threshold_pass,conversion_pass,forward_pass))
    if (training_pass!=bool(value["training_capture_pass"])
            or threshold_pass!=bool(value["threshold_pass"])
            or conversion_pass!=bool(value["conversion_pass"])
            or forward_pass!=bool(value["forward_pass"])
            or passed!=(value.get("status")=="PASS")
            or any(row.state_conditioned!=conditioned
                   for row in calibrations.values())):
        raise RecoveryRefusal("fit-only reload gate status differs")
    result=FitOnlyExecutionResult(str(value["name"]),chronology,curriculum,
        MappingProxyType(training),MappingProxyType(calibrations),
        MappingProxyType(thresholds),MappingProxyType(threshold_gates),
        MappingProxyType(raw_blocks),MappingProxyType(forward),
        MappingProxyType(separations),MappingProxyType(conversion),
        training_pass,threshold_pass,conversion_pass,forward_pass,conditioned,
        "PASS" if passed else "FAILURE_BRANCH_REQUIRED",str(source),
        str(value["receipt_sha256"]))
    result.__post_init__();return result


__all__=["FIT_ONLY_SCHEMA","FitOnlyExecutionResult",
         "load_fit_only_execution","run_fit_only_execution"]
