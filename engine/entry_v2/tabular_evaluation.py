"""Durable live-policy replay, calibration, and economic gate execution."""

from __future__ import annotations

from dataclasses import asdict,dataclass
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Final,Mapping,Sequence

import numpy as np

from . import common as C
from .confirmation_experiment import AuthoritativeConfirmationSessionSpec
from .contracts import SessionRef
from .exact_delayed_teacher import DayOptionUniverse,ExactDelayedTeacherDay
from .tabular_calibration import (
    AdmissionContract,BlockReplayEvidence,CalibrationBundle,ThresholdSelection,
    ThresholdTrial,evaluate_economic_gate,fit_calibration_bundle,
    measure_conversion_retention,measure_seed_control_separation,
    select_threshold_from_calibration_bank,
)
from .tabular_campaign import (
    CachedRecoverySession,CachedTeacherDay,
    load_or_materialize_dense_session,
)
from .tabular_experiment import ActionPredictionTable,SeedModelRoster
from .tabular_live_replay import (
    PolicyDayTrace,load_policy_day_trace,replay_policy_block,
    replay_policy_day,save_policy_day_trace,
)
from .tabular_matrix_store import load_action_matrix
from .tabular_models import ActionModelBundle,ComponentModelBundle
from .tabular_model_io import load_action_model,load_component_model
from .tabular_recovery_contracts import (
    CausalFeatureSchema,EconomicGateResult,REGIME_FEATURE_NAMES,
    RecoveryChronology,RecoveryConfig,RecoveryRefusal,
)
from .tabular_walk_twin import wtwin_load_or_replay_day_multistate


BLOCK_RESULT_SCHEMA:Final="QRE2TABPOLICYBLOCK2"
CALIBRATION_STORE_SCHEMA:Final="QRE2TABCALIBRATIONSTORE1"
THRESHOLD_STORE_SCHEMA:Final="QRE2TABTHRESHOLDSTORE2"
TRAINING_CAPTURE_SCHEMA:Final="QRE2TABTRAININGCAPTURE2"
DEVELOPMENT_EVALUATION_SCHEMA:Final="QRE2TABDEVELOPMENTEVAL2"


def _sha(value:object)->bool:
    return (isinstance(value,str) and len(value)==64
            and all(char in "0123456789abcdef" for char in value))


def _array_sha256(value:np.ndarray)->str:
    array=np.ascontiguousarray(value);digest=hashlib.sha256()
    digest.update(str(array.dtype).encode());digest.update(repr(array.shape).encode())
    digest.update(array.tobytes());return digest.hexdigest()


def _strict_json(path:Path,value:Mapping[str,object])->str:
    target=C.assert_workspace_output(path);raw=C.canonical_bytes(value)
    if target.is_file():
        if target.read_bytes()!=raw:
            raise RecoveryRefusal("resumed evaluation artifact differs")
        return C.file_sha256(target)
    return C.atomic_json(target,value)


def _strict_payload(path:str|Path,schema:str)->tuple[Path,Mapping[str,object]]:
    source=Path(path);C.guard_payload(source)
    try:value=json.loads(source.read_text())
    except (OSError,UnicodeError,json.JSONDecodeError) as exc:
        raise RecoveryRefusal("cannot strict-load evaluation artifact") from exc
    core={key:item for key,item in value.items() if key!="receipt_sha256"}
    if (value.get("schema")!=schema or value.get("h2_open_count")!=0
            or C.object_sha256(core)!=value.get("receipt_sha256")):
        raise RecoveryRefusal("evaluation artifact schema/receipt differs")
    return source,MappingProxyType(value)


def _sessions_from_payload(rows:Sequence[Mapping[str,object]])->tuple[SessionRef,...]:
    result=tuple(sorted(SessionRef(**dict(row)) for row in rows))
    if not result or len(result)!=len(set(result)):
        raise RecoveryRefusal("evaluation session denominator differs")
    return result


def _evidence_from_trace_payload(value:Mapping[str,object])->BlockReplayEvidence:
    paths=tuple(map(str,value["trace_paths"]))
    receipts=tuple(map(str,value["trace_receipts"]))
    if len(paths)!=len(receipts) or not paths:
        raise RecoveryRefusal("evaluation trace roster differs")
    traces=tuple(load_policy_day_trace(path) for path in paths)
    if tuple(row.receipt_sha256 for row in traces)!=receipts:
        raise RecoveryRefusal("evaluation trace receipt differs")
    sessions=_sessions_from_payload(value["expected_sessions"])
    ceilings={int(day):int(cents) for day,cents in
              dict(value["exact_ceiling_cents_by_day"]).items()}
    asset_ceilings={str(asset):int(cents) for asset,cents in
                    dict(value["exact_ceiling_cents_by_asset"]).items()}
    return replay_policy_block(traces,expected_sessions=sessions,
                               exact_ceiling_cents_by_day=ceilings,
                               exact_ceiling_cents_by_asset=asset_ceilings)


def _outcomes_by_day(rows:Sequence[CachedRecoverySession]
        )->Mapping[int,tuple[CachedRecoverySession,...]]:
    output:dict[int,list[CachedRecoverySession]]={}
    for row in rows:
        if row.status=="MATERIALIZED":
            output.setdefault(row.session.trading_day,[]).append(row)
    return MappingProxyType({day:tuple(sorted(values,key=lambda row:row.session))
                              for day,values in sorted(output.items())})


def _specs_by_day(rows:Sequence[AuthoritativeConfirmationSessionSpec]
        )->Mapping[int,tuple[AuthoritativeConfirmationSessionSpec,...]]:
    output:dict[int,list[AuthoritativeConfirmationSessionSpec]]={}
    for row in rows:output.setdefault(row.trading_day,[]).append(row)
    return MappingProxyType({day:tuple(sorted(values,key=lambda row:row.asset))
                              for day,values in sorted(output.items())})


