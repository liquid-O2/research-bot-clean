#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from . import common as C
from .plan_contract import verify_plan_contract


class PlanContractTest(unittest.TestCase):
    def test_live_authority_and_asset_day_goal(self) -> None:
        contract = verify_plan_contract()
        self.assertEqual(contract.minimum_asset_day_usd, 2_000.0)
        self.assertEqual(contract.denominator, "asset_trading_day")
        self.assertIn("maximize", contract.objective)
        self.assertEqual(contract.receipt()["schema"], "entry-v2-plan-contract-v3")
        self.assertEqual(len(contract.clock_law_sha256), 64)
        self.assertEqual(len(contract.neural_diagnostic_sha256), 64)

    def test_missing_or_mutated_authority_refuses(self) -> None:
        with tempfile.TemporaryDirectory(dir=C.CACHE_ROOT) as td:
            root = Path(td)
            (root / "design").mkdir()
            (root / "design" / "ENTRY_V2_RECOVERY_PLAN.md").write_text("wrong")
            (root / "design" / "ENTRY_V2_RECOVERY_PLAN_AMENDMENTS.md").write_text(
                "wrong"
            )
            with self.assertRaisesRegex(C.EntryV2Refusal, "authority drifted"):
                verify_plan_contract(root)


if __name__ == "__main__":
    unittest.main()
