"""Vectorized-Python twin of the every-second policy walk (levers R2/R3).

The oracle walk (``tabular_live_replay.replay_policy_day``) builds one
1,764-element tuple plus a ``PortfolioDecisionState`` per row per second —
~0.45 ms/row of pure Python object overhead over arithmetic that is a state
machine.  This module keeps the identical arithmetic but runs the per-row
part on numpy arrays, constructing contract objects only for the rows that
actually ENTER (and for proposals, which are an output).

D-051(2): the Python oracle stays the standing differential oracle; nothing
here is adopted without ``tools/diff_walk_twin.py`` reporting mismatches=0.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Final, Mapping, Sequence

import numpy as np

from . import common as C
from .contracts import EntryScore
from .exact_delayed_teacher import (
    DayOptionUniverse, PortfolioPrefixCondition, RolloutStateProposal, _arrival,
)
from .tabular_action_features import build_action_feature_matrix, qrf4_regime_matrix
from .tabular_calibration import (
    AdmissionContract, CalibrationBundle, calibration_group_key,
)
from .tabular_delayed_corpus import CausalFeatureShard
from .tabular_live_replay import (
    LIVE_REPLAY_SCHEMA, PolicyDayTrace, _ActiveWatchCounter, _arrival_payload,
    _day_feature_plane, _label_free_live_arrival, _watch_metadata,
    load_policy_day_trace, policy_mode_core_key, save_policy_day_trace,
    walkable_row_mask,
)
from .tabular_model_io import (
    load_action_model, load_component_model, predict_action_regret,
)
from .tabular_recovery_contracts import (
    ACTIVE_WATCH_KEYS, CausalFeatureSchema, ComponentPredictions,
    DecisionAction, OpenPositionState, PortfolioDecisionState, RecoveryRefusal,
    _lawful_state_feature_names,
)


WTWIN_ACTION_BY_CODE: Final = (DecisionAction.ENTER, DecisionAction.DEFER,
                               DecisionAction.PASS)
_WTWIN_ENTER: Final = 0
_WTWIN_DEFER: Final = 1
_WTWIN_PASS: Final = 2
_WTWIN_REGIME_NAMES: Final = np.asarray(("LOW", "MID", "HIGH", "UNKNOWN"), str)

# Walk-invocation counter.  The Edit-1 acceptance has to prove the twin
# actually EXECUTED: a warm per-theta trace cache short-circuits the walk, so a
# green differential over cached traces would accept code that never ran.
# Incremented inside replay_policy_day_multistate itself, so no caller can
# report a walk that did not happen.
_WTWIN_WALK_INVOCATIONS: dict[str, int] = {"multistate": 0}


def wtwin_walk_invocations() -> int:
    """Multistate walks executed in this process since the last reset."""

    return int(_WTWIN_WALK_INVOCATIONS["multistate"])


def wtwin_reset_walk_invocations() -> None:
    """Zero the counter so one acceptance run measures only its own walks."""

    _WTWIN_WALK_INVOCATIONS["multistate"] = 0


# --------------------------------------------------------------------------
# Shared step core: three kernels every entry point in this module runs.
# --------------------------------------------------------------------------

def wtwin_learned_action_codes(regrets: np.ndarray) -> np.ndarray:
    """Vector form of ``_learned_action``/``_action_index`` (same tie rules)."""

    values = np.asarray(regrets, np.float64)
    enter, defer, passed = values[:, 0], values[:, 1], values[:, 2]
    codes = np.full(len(values), _WTWIN_PASS, np.int8)
    codes[defer <= passed] = _WTWIN_DEFER
    codes[enter < np.minimum(defer, passed)] = _WTWIN_ENTER
    return codes


def wtwin_state_action_codes(*, learned: np.ndarray, occupied: np.ndarray,
        entries_used: int, admission: AdmissionContract | None,
        component: np.ndarray, lower: np.ndarray) -> np.ndarray:
    """Vector form of ``tabular_policy.decide`` / the RAW branch of the walk.

    Column order is ``COMPONENT_STACK_NAMES`` (NOT ``ComponentPredictions``
    field order — the two diverge from index 7): 0 current_q20, 6 wall
    probability, 7 mae_q90.
    """

    codes = np.asarray(learned, np.int8).copy()
    if admission is not None:
        admitted = ((lower >= admission.action_advantage_threshold_usd)
                    & (component[:, 0] >= admission.minimum_current_q20_usd)
                    & (component[:, 6] <= admission.maximum_wall_probability)
                    & (component[:, 7] <= admission.maximum_adverse_q90_usd))
        codes[(codes == _WTWIN_ENTER) & ~admitted] = _WTWIN_DEFER
    # WHY the order is inverted against the oracle: tabular_policy.decide
    # tests asset_occupied FIRST (:60-62, DEFER) and the portfolio cap SECOND
    # (:63-65, PASS), so occupancy outranks the cap.  Vectorized, the LAST
    # assignment wins, so the same precedence requires writing the cap first
    # and occupancy after it.  Reordering these two statements silently
    # inverts a production precedence rule.
    if int(entries_used) >= C.MAX_ENTRIES_PORTFOLIO_DAY:
        codes[:] = _WTWIN_PASS
    codes[np.asarray(occupied, bool)] = _WTWIN_DEFER
    return codes


def wtwin_margin_action_codes(*, margin: np.ndarray, occupied: np.ndarray,
        entries_used: int, admission: AdmissionContract,
        component: np.ndarray) -> np.ndarray:
    """Vector form of ``tabular_policy.decide_margin`` (A1 spec item 1).

    No argmin pre-stage exists here, so every unoccupied row starts at DEFER
    and is promoted to ENTER only by the margin threshold plus the three risk
    gates.  Column order is ``COMPONENT_STACK_NAMES``: 0 current_q20, 6 wall
    probability, 7 mae_q90.  The cap/occupancy precedence is written in the
    same order as ``wtwin_state_action_codes`` and for the same reason.
    """

    admitted = ((np.asarray(margin, np.float64)
                 >= admission.action_advantage_threshold_usd)
                & (component[:, 0] >= admission.minimum_current_q20_usd)
                & (component[:, 6] <= admission.maximum_wall_probability)
                & (component[:, 7] <= admission.maximum_adverse_q90_usd))
    codes = np.where(admitted, _WTWIN_ENTER, _WTWIN_DEFER).astype(np.int8)
    if int(entries_used) >= C.MAX_ENTRIES_PORTFOLIO_DAY:
        codes[:] = _WTWIN_PASS
    codes[np.asarray(occupied, bool)] = _WTWIN_DEFER
    return codes


def wtwin_rank_entries(*, codes: np.ndarray, priority: np.ndarray,
        candidate_id: np.ndarray, asset: np.ndarray,
        entries_used: int) -> tuple[list[int], set[int]]:
    """One free seat per asset, portfolio cap, exact candidate-id tie-break."""

    best: dict[str, tuple[tuple[float, str], int]] = {}
    for local in np.flatnonzero(np.asarray(codes) == _WTWIN_ENTER).tolist():
        key = (-float(priority[local]), str(candidate_id[local]))
        name = str(asset[local])
        if name not in best or key < best[name][0]:
            best[name] = (key, local)
    ranked = sorted((value[1] for value in best.values()),
                    key=lambda local: (-float(priority[local]),
                                       str(candidate_id[local])))
    return ranked, set(ranked[:max(
        0, C.MAX_ENTRIES_PORTFOLIO_DAY - int(entries_used))])


# --------------------------------------------------------------------------
# Row-level contract parity: the oracle validates every visited row through
# ComponentPredictions.__post_init__ and PortfolioDecisionState.__post_init__.
# --------------------------------------------------------------------------

def _wtwin_check_components(component: np.ndarray, probability: np.ndarray,
        regrets: np.ndarray, lower: np.ndarray, mapped: np.ndarray) -> None:
    values = np.asarray(component, np.float64)
    regret = np.asarray(regrets, np.float64)
    bad = ~(np.isfinite(values).all(axis=1) & np.isfinite(probability)
            & np.isfinite(regret).all(axis=1) & np.isfinite(lower)
            & np.isfinite(mapped))
    bad |= ~((values[:, 6] >= 0) & (values[:, 6] <= 1))
    bad |= ~((probability >= 0) & (probability <= 1))
    bad |= np.minimum.reduce([values[:, 7], values[:, 8], values[:, 9],
                              regret[:, 0], regret[:, 1], regret[:, 2]]) < 0
    for low, high in ((0, 1), (1, 2), (3, 4), (4, 5), (8, 9)):
        bad |= values[:, low] > values[:, high]
    if bool(bad.any()):
        raise RecoveryRefusal("component predictions are malformed")


def _wtwin_check_states(*, plane: "_WtwinPlane", rows: np.ndarray, now: int,
        causal: np.ndarray, entries_used: int,
        counts: tuple[int, ...]) -> None:
    if (not plane.lawful_names
            or not np.all(np.isfinite(causal))
            or not np.all(plane.watch_last[plane.series_index[rows]] >= now)
            or not np.all(np.isin(plane.side[rows], (-1, 1)))
            or not np.all(np.asarray(plane.opportunity[rows], str) != "")
            or not np.all(np.asarray(plane.candidate[rows], str) != "")
            or not np.all(np.asarray(plane.series[rows], str) != "")
            or not np.all(np.asarray(plane.phase[rows], str) != "")
            or not np.all(np.isin(plane.asset[rows], C.ASSETS))
            or int(now) <= 0
            or not 0 <= int(entries_used) <= C.MAX_ENTRIES_PORTFOLIO_DAY
            or len(counts) != len(ACTIVE_WATCH_KEYS)
            or any(int(value) < 0 for value in counts)):
        raise RecoveryRefusal("portfolio decision state is malformed/leaking")


# --------------------------------------------------------------------------
# Plane and per-admission machine state.
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class _WtwinPlane:
    universe: DayOptionUniverse
    universe_representation: str
    trading_day: int
    feature_schema: CausalFeatureSchema
    component_model: object
    action_model: object
    mode: str
    policy_mode: str
    calibration: object | None
    plane: Mapping[str, np.ndarray]
    opportunity: np.ndarray
    series: np.ndarray
    candidate: np.ndarray
    asset: np.ndarray
    side: np.ndarray
    phase: np.ndarray
    timestamp: np.ndarray
    features: np.ndarray
    components: np.ndarray
    asset_index: np.ndarray
    series_index: np.ndarray
    series_keys: tuple[str, ...]
    watch_last: np.ndarray
    watches: Mapping[str, tuple[int, int, str, int]]
    universe_lookup: Mapping[str, int]
    by_timestamp: tuple[tuple[int, np.ndarray], ...]
    lawful_names: bool


@dataclass(slots=True)
class _WtwinMachine:
    admission: AdmissionContract | None
    watch_counter: _ActiveWatchCounter
    blocked: np.ndarray
    consumed: set[str] = field(default_factory=set)
    passed: set[str] = field(default_factory=set)
    entries: int = 0
    positions: dict[str, tuple[str, int, int, int]] = field(default_factory=dict)
    selected: list[str] = field(default_factory=list)
    arrivals: list[object] = field(default_factory=list)
    proposals: list[RolloutStateProposal] = field(default_factory=list)
    crossings: dict[str, set[int]] = field(default_factory=dict)
    changes: dict[str, set[int]] = field(default_factory=dict)
    seen: np.ndarray | None = None
    previous_ge: np.ndarray | None = None
    previous_code: np.ndarray | None = None


def _wtwin_build_plane(*, universe: DayOptionUniverse,
        dense_feature_shards: Sequence[CausalFeatureShard],
        feature_schema: CausalFeatureSchema, component_model: object,
        action_model: object, mode: str, calibration: object | None,
        admission_present: bool,
        policy_mode: str = "ARGMIN") -> _WtwinPlane:
    """Byte-for-byte the oracle's pre-walk setup (tabular_live_replay:280-325)."""

    universe.validate()
    mode = str(mode).upper()
    policy_mode = str(policy_mode).upper()
    policy_mode_core_key(policy_mode)
    if policy_mode == "MARGIN" and mode != "CALIBRATED":
        raise RecoveryRefusal("margin policy mode is CALIBRATED-only")
    if mode not in {"RAW", "CALIBRATED"}:
        raise RecoveryRefusal("live replay mode is unknown")
    if mode == "CALIBRATED" and (calibration is None or not admission_present):
        raise RecoveryRefusal("calibrated live replay lacks frozen artifacts")
    if mode == "RAW" and (calibration is not None or admission_present):
        raise RecoveryRefusal("raw replay cannot read calibration/threshold")
    if tuple(component_model.feature_names) != feature_schema.names:
        raise RecoveryRefusal("live component schema differs")
    trading_day = universe.trading_day
    universe_representation = universe.representation_sha256
    plane = _day_feature_plane(dense_feature_shards, feature_schema)
    if int(np.asarray(plane["day"], np.int64)[0]) != trading_day:
        raise RecoveryRefusal("live feature/outcome day differs")
    opportunity = np.asarray(plane["opportunity_id"], str)
    series = np.asarray(plane["series_id"], str)
    asset = np.asarray(plane["asset"], str)
    side = np.asarray(plane["side"], np.int8)
    phase = np.asarray(plane["phase"], str)
    timestamp = np.asarray(plane["snapshot_ts_ns"], np.int64)
    features = np.asarray(plane["features"], np.float32)
    universe_lookup = {str(value): index for index, value in enumerate(
        np.asarray(universe.opportunity_id, str))}
    covered = walkable_row_mask(opportunity=opportunity, series=series,
        timestamp=timestamp, universe_ids=frozenset(universe_lookup))
    components = np.asarray(component_model.predict(features).values, np.float64)
    watches = _watch_metadata(series, timestamp, asset, side)
    series_keys = tuple(sorted(watches))
    series_position = {key: index for index, key in enumerate(series_keys)}
    series_index = np.asarray([series_position[str(value)]
                               for value in series.tolist()], np.int64)
    watch_last = np.asarray([watches[key][1] for key in series_keys], np.int64)
    asset_index = np.asarray([C.ASSET_INDEX[str(value)]
                              for value in asset.tolist()], np.int64)
    grouped: dict[int, list[int]] = {}
    for index, value in enumerate(timestamp):
        if covered[index]:
            grouped.setdefault(int(value), []).append(index)
    by_timestamp = tuple((now, np.asarray(rows, np.int64))
                         for now, rows in sorted(grouped.items()))
    return _WtwinPlane(universe=universe,
        universe_representation=universe_representation,
        trading_day=trading_day, feature_schema=feature_schema,
        component_model=component_model, action_model=action_model, mode=mode,
        policy_mode=policy_mode,
        calibration=calibration, plane=plane, opportunity=opportunity,
        series=series, candidate=np.asarray(plane["candidate_id"], str),
        asset=asset, side=side, phase=phase, timestamp=timestamp,
        features=features, components=components, asset_index=asset_index,
        series_index=series_index, series_keys=series_keys,
        watch_last=watch_last, watches=watches,
        universe_lookup=universe_lookup, by_timestamp=by_timestamp,
        lawful_names=_lawful_state_feature_names(tuple(feature_schema.names)))


