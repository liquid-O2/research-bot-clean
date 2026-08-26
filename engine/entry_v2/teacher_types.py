"""Teacher path and label types. Privileged values stay off the inference example."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math

from . import common as C
from .contracts import ContractError, NANOS_PER_SECOND


class ValueBin(str, Enum):
    LOSS = "LOSS"
    ZERO_TO_599 = "ZERO_TO_599"
    SIX_HUNDRED_TO_999 = "SIX_HUNDRED_TO_999"
    ONE_THOUSAND_TO_1999 = "ONE_THOUSAND_TO_1999"
    TWO_THOUSAND_PLUS = "TWO_THOUSAND_PLUS"


def value_bin(value_usd: float) -> ValueBin:
    value = float(value_usd)
    if not math.isfinite(value):
        raise ContractError("teacher value must be finite")
    if value < 0.0:
        return ValueBin.LOSS
    if value < 600.0:
        return ValueBin.ZERO_TO_599
    if value < 1_000.0:
        return ValueBin.SIX_HUNDRED_TO_999
    if value < 2_000.0:
        return ValueBin.ONE_THOUSAND_TO_1999
    return ValueBin.TWO_THOUSAND_PLUS


@dataclass(frozen=True, slots=True)
class TeacherPath:
    candidate_id: str
    asset: str
    trading_day: int
    decision_ts_ns: int
    exit_ts_ns: int
    cert_close_usd: float
    mfe_usd: float
    mae_usd: float
    wall_hit: bool
    time_to_peak_sec: float

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ContractError("teacher path needs candidate_id")
        if self.asset not in {"SI", "HG", "NKD"}:
            raise ContractError(f"unsupported teacher asset: {self.asset}")
        if int(self.decision_ts_ns) <= 0 or int(self.exit_ts_ns) < int(self.decision_ts_ns):
            raise ContractError("teacher path exit precedes arrival")
        for name in ("cert_close_usd", "mfe_usd", "mae_usd", "time_to_peak_sec"):
            if not math.isfinite(float(getattr(self, name))):
                raise ContractError(f"{name} must be finite")
        if self.mfe_usd < 0 or self.mae_usd < 0 or self.time_to_peak_sec < 0:
            raise ContractError("MFE, MAE, and time-to-peak must be non-negative")

    @property
    def arrival_second(self) -> int:
        return self.decision_ts_ns // NANOS_PER_SECOND


@dataclass(frozen=True, slots=True)
class TeacherLabel:
    candidate_id: str
    cert_close_usd: float
    value_bin: ValueBin
    top3: bool
    rank: int
    mfe_usd: float
    mae_usd: float
    wall_hit: bool
    time_to_peak_sec: float
    payer: bool
    take_target: bool
    action_loss_mask: bool = True

    def __post_init__(self) -> None:
        if not self.candidate_id or int(self.rank) < 1:
            raise ContractError("teacher label needs candidate_id and positive rank")
        object.__setattr__(self, "value_bin", ValueBin(self.value_bin))
        if bool(self.top3) != (self.rank <= 3):
            raise ContractError("top3 must agree with rank")
        if value_bin(self.cert_close_usd) is not self.value_bin:
            raise ContractError("value_bin does not agree with cert_close_usd")
        if bool(self.payer) != (self.cert_close_usd > 0.0):
            raise ContractError("payer must mean strictly positive certificate value")
        if self.take_target and not self.action_loss_mask:
            raise ContractError("take_target requires action supervision")
        for name in ("mfe_usd", "mae_usd", "time_to_peak_sec"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0:
                raise ContractError(f"{name} must be finite and non-negative")


def _chronological_action_supervision(
    paths: tuple[TeacherPath, ...],
) -> tuple[frozenset[str], frozenset[str]]:
    """Label decisions once on arrival; future arrivals never compete.

    Every available same-asset/same-timestamp set is supervised together.
    Its highest-value candidate clearing $600 is the sole positive (ties use
    candidate id).  Occupancy or caps mask the complete blocked set instead
    of turning an unavailable action into a negative label.
    """

    open_until: dict[str, int] = {}
    asset_day_count: dict[tuple[str, int], int] = {}
    day_count: dict[int, int] = {}
    selected: set[str] = set()
    supervised: set[str] = set()
    ordered = sorted(paths, key=lambda item: (
        item.decision_ts_ns, item.asset, item.trading_day, item.candidate_id
    ))
    index = 0
    while index < len(ordered):
        decision_ts_ns = ordered[index].decision_ts_ns
        end = index + 1
        while end < len(ordered) and ordered[end].decision_ts_ns == decision_ts_ns:
            end += 1
        timestamp_rows = ordered[index:end]
        groups: dict[tuple[str, int], list[TeacherPath]] = {}
        for path in timestamp_rows:
            groups.setdefault((path.asset, path.trading_day), []).append(path)

        available: list[tuple[TeacherPath | None, tuple[TeacherPath, ...]]] = []
        for (asset, day), rows in sorted(groups.items()):
            group = tuple(sorted(rows, key=lambda item: item.candidate_id))
            if (open_until.get(asset, -1) >= decision_ts_ns
                    or asset_day_count.get((asset, day), 0)
                        >= C.MAX_ENTRIES_PER_ASSET_DAY
                    or day_count.get(day, 0) >= C.MAX_ENTRIES_PORTFOLIO_DAY):
                continue
            eligible = tuple(
                row for row in group
                if row.cert_close_usd >= C.MIN_EXPECTANCY_USD
            )
            winner = min(
                eligible,
                key=lambda item: (-item.cert_close_usd, item.candidate_id),
                default=None,
            )
            available.append((winner, group))

        # A timestamp can expose multiple assets at once.  Allocate any
        # scarce portfolio seats by the same privileged value/candidate order;
        # groups blocked by that cap are masked in full.
        winners_by_day: dict[int, list[tuple[TeacherPath, tuple[TeacherPath, ...]]]] = {}
        for winner, group in available:
            if winner is None:
                supervised.update(row.candidate_id for row in group)
            else:
                winners_by_day.setdefault(winner.trading_day, []).append(
                    (winner, group)
                )
        for day, winner_groups in sorted(winners_by_day.items()):
            remaining = C.MAX_ENTRIES_PORTFOLIO_DAY - day_count.get(day, 0)
            allocated = sorted(
                winner_groups,
                key=lambda item: (
                    -item[0].cert_close_usd,
                    item[0].candidate_id,
                    item[0].asset,
                ),
            )[:max(0, remaining)]
            for winner, group in allocated:
                supervised.update(row.candidate_id for row in group)
                selected.add(winner.candidate_id)
                key = (winner.asset, winner.trading_day)
                open_until[winner.asset] = winner.exit_ts_ns
                asset_day_count[key] = asset_day_count.get(key, 0) + 1
                day_count[day] = day_count.get(day, 0) + 1
        index = end
    return frozenset(selected), frozenset(supervised)
