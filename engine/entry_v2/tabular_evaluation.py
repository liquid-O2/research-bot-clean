"""Durable live-policy replay, calibration, and economic gate execution."""

from __future__ import annotations

from dataclasses import asdict,dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Final,Mapping,Sequence

from . import common as C
from .confirmation_experiment import AuthoritativeConfirmationSessionSpec
from .tabular_calibration import (
    CalibrationBundle,evaluate_economic_gate,measure_conversion_retention,
    measure_seed_control_separation,
)
from .tabular_campaign import CachedRecoverySession,CachedTeacherDay
from .tabular_recovery_contracts import (
    RecoveryChronology,RecoveryConfig,RecoveryRefusal,
)
from .tabular_evaluation_calibration import (
    CALIBRATION_STORE_SCHEMA,THRESHOLD_STORE_SCHEMA,ThresholdBankResult,
    fit_seed_calibration,load_calibration_bundle,load_threshold_bank,
    load_threshold_bank_result,save_calibration_bundle,select_seed_threshold,
)
from .tabular_evaluation_io import _sha,_strict_json,_strict_payload
from .tabular_evaluation_policy import (
    BLOCK_RESULT_SCHEMA,PolicyBlockResult,evaluate_policy_block,
    load_policy_block_result,
)
from .tabular_evaluation_teacher import (
    TRAINING_CAPTURE_SCHEMA,TrainingTeacherCaptureResult,
    evaluate_training_teacher_capture,load_training_teacher_capture,
)

DEVELOPMENT_EVALUATION_SCHEMA:Final="QRE2TABDEVELOPMENTEVAL2"


@dataclass(frozen=True,slots=True)
class DevelopmentEvaluationResult:
    training_captures:Mapping[str,TrainingTeacherCaptureResult]
    raw_blocks:Mapping[str,Mapping[str,PolicyBlockResult]]
    calibrations:Mapping[str,CalibrationBundle]
    threshold_banks:Mapping[str,ThresholdBankResult]
    threshold_raw_blocks:Mapping[str,PolicyBlockResult]
    forward_blocks:Mapping[str,PolicyBlockResult]
    seed_control_measurements:Mapping[str,Mapping[str,object]]
    conversion_measurements:Mapping[str,Mapping[str,object]]
    training_capture_pass:bool
    raw_oof_pass:bool
    calibration_threshold_pass:bool
    conversion_pass:bool
    frozen_forward_pass:bool
    state_conditioned_calibration:bool
    status:str
    manifest_path:str
    receipt_sha256:str

    def __post_init__(self)->None:
        expected={f"{lane}:{seed}" for lane in ("real","shuffle")
                  for seed in RecoveryConfig().real_seeds}
        expected_real={f"real:{seed}" for seed in RecoveryConfig().real_seeds}
        if (set(self.training_captures)!=expected_real
                or set(self.calibrations)!=expected or set(self.threshold_banks)!=expected
                or set(self.threshold_raw_blocks)!=expected
                or set(self.forward_blocks)!=expected
                or self.status not in {"PASS","FAILURE_BRANCH_REQUIRED"}
                or (self.status=="PASS")!=all((self.training_capture_pass,
                    self.raw_oof_pass,
                    self.calibration_threshold_pass,self.conversion_pass,
                    self.frozen_forward_pass))
                or any(row.state_conditioned!=self.state_conditioned_calibration
                       for row in self.calibrations.values())
                or not _sha(self.receipt_sha256)):
            raise RecoveryRefusal("development evaluation result is malformed")


