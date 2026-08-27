"""Policy-block replay and strict result loading."""

from __future__ import annotations

from dataclasses import asdict,dataclass
from pathlib import Path
from typing import Final,Mapping,Sequence,TypeAlias

from . import common as C
from .confirmation_experiment import AuthoritativeConfirmationSessionSpec
from .contracts import SessionRef
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
from .tabular_live_replay import (
    FrozenRuleDayTrace,PolicyDayTrace,load_policy_day_trace,replay_policy_block,
)


BLOCK_RESULT_SCHEMA:Final="QRE2TABPOLICYBLOCK2"


def _lineage(value:Sequence[Sequence[str]],name:str)->tuple[tuple[str,str],...]:
    rows=tuple((str(row[0]),str(row[1])) for row in value if len(row)==2)
    if (len(rows)!=len(value) or not rows or tuple(sorted(rows))!=rows
            or len({path for path,_sha256 in rows})!=len(rows)
            or any(not path or not _sha(sha256) for path,sha256 in rows)):
        raise RecoveryRefusal(f"frozen policy {name} lineage is malformed")
    return rows


@dataclass(frozen=True,slots=True)
class LearnedPolicyBlockSource:
    seed:int
    mode:str
    component_roster_receipt_sha256:str
    action_roster_receipt_sha256:str
    calibration_receipt_sha256:str|None
    admission_receipt_sha256:str|None

    def __post_init__(self)->None:
        if (self.seed<0 or self.mode not in {"RAW","CALIBRATED"}
                or not _sha(self.component_roster_receipt_sha256)
                or not _sha(self.action_roster_receipt_sha256)
                or (self.mode=="CALIBRATED")
                   !=(self.calibration_receipt_sha256 is not None)
                or (self.mode=="CALIBRATED")
                   !=(self.admission_receipt_sha256 is not None)
                or (self.calibration_receipt_sha256 is not None
                    and not _sha(self.calibration_receipt_sha256))
                or (self.admission_receipt_sha256 is not None
                    and not _sha(self.admission_receipt_sha256))):
            raise RecoveryRefusal("learned policy block source is malformed")


@dataclass(frozen=True,slots=True)
class FrozenRuleBlockSource:
    rule_name:str
    rule_sha256:str
    age_seconds:int
    candidate_receipt_sha256s:tuple[tuple[str,str],...]
    candidate_sha256s:tuple[tuple[str,str],...]
    event_pack_sha256s:tuple[tuple[str,str],...]
    selected_by_cell_sha256:str

    def __post_init__(self)->None:
        _lineage(self.candidate_receipt_sha256s,"candidate receipt")
        _lineage(self.candidate_sha256s,"candidate")
        _lineage(self.event_pack_sha256s,"EventPack")
        if (not self.rule_name or not _sha(self.rule_sha256)
                or self.age_seconds<=0 or not _sha(self.selected_by_cell_sha256)):
            raise RecoveryRefusal("frozen rule block source is malformed")


PolicyBlockSource:TypeAlias=LearnedPolicyBlockSource|FrozenRuleBlockSource


@dataclass(frozen=True,slots=True)
class PolicyBlockResult:
    name:str
    bounds:tuple[int,int]
    lane:str
    trace_paths:tuple[str,...]
    evidence:BlockReplayEvidence
    gate:EconomicGateResult
    source:PolicyBlockSource
    manifest_path:str
    receipt_sha256:str

    def __post_init__(self)->None:
        self.source.__post_init__();self.evidence.__post_init__()
        if (not self.name or self.bounds[0]>self.bounds[1]
                or self.lane not in {"real","shuffle"}
                or not self.trace_paths
                or len(self.trace_paths)!=len(set(self.trace_paths))
                or not _sha(self.gate.receipt_sha256)
                or not _sha(self.receipt_sha256)):
            raise RecoveryRefusal("policy block result is malformed")

    @property
    def seed(self)->int|None:
        return self.source.seed if isinstance(self.source,LearnedPolicyBlockSource) else None

    @property
    def mode(self)->str:
        return (self.source.mode if isinstance(self.source,LearnedPolicyBlockSource)
                else "FROZEN_RULE")

    @property
    def component_roster_receipt_sha256(self)->str|None:
        return (self.source.component_roster_receipt_sha256
                if isinstance(self.source,LearnedPolicyBlockSource) else None)

    @property
    def action_roster_receipt_sha256(self)->str|None:
        return (self.source.action_roster_receipt_sha256
                if isinstance(self.source,LearnedPolicyBlockSource) else None)

    @property
    def calibration_receipt_sha256(self)->str|None:
        return (self.source.calibration_receipt_sha256
                if isinstance(self.source,LearnedPolicyBlockSource) else None)

    @property
    def admission_receipt_sha256(self)->str|None:
        return (self.source.admission_receipt_sha256
                if isinstance(self.source,LearnedPolicyBlockSource) else None)


