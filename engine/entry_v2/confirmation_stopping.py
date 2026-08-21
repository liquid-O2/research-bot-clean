"""Oracle-derived supervision for the Entry V2 stopping decision.

This module does not perform reinforcement learning.  Historical confirmation
paths expose the value of every recorded entry timestamp, so the richer and
lower-variance construction is to turn that full-feedback oracle into explicit
supervised targets for CatBoost:

* ``Q_enter`` -- certified outcome if the candidate is entered now;
* ``Q_wait`` -- best non-negative certified outcome at a strictly later
  snapshot in the same candidate series;
* ``Q_pass`` -- zero dollars;
* the conservative optimal action, advantage, and regret; and
* several ordinal payoff and timing/stability labels.

The first ledger is deliberately candidate-local.  It is an audit and model
target, not a portfolio-policy oracle: it does not price contention with other
candidates, the twelve-entry daily budget, or asset occupancy.  Those effects
remain the responsibility of canonical replay and, later, a separately named
portfolio action oracle.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import os
from pathlib import Path
from types import MappingProxyType
from typing import Final, Mapping

import numpy as np

from . import common as C
from .confirmation import ConfirmationDataset, ConfirmationRefusal, re_full_sha


SCHEMA: Final = "QRE2CONFACTION1"
PASS: Final = 0
WAIT: Final = 1
ENTER: Final = 2
ACTION_NAMES: Final = ("PASS", "WAIT", "ENTER")
REGISTERED_PAYOFF_THRESHOLDS_USD: Final = (
    0.0, 300.0, 600.0, 900.0, 1_200.0, 1_800.0, 2_500.0,
)


def _money_cents(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, np.float64)
    cents = np.rint(values * 100.0).astype(np.int64)
    if not np.allclose(cents / 100.0, values, atol=1e-7, rtol=0):
        raise ConfirmationRefusal("oracle action values are not cent-exact")
    return cents


@dataclass(frozen=True, slots=True)
class OracleActionLedger:
    """Durable candidate-local full-feedback stopping supervision."""

    opportunity_id: np.ndarray
    series_id: np.ndarray
    snapshot_ts_ns: np.ndarray
    q_enter_usd: np.ndarray
    q_wait_usd: np.ndarray
    q_pass_usd: np.ndarray
    q_optimal_usd: np.ndarray
    enter_advantage_usd: np.ndarray
    enter_regret_usd: np.ndarray
    optimal_action: np.ndarray
    future_best_snapshot_ts_ns: np.ndarray
    future_best_delay_sec: np.ndarray
    action_run_observations: np.ndarray
    action_run_horizon_sec: np.ndarray
    payoff_thresholds_usd: tuple[float, ...]
    enter_ge_threshold: np.ndarray
    optimal_ge_threshold: np.ndarray
    enter_payoff_class: np.ndarray
    optimal_payoff_class: np.ndarray
    source_representation_sha256: str
    scope: str

    def validate(self) -> None:
        n = len(self.opportunity_id)
        vectors = (
            self.series_id, self.snapshot_ts_ns, self.q_enter_usd,
            self.q_wait_usd, self.q_pass_usd, self.q_optimal_usd,
            self.enter_advantage_usd, self.enter_regret_usd,
            self.optimal_action, self.future_best_snapshot_ts_ns,
            self.future_best_delay_sec, self.action_run_observations,
            self.action_run_horizon_sec, self.enter_payoff_class,
            self.optimal_payoff_class,
        )
        thresholds = np.asarray(self.payoff_thresholds_usd, np.float64)
        if (n == 0 or any(np.asarray(value).shape != (n,) for value in vectors)
                or np.asarray(self.enter_ge_threshold).shape
                != (n, len(thresholds))
                or np.asarray(self.optimal_ge_threshold).shape
                != (n, len(thresholds))
                or len(set(np.asarray(self.opportunity_id, str).tolist())) != n
                or not re_full_sha(self.source_representation_sha256)
                or self.scope not in {
                    "CANDIDATE_LOCAL_SPARSE_TRAINING",
                    "CANDIDATE_LOCAL_EVERY_SECOND_REPLAY",
                }
                or len(thresholds) == 0 or not np.all(np.isfinite(thresholds))
                or np.any(np.diff(thresholds) <= 0)
                or thresholds[0] != 0.0):
            raise ConfirmationRefusal("oracle action ledger schema is invalid")
        money = tuple(np.asarray(value, np.float64) for value in (
            self.q_enter_usd, self.q_wait_usd, self.q_pass_usd,
            self.q_optimal_usd, self.enter_advantage_usd,
            self.enter_regret_usd,
        ))
        if (any(not np.all(np.isfinite(value)) for value in money)
                or not np.all(money[2] == 0.0)
                or np.any(money[1] < 0.0)
                or not np.allclose(
                    money[3], np.maximum.reduce((money[0], money[1], money[2])),
                    atol=1e-7, rtol=0)
                or not np.allclose(
                    money[4], money[0] - np.maximum(money[1], money[2]),
                    atol=1e-7, rtol=0)
                or not np.allclose(
                    money[5], money[3] - money[0], atol=1e-7, rtol=0)
                or not np.all(np.isin(self.optimal_action, (PASS, WAIT, ENTER)))):
            raise ConfirmationRefusal("oracle action value identities do not hold")
        actions = np.asarray(self.optimal_action, np.int8)
        expected_action = np.where(
            money[3] <= 0.0, PASS,
            np.where(money[0] > money[1], ENTER, WAIT),
        ).astype(np.int8)
        if not np.array_equal(actions, expected_action):
            raise ConfirmationRefusal("oracle action tie or dominance law differs")
        future_ts = np.asarray(self.future_best_snapshot_ts_ns, np.int64)
        now = np.asarray(self.snapshot_ts_ns, np.int64)
        delay = np.asarray(self.future_best_delay_sec, np.float64)
        has_future = money[1] > 0.0
        if (np.any(future_ts[has_future] <= now[has_future])
                or np.any(future_ts[~has_future] != -1)
                or np.any(delay[~has_future] != -1.0)
                or not np.allclose(
                    delay[has_future],
                    (future_ts[has_future] - now[has_future]) / 1e9,
                    atol=1e-9, rtol=0)
                or np.any(np.asarray(self.action_run_observations) < 1)
                or np.any(np.asarray(self.action_run_horizon_sec) < 0)):
            raise ConfirmationRefusal("oracle action timing identities do not hold")
        enter_ge = np.asarray(self.enter_ge_threshold, bool)
        optimal_ge = np.asarray(self.optimal_ge_threshold, bool)
        if (not np.array_equal(enter_ge, money[0][:, None] >= thresholds[None, :])
                or not np.array_equal(
                    optimal_ge, money[3][:, None] >= thresholds[None, :])
                or not np.array_equal(
                    np.asarray(self.enter_payoff_class, np.int8),
                    enter_ge.sum(axis=1).astype(np.int8))
                or not np.array_equal(
                    np.asarray(self.optimal_payoff_class, np.int8),
                    optimal_ge.sum(axis=1).astype(np.int8))):
            raise ConfirmationRefusal("oracle ordinal payoff identities do not hold")

    @property
    def representation_sha256(self) -> str:
        self.validate()
        digest = hashlib.sha256()
        digest.update(SCHEMA.encode())
        digest.update(self.source_representation_sha256.encode())
        digest.update(self.scope.encode())
        digest.update(repr(self.payoff_thresholds_usd).encode())
        for value in (
            np.asarray(self.opportunity_id, str), np.asarray(self.series_id, str),
            np.asarray(self.snapshot_ts_ns, np.int64),
            np.asarray(self.q_enter_usd, np.float64),
            np.asarray(self.q_wait_usd, np.float64),
            np.asarray(self.q_pass_usd, np.float64),
            np.asarray(self.q_optimal_usd, np.float64),
            np.asarray(self.enter_advantage_usd, np.float64),
            np.asarray(self.enter_regret_usd, np.float64),
            np.asarray(self.optimal_action, np.int8),
            np.asarray(self.future_best_snapshot_ts_ns, np.int64),
            np.asarray(self.future_best_delay_sec, np.float64),
            np.asarray(self.action_run_observations, np.int16),
            np.asarray(self.action_run_horizon_sec, np.float64),
            np.asarray(self.enter_ge_threshold, np.bool_),
            np.asarray(self.optimal_ge_threshold, np.bool_),
            np.asarray(self.enter_payoff_class, np.int8),
            np.asarray(self.optimal_payoff_class, np.int8),
        ):
            array = np.ascontiguousarray(value)
            digest.update(str(array.dtype).encode())
            digest.update(repr(array.shape).encode())
            digest.update(array.tobytes())
        return digest.hexdigest()

    def save(self, path: os.PathLike[str] | str) -> str:
        self.validate()
        target = C.assert_workspace_output(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.suffix != ".npz":
            raise ConfirmationRefusal("oracle action ledger path must end in .npz")
        tmp = target.with_name(target.name + f".tmp.{os.getpid()}")
        with tmp.open("xb") as handle:
            np.savez_compressed(
                handle,
                opportunity_id=np.asarray(self.opportunity_id, str),
                series_id=np.asarray(self.series_id, str),
                snapshot_ts_ns=np.asarray(self.snapshot_ts_ns, np.int64),
                q_enter_usd=np.asarray(self.q_enter_usd, np.float64),
                q_wait_usd=np.asarray(self.q_wait_usd, np.float64),
                q_pass_usd=np.asarray(self.q_pass_usd, np.float64),
                q_optimal_usd=np.asarray(self.q_optimal_usd, np.float64),
                enter_advantage_usd=np.asarray(
                    self.enter_advantage_usd, np.float64),
                enter_regret_usd=np.asarray(self.enter_regret_usd, np.float64),
                optimal_action=np.asarray(self.optimal_action, np.int8),
                future_best_snapshot_ts_ns=np.asarray(
                    self.future_best_snapshot_ts_ns, np.int64),
                future_best_delay_sec=np.asarray(
                    self.future_best_delay_sec, np.float64),
                action_run_observations=np.asarray(
                    self.action_run_observations, np.int16),
                action_run_horizon_sec=np.asarray(
                    self.action_run_horizon_sec, np.float64),
                payoff_thresholds_usd=np.asarray(
                    self.payoff_thresholds_usd, np.float64),
                enter_ge_threshold=np.asarray(self.enter_ge_threshold, np.bool_),
                optimal_ge_threshold=np.asarray(
                    self.optimal_ge_threshold, np.bool_),
                enter_payoff_class=np.asarray(self.enter_payoff_class, np.int8),
                optimal_payoff_class=np.asarray(self.optimal_payoff_class, np.int8),
                source_representation_sha256=np.asarray(
                    [self.source_representation_sha256], str),
                scope=np.asarray([self.scope], str),
                schema=np.asarray([SCHEMA], str),
                representation_sha256=np.asarray(
                    [self.representation_sha256], str),
            )
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
        return C.file_sha256(target)

    @classmethod
    def load(cls, path: os.PathLike[str] | str) -> "OracleActionLedger":
        source = Path(path)
        C.guard_payload(source)
        try:
            with np.load(source, allow_pickle=False) as z:
                if str(z["schema"][0]) != SCHEMA:
                    raise ConfirmationRefusal("oracle action ledger schema differs")
                result = cls(
                    opportunity_id=z["opportunity_id"], series_id=z["series_id"],
                    snapshot_ts_ns=z["snapshot_ts_ns"],
                    q_enter_usd=z["q_enter_usd"], q_wait_usd=z["q_wait_usd"],
                    q_pass_usd=z["q_pass_usd"],
                    q_optimal_usd=z["q_optimal_usd"],
                    enter_advantage_usd=z["enter_advantage_usd"],
                    enter_regret_usd=z["enter_regret_usd"],
                    optimal_action=z["optimal_action"],
                    future_best_snapshot_ts_ns=z["future_best_snapshot_ts_ns"],
                    future_best_delay_sec=z["future_best_delay_sec"],
                    action_run_observations=z["action_run_observations"],
                    action_run_horizon_sec=z["action_run_horizon_sec"],
                    payoff_thresholds_usd=tuple(
                        z["payoff_thresholds_usd"].astype(float).tolist()),
                    enter_ge_threshold=z["enter_ge_threshold"],
                    optimal_ge_threshold=z["optimal_ge_threshold"],
                    enter_payoff_class=z["enter_payoff_class"],
                    optimal_payoff_class=z["optimal_payoff_class"],
                    source_representation_sha256=str(
                        z["source_representation_sha256"][0]),
                    scope=str(z["scope"][0]),
                )
                expected = str(z["representation_sha256"][0])
        except (OSError, ValueError, KeyError) as exc:
            raise ConfirmationRefusal("cannot strict-load oracle action ledger") from exc
        result.validate()
        if result.representation_sha256 != expected:
            raise ConfirmationRefusal("oracle action ledger representation differs")
        return result


def derive_oracle_action_ledger(
    dataset: ConfirmationDataset,
    *, payoff_thresholds_usd: tuple[float, ...]
    = REGISTERED_PAYOFF_THRESHOLDS_USD,
) -> OracleActionLedger:
    """Derive deterministic full-feedback targets by backward series scans.

    Ties between entering now and retaining the option to enter later are
    labelled ``WAIT``.  This prevents redundant early entries from being
    taught as uniquely optimal.  ``PASS`` is selected when neither entering
    now nor any recorded future entry has positive value.
    """

    dataset.validate()
    n = len(dataset.features)
    thresholds = tuple(float(value) for value in payoff_thresholds_usd)
    threshold_array = np.asarray(thresholds, np.float64)
    if (not thresholds or not np.all(np.isfinite(threshold_array))
            or threshold_array[0] != 0.0
            or np.any(np.diff(threshold_array) <= 0)):
        raise ConfirmationRefusal("oracle payoff thresholds are malformed")
    enter_cents = _money_cents(dataset.cert_close_usd)
    wait_cents = np.zeros(n, np.int64)
    future_best_ts = np.full(n, -1, np.int64)
    series = np.asarray(dataset.series_id, str)
    timestamps = np.asarray(dataset.snapshot_ts_ns, np.int64)
    ids = np.asarray(dataset.opportunity_id, str)
    all_order = np.lexsort((ids, timestamps, series)).astype(np.int64)
    ordered_series = series[all_order]
    boundaries = np.flatnonzero(np.r_[
        True, ordered_series[1:] != ordered_series[:-1], True])
    for left, right in zip(boundaries[:-1], boundaries[1:]):
        order = all_order[left:right]
        ordered_ts = timestamps[order]
        if len(order) == 0 or np.any(np.diff(ordered_ts) <= 0):
            raise ConfirmationRefusal(
                "oracle action series timestamps are not strictly increasing")
        best_cents = 0
        best_timestamp = -1
        for index in order[::-1]:
            wait_cents[index] = best_cents
            future_best_ts[index] = best_timestamp
            current = int(enter_cents[index])
            # Equal values choose the earliest future opportunity, minimizing
            # unnecessary waiting while preserving the same certified value.
            if current >= best_cents and current > 0:
                best_cents = current
                best_timestamp = int(timestamps[index])

    pass_cents = np.zeros(n, np.int64)
    optimal_cents = np.maximum.reduce((enter_cents, wait_cents, pass_cents))
    action = np.where(
        optimal_cents <= 0, PASS,
        np.where(enter_cents > wait_cents, ENTER, WAIT),
    ).astype(np.int8)
    run_observations = np.ones(n, np.int16)
    run_horizon_sec = np.zeros(n, np.float64)
    for left, right in zip(boundaries[:-1], boundaries[1:]):
        order = all_order[left:right]
        run_end = len(order) - 1
        for position in range(len(order) - 1, -1, -1):
            if (position == len(order) - 1
                    or action[order[position]] != action[order[position + 1]]):
                run_end = position
            index = order[position]
            run_observations[index] = run_end - position + 1
            run_horizon_sec[index] = (
                timestamps[order[run_end]] - timestamps[index]) / 1e9

    wait_usd = wait_cents.astype(np.float64) / 100.0
    enter_usd = enter_cents.astype(np.float64) / 100.0
    optimal_usd = optimal_cents.astype(np.float64) / 100.0
    has_future = wait_cents > 0
    future_delay = np.full(n, -1.0, np.float64)
    future_delay[has_future] = (
        future_best_ts[has_future] - timestamps[has_future]) / 1e9
    enter_ge = enter_usd[:, None] >= threshold_array[None, :]
    optimal_ge = optimal_usd[:, None] >= threshold_array[None, :]
    result = OracleActionLedger(
        opportunity_id=np.asarray(dataset.opportunity_id, str).copy(),
        series_id=series.copy(), snapshot_ts_ns=timestamps.copy(),
        q_enter_usd=enter_usd, q_wait_usd=wait_usd,
        q_pass_usd=np.zeros(n, np.float64), q_optimal_usd=optimal_usd,
        enter_advantage_usd=enter_usd - wait_usd,
        enter_regret_usd=optimal_usd - enter_usd,
        optimal_action=action,
        future_best_snapshot_ts_ns=future_best_ts,
        future_best_delay_sec=future_delay,
        action_run_observations=run_observations,
        action_run_horizon_sec=run_horizon_sec,
        payoff_thresholds_usd=thresholds,
        enter_ge_threshold=enter_ge, optimal_ge_threshold=optimal_ge,
        enter_payoff_class=enter_ge.sum(axis=1).astype(np.int8),
        optimal_payoff_class=optimal_ge.sum(axis=1).astype(np.int8),
        source_representation_sha256=dataset.representation_sha256,
        scope=("CANDIDATE_LOCAL_SPARSE_TRAINING"
               if dataset.snapshot_mode == "TRAINING"
               else "CANDIDATE_LOCAL_EVERY_SECOND_REPLAY"),
    )
    result.validate()
    return result


def oracle_action_census(
    dataset: ConfirmationDataset, ledger: OracleActionLedger,
) -> Mapping[str, object]:
    """Summarize label geometry with the same series-balanced weighting as fit."""

    dataset.validate()
    ledger.validate()
    if (ledger.source_representation_sha256 != dataset.representation_sha256
            or not np.array_equal(ledger.opportunity_id, dataset.opportunity_id)
            or not np.array_equal(ledger.series_id, dataset.series_id)
            or not np.array_equal(ledger.snapshot_ts_ns, dataset.snapshot_ts_ns)):
        raise ConfirmationRefusal("oracle action census dataset identity differs")
    series = np.asarray(dataset.series_id, str)
    _, inverse, counts = np.unique(series, return_inverse=True, return_counts=True)
    weights = 1.0 / counts[inverse].astype(np.float64)
    actions = np.asarray(ledger.optimal_action, np.int8)
    goal = np.asarray(ledger.q_enter_usd >= 600.0, bool)
    strata = registered_oracle_training_strata(ledger)

    def quantiles(values: np.ndarray, mask: np.ndarray) -> Mapping[str, float | None]:
        selected = np.asarray(values, np.float64)[mask]
        if not len(selected):
            return {name: None for name in ("p10", "p25", "p50", "p75", "p90")}
        observed = np.quantile(selected, (.10, .25, .50, .75, .90))
        return {name: float(value) for name, value in zip(
            ("p10", "p25", "p50", "p75", "p90"), observed)}

    def block(mask: np.ndarray) -> Mapping[str, object]:
        mask = np.asarray(mask, bool)
        block_weight = weights[mask]
        if not mask.any() or block_weight.sum() <= 0:
            raise ConfirmationRefusal("oracle action census block is empty")

        def rate(condition: np.ndarray) -> float:
            return float(np.average(np.asarray(condition, bool)[mask],
                                    weights=block_weight))

        action_count = {
            ACTION_NAMES[value]: int(np.count_nonzero(mask & (actions == value)))
            for value in (PASS, WAIT, ENTER)
        }
        action_rate = {
            ACTION_NAMES[value]: rate(actions == value)
            for value in (PASS, WAIT, ENTER)
        }
        goal_mask = mask & goal
        enter_mask = mask & (actions == ENTER)
        local_indices = np.flatnonzero(mask)
        local_series = series[local_indices]
        local_order = np.argsort(local_series, kind="stable")
        ordered_series = local_series[local_order]
        starts = np.flatnonzero(np.r_[
            True, ordered_series[1:] != ordered_series[:-1]])
        series_best = np.maximum.reduceat(
            np.asarray(ledger.q_enter_usd, np.float64)
            [local_indices[local_order]], starts)
        return {
            "rows": int(mask.sum()),
            "series": int(len(set(series[mask].tolist()))),
            "action_row_count": action_count,
            "action_series_balanced_rate": action_rate,
            "goal_label_series_balanced_rate": rate(goal),
            "goal_row_action_count": {
                ACTION_NAMES[value]: int(np.count_nonzero(
                    goal_mask & (actions == value)))
                for value in (PASS, WAIT, ENTER)
            },
            "goal_but_not_enter_series_balanced_rate": rate(
                goal & (actions != ENTER)),
            "enter_below_goal_series_balanced_rate": rate(
                (actions == ENTER) & ~goal),
            "stable_enter_ge_10s_series_balanced_rate": rate(
                (actions == ENTER) & (ledger.action_run_horizon_sec >= 10.0)),
            "stable_enter_ge_30s_series_balanced_rate": rate(
                (actions == ENTER) & (ledger.action_run_horizon_sec >= 30.0)),
            "q_enter_usd_quantiles": quantiles(ledger.q_enter_usd, mask),
            "enter_advantage_usd_quantiles": quantiles(
                ledger.enter_advantage_usd, mask),
            "enter_action_advantage_usd_quantiles": quantiles(
                ledger.enter_advantage_usd, enter_mask),
            "positive_wait_delay_sec_quantiles": quantiles(
                ledger.future_best_delay_sec,
                mask & (ledger.q_wait_usd > 0.0)),
            "training_stratum_row_count": {
                name: int(np.count_nonzero(mask & value))
                for name, value in strata.items()
            },
            "training_stratum_series_balanced_rate": {
                name: rate(value) for name, value in strata.items()
            },
            "series_best_q_enter_mean_usd": float(np.mean(series_best)),
            "series_best_q_enter_median_usd": float(np.median(series_best)),
            "series_best_q_enter_rate": {
                "POSITIVE": float(np.mean(series_best > 0.0)),
                "GE_250": float(np.mean(series_best >= 250.0)),
                "GE_500": float(np.mean(series_best >= 500.0)),
                "GE_1000": float(np.mean(series_best >= 1_000.0)),
            },
        }

    output = {
        "schema": "QRE2CONFACTIONCENSUS1",
        "scope": ledger.scope,
        "dataset_representation_sha256": dataset.representation_sha256,
        "ledger_representation_sha256": ledger.representation_sha256,
        "overall": block(np.ones(len(dataset.features), bool)),
        "by_asset": {
            asset: block(np.asarray(dataset.asset, str) == asset)
            for asset in C.ASSETS
            if np.any(np.asarray(dataset.asset, str) == asset)
        },
    }
    return {**output, "receipt_sha256": C.object_sha256(output)}


def registered_oracle_training_strata(
    ledger: OracleActionLedger,
) -> Mapping[str, np.ndarray]:
    """Exclusive strata for hurdle fitting and hard-negative sampling."""

    ledger.validate()
    enter = np.asarray(ledger.q_enter_usd, np.float64)
    wait = np.asarray(ledger.q_wait_usd, np.float64)
    optimal = np.asarray(ledger.q_optimal_usd, np.float64)
    regret = np.asarray(ledger.enter_regret_usd, np.float64)
    strata = {
        "ENTER_POSITIVE_R50": (enter > 0.0) & (regret <= 50.0),
        "POSITIVE_TOO_EARLY_R50": (enter > 0.0) & (regret > 50.0),
        "NONPOSITIVE_NOW_FUTURE_POSITIVE": (enter <= 0.0) & (wait > 0.0),
        "NO_POSITIVE_REMAINING": optimal <= 0.0,
    }
    membership = np.sum(np.column_stack(tuple(strata.values())), axis=1)
    if (any(value.shape != (len(enter),) for value in strata.values())
            or not np.all(membership == 1)):
        raise ConfirmationRefusal("oracle training strata are not exhaustive")
    return MappingProxyType({name: np.asarray(value, bool)
                             for name, value in strata.items()})


def rebind_oracle_action_ledger(
    ledger: OracleActionLedger, dataset: ConfirmationDataset,
) -> OracleActionLedger:
    """Bind unchanged supervision to a strict row-identical feature augmentation."""

    ledger.validate(); dataset.validate()
    if (not np.array_equal(ledger.opportunity_id, dataset.opportunity_id)
            or not np.array_equal(ledger.series_id, dataset.series_id)
            or not np.array_equal(ledger.snapshot_ts_ns, dataset.snapshot_ts_ns)):
        raise ConfirmationRefusal("oracle ledger cannot bind to different rows")
    result = replace(
        ledger, source_representation_sha256=dataset.representation_sha256)
    result.validate()
    return result


def registered_oracle_label_family(
    ledger: OracleActionLedger,
) -> Mapping[str, np.ndarray]:
    """A small, support-preserving family derived from continuous action value.

    The family deliberately spans exact, tolerant, payoff-conditioned, and
    continuation targets.  It is not a label search: every member is reported
    together and no economic policy may select among them on the threshold
    block without a separately frozen selection rule.
    """

    ledger.validate()
    enter = np.asarray(ledger.q_enter_usd, np.float64)
    regret = np.asarray(ledger.enter_regret_usd, np.float64)
    labels = {
        "EXACT_ENTER": np.asarray(ledger.optimal_action == ENTER, np.int8),
        "ENTER_POSITIVE_R50": np.asarray((enter > 0.0) & (regret <= 50.0), np.int8),
        "ENTER_P300_R50": np.asarray((enter >= 300.0) & (regret <= 50.0), np.int8),
        "ENTER_P600_R100": np.asarray(
            (enter >= 600.0) & (regret <= 100.0), np.int8),
        "ENTER_P600_R200": np.asarray(
            (enter >= 600.0) & (regret <= 200.0), np.int8),
        "WAIT_P600": np.asarray(
            (ledger.optimal_action == WAIT) & (ledger.q_wait_usd >= 600.0),
            np.int8),
    }
    if any(value.shape != (len(enter),) or len(np.unique(value)) != 2
           for value in labels.values()):
        raise ConfirmationRefusal("registered oracle label family is one-class")
    return MappingProxyType(labels)


__all__ = [
    "ACTION_NAMES", "ENTER", "OracleActionLedger", "PASS",
    "REGISTERED_PAYOFF_THRESHOLDS_USD", "SCHEMA", "WAIT",
    "derive_oracle_action_ledger", "oracle_action_census",
    "rebind_oracle_action_ledger", "registered_oracle_label_family",
    "registered_oracle_training_strata",
]
