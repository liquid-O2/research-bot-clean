#!/usr/bin/env python3
"""Duration-aware BBO defense, depletion, and rebuild maps."""

from __future__ import annotations

import numpy as np

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .discretionary_features import CausalDiscretionaryPlane

from .discretionary_features import _destroy_tick


def _best_quote_window_map(
    plane: CausalDiscretionaryPlane, *, prefix: str, formation_tick: int, left_ns: int,
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
    left_ns = max(int(left_ns), int(plane.open_ns))
    right_ns = int(right_ns)
    if right_ns <= left_ns or not len(plane._economic_ts):
        return output
    first = max(0, int(np.searchsorted(
        plane._economic_ts, left_ns, side="left")) - 1)
    stop = int(np.searchsorted(plane._economic_ts, right_ns, side="left"))
    if first >= stop:
        return output
    ts = plane._economic_ts[first:stop]
    starts = np.maximum(ts, left_ns)
    ends = np.minimum(np.r_[ts[1:], right_ns], right_ns)
    durations = np.maximum(0, ends - starts).astype(np.float64) / 1e9
    keep = durations > 0.0
    if not np.any(keep):
        return output
    ts = ts[keep]; starts = starts[keep]; durations = durations[keep]
    if side > 0:
        defense_tick = plane._economic_bid_tick[first:stop][keep].copy()
        opposing_tick = plane._economic_ask_tick[first:stop][keep].copy()
        defense_size = plane._economic_bid_size[first:stop][keep].astype(np.float64)
        defense_count = plane._economic_bid_count[first:stop][keep].astype(np.float64)
    else:
        defense_tick = plane._economic_ask_tick[first:stop][keep].copy()
        opposing_tick = plane._economic_bid_tick[first:stop][keep].copy()
        defense_size = plane._economic_ask_size[first:stop][keep].astype(np.float64)
        defense_count = plane._economic_ask_count[first:stop][keep].astype(np.float64)
    if plane.level_association_mode == "LEVEL_ASSOCIATION_DESTROYED":
        defense_tick = np.asarray([
            _destroy_tick(int(value), plane.asset) for value in defense_tick],
            np.int64)
        opposing_tick = np.asarray([
            _destroy_tick(int(value), plane.asset) for value in opposing_tick],
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
    plane: CausalDiscretionaryPlane, *, formation_tick: int, formation_ts_ns: int,
    snapshot_ts_ns: int, side: int,
) -> dict[str, float]:
    values: dict[str, float] = {}
    for label, left_ns in (
        ("formation", formation_ts_ns),
        ("h30", max(formation_ts_ns, snapshot_ts_ns - 30_000_000_000)),
        ("h120", max(formation_ts_ns, snapshot_ts_ns - 120_000_000_000)),
    ):
        values.update(_best_quote_window_map(
            plane, prefix=f"disc_quote_{label}_",
            formation_tick=formation_tick, left_ns=left_ns,
            right_ns=snapshot_ts_ns, side=side))
    return values
