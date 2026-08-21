"""Horizon-clean, group-relative diagnostics for confirmation stopping.

The retired direct-utility target compared ``Q_enter`` with the best value at
*any* later cached row.  That makes the amount of future available to the
target shrink mechanically near cache expiry.  This module replaces that
variable horizon with an exact fixed future window and refuses right-censored
rows.  It also represents every dynamic feature as a change from the same
candidate's watch row and evaluates signal within candidate paths.

This is a mechanism audit, not a learner and not launch evidence.  It answers
two cheaper questions before another fit is allowed:

* can a fixed-horizon stopping rule express enough of the roster ceiling; and
* do causal watch-relative feature directions survive chronological FIT
  blocks and transfer to PLATT beyond within-path null controls?
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final, Mapping, Sequence

import numpy as np

from . import common as C
from .confirmation import ConfirmationDataset, ConfirmationRefusal
from .confirmation_direct_utility_policy import _first_triggers
from .confirmation_dynamic_hurdle_policy import (
    _arrival, _evaluation_summary, _sparse_schedule_ceiling,
)
from .confirmation_stopping import OracleActionLedger
from .contracts import SessionRef
from .replay import replay


SCHEMA: Final = "QRE2CONFFIXEDHORIZON1"
FEATURE_PREFIXES: Final = (
    "current_", "aligned_from_formation_",
    "w1_", "w5_", "w15_", "w30_", "w60_", "w120_", "w300_",
    "disc_current_", "disc_state_", "disc_evt_", "disc_eclock_",
    "disc_tclock_", "disc_vclock_", "disc_tape_", "disc_test_",
    "disc_quote_", "disc_behavior_", "disc_ib_", "disc_footprint_",
    "disc_mhi_", "disc_absorption_", "disc_path_", "disc_memory_",
    "disc_fvol_", "disc_regime_", "disc_level_",
)
CONTROL_KINDS: Final = (
    "WITHIN_SERIES_PERMUTATION", "WITHIN_SERIES_CIRCULAR_SHIFT",
)


@dataclass(frozen=True, slots=True)
class FixedHorizonConfig:
    watch_age_sec: int = 30
    capacity: int = 12
    horizons_sec: tuple[int, ...] = (60, 120)
    chronological_blocks: int = 3
    minimum_dynamic_series_fraction: float = .10
    stability_floors: tuple[float, ...] = (
        .005, .01, .015, .02, .03, .05,
    )
    strict_stability_floor: float = .05
    maximum_selected_features: int = 48
    control_replicates: int = 4
    control_seed: int = 20260820
    value_thresholds_usd: tuple[float, ...] = (.01, 100.0, 300.0, 600.0)
    regret_thresholds_usd: tuple[float, ...] = (0.0, 12.5, 25.0, 50.0)
    minimum_oracle_capture: float = .80
    minimum_platt_path_spearman: float = .10
    minimum_platt_positive_path_fraction: float = .65

    def __post_init__(self) -> None:
        horizons = tuple(map(int, self.horizons_sec))
        floors = tuple(map(float, self.stability_floors))
        values = tuple(map(float, self.value_thresholds_usd))
        regrets = tuple(map(float, self.regret_thresholds_usd))
        if (not 0 <= self.watch_age_sec < 300
                or not 1 <= self.capacity <= 12
                or horizons != tuple(sorted(set(horizons)))
                or not horizons or horizons[0] <= 0 or horizons[-1] > 240
                or not 2 <= self.chronological_blocks <= 6
                or not 0 < self.minimum_dynamic_series_fraction <= 1
                or floors != tuple(sorted(set(floors))) or not floors
                or floors[0] <= 0 or floors[-1] >= 1
                or self.strict_stability_floor not in floors
                or not 1 <= self.maximum_selected_features <= 128
                or not 1 <= self.control_replicates <= 16
                or values != tuple(sorted(set(values))) or not values
                or values[0] <= 0
                or regrets != tuple(sorted(set(regrets))) or not regrets
                or regrets[0] != 0.0
                or not 0 < self.minimum_oracle_capture <= 1
                or not -1 <= self.minimum_platt_path_spearman <= 1
                or not 0 <= self.minimum_platt_positive_path_fraction <= 1):
            raise ConfirmationRefusal("fixed-horizon configuration is invalid")

    @property
    def receipt_sha256(self) -> str:
        return C.object_sha256({"schema": SCHEMA, **asdict(self)})


@dataclass(frozen=True, slots=True)
class FixedHorizonTarget:
    horizon_sec: int
    stop_utility_usd: np.ndarray
    future_best_q_enter_usd: np.ndarray
    eligible: np.ndarray
    terminal_row: np.ndarray

    def validate(self, dataset: ConfirmationDataset,
                 ledger: OracleActionLedger) -> None:
        n = len(dataset.features)
        if (not 0 < self.horizon_sec <= 240
                or np.asarray(self.stop_utility_usd).shape != (n,)
                or np.asarray(self.future_best_q_enter_usd).shape != (n,)
                or np.asarray(self.eligible).shape != (n,)
                or np.asarray(self.terminal_row).shape != (n,)):
            raise ConfirmationRefusal("fixed-horizon target schema differs")
        eligible = np.asarray(self.eligible, bool)
        terminal = np.asarray(self.terminal_row, bool)
        stop = np.asarray(self.stop_utility_usd, np.float64)
        future = np.asarray(self.future_best_q_enter_usd, np.float64)
        q_enter = np.asarray(ledger.q_enter_usd, np.float64)
        if (not eligible.any() or not terminal.any()
                or np.any(eligible & terminal)
                or not np.all(np.isfinite(stop[eligible]))
                or not np.all(np.isfinite(future[eligible]))
                or not np.allclose(
                    stop[eligible], q_enter[eligible] - future[eligible],
                    atol=1e-7, rtol=0)
                or np.any(np.isfinite(stop[~eligible]))
                or np.any(np.isfinite(future[~eligible]))):
            raise ConfirmationRefusal("fixed-horizon target identities differ")


def ordered_series_groups(
    series_id: np.ndarray, timestamp_ns: np.ndarray,
) -> tuple[np.ndarray, ...]:
    """Group once in O(n log n), rather than rescanning n rows per series."""

    series = np.asarray(series_id, str)
    timestamp = np.asarray(timestamp_ns, np.int64)
    if series.ndim != 1 or timestamp.shape != series.shape or not len(series):
        raise ConfirmationRefusal("fixed-horizon series grouping differs")
    order = np.lexsort((timestamp, series))
    ordered_series = series[order]
    boundaries = np.r_[0, np.flatnonzero(
        ordered_series[1:] != ordered_series[:-1]) + 1, len(order)]
    groups = tuple(order[left:right]
                   for left, right in zip(boundaries[:-1], boundaries[1:]))
    if (sum(len(group) for group in groups) != len(series)
            or len(groups) != len(set(series.tolist()))):
        raise ConfirmationRefusal("fixed-horizon series grouping lost rows")
    return groups


def _validate_pair(
    dataset: ConfirmationDataset, ledger: OracleActionLedger,
    *, watch_age_sec: int,
) -> None:
    dataset.validate(); ledger.validate()
    if (ledger.source_representation_sha256
            != dataset.representation_sha256
            or not np.array_equal(dataset.opportunity_id,
                                  ledger.opportunity_id)
            or not np.array_equal(dataset.series_id, ledger.series_id)
            or not np.array_equal(dataset.snapshot_ts_ns,
                                  ledger.snapshot_ts_ns)):
        raise ConfirmationRefusal("fixed-horizon dataset/ledger identity differs")
    series = np.asarray(dataset.series_id, str)
    timestamps = np.asarray(dataset.snapshot_ts_ns, np.int64)
    # A series may merge overlapping alerts.  The watch anchor is the newest
    # constituent alert (minimum age); max age belongs to an older alert and
    # is not the candidate's watch clock.
    ages = np.asarray(dataset.min_alert_age_sec, np.float64)
    for ordered in ordered_series_groups(series, timestamps):
        # Snapshots are whole receive-second boundaries while alert creation
        # is subsecond.  An exact 30-second watch therefore has an observed
        # alert age in [30, 31), not necessarily the float 30.0.
        first_age = float(ages[ordered[0]])
        if (np.any(np.diff(timestamps[ordered]) <= 0)
                or not watch_age_sec <= first_age < watch_age_sec + 1):
            raise ConfirmationRefusal(
                "fixed-horizon path does not start at exact watch state")


def fixed_horizon_target(
    dataset: ConfirmationDataset, ledger: OracleActionLedger,
    horizon_sec: int,
) -> FixedHorizonTarget:
    """Return exact-window stop utility and refuse implicit tail padding.

    A row is eligible only when the path contains an observation exactly at
    ``now + horizon``.  The future maximum uses strictly later rows no farther
    than that endpoint.  Every other row is explicitly right-censored.
    """

    _validate_pair(dataset, ledger, watch_age_sec=int(
        np.floor(float(np.min(dataset.min_alert_age_sec)))))
    horizon = int(horizon_sec)
    if not 0 < horizon <= 240:
        raise ConfirmationRefusal("fixed horizon is invalid")
    n = len(dataset.features)
    stop = np.full(n, np.nan, np.float64)
    future = np.full(n, np.nan, np.float64)
    eligible = np.zeros(n, bool)
    terminal = np.zeros(n, bool)
    series = np.asarray(dataset.series_id, str)
    timestamp = np.asarray(dataset.snapshot_ts_ns, np.int64)
    q_enter = np.asarray(ledger.q_enter_usd, np.float64)
    horizon_ns = horizon * 1_000_000_000
    for ordered in ordered_series_groups(series, timestamp):
        times = timestamp[ordered]
        terminal[ordered[-1]] = True
        for position, row in enumerate(ordered[:-1]):
            endpoint = times[position] + horizon_ns
            if not np.any(times == endpoint):
                continue
            future_local = np.flatnonzero(
                (times > times[position]) & (times <= endpoint))
            if not len(future_local):
                raise ConfirmationRefusal("fixed horizon has no future rows")
            best = float(np.max(q_enter[ordered[future_local]]))
            future[row] = best
            stop[row] = float(q_enter[row] - best)
            eligible[row] = True
    result = FixedHorizonTarget(
        horizon_sec=horizon, stop_utility_usd=stop,
        future_best_q_enter_usd=future, eligible=eligible,
        terminal_row=terminal)
    result.validate(dataset, ledger)
    return result


def eligible_feature_indices(
    feature_names: Sequence[str],
) -> np.ndarray:
    """Causal dynamic families, excluding global age/macro shortcuts."""

    names = tuple(map(str, feature_names))
    selected = np.asarray([
        index for index, name in enumerate(names)
        if name.startswith(FEATURE_PREFIXES)
    ], np.int64)
    if (not len(selected)
            or any(names[index] in {"min_alert_age_sec", "max_alert_age_sec"}
                   for index in selected)
            or any(names[index].startswith(("ctx_", "disc_auction_"))
                   for index in selected)):
        raise ConfirmationRefusal("fixed-horizon feature allowlist differs")
    return selected


def watch_relative_matrix(
    dataset: ConfirmationDataset, feature_indices: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Subtract each candidate's first observed watch state from later rows."""

    selected = np.asarray(feature_indices, np.int64)
    if (selected.ndim != 1 or not len(selected)
            or np.any(selected < 0)
            or np.any(selected >= len(dataset.feature_names))):
        raise ConfirmationRefusal("watch-relative feature indices differ")
    matrix = np.asarray(dataset.features[:, selected], np.float32)
    result = np.empty_like(matrix)
    dynamic_count = np.zeros(len(selected), np.int64)
    series = np.asarray(dataset.series_id, str)
    timestamp = np.asarray(dataset.snapshot_ts_ns, np.int64)
    groups = ordered_series_groups(series, timestamp)
    for ordered in groups:
        baseline = matrix[ordered[0]]
        result[ordered] = matrix[ordered] - baseline
        dynamic_count += np.ptp(matrix[ordered], axis=0) > 1e-7
    if not np.all(result[np.asarray(
            [ordered[0] for ordered in groups], np.int64)] == 0):
        raise ConfirmationRefusal("watch-relative baseline is not zero")
    return result, dynamic_count.astype(np.float64) / len(groups)


