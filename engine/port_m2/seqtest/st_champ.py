#!/usr/bin/python3
"""PORT M2 FIXPASS2 — F5: THE CHAMPION UPGRADES.

The reigning champion is the pointwise GBT on the committed 202-feature m3
matrix (pooled capture_oracle 0.0322 [0.0229, 0.0416]).  The ruling authorises
two upgrades to it, both independent of the deep stack:

 (a) THE 26 CREATOR FEATURES.  `CREATOR_MECHANICS_CENSUS.md` §6.1 declares the
     21 entry survivors + 5 veto survivors matrix-ready ("winner concentrators
     — that is the only claim attached to them").  They are added to the matrix
     as 26 extra columns and the GBT walk-forward is re-run.

 (b) THE D-021 MAE-CAP LABEL VARIANT.  §5(a): the creator's central execution
     claim — winners go 18 ticks against you first — replicates on our data
     (uncapped median 9 ticks, **q75 exactly 18**), and D-021's own MAE <= $300
     cap is *selecting those winners away*.  The variant caps at the measured
     18-tick dip instead: SI/NKD 18 x $25 = $450, HG 18 x $12.50 = $225.  It is
     an ALTERNATIVE TARGET COLUMN, never a contract change (D-029): the dollars
     that score every arm are the same replayed certificate dollars.

Everything else is the SEQTEST schedule verbatim — same folds (train E2..Ek ->
test E(k+1)), m3's own committed per-era hyper-parameters (no new search
anywhere), `m3_walk`'s deployable arm for the scoring, CIs clustered by DAY.

Run:
    st_champ.py --grid
"""
import argparse
import json
import os
import time

import numpy as np

import st_common as SC
import st_creator as CR
import st_run as R
import m2_common as MC
import m3_common as M3
import m3_walk as W

DIP_TICKS = 18.0                     # the census's measured q75 adverse dip
D021_MAE_USD = 300.0                 # the committed cap this variant replaces
D021_WIN_USD = 1000.0


def maecap_usd():
    """18 ticks in dollars, per asset (`common.ASSETS[a]['tick_usd']`)."""
    import common as C
    return np.array([DIP_TICKS * float(C.ASSETS[a]["tick_usd"])
                     for a in MC.ASSET_ORDER], dtype=np.float64)


def label_variant(D, kind="d021"):
    """`y_winner` (D-021 verbatim) or its MAE-cap variant, on the same rows."""
    cc = D["cert_close_usd"].astype(np.float64)
    mae = D["mae_before_argmax"].astype(np.float64)
    walled = D["walled"].astype(np.float64)
    ref = D["cert_refused"].astype(np.float64)
    if kind == "d021":
        cap = np.full(cc.size, D021_MAE_USD)
    else:
        cap = maecap_usd()[D["asset_idx"].astype(np.int64)]
    y = ((cc >= D021_WIN_USD) & (mae <= cap) & (walled == 0)
         & (ref == 0)).astype(np.float64)
    return y, cap


def _hp(era, target):
    return R.committed_hp(era, target)


def run(use_creator=False, label="d021", tag=None, test_eras=SC.TEST_ERAS,
        shuffle=False, from_era="E2"):
    import xgboost as xgb
    D, _p = W.load_matrix()
    ceil = R.ceilings_of(D)
    n = D["d8"].size
    X = D["X"]
    names = list(D["names"])
    cov = np.ones(n, dtype=bool)
    if use_creator:
        A, cols, cov = CR.creator_columns(D)
        X = np.hstack([X, A])
        names = names + cols
    y_champ = D["y_retg_rank_phase"].astype(np.float64)
    y_win, cap = label_variant(D, label)
    y_d021 = D["y_winner"].astype(np.float64)
    name = tag or ("GBT%s%s%s%s" % ("_CRE26" if use_creator else "",
                                    "_MAECAP" if label != "d021" else "",
                                    "_ALLDATA" if from_era == "PRE_E1" else "",
                                    "_SHUFFLED" if shuffle else ""))
    champ = np.full(n, np.nan)
    win = np.full(n, np.nan)
    ledger = []
    for era in test_eras:
        t0 = time.time()
        tr, ev = R.fold_rows(D, era, from_era=from_era)
        info = {"era": era, "n_train": int(tr.size), "n_eval": int(ev.size),
                "n_features": int(X.shape[1])}
        for target, y0 in (("y_retg_rank_phase", y_champ),
                           ("winner", y_win)):
            cfg, rounds = _hp(era, "y_retg_rank_phase" if target ==
                              "y_retg_rank_phase" else "y_winner")
            y = y0
            if shuffle:
                # THE RED-FIRST CONTROL: the TRAINING block's labels are
                # permuted; every downstream number must be at chance.
                y = y0.copy()
                rs = np.random.RandomState(SC.SEED + SC.ERA_IDX[era])
                y[tr] = y0[tr][rs.permutation(tr.size)]
            f = tr[np.isfinite(y[tr])]
            b = xgb.train(cfg, xgb.DMatrix(X[f], label=y[f],
                                           feature_names=names), rounds)
            s = b.predict(xgb.DMatrix(X[ev], feature_names=names))
            if target == "y_retg_rank_phase":
                champ[ev] = s
            else:
                win[ev] = s
            if use_creator:
                g = b.get_score(importance_type="gain")
                tot = sum(g.values()) or 1.0
                info["gain_share_creator_%s" % target] = round(
                    sum(v for k, v in g.items() if k.startswith("cre_")) / tot,
                    5)
                top = sorted(((v / tot, k) for k, v in g.items()
                              if k.startswith("cre_")), reverse=True)[:5]
                info["top_creator_%s" % target] = [[k, round(v, 5)]
                                                   for v, k in top]
        info.update({"winner_rate_train": round(float(y_win[tr].mean()), 5),
                     "winner_n_train": int(y_win[tr].sum()),
                     "winner_rate_eval": round(float(y_win[ev].mean()), 5),
                     "winner_n_eval": int(y_win[ev].sum()),
                     "auc_winner_vs_label": round(R.auc(y_win[ev], win[ev]), 4),
                     "auc_winner_vs_d021": round(R.auc(y_d021[ev], win[ev]), 4),
                     "fit_secs": round(time.time() - t0, 1)})
        ledger.append(info)
        SC.hb("CHAMP %s %s: auc(label)=%.4f auc(D021)=%.4f (%.0fs)"
              % (name, era, info["auc_winner_vs_label"],
                 info["auc_winner_vs_d021"], info["fit_secs"]))
    pos = np.zeros(n, dtype=np.int64)          # every matrix row is scoreable
    per, pool = R.eval_scores(D, champ, win, ceil, pos, test_eras=test_eras)
    R.save_result(name, {
        "kind": "champion", "shuffled": bool(shuffle), "from_era": from_era, "arch": "gbt-m3features%s" % ("+creator26"
                                                          if use_creator else ""),
        "rung": "gbt", "L": 0, "label": label, "use_creator": bool(use_creator),
        "n_features": int(X.shape[1]),
        "creator_coverage": round(float(cov.mean()), 5),
        "label_winner_n": int(y_win.sum()),
        "label_winner_rate": round(float(y_win.mean()), 6),
        "d021_winner_n": int(y_d021.sum()),
        "d021_winner_rate": round(float(y_d021.mean()), 6),
        "mae_cap_usd": {a: float(maecap_usd()[i]) if label != "d021"
                        else D021_MAE_USD for i, a in enumerate(MC.ASSET_ORDER)},
        "per_era": [R._strip(a) for a in per], "pooled": pool,
        "ledger": ledger, "gpu": {"device": "cpu/xgboost"}})
    np.savez(os.path.join(R._sdir(), "%s.npz" % name), champ=champ, win=win)
    SC.hb("%s pooled capture_oracle=%.4f [%.4f,%.4f] $%.2f/session"
          % (name, pool["capture_oracle"] or float("nan"),
             pool["co_lo"] or float("nan"), pool["co_hi"] or float("nan"),
             pool["usd_per_session"] or float("nan")))
    return pool


