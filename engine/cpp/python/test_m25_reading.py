"""test_m25_reading — the M2.5 reading's red-first suite.

It proves four things the verdict rests on:
  1. the bounds come from the SHA-PINNED estimator and the vectorised draw
     reproduces it EXACTLY, not approximately;
  2. the affine encoding is FINAL_PLAN section 11's formula, with the floor
     fatal and the cap clipped-and-counted;
  3. the TRAIN wall holds on the Python side too;
  4. END TO END on published synthetic corpora: the gate FAILS on a corpus built
     to be unreachable and PASSES on one built to be reachable — the whole point
     of a gate that "CAN fail".

usage: python3 test_m25_reading.py [--scratch DIR] [--skip-end-to-end]
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import sys
import traceback
from typing import List, Tuple

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import m25_reading as m25  # noqa: E402

RESULTS: List[Tuple[str, bool, str]] = []

RELEASE_BIN = pathlib.Path("/workspace/artifacts/cache/cpp/release/bin")
CARD_SHA = "5c26438b12dd90e15b005375829d976fa46a1710c78041ff20ffc587dc092792"
SYNTH_SESSIONS = 50
SYNTH_CLOCKS = 3000
SYNTH_QGRID = "0.0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0"


def check(name: str):
    def decorate(function):
        def run(*args, **kwargs):
            try:
                function(*args, **kwargs)
            except Exception:  # noqa: BLE001 — a self-test reports, never raises
                RESULTS.append((name, False, traceback.format_exc()))
            else:
                RESULTS.append((name, True, ""))

        return run

    return decorate


def expect_refusal(name: str, thunk) -> None:
    try:
        thunk()
    except m25.ReadingError:
        return
    except Exception as error:  # noqa: BLE001
        raise AssertionError(f"{name}: refused with {type(error).__name__}") from error
    raise AssertionError(f"{name}: was ACCEPTED; it must be refused")


# --- 1. the pinned estimator ----------------------------------------------


@check("the pinned estimator is the sha registered in authorities/REGISTRY.tsv")
def check_pinned_sha() -> None:
    m25.assert_pinned_estimator()
    # And the check is a WALL, not a formality: point it at a sha the file does
    # not have and it must refuse rather than shrug.
    registered = m25._PINNED_SHA
    try:
        m25._PINNED_SHA = "0" * 64
        expect_refusal("a foreign estimator sha", m25.assert_pinned_estimator)
    finally:
        m25._PINNED_SHA = registered


@check("the vectorised block bootstrap reproduces the pinned entry point exactly")
def check_vectorised_parity() -> None:
    rng = np.random.default_rng(20260810)
    years = [2022] * 60 + [2023] * 55 + [2024] * 62
    ordinals = list(range(125, 125 + len(years)))
    indices = m25.block_draw_indices(years, ordinals)
    if indices.shape != (10000, len(years)):
        raise AssertionError(f"draw shape {indices.shape}")
    populations = []
    for _ in range(4):
        truths = np.full(len(years), 1_600_000, dtype=np.int64)
        hits = rng.integers(0, 1_600_001, size=len(years), dtype=np.int64)
        populations.append((hits, truths))
    # An INEXACT reproduction refuses; only bit-equality passes.
    m25.verify_pinned_parity(years, ordinals, indices, populations)


@check("a draw that is not the pinned draw is refused, not tolerated")
def check_parity_is_a_wall() -> None:
    years = [2022] * 20 + [2023] * 20
    ordinals = list(range(125, 165))
    indices = m25.block_draw_indices(years, ordinals)
    # An IID session bootstrap: the same shape and the same marginal population,
    # but not the pinned law's year-stratified WHOLE-BLOCK draw.
    tampered = np.random.default_rng(7).integers(0, len(years), size=indices.shape,
                                                 dtype=np.int32)
    truths = np.full(len(years), 1_600_000, dtype=np.int64)
    hits = (np.arange(len(years), dtype=np.int64) * 37_000) % 1_600_000
    expect_refusal(
        "a rolled draw",
        lambda: m25.verify_pinned_parity(years, ordinals, tampered, [(hits, truths)]),
    )


# --- 2. the affine encoding ------------------------------------------------


@check("the affine encoding is exactly hits = 100*x + 400,000 over truths = 100*(A+B)")
def check_affine_formula() -> None:
    cap = m25.AffineCap(400_000, 600_000, 10, (600_000,) * 7)
    nets = np.array([-399_999, -1, 0, 1, 250_000, 600_000], dtype=np.int64)
    encoded = m25.affine_encode(nets, cap)
    if list(encoded.hits) != [1, 399_999, 400_000, 400_001, 650_000, 1_000_000]:
        raise AssertionError(f"hits {list(encoded.hits)}")
    if set(encoded.truths.tolist()) != {1_000_000}:
        raise AssertionError(f"truths {set(encoded.truths.tolist())}")
    if encoded.cap_violations or encoded.floor_violations:
        raise AssertionError("no violation should have been recorded")


@check("a session below the -$4,000 floor is fatal and never silently clipped")
def check_floor_is_fatal() -> None:
    cap = m25.AffineCap(400_000, 600_000, 10, (600_000,) * 7)
    nets = np.array([1000, -400_001], dtype=np.int64)
    expect_refusal("a floor violation", lambda: m25.affine_encode(nets, cap))


@check("a session above the cap is clipped and counted, conservatively")
def check_cap_is_clipped_and_counted() -> None:
    cap = m25.AffineCap(400_000, 600_000, 10, (600_000,) * 7)
    nets = np.array([1000, 600_001, 900_000], dtype=np.int64)
    encoded = m25.affine_encode(nets, cap)
    if encoded.cap_violations != 2:
        raise AssertionError(f"cap violations {encoded.cap_violations}")
    if int(encoded.hits.max()) != 1_000_000:
        raise AssertionError("a clipped session must sit exactly at truths")


@check("B is the nearest-rank p99.9 of the perfect-skill envelope")
def check_cap_derivation() -> None:
    envelope = {h: np.arange(1, 1001, dtype=np.int64) * 1000 for h in range(7)}
    cap = m25.derive_affine_cap(envelope)
    # 7,000 pooled values; ceil(0.999*7000) = 6,993 -> the 6,993rd smallest.
    pooled = np.sort(np.concatenate([envelope[h] for h in range(7)]))
    if cap.cap_cent != int(pooled[6992]):
        raise AssertionError(f"cap {cap.cap_cent} != {int(pooled[6992])}")
    if cap.floor_cent != 400_000:
        raise AssertionError("the floor is preregistered at $4,000 and is not derived")


# --- 3. the drawdown sibling ----------------------------------------------


@check("the drawdown is the exact zero-inclusive end-of-day law, E0 in the running max")
def check_point_mdd() -> None:
    # +2000, 0, -90000 -> equity 2000, 2000, -88000; running max includes E0 = 0,
    # so the drawdown is 2000 - (-88000) = 90000c = $900.
    nets = np.array([2000, 0, -90000], dtype=np.int64)
    got = m25.point_mdd_dollars(nets)
    if abs(got - 900.0) > 1e-9:
        raise AssertionError(f"mdd {got}")
    # A monotone rising equity never draws down, and a first-day loss draws down
    # from E0 = 0 (not from the first equity), which is the whole point of the law.
    if m25.point_mdd_dollars(np.array([100, 200, 300], dtype=np.int64)) != 0.0:
        raise AssertionError("a rising equity cannot draw down")
    if m25.point_mdd_dollars(np.array([-50_000, 10_000], dtype=np.int64)) != 500.0:
        raise AssertionError("E0 must be in the running maximum")


@check("the MDD upper bound is a genuine 95th percentile of the resampled drawdowns")
def check_mdd_ucb() -> None:
    years = [2022] * 25 + [2023] * 25
    ordinals = list(range(125, 175))
    indices = m25.block_draw_indices(years, ordinals)
    nets = np.full(50, 10_000, dtype=np.int64)
    if m25.mdd_ucb_dollars(nets, indices) != 0.0:
        raise AssertionError("an all-positive stream has no drawdown in any resample")
    losing = np.full(50, -10_000, dtype=np.int64)
    # Every resample is 50 losses of $100 -> a $5,000 drawdown, exactly.
    if abs(m25.mdd_ucb_dollars(losing, indices) - 5000.0) > 1e-9:
        raise AssertionError("an all-negative stream draws down its whole equity")
    mixed = np.where(np.arange(50) % 7 < 3, 30_000, -20_000).astype(np.int64)
    ucb = m25.mdd_ucb_dollars(mixed, indices)
    point = m25.point_mdd_dollars(mixed)
    if not ucb >= point:
        raise AssertionError(f"the 95th percentile {ucb} is under the point drawdown {point}")
    # THE INDEX RULE, pinned: the sibling reports the ascending replicate at
    # floor(0.95*(R-1)) — the mirror image of the pinned lower bound's
    # floor(0.05*(R-1)) — and it is a genuinely UPPER tail of a spread
    # distribution, not the lower one under another name.
    drawn = mixed[indices].astype(np.int64)
    equity = np.cumsum(drawn, axis=1)
    running = np.maximum(np.maximum.accumulate(equity, axis=1), 0)
    per_replicate = np.sort((running - equity).max(axis=1))
    if abs(ucb - per_replicate[9499] / 100.0) > 1e-9:
        raise AssertionError(f"ucb {ucb} is not the 9,499th ascending replicate")
    if not per_replicate[9499] > per_replicate[499]:
        raise AssertionError("the fixture does not separate the two tails; strengthen it")


# --- 4. end to end on published synthetic corpora --------------------------


def _run(command: List[str]) -> None:
    finished = subprocess.run(command, capture_output=True, text=True)
    if finished.returncode != 0:
        raise AssertionError(f"{' '.join(command)}\n{finished.stdout}\n{finished.stderr}")


def build_corpus(scratch: pathlib.Path, mode: str) -> pathlib.Path:
    corpus = scratch / f"synth_{mode}"
    receipts = scratch / f"out_{mode}"
    if not (receipts / "run.tsv").exists():
        shutil.rmtree(corpus, ignore_errors=True)
        _run([str(RELEASE_BIN / "qr_m25_synth"), "--base", str(corpus), "--mode", mode,
              "--sessions", str(SYNTH_SESSIONS), "--clocks", str(SYNTH_CLOCKS),
              "--spacing-seconds", "1", "--card-sha", CARD_SHA])
        _run([str(RELEASE_BIN / "qr_m25_run"), "--run", str(corpus), "--fold", "F4",
              "--out", str(receipts), "--mode", "all", "--first", "125",
              "--last", str(125 + SYNTH_SESSIONS - 1), "--threads", "12",
              "--replicates", "2", "--qgrid", SYNTH_QGRID])
    return receipts


def read(receipts: pathlib.Path) -> m25.FoldReading:
    bundle = m25.load_receipts(receipts)
    arms = m25.load_arms(receipts)
    return m25.read_fold(bundle, arms, "F4", allow_partial_train=True)


@check("the gate FAILS on a corpus built so that Q* > Q_max by construction")
def check_unreachable_fails(scratch: pathlib.Path) -> None:
    reading = read(build_corpus(scratch, "unreachable"))
    if reading.verdict == "PASS":
        raise AssertionError(f"the unreachable corpus PASSED: {reading}")
    if reading.q_star is None:
        raise AssertionError("the unreachable corpus must still HAVE a required skill")
    if not reading.q_star > reading.q_max:
        raise AssertionError(f"q*={reading.q_star} q_max={reading.q_max}")
    # It is unreachable because the prefix carries nothing, not because the
    # dollars are absent: perfect skill earns far more than the bar.
    if reading.q_max > 0.5:
        raise AssertionError(f"an independent prefix must collapse the ceiling: {reading.q_max}")


@check("the gate PASSES on a corpus built so that Q* <= Q_max by construction")
def check_reachable_passes(scratch: pathlib.Path) -> None:
    reading = read(build_corpus(scratch, "reachable"))
    if reading.verdict != "PASS":
        raise AssertionError(f"the reachable corpus did not pass: {reading.verdict}")
    if reading.q_star is None or not reading.q_star <= reading.q_max:
        raise AssertionError(f"q*={reading.q_star} q_max={reading.q_max}")
    if reading.q_max < 0.9:
        raise AssertionError(f"a determining prefix must lift the ceiling: {reading.q_max}")


@check("the two corpora differ in the CEILING, not in the dollars")
def check_the_difference_is_observability(scratch: pathlib.Path) -> None:
    reachable = read(build_corpus(scratch, "reachable"))
    unreachable = read(build_corpus(scratch, "unreachable"))
    # Same generating scale, so the required skill is the same to within a grid
    # step; what separates PASS from FAIL is Q_max alone.
    if abs((reachable.q_star or 0) - (unreachable.q_star or 0)) > 0.15:
        raise AssertionError(
            f"the constructions were meant to differ only in observability: "
            f"{reachable.q_star} vs {unreachable.q_star}")
    if not reachable.q_max > unreachable.q_max + 0.5:
        raise AssertionError(f"{reachable.q_max} vs {unreachable.q_max}")


@check("the reading is reproducible: two reads of one receipt agree exactly")
def check_reading_is_reproducible(scratch: pathlib.Path) -> None:
    first = read(build_corpus(scratch, "reachable"))
    second = read(build_corpus(scratch, "reachable"))
    if (first.q_star, first.q_max, first.cap.cap_cent, first.verdict) != (
            second.q_star, second.q_max, second.cap.cap_cent, second.verdict):
        raise AssertionError("the reading is not deterministic")
    if first.pinned_lcb_dollars != second.pinned_lcb_dollars:
        raise AssertionError("the pinned bound is not deterministic")


@check("the reading refuses a fold whose TRAIN range the receipts do not cover")
def check_train_coverage_wall(scratch: pathlib.Path) -> None:
    receipts = build_corpus(scratch, "reachable")
    bundle = m25.load_receipts(receipts)
    arms = m25.load_arms(receipts)
    # The synthetic covers 125..174, so neither F4 (125..395) nor F5 (125..520) is
    # covered: reading either without the declared fixture flag would bound a
    # different population than the verdict names.
    expect_refusal("an uncovered F4", lambda: m25.read_fold(bundle, arms, "F4"))
    expect_refusal("an uncovered F5", lambda: m25.read_fold(bundle, arms, "F5"))


@check("the reading refuses a session outside the fold's TRAIN range")
def check_out_of_range_session(scratch: pathlib.Path) -> None:
    receipts = build_corpus(scratch, "reachable")
    bundle = m25.load_receipts(receipts)
    bundle.sweep_sessions = list(bundle.sweep_sessions)
    bundle.sweep_sessions[-1] = 700  # a TEST ordinal smuggled into the receipts
    bundle.session_year[700] = 2024
    arms = m25.load_arms(receipts)
    expect_refusal("a TEST session in the receipts",
                   lambda: m25.read_fold(bundle, arms, "F4", allow_partial_train=True))


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch", type=pathlib.Path,
                        default=pathlib.Path("/workspace/artifacts/cache/m25_scratch"))
    parser.add_argument("--skip-end-to-end", action="store_true")
    args = parser.parse_args(argv)
    args.scratch.mkdir(parents=True, exist_ok=True)

    check_pinned_sha()
    check_vectorised_parity()
    check_parity_is_a_wall()
    check_affine_formula()
    check_floor_is_fatal()
    check_cap_is_clipped_and_counted()
    check_cap_derivation()
    check_point_mdd()
    check_mdd_ucb()
    if not args.skip_end_to_end:
        check_unreachable_fails(args.scratch)
        check_reachable_passes(args.scratch)
        check_the_difference_is_observability(args.scratch)
        check_reading_is_reproducible(args.scratch)
        check_train_coverage_wall(args.scratch)
        check_out_of_range_session(args.scratch)

    failures = 0
    for name, passed, detail in RESULTS:
        if passed:
            print(f"PASS: {name}")
        else:
            failures += 1
            print(f"FAIL: {name}\n{detail}")
    print(f"{len(RESULTS) - failures}/{len(RESULTS)} M2.5 reading checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
