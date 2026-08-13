#!/usr/bin/python3
"""PORT M2 — FROZEN MECHANICAL BASELINES (CC-M2-4.1).

    "every scored day is also replayed under frozen zero-intelligence policies
     (EARLIEST-per-episode + value threshold ...).  The reader's headline =
     margin over the best mechanical baseline, day-paired, cluster-robust.
     Judgment must beat rules."

THE POLICY (zero intelligence, no sheet reading at all)
  1. group the day's candidates with EPISODE_CAUSAL — the FROZEN CC-M1-12 v2
     grouping (same session AND same side; link iff gap <= K*; anti-chaining
     split at SPAN_MAX), K*/SPAN_MAX read from the committed episode_v2
     receipt, never re-fitted here;
  2. keep the EARLIEST member of each episode (the arm the episode census
     scores at 0.899 capture-of-best on SI/close, i.e. a strong arm);
  3. TAKE it iff its D-071 CLASS CENSUS conditional value (the S13 class card,
     a committed population statistic that is strictly ex ante) is >= a frozen
     threshold.  The threshold is swept over the distinct class values present
     so the comparison is against the BEST arm, not a convenient one.

Everything the policy reads is available at the decision second and none of it
is candidate-specific judgement — that is the point.

Run:
  baseline_replay.py --index TRIAGE_INDEX.tsv --outdir DIR
"""
import argparse
import csv
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for p in (_HERE, os.path.join(os.path.dirname(_HERE), "port_m1")):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np                                            # noqa: E402
import episode_v2 as EV                                       # noqa: E402

# FROZEN, from artifacts/cache/port/m1/episodes_v2/EPISODE_V2_REPORT.md §P2
KSTAR = {("SI", -1): 150, ("SI", 1): 180, ("HG", -1): 120, ("HG", 1): 120,
         ("NKD", -1): 150, ("NKD", 1): 150}
SPAN_MAX = {("SI", -1): 588, ("SI", 1): 733, ("HG", -1): 413, ("HG", 1): 412,
            ("NKD", -1): 536, ("NKD", 1): 544}

# FROZEN, the D-071 E1 class census cards as printed in S13 of every sheet
COND_VALUE = {"REVERSAL-CONFIRMATION": 516.84, "RECLAIM": 500.14,
              "NEWS-WINDOW": 704.60, "OPEN-DYNAMICS": 650.35,
              "LEVEL-FIRST-TEST": 639.59}
THRESHOLDS = (0.0, 500.15, 516.85, 639.60, 650.36)


def episodes(rows):
    """{(asset, side): [[cid, ...], ...]} under EPISODE_CAUSAL."""
    out = {}
    by = {}
    for r in rows:
        side = 1 if r["side"] == "LONG" else -1
        by.setdefault((r["asset"], side), []).append(r)
    for key, rs in by.items():
        rs.sort(key=lambda r: int(r["sec"]))
        dec = np.array([int(r["sec"]) for r in rs], dtype=np.int64)
        spans = EV.group_causal(dec, KSTAR[key], SPAN_MAX[key])
        out[key] = [[rs[i]["cid"] for i in range(lo, hi)] for lo, hi in spans]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--outdir", required=True)
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.index).readlines()[1:], delimiter="\t"))
    idx = {r["cid"]: r for r in rows}
    eps = episodes(rows)
    earliest = set()
    n_ep = 0
    for key, groups in eps.items():
        n_ep += len(groups)
        for g in groups:
            earliest.add(min(g, key=lambda c: int(idx[c]["sec"])))
    sys.stderr.write("EPISODE_CAUSAL: %d episodes over %d candidates "
                     "(%.2f cand/episode)\n"
                     % (n_ep, len(rows), len(rows) / float(n_ep)))
    os.makedirs(a.outdir, exist_ok=True)
    for th in THRESHOLDS:
        name = "BASE_EARLIEST_CV%d" % int(th)
        path = os.path.join(a.outdir, name + ".tsv")
        n = 0
        with open(path, "w") as fh:
            fh.write("cid\tcall\tconf\tprimary\n")
            for r in rows:
                take = (r["cid"] in earliest
                        and COND_VALUE.get(r["cls"], 0.0) >= th)
                n += bool(take)
                fh.write("%s\t%s\tC\tprimary: frozen mechanical policy — "
                         "EARLIEST member of its EPISODE_CAUSAL group "
                         "(K*=%ds) and S13 class census cond_value$=%.2f "
                         "vs threshold $%.2f\n"
                         % (r["cid"], "TAKE" if take else "SKIP",
                            KSTAR[(r["asset"], 1 if r["side"] == "LONG" else -1)],
                            COND_VALUE.get(r["cls"], 0.0), th))
        sys.stderr.write("  %s: %d TAKE -> %s\n" % (name, n, path))


if __name__ == "__main__":
    main()
