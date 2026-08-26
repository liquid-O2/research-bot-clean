"""Role corpora and threshold experiments for tabular confirmation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, Sequence

import numpy as np
from sklearn.metrics import brier_score_loss, roc_auc_score

from . import common as C
from .confirmation import (
    ConfirmationDataset, ConfirmationOpportunitySet, ConfirmationRefusal,
    combine_confirmation_datasets,
)
from .confirmation_cache import (
    FEATURE_CACHE_SCHEMA, OPPORTUNITY_CACHE_SCHEMA, CachedConfirmationSession,
    _forecast_provider, _manifest, _prior_session_context, _record_from_manifest,
    cache_confirmation_feature_session, cache_confirmation_opportunity_session,
    materialize_feature_cache, materialize_opportunity_cache,
)
from .confirmation_diagnostics import (
    PolicyGridEvaluation, registered_feature_sets, registered_policy_grid,
    score_confirmation_policies, shuffle_confirmation_targets,
)
from .confirmation_model import (
    ConfirmationModel, ConfirmationModelConfig, ConfirmationPredictions,
    FitOnlyFeatureSelector, fit_confirmation_model,
)
from .confirmation_roster import (
    AuthoritativeConfirmationSessionSpec, _context_repository, _sha,
    canonical_stage_specs, discover_authoritative_session_specs,
)
from .contracts import SessionRef

ROLE_SCHEMA = "QRE2CONFROLE1"
PREDICTIVE_SCHEMA = "QRE2CONFPREDIAG1"
LANE_REGISTRY_SCHEMA = "QRE2CONFLANES1"
THRESHOLD_RUN_SCHEMA = "QRE2CONFTHRUN1"

@dataclass(frozen=True, slots=True)
class ConfirmationRoleCorpus:
    role: str
    window: tuple[int, int]
    dataset: ConfirmationDataset
    expected_sessions: tuple[SessionRef, ...]
    empty_sessions: tuple[SessionRef, ...]
    session_receipts: tuple[str, ...]
    receipt_sha256: str

    def validate(self) -> None:
        self.dataset.validate()
        represented = {
            SessionRef(str(asset), int(day), f"{asset}-{int(day)}")
            for asset, day in zip(self.dataset.asset, self.dataset.day)}
        if (self.role not in {"FIT", "PLATT", "THRESHOLD", "FORWARD"}
                or self.window[0] > self.window[1]
                or not self.expected_sessions
                or tuple(sorted(self.expected_sessions)) != self.expected_sessions
                or len(self.expected_sessions) != len(set(self.expected_sessions))
                or not represented <= set(self.expected_sessions)
                or set(self.empty_sessions) & represented
                or not set(self.empty_sessions) <= set(self.expected_sessions)
                or len(self.session_receipts) != len(self.expected_sessions)
                or not _sha(self.receipt_sha256)):
            raise ConfirmationRefusal("confirmation role corpus is malformed")

@dataclass(frozen=True, slots=True)
class PredictiveDiagnostic:
    rows: int
    series: int
    goal_base_rate: float
    wall_base_rate: float
    goal_auc: float
    wall_auc: float
    goal_brier: float
    wall_brier: float
    pnl_correlation: float
    top_goal_decile_lift: float
    receipt_sha256: str

@dataclass(frozen=True, slots=True)
class FeatureThresholdResult:
    feature_set: str
    input_feature_count: int
    feature_count: int
    selector_receipt_sha256: str
    model_hash: str
    model_path: str
    fit_diagnostic: PredictiveDiagnostic
    platt_diagnostic: PredictiveDiagnostic
    threshold_diagnostic: PredictiveDiagnostic
    policy_grid: PolicyGridEvaluation
    receipt_sha256: str

@dataclass(frozen=True, slots=True)
class ShuffledControlResult:
    status: str
    feature_set: str
    seed: int
    threshold_diagnostic: PredictiveDiagnostic | None
    policy_grid: PolicyGridEvaluation | None
    refusal_reason: str | None
    receipt_sha256: str

    def __post_init__(self) -> None:
        measured = self.status == "MEASURED"
        if (self.status not in {"MEASURED", "REFUSED_BY_LEARNER_CONTRACT"}
                or measured != (self.threshold_diagnostic is not None)
                or measured != (self.policy_grid is not None)
                or measured == (self.refusal_reason is not None)):
            raise ConfirmationRefusal("shuffled control result is malformed")

@dataclass(frozen=True, slots=True)
class ThresholdExperimentResult:
    status: str
    stage: str
    role_receipts: Mapping[str, str]
    feature_results: tuple[FeatureThresholdResult, ...]
    selected_feature_set: str | None
    selected_model_path: str | None
    selected_policy_receipt_sha256: str | None
    shuffled_control: ShuffledControlResult | None
    receipt_sha256: str

    def __post_init__(self) -> None:
        selected = self.status == "SELECTED"
        if (self.status not in {"SELECTED", "NO_FEASIBLE_THRESHOLD"}
                or not self.feature_results
                or selected != (self.selected_feature_set is not None)
                or selected != (self.selected_model_path is not None)
                or selected != (self.selected_policy_receipt_sha256 is not None)):
            raise ConfirmationRefusal("threshold experiment result is malformed")

def confirmation_lane_registry() -> Mapping[str, object]:
    """Declare the recovery lane without deleting legacy evidence."""

    core = {
        "schema": LANE_REGISTRY_SCHEMA,
        "active_lane": "TABULAR_CATBOOST_CONFIRMATION_V1",
        "executable_learners": ("CATBOOST_TABULAR",),
        "active_inputs": (
            "LOSSLESS_MBP1_EVENT_STREAM", "CAUSAL_STATE_FEATURES",
            "REANCHORED_TIMESTAMP_LABELS"),
        "active_horizon_seconds": (300,),
        "legacy_lanes": ({
            "name": "ENTRY_V2_NEURAL_ARM_MATRIX",
            "status": "HISTORICAL_NON_EXECUTABLE_IN_CONFIRMATION_LANE",
            "artifacts_preserved": True,
        },),
        "transformers_registered": False,
    }
    return MappingProxyType({**core, "receipt_sha256": C.object_sha256(core)})

def combine_feature_role(
    role: str, window: tuple[int, int],
    records: Sequence[CachedConfirmationSession],
) -> ConfirmationRoleCorpus:
    rows = tuple(sorted(records, key=lambda row: row.session))
    datasets = [ConfirmationDataset.load(row.dataset_path) for row in rows
                if row.status == "MATERIALIZED" and row.dataset_path is not None]
    if not datasets:
        raise ConfirmationRefusal("confirmation role has no candidate rows")
    combined = combine_confirmation_datasets(datasets)
    expected = tuple(row.session for row in rows)
    empty = tuple(row.session for row in rows
                  if row.status in {
                      "NO_NATIVE_CANDIDATES", "NO_LEARNABLE_CANDIDATES"})
    core = {
        "schema": ROLE_SCHEMA, "role": role, "window": window,
        "expected_sessions": tuple(asdict(row) for row in expected),
        "empty_sessions": tuple(asdict(row) for row in empty),
        "session_receipts": tuple(row.receipt_sha256 for row in rows),
        "dataset": combined.representation_sha256,
    }
    result = ConfirmationRoleCorpus(
        role, tuple(map(int, window)), combined, expected, empty,
        tuple(row.receipt_sha256 for row in rows), C.object_sha256(core))
    result.validate(); return result

def load_opportunity_shards(
    records: Sequence[CachedConfirmationSession],
) -> tuple[ConfirmationOpportunitySet, ...]:
    rows = tuple(sorted(records, key=lambda row: row.session))
    shards = tuple(ConfirmationOpportunitySet.load(row.dataset_path)
                   for row in rows if row.status == "MATERIALIZED"
                   and row.dataset_path is not None)
    if not shards:
        raise ConfirmationRefusal("opportunity cache has no materialized shards")
    return shards

def project_feature_set(
    dataset: ConfirmationDataset, feature_set: str,
) -> ConfirmationDataset:
    masks = registered_feature_sets(dataset.feature_names)
    try:
        mask = masks[str(feature_set).upper()]
    except KeyError as exc:
        raise ConfirmationRefusal("unknown registered confirmation feature set") from exc
    return dataset if bool(np.all(mask)) else dataset.select_features(mask)

def _series_weights(dataset: ConfirmationDataset) -> np.ndarray:
    _, inverse, counts = np.unique(
        np.asarray(dataset.series_id, str), return_inverse=True,
        return_counts=True)
    weights = 1.0 / counts[inverse].astype(np.float64)
    return weights * (len(weights) / weights.sum())

def _weighted_correlation(
    left: np.ndarray, right: np.ndarray, weight: np.ndarray,
) -> float:
    x = np.asarray(left, np.float64); y = np.asarray(right, np.float64)
    w = np.asarray(weight, np.float64); w = w / w.sum()
    dx = x - np.sum(w * x); dy = y - np.sum(w * y)
    denominator = math.sqrt(float(np.sum(w * dx * dx) * np.sum(w * dy * dy)))
    return 0.0 if denominator == 0 else float(np.sum(w * dx * dy) / denominator)

def predictive_diagnostic(
    dataset: ConfirmationDataset, predictions: ConfirmationPredictions,
) -> PredictiveDiagnostic:
    dataset.validate(); predictions.validate(dataset.opportunity_id)
    weights = _series_weights(dataset)
    goal = np.asarray(dataset.cert_close_usd >= C.MIN_EXPECTANCY_USD, np.int8)
    wall = np.asarray(dataset.wall_hit, np.int8)
    if len(np.unique(goal)) != 2 or len(np.unique(wall)) != 2:
        raise ConfirmationRefusal("predictive diagnostic block is one-class")
    goal_rate = float(np.average(goal, weights=weights))
    wall_rate = float(np.average(wall, weights=weights))
    threshold = float(np.quantile(predictions.goal_probability, .90))
    top = np.asarray(predictions.goal_probability) >= threshold
    top_rate = float(np.average(goal[top], weights=weights[top]))
    core = {
        "schema": PREDICTIVE_SCHEMA,
        "dataset": dataset.representation_sha256,
        "model": predictions.model_hash,
        "rows": len(goal), "series": len(set(dataset.series_id)),
        "goal_base_rate": goal_rate, "wall_base_rate": wall_rate,
        "goal_auc": float(roc_auc_score(
            goal, predictions.goal_probability, sample_weight=weights)),
        "wall_auc": float(roc_auc_score(
            wall, predictions.wall_probability, sample_weight=weights)),
        "goal_brier": float(brier_score_loss(
            goal, predictions.goal_probability, sample_weight=weights)),
        "wall_brier": float(brier_score_loss(
            wall, predictions.wall_probability, sample_weight=weights)),
        "pnl_correlation": _weighted_correlation(
            predictions.expected_pnl_usd, dataset.cert_close_usd, weights),
        "top_goal_decile_lift": top_rate / goal_rate,
    }
    return PredictiveDiagnostic(
        rows=int(core["rows"]), series=int(core["series"]),
        goal_base_rate=goal_rate, wall_base_rate=wall_rate,
        goal_auc=float(core["goal_auc"]), wall_auc=float(core["wall_auc"]),
        goal_brier=float(core["goal_brier"]), wall_brier=float(core["wall_brier"]),
        pnl_correlation=float(core["pnl_correlation"]),
        top_goal_decile_lift=float(core["top_goal_decile_lift"]),
        receipt_sha256=C.object_sha256(core))

def _load_or_fit_model(
    fit: ConfirmationDataset, platt: ConfirmationDataset,
    config: ConfirmationModelConfig, model_path: Path,
) -> ConfirmationModel:
    if model_path.exists():
        if not (model_path / "manifest.json").is_file():
            raise ConfirmationRefusal(
                f"incomplete confirmation model boundary: {model_path}")
        model = ConfirmationModel.load(model_path)
        if (model.config != config or model.feature_names != fit.feature_names
                or model.fit_representation_sha256 != fit.representation_sha256
                or model.platt_representation_sha256
                   != platt.representation_sha256):
            raise ConfirmationRefusal("cached confirmation model identity differs")
        return model
    model = fit_confirmation_model(fit, platt, config=config)
    model.save(model_path)
    loaded = ConfirmationModel.load(model_path)
    before = model.predict(platt); after = loaded.predict(platt)
    for name in ("expected_pnl_usd", "pnl_q20_usd", "goal_probability",
                 "wall_probability", "mae_q90_usd"):
        if not np.array_equal(getattr(before, name), getattr(after, name)):
            raise ConfirmationRefusal(
                f"strict model reload prediction differs: {name}")
    return loaded

def _load_or_fit_selector(
    fit: ConfirmationDataset, selector_path: Path,
) -> FitOnlyFeatureSelector:
    expected = FitOnlyFeatureSelector.fit(fit)
    if selector_path.is_file():
        loaded = FitOnlyFeatureSelector.load(selector_path)
        if loaded != expected:
            raise ConfirmationRefusal("cached fit-only selector identity differs")
        return loaded
    expected.save(selector_path)
    loaded = FitOnlyFeatureSelector.load(selector_path)
    if loaded != expected:
        raise ConfirmationRefusal("strict fit-only selector reload differs")
    return loaded

def _feature_threshold_result(
    feature_set: str, fit: ConfirmationDataset,
    platt: ConfirmationDataset, threshold: ConfirmationDataset,
    expected_threshold_sessions: Sequence[SessionRef],
    config: ConfirmationModelConfig, model_path: Path,
) -> FeatureThresholdResult:
    input_feature_count = len(fit.feature_names)
    selector = _load_or_fit_selector(
        fit, model_path.with_name(model_path.name + ".selector.json"))
    fit = selector.transform(fit)
    platt = selector.transform(platt)
    threshold = selector.transform(threshold)
    model = _load_or_fit_model(fit, platt, config, model_path)
    fit_prediction = model.predict(fit)
    platt_prediction = model.predict(platt)
    threshold_prediction = model.predict(threshold)
    fit_diag = predictive_diagnostic(fit, fit_prediction)
    platt_diag = predictive_diagnostic(platt, platt_prediction)
    threshold_diag = predictive_diagnostic(threshold, threshold_prediction)
    grid = score_confirmation_policies(
        threshold, threshold_prediction,
        expected_sessions=expected_threshold_sessions)
    core = {
        "schema": THRESHOLD_RUN_SCHEMA, "feature_set": feature_set,
        "input_feature_count": input_feature_count,
        "feature_count": len(fit.feature_names),
        "selector_receipt_sha256": selector.receipt_sha256,
        "model": model.model_hash,
        "model_path": str(model_path), "fit": fit_diag.receipt_sha256,
        "platt": platt_diag.receipt_sha256,
        "threshold": threshold_diag.receipt_sha256,
        "policy_grid": grid.receipt_sha256,
    }
    return FeatureThresholdResult(
        feature_set, input_feature_count, len(fit.feature_names),
        selector.receipt_sha256, model.model_hash,
        str(model_path), fit_diag, platt_diag, threshold_diag, grid,
        C.object_sha256(core))

def run_threshold_experiment(
    roles: Mapping[str, ConfirmationRoleCorpus],
    *, feature_sets: Sequence[str], model_config: ConfirmationModelConfig,
    output_directory: str | Path, stage: str,
    run_shuffled_control: bool = True, shuffled_seed: int = 20260819,
    model_directory: str | Path | None = None,
) -> ThresholdExperimentResult:
    """Fit/calibrate/threshold tabular variants; never opens FORWARD data."""

    if set(roles) != {"FIT", "PLATT", "THRESHOLD"}:
        raise ConfirmationRefusal("threshold experiment role roster differs")
    for corpus in roles.values():
        corpus.validate()
    if not (roles["FIT"].window[1] < roles["PLATT"].window[0]
            <= roles["PLATT"].window[1] < roles["THRESHOLD"].window[0]):
        raise ConfirmationRefusal("threshold experiment chronology differs")
    requested = tuple(str(name).upper() for name in feature_sets)
    if not requested or len(set(requested)) != len(requested):
        raise ConfirmationRefusal("feature experiment roster is empty/duplicated")
    registered = registered_feature_sets(roles["FIT"].dataset.feature_names)
    if set(requested) - set(registered):
        raise ConfirmationRefusal("feature experiment names are unregistered")

    output = C.assert_workspace_output(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    models_root = (output / "models" if model_directory is None else
                   C.assert_workspace_output(model_directory))
    policy_grid_receipt = C.object_sha256(tuple(
        row.receipt_sha256 for row in registered_policy_grid(
            roles["THRESHOLD"].dataset.max_delay_sec)))
    role_receipts = {name: roles[name].receipt_sha256
                     for name in ("FIT", "PLATT", "THRESHOLD")}
    identity = {
        "schema": THRESHOLD_RUN_SCHEMA, "stage": str(stage).upper(),
        "role_receipts": role_receipts, "feature_sets": requested,
        "model_config": asdict(model_config),
        "model_directory": str(models_root),
        "policy_grid_receipt_sha256": policy_grid_receipt,
        "lane_registry": confirmation_lane_registry(),
        "forward_opened": False,
    }
    identity_path = output / "identity.json"
    if identity_path.is_file():
        if _manifest(identity_path) != identity:
            raise ConfirmationRefusal("threshold experiment restart identity differs")
    else:
        C.atomic_json(identity_path, identity)

    results = []
    for name in requested:
        fit = project_feature_set(roles["FIT"].dataset, name)
        platt = project_feature_set(roles["PLATT"].dataset, name)
        threshold = project_feature_set(roles["THRESHOLD"].dataset, name)
        result = _feature_threshold_result(
            name, fit, platt, threshold,
            roles["THRESHOLD"].expected_sessions, model_config,
            models_root / name)
        C.atomic_json(output / "feature_reports" / f"{name}.json", result)
        results.append(result)

    feasible = [row for row in results if row.policy_grid.status == "SELECTED"]
    best = (None if not feasible else min(feasible, key=lambda row: (
        -float(row.policy_grid.selected_evaluation.total_pnl_usd),
        float(row.policy_grid.selected_evaluation.max_drawdown_usd),
        row.feature_count, row.feature_set)))

    null_result = None
    if run_shuffled_control:
        control_name = (best.feature_set if best is not None else
                        max(results, key=lambda row: (
                            row.threshold_diagnostic.goal_auc
                            + row.threshold_diagnostic.wall_auc,
                            -row.feature_count)).feature_set)
        fit = project_feature_set(roles["FIT"].dataset, control_name)
        platt = project_feature_set(roles["PLATT"].dataset, control_name)
        threshold = project_feature_set(roles["THRESHOLD"].dataset, control_name)
        selector = _load_or_fit_selector(
            fit, models_root / f"{control_name}__SHUFFLED.selector.json")
        fit = selector.transform(fit)
        platt = selector.transform(platt)
        threshold = selector.transform(threshold)
        shuffled_fit = shuffle_confirmation_targets(fit, shuffled_seed)
        shuffled_platt = shuffle_confirmation_targets(platt, shuffled_seed + 1)
        try:
            null_model = _load_or_fit_model(
                shuffled_fit, shuffled_platt, model_config,
                models_root / f"{control_name}__SHUFFLED")
            prediction = null_model.predict(threshold)
            diagnostic = predictive_diagnostic(threshold, prediction)
            grid = score_confirmation_policies(
                threshold, prediction,
                expected_sessions=roles["THRESHOLD"].expected_sessions)
            null_core = {
                "schema": "QRE2CONFNULL1", "status": "MEASURED",
                "feature_set": control_name, "seed": shuffled_seed,
                "diagnostic": diagnostic.receipt_sha256,
                "policy_grid": grid.receipt_sha256,
            }
            null_result = ShuffledControlResult(
                "MEASURED", control_name, shuffled_seed, diagnostic, grid,
                None, C.object_sha256(null_core))
        except ConfirmationRefusal as exc:
            null_core = {
                "schema": "QRE2CONFNULL1",
                "status": "REFUSED_BY_LEARNER_CONTRACT",
                "feature_set": control_name, "seed": shuffled_seed,
                "refusal_reason": str(exc),
            }
            null_result = ShuffledControlResult(
                "REFUSED_BY_LEARNER_CONTRACT", control_name, shuffled_seed,
                None, None, str(exc), C.object_sha256(null_core))
        C.atomic_json(output / "shuffled_control.json", null_result)

    status = "SELECTED" if best is not None else "NO_FEASIBLE_THRESHOLD"
    core = {
        "schema": THRESHOLD_RUN_SCHEMA, "status": status,
        "stage": str(stage).upper(), "role_receipts": role_receipts,
        "features": tuple(row.receipt_sha256 for row in results),
        "selected_feature_set": None if best is None else best.feature_set,
        "selected_model_path": None if best is None else best.model_path,
        "selected_policy": (None if best is None else
                            best.policy_grid.selected.receipt_sha256),
        "shuffled_control": (None if null_result is None else
                             null_result.receipt_sha256),
        "forward_opened": False,
    }
    result = ThresholdExperimentResult(
        status, str(stage).upper(), dict(role_receipts),
        tuple(results), None if best is None else best.feature_set,
        None if best is None else best.model_path,
        None if best is None else best.policy_grid.selected.receipt_sha256,
        null_result, C.object_sha256(core))
    C.atomic_json(output / "threshold_result.json", result)
    return result

__all__ = [
    "AuthoritativeConfirmationSessionSpec", "CachedConfirmationSession",
    "ConfirmationRoleCorpus", "FEATURE_CACHE_SCHEMA", "FeatureThresholdResult",
    "ShuffledControlResult", "ThresholdExperimentResult",
    "PredictiveDiagnostic", "cache_confirmation_feature_session",
    "cache_confirmation_opportunity_session", "canonical_stage_specs",
    "combine_feature_role", "confirmation_lane_registry",
    "discover_authoritative_session_specs", "load_opportunity_shards",
    "materialize_feature_cache", "materialize_opportunity_cache",
    "predictive_diagnostic", "project_feature_set",
    "run_threshold_experiment",
]
