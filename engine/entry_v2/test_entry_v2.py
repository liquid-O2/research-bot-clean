"""Focused causality and policy tests for the clean entry contracts."""

from __future__ import annotations

from dataclasses import replace
import unittest

from engine.entry_v2.context_pack import (
    AvailableObservation,
    ContextSource,
    build_context_pack,
)
from engine.entry_v2.contracts import (
    CausalEntryExample,
    ContractError,
    EntryScore,
    ExitReason,
    NANOS_PER_SECOND,
    RawPrefixRef,
    SessionRef,
    Side,
    VintageClass,
)
from engine.entry_v2.replay import (
    ReplayOutcome,
    ScoredArrival,
    candidate_ceiling,
    replay,
)
from engine.entry_v2.teacher import TeacherPath, build_teacher_store


NS = NANOS_PER_SECOND
D8 = 20250102


def example(candidate_id: str, asset: str, second: float, *,
            day: int = D8, session: str | None = None,
            features: dict[str, float] | None = None) -> CausalEntryExample:
    ts = int(second * NS)
    return CausalEntryExample(
        candidate_id=candidate_id,
        asset=asset,
        trading_day=day,
        session_id=session or f"{asset}-{day}",
        decision_ts_ns=ts,
        side=Side.LONG,
        phase="TOKYO",
        locked_iid=11,
        raw_prefix_ref=RawPrefixRef(
            shard=f"{asset}/{day}.npz",
            event_start_index=0,
            event_end_index=1,
            event_count=1,
            first_availability_ts_ns=ts - 10,
            last_availability_ts_ns=ts - 10,
            source_hash="raw-hash",
        ),
        causal_features=features or {"spread_ticks": 1.0},
        context=None,
        lineage_hash="lineage-hash",
    )


def score(item: CausalEntryExample, priority: float, *, enter: bool = True,
          model_hash: str = "model-hash") -> EntryScore:
    return EntryScore(
        candidate_id=item.candidate_id,
        asset=item.asset,
        decision_ts_ns=item.decision_ts_ns,
        model_hash=model_hash,
        priority_score=priority,
        take_probability=0.9 if enter else 0.1,
        expected_pnl_usd=priority,
        expected_pnl_lower_usd=priority,
        top3_probability=0.5,
        mae_p90_usd=100.0,
        wall_probability=0.1,
        enter=enter,
    )


def outcome(item: CausalEntryExample, exit_second: float, pnl: float, *,
            phase_second: float = 1_000.0,
            phase_pnl: float | None = None,
            wall_second: float | None = None) -> ReplayOutcome:
    return ReplayOutcome(
        candidate_id=item.candidate_id,
        close_ts_ns=int(exit_second * NS),
        close_pnl_usd=pnl,
        phase_close_ts_ns=int(phase_second * NS),
        phase_close_pnl_usd=pnl if phase_pnl is None else phase_pnl,
        wall_hit_ts_ns=None if wall_second is None else int(wall_second * NS),
    )


class ContextContractTests(unittest.TestCase):
    def test_last64_strict_availability_future_invariant_and_revised_mask(self) -> None:
        decision = 100 * NS
        past = tuple(AvailableObservation(str(i), i * NS, (float(i),))
                     for i in range(1, 71))
        future_a = (AvailableObservation("equal", decision, (1_000.0,)),
                    AvailableObservation("future", 120 * NS, (2_000.0,)))
        future_b = (AvailableObservation("equal-mutated", decision, (-9_000.0,)),
                    AvailableObservation("future-mutated", 999 * NS, (9_000.0,)))
        revised = ContextSource(
            "FRED_DGS10", VintageClass.REVISED_VALUE,
            (AvailableObservation("old", NS, (4.0,)),),
        )
        sources_a = {
            "VIX": ContextSource("VIX", VintageClass.FIRST_PRINT, past + future_a),
            "FRED_DGS10": revised,
        }
        sources_b = {
            "VIX": ContextSource("VIX", VintageClass.FIRST_PRINT, past + future_b),
            "FRED_DGS10": revised,
        }
        pack_a = build_context_pack(
            "SI", decision, sources_a, trading_day=D8,
            roster=("VIX", "FRED_DGS10", "MISSING"))
        pack_b = build_context_pack(
            "SI", decision, sources_b, trading_day=D8,
            roster=("VIX", "FRED_DGS10", "MISSING"))
        self.assertEqual(pack_a, pack_b)
        vix = pack_a.by_id()["VIX"]
        self.assertEqual(len(vix.points), 64)
        self.assertEqual(vix.points[0].values, (7.0,))
        self.assertEqual(vix.points[0].deltas, (1.0,))
        self.assertTrue(all(point.availability_ts_ns < decision for point in vix.points))
        self.assertFalse(pack_a.by_id()["FRED_DGS10"].mask)
        self.assertEqual(pack_a.by_id()["FRED_DGS10"].missing_reason,
                         "REVISED_VALUE_MASKED")
        self.assertFalse(pack_a.by_id()["MISSING"].mask)

    def test_future_fields_and_event_at_decision_refuse(self) -> None:
        for name in ("cert_close_usd", "oracle_action", "take_target"):
            with self.subTest(name=name), self.assertRaises(ContractError):
                example("bad-feature", "SI", 10, features={name: 1.0})
        good = example("bad-prefix", "SI", 10)
        bad_prefix = replace(good.raw_prefix_ref,
                             first_availability_ts_ns=good.decision_ts_ns,
                             last_availability_ts_ns=good.decision_ts_ns)
        with self.assertRaises(ContractError):
            replace(good, raw_prefix_ref=bad_prefix)