def _wtwin_new_machine(plane: _WtwinPlane,
                       admission: AdmissionContract | None) -> _WtwinMachine:
    width = len(plane.series_keys)
    return _WtwinMachine(admission=admission,
        watch_counter=_ActiveWatchCounter(plane.watches),
        blocked=np.zeros(width, bool), seen=np.zeros(width, bool),
        previous_ge=np.zeros(width, bool),
        previous_code=np.zeros(width, np.int8))


# --------------------------------------------------------------------------
# Scoring: shared by every machine that reaches a timestamp in the same state.
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class _WtwinScores:
    causal: np.ndarray
    component: np.ndarray
    regrets: np.ndarray
    mapped: np.ndarray
    lower: np.ndarray
    probability: np.ndarray
    regime_names: np.ndarray
    learned: np.ndarray
    margin: np.ndarray


def _wtwin_score_rows(plane: _WtwinPlane, *, now: int, rows: np.ndarray,
        entries: int, causal_open: tuple[int, ...],
        counts: tuple[int, ...]) -> _WtwinScores:
    causal = plane.features[rows]
    component = plane.components[rows]
    action_names, action_x = build_action_feature_matrix(
        causal_feature_names=plane.feature_schema.names, causal_matrix=causal,
        component_predictions=component, asset=plane.asset[rows],
        snapshot_ts_ns=np.full(len(rows), now, np.int64),
        entries_used=np.full(len(rows), entries, np.int8),
        open_until_ts_ns=np.asarray([causal_open] * len(rows), np.int64),
        active_watches_by_asset_side=np.asarray([counts] * len(rows), np.int16),
        phase=plane.phase[rows])
    if action_names != tuple(plane.action_model.feature_names):
        raise RecoveryRefusal("live action schema differs")
    regrets = predict_action_regret(plane.action_model, action_x,
                                    trading_day=plane.trading_day)
    if regrets.shape != (len(rows), 3) or not np.all(np.isfinite(regrets)):
        raise RecoveryRefusal("live action regret output differs")
    raw_advantage = np.minimum(regrets[:, 1], regrets[:, 2]) - regrets[:, 0]
    regime = qrf4_regime_matrix(plane.feature_schema.names, causal)
    regime_names = _WTWIN_REGIME_NAMES[np.argmax(regime, axis=1)]
    if plane.mode == "CALIBRATED":
        calibration = plane.calibration
        group = (calibration_group_key(
            entries_used=np.full(len(rows), entries), phase=plane.phase[rows],
            regime=regime_names) if calibration.state_conditioned else None)
        mapped = calibration.predict_dollars(raw_advantage, group_key=group)
        lower = calibration.predict_lower(raw_advantage, group_key=group)
        probability = calibration.enter_optimal_platt.predict(raw_advantage)
    else:
        mapped = raw_advantage.copy()
        lower = raw_advantage.copy()
        probability = 1.0 / (1.0 + np.exp(
            -np.clip(raw_advantage / 600.0, -40, 40)))
    _wtwin_check_components(component, probability, regrets, lower, mapped)
    _wtwin_check_states(plane=plane, rows=rows, now=now, causal=causal,
                        entries_used=entries, counts=counts)
    return _WtwinScores(causal=causal, component=component, regrets=regrets,
        mapped=mapped, lower=lower, probability=probability,
        regime_names=regime_names,
        learned=wtwin_learned_action_codes(regrets),
        margin=regrets[:, 1] - regrets[:, 0])


