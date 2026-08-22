"""Every-second causal policy simulation through canonical Entry V2 replay."""

from __future__ import annotations

from dataclasses import asdict,dataclass,replace
import json
from pathlib import Path
from types import MappingProxyType
from typing import Final, Mapping, Sequence

import numpy as np

from . import common as C
from .contracts import (
    CausalEntryExample,EntryScore,RawPrefixRef,SessionRef,Side,
)
from .exact_delayed_teacher import (
    DayOptionUniverse, PortfolioPrefixCondition, RolloutStateProposal, _arrival,
)
from .replay import ReplayOutcome,ScoredArrival,replay
from .tabular_action_features import build_action_feature_matrix, qrf4_regime_matrix
from .tabular_calibration import (
    AdmissionContract, BlockReplayEvidence, CalibrationBundle,
    calibration_group_key,
)
from .tabular_delayed_corpus import CausalFeatureShard,prepare_runtime_feature_shard
from .tabular_recovery_contracts import (
    ACTIVE_WATCH_KEYS, CausalFeatureSchema, ComponentPredictions,
    DecisionAction, OpenPositionState, PortfolioDecisionState,
    RecoveryRefusal,
)
from .tabular_policy import decide,decide_margin
from .tabular_model_io import predict_action_regret


LIVE_REPLAY_SCHEMA: Final="QRE2TABLIVEREPLAY3"
TRACE_STORE_SCHEMA: Final="QRE2TABLIVETRACESTORE1"
# A1 diagnosis (design/A1_MARGIN_RULE_SPEC.md item 2).  ARGMIN is the frozen
# chain default; MARGIN is CALIBRATED-only and reached by explicit argument.
POLICY_MODES: Final=("ARGMIN","MARGIN")


def policy_mode_core_key(policy_mode:str)->Mapping[str,str]:
    """The receipt-core contribution of ``policy_mode``, empty for ARGMIN.

    WHY conditional: every already-published PolicyDayTrace and trace-store
    file was hashed WITHOUT this key, and A1 spec item 2 requires the default
    to stay byte-identical.  An unconditional key would invalidate every
    stored artifact on strict reload.
    """

    if policy_mode not in POLICY_MODES:
        raise RecoveryRefusal(f"live replay policy mode is unknown: {policy_mode!r}")
    return {} if policy_mode=="ARGMIN" else {"policy_mode":policy_mode}


def _learned_action(regret:np.ndarray)->DecisionAction:
    enter,defer,passed=map(float,regret)
    if enter<min(defer,passed):return DecisionAction.ENTER
    if defer<=passed:return DecisionAction.DEFER
    return DecisionAction.PASS


