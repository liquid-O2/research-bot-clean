"""Action-aligned candidate rank plus fixed-horizon stopping conversion.

This is a bounded PLATT model-ceiling diagnostic.  It fits the stopping model
on FIT only, freezes all score thresholds as FIT-score quantiles, and then
prices every registered causal first-crossing policy through canonical replay.
The best PLATT cell is intentionally labelled non-deployable: its purpose is
to measure whether the tabular learner can convert, not to authorize a held
run.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Final, Mapping, Sequence

import catboost
from catboost import CatBoostRanker, Pool
import numpy as np

from . import common as C
from .capacity_contract import threshold_feasibility
from .confirmation import ConfirmationDataset, ConfirmationRefusal
from .confirmation_dynamic_hurdle_policy import (
    _evaluation_summary, _sparse_schedule_ceiling,
)
from .confirmation_fixed_horizon import (
    FixedHorizonTarget, _path_metrics, fixed_horizon_target,
    shuffle_within_series, watch_relative_matrix,
)
from .confirmation_lawful_value_model import LawfulValueRankModels
from .confirmation_policy import _arrival, confirmation_series_time_order
from .confirmation_stopping import OracleActionLedger
from .contracts import SessionRef
from .replay import replay


SCHEMA: Final = "QRE2CONFLAWFULPOLICY1"
ARMS: Final = ("REAL_REAL", "REAL_CONTROL", "CONTROL_REAL", "CONTROL_CONTROL")


@dataclass(frozen=True, slots=True)
class LawfulPolicyConfig:
    watch_age_sec: int = 30
    horizon_sec: int = 120
    maximum_stop_regret_usd: float = 0.0
    capacity: int = 12
    iterations: int = 160
    depth: int = 5
    learning_rate: float = .04
    l2_leaf_reg: float = 20.0
    random_seed: int = 20260821
    thread_count: int = 16
    candidate_topk: tuple[int, ...] = (2, 4, 6, 8, 10, 12)
    minimum_delay_sec: tuple[int, ...] = (0, 5, 15, 30, 60)
    stop_score_quantiles: tuple[float, ...] = (
        0.0, .10, .25, .40, .55, .70, .80, .90, .95,
    )

    def __post_init__(self) -> None:
        topk = tuple(map(int, self.candidate_topk))
        delay = tuple(map(int, self.minimum_delay_sec))
        quantile = tuple(map(float, self.stop_score_quantiles))
        if (not 0 <= self.watch_age_sec < 300
                or not 0 < self.horizon_sec <= 240
                or not 0 <= self.maximum_stop_regret_usd <= 250
                or not 1 <= self.capacity <= 12
                or not 20 <= self.iterations <= 500
                or not 3 <= self.depth <= 8
                or not 0 < self.learning_rate <= .3
                or not 0 < self.l2_leaf_reg <= 1_000
                or not 1 <= self.thread_count <= C.MAX_CPU_WORKERS
                or topk != tuple(sorted(set(topk))) or not topk
                or topk[0] < 1 or topk[-1] > self.capacity
                or delay != tuple(sorted(set(delay))) or not delay
                or delay[0] != 0 or delay[-1] > 180
                or quantile != tuple(sorted(set(quantile))) or not quantile
                or quantile[0] < 0 or quantile[-1] >= 1):
            raise ConfirmationRefusal("lawful-policy configuration invalid")

    @property
    def receipt_sha256(self) -> str:
        return C.object_sha256({"schema": SCHEMA, **asdict(self)})


@dataclass(frozen=True, slots=True)
class FixedHorizonRankModels:
    real: CatBoostRanker
    control: CatBoostRanker
    feature_names: tuple[str, ...]


def _stop_matrix(
    dataset: ConfirmationDataset,
    transform: Sequence[Mapping[str, object]],
) -> tuple[np.ndarray, tuple[str, ...]]:
    rows = tuple(transform)
    columns = np.asarray([int(row["source_column"]) for row in rows], np.int64)
    names = tuple(str(row["feature_name"]) for row in rows)
    direction = np.asarray([int(row["direction"]) for row in rows], np.float64)
    scale = np.asarray([float(row["fit_scale"]) for row in rows], np.float64)
    if (not rows or len(set(columns.tolist())) != len(columns)
            or np.any(columns < 0) or np.any(columns >= len(dataset.feature_names))
            or names != tuple(dataset.feature_names[index] for index in columns)
            or np.any(~np.isin(direction, (-1.0, 1.0)))
            or not np.all(np.isfinite(scale)) or np.any(scale <= 0.0)):
        raise ConfirmationRefusal("fixed-horizon selected transform differs")
    relative, _ = watch_relative_matrix(dataset, columns)
    matrix = relative / scale[None, :] * direction[None, :]
    if not np.all(matrix[confirmation_series_time_order(dataset)[0]] == 0.0):
        # This first-row spot check is supplemented by the exact all-series
        # baseline check below; it gives a more local refusal reason.
        raise ConfirmationRefusal("fixed-horizon watch baseline differs")
    series = np.asarray(dataset.series_id, str)
    timestamp = np.asarray(dataset.snapshot_ts_ns, np.int64)
    first = []
    for key in sorted(set(series.tolist())):
        local = np.flatnonzero(series == key)
        first.append(int(local[np.argmin(timestamp[local])]))
    if not np.all(matrix[np.asarray(first, np.int64)] == 0.0):
        raise ConfirmationRefusal("fixed-horizon path baseline is not zero")
    return np.asarray(matrix, np.float32), names


def _rank_pool(
    matrix: np.ndarray, target: FixedHorizonTarget,
    dataset: ConfirmationDataset, values: np.ndarray,
) -> Pool:
    eligible = np.asarray(target.eligible, bool)
    series = np.asarray(dataset.series_id, str)
    timestamp = np.asarray(dataset.snapshot_ts_ns, np.int64)
    indices = np.flatnonzero(eligible)
    indices = indices[np.lexsort((timestamp[indices], series[indices]))]
    label = np.asarray(values, np.float64)[indices].copy()
    groups = series[indices]
    for key in sorted(set(groups.tolist())):
        local = np.flatnonzero(groups == key)
        label[local] -= float(np.min(label[local]))
    if (not len(indices) or np.any(label < 0.0)
            or not np.all(np.isfinite(label))):
        raise ConfirmationRefusal("fixed-horizon rank relevance differs")
    return Pool(matrix[indices], label=label, group_id=groups.tolist())


def fit_fixed_horizon_rankers(
    fit_dataset: ConfirmationDataset, fit_ledger: OracleActionLedger,
    platt_dataset: ConfirmationDataset, platt_ledger: OracleActionLedger, *,
    selected_transform: Sequence[Mapping[str, object]],
    config: LawfulPolicyConfig = LawfulPolicyConfig(),
) -> tuple[FixedHorizonRankModels, Mapping[str, object],
           FixedHorizonTarget, FixedHorizonTarget, np.ndarray, np.ndarray]:
    if (fit_dataset.feature_names != platt_dataset.feature_names
            or int(np.max(fit_dataset.day)) >= int(np.min(platt_dataset.day))):
        raise ConfirmationRefusal("fixed-horizon rank chronology differs")
    fit_target = fixed_horizon_target(
        fit_dataset, fit_ledger, config.horizon_sec)
    platt_target = fixed_horizon_target(
        platt_dataset, platt_ledger, config.horizon_sec)
    fit_matrix, names = _stop_matrix(fit_dataset, selected_transform)
    platt_matrix, platt_names = _stop_matrix(platt_dataset, selected_transform)
    if names != platt_names:
        raise ConfirmationRefusal("fixed-horizon rank schema differs")
    control_values = shuffle_within_series(
        fit_target.stop_utility_usd, fit_target.eligible,
        fit_dataset.series_id, seed=config.random_seed + 10_000,
        kind="WITHIN_SERIES_PERMUTATION")
    common = dict(
        loss_function=f"YetiRankPairwise:mode=NDCG;top={config.capacity}",
        iterations=config.iterations, depth=config.depth,
        learning_rate=config.learning_rate, l2_leaf_reg=config.l2_leaf_reg,
        thread_count=config.thread_count, allow_writing_files=False,
        verbose=False)
    real = CatBoostRanker(random_seed=config.random_seed, **common)
    control = CatBoostRanker(random_seed=config.random_seed, **common)
    real.fit(_rank_pool(
        fit_matrix, fit_target, fit_dataset, fit_target.stop_utility_usd),
        verbose=False)
    control.fit(_rank_pool(
        fit_matrix, fit_target, fit_dataset, control_values), verbose=False)
    if (int(real.tree_count_) != config.iterations
            or int(control.tree_count_) != config.iterations):
        raise ConfirmationRefusal("fixed-horizon rank tree count differs")
    fit_real = np.asarray(real.predict(fit_matrix), np.float64)
    fit_control = np.asarray(control.predict(fit_matrix), np.float64)
    platt_real = np.asarray(real.predict(platt_matrix), np.float64)
    platt_control = np.asarray(control.predict(platt_matrix), np.float64)
    diagnostics = {
        "fit_real": _path_metrics(
            fit_real, fit_target.stop_utility_usd,
            fit_target.eligible, fit_dataset),
        "fit_control": _path_metrics(
            fit_control, fit_target.stop_utility_usd,
            fit_target.eligible, fit_dataset),
        "platt_real": _path_metrics(
            platt_real, platt_target.stop_utility_usd,
            platt_target.eligible, platt_dataset),
        "platt_control": _path_metrics(
            platt_control, platt_target.stop_utility_usd,
            platt_target.eligible, platt_dataset),
    }
    gate = bool(
        diagnostics["platt_real"]["overall"]["mean_spearman"] >= .10
        and diagnostics["platt_real"]["overall"]["mean_spearman"]
        > diagnostics["platt_control"]["overall"]["mean_spearman"]
        and diagnostics["platt_real"]["overall"]["positive_path_fraction"]
        >= .65)
    importance = np.asarray(real.get_feature_importance(
        type="PredictionValuesChange"), np.float64)
    top = np.argsort(-importance, kind="stable")[:20]
    core = {
        "catboost_version": catboost.__version__,
        "objective": f"YetiRankPairwise:mode=NDCG;top={config.capacity}",
        "group_scope": "CANDIDATE_PATH",
        "target": "FIXED_HORIZON_STOP_UTILITY_SHIFTED_WITHIN_PATH",
        "feature_count": len(names), "feature_names": names,
        "diagnostics": diagnostics,
        "top_feature_importance": tuple({
            "feature": names[index], "importance": float(importance[index]),
        } for index in top if importance[index] > 0.0),
        "model_gate_pass": gate,
    }
    return (FixedHorizonRankModels(real, control, names),
            {**core, "receipt_sha256": C.object_sha256(core)},
            fit_target, platt_target, fit_real, fit_control)


def _score_delta(dataset: ConfirmationDataset, score: np.ndarray) -> np.ndarray:
    values = np.asarray(score, np.float64)
    if values.shape != (len(dataset.features),) \
            or not np.all(np.isfinite(values)):
        raise ConfirmationRefusal("fixed-horizon score differs")
    result = np.empty_like(values)
    series = np.asarray(dataset.series_id, str)
    timestamp = np.asarray(dataset.snapshot_ts_ns, np.int64)
    for key in sorted(set(series.tolist())):
        local = np.flatnonzero(series == key)
        first = int(local[np.argmin(timestamp[local])])
        result[local] = values[local] - values[first]
    return result


def _candidate_topk(
    fixed: ConfirmationDataset, base_roster: Sequence[str],
    score: np.ndarray, topk: int,
) -> set[str]:
    values = np.asarray(score, np.float64)
    base = set(map(str, base_roster)); series = np.asarray(fixed.series_id, str)
    if values.shape != (len(fixed.features),) or not base <= set(series.tolist()):
        raise ConfirmationRefusal("lawful-policy candidate scores differ")
    asset = np.asarray(fixed.asset, str); day = np.asarray(fixed.day, np.int64)
    groups = np.asarray([f"{name}:{int(d8)}" for name, d8 in zip(asset, day)], str)
    selected = set()
    for group in sorted(set(groups[np.isin(series, tuple(base))].tolist())):
        local = np.flatnonzero((groups == group) & np.isin(series, tuple(base)))
        ordered = local[np.lexsort((series[local], -values[local]))]
        selected.update(series[ordered[:topk]].tolist())
    if not selected or not selected <= base:
        raise ConfirmationRefusal("lawful-policy candidate top-k differs")
    return selected


def causal_first_crossings(
    dataset: ConfirmationDataset, target: FixedHorizonTarget,
    stop_score: np.ndarray, candidate_roster: Sequence[str], *,
    minimum_delay_sec: int, stop_delta_threshold: float,
) -> np.ndarray:
    delta = _score_delta(dataset, stop_score)
    series = np.asarray(dataset.series_id, str)
    timestamp = np.asarray(dataset.snapshot_ts_ns, np.int64)
    elapsed = np.empty(len(series), np.float64)
    for key in sorted(set(series.tolist())):
        local = np.flatnonzero(series == key)
        first_ts = int(np.min(timestamp[local]))
        elapsed[local] = (timestamp[local] - first_ts) / 1e9
    passing = (np.asarray(target.eligible, bool)
               & np.isin(series, tuple(map(str, candidate_roster)))
               & (elapsed >= int(minimum_delay_sec))
               & (delta >= float(stop_delta_threshold)))
    order = confirmation_series_time_order(dataset)
    eligible = order[passing[order]]
    if not len(eligible):
        return np.empty(0, np.int64)
    ordered_series = series[eligible]
    return eligible[np.r_[True, ordered_series[1:] != ordered_series[:-1]]]


def _thresholds(
    dataset: ConfirmationDataset, target: FixedHorizonTarget,
    score: np.ndarray, quantiles: Sequence[float],
) -> tuple[Mapping[str, float], ...]:
    delta = _score_delta(dataset, score)
    values = delta[np.asarray(target.eligible, bool)]
    rows = []
    for quantile in quantiles:
        threshold = float(np.quantile(values, float(quantile)))
        row = {"fit_quantile": float(quantile),
               "stop_delta_threshold": threshold}
        if not rows or threshold != rows[-1]["stop_delta_threshold"]:
            rows.append(row)
    if not rows:
        raise ConfirmationRefusal("lawful-policy threshold grid is empty")
    return tuple(rows)


def run_lawful_policy_ceiling(
    fit_dataset: ConfirmationDataset, fit_ledger: OracleActionLedger,
    platt_dataset: ConfirmationDataset, platt_ledger: OracleActionLedger,
    platt_fixed: ConfirmationDataset, platt_sessions: Sequence[SessionRef], *,
    base_roster: Sequence[str], candidate_models: LawfulValueRankModels,
    candidate_scores: Mapping[str, np.ndarray],
    stop_models: FixedHorizonRankModels,
    stop_targets: Mapping[str, FixedHorizonTarget],
    fit_stop_scores: Mapping[str, np.ndarray],
    selected_stop_transform: Sequence[Mapping[str, object]],
    config: LawfulPolicyConfig = LawfulPolicyConfig(),
) -> Mapping[str, object]:
    platt_matrix, names = _stop_matrix(platt_dataset, selected_stop_transform)
    if names != stop_models.feature_names:
        raise ConfirmationRefusal("lawful-policy stopping schema differs")
    platt_stop = {
        "REAL": np.asarray(stop_models.real.predict(platt_matrix), np.float64),
        "CONTROL": np.asarray(
            stop_models.control.predict(platt_matrix), np.float64),
    }
    if set(candidate_scores) != {"REAL", "CONTROL"}:
        raise ConfirmationRefusal("lawful-policy candidate arm roster differs")
    score_by_series = {kind: {
        str(series): float(score) for series, score in zip(
            platt_fixed.series_id, candidate_scores[kind])}
        for kind in ("REAL", "CONTROL")}
    stop_thresholds = {kind: _thresholds(
        fit_dataset, stop_targets["FIT"], fit_stop_scores[kind],
        config.stop_score_quantiles) for kind in ("REAL", "CONTROL")}
    target = stop_targets["PLATT"]
    arms = {}
    for arm in ARMS:
        candidate_kind, stop_kind = arm.split("_")
        cards = []
        fixed_candidate_score = np.asarray(
            candidate_scores[candidate_kind], np.float64)
        for topk in config.candidate_topk:
            roster = _candidate_topk(
                platt_fixed, base_roster, fixed_candidate_score, topk)
            for delay in config.minimum_delay_sec:
                for threshold in stop_thresholds[stop_kind]:
                    chosen = causal_first_crossings(
                        platt_dataset, target, platt_stop[stop_kind], roster,
                        minimum_delay_sec=delay,
                        stop_delta_threshold=threshold["stop_delta_threshold"])
                    if not len(chosen):
                        continue
                    arrivals = tuple(_arrival(
                        platt_dataset, int(index),
                        model_hash=f"lawful-policy-{arm.lower()}",
                        expected_pnl_usd=score_by_series[candidate_kind][
                            str(platt_dataset.series_id[index])],
                        pnl_q20_usd=score_by_series[candidate_kind][
                            str(platt_dataset.series_id[index])],
                        goal_probability=1.0, wall_probability=0.0,
                        mae_q90_usd=0.0,
                    ) for index in chosen)
                    evaluation = replay(arrivals, expected_sessions=platt_sessions)
                    summary = _evaluation_summary(evaluation, platt_sessions)
                    days_with_trades = sum(
                        row.trades > 0 for row in evaluation.asset_day_results)
                    feasibility = threshold_feasibility(
                        trades=evaluation.trades,
                        usd_per_trade=evaluation.usd_per_trade,
                        max_drawdown_usd=evaluation.max_drawdown_usd,
                        days_with_trades=days_with_trades,
                        eligible_days=evaluation.asset_days)
                    card = {
                        "candidate_topk_per_asset_day": int(topk),
                        "minimum_delay_sec": int(delay), **threshold,
                        "candidate_first_triggers": len(chosen),
                        "evaluation": summary,
                        "feasible": feasibility.feasible,
                        "feasibility_reasons": feasibility.reasons,
                        "feasibility_sha256": feasibility.receipt_sha256,
                    }
                    cards.append({**card, "receipt_sha256": C.object_sha256(card)})
        if not cards:
            raise ConfirmationRefusal(f"lawful-policy {arm} grid is empty")
        selected = min(cards, key=lambda row: (
            -float(row["evaluation"]["total_pnl_usd"]),
            float(row["evaluation"]["max_drawdown_usd"]),
            row["receipt_sha256"]))
        arm_core = {
            "selection_scope": "PLATT_MODEL_CEILING_NOT_DEPLOYABLE",
            "selected": selected, "scorecards": tuple(cards),
        }
        arms[arm] = {**arm_core, "receipt_sha256": C.object_sha256(arm_core)}
    ceiling = _sparse_schedule_ceiling(platt_dataset, platt_sessions)
    ceiling_pnl = float(ceiling["evaluation"]["total_pnl_usd"])
    for arm in ARMS:
        selected = dict(arms[arm]["selected"])
        selected["capture_of_sparse_roster_ceiling"] = (
            float(selected["evaluation"]["total_pnl_usd"] / ceiling_pnl)
            if ceiling_pnl > 0 else 0.0)
        arm_core = {
            "selection_scope": arms[arm]["selection_scope"],
            "selected": arms[arm]["selected"],
            "selected_with_capture": selected,
            "scorecards": arms[arm]["scorecards"],
        }
        arms[arm] = {**arm_core, "receipt_sha256": C.object_sha256(arm_core)}
    real_capture = float(arms["REAL_REAL"]["selected_with_capture"][
        "capture_of_sparse_roster_ceiling"])
    control_capture = max(float(arms[name]["selected_with_capture"][
        "capture_of_sparse_roster_ceiling"]) for name in ARMS[1:])
    core = {
        "schema": SCHEMA, "config": asdict(config),
        "config_sha256": config.receipt_sha256,
        "candidate_model_feature_names": candidate_models.feature_names,
        "stopping_model_feature_names": stop_models.feature_names,
        "fit_derived_stop_thresholds": stop_thresholds,
        "base_roster_series": len(set(map(str, base_roster))),
        "sparse_roster_ceiling": ceiling,
        "arms": arms,
        "real_real_capture": real_capture,
        "maximum_control_arm_capture": control_capture,
        "real_real_gap_vs_maximum_control": real_capture - control_capture,
        "platt_model_ceiling_passes_80_percent": real_capture >= .80,
        "platt_model_ceiling_passes_90_percent": real_capture >= .90,
        "selection_is_deployable": False,
        "canonical_replay_executed": True,
        "learned_economics_executed": True,
        "threshold_open_count": 0, "forward_open_count": 0,
        "h2_open_count": 0,
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


__all__ = [
    "ARMS", "SCHEMA", "FixedHorizonRankModels", "LawfulPolicyConfig",
    "causal_first_crossings", "fit_fixed_horizon_rankers",
    "run_lawful_policy_ceiling",
]
