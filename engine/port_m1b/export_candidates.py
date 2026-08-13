#!/usr/bin/python3
"""PORT M1.B S3 — roster -> QRCAND1 candidate receipt (CONV C2).

The label engine is ROSTER-AGNOSTIC: it consumes (cand_id, date8, dec_sec,
side, atr14_usd) and nothing else.  This exporter is the only place that knows
what a roster npz looks like, so S1 replacing the candidate SET replaces only
this file's input, never the engine.

usage: export_candidates.py [ASSET ...]
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import binpack  # noqa: E402

ROSTER_DIR = "/workspace/artifacts/cache/port/m1/generation"
OUT_DIR = "/workspace/artifacts/cache/port/m1/skel/candidates"
ASSETS = ("SI", "HG", "NKD")


def export(asset):
    src = os.path.join(ROSTER_DIR, "union_roster_%s.npz" % asset)
    z = np.load(src, allow_pickle=False)
    date8 = np.asarray(z["date8"], dtype=np.int32)
    dec_sec = np.asarray(z["dec_sec"], dtype=np.int32)
    side = np.asarray(z["side"], dtype=np.int8)
    atr = np.asarray(z["atr14_usd"], dtype=np.float64)
    n = date8.size
    if not (dec_sec.size == side.size == atr.size == n):
        raise SystemExit("%s: roster columns have unequal lengths" % asset)
    if np.any(np.diff(date8.astype(np.int64)) < 0):
        raise SystemExit("%s: roster date8 is not non-decreasing" % asset)
    if not np.all(np.isin(side, (-1, 1))):
        raise SystemExit("%s: roster side column is not +/-1" % asset)
    cand_id = np.arange(n, dtype=np.int64)   # the row ordinal in THIS roster
    stem = os.path.join(OUT_DIR, asset)
    binpack.write(stem, "QRCAND1",
                  [("cand_id", cand_id), ("date8", date8), ("dec_sec", dec_sec),
                   ("side", side), ("atr14_usd", atr)],
                  extra={"asset": asset, "source": os.path.basename(src),
                         "n": int(n)})
    print("%s -> %s.{bin,json}  n=%d sessions=%d"
          % (asset, stem, n, np.unique(date8).size))


if __name__ == "__main__":
    for a in (sys.argv[1:] or list(ASSETS)):
        export(a)
