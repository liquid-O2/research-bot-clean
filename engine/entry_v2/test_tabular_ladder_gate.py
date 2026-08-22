"""RAIL-0 ladder gate checks (design/RAIL0_LADDER_GATE_SPEC.md, SC-RAIL0-*).

Synthetic regression checks only: they are not rehearsal, learning, or
economic evidence.  SC ids bind spec -> test -> receipt.
"""

from __future__ import annotations

from pathlib import Path
import unittest

from . import common as C
from .contracts import (
    CausalEntryExample, EntryScore, RawPrefixRef, SessionRef, Side,
)
from .replay import ReplayOutcome, ScoredArrival, replay
from .tabular_calibration import BlockReplayEvidence, evaluate_economic_gate
from .tabular_evaluation import load_policy_block_result
from .tabular_recovery_contracts import RecoveryConfig, RecoveryRefusal


_BASE = 1_704_278_400_000_000_000
_SHA = "a" * 64
_LADDER_DAYS = tuple(20240103 + offset for offset in range(10))
# SC-RAIL0-6 needs a genuinely pre-ladder published artifact; the frozen E1R
# forward block is one (its gate receipt was computed under the flat floor).
_PRE_LADDER_BLOCK = (C.REPO_ROOT / "artifacts/entry_v2/tabular_recovery/rehearsal"
                     / "fit_only/e1r/evaluation/E1R_frozen_FORWARD/real"
                     / "seed_20260820/calibrated_block.json")


def _ladder_trade(asset: str, day: int, index: int, pnl_usd: float
                  ) -> ScoredArrival:
    ts = _BASE + (int(day) - 20240103) * 86_400_000_000_000
    ts += C.ASSET_INDEX[asset] * 1_000_000_000 + index * 300_000_000_000
    exit_ts = ts + 60_000_000_000
    candidate = f"{asset}-{day}-t{index}"
    example = CausalEntryExample(
        candidate_id=candidate, asset=asset, trading_day=day,
        session_id=f"{asset}-{day}", decision_ts_ns=ts, side=Side.LONG,
        phase="2", locked_iid=0,
        raw_prefix_ref=RawPrefixRef(
            shard=f"ladder/{asset}/{day}", event_start_index=0,
            event_end_index=1, event_count=1, first_availability_ts_ns=1,
            last_availability_ts_ns=ts - 1, source_hash=_SHA),
        causal_features={"policy_snapshot_present": 1.0}, lineage_hash=_SHA)
    score = EntryScore(
        candidate_id=candidate, asset=asset, decision_ts_ns=ts,
        model_hash=_SHA, priority_score=float(pnl_usd), take_probability=1.0,
        expected_pnl_usd=float(pnl_usd), expected_pnl_lower_usd=float(pnl_usd),
        top3_probability=1.0, mae_p90_usd=0.0, wall_probability=0.0, enter=True)
    outcome = ReplayOutcome(
        candidate_id=candidate, close_ts_ns=exit_ts,
        close_pnl_usd=float(pnl_usd), phase_close_ts_ns=exit_ts,
        phase_close_pnl_usd=float(pnl_usd))
    return ScoredArrival(example, score, outcome)


def _ladder_evidence(*, usd_per_asset_day: float, ceiling_usd_per_day: float,
                     trades_per_asset_day: int = 1) -> BlockReplayEvidence:
    """Every asset gets the same replay dollars, ceiling and trade count."""

    arrivals = []
    sessions = []
    per_trade = float(usd_per_asset_day) / trades_per_asset_day
    for day in _LADDER_DAYS:
        for asset in C.ASSETS:
            sessions.append(SessionRef(asset, day, f"{asset}-{day}"))
            for index in range(trades_per_asset_day):
                arrivals.append(_ladder_trade(asset, day, index, per_trade))
    evaluation = replay(arrivals, expected_sessions=sessions)
    asset_ceiling = float(ceiling_usd_per_day) * len(_LADDER_DAYS)
    by_asset = tuple((asset, asset_ceiling) for asset in C.ASSETS)
    return BlockReplayEvidence(
        evaluation, asset_ceiling * len(C.ASSETS), _LADDER_DAYS, _LADDER_DAYS,
        tuple((asset, day) for asset in C.ASSETS for day in _LADDER_DAYS),
        by_asset, 1)


