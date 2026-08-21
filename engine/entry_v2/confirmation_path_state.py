"""Causal candidate-path states for delayed Entry V2 acceptance.

The fixed-watch acceptance heads saw one absolute snapshot per candidate.  A
snapshot cannot distinguish favorable follow-through, fast adverse
continuation, and a slow adverse move that is stabilising.  This module turns
the already materialised one-second/event-derived path into explicit causal
geometry at fixed landmarks.  It never reads a row after the landmark.

The target is the signed best value over rows with a complete fixed-horizon
future.  It preserves the difference between a candidate whose best delayed
entry is -$20 and one whose best is -$905.  Clipping both to the value of
passing creates a large artificial label plateau and makes acceptance losses
unlearnable.  Only genuinely truncated paths are right-censored.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Final, Mapping, Sequence

import numpy as np

from . import common as C
from .confirmation import ConfirmationDataset, ConfirmationRefusal
from .confirmation_fixed_horizon import (
    FixedHorizonTarget, fixed_horizon_target, ordered_series_groups,
)
from .confirmation_stopping import OracleActionLedger


SCHEMA: Final = "QRE2CONFPATHSTATE1"

# These are exact per-second increments.  Aggregating their candidate-local
# sequence retains ordering and speed that an absolute landmark snapshot loses.
INCREMENT_SIGNALS: Final = (
    "w1_event_count",
    "w1_trade_count",
    "w1_trade_volume",
    "w1_aligned_trade_flow",
    "w1_aligned_defense",
    "w1_opposing_retreat",
    "w1_spread_widen_minus_narrow",
)

# These are state variables whose change, slope, extrema and recovery matter.
STATE_SIGNALS: Final = (
    "disc_state_current_displacement_ticks",
    "current_spread_usd",
    "current_size_imbalance",
    "disc_behavior_control_evidence_balance",
    "disc_state_price_yield_per_attack",
    "disc_absorption_attack_per_adverse_tick",
    "disc_absorption_reload_per_attack",
    "disc_mhi_attack_exhaustion_5_vs_30",
    "disc_mhi_lift_acceleration_5_vs_30",
)

WINDOWS_SEC: Final = (5, 10, 30, 60)


@dataclass(frozen=True, slots=True)
class DelayedCandidateValueTarget:
    value_usd: np.ndarray
    observed: np.ndarray
    best_snapshot_ts_ns: np.ndarray
    horizon_sec: int

    def validate(self, dataset: ConfirmationDataset) -> None:
        n = len(dataset.features)
        value = np.asarray(self.value_usd, np.float64)
        observed = np.asarray(self.observed, bool)
        timestamp = np.asarray(self.best_snapshot_ts_ns, np.int64)
        if (value.shape != (n,) or observed.shape != (n,)
                or timestamp.shape != (n,) or not observed.any()
                or not 0 < self.horizon_sec <= 240
                or not np.all(np.isfinite(value[observed]))
                or np.any(np.isfinite(value[~observed]))
                or np.any(timestamp[observed] < 0)
                or np.any(timestamp[~observed] != -1)):
            raise ConfirmationRefusal("delayed candidate-value target differs")


@dataclass(frozen=True, slots=True)
class PathStateLandmark:
    """One observed row and one causal path-state vector per candidate."""

    dataset: ConfirmationDataset
    target: DelayedCandidateValueTarget
    matrix: np.ndarray
    feature_names: tuple[str, ...]
    source_row: np.ndarray
    landmark_delay_sec: int
    watch_age_sec: int

    def validate(self, source: ConfirmationDataset) -> None:
        self.dataset.validate(); self.target.validate(self.dataset)
        matrix = np.asarray(self.matrix, np.float64)
        rows = np.asarray(self.source_row, np.int64)
        n = len(self.dataset.features)
        if (matrix.shape != (n, len(self.feature_names))
                or rows.shape != (n,) or not len(self.feature_names)
                or len(set(self.feature_names)) != len(self.feature_names)
                or not np.all(np.isfinite(matrix))
                or np.any(rows < 0) or np.any(rows >= len(source.features))
                or not np.all(np.diff(rows) > 0)
                or not np.array_equal(
                    self.dataset.opportunity_id, source.opportunity_id[rows])
                or not np.array_equal(
                    self.dataset.snapshot_ts_ns, source.snapshot_ts_ns[rows])
                or not 0 <= self.watch_age_sec < 300
                or not 0 <= self.landmark_delay_sec <= 240
                or not np.all(self.target.observed)):
            raise ConfirmationRefusal("path-state landmark identity differs")

    @property
    def representation_sha256(self) -> str:
        # The caller's source identity is already bound by dataset receipts;
        # hash the derived payload and semantic roster here.
        return C.object_sha256({
            "schema": SCHEMA,
            "dataset_sha256": self.dataset.representation_sha256,
            "target_horizon_sec": self.target.horizon_sec,
            "feature_names": self.feature_names,
            "matrix_sha256": _array_sha256(np.asarray(
                self.matrix, np.float64)),
            "source_row_sha256": _array_sha256(np.asarray(
                self.source_row, np.int64)),
            "landmark_delay_sec": self.landmark_delay_sec,
            "watch_age_sec": self.watch_age_sec,
        })


def _array_sha256(value: np.ndarray) -> str:
    array = np.ascontiguousarray(value)
    digest = hashlib.sha256()
    digest.update(str(array.dtype).encode())
    digest.update(repr(array.shape).encode())
    digest.update(array.tobytes())
    return digest.hexdigest()


def _column_lookup(dataset: ConfirmationDataset) -> Mapping[str, int]:
    lookup = {name: index for index, name in enumerate(dataset.feature_names)}
    required = set(INCREMENT_SIGNALS) | set(STATE_SIGNALS)
    missing = sorted(required - set(lookup))
    if missing:
        raise ConfirmationRefusal(
            f"path-state source features are absent: {missing}")
    return lookup


def _slope(values: np.ndarray) -> float:
    y = np.asarray(values, np.float64)
    if len(y) < 2:
        return 0.0
    x = np.arange(len(y), dtype=np.float64)
    x -= np.mean(x); y = y - np.mean(y)
    denominator = float(np.dot(x, x))
    return 0.0 if denominator <= 0 else float(np.dot(x, y) / denominator)


def _window(values: np.ndarray, timestamps: np.ndarray, seconds: int) \
        -> np.ndarray:
    cutoff = int(timestamps[-1]) - int(seconds) * 1_000_000_000
    return np.asarray(values[np.asarray(timestamps) > cutoff], np.float64)


def _safe_ratio(numerator: float, denominator: float) -> float:
    return float(numerator / (1.0 + abs(denominator)))


def path_state_feature_names() -> tuple[str, ...]:
    names: list[str] = [
        "pathstate_asset_SI", "pathstate_asset_HG", "pathstate_asset_NKD",
        "pathstate_side", "pathstate_phase_index",
        "pathstate_landmark_delay_sec",
    ]
    names.extend((
        "pathstate_disp_current", "pathstate_disp_from_watch",
        "pathstate_disp_path_min", "pathstate_disp_path_max",
        "pathstate_disp_path_range", "pathstate_disp_recovery_from_min",
        "pathstate_disp_pullback_from_max", "pathstate_disp_total_variation",
        "pathstate_disp_efficiency", "pathstate_disp_positive_fraction",
        "pathstate_disp_negative_fraction", "pathstate_disp_zero_crossings",
        "pathstate_disp_seconds_since_min", "pathstate_disp_seconds_since_max",
    ))
    for seconds in WINDOWS_SEC:
        names.extend((
            f"pathstate_disp_h{seconds}_delta",
            f"pathstate_disp_h{seconds}_velocity",
            f"pathstate_disp_h{seconds}_slope",
            f"pathstate_disp_h{seconds}_variation",
            f"pathstate_disp_h{seconds}_efficiency",
        ))
    for signal in INCREMENT_SIGNALS:
        short = signal.removeprefix("w1_")
        names.extend((
            f"pathstate_inc_{short}_cumulative_sum",
            f"pathstate_inc_{short}_cumulative_mean",
        ))
        for seconds in WINDOWS_SEC:
            names.extend((
                f"pathstate_inc_{short}_h{seconds}_sum",
                f"pathstate_inc_{short}_h{seconds}_mean",
                f"pathstate_inc_{short}_h{seconds}_slope",
                f"pathstate_inc_{short}_h{seconds}_max_abs",
            ))
        names.extend((
            f"pathstate_inc_{short}_recent5_minus_prior10",
            f"pathstate_inc_{short}_recent10_minus_prior20",
        ))
    for signal in STATE_SIGNALS[1:]:
        short = signal.removeprefix("disc_").removeprefix("current_")
        names.extend((
            f"pathstate_level_{short}_current",
            f"pathstate_level_{short}_from_watch",
            f"pathstate_level_{short}_path_min",
            f"pathstate_level_{short}_path_max",
            f"pathstate_level_{short}_path_range",
        ))
        for seconds in WINDOWS_SEC:
            names.extend((
                f"pathstate_level_{short}_h{seconds}_delta",
                f"pathstate_level_{short}_h{seconds}_slope",
                f"pathstate_level_{short}_h{seconds}_mean",
            ))
    names.extend((
        "pathstate_interaction_momentum_flow_5",
        "pathstate_interaction_momentum_flow_10",
        "pathstate_interaction_fast_adverse_continuation",
        "pathstate_interaction_adverse_activity_shock",
        "pathstate_interaction_adverse_volume_shock",
        "pathstate_interaction_slow_fade_stabilisation",
        "pathstate_interaction_recovery_under_adverse_flow",
        "pathstate_interaction_defended_recovery",
        "pathstate_interaction_absorption_no_extension",
        "pathstate_interaction_favorable_price_yield",
        "pathstate_interaction_adverse_price_yield",
        "pathstate_interaction_sparse_tape_stabilisation",
    ))
    return tuple(names)


def _recent_prior(values: np.ndarray, recent: int, prior: int) \
        -> tuple[float, float]:
    source = np.asarray(values, np.float64)
    recent_values = source[-recent:]
    prior_values = source[max(0, len(source) - recent - prior):
                          max(0, len(source) - recent)]
    recent_mean = float(np.mean(recent_values)) if len(recent_values) else 0.0
    prior_mean = float(np.mean(prior_values)) if len(prior_values) else 0.0
    return recent_mean, prior_mean


def _path_vector(
    dataset: ConfirmationDataset, ordered_prefix: np.ndarray,
    lookup: Mapping[str, int], *, landmark_delay_sec: int,
) -> np.ndarray:
    rows = np.asarray(ordered_prefix, np.int64)
    timestamps = np.asarray(dataset.snapshot_ts_ns[rows], np.int64)
    x = np.asarray(dataset.features[rows], np.float64)
    asset = str(dataset.asset[rows[-1]])
    phase = str(dataset.phase[rows[-1]])
    try:
        phase_index = float(phase)
    except ValueError:
        phase_index = float(lookup.get(f"phase_{phase}", 0))
    result: list[float] = [
        float(asset == "SI"), float(asset == "HG"), float(asset == "NKD"),
        float(dataset.side[rows[-1]]), phase_index, float(landmark_delay_sec),
    ]

    displacement = x[:, lookup[STATE_SIGNALS[0]]]
    current = float(displacement[-1]); watch = float(displacement[0])
    relative = displacement - watch
    differences = np.diff(relative)
    total_variation = float(np.sum(np.abs(differences)))
    minimum_position = int(np.argmin(relative))
    maximum_position = int(np.argmax(relative))
    result.extend((
        current, current - watch, float(np.min(relative)),
        float(np.max(relative)), float(np.ptp(relative)),
        float(relative[-1] - np.min(relative)),
        float(relative[-1] - np.max(relative)), total_variation,
        _safe_ratio(float(abs(relative[-1])), total_variation),
        float(np.mean(relative > 0.0)), float(np.mean(relative < 0.0)),
        float(np.sum(np.signbit(relative[1:]) != np.signbit(relative[:-1]))),
        float((timestamps[-1] - timestamps[minimum_position]) / 1e9),
        float((timestamps[-1] - timestamps[maximum_position]) / 1e9),
    ))
    for seconds in WINDOWS_SEC:
        local = _window(displacement, timestamps, seconds)
        delta = float(local[-1] - local[0]) if len(local) > 1 else 0.0
        variation = float(np.sum(np.abs(np.diff(local))))
        result.extend((
            delta, delta / max(1.0, float(len(local) - 1)), _slope(local),
            variation, _safe_ratio(abs(delta), variation),
        ))

    increment_sequences: dict[str, np.ndarray] = {}
    for signal in INCREMENT_SIGNALS:
        values = x[:, lookup[signal]]
        increment_sequences[signal] = values
        result.extend((float(np.sum(values)), float(np.mean(values))))
        for seconds in WINDOWS_SEC:
            local = _window(values, timestamps, seconds)
            result.extend((
                float(np.sum(local)), float(np.mean(local)), _slope(local),
                float(np.max(np.abs(local))),
            ))
        recent5, prior10 = _recent_prior(values, 5, 10)
        recent10, prior20 = _recent_prior(values, 10, 20)
        result.extend((recent5 - prior10, recent10 - prior20))

    for signal in STATE_SIGNALS[1:]:
        values = x[:, lookup[signal]]
        if signal == "current_size_imbalance":
            values = values * float(dataset.side[rows[-1]])
        result.extend((
            float(values[-1]), float(values[-1] - values[0]),
            float(np.min(values)), float(np.max(values)), float(np.ptp(values)),
        ))
        for seconds in WINDOWS_SEC:
            local = _window(values, timestamps, seconds)
            result.extend((
                float(local[-1] - local[0]) if len(local) > 1 else 0.0,
                _slope(local), float(np.mean(local)),
            ))

    def inc_sum(name: str, seconds: int) -> float:
        return float(np.sum(_window(
            increment_sequences[name], timestamps, seconds)))

    disp5 = float(_window(displacement, timestamps, 5)[-1]
                  - _window(displacement, timestamps, 5)[0])
    disp10_values = _window(displacement, timestamps, 10)
    disp10 = float(disp10_values[-1] - disp10_values[0])
    disp30_values = _window(displacement, timestamps, 30)
    disp30 = float(disp30_values[-1] - disp30_values[0])
    flow5 = inc_sum("w1_aligned_trade_flow", 5)
    flow10 = inc_sum("w1_aligned_trade_flow", 10)
    adverse_flow10 = max(0.0, -flow10)
    favorable_flow10 = max(0.0, flow10)
    event5 = inc_sum("w1_event_count", 5)
    event30 = inc_sum("w1_event_count", 30)
    volume5 = inc_sum("w1_trade_volume", 5)
    volume30 = inc_sum("w1_trade_volume", 30)
    defense10 = inc_sum("w1_aligned_defense", 10)
    recent_velocity = disp5 / 5.0
    prior_velocity = (disp30 - disp10) / 20.0
    acceleration = recent_velocity - prior_velocity
    adverse_depth = max(0.0, -float(relative[-1]))
    recovery = max(0.0, float(relative[-1] - np.min(relative)))
    event_shock = _safe_ratio(event5 / 5.0 - event30 / 30.0,
                              event30 / 30.0)
    volume_shock = _safe_ratio(volume5 / 5.0 - volume30 / 30.0,
                               volume30 / 30.0)
    result.extend((
        disp5 * flow5,
        disp10 * flow10,
        max(0.0, -disp5) * adverse_flow10,
        max(0.0, -disp5) * max(0.0, event_shock),
        max(0.0, -disp5) * max(0.0, volume_shock),
        adverse_depth * max(0.0, acceleration),
        recovery * adverse_flow10,
        recovery * max(0.0, defense10),
        _safe_ratio(adverse_flow10, max(0.0, -disp10)),
        _safe_ratio(max(0.0, disp10), favorable_flow10),
        _safe_ratio(max(0.0, -disp10), adverse_flow10),
        adverse_depth * max(0.0, acceleration)
        / (1.0 + max(0.0, event30 / 30.0)),
    ))
    values = np.asarray(result, np.float64)
    if (values.shape != (len(path_state_feature_names()),)
            or not np.all(np.isfinite(values))):
        raise ConfirmationRefusal("path-state vector schema differs")
    return values


def build_path_state_landmark(
    dataset: ConfirmationDataset, ledger: OracleActionLedger, *,
    landmark_delay_sec: int, horizon_sec: int = 120,
    watch_age_sec: int = 30,
) -> PathStateLandmark:
    """Build a signed target and causal state at one landmark."""

    dataset.validate(); ledger.validate()
    if (ledger.source_representation_sha256 != dataset.representation_sha256
            or not np.array_equal(ledger.opportunity_id,
                                  dataset.opportunity_id)
            or not 0 <= landmark_delay_sec <= 240):
        raise ConfirmationRefusal("path-state source identity differs")
    lookup = _column_lookup(dataset)
    horizon: FixedHorizonTarget = fixed_horizon_target(
        dataset, ledger, int(horizon_sec))
    series = np.asarray(dataset.series_id, str)
    timestamp = np.asarray(dataset.snapshot_ts_ns, np.int64)
    q_enter = np.asarray(ledger.q_enter_usd, np.float64)
    source_rows: list[int] = []
    values: list[float] = []
    best_timestamps: list[int] = []
    vectors: list[np.ndarray] = []
    for ordered in ordered_series_groups(series, timestamp):
        times = timestamp[ordered]
        first_age = float(dataset.min_alert_age_sec[ordered[0]])
        if not watch_age_sec <= first_age < watch_age_sec + 1:
            raise ConfirmationRefusal("path-state watch anchor differs")
        landmark_ts = int(times[0]) + int(landmark_delay_sec) * 1_000_000_000
        position = np.flatnonzero(times == landmark_ts)
        if len(position) != 1:
            continue
        landmark_position = int(position[0])
        candidate_actions = ordered[
            (times >= landmark_ts) & np.asarray(horizon.eligible[ordered], bool)]
        if not len(candidate_actions):
            # No fully observed action remains; this is censoring, not a zero.
            continue
        chosen = int(candidate_actions[int(np.argmax(
            q_enter[candidate_actions]))])
        value = float(q_enter[chosen])
        best_timestamp = int(timestamp[chosen])
        row = int(ordered[landmark_position])
        source_rows.append(row); values.append(value)
        best_timestamps.append(best_timestamp)
        vectors.append(_path_vector(
            dataset, ordered[:landmark_position + 1], lookup,
            landmark_delay_sec=int(landmark_delay_sec)))
    if not source_rows:
        raise ConfirmationRefusal("path-state landmark is empty")
    order = np.argsort(np.asarray(source_rows), kind="stable")
    rows = np.asarray(source_rows, np.int64)[order]
    matrix = np.vstack(vectors)[order]
    target_value = np.asarray(values, np.float64)[order]
    best_timestamp = np.asarray(best_timestamps, np.int64)[order]
    mask = np.zeros(len(dataset.features), bool); mask[rows] = True
    landmark_dataset = dataset.subset(mask)
    target = DelayedCandidateValueTarget(
        value_usd=target_value,
        observed=np.ones(len(rows), bool),
        best_snapshot_ts_ns=best_timestamp,
        horizon_sec=int(horizon_sec))
    result = PathStateLandmark(
        dataset=landmark_dataset, target=target, matrix=matrix,
        feature_names=path_state_feature_names(), source_row=rows,
        landmark_delay_sec=int(landmark_delay_sec),
        watch_age_sec=int(watch_age_sec))
    result.validate(dataset)
    return result


__all__ = [
    "SCHEMA", "INCREMENT_SIGNALS", "STATE_SIGNALS", "WINDOWS_SEC",
    "DelayedCandidateValueTarget", "PathStateLandmark",
    "build_path_state_landmark",
    "path_state_feature_names",
]
