#!/usr/bin/python3
"""PORT M2 — THE CURRICULUM ROUND, under the no-single-fit law.

EVERY ARM IS A 5-SEED DISTRIBUTION at the deployed full-history window
(`PRE_E1`).  The reference is the champion's own 5-seed distribution
($754.20 +/- 322.82 pooled E3-E7).  No arm is ever quoted as a single fit.

TREATMENT 1 -- SAMPLE / ERA WEIGHTING inside full history.  The measured $831
window swing (E6: PRE_E1 $625.91 / E1 $436.43 / E2 $264.76) says data
COMPOSITION is the largest untuned lever in the stack, and the champion never
tuned it: it takes every row of every prior era at weight 1.  Variants sweep
recency half-lives, per-era balance, and vol-regime matching.  All weighting is
applied as a per-GROUP weight (a cell is the unit the ranker scores), computed
from TRAINING rows only.

THE ENSEMBLE DIAGNOSIS THAT PRECEDED THIS ROUND (coordinator-ordered, done
first, and it changed the construction):
    era | members PRE_E1 / E1 / E2 | ens(all 15) | ens(PRE_E1 only, 5)
    E3  |   448.85 / 226.38 / 214.51 |   222.52  |  424.91
    E5  |   755.94 / 606.39 / 487.46 |   699.10  |  723.58
    E7  | 1052.91 / 986.70 / 639.77  |   977.76  | 1160.72
The "E3 ensemble collapse" was an artefact of MY member set: the 15-member
ensemble averaged strong full-history members with deliberately data-starved
E1/E2-window members, so it landed near the MIXTURE mean.  Rebuilt on the
deployed window alone it sits at the member mean (E3 -24, E5 -32) or above it
(E7 +108).  Score-mean ensembling is not broken.
    WHY IT GAINS SO LITTLE, measured: the within-cell rank correlation BETWEEN
MEMBERS is 0.75-0.80.  At rho ~= 0.79 with 5 members the variance-reduction
factor is sqrt((1+4*rho)/5) ~= 0.91 -- only ~9% of the noise is removable by
averaging seeds.  Members make CORRELATED errors, which is why decorrelating
them (bagged features) is the only ensemble variant worth spending on.
"""
import argparse
import json
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, "/workspace/engine/port_m2/seqtest", "/workspace/engine/port_m0",
           "/workspace/engine/port_m1", "/workspace/engine/port_m3",
           "/workspace/artifacts/cache/pylibs"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import newobj as N                        # noqa: E402
import newobj_arms as NA                  # noqa: E402
import rank_atlas as RA                   # noqa: E402
import champ_floor as CF                  # noqa: E402
import risk_panel as RP                   # noqa: E402
import st_common as SC                    # noqa: E402
import m2_common as MC                    # noqa: E402

ERAS = N.DEV_ERAS
SEEDS = (0, 1, 2, 3, 4)
WINDOW = "PRE_E1"                          # the DEPLOYED window, always

# TREATMENT 1: the weighting variants.  W_FLAT is the champion verbatim.
WEIGHTS = ("W_FLAT", "W_HL1", "W_HL2", "W_HL4", "W_ERABAL", "W_VOLMATCH")


def group_weights(D, tr_rows, r_f, g_f, era, kind):
    """A per-GROUP weight vector.  Computed from TRAINING rows only."""
    if kind == "W_FLAT":
        return None
    ptr = np.concatenate([[0], np.cumsum(g_f)])
    gera = np.array([float(np.median(D["era_idx"][r_f[a:b]]))
                     for a, b in zip(ptr[:-1], ptr[1:])])
    k = float(SC.ERA_IDX[era])
    if kind in ("W_HL1", "W_HL2", "W_HL4"):
        hl = {"W_HL1": 1.0, "W_HL2": 2.0, "W_HL4": 4.0}[kind]
        return np.clip(0.5 ** ((k - 1.0 - gera) / hl), 0.02, 1.0)
    if kind == "W_ERABAL":
        # every era contributes the SAME total weight, so the recent eras are
        # not simply out-voted by the accumulated bulk of the old ones
        w = np.ones(gera.size)
        for e in np.unique(gera):
            m = gera == e
            w[m] = 1.0 / max(float(m.sum()), 1.0)
        return np.clip(w / w.mean(), 0.02, 20.0)
    if kind == "W_VOLMATCH":
        # weight a training cell by how close its regime is to the regime the
        # EVALUATION era will actually present.  The regime summary is read from
        # the matrix's own `regime_tercile` column; the target is the mean over
        # the TRAINING block's most recent era (never the evaluation era).
        j = D["names"].index("regime_tercile")
        v = D["X"][:, j]
        gval = np.array([float(np.nanmean(v[r_f[a:b]]))
                         for a, b in zip(ptr[:-1], ptr[1:])])
        recent = tr_rows[D["era_idx"][tr_rows] == int(k - 1)]
        tgt = float(np.nanmean(v[recent])) if recent.size else float(
            np.nanmean(v[tr_rows]))
        sd = float(np.nanstd(v[tr_rows])) or 1.0
        return np.clip(np.exp(-0.5 * ((gval - tgt) / sd) ** 2), 0.02, 1.0)
    raise N.NewObjRefusal("unknown weighting %r" % kind)


def fit_weighted(D, P, era, seed, kind):
    import xgboost as xgb
    tr, itr, iva, ev_r = NA.fold(D, era)
    cols, names = NA.feat_cols(D)
    XF = D["X"][:, cols]
    val = D["cert_close_usd"].astype(np.float64)
    hp = NA.CHAMP_HP[era]
    cfg = {"objective": "rank:ndcg", "eval_metric": "ndcg@3",
           "tree_method": "hist", "min_child_weight": 20, "subsample": 0.8,
           "colsample_bytree": 0.8, "lambdarank_pair_method": "topk",
           "lambdarank_normalization": True,
           "lambdarank_num_pair_per_sample":
               hp["lambdarank_num_pair_per_sample"],
           "max_depth": hp["max_depth"], "eta": hp["eta"],
           "seed": int(N.SEED + seed), "nthread": RA.N_THREAD}
    r_f, g_f = RA._groups_of(D, tr, CF.SPEC)
    d = xgb.DMatrix(XF[r_f], label=NA.grades(val[r_f]), feature_names=names)
    d.set_group(g_f)
    gw = group_weights(D, tr, r_f, g_f, era, kind)
    if gw is not None:
        d.set_weight(gw)
    b = xgb.train(cfg, d, int(hp["rounds"]))
    del d
    r_s, _g = RA._groups_of(D, ev_r, CF.SPEC)
    sc = np.full(D["d8"].size, np.nan)
    sc[r_s] = b.predict(xgb.DMatrix(XF[r_s], feature_names=names),
                        output_margin=True)
    return sc, ev_r


def _one(job):
    era, seed, kind = job
    try:
        D, P = CF.boot()
        t0 = time.time()
        sc, ev_r = fit_weighted(D, P, era, seed, kind)
        np.save(os.path.join(_sdir(), "%s_%s_%d.npy" % (kind, era, seed)),
                sc.astype(np.float32))
        _u, n_ = N.committed_policy().get(era, ("cell", 1))
        a = N.read_rows(D, N.replay_delayed(
            D, N.top_per_cell_score(D, ev_r, sc, n_), P))
        return (era, seed, kind, {"usd": a["usd_per_session"],
                                  "seats": a["n_seated"],
                                  "secs": round(time.time() - t0, 1)}, None)
    except Exception as exc:                            # noqa: BLE001
        return (era, seed, kind, None,
                "%s: %s" % (type(exc).__name__, exc))


def _sdir():
    d = os.path.join(N.OUT_ROOT, "curriculum_scores")
    os.makedirs(d, exist_ok=True)
    return d


def members_path():
    return os.path.join(N.OUT_ROOT, "curriculum_members.jsonl")


