#!/usr/bin/python3
"""PORT M2 SEQTEST — LAMBDAMART SIBLINGS (menu items f/g/i).

Same folds, same cell grouping, same grades, same schedule, same controls as the
champion — only the LEARNING ENGINE changes, so each is one change:

  `catboost`  YetiRank / StochasticRank with ORDERED BOOSTING.  Ordered
              boosting is the small-data target-leakage protection, and the weak
              early eras are exactly where that should pay if anything does.
  `lightgbm`  `lambdarank`, the leaf-wise engine, on identical folds.

Both take the champion's own per-era hyper-parameter DEPTH/LR where the engine
has an equivalent, and their own iteration count is chosen by early stopping on
the training block's inner validation split — never on the evaluation era.

Run:
  st_engines.py --run --engine catboost --loss YetiRank --tag F_CATB_YETI
  st_engines.py --run --engine lightgbm --tag G_LGBM
"""
import argparse
import os
import time

import numpy as np

import st_common as SC
import st_run as R
import st_rank as RK
import st_lmart as LM

ERAS = ("E3", "E4", "E5", "E6", "E7")
ROUNDS = 400
EARLY = 30


def _cols(D):
    return [i for i, n in enumerate(D["names"])
            if not str(n).startswith("tf_")]


def _blocks(group_sizes):
    ptr = np.concatenate([[0], np.cumsum(np.asarray(group_sizes, np.int64))])
    return ptr


