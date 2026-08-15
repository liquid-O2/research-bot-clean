#!/usr/bin/python3
"""PORT M2 — S2: THE LABEL RE-SCREEN AT THE ALIGNED HORIZON.

S1 SETTLED THE HORIZON: the aligned exit horizon IS the incumbent PHASE CLOSE
(HORIZON_ALIGNMENT.tsv — 0 of 141 rows promoted a longer hold; the foresight
ceiling itself shrinks 33-43% by session close and seats/session collapse
2.56 -> 1.00).  So every arm here trains on its own target and is EVALUATED,
always, on REAL REPLAY DOLLARS AT THE PHASE CLOSE with the $900 wall and the
adopted first-wall stop.

S1 ALSO CORRECTED THE PREMISE, and this file records it: the deployed arm was
never mislabelled.  `m3_walk.py:105 PRIMARY_TARGET = y_retg_rank_phase`
(= retg|e30|SESS_CLOSE) belongs to the M3 walk-forward lane; the arm this
campaign deploys — st_lmart / LMART_HP_NOTF and every newobj / curriculum /
fold descendant — trains on `grades(D['cert_close_usd'])` (st_lmart.py:144,
newobj_arms.grades, champ_floor.fit_member, fold_stack._one).  The sess-close
rank target is therefore measured HERE as one arm among many, not assumed.

THE ARMS (the target axis; the base config is the DEPLOYED FOLD, unchanged)
  T_INCUMBENT      grades(cert_close_usd) — what the deployed arm trains on.
  T_CHAMP_RETG     y_retg_rank_phase, the M3 lane's retg|e30|sess_close rank.
  T_DELAY_AVG      MEAN of cert_D over D in {0, 60, 120, 300} from the
                   delayed-certificate tensor — the LABEL-NOISE DENOISER: the
                   same act's value averaged over a neighbourhood of entry
                   seconds, which cancels the second-to-second path noise the
                   single-D label carries.
  T_DELAY_RETAIN   the same neighbourhood average of RETENTION (cert_D over the
                   unwalled MFE) rather than of dollars.
  T_MULTI_MARK     the mean mark over the exit-horizon ladder {300, 600, 900,
                   1800, 3600 s, phase close} — denoising along the HOLD axis
                   instead of the ENTRY axis.
  T_RACE_900       FIRST-PASSAGE RACE, binary: does the favourable skeleton
                   reach +$900 BEFORE the adverse skeleton reaches -$900,
                   inside the phase?  The trade's true object as a survival
                   race.
  T_RACE_1200      the same race at +$1,200 against the $900 wall.
  T_RACE_MARGIN    the SIGNED RACE MARGIN, tau_dn(900) - tau_up(900), a
                   continuous target: how much time the winner wins by.
  (race targets marginalise path noise differently from neighbourhood
   averaging, which is why both philosophies are on the table.)

THE TWO NON-TARGET ROWS THE BRIEF NAMES
  P_SEATREGION     N4: train ONLY on the historical top-of-cell region the
                   deployment actually seats from (population axis, incumbent
                   target).
  F_FLOWGEO        the ablation's finding as a feature set: the 31 flow +
                   geometry columns that carry ~all within-cell ordering
                   signal, alone.

THE STANDING LAW ADDITION (user, binding, applied from this table onward)
  1. NO ADAPTIVE HP OPTIMIZERS.  The config is the deployed fold's, fixed and
     pre-registered; nothing here searches HP.
  2. SEARCH-ADJUSTED NULL.  The same-width sweep is re-run on SHUFFLED labels
     and the BEST of those shuffled arms is the luck bar; a winner's delta must
     exceed it or it is reported as luck-indistinguishable, never promoted.
  3. PBO via CSCV over the (config x day) matrix, reported per sweep.

Everything else stands: 5 seeds, promotion at delta_minus_sd > 0, binding eras
first, armored rows primary, aim columns, E8 quarantined, a zero-row table is a
REFUSAL.

CLI
  labelscreen.py --targets [--workers 8]    build the target tensor
  labelscreen.py --screen  [--workers 6]    the sweep + shuffled null + PBO
"""
import argparse
import json
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
import m2_common as MC                    # noqa: E402
import m2_delay as MD                     # noqa: E402
import census_common as X                 # noqa: E402
import common as C                        # noqa: E402
import assemble as A                      # noqa: E402
import horizon as HZ                      # noqa: E402

