"""Shared strict I/O and replay helpers for tabular evaluation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Mapping,Sequence

import numpy as np

from . import common as C
from .confirmation_experiment import AuthoritativeConfirmationSessionSpec
from .contracts import SessionRef
from .exact_delayed_teacher import ExactDelayedTeacherDay
from .exact_teacher_types import DayOptionUniverse
from .tabular_calibration import AdmissionContract,BlockReplayEvidence,CalibrationBundle
from .tabular_campaign import (
    CachedRecoverySession,CachedTeacherDay,load_or_materialize_dense_session,
)
from .tabular_experiment import SeedModelRoster
from .tabular_live_replay import (
    PolicyDayTrace,load_policy_day_trace,replay_policy_block,replay_policy_day,
    save_policy_day_trace,
)
from .tabular_model_io import load_action_model,load_component_model
from .tabular_recovery_contracts import (
    CausalFeatureSchema,RecoveryRefusal,
)


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
