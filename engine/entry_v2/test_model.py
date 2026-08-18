#!/usr/bin/env python3
"""One adversarial verification cycle for the fixed entry-v2 model."""

from __future__ import annotations

import unittest

import torch

from engine.entry_v2.model import (
    EntryModelRefusal,
    FullPrefixEntryModel,
    model_state_sha256,
    partition_event_blocks,
)


EVENT_CONTINUOUS = 6
CANDIDATE_FEATURES = 7
CONTEXT_CONTINUOUS = 4
CONTEXT_TYPES = 12
CATEGORY_SIZES = (11, 7, 5)


def _model(device: torch.device | str = "cpu") -> FullPrefixEntryModel:
    return FullPrefixEntryModel(
        EVENT_CONTINUOUS,
        CANDIDATE_FEATURES,
        CONTEXT_CONTINUOUS,
        CONTEXT_TYPES,
        event_category_sizes=CATEGORY_SIZES,
        n_value_bins=7,
    ).to(device)


def _session(
    n_events: int,
    cutoffs: list[int],
    *,
    device: torch.device | str = "cpu",
    seed: int = 17,
) -> dict[str, torch.Tensor | int]:
    generator = torch.Generator(device=device).manual_seed(seed)
    candidates = len(cutoffs)
    series, history = 4, 9
    categorical = torch.stack(
        [
            torch.randint(size, (n_events,), generator=generator, device=device)
            for size in CATEGORY_SIZES
        ],
        dim=1,
    )
    context_valid = torch.ones(
        (candidates, series, history), dtype=torch.bool, device=device
    )
    if candidates:
        # Exercise both an entirely absent candidate context and one missing
        # typed series without introducing NaNs into the batch.
        context_valid[0] = False
        if candidates > 1:
            context_valid[1:, -1] = False
    return {
        "event_continuous": torch.randn(
            (n_events, EVENT_CONTINUOUS), generator=generator, device=device
        ),
        "event_categorical": categorical,
        "candidate_cutoffs": torch.tensor(
            cutoffs, dtype=torch.int64, device=device
        ),
        "candidate_features": torch.randn(
            (candidates, CANDIDATE_FEATURES), generator=generator, device=device
        ),
        "context_values": torch.randn(
            (candidates, series, history, CONTEXT_CONTINUOUS),
            generator=generator,
            device=device,
        ),
        "context_type_ids": torch.tensor([1, 3, 7, 9], device=device),
        "context_valid": context_valid,
        "asset_idx": seed % 3,
    }