def _development_seed_worker(args:tuple)->tuple[str,dict[str,str]]:
    """One (lane, seed) development chain for the 16-worker pool.

    Publishes through the same functions the sequential path called; the
    parent strict-loads the artifacts, so receipts are byte-identical."""

    (lane,seed,component_roster_path,action_roster_path,action_matrix_path,
     action_oof_path,outcome_rows,teacher_rows,spec_rows,schema,chronology,
     config,root,state_conditioned)=args
    from .tabular_campaign import _bounded_worker_call
    from .tabular_experiment import load_seed_rosters

    def run()->dict[str,str]:
        component=next(row for row in load_seed_rosters(component_roster_path)
                       if row.seed==seed)
        action=next(row for row in load_seed_rosters(action_roster_path)
                    if row.seed==seed)
        base=Path(root);paths={}
        if lane=="real":
            paths["training"]=evaluate_training_teacher_capture(
                component_roster=component,action_roster=action,
                outcomes=outcome_rows,teachers=teacher_rows,specs=spec_rows,
                feature_schema=schema,config=config,
                output_root=base).manifest_path
        for block_name,lo,hi in chronology.oof_blocks:
            paths[f"raw_{block_name}"]=evaluate_policy_block(
                name=f"raw_{block_name}",bounds=(lo,hi),lane=lane,
                component_roster=component,action_roster=action,
                outcomes=outcome_rows,teachers=teacher_rows,specs=spec_rows,
                feature_schema=schema,config=config,output_root=base,
                mode="RAW").manifest_path
        calibration_path=base/"calibration"/lane/f"seed_{seed}.json"
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
            output_root=base)
        paths["calibration"]=str(calibration_path)
        paths["threshold"]=threshold.manifest_path
        paths["raw_q4"]=evaluate_policy_block(name="raw_THRESHOLD",
            bounds=chronology.threshold,lane=lane,
            component_roster=component,action_roster=action,
            outcomes=outcome_rows,teachers=teacher_rows,specs=spec_rows,
            feature_schema=schema,config=config,output_root=base,
            mode="RAW").manifest_path
        paths["forward"]=evaluate_policy_block(name="frozen_FORWARD",
            bounds=chronology.forward,lane=lane,
            component_roster=component,action_roster=action,
            outcomes=outcome_rows,teachers=teacher_rows,specs=spec_rows,
            feature_schema=schema,config=config,output_root=base,
            mode="CALIBRATED",calibration=calibration,
            admission=threshold.admission).manifest_path
        return paths

    return f"{lane}:{seed}",dict(_bounded_worker_call(run))


