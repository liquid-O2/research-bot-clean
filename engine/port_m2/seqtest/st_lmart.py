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


def _pct_within(v, key):
    """Within-group percentile, so two heads on different scales can be summed
    (the same device m3_walk._unit_pct uses for its composition)."""
    out = np.zeros(v.size)
    order = np.argsort(key, kind="stable")
    k = key[order]
    starts = [0] + (np.flatnonzero(k[1:] != k[:-1]) + 1).tolist()
    stops = starts[1:] + [k.size]
    for a, b in zip(starts, stops):
        idx = order[a:b]
        r = np.argsort(np.argsort(v[idx], kind="stable"), kind="stable")
        out[idx] = (r + 0.5) / max(idx.size, 1)
    return out


def grades(v):
    g = np.zeros(v.size, dtype=np.int32)
    for e in GRADE_EDGES:
        g += (v >= e).astype(np.int32)
    g[v <= 0] = 0
    return np.clip(g, 0, 4)


def _group_arrays(D, rows, klass, unit="class"):
    """Rows sorted by group + the xgboost group-size vector."""
    r = np.asarray(rows, dtype=np.int64)
    key = RK.group_key(D, r, klass, unit)
    order = np.lexsort((D["dec_sec"][r], key))
    ro, ko = r[order], key[order]
    _u, cnt = np.unique(ko, return_counts=True)
    return ro, cnt


