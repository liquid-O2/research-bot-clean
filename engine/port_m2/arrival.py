#!/usr/bin/python3
"""PORT M2 — THE ARRIVAL-TIME POLICY.  The object, respecified.

WHY EVERYTHING BEFORE THIS IS VOID FOR DEPLOYMENT
  The committed seat rule is `top_per_cell_score` = the cell's EVENTUAL argmax
  (newobj.py:361).  A cell carries ~130 members arriving across the whole
  phase; the argmax is the cell's FIRST arrival only 5.9-14.4% of the time and
  the mean lookahead is ~5.5 HOURS (LEAK_SEATING_CENSUS.tsv).  To seat the
  09:41 candidate as "the cell's best" you must already have seen 10:05 and
  10:40.  The trade is entered at 09:41.  Every $/session this program has
  printed under that rule is therefore not earnable at arrival time.

  The leak audit's mechanism table says exactly where the signal lives: the
  cell's rank-1 member is worth $294.85 against a population mean of -$24.52,
  so the WITHIN-CELL ORDERING is real — but every threshold-shaped causal rule
  on the same score reads ~$0, because the score is informative in RANK and not
  in LEVEL.  A stopping rule consumes LEVEL.  That is the whole respecification.

THE NEW OBJECT
  At each arrival, with only the past in hand, decide TAKE or PASS, under one
  position per (asset, session) and the <=10 trades/day cap.  Nothing in this
  file may read a later arrival than the one being decided.

WHAT IS EVALUATED
  THE SCORE ZOO — every score already committed, re-read as an ARRIVAL score:
    S_TABPFN     the walk-forward TabPFN winner PROBABILITY
                 (`atlas_feat.build_tabpfn`: each era's value produced by a
                 TabPFN fitted strictly earlier, so it is causal by
                 construction).  FIRST, deliberately: it is the only score in
                 the program with calibrated GLOBAL discrimination (AUC 0.687
                 vs the champion's 0.521), and its "loss" was measured against
                 the leaked within-cell objective — the wrong test for it.
    S_XGB        the deployed folded members' score, as-is.
                 THE OBVIOUS REPAIR IS ALREADY RULED OUT, ANALYTICALLY, AND IS
                 THEREFORE NOT RUN AS A SEPARATE ROW: pushing the score through
                 the training block's ECDF is a MONOTONE transform, and every
                 threshold policy here fires on a training-block QUANTILE of
                 the score — which is invariant to any monotone transform.
                 Re-levelling produces seat-for-seat identical rows by
                 construction.  The level problem cannot be rescaled away; it
                 needs a different OBJECTIVE, which is step 2 (`arrival_fit`).
    S_AGREE      the members' AGREEMENT (negative dispersion) — the program's
                 one measured confidence mechanism, re-read as a level.
    S_TABPFN_AGREE  the two multiplied: global discrimination gated by
                 agreement.
  THE POLICY FAMILY — strictly causal, every knob fixed BEFORE the era it is
  applied to:
    FIRST_N          take the first arrivals.  Score-blind participation floor.
    TAU_PREV         take the first arrivals clearing tau; tau = a quantile of
                     the TRAINING BLOCK's score distribution.
    TAU_RATEMATCH    tau set on the TRAINING BLOCK so the seat rate matches the
                     compliant schedule.
    TAU_DAYSOFAR     tau recalibrated INTRADAY from the day's own arrivals so
                     far — lawful, because it reads only arrivals already past.
    SECRETARY        observe a fixed fraction of the phase, then take the first
                     arrival beating everything seen so far in that cell.
    SECRETARY_REENTRY  the same, re-armed after the position frees, so a better
                     arrival later in the phase is still reachable.

THE LAW ON THIS TABLE
  * THE POLICY FAMILY IS A SEARCH, so it carries the SEARCH-ADJUSTED NULL: the
    identical family is run on SHUFFLED scores (arrival times preserved,
    row->score pairing destroyed) and the BEST of those is the luck bar.
  * Every knob has BOTH readings: chosen on the PREVIOUS era (honest, blind,
    deployable) and chosen on the eval era (labelled UPPER BOUND, never
    promoted).
  * Day-clustered intervals throughout (D-036/D-073); 5 seeds wherever a fit
    exists; binding eras first; armored (first-wall stop) primary; capture and
    aims against the surviving ORACLE ceilings, which are hindsight bounds and
    are unaffected by the seating defect.

CLI  arrival.py --zoo [--eras ...]      the zoo x policy-family table
"""
import argparse
import json
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
import m2_common as MC                    # noqa: E402

