"""Deterministic arrival-only entry replay for entry-v2."""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass, replace
import hashlib
import json
import math
from typing import Iterable

from .contracts import (
    AssetDayResult,
    AssetEvaluation,
    CausalEntryExample,
    ContractError,
    EntryEvaluation,
    EntryScore,
    ExitReason,
    SessionRef,
    TradeResult,
)


WALL_LOSS_USD = -900.0
MAX_ENTRIES_PER_ASSET_DAY = 3
MAX_ENTRIES_PER_DAY = 9


@dataclass(frozen=True, slots=True)
class ReplayOutcome:
    """Outcome-plane inputs, never fields on ``CausalEntryExample``.

    The resolved exit is the earliest of anchored close, phase close, and the
    first $900 wall touch.  Ties conservatively resolve WALL before phase close
    before ordinary close.
    """

    candidate_id: str
    close_ts_ns: int
    close_pnl_usd: float
    phase_close_ts_ns: int
    phase_close_pnl_usd: float
    wall_hit_ts_ns: int | None = None
    wall_pnl_usd: float = WALL_LOSS_USD

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ContractError("replay outcome needs candidate_id")
        for name in ("close_pnl_usd", "phase_close_pnl_usd", "wall_pnl_usd"):
            if not math.isfinite(float(getattr(self, name))):
                raise ContractError(f"{name} must be finite")
        if self.wall_pnl_usd > 0:
            raise ContractError("wall_pnl_usd cannot be positive")
        if int(self.close_ts_ns) <= 0 or int(self.phase_close_ts_ns) <= 0:
            raise ContractError("replay exit timestamps must be positive")
        if self.wall_hit_ts_ns is not None and int(self.wall_hit_ts_ns) <= 0:
            raise ContractError("wall_hit_ts_ns must be positive")

    def resolve(self, decision_ts_ns: int) -> tuple[int, float, ExitReason]:
        if self.close_ts_ns < decision_ts_ns or self.phase_close_ts_ns < decision_ts_ns:
            raise ContractError(f"exit precedes arrival for {self.candidate_id}")
        choices = [
            (int(self.close_ts_ns), 2, float(self.close_pnl_usd), ExitReason.CLOSE),
            (int(self.phase_close_ts_ns), 1, float(self.phase_close_pnl_usd),
             ExitReason.PHASE_CLOSE),
        ]
        if self.wall_hit_ts_ns is not None:
            if self.wall_hit_ts_ns < decision_ts_ns:
                raise ContractError(f"wall precedes arrival for {self.candidate_id}")
            choices.append((int(self.wall_hit_ts_ns), 0, float(self.wall_pnl_usd),
                            ExitReason.WALL))
        exit_ts, _priority, pnl, reason = min(choices, key=lambda item: (item[0], item[1]))
        return exit_ts, pnl, reason


@dataclass(frozen=True, slots=True)
class ScoredArrival:
    example: CausalEntryExample
    score: EntryScore
    outcome: ReplayOutcome

    def __post_init__(self) -> None:
        if (self.example.candidate_id != self.score.candidate_id
                or self.example.candidate_id != self.outcome.candidate_id):
            raise ContractError("example, score, and outcome candidate_id differ")
        if self.example.asset != self.score.asset:
            raise ContractError("example and score asset differ")
        if self.example.decision_ts_ns != self.score.decision_ts_ns:
            raise ContractError("example and score timestamps differ")
        # Resolve now so bad outcome clocks refuse before any replay state is
        # changed.
        self.outcome.resolve(self.example.decision_ts_ns)


@dataclass(frozen=True, slots=True)
class CandidateCeiling:
    """Full-hindsight schedule ceiling over the fixed candidate universe."""

    evaluation: EntryEvaluation
    selected_candidate_ids: tuple[str, ...]
    schedule_sha256: str


