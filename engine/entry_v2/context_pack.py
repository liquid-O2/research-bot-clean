"""Strict point-in-time context sequence construction for entry-v2."""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from typing import Iterable, Mapping

from . import common as C
from .contracts import (
    ContextPack,
    ContextPoint,
    ContextSeries,
    ContractError,
    Numeric,
    VintageClass,
)


HISTORY_LENGTH = 64

ASSET_CONTEXT_SERIES: Mapping[str, tuple[str, ...]] = {
    "SI": ("GVZ", "VIX", "RVX", "COT_DISAGG_SILVER", "SLV_FLOW_OZ",
           "SHFE_INV_SILVER", "FRED_DGS10", "FRED_T10YIE", "FRED_DFII10",
           "FRED_DTWEXBGS", "FRED_DEXJPUS", "JGB_10Y", "GOLD_SILVER_RATIO",
           "CAL_BLS", "CAL_FOMC"),
    "HG": ("GVZ", "VIX", "RVX", "COT_DISAGG_COPPER", "SHFE_INV_COPPER",
           "FRED_DGS10", "FRED_DTWEXBGS", "FRED_DEXCHUS", "FRED_DEXJPUS",
           "JGB_10Y", "GOLD_SILVER_RATIO", "CAL_BLS", "CAL_FOMC"),
    "NKD": ("NIKKEI_VI", "GVZ", "VIX", "RVX", "COT_TFF_NIKKEI",
            "FRED_DGS10", "FRED_DTWEXBGS", "FRED_DEXJPUS", "JGB_10Y",
            "GOLD_SILVER_RATIO", "CAL_BLS", "CAL_FOMC", "CAL_BOJ"),
}


@dataclass(frozen=True, slots=True)
class AvailableObservation:
    """One raw context release before point-in-time filtering."""

    stamp: str
    availability_ts_ns: int
    values: tuple[Numeric, ...]

    def __post_init__(self) -> None:
        if not self.stamp or int(self.availability_ts_ns) < 0 or not self.values:
            raise ContractError("invalid available context observation")


@dataclass(frozen=True, slots=True)
class ContextSource:
    series_id: str
    vintage_class: VintageClass
    observations: tuple[AvailableObservation, ...]

    def __post_init__(self) -> None:
        if not self.series_id:
            raise ContractError("context source needs series_id")
        object.__setattr__(self, "vintage_class", VintageClass(self.vintage_class))
        widths = {len(obs.values) for obs in self.observations}
        if len(widths) > 1:
            raise ContractError(f"context width changes inside {self.series_id}")
        object.__setattr__(self, "observations", tuple(sorted(
            self.observations,
            key=lambda obs: (obs.availability_ts_ns, obs.stamp,
                             repr(obs.values)),
        )))


def _delta(current: tuple[Numeric, ...], previous: tuple[Numeric, ...] | None,
           ) -> tuple[Numeric, ...]:
    if previous is None:
        return tuple(None for _ in current)
    out: list[Numeric] = []
    for now, old in zip(current, previous):
        if now is None or old is None or isinstance(now, bool) or isinstance(old, bool):
            out.append(None)
        else:
            out.append(float(now) - float(old))
    return tuple(out)


def _pack_one(series_id: str, decision_ts_ns: int,
              source: ContextSource | None) -> ContextSeries:
    if source is None:
        return ContextSeries(series_id, VintageClass.FIRST_PRINT, False, (), "MISSING_SOURCE")
    if source.series_id != series_id:
        raise ContractError(f"source key/id mismatch: {series_id} != {source.series_id}")
    if source.vintage_class is VintageClass.REVISED_VALUE:
        return ContextSeries(series_id, source.vintage_class, False, (), "REVISED_VALUE_MASKED")
    if source.vintage_class not in (VintageClass.FIRST_PRINT, VintageClass.SCHEDULE):
        raise ContractError(f"unsupported vintage class for {series_id}")

    # Sources are canonically ordered once at construction.  Binary search
    # preserves the strict availability wall without rescanning and sorting
    # thousands of observations for every candidate.
    end = bisect.bisect_left(
        source.observations,
        int(decision_ts_ns),
        key=lambda obs: obs.availability_ts_ns,
    )
    if not end:
        return ContextSeries(series_id, source.vintage_class, False, (), "NO_AVAILABLE_HISTORY")

    points: list[ContextPoint] = []
    start = max(0, end - HISTORY_LENGTH)
    previous: tuple[Numeric, ...] | None = (
        tuple(source.observations[start - 1].values) if start else None)
    for obs in source.observations[start:end]:
        points.append(ContextPoint(
            stamp=obs.stamp,
            availability_ts_ns=obs.availability_ts_ns,
            age_ns=decision_ts_ns - obs.availability_ts_ns,
            values=tuple(obs.values),
            deltas=_delta(tuple(obs.values), previous),
        ))
        previous = tuple(obs.values)
    return ContextSeries(series_id, source.vintage_class, True, tuple(points), None)


def build_context_pack(asset: str, decision_ts_ns: int,
                       sources: Mapping[str, ContextSource],
                       *, trading_day: int,
                       permit: C.FinalExamPermit | None = None,
                       roster: Iterable[str] | None = None) -> ContextPack:
    """Return the fixed last-64 context pack available strictly before arrival.

    ``REVISED_VALUE`` sources are represented by a typed zero mask.  They are
    never silently substituted with their latest-vintage values.
    """
    # Futures trading days do not always equal the UTC date of the decision.
    # The explicit trading-day wall must fire before the source mapping is
    # interrogated, otherwise a holdout-backed lazy mapping could be opened
    # before the refusal.
    C.guard_date(int(trading_day), permit)
    asset = str(asset).upper()
    if asset not in ASSET_CONTEXT_SERIES:
        raise ContractError(f"unsupported asset: {asset}")
    if int(decision_ts_ns) <= 0:
        raise ContractError("decision_ts_ns must be positive")
    ids = tuple(ASSET_CONTEXT_SERIES[asset] if roster is None else roster)
    if len(ids) != len(set(ids)):
        raise ContractError("context roster contains duplicate series")
    packed = tuple(_pack_one(series_id, int(decision_ts_ns), sources.get(series_id))
                   for series_id in ids)
    return ContextPack(asset, int(decision_ts_ns), packed)
