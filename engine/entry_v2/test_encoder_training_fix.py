"""Law tests for the Entry V2 encoder-training fix pass (design REVISION 2).

Every test here is red against the pre-fix engine: the total-loss governor,
the unscoped reconstruction target, and the absent candidate-identity /
memory-value objectives all fail these assertions by construction.
"""
from __future__ import annotations

import unittest

import numpy as np
import torch

from . import common as C
from .corpus import CANDIDATE_FEATURE_SCHEMA
from .train import VALUE_SCALE_USD
from .neural_sufficiency_model import (
    ABSOLUTE_CLOCK_TARGET_FIELDS, EntryModelRefusal, LastRowReconstructionProbe,
    LiTShortMemoryEncoder, generic_event_schema, reconstruction_receipt,
    reconstruction_target_scope,
)
from .neural_sufficiency_resources import (
    ARM_WALL_CEILING_SECONDS, AUX_IDENTITY_WEIGHT, AUX_MEMORY_VALUE_WEIGHT,
    AUX_RECON_WEIGHT, AUX_SHARE_CAPS, AUX_SHARE_CAPS_MEASURED,
    AUX_WEIGHTS_MEASURED, AUX_WEIGHT_TODO, BASE_STAGE_CHECKPOINT_LAW,
    BASE_STAGE_GOVERNED_TRACES, BASE_STAGE_STOP_REASONS,
    CandidateIdentityProjection, GRADIENT_SHARE_MEASUREMENT_EPOCHS,
    IDENTITY_MAX_CROP_EVENTS, IDENTITY_MIN_CUTOFF_GAP_EVENTS,
    IDENTITY_MINIMUM_UNIQUE_WINDOWS, IDENTITY_POOLED_NEGATIVE_THRESHOLD,
    IDENTITY_TEMPERATURE, IDENTITY_TRAINED_ARMS, IDENTITY_UNAVAILABLE_BROADCAST,
    M1_ENCODER_GRU_LR_SCALE, M1_WARMUP_EPOCHS,
    MemoryValueProbe, RECONSTRUCTION_VALIDATION_MINIMUM_ROWS,
    RECONSTRUCTION_VALIDATION_MAXIMUM_HELD_FRACTION,
    GOAL_GRADE_USD, FROZEN_COST_FEATURE_NAME,
    IDENTITY_VALIDATION_UNAVAILABLE, MEMORY_VALUE_BASELINE_LAW,
    MEMORY_VALUE_LIST_TAU, MEMORY_VALUE_SHUFFLE_SEED,
    MEMORY_VALUE_TAIL_SCALE_USD, MEMORY_VALUE_TARGETS,
    MEMORY_VALUE_TARGET_SHARES, MEMORY_VALUE_UTIL_WEIGHT_CEILING_USD,
    MEMORY_VALUE_UTIL_WEIGHT_FLOOR_USD, MEMORY_VALUE_UTIL_WEIGHT_SCALE_USD,
    MEMORY_VALUE_VALUE_BIN_LAW, MEMORY_VALUE_WEIGHTS_MEASURED,
    EPISODE_CLUSTER_COLLAPSE, EPISODE_CLUSTER_GAP_SECONDS,
    MEMORY_VALUE_ACCEPTANCE_RULE, MEMORY_VALUE_LINEAR_PROBE_LAW,
    MEMORY_VALUE_PROBE_KINDS, _episode_clusters,
    RealDiagnosticExecutorRefusal, _PerComponentGovernor,
    _apply_linear_warmup, _auxiliary_share_scales, _batch_dollars,
    _base_stage_fix_receipt, _base_stage_parameter_groups,
    _candidate_identity_loss, _CandidateBatch, _encoder_gradient_shares,
    _field_reconstruction_loss, _identity_cropped_views,
    _memory_value_list_loss, _memory_value_probe_loss,
    _widened_validation_days, _within_session_shuffled_memory,
)


N_CONTINUOUS = 16
CATEGORY_SIZES = (4, 4, 4, 4, 4)


def _tiny_encoder(seed: int = 7) -> LiTShortMemoryEncoder:
    torch.manual_seed(seed)
    return LiTShortMemoryEncoder(
        N_CONTINUOUS, CATEGORY_SIZES,
        field_schema=generic_event_schema(N_CONTINUOUS, CATEGORY_SIZES))


def _tiny_batch(*, clock: np.ndarray, cutoffs: np.ndarray, asset: str = "HG",
                day: int = 20210701, session_id: str = "S1",
                seed: int = 11, certified_usd=None, frozen_usd=None,
                wall_hit=None) -> _CandidateBatch:
    """One real ``_CandidateBatch`` over a synthetic but LAWFUL event tape."""
    generator = torch.Generator().manual_seed(seed)
    events = len(clock)
    candidates = len(cutoffs)
    clock_tensor = torch.as_tensor(np.asarray(clock, np.int64))
    cutoff_tensor = torch.as_tensor(np.asarray(cutoffs, np.int64))
    decisions = torch.as_tensor(
        np.asarray([int(clock[int(cut) - 1]) + 1 for cut in cutoffs], np.int64))
    if not torch.equal(torch.searchsorted(clock_tensor, decisions), cutoff_tensor):
        raise AssertionError("fixture cutoffs are not lawful lower bounds")
    return _CandidateBatch(
        asset=asset, day=int(day), session_id=session_id,
        candidate_ids=tuple(f"{session_id}-{index}" for index in range(candidates)),
        continuous=torch.randn(events, N_CONTINUOUS, generator=generator),
        categorical=torch.randint(0, 4, (events, len(CATEGORY_SIZES)),
                                  generator=generator),
        clock=clock_tensor,
        cutoffs=cutoff_tensor,
        decisions=decisions,
        candidate_features=_candidate_feature_block(candidates, frozen_usd),
        context_values=torch.zeros(candidates, 2, 4, 3),
        context_type_ids=torch.zeros(2, dtype=torch.long),
        context_valid=torch.ones(candidates, 2, 4, dtype=torch.bool),
        static_features=torch.zeros(candidates, 1_865),
        targets=torch.randint(0, 2, (candidates,), generator=generator).float(),
        action_loss_mask=torch.ones(candidates, dtype=torch.bool),
        oracle_targets={
            "value_bin": torch.randint(0, 5, (candidates,), generator=generator),
            # The base stage stores certified dollars scaled by VALUE_SCALE_USD.
            "value": (torch.randn(candidates, generator=generator)
                      if certified_usd is None
                      else torch.as_tensor(certified_usd, dtype=torch.float32)
                      / VALUE_SCALE_USD),
            "top3": torch.randint(0, 2, (candidates,), generator=generator).float(),
            "rank": torch.randn(candidates, generator=generator),
            "mfe": torch.randn(candidates, generator=generator),
            "mae": torch.randn(candidates, generator=generator),
            "wall": (torch.randint(0, 2, (candidates,),
                                   generator=generator).float()
                     if wall_hit is None
                     else torch.as_tensor(wall_hit, dtype=torch.float32)),
            "time": torch.randn(candidates, generator=generator),
        },
        horizon_targets=torch.randn(candidates, 6, generator=generator),
        horizon_valid=torch.ones(candidates, 6, dtype=torch.bool),
        phase_targets=torch.zeros(candidates, dtype=torch.long),
        phase_valid=torch.ones(candidates, dtype=torch.bool),
        last_continuous=torch.randn(candidates, N_CONTINUOUS, generator=generator),
        last_categorical=torch.randint(0, 4, (candidates, len(CATEGORY_SIZES)),
                                       generator=generator),
    )


def _candidate_feature_block(candidates: int, frozen_usd) -> torch.Tensor:
    """The frozen candidate-feature schema width, with a real frozen cost."""
    block = torch.zeros(candidates, len(CANDIDATE_FEATURE_SCHEMA))
    column = CANDIDATE_FEATURE_SCHEMA.index(FROZEN_COST_FEATURE_NAME)
    if frozen_usd is not None:
        block[:, column] = torch.as_tensor(frozen_usd, dtype=torch.float32)
    return block


def _graph_leaf_pointers(tensor: torch.Tensor) -> set[int]:
    """Every leaf tensor the autograd graph of ``tensor`` can reach."""
    seen: set[int] = set(); leaves: set[int] = set()
    # Autograd node wrappers are created on demand; without a keep-alive list
    # a freed node's id can be reused and the walk silently truncates.
    keep: list[object] = []
    stack = [tensor.grad_fn]
    while stack:
        node = stack.pop()
        if node is None or id(node) in seen:
            continue
        seen.add(id(node)); keep.append(node)
        variable = getattr(node, "variable", None)
        if variable is not None:
            leaves.add(variable.data_ptr())
        for following, _index in getattr(node, "next_functions", ()):
            stack.append(following)
    return leaves


class PerComponentGovernorLawTest(unittest.TestCase):
    """F2 + R3: stopping and checkpoint selection move together."""

    def _governor(self, governed=("oracle", "recon", "identity", "memory_value")):
        return _PerComponentGovernor(governed, minimum_relative_improvement=.001,
                                     patience=3)

    def test_stage_continues_while_one_trace_still_improves(self):
        # The measured failure: the oracle plateaus in 2-3 epochs and the old
        # summed scalar stopped the stage there, while reconstruction and
        # identity were still descending.
        governor = self._governor(("oracle", "recon"))
        verdicts = []
        for epoch in range(6):
            verdicts.append(governor.observe({
                "oracle": 10.0 if epoch else 10.5,     # plateau after epoch 0
                "recon": 5.0 * (0.5 ** epoch),          # still descending
            }))
        self.assertTrue(all(int(v["stale_by_trace"]["oracle"]) >= 3
                            for v in verdicts[4:]))
        self.assertTrue(all(int(v["stale_by_trace"]["recon"]) == 0
                            for v in verdicts))
        self.assertFalse(any(bool(v["all_stale"]) for v in verdicts))

    def test_stops_only_when_every_trace_is_stale(self):
        governor = self._governor(("oracle", "recon"))
        stops = [governor.observe({"oracle": 1.0, "recon": 1.0})["all_stale"]
                 for _ in range(5)]
        self.assertEqual(stops, [False, False, False, True, True])

    def test_a_sub_threshold_improvement_still_counts_as_stale(self):
        governor = self._governor(("oracle",))
        governor.observe({"oracle": 1.0})
        verdict = governor.observe({"oracle": 0.9995})   # 0.05% < 0.1% law
        self.assertEqual(int(verdict["stale_by_trace"]["oracle"]), 1)

    def test_checkpoint_is_the_scale_free_composite_not_the_oracle_minimum(self):
        # Oracle is minimal at epoch 1; the mean of epoch-0-normalized traces
        # is minimal at epoch 2.  The old law (one summed scalar dominated by
        # the ~16-unit oracle stack) would reload epoch 1.
        governor = self._governor(("oracle", "recon"))
        rows = [{"oracle": 16.0, "recon": 0.40},
                {"oracle": 10.0, "recon": 0.40},
                {"oracle": 10.4, "recon": 0.05}]
        verdicts = [governor.observe(row) for row in rows]
        summed = [row["oracle"] + row["recon"] for row in rows]
        self.assertEqual(int(np.argmin(summed)), 1)
        self.assertEqual(governor.best_epoch, 2)
        self.assertTrue(verdicts[2]["selected"])
        self.assertAlmostEqual(float(verdicts[0]["composite"]), 1.0)

    def test_epoch_zero_traces_must_be_positive_to_normalize(self):
        governor = self._governor(("oracle",))
        with self.assertRaisesRegex(RealDiagnosticExecutorRefusal,
                                    "epoch-0 governed traces"):
            governor.observe({"oracle": 0.0})

    def test_a_missing_governed_trace_refuses(self):
        governor = self._governor(("oracle", "identity"))
        with self.assertRaisesRegex(RealDiagnosticExecutorRefusal,
                                    "governed traces are missing"):
            governor.observe({"oracle": 1.0})

    def test_governed_roster_and_stop_reasons_are_typed(self):
        self.assertEqual(BASE_STAGE_GOVERNED_TRACES,
                         ("oracle", "recon", "identity", "memory_value"))
        self.assertIn("CONVERGED", BASE_STAGE_STOP_REASONS)
        self.assertIn("WALL_CEILING", BASE_STAGE_STOP_REASONS)
        self.assertEqual(BASE_STAGE_CHECKPOINT_LAW,
                         "MIN_MEAN_EPOCH0_NORMALIZED_GOVERNED_TRACES")

    def test_wall_ceilings_are_the_measured_per_arm_seconds(self):
        self.assertEqual(dict(ARM_WALL_CEILING_SECONDS),
                         {"C0": 360.0, "C1": 360.0, "L0": 480.0, "L1": 480.0,
                          "M1": 1800.0})


