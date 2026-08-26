#!/usr/bin/env python3
"""Event streams, micro structure, test maturity, and path state."""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

import numpy as np

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .discretionary_features import CausalDiscretionaryPlane

from .discretionary_tape import _slope


def _peak_count(timestamps: np.ndarray, width_ns: int) -> int:
    left = best = 0
    for right in range(len(timestamps)):
        while timestamps[right] - timestamps[left] >= width_ns:
            left += 1
        best = max(best, right - left + 1)
    return best

def _test_maturity_map(
    plane: CausalDiscretionaryPlane, *, formation_tick: int, formation_ts_ns: int,
    snapshot_ts_ns: int, side: int,
) -> dict[str, float]:
    stream = _event_streams(plane,
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
        "disc_test_volume_slope": _slope(burst_volume),
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
            left = int(np.searchsorted(plane._economic_ts, timestamp, side="left"))
            right = int(np.searchsorted(
                plane._economic_ts,
                timestamp + horizon_sec * 1_000_000_000, side="left"))
            if left >= right:
                continue
            baseline = int(plane._economic_mid2[max(0, left - 1)])
            path = (side * (plane._economic_mid2[left:right] - baseline)
                    / (2.0 * plane.raw_tick))
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
            prefix + "favorable_slope_ticks": _slope(fav),
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
    plane: CausalDiscretionaryPlane, *, center_tick: int, radius: int, left_ns: int,
    right_ns: int, side: int,
) -> Mapping[str, np.ndarray]:
    buckets: dict[str, list[tuple[np.ndarray, np.ndarray]]] = {
        name: [] for name in ("attack", "lift", "reload", "pull")}
    for tick in range(center_tick - radius, center_tick + radius + 1):
        ledger = plane._ledger.get(tick)
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
    plane: CausalDiscretionaryPlane, *, prefix: str, center_tick: int, radius: int,
    left_ns: int, right_ns: int, side: int,
) -> dict[str, float]:
    stream = _event_streams(plane,
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
        prefix + "attack_peak_100ms": float(_peak_count(attack_ts, 100_000_000)),
        prefix + "attack_peak_250ms": float(_peak_count(attack_ts, 250_000_000)),
        prefix + "attack_rate_acceleration": float(
            (attack_second + 1.0) / (attack_first + 1.0)),
        prefix + "lift_event_count": float(len(lift_ts)),
        prefix + "lift_event_rate": float(len(lift_ts) / width_sec),
        prefix + "lift_volume": float(lift_size.sum(dtype=np.int64)),
        prefix + "lift_mean_size": float(lift_size.mean() if len(lift_size) else 0.0),
        prefix + "lift_max_size": float(lift_size.max() if len(lift_size) else 0.0),
        prefix + "lift_gap_median_ms": float(np.median(lift_gap) if len(lift_gap) else 0.0),
        prefix + "lift_peak_100ms": float(_peak_count(lift_ts, 100_000_000)),
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
    plane: CausalDiscretionaryPlane, formation_ts_ns: int, formation_mid2: int, side: int,
) -> Mapping[str, np.ndarray]:
    key = (int(formation_ts_ns), int(formation_mid2), int(side))
    cached = plane._state_cache.get(key)
    if cached is not None:
        return cached
    formation_ns = int(formation_ts_ns)
    stop_ns = formation_ns + 601_000_000_000
    left = int(np.searchsorted(plane._price_ts, formation_ns, side="left"))
    right = int(np.searchsorted(plane._price_ts, stop_ns, side="left"))
    # The virtual formation observation makes the state well-typed before
    # the first subsequent BBO price change.  Every real intrasecond price
    # transition is retained; same-price size changes are irrelevant to
    # this price-path state and live in the event/reload ledgers instead.
    timestamps = np.r_[
        np.int64(formation_ns), plane._price_ts[left:right]].astype(np.int64)
    mids = np.r_[
        np.int64(formation_mid2), plane._price_mid2[left:right]].astype(np.int64)
    displacement = (side * (mids - int(formation_mid2))
                    / (2.0 * plane.raw_tick)).astype(np.float64)
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
    plane._state_cache[key] = result
    return result