def _wtwin_decision_state(plane: _WtwinPlane, scores: _WtwinScores,
        rows: np.ndarray, local: int, *, now: int, entries: int,
        open_states: tuple[OpenPositionState, ...],
        counts: tuple[int, ...]) -> PortfolioDecisionState:
    row = int(rows[local])
    prediction = ComponentPredictions(
        *map(float, scores.component[local, :7]),
        float(scores.probability[local]),
        *map(float, scores.component[local, 7:]),
        *map(float, scores.regrets[local]),
        float(scores.lower[local]), float(scores.mapped[local]))
    return PortfolioDecisionState(str(plane.candidate[row]),
        str(plane.series[row]), str(plane.asset[row]), plane.trading_day,
        int(plane.side[row]), now, plane.watches[str(plane.series[row])][1],
        plane.feature_schema.names, tuple(scores.causal[local].tolist()),
        prediction, entries, open_states, counts, str(plane.phase[row]),
        str(scores.regime_names[local]))


# --------------------------------------------------------------------------
# The walk itself.
# --------------------------------------------------------------------------

def _wtwin_apply(plane: _WtwinPlane, machine: _WtwinMachine, *, now: int,
        rows: np.ndarray, counts: tuple[int, ...],
        causal_open: tuple[int, ...], condition: PortfolioPrefixCondition,
        scores: _WtwinScores, collect_proposals: bool) -> None:
    entries_at_start = machine.entries
    open_states = tuple(OpenPositionState(name, value[0], value[1], value[3])
                        for name, value in sorted(machine.positions.items()))
    causal_open_array = np.asarray(causal_open, np.int64)
    occupied = causal_open_array[plane.asset_index[rows]] >= now
    if plane.policy_mode == "MARGIN":
        # PolicyDecision.incremental_dollars_usd carries the margin, so the
        # per-second best-per-asset competition ranks by it (A1 spec item 1).
        priority = scores.margin
        codes = wtwin_margin_action_codes(margin=scores.margin,
            occupied=occupied, entries_used=entries_at_start,
            admission=machine.admission, component=scores.component)
    else:
        priority = scores.mapped
        codes = wtwin_state_action_codes(learned=scores.learned,
            occupied=occupied, entries_used=entries_at_start,
            admission=machine.admission, component=scores.component,
            lower=scores.lower)
    candidate = plane.candidate[rows]
    ranked, chosen = wtwin_rank_entries(codes=codes, priority=priority,
        candidate_id=candidate, asset=plane.asset[rows],
        entries_used=entries_at_start)
    final = codes.copy()
    if chosen:
        keep = np.zeros(len(codes), bool)
        keep[np.asarray(sorted(chosen), np.int64)] = True
        final[(codes == _WTWIN_ENTER) & ~keep] = _WTWIN_DEFER
    else:
        final[codes == _WTWIN_ENTER] = _WTWIN_DEFER

    local_series = plane.series_index[rows]
    threshold = (machine.admission.action_advantage_threshold_usd
                 if machine.admission is not None else 0.0)
    current_ge = np.asarray(scores.lower, np.float64) >= threshold
    seen = machine.seen[local_series]
    for local in np.flatnonzero(
            seen & (machine.previous_ge[local_series] != current_ge)).tolist():
        machine.crossings.setdefault(
            str(plane.series[rows[local]]), set()).add(now)
    for local in np.flatnonzero(
            seen & (machine.previous_code[local_series] != final)).tolist():
        machine.changes.setdefault(
            str(plane.series[rows[local]]), set()).add(now)
    machine.seen[local_series] = True
    machine.previous_ge[local_series] = current_ge
    machine.previous_code[local_series] = final

    if collect_proposals:
        opportunity = plane.opportunity[rows]
        machine.proposals.extend(
            RolloutStateProposal(str(opportunity[local]), condition,
                                 WTWIN_ACTION_BY_CODE[int(final[local])])
            for local in range(len(rows)))

    for local in np.flatnonzero(final == _WTWIN_PASS).tolist():
        key = str(plane.series[rows[local]])
        machine.passed.add(key)
        machine.blocked[local_series[local]] = True
        machine.watch_counter.block(key)

    for local in ranked:
        if local not in chosen:
            continue
        row = int(rows[local])
        uid = str(plane.opportunity[row])
        index = plane.universe_lookup[uid]
        key = str(plane.series[row])
        name = str(plane.asset[row])
        machine.consumed.add(key)
        machine.blocked[local_series[local]] = True
        machine.watch_counter.block(key)
        machine.entries += 1
        machine.positions[name] = (key, now,
            int(plane.universe.exit_ts_ns[index]),
            int(plane.universe.phase_close_ts_ns[index]))
        base = _arrival(plane.universe, index,
                        str(plane.action_model.receipt_sha256), enter=True)
        state = _wtwin_decision_state(plane, scores, rows, local, now=now,
            entries=entries_at_start, open_states=open_states, counts=counts)
        probability = float(state.components.enter_probability)
        score = EntryScore(candidate_id=base.example.candidate_id,
            asset=base.example.asset, decision_ts_ns=now,
            model_hash=str(plane.action_model.receipt_sha256),
            priority_score=float(priority[local]),
            take_probability=probability,
            expected_pnl_usd=state.components.current_q50_usd,
            expected_pnl_lower_usd=state.components.current_q20_usd,
            top3_probability=probability,
            mae_p90_usd=state.components.mae_q90_usd,
            wall_probability=state.components.wall_probability, enter=True)
        machine.arrivals.append(_label_free_live_arrival(base, score))
        machine.selected.append(uid)


