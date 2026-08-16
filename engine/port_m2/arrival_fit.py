#!/usr/bin/python3
"""PORT M2 — THE ARRIVAL-TIME POLICY, STEP 2: TRAIN FOR THE DECISION WE MAKE.

WHAT THE LEAK AUDIT PROVED ABOUT THE EXISTING SCORES
  The deployed score is informative in RANK and not in LEVEL: the cell's rank-1
  member is worth $294.85 against a population mean of -$24.52, yet every
  threshold-shaped causal rule on that same score reads ~$0
  (LEAK_SEATING_MECHANISM.tsv).  That is not a paradox — it is what a pairwise
  ranking objective optimises.  `rank:ndcg` is invariant to any monotone
  transform of the score WITHIN a group and is never asked to make the score
  mean the same thing across groups.  A STOPPING RULE CONSUMES LEVEL, so the
  champion's objective is the wrong objective for the decision we actually
  make, and no amount of threshold tuning on its output can repair that.

THE TWO TARGETS, both GLOBAL and both calibrated
  A_PWIN   P(this candidate is a D-021 WINNER) — cert >= $1,000, MAE <= $300,
           not walled.  The plain "is this a good trade" probability.
  A_PBAR   P(this candidate CLEARS THE DAY'S EVENTUAL BAR) — its certificate is
           at least the k-th best of its own asset-day among deployable
           candidates, k = the compliant day cap.  This is precisely the
           quantity a stopping rule needs: not "is it good" but "is it good
           enough to spend one of today's three seats on RIGHT NOW".  It is a
           historical label — computed from the whole day in hindsight, like
           every label — and the model predicts it causally.

  Both are fitted with `binary:logistic` on the DEPLOYED FOLD's structure
  (per-era strictness k, its monotone sign vector, W_VOLMATCH weighting pushed
  from group grain down to row grain, the era's depth/eta/rounds) and then
  ISOTONICALLY CALIBRATED on the era's own INNER VALIDATION BLOCK, which is
  training-block data and never the eval era.  The calibration is what makes
  the level mean something; without it a logistic score is still only ordinal.

THE LAW
  No adaptive HP optimiser: the config is inherited, fixed, pre-registered.
  5 seeds.  Day-clustered intervals.  Binding eras first.  The causal policy
  family from `arrival.py` is re-run on the calibrated probability, and it
  carries the same SEARCH-ADJUSTED LUCK BAR (identical family, shuffled scores,
  arrival times preserved).  Evaluation is always REAL REPLAY DOLLARS under
  arrival-time seating with the one-position constraint, the <=10/day cap and
  the adopted first-wall stop.

CLI
  arrival_fit.py --fit [--workers 5] [--eras ...]     fit + calibrate
  arrival_fit.py --policy [--eras ...]                the policy family on them
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
import arrival as AR                      # noqa: E402

VERSION = "PORT-M2-ARRIVALFIT-V1"
OUT_ROOT = os.path.join(MC.M2_ROOT, "arrival")
SCORES = os.path.join(OUT_ROOT, "scores")
BINDING = AR.BINDING
ERAS = AR.ERAS
SEEDS = AR.SEEDS
# The three arrival targets, plus the ENGINE VARIANTS of the expectancy that
# ARRIVAL_ENGINES.tsv measured (LightGBM doubles E7's tail dollars over xgb and
# cuts seed variance 27x).  Their score columns are already on disk; listing
# them here is what puts them through the causal policy family and its
# search-adjusted luck bar, which is the only thing that can promote them.
TARGETS = ("A_PWIN", "A_PBAR", "A_EV",
           "A_EV_LGBM", "A_EV_LGBM_DART", "A_EV_CATB")
# The engine variants are SCORED ONLY (never refitted here): _one() returns
# CACHED for any target whose .npy already exists, so --fit is a no-op for them
# and --policy is what consumes them.


def hb(m):
    sys.stderr.write("[arrfit %s] %s\n" % (time.strftime("%H:%M:%S"), m))
    sys.stderr.flush()


class FitRefusal(RuntimeError):
    """A guard fired.  Never downgraded, never silently filtered."""


def day_bar_label(D, k=AR.DAY_CAP):
    """1 where the candidate's certificate reaches the k-th best of its own
    asset-day, over the DEPLOYABLE pool of that day.  The day's own bar, in
    hindsight — a label, exactly like every other label in this program."""
    v = D["cert_close_usd"].astype(np.float64)
    ok = D["cert_refused"] == 0
    dep = np.zeros(v.size, dtype=bool)
    dep[N.deployable(D, np.arange(v.size))] = True
    y = np.zeros(v.size, dtype=np.float64)
    sess = D["session"]
    order = np.argsort(sess, kind="stable")
    so = sess[order]
    st = [0] + (np.flatnonzero(so[1:] != so[:-1]) + 1).tolist()
    for a, b in zip(st, st[1:] + [so.size]):
        idx = order[a:b]
        good = idx[ok[idx] & dep[idx] & np.isfinite(v[idx])]
        if good.size == 0:
            continue
        srt = np.sort(v[good])[::-1]
        bar = float(srt[min(k, srt.size) - 1])
        y[idx] = (v[idx] >= bar).astype(np.float64)
    return y


def isotonic(x, y):
    """Isotonic (pool-adjacent-violators) calibration, returned as a callable.

    A MONOTONE map from score to probability: it cannot reorder anything — the
    within-cell ranking the champion already has is preserved exactly — it can
    only make the LEVEL mean what it claims to mean.  That is precisely the
    quantity a stopping rule consumes and the one the ranking objective never
    had to supply.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    if x.size == 0:
        raise FitRefusal("isotonic calibration got an EMPTY inner block")
    from sklearn.isotonic import IsotonicRegression
    ir = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
    ir.fit(x, y)

    def f(z):
        z = np.asarray(z, dtype=np.float64)
        out = np.full(z.size, np.nan)
        k = np.isfinite(z)
        if k.any():
            out[k] = ir.predict(z[k])
        return out
    return f


