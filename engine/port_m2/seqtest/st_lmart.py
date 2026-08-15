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

# THE INNER-BLOCK HP GRID.  m3's own discipline is a small documented search on
# the FIT side only; this lane had been running a single fixed guess.  Selected
# by inner-validation NDCG@3 and nothing else; the evaluation era is never
# touched by the choice.
HP_GRID = tuple({"max_depth": d, "eta": e,
                 "lambdarank_num_pair_per_sample": p}
                for d in (4, 6, 8)
                for e in (0.05, 0.10)
                for p in (8, 16))


def _ndcg_metric(dollars_sorted, group_sizes):
    """NDCG@1 on the inner block for the custom objective — i.e. exactly the
    top-1-per-cell hit the deployment makes."""
    ptr = np.concatenate([[0], np.cumsum(np.asarray(group_sizes,
                                                    dtype=np.int64))])

    def m(preds, dvalid):
        p = np.asarray(preds, dtype=np.float64)
        num = den = 0.0
        for a, b in zip(ptr[:-1], ptr[1:]):
            if b - a < 2:
                continue
            v = np.maximum(dollars_sorted[a:b], 0.0)
            if v.sum() <= 0:
                continue
            num += float(v[int(np.argmax(p[a:b]))])
            den += float(v.max())
        return "ndcg@1", (num / den if den > 0 else 0.0)
    return m


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


_GRP = {}


