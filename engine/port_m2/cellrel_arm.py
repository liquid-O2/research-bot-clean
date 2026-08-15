#!/usr/bin/python3
"""PORT M2 — THE CELLREL ARM ON THE DEPLOYED STACK CONFIG (audit finding).

AUDIT: every member family of the deployed stack (`fit_weighted`, `_bag_one`,
`fit_reg`, `_con_one`) calls `NA.feat_cols` -- the BASE 184 columns.  CELLREL is
NOT in the deployed stack.  It was measured as the marquee screen axis (+$68 at
matched config, and the top screen cells all carried it) and then died with the
RETRACTED atlas arm -- the retraction was of the JOINT arm's dollars, not of the
feature family.  A measured screen winner has been sitting unused.

This runs CELLREL on the CURRENT deployed configuration -- W_VOLMATCH weighting
x TOP50 monotone constraints, cell grouping, champion per-era HP -- as a 5-seed
distribution against the same configuration on BASE.  Binding eras first.
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


def _one(job):
    era, seed, feat = job
    try:
        import xgboost as xgb
        D, P = CF.boot()
        tr, itr, iva, ev = NA.fold(D, era)
        spec = dict(CF.SPEC); spec["feat"] = feat
        XF, FN = RA.build_features(D, spec, tr, np.arange(D["d8"].size))
        val = D["cert_close_usd"].astype(np.float64)
        hp = NA.CHAMP_HP[era]
        vec = CP._vec(D, era, 50)
        # the constraint vector is BASE-length; CELLREL appends columns, which
        # are left UNCONSTRAINED (no stability receipt exists for them yet)
        vec = list(vec) + [0] * (XF.shape[1] - len(vec))
        cfg = {"objective": "rank:ndcg", "eval_metric": "ndcg@3",
               "tree_method": "hist", "min_child_weight": 20, "subsample": .8,
               "colsample_bytree": .8, "lambdarank_pair_method": "topk",
               "lambdarank_normalization": True,
               "lambdarank_num_pair_per_sample":
                   hp["lambdarank_num_pair_per_sample"],
               "max_depth": hp["max_depth"], "eta": hp["eta"],
               "seed": N.SEED + seed, "nthread": RA.N_THREAD,
               "monotone_constraints": "(" + ",".join(str(int(z))
                                                      for z in vec) + ")"}
        rf, gf = RA._groups_of(D, tr, CF.SPEC)
        d = xgb.DMatrix(XF[rf], label=NA.grades(val[rf]), feature_names=FN)
        d.set_group(gf)
        gw = CU.group_weights(D, tr, rf, gf, era, "W_VOLMATCH")
        if gw is not None:
            d.set_weight(gw)
        b = xgb.train(cfg, d, int(hp["rounds"]))
        del d
        rs, _g = RA._groups_of(D, ev, CF.SPEC)
        sc = np.full(D["d8"].size, np.nan)
        sc[rs] = b.predict(xgb.DMatrix(XF[rs], feature_names=FN),
                           output_margin=True)
        np.save(os.path.join(CU._sdir(), "CELLREL%s_%s_%d.npy"
                             % (feat, era, seed)), sc.astype(np.float32))
        a = N.read_rows(D, N.replay_delayed(
            D, N.top_per_cell_score(D, ev, sc,
                                    N.committed_policy()[era][1]), P))
        return (era, seed, feat, a["usd_per_session"], None)
    except Exception as e:                              # noqa: BLE001
        return (era, seed, feat, None, "%s: %s" % (type(e).__name__, e))


def run(workers=6):
    import multiprocessing as mp
    D, P = CF.boot()
    ceil = CO.ceilings()
    eras = BINDING + CONTEXT
    jobs = [(e, s, f) for f in ("CELLREL", "BASE") for e in eras
            for s in SEEDS]
    N.hb("cellrel arm: %d fits (2 feature sets x %d eras x %d seeds)"
         % (len(jobs), len(eras), len(SEEDS)))
    res, errs, t0 = {}, [], time.time()
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        for i, (e, s, f, v, err) in enumerate(
                pool.imap_unordered(_one, jobs), 1):
            if err:
                errs.append(err)
                N.hb("cellrel FAILED %s %s: %s" % (f, e, err))
                continue
            res.setdefault((f, e), []).append(v)
            if i % 10 == 0 or i == len(jobs):
                N.hb("cellrel %d/%d [eta %.0fs]"
                     % (i, len(jobs), (time.time() - t0) / i * (len(jobs) - i)))
    rows = []
    for e in eras:
        b = np.asarray([x for x in res.get(("BASE", e), []) if x is not None])
        c = np.asarray([x for x in res.get(("CELLREL", e), [])
                        if x is not None])
        if b.size == 0 or c.size == 0:
            continue
        cl = ceil.get("%s|ALL" % e)
        rows.append([e, "BINDING" if e in BINDING else "context",
                     int(b.size), N._r(b.mean()), N._r(b.std()),
                     int(c.size), N._r(c.mean()), N._r(c.std()),
                     N._r(c.mean() - b.mean()),
                     N._r(c.mean() - b.mean() - c.std()),
                     N._r(c.mean() / cl, 4) if cl else ""])
    if not rows:
        raise N.NewObjRefusal("cellrel arm produced zero rows (%d errors)"
                              % len(errs))
    N.write_tsv("CELLREL_ON_STACK.tsv",
                ["era", "criterion", "n_base", "base_mean", "base_sd",
                 "n_cellrel", "cellrel_mean", "cellrel_sd", "delta",
                 "delta_minus_sd", "cellrel_capture"], rows,
                extra=["AUDIT FINDING: CELLREL is NOT in the deployed stack -- "
                       "every member family uses the BASE 184 columns.  It was "
                       "the marquee screen axis and died with the RETRACTED "
                       "atlas arm, but the retraction was of that arm's "
                       "DOLLARS, not of the feature family.",
                       "Both arms are the CURRENT deployed configuration "
                       "(W_VOLMATCH x TOP50 constraints, cell grouping, "
                       "champion per-era HP); only the feature set differs.",
                       "The 64 CELLREL columns are left UNCONSTRAINED -- no "
                       "stability receipt exists for them yet, and inventing "
                       "one here would be fitting the prior to the arm.",
                       "PROMOTION: delta_minus_sd > 0 on the BINDING eras "
                       "(E5/E6/E7).  E3/E4 are context only."])
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    if a.run:
        run()
    else:
        ap.print_help()
