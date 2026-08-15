#!/usr/bin/python3
"""PORT M2 SEQTEST — THE STACKER and THE META-LABELLING GATE.

Two user-directed arms on the champion's exact protocol (cell grouping, m3's
committed per-era policy, D-077 veto, phase-close replay, day-clustered CR1,
E8 quarantined — folds are E3..E7 only).

STACKER (`--stack`).  Independent-judge ensembling. The champion ranks well
INSIDE a cell but is near-flat globally (AUC 0.521); TabPFN is the best global
winner-classifier this program has produced (AUC 0.687) but its within-cell
ordering is anti-correlated with dollars. Blending them is the natural move:
each component is rank-normalised WITHIN the cell it will be seated in, then
combined as `(1-w)*champion + w*component`, with **w chosen on the inner
validation block by realised $/session from a grid that CONTAINS ZERO** — so if
the component is useless the inner block returns the champion untouched.

META-LABELLING GATE (`--meta`).  A secondary judge on the champion's OWN picks:
for every take the champion would have made on the training block, the label is
"did this pick pay", the features are the 184 plus the champion's own score and
its margin over the runner-up in that cell. On evaluation the gate vetoes takes
whose predicted pay-probability is below a threshold swept on the inner block.
It targets PARTICIPATION and the precision lines rather than the ordering.

The champion's per-era hyper-parameters are the ones its own inner-block search
already selected (CHAMPION_FREEZE_CANDIDATE.md §2.5) — re-used, never re-searched.

Run:
  st_stack.py --stack --component FM_TABPFN_WINNER --tag STK_TABPFN
  st_stack.py --meta --tag META_GATE
"""
import argparse
import json
import os
import time

import numpy as np

import st_common as SC
import st_run as R
import st_rank as RK
import st_lmart as LM
import m3_common as M3
import panel_score as PS

ERAS = ("E3", "E4", "E5", "E6", "E7")

# The champion's OWN inner-selected per-era HP (freeze candidate S2.5) — reused
# rather than re-searched, so the stacker is one change and not two.
CHAMP_HP = {
    "E3": dict(max_depth=4, eta=0.10, lambdarank_num_pair_per_sample=8, rounds=74),
    "E4": dict(max_depth=4, eta=0.05, lambdarank_num_pair_per_sample=8, rounds=178),
    "E5": dict(max_depth=4, eta=0.10, lambdarank_num_pair_per_sample=16, rounds=138),
    "E6": dict(max_depth=6, eta=0.05, lambdarank_num_pair_per_sample=16, rounds=82),
    "E7": dict(max_depth=6, eta=0.05, lambdarank_num_pair_per_sample=16, rounds=107),
}
W_GRID = (0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0)
TAU_GRID = (0.0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50)


def _cols(D):
    return [i for i, n in enumerate(D["names"])
            if not str(n).startswith("tf_")]


def _fit_champion(D, XF, FN, tr, era, klass, shuffle=False):
    """The champion ranker for one fold, at its own committed HP."""
    import xgboost as xgb
    hp = CHAMP_HP[era]
    v = D["cert_close_usd"].astype(np.float64)
    if shuffle:
        rs = np.random.RandomState(SC.SEED + SC.ERA_IDX[era])
        v = v.copy()
        v[tr] = v[tr][rs.permutation(tr.size)]
    r_tr, g_tr = LM._group_arrays(D, tr, klass, "cell")
    d = xgb.DMatrix(XF[r_tr], label=LM.grades(v[r_tr]), feature_names=FN)
    d.set_group(g_tr)
    cfg = {"objective": "rank:ndcg", "eval_metric": "ndcg@3",
           "tree_method": "hist", "min_child_weight": 20, "subsample": 0.8,
           "colsample_bytree": 0.8, "lambdarank_pair_method": "topk",
           "seed": SC.SEED, "nthread": 8,
           "max_depth": hp["max_depth"], "eta": hp["eta"],
           "lambdarank_num_pair_per_sample":
               hp["lambdarank_num_pair_per_sample"]}
    return xgb.train(cfg, d, hp["rounds"])


def _cellrank(D, s, rows, klass):
    """Within-CELL rank in [0,1] — the only scale on which two judges with
    different units can be added, because the cell is what gets seated."""
    key = RK.group_key(D, rows, klass, "cell")
    out = np.zeros(rows.size)
    order = np.argsort(key, kind="stable")
    k = key[order]
    st = [0] + (np.flatnonzero(k[1:] != k[:-1]) + 1).tolist()
    sp = st[1:] + [k.size]
    for a, b in zip(st, sp):
        ix = order[a:b]
        r = np.argsort(np.argsort(s[ix], kind="stable"), kind="stable")
        out[ix] = (r + 0.5) / max(ix.size, 1)
    return out