class ReconstructionTargetScopeTest(unittest.TestCase):
    """R9: the six absolute-clock columns leave the reconstruction TARGET."""

    def _names(self):
        return ("raw.price", "raw.size", *ABSOLUTE_CLOCK_TARGET_FIELDS,
                "derived.receive_gap_ns.quotient_1e9")

    def test_absolute_clock_columns_are_excluded_by_name(self):
        names = self._names()
        scope = reconstruction_target_scope(names, strict=True)
        excluded = {name for name, keep in zip(names, scope) if not keep}
        self.assertEqual(excluded, set(ABSOLUTE_CLOCK_TARGET_FIELDS))
        self.assertEqual(len(ABSOLUTE_CLOCK_TARGET_FIELDS), 6)

    def test_the_production_schema_carries_every_named_clock_column(self):
        from .neural_sufficiency_resources import _expanded_columns  # noqa: F401
        from .diagnostic_inputs import RAW_ROUTE_FIELDS
        self.assertIn("ts_recv_ns", RAW_ROUTE_FIELDS)
        self.assertIn("ts_event_ns", RAW_ROUTE_FIELDS)

    def test_strict_scope_refuses_a_schema_without_the_named_columns(self):
        with self.assertRaisesRegex(EntryModelRefusal, "absolute-clock"):
            reconstruction_target_scope(("raw.price", "raw.size"), strict=True)

    def test_non_strict_scope_keeps_every_unnamed_column(self):
        scope = reconstruction_target_scope(("raw.price", "raw.size"))
        self.assertEqual(scope, (True, True))

    def test_scoped_loss_ignores_the_excluded_columns(self):
        names = self._names()
        scope = reconstruction_target_scope(names, strict=True)
        batch = _tiny_batch(clock=np.arange(1, 41, dtype=np.int64) * 1_000,
                            cutoffs=np.asarray([10, 20, 30], np.int64))
        batch.last_continuous.zero_()
        wide = torch.zeros(3, len(names))
        batch = _replace_last_continuous(batch, wide)
        decoder = LastRowReconstructionProbe(len(names), CATEGORY_SIZES)
        memory = torch.randn(3, 4, 512)
        with torch.no_grad():
            before, _c, _k = _field_reconstruction_loss(
                decoder, memory, batch, continuous_scope=scope)
        clock_column = names.index("raw.ts_recv_ns.sec")
        price_column = names.index("raw.price")
        moved = wide.clone(); moved[:, clock_column] += 100.0
        with torch.no_grad():
            after_clock, _c, _k = _field_reconstruction_loss(
                decoder, memory, _replace_last_continuous(batch, moved),
                continuous_scope=scope)
        moved = wide.clone(); moved[:, price_column] += 100.0
        with torch.no_grad():
            after_price, _c, _k = _field_reconstruction_loss(
                decoder, memory, _replace_last_continuous(batch, moved),
                continuous_scope=scope)
        self.assertAlmostEqual(float(before), float(after_clock), places=5)
        self.assertGreater(float(after_price), float(before) + 1.0)

    def test_scoped_receipt_counts_only_scoped_fields(self):
        names = self._names()
        scope = reconstruction_target_scope(names, strict=True)
        decoder = LastRowReconstructionProbe(len(names), CATEGORY_SIZES)
        memory = torch.randn(5, 4, 512)
        continuous = torch.zeros(5, len(names))
        continuous[:, names.index("raw.ts_recv_ns.sec")] = 1_000.0
        categorical = torch.zeros(5, len(CATEGORY_SIZES), dtype=torch.long)
        scoped = reconstruction_receipt(decoder, memory, continuous, categorical,
                                        continuous_scope=scope)
        unscoped = reconstruction_receipt(decoder, memory, continuous, categorical)
        self.assertEqual(int(scoped.scoped_continuous_fields), len(names) - 6)
        self.assertEqual(int(unscoped.scoped_continuous_fields), len(names))
        self.assertLess(float(scoped.continuous_mae),
                        float(unscoped.continuous_mae))


def _replace_last_continuous(batch: _CandidateBatch,
                             values: torch.Tensor) -> _CandidateBatch:
    return dataclasses_replace(batch, last_continuous=values)


def dataclasses_replace(batch: _CandidateBatch, **changes) -> _CandidateBatch:
    import dataclasses
    return dataclasses.replace(batch, **changes)


class CandidateIdentityLawTest(unittest.TestCase):
    """R1: the identity objective is a function of the INPUT tape only."""

    def _views(self, *, clock=None, cutoffs=None, seed=3):
        clock = (np.arange(1, 121, dtype=np.int64) * 1_000 if clock is None
                 else clock)
        cutoffs = (np.asarray([40, 70, 100], np.int64) if cutoffs is None
                   else cutoffs)
        encoder = _tiny_encoder()
        projection = CandidateIdentityProjection()
        batch = _tiny_batch(clock=clock, cutoffs=cutoffs)
        memory = encoder(batch.continuous, batch.categorical, batch.cutoffs,
                         receive_clock_ns=batch.clock,
                         candidate_decision_ts_ns=batch.decisions,
                         asset_idx=C.ASSET_INDEX[batch.asset])
        record, skipped = _identity_cropped_views(
            encoder, batch, memory, projection,
            device=torch.device("cpu"), seed=seed)
        return encoder, projection, batch, memory, record, skipped

    def test_identity_loss_graph_never_reaches_a_target_or_outcome_tensor(self):
        _encoder, _projection, batch, _memory, record, skipped = self._views()
        self.assertIsNone(skipped)
        outcome = {"action_target": batch.targets,
                   "top3": batch.oracle_targets["top3"],
                   "value": batch.oracle_targets["value"],
                   "wall": batch.oracle_targets["wall"],
                   "horizons": batch.horizon_targets}
        for tensor in outcome.values():
            tensor.requires_grad_(True)
        loss, receipt = _candidate_identity_loss([record])
        self.assertIsNotNone(loss)
        self.assertGreaterEqual(int(receipt["rows"]), 2)
        reachable = _graph_leaf_pointers(loss)
        for name, tensor in outcome.items():
            self.assertNotIn(tensor.data_ptr(), reachable,
                             f"identity loss graph reached {name}")
        loss.backward()
        for name, tensor in outcome.items():
            self.assertIsNone(tensor.grad, f"identity loss trained on {name}")

    def test_the_graph_walk_itself_catches_a_planted_leak(self):
        # A leakage assertion that cannot fail is not an assertion.
        _encoder, _projection, batch, _memory, record, _skipped = self._views()
        batch.targets.requires_grad_(True)
        loss, _receipt = _candidate_identity_loss([record])
        leaky = loss + batch.targets.sum()
        self.assertIn(batch.targets.data_ptr(), _graph_leaf_pointers(leaky))

    def test_the_target_view_carries_no_gradient(self):
        _encoder, _projection, _batch, _memory, record, _skipped = self._views()
        self.assertTrue(record["view"].requires_grad)
        self.assertFalse(record["target"].requires_grad)

    def test_cropped_views_are_lawful_lower_bound_cutoffs(self):
        # Duplicate receive timestamps are the case a naive ``cutoff - k``
        # gets wrong: the model plane proves every cutoff with
        # ``lower_bound(receive_clock_ns, decision)``.
        clock = np.repeat(np.arange(1, 41, dtype=np.int64) * 1_000, 3)
        cutoffs = np.asarray([30, 60, 90], np.int64)
        encoder, _projection, batch, _memory, record, skipped = self._views(
            clock=clock, cutoffs=cutoffs)
        self.assertIsNone(skipped)
        cropped = np.asarray(record["cropped_cutoffs"])
        self.assertTrue(np.all(cropped < np.asarray(record["cutoffs"])))
        decisions = torch.as_tensor(
            [int(clock[int(cut) - 1]) + 1 for cut in cropped], dtype=torch.int64)
        visible = int(cropped.max())
        np.testing.assert_array_equal(
            torch.searchsorted(torch.as_tensor(clock[:visible]),
                               decisions).numpy(), cropped)

    def test_a_naive_trailing_crop_is_refused_by_the_model_plane(self):
        clock = np.repeat(np.arange(1, 41, dtype=np.int64) * 1_000, 3)
        batch = _tiny_batch(clock=clock,
                            cutoffs=np.asarray([30, 60, 90], np.int64))
        encoder = _tiny_encoder()
        naive = batch.cutoffs - 1          # lands mid-tie: unprovable
        with self.assertRaises(EntryModelRefusal):
            encoder(batch.continuous, batch.categorical, naive,
                    receive_clock_ns=batch.clock,
                    candidate_decision_ts_ns=torch.as_tensor(
                        [int(clock[int(cut) - 1]) + 1 for cut in naive],
                        dtype=torch.int64),
                    asset_idx=0)

    def test_same_cutoff_candidates_collapse_into_one_identity_class(self):
        clock = np.arange(1, 121, dtype=np.int64) * 1_000
        cutoffs = np.asarray([40, 40, 40, 100], np.int64)
        _encoder, _projection, _batch, _memory, record, skipped = self._views(
            clock=clock, cutoffs=cutoffs)
        self.assertIsNone(skipped)
        self.assertEqual(len(record["cutoffs"]), 2)
        self.assertEqual(sorted(int(x) for x in record["cutoffs"]), [40, 100])

    def test_a_session_without_two_unique_windows_is_a_typed_skip(self):
        clock = np.arange(1, 121, dtype=np.int64) * 1_000
        cutoffs = np.asarray([40, 40, 40], np.int64)
        _e, _p, _b, _m, record, skipped = self._views(clock=clock, cutoffs=cutoffs)
        self.assertIsNone(record)
        self.assertEqual(skipped, "TOO_FEW_UNIQUE_WINDOWS")
        self.assertEqual(IDENTITY_MINIMUM_UNIQUE_WINDOWS, 2)

    def test_near_cutoff_negatives_are_excluded_from_the_denominator(self):
        # Two windows one event apart are the same tape; separating them is
        # noise, not identity.
        near = {"session_id": "S", "view": torch.eye(3, 8)[:, :8],
                "target": torch.eye(3, 8)[:, :8],
                "cutoffs": np.asarray([100, 101, 200], np.int64),
                "cropped_cutoffs": np.asarray([96, 97, 196], np.int64)}
        loss, receipt = _candidate_identity_loss([near])
        self.assertIsNotNone(loss)
        # rows 0 and 1 are 1 event apart (< 4): each keeps only itself + row 2.
        self.assertAlmostEqual(float(receipt["mean_negatives"]), 4.0 / 3.0)
        self.assertEqual(IDENTITY_MIN_CUTOFF_GAP_EVENTS, 4)

    def test_thin_sessions_pool_asset_day_negatives(self):
        def record(name, cutoffs):
            count = len(cutoffs)
            return {"session_id": name, "view": torch.randn(count, 8),
                    "target": torch.randn(count, 8),
                    "cutoffs": np.asarray(cutoffs, np.int64),
                    "cropped_cutoffs": np.asarray(cutoffs, np.int64) - 4}
        thin = [record("A", [100, 200]), record("B", [300, 400])]
        _loss, receipt = _candidate_identity_loss(thin)
        self.assertEqual(int(receipt["rows"]), 4)
        self.assertEqual(int(receipt["pooled_rows"]), 4)
        self.assertAlmostEqual(float(receipt["mean_negatives"]), 3.0)
        self.assertEqual(IDENTITY_POOLED_NEGATIVE_THRESHOLD, 8)

    def test_temperature_and_crop_depth_are_module_constants(self):
        self.assertEqual(IDENTITY_TEMPERATURE, 0.1)
        self.assertEqual(IDENTITY_MAX_CROP_EVENTS, 8)

    def test_broadcast_arms_are_not_in_the_identity_roster(self):
        self.assertEqual(IDENTITY_TRAINED_ARMS, ("L0", "L1", "M1"))
        self.assertNotIn("C0", IDENTITY_TRAINED_ARMS)
        self.assertNotIn("C1", IDENTITY_TRAINED_ARMS)