def _one(job):
    target, era, seed = job
    try:
        # INCREMENTAL: a score already on disk is not refitted.  Deleting the
        # .npy is the explicit way to force a redo, so a corrected target can
        # be added to TARGETS without paying for the ones already measured.
        _sp = os.path.join(SCORES, "%s_%s_%d.npy" % (target, era, seed))
        if os.path.exists(_sp):
            return (target, era, seed, None, None, None, "CACHED")
        import xgboost as xgb
        import newobj_arms as NA
        import rank_atlas as RA
        import champ_floor as CF
        import curriculum as CU
        import campaign as CP
        import fold_stack as FS
        D, P = CF.boot()
        tr, itr, iva, ev = NA.fold(D, era)
        # A_EV is the AUDIT'S OWN PRESCRIPTION and the only ABSOLUTE
        # expectancy of the three: a stopping rule compares this candidate's
        # expected DOLLARS against the continuation value in DOLLARS, so the
        # target must be dollars.  A_PWIN is a threshold indicator (absolute
        # but coarse); A_PBAR is DAY-RELATIVE and is retained only as the
        # measured counter-example — its AUC 0.89 does not convert, because
        # being the best of a bad day is still a losing trade.
        if target == "A_PWIN":
            y = np.nan_to_num(D["y_winner"].astype(np.float64), nan=0.0)
        elif target == "A_PBAR":
            y = day_bar_label(D)
        else:
            y = np.nan_to_num(D["cert_close_usd"].astype(np.float64), nan=0.0)
        # LEAK FIX P3_DOM_SHARE_FEATURE: the audited leaky columns are dropped
        # here, and the monotone sign vector is subset BY POSITION so the
        # surviving columns keep exactly the signs the champion gave them.
        base_cols, base_names = NA.feat_cols(D)
        vec_base = list(CP._vec(D, era, FS.BEST_K[era]))
        keep = [j for j, n in enumerate(base_names)
                if n not in AR.LEAKY_FEATURES]
        cols = [base_cols[j] for j in keep]
        names = [base_names[j] for j in keep]
        vec = ([vec_base[j] for j in keep]
               if len(vec_base) == len(base_cols) else [0] * len(keep))
        XF = D["X"][:, cols]
        hp = NA.CHAMP_HP[era]
        vec = vec[:XF.shape[1]] + [0] * max(0, XF.shape[1] - len(vec))
        is_ev = (target == "A_EV")
        cfg = {"objective": ("reg:squarederror" if is_ev
                             else "binary:logistic"),
               "eval_metric": ("rmse" if is_ev else "logloss"),
               "tree_method": "hist", "min_child_weight": 20, "subsample": .8,
               "colsample_bytree": .8, "max_depth": hp["max_depth"],
               "eta": hp["eta"], "seed": N.SEED + seed,
               "nthread": RA.N_THREAD,
               "monotone_constraints": "(" + ",".join(str(int(z))
                                                      for z in vec) + ")"}
        cfg.update(FS.BEST_HP.get(era, {}))
        # W_VOLMATCH, pushed from GROUP grain to ROW grain so the pointwise
        # objective inherits the one weighting treatment that ever promoted
        r_f, g_f = RA._groups_of(D, itr, CF.SPEC)
        gw = CU.group_weights(D, itr, r_f, g_f, era, "W_VOLMATCH")
        wrow = None
        if gw is not None:
            wrow = np.repeat(np.asarray(gw, dtype=np.float64),
                             np.asarray(g_f, dtype=np.int64))
        d = xgb.DMatrix(XF[r_f], label=y[r_f], feature_names=names)
        if wrow is not None:
            d.set_weight(wrow)
        b = xgb.train(cfg, d, int(hp["rounds"]))
        del d
        # ISOTONIC CALIBRATION on the INNER VALIDATION BLOCK (training data,
        # never the eval era).  For A_EV the map is fitted against the SIGN of
        # the certificate, so the calibrated column is P(profitable) while the
        # RAW expectancy is what the policy actually thresholds — both are
        # kept, and A_EV deliberately deploys the RAW dollars because that is
        # the quantity the stopping comparison is in.
        pv = b.predict(xgb.DMatrix(XF[iva], feature_names=names))
        sc = np.full(D["d8"].size, np.nan)
        raw = b.predict(xgb.DMatrix(XF[ev], feature_names=names))
        if is_ev:
            sc[ev] = raw
        else:
            cal = isotonic(pv, y[iva])
            sc[ev] = cal(raw)
        os.makedirs(SCORES, exist_ok=True)
        np.save(os.path.join(SCORES, "%s_%s_%d.npy" % (target, era, seed)),
                sc.astype(np.float32))
        # honest calibration diagnostics on the EVAL era, reported not tuned
        m = np.isfinite(sc[ev])
        yy, pp = y[ev][m], sc[ev][m]
        brier = float(np.mean((pp - yy) ** 2)) if m.any() else None
        base = float(np.mean(yy)) if m.any() else None
        try:
            from sklearn.metrics import roc_auc_score
            # for A_EV the discrimination question is "does it separate
            # profitable from unprofitable", so the AUC is taken against the
            # SIGN of the certificate rather than against the raw dollars
            yb = (yy > 0).astype(int) if is_ev else yy
            auc = float(roc_auc_score(yb, pp)) if len(set(yb.tolist())) > 1 \
                else None
        except Exception:                                 # noqa: BLE001
            auc = None
        return (target, era, seed, brier, base, auc, None)
    except Exception as e:                                # noqa: BLE001
        import traceback
        return (target, era, seed, None, None, None,
                "%s: %s | %s" % (type(e).__name__, e,
                                 traceback.format_exc()[-300:]))