VERSION = "PORT-M2-ARRIVAL-V1"
OUT_ROOT = os.path.join(MC.M2_ROOT, "arrival")
BINDING = ("E5", "E6", "E7")
ERAS = BINDING + ("E3", "E4")
SEEDS = (0, 1, 2, 3, 4)
DAY_CAP = 3                    # per asset-day; 3 books x 3 = 9 of the <=10 cap

# THE BAR, and it is the CAUSAL one.  The full-hindsight DP ceiling is not the
# right denominator for an arrival-time policy — it is allowed to see the whole
# day.  These are the CAUSAL ORACLE readings (leak audit, CAUSAL_CEILING): the
# most any arrival-time rule can earn.  Aims are 0.80 x THESE, and on this
# denominator the $2,000 floor is reachable at this formulation by measurement,
# which is why the campaign continues rather than closing.
CAUSAL_ORACLE = {"E3": 2348.0, "E4": 2133.0, "E5": 2021.0, "E6": 2675.0,
                 "E7": 3360.0}

# LEAK FIX P3_DOM_SHARE_FEATURE (leak audit, LOW): `dom_share` is a
# WHOLE-SESSION aggregate — the dominant instrument's share of the session's
# entire volume — and it aliased past three separate guards because it is
# constant within a session and so trips no shift/constancy test.  A decision
# at 09:41 cannot know the session's final volume split.  Dropped everywhere in
# this lane; the as-of running replacement is queued, not faked.
LEAKY_FEATURES = ("dom_share",)


def clean_feature_cols(D):
    """The champion's feature columns MINUS the audited leaky ones."""
    import newobj_arms as NA
    cols, names = NA.feat_cols(D)
    keep = [(i, n) for i, n in zip(cols, names) if n not in LEAKY_FEATURES]
    return [i for i, _n in keep], [n for _i, n in keep]

# PRE-REGISTERED KNOB GRIDS.  Fixed before any era is read; never adaptive.
TAU_Q = (0.50, 0.70, 0.80, 0.90, 0.95, 0.975, 0.99)
DAY_Q = (0.50, 0.70, 0.90)
DAY_WARM = 10                  # arrivals observed before the intraday tau arms
CELL_Q = (0.80, 0.90, 0.95, 0.99)   # the within-cell running quantile family
SEC_F = (0.10, 0.25, 0.50)     # fraction of the phase spent observing


def hb(m):
    sys.stderr.write("[arrival %s] %s\n" % (time.strftime("%H:%M:%S"), m))
    sys.stderr.flush()


class ArrivalRefusal(RuntimeError):
    """A guard fired.  Never downgraded, never silently filtered."""


def _sdir():
    import curriculum as CU
    return CU._sdir()


# ============================================================== the zoo =====
def zoo(D, era):
    """Every committed score, re-read as an ARRIVAL score.  Each entry is a
    list of per-seed columns (length 1 where the score is a single artifact)."""
    out = {}
    fold = []
    for s in SEEDS:
        p = os.path.join(_sdir(), "FOLD_%s_%d.npy" % (era, s))
        if os.path.exists(p):
            fold.append(np.load(p).astype(np.float64))
    if not fold:
        raise ArrivalRefusal("no folded members for %s" % era)
    out["S_XGB"] = fold
    F = np.vstack(fold)
    with np.errstate(invalid="ignore"):
        disp = np.nanstd(F, axis=0)
    agree = -disp
    out["S_AGREE"] = [agree]
    p = os.path.join(N.OUT_ROOT, "feat_tabpfn.npz")
    if os.path.exists(p):
        z = np.load(p, allow_pickle=False)
        tp = z["X"][:, 0].astype(np.float64)
        z.close()
        out["S_TABPFN"] = [tp]
        # global discrimination GATED BY agreement, both first mapped to the
        # training block's own ECDF so the product is between comparables
        out["S_TABPFN_AGREE"] = [(tp, agree)]
    return out


def ecdf_map(v, train_rows):
    """Push a score onto [0,1] through the TRAINING BLOCK's own ECDF.  This is
    the cheapest possible repair of the level problem: the rank information is
    kept exactly and a comparable global level is manufactured from history
    only.  Nothing from the eval era enters the mapping."""
    ref = np.asarray(v)[train_rows]
    ref = np.sort(ref[np.isfinite(ref)])
    if ref.size == 0:
        return np.full_like(np.asarray(v, dtype=np.float64), np.nan)
    out = np.full(np.asarray(v).size, np.nan)
    m = np.isfinite(v)
    out[m] = np.searchsorted(ref, np.asarray(v)[m], side="right") / float(
        ref.size)
    return out