class MemoryValueProbeLawTest(unittest.TestCase):
    """R2 as AMENDED: the probe is graded on DOLLAR ORDERING, not bulk labels.

    The measured pathology the amendment answers: AUROC 0.70 bought -$41/day,
    and the tail is invisible to every shallow plane.
    """

    def _batch(self, certified=None, frozen=None, wall=None, candidates=3,
               asset="HG", day=20210701, session_id="S1"):
        cutoffs = np.asarray([10 * (index + 1) for index in range(candidates)],
                             np.int64)
        clock = np.arange(1, 10 * candidates + 11, dtype=np.int64) * 1_000
        return _tiny_batch(clock=clock, cutoffs=cutoffs, asset=asset, day=day,
                           session_id=session_id, certified_usd=certified,
                           frozen_usd=frozen, wall_hit=wall)

    def test_dollars_come_from_planes_the_stage_already_consumes(self):
        batch = self._batch(certified=[1_200.0, 400.0, 0.0],
                            frozen=[200.0, 100.0, 50.0])
        dollars = _batch_dollars(batch, torch.device("cpu"))
        np.testing.assert_allclose(dollars["certified_usd"].numpy(),
                                   [1_200.0, 400.0, 0.0], rtol=1e-5)
        np.testing.assert_allclose(dollars["net_usd"].numpy(),
                                   [1_000.0, 300.0, -50.0], rtol=1e-5)
        np.testing.assert_allclose(dollars["goal_grade"].numpy(), [1.0, 0.0, 0.0])
        self.assertEqual(GOAL_GRADE_USD, 600.0)

    def test_frozen_cost_is_resolved_by_name_not_position(self):
        self.assertIn(FROZEN_COST_FEATURE_NAME, CANDIDATE_FEATURE_SCHEMA)
        batch = self._batch(certified=[1_000.0] * 3, frozen=[10.0] * 3)
        moved = dataclasses_replace(
            batch, candidate_features=batch.candidate_features[:, :4])
        with self.assertRaisesRegex(RealDiagnosticExecutorRefusal,
                                    "frozen candidate feature schema"):
            _batch_dollars(moved, torch.device("cpu"))

    def test_util_weight_is_clipped_dollar_magnitude(self):
        # w = clip(|net|, 50, 1500)/600: a $10 candidate and a $5,000 candidate
        # both stop counting at the clip, so one outlier cannot own the batch.
        batch = self._batch(certified=[610.0, 6_500.0, 605.0],
                            frozen=[600.0, 0.0, 0.0])
        dollars = _batch_dollars(batch, torch.device("cpu"))
        net = dollars["net_usd"]
        weight = (net.abs().clamp(MEMORY_VALUE_UTIL_WEIGHT_FLOOR_USD,
                                  MEMORY_VALUE_UTIL_WEIGHT_CEILING_USD)
                  / MEMORY_VALUE_UTIL_WEIGHT_SCALE_USD)
        self.assertAlmostEqual(float(weight[0]),
                              MEMORY_VALUE_UTIL_WEIGHT_FLOOR_USD / 600.0)
        self.assertAlmostEqual(float(weight[1]),
                              MEMORY_VALUE_UTIL_WEIGHT_CEILING_USD / 600.0)

    def test_the_big_dollar_row_dominates_the_util_gradient(self):
        # The whole point of the retarget: two rows with the SAME label but
        # very different dollars must not pull equally.  With IDENTICAL
        # memories the two rows differ only in their dollar weight, so the
        # gradient ratio is exactly w0/w1 - the law, not a correlation.
        torch.manual_seed(3)
        probe = MemoryValueProbe()
        batch = self._batch(certified=[3_000.0, 620.0], frozen=[0.0, 0.0],
                            wall=[0.0, 0.0], candidates=2)
        row = torch.randn(1, 4, 512)
        memory = row.repeat(2, 1, 1).clone().requires_grad_(True)
        _total, components, _record = _memory_value_probe_loss(
            probe, memory, batch)
        grads = torch.autograd.grad(components["util"], memory)[0]
        clipped = [min(max(value, MEMORY_VALUE_UTIL_WEIGHT_FLOOR_USD),
                       MEMORY_VALUE_UTIL_WEIGHT_CEILING_USD)
                   for value in (3_000.0, 620.0)]
        self.assertAlmostEqual(
            float(grads[0].abs().sum() / grads[1].abs().sum()),
            clipped[0] / clipped[1], places=4)

    def test_listwise_term_is_the_dollar_mass_kl_on_the_util_score(self):
        # Ranking the day's dollars correctly must score better than the
        # reverse ranking, and a perfectly matched ranking is the entropy floor.
        gains = torch.tensor([300.0, 100.0, 0.0])
        target = gains / gains.sum()

        def loss_for(scores):
            record = {"asset": "HG", "day": 20210701, "session_id": "S",
                      "scores": torch.as_tensor(scores),
                      "gains": gains, "rows": 3}
            value, receipt = _memory_value_list_loss([record])
            return float(value), receipt

        aligned = torch.log(target.clamp_min(1e-9)) * MEMORY_VALUE_LIST_TAU
        right, receipt = loss_for([3.0, 1.0, 0.0])
        wrong, _ = loss_for([0.0, 1.0, 3.0])
        matched, _ = loss_for(aligned)
        entropy = float(-(target * torch.log(target.clamp_min(1e-9))).sum())
        self.assertLess(right, wrong)
        self.assertAlmostEqual(matched, entropy, places=4)
        self.assertEqual(int(receipt["groups"]), 1)
        self.assertAlmostEqual(float(receipt["list_coverage"]), 1.0)

    def test_a_day_without_positive_dollar_mass_is_a_typed_skip(self):
        record = {"asset": "HG", "day": 20210701, "session_id": "S",
                  "scores": torch.zeros(3), "gains": torch.zeros(3), "rows": 3}
        value, receipt = _memory_value_list_loss([record])
        self.assertIsNone(value)
        self.assertEqual(dict(receipt["skips"]),
                         {"NO_POSITIVE_DOLLAR_MASS": 1})

    def test_listwise_groups_by_asset_day_across_sessions(self):
        def record(asset, day, session):
            return {"asset": asset, "day": day, "session_id": session,
                    "scores": torch.zeros(2), "gains": torch.tensor([1.0, 0.0]),
                    "rows": 2}
        _value, receipt = _memory_value_list_loss([
            record("HG", 20210701, "a"), record("HG", 20210701, "b"),
            record("SI", 20210701, "c")])
        self.assertEqual(int(receipt["groups"]), 2)
        self.assertEqual(int(receipt["rows"]), 6)

    def test_tail_term_weights_losers_by_their_drawdown(self):
        batch = self._batch(certified=[0.0, 0.0], frozen=[900.0, 0.0],
                            wall=[1.0, 1.0], candidates=2)
        dollars = _batch_dollars(batch, torch.device("cpu"))
        weight = (1.0 + dollars["net_usd"].clamp_max(0.0).abs()
                  / MEMORY_VALUE_TAIL_SCALE_USD)
        self.assertAlmostEqual(float(weight[0]), 2.0)
        self.assertAlmostEqual(float(weight[1]), 1.0)
        self.assertEqual(MEMORY_VALUE_TAIL_SCALE_USD, 900.0)

    def test_value_bin_is_a_detached_passive_diagnostic(self):
        # It reports, it does not steer: no encoder gradient may flow from it.
        torch.manual_seed(5)
        probe = MemoryValueProbe()
        batch = self._batch(certified=[1_000.0, 100.0, 0.0], frozen=[0.0] * 3)
        memory = torch.randn(3, 4, 512, requires_grad=True)
        _total, components, _record = _memory_value_probe_loss(
            probe, memory, batch)
        components["value_bin_diagnostic"].backward()
        self.assertIsNone(memory.grad)
        self.assertIsNotNone(probe.value_bin.weight.grad)
        self.assertEqual(MEMORY_VALUE_VALUE_BIN_LAW,
                         "DETACHED_PASSIVE_DIAGNOSTIC")

    def test_the_trained_terms_do_reach_the_memory(self):
        torch.manual_seed(7)
        probe = MemoryValueProbe()
        batch = self._batch(certified=[1_000.0, 100.0, 0.0], frozen=[0.0] * 3)
        memory = torch.randn(3, 4, 512, requires_grad=True)
        total, components, record = _memory_value_probe_loss(
            probe, memory, batch)
        total.backward()
        self.assertIsNotNone(memory.grad)
        self.assertGreater(float(memory.grad.abs().sum()), 0.0)
        self.assertEqual(set(components),
                         {"util", "tail", "value_bin_diagnostic"})
        self.assertEqual(MEMORY_VALUE_TARGETS,
                         ("util_goal_grade", "list_dollar_mass", "tail_wall_hit"))

    def test_the_probe_channel_MAY_touch_outcome_tensors(self):
        # The leakage law is two-sided: identity must reach no outcome tensor,
        # and the probe channel must actually be where the outcome-derived
        # weights live.  An assertion that only ever holds one way is half a
        # law.
        torch.manual_seed(13)
        probe = MemoryValueProbe()
        batch = self._batch(certified=[2_000.0, 100.0], frozen=[0.0, 0.0],
                            wall=[1.0, 0.0], candidates=2)
        certified = batch.oracle_targets["value"]
        wall = batch.oracle_targets["wall"]
        certified.requires_grad_(True); wall.requires_grad_(True)
        memory = torch.randn(2, 4, 512, requires_grad=True)
        total, _components, _record = _memory_value_probe_loss(
            probe, memory, batch)
        reachable = _graph_leaf_pointers(total)
        self.assertIn(certified.data_ptr(), reachable)
        self.assertIn(wall.data_ptr(), reachable)

    def test_internal_target_shares_are_the_pre_registered_fifty_thirty_twenty(self):
        self.assertEqual(dict(MEMORY_VALUE_TARGET_SHARES),
                         {"util": 0.50, "list": 0.30, "tail": 0.20})
        self.assertFalse(MEMORY_VALUE_WEIGHTS_MEASURED)


