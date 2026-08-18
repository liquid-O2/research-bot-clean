#!/usr/bin/env python3
"""Focused exact-union fixture for the E3..E8 campaign receipt."""

from __future__ import annotations

from dataclasses import replace
import datetime as dt
from types import MappingProxyType, SimpleNamespace
import unittest

import numpy as np

from engine.entry_v2 import campaign as CP
from engine.entry_v2 import common as C
from engine.entry_v2 import train as T
from engine.entry_v2.event_pack import (
    CATEGORY_SIZES as EVENT_CATEGORY_SIZES,
    CATEGORICAL_FIELDS,
    CONTINUOUS_FIELDS,
)
from engine.entry_v2.policy import ModelInputBinding, entry_gate_contract
from engine.entry_v2.session_stream import MODEL_ARRAYS_CONVERSION_LAW_SHA256
from engine.entry_v2.audit import _attribute_bottleneck
from engine.entry_v2.contracts import (
    AssetDayRegime,
    CausalEntryExample,
    EntryScore,
    RawPrefixRef,
    SessionRef,
    Side,
)
from engine.entry_v2.replay import (
    ReplayOutcome,
    ScoredArrival,
    candidate_ceiling,
    replay,
)
from engine.entry_v2.train import ARM_FULL_PREFIX, ARM_NAMES, FoldOOFResult


NS = 1_000_000_000


def _fixture_days(start_d8: int, count: int) -> tuple[int, ...]:
    text = str(int(start_d8))
    cursor = dt.date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    days = []
    while len(days) < int(count):
        d8 = cursor.year * 10_000 + cursor.month * 100 + cursor.day
        eligible = cursor.weekday() < 5
        if eligible and d8 < C.HOLDOUT_START_D8:
            eligible = all(C.is_denominator_day(asset, d8) for asset in C.ASSETS)
        if eligible:
            days.append(d8)
        cursor += dt.timedelta(days=1)
    return tuple(days)


def _binding() -> ModelInputBinding:
    return ModelInputBinding(
        tuple(CONTINUOUS_FIELDS), tuple(CATEGORICAL_FIELDS),
        tuple(EVENT_CATEGORY_SIZES),
        MODEL_ARRAYS_CONVERSION_LAW_SHA256,
        C.object_sha256("campaign-session-stream-receipts"),
        C.object_sha256("campaign-corpus-receipt"),
        C.object_sha256("campaign-corpus-source-lineage"),
        C.object_sha256("campaign-clock-law-receipt"),
    )


def _score(example, model_hash, *, take, enter):
    return EntryScore(
        candidate_id=example.candidate_id,
        asset=example.asset,
        decision_ts_ns=example.decision_ts_ns,
        model_hash=model_hash,
        priority_score=float(take),
        take_probability=float(take),
        expected_pnl_usd=2500.0,
        expected_pnl_lower_usd=2500.0,
        top3_probability=1.0,
        mae_p90_usd=100.0,
        wall_probability=0.0,
        enter=bool(enter),
    )


