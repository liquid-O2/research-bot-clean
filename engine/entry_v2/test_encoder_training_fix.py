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
    RealDiagnosticExecutorRefusal, _PerComponentGovernor,
    _apply_linear_warmup, _auxiliary_share_scales,
    _base_stage_fix_receipt, _base_stage_parameter_groups,
    _candidate_identity_loss, _CandidateBatch, _encoder_gradient_shares,
    _field_reconstruction_loss, _identity_cropped_views,
    _memory_value_probe_loss, _widened_validation_days,
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
                seed: int = 11) -> _CandidateBatch:
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
        candidate_features=torch.randn(candidates, 8, generator=generator),
        context_values=torch.zeros(candidates, 2, 4, 3),
        context_type_ids=torch.zeros(2, dtype=torch.long),
        context_valid=torch.ones(candidates, 2, 4, dtype=torch.bool),
        static_features=torch.zeros(candidates, 1_865),
        targets=torch.randint(0, 2, (candidates,), generator=generator).float(),
        action_loss_mask=torch.ones(candidates, dtype=torch.bool),
        oracle_targets={
            "value_bin": torch.randint(0, 5, (candidates,), generator=generator),
            "value": torch.randn(candidates, generator=generator),
            "top3": torch.randint(0, 2, (candidates,), generator=generator).float(),
            "rank": torch.randn(candidates, generator=generator),
            "mfe": torch.randn(candidates, generator=generator),
            "mae": torch.randn(candidates, generator=generator),
            "wall": torch.randint(0, 2, (candidates,), generator=generator).float(),
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
    import dataclasses
    return dataclasses.replace(batch, last_continuous=values)


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
    """R2: the dollars bridge reads the RAW MEMORY and nothing else."""

    def _batch(self):
        return _tiny_batch(clock=np.arange(1, 41, dtype=np.int64) * 1_000,
                           cutoffs=np.asarray([10, 20, 30], np.int64))

    def test_probe_gradient_reaches_the_memory(self):
        batch = self._batch()
        probe = MemoryValueProbe()
        memory = torch.randn(3, 4, 512, requires_grad=True)
        loss, components = _memory_value_probe_loss(probe, memory, batch)
        loss.backward()
        self.assertIsNotNone(memory.grad)
        self.assertGreater(float(memory.grad.abs().sum()), 0.0)
        self.assertEqual(set(components), {"value_bin", "top3", "action"})

    def test_occluding_the_memory_changes_the_probe_loss(self):
        batch = self._batch()
        probe = MemoryValueProbe()
        memory = torch.randn(3, 4, 512)
        with torch.no_grad():
            live, _ = _memory_value_probe_loss(probe, memory, batch)
            occluded, _ = _memory_value_probe_loss(
                probe, torch.zeros_like(memory), batch)
        self.assertNotAlmostEqual(float(live), float(occluded))

    def test_negative_fit_weights_refuse(self):
        batch = self._batch()
        probe = MemoryValueProbe()
        with self.assertRaisesRegex(RealDiagnosticExecutorRefusal,
                                    "memory-value probe fit weights"):
            _memory_value_probe_loss(probe, torch.randn(3, 4, 512), batch,
                                     torch.tensor([-1.0, 1.0, 1.0]))


class BaseStageFixReceiptTest(unittest.TestCase):
    """Every law the fix pass introduced is receipted, and typed."""

    def _receipt(self, *, identity_enabled: bool, stop_reason="CONVERGED"):
        governed = ("oracle", "recon", "memory_value")
        if identity_enabled:
            governed = ("oracle", "recon", "identity", "memory_value")
        trace = []
        for epoch in range(2):
            row = {"epoch": epoch, "composite": 1.0 - .1 * epoch,
                   "memory_value_occluded": 2.0, "memory_value_margin": .5,
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
            validation_window_receipt={"held_rows": 120})

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
        self.assertEqual(len(receipt["memory_value_occluded_baseline"]), 2)
        self.assertEqual(receipt["memory_value_fit_weight_law"],
                         "OUTCOME_FREE_BASE")

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

    def test_default_caps_are_inactive_until_measured(self):
        self.assertEqual(dict(AUX_SHARE_CAPS),
                         {"recon": 1.0, "identity": 1.0, "memory_value": 1.0})
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

    def test_window_widens_until_the_hundred_row_floor(self):
        days, receipt = _widened_validation_days(self._batches(20, 10))
        self.assertEqual(int(receipt["baseline_trailing_days"]), 2)
        self.assertEqual(int(receipt["trailing_days"]), 10)
        self.assertGreaterEqual(int(receipt["held_rows"]),
                                RECONSTRUCTION_VALIDATION_MINIMUM_ROWS)
        self.assertTrue(receipt["meets_minimum"])
        self.assertEqual(len(days), 10)

    def test_a_wide_enough_baseline_window_is_left_alone(self):
        _days, receipt = _widened_validation_days(self._batches(20, 60))
        self.assertEqual(int(receipt["trailing_days"]),
                         int(receipt["baseline_trailing_days"]))

    def test_at_least_one_training_day_always_survives(self):
        days, receipt = _widened_validation_days(self._batches(3, 2))
        self.assertEqual(len(days), 2)
        self.assertFalse(receipt["meets_minimum"])
        self.assertEqual(RECONSTRUCTION_VALIDATION_MINIMUM_ROWS, 100)


class EncoderHarnessAcceptanceMetricTest(unittest.TestCase):
    """R7: the harness scores held-day TOP-3 DOLLARS, not AUROC."""

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

    def _data_root(self, rows):
        import tempfile
        from pathlib import Path
        root = Path(tempfile.mkdtemp())
        self.addCleanup(__import__("shutil").rmtree, root, True)
        (root / "g1" / "candidates" / "HG").mkdir(parents=True)
        (root / "g1" / "teacher" / "HG").mkdir(parents=True)
        candidates = ["# provenance header", "candidate_id\tfrozen_cost_usd"]
        teacher = ["# provenance header",
                   "candidate_id\tcert_close_usd\tcompliance_status"]
        for candidate_id, frozen, certified, status in rows:
            candidates.append(f"{candidate_id}\t{frozen}")
            teacher.append(f"{candidate_id}\t{certified}\t{status}")
        (root / "g1" / "candidates" / "HG" / "20210813.tsv").write_text(
            "\n".join(candidates) + "\n")
        (root / "g1" / "teacher" / "HG" / "20210813.tsv").write_text(
            "\n".join(teacher) + "\n")
        return str(root)

    def test_ledger_is_certified_minus_frozen_for_compliant_rows_only(self):
        harness = self._harness()
        root = self._data_root([("a", 10.0, 110.0, "CLEAR"),
                                ("b", 5.0, 55.0, "READY"),
                                ("c", 1.0, 900.0, "BLOCKED")])
        ledger = harness.day_dollar_ledger(root, "HG", 20210813)
        self.assertEqual(set(ledger), {"a", "b"})
        self.assertAlmostEqual(ledger["a"], 100.0)
        self.assertAlmostEqual(ledger["b"], 50.0)

    def test_memory_only_top3_beats_the_occluded_baseline(self):
        harness = self._harness()
        from types import SimpleNamespace
        names = [f"c{index}" for index in range(6)]
        dollars = [0.0, 0.0, 0.0, 100.0, 200.0, 300.0]
        root = self._data_root([(name, 0.0, value, "CLEAR")
                                for name, value in zip(names, dollars)])

        class _Probe(torch.nn.Module):
            def forward(self, memory):
                score = memory.reshape(memory.shape[0], -1).sum(1)
                return (torch.zeros(memory.shape[0], 5), score,
                        torch.zeros(memory.shape[0]))

        memories = {name: torch.full((4, 512), float(index))
                    for index, name in enumerate(names)}
        rows = SimpleNamespace(candidate_id=np.asarray(names),
                               asset=np.asarray(["HG"] * 6),
                               day=np.asarray([20210813] * 6))
        result = harness.held_day_top3_dollars(
            rows, memories, _Probe(), device=torch.device("cpu"),
            data_root=root, held_days=frozenset({20210813}))
        self.assertEqual(int(result["days"]), 1)
        self.assertAlmostEqual(result["memory_only_usd_day"], 600.0)
        self.assertAlmostEqual(result["occluded_usd_day"], 0.0)
        self.assertAlmostEqual(result["oracle_usd_day"], 600.0)
        self.assertTrue(result["beats_occlusion"])
        self.assertAlmostEqual(result["margin_usd_day"], 600.0)



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
        head = SharedCandidateDecisionHead(8, 3, 2)
        model = NeuralSufficiencyModel(encoder, head)
        batch = _tiny_batch(clock=np.arange(1, 121, dtype=np.int64) * 1_000,
                            cutoffs=np.asarray([40, 70, 100], np.int64))
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
        value, _v = _memory_value_probe_loss(
            probe, out.raw_memory, batch, weights["base"])
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



if __name__ == "__main__":
    unittest.main()