class EpisodeClusterCollapseTest(unittest.TestCase):
    """Section 2's [A/B], behind ONE flag.

    Candidates inside one episode are near-duplicates of the same
    opportunity; ranking them against each other is noise, so the collapse
    makes the listwise target rank EPISODES.
    """

    def _record(self, scores, gains, decisions):
        return {"asset": "HG", "day": 20210701, "session_id": "S",
                "scores": torch.as_tensor(scores, dtype=torch.float32),
                "gains": torch.as_tensor(gains, dtype=torch.float32),
                "decisions": np.asarray(decisions, np.int64),
                "rows": len(scores)}

    def test_the_flag_is_off_by_default(self):
        self.assertFalse(EPISODE_CLUSTER_COLLAPSE)
        self.assertEqual(EPISODE_CLUSTER_GAP_SECONDS, 60)

    def test_clusters_break_on_a_sixty_second_decision_gap(self):
        second = 1_000_000_000
        decisions = np.asarray(
            [0, 10 * second, 20 * second,          # one episode
             200 * second, 210 * second,           # a second episode
             400 * second], np.int64)
        ids = _episode_clusters(decisions, gap_seconds=60)
        np.testing.assert_array_equal(ids, [0, 0, 0, 1, 1, 2])

    def test_cluster_ids_follow_the_row_back_out_of_order(self):
        second = 1_000_000_000
        # Rows arrive session-ordered, not clock-ordered.
        decisions = np.asarray([400 * second, 0, 10 * second], np.int64)
        ids = _episode_clusters(decisions, gap_seconds=60)
        np.testing.assert_array_equal(ids, [1, 0, 0])

    def test_collapse_ranks_episodes_not_near_duplicate_candidates(self):
        second = 1_000_000_000
        # Three near-duplicate candidates of ONE $0 episode, and one real
        # $900 winner.  Uncollapsed, the flat trio owns three quarters of the
        # list; collapsed, it is one entry carrying its own best gain.
        record = self._record(
            [0.0, 0.0, 0.0, 5.0], [0.0, 0.0, 0.0, 900.0],
            [0, 5 * second, 10 * second, 600 * second])
        without, plain = _memory_value_list_loss(
            [record], collapse_episodes=False)
        with_collapse, collapsed = _memory_value_list_loss(
            [record], collapse_episodes=True, gap_seconds=60)
        self.assertEqual(int(plain["rows"]), 4)
        self.assertEqual(int(collapsed["rows"]), 2)
        self.assertFalse(plain["episode_cluster_collapse"])
        self.assertTrue(collapsed["episode_cluster_collapse"])
        self.assertEqual(int(collapsed["episode_cluster_gap_seconds"]), 60)
        # All the dollar mass is on the winner, and the collapsed list gives
        # the winner a two-way contest instead of a four-way one.
        self.assertLess(float(with_collapse), float(without))

    def test_collapse_takes_the_cluster_max_gain(self):
        second = 1_000_000_000
        # Two candidates in ONE episode: $0 and $900.  Collapsed the episode
        # is worth its best candidate, so the loss matches a single entry.
        record = self._record([0.0, 3.0, 3.0], [0.0, 900.0, 900.0],
                              [0, 5 * second, 600 * second])
        _value, receipt = _memory_value_list_loss(
            [record], collapse_episodes=True, gap_seconds=60)
        self.assertEqual(int(receipt["rows"]), 2)
        self.assertEqual(int(receipt["clusters"]), 2)

    def test_the_gradient_reaches_the_candidate_that_would_be_taken(self):
        second = 1_000_000_000
        scores = torch.tensor([1.0, 4.0, 0.0], requires_grad=True)
        record = {"asset": "HG", "day": 20210701, "session_id": "S",
                  "scores": scores, "gains": torch.tensor([500.0, 500.0, 0.0]),
                  "decisions": np.asarray([0, 5 * second, 600 * second],
                                          np.int64),
                  "rows": 3}
        value, _receipt = _memory_value_list_loss(
            [record], collapse_episodes=True, gap_seconds=60)
        value.backward()
        # Row 1 is the episode's best candidate; row 0 is the sibling it
        # represents and must not be pulled.
        self.assertEqual(float(scores.grad[0]), 0.0)
        self.assertNotEqual(float(scores.grad[1]), 0.0)


class FlatShelfIndifferenceTest(unittest.TestCase):
    """Ruling 2 of the final batch: the KL's indifference IS the intent."""

    def test_a_flat_dollar_shelf_scores_every_ordering_alike(self):
        gains = torch.tensor([300.0, 300.0, 300.0])

        def loss_for(scores):
            value, _receipt = _memory_value_list_loss([{
                "asset": "HG", "day": 20210701, "session_id": "S",
                "scores": torch.as_tensor(scores, dtype=torch.float32),
                "gains": gains,
                "decisions": np.asarray([0, 10 ** 12, 2 * 10 ** 12], np.int64),
                "rows": 3}])
            return float(value)

        # On a shelf the oracle cannot tell rank 1 from rank 3, so neither
        # should the loss: any PERMUTATION of one score set is equivalent.
        self.assertAlmostEqual(loss_for([2.0, 1.0, 0.0]),
                               loss_for([0.0, 1.0, 2.0]), places=6)
        # Flat scores are the minimum on a flat shelf.
        self.assertLess(loss_for([1.0, 1.0, 1.0]), loss_for([5.0, 0.0, 0.0]))


class TwoProbeAcceptanceTest(unittest.TestCase):
    """Section 4: linear + MLP, accept on either, the null must fail both."""

    def _batch(self):
        return _tiny_batch(clock=np.arange(1, 41, dtype=np.int64) * 1_000,
                           cutoffs=np.asarray([10, 20, 30], np.int64),
                           certified_usd=[2_000.0, 700.0, 0.0],
                           frozen_usd=[0.0, 0.0, 0.0])

    def test_probe_kinds_are_typed(self):
        self.assertEqual(MEMORY_VALUE_PROBE_KINDS, ("mlp", "linear"))
        with self.assertRaisesRegex(RealDiagnosticExecutorRefusal, "untyped"):
            MemoryValueProbe(kind="quadratic")

    def test_the_linear_probe_has_no_hidden_layer(self):
        linear = MemoryValueProbe(kind="linear")
        mlp = MemoryValueProbe(kind="mlp")
        self.assertIsInstance(linear.trunk, torch.nn.Flatten)
        self.assertIsInstance(mlp.trunk, torch.nn.Sequential)
        self.assertEqual(linear.util.in_features, 4 * 512)
        self.assertEqual(mlp.util.in_features, 512)

    def test_both_probes_read_the_same_memory_and_score_it(self):
        torch.manual_seed(17)
        batch = self._batch()
        memory = torch.randn(3, 4, 512)
        with torch.no_grad():
            mlp, _c, _r = _memory_value_probe_loss(
                MemoryValueProbe(kind="mlp"), memory, batch)
            linear, _c, _r = _memory_value_probe_loss(
                MemoryValueProbe(kind="linear"), memory, batch)
        self.assertTrue(np.isfinite(float(mlp)))
        self.assertTrue(np.isfinite(float(linear)))

    def test_the_linear_readout_cannot_change_the_training_signal(self):
        # It is an AUDITOR: run on a detached memory it must leave the
        # encoder's gradient untouched.
        torch.manual_seed(19)
        batch = self._batch()
        memory = torch.randn(3, 4, 512, requires_grad=True)
        linear = MemoryValueProbe(kind="linear")
        total, _components, _record = _memory_value_probe_loss(
            linear, memory.detach(), batch)
        total.backward()
        self.assertIsNone(memory.grad)
        self.assertIsNotNone(linear.util.weight.grad)
        self.assertEqual(MEMORY_VALUE_LINEAR_PROBE_LAW,
                         "DETACHED_SECOND_READOUT")

    def test_the_dual_acceptance_rule_is_receipted(self):
        self.assertEqual(
            MEMORY_VALUE_ACCEPTANCE_RULE,
            "EITHER_PROBE_PASSES_SHUFFLED_NULL_FAILS_BOTH")


