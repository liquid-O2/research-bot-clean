"""Training teacher-capture evaluation and strict loading."""

from __future__ import annotations

from dataclasses import asdict,dataclass
from pathlib import Path
from typing import Final,Sequence

import numpy as np

from . import common as C
from .confirmation_experiment import AuthoritativeConfirmationSessionSpec
from .tabular_calibration import BlockReplayEvidence
from .tabular_campaign import CachedRecoverySession,CachedTeacherDay
from .tabular_experiment import SeedModelRoster
from .tabular_live_replay import replay_policy_block
from .tabular_model_io import load_action_model
from .tabular_recovery_contracts import (
    CausalFeatureSchema,RecoveryConfig,RecoveryRefusal,
)
from .tabular_evaluation_io import (
    _asset_ceiling_cents,_evidence_from_trace_payload,_load_or_replay_day,
    _outcomes_by_day,_sessions_for_bounds,_sha,_specs_by_day,_strict_json,
    _strict_payload,_trace_identity,_universe,_validate_roster_pair,
)

TRAINING_CAPTURE_SCHEMA:Final="QRE2TABTRAININGCAPTURE2"


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