class TeacherControlTests(unittest.TestCase):
    def test_exact_teacher_action_changes_with_occupancy_and_cap(self) -> None:
        specs = (
            ("p1", 10, 30, 1_000.0),
            ("p2", 20, 25, 3_000.0),  # better, but arrives while p1 is open
            ("p3", 30, 40, 800.0),
            ("p4", 50, 60, 2_000.0),
            ("p5", 70, 80, 1_500.0),
        )
        paths = tuple(TeacherPath(
            candidate_id=cid, asset="SI", trading_day=D8,
            decision_ts_ns=dec * NS, exit_ts_ns=ex * NS,
            cert_close_usd=value, mfe_usd=value + 100.0, mae_usd=100.0,
            wall_hit=False, time_to_peak_sec=5.0,
        ) for cid, dec, ex, value in specs)
        examples = tuple(example(cid, "SI", dec) for cid, dec, _ex, _v in specs)
        store = build_teacher_store(
            paths, expected_sessions=(examples[0].session,)
        )
        self.assertTrue(all(store[cid].payer for cid, *_ in specs))
        # Decisions are final on arrival: later, higher-value p2 cannot change
        # p1.  p2 is occupied and p3 arrives exactly at p1's exit, so both are
        # masked rather than supervised as bad actions.
        self.assertEqual(
            {cid: store[cid].take_target for cid, *_ in specs},
            {"p1": True, "p2": False, "p3": False,
             "p4": True, "p5": True},
        )
        self.assertTrue(store["p1"].action_loss_mask)
        self.assertFalse(store["p2"].action_loss_mask)
        self.assertFalse(store["p3"].action_loss_mask)
        self.assertEqual(store["p2"].rank, 1)
        self.assertEqual(store["p3"].rank, 5)

        scores = store.truth_scores(
            examples,
            entry_thresholds_usd={"SI": 600.0, "HG": 600.0, "NKD": 600.0},
        )
        score_by_id = {item.candidate_id: item for item in scores}
        arrivals = tuple(ScoredArrival(
            item,
            score_by_id[item.candidate_id],
            outcome(item, ex, value),
        ) for item, (_cid, _dec, ex, value) in zip(examples, specs))
        result = replay(arrivals, expected_sessions=(examples[0].session,))
        self.assertEqual([trade.candidate_id for trade in result.trade_results],
                         ["p1", "p4", "p5"])
        self.assertEqual(result.total_pnl_usd, 4_500.0)
        ceiling = candidate_ceiling(arrivals, expected_sessions=(examples[0].session,))
        self.assertEqual(
            {trade.candidate_id for trade in ceiling.evaluation.trade_results},
            {"p2", "p4", "p5"},
        )
        self.assertEqual(ceiling.evaluation.total_pnl_usd, 6_500.0)

        with self.assertRaisesRegex(ContractError, "outside expected sessions"):
            build_teacher_store(
                paths,
                expected_sessions=(SessionRef("SI", 20250103, "wrong"),),
            )

        shuffled = store.shuffled(17)
        self.assertNotEqual(store.store_hash, shuffled.store_hash)
        self.assertEqual(
            [shuffled[cid].action_loss_mask for cid, *_ in specs],
            [store[cid].action_loss_mask for cid, *_ in specs],
        )
        self.assertTrue(all(
            not shuffled[cid].take_target or shuffled[cid].action_loss_mask
            for cid, *_ in specs
        ))
        self.assertEqual(
            shuffled.control_metadata["action_loss_mask"], "RECIPIENT_FIXED"
        )
        self.assertEqual({item.candidate_id for item in shuffled.truth_scores(
                             examples,
                             entry_thresholds_usd={"SI": 600.0, "HG": 600.0,
                                                   "NKD": 600.0})},
                         {item.candidate_id for item in examples})
        self.assertTrue(all(shuffled[cid].cert_close_usd != store[cid].cert_close_usd
                            for cid in ("p1", "p2", "p3", "p4", "p5")))
        vector = lambda label: (
            label.cert_close_usd, label.take_target, label.action_loss_mask
        )
        self.assertEqual(
            sorted(vector(shuffled[cid]) for cid, *_ in specs),
            sorted(vector(store[cid]) for cid, *_ in specs),
        )

    def test_same_timestamp_highest_wins_peers_negative_and_cap_masks(self) -> None:
        specs = (
            ("same-low", 10, 11, 700.0),
            ("same-high-z", 10, 11, 1_500.0),
            ("same-high-a", 10, 11, 1_500.0),
            ("second", 20, 21, 900.0),
            ("third", 30, 31, 800.0),
            ("capped", 40, 41, 4_000.0),
        )
        paths = tuple(TeacherPath(
            candidate_id=cid, asset="SI", trading_day=D8,
            decision_ts_ns=dec * NS, exit_ts_ns=ex * NS,
            cert_close_usd=value, mfe_usd=value, mae_usd=10.0,
            wall_hit=False, time_to_peak_sec=1.0,
        ) for cid, dec, ex, value in specs)
        store = build_teacher_store(
            paths, expected_sessions=(SessionRef("SI", D8, f"SI-{D8}"),)
        )
        self.assertTrue(store["same-high-a"].take_target)
        self.assertFalse(store["same-high-z"].take_target)
        self.assertFalse(store["same-low"].take_target)
        self.assertTrue(store["same-high-z"].action_loss_mask)
        self.assertTrue(store["same-low"].action_loss_mask)
        self.assertFalse(store["capped"].take_target)
        self.assertFalse(store["capped"].action_loss_mask)

