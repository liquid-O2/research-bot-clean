#!/usr/bin/env python3
"""Per-tick ledgers and level / footprint queries."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

import numpy as np

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .discretionary_features import CausalDiscretionaryPlane

from .discretionary_features import DiscretionaryFeatureRefusal


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

def _build_ledger(
    plane: CausalDiscretionaryPlane, event_index: np.ndarray, ticks: np.ndarray, action: np.ndarray,
    side: np.ndarray, size: np.ndarray,
    flags: Mapping[str, np.ndarray],
) -> Mapping[int, _TickLedger]:
    if not len(event_index):
        return MappingProxyType({})
    raw_ts = plane.rows["ts_recv_ns"].astype(np.int64)
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
        if (plane.level_association_mode == "FILL_COUPLING_DESTROYED"
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
    seconds = plane.second[event_index]
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
        event_ts = plane.rows["ts_recv_ns"][event_rows].astype(np.int64)
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

def _ledger_sum(
    plane: CausalDiscretionaryPlane, *, center_tick: int, radius: int, left_sec: int, right_sec: int,
) -> tuple[np.ndarray, int, int, int, int, int, int]:
    totals = np.zeros(len(_LEDGER_METRICS), np.int64)
    buy_bursts = sell_bursts = 0
    last_buy = last_sell = -1
    max_buy = max_sell = 0
    for tick in range(int(center_tick) - radius, int(center_tick) + radius + 1):
        ledger = plane._ledger.get(tick)
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
    plane: CausalDiscretionaryPlane, *, prefix: str, center_tick: int, radius: int,
    left_sec: int, right_sec: int, side: int, age_reference_sec: int,
) -> dict[str, float]:
    (total, buy_bursts, sell_bursts, last_buy, last_sell,
     max_buy, max_sell) = _ledger_sum(plane,
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
    plane: CausalDiscretionaryPlane, *, prefix: str, center_tick: int, radius: int,
    left_sec: int, right_sec: int, side: int,
) -> dict[str, float]:
    ticks = np.arange(center_tick - radius, center_tick + radius + 1)
    buy = np.zeros(len(ticks), np.float64)
    sell = np.zeros(len(ticks), np.float64)
    reload = np.zeros(len(ticks), np.float64)
    for index, tick in enumerate(ticks):
        total, *_rest = _ledger_sum(plane,
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
