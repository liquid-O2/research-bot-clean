"""Cheap causal and destruction checks for discretionary Entry V2 features.

These are regression/falsification checks only.  They are not launch evidence.
"""

from __future__ import annotations

import unittest

import numpy as np

from engine.entry_v2.confirmation_diagnostics import registered_feature_sets
from engine.entry_v2.discretionary_features import (
    CausalDiscretionaryPlane, PriorSessionContext,
)
from engine.entry_v2.event_pack import EVENT_DTYPE


def _fixture(*, include_future: bool = True):
    # (second, action, side, event price, size, bid, ask)
    source = [
        (10, "T", "A", 100, 10, 100, 101),
        (11, "A", "B", 100, 8, 100, 101),
        (20, "T", "B", 101, 7, 100, 101),
        (100, "T", "A", 100, 6, 100, 101),
        (200, "T", "B", 102, 5, 101, 102),
        (350, "M", "B", 100, 1, 100, 101),
        (351, "M", "B", 99, 1, 99, 100),
        (352, "M", "B", 100, 1, 100, 101),
        (353, "M", "B", 102, 1, 102, 103),
        (354, "M", "B", 100, 1, 100, 101),
    ]
    if include_future:
        source.extend((
            (700, "T", "B", 200, 999, 199, 200),
            (701, "A", "A", 200, 999, 199, 200),
        ))
    rows = np.zeros(len(source), dtype=EVENT_DTYPE)
    open_ns = 1_000_000_000_000
    for index, (second, action, side, price, size, bid, ask) in enumerate(source):
        timestamp = open_ns + second * 1_000_000_000 + index
        rows[index]["ts_recv_ns"] = timestamp
        rows[index]["ts_event_ns"] = timestamp - 100
        rows[index]["price"] = price
        rows[index]["bid_px"] = bid
        rows[index]["ask_px"] = ask
        rows[index]["size"] = size
        rows[index]["bid_sz"] = 20
        rows[index]["ask_sz"] = 20
        rows[index]["bid_ct"] = 2
        rows[index]["ask_ct"] = 2
        rows[index]["sequence"] = index + 1
        rows[index]["receive_session_sec"] = second
        rows[index]["action"] = ord(action)
        rows[index]["side"] = ord(side)
    truth = {
        "trusted_message": np.ones(len(rows), bool),
        "trusted_economic": np.ones(len(rows), bool),
        "mid2": rows["bid_px"].astype(np.int64) + rows["ask_px"].astype(np.int64),
    }
    flags = {name: np.zeros(len(rows), np.int64) for name in (
        "bid_reload", "ask_reload", "bid_pull_no_fill", "ask_pull_no_fill",
        "bid_reload_latency_ns", "ask_reload_latency_ns",
        "bid_pull_lifetime_ns", "ask_pull_lifetime_ns")}
    flags["bid_reload"][1] = 1
    flags["bid_reload_latency_ns"][1] = 1_000_000_001
    candidate = {
        "decision_sec": "350",
        "decision_ts_ns": str(open_ns + 350 * 1_000_000_000),
        "entry_mid2": "201",
        "entry_bid_px": "100", "entry_ask_px": "101",
        "phase_open_utc": "1000",
    }
    return rows, truth, flags, candidate, open_ns


def _plane(*, include_future: bool, mode: str = "REAL", prior=None):
    rows, truth, flags, candidate, open_ns = _fixture(
        include_future=include_future)
    plane = CausalDiscretionaryPlane(
        rows=rows, truth=truth, asset="SI", open_ns=open_ns,
        duration_sec=1_000, raw_tick=1, multiplier=5_000,
        event_state_flags=flags, level_association_mode=mode,
        prior_session=prior)
    return plane, candidate, open_ns


