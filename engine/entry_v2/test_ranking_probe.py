from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

import numpy as np

from .contracts import CausalEntryExample, EntryScore, RawPrefixRef, SessionRef, Side
from .ranking_probe import (
    RankerConfig, _save_model, feature_matrix, fit_ranker,
    hindsight_test_diagnostic, predict_ranker, prepare_ranking_pool,
)
from .representation_probe import (
    MonotonePlatt, ProbeRows, _sha256_array, _split_score_diagnostics,
    normalize_from_fit, select_thresholds, split_rows,
)
from .replay import ReplayOutcome, ScoredArrival


TEST_CONFIG = RankerConfig(iterations=24, depth=4, learning_rate=0.12,
                           l2_leaf_reg=2.0, thread_count=2)


class TinyFold:
    pass


def _example(cid: str, asset: str, day: int, timestamp: int) -> CausalEntryExample:
    return CausalEntryExample(
        cid, asset, day, f"{asset}-{day}", timestamp, Side.LONG, "P", 1,
        RawPrefixRef("fixture", 0, 0, 0, None, None, "0" * 64), {}, None, "1" * 64,
    )


def fixture() -> tuple[TinyFold, ProbeRows]:
    candidate_ids, assets, days, timestamps = [], [], [], []
    embedding, static = [], []
    action, mask, expected, top3, wall, mae = [], [], [], [], [], []
    arrivals = []
    counter = 10
    split_days = (20220701, 20221001, 20221101)
    for asset_index, asset in enumerate(("HG", "NKD", "SI")):
        for day_index, day in enumerate(split_days):
            for candidate in range(6):
                cid = f"{asset}-{day}-{candidate}"
                target = bool(candidate % 2)
                supervised = candidate != 5
                signal = 1.0 if target else -1.0
                candidate_ids.append(cid); assets.append(asset); days.append(day)
                timestamps.append(counter); counter += 2
                static.append((signal, candidate / 5.0, float(asset_index), 4.0))
                embedding.append((signal, signal * .5, candidate / 7.0,
                                  float(day_index), float(asset_index), -3.0))
                action.append(target); mask.append(supervised)
                pnl = 750.0 if target else -150.0
                expected.append(pnl); top3.append(float(target)); wall.append(float(not target))
                mae.append(100.0 if target else 900.0)
                example = _example(cid, asset, day, timestamps[-1])
                score = EntryScore(cid, asset, timestamps[-1], "fixture", 0.0, 0.0,
                    pnl, pnl, float(target), mae[-1], float(not target), False)
                outcome = ReplayOutcome(cid, timestamps[-1] + 1, pnl,
                                        timestamps[-1] + 1, pnl)
                arrivals.append(ScoredArrival(example, score, outcome))
    rows = ProbeRows(tuple(candidate_ids), tuple(assets), np.asarray(days),
        np.asarray(timestamps), np.asarray(embedding, dtype=np.float32),
        np.asarray(static, dtype=np.float32), np.asarray(action, dtype=bool),
        np.asarray(mask, dtype=bool), np.asarray(expected, dtype=np.float32),
        np.asarray(top3, dtype=np.float32), np.asarray(wall, dtype=np.float32),
        np.asarray(mae, dtype=np.float32))
    fold = TinyFold(); fold.assets = rows.assets; fold.truth_arrivals = tuple(arrivals)
    fold.expected_sessions = tuple(SessionRef(asset, day, f"{asset}-{day}")
        for asset in ("HG", "NKD", "SI") for day in split_days)
    return fold, rows


def decision(rows: ProbeRows, fold: TinyFold):
    splits = split_rows(rows, min_supervised_rows=2)
    normalized, normalization = normalize_from_fit(rows, splits["fit"])
    features = feature_matrix(normalized, "late_fusion")
    fitted = fit_ranker(normalized.take(splits["fit"]), features[splits["fit"]],
                        TEST_CONFIG)
    logits = {name: predict_ranker(fitted, features[indices])
              for name, indices in splits.items()}
    calibration = normalized.take(splits["calibration"])
    supervised = calibration.action_mask
    platt = MonotonePlatt.fit(logits["calibration"][supervised],
                              calibration.action[supervised])
    probabilities = {name: platt.predict(value) for name, value in logits.items()}
    thresholds, _funnel = select_thresholds(
        fold, splits["calibration"], probabilities["calibration"]
    )
    test = normalized.take(splits["test"])
    metrics = _split_score_diagnostics(test, logits["test"], probabilities["test"])
    canary = (_sha256_array(logits["fit"]), _sha256_array(logits["calibration"]),
              _sha256_array(logits["test"]), platt, tuple(sorted(thresholds.items())),
              normalization)
    return fitted, canary, metrics, probabilities, splits, normalized