def _sessions_for_bounds(specs:Sequence[AuthoritativeConfirmationSessionSpec],
                         bounds:tuple[int,int])->tuple[SessionRef,...]:
    lo,hi=map(int,bounds);rows=tuple(sorted(
        spec.session for spec in specs if lo<=spec.trading_day<=hi))
    if not rows or {row.asset for row in rows}!=set(C.ASSETS):
        raise RecoveryRefusal("policy block has no all-asset denominator")
    return rows


def _universe(rows:Sequence[CachedRecoverySession])->DayOptionUniverse:
    from .tabular_delayed_corpus import DelayedOutcomeShard
    result=DayOptionUniverse.from_shards(tuple(
        DelayedOutcomeShard.load(row.artifact_path) for row in rows))
    return result


def _asset_ceiling_cents(*,teacher_map:Mapping[int,CachedTeacherDay],
        outcome_map:Mapping[int,tuple[CachedRecoverySession,...]],
        active_days:Sequence[int])->dict[str,int]:
    totals={asset:0 for asset in C.ASSETS}
    for day in active_days:
        universe=_universe(outcome_map[day])
        teacher=ExactDelayedTeacherDay.load(teacher_map[day].artifact_path)
        if teacher.representation_sha256!=teacher_map[day].representation_sha256:
            raise RecoveryRefusal("teacher representation drifted before per-asset ceiling")
        selected=set(map(str,teacher.selected_opportunity_ids))
        day_totals={asset:0 for asset in C.ASSETS}
        for oid,asset,cents in zip(
                np.asarray(universe.opportunity_id,str),
                np.asarray(universe.asset,str),
                np.asarray(universe.signed_pnl_cents,np.int64)):
            if str(oid) in selected:
                day_totals[str(asset)]+=int(cents)
        if sum(day_totals.values())!=int(teacher.exact_objective_cents):
            raise RecoveryRefusal("per-asset delayed-teacher dollars do not reconcile")
        for asset,value in day_totals.items():
            totals[asset]+=value
    if sum(totals.values())!=sum(
            int(teacher_map[day].exact_objective_cents) for day in active_days):
        raise RecoveryRefusal("block per-asset delayed-teacher dollars do not reconcile")
    return totals


def _validate_roster_pair(component:SeedModelRoster,action:SeedModelRoster)->None:
    component.__post_init__();action.__post_init__()
    if (component.kind!="COMPONENT" or action.kind!="ACTION"
            or component.seed!=action.seed
            or component.shuffled_labels!=action.shuffled_labels
            or component.shuffle_seed!=action.shuffle_seed
            or component.chronology_receipt_sha256
               !=action.chronology_receipt_sha256):
        raise RecoveryRefusal("policy replay component/action roster pair differs")


def _trace_identity(*,day:int,mode:str,universe:DayOptionUniverse,
        component_receipt:str,action_receipt:str,
        feature_schema:CausalFeatureSchema,calibration:CalibrationBundle|None,
        admission:AdmissionContract|None)->str:
    return C.object_sha256({"schema":"QRE2TABPOLICYTRACEIDENTITY1",
        "day":day,"mode":mode,"universe":universe.representation_sha256,
        "component":component_receipt,"action":action_receipt,
        "feature_schema":feature_schema.receipt_sha256,
        "calibration":None if calibration is None else calibration.receipt_sha256,
        "admission":None if admission is None else admission.receipt_sha256,
        "live_implementation":C.file_sha256(
            Path(__file__).with_name("tabular_live_replay.py")),
        "feature_implementation":C.file_sha256(
            Path(__file__).with_name("confirmation.py")),"h2_open_count":0})


def _load_or_replay_day(*,day:int,universe:DayOptionUniverse,
        specs:Sequence[AuthoritativeConfirmationSessionSpec],
        outcome_rows:Sequence[CachedRecoverySession],
        feature_schema:CausalFeatureSchema,component_fold:object,
        action_fold:object,mode:str,output_root:Path,
        calibration:CalibrationBundle|None=None,
        admission:AdmissionContract|None=None,
        dense_features:Sequence[object]|None=None)->PolicyDayTrace:
    component=load_component_model(component_fold.bundle_path)
    action=load_action_model(action_fold.bundle_path)
    if (component.receipt_sha256!=component_fold.bundle_receipt_sha256
            or action.receipt_sha256!=action_fold.bundle_receipt_sha256):
        raise RecoveryRefusal("policy replay fold model strict load differs")
    identity=_trace_identity(day=day,mode=mode,universe=universe,
        component_receipt=component.receipt_sha256,
        action_receipt=action.receipt_sha256,feature_schema=feature_schema,
        calibration=calibration,admission=admission)
    target=output_root/mode.lower()/identity/f"{day}.json"
    if target.is_file():
        trace=load_policy_day_trace(target)
        if (trace.source_universe_sha256!=universe.representation_sha256
                or trace.component_model_sha256!=component.receipt_sha256
                or trace.action_model_sha256!=action.receipt_sha256
                or trace.feature_schema_sha256!=feature_schema.receipt_sha256):
            raise RecoveryRefusal("resumed policy trace inputs differ")
        return trace
    materialized={row.session for row in outcome_rows}
    day_specs=tuple(row for row in specs if row.session in materialized)
    if len(day_specs)!=len(outcome_rows):
        raise RecoveryRefusal("policy trace source spec/outcome roster differs")
    from .tabular_delayed_corpus import DelayedOutcomeShard
    horizons={DelayedOutcomeShard.load(row.artifact_path).max_delay_sec
              for row in outcome_rows}
    if len(horizons)!=1:
        raise RecoveryRefusal("policy trace outcome horizons differ")
    max_delay_sec=int(next(iter(horizons)))
    dense=tuple(dense_features) if dense_features is not None else tuple(
        load_or_materialize_dense_session(
            row,max_delay_sec=max_delay_sec)
        for row in day_specs)
    trace=replay_policy_day(universe=universe,dense_feature_shards=dense,
        feature_schema=feature_schema,component_model=component,
        action_model=action,mode=mode,calibration=calibration,
        admission=admission,collect_proposals=False)
    save_policy_day_trace(trace,target);stored=load_policy_day_trace(target)
    if stored.receipt_sha256!=trace.receipt_sha256:
        raise RecoveryRefusal("policy day trace strict reload differs")
    return stored


