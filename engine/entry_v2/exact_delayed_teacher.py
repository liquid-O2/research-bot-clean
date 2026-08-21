"""Exact delayed portfolio teacher and conditioned ENTER/DEFER/PASS values.

Future information is confined to this module's artifacts.  Production model
and policy modules import only the label-free contracts and never import this
module.  One MILP authority is reused for the daily ceiling and every suffix
action value; no weighted-interval proxy is permitted here.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import math
import os
from pathlib import Path
from types import MappingProxyType
from typing import Final, Iterable, Mapping, Sequence

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_array, csr_array

from . import common as C
from .contracts import (
    CausalEntryExample, EntryScore, RawPrefixRef, SessionRef, Side,
)
from .confirmation import training_offsets_seconds
from .replay import ReplayOutcome, ScoredArrival, replay
from .tabular_delayed_corpus import DelayedOutcomeShard
from .tabular_recovery_contracts import (
    ACTIVE_WATCH_KEYS, BASE_TRAINING_OFFSETS_SEC, DecisionAction,
    RecoveryRefusal,
)


TEACHER_DAY_SCHEMA: Final = "QRE2EXACTDELAYEDTEACHER2"
TEACHER_MANIFEST_SCHEMA: Final = "QRE2EXACTDELAYEDTEACHERMANIFEST2"
ACTION_SOURCE_NAMES: Final = (
    "ORACLE_TRAJECTORY", "HIGH_VALUE_CONFLICT",
    "POLICY_ROLLOUT_1", "POLICY_ROLLOUT_2")


def _sha(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def _hash_array(digest: "hashlib._Hash", value: np.ndarray) -> None:
    array = np.ascontiguousarray(value)
    digest.update(str(array.dtype).encode())
    digest.update(repr(array.shape).encode())
    digest.update(array.tobytes())


def _cents(values: np.ndarray, name: str) -> np.ndarray:
    source = np.asarray(values, np.float64)
    output = np.rint(source * 100.0).astype(np.int64)
    if not np.allclose(output / 100.0, source, atol=1e-7, rtol=0):
        raise RecoveryRefusal(f"{name} is not cent-valued")
    return output


@dataclass(frozen=True, slots=True)
class PortfolioPrefixCondition:
    """Causal portfolio state immediately before one timestamp batch."""

    trading_day: int
    timestamp_ns: int
    entries_used: int
    # Privileged realized occupancy is used only by the exact suffix solver.
    open_until_by_asset: tuple[int, int, int]
    # The model-visible clock is the known scheduled phase close for a
    # currently open position, never its future wall-hit timestamp.
    causal_open_until_by_asset: tuple[int, int, int]
    consumed_series: tuple[str, ...] = ()
    passed_series: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        C.guard_date(int(self.trading_day))
        if (int(self.timestamp_ns) <= 0
                or not 0 <= int(self.entries_used)
                       <= C.MAX_ENTRIES_PORTFOLIO_DAY
                or len(self.open_until_by_asset) != len(C.ASSETS)
                or len(self.causal_open_until_by_asset) != len(C.ASSETS)
                or any(int(value) < -1 for value in self.open_until_by_asset)
                or any(int(value) < -1
                       for value in self.causal_open_until_by_asset)
                or tuple(sorted(set(self.consumed_series)))
                   != self.consumed_series
                or tuple(sorted(set(self.passed_series))) != self.passed_series
                or set(self.consumed_series) & set(self.passed_series)):
            raise RecoveryRefusal("portfolio prefix condition is malformed")
        for realized, causal in zip(
                self.open_until_by_asset, self.causal_open_until_by_asset):
            realized_active = int(realized) >= int(self.timestamp_ns)
            causal_active = int(causal) >= int(self.timestamp_ns)
            if (realized_active != causal_active
                    or (realized_active and int(causal) < int(realized))):
                raise RecoveryRefusal(
                    "causal and privileged occupancy states disagree")

    @property
    def receipt_sha256(self) -> str:
        return C.object_sha256({"schema": "QRE2PORTPREFIX1", **asdict(self)})


@dataclass(frozen=True, slots=True)
class ActionQuery:
    opportunity_id: str
    condition: PortfolioPrefixCondition
    source: str
    rollout_round: int = 0

    def __post_init__(self) -> None:
        if (not self.opportunity_id or self.source not in ACTION_SOURCE_NAMES
                or self.rollout_round not in (0, 1, 2)
                or (self.source.startswith("POLICY_ROLLOUT_")
                    != (self.rollout_round > 0))
                or (self.rollout_round > 0
                    and self.source != f"POLICY_ROLLOUT_{self.rollout_round}")):
            raise RecoveryRefusal("action query source/round is malformed")


@dataclass(frozen=True, slots=True)
class RolloutStateProposal:
    opportunity_id: str
    condition: PortfolioPrefixCondition
    predicted_action: DecisionAction

    def __post_init__(self) -> None:
        if not self.opportunity_id:
            raise RecoveryRefusal("rollout proposal lacks opportunity identity")
        object.__setattr__(self, "predicted_action", DecisionAction(
            self.predicted_action))


@dataclass(frozen=True, slots=True)
class ExactDaySolution:
    objective_cents: int
    selected_indices: tuple[int, ...]
    selected_opportunity_ids: tuple[str, ...]
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class DayOptionUniverse:
    """Joint all-asset dense option universe for one portfolio day."""

    opportunity_id: np.ndarray
    series_id: np.ndarray
    candidate_id: np.ndarray
    asset: np.ndarray
    day: np.ndarray
    side: np.ndarray
    phase: np.ndarray
    watch_start_ts_ns: np.ndarray
    snapshot_ts_ns: np.ndarray
    phase_close_ts_ns: np.ndarray
    event_cutoff: np.ndarray
    entry_event_ordinal: np.ndarray
    entry_availability_ts_ns: np.ndarray
    signed_pnl_cents: np.ndarray
    phase_close_pnl_cents: np.ndarray
    phase_exit_ts_ns: np.ndarray
    mfe_usd: np.ndarray
    mae_usd: np.ndarray
    wall_hit: np.ndarray
    wall_hit_ts_ns: np.ndarray
    wall_pnl_usd: np.ndarray
    exit_ts_ns: np.ndarray
    event_prefix_receipt_sha256: np.ndarray
    source_outcome_sha256: tuple[str, ...]

    @classmethod
    def from_shards(cls, shards: Sequence[DelayedOutcomeShard]) -> "DayOptionUniverse":
        rows = tuple(shards)
        if not rows:
            raise RecoveryRefusal("day option universe has no outcome shards")
        for row in rows:
            row.validate()
        days = {int(value) for row in rows for value in np.asarray(row.day)}
        assets = [str(np.asarray(row.asset, str)[0]) for row in rows]
        if (len(days) != 1 or len(assets) != len(set(assets))
                or any(row.max_delay_sec != rows[0].max_delay_sec for row in rows)):
            raise RecoveryRefusal("day option shards cross day/asset/config")
        fields = (
            "opportunity_id", "series_id", "candidate_id", "asset", "day",
            "side", "phase", "watch_start_ts_ns", "snapshot_ts_ns",
            "phase_close_ts_ns", "event_cutoff", "entry_event_ordinal",
            "entry_availability_ts_ns", "mfe_usd", "mae_usd", "wall_hit",
            "wall_hit_ts_ns", "wall_pnl_usd", "exit_ts_ns",
            "phase_exit_ts_ns",
            "event_prefix_receipt_sha256")
        result = cls(
            **{name: np.concatenate([
                np.asarray(getattr(row, name)) for row in rows])
               for name in fields},
            signed_pnl_cents=np.concatenate([
                _cents(row.signed_pnl_usd, "signed PnL") for row in rows]),
            phase_close_pnl_cents=np.concatenate([
                _cents(row.phase_close_pnl_usd, "phase-close PnL")
                for row in rows]),
            source_outcome_sha256=tuple(sorted(
                row.representation_sha256 for row in rows)))
        result.validate(); return result

    def validate(self) -> None:
        n = len(self.opportunity_id)
        fields = tuple(getattr(self, name) for name in (
            "series_id", "candidate_id", "asset", "day", "side", "phase",
            "watch_start_ts_ns", "snapshot_ts_ns", "phase_close_ts_ns",
            "event_cutoff", "entry_event_ordinal", "entry_availability_ts_ns",
            "signed_pnl_cents", "phase_close_pnl_cents", "mfe_usd", "mae_usd",
            "wall_hit", "wall_hit_ts_ns", "wall_pnl_usd", "exit_ts_ns",
            "phase_exit_ts_ns",
            "event_prefix_receipt_sha256"))
        if (n == 0 or any(np.asarray(value).shape != (n,) for value in fields)
                or len(set(np.asarray(self.opportunity_id, str).tolist())) != n
                or len(set(np.asarray(self.day, np.int64).tolist())) != 1
                or not np.all(np.isin(self.asset, C.ASSETS))
                or not np.all(np.isin(self.side, (-1, 1)))
                or not np.all(np.asarray(self.exit_ts_ns)
                              >= np.asarray(self.snapshot_ts_ns))
                or not np.all(np.asarray(self.phase_exit_ts_ns)
                              >= np.asarray(self.exit_ts_ns))
                or not np.all(np.asarray(self.phase_close_ts_ns)
                              >= np.asarray(self.exit_ts_ns))
                or any(not _sha(value) for value in self.source_outcome_sha256)):
            raise RecoveryRefusal("day option universe is malformed")

    @property
    def trading_day(self) -> int:
        self.validate(); return int(np.asarray(self.day, np.int64)[0])

    @property
    def representation_sha256(self) -> str:
        self.validate()
        digest = hashlib.sha256()
        digest.update("QRE2DAYOPTIONS1".encode())
        digest.update("\n".join(self.source_outcome_sha256).encode())
        for name in (
            "opportunity_id", "series_id", "candidate_id", "asset", "day",
            "side", "phase", "watch_start_ts_ns", "snapshot_ts_ns",
            "phase_close_ts_ns", "event_cutoff", "entry_event_ordinal",
            "entry_availability_ts_ns", "signed_pnl_cents",
            "phase_close_pnl_cents", "mfe_usd", "mae_usd", "wall_hit",
            "wall_hit_ts_ns", "wall_pnl_usd", "exit_ts_ns",
            "phase_exit_ts_ns",
            "event_prefix_receipt_sha256"):
            _hash_array(digest, np.asarray(getattr(self, name)))
        return digest.hexdigest()


class _FenwickMaximum:
    def __init__(self, size: int) -> None:
        self.values = np.full(size + 1, np.iinfo(np.int64).min, np.int64)

    def update(self, index: int, value: int) -> None:
        point = int(index) + 1
        while point < len(self.values):
            self.values[point] = max(int(self.values[point]), int(value))
            point += point & -point

    def prefix_max(self, index: int) -> int:
        point = int(index) + 1
        value = np.iinfo(np.int64).min
        while point > 0:
            value = max(value, int(self.values[point]))
            point -= point & -point
        return int(value)


def _dominance_pruned_arrays(
    series: np.ndarray, start: np.ndarray, end: np.ndarray,
    cents: np.ndarray, ids: np.ndarray,
) -> np.ndarray:
    """Return positions surviving exact series-local dominance."""

    series = np.asarray(series, str)
    start = np.asarray(start, np.int64)
    end = np.asarray(end, np.int64)
    cents = np.asarray(cents, np.int64)
    ids = np.asarray(ids, str)
    n = len(series)
    if any(len(value) != n for value in (start, end, cents, ids)):
        raise RecoveryRefusal("dominance inputs have different row counts")
    output: list[int] = []
    for key in sorted(set(series.tolist())):
        local = np.flatnonzero((series == key) & (cents > 0))
        if not len(local):
            continue
        end_values = np.asarray(sorted(set(end[local].tolist())), np.int64)
        end_rank = {int(value): index for index, value in enumerate(end_values)}
        tree = _FenwickMaximum(len(end_values))
        # Canonical order makes retained output invariant to source row order.
        order = local[np.lexsort((ids[local], end[local], -start[local]))]
        positions = 0
        while positions < len(order):
            batch_end = positions + 1
            while (batch_end < len(order)
                   and start[order[batch_end]] == start[order[positions]]):
                batch_end += 1
            batch = order[positions:batch_end]
            batch = batch[np.lexsort((ids[batch], -cents[batch], end[batch]))]
            same_start_best = np.iinfo(np.int64).min
            same_start_end = None
            kept: list[int] = []
            for index in batch:
                rank = end_rank[int(end[index])]
                later_best = tree.prefix_max(rank)
                same_dominates = (
                    same_start_best >= cents[index]
                    and (same_start_end is not None)
                    and (same_start_end < end[index]
                         or same_start_best > cents[index]))
                if later_best < cents[index] and not same_dominates:
                    kept.append(int(index))
                if cents[index] > same_start_best:
                    same_start_best = int(cents[index])
                    same_start_end = int(end[index])
                elif cents[index] == same_start_best:
                    same_start_end = min(int(end[index]), int(same_start_end))
            for index in kept:
                tree.update(end_rank[int(end[index])], int(cents[index]))
                output.append(index)
            positions = batch_end
    return np.asarray(sorted(output), np.int64)


def dominance_pruned_indices(universe: DayOptionUniverse) -> np.ndarray:
    """O(n log n) exact series-local dominance pruning.

    Option j dominates i only when it starts no earlier, exits no later, pays
    no less, and improves at least one of those three dimensions.  Zero and
    negative options are excluded from an unconstrained optimum but remain in
    the dense outcome shard for forced ENTER action values.
    """

    universe.validate()
    return _dominance_pruned_arrays(
        np.asarray(universe.series_id, str),
        np.asarray(universe.snapshot_ts_ns, np.int64),
        np.asarray(universe.exit_ts_ns, np.int64),
        np.asarray(universe.signed_pnl_cents, np.int64),
        np.asarray(universe.opportunity_id, str))


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


def _component_indices(
    universe: DayOptionUniverse, selected_indices: Sequence[int],
) -> np.ndarray:
    series = np.asarray(universe.series_id, str)
    ts = np.asarray(universe.snapshot_ts_ns, np.int64)
    watch = np.asarray(universe.watch_start_ts_ns, np.int64)
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


def replay_perfect_teacher_actions(
    teacher: ExactDelayedTeacherDay, universe: DayOptionUniverse, *,
    expected_sessions: Iterable[SessionRef],
) -> object:
    """Prove that the teacher's published ENTER actions are its exact schedule."""

    teacher.validate(); universe.validate()
    action_ids = np.asarray(teacher.action_opportunity_id, str)
    action = np.asarray(teacher.optimal_action, str)
    entered = set(action_ids[action == DecisionAction.ENTER.value].tolist())
    selected = set(teacher.selected_opportunity_ids)
    if entered != selected:
        raise RecoveryRefusal("perfect teacher ENTER actions differ from exact schedule")
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
    "ACTION_SOURCE_NAMES", "ActionQuery", "DayOptionUniverse",
    "ExactDaySolution", "ExactDaySolver", "ExactDelayedTeacherDay",
    "PortfolioPrefixCondition", "TEACHER_DAY_SCHEMA",
    "RolloutStateProposal",
    "TEACHER_MANIFEST_SCHEMA", "add_rollout_relabels",
    "build_exact_delayed_teacher_day", "dominance_pruned_indices",
    "publish_teacher_manifest", "replay_exact_teacher_day",
    "replay_perfect_teacher_actions", "rollout_error_queries",
]
