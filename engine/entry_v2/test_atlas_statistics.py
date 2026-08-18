from __future__ import annotations

import unittest
import numpy as np

from scipy.stats import norm
from scipy.stats import t as student_t

from engine.entry_v2.atlas_statistics import (
    AtlasStatisticsRefusal, FitLedgerRecord, PairedObservationRecord,
    PairedTestState, SupportKind, SupportState, e1_fit_count,
    hierarchical_holm, holm_rejections, holm_rejections_with_ledger,
    nonredundant_finalists, paired_day_cluster_records, paired_day_cluster_test,
    romano_wolf_lower_bounds, support_gate,
    through_e2_fit_count, validate_fit_ledger,
)


class AtlasStatisticsTest(unittest.TestCase):
    def test_exact_support_boundaries(self):
        asset = np.repeat(["HG", "NKD", "SI"], [200, 200, 100])
        values = np.arange(500, dtype=float)
        uncensored = np.zeros(500, bool)
        self.assertTrue(support_gate(SupportKind.CONTINUOUS, asset=asset, values=values,
                                     censored=uncensored).available)
        self.assertFalse(support_gate(SupportKind.CONTINUOUS, asset=asset[:-1],
                                      values=values[:-1],
                                      censored=uncensored[:-1]).available)
        # C6: the quota counts uncensored rows, not merely finite ones.  One
        # censored SI row drops the per-asset census below its floor.
        one_censored = uncensored.copy(); one_censored[-1] = True
        self.assertFalse(support_gate(SupportKind.CONTINUOUS, asset=asset,
                                      values=values, censored=one_censored).available)
        with self.assertRaises(AtlasStatisticsRefusal):
            support_gate(SupportKind.CONTINUOUS, asset=asset, values=values)
        cls_asset = np.repeat(["HG", "NKD", "SI"], 400)
        classes = np.tile(np.repeat([0, 1], 200), 3)
        self.assertTrue(support_gate(SupportKind.BINARY_ORDINAL, asset=cls_asset,
                                     values=classes, required_levels=[0, 1]).available)
        causes = classes.copy()
        self.assertEqual(support_gate(SupportKind.COMPETING_CAUSE, asset=cls_asset,
                                      values=causes, required_levels=[0, 1]).state,
                         SupportState.MATERIALIZED)
        rank_asset = np.repeat(["HG", "NKD", "SI"], [240, 80, 80])
        rank_groups = np.repeat(np.arange(200), 2)
        rank_day = np.repeat(np.arange(200), 2)
        rank_ts = np.repeat(np.arange(200, dtype=np.int64) + 1_000, 2)
        self.assertTrue(support_gate(SupportKind.EXACT_TIME_RANKING, asset=rank_asset,
                                     group_id=rank_groups, day=rank_day,
                                     decision_ts=rank_ts).available)
        econ_asset = np.repeat(["HG", "NKD", "SI"], 60)
        econ_day = np.tile(np.arange(60), 3)
        self.assertTrue(support_gate(SupportKind.ECONOMIC, asset=econ_asset, day=econ_day).available)
        self.assertFalse(support_gate(SupportKind.ECONOMIC, asset=econ_asset[:-1], day=econ_day[:-1]).available)

        # Pooled variation cannot hide a constant per-asset target.
        constant_si = values.copy()
        constant_si[asset == "SI"] = 7.0
        self.assertFalse(support_gate(
            SupportKind.CONTINUOUS, asset=asset, values=constant_si,
            censored=uncensored,
        ).available)

        # Reusing the same group label on different clocks is not a deployed
        # exact-time choice set.
        with self.assertRaises(AtlasStatisticsRefusal):
            support_gate(SupportKind.EXACT_TIME_RANKING, asset=rank_asset,
                         group_id=rank_groups)

    def test_paired_cluster_and_holm(self):
        records = tuple(
            PairedObservationRecord(f"{asset}-{day}", asset, day, True,
                                    "a" * 64, "b" * 64, real, 1.0)
            for asset, day, real in zip(("HG", "NKD", "SI", "HG", "NKD", "SI"),
                                        ("d1", "d1", "d1", "d2", "d2", "d2"),
                                        (2., 3., 4., 5., 6., 7.))
        )
        result = paired_day_cluster_records(records)
        self.assertGreater(result.mean_difference, 0)
        self.assertEqual(result.n_day_clusters, 2)
        self.assertEqual(holm_rejections({"a": .01, "b": .03, "c": .2}), ("a",))
        hh = hierarchical_holm(
            {"a1": .001, "a2": .01, "b1": .2},
            {"a1": "a", "a2": "a", "b1": "b"},
        )
        self.assertEqual(hh.surviving_families, ("a",))
        self.assertEqual(set(hh.surviving_probes), {"a1", "a2"})

        # Candidate replication inside one asset-day must not change the
        # equal-asset-day estimand.
        replicated = records + tuple(
            PairedObservationRecord(f"HG-d1-extra-{i}", "HG", "d1", True,
                                    "a" * 64, "b" * 64, 2.0, 1.0)
            for i in range(20)
        )
        balanced = paired_day_cluster_records(replicated)
        self.assertAlmostEqual(balanced.mean_difference,
                               result.mean_difference)

    def test_paired_p_value_uses_student_t_on_day_cluster_degrees_of_freedom(self):
        # S1: the sole engine-wide p-value site is Student-t on G-1, not normal.
        real = [2.0, 3.5, 4.0, 5.5, 3.0]
        day = ["d1", "d2", "d3", "d4", "d5"]
        result = paired_day_cluster_test(real, [1.0] * 5, day)
        self.assertIs(result.state, PairedTestState.MATERIALIZED)
        self.assertEqual(result.n_day_clusters, 5)
        self.assertAlmostEqual(
            result.p_value_one_sided,
            float(student_t.sf(result.t_statistic, result.n_day_clusters - 1)),
            places=15,
        )
        self.assertGreater(result.p_value_one_sided,
                           float(norm.sf(result.t_statistic)))

    def test_degenerate_and_low_support_paired_tests_are_typed_never_p_values(self):
        # S2: a constant positive paired column has se == 0.  It must never
        # become p = 0.0 and win Holm at any alpha.
        constant = paired_day_cluster_test([2.0, 2.0, 2.0], [1.0, 1.0, 1.0],
                                           ["d1", "d2", "d3"])
        self.assertIs(constant.state, PairedTestState.DEGENERATE_ZERO_VARIANCE)
        self.assertIsNone(constant.p_value_one_sided)
        self.assertIsNone(constant.t_statistic)
        # The already-covered all-zero column stays typed too.
        zero = paired_day_cluster_test([1.0, 1.0], [1.0, 1.0], ["d1", "d2"])
        self.assertIs(zero.state, PairedTestState.DEGENERATE_ZERO_VARIANCE)
        self.assertIsNone(zero.p_value_one_sided)
        # S3: G = 1 is typed UNAVAILABLE_LOW_SUPPORT and retained in the
        # ledger; it must not abort the surrounding 44-objective screen.
        single = paired_day_cluster_test([2.0, 3.0], [1.0, 1.0], ["d1", "d1"])
        self.assertIs(single.state, PairedTestState.UNAVAILABLE_LOW_SUPPORT)
        self.assertIsNone(single.p_value_one_sided)
        self.assertEqual(single.n_day_clusters, 1)

        accepted, skipped = holm_rejections_with_ledger({
            "a": .01,
            "degenerate": PairedTestState.DEGENERATE_ZERO_VARIANCE,
            "thin": PairedTestState.UNAVAILABLE_LOW_SUPPORT,
        })
        self.assertEqual(accepted, ("a",))
        self.assertEqual(dict(skipped), {
            "degenerate": "DEGENERATE_ZERO_VARIANCE",
            "thin": "UNAVAILABLE_LOW_SUPPORT",
        })
        self.assertEqual(holm_rejections({"a": .01, "z": constant}), ("a",))
        hierarchy = hierarchical_holm(
            {"a1": .001, "a2": .01, "b1": single},
            {"a1": "a", "a2": "a", "b1": "b"},
        )
        self.assertEqual(hierarchy.excluded_probes, ("b1",))
        self.assertNotIn("b1", hierarchy.surviving_probes)
        self.assertEqual(hierarchy.surviving_families, ("a",))

    def test_dedup_and_deterministic_max_t(self):
        ids = ("a", "b", "c", "d", "e")
        corr = np.eye(5)
        corr[0, 1] = corr[1, 0] = 1
        selected = nonredundant_finalists(
            ids, target_correlation=corr,
            target_hashes={"a": "x", "b": "y", "c": "z", "d": "z", "e": "q"},
        )
        self.assertEqual(selected.finalists, ("a", "c", "e"))
        self.assertEqual(len(selected.correlation_sha256), 64)
        rng = np.random.default_rng(7)
        x = rng.normal(.5, .2, size=(80, 6))
        hypothesis_ids = tuple(f"{probe}:{asset}" for probe in ("a", "c")
                               for asset in ("HG", "NKD", "SI"))
        hypothesis_assets = ("HG", "NKD", "SI") * 2
        one = romano_wolf_lower_bounds(
            x, resamples=512, hypothesis_ids=hypothesis_ids,
            hypothesis_assets=hypothesis_assets,
            hypothesis_families=("a",) * 3 + ("c",) * 3,
        )
        two = romano_wolf_lower_bounds(
            x, resamples=512, hypothesis_ids=hypothesis_ids,
            hypothesis_assets=hypothesis_assets,
            hypothesis_families=("a",) * 3 + ("c",) * 3,
        )
        np.testing.assert_array_equal(one.simultaneous_lower_bounds, two.simultaneous_lower_bounds)
        self.assertEqual(one.receipt_sha256, two.receipt_sha256)
        marginal = x.mean(0) - 1.6448536269514722 * x.std(0, ddof=1) / np.sqrt(len(x))
        self.assertTrue(np.all(one.simultaneous_lower_bounds <= marginal + 1e-12))

        x30 = rng.normal(.3, .4, size=(80, 30))
        ids30 = tuple(f"path-{i // 3}:{asset}" for i, asset in enumerate(
            ("HG", "NKD", "SI") * 10))
        assets30 = ("HG", "NKD", "SI") * 10
        base = romano_wolf_lower_bounds(
            x30, resamples=128, hypothesis_ids=ids30,
            hypothesis_assets=assets30,
            hypothesis_families=tuple(f"path-{i // 3}" for i in range(30)))
        order = np.random.default_rng(11).permutation(30)
        permuted = romano_wolf_lower_bounds(
            x30[:, order], resamples=128,
            hypothesis_ids=tuple(ids30[i] for i in order),
            hypothesis_assets=tuple(assets30[i] for i in order),
            hypothesis_families=tuple(f"path-{i // 3}" for i in order))
        inverse = np.argsort(order)
        np.testing.assert_allclose(
            base.simultaneous_lower_bounds,
            permuted.simultaneous_lower_bounds[inverse], rtol=0.0, atol=3e-16)
        with self.assertRaises(AtlasStatisticsRefusal):
            romano_wolf_lower_bounds(
                rng.normal(size=(80, 33)), resamples=16,
                hypothesis_ids=tuple(f"h{i}" for i in range(33)),
                hypothesis_assets=("HG", "NKD", "SI") * 11,
                hypothesis_families=tuple(f"h{i // 3}" for i in range(33)))

        # Typed losers remain in the exact 30-hypothesis family without a
        # divide-by-zero; capture ids retain a suffix after the asset token.
        mixed = x30.copy(); mixed[:, -3:] = 0.0
        capture_ids = tuple(f"path-{i // 3}:{asset}:capture"
                            for i, asset in enumerate(assets30))
        families30 = tuple(f"path-{i // 3}" for i in range(30))
        zero = romano_wolf_lower_bounds(
            mixed, resamples=128, hypothesis_ids=capture_ids,
            hypothesis_assets=assets30,
            hypothesis_families=families30)
        # S5: a zero-variance column carries no uncertainty and is therefore
        # ineligible for selection; its simultaneous bound is -inf.
        self.assertTrue(np.all(np.isneginf(zero.simultaneous_lower_bounds[-3:])))
        np.testing.assert_array_equal(zero.stochastic_mask[-3:], False)
        np.testing.assert_array_equal(zero.eligible_mask[-3:], False)
        self.assertEqual(zero.column_states[-3:],
                         ("DEGENERATE_ZERO_VARIANCE",) * 3)
        self.assertEqual(len(zero.hypothesis_ids), 30)

        # The measured defect: a CONSTANT POSITIVE column also has se == 0 and
        # previously passed selection with zero uncertainty at lower=estimate.
        constant = x30.copy(); constant[:, -3:] = 0.75
        positive = romano_wolf_lower_bounds(
            constant, resamples=128, hypothesis_ids=capture_ids,
            hypothesis_assets=assets30, hypothesis_families=families30)
        np.testing.assert_array_equal(positive.estimates[-3:], 0.75)
        self.assertTrue(np.all(np.isneginf(
            positive.simultaneous_lower_bounds[-3:])))
        self.assertFalse(bool(positive.eligible_mask[-3:].any()))

        # All-degenerate gives critical = 0.0; no column may become selectable.
        all_constant = np.full((80, 3), 0.75)
        degenerate = romano_wolf_lower_bounds(
            all_constant, resamples=128,
            hypothesis_ids=("only:HG", "only:NKD", "only:SI"),
            hypothesis_assets=("HG", "NKD", "SI"),
            hypothesis_families=("only",) * 3)
        self.assertEqual(degenerate.max_t_critical_value, 0.0)
        self.assertTrue(np.all(np.isneginf(
            degenerate.simultaneous_lower_bounds)))
        self.assertFalse(bool(degenerate.eligible_mask.any()))

    def test_fit_accounting(self):
        self.assertEqual(e1_fit_count(), 90)
        self.assertEqual(through_e2_fit_count(4), 98)
        artifact = "c" * 64
        records = []
        records.extend(FitLedgerRecord(f"pretext-{i}", "E1_PRETEXT", "FIT", artifact,
                                       ("C01P01", "C02P01")[i])
                       for i in range(2))
        records.extend(FitLedgerRecord(f"real-{i}", "E1_REAL", "FIT", artifact)
                       for i in range(44))
        records.extend(FitLedgerRecord(f"twin-{i}", "E1_TWIN", "FIT", artifact)
                       for i in range(44))
        records.extend(FitLedgerRecord(f"e2-real-{i}", "E2_REAL", "FIT", artifact)
                       for i in range(4))
        records.extend(FitLedgerRecord(f"e2-twin-{i}", "E2_TWIN", "FIT", artifact)
                       for i in range(4))
        records.append(FitLedgerRecord("competence-0", "COMPETENCE", "FIT", artifact))
        ledger = validate_fit_ledger(records, finalist_count=4)
        self.assertEqual(ledger.through_e2_optimizer_fits, 98)
        self.assertEqual(ledger.discarded_competence_fits, 1)
        with self.assertRaises(AtlasStatisticsRefusal):
            e1_fit_count(43, 44, 2)
        with self.assertRaises(AtlasStatisticsRefusal):
            through_e2_fit_count(5)


if __name__ == "__main__":
    unittest.main()