@dataclass(frozen=True,slots=True)
class PolicyBlockResult:
    name:str
    bounds:tuple[int,int]
    lane:str
    seed:int
    mode:str
    trace_paths:tuple[str,...]
    evidence:BlockReplayEvidence
    gate:EconomicGateResult
    component_roster_receipt_sha256:str
    action_roster_receipt_sha256:str
    calibration_receipt_sha256:str|None
    admission_receipt_sha256:str|None
    manifest_path:str
    receipt_sha256:str

    def __post_init__(self)->None:
        if (not self.name or self.bounds[0]>self.bounds[1]
                or self.lane not in {"real","shuffle"}
                or self.mode not in {"RAW","CALIBRATED"}
                or not self.trace_paths
                or not all(_sha(value) for value in (
                    self.component_roster_receipt_sha256,
                    self.action_roster_receipt_sha256,self.gate.receipt_sha256,
                    self.receipt_sha256))
                or (self.mode=="CALIBRATED")
                   !=(self.calibration_receipt_sha256 is not None)
                or (self.mode=="CALIBRATED")
                   !=(self.admission_receipt_sha256 is not None)):
            raise RecoveryRefusal("policy block result is malformed")


@dataclass(frozen=True,slots=True)
class TrainingTeacherCaptureResult:
    """Exact live replay of the final action fold on its fit period.

    This is deliberately typed as an in-sample diagnostic.  It controls the
    failure ladder only and can never satisfy an OOF or forward economic gate.
    Component predictions remain chronological OOF on every replayed day.
    """

    seed:int
    bounds:tuple[int,int]
    trace_paths:tuple[str,...]
    evidence:BlockReplayEvidence
    training_teacher_capture:float
    target_capture:float
    passed:bool
    component_roster_receipt_sha256:str
    action_roster_receipt_sha256:str
    fixed_action_model_receipt_sha256:str
    manifest_path:str
    receipt_sha256:str

    def __post_init__(self)->None:
        if (self.bounds[0]>self.bounds[1] or not self.trace_paths
                or not np.isfinite(self.training_teacher_capture)
                or self.target_capture!=RecoveryConfig().target_ceiling_capture
                or self.passed!=(self.training_teacher_capture
                                >=self.target_capture)
                or not all(_sha(value) for value in (
                    self.component_roster_receipt_sha256,
                    self.action_roster_receipt_sha256,
                    self.fixed_action_model_receipt_sha256,
                    self.receipt_sha256))):
            raise RecoveryRefusal("training teacher-capture result is malformed")


def evaluate_policy_block(*,name:str,bounds:tuple[int,int],lane:str,
        component_roster:SeedModelRoster,action_roster:SeedModelRoster,
        outcomes:Sequence[CachedRecoverySession],teachers:Sequence[CachedTeacherDay],
        specs:Sequence[AuthoritativeConfirmationSessionSpec],
        feature_schema:CausalFeatureSchema,config:RecoveryConfig,
        output_root:str|Path,mode:str="RAW",
        calibration:CalibrationBundle|None=None,
        admission:AdmissionContract|None=None)->PolicyBlockResult:
    _validate_roster_pair(component_roster,action_roster)
    feature_schema.__post_init__();config.__post_init__();mode=mode.upper()
    lane=lane.lower()
    if ((lane=="shuffle")!=component_roster.shuffled_labels
            or mode not in {"RAW","CALIBRATED"}):
        raise RecoveryRefusal("policy block lane/mode differs")
    lo,hi=map(int,bounds);C.guard_date(lo);C.guard_date(hi)
    if lo>hi:raise RecoveryRefusal("policy block bounds are reversed")
    outcome_map=_outcomes_by_day(outcomes);spec_map=_specs_by_day(specs)
    teacher_map={row.trading_day:row for row in teachers if lo<=row.trading_day<=hi}
    active_days=tuple(day for day in sorted(teacher_map) if day in outcome_map)
    if not active_days:raise RecoveryRefusal("policy block has no active teacher day")
    root=C.assert_workspace_output(output_root)/name/lane/f"seed_{component_roster.seed}"
    traces=[];paths=[]
    for day in active_days:
        universe=_universe(outcome_map[day])
        component_fold=component_roster.bundle_for_day(day)
        action_fold=action_roster.bundle_for_day(day)
        identity=_trace_identity(day=day,mode=mode,universe=universe,
            component_receipt=component_fold.bundle_receipt_sha256,
            action_receipt=action_fold.bundle_receipt_sha256,
            feature_schema=feature_schema,calibration=calibration,
            admission=admission)
        target=root/mode.lower()/identity/f"{day}.json"
        trace=_load_or_replay_day(day=day,universe=universe,
            specs=spec_map.get(day,()),outcome_rows=outcome_map[day],
            feature_schema=feature_schema,component_fold=component_fold,
            action_fold=action_fold,mode=mode,output_root=root,
            calibration=calibration,admission=admission)
        traces.append(trace);paths.append(str(target))
    sessions=_sessions_for_bounds(specs,(lo,hi))
    ceilings={day:teacher_map[day].exact_objective_cents for day in active_days}
    asset_ceilings=_asset_ceiling_cents(
        teacher_map=teacher_map,outcome_map=outcome_map,active_days=active_days)
    evidence=replay_policy_block(traces,expected_sessions=sessions,
        exact_ceiling_cents_by_day=ceilings,
        exact_ceiling_cents_by_asset=asset_ceilings)
    gate=evaluate_economic_gate(evidence,config=config)
    core={"schema":BLOCK_RESULT_SCHEMA,"name":name,"bounds":(lo,hi),
        "lane":lane,"seed":component_roster.seed,"mode":mode,
        "trace_paths":tuple(paths),
        "trace_receipts":tuple(row.receipt_sha256 for row in traces),
        "expected_sessions":tuple(asdict(row) for row in sessions),
        "exact_ceiling_cents_by_day":{
            str(day):int(value) for day,value in sorted(ceilings.items())},
        "exact_ceiling_cents_by_asset":{
            asset:int(value) for asset,value in sorted(asset_ceilings.items())},
        "component_roster":component_roster.receipt_sha256,
        "action_roster":action_roster.receipt_sha256,
        "calibration":None if calibration is None else calibration.receipt_sha256,
        "admission":None if admission is None else admission.receipt_sha256,
        "gate":gate.receipt_sha256,"h2_open_count":0}
    artifact_core={**core,"gate_detail":asdict(gate)}
    receipt=C.object_sha256(artifact_core)
    manifest=root/f"{mode.lower()}_block.json"
    _strict_json(manifest,{**artifact_core,"receipt_sha256":receipt})
    result=PolicyBlockResult(name,(lo,hi),lane,component_roster.seed,mode,
        tuple(paths),evidence,gate,component_roster.receipt_sha256,
        action_roster.receipt_sha256,
        None if calibration is None else calibration.receipt_sha256,
        None if admission is None else admission.receipt_sha256,
        str(manifest),receipt);result.__post_init__()
    return result