def _fold_result(
    era, *, shuffled=False, day_override=None, shuffled_policy_action=None,
    regime="LOW", days_per_asset=1,
):
    lo, _hi = {name: (start, end) for name, start, end in C.ERAS}[era]
    first_common_denominator_day = {
        "E3": 20220701,
        "E4": 20230103,
        "E5": 20230703,
        "E6": 20240102,
        "E7": 20240701,
        "E8": 20250102,
    }
    day = int(day_override or first_common_denominator_day.get(era, lo))
    examples = []
    sessions = []
    outcomes = []
    if int(days_per_asset) < 1:
        raise ValueError("days_per_asset must be positive")
    fixture_days = _fixture_days(day, int(days_per_asset))
    for asset_index, asset in enumerate(C.ASSETS):
        for row_day in fixture_days:
            session_id = f"{asset}-{row_day}"
            sessions.append(SessionRef(asset, row_day, session_id))
            decision = (row_day * 100 + asset_index) * NS
            candidate_id = f"{era}-{asset}-{row_day}"
            examples.append(CausalEntryExample(
                candidate_id=candidate_id,
                asset=asset,
                trading_day=row_day,
                session_id=session_id,
                decision_ts_ns=decision,
                side=Side.LONG,
                phase="SYNTH",
                locked_iid=asset_index,
                raw_prefix_ref=RawPrefixRef(
                    shard=f"events/{asset}/{row_day}.qre2",
                    event_start_index=0,
                    event_end_index=10,
                    event_count=10,
                    first_availability_ts_ns=decision - 10,
                    last_availability_ts_ns=decision - 1,
                    source_hash=(f"{asset_index + 1:x}" * 64)[:64],
                ),
                causal_features={"candidate_geometry": float(asset_index)},
                lineage_hash=(f"{asset_index + 4:x}" * 64)[:64],
            ))
            outcomes.append(ReplayOutcome(
                candidate_id,
                decision + 10 * NS,
                2500.0,
                decision + 20 * NS,
                2500.0,
            ))

    direct_action = 0.0 if shuffled else 1.0
    action = (
        direct_action if shuffled_policy_action is None
        else float(shuffled_policy_action)
    )
    arm_scores = {
        arm: tuple(
            _score(
                example, f"{arm}:{era}", take=action,
                enter=bool(action >= 0.5),
            )
            for example in examples
        )
        for arm in ARM_NAMES
    }
    truth_scores = tuple(
        _score(example, f"truth:{era}", take=1.0, enter=True)
        for example in examples
    )

    def arrivals(scores):
        return tuple(ScoredArrival(example, score, outcome)
                     for example, score, outcome in zip(examples, scores, outcomes))

    arm_arrivals = {arm: arrivals(scores) for arm, scores in arm_scores.items()}
    truth_arrivals = arrivals(truth_scores)
    expected = tuple(sessions)
    regimes = tuple(
        AssetDayRegime(example.asset, example.trading_day, regime,
                       example.trading_day * NS)
        for example in examples
    )
    arm_evaluations = {
        arm: replay(rows, expected_sessions=expected)
        for arm, rows in arm_arrivals.items()
    }
    truth_eval = replay(truth_arrivals, expected_sessions=expected)
    ceiling = candidate_ceiling(truth_arrivals, expected_sessions=expected)
    row_count = len(examples)
    score_arrays = MappingProxyType({
        "action_p": np.full(row_count, action, dtype=np.float32),
        "top3_p": np.ones(row_count, dtype=np.float32),
        "wall_p_upper": np.zeros(row_count, dtype=np.float32),
        "expected_value_raw": np.full(row_count, 2500.0, dtype=np.float32),
        "expected_value_lower": np.full(row_count, 2500.0, dtype=np.float32),
        "expected_value_upper": np.full(row_count, 2600.0, dtype=np.float32),
        "mae_q90": np.full(row_count, 100.0, dtype=np.float32),
        "enter": np.full(row_count, int(action >= 0.5), dtype=np.uint8),
    })
    training_hash = C.object_sha256(["training", era, shuffled])
    normalizer_hash = C.object_sha256(["normalizer", era, shuffled])
    training = SimpleNamespace(
        trace=SimpleNamespace(
            receipt_sha256=training_hash, model_input_binding=_binding()
        ),
        normalizer=SimpleNamespace(
            receipt_sha256=normalizer_hash, model_input_binding=_binding()
        ),
    )
    thresholds = MappingProxyType({asset: 0.5 for asset in C.ASSETS})
    truth_thresholds = MappingProxyType({asset: 600.0 for asset in C.ASSETS})
    result = FoldOOFResult(
        fold=era,
        candidate_ids=tuple(example.candidate_id for example in examples),
        assets=tuple(example.asset for example in examples),
        days=np.asarray([example.trading_day for example in examples], dtype=np.int64),
        embeddings=np.arange(row_count * 2, dtype=np.float32).reshape(row_count, 2),
        static_features=np.arange(row_count * 3, dtype=np.float32).reshape(row_count, 3),
        arm_score_arrays=MappingProxyType({
            arm: score_arrays for arm in ARM_NAMES
        }),
        arm_entry_scores=MappingProxyType(arm_scores),
        arm_arrivals=MappingProxyType(arm_arrivals),
        arm_thresholds=MappingProxyType({
            arm: thresholds for arm in ARM_NAMES
        }),
        arm_evaluations=MappingProxyType(arm_evaluations),
        arm_policies=MappingProxyType({
            arm: MappingProxyType({}) for arm in ARM_NAMES
        }),
        truth_scores=truth_scores,
        truth_arrivals=truth_arrivals,
        expected_sessions=expected,
        regime_declarations=regimes,
        truth_thresholds_usd=truth_thresholds,
        truth_evaluation=truth_eval,
        candidate_ceiling=ceiling,
        training=training,
        receipt=MappingProxyType({}),
        control_name="SHUFFLED_17" if shuffled else "PROPHET",
    )
    receipt = {
        "schema": "entry-v2-fold-oof-v5",
        "fold": era,
        "training_receipt_sha256": training_hash,
        "normalizer_sha256": normalizer_hash,
        "model_input_binding": _binding().as_dict(),
        "fit_max_d8": max(1, day - 3),
        "calibration_min_d8": max(1, day - 2),
        "calibration_max_d8": max(1, day - 1),
        "test_min_d8": day,
        "test_max_d8": max(fixture_days),
        "test_days_declared": sorted({example.trading_day for example in examples}),
        "test_candidate_sha256": C.object_sha256(list(result.candidate_ids)),
        "arrays_sha256": CP._fold_array_hash(result),
        "assets": list(C.ASSETS),
        "arms": list(ARM_NAMES),
        "static_summary_schema": "entry-v2-static-candidate-context-summary-v1",
        "training_control": result.control_name,
        "null_control": ({
            "schema": "entry-v2-stage-asset-day-shuffle-v2",
            "seed": 17,
            "selected_labels": row_count,
            "within_asset_day_rows": 0,
            "stage_asset_fallback_rows": 0,
            "labels_outside_fold_untouched": 0,
            "preserved_marginals": (
                "stage,asset,action_loss_mask; asset/day/mask where size>=2"
            ),
            "action_loss_mask": "RECIPIENT_FIXED",
        } if shuffled else {
            "schema": "entry-v2-positive-control-v1", "control": "PROPHET",
        }),
        "regime_declarations": [
            {
                "asset": row.asset,
                "trading_day": row.trading_day,
                "regime": row.regime,
                "availability_ts_ns": row.availability_ts_ns,
            }
            for row in regimes
        ],
        "prequential": {
            "blocks": [[max(1, day - 2)], [max(1, day - 1)]],
            "calibration_days": [max(1, day - 2)],
            "threshold_selection_days": [max(1, day - 1)],
            "calibration_and_selection_predictions_disjoint": True,
            "test_predictions_never_used_for_calibration_or_selection": True,
        },
        "arm_thresholds": {
            arm: {
                asset: {"threshold": thresholds[asset],
                        "asset_days": int(days_per_asset),
                        "usd_per_asset_day": 2500.0}
                for asset in C.ASSETS
            }
            for arm in ARM_NAMES
        },
        "truth_inner_thresholds_usd": {
            asset: {"threshold": truth_thresholds[asset],
                    "asset_days": int(days_per_asset),
                    "usd_per_asset_day": 2500.0}
            for asset in C.ASSETS
        },
        "threshold_grid": [],
        "truth_threshold_grid_usd": [],
        "candidate_oracle_preflight": {
            "schema": "entry-v2-candidate-oracle-preflight-v5",
            "passed": True,
            "acceptance_law": (
                "oracle_usd_per_asset_day >= LOW_CAPACITY_ASSET_DAY_FLOOR_USD"
            ),
            "acceptance_floor_usd_per_asset_day":
                C.LOW_CAPACITY_ASSET_DAY_FLOOR_USD,
            "normal_floor_usd_per_asset_day": C.WEAK_ASSET_DAY_FLOOR_USD,
            "risk_exception_contract": (
                "learned era usd_per_asset_day >= LOW_CAPACITY_ASSET_DAY_FLOOR_USD "
                "and chronological max_drawdown_usd < LOW_CAPACITY_MAX_DRAWDOWN_USD"
            ),
            "risk_exception_max_drawdown_usd":
                C.LOW_CAPACITY_MAX_DRAWDOWN_USD,
            "optimization_goal_usd_per_asset_day": C.TARGET_ASSET_DAY_USD,
            "optimization_target": "full_total_pnl_usd",
            "values_clipped_to_acceptance_floor": False,
            "schedule_sha256": ceiling.schedule_sha256,
            "per_asset": {
                asset: {
                    "asset_days": int(days_per_asset),
                    "total_pnl_usd": 2500.0 * int(days_per_asset),
                    "usd_per_asset_day": 2500.0,
                    "acceptance_floor_usd_per_asset_day": 1000.0,
                    "normal_floor_usd_per_asset_day": 1500.0,
                    "optimization_goal_usd_per_asset_day": 2000.0,
                    "acceptance_floor_headroom_usd_per_asset_day": 1500.0,
                    "normal_floor_headroom_usd_per_asset_day": 1000.0,
                    "goal_headroom_usd_per_asset_day": 500.0,
                    "risk_exception_required": False,
                    "passed": True,
                    "oracle_capture": 1.0,
                    "oracle_replay_receipt_sha256": "e" * 64,
                }
                for asset in C.ASSETS
            },
        },
        "entry_gate_contract": entry_gate_contract(),
        "threshold_candidate_law": T.threshold_candidate_law(),
        "threshold_funnel_schema": T.THRESHOLD_FUNNEL_SCHEMA,
        "action_supervision_census": {
            "schema": "entry-v2-action-supervision-census-v1",
            "passed": True,
            "per_asset": {asset: {} for asset in C.ASSETS},
        },
        "decision_contract": {"proxy_metrics": "diagnostic_only"},
    }
    receipt["sha256"] = C.object_sha256(receipt)
    result.receipt = MappingProxyType(receipt)
    return result