def run_development_evaluation(*,curriculum:object,
        outcomes:Sequence[CachedRecoverySession],teachers:Sequence[CachedTeacherDay],
        specs:Sequence[AuthoritativeConfirmationSessionSpec],
        chronology:RecoveryChronology,config:RecoveryConfig,
        output_root:str|Path,
        state_conditioned_calibration:bool=False)->DevelopmentEvaluationResult:
    """Run E3-E8 for every real seed and matched shuffled control."""

    if getattr(curriculum,"round_index",None)!=2:
        raise RecoveryRefusal("development evaluation requires round-two curriculum")
    chronology.__post_init__();config.__post_init__()
    if (curriculum.chronology_receipt_sha256!=chronology.receipt_sha256
            or curriculum.config_receipt_sha256!=config.receipt_sha256):
        raise RecoveryRefusal("development curriculum chronology/config differs")
    root=C.assert_workspace_output(output_root)
    # Ten independent (lane, seed) chains, each walking the every-second
    # policy over whole windows: publish them from the corpus pool and
    # strict-load the identical artifacts here.
    jobs=[(lane,seed,curriculum.component_roster_paths[lane],
           curriculum.action_roster_paths[lane],
           curriculum.action_matrix_paths[f"{lane}:{seed}"],
           curriculum.action_oof_paths[f"{lane}:{seed}"],
           tuple(outcomes),tuple(teachers),tuple(specs),
           curriculum.feature_schema,chronology,config,str(root),
           state_conditioned_calibration)
          for lane in ("real","shuffle") for seed in config.real_seeds]
    from concurrent.futures import as_completed
    from .tabular_campaign import _corpus_pool
    artifact_map:dict[str,dict[str,str]]={}
    with _corpus_pool(config.workers) as executor:
        futures=[executor.submit(_development_seed_worker,job) for job in jobs]
        for future in as_completed(futures):
            key,paths=future.result();artifact_map[key]=paths
    keys=tuple(f"{lane}:{seed}" for lane in ("real","shuffle")
               for seed in config.real_seeds)

    training={f"real:{seed}":load_training_teacher_capture(
        artifact_map[f"real:{seed}"]["training"],config=config)
        for seed in config.real_seeds}
    training_pass=all(row.passed for row in training.values())
    raw_blocks={};separations={}
    for block_name,_lo,_hi in chronology.oof_blocks:
        rows={key:load_policy_block_result(
            artifact_map[key][f"raw_{block_name}"],config=config)
            for key in keys}
        raw_blocks[block_name]=MappingProxyType(rows)
        separations[block_name]=measure_seed_control_separation(
            [rows[f"real:{seed}"].gate for seed in config.real_seeds],
            [rows[f"shuffle:{seed}"].gate for seed in config.real_seeds])

    calibrations={};thresholds={};threshold_raw={};forward={};conversion={}
    for key in keys:
        calibrations[key]=load_calibration_bundle(
            artifact_map[key]["calibration"])
        thresholds[key]=load_threshold_bank_result(
            artifact_map[key]["threshold"],config=config)
        threshold_raw[key]=load_policy_block_result(
            artifact_map[key]["raw_q4"],config=config)
        forward[key]=load_policy_block_result(
            artifact_map[key]["forward"],config=config)
        conversion[key]=measure_conversion_retention(
            converted=thresholds[key].selected_evidence,
            raw_score_ceiling=threshold_raw[key].evidence,config=config)
    separations["FORWARD"]=measure_seed_control_separation(
        [forward[f"real:{seed}"].gate for seed in config.real_seeds],
        [forward[f"shuffle:{seed}"].gate for seed in config.real_seeds])
    threshold_gates={key:evaluate_economic_gate(value.selected_evidence,
                                                 config=config)
                     for key,value in thresholds.items()}
    separations["THRESHOLD"]=measure_seed_control_separation(
        [threshold_gates[f"real:{seed}"] for seed in config.real_seeds],
        [threshold_gates[f"shuffle:{seed}"] for seed in config.real_seeds])
    raw_pass=all(row.gate.floor_pass for values in raw_blocks.values()
                 for key,row in values.items() if key.startswith("real:")) and all(
        bool(separations[name]["passed"]) for name,_lo,_hi in chronology.oof_blocks)
    threshold_pass=(all(thresholds[f"real:{seed}"].selection.floor_feasible
                        for seed in config.real_seeds)
                    and bool(separations["THRESHOLD"]["passed"]))
    conversion_pass=all(bool(conversion[f"real:{seed}"]["passed"])
                        for seed in config.real_seeds)
    forward_pass=(all(forward[f"real:{seed}"].gate.floor_pass
                      for seed in config.real_seeds)
                  and bool(separations["FORWARD"]["passed"]))
    passed=all((training_pass,raw_pass,threshold_pass,conversion_pass,
                forward_pass))
    core={"schema":DEVELOPMENT_EVALUATION_SCHEMA,
        "curriculum":curriculum.receipt_sha256,
        "training_capture":{key:value.receipt_sha256
                            for key,value in training.items()},
        "raw_blocks":{name:{key:value.receipt_sha256 for key,value in rows.items()}
                      for name,rows in raw_blocks.items()},
        "calibrations":{key:value.receipt_sha256 for key,value in calibrations.items()},
        "thresholds":{key:value.receipt_sha256 for key,value in thresholds.items()},
        "threshold_raw":{key:value.receipt_sha256 for key,value in threshold_raw.items()},
        "forward":{key:value.receipt_sha256 for key,value in forward.items()},
        "seed_control":{key:value["receipt_sha256"]
                        for key,value in separations.items()},
        "conversion":{key:value["receipt_sha256"]
                      for key,value in conversion.items()},
        "training_capture_pass":training_pass,"raw_oof_pass":raw_pass,
        "calibration_threshold_pass":threshold_pass,
        "conversion_pass":conversion_pass,"frozen_forward_pass":forward_pass,
        "state_conditioned_calibration":state_conditioned_calibration,
        "status":"PASS" if passed else "FAILURE_BRANCH_REQUIRED",
        "h2_open_count":0}
    artifact_core={**core,
        "artifact_paths":{
            "training_capture":{key:value.manifest_path
                                for key,value in training.items()},
            "raw_blocks":{name:{key:value.manifest_path
                                for key,value in rows.items()}
                          for name,rows in raw_blocks.items()},
            "calibrations":{key:str(root/"calibration"/key.split(":")[0]/
                                    f"seed_{key.split(':')[1]}.json")
                            for key in calibrations},
            "thresholds":{key:value.manifest_path
                          for key,value in thresholds.items()},
            "threshold_raw":{key:value.manifest_path
                             for key,value in threshold_raw.items()},
            "forward":{key:value.manifest_path for key,value in forward.items()}},
        "raw_gate_detail":{name:{key:asdict(value.gate) for key,value in rows.items()}
                           for name,rows in raw_blocks.items()},
        "threshold_gate_detail":{key:tuple(asdict(row.gate)
            for row in value.selection.trials) for key,value in thresholds.items()},
        "forward_gate_detail":{key:asdict(value.gate) for key,value in forward.items()}}
    receipt=C.object_sha256(artifact_core)
    manifest=root/"development_evaluation.json"
    _strict_json(manifest,
        {**artifact_core,"receipt_sha256":receipt})
    result=DevelopmentEvaluationResult(
        MappingProxyType(training),
        MappingProxyType({key:MappingProxyType(dict(value))
                          for key,value in raw_blocks.items()}),
        MappingProxyType(calibrations),MappingProxyType(thresholds),
        MappingProxyType(threshold_raw),MappingProxyType(forward),
        MappingProxyType(separations),MappingProxyType(conversion),
        training_pass,raw_pass,threshold_pass,conversion_pass,forward_pass,
        state_conditioned_calibration,
        "PASS" if passed else "FAILURE_BRANCH_REQUIRED",str(manifest),receipt)
    result.__post_init__();return result