def _frozen_source_payload(source:FrozenRuleBlockSource)->Mapping[str,object]:
    source.__post_init__()
    return {"kind":"FROZEN_RULE","rule_name":source.rule_name,
        "rule_sha256":source.rule_sha256,"age_seconds":source.age_seconds,
        "candidate_receipt_sha256s":source.candidate_receipt_sha256s,
        "candidate_sha256s":source.candidate_sha256s,
        "event_pack_sha256s":source.event_pack_sha256s,
        "selected_by_cell_sha256":source.selected_by_cell_sha256}


def _source_from_payload(value:Mapping[str,object])->PolicyBlockSource:
    raw=value.get("source")
    if raw is None:
        result=LearnedPolicyBlockSource(
            int(value["seed"]),str(value["mode"]),str(value["component_roster"]),
            str(value["action_roster"]),
            None if value.get("calibration") is None else str(value["calibration"]),
            None if value.get("admission") is None else str(value["admission"]))
        result.__post_init__();return result
    if not isinstance(raw,Mapping) or raw.get("kind")!="FROZEN_RULE":
        raise RecoveryRefusal("policy block source variant is unknown")
    result=FrozenRuleBlockSource(str(raw["rule_name"]),str(raw["rule_sha256"]),
        int(raw["age_seconds"]),
        tuple(tuple(map(str,row)) for row in raw["candidate_receipt_sha256s"]),
        tuple(tuple(map(str,row)) for row in raw["candidate_sha256s"]),
        tuple(tuple(map(str,row)) for row in raw["event_pack_sha256s"]),
        str(raw["selected_by_cell_sha256"]))
    result.__post_init__();return result


def _validate_trace_source(value:Mapping[str,object],source:PolicyBlockSource)->None:
    traces=tuple(load_policy_day_trace(path) for path in value["trace_paths"])
    if isinstance(source,LearnedPolicyBlockSource):
        if any(not isinstance(row,PolicyDayTrace) for row in traces):
            raise RecoveryRefusal("learned block contains a frozen rule trace")
        return
    if any(not isinstance(row,FrozenRuleDayTrace) for row in traces):
        raise RecoveryRefusal("frozen rule block contains a learned trace")
    frozen=tuple(row for row in traces if isinstance(row,FrozenRuleDayTrace))
    if (any(row.rule_name!=source.rule_name
            or row.rule_sha256!=source.rule_sha256
            or row.age_seconds!=source.age_seconds for row in frozen)
            or tuple(sorted(item for row in frozen
                            for item in row.candidate_receipt_sha256s))
               !=source.candidate_receipt_sha256s
            or tuple(sorted(item for row in frozen for item in row.candidate_sha256s))
               !=source.candidate_sha256s
            or tuple(sorted(item for row in frozen for item in row.event_pack_sha256s))
               !=source.event_pack_sha256s):
        raise RecoveryRefusal("frozen rule block and trace lineage differ")


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
    learned=LearnedPolicyBlockSource(component_roster.seed,mode,
        component_roster.receipt_sha256,action_roster.receipt_sha256,
        None if calibration is None else calibration.receipt_sha256,
        None if admission is None else admission.receipt_sha256)
    result=PolicyBlockResult(name,(lo,hi),lane,tuple(paths),evidence,gate,
        learned,str(manifest),receipt);result.__post_init__();return result


