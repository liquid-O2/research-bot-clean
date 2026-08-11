"""verify_co_train.py — ACCEPTANCE for the co-trained group (red-first).

Co-training is only a SCHEDULING change if every arm comes out exactly as its
solo twin.  This proves that against the real corpus:

  1. each co-trained arm's published logits are BIT-IDENTICAL to the same arm
     trained solo, on both sides of every scored session;
  2. running the group twice reproduces byte-identical logits (two-run identity);
  3. every arm publishes its OWN receipt -- separate curves, separate GPU
     receipt, separate config hash;
  4. the arms really are independent: their logits are NOT equal to each other
     (a co-trainer that accidentally shared weights would pass 1-3 and be wrong).

Any mismatch in (1) is a DEFECT, not something to rationalise away.

usage: verify_co_train.py [--arms quad|trio] [--sessions N] [--epochs N]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys
from dataclasses import replace

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import co_train    # noqa: E402
import train       # noqa: E402

DATA = "/workspace/artifacts/tensors/v4.0/run1"
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arms", default="quad")
    parser.add_argument("--fold", default="F4")
    parser.add_argument("--sessions", type=int, default=2)
    parser.add_argument("--eval-sessions", type=int, default=1)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args(argv)

    names = {"quad": co_train.NATIVE_QUAD, "trio": co_train.CHEAP_TRIO}.get(
        args.arms, tuple(part for part in args.arms.split(",") if part))
    root = pathlib.Path("/workspace/artifacts/cache/campaign/r4/co_train_acceptance")
    if root.exists():
        shutil.rmtree(root)

    base = train.RunConfig(
        arm=names[0], fold=args.fold, data=DATA, out="", epochs=args.epochs,
        device=args.device, max_train_sessions=args.sessions,
        max_eval_sessions=args.eval_sessions)

    # --- the co-trained group ----------------------------------------------
    co_train.co_train(names, base, root / "co")
    # --- and again, for two-run identity ------------------------------------
    co_train.co_train(names, base, root / "co_again")

    # --- each arm, solo ------------------------------------------------------
    for name in names:
        result = train.train(replace(base, arm=name, out=str(root / "solo" / name)),
                             None)
        train.publish(result, root / "solo" / f"{name}_{args.fold}")

    identical, mismatches = True, []
    for name in names:
        solo = np.load(root / "solo" / f"{name}_{args.fold}" / "logits.npy")
        co = np.load(root / "co" / f"{name}_{args.fold}" / "logits.npy")
        if solo.shape != co.shape or not np.array_equal(solo, co):
            identical = False
            worst = (float(np.abs(solo - co).max())
                     if solo.shape == co.shape else float("nan"))
            mismatches.append(f"{name}: shapes {solo.shape} vs {co.shape}, "
                              f"max|delta|={worst:.3e}")
    check("every co-trained arm is BIT-IDENTICAL to its solo twin", identical,
          "; ".join(mismatches))

    two_run = True
    for name in names:
        first = np.load(root / "co" / f"{name}_{args.fold}" / "logits.npy")
        second = np.load(root / "co_again" / f"{name}_{args.fold}" / "logits.npy")
        if not np.array_equal(first, second):
            two_run = False
    check("running the group twice reproduces byte-identical logits", two_run)

    receipts, hashes = {}, set()
    for name in names:
        receipt = json.loads(
            (root / "co" / f"{name}_{args.fold}" / "receipt.json").read_text())
        receipts[name] = receipt
        hashes.add(receipt["config_sha256"])
    separate = (len(hashes) == len(names)
                and all(receipts[n]["config"]["arm"] == n for n in names)
                and all(receipts[n]["gpu_receipt"] for n in names)
                and all(receipts[n]["co_trained_with"] == list(names) for n in names))
    check("each arm publishes its own receipt (config hash, curve, GPU receipt)",
          separate, f"{len(hashes)} distinct config hashes for {len(names)} arms")

    distinct = True
    reference = np.load(root / "co" / f"{names[0]}_{args.fold}" / "logits.npy")
    for name in names[1:]:
        other = np.load(root / "co" / f"{name}_{args.fold}" / "logits.npy")
        if reference.shape == other.shape and np.array_equal(reference, other):
            distinct = False
    check("the arms are independent models, not one model published N times",
          distinct)

    if not args.keep:
        shutil.rmtree(root, ignore_errors=True)

    failures = 0
    for name, ok, detail in RESULTS:
        if ok:
            print(f"PASS: {name}")
        else:
            failures += 1
            print(f"FAIL: {name}" + (f"\n      {detail}" if detail else ""))
    print(f"{len(RESULTS) - failures}/{len(RESULTS)} co-train acceptance checks passed "
          f"({args.arms}: {', '.join(names)})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
