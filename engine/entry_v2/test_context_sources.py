#!/usr/bin/env python3
"""One adversarial fixture for the entry-v2 slow-context boundary."""

from __future__ import annotations

import datetime as dt
from types import MappingProxyType
import unittest

import numpy as np
import torch

from engine.entry_v2 import common as C
from engine.entry_v2.context_pack import (
    AvailableObservation,
    ContextSource,
    build_context_pack,
)
from engine.entry_v2.context_sources import (
    CONTEXT_TENSOR_WIDTH, CausalContextRepository,
    TABULAR_CONTEXT_FEATURE_NAMES,
    load_context_repository,
    tabular_context_summary,
    tensorize_context_pack,
)
from engine.entry_v2.contracts import VintageClass


NS = 1_000_000_000
D8 = 20250115


class ContextSourceAdversarialTests(unittest.TestCase):
    def test_tabular_summary_has_global_schema_and_strict_prior_values(self) -> None:
        decision = 100 * NS
        source = ContextSource(
            "VIX", VintageClass.FIRST_PRINT, (
                AvailableObservation("past-1", 50 * NS, (20.0,)),
                AvailableObservation("past-2", 90 * NS, (22.0,)),
                AvailableObservation("equal", decision, (9_000.0,)),
                AvailableObservation("future", 101 * NS, (-9_000.0,)),
            ))
        receipt = {"schema": "test", "receipt_sha256": "a" * 64}
        repository = CausalContextRepository(
            "SI", MappingProxyType({"VIX": source}),
            MappingProxyType(receipt))
        matrix = tabular_context_summary(repository, D8, (decision,))
        self.assertEqual(matrix.shape, (1, len(TABULAR_CONTEXT_FEATURE_NAMES)))
        positions = {name: index for index, name in enumerate(
            TABULAR_CONTEXT_FEATURE_NAMES)}
        self.assertEqual(matrix[0, positions["ctx_VIX_last_value_0"]], 22.0)
        self.assertEqual(matrix[0, positions["ctx_VIX_mean_value_0"]], 21.0)
        self.assertAlmostEqual(
            matrix[0, positions["ctx_VIX_history_coverage"]], 2.0 / 64.0)
        self.assertEqual(
            matrix[0, positions["ctx_FRED_DTWEXBGS_history_coverage"]], 0.0)
        self.assertTrue(np.isfinite(matrix).all())

    def test_future_mutation_cannot_change_pack_or_tensor(self) -> None:
        decision = 100 * NS
        past = (
            AvailableObservation("past-1", 50 * NS, (20.0,)),
            AvailableObservation("past-2", 90 * NS, (21.0,)),
        )
        source_a = ContextSource(
            "VIX", VintageClass.FIRST_PRINT, past + (
                AvailableObservation("equal-a", decision, (9_000.0,)),
                AvailableObservation("future-a", 101 * NS, (8_000.0,)),
            ),
        )
        source_b = ContextSource(
            "VIX", VintageClass.FIRST_PRINT, past + (
                AvailableObservation("equal-b", decision, (-9_000.0,)),
                AvailableObservation("future-b", 999 * NS, (-8_000.0,)),
            ),
        )
        pack_a = build_context_pack(
            "SI", decision, {"VIX": source_a}, trading_day=D8
        )
        pack_b = build_context_pack(
            "SI", decision, {"VIX": source_b}, trading_day=D8
        )
        self.assertEqual(pack_a, pack_b)
        tensor_a = tensorize_context_pack(pack_a)
        tensor_b = tensorize_context_pack(pack_b)
        self.assertTrue(torch.equal(tensor_a.values, tensor_b.values))
        self.assertTrue(torch.equal(tensor_a.valid, tensor_b.valid))

    def test_equal_time_is_missing_and_wall_fires_before_mapping_read(self) -> None:
        decision = 100 * NS
        equal = ContextSource(
            "VIX",
            VintageClass.FIRST_PRINT,
            (AvailableObservation("equal", decision, (20.0,)),),
        )
        pack = build_context_pack(
            "SI", decision, {"VIX": equal}, trading_day=D8
        )
        vix = pack.by_id()["VIX"]
        self.assertFalse(vix.mask)
        self.assertEqual(vix.missing_reason, "NO_AVAILABLE_HISTORY")

        class MustNotRead(dict[str, ContextSource]):
            def get(self, key: str, default: object = None) -> object:
                raise AssertionError(f"source mapping read before wall: {key}")

        with self.assertRaisesRegex(C.EntryV2Refusal, "2025H2 HOLDOUT"):
            build_context_pack(
                "SI", decision, MustNotRead(), trading_day=20250701
            )

    def test_revised_value_poisoning_is_tensor_invariant(self) -> None:
        decision = 100 * NS
        poison_a = ContextSource(
            "FRED_DGS10",
            VintageClass.REVISED_VALUE,
            (AvailableObservation("poison-a", NS, (4.0,)),),
        )
        poison_b = ContextSource(
            "FRED_DGS10",
            VintageClass.REVISED_VALUE,
            (AvailableObservation("poison-b", 99 * NS, (-1.0e12,)),),
        )
        pack_a = build_context_pack(
            "SI", decision, {"FRED_DGS10": poison_a}, trading_day=D8
        )
        pack_b = build_context_pack(
            "SI", decision, {"FRED_DGS10": poison_b}, trading_day=D8
        )
        self.assertEqual(pack_a, pack_b)
        rate = pack_a.by_id()["FRED_DGS10"]
        self.assertFalse(rate.mask)
        self.assertEqual(rate.missing_reason, "REVISED_VALUE_MASKED")
        self.assertTrue(torch.equal(
            tensorize_context_pack(pack_a).values,
            tensorize_context_pack(pack_b).values,
        ))

    def test_actual_live_sources_smoke_and_deterministic_receipt(self) -> None:
        repository = load_context_repository("NKD", D8)
        decision = int(dt.datetime(
            2025, 1, 15, 12, tzinfo=dt.timezone.utc
        ).timestamp() * NS)
        pack = repository.pack(D8, decision)
        by_id = pack.by_id()
        for series_id in (
            "NIKKEI_VI", "GVZ", "VIX", "RVX", "JGB_10Y",
            "GOLD_SILVER_RATIO",
        ):
            self.assertTrue(by_id[series_id].mask, series_id)
            self.assertTrue(all(
                point.availability_ts_ns < decision
                for point in by_id[series_id].points
            ))
        # 2026-08-18 data ruling: COT/FRED market-rate series are FIRST_PRINT
        # (as-published records); only the re-weighted DTWEXBGS index remains
        # vintage-masked pending genuine ALFRED vintages.
        for series_id in ("COT_TFF_NIKKEI", "FRED_DGS10", "FRED_DEXJPUS"):
            self.assertTrue(by_id[series_id].mask, series_id)
            self.assertTrue(all(
                point.availability_ts_ns < decision
                for point in by_id[series_id].points
            ))
        self.assertEqual(
            by_id["FRED_DTWEXBGS"].missing_reason, "REVISED_VALUE_MASKED"
        )
        self.assertTrue(by_id["CAL_BOJ"].mask)
        # JGB unpadded-date regression: 2021+ rows must survive parsing, and
        # the last-64 window at a 2025 decision must reach recent stamps.
        self.assertGreaterEqual(
            max(point.stamp for point in by_id["JGB_10Y"].points), "2024-12-01"
        )

        tensor = tensorize_context_pack(pack)
        self.assertEqual(
            tuple(tensor.values.shape),
            (len(pack.series), 64, CONTEXT_TENSOR_WIDTH),
        )
        self.assertTrue(bool(tensor.valid.any()))
        self.assertTrue(bool(torch.isfinite(tensor.values).all()))

        rows = repository.receipt["series"]
        revised = [row for row in rows
                   if row["vintage_class"] == "REVISED_VALUE"]
        self.assertTrue(revised)
        self.assertTrue(all(
            row["status"] == "REVISED_VALUE_FILE_NOT_OPENED"
            and row["consumed_paths"] == []
            for row in revised
        ))
        repeat = load_context_repository("NKD", D8)
        self.assertEqual(
            repository.receipt["receipt_sha256"],
            repeat.receipt["receipt_sha256"],
        )
        receipt_payload = dict(repository.receipt)
        receipt_sha256 = receipt_payload.pop("receipt_sha256")
        self.assertEqual(C.object_sha256(receipt_payload), receipt_sha256)


if __name__ == "__main__":
    unittest.main()