class WithinSessionShuffleBaselineTest(unittest.TestCase):
    """Section 4: the acceptance baseline is a SIBLING's memory, not zeros."""

    def test_shuffle_permutes_inside_the_session_and_is_deterministic(self):
        memory = torch.arange(6 * 4 * 512, dtype=torch.float32).reshape(6, 4, 512)
        first = _within_session_shuffled_memory(
            memory, seed=MEMORY_VALUE_SHUFFLE_SEED, epoch=0, session_id="S")
        again = _within_session_shuffled_memory(
            memory, seed=MEMORY_VALUE_SHUFFLE_SEED, epoch=0, session_id="S")
        self.assertTrue(torch.equal(first, again))
        self.assertFalse(torch.equal(first, memory))
        # A permutation moves rows; it never invents or drops one.
        self.assertEqual(sorted(float(row[0, 0]) for row in first),
                         sorted(float(row[0, 0]) for row in memory))

    def test_a_different_session_or_epoch_draws_a_different_permutation(self):
        memory = torch.arange(8 * 4 * 512, dtype=torch.float32).reshape(8, 4, 512)
        base = _within_session_shuffled_memory(
            memory, seed=MEMORY_VALUE_SHUFFLE_SEED, epoch=0, session_id="A")
        other_session = _within_session_shuffled_memory(
            memory, seed=MEMORY_VALUE_SHUFFLE_SEED, epoch=0, session_id="B")
        other_epoch = _within_session_shuffled_memory(
            memory, seed=MEMORY_VALUE_SHUFFLE_SEED, epoch=1, session_id="A")
        self.assertFalse(torch.equal(base, other_session))
        self.assertFalse(torch.equal(base, other_epoch))

    def test_a_single_candidate_session_cannot_be_shuffled(self):
        memory = torch.randn(1, 4, 512)
        self.assertTrue(torch.equal(
            _within_session_shuffled_memory(
                memory, seed=MEMORY_VALUE_SHUFFLE_SEED, epoch=0,
                session_id="S"), memory))

    def test_the_shuffled_baseline_is_not_the_zero_baseline(self):
        torch.manual_seed(11)
        probe = MemoryValueProbe()
        clock = np.arange(1, 61, dtype=np.int64) * 1_000
        batch = _tiny_batch(clock=clock,
                            cutoffs=np.asarray([10, 20, 30, 40], np.int64),
                            certified_usd=[2_000.0, 700.0, 100.0, 0.0],
                            frozen_usd=[0.0] * 4)
        memory = torch.randn(4, 4, 512)
        with torch.no_grad():
            live, _c, _r = _memory_value_probe_loss(probe, memory, batch)
            shuffled, _c, _r = _memory_value_probe_loss(
                probe, _within_session_shuffled_memory(
                    memory, seed=MEMORY_VALUE_SHUFFLE_SEED, epoch=0,
                    session_id="S1"), batch)
            zeroed, _c, _r = _memory_value_probe_loss(
                probe, torch.zeros_like(memory), batch)
        self.assertNotAlmostEqual(float(shuffled), float(zeroed), places=4)
        self.assertNotAlmostEqual(float(shuffled), float(live), places=4)
        self.assertEqual(MEMORY_VALUE_BASELINE_LAW,
                         "WITHIN_SESSION_SHUFFLED_MEMORY")


class BaseStageFixReceiptTest(unittest.TestCase):
    """Every law the fix pass introduced is receipted, and typed."""

    def _receipt(self, *, identity_enabled: bool, stop_reason="CONVERGED",
                 governed_override=None,
                 identity_validation_status=None):
        governed = ("oracle", "recon", "memory_value")
        if identity_enabled:
            governed = ("oracle", "recon", "identity", "memory_value")
        if governed_override is not None:
            governed = tuple(governed_override)
        trace = []
        for epoch in range(2):
            row = {"epoch": epoch, "composite": 1.0 - .1 * epoch,
                   "memory_value_shuffled": 1.8,
                   "memory_value_occluded": 2.0,
                   "memory_value_margin": .8,
                   "memory_value_occluded_margin": 1.0,
                   "memory_value_list_coverage": 1.0,
                   "memory_value_linear": 1.2,
                   "memory_value_linear_shuffled": 1.9,
                   "memory_value_linear_margin": .7,
                   "governed": {name: 1.0 for name in governed}}
            trace.append(row)
        return _base_stage_fix_receipt(
            arm="M1" if identity_enabled else "C0", trace=trace,
            governed=governed, epoch_zero={name: 1.0 for name in governed},
            stale_by_trace={name: 0 for name in governed},
            best_composite=.9, best_epoch=1, stop_reason=stop_reason,
            wall_ceiling_s=1_800.0,
            spec=type("S", (), {"minimum_relative_improvement": .001,
                                "patience": 3, "max_epochs": 40})(),
            identity_enabled=identity_enabled, identity_skips={},
            auxiliary_scales={"recon": 1.0, "identity": 1.0,
                              "memory_value": 1.0},
            gradient_share_receipts=(), optimizer_group_receipt={},
            scope_receipt={"scoped_fields": 10},
            validation_window_receipt={"held_rows": 120},
            **({} if identity_validation_status is None
               else {"identity_validation_status": identity_validation_status}))

    def test_broadcast_arms_carry_the_typed_identity_refusal(self):
        receipt = self._receipt(identity_enabled=False)
        self.assertEqual(receipt["identity_status"], IDENTITY_UNAVAILABLE_BROADCAST)
        self.assertEqual(receipt["identity_trace"], IDENTITY_UNAVAILABLE_BROADCAST)
        self.assertNotIn("identity", receipt["governed_traces"])
        self.assertEqual(IDENTITY_UNAVAILABLE_BROADCAST,
                         "IDENTITY_UNAVAILABLE_BROADCAST")

    def test_per_candidate_arms_receipt_a_real_identity_trace(self):
        receipt = self._receipt(identity_enabled=True)
        self.assertEqual(receipt["identity_status"], "TRAINED")
        self.assertEqual(len(receipt["identity_trace"]), 2)
        self.assertIn("identity", receipt["governed_traces"])

    def test_the_discarded_heads_are_receipted_as_never_persisted(self):
        receipt = self._receipt(identity_enabled=True)
        self.assertFalse(receipt["identity_projection_persisted"])
        self.assertFalse(receipt["memory_value_probe_persisted"])

    def test_memory_value_margin_keys_are_present(self):
        receipt = self._receipt(identity_enabled=True)
        self.assertEqual(len(receipt["memory_value_trace"]), 2)
        # The ACCEPTANCE baseline is the shuffled one; zeros are a reference.
        self.assertEqual(len(receipt["memory_value_shuffled_baseline"]), 2)
        self.assertEqual(len(receipt["memory_value_occluded_baseline"]), 2)
        self.assertEqual(receipt["memory_value_baseline_law"],
                         "WITHIN_SESSION_SHUFFLED_MEMORY")
        self.assertEqual(tuple(receipt["memory_value_margin"]), (0.8, 0.8))
        self.assertEqual(tuple(receipt["memory_value_occluded_margin"]),
                         (1.0, 1.0))
        # Outcome-derived weights are lawful in the PROBE channel only.
        self.assertEqual(receipt["memory_value_fit_weight_law"],
                         "OUTCOME_DERIVED_PROBE_CHANNEL_ONLY")
        self.assertEqual(receipt["memory_value_targets"], MEMORY_VALUE_TARGETS)
        self.assertEqual(float(receipt["memory_value_goal_grade_usd"]), 600.0)
        self.assertFalse(receipt["memory_value_internal_weights_measured"])
        self.assertEqual(dict(receipt["memory_value_internal_target_shares"]),
                         {"util": 0.50, "list": 0.30, "tail": 0.20})

    def test_both_probe_traces_are_receipted_for_dual_acceptance(self):
        receipt = self._receipt(identity_enabled=True)
        self.assertEqual(receipt["memory_value_probe_kinds"], ("mlp", "linear"))
        self.assertEqual(len(receipt["memory_value_linear_trace"]), 2)
        self.assertEqual(len(receipt["memory_value_linear_shuffled_baseline"]), 2)
        self.assertEqual(tuple(receipt["memory_value_linear_margin"]),
                         (0.7, 0.7))
        self.assertEqual(receipt["memory_value_acceptance_rule"],
                         MEMORY_VALUE_ACCEPTANCE_RULE)
        self.assertEqual(receipt["memory_value_linear_probe_law"],
                         MEMORY_VALUE_LINEAR_PROBE_LAW)

    def test_the_fit_block_is_receipted(self):
        receipt = self._receipt(identity_enabled=True)
        self.assertEqual(receipt["fit_block_days"],
                         "FULL_COMPETENCE_POPULATION")
        self.assertFalse(receipt["episode_cluster_collapse"])
        self.assertEqual(int(receipt["episode_cluster_gap_seconds"]), 60)

    def test_identity_can_be_dropped_as_a_typed_capability_fact(self):
        # Ruling 5: no multi-window held session is a data-shape fact, not a
        # mechanical defect - identity leaves the governed set, typed.
        receipt = self._receipt(identity_enabled=True, governed_override=(
            "oracle", "recon", "memory_value"),
            identity_validation_status=IDENTITY_VALIDATION_UNAVAILABLE)
        self.assertEqual(receipt["identity_validation"],
                         IDENTITY_VALIDATION_UNAVAILABLE)
        self.assertEqual(receipt["identity_trace"],
                         IDENTITY_VALIDATION_UNAVAILABLE)
        self.assertNotIn("identity", receipt["governed_traces"])
        self.assertEqual(IDENTITY_VALIDATION_UNAVAILABLE,
                         "UNAVAILABLE_NO_MULTI_WINDOW_SESSIONS")

    def test_an_untyped_stop_reason_refuses(self):
        with self.assertRaisesRegex(RealDiagnosticExecutorRefusal, "untyped"):
            self._receipt(identity_enabled=True, stop_reason="GAVE_UP")

    def test_wall_ceiling_is_receipted_but_elapsed_wall_clock_is_not(self):
        receipt = self._receipt(identity_enabled=True)
        self.assertEqual(float(receipt["wall_ceiling_seconds"]), 1_800.0)
        self.assertNotIn("elapsed_seconds", receipt)
        self.assertNotIn("base_stage_s", receipt)

    def test_the_receipt_is_canonically_hashable(self):
        from .neural_sufficiency_resources import _sha
        receipt = self._receipt(identity_enabled=True)
        first = _sha(receipt)
        self.assertEqual(first, _sha(self._receipt(identity_enabled=True)))
        self.assertEqual(len(first), 64)
        self.assertNotEqual(first, _sha(self._receipt(identity_enabled=False)))

    def test_auxiliary_weights_are_flagged_unmeasured(self):
        receipt = self._receipt(identity_enabled=True)
        self.assertFalse(receipt["auxiliary_weights_measured"])
        self.assertFalse(receipt["auxiliary_share_caps_measured"])
        self.assertEqual(receipt["auxiliary_weights_todo"], AUX_WEIGHT_TODO)
        self.assertEqual(receipt["auxiliary_weights"],
                         {"recon": AUX_RECON_WEIGHT,
                          "identity": AUX_IDENTITY_WEIGHT,
                          "memory_value": AUX_MEMORY_VALUE_WEIGHT})