def load_policy_block_result(path:str|Path,*,config:RecoveryConfig
                             )->PolicyBlockResult:
    """Strict-load traces and recompute canonical block economics."""

    config.__post_init__();source,value=_strict_payload(path,BLOCK_RESULT_SCHEMA)
    evidence=_evidence_from_trace_payload(value)
    gate=evaluate_economic_gate(evidence,config=config)
    if (gate.receipt_sha256!=value.get("gate")
            or C.canonical_json_value(asdict(gate))!=value.get("gate_detail")):
        raise RecoveryRefusal("strict block replay gate differs")
    result=PolicyBlockResult(str(value["name"]),tuple(map(int,value["bounds"])),
        str(value["lane"]),int(value["seed"]),str(value["mode"]),
        tuple(map(str,value["trace_paths"])),evidence,gate,
        str(value["component_roster"]),str(value["action_roster"]),
        None if value.get("calibration") is None else str(value["calibration"]),
        None if value.get("admission") is None else str(value["admission"]),
        str(source),str(value["receipt_sha256"]))
    result.__post_init__();return result


def evaluate_training_teacher_capture(*,component_roster:SeedModelRoster,
        action_roster:SeedModelRoster,
        outcomes:Sequence[CachedRecoverySession],
        teachers:Sequence[CachedTeacherDay],
        specs:Sequence[AuthoritativeConfirmationSessionSpec],
        feature_schema:CausalFeatureSchema,config:RecoveryConfig,
        output_root:str|Path)->TrainingTeacherCaptureResult:
    """Measure the branch-2 training fit without promoting in-sample results."""

    _validate_roster_pair(component_roster,action_roster)
    feature_schema.__post_init__();config.__post_init__()
    if component_roster.shuffled_labels or action_roster.shuffled_labels:
        raise RecoveryRefusal("training teacher capture is a real-lane diagnostic")
    candidates=tuple(row for row in action_roster.folds
                     if row.name=="FROZEN_Q3_E8")
    if len(candidates)!=1:
        raise RecoveryRefusal("training capture lacks one final action fold")
    action_fold=candidates[0]
    action_bundle=load_action_model(action_fold.bundle_path)
    if (action_bundle.receipt_sha256!=action_fold.bundle_receipt_sha256
            or action_bundle.objective!=action_roster.objective):
        raise RecoveryRefusal("training capture final action model differs")
    bounds=action_bundle.train_day_range;lo,hi=bounds
    outcome_map=_outcomes_by_day(outcomes);spec_map=_specs_by_day(specs)
    teacher_map={row.trading_day:row for row in teachers
                 if lo<=row.trading_day<=hi}
    active_days=tuple(day for day in sorted(teacher_map) if day in outcome_map)
    if not active_days:
        raise RecoveryRefusal("training capture has no active exact-teacher day")
    root=(C.assert_workspace_output(output_root)/"training_capture"/
          f"seed_{component_roster.seed}")
    traces=[];paths=[]
    for day in active_days:
        universe=_universe(outcome_map[day])
        component_fold=component_roster.bundle_for_day(day)
        identity=_trace_identity(day=day,mode="RAW",universe=universe,
            component_receipt=component_fold.bundle_receipt_sha256,
            action_receipt=action_fold.bundle_receipt_sha256,
            feature_schema=feature_schema,calibration=None,admission=None)
        target=root/"raw"/identity/f"{day}.json"
        trace=_load_or_replay_day(day=day,universe=universe,
            specs=spec_map.get(day,()),outcome_rows=outcome_map[day],
            feature_schema=feature_schema,component_fold=component_fold,
            action_fold=action_fold,mode="RAW",output_root=root)
        traces.append(trace);paths.append(str(target))
    sessions=_sessions_for_bounds(specs,bounds)
    ceilings={day:teacher_map[day].exact_objective_cents for day in active_days}
    asset_ceilings=_asset_ceiling_cents(
        teacher_map=teacher_map,outcome_map=outcome_map,active_days=active_days)
    evidence=replay_policy_block(traces,expected_sessions=sessions,
        exact_ceiling_cents_by_day=ceilings,
        exact_ceiling_cents_by_asset=asset_ceilings)
    capture=float(evidence.evaluation.total_pnl_usd)/evidence.exact_ceiling_usd
    passed=capture>=config.target_ceiling_capture
    core={"schema":TRAINING_CAPTURE_SCHEMA,"seed":component_roster.seed,
        "bounds":bounds,"trace_paths":tuple(paths),
        "trace_receipts":tuple(row.receipt_sha256 for row in traces),
        "expected_sessions":tuple(asdict(row) for row in sessions),
        "exact_ceiling_cents_by_day":{
            str(day):int(value) for day,value in sorted(ceilings.items())},
        "exact_ceiling_cents_by_asset":{
            asset:int(value) for asset,value in sorted(asset_ceilings.items())},
        "evidence":{"total_pnl_usd":evidence.evaluation.total_pnl_usd,
            "exact_ceiling_usd":evidence.exact_ceiling_usd,
            "active_portfolio_days":evidence.active_portfolio_days,
            "evaluation_receipt_sha256":C.object_sha256(
                asdict(evidence.evaluation))},
        "training_teacher_capture":capture,
        "target_capture":config.target_ceiling_capture,"passed":passed,
        "component_roster":component_roster.receipt_sha256,
        "action_roster":action_roster.receipt_sha256,
        "fixed_action_model":action_bundle.receipt_sha256,
        "diagnostic_only":True,"can_satisfy_forward_gate":False,
        "h2_open_count":0}
    receipt=C.object_sha256(core);manifest=root/"training_teacher_capture.json"
    _strict_json(manifest,{**core,"receipt_sha256":receipt})
    result=TrainingTeacherCaptureResult(component_roster.seed,bounds,
        tuple(paths),evidence,capture,config.target_ceiling_capture,passed,
        component_roster.receipt_sha256,action_roster.receipt_sha256,
        action_bundle.receipt_sha256,str(manifest),receipt)
    result.__post_init__();return result


