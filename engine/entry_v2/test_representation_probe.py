from __future__ import annotations

from dataclasses import replace
import unittest

import numpy as np
import torch
import torch.nn.functional as F

from .contracts import CausalEntryExample, EntryScore, RawPrefixRef, SessionRef, Side
from .replay import ReplayOutcome, ScoredArrival
from . import teacher
from .representation_probe import (
    ASSETS, CrossAttentionBlock, LossWeights, MonotonePlatt, ProbeRows,
    RepresentationModel, _chronological_action_supervision,
    assert_fast_sweep_parity, decision_canary_sha256, depth_funnel,
    fast_threshold_sweep,
    normalize_from_fit, predict_logits, probe_loss, reconstruct_action_supervision,
    select_thresholds, split_rows, state_sha256, threshold_candidates,
    train_models, transport_receipt,
)
from .teacher import TeacherPath


def path(cid, asset, day, ts, exit_ts, value):
    return TeacherPath(cid, asset, day, ts, exit_ts, value, 0, 10, value < -899, 0)


def example(cid, asset, day, ts):
    return CausalEntryExample(cid, asset, day, f"{asset}-{day}", ts, Side.LONG,
        "P", 1, RawPrefixRef("f", 0, 0, 0, None, None, "0" * 64), {}, None, "1" * 64)


def arrival(p, take=False, probability=0.0):
    ex = example(p.candidate_id, p.asset, p.trading_day, p.decision_ts_ns)
    score = EntryScore(p.candidate_id, p.asset, p.decision_ts_ns, "truth", probability,
        float(take), p.cert_close_usd, p.cert_close_usd, 0, p.mae_usd,
        float(p.wall_hit), False)
    out = ReplayOutcome(p.candidate_id, p.exit_ts_ns, p.cert_close_usd,
                        p.exit_ts_ns, p.cert_close_usd)
    return ScoredArrival(ex, score, out)


def tiny_rows():
    days = np.asarray(([20220701] * 6 + [20221001] * 6 + [20221101] * 6) * 3)
    assets = tuple(asset for asset in ASSETS for _ in range(18))
    action = np.asarray(([0, 1] * 9) * 3, bool)
    rng = np.random.default_rng(7)
    embedding = rng.normal(size=(54, 5)).astype("f")
    static = rng.normal(size=(54, 3)).astype("f")
    embedding[:, -1] = 4.0
    static[:, -1] = -2.0
    return ProbeRows(tuple(f"c{i:03}" for i in range(54)), assets, days,
        np.arange(54) + 1, embedding, static, action, np.ones(54, bool),
        rng.normal(size=54).astype("f") * 1000, action.astype("f"),
        (~action).astype("f"), np.full(54, 100, dtype="f"))


class TinyFold:
    pass


def tiny_fold(rows):
    fold = TinyFold()
    fold.assets = rows.assets
    arrivals = []
    for i, (cid, asset, day, ts) in enumerate(zip(
            rows.candidate_ids, rows.assets, rows.days, rows.timestamps)):
        pnl = 700.0 if rows.action[i] else -100.0
        arrivals.append(arrival(path(cid, asset, int(day), int(ts), int(ts) + 1, pnl)))
    fold.truth_arrivals = tuple(arrivals)
    fold.expected_sessions = tuple(SessionRef(asset, day, f"{asset}-{day}")
        for asset in ASSETS for day in (20220701, 20221001, 20221101))
    return fold


def decision_artifacts(rows):
    splits = split_rows(rows, min_supervised_rows=2)
    normalized, _receipt = normalize_from_fit(rows, splits["fit"])
    fit = normalized.take(splits["fit"])
    model = train_models(fit, "static", batch_size=64, device="cpu")["standard"]
    cal_rows = normalized.take(splits["calibration"])
    logits = predict_logits(model, cal_rows, "cpu", 64)["action"]
    calibrator = MonotonePlatt.fit(logits[cal_rows.action_mask],
                                   cal_rows.action[cal_rows.action_mask])
    probabilities = calibrator.predict(logits)
    thresholds, _funnels = select_thresholds(
        tiny_fold(normalized), splits["calibration"], probabilities
    )
    return decision_canary_sha256(model, calibrator, thresholds)


