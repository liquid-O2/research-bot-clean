"""Teacher-day assembly helpers and rollout relabel append."""

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType
from typing import TYPE_CHECKING, Mapping, Sequence

import numpy as np

from . import common as C
from .exact_teacher_prune import dominance_pruned_indices
from .exact_teacher_types import (
    ActionQuery, DayOptionUniverse, PortfolioPrefixCondition, RolloutStateProposal,
)
from .tabular_recovery_contracts import DecisionAction, RecoveryRefusal

if TYPE_CHECKING:
    from .exact_delayed_teacher import ExactDelayedTeacherDay
    from .exact_teacher_solver import ExactDaySolver


def _component_indices(
    universe: DayOptionUniverse, selected_indices: Sequence[int],
) -> np.ndarray:
    series = np.asarray(universe.series_id, str)
    ts = np.asarray(universe.snapshot_ts_ns, np.int64)
    watch = np.asarray(universe.watch_start_ts_ns, np.int64)
    from .confirmation import training_offsets_seconds
    age = np.rint((ts - watch) / 1e9).astype(np.int64)
    max_delay = 600 if int(age.max()) > 300 else 300
    keep = np.isin(age, training_offsets_seconds(max_delay))
    for index in selected_indices:
        target = int(ts[index]); key = str(series[index])
        keep |= ((series == key)
                 & np.isin(ts, (target - 1_000_000_000, target,
                                target + 1_000_000_000)))
    return np.flatnonzero(keep)


def _component_targets(
    universe: DayOptionUniverse, indices: np.ndarray,
) -> Mapping[str, np.ndarray]:
    series = np.asarray(universe.series_id, str)
    ts = np.asarray(universe.snapshot_ts_ns, np.int64)
    current = np.asarray(universe.signed_pnl_cents, np.int64) / 100.0
    continuation = np.zeros(len(indices), np.float64)
    observed = np.zeros(len(indices), bool)
    by_series = {key: np.flatnonzero(series == key)
                 for key in sorted(set(series.tolist()))}
    for position, index in enumerate(indices):
        local = by_series[str(series[index])]
        strictly_later = local[(ts[local] > ts[index])
                               & (ts[local] <= ts[index] + 120_000_000_000)]
        horizon_observed = int(ts[local].max()) >= int(ts[index]) + 120_000_000_000
        observed[position] = horizon_observed
        continuation[position] = (0.0 if not len(strictly_later) else
                                  float(np.max(current[strictly_later])))
    return MappingProxyType({
        "component_opportunity_id": np.asarray(
            universe.opportunity_id, str)[indices].copy(),
        "current_entry_usd": current[indices].astype(np.float64),
        "continuation_120_usd": continuation,
        "continuation_observed": observed,
        "wall_target": np.asarray(universe.wall_hit, bool)[indices].copy(),
        "mae_usd": np.asarray(universe.mae_usd, np.float64)[indices].copy(),
        "occupancy_sec": ((np.asarray(universe.exit_ts_ns, np.int64)[indices]
                           - ts[indices]) / 1e9).astype(np.float64),
    })


def _prefix_condition_for_schedule(
    universe: DayOptionUniverse, selected_indices: Sequence[int], timestamp: int,
) -> PortfolioPrefixCondition:
    selected = np.asarray(selected_indices, np.int64)
    starts = np.asarray(universe.snapshot_ts_ns, np.int64)[selected]
    exits = np.asarray(universe.exit_ts_ns, np.int64)[selected]
    phase_closes = np.asarray(universe.phase_close_ts_ns, np.int64)[selected]
    assets = np.asarray(universe.asset, str)[selected]
    series = np.asarray(universe.series_id, str)[selected]
    prior = starts < int(timestamp)
    open_until = []
    causal_open_until = []
    for asset in C.ASSETS:
        active_mask = prior & (assets == asset) & (exits >= int(timestamp))
        active = exits[active_mask]
        open_until.append(-1 if not len(active) else int(np.max(active)))
        causal = phase_closes[active_mask]
        causal_open_until.append(
            -1 if not len(causal) else int(np.max(causal)))
    return PortfolioPrefixCondition(
        universe.trading_day, int(timestamp), int(np.count_nonzero(prior)),
        tuple(open_until), tuple(causal_open_until),
        tuple(sorted(set(series[prior].tolist()))), ())