def _wtwin_walk(plane: _WtwinPlane, machines: Sequence[_WtwinMachine],
                collect_proposals: bool) -> None:
    for now, raw_rows in plane.by_timestamp:
        pending: dict[object, list[tuple[_WtwinMachine, np.ndarray,
                                         tuple[int, ...], tuple[int, ...],
                                         PortfolioPrefixCondition]]] = {}
        for machine in machines:
            for position_asset, value in tuple(machine.positions.items()):
                if value[2] < now:
                    machine.positions.pop(position_asset)
            rows = raw_rows[~machine.blocked[plane.series_index[raw_rows]]]
            if not len(rows):
                continue
            counts = machine.watch_counter.counts_at(now)
            realized_open = tuple(machine.positions.get(name, ("", 0, -1, -1))[2]
                                  for name in C.ASSETS)
            causal_open = tuple(machine.positions.get(name, ("", 0, -1, -1))[3]
                                for name in C.ASSETS)
            condition = PortfolioPrefixCondition(plane.trading_day, now,
                machine.entries, realized_open, causal_open,
                tuple(sorted(machine.consumed)), tuple(sorted(machine.passed)))
            key = (rows.tobytes(), machine.entries, causal_open, counts)
            pending.setdefault(key, []).append(
                (machine, rows, counts, causal_open, condition))
        for members in pending.values():
            head = members[0]
            scores = _wtwin_score_rows(plane, now=now, rows=head[1],
                entries=head[0].entries, causal_open=head[3], counts=head[2])
            for machine, rows, counts, causal_open, condition in members:
                _wtwin_apply(plane, machine, now=now, rows=rows, counts=counts,
                    causal_open=causal_open, condition=condition,
                    scores=scores, collect_proposals=collect_proposals)


