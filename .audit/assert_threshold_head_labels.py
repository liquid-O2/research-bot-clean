#!/usr/bin/env python3
"""Predict-only head-versus-label receipt for the frozen E1R regret head.

Walks never ENTER. Labels mark ENTER optimal on 7.7% of fit rows. This
script asks whether the fitted head ever ranks ENTER as the strict min on
those same stored rows. No training.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

import numpy as np

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from engine.entry_v2.tabular_matrix_store import load_action_matrix
from engine.entry_v2.tabular_model_io import load_action_model, predict_action_regret

ROUND2 = REPO / (
    "artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/"
    "e1r/curriculum/fits/round_2"
)
ROSTER = ROUND2 / "action_real_roster.json"
MATRICES = ROUND2 / "action_matrices/real"
RECEIPT = REPO / ".audit/threshold-head-labels-20260826.json"
FROZEN_FOLD = "FROZEN_Q3_E8"
NAMED_CAUSE = "e1r_regret_head_never_prefers_enter_on_any_walked_window"
CHECK = "python3 .audit/assert_threshold_head_labels.py"
HEALTHY_FRACTION_OF_LABEL = 0.5


def enter_is_strict_min(regret: np.ndarray) -> np.ndarray:
    if regret.ndim != 2 or regret.shape[1] != 3:
        raise ValueError(
            f"regret must be (n, 3), got shape {tuple(regret.shape)}"
        )
    enter = regret[:, 0]
    return (enter < regret[:, 1]) & (enter < regret[:, 2])


def enter_margin_usd(regret: np.ndarray) -> np.ndarray:
    if regret.ndim != 2 or regret.shape[1] != 3:
        raise ValueError(
            f"regret must be (n, 3), got shape {tuple(regret.shape)}"
        )
    return np.minimum(regret[:, 1], regret[:, 2]) - regret[:, 0]


def _rate(count: int, n: int) -> float:
    if n < 0:
        raise ValueError(f"n must be >= 0, got {n}")
    if n == 0:
        return 0.0
    return float(count) / float(n)


def _margin_stats(values: np.ndarray) -> dict[str, float]:
    if values.size == 0:
        return {"mean": 0.0, "p50": 0.0, "pmax": 0.0}
    return {
        "mean": float(np.mean(values)),
        "p50": float(np.quantile(values, 0.5)),
        "pmax": float(np.max(values)),
    }


def summarize_slice(
    *,
    labels: np.ndarray,
    pred_regret: np.ndarray,
    label_margin_usd: np.ndarray,
) -> dict[str, Any]:
    n = int(len(labels))
    if pred_regret.shape != (n, 3):
        raise ValueError(
            f"pred_regret shape {tuple(pred_regret.shape)} != ({n}, 3)"
        )
    if label_margin_usd.shape != (n,):
        raise ValueError(
            f"label_margin_usd shape {tuple(label_margin_usd.shape)} != ({n},)"
        )
    pred_enter = enter_is_strict_min(pred_regret)
    label_enter = np.asarray(labels) == "ENTER"
    return {
        "n_rows": n,
        "label_enter_count": int(np.count_nonzero(label_enter)),
        "label_enter_rate": _rate(int(np.count_nonzero(label_enter)), n),
        "pred_enter_count": int(np.count_nonzero(pred_enter)),
        "pred_enter_rate": _rate(int(np.count_nonzero(pred_enter)), n),
        "label_margin_usd": _margin_stats(np.asarray(label_margin_usd, np.float64)),
        "pred_margin_usd": _margin_stats(enter_margin_usd(pred_regret)),
    }


def _roster_folds(roster: Mapping[str, Any], seed: int) -> list[dict[str, Any]]:
    matches = [
        row for row in roster["rosters"]
        if int(row["seed"]) == seed and not bool(row["shuffled_labels"])
    ]
    if len(matches) != 1:
        raise ValueError(
            f"roster must have one real ACTION roster for seed {seed}, "
            f"got {len(matches)}"
        )
    return list(matches[0]["folds"])


def _fold_for_day(
    folds: list[dict[str, Any]], day: int
) -> dict[str, Any] | None:
    matches = [
        row for row in folds
        if int(row["score_range"][0]) <= day <= int(row["score_range"][1])
    ]
    if len(matches) > 1:
        names = [row["name"] for row in matches]
        raise ValueError(
            f"day {day} matched multiple folds {names}, expected 0 or 1"
        )
    return matches[0] if matches else None


def score_seed(roster: Mapping[str, Any], seed: int) -> dict[str, Any]:
    matrix_dir = MATRICES / f"seed_{seed}"
    if not matrix_dir.is_dir():
        raise FileNotFoundError(f"action matrix missing: {matrix_dir}")
    matrix = load_action_matrix(matrix_dir)
    x = np.asarray(matrix.x)
    days = np.asarray(matrix.day, np.int64)
    labels = np.asarray(matrix.optimal_action)
    label_margin = np.asarray(matrix.action_margin_cents, np.float64) / 100.0
    folds = _roster_folds(roster, seed)
    models: dict[str, Any] = {}
    for row in folds:
        model = load_action_model(row["bundle_path"])
        receipt = getattr(model, "receipt_sha256", None)
        if receipt != row["bundle_receipt_sha256"]:
            raise ValueError(
                f"seed {seed} fold {row['name']} receipt "
                f"{receipt!r} != roster {row['bundle_receipt_sha256']!r}"
            )
        models[str(row["name"])] = model
    if FROZEN_FOLD not in models:
        raise ValueError(
            f"seed {seed} roster missing {FROZEN_FOLD}, "
            f"got {sorted(models)}"
        )
    oof_regret = np.full((len(x), 3), np.nan, np.float64)
    routed = np.zeros(len(x), dtype=bool)
    by_fold: dict[str, list[int]] = {}
    for index, day in enumerate(days.tolist()):
        fold = _fold_for_day(folds, int(day))
        if fold is None:
            continue
        by_fold.setdefault(str(fold["name"]), []).append(index)
        routed[index] = True
    for name, indices in by_fold.items():
        idx = np.asarray(indices, np.int64)
        pred = predict_action_regret(
            models[name], x[idx], trading_day=int(days[idx[0]])
        )
        if pred.shape != (len(idx), 3):
            raise ValueError(
                f"seed {seed} fold {name} predict shape "
                f"{tuple(pred.shape)} != ({len(idx)}, 3)"
            )
        oof_regret[idx] = pred
    frozen_day = int(
        next(
            row["score_range"][0]
            for row in folds
            if row["name"] == FROZEN_FOLD
        )
    )
    frozen_all = predict_action_regret(
        models[FROZEN_FOLD], x, trading_day=frozen_day
    )
    oof = summarize_slice(
        labels=labels[routed],
        pred_regret=oof_regret[routed],
        label_margin_usd=label_margin[routed],
    )
    frozen = summarize_slice(
        labels=labels,
        pred_regret=frozen_all,
        label_margin_usd=label_margin,
    )
    return {
        "seed": seed,
        "n_rows": int(len(x)),
        "n_oof_rows": int(np.count_nonzero(routed)),
        "n_unrouted_rows": int(len(x) - np.count_nonzero(routed)),
        "oof_folds_used": sorted(by_fold),
        "oof": oof,
        "frozen_all_rows": frozen,
        "frozen_bundle_sha256": next(
            row["bundle_receipt_sha256"]
            for row in folds
            if row["name"] == FROZEN_FOLD
        ),
    }


def build_receipt(seeds: tuple[int, ...]) -> dict[str, Any]:
    if not ROSTER.is_file():
        raise FileNotFoundError(f"action roster missing: {ROSTER}")
    roster = json.loads(ROSTER.read_text())
    if roster.get("schema") != "QRE2TABSEEDROSTER4":
        raise ValueError(
            f"{ROSTER} schema {roster.get('schema')!r} != QRE2TABSEEDROSTER4"
        )
    by_seed = {str(seed): score_seed(roster, seed) for seed in seeds}
    label_rates = [
        float(row["frozen_all_rows"]["label_enter_rate"])
        for row in by_seed.values()
    ]
    frozen_rates = [
        float(row["frozen_all_rows"]["pred_enter_rate"])
        for row in by_seed.values()
    ]
    label_rate = float(label_rates[0]) if label_rates else 0.0
    if any(abs(rate - label_rate) > 1e-12 for rate in label_rates):
        raise ValueError(f"label ENTER rate differs across seeds: {label_rates}")
    max_frozen = max(frozen_rates) if frozen_rates else 0.0
    healthy = max_frozen >= HEALTHY_FRACTION_OF_LABEL * label_rate and (
        label_rate > 0.0
    )
    return {
        "schema": "QRE2THRESHOLDHEADLABEL1",
        "named_cause": NAMED_CAUSE,
        "check_command": CHECK,
        "roster": str(ROSTER.relative_to(REPO)),
        "label_enter_rate": label_rate,
        "healthy_fraction_of_label": HEALTHY_FRACTION_OF_LABEL,
        "max_frozen_pred_enter_rate": max_frozen,
        "healthy_in_sample": healthy,
        "cause_retracts_to_feature_mismatch": healthy,
        "by_seed": by_seed,
    }


def _selftest() -> int:
    labels = np.asarray(["ENTER", "DEFER", "PASS", "PASS"], str)
    pred = np.asarray(
        [
            [1.0, 2.0, 3.0],
            [3.0, 1.0, 2.0],
            [3.0, 2.0, 1.0],
            [0.5, 0.6, 0.7],
        ],
        np.float64,
    )
    margin = np.asarray([10.0, 4.0, 2.0, 1.0], np.float64)
    row = summarize_slice(
        labels=labels, pred_regret=pred, label_margin_usd=margin
    )
    if row["n_rows"] != 4:
        raise AssertionError(f"selftest n_rows {row['n_rows']} != 4")
    if row["label_enter_count"] != 1 or abs(row["label_enter_rate"] - 0.25) > 1e-12:
        raise AssertionError(f"selftest label ENTER {row!r}")
    if row["pred_enter_count"] != 2 or abs(row["pred_enter_rate"] - 0.5) > 1e-12:
        raise AssertionError(f"selftest pred ENTER {row!r}")
    if abs(row["pred_margin_usd"]["pmax"] - 1.0) > 1e-12:
        raise AssertionError(f"selftest pred margin {row['pred_margin_usd']!r}")
    dead = summarize_slice(
        labels=labels,
        pred_regret=np.asarray(
            [[5.0, 1.0, 2.0]] * 4, np.float64
        ),
        label_margin_usd=margin,
    )
    if dead["pred_enter_count"] != 0:
        raise AssertionError(f"selftest dead head must never ENTER, got {dead!r}")
    print("selftest_ok")
    return 0


def main() -> int:
    if "--selftest" in sys.argv[1:]:
        return _selftest()
    seeds = (20260820, 20260821, 20260822, 20260823, 20260824)
    if "--seed" in sys.argv[1:]:
        at = sys.argv.index("--seed")
        if at + 1 >= len(sys.argv):
            raise ValueError("--seed needs an integer, argv ended")
        seeds = (int(sys.argv[at + 1]),)
    receipt = build_receipt(seeds)
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