def run(test_eras=SC.TEST_ERAS, tag="LMART_M3FEATURES", unit="class",
        shuffle=False, drop_tf=False, from_era="E2", compose=False,
        emb=None, n_pc=64):
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
    cols = list(range(len(D["names"])))
    if drop_tf:
        # THE ABLATION: the 18 teacher-evidence columns the matrix gained
        # mid-session, struck out, so the arm runs on the ORIGINAL 184.
        cols = [i for i, n in enumerate(D["names"])
                if not str(n).startswith("tf_")]
        SC.hb("drop_tf: %d -> %d feature columns" % (len(D["names"]),
                                                     len(cols)))
    XF = D["X"][:, cols]
    FN = [str(D["names"][i]) for i in cols]
    if emb:
        # THE LANE'S HEADLINE QUESTION, RE-ASKED ON THE ARM THAT WORKS: does the
        # frozen raw-event representation add anything on top of the features,
        # under the correct grouping and the correct schedule?
        # The PCA basis is fitted ONLY on rows strictly earlier than the first
        # evaluation era, so it is causal for every fold at once.
        import st_pretrain as PT
        E = np.asarray(PT.embed_all(emb)).astype(np.float32)
        pos = PT.load_ft()["pos"]
        fit = np.nonzero((D["era_idx"] < SC.ERA_IDX["E3"]) & (pos >= 0))[0]
        fit = fit[::max(1, fit.size // 120000)]
        A = E[pos[fit]]
        mu = A.mean(0)
        U, S_, Vt = np.linalg.svd(A - mu, full_matrices=False)
        W = Vt[:n_pc].T
        SC.hb("emb PCA: basis on %d rows strictly before E3, %d -> %d comps "
              "(var kept %.3f)" % (fit.size, E.shape[1], n_pc,
                                   float((S_[:n_pc] ** 2).sum()
                                         / max((S_ ** 2).sum(), 1e-9))))
        P = np.full((D["d8"].size, n_pc), np.nan, dtype=np.float32)
        have = np.nonzero(pos >= 0)[0]
        for a0 in range(0, have.size, 200000):
            r = have[a0:a0 + 200000]
            P[r] = (E[pos[r]] - mu) @ W
        XF = np.hstack([XF, P])
        FN = FN + ["emb_pc%02d" % k for k in range(n_pc)]
        del E, P
    for era in test_eras:
        t0 = time.time()
        tr, ev = R.fold_rows(D, era, from_era=from_era)
        tr = tr[D["X"][tr, j] < 0.5]
        ev_r = ev[D["X"][ev, j] < 0.5]
        cut = SC.inner_split_days(D["d8"][tr])
        itr, iva = tr[D["d8"][tr] <= cut], tr[D["d8"][tr] > cut]
        SC.assert_disjoint_days(itr, iva, D["d8"], tag="%s inner" % era)
        yv = value
        if shuffle:
            # THE RED-FIRST CONTROL FOR THIS ARM: the grades are permuted
            # WITHIN the training block only.  A ranker that still scores must
            # be reading something other than the label.
            rs = np.random.RandomState(SC.SEED + SC.ERA_IDX[era])
            yv = value.copy()
            yv[tr] = value[tr][rs.permutation(tr.size)]
        r_itr, g_itr = _group_arrays(D, itr, klass, unit)
        r_iva, g_iva = _group_arrays(D, iva, klass, unit)
        dtr = xgb.DMatrix(XF[r_itr], label=grades(yv[r_itr]),
                          feature_names=FN)
        dtr.set_group(g_itr)
        dva = xgb.DMatrix(XF[r_iva], label=grades(yv[r_iva]),
                          feature_names=FN)
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
        r_tr, g_tr = _group_arrays(D, tr, klass, unit)
        dall = xgb.DMatrix(XF[r_tr], label=grades(yv[r_tr]),
                           feature_names=FN)
        dall.set_group(g_tr)
        b2 = xgb.train(cfg, dall, best_rounds)
        s = b2.predict(xgb.DMatrix(XF[ev_r], feature_names=FN))
        if compose:
            # THE FEASIBILITY GATE, m3_walk's COMPOSED construction verbatim:
            # the ranking head ORDERS, the walled-winner head says whether a
            # seat exists here at all.  Both are put on a common monotone scale
            # (within-CELL percentile) and summed.  This attacks SEL_WRONG_SIDE,
            # which the pure ranker made worse.
            yw = D["y_winner"]
            fw = tr[np.isfinite(yw[tr])]
            cfgw = {"objective": "reg:squarederror", "tree_method": "hist",
                    "subsample": 0.8, "seed": SC.SEED, "nthread": 8,
                    "max_depth": 4, "eta": 0.08, "min_child_weight": 20,
                    "colsample_bytree": 0.6}
            bw = xgb.train(cfgw, xgb.DMatrix(XF[fw], label=yw[fw],
                                             feature_names=FN), 60)
            w = bw.predict(xgb.DMatrix(XF[ev_r], feature_names=FN))
            key = RK.group_key(D, ev_r, klass, unit)
            s = _pct_within(s, key) + _pct_within(w, key)
        score[ev_r] = s
        g_ev = RK.build_groups(D, ev_r, klass, unit)
        nd, ng = RK.ndcg_at_k(score, value, g_ev, 3)
        rnd = np.random.RandomState(SC.SEED).rand(n)
        nd_rand, _ = RK.ndcg_at_k(rnd, value, g_ev, 3)
        nd_earl, _ = RK.ndcg_at_k(-D["dec_sec"].astype(np.float64), value,
                                  g_ev, 3)
        ledger.append({"era": era, "loss": "rank:ndcg", "inner_ndcg3": inner,
                       "best_epoch": best_rounds,
                       "loss_curve": [["rank:ndcg", round(inner, 5)]],
                       "n_groups_train": len(RK.build_groups(D, tr, klass, unit)),
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
    R.save_result(tag, {"kind": "rank", "group_unit": unit,
                        "arch": "lambdamart-%s" % unit,
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
    ap.add_argument("--unit", default="class",
                    choices=("class", "cell", "day"))
    ap.add_argument("--tag", default=None)
    ap.add_argument("--shuffle", action="store_true")
    ap.add_argument("--drop-tf", action="store_true")
    ap.add_argument("--from-era", default="E2")
    ap.add_argument("--compose", action="store_true")
    ap.add_argument("--emb", default=None)
    ap.add_argument("--n-pc", type=int, default=64)
    a = ap.parse_args()
    if a.run:
        run(test_eras=tuple(a.eras.split(",")), unit=a.unit, shuffle=a.shuffle,
            drop_tf=a.drop_tf, from_era=a.from_era, compose=a.compose,
            emb=a.emb, n_pc=a.n_pc,
            tag=a.tag or ("LMART_%s%s" % (a.unit.upper(),
                                          "_SHUFFLED" if a.shuffle else "")))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