def _wtwin_trace(plane: _WtwinPlane, machine: _WtwinMachine,
        dense_feature_shards: Sequence[CausalFeatureShard]) -> PolicyDayTrace:
    fallback_base = _arrival(plane.universe, 0,
                             str(plane.action_model.receipt_sha256), enter=False)
    fallback = _label_free_live_arrival(fallback_base, fallback_base.score)
    crossing_frozen = MappingProxyType({key: tuple(sorted(value))
        for key, value in sorted(machine.crossings.items())})
    change_frozen = MappingProxyType({key: tuple(sorted(value))
        for key, value in sorted(machine.changes.items())})
    calibration = plane.calibration
    admission = machine.admission
    shard_receipts = tuple(sorted(row.representation_sha256
                                  for row in dense_feature_shards))
    core = {"schema": LIVE_REPLAY_SCHEMA, "day": plane.trading_day,
        "mode": plane.mode,
        "calibration": (None if calibration is None
                        else calibration.receipt_sha256),
        "admission": None if admission is None else admission.receipt_sha256,
        "selected": tuple(machine.selected),
        "component": plane.component_model.receipt_sha256,
        "action": plane.action_model.receipt_sha256,
        "feature_schema": plane.feature_schema.receipt_sha256,
        "source_universe": plane.universe_representation,
        "feature_shards": shard_receipts,
        "arrivals": tuple(_arrival_payload(row) for row in machine.arrivals),
        "rejected_fallback": _arrival_payload(fallback),
        "proposals": tuple((row.opportunity_id, row.condition.receipt_sha256,
                            row.predicted_action.value)
                           for row in machine.proposals),
        "crossings": dict(crossing_frozen),
        "action_changes": dict(change_frozen),
        **policy_mode_core_key(plane.policy_mode), "h2_open_count": 0}
    result = PolicyDayTrace(plane.trading_day, plane.mode,
        None if calibration is None else calibration.receipt_sha256,
        None if admission is None else admission.receipt_sha256,
        tuple(machine.selected), tuple(machine.arrivals), fallback,
        tuple(machine.proposals), crossing_frozen, change_frozen,
        plane.component_model.receipt_sha256,
        plane.action_model.receipt_sha256,
        plane.feature_schema.receipt_sha256, plane.universe_representation,
        shard_receipts, C.object_sha256(core), plane.policy_mode)
    result.__post_init__()
    return result


