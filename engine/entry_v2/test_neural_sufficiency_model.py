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
    assert_lit_checkpoint_identity, build_five_arm_registry,
    build_shared_arms, generic_event_schema,
)


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


if __name__ == "__main__":
    unittest.main()
