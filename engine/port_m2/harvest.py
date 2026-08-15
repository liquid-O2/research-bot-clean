#!/usr/bin/python3
"""PORT M2 — THE HARVEST ROUND on the atlas's winning arm.

WHAT IS BEING HARVESTED, stated precisely, because the arm's name is misleading.
The atlas winner is `joint|dpairs|dollars|full|xgb|CELLREL` -- but its money is
NOT the timing freedom.  Three independent measurements say so:

  * its own oracle on the identical block: joint $2,864.17 vs member $2,731.92
    at IDENTICAL seat counts -- a +$132 ceiling against a +$752 claimed lift;
  * the decomposition: exercising the delay is worth -$23.14 / -$18.16 / +$3.55
    (mean **-$12.58**/session) on E3/E5/E7;
  * a 5x DUPLICATION control carrying NO delay information reproduces most of
    the lift ($303.56 / $872.95 / $596.07).

So the deployable object is **train on an INFLATED design, execute at the
confirmation second**.  No delayed execution, no contract change.  That also
means the two arbitrary numbers inside it -- the 5x inflation and
`lambdarank_num_pair_per_sample=16` -- are the actual knobs, and neither was
ever chosen.  Both plausibly do the same thing (more sampled pairs per group),
which is why the sweep crosses them: if the pair budget alone recovers the gain,
the arm gets 5-10x CHEAPER as well as better.

FOUR TREATMENTS (coordinator, E3-E7 ONLY -- E8 is spent for this family and the
2025-H2 holdout stays sealed as the final validator):
  1 ENSEMBLE   seeds x training-window variants, score-averaged
  2 SWEEP      inflation {1,3,5,8,10} x pairs {4,8,16,32}
  3 ABSTAIN    threshold on the arm's own score, inner-selected per era
  4 META       a secondary veto retrained on the NEW arm's takes

One-change receipts, a shuffled control per treatment, ledger decompositions,
and the per-era x per-asset table reported prominently against the $2,000 bar.
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
import atlas_feat as AF                   # noqa: E402
import st_common as SC                    # noqa: E402
import m2_common as MC                    # noqa: E402

ERAS = N.DEV_ERAS                          # E3-E7.  E8 is SPENT for this family.
WEAK = ("E3", "E5", "E7")
BAR = 2000.0

# the arm, as the atlas left it
ARM = {"group": "cell", "obj": "dpairs", "target": "dollars", "pop": "full",
       "engine": "xgb", "feat": "CELLREL"}
INFLATE = (1, 3, 5, 8, 10)
PAIRS = (4, 8, 16, 32)

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


def fit_arm(D, P, era, inflate=5, pairs=16, seed=None, from_era="PRE_E1",
            shuffle=False, budget=None, feat="CELLREL", ret_model=False):
    """The harvested arm: cell-grouped dollar-weighted pairs on an INFLATED
    design, seated at the confirmation second (D=0).

    `inflate` duplicates every training row k times inside its own cell, which
    is what the joint design was doing accidentally; `pairs` is the per-document
    pair-sampling budget.  Both were arbitrary in the arm that won the atlas.
    """
    import xgboost as xgb
    spec = dict(ARM)
    spec["feat"] = feat
    B = budget or dict(RA.SCREEN)
    tr, itr, iva, ev_r = NA.fold(D, era)
    if from_era != "PRE_E1":
        tr = tr[D["era_idx"][tr] >= SC.ERA_IDX[from_era]]
        itr = itr[D["era_idx"][itr] >= SC.ERA_IDX[from_era]]
    XF, FN = RA.build_features(D, spec, tr, np.arange(D["d8"].size))
    val = RA.target_value(D, spec)
    if shuffle:
        rs = np.random.RandomState(N.SEED + 771 + SC.ERA_IDX[era])
        val = val.copy()
        val[tr] = val[tr][rs.permutation(tr.size)]
    r_f, g_f = RA._groups_of(D, tr, spec)
    if inflate > 1:
        r_f = np.repeat(r_f, inflate)
        g_f = g_f * inflate
    y = val[r_f]
    ptr = np.concatenate([[0], np.cumsum(g_f)])
    gw = np.array([max(0.0, float(np.max(np.maximum(y[a:b], 0.0))
                                  - np.median(np.maximum(y[a:b], 0.0))))
                   for a, b in zip(ptr[:-1], ptr[1:])]) / 1000.0
    gw = np.clip(gw, 0.05, 5.0)
    hp = NA.CHAMP_HP[era]
    cfg = {"objective": "rank:pairwise", "eval_metric": "ndcg@3",
           "tree_method": "hist", "min_child_weight": 20, "subsample": 0.8,
           "colsample_bytree": 0.8, "lambdarank_pair_method": "topk",
           "lambdarank_num_pair_per_sample": int(pairs),
           "seed": int(seed if seed is not None else N.SEED),
           "nthread": RA.N_THREAD, "max_depth": hp["max_depth"],
           "eta": hp["eta"]}
    d = xgb.DMatrix(XF[r_f], label=NA.grades(y), feature_names=FN)
    d.set_group(g_f)
    d.set_weight(gw)
    b = xgb.train(cfg, d, int(B.get("rounds", hp["rounds"])))
    del d
    sc = np.full(D["d8"].size, np.nan)
    r_s, _g = RA._groups_of(D, ev_r, spec)
    sc[r_s] = b.predict(xgb.DMatrix(XF[r_s], feature_names=FN),
                        output_margin=True)
    sc_iva = np.full(D["d8"].size, np.nan)
    r_v, _gv = RA._groups_of(D, iva, spec)
    sc_iva[r_v] = b.predict(xgb.DMatrix(XF[r_v], feature_names=FN),
                            output_margin=True)
    if ret_model:
        return sc, sc_iva, ev_r, iva, tr, XF, FN, val, b
    return sc, sc_iva, ev_r, iva


def seat(D, P, ev_rows, sc, era):
    _u, n_ = N.committed_policy().get(era, ("cell", 1))
    return N.read_rows(D, N.replay_delayed(
        D, N.top_per_cell_score(D, ev_rows, sc, n_), P))


def per_asset(D, P, ev_rows, sc, era):
    out = {}
    for ai in sorted(set(D["asset_idx"][ev_rows].tolist())):
        sel = ev_rows[D["asset_idx"][ev_rows] == ai]
        out[MC.ASSET_ORDER[ai]] = seat(D, P, sel, sc, era)
    return out


# ============================================================ 2: THE SWEEP ====
def _sweep_one(job):
    inflate, pairs, era, shuffle = job
    try:
        D, P = boot()
        t0 = time.time()
        sc, _si, ev_r, _iva = fit_arm(D, P, era, inflate=inflate, pairs=pairs,
                                      shuffle=shuffle)
        a = seat(D, P, ev_r, sc, era)
        return (inflate, pairs, era, shuffle,
                {"usd": a["usd_per_session"], "lo": a["ps_lo"],
                 "hi": a["ps_hi"], "seats": a["n_seated"],
                 "secs": round(time.time() - t0, 1)}, None)
    except Exception as exc:                            # noqa: BLE001
        return (inflate, pairs, era, shuffle, None,
                "%s: %s" % (type(exc).__name__, exc))


def stage_sweep(eras=WEAK, workers=None):
    """TREATMENT 2 -- sweep the two numbers nobody chose."""
    import multiprocessing as mp
    boot()
    workers = workers or RA.N_WORKERS
    jobs = [(i, p, e, False) for i in INFLATE for p in PAIRS for e in eras]
    # the shuffled control runs at the arm's own reference setting only
    jobs += [(5, 16, e, True) for e in eras]
    N.hb("sweep: %d fits (%d configs x %d eras + controls), workers=%d"
         % (len(jobs), len(INFLATE) * len(PAIRS), len(eras), workers))
    res, errs = {}, []
    t0 = time.time()
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        for k, (i, p, e, sh, out, err) in enumerate(
                pool.imap_unordered(_sweep_one, jobs), start=1):
            if err:
                errs.append([i, p, e, int(sh), err])
                N.hb("sweep FAIL %sx/%s %s: %s" % (i, p, e, err))
                continue
            res[(i, p, e, sh)] = out
            N.hb("sweep %d/%d inflate=%dx pairs=%d %s%s: $%s/session (%.0fs, "
                 "eta %.0fs)" % (k, len(jobs), i, p, e,
                                 " SHUF" if sh else "", N._r(out["usd"]),
                                 out["secs"],
                                 (time.time() - t0) / k * (len(jobs) - k)))
    rows = []
    for i in INFLATE:
        for p in PAIRS:
            vals = [res[(i, p, e, False)]["usd"] for e in eras
                    if (i, p, e, False) in res]
            if not vals:
                continue
            rows.append([i, p, len(vals), N._r(float(np.mean(vals))),
                         *[N._r(res.get((i, p, e, False), {}).get("usd"))
                           for e in eras]])
    rows.sort(key=lambda r: -(r[3] if isinstance(r[3], float) else -1e9))
    sh_vals = [res[(5, 16, e, True)]["usd"] for e in eras
               if (5, 16, e, True) in res]
    N.write_tsv("HARVEST_SWEEP.tsv",
                ["inflate_x", "pairs_per_sample", "n_eras", "mean_usd",
                 *["usd_%s" % e for e in eras]], rows,
                extra=["TREATMENT 2: the two arbitrary numbers inside the "
                       "winning arm, swept.  Training-design inflation and the "
                       "per-document pair-sampling budget plausibly do the SAME "
                       "thing (more sampled pairs per group); if the pair "
                       "budget alone recovers the gain the arm gets 5-10x "
                       "cheaper as well as better.",
                       "Screen budget, cell grouping, dollar-weighted pairs, "
                       "CELLREL features, seated at D=0 (the confirmation "
                       "second).  E3-E7 only; E8 is spent for this family.",
                       "shuffled control at the reference setting (5x/16): %s"
                       % ", ".join("%s=%s" % (e, N._r(v))
                                   for e, v in zip(eras, sh_vals))])
    N.save_json("harvest_sweep.json",
                {"results": {"%d|%d|%s|%d" % k: v for k, v in res.items()},
                 "errors": errs, "secs": round(time.time() - t0, 1)})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--ensemble", action="store_true")
    ap.add_argument("--abstain", action="store_true")
    ap.add_argument("--inflate", type=int, default=5)
    ap.add_argument("--pairs", type=int, default=16)
    ap.add_argument("--eras", default=",".join(WEAK))
    ap.add_argument("--workers", type=int, default=None)
    a = ap.parse_args()
    eras = tuple(e for e in a.eras.split(",") if e)
    if a.sweep:
        stage_sweep(eras=eras, workers=a.workers)
    elif a.ensemble:
        stage_ensemble(eras=eras, inflate=a.inflate, pairs=a.pairs,
                       workers=a.workers)
    elif a.abstain:
        stage_abstain(eras=eras, inflate=a.inflate, pairs=a.pairs)
    else:
        ap.print_help()



# ======================================================== 1: THE ENSEMBLE =====
def _ens_one(job):
    seed, from_era, era, inflate, pairs = job
    try:
        D, P = boot()
        sc, sc_iva, ev_r, iva = fit_arm(D, P, era, inflate=inflate,
                                        pairs=pairs, seed=seed,
                                        from_era=from_era)
        return (seed, from_era, era, sc, sc_iva, ev_r, iva, None)
    except Exception as exc:                            # noqa: BLE001
        return (seed, from_era, era, None, None, None, None,
                "%s: %s" % (type(exc).__name__, exc))


def _pct_within_cell(D, rows, s):
    """Within-cell percentile, so fits on different scales can be averaged."""
    out = np.full(D["d8"].size, np.nan)
    ro, blocks = N.cell_blocks(D, rows)
    v = np.asarray(s)[ro]
    for a, b in blocks:
        idx = np.arange(a, b)
        ok = idx[np.isfinite(v[idx])]
        if ok.size == 0:
            continue
        r = np.argsort(np.argsort(v[ok], kind="stable"), kind="stable")
        out[ro[ok]] = (r + 0.5) / ok.size
    return out


def _member_path():
    return os.path.join(N.OUT_ROOT, "harvest_ensemble_members.jsonl")


def stage_ensemble(eras=WEAK, inflate=5, pairs=16, seeds=(0, 1, 2, 3, 4),
                   windows=("PRE_E1", "E1", "E2"), workers=None):
    """TREATMENT 1 -- seeds x training windows, SCORE-AVERAGED, and the arm's
    NOISE FLOOR.

    Averaging is on the WITHIN-CELL PERCENTILE of each member's score: different
    fits put their margins on different scales and only the within-cell ORDER is
    ever spent, so the percentile is the only scale on which an average means
    anything.

    Every member's result is written to a JSONL file AS IT COMPLETES and every
    member emits a heartbeat line, so a hang can never again strand results in
    memory and "is it running" is answerable from the hb file alone.

    The pool is sized from a MEASURED member RSS against the cgroup limit -- the
    host's free RAM is not the quota, and the last sweep was OOM-killed for
    assuming otherwise.
    """
    import multiprocessing as mp
    import resource
    D, P = boot()
    lim = 260.0
    try:
        lim = int(open("/sys/fs/cgroup/memory.max").read()) / 1e9
        cur = int(open("/sys/fs/cgroup/memory.current").read()) / 1e9
    except Exception:                                   # noqa: BLE001
        cur = 0.0
    t0 = time.time()
    N.hb("ensemble: measuring one member's footprint before sizing the pool")
    sc0, _si, ev0, _iva = fit_arm(D, P, eras[0], inflate=inflate, pairs=pairs,
                                  seed=N.SEED)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6
    a0 = seat(D, P, ev0, sc0, eras[0])
    free = max(lim - cur, 20.0)
    w_mem = max(1, int(free * 0.60 / max(rss, 1.0)))
    workers = int(workers or min(4, w_mem, RA.N_WORKERS))
    N.hb("ensemble: member RSS %.1f GB, cgroup %.0f GB (%.0f used, %.0f free) "
         "-> %d workers by memory, using %d; first member $%s (%.0fs)"
         % (rss, lim, cur, free, w_mem, workers, N._r(a0["usd_per_session"]),
            time.time() - t0))
    jobs = [(N.SEED + s, w, e, inflate, pairs)
            for s in seeds for w in windows for e in eras]
    N.hb("ensemble: %d member fits (%d seeds x %d windows x %d eras), "
         "incremental writes to %s"
         % (len(jobs), len(seeds), len(windows), len(eras), _member_path()))
    open(_member_path(), "w").close()
    members, errs = {}, []
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        for k, (sd, w, e, sc, sc_iva, ev_r, iva, err) in enumerate(
                pool.imap_unordered(_ens_one, jobs), start=1):
            if err:
                errs.append([sd, w, e, err])
                N.hb("ensemble %d/%d MEMBER FAILED seed=%s window=%s %s: %s"
                     % (k, len(jobs), sd, w, e, err))
                continue
            a = seat(D, P, ev_r, sc, e)
            members.setdefault(e, []).append((sd, w, sc, ev_r))
            rec = {"seed": int(sd), "window": w, "era": e,
                   "usd_per_session": a["usd_per_session"],
                   "n_seated": a["n_seated"], "k": k, "of": len(jobs),
                   "elapsed_s": round(time.time() - t0, 1)}
            with open(_member_path(), "a") as fh:       # INCREMENTAL WRITE
                fh.write(json.dumps(rec) + "\n")
            N.hb("ensemble MEMBER %d/%d seed=%d window=%-6s %s: $%s/session "
                 "(%d seats) [%.0fs elapsed, eta %.0fs]"
                 % (k, len(jobs), sd, w, e, N._r(a["usd_per_session"]),
                    a["n_seated"], time.time() - t0,
                    (time.time() - t0) / k * (len(jobs) - k)))
    rows, per_era = [], {}
    for era in eras:
        ms = members.get(era, [])
        if not ms:
            continue
        ev_r = ms[0][3]
        mem_usd = [seat(D, P, ev_r, sc, era)["usd_per_session"]
                   for _sd, _w, sc, _ev in ms]
        mem_usd = [v for v in mem_usd if v is not None]
        spread = float(np.std(mem_usd)) if len(mem_usd) > 1 else float("nan")
        rng = (max(mem_usd) - min(mem_usd)) if len(mem_usd) > 1 else float("nan")
        base = float(np.mean(mem_usd)) if mem_usd else None
        N.hb("ensemble %s NOISE FLOOR: %d members, mean $%.2f, sd $%.2f, "
             "range $%.2f (min $%.2f max $%.2f)"
             % (era, len(mem_usd), base, spread, rng, min(mem_usd),
                max(mem_usd)))
        acc = np.zeros(D["d8"].size)
        cnt = np.zeros(D["d8"].size)
        for _sd, _w, sc, _ev in ms:
            pc = _pct_within_cell(D, ev_r, sc)
            ok = np.isfinite(pc)
            acc[ok] += pc[ok]
            cnt[ok] += 1
        avg = np.where(cnt > 0, acc / np.maximum(cnt, 1), np.nan)
        a = seat(D, P, ev_r, avg, era)
        per_era[era] = a
        rows.append([era, len(ms), N._r(base), N._r(a["usd_per_session"]),
                     N._r(a["ps_lo"]), N._r(a["ps_hi"]),
                     N._r((a["usd_per_session"] or 0) - (base or 0)),
                     a["n_seated"], N._r(spread), N._r(rng)])
        for asset, aa in per_asset(D, P, ev_r, avg, era).items():
            rows.append(["%s|%s" % (era, asset), len(ms), "",
                         N._r(aa["usd_per_session"]), N._r(aa["ps_lo"]),
                         N._r(aa["ps_hi"]), "", aa["n_seated"], "", ""])
    q = N.pool_reads([per_era[e] for e in eras if e in per_era])
    rows.append(["POOLED", "", "", N._r(q.get("usd_per_session")),
                 N._r(q.get("ps_lo")), N._r(q.get("ps_hi")), "",
                 q.get("n_seated"), "", ""])
    N.write_tsv("HARVEST_ENSEMBLE.tsv",
                ["era", "n_members", "member_mean_usd", "ensemble_usd", "lo",
                 "hi", "delta_vs_member_mean", "n_seated", "member_sd",
                 "member_range"], rows,
                extra=["TREATMENT 1: %d seeds x %d training windows at the "
                       "arm's own configuration (inflate=%dx, pairs=%d), "
                       "averaged on the WITHIN-CELL PERCENTILE."
                       % (len(seeds), len(windows), inflate, pairs),
                       "member_sd / member_range are THE NOISE FLOOR: every "
                       "member is the SAME configuration at a different "
                       "seed/window, so their spread is pure fit noise.  The "
                       "sweep's config-to-config differences, and the atlas "
                       "arm's +$524.88 over the champion, can only be believed "
                       "to the extent they EXCEED it.",
                       "Rows of the form ERA|ASSET are the per-asset table "
                       "against the $%d bar." % int(BAR)])
    N.save_json("harvest_ensemble.json",
                {"errors": errs, "workers": workers, "member_rss_gb": rss,
                 "secs": round(time.time() - t0, 1)})
    return rows


# ======================================================= 3: THE ABSTENTION ====
def stage_abstain(eras=ERAS, inflate=5, pairs=16):
    """TREATMENT 3 -- a plain threshold on the arm's OWN score, inner-selected.

    The verify census showed the +$550-class work is done by ABSTENTION, not by
    a post-window gate.  This is the cheapest possible abstainer: no second
    model, no new information, one number per era chosen on the inner block.
    """
    D, P = boot()
    rows = []
    per_era_on, per_era_off = {}, {}
    for era in eras:
        sc, sc_iva, ev_r, iva = fit_arm(D, P, era, inflate=inflate, pairs=pairs)
        _u, n_ = N.committed_policy().get(era, ("cell", 1))
        iva_dep = N.deployable(D, iva)
        base = seat(D, P, ev_r, sc, era)
        per_era_off[era] = base
        qs = np.nanpercentile(sc_iva[np.isfinite(sc_iva)],
                              np.arange(0, 96, 5))
        best_tau, best_v = -np.inf, -np.inf
        for tau in np.concatenate([[-np.inf], qs]):
            tk = [(i, d) for (i, d) in
                  N.top_per_cell_score(D, iva_dep, sc_iva, n_)
                  if sc_iva[i] >= tau]
            v = N.read_rows(D, N.replay_delayed(D, tk, P)).get(
                "usd_per_session")
            if v is not None and v > best_v:
                best_tau, best_v = tau, v
        tk = [(i, d) for (i, d) in N.top_per_cell_score(D, ev_r, sc, n_)
              if sc[i] >= best_tau]
        a = N.read_rows(D, N.replay_delayed(D, tk, P))
        per_era_on[era] = a
        wk = a["n_seated"] / max(len(set(D["d8"][ev_r].tolist())) / 5.0, 1e-9)
        rows.append([era, N._r(base["usd_per_session"]), base["n_seated"],
                     N._r(a["usd_per_session"]), N._r(a["ps_lo"]),
                     N._r(a["ps_hi"]), a["n_seated"],
                     N._r((a["usd_per_session"] or 0)
                          - (base["usd_per_session"] or 0)),
                     N._r(best_tau, 4), N._r(wk, 2)])
        N.hb("abstain %s: no-veto $%s (%d seats) -> tau %.4f $%s (%d seats)"
             % (era, N._r(base["usd_per_session"]), base["n_seated"],
                best_tau, N._r(a["usd_per_session"]), a["n_seated"]))
    on = N.pool_reads([per_era_on[e] for e in eras if e in per_era_on])
    off = N.pool_reads([per_era_off[e] for e in eras if e in per_era_off])
    rows.append(["POOLED_E3-E7", N._r(off.get("usd_per_session")),
                 off.get("n_seated"), N._r(on.get("usd_per_session")),
                 N._r(on.get("ps_lo")), N._r(on.get("ps_hi")),
                 on.get("n_seated"),
                 N._r((on.get("usd_per_session") or 0)
                      - (off.get("usd_per_session") or 0)), "", ""])
    N.write_tsv("HARVEST_ABSTAIN.tsv",
                ["era", "no_veto_usd", "no_veto_seats", "abstain_usd", "lo",
                 "hi", "abstain_seats", "delta_usd", "tau", "takes_per_week"],
                rows,
                extra=["TREATMENT 3: one threshold per era on the arm's own "
                       "score, chosen on the inner validation block by realised "
                       "$/session and nothing else.  The grid CONTAINS -inf, so "
                       "if abstention is worthless the inner block can return "
                       "the unvetoed arm untouched.",
                       "takes_per_week is reported because the standing floor "
                       "is 3-4 takes/week; an abstainer that clears the bar by "
                       "refusing to trade does not count."])
    return rows

def _selfcheck():
    """GUARD against the append-below-entrypoint bug that has now bitten this
    lane three times: every stage `main()` can dispatch to must exist at import
    time.  Fails loudly here rather than after a stage has already burned an
    hour of compute."""
    missing = [n for n in ("stage_sweep", "stage_ensemble", "stage_abstain")
               if n not in globals()]
    if missing:
        raise RuntimeError("harvest.py is mis-assembled: %s defined below the "
                           "entrypoint" % ", ".join(missing))


if __name__ == "__main__":
    _selfcheck()
    main()
