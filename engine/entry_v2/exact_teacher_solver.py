"""Exact MILP / interval-DP suffix solver for one delayed teacher day."""

from __future__ import annotations

from typing import Sequence

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_array, csr_array

from . import common as C
from .exact_teacher_prune import _dominance_pruned_arrays, dominance_pruned_indices
from .exact_teacher_types import (
    ActionQuery, DayOptionUniverse, ExactDaySolution, PortfolioPrefixCondition,
)
from .tabular_recovery_contracts import (
    ACTIVE_WATCH_KEYS, DecisionAction, RecoveryRefusal,
)


class ExactDaySolver:
    """Reusable exact MILP matrix for one day and its conditioned suffixes."""

    def __init__(self, universe: DayOptionUniverse) -> None:
        universe.validate()
        self.universe = universe
        self._dense_series = np.asarray(universe.series_id, str)
        self._dense_start = np.asarray(universe.snapshot_ts_ns, np.int64)
        self._dense_end = np.asarray(universe.exit_ts_ns, np.int64)
        self._dense_asset = np.asarray(universe.asset, str)
        self._dense_cents = np.asarray(universe.signed_pnl_cents, np.int64)
        self._dense_ids = np.asarray(universe.opportunity_id, str)
        self._universe_index_by_opportunity = {
            str(value): int(index) for index, value in enumerate(self._dense_ids)}
        retained = dominance_pruned_indices(universe)
        canonical = np.lexsort((
            np.asarray(universe.opportunity_id, str)[retained],
            np.asarray(universe.snapshot_ts_ns, np.int64)[retained],
            np.asarray(universe.candidate_id, str)[retained]))
        self.indices = retained[canonical]
        self.start = np.asarray(universe.snapshot_ts_ns, np.int64)[self.indices]
        self.end = np.asarray(universe.exit_ts_ns, np.int64)[self.indices]
        self.series = np.asarray(universe.series_id, str)[self.indices]
        self.asset = np.asarray(universe.asset, str)[self.indices]
        self.ids = np.asarray(universe.opportunity_id, str)[self.indices]
        self.candidate = np.asarray(universe.candidate_id, str)[self.indices]
        self.cents = np.asarray(universe.signed_pnl_cents, np.int64)[self.indices]
        self._matrix, self._base_upper, self._cap_row = self._constraints()
        self._value_cache: dict[tuple[object, ...], int] = {}
        self._schedule_cache: dict[str, ExactDaySolution] = {}
        self._interval_dp_authorized = False
        self._interval_dp_match_receipt_sha256 = ""
        self._index_by_opportunity = {
            str(value): int(index) for index, value in enumerate(self.ids)}
        # Active-watch portfolio fields are causal series-level state.  Build
        # their one-row-per-series index once; rescanning the dense 301-second
        # outcome plane for every action query is both unnecessary and
        # prohibitively expensive on real days.
        dense_series = self._dense_series
        dense_order = np.argsort(dense_series, kind="stable")
        ordered_series = dense_series[dense_order]
        watch_series, group_start = np.unique(
            ordered_series, return_index=True)
        watch_start = np.asarray(universe.watch_start_ts_ns, np.int64)[
            dense_order]
        watch_end = np.asarray(universe.snapshot_ts_ns, np.int64)[dense_order]
        self.watch_series = watch_series
        self.watch_start = np.minimum.reduceat(watch_start, group_start)
        self.watch_end = np.maximum.reduceat(watch_end, group_start)
        first_rows = dense_order[group_start]
        self.watch_asset = np.asarray(universe.asset, str)[first_rows]
        self.watch_side = np.asarray(universe.side, np.int8)[first_rows]
        dense_group = np.searchsorted(watch_series, dense_series)
        if (not np.array_equal(
                    np.asarray(universe.asset, str),
                    self.watch_asset[dense_group])
                or not np.all(np.minimum.reduceat(
                    np.asarray(universe.side, np.int8)[dense_order], group_start)
                == self.watch_side)
                or not np.all(np.maximum.reduceat(
                    np.asarray(universe.side, np.int8)[dense_order], group_start)
                == self.watch_side)):
            raise RecoveryRefusal("series changes side inside a day")
        ordered_positive = self._dense_cents[dense_order] > 0
        positive_count = np.add.reduceat(
            ordered_positive.astype(np.int32), group_start)
        latest_start = np.maximum.reduceat(np.where(
            ordered_positive, self._dense_start[dense_order],
            np.iinfo(np.int64).min), group_start)
        earliest_end = np.minimum.reduceat(np.where(
            ordered_positive, self._dense_end[dense_order],
            np.iinfo(np.int64).max), group_start)
        overlap_violations = ((positive_count > 0)
                              & (latest_start > earliest_end))
        self._series_interval_redundancy = not bool(np.any(overlap_violations))
        self._series_interval_violation_count = int(
            np.count_nonzero(overlap_violations))

    def _constraints(self) -> tuple[csr_array, np.ndarray, int]:
        n = len(self.indices)
        row_index: list[int] = []
        col_index: list[int] = []
        values: list[float] = []
        upper: list[float] = []

        def add(columns: Sequence[int], limit: int) -> int:
            row = len(upper)
            for column in columns:
                row_index.append(row); col_index.append(int(column)); values.append(1.0)
            upper.append(float(limit)); return row

        for key in sorted(set(self.series.tolist())):
            columns = np.flatnonzero(self.series == key)
            if len(columns) > 1:
                add(columns.tolist(), 1)
        cap_row = add(tuple(range(n)), C.MAX_ENTRIES_PORTFOLIO_DAY)
        for asset in C.ASSETS:
            columns = np.flatnonzero(self.asset == asset)
            active: set[int] = set()
            last_clique: tuple[int, ...] | None = None
            for timestamp in sorted(set(self.start[columns].tolist())):
                active = {column for column in active if self.end[column] >= timestamp}
                active.update(int(column) for column in columns
                              if self.start[column] == timestamp)
                clique = tuple(sorted(active))
                if len(clique) > 1 and clique != last_clique:
                    add(clique, 1); last_clique = clique
        matrix = coo_array(
            (values, (row_index, col_index)), shape=(len(upper), n)).tocsr()
        return matrix, np.asarray(upper, np.float64), cap_row

    def _eligible_bounds(
        self, condition: PortfolioPrefixCondition, *,
        remove_opportunity_id: str | None = None,
        remove_series_id: str | None = None,
    ) -> np.ndarray:
        condition.__post_init__()
        if condition.trading_day != self.universe.trading_day:
            raise RecoveryRefusal("suffix condition belongs to another day")
        allowed = self.start >= int(condition.timestamp_ns)
        forbidden_series = set(condition.consumed_series) | set(condition.passed_series)
        if forbidden_series:
            allowed &= ~np.isin(self.series, tuple(forbidden_series))
        if remove_series_id is not None:
            allowed &= self.series != str(remove_series_id)
        if remove_opportunity_id is not None:
            allowed &= self.ids != str(remove_opportunity_id)
        for asset_index, asset in enumerate(C.ASSETS):
            open_until = int(condition.open_until_by_asset[asset_index])
            if open_until >= condition.timestamp_ns:
                allowed &= ~((self.asset == asset) & (self.start <= open_until))
        return allowed.astype(np.float64)

    def _conditional_retained_indices(
        self, *, remove_opportunity_id: str | None = None,
        remove_series_id: str | None = None,
    ) -> np.ndarray:
        """Restore the exact local frontier after a snapshot removal.

        Global dominance is stable under suffix clocks, occupied intervals,
        and whole-series removals.  It is not stable when DEFER removes the
        particular snapshot that dominated another snapshot.  Recomputing the
        frontier for that one series keeps DEFER exact without rebuilding the
        255k-row day.
        """

        retained = self.indices
        if remove_series_id is not None:
            retained = retained[
                self._dense_series[retained] != str(remove_series_id)]
        if remove_opportunity_id is None:
            return retained
        dense_row = self._universe_index_by_opportunity.get(
            str(remove_opportunity_id))
        if dense_row is None:
            raise RecoveryRefusal("removed opportunity is absent")
        affected_series = str(self._dense_series[dense_row])
        if remove_series_id is not None and affected_series == str(remove_series_id):
            return retained
        other = retained[
            self._dense_series[retained] != affected_series]
        local = np.flatnonzero(
            (self._dense_series == affected_series)
            & (self._dense_ids != str(remove_opportunity_id)))
        local_frontier = _dominance_pruned_arrays(
            self._dense_series[local], self._dense_start[local],
            self._dense_end[local], self._dense_cents[local],
            self._dense_ids[local])
        return np.sort(np.concatenate((other, local[local_frontier]))).astype(
            np.int64, copy=False)

    def _interval_dp_value(
        self, condition: PortfolioPrefixCondition, *,
        remove_opportunity_id: str | None = None,
        remove_series_id: str | None = None,
    ) -> int:
        """Exact closed-interval K1 value by asset and remaining seat count."""

        condition.__post_init__()
        remaining = C.MAX_ENTRIES_PORTFOLIO_DAY - int(condition.entries_used)
        if remaining <= 0:
            return 0
        indices = self._conditional_retained_indices(
            remove_opportunity_id=remove_opportunity_id,
            remove_series_id=remove_series_id)
        if not len(indices):
            return 0
        allowed = self._dense_start[indices] >= int(condition.timestamp_ns)
        forbidden = set(condition.consumed_series) | set(condition.passed_series)
        if forbidden:
            allowed &= ~np.isin(
                self._dense_series[indices], tuple(sorted(forbidden)))
        for asset_index, asset in enumerate(C.ASSETS):
            open_until = int(condition.open_until_by_asset[asset_index])
            if open_until >= int(condition.timestamp_ns):
                allowed &= ~(
                    (self._dense_asset[indices] == asset)
                    & (self._dense_start[indices] <= open_until))
        indices = indices[allowed]
        if not len(indices):
            return 0

        values_by_asset: list[np.ndarray] = []
        for asset in C.ASSETS:
            local = indices[self._dense_asset[indices] == asset]
            if not len(local):
                values_by_asset.append(np.zeros(remaining + 1, np.int64))
                continue
            order = np.lexsort((
                self._dense_ids[local], self._dense_start[local],
                self._dense_end[local]))
            local = local[order]
            ends = self._dense_end[local]
            predecessor = np.searchsorted(
                ends, self._dense_start[local], side="left") - 1
            table = np.zeros((len(local) + 1, remaining + 1), np.int64)
            for row, (prior, cents) in enumerate(zip(
                    predecessor, self._dense_cents[local]), start=1):
                table[row] = table[row - 1]
                take = int(cents) + table[int(prior) + 1, :-1]
                table[row, 1:] = np.maximum(table[row, 1:], take)
            values_by_asset.append(table[-1])

        combined = np.zeros(remaining + 1, np.int64)
        for asset_values in values_by_asset:
            merged = np.zeros_like(combined)
            for seats in range(remaining + 1):
                merged[seats] = max(
                    int(combined[seats - used]) + int(asset_values[used])
                    for used in range(seats + 1))
            combined = merged
        return int(combined[-1])

    def authorize_interval_suffix_solver(
        self, milp_solution: ExactDaySolution,
    ) -> str:
        """Authorize DP only after a structural proof and same-day MILP match."""

        if not self._series_interval_redundancy:
            raise RecoveryRefusal(
                "weighted interval solver cannot represent series uniqueness")
        dp_value = self._interval_dp_value(self.initial_condition())
        if dp_value != int(milp_solution.objective_cents):
            raise RecoveryRefusal("interval solver differs from authoritative MILP")
        core = {
            "schema": "QRE2INTERVALMILPMATCH1",
            "day": self.universe.trading_day,
            "universe": self.universe.representation_sha256,
            "milp_receipt": milp_solution.receipt_sha256,
            "milp_objective_cents": int(milp_solution.objective_cents),
            "interval_objective_cents": dp_value,
            "positive_series_pairwise_overlap": True,
            "series_constraint_redundant_under_k1": True,
            "closed_interval_predecessor": "exit_ts_ns < entry_ts_ns",
        }
        self._interval_dp_authorized = True
        self._interval_dp_match_receipt_sha256 = C.object_sha256(core)
        return self._interval_dp_match_receipt_sha256

    def suffix_objective(
        self, condition: PortfolioPrefixCondition, *,
        remove_opportunity_id: str | None = None,
        remove_series_id: str | None = None,
    ) -> int:
        if not self._interval_dp_authorized:
            raise RecoveryRefusal(
                "suffix DP used before same-day authoritative MILP match")
        cache_key = (
            "INTERVAL_DP", condition.receipt_sha256,
            remove_opportunity_id, remove_series_id)
        if cache_key not in self._value_cache:
            self._value_cache[cache_key] = self._interval_dp_value(
                condition, remove_opportunity_id=remove_opportunity_id,
                remove_series_id=remove_series_id)
        return int(self._value_cache[cache_key])

    def solve(
        self, condition: PortfolioPrefixCondition, *,
        remove_opportunity_id: str | None = None,
        remove_series_id: str | None = None,
        return_schedule: bool = False,
        canonical_tie_break: bool = False,
    ) -> ExactDaySolution:
        remaining = C.MAX_ENTRIES_PORTFOLIO_DAY - int(condition.entries_used)
        if remaining <= 0:
            core = {
                "schema": "QRE2SUFFIXSOLVE1", "condition": condition.receipt_sha256,
                "remove_opportunity_id": remove_opportunity_id,
                "remove_series_id": remove_series_id,
                "objective_cents": 0, "selected_opportunity_ids": (),
            }
            return ExactDaySolution(0, (), (), C.object_sha256(core))
        cache_key = (
            condition.receipt_sha256, remove_opportunity_id, remove_series_id)
        if (return_schedule and not canonical_tie_break
                and remove_opportunity_id is None and remove_series_id is None
                and condition.receipt_sha256 in self._schedule_cache):
            return self._schedule_cache[condition.receipt_sha256]
        if not return_schedule and cache_key in self._value_cache:
            objective = self._value_cache[cache_key]
            core = {
                "schema": "QRE2SUFFIXSOLVE1", "condition": condition.receipt_sha256,
                "remove_opportunity_id": remove_opportunity_id,
                "remove_series_id": remove_series_id,
                "objective_cents": objective, "selected_opportunity_ids": (),
            }
            return ExactDaySolution(objective, (), (), C.object_sha256(core))
        upper = self._base_upper.copy(); upper[self._cap_row] = remaining
        eligible = self._eligible_bounds(
            condition, remove_opportunity_id=remove_opportunity_id,
            remove_series_id=remove_series_id)
        if not np.any(eligible):
            selected_local = np.empty(0, np.int64); objective = 0
        else:
            if canonical_tie_break:
                n = len(self.cents)
                # One cent dominates every possible 12-seat secondary bonus.
                scale = C.MAX_ENTRIES_PORTFOLIO_DAY * n + 1
                bonus = np.arange(n, 0, -1, dtype=np.int64)
                objective_vector = self.cents * scale + bonus
            else:
                objective_vector = self.cents
            result = milp(
                c=-objective_vector.astype(np.float64),
                integrality=np.ones(len(self.cents), np.int8),
                bounds=Bounds(np.zeros(len(self.cents)), eligible),
                constraints=LinearConstraint(
                    self._matrix, np.full(len(upper), -np.inf), upper),
                options={"mip_rel_gap": 0.0, "presolve": True})
            if (not result.success or result.x is None
                    or result.mip_gap is None or float(result.mip_gap) > 1e-9):
                raise RecoveryRefusal(
                    f"exact suffix MILP failed: {result.status} {result.message}")
            selected_local = np.flatnonzero(np.asarray(result.x) > 0.5)
            if (np.any(np.abs(np.asarray(result.x)[selected_local] - 1.0) > 1e-6)
                    or len(selected_local) > remaining):
                raise RecoveryRefusal("exact suffix solution is fractional/over-cap")
            objective = int(self.cents[selected_local].sum())
        selected_indices = tuple(int(self.indices[index]) for index in selected_local)
        selected_ids = tuple(sorted(
            str(self.universe.opportunity_id[index]) for index in selected_indices))
        core = {
            "schema": "QRE2SUFFIXSOLVE1", "universe": self.universe.representation_sha256,
            "condition": condition.receipt_sha256,
            "remove_opportunity_id": remove_opportunity_id,
            "remove_series_id": remove_series_id,
            "objective_cents": objective,
            "selected_opportunity_ids": selected_ids,
            "canonical_tie_break": bool(canonical_tie_break),
        }
        if not return_schedule:
            self._value_cache[cache_key] = objective
            selected_indices = (); selected_ids = ()
        solution = ExactDaySolution(
            objective, selected_indices, selected_ids, C.object_sha256(core))
        if (return_schedule and not canonical_tie_break
                and remove_opportunity_id is None and remove_series_id is None):
            self._schedule_cache[condition.receipt_sha256] = solution
        return solution

    def initial_condition(self) -> PortfolioPrefixCondition:
        timestamp = int(np.min(np.asarray(
            self.universe.snapshot_ts_ns, np.int64)))
        return PortfolioPrefixCondition(
            self.universe.trading_day, timestamp, 0, (-1, -1, -1),
            (-1, -1, -1))

    def exact_schedule(self) -> ExactDaySolution:
        return self.solve(
            self.initial_condition(), return_schedule=True,
            canonical_tie_break=True)

    def active_watch_counts(
        self, condition: PortfolioPrefixCondition,
    ) -> tuple[int, ...]:
        """Count live watches from the precomputed causal series index."""

        condition.__post_init__()
        active = ((self.watch_start <= int(condition.timestamp_ns))
                  & (self.watch_end >= int(condition.timestamp_ns)))
        forbidden = set(condition.consumed_series) | set(condition.passed_series)
        if forbidden:
            active &= ~np.isin(self.watch_series, tuple(sorted(forbidden)))
        return tuple(int(np.count_nonzero(
            active & (self.watch_asset == asset) & (self.watch_side == side)))
            for asset, side in ACTIVE_WATCH_KEYS)

    def action_values(
        self, query: ActionQuery,
    ) -> tuple[int, int, int, DecisionAction, tuple[int, int, int]]:
        """Return exact suffix Q and regrets in ENTER, DEFER, PASS order."""

        query.__post_init__()
        try:
            # O(1) bijection built in __init__ (:360-361); DayOptionUniverse
            # .validate refuses duplicate opportunity_id (:218) and __init__
            # calls it, so this cannot silently pick a different row than the
            # first-match scan it replaces.
            index = self._universe_index_by_opportunity[str(query.opportunity_id)]
        except KeyError as exc:
            raise RecoveryRefusal("action query opportunity is absent") from exc
        condition = query.condition
        now = int(self.universe.snapshot_ts_ns[index])
        if condition.timestamp_ns != now:
            raise RecoveryRefusal("action query clock differs from opportunity")
        series = str(self.universe.series_id[index])
        asset = str(self.universe.asset[index])
        current_cents = int(self.universe.signed_pnl_cents[index])
        # ENTER locks the current option, consumes its series/seat, and closes
        # the asset through the option's closed exit interval.
        open_until = list(condition.open_until_by_asset)
        causal_open_until = list(condition.causal_open_until_by_asset)
        asset_index = C.ASSET_INDEX[asset]
        forbidden = (set(condition.consumed_series)
                     | set(condition.passed_series))
        if series in forbidden:
            q_enter = -10**18
        elif open_until[asset_index] >= now:
            q_enter = -10**18
        elif condition.entries_used >= C.MAX_ENTRIES_PORTFOLIO_DAY:
            q_enter = -10**18
        else:
            open_until[asset_index] = max(
                int(open_until[asset_index]), int(self.universe.exit_ts_ns[index]))
            causal_open_until[asset_index] = max(
                int(causal_open_until[asset_index]),
                int(self.universe.phase_close_ts_ns[index]))
            enter_condition = PortfolioPrefixCondition(
                condition.trading_day, now, condition.entries_used + 1,
                tuple(open_until), tuple(causal_open_until),
                tuple(sorted(set(condition.consumed_series) | {series})),
                condition.passed_series)
            q_enter = current_cents + self.suffix_objective(enter_condition)
        baseline = self.suffix_objective(condition)
        # DEFER removes only this snapshot.  The conditional frontier helper
        # restores any same-series option shadowed by that snapshot, avoiding
        # the common but inexact shortcut of removing it from a globally
        # pruned matrix.  PASS removes the complete series.
        if query.opportunity_id not in self._index_by_opportunity:
            q_defer = baseline
        else:
            q_defer = self.suffix_objective(
                condition, remove_opportunity_id=query.opportunity_id)
        q_pass = self.suffix_objective(condition, remove_series_id=series)
        values = (int(q_enter), int(q_defer), int(q_pass))
        best = max(values)
        regrets = tuple(int(best - value) for value in values)
        # Conservative deterministic tie rule: preserve optionality, then pass,
        # unless ENTER is uniquely better.  Canonical schedule membership can
        # override an exact tie when the teacher day is assembled below.
        if q_enter > max(q_defer, q_pass):
            action = DecisionAction.ENTER
        elif q_defer >= q_pass:
            action = DecisionAction.DEFER
        else:
            action = DecisionAction.PASS
        return values[0], values[1], values[2], action, regrets