def shuffle_within_series(
    target: np.ndarray, eligible: np.ndarray, series_id: np.ndarray, *,
    seed: int, kind: str,
) -> np.ndarray:
    """Destroy recipient timing while preserving each path's target multiset."""

    values = np.asarray(target, np.float64)
    mask = np.asarray(eligible, bool)
    series = np.asarray(series_id, str)
    if (values.shape != mask.shape or values.shape != series.shape
            or kind not in CONTROL_KINDS):
        raise ConfirmationRefusal("fixed-horizon control inputs differ")
    result = values.copy(); rng = np.random.default_rng(int(seed))
    changed = 0
    for key in sorted(set(series[mask].tolist())):
        local = np.flatnonzero(mask & (series == key))
        original = values[local]
        if kind == "WITHIN_SERIES_PERMUTATION":
            donor = original[rng.permutation(len(local))]
        else:
            offset = int(rng.integers(1, len(local)))
            donor = np.roll(original, offset)
        result[local] = donor
        if not np.array_equal(np.sort(original), np.sort(donor)):
            raise ConfirmationRefusal("within-series control changed target mass")
        changed += int(np.sum(original != donor))
    if changed == 0:
        raise ConfirmationRefusal("within-series control changed no recipients")
    return result


def _series_centered_correlations(
    matrix: np.ndarray, target: np.ndarray, eligible: np.ndarray,
    dataset: ConfirmationDataset, days: np.ndarray,
) -> np.ndarray:
    mask = np.asarray(eligible, bool) & np.isin(dataset.day, days)
    indices = np.flatnonzero(mask)
    if not len(indices):
        raise ConfirmationRefusal("chronological correlation block is empty")
    x = np.asarray(matrix[indices], np.float64).copy()
    y = np.asarray(target[indices], np.float64).copy()
    series = np.asarray(dataset.series_id, str)[indices]
    for key in np.unique(series):
        local = np.flatnonzero(series == key)
        x[local] -= np.mean(x[local], axis=0)
        y[local] -= float(np.mean(y[local]))
    denominator = np.sqrt(np.sum(x * x, axis=0) * np.sum(y * y))
    return np.divide(
        x.T @ y, denominator, out=np.zeros(x.shape[1], np.float64),
        where=denominator > 0)


