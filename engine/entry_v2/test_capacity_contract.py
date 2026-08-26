from __future__ import annotations

import unittest

from . import common as C
from .capacity_contract import capacity_eligibility, threshold_feasibility


def _row(*, trades=10, total=18_000.0, days_with_trades=3,
         mdd=900.0, oracle_total=22_500.0, regime="FULL"):
    days = 9
    return {
        "included_trading_days": days, "trades": trades,
        "total_pnl_usd": total, "usd_per_asset_day": total / days,
        "usd_per_trade": total / trades if trades else 0.0,
        "oracle_total_pnl_usd": oracle_total,
        "oracle_usd_per_asset_day": oracle_total / days,
        "oracle_capture": total / oracle_total if oracle_total else 0.0,
        "chronological_max_drawdown_usd": mdd,
        "days_with_trades": days_with_trades, "capacity_regime": regime,
    }


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


if __name__ == "__main__":
    unittest.main()