VERSION = "PORT-M2-LABELSCREEN-V1"
OUT_ROOT = os.path.join(MC.M2_ROOT, "labelscreen")
BINDING = ("E5", "E6", "E7")
ERAS = BINDING + ("E3", "E4")
SEEDS = (0, 1, 2, 3, 4)
NULL_SEEDS = (0, 1, 2)                     # the luck bar, same sweep width
DELAY_AVG = (0, 60, 120, 300)              # the mandated denoiser grid
MARK_H = (300, 600, 900, 1800, 3600)       # + the phase close
RACE_UP = (900.0, 1200.0)
WALL = 900.0
SCALE = 2000.0                             # rank/ratio targets -> dollar space

TARGETS = ("T_INCUMBENT", "T_CHAMP_RETG", "T_DELAY_AVG", "T_DELAY_RETAIN",
           "T_MULTI_MARK", "T_RACE_900", "T_RACE_1200", "T_RACE_MARGIN")
ROWS_EXTRA = ("P_SEATREGION", "F_FLOWGEO")
ARMS = TARGETS + ROWS_EXTRA

# the race columns produced by the session pass
RCOLS = ("tau_up900", "tau_up1200", "tau_dn900", "pc_sec")
RIDX = {c: i for i, c in enumerate(RCOLS)}


def hb(msg):
    sys.stderr.write("[labelscreen %s] %s\n" % (time.strftime("%H:%M:%S"), msg))
    sys.stderr.flush()


class ScreenRefusal(RuntimeError):
    """A guard fired.  Never downgraded, never silently filtered."""


# =================================================== STAGE 1: THE TARGETS ===
def _race_one(job):
    """First-passage times on the SAME skeleton the certificate uses.

    `m2_delay._leg` returns the ADVERSE record arrays; the favourable records
    are the mirror construction on +f, built here with the identical
    prefix-maxima / first-record rule so tau_up and tau_dn are measured on one
    consistent object.
    """
    asset, d8, rows = job
    try:
        sess = A.load_session(asset, int(d8))
        s = sess["s"]
        mult = float(C.ASSETS[asset]["mult"])
        out = []
        for (i, t, side, cost) in rows:
            t, side = int(t), int(side)
            r = np.full(len(RCOLS), np.nan, dtype=np.float64)
            e = MD._first_sane(s, t)
            pc0 = X.next_phase_boundary(s, t)
            r[RIDX["pc_sec"]] = float(pc0)
            if e >= 0 and e < pc0:
                vt, f, at, av = MD._leg(s, e, float(s.mid[e]), side, mult)
                if vt.size:
                    run_f = np.maximum.accumulate(f)
                    nf = np.empty(run_f.size, dtype=bool)
                    nf[0] = False              # index 0 is never a record
                    if run_f.size > 1:
                        nf[1:] = run_f[1:] > run_f[:-1]
                    ft = vt[nf].astype(np.int32)
                    fv = run_f[nf].astype(np.float32)
                    for U in RACE_UP:
                        k = int(np.searchsorted(fv, np.float32(U),
                                                side="left"))
                        r[RIDX["tau_up%d" % int(U)]] = (
                            float(ft[k]) if k < fv.size else np.inf)
                    w = MD._wall_sec(at, av, WALL)
                    r[RIDX["tau_dn900"]] = float(w) if w is not None else np.inf
            out.append((int(i), r))
        return (asset, int(d8), out, None)
    except Exception as exc:                              # noqa: BLE001
        return (asset, int(d8), [], "%s: %s" % (type(exc).__name__, exc))


