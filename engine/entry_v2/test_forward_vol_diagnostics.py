#!/usr/bin/env python3
"""Regression tests for cheap, strictly-prior forward-vol diagnostics."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np

from tools.audit_entry_v2_forward_vol import (
    EVALUATION_COLUMNS,
    _evaluation_targets,
    _shifted_sigma_recovery,
    _range_persistence_targets,
    point_diagnostic,
)
from entry_v2.corpus import QRE2_FORECAST_LAW_SHA256
from tools.probe_entry_v2_forward_vol_sigma import causal_ratio_calibration


class ForwardVolDiagnosticTests(unittest.TestCase):
    @staticmethod
    def _evaluation_fixture(path: Path, *, lineage: str | None = None) -> dict:
        row = {
            "asset": "SI", "d8": "20240102", "segment": "SESSION",
            "forecast_status": "READY",
            "forecast_lineage_sha256": "a" * 64,
            "source_session_sha256": "b" * 64,
            "realized_valid": "1", "sane_events": "100",
            "grid_samples": "20", "open_px": "10", "high_px": "12",
            "low_px": "9", "close_px": "11", "range_usd": "20",
            "rv_usd": "9", "bv_usd": "5", "jump_usd": "4",
            "sigma_usd": "3", "parkinson_usd": "8", "gk_usd": "7",
            "rs_usd": "6", "evaluation_lineage_sha256": "",
        }
        parts = [
            "QRE2FORECASTEVALROW4", QRE2_FORECAST_LAW_SHA256, "0",
            row["d8"], "0", "0", row["forecast_lineage_sha256"],
            row["source_session_sha256"], row["realized_valid"],
            row["sane_events"], row["grid_samples"],
            *(row[name] for name in (
                "open_px", "high_px", "low_px", "close_px", "range_usd",
                "rv_usd", "bv_usd", "jump_usd", "sigma_usd",
                "parkinson_usd", "gk_usd", "rs_usd")),
        ]
        row["evaluation_lineage_sha256"] = lineage or hashlib.sha256(
            "|".join(parts).encode()).hexdigest()
        path.write_text(
            "# QRE2FORECASTEVAL4 start_d8=20240101 "
            "end_d8_exclusive=20240104 asset=SI "
            f"law_sha256={QRE2_FORECAST_LAW_SHA256}\n"
            + "\t".join(EVALUATION_COLUMNS) + "\n"
            + "\t".join(row[name] for name in EVALUATION_COLUMNS) + "\n",
            encoding="utf-8")
        return {
            "asset": "SI", "evaluation_path": str(path),
            "evaluation_rows": 1, "evaluation_valid_rows": 1,
            "start_d8": 20240101, "end_d8_exclusive": 20240104,
        }

    def test_exact_sigma_target_is_shifted_by_explicit_history_day(self) -> None:
        rows = ({
            "asset": "SI", "d8": "20240102", "segment": "SESSION",
            "history_end_d8": "20231229", "rv1_usd": "400",
        }, {
            "asset": "SI", "d8": "20240103", "segment": "SESSION",
            "history_end_d8": "20240102", "rv1_usd": "900",
        })
        targets = _shifted_sigma_recovery(rows)
        self.assertEqual(targets[("SI", 20231229, "SESSION")], 20.0)
        self.assertEqual(targets[("SI", 20240102, "SESSION")], 30.0)
        self.assertNotIn(("SI", 20240103, "SESSION"), targets)

    def test_ratio_calibration_never_reads_current_or_future_target(self) -> None:
        raw = np.full(5, 10.0)
        target_a = np.asarray([10.0, 20.0, 30.0, 40.0, 50.0])
        target_b = np.asarray([10.0, 20.0, 30.0, 4_000.0, 5_000.0])
        got_a, ratio_a, count_a = causal_ratio_calibration(
            raw, target_a, window=3, minimum=2)
        got_b, ratio_b, count_b = causal_ratio_calibration(
            raw, target_b, window=3, minimum=2)
        np.testing.assert_array_equal(count_a, count_b)
        np.testing.assert_allclose(got_a[:4], got_b[:4], equal_nan=True)
        np.testing.assert_allclose(ratio_a[:4], ratio_b[:4], equal_nan=True)
        self.assertEqual(got_a[0], 10.0)
        self.assertEqual(got_a[1], 10.0)
        self.assertEqual(got_a[2], 15.0)

    def test_range_persistence_crosses_period_boundary_without_future_data(
            self) -> None:
        targets = {
            ("SI", 20231229, "SESSION"): (100.0, 10.0),
            ("SI", 20240102, "SESSION"): (120.0, 11.0),
            ("SI", 20240103, "SESSION"): (90.0, 9.0),
            ("SI", 20231229, "NY"): (50.0, 5.0),
            ("HG", 20240102, "SESSION"): (200.0, 20.0),
        }
        baseline = _range_persistence_targets(targets)
        self.assertEqual(baseline[("SI", 20240102, "SESSION")], 100.0)
        self.assertEqual(baseline[("SI", 20240103, "SESSION")], 120.0)
        self.assertNotIn(("SI", 20231229, "SESSION"), baseline)
        self.assertNotIn(("HG", 20240102, "SESSION"), baseline)

    def test_point_diagnostic_exposes_exact_parity_failure(self) -> None:
        report = point_diagnostic([1.0, 2.0], [1.0, 2.25], [1.0, 2.25])
        self.assertEqual(report["max_absolute_error_usd"], 0.25)

    def test_exact_evaluation_sidecar_parses_and_binds_forecast_lineage(
            self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pin = self._evaluation_fixture(Path(directory) / "SI.qrf4.eval.tsv")
            targets = _evaluation_targets(
                {"artifacts": [pin]}, ({
                    "asset": "SI", "d8": "20240102", "segment": "SESSION",
                    "lineage_sha256": "a" * 64,
                },))
        self.assertEqual(targets[("SI", 20240102, "SESSION")], (20.0, 3.0))

    def test_exact_evaluation_sidecar_refuses_lineage_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pin = self._evaluation_fixture(
                Path(directory) / "SI.qrf4.eval.tsv", lineage="f" * 64)
            with self.assertRaisesRegex(RuntimeError, "lineage differs"):
                _evaluation_targets(
                    {"artifacts": [pin]}, ({
                        "asset": "SI", "d8": "20240102",
                        "segment": "SESSION", "lineage_sha256": "a" * 64,
                    },))


if __name__ == "__main__":
    unittest.main()