class ArrivalReplayTests(unittest.TestCase):
    def test_exact_timestamp_batch_occupancy_and_future_mutation(self) -> None:
        low = example("low", "SI", 10.1)
        high = example("high", "SI", 10.9)
        overlap = example("overlap", "SI", 15)
        after = example("after", "SI", 20)
        future = example("future", "SI", 100)
        base = (
            ScoredArrival(low, score(low, 100), outcome(low, 19, 100)),
            ScoredArrival(high, score(high, 200), outcome(high, 20, 200)),
            ScoredArrival(overlap, score(overlap, 500), outcome(overlap, 18, 500)),
            ScoredArrival(after, score(after, 150), outcome(after, 25, 150)),
        )
        result = replay(base, expected_sessions=(low.session,))
        self.assertEqual([trade.candidate_id for trade in result.trade_results],
                         ["low", "after"])

        same_low = example("same-low", "SI", 30.1)
        same_high = example("same-high", "SI", 30.1)
        simultaneous = replay((
            ScoredArrival(
                same_low, score(same_low, 100), outcome(same_low, 31, 100)
            ),
            ScoredArrival(
                same_high, score(same_high, 200), outcome(same_high, 31, 200)
            ),
        ), expected_sessions=(same_low.session,))
        self.assertEqual(
            [trade.candidate_id for trade in simultaneous.trade_results],
            ["same-high"],
        )

        low_future = ScoredArrival(future, score(future, 1), outcome(future, 101, 1))
        high_future = ScoredArrival(future, score(future, 99_999),
                                    outcome(future, 101, 1))
        result_a = replay(base + (low_future,), expected_sessions=(low.session,))
        result_b = replay(base + (high_future,), expected_sessions=(low.session,))
        early_a = tuple(t.candidate_id for t in result_a.trade_results if t.entry_ts_ns < 100 * NS)
        early_b = tuple(t.candidate_id for t in result_b.trade_results if t.entry_ts_ns < 100 * NS)
        self.assertEqual(early_a, early_b)
        self.assertEqual(early_a, ("low", "after"))

    def test_exact_timestamp_ranking_ignores_all_diagnostics(self) -> None:
        winner = example("a-deterministic", "SI", 30.1)
        loser = example("z-diagnostic", "SI", 30.1)
        base_score = score(winner, 0.7)
        winner_score = replace(
            base_score,
            candidate_id=winner.candidate_id,
            expected_pnl_usd=-1e12,
            expected_pnl_lower_usd=-1e12,
            mae_p90_usd=1e12,
            wall_probability=1.0,
        )
        loser_score = replace(
            base_score,
            candidate_id=loser.candidate_id,
            expected_pnl_usd=1e12,
            expected_pnl_lower_usd=1e12,
            mae_p90_usd=0.0,
            wall_probability=0.0,
        )
        result = replay((
            ScoredArrival(winner, winner_score, outcome(winner, 31, 100.0)),
            ScoredArrival(loser, loser_score, outcome(loser, 31, 999.0)),
        ), expected_sessions=(winner.session,))
        self.assertEqual(
            tuple(row.candidate_id for row in result.trade_results),
            ("a-deterministic",),
        )

    def test_wall_phase_close_caps_and_asset_day_denominator(self) -> None:
        wall = example("wall", "SI", 10)
        phase = example("phase", "SI", 20)
        first = ScoredArrival(
            wall, score(wall, 100),
            outcome(wall, 50, 1_000, phase_second=60, wall_second=15))
        second = ScoredArrival(
            phase, score(phase, 100),
            outcome(phase, 50, 1_000, phase_second=30, phase_pnl=300))
        result = replay((first, second), expected_sessions=(wall.session,))
        self.assertEqual(result.trade_results[0].exit_reason, ExitReason.WALL)
        self.assertEqual(result.trade_results[0].pnl_usd, -900.0)
        self.assertEqual(result.trade_results[1].exit_reason, ExitReason.PHASE_CLOSE)
        self.assertEqual(result.trade_results[1].pnl_usd, 300.0)
        self.assertEqual(result.max_drawdown_usd, 900.0)

        arrivals = []
        expected = []
        for asset in ("SI", "HG", "NKD"):
            expected.append(SessionRef(asset, D8, f"{asset}-{D8}"))
            for k in range(4):
                item = example(f"{asset}-{k}", asset, 100 + k * 2)
                arrivals.append(ScoredArrival(
                    item, score(item, 100 - k), outcome(item, 101 + k * 2, 100)))
        expected.extend((
            SessionRef("SI", D8, f"SI-{D8}-second-session-empty"),
            SessionRef("SI", 20250103, "SI-20250103-empty"),
        ))
        capped = replay(arrivals, expected_sessions=expected)
        self.assertEqual(capped.trades, 9)
        self.assertEqual([row.trades for row in capped.by_asset], [3, 3, 3])
        self.assertEqual(capped.asset_days, 4)
        self.assertEqual(capped.zero_asset_days, 1)
        self.assertEqual(capped.total_pnl_usd, 900.0)
        self.assertEqual(capped.usd_per_asset_day, 225.0)

    def test_drawdown_is_cumulative_per_asset_and_wall_loss_carries_cost(self) -> None:
        losses = tuple(
            example(f"loss-{i}", "SI", 100 + i * 100,
                    day=20250102 + i, session=f"SI-loss-{i}")
            for i in range(2)
        )
        profit = example(
            "profit", "SI", 50, day=20250102, session="SI-loss-0"
        )
        arrivals = [ScoredArrival(
            profit, score(profit, 20), outcome(profit, 60, 1_000.0)
        )]
        for i, item in enumerate(losses):
            result = ReplayOutcome(
                candidate_id=item.candidate_id,
                close_ts_ns=item.decision_ts_ns + 20 * NS,
                close_pnl_usd=0.0,
                phase_close_ts_ns=item.decision_ts_ns + 30 * NS,
                phase_close_pnl_usd=0.0,
                wall_hit_ts_ns=item.decision_ts_ns + 10 * NS,
                wall_pnl_usd=-905.0,
            )
            arrivals.append(ScoredArrival(item, score(item, 10 - i), result))
        evaluation = replay(arrivals,
                            expected_sessions=tuple(item.session for item in losses))
        self.assertEqual([row.pnl_usd for row in evaluation.trade_results],
                         [1_000.0, -905.0, -905.0])
        self.assertEqual(evaluation.max_drawdown_usd, 1_810.0)
        self.assertEqual(evaluation.drawdown_p90_usd, 905.0)
        self.assertEqual(evaluation.drawdown_breach_rate, 0.0)
        self.assertEqual(evaluation.by_asset[0].max_drawdown_usd, 1_810.0)


if __name__ == "__main__":
    unittest.main()
