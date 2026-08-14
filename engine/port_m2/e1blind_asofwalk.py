#!/usr/bin/python3
"""E1 BLIND — THE AS-OF WALK (D18b; mandatory since CC-M2-16.4).

Walks the driver's chronological prefixes in order and computes each row's call
AT THE CUT WHERE THE ROW FIRST BECOMES VISIBLE, then proves:
  (1) PREFIX-IDENTITY — that call equals the day-complete call, for every row
      (the reader policy is a pure function of one row, so this must hold; the
      walk PROVES it rather than asserting it);
  (2) SEAT-CHAIN IDENTITY — the chronological walk reaches the same seat
      spender per (asset, phase) cell as the day-complete pass.
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e1blind_policy as P                                       # noqa: E402


def read_tsv(path):
    with open(path) as fh:
        return list(csv.DictReader([l for l in fh if not l.startswith("#")],
                                   delimiter="\t"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drive", required=True)
    ap.add_argument("--full", required=True)
    ap.add_argument("--day", type=int, required=True)
    a = ap.parse_args()

    seen = {}
    files = sorted(f for f in os.listdir(a.drive) if f.startswith("ASOF_"))
    for fn in files:
        rows = read_tsv(os.path.join(a.drive, fn))
        for c in P.call_day(rows, a.day):
            seen.setdefault(c["cid"], c["call"])
    full = read_tsv(a.full)
    calls = P.call_day(full, a.day)
    day = {c["cid"]: c["call"] for c in calls}
    mism = [c for c in day if c in seen and seen[c] != day[c]]
    missing = [c for c in day if c not in seen]
    print("as-of walk: %d prefixes, %d cids revealed, %d day-complete rows"
          % (len(files), len(seen), len(day)))
    print("PREFIX-IDENTITY: %d mismatches, %d never revealed"
          % (len(mism), len(missing)))
    chain = P.seats(calls)
    wchain = {}
    for fn in files:
        for c in P.call_day(read_tsv(os.path.join(a.drive, fn)), a.day):
            if c["call"] == "TAKE":
                wchain.setdefault((c["asset"], c["phase_dec"]), c["cid"])
    print("SEAT-CHAIN IDENTITY: %s (%d cells)"
          % ("OK" if wchain == chain else "MISMATCH %s vs %s" % (wchain, chain),
             len(chain)))
    return 1 if (mism or missing or wchain != chain) else 0


if __name__ == "__main__":
    sys.exit(main())
