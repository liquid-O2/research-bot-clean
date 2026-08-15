#!/usr/bin/python3
"""PORT M2 — FOLD THE PER-ERA STRICTNESS WINNERS INTO THE DEPLOYED STACK.

The strictness sweep's per-era argmax by `delta_minus_sd` (the promotion rule,
not the raw mean):

    E3 k=65 · E4 k=80 · E5 k=80 · E6 k=65 · E7 k=65

TOP50 was a POOLED compromise; every binding era wants MORE constraint than it,
and the optimum is still interior (65-80 of ~112 stable signs, not all of them).
These become the deployed members, and everything downstream rebases onto them:
the CELLREL arm was queued against the OLD base and is re-run here, and the
HP re-search matters MORE at higher k because a more-constrained tree spends
capacity differently.
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

BINDING = ("E5", "E6", "E7")
ERAS = BINDING + ("E3", "E4")
SEEDS = (0, 1, 2, 3, 4)
BEST_K = {"E3": 65, "E4": 80, "E5": 80, "E6": 65, "E7": 65}
# HP RE-SEARCH PROMOTES (RIDER_CONSTRAINED_HP.tsv, promotion rule delta_minus_sd):
#   E6 depth3/eta0.10  +$488.19, dm-sd +159.98  -> PROMOTED
#   E4 depth3/eta0.10  + $90.16, dm-sd  +2.94   -> promoted, marginal, flagged
#   E5/E7/E3 fail their own sd and KEEP the champion HP.
# Constraints changed the optimal capacity exactly where the constraint gain was
# largest (E6), which is the coherent story, not a coincidence.
BEST_HP = {"E6": {"max_depth": 3, "eta": 0.10},
           "E4": {"max_depth": 3, "eta": 0.10}}


def _one(job):
    era, seed, feat = job
    try:
        import xgboost as xgb
        D, P = CF.boot()
        tr, itr, iva, ev = NA.fold(D, era)
        k = BEST_K[era]
        if feat == "BASE":
            cols, names = NA.feat_cols(D)
            XF = D["X"][:, cols]
            FN = names
        else:
            spec = dict(CF.SPEC)
            spec["feat"] = feat
            XF, FN = RA.build_features(D, spec, tr, np.arange(D["d8"].size))
        val = D["cert_close_usd"].astype(np.float64)
        hp = NA.CHAMP_HP[era]
        vec = list(CP._vec(D, era, k))
        vec += [0] * (XF.shape[1] - len(vec))       # extra cols unconstrained
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
        cfg.update(BEST_HP.get(era, {}))        # the promoted HP, where one won
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
        tag = "FOLD" if feat == "BASE" else "FOLDCELLREL"
        np.save(os.path.join(CU._sdir(), "%s_%s_%d.npy" % (tag, era, seed)),
                sc.astype(np.float32))
        rep = N.replay_delayed(D, N.top_per_cell_score(
            D, ev, sc, N.committed_policy()[era][1]), P)
        raw = N.read_rows(D, rep)["usd_per_session"]
        arm = N.read_rows(D, SF.apply_stop(D, rep,
                                           "STOP_WALL1"))["usd_per_session"]
        return (era, seed, feat, raw, arm, None)
    except Exception as e:                              # noqa: BLE001
        return (era, seed, feat, None, None,
                "%s: %s" % (type(e).__name__, e))


def run(workers=6):
    import multiprocessing as mp
    D, P = CF.boot()
    ceil = CO.ceilings()
    jobs = [(e, s, f) for f in ("BASE", "CELLREL") for e in ERAS
            for s in SEEDS]
    N.hb("fold: %d fits (per-era k %s) x {BASE, CELLREL-rebased}"
         % (len(jobs), BEST_K))
    res, t0 = {}, time.time()
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        for i, (e, s, f, raw, arm, err) in enumerate(
                pool.imap_unordered(_one, jobs), 1):
            if err:
                N.hb("fold FAILED %s %s: %s" % (f, e, err))
                continue
            res.setdefault((f, e), []).append((raw, arm))
            if i % 10 == 0 or i == len(jobs):
                N.hb("fold %d/%d [eta %.0fs]"
                     % (i, len(jobs), (time.time() - t0) / i * (len(jobs) - i)))
    rows = []
    for e in ERAS:
        for f in ("BASE", "CELLREL"):
            v = res.get((f, e), [])
            raw = np.asarray([x[0] for x in v if x[0] is not None])
            arm = np.asarray([x[1] for x in v if x[1] is not None])
            if arm.size == 0:
                continue
            # incumbent: the TOP50 members this replaces
            inc = []
            evr = N.deployable(D, N.era_rows(D, e))
            for s in SEEDS:
                fp = os.path.join(CU._sdir(), "CONTOP50_%s_%d.npy" % (e, s))
                if not os.path.exists(fp):
                    continue
                sc = np.load(fp).astype(np.float64)
                rp = N.replay_delayed(D, N.top_per_cell_score(
                    D, evr, sc, N.committed_policy()[e][1]), P)
                inc.append(N.read_rows(D, SF.apply_stop(
                    D, rp, "STOP_WALL1"))["usd_per_session"])
            ic = np.asarray([x for x in inc if x is not None])
            cl = ceil.get("%s|ALL" % e)
            rows.append([e, "BINDING" if e in BINDING else "context", f,
                         BEST_K[e], int(arm.size), N._r(raw.mean()),
                         N._r(arm.mean()), N._r(arm.std()),
                         N._r(ic.mean()) if ic.size else "",
                         N._r(arm.mean() - ic.mean()) if ic.size else "",
                         N._r(arm.mean() - ic.mean() - arm.std())
                         if ic.size else "",
                         N._r(arm.mean() / cl, 4) if cl else ""])
    N.write_tsv("FOLDED_STACK.tsv",
                ["era", "criterion", "feature_set", "k", "n_seeds",
                 "raw_mean", "armed_mean", "armed_sd", "incumbent_top50_armed",
                 "delta", "delta_minus_sd", "armed_capture"], rows,
                extra=["THE PER-ERA STRICTNESS WINNERS FOLDED IN: E3 k=65, "
                       "E4 k=80, E5 k=80, E6 k=65, E7 k=65 -- chosen by the "
                       "promotion rule (delta_minus_sd), not the raw mean.  "
                       "TOP50 was a POOLED compromise and every binding era "
                       "wants more constraint than it; the optimum is still "
                       "INTERIOR (65-80 of ~112 stable signs).",
                       "CELLREL is REBASED here -- it was queued against the "
                       "old TOP50 base and that read is superseded.  Its extra "
                       "columns stay unconstrained (no stability receipt).",
                       "ARMED rows are primary (first-wall stop adopted); raw "
                       "is reference.  Incumbent = the TOP50 members replaced."])
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    if a.run:
        run()
    else:
        ap.print_help()