def _chronological_correlations(
    matrix: np.ndarray, target: np.ndarray, eligible: np.ndarray,
    dataset: ConfirmationDataset, *, blocks: int,
) -> tuple[np.ndarray, tuple[tuple[int, ...], ...]]:
    days = np.unique(np.asarray(dataset.day, np.int64)[eligible])
    if len(days) < blocks:
        raise ConfirmationRefusal("fixed-horizon FIT calendar is too short")
    day_blocks = tuple(tuple(map(int, value.tolist()))
                       for value in np.array_split(days, blocks))
    correlations = np.vstack([
        _series_centered_correlations(
            matrix, target, eligible, dataset, np.asarray(block, np.int64))
        for block in day_blocks
    ])
    return correlations, day_blocks


def _stable_mask(correlations: np.ndarray, floor: float) -> np.ndarray:
    values = np.asarray(correlations, np.float64)
    signs = np.sign(values)
    return (np.all(signs == signs[0], axis=0)
            & (signs[0] != 0)
            & (np.min(np.abs(values), axis=0) >= float(floor)))


def _average_ranks(values: np.ndarray) -> np.ndarray:
    source = np.asarray(values, np.float64)
    order = np.argsort(source, kind="stable")
    ranked = np.empty(len(source), np.float64)
    position = 0
    while position < len(order):
        end = position + 1
        while end < len(order) and source[order[end]] == source[order[position]]:
            end += 1
        ranked[order[position:end]] = .5 * (position + end - 1) + 1.0
        position = end
    return ranked