class LadderGateTest(unittest.TestCase):
    """SC-RAIL0-1..7 minus SC-RAIL0-5 (real-path, tools/regate_policy_block.py)."""

    def test_sc_rail0_1_supported_target_rung_refuses_below_two_thousand(self):
        gate = evaluate_economic_gate(
            _ladder_evidence(usd_per_asset_day=1_900.0,
                             ceiling_usd_per_day=2_870.0),
            config=RecoveryConfig())
        for asset in C.ASSETS:
            self.assertIn(f"ASSET_DAY_LADDER:{asset}", gate.reasons)
            self.assertEqual(gate.ladder[asset]["rung_usd"],
                             C.TARGET_ASSET_DAY_USD)
            self.assertTrue(gate.ladder[asset]["rung_supported"])
            self.assertAlmostEqual(gate.ladder[asset]["ceiling_usd_per_day"],
                                   2_870.0)

    def test_sc_rail0_2_fallback_rung_passes_when_ceiling_cannot_support_target(self):
        gate = evaluate_economic_gate(
            _ladder_evidence(usd_per_asset_day=1_600.0,
                             ceiling_usd_per_day=1_900.0),
            config=RecoveryConfig())
        for asset in C.ASSETS:
            self.assertNotIn(f"ASSET_DAY_LADDER:{asset}", gate.reasons)
            self.assertEqual(gate.ladder[asset]["rung_usd"],
                             C.LADDER_FALLBACK_ASSET_DAY_USD)
            self.assertTrue(gate.ladder[asset]["rung_supported"])

    def test_sc_rail0_3_usd_per_trade_is_reported_not_refused(self):
        # $450/trade under the $600 preference; $1,800/asset-day clears the
        # $1,500 rung, so after L1+L2 nothing refuses.  SC-RAIL0-3 asks for a
        # fixture whose ONLY old-gate failure is usd_per_trade; that is
        # unreachable -- $450/trade needs >4 trades/asset-day to clear the old
        # flat $2,000 floor, and 5x3 assets breaks MAX_ENTRIES_PORTFOLIO_DAY=12
        # -- so the red run showed ('USD_PER_TRADE:SI','ASSET_DAY_FLOOR:SI',...)
        # and this is the closest fixture that proves the demotion.
        gate = evaluate_economic_gate(
            _ladder_evidence(usd_per_asset_day=1_800.0,
                             ceiling_usd_per_day=2_000.0,
                             trades_per_asset_day=4),
            config=RecoveryConfig())
        self.assertTrue(gate.laws_pass, gate.reasons)
        self.assertEqual(gate.reasons, ())
        for asset in C.ASSETS:
            self.assertAlmostEqual(gate.usd_per_trade_by_asset[asset], 450.0)
        self.assertLess(gate.usd_per_trade,
                        RecoveryConfig().minimum_usd_per_trade)

    def test_sc_rail0_4_unsupported_fallback_rung_is_reported_not_lowered(self):
        gate = evaluate_economic_gate(
            _ladder_evidence(usd_per_asset_day=1_300.0,
                             ceiling_usd_per_day=1_200.0),
            config=RecoveryConfig())
        for asset in C.ASSETS:
            self.assertIn(f"ASSET_DAY_LADDER:{asset}", gate.reasons)
            self.assertEqual(gate.ladder[asset]["rung_usd"],
                             C.LADDER_FALLBACK_ASSET_DAY_USD)
            self.assertFalse(gate.ladder[asset]["rung_supported"])

    def test_sc_rail0_6_pre_ladder_artifact_strict_reload_refuses(self):
        self.assertTrue(_PRE_LADDER_BLOCK.is_file(), _PRE_LADDER_BLOCK)
        with self.assertRaises(RecoveryRefusal) as caught:
            load_policy_block_result(_PRE_LADDER_BLOCK, config=RecoveryConfig())
        self.assertEqual(str(caught.exception),
                         "strict block replay gate differs")

    def test_sc_rail0_7_rung_boundary_mutant(self):
        exact = evaluate_economic_gate(
            _ladder_evidence(usd_per_asset_day=1_900.0,
                             ceiling_usd_per_day=2_500.0),
            config=RecoveryConfig())
        below = evaluate_economic_gate(
            _ladder_evidence(usd_per_asset_day=1_900.0,
                             ceiling_usd_per_day=2_499.0),
            config=RecoveryConfig())
        for asset in C.ASSETS:
            self.assertEqual(exact.ladder[asset]["rung_usd"],
                             C.TARGET_ASSET_DAY_USD)
            self.assertEqual(below.ladder[asset]["rung_usd"],
                             C.LADDER_FALLBACK_ASSET_DAY_USD)


if __name__ == "__main__":
    unittest.main()
