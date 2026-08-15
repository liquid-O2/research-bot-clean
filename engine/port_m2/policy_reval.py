#!/usr/bin/python3
"""PORT M2 — SEAT-POLICY REVALIDATION UNDER THE 5-SEED LAW (internal wrong).

THE WRONG BEING FIXED: the per-era (unit, N) seat policy was chosen by
`m3_walk.select_policy` on a SINGLE FIT, many arms ago, and has been inherited
unquestioned ever since -- including through every table in this campaign.  It
predates the law this round established: with a per-era seed sd of $150-378, a
single-fit choice between policies is a coin toss dressed as a selection.

Re-asked under current discipline: every policy replayed on the SAME five
constrained member scores, so it is a 5-seed distribution against a 5-seed
distribution.  REPLAY ONLY -- nothing refitted, so the answer costs arithmetic.
"""
import argparse
import os
import sys

import numpy as np

_H = os.path.dirname(os.path.abspath(__file__))
for _p in (_H, "/workspace/engine/port_m2/seqtest", "/workspace/engine/port_m0",
           "/workspace/engine/port_m1", "/workspace/engine/port_m3",
           "/workspace/artifacts/cache/pylibs"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import newobj as N                        # noqa: E402
import champ_floor as CF                  # noqa: E402
import curriculum as CU                   # noqa: E402
import confidence as CO                   # noqa: E402
import stacked_final as SF                # noqa: E402
import m3_walk as W                       # noqa: E402

BINDING = ("E5", "E6", "E7")
ERAS = BINDING + ("E3", "E4")
POLICIES = (("cell", 1), ("cell", 2), ("cell", 3), ("session", 1),
            ("session", 2), ("session", 3))


def run():
    D, P = CF.boot()
    ceil = CO.ceilings()
    rows = []
    for era in ERAS:
        ev = N.deployable(D, N.era_rows(D, era))
        cur = N.committed_policy()[era]
        S = []
        for s in range(5):
            f = os.path.join(CU._sdir(), "CONTOP50_%s_%d.npy" % (era, s))
            if os.path.exists(f):
                S.append(np.load(f).astype(np.float64))
        if not S:
            continue
        for (u, n_) in POLICIES:
            vals, armed = [], []
            for sc in S:
                tk = W.topn_takes(D, sc, ev, n_, deployable=True, unit=u)
                rep = N.replay_delayed(D, [(int(i), 0) for i in tk.tolist()], P)
                vals.append(N.read_rows(D, rep)["usd_per_session"])
                armed.append(N.read_rows(
                    D, SF.apply_stop(D, rep, "STOP_WALL1"))["usd_per_session"])
            a = np.asarray([x for x in vals if x is not None])
            ar = np.asarray([x for x in armed if x is not None])
            cl = ceil.get("%s|ALL" % era)
            rows.append([era, "BINDING" if era in BINDING else "context",
                         "%s/%d" % (u, n_),
                         "CURRENT" if (u, n_) == cur else "",
                         int(a.size), N._r(a.mean()), N._r(a.std()),
                         N._r(ar.mean()), N._r(ar.std()),
                         N._r(ar.mean() / cl, 4) if cl else ""])
        N.hb("policy reval %s done (current %s/%d)" % (era, cur[0], cur[1]))
    N.write_tsv("POLICY_REVALIDATION.tsv",
                ["era", "criterion", "policy", "is_current", "n_seeds",
                 "raw_mean", "raw_sd", "armed_mean", "armed_sd",
                 "armed_capture"], rows,
                extra=["THE SEAT POLICY RE-ASKED UNDER THE 5-SEED LAW.  It was "
                       "chosen on a SINGLE FIT by m3_walk.select_policy and "
                       "inherited unquestioned; a single-fit choice against a "
                       "$150-378 seed sd is a coin toss dressed as a selection.",
                       "REPLAY ONLY on the five constrained member scores.",
                       "armed_* is the PRIMARY reading (the first-wall stop is "
                       "adopted); raw is reference.",
                       "PROMOTION: a policy displaces the current one only if "
                       "its 5-seed armed mean clears the current policy's by "
                       "more than its own sd, on the BINDING eras."])
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    if a.run:
        run()
    else:
        ap.print_help()