def label_stats():
    """The winner-set arithmetic the ruling asks for, on its own."""
    D, _p = W.load_matrix()
    out = {}
    for kind in ("d021", "maecap"):
        y, cap = label_variant(D, kind)
        m = np.isin(D["era_idx"], [SC.ERA_IDX[e] for e in SC.UNIVERSE_ERAS])
        out[kind] = {"n_winners_all": int(y.sum()),
                     "rate_all": round(float(y.mean()), 6),
                     "n_winners_E2E8": int(y[m].sum()),
                     "rate_E2E8": round(float(y[m].mean()), 6),
                     "cap_usd_by_asset": {a: float(np.unique(cap[
                         D["asset_idx"] == i])[0]) if (D["asset_idx"] == i).any()
                         else None for i, a in enumerate(MC.ASSET_ORDER)}}
    y0, _ = label_variant(D, "d021")
    y1, _ = label_variant(D, "maecap")
    out["overlap"] = {"both": int(((y0 > 0) & (y1 > 0)).sum()),
                      "maecap_only": int(((y0 <= 0) & (y1 > 0)).sum()),
                      "d021_only": int(((y0 > 0) & (y1 <= 0)).sum())}
    # the dip the census measured, re-read here so the cap is not a rumour
    cc = D["cert_close_usd"].astype(np.float64)
    mae = D["mae_before_argmax"].astype(np.float64)
    import common as C
    tk = np.array([float(C.ASSETS[a]["tick_usd"]) for a in MC.ASSET_ORDER])
    dip = mae / tk[D["asset_idx"].astype(np.int64)]
    unc = (cc >= D021_WIN_USD) & (D["walled"] == 0)
    out["uncapped_dip_ticks"] = {
        "n": int(unc.sum()),
        "median": round(float(np.nanmedian(dip[unc])), 2),
        "q75": round(float(np.nanpercentile(dip[unc], 75)), 2),
        "q90": round(float(np.nanpercentile(dip[unc], 90)), 2)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", action="store_true")
    ap.add_argument("--labels", action="store_true")
    ap.add_argument("--eras", default=",".join(SC.TEST_ERAS))
    ap.add_argument("--shuffle", action="store_true")
    ap.add_argument("--creator", action="store_true")
    ap.add_argument("--label", default="d021")
    ap.add_argument("--one", action="store_true")
    ap.add_argument("--from-era", default="E2")
    a = ap.parse_args()
    eras = tuple(x for x in a.eras.split(",") if x)
    if a.labels:
        print(json.dumps(label_stats(), indent=1))
    if a.grid:
        stats = label_stats()
        with open(os.path.join(SC.CACHE_ROOT, "champ_labels.json"), "w") as fh:
            json.dump(stats, fh, indent=1)
        SC.hb("label stats: %s" % json.dumps(stats["overlap"]))
        for use_cre, lab in ((False, "d021"), (True, "d021"),
                             (False, "maecap"), (True, "maecap")):
            run(use_creator=use_cre, label=lab, test_eras=eras,
                from_era=a.from_era)
    if a.one:
        run(use_creator=a.creator, label=a.label, test_eras=eras,
            shuffle=a.shuffle, from_era=a.from_era)
    if not (a.grid or a.labels or a.one):
        ap.print_help()


if __name__ == "__main__":
    main()
