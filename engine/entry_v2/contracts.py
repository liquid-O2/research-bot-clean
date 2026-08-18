"""Public, label-free contracts for the clean entry pipeline.

All timestamps in this package are UTC Unix nanoseconds.  The inference
example intentionally has no field capable of carrying a certificate, future
path, rank, or other teacher-only value; those live in :mod:`teacher` and are
joined by ``candidate_id`` only while constructing training batches.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
import re
from types import MappingProxyType
from typing import Mapping, TypeAlias


NANOS_PER_SECOND = 1_000_000_000
ASSETS = frozenset({"SI", "HG", "NKD"})

Scalar: TypeAlias = float | int | bool | str | None
Numeric: TypeAlias = float | int | None


class ContractError(ValueError):
    """A value violates an entry-v2 public contract."""


class VintageClass(str, Enum):
    FIRST_PRINT = "FIRST_PRINT"
    SCHEDULE = "SCHEDULE"
    REVISED_VALUE = "REVISED_VALUE"


class Side(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class ExitReason(str, Enum):
    CLOSE = "CLOSE"
    PHASE_CLOSE = "PHASE_CLOSE"
    WALL = "WALL"


def _finite(value: float | int, name: str) -> float:
    out = float(value)
    if not math.isfinite(out):
        raise ContractError(f"{name} must be finite")
    return out


def _probability(value: float, name: str) -> float:
    out = _finite(value, name)
    if not 0.0 <= out <= 1.0:
        raise ContractError(f"{name} must be in [0, 1]")
    return out


def _asset(value: str) -> str:
    out = str(value).upper()
    if out not in ASSETS:
        raise ContractError(f"unsupported asset: {value!r}")
    return out


def _d8(value: int) -> int:
    out = int(value)
    text = str(out)
    if len(text) != 8 or not text.isdigit():
        raise ContractError(f"trading_day must be YYYYMMDD, got {value!r}")
    return out


@dataclass(frozen=True, slots=True, order=True)
class SessionRef:
    """A denominator unit: one asset-session, including empty sessions."""

    asset: str
    trading_day: int
    session_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "asset", _asset(self.asset))
        object.__setattr__(self, "trading_day", _d8(self.trading_day))
        if not self.session_id:
            raise ContractError("session_id must be non-empty")


@dataclass(frozen=True, slots=True, order=True)
class AssetDayRegime:
    """A session-open, strictly causal regime declaration for one asset-day."""

    asset: str
    trading_day: int
    regime: str
    availability_ts_ns: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "asset", _asset(self.asset))
        object.__setattr__(self, "trading_day", _d8(self.trading_day))
        regime = str(self.regime).upper()
        if regime not in {"LOW", "MID", "HIGH", "UNKNOWN"}:
            raise ContractError(
                "asset-day regime must be LOW, MID, HIGH, or UNKNOWN"
            )
        object.__setattr__(self, "regime", regime)
        if int(self.availability_ts_ns) <= 0:
            raise ContractError("asset-day regime availability must be positive")

    @property
    def weak(self) -> bool:
        return self.regime == "LOW"

    @property
    def known(self) -> bool:
        return self.regime != "UNKNOWN"


@dataclass(frozen=True, slots=True)
class RawPrefixRef:
    """A shared raw-event shard and the strict ``[start, end)`` prefix."""

    shard: str
    event_start_index: int
    event_end_index: int
    event_count: int
    first_availability_ts_ns: int | None
    last_availability_ts_ns: int | None
    source_hash: str

    def __post_init__(self) -> None:
        if not self.shard or not self.source_hash:
            raise ContractError("raw prefix needs a shard and source_hash")
        start, end, count = (int(self.event_start_index),
                             int(self.event_end_index), int(self.event_count))
        if start < 0 or end < start or count != end - start:
            raise ContractError("event_count must equal event_end_index - event_start_index")
        if count == 0:
            if (self.first_availability_ts_ns is not None
                    or self.last_availability_ts_ns is not None):
                raise ContractError("empty prefixes cannot name first/last timestamps")
        else:
            if (self.first_availability_ts_ns is None
                    or self.last_availability_ts_ns is None):
                raise ContractError("non-empty prefixes need first/last timestamps")
            if (int(self.first_availability_ts_ns)
                    > int(self.last_availability_ts_ns)):
                raise ContractError("raw prefix timestamps are reversed")


@dataclass(frozen=True, slots=True)
class ContextPoint:
    stamp: str
    availability_ts_ns: int
    age_ns: int
    values: tuple[Numeric, ...]
    deltas: tuple[Numeric, ...]

    def __post_init__(self) -> None:
        if not self.stamp:
            raise ContractError("context stamp must be non-empty")
        if int(self.availability_ts_ns) < 0 or int(self.age_ns) <= 0:
            raise ContractError("context points must be strictly older than the decision")
        if len(self.values) == 0 or len(self.values) != len(self.deltas):
            raise ContractError("context values/deltas must have equal non-zero width")
        for name, seq in (("value", self.values), ("delta", self.deltas)):
            for value in seq:
                if value is not None:
                    _finite(value, f"context {name}")


@dataclass(frozen=True, slots=True)
class ContextSeries:
    series_id: str
    vintage_class: VintageClass
    mask: bool
    points: tuple[ContextPoint, ...] = ()
    missing_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.series_id:
            raise ContractError("context series_id must be non-empty")
        object.__setattr__(self, "vintage_class", VintageClass(self.vintage_class))
        if self.mask:
            if not self.points:
                raise ContractError("present context series needs at least one point")
            if self.missing_reason is not None:
                raise ContractError("present context series cannot have missing_reason")
            if self.vintage_class is VintageClass.REVISED_VALUE:
                raise ContractError("REVISED_VALUE series cannot enter a student pack")
        elif self.points:
            raise ContractError("masked context series cannot carry values")


@dataclass(frozen=True, slots=True)
class ContextPack:
    asset: str
    decision_ts_ns: int
    series: tuple[ContextSeries, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "asset", _asset(self.asset))
        if int(self.decision_ts_ns) <= 0:
            raise ContractError("decision_ts_ns must be positive")
        ids = [item.series_id for item in self.series]
        if len(ids) != len(set(ids)):
            raise ContractError("context series_id values must be unique")
        for item in self.series:
            for point in item.points:
                if point.availability_ts_ns >= self.decision_ts_ns:
                    raise ContractError("context availability must be strictly before decision")
                if point.age_ns != self.decision_ts_ns - point.availability_ts_ns:
                    raise ContractError("context age does not match decision timestamp")

    def by_id(self) -> Mapping[str, ContextSeries]:
        return MappingProxyType({item.series_id: item for item in self.series})


_TEACHER_FIELD = re.compile(
    r"(^|_)(cert|certificate|teacher|oracle|outcome|future|top3|rank|mfe|mae|"
    r"walled|wall_hit|time_to_peak|take_target|action_target|payer|value_bin|"
    r"enter|skip)(_|$)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class CausalEntryExample:
    """Everything an entry model may know at one candidate arrival."""

    candidate_id: str
    asset: str
    trading_day: int
    session_id: str
    decision_ts_ns: int
    side: Side
    phase: str
    locked_iid: int
    raw_prefix_ref: RawPrefixRef
    causal_features: Mapping[str, Scalar] = field(default_factory=dict)
    context: ContextPack | None = None
    lineage_hash: str = ""

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.session_id or not self.phase:
            raise ContractError("candidate_id, session_id, and phase are required")
        object.__setattr__(self, "asset", _asset(self.asset))
        object.__setattr__(self, "trading_day", _d8(self.trading_day))
        object.__setattr__(self, "side", Side(self.side))
        if int(self.decision_ts_ns) <= 0 or int(self.locked_iid) < 0:
            raise ContractError("decision timestamp and locked_iid are invalid")
        if not self.lineage_hash:
            raise ContractError("lineage_hash is required")
        clean: dict[str, Scalar] = {}
        for name, value in self.causal_features.items():
            if not name or _TEACHER_FIELD.search(name):
                raise ContractError(f"teacher/future field forbidden in causal_features: {name!r}")
            if isinstance(value, float):
                _finite(value, f"causal feature {name}")
            clean[str(name)] = value
        object.__setattr__(self, "causal_features", MappingProxyType(dict(sorted(clean.items()))))
        if self.raw_prefix_ref.event_count:
            assert self.raw_prefix_ref.last_availability_ts_ns is not None
            if (self.raw_prefix_ref.last_availability_ts_ns
                    >= self.decision_ts_ns):
                raise ContractError("raw prefix contains an event at/after decision_ts_ns")
        if self.context is not None:
            if self.context.asset != self.asset or self.context.decision_ts_ns != self.decision_ts_ns:
                raise ContractError("context pack does not belong to this example")

    @property
    def session(self) -> SessionRef:
        return SessionRef(self.asset, self.trading_day, self.session_id)

    @property
    def arrival_second(self) -> int:
        return self.decision_ts_ns // NANOS_PER_SECOND


@dataclass(frozen=True, slots=True)
class EntryScore:
    candidate_id: str
    asset: str
    decision_ts_ns: int
    model_hash: str
    priority_score: float
    take_probability: float
    expected_pnl_usd: float
    expected_pnl_lower_usd: float
    top3_probability: float
    mae_p90_usd: float
    wall_probability: float
    enter: bool

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.model_hash:
            raise ContractError("score needs candidate_id and model_hash")
        object.__setattr__(self, "asset", _asset(self.asset))
        if int(self.decision_ts_ns) <= 0:
            raise ContractError("score decision_ts_ns must be positive")
        for name in ("priority_score", "expected_pnl_usd", "expected_pnl_lower_usd",
                     "mae_p90_usd"):
            _finite(getattr(self, name), name)
        if self.mae_p90_usd < 0:
            raise ContractError("mae_p90_usd cannot be negative")
        for name in ("take_probability", "top3_probability", "wall_probability"):
            _probability(getattr(self, name), name)


@dataclass(frozen=True, slots=True)
class TradeResult:
    candidate_id: str
    asset: str
    trading_day: int
    session_id: str
    entry_ts_ns: int
    exit_ts_ns: int
    exit_reason: ExitReason
    pnl_usd: float


@dataclass(frozen=True, slots=True)
class AssetDayResult:
    """One certification denominator unit, aggregated across its sessions."""

    asset: str
    trading_day: int
    session_ids: tuple[str, ...]
    pnl_usd: float
    trades: int
    max_drawdown_usd: float


@dataclass(frozen=True, slots=True)
class AssetEvaluation:
    asset: str
    asset_days: int
    trades: int
    total_pnl_usd: float
    usd_per_asset_day: float
    usd_per_trade: float
    zero_asset_days: int
    worst_asset_day_usd: float
    max_drawdown_usd: float
    drawdown_p90_usd: float
    drawdown_breach_rate: float


@dataclass(frozen=True, slots=True)
class EntryEvaluation:
    """Arrival replay metrics on the explicit all-asset-day denominator."""

    asset_days: int
    trades: int
    total_pnl_usd: float
    usd_per_asset_day: float
    usd_per_trade: float
    zero_asset_days: int
    worst_asset_day_usd: float
    max_drawdown_usd: float
    drawdown_p90_usd: float
    drawdown_breach_rate: float
    asset_day_results: tuple[AssetDayResult, ...]
    trade_results: tuple[TradeResult, ...]
    by_asset: tuple[AssetEvaluation, ...]
