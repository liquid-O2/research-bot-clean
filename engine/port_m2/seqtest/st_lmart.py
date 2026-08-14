#!/usr/bin/python3
"""PORT M2 SEQTEST — THE IR-FIELD BASELINE (LambdaMART on the existing matrix).

The mature learning-to-rank tool, aimed straight at the deficit ledger's
dominant component, on the features the program already has:

    xgboost `rank:ndcg`, GROUPS = (asset, day, CLASS), the committed m3 matrix's
    own feature columns, the lane's own walk-forward whole-day folds, and the
    identical m3_walk deployable scoring.

Why it matters either way, stated before the run: **if listwise-on-features
already moves SEL_WRONG_MEMBER, that is deployable today without a transformer;
if it does not, it is the honest floor the deep stack has to beat.**

Relevance grades are the certificate dollars mapped onto the 0..4 grade scale
`rank:ndcg` wants, by fixed dollar thresholds (not fitted): <=0, >0, >=$600
(the D-021 floor), >=$1,000 (the D-021 target), >=$2,000.

Run:  st_lmart.py --run
"""
import argparse
import json
import os
import time

import numpy as np

import st_common as SC
import st_run as R
import st_rank as RK
import m3_common as M3

GRADE_EDGES = (0.0, 600.0, 1000.0, 2000.0)   # -> grades 0..4
ROUNDS = 300
EARLY = 25


def grades(v):
    g = np.zeros(v.size, dtype=np.int32)
    for e in GRADE_EDGES:
        g += (v >= e).astype(np.int32)
    g[v <= 0] = 0
    return np.clip(g, 0, 4)


def _group_arrays(D, rows, klass):
    """Rows sorted by group + the xgboost group-size vector."""
    r = np.asarray(rows, dtype=np.int64)
    key = (D["asset_idx"][r].astype(np.int64) * 100000000
           + D["d8"][r].astype(np.int64)) * 100 + klass[r]
    order = np.lexsort((D["dec_sec"][r], key))
    ro, ko = r[order], key[order]
    _u, cnt = np.unique(ko, return_counts=True)
    return ro, cnt


def run(test_eras=SC.TEST_ERAS, tag="LMART_M3FEATURES"):
    import xgboost as xgb
    import m3_walk as W
    D, _p = W.load_matrix()
    klass, cls_names = RK.class_index(D)
    ceil = R.ceilings_of(D)
    value = D["cert_close_usd"].astype(np.float64)
    n = D["d8"].size
    score = np.full(n, np.nan)
    pos = np.zeros(n, dtype=np.int64)      # every matrix row is scoreable here
    ledger = []
    j = D["names"].index("in_news_window")
    for era in test_eras:
        t0 = time.time()
        tr, ev = R.fold_rows(D, era)
        tr = tr[D["X"][tr, j] < 0.5]
        ev_r = ev[D["X"][ev, j] < 0.5]
        cut = SC.inner_split_days(D["d8"][tr])
        itr, iva = tr[D["d8"][tr] <= cut], tr[D["d8"][tr] > cut]
        SC.assert_disjoint_days(itr, iva, D["d8"], tag="%s inner" % era)
        r_itr, g_itr = _group_arrays(D, itr, klass)
        r_iva, g_iva = _group_arrays(D, iva, klass)
        dtr = xgb.DMatrix(D["X"][r_itr], label=grades(value[r_itr]),
                          feature_names=list(D["names"]))
        dtr.set_group(g_itr)
        dva = xgb.DMatrix(D["X"][r_iva], label=grades(value[r_iva]),
                          feature_names=list(D["names"]))
        dva.set_group(g_iva)
        cfg = {"objective": "rank:ndcg", "eval_metric": "ndcg@3",
               "tree_method": "hist", "eta": 0.05, "max_depth": 6,
               "min_child_weight": 20, "subsample": 0.8,
               "colsample_bytree": 0.8, "lambdarank_pair_method": "topk",
               "lambdarank_num_pair_per_sample": 8,
               "seed": SC.SEED, "nthread": 8}
        b = xgb.train(cfg, dtr, ROUNDS, evals=[(dva, "inner")],
                      early_stopping_rounds=EARLY, verbose_eval=False)
        best_rounds = int(b.best_iteration) + 1
        inner = float(b.best_score)
        # refit on the WHOLE training block at the selected round count
        r_tr, g_tr = _group_arrays(D, tr, klass)
        dall = xgb.DMatrix(D["X"][r_tr], label=grades(value[r_tr]),
                           feature_names=list(D["names"]))
        dall.set_group(g_tr)
        b2 = xgb.train(cfg, dall, best_rounds)
        s = b2.predict(xgb.DMatrix(D["X"][ev_r], feature_names=list(D["names"])))
        score[ev_r] = s
        g_ev = RK.build_groups(D, ev_r, klass)
        nd, ng = RK.ndcg_at_k(score, value, g_ev, 3)
        rnd = np.random.RandomState(SC.SEED).rand(n)
        nd_rand, _ = RK.ndcg_at_k(rnd, value, g_ev, 3)
        nd_earl, _ = RK.ndcg_at_k(-D["dec_sec"].astype(np.float64), value,
                                  g_ev, 3)
        ledger.append({"era": era, "loss": "rank:ndcg", "inner_ndcg3": inner,
                       "best_epoch": best_rounds,
                       "loss_curve": [["rank:ndcg", round(inner, 5)]],
                       "n_groups_train": len(RK.build_groups(D, tr, klass)),
                       "n_groups_eval": len(g_ev),
                       "median_group": int(np.median([g.size for g in g_ev]))
                       if g_ev else 0,
                       "eval_ndcg3": nd, "eval_ndcg3_random": nd_rand,
                       "eval_ndcg3_earliest": nd_earl, "n_scored_groups": ng,
                       "n_eval": int(ev_r.size),
                       "fit_secs": round(time.time() - t0, 1)})
        SC.hb("LMART %s: rounds=%d inner_ndcg3=%.5f eval NDCG@3 %.5f "
              "(random %.5f, earliest %.5f) over %d groups (%.0fs)"
              % (era, best_rounds, inner, nd, nd_rand, nd_earl, ng,
                 time.time() - t0))
    per, pool = R.eval_scores(D, score, score, ceil, pos, test_eras=test_eras)
    R.save_result(tag, {"kind": "rank", "arch": "lambdamart-m3features",
                        "rung": "gbt", "L": 0, "trunk": "NONE",
                        "mode": "ctx", "classes": cls_names,
                        "pretrained": False,
                        "per_era": [R._strip(a) for a in per], "pooled": pool,
                        "ledger": ledger, "gpu": {"device": "cpu/xgboost"}})
    np.savez(os.path.join(R._sdir(), "%s.npz" % tag), champ=score, win=score)
    SC.hb("%s pooled capture_oracle=%.4f [%.4f,%.4f]"
          % (tag, pool["capture_oracle"] or float("nan"),
             pool["co_lo"] or float("nan"), pool["co_hi"] or float("nan")))
    return pool


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--eras", default=",".join(SC.TEST_ERAS))
    a = ap.parse_args()
    if a.run:
        run(test_eras=tuple(a.eras.split(",")))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
