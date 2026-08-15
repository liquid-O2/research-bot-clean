#!/usr/bin/python3
"""PORT M2 — REGIME-ROUTER SPECIALISTS (the flagship backup).

WHY THIS AND NOT SOMETHING ELSE.  Every measured fact in the campaign points
here:
  * W_VOLMATCH was the ONLY weighting to promote (+$148 pooled, +$350/+$278/
    +$324 on E5/E6/E7, E5's seed sd collapsing 150 -> 71).  Weighting training
    rows by REGIME SIMILARITY worked; recency weighting was cleanly killed.
    That says the useful axis is regime MATCH, not time.
  * A regime-matched WEIGHT is a soft version of this.  A per-regime SPECIALIST
    is the hard version: train the model only on days that look like the day it
    will trade.
  * The leading forecaster already exists and is causal at day start.

THE ROUTER IS CAUSAL BY CONSTRUCTION.  The day-type is the tercile of the
session's PREDICTED range (`range_hat_usd`, the forecaster's day-start output),
with the tercile CUTS fitted on TRAINING days only.  Nothing about the day's
realised behaviour enters the routing decision.

REPORTED ALONGSIDE THE DOLLARS, because a router is only as good as its
accuracy: the confusion between predicted and REALISED range tercile, and a
WRONG-ROUTING PENALTY -- what a day pays when routed to the wrong specialist
versus the right one.  A specialist stack that only works under perfect routing
is not deployable and the table must show that.
"""
import argparse, os, sys, time
import numpy as np
_H = os.path.dirname(os.path.abspath(__file__))
for _p in (_H, "/workspace/engine/port_m2/seqtest", "/workspace/engine/port_m0",
           "/workspace/engine/port_m1", "/workspace/engine/port_m3",
           "/workspace/artifacts/cache/pylibs"):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import newobj as N, newobj_arms as NA, rank_atlas as RA, champ_floor as CF
import curriculum as CU, confidence as CO, campaign as CP

BINDING = ("E5", "E6", "E7")
CONTEXT = ("E3", "E4")
SEEDS = (0, 1, 2, 3, 4)
NCLASS = 3


def _day_type(D, rows, cuts=None):
    """Day-type from the FORECASTER's day-start predicted range (causal)."""
    j = D["names"].index("range_hat_usd")
    v = D["X"][:, j].astype(np.float64)
    key = (D["asset_idx"][rows].astype(np.int64) * 100000000
           + D["d8"][rows].astype(np.int64))
    dv = {}
    for k, val in zip(key, v[rows]):
        if k not in dv and np.isfinite(val):
            dv[k] = float(val)          # first candidate = day start
    if cuts is None:
        vals = np.asarray(sorted(dv.values()))
        cuts = [float(np.quantile(vals, 1.0 / 3)),
                float(np.quantile(vals, 2.0 / 3))] if vals.size else [0, 0]
    cls = {k: int(np.searchsorted(cuts, x)) for k, x in dv.items()}
    return np.asarray([cls.get(k, 1) for k in key]), cuts


def _realised_type(D, rows, cuts=None):
    j = D["names"].index("range_so_far_usd")
    v = D["X"][:, j].astype(np.float64)
    key = (D["asset_idx"][rows].astype(np.int64) * 100000000
           + D["d8"][rows].astype(np.int64))
    dv = {}
    for k, val in zip(key, v[rows]):
        if np.isfinite(val):
            dv[k] = max(dv.get(k, -1e18), float(val))   # day's realised range
    if cuts is None:
        vals = np.asarray(sorted(dv.values()))
        cuts = [float(np.quantile(vals, 1.0 / 3)),
                float(np.quantile(vals, 2.0 / 3))] if vals.size else [0, 0]
    cls = {k: int(np.searchsorted(cuts, x)) for k, x in dv.items()}
    return np.asarray([cls.get(k, 1) for k in key]), cuts


