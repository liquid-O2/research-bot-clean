from __future__ import annotations

import unittest

from . import common as C
from .capacity_contract import (
    DENOMINATOR, SCHEMA, capacity_eligibility, threshold_feasibility,
    validate_capacity_document,
)


def _row(*, trades=10, total=18_000.0, days_with_trades=3,
         mdd=900.0, oracle_total=22_500.0, regime="FULL"):
    days = 9
    row = {
        "included_trading_days": days, "trades": trades,
        "total_pnl_usd": total, "usd_per_asset_day": total / days,
        "usd_per_trade": total / trades if trades else 0.0,
        "oracle_total_pnl_usd": oracle_total,
        "oracle_usd_per_asset_day": oracle_total / days,
        "oracle_capture": total / oracle_total if oracle_total else 0.0,
        "chronological_max_drawdown_usd": mdd,
        "drawdown_p90_usd": min(mdd, 400.0),
        "days_with_trades": days_with_trades, "capacity_regime": regime,
        "values_clipped": False, "asset_day_denominator": DENOMINATOR,
        "replay_receipt_sha256": "1" * 64,
        "oracle_replay_receipt_sha256": "2" * 64,
    }
    eligibility = capacity_eligibility(row)
    row.update({
        "threshold_feasibility_sha256": eligibility.threshold_feasibility_sha256,
        "capacity_eligibility_sha256": eligibility.receipt_sha256,
        "eligibility": "ELIGIBLE" if eligibility.eligible else "INELIGIBLE",
    })
    return row


def _document(row):
    return {"schema": SCHEMA, "values_clipped": False,
            "asset_day_denominator": DENOMINATOR,
            "per_asset": {asset: dict(row) for asset in C.ASSETS}}


class CapacityContractTest(unittest.TestCase):
    def test_threshold_trade_day_coverage_and_low_strict_mdd(self):
        covered = threshold_feasibility(
            trades=C.MIN_TRADES, usd_per_trade=600.0,
            max_drawdown_usd=1000.0, days_with_trades=3, eligible_days=9)
        self.assertTrue(covered.feasible)
        sparse = threshold_feasibility(
            trades=C.MIN_TRADES, usd_per_trade=600.0,
            max_drawdown_usd=1000.0, days_with_trades=2, eligible_days=9)
        self.assertFalse(sparse.feasible)
        self.assertIn("TRADE_DAY_COVERAGE_BELOW_MINIMUM", sparse.reasons)

        low = _row(total=9_000.0, oracle_total=10_800.0,
                   regime="LOW", mdd=500.0)
        eligibility = capacity_eligibility(low)
        self.assertFalse(eligibility.eligible)
        self.assertIn("LOW_CAPACITY_MDD_NOT_BELOW_LIMIT", eligibility.reasons)

    def test_goal_optional_validation_preserves_measured_failures(self):
        validate_capacity_document(_document(_row()), require_goal=True)
        zero = _row(trades=0, total=0.0, days_with_trades=0, mdd=0.0)
        validate_capacity_document(_document(zero), require_goal=False)
        with self.assertRaisesRegex(C.EntryV2Refusal, "do not reconcile"):
            validate_capacity_document(_document(zero), require_goal=True)
        negative = _row(total=-9_000.0)
        validate_capacity_document(_document(negative), require_goal=False)


if __name__ == "__main__":
    unittest.main()