def run_fit(eras=ERAS, workers=5):
    import multiprocessing as mp
    jobs = [(t, e, s) for t in TARGETS for e in eras for s in SEEDS]
    hb("fit: %d jobs (%d targets x %d eras x %d seeds), workers=%d"
       % (len(jobs), len(TARGETS), len(eras), len(SEEDS), workers))
    rows, nerr, t0 = [], 0, time.time()
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        for i, (t, e, s, br, bs, auc, err) in enumerate(
                pool.imap_unordered(_one, jobs), 1):
            if err == "CACHED":
                hb("cached %s %s s%d — not refitted" % (t, e, s))
            elif err:
                nerr += 1
                hb("FIT FAILED %s %s s%d: %s" % (t, e, s, err))
            else:
                rows.append([t, e, s, N._r(br, 5), N._r(bs, 5), N._r(auc, 5)])
            hb("fit %d/%d [eta %.0fs, %d failed]"
               % (i, len(jobs), (time.time() - t0) / i * (len(jobs) - i),
                  nerr))
    if not rows:
        raise FitRefusal("ARRIVAL_TARGETS produced ZERO rows (%d failed) — a "
                         "null prints rows, so this is a FAILURE" % nerr)
    N.write_tsv("ARRIVAL_TARGETS.tsv",
                ["target", "era", "seed", "brier", "base_rate", "auc"], rows,
                extra=[
                    "STEP 2 — TRAINING FOR THE DECISION WE ACTUALLY MAKE.  "
                    "binary:logistic on the DEPLOYED FOLD's structure "
                    "(per-era strictness k, its monotone sign vector, "
                    "W_VOLMATCH pushed to row grain, the era's depth/eta/"
                    "rounds), then ISOTONIC CALIBRATION on the era's own INNER "
                    "VALIDATION BLOCK — training data, never the eval era.",
                    "WHY A NEW OBJECTIVE AT ALL: rank:ndcg is invariant to any "
                    "monotone transform of the score WITHIN a group and is "
                    "never asked to make the score comparable ACROSS groups.  "
                    "A stopping rule consumes exactly that cross-group level, "
                    "which is why the leak audit found the champion's score "
                    "worth $294.85/trade at rank 1 and ~$0 under every "
                    "threshold rule.",
                    "A_PBAR is the stopping-relevant target: not 'is this a "
                    "good trade' but 'is it good enough to spend one of "
                    "today's three seats on right now'.",
                    "brier / auc are HONEST EVAL-ERA DIAGNOSTICS: reported, "
                    "never tuned on, and no threshold in this program is "
                    "chosen from them."])
    hb("ARRIVAL_TARGETS.tsv: %d rows (%d failed)" % (len(rows), nerr))
    return rows