def load_training_teacher_capture(path:str|Path,*,config:RecoveryConfig
                                  )->TrainingTeacherCaptureResult:
    """Strict-load the diagnostic and replay every stored training trace."""

    config.__post_init__();source,value=_strict_payload(
        path,TRAINING_CAPTURE_SCHEMA)
    if (value.get("diagnostic_only") is not True
            or value.get("can_satisfy_forward_gate") is not False):
        raise RecoveryRefusal("training capture changed authority")
    evidence=_evidence_from_trace_payload(value)
    capture=float(evidence.evaluation.total_pnl_usd)/evidence.exact_ceiling_usd
    summary=value["evidence"]
    if (not np.isclose(capture,float(value["training_teacher_capture"]),
                       atol=0,rtol=0)
            or float(summary["total_pnl_usd"])!=evidence.evaluation.total_pnl_usd
            or float(summary["exact_ceiling_usd"])!=evidence.exact_ceiling_usd
            or tuple(map(int,summary["active_portfolio_days"]))
               !=evidence.active_portfolio_days
            or str(summary["evaluation_receipt_sha256"])
               !=C.object_sha256(asdict(evidence.evaluation))):
        raise RecoveryRefusal("strict training capture economics differ")
    passed=capture>=config.target_ceiling_capture
    result=TrainingTeacherCaptureResult(int(value["seed"]),
        tuple(map(int,value["bounds"])),tuple(map(str,value["trace_paths"])),
        evidence,capture,float(value["target_capture"]),passed,
        str(value["component_roster"]),str(value["action_roster"]),
        str(value["fixed_action_model"]),str(source),
        str(value["receipt_sha256"]))
    if passed!=bool(value["passed"]):
        raise RecoveryRefusal("strict training capture status differs")
    result.__post_init__();return result


def _calibration_group(matrix,indices:np.ndarray)->np.ndarray:
    names={name:index for index,name in enumerate(matrix.feature_names)}
    required={"portfolio_entries_used","portfolio_phase_index",
              *REGIME_FEATURE_NAMES}
    if not required<=set(names):
        raise RecoveryRefusal("state calibration features are absent")
    x=np.asarray(matrix.x)
    entries=np.rint(x[indices,names["portfolio_entries_used"]]).astype(np.int64)
    phase=np.asarray([f"{float(value):g}"
        for value in x[indices,names["portfolio_phase_index"]]],str)
    regime_matrix=np.column_stack(tuple(
        x[indices,names[value]] for value in REGIME_FEATURE_NAMES))
    regime=np.asarray(("LOW","MID","HIGH","UNKNOWN"),str)[
        np.argmax(regime_matrix,axis=1)]
    from .tabular_calibration import calibration_group_key
    return calibration_group_key(entries_used=entries,phase=phase,regime=regime)


def save_calibration_bundle(bundle:CalibrationBundle,path:str|Path)->str:
    bundle.__post_init__();core={"schema":CALIBRATION_STORE_SCHEMA,
        "bundle":dict(bundle.to_mapping()),"h2_open_count":0}
    return _strict_json(Path(path),
        {**core,"receipt_sha256":C.object_sha256(core)})


