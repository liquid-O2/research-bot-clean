"""Capacity-aligned candidate ranking during the confirmation watch state.

This diagnostic deliberately separates candidate quality from entry timing.
At a fixed elapsed watch age, every candidate contributes at most one row and
is ranked against the other candidates from the same trading day.  The target
is non-negative remaining candidate opportunity (``Q_optimal``), and the
registered objective emphasizes the top twelve positions matching the daily
entry budget.  Occupancy and arrival causality remain later replay boundaries.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from pathlib import Path
from types import MappingProxyType
from typing import Callable, Final, Mapping

import catboost
from catboost import CatBoostRanker, Pool
import numpy as np

from . import common as C
from .confirmation import ConfirmationDataset, ConfirmationRefusal
from .confirmation_diagnostics import registered_feature_sets
from .confirmation_model import FitOnlyFeatureSelector
from .confirmation_stopping import OracleActionLedger


SCHEMA: Final = "QRE2CONFCANDRANK5"
AGE_SCHEMA: Final = "QRE2CONFAGECANDRANK6"
WATCH_AGES_SECONDS: Final = (0, 30, 60, 120, 180, 240)
CAPACITY: Final = 12
GROUP_SCOPES: Final = (
    "PORTFOLIO_DAY_WATCH_AGE", "ASSET_DAY_WATCH_AGE",
)
TARGET_SCOPE: Final = "FORMATION_Q_OPTIMAL_BROADCAST"
CURRENT_TARGET_SCOPE: Final = "CURRENT_ROW_Q_OPTIMAL"
TARGET_SCOPES: Final = (TARGET_SCOPE, CURRENT_TARGET_SCOPE)


@dataclass(frozen=True, slots=True)
class CandidateRankConfig:
    feature_set: str = "MAX_PLUS_EPISODE"
    target_scope: str = TARGET_SCOPE
    excluded_feature_names: tuple[str, ...] = ()
    require_complete_watch_grid: bool = True
    watch_ages_seconds: tuple[int, ...] = WATCH_AGES_SECONDS
    capacity: int = CAPACITY
    iterations: int = 80
    depth: int = 5
    learning_rate: float = 0.06
    l2_leaf_reg: float = 10.0
    random_seed: int = 20260819
    thread_count: int = 16
    early_stopping_rounds: int = 10

    def __post_init__(self) -> None:
        ages = tuple(int(value) for value in self.watch_ages_seconds)
        excluded = tuple(str(value) for value in self.excluded_feature_names)
        if (not self.feature_set or self.target_scope not in TARGET_SCOPES
                or not isinstance(self.require_complete_watch_grid, bool)
                or excluded != tuple(self.excluded_feature_names)
                or len(set(excluded)) != len(excluded)
                or any(not value for value in excluded)
                or ages != tuple(sorted(set(ages)))
                or not ages or ages[0] != 0 or ages[-1] > 300
                or not 1 <= self.capacity <= 24
                or not 20 <= self.iterations <= 500
                or not 3 <= self.depth <= 8
                or not 0 < self.learning_rate <= .3
                or not 0 < self.l2_leaf_reg <= 1_000
                or not 1 <= self.thread_count <= C.MAX_CPU_WORKERS
                or not 5 <= self.early_stopping_rounds < self.iterations):
            raise ConfirmationRefusal("candidate-rank configuration is invalid")

    @property
    def receipt_sha256(self) -> str:
        return C.object_sha256({"schema": SCHEMA, **asdict(self)})


def _feature_columns(
    feature_names: tuple[str, ...], config: CandidateRankConfig,
) -> tuple[np.ndarray, tuple[str, ...]]:
    masks = registered_feature_sets(feature_names)
    if config.feature_set not in masks:
        raise ConfirmationRefusal("candidate rank feature set is not registered")
    selected = np.flatnonzero(masks[config.feature_set])
    selected_names = tuple(np.asarray(feature_names, str)[selected].tolist())
    excluded = set(config.excluded_feature_names)
    absent = excluded - set(selected_names)
    if absent:
        raise ConfirmationRefusal(
            f"candidate rank excluded feature is absent: {sorted(absent)}")
    keep = np.asarray([name not in excluded for name in selected_names], bool)
    columns = selected[keep]
    names = tuple(np.asarray(feature_names, str)[columns].tolist())
    if not len(columns):
        raise ConfirmationRefusal("candidate rank removed every feature")
    return columns, names


def _fit_only_feature_columns(
    fit: ConfirmationDataset, config: CandidateRankConfig,
) -> tuple[np.ndarray, tuple[str, ...], FitOnlyFeatureSelector]:
    """Apply the registered roster, then prune constants/aliases on FIT only."""

    columns, _ = _feature_columns(fit.feature_names, config)
    mask = np.zeros(len(fit.feature_names), bool)
    mask[columns] = True
    narrowed = fit.select_features(mask)
    selector = FitOnlyFeatureSelector.fit(narrowed)
    relative = np.asarray(selector.selected_indices, np.int64)
    final_columns = columns[relative]
    final_names = tuple(np.asarray(fit.feature_names, str)[final_columns].tolist())
    if final_names != selector.selected_feature_names:
        raise ConfirmationRefusal("candidate rank selector column map differs")
    return final_columns, final_names, selector


def _probe_bindings(
    datasets: Mapping[str, ConfirmationDataset],
    ledgers: Mapping[str, OracleActionLedger],
) -> tuple[Mapping[str, Mapping[str, str]], Mapping[str, str]]:
    directory = Path(__file__).resolve().parent
    inputs = {
        role: {
            "dataset_sha256": datasets[role].representation_sha256,
            "ledger_sha256": ledgers[role].representation_sha256,
        }
        for role in sorted(datasets)
    }
    implementation = {
        "candidate_rank": C.file_sha256(Path(__file__)),
        "diagnostics": C.file_sha256(
            directory / "confirmation_diagnostics.py"),
        "feature_selector": C.file_sha256(
            directory / "confirmation_model.py"),
        "stopping": C.file_sha256(
            directory / "confirmation_stopping.py"),
    }
    return inputs, implementation


def _series_groups(dataset: ConfirmationDataset) -> tuple[np.ndarray, np.ndarray]:
    series = np.asarray(dataset.series_id, str)
    timestamps = np.asarray(dataset.snapshot_ts_ns, np.int64)
    ids = np.asarray(dataset.opportunity_id, str)
    order = np.lexsort((ids, timestamps, series)).astype(np.int64)
    ordered_series = series[order]
    boundaries = np.flatnonzero(np.r_[
        True, ordered_series[1:] != ordered_series[:-1], True])
    return order, boundaries


def candidate_watch_rows(
    dataset: ConfirmationDataset, *,
    watch_ages_seconds: tuple[int, ...] = WATCH_AGES_SECONDS,
    require_complete_grid: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    """Select the first causal row at or after each fixed elapsed watch age."""

    dataset.validate()
    ages = tuple(int(value) for value in watch_ages_seconds)
    if (not isinstance(require_complete_grid, bool)
            or not ages or ages != tuple(sorted(set(ages))) or ages[0] != 0
            or ages[-1] > dataset.max_delay_sec):
        raise ConfirmationRefusal("candidate watch ages are invalid")
    selected = []
    selected_age = []
    timestamps = np.asarray(dataset.snapshot_ts_ns, np.int64)
    order, boundaries = _series_groups(dataset)
    for left, right in zip(boundaries[:-1], boundaries[1:]):
        indices = order[left:right]
        elapsed = (timestamps[indices] - timestamps[indices[0]]) / 1e9
        local_indices = []
        for age in ages:
            position = int(np.searchsorted(elapsed, float(age), side="left"))
            if position < len(indices):
                local_indices.append(int(indices[position]))
            elif require_complete_grid:
                local_indices = []
                break
        selected.extend(local_indices)
        selected_age.extend(ages[:len(local_indices)])
    indices = np.asarray(selected, np.int64)
    checkpoints = np.asarray(selected_age, np.int16)
    if (not len(indices) or len(set(zip(
            np.asarray(dataset.series_id, str)[indices].tolist(),
            checkpoints.tolist()))) != len(indices)):
        raise ConfirmationRefusal("candidate watch rows are duplicated/empty")
    return indices, checkpoints


def candidate_formation_targets(
    dataset: ConfirmationDataset, ledger: OracleActionLedger, *,
    indices: np.ndarray, checkpoints: np.ndarray,
) -> np.ndarray:
    """Broadcast each candidate's formation opportunity to every watch age."""

    dataset.validate(); ledger.validate()
    selected = np.asarray(indices, np.int64)
    ages = np.asarray(checkpoints, np.int16)
    if (selected.shape != ages.shape or not len(selected)
            or np.any(selected < 0) or np.any(selected >= len(dataset.features))
            or ledger.source_representation_sha256
            != dataset.representation_sha256
            or not np.array_equal(
                ledger.opportunity_id, dataset.opportunity_id)):
        raise ConfirmationRefusal("candidate formation-target identity differs")
    series = np.asarray(dataset.series_id, str)[selected]
    q_optimal = np.asarray(ledger.q_optimal_usd, np.float64)
    formation: dict[str, float] = {}
    for series_id in np.unique(series):
        local = np.flatnonzero((series == series_id) & (ages == 0))
        if len(local) != 1:
            raise ConfirmationRefusal(
                "candidate formation target is absent/duplicated")
        formation[str(series_id)] = float(q_optimal[selected[local[0]]])
    target = np.asarray([formation[str(value)] for value in series], np.float64)
    if np.any(target < 0.0) or not np.all(np.isfinite(target)):
        raise ConfirmationRefusal("candidate formation target is invalid")
    return target