class DiscretionaryFeatureTests(unittest.TestCase):
    def test_fill_coupling_twin_preserves_level_marginals_not_timing(self) -> None:
        open_ns = 6_000_000_000_000
        source = (
            (100, "T", "A", 100, 10, 100, 101),
            (101, "M", "B", 100, 7, 100, 101),
            (110, "T", "A", 110, 9, 110, 111),
            (150, "M", "B", 110, 13, 110, 111),
            (199, "M", "B", 100, 1, 100, 101),
        )
        rows = np.zeros(len(source), dtype=EVENT_DTYPE)
        for index, (second, action, event_side, price, size, bid, ask) in enumerate(source):
            timestamp = open_ns + second * 1_000_000_000 + 1
            rows[index]["ts_recv_ns"] = timestamp
            rows[index]["ts_event_ns"] = timestamp - 10
            rows[index]["price"] = price; rows[index]["size"] = size
            rows[index]["bid_px"] = bid; rows[index]["ask_px"] = ask
            rows[index]["bid_sz"] = 20; rows[index]["ask_sz"] = 20
            rows[index]["bid_ct"] = 2; rows[index]["ask_ct"] = 2
            rows[index]["receive_session_sec"] = second
            rows[index]["action"] = ord(action)
            rows[index]["side"] = ord(event_side)
        truth = {
            "trusted_message": np.ones(len(rows), bool),
            "trusted_economic": np.ones(len(rows), bool),
            "mid2": rows["bid_px"].astype(np.int64)
                    + rows["ask_px"].astype(np.int64),
        }
        flags = {name: np.zeros(len(rows), np.int64) for name in (
            "bid_reload", "ask_reload", "bid_pull_no_fill",
            "ask_pull_no_fill", "bid_reload_latency_ns",
            "ask_reload_latency_ns", "bid_pull_lifetime_ns",
            "ask_pull_lifetime_ns")}
        flags["bid_reload"][[1, 3]] = 1
        flags["bid_reload_latency_ns"][[1, 3]] = (
            1_000_000_000, 40_000_000_000)
        candidate = {
            "decision_sec": "100",
            "decision_ts_ns": str(open_ns + 100 * 1_000_000_000),
            "entry_mid2": "201", "entry_bid_px": "100",
            "entry_ask_px": "101", "phase_open_utc": "6000",
        }
        kwargs = dict(
            snapshot_ts_ns=open_ns + 200 * 1_000_000_000,
            current_bid=100, current_ask=101, current_mid2=201,
            side=1, formation_candidate=candidate)
        def values(mode: str):
            return CausalDiscretionaryPlane(
                rows=rows, truth=truth, asset="SI", open_ns=open_ns,
                duration_sec=700, raw_tick=1, multiplier=5_000,
                event_state_flags=flags,
                level_association_mode=mode).feature_map(**kwargs)
        real = values("REAL")
        destroyed = values("FILL_COUPLING_DESTROYED")
        for name in (
                "disc_level_z0_defense_reload_count",
                "disc_level_z0_defense_reload_size",
                "disc_level_z0_attack_volume"):
            self.assertEqual(real[name], destroyed[name], name)
        self.assertNotEqual(
            real["disc_evt_h120_reload_latency_median_ms"],
            destroyed["disc_evt_h120_reload_latency_median_ms"])
        self.assertEqual(real["disc_fill_coupling_destroyed"], 0.0)
        self.assertEqual(destroyed["disc_fill_coupling_destroyed"], 1.0)

    def test_max_w300_roster_reaches_every_discretionary_family(self) -> None:
        plane, candidate, open_ns = _plane(include_future=False)
        values = plane.feature_map(
            snapshot_ts_ns=open_ns + 355 * 1_000_000_000,
            current_bid=100, current_ask=101, current_mid2=201,
            side=1, formation_candidate=candidate)
        names = tuple(values)
        mask = registered_feature_sets(names)["MAX_W300"]
        missing = [name for name, selected in zip(names, mask)
                   if name.startswith("disc_") and not selected]
        self.assertEqual(missing, [])

    def test_best_quote_dwell_depletion_rebuild_and_level_control(self) -> None:
        open_ns = 5_000_000_000_000
        source = (
            # second, bid, ask, bid size, bid count
            (100, 100, 101, 100, 4),
            (101, 100, 101, 60, 3),   # same-best depletion
            (102, 100, 101, 90, 5),   # same-best rebuild
            (104, 99, 100, 40, 2),    # defended level disappears
        )
        rows = np.zeros(len(source), dtype=EVENT_DTYPE)
        for index, (second, bid, ask, bid_size, bid_count) in enumerate(source):
            timestamp = open_ns + second * 1_000_000_000 + 1
            rows[index]["ts_recv_ns"] = timestamp
            rows[index]["ts_event_ns"] = timestamp - 10
            rows[index]["price"] = bid
            rows[index]["bid_px"] = bid; rows[index]["ask_px"] = ask
            rows[index]["bid_sz"] = bid_size; rows[index]["ask_sz"] = 50
            rows[index]["bid_ct"] = bid_count; rows[index]["ask_ct"] = 2
            rows[index]["size"] = abs(bid_size)
            rows[index]["receive_session_sec"] = second
            rows[index]["action"] = ord("M"); rows[index]["side"] = ord("B")
        truth = {
            "trusted_message": np.ones(len(rows), bool),
            "trusted_economic": np.ones(len(rows), bool),
            "mid2": rows["bid_px"].astype(np.int64)
                    + rows["ask_px"].astype(np.int64),
        }
        flags = {name: np.zeros(len(rows), np.int64) for name in (
            "bid_reload", "ask_reload", "bid_pull_no_fill",
            "ask_pull_no_fill", "bid_reload_latency_ns",
            "ask_reload_latency_ns", "bid_pull_lifetime_ns",
            "ask_pull_lifetime_ns")}
        candidate = {
            "decision_sec": "100",
            "decision_ts_ns": str(open_ns + 100 * 1_000_000_000),
            "entry_mid2": "201", "entry_bid_px": "100",
            "entry_ask_px": "101", "phase_open_utc": "5000",
        }
        kwargs = dict(
            snapshot_ts_ns=open_ns + 105 * 1_000_000_000,
            current_bid=99, current_ask=100, current_mid2=199,
            side=1, formation_candidate=candidate)
        planes = [CausalDiscretionaryPlane(
            rows=rows, truth=truth, asset="SI", open_ns=open_ns,
            duration_sec=700, raw_tick=1, multiplier=5_000,
            event_state_flags=flags, level_association_mode=mode)
            for mode in ("REAL", "LEVEL_ASSOCIATION_DESTROYED")]
        real, destroyed = (plane.feature_map(**kwargs) for plane in planes)
        prefix = "disc_quote_formation_"
        self.assertAlmostEqual(
            real[prefix + "defense_at_formation_time_fraction"], .8,
            places=6)
        self.assertEqual(real[prefix + "depletion_count"], 1.0)
        self.assertEqual(real[prefix + "depletion_size"], 40.0)
        self.assertEqual(real[prefix + "rebuild_count"], 1.0)
        self.assertEqual(real[prefix + "rebuild_size"], 30.0)
        self.assertEqual(real[prefix + "rebuild_after_depletion_count"], 1.0)
        self.assertAlmostEqual(
            real[prefix + "rebuild_after_depletion_mean_latency_ms"], 1000.0)
        self.assertEqual(
            real[prefix + "formation_level_disappearance_count"], 1.0)
        self.assertNotEqual(
            real[prefix + "defense_at_formation_time_fraction"],
            destroyed[prefix + "defense_at_formation_time_fraction"])

    def test_subsecond_price_path_drives_confirmation_state(self) -> None:
        open_ns = 3_000_000_000_000
        # All four transitions occur inside second 101.  A one-row-per-second
        # state machine sees only the final retest and therefore misses the
        # adverse -> reclaim -> lift ordering entirely.
        books = (
            (100, 1, 100, 101),
            (101, 100_000_000, 99, 100),
            (101, 200_000_000, 100, 101),
            (101, 300_000_000, 102, 103),
            (101, 400_000_000, 100, 101),
        )
        rows = np.zeros(len(books), dtype=EVENT_DTYPE)
        for index, (second, offset, bid, ask) in enumerate(books):
            timestamp = open_ns + second * 1_000_000_000 + offset
            rows[index]["ts_recv_ns"] = timestamp
            rows[index]["ts_event_ns"] = timestamp - 10
            rows[index]["price"] = bid
            rows[index]["bid_px"] = bid
            rows[index]["ask_px"] = ask
            rows[index]["size"] = 1
            rows[index]["receive_session_sec"] = second
            rows[index]["action"] = ord("M")
            rows[index]["side"] = ord("B")
        truth = {
            "trusted_message": np.ones(len(rows), bool),
            "trusted_economic": np.ones(len(rows), bool),
            "mid2": rows["bid_px"].astype(np.int64)
                    + rows["ask_px"].astype(np.int64),
        }
        flags = {name: np.zeros(len(rows), np.int64) for name in (
            "bid_reload", "ask_reload", "bid_pull_no_fill",
            "ask_pull_no_fill", "bid_reload_latency_ns",
            "ask_reload_latency_ns", "bid_pull_lifetime_ns",
            "ask_pull_lifetime_ns")}
        plane = CausalDiscretionaryPlane(
            rows=rows, truth=truth, asset="SI", open_ns=open_ns,
            duration_sec=700, raw_tick=1, multiplier=5_000,
            event_state_flags=flags)
        candidate = {
            "decision_sec": "100",
            "decision_ts_ns": str(open_ns + 100 * 1_000_000_000),
            "entry_mid2": "201", "entry_bid_px": "100",
            "entry_ask_px": "101", "phase_open_utc": "3000",
        }
        values = plane.feature_map(
            snapshot_ts_ns=open_ns + 102 * 1_000_000_000,
            current_bid=100, current_ask=101, current_mid2=201,
            side=1, formation_candidate=candidate)
        for name in ("adverse", "reclaim", "lift", "retest"):
            self.assertEqual(values[f"disc_state_{name}_seen"], 1.0)
        self.assertAlmostEqual(values["disc_state_adverse_age_sec"], .9)
        self.assertAlmostEqual(values["disc_state_reclaim_age_sec"], .8)
        self.assertAlmostEqual(values["disc_state_lift_age_sec"], .7)
        self.assertAlmostEqual(values["disc_state_retest_age_sec"], .6)

    def test_prior_reactions_are_count_weighted_across_price_radius(self) -> None:
        open_ns = 4_000_000_000_000
        source = (
            (10, "T", "A", 100, 100, 101),
            (11, "M", "B", 101, 101, 102),
            (20, "T", "A", 101, 101, 102),
            (21, "M", "B", 102, 102, 103),
            (60, "M", "B", 102, 102, 103),
            (150, "M", "B", 102, 102, 103),
        )
        rows = np.zeros(len(source), dtype=EVENT_DTYPE)
        for index, (second, action, side, price, bid, ask) in enumerate(source):
            timestamp = open_ns + second * 1_000_000_000
            rows[index]["ts_recv_ns"] = timestamp
            rows[index]["ts_event_ns"] = timestamp - 10
            rows[index]["price"] = price
            rows[index]["bid_px"] = bid
            rows[index]["ask_px"] = ask
            rows[index]["size"] = 5
            rows[index]["receive_session_sec"] = second
            rows[index]["action"] = ord(action)
            rows[index]["side"] = ord(side)
        prior = PriorSessionContext(
            rows=rows, asset="SI", trading_day=20210103,
            event_pack_sha256="b" * 64, raw_tick=1, multiplier=5_000)
        values = prior.feature_map(
            current_mid2=205, formation_bid=100, formation_ask=101, side=1)
        self.assertEqual(values["disc_prior_level_z2_reaction_30_count"], 2.0)
        self.assertEqual(values["disc_prior_level_z2_reaction_30_defense_rate"], 1.0)
        self.assertLessEqual(
            values["disc_prior_level_z2_reaction_30_mean_usd"],
            values["disc_prior_level_z2_reaction_30_max_usd"])

    def test_q90_surprise_is_not_a_coverage_alias(self) -> None:
        plane, candidate, open_ns = _plane(include_future=False)
        candidate = dict(candidate)
        for scope in ("session", "phase"):
            candidate[f"{scope}_forecast_present"] = "1"
            candidate[f"{scope}_move_q50_usd"] = "1000"
            candidate[f"{scope}_move_q90_usd"] = "2000"
        values = plane.feature_map(
            snapshot_ts_ns=open_ns + 600 * 1_000_000_000,
            current_bid=100, current_ask=101, current_mid2=201,
            side=1, formation_candidate=candidate)
        self.assertGreater(values["disc_fvol_session_q90_coverage"], 0.0)
        self.assertEqual(values["disc_fvol_session_range_surprise_over_q90"], 0.0)

    def test_qrf4_sigma_decomposition_reaches_confirmation_features(self) -> None:
        plane, candidate, open_ns = _plane(include_future=False)
        candidate = dict(candidate)
        for scope in ("session", "phase"):
            candidate.update({
                f"{scope}_forecast_present": "1",
                f"{scope}_sigma_hat_usd": "210.5",
                f"{scope}_sigma_components_present": "1",
                f"{scope}_sigma_raw_hat_usd": "200",
                f"{scope}_sigma_persistence_usd": "250",
                f"{scope}_sigma_calibration_ratio": "1.0525",
                f"{scope}_sigma_calibration_count": "66",
                f"{scope}_sigma_calibrated_hat_usd": "210.5",
                f"{scope}_sigma_shrinkage_delta_usd": "10.5",
                f"{scope}_sigma_ols_minus_persistence_usd": "-50",
                f"{scope}_sigma_ols_over_persistence": ".8",
                f"{scope}_unscaled_fallback_present": "0",
            })
        values = plane.feature_map(
            snapshot_ts_ns=open_ns + 600 * 1_000_000_000,
            current_bid=100, current_ask=101, current_mid2=201,
            side=1, formation_candidate=candidate)
        for scope in ("session", "phase"):
            prefix = f"disc_fvol_{scope}_"
            self.assertEqual(values[prefix + "sigma_components_present"], 1.0)
            self.assertEqual(values[prefix + "sigma_raw_hat_usd"], 200.0)
            self.assertEqual(values[prefix + "sigma_persistence_usd"], 250.0)
            self.assertEqual(values[prefix + "sigma_calibration_ratio"], 1.0525)
            self.assertEqual(values[prefix + "sigma_calibration_count"], 66.0)
            self.assertEqual(values[prefix + "sigma_calibrated_hat_usd"], 210.5)
            self.assertEqual(values[prefix + "sigma_shrinkage_delta_usd"], 10.5)
            self.assertEqual(
                values[prefix + "sigma_ols_minus_persistence_usd"], -50.0)
            self.assertEqual(values[prefix + "sigma_ols_over_persistence"], .8)
            self.assertEqual(values[prefix + "unscaled_fallback_present"], 0.0)

    def test_side_mirror_preserves_aligned_mechanism_features(self) -> None:
        rows, truth, flags, candidate, open_ns = _fixture(include_future=False)
        mirror_rows = rows.copy()
        center = 201
        mirror_rows["price"] = center - rows["price"]
        mirror_rows["bid_px"] = center - rows["ask_px"]
        mirror_rows["ask_px"] = center - rows["bid_px"]
        mirror_rows["side"] = np.where(
            rows["side"] == ord("B"), ord("A"), ord("B"))
        mirror_truth = dict(truth)
        mirror_truth["mid2"] = (mirror_rows["bid_px"].astype(np.int64)
                                + mirror_rows["ask_px"].astype(np.int64))
        mirror_flags = {name: values.copy() for name, values in flags.items()}
        for left, right in (
                ("bid_reload", "ask_reload"),
                ("bid_pull_no_fill", "ask_pull_no_fill"),
                ("bid_reload_latency_ns", "ask_reload_latency_ns"),
                ("bid_pull_lifetime_ns", "ask_pull_lifetime_ns")):
            mirror_flags[left] = flags[right].copy()
            mirror_flags[right] = flags[left].copy()
        long = CausalDiscretionaryPlane(
            rows=rows, truth=truth, asset="SI", open_ns=open_ns,
            duration_sec=1_000, raw_tick=1, multiplier=5_000,
            event_state_flags=flags)
        short = CausalDiscretionaryPlane(
            rows=mirror_rows, truth=mirror_truth, asset="SI", open_ns=open_ns,
            duration_sec=1_000, raw_tick=1, multiplier=5_000,
            event_state_flags=mirror_flags)
        kwargs = dict(
            snapshot_ts_ns=open_ns + 355 * 1_000_000_000,
            current_bid=100, current_ask=101, current_mid2=201,
            formation_candidate=candidate)
        up = long.feature_map(side=1, **kwargs)
        down = short.feature_map(side=-1, **kwargs)
        for name in (
                "disc_memory_z2_attack_volume",
                "disc_memory_z2_lift_volume",
                "disc_memory_z2_signed_control_fraction",
                "disc_level_z2_defense_reload_count",
                "disc_state_current_displacement_ticks",
                "disc_state_adverse_max_ticks",
                "disc_state_favorable_max_ticks",
                "disc_state_reclaim_seen", "disc_state_lift_seen",
                "disc_state_retest_seen",
                "disc_absorption_attack_per_adverse_tick",
                "disc_path_failed_auction_reentry",
                "disc_path_ofm_retest_complete",
                "disc_eclock_n64_defense_commitment",
                "disc_eclock_n64_aligned_size_imbalance_mean",
                "disc_eclock_n64_size_count_divergence",
                "disc_tclock_n32_aligned_flow_fraction",
                "disc_tclock_n32_current_run_control",
                "disc_tclock_n32_aligned_displacement_ticks",
                "disc_vclock_v64_aligned_flow_fraction",
                "disc_tape_h30_aligned_flow_mean_per_sec",
                "disc_test_response_h1_favorable_mean_ticks",
                "disc_quote_formation_defense_at_formation_time_fraction",
                "disc_quote_formation_defense_best_aligned_ticks_mean",
                "disc_quote_formation_depletion_count",
                "disc_quote_formation_rebuild_count",
                "disc_behavior_control_evidence_balance"):
            self.assertAlmostEqual(up[name], down[name], msg=name)

    def test_volume_scale_preserves_ratios_and_scales_absolute_effort(self) -> None:
        rows, truth, flags, candidate, open_ns = _fixture(include_future=False)
        scaled_rows = rows.copy()
        scaled_rows["size"] *= 7
        scaled_rows["bid_sz"] *= 7
        scaled_rows["ask_sz"] *= 7
        base = CausalDiscretionaryPlane(
            rows=rows, truth=truth, asset="SI", open_ns=open_ns,
            duration_sec=1_000, raw_tick=1, multiplier=5_000,
            event_state_flags=flags)
        scaled = CausalDiscretionaryPlane(
            rows=scaled_rows, truth=truth, asset="SI", open_ns=open_ns,
            duration_sec=1_000, raw_tick=1, multiplier=5_000,
            event_state_flags=flags)
        kwargs = dict(
            snapshot_ts_ns=open_ns + 355 * 1_000_000_000,
            current_bid=100, current_ask=101, current_mid2=201,
            side=1, formation_candidate=candidate)
        small = base.feature_map(**kwargs)
        large = scaled.feature_map(**kwargs)
        self.assertEqual(
            large["disc_memory_z2_attack_volume"],
            7.0 * small["disc_memory_z2_attack_volume"])
        self.assertEqual(
            large["disc_memory_z2_lift_volume"],
            7.0 * small["disc_memory_z2_lift_volume"])
        self.assertAlmostEqual(
            large["disc_memory_z2_attack_fraction"],
            small["disc_memory_z2_attack_fraction"])
        self.assertAlmostEqual(
            large["disc_memory_z2_signed_control_fraction"],
            small["disc_memory_z2_signed_control_fraction"])
        self.assertEqual(
            large["disc_tclock_n32_volume"],
            7.0 * small["disc_tclock_n32_volume"])
        self.assertAlmostEqual(
            large["disc_tclock_n32_aligned_flow_fraction"],
            small["disc_tclock_n32_aligned_flow_fraction"])
        self.assertAlmostEqual(
            large["disc_tclock_n32_size_hhi"],
            small["disc_tclock_n32_size_hhi"])
        self.assertEqual(
            large["disc_eclock_n64_defense_average_order_size"],
            7.0 * small["disc_eclock_n64_defense_average_order_size"])
        self.assertAlmostEqual(
            large["disc_eclock_n64_aligned_size_imbalance_mean"],
            small["disc_eclock_n64_aligned_size_imbalance_mean"])
        self.assertEqual(
            large["disc_state_current_displacement_ticks"],
            small["disc_state_current_displacement_ticks"])

    def test_adaptive_clocks_expose_support_and_tape_speed(self) -> None:
        plane, candidate, open_ns = _plane(include_future=False)
        values = plane.feature_map(
            snapshot_ts_ns=open_ns + 355 * 1_000_000_000,
            current_bid=100, current_ask=101, current_mid2=201,
            side=1, formation_candidate=candidate)
        self.assertGreater(values["disc_eclock_n16_support_count"], 0.0)
        self.assertGreater(values["disc_tclock_n8_support_count"], 0.0)
        self.assertGreater(values["disc_vclock_v64_support_fraction"], 0.0)
        self.assertGreaterEqual(values["disc_tape_h30_event_active_second_fraction"], 0.0)
        self.assertLessEqual(values["disc_tape_h30_event_active_second_fraction"], 1.0)
        self.assertGreaterEqual(values["disc_tclock_n8_size_hhi"], 0.0)
        self.assertLessEqual(values["disc_tclock_n8_size_hhi"], 1.0)

    def test_prior_present_and_absent_have_identical_schema_order(self) -> None:
        rows, _truth, _flags, candidate, open_ns = _fixture(
            include_future=False)
        prior = PriorSessionContext(
            rows=rows, asset="SI", trading_day=20210103,
            event_pack_sha256="a" * 64, raw_tick=1, multiplier=5_000)
        absent, _candidate, _open_ns = _plane(include_future=False)
        present, _candidate, _open_ns = _plane(
            include_future=False, prior=prior)
        kwargs = dict(
            snapshot_ts_ns=open_ns + 355 * 1_000_000_000,
            current_bid=100, current_ask=101, current_mid2=201,
            side=1, formation_candidate=candidate)
        empty = absent.feature_map(**kwargs)
        full = present.feature_map(**kwargs)
        self.assertEqual(tuple(empty), tuple(full))
        self.assertEqual(empty["disc_prior_present"], 0.0)
        self.assertEqual(full["disc_prior_present"], 1.0)
        self.assertGreater(full["disc_prior_level_z2_trade_volume"], 0.0)

    def test_level_destruction_also_breaks_prior_price_memory(self) -> None:
        rows, _truth, _flags, _candidate, _open_ns = _fixture(
            include_future=False)
        prior = PriorSessionContext(
            rows=rows, asset="SI", trading_day=20210103,
            event_pack_sha256="c" * 64, raw_tick=1, multiplier=5_000)
        kwargs = dict(
            current_mid2=201, formation_bid=100, formation_ask=101, side=1)
        real = prior.feature_map(**kwargs)
        destroyed = prior.feature_map(
            **kwargs, level_association_mode="LEVEL_ASSOCIATION_DESTROYED")
        self.assertGreater(real["disc_prior_level_z2_trade_volume"], 0.0)
        self.assertNotEqual(
            real["disc_prior_level_z2_trade_volume"],
            destroyed["disc_prior_level_z2_trade_volume"])

    def test_fill_coupling_mode_cannot_change_prior_price_memory(self) -> None:
        rows, _truth, _flags, _candidate, _open_ns = _fixture(
            include_future=False)
        prior = PriorSessionContext(
            rows=rows, asset="SI", trading_day=20210103,
            event_pack_sha256="d" * 64, raw_tick=1, multiplier=5_000)
        kwargs = dict(
            current_mid2=201, formation_bid=100, formation_ask=101, side=1)
        real = prior.feature_map(**kwargs)
        fill = prior.feature_map(
            **kwargs, level_association_mode="FILL_COUPLING_DESTROYED")
        self.assertEqual(tuple(real), tuple(fill))
        for name in real:
            self.assertEqual(real[name], fill[name], name)

    def test_nanosecond_order_separates_equal_one_second_marginals(self) -> None:
        open_ns = 2_000_000_000_000
        candidate = {
            "decision_sec": "100",
            "decision_ts_ns": str(open_ns + 100 * 1_000_000_000),
            "entry_mid2": "201", "entry_bid_px": "100",
            "entry_ask_px": "101", "phase_open_utc": "2000",
        }
        def build(offsets):
            rows = np.zeros(1 + len(offsets), dtype=EVENT_DTYPE)
            events = [(100, 1, "M", "B")] + [
                (101, value, "T", "A") for value in offsets]
            for index, (second, offset, action, side) in enumerate(events):
                timestamp = open_ns + second * 1_000_000_000 + offset
                rows[index]["ts_recv_ns"] = timestamp
                rows[index]["ts_event_ns"] = timestamp - 10
                rows[index]["price"] = 100
                rows[index]["bid_px"] = 100
                rows[index]["ask_px"] = 101
                rows[index]["size"] = 5
                rows[index]["receive_session_sec"] = second
                rows[index]["action"] = ord(action)
                rows[index]["side"] = ord(side)
            truth = {
                "trusted_message": np.ones(len(rows), bool),
                "trusted_economic": np.ones(len(rows), bool),
                "mid2": np.full(len(rows), 201, np.int64),
            }
            flags = {name: np.zeros(len(rows), np.int64) for name in (
                "bid_reload", "ask_reload", "bid_pull_no_fill",
                "ask_pull_no_fill", "bid_reload_latency_ns",
                "ask_reload_latency_ns", "bid_pull_lifetime_ns",
                "ask_pull_lifetime_ns")}
            return CausalDiscretionaryPlane(
                rows=rows, truth=truth, asset="SI", open_ns=open_ns,
                duration_sec=700, raw_tick=1, multiplier=5_000,
                event_state_flags=flags)
        clustered = build((10_000_000, 20_000_000, 30_000_000))
        dispersed = build((10_000_000, 400_000_000, 900_000_000))
        kwargs = dict(
            snapshot_ts_ns=open_ns + 102 * 1_000_000_000,
            current_bid=100, current_ask=101, current_mid2=201,
            side=1, formation_candidate=candidate)
        fast = clustered.feature_map(**kwargs)
        slow = dispersed.feature_map(**kwargs)
        self.assertEqual(
            fast["disc_evt_h5_attack_event_count"],
            slow["disc_evt_h5_attack_event_count"])
        self.assertEqual(
            fast["disc_evt_h5_attack_volume"],
            slow["disc_evt_h5_attack_volume"])
        self.assertGreater(
            fast["disc_evt_h5_attack_peak_100ms"],
            slow["disc_evt_h5_attack_peak_100ms"])
        self.assertLess(
            fast["disc_evt_h5_attack_gap_median_ms"],
            slow["disc_evt_h5_attack_gap_median_ms"])

    def test_absent_and_present_profiles_have_identical_schema_order(self) -> None:
        plane, candidate, open_ns = _plane(include_future=False)
        # Use a formation time before the first complete five-minute profile
        # solely to exercise the absent branch.
        early_candidate = dict(
            candidate, decision_sec="100",
            decision_ts_ns=str(open_ns + 100 * 1_000_000_000))
        early = plane.feature_map(
            snapshot_ts_ns=open_ns + 200 * 1_000_000_000,
            current_bid=100, current_ask=101, current_mid2=201,
            side=1, formation_candidate=early_candidate)
        late = plane.feature_map(
            snapshot_ts_ns=open_ns + 600 * 1_000_000_000,
            current_bid=100, current_ask=101, current_mid2=201,
            side=1, formation_candidate=candidate)
        self.assertEqual(tuple(early), tuple(late))

    def test_future_rows_cannot_change_a_prefix_feature(self) -> None:
        full, candidate, open_ns = _plane(include_future=True)
        truncated, _candidate, _open_ns = _plane(include_future=False)
        kwargs = dict(
            snapshot_ts_ns=open_ns + 600 * 1_000_000_000,
            current_bid=100, current_ask=101, current_mid2=201,
            side=1, formation_candidate=candidate)
        observed = full.feature_map(**kwargs)
        expected = truncated.feature_map(**kwargs)
        self.assertEqual(tuple(observed), tuple(expected))
        for name in observed:
            self.assertAlmostEqual(observed[name], expected[name], msg=name)

    def test_level_destruction_preserves_metric_marginals(self) -> None:
        real, _candidate, _open_ns = _plane(include_future=True)
        destroyed, _candidate, _open_ns = _plane(
            include_future=True, mode="LEVEL_ASSOCIATION_DESTROYED")
        real_total = np.sum([
            ledger.cumulative[-1] for ledger in real._ledger.values()
        ], axis=0)
        destroyed_total = np.sum([
            ledger.cumulative[-1] for ledger in destroyed._ledger.values()
        ], axis=0)
        self.assertTrue(np.array_equal(real_total, destroyed_total))

    def test_level_destruction_breaks_candidate_price_association(self) -> None:
        real, candidate, open_ns = _plane(include_future=False)
        destroyed, _candidate, _open_ns = _plane(
            include_future=False, mode="LEVEL_ASSOCIATION_DESTROYED")
        kwargs = dict(
            snapshot_ts_ns=open_ns + 355 * 1_000_000_000,
            current_bid=100, current_ask=101, current_mid2=201,
            side=1, formation_candidate=candidate)
        actual = real.feature_map(**kwargs)
        null = destroyed.feature_map(**kwargs)
        self.assertGreater(actual["disc_memory_z0_attack_volume"], 0.0)
        self.assertEqual(null["disc_memory_z0_attack_volume"], 0.0)
        self.assertEqual(actual["disc_level_association_destroyed"], 0.0)
        self.assertEqual(null["disc_level_association_destroyed"], 1.0)

    def test_ordered_candidate_state_encodes_defense_reclaim_lift_retest(self) -> None:
        plane, candidate, open_ns = _plane(include_future=False)
        values = plane.feature_map(
            snapshot_ts_ns=open_ns + 355 * 1_000_000_000,
            current_bid=100, current_ask=101, current_mid2=201,
            side=1, formation_candidate=candidate)
        self.assertEqual(values["disc_state_adverse_seen"], 1.0)
        self.assertEqual(values["disc_state_reclaim_seen"], 1.0)
        self.assertEqual(values["disc_state_lift_seen"], 1.0)
        self.assertEqual(values["disc_state_retest_seen"], 1.0)
        self.assertEqual(values["disc_state_invalidated_seen"], 0.0)

    def test_completed_profile_exposes_location_without_future_volume(self) -> None:
        plane, candidate, open_ns = _plane(include_future=True)
        values = plane.feature_map(
            snapshot_ts_ns=open_ns + 600 * 1_000_000_000,
            current_bid=100, current_ask=101, current_mid2=201,
            side=1, formation_candidate=candidate)
        self.assertEqual(values["disc_auction_session_present"], 1.0)
        self.assertEqual(values["disc_auction_session_age_sec"], 0.0)
        self.assertGreater(values["disc_auction_session_poc_volume_fraction"], 0.0)
        self.assertGreaterEqual(values["disc_auction_session_range_position"], 0.0)
        self.assertLessEqual(values["disc_auction_session_range_position"], 1.0)


if __name__ == "__main__":
    unittest.main()
