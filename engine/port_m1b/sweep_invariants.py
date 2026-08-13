#!/usr/bin/python3
"""PORT M1.B S3 — corpus-wide structural sweep over every emitted shard.

Parity (compare_skel.py) proves the arithmetic on stratified sessions; this
proves the STRUCTURAL laws hold on all 2.48M candidates, where a brute-force
oracle cannot go:

  1. FIXED SHAPE: len(tau_up) == len(tau_dn) == rows * 200, per anchor, always.
  2. tau monotonicity in k: a larger rung can never be reached earlier.
  3. tau values are either -1 or a session second >= anchor_sec.
  4. UNAVAILABLE typing: observed_secs == 0  <=>  the full null fill
     (all tau -1, every float NaN, f_len == a_len == 0), and never the reverse.
  5. NO -0.0 in any emitted float array (CONV C4).
  6. record sequences are strictly increasing in BOTH time and float64-visible
     value, and their offsets tile the ragged arrays exactly once, in order.
  7. mfe >= 0, mae >= 0, giveback >= 0, 0 <= uw_share <= 1,
     0 <= monotonicity <= 1, time_to_peak >= 0.

usage: sweep_invariants.py [--workers N] [ASSET ...]
"""
import argparse
import glob
import json
import multiprocessing as mp
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import binpack  # noqa: E402

SKEL = "/workspace/artifacts/cache/port/m1/skel"
RUNGS = 200
ANCHORS = 2
FLOATS = ("entry_mid", "f_h30", "f_h60", "f_h120", "f_phase_close",
          "f_sess_close", "mfe_usd", "mae_before_argmax_usd",
          "mae_unwalled_usd", "f_terminal_usd", "giveback_post_peak_usd",
          "uw_share", "monotonicity")


def check_shard(path):
    stem = path[:-len(".json")]
    _, S = binpack.read(stem, "QRSKEL1")
    n = S["cand_id"].size
    bad = []

    def fail(msg):
        bad.append("%s: %s" % (os.path.basename(stem), msg))

    for a in range(ANCHORS):
        p = "a%d_" % a
        up = S[p + "tau_up"]
        dn = S[p + "tau_dn"]
        if up.size != n * RUNGS or dn.size != n * RUNGS:
            fail("law1 tensor shape %d/%d != %d" % (up.size, dn.size, n * RUNGS))
            continue
        up = up.reshape(n, RUNGS)
        dn = dn.reshape(n, RUNGS)
        obs = S[p + "observed_secs"]
        anc = S[p + "anchor_sec"]

        # law 2: within a row, tau is non-decreasing in k once the -1 tail starts
        for t in (up, dn):
            hit = t >= 0
            # a hit rung after a null rung is impossible (nulls are a suffix)
            if np.any(hit[:, 1:] & ~hit[:, :-1]):
                fail("law2 a null rung is followed by a hit rung")
            d = np.diff(t, axis=1)
            if np.any((hit[:, 1:] & hit[:, :-1]) & (d < 0)):
                fail("law2 tau decreases with the rung")
            # law 3
            if np.any(hit & (t < anc[:, None])):
                fail("law3 a touch precedes its anchor")

        # law 4: the unavailable typing, both directions
        un = obs == 0
        if np.any(un):
            if not np.all(up[un] == -1) or not np.all(dn[un] == -1):
                fail("law4 an unavailable anchor carries a tau")
            if not np.all(S[p + "f_len"][un] == 0) or not np.all(S[p + "a_len"][un] == 0):
                fail("law4 an unavailable anchor carries records")
            for f in FLOATS:
                if not np.all(np.isnan(S[p + f][un])):
                    fail("law4 %s is not NaN on an unavailable anchor" % f)
        av = ~un
        if np.any(av) and np.any(np.isnan(S[p + "mfe_usd"][av])):
            fail("law4 an available anchor has a NaN MFE")

        # law 5: no negative zero anywhere
        for f in FLOATS:
            v = np.ascontiguousarray(S[p + f])
            if np.any(np.signbit(v) & (v == 0.0)):
                fail("law5 %s carries -0.0" % f)
        for f in ("skel_f_v", "skel_a_v"):
            v = np.ascontiguousarray(S[p + f])
            if np.any(np.signbit(v) & (v == 0.0)):
                fail("law5 %s carries -0.0" % f)

        # law 6: records tile the ragged arrays in order and strictly increase
        for off_k, len_k, t_k, v_k in (("f_off", "f_len", "skel_f_t", "skel_f_v"),
                                       ("a_off", "a_len", "skel_a_t", "skel_a_v")):
            off, ln = S[p + off_k], S[p + len_k]
            if n and (off[0] != 0 or not np.array_equal(off[1:], np.cumsum(ln)[:-1])
                      or off[-1] + ln[-1] != S[p + t_k].size):
                fail("law6 %s offsets do not tile %s" % (off_k, t_k))
                continue
            tt, vv = S[p + t_k], S[p + v_k]
            # strict increase inside each block: check globally, then repair the
            # block boundaries (a block start is allowed to drop).
            start = off[ln > 0]
            if tt.size > 1:
                dmask = np.ones(tt.size - 1, dtype=bool)
                dmask[start[start > 0] - 1] = False
                if np.any((np.diff(tt) <= 0) & dmask):
                    fail("law6 %s is not strictly increasing in time" % t_k)
                if np.any((np.diff(vv.astype(np.float64)) <= 0) & dmask):
                    fail("law6 %s is not strictly increasing in value" % v_k)

        # law 7: sign laws on the available rows
        if np.any(av):
            if np.any(S[p + "mfe_usd"][av] < 0) or np.any(S[p + "mae_unwalled_usd"][av] < 0):
                fail("law7 a negative MFE or MAE")
            if np.any(S[p + "mae_before_argmax_usd"][av] < 0):
                fail("law7 a negative MAE-before-argmax")
            if np.any(S[p + "giveback_post_peak_usd"][av] < 0):
                fail("law7 a negative giveback")
            u = S[p + "uw_share"][av]
            if np.any(u < 0) or np.any(u > 1):
                fail("law7 uw_share outside [0,1]")
            mo = S[p + "monotonicity"][av]
            mo = mo[~np.isnan(mo)]
            if mo.size and (np.any(mo < 0) or np.any(mo > 1)):
                fail("law7 monotonicity outside [0,1]")
            if np.any(S[p + "time_to_peak_secs"][av] < 0):
                fail("law7 a negative time-to-peak")
    return int(n), bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("assets", nargs="*", default=["SI", "HG", "NKD"])
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    files = []
    for a in (args.assets or ["SI", "HG", "NKD"]):
        files += sorted(glob.glob(os.path.join(SKEL, "shards", "%s_2*.json" % a)))
    with mp.Pool(args.workers) as pool:
        res = pool.map(check_shard, files)
    rows = sum(r[0] for r in res)
    bad = [m for r in res for m in r[1]]
    receipt = {"shards": len(files), "candidates": rows,
               "anchors": rows * ANCHORS,
               "tensor_cells": rows * ANCHORS * 2 * RUNGS,
               "violations": len(bad), "examples": bad[:10],
               "verdict": "PASS" if not bad else "FAIL"}
    out = os.path.join(SKEL, "parity")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "sweep.receipt.json"), "w") as fh:
        json.dump(receipt, fh, indent=1, sort_keys=True)
    print(json.dumps(receipt, sort_keys=True, indent=1))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