class CampaignTest(unittest.TestCase):
    def test_exact_union_audit_schema_goal_and_refusals(self):
        folds = tuple(
            _fold_result(era, days_per_asset=10) for era in CP.EXPECTED_FOLDS
        )
        shuffled = tuple(
            _fold_result(era, shuffled=True, days_per_asset=10)
            for era in CP.EXPECTED_FOLDS
        )
        raw = CP.RawPrefixFidelityEvidence(
            expected_events=1800,
            observed_events=1800,
            mismatched_events=0,
            source_receipt_sha256="a" * 64,
            pack_receipt_sha256="b" * 64,
        )
        teacher = CP.TeacherAlignmentEvidence(
            expected_candidates=180,
            matched_candidates=180,
            mismatched_candidates=0,
            teacher_receipt_sha256="c" * 64,
            join_receipt_sha256="d" * 64,
        )
        result = CP.build_oof_campaign(
            folds,
            raw_prefix_fidelity=raw,
            teacher_alignment=teacher,
            shuffled_folds=shuffled,
        )
        self.assertTrue(CP.verify_campaign_receipt(result.receipt))
        self.assertTrue(result.receipt["goal_gate"]["passed"])
        self.assertTrue(result.receipt["promotion_ready"])
        self.assertEqual(result.receipt["schema"], "entry-v2-oof-campaign-v4")
        self.assertEqual(result.receipt["model_input_binding"], _binding().as_dict())
        self.assertEqual(result.learned_evaluation.asset_days, 180)
        for asset in C.ASSETS:
            metrics = result.receipt["per_asset"][asset]
            self.assertEqual(tuple(metrics["arms"]), ARM_NAMES)
            for arm in ARM_NAMES:
                arm_metrics = metrics["arms"][arm]
                self.assertEqual(arm_metrics["usd_per_asset_day"], 2500.0)
                self.assertEqual(
                    arm_metrics["shuffled_usd_per_asset_day"], 0.0
                )
                self.assertEqual(arm_metrics["candidate_oracle_capture"], 1.0)
                self.assertEqual(arm_metrics["max_drawdown_usd"], 0.0)
                self.assertTrue(arm_metrics["weak_regime"]["passed"])
                self.assertIn("concentration", arm_metrics)
                self.assertIn("day_clustered_mean_ci95_usd", arm_metrics)
                self.assertIn("adaptation_latency", arm_metrics)
                self.assertEqual(
                    arm_metrics["lift_over_shuffled_usd_per_asset_day"],
                    2500.0,
                )
        attributed = _attribute_bottleneck(
            result.receipt["bottleneck_boundaries"]
        )
        self.assertTrue(attributed["promotion"]["promoted"])
        self.assertIsNone(attributed["first_failed_boundary"])

        with self.assertRaisesRegex(C.EntryV2Refusal, "production campaign requires"):
            CP.build_oof_campaign(
                folds,
                raw_prefix_fidelity=None,
                teacher_alignment=teacher,
                shuffled_folds=shuffled,
            )

        incomplete_raw = CP.RawPrefixFidelityEvidence(
            expected_events=1800,
            observed_events=1799,
            mismatched_events=1,
            source_receipt_sha256="a" * 64,
            pack_receipt_sha256="b" * 64,
        )
        with self.assertRaisesRegex(C.EntryV2Refusal, "passing raw-prefix"):
            CP.build_oof_campaign(
                folds,
                raw_prefix_fidelity=incomplete_raw,
                teacher_alignment=teacher,
                shuffled_folds=shuffled,
            )

        diagnostic = CP.build_oof_campaign(
            folds,
            raw_prefix_fidelity=None,
            teacher_alignment=None,
            shuffled_folds=None,
            diagnostic=True,
        )
        self.assertFalse(diagnostic.receipt["promotion_ready"])
        self.assertFalse(
            diagnostic.receipt["bottleneck_boundaries"]["raw_prefix_fidelity"]
            ["resolved"]
        )

        failed_diagnostic = CP.build_oof_campaign(
            folds,
            raw_prefix_fidelity=incomplete_raw,
            teacher_alignment=teacher,
            shuffled_folds=shuffled,
            diagnostic=True,
        )
        failed_attribution = _attribute_bottleneck(
            failed_diagnostic.receipt["bottleneck_boundaries"]
        )
        self.assertEqual(
            failed_attribution["first_failed_boundary"], "raw_prefix_fidelity"
        )
        self.assertFalse(failed_diagnostic.receipt["promotion_ready"])

        passing_diagnostic = CP.build_oof_campaign(
            folds,
            raw_prefix_fidelity=raw,
            teacher_alignment=teacher,
            shuffled_folds=shuffled,
            diagnostic=True,
        )
        passing_diagnostic_attribution = _attribute_bottleneck(
            passing_diagnostic.receipt["bottleneck_boundaries"]
        )
        self.assertEqual(
            passing_diagnostic_attribution["first_failed_boundary"],
            "exact_replay",
        )
        self.assertFalse(
            passing_diagnostic_attribution["promotion"]["promoted"]
        )

        policy_leaking_null = tuple(
            _fold_result(
                era, shuffled=True, shuffled_policy_action=1.0,
                days_per_asset=10,
            )
            for era in CP.EXPECTED_FOLDS
        )
        null_failure = CP.build_oof_campaign(
            folds,
            raw_prefix_fidelity=raw,
            teacher_alignment=teacher,
            shuffled_folds=policy_leaking_null,
            diagnostic=True,
        )
        null_attribution = _attribute_bottleneck(
            null_failure.receipt["bottleneck_boundaries"]
        )
        self.assertEqual(
            null_attribution["first_failed_boundary"],
            "representation_learnability",
        )

        nonweak = tuple(
            _fold_result(era, regime="MID", days_per_asset=10)
            for era in CP.EXPECTED_FOLDS
        )
        nonweak_null = tuple(
            _fold_result(era, shuffled=True, regime="MID", days_per_asset=10)
            for era in CP.EXPECTED_FOLDS
        )
        weak_unresolved = CP.build_oof_campaign(
            nonweak,
            raw_prefix_fidelity=raw,
            teacher_alignment=teacher,
            shuffled_folds=nonweak_null,
            diagnostic=True,
        )
        self.assertFalse(weak_unresolved.receipt["goal_gate"]["passed"])
        self.assertTrue(all(
            not weak_unresolved.receipt["per_asset"][asset]["arms"]
                [ARM_FULL_PREFIX]["resolved"]
            for asset in C.ASSETS
        ))

        changed_full_prefix = MappingProxyType({
            **dict(folds[0].arm_thresholds[ARM_FULL_PREFIX]), "SI": 0.75,
        })
        changed_thresholds = MappingProxyType({
            **dict(folds[0].arm_thresholds),
            ARM_FULL_PREFIX: changed_full_prefix,
        })
        changed_threshold_fold = replace(
            folds[0], arm_thresholds=changed_thresholds
        )
        with self.assertRaisesRegex(C.EntryV2Refusal, "thresholds differ"):
            CP.build_oof_campaign(
                (changed_threshold_fold, *folds[1:]),
                raw_prefix_fidelity=raw,
                teacher_alignment=teacher,
                shuffled_folds=shuffled,
            )

        bad_receipt = dict(folds[0].receipt)
        bad_receipt["test_candidate_sha256"] = "0" * 64
        corrupted = replace(folds[0], receipt=MappingProxyType(bad_receipt))
        with self.assertRaisesRegex(C.EntryV2Refusal, "receipt hash mismatch"):
            CP.build_oof_campaign(
                (corrupted, *folds[1:]),
                raw_prefix_fidelity=raw,
                teacher_alignment=teacher,
                shuffled_folds=shuffled,
            )

        holdout = _fold_result("E8", day_override=20250701, days_per_asset=10)
        with self.assertRaisesRegex(C.EntryV2Refusal, "2025H2 HOLDOUT"):
            CP.build_oof_campaign(
                (*folds[:-1], holdout),
                raw_prefix_fidelity=raw,
                teacher_alignment=teacher,
                shuffled_folds=shuffled,
            )


class CapacityBoundaryTest(unittest.TestCase):
    def test_exact_weak_floor_is_not_low_capacity(self) -> None:
        self.assertEqual(CP._oracle_capacity_regime(2_000.0), "FULL")
        self.assertEqual(CP._oracle_capacity_regime(1_500.0), "WEAK")
        self.assertEqual(CP._oracle_capacity_regime(1_499.99), "LOW")


if __name__ == "__main__":
    unittest.main()