def _softmax_top1_obj(dollars_sorted):
    """(h) THE DEPLOYMENT-EXACT OBJECTIVE.

    We deploy TOP-1 PER CELL but train NDCG@k, which spends gradient on ranks
    2..k that are never seated.  This is the objective the deployment actually
    implies: a MULTINOMIAL over each cell's members, target = the member that
    paid most.  Softmax cross-entropy per group, so
        grad_i = p_i - t_i ,  hess_i = p_i (1 - p_i)
    with p the within-cell softmax of the score.
    """
    def obj(preds, dtrain):
        g = np.asarray(dtrain.get_uint_info("group_ptr"), dtype=np.int64)
        p = np.asarray(preds, dtype=np.float64)
        grad = np.zeros_like(p)
        hess = np.zeros_like(p)
        for a, b in zip(g[:-1], g[1:]):
            if b - a < 2:
                continue
            z = p[a:b] - p[a:b].max()
            e = np.exp(z)
            pr = e / max(e.sum(), 1e-12)
            t = np.zeros(b - a)
            t[int(np.argmax(dollars_sorted[a:b]))] = 1.0
            grad[a:b] = pr - t
            hess[a:b] = np.maximum(pr * (1.0 - pr), 1e-6)
        return grad, hess
    return obj


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
        emb=None, n_pc=64, search=False, side_veto=False,
        side_soft=False, topk=3, policy_select=False,
        objective="ndcg"):
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
    lam_sel = {}
    pol_sel = {}
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
        base = {"objective": "rank:ndcg", "eval_metric": "ndcg@%d" % topk,
                "tree_method": "hist", "min_child_weight": 20,
                "subsample": 0.8, "colsample_bytree": 0.8,
                "lambdarank_pair_method": "topk",
                "lambdarank_normalization": True,
                "seed": SC.SEED, "nthread": 8}
        grid = HP_GRID if search else ({"max_depth": 6, "eta": 0.05,
                                        "lambdarank_num_pair_per_sample": 8},)
        obj_tr = obj_va = None
        if objective == "top1":
            base = {k2: v2 for k2, v2 in base.items()
                    if k2 not in ("objective",)}
            base["disable_default_eval_metric"] = 1
            obj_tr = _softmax_top1_obj(yv[r_itr])
        cfg, best_rounds, inner = None, ROUNDS, -np.inf
        for hp in grid:
            c = dict(base)
            c.update(hp)
            if objective == "top1":
                c.pop("lambdarank_num_pair_per_sample", None)
                c.pop("lambdarank_pair_method", None)
                c.pop("lambdarank_normalization", None)
                c.pop("eval_metric", None)
            bb = xgb.train(c, dtr, ROUNDS, evals=[(dva, "inner")],
                           early_stopping_rounds=EARLY, verbose_eval=False,
                           obj=obj_tr,
                           custom_metric=(_ndcg_metric(yv[r_iva], g_iva)
                                          if objective == "top1" else None))
            if float(bb.best_score) > inner:
                cfg = c
                best_rounds = int(bb.best_iteration) + 1
                inner = float(bb.best_score)
        SC.hb("%s %s: HP %s rounds=%d inner=%.5f"
              % (tag, era, {k: cfg.get(k) for k in
                            ("max_depth", "eta",
                             "lambdarank_num_pair_per_sample")},
                 best_rounds, inner))
        # refit on the WHOLE training block at the selected round count
        r_tr, g_tr = _group_arrays(D, tr, klass, unit)
        dall = xgb.DMatrix(XF[r_tr], label=grades(yv[r_tr]),
                           feature_names=FN)
        dall.set_group(g_tr)
        b2 = xgb.train(cfg, dall, best_rounds,
                       obj=(_softmax_top1_obj(yv[r_tr])
                            if objective == "top1" else None))
        s = b2.predict(xgb.DMatrix(XF[ev_r], feature_names=FN))
        if side_soft:
            # ITERATION 2 ON THE SIDE FRONT.  The hard veto lost because it
            # discards half the pool on a ~57% side signal.  This is the same
            # idea made SELF-LIMITING: the ranker's score is penalised by the
            # cell's side-margin, and the penalty strength lambda is chosen on
            # the INNER VALIDATION BLOCK from a grid that CONTAINS ZERO.  If the
            # side signal is worthless the inner block picks lambda=0 and the
            # arm reduces exactly to the champion, so this cannot cost anything
            # that inner selection can see.
            yw = D["y_winner"].astype(np.float64)
            if shuffle:
                rs2 = np.random.RandomState(SC.SEED + 977 + SC.ERA_IDX[era])
                yw = yw.copy()
                yw[tr] = yw[tr][rs2.permutation(tr.size)]
            fw = tr[np.isfinite(yw[tr])]
            cfgw = {"objective": "reg:squarederror", "tree_method": "hist",
                    "subsample": 0.8, "seed": SC.SEED, "nthread": 8,
                    "max_depth": 4, "eta": 0.08, "min_child_weight": 20,
                    "colsample_bytree": 0.6}
            bw = xgb.train(cfgw, xgb.DMatrix(XF[fw], label=yw[fw],
                                             feature_names=FN), 60)

            def _margins(rows_idx):
                ww = bw.predict(xgb.DMatrix(XF[rows_idx], feature_names=FN))
                kk2 = RK.group_key(D, rows_idx, klass, unit)
                sd2 = D["side"][rows_idx].astype(np.int64)
                out = np.zeros(rows_idx.size)
                o2 = np.argsort(kk2, kind="stable")
                k2 = kk2[o2]
                st2 = [0] + (np.flatnonzero(k2[1:] != k2[:-1]) + 1).tolist()
                sp2 = st2[1:] + [k2.size]
                for a1, b1 in zip(st2, sp2):
                    ix1 = o2[a1:b1]
                    sides = np.unique(sd2[ix1])
                    if sides.size < 2:
                        continue
                    m = {int(v): float(ww[ix1[sd2[ix1] == v]].mean())
                         for v in sides}
                    hi = max(m.values())
                    for v in sides:
                        out[ix1[sd2[ix1] == v]] = m[int(v)] - hi
                return out           # 0 on the favoured side, negative on the other

            # inner-block selection of lambda on REALISED $/session
            iva_rows = tr[D["d8"][tr] > cut]
            s_iva = b2.predict(xgb.DMatrix(XF[iva_rows], feature_names=FN))
            g_iva_m = _margins(iva_rows)
            rng_s = float(np.std(s_iva)) or 1.0
            best_lam, best_val = 0.0, -np.inf
            for lam in (0.0, 0.25, 0.5, 1.0, 2.0, 4.0):
                sc_try = np.full(D["d8"].size, np.nan)
                sc_try[iva_rows] = s_iva + lam * rng_s * g_iva_m
                aa = R.score_arm(D, sc_try, iva_rows, ceil, unit="cell", n=1)
                v = aa["usd_per_session"] or -np.inf
                if v > best_val:
                    best_lam, best_val = lam, v
            SC.hb("%s %s side-soft: lambda=%.2f chosen on inner block "
                  "($%.2f/session there)" % (tag, era, best_lam, best_val))
            s = s + best_lam * rng_s * _margins(ev_r)
            lam_sel[era] = best_lam
        if side_veto:
            # THE SIDE FRONT, as a VETO on the candidate POOL — never as a
            # re-ranking.  Iteration 3 failed by SUMMING the winner head into
            # the ordering; here the ranker's ordering is left completely
            # untouched and the winner head only decides WHICH SIDE of a cell is
            # eligible.  Per (asset, day, phase) cell: mean predicted
            # walled-winner probability per side, keep the better side, drop the
            # other.  Causal — the head is fitted on the training block only.
            # CONTROL CORRECTNESS (defect found 2026-08-17): in the shuffled
            # arm this head must ALSO see permuted labels, or the "control"
            # keeps a real side gate.  Observed symptom: identical drop counts
            # in the real and shuffled runs.
            yw = D["y_winner"].astype(np.float64)
            if shuffle:
                rs2 = np.random.RandomState(SC.SEED + 977 + SC.ERA_IDX[era])
                yw = yw.copy()
                yw[tr] = yw[tr][rs2.permutation(tr.size)]
            fw = tr[np.isfinite(yw[tr])]
            cfgw = {"objective": "reg:squarederror", "tree_method": "hist",
                    "subsample": 0.8, "seed": SC.SEED, "nthread": 8,
                    "max_depth": 4, "eta": 0.08, "min_child_weight": 20,
                    "colsample_bytree": 0.6}
            bw = xgb.train(cfgw, xgb.DMatrix(XF[fw], label=yw[fw],
                                             feature_names=FN), 60)
            w = bw.predict(xgb.DMatrix(XF[ev_r], feature_names=FN))
            key = RK.group_key(D, ev_r, klass, unit)
            sd = D["side"][ev_r].astype(np.int64)
            order = np.argsort(key, kind="stable")
            kk = key[order]
            starts = [0] + (np.flatnonzero(kk[1:] != kk[:-1]) + 1).tolist()
            stops = starts[1:] + [kk.size]
            n_drop = 0
            for a0, b0 in zip(starts, stops):
                idx = order[a0:b0]
                sides = np.unique(sd[idx])
                if sides.size < 2:
                    continue
                means = {int(v): float(w[idx[sd[idx] == v]].mean())
                         for v in sides}
                keep_side = max(means, key=means.get)
                bad = idx[sd[idx] != keep_side]
                s[bad] = -np.inf
                n_drop += int(bad.size)
            SC.hb("%s %s side-veto: %d/%d candidates dropped (%.1f%%)"
                  % (tag, era, n_drop, ev_r.size,
                     100.0 * n_drop / max(ev_r.size, 1)))
        if compose:
            # THE FEASIBILITY GATE, m3_walk's COMPOSED construction verbatim:
            # the ranking head ORDERS, the walled-winner head says whether a
            # seat exists here at all.  Both are put on a common monotone scale
            # (within-CELL percentile) and summed.  This attacks SEL_WRONG_SIDE,
            # which the pure ranker made worse.
            # CONTROL CORRECTNESS (defect found 2026-08-17): in the shuffled
            # arm this head must ALSO see permuted labels, or the "control"
            # keeps a real side gate.  Observed symptom: identical drop counts
            # in the real and shuffled runs.
            yw = D["y_winner"].astype(np.float64)
            if shuffle:
                rs2 = np.random.RandomState(SC.SEED + 977 + SC.ERA_IDX[era])
                yw = yw.copy()
                yw[tr] = yw[tr][rs2.permutation(tr.size)]
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
        if policy_select:
            # PER-ERA POLICY REFINEMENT, chosen on the INNER VALIDATION BLOCK
            # with THIS arm's own scores.  The champion inherited m3's committed
            # (unit, N), which was selected for m3's POINTWISE scores — a
            # different ordering with a different concentration.  Nothing here
            # ever sees an evaluation era.
            iva_rows = tr[D["d8"][tr] > cut]
            s_iva = np.full(D["d8"].size, np.nan)
            s_iva[iva_rows] = b2.predict(xgb.DMatrix(XF[iva_rows],
                                                     feature_names=FN))
            best_p, best_v = ("cell", 1), -np.inf
            curve = []
            for u2 in ("session", "cell"):
                for n2 in (1, 2, 3, 5, 8):
                    aa = R.score_arm(D, s_iva, iva_rows, ceil, unit=u2, n=n2)
                    v = aa["usd_per_session"] or -np.inf
                    curve.append([u2, n2, round(float(v), 2)])
                    if v > best_v:
                        best_p, best_v = (u2, n2), v
            pol_sel[era] = list(best_p)
            SC.hb("%s %s policy-select: %s/%d on inner block ($%.2f/session "
                  "there)" % (tag, era, best_p[0], best_p[1], best_v))
        score[ev_r] = s
        g_ev = RK.build_groups(D, ev_r, klass, unit)
        nd, ng = RK.ndcg_at_k(score, value, g_ev, 3)
        rnd = np.random.RandomState(SC.SEED).rand(n)
        nd_rand, _ = RK.ndcg_at_k(rnd, value, g_ev, 3)
        nd_earl, _ = RK.ndcg_at_k(-D["dec_sec"].astype(np.float64), value,
                                  g_ev, 3)
        ledger.append({"era": era, "loss": "rank:ndcg@%d" % topk, "inner_ndcg3": inner,
                       "best_epoch": best_rounds,
                       "loss_curve": [["rank:ndcg", round(inner, 5)]],
                       "n_groups_train": len(RK.build_groups(D, tr, klass, unit)),
                       "n_groups_eval": len(g_ev),
                       "median_group": int(np.median([g.size for g in g_ev]))
                       if g_ev else 0,
                       "eval_ndcg3": nd, "eval_ndcg3_random": nd_rand,
                       "eval_ndcg3_earliest": nd_earl, "n_scored_groups": ng,
                       "n_eval": int(ev_r.size),
                       "side_lambda": lam_sel.get(era),
                       "policy_selected": pol_sel.get(era),
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
    if pol_sel:
        with open(os.path.join(R.SCORE_DIR, "%s.policy.json" % tag), "w") as fh:
            json.dump({k: list(v) for k, v in pol_sel.items()}, fh, indent=1)
        SC.hb("%s: inner-selected policy %s" % (tag, pol_sel))
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
    ap.add_argument("--search", action="store_true")
    ap.add_argument("--side-veto", action="store_true")
    ap.add_argument("--side-soft", action="store_true")
    ap.add_argument("--topk", type=int, default=3)
    ap.add_argument("--policy-select", action="store_true")
    ap.add_argument("--objective", default="ndcg", choices=("ndcg", "top1"))
    a = ap.parse_args()
    if a.run:
        run(test_eras=tuple(a.eras.split(",")), unit=a.unit, shuffle=a.shuffle,
            drop_tf=a.drop_tf, from_era=a.from_era, compose=a.compose,
            emb=a.emb, n_pc=a.n_pc, search=a.search,
            side_veto=a.side_veto, side_soft=a.side_soft, topk=a.topk,
            policy_select=a.policy_select, objective=a.objective,
            tag=a.tag or ("LMART_%s%s" % (a.unit.upper(),
                                          "_SHUFFLED" if a.shuffle else "")))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
