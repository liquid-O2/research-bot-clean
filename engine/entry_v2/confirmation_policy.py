"""Stopping policy, canonical replay adapter, and exact delayed ceiling."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import math
from types import MappingProxyType
from typing import Iterable, Sequence

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_array

from . import common as C
from .confirmation import (
    ConfirmationDataset, ConfirmationOpportunitySet, ConfirmationRefusal,
    combine_confirmation_opportunity_sets,
)
from .confirmation_model import ConfirmationPredictions
from .contracts import (
    CausalEntryExample, EntryEvaluation, EntryScore, RawPrefixRef, SessionRef,
    Side,
)
from .replay import ReplayOutcome, ScoredArrival, replay


POLICY_SCHEMA = "QRE2CONFPOL1"
CEILING_SCHEMA = "QRE2CONFCEIL1"


@dataclass(frozen=True, slots=True)
class ConfirmationPolicy:
    min_expected_pnl_usd: float
    min_pnl_q20_usd: float
    min_goal_probability: float
    max_wall_probability: float
    max_mae_q90_usd: float = 900.0
    min_alert_age_sec: float = 0.0
    max_alert_age_sec: float = 300.0

    def __post_init__(self) -> None:
        values = (self.min_expected_pnl_usd, self.min_pnl_q20_usd,
                  self.min_goal_probability, self.max_wall_probability,
                  self.max_mae_q90_usd, self.min_alert_age_sec,
                  self.max_alert_age_sec)
        if (any(not math.isfinite(value) for value in values)
                or not 0 <= self.min_goal_probability <= 1
                or not 0 <= self.max_wall_probability <= 1
                or self.max_mae_q90_usd <= 0
                or self.min_alert_age_sec < 0
                or self.max_alert_age_sec not in (300.0, 600.0)
                or self.min_alert_age_sec > self.max_alert_age_sec):
            raise ConfirmationRefusal("confirmation policy thresholds are invalid")

    @property
    def receipt_sha256(self) -> str:
        return C.object_sha256({"schema": POLICY_SCHEMA, **asdict(self)})

    def mask(self, dataset: ConfirmationDataset,
             predictions: ConfirmationPredictions) -> np.ndarray:
        dataset.validate(); predictions.validate(dataset.opportunity_id)
        age = np.asarray(dataset.min_alert_age_sec, np.float64)
        return (
            (np.asarray(predictions.expected_pnl_usd)
             >= self.min_expected_pnl_usd)
            & (np.asarray(predictions.pnl_q20_usd) >= self.min_pnl_q20_usd)
            & (np.asarray(predictions.goal_probability)
               >= self.min_goal_probability)
            & (np.asarray(predictions.wall_probability)
               <= self.max_wall_probability)
            & (np.asarray(predictions.mae_q90_usd) <= self.max_mae_q90_usd)
            & (age >= self.min_alert_age_sec)
            & (age <= self.max_alert_age_sec)
        )


def first_trigger_indices(
    dataset: ConfirmationDataset,
    predictions: ConfirmationPredictions,
    policy: ConfirmationPolicy,
    *, series_time_order: np.ndarray | None = None,
) -> np.ndarray:
    """Return the first causal passing timestamp for every native candidate."""

    passing = policy.mask(dataset, predictions)
    series = np.asarray(dataset.series_id, str)
    order = (confirmation_series_time_order(dataset) if series_time_order is None
             else np.asarray(series_time_order, np.int64))
    if order.shape != (len(series),):
        raise ConfirmationRefusal("confirmation series order is malformed")
    eligible = order[passing[order]]
    if not len(eligible):
        return np.empty(0, np.int64)
    sorted_series = series[eligible]
    first = np.r_[True, sorted_series[1:] != sorted_series[:-1]]
    return eligible[first].astype(np.int64, copy=False)


def confirmation_series_time_order(
    dataset: ConfirmationDataset,
) -> np.ndarray:
    """Validate and cacheable-sort the immutable series chronology once."""

    dataset.validate()
    series = np.asarray(dataset.series_id, str)
    timestamps = np.asarray(dataset.snapshot_ts_ns, np.int64)
    ids = np.asarray(dataset.opportunity_id, str)
    order = np.lexsort((ids, timestamps, series)).astype(np.int64)
    sorted_series = series[order]; sorted_time = timestamps[order]
    if np.any((sorted_series[1:] == sorted_series[:-1])
              & (sorted_time[1:] == sorted_time[:-1])):
        raise ConfirmationRefusal("confirmation series has duplicate snapshot time")
    return order


def _arrival(
    dataset: ConfirmationDataset,
    index: int,
    *, model_hash: str,
    expected_pnl_usd: float,
    pnl_q20_usd: float,
    goal_probability: float,
    wall_probability: float,
    mae_q90_usd: float,
) -> ScoredArrival:
    i = int(index)
    opportunity_id = str(dataset.opportunity_id[i])
    decision = int(dataset.snapshot_ts_ns[i])
    ordinal = int(dataset.entry_event_ordinal[i])
    availability = int(dataset.entry_availability_ts_ns[i])
    prefix = RawPrefixRef(
        shard=f"confirmation/{dataset.asset[i]}/{int(dataset.day[i])}.qre2",
        event_start_index=ordinal, event_end_index=ordinal + 1, event_count=1,
        first_availability_ts_ns=availability,
        last_availability_ts_ns=availability,
        source_hash=str(dataset.feature_receipt_sha256[i]),
    )
    example = CausalEntryExample(
        candidate_id=opportunity_id, asset=str(dataset.asset[i]),
        trading_day=int(dataset.day[i]),
        session_id=f"{dataset.asset[i]}-{int(dataset.day[i])}",
        decision_ts_ns=decision,
        side=Side.LONG if int(dataset.side[i]) > 0 else Side.SHORT,
        phase=str(dataset.phase[i]), locked_iid=0, raw_prefix_ref=prefix,
        causal_features={"confirmation_priority_score": float(expected_pnl_usd)},
        context=None, lineage_hash=str(dataset.feature_receipt_sha256[i]),
    )
    score = EntryScore(
        candidate_id=opportunity_id, asset=str(dataset.asset[i]),
        decision_ts_ns=decision, model_hash=model_hash,
        priority_score=float(expected_pnl_usd),
        take_probability=float(goal_probability),
        expected_pnl_usd=float(expected_pnl_usd),
        expected_pnl_lower_usd=float(pnl_q20_usd),
        top3_probability=float(goal_probability),
        mae_p90_usd=max(0.0, float(mae_q90_usd)),
        wall_probability=float(wall_probability), enter=True,
    )
    cert = float(dataset.cert_close_usd[i])
    exit_ts = int(dataset.exit_ts_ns[i])
    wall = bool(dataset.wall_hit[i])
    outcome = ReplayOutcome(
        candidate_id=opportunity_id,
        close_ts_ns=exit_ts, close_pnl_usd=cert,
        phase_close_ts_ns=exit_ts, phase_close_pnl_usd=cert,
        wall_hit_ts_ns=exit_ts if wall else None,
        wall_pnl_usd=cert if wall else -C.WALL_USD,
    )
    return ScoredArrival(example, score, outcome)


def default_expected_sessions(dataset: ConfirmationDataset) -> tuple[SessionRef, ...]:
    """Candidate-containing sessions only; full rehearsals pass the full roster."""

    dataset.validate()
    return tuple(sorted({SessionRef(str(asset), int(day), f"{asset}-{int(day)}")
                         for asset, day in zip(dataset.asset, dataset.day)}))


def replay_confirmation(
    dataset: ConfirmationDataset,
    predictions: ConfirmationPredictions,
    policy: ConfirmationPolicy,
    *, expected_sessions: Iterable[SessionRef],
    series_time_order: np.ndarray | None = None,
) -> EntryEvaluation:
    chosen = first_trigger_indices(
        dataset, predictions, policy, series_time_order=series_time_order)
    if not len(chosen):
        raise ConfirmationRefusal("confirmation policy produced an empty book")
    arrivals = tuple(_arrival(
        dataset, index, model_hash=predictions.model_hash,
        expected_pnl_usd=float(predictions.expected_pnl_usd[index]),
        pnl_q20_usd=float(predictions.pnl_q20_usd[index]),
        goal_probability=float(predictions.goal_probability[index]),
        wall_probability=float(predictions.wall_probability[index]),
        mae_q90_usd=float(predictions.mae_q90_usd[index]),
    ) for index in chosen)
    return replay(arrivals, expected_sessions=expected_sessions)


@dataclass(frozen=True, slots=True)
class DelayedCandidateCeiling:
    evaluation: EntryEvaluation
    selected_opportunity_ids: tuple[str, ...]
    selected_series_ids: tuple[str, ...]
    exact_objective_cents: int
    original_positive_options: int
    nondominated_options: int
    receipt_sha256: str


def _nondominated_positive_indices(dataset: ConfirmationDataset) -> np.ndarray:
    output: list[int] = []
    series = np.asarray(dataset.series_id, str)
    start = np.asarray(dataset.snapshot_ts_ns, np.int64)
    end = np.asarray(dataset.exit_ts_ns, np.int64)
    cents = np.rint(np.asarray(dataset.cert_close_usd, np.float64) * 100).astype(np.int64)
    if not np.allclose(cents / 100.0, dataset.cert_close_usd, atol=1e-7, rtol=0):
        raise ConfirmationRefusal("delayed ceiling outcomes are not exact cents")
    for key in sorted(set(series)):
        candidates = np.flatnonzero((series == key) & (cents > 0))
        for i in candidates:
            dominated = False
            for j in candidates:
                if i == j:
                    continue
                if (start[j] >= start[i] and end[j] <= end[i]
                        and cents[j] >= cents[i]
                        and (start[j] > start[i] or end[j] < end[i]
                             or cents[j] > cents[i])):
                    dominated = True
                    break
            if not dominated:
                output.append(int(i))
    return np.asarray(sorted(output), np.int64)


def _solve_day(
    dataset: ConfirmationDataset, indices: np.ndarray,
) -> tuple[np.ndarray, int]:
    """Exact binary interval/series/portfolio program for one trading day."""

    n = len(indices)
    if not n:
        return np.empty(0, np.int64), 0
    starts = np.asarray(dataset.snapshot_ts_ns, np.int64)[indices]
    ends = np.asarray(dataset.exit_ts_ns, np.int64)[indices]
    series = np.asarray(dataset.series_id, str)[indices]
    assets = np.asarray(dataset.asset, str)[indices]
    cents = np.rint(np.asarray(dataset.cert_close_usd, np.float64)[indices]
                     * 100).astype(np.int64)

    row_index: list[int] = []
    col_index: list[int] = []
    values: list[float] = []
    upper: list[float] = []

    def constraint(columns: Sequence[int], limit: int) -> None:
        row = len(upper)
        for column in columns:
            row_index.append(row); col_index.append(int(column)); values.append(1.0)
        upper.append(float(limit))

    for key in sorted(set(series)):
        columns = np.flatnonzero(series == key)
        if len(columns) > 1:
            constraint(columns.tolist(), 1)
    constraint(list(range(n)), C.MAX_ENTRIES_PORTFOLIO_DAY)

    # Closed intervals reproduce replay's ``open_until >= next decision`` law.
    # Every maximal overlap clique appears immediately after a start batch.
    for asset in sorted(set(assets)):
        columns = np.flatnonzero(assets == asset)
        active: set[int] = set()
        for timestamp in sorted(set(starts[columns].tolist())):
            active = {column for column in active if ends[column] >= timestamp}
            active.update(int(column) for column in columns
                          if starts[column] == timestamp)
            if len(active) > 1:
                constraint(sorted(active), 1)

    matrix = coo_array((values, (row_index, col_index)),
                       shape=(len(upper), n)).tocsr()
    result = milp(
        c=-cents.astype(np.float64), integrality=np.ones(n, np.int8),
        bounds=Bounds(np.zeros(n), np.ones(n)),
        constraints=LinearConstraint(
            matrix, np.full(len(upper), -np.inf), np.asarray(upper)),
        options={"mip_rel_gap": 0.0, "presolve": True},
    )
    if (not result.success or result.x is None
            or result.mip_gap is None or float(result.mip_gap) > 1e-9):
        raise ConfirmationRefusal(
            f"exact delayed ceiling MILP failed: status={result.status} {result.message}")
    selected_local = np.flatnonzero(np.asarray(result.x) > 0.5)
    if (np.any(np.abs(result.x[selected_local] - 1.0) > 1e-6)
            or len(selected_local) > C.MAX_ENTRIES_PORTFOLIO_DAY):
        raise ConfirmationRefusal("delayed ceiling solution is fractional/over-cap")
    return indices[selected_local], int(cents[selected_local].sum())


def exact_delayed_candidate_ceiling(
    dataset: ConfirmationDataset,
    *, expected_sessions: Iterable[SessionRef],
) -> DelayedCandidateCeiling:
    """Solve the exact best timestamp/schedule in the materialized universe."""

    dataset.validate()
    if dataset.snapshot_mode != "REPLAY":
        raise ConfirmationRefusal(
            "exact delayed ceiling requires the every-second REPLAY grid")
    positive = int(np.sum(np.asarray(dataset.cert_close_usd) > 0))
    retained = _nondominated_positive_indices(dataset)
    selected: list[int] = []
    objective = 0
    days = np.asarray(dataset.day, np.int64)
    for day in sorted(set(days[retained].tolist())):
        chosen, cents = _solve_day(dataset, retained[days[retained] == day])
        selected.extend(chosen.tolist()); objective += cents
    if not selected:
        raise ConfirmationRefusal("delayed candidate universe has no positive schedule")
    selected_array = np.asarray(sorted(selected), np.int64)
    opportunity_ids = tuple(sorted(np.asarray(
        dataset.opportunity_id, str)[selected_array].tolist()))
    series_ids = tuple(sorted(np.asarray(
        dataset.series_id, str)[selected_array].tolist()))
    if len(series_ids) != len(set(series_ids)):
        raise ConfirmationRefusal("delayed ceiling selected one candidate twice")
    receipt = C.object_sha256({
        "schema": CEILING_SCHEMA,
        "dataset": dataset.representation_sha256,
        "selected_opportunity_ids": opportunity_ids,
        "selected_series_ids": series_ids,
        "exact_objective_cents": objective,
        "original_positive_options": positive,
        "nondominated_options": len(retained),
        "portfolio_day_cap": C.MAX_ENTRIES_PORTFOLIO_DAY,
        "asset_occupancy": 1,
    })
    arrivals = tuple(_arrival(
        dataset, index, model_hash=f"delayed-ceiling:{receipt}",
        expected_pnl_usd=float(dataset.cert_close_usd[index]),
        pnl_q20_usd=float(dataset.cert_close_usd[index]),
        goal_probability=float(dataset.cert_close_usd[index] >= C.MIN_EXPECTANCY_USD),
        wall_probability=float(dataset.wall_hit[index]),
        mae_q90_usd=float(dataset.mae_usd[index]),
    ) for index in selected_array)
    evaluation = replay(arrivals, expected_sessions=expected_sessions)
    if (abs(evaluation.total_pnl_usd - objective / 100.0) > 1e-7
            or {row.candidate_id for row in evaluation.trade_results}
            != set(opportunity_ids)):
        raise ConfirmationRefusal("delayed ceiling solution did not survive canonical replay")
    return DelayedCandidateCeiling(
        evaluation=evaluation, selected_opportunity_ids=opportunity_ids,
        selected_series_ids=series_ids, exact_objective_cents=objective,
        original_positive_options=positive, nondominated_options=len(retained),
        receipt_sha256=receipt,
    )


def exact_delayed_candidate_ceiling_shards(
    datasets: Sequence[ConfirmationOpportunitySet],
    *, expected_sessions: Iterable[SessionRef],
) -> DelayedCandidateCeiling:
    """Exact block ceiling with memory bounded to one portfolio day.

    Asset occupancy and the portfolio-entry budget do not cross a trading-day
    boundary.  Solving each day jointly across assets is therefore exactly
    equivalent to one block MILP, while avoiding an all-days concatenation of
    the every-second universe.
    """

    shards = tuple(datasets)
    sessions = tuple(expected_sessions)
    if not shards or not sessions:
        raise ConfirmationRefusal("sharded delayed ceiling roster is empty")
    for dataset in shards:
        dataset.validate()
    first = shards[0]
    if (any(row.max_delay_sec != first.max_delay_sec for row in shards)
            or any(row.config_sha256 != first.config_sha256 for row in shards)
            or len({(str(asset), int(day)) for row in shards
                    for asset, day in zip(row.asset, row.day)})
               != len(shards)):
        raise ConfirmationRefusal(
            "sharded delayed ceiling config/session roster differs")
    by_day: dict[int, list[ConfirmationOpportunitySet]] = {}
    for row in shards:
        days = set(np.asarray(row.day, np.int64).tolist())
        if len(days) != 1:
            raise ConfirmationRefusal("delayed ceiling shard crosses trading days")
        by_day.setdefault(int(next(iter(days))), []).append(row)

    selected_rows: list[tuple[ConfirmationOpportunitySet, int]] = []
    original_positive = 0
    nondominated = 0
    objective = 0
    day_receipts: list[str] = []
    for day in sorted(by_day):
        universe = combine_confirmation_opportunity_sets(by_day[day])
        positive = int(np.sum(np.asarray(universe.cert_close_usd) > 0))
        retained = _nondominated_positive_indices(universe)
        chosen, cents = _solve_day(universe, retained)
        if not len(chosen):
            day_receipts.append(C.object_sha256({
                "schema": CEILING_SCHEMA, "day": day,
                "universe": universe.representation_sha256,
                "selected": (), "objective_cents": 0,
            }))
        else:
            for index in chosen:
                selected_rows.append((universe, int(index)))
            day_receipts.append(C.object_sha256({
                "schema": CEILING_SCHEMA, "day": day,
                "universe": universe.representation_sha256,
                "selected": tuple(sorted(np.asarray(
                    universe.opportunity_id, str)[chosen].tolist())),
                "objective_cents": cents,
            }))
        original_positive += positive
        nondominated += len(retained)
        objective += cents
    if not selected_rows:
        raise ConfirmationRefusal("sharded delayed universe has no positive schedule")
    opportunity_ids = tuple(sorted(
        str(row.opportunity_id[index]) for row, index in selected_rows))
    series_ids = tuple(sorted(
        str(row.series_id[index]) for row, index in selected_rows))
    if len(series_ids) != len(set(series_ids)):
        raise ConfirmationRefusal("sharded ceiling selected one candidate twice")
    receipt = C.object_sha256({
        "schema": "QRE2CONFCEILSHARD1",
        "shards": tuple(sorted(row.representation_sha256 for row in shards)),
        "day_receipts": tuple(day_receipts),
        "selected_opportunity_ids": opportunity_ids,
        "selected_series_ids": series_ids,
        "exact_objective_cents": objective,
        "original_positive_options": original_positive,
        "nondominated_options": nondominated,
        "portfolio_day_cap": C.MAX_ENTRIES_PORTFOLIO_DAY,
        "asset_occupancy": 1,
    })
    arrivals = tuple(_arrival(
        row, index, model_hash=f"delayed-ceiling:{receipt}",
        expected_pnl_usd=float(row.cert_close_usd[index]),
        pnl_q20_usd=float(row.cert_close_usd[index]),
        goal_probability=float(row.cert_close_usd[index]
                               >= C.MIN_EXPECTANCY_USD),
        wall_probability=float(row.wall_hit[index]),
        mae_q90_usd=float(row.mae_usd[index]),
    ) for row, index in selected_rows)
    evaluation = replay(arrivals, expected_sessions=sessions)
    if (abs(evaluation.total_pnl_usd - objective / 100.0) > 1e-7
            or {row.candidate_id for row in evaluation.trade_results}
            != set(opportunity_ids)):
        raise ConfirmationRefusal(
            "sharded delayed ceiling did not survive canonical replay")
    return DelayedCandidateCeiling(
        evaluation=evaluation, selected_opportunity_ids=opportunity_ids,
        selected_series_ids=series_ids, exact_objective_cents=objective,
        original_positive_options=original_positive,
        nondominated_options=nondominated, receipt_sha256=receipt)


__all__ = [
    "ConfirmationPolicy", "DelayedCandidateCeiling", "default_expected_sessions",
    "confirmation_series_time_order", "exact_delayed_candidate_ceiling",
    "exact_delayed_candidate_ceiling_shards", "first_trigger_indices",
    "replay_confirmation",
]
