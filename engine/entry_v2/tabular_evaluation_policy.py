"""Policy-block replay and strict result loading."""

from __future__ import annotations

from dataclasses import asdict,dataclass
from pathlib import Path
from typing import Final,Sequence

from . import common as C
from .confirmation_experiment import AuthoritativeConfirmationSessionSpec
from .tabular_calibration import (
    AdmissionContract,BlockReplayEvidence,CalibrationBundle,evaluate_economic_gate,
)
from .tabular_campaign import CachedRecoverySession,CachedTeacherDay
from .tabular_experiment import SeedModelRoster
from .tabular_recovery_contracts import (
    CausalFeatureSchema,EconomicGateResult,RecoveryConfig,RecoveryRefusal,
)
from .tabular_evaluation_io import (
    _asset_ceiling_cents,_evidence_from_trace_payload,_load_or_replay_day,
    _outcomes_by_day,_sessions_for_bounds,_sha,_specs_by_day,_strict_json,
    _strict_payload,_trace_identity,_universe,_validate_roster_pair,
)
from .tabular_live_replay import replay_policy_block

BLOCK_RESULT_SCHEMA:Final="QRE2TABPOLICYBLOCK2"


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
