#!/usr/bin/python3
"""PORT M2 — THE CAPTURE CAMPAIGN, continuing past the milestone brief.

(1) PER-ERA CONSTRAINT SETS + PER-ERA STRICTNESS.  TOP50 was chosen POOLED and
    the strictness optimum was already shown to be INTERIOR (50 beat both 6 and
    112).  There is no reason E3's recipe is E5's: E3 is the era constraints
    rescued (+$636, +$491 after its own seed sd) and E5 is the era that was
    already strong.  k is swept per era and the winner is read per era.
(2) THE MAE-CAP LABEL, full test on the stacked config -- the 18-tick-dip
    blind spot, where D-021's MAE<=$300 winner definition selects away exactly
    the creator-style winners the census found replicating.
Every arm is a 5-SEED distribution with capture-of-ceiling.
"""
import argparse, json, os, sys, time
import numpy as np
_H = os.path.dirname(os.path.abspath(__file__))
for _p in (_H, "/workspace/engine/port_m2/seqtest", "/workspace/engine/port_m0",
           "/workspace/engine/port_m1", "/workspace/engine/port_m3",
           "/workspace/artifacts/cache/pylibs"):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import newobj as N, newobj_arms as NA, rank_atlas as RA, champ_floor as CF
import curriculum as CU, confidence as CO, monotone as MO, m2_common as MC
import st_common as SC

ERAS, SEEDS = N.DEV_ERAS, (0, 1, 2, 3, 4)
KS = (30, 40, 50, 65, 80)


def _vec(D, era, k):
    cols, names = NA.feat_cols(D)
    X = D["X"][:, cols]
    v = D["cert_close_usd"].astype(np.float64)
    te = [e for e in ("E1", "E2", "E3", "E4", "E5", "E6", "E7")
          if SC.ERA_IDX.get(e, 99) < SC.ERA_IDX[era]]
    M = []
    for t in te:
        r = N.deployable(D, N.era_rows(D, t))
        if r.size < 500:
            continue
        M.append(np.array([MO._within_cell_rho(D, r, X[:, j], v)
                           for j in range(X.shape[1])]))
    if not M:
        return [0] * len(names)
    M = np.vstack(M); mr = M.mean(0)
    ag = np.all(np.sign(M) == np.sign(mr)[None, :], axis=0)
    cand = sorted([(abs(mr[j]), j) for j in range(len(names))
                   if ag[j] and abs(mr[j]) >= MO.RHO_FLOOR], reverse=True)[:k]
    keep = {j for _a, j in cand}
    return [int(np.sign(mr[j])) if j in keep else 0 for j in range(len(names))]


def _one(job):
    era, seed, k, label = job
    try:
        import xgboost as xgb
        D, P = CF.boot()
        tr, itr, iva, ev = NA.fold(D, era)
        cols, names = NA.feat_cols(D)
        XF = D["X"][:, cols]
        if label == "maecap":
            import st_champ as CH
            y, _c = CH.label_variant(D, "maecap")
            val = D["cert_close_usd"].astype(np.float64).copy()
            val[(y <= 0) & (val > 0)] = 0.0
        else:
            val = D["cert_close_usd"].astype(np.float64)
        hp = NA.CHAMP_HP[era]
        cfg = {"objective": "rank:ndcg", "eval_metric": "ndcg@3",
               "tree_method": "hist", "min_child_weight": 20, "subsample": .8,
               "colsample_bytree": .8, "lambdarank_pair_method": "topk",
               "lambdarank_normalization": True,
               "lambdarank_num_pair_per_sample":
                   hp["lambdarank_num_pair_per_sample"],
               "max_depth": hp["max_depth"], "eta": hp["eta"],
               "seed": N.SEED + seed, "nthread": RA.N_THREAD}
        if k:
            cfg["monotone_constraints"] = "(" + ",".join(
                str(int(z)) for z in _vec(D, era, k)) + ")"
        rf, gf = RA._groups_of(D, tr, CF.SPEC)
        d = xgb.DMatrix(XF[rf], label=NA.grades(val[rf]), feature_names=names)
        d.set_group(gf)
        gw = CU.group_weights(D, tr, rf, gf, era, "W_VOLMATCH")
        if gw is not None:
            d.set_weight(gw)
        b = xgb.train(cfg, d, int(hp["rounds"]))
        del d
        rs, _g = RA._groups_of(D, ev, CF.SPEC)
        sc = np.full(D["d8"].size, np.nan)
        sc[rs] = b.predict(xgb.DMatrix(XF[rs], feature_names=names),
                           output_margin=True)
        a = N.read_rows(D, N.replay_delayed(
            D, N.top_per_cell_score(D, ev, sc, N.committed_policy()[era][1]), P))
        return (era, seed, k, label, a["usd_per_session"], None)
    except Exception as e:                              # noqa: BLE001
        return (era, seed, k, label, None, "%s: %s" % (type(e).__name__, e))


def run(eras=ERAS, workers=6):
    import multiprocessing as mp
    D, P = CF.boot()
    ceil = CO.ceilings(eras)
    jobs = [(e, s, k, "dollars") for e in eras for s in SEEDS for k in KS]
    jobs += [(e, s, 50, "maecap") for e in eras for s in SEEDS]
    N.hb("campaign: %d fits (%d strictness x %d eras x %d seeds + MAE-cap)"
         % (len(jobs), len(KS), len(eras), len(SEEDS)))
    res, errs, t0 = {}, [], time.time()
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        for i, (e, s, k, lb, v, err) in enumerate(
                pool.imap_unordered(_one, jobs), start=1):
            if err:
                errs.append([e, s, k, lb, err])
                N.hb("campaign FAILED %s k=%s %s: %s" % (e, k, lb, err))
                continue
            res.setdefault((e, k, lb), []).append(v)
            if i % 10 == 0 or i == len(jobs):
                N.hb("campaign %d/%d [eta %.0fs]"
                     % (i, len(jobs), (time.time() - t0) / i * (len(jobs) - i)))
    rows = []
    for e in eras:
        for lb in ("dollars", "maecap"):
            for k in (KS if lb == "dollars" else (50,)):
                a = np.asarray([x for x in res.get((e, k, lb), [])
                                if x is not None])
                if a.size == 0:
                    continue
                c = ceil.get("%s|ALL" % e)
                rows.append([e, lb, k, int(a.size), N._r(a.mean()),
                             N._r(a.std()), N._r(a.min()), N._r(a.max()),
                             N._r(c), N._r(a.mean() / c, 4) if c else ""])
    if not rows:
        raise N.NewObjRefusal("campaign produced zero rows; %d failures"
                              % len(errs))
    N.write_tsv("CAMPAIGN_STRICTNESS_MAECAP.tsv",
                ["era", "label", "n_constraints", "n_seeds", "mean_usd",
                 "sd_usd", "min_usd", "max_usd", "entry_foresight_ceiling",
                 "capture_of_ceiling"], rows,
                extra=["PER-ERA constraint strictness swept (k = 30/40/50/65/80 "
                       "stable signs) on the W_VOLMATCH base, plus the MAE-CAP "
                       "label at k=50.  Every cell a 5-SEED distribution.",
                       "TOP50 was chosen POOLED; the optimum was already known "
                       "to be interior (50 beat both 6 and 112), so there is no "
                       "reason E3's recipe is E5's.",
                       "PROMOTION: a per-era k counts only if its 5-seed mean "
                       "clears the k=50 mean by more than its own seed sd."])
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()
    if a.run:
        run()
    else:
        ap.print_help()
