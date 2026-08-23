"""Cheap correctness and method-understanding checks for confirmation V1."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

import numpy as np

from engine.entry_v2 import common as C
from engine.entry_v2 import confirmation
from engine.entry_v2.confirmation import (
    ConfirmationConfig, ConfirmationDataset, ConfirmationOpportunitySet,
    ConfirmationRefusal, combine_confirmation_datasets,
    confirmation_implementation_hashes,
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
from engine.entry_v2.confirmation_action_probe import (
    ActionProbeConfig, _balanced_binary_weights, action_probe_diagnostic,
    run_action_probe_matrix,
)
from engine.entry_v2.confirmation_policy import (
    ConfirmationPolicy, default_expected_sessions,
    exact_delayed_candidate_ceiling,
    exact_delayed_candidate_ceiling_shards,
    first_trigger_indices,
)
from engine.entry_v2.confirmation_stopping import (
    ENTER, PASS, WAIT, OracleActionLedger, derive_oracle_action_ledger,
    oracle_action_census, rebind_oracle_action_ledger,
    registered_oracle_label_family, registered_oracle_training_strata,
)
from engine.entry_v2.confirmation_value_probe import (
    timing_rank_diagnostic, value_stack_diagnostic,
)
from engine.entry_v2.confirmation_snell_probe import (
    entry_price_offset_usd, factorized_entry_target,
    fitted_policy_diagnostic, fitted_policy_recursion,
)
from engine.entry_v2.confirmation_candidate_rank import (
    CURRENT_TARGET_SCOPE, CandidateRankConfig, candidate_formation_targets,
    candidate_rank_diagnostic, candidate_watch_rows,
    run_candidate_age_rank_probe,
)
from engine.entry_v2.confirmation_capacity_probe import (
    CapacityProbeConfig, capacity_topk_labels, run_capacity_probe,
    survival_expected_value,
)
from engine.entry_v2.confirmation_capacity_corpus import (
    CapacityCorpusConfig, _take_ledger, prepare_capacity_corpora,
)
from engine.entry_v2.confirmation_conditional_corpus import (
    ConditionalCorpusConfig, prepare_conditional_role,
)
from engine.entry_v2.confirmation_capacity_stability import (
    CapacityStabilityConfig, capacity_dollar_margin_weights,
    capacity_soft_relevance, forward_day_folds,
    run_capacity_stability_probe,
)
from engine.entry_v2.confirmation_factorized_policy import (
    FactorizedPolicyConfig, _gated_predictions, fit_factorized_models,
    run_factorized_policy, select_top_capacity_series,
)
from engine.entry_v2.confirmation_acceptance_stability import (
    acceptance_potential_diagnostic,
)
from engine.entry_v2.confirmation_acceptance_mechanism import (
    acceptance_feature_indices, asset_day_groups, cross_section_matrix,
    shuffle_within_asset_day,
)
from engine.entry_v2.confirmation_dynamic_hurdle_policy import (
    DynamicHurdleConfig, DynamicHurdleModels, fit_dynamic_hurdle_models,
    run_dynamic_hurdle_policy,
)
from engine.entry_v2.confirmation_portfolio_gate_probe import (
    PortfolioGateConfig, fit_portfolio_gate_models,
    portfolio_schedule_target, run_portfolio_gate_probe,
)
from engine.entry_v2.confirmation_direct_utility_policy import (
    DirectUtilityConfig, DirectUtilityModels, fit_direct_utility_models,
    run_direct_utility_policy,
)
from engine.entry_v2.confirmation_fixed_horizon import (
    FixedHorizonConfig, _oracle_policy_family, eligible_feature_indices,
    fixed_horizon_target, shuffle_within_series, watch_relative_matrix,
)
from engine.entry_v2.confirmation_lawful_value import (
    candidate_lawful_value_target, shuffle_observed_within_asset_day,
)
from engine.entry_v2.confirmation_lawful_value_model import (
    LawfulValueRankConfig, lawful_value_rank_diagnostic,
)
from engine.entry_v2.confirmation_lawful_policy import (
    causal_first_crossings,
)
from engine.entry_v2.confirmation_path_state import (
    INCREMENT_SIGNALS, STATE_SIGNALS, build_path_state_landmark,
)
from engine.entry_v2.confirmation_path_state_model import (
    PathStateRankConfig, _objective_relevance,
)
from engine.entry_v2.confirmation_path_state_ceiling import (
    run_path_state_acceptance_ceiling,
)
from engine.entry_v2.confirmation_candidate_value import (
    candidate_value_transform, survival_expected_score,
)
from engine.entry_v2.confirmation_ordered import (
    ORDERED_FEATURE_NAMES, _ordered_map_from_channels,
)
from engine.entry_v2.confirmation_experiment import (
    FEATURE_CACHE_SCHEMA, _record_from_manifest,
)
from engine.entry_v2.confirmation_dossier import select_blind_raw_dossiers
from engine.entry_v2.diagnostic_inputs import (
    UNITS_PER_USD, build_candidate_truth_bindings, build_event_truth_columns,
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

    def test_corpus_grid_covers_every_age_the_live_probes_read(self) -> None:
        """Derived from the probes' own constants, never hand-copied."""

        import sys
        sys.path.insert(0, "/workspace/tools")
        from probe_armed_entry import AGE_GRID
        from probe_path_dedup_live import DELTA_SEC, FORM_DELTA
        from probe_trained_accrual import DELTAS
        needed = {int(d) for d in DELTAS} | {int(a) for a in AGE_GRID}
        needed |= {int(FORM_DELTA), int(DELTA_SEC)}
        missing = needed - set(confirmation.CORPUS_AGE_GRID_SECONDS)
        self.assertEqual(missing, set(),
                         f"the corpus grid drops ages a live probe reads: {sorted(missing)}")

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
        from unittest import mock
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

    def test_oracle_action_ledger_backward_values_and_actions(self) -> None:
        dataset = _synthetic_dataset(20210104, series_count=3)
        ledger = derive_oracle_action_ledger(dataset)
        first = np.flatnonzero(dataset.series_id == dataset.series_id[0])
        second = np.flatnonzero(dataset.series_id == dataset.series_id[3])
        third = np.flatnonzero(dataset.series_id == dataset.series_id[6])
        self.assertEqual(ledger.scope, "CANDIDATE_LOCAL_SPARSE_TRAINING")
        self.assertEqual(ledger.q_enter_usd[first].tolist(),
                         [-905.0, -100.0, 1_200.0])
        self.assertEqual(ledger.q_wait_usd[first].tolist(),
                         [1_200.0, 1_200.0, 0.0])
        self.assertEqual(ledger.optimal_action[first].tolist(),
                         [WAIT, WAIT, ENTER])
        self.assertEqual(ledger.optimal_action[second].tolist(),
                         [ENTER, PASS, PASS])
        self.assertEqual(ledger.optimal_action[third].tolist(),
                         [WAIT, WAIT, ENTER])
        self.assertEqual(ledger.action_run_observations[first].tolist(),
                         [2, 1, 1])
        self.assertEqual(ledger.action_run_horizon_sec[first].tolist(),
                         [1.0, 0.0, 0.0])

    def test_oracle_action_ties_prefer_wait_and_nonpositive_paths_pass(self) -> None:
        dataset = _synthetic_dataset(20210104, series_count=2)
        pnl = np.asarray([500.0, 500.0, 400.0,
                          0.0, -10.0, -20.0], np.float64)
        dataset = replace(
            dataset, cert_close_usd=pnl, mfe_usd=np.maximum(pnl, 0.0),
            mae_usd=np.maximum(-pnl, 0.0), wall_hit=pnl <= -900.0)
        dataset.validate()
        ledger = derive_oracle_action_ledger(dataset)
        self.assertEqual(ledger.optimal_action[:3].tolist(),
                         [WAIT, ENTER, ENTER])
        self.assertEqual(ledger.optimal_action[3:].tolist(),
                         [PASS, PASS, PASS])
        self.assertEqual(ledger.future_best_delay_sec[0], 1.0)
        self.assertEqual(ledger.future_best_snapshot_ts_ns[3], -1)

    def test_oracle_action_ledger_strict_reload_identity(self) -> None:
        ledger = derive_oracle_action_ledger(_synthetic_dataset(20210104))
        with tempfile.TemporaryDirectory(
                dir="/workspace/artifacts/cache") as tmp:
            path = Path(tmp) / "action_ledger.npz"
            ledger.save(path)
            loaded = OracleActionLedger.load(path)
        self.assertEqual(ledger.representation_sha256,
                         loaded.representation_sha256)
        self.assertTrue(np.array_equal(ledger.optimal_action,
                                       loaded.optimal_action))

    def test_oracle_action_census_exposes_goal_action_disagreement(self) -> None:
        dataset = _synthetic_dataset(20210104, series_count=3)
        ledger = derive_oracle_action_ledger(dataset)
        census = oracle_action_census(dataset, ledger)
        overall = census["overall"]
        self.assertEqual(overall["rows"], 9)
        self.assertEqual(overall["action_row_count"], {
            "PASS": 2, "WAIT": 4, "ENTER": 3})
        self.assertEqual(overall["goal_row_action_count"], {
            "PASS": 0, "WAIT": 2, "ENTER": 2})

    def test_registered_oracle_label_family_is_not_one_blunt_class(self) -> None:
        labels = registered_oracle_label_family(
            derive_oracle_action_ledger(_synthetic_dataset(20210104)))
        self.assertEqual(tuple(labels), (
            "EXACT_ENTER", "ENTER_POSITIVE_R50", "ENTER_P300_R50",
            "ENTER_P600_R100", "ENTER_P600_R200", "WAIT_P600"))
        self.assertGreater(len({value.tobytes() for value in labels.values()}), 3)

    def test_oracle_training_strata_are_exclusive_and_exhaustive(self) -> None:
        ledger = derive_oracle_action_ledger(_synthetic_dataset(20210104))
        strata = registered_oracle_training_strata(ledger)
        membership = np.sum(np.column_stack(tuple(strata.values())), axis=1)
        self.assertTrue(np.all(membership == 1))
        self.assertEqual(tuple(strata), (
            "ENTER_POSITIVE_R50", "POSITIVE_TOO_EARLY_R50",
            "NONPOSITIVE_NOW_FUTURE_POSITIVE", "NO_POSITIVE_REMAINING"))

    def test_oracle_ledger_rebind_requires_identical_augmented_rows(self) -> None:
        dataset = _synthetic_dataset(20210104)
        ledger = derive_oracle_action_ledger(dataset)
        augmented = replace(
            dataset,
            feature_names=dataset.feature_names + ("ordered_dummy",),
            features=np.column_stack((dataset.features, np.zeros(len(dataset.features)))),
            source_receipts=dataset.source_receipts + (C.object_sha256({"aug": 1}),))
        augmented.validate()
        rebound = rebind_oracle_action_ledger(ledger, augmented)
        self.assertEqual(rebound.source_representation_sha256,
                         augmented.representation_sha256)
        self.assertTrue(np.array_equal(rebound.q_enter_usd, ledger.q_enter_usd))

    def test_action_probe_separates_global_from_within_series_signal(self) -> None:
        dataset = _synthetic_dataset(20210104)
        ledger = derive_oracle_action_ledger(dataset)
        target = registered_oracle_label_family(ledger)["ENTER_P600_R100"]
        diagnostic = action_probe_diagnostic(
            dataset, ledger, target, target.astype(np.float64))
        self.assertEqual(diagnostic["global_series_balanced_auc"], 1.0)
        self.assertEqual(diagnostic["within_series_auc_mean"], 1.0)
        self.assertGreater(diagnostic["within_series_auc_groups"], 0)

    def test_action_probe_weights_balance_series_then_classes(self) -> None:
        dataset = _synthetic_dataset(20210104, series_count=3)
        target = registered_oracle_label_family(
            derive_oracle_action_ledger(dataset))["ENTER_P600_R100"]
        weights = _balanced_binary_weights(dataset, target)
        self.assertAlmostEqual(float(weights[target == 0].sum()), len(weights) / 2)
        self.assertAlmostEqual(float(weights[target == 1].sum()), len(weights) / 2)
        series = np.asarray(dataset.series_id, str)
        per_series = np.asarray([
            weights[series == value].sum() for value in sorted(set(series))])
        self.assertTrue(np.all(np.isfinite(per_series)))

    def test_action_probe_full_result_binds_real_ledger_identity(self) -> None:
        datasets = {}
        for role, day in (
                ("FIT", 20210104), ("PLATT", 20210105),
                ("THRESHOLD", 20210106)):
            base = _synthetic_dataset(day)
            receipt = C.object_sha256({"action_probe_preflight": day})
            dataset = replace(
                base,
                feature_names=("asset_SI",) + base.feature_names,
                features=np.column_stack((
                    np.ones(len(base.features), np.float32), base.features)),
                source_receipts=base.source_receipts + (receipt,))
            dataset.validate()
            datasets[role] = dataset
        ledgers = {role: derive_oracle_action_ledger(dataset)
                   for role, dataset in datasets.items()}
        result = run_action_probe_matrix(
            datasets, ledgers, feature_sets=("FULL",),
            labels=("ENTER_P600_R100",),
            config=ActionProbeConfig(
                iterations=12, depth=3, thread_count=1,
                early_stopping_rounds=5))
        self.assertEqual(result["schema"], "QRE2CONFACTIONPROBE2")
        for role in datasets:
            self.assertEqual(
                result["inputs"][role]["ledger_sha256"],
                ledgers[role].representation_sha256)
        controls = [row for row in result["results"] if "control" in row]
        self.assertEqual(len(controls), 1)
        self.assertEqual(
            controls[0]["control"],
            "FIT_RECIPIENT_FIXED_SERIES_TARGET_SHUFFLE")

    def test_action_probe_hindsight_regret_does_not_forgive_late_choice(self) -> None:
        dataset = _synthetic_dataset(20210104, series_count=1)
        pnl = np.asarray([100.0, -905.0, -905.0], np.float64)
        dataset = replace(
            dataset, cert_close_usd=pnl, mfe_usd=np.maximum(pnl, 0.0),
            mae_usd=np.maximum(-pnl, 0.0), wall_hit=pnl <= -900.0)
        dataset.validate()
        ledger = derive_oracle_action_ledger(dataset)
        target = np.asarray([1, 0, 0], np.int8)
        # Highest score is deliberately the final timestamp, after the
        # series' best entry.  Causal best-remaining regret there is $905,
        # while whole-series hindsight regret is correctly $1,005.
        diagnostic = action_probe_diagnostic(
            dataset, ledger, target, np.asarray([0.0, 0.1, 1.0]))
        self.assertEqual(
            diagnostic["hindsight_argmax_median_enter_regret_usd"], 1_005.0)

    def test_value_probe_perfect_timing_has_zero_whole_series_regret(self) -> None:
        dataset = _synthetic_dataset(20210104)
        ledger = derive_oracle_action_ledger(dataset)
        diagnostic = timing_rank_diagnostic(
            dataset, ledger, ledger.q_enter_usd)
        self.assertEqual(diagnostic["hindsight_argmax_median_regret_usd"], 0.0)
        self.assertEqual(diagnostic["hindsight_argmax_positive_value_capture"], 1.0)
        self.assertEqual(diagnostic["within_series_pairwise_accuracy"], 1.0)

    def test_value_stack_reports_dollar_alignment_without_economics(self) -> None:
        dataset = _synthetic_dataset(20210104)
        ledger = derive_oracle_action_ledger(dataset)
        diagnostic = value_stack_diagnostic(
            dataset, ledger, opportunity_score=ledger.q_optimal_usd,
            advantage_score=ledger.enter_advantage_usd,
            timing_score=ledger.q_enter_usd)
        self.assertEqual(diagnostic["opportunity_q_optimal_correlation"], 1.0)
        self.assertEqual(diagnostic["advantage_correlation"], 1.0)
        self.assertFalse(diagnostic["economics_executed"])

    def test_fitted_policy_recursion_recovers_perfect_stopping_values(self) -> None:
        dataset = _synthetic_dataset(20210104)
        ledger = derive_oracle_action_ledger(dataset)
        recursion = fitted_policy_recursion(
            dataset, ledger, immediate_score=ledger.q_enter_usd,
            continuation_score=ledger.q_wait_usd)
        self.assertTrue(np.array_equal(
            recursion["action"], ledger.optimal_action))
        starts = recursion["series_start_indices"]
        self.assertTrue(np.array_equal(
            recursion["realized_value"][starts], ledger.q_optimal_usd[starts]))
        diagnostic = fitted_policy_diagnostic(
            dataset, ledger, recursion, iteration=0)
        self.assertEqual(diagnostic["candidate_local_net_value_capture"], 1.0)
        self.assertFalse(diagnostic["economics_executed"])

    def test_fitted_policy_pass_cannot_retroactively_take_later_winner(self) -> None:
        dataset = _synthetic_dataset(20210104, series_count=1)
        ledger = derive_oracle_action_ledger(dataset)
        recursion = fitted_policy_recursion(
            dataset, ledger,
            immediate_score=np.asarray([-10.0, -10.0, 1_000.0]),
            continuation_score=np.zeros(3, np.float64))
        self.assertEqual(recursion["action"].tolist(), [PASS, PASS, ENTER])
        self.assertEqual(recursion["selected_indices"].tolist(), [])
        self.assertEqual(recursion["realized_value"][0], 0.0)

    def test_factorized_target_removes_exact_entry_price_offset(self) -> None:
        dataset = _synthetic_dataset(20210104, series_count=1)
        increments = np.asarray([0, 20_000_000, 40_000_000], np.int64)
        bid = np.asarray(dataset.entry_bid_px, np.int64) + increments
        ask = np.asarray(dataset.entry_ask_px, np.int64) + increments
        # SI factor is $2.5e-6 per doubled-price unit, so the entry-price
        # displacement is exactly $0/$100/$200.  With $30 costs, these
        # q_enter labels all imply the same $500 terminal move from formation.
        pnl = np.asarray([470.0, 370.0, 270.0], np.float64)
        dataset = replace(
            dataset, entry_bid_px=bid, entry_ask_px=ask,
            entry_mid2=bid + ask, cert_close_usd=pnl,
            mfe_usd=pnl.copy(), mae_usd=np.zeros(3, np.float64),
            wall_hit=np.zeros(3, bool))
        dataset.validate()
        ledger = derive_oracle_action_ledger(dataset)
        self.assertTrue(np.allclose(
            entry_price_offset_usd(dataset), [30.0, 130.0, 230.0]))
        self.assertTrue(np.allclose(
            factorized_entry_target(dataset, ledger), 500.0))

    def test_candidate_rank_perfect_score_captures_top_capacity(self) -> None:
        dataset = _synthetic_dataset(20210104, series_count=30)
        ledger = derive_oracle_action_ledger(dataset)
        indices, checkpoints = candidate_watch_rows(
            dataset, watch_ages_seconds=(0, 1, 2))
        self.assertEqual(len(indices), 90)
        diagnostic = candidate_rank_diagnostic(
            dataset, ledger, indices=indices, checkpoints=checkpoints,
            score=ledger.q_optimal_usd[indices], capacity=12)
        self.assertEqual(
            diagnostic["overall"]["top_capacity_opportunity_capture"], 1.0)
        self.assertEqual(set(diagnostic["by_watch_age"]), {"0", "1", "2"})

    def test_candidate_age_rank_full_result_is_pruned_and_receipt_bound(self) -> None:
        datasets = {}
        for role, day in (
                ("FIT", 20210104), ("PLATT", 20210105),
                ("THRESHOLD", 20210106)):
            base = _synthetic_dataset(day)
            receipt = C.object_sha256({"candidate_rank_preflight": day})
            dataset = replace(
                base,
                feature_names=("asset_SI",) + base.feature_names,
                features=np.column_stack((
                    np.ones(len(base.features), np.float32), base.features)),
                source_receipts=base.source_receipts + (receipt,))
            dataset.validate()
            datasets[role] = dataset
        ledgers = {role: derive_oracle_action_ledger(dataset)
                   for role, dataset in datasets.items()}
        result = run_candidate_age_rank_probe(
            datasets, ledgers,
            config=CandidateRankConfig(
                feature_set="MAX_W300", watch_ages_seconds=(0,),
                target_scope=CURRENT_TARGET_SCOPE,
                capacity=4, iterations=20, depth=3, thread_count=1,
                early_stopping_rounds=5))
        self.assertEqual(result["schema"], "QRE2CONFAGECANDRANK6")
        self.assertEqual(result["target_scope"], CURRENT_TARGET_SCOPE)
        self.assertFalse(result["fit_only_selector"]["labels_used"])
        self.assertLess(
            result["fit_only_selector"]["selected_feature_count"],
            result["fit_only_selector"]["input_feature_count"])
        for role in datasets:
            self.assertEqual(
                result["inputs"][role]["ledger_sha256"],
                ledgers[role].representation_sha256)

    def test_candidate_rank_exclusion_is_receipt_bound(self) -> None:
        baseline = CandidateRankConfig()
        destruction = CandidateRankConfig(
            excluded_feature_names=("phase_remaining_sec",))
        self.assertNotEqual(
            baseline.receipt_sha256, destruction.receipt_sha256)
        with self.assertRaisesRegex(ConfirmationRefusal, "invalid"):
            CandidateRankConfig(excluded_feature_names=("x", "x"))

    def test_capacity_labels_and_survival_score_obey_tail_laws(self) -> None:
        dataset = _synthetic_dataset(20210104, series_count=30)
        ledger = derive_oracle_action_ledger(dataset)
        indices, checkpoints = candidate_watch_rows(
            dataset, watch_ages_seconds=(0, 2),
            require_complete_grid=True)
        indices = indices[checkpoints == 2]
        target = np.asarray(ledger.q_optimal_usd, np.float64)[indices]
        label = capacity_topk_labels(
            dataset, indices, target, capacity=4)
        self.assertEqual(int(label.sum()), 4)
        self.assertTrue(np.all(target[label == 1] > 0.0))
        score = survival_expected_value(np.asarray([
            [.9, .8, .6, .4], [.9, .6, .2, .1],
        ]), (0.0, 250.0, 600.0, 900.0), 1_500.0)
        self.assertGreater(score[0], score[1])

    def test_capacity_probe_full_result_is_bound_before_real_fit(self) -> None:
        datasets = {}
        for role, day in (
                ("FIT", 20210104), ("PLATT", 20210105),
                ("THRESHOLD", 20210106)):
            base = _synthetic_dataset(day)
            receipt = C.object_sha256({"capacity_probe_preflight": day})
            dataset = replace(
                base,
                feature_names=("asset_SI",) + base.feature_names,
                features=np.column_stack((
                    np.ones(len(base.features), np.float32), base.features)),
                source_receipts=base.source_receipts + (receipt,))
            dataset.validate()
            datasets[role] = dataset
        ledgers = {role: derive_oracle_action_ledger(dataset)
                   for role, dataset in datasets.items()}
        result = run_capacity_probe(
            datasets, ledgers,
            config=CapacityProbeConfig(
                watch_age_sec=2, capacity=4,
                survival_thresholds_usd=(0.0, 250.0, 600.0, 900.0),
                survival_cap_usd=1_500.0,
                iterations=20, depth=3, thread_count=1,
                early_stopping_rounds=5))
        self.assertEqual(result["schema"], "QRE2CONFCAPACITYPROBE1")
        self.assertEqual(
            {row["family"] for row in result["family_results"]},
            {"BALANCED_TOPK", "SURVIVAL_EXPECTED_VALUE", "HARD_PAIRLOGIT"})
        self.assertIn(result["selected_family"], {
            "BALANCED_TOPK", "SURVIVAL_EXPECTED_VALUE", "HARD_PAIRLOGIT"})
        self.assertEqual(result["h2_open_count"], 0)
        self.assertFalse(result["economics_executed"])
        for role in datasets:
            self.assertEqual(
                result["inputs"][role]["ledger_sha256"],
                ledgers[role].representation_sha256)

    def test_capacity_corpus_preserves_fixed_watch_oracle_and_reload(self) -> None:
        datasets = {}
        for role, day in (
                ("FIT", 20210104), ("PLATT", 20210105),
                ("THRESHOLD", 20210106)):
            base = _synthetic_dataset(day)
            receipt = C.object_sha256({"capacity_corpus_preflight": day})
            dataset = replace(
                base,
                feature_names=("asset_SI",) + base.feature_names,
                features=np.column_stack((
                    np.ones(len(base.features), np.float32), base.features)),
                source_receipts=base.source_receipts + (receipt,))
            dataset.validate()
            datasets[role] = dataset
        ledgers = {role: derive_oracle_action_ledger(dataset)
                   for role, dataset in datasets.items()}
        reduced, reduced_ledgers, manifest = prepare_capacity_corpora(
            datasets, ledgers,
            config=CapacityCorpusConfig(watch_age_sec=2, capacity=4))
        self.assertEqual(manifest["schema"], "QRE2CONFCAPACITYCORPUS1")
        self.assertFalse(manifest["labels_used_for_feature_selection"])
        for role in datasets:
            self.assertEqual(len(reduced[role].features), 30)
            self.assertEqual(
                len(set(np.asarray(reduced[role].series_id, str))), 30)
            self.assertTrue(np.array_equal(
                reduced[role].opportunity_id,
                reduced_ledgers[role].opportunity_id))
            self.assertEqual(
                reduced_ledgers[role].source_representation_sha256,
                reduced[role].representation_sha256)
        with tempfile.TemporaryDirectory(
                dir="/workspace/artifacts/cache") as tmp:
            dataset_path = Path(tmp) / "dataset.npz"
            ledger_path = Path(tmp) / "ledger.npz"
            reduced["FIT"].save(dataset_path)
            reduced_ledgers["FIT"].save(ledger_path)
            loaded_dataset = ConfirmationDataset.load(dataset_path)
            loaded_ledger = OracleActionLedger.load(ledger_path)
        self.assertEqual(
            loaded_dataset.representation_sha256,
            reduced["FIT"].representation_sha256)
        self.assertEqual(
            loaded_ledger.representation_sha256,
            reduced_ledgers["FIT"].representation_sha256)

    def test_capacity_forward_folds_are_expanding_and_disjoint(self) -> None:
        days = np.repeat(np.arange(1, 31, dtype=np.int64), 3)
        folds = forward_day_folds(
            days, minimum_train_days=12, validation_days=6,
            fold_count=3)
        self.assertEqual(len(folds), 3)
        self.assertEqual([len(fold["train_days"]) for fold in folds],
                         [12, 18, 24])
        for fold in folds:
            self.assertLess(
                max(fold["train_days"]), min(fold["validation_days"]))
            self.assertFalse(
                set(fold["train_indices"])
                & set(fold["validation_indices"]))

    def test_capacity_soft_and_margin_targets_preserve_dollar_geometry(self) -> None:
        dataset = _synthetic_dataset(20210104, series_count=30)
        ledger = derive_oracle_action_ledger(dataset)
        indices, checkpoints = candidate_watch_rows(
            dataset, watch_ages_seconds=(0, 2),
            require_complete_grid=True)
        indices = indices[checkpoints == 2]
        target = np.asarray(ledger.q_optimal_usd, np.float64)[indices]
        soft = capacity_soft_relevance(
            dataset, indices, target, capacity=4)
        labels, weights = capacity_dollar_margin_weights(
            dataset, indices, target, capacity=4)
        self.assertTrue(np.all((soft >= 0.0) & (soft <= 1.0)))
        self.assertTrue(np.any((soft > 0.0) & (soft < 1.0)))
        self.assertEqual(int(labels.sum()), 4)
        self.assertTrue(np.all(weights > 0.0))
        self.assertAlmostEqual(float(weights.sum()), len(weights))

    def test_capacity_stability_selects_only_on_fit_forward_oof(self) -> None:
        def concatenate(days: tuple[int, ...]) -> ConfirmationDataset:
            parts_list = []
            for day in days:
                part = _synthetic_dataset(day)
                # Fold 2 validation intentionally has no >=$900 outcome.
                # Fixed-iteration folds only score this block; they do not
                # consume its binary tail as an eval/early-stop label.
                if day == 20210107:
                    pnl = np.asarray(part.cert_close_usd, np.float64) * .5
                    part = replace(
                        part, cert_close_usd=pnl,
                        mfe_usd=np.maximum(pnl, 0.0),
                        mae_usd=np.maximum(-pnl, 0.0),
                        wall_hit=pnl <= -900.0)
                    part.validate()
                parts_list.append(part)
            parts = tuple(parts_list)
            first = parts[0]
            fields = (
                "features", "opportunity_id", "series_id", "candidate_id",
                "asset", "day", "side", "phase", "snapshot_ts_ns",
                "phase_close_ts_ns", "event_cutoff", "entry_event_ordinal",
                "entry_availability_ts_ns", "entry_bid_px", "entry_ask_px",
                "entry_mid2", "entry_spread_usd", "frozen_cost_usd",
                "candidate_count", "min_alert_age_sec", "max_alert_age_sec",
                "cert_close_usd", "mfe_usd", "mae_usd", "wall_hit",
                "exit_ts_ns", "feature_receipt_sha256",
            )
            result = replace(
                first,
                **{name: np.concatenate(tuple(
                    np.asarray(getattr(part, name)) for part in parts))
                   for name in fields},
                source_receipts=tuple(
                    receipt for part in parts for receipt in part.source_receipts))
            result = replace(
                result,
                feature_names=("asset_SI",) + result.feature_names,
                features=np.column_stack((
                    np.ones(len(result.features), np.float32),
                    result.features)))
            result.validate()
            return result

        datasets = {
            "FIT": concatenate(tuple(range(20210104, 20210110))),
            "PLATT": concatenate((20210110,)),
            "THRESHOLD": concatenate((20210111,)),
        }
        ledgers = {role: derive_oracle_action_ledger(dataset)
                   for role, dataset in datasets.items()}
        reduced, reduced_ledgers, manifest = prepare_capacity_corpora(
            datasets, ledgers,
            config=CapacityCorpusConfig(watch_age_sec=2, capacity=4))
        result = run_capacity_stability_probe(
            reduced, reduced_ledgers,
            capacity_corpus_receipt_sha256=manifest["receipt_sha256"],
            config=CapacityStabilityConfig(
                watch_age_sec=2, minimum_train_days=2,
                validation_days=1, fold_count=4,
                fold_iterations=10, final_iterations=20,
                depth=3, thread_count=1, early_stopping_rounds=5,
                survival_thresholds_usd=(0.0, 250.0, 600.0, 900.0),
                survival_cap_usd=1_500.0))
        self.assertEqual(result["schema"], "QRE2CONFCAPACITYSTABILITY2")
        self.assertEqual(result["selection_role"], "FIT_FORWARD_OOF_ONLY")
        self.assertEqual(
            result["preflight"]["fold_support"][1]["validation"]
            ["survival"]["900.0"]["positive"], 0)
        self.assertFalse(
            result["preflight"]["fold_support"][1]
            ["validation_labels_consumed_by_fixed_fit"])
        self.assertEqual(
            {row["family"] for row in result["family_results"]},
            {"YETI_RAW_USD", "BALANCED_TOPK", "DOLLAR_MARGIN_TOPK",
             "SOFT_TOPK_RELEVANCE", "SURVIVAL_EXPECTED_VALUE",
             "HARD_PAIRLOGIT"})
        self.assertIn(result["selected_family"], {
            "YETI_RAW_USD", "BALANCED_TOPK", "DOLLAR_MARGIN_TOPK",
            "SOFT_TOPK_RELEVANCE", "SURVIVAL_EXPECTED_VALUE",
            "HARD_PAIRLOGIT"})
        self.assertEqual(result["h2_open_count"], 0)
        self.assertFalse(result["economics_executed"])

    def test_candidate_rank_broadcasts_one_formation_target_per_series(self) -> None:
        dataset = _synthetic_dataset(20210104, series_count=30)
        ledger = derive_oracle_action_ledger(dataset)
        indices, checkpoints = candidate_watch_rows(
            dataset, watch_ages_seconds=(0, 1, 2),
            require_complete_grid=True)
        target = candidate_formation_targets(
            dataset, ledger, indices=indices, checkpoints=checkpoints)
        series = np.asarray(dataset.series_id, str)[indices]
        for series_id in np.unique(series):
            local = np.flatnonzero(series == series_id)
            self.assertEqual(set(target[local]), {target[local[0]]})
            formation = local[checkpoints[local] == 0]
            self.assertEqual(len(formation), 1)
            self.assertEqual(
                target[local[0]], ledger.q_optimal_usd[indices[formation[0]]])

    def test_candidate_value_transforms_preserve_order_and_survival_laws(self) -> None:
        target = np.asarray([0.0, 1.0, 100.0, 250.0, 500.0,
                             1_000.0, 1_800.0, 4_000.0])
        for family in (
                "YETI_RAW_USD", "YETI_LOG1P", "YETI_WINSOR_1800",
                "YETI_ORDINAL", "LOG1P_RMSE"):
            transformed = candidate_value_transform(family, target)
            self.assertTrue(np.all(np.diff(transformed) >= 0.0))
        self.assertEqual(
            candidate_value_transform("YETI_ORDINAL", target).tolist(),
            [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 6.0])
        score = survival_expected_score(np.asarray([
            [.8, .9, .7, .6, .4, .2],
            [.5, .4, .3, .2, .1, .0],
        ]))
        self.assertTrue(np.all(score >= 0.0))
        self.assertGreater(score[0], score[1])

    def test_blind_dossier_selection_is_outcome_independent(self) -> None:
        dataset = _synthetic_dataset(20210104, series_count=30)
        series_order = {
            value: index for index, value in enumerate(
                np.unique(np.asarray(dataset.series_id, str)))
        }
        assets = np.asarray([
            C.ASSETS[series_order[str(value)] % len(C.ASSETS)]
            for value in dataset.series_id], str)
        dataset = replace(dataset, asset=assets)
        dataset.validate()
        first = select_blind_raw_dossiers(
            dataset, per_asset_side=1, watch_ages_seconds=(0, 1, 2))
        reversed_outcomes = np.asarray(dataset.cert_close_usd, np.float64)[::-1]
        changed = replace(
            dataset, cert_close_usd=reversed_outcomes,
            mfe_usd=np.maximum(reversed_outcomes, 0.0),
            mae_usd=np.maximum(-reversed_outcomes, 0.0),
            wall_hit=reversed_outcomes <= -900.0)
        changed.validate()
        second = select_blind_raw_dossiers(
            changed, per_asset_side=1, watch_ages_seconds=(0, 1, 2))
        self.assertEqual(
            [str(dataset.series_id[row.anchor_index]) for row in first],
            [str(changed.series_id[row.anchor_index]) for row in second])

    def test_ordered_twin_preserves_totals_but_destroys_episode_order(self) -> None:
        channels = {
            "price_return_usd": np.asarray([-100.0, -50.0, 25.0, 125.0]),
            "aligned_trade_flow": np.asarray([-20.0, -10.0, 30.0, 40.0]),
            "trade_volume": np.asarray([20.0, 10.0, 30.0, 40.0]),
            "defense_reload": np.asarray([0.0, 1.0, 3.0, 2.0]),
            "opposing_reload": np.asarray([2.0, 1.0, 0.0, 0.0]),
            "mid_direction": np.asarray([-1.0, -1.0, 1.0, 1.0]),
            "event_count": np.asarray([10.0, 20.0, 30.0, 40.0]),
        }
        ordered = _ordered_map_from_channels(
            channels, order_mode="ORDERED", permutation_key=7)
        destroyed = _ordered_map_from_channels(
            channels, order_mode="WITHIN_ROW_ORDER_DESTROYED",
            permutation_key=7)
        self.assertEqual(tuple(ordered), ORDERED_FEATURE_NAMES)
        for name in (
            "episode_current_displacement_usd", "episode_aligned_flow_total",
            "episode_trade_volume_total", "episode_event_count_total",
            "episode_defense_reload_total", "episode_opposing_reload_total",
            "episode_path_variation_usd",
        ):
            self.assertAlmostEqual(ordered[name], destroyed[name])
        self.assertNotEqual(
            ordered["episode_time_since_adverse_extreme_sec"],
            destroyed["episode_time_since_adverse_extreme_sec"])

    def test_ordered_feature_map_ignores_events_after_decision_boundary(self) -> None:
        base = {
            "price_return_usd": np.asarray([-50.0, 25.0, 25.0]),
            "aligned_trade_flow": np.asarray([-10.0, 5.0, 5.0]),
            "trade_volume": np.asarray([10.0, 5.0, 5.0]),
            "defense_reload": np.asarray([0.0, 1.0, 1.0]),
            "opposing_reload": np.asarray([1.0, 0.0, 0.0]),
            "mid_direction": np.asarray([-1.0, 1.0, 1.0]),
            "event_count": np.asarray([10.0, 10.0, 10.0]),
        }
        before = _ordered_map_from_channels(
            base, order_mode="ORDERED", permutation_key=11)
        # A future event is deliberately held outside the supplied causal
        # prefix.  Mutating it cannot alter any feature at this boundary.
        future = {name: np.r_[value, 1_000_000.0]
                  for name, value in base.items()}
        after = _ordered_map_from_channels(
            {name: value[:-1] for name, value in future.items()},
            order_mode="ORDERED", permutation_key=11)
        self.assertEqual(before, after)

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

    def test_factorized_rank_gate_is_deterministic_and_capacity_bounded(self) -> None:
        full = _synthetic_dataset(20210104)
        fixed = full.subset(np.asarray(full.min_alert_age_sec) == 0.0)
        score = np.arange(len(fixed.features), dtype=np.float64)
        selected = select_top_capacity_series(fixed, score, capacity=4)
        expected = tuple(sorted(np.asarray(fixed.series_id, str)[-4:].tolist()))
        self.assertEqual(selected, expected)
        self.assertEqual(len(selected), 4)
        self.assertEqual(FactorizedPolicyConfig().watch_age_sec, 30)

    def test_factorized_path_begins_at_selected_watch_row_not_float_age(self) -> None:
        full = _synthetic_dataset(20210104, series_count=6)
        fixed = full.subset(np.asarray(full.min_alert_age_sec) == 1.0)
        watched = tuple(np.asarray(fixed.series_id, str).tolist())
        rank = {series: float(index) for index, series in enumerate(watched)}
        watch_ts = {str(series): int(timestamp) for series, timestamp in zip(
            fixed.series_id, fixed.snapshot_ts_ns)}
        subset, _prediction, _mask = _gated_predictions(
            full, watched_series=watched, rank_by_series=rank,
            action_score=np.ones(len(full.features)),
            watch_snapshot_by_series=watch_ts, model_hash="watch-row")
        for series in watched:
            local = np.flatnonzero(np.asarray(subset.series_id, str) == series)
            self.assertEqual(int(np.min(subset.snapshot_ts_ns[local])),
                             watch_ts[series])

    def test_factorized_miniature_executes_selection_replay_and_decomposition(self) -> None:
        ranges = {
            "FIT": range(20210104, 20210108),
            "PLATT": range(20210108, 20210112),
            "THRESHOLD": range(20210112, 20210116),
        }
        datasets = {}
        for role, days in ranges.items():
            parts = []
            for day in days:
                base = _synthetic_dataset(day)
                part = replace(
                    base,
                    feature_names=("asset_SI",) + base.feature_names,
                    features=np.column_stack((
                        np.ones(len(base.features), np.float32),
                        base.features)))
                part.validate(); parts.append(part)
            datasets[role] = combine_confirmation_datasets(parts)
        ledgers = {role: derive_oracle_action_ledger(dataset)
                   for role, dataset in datasets.items()}
        fixed, fixed_ledgers, _manifest = prepare_capacity_corpora(
            datasets, ledgers,
            config=CapacityCorpusConfig(
                watch_age_sec=2, capacity=4, feature_set="MAX_W300",
                excluded_feature_names=()))
        config = FactorizedPolicyConfig(
            watch_age_sec=2, capacity=4, action_feature_set="MAX_W300",
            excluded_action_features=(), rank_iterations=5,
            action_iterations=5, depth=3, thread_count=1,
            action_thresholds=(.1, .5, .9))
        models = fit_factorized_models(
            datasets, ledgers, fixed, fixed_ledgers, config=config)
        result = run_factorized_policy(
            datasets, ledgers, fixed, fixed_ledgers,
            {role: default_expected_sessions(dataset)
             for role, dataset in datasets.items()},
            models=models, config=config)
        self.assertEqual(
            result["arms"]["LEARNED_RANK_LEARNED_TIMING"]
            ["platt_selection"]["status"], "SELECTED")
        self.assertEqual(
            set(result["decomposition"]), {"PLATT", "THRESHOLD"})
        self.assertGreater(
            result["decomposition"]["THRESHOLD"]
            ["LEARNED_RANK_LEARNED_TIMING"]
            ["evaluation"]["usd_per_portfolio_day"], 0.0)

    def test_dynamic_hurdle_executes_gate_fit_controls_and_replay(self) -> None:
        ranges = {
            "FIT": range(20210104, 20210108),
            "PLATT": range(20210108, 20210112),
            "THRESHOLD": range(20210112, 20210116),
        }
        datasets = {}
        for role, days in ranges.items():
            parts = []
            for day in days:
                base = _synthetic_dataset(day)
                varied_pnl = np.asarray(base.cert_close_usd, np.float64).copy()
                for position, series in enumerate(np.unique(base.series_id)):
                    if position % 2 == 0:
                        local = np.flatnonzero(base.series_id == series)
                        varied_pnl[local] = (950.0, 900.0, 1_000.0)
                base = replace(
                    base, cert_close_usd=varied_pnl,
                    mfe_usd=np.maximum(varied_pnl, 0.0),
                    mae_usd=np.maximum(-varied_pnl, 0.0),
                    wall_hit=varied_pnl <= -900.0)
                base.validate()
                part = replace(
                    base,
                    feature_names=("asset_SI",) + base.feature_names,
                    features=np.column_stack((
                        np.ones(len(base.features), np.float32),
                        base.features)))
                part.validate(); parts.append(part)
            datasets[role] = combine_confirmation_datasets(parts)
        ledgers = {role: derive_oracle_action_ledger(dataset)
                   for role, dataset in datasets.items()}
        fixed, fixed_ledgers, _manifest = prepare_capacity_corpora(
            datasets, ledgers,
            config=CapacityCorpusConfig(
                watch_age_sec=0, capacity=12, feature_set="MAX_W300",
                excluded_feature_names=()))
        factor_config = FactorizedPolicyConfig(
            watch_age_sec=0, capacity=12, action_feature_set="MAX_W300",
            excluded_action_features=(), rank_iterations=5,
            action_iterations=5, depth=3, thread_count=1,
            action_thresholds=(.1, .5, .9))
        rank_models = fit_factorized_models(
            datasets, ledgers, fixed, fixed_ledgers, config=factor_config)
        sessions = {role: default_expected_sessions(dataset)
                    for role, dataset in datasets.items()}
        all_paths, all_ledger, all_report = prepare_conditional_role(
            "FIT", datasets["FIT"], ledgers["FIT"], fixed["FIT"],
            fixed_ledgers["FIT"], rank_model=rank_models.rank,
            rank_control_model=rank_models.rank_control,
            expected_sessions=sessions["FIT"],
            config=ConditionalCorpusConfig(
                watch_age_sec=0, capacity=12, extra_feature_names=(),
                include_all_watchable_series=True))
        self.assertEqual(all_report["retention_mode"],
                         "ALL_WATCHABLE_SERIES")
        self.assertEqual(set(all_paths.series_id), set(fixed["FIT"].series_id))
        self.assertEqual(all_ledger.source_representation_sha256,
                         all_paths.representation_sha256)
        # The full miniature already is a small conditional cache and starts
        # exactly at the configured zero-second watch row.
        conditional = datasets
        conditional_ledgers = ledgers
        fit_score = np.asarray(rank_models.rank.predict_proba(
            fixed["FIT"].features)[:, 1], np.float64)
        fit_series = set(select_top_capacity_series(
            fixed["FIT"], fit_score, capacity=12))
        fit_mask = np.isin(conditional["FIT"].series_id, tuple(fit_series))
        fit_dataset = conditional["FIT"].subset(fit_mask)
        fit_ledger = _take_ledger(
            conditional_ledgers["FIT"], np.flatnonzero(fit_mask), fit_dataset)
        config = DynamicHurdleConfig(
            watch_age_sec=0, capacity=12, iterations=5, depth=3,
            thread_count=1, timing_thresholds=(.1, .5, .9),
            value_thresholds=(.1, .5, .9))
        models = fit_dynamic_hurdle_models(
            fit_dataset, fit_ledger, config=config)
        named = {
            "rank": rank_models.rank,
            "rank_control": rank_models.rank_control,
            "timing": models.timing, "value": models.value,
            "timing_control": models.timing_control,
            "value_control": models.value_control,
        }
        with tempfile.TemporaryDirectory(
                dir="/workspace/artifacts/cache") as tmp:
            loaded = {}
            for name, model in named.items():
                path = Path(tmp) / f"{name}.cbm"
                model.save_model(path, format="cbm")
                restored = type(model)(); restored.load_model(path, format="cbm")
                loaded[name] = restored
            restored_models = DynamicHurdleModels(
                timing=loaded["timing"], value=loaded["value"],
                timing_control=loaded["timing_control"],
                value_control=loaded["value_control"],
                feature_names=models.feature_names,
                timing_model_sha256=models.timing_model_sha256,
                value_model_sha256=models.value_model_sha256,
                timing_control_model_sha256=models.timing_control_model_sha256,
                value_control_model_sha256=models.value_control_model_sha256)
            result = run_dynamic_hurdle_policy(
                conditional, conditional_ledgers, fixed, fixed_ledgers, sessions,
                rank_model=loaded["rank"],
                rank_control_model=loaded["rank_control"],
                rank_model_sha256=rank_models.rank_model_sha256,
                rank_control_model_sha256=rank_models.rank_control_model_sha256,
                models=restored_models, config=config)
        self.assertEqual(result["platt_selection"]["status"], "SELECTED")
        self.assertEqual(set(result["decomposition"]), {"PLATT", "THRESHOLD"})
        self.assertIsNotNone(result["threshold_fixed_policy_arms"])
        self.assertEqual(set(result["platt_fixed_policy_arms"]), {
            "LEARNED_RANK_LEARNED_BOTH",
            "LEARNED_RANK_SHUFFLED_TIMING",
            "LEARNED_RANK_SHUFFLED_VALUE",
            "LEARNED_RANK_SHUFFLED_BOTH",
            "SHUFFLED_RANK_LEARNED_BOTH",
        })
        self.assertEqual(result["value_score_units"],
                         "DIMENSIONLESS_CLASS_PROBABILITY_NOT_USD")
        self.assertEqual(
            result["sparse_schedule_ceiling"]["PLATT"]["LEARNED"]["scope"],
            "SPARSE_TRAINING_GRID_HINDSIGHT_UPPER_BOUND_NOT_EXACT")
        self.assertFalse(result["sparse_schedule_ceiling"]["PLATT"]
                         ["LEARNED"]["exact_replay_ceiling"])
        portfolio_target, target_report = portfolio_schedule_target(
            conditional["FIT"], fixed["FIT"])
        self.assertGreater(target_report["positive"], 0)
        portfolio_config = PortfolioGateConfig(
            watch_age_sec=0, capacity_per_asset_day=12,
            iterations=5, depth=3, thread_count=1, folds=((2, 1),))
        portfolio_models = fit_portfolio_gate_models(
            fixed["FIT"], portfolio_target, config=portfolio_config)
        portfolio_result = run_portfolio_gate_probe(
            conditional, fixed, sessions,
            rank_model=rank_models.rank,
            rank_control_model=rank_models.rank_control,
            models=portfolio_models, config=portfolio_config)
        self.assertFalse(portfolio_result["roster_conditioned"])
        self.assertEqual(set(portfolio_result["fit_oof_capture"]), {
            "REAL", "CONTROL", "OLD_RANK", "OLD_RANK_CONTROL"})
        self.assertTrue(portfolio_result["candidate_gate_ceiling_only"])
        self.assertFalse(portfolio_result["learned_economics_executed"])
        utility_config = DirectUtilityConfig(
            watch_age_sec=0, capacity=12, iterations=5, depth=3,
            thread_count=1,
            enter_thresholds_usd=(-300.0, .01, 300.0),
            advantage_thresholds_usd=(-100.0, .01, 100.0))
        utility_models = fit_direct_utility_models(
            fit_dataset, fit_ledger, config=utility_config)
        with tempfile.TemporaryDirectory(
                dir="/workspace/artifacts/cache") as tmp:
            restored = {}
            for name, model in (("real", utility_models.real),
                                ("control", utility_models.control)):
                path = Path(tmp) / f"utility_{name}.cbm"
                model.save_model(path, format="cbm")
                loaded_model = type(model)()
                loaded_model.load_model(path, format="cbm")
                restored[name] = loaded_model
            restored_utility = DirectUtilityModels(
                real=restored["real"], control=restored["control"],
                feature_names=utility_models.feature_names,
                real_model_sha256=utility_models.real_model_sha256,
                control_model_sha256=utility_models.control_model_sha256)
            utility_result = run_direct_utility_policy(
                conditional, conditional_ledgers, fixed, fixed_ledgers,
                sessions, rank_model=rank_models.rank,
                rank_control_model=rank_models.rank_control,
                models=restored_utility, config=utility_config)
        self.assertEqual(utility_result["target_units"], "USD")
        self.assertTrue(utility_result["canonical_replay_executed"])
        self.assertFalse(utility_result["threshold_economics_executed"])
        self.assertEqual(set(utility_result["platt_fixed_policy_arms"]),
                         {"REAL", "CONTROL", "ORACLE"})
        self.assertEqual(set(utility_result[
            "platt_model_score_argmax_replay_diagnostics"]),
            {"REAL", "CONTROL", "ORACLE"})

    def test_acceptance_diagnostic_enforces_absolute_potential_laws(self) -> None:
        full = _synthetic_dataset(20210104)
        fixed = full.subset(np.asarray(full.min_alert_age_sec) == 2.0)
        ledger = derive_oracle_action_ledger(full)
        lookup = {str(value): float(target) for value, target in zip(
            full.opportunity_id, ledger.q_optimal_usd)}
        target = np.asarray([lookup[str(value)]
                             for value in fixed.opportunity_id], np.float64)
        score = np.clip(target / 1_200.0, 0.0, 1.0)
        result = acceptance_potential_diagnostic(
            fixed, target, rank_score=score, acceptance_score=score,
            score_thresholds=(.3, .8), capacity=12,
            minimum_potential_mean_usd=600.0,
            minimum_portfolio_day_usd=3_000.0)
        self.assertEqual(result["status"], "GOAL_POTENTIAL")
        self.assertGreaterEqual(
            result["selected_scorecard"]["potential_mean_usd"], 600.0)

    def test_fixed_horizon_target_excludes_right_censored_tail(self) -> None:
        dataset = _synthetic_dataset(20210104, series_count=3)
        ledger = derive_oracle_action_ledger(dataset)
        target = fixed_horizon_target(dataset, ledger, 1)
        series = np.asarray(dataset.series_id, str)
        timestamp = np.asarray(dataset.snapshot_ts_ns, np.int64)
        first_series = series[0]
        local = np.flatnonzero(series == first_series)
        local = local[np.argsort(timestamp[local])]
        self.assertTrue(np.array_equal(
            target.eligible[local], np.asarray((True, True, False))))
        self.assertTrue(np.array_equal(
            target.terminal_row[local], np.asarray((False, False, True))))
        self.assertAlmostEqual(
            target.stop_utility_usd[local[0]], -805.0)
        self.assertAlmostEqual(
            target.stop_utility_usd[local[1]], -1_300.0)
        self.assertTrue(np.isnan(target.stop_utility_usd[local[2]]))

    def test_watch_relative_features_do_not_cross_candidate_paths(self) -> None:
        dataset = _synthetic_dataset(20210104, series_count=3)
        index = np.asarray((dataset.feature_names.index("state_age"),),
                           np.int64)
        relative, dynamic = watch_relative_matrix(dataset, index)
        series = np.asarray(dataset.series_id, str)
        timestamp = np.asarray(dataset.snapshot_ts_ns, np.int64)
        for key in np.unique(series):
            local = np.flatnonzero(series == key)
            local = local[np.argsort(timestamp[local])]
            self.assertTrue(np.array_equal(
                relative[local, 0], np.asarray((0.0, 1.0, 2.0))))
        self.assertEqual(dynamic[0], 1.0)

    def test_fixed_horizon_controls_preserve_path_target_mass(self) -> None:
        dataset = _synthetic_dataset(20210104, series_count=6)
        ledger = derive_oracle_action_ledger(dataset)
        target = fixed_horizon_target(dataset, ledger, 1)
        shuffled = shuffle_within_series(
            target.stop_utility_usd, target.eligible, dataset.series_id,
            seed=19, kind="WITHIN_SERIES_PERMUTATION")
        series = np.asarray(dataset.series_id, str)
        for key in np.unique(series):
            local = np.flatnonzero(target.eligible & (series == key))
            self.assertTrue(np.array_equal(
                np.sort(shuffled[local]),
                np.sort(target.stop_utility_usd[local])))
        self.assertFalse(np.array_equal(
            shuffled[target.eligible],
            target.stop_utility_usd[target.eligible]))

    def test_fixed_horizon_allowlist_removes_global_clock_shortcuts(self) -> None:
        names = (
            "max_alert_age_sec", "ctx_VIX_last_value_0",
            "disc_auction_session_age_sec", "disc_path_defended_retest_current",
            "disc_eclock_n64_event_rate_hz", "w30_path_efficiency",
        )
        selected = eligible_feature_indices(names)
        self.assertEqual(selected.tolist(), [3, 4, 5])

    def test_fixed_horizon_oracle_executes_canonical_receipt_boundary(self) -> None:
        dataset = _synthetic_dataset(20210104)
        ledger = derive_oracle_action_ledger(dataset)
        config = FixedHorizonConfig(
            watch_age_sec=0, horizons_sec=(1,),
            value_thresholds_usd=(.01,), regret_thresholds_usd=(0.0,),
            control_replicates=1)
        result = _oracle_policy_family(
            dataset, ledger, {1: fixed_horizon_target(dataset, ledger, 1)},
            default_expected_sessions(dataset), config)
        self.assertEqual(
            result["scope"],
            "ORACLE_MECHANISM_DIAGNOSTIC_NOT_LEARNED_ECONOMICS")
        self.assertGreater(
            result["selected"]["evaluation"]["portfolio_days"], 0)

    def test_acceptance_cross_section_centres_without_target_access(self) -> None:
        dataset = _synthetic_dataset(20210104, series_count=6).subset(
            np.asarray(_synthetic_dataset(
                20210104, series_count=6).max_alert_age_sec) == 2.0)
        selected = np.asarray((dataset.feature_names.index("state_signal"),),
                              np.int64)
        matrix, dynamic = cross_section_matrix(dataset, selected)
        groups = asset_day_groups(dataset)
        for group in np.unique(groups):
            self.assertAlmostEqual(float(np.mean(matrix[groups == group])), 0.0)
        self.assertEqual(dynamic[0], 1.0)

    def test_acceptance_control_preserves_each_asset_day_target_mass(self) -> None:
        full = _synthetic_dataset(20210104, series_count=12)
        fixed = full.subset(np.asarray(full.max_alert_age_sec) == 2.0)
        target = np.arange(len(fixed.features), dtype=np.float64)
        shuffled = shuffle_within_asset_day(fixed, target, seed=29)
        groups = asset_day_groups(fixed)
        for group in np.unique(groups):
            local = groups == group
            self.assertTrue(np.array_equal(
                np.sort(target[local]), np.sort(shuffled[local])))
        self.assertFalse(np.array_equal(target, shuffled))

    def test_acceptance_feature_filter_removes_all_age_proxies(self) -> None:
        names = ("state_signal", "max_alert_age_sec",
                 "disc_state_retest_age_sec", "ctx_VIX_history_coverage")
        self.assertEqual(acceptance_feature_indices(names).tolist(), [0])

    def test_lawful_candidate_value_excludes_terminal_and_censored_paths(
            self) -> None:
        full = _synthetic_dataset(20210104, series_count=6)
        series = np.asarray(full.series_id, str)
        age = np.asarray(full.min_alert_age_sec, np.float64)
        first_series = str(series[0])
        conditional = full.subset((series != first_series) | (age == 0.0))
        fixed = conditional.subset(
            np.asarray(conditional.min_alert_age_sec, np.float64) == 0.0)
        ledger = derive_oracle_action_ledger(conditional)
        target = candidate_lawful_value_target(
            conditional, ledger, fixed, horizon_sec=1,
            maximum_stop_regret_usd=0.0, watch_age_sec=0)
        fixed_series = np.asarray(fixed.series_id, str)
        self.assertFalse(target.observed[fixed_series == first_series][0])
        observed_values = target.value_usd[target.observed]
        # Falling paths expose a lawful local maximum at the first row;
        # rising paths do not get to use the excluded terminal action.
        self.assertEqual(sorted(observed_values.tolist()),
                         [0.0, 0.0, 0.0, 100.0, 100.0])
        self.assertTrue(np.isnan(target.value_usd[~target.observed]).all())

    def test_lawful_value_control_preserves_censoring_and_group_mass(
            self) -> None:
        full = _synthetic_dataset(20210104, series_count=12)
        fixed = full.subset(
            np.asarray(full.min_alert_age_sec, np.float64) == 0.0)
        target = candidate_lawful_value_target(
            full, derive_oracle_action_ledger(full), fixed, horizon_sec=1,
            maximum_stop_regret_usd=0.0, watch_age_sec=0)
        shuffled = shuffle_observed_within_asset_day(
            fixed, target, seed=31)
        groups = asset_day_groups(fixed)
        for group in np.unique(groups):
            local = target.observed & (groups == group)
            self.assertTrue(np.array_equal(
                np.sort(target.value_usd[local]), np.sort(shuffled[local])))
        self.assertFalse(np.array_equal(
            target.value_usd[target.observed], shuffled[target.observed]))

    def test_lawful_value_rank_diagnostic_uses_dollars_not_auc(self) -> None:
        full = _synthetic_dataset(20210104, series_count=12)
        fixed = full.subset(
            np.asarray(full.min_alert_age_sec, np.float64) == 0.0)
        target = candidate_lawful_value_target(
            full, derive_oracle_action_ledger(full), fixed, horizon_sec=1,
            maximum_stop_regret_usd=0.0, watch_age_sec=0)
        score = np.nan_to_num(target.value_usd)
        result = lawful_value_rank_diagnostic(
            score, target, fixed, capacity=4)
        self.assertEqual(result["top_capacity_lawful_value_capture"], 1.0)
        self.assertTrue(result["not_schedule_economics"])
        self.assertEqual(LawfulValueRankConfig().capacity, 12)

    def test_lawful_policy_crossing_is_causal_and_excludes_terminal(self) -> None:
        dataset = _synthetic_dataset(20210104, series_count=3)
        ledger = derive_oracle_action_ledger(dataset)
        target = fixed_horizon_target(dataset, ledger, 1)
        # Every path starts at score zero; only the middle row clears +1.
        score = np.tile(np.asarray((0.0, 2.0, 9.0)), 3)
        chosen = causal_first_crossings(
            dataset, target, score,
            sorted(set(np.asarray(dataset.series_id, str).tolist())),
            minimum_delay_sec=1, stop_delta_threshold=1.0)
        self.assertEqual(len(chosen), 3)
        self.assertTrue(np.all(
            np.asarray(dataset.min_alert_age_sec)[chosen] == 1.0))
        self.assertFalse(np.any(target.terminal_row[chosen]))

    def test_path_state_keeps_signed_losses_and_is_suffix_invariant(self) -> None:
        source = _synthetic_dataset(20210104, series_count=9)
        signal = np.asarray(source.features[:, 0], np.float64)
        step = np.asarray(source.min_alert_age_sec, np.float64)
        side = np.asarray(source.side, np.float64)
        columns = {
            "w1_event_count": 2.0 + step,
            "w1_trade_count": np.ones(len(step)),
            "w1_trade_volume": 10.0 + np.abs(signal) * 10.0,
            "w1_aligned_trade_flow": signal * 10.0,
            "w1_aligned_defense": np.maximum(-signal, 0.0) * 5.0,
            "w1_opposing_retreat": np.maximum(signal, 0.0) * 3.0,
            "w1_spread_widen_minus_narrow": np.sign(signal),
            "disc_state_current_displacement_ticks": signal * 4.0,
            "current_spread_usd": np.full(len(step), 25.0),
            "current_size_imbalance": signal * side,
            "disc_behavior_control_evidence_balance": signal,
            "disc_state_price_yield_per_attack": signal / 2.0,
            "disc_absorption_attack_per_adverse_tick": np.maximum(
                -signal, 0.0),
            "disc_absorption_reload_per_attack": np.maximum(signal, 0.0),
            "disc_mhi_attack_exhaustion_5_vs_30": -signal,
            "disc_mhi_lift_acceleration_5_vs_30": signal,
        }
        names = tuple(INCREMENT_SIGNALS) + tuple(STATE_SIGNALS)
        dataset = replace(
            source, feature_names=names,
            features=np.column_stack([columns[name] for name in names])
                .astype(np.float32))
        dataset.validate()
        ledger = derive_oracle_action_ledger(dataset)
        watch = build_path_state_landmark(
            dataset, ledger, landmark_delay_sec=0, horizon_sec=1,
            watch_age_sec=0)
        self.assertEqual(len(watch.dataset.features), 9)
        self.assertTrue(np.all(watch.target.observed))
        self.assertGreater(np.sum(watch.target.value_usd < 0.0), 0)
        self.assertGreater(np.sum(watch.target.value_usd > 0.0), 0)

        landmark = build_path_state_landmark(
            dataset, ledger, landmark_delay_sec=1, horizon_sec=1,
            watch_age_sec=0)
        changed = np.asarray(dataset.features).copy()
        changed[np.asarray(dataset.min_alert_age_sec) > 1.0] += 999.0
        suffix_changed = replace(dataset, features=changed)
        suffix_changed.validate()
        changed_landmark = build_path_state_landmark(
            suffix_changed, derive_oracle_action_ledger(suffix_changed),
            landmark_delay_sec=1, horizon_sec=1, watch_age_sec=0)
        self.assertTrue(np.array_equal(
            landmark.matrix, changed_landmark.matrix))

        population = np.ones(len(watch.dataset.features), bool)
        ordinal = _objective_relevance(
            watch.target.value_usd, watch, population,
            PathStateRankConfig(objective_variant="ORDINAL_POSITIVE_TOP3"))
        groups = asset_day_groups(watch.dataset)
        for group in np.unique(groups):
            local = np.flatnonzero(groups == group)
            positive = local[watch.target.value_usd[local] > 0.0]
            expected_nonzero = min(3, len(positive))
            self.assertEqual(np.count_nonzero(ordinal[local]), expected_nonzero)
            self.assertTrue(np.all(
                ordinal[local][watch.target.value_usd[local] <= 0.0] == 0.0))

        roster = tuple(map(str, watch.dataset.series_id.tolist()))
        ceiling = run_path_state_acceptance_ceiling(
            dataset, ledger, watch, default_expected_sessions(dataset),
            roster=roster, real_score=watch.target.value_usd,
            control_score=-watch.target.value_usd,
            evaluation_scope="FIT_CHRONOLOGICAL_OOF")
        self.assertIn(
            ceiling["arms"]["REAL"]["selected"]["selection_family"],
            {"FIXED_TOPK_PER_ASSET_DAY", "GLOBAL_SCORE_CUTOFF_CEILING"})
        self.assertTrue(any(
            row["selection_family"] == "GLOBAL_SCORE_CUTOFF_CEILING"
            for row in ceiling["arms"]["REAL"]["scorecards"]))

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
