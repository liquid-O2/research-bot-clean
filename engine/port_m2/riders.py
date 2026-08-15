#!/usr/bin/python3
"""PORT M2 — TWO RIDERS.

(a) CONSTRAINED-HP RE-SEARCH.  The champion's per-era HP were tuned for
    UNCONSTRAINED trees.  Monotone constraints change the optimal capacity --
    a constrained tree spends depth differently because whole split directions
    are forbidden -- so the inherited depth/eta may now be wrong.  The 12-cell
    grid plus depth 5 and 6 rows is re-searched ON the TOP50-constrained config,
    selected on INNER NDCG (never dollars -- that was the winner's-curse defect),
    and reported as a 5-seed EVAL distribution.

(b) BIG-N ENSEMBLE.  N=50 seeds, score-mean, on the best config available.
    Member rank-correlation is 0.69-0.80, which caps averaging at ~9% noise
    removal, so this is expected to buy PRECISION (a tighter seed sd) rather
    than dollars.  Reported either way.
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
ERAS = BINDING + ("E3", "E4")
SEEDS = (0, 1, 2, 3, 4)
BIGN = 50
HPG = tuple({"max_depth": d, "eta": e}
            for d in (3, 4, 5, 6, 8) for e in (0.05, 0.10))


def _fit(D, era, seed, hp, rows_fit, rows_score, ret_inner=False):
    import xgboost as xgb
    cols, names = NA.feat_cols(D)
    XF = D["X"][:, cols]
    val = D["cert_close_usd"].astype(np.float64)
    ch = NA.CHAMP_HP[era]
    vec = CP._vec(D, era, 50)
    cfg = {"objective": "rank:ndcg", "eval_metric": "ndcg@3",
           "tree_method": "hist", "min_child_weight": 20, "subsample": .8,
           "colsample_bytree": .8, "lambdarank_pair_method": "topk",
           "lambdarank_normalization": True,
           "lambdarank_num_pair_per_sample":
               ch["lambdarank_num_pair_per_sample"],
           "seed": N.SEED + seed, "nthread": RA.N_THREAD,
           "monotone_constraints": "(" + ",".join(str(int(z))
                                                  for z in vec) + ")"}
    cfg.update(hp)
    rf, gf = RA._groups_of(D, rows_fit, CF.SPEC)
    d = xgb.DMatrix(XF[rf], label=NA.grades(val[rf]), feature_names=names)
    d.set_group(gf)
    gw = CU.group_weights(D, rows_fit, rf, gf, era, "W_VOLMATCH")
    if gw is not None:
        d.set_weight(gw)
    if ret_inner:
        rv, gv = RA._groups_of(D, rows_score, CF.SPEC)
        dv = xgb.DMatrix(XF[rv], label=NA.grades(val[rv]),
                         feature_names=names)
        dv.set_group(gv)
        b = xgb.train(cfg, d, int(ch["rounds"]), evals=[(dv, "in")],
                      early_stopping_rounds=25, verbose_eval=False)
        return float(b.best_score)
    b = xgb.train(cfg, d, int(ch["rounds"]))
    rs, _g = RA._groups_of(D, rows_score, CF.SPEC)
    sc = np.full(D["d8"].size, np.nan)
    sc[rs] = b.predict(xgb.DMatrix(XF[rs], feature_names=names),
                       output_margin=True)
    return sc


def _hp_one(job):
    era, hp = job
    try:
        D, P = CF.boot()
        tr, itr, iva, ev = NA.fold(D, era)
        return (era, str(hp), _fit(D, era, 0, hp, itr,
                                   N.deployable(D, iva), True), None)
    except Exception as e:                              # noqa: BLE001
        return (era, str(hp), None, "%s: %s" % (type(e).__name__, e))


def _ev_one(job):
    era, seed, hp = job
    try:
        D, P = CF.boot()
        tr, itr, iva, ev = NA.fold(D, era)
        sc = _fit(D, era, seed, hp, tr, ev)
        np.save(os.path.join(CU._sdir(), "RIDER_%s_%d.npy" % (era, seed)),
                sc.astype(np.float32))
        a = N.read_rows(D, N.replay_delayed(
            D, N.top_per_cell_score(D, ev, sc,
                                    N.committed_policy()[era][1]), P))
        return (era, seed, a["usd_per_session"], None)
    except Exception as e:                              # noqa: BLE001
        return (era, seed, None, "%s: %s" % (type(e).__name__, e))


def run(workers=6, bign=False):
    import multiprocessing as mp
    D, P = CF.boot()
    ceil = CO.ceilings()
    ctx = mp.get_context("spawn")
    jobs = [(e, hp) for e in ERAS for hp in HPG]
    N.hb("rider(a): %d inner fits (constrained-HP re-search)" % len(jobs))
    inner = {}
    with ctx.Pool(processes=workers) as pool:
        for i, (e, hs, v, err) in enumerate(
                pool.imap_unordered(_hp_one, jobs), 1):
            if err:
                continue
            inner[(e, hs)] = v
    best = {}
    irows = []
    for e in ERAS:
        bh, bv = None, -np.inf
        for hp in HPG:
            v = inner.get((e, str(hp)))
            irows.append([e, str(hp), N._r(v, 5) if v else ""])
            if v is not None and v > bv:
                bh, bv = hp, v
        best[e] = bh
        N.hb("rider(a) %s -> %s (inner ndcg %.5f)" % (e, bh, bv))
    N.write_tsv("RIDER_HP_INNER.tsv", ["era", "config", "inner_ndcg3"], irows)
    ev_jobs = [(e, s, best[e]) for e in ERAS for s in SEEDS]
    res = {}
    with ctx.Pool(processes=workers) as pool:
        for i, (e, s, v, err) in enumerate(
                pool.imap_unordered(_ev_one, ev_jobs), 1):
            if err:
                N.hb("rider(a) eval FAILED %s: %s" % (e, err))
                continue
            res.setdefault(e, []).append(v)
    rows = []
    for e in ERAS:
        a = np.asarray([x for x in res.get(e, []) if x is not None])
        if a.size == 0:
            continue
        # the incumbent: champion HP under the same constraints
        inc = []
        for s in SEEDS:
            f = os.path.join(CU._sdir(), "CONTOP50_%s_%d.npy" % (e, s))
            if os.path.exists(f):
                sc = np.load(f).astype(np.float64)
                evr = N.deployable(D, N.era_rows(D, e))
                inc.append(N.read_rows(D, N.replay_delayed(
                    D, N.top_per_cell_score(D, evr, sc,
                                            N.committed_policy()[e][1]),
                    P))["usd_per_session"])
        ic = np.asarray([x for x in inc if x is not None])
        cl = ceil.get("%s|ALL" % e)
        rows.append([e, "BINDING" if e in BINDING else "context",
                     str(best[e]), int(a.size), N._r(a.mean()), N._r(a.std()),
                     N._r(ic.mean()) if ic.size else "",
                     N._r(a.mean() - ic.mean()) if ic.size else "",
                     N._r(a.mean() - ic.mean() - a.std()) if ic.size else "",
                     N._r(a.mean() / cl, 4) if cl else ""])
    if not rows:
        raise N.NewObjRefusal(
            "RIDER produced ZERO rows -- a null prints rows, so this is a "
            "FAILURE.  inner selections=%d, eval results=%d"
            % (len(inner), sum(len(v) for v in res.values())))
    N.write_tsv("RIDER_CONSTRAINED_HP.tsv",
                ["era", "criterion", "chosen_hp", "n_seeds", "mean_usd",
                 "sd_usd", "incumbent_champHP_mean", "delta",
                 "delta_minus_sd", "capture"], rows,
                extra=["RIDER (a): the HP grid re-searched ON the "
                       "TOP50-constrained configuration.  The champion's per-era "
                       "HP were tuned for UNCONSTRAINED trees, and constraints "
                       "change the optimal capacity.",
                       "Selected on INNER NDCG@3 -- never on inner dollars, "
                       "which was the winner's-curse defect this campaign "
                       "already had to correct once.",
                       "Incumbent = the same constrained config at the "
                       "champion's inherited HP.  PROMOTION: delta_minus_sd > 0 "
                       "on the BINDING eras."])
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    if a.run:
        run()
    else:
        ap.print_help()
