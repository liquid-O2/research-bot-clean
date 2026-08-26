"""Exact delayed portfolio teacher and conditioned ENTER/DEFER/PASS values.

Future information is confined to this module's artifacts.  Production model
and policy modules import only the label-free contracts and never import this
module.  One MILP authority is reused for the daily ceiling and every suffix
action value; no weighted-interval proxy is permitted here.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from types import MappingProxyType
from typing import Final, Iterable, Mapping, Sequence

import numpy as np

from . import common as C
from .contracts import (
    CausalEntryExample, EntryScore, RawPrefixRef, SessionRef, Side,
)
from .exact_teacher_build import (
    _action_query_indices, _component_indices, _component_targets,
    _prefix_condition_for_schedule,
)
from .exact_teacher_solver import ExactDaySolver
from .exact_teacher_types import (
    ACTION_SOURCE_NAMES, ActionQuery, DayOptionUniverse, _hash_array, _sha,
)
from .replay import ReplayOutcome, ScoredArrival, replay
from .tabular_recovery_contracts import (
    ACTIVE_WATCH_KEYS, DecisionAction, RecoveryRefusal,
)

TEACHER_DAY_SCHEMA: Final = "QRE2EXACTDELAYEDTEACHER2"
TEACHER_MANIFEST_SCHEMA: Final = "QRE2EXACTDELAYEDTEACHERMANIFEST2"

@dataclass(frozen=True, slots=True)
class ExactDelayedTeacherDay:
    trading_day: int
    source_universe_sha256: str
    solver_receipt_sha256: str
    exact_objective_cents: int
    selected_opportunity_ids: tuple[str, ...]
    selected_series_ids: tuple[str, ...]
    selected_snapshot_ts_ns: tuple[int, ...]
    component_opportunity_id: np.ndarray
    current_entry_usd: np.ndarray
    continuation_120_usd: np.ndarray
    continuation_observed: np.ndarray
    wall_target: np.ndarray
    mae_usd: np.ndarray
    occupancy_sec: np.ndarray
    action_opportunity_id: np.ndarray
    action_condition_receipt_sha256: np.ndarray
    action_source: np.ndarray
    action_rollout_round: np.ndarray
    action_entries_used: np.ndarray
    action_open_until_ts_ns: np.ndarray
    action_active_watches_by_asset_side: np.ndarray
    q_enter_cents: np.ndarray
    q_defer_cents: np.ndarray
    q_pass_cents: np.ndarray
    regret_enter_cents: np.ndarray
    regret_defer_cents: np.ndarray
    regret_pass_cents: np.ndarray
    optimal_action: np.ndarray
    action_margin_cents: np.ndarray
    representation_sha256_stored: str = ""

    def validate(self) -> None:
        C.guard_date(int(self.trading_day))
        component_n = len(self.component_opportunity_id)
        component_fields = tuple(getattr(self, name) for name in (
            "current_entry_usd", "continuation_120_usd",
            "continuation_observed", "wall_target", "mae_usd", "occupancy_sec"))
        action_n = len(self.action_opportunity_id)
        action_fields = tuple(getattr(self, name) for name in (
            "action_condition_receipt_sha256", "action_source",
            "action_rollout_round", "q_enter_cents", "q_defer_cents",
            "q_pass_cents", "regret_enter_cents", "regret_defer_cents",
            "regret_pass_cents", "optimal_action", "action_margin_cents"))
        if (not _sha(self.source_universe_sha256)
                or not _sha(self.solver_receipt_sha256)
                or self.exact_objective_cents < 0
                or len(self.selected_opportunity_ids)
                   != len(self.selected_series_ids)
                or len(self.selected_opportunity_ids)
                   != len(self.selected_snapshot_ts_ns)
                or len(set(self.selected_opportunity_ids))
                   != len(self.selected_opportunity_ids)
                or len(set(self.selected_series_ids)) != len(self.selected_series_ids)
                or component_n == 0
                or any(np.asarray(value).shape != (component_n,)
                       for value in component_fields)
                or len(set(np.asarray(self.component_opportunity_id, str).tolist()))
                   != component_n
                or not np.all(np.isfinite(self.current_entry_usd))
                or not np.all(np.isfinite(self.continuation_120_usd))
                or not np.all(np.asarray(self.mae_usd) >= 0)
                or not np.all(np.asarray(self.occupancy_sec) >= 0)
                or any(np.asarray(value).shape != (action_n,)
                       for value in action_fields)
                or np.asarray(self.action_entries_used).shape != (action_n,)
                or np.asarray(self.action_open_until_ts_ns).shape != (action_n, 3)
                or np.asarray(self.action_active_watches_by_asset_side).shape \
                   != (action_n, 6)
                or np.any(np.asarray(self.action_entries_used) < 0)
                or np.any(np.asarray(self.action_entries_used)
                          > C.MAX_ENTRIES_PORTFOLIO_DAY)
                or np.any(np.asarray(self.action_open_until_ts_ns) < -1)
                or np.any(np.asarray(
                    self.action_active_watches_by_asset_side) < 0)
                or len(set(zip(
                    np.asarray(self.action_opportunity_id, str).tolist(),
                    np.asarray(self.action_condition_receipt_sha256, str).tolist())))
                   != action_n
                or any(value not in ACTION_SOURCE_NAMES
                       for value in np.asarray(self.action_source, str))
                or not np.all(np.isin(self.action_rollout_round, (0, 1, 2)))
                or not np.all(np.isin(
                    self.optimal_action,
                    tuple(action.value for action in DecisionAction)))):
            raise RecoveryRefusal("exact delayed teacher day is malformed")
        q = np.column_stack((self.q_enter_cents, self.q_defer_cents,
                             self.q_pass_cents)).astype(np.int64)
        regret = np.column_stack((self.regret_enter_cents,
                                  self.regret_defer_cents,
                                  self.regret_pass_cents)).astype(np.int64)
        expected = q.max(axis=1, keepdims=True) - q
        sorted_q = np.sort(q, axis=1)
        if (not np.array_equal(regret, expected)
                or not np.array_equal(
                    np.asarray(self.action_margin_cents, np.int64),
                    sorted_q[:, -1] - sorted_q[:, -2])):
            raise RecoveryRefusal("teacher action regret/margin identities differ")
        if self.representation_sha256_stored:
            if (not _sha(self.representation_sha256_stored)
                    or self.representation_sha256_stored
                       != self._representation_sha256(include_stored=False)):
                raise RecoveryRefusal("teacher stored representation differs")

    @staticmethod
    def array_fields() -> tuple[str, ...]:
        return (
            "component_opportunity_id", "current_entry_usd",
            "continuation_120_usd", "continuation_observed", "wall_target",
            "mae_usd", "occupancy_sec", "action_opportunity_id",
            "action_condition_receipt_sha256", "action_source",
            "action_rollout_round", "action_entries_used",
            "action_open_until_ts_ns", "action_active_watches_by_asset_side",
            "q_enter_cents", "q_defer_cents", "q_pass_cents",
            "regret_enter_cents", "regret_defer_cents",
            "regret_pass_cents", "optimal_action", "action_margin_cents")

    def _representation_sha256(self, *, include_stored: bool = False) -> str:
        digest = hashlib.sha256()
        digest.update(TEACHER_DAY_SCHEMA.encode())
        digest.update(str(self.trading_day).encode())
        digest.update(self.source_universe_sha256.encode())
        digest.update(self.solver_receipt_sha256.encode())
        digest.update(str(self.exact_objective_cents).encode())
        digest.update(repr(self.selected_opportunity_ids).encode())
        digest.update(repr(self.selected_series_ids).encode())
        digest.update(repr(self.selected_snapshot_ts_ns).encode())
        for name in self.array_fields():
            _hash_array(digest, np.asarray(getattr(self, name)))
        if include_stored:
            digest.update(self.representation_sha256_stored.encode())
        return digest.hexdigest()

    @property
    def representation_sha256(self) -> str:
        self.validate(); return self._representation_sha256(include_stored=False)

    def save(self, path: os.PathLike[str] | str) -> str:
        self.validate()
        target = C.assert_workspace_output(path)
        if target.suffix != ".npz":
            raise RecoveryRefusal("teacher day path must be .npz")
        target.parent.mkdir(parents=True, exist_ok=True)
        representation = self._representation_sha256(include_stored=False)
        tmp = target.with_name(target.name + f".tmp.{os.getpid()}")
        with tmp.open("xb") as handle:
            np.savez_compressed(
                handle, **{name: np.asarray(getattr(self, name))
                           for name in self.array_fields()},
                schema=np.asarray([TEACHER_DAY_SCHEMA], str),
                trading_day=np.asarray([self.trading_day], np.int64),
                source_universe_sha256=np.asarray(
                    [self.source_universe_sha256], str),
                solver_receipt_sha256=np.asarray([self.solver_receipt_sha256], str),
                exact_objective_cents=np.asarray(
                    [self.exact_objective_cents], np.int64),
                selected_opportunity_ids=np.asarray(
                    self.selected_opportunity_ids, str),
                selected_series_ids=np.asarray(self.selected_series_ids, str),
                selected_snapshot_ts_ns=np.asarray(
                    self.selected_snapshot_ts_ns, np.int64),
                representation_sha256=np.asarray([representation], str))
            handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, target)
        return C.file_sha256(target)

    @classmethod
    def load(cls, path: os.PathLike[str] | str) -> "ExactDelayedTeacherDay":
        source = Path(path); C.guard_payload(source)
        try:
            with np.load(source, allow_pickle=False) as values:
                if str(values["schema"][0]) != TEACHER_DAY_SCHEMA:
                    raise RecoveryRefusal("teacher day schema differs")
                result = cls(
                    trading_day=int(values["trading_day"][0]),
                    source_universe_sha256=str(
                        values["source_universe_sha256"][0]),
                    solver_receipt_sha256=str(
                        values["solver_receipt_sha256"][0]),
                    exact_objective_cents=int(values["exact_objective_cents"][0]),
                    selected_opportunity_ids=tuple(
                        values["selected_opportunity_ids"].astype(str).tolist()),
                    selected_series_ids=tuple(
                        values["selected_series_ids"].astype(str).tolist()),
                    selected_snapshot_ts_ns=tuple(
                        values["selected_snapshot_ts_ns"].astype(np.int64).tolist()),
                    **{name: values[name] for name in cls.array_fields()},
                    representation_sha256_stored=str(
                        values["representation_sha256"][0]))
        except (OSError, ValueError, KeyError) as exc:
            raise RecoveryRefusal("cannot strict-load exact teacher day") from exc
        result.validate(); return result


def build_exact_delayed_teacher_day(
    universe: DayOptionUniverse,
) -> tuple[ExactDelayedTeacherDay, ExactDaySolver]:
    """Solve one day and publish component plus exact action supervision."""

    universe.validate()
    solver = ExactDaySolver(universe)
    solution = solver.exact_schedule()
    interval_match_receipt = solver.authorize_interval_suffix_solver(solution)
    selected = tuple(map(int, solution.selected_indices))
    selected_ids = tuple(str(universe.opportunity_id[index]) for index in selected)
    selected_series = tuple(str(universe.series_id[index]) for index in selected)
    selected_ts = tuple(int(universe.snapshot_ts_ns[index]) for index in selected)
    if len(selected_series) != len(set(selected_series)):
        raise RecoveryRefusal("exact schedule selected a series twice")
    component_indices = _component_indices(universe, selected)
    component = _component_targets(universe, component_indices)
    action_indices = _action_query_indices(universe, selected)
    action_values: list[tuple[int, int, int]] = []
    regrets: list[tuple[int, int, int]] = []
    actions: list[str] = []
    margins: list[int] = []
    condition_receipts: list[str] = []
    sources: list[str] = []
    entries_used: list[int] = []
    open_until_rows: list[tuple[int, int, int]] = []
    active_watch_rows: list[tuple[int, ...]] = []
    selected_set = set(selected_ids)
    selected_series_to_ts = dict(zip(selected_series, selected_ts))
    for index, source in action_indices.items():
        timestamp = int(universe.snapshot_ts_ns[index])
        condition = _prefix_condition_for_schedule(universe, selected, timestamp)
        query = ActionQuery(
            str(universe.opportunity_id[index]), condition, source, 0)
        enter, defer, passed, action, row_regrets = solver.action_values(query)
        opportunity = str(universe.opportunity_id[index])
        series_id = str(universe.series_id[index])
        values = (enter, defer, passed)
        best = max(values)
        # Bind exact schedule membership on Q ties.  Non-tied rows retain the
        # value-optimal conservative action.
        if opportunity in selected_set:
            if enter != best:
                raise RecoveryRefusal("selected exact action is not Q-optimal")
            action = DecisionAction.ENTER
        elif selected_series_to_ts.get(series_id, -1) > timestamp and defer == best:
            action = DecisionAction.DEFER
        elif passed == best:
            action = DecisionAction.PASS
        action_values.append(values); regrets.append(row_regrets)
        actions.append(action.value)
        ordered = sorted(values)
        margins.append(int(ordered[-1] - ordered[-2]))
        condition_receipts.append(condition.receipt_sha256); sources.append(source)
        entries_used.append(condition.entries_used)
        open_until_rows.append(condition.causal_open_until_by_asset)
        active_watch_rows.append(solver.active_watch_counts(condition))
    q = np.asarray(action_values, np.int64).reshape((-1, 3))
    r = np.asarray(regrets, np.int64).reshape((-1, 3))
    solver_core = {
        "schema": "QRE2EXACTDAYSOLVER1",
        "universe": universe.representation_sha256,
        "nondominated_options": len(solver.indices),
        "original_options": len(universe.opportunity_id),
        "daily_cap": C.MAX_ENTRIES_PORTFOLIO_DAY,
        "asset_occupancy": 1,
        "closed_intervals": True,
        "series_uniqueness": True,
        "cent_objective": True,
        "canonical_candidate_id_tie_break": True,
        "solution_receipt_sha256": solution.receipt_sha256,
        "suffix_engine": "EXACT_CLOSED_INTERVAL_COUNT_DP",
        "interval_milp_match_receipt_sha256": interval_match_receipt,
        "series_constraint_redundant_under_k1": True,
        "snapshot_removal_frontier_rebuilt": True,
        "published_open_until": "CAUSAL_SCHEDULED_PHASE_CLOSE_WHILE_ACTIVE",
        "realized_exit_confined_to_suffix_solver": True,
    }
    result = ExactDelayedTeacherDay(
        trading_day=universe.trading_day,
        source_universe_sha256=universe.representation_sha256,
        solver_receipt_sha256=C.object_sha256(solver_core),
        exact_objective_cents=solution.objective_cents,
        selected_opportunity_ids=selected_ids,
        selected_series_ids=selected_series,
        selected_snapshot_ts_ns=selected_ts,
        **component,
        action_opportunity_id=np.asarray(
            [str(universe.opportunity_id[index]) for index in action_indices], str),
        action_condition_receipt_sha256=np.asarray(condition_receipts, str),
        action_source=np.asarray(sources, str),
        action_rollout_round=np.zeros(len(action_indices), np.int8),
        action_entries_used=np.asarray(entries_used, np.int8),
        action_open_until_ts_ns=np.asarray(
            open_until_rows, np.int64).reshape((-1, len(C.ASSETS))),
        action_active_watches_by_asset_side=np.asarray(
            active_watch_rows, np.int16).reshape((-1, len(ACTIVE_WATCH_KEYS))),
        q_enter_cents=q[:, 0], q_defer_cents=q[:, 1], q_pass_cents=q[:, 2],
        regret_enter_cents=r[:, 0], regret_defer_cents=r[:, 1],
        regret_pass_cents=r[:, 2], optimal_action=np.asarray(actions, str),
        action_margin_cents=np.asarray(margins, np.int64))
    result.validate(); return result, solver


def _arrival(
    universe: DayOptionUniverse, index: int, model_hash: str, *, enter: bool = True,
) -> ScoredArrival:
    i = int(index); opportunity = str(universe.opportunity_id[i])
    timestamp = int(universe.snapshot_ts_ns[i])
    availability = int(universe.entry_availability_ts_ns[i])
    ordinal = int(universe.entry_event_ordinal[i])
    example = CausalEntryExample(
        candidate_id=opportunity, asset=str(universe.asset[i]),
        trading_day=int(universe.day[i]),
        session_id=f"{universe.asset[i]}-{int(universe.day[i])}",
        decision_ts_ns=timestamp,
        side=Side.LONG if int(universe.side[i]) > 0 else Side.SHORT,
        phase=str(universe.phase[i]), locked_iid=0,
        raw_prefix_ref=RawPrefixRef(
            shard=f"tabular-outcome/{universe.asset[i]}/{int(universe.day[i])}",
            event_start_index=0, event_end_index=ordinal + 1,
            event_count=ordinal + 1,
            first_availability_ts_ns=1,
            last_availability_ts_ns=availability,
            source_hash=str(universe.event_prefix_receipt_sha256[i])),
        causal_features={"schedule_priority":
                         float(universe.signed_pnl_cents[i]) / 100.0},
        lineage_hash=str(universe.event_prefix_receipt_sha256[i]))
    pnl = float(universe.signed_pnl_cents[i]) / 100.0
    phase_pnl = float(universe.phase_close_pnl_cents[i]) / 100.0
    wall = bool(universe.wall_hit[i])
    score = EntryScore(
        candidate_id=opportunity, asset=str(universe.asset[i]),
        decision_ts_ns=timestamp, model_hash=model_hash,
        priority_score=pnl, take_probability=float(pnl >= 600.0),
        expected_pnl_usd=pnl, expected_pnl_lower_usd=pnl,
        top3_probability=float(pnl >= 600.0),
        mae_p90_usd=float(universe.mae_usd[i]),
        wall_probability=float(wall), enter=bool(enter))
    outcome = ReplayOutcome(
        candidate_id=opportunity,
        close_ts_ns=int(universe.phase_exit_ts_ns[i]),
        close_pnl_usd=phase_pnl,
        phase_close_ts_ns=int(universe.phase_exit_ts_ns[i]),
        phase_close_pnl_usd=phase_pnl,
        wall_hit_ts_ns=(int(universe.wall_hit_ts_ns[i]) if wall else None),
        wall_pnl_usd=(float(universe.wall_pnl_usd[i]) if wall else -C.WALL_USD))
    return ScoredArrival(example, score, outcome)


def replay_exact_teacher_day(
    teacher: ExactDelayedTeacherDay, universe: DayOptionUniverse, *,
    expected_sessions: Iterable[SessionRef],
) -> object:
    """Cent-parity proof through the unchanged canonical replay."""

    teacher.validate(); universe.validate()
    if teacher.source_universe_sha256 != universe.representation_sha256:
        raise RecoveryRefusal("teacher replay universe differs")
    index = {str(value): i for i, value in enumerate(universe.opportunity_id)}
    selected = set(teacher.selected_opportunity_ids)
    replay_indices = [index[opportunity]
                      for opportunity in teacher.selected_opportunity_ids]
    # Canonical replay deliberately types an entirely absent arrival stream.
    # A zero-ceiling day therefore supplies one real, rejected opportunity so
    # the empty schedule is still exercised through the production boundary.
    if not replay_indices:
        replay_indices.append(0)
    arrivals = tuple(_arrival(
        universe, row,
        f"exact-delayed-teacher:{teacher.representation_sha256}",
        enter=str(universe.opportunity_id[row]) in selected)
        for row in replay_indices)
    evaluation = replay(arrivals, expected_sessions=tuple(expected_sessions))
    if (abs(evaluation.total_pnl_usd
            - teacher.exact_objective_cents / 100.0) > 1e-7
            or {row.candidate_id for row in evaluation.trade_results}
               != set(teacher.selected_opportunity_ids)):
        raise RecoveryRefusal("exact teacher schedule failed canonical cent parity")
    return evaluation


def assert_perfect_enter_actions(teacher: ExactDelayedTeacherDay) -> None:
    """Base-plane ENTER rows must be exactly the exact schedule.

    Scoped to base rows (action_rollout_round == 0): relabel rows are
    policy-conditioned lessons and may lawfully mark ENTER off-schedule
    (2026-08-21, day 20210706 — premature-pass relabels whose conditioned
    optimum is ENTER; latent since round-1 relabeling landed, surfaced by
    the first heavy-tail day containing one. The whole-plane equality this
    replaces was correct only for round-0 teachers)."""

    action_ids = np.asarray(teacher.action_opportunity_id, str)
    action = np.asarray(teacher.optimal_action, str)
    rounds = np.asarray(teacher.action_rollout_round, np.int64)
    base = rounds == 0
    if not base.any():
        raise RecoveryRefusal("teacher has no base-round action rows")
    entered = set(action_ids[
        base & (action == DecisionAction.ENTER.value)].tolist())
    selected = set(teacher.selected_opportunity_ids)
    if entered != selected:
        raise RecoveryRefusal("perfect teacher ENTER actions differ from exact schedule")


def replay_perfect_teacher_actions(
    teacher: ExactDelayedTeacherDay, universe: DayOptionUniverse, *,
    expected_sessions: Iterable[SessionRef],
) -> object:
    """Prove that the teacher's published base ENTER actions are its exact schedule."""

    teacher.validate(); universe.validate()
    assert_perfect_enter_actions(teacher)
    return replay_exact_teacher_day(
        teacher, universe, expected_sessions=expected_sessions)