def run_policy(eras=ERAS):
    """The causal policy family from `arrival.py`, on the calibrated targets."""
    import champ_floor as CF
    import stacked_final as SF
    import newobj_arms as NA
    import confidence as CO
    D, P = CF.boot()
    ceil = CO.ceilings()
    rng = np.random.default_rng(N.SEED)
    rows = []
    for era in eras:
        crit = "BINDING" if era in BINDING else "context"
        tr, itr, iva, ev = NA.fold(D, era)
        # THE BAR IS THE CAUSAL ORACLE, not the full-hindsight DP ceiling: an
        # arrival-time rule cannot be asked to capture a fraction of a bound
        # that is allowed to see the whole day.  aims = 0.80 x the causal
        # oracle; the hindsight ceiling is kept beside it as context only.
        cl = AR.CAUSAL_ORACLE.get(era)
        dp = ceil.get("%s|ALL" % era)
        aim = 0.80 * cl if cl else None

        def read(seats):
            rp = N.replay_delayed(D, seats, P)
            return N.read_rows(D, SF.apply_stop(
                D, AR.cap_seats(D, rp), "STOP_WALL1"))

        best_real, best_null = {}, {}
        for tgt in TARGETS:
            cols = []
            for s in SEEDS:
                p = os.path.join(SCORES, "%s_%s_%d.npy" % (tgt, era, s))
                if os.path.exists(p):
                    cols.append(np.load(p).astype(np.float64))
            if not cols:
                continue
            for pname, kind, knob in AR.POLICIES:
                real, null, nse = [], [], []
                for v in cols:
                    r = read(AR.build_seats(D, ev, v, kind, knob, tr))
                    if r.get("usd_per_session") is not None:
                        real.append(r["usd_per_session"])
                        nse.append(r["n_seated"] / max(r["n_sessions"], 1))
                    vs = v.copy()
                    fin = np.nonzero(np.isfinite(vs))[0]
                    vs[fin] = vs[rng.permutation(fin)]
                    rs = read(AR.build_seats(D, ev, vs, kind, knob, tr))
                    if rs.get("usd_per_session") is not None:
                        null.append(rs["usd_per_session"])
                if not real:
                    continue
                a = np.asarray(real, dtype=np.float64)
                nl = np.asarray(null, dtype=np.float64)
                best_real[(tgt, pname)] = a.mean()
                if nl.size:
                    best_null[(tgt, pname)] = nl.mean()
                hb("%s %s %s: $%s (null $%s)"
                   % (era, tgt, pname, N._r(a.mean()),
                      N._r(nl.mean()) if nl.size else "-"))
                rows.append([era, crit, tgt, pname,
                             "" if knob is None else N._r(knob, 4),
                             int(a.size), N._r(a.mean()), N._r(a.std()),
                             N._r(float(np.mean(nse)), 3),
                             N._r(nl.mean()) if nl.size else "",
                             N._r(cl), N._r(a.mean() / cl, 4) if cl else "",
                             N._r(aim), N._r(a.mean() - aim) if aim else "",
                             N._r(dp), ""])
        if best_real:
            bk = max(best_real, key=best_real.get)
            luck = max(best_null.values()) if best_null else None
            rows.append([era, crit, "FAMILY_VERDICT", "%s|%s" % bk, "", "",
                         N._r(best_real[bk]), "", "",
                         N._r(luck) if luck is not None else "", N._r(cl),
                         N._r(best_real[bk] / cl, 4) if cl else "",
                         N._r(aim), N._r(best_real[bk] - aim) if aim else "",
                         N._r(dp),
                         "YES" if (luck is not None
                                   and best_real[bk] > luck) else "no"])
            hb("%s: best calibrated-target policy %s|%s $%.2f (luck $%s)"
               % (era, bk[0], bk[1], best_real[bk],
                  N._r(luck) if luck is not None else "-"))
    if not rows:
        raise FitRefusal("ARRIVAL_FITTED produced ZERO rows — a null prints "
                         "rows, so this is a FAILURE, not a result")
    N.write_tsv(
        "ARRIVAL_FITTED.tsv",
        ["era", "criterion", "target", "policy", "knob", "n_seeds",
         "usd_per_session", "sd_usd", "seats_per_session", "shuffled_null",
         "causal_oracle", "capture_of_causal_oracle", "aim_08causal",
         "gap_to_aim", "hindsight_dp_ceiling",
         "beats_search_adjusted_null"], rows,
        extra=[
            "The causal arrival policy family, run on models TRAINED AND "
            "CALIBRATED FOR THE ARRIVAL DECISION rather than for within-cell "
            "ordering.  Every row is strictly causal: the decision at arrival "
            "j reads only arrivals <= j.",
            "THE FAMILY IS A SEARCH and carries its search-adjusted luck bar: "
            "the identical family on shuffled scores, arrival times preserved, "
            "best-of taken as the bar.",
            "THE DENOMINATOR IS THE CAUSAL ORACLE (E3 $2,348 / E4 $2,133 / "
            "E5 $2,021 / E6 $2,675 / E7 $3,360), not the full-hindsight DP "
            "ceiling: an arrival-time rule may not be asked to capture a "
            "fraction of a bound allowed to see the whole day.  aims = 0.80 x "
            "the causal oracle; the hindsight ceiling rides beside it as "
            "context only.",
            "ANY ROW HERE THAT READS NEGATIVE IS THE HONEST BASELINE, not a "
            "losing arm to file away: it is what this formulation actually "
            "earns at the arrival second, and it is reported as such."])
    hb("ARRIVAL_FITTED.tsv: %d rows" % len(rows))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit", action="store_true")
    ap.add_argument("--policy", action="store_true")
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--eras", nargs="*", default=None)
    a = ap.parse_args()
    eras = tuple(a.eras) if a.eras else ERAS
    did = False
    if a.fit:
        run_fit(eras=eras, workers=a.workers)
        did = True
    if a.policy:
        run_policy(eras=eras)
        did = True
    if not did:
        ap.print_help()


if __name__ == "__main__":
    main()