def _better_schedule(
    left: tuple[float, tuple[str, ...]],
    right: tuple[float, tuple[str, ...]],
) -> tuple[float, tuple[str, ...]]:
    if left[0] != right[0]:
        return left if left[0] > right[0] else right
    return left if left[1] < right[1] else right


def _asset_day_ceiling(rows: tuple[ScoredArrival, ...]) -> tuple[str, ...]:
    """Exact weighted-interval schedule with at most three entries."""

    intervals: list[tuple[int, int, float, str]] = []
    for row in rows:
        exit_ns, pnl_usd, _reason = row.outcome.resolve(
            row.example.decision_ts_ns)
        if pnl_usd <= 0.0:
            continue
        start_ns = row.example.decision_ts_ns
        intervals.append((exit_ns, start_ns, float(pnl_usd),
                          row.example.candidate_id))
    intervals.sort(key=lambda item: (item[0], item[1], item[3]))
    ends = [item[0] for item in intervals]
    # dp[i][k] is the best schedule among the first i intervals using at most k.
    dp: list[list[tuple[float, tuple[str, ...]]]] = [
        [(0.0, ()) for _ in range(MAX_ENTRIES_PER_ASSET_DAY + 1)]
        for _ in range(len(intervals) + 1)
    ]
    for i, (_end_ns, start_ns, pnl_usd, candidate_id) in enumerate(intervals, 1):
        # Equal-time exit/entry ordering is unknowable from the timestamp
        # alone.  Match the native C++ law and permit only exits strictly
        # before the next decision.
        previous = bisect_left(ends, start_ns, 0, i - 1)
        for cap in range(1, MAX_ENTRIES_PER_ASSET_DAY + 1):
            skip = dp[i - 1][cap]
            base = dp[previous][cap - 1]
            take = (base[0] + pnl_usd, base[1] + (candidate_id,))
            dp[i][cap] = _better_schedule(skip, take)
    return dp[-1][MAX_ENTRIES_PER_ASSET_DAY][1]


def candidate_ceiling(
    arrivals: Iterable[ScoredArrival], *,
    expected_sessions: Iterable[SessionRef],
) -> CandidateCeiling:
    """Return the exact candidate-set schedule ceiling.

    This is deliberately not an online prophet.  It solves the weighted
    interval schedule with full future knowledge, independently per asset-day.
    With the fixed three-asset universe, the three-per-asset cap implies the
    nine-per-day portfolio cap.  The selected schedule is then passed through
    the same replay implementation as every learned policy.
    """

    rows = tuple(arrivals)
    groups: dict[tuple[str, int], list[ScoredArrival]] = {}
    for row in rows:
        groups.setdefault((row.example.asset, row.example.trading_day), []).append(row)
    selected: set[str] = set()
    by_day: dict[int, int] = {}
    for (_asset, day), group in sorted(groups.items()):
        chosen = _asset_day_ceiling(tuple(group))
        selected.update(chosen)
        by_day[day] = by_day.get(day, 0) + len(chosen)
    if any(count > MAX_ENTRIES_PER_DAY for count in by_day.values()):
        raise ContractError("candidate ceiling exceeds portfolio daily cap")
    ordered_ids = tuple(sorted(selected))
    schedule_hash = hashlib.sha256(json.dumps(
        ordered_ids, separators=(",", ":")
    ).encode()).hexdigest()
    oracle_rows = tuple(ScoredArrival(
        row.example,
        replace(
            row.score,
            model_hash=f"candidate-ceiling:{schedule_hash}",
            enter=row.example.candidate_id in selected,
        ),
        row.outcome,
    ) for row in rows)
    evaluation = replay(oracle_rows, expected_sessions=expected_sessions)
    if {trade.candidate_id for trade in evaluation.trade_results} != selected:
        raise ContractError("candidate ceiling schedule did not survive replay law")
    return CandidateCeiling(evaluation, ordered_ids, schedule_hash)


def _drawdown(pnls: Iterable[float]) -> float:
    cumulative = 0.0
    peak = 0.0
    worst = 0.0
    for pnl in pnls:
        cumulative += float(pnl)
        peak = max(peak, cumulative)
        worst = max(worst, peak - cumulative)
    return worst


