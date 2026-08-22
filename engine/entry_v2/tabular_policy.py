"""Causal every-second ENTER/DEFER/PASS policy and strict bundle artifact."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
from types import MappingProxyType
from typing import Any, Final, Mapping, Sequence

import numpy as np

from . import common as C
from .tabular_atomic import atomic_replace_directory
from .contracts import EntryScore
from .tabular_action_features import build_action_feature_matrix, qrf4_regime_matrix
from .tabular_calibration import (
    AdmissionContract, CalibrationBundle,calibration_group_key,
)
from .tabular_model_io import (
    load_action_model,load_component_model,predict_action_regret,
)
from .tabular_recovery_contracts import (
    CausalFeatureSchema, ComponentPredictions, DecisionAction,
    OpenPositionState, PolicyDecision, PortfolioDecisionState,
    RecoveryChronology, RecoveryConfig, RecoveryRefusal, recovery_lane_registry,
)


POLICY_BUNDLE_SCHEMA: Final = "QRE2TABULARPOLICYBUNDLE3"
CHECKPOINT_SCHEMA: Final = "QRE2TABULARPOLICYCHECKPOINT1"


def _sha(value: object)->bool:
    return isinstance(value,str) and len(value)==64 and all(c in "0123456789abcdef" for c in value)


def _model_backend(model:Any)->str:
    if getattr(model,"day_routed",False):return "CAUSAL_EXPERTS"
    backend=getattr(model,"backend",None)
    return str(backend) if backend is not None else "CATBOOST"


def _action_index(regrets:Sequence[float])->DecisionAction:
    enter,defer,passed=map(float,regrets)
    # Exact ties preserve the watch before retiring it; ENTER must establish
    # a real advantage through the calibrated threshold below.
    if enter<min(defer,passed): return DecisionAction.ENTER
    if defer<=passed: return DecisionAction.DEFER
    return DecisionAction.PASS


def decide(state:PortfolioDecisionState,admission:AdmissionContract)->PolicyDecision:
    """The single production decision interface required by the plan."""
    state.__post_init__();admission.__post_init__();component=state.components
    if state.asset_occupied:
        return PolicyDecision(DecisionAction.DEFER,component.incremental_dollars_usd,
                              component.lower_action_advantage_usd,"ASSET_OCCUPIED")
    if state.entries_used>=C.MAX_ENTRIES_PORTFOLIO_DAY:
        return PolicyDecision(DecisionAction.PASS,component.incremental_dollars_usd,
                              component.lower_action_advantage_usd,"PORTFOLIO_CAP_EXHAUSTED")
    learned=_action_index((component.enter_regret,component.defer_regret,
                           component.pass_regret))
    if learned is DecisionAction.PASS:
        return PolicyDecision(learned,component.incremental_dollars_usd,
                              component.lower_action_advantage_usd,"MINIMUM_REGRET_PASS")
    if learned is DecisionAction.DEFER:
        return PolicyDecision(learned,component.incremental_dollars_usd,
                              component.lower_action_advantage_usd,"MINIMUM_REGRET_DEFER")
    failures=[]
    if component.lower_action_advantage_usd<admission.action_advantage_threshold_usd:
        failures.append("ADVANTAGE")
    if component.current_q20_usd<admission.minimum_current_q20_usd:
        failures.append("CURRENT_Q20")
    if component.wall_probability>admission.maximum_wall_probability:
        failures.append("WALL")
    if component.mae_q90_usd>admission.maximum_adverse_q90_usd:
        failures.append("ADVERSE")
    if failures:
        return PolicyDecision(DecisionAction.DEFER,component.incremental_dollars_usd,
                              component.lower_action_advantage_usd,
                              "ADMISSION_"+"_".join(failures))
    return PolicyDecision(DecisionAction.ENTER,component.incremental_dollars_usd,
                          component.lower_action_advantage_usd,"ADMITTED")


def decide_margin(state:PortfolioDecisionState,admission:AdmissionContract)->PolicyDecision:
    """A1 diagnosis rule (design/A1_MARGIN_RULE_SPEC.md item 1).

    The argmin pre-stage of ``decide`` is REMOVED.  The decision score is the
    predicted dollars by which entering beats deferring, and it takes the
    threshold slot the argmin stage used to guard, so MARGIN_BELOW_THRESHOLD
    replaces the MINIMUM_REGRET_* reasons and the three risk gates keep their
    ADMISSION_ names.  Never a chain default: only ``policy_mode="MARGIN"``
    reaches this function.
    """

    state.__post_init__();admission.__post_init__();component=state.components
    margin=float(component.defer_regret-component.enter_regret)
    if state.asset_occupied:
        return PolicyDecision(DecisionAction.DEFER,margin,
                              component.lower_action_advantage_usd,"ASSET_OCCUPIED")
    if state.entries_used>=C.MAX_ENTRIES_PORTFOLIO_DAY:
        return PolicyDecision(DecisionAction.PASS,margin,
                              component.lower_action_advantage_usd,
                              "PORTFOLIO_CAP_EXHAUSTED")
    if margin<admission.action_advantage_threshold_usd:
        return PolicyDecision(DecisionAction.DEFER,margin,
                              component.lower_action_advantage_usd,
                              "MARGIN_BELOW_THRESHOLD")
    failures=[]
    if component.current_q20_usd<admission.minimum_current_q20_usd:
        failures.append("CURRENT_Q20")
    if component.wall_probability>admission.maximum_wall_probability:
        failures.append("WALL")
    if component.mae_q90_usd>admission.maximum_adverse_q90_usd:
        failures.append("ADVERSE")
    if failures:
        return PolicyDecision(DecisionAction.DEFER,margin,
                              component.lower_action_advantage_usd,
                              "ADMISSION_"+"_".join(failures))
    return PolicyDecision(DecisionAction.ENTER,margin,
                          component.lower_action_advantage_usd,"ADMITTED")


@dataclass(frozen=True,slots=True)
class CausalSnapshotInput:
    candidate_id:str
    series_id:str
    asset:str
    trading_day:int
    side:int
    snapshot_ts_ns:int
    watch_expiry_ts_ns:int
    feature_names:tuple[str,...]
    causal_features:tuple[float,...]
    entries_used:int
    open_positions:tuple[OpenPositionState,...]
    active_watches_by_asset_side:tuple[int,int,int,int,int,int]
    phase:str

    def __post_init__(self)->None:
        # Reuse the hardened public state validator with finite placeholder
        # predictions; no future/outcome field can be represented here.
        placeholder=ComponentPredictions(0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0)
        PortfolioDecisionState(self.candidate_id,self.series_id,self.asset,
            self.trading_day,self.side,self.snapshot_ts_ns,self.watch_expiry_ts_ns,
            self.feature_names,self.causal_features,placeholder,self.entries_used,
            self.open_positions,self.active_watches_by_asset_side,self.phase,"UNKNOWN")


class TabularInferencePipeline:
    def __init__(self,*,component:Any,action:Any,
                 calibration:CalibrationBundle,feature_schema:CausalFeatureSchema)->None:
        if (component.feature_names!=feature_schema.names
                or calibration.runtime_action_model_sha256!=action.receipt_sha256):
            raise RecoveryRefusal("inference model/schema/calibration receipts differ")
        self.component=component;self.action=action
        self.calibration=calibration;self.feature_schema=feature_schema

    def score(self,snapshot:CausalSnapshotInput)->PortfolioDecisionState:
        snapshot.__post_init__()
        if snapshot.feature_names!=self.feature_schema.names:
            raise RecoveryRefusal("runtime causal feature schema differs")
        causal=np.asarray(snapshot.causal_features,np.float32).reshape((1,-1))
        component=self.component.predict(causal).values
        open_until=np.full((1,len(C.ASSETS)),-1,np.int64)
        for position in snapshot.open_positions:
            open_until[0,C.ASSET_INDEX[position.asset]]=position.open_until_ts_ns
        action_names,action_x=build_action_feature_matrix(
            causal_feature_names=snapshot.feature_names,causal_matrix=causal,
            component_predictions=component,asset=np.asarray([snapshot.asset]),
            snapshot_ts_ns=np.asarray([snapshot.snapshot_ts_ns],np.int64),
            entries_used=np.asarray([snapshot.entries_used],np.int8),
            open_until_ts_ns=open_until,
            active_watches_by_asset_side=np.asarray(
                [snapshot.active_watches_by_asset_side],np.int16),
            phase=np.asarray([snapshot.phase]))
        if action_names!=self.action.feature_names:
            raise RecoveryRefusal("runtime action feature schema differs from fit")
        regrets=predict_action_regret(self.action,action_x,
                                      trading_day=snapshot.trading_day)[0]
        raw_advantage=float(min(regrets[1],regrets[2])-regrets[0])
        regime_vector=qrf4_regime_matrix(snapshot.feature_names,causal)[0]
        regime=("LOW","MID","HIGH","UNKNOWN")[int(np.argmax(regime_vector))]
        group=(calibration_group_key(entries_used=[snapshot.entries_used],
            phase=[snapshot.phase],regime=[regime])
            if self.calibration.state_conditioned else None)
        mapped=float(self.calibration.predict_dollars(
            np.asarray([raw_advantage]),group_key=group)[0])
        lower=float(self.calibration.predict_lower(
            np.asarray([raw_advantage]),group_key=group)[0])
        enter_probability=float(self.calibration.enter_optimal_platt.predict(
            np.asarray([raw_advantage]))[0])
        row=component[0]
        predictions=ComponentPredictions(
            current_q20_usd=float(row[0]),current_q50_usd=float(row[1]),
            current_q80_usd=float(row[2]),continuation_q20_usd=float(row[3]),
            continuation_q50_usd=float(row[4]),continuation_q80_usd=float(row[5]),
            wall_probability=float(row[6]),enter_probability=enter_probability,
            mae_q90_usd=float(row[7]),
            occupancy_q50_sec=float(row[8]),occupancy_q90_sec=float(row[9]),
            enter_regret=float(regrets[0]),defer_regret=float(regrets[1]),
            pass_regret=float(regrets[2]),lower_action_advantage_usd=lower,
            incremental_dollars_usd=mapped)
        return PortfolioDecisionState(
            snapshot.candidate_id,snapshot.series_id,snapshot.asset,
            snapshot.trading_day,snapshot.side,snapshot.snapshot_ts_ns,
            snapshot.watch_expiry_ts_ns,snapshot.feature_names,
            snapshot.causal_features,predictions,snapshot.entries_used,
            snapshot.open_positions,snapshot.active_watches_by_asset_side,
            snapshot.phase,regime)


@dataclass(frozen=True,slots=True)
class RankedDecision:
    state:PortfolioDecisionState
    decision:PolicyDecision


def decide_simultaneous(states:Sequence[PortfolioDecisionState],
                        admission:AdmissionContract)->tuple[RankedDecision,...]:
    rows=tuple(states)
    if not rows:return ()
    timestamps={row.snapshot_ts_ns for row in rows};days={row.trading_day for row in rows}
    if (len(timestamps)!=1 or len(days)!=1
            or len({row.candidate_id for row in rows})!=len(rows)
            or len({row.entries_used for row in rows})!=1
            or any(row.open_positions!=rows[0].open_positions for row in rows)
            or any(row.active_watches_by_asset_side
                   !=rows[0].active_watches_by_asset_side for row in rows)):
        raise RecoveryRefusal("simultaneous decision batch crosses clock/day")
    provisional=[RankedDecision(row,decide(row,admission)) for row in rows]
    enters=[row for row in provisional if row.decision.action is DecisionAction.ENTER]
    others=[row for row in provisional if row.decision.action is not DecisionAction.ENTER]
    # One free seat per asset at a timestamp.  Incremental dollars are the
    # portfolio priority; candidate id is the canonical exact tie-break.
    selected=[]
    for asset in C.ASSETS:
        local=[row for row in enters if row.state.asset==asset]
        if local:
            selected.append(min(local,key=lambda row:(
                -row.decision.incremental_dollars_usd,row.state.candidate_id)))
    capacity=max(0,C.MAX_ENTRIES_PORTFOLIO_DAY-rows[0].entries_used)
    selected=sorted(selected,key=lambda row:(-row.decision.incremental_dollars_usd,
                                              row.state.candidate_id))[:capacity]
    selected_ids={id(row) for row in selected}
    for row in enters:
        if id(row) not in selected_ids:
            others.append(RankedDecision(row.state,PolicyDecision(
                DecisionAction.DEFER,row.decision.incremental_dollars_usd,
                row.decision.lower_action_advantage_usd,
                "SIMULTANEOUS_PORTFOLIO_RANK")))
    return tuple(sorted((*selected,*others),key=lambda row:row.state.candidate_id))


def decision_entry_score(state:PortfolioDecisionState,decision:PolicyDecision,
                         *,model_hash:str)->EntryScore:
    if not _sha(model_hash):raise RecoveryRefusal("EntryScore model hash is malformed")
    component=state.components
    probability=component.enter_probability
    return EntryScore(candidate_id=state.candidate_id,asset=state.asset,
        decision_ts_ns=state.snapshot_ts_ns,model_hash=model_hash,
        priority_score=component.incremental_dollars_usd,
        take_probability=probability,expected_pnl_usd=component.current_q50_usd,
        expected_pnl_lower_usd=component.current_q20_usd,
        top3_probability=probability,mae_p90_usd=component.mae_q90_usd,
        wall_probability=component.wall_probability,
        enter=decision.action is DecisionAction.ENTER)


@dataclass(frozen=True,slots=True)
class PolicyRestartProbe:
    snapshot:CausalSnapshotInput
    expected_component:ComponentPredictions
    expected_decision:PolicyDecision
    receipt_sha256:str

    def __post_init__(self)->None:
        self.snapshot.__post_init__();self.expected_component.__post_init__()
        self.expected_decision.__post_init__()
        core={"schema":"QRE2TABRESTARTPROBE1","snapshot":asdict(self.snapshot),
              "expected_component":asdict(self.expected_component),
              "expected_decision":asdict(self.expected_decision)}
        if C.object_sha256(core)!=self.receipt_sha256:
            raise RecoveryRefusal("restart probe receipt differs")


class TabularPolicyBundle:
    def __init__(self,*,config:RecoveryConfig,chronology:RecoveryChronology,
            feature_schema:CausalFeatureSchema,component:Any,
            action:Any,calibration:CalibrationBundle,
            admission:AdmissionContract,teacher_manifest_sha256:str,
            restart_probe:PolicyRestartProbe,receipt_sha256:str)->None:
        config.__post_init__();chronology.__post_init__();feature_schema.__post_init__()
        if (component.config.receipt_sha256!=config.receipt_sha256
                or action.config.receipt_sha256!=config.receipt_sha256
                or component.feature_names!=feature_schema.names
                or calibration.runtime_action_model_sha256!=action.receipt_sha256
                or admission.calibration_receipt_sha256!=calibration.receipt_sha256
                or not component.refit_all_pre_h2
                or not action.refit_all_pre_h2
                or component.train_day_range[1]!=action.train_day_range[1]
                or component.train_day_range[1]>=C.HOLDOUT_START_D8
                or not _sha(teacher_manifest_sha256) or not _sha(receipt_sha256)):
            raise RecoveryRefusal("tabular policy bundle contracts differ")
        self.config=config;self.chronology=chronology;self.feature_schema=feature_schema
        self.component=component;self.action=action;self.calibration=calibration
        self.admission=admission;self.teacher_manifest_sha256=teacher_manifest_sha256
        self.restart_probe=restart_probe;self.receipt_sha256=receipt_sha256
        self.pipeline=TabularInferencePipeline(component=component,action=action,
            calibration=calibration,feature_schema=feature_schema)

    def score_and_decide(self,snapshot:CausalSnapshotInput)->RankedDecision:
        state=self.pipeline.score(snapshot);return RankedDecision(state,decide(state,self.admission))

    def verify_restart(self)->str:
        actual=self.score_and_decide(self.restart_probe.snapshot)
        if (asdict(actual.state.components)!=asdict(self.restart_probe.expected_component)
                or asdict(actual.decision)!=asdict(self.restart_probe.expected_decision)):
            raise RecoveryRefusal("strict restart predictions/decision differ")
        return self.restart_probe.receipt_sha256

    def _core(self)->Mapping[str,object]:
        return {"schema":POLICY_BUNDLE_SCHEMA,"config_sha256":self.config.receipt_sha256,
                "chronology_sha256":self.chronology.receipt_sha256,
                "feature_schema_sha256":self.feature_schema.receipt_sha256,
                "component_model_sha256":self.component.receipt_sha256,
                "action_model_sha256":self.action.receipt_sha256,
                "component_backend":_model_backend(self.component),
                "action_backend":_model_backend(self.action),
                "calibration_sha256":self.calibration.receipt_sha256,
                "admission":asdict(self.admission),
                "teacher_manifest_sha256":self.teacher_manifest_sha256,
                "restart_probe_sha256":self.restart_probe.receipt_sha256,
                "component_all_pre_h2_refit":self.component.refit_all_pre_h2,
                "action_all_pre_h2_refit":self.action.refit_all_pre_h2,
                "lane_registry_sha256":recovery_lane_registry()["receipt_sha256"],
                "actions":("ENTER","DEFER","PASS"),"one_mini":True,
                "closed_interval_k1":True,"portfolio_cap":12,
                "every_receive_second":True,"h2_open_count":0}

    def save(self,path:os.PathLike[str]|str)->str:
        if self.verify_restart()!=self.restart_probe.receipt_sha256:
            raise RecoveryRefusal("restart probe did not verify before publication")
        core=dict(self._core())
        if C.object_sha256(core)!=self.receipt_sha256:
            raise RecoveryRefusal("policy bundle identity differs before save")
        target=C.assert_workspace_output(path)
        if target.exists():raise RecoveryRefusal("policy bundle target already exists")
        target.parent.mkdir(parents=True,exist_ok=True)
        stage=Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp.",dir=target.parent))
        try:
            self.component.save(stage/"component")
            self.action.save(stage/"action")
            detail={"config":asdict(self.config),"chronology":asdict(self.chronology),
                    "feature_schema":asdict(self.feature_schema),
                    "calibration":dict(self.calibration.to_mapping()),
                    "admission":asdict(self.admission),
                    "restart_probe":asdict(self.restart_probe),
                    "component_manifest_sha256":C.file_sha256(stage/"component"/"manifest.json"),
                    "action_manifest_sha256":C.file_sha256(stage/"action"/"manifest.json")}
            C.atomic_json(stage/"detail.json",detail)
            C.atomic_json(stage/"manifest.json",{**core,"receipt_sha256":self.receipt_sha256,
                          "detail_sha256":C.file_sha256(stage/"detail.json")})
            atomic_replace_directory(stage,target)
        except Exception:
            shutil.rmtree(stage,ignore_errors=True);raise
        return C.file_sha256(target/"manifest.json")

    @classmethod
    def load(cls,path:os.PathLike[str]|str)->"TabularPolicyBundle":
        source=Path(path).resolve();C.guard_payload(source)
        try:
            manifest=json.loads((source/"manifest.json").read_text())
            detail_path=source/"detail.json"
            if C.file_sha256(detail_path)!=manifest.get("detail_sha256"):
                raise RecoveryRefusal("policy detail hash differs")
            detail=json.loads(detail_path.read_text())
        except (OSError,UnicodeError,json.JSONDecodeError) as exc:
            raise RecoveryRefusal("cannot strict-load policy bundle") from exc
        if manifest.get("schema")!=POLICY_BUNDLE_SCHEMA:
            raise RecoveryRefusal("policy bundle schema differs")
        config_value=dict(detail["config"])
        config_value["real_seeds"]=tuple(config_value["real_seeds"])
        config_value["shuffle_seeds"]=tuple(config_value["shuffle_seeds"])
        config=RecoveryConfig(**config_value)
        chronology_value=dict(detail["chronology"])
        chronology_value["burned"]=tuple(chronology_value["burned"])
        chronology_value["oof_blocks"]=tuple(
            tuple(value) for value in chronology_value["oof_blocks"])
        chronology_value["rehearsals"]=tuple(
            (str(value[0]), *(tuple(window) for window in value[1:]))
            for value in chronology_value["rehearsals"])
        for key in ("component_folds","action_folds"):
            chronology_value[key]=tuple(tuple(value)
                                        for value in chronology_value[key])
        for key in ("platt","threshold","forward"):
            chronology_value[key]=tuple(chronology_value[key])
        chronology=RecoveryChronology(**chronology_value)
        schema_value=dict(detail["feature_schema"])
        schema_value["names"]=tuple(schema_value["names"])
        schema_value["removed_constants"]=tuple(schema_value["removed_constants"])
        schema_value["removed_duplicates"]=tuple(
            tuple(value) for value in schema_value["removed_duplicates"])
        schema_value["removed_proven_leaks"]=tuple(
            schema_value["removed_proven_leaks"])
        schema_value["relation_source_features"]=tuple(
            schema_value.get("relation_source_features",()))
        feature_schema=CausalFeatureSchema(**schema_value)
        calibration=CalibrationBundle.from_mapping(detail["calibration"])
        admission=AdmissionContract(**detail["admission"])
        probe_value=detail["restart_probe"]
        snapshot_value=dict(probe_value["snapshot"])
        snapshot_value["feature_names"]=tuple(snapshot_value["feature_names"])
        snapshot_value["causal_features"]=tuple(snapshot_value["causal_features"])
        snapshot_value["active_watches_by_asset_side"]=tuple(
            snapshot_value["active_watches_by_asset_side"])
        snapshot_value["open_positions"]=tuple(
            OpenPositionState(**value) for value in snapshot_value["open_positions"])
        probe=PolicyRestartProbe(CausalSnapshotInput(**snapshot_value),
            ComponentPredictions(**probe_value["expected_component"]),
            PolicyDecision(**probe_value["expected_decision"]),
            probe_value["receipt_sha256"])
        if (C.file_sha256(source/"component"/"manifest.json")
                !=detail["component_manifest_sha256"]
                or C.file_sha256(source/"action"/"manifest.json")
                !=detail["action_manifest_sha256"]):
            raise RecoveryRefusal("nested model manifest hash differs")
        component=load_component_model(source/"component")
        action=load_action_model(source/"action")
        result=cls(config=config,chronology=chronology,feature_schema=feature_schema,
            component=component,action=action,calibration=calibration,
            admission=admission,teacher_manifest_sha256=manifest["teacher_manifest_sha256"],
            restart_probe=probe,receipt_sha256=manifest["receipt_sha256"])
        core=dict(result._core())
        stored_core=C.canonical_json_value(core)
        if (C.object_sha256(core)!=result.receipt_sha256
                or any(manifest.get(key)!=value
                       for key,value in stored_core.items())):
            raise RecoveryRefusal("strict-loaded policy identity differs")
        result.verify_restart();return result


def create_policy_bundle(*,config:RecoveryConfig,chronology:RecoveryChronology,
        feature_schema:CausalFeatureSchema,component:Any,
        action:Any,calibration:CalibrationBundle,
        admission:AdmissionContract,teacher_manifest_sha256:str,
        restart_snapshot:CausalSnapshotInput)->TabularPolicyBundle:
    pipeline=TabularInferencePipeline(component=component,action=action,
        calibration=calibration,feature_schema=feature_schema)
    state=pipeline.score(restart_snapshot);decision_row=decide(state,admission)
    probe_core={"schema":"QRE2TABRESTARTPROBE1","snapshot":asdict(restart_snapshot),
                "expected_component":asdict(state.components),
                "expected_decision":asdict(decision_row)}
    probe=PolicyRestartProbe(restart_snapshot,state.components,decision_row,
                             C.object_sha256(probe_core))
    temporary=TabularPolicyBundle(config=config,chronology=chronology,
        feature_schema=feature_schema,component=component,action=action,
        calibration=calibration,admission=admission,
        teacher_manifest_sha256=teacher_manifest_sha256,restart_probe=probe,
        receipt_sha256="0"*64)
    receipt=C.object_sha256(temporary._core())
    return TabularPolicyBundle(config=config,chronology=chronology,
        feature_schema=feature_schema,component=component,action=action,
        calibration=calibration,admission=admission,
        teacher_manifest_sha256=teacher_manifest_sha256,restart_probe=probe,
        receipt_sha256=receipt)


@dataclass(frozen=True,slots=True)
class RuntimeCheckpoint:
    trading_day:int
    timestamp_ns:int
    entries_used:int
    live_watch_series:tuple[str,...]
    passed_series:tuple[str,...]
    entered_series:tuple[str,...]
    open_positions:tuple[OpenPositionState,...]
    policy_bundle_sha256:str
    receipt_sha256:str

    def __post_init__(self)->None:
        C.guard_date(self.trading_day)
        core={"schema":CHECKPOINT_SCHEMA,"trading_day":self.trading_day,
              "timestamp_ns":self.timestamp_ns,"entries_used":self.entries_used,
              "live_watch_series":self.live_watch_series,
              "passed_series":self.passed_series,"entered_series":self.entered_series,
              "open_positions":tuple(asdict(row) for row in self.open_positions),
              "policy_bundle_sha256":self.policy_bundle_sha256}
        if (self.timestamp_ns<=0 or not 0<=self.entries_used<=12
                or any(tuple(sorted(set(values)))!=values for values in (
                    self.live_watch_series,self.passed_series,self.entered_series))
                or set(self.live_watch_series)&(set(self.passed_series)|set(self.entered_series))
                or not _sha(self.policy_bundle_sha256)
                or C.object_sha256(core)!=self.receipt_sha256):
            raise RecoveryRefusal("runtime checkpoint is malformed")

    def save(self,path:os.PathLike[str]|str)->str:
        self.__post_init__();target=C.assert_workspace_output(path)
        C.atomic_json(target,{"schema":CHECKPOINT_SCHEMA,**asdict(self)})
        return C.file_sha256(target)

    @classmethod
    def load(cls,path:os.PathLike[str]|str,*,expected_bundle_sha256:str)->"RuntimeCheckpoint":
        source=Path(path);C.guard_payload(source)
        try:value=json.loads(source.read_text())
        except (OSError,UnicodeError,json.JSONDecodeError) as exc:
            raise RecoveryRefusal("cannot strict-load runtime checkpoint") from exc
        if value.pop("schema",None)!=CHECKPOINT_SCHEMA:
            raise RecoveryRefusal("runtime checkpoint schema differs")
        value["open_positions"]=tuple(OpenPositionState(**row)
                                      for row in value["open_positions"])
        for key in ("live_watch_series","passed_series","entered_series"):
            value[key]=tuple(value[key])
        result=cls(**value);result.__post_init__()
        if result.policy_bundle_sha256!=expected_bundle_sha256:
            raise RecoveryRefusal("checkpoint belongs to another policy bundle")
        return result


__all__=["CausalSnapshotInput","PolicyRestartProbe","RankedDecision",
         "RuntimeCheckpoint","TabularInferencePipeline","TabularPolicyBundle",
         "create_policy_bundle","decide","decide_margin","decide_simultaneous",
         "decision_entry_score"]
