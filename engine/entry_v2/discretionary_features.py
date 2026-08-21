#!/usr/bin/env python3
"""Causal discretionary-state features for the Entry V2 tabular learner.

The discretionary documents describe a hierarchy rather than a single entry
pattern: auction location and level memory establish the thesis, price-local
effort/reward establishes control, and an ordered defense/reclaim/retest state
times the expression.  This module measures those objects from the lossless
MBP-1 prefix.  It deliberately does not consume a teacher, an outcome, or an
event at/after the decision boundary.

The profile is frozen at completed five-minute boundaries.  Price ledgers are
queried by exclusive receive-second cutoffs.  ``LEVEL_ASSOCIATION_DESTROYED``
is a registered negative control: a causal, fixed bijection scrambles event
price coordinates while preserving every event and metric marginal.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Mapping

import numpy as np

from .diagnostic_inputs import native_book_quality


DISCRETIONARY_FEATURE_SCHEMA = "QRE2DISCRETIONARY8"
PROFILE_INTERVAL_SEC = 300
VALUE_AREA_FRACTION = 0.70
PROFILE_KERNEL = np.asarray((1.0, 2.0, 3.0, 2.0, 1.0), np.float64) / 9.0
LEVEL_ASSOCIATION_MODES = frozenset((
    "REAL", "LEVEL_ASSOCIATION_DESTROYED", "FILL_COUPLING_DESTROYED",
))
PRIOR_SESSION_SCHEMA = "QRE2DISCPRIOR2"
_DESTROY_BLOCK_TICKS = 64
_DESTROY_MULTIPLIER = 13
_DESTROY_INVERSE = 5  # 13 * 5 == 1 (mod 64)


def _destroy_shift(asset: str) -> int:
    return {"SI": 7, "HG": 11, "NKD": 17}.get(str(asset), 23)


def _destroy_tick(tick: int, asset: str) -> int:
    """Fixed no-fixed-point permutation inside causal 64-tick bands."""

    block, offset = divmod(int(tick), _DESTROY_BLOCK_TICKS)
    mapped = (_DESTROY_MULTIPLIER * offset + _destroy_shift(asset)) \
        % _DESTROY_BLOCK_TICKS
    return block * _DESTROY_BLOCK_TICKS + mapped


def _destroy_tick_inverse(tick: int, asset: str) -> int:
    block, offset = divmod(int(tick), _DESTROY_BLOCK_TICKS)
    original = (_DESTROY_INVERSE * (offset - _destroy_shift(asset))) \
        % _DESTROY_BLOCK_TICKS
    return block * _DESTROY_BLOCK_TICKS + original


class DiscretionaryFeatureRefusal(RuntimeError):
    """A raw-state or causal-boundary contract was violated."""


class PriorSessionContext:
    """Compact, completed-session auction and per-price memory."""

    def __init__(
        self, *, rows: np.ndarray, asset: str, trading_day: int,
        event_pack_sha256: str, raw_tick: int, multiplier: int,
    ) -> None:
        self.asset = str(asset); self.trading_day = int(trading_day)
        self.event_pack_sha256 = str(event_pack_sha256)
        self.raw_tick = int(raw_tick); self.multiplier = int(multiplier)
        self.factor = .5e-9 * self.multiplier
        source = np.asarray(rows)
        if not len(source):
            raise DiscretionaryFeatureRefusal("prior session is empty")
        action = source["action"]; side = source["side"]
        price = source["price"].astype(np.int64)
        size = source["size"].astype(np.int64)
        ts = source["ts_recv_ns"].astype(np.int64)
        sec = source["receive_session_sec"].astype(np.int64)
        raw_book = ((source["bid_px"] > 0)
                    & (source["ask_px"] > source["bid_px"])
                    & ((source["ask_px"].astype(np.int64)
                        - source["bid_px"].astype(np.int64)) % self.raw_tick == 0))
        quality = native_book_quality(ts, source["flags"], raw_book)
        trusted_message = np.asarray(quality.trusted_message, bool)
        trusted_economic = np.asarray(quality.trusted_economic, bool)
        trade = (action == ord("T")) & trusted_message & (price > 0) \
            & (price % self.raw_tick == 0) & (size > 0)
        trade_tick = (price[trade] // self.raw_tick).astype(np.int64)
        trade_size = size[trade]
        self.profile = _profile_state(
            trade_tick, trade_size, int(sec.max()) + 1,
            int(trade_tick[-1]) if len(trade_tick) else 0)

        valid_book = trusted_economic
        book_index = np.flatnonzero(valid_book)
        if not len(book_index):
            raise DiscretionaryFeatureRefusal("prior session has no trusted BBO")
        self.book_ts = ts[book_index]
        self.book_mid2 = (source["bid_px"][book_index].astype(np.int64)
                          + source["ask_px"][book_index].astype(np.int64))
        self.close_mid2 = int(self.book_mid2[-1])
        self.low_mid2 = int(self.book_mid2.min())
        self.high_mid2 = int(self.book_mid2.max())

        self.levels: dict[int, dict[str, float]] = {}
        trade_indices = np.flatnonzero(trade)
        trade_order = np.argsort(trade_tick, kind="stable")
        ordered_ticks = trade_tick[trade_order]
        starts = np.r_[
            0, np.flatnonzero(ordered_ticks[1:] != ordered_ticks[:-1]) + 1]
        stops = np.r_[starts[1:], len(ordered_ticks)]
        for start, stop in zip(starts, stops):
            tick = int(ordered_ticks[start])
            local = trade_indices[trade_order[start:stop]]
            local_ts = ts[local]
            local_size = size[local]
            buy = side[local] == ord("B")
            sell = side[local] == ord("A")
            buy_ts = local_ts[buy]; sell_ts = local_ts[sell]
            buy_bursts = buy_ts[np.r_[True, np.diff(buy_ts) > 5_000_000_000]] \
                if len(buy_ts) else buy_ts
            sell_bursts = sell_ts[np.r_[True, np.diff(sell_ts) > 5_000_000_000]] \
                if len(sell_ts) else sell_ts
            values = {
                "trade_volume": float(local_size.sum(dtype=np.int64)),
                "buy_volume": float(local_size[buy].sum(dtype=np.int64)),
                "sell_volume": float(local_size[sell].sum(dtype=np.int64)),
                "buy_bursts": float(len(buy_bursts)),
                "sell_bursts": float(len(sell_bursts)),
            }
            for horizon in (30, 120):
                for name, bursts, direction in (
                        ("sell", sell_bursts, 1),
                        ("buy", buy_bursts, -1)):
                    favorable: list[float] = []
                    adverse: list[float] = []
                    for timestamp in bursts[-40:]:
                        left = int(np.searchsorted(
                            self.book_ts, timestamp, side="left"))
                        right = int(np.searchsorted(
                            self.book_ts,
                            timestamp + horizon * 1_000_000_000, side="left"))
                        if left >= right:
                            continue
                        base = int(self.book_mid2[max(0, left - 1)])
                        path = direction * (self.book_mid2[left:right] - base) * self.factor
                        favorable.append(float(max(0.0, np.max(path))))
                        adverse.append(float(max(0.0, -np.min(path))))
                    values[f"{name}_reaction_{horizon}_count"] = float(len(favorable))
                    values[f"{name}_reaction_{horizon}_sum"] = float(
                        np.sum(favorable) if favorable else 0.0)
                    values[f"{name}_reaction_{horizon}_max"] = float(
                        np.max(favorable) if favorable else 0.0)
                    values[f"{name}_reaction_{horizon}_defense_count"] = float(
                        np.sum(np.asarray(favorable) > np.asarray(adverse))
                        if favorable else 0.0)
            self.levels[int(tick)] = values
        self.receipt_sha256 = _simple_sha({
            "schema": PRIOR_SESSION_SCHEMA, "asset": self.asset,
            "trading_day": self.trading_day,
            "event_pack_sha256": self.event_pack_sha256,
            "raw_tick": self.raw_tick, "multiplier": self.multiplier,
            "profile": None if self.profile is None else {
                name: getattr(self.profile, name)
                for name in self.profile.__dataclass_fields__},
            "close_mid2": self.close_mid2, "low_mid2": self.low_mid2,
            "high_mid2": self.high_mid2, "levels": self.levels,
        })

    @staticmethod
    def empty_feature_map() -> Mapping[str, float]:
        values: dict[str, float] = {
            "disc_prior_present": 0.0,
            "disc_prior_close_aligned_usd": 0.0,
            "disc_prior_low_aligned_usd": 0.0,
            "disc_prior_high_aligned_usd": 0.0,
            "disc_prior_range_usd": 0.0,
        }
        for name in ("poc", "val", "vah", "hvn", "lvn"):
            values[f"disc_prior_{name}_aligned_usd"] = 0.0
        values["disc_prior_inside_value"] = 0.0
        for radius in (0, 2, 4):
            prefix = f"disc_prior_level_z{radius}_"
            for name in (
                    "untouched", "trade_volume", "attack_volume", "lift_volume",
                    "attack_fraction", "attack_bursts", "lift_bursts"):
                values[prefix + name] = 0.0
            for horizon in (30, 120):
                for name in ("count", "mean_usd", "max_usd", "defense_rate"):
                    values[prefix + f"reaction_{horizon}_{name}"] = 0.0
            values[prefix + "distance_ticks"] = 0.0
            values[prefix + "tick_value_usd"] = 0.0
        return MappingProxyType(values)

    def feature_map(
        self, *, current_mid2: int, formation_bid: int,
        formation_ask: int, side: int,
        level_association_mode: str = "REAL",
    ) -> Mapping[str, float]:
        if level_association_mode not in LEVEL_ASSOCIATION_MODES:
            raise DiscretionaryFeatureRefusal(
                "unknown prior level-association mode")
        unit = self.raw_tick * 1e-9 * self.multiplier
        center = (formation_bid if side > 0 else formation_ask) // self.raw_tick
        values: dict[str, float] = {
            "disc_prior_present": 1.0,
            "disc_prior_close_aligned_usd": float(
                side * (current_mid2 - self.close_mid2) * self.factor),
            "disc_prior_low_aligned_usd": float(
                side * (current_mid2 - self.low_mid2) * self.factor),
            "disc_prior_high_aligned_usd": float(
                side * (current_mid2 - self.high_mid2) * self.factor),
            "disc_prior_range_usd": float(
                (self.high_mid2 - self.low_mid2) * self.factor),
        }
        profile = self.profile
        for name in ("poc", "val", "vah", "hvn", "lvn"):
            tick = (None if profile is None else {
                "poc": profile.poc_tick, "val": profile.val_tick,
                "vah": profile.vah_tick, "hvn": profile.nearest_hvn_tick,
                "lvn": profile.nearest_lvn_tick,
            }[name])
            values[f"disc_prior_{name}_aligned_usd"] = (0.0 if tick is None else
                float(side * (current_mid2 - 2 * tick * self.raw_tick) * self.factor))
        current_tick = current_mid2 / (2.0 * self.raw_tick)
        values["disc_prior_inside_value"] = float(
            profile is not None and profile.val_tick <= current_tick <= profile.vah_tick)
        for radius in (0, 2, 4):
            totals: dict[str, float] = {}
            for tick in range(center - radius, center + radius + 1):
                source_tick = (
                    _destroy_tick_inverse(tick, self.asset)
                    if level_association_mode == "LEVEL_ASSOCIATION_DESTROYED"
                    else tick)
                for name, value in self.levels.get(source_tick, {}).items():
                    if name.endswith("_max"):
                        totals[name] = max(totals.get(name, 0.0), value)
                    else:
                        totals[name] = totals.get(name, 0.0) + value
            attack = "sell" if side > 0 else "buy"
            lift = "buy" if side > 0 else "sell"
            prefix = f"disc_prior_level_z{radius}_"
            trade_volume = totals.get("trade_volume", 0.0)
            attack_volume = totals.get(f"{attack}_volume", 0.0)
            values.update({
                prefix + "untouched": float(trade_volume == 0.0),
                prefix + "trade_volume": trade_volume,
                prefix + "attack_volume": attack_volume,
                prefix + "lift_volume": totals.get(f"{lift}_volume", 0.0),
                prefix + "attack_fraction": (
                    attack_volume / trade_volume if trade_volume else 0.0),
                prefix + "attack_bursts": totals.get(f"{attack}_bursts", 0.0),
                prefix + "lift_bursts": totals.get(f"{lift}_bursts", 0.0),
            })
            for horizon in (30, 120):
                count = totals.get(
                    f"{attack}_reaction_{horizon}_count", 0.0)
                values.update({
                    prefix + f"reaction_{horizon}_count": count,
                    prefix + f"reaction_{horizon}_mean_usd": (
                        totals.get(f"{attack}_reaction_{horizon}_sum", 0.0)
                        / count if count else 0.0),
                    prefix + f"reaction_{horizon}_max_usd": totals.get(
                        f"{attack}_reaction_{horizon}_max", 0.0),
                    prefix + f"reaction_{horizon}_defense_rate": (
                        totals.get(
                            f"{attack}_reaction_{horizon}_defense_count", 0.0)
                        / count if count else 0.0),
                })
            values[prefix + "distance_ticks"] = float(
                side * (current_tick - center))
            values[prefix + "tick_value_usd"] = float(unit)
        return MappingProxyType(values)


def _simple_sha(value: object) -> str:
    import hashlib
    import json
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class _ProfileState:
    boundary_sec: int
    total_volume: int
    low_tick: int
    high_tick: int
    poc_tick: int
    val_tick: int
    vah_tick: int
    nearest_hvn_tick: int
    nearest_lvn_tick: int
    vwap_tick: float
    entropy: float
    poc_fraction: float
    skewness: float
    excess_kurtosis: float
    lower_tail_fraction: float
    upper_tail_fraction: float
    low_edge_fraction: float
    high_edge_fraction: float
    low_excess_score: float
    high_excess_score: float
    low_poor_score: float
    high_poor_score: float
    single_print_fraction: float
    low_single_tail_ticks: int
    high_single_tail_ticks: int
    mode_count: int
    delta_fraction: float
    absolute_delta_fraction: float
    poc_delta_fraction: float


@dataclass(frozen=True, slots=True)
class _TickLedger:
    seconds: np.ndarray
    cumulative: np.ndarray
    buy_burst_cumulative: np.ndarray
    sell_burst_cumulative: np.ndarray
    buy_seconds: np.ndarray
    sell_seconds: np.ndarray
    buy_second_volume: np.ndarray
    sell_second_volume: np.ndarray
    buy_ts_ns: np.ndarray
    sell_ts_ns: np.ndarray
    buy_event_size: np.ndarray
    sell_event_size: np.ndarray
    bid_reload_ts_ns: np.ndarray
    ask_reload_ts_ns: np.ndarray
    bid_reload_latency_ns: np.ndarray
    ask_reload_latency_ns: np.ndarray
    bid_reload_size: np.ndarray
    ask_reload_size: np.ndarray
    bid_pull_ts_ns: np.ndarray
    ask_pull_ts_ns: np.ndarray
    bid_pull_lifetime_ns: np.ndarray
    ask_pull_lifetime_ns: np.ndarray
    bid_pull_size: np.ndarray
    ask_pull_size: np.ndarray


_LEDGER_METRICS = (
    "trade_count", "trade_volume", "buy_volume", "sell_volume",
    "unsigned_volume", "bid_add_size", "ask_add_size",
    "bid_cancel_size", "ask_cancel_size", "bid_modify_size",
    "ask_modify_size", "bid_reload_count", "ask_reload_count",
    "bid_reload_size", "ask_reload_size", "bid_pull_no_fill",
    "ask_pull_no_fill",
)
_LEDGER_INDEX = MappingProxyType({
    name: index for index, name in enumerate(_LEDGER_METRICS)
})


def _value_area(smoothed: np.ndarray, poc: int) -> tuple[int, int]:
    total = float(smoothed.sum())
    if total <= 0:
        return poc, poc
    need = VALUE_AREA_FRACTION * total
    lo = hi = int(poc)
    accumulated = float(smoothed[poc])
    while accumulated < need and (lo > 0 or hi < len(smoothed) - 1):
        lower = float(smoothed[lo - 1]) if lo > 0 else -math.inf
        upper = (float(smoothed[hi + 1])
                 if hi < len(smoothed) - 1 else -math.inf)
        if lower > upper or (lower == upper and lo > 0):
            lo -= 1
            accumulated += lower
        else:
            hi += 1
            accumulated += upper
    return lo, hi


def _local_extrema(smoothed: np.ndarray, *, maxima: bool) -> np.ndarray:
    if len(smoothed) < 3:
        return np.empty(0, np.int64)
    values = smoothed if maxima else -smoothed
    selected = np.flatnonzero(
        (values[1:-1] > values[:-2]) & (values[1:-1] >= values[2:])) + 1
    return selected.astype(np.int64, copy=False)


def _profile_state(
    ticks: np.ndarray, sizes: np.ndarray, boundary_sec: int,
    reference_tick: int, signed_sizes: np.ndarray | None = None,
    *, tpo: bool = False,
) -> _ProfileState | None:
    if not len(ticks):
        return None
    low = int(ticks.min())
    high = int(ticks.max())
    raw = np.zeros(high - low + 5, np.int64)
    np.add.at(raw, ticks.astype(np.int64) - low + 2, sizes.astype(np.int64))
    smoothed = np.convolve(raw.astype(np.float64), PROFILE_KERNEL, mode="same")
    if not np.isclose(smoothed.sum(), raw.sum(), rtol=0.0, atol=1e-7):
        raise DiscretionaryFeatureRefusal("profile smoothing does not conserve volume")
    poc = int(np.argmax(smoothed))
    val, vah = _value_area(smoothed, poc)
    maxima = _local_extrema(smoothed, maxima=True)
    minima = _local_extrema(smoothed, maxima=False)
    ref_index = int(reference_tick) - low + 2
    nearest_hvn = (poc if not len(maxima)
                   else int(maxima[np.argmin(np.abs(maxima - ref_index))]))
    nearest_lvn = (poc if not len(minima)
                   else int(minima[np.argmin(np.abs(minima - ref_index))]))
    mass = smoothed / float(smoothed.sum())
    positive = mass[mass > 0]
    entropy = (-float(np.sum(positive * np.log(positive)))
               / max(1.0, math.log(float(len(positive)))))
    weights = sizes.astype(np.float64) / float(sizes.sum())
    mean_tick = float(np.dot(ticks.astype(np.float64), weights))
    centered = ticks.astype(np.float64) - mean_tick
    variance = float(np.dot(centered * centered, weights))
    if variance > 0.0:
        skewness = float(np.dot(centered ** 3, weights) / variance ** 1.5)
        excess_kurtosis = float(np.dot(centered ** 4, weights) / variance ** 2 - 3.0)
    else:
        skewness = excess_kurtosis = 0.0
    lower_tail = float(sizes[ticks < low - 2 + val].sum() / sizes.sum())
    upper_tail = float(sizes[ticks > low - 2 + vah].sum() / sizes.sum())
    low_edge = float(sizes[0] / sizes.sum())
    high_edge = float(sizes[-1] / sizes.sum())
    low_neighbor = float(np.mean(sizes[1:min(4, len(sizes))])) \
        if len(sizes) > 1 else float(sizes[0])
    high_neighbor = float(np.mean(sizes[max(0, len(sizes) - 4):-1])) \
        if len(sizes) > 1 else float(sizes[-1])
    low_ratio = float(sizes[0] / max(1.0, low_neighbor))
    high_ratio = float(sizes[-1] / max(1.0, high_neighbor))
    low_single = 0
    high_single = 0
    if tpo:
        for value in sizes:
            if int(value) != 1:
                break
            low_single += 1
        for value in sizes[::-1]:
            if int(value) != 1:
                break
            high_single += 1
    if signed_sizes is None:
        signed = np.zeros(len(sizes), np.float64)
    else:
        signed = np.asarray(signed_sizes, np.float64)
        if signed.shape != sizes.shape:
            raise DiscretionaryFeatureRefusal("profile delta does not align")
    poc_tick = low - 2 + poc
    poc_source = int(np.searchsorted(ticks, poc_tick, side="left"))
    poc_delta = (float(signed[poc_source] / max(1.0, sizes[poc_source]))
                 if poc_source < len(ticks) and int(ticks[poc_source]) == poc_tick
                 else 0.0)
    return _ProfileState(
        boundary_sec=int(boundary_sec), total_volume=int(raw.sum()),
        low_tick=low, high_tick=high, poc_tick=low - 2 + poc,
        val_tick=low - 2 + val, vah_tick=low - 2 + vah,
        nearest_hvn_tick=low - 2 + nearest_hvn,
        nearest_lvn_tick=low - 2 + nearest_lvn,
        vwap_tick=float(np.average(ticks, weights=sizes)),
        entropy=float(entropy),
        poc_fraction=float(smoothed[poc] / smoothed.sum()),
        skewness=skewness, excess_kurtosis=excess_kurtosis,
        lower_tail_fraction=lower_tail, upper_tail_fraction=upper_tail,
        low_edge_fraction=low_edge, high_edge_fraction=high_edge,
        low_excess_score=max(0.0, 1.0 - low_ratio),
        high_excess_score=max(0.0, 1.0 - high_ratio),
        low_poor_score=low_ratio, high_poor_score=high_ratio,
        single_print_fraction=float(np.mean(sizes == 1)) if tpo else 0.0,
        low_single_tail_ticks=low_single, high_single_tail_ticks=high_single,
        mode_count=int(len(maxima)),
        delta_fraction=float(signed.sum() / max(1.0, sizes.sum())),
        absolute_delta_fraction=float(
            np.abs(signed).sum() / max(1.0, sizes.sum())),
        poc_delta_fraction=poc_delta,
    )


class CausalDiscretionaryPlane:
    """Prefix-queryable auction, price-ledger, and confirmation state."""

    def __init__(
        self, *, rows: np.ndarray, truth: Mapping[str, np.ndarray],
        asset: str, open_ns: int, duration_sec: int, raw_tick: int,
        multiplier: int, event_state_flags: Mapping[str, np.ndarray],
        level_association_mode: str = "REAL",
        prior_session: PriorSessionContext | None = None,
    ) -> None:
        if level_association_mode not in LEVEL_ASSOCIATION_MODES:
            raise DiscretionaryFeatureRefusal("unknown level-association mode")
        self.rows = np.asarray(rows)
        self.asset = str(asset)
        self.open_ns = int(open_ns)
        self.duration = int(duration_sec)
        self.raw_tick = int(raw_tick)
        self.multiplier = int(multiplier)
        self.factor = 0.5e-9 * float(multiplier)
        self.level_association_mode = level_association_mode
        # Date ordering is checked by the caller, which owns the current
        # EventPack header; asset mismatch can be rejected locally.
        if (prior_session is not None
                and (prior_session.asset != self.asset
                     or prior_session.raw_tick != self.raw_tick
                     or prior_session.multiplier != self.multiplier)):
            raise DiscretionaryFeatureRefusal(
                "prior-session instrument identity differs")
        self.prior_session = prior_session
        self._profile_cache: dict[int, tuple[_ProfileState | None, ...]] = {}
        self._tpo_cache: dict[int, tuple[_ProfileState | None, ...]] = {}
        self._state_cache: dict[tuple[int, int, int], Mapping[str, np.ndarray]] = {}

        n = len(self.rows)
        required_truth = ("trusted_message", "trusted_economic", "mid2")
        if any(np.asarray(truth[name]).shape != (n,) for name in required_truth):
            raise DiscretionaryFeatureRefusal("truth columns do not align with events")
        for name in (
                "bid_reload", "ask_reload", "bid_pull_no_fill",
                "ask_pull_no_fill", "bid_reload_latency_ns",
                "ask_reload_latency_ns", "bid_pull_lifetime_ns",
                "ask_pull_lifetime_ns"):
            if np.asarray(event_state_flags[name]).shape != (n,):
                raise DiscretionaryFeatureRefusal("event-state flags do not align")

        self.message = np.asarray(truth["trusted_message"], bool)
        self.economic = np.asarray(truth["trusted_economic"], bool)
        self.mid2 = np.asarray(truth["mid2"], np.int64)
        self.second = self.rows["receive_session_sec"].astype(np.int64)
        if (n and (int(self.second.min()) < 0
                   or int(self.second.max()) >= self.duration)):
            raise DiscretionaryFeatureRefusal("event second is outside the session")

        self._last_mid = np.full(self.duration, -1, np.int64)
        econ_index = np.flatnonzero(self.economic)
        self._economic_ts = self.rows["ts_recv_ns"][econ_index].astype(np.int64)
        self._economic_mid2 = self.mid2[econ_index].astype(np.int64)
        self._economic_bid_tick = (
            self.rows["bid_px"][econ_index].astype(np.int64) // self.raw_tick)
        self._economic_ask_tick = (
            self.rows["ask_px"][econ_index].astype(np.int64) // self.raw_tick)
        self._economic_bid_size = self.rows["bid_sz"][econ_index].astype(np.int64)
        self._economic_ask_size = self.rows["ask_sz"][econ_index].astype(np.int64)
        self._economic_bid_count = self.rows["bid_ct"][econ_index].astype(np.int64)
        self._economic_ask_count = self.rows["ask_ct"][econ_index].astype(np.int64)
        price_change = (np.r_[True, self._economic_mid2[1:] != self._economic_mid2[:-1]]
                        if len(self._economic_mid2) else np.empty(0, bool))
        self._price_ts = self._economic_ts[price_change]
        self._price_mid2 = self._economic_mid2[price_change]
        if len(econ_index):
            last_index = np.full(self.duration, -1, np.int64)
            np.maximum.at(last_index, self.second[econ_index], econ_index)
            last_index = np.maximum.accumulate(last_index)
            present = last_index >= 0
            self._last_mid[present] = self.mid2[last_index[present]]

        action = self.rows["action"]
        side = self.rows["side"]
        price = self.rows["price"].astype(np.int64)
        size = self.rows["size"].astype(np.int64)

        # Exact trusted-message and trade clocks.  Wall-clock summaries make
        # a quiet tape and a bursty tape look alike; these arrays retain the
        # adaptive event/trade/volume-time state without retaining outcomes.
        message_index = np.flatnonzero(self.message)
        self._message_ts = self.rows["ts_recv_ns"][message_index].astype(np.int64)
        self._message_action = action[message_index].astype(np.uint8)
        self._message_side = side[message_index].astype(np.uint8)
        self._message_size = size[message_index].astype(np.int64)
        self._message_mid2 = self.mid2[message_index].astype(np.int64)
        self._message_economic = self.economic[message_index].astype(bool)
        for name in ("bid_px", "ask_px", "bid_sz", "ask_sz", "bid_ct", "ask_ct"):
            setattr(self, f"_message_{name}",
                    self.rows[name][message_index].astype(np.int64))

        self._second_clock: dict[str, np.ndarray] = {}
        message_second = self.second[message_index]
        message_trade = self._message_action == ord("T")
        message_buy = message_trade & (self._message_side == ord("B"))
        message_sell = message_trade & (self._message_side == ord("A"))
        clock_sources = {
            "event": np.ones(len(message_index), np.int64),
            "trade": message_trade.astype(np.int64),
            "volume": np.where(message_trade, self._message_size, 0),
            "signed_volume": np.where(
                message_buy, self._message_size,
                np.where(message_sell, -self._message_size, 0)),
            "quote_churn": np.where(np.isin(
                self._message_action, (ord("A"), ord("C"), ord("M"))),
                self._message_size, 0),
        }
        for name, source in clock_sources.items():
            aggregate = np.zeros(self.duration, np.int64)
            if len(source):
                np.add.at(aggregate, message_second, source)
            self._second_clock[name] = aggregate
        valid_price = ((price > 0) & (price % self.raw_tick == 0)
                       & self.message
                       & np.isin(action, (ord("A"), ord("C"), ord("M"), ord("T"))))
        event_index = np.flatnonzero(valid_price)
        ticks = (price[event_index] // self.raw_tick).astype(np.int64)
        if level_association_mode == "LEVEL_ASSOCIATION_DESTROYED":
            # Independent of observed data/future rows.  Keeping coordinates
            # inside 64-tick bands preserves realistic local density while
            # breaking exact candidate-level identity.  The odd shifts make
            # the affine permutation fixed-point free.
            ticks = np.asarray([
                _destroy_tick(int(tick), self.asset) for tick in ticks],
                np.int64)
        self._ledger = self._build_ledger(
            event_index, ticks, action, side, size, event_state_flags)

        trade = (action == ord("T")) & valid_price
        trade_index = np.flatnonzero(trade)
        self._trade_ts = self.rows["ts_recv_ns"][trade_index].astype(np.int64)
        self._trade_sign = np.where(
            side[trade_index] == ord("B"), 1,
            np.where(side[trade_index] == ord("A"), -1, 0)).astype(np.int8)
        self._trade_exact_ticks = (price[trade_index] // self.raw_tick).astype(np.int64)
        self._trade_exact_sizes = size[trade_index].astype(np.int64)
        self._trade_volume_prefix = np.r_[
            np.int64(0), np.cumsum(self._trade_exact_sizes, dtype=np.int64)]
        self._trade_seconds = self.second[trade]
        self._trade_ticks = (price[trade] // self.raw_tick).astype(np.int64)
        self._trade_sizes = size[trade]
        profile_sign = self._trade_sign.astype(np.int64, copy=True)
        order = np.argsort(self._trade_seconds, kind="stable")
        self._trade_seconds = self._trade_seconds[order]
        self._trade_ticks = self._trade_ticks[order]
        self._trade_sizes = self._trade_sizes[order]
        self._trade_profile_sign = profile_sign[order]
        self._profile_cache[0] = self._build_profile_series(0)
        self._tpo_cache[0] = self._build_tpo_series(0)

    def _build_ledger(
        self, event_index: np.ndarray, ticks: np.ndarray, action: np.ndarray,
        side: np.ndarray, size: np.ndarray,
        flags: Mapping[str, np.ndarray],
    ) -> Mapping[int, _TickLedger]:
        if not len(event_index):
            return MappingProxyType({})
        raw_ts = self.rows["ts_recv_ns"].astype(np.int64)
        coupling_ts: dict[str, np.ndarray] = {}
        coupling_aux: dict[str, np.ndarray] = {}
        for flag_name, aux_name in (
                ("bid_reload", "bid_reload_latency_ns"),
                ("ask_reload", "ask_reload_latency_ns"),
                ("bid_pull_no_fill", "bid_pull_lifetime_ns"),
                ("ask_pull_no_fill", "ask_pull_lifetime_ns")):
            mapped_ts = raw_ts.copy()
            mapped_aux = np.asarray(flags[aux_name], np.int64).copy()
            positions = np.flatnonzero(np.asarray(flags[flag_name], bool))
            if (self.level_association_mode == "FILL_COUPLING_DESTROYED"
                    and len(positions) > 1):
                # Re-pair each same-side reload/pull record with another
                # record's time and latency/lifetime.  Flags remain on their
                # original event, price and size, so every count/size/price
                # marginal remains exact while attack-response timing is lost.
                donors = np.roll(positions, 1)
                mapped_ts[positions] = raw_ts[donors]
                mapped_aux[positions] = np.asarray(
                    flags[aux_name], np.int64)[donors]
            coupling_ts[flag_name] = mapped_ts
            coupling_aux[flag_name] = mapped_aux
        seconds = self.second[event_index]
        # Price is the primary key and original event ordinal the secondary
        # key.  The latter preserves the authoritative nanosecond event order
        # within each price, including same-second sequences.
        order = np.lexsort((event_index, ticks))
        idx = event_index[order]
        ordered_ticks = ticks[order]
        ordered_seconds = seconds[order]
        starts = np.r_[0, np.flatnonzero(
            (ordered_ticks[1:] != ordered_ticks[:-1])
            | (ordered_seconds[1:] != ordered_seconds[:-1])) + 1]
        stops = np.r_[starts[1:], len(idx)]
        group_ticks = ordered_ticks[starts]
        group_seconds = ordered_seconds[starts]

        a = action[idx]
        s = side[idx]
        z = size[idx]
        is_trade = a == ord("T")
        buy = is_trade & (s == ord("B"))
        sell = is_trade & (s == ord("A"))
        unsigned = is_trade & ~(buy | sell)
        sources = (
            is_trade.astype(np.int64), np.where(is_trade, z, 0),
            np.where(buy, z, 0), np.where(sell, z, 0),
            np.where(unsigned, z, 0),
            np.where((a == ord("A")) & (s == ord("B")), z, 0),
            np.where((a == ord("A")) & (s == ord("A")), z, 0),
            np.where((a == ord("C")) & (s == ord("B")), z, 0),
            np.where((a == ord("C")) & (s == ord("A")), z, 0),
            np.where((a == ord("M")) & (s == ord("B")), z, 0),
            np.where((a == ord("M")) & (s == ord("A")), z, 0),
            np.asarray(flags["bid_reload"], np.int64)[idx],
            np.asarray(flags["ask_reload"], np.int64)[idx],
            np.asarray(flags["bid_reload"], np.int64)[idx] * z,
            np.asarray(flags["ask_reload"], np.int64)[idx] * z,
            np.asarray(flags["bid_pull_no_fill"], np.int64)[idx],
            np.asarray(flags["ask_pull_no_fill"], np.int64)[idx],
        )
        grouped = np.column_stack([
            np.add.reduceat(source, starts) for source in sources
        ]).astype(np.int64, copy=False)
        if np.any(np.sum(grouped, axis=0) != np.asarray([
                int(source.sum(dtype=np.int64)) for source in sources])):
            raise DiscretionaryFeatureRefusal("price ledger does not conserve metrics")

        output: dict[int, _TickLedger] = {}
        tick_starts = np.r_[0, np.flatnonzero(group_ticks[1:] != group_ticks[:-1]) + 1]
        tick_stops = np.r_[tick_starts[1:], len(group_ticks)]
        event_tick_starts = np.r_[
            0, np.flatnonzero(ordered_ticks[1:] != ordered_ticks[:-1]) + 1]
        event_tick_stops = np.r_[event_tick_starts[1:], len(ordered_ticks)]
        event_bounds = {
            int(ordered_ticks[left]): (int(left), int(right))
            for left, right in zip(event_tick_starts, event_tick_stops)
        }
        buy_index = _LEDGER_INDEX["buy_volume"]
        sell_index = _LEDGER_INDEX["sell_volume"]
        for left, right in zip(tick_starts, tick_stops):
            tick_value = int(group_ticks[left])
            local_seconds = group_seconds[left:right].astype(np.int64, copy=False)
            local = grouped[left:right]
            buy_present = local[:, buy_index] > 0
            sell_present = local[:, sell_index] > 0
            buy_burst = np.zeros(len(local), bool)
            sell_burst = np.zeros(len(local), bool)
            buy_rows = np.flatnonzero(buy_present)
            sell_rows = np.flatnonzero(sell_present)
            if len(buy_rows):
                buy_burst[buy_rows] = np.r_[
                    True, np.diff(local_seconds[buy_rows]) > 5]
            if len(sell_rows):
                sell_burst[sell_rows] = np.r_[
                    True, np.diff(local_seconds[sell_rows]) > 5]
            event_left, event_right = event_bounds[tick_value]
            event_rows = idx[event_left:event_right]
            event_action = action[event_rows]
            event_side = side[event_rows]
            event_size = size[event_rows]
            event_ts = self.rows["ts_recv_ns"][event_rows].astype(np.int64)
            event_buy = (event_action == ord("T")) & (event_side == ord("B"))
            event_sell = (event_action == ord("T")) & (event_side == ord("A"))
            bid_reload = np.asarray(flags["bid_reload"], bool)[event_rows]
            ask_reload = np.asarray(flags["ask_reload"], bool)[event_rows]
            bid_pull = np.asarray(flags["bid_pull_no_fill"], bool)[event_rows]
            ask_pull = np.asarray(flags["ask_pull_no_fill"], bool)[event_rows]
            def coupled(
                flag_name: str, mask: np.ndarray,
            ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
                timestamps = coupling_ts[flag_name][event_rows][mask]
                auxiliary = coupling_aux[flag_name][event_rows][mask]
                event_sizes = event_size[mask].astype(np.int64, copy=False)
                order = np.argsort(timestamps, kind="stable")
                return (timestamps[order], auxiliary[order], event_sizes[order])
            bid_reload_ts, bid_reload_latency, bid_reload_sizes = coupled(
                "bid_reload", bid_reload)
            ask_reload_ts, ask_reload_latency, ask_reload_sizes = coupled(
                "ask_reload", ask_reload)
            bid_pull_ts, bid_pull_lifetime, bid_pull_sizes = coupled(
                "bid_pull_no_fill", bid_pull)
            ask_pull_ts, ask_pull_lifetime, ask_pull_sizes = coupled(
                "ask_pull_no_fill", ask_pull)
            output[tick_value] = _TickLedger(
                seconds=local_seconds,
                cumulative=np.vstack((
                    np.zeros((1, len(_LEDGER_METRICS)), np.int64),
                    np.cumsum(local, axis=0, dtype=np.int64),
                )),
                buy_burst_cumulative=np.r_[0, np.cumsum(buy_burst, dtype=np.int64)],
                sell_burst_cumulative=np.r_[0, np.cumsum(sell_burst, dtype=np.int64)],
                buy_seconds=local_seconds[buy_present],
                sell_seconds=local_seconds[sell_present],
                buy_second_volume=local[buy_present, buy_index],
                sell_second_volume=local[sell_present, sell_index],
                buy_ts_ns=event_ts[event_buy],
                sell_ts_ns=event_ts[event_sell],
                buy_event_size=event_size[event_buy].astype(np.int64, copy=False),
                sell_event_size=event_size[event_sell].astype(np.int64, copy=False),
                bid_reload_ts_ns=bid_reload_ts,
                ask_reload_ts_ns=ask_reload_ts,
                bid_reload_latency_ns=bid_reload_latency,
                ask_reload_latency_ns=ask_reload_latency,
                bid_reload_size=bid_reload_sizes,
                ask_reload_size=ask_reload_sizes,
                bid_pull_ts_ns=bid_pull_ts,
                ask_pull_ts_ns=ask_pull_ts,
                bid_pull_lifetime_ns=bid_pull_lifetime,
                ask_pull_lifetime_ns=ask_pull_lifetime,
                bid_pull_size=bid_pull_sizes,
                ask_pull_size=ask_pull_sizes,
            )
        return MappingProxyType(output)

    def _build_profile_series(self, start_sec: int) -> tuple[_ProfileState | None, ...]:
        start = max(0, int(start_sec))
        boundaries = range(start + PROFILE_INTERVAL_SEC,
                           self.duration + 1, PROFILE_INTERVAL_SEC)
        output: list[_ProfileState | None] = []
        cursor = int(np.searchsorted(self._trade_seconds, start, side="left"))
        histogram: dict[int, int] = {}
        signed_histogram: dict[int, int] = {}
        for boundary in boundaries:
            trade_right = int(np.searchsorted(
                self._trade_seconds, boundary, side="left"))
            new_ticks = self._trade_ticks[cursor:trade_right]
            new_sizes = self._trade_sizes[cursor:trade_right]
            new_signed = (self._trade_profile_sign[cursor:trade_right]
                          * new_sizes.astype(np.int64))
            if len(new_ticks):
                unique, inverse = np.unique(new_ticks, return_inverse=True)
                totals = np.zeros(len(unique), np.int64)
                signed_totals = np.zeros(len(unique), np.int64)
                np.add.at(totals, inverse, new_sizes)
                np.add.at(signed_totals, inverse, new_signed)
                for tick, volume, signed_volume in zip(
                        unique, totals, signed_totals):
                    histogram[int(tick)] = histogram.get(int(tick), 0) + int(volume)
                    signed_histogram[int(tick)] = (
                        signed_histogram.get(int(tick), 0) + int(signed_volume))
            cursor = trade_right
            if histogram:
                ticks = np.fromiter(sorted(histogram), dtype=np.int64)
                sizes = np.asarray([histogram[int(tick)] for tick in ticks], np.int64)
                signed_sizes = np.asarray(
                    [signed_histogram[int(tick)] for tick in ticks], np.int64)
                reference = (int(self._trade_ticks[trade_right - 1])
                             if trade_right > 0 else int(ticks[-1]))
                output.append(_profile_state(
                    ticks, sizes, boundary, reference, signed_sizes))
            else:
                output.append(None)
        return tuple(output)

    def _profile_at(self, start_sec: int, snapshot_sec: int) -> tuple[
            _ProfileState | None, int]:
        start = max(0, int(start_sec))
        if start not in self._profile_cache:
            self._profile_cache[start] = self._build_profile_series(start)
        ordinal = (int(snapshot_sec) - start) // PROFILE_INTERVAL_SEC - 1
        series = self._profile_cache[start]
        if ordinal < 0 or ordinal >= len(series):
            return None, ordinal
        return series[ordinal], ordinal

    def _build_tpo_series(self, start_sec: int) -> tuple[_ProfileState | None, ...]:
        start = max(0, int(start_sec))
        boundaries = range(start + PROFILE_INTERVAL_SEC,
                           self.duration + 1, PROFILE_INTERVAL_SEC)
        histogram: dict[int, int] = {}
        cursor = start
        output: list[_ProfileState | None] = []
        for boundary in boundaries:
            mids = self._last_mid[cursor:boundary]
            mids = mids[mids > 0]
            if len(mids):
                ticks = np.rint(
                    mids.astype(np.float64) / (2.0 * self.raw_tick)).astype(np.int64)
                unique, counts = np.unique(ticks, return_counts=True)
                for tick, count in zip(unique, counts):
                    histogram[int(tick)] = histogram.get(int(tick), 0) + int(count)
            cursor = boundary
            if histogram:
                ticks = np.fromiter(sorted(histogram), dtype=np.int64)
                counts = np.asarray([histogram[int(tick)] for tick in ticks], np.int64)
                reference = int(np.rint(
                    self._last_mid[boundary - 1] / (2.0 * self.raw_tick)))
                output.append(_profile_state(
                    ticks, counts, boundary, reference, tpo=True))
            else:
                output.append(None)
        return tuple(output)

    def _tpo_at(self, start_sec: int, snapshot_sec: int) -> _ProfileState | None:
        start = max(0, int(start_sec))
        if start not in self._tpo_cache:
            self._tpo_cache[start] = self._build_tpo_series(start)
        ordinal = (int(snapshot_sec) - start) // PROFILE_INTERVAL_SEC - 1
        series = self._tpo_cache[start]
        return None if ordinal < 0 or ordinal >= len(series) else series[ordinal]

    def _profile_map(
        self, *, prefix: str, start_sec: int, snapshot_sec: int,
        current_mid2: int, side: int,
    ) -> dict[str, float]:
        state, ordinal = self._profile_at(start_sec, snapshot_sec)
        zeros = (
            "age_sec", "poc_aligned_usd", "val_aligned_usd",
            "vah_aligned_usd", "value_width_usd", "inside_value",
            "range_position", "poc_migration_5m_aligned_usd",
            "poc_migration_15m_aligned_usd", "poc_migration_30m_aligned_usd",
            "nearest_hvn_aligned_usd", "nearest_lvn_aligned_usd",
            "entropy", "poc_volume_fraction", "above_value_time_fraction",
            "below_value_time_fraction", "outside_value_time_fraction",
            "vwap_aligned_usd", "tpo_present", "tpo_poc_aligned_usd",
            "tpo_value_width_usd", "vp_tpo_poc_disagreement_usd",
            "vp_tpo_value_overlap_fraction",
            "profile_skewness", "profile_excess_kurtosis",
            "directional_profile_skewness",
            "lower_tail_mass_fraction", "upper_tail_mass_fraction",
            "low_edge_fraction", "high_edge_fraction",
            "low_excess_score", "high_excess_score",
            "low_poor_score", "high_poor_score", "mode_count",
            "delta_fraction", "absolute_delta_fraction",
            "poc_delta_fraction", "directional_delta_fraction",
            "directional_escape_time_fraction",
            "opposing_escape_time_fraction", "directional_escape_age_sec",
            "directional_escape_current_run_sec",
            "directional_escape_max_run_sec", "directional_escape_episodes",
            "directional_escape_reentry_seen", "failed_directional_auction",
            "directional_acceptance_score", "tpo_single_print_fraction",
            "tpo_low_single_tail_ticks", "tpo_high_single_tail_ticks",
            "tpo_low_excess_score", "tpo_high_excess_score",
            "tpo_low_poor_score", "tpo_high_poor_score",
        )
        # Initialize the complete schema before branching.  Updating values
        # later does not change insertion order, so absent and present profile
        # states are byte-for-byte schema compatible.
        values: dict[str, float] = {prefix + "present": float(state is not None)}
        values.update({prefix + name: 0.0 for name in zeros})
        if state is None:
            return values
        def distance(tick: int) -> float:
            return side * (int(current_mid2) - 2 * tick * self.raw_tick) * self.factor
        current_tick = float(current_mid2) / (2.0 * self.raw_tick)
        width = max(1, state.high_tick - state.low_tick)
        values.update({
            prefix + "age_sec": float(snapshot_sec - state.boundary_sec),
            prefix + "poc_aligned_usd": distance(state.poc_tick),
            prefix + "val_aligned_usd": distance(state.val_tick),
            prefix + "vah_aligned_usd": distance(state.vah_tick),
            prefix + "value_width_usd": ((state.vah_tick - state.val_tick)
                                          * self.raw_tick * 1e-9 * self.multiplier),
            prefix + "inside_value": float(
                state.val_tick <= current_tick <= state.vah_tick),
            prefix + "range_position": float(np.clip(
                (current_tick - state.low_tick) / width, 0.0, 1.0)),
            prefix + "nearest_hvn_aligned_usd": distance(state.nearest_hvn_tick),
            prefix + "nearest_lvn_aligned_usd": distance(state.nearest_lvn_tick),
            prefix + "vwap_aligned_usd": float(
                side * (int(current_mid2) - 2.0 * state.vwap_tick * self.raw_tick)
                * self.factor),
            prefix + "entropy": state.entropy,
            prefix + "poc_volume_fraction": state.poc_fraction,
            prefix + "profile_skewness": state.skewness,
            prefix + "directional_profile_skewness": side * state.skewness,
            prefix + "profile_excess_kurtosis": state.excess_kurtosis,
            prefix + "lower_tail_mass_fraction": state.lower_tail_fraction,
            prefix + "upper_tail_mass_fraction": state.upper_tail_fraction,
            prefix + "low_edge_fraction": state.low_edge_fraction,
            prefix + "high_edge_fraction": state.high_edge_fraction,
            prefix + "low_excess_score": state.low_excess_score,
            prefix + "high_excess_score": state.high_excess_score,
            prefix + "low_poor_score": state.low_poor_score,
            prefix + "high_poor_score": state.high_poor_score,
            prefix + "mode_count": float(state.mode_count),
            prefix + "delta_fraction": state.delta_fraction,
            prefix + "absolute_delta_fraction": state.absolute_delta_fraction,
            prefix + "poc_delta_fraction": state.poc_delta_fraction,
            prefix + "directional_delta_fraction": side * state.delta_fraction,
        })
        series = self._profile_cache[max(0, int(start_sec))]
        for steps, label in ((1, "5m"), (3, "15m"), (6, "30m")):
            previous = ordinal - steps
            migration = 0.0
            if previous >= 0 and series[previous] is not None:
                migration = (side * (state.poc_tick - series[previous].poc_tick)
                             * self.raw_tick * 1e-9 * self.multiplier)
            values[prefix + f"poc_migration_{label}_aligned_usd"] = float(migration)
        left = max(state.boundary_sec, 0)
        mids = self._last_mid[left:snapshot_sec]
        mids = mids[mids > 0]
        if len(mids):
            low2 = 2 * state.val_tick * self.raw_tick
            high2 = 2 * state.vah_tick * self.raw_tick
            above = float(np.mean(mids > high2))
            below = float(np.mean(mids < low2))
            directional = mids > high2 if side > 0 else mids < low2
            opposing = mids < low2 if side > 0 else mids > high2
            inside = ~(directional | opposing)
            directional_rows = np.flatnonzero(directional)
            current_run = 0
            for present in directional[::-1]:
                if not present:
                    break
                current_run += 1
            best = run = episodes = 0
            previous = False
            for present in directional:
                if present:
                    run += 1
                    if not previous:
                        episodes += 1
                    best = max(best, run)
                else:
                    run = 0
                previous = bool(present)
            reentry = bool(len(directional_rows)
                           and np.any(inside[directional_rows[0] + 1:]))
            escape_age = (float(len(mids) - 1 - directional_rows[0])
                          if len(directional_rows) else 0.0)
            values.update({
                prefix + "directional_escape_time_fraction": float(
                    np.mean(directional)),
                prefix + "opposing_escape_time_fraction": float(np.mean(opposing)),
                prefix + "directional_escape_age_sec": escape_age,
                prefix + "directional_escape_current_run_sec": float(current_run),
                prefix + "directional_escape_max_run_sec": float(best),
                prefix + "directional_escape_episodes": float(episodes),
                prefix + "directional_escape_reentry_seen": float(reentry),
                prefix + "failed_directional_auction": float(
                    reentry and not directional[-1]),
                prefix + "directional_acceptance_score": float(
                    np.mean(directional) * min(1.0, current_run / 30.0)),
            })
        else:
            above = below = 0.0
        values[prefix + "above_value_time_fraction"] = above
        values[prefix + "below_value_time_fraction"] = below
        values[prefix + "outside_value_time_fraction"] = above + below
        tpo = self._tpo_at(start_sec, snapshot_sec)
        if tpo is not None:
            intersection = max(0, min(state.vah_tick, tpo.vah_tick)
                               - max(state.val_tick, tpo.val_tick) + 1)
            union = max(state.vah_tick, tpo.vah_tick) - min(
                state.val_tick, tpo.val_tick) + 1
            values.update({
                prefix + "tpo_present": 1.0,
                prefix + "tpo_poc_aligned_usd": distance(tpo.poc_tick),
                prefix + "tpo_value_width_usd": (
                    (tpo.vah_tick - tpo.val_tick) * self.raw_tick
                    * 1e-9 * self.multiplier),
                prefix + "vp_tpo_poc_disagreement_usd": (
                    abs(state.poc_tick - tpo.poc_tick) * self.raw_tick
                    * 1e-9 * self.multiplier),
                prefix + "vp_tpo_value_overlap_fraction": float(
                    intersection / union if union else 0.0),
                prefix + "tpo_single_print_fraction": tpo.single_print_fraction,
                prefix + "tpo_low_single_tail_ticks": float(
                    tpo.low_single_tail_ticks),
                prefix + "tpo_high_single_tail_ticks": float(
                    tpo.high_single_tail_ticks),
                prefix + "tpo_low_excess_score": tpo.low_excess_score,
                prefix + "tpo_high_excess_score": tpo.high_excess_score,
                prefix + "tpo_low_poor_score": tpo.low_poor_score,
                prefix + "tpo_high_poor_score": tpo.high_poor_score,
            })
        return values

    def _initial_balance_map(
        self, *, prefix: str, start_sec: int, snapshot_sec: int,
        current_mid2: int, side: int,
    ) -> dict[str, float]:
        start = max(0, int(start_sec))
        ib_end = min(self.duration, start + 3_600)
        right = min(int(snapshot_sec), ib_end)
        mids = self._last_mid[start:right]
        mids = mids[mids > 0]
        if not len(mids):
            return {
                prefix + "present": 0.0,
                prefix + "support_fraction": 0.0,
                prefix + "complete": 0.0,
                prefix + "range_usd": 0.0,
                prefix + "midpoint_aligned_usd": 0.0,
                prefix + "high_aligned_usd": 0.0,
                prefix + "low_aligned_usd": 0.0,
                prefix + "inside": 0.0,
                prefix + "directional_extension_usd": 0.0,
                prefix + "opposing_extension_usd": 0.0,
                prefix + "directional_extension_over_range": 0.0,
                prefix + "opposing_extension_over_range": 0.0,
                prefix + "directional_break_seen": 0.0,
                prefix + "opposing_break_seen": 0.0,
                prefix + "directional_break_age_sec": 0.0,
                prefix + "directional_break_reentry_seen": 0.0,
            }
        low = int(mids.min())
        high = int(mids.max())
        midpoint = .5 * (low + high)
        range_usd = float((high - low) * self.factor)
        post = self._last_mid[ib_end:snapshot_sec] if snapshot_sec > ib_end else np.empty(0, np.int64)
        post = post[post > 0]
        directional_path = (side * (post - (high if side > 0 else low))
                            * self.factor) if len(post) else np.empty(0, np.float64)
        opposing_path = (-side * (post - (low if side > 0 else high))
                         * self.factor) if len(post) else np.empty(0, np.float64)
        directional_rows = np.flatnonzero(directional_path > 0)
        directional_reentry = bool(
            len(directional_rows)
            and np.any(directional_path[directional_rows[0] + 1:] <= 0))
        current = int(current_mid2)
        return {
            prefix + "present": 1.0,
            prefix + "support_fraction": float(max(0, right - start) / 3_600.0),
            prefix + "complete": float(snapshot_sec >= ib_end),
            prefix + "range_usd": range_usd,
            prefix + "midpoint_aligned_usd": float(
                side * (current - midpoint) * self.factor),
            prefix + "high_aligned_usd": float(side * (current - high) * self.factor),
            prefix + "low_aligned_usd": float(side * (current - low) * self.factor),
            prefix + "inside": float(low <= current <= high),
            prefix + "directional_extension_usd": float(
                max(0.0, side * (current - (high if side > 0 else low)) * self.factor)),
            prefix + "opposing_extension_usd": float(
                max(0.0, -side * (current - (low if side > 0 else high)) * self.factor)),
            prefix + "directional_extension_over_range": float(
                max(0.0, side * (current - (high if side > 0 else low)) * self.factor)
                / range_usd if range_usd > 0 else 0.0),
            prefix + "opposing_extension_over_range": float(
                max(0.0, -side * (current - (low if side > 0 else high)) * self.factor)
                / range_usd if range_usd > 0 else 0.0),
            prefix + "directional_break_seen": float(len(directional_rows) > 0),
            prefix + "opposing_break_seen": float(np.any(opposing_path > 0)),
            prefix + "directional_break_age_sec": float(
                len(post) - 1 - directional_rows[0] if len(directional_rows) else 0.0),
            prefix + "directional_break_reentry_seen": float(directional_reentry),
        }

    def _ledger_sum(
        self, *, center_tick: int, radius: int, left_sec: int, right_sec: int,
    ) -> tuple[np.ndarray, int, int, int, int, int, int]:
        totals = np.zeros(len(_LEDGER_METRICS), np.int64)
        buy_bursts = sell_bursts = 0
        last_buy = last_sell = -1
        max_buy = max_sell = 0
        for tick in range(int(center_tick) - radius, int(center_tick) + radius + 1):
            ledger = self._ledger.get(tick)
            if ledger is None:
                continue
            left = int(np.searchsorted(ledger.seconds, left_sec, side="left"))
            right = int(np.searchsorted(ledger.seconds, right_sec, side="left"))
            totals += ledger.cumulative[right] - ledger.cumulative[left]
            buy_bursts += int(ledger.buy_burst_cumulative[right]
                              - ledger.buy_burst_cumulative[left])
            sell_bursts += int(ledger.sell_burst_cumulative[right]
                               - ledger.sell_burst_cumulative[left])
            buy_left = int(np.searchsorted(ledger.buy_seconds, left_sec, side="left"))
            buy_right = int(np.searchsorted(ledger.buy_seconds, right_sec, side="left"))
            sell_left = int(np.searchsorted(ledger.sell_seconds, left_sec, side="left"))
            sell_right = int(np.searchsorted(ledger.sell_seconds, right_sec, side="left"))
            if buy_right > buy_left:
                last_buy = max(last_buy, int(ledger.buy_seconds[buy_right - 1]))
                max_buy = max(max_buy, int(np.max(
                    ledger.buy_second_volume[buy_left:buy_right])))
            if sell_right > sell_left:
                last_sell = max(last_sell, int(ledger.sell_seconds[sell_right - 1]))
                max_sell = max(max_sell, int(np.max(
                    ledger.sell_second_volume[sell_left:sell_right])))
        return (totals, buy_bursts, sell_bursts, last_buy, last_sell,
                max_buy, max_sell)

    def _level_values(
        self, *, prefix: str, center_tick: int, radius: int,
        left_sec: int, right_sec: int, side: int, age_reference_sec: int,
    ) -> dict[str, float]:
        (total, buy_bursts, sell_bursts, last_buy, last_sell,
         max_buy, max_sell) = self._ledger_sum(
            center_tick=center_tick, radius=radius,
            left_sec=left_sec, right_sec=right_sec)
        attack_name = "sell_volume" if side > 0 else "buy_volume"
        lift_name = "buy_volume" if side > 0 else "sell_volume"
        reload_name = "bid_reload" if side > 0 else "ask_reload"
        pull_name = "bid_pull_no_fill" if side > 0 else "ask_pull_no_fill"
        display_side = "bid" if side > 0 else "ask"
        attack = int(total[_LEDGER_INDEX[attack_name]])
        lift = int(total[_LEDGER_INDEX[lift_name]])
        trade = int(total[_LEDGER_INDEX["trade_volume"]])
        last_attack = last_sell if side > 0 else last_buy
        attack_bursts = sell_bursts if side > 0 else buy_bursts
        lift_bursts = buy_bursts if side > 0 else sell_bursts
        max_attack = max_sell if side > 0 else max_buy
        max_lift = max_buy if side > 0 else max_sell
        display = (int(total[_LEDGER_INDEX[f"{display_side}_add_size"]])
                   + int(total[_LEDGER_INDEX[f"{display_side}_modify_size"]])
                   - int(total[_LEDGER_INDEX[f"{display_side}_cancel_size"]]))
        return {
            prefix + "trade_volume": float(trade),
            prefix + "attack_volume": float(attack),
            prefix + "lift_volume": float(lift),
            prefix + "attack_fraction": float(attack / trade if trade else 0.0),
            prefix + "signed_control_fraction": float(
                (lift - attack) / trade if trade else 0.0),
            prefix + "attack_bursts": float(attack_bursts),
            prefix + "lift_bursts": float(lift_bursts),
            prefix + "max_attack_second_volume": float(max_attack),
            prefix + "max_lift_second_volume": float(max_lift),
            prefix + "defense_reload_count": float(
                total[_LEDGER_INDEX[f"{reload_name}_count"]]),
            prefix + "defense_reload_size": float(
                total[_LEDGER_INDEX[f"{reload_name}_size"]]),
            prefix + "defense_pull_no_fill": float(
                total[_LEDGER_INDEX[pull_name]]),
            prefix + "net_defense_display": float(display),
            prefix + "last_attack_age_sec": float(
                age_reference_sec - last_attack if last_attack >= 0 else 0.0),
            prefix + "last_attack_present": float(last_attack >= 0),
        }

    def _price_shape_values(
        self, *, prefix: str, center_tick: int, radius: int,
        left_sec: int, right_sec: int, side: int,
    ) -> dict[str, float]:
        ticks = np.arange(center_tick - radius, center_tick + radius + 1)
        buy = np.zeros(len(ticks), np.float64)
        sell = np.zeros(len(ticks), np.float64)
        reload = np.zeros(len(ticks), np.float64)
        for index, tick in enumerate(ticks):
            total, *_rest = self._ledger_sum(
                center_tick=int(tick), radius=0,
                left_sec=left_sec, right_sec=right_sec)
            buy[index] = total[_LEDGER_INDEX["buy_volume"]]
            sell[index] = total[_LEDGER_INDEX["sell_volume"]]
            reload[index] = total[_LEDGER_INDEX[
                "bid_reload_count" if side > 0 else "ask_reload_count"]]
        # Footprint diagonal: buy at p versus sell one tick below, and sell at
        # p versus buy one tick above.  Expose both directions and let context
        # decide whether dominance is continuation or trapped aggression.
        buy_diag = buy[1:] / np.maximum(1.0, sell[:-1])
        sell_diag = sell[:-1] / np.maximum(1.0, buy[1:])
        lift_mask = (buy_diag >= 3.5) if side > 0 else (sell_diag >= 3.5)
        attack_mask = (sell_diag >= 3.5) if side > 0 else (buy_diag >= 3.5)
        def max_run(mask: np.ndarray) -> int:
            best = current = 0
            for value in mask:
                current = current + 1 if value else 0
                best = max(best, current)
            return best
        total_reload = float(reload.sum())
        centroid = (0.0 if not total_reload else
                    float(np.sum((ticks - center_tick) * reload) / total_reload))
        return {
            prefix + "lift_diagonal_350_levels": float(lift_mask.sum()),
            prefix + "attack_diagonal_350_levels": float(attack_mask.sum()),
            prefix + "lift_diagonal_350_max_stack": float(max_run(lift_mask)),
            prefix + "attack_diagonal_350_max_stack": float(max_run(attack_mask)),
            prefix + "defense_reload_centroid_aligned_ticks": float(side * centroid),
            prefix + "two_sided_active_levels": float(np.sum((buy > 0) & (sell > 0))),
        }

    @staticmethod
    def _time_slice(
        timestamps: np.ndarray, values: np.ndarray,
        left_ns: int, right_ns: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        left = int(np.searchsorted(timestamps, left_ns, side="left"))
        right = int(np.searchsorted(timestamps, right_ns, side="left"))
        return timestamps[left:right], values[left:right]

    @staticmethod
    def _peak_count(timestamps: np.ndarray, width_ns: int) -> int:
        left = best = 0
        for right in range(len(timestamps)):
            while timestamps[right] - timestamps[left] >= width_ns:
                left += 1
            best = max(best, right - left + 1)
        return best

    @staticmethod
    def _slope(values: np.ndarray) -> float:
        array = np.asarray(values, np.float64)
        if len(array) < 2:
            return 0.0
        x = np.arange(len(array), dtype=np.float64)
        centered = x - float(x.mean())
        denominator = float(np.dot(centered, centered))
        return float(np.dot(centered, array - array.mean()) / denominator
                     if denominator > 0.0 else 0.0)

    def _best_quote_window_map(
        self, *, prefix: str, formation_tick: int, left_ns: int,
        right_ns: int, side: int,
    ) -> dict[str, float]:
        """Duration-aware BBO defense, depletion and rebuild state.

        The economic BBO is a piecewise-constant state, so a fast burst of
        updates must not receive the same weight as a queue that persists for
        seconds.  The state immediately before ``left_ns`` is carried into the
        window and every interval is clipped at the exclusive decision time.
        """

        names = (
            "present", "support_fraction", "update_count",
            "defense_at_formation_time_fraction",
            "defense_inside_z1_time_fraction",
            "opposing_at_formation_time_fraction",
            "defense_best_aligned_ticks_mean",
            "defense_best_aligned_ticks_current",
            "defense_best_favorable_change_count",
            "defense_best_adverse_change_count",
            "defense_best_change_count", "defense_best_current_dwell_sec",
            "defense_best_max_dwell_sec", "defense_size_time_mean",
            "defense_size_current", "defense_size_min", "defense_size_max",
            "defense_size_slope_per_sec", "defense_count_time_mean",
            "defense_count_current", "defense_average_order_size_time_mean",
            "defense_average_order_size_current",
            "defense_fragmentation_time_mean", "depletion_count",
            "depletion_size", "depletion_rate_per_sec", "rebuild_count",
            "rebuild_size", "rebuild_rate_per_sec",
            "rebuild_after_depletion_count",
            "rebuild_after_depletion_mean_latency_ms",
            "rebuild_after_depletion_max_latency_ms",
            "peak_to_min_drawdown_fraction", "current_from_peak_fraction",
            "formation_level_disappearance_count",
        )
        output = {prefix + name: 0.0 for name in names}
        left_ns = max(int(left_ns), int(self.open_ns))
        right_ns = int(right_ns)
        if right_ns <= left_ns or not len(self._economic_ts):
            return output
        first = max(0, int(np.searchsorted(
            self._economic_ts, left_ns, side="left")) - 1)
        stop = int(np.searchsorted(self._economic_ts, right_ns, side="left"))
        if first >= stop:
            return output
        ts = self._economic_ts[first:stop]
        starts = np.maximum(ts, left_ns)
        ends = np.minimum(np.r_[ts[1:], right_ns], right_ns)
        durations = np.maximum(0, ends - starts).astype(np.float64) / 1e9
        keep = durations > 0.0
        if not np.any(keep):
            return output
        ts = ts[keep]; starts = starts[keep]; durations = durations[keep]
        if side > 0:
            defense_tick = self._economic_bid_tick[first:stop][keep].copy()
            opposing_tick = self._economic_ask_tick[first:stop][keep].copy()
            defense_size = self._economic_bid_size[first:stop][keep].astype(np.float64)
            defense_count = self._economic_bid_count[first:stop][keep].astype(np.float64)
        else:
            defense_tick = self._economic_ask_tick[first:stop][keep].copy()
            opposing_tick = self._economic_bid_tick[first:stop][keep].copy()
            defense_size = self._economic_ask_size[first:stop][keep].astype(np.float64)
            defense_count = self._economic_ask_count[first:stop][keep].astype(np.float64)
        if self.level_association_mode == "LEVEL_ASSOCIATION_DESTROYED":
            defense_tick = np.asarray([
                _destroy_tick(int(value), self.asset) for value in defense_tick],
                np.int64)
            opposing_tick = np.asarray([
                _destroy_tick(int(value), self.asset) for value in opposing_tick],
                np.int64)
        total_duration = float(durations.sum())
        requested_duration = (right_ns - left_ns) / 1e9
        weights = durations / total_duration
        aligned_tick = side * (defense_tick.astype(np.float64) - formation_tick)
        average_order = defense_size / np.maximum(1.0, defense_count)
        fragmentation = defense_count / np.maximum(1.0, defense_size)

        # Consecutive economic states define exact same-best queue changes.
        same_best = defense_tick[1:] == defense_tick[:-1]
        size_delta = np.diff(defense_size)
        depletion = same_best & (size_delta < 0)
        rebuild = same_best & (size_delta > 0)
        favorable_best = side * np.diff(defense_tick) > 0
        adverse_best = side * np.diff(defense_tick) < 0
        formation_present = defense_tick == int(formation_tick)
        disappears = formation_present[:-1] & ~formation_present[1:]

        rebuild_latencies: list[float] = []
        pending_depletion: dict[int, int] = {}
        for index in range(1, len(defense_tick)):
            tick = int(defense_tick[index])
            if defense_tick[index] != defense_tick[index - 1]:
                pending_depletion.pop(int(defense_tick[index - 1]), None)
                continue
            if size_delta[index - 1] < 0:
                pending_depletion[tick] = int(ts[index])
            elif size_delta[index - 1] > 0 and tick in pending_depletion:
                rebuild_latencies.append(
                    (int(ts[index]) - pending_depletion.pop(tick)) / 1e6)

        # Dwell is duration, not message count.  Merge adjacent equal bests.
        best_dwell = current_dwell = 0.0
        run_tick: int | None = None
        run_duration = 0.0
        for tick, duration in zip(defense_tick, durations):
            if run_tick is None or int(tick) == run_tick:
                run_duration += float(duration)
            else:
                best_dwell = max(best_dwell, run_duration)
                run_duration = float(duration)
            run_tick = int(tick)
        best_dwell = max(best_dwell, run_duration)
        current_dwell = run_duration

        elapsed = (starts.astype(np.float64) - float(starts[0])) / 1e9
        centered = elapsed - elapsed.mean()
        denominator = float(np.dot(centered, centered))
        size_slope = float(np.dot(
            centered, defense_size - defense_size.mean()) / denominator
            if denominator > 0.0 else 0.0)
        peak = np.maximum.accumulate(defense_size)
        drawdown = (peak - defense_size) / np.maximum(1.0, peak)
        output.update({
            prefix + "present": 1.0,
            prefix + "support_fraction": float(
                min(1.0, total_duration / requested_duration)
                if requested_duration > 0 else 0.0),
            prefix + "update_count": float(np.sum(ts >= left_ns)),
            prefix + "defense_at_formation_time_fraction": float(
                np.dot(weights, formation_present)),
            prefix + "defense_inside_z1_time_fraction": float(
                np.dot(weights, np.abs(defense_tick - formation_tick) <= 1)),
            prefix + "opposing_at_formation_time_fraction": float(
                np.dot(weights, opposing_tick == formation_tick)),
            prefix + "defense_best_aligned_ticks_mean": float(
                np.dot(weights, aligned_tick)),
            prefix + "defense_best_aligned_ticks_current": float(aligned_tick[-1]),
            prefix + "defense_best_favorable_change_count": float(
                favorable_best.sum()),
            prefix + "defense_best_adverse_change_count": float(adverse_best.sum()),
            prefix + "defense_best_change_count": float(
                np.sum(defense_tick[1:] != defense_tick[:-1])),
            prefix + "defense_best_current_dwell_sec": current_dwell,
            prefix + "defense_best_max_dwell_sec": best_dwell,
            prefix + "defense_size_time_mean": float(np.dot(weights, defense_size)),
            prefix + "defense_size_current": float(defense_size[-1]),
            prefix + "defense_size_min": float(defense_size.min()),
            prefix + "defense_size_max": float(defense_size.max()),
            prefix + "defense_size_slope_per_sec": size_slope,
            prefix + "defense_count_time_mean": float(np.dot(weights, defense_count)),
            prefix + "defense_count_current": float(defense_count[-1]),
            prefix + "defense_average_order_size_time_mean": float(
                np.dot(weights, average_order)),
            prefix + "defense_average_order_size_current": float(average_order[-1]),
            prefix + "defense_fragmentation_time_mean": float(
                np.dot(weights, fragmentation)),
            prefix + "depletion_count": float(depletion.sum()),
            prefix + "depletion_size": float((-size_delta[depletion]).sum()),
            prefix + "depletion_rate_per_sec": float(
                depletion.sum() / total_duration),
            prefix + "rebuild_count": float(rebuild.sum()),
            prefix + "rebuild_size": float(size_delta[rebuild].sum()),
            prefix + "rebuild_rate_per_sec": float(rebuild.sum() / total_duration),
            prefix + "rebuild_after_depletion_count": float(len(rebuild_latencies)),
            prefix + "rebuild_after_depletion_mean_latency_ms": float(
                np.mean(rebuild_latencies) if rebuild_latencies else 0.0),
            prefix + "rebuild_after_depletion_max_latency_ms": float(
                np.max(rebuild_latencies) if rebuild_latencies else 0.0),
            prefix + "peak_to_min_drawdown_fraction": float(drawdown.max()),
            prefix + "current_from_peak_fraction": float(
                defense_size[-1] / max(1.0, peak[-1])),
            prefix + "formation_level_disappearance_count": float(
                disappears.sum()),
        })
        return output

    def _best_quote_response_map(
        self, *, formation_tick: int, formation_ts_ns: int,
        snapshot_ts_ns: int, side: int,
    ) -> dict[str, float]:
        values: dict[str, float] = {}
        for label, left_ns in (
            ("formation", formation_ts_ns),
            ("h30", max(formation_ts_ns, snapshot_ts_ns - 30_000_000_000)),
            ("h120", max(formation_ts_ns, snapshot_ts_ns - 120_000_000_000)),
        ):
            values.update(self._best_quote_window_map(
                prefix=f"disc_quote_{label}_",
                formation_tick=formation_tick, left_ns=left_ns,
                right_ns=snapshot_ts_ns, side=side))
        return values

    def _event_clock_map(
        self, *, target_count: int, snapshot_ts_ns: int,
        formation_ts_ns: int, side: int,
    ) -> dict[str, float]:
        prefix = f"disc_eclock_n{target_count}_"
        right = int(np.searchsorted(
            self._message_ts, snapshot_ts_ns, side="left"))
        left = max(0, right - int(target_count))
        ts = self._message_ts[left:right]
        action = self._message_action[left:right]
        event_side = self._message_side[left:right]
        size = self._message_size[left:right].astype(np.float64)
        econ = self._message_economic[left:right]
        count = len(ts)
        span = float((ts[-1] - ts[0]) / 1e9) if count >= 2 else 0.0
        gaps = np.diff(ts).astype(np.float64) / 1e6
        trade = action == ord("T")
        buy = trade & (event_side == ord("B"))
        sell = trade & (event_side == ord("A"))
        signed = np.where(buy, size, np.where(sell, -size, 0.0))
        trade_volume = float(size[trade].sum())
        quote = np.isin(action, (ord("A"), ord("C"), ord("M")))
        add = action == ord("A")
        cancel = action == ord("C")
        modify = action == ord("M")
        defense_side = ord("B") if side > 0 else ord("A")
        opposing_side = ord("A") if side > 0 else ord("B")
        defense = event_side == defense_side
        opposing = event_side == opposing_side
        quote_size = float(size[quote].sum())
        defense_commitment = float(
            (size[(add | modify) & defense].sum()
             - size[cancel & defense].sum()) / quote_size
            if quote_size else 0.0)
        opposing_withdrawal = float(
            (size[cancel & opposing].sum()
             - size[(add | modify) & opposing].sum()) / quote_size
            if quote_size else 0.0)

        mids = self._message_mid2[left:right][econ]
        if len(mids) >= 2:
            mid_delta = np.diff(mids).astype(np.float64)
            displacement = float(side * (mids[-1] - mids[0]) * self.factor)
            variation = float(np.abs(mid_delta).sum() * self.factor)
        else:
            displacement = variation = 0.0
        bid_size = self._message_bid_sz[left:right][econ].astype(np.float64)
        ask_size = self._message_ask_sz[left:right][econ].astype(np.float64)
        bid_count = self._message_bid_ct[left:right][econ].astype(np.float64)
        ask_count = self._message_ask_ct[left:right][econ].astype(np.float64)
        if len(bid_size):
            total_size = bid_size + ask_size
            total_count = bid_count + ask_count
            size_imbalance = side * (bid_size - ask_size) / np.maximum(1.0, total_size)
            count_imbalance = side * (bid_count - ask_count) / np.maximum(1.0, total_count)
            defense_size = bid_size if side > 0 else ask_size
            defense_count = bid_count if side > 0 else ask_count
            opposing_size = ask_size if side > 0 else bid_size
            opposing_count = ask_count if side > 0 else bid_count
            defense_average = defense_size / np.maximum(1.0, defense_count)
            opposing_average = opposing_size / np.maximum(1.0, opposing_count)
        else:
            size_imbalance = count_imbalance = np.empty(0, np.float64)
            defense_average = opposing_average = np.empty(0, np.float64)

        def mean(values: np.ndarray) -> float:
            return float(values.mean()) if len(values) else 0.0

        return {
            prefix + "support_count": float(count),
            prefix + "support_fraction": float(count / target_count),
            prefix + "span_ms": span * 1e3,
            prefix + "event_rate_hz": float(count / span if span > 0 else 0.0),
            prefix + "gap_median_ms": float(np.median(gaps) if len(gaps) else 0.0),
            prefix + "gap_p10_ms": float(np.quantile(gaps, .10) if len(gaps) else 0.0),
            prefix + "formation_fraction": float(
                np.mean(ts >= formation_ts_ns) if count else 0.0),
            prefix + "trade_fraction": float(np.mean(trade) if count else 0.0),
            prefix + "add_fraction": float(np.mean(add) if count else 0.0),
            prefix + "cancel_fraction": float(np.mean(cancel) if count else 0.0),
            prefix + "modify_fraction": float(np.mean(modify) if count else 0.0),
            prefix + "trade_volume": trade_volume,
            prefix + "aligned_flow_fraction": float(
                side * signed.sum() / trade_volume if trade_volume else 0.0),
            prefix + "defense_commitment": defense_commitment,
            prefix + "opposing_withdrawal": opposing_withdrawal,
            prefix + "quote_churn_per_trade_volume": float(
                quote_size / trade_volume if trade_volume else 0.0),
            prefix + "aligned_displacement_usd": displacement,
            prefix + "path_variation_usd": variation,
            prefix + "path_efficiency": float(
                abs(displacement) / variation if variation else 0.0),
            prefix + "aligned_size_imbalance_mean": mean(size_imbalance),
            prefix + "aligned_size_imbalance_slope": self._slope(size_imbalance),
            prefix + "aligned_count_imbalance_mean": mean(count_imbalance),
            prefix + "aligned_count_imbalance_slope": self._slope(count_imbalance),
            prefix + "defense_average_order_size": mean(defense_average),
            prefix + "defense_average_order_size_slope": self._slope(defense_average),
            prefix + "opposing_average_order_size": mean(opposing_average),
            prefix + "opposing_average_order_size_slope": self._slope(opposing_average),
            prefix + "size_count_divergence": float(
                mean(size_imbalance) - mean(count_imbalance)),
            prefix + "economic_fraction": float(np.mean(econ) if count else 0.0),
        }

    def _trade_slice_map(
        self, *, prefix: str, left: int, right: int, support_fraction: float,
        snapshot_ts_ns: int, formation_ts_ns: int, side: int,
    ) -> dict[str, float]:
        ts = self._trade_ts[left:right]
        signs = self._trade_sign[left:right].astype(np.float64)
        sizes = self._trade_exact_sizes[left:right].astype(np.float64)
        ticks = self._trade_exact_ticks[left:right].astype(np.float64)
        count = len(ts)
        volume = float(sizes.sum())
        span = float((ts[-1] - ts[0]) / 1e9) if count >= 2 else 0.0
        gaps = np.diff(ts).astype(np.float64) / 1e6
        aligned = side * signs

        def autocorrelation(lag: int) -> float:
            if count <= lag:
                return 0.0
            return float(np.mean(signs[lag:] * signs[:-lag]))

        current_run_count = 0
        current_run_volume = 0.0
        current_run_duration = 0.0
        current_control = 0.0
        max_run_count = 0
        max_run_volume = 0.0
        if count:
            current_sign = signs[-1]
            start = count - 1
            while start > 0 and signs[start - 1] == current_sign:
                start -= 1
            current_run_count = count - start
            current_run_volume = float(sizes[start:].sum())
            current_run_duration = float((ts[-1] - ts[start]) / 1e6)
            current_control = float(side * current_sign)
            run_start = 0
            for index in range(1, count + 1):
                if index == count or signs[index] != signs[run_start]:
                    max_run_count = max(max_run_count, index - run_start)
                    max_run_volume = max(
                        max_run_volume, float(sizes[run_start:index].sum()))
                    run_start = index

        if count >= 2:
            displacement = float(side * (ticks[-1] - ticks[0]))
            variation = float(np.abs(np.diff(ticks)).sum())
            tick_range = float(ticks.max() - ticks.min())
        else:
            displacement = variation = tick_range = 0.0
        weights = sizes / volume if volume else np.empty(0, np.float64)
        first_volume = float(sizes[:count // 2].sum()) if count >= 2 else 0.0
        second_volume = float(sizes[count // 2:].sum()) if count >= 2 else volume
        return {
            prefix + "support_count": float(count),
            prefix + "support_fraction": float(support_fraction),
            prefix + "span_ms": span * 1e3,
            prefix + "trade_rate_hz": float(count / span if span > 0 else 0.0),
            prefix + "volume": volume,
            prefix + "volume_rate": float(volume / span if span > 0 else 0.0),
            prefix + "formation_fraction": float(
                np.mean(ts >= formation_ts_ns) if count else 0.0),
            prefix + "aligned_flow_fraction": float(
                np.dot(aligned, sizes) / volume if volume else 0.0),
            prefix + "sign_autocorrelation_lag1": autocorrelation(1),
            prefix + "sign_autocorrelation_lag4": autocorrelation(4),
            prefix + "gap_median_ms": float(np.median(gaps) if len(gaps) else 0.0),
            prefix + "gap_p10_ms": float(np.quantile(gaps, .10) if len(gaps) else 0.0),
            prefix + "current_run_control": current_control,
            prefix + "current_run_count": float(current_run_count),
            prefix + "current_run_volume": current_run_volume,
            prefix + "current_run_duration_ms": current_run_duration,
            prefix + "current_run_over_max_volume": float(
                current_run_volume / max_run_volume if max_run_volume else 0.0),
            prefix + "max_run_count": float(max_run_count),
            prefix + "max_run_volume": max_run_volume,
            prefix + "volume_acceleration": float(
                (second_volume + 1.0) / (first_volume + 1.0)),
            prefix + "size_hhi": float(np.dot(weights, weights) if len(weights) else 0.0),
            prefix + "max_size_fraction": float(weights.max() if len(weights) else 0.0),
            prefix + "top3_size_fraction": float(
                np.sort(weights)[-3:].sum() if len(weights) else 0.0),
            prefix + "distinct_price_levels": float(len(np.unique(ticks))),
            prefix + "price_range_ticks": tick_range,
            prefix + "aligned_displacement_ticks": displacement,
            prefix + "path_variation_ticks": variation,
            prefix + "path_efficiency": float(
                abs(displacement) / variation if variation else 0.0),
            prefix + "sweep_speed_ticks_per_sec": float(
                tick_range / span if span > 0 else 0.0),
            prefix + "price_yield_per_aligned_volume": float(
                displacement / abs(np.dot(aligned, sizes))
                if np.dot(aligned, sizes) else 0.0),
            prefix + "last_trade_age_ms": float(
                (snapshot_ts_ns - ts[-1]) / 1e6 if count else 0.0),
        }

    def _trade_clock_map(
        self, *, target_count: int, snapshot_ts_ns: int,
        formation_ts_ns: int, side: int,
    ) -> dict[str, float]:
        right = int(np.searchsorted(self._trade_ts, snapshot_ts_ns, side="left"))
        left = max(0, right - int(target_count))
        return self._trade_slice_map(
            prefix=f"disc_tclock_n{target_count}_", left=left, right=right,
            support_fraction=(right - left) / float(target_count),
            snapshot_ts_ns=snapshot_ts_ns,
            formation_ts_ns=formation_ts_ns, side=side)

    def _volume_clock_map(
        self, *, target_volume: int, snapshot_ts_ns: int,
        formation_ts_ns: int, side: int,
    ) -> dict[str, float]:
        right = int(np.searchsorted(self._trade_ts, snapshot_ts_ns, side="left"))
        available = int(self._trade_volume_prefix[right])
        threshold = max(0, available - int(target_volume))
        left = max(0, int(np.searchsorted(
            self._trade_volume_prefix, threshold, side="right")) - 1)
        selected_volume = int(
            self._trade_volume_prefix[right] - self._trade_volume_prefix[left])
        return self._trade_slice_map(
            prefix=f"disc_vclock_v{target_volume}_", left=left, right=right,
            support_fraction=min(1.0, selected_volume / float(target_volume)),
            snapshot_ts_ns=snapshot_ts_ns,
            formation_ts_ns=formation_ts_ns, side=side)

    def _tape_slope_map(self, *, snapshot_sec: int, side: int) -> dict[str, float]:
        output: dict[str, float] = {}
        for horizon in (30, 120):
            left = max(0, snapshot_sec - horizon)
            width = snapshot_sec - left
            prefix = f"disc_tape_h{horizon}_"
            output[prefix + "support_fraction"] = float(width / horizon)
            for name in ("event", "trade", "volume", "quote_churn"):
                series = self._second_clock[name][left:snapshot_sec].astype(np.float64)
                half = len(series) // 2
                early = self._slope(series[:half]) if half >= 2 else 0.0
                late = self._slope(series[half:]) if len(series) - half >= 2 else 0.0
                output.update({
                    prefix + name + "_mean_per_sec": float(
                        series.mean() if len(series) else 0.0),
                    prefix + name + "_slope_per_sec2": self._slope(series),
                    prefix + name + "_slope_acceleration": float(late - early),
                    prefix + name + "_active_second_fraction": float(
                        np.mean(series > 0) if len(series) else 0.0),
                })
            signed = (side * self._second_clock["signed_volume"][
                left:snapshot_sec]).astype(np.float64)
            output.update({
                prefix + "aligned_flow_mean_per_sec": float(
                    signed.mean() if len(signed) else 0.0),
                prefix + "aligned_flow_slope_per_sec2": self._slope(signed),
            })
        return output

    def _test_maturity_map(
        self, *, formation_tick: int, formation_ts_ns: int,
        snapshot_ts_ns: int, side: int,
    ) -> dict[str, float]:
        stream = self._event_streams(
            center_tick=formation_tick, radius=2,
            left_ns=formation_ts_ns, right_ns=snapshot_ts_ns, side=side)
        attack_ts = stream["attack_ts"]
        attack_size = stream["attack_size"]
        starts = (np.r_[0, np.flatnonzero(
            np.diff(attack_ts) > 5_000_000_000) + 1]
                  if len(attack_ts) else np.empty(0, np.int64))
        burst_ts = attack_ts[starts] if len(starts) else np.empty(0, np.int64)
        burst_volume = (np.add.reduceat(attack_size, starts)
                        if len(starts) else np.empty(0, np.int64))
        gaps = np.diff(burst_ts).astype(np.float64) / 1e9
        output: dict[str, float] = {
            "disc_test_attack_events": float(len(attack_ts)),
            "disc_test_count": float(len(burst_ts)),
            "disc_test_span_sec": float(
                (burst_ts[-1] - burst_ts[0]) / 1e9 if len(burst_ts) >= 2 else 0.0),
            "disc_test_gap_median_sec": float(np.median(gaps) if len(gaps) else 0.0),
            "disc_test_last_age_sec": float(
                (snapshot_ts_ns - burst_ts[-1]) / 1e9 if len(burst_ts) else 0.0),
            "disc_test_first_volume": float(burst_volume[0] if len(burst_volume) else 0.0),
            "disc_test_last_volume": float(burst_volume[-1] if len(burst_volume) else 0.0),
            "disc_test_volume_slope": self._slope(burst_volume),
            "disc_test_last_over_first_volume": float(
                burst_volume[-1] / burst_volume[0]
                if len(burst_volume) and burst_volume[0] else 0.0),
        }
        for horizon_sec in (1, 5):
            completed = burst_ts[
                burst_ts + horizon_sec * 1_000_000_000 <= snapshot_ts_ns][-20:]
            favorable: list[float] = []
            adverse: list[float] = []
            endpoints: list[float] = []
            for timestamp in completed:
                left = int(np.searchsorted(self._economic_ts, timestamp, side="left"))
                right = int(np.searchsorted(
                    self._economic_ts,
                    timestamp + horizon_sec * 1_000_000_000, side="left"))
                if left >= right:
                    continue
                baseline = int(self._economic_mid2[max(0, left - 1)])
                path = (side * (self._economic_mid2[left:right] - baseline)
                        / (2.0 * self.raw_tick))
                favorable.append(float(max(0.0, np.max(path))))
                adverse.append(float(max(0.0, -np.min(path))))
                endpoints.append(float(path[-1]))
            fav = np.asarray(favorable, np.float64)
            adv = np.asarray(adverse, np.float64)
            end = np.asarray(endpoints, np.float64)
            prefix = f"disc_test_response_h{horizon_sec}_"
            output.update({
                prefix + "completed": float(len(fav)),
                prefix + "favorable_mean_ticks": float(fav.mean() if len(fav) else 0.0),
                prefix + "favorable_first_ticks": float(fav[0] if len(fav) else 0.0),
                prefix + "favorable_last_ticks": float(fav[-1] if len(fav) else 0.0),
                prefix + "favorable_slope_ticks": self._slope(fav),
                prefix + "adverse_mean_ticks": float(adv.mean() if len(adv) else 0.0),
                prefix + "adverse_last_ticks": float(adv[-1] if len(adv) else 0.0),
                prefix + "endpoint_mean_ticks": float(end.mean() if len(end) else 0.0),
                prefix + "endpoint_last_ticks": float(end[-1] if len(end) else 0.0),
                prefix + "defense_rate": float(
                    np.mean((adv <= 1.0) & (end >= -0.5)) if len(fav) else 0.0),
            })

        reload_ts = stream["reload_ts"]
        lift_ts = stream["lift_ts"]
        ordered = 0
        transfer_latency: list[float] = []
        for timestamp in burst_ts[-20:]:
            reload_index = int(np.searchsorted(reload_ts, timestamp, side="left"))
            if reload_index >= len(reload_ts):
                continue
            reload_time = int(reload_ts[reload_index])
            if reload_time - int(timestamp) > 1_000_000_000:
                continue
            lift_index = int(np.searchsorted(lift_ts, reload_time, side="right"))
            if lift_index < len(lift_ts) and int(lift_ts[lift_index]) < snapshot_ts_ns:
                ordered += 1
                transfer_latency.append((int(lift_ts[lift_index]) - int(timestamp)) / 1e6)
        output.update({
            "disc_test_reload_answer_rate": float(
                len(reload_ts) / len(attack_ts) if len(attack_ts) else 0.0),
            "disc_test_reload_size_per_attack_volume": float(
                stream["reload_size"].sum(dtype=np.int64)
                / attack_size.sum(dtype=np.int64)
                if attack_size.sum(dtype=np.int64) else 0.0),
            "disc_test_pull_over_reload_size": float(
                stream["pull_size"].sum(dtype=np.int64)
                / stream["reload_size"].sum(dtype=np.int64)
                if stream["reload_size"].sum(dtype=np.int64) else 0.0),
            "disc_test_attack_reload_lift_sequences": float(ordered),
            "disc_test_control_transfer_latency_median_ms": float(
                np.median(transfer_latency) if transfer_latency else 0.0),
        })
        return output

    def _event_streams(
        self, *, center_tick: int, radius: int, left_ns: int,
        right_ns: int, side: int,
    ) -> Mapping[str, np.ndarray]:
        buckets: dict[str, list[tuple[np.ndarray, np.ndarray]]] = {
            name: [] for name in ("attack", "lift", "reload", "pull")}
        for tick in range(center_tick - radius, center_tick + radius + 1):
            ledger = self._ledger.get(tick)
            if ledger is None:
                continue
            if side > 0:
                attack_ts, attack_size = ledger.sell_ts_ns, ledger.sell_event_size
                lift_ts, lift_size = ledger.buy_ts_ns, ledger.buy_event_size
                reload_ts = ledger.bid_reload_ts_ns
                reload_latency = ledger.bid_reload_latency_ns
                reload_size = ledger.bid_reload_size
                pull_ts = ledger.bid_pull_ts_ns
                pull_lifetime = ledger.bid_pull_lifetime_ns
                pull_size = ledger.bid_pull_size
            else:
                attack_ts, attack_size = ledger.buy_ts_ns, ledger.buy_event_size
                lift_ts, lift_size = ledger.sell_ts_ns, ledger.sell_event_size
                reload_ts = ledger.ask_reload_ts_ns
                reload_latency = ledger.ask_reload_latency_ns
                reload_size = ledger.ask_reload_size
                pull_ts = ledger.ask_pull_ts_ns
                pull_lifetime = ledger.ask_pull_lifetime_ns
                pull_size = ledger.ask_pull_size
            for name, timestamps, columns in (
                    ("attack", attack_ts, (attack_size,)),
                    ("lift", lift_ts, (lift_size,)),
                    ("reload", reload_ts, (reload_latency, reload_size)),
                    ("pull", pull_ts, (pull_lifetime, pull_size))):
                left = int(np.searchsorted(timestamps, left_ns, side="left"))
                right = int(np.searchsorted(timestamps, right_ns, side="left"))
                if right > left:
                    matrix = np.column_stack(tuple(
                        np.asarray(column[left:right], np.int64)
                        for column in columns))
                    buckets[name].append((timestamps[left:right], matrix))
        output: dict[str, np.ndarray] = {}
        for name, chunks in buckets.items():
            if not chunks:
                output[name + "_ts"] = np.empty(0, np.int64)
                if name in {"attack", "lift"}:
                    output[name + "_size"] = np.empty(0, np.int64)
                elif name == "reload":
                    output["reload_latency"] = np.empty(0, np.int64)
                    output["reload_size"] = np.empty(0, np.int64)
                else:
                    output["pull_lifetime"] = np.empty(0, np.int64)
                    output["pull_size"] = np.empty(0, np.int64)
                continue
            timestamps = np.concatenate([chunk[0] for chunk in chunks])
            matrix = np.concatenate([chunk[1] for chunk in chunks], axis=0)
            order = np.argsort(timestamps, kind="stable")
            output[name + "_ts"] = timestamps[order].astype(np.int64, copy=False)
            matrix = matrix[order]
            if name in {"attack", "lift"}:
                output[name + "_size"] = matrix[:, 0]
            elif name == "reload":
                output["reload_latency"] = matrix[:, 0]
                output["reload_size"] = matrix[:, 1]
            else:
                output["pull_lifetime"] = matrix[:, 0]
                output["pull_size"] = matrix[:, 1]
        return MappingProxyType(output)

    def _event_micro_map(
        self, *, prefix: str, center_tick: int, radius: int,
        left_ns: int, right_ns: int, side: int,
    ) -> dict[str, float]:
        stream = self._event_streams(
            center_tick=center_tick, radius=radius,
            left_ns=left_ns, right_ns=right_ns, side=side)
        attack_ts = stream["attack_ts"]; attack_size = stream["attack_size"]
        lift_ts = stream["lift_ts"]; lift_size = stream["lift_size"]
        reload_ts = stream["reload_ts"]; latency = stream["reload_latency"]
        reload_size = stream["reload_size"]
        pull_ts = stream["pull_ts"]; lifetime = stream["pull_lifetime"]
        pull_size = stream["pull_size"]
        width_sec = max(1e-9, (right_ns - left_ns) / 1e9)
        attack_gap = np.diff(attack_ts).astype(np.float64) / 1e6
        lift_gap = np.diff(lift_ts).astype(np.float64) / 1e6
        midpoint = left_ns + (right_ns - left_ns) // 2
        attack_first = int(np.sum(attack_ts < midpoint))
        attack_second = len(attack_ts) - attack_first
        ordered = False
        if len(attack_ts) and len(reload_ts) and len(lift_ts):
            for reload_time in reload_ts:
                if (np.searchsorted(attack_ts, reload_time, side="left") > 0
                        and np.searchsorted(lift_ts, reload_time, side="right")
                        < len(lift_ts)):
                    ordered = True
                    break
        return {
            prefix + "attack_event_count": float(len(attack_ts)),
            prefix + "attack_event_rate": float(len(attack_ts) / width_sec),
            prefix + "attack_volume": float(attack_size.sum(dtype=np.int64)),
            prefix + "attack_mean_size": float(attack_size.mean() if len(attack_size) else 0.0),
            prefix + "attack_max_size": float(attack_size.max() if len(attack_size) else 0.0),
            prefix + "attack_gap_median_ms": float(np.median(attack_gap) if len(attack_gap) else 0.0),
            prefix + "attack_gap_p10_ms": float(np.quantile(attack_gap, .10) if len(attack_gap) else 0.0),
            prefix + "attack_peak_100ms": float(self._peak_count(attack_ts, 100_000_000)),
            prefix + "attack_peak_250ms": float(self._peak_count(attack_ts, 250_000_000)),
            prefix + "attack_rate_acceleration": float(
                (attack_second + 1.0) / (attack_first + 1.0)),
            prefix + "lift_event_count": float(len(lift_ts)),
            prefix + "lift_event_rate": float(len(lift_ts) / width_sec),
            prefix + "lift_volume": float(lift_size.sum(dtype=np.int64)),
            prefix + "lift_mean_size": float(lift_size.mean() if len(lift_size) else 0.0),
            prefix + "lift_max_size": float(lift_size.max() if len(lift_size) else 0.0),
            prefix + "lift_gap_median_ms": float(np.median(lift_gap) if len(lift_gap) else 0.0),
            prefix + "lift_peak_100ms": float(self._peak_count(lift_ts, 100_000_000)),
            prefix + "reload_event_count": float(len(reload_ts)),
            prefix + "reload_size": float(reload_size.sum(dtype=np.int64)),
            prefix + "reload_latency_median_ms": float(
                np.median(latency) / 1e6 if len(latency) else 0.0),
            prefix + "reload_latency_p90_ms": float(
                np.quantile(latency, .90) / 1e6 if len(latency) else 0.0),
            prefix + "reload_per_attack": float(
                len(reload_ts) / len(attack_ts) if len(attack_ts) else 0.0),
            prefix + "reload_size_per_attack_volume": float(
                reload_size.sum(dtype=np.int64) / attack_size.sum(dtype=np.int64)
                if attack_size.sum(dtype=np.int64) else 0.0),
            prefix + "pull_no_fill_count": float(len(pull_ts)),
            prefix + "pull_no_fill_size": float(pull_size.sum(dtype=np.int64)),
            prefix + "pull_size_over_reload_size": float(
                pull_size.sum(dtype=np.int64) / reload_size.sum(dtype=np.int64)
                if reload_size.sum(dtype=np.int64) else 0.0),
            prefix + "pull_lifetime_median_ms": float(
                np.median(lifetime) / 1e6 if len(lifetime) else 0.0),
            prefix + "attack_reload_lift_ordered": float(ordered),
            prefix + "last_attack_age_ms": float(
                (right_ns - attack_ts[-1]) / 1e6 if len(attack_ts) else 0.0),
            prefix + "last_lift_age_ms": float(
                (right_ns - lift_ts[-1]) / 1e6 if len(lift_ts) else 0.0),
            prefix + "last_reload_age_ms": float(
                (right_ns - reload_ts[-1]) / 1e6 if len(reload_ts) else 0.0),
        }

    def _state_series(
        self, formation_ts_ns: int, formation_mid2: int, side: int,
    ) -> Mapping[str, np.ndarray]:
        key = (int(formation_ts_ns), int(formation_mid2), int(side))
        cached = self._state_cache.get(key)
        if cached is not None:
            return cached
        formation_ns = int(formation_ts_ns)
        stop_ns = formation_ns + 601_000_000_000
        left = int(np.searchsorted(self._price_ts, formation_ns, side="left"))
        right = int(np.searchsorted(self._price_ts, stop_ns, side="left"))
        # The virtual formation observation makes the state well-typed before
        # the first subsequent BBO price change.  Every real intrasecond price
        # transition is retained; same-price size changes are irrelevant to
        # this price-path state and live in the event/reload ledgers instead.
        timestamps = np.r_[
            np.int64(formation_ns), self._price_ts[left:right]].astype(np.int64)
        mids = np.r_[
            np.int64(formation_mid2), self._price_mid2[left:right]].astype(np.int64)
        displacement = (side * (mids - int(formation_mid2))
                        / (2.0 * self.raw_tick)).astype(np.float64)
        adverse_max = np.maximum.accumulate(np.maximum(-displacement, 0.0))
        favorable_max = np.maximum.accumulate(np.maximum(displacement, 0.0))
        adverse_seen = np.zeros(len(mids), bool)
        reclaim_seen = np.zeros(len(mids), bool)
        lift_seen = np.zeros(len(mids), bool)
        retest_seen = np.zeros(len(mids), bool)
        invalidated_seen = np.zeros(len(mids), bool)
        first_adverse = first_reclaim = first_lift = first_retest = -1
        for index, value in enumerate(displacement):
            if first_adverse < 0 and value <= -1.0:
                first_adverse = index
            if first_adverse >= 0 and first_reclaim < 0 and value >= 0.0:
                first_reclaim = index
            if first_reclaim >= 0 and first_lift < 0 and value >= 2.0:
                first_lift = index
            if (first_lift >= 0 and index > first_lift and first_retest < 0
                    and abs(value) <= 1.0):
                first_retest = index
            adverse_seen[index] = first_adverse >= 0
            reclaim_seen[index] = first_reclaim >= 0
            lift_seen[index] = first_lift >= 0
            retest_seen[index] = first_retest >= 0
            invalidated_seen[index] = (index > 0 and (
                invalidated_seen[index - 1] or value <= -4.0))
        result = MappingProxyType({
            "ts_ns": timestamps,
            "displacement": displacement, "adverse_max": adverse_max,
            "favorable_max": favorable_max, "adverse_seen": adverse_seen,
            "reclaim_seen": reclaim_seen, "lift_seen": lift_seen,
            "retest_seen": retest_seen, "invalidated_seen": invalidated_seen,
            "first_ts_ns": np.asarray(tuple(
                -1 if index < 0 else int(timestamps[index])
                for index in (first_adverse, first_reclaim,
                              first_lift, first_retest)), np.int64),
        })
        self._state_cache[key] = result
        return result

    def _forward_vol_map(
        self, *, formation_candidate: Mapping[str, object],
        formation_sec: int, phase_open_sec: int, snapshot_sec: int,
        current_mid2: int, formation_mid2: int, side: int,
    ) -> dict[str, float]:
        values: dict[str, float] = {}
        elapsed = max(0, snapshot_sec - formation_sec)
        for scope, start in (("session", 0), ("phase", phase_open_sec)):
            prefix = f"disc_fvol_{scope}_"
            def number(name: str) -> float:
                try:
                    value = float(formation_candidate.get(
                        f"{scope}_{name}", 0.0))
                except (TypeError, ValueError):
                    value = 0.0
                return value if math.isfinite(value) else 0.0
            present = number("forecast_present")
            sigma = number("sigma_hat_usd")
            range_hat = number("range_hat_usd")
            q10 = number("move_q10_usd")
            q25 = number("move_q25_usd")
            q50 = number("move_q50_usd")
            q75 = number("move_q75_usd")
            q90 = number("move_q90_usd")
            scope_elapsed = max(0, snapshot_sec - max(0, start))
            if scope == "phase":
                try:
                    close_sec = (int(formation_candidate.get(
                        "phase_close_utc", 0))
                        - self.open_ns // 1_000_000_000)
                except (TypeError, ValueError):
                    close_sec = snapshot_sec
            else:
                close_sec = self.duration
            remaining_sec = max(0, close_sec - snapshot_sec)
            mids = self._last_mid[max(0, start):snapshot_sec]
            mids = mids[mids > 0]
            actual_range = (0.0 if not len(mids) else
                            float((mids.max() - mids.min()) * self.factor))
            aligned_displacement = float(
                side * (int(current_mid2) - int(formation_mid2)) * self.factor)
            values.update({
                prefix + "present": present,
                prefix + "age_now_sec": number("forecast_age_sec") + elapsed,
                prefix + "sigma_hat_usd": sigma,
                prefix + "range_hat_usd": range_hat,
                # Keep the complete causal QRF4 sigma decomposition reachable
                # by the confirmation learner.  The selected point forecast is
                # useful, but by itself hides whether today's forecast differs
                # from persistence because of the OLS state, the causal
                # calibration ratio, or both.  Those distinctions are model
                # inputs; the diagnostics-only evaluation sidecar is not.
                prefix + "sigma_components_present": number(
                    "sigma_components_present"),
                prefix + "sigma_raw_hat_usd": number("sigma_raw_hat_usd"),
                prefix + "sigma_persistence_usd": number(
                    "sigma_persistence_usd"),
                prefix + "sigma_calibration_ratio": number(
                    "sigma_calibration_ratio"),
                prefix + "sigma_calibration_count": number(
                    "sigma_calibration_count"),
                prefix + "sigma_calibrated_hat_usd": number(
                    "sigma_calibrated_hat_usd"),
                prefix + "sigma_shrinkage_delta_usd": number(
                    "sigma_shrinkage_delta_usd"),
                prefix + "sigma_ols_minus_persistence_usd": number(
                    "sigma_ols_minus_persistence_usd"),
                prefix + "sigma_ols_over_persistence": number(
                    "sigma_ols_over_persistence"),
                prefix + "move_q10_usd": q10,
                prefix + "move_q25_usd": q25,
                prefix + "move_q50_usd": q50,
                prefix + "move_q75_usd": q75,
                prefix + "move_q90_usd": q90,
                prefix + "rv5_over_rv66": number("rv5_over_rv66"),
                prefix + "rv5_over_rv66_present": number("rv5_over_rv66_present"),
                prefix + "regime_low": number("regime_low_present"),
                prefix + "regime_mid": number("regime_mid_present"),
                prefix + "regime_high": number("regime_high_present"),
                prefix + "regime_present": number("regime_present"),
                prefix + "move_ladder_present": number("move_ladder_present"),
                prefix + "unscaled_fallback_present": number(
                    "unscaled_fallback_present"),
                prefix + "actual_range_usd": actual_range,
                prefix + "range_coverage": (
                    actual_range / range_hat if range_hat > 0 else 0.0),
                prefix + "q50_coverage": actual_range / q50 if q50 > 0 else 0.0,
                prefix + "q90_coverage": actual_range / q90 if q90 > 0 else 0.0,
                prefix + "q50_remaining_usd": max(0.0, q50 - actual_range),
                prefix + "q90_remaining_usd": max(0.0, q90 - actual_range),
                prefix + "aligned_displacement_over_q50": (
                    aligned_displacement / q50 if q50 > 0 else 0.0),
                prefix + "range_surprise_over_q90": (
                    max(0.0, actual_range - q90) / q90
                    if q90 > 0 else 0.0),
                prefix + "range_hat_over_sigma": (
                    range_hat / sigma if sigma > 0 else 0.0),
                prefix + "iqr_90_10_usd": max(0.0, q90 - q10),
                prefix + "iqr_75_25_usd": max(0.0, q75 - q25),
                prefix + "lower_tail_width_usd": max(0.0, q25 - q10),
                prefix + "lower_center_width_usd": max(0.0, q50 - q25),
                prefix + "upper_center_width_usd": max(0.0, q75 - q50),
                prefix + "upper_tail_width_usd": max(0.0, q90 - q75),
                prefix + "tail_width_asymmetry": float(
                    ((q90 - q75) - (q25 - q10)) / max(1.0, q90 - q10)
                    if q90 >= q75 >= q50 >= q25 >= q10 > 0 else 0.0),
                prefix + "center_width_asymmetry": float(
                    ((q75 - q50) - (q50 - q25)) / max(1.0, q75 - q25)
                    if q75 >= q50 >= q25 > 0 else 0.0),
                prefix + "quantile_slope_usd": float(
                    (q90 - q10) / .8 if q90 >= q10 > 0 else 0.0),
                prefix + "quantile_curvature_usd": float(
                    (q90 - q75) - (q25 - q10)
                    if q90 >= q75 >= q25 >= q10 > 0 else 0.0),
                prefix + "q90_over_q50": float(q90 / q50 if q50 > 0 else 0.0),
                prefix + "q50_over_sigma": float(q50 / sigma if sigma > 0 else 0.0),
                prefix + "q90_over_sigma": float(q90 / sigma if sigma > 0 else 0.0),
                prefix + "ladder_monotone": float(
                    q90 >= q75 >= q50 >= q25 >= q10 > 0),
                prefix + "scope_elapsed_sec": float(scope_elapsed),
                prefix + "scope_remaining_sec": float(remaining_sec),
                prefix + "range_consumption_usd_per_min": float(
                    actual_range * 60.0 / scope_elapsed
                    if scope_elapsed > 0 else 0.0),
                prefix + "q50_consumption_fraction_per_min": float(
                    actual_range / q50 * 60.0 / scope_elapsed
                    if scope_elapsed > 0 and q50 > 0 else 0.0),
                prefix + "q90_consumption_fraction_per_min": float(
                    actual_range / q90 * 60.0 / scope_elapsed
                    if scope_elapsed > 0 and q90 > 0 else 0.0),
                prefix + "q50_headroom_usd_per_remaining_min": float(
                    max(0.0, q50 - actual_range) * 60.0 / remaining_sec
                    if remaining_sec > 0 else 0.0),
                prefix + "q90_headroom_usd_per_remaining_min": float(
                    max(0.0, q90 - actual_range) * 60.0 / remaining_sec
                    if remaining_sec > 0 else 0.0),
                prefix + "q50_overshoot_usd": max(0.0, actual_range - q50),
                prefix + "q90_overshoot_usd": max(0.0, actual_range - q90),
            })
            for name in (
                    "vintage_history_present", "vintage_ready_count_5",
                    "vintage_ready_count_22", "vintage_sigma_delta_1_usd",
                    "vintage_sigma_slope_5_usd", "vintage_sigma_slope_22_usd",
                    "vintage_sigma_acceleration_usd", "vintage_range_delta_1_usd",
                    "vintage_range_slope_5_usd", "vintage_range_slope_22_usd",
                    "vintage_range_acceleration_usd", "vintage_q50_delta_1_usd",
                    "vintage_q50_slope_5_usd", "vintage_q50_slope_22_usd",
                    "vintage_q50_acceleration_usd", "vintage_q90_delta_1_usd",
                    "vintage_q90_slope_5_usd", "vintage_q90_slope_22_usd",
                    "vintage_q90_acceleration_usd", "vintage_rv_ratio_delta_1",
                    "vintage_rv_ratio_slope_5", "vintage_rv_ratio_slope_22",
                    "vintage_rv_ratio_acceleration", "vintage_regime_changed",
                    "vintage_regime_persistence"):
                values[prefix + name] = number(name)
        session_prefix = "disc_fvol_session_"
        phase_prefix = "disc_fvol_phase_"
        def difference(name: str) -> float:
            return float(values[phase_prefix + name] - values[session_prefix + name])
        def ratio(name: str) -> float:
            denominator = values[session_prefix + name]
            return float(values[phase_prefix + name] / denominator
                         if denominator else 0.0)
        values.update({
            "disc_fvol_cross_sigma_phase_minus_session_usd": difference("sigma_hat_usd"),
            "disc_fvol_cross_sigma_phase_over_session": ratio("sigma_hat_usd"),
            "disc_fvol_cross_range_phase_minus_session_usd": difference("range_hat_usd"),
            "disc_fvol_cross_range_phase_over_session": ratio("range_hat_usd"),
            "disc_fvol_cross_q50_phase_minus_session_usd": difference("move_q50_usd"),
            "disc_fvol_cross_q50_phase_over_session": ratio("move_q50_usd"),
            "disc_fvol_cross_q90_phase_minus_session_usd": difference("move_q90_usd"),
            "disc_fvol_cross_q90_phase_over_session": ratio("move_q90_usd"),
            "disc_fvol_cross_q50_coverage_disagreement": difference("q50_coverage"),
            "disc_fvol_cross_q90_coverage_disagreement": difference("q90_coverage"),
            "disc_fvol_cross_q50_remaining_disagreement_usd": difference(
                "q50_remaining_usd"),
            "disc_fvol_cross_quantile_curvature_disagreement_usd": difference(
                "quantile_curvature_usd"),
            "disc_fvol_cross_vintage_sigma_slope_5_disagreement_usd": difference(
                "vintage_sigma_slope_5_usd"),
            "disc_fvol_cross_vintage_range_slope_5_disagreement_usd": difference(
                "vintage_range_slope_5_usd"),
            "disc_fvol_cross_regime_disagreement": float(
                values[session_prefix + "regime_present"] > 0
                and values[phase_prefix + "regime_present"] > 0
                and ((values[session_prefix + "regime_low"]
                      != values[phase_prefix + "regime_low"])
                     or (values[session_prefix + "regime_mid"]
                         != values[phase_prefix + "regime_mid"])
                     or (values[session_prefix + "regime_high"]
                         != values[phase_prefix + "regime_high"]))),
            # The present QRE2 artifact has one open-time vintage per day.
            # Intraday revision features remain typed unavailable until the
            # upgraded publisher emits causal intra-session vintages.
            "disc_fvol_intraday_revision_available": 0.0,
        })
        return values

    def _regime_map(
        self, *, snapshot_sec: int, current_mid2: int, side: int,
    ) -> dict[str, float]:
        values: dict[str, float] = {}
        for horizon in (60, 300, 1800):
            mids = self._last_mid[max(0, snapshot_sec - horizon):snapshot_sec]
            mids = mids[mids > 0]
            prefix = f"disc_regime_h{horizon}_"
            if len(mids) < 2:
                values.update({
                    prefix + "range_usd": 0.0,
                    prefix + "displacement_usd": 0.0,
                    prefix + "aligned_displacement_usd": 0.0,
                    prefix + "path_variation_usd": 0.0,
                    prefix + "path_efficiency": 0.0,
                    prefix + "range_position": 0.0,
                })
                continue
            delta = np.diff(mids)
            displacement = float((mids[-1] - mids[0]) * self.factor)
            variation = float(np.abs(delta).sum(dtype=np.int64) * self.factor)
            span = float((mids.max() - mids.min()) * self.factor)
            values.update({
                prefix + "range_usd": span,
                prefix + "displacement_usd": displacement,
                prefix + "aligned_displacement_usd": side * displacement,
                prefix + "path_variation_usd": variation,
                prefix + "path_efficiency": (
                    abs(displacement) / variation if variation else 0.0),
                prefix + "range_position": float(
                    (int(current_mid2) - int(mids.min()))
                    / max(1, int(mids.max()) - int(mids.min()))),
            })
        values.update({
            "disc_regime_efficiency_60_over_1800": float(
                (values["disc_regime_h60_path_efficiency"] + .01)
                / (values["disc_regime_h1800_path_efficiency"] + .01)),
            "disc_regime_range_60_over_1800": float(
                (values["disc_regime_h60_range_usd"] + 1.0)
                / (values["disc_regime_h1800_range_usd"] + 1.0)),
            "disc_regime_range_300_over_1800": float(
                (values["disc_regime_h300_range_usd"] + 1.0)
                / (values["disc_regime_h1800_range_usd"] + 1.0)),
        })
        return values

    def _target_map(
        self, *, snapshot_sec: int, current_mid2: int, side: int,
        phase_open_sec: int, atr_usd: float,
    ) -> dict[str, float]:
        levels: list[float] = []
        for start in (0, phase_open_sec):
            state, _ordinal = self._profile_at(start, snapshot_sec)
            if state is not None:
                levels.extend((
                    state.low_tick, state.val_tick, state.poc_tick,
                    state.vah_tick, state.high_tick,
                    state.nearest_hvn_tick, state.nearest_lvn_tick))
        prior = self.prior_session
        if prior is not None:
            levels.extend((
                prior.low_mid2 / (2.0 * self.raw_tick),
                prior.close_mid2 / (2.0 * self.raw_tick),
                prior.high_mid2 / (2.0 * self.raw_tick),
            ))
            if prior.profile is not None:
                levels.extend((
                    prior.profile.low_tick, prior.profile.val_tick,
                    prior.profile.poc_tick, prior.profile.vah_tick,
                    prior.profile.high_tick, prior.profile.nearest_hvn_tick,
                    prior.profile.nearest_lvn_tick,
                ))
        current_tick = float(current_mid2) / (2.0 * self.raw_tick)
        unit = self.raw_tick * 1e-9 * self.multiplier
        distances = sorted(set(
            side * (float(level) - current_tick) * unit for level in levels))
        forward = [value for value in distances if value > 0.0]
        behind = sorted(-value for value in distances if value < 0.0)
        room = forward[0] if forward else 0.0
        invalidation = behind[0] if behind else 0.0
        return {
            "disc_target_forward_present": float(bool(forward)),
            "disc_target_next_room_usd": float(room),
            "disc_target_second_room_usd": float(
                forward[1] if len(forward) > 1 else 0.0),
            "disc_target_backward_present": float(bool(behind)),
            "disc_target_nearest_invalidation_usd": float(invalidation),
            "disc_target_forward_levels_300": float(sum(value <= 300 for value in forward)),
            "disc_target_forward_levels_600": float(sum(value <= 600 for value in forward)),
            "disc_target_forward_levels_900": float(sum(value <= 900 for value in forward)),
            "disc_target_room_over_atr": float(room / atr_usd if atr_usd > 0 else 0.0),
            "disc_target_room_over_invalidation": float(
                room / invalidation if invalidation > 0 else 0.0),
        }

    def _prior_reaction_map(
        self, *, formation_tick: int, formation_ts_ns: int,
        side: int,
    ) -> dict[str, float]:
        stream = self._event_streams(
            center_tick=formation_tick, radius=2,
            left_ns=self.open_ns, right_ns=formation_ts_ns, side=side)
        attack = stream["attack_ts"]
        if len(attack):
            burst = attack[np.r_[True, np.diff(attack) > 5_000_000_000]]
        else:
            burst = attack
        values: dict[str, float] = {
            "disc_origin_prior_attack_bursts": float(len(burst)),
            "disc_origin_last_attack_age_sec": float(
                (formation_ts_ns - burst[-1]) / 1e9 if len(burst) else 0.0),
        }
        for horizon in (5, 30, 120):
            completed = burst[burst + horizon * 1_000_000_000 <= formation_ts_ns]
            completed = completed[-20:]
            favorable: list[float] = []
            adverse: list[float] = []
            for timestamp in completed:
                left = int(np.searchsorted(
                    self._economic_ts, timestamp, side="left"))
                right = int(np.searchsorted(
                    self._economic_ts,
                    timestamp + horizon * 1_000_000_000, side="left"))
                if left >= right:
                    continue
                base_index = max(0, left - 1)
                base = int(self._economic_mid2[base_index])
                path = (side * (self._economic_mid2[left:right] - base)
                        * self.factor)
                favorable.append(float(max(0.0, np.max(path))))
                adverse.append(float(max(0.0, -np.min(path))))
            prefix = f"disc_origin_h{horizon}_"
            values.update({
                prefix + "completed_reactions": float(len(favorable)),
                prefix + "favorable_mean_usd": float(
                    np.mean(favorable) if favorable else 0.0),
                prefix + "favorable_max_usd": float(
                    np.max(favorable) if favorable else 0.0),
                prefix + "favorable_first_usd": float(
                    favorable[0] if favorable else 0.0),
                prefix + "favorable_last_usd": float(
                    favorable[-1] if favorable else 0.0),
                prefix + "favorable_slope_usd": self._slope(
                    np.asarray(favorable, np.float64)),
                prefix + "adverse_mean_usd": float(
                    np.mean(adverse) if adverse else 0.0),
                prefix + "adverse_first_usd": float(
                    adverse[0] if adverse else 0.0),
                prefix + "adverse_last_usd": float(
                    adverse[-1] if adverse else 0.0),
                prefix + "adverse_slope_usd": self._slope(
                    np.asarray(adverse, np.float64)),
                prefix + "response_decay_usd": float(
                    favorable[-1] - favorable[0] if favorable else 0.0),
                prefix + "defense_rate": float(
                    np.mean(np.asarray(favorable) > np.asarray(adverse))
                    if favorable else 0.0),
                prefix + "large_origin_count": float(
                    np.sum(np.asarray(favorable) >= 4.0 * self.raw_tick
                           * 1e-9 * self.multiplier) if favorable else 0.0),
            })
        return values

    def feature_map(
        self, *, snapshot_ts_ns: int, current_bid: int, current_ask: int,
        current_mid2: int, side: int, formation_candidate: Mapping[str, str],
    ) -> Mapping[str, float]:
        snapshot_sec = int((int(snapshot_ts_ns) - self.open_ns) // 1_000_000_000)
        if not 0 <= snapshot_sec <= self.duration:
            raise DiscretionaryFeatureRefusal("snapshot is outside session")
        formation_sec = int(formation_candidate["decision_sec"])
        formation_mid2 = int(formation_candidate["entry_mid2"])
        formation_bid = int(formation_candidate["entry_bid_px"])
        formation_ask = int(formation_candidate["entry_ask_px"])
        phase_open_sec = int(formation_candidate["phase_open_utc"]) - self.open_ns // 1_000_000_000
        if not (0 <= formation_sec <= snapshot_sec
                and formation_bid > 0 and formation_ask > formation_bid):
            raise DiscretionaryFeatureRefusal("formation state is malformed")
        values: dict[str, float] = {}
        values.update(self._profile_map(
            prefix="disc_auction_session_", start_sec=0,
            snapshot_sec=snapshot_sec, current_mid2=current_mid2, side=side))
        values.update(self._profile_map(
            prefix="disc_auction_phase_", start_sec=phase_open_sec,
            snapshot_sec=snapshot_sec, current_mid2=current_mid2, side=side))
        values.update(self._initial_balance_map(
            prefix="disc_ib_session_", start_sec=0,
            snapshot_sec=snapshot_sec, current_mid2=current_mid2, side=side))
        values.update(self._initial_balance_map(
            prefix="disc_ib_phase_", start_sec=phase_open_sec,
            snapshot_sec=snapshot_sec, current_mid2=current_mid2, side=side))
        if self.prior_session is None:
            values.update(PriorSessionContext.empty_feature_map())
        else:
            values.update(self.prior_session.feature_map(
                current_mid2=current_mid2, formation_bid=formation_bid,
                formation_ask=formation_ask, side=side,
                level_association_mode=self.level_association_mode))
        values.update(self._forward_vol_map(
            formation_candidate=formation_candidate,
            formation_sec=formation_sec, phase_open_sec=phase_open_sec,
            snapshot_sec=snapshot_sec, current_mid2=current_mid2,
            formation_mid2=formation_mid2, side=side))
        values.update(self._regime_map(
            snapshot_sec=snapshot_sec, current_mid2=current_mid2, side=side))

        formation_tick = ((formation_bid if side > 0 else formation_ask)
                          // self.raw_tick)
        current_tick = ((int(current_bid) if side > 0 else int(current_ask))
                        // self.raw_tick)
        try:
            atr_usd = float(formation_candidate.get("atr14_prev_usd", 0.0))
        except (TypeError, ValueError):
            atr_usd = 0.0
        values.update(self._target_map(
            snapshot_sec=snapshot_sec, current_mid2=current_mid2,
            side=side, phase_open_sec=phase_open_sec, atr_usd=atr_usd))
        for radius in (0, 2, 4):
            values.update(self._level_values(
                prefix=f"disc_memory_z{radius}_", center_tick=formation_tick,
                radius=radius, left_sec=0, right_sec=formation_sec,
                side=side, age_reference_sec=formation_sec))
            values.update(self._level_values(
                prefix=f"disc_level_z{radius}_", center_tick=formation_tick,
                radius=radius, left_sec=formation_sec, right_sec=snapshot_sec,
                side=side, age_reference_sec=snapshot_sec))
        values.update(self._level_values(
            prefix="disc_current_z2_", center_tick=current_tick, radius=2,
            left_sec=max(0, snapshot_sec - 30), right_sec=snapshot_sec,
            side=side, age_reference_sec=snapshot_sec))

        formation_ts_ns = int(formation_candidate["decision_ts_ns"])
        values.update(self._prior_reaction_map(
            formation_tick=formation_tick,
            formation_ts_ns=formation_ts_ns, side=side))
        for target_count in (16, 64, 256, 1024):
            values.update(self._event_clock_map(
                target_count=target_count,
                snapshot_ts_ns=int(snapshot_ts_ns),
                formation_ts_ns=formation_ts_ns, side=side))
        for target_count in (8, 32, 128, 512):
            values.update(self._trade_clock_map(
                target_count=target_count,
                snapshot_ts_ns=int(snapshot_ts_ns),
                formation_ts_ns=formation_ts_ns, side=side))
        for target_volume in (64, 256, 1024):
            values.update(self._volume_clock_map(
                target_volume=target_volume,
                snapshot_ts_ns=int(snapshot_ts_ns),
                formation_ts_ns=formation_ts_ns, side=side))
        values.update(self._tape_slope_map(
            snapshot_sec=snapshot_sec, side=side))
        values.update(self._test_maturity_map(
            formation_tick=formation_tick,
            formation_ts_ns=formation_ts_ns,
            snapshot_ts_ns=int(snapshot_ts_ns), side=side))
        values.update(self._best_quote_response_map(
            formation_tick=formation_tick,
            formation_ts_ns=formation_ts_ns,
            snapshot_ts_ns=int(snapshot_ts_ns), side=side))
        event_prefixes: dict[int, str] = {}
        for horizon in (1, 5, 15, 30, 60, 120, 300):
            event_prefix = f"disc_evt_h{horizon}_"
            event_prefixes[horizon] = event_prefix
            values.update(self._event_micro_map(
                prefix=event_prefix, center_tick=formation_tick, radius=2,
                left_ns=max(formation_ts_ns,
                            int(snapshot_ts_ns) - horizon * 1_000_000_000),
                right_ns=int(snapshot_ts_ns), side=side))
        for horizon in (30, 300):
            values.update(self._price_shape_values(
                prefix=f"disc_footprint_h{horizon}_",
                center_tick=formation_tick, radius=4,
                left_sec=max(formation_sec, snapshot_sec - horizon),
                right_sec=snapshot_sec, side=side))

        def ratio(short_horizon: int, long_horizon: int, suffix: str) -> float:
            short = values[event_prefixes[short_horizon] + suffix]
            long = values[event_prefixes[long_horizon] + suffix]
            return float((short + 1.0) / (long + 1.0))
        values.update({
            "disc_mhi_attack_rate_1_over_30": ratio(
                1, 30, "attack_event_rate"),
            "disc_mhi_attack_rate_5_over_60": ratio(
                5, 60, "attack_event_rate"),
            "disc_mhi_lift_rate_1_over_30": ratio(
                1, 30, "lift_event_rate"),
            "disc_mhi_lift_rate_5_over_60": ratio(
                5, 60, "lift_event_rate"),
            "disc_mhi_reload_per_attack_5_minus_60": float(
                values["disc_evt_h5_reload_per_attack"]
                - values["disc_evt_h60_reload_per_attack"]),
            "disc_mhi_attack_exhaustion_5_vs_30": float(
                values["disc_evt_h5_attack_event_rate"]
                < values["disc_evt_h30_attack_event_rate"]),
            "disc_mhi_lift_acceleration_5_vs_30": float(
                values["disc_evt_h5_lift_event_rate"]
                > values["disc_evt_h30_lift_event_rate"]),
        })

        state = self._state_series(formation_ts_ns, formation_mid2, side)
        index = int(np.searchsorted(
            state["ts_ns"], int(snapshot_ts_ns), side="left") - 1)
        index = min(max(0, index), len(state["displacement"]) - 1)
        first_ts_ns = np.asarray(state["first_ts_ns"], np.int64)
        def state_age(first_timestamp: int) -> float:
            return float((int(snapshot_ts_ns) - first_timestamp) / 1e9
                         if 0 <= first_timestamp < int(snapshot_ts_ns) else 0.0)
        values.update({
            "disc_state_current_displacement_ticks": float(state["displacement"][index]),
            "disc_state_adverse_max_ticks": float(state["adverse_max"][index]),
            "disc_state_favorable_max_ticks": float(state["favorable_max"][index]),
            "disc_state_adverse_seen": float(state["adverse_seen"][index]),
            "disc_state_reclaim_seen": float(state["reclaim_seen"][index]),
            "disc_state_lift_seen": float(state["lift_seen"][index]),
            "disc_state_retest_seen": float(state["retest_seen"][index]),
            "disc_state_invalidated_seen": float(state["invalidated_seen"][index]),
            "disc_state_adverse_age_sec": state_age(int(first_ts_ns[0])),
            "disc_state_reclaim_age_sec": state_age(int(first_ts_ns[1])),
            "disc_state_lift_age_sec": state_age(int(first_ts_ns[2])),
            "disc_state_retest_age_sec": state_age(int(first_ts_ns[3])),
            "disc_state_near_formation_z2": float(abs(state["displacement"][index]) <= 2.0),
        })
        attack = values["disc_level_z2_attack_volume"]
        lift = values["disc_level_z2_lift_volume"]
        displacement_usd = (side * (int(current_mid2) - formation_mid2)
                            * self.factor)
        values["disc_state_price_yield_per_attack"] = float(
            displacement_usd / attack if attack else 0.0)
        values["disc_state_price_yield_per_net_aggression"] = float(
            displacement_usd / abs(lift - attack) if lift != attack else 0.0)
        adverse_ticks = values["disc_state_adverse_max_ticks"]
        favorable_ticks = values["disc_state_favorable_max_ticks"]
        reloads = values["disc_level_z2_defense_reload_count"]
        pulls = values["disc_level_z2_defense_pull_no_fill"]
        values.update({
            "disc_absorption_attack_per_adverse_tick": float(
                attack / (1.0 + adverse_ticks)),
            "disc_absorption_lift_per_favorable_tick": float(
                lift / (1.0 + favorable_ticks)),
            "disc_absorption_reload_per_attack": float(
                reloads / attack if attack else 0.0),
            "disc_absorption_pull_vs_refill": float(
                (pulls + 1.0) / (reloads + 1.0)),
            "disc_absorption_two_sided": float(attack > 0 and lift > 0),
            "disc_path_failed_auction_reentry": float(
                state["adverse_seen"][index] and state["reclaim_seen"][index]),
            "disc_path_absorption_control_transfer": float(
                attack > 0 and reloads > 0 and state["lift_seen"][index]),
            "disc_path_refill_exhaustion_liftoff": float(
                reloads > 0
                and values["disc_mhi_attack_exhaustion_5_vs_30"] > 0
                and values["disc_mhi_lift_acceleration_5_vs_30"] > 0),
            "disc_path_ofm_retest_complete": float(
                state["adverse_seen"][index] and state["reclaim_seen"][index]
                and state["lift_seen"][index] and state["retest_seen"][index]),
            "disc_path_defended_retest_current": float(
                state["retest_seen"][index]
                and not state["invalidated_seen"][index]
                and state["displacement"][index] >= -1.0),
            "disc_path_second_test_memory": float(
                values["disc_memory_z2_attack_bursts"] >= 2.0),
            "disc_path_failed_reclaim_continuation": float(
                state["reclaim_seen"][index]
                and state["displacement"][index] <= -1.0),
        })
        directional_acceptance = (
            values["disc_auction_session_above_value_time_fraction"]
            if side > 0 else
            values["disc_auction_session_below_value_time_fraction"])
        opposite_acceptance = (
            values["disc_auction_session_below_value_time_fraction"]
            if side > 0 else
            values["disc_auction_session_above_value_time_fraction"])
        phase_headroom = values["disc_fvol_phase_q50_remaining_usd"]
        values.update({
            "disc_path_directional_value_acceptance": float(directional_acceptance),
            "disc_path_opposite_value_acceptance": float(opposite_acceptance),
            "disc_path_balance_fade_context": float(
                values["disc_auction_session_inside_value"] > 0
                and values["disc_regime_h300_path_efficiency"] < .35),
            "disc_path_balance_fade_confirmed": float(
                values["disc_auction_session_inside_value"] > 0
                and state["adverse_seen"][index]
                and state["reclaim_seen"][index]),
            "disc_path_expansion_context": float(
                directional_acceptance >= .5
                and values["disc_regime_h300_path_efficiency"] >= .35),
            "disc_path_expansion_with_headroom": float(
                directional_acceptance >= .5 and phase_headroom > 0.0),
            "disc_path_profile_forecast_headroom_ratio": float(
                values["disc_target_next_room_usd"] / phase_headroom
                if phase_headroom > 0 else 0.0),
            "disc_path_profile_forecast_q90_headroom_ratio": float(
                values["disc_target_next_room_usd"]
                / values["disc_fvol_phase_q90_remaining_usd"]
                if values["disc_fvol_phase_q90_remaining_usd"] > 0 else 0.0),
            "disc_path_forecast_clears_next_obstacle_q50": float(
                phase_headroom >= values["disc_target_next_room_usd"] > 0),
            "disc_path_forecast_clears_next_obstacle_q90": float(
                values["disc_fvol_phase_q90_remaining_usd"]
                >= values["disc_target_next_room_usd"] > 0),
            "disc_path_obstacle_minus_q50_headroom_usd": float(
                values["disc_target_next_room_usd"] - phase_headroom),
            "disc_path_ib_directional_break": float(
                values["disc_ib_phase_directional_break_seen"]),
            "disc_path_ib_failed_break": float(
                values["disc_ib_phase_directional_break_reentry_seen"]),
            "disc_path_value_escape_accepted": float(
                values["disc_auction_phase_directional_acceptance_score"]),
            "disc_path_value_escape_failed": float(
                values["disc_auction_phase_failed_directional_auction"]),
            "disc_path_directional_delta_at_value": float(
                values["disc_auction_phase_directional_delta_fraction"]),
            "disc_path_poc_migration_acceleration_usd": float(
                values["disc_auction_phase_poc_migration_5m_aligned_usd"]
                - (values["disc_auction_phase_poc_migration_15m_aligned_usd"] / 3.0)),
        })
        attack_plus_lift = attack + lift
        conflict_fraction = (2.0 * min(attack, lift) / attack_plus_lift
                             if attack_plus_lift else 0.0)
        values.update({
            "disc_behavior_aggressor_persistence": float(
                values["disc_tclock_n32_sign_autocorrelation_lag1"]),
            "disc_behavior_aggressor_concentration": float(
                values["disc_tclock_n32_size_hhi"]),
            "disc_behavior_defense_commitment": float(
                values["disc_eclock_n64_defense_commitment"]),
            "disc_behavior_opposing_withdrawal": float(
                values["disc_eclock_n64_opposing_withdrawal"]),
            "disc_behavior_price_elasticity_per_attack": float(
                adverse_ticks / attack if attack else 0.0),
            "disc_behavior_conflict_fraction": float(conflict_fraction),
            "disc_behavior_conflict_intensity": float(
                conflict_fraction * math.log1p(attack_plus_lift)),
            "disc_behavior_response_decay_h5_ticks": float(
                values["disc_test_response_h5_favorable_last_ticks"]
                - values["disc_test_response_h5_favorable_first_ticks"]),
            "disc_behavior_control_evidence_balance": float(
                values["disc_tclock_n32_aligned_flow_fraction"]
                + values["disc_eclock_n64_defense_commitment"]
                + values["disc_eclock_n64_opposing_withdrawal"]
                - values["disc_test_pull_over_reload_size"]),
            "disc_mhi_tape_event_slope_30_minus_120": float(
                values["disc_tape_h30_event_slope_per_sec2"]
                - values["disc_tape_h120_event_slope_per_sec2"]),
            "disc_mhi_tape_volume_slope_30_minus_120": float(
                values["disc_tape_h30_volume_slope_per_sec2"]
                - values["disc_tape_h120_volume_slope_per_sec2"]),
            "disc_mhi_trade_persistence_32_minus_128": float(
                values["disc_tclock_n32_sign_autocorrelation_lag1"]
                - values["disc_tclock_n128_sign_autocorrelation_lag1"]),
            "disc_mhi_defense_commitment_64_minus_256": float(
                values["disc_eclock_n64_defense_commitment"]
                - values["disc_eclock_n256_defense_commitment"]),
            "disc_mhi_tape_slope_x_phase_headroom": float(
                values["disc_tape_h30_volume_slope_per_sec2"]
                * values["disc_fvol_phase_q50_remaining_usd"]),
            "disc_mhi_flow_x_phase_headroom_fraction": float(
                values["disc_tclock_n32_aligned_flow_fraction"]
                * (1.0 - min(1.0, values["disc_fvol_phase_q50_coverage"]))),
        })
        values["disc_level_association_destroyed"] = float(
            self.level_association_mode == "LEVEL_ASSOCIATION_DESTROYED")
        values["disc_fill_coupling_destroyed"] = float(
            self.level_association_mode == "FILL_COUPLING_DESTROYED")
        if any(not math.isfinite(value) for value in values.values()):
            raise DiscretionaryFeatureRefusal("discretionary feature map is non-finite")
        return MappingProxyType(values)


__all__ = [
    "CausalDiscretionaryPlane", "DISCRETIONARY_FEATURE_SCHEMA",
    "DiscretionaryFeatureRefusal", "LEVEL_ASSOCIATION_MODES",
    "PRIOR_SESSION_SCHEMA", "PROFILE_INTERVAL_SEC", "PriorSessionContext",
]