def build_targets(workers=8, out_dir=None):
    import multiprocessing as mp
    out_dir = out_dir or OUT_ROOT
    os.makedirs(out_dir, exist_ok=True)
    D = N.matrix()
    n = int(D["d8"].size)

    # --- the first-passage race tensor (one session pass) -------------------
    R = np.full((n, len(RCOLS)), np.nan, dtype=np.float64)
    joblist = N._jobs_from_matrix(D)
    t0, errs, done = time.time(), [], 0
    hb("race: %d sessions, %d candidates" % (len(joblist), n))
    with mp.Pool(processes=int(workers)) as pool:
        for k, (a_, d_, rows, err) in enumerate(
                pool.imap_unordered(_race_one, joblist, chunksize=1), 1):
            if err:
                errs.append("%s %d %s" % (a_, d_, err))
            for i, r in rows:
                R[i] = r
                done += 1
            if k % 500 == 0 or k == len(joblist):
                el = time.time() - t0
                hb("race %d/%d %.0fs eta %.0fs filled=%d errs=%d"
                   % (k, len(joblist), el, el / k * (len(joblist) - k), done,
                      len(errs)))
    if errs:
        raise ScreenRefusal("%d session errors in the race pass — first: %s"
                            % (len(errs), errs[0]))

    # --- the target value columns ------------------------------------------
    V = {}
    cert = D["cert_close_usd"].astype(np.float64)
    V["T_INCUMBENT"] = cert.copy()

    retg = D["y_retg_rank_phase"].astype(np.float64)
    V["T_CHAMP_RETG"] = np.nan_to_num(retg, nan=0.0) * SCALE

    P = N.load_paths()
    stack = []
    for dl in DELAY_AVG:
        v = P[dl][:, N.FIDX["cert_close"]].copy()
        v[P[dl][:, N.FIDX["feasible"]] <= 0.5] = np.nan
        stack.append(v)
    Sd = np.vstack(stack)
    with np.errstate(invalid="ignore"):
        avg = np.nanmean(Sd, axis=0)
    V["T_DELAY_AVG"] = np.where(np.isfinite(avg), avg, cert)

    mfe = D["mfe_unwalled"].astype(np.float64)
    den = np.maximum(mfe, 30.0 * D["cost_rt"].astype(np.float64))
    with np.errstate(invalid="ignore", divide="ignore"):
        ret = np.clip(Sd / den[None, :], -1.0, 1.0)
        ravg = np.nanmean(ret, axis=0)
    V["T_DELAY_RETAIN"] = np.where(np.isfinite(ravg), ravg, 0.0) * SCALE

    S = HZ.load_short()
    T = HZ.load()
    marks = [S[:, HZ.SIDX["H%d_cert" % h]] for h in MARK_H]
    marks.append(T[:, HZ.CIDX["PHASE_cert"]])
    with np.errstate(invalid="ignore"):
        mavg = np.nanmean(np.vstack(marks), axis=0)
    V["T_MULTI_MARK"] = np.where(np.isfinite(mavg), mavg, cert)

    pc = R[:, RIDX["pc_sec"]]
    dn = R[:, RIDX["tau_dn900"]]
    for U in RACE_UP:
        up = R[:, RIDX["tau_up%d" % int(U)]]
        won = (up < dn) & (up <= pc)
        V["T_RACE_%d" % int(U)] = np.where(
            np.isfinite(up) | np.isfinite(dn), won.astype(np.float64), 0.0) \
            * 1000.0
    up9 = R[:, RIDX["tau_up900"]]
    gap = np.where(np.isfinite(dn), dn, pc) - np.where(np.isfinite(up9), up9,
                                                       pc)
    gap = np.clip(gap, -3600.0, 3600.0) / 3600.0
    # the margin is a SIGNED TIME, rescaled monotonically into dollar space so
    # the frozen D-021 grade ladder bites it the same way it bites every other
    # target.  No fitted transform anywhere.
    V["T_RACE_MARGIN"] = np.where(np.isfinite(gap), gap, 0.0) * SCALE

    cols = list(TARGETS)
    Vm = np.vstack([V[c] for c in cols]).astype(np.float32)
    np.savez(os.path.join(out_dir, "targets.npz"),
             cols=np.array(cols), V=Vm, R=R.astype(np.float32),
             rcols=np.array(RCOLS))
    rec = {"version": VERSION, "n": n, "targets": cols,
           "delay_avg_grid": list(DELAY_AVG), "mark_grid": list(MARK_H),
           "race_up": list(RACE_UP), "wall": WALL, "scale": SCALE,
           "race_win_rate_900": float(np.mean(V["T_RACE_900"] > 0)),
           "race_win_rate_1200": float(np.mean(V["T_RACE_1200"] > 0)),
           "corr_incumbent_delayavg": float(np.corrcoef(
               V["T_INCUMBENT"], V["T_DELAY_AVG"])[0, 1]),
           "corr_incumbent_retg": float(np.corrcoef(
               V["T_INCUMBENT"], V["T_CHAMP_RETG"])[0, 1]),
           "corr_incumbent_race900": float(np.corrcoef(
               V["T_INCUMBENT"], V["T_RACE_900"])[0, 1]),
           "secs": round(time.time() - t0, 1)}
    with open(os.path.join(out_dir, "targets.receipt.json"), "w") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True)
    hb("targets: %d columns; race win rate 900/%1.3f 1200/%1.3f; "
       "corr(incumbent, delay_avg)=%.3f retg=%.3f race900=%.3f"
       % (len(cols), rec["race_win_rate_900"], rec["race_win_rate_1200"],
          rec["corr_incumbent_delayavg"], rec["corr_incumbent_retg"],
          rec["corr_incumbent_race900"]))
    return Vm