def _spearman(left: np.ndarray, right: np.ndarray) -> float | None:
    x = _average_ranks(left); y = _average_ranks(right)
    x -= np.mean(x); y -= np.mean(y)
    denominator = float(np.sqrt(np.sum(x * x) * np.sum(y * y)))
    if denominator <= 0:
        return None
    return float(np.dot(x, y) / denominator)


def _binary_auc(label: np.ndarray, score: np.ndarray) -> float | None:
    y = np.asarray(label, bool); value = np.asarray(score, np.float64)
    positive = int(np.sum(y)); negative = int(np.sum(~y))
    if not positive or not negative:
        return None
    ranks = _average_ranks(value)
    return float((np.sum(ranks[y]) - positive * (positive + 1) / 2)
                 / (positive * negative))


def _path_metrics(
    score: np.ndarray, target: np.ndarray, eligible: np.ndarray,
    dataset: ConfirmationDataset,
) -> Mapping[str, object]:
    series = np.asarray(dataset.series_id, str)
    asset = np.asarray(dataset.asset, str)
    rows = []
    for key in sorted(set(series[eligible].tolist())):
        local = np.flatnonzero(np.asarray(eligible, bool) & (series == key))
        correlation = _spearman(score[local], target[local])
        if correlation is not None:
            rows.append((key, str(asset[local[0]]), correlation))
    if not rows:
        raise ConfirmationRefusal("fixed-horizon path metric is empty")
    values = np.asarray([row[2] for row in rows], np.float64)

    def summary(use: np.ndarray) -> Mapping[str, object]:
        selected = values[use]
        return {
            "paths": len(selected),
            "mean_spearman": float(np.mean(selected)),
            "median_spearman": float(np.median(selected)),
            "positive_path_fraction": float(np.mean(selected > 0.0)),
            "spearman_quantiles": tuple(float(value) for value in
                np.quantile(selected, (0.0, .1, .25, .5, .75, .9, 1.0))),
        }

    result = {"overall": summary(np.ones(len(rows), bool)), "by_asset": {}}
    row_assets = np.asarray([row[1] for row in rows], str)
    for name in sorted(set(row_assets.tolist())):
        result["by_asset"][name] = summary(row_assets == name)
    return result


