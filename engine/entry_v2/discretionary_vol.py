#!/usr/bin/env python3
"""Forward-vol, regime, target-room, and origin-reaction maps."""

from __future__ import annotations

import math
from typing import Mapping

import numpy as np

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .discretionary_features import CausalDiscretionaryPlane

from .discretionary_profile import _profile_at
from .discretionary_tape import _slope
from .discretionary_tape_events import _event_streams


def _forward_vol_map(
    plane: CausalDiscretionaryPlane, *, formation_candidate: Mapping[str, object],
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
                    - plane.open_ns // 1_000_000_000)
            except (TypeError, ValueError):
                close_sec = snapshot_sec
        else:
            close_sec = plane.duration
        remaining_sec = max(0, close_sec - snapshot_sec)
        mids = plane._last_mid[max(0, start):snapshot_sec]
        mids = mids[mids > 0]
        actual_range = (0.0 if not len(mids) else
                        float((mids.max() - mids.min()) * plane.factor))
        aligned_displacement = float(
            side * (int(current_mid2) - int(formation_mid2)) * plane.factor)
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
    plane: CausalDiscretionaryPlane, *, snapshot_sec: int, current_mid2: int, side: int,
) -> dict[str, float]:
    values: dict[str, float] = {}
    for horizon in (60, 300, 1800):
        mids = plane._last_mid[max(0, snapshot_sec - horizon):snapshot_sec]
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
        displacement = float((mids[-1] - mids[0]) * plane.factor)
        variation = float(np.abs(delta).sum(dtype=np.int64) * plane.factor)
        span = float((mids.max() - mids.min()) * plane.factor)
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
    plane: CausalDiscretionaryPlane, *, snapshot_sec: int, current_mid2: int, side: int,
    phase_open_sec: int, atr_usd: float,
) -> dict[str, float]:
    levels: list[float] = []
    for start in (0, phase_open_sec):
        state, _ordinal = _profile_at(plane, start, snapshot_sec)
        if state is not None:
            levels.extend((
                state.low_tick, state.val_tick, state.poc_tick,
                state.vah_tick, state.high_tick,
                state.nearest_hvn_tick, state.nearest_lvn_tick))
    prior = plane.prior_session
    if prior is not None:
        levels.extend((
            prior.low_mid2 / (2.0 * plane.raw_tick),
            prior.close_mid2 / (2.0 * plane.raw_tick),
            prior.high_mid2 / (2.0 * plane.raw_tick),
        ))
        if prior.profile is not None:
            levels.extend((
                prior.profile.low_tick, prior.profile.val_tick,
                prior.profile.poc_tick, prior.profile.vah_tick,
                prior.profile.high_tick, prior.profile.nearest_hvn_tick,
                prior.profile.nearest_lvn_tick,
            ))
    current_tick = float(current_mid2) / (2.0 * plane.raw_tick)
    unit = plane.raw_tick * 1e-9 * plane.multiplier
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
    plane: CausalDiscretionaryPlane, *, formation_tick: int, formation_ts_ns: int,
    side: int,
) -> dict[str, float]:
    stream = _event_streams(plane,
        center_tick=formation_tick, radius=2,
        left_ns=plane.open_ns, right_ns=formation_ts_ns, side=side)
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
                plane._economic_ts, timestamp, side="left"))
            right = int(np.searchsorted(
                plane._economic_ts,
                timestamp + horizon * 1_000_000_000, side="left"))
            if left >= right:
                continue
            base_index = max(0, left - 1)
            base = int(plane._economic_mid2[base_index])
            path = (side * (plane._economic_mid2[left:right] - base)
                    * plane.factor)
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
            prefix + "favorable_slope_usd": _slope(
                np.asarray(favorable, np.float64)),
            prefix + "adverse_mean_usd": float(
                np.mean(adverse) if adverse else 0.0),
            prefix + "adverse_first_usd": float(
                adverse[0] if adverse else 0.0),
            prefix + "adverse_last_usd": float(
                adverse[-1] if adverse else 0.0),
            prefix + "adverse_slope_usd": _slope(
                np.asarray(adverse, np.float64)),
            prefix + "response_decay_usd": float(
                favorable[-1] - favorable[0] if favorable else 0.0),
            prefix + "defense_rate": float(
                np.mean(np.asarray(favorable) > np.asarray(adverse))
                if favorable else 0.0),
            prefix + "large_origin_count": float(
                np.sum(np.asarray(favorable) >= 4.0 * plane.raw_tick
                       * 1e-9 * plane.multiplier) if favorable else 0.0),
        })
    return values