def replay_policy_day_twin(*, universe: DayOptionUniverse,
        dense_feature_shards: Sequence[CausalFeatureShard],
        feature_schema: CausalFeatureSchema, component_model: object,
        action_model: object, mode: str,
        calibration: CalibrationBundle | None = None,
        admission: AdmissionContract | None = None,
        collect_proposals: bool = False,
        policy_mode: str = "ARGMIN") -> PolicyDayTrace:
    """Drop-in twin of ``tabular_live_replay.replay_policy_day``."""

    plane = _wtwin_build_plane(universe=universe,
        dense_feature_shards=dense_feature_shards,
        feature_schema=feature_schema, component_model=component_model,
        action_model=action_model, mode=mode, calibration=calibration,
        admission_present=admission is not None, policy_mode=policy_mode)
    machine = _wtwin_new_machine(plane, admission)
    _wtwin_walk(plane, (machine,), collect_proposals)
    return _wtwin_trace(plane, machine, dense_feature_shards)


def replay_policy_day_multistate(*, admissions: Sequence[AdmissionContract],
        universe: DayOptionUniverse,
        dense_feature_shards: Sequence[CausalFeatureShard],
        feature_schema: CausalFeatureSchema, component_model: object,
        action_model: object,
        calibration: CalibrationBundle,
        policy_mode: str = "ARGMIN") -> tuple[PolicyDayTrace, ...]:
    """One row scan carrying N independent CALIBRATED admission machines.

    Machines that reach a timestamp in the same walk state (identical live
    row set, entries used, causal occupancy and active-watch counts) share
    one action-feature build and one CatBoost dispatch; every decision after
    that is taken per machine from its own admission contract.  Lossless by
    construction — the shared inputs are exactly the inputs each sequential
    walk would have built for itself.
    """

    rows = tuple(admissions)
    if not rows:
        raise RecoveryRefusal("multistate walk has no admission contracts")
    plane = _wtwin_build_plane(universe=universe,
        dense_feature_shards=dense_feature_shards,
        feature_schema=feature_schema, component_model=component_model,
        action_model=action_model, mode="CALIBRATED", calibration=calibration,
        admission_present=True, policy_mode=policy_mode)
    machines = tuple(_wtwin_new_machine(plane, admission) for admission in rows)
    _WTWIN_WALK_INVOCATIONS["multistate"] += 1
    # Proposals are a rollout-only output; the eval theta loop that is the sole
    # caller passes collect_proposals=False, so the parameter is not offered.
    _wtwin_walk(plane, machines, False)
    return tuple(_wtwin_trace(plane, machine, dense_feature_shards)
                 for machine in machines)