@dataclass(frozen=True,slots=True)
class PolicyDayTrace:
    trading_day:int
    mode:str
    calibration_receipt_sha256:str|None
    admission_receipt_sha256:str|None
    selected_opportunity_ids:tuple[str,...]
    arrivals:tuple[ScoredArrival,...]
    rejected_fallback:ScoredArrival
    proposals:tuple[RolloutStateProposal,...]
    policy_crossing_timestamps:Mapping[str,tuple[int,...]]
    action_change_timestamps:Mapping[str,tuple[int,...]]
    component_model_sha256:str
    action_model_sha256:str
    feature_schema_sha256:str
    source_universe_sha256:str
    source_feature_receipts:tuple[str,...]
    receipt_sha256:str
    # Trails receipt_sha256 so every existing positional construction and
    # every stored trace keeps its meaning (A1 spec item 2).
    policy_mode:str="ARGMIN"

    def __post_init__(self)->None:
        C.guard_date(self.trading_day)
        if (self.mode not in {"RAW","CALIBRATED"}
                or self.policy_mode not in POLICY_MODES
                or (self.policy_mode=="MARGIN" and self.mode!="CALIBRATED")
                or (self.mode=="CALIBRATED")
                   !=(self.calibration_receipt_sha256 is not None)
                or (self.mode=="CALIBRATED")
                   !=(self.admission_receipt_sha256 is not None)
                or (self.calibration_receipt_sha256 is not None
                    and len(self.calibration_receipt_sha256)!=64)
                or (self.admission_receipt_sha256 is not None
                    and len(self.admission_receipt_sha256)!=64)
                or len(self.selected_opportunity_ids)!=len(set(
                    self.selected_opportunity_ids))
                or tuple(row.example.candidate_id for row in self.arrivals)
                   !=self.selected_opportunity_ids
                or any(dict(row.example.causal_features)
                       !={"policy_snapshot_present":1.0}
                       for row in self.arrivals+(self.rejected_fallback,))
                or any(not key for key in self.policy_crossing_timestamps)
                or any(not key for key in self.action_change_timestamps)
                or len(self.source_feature_receipts)!=len(set(
                    self.source_feature_receipts))
                or any(len(value)!=64 for value in (
                    self.component_model_sha256,self.action_model_sha256,
                    self.feature_schema_sha256,self.source_universe_sha256,
                    self.receipt_sha256))
                or any(len(value)!=64 for value in self.source_feature_receipts)):
            raise RecoveryRefusal("live policy day trace is malformed")
        core={"schema":LIVE_REPLAY_SCHEMA,"day":self.trading_day,
              "mode":self.mode,
              "calibration":self.calibration_receipt_sha256,
              "admission":self.admission_receipt_sha256,
              "selected":self.selected_opportunity_ids,
              "component":self.component_model_sha256,
              "action":self.action_model_sha256,
              "feature_schema":self.feature_schema_sha256,
              "source_universe":self.source_universe_sha256,
              "feature_shards":self.source_feature_receipts,
              "arrivals":tuple(_arrival_payload(row) for row in self.arrivals),
              "rejected_fallback":_arrival_payload(self.rejected_fallback),
              "proposals":tuple((row.opportunity_id,
                  row.condition.receipt_sha256,row.predicted_action.value)
                  for row in self.proposals),
              "crossings":dict(self.policy_crossing_timestamps),
              "action_changes":dict(self.action_change_timestamps),
              **policy_mode_core_key(self.policy_mode),
              "h2_open_count":0}
        if C.object_sha256(core)!=self.receipt_sha256:
            raise RecoveryRefusal("live policy day trace receipt differs")


@dataclass(frozen=True,slots=True)
class _RawDecision:
    action:DecisionAction
    incremental_dollars_usd:float


def _arrival_payload(row:ScoredArrival)->Mapping[str,object]:
    example=row.example
    if example.context is not None:
        raise RecoveryRefusal("tabular live arrival unexpectedly carries context")
    return MappingProxyType({
        "example":{"candidate_id":example.candidate_id,"asset":example.asset,
            "trading_day":example.trading_day,"session_id":example.session_id,
            "decision_ts_ns":example.decision_ts_ns,"side":example.side.value,
            "phase":example.phase,"locked_iid":example.locked_iid,
            "raw_prefix_ref":asdict(example.raw_prefix_ref),
            "causal_features":dict(example.causal_features),
            "lineage_hash":example.lineage_hash},
        "score":asdict(row.score),"outcome":asdict(row.outcome)})


def _arrival_from_payload(value:Mapping[str,object])->ScoredArrival:
    raw=dict(value);example_raw=dict(raw["example"])
    example_raw["raw_prefix_ref"]=RawPrefixRef(**example_raw["raw_prefix_ref"])
    example_raw["side"]=Side(example_raw["side"])
    example=CausalEntryExample(**example_raw)
    return ScoredArrival(example,EntryScore(**raw["score"]),
                         ReplayOutcome(**raw["outcome"]))


def _label_free_live_arrival(base:ScoredArrival,score:EntryScore)->ScoredArrival:
    example=replace(base.example,
        causal_features={"policy_snapshot_present":1.0})
    return ScoredArrival(example,score,base.outcome)


