from __future__ import annotations

import unittest
import numpy as np

from engine.entry_v2.diagnostic_catboost import (
    DiagnosticCatBoostRefusal, FrozenRepresentationRows, RankerAvailability,
    exact_pair_manifest, fit_diagnostic_catboost, rehearse_catboost_competence,
)


def _known_rows(*, groups: int = 40, test_groups: int = 0,
                explicit_pairs: bool = True) -> FrozenRepresentationRows:
    rng = np.random.default_rng(20260816)
    representations = []; candidates = []; assets = []; days = []
    decisions = []; targets = []; group_ids = []; splits = []
    for asset_number, asset in enumerate(("HG", "NKD", "SI")):
        for group in range(groups + test_groups):
            label_pair = (0, 1)
            for member, label in enumerate(label_pair):
                vector = rng.normal(0, .02, 8)
                vector[0] = -12.0 if label == 0 else 12.0
                vector[1] = asset_number
                representations.append(vector)
                candidates.append(f"{asset}-{group:03d}-{member}")
                assets.append(asset)
                days.append(20210601 + group // 4 if group < groups else 20211101)
                decisions.append(group * 1000)
                targets.append(label)
                group_ids.append(f"g{group}" if explicit_pairs else f"singleton-{member}-{group}")
                splits.append("FIT" if group < groups else "TEST")
    return FrozenRepresentationRows(
        np.asarray(representations, np.float32), np.asarray(candidates), np.asarray(assets),
        np.asarray(days), np.asarray(decisions, np.int64), np.asarray(targets, np.int8),
        np.ones(len(targets), bool), np.asarray(group_ids), np.asarray(splits),
    )


class DiagnosticCatBoostTest(unittest.TestCase):
    def test_exact_pair_manifest_and_competence(self):
        rows = _known_rows()
        manifest = exact_pair_manifest(rows, "SI")
        self.assertEqual(manifest.group_count, 40)
        self.assertEqual(len(manifest.pairs), 40)
        self.assertEqual(len(manifest.pair_weights), 40)
        self.assertTrue(all(weight > 0 for weight in manifest.pair_weights))
        result = rehearse_catboost_competence(
            rows, expected_representation_sha256=rows.representation_sha256,
        )
        self.assertGreaterEqual(min(result.auroc_by_asset.values()), .995)
        self.assertLessEqual(max(result.bce_by_asset.values()), .02)
        self.assertGreaterEqual(min(result.pair_accuracy_by_asset.values()), .995)
        np.testing.assert_array_equal(result.candidate_id, rows.candidate_id)
        self.assertEqual(result.action_probability.shape, (len(rows.candidate_id),))
        self.assertFalse(result.action_probability.flags.writeable)
        self.assertEqual(set(result.pair_group_count_by_asset.values()), {40})
        self.assertEqual(len(result.row_manifest_sha256), 64)

    def test_singletons_never_become_day_pseudo_groups(self):
        rows = _known_rows(explicit_pairs=False)
        # Even though all candidates share only ten days, explicit IDs are singleton.
        self.assertEqual(exact_pair_manifest(rows, "HG").group_count, 0)
        fit = fit_diagnostic_catboost(
            rows, expected_representation_sha256=rows.representation_sha256,
        )
        self.assertTrue(np.all(np.isfinite(fit.action_probability)))
        self.assertTrue(all(value.ranker_availability == RankerAvailability.UNAVAILABLE_LOW_SUPPORT
                            for value in fit.assets.values()))

    def test_rehearsal_uses_all_real_day_phase_groups_without_inventing_forty(self):
        rows = _known_rows(groups=32)
        fit = fit_diagnostic_catboost(
            rows, expected_representation_sha256=rows.representation_sha256,
            minimum_pair_groups_per_asset=1,
        )
        self.assertEqual(
            {asset: row.pair_manifest.group_count
             for asset, row in fit.assets.items()},
            {"HG": 32, "NKD": 32, "SI": 32},
        )
        self.assertTrue(all(row.ranker_availability is RankerAvailability.MATERIALIZED
                            for row in fit.assets.values()))

    def test_test_target_mutation_and_representation_hash_refusal(self):
        rows = _known_rows(groups=32, test_groups=8)
        one = fit_diagnostic_catboost(
            rows, expected_representation_sha256=rows.representation_sha256,
        )
        changed_target = np.asarray(rows.action_target).copy()
        changed_target[rows.frozen_split() == "HELD_FORWARD"] ^= 1
        changed = FrozenRepresentationRows(
            rows.representation, rows.candidate_id, rows.asset, rows.day,
            rows.decision_ts_ns, changed_target, rows.action_loss_mask,
            rows.exact_time_group_id, rows.split,
        )
        two = fit_diagnostic_catboost(
            changed, expected_representation_sha256=rows.representation_sha256,
        )
        self.assertEqual(one.canonical_order_sha256, two.canonical_order_sha256)
        self.assertEqual([one.assets[a].action_model_sha256 for a in ("HG", "NKD", "SI")],
                         [two.assets[a].action_model_sha256 for a in ("HG", "NKD", "SI")])
        with self.assertRaisesRegex(DiagnosticCatBoostRefusal, "representation hash"):
            fit_diagnostic_catboost(rows, expected_representation_sha256="0" * 64)


if __name__ == "__main__":
    unittest.main()