def _oracle_policy_family(
    dataset: ConfirmationDataset, ledger: OracleActionLedger,
    targets: Mapping[int, FixedHorizonTarget],
    sessions: Sequence[SessionRef], config: FixedHorizonConfig,
) -> Mapping[str, object]:
    ceiling = _sparse_schedule_ceiling(dataset, sessions)
    ceiling_pnl = float(ceiling["evaluation"]["total_pnl_usd"])
    q_enter = np.asarray(ledger.q_enter_usd, np.float64)
    rows = []
    for horizon in config.horizons_sec:
        target = targets[int(horizon)]
        for minimum_value in config.value_thresholds_usd:
            for regret in config.regret_thresholds_usd:
                trigger = (np.asarray(target.eligible, bool)
                           & (q_enter >= minimum_value)
                           & (target.stop_utility_usd >= -regret))
                # A separate terminal action is lawful but has no shrinking
                # future-window label.  It must be positive on its own terms.
                trigger |= (np.asarray(target.terminal_row, bool)
                            & (q_enter >= minimum_value))
                prediction = np.column_stack((
                    q_enter,
                    np.where(trigger, 1.0, -1.0),
                ))
                policy = type("Policy", (), {
                    "min_q_enter_usd": float(minimum_value),
                    "min_enter_advantage_usd": 0.0,
                })()
                chosen = _first_triggers(dataset, prediction, policy)
                if not len(chosen):
                    continue
                arrivals = tuple(_arrival(
                    dataset, int(index), model_hash="fixed-horizon-oracle",
                    expected_pnl_usd=float(q_enter[index]),
                    pnl_q20_usd=float(q_enter[index]),
                    goal_probability=1.0, wall_probability=0.0,
                    mae_q90_usd=0.0,
                ) for index in chosen)
                evaluation = replay(arrivals, expected_sessions=sessions)
                ages = np.asarray(dataset.max_alert_age_sec, np.float64)[chosen]
                card = {
                    "horizon_sec": int(horizon),
                    "minimum_q_enter_usd": float(minimum_value),
                    "maximum_fixed_horizon_regret_usd": float(regret),
                    "candidate_first_triggers": len(chosen),
                    "mean_trigger_age_sec": float(np.mean(ages)),
                    "late_trigger_fraction_ge_270s": float(np.mean(ages >= 270)),
                    "evaluation": _evaluation_summary(evaluation, sessions),
                    "capture_of_sparse_roster_ceiling": (
                        float(evaluation.total_pnl_usd / ceiling_pnl)
                        if ceiling_pnl > 0 else 0.0),
                }
                rows.append({**card, "receipt_sha256": C.object_sha256(card)})
    if not rows:
        raise ConfirmationRefusal("fixed-horizon Oracle family is empty")
    selected = min(rows, key=lambda row: (
        -float(row["evaluation"]["total_pnl_usd"]),
        int(row["horizon_sec"]),
        float(row["minimum_q_enter_usd"]),
        float(row["maximum_fixed_horizon_regret_usd"]),
    ))
    core = {
        "scope": "ORACLE_MECHANISM_DIAGNOSTIC_NOT_LEARNED_ECONOMICS",
        "sparse_roster_ceiling": ceiling,
        "selected": selected,
        "scorecards": tuple(rows),
        "passes_minimum_capture": bool(
            selected["capture_of_sparse_roster_ceiling"]
            >= config.minimum_oracle_capture),
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


def run_fixed_horizon_audit(
    fit_dataset: ConfirmationDataset, fit_ledger: OracleActionLedger,
    platt_dataset: ConfirmationDataset, platt_ledger: OracleActionLedger,
    platt_sessions: Sequence[SessionRef], *,
    config: FixedHorizonConfig = FixedHorizonConfig(),
) -> Mapping[str, object]:
    """Run the complete no-model FIT-to-PLATT stopping mechanism audit."""

    _validate_pair(fit_dataset, fit_ledger,
                   watch_age_sec=config.watch_age_sec)
    _validate_pair(platt_dataset, platt_ledger,
                   watch_age_sec=config.watch_age_sec)
    if (fit_dataset.feature_names != platt_dataset.feature_names
            or int(np.max(fit_dataset.day)) >= int(np.min(platt_dataset.day))):
        raise ConfirmationRefusal("fixed-horizon schema/chronology differs")
    feature_indices = eligible_feature_indices(fit_dataset.feature_names)
    fit_relative, dynamic_fraction = watch_relative_matrix(
        fit_dataset, feature_indices)
    platt_relative, _ = watch_relative_matrix(platt_dataset, feature_indices)
    dynamic = dynamic_fraction >= config.minimum_dynamic_series_fraction
    if not np.any(dynamic):
        raise ConfirmationRefusal("fixed-horizon dynamic feature set is empty")
    feature_indices = feature_indices[dynamic]
    feature_names = np.asarray(fit_dataset.feature_names, str)[feature_indices]
    fit_relative = fit_relative[:, dynamic]
    platt_relative = platt_relative[:, dynamic]
    dynamic_fraction = dynamic_fraction[dynamic]
    fit_targets = {int(horizon): fixed_horizon_target(
        fit_dataset, fit_ledger, int(horizon))
        for horizon in config.horizons_sec}
    platt_targets = {int(horizon): fixed_horizon_target(
        platt_dataset, platt_ledger, int(horizon))
        for horizon in config.horizons_sec}
    horizon_reports = {}
    mechanism_passes = []
    for horizon in config.horizons_sec:
        fit_target = fit_targets[int(horizon)]
        platt_target = platt_targets[int(horizon)]
        real_corr, day_blocks = _chronological_correlations(
            fit_relative, fit_target.stop_utility_usd,
            fit_target.eligible, fit_dataset,
            blocks=config.chronological_blocks)
        stable_counts = {
            str(floor): int(np.sum(_stable_mask(real_corr, floor)))
            for floor in config.stability_floors
        }
        control_rows = []
        for kind_ordinal, kind in enumerate(CONTROL_KINDS):
            for replicate in range(config.control_replicates):
                seed = (config.control_seed + int(horizon) * 10_000
                        + kind_ordinal * 1_000 + replicate)
                control_target = shuffle_within_series(
                    fit_target.stop_utility_usd, fit_target.eligible,
                    fit_dataset.series_id, seed=seed, kind=kind)
                control_corr, control_blocks = _chronological_correlations(
                    fit_relative, control_target, fit_target.eligible,
                    fit_dataset, blocks=config.chronological_blocks)
                if control_blocks != day_blocks:
                    raise ConfirmationRefusal(
                        "fixed-horizon control chronology differs")
                counts = {
                    str(floor): int(np.sum(_stable_mask(control_corr, floor)))
                    for floor in config.stability_floors
                }
                row = {
                    "kind": kind, "replicate": replicate + 1,
                    "seed": seed, "stable_feature_counts": counts,
                }
                control_rows.append({
                    **row, "receipt_sha256": C.object_sha256(row)})
        strict = _stable_mask(real_corr, config.strict_stability_floor)
        strict_indices = np.flatnonzero(strict)
        if not len(strict_indices):
            raise ConfirmationRefusal(
                "fixed-horizon strict stable feature set is empty")
        strength = np.min(np.abs(real_corr[:, strict_indices]), axis=0)
        order = np.lexsort((feature_names[strict_indices], -strength))
        selected = strict_indices[order[:config.maximum_selected_features]]
        direction = np.sign(np.mean(real_corr[:, selected], axis=0))
        scale = np.std(
            fit_relative[np.asarray(fit_target.eligible, bool)][:, selected],
            axis=0, dtype=np.float64)
        scale = np.where(scale > 1e-7, scale, 1.0)
        fit_score = np.sum(
            fit_relative[:, selected] / scale * direction, axis=1
        ) / np.sqrt(len(selected))
        platt_score = np.sum(
            platt_relative[:, selected] / scale * direction, axis=1
        ) / np.sqrt(len(selected))
        fit_path = _path_metrics(
            fit_score, fit_target.stop_utility_usd,
            fit_target.eligible, fit_dataset)
        platt_path = _path_metrics(
            platt_score, platt_target.stop_utility_usd,
            platt_target.eligible, platt_dataset)
        platt_corr = _series_centered_correlations(
            platt_relative[:, selected], platt_target.stop_utility_usd,
            platt_target.eligible, platt_dataset,
            np.unique(platt_dataset.day[platt_target.eligible]))
        control_max = {
            str(floor): max(row["stable_feature_counts"][str(floor)]
                            for row in control_rows)
            for floor in config.stability_floors
        }
        feature_ledger = []
        for local in np.argsort(-np.min(np.abs(real_corr), axis=0)):
            row = {
                "feature_name": str(feature_names[local]),
                "source_column": int(feature_indices[local]),
                "dynamic_series_fraction": float(dynamic_fraction[local]),
                "fit_block_correlations": tuple(
                    float(value) for value in real_corr[:, local]),
                "minimum_absolute_fit_correlation": float(
                    np.min(np.abs(real_corr[:, local]))),
                "stable_at_strict_floor": bool(strict[local]),
            }
            feature_ledger.append(row)
        selected_names = tuple(map(str, feature_names[selected].tolist()))
        selected_transform = tuple({
            "feature_name": str(feature_names[local]),
            "source_column": int(feature_indices[local]),
            "direction": int(direction[position]),
            "fit_scale": float(scale[position]),
        } for position, local in enumerate(selected))
        selected_sign_agreement = float(np.mean(
            np.sign(platt_corr) == direction))
        gate = bool(
            stable_counts[str(config.strict_stability_floor)]
            > control_max[str(config.strict_stability_floor)]
            and platt_path["overall"]["mean_spearman"]
            >= config.minimum_platt_path_spearman
            and platt_path["overall"]["positive_path_fraction"]
            >= config.minimum_platt_positive_path_fraction)
        mechanism_passes.append(gate)
        core = {
            "horizon_sec": int(horizon),
            "fit_rows": int(np.sum(fit_target.eligible)),
            "fit_right_censored_rows": int(np.sum(~fit_target.eligible)),
            "fit_paths": len(set(np.asarray(
                fit_dataset.series_id, str).tolist())),
            "platt_rows": int(np.sum(platt_target.eligible)),
            "platt_right_censored_rows": int(np.sum(~platt_target.eligible)),
            "platt_paths": len(set(np.asarray(
                platt_dataset.series_id, str).tolist())),
            "fit_stop_rate": float(np.mean(
                fit_target.stop_utility_usd[fit_target.eligible] >= 0.0)),
            "platt_stop_rate": float(np.mean(
                platt_target.stop_utility_usd[platt_target.eligible] >= 0.0)),
            "chronological_fit_day_blocks": day_blocks,
            "stable_feature_counts": stable_counts,
            "control_replicates": tuple(control_rows),
            "maximum_control_stable_feature_counts": control_max,
            "selected_feature_names": selected_names,
            "selected_feature_transform": selected_transform,
            "selected_features": len(selected_names),
            "selected_platt_direction_agreement_fraction":
                selected_sign_agreement,
            "fit_path_metrics": fit_path,
            "platt_path_metrics": platt_path,
            "platt_global_stop_auc": _binary_auc(
                platt_target.stop_utility_usd[platt_target.eligible] >= 0.0,
                platt_score[platt_target.eligible]),
            "feature_ledger": tuple(feature_ledger),
            "mechanism_gate_pass": gate,
        }
        horizon_reports[str(horizon)] = {
            **core, "receipt_sha256": C.object_sha256(core)}
    oracle = _oracle_policy_family(
        platt_dataset, platt_ledger, platt_targets, platt_sessions, config)
    overall_pass = bool(all(mechanism_passes)
                        and oracle["passes_minimum_capture"])
    core = {
        "schema": SCHEMA,
        "config": asdict(config),
        "config_sha256": config.receipt_sha256,
        "fit_dataset_sha256": fit_dataset.representation_sha256,
        "fit_ledger_sha256": fit_ledger.representation_sha256,
        "platt_dataset_sha256": platt_dataset.representation_sha256,
        "platt_ledger_sha256": platt_ledger.representation_sha256,
        "eligible_feature_families": FEATURE_PREFIXES,
        "allowed_features": len(eligible_feature_indices(
            fit_dataset.feature_names)),
        "dynamic_features": len(feature_indices),
        "horizons": horizon_reports,
        "oracle_policy_family": oracle,
        "mechanism_gate_pass": overall_pass,
        "models_executed": False,
        "learned_economics_executed": False,
        "oracle_mechanism_economics_executed": True,
        "threshold_open_count": 0,
        "forward_open_count": 0,
        "h2_open_count": 0,
        "implementation_sha256": C.file_sha256(Path(__file__)),
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}