def candidate_rank_targets(
    dataset: ConfirmationDataset, ledger: OracleActionLedger, *,
    indices: np.ndarray, checkpoints: np.ndarray, target_scope: str,
) -> np.ndarray:
    """Return either diagnostic formation value or deployable value remaining."""

    if target_scope == TARGET_SCOPE:
        return candidate_formation_targets(
            dataset, ledger, indices=indices, checkpoints=checkpoints)
    if target_scope == CURRENT_TARGET_SCOPE:
        dataset.validate(); ledger.validate()
        selected = np.asarray(indices, np.int64)
        ages = np.asarray(checkpoints, np.int16)
        if (selected.shape != ages.shape or not len(selected)
                or np.any(selected < 0)
                or np.any(selected >= len(dataset.features))
                or ledger.source_representation_sha256
                != dataset.representation_sha256
                or not np.array_equal(
                    ledger.opportunity_id, dataset.opportunity_id)):
            raise ConfirmationRefusal("candidate current-target identity differs")
        target = np.asarray(ledger.q_optimal_usd, np.float64)[selected]
        if np.any(target < 0.0) or not np.all(np.isfinite(target)):
            raise ConfirmationRefusal("candidate current target is invalid")
        return target
    raise ConfirmationRefusal("candidate rank target scope is invalid")