def evaluate_frozen_policy_block(*,name:str,bounds:tuple[int,int],lane:str,
        source:FrozenRuleBlockSource,traces:Sequence[FrozenRuleDayTrace],
        trace_paths:Sequence[str|Path],expected_sessions:Sequence[SessionRef],
        exact_ceiling_cents_by_day:Mapping[int,int],
        exact_ceiling_cents_by_asset:Mapping[str,int],config:RecoveryConfig,
        output_path:str|Path)->PolicyBlockResult:
    if not isinstance(source,FrozenRuleBlockSource):
        raise RecoveryRefusal("frozen policy block lacks frozen source lineage")
    source.__post_init__();config.__post_init__();lo,hi=map(int,bounds)
    C.guard_date(lo);C.guard_date(hi);lane=lane.lower()
    paths=tuple(map(str,trace_paths));rows=tuple(traces);sessions=tuple(expected_sessions)
    if (lo>hi or lane not in {"real","shuffle"} or lane!="real"
            or not rows or len(rows)!=len(paths)
            or any(not isinstance(row,FrozenRuleDayTrace) for row in rows)
            or tuple(row.trading_day for row in rows)
               !=tuple(sorted({row.trading_day for row in rows}))):
        raise RecoveryRefusal("frozen policy block request is malformed")
    loaded=tuple(load_policy_day_trace(path) for path in paths)
    if (any(not isinstance(row,FrozenRuleDayTrace) for row in loaded)
            or tuple(row.receipt_sha256 for row in loaded)
               !=tuple(row.receipt_sha256 for row in rows)):
        raise RecoveryRefusal("frozen policy trace strict reload differs")
    evidence=replay_policy_block(rows,expected_sessions=sessions,
        exact_ceiling_cents_by_day=exact_ceiling_cents_by_day,
        exact_ceiling_cents_by_asset=exact_ceiling_cents_by_asset)
    gate=evaluate_economic_gate(evidence,config=config)
    core={"schema":BLOCK_RESULT_SCHEMA,"name":name,"bounds":(lo,hi),
        "lane":lane,"source":_frozen_source_payload(source),
        "trace_paths":paths,
        "trace_receipts":tuple(row.receipt_sha256 for row in rows),
        "expected_sessions":tuple(asdict(row) for row in sessions),
        "exact_ceiling_cents_by_day":{
            str(day):int(value) for day,value in sorted(
                exact_ceiling_cents_by_day.items())},
        "exact_ceiling_cents_by_asset":{
            asset:int(value) for asset,value in sorted(
                exact_ceiling_cents_by_asset.items())},
        "gate":gate.receipt_sha256,"h2_open_count":0}
    artifact_core={**core,"gate_detail":asdict(gate)}
    receipt=C.object_sha256(artifact_core);manifest=Path(output_path)
    _strict_json(manifest,{**artifact_core,"receipt_sha256":receipt})
    result=PolicyBlockResult(name,(lo,hi),lane,paths,evidence,gate,source,
        str(manifest),receipt);result.__post_init__();return result


def load_policy_block_result(path:str|Path,*,config:RecoveryConfig
                             )->PolicyBlockResult:
    """Strict-load traces and recompute canonical block economics."""

    config.__post_init__();source_path,value=_strict_payload(path,BLOCK_RESULT_SCHEMA)
    source=_source_from_payload(value);_validate_trace_source(value,source)
    evidence=_evidence_from_trace_payload(value)
    gate=evaluate_economic_gate(evidence,config=config)
    current=(gate.receipt_sha256==value.get("gate")
             and C.canonical_json_value(asdict(gate))==value.get("gate_detail"))
    if not current:
        raise RecoveryRefusal("strict block replay gate differs")
    result=PolicyBlockResult(str(value["name"]),tuple(map(int,value["bounds"])),
        str(value["lane"]),tuple(map(str,value["trace_paths"])),evidence,gate,
        source,str(source_path),str(value["receipt_sha256"]))
    result.__post_init__();return result


__all__=["BLOCK_RESULT_SCHEMA","FrozenRuleBlockSource",
         "LearnedPolicyBlockSource","PolicyBlockResult","PolicyBlockSource",
         "evaluate_frozen_policy_block","evaluate_policy_block",
         "load_policy_block_result"]