_TV = {}


def targets(out_dir=None):
    if "V" in _TV:
        return _TV["V"]
    p = os.path.join(out_dir or OUT_ROOT, "targets.npz")
    if not os.path.exists(p):
        raise ScreenRefusal("no target tensor at %s — run --targets" % p)
    z = np.load(p, allow_pickle=False)
    cols = [str(x) for x in z["cols"].tolist()]
    _TV["V"] = {c: z["V"][i].astype(np.float64) for i, c in enumerate(cols)}
    z.close()
    return _TV["V"]


# ==================================================== STAGE 2: THE SWEEP ====
def seat_region_rows(D, rows, V0, frac=0.34):
    """N4: the top-of-cell region the deployment actually seats from — the top
    `frac` of each TRAINING cell by the incumbent value.  Computed on TRAINING
    rows only; nothing about the eval era enters it."""
    ro, blocks = N.cell_blocks(D, rows)
    keep = []
    v = V0[ro]
    for a, b in blocks:
        idx = np.arange(a, b)
        k = max(1, int(round((b - a) * frac)))
        order = idx[np.argsort(-np.nan_to_num(v[idx], nan=-1e18),
                               kind="stable")][:k]
        keep.extend(ro[order].tolist())
    return np.sort(np.asarray(keep, dtype=np.int64))


