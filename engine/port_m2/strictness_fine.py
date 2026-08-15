#!/usr/bin/python3
"""PORT M2 — FINE STRICTNESS, SELECTED ON INNER BLOCKS ONLY.

THE DISCIPLINE POINT THAT GOVERNS THIS PASS.  The existing per-era winners
(E3 65 / E4 80 / E5 80 / E6 65 / E7 65) were chosen by ERA ARGMAX -- picking the
k that paid most on the very era being reported.  That carries a selection
premium the 5-seed bars do not capture, and choosing again the same way would
COMPOUND it.  So this pass selects k on the INNER VALIDATION BLOCK only and
reports the inner-selected recipe's honest eval as the result; the era-argmax is
reported beside it as CONTEXT ONLY and is flagged as such.

k in {55, 60, 65, 70, 75, 80}, per era AND per asset.  The per-asset split is
free: one inner fit per (era, k, seed) is scored once and read per asset.

THE HONEST STOPPING RULE, stated before the run: inner selection has already
FAILED once on this program -- on the weighting axis it picked flat where
volmatch won and pooled below both references.  If it cannot distinguish k here
either, that is reported plainly and THE AXIS CLOSES; shape constraints stay
gated on this passing, so they close with it.
"""
import argparse
import os
import sys
import time

import numpy as np