def _group_labels(
    dataset: ConfirmationDataset, indices: np.ndarray,
    checkpoints: np.ndarray,
    *, group_scope: str = "PORTFOLIO_DAY_WATCH_AGE",
) -> np.ndarray:
    day = np.asarray(dataset.day, np.int64)[indices]
    if group_scope == "PORTFOLIO_DAY_WATCH_AGE":
        return np.asarray([
            f"{int(local_day)}:{int(age)}"
            for local_day, age in zip(day, checkpoints)], str)
    if group_scope == "ASSET_DAY_WATCH_AGE":
        asset = np.asarray(dataset.asset, str)[indices]
        return np.asarray([
            f"{local_asset}:{int(local_day)}:{int(age)}"
            for local_asset, local_day, age in zip(asset, day, checkpoints)], str)
    raise ConfirmationRefusal("candidate rank group scope is invalid")


def _rank_pool(
    dataset: ConfirmationDataset, features: np.ndarray, target: np.ndarray,
    indices: np.ndarray, checkpoints: np.ndarray,
    *, group_scope: str = "PORTFOLIO_DAY_WATCH_AGE",
) -> tuple[Pool, np.ndarray]:
    group = _group_labels(
        dataset, indices, checkpoints, group_scope=group_scope)
    ids = np.asarray(dataset.series_id, str)[indices]
    order = np.lexsort((ids, group)).astype(np.int64)
    ordered_group = group[order]
    first = np.r_[True, ordered_group[1:] != ordered_group[:-1]]
    group_id = np.cumsum(first).astype(np.int64) - 1
    values = np.asarray(target, np.float64)
    if values.shape != (len(indices),) or np.any(values < 0.0):
        raise ConfirmationRefusal("candidate rank target is invalid")
    return (Pool(
        np.asarray(features, np.float32)[indices][order], values[order],
        group_id=group_id), order)


