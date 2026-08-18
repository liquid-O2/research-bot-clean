#!/usr/bin/env python3
"""Focused synthetic laws for the corrected neural model plane."""

from __future__ import annotations

import copy
import unittest

import torch
from torch import nn

from .model import EntryModelRefusal, FullPrefixEntryModel
from .neural_sufficiency_model import (
    CausalMultiresolutionEncoder, CurrentEncoderAdapter,
    LiTShortMemoryEncoder,
    LosslessStaticTokenAdapter, NeuralSufficiencyModel,
    SharedCandidateDecisionHead,
    STAGE_SPECS, FrozenRowManifest,
    assert_current_checkpoint_identity,
    assert_lit_checkpoint_identity, build_five_arm_registry,
    build_shared_arms, field_routing_competence, generic_event_schema,
    train_chronological_stage,
)
from .neural_sufficiency_model import _field_routing_mutation_rows


CONTINUOUS = 16
CATEGORIES = (7, 5, 11, 4, 8)
NS = 1_000_000_000
SCHEMA = generic_event_schema(CONTINUOUS, CATEGORIES)


def _events(n: int = 520, seed: int = 17):
    g = torch.Generator().manual_seed(seed)
    x = torch.randn(n, CONTINUOUS, generator=g)
    k = torch.stack([torch.randint(size, (n,), generator=g)
                     for size in CATEGORIES], dim=1)
    clocks = torch.arange(n, dtype=torch.int64) * NS
    return x, k, clocks


def _bounds(clocks: torch.Tensor, decisions: list[int]):
    decision = torch.tensor(decisions, dtype=torch.int64)
    return torch.searchsorted(clocks, decision, right=False), decision


