"""verify_real_tape.py — the REAL-corpus door check: load -> Batch -> forward.

Stage 2 of the binding: one published session is read through `tapes.load_side`,
every arm scores it in a single forward pass (NO training), and the structural
laws that the synthetic self-test can only assert on made-up numbers are checked
against the emitted bytes.

This is deliberately NOT part of test_campaign.py: that suite proves it never
touches a real tensor path, and this one exists to touch exactly that path.

usage: verify_real_tape.py [--root DIR] [--session N] [--rows N] [--verify-sha]
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import numpy as np
import torch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import arms      # noqa: E402
import tapes     # noqa: E402
import train     # noqa: E402

DEFAULT_ROOT = "/workspace/artifacts/tensors/v4.0/run1"
RESULTS: list[tuple[str, bool, str]] = []


def check(name):
    def wrap(function):
        def run(*args, **kwargs):
            try:
                function(*args, **kwargs)
                RESULTS.append((name, True, ""))
            except Exception as error:                      # noqa: BLE001
                import traceback
                RESULTS.append((name, False, traceback.format_exc()))
        return run
    return wrap


@check("every arm scores the real session in one forward pass, all finite")
def check_forward(loaded) -> None:
    for side, (batch, _) in loaded.items():
        for name in arms.ARM_NAMES:
            torch.manual_seed(train.SEED)
            model = arms.build_arm(name)
            model.eval()
            with torch.no_grad():
                logits = model(batch)
            assert logits.shape == (batch.rows, arms.N_OUT), (name, side, logits.shape)
            assert torch.isfinite(logits).all(), f"{name}/{side} produced a non-finite logit"


@check("every carrier index the tape emitted is inside its own table")
def check_indices(loaded) -> None:
    for side, (batch, _) in loaded.items():
        for index, modality in enumerate(arms.MODALITIES):
            groups = batch.groups[index].shape[0]
            slot = batch.micro_slot[:, index]
            assert int(slot.min()) >= -1 and int(slot.max()) < groups, (side, modality)
            reference = batch.bin_ref[:, index]
            assert int(reference.min()) >= -1, (side, modality)
            assert int(reference.max()) < batch.bin_segments[index], (side, modality)
            segment = batch.bin_seg[index]
            assert segment.shape[0] == groups, (side, modality, segment.shape)
            assert int(segment.max()) < batch.bin_segments[index], (side, modality)
            phase = batch.micro_phase[:, index]
            assert int(phase.min()) >= 0 and int(phase.max()) <= 2, (side, modality)
        present = batch.jsa_mod >= 0
        assert int(batch.jsa_slot[present].min()) >= 0
        for index in range(len(arms.MODALITIES)):
            pick = present & (batch.jsa_mod == index)
            if bool(pick.any()):
                assert int(batch.jsa_slot[pick].max()) < batch.groups[index].shape[0]


@check("the availability plane is the frozen masks[N,7] and reaches r_modality")
def check_masks(loaded) -> None:
    for side, (batch, targets) in loaded.items():
        assert set(np.unique(batch.r_modality.numpy())) <= {0.0, 1.0}, side
        assert set(np.unique(batch.candset_valid.numpy())) <= {0.0, 1.0}, side
        assert batch.r_modality.shape == (batch.rows, 3), side
        # stage_mask packs the three watch-stage bits, so it is in 0..7.
        assert int(targets.stage_mask.min()) >= 0 and int(targets.stage_mask.max()) <= 7, side
        assert set(np.unique(targets.row_mask.numpy())) <= {0.0, 1.0}, side


@check("a group vector's max is never below its mean, on BOTH sides")
def check_orientation_is_a_reduction(loaded) -> None:
    """The orientation law is only right if what it produces is still a
    mean+max reduction: `max >= mean` must survive the SHORT flip, and that is
    an independent falsifier because the SHORT max comes from the MIN block."""
    for side, (batch, _) in loaded.items():
        for index, modality in enumerate(arms.MODALITIES):
            channels = tapes.CHANNELS[modality]
            table = batch.groups[index].numpy()
            mean = table[:, 0:channels]
            mean_mask = table[:, channels:2 * channels]
            maximum = table[:, 2 * channels:3 * channels]
            max_mask = table[:, 3 * channels:4 * channels]
            present = (mean_mask > 0) & (max_mask > 0)
            slack = maximum - mean
            worst = float(slack[present].min()) if present.any() else 0.0
            assert worst >= -1e-3, f"{side}/{modality}: max is {worst} below mean"


@check("the SHORT table follows the emitted orientation law channel by channel")
def check_orientation_law(root: pathlib.Path, session: int) -> None:
    long_tape = tapes.DecisionTape(tapes._session_dir(root, session, "L"))
    for modality in arms.MODALITIES:
        channels = tapes.CHANNELS[modality]
        features = long_tape.features([f"groups_{modality}", f"orientation_{modality}"])
        neutral = np.asarray(features[f"groups_{modality}"][:4096])
        orientation = np.asarray(features[f"orientation_{modality}"])
        long_side = tapes.orient_group_vector(neutral, orientation, channels, tapes.SIDE_LONG)
        short = tapes.orient_group_vector(neutral, orientation, channels, tapes.SIDE_SHORT)
        assert np.array_equal(long_side, neutral[:, :4 * channels + 1].astype(np.float32)), modality

        kind = orientation[:, 0]
        partner = orientation[:, 1]
        invariant = np.flatnonzero(kind == tapes.ORIENT_INVARIANT)
        for block in (0, 1, 2, 3):
            low = block * channels
            assert np.array_equal(short[:, low + invariant], long_side[:, low + invariant]), modality
        negating = np.flatnonzero((kind == tapes.ORIENT_SIGMA)
                                  | (kind == tapes.ORIENT_SIGMA_RHO))
        if negating.size:
            present = long_side[:, channels + negating] > 0
            expected = -long_side[:, negating]
            assert np.array_equal(short[:, negating][present], expected[present]), modality
            # masks are copied, never negated
            assert np.array_equal(short[:, channels + negating],
                                  long_side[:, channels + negating]), modality
            assert np.array_equal(short[:, 3 * channels + negating],
                                  long_side[:, 3 * channels + negating]), modality
        swaps = np.flatnonzero(kind == tapes.ORIENT_SWAP)
        if swaps.size:
            mates = partner[swaps]
            assert np.array_equal(short[:, swaps], long_side[:, mates]), modality
            assert np.array_equal(short[:, channels + swaps],
                                  long_side[:, channels + mates]), modality
        # log1p multiplicity is side-invariant
        assert np.array_equal(short[:, 4 * channels], long_side[:, 4 * channels]), modality


@check("the loader reads truth only through the allowlist, and never as a feature")
def check_truth_receipt(root: pathlib.Path, session: int) -> None:
    for side in tapes.SIDES:
        tape = tapes.DecisionTape(tapes._session_dir(root, session, side))
        tape.features()
        tape.assert_features_never_touched_truth()
        allowed = tape.truth(list(tapes.TRUTH_ALLOWLIST))
        assert set(allowed) == set(tapes.TRUTH_ALLOWLIST), side
        opened = tape.truth_paths_opened()
        names = {pathlib.Path(path).stem for path in opened}
        assert names <= set(tapes.TRUTH_ALLOWLIST), f"{side}: opened {names}"
        # The loader's allowlist is PER CALL, so the contract to check is that
        # within a call it refuses to serve a leaf the caller did not allow --
        # which is exactly how the campaign uses it (always TRUTH_ALLOWLIST).
        for outside in ("menu_mae_cent", "entry_ts_ns", "cost_charged_cent"):
            assert outside in tape.leaf_names("truth"), f"{side}: {outside} is not on the tape"
            try:
                tape.truth(list(tapes.TRUTH_ALLOWLIST), names=[outside])
            except Exception:                              # noqa: BLE001
                continue
            raise AssertionError(f"{side}: truth() served {outside} outside the allowlist")
        # ... and the three additive truth leaves the driver documented are on
        # the tape but deliberately OUTSIDE the campaign's allowlist.
        for additive in ("entry_ts_ns", "gap_through_cent", "cost_charged_cent"):
            assert additive not in tapes.TRUTH_ALLOWLIST, additive


@check("two loads of the same rows produce bit-identical tensors")
def check_load_determinism(root: pathlib.Path, session: int, rows: np.ndarray) -> None:
    first = tapes.load_side(root, session, "S", rows=rows)[0]
    second = tapes.load_side(root, session, "S", rows=rows)[0]
    for field in ("candset", "loc_value", "direct", "r_modality", "micro_slot",
                  "micro_phase", "micro_ckpt", "bin_ref", "jsa_mod", "jsa_slot",
                  "jsa_phase", "jsa_ts_us"):
        assert torch.equal(getattr(first, field), getattr(second, field)), field
    for index in range(len(arms.MODALITIES)):
        assert torch.equal(first.groups[index], second.groups[index])
        assert torch.equal(first.bin_seg[index], second.bin_seg[index])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=DEFAULT_ROOT)
    parser.add_argument("--session", type=int, default=125)
    parser.add_argument("--rows", type=int, default=256)
    parser.add_argument("--verify-sha", action="store_true")
    args = parser.parse_args(argv)
    root = pathlib.Path(args.root)

    rows = np.arange(2000, 2000 + args.rows, dtype=np.int64)
    loaded = {side: tapes.load_side(root, args.session, side, rows=rows,
                                    verify_sha=args.verify_sha)
              for side in tapes.SIDES}

    check_forward(loaded)
    check_indices(loaded)
    check_masks(loaded)
    check_orientation_is_a_reduction(loaded)
    check_orientation_law(root, args.session)
    check_truth_receipt(root, args.session)
    check_load_determinism(root, args.session, rows)

    failures = 0
    for name, passed, detail in RESULTS:
        if passed:
            print(f"PASS: {name}")
        else:
            failures += 1
            print(f"FAIL: {name}\n{detail}")
    print(f"{len(RESULTS) - failures}/{len(RESULTS)} real-tape checks passed "
          f"(session {args.session}, {args.rows} rows per side)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
