#!/usr/bin/python3
"""E1 STUDY DAY 5 — THE PRE-MORTEM VETO (CC-M2-13.4(b)), made executable.

The declared protocol (`e1d5_policy.py` (b)): a pre-mortem is written for every
SEAT-SPENDING TAKE before the call is finalised; if it names a mechanism that is
MEASURABLE ON THE SHEET and ALREADY PRESENT at the decision second, the TAKE
becomes a SKIP and the seat passes to the next surviving TAKE of that cell,
which gets its own deep read and its own pre-mortem.  Each veto's named
mechanism is written down here AS A TRIGGER so that (i) every one of the day's
112 policy TAKEs can be graded by it rather than only the four that were deep
read, and (ii) the delta of obeying the pre-mortems is measurable on the pooled
take set and not just on the replay.

THE THREE TRIGGERS, each minted by a deep read, each named in the pre-mortem of
the candidate that minted it, and each applied unchanged to every later TAKE:

 V1  BAR OUTSIDE THE DEVELOPING VALUE AREA (minted on HG-20210707-048882-L,
     13:34:42, and on SI-20210707-050720-L, 14:05:20).
     S10 developing VAH/VAL vs the price the $1,000 bar requires: for a LONG,
     entry + 1000/mult > VAH_dev; for a SHORT, entry - 1000/mult < VAL_dev.
     "The profile prices this move short of the bar before the trade is taken."
     Provenance: S10's developing POC/VAH is the only magnitude object of the
     round with an unbroken record — 2-for-2 on the two days it was read
     (E1_POSTMORTEMS §E1D3-11, §E1D4-F6), and both times it was written into
     the against/pre-mortem field and then ignored.  Defect D17 (it is still
     not in the triage index) is why day 5 had to extract it in-lane
     (`e1d5_s10.py`).

 V2  PHASE INVENTORY OVERHANG AGAINST THE TRADE, WITH THE ADVERSE STREAM STILL
     RUNNING (minted on HG-20210707-058061-L, 16:07:41, and confirmed on
     SI-20210707-058372-L, 16:12:52).
     S8 FUEL MAP trapped-against volume >= 90% of the phase total AND either
     (a) S8 5m sflow opposed at >= 10% of its own 5m volume, or (b) S8
     through_book_600s with n >= 10 and the adverse side >= 2x the trade side.
     "Every position taken in this phase is underwater on my side and the side
     that put them there is still transacting."  This is the mechanism the
     day-4 SI pre-mortem named verbatim ("7,805 of 7,902 contracts trapped
     ABOVE the mid: every buyer of this phase is underwater and each of them is
     a seller into any bounce") and that pre-mortem fired.
     ON RECORD AGAINST IT: P009 FUEL_POLARITY is DEAD in the ledger — fuel-map
     polarity as a DIRECTION source was killed in the warm-up.  V2 is not that
     claim: it is a SUPPLY claim conditioned on the adverse stream still being
     active, and it is logged here so the census can separate the two.

 V3  TWO-STREAM OPPOSITION AT THE DECISION SECOND = P018 (minted on
     SI-20210707-059369-L, 16:29:29).
     S8 60s |sflow| >= 10% of 60s volume with vol >= 20 AND S5 mid_slope_$/min
     (T-1m) opposed to the trade.  P018 is ACTIVE and 5-0 in the ledger,
     validated on day-1 history before it was ever used.
     "One stream opposing is absorption; two streams agreeing against the trade
     is the market telling you the impulse is still running."

A TAKE that carries NO trigger stands, and any measurable-but-not-yet-present
mechanism its pre-mortem names is logged as a FLIP THRESHOLD instead of a veto
(the protocol's conditional branch).
"""
import argparse
import csv
import os
import sys


def F(r, k):
    try:
        return float(r[k])
    except Exception:
        return None


def load(index, s10, policy):
    idx = {r["cid"]: r for r in csv.DictReader(
        [l for l in open(index) if not l.startswith("#")], delimiter="\t")}
    prof = {r["cid"]: r for r in csv.DictReader(open(s10), delimiter="\t")}
    pol = list(csv.DictReader(open(policy), delimiter="\t"))
    return idx, prof, pol


def v1(cid, idx, prof):
    d = prof.get(cid)
    return bool(d is not None and d["bar_outside_va"] == "1")


def v2(cid, idx, prof):
    r = idx[cid]
    side = 1 if r["side"] == "LONG" else -1
    ta, tb, pt = F(r, "trapped_above"), F(r, "trapped_below"), F(r, "phase_total")
    if ta is None or tb is None or not pt:
        return False
    frac = (ta / pt) if side > 0 else (tb / pt)
    if frac < 0.90:
        return False
    s5, v5 = F(r, "f5m_sflow"), F(r, "f5m_vol")
    flow = bool(s5 is not None and v5 and abs(s5) / v5 >= 0.10
                and ((s5 < 0) == (side > 0)))
    tn, tbid, task = F(r, "thru_n"), F(r, "thru_bid"), F(r, "thru_ask")
    book = bool(tn is not None and tn >= 10 and tbid is not None
                and task is not None
                and ((tbid >= 2 * task) if side > 0 else (task >= 2 * tbid)))
    return flow or book


def v3(cid, idx, prof):
    r = idx[cid]
    side = 1 if r["side"] == "LONG" else -1
    s60, v60 = F(r, "f60_sflow"), F(r, "f60_vol")
    sl = F(r, "slope1m")
    if s60 is None or not v60 or v60 < 20 or sl is None:
        return False
    return bool(abs(s60) / v60 >= 0.10 and ((s60 < 0) == (side > 0))
                and ((sl < 0) == (side > 0)))


TRIGGERS = (("V1", v1), ("V2", v2), ("V3", v3))


def vetoes(cid, idx, prof):
    return [n for n, f in TRIGGERS if f(cid, idx, prof)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--s10", required=True)
    ap.add_argument("--policy", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    idx, prof, pol = load(a.index, a.s10, a.policy)
    rows = []
    for p in pol:
        vs = vetoes(p["cid"], idx, prof) if p["call"] == "TAKE" else []
        rows.append({"cid": p["cid"], "policy_call": p["call"],
                     "veto": ";".join(vs),
                     "final_call": "SKIP" if vs else p["call"]})
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["cid", "policy_call", "veto",
                                           "final_call"], delimiter="\t")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    nt = sum(1 for r in rows if r["policy_call"] == "TAKE")
    nv = sum(1 for r in rows if r["veto"])
    print("e1d5_veto: %d policy TAKEs, %d vetoed, %d stand -> %s"
          % (nt, nv, nt - nv, a.out))
    from collections import Counter
    print("   by trigger:", Counter(r["veto"] for r in rows if r["veto"]))


if __name__ == "__main__":
    sys.exit(main())
