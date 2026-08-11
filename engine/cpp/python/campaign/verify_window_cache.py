"""verify_window_cache.py — ACCEPTANCE for the disk-backed oriented-window cache.

The cache only earns its place if its bytes are the exact f32 the live path
produces.  This proves that end to end, on the real corpus:

  1. every baked window is bit-identical to the live computation;
  2. an arm's logits through the cache are BIT-IDENTICAL to its logits through
     the live path, on BOTH sides of the session;
  3. every shard re-hashes to the sha256 in its own index (the receipt);
  4. baking twice produces byte-identical shards (two-run identity);
  5. a stale cache is REFUSED, not silently used.

usage: verify_window_cache.py [--session N] [--root DIR] [--keep]
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import shutil
import sys
import time

import numpy as np
import torch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import arms            # noqa: E402
import train           # noqa: E402
import window_cache    # noqa: E402

DATA = pathlib.Path("/workspace/artifacts/tensors/v4.0/run1")
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(condition), detail))


def shard_digest(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 22), b""):
            digest.update(block)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=int, default=125)
    parser.add_argument("--root", default=None)
    parser.add_argument("--fold", default="F4")
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args(argv)

    root = pathlib.Path(args.root) if args.root else (
        pathlib.Path("/workspace/artifacts/cache/campaign/r4/window_cache_acceptance"))
    if root.exists():
        shutil.rmtree(root)

    train.set_determinism("cpu")
    config = train.RunConfig(arm="NATIVE_ORDER", fold=args.fold, data=str(DATA),
                             out="", epochs=1, device="cpu")
    session = train.load_sessions(DATA, [args.session], with_groups=True)[0]

    # --- 1. bake, and compare every window against the live computation -----
    started = time.time()
    written = window_cache.bake_session(root, args.fold, session, config, train)
    bake_seconds = time.time() - started
    baked_bytes = sum(row["bytes"] for row in written.values())

    cache = window_cache.WindowCache(root, args.fold)
    mismatched = 0
    for side in ("L", "S"):
        batch, _ = session.sides[side]
        reader = cache.reader(args.session, side)
        for lo, rows in window_cache._windows(session, side, config, train):
            if rows.numel() == 0:
                continue
            sliced_micro = batch.micro_slot[rows]
            sliced_bin_ref = batch.bin_ref[rows]
            sliced_jsa = batch.jsa_slot[rows]
            sliced_mod = batch.jsa_mod[rows]
            for modality in range(window_cache.MODALITIES):
                slot = sliced_micro[:, modality]
                reference = sliced_bin_ref[:, modality]
                jsa_here = torch.where(sliced_mod == modality, sliced_jsa,
                                       torch.full_like(sliced_jsa, -1))
                geometry = train.window_geometry(batch, modality, slot, reference,
                                                 jsa_here)
                if geometry is None:
                    continue
                low, high, _, _ = geometry
                live = train.window_bytes(batch, modality, low, high)
                stored = reader.read(lo, modality, low, high)
                if not np.array_equal(live, stored):
                    mismatched += 1
    check("every baked window is bit-identical to the live computation",
          mismatched == 0, f"{mismatched} window(s) differ")

    # --- 2. logits through the cache vs through the live path ---------------
    worst = 0.0
    identical = True
    for side in ("L", "S"):
        batch, _ = session.sides[side]
        for lo, rows in window_cache._windows(session, side, config, train):
            if rows.numel() == 0:
                continue
            key = (args.session, side, lo)
            live_batch = train.slice_batch(batch, rows)
            cached_batch = train.slice_batch(batch, rows, cache=cache, key=key)
            torch.manual_seed(train.SEED)
            model_a = arms.build_arm("NATIVE_ORDER").eval()
            torch.manual_seed(train.SEED)
            model_b = arms.build_arm("NATIVE_ORDER").eval()
            with torch.no_grad():
                first, second = model_a(live_batch), model_b(cached_batch)
            if not torch.equal(first, second):
                identical = False
                worst = max(worst, float((first - second).abs().max()))
    check("an arm's logits through the CACHE are bit-identical to the live path",
          identical, f"max|delta| = {worst:.3e}")

    # --- 3. the sha receipt -------------------------------------------------
    receipts_ok = True
    for side in ("L", "S"):
        binary_path, _ = window_cache.shard_paths(root, args.fold, args.session, side)
        reader = cache.reader(args.session, side)
        if shard_digest(binary_path) != reader.index["sha256"] or not reader.verify():
            receipts_ok = False
    check("every shard re-hashes to the sha256 in its own index", receipts_ok)

    # --- 4. two-run identity ------------------------------------------------
    first_digests = {side: shard_digest(
        window_cache.shard_paths(root, args.fold, args.session, side)[0])
        for side in ("L", "S")}
    second_root = root.with_name(root.name + "_again")
    if second_root.exists():
        shutil.rmtree(second_root)
    window_cache.bake_session(second_root, args.fold, session, config, train)
    second_digests = {side: shard_digest(
        window_cache.shard_paths(second_root, args.fold, args.session, side)[0])
        for side in ("L", "S")}
    check("baking twice produces byte-identical shards",
          first_digests == second_digests,
          f"{first_digests} vs {second_digests}")

    # --- 5. a stale cache is refused ----------------------------------------
    refused = False
    try:
        cache.reader(args.session, "L").read(0, 0, -12345, -12000)
    except window_cache.WindowCacheError:
        refused = True
    except Exception:                                       # noqa: BLE001
        refused = False
    check("a window whose geometry disagrees with the cache is REFUSED", refused)

    if not args.keep:
        shutil.rmtree(root, ignore_errors=True)
        shutil.rmtree(second_root, ignore_errors=True)

    failures = 0
    for name, passed, detail in RESULTS:
        if passed:
            print(f"PASS: {name}")
        else:
            failures += 1
            print(f"FAIL: {name}" + (f"\n      {detail}" if detail else ""))
    print(f"{len(RESULTS) - failures}/{len(RESULTS)} window-cache acceptance checks "
          f"passed (session {args.session}, {baked_bytes / 2**20:.0f} MB baked in "
          f"{bake_seconds:.1f}s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