class AuxiliaryShareLawTest(unittest.TestCase):
    """F3: measured shares, receipted conflict cosine, and the share caps."""

    def test_share_cap_downscales_only_the_over_target_auxiliary(self):
        scales = _auxiliary_share_scales(
            {"oracle": .5, "recon": .4, "identity": .05, "memory_value": .05},
            {"recon": .2, "identity": .2, "memory_value": .2})
        self.assertAlmostEqual(scales["recon"], .5)
        self.assertEqual(scales["identity"], 1.0)
        self.assertEqual(scales["memory_value"], 1.0)

    def test_caps_carry_the_pre_registered_targets_with_headroom(self):
        # Ruling 2 / pre-registration section 7: targets ~15/20/35-40%, caps
        # sit above them so an on-target auxiliary is never throttled.
        self.assertEqual(dict(AUX_SHARE_CAPS),
                         {"recon": 0.20, "identity": 0.25,
                          "memory_value": 0.45})
        self.assertFalse(AUX_SHARE_CAPS_MEASURED)
        self.assertFalse(AUX_WEIGHTS_MEASURED)
        self.assertEqual(GRADIENT_SHARE_MEASUREMENT_EPOCHS, (0, 3))

    def test_encoder_gradient_shares_and_conflict_cosine(self):
        class _Tiny(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.encoder = torch.nn.Linear(4, 4, bias=False)

        model = _Tiny()
        with torch.no_grad():
            model.encoder.weight.copy_(torch.eye(4))
        inputs = torch.ones(1, 4)
        state = model.encoder(inputs)
        shares = _encoder_gradient_shares(model, {
            "oracle": state.sum(), "recon": (2.0 * state).sum(),
            "identity": (-1.0 * state).sum(), "memory_value": None})
        self.assertAlmostEqual(
            sum(shares["encoder_gradient_share"].values()), 1.0, places=6)
        self.assertAlmostEqual(shares["cosine_to_oracle"]["recon"], 1.0, places=5)
        self.assertAlmostEqual(shares["cosine_to_oracle"]["identity"], -1.0,
                               places=5)
        self.assertEqual(shares["encoder_gradient_l1"]["memory_value"], 0.0)


class M1StabilityLawTest(unittest.TestCase):
    """R8: the GRU banks get their own lr group and the first epoch warms up."""

    def test_non_m1_arms_keep_one_group_and_no_warmup(self):
        model = torch.nn.Sequential(torch.nn.Linear(2, 2))
        groups, receipt = _base_stage_parameter_groups(model, "L0", 1e-3)
        self.assertEqual(len(groups), 1)
        self.assertEqual(receipt["warmup_epochs"], 0)
        self.assertIsNone(receipt["encoder_gru_lr_scale"])

    def test_m1_named_gru_banks_take_the_scaled_lr(self):
        class _M1(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.encoder = torch.nn.Module()
                self.encoder.gru_60 = torch.nn.GRU(2, 2)
                self.encoder.gru_300 = torch.nn.GRU(2, 2)
                self.encoder.gru_900 = torch.nn.GRU(2, 2)
                self.encoder.gru_full = torch.nn.GRU(2, 2)
                self.encoder.other = torch.nn.Linear(2, 2)
                self.head = torch.nn.Linear(2, 2)

        groups, receipt = _base_stage_parameter_groups(_M1(), "M1", 1e-3)
        self.assertEqual([group["name"] for group in groups],
                         ["encoder_gru", "rest"])
        self.assertAlmostEqual(groups[0]["lr"], 1e-3 * M1_ENCODER_GRU_LR_SCALE)
        self.assertAlmostEqual(groups[1]["lr"], 1e-3)
        self.assertEqual(receipt["warmup_epochs"], M1_WARMUP_EPOCHS)
        self.assertEqual(int(receipt["encoder_gru_parameter_tensors"]), 16)

    def test_an_empty_gru_group_refuses(self):
        model = torch.nn.Sequential(torch.nn.Linear(2, 2))
        with self.assertRaisesRegex(RealDiagnosticExecutorRefusal,
                                    "GRU-bank parameter group"):
            _base_stage_parameter_groups(model, "M1", 1e-3)

    def test_linear_warmup_reaches_full_lr_at_the_end_of_the_first_epoch(self):
        parameter = torch.zeros(1, requires_grad=True)
        optimizer = torch.optim.SGD([{"params": [parameter], "lr": 1e-3}])
        scales = [_apply_linear_warmup(optimizer, [1e-3], epoch=0, step=step,
                                       steps_per_epoch=4, warmup_epochs=1)
                  for step in range(4)]
        self.assertEqual(scales, [.25, .5, .75, 1.0])
        self.assertAlmostEqual(optimizer.param_groups[0]["lr"], 1e-3)
        self.assertEqual(
            _apply_linear_warmup(optimizer, [1e-3], epoch=3, step=0,
                                 steps_per_epoch=4, warmup_epochs=0), 1.0)


class ValidationWindowLawTest(unittest.TestCase):
    """Section 4.5: the held reconstruction slice must be able to certify."""

    def _batches(self, days: int, rows_per_day: int):
        clock = np.arange(1, rows_per_day + 21, dtype=np.int64) * 1_000
        return [
            _tiny_batch(clock=clock,
                        cutoffs=np.asarray(
                            [10 + index for index in range(rows_per_day)],
                            np.int64),
                        day=20210700 + day, session_id=f"S{day}")
            for day in range(1, days + 1)]

    def test_window_widens_to_the_hundred_row_floor_on_a_large_population(self):
        # 40 days x 40 rows = 1600 rows: 100 is well under a quarter, so the
        # absolute floor binds and the window stops there.
        days, receipt = _widened_validation_days(self._batches(40, 40))
        self.assertEqual(int(receipt["effective_minimum_held_rows"]),
                         RECONSTRUCTION_VALIDATION_MINIMUM_ROWS)
        self.assertGreaterEqual(int(receipt["held_rows"]),
                                RECONSTRUCTION_VALIDATION_MINIMUM_ROWS)
        self.assertTrue(receipt["meets_minimum"])
        self.assertTrue(receipt["meets_absolute_minimum"])
        self.assertLessEqual(float(receipt["held_fraction"]),
                             RECONSTRUCTION_VALIDATION_MAXIMUM_HELD_FRACTION)
        self.assertEqual(len(days), int(receipt["trailing_days"]))

    def test_a_small_population_never_pays_more_than_a_quarter_of_itself(self):
        # Ruling 3: 20 days x 10 rows = 200 rows.  The old law would have held
        # 100 of them (half the competence population); the quarter cap stops
        # the window at 50.
        days, receipt = _widened_validation_days(self._batches(20, 10))
        self.assertEqual(int(receipt["total_rows"]), 200)
        self.assertEqual(int(receipt["effective_minimum_held_rows"]), 50)
        self.assertEqual(int(receipt["held_rows"]), 50)
        self.assertEqual(int(receipt["training_rows"]), 150)
        self.assertAlmostEqual(float(receipt["held_fraction"]), 0.25)
        self.assertTrue(receipt["meets_minimum"])
        self.assertFalse(receipt["meets_absolute_minimum"])
        self.assertEqual(len(days), 5)
        self.assertEqual(RECONSTRUCTION_VALIDATION_MAXIMUM_HELD_FRACTION, 0.25)

    def test_a_wide_enough_baseline_window_is_left_alone(self):
        _days, receipt = _widened_validation_days(self._batches(20, 60))
        self.assertEqual(int(receipt["trailing_days"]),
                         int(receipt["baseline_trailing_days"]))

    def test_a_fold_fit_block_keeps_its_held_window_inside_itself(self):
        # The critical fold property: the stage's own trailing held window is
        # carved out of the FOLD's fit block, so training never sees a day the
        # fold will score on.
        batches = self._batches(30, 10)
        fit_days = sorted({int(batch.day) for batch in batches})[:20]
        score_days = sorted({int(batch.day) for batch in batches})[20:25]
        fit_batches = [batch for batch in batches
                       if int(batch.day) in set(fit_days)]
        days, receipt = _widened_validation_days(fit_batches)
        self.assertTrue(set(days) <= set(fit_days))
        self.assertFalse(set(days) & set(score_days))
        self.assertGreaterEqual(int(receipt["training_rows"]), 1)

    def test_at_least_one_training_day_always_survives(self):
        days, receipt = _widened_validation_days(self._batches(3, 2))
        self.assertLessEqual(len(days), 2)
        self.assertGreaterEqual(int(receipt["training_rows"]), 1)
        self.assertFalse(receipt["meets_absolute_minimum"])
        self.assertEqual(RECONSTRUCTION_VALIDATION_MINIMUM_ROWS, 100)


class InnerFoldCalendarTest(unittest.TestCase):
    """Section 4: forward-chained day-blocked folds, strictly inside the era."""

    @staticmethod
    def _harness():
        import importlib.util
        from pathlib import Path
        path = (Path(__file__).resolve().parents[2]
                / "harness" / "encoder_harness.py")
        spec = importlib.util.spec_from_file_location("_encoder_harness", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _days(self, count=30):
        # A plausible trading calendar inside the fit era plus CONFIRM days
        # that must never be touched.
        july = [20210700 + day for day in range(1, 32)]
        august = [20210800 + day for day in range(1, 14)]
        return [day for day in july + august][:count + 13]

    def test_folds_are_forward_chained_and_day_blocked(self):
        harness = self._harness()
        previous_fit = None
        for fold in (1, 2, 3):
            calendar = harness.fold_calendar(self._days(), fold)
            self.assertEqual(len(calendar["fit_days"]), 7 + 5 * fold)
            self.assertEqual(len(calendar["score_days"]), 5)
            self.assertFalse(set(calendar["fit_days"])
                             & set(calendar["score_days"]))
            # Forward chaining: each fold's fit block extends the last.
            if previous_fit is not None:
                self.assertEqual(calendar["fit_days"][:len(previous_fit)],
                                 previous_fit)
            previous_fit = calendar["fit_days"]
            # The fit block always precedes the scored block in time.
            self.assertLess(max(calendar["fit_days"]),
                            min(calendar["score_days"]))

    def test_no_fold_ever_scores_past_the_confirm_wall(self):
        harness = self._harness()
        for fold in (1, 2, 3):
            calendar = harness.fold_calendar(self._days(), fold)
            self.assertTrue(all(day < 20210802
                                for day in calendar["score_days"]))
            self.assertTrue(all(day <= 20210801
                                for day in calendar["fit_days"]))

    def test_the_calendar_comes_from_the_days_the_corpus_carries(self):
        harness = self._harness()
        # A real calendar has weekends and holidays: the fold must count the
        # days the corpus HAS, never a nominal 7+5k span of the month.
        sparse = [20210701, 20210702, 20210706, 20210707, 20210708,
                  20210709, 20210712, 20210713, 20210714, 20210715,
                  20210716, 20210719, 20210720, 20210721, 20210722,
                  20210723, 20210726]
        calendar = harness.fold_calendar(sparse, 1)
        self.assertEqual(list(calendar["fit_days"]), sparse[:12])
        self.assertEqual(list(calendar["score_days"]), sparse[12:17])
        # 22 fit + 5 scored days do not exist here; the amended law (the
        # real diagnostic corpus carries only 8 pre-CONFIRM days) falls back
        # to chained proportional folds: 2-day score blocks carved from the
        # era's end, fold 3 taking the final block.
        calendar3 = harness.fold_calendar(sparse, 3)
        self.assertEqual(list(calendar3["fit_days"]), sparse[:15])
        self.assertEqual(list(calendar3["score_days"]), sparse[15:17])
        self.assertEqual(calendar3["fit_days"][-1], 20210722)

    def test_a_short_corpus_refuses_rather_than_running_a_short_fold(self):
        harness = self._harness()
        # Even the proportional fallback needs >=4 fit days + a 2-day score
        # block; a 2-day corpus refuses with the typed unavailability.
        with self.assertRaisesRegex(ValueError, "proportional fold"):
            harness.fold_calendar([20210701, 20210702], 1)

    def test_an_untyped_fold_refuses(self):
        harness = self._harness()
        with self.assertRaisesRegex(ValueError, "fold must be one of"):
            harness.fold_calendar(self._days(), 4)


class EncoderHarnessAcceptanceMetricTest(unittest.TestCase):
    """The acceptance currency: ARRIVAL-ORDER goal-grade dollars.

    Hindsight top-3 was a lookahead coordinate system - the cap fills
    chronologically.  These tests pin the deployable rule, both cap laws, the
    shuffled baseline, the report-only theta columns and tail visibility.
    """

    @staticmethod
    def _harness():
        return InnerFoldCalendarTest._harness()

    def _data_root(self, rows_by_day):
        import tempfile
        from pathlib import Path
        root = Path(tempfile.mkdtemp())
        self.addCleanup(__import__("shutil").rmtree, root, True)
        for (asset, day), rows in rows_by_day.items():
            (root / "g1" / "candidates" / asset).mkdir(parents=True, exist_ok=True)
            (root / "g1" / "teacher" / asset).mkdir(parents=True, exist_ok=True)
            candidates = ["# provenance header",
                          "candidate_id\tfrozen_cost_usd"]
            teacher = ["# provenance header",
                       "candidate_id\tcert_close_usd\tcompliance_status"]
            for candidate_id, frozen, certified, status in rows:
                candidates.append(f"{candidate_id}\t{frozen}")
                teacher.append(f"{candidate_id}\t{certified}\t{status}")
            (root / "g1" / "candidates" / asset / f"{day}.tsv").write_text(
                "\n".join(candidates) + "\n")
            (root / "g1" / "teacher" / asset / f"{day}.tsv").write_text(
                "\n".join(teacher) + "\n")
        return str(root)

    def test_ledger_carries_net_dollars_and_goal_grade(self):
        harness = self._harness()
        root = self._data_root({("HG", 20210813): [
            ("a", 10.0, 1_110.0, "CLEAR"),
            ("b", 5.0, 500.0, "READY"),
            ("c", 1.0, 900.0, "BLOCKED")]})
        ledger = harness.day_dollar_ledger(root, "HG", 20210813)
        self.assertEqual(set(ledger), {"a", "b"})
        self.assertAlmostEqual(ledger["a"]["net_usd"], 1_100.0)
        self.assertEqual(ledger["a"]["goal_grade"], 1)
        self.assertEqual(ledger["b"]["goal_grade"], 0)
        self.assertEqual(harness.GOAL_GRADE_USD, 600.0)

    def test_the_amended_law_is_portfolio_twelve_with_no_per_asset_cap(self):
        harness = self._harness()
        self.assertEqual(harness.AMENDED_LAW["budget"], 12)
        self.assertIsNone(harness.AMENDED_LAW["per_asset_cap"])
        self.assertEqual(harness.LEGACY_LAW["budget"], 9)
        self.assertEqual(harness.LEGACY_LAW["per_asset_cap"], 3)
        self.assertEqual(harness.PORTFOLIO_GOAL_USD_DAY, 7_000.0)
        self.assertEqual(harness.PORTFOLIO_MINIMUM_USD_DAY, 6_000.0)

    def test_arrival_order_is_not_hindsight_order(self):
        # The winner arrives LAST.  A hindsight top-1 takes it; the arrival
        # rule with a budget of 1 has already spent the budget on the early
        # candidate that cleared theta.  That gap is the haircut.
        harness = self._harness()
        decisions = [10, 20, 30]
        assets = ["HG", "HG", "HG"]
        nets = [100.0, 0.0, 5_000.0]
        scores = [9.0, 0.0, 8.0]
        total, _per_asset, picks, _taken = harness._run_arrival_rule(
            [0, 1, 2], decisions, assets, nets, scores,
            budget=1, per_asset_cap=None, theta=1.0)
        self.assertEqual(picks, [0])
        self.assertAlmostEqual(total, 100.0)
        self.assertAlmostEqual(harness._hindsight_top3([0, 1, 2], nets, scores),
                               5_100.0)

    def test_the_per_asset_cap_costs_deployable_ceiling(self):
        # Section 9's measured finding, in miniature: the winners cluster on
        # one asset, and the 3-per-asset cap leaves money on the table that a
        # portfolio budget collects.
        harness = self._harness()
        decisions = list(range(8))
        assets = ["NKD"] * 5 + ["HG"] * 3
        nets = [1_000.0] * 5 + [10.0] * 3
        scores = [5.0] * 8
        capped, _pa, capped_picks, _t = harness._run_arrival_rule(
            list(range(8)), decisions, assets, nets, scores,
            budget=9, per_asset_cap=3, theta=1.0)
        portfolio, _pa, portfolio_picks, _t = harness._run_arrival_rule(
            list(range(8)), decisions, assets, nets, scores,
            budget=12, per_asset_cap=None, theta=1.0)
        self.assertEqual(len(capped_picks), 6)
        self.assertEqual(len(portfolio_picks), 8)
        self.assertAlmostEqual(capped, 3_030.0)
        self.assertAlmostEqual(portfolio, 5_030.0)
        self.assertGreater(portfolio, capped)

    def test_the_portfolio_budget_binds_at_twelve(self):
        harness = self._harness()
        decisions = list(range(20))
        assets = ["HG"] * 20
        nets = [100.0] * 20
        scores = [5.0] * 20
        total, _pa, picks, _t = harness._run_arrival_rule(
            list(range(20)), decisions, assets, nets, scores,
            budget=12, per_asset_cap=None, theta=1.0)
        self.assertEqual(len(picks), 12)
        self.assertAlmostEqual(total, 1_200.0)

    def test_the_oracle_variant_is_a_perfect_classifier_under_the_same_rule(self):
        harness = self._harness()
        decisions = [1, 2, 3, 4]
        assets = ["HG"] * 4
        nets = [-50.0, 900.0, -20.0, 700.0]
        goal_grade = [0, 1, 0, 1]
        total, _pa, picks, _t = harness._run_arrival_rule(
            [0, 1, 2, 3], decisions, assets, nets, scores=[0.0] * 4,
            budget=12, per_asset_cap=None, goal_grade=goal_grade)
        self.assertEqual(picks, [1, 3])
        self.assertAlmostEqual(total, 1_600.0)

    def test_theta_is_frozen_on_train_days_and_reports_its_quantile(self):
        import numpy as np
        harness = self._harness()
        decisions = list(range(40))
        assets = ["HG"] * 40
        nets = [100.0] * 40
        scores = np.linspace(0.0, 1.0, 40)
        day_rows = {1: np.arange(0, 20), 2: np.arange(20, 40)}
        theta, quantile = harness._calibrate_theta(
            [1, 2], day_rows, decisions, assets, nets, scores,
            budget=12, per_asset_cap=None)
        self.assertIsNotNone(theta)
        self.assertIn(quantile, harness.THETA_QUANTILE_GRID)

    def test_trailing_theta_reads_the_last_five_scored_days(self):
        import numpy as np
        harness = self._harness()
        # Day k carries scores centred on k; the trailing window must follow.
        day_rows = {day: np.arange(10 * day, 10 * day + 10)
                    for day in range(1, 9)}
        scores = np.concatenate([np.full(10, 0.0)]
                                + [np.full(10, float(day))
                                   for day in range(1, 9)])
        early = harness._trailing_theta([1, 2], day_rows, scores, 0.9)
        late = harness._trailing_theta([1, 2, 3, 4, 5, 6, 7], day_rows,
                                       scores, 0.9)
        self.assertLess(early, late)
        # Only the last five scored days count.
        self.assertAlmostEqual(
            late, float(np.quantile(np.concatenate(
                [scores[day_rows[day]] for day in (3, 4, 5, 6, 7)]), 0.9)))

    def test_trailing_theta_has_nothing_to_read_on_the_first_day(self):
        import numpy as np
        harness = self._harness()
        day_rows = {1: np.arange(0, 10)}
        self.assertIsNone(harness._trailing_theta([], day_rows,
                                                  np.zeros(10), 0.9))

    def test_rank_normalization_puts_every_asset_on_its_own_scale(self):
        import numpy as np
        harness = self._harness()
        # HG scores live near +100, SI near -100.  A shared raw theta would
        # let HG hog the budget; on their own train-day CDFs they are
        # comparable.
        assets = ["HG"] * 10 + ["SI"] * 10
        days = [1] * 5 + [2] * 5 + [1] * 5 + [2] * 5
        scores = np.concatenate([np.linspace(100, 110, 10),
                                 np.linspace(-110, -100, 10)])
        normalized = harness.rank_normalize(scores, assets, days,
                                            train_days=[1])
        # Each asset's own top score maps near 1.0 on its own CDF.
        self.assertGreater(normalized[9], 0.9)
        self.assertGreater(normalized[19], 0.9)
        self.assertLess(normalized[0], 0.5)
        self.assertLess(normalized[10], 0.5)

    def test_per_asset_score_quantiles_are_reported_on_held_days(self):
        import numpy as np
        harness = self._harness()
        assets = ["HG"] * 10 + ["SI"] * 10
        days = [20210813] * 20
        scores = np.concatenate([np.linspace(0, 1, 10),
                                 np.linspace(10, 11, 10)])
        quantiles = harness.score_quantiles(scores, assets, days, [20210813])
        self.assertEqual(set(quantiles["HG"]), {"p50", "p90", "p99"})
        self.assertLess(quantiles["HG"]["p50"], quantiles["SI"]["p50"])

    def test_tail_visibility_is_auroc_within_the_winners(self):
        import numpy as np
        harness = self._harness()
        assets = ["HG"] * 12
        nets = [float(100 * (index + 1)) for index in range(12)]
        goal_grade = [1] * 12
        held = [True] * 12
        perfect = harness.tail_visibility(
            assets, nets, goal_grade, np.asarray(nets), held)
        inverted = harness.tail_visibility(
            assets, nets, goal_grade, -np.asarray(nets), held)
        self.assertAlmostEqual(perfect["HG"], 1.0)
        self.assertAlmostEqual(inverted["HG"], 0.0)

    def test_tail_visibility_refuses_to_invent_a_number_on_a_thin_slice(self):
        import numpy as np
        harness = self._harness()
        assets = ["HG"] * 4
        result = harness.tail_visibility(
            assets, [1.0, 2.0, 3.0, 4.0], [1, 1, 1, 1],
            np.asarray([1.0, 2.0, 3.0, 4.0]), [True] * 4)
        self.assertIsNone(result["HG"])

    def test_a_fold_never_calibrates_theta_outside_its_own_fit_block(self):
        # The competence population reaches past the fold era.  A day the
        # fold never fit on must not enter theta calibration, the scored
        # block, or the tail column.
        harness = self._harness()
        from types import SimpleNamespace
        rows_by_day = {}
        names = []
        for day in (20210701, 20210702, 20210703, 20210930):
            day_rows = []
            for index in range(4):
                name = f"{day}-{index}"
                names.append(name)
                day_rows.append((name, 0.0, 2_000.0 if index else 0.0, "CLEAR"))
            rows_by_day[("HG", day)] = day_rows
        root = self._data_root(rows_by_day)

        class _Probe(torch.nn.Module):
            def forward(self, memory):
                score = memory.reshape(memory.shape[0], -1)[:, 0]
                return (score, torch.zeros_like(score),
                        torch.zeros(memory.shape[0], 5))

        memories = {name: torch.full((4, 512), 1.0) for name in names}
        batches = [SimpleNamespace(
            asset="HG", day=day, session_id=f"s{day}",
            candidate_ids=tuple(f"{day}-{index}" for index in range(4)))
            for day in (20210701, 20210702, 20210703, 20210930)]
        rows = SimpleNamespace(
            candidate_id=np.asarray(names),
            asset=np.asarray(["HG"] * len(names)),
            day=np.asarray([int(name.split("-")[0]) for name in names]),
            decision_ts_ns=np.asarray(list(range(len(names)))))
        result = harness.arrival_acceptance(
            rows, memories, {"mlp": _Probe()}, device=torch.device("cpu"),
            data_root=root, held_days=frozenset({20210703}), batches=batches,
            shuffle_seed=20260819, train_days=(20210701, 20210702))
        self.assertEqual(result["train_day_list"], [20210701, 20210702])
        self.assertEqual(result["held_days"], [20210703])
        self.assertNotIn(20210930, result["train_day_list"])

    def test_within_session_shuffle_moves_memories_inside_the_session(self):
        harness = self._harness()
        from types import SimpleNamespace
        batches = [
            SimpleNamespace(asset="HG", day=20210813, session_id="s1",
                            candidate_ids=("a", "b", "c")),
            SimpleNamespace(asset="SI", day=20210813, session_id="s2",
                            candidate_ids=("d", "e", "f")),
        ]
        memories = {name: torch.full((4, 512), float(index))
                    for index, name in enumerate("abcdef")}
        shuffled = harness.within_session_shuffled_memories(
            batches, memories, seed=20260819)
        first = {float(shuffled[name][0, 0]) for name in "abc"}
        second = {float(shuffled[name][0, 0]) for name in "def"}
        self.assertEqual(first, {0.0, 1.0, 2.0})
        self.assertEqual(second, {3.0, 4.0, 5.0})
        self.assertNotEqual([float(shuffled[name][0, 0]) for name in "abc"],
                            [0.0, 1.0, 2.0])

    def test_full_acceptance_reports_both_laws_both_probes_and_the_verdict(self):
        harness = self._harness()
        from types import SimpleNamespace
        rows_by_day = {}
        names = []
        for day in (20210801, 20210802, 20210813):
            day_rows = []
            for index in range(6):
                name = f"{day}-{index}"
                names.append(name)
                certified = 2_000.0 if index >= 4 else 100.0
                day_rows.append((name, 0.0, certified, "CLEAR"))
            rows_by_day[("HG", day)] = day_rows
        root = self._data_root(rows_by_day)

        class _Probe(torch.nn.Module):
            def forward(self, memory):
                score = memory.reshape(memory.shape[0], -1)[:, 0]
                return (score, torch.zeros_like(score),
                        torch.zeros(memory.shape[0], 5))

        memories = {}
        batches = []
        for day in (20210801, 20210802, 20210813):
            ids = tuple(f"{day}-{index}" for index in range(6))
            batches.append(SimpleNamespace(
                asset="HG", day=day, session_id=f"s{day}", candidate_ids=ids))
            for index, name in enumerate(ids):
                memories[name] = torch.full(
                    (4, 512), 5.0 if index >= 4 else -5.0)
        rows = SimpleNamespace(
            candidate_id=np.asarray(names),
            asset=np.asarray(["HG"] * len(names)),
            day=np.asarray([int(name.split("-")[0]) for name in names]),
            decision_ts_ns=np.asarray([index for index in range(len(names))]))
        result = harness.arrival_acceptance(
            rows, memories, {"mlp": _Probe(), "linear": _Probe()},
            device=torch.device("cpu"), data_root=root,
            held_days=frozenset({20210813}), batches=batches,
            shuffle_seed=20260819)
        self.assertEqual(int(result["days"]), 1)
        self.assertEqual(set(result["probes"]), {"mlp", "linear"})
        law = harness.AMENDED_LAW["name"]
        entry = result["probes"]["mlp"]["rules"][law]
        self.assertEqual(int(entry["budget"]), 12)
        self.assertIsNone(entry["per_asset_cap"])
        self.assertGreater(entry["memory"]["portfolio_usd_day"],
                           entry["shuffled"]["portfolio_usd_day"])
        self.assertTrue(entry["beats_shuffled"])
        self.assertGreaterEqual(entry["oracle"]["portfolio_usd_day"],
                                entry["memory"]["portfolio_usd_day"])
        # Every report-only column is present alongside the frozen one.
        self.assertIn("memory_trailing_quantile", entry)
        self.assertIn("memory_rank_normalized", entry)
        self.assertIn("per_asset_pick_share", entry["memory"])
        # Dual acceptance is decided, not implied.
        verdict = result["dual"][law]
        self.assertTrue(verdict["accepted_either"])
        self.assertIn("null_fails_both", verdict)
        self.assertIn("accepted", verdict)
        self.assertEqual(set(verdict["per_probe_beats_shuffled"]),
                         {"mlp", "linear"})
        self.assertIn("HG", result["probes"]["mlp"]["score_quantiles"])


class BaseStageInnerLoopSmokeTest(unittest.TestCase):
    """The session-batch InfoNCE gather is exactly the class that bit gate-5.

    One real inner training step over a real encoder + the real shared head:
    oracle stack, scoped reconstruction, memory-value probe and candidate
    identity composed into ONE backward, with the same gradient-presence
    checks the base stage enforces.
    """

    def test_one_full_inner_step_composes_and_backpropagates(self):
        from .neural_sufficiency_model import (
            NeuralSufficiencyModel, SharedCandidateDecisionHead)
        from .neural_sufficiency_resources import (
            AUX_IDENTITY_WEIGHT as identity_weight,
            AUX_MEMORY_VALUE_WEIGHT as value_weight,
            AUX_RECON_WEIGHT as recon_weight,
            _actual_multitask_loss)
        torch.manual_seed(20260819)
        encoder = _tiny_encoder()
        head = SharedCandidateDecisionHead(len(CANDIDATE_FEATURE_SCHEMA), 3, 2)
        model = NeuralSufficiencyModel(encoder, head)
        batch = _tiny_batch(clock=np.arange(1, 121, dtype=np.int64) * 1_000,
                            cutoffs=np.asarray([40, 70, 100], np.int64),
                            certified_usd=[2_000.0, 700.0, 0.0],
                            frozen_usd=[100.0, 100.0, 100.0])
        scope = reconstruction_target_scope(
            tuple(f"raw.f{index}" for index in range(N_CONTINUOUS)))
        decoder = LastRowReconstructionProbe(N_CONTINUOUS, CATEGORY_SIZES)
        projection = CandidateIdentityProjection()
        probe = MemoryValueProbe()
        out = model(
            event_continuous=batch.continuous,
            event_categorical=batch.categorical,
            receive_clock_ns=batch.clock,
            candidate_cutoffs=batch.cutoffs,
            candidate_decision_ts_ns=batch.decisions,
            candidate_features=batch.candidate_features,
            context_values=batch.context_values,
            context_type_ids=batch.context_type_ids,
            context_valid=batch.context_valid,
            asset_idx=C.ASSET_INDEX[batch.asset], static_features=None)
        self.assertEqual(tuple(out.raw_memory.shape), (3, 4, 512))
        weights = {name: torch.full((3,), 1 / 3) for name in
                   ("action", "base", "top3", "wall")}
        oracle, _components = _actual_multitask_loss(out, batch, weights)
        recon, _c, _k = _field_reconstruction_loss(
            decoder, out.raw_memory, batch, weights["base"],
            continuous_scope=scope)
        value, _v, value_record = _memory_value_probe_loss(
            probe, out.raw_memory, batch)
        listwise, list_receipt = _memory_value_list_loss([value_record])
        self.assertIn("decisions", value_record)
        if listwise is not None:
            value = value + listwise
        record, skipped = _identity_cropped_views(
            model.encoder, batch, out.raw_memory, projection,
            device=torch.device("cpu"), seed=5)
        self.assertIsNone(skipped)
        identity, identity_receipt = _candidate_identity_loss([record])
        shares = _encoder_gradient_shares(model, {
            "oracle": oracle, "recon": recon, "identity": identity,
            "memory_value": value})
        self.assertAlmostEqual(
            sum(shares["encoder_gradient_share"].values()), 1.0, places=5)
        model.zero_grad(set_to_none=True)
        total = (oracle + recon_weight * recon + value_weight * value
                 + identity_weight * identity)
        total.backward()
        encoder_grad = sum(float(p.grad.abs().sum())
                           for p in model.encoder.parameters()
                           if p.grad is not None)
        head_grad = sum(float(p.grad.abs().sum())
                        for p in model.head.parameters() if p.grad is not None)
        decoder_grad = sum(float(p.grad.abs().sum())
                           for p in decoder.parameters() if p.grad is not None)
        projection_grad = sum(float(p.grad.abs().sum())
                              for p in projection.parameters()
                              if p.grad is not None)
        probe_grad = sum(float(p.grad.abs().sum())
                         for p in probe.parameters() if p.grad is not None)
        for name, value_ in (("encoder", encoder_grad), ("head", head_grad),
                             ("decoder", decoder_grad),
                             ("projection", projection_grad),
                             ("probe", probe_grad)):
            self.assertGreater(value_, 0.0, f"{name} received no gradient")
        self.assertTrue(np.isfinite(float(total.detach())))
        self.assertGreaterEqual(int(identity_receipt["rows"]), 2)
        self.assertGreaterEqual(float(list_receipt["list_coverage"]), 0.0)
        # The acceptance baseline runs on the SAME batch, same probe.
        with torch.no_grad():
            shuffled, _c, _r = _memory_value_probe_loss(
                probe, _within_session_shuffled_memory(
                    out.raw_memory, seed=MEMORY_VALUE_SHUFFLE_SEED, epoch=0,
                    session_id=str(batch.session_id)), batch)
        self.assertTrue(np.isfinite(float(shuffled)))



if __name__ == "__main__":
    unittest.main()
