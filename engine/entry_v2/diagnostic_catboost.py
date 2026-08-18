"""Deterministic CatBoost attribution on the exact frozen diagnostic state.

Action classification is the A-004 singleton-safe policy attribution.  The
selectable PairLogit head uses explicit same-(asset, day, phase) groups;
asset/day pseudo-groups and inferred time groups are impossible in this API.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
import tempfile
import os
from typing import Mapping, Sequence

import catboost
from catboost import CatBoostClassifier, CatBoostRanker, Pool
import numpy as np
from sklearn.metrics import average_precision_score, log_loss, roc_auc_score
from . import common as C
from .diagnostic_inputs import DiagnosticInputRefusal, frozen_chronology_split
from .atlas_probe_model import canonical_phase_pair_manifest, action_fit_weights


SEED = 20260816
EXACT_ASSETS = ("HG", "NKD", "SI")
PINNED_CATBOOST_VERSION = "1.2.10"


class DiagnosticCatBoostRefusal(RuntimeError):
    pass


class RankerAvailability(str, Enum):
    MATERIALIZED = "MATERIALIZED"
    UNAVAILABLE_LOW_SUPPORT = "UNAVAILABLE_LOW_SUPPORT"


def _array_hash(value: np.ndarray) -> str:
    array = np.ascontiguousarray(value)
    digest = hashlib.sha256()
    digest.update(str(array.dtype).encode()); digest.update(repr(array.shape).encode())
    digest.update(array.tobytes())
    return digest.hexdigest()


def _payload_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(
        C.canonical_json_value(value), sort_keys=True, separators=(",", ":"),
        allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class FrozenRepresentationRows:
    representation: np.ndarray
    candidate_id: np.ndarray
    asset: np.ndarray
    day: np.ndarray
    decision_ts_ns: np.ndarray
    action_target: np.ndarray
    action_loss_mask: np.ndarray
    exact_time_group_id: np.ndarray
    split: np.ndarray
    chronology: str = "E1"
    eligible_development_days: tuple[int, ...] = ()
    group_semantics: str = "PHASE"

    def validate(self) -> None:
        x = np.asarray(self.representation)
        n = len(x)
        vectors = (self.candidate_id, self.asset, self.day, self.decision_ts_ns,
                   self.action_target, self.action_loss_mask,
                   self.exact_time_group_id, self.split)
        if (x.ndim != 2 or not n or not np.all(np.isfinite(x))
                or any(np.asarray(value).shape != (n,) for value in vectors)
                or len(set(np.asarray(self.candidate_id, str).tolist())) != n
                or tuple(sorted(set(np.asarray(self.asset, str).tolist()))) != EXACT_ASSETS
                or self.group_semantics != "PHASE"):
            raise DiagnosticCatBoostRefusal("diagnostic CatBoost row schema is invalid")
        if (np.asarray(self.decision_ts_ns).dtype.kind not in "iu"
                or not np.all(np.isin(self.action_target, (0, 1, False, True)))
                or not np.all(np.isin(self.action_loss_mask, (0, 1, False, True)))
                ):
            raise DiagnosticCatBoostRefusal("diagnostic CatBoost row semantics are invalid")
        try:
            derived = self.frozen_split()
        except DiagnosticInputRefusal as exc:
            raise DiagnosticCatBoostRefusal(str(exc)) from exc
        if "FIT" not in set(derived.tolist()):
            raise DiagnosticCatBoostRefusal("diagnostic chronology has no fit rows")

    def frozen_split(self) -> np.ndarray:
        return frozen_chronology_split(
            np.asarray(self.day), self.chronology,
            eligible_days=(self.eligible_development_days or None))

    @property
    def representation_sha256(self) -> str:
        return _array_hash(np.asarray(self.representation, np.float32))

    def canonical_order(self, mask: np.ndarray) -> np.ndarray:
        selected = np.flatnonzero(np.asarray(mask, bool))
        order = np.lexsort((np.asarray(self.candidate_id, str)[selected],
                            np.asarray(self.decision_ts_ns, np.int64)[selected],
                            np.asarray(self.day, str)[selected],
                            np.asarray(self.asset, str)[selected]))
        return selected[order]


@dataclass(frozen=True)
class ExactPairManifest:
    indices: np.ndarray
    group_ids: np.ndarray
    pairs: tuple[tuple[int, int], ...]
    pair_weights: tuple[float, ...]
    group_count: int
    receipt_sha256: str


def exact_pair_manifest(rows: FrozenRepresentationRows, asset: str, *,
                        fit_only: bool = True) -> ExactPairManifest:
    rows.validate()
    split = rows.frozen_split()
    mask = np.asarray(rows.asset, str) == asset
    if fit_only:
        explicit = np.asarray(rows.split, str)
        if set(explicit.tolist()) == {"PAIR_FIT"}:
            # The independent M2 depth roster is entirely a fit-only ranker
            # support population.  Its 16/14/14 construction strata are not
            # mapper/Platt/threshold supervision partitions.
            mask &= explicit == "PAIR_FIT"
        else:
            mask &= (split == "FIT") & (explicit != "VALIDATION")
    exact = canonical_phase_pair_manifest(
        rows.candidate_id, rows.asset, rows.day, rows.exact_time_group_id,
        rows.decision_ts_ns, rows.action_target, rows.action_loss_mask, mask)
    return ExactPairManifest(
        exact.indices, exact.group_ids, exact.pairs,
        tuple(map(float, exact.pair_weights.tolist())), exact.group_count,
        exact.receipt_sha256)


def _classifier_params() -> dict[str, object]:
    return {"loss_function": "Logloss", "iterations": 200, "depth": 6,
            "learning_rate": .05, "l2_leaf_reg": 3.0, "random_seed": SEED,
            "random_strength": 0.0, "bootstrap_type": "No", "thread_count": _threads(),
            "task_type": "CPU", "allow_writing_files": False, "verbose": False}


def _ranker_params() -> dict[str, object]:
    return {"loss_function": "PairLogit", "iterations": 200, "depth": 6,
            "learning_rate": .05, "l2_leaf_reg": 3.0, "random_seed": SEED,
            "random_strength": 0.0, "bootstrap_type": "No", "thread_count": _threads(),
            "task_type": "CPU", "allow_writing_files": False, "verbose": False}


def _threads() -> int:
    # Semantic determinism is pinned; detected host parallelism is timing-only
    # evidence and never changes a CatBoost model/config hash.
    return 8


def _model_hash(model: object) -> str:
    with tempfile.TemporaryDirectory(prefix="entry-v2-catboost-hash-") as directory:
        path = Path(directory) / "model.json"
        model.save_model(str(path), format="json")  # type: ignore[attr-defined]
        payload = json.loads(path.read_text())
        # CatBoost inserts these container fields after an otherwise identical
        # deterministic CPU fit; they are not model parameters or structure.
        model_info = payload.get("model_info", {})
        for key in ("model_guid", "train_finish_time"):
            model_info.pop(key, None)
        return _payload_hash(payload)


@dataclass
class AssetCatBoostFit:
    action_model: CatBoostClassifier
    ranker_model: CatBoostRanker | None
    ranker_availability: RankerAvailability
    pair_manifest: ExactPairManifest
    action_model_sha256: str
    ranker_model_sha256: str | None


@dataclass
class DiagnosticCatBoostFit:
    assets: Mapping[str, AssetCatBoostFit]
    action_probability: np.ndarray
    rank_score: np.ndarray
    representation_sha256: str
    canonical_order_sha256: str
    split_manifest_sha256: str
    config_sha256: str
    action_weight_receipt_sha256: str
    receipt_sha256: str


def fit_diagnostic_catboost(
    rows: FrozenRepresentationRows, *, expected_representation_sha256: str,
    minimum_pair_groups_per_asset: int = 40,
    pair_rows: FrozenRepresentationRows | None = None,
) -> DiagnosticCatBoostFit:
    if catboost.__version__ != PINNED_CATBOOST_VERSION:
        raise DiagnosticCatBoostRefusal("CatBoost version differs from the pinned package")
    rows.validate()
    if rows.representation_sha256 != expected_representation_sha256:
        raise DiagnosticCatBoostRefusal("CatBoost/direct-head representation hash differs")
    if (isinstance(minimum_pair_groups_per_asset, bool)
            or not isinstance(minimum_pair_groups_per_asset, int)
            or not 1 <= minimum_pair_groups_per_asset <= 40):
        raise DiagnosticCatBoostRefusal("PairLogit support floor is invalid")
    pair_rows = rows if pair_rows is None else pair_rows
    pair_rows.validate()
    if np.asarray(pair_rows.representation).shape[1] != np.asarray(rows.representation).shape[1]:
        raise DiagnosticCatBoostRefusal("PairLogit depth representation width differs")
    x = np.ascontiguousarray(rows.representation, np.float32)
    action = np.asarray(rows.action_target, np.int8)
    fit_split = rows.frozen_split() == "FIT"
    probability = np.full(len(x), np.nan, np.float64)
    rank_score = np.full(len(x), np.nan, np.float64)
    fits: dict[str, AssetCatBoostFit] = {}
    explicit_stage = np.asarray(rows.split, str)
    fit_training = fit_split & (explicit_stage != "VALIDATION")
    global_fit = fit_training & np.asarray(rows.action_loss_mask, bool)
    global_fit_indices = rows.canonical_order(fit_training)
    local_action_weights, weight_receipt = action_fit_weights(
        np.asarray(rows.asset)[global_fit_indices],
        np.asarray(rows.day)[global_fit_indices],
        np.asarray(rows.action_target)[global_fit_indices],
        np.asarray(rows.action_loss_mask)[global_fit_indices],
        np.ones(len(global_fit_indices), bool))
    action_weights = np.zeros(len(x), np.float32)
    action_weights[global_fit_indices] = local_action_weights
    canonical: list[str] = []
    for asset in EXACT_ASSETS:
        train_mask = ((np.asarray(rows.asset, str) == asset) & global_fit
                      & np.asarray(rows.action_loss_mask, bool))
        train = rows.canonical_order(train_mask)
        if (len(train) < 64 or min(int(np.sum(action[train] == 0)),
                                  int(np.sum(action[train] == 1))) < 32):
            raise DiagnosticCatBoostRefusal(f"{asset} action classifier lacks fit competence support")
        canonical.extend(np.asarray(rows.candidate_id, str)[train].tolist())
        classifier = CatBoostClassifier(**_classifier_params())
        classifier.fit(x[train], action[train], sample_weight=action_weights[train])
        asset_rows = rows.canonical_order(np.asarray(rows.asset, str) == asset)
        probability[asset_rows] = classifier.predict_proba(x[asset_rows])[:, 1]
        manifest = exact_pair_manifest(pair_rows, asset)
        ranker: CatBoostRanker | None = None; ranker_hash: str | None = None
        availability = RankerAvailability.UNAVAILABLE_LOW_SUPPORT
        if manifest.group_count >= minimum_pair_groups_per_asset:
            pair_x = np.ascontiguousarray(pair_rows.representation, np.float32)
            pair_action = np.asarray(pair_rows.action_target, np.int8)
            pool = Pool(pair_x[manifest.indices],
                        label=pair_action[manifest.indices].astype(np.float32),
                        group_id=manifest.group_ids, pairs=list(manifest.pairs),
                        pairs_weight=list(manifest.pair_weights))
            ranker = CatBoostRanker(**_ranker_params()); ranker.fit(pool)
            rank_score[asset_rows] = np.asarray(ranker.predict(x[asset_rows]), np.float64)
            ranker_hash = _model_hash(ranker); availability = RankerAvailability.MATERIALIZED
        fits[asset] = AssetCatBoostFit(
            classifier, ranker, availability, manifest, _model_hash(classifier), ranker_hash
        )
    if not np.all(np.isfinite(probability)):
        raise DiagnosticCatBoostRefusal("action classifier prediction coverage is incomplete")
    order_hash = hashlib.sha256("\n".join(canonical).encode()).hexdigest()
    fit_indices = rows.canonical_order(global_fit)
    split_hash = _payload_hash({
        "fit_candidate_id": np.asarray(rows.candidate_id, str)[fit_indices].tolist(),
        "fit_action": action[fit_indices].tolist(),
        "fit_mask": np.asarray(rows.action_loss_mask, bool)[fit_indices].tolist(),
        "chronology": rows.chronology,
        "eligible_development_days": rows.eligible_development_days,
    })
    prediction_roster_hash = _payload_hash({
        "candidate_id": np.asarray(rows.candidate_id, str).tolist(),
        "split": rows.frozen_split().tolist()})
    config_hash = _payload_hash({"version": PINNED_CATBOOST_VERSION,
                                 "classifier": _classifier_params(),
                                 "ranker": _ranker_params(),
                                 "minimum_pair_groups_per_asset":
                                     minimum_pair_groups_per_asset,
                                 "pair_semantics": "asset-day-phase"})
    payload = {"representation_sha256": rows.representation_sha256,
               "canonical_order_sha256": order_hash, "split_sha256": split_hash,
               "config_sha256": config_hash,
               "action_models": {a: fits[a].action_model_sha256 for a in EXACT_ASSETS},
               "ranker_models": {a: fits[a].ranker_model_sha256 for a in EXACT_ASSETS},
               "pair_manifests": {a: fits[a].pair_manifest.receipt_sha256 for a in EXACT_ASSETS},
               "pair_representation_sha256": pair_rows.representation_sha256,
               "prediction_roster_sha256": prediction_roster_hash,
               "action_weight_receipt_sha256": weight_receipt.receipt_sha256,
               "action_weight_law": "entry-v2-action-fit-weights-v1"}
    return DiagnosticCatBoostFit(fits, probability, rank_score,
                                 rows.representation_sha256, order_hash,
                                 split_hash, config_hash,
                                 weight_receipt.receipt_sha256,
                                 _payload_hash(payload))


@dataclass(frozen=True)
class CatBoostCompetenceResult:
    auroc_by_asset: Mapping[str, float]
    ap_by_asset: Mapping[str, float]
    bce_by_asset: Mapping[str, float]
    pair_accuracy_by_asset: Mapping[str, float | None]
    representation_sha256: str
    candidate_id: np.ndarray
    action_probability: np.ndarray
    rank_score: np.ndarray
    ranker_availability_by_asset: Mapping[str, str]
    pair_manifest_sha256_by_asset: Mapping[str, str]
    pair_group_count_by_asset: Mapping[str, int]
    pair_row_manifest_sha256: str
    row_manifest_sha256: str
    receipt_sha256: str


def rehearse_catboost_competence(
    rows: FrozenRepresentationRows, *, expected_representation_sha256: str,
    pair_rows: FrozenRepresentationRows | None = None,
    fitted: DiagnosticCatBoostFit | None = None,
) -> CatBoostCompetenceResult:
    fit = fitted or fit_diagnostic_catboost(
        rows, expected_representation_sha256=expected_representation_sha256,
        pair_rows=pair_rows,
    )
    if (fit.representation_sha256 != expected_representation_sha256
            or len(fit.action_probability) != len(rows.candidate_id)
            or len(fit.rank_score) != len(rows.candidate_id)):
        raise DiagnosticCatBoostRefusal("prefitted competence model/rows differ")
    pair_rows = rows if pair_rows is None else pair_rows
    y = np.asarray(rows.action_target, int); assets = np.asarray(rows.asset, str)
    split = rows.frozen_split() == "FIT"; mask = np.asarray(rows.action_loss_mask, bool)
    auroc: dict[str, float] = {}; ap: dict[str, float] = {}; bce: dict[str, float] = {}
    pair_accuracy: dict[str, float | None] = {}
    for asset in EXACT_ASSETS:
        idx = np.flatnonzero((assets == asset) & split & mask)
        if min(np.sum(y[idx] == 0), np.sum(y[idx] == 1)) < 32:
            raise DiagnosticCatBoostRefusal(f"{asset} competence slice lacks 32/32 actions")
        p = fit.action_probability[idx]
        auroc[asset] = float(roc_auc_score(y[idx], p))
        ap[asset] = float(average_precision_score(y[idx], p))
        bce[asset] = float(log_loss(y[idx], p, labels=[0, 1]))
        asset_fit = fit.assets[asset]
        if asset_fit.ranker_model is None:
            pair_accuracy[asset] = None
        else:
            manifest = asset_fit.pair_manifest
            scores = np.asarray(asset_fit.ranker_model.predict(
                np.asarray(pair_rows.representation, np.float32)[manifest.indices]), np.float64)
            pair_accuracy[asset] = float(np.mean([scores[a] > scores[b]
                                                  for a, b in manifest.pairs]))
    if (min(auroc.values()) < .995 or min(ap.values()) < .995
            or max(bce.values()) > .02
            or any(value is None for value in pair_accuracy.values())
            or min(float(value) for value in pair_accuracy.values()
                   if value is not None) < .995):
        raise DiagnosticCatBoostRefusal("CatBoost competence thresholds were not reached")
    payload = {"auroc": auroc, "ap": ap, "bce": bce,
               "pair_accuracy": pair_accuracy,
               "representation_sha256": rows.representation_sha256,
               "fit_receipt_sha256": fit.receipt_sha256}
    candidate_id = np.asarray(rows.candidate_id, str).copy()
    probability = np.asarray(fit.action_probability, np.float64).copy()
    rank_score = np.asarray(fit.rank_score, np.float64).copy()
    candidate_id.setflags(write=False); probability.setflags(write=False)
    rank_score.setflags(write=False)
    availability = {asset: fit.assets[asset].ranker_availability.value
                    for asset in EXACT_ASSETS}
    pair_hashes = {asset: fit.assets[asset].pair_manifest.receipt_sha256
                   for asset in EXACT_ASSETS}
    pair_counts = {asset: fit.assets[asset].pair_manifest.group_count
                   for asset in EXACT_ASSETS}
    pair_row_manifest = _payload_hash({
        "candidate_id": np.asarray(pair_rows.candidate_id, str).tolist(),
        "representation_sha256": pair_rows.representation_sha256,
        "phase": np.asarray(pair_rows.exact_time_group_id, str).tolist(),
        "pair_manifests": pair_hashes})
    row_manifest = _payload_hash({
        "candidate_id": candidate_id.tolist(),
        "representation_sha256": rows.representation_sha256,
        "action_probability_sha256": _array_hash(probability),
        "rank_score_sha256": _array_hash(rank_score),
        "pair_manifests": pair_hashes,
    })
    payload["row_manifest_sha256"] = row_manifest
    payload["pair_row_manifest_sha256"] = pair_row_manifest
    return CatBoostCompetenceResult(
        auroc, ap, bce, pair_accuracy, rows.representation_sha256,
        candidate_id, probability, rank_score, availability, pair_hashes,
        pair_counts, pair_row_manifest, row_manifest, _payload_hash(payload))


__all__ = [
    "AssetCatBoostFit", "CatBoostCompetenceResult", "DiagnosticCatBoostFit",
    "DiagnosticCatBoostRefusal", "EXACT_ASSETS", "ExactPairManifest",
    "FrozenRepresentationRows", "PINNED_CATBOOST_VERSION", "RankerAvailability",
    "exact_pair_manifest", "fit_diagnostic_catboost", "rehearse_catboost_competence",
]
