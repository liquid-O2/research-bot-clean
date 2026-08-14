#!/usr/bin/python3
"""E1 BLIND — THE AS-OF WALK (D18b; mandatory since CC-M2-16.4).

Walks the driver's chronological prefixes in order and computes each row's call
AT THE CUT WHERE THE ROW FIRST BECOMES VISIBLE, then proves:
  (1) PREFIX-IDENTITY — that call equals the day-complete call, for every row
      (the reader policy is a pure function of one row, so this must hold; the
      walk PROVES it rather than asserting it);
  (1b) VETO IDENTITY — the same for the row's VETO SET.  D18b/CC-M2-16.4 is
      SPECIFICALLY about the veto walk, and this walker — the one that runs on
      the round the teacher gate scores — was the only one of the three that
      dropped the veto from the comparison (R30).  It compared
      `seen.setdefault(cid, c["call"])` alone while `e1d6_asofwalk:84-88` and
      `e1d7_asofwalk:85-89` compared `call != w["call"] or vet != w["vetoes"]`.
      A veto that fires at one cut and not at another is a leak even when the
      TAKE/SKIP happens to agree — V2's inputs (the S8 fuel map and the
      through-book) are exactly the fields a coarser prefix can move.
  (2) SEAT-CHAIN IDENTITY — the chronological walk reaches the same seat
      spender per (asset, phase) cell as the day-complete pass.
  (2b) V2-REFUSAL IDENTITY — the declared pass-on-refused selector (R21) must
      also be stable across cuts, or the refusal ACCOUNTING is prefix-
      dependent even where the call is not.
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


def sig(c):
    """R30: the walked SIGNATURE of a call.

    D18b/CC-M2-16.4 is specifically about the VETO walk, and this walker — the
    one that runs on the round the teacher gate scores — was the only one of
    the three that compared the CALL alone (`seen.setdefault(cid, c["call"])`)
    while `e1d6_asofwalk:84-88` and `e1d7_asofwalk:85-89` compared
    `call != w["call"] or vet != w["vetoes"]`.  A veto that fires at one cut
    and not at another is a leak even where the TAKE/SKIP agrees.
    """
    return (c["call"], c["vetoes"], c.get("v2_state", "-"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drive", required=True)
    ap.add_argument("--full", required=True)
    ap.add_argument("--day", type=int, required=True)
    a = ap.parse_args()

    _sig = sig
    seen, cut_of = {}, {}
    files = sorted(f for f in os.listdir(a.drive) if f.startswith("ASOF_"))
    for fn in files:
        rows = read_tsv(os.path.join(a.drive, fn))
        for c in P.call_day(rows, a.day):
            if c["cid"] not in seen:
                seen[c["cid"]] = _sig(c)
                cut_of[c["cid"]] = fn
    full = read_tsv(a.full)
    calls = P.call_day(full, a.day)
    day = {c["cid"]: _sig(c) for c in calls}
    mism = [c for c in day if c in seen and seen[c] != day[c]]
    missing = [c for c in day if c not in seen]
    n_call = sum(1 for c in mism if seen[c][0] != day[c][0])
    n_veto = sum(1 for c in mism if seen[c][1] != day[c][1])
    n_ref = sum(1 for c in mism if seen[c][2] != day[c][2])
    print("as-of walk: %d prefixes, %d cids revealed, %d day-complete rows"
          % (len(files), len(seen), len(day)))
    print("PREFIX-IDENTITY: %d mismatches (call %d, VETO SET %d, V2-refusal "
          "state %d), %d never revealed"
          % (len(mism), n_call, n_veto, n_ref, len(missing)))
    for c in sorted(mism)[:10]:
        print("   MISMATCH %s: at %s %s vs day-complete %s"
              % (c, cut_of[c], seen[c], day[c]))
    print("VETO WALK: %d rows carry a veto in the day-complete pass, %d at the "
          "cut where they first became visible"
          % (sum(1 for c in day.values() if c[1]),
             sum(1 for c in seen.values() if c[1])))
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