def stack(component, tag=None, eras=ERAS, shuffle=False):
    import xgboost as xgb
    import m3_walk as W
    tag = tag or ("STK_%s%s" % (component, "_SHUF" if shuffle else ""))
    D, _p = W.load_matrix()
    ceil = R.ceilings_of(D)
    klass, _ = RK.class_index(D)
    cols = _cols(D)
    XF = D["X"][:, cols]
    FN = [str(D["names"][i]) for i in cols]
    comp_all = np.load(os.path.join(R.SCORE_DIR, "%s.npz" % component))["champ"]
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
        # the component only exists on evaluation eras, so w is selected on the
        # inner block using a champion fitted WITHOUT those days
        b_in = _fit_champion(D, XF, FN, itr, era, klass, shuffle)
        s_iva = b_in.predict(xgb.DMatrix(XF[iva], feature_names=FN))
        c_iva = comp_all[iva]
        if not np.isfinite(c_iva).any():
            best_w, best_v, curve = 0.0, None, []
            SC.hb("%s %s: component undefined on the inner block -> w=0 "
                  "(champion untouched)" % (tag, era))
        else:
            ch_r = _cellrank(D, s_iva, iva, klass)
            co_r = _cellrank(D, np.nan_to_num(c_iva), iva, klass)
            best_w, best_v, curve = 0.0, -np.inf, []
            for w in W_GRID:
                sc = np.full(n, np.nan)
                sc[iva] = (1.0 - w) * ch_r + w * co_r
                aa = R.score_arm(D, sc, iva, ceil, unit="cell", n=1)
                v = aa["usd_per_session"] or -np.inf
                curve.append([w, round(float(v), 2)])
                if v > best_v:
                    best_w, best_v = w, v
            SC.hb("%s %s: w=%.2f on inner block ($%.2f/session there) %s"
                  % (tag, era, best_w, best_v, curve))
        b_full = _fit_champion(D, XF, FN, tr, era, klass, shuffle)
        s_ev = b_full.predict(xgb.DMatrix(XF[ev_r], feature_names=FN))
        ch_r = _cellrank(D, s_ev, ev_r, klass)
        if best_w > 0:
            co_r = _cellrank(D, np.nan_to_num(comp_all[ev_r]), ev_r, klass)
            score[ev_r] = (1.0 - best_w) * ch_r + best_w * co_r
        else:
            score[ev_r] = ch_r
        ledger.append({"era": era, "w": best_w, "inner_usd": best_v,
                       "w_curve": curve, "n_eval": int(ev_r.size),
                       "secs": round(time.time() - t0, 1)})
    np.savez(os.path.join(R._sdir(), "%s.npz" % tag), champ=score, win=score)
    R.save_result(tag, {"kind": "rank", "group_unit": "cell",
                        "arch": "stacker-%s" % component, "rung": "blend",
                        "L": 0, "trunk": component, "mode": "ctx",
                        "pretrained": False, "per_era": [], "pooled": {},
                        "ledger": ledger, "gpu": R.gpu_note()})
    SC.hb("%s done" % tag)
    return tag