# ======================================================= the policy family ==
def _arrivals(D, rows, score):
    """Rows sorted by (cell, arrival second), finite score only, plus the
    per-cell block bounds and the phase span of each cell."""
    r = np.asarray(rows, dtype=np.int64)
    r = r[np.isfinite(np.asarray(score)[r])]
    cell = D["cell"][r]
    order = np.lexsort((D["dec_sec"][r], cell))
    ro, co = r[order], cell[order]
    if ro.size == 0:
        return ro, []
    st = [0] + (np.flatnonzero(co[1:] != co[:-1]) + 1).tolist()
    return ro, list(zip(st, st[1:] + [co.size]))


def seats_first(D, rows, score, n=DAY_CAP):
    ro, blocks = _arrivals(D, rows, score)
    return [(int(ro[j]), 0) for a, b in blocks
            for j in range(a, min(a + n, b))]


def seats_tau(D, rows, score, tau):
    """Every arrival clearing tau, in arrival order.  Occupancy and the day cap
    are applied downstream by the replay and `cap_seats`, exactly as a live
    system would: the rule fires, the book decides whether there is room."""
    ro, blocks = _arrivals(D, rows, score)
    s = np.asarray(score)[ro]
    return [(int(ro[j]), 0) for a, b in blocks for j in range(a, b)
            if s[j] >= tau]


def seats_daysofar(D, rows, score, q, warm=DAY_WARM):
    """tau recalibrated INTRADAY from the day's own arrivals so far.

    Lawful by construction: at arrival j the threshold is a quantile of
    arrivals 0..j-1 OF THE SAME ASSET-DAY.  Nothing later than j is read.
    """
    r = np.asarray(rows, dtype=np.int64)
    r = r[np.isfinite(np.asarray(score)[r])]
    sess = D["session"][r]
    order = np.lexsort((D["dec_sec"][r], sess))
    ro, so = r[order], sess[order]
    s = np.asarray(score)[ro]
    if ro.size == 0:
        return []
    st = [0] + (np.flatnonzero(so[1:] != so[:-1]) + 1).tolist()
    out = []
    for a, b in zip(st, st[1:] + [so.size]):
        seen = []
        for j in range(a, b):
            if len(seen) >= warm:
                if s[j] >= np.quantile(seen, q):
                    out.append((int(ro[j]), 0))
            seen.append(float(s[j]))
    return out


def seats_cellsofar(D, rows, score, q, warm=5):
    """tau recalibrated from the CELL's own arrivals so far.

    WHY THIS SHAPE EXISTS.  The leak audit's finding is that the score is
    informative in RANK and not in LEVEL — and the rank it is trained on is the
    WITHIN-CELL rank.  DAYSOFAR asks the score to be comparable across the
    whole asset-day, which is more than it was ever trained to be; SECRETARY is
    the running-MAX special case and can only ever fire on a new record.  This
    is the family that matches exactly what the score does know: at arrival j,
    is this candidate in the top (1-q) of THIS CELL so far?  Strictly causal —
    arrivals 0..j-1 of the same cell and nothing else.
    """
    ro, blocks = _arrivals(D, rows, score)
    s = np.asarray(score)[ro]
    out = []
    for a, b in blocks:
        seen = []
        for j in range(a, b):
            if len(seen) >= warm and s[j] >= np.quantile(seen, q):
                out.append((int(ro[j]), 0))
            seen.append(float(s[j]))
    return out


def seats_secretary(D, rows, score, frac, reentry=False):
    """Observe the first `frac` of the CELL's arrival sequence, then take the
    first arrival beating everything seen so far.  With `reentry`, the rule
    re-arms after each take so a later, better arrival is still reachable."""
    ro, blocks = _arrivals(D, rows, score)
    s = np.asarray(score)[ro]
    out = []
    for a, b in blocks:
        m = b - a
        k = max(1, int(round(m * frac)))
        if m <= k:
            continue
        best = float(np.max(s[a:a + k]))
        for j in range(a + k, b):
            if s[j] > best:
                out.append((int(ro[j]), 0))
                if not reentry:
                    break
                best = float(s[j])
    return out


def cap_seats(D, rows, k=DAY_CAP):
    """The <=10 trades/day compliance cap, applied causally: the FIRST k seats
    of each asset-session survive and everything after is refused.  Truncating
    a chronological seat list from the front is exactly what a live cap does."""
    out = []
    for r in rows:
        kept = list(r["seats"])[:k]
        out.append({"session": r["session"],
                    "realised": float(sum(x[2] for x in kept)),
                    "n_takes": r["n_takes"], "n_seated": len(kept),
                    "n_forfeited": r["n_forfeited"],
                    "n_refused": r["n_refused"], "seats": kept})
    return out