# --------------------------------------------------------------------------
# Cached theta loop (WALK_TWIN_SWAP_SPEC Edit 1).  Lives here, not in
# tabular_evaluation.py, so the reviewed bytes are the ones that ship: the
# freeze edit in tabular_evaluation.py is then an import plus a loop rewrite.
# --------------------------------------------------------------------------

def _wtwin_multistate_targets(*, day: int, universe: DayOptionUniverse,
        component_receipt: str, action_receipt: str,
        feature_schema: CausalFeatureSchema, calibration: CalibrationBundle,
        admissions: Sequence[AdmissionContract],
        output_root: object) -> tuple[Path, ...]:
    """The per-theta trace paths, byte-identical to ``_load_or_replay_day``'s.

    WHY the private import: the target path IS the trace-cache identity, and an
    identity computed by a local copy of ``_trace_identity`` would fork the
    cache silently the first time either copy changed.  Imported at call time
    rather than at module scope so this module stays importable by tools that
    must not pull in the evaluation stack.
    """

    from .tabular_evaluation import _trace_identity
    root = Path(output_root)
    return tuple(
        root / "calibrated" / _trace_identity(
            day=day, mode="CALIBRATED", universe=universe,
            component_receipt=component_receipt, action_receipt=action_receipt,
            feature_schema=feature_schema, calibration=calibration,
            admission=admission) / f"{day}.json"
        for admission in admissions)


