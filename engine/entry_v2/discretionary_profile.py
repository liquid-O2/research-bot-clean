#!/usr/bin/env python3
"""Auction profile, TPO, and initial-balance maps."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .discretionary_features import CausalDiscretionaryPlane

from .discretionary_features import (
    PROFILE_INTERVAL_SEC, PROFILE_KERNEL, VALUE_AREA_FRACTION,
    DiscretionaryFeatureRefusal,
)


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
def _build_profile_series(plane: CausalDiscretionaryPlane, start_sec: int) -> tuple[_ProfileState | None, ...]:
    start = max(0, int(start_sec))
    boundaries = range(start + PROFILE_INTERVAL_SEC,
                       plane.duration + 1, PROFILE_INTERVAL_SEC)
    output: list[_ProfileState | None] = []
    cursor = int(np.searchsorted(plane._trade_seconds, start, side="left"))
    histogram: dict[int, int] = {}
    signed_histogram: dict[int, int] = {}
    for boundary in boundaries:
        trade_right = int(np.searchsorted(
            plane._trade_seconds, boundary, side="left"))
        new_ticks = plane._trade_ticks[cursor:trade_right]
        new_sizes = plane._trade_sizes[cursor:trade_right]
        new_signed = (plane._trade_profile_sign[cursor:trade_right]
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
            reference = (int(plane._trade_ticks[trade_right - 1])
                         if trade_right > 0 else int(ticks[-1]))
            output.append(_profile_state(
                ticks, sizes, boundary, reference, signed_sizes))
        else:
            output.append(None)
    return tuple(output)

def _profile_at(plane: CausalDiscretionaryPlane, start_sec: int, snapshot_sec: int) -> tuple[
        _ProfileState | None, int]:
    start = max(0, int(start_sec))
    if start not in plane._profile_cache:
        plane._profile_cache[start] = _build_profile_series(plane, start)
    ordinal = (int(snapshot_sec) - start) // PROFILE_INTERVAL_SEC - 1
    series = plane._profile_cache[start]
    if ordinal < 0 or ordinal >= len(series):
        return None, ordinal
    return series[ordinal], ordinal

def _build_tpo_series(plane: CausalDiscretionaryPlane, start_sec: int) -> tuple[_ProfileState | None, ...]:
    start = max(0, int(start_sec))
    boundaries = range(start + PROFILE_INTERVAL_SEC,
                       plane.duration + 1, PROFILE_INTERVAL_SEC)
    histogram: dict[int, int] = {}
    cursor = start
    output: list[_ProfileState | None] = []
    for boundary in boundaries:
        mids = plane._last_mid[cursor:boundary]
        mids = mids[mids > 0]
        if len(mids):
            ticks = np.rint(
                mids.astype(np.float64) / (2.0 * plane.raw_tick)).astype(np.int64)
            unique, counts = np.unique(ticks, return_counts=True)
            for tick, count in zip(unique, counts):
                histogram[int(tick)] = histogram.get(int(tick), 0) + int(count)
        cursor = boundary
        if histogram:
            ticks = np.fromiter(sorted(histogram), dtype=np.int64)
            counts = np.asarray([histogram[int(tick)] for tick in ticks], np.int64)
            reference = int(np.rint(
                plane._last_mid[boundary - 1] / (2.0 * plane.raw_tick)))
            output.append(_profile_state(
                ticks, counts, boundary, reference, tpo=True))
        else:
            output.append(None)
    return tuple(output)

def _tpo_at(plane: CausalDiscretionaryPlane, start_sec: int, snapshot_sec: int) -> _ProfileState | None:
    start = max(0, int(start_sec))
    if start not in plane._tpo_cache:
        plane._tpo_cache[start] = _build_tpo_series(plane, start)
    ordinal = (int(snapshot_sec) - start) // PROFILE_INTERVAL_SEC - 1
    series = plane._tpo_cache[start]
    return None if ordinal < 0 or ordinal >= len(series) else series[ordinal]

def _profile_map(
    plane: CausalDiscretionaryPlane, *, prefix: str, start_sec: int, snapshot_sec: int,
    current_mid2: int, side: int,
) -> dict[str, float]:
    state, ordinal = _profile_at(plane, start_sec, snapshot_sec)
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
        return side * (int(current_mid2) - 2 * tick * plane.raw_tick) * plane.factor
    current_tick = float(current_mid2) / (2.0 * plane.raw_tick)
    width = max(1, state.high_tick - state.low_tick)
    values.update({
        prefix + "age_sec": float(snapshot_sec - state.boundary_sec),
        prefix + "poc_aligned_usd": distance(state.poc_tick),
        prefix + "val_aligned_usd": distance(state.val_tick),
        prefix + "vah_aligned_usd": distance(state.vah_tick),
        prefix + "value_width_usd": ((state.vah_tick - state.val_tick)
                                      * plane.raw_tick * 1e-9 * plane.multiplier),
        prefix + "inside_value": float(
            state.val_tick <= current_tick <= state.vah_tick),
        prefix + "range_position": float(np.clip(
            (current_tick - state.low_tick) / width, 0.0, 1.0)),
        prefix + "nearest_hvn_aligned_usd": distance(state.nearest_hvn_tick),
        prefix + "nearest_lvn_aligned_usd": distance(state.nearest_lvn_tick),
        prefix + "vwap_aligned_usd": float(
            side * (int(current_mid2) - 2.0 * state.vwap_tick * plane.raw_tick)
            * plane.factor),
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
    series = plane._profile_cache[max(0, int(start_sec))]
    for steps, label in ((1, "5m"), (3, "15m"), (6, "30m")):
        previous = ordinal - steps
        migration = 0.0
        if previous >= 0 and series[previous] is not None:
            migration = (side * (state.poc_tick - series[previous].poc_tick)
                         * plane.raw_tick * 1e-9 * plane.multiplier)
        values[prefix + f"poc_migration_{label}_aligned_usd"] = float(migration)
    left = max(state.boundary_sec, 0)
    mids = plane._last_mid[left:snapshot_sec]
    mids = mids[mids > 0]
    if len(mids):
        low2 = 2 * state.val_tick * plane.raw_tick
        high2 = 2 * state.vah_tick * plane.raw_tick
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
    tpo = _tpo_at(plane, start_sec, snapshot_sec)
    if tpo is not None:
        intersection = max(0, min(state.vah_tick, tpo.vah_tick)
                           - max(state.val_tick, tpo.val_tick) + 1)
        union = max(state.vah_tick, tpo.vah_tick) - min(
            state.val_tick, tpo.val_tick) + 1
        values.update({
            prefix + "tpo_present": 1.0,
            prefix + "tpo_poc_aligned_usd": distance(tpo.poc_tick),
            prefix + "tpo_value_width_usd": (
                (tpo.vah_tick - tpo.val_tick) * plane.raw_tick
                * 1e-9 * plane.multiplier),
            prefix + "vp_tpo_poc_disagreement_usd": (
                abs(state.poc_tick - tpo.poc_tick) * plane.raw_tick
                * 1e-9 * plane.multiplier),
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
    plane: CausalDiscretionaryPlane, *, prefix: str, start_sec: int, snapshot_sec: int,
    current_mid2: int, side: int,
) -> dict[str, float]:
    start = max(0, int(start_sec))
    ib_end = min(plane.duration, start + 3_600)
    right = min(int(snapshot_sec), ib_end)
    mids = plane._last_mid[start:right]
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
    range_usd = float((high - low) * plane.factor)
    post = plane._last_mid[ib_end:snapshot_sec] if snapshot_sec > ib_end else np.empty(0, np.int64)
    post = post[post > 0]
    directional_path = (side * (post - (high if side > 0 else low))
                        * plane.factor) if len(post) else np.empty(0, np.float64)
    opposing_path = (-side * (post - (low if side > 0 else high))
                     * plane.factor) if len(post) else np.empty(0, np.float64)
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
            side * (current - midpoint) * plane.factor),
        prefix + "high_aligned_usd": float(side * (current - high) * plane.factor),
        prefix + "low_aligned_usd": float(side * (current - low) * plane.factor),
        prefix + "inside": float(low <= current <= high),
        prefix + "directional_extension_usd": float(
            max(0.0, side * (current - (high if side > 0 else low)) * plane.factor)),
        prefix + "opposing_extension_usd": float(
            max(0.0, -side * (current - (low if side > 0 else high)) * plane.factor)),
        prefix + "directional_extension_over_range": float(
            max(0.0, side * (current - (high if side > 0 else low)) * plane.factor)
            / range_usd if range_usd > 0 else 0.0),
        prefix + "opposing_extension_over_range": float(
            max(0.0, -side * (current - (low if side > 0 else high)) * plane.factor)
            / range_usd if range_usd > 0 else 0.0),
        prefix + "directional_break_seen": float(len(directional_rows) > 0),
        prefix + "opposing_break_seen": float(np.any(opposing_path > 0)),
        prefix + "directional_break_age_sec": float(
            len(post) - 1 - directional_rows[0] if len(directional_rows) else 0.0),
        prefix + "directional_break_reentry_seen": float(directional_reentry),
    }