def load_calibration_bundle(path:str|Path)->CalibrationBundle:
    source=Path(path);C.guard_payload(source)
    try:value=json.loads(source.read_text())
    except (OSError,UnicodeError,json.JSONDecodeError) as exc:
        raise RecoveryRefusal("cannot strict-load calibration store") from exc
    core={key:item for key,item in value.items() if key!="receipt_sha256"}
    if (value.get("schema")!=CALIBRATION_STORE_SCHEMA
            or C.object_sha256(core)!=value.get("receipt_sha256")):
        raise RecoveryRefusal("calibration store receipt differs")
    return CalibrationBundle.from_mapping(value["bundle"])


def fit_seed_calibration(*,action_matrix_path:str,
        action_oof_path:str,action_roster:SeedModelRoster,
        chronology:RecoveryChronology,output_path:str|Path,
        state_conditioned:bool=False)->CalibrationBundle:
    action_roster.__post_init__();chronology.__post_init__()
    if action_roster.kind!="ACTION":
        raise RecoveryRefusal("calibration received non-action roster")
    matrix=load_action_matrix(action_matrix_path)
    prediction=ActionPredictionTable.load(action_oof_path)
    if (prediction.source_matrix_receipt_sha256!=matrix.receipt_sha256
            or prediction.model_roster_receipt_sha256!=action_roster.receipt_sha256
            or prediction.chronology_receipt_sha256!=chronology.receipt_sha256):
        raise RecoveryRefusal("calibration OOF/matrix/model lineage differs")
    local=(prediction.day>=chronology.platt[0])&(prediction.day<=chronology.platt[1])
    if not local.any():raise RecoveryRefusal("calibration Q3 bank is empty")
    indices=np.asarray(prediction.matrix_row_index,np.int64)[local]
    if (np.any(indices>=len(matrix.x))
            or not np.array_equal(np.asarray(matrix.opportunity_id,str)[indices],
                                  np.asarray(prediction.opportunity_id,str)[local])
            or not np.array_equal(np.asarray(matrix.day,np.int64)[indices],
                                  np.asarray(prediction.day,np.int64)[local])):
        raise RecoveryRefusal("calibration prediction rows do not bind matrix")
    fold_models=set(np.asarray(prediction.fold_model_receipt_sha256,str)[local])
    if len(fold_models)!=1:
        raise RecoveryRefusal("calibration bank crosses action fold models")
    expected={action_roster.bundle_for_day(int(day)).bundle_receipt_sha256
              for day in np.unique(prediction.day[local])}
    if fold_models!=expected:
        raise RecoveryRefusal("calibration bank action model differs")
    group=_calibration_group(matrix,indices) if state_conditioned else None
    bundle=fit_calibration_bundle(raw_advantage=prediction.raw_advantage_usd[local],
        exact_regret_cents=np.asarray(matrix.regret_cents,np.int64)[indices],
        day=np.asarray(matrix.day,np.int64)[indices],
        weight=np.asarray(matrix.sample_weight,np.float64)[indices],
        chronology_receipt_sha256=chronology.receipt_sha256,
        action_model_receipt_sha256=next(iter(fold_models)),group_key=group)
    target=Path(output_path)
    if target.is_file():
        stored=load_calibration_bundle(target)
        if stored.receipt_sha256!=bundle.receipt_sha256:
            raise RecoveryRefusal("resumed calibration bundle differs")
        return stored
    save_calibration_bundle(bundle,target);stored=load_calibration_bundle(target)
    if stored.receipt_sha256!=bundle.receipt_sha256:
        raise RecoveryRefusal("calibration strict reload differs")
    return stored


def _calibration_rows(*,action_matrix_path:str,action_oof_path:str,
        action_roster:SeedModelRoster,chronology:RecoveryChronology
        )->tuple[object,ActionPredictionTable,np.ndarray,np.ndarray|None]:
    matrix=load_action_matrix(action_matrix_path)
    prediction=ActionPredictionTable.load(action_oof_path)
    if (prediction.source_matrix_receipt_sha256!=matrix.receipt_sha256
            or prediction.model_roster_receipt_sha256!=action_roster.receipt_sha256
            or prediction.chronology_receipt_sha256!=chronology.receipt_sha256):
        raise RecoveryRefusal("threshold calibration lineage differs")
    local=(prediction.day>=chronology.platt[0])&(prediction.day<=chronology.platt[1])
    indices=np.asarray(prediction.matrix_row_index,np.int64)[local]
    if not len(indices):raise RecoveryRefusal("threshold calibration bank is empty")
    return matrix,prediction,local,indices


def _selection_mapping(selection:ThresholdSelection)->Mapping[str,object]:
    return MappingProxyType({"thresholds_usd":selection.thresholds_usd,
        "trials":tuple({"quantile_index":row.quantile_index,
            "threshold_usd":row.threshold_usd,
            "weekly_lcb_usd_per_active_day":row.weekly_lcb_usd_per_active_day,
            "gate":asdict(row.gate)} for row in selection.trials),
        "selected_quantile_index":selection.selected_quantile_index,
        "selected_threshold_usd":selection.selected_threshold_usd,
        "floor_feasible":selection.floor_feasible,
        "calibration_receipt_sha256":selection.calibration_receipt_sha256,
        "receipt_sha256":selection.receipt_sha256})


def _selection_from_mapping(value:Mapping[str,object])->ThresholdSelection:
    trials=tuple(ThresholdTrial(int(row["quantile_index"]),
        float(row["threshold_usd"]),float(row["weekly_lcb_usd_per_active_day"]),
        EconomicGateResult(**row["gate"])) for row in value["trials"])
    result=ThresholdSelection(tuple(map(float,value["thresholds_usd"])),trials,
        int(value["selected_quantile_index"]),
        float(value["selected_threshold_usd"]),bool(value["floor_feasible"]),
        str(value["calibration_receipt_sha256"]),str(value["receipt_sha256"]))
    result.__post_init__();return result


