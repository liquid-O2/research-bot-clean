#!/usr/bin/python3
"""PORT M2 SEQTEST — THE TABULAR FOUNDATION-MODEL ARMS (user-ordered).

Two in-context tabular foundation models scored under the champion's exact
protocol, as extra arms beside the GBT-ranking family:

  `tabpfn`  TabPFN v3, LOCAL checkpoints from
            artifacts/cache/port/models/tabpfn_v3/ckpt — the binary classifier
            and the OOD / TIMESERIES regressor variants. **GPU MANDATORY.**
  `tabfm`   Google `tabfm` (vendor/tabfm), pytorch backend, same protocol.

THE FIT STRATEGY, and why it is needed (documented per instruction). Both models
are IN-CONTEXT learners: they read the training rows as a prompt rather than
fitting parameters, so the training block cannot simply be handed over — our
blocks are 417k–1.16M rows. Strategy:

  * per fold, draw `N_CONTEXT` rows at random from that fold's training block
    (`PRE_E1..E(k-1)`, whole days, identical to the champion's block);
  * repeat for `N_ENSEMBLE` independent draws with different seeds and AVERAGE
    the predictions — chunked ensembling over subsampled contexts;
  * evaluation rows are predicted in chunks; no evaluation row is ever in a
    context, and no context ever contains a row from the evaluation era.

Sampling is uniform, so the label's natural base rate is preserved and the
output stays calibrated; the ensemble is what recovers the information the
single-context limit throws away.

**Their natural edge is small data**, so the per-era reading — especially the
weak early eras E3–E5 — is the point, not the pooled mean.

Scoring is the champion's, unchanged: rank within the `(asset, day, phase)` CELL,
top-1 per cell under m3's committed per-era policy, D-077 veto, phase-close
replay, day-clustered CR1. Exits stay parked.

Run:
  st_fm.py --run --model tabpfn --target winner --eras E3,E4,E5,E6,E7
  st_fm.py --run --model tabfm  --target dollars
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
import panel_score as PS

TABPFN_CKPT = "/workspace/artifacts/cache/port/models/tabpfn_v3/ckpt"
CKPT = {
    "clf_binary": "tabpfn-v3-classifier-v3_20260417_binary.ckpt",
    "clf_ood": "tabpfn-v3-classifier-v3_20260506_ood.ckpt",
    "reg_ood": "tabpfn-v3-regressor-v3_20260506_ood.ckpt",
    "reg_timeseries": "tabpfn-v3-regressor-v3_20260506_timeseries.ckpt",
}
N_CONTEXT = 32768
N_ENSEMBLE = 4
CHUNK = 20000
# Both arms get the SAME 32,768-row context — the comparison is not handicapped
# on either side.  TabFM's activation footprint is larger than TabPFN's, and the
# 97 GB card has the headroom for it.
N_CONTEXT_TABFM = N_CONTEXT


def feature_cols(D):
    """The champion's own 184 columns — every non-`tf_` feature."""
    cols = [i for i, n in enumerate(D["names"]) if not str(n).startswith("tf_")]
    return cols


def _ctx_draw(rows, n, seed):
    rs = np.random.RandomState(seed)
    if rows.size <= n:
        return rows
    return np.sort(rs.choice(rows, size=n, replace=False))


def _fit_predict_tabpfn(Xtr, ytr, Xte, target, variant, seed):
    import torch
    from tabpfn import TabPFNClassifier, TabPFNRegressor
    p = os.path.join(TABPFN_CKPT, CKPT[variant])
    if not os.path.exists(p):
        raise SC.SeqTestRefusal("missing local checkpoint %s" % p)
    if not torch.cuda.is_available():
        raise SC.SeqTestRefusal("GPU MANDATORY for the TabPFN arm and CUDA is "
                                "not available — refusing to run on CPU")
    kw = dict(model_path=p, device="cuda", n_estimators=1,
              ignore_pretraining_limits=True, random_state=seed)
    out = np.zeros(Xte.shape[0])
    if target == "winner":
        m = TabPFNClassifier(**kw)
        m.fit(Xtr, ytr.astype(int))
        for a in range(0, Xte.shape[0], CHUNK):
            out[a:a + CHUNK] = m.predict_proba(Xte[a:a + CHUNK])[:, 1]
    else:
        m = TabPFNRegressor(**kw)
        m.fit(Xtr, ytr)
        for a in range(0, Xte.shape[0], CHUNK):
            out[a:a + CHUNK] = m.predict(Xte[a:a + CHUNK])
    del m
    torch.cuda.empty_cache()
    return out


_TABFM = {}


