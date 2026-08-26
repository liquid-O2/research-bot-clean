#!/usr/bin/env python3
"""Strictly-prior shrinkage probe for QRE2 forward-vol sigma forecasts.

One global blend weight is selected on causal forecasts whose target day is no
later than 2023-12-31.  The selected weight is then frozen and reported on
2024 and 2025H1 separately, including every asset/segment cell.  No Entry V2
labels or economics enter this probe.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "engine"))

from entry_v2 import common as C  # noqa: E402
from entry_v2.corpus_forecast import FORECAST_SEGMENTS  # noqa: E402
from tools import audit_entry_v2_forward_vol as A  # noqa: E402


SCHEMA = "QRE2FORWARDVOLSIGMAPROBE4"
CALIBRATION_WINDOW = 66
CALIBRATION_MIN = 20
WEIGHTS = (0.0, 0.25, 0.50, 0.75, 1.0)
SELECTION_END_D8_EXCLUSIVE = 20240101
VALIDATION_WINDOWS = {
    "2024": (20240101, 20250101),
    "2025H1": (20250101, C.HOLDOUT_START_D8),
}


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-root", type=Path,
        default=REPO_ROOT / "artifacts/cache/port/entry_v2")
    parser.add_argument(
        "--output", type=Path,
        default=REPO_ROOT / (
            "artifacts/entry_v2/forecast/forward_vol_sigma_probe_v4_exact.json"))
    return parser.parse_args()


def causal_ratio_calibration(
    raw_prediction: np.ndarray, target: np.ndarray,
    *, window: int = CALIBRATION_WINDOW, minimum: int = CALIBRATION_MIN,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return calibrated predictions, ratios and counts using only rows < i."""

    raw = np.asarray(raw_prediction, dtype=np.float64)
    y = np.asarray(target, dtype=np.float64)
    if raw.ndim != 1 or y.shape != raw.shape or window < 1 or minimum < 1:
        raise ValueError("invalid causal calibration arrays/config")
    calibrated = np.full(len(y), np.nan, dtype=np.float64)
    ratios = np.full(len(y), np.nan, dtype=np.float64)
    counts = np.zeros(len(y), dtype=np.int64)
    for index in range(len(y)):
        begin = max(0, index - int(window))
        history = y[begin:index] / raw[begin:index]
        history = history[np.isfinite(history) & (history > 0.0)]
        counts[index] = len(history)
        if math.isfinite(raw[index]):
            ratios[index] = (float(np.median(history))
                             if len(history) >= minimum else 1.0)
            calibrated[index] = raw[index] * ratios[index]
    return calibrated, ratios, counts


def _series(
    rows: tuple[dict[str, str], ...],
    targets: dict[tuple[str, int, str], tuple[float, float]],
    asset: str, segment: str,
) -> dict[str, np.ndarray]:
    selected = sorted((row for row in rows
                       if row["asset"] == asset
                       and row["segment"] == segment
                       and (asset, int(row["d8"]), segment) in targets),
                      key=lambda row: int(row["d8"]))
    day = np.asarray([int(row["d8"]) for row in selected], dtype=np.int64)
    target = np.asarray([
        targets[(asset, int(row["d8"]), segment)][1] for row in selected
    ], dtype=np.float64)
    raw = np.asarray([A._number(row["sigma_raw_hat_usd"])
                      for row in selected],
                     dtype=np.float64)
    persistence = np.asarray([
        A._number(row["sigma_persistence_usd"]) for row in selected
    ], dtype=np.float64)
    published = np.asarray([
        A._number(row["sigma_hat_usd"]) for row in selected
    ], dtype=np.float64)
    published_ratio = np.asarray([
        A._number(row["sigma_calibration_ratio"]) for row in selected
    ], dtype=np.float64)
    published_count = np.asarray([
        int(row["n_sigma_calibration"]) for row in selected
    ], dtype=np.int64)
    calibrated, ratio, count = causal_ratio_calibration(raw, target)
    return {"day": day, "target": target, "raw": raw,
            "persistence": persistence, "calibrated": calibrated,
            "calibration_ratio": ratio, "calibration_count": count,
            "published": published, "published_ratio": published_ratio,
            "published_count": published_count}


def _errors(series: dict[str, np.ndarray], weight: float,
            lower: int, upper: int) -> np.ndarray:
    prediction = (float(weight) * series["calibrated"]
                  + (1.0 - float(weight)) * series["persistence"])
    selected = ((series["day"] >= int(lower)) & (series["day"] < int(upper))
                & np.isfinite(prediction) & np.isfinite(series["target"]))
    return np.abs(prediction[selected] - series["target"][selected])