@dataclass(frozen=True,slots=True)
class ThresholdBankResult:
    lane:str
    seed:int
    selection:ThresholdSelection
    admission:AdmissionContract
    selected_evidence:BlockReplayEvidence
    trial_trace_paths:Mapping[int,tuple[str,...]]
    provisional_bank_receipt_sha256:str
    manifest_path:str
    receipt_sha256:str

    def __post_init__(self)->None:
        if (self.lane not in {"real","shuffle"}
                or set(self.trial_trace_paths)!=set(range(21))
                or self.admission.threshold_quantile_index
                   !=self.selection.selected_quantile_index
                or self.admission.action_advantage_threshold_usd
                   !=self.selection.selected_threshold_usd
                or self.admission.threshold_bank_receipt_sha256
                   !=self.selection.receipt_sha256
                or not _sha(self.provisional_bank_receipt_sha256)
                or not _sha(self.receipt_sha256)):
            raise RecoveryRefusal("threshold bank result is malformed")


def select_seed_threshold(*,lane:str,component_roster:SeedModelRoster,
        action_roster:SeedModelRoster,action_matrix_path:str,
        action_oof_path:str,calibration:CalibrationBundle,
        outcomes:Sequence[CachedRecoverySession],teachers:Sequence[CachedTeacherDay],
        specs:Sequence[AuthoritativeConfirmationSessionSpec],
        feature_schema:CausalFeatureSchema,chronology:RecoveryChronology,
        config:RecoveryConfig,output_root:str|Path)->ThresholdBankResult:
    """Evaluate the 21 registered Q4 thresholds with one dense load per day."""

    _validate_roster_pair(component_roster,action_roster)
    matrix,prediction,local,indices=_calibration_rows(
        action_matrix_path=action_matrix_path,action_oof_path=action_oof_path,
        action_roster=action_roster,chronology=chronology)
    if calibration.action_model_receipt_sha256 not in set(np.asarray(
            prediction.fold_model_receipt_sha256,str)[local]):
        raise RecoveryRefusal("threshold bank uses another calibration action model")
    groups=_calibration_group(matrix,indices) if calibration.state_conditioned else None
    lower=calibration.predict_lower(
        prediction.raw_advantage_usd[local],group_key=groups)
    thresholds=tuple(map(float,np.quantile(lower,np.linspace(0,1,21))))
    provisional=C.object_sha256({"schema":"QRE2TABTHRESHOLDBANK1",
        "calibration":calibration.receipt_sha256,"chronology":chronology.receipt_sha256,
        "lower_scores":_array_sha256(lower),"thresholds":thresholds,
        "quantiles":21,"h2_open_count":0})
    admissions=tuple(AdmissionContract(
        config.admission_minimum_current_q20_usd,
        config.admission_maximum_wall_probability,
        config.admission_maximum_adverse_q90_usd,threshold,index,
        calibration.receipt_sha256,provisional)
        for index,threshold in enumerate(thresholds))
    lo,hi=chronology.threshold;outcome_map=_outcomes_by_day(outcomes)
    spec_map=_specs_by_day(specs)
    teacher_map={row.trading_day:row for row in teachers if lo<=row.trading_day<=hi}
    active_days=tuple(day for day in sorted(teacher_map) if day in outcome_map)
    if not active_days:raise RecoveryRefusal("threshold block has no active day")
    root=(C.assert_workspace_output(output_root)/"threshold"/lane/
          f"seed_{component_roster.seed}")
    trace_by_index:dict[int,list[PolicyDayTrace]]={index:[] for index in range(21)}
    paths_by_index:dict[int,list[str]]={index:[] for index in range(21)}
    for day in active_days:
        universe=_universe(outcome_map[day])
        component_fold=component_roster.bundle_for_day(day)
        action_fold=action_roster.bundle_for_day(day)
        targets=[]
        for admission in admissions:
            identity=_trace_identity(day=day,mode="CALIBRATED",universe=universe,
                component_receipt=component_fold.bundle_receipt_sha256,
                action_receipt=action_fold.bundle_receipt_sha256,
                feature_schema=feature_schema,calibration=calibration,
                admission=admission)
            targets.append(root/"calibrated"/identity/f"{day}.json")
        dense=None
        if any(not target.is_file() for target in targets):
            materialized={row.session for row in outcome_map[day]}
            day_specs=tuple(row for row in spec_map.get(day,())
                            if row.session in materialized)
            from .tabular_delayed_corpus import DelayedOutcomeShard
            horizons={DelayedOutcomeShard.load(row.artifact_path).max_delay_sec
                      for row in outcome_map[day]}
            if len(horizons)!=1 or len(day_specs)!=len(outcome_map[day]):
                raise RecoveryRefusal("threshold dense day source roster differs")
            dense=tuple(load_or_materialize_dense_session(
                row,max_delay_sec=int(next(iter(horizons)))) for row in day_specs)
        for index,trace in enumerate(wtwin_load_or_replay_day_multistate(
                day=day,universe=universe,feature_schema=feature_schema,
                component_fold=component_fold,action_fold=action_fold,
                output_root=root,calibration=calibration,
                admissions=admissions,dense_features=dense)):
            trace_by_index[index].append(trace)
            paths_by_index[index].append(str(targets[index]))
    sessions=_sessions_for_bounds(specs,(lo,hi))
    ceilings={day:teacher_map[day].exact_objective_cents for day in active_days}
    asset_ceilings=_asset_ceiling_cents(
        teacher_map=teacher_map,outcome_map=outcome_map,active_days=active_days)
    evidence_by_index={index:replay_policy_block(rows,
        expected_sessions=sessions,exact_ceiling_cents_by_day=ceilings,
        exact_ceiling_cents_by_asset=asset_ceilings)
        for index,rows in trace_by_index.items()}
    evidence_by_threshold={thresholds[index]:evidence
                           for index,evidence in evidence_by_index.items()}
    selection=select_threshold_from_calibration_bank(lower_advantage_usd=lower,
        replay_at_threshold=lambda threshold:evidence_by_threshold[float(threshold)],
        calibration_receipt_sha256=calibration.receipt_sha256,config=config)
    for index,trial in enumerate(selection.trials):
        expected=evaluate_economic_gate(evidence_by_index[index],config=config)
        if trial.gate.receipt_sha256!=expected.receipt_sha256:
            raise RecoveryRefusal("threshold trial/evidence gate differs")
    admission=AdmissionContract(config.admission_minimum_current_q20_usd,
        config.admission_maximum_wall_probability,
        config.admission_maximum_adverse_q90_usd,
        selection.selected_threshold_usd,selection.selected_quantile_index,
        calibration.receipt_sha256,selection.receipt_sha256)
    core={"schema":THRESHOLD_STORE_SCHEMA,"lane":lane,"seed":component_roster.seed,
        "selection":dict(_selection_mapping(selection)),"admission":asdict(admission),
        "trial_trace_paths":{str(key):tuple(value)
                             for key,value in paths_by_index.items()},
        "trial_trace_receipts":{str(key):tuple(row.receipt_sha256 for row in value)
                                for key,value in trace_by_index.items()},
        "expected_sessions":tuple(asdict(row) for row in sessions),
        "exact_ceiling_cents_by_day":{
            str(day):int(value) for day,value in sorted(ceilings.items())},
        "exact_ceiling_cents_by_asset":{
            asset:int(value) for asset,value in sorted(asset_ceilings.items())},
        "provisional_bank_receipt_sha256":provisional,"h2_open_count":0}
    receipt=C.object_sha256(core);artifact={**core,"receipt_sha256":receipt}
    target=root/"threshold_selection.json";_strict_json(target,artifact)
    result=ThresholdBankResult(lane,component_roster.seed,selection,admission,
        evidence_by_index[selection.selected_quantile_index],
        MappingProxyType({key:tuple(value) for key,value in paths_by_index.items()}),
        provisional,str(target),receipt);result.__post_init__();return result