def _action_query_indices(
    universe: DayOptionUniverse, selected_indices: Sequence[int],
) -> Mapping[int, str]:
    selected = np.asarray(selected_indices, np.int64)
    selected_set = set(map(int, selected.tolist()))
    series = np.asarray(universe.series_id, str)
    ts = np.asarray(universe.snapshot_ts_ns, np.int64)
    start = ts
    end = np.asarray(universe.exit_ts_ns, np.int64)
    asset = np.asarray(universe.asset, str)
    cents = np.asarray(universe.signed_pnl_cents, np.int64)
    chosen_series = set(series[selected].tolist())
    from .confirmation import training_offsets_seconds
    result: dict[int, str] = {}
    # Every sparse causal state on each Oracle-selected watch through entry.
    for selected_index in selected:
        key = str(series[selected_index]); entry = int(ts[selected_index])
        local = np.flatnonzero((series == key) & (ts <= entry))
        age = np.rint((ts[local]
                       - np.asarray(universe.watch_start_ts_ns, np.int64)[local])
                      / 1e9).astype(np.int64)
        max_delay = 600 if int(np.max(
            (ts[local]-np.asarray(universe.watch_start_ts_ns,np.int64)[local])
            /1e9))>300 else 300
        for index in local[np.isin(age, training_offsets_seconds(max_delay))]:
            result[int(index)] = "ORACLE_TRAJECTORY"
        # The +1 second state is retained on the component feature clock, but
        # is no longer actionable after the exact ENTER consumed the watch.
        for point in (entry - 1_000_000_000, entry):
            found = np.flatnonzero((series == key) & (ts == point))
            for index in found:
                result[int(index)] = "ORACLE_TRAJECTORY"
    # Goal-grade alternatives that conflict with a chosen asset interval or,
    # when the 12-seat cap binds, with the daily schedule budget.
    cap_binds = len(selected) >= C.MAX_ENTRIES_PORTFOLIO_DAY
    # Dense seconds that are strictly dominated within their own watch cannot
    # be a suffix decision and would create thousands of equivalent MILPs.
    # Keep every nondominated goal-grade conflict; this is exact pruning, not
    # a value/top-K roster filter.
    nondominated = dominance_pruned_indices(universe)
    goal = nondominated[cents[nondominated]
                        >= int(C.MIN_EXPECTANCY_USD * 100)]
    for index in goal:
        if int(index) in selected_set:
            continue
        # A selected series has ceased to be a live watch after its entry.
        selected_entry = next((int(ts[value]) for value in selected
                               if series[value] == series[index]), None)
        if selected_entry is not None and int(ts[index]) > selected_entry:
            continue
        overlap = np.any(
            (asset[selected] == asset[index])
            & (start[selected] <= end[index])
            & (end[selected] >= start[index]))
        if overlap or cap_binds or str(series[index]) in chosen_series:
            result.setdefault(int(index), "HIGH_VALUE_CONFLICT")
    return MappingProxyType(dict(sorted(result.items())))