def _fit_one(job):
    """ONE arm, ONE era, ONE seed.  The DEPLOYED FOLD config, unchanged; only
    the label column (or the training population / feature set) varies."""
    arm, era, seed, shuffled = job
    try:
        import xgboost as xgb
        import newobj_arms as NA
        import rank_atlas as RA
        import champ_floor as CF
        import curriculum as CU
        import campaign as CP
        import fold_stack as FS
        import stacked_final as SF
        D, P = CF.boot()
        tr, itr, iva, ev = NA.fold(D, era)
        V = targets()
        cols, names = NA.feat_cols(D)
        k = FS.BEST_K[era]
        vec = list(CP._vec(D, era, k))     # the BASE-shaped stability vector
        if arm == "F_FLOWGEO":
            # LIKE-FOR-LIKE: the 31 flow+geometry columns keep the SAME
            # monotone signs the full-feature champion gives them, selected by
            # position out of the base vector rather than dropped.
            fg = [str(g) for g in D["feature_groups"].tolist()]
            keep = [j for j, i in enumerate(cols)
                    if fg[i] in ("flow", "geometry")]
            vec = [vec[j] for j in keep] if len(vec) == len(cols) else \
                [0] * len(keep)
            cols = [cols[j] for j in keep]
            names = [str(D["names"][i]) for i in cols]
        XF = D["X"][:, cols]
        tgt = "T_INCUMBENT" if arm in ROWS_EXTRA else arm
        val = V[tgt].copy()
        if arm == "P_SEATREGION":
            tr = seat_region_rows(D, tr, V["T_INCUMBENT"])
        if shuffled:
            # THE LUCK BAR: the label is permuted WITHIN each training cell, so
            # the group structure, the cell sizes and the grade marginals are
            # all preserved and only the row->label assignment is destroyed.
            rng = np.random.default_rng(N.SEED + 7919 * seed)
            ro, blocks = N.cell_blocks(D, tr)
            for a, b in blocks:
                ix = ro[a:b]
                val[ix] = val[rng.permutation(ix)]
        hp = NA.CHAMP_HP[era]
        vec = vec[:XF.shape[1]] + [0] * max(0, XF.shape[1] - len(vec))
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
        cfg.update(FS.BEST_HP.get(era, {}))   # the pre-registered fold HP
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
        # EVALUATION IS ALWAYS REAL REPLAY DOLLARS AT THE PHASE CLOSE
        rp = N.replay_delayed(D, N.top_per_cell_score(
            D, ev, sc, N.committed_policy()[era][1]), P)
        armed = SF.apply_stop(D, rp, "STOP_WALL1")
        a = N.read_rows(D, armed)
        r = N.read_rows(D, rp)
        per = {x["session"]: x["realised"] for x in armed}
        return (arm, era, seed, shuffled, a["usd_per_session"],
                r["usd_per_session"], per, None)
    except Exception as e:                                # noqa: BLE001
        import traceback
        return (arm, era, seed, shuffled, None, None, None,
                "%s: %s | %s" % (type(e).__name__, e,
                                 traceback.format_exc()[-400:]))


def pbo_cscv(per_by_arm, n_blocks=10):
    """PROBABILITY OF BACKTEST OVERFITTING, Bailey et al.'s CSCV, over the
    (config x day) matrix of this sweep.

    The days are cut into `n_blocks` contiguous blocks; every balanced split of
    the blocks into IS / OOS halves is enumerated; the IS-best config's OOS
    RANK is recorded; PBO = the share of splits where the IS winner lands in
    the BOTTOM HALF out of sample.  A high PBO means the sweep's winner is a
    property of the split, not of the data.
    """
    import itertools
    arms = sorted(per_by_arm)
    days = sorted(set(k for a in arms for k in per_by_arm[a]))
    if len(arms) < 2 or len(days) < n_blocks * 2:
        return None
    M = np.full((len(arms), len(days)), np.nan)
    for i, a in enumerate(arms):
        for j, d in enumerate(days):
            M[i, j] = per_by_arm[a].get(d, np.nan)
    keep = ~np.isnan(M).any(axis=0)
    M = M[:, keep]
    if M.shape[1] < n_blocks * 2:
        return None
    bl = np.array_split(np.arange(M.shape[1]), n_blocks)
    half = n_blocks // 2
    lam = []
    for combo in itertools.combinations(range(n_blocks), half):
        isx = np.concatenate([bl[i] for i in combo])
        osx = np.concatenate([bl[i] for i in range(n_blocks)
                              if i not in combo])
        mis = np.nanmean(M[:, isx], axis=1)
        mos = np.nanmean(M[:, osx], axis=1)
        w = int(np.argmax(mis))
        rank = float((mos < mos[w]).sum()) / max(len(arms) - 1, 1)
        lam.append(rank)
    lam = np.asarray(lam)
    return {"pbo": float((lam <= 0.5).mean()), "n_splits": int(lam.size),
            "median_oos_rank": float(np.median(lam)), "n_arms": len(arms)}


def _cache_path(out_dir=None):
    return os.path.join(out_dir or OUT_ROOT, "fits.jsonl")


