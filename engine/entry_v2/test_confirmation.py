"""Cheap correctness and method-understanding checks for confirmation V1."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np

from engine.entry_v2 import common as C
from engine.entry_v2 import confirmation
from engine.entry_v2.confirmation import (
    ConfirmationConfig, ConfirmationDataset, ConfirmationOpportunitySet,
    ConfirmationRefusal, confirmation_implementation_hashes,
    _OutcomeIndex, learnable_confirmation_count, read_versioned_tsv,
)
from engine.entry_v2.confirmation_diagnostics import (
    registered_feature_ablations, registered_feature_sets,
    registered_policy_grid, score_confirmation_policies,
    shuffle_confirmation_targets,
)
from engine.entry_v2.confirmation_model import (
    ConfirmationModel, ConfirmationModelConfig, ConfirmationPredictions,
    FitOnlyFeatureSelector, fit_confirmation_model,
)
from engine.entry_v2.confirmation_policy import (
    ConfirmationPolicy, default_expected_sessions,
    exact_delayed_candidate_ceiling,
    exact_delayed_candidate_ceiling_shards,
    first_trigger_indices,
)
from engine.entry_v2.confirmation_experiment import (
    FEATURE_CACHE_SCHEMA, _record_from_manifest,
)
from engine.entry_v2.diagnostic_inputs import (
    build_candidate_truth_bindings, build_event_truth_columns,
)
from engine.entry_v2.event_pack import EventPack


ROOT = Path("/workspace/artifacts/cache/port/entry_v2")
REAL_AVAILABLE = all(path.is_file() for path in (
    ROOT / "events/SI/20210804.qre2",
    ROOT / "g1/candidates/SI/20210804.tsv",
    ROOT / "g1/teacher/SI/20210804.tsv",
))


def _synthetic_dataset(day: int, *, mode: str = "TRAINING",
                       series_count: int = 30) -> ConfirmationDataset:
    config = ConfirmationConfig(max_delay_sec=300, snapshot_mode=mode)
    names = ("state_signal", "state_age", "state_side", "w5_opposing_absorption",
             "w5_bid_reload", "w5_path_efficiency", "w5_aligned_trade_flow",
             "aligned_from_formation_mean_usd", "w5_favorable_excursion_usd")
    rows = []
    for series in range(series_count):
        for step in range(3):
            if series % 3 == 0:
                pnl = (-905.0, -100.0, 1_200.0)[step]
            elif series % 3 == 1:
                pnl = (100.0, -905.0, -905.0)[step]
            else:
                pnl = (700.0, 850.0, 1_000.0)[step]
            # Keep synthetic trading days temporally disjoint just as the
            # authoritative exchange timestamps are.  Replay occupancy is a
            # continuous clock and intentionally does not reset by date.
            base = (1_620_000_000_000_000_000
                    + (day - 20_210_101) * 100_000_000_000_000)
            snapshot = base + series * 100_000_000_000 + step * 1_000_000_000
            rows.append((series, step, pnl, snapshot))
    n = len(rows)
    opportunity = np.asarray([
        C.object_sha256({"day": day, "series": s, "step": k})
        for s, k, _p, _ts in rows], str)
    series_id = np.asarray([
        C.object_sha256({"day": day, "series": s})
        for s, _k, _p, _ts in rows], str)
    candidate_id = np.asarray([f"candidate-{day}-{s}" for s, *_ in rows], str)
    pnl = np.asarray([p for _s, _k, p, _ts in rows], np.float64)
    step = np.asarray([k for _s, k, _p, _ts in rows], np.float64)
    side = np.asarray([1 if s % 2 == 0 else -1 for s, *_ in rows], np.int8)
    signal = pnl / 1_000.0 + np.asarray([((s * 7 + k) % 5) * .01
                                        for s, k, _p, _ts in rows])
    features = np.column_stack((
        signal, step, side, -signal, np.maximum(signal, 0),
        np.abs(signal), signal * side, signal, np.maximum(signal, 0),
    )).astype(np.float32)
    snapshot = np.asarray([ts for _s, _k, _p, ts in rows], np.int64)
    cutoff = np.asarray([10 + k for _s, k, _p, _ts in rows], np.int64)
    bid = np.full(n, 25_000_000_000, np.int64)
    ask = np.full(n, 25_005_000_000, np.int64)
    receipt = C.object_sha256({"synthetic": day, "mode": mode})
    dataset = ConfirmationDataset(
        feature_names=names, features=features,
        opportunity_id=opportunity, series_id=series_id,
        candidate_id=candidate_id, asset=np.full(n, "SI"),
        day=np.full(n, day, np.int64), side=side, phase=np.full(n, "2"),
        snapshot_ts_ns=snapshot, phase_close_ts_ns=snapshot + 50_000_000_000,
        event_cutoff=cutoff, entry_event_ordinal=cutoff - 1,
        entry_availability_ts_ns=snapshot - 1,
        entry_bid_px=bid, entry_ask_px=ask, entry_mid2=bid + ask,
        entry_spread_usd=np.full(n, 25.0),
        frozen_cost_usd=np.full(n, 30.0),
        candidate_count=np.ones(n, np.int16),
        min_alert_age_sec=step, max_alert_age_sec=step,
        cert_close_usd=pnl,
        mfe_usd=np.maximum(pnl, 0), mae_usd=np.maximum(-pnl, 0),
        wall_hit=pnl <= -900.0, exit_ts_ns=snapshot + 10_000_000_000,
        feature_receipt_sha256=np.full(n, receipt),
        max_delay_sec=300, snapshot_mode=mode,
        config_sha256=config.receipt_sha256, source_receipts=(receipt,),
    )
    dataset.validate(); return dataset


def _synthetic_opportunity_set(day: int) -> ConfirmationOpportunitySet:
    dataset = _synthetic_dataset(day, mode="REPLAY")
    result = ConfirmationOpportunitySet(
        **{name: np.asarray(getattr(dataset, name)).copy() for name in (
            "opportunity_id", "series_id", "candidate_id", "asset", "day",
            "side", "phase", "snapshot_ts_ns", "phase_close_ts_ns",
            "event_cutoff", "entry_event_ordinal",
            "entry_availability_ts_ns", "cert_close_usd", "mfe_usd",
            "mae_usd", "wall_hit", "exit_ts_ns",
            "feature_receipt_sha256")},
        max_delay_sec=dataset.max_delay_sec,
        snapshot_mode=dataset.snapshot_mode,
        config_sha256=dataset.config_sha256,
        source_receipts=dataset.source_receipts,
    )
    result.validate()
    return result


class CorpusAgeGrid(unittest.TestCase):
    """The corpus row grid (ticket 42).

    The corpus does not need every scheduled age. It needs the ages the entry
    work actually reads, and cutting below that silently disarms measurements
    that have already decided things: the ticket-29 decay bound reads eight ages
    and a four-age corpus cannot answer it at all.
    """

    def test_corpus_grid_is_a_strict_subset_of_the_schedule(self) -> None:
        scheduled = set(confirmation.training_offsets_seconds(300))
        grid = set(confirmation.CORPUS_AGE_GRID_SECONDS)
        self.assertTrue(grid < scheduled,
                        "the corpus grid must be a STRICT subset of the schedule; "
                        f"off-schedule ages: {sorted(grid - scheduled)}")

    def test_selecting_the_corpus_grid_changes_the_receipt(self) -> None:
        full = confirmation.ConfirmationConfig(max_delay_sec=300)
        corpus = confirmation.ConfirmationConfig(max_delay_sec=300, age_grid="CORPUS")
        self.assertEqual(full.offsets, confirmation.training_offsets_seconds(300),
                         "the FULL path must be byte-for-byte what it was")
        self.assertEqual(corpus.offsets, confirmation.CORPUS_AGE_GRID_SECONDS)
        self.assertNotEqual(full.receipt_sha256, corpus.receipt_sha256,
                            "a corpus built on a reduced grid must not be able to "
                            "pass as a full-resolution one")
        # Two independent paths protect that: the age_grid field is in asdict,
        # AND the resolved offsets are in the receipt. Pin the second one too,
        # by moving the grid with the field held constant - otherwise a future
        # refactor could drop offsets from the receipt and nothing would notice.
        with mock.patch.object(confirmation, "CORPUS_AGE_GRID_SECONDS",
                               (0, 60, 180, 300)):
            narrower = confirmation.ConfirmationConfig(
                max_delay_sec=300, age_grid="CORPUS").receipt_sha256
        self.assertNotEqual(
            corpus.receipt_sha256, narrower,
            "two corpora built on DIFFERENT age grids share a receipt sha; the "
            "resolved offsets are not reaching receipt_sha256")

    def test_an_unknown_grid_is_refused(self) -> None:
        with self.assertRaises(confirmation.ConfirmationRefusal):
            confirmation.ConfirmationConfig(age_grid="SOMETHING_ELSE")

    def test_late_grid_resolves_the_preregistered_schedule(self) -> None:
        expected = (
            0, 30, 60, 90, 120, 180, 240, 290, 300,
            600, 1200, 2400, 3600, 5400, 7200, 10800,
        )
        config = confirmation.ConfirmationConfig(
            max_delay_sec=10800, age_grid="LATE")
        self.assertEqual(config.offsets, expected)

    def test_late_grid_refuses_an_off_schedule_age(self) -> None:
        config = confirmation.ConfirmationConfig(
            max_delay_sec=10800, age_grid="LATE")
        with mock.patch.object(
                confirmation, "LATE_AGE_GRID_SECONDS",
                (*confirmation.LATE_AGE_GRID_SECONDS, 10830)):
            with self.assertRaisesRegex(
                    confirmation.ConfirmationRefusal, "does not contain"):
                _ = config.offsets


class ConfirmationUnitTests(unittest.TestCase):
    def test_materialization_cache_binds_complete_implementation_roster(
            self) -> None:
        hashes = dict(confirmation_implementation_hashes())
        self.assertEqual(set(hashes), {
            "availability_clock", "common_contract", "confirmation",
            "confirmation_cache", "context_pack", "contracts",
            "discretionary_features", "event_pack", "forecast_features",
            "label_truth", "slow_context",
        })
        self.assertTrue(all(len(value) == 64 for value in hashes.values()))

    def test_materialization_cache_refuses_stale_dependency_roster(self) -> None:
        source = {"asset": "SI", "trading_day": 20240102}
        config_sha = "c" * 64
        path = Path("/workspace/artifacts/test-only-manifest.json")
        core = {
            "schema": FEATURE_CACHE_SCHEMA, "source": source,
            "config_sha256": config_sha,
            "implementation_sha256": dict(
                confirmation_implementation_hashes()),
            "status": "NO_NATIVE_CANDIDATES", "dataset_path": None,
            "dataset_sha256": None,
            "dataset_representation_sha256": None,
            "empty_stream_receipt_sha256": "d" * 64,
        }
        value = {**core, "receipt_sha256": C.object_sha256(core)}
        record = _record_from_manifest(
            path, value, schema=FEATURE_CACHE_SCHEMA,
            source=source, config_sha256=config_sha)
        self.assertEqual(record.status, "NO_NATIVE_CANDIDATES")
        stale = dict(value)
        stale_implementation = dict(stale["implementation_sha256"])
        stale_implementation["forecast_features"] = "e" * 64
        stale["implementation_sha256"] = stale_implementation
        stale_core = {key: item for key, item in stale.items()
                      if key != "receipt_sha256"}
        stale["receipt_sha256"] = C.object_sha256(stale_core)
        with self.assertRaisesRegex(
                ConfirmationRefusal, "identity/receipt differs"):
            _record_from_manifest(
                path, stale, schema=FEATURE_CACHE_SCHEMA,
                source=source, config_sha256=config_sha)

    def test_fit_only_selector_prunes_constants_and_aliases_and_reloads(self) -> None:
        dataset = _synthetic_dataset(20210104)
        x = np.asarray(dataset.features, np.float32)
        augmented = replace(
            dataset,
            feature_names=dataset.feature_names + (
                "structural_constant", "exact_duplicate"),
            features=np.column_stack((
                x, np.full(len(x), 7.0, np.float32), x[:, 0])),
        )
        augmented.validate()
        selector = FitOnlyFeatureSelector.fit(augmented)
        self.assertNotIn("structural_constant", selector.selected_feature_names)
        self.assertNotIn("exact_duplicate", selector.selected_feature_names)
        transformed = selector.transform(augmented)
        self.assertTrue(np.array_equal(
            transformed.cert_close_usd, augmented.cert_close_usd))
        self.assertEqual(transformed.source_receipts[-1], selector.receipt_sha256)
        with tempfile.TemporaryDirectory(
                dir="/workspace/artifacts/cache") as tmp:
            path = Path(tmp) / "selector.json"
            selector.save(path)
            loaded = FitOnlyFeatureSelector.load(path)
        self.assertEqual(selector, loaded)
        self.assertTrue(np.array_equal(
            transformed.features, loaded.transform(augmented).features))































    def test_registered_policy_grid_includes_explicit_waits(self) -> None:
        grid = registered_policy_grid(300)
        self.assertEqual(len(grid), 1_344)
        self.assertEqual({row.min_alert_age_sec for row in grid},
                         {0.0, 15.0, 30.0, 60.0, 120.0, 180.0, 240.0})

    def test_first_trigger_respects_minimum_confirmation_age(self) -> None:
        dataset = _synthetic_dataset(20210104)
        n = len(dataset.features)
        predictions = ConfirmationPredictions(
            opportunity_id=dataset.opportunity_id.copy(),
            expected_pnl_usd=np.full(n, 1_000.0),
            pnl_q20_usd=np.full(n, 500.0),
            goal_probability=np.full(n, .5),
            wall_probability=np.full(n, .01),
            mae_q90_usd=np.full(n, 100.0), model_hash="all-pass")
        policy = ConfirmationPolicy(0.0, -600.0, .05, .35,
                                    min_alert_age_sec=1.0)
        chosen = first_trigger_indices(dataset, predictions, policy)
        self.assertEqual(len(chosen), 30)
        self.assertTrue(np.all(dataset.min_alert_age_sec[chosen] == 1.0))

    def test_teacher_refusal_is_not_a_learnable_candidate(self) -> None:
        candidates_path = ROOT / "g1/candidates/SI/20210712.tsv"
        teachers_path = ROOT / "g1/teacher/SI/20210712.tsv"
        if not candidates_path.is_file() or not teachers_path.is_file():
            self.skipTest("authoritative all-refused session is unavailable")
        candidates = read_versioned_tsv(candidates_path)
        teachers = read_versioned_tsv(teachers_path)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(learnable_confirmation_count(candidates, teachers), 0)

    def test_mixed_teacher_session_keeps_only_ready_candidates(self) -> None:
        candidates_path = ROOT / "g1/candidates/SI/20210726.tsv"
        teachers_path = ROOT / "g1/teacher/SI/20210726.tsv"
        if not candidates_path.is_file() or not teachers_path.is_file():
            self.skipTest("authoritative mixed teacher session is unavailable")
        candidates = read_versioned_tsv(candidates_path)
        teachers = read_versioned_tsv(teachers_path)
        self.assertEqual(len(candidates), 3)
        self.assertEqual(learnable_confirmation_count(candidates, teachers), 1)

    def test_sharded_ceiling_matches_independent_day_sum(self) -> None:
        first = _synthetic_opportunity_set(20210104)
        second = _synthetic_opportunity_set(20210105)
        sessions = (default_expected_sessions(_synthetic_dataset(
            20210104, mode="REPLAY"))
                    + default_expected_sessions(_synthetic_dataset(
                        20210105, mode="REPLAY")))
        combined = exact_delayed_candidate_ceiling_shards(
            (first, second), expected_sessions=sessions)
        first_only = exact_delayed_candidate_ceiling(
            first, expected_sessions=sessions[:1])
        second_only = exact_delayed_candidate_ceiling(
            second, expected_sessions=sessions[1:])
        self.assertEqual(combined.exact_objective_cents,
                         first_only.exact_objective_cents
                         + second_only.exact_objective_cents)
        self.assertEqual(combined.evaluation.trades, 24)

    def test_registered_feature_sets_are_nested(self) -> None:
        names = (
            "asset_SI", "asset_HG", "asset_NKD", "side", "phase_index",
            "candidate_count", "formation_atr_mean_usd",
            "spread_prior_present_fraction", "fast_open_present",
            "rung_0_present", "min_alert_age_sec", "max_alert_age_sec",
            "phase_remaining_sec", "current_spread_usd", "current_cost_usd",
            "current_bid_size", "current_ask_size", "current_size_imbalance",
            "current_count_imbalance", "aligned_from_formation_mean_usd",
            "ctx_VIX_last_value_0", "disc_ib_phase_present",
            "disc_eclock_n64_support_count",
            "disc_tclock_n32_support_count",
            "disc_vclock_v64_support_fraction",
            "disc_tape_h30_event_mean_per_sec",
            "disc_test_count", "disc_quote_h30_present",
            "disc_behavior_control_evidence_balance",
            "w1_event_count", "w300_trade_volume", "w600_event_count",
            "w1800_event_count")
        masks = registered_feature_sets(names)
        self.assertEqual(tuple(masks), (
            "FORMATION_ONLY", "PLUS_CLOCK", "PLUS_CURRENT_BOOK",
            "PLUS_RECLAIM", "PLUS_LEVEL_STATE", "MAX_W300", "MAX_PLUS_EPISODE",
            "MAX_PLUS_ORDERED", "FULL"))
        counts = [int(mask.sum()) for mask in masks.values()]
        self.assertEqual(counts, sorted(counts))
        self.assertFalse(masks["MAX_W300"][names.index("w600_event_count")])
        self.assertTrue(masks["FULL"][names.index("w600_event_count")])
        for name in (
                "ctx_VIX_last_value_0", "disc_ib_phase_present",
                "disc_eclock_n64_support_count", "disc_tclock_n32_support_count",
                "disc_vclock_v64_support_fraction",
                "disc_tape_h30_event_mean_per_sec", "disc_test_count",
                "disc_quote_h30_present",
                "disc_behavior_control_evidence_balance"):
            self.assertTrue(masks["MAX_W300"][names.index(name)], name)

    def test_all_failed_policy_grid_preserves_scorecards(self) -> None:
        dataset = _synthetic_dataset(20210104)
        n = len(dataset.features)
        predictions = ConfirmationPredictions(
            opportunity_id=dataset.opportunity_id.copy(),
            expected_pnl_usd=np.zeros(n), pnl_q20_usd=np.zeros(n),
            goal_probability=np.zeros(n), wall_probability=np.ones(n),
            mae_q90_usd=np.full(n, 900.0), model_hash="synthetic-model")
        policy = ConfirmationPolicy(
            min_expected_pnl_usd=900.0, min_pnl_q20_usd=300.0,
            min_goal_probability=.30, max_wall_probability=.05)
        scored = score_confirmation_policies(
            dataset, predictions,
            expected_sessions=default_expected_sessions(dataset),
            policies=(policy,))
        self.assertEqual(scored.status, "NO_FEASIBLE_THRESHOLD")
        self.assertIsNone(scored.selected)
        self.assertEqual(len(scored.all_scorecards), 1)
        self.assertIn("empty book", scored.all_scorecards[0].reasons[0])

    def test_opportunity_universe_strict_reload_identity(self) -> None:
        universe = _synthetic_opportunity_set(20210104)
        with tempfile.TemporaryDirectory(
                dir="/workspace/artifacts/cache") as tmp:
            path = Path(tmp) / "opportunities.npz"
            universe.save(path)
            loaded = ConfirmationOpportunitySet.load(path)
        self.assertEqual(universe.representation_sha256,
                         loaded.representation_sha256)
        self.assertTrue(np.array_equal(universe.opportunity_id,
                                       loaded.opportunity_id))

    def test_sparse_grid_cannot_claim_exact_ceiling(self) -> None:
        dataset = _synthetic_dataset(20210104)
        with self.assertRaisesRegex(ConfirmationRefusal, "every-second REPLAY"):
            exact_delayed_candidate_ceiling(
                dataset, expected_sessions=default_expected_sessions(dataset))



















    def test_exact_ceiling_uses_one_timestamp_per_series_and_twelve_per_day(self) -> None:
        dataset = _synthetic_dataset(20210104, mode="REPLAY")
        ceiling = exact_delayed_candidate_ceiling(
            dataset, expected_sessions=default_expected_sessions(dataset))
        self.assertEqual(ceiling.evaluation.trades, 12)
        self.assertEqual(len(ceiling.selected_series_ids), 12)
        self.assertEqual(len(set(ceiling.selected_series_ids)), 12)
        self.assertEqual(
            ceiling.evaluation.total_pnl_usd,
            ceiling.exact_objective_cents / 100.0)

    def test_null_shuffle_keeps_recipients_and_changes_targets(self) -> None:
        dataset = _synthetic_dataset(20210104)
        shuffled = shuffle_confirmation_targets(dataset, 19)
        self.assertTrue(np.array_equal(dataset.features, shuffled.features))
        self.assertTrue(np.array_equal(dataset.series_id, shuffled.series_id))
        self.assertFalse(np.array_equal(dataset.cert_close_usd,
                                        shuffled.cert_close_usd))
        self.assertNotEqual(dataset.representation_sha256,
                            shuffled.representation_sha256)

    def test_registered_ablations_remove_real_feature_families(self) -> None:
        dataset = _synthetic_dataset(20210104)
        masks = registered_feature_ablations(dataset.feature_names)
        self.assertEqual(set(masks), {
            "formation_reclaim", "aggressive_flow", "absorption",
            "defense_retreat", "path_shape"})
        for mask in masks.values():
            ablated = dataset.select_features(mask)
            self.assertLess(len(ablated.feature_names), len(dataset.feature_names))

    def test_catboost_heads_calibration_and_strict_reload(self) -> None:
        fit = _synthetic_dataset(20210104)
        platt = _synthetic_dataset(20210105)
        model = fit_confirmation_model(
            fit, platt,
            config=ConfirmationModelConfig(
                iterations=20, depth=3, learning_rate=.1, thread_count=2))
        before = model.predict(platt)
        with tempfile.TemporaryDirectory(dir="/workspace/artifacts/cache") as tmp:
            path = Path(tmp) / "model"
            model.save(path)
            loaded = ConfirmationModel.load(path)
            after = loaded.predict(platt)
            for name in ("expected_pnl_usd", "pnl_q20_usd",
                         "goal_probability", "wall_probability",
                         "mae_q90_usd"):
                self.assertTrue(np.array_equal(
                    getattr(before, name), getattr(after, name)), name)

    def test_empty_candidate_tsv_is_typed_only_when_requested(self) -> None:
        path = ROOT / "g1/candidates/SI/20210802.tsv"
        if not path.is_file():
            self.skipTest("authoritative empty-session fixture is unavailable")
        with self.assertRaisesRegex(ConfirmationRefusal, "empty"):
            read_versioned_tsv(path)
        self.assertEqual(read_versioned_tsv(path, allow_empty=True), ())


@unittest.skipUnless(REAL_AVAILABLE, "authoritative SI regression fixture unavailable")
class ConfirmationRealDataTests(unittest.TestCase):
    def test_si_20210804_delayed_reanchoring_regression(self) -> None:
        candidates = read_versioned_tsv(ROOT / "g1/candidates/SI/20210804.tsv")
        teachers = read_versioned_tsv(ROOT / "g1/teacher/SI/20210804.tsv")
        bindings = build_candidate_truth_bindings(candidates, teachers)
        target = next(row for row in bindings
                      if row.candidate_id.startswith("QRE2V2-b243"))
        with EventPack(ROOT / "events/SI/20210804.qre2", verify_hash=True) as pack:
            truth = build_event_truth_columns(pack.rows, "SI", bindings)
            index = _OutcomeIndex(
                pack.rows, truth.candidate_columns(target), "SI")
            observed = []
            snapshots = []
            entry_mid2 = []
            frozen_cost = []
            for delay in (0, 15, 300):
                timestamp = target.decision_ts_ns + delay * 1_000_000_000
                current = index.current(timestamp)
                self.assertIsNotNone(current)
                _position, _raw, bid, ask, mid2 = current
                cost = (ask - bid) * 1e-9 * 5_000 + 5.0
                outcome = index.outcome(
                    opportunity_id=str(delay), snapshot_ts_ns=timestamp,
                    side=-1, phase_close_ts_ns=target.phase_close_ts_ns,
                    entry_mid2=mid2, frozen_cost_usd=cost,
                    generation=index.generation_at_snapshot(timestamp))
                self.assertIsNotNone(outcome)
                observed.append(outcome)
                snapshots.append(timestamp)
                entry_mid2.append(mid2)
                frozen_cost.append(cost)
            batched = index.outcomes_many(
                snapshot_ts_ns=np.asarray(snapshots, np.int64), side=-1,
                phase_close_ts_ns=target.phase_close_ts_ns,
                entry_mid2=np.asarray(entry_mid2, np.int64),
                frozen_cost_usd=np.asarray(frozen_cost, np.float64))
            self.assertTrue(np.array_equal(
                batched["input_index"], np.arange(len(observed))))
            for row, scalar in enumerate(observed):
                self.assertAlmostEqual(
                    batched["cert_close_usd"][row], scalar.cert_close_usd)
                self.assertAlmostEqual(batched["mfe_usd"][row], scalar.mfe_usd)
                self.assertAlmostEqual(batched["mae_usd"][row], scalar.mae_usd)
                self.assertEqual(bool(batched["wall_hit"][row]),
                                 scalar.wall_hit)
                self.assertEqual(int(batched["exit_ts_ns"][row]),
                                 scalar.exit_ts_ns)
        self.assertAlmostEqual(observed[0].cert_close_usd, 2_482.5)
        self.assertAlmostEqual(observed[0].mfe_usd, 2_707.5)
        self.assertAlmostEqual(observed[0].mae_usd, 880.0)
        self.assertFalse(observed[0].wall_hit)
        self.assertAlmostEqual(observed[1].cert_close_usd, -905.0)
        self.assertTrue(observed[1].wall_hit)
        self.assertAlmostEqual(observed[2].cert_close_usd, 2_620.0)
        self.assertAlmostEqual(observed[2].mfe_usd, 2_845.0)
        self.assertAlmostEqual(observed[2].mae_usd, 742.5)
        self.assertFalse(observed[2].wall_hit)


if __name__ == "__main__":
    unittest.main()