class NeuralSufficiencyModelTest(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(41)

    def test_exact_lower_bound_equal_future_and_visible_only_validation(self):
        x, k, clock = _events(20)
        cutoffs, decisions = _bounds(clock, [5 * NS, 5 * NS + 1])
        self.assertEqual(cutoffs.tolist(), [5, 6])
        model = CausalMultiresolutionEncoder(CONTINUOUS, CATEGORIES,
                                             field_schema=SCHEMA).eval()
        with torch.inference_mode():
            out = model(x, k, cutoffs, receive_clock_ns=clock,
                        candidate_decision_ts_ns=decisions)
        self.assertEqual(out.shape, (2, 4, 512))
        bad = k.clone(); bad[10:, 0] = 999
        with torch.inference_mode():
            model(x, bad, torch.tensor([5]), receive_clock_ns=clock,
                  candidate_decision_ts_ns=torch.tensor([5 * NS]))
        with self.assertRaises(EntryModelRefusal):
            model(x, k, torch.tensor([6]), receive_clock_ns=clock,
                  candidate_decision_ts_ns=torch.tensor([5 * NS]))
        with self.assertRaises(EntryModelRefusal):
            model(x, k, cutoffs, receive_clock_ns=clock.float(),
                  candidate_decision_ts_ns=decisions)
        with torch.inference_mode():
            empty = model(x, k, torch.tensor([0]), receive_clock_ns=clock,
                          candidate_decision_ts_ns=torch.tensor([0]))
        self.assertEqual(empty.shape, (1, 4, 512))
        changed_clock = clock.clone(); changed_clock[10:] = -1
        with torch.inference_mode():
            isolated = model(x, k, torch.tensor([5]), receive_clock_ns=changed_clock,
                             candidate_decision_ts_ns=torch.tensor([5 * NS]))
            baseline = model(x, k, torch.tensor([5]), receive_clock_ns=clock,
                             candidate_decision_ts_ns=torch.tensor([5 * NS]))
        self.assertTrue(torch.equal(isolated, baseline))

    def test_cache_recent256_band_boundaries_decision_gap_and_complexity(self):
        x, k, clock = _events(520)
        model = CausalMultiresolutionEncoder(CONTINUOUS, CATEGORIES,
                                             field_schema=SCHEMA).eval()
        decisions = torch.tensor([510 * NS, 510 * NS + NS // 2])
        cutoffs = torch.tensor([510, 511])
        with torch.inference_mode():
            cache = model.encode_session(x, k, clock, visible_events=511)
            before = model.gather_candidate_memory(cache, cutoffs, decisions)
        self.assertEqual(model._regular_encode_calls, 1)
        self.assertNotEqual(before[0, 1].tolist(), before[1, 1].tolist())
        self.assertEqual(model.band_membership(cache, 510, 510 * NS, 300), (0, 1))
        self.assertEqual(model.band_membership(cache, 510, 510 * NS, 60), (1,))
        changed = x.clone(); changed[253, 7] += 100
        with torch.inference_mode():
            changed_cache = model.encode_session(changed, k, clock, visible_events=511)
            after = model.gather_candidate_memory(changed_cache, cutoffs, decisions)
        # row 253 is outside candidate 510's exact [254,510) token-0 window.
        self.assertTrue(torch.equal(before[0, 0], after[0, 0]))
        receipt = model.last_complexity_receipt
        self.assertEqual((receipt.events_visible, receipt.regular_blocks,
                          receipt.candidates), (511, 1, 2))
        self.assertLessEqual(receipt.recent_window_events, 256 * 2)
        self.assertLessEqual(receipt.partial_block_events, 256 * 2)
        self.assertLessEqual(receipt.candidate_window_chunk_high_water, 32)
        gap_clock = torch.cat((torch.arange(256, dtype=torch.int64) * NS,
                               (torch.arange(8, dtype=torch.int64) + 400) * NS))
        gap_x, gap_k, _ = _events(len(gap_clock), seed=23)
        with torch.inference_mode():
            gap_cache = model.encode_session(gap_x, gap_k, gap_clock,
                                              visible_events=256)
        self.assertEqual(model.band_membership(gap_cache, 256, 315 * NS, 60), (0,))
        self.assertEqual(model.band_membership(gap_cache, 256, 316 * NS, 60), ())

    def test_m1_training_checkpoints_regular_blocks_and_keeps_gradients(self):
        x, k, clock = _events(520)
        model = CausalMultiresolutionEncoder(
            CONTINUOUS, CATEGORIES, field_schema=SCHEMA
        ).train()
        cutoffs, decisions = _bounds(clock, [510 * NS])
        output = model(x, k, cutoffs, receive_clock_ns=clock,
                       candidate_decision_ts_ns=decisions)
        output.square().mean().backward()
        self.assertTrue(any(parameter.grad is not None and bool(
            torch.isfinite(parameter.grad).all()) for parameter in model.parameters()))
        self.assertIn("training_checkpointed", model.last_complexity_receipt.law[0])

    def test_suffix_isolation_and_all_field_gradients(self):
        x, k, clock = _events(20)
        cutoff, decision = _bounds(clock, [10 * NS])
        model = CausalMultiresolutionEncoder(CONTINUOUS, CATEGORIES,
                                             field_schema=SCHEMA).eval()
        x.requires_grad_()
        raw = model(x, k, cutoff, receive_clock_ns=clock,
                    candidate_decision_ts_ns=decision)
        raw.sum().backward()
        self.assertTrue((x.grad[:10].abs().sum(dim=0) > 0).all())
        changed_x, changed_k = x.detach().clone(), k.clone()
        changed_x[10:] = torch.nan
        changed_k[10:] = 999
        with torch.inference_mode():
            suffix = model(changed_x, changed_k, cutoff, receive_clock_ns=clock,
                           candidate_decision_ts_ns=decision)
        self.assertTrue(torch.equal(raw.detach(), suffix))
        for field, size in enumerate(CATEGORIES):
            mutant = k.clone(); mutant[3, field] = (mutant[3, field] + 1) % size
            with torch.inference_mode():
                changed = model(x.detach(), mutant, cutoff, receive_clock_ns=clock,
                                candidate_decision_ts_ns=decision)
            self.assertGreater(float((changed - raw.detach()).abs().max()), 1e-6)

    def test_lit_visibility_order_and_registered_quote_fields(self):
        x, k, clock = _events(80)
        cutoffs, decisions = _bounds(clock, [70 * NS])
        model = LiTShortMemoryEncoder(CONTINUOUS, CATEGORIES,
                                      bid_field_indices=(8, 10, 12),
                                      ask_field_indices=(9, 11, 13),
                                      field_schema=SCHEMA).eval()
        self.assertEqual(model.bid_field_indices.tolist(), [8, 10, 12])
        with torch.inference_mode():
            base = model(x, k, cutoffs, receive_clock_ns=clock,
                         candidate_decision_ts_ns=decisions)
            future = x.clone(); future[70:] += 100
            self.assertTrue(torch.equal(base, model(
                future, k, cutoffs, receive_clock_ns=clock,
                candidate_decision_ts_ns=decisions)))
            reordered = x.clone(); reordered[10:14] = reordered[10:14].flip(0)
            changed = model(reordered, k, cutoffs, receive_clock_ns=clock,
                            candidate_decision_ts_ns=decisions)
        self.assertFalse(torch.equal(base, changed))

    def test_current_adapter_requires_one_homogeneous_session_asset(self):
        x, k, clock = _events(20)
        cutoffs, decisions = _bounds(clock, [5 * NS, 10 * NS])
        adapter = CurrentEncoderAdapter(
            FullPrefixEntryModel(
                CONTINUOUS, 6, 3, 9, event_category_sizes=CATEGORIES
            ),
            SCHEMA,
        ).eval()
        with torch.inference_mode():
            scalar = adapter(
                x, k, cutoffs, receive_clock_ns=clock,
                candidate_decision_ts_ns=decisions, asset_idx=1,
            )
            homogeneous = adapter(
                x, k, cutoffs, receive_clock_ns=clock,
                candidate_decision_ts_ns=decisions,
                asset_idx=torch.tensor([1, 1]),
            )
        self.assertTrue(torch.equal(scalar, homogeneous))
        with self.assertRaises(EntryModelRefusal):
            adapter(
                x, k, cutoffs, receive_clock_ns=clock,
                candidate_decision_ts_ns=decisions,
                asset_idx=torch.tensor([1, 2]),
            )
        with self.assertRaises(EntryModelRefusal):
            adapter(
                x, k, cutoffs, receive_clock_ns=clock,
                candidate_decision_ts_ns=decisions,
                asset_idx=torch.tensor([], dtype=torch.long),
            )

    def test_static_slots_outputs_and_monotonic_semantics(self):
        adapter = LosslessStaticTokenAdapter()
        static = torch.arange(1865, dtype=torch.float32)[None].repeat(2, 1)
        tokens = adapter(static)
        self.assertTrue(torch.equal(adapter.inverse(tokens), static))
        head = SharedCandidateDecisionHead(6, 3, 9).eval()
        raw = torch.zeros(2, 4, 512)
        context = torch.randn(2, 2, 3, 3)
        valid = torch.ones(2, 2, 3, dtype=torch.bool)
        with torch.inference_mode():
            output = head(raw, torch.randn(2, 6), context, torch.tensor([1, 2]),
                          valid, torch.tensor([0, 1]), static_features=static)
            decorated = head.decorated_memory(raw, output.context_token, tokens)
        self.assertTrue(torch.equal(output.raw_memory, raw))
        self.assertTrue(torch.equal(output.static_tokens, tokens))
        self.assertFalse(torch.equal(decorated[:, 5], decorated[:, 6]))
        self.assertTrue((output.ordinal_logits[:, 1:] <=
                         output.ordinal_logits[:, :-1]).all())
        for name in ("value_quantiles", "mfe_quantiles", "mae_quantiles"):
            value = getattr(output, name)
            self.assertTrue((value[:, 1:] >= value[:, :-1]).all(), name)
        self.assertTrue((output.mfe_quantiles >= 0).all())
        self.assertTrue((output.mae_quantiles >= 0).all())
        self.assertEqual(output.phase_logits.shape, (2, 8))
        self.assertEqual(output.horizon_values.shape, (2, 6))
        self.assertEqual(len(output.output_schema_sha256), 64)
        bad_static = static.clone(); bad_static[0, 0] = float("nan")
        with self.assertRaises(EntryModelRefusal):
            adapter(bad_static)

    def test_shared_nonaliasing_five_arms_and_lit_identity(self):
        head = SharedCandidateDecisionHead(6, 3, 9)
        lit = LiTShortMemoryEncoder(CONTINUOUS, CATEGORIES, field_schema=SCHEMA)
        dummy = nn.Linear(2, 2)
        with self.assertRaises(EntryModelRefusal):
            build_five_arm_registry(copy.deepcopy(dummy), copy.deepcopy(dummy),
                lit, CausalMultiresolutionEncoder(CONTINUOUS, CATEGORIES,
                                                   field_schema=SCHEMA), head)
        with self.assertRaises(EntryModelRefusal):
            build_shared_arms({"M1": dummy}, head, require_canonical=True)

    @unittest.skipUnless(torch.cuda.is_available(), "CUDA BF16 gate")
    def test_m1_shared_head_bf16_forward_backward(self):
        """Autocast buffers must not mix raw float32 and BF16 activations."""
        device = torch.device("cuda")
        torch.manual_seed(20260816)
        torch.cuda.manual_seed_all(20260816)
        model = NeuralSufficiencyModel(
            CausalMultiresolutionEncoder(
                CONTINUOUS, CATEGORIES, field_schema=SCHEMA
            ),
            SharedCandidateDecisionHead(6, 3, 9),
        ).to(device).train()
        generator = torch.Generator(device=device).manual_seed(93)
        events = 257
        candidates = 3
        continuous = torch.randn(
            events, CONTINUOUS, generator=generator, device=device
        )
        categorical = torch.stack([
            torch.randint(size, (events,), generator=generator, device=device)
            for size in CATEGORIES
        ], dim=1)
        receive_clock = torch.arange(
            events, dtype=torch.int64, device=device
        ) * 1_000_000
        decisions = torch.tensor(
            [64, 129, 257], dtype=torch.int64, device=device
        ) * 1_000_000
        cutoffs = torch.searchsorted(receive_clock, decisions, right=False)
        with torch.autocast("cuda", dtype=torch.bfloat16):
            output = model(
                event_continuous=continuous,
                event_categorical=categorical,
                receive_clock_ns=receive_clock,
                candidate_cutoffs=cutoffs,
                candidate_decision_ts_ns=decisions,
                candidate_features=torch.randn(
                    candidates, 6, generator=generator, device=device
                ),
                context_values=torch.randn(
                    candidates, 2, 3, 3, generator=generator, device=device
                ),
                context_type_ids=torch.tensor([1, 2], device=device),
                context_valid=torch.ones(
                    candidates, 2, 3, dtype=torch.bool, device=device
                ),
                asset_idx=torch.tensor([0, 1, 2], device=device),
                static_features=torch.randn(
                    candidates, 1_865, generator=generator, device=device
                ),
            )
            loss = (output.action_logit.float().square().mean()
                    + output.ordinal_logits.float().square().mean()
                    + output.horizon_values.float().square().mean())
        loss.backward()
        self.assertTrue(torch.isfinite(loss))
        self.assertTrue(all(
            parameter.grad is None or bool(torch.isfinite(parameter.grad).all())
            for parameter in model.parameters()
        ))

        lit = LiTShortMemoryEncoder(
            CONTINUOUS, CATEGORIES, field_schema=SCHEMA
        ).to(device).train()
        lit_continuous = continuous.detach().clone().requires_grad_(True)
        with torch.autocast("cuda", dtype=torch.bfloat16):
            lit_memory = lit(
                lit_continuous, categorical, cutoffs,
                receive_clock_ns=receive_clock,
                candidate_decision_ts_ns=decisions,
            )
            lit_loss = lit_memory.float().square().mean()
        lit_loss.backward()
        self.assertTrue(torch.isfinite(lit_loss))
        self.assertEqual(lit_memory.dtype, torch.float32)
        self.assertTrue(torch.isfinite(lit_continuous.grad).all())


class _CountingStageModel(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.linear = nn.Linear(2, 1)


def _stage_callbacks(validations):
    state = {"epoch": 0, "validations": 0}

    def train_epoch(model, optimizer, manifest):
        optimizer.zero_grad(set_to_none=True)
        loss = (model.linear(torch.ones(1, 2)).squeeze() - 3.0) ** 2
        loss.backward()
        optimizer.step()
        state["epoch"] += 1
        return loss.detach()

    def validate_epoch(model, manifest):
        index = min(state["validations"], len(validations) - 1)
        state["validations"] += 1
        return torch.tensor(float(validations[index]))

    return train_epoch, validate_epoch, state


class SelectedStageLawTest(unittest.TestCase):
    """Red-first laws for the frozen stage/convergence contract."""

    def _manifest(self) -> FrozenRowManifest:
        return FrozenRowManifest.build_fit_validation(
            ["a", "b", "c", "d"], ["SI"] * 4, [20240102, 20240102, 20240103, 20240104],
            chronology="E4",
        )

    def test_field_survival_is_not_an_independent_full_tape_stage(self):
        self.assertNotIn("field_survival", STAGE_SPECS)
        self.assertEqual(tuple(STAGE_SPECS), ("pointwise_dense", "grouped_atlas"))
        self.assertEqual(STAGE_SPECS["pointwise_dense"].max_epochs, 12)
        self.assertEqual(STAGE_SPECS["pointwise_dense"].patience, 3)
        model = _CountingStageModel()
        train_epoch, validate_epoch, _ = _stage_callbacks([1.0, 0.5, 0.6, 0.6])
        with self.assertRaises(EntryModelRefusal):
            train_chronological_stage(
                model, torch.optim.AdamW(model.parameters(), lr=1e-2),
                stage="field_survival", row_manifest=self._manifest(),
                train_epoch=train_epoch, validate_epoch=validate_epoch)

    def test_stage_must_not_finish_at_a_rising_best_validation_loss(self):
        model = _CountingStageModel()
        # Still improving at every one of the six grouped-atlas epochs: the
        # budget was exhausted mid-descent, which is not convergence.
        train_epoch, validate_epoch, _ = _stage_callbacks(
            [1.0, .8, .6, .4, .2, .1])
        with self.assertRaises(EntryModelRefusal) as caught:
            train_chronological_stage(
                model, torch.optim.AdamW(model.parameters(), lr=1e-2),
                stage="grouped_atlas", row_manifest=self._manifest(),
                train_epoch=train_epoch, validate_epoch=validate_epoch)
        self.assertIn("exhausted its epoch budget", str(caught.exception))

    def test_reloaded_best_checkpoint_must_reproduce_the_best_loss(self):
        model = _CountingStageModel()
        # Converged: best at epoch 0, then patience exhausted.  The post-reload
        # validation call is answered with a different value, which proves the
        # reloaded bytes are not the measured best.
        train_epoch, validate_epoch, _ = _stage_callbacks(
            [1.0, 0.5, 0.6, 0.6, 9.0])
        with self.assertRaises(EntryModelRefusal) as caught:
            train_chronological_stage(
                model, torch.optim.AdamW(model.parameters(), lr=1e-2),
                stage="grouped_atlas", row_manifest=self._manifest(),
                train_epoch=train_epoch, validate_epoch=validate_epoch)
        self.assertIn("reloaded checkpoint validation loss", str(caught.exception))

    def test_converged_stage_reloads_and_reproduces_the_best_loss(self):
        model = _CountingStageModel()
        train_epoch, validate_epoch, _ = _stage_callbacks(
            [1.0, 0.5, 0.6, 0.6, 0.5])
        receipt = train_chronological_stage(
            model, torch.optim.AdamW(model.parameters(), lr=1e-2),
            stage="grouped_atlas", row_manifest=self._manifest(),
            train_epoch=train_epoch, validate_epoch=validate_epoch)
        self.assertTrue(receipt.best_reloaded)
        self.assertEqual(receipt.best_epoch, 1)
        self.assertAlmostEqual(receipt.best_validation_loss, 0.5)

    def test_c1_must_consume_c0_exact_checkpoint(self):
        head = SharedCandidateDecisionHead(6, 3, 9)
        lit = LiTShortMemoryEncoder(CONTINUOUS, CATEGORIES, field_schema=SCHEMA)
        m1 = CausalMultiresolutionEncoder(CONTINUOUS, CATEGORIES, field_schema=SCHEMA)
        base = FullPrefixEntryModel(
            CONTINUOUS, 6, 3, 9, event_category_sizes=CATEGORIES)
        c0 = CurrentEncoderAdapter(base, SCHEMA)
        same = CurrentEncoderAdapter(copy.deepcopy(base), SCHEMA)
        arms = build_five_arm_registry(c0, same, lit, m1, head)
        digest = assert_current_checkpoint_identity(arms)
        self.assertEqual(len(digest), 64)
        different = CurrentEncoderAdapter(
            FullPrefixEntryModel(
                CONTINUOUS, 6, 3, 9, event_category_sizes=CATEGORIES),
            SCHEMA)
        with self.assertRaises(EntryModelRefusal):
            build_five_arm_registry(c0, different, lit, m1, head)

    def test_m1_gather_candidate_memory_after_strict_load(self):
        source = CausalMultiresolutionEncoder(CONTINUOUS, CATEGORIES,
                                              field_schema=SCHEMA)
        loaded = CausalMultiresolutionEncoder(CONTINUOUS, CATEGORIES,
                                              field_schema=SCHEMA)
        loaded.load_state_dict(source.state_dict(), strict=True)
        loaded.eval()
        self.assertEqual(loaded._regular_block_chunks, 0)
        self.assertEqual(loaded._regular_block_chunk_high_water, 0)
        x, k, clock = _events(300)
        cutoffs, decisions = _bounds(clock, [120 * NS, 200 * NS])
        with torch.no_grad():
            cache = loaded.encode_session(x, k, clock, visible_events=260)
        fresh = CausalMultiresolutionEncoder(CONTINUOUS, CATEGORIES,
                                             field_schema=SCHEMA)
        fresh.load_state_dict(source.state_dict(), strict=True)
        fresh.eval()
        with torch.no_grad():
            memory = fresh.gather_candidate_memory(cache, cutoffs, decisions)
        self.assertEqual(memory.shape, (2, 4, 512))
        self.assertEqual(fresh.last_complexity_receipt.regular_block_chunks, 0)


class FieldRoutingCompetenceTest(unittest.TestCase):
    """Red-first laws for the every-field routing competence gate."""

    def _inputs(self, n: int = 400):
        x, k, clock = _events(n, seed=5)
        cutoffs, decisions = _bounds(clock, [(n - 4) * NS, (n - 2) * NS])
        return x.double().float(), k, clock, cutoffs, decisions

    def test_mutation_rows_span_the_declared_bands(self):
        _x, _k, clock, cutoffs, decisions = self._inputs()
        rows = _field_routing_mutation_rows(
            clock, decisions, cutoffs, seed=7, rows_per_band=2)
        self.assertIn(0, rows)
        visible = int(cutoffs.max())
        self.assertIn(visible - 1, rows)
        self.assertGreaterEqual(len(rows), 5)
        self.assertEqual(rows, _field_routing_mutation_rows(
            clock, decisions, cutoffs, seed=7, rows_per_band=2))

    def test_late_drop_encoder_fails_and_a_full_router_passes(self):
        x, k, clock, cutoffs, decisions = self._inputs()
        full = CausalMultiresolutionEncoder(CONTINUOUS, CATEGORIES,
                                            field_schema=SCHEMA)
        receipt = field_routing_competence(
            full, event_continuous=x, event_categorical=k,
            receive_clock_ns=clock, candidate_cutoffs=cutoffs,
            candidate_decision_ts_ns=decisions,
            price_field_indices=(5, 8, 9), undefined_mask_field=4)
        self.assertTrue(receipt.passed)
        self.assertEqual(receipt.comparison_device, "cpu")
        self.assertEqual(receipt.comparison_dtype, "torch.float32")
        self.assertEqual(len(receipt.mask_only_mutations), 3)
        self.assertEqual(len(receipt.price_mask_mutations), 3)
        self.assertGreater(len(receipt.mutation_rows), 4)
        # Mutating only row 0 is exactly the hole this gate closed: a memory
        # that drops every recent event still moves when row 0 moves.  The
        # declared short-memory control therefore cannot pass the band-spanning
        # arm on a long tape, and it is gated on its own declared window.
        short = LiTShortMemoryEncoder(CONTINUOUS, CATEGORIES,
                                      field_schema=SCHEMA)
        with self.assertRaises(EntryModelRefusal):
            field_routing_competence(
                short, event_continuous=x, event_categorical=k,
                receive_clock_ns=clock, candidate_cutoffs=cutoffs,
                candidate_decision_ts_ns=decisions,
                price_field_indices=(5, 8, 9), undefined_mask_field=4)

    def test_price_and_mask_routes_must_resolve(self):
        x, k, clock, cutoffs, decisions = self._inputs(80)
        encoder = LiTShortMemoryEncoder(CONTINUOUS, CATEGORIES,
                                        field_schema=SCHEMA)
        with self.assertRaises(EntryModelRefusal):
            field_routing_competence(
                encoder, event_continuous=x, event_categorical=k,
                receive_clock_ns=clock, candidate_cutoffs=cutoffs,
                candidate_decision_ts_ns=decisions,
                price_field_indices=(999,), undefined_mask_field=4)


if __name__ == "__main__":
    unittest.main()
