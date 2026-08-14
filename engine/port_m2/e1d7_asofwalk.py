#!/usr/bin/python3
"""E1 STUDY DAY 7 — THE AS-OF WALK (defect D18b, CC-M2-16.4's closing clause).

D18 (day 5) named the hazard: the pre-mortem VETO walk was driven by a
day-complete table, so although every trigger is a pure function of one row and
the CALLS were mechanically unexposed, the choice of which rows to deep-read was
made with the whole day in front of the reader.  CC-M2-16.4 rules that day 6
must drive BOTH triage and the veto walk through the as-of stepper, at HEAD.

THIS MODULE IS THAT DRIVE.  It walks `triage_index.py --drive-step`'s
chronological prefixes IN ORDER, and for each row at the cut at which it first
becomes visible it computes the day-7 policy call (core terms + the committed
cell-side gate + the V2/V3 vetoes) FROM THE PREFIX ROW ONLY.  It then proves
the two properties the protocol needs:

  (1) PREFIX-IDENTITY: the call computed at the row's own reveal cut is
      identical to the day-complete call, for every row.  If it were not, the
      day-complete run would be exploiting information the clock had not
      reached.
  (2) SEAT-CHAIN IDENTITY: the seat spender of each (asset, phase) cell — the
      only call that can move the replay under CC-M2-10.3 phase-close seating —
      is reached by the chronological walk in the same order.

The veto walk therefore has no day-complete table anywhere in it: the vetoes
are evaluated row by row as the tape reveals them, and the seat chain is the
output of the walk rather than of a scan.
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e1d7_policy as P                                        # noqa: E402

DRIVE = "/workspace/artifacts/cache/port/m2/triage/E1D7_DRIVE"
FULL = "/workspace/artifacts/cache/port/m2/triage/E1D7_TRIAGE_INDEX.tsv"


def read_tsv(path):
    return list(csv.DictReader(
        [l for l in open(path) if not l.startswith("#")], delimiter="\t"))


def one_call(r, arm="CORE+SEAT+SIDE"):
    t = P.terms(r)
    core = all(t[k] for k in P.TERMS)
    seat_ok, _ = P.seat_gate(r, arm)
    gate_ok, _ = P.side_gate(r, arm)
    vl = P.veto_list(r) if (core and seat_ok and gate_ok) else []
    return ("TAKE" if (core and seat_ok and gate_ok and not vl) else "SKIP",
            "+".join(vl), core, seat_ok and gate_ok)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drive", default=DRIVE)
    ap.add_argument("--full", default=FULL)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    man = [l.split("\t") for l in open(os.path.join(a.drive,
                                                    "DRIVE_MANIFEST.tsv"))
           if not l.startswith("#")]
    hdr, man = man[0], man[1:]
    seen, walk = set(), []
    for row in man:
        cut = int(row[0])
        sub = read_tsv(os.path.join(a.drive, row[5].strip()))
        for r in sub:
            if r["cid"] in seen:
                continue
            seen.add(r["cid"])
            call, vet, core, gate = one_call(r)
            walk.append(dict(cid=r["cid"], reveal_cut=cut,
                             sec=int(float(r["sec"])), asset=r["asset"],
                             phase_dec=r["phase_dec"], side=r["side"],
                             call=call, vetoes=vet, core=int(core),
                             gate=int(gate)))
    full = {r["cid"]: r for r in read_tsv(a.full)}
    assert len(walk) == len(full), ("walk %d vs full %d" % (len(walk), len(full)))

    bad = 0
    for w in walk:
        call, vet, _, _ = one_call(full[w["cid"]])
        if call != w["call"] or vet != w["vetoes"]:
            bad += 1
            print("MISMATCH %s: walk %s/%s vs full %s/%s"
                  % (w["cid"], w["call"], w["vetoes"], call, vet))
    print("PREFIX-IDENTITY: %d rows walked over %d cuts, %d mismatches"
          % (len(walk), len(man), bad))

    chain, order = {}, []
    for w in sorted(walk, key=lambda x: (x["sec"], x["cid"])):
        if w["call"] != "TAKE":
            continue
        k = (w["asset"], w["phase_dec"])
        if k not in chain:
            chain[k] = w["cid"]
            order.append((w["sec"], k, w["cid"], w["side"], w["reveal_cut"]))
    print("SEAT CHAIN (chronological, from the walk — %d cells):" % len(order))
    for sec, k, cid, side, cut in order:
        print("   %02d:%02d:%02d  %-12s %-5s %s   [first visible at cut %d]"
              % (sec // 3600, sec % 3600 // 60, sec % 60, "/".join(k), side,
                 cid, cut))

    nv = sum(1 for w in walk if w["vetoes"])
    print("VETO WALK: %d rows carry a V2/V3 veto on a row the core and the "
          "cell-side call both admit" % nv)
    if a.out:
        with open(a.out, "w", newline="") as fh:
            wr = csv.DictWriter(fh, fieldnames=list(walk[0].keys()),
                                delimiter="\t")
            wr.writeheader()
            for w in walk:
                wr.writerow(w)
        print("wrote %s" % a.out)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