class RepresentationProbeTest(unittest.TestCase):
    def test_teacher_identity_and_exact_mask_reconstruction(self):
        self.assertIs(_chronological_action_supervision,
                      teacher._chronological_action_supervision)
        rows = [path("equal-b", "SI", 20220701, 10, 20, 700),
                path("equal-a", "SI", 20220701, 10, 20, 800),
                path("occupied", "SI", 20220701, 20, 21, 900)]
        for asset in ("HG", "NKD"):
            for j, ts in enumerate((30, 40, 50)):
                rows.append(path(f"{asset}{j}", asset, 20220701, ts, ts + 1, 700 + j))
        rows += [path("si2", "SI", 20220701, 30, 31, 700),
                 path("si3", "SI", 20220701, 40, 41, 700),
                 path("asset-cap", "SI", 20220701, 50, 51, 900)]
        selected, supervised = teacher._chronological_action_supervision(tuple(rows))
        self.assertEqual(len(selected), 9)
        self.assertTrue({"equal-a", "equal-b"} <= supervised)
        self.assertNotIn("occupied", supervised)  # equal exit is still occupied
        self.assertNotIn("asset-cap", supervised)
        arrivals = tuple(arrival(p, p.candidate_id in selected) for p in rows)
        action, mask = reconstruct_action_supervision(
            arrivals, tuple(row.score for row in arrivals))
        ids = np.asarray([p.candidate_id for p in rows])
        self.assertEqual(set(ids[action]), selected)
        self.assertEqual(set(ids[mask]), supervised)

    def test_fit_only_normalization_split_refusal_and_constant_columns(self):
        rows = tiny_rows()
        splits = split_rows(rows, min_supervised_rows=2)
        normalized, receipt = normalize_from_fit(rows, splits["fit"])
        self.assertTrue(np.all(normalized.embeddings[:, -1] == 0))
        self.assertTrue(np.all(normalized.static_features[:, -1] == 0))
        self.assertAlmostEqual(float(normalized.embeddings[splits["fit"], 0].mean()), 0, places=6)
        changed = rows.embeddings.copy()
        changed[splits["test"], 0] += 1e6
        _, changed_receipt = normalize_from_fit(replace(rows, embeddings=changed), splits["fit"])
        self.assertEqual(receipt, changed_receipt)
        with self.assertRaisesRegex(Exception, "both classes"):
            split_rows(replace(rows, action=np.zeros_like(rows.action)),
                       min_supervised_rows=2)

    def test_head_shapes_identical_architecture_and_initial_bytes(self):
        receipts, head_hashes = [], []
        for kind, count in (("embedding", 4), ("static", 4), ("late_fusion", 8)):
            model = RepresentationModel(kind, 5, 3)
            output = model(torch.randn(2, 5), torch.randn(2, 3), torch.tensor([0, 2]))
            self.assertTrue(all(value.shape == (2,) for value in output.values()))
            receipt = model.architecture_receipt()
            self.assertEqual(receipt["memory_tokens"], count)
            receipts.append(receipt["downstream_sha256"])
            head_hashes.append(model.initial_head_sha256)
        self.assertEqual(len(set(receipts)), 1)
        self.assertEqual(len(set(head_hashes)), 1)
        self.assertEqual(sum(isinstance(m, CrossAttentionBlock)
            for m in RepresentationModel("embedding", 5, 3).modules()), 2)

    def test_global_weights_masked_mutation_and_empty_supervision(self):
        rows = tiny_rows().take(np.arange(18))
        weights = LossWeights.from_fit(rows)
        self.assertEqual(weights.action, 1.0)
        outputs = {name: torch.randn(6) for name in
                   ("action", "expected_value", "top3", "wall", "mae")}
        targets = {"action": torch.tensor([0., 1., 0., 1., 0., 1.]),
                   "expected_value": torch.randn(6), "top3": torch.tensor([0.,1.,0.,1.,0.,1.]),
                   "wall": torch.tensor([1.,0.,1.,0.,1.,0.]), "mae": torch.rand(6)*900}
        mask = torch.tensor([True, True, False, True, False, True])
        first = probe_loss(outputs, targets, mask, weights)
        changed = dict(targets); changed["action"] = targets["action"].clone()
        changed["action"][~mask] = 1 - changed["action"][~mask]
        self.assertEqual(float(first), float(probe_loss(outputs, changed, mask, weights)))
        empty = probe_loss(outputs, targets, torch.zeros(6, dtype=torch.bool), weights)
        changed_all = dict(targets); changed_all["action"] = 1 - targets["action"]
        self.assertEqual(float(empty), float(probe_loss(
            outputs, changed_all, torch.zeros(6, dtype=torch.bool), weights)))

    def test_test_label_mutation_real_orchestration_canary(self):
        rows = tiny_rows()
        first = decision_artifacts(rows)
        splits = split_rows(rows, min_supervised_rows=2)
        changed = rows.action.copy(); changed[splits["test"]] = ~changed[splits["test"]]
        second = decision_artifacts(replace(rows, action=changed))
        self.assertEqual(first, second)

    def test_platt_preserves_order(self):
        x = np.asarray([2., -1., 0., 2., 1.]); y = np.asarray([1., 0., 0., 1., 1.])
        calibrated = MonotonePlatt.fit(x, y).predict(x)
        for i in range(len(x)):
            for j in range(len(x)):
                self.assertEqual(np.sign(x[i] - x[j]),
                                 np.sign(calibrated[i] - calibrated[j]))

    def test_known_answer_fast_sweep_exact_replay_and_denominator(self):
        paths = [path("tie-a", "SI", 20221001, 10, 20, -200),
                 path("tie-b", "SI", 20221001, 10, 11, 900),
                 path("equal-open", "SI", 20221001, 20, 21, 1000),
                 path("after", "SI", 20221001, 21, 22, 800),
                 path("cap3", "SI", 20221001, 23, 24, -900),
                 path("capped", "SI", 20221001, 25, 26, 2000)]
        probabilities = np.asarray([.8, .8, .9, .7, .6, .5])
        rows = tuple(arrival(p, probability=float(probabilities[i]))
                     for i, p in enumerate(paths))
        sessions = (SessionRef("SI", 20221001, "SI-20221001"),
                    SessionRef("SI", 20221002, "empty"))
        sweep = fast_threshold_sweep(rows, probabilities, sessions)
        self.assertTrue(np.array_equal(sweep.thresholds, threshold_candidates(probabilities)))
        self.assertEqual(int(sweep.trades[-1]), 0)  # no-entry sentinel
        self.assertEqual(sweep.usd_per_asset_day[-1], 0.0)
        parity = assert_fast_sweep_parity(rows, probabilities, sessions, sweep,
                                          samples=len(sweep.thresholds))
        self.assertEqual(len(parity), 64)
        # At threshold .8, tie-a wins by candidate id; equal-time 20 is blocked.
        i = int(np.flatnonzero(sweep.thresholds == .8)[0])
        self.assertEqual(int(sweep.trades[i]), 1)
        self.assertEqual(float(sweep.total_pnl_usd[i]), -200.0)
        self.assertEqual(float(sweep.usd_per_asset_day[i]), -100.0)
        np.testing.assert_array_equal(sweep.daily_trades[i], [1, 0])
        np.testing.assert_array_equal(sweep.daily_admissions[i], [3, 0])
        np.testing.assert_array_equal(sweep.daily_pnl_usd[i], [-200.0, 0.0])
        self.assertEqual(int(sweep.days_with_trades[i]), 1)
        self.assertFalse(sweep.daily_pnl_usd.flags.writeable)
        changed_thresholds = sweep.thresholds.copy(); changed_thresholds[0] -= .01
        with self.assertRaisesRegex(Exception, "receipt"):
            replace(sweep, thresholds=changed_thresholds)

        frozen = depth_funnel(
            rows, probabilities, .9, sessions, positive_candidate_ids=("tie-a",))
        held_nonpositive = depth_funnel(
            rows, probabilities, .8, sessions, positive_candidate_ids=("tie-a",))
        twin = depth_funnel(
            rows, probabilities, 2.0, sessions, positive_candidate_ids=())
        transport = transport_receipt(frozen, held_nonpositive, twin)
        self.assertTrue(transport.held_optimum_nonpositive)
        self.assertEqual(transport.ratio_denominator_usd, 1e-9)
        self.assertEqual(frozen.executed_trade_precision, 0.0)
        with self.assertRaisesRegex(Exception, "cannot enter selection"):
            bool(transport)
        with self.assertRaisesRegex(Exception, "cannot enter selection"):
            bool(frozen)

    def test_deterministic_cpu_tail_starts_standard_checkpoint(self):
        rows = tiny_rows(); split = split_rows(rows, min_supervised_rows=2)
        normalized, _ = normalize_from_fit(rows, split["fit"])
        fit = normalized.take(split["fit"])
        a = train_models(fit, "embedding", batch_size=7, device="cpu")
        b = train_models(fit, "embedding", batch_size=7, device="cpu")
        self.assertEqual(state_sha256(a["tail_aware"]), state_sha256(b["tail_aware"]))
        self.assertEqual(a["standard"].standard_checkpoint_sha256,
                         a["tail_aware"].tail_start_sha256)
        self.assertEqual(len(a["standard"].training_history), 2)
        self.assertEqual(len(a["tail_aware"].training_history), 3)

    def test_balanced_slice_full_head_overfit_canary(self):
        model = RepresentationModel("static", 1, 2)
        embedding = torch.zeros(8, 1)
        labels = torch.tensor([0., 0., 0., 0., 1., 1., 1., 1.])
        static = torch.stack((labels * 2 - 1, torch.linspace(-.2, .2, 8)), dim=1)
        assets = torch.zeros(8, dtype=torch.long)
        optimizer = torch.optim.AdamW(model.parameters(), lr=3e-3, weight_decay=0.0)
        with torch.no_grad():
            initial = float(F.binary_cross_entropy_with_logits(
                model(embedding, static, assets)["action"], labels))
        for _ in range(30):
            optimizer.zero_grad(set_to_none=True)
            logits = model(embedding, static, assets)["action"]
            loss = F.binary_cross_entropy_with_logits(logits, labels)
            loss.backward(); optimizer.step()
        with torch.no_grad():
            logits = model(embedding, static, assets)["action"]
            final = float(F.binary_cross_entropy_with_logits(logits, labels))
            accuracy = float(((logits >= 0) == labels.bool()).float().mean())
        self.assertLess(final, initial)
        self.assertEqual(accuracy, 1.0)


if __name__ == "__main__":
    unittest.main()
