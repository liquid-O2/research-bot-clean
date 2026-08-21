"""Chronological solver-in-the-loop rollout and exact relabel curriculum."""

from __future__ import annotations

from dataclasses import asdict,dataclass
from types import MappingProxyType
from typing import Mapping,Sequence

import numpy as np

from . import common as C
from .exact_delayed_teacher import (
    DayOptionUniverse,ExactDaySolver,ExactDelayedTeacherDay,
    PortfolioPrefixCondition,RolloutStateProposal,
    add_rollout_relabels,rollout_error_queries,
)
from .tabular_action_features import build_action_feature_matrix
from .tabular_delayed_corpus import CausalFeatureShard,prepare_runtime_feature_shard
from .tabular_models import ActionModelBundle,ComponentModelBundle
from .tabular_model_io import predict_action_regret
from .tabular_recovery_contracts import (
    CausalFeatureSchema,DecisionAction,RecoveryRefusal,
)


def _learned_action(regret:np.ndarray)->DecisionAction:
    enter,defer,passed=map(float,regret)
    if enter<min(defer,passed):return DecisionAction.ENTER
    if defer<=passed:return DecisionAction.DEFER
    return DecisionAction.PASS


def _feature_matrix(dataset:CausalFeatureShard,schema:CausalFeatureSchema)->np.ndarray:
    prepared=prepare_runtime_feature_shard(dataset,schema)
    if prepared.feature_names!=schema.names:
        raise RecoveryRefusal("dense rollout feature schema differs")
    return np.asarray(prepared.features,np.float32)


@dataclass(frozen=True,slots=True)
class RolloutRoundReceipt:
    trading_day:int
    round_index:int
    policy_receipts:tuple[str,...]
    visited_states:int
    false_or_missed_states:int
    rows_added:int
    teacher_before_sha256:str
    teacher_after_sha256:str
    source_universe_sha256:str
    source_feature_receipts:tuple[str,...]
    receipt_sha256:str

    def __post_init__(self)->None:
        C.guard_date(self.trading_day)
        is_sha=lambda value:(isinstance(value,str) and len(value)==64
            and all(char in "0123456789abcdef" for char in value))
        core={"schema":"QRE2TABROLLOUTROUND2","trading_day":self.trading_day,
              "round_index":self.round_index,"policy_receipts":self.policy_receipts,
              "visited_states":self.visited_states,
              "false_or_missed_states":self.false_or_missed_states,
              "rows_added":self.rows_added,
              "teacher_before_sha256":self.teacher_before_sha256,
              "teacher_after_sha256":self.teacher_after_sha256,
              "source_universe_sha256":self.source_universe_sha256,
              "source_feature_receipts":self.source_feature_receipts}
        if (self.round_index not in (1,2) or self.visited_states<0
                or self.false_or_missed_states<0 or self.rows_added<0
                or self.false_or_missed_states>self.visited_states
                or len(self.policy_receipts)!=5
                or len(set(self.policy_receipts))!=5
                or len(self.source_feature_receipts)
                   !=len(set(self.source_feature_receipts))
                or any(not is_sha(value) for value in (
                    self.teacher_before_sha256,self.teacher_after_sha256,
                    self.source_universe_sha256,self.receipt_sha256))
                or any(not is_sha(value) for value in self.source_feature_receipts)
                or C.object_sha256(core)!=self.receipt_sha256):
            raise RecoveryRefusal("rollout round receipt is malformed")


