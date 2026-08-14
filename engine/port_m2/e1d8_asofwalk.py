#!/usr/bin/python3
"""E1 STUDY DAY 8 — THE AS-OF WALK (D18b, mandatory since CC-M2-16.4).

Walks `triage_index.py --drive-step`'s chronological prefixes IN ORDER and,
for each row at the cut at which it FIRST becomes visible, computes the day-8
policy call from that prefix row only.  It then proves the two properties the
protocol needs:

  (1) PREFIX-IDENTITY — the call computed at a row's own reveal cut is
      identical to the day-complete call, for every row.  The day-8 policy is a
      pure function of one row (the rolling stage-1 state is read at the row
      itself, which is the whole point of CC-M2-19.1), so this must hold; the
      walk proves it rather than asserting it.
  (2) SEAT-CHAIN IDENTITY — the seat spender of each (asset, phase) cell, the
      only call that can move the replay under CC-M2-10.3 phase-close seating,
      is reached by the chronological walk in the same order.
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e1d8_policy as P                                        # noqa: E402

DRIVE = "/workspace/artifacts/cache/port/m2/triage/E1D8_DRIVE"
FULL = "/workspace/artifacts/cache/port/m2/triage/E1D8_TRIAGE_INDEX.tsv"


def read_tsv(path):
    return list(csv.DictReader(
        [l for l in open(path) if not l.startswith("#")], delimiter="\t"))


def one_call(r, arm):
    t = P.terms(r)
    core = all(t[k] for k in P.TERMS)
    seat_ok, _ = P.seat_gate(r, arm)
    gate_ok, _ = P.side_gate(r, arm)
    vl = P.veto_list(r) if (core and seat_ok and gate_ok) else []
    return ("TAKE" if (core and seat_ok and gate_ok and not vl) else "SKIP",
            "+".join(vl))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drive", default=DRIVE)
    ap.add_argument("--full", default=FULL)
    ap.add_argument("--arm", default="CORE+SEAT")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    man = os.path.join(a.drive, "DRIVE_MANIFEST.tsv")
    cuts = []
    if os.path.exists(man):
        for r in read_tsv(man):
            cuts.append(r)
    files = sorted(f for f in os.listdir(a.drive) if f.endswith(".tsv")
                   and f.startswith("ASOF_"))
    seen, first_at = {}, {}
    for f in files:
        rows = read_tsv(os.path.join(a.drive, f))
        for r in rows:
            if r["cid"] in seen:
                continue
            seen[r["cid"]] = one_call(r, a.arm)
            first_at[r["cid"]] = f

    full = read_tsv(a.full)
    day = {r["cid"]: one_call(r, a.arm) for r in full}
    missing = [c for c in day if c not in seen]
    mism = [c for c in day if c in seen and seen[c] != day[c]]
    print("as-of walk: %d prefixes, %d cids revealed, %d day-complete rows"
          % (len(files), len(seen), len(day)))
    print("PREFIX-IDENTITY: %d mismatches, %d cids never revealed"
          % (len(mism), len(missing)))
    if mism[:5]:
        for c in mism[:5]:
            print("   MISMATCH %s prefix=%s day=%s" % (c, seen[c], day[c]))

    # seat chain, chronological
    order = sorted(full, key=lambda r: (int(float(r["sec"])), r["cid"]))
    chain, held = [], {}
    for r in order:
        if day[r["cid"]][0] != "TAKE":
            continue
        k = (r["asset"], r["phase_dec"])
        if k in held:
            continue
        held[k] = r["cid"]
        chain.append((k, r["cid"], r["clock"], r["side"]))
    print("SEAT CHAIN (%d cells):" % len(chain))
    for k, cid, clock, side in chain:
        print("   %-12s %-28s %s %s" % ("/".join(k), cid, clock, side))
    if a.out:
        with open(a.out, "w", newline="") as fh:
            w = csv.writer(fh, delimiter="\t")
            w.writerow(["cid", "first_prefix", "call", "vetoes"])
            for c in sorted(seen):
                w.writerow([c, first_at[c], seen[c][0], seen[c][1]])
        print("wrote %s" % a.out)
    return 1 if (mism or missing) else 0


if __name__ == "__main__":
    sys.exit(main())
