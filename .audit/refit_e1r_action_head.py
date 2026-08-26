#!/usr/bin/env python3
"""Refit the E1R FROZEN_Q3_E8 action head on stored matrices. Predict only after fit.

H1 MultiClass and H2 PairLogit use the frozen fold days as-is. H3 keeps those
days and inverse-frequency weights ENTER so its train mass matches non-ENTER.
H4 accepts one milder ENTER scale on the same MultiClass chronology. The frozen
train slice is 3.28% ENTER. Unweighted MultiClass logloss is mostly DEFER/PASS.
H5 uses the official E1R FIT and PLATT walls with unweighted MultiClass.
H7 combines the official walls with inverse-frequency ENTER weights.
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from engine.entry_v2.tabular_matrix_store import load_action_matrix
from engine.entry_v2.tabular_model_action import (
    fit_action_bundle,
    fit_pairwise_action_bundle,
)
from engine.entry_v2.tabular_model_io import load_action_model, predict_action_regret
from engine.entry_v2.tabular_recovery_contracts import RecoveryConfig
from engine.entry_v2.tabular_training import ActionTrainingMatrix

ROUND2 = REPO / (
    "artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/"
    "e1r/curriculum/fits/round_2"
)
MATRICES = ROUND2 / "action_matrices/real"
FROZEN_BUNDLE = (
    ROUND2 / "action_models/catboost/real/seed_20260820/"
    "FROZEN_Q3_E8/action_MultiRMSE"
)
OUT_ROOT = REPO / "artifacts/cache/threshold_refit"
RECEIPTS = {
    "MultiClass": REPO / ".audit/threshold-refit-h1-multiclass.json",
    "PairLogitPairwise": REPO / ".audit/threshold-refit-h2-pairwise.json",
    "MultiClassEnterBalance": (
        REPO / ".audit/threshold-refit-h3-enter-balance.json"
    ),
    "MultiClassEnterMild": REPO / ".audit/threshold-refit-h4-mild-enter.json",
    "MultiClassOfficialE1R": (
        REPO / ".audit/threshold-refit-h5-official-e1r.json"
    ),
    "PairLogitPairwiseEnterBalance": (
        REPO / ".audit/threshold-refit-h6-pairwise-enter.json"
    ),
    "MultiClassOfficialEnterBalance": (
        REPO / ".audit/threshold-refit-h7-official-enter.json"
    ),
}
TRAIN_DAYS = (20210610, 20210701)
VAL_DAYS = (20210702, 20210709)
SCORE_DAYS = (20210712, 20210831)
OFFICIAL_FIT_DAYS = (20210531, 20210709)
OFFICIAL_PLATT_DAYS = (20210712, 20210720)
OFFICIAL_THRESHOLD_DAYS = (20210721, 20210806)
SEED = 20260820
CHECK = "python3 .audit/refit_e1r_action_head.py"


def _range_mask(day: np.ndarray, bounds: tuple[int, int]) -> np.ndarray:
    lo, hi = bounds
    values = np.asarray(day, np.int64)
    return (values >= lo) & (values <= hi)


def enter_is_strict_min(regret: np.ndarray) -> np.ndarray:
    if regret.ndim != 2 or regret.shape[1] != 3:
        raise ValueError(f"regret must be (n, 3), got {tuple(regret.shape)}")
    enter = regret[:, 0]
    return (enter < regret[:, 1]) & (enter < regret[:, 2])


def enter_balance_scale(actions: np.ndarray) -> float:
    labels = np.asarray(actions)
    n_enter = int(np.count_nonzero(labels == "ENTER"))
    n_other = int(len(labels) - n_enter)
    if n_enter == 0:
        raise ValueError(f"no ENTER labels in {len(labels)} rows")
    return float(n_other) / float(n_enter)


def with_enter_balance(
    matrix: ActionTrainingMatrix, scale: float
) -> ActionTrainingMatrix:
    if scale <= 0.0:
        raise ValueError(f"enter balance scale must be > 0, got {scale}")
    weights = np.asarray(matrix.sample_weight, np.float64).copy()
    enter = np.asarray(matrix.optimal_action) == "ENTER"
    weights[enter] *= scale
    balanced = replace(matrix, sample_weight=weights)
    balanced.validate()
    return balanced


def summarize(labels: np.ndarray, pred: np.ndarray) -> dict[str, Any]:
    n = int(len(labels))
    if pred.shape != (n, 3):
        raise ValueError(f"pred shape {tuple(pred.shape)} != ({n}, 3)")
    label_enter = np.asarray(labels) == "ENTER"
    pred_enter = enter_is_strict_min(pred)
    return {
        "n_rows": n,
        "label_enter_count": int(np.count_nonzero(label_enter)),
        "label_enter_rate": (
            float(np.count_nonzero(label_enter)) / n if n else 0.0
        ),
        "pred_enter_count": int(np.count_nonzero(pred_enter)),
        "pred_enter_rate": (
            float(np.count_nonzero(pred_enter)) / n if n else 0.0
        ),
    }


def _score(
    model: Any, matrix: Any, bounds: tuple[int, int]
) -> dict[str, Any]:
    keep = _range_mask(matrix.day, bounds)
    if not np.any(keep):
        return {
            "n_rows": 0,
            "label_enter_count": 0,
            "label_enter_rate": 0.0,
            "pred_enter_count": 0,
            "pred_enter_rate": 0.0,
        }
    x = np.asarray(matrix.x)[keep]
    labels = np.asarray(matrix.optimal_action)[keep]
    days = np.asarray(matrix.day, np.int64)[keep]
    pred = predict_action_regret(model, x, trading_day=int(days[0]))
    return summarize(labels, pred)


def score_model(
    model: Any,
    matrix: Any,
    *,
    train_days: tuple[int, int] = TRAIN_DAYS,
    validation_days: tuple[int, int] = VAL_DAYS,
    score_days: tuple[int, int] = SCORE_DAYS,
) -> dict[str, Any]:
    return {
        "train": _score(model, matrix, train_days),
        "validation": _score(model, matrix, validation_days),
        "score_range": _score(model, matrix, score_days),
        "all_rows": summarize(
            np.asarray(matrix.optimal_action),
            predict_action_regret(
                model,
                np.asarray(matrix.x),
                trading_day=int(score_days[0]),
            ),
        ),
    }


def main() -> int:
    if "--selftest" in sys.argv[1:]:
        dummy = np.asarray(
            [[1.0, 2.0, 3.0], [3.0, 1.0, 2.0]], np.float64
        )
        row = summarize(np.asarray(["ENTER", "DEFER"]), dummy)
        if row["pred_enter_count"] != 1:
            raise AssertionError(f"selftest pred ENTER {row!r}")
        scale = enter_balance_scale(np.asarray(["ENTER", "DEFER", "PASS"]))
        if abs(scale - 2.0) > 1e-12:
            raise AssertionError(f"selftest enter scale {scale}")
        days = np.asarray(
            [20210531, 20210709, 20210712, 20210720, 20210721, 20210806]
        )
        counts = tuple(
            int(np.count_nonzero(_range_mask(days, bounds)))
            for bounds in (
                OFFICIAL_FIT_DAYS,
                OFFICIAL_PLATT_DAYS,
                OFFICIAL_THRESHOLD_DAYS,
            )
        )
        if counts != (2, 2, 2):
            raise AssertionError(f"selftest official E1R walls {counts}")
        print("selftest_ok")
        return 0
    matrix_dir = MATRICES / f"seed_{SEED}"
    if not matrix_dir.is_dir():
        raise FileNotFoundError(f"action matrix missing: {matrix_dir}")
    matrix = load_action_matrix(matrix_dir)
    if "--baseline" in sys.argv[1:]:
        frozen = load_action_model(FROZEN_BUNDLE)
        payload = {
            "schema": "QRE2THRESHOLDREFITH1",
            "hypothesis": "baseline_frozen_MultiRMSE",
            "seed": SEED,
            "objective": "MultiRMSE",
            "slices": score_model(frozen, matrix),
            "check_command": CHECK + " --baseline",
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    objective = "MultiClass"
    if "--objective" in sys.argv[1:]:
        at = sys.argv.index("--objective")
        if at + 1 >= len(sys.argv):
            raise ValueError("--objective needs MultiClass or PairLogitPairwise")
        objective = str(sys.argv[at + 1])
    if objective not in {"MultiClass", "PairLogitPairwise"}:
        raise ValueError(
            f"objective {objective!r} not in "
            f"('MultiClass', 'PairLogitPairwise')"
        )
    enter_balance = "--enter-balance" in sys.argv[1:]
    enter_scale_arg: float | None = None
    if "--enter-scale" in sys.argv[1:]:
        at = sys.argv.index("--enter-scale")
        if at + 1 >= len(sys.argv):
            raise ValueError("--enter-scale needs one positive number")
        enter_scale_arg = float(sys.argv[at + 1])
        if not np.isfinite(enter_scale_arg) or enter_scale_arg <= 0.0:
            raise ValueError(
                f"--enter-scale must be finite and > 0, got {enter_scale_arg}"
            )
    if enter_balance and enter_scale_arg is not None:
        raise ValueError("--enter-balance and --enter-scale are mutually exclusive")
    if enter_scale_arg is not None and objective != "MultiClass":
        raise ValueError(f"--enter-scale requires MultiClass, got {objective!r}")
    official_e1r = "--official-e1r" in sys.argv[1:]
    if official_e1r and (
        objective != "MultiClass"
        or enter_scale_arg is not None
    ):
        raise ValueError(
            "--official-e1r requires MultiClass without --enter-scale"
        )
    train_days = OFFICIAL_FIT_DAYS if official_e1r else TRAIN_DAYS
    validation_days = OFFICIAL_PLATT_DAYS if official_e1r else VAL_DAYS
    score_days = OFFICIAL_THRESHOLD_DAYS if official_e1r else SCORE_DAYS
    train = matrix.mask(_range_mask(matrix.day, train_days))
    validation = matrix.mask(_range_mask(matrix.day, validation_days))
    enter_scale = 1.0
    if enter_balance:
        enter_scale = enter_balance_scale(train.optimal_action)
    elif enter_scale_arg is not None:
        enter_scale = enter_scale_arg
    if enter_balance or enter_scale_arg is not None:
        train = with_enter_balance(train, enter_scale)
        validation = with_enter_balance(validation, enter_scale)
    config = RecoveryConfig()
    if official_e1r and enter_balance:
        slug = "multiclass_official_enter_balance"
        receipt_key = "MultiClassOfficialEnterBalance"
        hypothesis = "H7_MultiClass_official_E1R_enter_balance"
        check = (
            f"ENTRY_V2_PREDICT_THREADS=16 {CHECK} "
            "--official-e1r --enter-balance"
        )
    elif official_e1r:
        slug = "multiclass_official_e1r"
        receipt_key = "MultiClassOfficialE1R"
        hypothesis = "H5_MultiClass_unweighted_official_E1R_FIT_PLATT"
        check = f"{CHECK} --official-e1r"
    elif enter_scale_arg is not None:
        slug = "multiclass_enter_mild"
        receipt_key = "MultiClassEnterMild"
        hypothesis = "H4_MultiClass_mild_enter_same_chronology"
        check = f"{CHECK} --objective MultiClass --enter-scale {enter_scale_arg}"
    elif enter_balance and objective == "PairLogitPairwise":
        slug = "pairwise_enter_balance"
        receipt_key = "PairLogitPairwiseEnterBalance"
        hypothesis = "H6_PairLogitPairwise_enter_balance_same_chronology"
        check = (
            f"ENTRY_V2_PREDICT_THREADS=16 {CHECK} "
            "--objective PairLogitPairwise --enter-balance"
        )
    elif enter_balance:
        slug = "multiclass_enter_balance"
        receipt_key = "MultiClassEnterBalance"
        hypothesis = "H3_MultiClass_enter_balance_same_chronology"
        check = f"{CHECK} --objective MultiClass --enter-balance"
    elif objective == "PairLogitPairwise":
        slug = "pairwise"
        receipt_key = objective
        hypothesis = "H2_PairLogitPairwise_same_chronology"
        check = f"{CHECK} --objective {objective}"
    else:
        slug = "multiclass"
        receipt_key = objective
        hypothesis = "H1_MultiClass_same_chronology"
        check = f"{CHECK} --objective {objective}"
    bundle_dir = (
        OUT_ROOT / slug / f"seed_{SEED}" / "FROZEN_Q3_E8"
        / f"action_{objective}"
    )
    if bundle_dir.is_dir():
        bundle = load_action_model(bundle_dir)
        if (
            bundle.objective != objective
            or bundle.seed != SEED
            or bundle.train_receipt_sha256 != train.receipt_sha256
            or bundle.validation_receipt_sha256 != validation.receipt_sha256
        ):
            raise ValueError(
                f"existing bundle differs from requested fit: {bundle_dir}"
            )
        fitted = False
    elif objective == "PairLogitPairwise":
        bundle = fit_pairwise_action_bundle(
            train, validation, config=config, seed=SEED
        )
        bundle_dir.parent.mkdir(parents=True, exist_ok=True)
        bundle.save(bundle_dir)
        fitted = True
    else:
        bundle = fit_action_bundle(
            train,
            validation,
            config=config,
            seed=SEED,
            objective="MultiClass",
        )
        bundle_dir.parent.mkdir(parents=True, exist_ok=True)
        bundle.save(bundle_dir)
        fitted = True
    slices = score_model(
        bundle,
        matrix,
        train_days=train_days,
        validation_days=validation_days,
        score_days=score_days,
    )
    val_rate = float(slices["validation"]["pred_enter_rate"])
    label_rate = float(slices["validation"]["label_enter_rate"])
    healthy = label_rate > 0.0 and val_rate >= 0.5 * label_rate
    payload = {
        "schema": "QRE2THRESHOLDREFITH1",
        "hypothesis": hypothesis,
        "seed": SEED,
        "objective": objective,
        "official_e1r": official_e1r,
        "enter_balance": enter_balance,
        "enter_scale_override": enter_scale_arg,
        "enter_balance_scale": enter_scale,
        "fitted_this_run": fitted,
        "bundle": str(bundle_dir.relative_to(REPO)),
        "bundle_receipt_sha256": bundle.receipt_sha256,
        "train_days": list(train_days),
        "validation_days": list(validation_days),
        "score_days": list(score_days),
        "slices": slices,
        "healthy_on_validation": healthy,
        "check_command": check,
    }
    RECEIPTS[receipt_key].write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