def add_rollout_relabels(
    teacher: ExactDelayedTeacherDay, solver: ExactDaySolver,
    queries: Sequence[ActionQuery], *, round_index: int,
) -> ExactDelayedTeacherDay:
    """Append all unique learned-policy proposal states for one fixed round."""

    teacher.validate()
    if round_index not in (1, 2):
        raise RecoveryRefusal("rollout relabel round must be exactly one or two")
    if any(query.rollout_round != round_index for query in queries):
        raise RecoveryRefusal("rollout query round differs")
    existing = set(zip(
        np.asarray(teacher.action_opportunity_id, str).tolist(),
        np.asarray(teacher.action_condition_receipt_sha256, str).tolist()))
    kept = []
    for query in queries:
        key = (query.opportunity_id, query.condition.receipt_sha256)
        if key not in existing:
            kept.append(query); existing.add(key)
    if not kept:
        return teacher
    q_rows = []; regret_rows = []; action_rows = []; margin_rows = []
    active_watch_rows = []
    for query in kept:
        enter, defer, passed, action, regrets = solver.action_values(query)
        values = (enter, defer, passed); ordered = sorted(values)
        q_rows.append(values); regret_rows.append(regrets)
        action_rows.append(action.value)
        margin_rows.append(ordered[-1] - ordered[-2])
        active_watch_rows.append(solver.active_watch_counts(query.condition))
    q = np.asarray(q_rows, np.int64); regret = np.asarray(regret_rows, np.int64)
    def append(name: str, values: np.ndarray) -> np.ndarray:
        return np.concatenate((np.asarray(getattr(teacher, name)), values))
    result = replace(
        teacher,
        action_opportunity_id=append(
            "action_opportunity_id",
            np.asarray([query.opportunity_id for query in kept], str)),
        action_condition_receipt_sha256=append(
            "action_condition_receipt_sha256",
            np.asarray([query.condition.receipt_sha256 for query in kept], str)),
        action_source=append(
            "action_source", np.asarray([query.source for query in kept], str)),
        action_rollout_round=append(
            "action_rollout_round",
            np.full(len(kept), round_index, np.int8)),
        action_entries_used=append(
            "action_entries_used",
            np.asarray([query.condition.entries_used for query in kept], np.int8)),
        action_open_until_ts_ns=append(
            "action_open_until_ts_ns",
            np.asarray([query.condition.causal_open_until_by_asset
                        for query in kept],
                       np.int64)),
        action_active_watches_by_asset_side=append(
            "action_active_watches_by_asset_side",
            np.asarray(active_watch_rows, np.int16)),
        q_enter_cents=append("q_enter_cents", q[:, 0]),
        q_defer_cents=append("q_defer_cents", q[:, 1]),
        q_pass_cents=append("q_pass_cents", q[:, 2]),
        regret_enter_cents=append("regret_enter_cents", regret[:, 0]),
        regret_defer_cents=append("regret_defer_cents", regret[:, 1]),
        regret_pass_cents=append("regret_pass_cents", regret[:, 2]),
        optimal_action=append("optimal_action", np.asarray(action_rows, str)),
        action_margin_cents=append(
            "action_margin_cents", np.asarray(margin_rows, np.int64)),
        representation_sha256_stored="")
    result.validate(); return result


def rollout_error_queries(
    teacher: ExactDelayedTeacherDay, solver: ExactDaySolver,
    proposals: Sequence[RolloutStateProposal], *, round_index: int,
) -> tuple[ActionQuery, ...]:
    """Exact-relabel every economically wrong OOF policy proposal."""

    teacher.validate()
    if round_index not in (1, 2):
        raise RecoveryRefusal("rollout error round must be exactly one or two")
    selected = set(teacher.selected_opportunity_ids)
    output = []
    seen: set[tuple[str, str]] = set()
    for proposal in proposals:
        proposal.__post_init__()
        query = ActionQuery(
            proposal.opportunity_id, proposal.condition,
            f"POLICY_ROLLOUT_{round_index}", round_index)
        # Structurally unflaggable states: none of the three error classes can
        # fire, so the exact solver call is pure cost.  Off the oracle schedule
        # missed_oracle cannot fire; DEFER fires neither false_enter nor
        # premature_pass; at the entry cap _interval_dp_value returns 0 for
        # every conditioned variant (:526-527) so regrets are (10**18, 0, 0)
        # and premature_pass cannot fire for PASS either.
        if str(proposal.opportunity_id) not in selected:
            if proposal.predicted_action is DecisionAction.DEFER:
                continue
            if (proposal.predicted_action is DecisionAction.PASS
                    and int(proposal.condition.entries_used)
                    >= C.MAX_ENTRIES_PORTFOLIO_DAY):
                continue
        enter, defer, passed, _optimal, regrets = solver.action_values(query)
        predicted_index = {
            DecisionAction.ENTER: 0, DecisionAction.DEFER: 1,
            DecisionAction.PASS: 2}[proposal.predicted_action]
        false_enter = (proposal.predicted_action is DecisionAction.ENTER
                       and regrets[0] > 0)
        premature_pass = (proposal.predicted_action is DecisionAction.PASS
                          and regrets[2] > 0)
        missed_oracle = (proposal.opportunity_id in selected
                         and proposal.predicted_action is not DecisionAction.ENTER)
        # A wrong DEFER on a non-Oracle state is still a learned-policy action
        # change, but the fixed curriculum named only these three error classes.
        if not (false_enter or premature_pass or missed_oracle):
            continue
        if regrets[predicted_index] <= 0 and not missed_oracle:
            continue
        key = (query.opportunity_id, query.condition.receipt_sha256)
        if key not in seen:
            output.append(query); seen.add(key)
    return tuple(output)


__all__ = ["add_rollout_relabels", "rollout_error_queries"]
