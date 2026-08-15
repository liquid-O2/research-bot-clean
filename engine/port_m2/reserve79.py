#!/usr/bin/python3
"""PORT M2 — N7 / N9 CEILINGS.  Replay arithmetic on already-fitted members.

N7  DEFER-ON-DISAGREEMENT.  Agreement is this program's ONE working confidence
    mechanism (win 0.71 -> 0.91, $/trade 509 -> 956 at the agreeing end).  N7
    asks whether a little TIME can convert a disagreement into a decision:
    where the five folded members disagree about which member of a cell to
    seat, wait {60, 120} s and seat then instead.

    THE TOLL IS KNOWN AND IS THE BAR: the DELAY census measured ~1.5%/min of
    the winner's value lost to waiting, so the rule must beat that toll to be
    worth anything.  Two arms are priced and the pair is the whole point:
      N7_MECH   the MECHANICAL rule — on a disagreeing cell, always take the
                delayed entry.  Deployable as written; no foresight.
      N7_ORACLE the HINDSIGHT bound — on a disagreeing cell, take whichever of
                {0, 60, 120} actually paid most.  If even THIS is small, the
                idea is dead and no re-scoring model can rescue it.

N9  DYNAMIC SOFT BLENDING.  The router idea without the starvation: no data is
    split, every member still trains on everything, and the conditioning
    happens at BLEND time.  Ceiling first, so the fitted version is only built
    if the bound is there:
      N9_FIXED   the deployed single family (W_VOLMATCH), the incumbent.
      N9_EQUAL   the equal-weight score-mean blend of the three weighting
                 families {W_FLAT, W_VOLMATCH, W_ERABAL}.
      N9_ORACLE  the per-DAY hindsight pick of the best family — the ceiling of
                 ANY day-level router, however it is fitted.  A small
                 N9_ORACLE - N9_FIXED gap kills N9 outright.

Both are pure replay on committed score files: no fit, no search, no HP.
Nothing here can be overfitted because nothing here is fitted, and the two
ORACLE rows are labelled hindsight bounds on the face of the table.

CLI  reserve79.py --run
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

BINDING = ("E5", "E6", "E7")
ERAS = BINDING + ("E3", "E4")
SEEDS = (0, 1, 2, 3, 4)
N7_DELAYS = (60, 120)
FAMILIES = ("W_FLAT", "W_VOLMATCH", "W_ERABAL")


def hb(m):
    N.hb("[reserve79] %s" % m)


class R79Refusal(RuntimeError):
    """A guard fired.  Never downgraded, never silently filtered."""


def _sdir():
    import curriculum as CU
    return CU._sdir()


def _load(tag, era, seed):
    p = os.path.join(_sdir(), "%s_%s_%d.npy" % (tag, era, seed))
    if not os.path.exists(p):
        return None
    return np.load(p).astype(np.float64)


def disagreeing_cells(D, rows, scores):
    """Cells where the members do NOT agree on the top pick.  `scores` is the
    list of the five folded members' score columns."""
    ro, blocks = N.cell_blocks(D, rows)
    picks = []
    for sc in scores:
        s = np.asarray(sc)[ro]
        top = []
        for a, b in blocks:
            idx = np.arange(a, b)
            good = idx[np.isfinite(s[idx])]
            top.append(int(ro[good[np.argmax(s[good])]]) if good.size else -1)
        picks.append(top)
    P = np.asarray(picks)
    agree = (P == P[0]).all(axis=0)
    return ro, blocks, agree