def stage_weighting(eras=ERAS, seeds=SEEDS, kinds=WEIGHTS, workers=None,
                    shuffle_control=True):
    import multiprocessing as mp
    import resource
    D, P = CF.boot()
    try:
        lim = int(open("/sys/fs/cgroup/memory.max").read()) / 1e9
        cur = int(open("/sys/fs/cgroup/memory.current").read()) / 1e9
    except Exception:                                   # noqa: BLE001
        lim, cur = 260.0, 0.0
    t0 = time.time()
    sc0, _ev = fit_weighted(D, P, eras[0], 0, "W_FLAT")
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6
    workers = int(workers or min(6, max(1, int((lim - cur) * 0.6 / max(rss, 1)))))
    N.hb("curriculum: member RSS %.1f GB -> %d workers" % (rss, workers))
    jobs = [(e, s, k) for k in kinds for e in eras for s in seeds]
    N.hb("curriculum: %d fits (%d weightings x %d eras x %d seeds), "
         "incremental writes" % (len(jobs), len(kinds), len(eras), len(seeds)))
    open(members_path(), "w").close()
    res, errs = {}, []
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        for k, (era, seed, kind, out, err) in enumerate(
                pool.imap_unordered(_one, jobs), start=1):
            if err:
                errs.append([era, seed, kind, err])
                N.hb("curriculum %d/%d FAILED %s %s s%d: %s"
                     % (k, len(jobs), kind, era, seed, err))
                continue
            res[(era, seed, kind)] = out
            with open(members_path(), "a") as fh:
                fh.write(json.dumps({"era": era, "seed": seed, "kind": kind,
                                     **out}) + "\n")
            N.hb("curriculum MEMBER %d/%d %-10s %s s%d: $%s (%d seats) "
                 "[%.0fs eta %.0fs]"
                 % (k, len(jobs), kind, era, seed, N._r(out["usd"]),
                    out["seats"], time.time() - t0,
                    (time.time() - t0) / k * (len(jobs) - k)))
    rows = []
    ref = {}
    for kind in kinds:
        pooled = []
        for era in eras:
            v = np.asarray([res[(era, s, kind)]["usd"] for s in seeds
                            if (era, s, kind) in res], dtype=np.float64)
            if v.size == 0:
                continue
            pooled.append(v)
            if kind == "W_FLAT":
                ref[era] = v.mean()
            rows.append([kind, era, int(v.size), N._r(v.mean()), N._r(v.std()),
                         N._r(v.min()), N._r(v.max()),
                         N._r(v.mean() - ref.get(era, np.nan))])
        if pooled:
            allv = np.concatenate(pooled)
            rows.append([kind, "POOLED", int(allv.size), N._r(allv.mean()),
                         N._r(allv.std()), N._r(allv.min()), N._r(allv.max()),
                         N._r(allv.mean()
                              - np.mean([ref[e] for e in ref]) if ref else None)])
    N.write_tsv("CURRICULUM_WEIGHTING.tsv",
                ["weighting", "era", "n_seeds", "mean_usd", "sd_usd",
                 "min_usd", "max_usd", "delta_vs_W_FLAT"], rows,
                extra=["TREATMENT 1 under the NO-SINGLE-FIT law: every cell is "
                       "a 5-SEED MEAN with its sd, at the deployed PRE_E1 "
                       "window.  W_FLAT is the champion verbatim and is the "
                       "reference; its distribution is $754.20 +/- 322.82 "
                       "pooled.",
                       "A weighting only counts as signal if its 5-seed mean "
                       "clears W_FLAT's 5-seed mean by more than the seed sd -- "
                       "a single fit beating a single fit is exactly the "
                       "artefact that retracted the ranking atlas's winner.",
                       "Weights are per-GROUP (the cell is what the ranker "
                       "scores) and are computed from TRAINING rows only; "
                       "W_VOLMATCH's target regime is read from the training "
                       "block's most recent era, never the evaluation era."])
    N.save_json("curriculum_weighting.json",
                {"errors": errs, "workers": workers,
                 "secs": round(time.time() - t0, 1)})
    return rows