def meta(tag=None, eras=ERAS, shuffle=False, pay=600.0):
    """META-LABELLING: a second judge on the champion's own picks."""
    import xgboost as xgb
    import m3_walk as W
    tag = tag or ("META_GATE%s" % ("_SHUF" if shuffle else ""))
    D, _p = W.load_matrix()
    ceil = R.ceilings_of(D)
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
        b_in = _fit_champion(D, XF, FN, itr, era, klass, shuffle)

        def picks_and_meta(rows, booster):
            s = booster.predict(xgb.DMatrix(XF[rows], feature_names=FN))
            sc = np.full(n, np.nan)
            sc[rows] = s
            take = W.topn_takes(D, sc, rows, 1, deployable=True, unit="cell")
            # the champion's own score and its MARGIN over the cell runner-up
            key = RK.group_key(D, rows, klass, "cell")
            marg = {}
            order = np.argsort(key, kind="stable")
            k2 = key[order]
            st = [0] + (np.flatnonzero(k2[1:] != k2[:-1]) + 1).tolist()
            sp = st[1:] + [k2.size]
            for a, b in zip(st, sp):
                ix = rows[order[a:b]]
                v = sc[ix]
                o = np.argsort(-v, kind="stable")
                if o.size >= 2:
                    marg[int(ix[o[0]])] = float(v[o[0]] - v[o[1]])
                elif o.size == 1:
                    marg[int(ix[o[0]])] = 0.0
            M = np.column_stack([
                XF[take],
                sc[take],
                np.array([marg.get(int(i), 0.0) for i in take]),
                D["dec_sec"][take].astype(np.float64),
                D["phase_dec"][take].astype(np.float64)])
            return take, M

        tk_tr, M_tr = picks_and_meta(itr, b_in)
        y_pay = (D["cert_close_usd"][tk_tr] >= pay).astype(int)
        if shuffle:
            rs = np.random.RandomState(SC.SEED + 31 + SC.ERA_IDX[era])
            y_pay = y_pay[rs.permutation(y_pay.size)]
        # prefixed: `dec_sec` already exists in the 184 and xgboost refuses
        # duplicate feature names
        mfn = FN + ["meta_champ_score", "meta_champ_margin", "meta_dec_sec",
                    "meta_phase"]
        gate = xgb.train({"objective": "binary:logistic", "tree_method": "hist",
                          "max_depth": 4, "eta": 0.05, "min_child_weight": 20,
                          "subsample": 0.8, "colsample_bytree": 0.8,
                          "seed": SC.SEED, "nthread": 8},
                         xgb.DMatrix(M_tr, label=y_pay, feature_names=mfn), 200)
        # sweep the veto threshold on the INNER VALIDATION block
        tk_iv, M_iv = picks_and_meta(iva, b_in)
        p_iv = gate.predict(xgb.DMatrix(M_iv, feature_names=mfn))
        s_iv = np.full(n, np.nan)
        s_iv[tk_iv] = p_iv
        best_tau, best_v, curve = 0.0, -np.inf, []
        for tau in TAU_GRID:
            keep = tk_iv[p_iv >= tau]
            rows_r = W.replay_rows(D, keep)
            y = [r["realised"] for r in rows_r]
            cl = [int(r["session"].split("|")[1]) for r in rows_r]
            # the fair comparison is $/session over the SAME session set the
            # champion was responsible for, so a veto that skips a day is
            # charged $0 for it rather than silently dropping it
            allsess = np.unique(D["session"][iva]).size
            v = (sum(y) / allsess) if allsess else -np.inf
            curve.append([tau, round(float(v), 2), len(keep)])
            if v > best_v:
                best_tau, best_v = tau, v
        SC.hb("%s %s: tau=%.2f on inner block ($%.2f/session there) %s"
              % (tag, era, best_tau, best_v, curve))
        b_full = _fit_champion(D, XF, FN, tr, era, klass, shuffle)
        tk_ev, M_ev = picks_and_meta(ev_r, b_full)
        p_ev = gate.predict(xgb.DMatrix(M_ev, feature_names=mfn))
        s_ev = b_full.predict(xgb.DMatrix(XF[ev_r], feature_names=FN))
        base = np.full(n, np.nan)
        base[ev_r] = s_ev
        # the gate is a VETO: a vetoed pick is removed from the pool entirely,
        # so the cell simply goes unseated (that is the participation cost)
        keep = set(tk_ev[p_ev >= best_tau].tolist())
        drop = [int(i) for i in tk_ev.tolist() if i not in keep]
        if drop:
            base[np.asarray(drop, dtype=np.int64)] = -np.inf
        score[ev_r] = base[ev_r]
        ledger.append({"era": era, "tau": best_tau, "inner_usd": best_v,
                       "tau_curve": curve, "n_picks": int(tk_ev.size),
                       "n_vetoed": len(drop),
                       "secs": round(time.time() - t0, 1)})
    np.savez(os.path.join(R._sdir(), "%s.npz" % tag), champ=score, win=score)
    R.save_result(tag, {"kind": "rank", "group_unit": "cell",
                        "arch": "meta-label-gate", "rung": "gate", "L": 0,
                        "trunk": "champion", "mode": "ctx", "pretrained": False,
                        "per_era": [], "pooled": {}, "ledger": ledger,
                        "gpu": R.gpu_note()})
    SC.hb("%s done" % tag)
    return tag


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stack", action="store_true")
    ap.add_argument("--meta", action="store_true")
    ap.add_argument("--component", default="FM_TABPFN_WINNER")
    ap.add_argument("--tag", default=None)
    ap.add_argument("--eras", default=",".join(ERAS))
    ap.add_argument("--shuffle", action="store_true")
    a = ap.parse_args()
    eras = tuple(a.eras.split(","))
    if a.stack:
        stack(a.component, tag=a.tag, eras=eras, shuffle=a.shuffle)
    elif a.meta:
        meta(tag=a.tag, eras=eras, shuffle=a.shuffle)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