def run(engine="catboost", loss="YetiRank", tag=None, eras=ERAS,
        shuffle=False, depth=6, lr=0.05):
    import m3_walk as W
    tag = tag or ("ENG_%s%s" % (engine.upper(), "_SHUF" if shuffle else ""))
    D, _p = W.load_matrix()
    klass, _ = RK.class_index(D)
    cols = _cols(D)
    XF = D["X"][:, cols]
    FN = [str(D["names"][i]) for i in cols]
    j = D["names"].index("in_news_window")
    n = D["d8"].size
    score = np.full(n, np.nan)
    ledger = []
    for era in eras:
        t0 = time.time()
        tr, ev = R.fold_rows(D, era, from_era="PRE_E1")
        tr = tr[D["X"][tr, j] < 0.5]
        ev_r = ev[D["X"][ev, j] < 0.5]
        cut = SC.inner_split_days(D["d8"][tr])
        itr, iva = tr[D["d8"][tr] <= cut], tr[D["d8"][tr] > cut]
        SC.assert_disjoint_days(itr, iva, D["d8"], tag="%s %s" % (tag, era))
        v = D["cert_close_usd"].astype(np.float64)
        if shuffle:
            rs = np.random.RandomState(SC.SEED + SC.ERA_IDX[era])
            v = v.copy()
            v[tr] = v[tr][rs.permutation(tr.size)]
        r_itr, g_itr = LM._group_arrays(D, itr, klass, "cell")
        r_iva, g_iva = LM._group_arrays(D, iva, klass, "cell")
        r_tr, g_tr = LM._group_arrays(D, tr, klass, "cell")
        y_itr, y_iva, y_tr = (LM.grades(v[r_itr]), LM.grades(v[r_iva]),
                              LM.grades(v[r_tr]))
        if engine == "catboost":
            from catboost import CatBoost, Pool
            gid_i = np.repeat(np.arange(len(g_itr)), g_itr)
            gid_v = np.repeat(np.arange(len(g_iva)), g_iva)
            gid_t = np.repeat(np.arange(len(g_tr)), g_tr)
            ptr = Pool(XF[r_itr], label=y_itr, group_id=gid_i,
                       feature_names=FN)
            pva = Pool(XF[r_iva], label=y_iva, group_id=gid_v,
                       feature_names=FN)
            params = {"loss_function": loss, "iterations": ROUNDS,
                      "depth": depth, "learning_rate": lr,
                      "random_seed": SC.SEED, "verbose": False,
                      "boosting_type": "Ordered",
                      "od_type": "Iter", "od_wait": EARLY,
                      "thread_count": 8, "allow_writing_files": False}
            m = CatBoost(params)
            m.fit(ptr, eval_set=pva, use_best_model=True)
            best = int(m.get_best_iteration() or ROUNDS)
            params2 = dict(params)
            params2["iterations"] = max(best, 1)
            params2.pop("od_type", None)
            params2.pop("od_wait", None)
            m2 = CatBoost(params2)
            m2.fit(Pool(XF[r_tr], label=y_tr, group_id=gid_t,
                        feature_names=FN))
            s = m2.predict(Pool(XF[ev_r], group_id=np.repeat(
                np.arange(len(LM._group_arrays(D, ev_r, klass, "cell")[1])),
                LM._group_arrays(D, ev_r, klass, "cell")[1]),
                feature_names=FN))
            r_ev, _g_ev = LM._group_arrays(D, ev_r, klass, "cell")
            score[r_ev] = s
        else:
            import lightgbm as lgb
            dtr = lgb.Dataset(XF[r_itr], label=y_itr, group=g_itr,
                              feature_name=FN, free_raw_data=False)
            dva = lgb.Dataset(XF[r_iva], label=y_iva, group=g_iva,
                              feature_name=FN, reference=dtr,
                              free_raw_data=False)
            params = {"objective": "lambdarank", "metric": "ndcg",
                      "ndcg_eval_at": [1, 3], "learning_rate": lr,
                      "num_leaves": 2 ** depth, "min_data_in_leaf": 20,
                      "feature_fraction": 0.8, "bagging_fraction": 0.8,
                      "bagging_freq": 1, "seed": SC.SEED, "num_threads": 8,
                      "verbosity": -1}
            b = lgb.train(params, dtr, ROUNDS, valid_sets=[dva],
                          callbacks=[lgb.early_stopping(EARLY, verbose=False)])
            best = int(b.best_iteration or ROUNDS)
            dall = lgb.Dataset(XF[r_tr], label=y_tr, group=g_tr,
                               feature_name=FN, free_raw_data=False)
            b2 = lgb.train(params, dall, best)
            r_ev, _g = LM._group_arrays(D, ev_r, klass, "cell")
            score[r_ev] = b2.predict(XF[r_ev])
        ledger.append({"era": era, "engine": engine, "loss": loss,
                       "best_iteration": best, "n_eval": int(ev_r.size),
                       "n_groups_train": len(g_tr),
                       "secs": round(time.time() - t0, 1)})
        SC.hb("%s %s: %s/%s best_iter=%d (%.0fs)"
              % (tag, era, engine, loss, best, time.time() - t0))
    np.savez(os.path.join(R._sdir(), "%s.npz" % tag), champ=score, win=score)
    R.save_result(tag, {"kind": "rank", "group_unit": "cell",
                        "arch": "%s-%s" % (engine, loss), "rung": "engine",
                        "L": 0, "trunk": engine, "mode": "ctx",
                        "pretrained": False, "per_era": [], "pooled": {},
                        "ledger": ledger, "gpu": R.gpu_note()})
    SC.hb("%s done" % tag)
    return tag


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--engine", default="catboost",
                    choices=("catboost", "lightgbm"))
    ap.add_argument("--loss", default="YetiRank")
    ap.add_argument("--tag", default=None)
    ap.add_argument("--eras", default=",".join(ERAS))
    ap.add_argument("--shuffle", action="store_true")
    ap.add_argument("--depth", type=int, default=6)
    ap.add_argument("--lr", type=float, default=0.05)
    a = ap.parse_args()
    if a.run:
        run(engine=a.engine, loss=a.loss, tag=a.tag,
            eras=tuple(a.eras.split(",")), shuffle=a.shuffle, depth=a.depth,
            lr=a.lr)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