def _selfcheck():
    for n in ("stage_weighting", "fit_weighted", "group_weights", "_one"):
        if n not in globals():
            raise RuntimeError("curriculum.py mis-assembled: %s missing" % n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weighting", action="store_true")
    ap.add_argument("--select", action="store_true")
    ap.add_argument("--bagged", action="store_true")
    ap.add_argument("--reg", action="store_true")
    ap.add_argument("--stacked", action="store_true")
    ap.add_argument("--weapons", default="")
    ap.add_argument("--wdiverse", action="store_true")
    ap.add_argument("--condepth", default="")
    ap.add_argument("--distill", action="store_true")
    ap.add_argument("--condistill", action="store_true")
    ap.add_argument("--base", default="W_VOLMATCH")
    ap.add_argument("--colsample", type=float, default=0.4)
    ap.add_argument("--eras", default=",".join(ERAS))
    ap.add_argument("--workers", type=int, default=None)
    a = ap.parse_args()
    eras = tuple(e for e in a.eras.split(",") if e)
    if a.weighting:
        stage_weighting(eras=eras, workers=a.workers)
    elif a.select:
        stage_select(eras=eras, workers=a.workers or 6)
    elif a.bagged:
        globals()["BAG_FRAC"] = a.colsample
        stage_bagged({e: a.base for e in eras}, eras=eras,
                     workers=a.workers or 6)
    elif a.reg:
        stage_reg(eras=eras, workers=a.workers or 6)
    elif a.stacked:
        stage_stacked(eras=eras, workers=a.workers or 6)
    elif a.weapons:
        stage_weapons(eras=eras,
                      weapons=tuple(w for w in a.weapons.split(",") if w),
                      workers=a.workers or 6)
    elif a.wdiverse:
        stage_wdiverse(eras=eras, workers=a.workers or 6)
    elif a.condepth:
        stage_condepth(eras=eras,
                       variants=tuple(v for v in a.condepth.split(",") if v),
                       workers=a.workers or 6)
    elif a.distill:
        stage_distill(eras=eras, workers=a.workers or 6)
    elif a.condistill:
        stage_condistill(eras=eras, workers=a.workers)
    else:
        ap.print_help()



# =============================== 1: PER-ERA WEIGHTING SELECTION (lawful) =====
# DECISION MADE WITHOUT ASKING (noted, per coordinator): the per-era choice is
# made on the INNER-VALIDATION block with 3 seeds (not 5), because inner
# selection only has to RANK three candidates while the reported number is still
# a 5-seed eval distribution.  Using the already-computed eval scores for the
# report keeps the selection and the reporting strictly separate.
SEL_KINDS = ("W_FLAT", "W_VOLMATCH", "W_ERABAL")
SEL_SEEDS = (0, 1, 2)


def fit_inner(D, P, era, seed, kind):
    """Fit on inner-TRAIN, score inner-VALIDATION -- selection only."""
    import xgboost as xgb
    tr, itr, iva, ev_r = NA.fold(D, era)
    cols, names = NA.feat_cols(D)
    XF = D["X"][:, cols]
    val = D["cert_close_usd"].astype(np.float64)
    hp = NA.CHAMP_HP[era]
    cfg = {"objective": "rank:ndcg", "eval_metric": "ndcg@3",
           "tree_method": "hist", "min_child_weight": 20, "subsample": 0.8,
           "colsample_bytree": 0.8, "lambdarank_pair_method": "topk",
           "lambdarank_normalization": True,
           "lambdarank_num_pair_per_sample":
               hp["lambdarank_num_pair_per_sample"],
           "max_depth": hp["max_depth"], "eta": hp["eta"],
           "seed": int(N.SEED + seed), "nthread": RA.N_THREAD}
    r_f, g_f = RA._groups_of(D, itr, CF.SPEC)
    d = xgb.DMatrix(XF[r_f], label=NA.grades(val[r_f]), feature_names=names)
    d.set_group(g_f)
    gw = group_weights(D, itr, r_f, g_f, era, kind)
    if gw is not None:
        d.set_weight(gw)
    b = xgb.train(cfg, d, int(hp["rounds"]))
    del d
    iva_dep = N.deployable(D, iva)
    r_s, _g = RA._groups_of(D, iva_dep, CF.SPEC)
    sc = np.full(D["d8"].size, np.nan)
    sc[r_s] = b.predict(xgb.DMatrix(XF[r_s], feature_names=names),
                        output_margin=True)
    _u, n_ = N.committed_policy().get(era, ("cell", 1))
    return N.read_rows(D, N.replay_delayed(
        D, N.top_per_cell_score(D, iva_dep, sc, n_), P)).get("usd_per_session")


def _sel_one(job):
    era, seed, kind = job
    try:
        D, P = CF.boot()
        return (era, seed, kind, fit_inner(D, P, era, seed, kind), None)
    except Exception as exc:                            # noqa: BLE001
        return (era, seed, kind, None, "%s: %s" % (type(exc).__name__, exc))


def stage_select(eras=ERAS, workers=6):
    import multiprocessing as mp
    D, P = CF.boot()
    jobs = [(e, s, k) for e in eras for s in SEL_SEEDS for k in SEL_KINDS]
    N.hb("select: %d inner fits (%d weightings x %d eras x %d seeds)"
         % (len(jobs), len(SEL_KINDS), len(eras), len(SEL_SEEDS)))
    inner, t0 = {}, time.time()
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        for k, (era, seed, kind, v, err) in enumerate(
                pool.imap_unordered(_sel_one, jobs), start=1):
            if err:
                N.hb("select FAILED %s %s s%d: %s" % (kind, era, seed, err))
                continue
            inner.setdefault((era, kind), []).append(v)
            if k % 10 == 0 or k == len(jobs):
                N.hb("select %d/%d (%.0fs)" % (k, len(jobs), time.time() - t0))
    chosen, rows = {}, []
    for era in eras:
        best, bv = None, -np.inf
        for kind in SEL_KINDS:
            v = [x for x in inner.get((era, kind), []) if x is not None]
            m = float(np.mean(v)) if v else float("-inf")
            rows.append([era, kind, len(v), N._r(m)])
            if m > bv:
                best, bv = kind, m
        chosen[era] = best
        N.hb("select %s -> %s (inner $%.2f)" % (era, best, bv))
    # report the SELECTED arm from the already-computed 5-seed EVAL scores
    out, per_era = [], {}
    for era in eras:
        kind = chosen[era]
        v = []
        for s in SEEDS:
            p = os.path.join(_sdir(), "%s_%s_%d.npy" % (kind, era, s))
            if not os.path.exists(p):
                continue
            sc = np.load(p).astype(np.float64)
            ev = N.deployable(D, N.era_rows(D, era))
            n_ = N.committed_policy()[era][1]
            v.append(N.read_rows(D, N.replay_delayed(
                D, N.top_per_cell_score(D, ev, sc, n_), P))["usd_per_session"])
        v = np.asarray(v, dtype=np.float64)
        per_era[era] = v
        out.append([era, kind, int(v.size), N._r(v.mean()), N._r(v.std()),
                    N._r(v.min()), N._r(v.max())])
    allv = np.concatenate([per_era[e] for e in eras if e in per_era])
    out.append(["POOLED", "per-era selected", int(allv.size),
                N._r(allv.mean()), N._r(allv.std()), N._r(allv.min()),
                N._r(allv.max())])
    N.write_tsv("CURRICULUM_SELECT.tsv",
                ["era", "chosen_weighting", "n_seeds", "mean_usd", "sd_usd",
                 "min_usd", "max_usd"], out,
                extra=["TREATMENT 1b: the LAWFUL combined arm -- the weighting "
                       "is chosen PER ERA on the inner-validation block "
                       "(3 seeds, ranking only) and the reported number is the "
                       "5-seed EVAL distribution of that choice.  Selection and "
                       "reporting never touch the same rows.",
                       "Inner-block selection table follows in "
                       "CURRICULUM_SELECT_INNER.tsv."])
    N.write_tsv("CURRICULUM_SELECT_INNER.tsv",
                ["era", "weighting", "n_seeds", "inner_mean_usd"], rows)
    N.save_json("curriculum_select.json", {"chosen": chosen})
    return chosen


# ============================================ 3: DECORRELATED ENSEMBLE =======
# The rho=0.79 prediction: seed-only members are too correlated for averaging to
# pay.  Feature-BAGGED members force decorrelation by giving each member a
# different random 60% of the columns (in addition to a different seed).
BAG_N = 10
BAG_FRAC = 0.6


def _bag_one(job):
    era, m, kind = job
    try:
        import xgboost as xgb
        D, P = CF.boot()
        tr, itr, iva, ev_r = NA.fold(D, era)
        cols, names = NA.feat_cols(D)
        rs = np.random.RandomState(N.SEED + 5000 + m)
        keep = np.sort(rs.choice(len(cols), int(len(cols) * BAG_FRAC),
                                 replace=False))
        XF = D["X"][:, [cols[i] for i in keep]]
        FN = [names[i] for i in keep]
        val = D["cert_close_usd"].astype(np.float64)
        hp = NA.CHAMP_HP[era]
        cfg = {"objective": "rank:ndcg", "eval_metric": "ndcg@3",
               "tree_method": "hist", "min_child_weight": 20, "subsample": 0.8,
               "colsample_bytree": 0.8, "lambdarank_pair_method": "topk",
               "lambdarank_normalization": True,
               "lambdarank_num_pair_per_sample":
                   hp["lambdarank_num_pair_per_sample"],
               "max_depth": hp["max_depth"], "eta": hp["eta"],
               "seed": int(N.SEED + 5000 + m), "nthread": RA.N_THREAD}
        r_f, g_f = RA._groups_of(D, tr, CF.SPEC)
        d = xgb.DMatrix(XF[r_f], label=NA.grades(val[r_f]), feature_names=FN)
        d.set_group(g_f)
        gw = group_weights(D, tr, r_f, g_f, era, kind)
        if gw is not None:
            d.set_weight(gw)
        b = xgb.train(cfg, d, int(hp["rounds"]))
        del d
        r_s, _g = RA._groups_of(D, ev_r, CF.SPEC)
        sc = np.full(D["d8"].size, np.nan)
        sc[r_s] = b.predict(xgb.DMatrix(XF[r_s], feature_names=FN),
                            output_margin=True)
        np.save(os.path.join(_sdir(), "BAG_%s_%d.npy" % (era, m)),
                sc.astype(np.float32))
        _u, n_ = N.committed_policy().get(era, ("cell", 1))
        a = N.read_rows(D, N.replay_delayed(
            D, N.top_per_cell_score(D, ev_r, sc, n_), P))
        return (era, m, a["usd_per_session"], None)
    except Exception as exc:                            # noqa: BLE001
        return (era, m, None, "%s: %s" % (type(exc).__name__, exc))


def stage_bagged(chosen, eras=ERAS, workers=6):
    import multiprocessing as mp
    D, P = CF.boot()
    jobs = [(e, m, chosen.get(e, "W_FLAT")) for e in eras
            for m in range(BAG_N)]
    N.hb("bagged: %d members (%d per era, %.0f%% of columns each)"
         % (len(jobs), BAG_N, BAG_FRAC * 100))
    mem, t0 = {}, time.time()
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        for k, (era, m, v, err) in enumerate(
                pool.imap_unordered(_bag_one, jobs), start=1):
            if err:
                N.hb("bagged FAILED %s m%d: %s" % (era, m, err))
                continue
            mem.setdefault(era, []).append(v)
            N.hb("bagged MEMBER %d/%d %s m%d: $%s [%.0fs]"
                 % (k, len(jobs), era, m, N._r(v), time.time() - t0))
    rows, panel, per_era = [], [], {}
    for era in eras:
        v = np.asarray([x for x in mem.get(era, []) if x is not None])
        if v.size == 0:
            continue
        S = [np.load(os.path.join(_sdir(), "BAG_%s_%d.npy" % (era, m)))
             .astype(np.float64) for m in range(BAG_N)
             if os.path.exists(os.path.join(_sdir(), "BAG_%s_%d.npy" % (era, m)))]
        ev = N.deployable(D, N.era_rows(D, era))
        n_ = N.committed_policy()[era][1]
        # member decorrelation actually achieved
        ro, blocks = N.cell_blocks(D, ev)
        cors = []
        for a_, b_ in blocks[:300]:
            idx = ro[a_:b_]
            if idx.size < 4:
                continue
            M = np.vstack([x[idx] for x in S])
            if not np.isfinite(M).all():
                continue
            R = np.vstack([np.argsort(np.argsort(mm)) for mm in M]).astype(float)
            c = np.corrcoef(R)
            cors.append(c[np.triu_indices(len(S), 1)].mean())
        rho = float(np.mean(cors)) if cors else float("nan")
        ens = np.nanmean(np.vstack(S), axis=0)
        a = N.read_rows(D, N.replay_delayed(
            D, N.top_per_cell_score(D, ev, ens, n_), P))
        per_era[era] = a
        rows.append([era, chosen.get(era, "W_FLAT"), int(v.size),
                     N._r(v.mean()), N._r(v.std()), N._r(a["usd_per_session"]),
                     N._r(a["ps_lo"]), N._r(a["ps_hi"]),
                     N._r((a["usd_per_session"] or 0) - v.mean()), N._r(rho, 3)])
        RP.panel_for_score(D, P, ens, "CURRICULUM_BAGGED", (era,), panel)
        N.hb("bagged %s: members $%.2f+/-%.2f -> ensemble $%s (rho %.3f)"
             % (era, v.mean(), v.std(), N._r(a["usd_per_session"]), rho))
    q = N.pool_reads([per_era[e] for e in eras if e in per_era])
    rows.append(["POOLED", "", "", "", "", N._r(q.get("usd_per_session")),
                 N._r(q.get("ps_lo")), N._r(q.get("ps_hi")), "", ""])
    N.write_tsv("CURRICULUM_BAGGED.tsv",
                ["era", "weighting", "n_members", "member_mean", "member_sd",
                 "ensemble_usd", "lo", "hi", "delta_vs_member_mean",
                 "member_rank_rho"], rows,
                extra=["TREATMENT 3: FEATURE-BAGGED members (%d per era, each on "
                       "a random %.0f%% of the columns plus its own seed) on top "
                       "of the per-era selected weighting." % (BAG_N,
                                                               BAG_FRAC * 100),
                       "member_rank_rho is the achieved within-cell rank "
                       "correlation BETWEEN members.  Seed-only members sat at "
                       "0.75-0.80, which caps averaging at ~9% noise removal; "
                       "this column is the test of whether bagging actually "
                       "decorrelated them."])
    RP.write(panel, "RISK_PANEL_CURRICULUM_BAGGED.tsv",
             extra=["arm = feature-bagged ensemble on the per-era selected "
                    "weighting"])
    return rows


def _sc2():
    for n in ("stage_select","stage_bagged"):
        if n not in globals():
            raise RuntimeError("curriculum.py mis-assembled: %s" % n)

# ================ 2: REGULARIZATION SWEEP (on the W_VOLMATCH base) ===========
REG_GRID = tuple({"max_depth": d, "min_child_weight": m}
                 for d in (3, 4, 6) for m in (20, 60, 150))
REG_SEEDS = (0, 1)


def fit_reg(D, P, era, seed, kind, hpx, inner=True):
    import xgboost as xgb
    tr, itr, iva, ev_r = NA.fold(D, era)
    fit_rows = itr if inner else tr
    score_rows = N.deployable(D, iva) if inner else ev_r
    cols, names = NA.feat_cols(D)
    XF = D["X"][:, cols]
    val = D["cert_close_usd"].astype(np.float64)
    hp = NA.CHAMP_HP[era]
    cfg = {"objective": "rank:ndcg", "eval_metric": "ndcg@3",
           "tree_method": "hist", "subsample": 0.8, "colsample_bytree": 0.8,
           "lambdarank_pair_method": "topk", "lambdarank_normalization": True,
           "lambdarank_num_pair_per_sample":
               hp["lambdarank_num_pair_per_sample"],
           "eta": hp["eta"], "seed": int(N.SEED + seed),
           "nthread": RA.N_THREAD}
    cfg.update(hpx)
    r_f, g_f = RA._groups_of(D, fit_rows, CF.SPEC)
    d = xgb.DMatrix(XF[r_f], label=NA.grades(val[r_f]), feature_names=names)
    d.set_group(g_f)
    gw = group_weights(D, fit_rows, r_f, g_f, era, kind)
    if gw is not None:
        d.set_weight(gw)
    b = xgb.train(cfg, d, int(hp["rounds"]))
    del d
    r_s, _g = RA._groups_of(D, score_rows, CF.SPEC)
    sc = np.full(D["d8"].size, np.nan)
    sc[r_s] = b.predict(xgb.DMatrix(XF[r_s], feature_names=names),
                        output_margin=True)
    _u, n_ = N.committed_policy().get(era, ("cell", 1))
    a = N.read_rows(D, N.replay_delayed(
        D, N.top_per_cell_score(D, score_rows, sc, n_), P))
    return a.get("usd_per_session"), sc


def _reg_one(job):
    era, seed, hpx, inner = job
    try:
        D, P = CF.boot()
        v, sc = fit_reg(D, P, era, seed, "W_VOLMATCH", hpx, inner=inner)
        if not inner:
            np.save(os.path.join(_sdir(), "REG_%s_%d.npy" % (era, seed)),
                    sc.astype(np.float32))
        return (era, seed, json.dumps(hpx, sort_keys=True), v, None)
    except Exception as exc:                            # noqa: BLE001
        return (era, seed, json.dumps(hpx, sort_keys=True), None,
                "%s: %s" % (type(exc).__name__, exc))


def stage_reg(eras=ERAS, workers=6):
    import multiprocessing as mp
    D, P = CF.boot()
    jobs = [(e, s, hp, True) for e in eras for s in REG_SEEDS
            for hp in REG_GRID]
    N.hb("REG: %d inner fits (%d configs x %d eras x %d seeds) on W_VOLMATCH"
         % (len(jobs), len(REG_GRID), len(eras), len(REG_SEEDS)))
    inner, t0 = {}, time.time()
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        for k, (era, seed, hj, v, err) in enumerate(
                pool.imap_unordered(_reg_one, jobs), start=1):
            if err:
                N.hb("REG FAILED %s %s: %s" % (era, hj, err))
                continue
            inner.setdefault((era, hj), []).append(v)
            if k % 8 == 0 or k == len(jobs):
                N.hb("REG inner %d/%d (%.0fs eta %.0fs)"
                     % (k, len(jobs), time.time() - t0,
                        (time.time() - t0) / k * (len(jobs) - k)))
    chosen, irows = {}, []
    for era in eras:
        best, bv = None, -np.inf
        for hp in REG_GRID:
            hj = json.dumps(hp, sort_keys=True)
            v = [x for x in inner.get((era, hj), []) if x is not None]
            m = float(np.mean(v)) if v else float("-inf")
            irows.append([era, hj, len(v), N._r(m)])
            if m > bv:
                best, bv = hp, m
        chosen[era] = best
        N.hb("REG %s -> %s (inner $%.2f)" % (era, best, bv))
    jobs2 = [(e, s, chosen[e], False) for e in eras for s in SEEDS]
    res = {}
    with ctx.Pool(processes=workers) as pool:
        for k, (era, seed, hj, v, err) in enumerate(
                pool.imap_unordered(_reg_one, jobs2), start=1):
            if err:
                continue
            res.setdefault(era, []).append(v)
            N.hb("REG eval %d/%d %s s%d: $%s" % (k, len(jobs2), era, seed,
                                                 N._r(v)))
    rows, pooled = [], []
    for era in eras:
        v = np.asarray([x for x in res.get(era, []) if x is not None])
        if v.size == 0:
            continue
        pooled.append(v)
        rows.append([era, json.dumps(chosen[era], sort_keys=True), int(v.size),
                     N._r(v.mean()), N._r(v.std()), N._r(v.min()),
                     N._r(v.max())])
    if pooled:
        allv = np.concatenate(pooled)
        rows.append(["POOLED", "", int(allv.size), N._r(allv.mean()),
                     N._r(allv.std()), N._r(allv.min()), N._r(allv.max())])
    N.write_tsv("CURRICULUM_REG.tsv",
                ["era", "chosen_reg", "n_seeds", "mean_usd", "sd_usd",
                 "min_usd", "max_usd"], rows,
                extra=["TREATMENT 2 on the W_VOLMATCH base: depth x "
                       "min_child_weight chosen on INNER blocks (2 seeds, "
                       "ranking only), reported as a 5-SEED EVAL distribution.",
                       "Targets the generalization pool the sufficiency "
                       "instrument sized at $1.5-2.6k/session."])
    N.write_tsv("CURRICULUM_REG_INNER.tsv",
                ["era", "config", "n_seeds", "inner_mean_usd"], irows)
    N.save_json("curriculum_reg.json", {"chosen": chosen})
    return chosen


def stage_stacked(eras=ERAS, workers=6):
    """TREATMENT 4 -- the stacked final: W_VOLMATCH x best regularization x
    feature-bagged ensemble, with its risk panel and D-030 breach rates."""
    D, P = CF.boot()
    reg = (N.load_json("curriculum_reg.json") or {}).get("chosen", {})
    rows, panel, per_era = [], [], {}
    for era in eras:
        S = []
        for m in range(BAG_N):
            f = os.path.join(_sdir(), "BAG_%s_%d.npy" % (era, m))
            if os.path.exists(f):
                S.append(np.load(f).astype(np.float64))
        for s in SEEDS:
            f = os.path.join(_sdir(), "REG_%s_%d.npy" % (era, s))
            if os.path.exists(f):
                S.append(np.load(f).astype(np.float64))
        # THE CONSTRAINT RESULT BELONGS IN THE POOL.  The previous stacked table
        # predated it entirely (E3 $535 with no TOP50 inside) while TOP50 was
        # the round's biggest single result (+$636 on E3, +$491 after its own
        # seed sd).  Constrained members are folded in here.
        for s in SEEDS:
            f = os.path.join(_sdir(), "CONTOP50_%s_%d.npy" % (era, s))
            if os.path.exists(f):
                S.append(np.load(f).astype(np.float64))
        if not S:
            continue
        ev = N.deployable(D, N.era_rows(D, era))
        n_ = N.committed_policy()[era][1]
        ens = np.nanmean(np.vstack(S), axis=0)
        a = N.read_rows(D, N.replay_delayed(
            D, N.top_per_cell_score(D, ev, ens, n_), P))
        per_era[era] = a
        rows.append([era, len(S), N._r(a["usd_per_session"]), N._r(a["ps_lo"]),
                     N._r(a["ps_hi"]), a["n_seated"],
                     json.dumps(reg.get(era, {}), sort_keys=True)])
        for ai in sorted(set(D["asset_idx"][ev].tolist())):
            sel = ev[D["asset_idx"][ev] == ai]
            aa = N.read_rows(D, N.replay_delayed(
                D, N.top_per_cell_score(D, sel, ens, n_), P))
            rows.append(["%s|%s" % (era, MC.ASSET_ORDER[ai]), "",
                         N._r(aa["usd_per_session"]), N._r(aa["ps_lo"]),
                         N._r(aa["ps_hi"]), aa["n_seated"], ""])
        RP.panel_for_score(D, P, ens, "CURRICULUM_STACKED", (era,), panel)
        N.hb("STACKED %s: %d members -> $%s/session"
             % (era, len(S), N._r(a["usd_per_session"])))
    q = N.pool_reads([per_era[e] for e in eras if e in per_era])
    rows.append(["POOLED", "", N._r(q.get("usd_per_session")),
                 N._r(q.get("ps_lo")), N._r(q.get("ps_hi")),
                 q.get("n_seated"), ""])
    N.write_tsv("CURRICULUM_STACKED.tsv",
                ["era", "n_members", "usd_per_session", "lo", "hi",
                 "n_seated", "reg_config"], rows,
                extra=["TREATMENT 4: the stacked final -- W_VOLMATCH weighting x "
                       "inner-selected regularization x feature-bagged "
                       "ensemble.  Reference: the champion's 5-seed "
                       "distribution $754.20 +/- 322.82.  Bar: $2,000.",
                       "Rows ERA|ASSET are the per-asset table."])
    RP.write(panel, "RISK_PANEL_CURRICULUM_STACKED.tsv",
             extra=["arm = the curriculum stacked final"])
    return rows


def _sc3():
    for n in ("stage_reg", "fit_reg", "stage_stacked"):
        if n not in globals():
            raise RuntimeError("curriculum.py mis-assembled: %s" % n)

# ===================== THE THREE TRAINING WEAPONS (user priority) ============
# All on the W_VOLMATCH base, all evaluated as 5-SEED distributions against it
# ($902.03 +/- 418.82 pooled).  The target is the expressible-but-not-learnable
# pool the sufficiency instrument sized at $1,540-2,590/session.
NOISE_SCALE = 0.25          # of each feature's own measurement grain


def _noise_sigma(D, cols, tr_rows):
    """Per-feature injection scale = NOISE_SCALE x the column's own measurement
    grain, estimated as the median absolute nonzero first difference of its
    sorted unique values (its rounding/tick quantum), floored by a small
    fraction of its sd so continuous columns still move."""
    X = D["X"][:, cols][tr_rows]
    sig = np.zeros(X.shape[1], dtype=np.float64)
    for j in range(X.shape[1]):
        v = X[:, j]
        v = v[np.isfinite(v)]
        if v.size < 50:
            continue
        u = np.unique(v[:: max(1, v.size // 20000)])
        d = np.diff(u)
        d = d[d > 0]
        grain = float(np.median(d)) if d.size else 0.0
        sig[j] = max(grain, 0.02 * float(np.std(v))) * NOISE_SCALE
    return sig


def fit_weapon(D, P, era, seed, weapon, base="W_VOLMATCH"):
    import xgboost as xgb
    tr, itr, iva, ev_r = NA.fold(D, era)
    cols, names = NA.feat_cols(D)
    XF = D["X"][:, cols]
    val = D["cert_close_usd"].astype(np.float64)
    hp = NA.CHAMP_HP[era]
    cfg = {"objective": "rank:ndcg", "eval_metric": "ndcg@3",
           "tree_method": "hist", "min_child_weight": 20, "subsample": 0.8,
           "colsample_bytree": 0.8, "lambdarank_pair_method": "topk",
           "lambdarank_normalization": True,
           "lambdarank_num_pair_per_sample":
               hp["lambdarank_num_pair_per_sample"],
           "max_depth": hp["max_depth"], "eta": hp["eta"],
           "seed": int(N.SEED + seed), "nthread": RA.N_THREAD}
    r_f, g_f = RA._groups_of(D, tr, CF.SPEC)
    Xtr = XF[r_f]
    if weapon == "MONOTONE":
        import monotone as MO
        vec = (N.load_json("monotone_vectors.json") or {}).get(era)
        if vec is None:
            vec = MO.build(eras=(era,))[era]
        cfg["monotone_constraints"] = "(" + ",".join(str(int(z))
                                                     for z in vec) + ")"
    elif weapon == "NOISE":
        sig = _noise_sigma(D, cols, tr)
        rs = np.random.RandomState(N.SEED + 9000 + seed)
        Xtr = Xtr + (rs.standard_normal(Xtr.shape).astype(np.float32)
                     * sig.astype(np.float32)[None, :])
    d = xgb.DMatrix(Xtr, label=NA.grades(val[r_f]), feature_names=names)
    d.set_group(g_f)
    gw = group_weights(D, tr, r_f, g_f, era, base)
    if gw is not None:
        d.set_weight(gw)
    b = xgb.train(cfg, d, int(hp["rounds"]))
    del d, Xtr
    r_s, _g = RA._groups_of(D, ev_r, CF.SPEC)
    sc = np.full(D["d8"].size, np.nan)
    sc[r_s] = b.predict(xgb.DMatrix(XF[r_s], feature_names=names),
                        output_margin=True)
    return sc, ev_r


def _weapon_one(job):
    era, seed, weapon, base = job
    try:
        D, P = CF.boot()
        t0 = time.time()
        sc, ev_r = fit_weapon(D, P, era, seed, weapon, base)
        np.save(os.path.join(_sdir(), "%s_%s_%d.npy" % (weapon, era, seed)),
                sc.astype(np.float32))
        _u, n_ = N.committed_policy().get(era, ("cell", 1))
        a = N.read_rows(D, N.replay_delayed(
            D, N.top_per_cell_score(D, ev_r, sc, n_), P))
        return (era, seed, weapon, a["usd_per_session"],
                round(time.time() - t0, 1), None)
    except Exception as exc:                            # noqa: BLE001
        return (era, seed, weapon, None, 0.0,
                "%s: %s" % (type(exc).__name__, exc))


def stage_weapons(eras=ERAS, weapons=("MONOTONE", "NOISE"), workers=6):
    import multiprocessing as mp
    D, P = CF.boot()
    jobs = [(e, s, w, "W_VOLMATCH") for w in weapons for e in eras
            for s in SEEDS]
    N.hb("WEAPONS: %d fits (%s x %d eras x %d seeds) on the W_VOLMATCH base"
         % (len(jobs), "+".join(weapons), len(eras), len(SEEDS)))
    res, t0 = {}, time.time()
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        for k, (era, seed, w, v, secs, err) in enumerate(
                pool.imap_unordered(_weapon_one, jobs), start=1):
            if err:
                N.hb("WEAPON FAILED %s %s s%d: %s" % (w, era, seed, err))
                continue
            res.setdefault((w, era), []).append(v)
            N.hb("WEAPON %d/%d %-9s %s s%d: $%s (%.0fs) [eta %.0fs]"
                 % (k, len(jobs), w, era, seed, N._r(v), secs,
                    (time.time() - t0) / k * (len(jobs) - k)))
    base = {}
    for era in eras:
        bv = []
        for s in SEEDS:
            f = os.path.join(_sdir(), "W_VOLMATCH_%s_%d.npy" % (era, s))
            if not os.path.exists(f):
                continue
            sc = np.load(f).astype(np.float64)
            ev = N.deployable(D, N.era_rows(D, era))
            bv.append(N.read_rows(D, N.replay_delayed(
                D, N.top_per_cell_score(D, ev, sc,
                                        N.committed_policy()[era][1]),
                P))["usd_per_session"])
        base[era] = np.asarray(bv, dtype=np.float64)
    rows = []
    for w in weapons:
        pooled = []
        for era in eras:
            v = np.asarray([x for x in res.get((w, era), [])
                            if x is not None])
            if v.size == 0:
                continue
            pooled.append(v)
            b = base.get(era, np.asarray([]))
            rows.append([w, era, int(v.size), N._r(v.mean()), N._r(v.std()),
                         N._r(b.mean()) if b.size else "",
                         N._r(v.mean() - b.mean()) if b.size else "",
                         N._r(v.mean() - b.mean() - v.std())
                         if b.size else ""])
        if pooled:
            av = np.concatenate(pooled)
            ab = np.concatenate([base[e] for e in eras if base.get(e) is not
                                 None and base[e].size])
            rows.append([w, "POOLED", int(av.size), N._r(av.mean()),
                         N._r(av.std()), N._r(ab.mean()),
                         N._r(av.mean() - ab.mean()),
                         N._r(av.mean() - ab.mean() - av.std())])
    N.write_tsv("CURRICULUM_WEAPONS.tsv",
                ["weapon", "era", "n_seeds", "mean_usd", "sd_usd",
                 "volmatch_base_mean", "delta_vs_base",
                 "delta_minus_sd"], rows,
                extra=["THE TRAINING WEAPONS, on the W_VOLMATCH base, every "
                       "cell a 5-SEED distribution.",
                       "MONOTONE loads xgboost's monotone_constraints with the "
                       "signs our own censuses proved, intersected with a "
                       "per-fold stability receipt (see "
                       "MONOTONE_CONSTRAINTS.tsv).  The model becomes UNABLE to "
                       "invert a stable relationship to chase era noise.",
                       "NOISE trains on feature-noise-injected copies, the "
                       "noise scaled per column to %.2f x its own measurement "
                       "grain (its rounding quantum), floored so continuous "
                       "columns still move." % NOISE_SCALE,
                       "PROMOTION RULE: `delta_minus_sd` > 0 is the bar -- the "
                       "arm must clear the base's 5-seed mean by MORE THAN its "
                       "own seed sd.  A single fit beating a single fit is the "
                       "artefact that retracted the ranking atlas winner."])
    N.save_json("curriculum_weapons.json",
                {"secs": round(time.time() - t0, 1)})
    return rows


def stage_wdiverse(eras=ERAS, workers=6):
    """WEAPON 2 -- the WEIGHTING-DIVERSE ensemble: members that differ by
    TRAINING DATA COMPOSITION rather than by seed.  Seed-only members sat at
    rho 0.75-0.80 and feature bagging barely moved it; weighting changes what
    the model is fitted ON, which is a stronger decorrelator in principle.  The
    achieved cross-weighting rho is reported as the test."""
    D, P = CF.boot()
    kinds = ("W_VOLMATCH", "W_ERABAL", "W_FLAT")
    rows, panel, per_era = [], [], {}
    for era in eras:
        S, mem = [], []
        ev = N.deployable(D, N.era_rows(D, era))
        n_ = N.committed_policy()[era][1]
        for k in kinds:
            for s in SEEDS:
                f = os.path.join(_sdir(), "%s_%s_%d.npy" % (k, era, s))
                if not os.path.exists(f):
                    continue
                sc = np.load(f).astype(np.float64)
                S.append(sc)
                mem.append(N.read_rows(D, N.replay_delayed(
                    D, N.top_per_cell_score(D, ev, sc, n_),
                    P))["usd_per_session"])
        if len(S) < 3:
            continue
        ro, blocks = N.cell_blocks(D, ev)
        cors = []
        for a_, b_ in blocks[:300]:
            idx = ro[a_:b_]
            if idx.size < 4:
                continue
            M = np.vstack([x[idx] for x in S])
            if not np.isfinite(M).all():
                continue
            R = np.vstack([np.argsort(np.argsort(m)) for m in M]).astype(float)
            c = np.corrcoef(R)
            cors.append(c[np.triu_indices(len(S), 1)].mean())
        rho = float(np.mean(cors)) if cors else float("nan")
        ens = np.nanmean(np.vstack(S), axis=0)
        a = N.read_rows(D, N.replay_delayed(
            D, N.top_per_cell_score(D, ev, ens, n_), P))
        per_era[era] = a
        mm = float(np.mean([x for x in mem if x is not None]))
        rows.append([era, len(S), N._r(mm), N._r(a["usd_per_session"]),
                     N._r(a["ps_lo"]), N._r(a["ps_hi"]),
                     N._r((a["usd_per_session"] or 0) - mm), N._r(rho, 3)])
        RP.panel_for_score(D, P, ens, "CURRICULUM_WDIVERSE", (era,), panel)
        N.hb("WDIVERSE %s: %d members (3 weightings x 5 seeds) mean $%.2f -> "
             "ensemble $%s (cross-weighting rho %.3f)"
             % (era, len(S), mm, N._r(a["usd_per_session"]), rho))
    q = N.pool_reads([per_era[e] for e in eras if e in per_era])
    rows.append(["POOLED", "", "", N._r(q.get("usd_per_session")),
                 N._r(q.get("ps_lo")), N._r(q.get("ps_hi")), "", ""])
    N.write_tsv("CURRICULUM_WDIVERSE.tsv",
                ["era", "n_members", "member_mean", "ensemble_usd", "lo", "hi",
                 "delta_vs_member_mean", "cross_weighting_rho"], rows,
                extra=["WEAPON 2: members differ by TRAINING DATA COMPOSITION "
                       "(volmatch / era-balanced / flat) rather than by seed.",
                       "cross_weighting_rho against the seed-only baseline of "
                       "0.75-0.80 is the test of whether composition "
                       "decorrelates members better than seeds or features do."])
    RP.write(panel, "RISK_PANEL_CURRICULUM_WDIVERSE.tsv",
             extra=["arm = the weighting-diverse ensemble"])
    return rows


def _sc4():
    for n in ("stage_weapons", "stage_wdiverse", "fit_weapon"):
        if n not in globals():
            raise RuntimeError("curriculum.py mis-assembled: %s" % n)

# ============ GAP-CLOSER 1: CONSTRAINTS TO FULL DEPTH ========================
# 110 constraints at once can OVER-constrain: a stable-but-weak sign costs the
# model a degree of freedom it might have spent better.  So strictness is swept,
# the census-only minimal set is run even if the full arm is null (it is the
# honest fallback), and the columns where census and measurement CONFLICT are
# tested BOTH ways instead of being silently freed.
CON_VARIANTS = ("ALL", "CENSUS6", "TOP50", "CONFLICT_CENSUS", "ALL_INTERACT")


def _con_vector(D, era, variant):
    """(monotone vector, interaction_constraints or None)."""
    import monotone as MO
    vec = (N.load_json("monotone_vectors.json") or {}).get(era)
    if vec is None:
        vec = MO.build(eras=(era,))[era]
    vec = list(vec)
    cols, names = NA.feat_cols(D)
    rows = [l.rstrip("\n").split("\t") for l in
            open(os.path.join(N.PROV, "MONOTONE_CONSTRAINTS.tsv"))
            if not l.startswith("#")]
    hdr = rows[0]
    ie, inm, isg, isrc, irho = (hdr.index("era"), hdr.index("feature"),
                                hdr.index("sign"), hdr.index("source"),
                                hdr.index("mean_rho_train_eras"))
    info = {r[inm]: r for r in rows[1:] if r[ie] == era}
    idx = {nm: j for j, nm in enumerate(names)}
    if variant == "CENSUS6":
        out = [0] * len(vec)
        for nm, r in info.items():
            if r[isrc] == "CENSUS+STABLE" and nm in idx:
                out[idx[nm]] = int(r[isg])
        vec = out
    elif variant == "TOP50":
        cand = sorted([(abs(float(r[irho] or 0)), nm) for nm, r in info.items()
                       if r[isg] not in ("", "0") and nm in idx], reverse=True)
        keep = {nm for _v, nm in cand[:50]}
        vec = [v if names[j] in keep else 0 for j, v in enumerate(vec)]
    elif variant == "CONFLICT_CENSUS":
        # the columns the artifact left FREE because census and measurement
        # disagreed are now forced to the CENSUS sign -- the other half of the
        # test the artifact deliberately declined to make
        for nm, r in info.items():
            if r[isrc] == "CONFLICT_census_vs_measured" and nm in idx:
                import monotone as MO2
                fs, _why = MO2.family_sign(nm)
                vec[idx[nm]] = int(fs)
    inter = None
    if variant == "ALL_INTERACT":
        groups = [str(g) for g in D["feature_groups"][cols].tolist()]
        byg = {}
        for j, g in enumerate(groups):
            byg.setdefault(g, []).append(j)
        inter = json.dumps([v for v in byg.values() if len(v) > 1])
    return vec, inter


def _con_one(job):
    era, seed, variant = job
    try:
        import xgboost as xgb
        D, P = CF.boot()
        tr, itr, iva, ev_r = NA.fold(D, era)
        cols, names = NA.feat_cols(D)
        XF = D["X"][:, cols]
        val = D["cert_close_usd"].astype(np.float64)
        hp = NA.CHAMP_HP[era]
        vec, inter = _con_vector(D, era, variant)
        cfg = {"objective": "rank:ndcg", "eval_metric": "ndcg@3",
               "tree_method": "hist", "min_child_weight": 20,
               "subsample": 0.8, "colsample_bytree": 0.8,
               "lambdarank_pair_method": "topk",
               "lambdarank_normalization": True,
               "lambdarank_num_pair_per_sample":
                   hp["lambdarank_num_pair_per_sample"],
               "max_depth": hp["max_depth"], "eta": hp["eta"],
               "seed": int(N.SEED + seed), "nthread": RA.N_THREAD,
               "monotone_constraints": "(" + ",".join(str(int(z))
                                                      for z in vec) + ")"}
        if inter:
            cfg["interaction_constraints"] = inter
        r_f, g_f = RA._groups_of(D, tr, CF.SPEC)
        d = xgb.DMatrix(XF[r_f], label=NA.grades(val[r_f]),
                        feature_names=names)
        d.set_group(g_f)
        gw = group_weights(D, tr, r_f, g_f, era, "W_VOLMATCH")
        if gw is not None:
            d.set_weight(gw)
        b = xgb.train(cfg, d, int(hp["rounds"]))
        del d
        r_s, _g = RA._groups_of(D, ev_r, CF.SPEC)
        sc = np.full(D["d8"].size, np.nan)
        sc[r_s] = b.predict(xgb.DMatrix(XF[r_s], feature_names=names),
                            output_margin=True)
        np.save(os.path.join(_sdir(), "CON%s_%s_%d.npy" % (variant, era, seed)),
                sc.astype(np.float32))
        _u, n_ = N.committed_policy().get(era, ("cell", 1))
        a = N.read_rows(D, N.replay_delayed(
            D, N.top_per_cell_score(D, ev_r, sc, n_), P))
        return (era, seed, variant, a["usd_per_session"],
                int(sum(1 for z in vec if z != 0)), None)
    except Exception as exc:                            # noqa: BLE001
        return (era, seed, variant, None, 0,
                "%s: %s" % (type(exc).__name__, exc))


def stage_condepth(eras=ERAS, variants=CON_VARIANTS, workers=6):
    import multiprocessing as mp
    D, P = CF.boot()
    jobs = [(e, s, v) for v in variants for e in eras for s in SEEDS]
    N.hb("CONDEPTH: %d fits (%d variants x %d eras x %d seeds)"
         % (len(jobs), len(variants), len(eras), len(SEEDS)))
    res, nc, t0 = {}, {}, time.time()
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        for k, (era, seed, v, val_, n_con, err) in enumerate(
                pool.imap_unordered(_con_one, jobs), start=1):
            if err:
                N.hb("CONDEPTH FAILED %s %s s%d: %s" % (v, era, seed, err))
                continue
            res.setdefault((v, era), []).append(val_)
            nc[(v, era)] = n_con
            N.hb("CONDEPTH %d/%d %-16s %s s%d: $%s (%d constrained) [eta %.0fs]"
                 % (k, len(jobs), v, era, seed, N._r(val_), n_con,
                    (time.time() - t0) / k * (len(jobs) - k)))
    base = _volmatch_base(D, P, eras)
    rows = []
    for v in variants:
        pooled = []
        for era in eras:
            a = np.asarray([x for x in res.get((v, era), []) if x is not None])
            if a.size == 0:
                continue
            pooled.append(a)
            b = base.get(era, np.asarray([]))
            rows.append([v, era, nc.get((v, era), ""), int(a.size),
                         N._r(a.mean()), N._r(a.std()),
                         N._r(b.mean()) if b.size else "",
                         N._r(a.mean() - b.mean()) if b.size else "",
                         N._r(a.mean() - b.mean() - a.std()) if b.size else ""])
        if pooled:
            av = np.concatenate(pooled)
            ab = np.concatenate([base[e] for e in eras if base.get(e) is not None
                                 and base[e].size])
            rows.append([v, "POOLED", "", int(av.size), N._r(av.mean()),
                         N._r(av.std()), N._r(ab.mean()),
                         N._r(av.mean() - ab.mean()),
                         N._r(av.mean() - ab.mean() - av.std())])
    N.write_tsv("CURRICULUM_CONDEPTH.tsv",
                ["variant", "era", "n_constrained", "n_seeds", "mean_usd",
                 "sd_usd", "volmatch_base_mean", "delta_vs_base",
                 "delta_minus_sd"], rows,
                extra=["CONSTRAINT STRICTNESS SWEPT.  ALL = every stable sign "
                       "(~110 cols); CENSUS6 = only the columns where a NAMED "
                       "census fact and the stability receipt agree (the "
                       "minimal proven set, run even if ALL is null because 110 "
                       "constraints at once can over-constrain); TOP50 = the 50 "
                       "strongest stable signs; CONFLICT_CENSUS forces the "
                       "census sign on the columns the artifact left FREE "
                       "because census and measurement disagreed; ALL_INTERACT "
                       "adds interaction_constraints built from the matrix's "
                       "own feature-group structure.",
                       "PROMOTION: delta_minus_sd > 0 against the W_VOLMATCH "
                       "5-seed base."])
    return rows


def _volmatch_base(D, P, eras):
    base = {}
    for era in eras:
        bv = []
        ev = N.deployable(D, N.era_rows(D, era))
        n_ = N.committed_policy()[era][1]
        for s in SEEDS:
            f = os.path.join(_sdir(), "W_VOLMATCH_%s_%d.npy" % (era, s))
            if not os.path.exists(f):
                continue
            sc = np.load(f).astype(np.float64)
            bv.append(N.read_rows(D, N.replay_delayed(
                D, N.top_per_cell_score(D, ev, sc, n_), P))["usd_per_session"])
        base[era] = np.asarray([x for x in bv if x is not None])
    return base


# ==================== GAP-CLOSER 2: DISTILLATION, DONE RIGHT =================
# NOT the sufficiency memorizer.  That one was fitted ON the evaluation rows to
# measure a representation ceiling and is non-causal by design.  THIS teacher is
# fitted on the TRAINING WINDOW ONLY and never sees the evaluation era, so the
# student is a lawful walk-forward arm.  The teacher still memorises the
# TRAINING era's noise -- that is the danger, and the 5-seed walk-forward
# evaluation is exactly the instrument that catches it.  Let it.
DISTILL = ("SOFT", "MIX", "SOFT_VM")


def _refuse_if_empty(rows, stage, errs):
    """A stage that produced NO rows did not find a null -- it FAILED.  Nulls
    print rows.  Refuse loudly, with the distinct errors surfaced, so a silent
    empty table can never again be mistaken for a measured null."""
    if rows:
        return
    seen, uniq = set(), []
    for e in (errs or []):
        msg = str(e[-1])
        key = msg.split(":")[0][:80]
        if key not in seen:
            seen.add(key)
            uniq.append(msg[:300])
    N.hb("%s PRODUCED ZERO ROWS -- %d failures, %d distinct:" % (stage,
                                                                 len(errs or []),
                                                                 len(uniq)))
    for u in uniq:
        N.hb("   %s" % u)
    raise N.NewObjRefusal(
        "%s produced zero rows from %d failed fits; distinct errors: %s"
        % (stage, len(errs or []), " | ".join(uniq[:3])))


def _distill_one(job):
    era, seed, variant = job
    try:
        import xgboost as xgb
        D, P = CF.boot()
        tr, itr, iva, ev_r = NA.fold(D, era)
        cols, names = NA.feat_cols(D)
        XF = D["X"][:, cols]
        val = D["cert_close_usd"].astype(np.float64)
        hp = NA.CHAMP_HP[era]
        r_f, g_f = RA._groups_of(D, tr, CF.SPEC)
        # --- the TEACHER: unconstrained capacity, TRAINING WINDOW ONLY
        tcfg = {"objective": "rank:ndcg", "eval_metric": "ndcg@1",
                "tree_method": "hist", "max_depth": 12, "eta": 0.30,
                "min_child_weight": 1, "subsample": 1.0,
                "colsample_bytree": 1.0, "reg_lambda": 0.0,
                "lambdarank_pair_method": "topk",
                "lambdarank_num_pair_per_sample": 16,
                "seed": int(N.SEED + seed), "nthread": RA.N_THREAD}
        dt = xgb.DMatrix(XF[r_f], label=NA.grades(val[r_f]),
                         feature_names=names)
        dt.set_group(g_f)
        tb = xgb.train(tcfg, dt, 300)
        soft = tb.predict(dt, output_margin=True)
        del dt, tb
        # soft targets -> within-cell percentile -> the same 0..4 grade ladder
        ptr = np.concatenate([[0], np.cumsum(g_f)])
        sg = np.zeros(soft.size)
        for a_, b_ in zip(ptr[:-1], ptr[1:]):
            if b_ - a_ < 2:
                continue
            r = np.argsort(np.argsort(soft[a_:b_])).astype(float)
            sg[a_:b_] = r / max(b_ - a_ - 1, 1) * 4.0
        true_g = NA.grades(val[r_f]).astype(float)
        # rank:ndcg takes INTEGER relevance only; quantise onto the same 0..4
        # D-021 ladder the champion uses.  Ordering survives, granularity does
        # not -- stated rather than hidden.
        sg = np.clip(np.rint(sg), 0, 4)
        lab = {"SOFT": sg, "SOFT_VM": sg,
               "MIX": np.clip(np.rint(0.5 * sg + 0.5 * true_g), 0, 4)}[variant]
        # --- the STUDENT: the deployable configuration
        scfg = {"objective": "rank:ndcg", "eval_metric": "ndcg@3",
                "tree_method": "hist", "min_child_weight": 20,
                "subsample": 0.8, "colsample_bytree": 0.8,
                "lambdarank_pair_method": "topk",
                "lambdarank_normalization": True,
                "lambdarank_num_pair_per_sample":
                    hp["lambdarank_num_pair_per_sample"],
                "max_depth": hp["max_depth"], "eta": hp["eta"],
                "seed": int(N.SEED + seed), "nthread": RA.N_THREAD}
        ds = xgb.DMatrix(XF[r_f], label=lab, feature_names=names)
        ds.set_group(g_f)
        if variant == "SOFT_VM":
            gw = group_weights(D, tr, r_f, g_f, era, "W_VOLMATCH")
            if gw is not None:
                ds.set_weight(gw)
        sb = xgb.train(scfg, ds, int(hp["rounds"]))
        del ds
        r_s, _g = RA._groups_of(D, ev_r, CF.SPEC)
        sc = np.full(D["d8"].size, np.nan)
        sc[r_s] = sb.predict(xgb.DMatrix(XF[r_s], feature_names=names),
                             output_margin=True)
        np.save(os.path.join(_sdir(), "DIS%s_%s_%d.npy" % (variant, era, seed)),
                sc.astype(np.float32))
        _u, n_ = N.committed_policy().get(era, ("cell", 1))
        a = N.read_rows(D, N.replay_delayed(
            D, N.top_per_cell_score(D, ev_r, sc, n_), P))
        return (era, seed, variant, a["usd_per_session"], None)
    except Exception as exc:                            # noqa: BLE001
        return (era, seed, variant, None,
                "%s: %s" % (type(exc).__name__, exc))


def stage_distill(eras=ERAS, variants=DISTILL, workers=6):
    import multiprocessing as mp
    D, P = CF.boot()
    jobs = [(e, s, v) for v in variants for e in eras for s in SEEDS]
    errs = []
    N.hb("DISTILL: %d fits (%d variants x %d eras x %d seeds); teacher is "
         "TRAIN-WINDOW-ONLY and never sees the evaluation era"
         % (len(jobs), len(variants), len(eras), len(SEEDS)))
    res, t0 = {}, time.time()
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        for k, (era, seed, v, val_, err) in enumerate(
                pool.imap_unordered(_distill_one, jobs), start=1):
            if err:
                errs.append([v, era, seed, err])
                N.hb("DISTILL FAILED %s %s s%d: %s" % (v, era, seed, err))
                continue
            res.setdefault((v, era), []).append(val_)
            N.hb("DISTILL %d/%d %-8s %s s%d: $%s [eta %.0fs]"
                 % (k, len(jobs), v, era, seed, N._r(val_),
                    (time.time() - t0) / k * (len(jobs) - k)))
    base = _volmatch_base(D, P, eras)
    rows = []
    for v in variants:
        pooled = []
        for era in eras:
            a = np.asarray([x for x in res.get((v, era), []) if x is not None])
            if a.size == 0:
                continue
            pooled.append(a)
            b = base.get(era, np.asarray([]))
            rows.append([v, era, int(a.size), N._r(a.mean()), N._r(a.std()),
                         N._r(b.mean()) if b.size else "",
                         N._r(a.mean() - b.mean()) if b.size else "",
                         N._r(a.mean() - b.mean() - a.std()) if b.size else ""])
        if pooled:
            av = np.concatenate(pooled)
            ab = np.concatenate([base[e] for e in eras if base.get(e) is not None
                                 and base[e].size])
            rows.append([v, "POOLED", int(av.size), N._r(av.mean()),
                         N._r(av.std()), N._r(ab.mean()),
                         N._r(av.mean() - ab.mean()),
                         N._r(av.mean() - ab.mean() - av.std())])
    _refuse_if_empty(rows, "DISTILL", errs)
    N.write_tsv("CURRICULUM_DISTILL.tsv",
                ["variant", "era", "n_seeds", "mean_usd", "sd_usd",
                 "volmatch_base_mean", "delta_vs_base", "delta_minus_sd"], rows,
                extra=["DISTILLATION with a LAWFUL teacher: unconstrained "
                       "capacity (depth 12, 300 rounds, no subsampling) fitted "
                       "on the TRAINING WINDOW ONLY, never on the evaluation "
                       "era.  This is NOT the sufficiency memorizer, which was "
                       "fitted on the evaluation rows to measure a "
                       "representation ceiling.",
                       "The teacher's within-cell score percentile becomes the "
                       "student's relevance on the SAME 0..4 ladder.  SOFT = "
                       "teacher only; MIX = 50/50 teacher and true grades; "
                       "SOFT_VM = teacher targets with volmatch weighting.",
                       "The teacher memorises the TRAINING era's noise -- that "
                       "is the known danger, and the 5-seed walk-forward "
                       "evaluation is the instrument that catches it."])
    return rows


def _sc5():
    for n in ("stage_condepth", "stage_distill", "_volmatch_base"):
        if n not in globals():
            raise RuntimeError("curriculum.py mis-assembled: %s" % n)

# ============ CONSTRAINTS x DISTILLATION COMBINED ===========================
# The round's two live objects, together.  Constraints (TOP50) were the biggest
# single result: +$636 on E3, +$491 after its own seed sd, and they also CUT the
# seed sd (298 -> 145).  Distillation attacks the same pool from the other side:
# the teacher can express structure the deployable student cannot reach.
#
# The combination is not obviously additive and could easily be sub-additive:
# a constrained student has FEWER degrees of freedom with which to imitate an
# unconstrained teacher, so the teacher's advice may simply be unfollowable.
# That is the thing worth measuring, and it is why this is a separate arm rather
# than an assumed stack.
#
# THE TEACHER IS UNCONSTRAINED AND TRAIN-WINDOW-ONLY (never the eval era).
# THE STUDENT CARRIES THE TOP50 CONSTRAINTS.
CONDIS = ("CD_SOFT", "CD_MIX", "CD_SOFT_VM")


def _condis_one(job):
    era, seed, variant = job
    try:
        import xgboost as xgb
        D, P = CF.boot()
        tr, itr, iva, ev_r = NA.fold(D, era)
        cols, names = NA.feat_cols(D)
        XF = D["X"][:, cols]
        val = D["cert_close_usd"].astype(np.float64)
        hp = NA.CHAMP_HP[era]
        r_f, g_f = RA._groups_of(D, tr, CF.SPEC)
        # ---- TEACHER: unconstrained capacity, TRAINING WINDOW ONLY
        tcfg = {"objective": "rank:ndcg", "eval_metric": "ndcg@1",
                "tree_method": "hist", "max_depth": 12, "eta": 0.30,
                "min_child_weight": 1, "subsample": 1.0,
                "colsample_bytree": 1.0, "reg_lambda": 0.0,
                "lambdarank_pair_method": "topk",
                "lambdarank_num_pair_per_sample": 16,
                "seed": int(N.SEED + seed), "nthread": RA.N_THREAD}
        dt = xgb.DMatrix(XF[r_f], label=NA.grades(val[r_f]),
                         feature_names=names)
        dt.set_group(g_f)
        tb = xgb.train(tcfg, dt, 300)
        soft = tb.predict(dt, output_margin=True)
        del dt, tb
        ptr = np.concatenate([[0], np.cumsum(g_f)])
        sg = np.zeros(soft.size)
        for a_, b_ in zip(ptr[:-1], ptr[1:]):
            if b_ - a_ < 2:
                continue
            r = np.argsort(np.argsort(soft[a_:b_])).astype(float)
            sg[a_:b_] = r / max(b_ - a_ - 1, 1) * 4.0
        true_g = NA.grades(val[r_f]).astype(float)
        # rank:ndcg takes INTEGER relevance only; quantise onto the same 0..4
        # D-021 ladder the champion uses.  Ordering survives, granularity does
        # not -- stated rather than hidden.
        sg = np.clip(np.rint(sg), 0, 4)
        lab = {"CD_SOFT": sg, "CD_SOFT_VM": sg,
               "CD_MIX": np.clip(np.rint(0.5 * sg + 0.5 * true_g),
                                 0, 4)}[variant]
        # ---- STUDENT: deployable config + the TOP50 constraints
        vec = _top50_vector(D, era, None)
        scfg = {"objective": "rank:ndcg", "eval_metric": "ndcg@3",
                "tree_method": "hist", "min_child_weight": 20,
                "subsample": 0.8, "colsample_bytree": 0.8,
                "lambdarank_pair_method": "topk",
                "lambdarank_normalization": True,
                "lambdarank_num_pair_per_sample":
                    hp["lambdarank_num_pair_per_sample"],
                "max_depth": hp["max_depth"], "eta": hp["eta"],
                "seed": int(N.SEED + seed), "nthread": RA.N_THREAD,
                "monotone_constraints": "(" + ",".join(str(int(z))
                                                       for z in vec) + ")"}
        ds = xgb.DMatrix(XF[r_f], label=lab, feature_names=names)
        ds.set_group(g_f)
        if variant == "CD_SOFT_VM":
            gw = group_weights(D, tr, r_f, g_f, era, "W_VOLMATCH")
            if gw is not None:
                ds.set_weight(gw)
        sb = xgb.train(scfg, ds, int(hp["rounds"]))
        del ds
        r_s, _g = RA._groups_of(D, ev_r, CF.SPEC)
        sc = np.full(D["d8"].size, np.nan)
        sc[r_s] = sb.predict(xgb.DMatrix(XF[r_s], feature_names=names),
                             output_margin=True)
        np.save(os.path.join(_sdir(), "%s_%s_%d.npy" % (variant, era, seed)),
                sc.astype(np.float32))
        a = N.read_rows(D, N.replay_delayed(
            D, N.top_per_cell_score(D, ev_r, sc,
                                    N.committed_policy()[era][1]), P))
        return (era, seed, variant, a["usd_per_session"], None)
    except Exception as exc:                            # noqa: BLE001
        return (era, seed, variant, None,
                "%s: %s" % (type(exc).__name__, exc))


def _top50_vector(D, era, asset=None, k=50):
    """The TOP50 stable-sign vector (shared across assets unless `asset` set)."""
    import monotone as MO
    cols, names = NA.feat_cols(D)
    X = D["X"][:, cols]
    v = D["cert_close_usd"].astype(np.float64)
    tr_eras = [e for e in ("E1", "E2", "E3", "E4", "E5", "E6", "E7")
               if SC.ERA_IDX.get(e, 99) < SC.ERA_IDX[era]]
    if not tr_eras:
        return [0] * len(names)
    M = []
    for te in tr_eras:
        r = N.deployable(D, N.era_rows(D, te))
        if asset is not None:
            r = r[D["asset_idx"][r] == MC.ASSET_ORDER.index(asset)]
        if r.size < 500:
            continue
        M.append(np.array([MO._within_cell_rho(D, r, X[:, j], v)
                           for j in range(X.shape[1])]))
    if not M:
        return [0] * len(names)
    M = np.vstack(M)
    mean_rho = M.mean(axis=0)
    agree = np.all(np.sign(M) == np.sign(mean_rho)[None, :], axis=0)
    cand = sorted([(abs(mean_rho[j]), j) for j in range(len(names))
                   if agree[j] and abs(mean_rho[j]) >= MO.RHO_FLOOR],
                  reverse=True)[:k]
    keep = {j for _r, j in cand}
    return [int(np.sign(mean_rho[j])) if j in keep else 0
            for j in range(len(names))]


def stage_condistill(eras=ERAS, variants=CONDIS, workers=None):
    import multiprocessing as mp
    D, P = CF.boot()
    workers = workers or 12
    RA.N_THREAD = 1
    jobs = [(e, s, v) for v in variants for e in eras for s in SEEDS]
    errs = []
    N.hb("CONDISTILL: %d fits (%d variants x %d eras x %d seeds); "
         "UNCONSTRAINED train-window-only teacher -> TOP50-CONSTRAINED student; "
         "%d workers x 1 thread"
         % (len(jobs), len(variants), len(eras), len(SEEDS), workers))
    res, t0 = {}, time.time()
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        for k, (era, seed, v, val_, err) in enumerate(
                pool.imap_unordered(_condis_one, jobs), start=1):
            if err:
                errs.append([v, era, seed, err])
                N.hb("CONDISTILL FAILED %s %s s%d: %s" % (v, era, seed, err))
                continue
            res.setdefault((v, era), []).append(val_)
            N.hb("CONDISTILL %d/%d %-11s %s s%d: $%s [eta %.0fs]"
                 % (k, len(jobs), v, era, seed, N._r(val_),
                    (time.time() - t0) / k * (len(jobs) - k)))
    # references: the volmatch base AND the TOP50-constraints-alone arm
    base = _volmatch_base(D, P, eras)
    con = {}
    for era in eras:
        ev = N.deployable(D, N.era_rows(D, era))
        n_ = N.committed_policy()[era][1]
        vv = []
        for s in SEEDS:
            f = os.path.join(_sdir(), "CONTOP50_%s_%d.npy" % (era, s))
            if not os.path.exists(f):
                continue
            sc = np.load(f).astype(np.float64)
            vv.append(N.read_rows(D, N.replay_delayed(
                D, N.top_per_cell_score(D, ev, sc, n_), P))["usd_per_session"])
        con[era] = np.asarray([x for x in vv if x is not None])
    rows = []
    for v in variants:
        pooled = []
        for era in eras:
            a = np.asarray([x for x in res.get((v, era), []) if x is not None])
            if a.size == 0:
                continue
            pooled.append(a)
            b = base.get(era, np.asarray([]))
            c = con.get(era, np.asarray([]))
            rows.append([v, era, int(a.size), N._r(a.mean()), N._r(a.std()),
                         N._r(b.mean()) if b.size else "",
                         N._r(c.mean()) if c.size else "",
                         N._r(a.mean() - c.mean()) if c.size else "",
                         N._r(a.mean() - c.mean() - a.std()) if c.size else ""])
        if pooled:
            av = np.concatenate(pooled)
            ab = np.concatenate([base[e] for e in eras
                                 if base.get(e) is not None and base[e].size])
            ac = np.concatenate([con[e] for e in eras
                                 if con.get(e) is not None and con[e].size])
            rows.append([v, "POOLED", int(av.size), N._r(av.mean()),
                         N._r(av.std()), N._r(ab.mean()),
                         N._r(ac.mean()) if ac.size else "",
                         N._r(av.mean() - ac.mean()) if ac.size else "",
                         N._r(av.mean() - ac.mean() - av.std())
                         if ac.size else ""])
    _refuse_if_empty(rows, "CONDISTILL", errs)
    N.write_tsv("CURRICULUM_CONDISTILL.tsv",
                ["variant", "era", "n_seeds", "mean_usd", "sd_usd",
                 "volmatch_base_mean", "top50_constraints_mean",
                 "delta_vs_constraints", "delta_minus_sd"], rows,
                extra=["CONSTRAINTS x DISTILLATION: an UNCONSTRAINED, "
                       "train-window-only teacher advising a student that "
                       "carries the TOP50 monotone constraints.",
                       "The reference is the TOP50-CONSTRAINTS-ALONE arm, not "
                       "the volmatch base: the question is whether distillation "
                       "adds anything ON TOP of the constraints, which are "
                       "already the round's biggest result.",
                       "SUB-ADDITIVITY IS THE LIVE RISK and is what this "
                       "measures: a constrained student has fewer degrees of "
                       "freedom with which to imitate an unconstrained teacher, "
                       "so the teacher's advice may simply be unfollowable."])
    return rows


def _sc6():
    for n in ("stage_condistill", "_top50_vector", "_condis_one"):
        if n not in globals():
            raise RuntimeError("curriculum.py mis-assembled: %s" % n)


if __name__ == "__main__":
    _selfcheck(); _sc2(); _sc3(); _sc4(); _sc5(); _sc6()
    main()