def wtwin_load_or_replay_day_multistate(*, day: int,
        universe: DayOptionUniverse, feature_schema: CausalFeatureSchema,
        component_fold: object, action_fold: object, output_root: object,
        calibration: CalibrationBundle,
        admissions: Sequence[AdmissionContract],
        dense_features: Sequence[CausalFeatureShard] | None,
        ) -> tuple[PolicyDayTrace, ...]:
    """One day's per-theta traces: cache-consulting wrapper over the twin."""

    rows = tuple(admissions)
    if not rows:
        raise RecoveryRefusal("multistate walk has no admission contracts")
    # (1) Strict-load BOTH fold bundles BEFORE any cache consult.  A warm cache
    # must never be able to hide a bundle whose bytes no longer match the
    # roster receipt (mirrors tabular_evaluation.py:194-206).
    component = load_component_model(component_fold.bundle_path)
    action = load_action_model(action_fold.bundle_path)
    if (component.receipt_sha256 != component_fold.bundle_receipt_sha256
            or action.receipt_sha256 != action_fold.bundle_receipt_sha256):
        raise RecoveryRefusal("policy replay fold model strict load differs")
    # (2) Identity from the LOADED receipts, never from the roster's claim.
    targets = _wtwin_multistate_targets(day=day, universe=universe,
        component_receipt=component.receipt_sha256,
        action_receipt=action.receipt_sha256, feature_schema=feature_schema,
        calibration=calibration, admissions=rows, output_root=output_root)
    cached: dict[int, PolicyDayTrace] = {}
    for index, target in enumerate(targets):
        if not target.is_file():
            continue
        trace = load_policy_day_trace(target)
        if (trace.source_universe_sha256 != universe.representation_sha256
                or trace.component_model_sha256 != component.receipt_sha256
                or trace.action_model_sha256 != action.receipt_sha256
                or trace.feature_schema_sha256 != feature_schema.receipt_sha256):
            raise RecoveryRefusal("resumed policy trace inputs differ")
        cached[index] = trace
    # (3) Every target present ⇒ the walk is not run at all.
    if len(cached) == len(rows):
        return tuple(cached[index] for index in range(len(rows)))
    dense = tuple(dense_features) if dense_features else ()
    if not dense:
        raise RecoveryRefusal("multistate walk has no dense causal shards")
    fresh = replay_policy_day_multistate(admissions=rows, universe=universe,
        dense_feature_shards=dense, feature_schema=feature_schema,
        component_model=component, action_model=action,
        calibration=calibration)
    # (4) The walk owes exactly one trace per admission.
    if len(fresh) != len(rows):
        raise RecoveryRefusal(
            f"multistate walk trace count differs: {len(fresh)} traces for "
            f"{len(rows)} admission contracts")
    for index, (trace, target) in enumerate(zip(fresh, targets)):
        if index in cached:
            # A pre-existing target the fresh walk reproduces differently is a
            # defect in the twin or the cache, not a cache miss.  Refuse.
            if trace.receipt_sha256 != cached[index].receipt_sha256:
                raise RecoveryRefusal(
                    f"cached multistate trace receipt differs at {target}: "
                    f"cached {cached[index].receipt_sha256} vs fresh "
                    f"{trace.receipt_sha256}")
            continue
        save_policy_day_trace(trace, target)
        stored = load_policy_day_trace(target)
        if stored.receipt_sha256 != trace.receipt_sha256:
            raise RecoveryRefusal("policy day trace strict reload differs")
    return tuple(fresh)


__all__ = ["WTWIN_ACTION_BY_CODE", "replay_policy_day_multistate",
           "replay_policy_day_twin", "wtwin_learned_action_codes",
           "wtwin_load_or_replay_day_multistate", "wtwin_margin_action_codes",
           "wtwin_rank_entries", "wtwin_reset_walk_invocations",
           "wtwin_state_action_codes", "wtwin_walk_invocations"]