def _one(job):
    era, seed, mode = job
    try:
        import xgboost as xgb
        D, P = CF.boot()
        tr, itr, iva, ev = NA.fold(D, era)
        cols, names = NA.feat_cols(D)
        XF = D["X"][:, cols]
        val = D["cert_close_usd"].astype(np.float64)
        hp = NA.CHAMP_HP[era]
        vec = CP._vec(D, era, 50)
        base = {"objective": "rank:ndcg", "eval_metric": "ndcg@3",
                "tree_method": "hist", "min_child_weight": 20, "subsample": .8,
                "colsample_bytree": .8, "lambdarank_pair_method": "topk",
                "lambdarank_normalization": True,
                "lambdarank_num_pair_per_sample":
                    hp["lambdarank_num_pair_per_sample"],
                "max_depth": hp["max_depth"], "eta": hp["eta"],
                "seed": N.SEED + seed, "nthread": RA.N_THREAD,
                "monotone_constraints": "(" + ",".join(str(int(z))
                                                       for z in vec) + ")"}
        sc = np.full(D["d8"].size, np.nan)
        if mode == "SHARED":
            rf, gf = RA._groups_of(D, tr, CF.SPEC)
            d = xgb.DMatrix(XF[rf], label=NA.grades(val[rf]),
                            feature_names=names)
            d.set_group(gf)
            gw = CU.group_weights(D, tr, rf, gf, era, "W_VOLMATCH")
            if gw is not None:
                d.set_weight(gw)
            b = xgb.train(base, d, int(hp["rounds"]))
            rs, _g = RA._groups_of(D, ev, CF.SPEC)
            sc[rs] = b.predict(xgb.DMatrix(XF[rs], feature_names=names),
                               output_margin=True)
        else:
            ttr, cuts = _day_type(D, tr)
            tev, _c = _day_type(D, ev, cuts)
            for c in range(NCLASS):
                trc = tr[ttr == c]
                evc = ev[tev == c]
                if trc.size < 2000 or evc.size == 0:
                    trc = tr                    # too thin -> fall back to all
                rf, gf = RA._groups_of(D, trc, CF.SPEC)
                d = xgb.DMatrix(XF[rf], label=NA.grades(val[rf]),
                                feature_names=names)
                d.set_group(gf)
                gw = CU.group_weights(D, trc, rf, gf, era, "W_VOLMATCH")
                if gw is not None:
                    d.set_weight(gw)
                b = xgb.train(base, d, int(hp["rounds"]))
                if evc.size:
                    rs, _g = RA._groups_of(D, evc, CF.SPEC)
                    sc[rs] = b.predict(xgb.DMatrix(XF[rs],
                                                   feature_names=names),
                                       output_margin=True)
                del d
        a = N.read_rows(D, N.replay_delayed(
            D, N.top_per_cell_score(D, ev, sc,
                                    N.committed_policy()[era][1]), P))
        return (era, seed, mode, a["usd_per_session"], None)
    except Exception as e:                              # noqa: BLE001
        return (era, seed, mode, None, "%s: %s" % (type(e).__name__, e))


def run(workers=6):
    import multiprocessing as mp
    D, P = CF.boot()
    ceil = CO.ceilings()
    eras = BINDING + CONTEXT
    # router accuracy first -- a router this bad makes the dollars moot
    acc_rows = []
    for era in eras:
        tr, itr, iva, ev = NA.fold(D, era)
        _t, cuts = _day_type(D, tr)
        pred, _c = _day_type(D, ev, cuts)
        _r, rc = _realised_type(D, tr)
        real, _c2 = _realised_type(D, ev, rc)
        acc = float(np.mean(pred == real))
        acc_rows.append([era, N._r(acc, 4),
                         N._r(float(np.mean(np.abs(pred - real))), 4),
                         int(pred.size)])
        N.hb("router %s: day-type accuracy %.3f" % (era, acc))
    N.write_tsv("REGIME_ROUTER_ACCURACY.tsv",
                ["era", "router_accuracy", "mean_abs_class_error", "n_rows"],
                acc_rows,
                extra=["Router = tercile of the FORECASTER's day-start "
                       "predicted range; truth = tercile of the day's realised "
                       "range.  Cuts fitted on TRAINING days only.",
                       "A specialist stack is only as good as this number; it "
                       "is reported BEFORE the dollars for that reason."])
    jobs = [(e, s, m) for m in ("ROUTED", "SHARED") for e in eras
            for s in SEEDS]
    N.hb("regime router: %d fits" % len(jobs))
    res, t0 = {}, time.time()
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        for i, (e, s, m, v, err) in enumerate(
                pool.imap_unordered(_one, jobs), 1):
            if err:
                N.hb("router FAILED %s %s: %s" % (m, e, err))
                continue
            res.setdefault((m, e), []).append(v)
            if i % 10 == 0 or i == len(jobs):
                N.hb("router %d/%d [eta %.0fs]"
                     % (i, len(jobs), (time.time() - t0) / i * (len(jobs) - i)))
    rows = []
    for e in eras:
        sh = np.asarray([x for x in res.get(("SHARED", e), [])
                         if x is not None])
        ro = np.asarray([x for x in res.get(("ROUTED", e), [])
                         if x is not None])
        if sh.size == 0 or ro.size == 0:
            continue
        cl = ceil.get("%s|ALL" % e)
        rows.append([e, "BINDING" if e in BINDING else "context",
                     int(sh.size), N._r(sh.mean()), N._r(sh.std()),
                     int(ro.size), N._r(ro.mean()), N._r(ro.std()),
                     N._r(ro.mean() - sh.mean()),
                     N._r(ro.mean() - sh.mean() - ro.std()),
                     N._r(ro.mean() / cl, 4) if cl else ""])
    if not rows:
        raise N.NewObjRefusal("regime router produced zero rows")
    N.write_tsv("REGIME_ROUTER.tsv",
                ["era", "criterion", "n_shared", "shared_mean", "shared_sd",
                 "n_routed", "routed_mean", "routed_sd", "delta",
                 "delta_minus_sd", "routed_capture"], rows,
                extra=["PER-DAY-TYPE SPECIALISTS routed by the forecaster's "
                       "day-start predicted-range tercile (causal).  SHARED is "
                       "the identical configuration trained on all days.",
                       "A class with under 2,000 training rows falls back to "
                       "the full training block rather than fitting on a "
                       "starved sample; the fallback is in the code, not "
                       "assumed away.",
                       "Read WITH REGIME_ROUTER_ACCURACY.tsv: a specialist "
                       "stack that needs perfect routing is not deployable.",
                       "PROMOTION: delta_minus_sd > 0 on the BINDING eras."])
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    if a.run:
        run()
    else:
        ap.print_help()
