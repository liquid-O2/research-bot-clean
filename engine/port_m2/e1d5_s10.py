#!/usr/bin/python3
"""E1 STUDY DAY 5 — S10 DEVELOPING-VALUE-AREA EXTRACTOR (defect D17, in-lane).

D17 (E1_POSTMORTEMS §10, day 4): "S10's developing POC/VAH/VAL are not in the
triage index.  Two days, two correct magnitude calls, no way to triage on it.
`d_POC`, `d_VAH`, `d_VAL`, `in_VA` are four numbers."  The tooling lane owns the
permanent fix; this module is the reader's in-lane read of the SAME BLIND
SHEETS the index is built from, so day 5 can use the object at all.

STRICTLY BLIND: reads `*.BLIND.sheet.txt` only; the S14 appendix is never
opened (there is no code path to it).  The S10 `developing` row is stamped with
its own `as_of` (a 30-minute profile snapshot at or before the decision second),
so the numbers are causal by construction.

It also emits the BAR-VS-VALUE-AREA test the day-5 pre-mortem veto is written
on: for a LONG the $1,000 bar sits at entry + 1000/mult and the question is
whether that price is above the developing VAH; for a SHORT, entry - 1000/mult
against the developing VAL.  `bar_outside_va=1` means the profile prices the
move short of the bar before the trade is taken.
"""
import argparse
import csv
import os
import re
import sys

ROOT = "/workspace/artifacts/cache/port/m2/era/%s/%s/%s/%s/%s.BLIND.sheet.txt"
DEV = re.compile(r"^\s*developing\s+as_of=(\S+)\s+POC=([\d.]+)\s+VAH=([\d.]+)"
                 r"\s+VAL=([\d.]+)\s+d_POC=\$?(-?[\d.]+)\s+in_VA=(\d)")
BAR_USD = 1000.0


def sheet_path(cid, era="E1", block="STUDY"):
    asset, d8, _sec, _side = cid.split("-")[0], cid.split("-")[1], None, None
    return ROOT % (era, block, asset, d8, cid)


def s10(cid):
    p = sheet_path(cid)
    if not os.path.exists(p):
        return None
    with open(p) as fh:
        for ln in fh:
            m = DEV.match(ln)
            if m:
                return {"dev_as_of": m.group(1), "d_POC_px": float(m.group(2)),
                        "d_VAH": float(m.group(3)), "d_VAL": float(m.group(4)),
                        "d_POC_usd": float(m.group(5)), "in_VA": int(m.group(6))}
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    with open(a.index) as fh:
        rows = list(csv.DictReader([l for l in fh if not l.startswith("#")],
                                   delimiter="\t"))
    cols = ("cid asset side sec dev_as_of d_POC_px d_VAH d_VAL d_POC_usd "
            "in_VA bar_px va_edge_px bar_outside_va va_gap_usd").split()
    n_missing = 0
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter="\t",
                           extrasaction="ignore")
        w.writeheader()
        for r in rows:
            d = s10(r["cid"])
            if d is None:
                n_missing += 1
                continue
            mult = float(r["mult"])
            mid = float(r["mid"])
            side = 1 if r["side"] == "LONG" else -1
            bar = mid + side * BAR_USD / mult
            edge = d["d_VAH"] if side > 0 else d["d_VAL"]
            outside = int((bar > edge) if side > 0 else (bar < edge))
            gap = (bar - edge) * mult * side
            w.writerow({"cid": r["cid"], "asset": r["asset"], "side": r["side"],
                        "sec": r["sec"], "bar_px": round(bar, 5),
                        "va_edge_px": edge, "bar_outside_va": outside,
                        "va_gap_usd": round(gap, 1), **d})
    print("e1d5_s10: %d rows (%d sheets missing an S10 developing row) -> %s"
          % (len(rows) - n_missing, n_missing, a.out))


if __name__ == "__main__":
    sys.exit(main())
