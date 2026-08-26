#!/usr/bin/env python3
"""Completed-session auction and per-price memory for discretionary features."""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

import numpy as np

from .diagnostic_inputs import native_book_quality
from .discretionary_features import (
    LEVEL_ASSOCIATION_MODES, PRIOR_SESSION_SCHEMA,
    DiscretionaryFeatureRefusal, _destroy_tick_inverse, _simple_sha,
)
from .discretionary_profile import _profile_state


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
