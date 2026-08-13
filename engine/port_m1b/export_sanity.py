#!/usr/bin/python3
"""PORT M1.B — sane_thresholds.tsv -> QRSANE1 receipts for the C++ label engine.

CC-M1-4 / D-054 with CC-M1-5 D15: the mid-sanity ceiling is
`min(10 x pooled same-phase trailing-60-session median spread_$, $500)`, with a
warm-up phase falling back to the cap.  That definition lives in
engine/port_m1/b7_sane.py, which already wrote the per-(asset, date, phase)
THRESHOLDS.  This exporter hands them to qr_skel; the engine never recomputes
them, so there is exactly one definition of the mask in the program.

usage: export_sanity.py [ASSET ...]
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import binpack  # noqa: E402

SRC = "/workspace/artifacts/cache/port/m1/sane/sane_thresholds.tsv"
OUT_DIR = "/workspace/artifacts/cache/port/m1/skel/sanity"
ASSETS = ("SI", "HG", "NKD")
PHASES = ("TOKYO", "LONDON", "NY")


def load():
    rows, cols = [], None
    with open(SRC) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            rows.append(dict(zip(cols, f)))
    return rows


def export(asset, rows):
    by_date = {}
    for r in rows:
        if r["asset"] != asset:
            continue
        d8 = int(r["trade_date"].replace("-", ""))
        p = PHASES.index(r["phase"])
        by_date.setdefault(d8, [float("nan")] * len(PHASES))[p] = float(r["threshold_usd"])
    dates = sorted(by_date)
    thr = np.array([by_date[d] for d in dates], dtype=np.float64)
    if not np.all(np.isfinite(thr)) or not np.all(thr > 0):
        bad = int((~np.isfinite(thr) | (thr <= 0)).sum())
        raise SystemExit("%s: %d phase thresholds are missing or non-positive"
                         % (asset, bad))
    stem = os.path.join(OUT_DIR, asset)
    binpack.write(stem, "QRSANE1",
                  [("date8", np.array(dates, dtype=np.int32)),
                   ("phase_threshold_usd", thr.reshape(-1))],
                  extra={"asset": asset, "phases": list(PHASES),
                         "source": os.path.basename(SRC), "n": len(dates)})
    print("%s -> %s.{bin,json}  sessions=%d  median_threshold=$%.0f"
          % (asset, stem, len(dates), float(np.median(thr))))


if __name__ == "__main__":
    rows = load()
    for a in (sys.argv[1:] or list(ASSETS)):
        export(a, rows)