def load_threshold_bank(path:str|Path)->tuple[ThresholdSelection,AdmissionContract]:
    source=Path(path);C.guard_payload(source)
    try:value=json.loads(source.read_text())
    except (OSError,UnicodeError,json.JSONDecodeError) as exc:
        raise RecoveryRefusal("cannot strict-load threshold bank") from exc
    core={key:item for key,item in value.items() if key!="receipt_sha256"}
    if (value.get("schema")!=THRESHOLD_STORE_SCHEMA
            or C.object_sha256(core)!=value.get("receipt_sha256")):
        raise RecoveryRefusal("threshold bank store receipt differs")
    selection=_selection_from_mapping(value["selection"])
    admission=AdmissionContract(**value["admission"]);admission.__post_init__()
    if admission.threshold_bank_receipt_sha256!=selection.receipt_sha256:
        raise RecoveryRefusal("threshold admission/selection receipt differs")
    return selection,admission


def load_threshold_bank_result(path:str|Path,*,config:RecoveryConfig
                               )->ThresholdBankResult:
    """Strict-load all 21 replay trials and reconstruct the selected evidence."""

    config.__post_init__();source,value=_strict_payload(path,THRESHOLD_STORE_SCHEMA)
    selection=_selection_from_mapping(value["selection"])
    admission=AdmissionContract(**value["admission"]);admission.__post_init__()
    if (admission.threshold_bank_receipt_sha256!=selection.receipt_sha256
            or admission.calibration_receipt_sha256
               !=selection.calibration_receipt_sha256):
        raise RecoveryRefusal("threshold bank admission lineage differs")
    sessions=_sessions_from_payload(value["expected_sessions"])
    ceilings={int(day):int(cents) for day,cents in
              dict(value["exact_ceiling_cents_by_day"]).items()}
    asset_ceilings={str(asset):int(cents) for asset,cents in
                    dict(value["exact_ceiling_cents_by_asset"]).items()}
    raw_paths={int(key):tuple(map(str,rows)) for key,rows in
               dict(value["trial_trace_paths"]).items()}
    raw_receipts={int(key):tuple(map(str,rows)) for key,rows in
                  dict(value["trial_trace_receipts"]).items()}
    if set(raw_paths)!=set(range(21)) or set(raw_receipts)!=set(range(21)):
        raise RecoveryRefusal("threshold trial roster differs")
    evidence={}
    for index in range(21):
        traces=tuple(load_policy_day_trace(path_value)
                     for path_value in raw_paths[index])
        if tuple(row.receipt_sha256 for row in traces)!=raw_receipts[index]:
            raise RecoveryRefusal("threshold trial trace receipt differs")
        evidence[index]=replay_policy_block(traces,expected_sessions=sessions,
            exact_ceiling_cents_by_day=ceilings,
            exact_ceiling_cents_by_asset=asset_ceilings)
        gate=evaluate_economic_gate(evidence[index],config=config)
        if gate.receipt_sha256!=selection.trials[index].gate.receipt_sha256:
            raise RecoveryRefusal("threshold trial strict gate differs")
    result=ThresholdBankResult(str(value["lane"]),int(value["seed"]),
        selection,admission,evidence[selection.selected_quantile_index],
        MappingProxyType(raw_paths),str(value["provisional_bank_receipt_sha256"]),
        str(source),str(value["receipt_sha256"]))
    result.__post_init__();return result


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
