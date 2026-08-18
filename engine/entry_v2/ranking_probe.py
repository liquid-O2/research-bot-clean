"""Diagnostic-only pooled PairLogit challenger for the sealed E3 fold."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
from time import perf_counter
from typing import Any, Mapping, Sequence

import catboost
from catboost import CatBoostRanker, Pool
import numpy as np

from . import common as C
from .representation_probe import (
    ASSETS, CALIBRATION_DAYS, DEFAULT_FOLD, FIT_DAYS, SEED, TEST_DAYS,
    EXPECTED_AGGREGATE_SHA256, MonotonePlatt, ProbeRows, _evaluation_receipt, _scored_rows,
    _sessions, _sha256_array, _sha256_ids, _split_receipt,
    _split_score_diagnostics, assert_fast_sweep_parity, fast_threshold_sweep,
    load_e3_rows, normalize_from_fit, select_thresholds, split_rows,
)
from .replay import replay


REPRESENTATIONS = ("static", "embedding", "late_fusion")


@dataclass(frozen=True)
class RankerConfig:
    loss_function: str = "PairLogit"
    iterations: int = 500
    depth: int = 8
    learning_rate: float = 0.03
    l2_leaf_reg: float = 3.0
    random_seed: int = SEED
    random_strength: float = 0.0
    bootstrap_type: str = "No"
    thread_count: int = 32
    task_type: str = "CPU"

    def catboost_params(self) -> Mapping[str, Any]:
        return {"loss_function": self.loss_function, "iterations": self.iterations,
            "depth": self.depth, "learning_rate": self.learning_rate,
            "l2_leaf_reg": self.l2_leaf_reg, "random_seed": self.random_seed,
            "random_strength": self.random_strength,
            "bootstrap_type": self.bootstrap_type, "thread_count": self.thread_count,
            "task_type": self.task_type, "allow_writing_files": False,
            "verbose": False}


PRODUCTION_CONFIG = RankerConfig()


def feature_matrix(rows: ProbeRows, representation: str) -> np.ndarray:
    if representation == "static":
        result = rows.static_features
    elif representation == "embedding":
        result = rows.embeddings
    elif representation == "late_fusion":
        result = np.concatenate((rows.embeddings, rows.static_features), axis=1)
    else:
        raise C.EntryV2Refusal(f"unknown ranking representation: {representation}")
    result = np.ascontiguousarray(result, dtype=np.float32)
    if result.ndim != 2 or not np.all(np.isfinite(result)):
        raise C.EntryV2Refusal("ranking features are not a finite matrix")
    return result


@dataclass(frozen=True)
class RankingPool:
    indices: np.ndarray
    group_ids: np.ndarray
    pairs: tuple[tuple[int, int], ...]
    group_count: int
    paired_group_count: int
    positive_rows: int
    negative_rows: int
    group_receipt_sha256: str
    pair_receipt_sha256: str


def prepare_ranking_pool(rows: ProbeRows) -> RankingPool:
    supervised = np.flatnonzero(rows.action_mask)
    if not len(supervised):
        raise C.EntryV2Refusal("PairLogit fit has no action-supervised rows")
    indices = np.asarray(sorted(supervised, key=lambda i: (
        rows.assets[int(i)], int(rows.days[int(i)]), rows.candidate_ids[int(i)]
    )), dtype=np.int64)
    group_ids = np.empty(len(indices), dtype=np.int64)
    groups: list[tuple[str, int, tuple[str, ...]]] = []
    pairs: list[tuple[int, int]] = []
    cursor = 0
    group_number = 0
    paired_groups = 0
    while cursor < len(indices):
        first = int(indices[cursor])
        key = (rows.assets[first], int(rows.days[first]))
        end = cursor + 1
        while end < len(indices):
            candidate = int(indices[end])
            if (rows.assets[candidate], int(rows.days[candidate])) != key:
                break
            end += 1
        group_ids[cursor:end] = group_number
        positives = [local for local in range(cursor, end)
                     if rows.action[int(indices[local])]]
        negatives = [local for local in range(cursor, end)
                     if not rows.action[int(indices[local])]]
        if positives and negatives:
            paired_groups += 1
            pairs.extend((positive, negative) for positive in positives
                         for negative in negatives)
        groups.append((key[0], key[1], tuple(
            rows.candidate_ids[int(indices[local])] for local in range(cursor, end)
        )))
        group_number += 1
        cursor = end
    if not pairs:
        raise C.EntryV2Refusal("PairLogit fit generated no within-group pairs")
    # Pair indices are local Pool row indices and must never cross a group.
    if any(group_ids[winner] != group_ids[loser] for winner, loser in pairs):
        raise C.EntryV2Refusal("PairLogit generated a cross-group pair")
    return RankingPool(indices, group_ids, tuple(pairs), group_number,
        paired_groups, int(rows.action[indices].sum()),
        int((~rows.action[indices]).sum()),
        hashlib.sha256(C.canonical_bytes(groups)).hexdigest(),
        hashlib.sha256(C.canonical_bytes(pairs)).hexdigest())


@dataclass
class FittedRanker:
    model: CatBoostRanker
    pool: RankingPool
    config: RankerConfig
    fit_seconds: float


def fit_ranker(rows: ProbeRows, features: np.ndarray,
               config: RankerConfig = PRODUCTION_CONFIG) -> FittedRanker:
    if len(features) != len(rows.candidate_ids):
        raise C.EntryV2Refusal("ranking feature/row length mismatch")
    prepared = prepare_ranking_pool(rows)
    pool = Pool(
        data=features[prepared.indices],
        label=rows.action[prepared.indices].astype(np.float32),
        group_id=prepared.group_ids,
        pairs=list(prepared.pairs),
    )
    model = CatBoostRanker(**config.catboost_params())
    started = perf_counter()
    model.fit(pool)
    return FittedRanker(model, prepared, config, perf_counter() - started)


def predict_ranker(fitted: FittedRanker, features: np.ndarray) -> np.ndarray:
    prediction = np.asarray(fitted.model.predict(features), dtype=np.float64)
    if prediction.shape != (len(features),) or not np.all(np.isfinite(prediction)):
        raise C.EntryV2Refusal("PairLogit produced invalid predictions")
    return prediction


def _sweep_row(sweep: Any, index: int) -> Mapping[str, Any]:
    return {"index": int(index), "threshold": float(sweep.thresholds[index]),
        "trades": int(sweep.trades[index]),
        "total_pnl_usd": float(sweep.total_pnl_usd[index]),
        "usd_per_trade": float(sweep.usd_per_trade[index]),
        "usd_per_asset_day": float(sweep.usd_per_asset_day[index]),
        "max_drawdown_usd": float(sweep.max_drawdown_usd[index]),
        "drawdown_p90_usd": float(sweep.drawdown_p90_usd[index])}


def _sweep_key(sweep: Any, index: int) -> tuple[float, float, float, float, float, int]:
    return (float(sweep.usd_per_asset_day[index]),
            float(sweep.usd_per_trade[index]),
            -float(sweep.max_drawdown_usd[index]),
            -float(sweep.drawdown_p90_usd[index]),
            float(sweep.thresholds[index]), int(sweep.trades[index]))


def hindsight_test_diagnostic(fold: Any, indices: np.ndarray,
                              probability: np.ndarray) -> Mapping[str, Any]:
    """Test-label economics, explicitly forbidden from selected policy decisions."""
    result: dict[str, Any] = {"label": "HINDSIGHT_DIAGNOSTIC_ONLY",
                             "used_for_selected_policy": False, "by_asset": {}}
    for asset in ASSETS:
        local = np.flatnonzero(np.asarray([fold.assets[int(i)] == asset for i in indices]))
        arrivals = tuple(fold.truth_arrivals[int(i)] for i in indices[local])
        sessions = _sessions(fold, *TEST_DAYS, asset)
        sweep = fast_threshold_sweep(arrivals, probability[local], sessions)
        parity = assert_fast_sweep_parity(
            arrivals, probability[local], sessions, sweep, samples=9
        )
        feasible = ((sweep.trades > 0)
                    & (sweep.usd_per_trade >= C.MIN_EXPECTANCY_USD)
                    & (sweep.max_drawdown_usd <= C.TARGET_MDD_USD))
        feasible_indices = np.flatnonzero(feasible)
        # A zero-trade sentinel scores exactly (0.0, 0.0, -0.0, -0.0, ...) and
        # therefore WON this argmax over any genuinely negative threshold, so
        # "best unconstrained" could be an empty book.  Zero-trade rows are
        # typed out of the comparison entirely.
        traded_indices = [i for i in range(len(sweep.thresholds))
                          if int(sweep.trades[i]) > 0]
        unconstrained_index = (max(traded_indices, key=lambda i: _sweep_key(sweep, i))
                               if traded_indices else None)
        best_feasible = (None if not len(feasible_indices) else _sweep_row(
            sweep, max(feasible_indices, key=lambda i: _sweep_key(sweep, int(i)))
        ))
        result["by_asset"][asset] = {
            "threshold_count": len(sweep.thresholds),
            "fast_replay_parity_sha256": parity,
            "best_feasible": best_feasible,
            "best_feasible_reason": (None if best_feasible is not None
                                     else "NO_FEASIBLE_THRESHOLD"),
            "best_unconstrained": (None if unconstrained_index is None
                                   else _sweep_row(sweep, unconstrained_index)),
            "best_unconstrained_reason": (None if unconstrained_index is not None
                                          else "NO_THRESHOLD_PRODUCES_A_TRADE"),
            "zero_trade_thresholds_excluded":
                len(sweep.thresholds) - len(traded_indices),
            "all_thresholds": [_sweep_row(sweep, i)
                               for i in range(len(sweep.thresholds))],
        }
    return result


def _save_model(model: CatBoostRanker, path: Path) -> Mapping[str, Any]:
    if path.exists():
        raise C.EntryV2Refusal(f"ranking model artifact exists: {path}")
    model.save_model(str(path), format="cbm")
    with open(path, "rb") as handle:
        raw = handle.read()
    with open(path, "rb") as handle:
        os.fsync(handle.fileno())
    return {"file": path.name, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def run_ranking_probe(path: str | Path = DEFAULT_FOLD, *, artifact_dir: Path
                      ) -> Mapping[str, Any]:
    started = perf_counter()
    if catboost.__version__ != "1.2.10":
        raise C.EntryV2Refusal(
            f"ranking probe pins catboost 1.2.10, got {catboost.__version__}"
        )
    fold, original = load_e3_rows(path)
    splits = split_rows(original)
    rows, normalization = normalize_from_fit(original, splits["fit"])
    truth_arrivals = tuple(fold.truth_arrivals[int(i)] for i in splits["test"])
    truth = replay(truth_arrivals, expected_sessions=_sessions(fold, *TEST_DAYS))
    receipt: dict[str, Any] = {
        "schema": "entry-v2-e3-pairlogit-ranking-probe-v1",
        "diagnostic_only": True, "fold": "E3", "control": "PROPHET",
        "fold_store_aggregate_sha256": EXPECTED_AGGREGATE_SHA256,
        "catboost_version": catboost.__version__,
        "objective": "PairLogit", "pooled_across_assets": True,
        "fit_scope": "action-supervised Jul-Sep rows only",
        "config": PRODUCTION_CONFIG.catboost_params(),
        "splits": _split_receipt(rows, splits), "normalization": normalization,
        "identity": {"candidate_ids_sha256": _sha256_ids(rows.candidate_ids),
            "action_mask_sha256": _sha256_array(rows.action_mask),
            "action_sha256": _sha256_array(rows.action),
            "days_sha256": _sha256_array(rows.days),
            "normalized_static_sha256": _sha256_array(rows.static_features),
            "normalized_embedding_sha256": _sha256_array(rows.embeddings)},
        "truth_control": _evaluation_receipt(truth), "representations": {},
    }
    fit_rows = rows.take(splits["fit"])
    artifact_dir.mkdir(parents=True, exist_ok=True)
    for representation in REPRESENTATIONS:
        representation_started = perf_counter()
        all_features = feature_matrix(rows, representation)
        fit_features = all_features[splits["fit"]]
        fitted = fit_ranker(fit_rows, fit_features)
        logits = {name: predict_ranker(fitted, all_features[indices])
                  for name, indices in splits.items()}
        calibration_rows = rows.take(splits["calibration"])
        supervised = calibration_rows.action_mask
        calibrator = MonotonePlatt.fit(
            logits["calibration"][supervised],
            calibration_rows.action[supervised].astype(float),
        )
        probability = {name: calibrator.predict(value) for name, value in logits.items()}
        thresholds, calibration_funnel = select_thresholds(
            fold, splits["calibration"], probability["calibration"]
        )
        test_arrivals = _scored_rows(
            fold, splits["test"], probability["test"], thresholds,
            f"e3-pairlogit:{representation}"
        )
        selected_test = replay(
            test_arrivals, expected_sessions=_sessions(fold, *TEST_DAYS)
        )
        artifact = _save_model(fitted.model, artifact_dir / f"{representation}.cbm")
        pool = fitted.pool
        receipt["representations"][representation] = {
            "feature_columns": all_features.shape[1],
            "feature_sha256": _sha256_array(all_features),
            "fit_feature_sha256": _sha256_array(fit_features),
            "prediction_sha256": {name: _sha256_array(value)
                                  for name, value in logits.items()},
            "model": artifact,
            "model_config_sha256": hashlib.sha256(C.canonical_bytes(
                fitted.config.catboost_params())).hexdigest(),
            "groups": {"group_count": pool.group_count,
                "group_key": "(asset,trading_day)",
                "paired_group_count": pool.paired_group_count,
                "pair_count": len(pool.pairs), "positive_rows": pool.positive_rows,
                "negative_rows": pool.negative_rows,
                "group_receipt_sha256": pool.group_receipt_sha256,
                "pair_receipt_sha256": pool.pair_receipt_sha256},
            "platt": {"slope": calibrator.slope, "intercept": calibrator.intercept},
            "thresholds": dict(thresholds),
            "calibration_funnel": calibration_funnel,
            # V4: publish the typed threshold status beside the economics so a
            # NO_FEASIBLE_THRESHOLD empty book is never read as a clean $0 row.
            "threshold_status_by_asset": {
                asset: calibration_funnel[asset]["status"]
                for asset in calibration_funnel},
            "economics_publishable": all(
                calibration_funnel[asset]["economics_publishable"]
                for asset in calibration_funnel),
            "score_diagnostics": {name: _split_score_diagnostics(
                rows.take(splits[name]), logits[name], probability[name]
            ) for name in ("fit", "calibration", "test")},
            "selected_test_replay": _evaluation_receipt(selected_test),
            "hindsight_test_sweep": hindsight_test_diagnostic(
                fold, splits["test"], probability["test"]),
            "runtime_seconds": {"fit": fitted.fit_seconds,
                "representation_total": perf_counter() - representation_started},
        }
    receipt["runtime_seconds"] = {"total": perf_counter() - started}
    receipt["receipt_sha256_law"] = "sha256(canonical JSON before receipt_sha256 field)"
    receipt["receipt_sha256"] = hashlib.sha256(C.canonical_bytes(receipt)).hexdigest()
    return receipt


def _publish(path: str | Path, fold_path: str | Path) -> Mapping[str, Any]:
    target = C.assert_workspace_output(path)
    if target.exists():
        raise C.EntryV2Refusal(f"ranking diagnostic output exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.", dir=target.parent))
    published = False
    try:
        receipt = run_ranking_probe(fold_path, artifact_dir=temporary)
        receipt_path = temporary / "receipt.json"
        with open(receipt_path, "xb") as handle:
            handle.write(C.canonical_bytes(receipt))
            handle.flush()
            os.fsync(handle.fileno())
        for child in temporary.iterdir():
            os.chmod(child, 0o444)
        os.rename(temporary, target)
        os.chmod(target, 0o555)
        directory_fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        published = True
        return receipt
    finally:
        if not published and temporary.exists():
            shutil.rmtree(temporary)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diagnostic-only E3 PairLogit probe")
    parser.add_argument("--fold", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    _publish(args.output, args.fold)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