def _shuffle_within_groups(
    dataset: ConfirmationDataset, target: np.ndarray,
    indices: np.ndarray, checkpoints: np.ndarray, *, seed: int,
    group_scope: str = "PORTFOLIO_DAY_WATCH_AGE",
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    result = np.asarray(target, np.float64).copy()
    group = _group_labels(
        dataset, indices, checkpoints, group_scope=group_scope)
    for name in np.unique(group):
        local = np.flatnonzero(group == name)
        result[local] = result[local][rng.permutation(len(local))]
    return result


def _correlation(left: np.ndarray, right: np.ndarray) -> float:
    x = np.asarray(left, np.float64); y = np.asarray(right, np.float64)
    if np.ptp(x) <= 0.0 or np.ptp(y) <= 0.0:
        return 0.0
    value = float(np.corrcoef(x, y)[0, 1])
    return value if math.isfinite(value) else 0.0


def candidate_rank_diagnostic(
    dataset: ConfirmationDataset, ledger: OracleActionLedger, *,
    indices: np.ndarray, checkpoints: np.ndarray, score: np.ndarray,
    capacity: int = CAPACITY,
    group_scope: str = "PORTFOLIO_DAY_WATCH_AGE",
    target: np.ndarray | None = None,
    target_scope: str = "CURRENT_ROW_Q_OPTIMAL",
) -> Mapping[str, object]:
    """Measure top-capacity remaining-opportunity capture by watch age."""

    dataset.validate(); ledger.validate()
    selected_indices = np.asarray(indices, np.int64)
    age = np.asarray(checkpoints, np.int16)
    prediction = np.asarray(score, np.float64)
    if (prediction.shape != (len(selected_indices),)
            or age.shape != prediction.shape
            or np.any(selected_indices < 0)
            or np.any(selected_indices >= len(dataset.features))
            or not np.all(np.isfinite(prediction))
            or not 1 <= capacity <= 24):
        raise ConfirmationRefusal("candidate rank diagnostic inputs differ")
    values = (np.asarray(ledger.q_optimal_usd, np.float64)[selected_indices]
              if target is None else np.asarray(target, np.float64))
    if (values.shape != prediction.shape or np.any(values < 0.0)
            or not np.all(np.isfinite(values)) or not target_scope):
        raise ConfirmationRefusal("candidate opportunity target is negative")
    groups = _group_labels(
        dataset, selected_indices, age, group_scope=group_scope)

    def summarize(mask: np.ndarray) -> Mapping[str, object]:
        group_names = np.unique(groups[mask])
        selected_value = []
        oracle_value = []
        selected_rows = []
        correlations = []
        ndcg = []
        for group_name in group_names:
            local = np.flatnonzero(mask & (groups == group_name))
            if not len(local):
                continue
            k = min(capacity, len(local))
            ranked = local[np.lexsort((
                np.asarray(dataset.series_id, str)[selected_indices[local]],
                -prediction[local]))][:k]
            oracle = local[np.argsort(-values[local], kind="stable")[:k]]
            selected_rows.extend(ranked.tolist())
            selected_value.append(float(values[ranked].sum()))
            oracle_value.append(float(values[oracle].sum()))
            correlations.append(_correlation(prediction[local], values[local]))
            discounts = 1.0 / np.log2(np.arange(2, k + 2, dtype=np.float64))
            dcg = float(np.sum(values[ranked] * discounts))
            ideal = float(np.sum(values[oracle] * discounts))
            ndcg.append(0.0 if ideal == 0.0 else dcg / ideal)
        chosen = np.asarray(selected_rows, np.int64)
        selected_total = float(np.sum(selected_value))
        oracle_total = float(np.sum(oracle_value))
        realized = values[chosen]
        return {
            "groups": len(group_names),
            "selected_rows": len(chosen),
            "selected_opportunity_total_usd": selected_total,
            "oracle_top_capacity_total_usd": oracle_total,
            "top_capacity_opportunity_capture": (
                0.0 if oracle_total == 0.0 else selected_total / oracle_total),
            "selected_opportunity_mean_usd": (
                None if not len(chosen) else float(np.mean(realized))),
            "selected_positive_rate": (
                None if not len(chosen) else float(np.mean(realized > 0.0))),
            "selected_ge_250_rate": (
                None if not len(chosen) else float(np.mean(realized >= 250.0))),
            "selected_ge_500_rate": (
                None if not len(chosen) else float(np.mean(realized >= 500.0))),
            "selected_ge_1000_rate": (
                None if not len(chosen) else float(np.mean(realized >= 1_000.0))),
            "within_group_correlation_mean": (
                None if not correlations else float(np.mean(correlations))),
            "ndcg_at_capacity_mean": (
                None if not ndcg else float(np.mean(ndcg))),
            "score_standard_deviation": float(np.std(prediction[mask])),
            "score_unique_count": int(len(np.unique(prediction[mask]))),
        }

    core = {
        "rows": len(selected_indices),
        "series": len(set(np.asarray(
            dataset.series_id, str)[selected_indices].tolist())),
        "capacity": capacity,
        "group_scope": group_scope,
        "target_scope": target_scope,
        "overall": summarize(np.ones(len(selected_indices), bool)),
        "by_asset": {
            local_asset: summarize(
                np.asarray(dataset.asset, str)[selected_indices] == local_asset)
            for local_asset in C.ASSETS
            if np.any(np.asarray(
                dataset.asset, str)[selected_indices] == local_asset)
        },
        "by_watch_age": {
            str(int(local_age)): summarize(age == local_age)
            for local_age in np.unique(age)
        },
        "economics_executed": False,
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


def run_candidate_rank_probe(
    datasets: Mapping[str, ConfirmationDataset],
    ledgers: Mapping[str, OracleActionLedger], *,
    config: CandidateRankConfig = CandidateRankConfig(),
    progress: Callable[[Mapping[str, object]], None] | None = None,
) -> Mapping[str, object]:
    """Fit one top-twelve day/watch-age candidate opportunity ranker."""

    roles = ("FIT", "PLATT", "THRESHOLD")
    if set(datasets) != set(roles) or set(ledgers) != set(roles):
        raise ConfirmationRefusal("candidate rank role roster is incomplete")
    for role in roles:
        datasets[role].validate(); ledgers[role].validate()
        if (ledgers[role].source_representation_sha256
                != datasets[role].representation_sha256
                or not np.array_equal(
                    datasets[role].opportunity_id, ledgers[role].opportunity_id)):
            raise ConfirmationRefusal("candidate rank role identity differs")
    fit = datasets["FIT"]; platt = datasets["PLATT"]
    if (fit.feature_names != platt.feature_names
            or fit.feature_names != datasets["THRESHOLD"].feature_names
            or int(np.max(fit.day)) >= int(np.min(platt.day))
            or int(np.max(platt.day)) >= int(np.min(datasets["THRESHOLD"].day))):
        raise ConfirmationRefusal("candidate rank schemas/chronology differ")
    inputs, implementation = _probe_bindings(datasets, ledgers)
    columns, feature_names, selector = _fit_only_feature_columns(fit, config)
    features = {role: np.asarray(
        datasets[role].features[:, columns], np.float32) for role in roles}
    rows = {role: candidate_watch_rows(
        datasets[role], watch_ages_seconds=config.watch_ages_seconds,
        require_complete_grid=config.require_complete_watch_grid)
        for role in roles}
    target = {role: candidate_rank_targets(
        datasets[role], ledgers[role], indices=rows[role][0],
        checkpoints=rows[role][1], target_scope=config.target_scope)
        for role in roles}
    fit_pool, _ = _rank_pool(
        fit, features["FIT"], target["FIT"], *rows["FIT"])
    platt_pool, _ = _rank_pool(
        platt, features["PLATT"], target["PLATT"], *rows["PLATT"])
    common = dict(
        iterations=config.iterations, depth=config.depth,
        learning_rate=config.learning_rate, l2_leaf_reg=config.l2_leaf_reg,
        random_seed=config.random_seed, thread_count=config.thread_count,
        allow_writing_files=False, verbose=False,
    )
    loss = f"YetiRankPairwise:mode=NDCG;top={config.capacity}"
    model = CatBoostRanker(
        loss_function=loss, eval_metric=f"NDCG:top={config.capacity}",
        od_type="Iter", od_wait=config.early_stopping_rounds, **common)
    model.fit(fit_pool, eval_set=platt_pool, use_best_model=True, verbose=False)
    if progress is not None:
        progress({"fit": "CANDIDATE_NDCG_RANK",
                  "trees": int(model.tree_count_)})
    scores = {role: np.asarray(
        model.predict(features[role][rows[role][0]]), np.float64)
        for role in roles}
    diagnostics = {role: candidate_rank_diagnostic(
        datasets[role], ledgers[role], indices=rows[role][0],
        checkpoints=rows[role][1], score=scores[role],
        capacity=config.capacity, target=target[role],
        target_scope=config.target_scope) for role in roles}

    shuffled = _shuffle_within_groups(
        fit, target["FIT"], *rows["FIT"], seed=config.random_seed + 1)
    control_pool, _ = _rank_pool(
        fit, features["FIT"], shuffled, *rows["FIT"])
    control = CatBoostRanker(loss_function=loss, **{
        **common, "random_seed": config.random_seed + 1})
    control.fit(control_pool, verbose=False)
    control_score = np.asarray(control.predict(
        features["THRESHOLD"][rows["THRESHOLD"][0]]), np.float64)
    control_diagnostic = candidate_rank_diagnostic(
        datasets["THRESHOLD"], ledgers["THRESHOLD"],
        indices=rows["THRESHOLD"][0], checkpoints=rows["THRESHOLD"][1],
        score=control_score, capacity=config.capacity,
        target=target["THRESHOLD"], target_scope=config.target_scope)
    if progress is not None:
        progress({"fit": "WITHIN_DAY_WATCH_AGE_TARGET_SHUFFLE",
                  "trees": int(control.tree_count_)})
    core = {
        "schema": SCHEMA,
        "config": asdict(config),
        "config_sha256": config.receipt_sha256,
        "catboost_version": catboost.__version__,
        "feature_set": config.feature_set,
        "feature_count": len(columns),
        "feature_names": feature_names,
        "fit_only_selector": {
            "receipt_sha256": selector.receipt_sha256,
            "input_feature_count": len(selector.input_feature_names),
            "selected_feature_count": len(selector.selected_indices),
            "constant_feature_count": len(selector.constant_feature_names),
            "duplicate_alias_count": len(selector.duplicate_aliases),
            "labels_used": False,
        },
        "inputs": inputs,
        "implementation_sha256": implementation,
        "target_scope": config.target_scope,
        "objective": loss,
        "tree_count": int(model.tree_count_),
        "diagnostics": diagnostics,
        "negative_control": {
            "name": "FIT_Q_OPTIMAL_SHUFFLED_WITHIN_DAY_WATCH_AGE",
            "seed": config.random_seed + 1,
            "tree_count": int(control.tree_count_),
            "threshold_diagnostic": control_diagnostic,
        },
        "economics_executed": False,
        "forward_open_count": 0,
        "h2_open_count": 0,
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


def run_candidate_age_rank_probe(
    datasets: Mapping[str, ConfirmationDataset],
    ledgers: Mapping[str, OracleActionLedger], *,
    config: CandidateRankConfig = CandidateRankConfig(capacity=4),
    progress: Callable[[Mapping[str, object]], None] | None = None,
) -> Mapping[str, object]:
    """Fit independent within-asset candidate rankers at each watch age.

    Independent age models prevent a strong formation/static split from
    suppressing a weaker confirmation-specific relationship.  Every age is
    registered before fitting; PLATT alone selects the age, while THRESHOLD
    remains read-only.
    """

    roles = ("FIT", "PLATT", "THRESHOLD")
    if set(datasets) != set(roles) or set(ledgers) != set(roles):
        raise ConfirmationRefusal("candidate-age rank role roster is incomplete")
    for role in roles:
        datasets[role].validate(); ledgers[role].validate()
        if (ledgers[role].source_representation_sha256
                != datasets[role].representation_sha256
                or not np.array_equal(
                    datasets[role].opportunity_id, ledgers[role].opportunity_id)):
            raise ConfirmationRefusal("candidate-age rank role identity differs")
    fit = datasets["FIT"]; platt = datasets["PLATT"]
    if (fit.feature_names != platt.feature_names
            or fit.feature_names != datasets["THRESHOLD"].feature_names
            or int(np.max(fit.day)) >= int(np.min(platt.day))
            or int(np.max(platt.day)) >= int(np.min(datasets["THRESHOLD"].day))):
        raise ConfirmationRefusal("candidate-age rank schemas/chronology differ")
    inputs, implementation = _probe_bindings(datasets, ledgers)
    columns, feature_names, selector = _fit_only_feature_columns(fit, config)
    features = {role: np.asarray(
        datasets[role].features[:, columns], np.float32) for role in roles}
    all_rows = {role: candidate_watch_rows(
        datasets[role], watch_ages_seconds=config.watch_ages_seconds,
        require_complete_grid=config.require_complete_watch_grid)
        for role in roles}
    all_targets = {role: candidate_rank_targets(
        datasets[role], ledgers[role], indices=all_rows[role][0],
        checkpoints=all_rows[role][1], target_scope=config.target_scope)
        for role in roles}
    common = dict(
        iterations=config.iterations, depth=config.depth,
        learning_rate=config.learning_rate, l2_leaf_reg=config.l2_leaf_reg,
        random_seed=config.random_seed, thread_count=config.thread_count,
        allow_writing_files=False, verbose=False,
    )
    loss = f"YetiRankPairwise:mode=NDCG;top={config.capacity}"
    age_results = []
    for ordinal, watch_age in enumerate(config.watch_ages_seconds):
        rows = {}
        target = {}
        for role in roles:
            indices, checkpoints = all_rows[role]
            keep = checkpoints == watch_age
            rows[role] = (indices[keep], checkpoints[keep])
            target[role] = all_targets[role][keep]
            if not len(indices[keep]):
                raise ConfirmationRefusal(
                    "candidate-age checkpoint has no authoritative rows")
        fit_pool, _ = _rank_pool(
            fit, features["FIT"], target["FIT"], *rows["FIT"],
            group_scope="ASSET_DAY_WATCH_AGE")
        platt_pool, _ = _rank_pool(
            platt, features["PLATT"], target["PLATT"], *rows["PLATT"],
            group_scope="ASSET_DAY_WATCH_AGE")
        model = CatBoostRanker(
            loss_function=loss, eval_metric=f"NDCG:top={config.capacity}",
            od_type="Iter", od_wait=config.early_stopping_rounds,
            **{**common, "random_seed": config.random_seed + ordinal})
        model.fit(
            fit_pool, eval_set=platt_pool, use_best_model=True, verbose=False)
        scores = {role: np.asarray(model.predict(
            features[role][rows[role][0]]), np.float64) for role in roles}
        diagnostics = {role: candidate_rank_diagnostic(
            datasets[role], ledgers[role], indices=rows[role][0],
            checkpoints=rows[role][1], score=scores[role],
            capacity=config.capacity,
            group_scope="ASSET_DAY_WATCH_AGE", target=target[role],
            target_scope=config.target_scope) for role in roles}
        # PredictionValuesChange is non-negative and describes the fitted
        # score itself.  LossFunctionChange can legitimately be negative for
        # rankers and must not be filtered as though it were unsigned.
        importance = np.asarray(model.get_feature_importance(
            type="PredictionValuesChange"), np.float64)
        top = np.argsort(-importance, kind="stable")[:20]

        shuffled = _shuffle_within_groups(
            fit, target["FIT"], *rows["FIT"],
            seed=config.random_seed + 1_000 + ordinal,
            group_scope="ASSET_DAY_WATCH_AGE")
        control_pool, _ = _rank_pool(
            fit, features["FIT"], shuffled, *rows["FIT"],
            group_scope="ASSET_DAY_WATCH_AGE")
        control = CatBoostRanker(
            loss_function=loss,
            **{**common, "random_seed": config.random_seed + 1_000 + ordinal})
        control.fit(control_pool, verbose=False)
        control_score = np.asarray(control.predict(
            features["THRESHOLD"][rows["THRESHOLD"][0]]), np.float64)
        control_diagnostic = candidate_rank_diagnostic(
            datasets["THRESHOLD"], ledgers["THRESHOLD"],
            indices=rows["THRESHOLD"][0],
            checkpoints=rows["THRESHOLD"][1], score=control_score,
            capacity=config.capacity,
            group_scope="ASSET_DAY_WATCH_AGE",
            target=target["THRESHOLD"], target_scope=config.target_scope)
        row_core = {
            "watch_age_sec": int(watch_age),
            "tree_count": int(model.tree_count_),
            "diagnostics": diagnostics,
            "top_feature_importance": tuple({
                "feature": feature_names[index],
                "importance": float(importance[index]),
            } for index in top if importance[index] > 0.0),
            "negative_control": {
                "name": "FIT_Q_OPTIMAL_SHUFFLED_WITHIN_ASSET_DAY_WATCH_AGE",
                "seed": config.random_seed + 1_000 + ordinal,
                "tree_count": int(control.tree_count_),
                "threshold_diagnostic": control_diagnostic,
            },
        }
        age_results.append({
            **row_core, "receipt_sha256": C.object_sha256(row_core)})
        if progress is not None:
            progress({
                "fit": "ASSET_DAY_CANDIDATE_NDCG_RANK",
                "watch_age_sec": int(watch_age),
                "trees": int(model.tree_count_),
                "platt_capture": diagnostics["PLATT"]["overall"]
                    ["top_capacity_opportunity_capture"],
                "threshold_capture": diagnostics["THRESHOLD"]["overall"]
                    ["top_capacity_opportunity_capture"],
                "threshold_control_capture": control_diagnostic["overall"]
                    ["top_capacity_opportunity_capture"],
            })
    selected = max(age_results, key=lambda row: (
        float(row["diagnostics"]["PLATT"]["overall"]
              ["top_capacity_opportunity_capture"]),
        -int(row["watch_age_sec"])))
    core = {
        "schema": AGE_SCHEMA,
        "config": asdict(config),
        "config_sha256": config.receipt_sha256,
        "catboost_version": catboost.__version__,
        "feature_set": config.feature_set,
        "feature_count": len(columns),
        "feature_names": feature_names,
        "fit_only_selector": {
            "receipt_sha256": selector.receipt_sha256,
            "input_feature_count": len(selector.input_feature_names),
            "selected_feature_count": len(selector.selected_indices),
            "constant_feature_count": len(selector.constant_feature_names),
            "duplicate_alias_count": len(selector.duplicate_aliases),
            "labels_used": False,
        },
        "inputs": inputs,
        "implementation_sha256": implementation,
        "target_scope": config.target_scope,
        "objective": loss,
        "group_scope": "ASSET_DAY_WATCH_AGE",
        "capacity_per_asset": config.capacity,
        "age_results": tuple(age_results),
        "selection_role": "PLATT",
        "selection_metric": "top_capacity_opportunity_capture",
        "selected_watch_age_sec": int(selected["watch_age_sec"]),
        "selected_threshold_diagnostic": selected["diagnostics"]["THRESHOLD"],
        "selected_threshold_negative_control": selected["negative_control"]
            ["threshold_diagnostic"],
        "economics_executed": False,
        "forward_open_count": 0,
        "h2_open_count": 0,
    }
    return {**core, "receipt_sha256": C.object_sha256(core)}


__all__ = [
    "AGE_SCHEMA", "CAPACITY", "CURRENT_TARGET_SCOPE", "GROUP_SCOPES", "SCHEMA",
    "TARGET_SCOPE", "TARGET_SCOPES", "WATCH_AGES_SECONDS", "CandidateRankConfig",
    "candidate_formation_targets", "candidate_rank_targets", "candidate_rank_diagnostic",
    "candidate_watch_rows",
    "run_candidate_age_rank_probe", "run_candidate_rank_probe",
]