def load_development_evaluation(path:str|Path,*,curriculum:object,
        chronology:RecoveryChronology,config:RecoveryConfig
        )->DevelopmentEvaluationResult:
    """Reconstruct the complete E3-E8 result from durable artifacts."""

    chronology.__post_init__();config.__post_init__()
    source,value=_strict_payload(path,DEVELOPMENT_EVALUATION_SCHEMA)
    if (getattr(curriculum,"round_index",None)!=2
            or value.get("curriculum")!=curriculum.receipt_sha256
            or curriculum.chronology_receipt_sha256!=chronology.receipt_sha256
            or curriculum.config_receipt_sha256!=config.receipt_sha256):
        raise RecoveryRefusal("development reload curriculum differs")
    paths=dict(value["artifact_paths"])
    training={key:load_training_teacher_capture(path_value,config=config)
              for key,path_value in dict(paths["training_capture"]).items()}
    raw_blocks={name:MappingProxyType({key:load_policy_block_result(
                    path_value,config=config)
                for key,path_value in dict(rows).items()})
        for name,rows in dict(paths["raw_blocks"]).items()}
    calibrations={key:load_calibration_bundle(path_value)
                  for key,path_value in dict(paths["calibrations"]).items()}
    thresholds={key:load_threshold_bank_result(path_value,config=config)
                for key,path_value in dict(paths["thresholds"]).items()}
    threshold_raw={key:load_policy_block_result(path_value,config=config)
                   for key,path_value in dict(paths["threshold_raw"]).items()}
    forward={key:load_policy_block_result(path_value,config=config)
             for key,path_value in dict(paths["forward"]).items()}
    expected={f"{lane}:{seed}" for lane in ("real","shuffle")
              for seed in config.real_seeds}
    if (set(calibrations)!=expected or set(thresholds)!=expected
            or set(threshold_raw)!=expected or set(forward)!=expected
            or set(raw_blocks)!={name for name,_lo,_hi in chronology.oof_blocks}
            or any(set(rows)!=expected for rows in raw_blocks.values())):
        raise RecoveryRefusal("development reload artifact roster differs")
    for key in expected:
        if (thresholds[key].selection.calibration_receipt_sha256
                !=calibrations[key].receipt_sha256
                or forward[key].calibration_receipt_sha256
                !=calibrations[key].receipt_sha256
                or forward[key].admission_receipt_sha256
                !=thresholds[key].admission.receipt_sha256):
            raise RecoveryRefusal("development reload mapper lineage differs")
    separations={}
    for name,_lo,_hi in chronology.oof_blocks:
        rows=raw_blocks[name]
        separations[name]=measure_seed_control_separation(
            [rows[f"real:{seed}"].gate for seed in config.real_seeds],
            [rows[f"shuffle:{seed}"].gate for seed in config.real_seeds])
    threshold_gates={key:evaluate_economic_gate(row.selected_evidence,
                                                 config=config)
                     for key,row in thresholds.items()}
    separations["THRESHOLD"]=measure_seed_control_separation(
        [threshold_gates[f"real:{seed}"] for seed in config.real_seeds],
        [threshold_gates[f"shuffle:{seed}"] for seed in config.real_seeds])
    separations["FORWARD"]=measure_seed_control_separation(
        [forward[f"real:{seed}"].gate for seed in config.real_seeds],
        [forward[f"shuffle:{seed}"].gate for seed in config.real_seeds])
    conversion={key:measure_conversion_retention(
        converted=thresholds[key].selected_evidence,
        raw_score_ceiling=threshold_raw[key].evidence,config=config)
        for key in expected}
    training_pass=all(row.passed for row in training.values())
    raw_pass=all(row.gate.floor_pass for rows in raw_blocks.values()
                 for key,row in rows.items() if key.startswith("real:")) and all(
        bool(separations[name]["passed"])
        for name,_lo,_hi in chronology.oof_blocks)
    threshold_pass=(all(thresholds[f"real:{seed}"].selection.floor_feasible
                        for seed in config.real_seeds)
                    and bool(separations["THRESHOLD"]["passed"]))
    conversion_pass=all(bool(conversion[f"real:{seed}"]["passed"])
                        for seed in config.real_seeds)
    forward_pass=(all(forward[f"real:{seed}"].gate.floor_pass
                      for seed in config.real_seeds)
                  and bool(separations["FORWARD"]["passed"]))
    stored_receipts=lambda name:{str(key):str(item) for key,item in
                                  dict(value[name]).items()}
    if ({key:row.receipt_sha256 for key,row in training.items()}
            !=stored_receipts("training_capture")
            or {key:row.receipt_sha256 for key,row in calibrations.items()}
            !=stored_receipts("calibrations")
            or {key:row.receipt_sha256 for key,row in thresholds.items()}
            !=stored_receipts("thresholds")
            or {key:row.receipt_sha256 for key,row in threshold_raw.items()}
            !=stored_receipts("threshold_raw")
            or {key:row.receipt_sha256 for key,row in forward.items()}
            !=stored_receipts("forward")
            or {key:str(row["receipt_sha256"]) for key,row in separations.items()}
            !=stored_receipts("seed_control")
            or {key:str(row["receipt_sha256"]) for key,row in conversion.items()}
            !=stored_receipts("conversion")):
        raise RecoveryRefusal("development reload receipt graph differs")
    stored_raw={name:{str(key):str(item) for key,item in dict(rows).items()}
                for name,rows in dict(value["raw_blocks"]).items()}
    if ({name:{key:row.receipt_sha256 for key,row in rows.items()}
         for name,rows in raw_blocks.items()}!=stored_raw):
        raise RecoveryRefusal("development raw-block receipt graph differs")
    conditioned=bool(value["state_conditioned_calibration"])
    passed=all((training_pass,raw_pass,threshold_pass,conversion_pass,
                forward_pass))
    if (passed!=(value.get("status")=="PASS")
            or training_pass!=bool(value["training_capture_pass"])
            or raw_pass!=bool(value["raw_oof_pass"])
            or threshold_pass!=bool(value["calibration_threshold_pass"])
            or conversion_pass!=bool(value["conversion_pass"])
            or forward_pass!=bool(value["frozen_forward_pass"])
            or any(row.state_conditioned!=conditioned
                   for row in calibrations.values())):
        raise RecoveryRefusal("development reload gate status differs")
    result=DevelopmentEvaluationResult(MappingProxyType(training),
        MappingProxyType(raw_blocks),MappingProxyType(calibrations),
        MappingProxyType(thresholds),MappingProxyType(threshold_raw),
        MappingProxyType(forward),MappingProxyType(separations),
        MappingProxyType(conversion),training_pass,raw_pass,threshold_pass,
        conversion_pass,forward_pass,conditioned,
        "PASS" if passed else "FAILURE_BRANCH_REQUIRED",str(source),
        str(value["receipt_sha256"]))
    result.__post_init__();return result


__all__=["BLOCK_RESULT_SCHEMA","CALIBRATION_STORE_SCHEMA",
         "DEVELOPMENT_EVALUATION_SCHEMA",
         "TRAINING_CAPTURE_SCHEMA","TrainingTeacherCaptureResult",
         "PolicyBlockResult","THRESHOLD_STORE_SCHEMA","ThresholdBankResult",
         "DevelopmentEvaluationResult",
         "evaluate_policy_block","evaluate_training_teacher_capture",
         "fit_seed_calibration","load_development_evaluation",
         "load_calibration_bundle","load_policy_block_result",
         "load_threshold_bank","load_threshold_bank_result",
         "load_training_teacher_capture",
         "run_development_evaluation","save_calibration_bundle",
         "select_seed_threshold"]
