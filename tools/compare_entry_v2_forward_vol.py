#!/usr/bin/env python3
"""Receipt-bound comparison of exact QRE2FORECAST3 and QRE2FORECAST4 audits."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "engine"))

from entry_v2 import common as C  # noqa: E402
from entry_v2.corpus import FORECAST_QUANTILES, FORECAST_SEGMENTS  # noqa: E402


SCHEMA = "QRE2FORWARDVOLCOMPARE1"
PERIODS = ("2024", "2025H1")
MAX_CELL_COVERAGE_ERROR = 0.075


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--v3", type=Path, default=REPO_ROOT / (
            "artifacts/entry_v2/forecast/forward_vol_audit_v3_exact.json"))
    parser.add_argument(
        "--v4", type=Path, default=REPO_ROOT / (
            "artifacts/entry_v2/forecast/forward_vol_audit_v4_exact.json"))
    parser.add_argument(
        "--output", type=Path, default=REPO_ROOT / (
            "artifacts/entry_v2/forecast/forward_vol_v3_v4_comparison.json"))
    return parser.parse_args()


def _audit(path: Path, schema: str) -> dict[str, object]:
    C.guard_payload(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise C.EntryV2Refusal(f"invalid forward-vol audit: {path}") from exc
    if not isinstance(value, dict) or value.get("schema") != schema:
        raise C.EntryV2Refusal("forward-vol audit schema differs")
    core = {key: item for key, item in value.items() if key != "receipt_sha256"}
    if (value.get("receipt_sha256") != C.object_sha256(core)
            or value.get("h2_open_count") != 0
            or value.get("entry_labels_or_economics_used") is not False
            or value.get("launch_authorization") is not False):
        raise C.EntryV2Refusal("forward-vol audit receipt/safety law differs")
    return value


def _weighted_pinball(slice_report: dict[str, object]) -> tuple[float, int]:
    quantiles = slice_report["range_quantiles_exact_publisher_target"]
    total = 0.0
    count = 0
    for name in FORECAST_QUANTILES:
        row = quantiles[name]
        n = int(row.get("n", 0))
        loss = row.get("pinball_loss_usd")
        if n > 0 and loss is not None:
            total += float(loss) * n
            count += n
    if count == 0:
        raise C.EntryV2Refusal("range quantile audit has no comparable rows")
    return total, count


def main() -> int:
    args = _arguments()
    v3 = _audit(args.v3.resolve(), "QRE2FORWARDVOLAUDIT3")
    v4 = _audit(args.v4.resolve(), "QRE2FORWARDVOLAUDIT4")
    if (v3.get("row_count") != v4.get("row_count")
            or v3.get("evaluation_target_count")
               != v4.get("evaluation_target_count")):
        raise C.EntryV2Refusal("v3/v4 exact target denominators differ")

    cells: dict[str, object] = {}
    period_summary: dict[str, object] = {}
    sigma_better_every_cell = True
    range_positive_every_cell = True
    coverage_healthy_every_cell = True
    range_point_identical = True
    for period in PERIODS:
        old_pinball = 0.0
        old_count = 0
        new_pinball = 0.0
        new_count = 0
        for asset in C.ASSETS:
            for segment in FORECAST_SEGMENTS:
                key = f"{asset}|{segment}|{period}"
                old = v3["slices"][key]
                new = v4["slices"][key]
                old_sigma = float(old["sigma_exact_publisher_target"][
                    "gain_vs_baseline"])
                new_sigma = float(new["sigma_exact_publisher_target"][
                    "gain_vs_baseline"])
                range_gain = float(new["range_exact_publisher_target"][
                    "gain_vs_baseline"])
                coverage = float(new[
                    "range_quantiles_exact_publisher_target"][
                        "mean_absolute_coverage_error"])
                sigma_better_every_cell &= new_sigma > old_sigma > 0.0
                range_positive_every_cell &= range_gain > 0.0
                coverage_healthy_every_cell &= (
                    coverage <= MAX_CELL_COVERAGE_ERROR)
                range_point_identical &= (
                    old["range_exact_publisher_target"]
                    == new["range_exact_publisher_target"])
                old_total, old_n = _weighted_pinball(old)
                new_total, new_n = _weighted_pinball(new)
                old_pinball += old_total
                old_count += old_n
                new_pinball += new_total
                new_count += new_n
                cells[key] = {
                    "v3_sigma_gain_vs_persistence": old_sigma,
                    "v4_sigma_gain_vs_persistence": new_sigma,
                    "v4_range_gain_vs_persistence": range_gain,
                    "v4_range_mean_absolute_coverage_error": coverage,
                    "v3_mean_pinball_loss_usd": old_total / old_n,
                    "v4_mean_pinball_loss_usd": new_total / new_n,
                }
        if old_count != new_count:
            raise C.EntryV2Refusal("v3/v4 quantile denominators differ")
        period_summary[period] = {
            "quantile_comparisons": old_count,
            "v3_pooled_pinball_loss_usd": old_pinball / old_count,
            "v4_pooled_pinball_loss_usd": new_pinball / new_count,
            "v4_pinball_gain": 1.0 - new_pinball / old_pinball,
        }

    pinball_better_both_periods = all(
        float(period_summary[period]["v4_pinball_gain"]) > 0.0
        for period in PERIODS)
    passed = all((sigma_better_every_cell, range_positive_every_cell,
                  coverage_healthy_every_cell, range_point_identical,
                  pinball_better_both_periods))
    core = {
        "schema": SCHEMA,
        "sources": {
            "v3_path": str(args.v3.resolve()),
            "v3_file_sha256": C.file_sha256(args.v3),
            "v3_receipt_sha256": v3["receipt_sha256"],
            "v4_path": str(args.v4.resolve()),
            "v4_file_sha256": C.file_sha256(args.v4),
            "v4_receipt_sha256": v4["receipt_sha256"],
        },
        "cells": cells,
        "periods": period_summary,
        "gates": {
            "sigma_better_every_cell": sigma_better_every_cell,
            "range_positive_every_cell": range_positive_every_cell,
            "range_point_identical": range_point_identical,
            "max_cell_coverage_error": MAX_CELL_COVERAGE_ERROR,
            "coverage_healthy_every_cell": coverage_healthy_every_cell,
            "pinball_better_both_periods": pinball_better_both_periods,
            "passed": passed,
        },
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
        "periods": period_summary,
        "gates": artifact["gates"],
        "h2_open_count": 0,
    }, sort_keys=True))
    if not passed:
        raise C.EntryV2Refusal("QRE2FORECAST4 comparison gate failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