def _day_feature_plane(shards:Sequence[CausalFeatureShard],
                       schema:CausalFeatureSchema)->Mapping[str,np.ndarray]:
    rows=tuple(prepare_runtime_feature_shard(row,schema) for row in shards)
    schema.__post_init__()
    if not rows:raise RecoveryRefusal("live replay has no causal feature shards")
    for row in rows:row.validate()
    days={int(np.asarray(row.day,np.int64)[0]) for row in rows}
    asset_rows=tuple(str(np.asarray(row.asset,str)[0]) for row in rows)
    assets=set(asset_rows)
    if (len(days)!=1 or not assets or not assets<=set(C.ASSETS)
            or len(asset_rows)!=len(assets)):
        raise RecoveryRefusal("live replay feature plane is not one unique-asset day")
    source={name:index for index,name in enumerate(rows[0].feature_names)}
    if (any(row.feature_names!=rows[0].feature_names for row in rows)
            or not set(schema.names)<=set(source)):
        raise RecoveryRefusal("live replay causal schema differs")
    columns=np.asarray([source[name] for name in schema.names],np.int64)
    plane={"features":np.concatenate([
        np.asarray(row.features,np.float32)[:,columns] for row in rows])}
    for name in ("opportunity_id","series_id","candidate_id","asset","day",
                 "side","phase","snapshot_ts_ns"):
        plane[name]=np.concatenate([np.asarray(getattr(row,name)) for row in rows])
    ids=np.asarray(plane["opportunity_id"],str)
    if len(ids)!=len(set(ids.tolist())):raise RecoveryRefusal("live opportunity repeats")
    order=np.lexsort((ids,np.asarray(plane["snapshot_ts_ns"],np.int64)))
    return MappingProxyType({key:np.asarray(value)[order] for key,value in plane.items()})


def _watch_metadata(series:np.ndarray,timestamp:np.ndarray,asset:np.ndarray,
                    side:np.ndarray)->Mapping[str,tuple[int,int,str,int]]:
    output={}
    for key in sorted(set(series.tolist())):
        local=np.flatnonzero(series==key);clock=np.sort(timestamp[local])
        if len(clock)>1 and np.any(np.diff(clock)!=1_000_000_000):
            raise RecoveryRefusal("runtime watch clock is not every receive-second")
        local_assets=set(asset[local].tolist());local_sides=set(map(int,side[local]))
        if len(local_assets)!=1 or len(local_sides)!=1:
            raise RecoveryRefusal("runtime watch changes asset/side")
        output[key]=(int(clock[0]),int(clock[-1]),str(next(iter(local_assets))),
                     int(next(iter(local_sides))))
    return MappingProxyType(output)


def walkable_row_mask(*,opportunity:np.ndarray,series:np.ndarray,
                      timestamp:np.ndarray,
                      universe_ids:frozenset[str])->np.ndarray:
    """Rows of the runtime feature plane the walk may decide on.

    The runtime feature clock runs to each watch's declared expiry, but the
    exact-outcome universe ends a watch at its last resolvable second, so a
    dense shard may carry a short unresolvable suffix per watch.  Those
    seconds can never be lawfully entered (no exact outcome exists) and the
    exact teacher never selects them; the walk skips exactly them.  Any
    non-trailing gap, or a watch with no resolvable second at all, is a
    source roster mismatch and refuses.
    """

    covered=np.asarray([value in universe_ids
                        for value in np.asarray(opportunity,str).tolist()],bool)
    if not covered.all():
        series=np.asarray(series,str);timestamp=np.asarray(timestamp,np.int64)
        for key in sorted(set(series[~covered].tolist())):
            local=series==key
            resolved=timestamp[local&covered]
            if (not len(resolved)
                    or int(np.min(timestamp[local&~covered]))
                       <=int(np.max(resolved))):
                raise RecoveryRefusal("live feature opportunity lacks exact outcome")
    return covered


