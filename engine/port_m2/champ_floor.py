#!/usr/bin/python3
"""PORT M2 — THE CHAMPION'S OWN NOISE FLOOR (the number the freeze stands on).

WHY THIS EXISTS.  The ranking atlas produced an arm that beat the champion by
+$524.88/session (Holm-significant) and cleared $2,000 on all three assets in the
E8 blind read.  Its own noise floor then RETRACTED it: 15 members that are the
SAME configuration at different seeds/training windows have member means of
$182.21 / $416.61 / $825.97 on E3/E5/E7 against the single fit's $1,501.79, with
per-era ranges of $516-707.  The arm was substantially a lucky fit.

That verdict cuts both ways, and this module is the other cut: **the champion has
never had its own floor measured either.**  Every per-era figure in
CHAMPION_FREEZE_CANDIDATE.md is a SINGLE FIT.  If the champion's floor is tight,
it freezes with honest error bars; if it is as loose as the atlas arm's, the
whole per-era table needs fit-variance bars and the holdout decision changes
character.

THE SPEC MEASURED HERE IS THE FROZEN ONE, EXACTLY:
  * the 184 non-`tf_` columns (no CELLREL, no inflation);
  * `rank:ndcg` / `ndcg@3`, `lambdarank_pair_method topk`,
    `lambdarank_normalization`, `min_child_weight 20`, `subsample 0.8`,
    `colsample_bytree 0.8`;
  * the champion's OWN per-era `max_depth` / `eta` /
    `lambdarank_num_pair_per_sample` / round count (§2.5, inner-selected);
  * cell grouping, D-077 veto before grouping, m3's committed per-era (unit, N),
    `replay_delayed` at D=0 (proved seat-for-seat against `m3_walk.replay_rows`).
Only the SEED and the TRAINING WINDOW vary -- the two things a deployment would
not get to choose.

E8 IS SPENT for this family and is not fitted here.  The 2025-H2 holdout stays
sealed.
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
import risk_panel as RP                   # noqa: E402
import st_common as SC                    # noqa: E402
import m2_common as MC                    # noqa: E402

ERAS = N.DEV_ERAS
SEEDS = (0, 1, 2, 3, 4)
WINDOWS = ("PRE_E1", "E1", "E2")
SPEC = {"group": "cell", "obj": "ndcg3", "target": "dollars", "pop": "full",
        "engine": "xgb", "feat": "BASE"}

_ST = {}


def boot():
    if "D" not in _ST:
        import st_rank as RK
        D = N.matrix()
        RA._D["D"] = D
        RA._D["klass"] = RK.class_index(D)[0]
        _ST["D"] = D
        _ST["P"] = N.load_paths()
    return _ST["D"], _ST["P"]


def members_path():
    return os.path.join(N.OUT_ROOT, "champ_floor_members.jsonl")


def scores_path(era, seed, window):
    d = os.path.join(N.OUT_ROOT, "champ_floor_scores")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "%s_%d_%s.npy" % (era, seed, window))


def fit_member(D, P, era, seed, window):
    """ONE champion member: its frozen config, this seed, this training window."""
    import xgboost as xgb
    tr, itr, iva, ev_r = NA.fold(D, era)
    if window != "PRE_E1":
        tr = tr[D["era_idx"][tr] >= SC.ERA_IDX[window]]
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
    r_f, g_f = RA._groups_of(D, tr, SPEC)
    d = xgb.DMatrix(XF[r_f], label=NA.grades(val[r_f]), feature_names=names)
    d.set_group(g_f)
    b = xgb.train(cfg, d, int(hp["rounds"]))
    del d
    r_s, _g = RA._groups_of(D, ev_r, SPEC)
    sc = np.full(D["d8"].size, np.nan)
    sc[r_s] = b.predict(xgb.DMatrix(XF[r_s], feature_names=names),
                        output_margin=True)
    return sc, ev_r


def _one(job):
    era, seed, window = job
    try:
        D, P = boot()
        t0 = time.time()
        sc, ev_r = fit_member(D, P, era, seed, window)
        np.save(scores_path(era, seed, window), sc.astype(np.float32))
        _u, n_ = N.committed_policy().get(era, ("cell", 1))
        a = N.read_rows(D, N.replay_delayed(
            D, N.top_per_cell_score(D, ev_r, sc, n_), P))
        per = {}
        for ai in sorted(set(D["asset_idx"][ev_r].tolist())):
            sel = ev_r[D["asset_idx"][ev_r] == ai]
            aa = N.read_rows(D, N.replay_delayed(
                D, N.top_per_cell_score(D, sel, sc, n_), P))
            per[MC.ASSET_ORDER[ai]] = aa["usd_per_session"]
        return (era, seed, window,
                {"usd_per_session": a["usd_per_session"],
                 "n_seated": a["n_seated"], "per_asset": per,
                 "secs": round(time.time() - t0, 1)}, None)
    except Exception as exc:                            # noqa: BLE001
        return (era, seed, window, None,
                "%s: %s" % (type(exc).__name__, exc))


def stage_floor(eras=ERAS, seeds=SEEDS, windows=WINDOWS, workers=None):
    import multiprocessing as mp
    import resource
    D, P = boot()
    try:
        lim = int(open("/sys/fs/cgroup/memory.max").read()) / 1e9
        cur = int(open("/sys/fs/cgroup/memory.current").read()) / 1e9
    except Exception:                                   # noqa: BLE001
        lim, cur = 260.0, 0.0
    t0 = time.time()
    N.hb("champ floor: measuring one member's footprint before sizing the pool")
    sc0, ev0 = fit_member(D, P, eras[0], 0, "PRE_E1")
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6
    free = max(lim - cur, 20.0)
    w_mem = max(1, int(free * 0.60 / max(rss, 1.0)))
    workers = int(workers or min(6, w_mem))
    N.hb("champ floor: member RSS %.1f GB, cgroup %.0f GB (%.0f used) -> %d by "
         "memory, using %d (%.0fs)"
         % (rss, lim, cur, w_mem, workers, time.time() - t0))
    jobs = [(e, s, w) for e in eras for s in seeds for w in windows]
    N.hb("champ floor: %d member fits (%d seeds x %d windows x %d eras); "
         "incremental writes to %s" % (len(jobs), len(seeds), len(windows),
                                       len(eras), members_path()))
    open(members_path(), "w").close()
    res, errs = {}, []
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        for k, (era, seed, window, out, err) in enumerate(
                pool.imap_unordered(_one, jobs), start=1):
            if err:
                errs.append([era, seed, window, err])
                N.hb("champ floor %d/%d MEMBER FAILED %s s%d %s: %s"
                     % (k, len(jobs), era, seed, window, err))
                continue
            res[(era, seed, window)] = out
            with open(members_path(), "a") as fh:
                fh.write(json.dumps({"era": era, "seed": seed,
                                     "window": window, **out}) + "\n")
            N.hb("champ floor MEMBER %d/%d %s seed=%d window=%-6s: "
                 "$%s/session (%d seats) [%.0fs, eta %.0fs]"
                 % (k, len(jobs), era, seed, window,
                    N._r(out["usd_per_session"]), out["n_seated"],
                    time.time() - t0,
                    (time.time() - t0) / k * (len(jobs) - k)))
    # ---------------- the floor table, and both ensemble constructions --------
    rows, ens_rows, panel_rows = [], [], []
    committed = N.champ_score()
    for era in eras:
        vals = [res[(era, s, w)]["usd_per_session"]
                for s in seeds for w in windows if (era, s, w) in res]
        vals = [v for v in vals if v is not None]
        if not vals:
            continue
        a = np.asarray(vals, dtype=np.float64)
        ev_r = N.deployable(D, N.era_rows(D, era))
        cm = N.read_rows(D, N.replay_delayed(
            D, N.top_per_cell_score(D, ev_r,
                                    committed,
                                    N.committed_policy()[era][1]), P))
        rows.append([era, "ALL", len(a), N._r(a.mean()), N._r(a.std()),
                     N._r(a.max() - a.min()), N._r(a.min()), N._r(a.max()),
                     N._r(np.percentile(a, 10)), N._r(np.percentile(a, 90)),
                     N._r(cm["usd_per_session"])])
        for asset in MC.ASSET_ORDER:
            pv = [res[(era, s, w)]["per_asset"].get(asset)
                  for s in seeds for w in windows if (era, s, w) in res]
            pv = np.asarray([v for v in pv if v is not None], dtype=np.float64)
            if pv.size == 0:
                continue
            sel = ev_r[D["asset_idx"][ev_r] == MC.ASSET_ORDER.index(asset)]
            cma = N.read_rows(D, N.replay_delayed(
                D, N.top_per_cell_score(D, sel, committed,
                                        N.committed_policy()[era][1]), P))
            rows.append([era, asset, int(pv.size), N._r(pv.mean()),
                         N._r(pv.std()), N._r(pv.max() - pv.min()),
                         N._r(pv.min()), N._r(pv.max()),
                         N._r(np.percentile(pv, 10)),
                         N._r(np.percentile(pv, 90)),
                         N._r(cma["usd_per_session"])])
        # BOTH ensemble constructions on the same members
        S = [np.load(scores_path(era, s, w))
             for s in seeds for w in windows if (era, s, w) in res]
        smean = np.nanmean(np.vstack([x.astype(np.float64) for x in S]), axis=0)
        pmean = np.zeros(D["d8"].size)
        cnt = np.zeros(D["d8"].size)
        for x in S:
            pc = RA._pct_within_cell(D, ev_r, x.astype(np.float64)) \
                if hasattr(RA, "_pct_within_cell") else None
            if pc is None:
                import harvest as HV
                pc = HV._pct_within_cell(D, ev_r, x.astype(np.float64))
            ok = np.isfinite(pc)
            pmean[ok] += pc[ok]
            cnt[ok] += 1
        pmean = np.where(cnt > 0, pmean / np.maximum(cnt, 1), np.nan)
        n_ = N.committed_policy()[era][1]
        for nm, col in (("SCORE_MEAN", smean), ("PERCENTILE_MEAN", pmean)):
            aa = N.read_rows(D, N.replay_delayed(
                D, N.top_per_cell_score(D, ev_r, col, n_), P))
            ens_rows.append([era, nm, N._r(a.mean()),
                             N._r(aa["usd_per_session"]), N._r(aa["ps_lo"]),
                             N._r(aa["ps_hi"]),
                             N._r((aa["usd_per_session"] or 0) - a.mean()),
                             aa["n_seated"], N._r(cm["usd_per_session"])])
        RP.panel_for_score(D, P, smean, "CHAMPION_ENSEMBLE_SCOREMEAN", (era,),
                           panel_rows)
        N.hb("champ floor %s: members mean $%.2f sd $%.2f range $%.2f | "
             "committed single fit $%s" % (era, a.mean(), a.std(),
                                           a.max() - a.min(),
                                           N._r(cm["usd_per_session"])))
    N.write_tsv("CHAMPION_FLOOR.tsv",
                ["era", "asset", "n_members", "member_mean", "member_sd",
                 "member_range", "member_min", "member_max", "member_p10",
                 "member_p90", "committed_single_fit"], rows,
                extra=["THE CHAMPION'S OWN FIT-VARIANCE, at its EXACT frozen "
                       "configuration.  Only the SEED and the TRAINING WINDOW "
                       "vary -- the two things a deployment does not get to "
                       "choose.  %d members = %d seeds x %d windows."
                       % (len(seeds) * len(windows), len(seeds), len(windows)),
                       "`committed_single_fit` is the number "
                       "CHAMPION_FREEZE_CANDIDATE.md currently quotes.  Where "
                       "it sits far above member_mean, the quoted figure is a "
                       "draw from this distribution rather than its centre.",
                       "This is the measurement that retracted the ranking "
                       "atlas's winning arm; it is applied to the incumbent on "
                       "the same terms."])
    N.write_tsv("CHAMPION_FLOOR_ENSEMBLE.tsv",
                ["era", "construction", "member_mean", "ensemble_usd", "lo",
                 "hi", "delta_vs_member_mean", "n_seated",
                 "committed_single_fit"], ens_rows,
                extra=["BOTH ensemble constructions on the SAME members: "
                       "SCORE_MEAN averages the raw margins (comparable across "
                       "seeds of one configuration), PERCENTILE_MEAN averages "
                       "the within-cell percentile.  The atlas ensemble used "
                       "the percentile form and it hurt; reporting both here "
                       "separates the construction from the effect."])
    RP.write(panel_rows, "RISK_PANEL_CHAMPION_ENSEMBLE.tsv",
             extra=["arm = the champion's SCORE-MEAN ensemble over %d members"
                    % (len(seeds) * len(windows))])
    N.save_json("champ_floor.json", {"errors": errs, "workers": workers,
                                     "member_rss_gb": rss,
                                     "secs": round(time.time() - t0, 1)})
    return rows


def _selfcheck():
    for n in ("stage_floor", "fit_member", "_one"):
        if n not in globals():
            raise RuntimeError("champ_floor.py mis-assembled: %s missing" % n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--eras", default=",".join(ERAS))
    ap.add_argument("--workers", type=int, default=None)
    a = ap.parse_args()
    if a.run:
        stage_floor(eras=tuple(e for e in a.eras.split(",") if e),
                    workers=a.workers)
    else:
        ap.print_help()


if __name__ == "__main__":
    _selfcheck()
    main()