_H = os.path.dirname(os.path.abspath(__file__))
for _p in (_H, "/workspace/engine/port_m2/seqtest", "/workspace/engine/port_m0",
           "/workspace/engine/port_m1", "/workspace/engine/port_m3",
           "/workspace/artifacts/cache/pylibs"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import newobj as N                        # noqa: E402
import newobj_arms as NA                  # noqa: E402
import rank_atlas as RA                   # noqa: E402
import champ_floor as CF                  # noqa: E402
import curriculum as CU                   # noqa: E402
import confidence as CO                   # noqa: E402
import campaign as CP                     # noqa: E402
import stacked_final as SF                # noqa: E402
import m2_common as MC                    # noqa: E402

BINDING = ("E5", "E6", "E7")
ERAS = BINDING + ("E3", "E4")
KS = (55, 60, 65, 70, 75, 80)
INNER_SEEDS = (0, 1)
EVAL_SEEDS = (0, 1, 2, 3, 4)
ERA_ARGMAX = {"E3": 65, "E4": 80, "E5": 80, "E6": 65, "E7": 65}


def _fit(D, era, seed, k, fit_rows, score_rows):
    import xgboost as xgb
    cols, names = NA.feat_cols(D)
    XF = D["X"][:, cols]
    val = D["cert_close_usd"].astype(np.float64)
    hp = NA.CHAMP_HP[era]
    vec = CP._vec(D, era, k)
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
    rf, gf = RA._groups_of(D, fit_rows, CF.SPEC)
    d = xgb.DMatrix(XF[rf], label=NA.grades(val[rf]), feature_names=names)
    d.set_group(gf)
    gw = CU.group_weights(D, fit_rows, rf, gf, era, "W_VOLMATCH")
    if gw is not None:
        d.set_weight(gw)
    b = xgb.train(cfg, d, int(hp["rounds"]))
    del d
    rs, _g = RA._groups_of(D, score_rows, CF.SPEC)
    sc = np.full(D["d8"].size, np.nan)
    sc[rs] = b.predict(xgb.DMatrix(XF[rs], feature_names=names),
                       output_margin=True)
    return sc


def _armed(D, P, rows, sc, era):
    rep = N.replay_delayed(D, N.top_per_cell_score(
        D, rows, sc, N.committed_policy()[era][1]), P)
    return N.read_rows(D, SF.apply_stop(D, rep,
                                        "STOP_WALL1"))["usd_per_session"]


def _inner_one(job):
    era, seed, k = job
    try:
        D, P = CF.boot()
        tr, itr, iva, ev = NA.fold(D, era)
        iva_d = N.deployable(D, iva)
        sc = _fit(D, era, seed, k, itr, iva_d)
        out = {"ALL": _armed(D, P, iva_d, sc, era)}
        for ai in sorted(set(D["asset_idx"][iva_d].tolist())):
            sel = iva_d[D["asset_idx"][iva_d] == ai]
            out[MC.ASSET_ORDER[ai]] = _armed(D, P, sel, sc, era)
        return (era, seed, k, out, None)
    except Exception as e:                              # noqa: BLE001
        return (era, seed, k, None, "%s: %s" % (type(e).__name__, e))


def _eval_one(job):
    era, seed, kmap = job
    try:
        D, P = CF.boot()
        tr, itr, iva, ev = NA.fold(D, era)
        if isinstance(kmap, int):
            sc = _fit(D, era, seed, kmap, tr, ev)
            v = _armed(D, P, ev, sc, era)
            return (era, seed, "per_era", v, None)
        # per-asset: fit each asset's k, score that asset's rows
        sc = np.full(D["d8"].size, np.nan)
        for a, k in kmap.items():
            ai = MC.ASSET_ORDER.index(a)
            eva = ev[D["asset_idx"][ev] == ai]
            if eva.size == 0:
                continue
            s1 = _fit(D, era, seed, k, tr, eva)
            m = np.isfinite(s1)
            sc[m] = s1[m]
        v = _armed(D, P, ev, sc, era)
        return (era, seed, "per_asset", v, None)
    except Exception as e:                              # noqa: BLE001
        return (era, seed, "?", None, "%s: %s" % (type(e).__name__, e))


def run(workers=6):
    import multiprocessing as mp
    D, P = CF.boot()
    ceil = CO.ceilings()
    ctx = mp.get_context("spawn")
    jobs = [(e, s, k) for e in ERAS for s in INNER_SEEDS for k in KS]
    N.hb("fine strictness: %d INNER fits (k=%s), selection on inner only"
         % (len(jobs), list(KS)))
    inner, t0 = {}, time.time()
    with ctx.Pool(processes=workers) as pool:
        for i, (e, s, k, out, err) in enumerate(
                pool.imap_unordered(_inner_one, jobs), 1):
            if err:
                N.hb("inner FAILED %s k=%d: %s" % (e, k, err))
                continue
            inner.setdefault((e, k), []).append(out)
            if i % 10 == 0 or i == len(jobs):
                N.hb("inner %d/%d [eta %.0fs]"
                     % (i, len(jobs), (time.time() - t0) / i * (len(jobs) - i)))
    sel_era, sel_asset, irows = {}, {}, []
    for e in ERAS:
        means = {}
        for k in KS:
            v = [d["ALL"] for d in inner.get((e, k), []) if d
                 and d.get("ALL") is not None]
            means[k] = float(np.mean(v)) if v else float("-inf")
            irows.append([e, "ALL", k, len(v), N._r(means[k])])
        sel_era[e] = max(means, key=means.get)
        spread = (max(means.values()) - min(means.values())
                  if means else float("nan"))
        N.hb("inner-selected %s -> k=%d (inner spread $%.2f across k)"
             % (e, sel_era[e], spread))
        am = {}
        for a in MC.ASSET_ORDER:
            mm = {}
            for k in KS:
                v = [d[a] for d in inner.get((e, k), []) if d
                     and d.get(a) is not None]
                mm[k] = float(np.mean(v)) if v else float("-inf")
                irows.append([e, a, k, len(v), N._r(mm[k])])
            am[a] = max(mm, key=mm.get)
        sel_asset[e] = am
    N.write_tsv("STRICTNESS_FINE_INNER.tsv",
                ["era", "scope", "k", "n_seeds", "inner_armed_usd"], irows,
                extra=["INNER-BLOCK selection table.  These are the ONLY "
                       "numbers the recipe is chosen on; the eval era's "
                       "outcome never enters."])
    ev_jobs = ([(e, s, sel_era[e]) for e in ERAS for s in EVAL_SEEDS]
               + [(e, s, sel_asset[e]) for e in ERAS for s in EVAL_SEEDS])
    N.hb("fine strictness: %d EVAL fits (inner-selected recipes)"
         % len(ev_jobs))
    res = {}
    with ctx.Pool(processes=workers) as pool:
        for i, (e, s, kind, v, err) in enumerate(
                pool.imap_unordered(_eval_one, ev_jobs), 1):
            if err:
                N.hb("eval FAILED %s: %s" % (e, err))
                continue
            res.setdefault((kind, e), []).append(v)
            if i % 10 == 0 or i == len(ev_jobs):
                N.hb("eval %d/%d" % (i, len(ev_jobs)))
    rows = []
    for e in ERAS:
        inc = []
        evr = N.deployable(D, N.era_rows(D, e))
        for s in EVAL_SEEDS:
            fp = os.path.join(CU._sdir(), "FOLD_%s_%d.npy" % (e, s))
            if not os.path.exists(fp):
                fp = os.path.join(CU._sdir(), "CONTOP50_%s_%d.npy" % (e, s))
            if os.path.exists(fp):
                sc = np.load(fp).astype(np.float64)
                inc.append(_armed(D, P, evr, sc, e))
        ic = np.asarray([x for x in inc if x is not None])
        cl = ceil.get("%s|ALL" % e)
        for kind in ("per_era", "per_asset"):
            a = np.asarray([x for x in res.get((kind, e), [])
                            if x is not None])
            if a.size == 0:
                continue
            rows.append([e, "BINDING" if e in BINDING else "context", kind,
                         str(sel_era[e] if kind == "per_era"
                             else sel_asset[e]),
                         ERA_ARGMAX.get(e), int(a.size), N._r(a.mean()),
                         N._r(a.std()), N._r(ic.mean()) if ic.size else "",
                         N._r(a.mean() - ic.mean()) if ic.size else "",
                         N._r(a.mean() - ic.mean() - a.std())
                         if ic.size else "",
                         N._r(a.mean() / cl, 4) if cl else ""])
    N.write_tsv("STRICTNESS_FINE.tsv",
                ["era", "criterion", "selection", "inner_selected_k",
                 "era_argmax_k_CONTEXT_ONLY", "n_seeds", "armed_mean",
                 "armed_sd", "incumbent_armed", "delta", "delta_minus_sd",
                 "armed_capture"], rows,
                extra=["FINE STRICTNESS, k in {55,60,65,70,75,80}, SELECTED ON "
                       "INNER BLOCKS ONLY.  `inner_selected_k` is the recipe; "
                       "`era_argmax_k_CONTEXT_ONLY` is the k that paid most on "
                       "the era itself and is NOT a recipe -- it carries "
                       "era-outcome selection premium and is shown only so the "
                       "premium is visible.",
                       "The incumbent is the folded per-era-argmax stack, so a "
                       "positive delta here means inner selection BEAT a "
                       "recipe that had already seen the answer.",
                       "STOPPING RULE (pre-registered): if inner selection "
                       "cannot separate the k values, the axis CLOSES and shape "
                       "constraints close with it -- inner selection already "
                       "failed once on the weighting axis, which is the "
                       "precedent for believing a null here."])
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    if a.run:
        run()
    else:
        ap.print_help()