def _load_cache(out_dir=None):
    """Completed fits, so a second pass over more eras never refits what the
    binding-era pass already paid for.  Incremental writes: the file is
    appended after every fit, so a killed run loses at most one fit."""
    out = {}
    p = _cache_path(out_dir)
    if not os.path.exists(p):
        return out
    with open(p) as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue                    # a torn last line, never fatal
            out[(r["arm"], r["era"], int(r["seed"]), bool(r["sh"]))] = r
    return out


def run_screen(eras=ERAS, workers=6, out_dir=None):
    import multiprocessing as mp
    out_dir = out_dir or OUT_ROOT
    os.makedirs(out_dir, exist_ok=True)
    import confidence as CO
    D = N.matrix()
    targets()
    cache = _load_cache(out_dir)
    allj = [(a, e, s, False) for a in ARMS for e in eras for s in SEEDS]
    allj += [(a, e, s, True) for a in ARMS for e in eras for s in NULL_SEEDS]
    jobs = [j for j in allj if (j[0], j[1], j[2], j[3]) not in cache]
    hb("screen: %d fits total, %d cached, %d to run (%d arms x %d eras), "
       "workers=%d" % (len(allj), len(allj) - len(jobs), len(jobs), len(ARMS),
                       len(eras), workers))
    res, per, t0, nerr = {}, {}, time.time(), 0
    for key, r in cache.items():
        if key[1] not in eras:
            continue
        res.setdefault((key[0], key[1], key[3]), []).append((r["av"], r["rv"]))
        if not key[3]:
            per.setdefault((key[1], key[0]), {}).update(r.get("per") or {})
    ctx = mp.get_context("spawn")
    fh = open(_cache_path(out_dir), "a")
    with ctx.Pool(processes=workers) as pool:
        for i, (arm, era, seed, sh, av, rv, pr, err) in enumerate(
                pool.imap_unordered(_fit_one, jobs), 1):
            if err:
                nerr += 1
                hb("FIT FAILED %s %s s%d shuf=%s: %s" % (arm, era, seed, sh,
                                                         err))
            else:
                res.setdefault((arm, era, sh), []).append((av, rv))
                if not sh:
                    per.setdefault((era, arm), {}).update(pr or {})
                fh.write(json.dumps({"arm": arm, "era": era, "seed": seed,
                                     "sh": sh, "av": av, "rv": rv,
                                     "per": pr if not sh else None}) + "\n")
                fh.flush()
            if i % 10 == 0 or i == len(jobs):
                hb("screen %d/%d [eta %.0fs, %d failed]"
                   % (i, len(jobs), (time.time() - t0) / max(i, 1)
                      * (len(jobs) - i), nerr))
    fh.close()
    ceil = CO.ceilings()
    rows = []
    for era in eras:
        crit = "BINDING" if era in BINDING else "context"
        inc = np.asarray([x[0] for x in res.get(("T_INCUMBENT", era, False),
                                                []) if x[0] is not None])
        # THE SEARCH-ADJUSTED NULL: the same-width sweep on shuffled labels,
        # its BEST arm.  That is the luck bar a winner must clear.
        null_means = []
        for a in ARMS:
            v = [x[0] for x in res.get((a, era, True), []) if x[0] is not None]
            if v:
                null_means.append(float(np.mean(v)))
        luck = max(null_means) if null_means else None
        luck_delta = (luck - inc.mean()) if (luck is not None and inc.size) \
            else None
        pb = pbo_cscv({a: per[(era, a)] for a in ARMS if (era, a) in per})
        cl = ceil.get("%s|ALL" % era)
        for a in ARMS:
            v = res.get((a, era, False), [])
            av = np.asarray([x[0] for x in v if x[0] is not None])
            rv = np.asarray([x[1] for x in v if x[1] is not None])
            if av.size == 0:
                continue
            d = av.mean() - inc.mean() if inc.size else None
            dms = (d - av.std()) if d is not None else None
            nv = [x[0] for x in res.get((a, era, True), [])
                  if x[0] is not None]
            beats_luck = (d is not None and luck_delta is not None
                          and d > luck_delta)
            aim = 0.80 * cl if cl else None
            rows.append([
                era, crit, a, int(av.size), N._r(av.mean()), N._r(av.std()),
                N._r(rv.mean()), N._r(rv.std()),
                N._r(inc.mean()) if inc.size else "",
                N._r(d) if d is not None else "",
                N._r(dms) if dms is not None else "",
                N._r(float(np.mean(nv))) if nv else "",
                N._r(luck) if luck is not None else "",
                N._r(luck_delta) if luck_delta is not None else "",
                "YES" if beats_luck else "no",
                N._r(pb["pbo"], 3) if pb else "",
                N._r(cl), N._r(av.mean() / cl, 4) if cl else "",
                N._r(aim), N._r(av.mean() - aim) if aim else "",
                "YES" if (dms is not None and dms > 0 and beats_luck)
                else "no"])
    if not rows:
        raise ScreenRefusal(
            "LABEL_RESCREEN produced ZERO rows (%d fits failed) — a null "
            "prints rows, so this is a FAILURE, not a result" % nerr)
    N.write_tsv(
        "LABEL_RESCREEN.tsv",
        ["era", "criterion", "arm", "n_seeds", "armed_mean", "armed_sd",
         "raw_mean", "raw_sd", "incumbent_mean", "delta", "delta_minus_sd",
         "shuffled_self_mean", "search_adjusted_luck_bar",
         "luck_bar_delta", "beats_search_adjusted_null", "pbo_cscv",
         "foresight_ceiling", "armed_capture", "aim_08ceiling", "gap_to_aim",
         "promotes"], rows,
        extra=[
            "S2 — THE LABEL RE-SCREEN AT THE ALIGNED HORIZON.  S1 settled that "
            "the aligned horizon IS the incumbent phase close, so every arm is "
            "EVALUATED on real replay dollars at the phase close with the $900 "
            "wall and the adopted first-wall stop.  Only the TARGET (or the "
            "training population / feature set) varies; the deployed fold "
            "config is otherwise unchanged and FIXED — no HP search anywhere.",
            "THE DEPLOYED ARM WAS NEVER MISLABELLED: st_lmart.py:144 / "
            "newobj_arms.grades / fold_stack._one all train on "
            "grades(cert_close_usd) = PHASE-CLOSE DOLLARS.  "
            "m3_walk.py:105's y_retg_rank_phase (retg|e30|sess_close) is the "
            "M3 walk lane's target and is measured here as T_CHAMP_RETG, one "
            "arm among many.",
            "SEARCH-ADJUSTED NULL (binding law): the identical sweep is re-run "
            "with the label PERMUTED WITHIN EACH TRAINING CELL — group "
            "structure, cell sizes and grade marginals preserved — and the "
            "BEST of those shuffled arms is the luck bar.  An arm promotes "
            "only if delta_minus_sd > 0 AND delta > luck_bar_delta.",
            "PBO = probability of backtest overfitting, Bailey CSCV over the "
            "(arm x day) matrix of this sweep, 10 blocks, all balanced splits. "
            " It is a property of the SWEEP, so it is the same value on every "
            "row of an era.",
            "T_DELAY_AVG / T_DELAY_RETAIN denoise along the ENTRY axis "
            "(neighbourhood of entry seconds); T_MULTI_MARK denoises along the "
            "HOLD axis; the T_RACE_* arms marginalise path noise as a "
            "first-passage survival race instead.  Three different denoising "
            "philosophies, measured against one another."])
    hb("LABEL_RESCREEN.tsv: %d rows (%d fits failed)" % (len(rows), nerr))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", action="store_true")
    ap.add_argument("--screen", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--eras", nargs="*", default=None)
    a = ap.parse_args()
    did = False
    if a.targets:
        build_targets(workers=a.workers)
        did = True
    if a.screen:
        run_screen(eras=tuple(a.eras) if a.eras else ERAS, workers=a.workers)
        did = True
    if not did:
        ap.print_help()


if __name__ == "__main__":
    main()