def rollout_teacher_day(*,universe:DayOptionUniverse,
        teacher:ExactDelayedTeacherDay,dense_features:Sequence[CausalFeatureShard],
        feature_schema:CausalFeatureSchema,component_models:Sequence[object],
        action_models:Sequence[object],round_index:int
        )->tuple[ExactDelayedTeacherDay,RolloutRoundReceipt]:
    universe.validate();teacher.validate();feature_schema.__post_init__()
    # Validating properties re-scan the whole universe per access; the
    # walk touched them per timestamp.  One access each, same values.
    trading_day=universe.trading_day
    universe_representation=universe.representation_sha256
    feature_rows=tuple(dense_features)
    if not feature_rows:raise RecoveryRefusal("rollout has no dense causal shards")
    for row in feature_rows:row.validate()
    asset_rows=tuple(str(np.asarray(row.asset,str)[0]) for row in feature_rows)
    if (not set(asset_rows) or not set(asset_rows)<=set(C.ASSETS)
            or len(asset_rows)!=len(set(asset_rows))
            or {int(np.asarray(row.day,np.int64)[0]) for row in feature_rows}
               !={trading_day}):
        raise RecoveryRefusal("rollout dense shards are not one unique-asset day")
    if (round_index not in (1,2) or len(component_models)!=5
            or len(action_models)!=5):
        raise RecoveryRefusal("rollout model roster/round is malformed")
    if (len({model.seed for model in component_models})!=5
            or tuple(model.seed for model in component_models)
               !=tuple(model.seed for model in action_models)
            or any(model.shuffled_labels for model in component_models)
            or any(model.shuffled_labels for model in action_models)):
        raise RecoveryRefusal("rollout requires five matched real OOF policies")
    if any(component.feature_names!=feature_schema.names for component in component_models):
        raise RecoveryRefusal("rollout component feature schema differs")
    if any(trading_day<=component.validation_day_range[1]
           or trading_day<=action.validation_day_range[1]
           for component,action in zip(component_models,action_models)):
        raise RecoveryRefusal("rollout policy is not chronological OOF")
    solver=ExactDaySolver(universe)
    authority=solver.exact_schedule()
    if (authority.objective_cents!=teacher.exact_objective_cents
            or set(authority.selected_opportunity_ids)
               !=set(teacher.selected_opportunity_ids)):
        raise RecoveryRefusal("rollout solver differs from published teacher")
    solver.authorize_interval_suffix_solver(authority)
    x=np.concatenate([_feature_matrix(row,feature_schema) for row in feature_rows])
    opportunity=np.concatenate([np.asarray(row.opportunity_id,str)
                                for row in feature_rows])
    feature_index={value:index for index,value in enumerate(opportunity)}
    universe_index={str(value):index for index,value in enumerate(universe.opportunity_id)}
    common_ids=sorted(set(feature_index)&set(universe_index),key=lambda value:(
        int(universe.snapshot_ts_ns[universe_index[value]]),value))
    by_timestamp={}
    for value in common_ids:
        by_timestamp.setdefault(int(universe.snapshot_ts_ns[universe_index[value]]),[]).append(value)
    all_queries=[];visited=0
    for component_model,action_model in zip(component_models,action_models):
        # One plane-wide predict per policy: component scores are causal-row
        # functions and CatBoost scores rows independently of batching, so
        # the values are byte-identical to the historical per-timestamp
        # calls without their per-call dispatch cost.
        x_components=np.asarray(component_model.predict(x).values,np.float64)
        consumed:set[str]=set();passed:set[str]=set();entries=0
        open_until={asset:-1 for asset in C.ASSETS}
        causal_open_until={asset:-1 for asset in C.ASSETS}
        proposals=[]
        for timestamp,ids in sorted(by_timestamp.items()):
            for asset in C.ASSETS:
                if open_until[asset]<timestamp:
                    open_until[asset]=-1;causal_open_until[asset]=-1
            blocked=consumed|passed
            live=[value for value in ids
                  if str(universe.series_id[universe_index[value]]) not in blocked]
            if not live:continue
            condition=PortfolioPrefixCondition(trading_day,timestamp,entries,
                tuple(open_until[asset] for asset in C.ASSETS),
                tuple(causal_open_until[asset] for asset in C.ASSETS),
                tuple(sorted(consumed)),tuple(sorted(passed)))
            active=np.asarray([solver.active_watch_counts(condition)]*len(live),np.int16)
            rows=np.asarray([feature_index[value] for value in live],np.int64)
            universe_rows=np.asarray([universe_index[value] for value in live],np.int64)
            causal=x[rows];components=x_components[rows]
            action_names,action_x=build_action_feature_matrix(
                causal_feature_names=feature_schema.names,causal_matrix=causal,
                component_predictions=components,
                asset=np.asarray(universe.asset,str)[universe_rows],
                snapshot_ts_ns=np.full(len(live),timestamp,np.int64),
                entries_used=np.full(len(live),entries,np.int8),
                open_until_ts_ns=np.asarray([
                    [causal_open_until[asset] for asset in C.ASSETS]
                    for _value in live],np.int64),
                active_watches_by_asset_side=active,
                phase=np.asarray(universe.phase,str)[universe_rows])
            if action_names!=action_model.feature_names:
                raise RecoveryRefusal("rollout action feature schema differs")
            regrets=predict_action_regret(action_model,action_x,
                                          trading_day=trading_day)
            learned=[]
            for position,value in enumerate(live):
                asset=str(universe.asset[universe_rows[position]])
                action=(DecisionAction.DEFER if open_until[asset]>=timestamp
                        else DecisionAction.PASS
                        if entries>=C.MAX_ENTRIES_PORTFOLIO_DAY
                        else _learned_action(regrets[position]))
                learned.append(action)
            enter_positions=[position for position,action in enumerate(learned)
                             if action is DecisionAction.ENTER]
            best_by_asset={}
            for position in enter_positions:
                asset=str(universe.asset[universe_rows[position]])
                advantage=float(min(regrets[position,1],regrets[position,2])
                                -regrets[position,0])
                key=(-advantage,str(universe.candidate_id[
                    universe_rows[position]]))
                if asset not in best_by_asset or key<best_by_asset[asset][0]:
                    best_by_asset[asset]=(key,position)
            ranked=sorted((value[1] for value in best_by_asset.values()),key=lambda position:(
                -(min(regrets[position,1],regrets[position,2])-regrets[position,0]),
                str(universe.candidate_id[universe_rows[position]])))
            chosen=set(ranked[:max(0,C.MAX_ENTRIES_PORTFOLIO_DAY-entries)])
            for position,value in enumerate(live):
                actual=(learned[position] if learned[position] is not DecisionAction.ENTER
                        or position in chosen else DecisionAction.DEFER)
                proposals.append(RolloutStateProposal(value,condition,actual));visited+=1
            for position,action in enumerate(learned):
                if action is DecisionAction.PASS:
                    passed.add(str(universe.series_id[universe_rows[position]]))
            for position in ranked:
                if position not in chosen:continue
                index=universe_rows[position];series=str(universe.series_id[index])
                asset=str(universe.asset[index]);consumed.add(series)
                open_until[asset]=int(universe.exit_ts_ns[index]);entries+=1
                causal_open_until[asset]=int(universe.phase_close_ts_ns[index])
        all_queries.extend(rollout_error_queries(
            teacher,solver,proposals,round_index=round_index))
    unique={}
    for query in all_queries:
        unique[(query.opportunity_id,query.condition.receipt_sha256)]=query
    queries=tuple(unique[key] for key in sorted(unique))
    before=teacher.representation_sha256
    updated=add_rollout_relabels(teacher,solver,queries,round_index=round_index)
    after=updated.representation_sha256;rows_added=len(updated.action_opportunity_id)-len(teacher.action_opportunity_id)
    policies=tuple(component.receipt_sha256+":"+action.receipt_sha256
                   for component,action in zip(component_models,action_models))
    feature_receipts=tuple(sorted(
        row.representation_sha256 for row in feature_rows))
    core={"schema":"QRE2TABROLLOUTROUND2","trading_day":trading_day,
          "round_index":round_index,"policy_receipts":policies,
          "visited_states":visited,"false_or_missed_states":len(queries),
          "rows_added":rows_added,"teacher_before_sha256":before,
          "teacher_after_sha256":after,
          "source_universe_sha256":universe_representation,
          "source_feature_receipts":feature_receipts}
    receipt=RolloutRoundReceipt(trading_day,round_index,policies,visited,
        len(queries),rows_added,before,after,universe_representation,
        feature_receipts,C.object_sha256(core))
    receipt.__post_init__()
    return updated,receipt


__all__=["RolloutRoundReceipt","rollout_teacher_day"]