def _p90(values: Iterable[float]) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    # Conservative nearest-rank p90, deterministic for small day counts.
    return ordered[max(0, math.ceil(0.90 * len(ordered)) - 1)]


def _asset_eval(
    asset: str,
    days: tuple[AssetDayResult, ...],
    asset_trades: tuple[TradeResult, ...],
) -> AssetEvaluation:
    if not days:
        raise ContractError(f"asset-day denominator is empty for {asset}")
    trade_count = sum(row.trades for row in days)
    total = sum(row.pnl_usd for row in days)
    chronological = tuple(sorted(
        asset_trades, key=lambda row: (row.entry_ts_ns, row.candidate_id)
    ))
    return AssetEvaluation(
        asset=asset,
        asset_days=len(days),
        trades=trade_count,
        total_pnl_usd=total,
        usd_per_asset_day=total / len(days),
        usd_per_trade=total / trade_count if trade_count else 0.0,
        zero_asset_days=sum(row.trades == 0 for row in days),
        worst_asset_day_usd=min(row.pnl_usd for row in days),
        max_drawdown_usd=_drawdown(row.pnl_usd for row in chronological),
        drawdown_p90_usd=_p90(row.max_drawdown_usd for row in days),
        drawdown_breach_rate=(sum(row.max_drawdown_usd > 1_000.0 for row in days)
                              / len(days)),
    )