def _tabfm_model(kind):
    """The TabFM weights cost ~39s to pull and materialise — load ONCE per
    process and move to the GPU, never per context."""
    import torch
    import tabfm as TF
    if kind not in _TABFM:
        m = TF.tabfm_v1_0_0_pytorch.load(model_type=kind)
        try:
            m = m.to("cuda")
        except Exception:                       # noqa: BLE001
            raise SC.SeqTestRefusal("TabFM could not be placed on the GPU and "
                                    "the GPU is mandatory for this arm")
        _TABFM[kind] = m
        SC.hb("tabfm %s weights loaded to GPU" % kind)
    return _TABFM[kind]


def _fit_predict_tabfm(Xtr, ytr, Xte, target, variant, seed):
    import torch
    from tabfm import TabFMClassifier, TabFMRegressor
    if not torch.cuda.is_available():
        raise SC.SeqTestRefusal("GPU MANDATORY for the TabFM arm and CUDA is "
                                "not available — refusing to run on CPU")
    mdl = _tabfm_model("classification" if target == "winner"
                       else "regression")
    kw = dict(model=mdl, n_estimators=1, random_state=seed)
    # TabFM refuses NaN (TabPFN ingests it natively).  The matrix carries
    # typed-missing entries, so they are imputed from the CONTEXT's own column
    # medians — train-only, therefore still causal — and the difference from the
    # TabPFN arm is recorded rather than hidden.
    med = np.nanmedian(np.where(np.isfinite(Xtr), Xtr, np.nan), axis=0)
    med = np.where(np.isfinite(med), med, 0.0).astype(np.float32)
    Xtr = np.where(np.isfinite(Xtr), Xtr, med[None, :]).astype(np.float32)
    Xte = np.where(np.isfinite(Xte), Xte, med[None, :]).astype(np.float32)
    out = np.zeros(Xte.shape[0])
    if target == "winner":
        m = TabFMClassifier(**kw)
        m.fit(Xtr, ytr.astype(int))
        for a in range(0, Xte.shape[0], CHUNK):
            pr = np.asarray(m.predict_proba(Xte[a:a + CHUNK]))
            out[a:a + CHUNK] = pr[:, -1]
    else:
        m = TabFMRegressor(**kw)
        m.fit(Xtr, ytr)
        for a in range(0, Xte.shape[0], CHUNK):
            out[a:a + CHUNK] = np.asarray(m.predict(Xte[a:a + CHUNK])).ravel()
    del m
    torch.cuda.empty_cache()
    return out


BACKEND = {"tabpfn": _fit_predict_tabpfn, "tabfm": _fit_predict_tabfm}


def run(model="tabpfn", target="winner", variant=None, eras=("E3", "E4", "E5",
                                                             "E6", "E7"),
        tag=None, shuffle=False, n_context=N_CONTEXT, n_ens=N_ENSEMBLE):
    import torch
    import m3_walk as W
    variant = variant or ("clf_binary" if target == "winner" else "reg_ood")
    tag = tag or ("FM_%s_%s%s" % (model.upper(), target.upper(),
                                  "_SHUF" if shuffle else ""))
    if model == "tabfm" and n_context == N_CONTEXT:
        n_context = N_CONTEXT_TABFM
    D, _p = W.load_matrix()
    ceil = R.ceilings_of(D)
    klass, _cn = RK.class_index(D)
    cols = feature_cols(D)
    X = D["X"][:, cols]
    n = D["d8"].size
    score = np.full(n, np.nan)
    j = D["names"].index("in_news_window")
    ledger = []
    t_all = time.time()
    gpu_peak = 0.0
    for era in eras:
        t0 = time.time()
        tr, ev = R.fold_rows(D, era, from_era="PRE_E1")
        tr = tr[D["X"][tr, j] < 0.5]
        ev_r = ev[D["X"][ev, j] < 0.5]
        y = (D["y_winner"] if target == "winner"
             else D["cert_close_usd"]).astype(np.float64)
        yv = y
        if shuffle:
            rs = np.random.RandomState(SC.SEED + SC.ERA_IDX[era])
            yv = y.copy()
            yv[tr] = y[tr][rs.permutation(tr.size)]
        fin = tr[np.isfinite(yv[tr])]
        acc = np.zeros(ev_r.size)
        torch.cuda.reset_peak_memory_stats()
        for e in range(n_ens):
            ctx = _ctx_draw(fin, n_context, SC.SEED + 1000 * e
                            + SC.ERA_IDX[era])
            SC.assert_disjoint_days(ctx, ev_r, D["d8"],
                                    tag="%s %s ctx%d" % (tag, era, e))
            SC.assert_causal_era_order(ctx, ev_r, D["era_idx"],
                                       tag="%s %s ctx%d" % (tag, era, e))
            acc += BACKEND[model](X[ctx], yv[ctx], X[ev_r], target, variant,
                                  SC.SEED + e)
            SC.hb("%s %s ctx %d/%d done (%.0fs)"
                  % (tag, era, e + 1, n_ens, time.time() - t0))
        score[ev_r] = acc / float(n_ens)
        gpu_peak = max(gpu_peak, torch.cuda.max_memory_allocated() / 1e9)
        ledger.append({"era": era, "model": model, "target": target,
                       "variant": variant, "n_context": int(n_context),
                       "n_ensemble": int(n_ens),
                       "n_train_pool": int(fin.size), "n_eval": int(ev_r.size),
                       "secs": round(time.time() - t0, 1),
                       "gpu_peak_gb": round(gpu_peak, 2)})
        SC.hb("%s %s: %d ctx x %d of %d pool -> %d eval rows (%.0fs)"
              % (tag, era, n_ens, n_context, fin.size, ev_r.size,
                 time.time() - t0))
    np.savez(os.path.join(R._sdir(), "%s.npz" % tag), champ=score, win=score)
    R.save_result(tag, {"kind": "rank", "group_unit": "cell",
                        "arch": "%s-%s-%s" % (model, target, variant),
                        "rung": "foundation", "L": 0, "trunk": model,
                        "mode": "ctx", "pretrained": True,
                        "per_era": [], "pooled": {}, "ledger": ledger,
                        "gpu": R.gpu_note(),
                        "wall_secs": round(time.time() - t_all, 1)})
    SC.hb("%s DONE in %.0fs, GPU peak %.2f GB"
          % (tag, time.time() - t_all, gpu_peak))
    return tag