def _metric(series: dict[str, np.ndarray], weight: float,
            lower: int, upper: int) -> dict[str, object]:
    errors = _errors(series, weight, lower, upper)
    baseline = _errors(series, 0.0, lower, upper)
    return {
        "n": len(errors),
        "mae_usd": float(np.mean(errors)) if len(errors) else None,
        "persistence_mae_usd": (
            float(np.mean(baseline)) if len(baseline) else None),
        "gain_vs_persistence": (
            float(1.0 - np.mean(errors) / np.mean(baseline))
            if len(errors) and np.mean(baseline) > 0.0 else None),
    }


def main() -> int:
    args = _arguments()
    _, rows, source = A._provider_and_rows(args.source_root.resolve())
    targets = A._evaluation_targets(source, rows)
    series = {(asset, segment): _series(rows, targets, asset, segment)
              for asset in C.ASSETS for segment in FORECAST_SEGMENTS}

    reproduction_errors = []
    ratio_errors = []
    count_errors = []
    for values in series.values():
        reconstructed = values["calibrated"]
        valid = np.isfinite(values["published"])
        reproduction_errors.extend(np.abs(
            reconstructed[valid] - values["published"][valid]))
        ratio_errors.extend(np.abs(
            values["calibration_ratio"][valid]
            - values["published_ratio"][valid]))
        count_errors.extend(np.abs(
            values["calibration_count"][valid]
            - values["published_count"][valid]))
    max_reproduction_error = float(np.max(reproduction_errors))
    max_ratio_error = float(np.max(ratio_errors))
    max_count_error = int(np.max(count_errors))
    if (max_reproduction_error > 1e-9 or max_ratio_error > 1e-12
            or max_count_error != 0):
        raise C.EntryV2Refusal(
            "exact sidecar cannot reproduce published sigma chronology")

    selection = {}
    for weight in WEIGHTS:
        errors = np.concatenate([
            _errors(values, weight, 0, SELECTION_END_D8_EXCLUSIVE)
            for values in series.values()
        ])
        selection[str(weight)] = {
            "n": len(errors), "pooled_mae_usd": float(np.mean(errors))}
    chosen = min(WEIGHTS, key=lambda weight: (
        selection[str(weight)]["pooled_mae_usd"], weight))

    validation = {}
    all_cells_positive = True
    for name, (lower, upper) in VALIDATION_WINDOWS.items():
        cell = {}
        pooled_errors, pooled_baseline = [], []
        for key, values in series.items():
            metric = _metric(values, chosen, lower, upper)
            cell["|".join(key)] = metric
            if (metric["gain_vs_persistence"] is None
                    or metric["gain_vs_persistence"] <= 0.0):
                all_cells_positive = False
            pooled_errors.append(_errors(values, chosen, lower, upper))
            pooled_baseline.append(_errors(values, 0.0, lower, upper))
        errors = np.concatenate(pooled_errors)
        baseline = np.concatenate(pooled_baseline)
        validation[name] = {
            "window": [lower, upper],
            "pooled": {
                "n": len(errors), "mae_usd": float(np.mean(errors)),
                "persistence_mae_usd": float(np.mean(baseline)),
                "gain_vs_persistence": float(
                    1.0 - np.mean(errors) / np.mean(baseline)),
            },
            "cells": cell,
        }

    core = {
        "schema": SCHEMA,
        "source": source,
        "target": "exact diagnostics-only QRE2FORECASTEVAL4 sigma target",
        "calibration": {
            "window": CALIBRATION_WINDOW, "minimum": CALIBRATION_MIN,
            "statistic": "median(target / raw_sigma_hat)",
            "chronology": "row i uses target/prediction pairs from rows < i only",
        },
        "policy": (
            "weight * calibrated_ols + (1-weight) * prior_session_sigma"),
        "published_reproduction": {
            "rows": len(reproduction_errors),
            "max_sigma_absolute_error_usd": max_reproduction_error,
            "max_calibration_ratio_absolute_error": max_ratio_error,
            "max_calibration_count_error": max_count_error,
        },
        "selection": {
            "end_d8_exclusive": SELECTION_END_D8_EXCLUSIVE,
            "metric": "pooled dollar MAE across all asset/segment series",
            "candidates": selection,
            "selected_weight": chosen,
        },
        "validation": validation,
        "gate": {
            "requires_positive_gain_in_every_asset_segment_on_both_windows": True,
            "passed": all_cells_positive,
        },
        "h2_open_count": 0,
        "entry_labels_or_economics_used": False,
        "publisher_change_authorized": all_cells_positive,
        "launch_authorization": False,
        "tool_sha256": C.file_sha256(Path(__file__)),
        "audit_dependency_sha256": C.file_sha256(Path(A.__file__)),
    }
    artifact = {**core, "receipt_sha256": C.object_sha256(core)}
    C.atomic_json(args.output, artifact)
    print(json.dumps({
        "output": str(args.output.resolve()),
        "receipt_sha256": artifact["receipt_sha256"],
        "selected_weight": chosen,
        "validation": {name: value["pooled"]
                       for name, value in validation.items()},
        "all_cells_positive_on_both_windows": all_cells_positive,
        "h2_open_count": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
