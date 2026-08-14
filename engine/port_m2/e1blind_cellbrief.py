#!/usr/bin/python3
"""E1 BLIND — THE AS-OF CELL BRIEF (CC-M2-19.2 composition order SIDE > SEAT >
MOMENT, driven by the D14 as-of stepper).

For every (asset, phase) cell of a blind day, this prints WHAT IS KNOWABLE AT
THE CELL'S OPEN — strictly the driver prefix whose cut is the last one at or
before the cell's first candidate row.  Nothing from later in the day is read
(that is the D14 leak the blind round exists to prevent), and no S14 file
exists in this round at all.

The reader writes its per-cell side read and its would-abstain flag from this
brief; neither ever gates a call (stage 2 has zero validated hand instruments,
CC-M2-21.2).
"""
import argparse
import csv
import os
import sys


def read_tsv(path):
    with open(path) as fh:
        return list(csv.DictReader([l for l in fh if not l.startswith("#")],
                                   delimiter="\t"))


def f(r, k):
    try:
        return float(r[k])
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drive", required=True)
    ap.add_argument("--full", required=True)
    a = ap.parse_args()

    full = read_tsv(a.full)
    full.sort(key=lambda r: (int(float(r["sec"])), r["cid"]))
    cells = {}
    for r in full:
        cells.setdefault((r["asset"], r["phase_dec"]), []).append(r)

    files = sorted(fn for fn in os.listdir(a.drive) if fn.startswith("ASOF_"))
    cuts = []
    for fn in files:
        try:
            cuts.append((int(fn.split("_")[1].split(".")[0]), fn))
        except Exception:
            continue
    cuts.sort()

    order = sorted(cells, key=lambda k: int(float(cells[k][0]["sec"])))
    for k in order:
        rows = cells[k]
        first = rows[0]
        open_sec = int(float(first["sec"]))
        pref = [fn for sec, fn in cuts if sec <= open_sec]
        prow = []
        if pref:
            prow = [r for r in read_tsv(os.path.join(a.drive, pref[-1]))
                    if r["asset"] == first["asset"]]
        print("=" * 78)
        print("CELL %s/%s — opens %s (sec %d), %d candidates in the cell"
              % (k[0], k[1], first["clock"], open_sec, len(rows)))
        print("  as-of prefix: %s (%d rows of this asset visible)"
              % (pref[-1] if pref else "NONE (first cell of the day)",
                 len(prow)))
        print("  AT THE OPEN — session state (prefix only):")
        print("    day_type_so_far=%s range_so_far=%s range_vs_hat=%s%% "
              "cov_sess=%s unspent_sess=%s"
              % (first.get("day_type_so_far"), first.get("range_so_far"),
                 first.get("range_vs_hat_pct"), first.get("cov_sess"),
                 first.get("unspent_sess")))
        print("    vol: rv1800=%s rv300=%s rv60=%s rv_collapse=%s "
              "vol_regime=%s surprise=%s q10/q50=%s/%s ladder=%s"
              % (first.get("rv1800"), first.get("rv300"), first.get("rv60"),
                 first.get("rv_collapse"), first.get("vol_regime"),
                 first.get("surprise"), first.get("q10"), first.get("q50"),
                 first.get("ladder_pos")))
        print("    phase: H=%s (%ss) L=%s (%ss) runway_phase=%s exit_is_sess=%s"
              % (first.get("phase_H"), first.get("phase_H_sec"),
                 first.get("phase_L"), first.get("phase_L_sec"),
                 first.get("runway_phase"), first.get("exit_is_sess")))
        print("    flows: fph_sflow=%s/%s f30m=%s/%s f5m=%s/%s f60=%s/%s"
              % (first.get("fph_sflow"), first.get("fph_vol"),
                 first.get("f30m_sflow"), first.get("f30m_vol"),
                 first.get("f5m_sflow"), first.get("f5m_vol"),
                 first.get("f60_sflow"), first.get("f60_vol")))
        print("    fuel map: above=%s below=%s total=%s thru n/bid/ask=%s/%s/%s"
              % (first.get("trapped_above"), first.get("trapped_below"),
                 first.get("phase_total"), first.get("thru_n"),
                 first.get("thru_bid"), first.get("thru_ask")))
        print("    profile: d_POC=%s in_VA=%s | schedule: last_age=%s "
              "next_in=%s | mid=%s spread=%s cost_rt=%s"
              % (first.get("d_POC"), first.get("in_VA"),
                 first.get("sched_last_age"), first.get("sched_next_in"),
                 first.get("mid"), first.get("spread_dec"),
                 first.get("cost_rt")))
        # what the asset has already done today, prefix-only
        if prow:
            mids = [f(r, "mid") for r in prow if f(r, "mid") is not None]
            secs = [int(float(r["sec"])) for r in prow]
            if mids:
                print("  ASSET SO FAR (prefix): %d rows %ds-%ds, mid %.4g -> "
                      "%.4g (net %.4g), lo/hi %.4g/%.4g"
                      % (len(prow), secs[0], secs[-1], mids[0], mids[-1],
                         mids[-1] - mids[0], min(mids), max(mids)))
            cl = {}
            for r in prow:
                cl[r["cls"]] = cl.get(r["cls"], 0) + 1
            print("  classes so far: %s" % sorted(cl.items(), key=lambda x: -x[1]))
        cl = {}
        for r in rows:
            cl[r["cls"]] = cl.get(r["cls"], 0) + 1
        print("  THIS CELL (counts only — no later row's fields are read): %s"
              % sorted(cl.items(), key=lambda x: -x[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