class _ActiveWatchCounter:
    """Incremental active-watch counts for a non-decreasing query clock.

    Set-identical to scanning ``{key: first<=now<=last and key not in
    consumed|passed}`` at every queried second — the historical scan is
    O(watches) per second and dominated large days.  Watches enter at their
    first second, leave strictly after their last, and leave immediately
    when blocked; single interval per series is guaranteed upstream by
    ``_watch_metadata``.
    """

    def __init__(self,watches:Mapping[str,tuple[int,int,str,int]])->None:
        self._meta=watches
        self._starts=sorted((first,key) for key,(first,_last,_a,_s)
                            in watches.items())
        self._expiries=sorted((last,key) for key,(_first,last,_a,_s)
                              in watches.items())
        self._start_index=0;self._expiry_index=0
        self._live:set[str]=set();self._blocked:set[str]=set()
        self._counts={key:0 for key in ACTIVE_WATCH_KEYS}

    def block(self,key:str)->None:
        if key in self._blocked:return
        self._blocked.add(key)
        if key in self._live:
            self._live.discard(key)
            _first,_last,name,side=self._meta[key]
            self._counts[(name,side)]-=1

    def counts_at(self,now:int)->tuple[int,...]:
        starts=self._starts;expiries=self._expiries
        while (self._start_index<len(starts)
               and starts[self._start_index][0]<=now):
            key=starts[self._start_index][1];self._start_index+=1
            if key in self._blocked:continue
            self._live.add(key)
            _first,_last,name,side=self._meta[key]
            self._counts[(name,side)]+=1
        while (self._expiry_index<len(expiries)
               and expiries[self._expiry_index][0]<now):
            key=expiries[self._expiry_index][1];self._expiry_index+=1
            if key in self._live:
                self._live.discard(key)
                _first,_last,name,side=self._meta[key]
                self._counts[(name,side)]-=1
        return tuple(self._counts[key] for key in ACTIVE_WATCH_KEYS)


