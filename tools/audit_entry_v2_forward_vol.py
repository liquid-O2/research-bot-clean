#!/usr/bin/env python3
"""Exact chronological diagnostics for the pinned QRE2 forward-vol publisher.

Range and sigma targets come only from the diagnostics-only, receipt-bound
QRE2FORECASTEVAL4 sidecar emitted during the sealed pre-H2 publisher pass.  The
next design row's ``history_end_d8``/``rv1_usd`` pair independently reconstructs
sigma and must agree with that sidecar.

This tool never opens 2025H2 and does not select an Entry V2 learner.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Iterable, Mapping

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "engine"))

from entry_v2 import common as C  # noqa: E402
from entry_v2.corpus import (  # noqa: E402
    FORECAST_QUANTILES,
    FORECAST_SEGMENTS,
    QRE2_FORECAST_LAW_SHA256,
    QRE2ForecastArtifactInput,
    QRE2ForecastProvider,
)


SCHEMA = "QRE2FORWARDVOLAUDIT4"
NOMINAL = dict(zip(FORECAST_QUANTILES, (0.10, 0.25, 0.50, 0.75, 0.90)))
EVALUATION_COLUMNS = (
    "asset", "d8", "segment", "forecast_status",
    "forecast_lineage_sha256", "source_session_sha256", "realized_valid",
    "sane_events", "grid_samples", "open_px", "high_px", "low_px",
    "close_px", "range_usd", "rv_usd", "bv_usd", "jump_usd",
    "sigma_usd", "parkinson_usd", "gk_usd", "rs_usd",
    "evaluation_lineage_sha256",
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-root", type=Path,
        default=REPO_ROOT / "artifacts/cache/port/entry_v2")
    parser.add_argument(
        "--output", type=Path,
        default=REPO_ROOT / (
            "artifacts/entry_v2/forecast/forward_vol_audit_v4_exact.json"))
    return parser.parse_args()


def _tsv_rows(path: Path) -> tuple[dict[str, str], ...]:
    C.guard_payload(path)
    with path.open("r", encoding="utf-8", newline="") as stream:
        for line in stream:
            if not line.startswith("#"):
                header = line.rstrip("\r\n")
                break
        else:
            raise C.EntryV2Refusal(f"TSV has no header: {path}")
        reader = csv.DictReader(stream, fieldnames=header.split("\t"),
                                delimiter="\t")
        rows = tuple(dict(row) for row in reader if any(row.values()))
    if not rows or any(None in row or None in row.values() for row in rows):
        raise C.EntryV2Refusal(f"TSV is empty or ragged: {path}")
    return rows


def _number(value: object) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return math.nan
    return parsed if math.isfinite(parsed) else math.nan


def _rank(values: np.ndarray) -> np.ndarray:
    """Stable average ranks, used only as a descriptive diagnostic."""

    order = np.argsort(values, kind="stable")
    ranked = np.empty(len(values), dtype=np.float64)
    start = 0
    while start < len(order):
        stop = start + 1
        while stop < len(order) and values[order[stop]] == values[order[start]]:
            stop += 1
        ranked[order[start:stop]] = (start + stop - 1) / 2.0
        start = stop
    return ranked


def _correlation(left: np.ndarray, right: np.ndarray, *, rank: bool) -> float | None:
    valid = np.isfinite(left) & np.isfinite(right)
    if np.count_nonzero(valid) < 3:
        return None
    x, y = left[valid], right[valid]
    if rank:
        x, y = _rank(x), _rank(y)
    if float(np.std(x)) == 0.0 or float(np.std(y)) == 0.0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def _finite(value: float) -> float | None:
    return float(value) if math.isfinite(float(value)) else None


def point_diagnostic(
    prediction: Iterable[float], target: Iterable[float],
    baseline: Iterable[float],
) -> dict[str, object]:
    prediction = np.asarray(tuple(prediction), dtype=np.float64)
    target = np.asarray(tuple(target), dtype=np.float64)
    baseline = np.asarray(tuple(baseline), dtype=np.float64)
    valid = np.isfinite(prediction) & np.isfinite(target)
    comparable = valid & np.isfinite(baseline)
    if not np.any(valid):
        return {"n": 0, "n_comparable": 0}
    error = prediction[valid] - target[valid]
    absolute = np.abs(error)
    mae = float(np.mean(absolute))
    baseline_mae = (float(np.mean(np.abs(baseline[comparable]
                                         - target[comparable])))
                    if np.any(comparable) else math.nan)
    model_comparable_mae = (float(np.mean(np.abs(prediction[comparable]
                                                - target[comparable])))
                            if np.any(comparable) else math.nan)
    return {
        "n": int(np.count_nonzero(valid)),
        "n_comparable": int(np.count_nonzero(comparable)),
        "target_mean_usd": float(np.mean(target[valid])),
        "prediction_mean_usd": float(np.mean(prediction[valid])),
        "mae_usd": mae,
        "max_absolute_error_usd": float(np.max(absolute)),
        "median_absolute_error_usd": float(np.median(absolute)),
        "bias_usd": float(np.mean(error)),
        "mean_absolute_percentage_error": float(np.mean(
            absolute / np.maximum(np.abs(target[valid]), 1.0))),
        "pearson": _correlation(prediction, target, rank=False),
        "spearman": _correlation(prediction, target, rank=True),
        "baseline_mae_usd": _finite(baseline_mae),
        "model_comparable_mae_usd": _finite(model_comparable_mae),
        "gain_vs_baseline": _finite(
            1.0 - model_comparable_mae / baseline_mae
            if math.isfinite(baseline_mae) and baseline_mae > 0.0
            else math.nan),
    }


def quantile_diagnostic(
    rows: Iterable[Mapping[str, str]], targets: Iterable[float],
) -> dict[str, object]:
    rows = tuple(rows)
    target = np.asarray(tuple(targets), dtype=np.float64)
    output: dict[str, object] = {}
    errors = []
    for quantile in FORECAST_QUANTILES:
        predicted = np.asarray([
            _number(row[f"move_rs_{quantile}_usd"]) for row in rows
        ], dtype=np.float64)
        valid = np.isfinite(predicted) & np.isfinite(target)
        nominal = NOMINAL[quantile]
        if not np.any(valid):
            output[quantile] = {"n": 0, "nominal": nominal}
            continue
        coverage = float(np.mean(target[valid] <= predicted[valid]))
        residual = target[valid] - predicted[valid]
        pinball = float(np.mean(np.maximum(
            nominal * residual, (nominal - 1.0) * residual)))
        error = coverage - nominal
        errors.append(abs(error))
        output[quantile] = {
            "n": int(np.count_nonzero(valid)),
            "nominal": nominal,
            "empirical_coverage": coverage,
            "coverage_error": error,
            "pinball_loss_usd": pinball,
            "mean_forecast_usd": float(np.mean(predicted[valid])),
        }
    output["mean_absolute_coverage_error"] = (
        float(np.mean(errors)) if errors else None)
    return output


def ladder_structure_diagnostic(
    rows: Iterable[Mapping[str, str]],
) -> dict[str, object]:
    rows = tuple(row for row in rows if row["status"] == "READY")
    sources = {name: sum(row["ladder_source"] == name for row in rows)
               for name in ("MISSING", "REGIME", "UNSCALED_FALLBACK")}
    present = tuple(row for row in rows if row["ladder_source"] != "MISSING")
    nonmonotone = 0
    widths = []
    for row in present:
        values = [_number(row[f"move_rs_{q}_usd"])
                  for q in FORECAST_QUANTILES]
        if (not all(math.isfinite(value) and value > 0.0 for value in values)
                or any(right < left for left, right in zip(values, values[1:]))):
            nonmonotone += 1
        else:
            widths.append(values[-1] - values[0])
    return {
        "ready_rows": len(rows),
        "source_counts": sources,
        "present_rows": len(present),
        "nonmonotone_rows": nonmonotone,
        "mean_q90_minus_q10_usd": (
            float(np.mean(widths)) if widths else None),
        "coverage_status": "STRUCTURE_ONLY_SEE_EXACT_QUANTILE_DIAGNOSTIC",
    }


def _period(day: int) -> tuple[str, ...]:
    values = ["ALL_PRE_H2"]
    if day < 20240101:
        values.append("THROUGH_2023")
    elif day < 20250101:
        values.append("2024")
    else:
        values.append("2025H1")
    return tuple(values)


def _provider_and_rows(source_root: Path) -> tuple[
        QRE2ForecastProvider, tuple[dict[str, str], ...], dict[str, object]]:
    inputs = []
    rows = []
    pins = []
    for asset in C.ASSETS:
        artifact = source_root / "forecast" / f"{asset}.qrf4.tsv"
        receipt = source_root / "forecast" / f"{asset}.qrf4.json"
        C.guard_payload(artifact)
        C.guard_payload(receipt)
        artifact_sha = C.file_sha256(artifact)
        receipt_sha = C.file_sha256(receipt)
        try:
            receipt_object = json.loads(receipt.read_text(encoding="utf-8"))
            start = int(receipt_object["start_d8"])
            end = int(receipt_object["end_d8_exclusive"])
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError,
                TypeError, ValueError) as exc:
            raise C.EntryV2Refusal("invalid forecast receipt") from exc
        C.guard_decode_window(start, end)
        evaluation = receipt_object.get("evaluation", {})
        evaluation_path = source_root / "forecast" / f"{asset}.qrf4.eval.tsv"
        inputs.append(QRE2ForecastArtifactInput(
            source_root, asset, artifact_sha, receipt_sha))
        asset_rows = _tsv_rows(artifact)
        if any(int(row["d8"]) >= C.HOLDOUT_START_D8 for row in asset_rows):
            raise C.EntryV2Refusal("forward-vol audit attempted to open 2025H2")
        rows.extend(asset_rows)
        pins.append({
            "asset": asset,
            "artifact_path": str(artifact.resolve()),
            "artifact_sha256": artifact_sha,
            "receipt_path": str(receipt.resolve()),
            "receipt_sha256": receipt_sha,
            "evaluation_path": str(evaluation_path.resolve()),
            "evaluation_sha256": evaluation.get("output_sha256"),
            "evaluation_rows": int(evaluation.get("rows", -1)),
            "evaluation_valid_rows": int(evaluation.get("valid_rows", -1)),
            "start_d8": start,
            "end_d8_exclusive": end,
            "rows": len(asset_rows),
        })
    provider = QRE2ForecastProvider(tuple(inputs))
    # The strict provider validates every receipt and declared pre-H2 window
    # without opening the hindsight plane.  Only the diagnostic then opens and
    # verifies the evaluation sidecars.
    for pin in pins:
        evaluation_sha = C.file_sha256(Path(pin["evaluation_path"]))
        if evaluation_sha != pin["evaluation_sha256"]:
            raise C.EntryV2Refusal("forecast evaluation hash differs from receipt")
    return provider, tuple(rows), {
        "provider_receipt_sha256": provider.receipt_sha256,
        "artifacts": pins,
    }


def _evaluation_targets(
    source: Mapping[str, object], forecast_rows: Iterable[Mapping[str, str]],
) -> dict[tuple[str, int, str], tuple[float, float]]:
    forecast_lineage = {
        (row["asset"], int(row["d8"]), row["segment"]): row["lineage_sha256"]
        for row in forecast_rows
    }
    output: dict[tuple[str, int, str], tuple[float, float]] = {}
    for pin in source["artifacts"]:
        path = Path(pin["evaluation_path"])
        with path.open("r", encoding="utf-8", newline="") as stream:
            header = stream.readline().rstrip("\r\n")
            match = re.fullmatch(
                r"# QRE2FORECASTEVAL4 start_d8=(\d{8}) "
                r"end_d8_exclusive=(\d{8}) asset=(SI|HG|NKD) "
                r"law_sha256=([0-9a-f]{64})", header)
            if (match is None or match.group(3) != pin["asset"]
                    or match.group(4) != QRE2_FORECAST_LAW_SHA256):
                raise C.EntryV2Refusal("forecast evaluation header mismatch")
            start, end = int(match.group(1)), int(match.group(2))
            C.guard_decode_window(start, end)
            if (start, end) != (pin["start_d8"], pin["end_d8_exclusive"]):
                raise C.EntryV2Refusal("forecast evaluation window differs")
            reader = csv.DictReader(stream, delimiter="\t")
            if tuple(reader.fieldnames or ()) != EVALUATION_COLUMNS:
                raise C.EntryV2Refusal("forecast evaluation columns differ")
            rows = tuple(dict(row) for row in reader)
        if len(rows) != pin["evaluation_rows"]:
            raise C.EntryV2Refusal("forecast evaluation row count differs")
        valid_count = 0
        prior: tuple[int, int] | None = None
        for row in rows:
            asset = row["asset"]
            day = int(row["d8"])
            if asset != pin["asset"] or not start <= day < end:
                raise C.EntryV2Refusal("forecast evaluation key differs")
            if day >= C.HOLDOUT_START_D8:
                raise C.EntryV2Refusal("forecast evaluation opened 2025H2")
            try:
                segment_index = FORECAST_SEGMENTS.index(row["segment"])
                status_index = {"READY": 0, "MISSING": 1}[
                    row["forecast_status"]]
            except (ValueError, KeyError) as exc:
                raise C.EntryV2Refusal("forecast evaluation enum differs") from exc
            order = (day, segment_index)
            if prior is not None and order <= prior:
                raise C.EntryV2Refusal("forecast evaluation is not ordered")
            prior = order
            key = (asset, day, row["segment"])
            if key in output:
                raise C.EntryV2Refusal("duplicate forecast evaluation key")
            if forecast_lineage.get(key) != row["forecast_lineage_sha256"]:
                raise C.EntryV2Refusal("evaluation/forecast lineage differs")
            for name in ("forecast_lineage_sha256", "source_session_sha256",
                         "evaluation_lineage_sha256"):
                if not re.fullmatch(r"[0-9a-f]{64}", row[name]):
                    raise C.EntryV2Refusal("evaluation hash is invalid")
            valid = row["realized_valid"] == "1"
            if row["realized_valid"] not in {"0", "1"}:
                raise C.EntryV2Refusal("evaluation validity flag differs")
            numeric = (
                "open_px", "high_px", "low_px", "close_px", "range_usd",
                "rv_usd", "bv_usd", "jump_usd", "sigma_usd",
                "parkinson_usd", "gk_usd", "rs_usd")
            try:
                sane_events = int(row["sane_events"])
                grid_samples = int(row["grid_samples"])
            except ValueError as exc:
                raise C.EntryV2Refusal(
                    "evaluation count is invalid") from exc
            if sane_events < 0 or grid_samples < 0:
                raise C.EntryV2Refusal("evaluation count is negative")
            if any(value != "NA" and not math.isfinite(_number(value))
                   for value in (row[name] for name in numeric)):
                raise C.EntryV2Refusal("evaluation scalar is invalid")
            parts = [
                "QRE2FORECASTEVALROW4", match.group(4),
                str(C.ASSET_INDEX[asset]), row["d8"], str(segment_index),
                str(status_index), row["forecast_lineage_sha256"],
                row["source_session_sha256"], row["realized_valid"],
                row["sane_events"], row["grid_samples"],
                *("nan" if row[name] == "NA" else row[name]
                  for name in numeric),
            ]
            if hashlib.sha256("|".join(parts).encode()).hexdigest() != row[
                    "evaluation_lineage_sha256"]:
                raise C.EntryV2Refusal("forecast evaluation lineage differs")
            if valid:
                range_usd = _number(row["range_usd"])
                sigma_usd = _number(row["sigma_usd"])
                if not range_usd > 0.0:
                    raise C.EntryV2Refusal("valid evaluation range is invalid")
                output[key] = (range_usd, sigma_usd)
                valid_count += 1
        if valid_count != pin["evaluation_valid_rows"]:
            raise C.EntryV2Refusal("evaluation valid count differs")
    return output


def _shifted_sigma_recovery(
    rows: Iterable[Mapping[str, str]],
) -> dict[tuple[str, int, str], float]:
    """Partial independent recovery, exact only across adjacent valid commits.

    ``history_end_d8`` advances even when a realization is invalid, whereas
    ``rv1_usd`` retains the most recent valid realized RV.  The key is therefore
    not a complete target source across invalid gaps.  Intersection with the
    exact evaluation plane is still a useful independent numeric parity check.
    """

    targets: dict[tuple[str, int, str], float] = {}
    for row in rows:
        history_day = int(row["history_end_d8"])
        rv1 = _number(row["rv1_usd"])
        if history_day < 0 or not math.isfinite(rv1) or rv1 <= 0.0:
            continue
        key = (row["asset"], history_day, row["segment"])
        value = math.sqrt(rv1)
        prior = targets.get(key)
        if prior is not None and prior != value:
            raise C.EntryV2Refusal("publisher sigma target is not unique")
        targets[key] = value
    return targets


def _range_persistence_targets(
    evaluation_targets: Mapping[tuple[str, int, str], tuple[float, float]],
) -> dict[tuple[str, int, str], float]:
    """Last valid realized range for each asset/segment across all periods."""

    output: dict[tuple[str, int, str], float] = {}
    prior: dict[tuple[str, str], float] = {}
    for key in sorted(evaluation_targets, key=lambda value: (
            value[0], value[2], value[1])):
        asset, _, segment = key
        series = (asset, segment)
        if series in prior:
            output[key] = prior[series]
        prior[series] = evaluation_targets[key][0]
    return output


def _slice_report(
    rows: tuple[Mapping[str, str], ...],
    evaluation_targets: Mapping[tuple[str, int, str], tuple[float, float]],
    range_persistence: Mapping[tuple[str, int, str], float],
) -> dict[str, object]:
    sigma_pred, sigma_y, sigma_base = [], [], []
    range_rows, range_y, range_pred, range_base = [], [], [], []
    for row in rows:
        key = (row["asset"], int(row["d8"]), row["segment"])
        if row["status"] == "READY" and key in evaluation_targets:
            sigma_pred.append(_number(row["sigma_hat_usd"]))
            sigma_y.append(evaluation_targets[key][1])
            sigma_base.append(_number(row["sigma_persistence_usd"]))
            range_rows.append(row)
            range_y.append(evaluation_targets[key][0])
            range_pred.append(_number(row["range_hat_usd"]))
            range_base.append(range_persistence.get(key, math.nan))
    return {
        "rows": len(rows),
        "ready_rows": sum(row["status"] == "READY" for row in rows),
        "sigma_exact_publisher_target": point_diagnostic(
            sigma_pred, sigma_y, sigma_base),
        "ladder_structure": ladder_structure_diagnostic(rows),
        "range_exact_publisher_target": point_diagnostic(
            range_pred, range_y, range_base),
        "range_quantiles_exact_publisher_target": quantile_diagnostic(
            range_rows, range_y),
    }


def main() -> int:
    args = _arguments()
    source_root = args.source_root.resolve()
    provider, rows, source = _provider_and_rows(source_root)
    shifted_sigma = _shifted_sigma_recovery(rows)
    evaluation_targets = _evaluation_targets(source, rows)
    range_persistence = _range_persistence_targets(evaluation_targets)
    shared = set(shifted_sigma) & set(evaluation_targets)
    sigma_parity = point_diagnostic(
        (evaluation_targets[key][1] for key in shared),
        (shifted_sigma[key] for key in shared),
        (shifted_sigma[key] for key in shared))
    if (not shared or sigma_parity.get("max_absolute_error_usd", math.inf)
            > 1e-9):
        raise C.EntryV2Refusal(
            "evaluation sigma differs from independent shifted target")

    slices: dict[str, object] = {}
    for asset in C.ASSETS:
        for segment in FORECAST_SEGMENTS:
            base = tuple(row for row in rows
                         if row["asset"] == asset and row["segment"] == segment)
            for period in ("ALL_PRE_H2", "THROUGH_2023", "2024", "2025H1"):
                selected = tuple(row for row in base
                                 if period in _period(int(row["d8"])))
                slices[f"{asset}|{segment}|{period}"] = _slice_report(
                    selected, evaluation_targets, range_persistence)
            for regime in ("LOW", "MID", "HIGH"):
                selected = tuple(row for row in base
                                 if row["regime_tag"] == regime)
                slices[f"{asset}|{segment}|REGIME_{regime}"] = _slice_report(
                    selected, evaluation_targets, range_persistence)

    core = {
        "schema": SCHEMA,
        "source": source,
        "target_contract": {
            "sigma": (
                "exact diagnostics-only publisher evaluation sidecar; partial "
                "history_end_d8/rv1 recovery is an independent overlap-only "
                "parity check because invalid commits can leave rv1 stale"),
            "range": "exact diagnostics-only publisher evaluation sidecar",
            "shifted_sigma_parity": sigma_parity,
        },
        "row_count": len(rows),
        "shifted_sigma_recovery_count": len(shifted_sigma),
        "evaluation_target_count": len(evaluation_targets),
        "slices": slices,
        "h2_open_count": 0,
        "entry_labels_or_economics_used": False,
        "launch_authorization": False,
        "tool_sha256": C.file_sha256(Path(__file__)),
    }
    artifact = {**core, "receipt_sha256": C.object_sha256(core)}
    C.atomic_json(args.output, artifact)
    print(json.dumps({
        "output": str(args.output.resolve()),
        "receipt_sha256": artifact["receipt_sha256"],
        "row_count": len(rows),
        "shifted_sigma_recovery_count": len(shifted_sigma),
        "all_cell_sigma_gain_vs_persistence": {
            key: value["sigma_exact_publisher_target"].get("gain_vs_baseline")
            for key, value in slices.items() if key.endswith("|ALL_PRE_H2")
        },
        "all_cell_range_mean_absolute_coverage_error": {
            key: value["range_quantiles_exact_publisher_target"].get(
                "mean_absolute_coverage_error")
            for key, value in slices.items() if key.endswith("|ALL_PRE_H2")
        },
        "h2_open_count": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