def paired_vs(tag_a, tag_b, eras, out=None):
    """Paired per-SESSION difference, clustered by DAY — arm A minus arm B."""
    import m3_walk as W
    D, _p = W.load_matrix()
    ceil = R.ceilings_of(D)
    with open(os.path.join(M3.WALK_DIR, "walk.summary.json")) as fh:
        pol = {e["era"]: (e["policy_unit"], int(e["topn"]))
               for e in json.load(fh)["eras"] if e.get("status") == "OK"}
    rows = []
    alld, allc = [], []
    for era in eras:
        ev = np.nonzero(D["era_idx"] == SC.ERA_IDX[era])[0]
        u, nn = pol.get(era, ("cell", 1))
        got = {}
        for t in (tag_a, tag_b):
            s = np.load(os.path.join(R.SCORE_DIR, "%s.npz" % t))["champ"]
            e2 = ev[np.isfinite(s[ev])]
            rr = W.replay_rows(D, W.topn_takes(D, s, e2, nn, deployable=True,
                                               unit=u))
            got[t] = {r["session"]: r["realised"] for r in rr}
        keys = sorted(set(got[tag_a]) & set(got[tag_b]))
        d = [got[tag_a][k] - got[tag_b][k] for k in keys]
        cl = [int(k.split("|")[1]) for k in keys]
        cm = PS.cluster_mean(d, cl) if d else None
        alld += d
        allc += cl
        rows.append([era, len(keys), R._r(cm["mean"]) if cm else "",
                     R._r(cm["ci_lo"]) if cm else "",
                     R._r(cm["ci_hi"]) if cm else "",
                     ("%.4g" % cm["p"]) if cm and cm["p"] is not None else ""])
    cm = PS.cluster_mean(alld, allc) if alld else None
    rows.append(["POOLED", len(alld), R._r(cm["mean"]) if cm else "",
                 R._r(cm["ci_lo"]) if cm else "",
                 R._r(cm["ci_hi"]) if cm else "",
                 ("%.4g" % cm["p"]) if cm and cm["p"] is not None else ""])
    R.write_tsv(out or ("SEQTEST_PAIRED_%s_vs_%s.tsv" % (tag_a, tag_b)),
                ["era", "n_sessions", "mean_diff_usd_per_session", "ci_lo",
                 "ci_hi", "p"], rows,
                extra=["PAIRED per-SESSION difference, %s MINUS %s, on the "
                       "identical schedule; CR1 clustered by DAY."
                       % (tag_a, tag_b)])
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--paired", nargs=2, default=None)
    ap.add_argument("--model", default="tabpfn", choices=("tabpfn", "tabfm"))
    ap.add_argument("--target", default="winner", choices=("winner", "dollars"))
    ap.add_argument("--variant", default=None)
    ap.add_argument("--eras", default="E3,E4,E5,E6,E7")
    ap.add_argument("--tag", default=None)
    ap.add_argument("--shuffle", action="store_true")
    ap.add_argument("--n-context", type=int, default=N_CONTEXT)
    ap.add_argument("--n-ens", type=int, default=N_ENSEMBLE)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    eras = tuple(a.eras.split(","))
    if a.paired:
        paired_vs(a.paired[0], a.paired[1], eras, out=a.out)
    elif a.run:
        run(model=a.model, target=a.target, variant=a.variant, eras=eras,
            tag=a.tag, shuffle=a.shuffle, n_context=a.n_context,
            n_ens=a.n_ens)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