def publish_teacher_manifest(
    path: os.PathLike[str] | str, *,
    day_files: Mapping[int, Mapping[str, object]],
    chronology_sha256: str,
    corpus_manifest_sha256: str,
    canonical_replay_sha256: str,
    rollout_rounds_completed: int,
) -> Mapping[str, object]:
    if (not day_files or not _sha(chronology_sha256)
            or not _sha(corpus_manifest_sha256)
            or not _sha(canonical_replay_sha256)
            or rollout_rounds_completed not in (0, 1, 2)
            or any(int(day) >= C.HOLDOUT_START_D8 for day in day_files)):
        raise RecoveryRefusal("teacher manifest inputs are invalid/sealed")
    objective = sum(int(row["exact_objective_cents"])
                    for row in day_files.values())
    core = {
        "schema": TEACHER_MANIFEST_SCHEMA,
        "chronology_sha256": chronology_sha256,
        "corpus_manifest_sha256": corpus_manifest_sha256,
        "canonical_replay_sha256": canonical_replay_sha256,
        "solver_implementation_sha256": C.file_sha256(Path(__file__)),
        "days": {str(day): dict(row)
                 for day, row in sorted(day_files.items())},
        "exact_block_objective_cents": objective,
        "rollout_rounds_completed": rollout_rounds_completed,
        "required_rollout_rounds": 2,
        "series_uniqueness": True,
        "closed_interval_k1": True,
        "portfolio_entry_cap": C.MAX_ENTRIES_PORTFOLIO_DAY,
        "cost_once": True,
        "strict_reload": True,
        "h2_open_count": 0,
    }
    artifact = MappingProxyType({
        **core, "receipt_sha256": C.object_sha256(core)})
    target=C.assert_workspace_output(path);raw=C.canonical_bytes(artifact)
    if target.is_file():
        if target.read_bytes()!=raw:
            raise RecoveryRefusal("resumed teacher manifest differs")
    else:C.atomic_json(target,artifact)
    return artifact

__all__ = [
    "ExactDelayedTeacherDay", "TEACHER_DAY_SCHEMA", "TEACHER_MANIFEST_SCHEMA",
    "build_exact_delayed_teacher_day", "publish_teacher_manifest",
    "replay_exact_teacher_day", "assert_perfect_enter_actions",
    "replay_perfect_teacher_actions",
]