def run(eras=ERAS):
    import champ_floor as CF
    import stacked_final as SF
    import confidence as CO
    D, P = CF.boot()
    ceil = CO.ceilings()
    V = {d: N.delayed_value(P, d, D) for d in (0,) + N7_DELAYS}
    rows = []
    for era in eras:
        crit = "BINDING" if era in BINDING else "context"
        ev = N.deployable(D, N.era_rows(D, era))
        n_ = N.committed_policy()[era][1]
        cl = ceil.get("%s|ALL" % era)
        fold = [_load("FOLD", era, s) for s in SEEDS]
        if any(x is None for x in fold):
            raise R79Refusal("missing FOLD members for %s" % era)
        ro, blocks, agree = disagreeing_cells(D, ev, fold)
        dis_frac = float(1.0 - agree.mean()) if agree.size else 0.0
        dis_rows = set()
        for (a, b), ag in zip(blocks, agree):
            if not ag:
                dis_rows.update(ro[a:b].tolist())

        def _arm(seatfn):
            out = []
            for s in SEEDS:
                seats = seatfn(fold[s])
                rp = N.replay_delayed(D, seats, P)
                out.append(N.read_rows(D, SF.apply_stop(
                    D, rp, "STOP_WALL1"))["usd_per_session"])
            a = np.asarray([x for x in out if x is not None], dtype=np.float64)
            return a

        def base_seats(sc):
            return N.top_per_cell_score(D, ev, sc, n_)

        def mech_seats(sc):
            return [(i, (N7_DELAYS[0] if i in dis_rows else 0))
                    for i, _d in N.top_per_cell_score(D, ev, sc, n_)]

        def oracle_seats(sc):
            out = []
            for i, _d in N.top_per_cell_score(D, ev, sc, n_):
                if i not in dis_rows:
                    out.append((i, 0))
                    continue
                best, bv = 0, -np.inf
                for d in (0,) + N7_DELAYS:
                    v = V[d][i]
                    if np.isfinite(v) and v > bv:
                        best, bv = d, v
                out.append((i, best))
            return out

        inc = _arm(base_seats)
        for name, fn, kind in (("N7_INCUMBENT_D0", base_seats, "deployable"),
                               ("N7_MECH_DEFER60", mech_seats, "deployable"),
                               ("N7_ORACLE_DEFER", oracle_seats, "HINDSIGHT")):
            a = _arm(fn)
            d = a.mean() - inc.mean()
            aim = 0.80 * cl if cl else None
            rows.append([era, crit, "N7", name, kind, int(a.size),
                         N._r(a.mean()), N._r(a.std()),
                         N._r(dis_frac, 4), N._r(cl),
                         N._r(a.mean() / cl, 4) if cl else "",
                         N._r(aim), N._r(a.mean() - aim) if aim else "",
                         N._r(d), N._r(d - a.std()),
                         "YES" if (d - a.std()) > 0 else "no"])

        # ------------------------------------------------------------- N9 --
        fam = {}
        for f in FAMILIES:
            m = [_load(f, era, s) for s in SEEDS]
            if any(x is None for x in m):
                continue
            fam[f] = m
        if len(fam) == len(FAMILIES):
            per = {}
            for f, m in fam.items():
                vals = []
                for s in SEEDS:
                    rp = N.replay_delayed(D, N.top_per_cell_score(
                        D, ev, m[s], n_), P)
                    vals.append(SF.apply_stop(D, rp, "STOP_WALL1"))
                per[f] = vals
            eq = []
            for s in SEEDS:
                ens = np.nanmean(np.vstack([fam[f][s] for f in FAMILIES]),
                                 axis=0)
                rp = N.replay_delayed(D, N.top_per_cell_score(D, ev, ens, n_),
                                      P)
                eq.append(SF.apply_stop(D, rp, "STOP_WALL1"))
            def _rd(lst):
                return np.asarray([N.read_rows(D, x)["usd_per_session"]
                                   for x in lst], dtype=np.float64)
            base = _rd(per["W_VOLMATCH"])
            arms = [("N9_FIXED_VOLMATCH", base, "deployable"),
                    ("N9_EQUAL_BLEND", _rd(eq), "deployable")]
            # the per-DAY hindsight pick: the bound on ANY day-level router
            orc = []
            for s in SEEDS:
                bysess = {}
                for f in FAMILIES:
                    for r in per[f][s]:
                        bysess.setdefault(r["session"], []).append(r)
                merged = [max(v, key=lambda r: r["realised"])
                          for v in bysess.values()]
                orc.append(N.read_rows(D, merged)["usd_per_session"])
            arms.append(("N9_ORACLE_DAY_ROUTER",
                         np.asarray(orc, dtype=np.float64), "HINDSIGHT"))
            for name, a, kind in arms:
                d = a.mean() - base.mean()
                aim = 0.80 * cl if cl else None
                rows.append([era, crit, "N9", name, kind, int(a.size),
                             N._r(a.mean()), N._r(a.std()), "", N._r(cl),
                             N._r(a.mean() / cl, 4) if cl else "",
                             N._r(aim), N._r(a.mean() - aim) if aim else "",
                             N._r(d), N._r(d - a.std()),
                             "YES" if (d - a.std()) > 0 else "no"])
        hb("%s done" % era)
    if not rows:
        raise R79Refusal("RESERVE_N7_N9 produced ZERO rows — a null prints "
                         "rows, so this is a FAILURE, not a result")
    N.write_tsv(
        "RESERVE_N7_N9.tsv",
        ["era", "criterion", "idea", "arm", "kind", "n_seeds",
         "usd_per_session", "sd_usd", "disagree_cell_frac",
         "entry_foresight_ceiling", "capture_of_ceiling", "aim_08ceiling",
         "gap_to_aim", "delta_vs_incumbent", "delta_minus_sd", "promotes"],
        rows,
        extra=[
            "N7 / N9 CEILINGS — pure replay on committed score files.  No fit, "
            "no search, no HP: nothing in this table can be overfitted because "
            "nothing in it is fitted.",
            "kind=HINDSIGHT rows are BOUNDS, not policies: N7_ORACLE_DEFER "
            "picks the delay that actually paid and N9_ORACLE_DAY_ROUTER picks "
            "the family that actually paid.  They exist so a small bound can "
            "kill an idea before anyone builds the fitted version — the OBJ-1 "
            "lesson.",
            "N7's bar is the measured delay toll (~1.5%/min of the winner's "
            "value, DELAY census); a mechanical deferral must beat it.",
            "N9_ORACLE_DAY_ROUTER is the ceiling of ANY day-level router over "
            "the three weighting families, however that router is fitted."])
    hb("RESERVE_N7_N9.tsv: %d rows" % len(rows))
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    if a.run:
        run()
    else:
        ap.print_help()
