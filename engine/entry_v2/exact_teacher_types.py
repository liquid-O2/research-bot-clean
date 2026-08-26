"""Exact delayed teacher domain types and the day option universe."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from typing import Final, Sequence

import numpy as np

from . import common as C
from .tabular_delayed_corpus import DelayedOutcomeShard
from .tabular_recovery_contracts import DecisionAction, RecoveryRefusal


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


__all__ = [
    "ACTION_SOURCE_NAMES", "ActionQuery", "DayOptionUniverse",
    "ExactDaySolution", "PortfolioPrefixCondition", "RolloutStateProposal",
]