def replay_policy_day(*,universe:DayOptionUniverse,
        dense_feature_shards:Sequence[CausalFeatureShard],
        feature_schema:CausalFeatureSchema,component_model:object,
        action_model:object,mode:str,
        calibration:CalibrationBundle|None=None,
        admission:AdmissionContract|None=None,
        collect_proposals:bool=False,
        policy_mode:str="ARGMIN")->PolicyDayTrace:
    """Run the unchanged policy chronologically at every available second."""

    universe.validate();mode=str(mode).upper()
    policy_mode=str(policy_mode).upper();policy_mode_core_key(policy_mode)
    if policy_mode=="MARGIN" and mode!="CALIBRATED":
        raise RecoveryRefusal("margin policy mode is CALIBRATED-only")
    if mode not in {"RAW","CALIBRATED"}:
        raise RecoveryRefusal("live replay mode is unknown")
    if mode=="CALIBRATED" and (calibration is None or admission is None):
        raise RecoveryRefusal("calibrated live replay lacks frozen artifacts")
    if mode=="RAW" and (calibration is not None or admission is not None):
        raise RecoveryRefusal("raw replay cannot read calibration/threshold")
    if tuple(component_model.feature_names)!=feature_schema.names:
        raise RecoveryRefusal("live component schema differs")
    # trading_day/representation_sha256 are validating properties that
    # re-scan the whole universe on every access; the walk touched them per
    # row and per second.  One access each here, same values.
    trading_day=universe.trading_day
    universe_representation=universe.representation_sha256
    plane=_day_feature_plane(dense_feature_shards,feature_schema)
    if int(np.asarray(plane["day"],np.int64)[0])!=trading_day:
        raise RecoveryRefusal("live feature/outcome day differs")
    opportunity=np.asarray(plane["opportunity_id"],str)
    series=np.asarray(plane["series_id"],str)
    asset=np.asarray(plane["asset"],str)
    side=np.asarray(plane["side"],np.int8)
    phase=np.asarray(plane["phase"],str)
    timestamp=np.asarray(plane["snapshot_ts_ns"],np.int64)
    features=np.asarray(plane["features"],np.float32)
    universe_lookup={str(value):index for index,value in enumerate(
        np.asarray(universe.opportunity_id,str))}
    covered=walkable_row_mask(opportunity=opportunity,series=series,
        timestamp=timestamp,universe_ids=frozenset(universe_lookup))
    # Component predictions depend only on the causal row, never on walk
    # state, and CatBoost scores each row independently of its batch, so one
    # plane-wide predict returns byte-identical values to the historical
    # per-timestamp calls while dropping ~4ms of dispatch per second walked.
    plane_components=np.asarray(component_model.predict(features).values,
                                np.float64)
    watches=_watch_metadata(series,timestamp,asset,side)
    by_timestamp={}
    for index,value in enumerate(timestamp):
        if covered[index]:by_timestamp.setdefault(int(value),[]).append(index)
    consumed:set[str]=set();passed:set[str]=set();entries=0
    watch_counter=_ActiveWatchCounter(watches)
    # asset -> (series, entry, realized exit, scheduled phase close)
    positions:dict[str,tuple[str,int,int,int]]={}
    selected=[];arrivals=[];proposals=[]
    crossings:dict[str,set[int]]={};changes:dict[str,set[int]]={}
    previous_score={};previous_action={}
    universe_ids=np.asarray(universe.opportunity_id,str)
    for now,raw_rows in sorted(by_timestamp.items()):
        for position_asset,value in tuple(positions.items()):
            if value[2]<now:positions.pop(position_asset)
        # Hoist the blocked-set union: evaluated inside the comprehensions it
        # is rebuilt per element, turning each second into an O(watches x
        # blocked-series) scan (~300ms/second late in a day).
        blocked=consumed|passed
        rows=np.asarray([index for index in raw_rows
            if str(series[index]) not in blocked],np.int64)
        if not len(rows):continue
        counts=watch_counter.counts_at(now)
        realized_open=tuple(positions.get(name,("",0,-1,-1))[2]
                            for name in C.ASSETS)
        causal_open=tuple(positions.get(name,("",0,-1,-1))[3]
                          for name in C.ASSETS)
        condition=PortfolioPrefixCondition(trading_day,now,entries,
            realized_open,causal_open,tuple(sorted(consumed)),tuple(sorted(passed)))
        causal=features[rows];component=plane_components[rows]
        action_names,action_x=build_action_feature_matrix(
            causal_feature_names=feature_schema.names,causal_matrix=causal,
            component_predictions=component,asset=asset[rows],
            snapshot_ts_ns=np.full(len(rows),now,np.int64),
            entries_used=np.full(len(rows),entries,np.int8),
            open_until_ts_ns=np.asarray([causal_open]*len(rows),np.int64),
            active_watches_by_asset_side=np.asarray([counts]*len(rows),np.int16),
            phase=phase[rows])
        if action_names!=tuple(action_model.feature_names):
            raise RecoveryRefusal("live action schema differs")
        regrets=predict_action_regret(action_model,action_x,
                                      trading_day=trading_day)
        if regrets.shape!=(len(rows),3) or not np.all(np.isfinite(regrets)):
            raise RecoveryRefusal("live action regret output differs")
        raw_advantage=np.minimum(regrets[:,1],regrets[:,2])-regrets[:,0]
        regime=qrf4_regime_matrix(feature_schema.names,causal)
        regime_names=np.asarray(("LOW","MID","HIGH","UNKNOWN"),str)[
            np.argmax(regime,axis=1)]
        if mode=="CALIBRATED":
            assert calibration is not None and admission is not None
            group=(calibration_group_key(entries_used=np.full(len(rows),entries),
                phase=phase[rows],regime=regime_names)
                if calibration.state_conditioned else None)
            mapped=calibration.predict_dollars(raw_advantage,group_key=group)
            lower=calibration.predict_lower(raw_advantage,group_key=group)
            probability=calibration.enter_optimal_platt.predict(raw_advantage)
        else:
            mapped=raw_advantage.copy();lower=raw_advantage.copy()
            probability=1.0/(1.0+np.exp(-np.clip(raw_advantage/600.0,-40,40)))
        decisions=[];states=[]
        open_states=tuple(OpenPositionState(name,value[0],value[1],value[3])
                          for name,value in sorted(positions.items()))
        for local,row in enumerate(rows):
            prediction=ComponentPredictions(
                *map(float,component[local,:7]),float(probability[local]),
                *map(float,component[local,7:]),*map(float,regrets[local]),
                float(lower[local]),float(mapped[local]))
            regime_name=str(regime_names[local])
            state=PortfolioDecisionState(str(plane["candidate_id"][row]),
                str(series[row]),str(asset[row]),trading_day,int(side[row]),
                now,watches[str(series[row])][1],feature_schema.names,
                tuple(causal[local].tolist()),prediction,entries,open_states,
                counts,str(phase[row]),regime_name)
            if mode=="CALIBRATED":
                decision=(decide(state,admission) if policy_mode=="ARGMIN"
                          else decide_margin(state,admission))
            elif state.asset_occupied:decision_action=DecisionAction.DEFER
            elif entries>=C.MAX_ENTRIES_PORTFOLIO_DAY:decision_action=DecisionAction.PASS
            else:decision_action=_learned_action(regrets[local])
            if mode=="RAW":
                decision=_RawDecision(decision_action,float(mapped[local]))
            decisions.append(decision);states.append(state)
        enter_positions=[index for index,row in enumerate(decisions)
                         if row.action is DecisionAction.ENTER]
        best_by_asset={}
        for local in enter_positions:
            key=(-float(decisions[local].incremental_dollars_usd),
                 str(plane["candidate_id"][rows[local]]))
            name=str(asset[rows[local]])
            if name not in best_by_asset or key<best_by_asset[name][0]:
                best_by_asset[name]=(key,local)
        ranked=sorted((value[1] for value in best_by_asset.values()),key=lambda local:(
            -float(decisions[local].incremental_dollars_usd),
            str(plane["candidate_id"][rows[local]])))
        chosen=set(ranked[:max(0,C.MAX_ENTRIES_PORTFOLIO_DAY-entries)])
        final_actions=[]
        for local,row in enumerate(rows):
            action=decisions[local].action
            if action is DecisionAction.ENTER and local not in chosen:
                action=DecisionAction.DEFER
            final_actions.append(action)
            key=str(series[row]);score=float(lower[local]);threshold=(
                admission.action_advantage_threshold_usd
                if admission is not None else 0.0)
            if key in previous_score and ((previous_score[key]>=threshold)
                                          !=(score>=threshold)):
                crossings.setdefault(key,set()).add(now)
            if key in previous_action and previous_action[key] is not action:
                changes.setdefault(key,set()).add(now)
            previous_score[key]=score;previous_action[key]=action
            if collect_proposals:
                proposals.append(RolloutStateProposal(str(opportunity[row]),condition,action))
        for local,action in enumerate(final_actions):
            if action is DecisionAction.PASS:
                key=str(series[rows[local]])
                passed.add(key);watch_counter.block(key)
        for local in ranked:
            if local not in chosen:continue
            row=rows[local];uid=str(opportunity[row]);index=universe_lookup[uid]
            key=str(series[row]);name=str(asset[row])
            consumed.add(key);watch_counter.block(key);entries+=1
            positions[name]=(key,now,int(universe.exit_ts_ns[index]),
                             int(universe.phase_close_ts_ns[index]))
            base=_arrival(universe,index,str(action_model.receipt_sha256),enter=True)
            state=states[local];prob=float(state.components.enter_probability)
            score=EntryScore(candidate_id=base.example.candidate_id,
                asset=base.example.asset,decision_ts_ns=now,
                model_hash=str(action_model.receipt_sha256),
                priority_score=float(decisions[local].incremental_dollars_usd),
                take_probability=prob,expected_pnl_usd=state.components.current_q50_usd,
                expected_pnl_lower_usd=state.components.current_q20_usd,
                top3_probability=prob,mae_p90_usd=state.components.mae_q90_usd,
                wall_probability=state.components.wall_probability,enter=True)
            arrivals.append(_label_free_live_arrival(base,score));selected.append(uid)
    fallback_base=_arrival(universe,0,str(action_model.receipt_sha256),enter=False)
    fallback=_label_free_live_arrival(fallback_base,fallback_base.score)
    crossing_frozen=MappingProxyType({key:tuple(sorted(value))
                                      for key,value in sorted(crossings.items())})
    change_frozen=MappingProxyType({key:tuple(sorted(value))
                                    for key,value in sorted(changes.items())})
    core={"schema":LIVE_REPLAY_SCHEMA,"day":trading_day,"mode":mode,
          "calibration":(None if calibration is None else calibration.receipt_sha256),
          "admission":(None if admission is None else admission.receipt_sha256),
          "selected":tuple(selected),"component":component_model.receipt_sha256,
          "action":action_model.receipt_sha256,"feature_schema":feature_schema.receipt_sha256,
          "source_universe":universe_representation,
          "feature_shards":tuple(sorted(
              row.representation_sha256 for row in dense_feature_shards)),
          "arrivals":tuple(_arrival_payload(row) for row in arrivals),
          "rejected_fallback":_arrival_payload(fallback),
          "proposals":tuple((row.opportunity_id,row.condition.receipt_sha256,
              row.predicted_action.value) for row in proposals),
          "crossings":dict(crossing_frozen),
          "action_changes":dict(change_frozen),
          **policy_mode_core_key(policy_mode),"h2_open_count":0}
    result=PolicyDayTrace(trading_day,mode,
        None if calibration is None else calibration.receipt_sha256,
        None if admission is None else admission.receipt_sha256,
        tuple(selected),tuple(arrivals),
        fallback,tuple(proposals),crossing_frozen,change_frozen,
        component_model.receipt_sha256,action_model.receipt_sha256,
        feature_schema.receipt_sha256,universe_representation,
        tuple(sorted(row.representation_sha256
                     for row in dense_feature_shards)),C.object_sha256(core),
        policy_mode)
    result.__post_init__();return result


