#!/usr/bin/env python3
"""Event, trade, and volume clocks plus tape-slope maps."""

from __future__ import annotations

import math

import numpy as np

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .discretionary_features import CausalDiscretionaryPlane


def _slope(values: np.ndarray) -> float:
    array = np.asarray(values, np.float64)
    if len(array) < 2:
        return 0.0
    x = np.arange(len(array), dtype=np.float64)
    centered = x - float(x.mean())
    denominator = float(np.dot(centered, centered))
    return float(np.dot(centered, array - array.mean()) / denominator
                 if denominator > 0.0 else 0.0)

def _event_clock_map(
    plane: CausalDiscretionaryPlane, *, target_count: int, snapshot_ts_ns: int,
    formation_ts_ns: int, side: int,
) -> dict[str, float]:
    prefix = f"disc_eclock_n{target_count}_"
    right = int(np.searchsorted(
        plane._message_ts, snapshot_ts_ns, side="left"))
    left = max(0, right - int(target_count))
    ts = plane._message_ts[left:right]
    action = plane._message_action[left:right]
    event_side = plane._message_side[left:right]
    size = plane._message_size[left:right].astype(np.float64)
    econ = plane._message_economic[left:right]
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

    mids = plane._message_mid2[left:right][econ]
    if len(mids) >= 2:
        mid_delta = np.diff(mids).astype(np.float64)
        displacement = float(side * (mids[-1] - mids[0]) * plane.factor)
        variation = float(np.abs(mid_delta).sum() * plane.factor)
    else:
        displacement = variation = 0.0
    bid_size = plane._message_bid_sz[left:right][econ].astype(np.float64)
    ask_size = plane._message_ask_sz[left:right][econ].astype(np.float64)
    bid_count = plane._message_bid_ct[left:right][econ].astype(np.float64)
    ask_count = plane._message_ask_ct[left:right][econ].astype(np.float64)
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
        prefix + "aligned_size_imbalance_slope": _slope(size_imbalance),
        prefix + "aligned_count_imbalance_mean": mean(count_imbalance),
        prefix + "aligned_count_imbalance_slope": _slope(count_imbalance),
        prefix + "defense_average_order_size": mean(defense_average),
        prefix + "defense_average_order_size_slope": _slope(defense_average),
        prefix + "opposing_average_order_size": mean(opposing_average),
        prefix + "opposing_average_order_size_slope": _slope(opposing_average),
        prefix + "size_count_divergence": float(
            mean(size_imbalance) - mean(count_imbalance)),
        prefix + "economic_fraction": float(np.mean(econ) if count else 0.0),
    }

def _trade_slice_map(
    plane: CausalDiscretionaryPlane, *, prefix: str, left: int, right: int, support_fraction: float,
    snapshot_ts_ns: int, formation_ts_ns: int, side: int,
) -> dict[str, float]:
    ts = plane._trade_ts[left:right]
    signs = plane._trade_sign[left:right].astype(np.float64)
    sizes = plane._trade_exact_sizes[left:right].astype(np.float64)
    ticks = plane._trade_exact_ticks[left:right].astype(np.float64)
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
    plane: CausalDiscretionaryPlane, *, target_count: int, snapshot_ts_ns: int,
    formation_ts_ns: int, side: int,
) -> dict[str, float]:
    right = int(np.searchsorted(plane._trade_ts, snapshot_ts_ns, side="left"))
    left = max(0, right - int(target_count))
    return _trade_slice_map(plane,
        prefix=f"disc_tclock_n{target_count}_", left=left, right=right,
        support_fraction=(right - left) / float(target_count),
        snapshot_ts_ns=snapshot_ts_ns,
        formation_ts_ns=formation_ts_ns, side=side)

def _volume_clock_map(
    plane: CausalDiscretionaryPlane, *, target_volume: int, snapshot_ts_ns: int,
    formation_ts_ns: int, side: int,
) -> dict[str, float]:
    right = int(np.searchsorted(plane._trade_ts, snapshot_ts_ns, side="left"))
    available = int(plane._trade_volume_prefix[right])
    threshold = max(0, available - int(target_volume))
    left = max(0, int(np.searchsorted(
        plane._trade_volume_prefix, threshold, side="right")) - 1)
    selected_volume = int(
        plane._trade_volume_prefix[right] - plane._trade_volume_prefix[left])
    return _trade_slice_map(plane,
        prefix=f"disc_vclock_v{target_volume}_", left=left, right=right,
        support_fraction=min(1.0, selected_volume / float(target_volume)),
        snapshot_ts_ns=snapshot_ts_ns,
        formation_ts_ns=formation_ts_ns, side=side)

def _tape_slope_map(plane: CausalDiscretionaryPlane, *, snapshot_sec: int, side: int) -> dict[str, float]:
    output: dict[str, float] = {}
    for horizon in (30, 120):
        left = max(0, snapshot_sec - horizon)
        width = snapshot_sec - left
        prefix = f"disc_tape_h{horizon}_"
        output[prefix + "support_fraction"] = float(width / horizon)
        for name in ("event", "trade", "volume", "quote_churn"):
            series = plane._second_clock[name][left:snapshot_sec].astype(np.float64)
            half = len(series) // 2
            early = _slope(series[:half]) if half >= 2 else 0.0
            late = _slope(series[half:]) if len(series) - half >= 2 else 0.0
            output.update({
                prefix + name + "_mean_per_sec": float(
                    series.mean() if len(series) else 0.0),
                prefix + name + "_slope_per_sec2": _slope(series),
                prefix + name + "_slope_acceleration": float(late - early),
                prefix + name + "_active_second_fraction": float(
                    np.mean(series > 0) if len(series) else 0.0),
            })
        signed = (side * plane._second_clock["signed_volume"][
            left:snapshot_sec]).astype(np.float64)
        output.update({
            prefix + "aligned_flow_mean_per_sec": float(
                signed.mean() if len(signed) else 0.0),
            prefix + "aligned_flow_slope_per_sec2": _slope(signed),
        })
    return output

def _path_behavior_map(
    plane: CausalDiscretionaryPlane, values: dict[str, float], *,
    snapshot_ts_ns: int, current_mid2: int, formation_mid2: int,
    formation_ts_ns: int, side: int, event_prefixes: dict[int, str],
) -> None:
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

    state = plane._state_series(formation_ts_ns, formation_mid2, side)
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
                        * plane.factor)
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