class FullPrefixModelTest(unittest.TestCase):
    def test_partition_inserts_cutoffs_and_never_crosses_one(self) -> None:
        cutoffs = torch.tensor([700, 257, 0, 10, 256, 257], dtype=torch.int64)
        part = partition_event_blocks(700, cutoffs)

        self.assertEqual(part.starts.tolist(), [0, 10, 256, 257, 512])
        self.assertEqual(part.stops.tolist(), [10, 256, 257, 512, 700])
        self.assertEqual(part.candidate_block.tolist(), [4, 2, -1, 0, 1, 2])
        self.assertLessEqual(int(part.lengths.max()), 256)
        for cutoff in set(cutoffs.tolist()):
            self.assertFalse(
                any(start < cutoff < stop for start, stop in zip(part.starts, part.stops))
            )

        empty = partition_event_blocks(0, torch.tensor([0, 0]))
        self.assertEqual(empty.n_blocks, 0)
        self.assertEqual(empty.candidate_block.tolist(), [-1, -1])
        with self.assertRaises(EntryModelRefusal):
            partition_event_blocks(12, torch.tensor([13]))

    def test_shared_prefix_and_adversarial_suffix_independence(self) -> None:
        torch.manual_seed(31)
        model = _model().eval()
        receipt = model.architecture()
        self.assertEqual(
            receipt,
            {
                "event_continuous": EVENT_CONTINUOUS,
                "event_category_sizes": list(CATEGORY_SIZES),
                "block_size": 256,
                "local": {
                    "width": 128,
                    "depth": 2,
                    "heads": 4,
                    "summaries_per_block": 4,
                },
                "long": {"width": 512, "depth": 8, "heads": 8},
                "context": {
                    "continuous": CONTEXT_CONTINUOUS,
                    "types": CONTEXT_TYPES,
                    "width": 128,
                    "depth": 2,
                    "heads": 4,
                },
                "assets": 3,
                "candidate_features": CANDIDATE_FEATURES,
                "value_bins": 7,
            },
        )

        base = _session(320, [0, 80, 80, 257], seed=41)
        with torch.inference_mode():
            original = model(**base)
        self.assertTrue(torch.equal(original.prefix_state[1], original.prefix_state[2]))
        self.assertFalse(torch.equal(original.embedding[1], original.embedding[2]))
        self.assertEqual(tuple(original.embedding.shape), (4, 512))
        self.assertEqual(tuple(original.value_bin_logits.shape), (4, 7))
        self.assertEqual(tuple(original.value_quantiles.shape), (4, 3))
        self.assertEqual(tuple(original.mae_quantiles.shape), (4, 3))
        self.assertEqual(tuple(original.expected_value.shape), (4,))

        # Keep a later candidate in the same long-attention stream, then alter
        # every event after the duplicate cutoff.  This attacks the causal
        # masks themselves (rather than the max-cutoff slice tested below).
        future_mutated = dict(base)
        future_mutated["event_continuous"] = base["event_continuous"].clone()
        future_mutated["event_categorical"] = base["event_categorical"].clone()
        future_mutated["event_continuous"][80:257].mul_(-19.0).add_(31.0)
        for column, size in enumerate(CATEGORY_SIZES):
            future_mutated["event_categorical"][80:257, column].add_(1).remainder_(size)
        with torch.inference_mode():
            after_future_mutation = model(**future_mutated)
        self.assertTrue(
            torch.equal(original.embedding[:3], after_future_mutation.embedding[:3])
        )
        self.assertTrue(
            torch.equal(
                original.prefix_state[:3], after_future_mutation.prefix_state[:3]
            )
        )
        self.assertFalse(
            torch.equal(original.prefix_state[3], after_future_mutation.prefix_state[3])
        )

        # Change every unavailable suffix field, append another 193 events, and
        # keep candidate geometry/context identical.  The model deliberately
        # slices at max(cutoff), so all outputs must be bit-identical.
        extended = _session(513, [0, 80, 80, 257], seed=97)
        for name in ("event_continuous", "event_categorical"):
            extended[name][:257] = base[name][:257]
        for name in (
            "candidate_features",
            "context_values",
            "context_type_ids",
            "context_valid",
        ):
            extended[name] = base[name]
        extended["asset_idx"] = base["asset_idx"]
        with torch.inference_mode():
            after_suffix = model(**extended)

        for field in (
            "prefix_state",
            "context_state",
            "embedding",
            "value_bin_logits",
            "value_quantiles",
            "expected_value",
            "top3_logit",
            "mae_quantiles",
            "wall_logit",
            "take_logit",
        ):
            self.assertTrue(
                torch.equal(getattr(original, field), getattr(after_suffix, field)),
                msg=f"future suffix changed {field}",
            )

    def test_context_mask_is_typed_and_nan_safe(self) -> None:
        torch.manual_seed(43)
        model = _model().eval()
        batch = _session(12, [0, 12], seed=53)
        with torch.inference_mode():
            output = model(**batch)
        self.assertTrue(torch.isfinite(output.context_state).all())
        self.assertTrue(torch.equal(output.context_state[0], torch.zeros(128)))

        changed = dict(batch)
        changed["context_type_ids"] = torch.tensor([2, 4, 8, 10])
        with torch.inference_mode():
            typed = model(**changed)
        self.assertFalse(torch.equal(output.context_state[1], typed.context_state[1]))
        # Tape state cannot depend on either context identity or values.
        self.assertTrue(torch.equal(output.prefix_state, typed.prefix_state))

    @unittest.skipUnless(torch.cuda.is_available(), "BF16 smoke requires CUDA")
    def test_ten_session_bf16_backward_and_state_hash(self) -> None:
        device = torch.device("cuda")
        torch.manual_seed(20260816)
        torch.cuda.manual_seed_all(20260816)
        model = _model(device).train()
        self.assertTrue(torch.cuda.is_bf16_supported())
        self.assertGreater(sum(p.numel() for p in model.parameters()), 27_000_000)

        before = model_state_sha256(model)
        model.zero_grad(set_to_none=True)
        for session in range(10):
            n_events = 273 + 17 * session
            inputs = _session(
                n_events,
                [0, 37, 37, n_events // 2, n_events],
                device=device,
                seed=1000 + session,
            )
            inputs["asset_idx"] = session % 3
            with torch.autocast("cuda", dtype=torch.bfloat16):
                output = model(**inputs)
                loss = (
                    output.embedding.square().mean()
                    + output.value_bin_logits.square().mean()
                    + output.value_quantiles.square().mean()
                    + output.expected_value.square().mean()
                    + output.top3_logit.square().mean()
                    + output.mae_quantiles.square().mean()
                    + output.wall_logit.square().mean()
                    + output.take_logit.square().mean()
                ) / 10.0
            self.assertEqual(output.embedding.dtype, torch.bfloat16)
            self.assertTrue(torch.isfinite(loss))
            loss.backward()

        after_backward = model_state_sha256(model)
        self.assertEqual(before, after_backward, "backward mutated model state")
        gradients = [p.grad for p in model.parameters() if p.grad is not None]
        self.assertGreater(len(gradients), 200)
        self.assertTrue(all(torch.isfinite(grad).all() for grad in gradients))
        self.assertGreater(sum(int(torch.count_nonzero(g)) for g in gradients), 0)

        torch.optim.SGD(model.parameters(), lr=1e-3).step()
        after_step = model_state_sha256(model)
        self.assertNotEqual(before, after_step)


if __name__ == "__main__":
    unittest.main()
