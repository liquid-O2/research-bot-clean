#!/usr/bin/python3
"""PORT M2 — RESERVE CEILINGS N1 / N2 (DP-replay arithmetic, no fitting).

CEILINGS FIRST.  Neither of these gets a model until its oracle bound says there
is money there -- the OBJ-1 lesson, where a fitted arm appeared to beat the
champion by $525 and its own oracle showed the object was worth $132.

N1 FLEXIBLE SEAT ALLOCATION.  The rigid `3 x 1 x 1` grid was inherited, never
chosen.  Price the oracle of JOINT daily allocation: 0-5 seats per asset per
day, <=10 across the three books, uneven phases allowed -- against the rigid
grid's own oracle on the same days.

N2 ASYMMETRIC PHASE BUDGETS.  Same seat count, freely allocated ACROSS PHASES
within a session instead of one per phase.

HONEST BOUND STATEMENT: the k-limited per-session optimum is computed GREEDILY
(repeatedly take the highest-value candidate that does not overlap an already
taken one).  Greedy is a LOWER bound on the true k-position optimum, so every
N1/N2 number here UNDERSTATES its ceiling.  That direction is the safe one --
a ceiling that looks small under a lower bound is not yet refuted, and is
labelled so rather than being read as a null.

N3 (re-entry after wall) and N6 (stop-and-reverse) need a second leg rebuilt
from the WALL SECOND, which is a session-load pass rather than matrix
arithmetic; they are the next block and are NOT estimated here.
"""
import argparse
import os
import sys
import time

import numpy as np

_H = os.path.dirname(os.path.abspath(__file__))
for _p in (_H, "/workspace/engine/port_m2/seqtest", "/workspace/engine/port_m0",
           "/workspace/engine/port_m1", "/workspace/engine/port_m3",
           "/workspace/artifacts/cache/pylibs"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import newobj as N                        # noqa: E402
import champ_floor as CF                  # noqa: E402
import confidence as CO                   # noqa: E402
import m2_common as MC                    # noqa: E402

BINDING = ("E5", "E6", "E7")
ERAS = BINDING + ("E3", "E4")
MAXK = 5
DAYCAP = 10
FLOOR = 2000.0


def _greedy(dec, ex, val, kmax):
    """Marginal value of the 1st..kmax non-overlapping seats, greedily."""
    order = np.argsort(-val)
    taken = []
    out = []
    for i in order:
        if len(taken) >= kmax:
            break
        if val[i] <= 0:
            break
        if any(not (ex[i] <= dec[j] or dec[i] >= ex[j]) for j in taken):
            continue
        taken.append(i)
        out.append(float(val[i]))
    cum = np.cumsum(out) if out else np.zeros(0)
    return np.concatenate([[0.0], cum,
                           np.full(max(0, kmax - cum.size),
                                   cum[-1] if cum.size else 0.0)])[:kmax + 1]


def run(eras=ERAS):
    D, P = CF.boot()
    ceil = CO.ceilings()
    rows = []
    for era in eras:
        ev = N.deployable(D, N.era_rows(D, era))
        dec = D["dec_sec"][ev].astype(np.int64)
        ex = D["exit_close_sec"][ev].astype(np.int64)
        val = D["cert_close_usd"][ev].astype(np.float64)
        ok = D["cert_refused"][ev] == 0
        asset = D["asset_idx"][ev].astype(np.int64)
        d8 = D["d8"][ev].astype(np.int64)
        ph = D["phase_dec"][ev].astype(np.int64)
        days = {}
        for i in range(ev.size):
            if not ok[i]:
                continue
            days.setdefault(int(d8[i]), {}).setdefault(int(asset[i]),
                                                       []).append(i)
        rigid = flex = phase_free = 0.0
        n_sess = 0
        for day, per_a in days.items():
            curves = {}
            for a, idxs in per_a.items():
                idxs = np.asarray(idxs)
                curves[a] = _greedy(dec[idxs], ex[idxs], val[idxs], MAXK)
                # rigid: one seat per PHASE cell (the committed shape)
                r = 0.0
                for p in np.unique(ph[idxs]):
                    sel = idxs[ph[idxs] == p]
                    if sel.size:
                        r += max(0.0, float(val[sel].max()))
                rigid += r
                n_sess += 1
                # N2: same seat count, freely allocated across phases
                nph = int(np.unique(ph[idxs]).size)
                phase_free += float(curves[a][min(nph, MAXK)])
            # N1: joint allocation across the day's books, <= DAYCAP total
            al = list(curves)
            best = 0.0
            for combo in np.ndindex(*[MAXK + 1] * len(al)):
                if sum(combo) > DAYCAP:
                    continue
                best = max(best, sum(curves[al[j]][combo[j]]
                                     for j in range(len(al))))
            flex += best
        c = ceil.get("%s|ALL" % era)
        for name, tot in (("RIGID_3x1x1_oracle", rigid),
                          ("N2_asym_phase_oracle", phase_free),
                          ("N1_flexible_alloc_oracle", flex)):
            per = tot / max(n_sess, 1)
            rows.append([era, "BINDING" if era in BINDING else "context",
                         name, n_sess, N._r(per), N._r(c),
                         N._r(per / c, 4) if c else "",
                         N._r(0.80 * c) if c else "",
                         N._r(0.80 * c - per) if c else "",
                         N._r(per - rigid / max(n_sess, 1))])
        N.hb("reserve %s: rigid $%.2f | N2 $%.2f | N1 $%.2f (per session)"
             % (era, rigid / max(n_sess, 1), phase_free / max(n_sess, 1),
                flex / max(n_sess, 1)))
    N.write_tsv("RESERVE_CEILINGS_N1_N2.tsv",
                ["era", "criterion", "arm", "n_sessions", "usd_per_session",
                 "entry_foresight_ceiling", "capture_of_ceiling",
                 "aim_08ceiling", "gap_to_aim", "delta_vs_rigid"], rows,
                extra=["CEILINGS ONLY -- hindsight bounds, no model, no policy. "
                       "A ceiling delta that is immaterial kills its idea here "
                       "and cheaply.",
                       "N1 = joint daily allocation, 0-%d seats/asset/day, "
                       "<=%d across the three books, uneven phases allowed.  "
                       "N2 = the SAME seat count freely allocated across phases "
                       "within a session.  RIGID = the committed one-per-phase "
                       "shape, on the identical days." % (MAXK, DAYCAP),
                       "THE k-LIMITED OPTIMUM IS GREEDY, which is a LOWER bound "
                       "on the true k-position DP.  Every N1/N2 figure "
                       "therefore UNDERSTATES its ceiling; a small number here "
                       "is not yet a refutation and must not be read as one.",
                       "N3 (re-entry after wall) and N6 (stop-and-reverse) need "
                       "a second leg rebuilt from the WALL SECOND -- a "
                       "session-load pass, not matrix arithmetic -- and are the "
                       "next block.  They are NOT estimated here."])
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    if a.run:
        run()
    else:
        ap.print_help()