def save_policy_day_trace(trace:PolicyDayTrace,path:str|Path)->str:
    """Persist exact live EntryScores/outcomes for restartable block replay."""

    trace.__post_init__();target=C.assert_workspace_output(path)
    proposals=tuple({"opportunity_id":row.opportunity_id,
        "condition":asdict(row.condition),"predicted_action":row.predicted_action.value}
        for row in trace.proposals)
    value={"trading_day":trace.trading_day,"mode":trace.mode,
        "calibration_receipt_sha256":trace.calibration_receipt_sha256,
        "admission_receipt_sha256":trace.admission_receipt_sha256,
        "selected_opportunity_ids":trace.selected_opportunity_ids,
        "arrivals":tuple(_arrival_payload(row) for row in trace.arrivals),
        "rejected_fallback":_arrival_payload(trace.rejected_fallback),
        "proposals":proposals,
        "policy_crossing_timestamps":dict(trace.policy_crossing_timestamps),
        "action_change_timestamps":dict(trace.action_change_timestamps),
        "component_model_sha256":trace.component_model_sha256,
        "action_model_sha256":trace.action_model_sha256,
        "feature_schema_sha256":trace.feature_schema_sha256,
        "source_universe_sha256":trace.source_universe_sha256,
        "source_feature_receipts":trace.source_feature_receipts,
        **policy_mode_core_key(trace.policy_mode),
        "trace_receipt_sha256":trace.receipt_sha256}
    core={"schema":TRACE_STORE_SCHEMA,"trace":value,"h2_open_count":0}
    return C.atomic_json(target,{**core,"receipt_sha256":C.object_sha256(core)})