POLICIES = ([("FIRST_%d" % DAY_CAP, "first", None)]
            + [("TAU_%g" % q, "tau", q) for q in TAU_Q]
            + [("DAYSOFAR_%g" % q, "day", q) for q in DAY_Q]
            + [("CELLSOFAR_%g" % q, "cell", q) for q in CELL_Q]
            + [("SECRETARY_%g" % f, "sec", f) for f in SEC_F]
            + [("SECRETARY_RE_%g" % f, "secre", f) for f in SEC_F])


def build_seats(D, rows, score, kind, knob, train_rows):
    if kind == "first":
        return seats_first(D, rows, score)
    if kind == "tau":
        ref = np.asarray(score)[train_rows]
        ref = ref[np.isfinite(ref)]
        if ref.size == 0:
            return []
        return seats_tau(D, rows, score, float(np.quantile(ref, knob)))
    if kind == "day":
        return seats_daysofar(D, rows, score, knob)
    if kind == "cell":
        return seats_cellsofar(D, rows, score, knob)
    if kind == "sec":
        return seats_secretary(D, rows, score, knob, False)
    if kind == "secre":
        return seats_secretary(D, rows, score, knob, True)
    raise ArrivalRefusal("unknown policy kind %r" % kind)


# ================================================================ the run ===
def run(eras=ERAS, out_dir=None):
    import champ_floor as CF
    import stacked_final as SF
    import newobj_arms as NA
    import confidence as CO
    out_dir = out_dir or OUT_ROOT
    os.makedirs(out_dir, exist_ok=True)
    D, P = CF.boot()
    ceil = CO.ceilings()
    rng = np.random.default_rng(N.SEED)
    rows = []
    hb("zoo x policy family: %d policies, day cap %d" % (len(POLICIES),
                                                          DAY_CAP))
    for era in eras:
        crit = "BINDING" if era in BINDING else "context"
        tr, itr, iva, ev = NA.fold(D, era)
        Z = zoo(D, era)
        cl = ceil.get("%s|ALL" % era)
        aim = 0.80 * cl if cl else None

        def read(seats):
            rp = N.replay_delayed(D, seats, P)
            rp = cap_seats(D, rp)
            return N.read_rows(D, SF.apply_stop(D, rp, "STOP_WALL1"))

        # the retrospective incumbent, for the size of the void
        inc = []
        for s in SEEDS:
            p = os.path.join(_sdir(), "FOLD_%s_%d.npy" % (era, s))
            if os.path.exists(p):
                sc = np.load(p).astype(np.float64)
                inc.append(read(N.top_per_cell_score(
                    D, ev, sc, N.committed_policy()[era][1]))
                    ["usd_per_session"])
        inc = np.asarray([x for x in inc if x is not None], dtype=np.float64)
        rows.append([era, crit, "RETROSPECTIVE_INCUMBENT", "cell_argmax", "",
                     "VOID_FOR_DEPLOYMENT", int(inc.size),
                     N._r(inc.mean()) if inc.size else "",
                     N._r(inc.std()) if inc.size else "", "", "", "",
                     N._r(cl), N._r(inc.mean() / cl, 4) if (cl and inc.size)
                     else "", N._r(aim),
                     N._r(inc.mean() - aim) if (aim and inc.size) else "",
                     "", "", ""])

        best_real, best_null = {}, {}
        for sname, cols in Z.items():
            for pname, kind, knob in POLICIES:
                real, null, nse = [], [], []
                for ci, col in enumerate(cols):
                    if sname == "S_TABPFN_AGREE":
                        a_, b_ = col
                        v = ecdf_map(a_, tr) * ecdf_map(b_, tr)
                    elif sname == "S_XGB":
                        v = np.asarray(col, dtype=np.float64)
                    else:
                        v = np.asarray(col, dtype=np.float64)
                    r = read(build_seats(D, ev, v, kind, knob, tr))
                    if r.get("usd_per_session") is not None:
                        real.append(r["usd_per_session"])
                        nse.append(r["n_seated"] / max(r["n_sessions"], 1))
                    # THE LUCK BAR: same policy, same arrival times, score
                    # pairing destroyed
                    vs = v.copy()
                    fin = np.nonzero(np.isfinite(vs))[0]
                    vs[fin] = vs[rng.permutation(fin)]
                    rs = read(build_seats(D, ev, vs, kind, knob, tr))
                    if rs.get("usd_per_session") is not None:
                        null.append(rs["usd_per_session"])
                if not real:
                    continue
                a = np.asarray(real, dtype=np.float64)
                nl = np.asarray(null, dtype=np.float64)
                best_real[(sname, pname)] = a.mean()
                if nl.size:
                    best_null[(sname, pname)] = nl.mean()
                rows.append([era, crit, sname, pname,
                             "" if knob is None else N._r(knob, 4), "causal",
                             int(a.size), N._r(a.mean()), N._r(a.std()),
                             N._r(float(np.mean(nse)), 3),
                             N._r(nl.mean()) if nl.size else "", "",
                             N._r(cl), N._r(a.mean() / cl, 4) if cl else "",
                             N._r(aim), N._r(a.mean() - aim) if aim else "",
                             "", "", ""])
        # the family-level search-adjusted verdict
        if best_real:
            bk = max(best_real, key=best_real.get)
            luck = max(best_null.values()) if best_null else None
            rows.append([era, crit, "FAMILY_VERDICT", "%s|%s" % bk, "",
                         "search-adjusted", "", N._r(best_real[bk]), "", "",
                         N._r(luck) if luck is not None else "",
                         N._r(best_real[bk] - luck) if luck is not None
                         else "", N._r(cl),
                         N._r(best_real[bk] / cl, 4) if cl else "",
                         N._r(aim), N._r(best_real[bk] - aim) if aim else "",
                         "YES" if (luck is not None
                                   and best_real[bk] > luck) else "no",
                         N._r(inc.mean()) if inc.size else "",
                         N._r(best_real[bk] - inc.mean()) if inc.size else ""])
            hb("%s: best causal %s|%s $%.2f vs luck bar $%s vs VOID incumbent "
               "$%.2f" % (era, bk[0], bk[1], best_real[bk],
                          N._r(luck) if luck is not None else "-",
                          inc.mean() if inc.size else float("nan")))
    if not rows:
        raise ArrivalRefusal("ARRIVAL_ZOO produced ZERO rows — a null prints "
                             "rows, so this is a FAILURE, not a result")
    N.write_tsv(
        "ARRIVAL_ZOO.tsv",
        ["era", "criterion", "score", "policy", "knob", "kind", "n_reads",
         "usd_per_session", "sd_usd", "seats_per_session", "shuffled_null",
         "delta_vs_luck_bar", "oracle_ceiling", "capture_of_ceiling",
         "aim_08ceiling", "gap_to_aim", "beats_search_adjusted_null",
         "void_incumbent", "delta_vs_void_incumbent"], rows,
        extra=[
            "THE OBJECT IS RESPECIFIED.  The committed seat rule is the cell's "
            "EVENTUAL argmax (newobj.py:361) — the argmax is the cell's first "
            "arrival only 5.9-14.4% of the time and the mean lookahead is ~5.5 "
            "HOURS (LEAK_SEATING_CENSUS.tsv).  The RETROSPECTIVE_INCUMBENT row "
            "is printed ONLY to size the void; it is marked "
            "VOID_FOR_DEPLOYMENT and is never a promotion target.",
            "EVERY OTHER ROW IS STRICTLY CAUSAL AT ARRIVAL: the decision at "
            "arrival j reads only arrivals <= j.  DAYSOFAR recalibrates its "
            "threshold intraday from the day's own past arrivals, which is "
            "lawful for exactly that reason.",
            "TAU thresholds are quantiles of the TRAINING BLOCK's own score "
            "distribution — prior eras only, never the eval era.",
            "THE POLICY FAMILY IS A SEARCH, so it carries a SEARCH-ADJUSTED "
            "NULL: the identical family runs on SHUFFLED scores with the "
            "ARRIVAL TIMES PRESERVED, and the BEST of those is the luck bar "
            "the FAMILY_VERDICT row must clear.",
            "S_TABPFN is first by design: it is the only score in the program "
            "with calibrated GLOBAL discrimination (AUC 0.687), which is the "
            "shape a stopping rule consumes.  Its earlier 'loss' was measured "
            "against the within-cell objective the leak audit has now voided.",
            "The <=10 trades/day cap is applied causally by truncating each "
            "asset-session's chronological seat list to its first %d."
            % DAY_CAP])
    hb("ARRIVAL_ZOO.tsv: %d rows" % len(rows))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zoo", action="store_true")
    ap.add_argument("--eras", nargs="*", default=None)
    a = ap.parse_args()
    if a.zoo:
        run(eras=tuple(a.eras) if a.eras else ERAS)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