class RankingProbeTest(unittest.TestCase):
    def test_real_pairlogit_pairs_are_positive_negative_and_group_local(self):
        _fold, rows = fixture()
        split = split_rows(rows, min_supervised_rows=2)
        normalized, _ = normalize_from_fit(rows, split["fit"])
        fit = normalized.take(split["fit"])
        prepared = prepare_ranking_pool(fit)
        self.assertEqual(prepared.group_count, 3)
        self.assertEqual(prepared.paired_group_count, 3)
        self.assertGreater(len(prepared.pairs), 0)
        for winner, loser in prepared.pairs:
            self.assertEqual(prepared.group_ids[winner], prepared.group_ids[loser])
            self.assertTrue(fit.action[prepared.indices[winner]])
            self.assertFalse(fit.action[prepared.indices[loser]])
        fitted = fit_ranker(fit, feature_matrix(fit, "static"), TEST_CONFIG)
        prediction = predict_ranker(fitted, feature_matrix(fit, "static"))
        self.assertGreater(prediction[fit.action].mean(), prediction[~fit.action].mean())

    def test_fit_only_and_test_label_mutation_leave_decision_artifacts_unchanged(self):
        fold, rows = fixture()
        first_model, first, first_metrics, _prob, splits, _normalized = decision(rows, fold)
        changed_action = rows.action.copy()
        # One masked fit label and every supervised test label are forbidden inputs.
        masked_fit = splits["fit"][~rows.action_mask[splits["fit"]]][0]
        changed_action[masked_fit] = ~changed_action[masked_fit]
        test_supervised = splits["test"][rows.action_mask[splits["test"]]]
        changed_action[test_supervised] = ~changed_action[test_supervised]
        changed = replace(rows, action=changed_action)
        second_model, second, second_metrics, _p2, _s2, _n2 = decision(changed, fold)
        self.assertEqual(first, second)
        np.testing.assert_array_equal(
            predict_ranker(first_model, feature_matrix(rows, "late_fusion")),
            predict_ranker(second_model, feature_matrix(rows, "late_fusion")),
        )
        self.assertNotEqual(first_metrics["global"]["raw"],
                            second_metrics["global"]["raw"])

    def test_deterministic_real_catboost_predictions_and_realized_model_hash(self):
        _fold, rows = fixture(); split = split_rows(rows, min_supervised_rows=2)
        normalized, _ = normalize_from_fit(rows, split["fit"])
        fit = normalized.take(split["fit"]); features = feature_matrix(fit, "embedding")
        first = fit_ranker(fit, features, TEST_CONFIG)
        second = fit_ranker(fit, features, TEST_CONFIG)
        np.testing.assert_array_equal(predict_ranker(first, features),
                                      predict_ranker(second, features))
        with tempfile.TemporaryDirectory() as directory:
            artifact = _save_model(first.model, Path(directory) / "model.cbm")
            self.assertEqual(len(artifact["sha256"]), 64)
            self.assertGreater(artifact["bytes"], 0)

    def test_hindsight_sweep_is_labeled_and_canonical_parity_checked(self):
        fold, rows = fixture()
        _model, _canary, _metrics, probabilities, splits, _normalized = decision(rows, fold)
        diagnostic = hindsight_test_diagnostic(
            fold, splits["test"], probabilities["test"]
        )
        self.assertEqual(diagnostic["label"], "HINDSIGHT_DIAGNOSTIC_ONLY")
        self.assertFalse(diagnostic["used_for_selected_policy"])
        for asset in ("HG", "NKD", "SI"):
            row = diagnostic["by_asset"][asset]
            self.assertEqual(row["threshold_count"], len(row["all_thresholds"]))
            self.assertEqual(len(row["fast_replay_parity_sha256"]), 64)
            self.assertIsNotNone(row["best_unconstrained"])


if __name__ == "__main__":
    unittest.main()