def load_policy_day_trace(path:str|Path)->PolicyDayTrace:
    source=Path(path);C.guard_payload(source)
    try:payload=json.loads(source.read_text())
    except (OSError,UnicodeError,json.JSONDecodeError) as exc:
        raise RecoveryRefusal("cannot strict-load live policy trace") from exc
    core={key:value for key,value in payload.items() if key!="receipt_sha256"}
    if (payload.get("schema")!=TRACE_STORE_SCHEMA
            or C.object_sha256(core)!=payload.get("receipt_sha256")):
        raise RecoveryRefusal("live policy trace store receipt differs")
    value=dict(payload["trace"]);proposals=[]
    for raw in value["proposals"]:
        condition=dict(raw["condition"])
        for key in ("open_until_by_asset","causal_open_until_by_asset",
                    "consumed_series","passed_series"):
            condition[key]=tuple(condition[key])
        proposals.append(RolloutStateProposal(raw["opportunity_id"],
            PortfolioPrefixCondition(**condition),DecisionAction(raw["predicted_action"])))
    result=PolicyDayTrace(int(value["trading_day"]),str(value["mode"]),
        value["calibration_receipt_sha256"],value["admission_receipt_sha256"],
        tuple(value["selected_opportunity_ids"]),
        tuple(_arrival_from_payload(row) for row in value["arrivals"]),
        _arrival_from_payload(value["rejected_fallback"]),tuple(proposals),
        MappingProxyType({str(key):tuple(map(int,rows)) for key,rows in
                          value["policy_crossing_timestamps"].items()}),
        MappingProxyType({str(key):tuple(map(int,rows)) for key,rows in
                          value["action_change_timestamps"].items()}),
        str(value["component_model_sha256"]),str(value["action_model_sha256"]),
        str(value["feature_schema_sha256"]),str(value["source_universe_sha256"]),
        tuple(value["source_feature_receipts"]),
        str(value["trace_receipt_sha256"]),
        str(value.get("policy_mode","ARGMIN")))
    result.__post_init__();return result