def replay(arrivals: Iterable[ScoredArrival], *,
           expected_sessions: Iterable[SessionRef]) -> EntryEvaluation:
    """Replay final decisions once, in arrival order.

    The caller must supply every eligible asset-session, including those with
    no candidates or no entries.  Only candidates with the exact same native
    ``decision_ts_ns`` are simultaneous and may be ranked together.  A later
    nanosecond—even inside the same wall-clock second—is a later arrival and
    cannot influence the earlier decision.
    """
    sessions = tuple(sorted(expected_sessions))
    if not sessions:
        raise ContractError("expected_sessions cannot be empty")
    if len(sessions) != len(set(sessions)):
        raise ContractError("expected_sessions contains duplicates")
    expected = set(sessions)
    rows = tuple(arrivals)
    ids = [row.example.candidate_id for row in rows]
    if len(ids) != len(set(ids)):
        raise ContractError("duplicate replay candidate_id")
    hashes = {row.score.model_hash for row in rows}
    if len(hashes) > 1:
        raise ContractError("one replay cannot mix model hashes")
    for row in rows:
        if row.example.session not in expected:
            raise ContractError(f"candidate outside expected sessions: {row.example.candidate_id}")

    ordered = sorted(rows, key=lambda row: (
        row.example.decision_ts_ns, row.example.candidate_id))
    open_until: dict[str, int] = {}
    asset_day_count: dict[tuple[str, int], int] = {}
    day_count: dict[int, int] = {}
    trades: list[TradeResult] = []
    i = 0
    while i < len(ordered):
        decision_ts_ns = ordered[i].example.decision_ts_ns
        j = i + 1
        while (
            j < len(ordered)
            and ordered[j].example.decision_ts_ns == decision_ts_ns
        ):
            j += 1

        # Exact-same-timestamp candidates are simultaneous.  Keep only the
        # deterministic best eligible score for each asset.
        best: dict[str, ScoredArrival] = {}
        for row in ordered[i:j]:
            example, score = row.example, row.score
            if not score.enter:
                continue
            if open_until.get(example.asset, -1) >= decision_ts_ns:
                continue
            key = (example.asset, example.trading_day)
            if asset_day_count.get(key, 0) >= MAX_ENTRIES_PER_ASSET_DAY:
                continue
            prior = best.get(example.asset)
            ranking = (-score.priority_score, example.candidate_id)
            if prior is None:
                best[example.asset] = row
            else:
                prior_ranking = (
                    -prior.score.priority_score,
                    prior.example.candidate_id,
                )
                if ranking < prior_ranking:
                    best[example.asset] = row

        choices = sorted(best.values(), key=lambda row: (
            -row.score.priority_score,
            row.example.asset, row.example.candidate_id))
        for row in choices:
            example = row.example
            if day_count.get(example.trading_day, 0) >= MAX_ENTRIES_PER_DAY:
                continue
            key = (example.asset, example.trading_day)
            if asset_day_count.get(key, 0) >= MAX_ENTRIES_PER_ASSET_DAY:
                continue
            exit_ts_ns, pnl_usd, reason = row.outcome.resolve(example.decision_ts_ns)
            open_until[example.asset] = exit_ts_ns
            asset_day_count[key] = asset_day_count.get(key, 0) + 1
            day_count[example.trading_day] = day_count.get(example.trading_day, 0) + 1
            trades.append(TradeResult(
                candidate_id=example.candidate_id,
                asset=example.asset,
                trading_day=example.trading_day,
                session_id=example.session_id,
                entry_ts_ns=example.decision_ts_ns,
                exit_ts_ns=exit_ts_ns,
                exit_reason=reason,
                pnl_usd=pnl_usd,
            ))
        i = j

    by_session: dict[SessionRef, list[TradeResult]] = {
        session: [] for session in sessions
    }
    for trade in trades:
        key = SessionRef(trade.asset, trade.trading_day, trade.session_id)
        by_session[key].append(trade)
    # Session ids remain an internal routing key.  Certification and every
    # public metric aggregate them to exactly one (asset, trading_day) unit.
    grouped_sessions: dict[tuple[str, int], list[SessionRef]] = {}
    for session in sessions:
        grouped_sessions.setdefault(
            (session.asset, session.trading_day), []
        ).append(session)
    asset_day_results: list[AssetDayResult] = []
    for (asset, trading_day), group in sorted(grouped_sessions.items()):
        day_trades = sorted(
            (
                trade
                for session in group
                for trade in by_session[session]
            ),
            key=lambda item: (item.entry_ts_ns, item.candidate_id),
        )
        asset_day_results.append(AssetDayResult(
            asset=asset,
            trading_day=trading_day,
            session_ids=tuple(sorted(session.session_id for session in group)),
            pnl_usd=sum(trade.pnl_usd for trade in day_trades),
            trades=len(day_trades),
            max_drawdown_usd=_drawdown(trade.pnl_usd for trade in day_trades),
        ))
    results = tuple(asset_day_results)
    total = sum(row.pnl_usd for row in results)
    n_trades = len(trades)
    assets = sorted({session.asset for session in sessions})
    per_asset = tuple(_asset_eval(
        asset,
        tuple(row for row in results if row.asset == asset),
        tuple(trade for trade in trades if trade.asset == asset),
    ) for asset in assets)
    daily_drawdowns = tuple(row.max_drawdown_usd for row in results)
    per_asset_mdd = tuple(row.max_drawdown_usd for row in per_asset)
    return EntryEvaluation(
        asset_days=len(results),
        trades=n_trades,
        total_pnl_usd=total,
        usd_per_asset_day=total / len(results),
        usd_per_trade=total / n_trades if n_trades else 0.0,
        zero_asset_days=sum(row.trades == 0 for row in results),
        worst_asset_day_usd=min(row.pnl_usd for row in results),
        # Certification MDD is the worst chronological cumulative per-asset
        # trade-PnL drawdown.  Daily trade-path drawdowns remain p90
        # diagnostics only.
        max_drawdown_usd=max(per_asset_mdd),
        drawdown_p90_usd=_p90(daily_drawdowns),
        drawdown_breach_rate=(sum(value > 1_000.0 for value in daily_drawdowns)
                              / len(daily_drawdowns)),
        asset_day_results=results,
        trade_results=tuple(trades),
        by_asset=per_asset,
    )