def replay_policy_block(traces:Sequence[PolicyDayTrace],*,
        expected_sessions:Sequence[SessionRef],
        exact_ceiling_cents_by_day:Mapping[int,int],
        exact_ceiling_cents_by_asset:Mapping[str,int])->BlockReplayEvidence:
    rows=tuple(sorted(traces,key=lambda row:row.trading_day))
    if not rows:raise RecoveryRefusal("live replay block has no day traces")
    if (set(exact_ceiling_cents_by_day)!={row.trading_day for row in rows}
            or any(int(value)<0 for value in exact_ceiling_cents_by_day.values())):
        raise RecoveryRefusal("live replay exact day ceilings differ from traces")
    if (set(exact_ceiling_cents_by_asset)!=set(C.ASSETS)
            or any(int(value)<0 for value in exact_ceiling_cents_by_asset.values())
            or sum(int(value) for value in exact_ceiling_cents_by_asset.values())
               !=sum(int(value) for value in exact_ceiling_cents_by_day.values())):
        raise RecoveryRefusal("live replay per-asset exact ceilings differ")
    arrivals=tuple(item for row in rows for item in row.arrivals)
    if not arrivals:arrivals=(rows[0].rejected_fallback,)
    evaluation=replay(arrivals,expected_sessions=tuple(expected_sessions))
    expected_days=tuple(sorted({row.trading_day for row in expected_sessions}))
    eligible=tuple(sorted({(row.asset,row.trading_day) for row in expected_sessions}))
    active=tuple(sorted(day for day,value in exact_ceiling_cents_by_day.items()
                        if int(value)>0))
    by_asset=tuple((asset,int(exact_ceiling_cents_by_asset[asset])/100.0)
                   for asset in C.ASSETS)
    return BlockReplayEvidence(evaluation,
        sum(map(int,exact_ceiling_cents_by_day.values()))/100.0,
        expected_days,active,eligible,by_asset,1)


__all__=["LIVE_REPLAY_SCHEMA","POLICY_MODES","PolicyDayTrace",
         "TRACE_STORE_SCHEMA","load_policy_day_trace","policy_mode_core_key",
         "replay_policy_block","replay_policy_day","save_policy_day_trace",
         "walkable_row_mask"]
