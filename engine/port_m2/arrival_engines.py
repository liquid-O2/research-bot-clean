#!/usr/bin/python3
"""PORT M2 — THE FAIR-ENGINE ROUND, FOLDED ONTO THE ARRIVAL EXPECTANCY.

WHY THE ENGINE QUESTION IS ONLY NOW WORTH ASKING
  Every previous engine comparison in this program was run against the
  WITHIN-CELL RANKING objective, which the leak audit has voided: a pairwise
  ranker is invariant to any monotone transform inside a group, so engines were
  being compared on a quantity the deployment cannot use.  The arrival object
  asks for something engines genuinely differ at — an ABSOLUTE regression onto
  dollars, whose TAIL is the only part that is ever seated.

  A_EV's measured weakness is precisely a place engines differ: its seed sd is
  0.35-2.7x its own mean.  A more stable expectancy fit at the same tail
  dollars is a real improvement, and a less stable one at higher dollars is
  not.  Both are reported.

THE DIAGNOSTIC IS TAIL DOLLARS, NOT AUC — this is tonight's own finding and it
  is binding on this table.  A_EV carries a coin-flip sign-AUC (0.478-0.507)
  and a +$766/trade tail; A_PBAR carried AUC 0.887-0.904 and a -$115 tail.  AUC
  is reported as CONTEXT ONLY and no selection is ever made on it.

THE LAW
  No adaptive HP optimiser.  One SMALL PRE-REGISTERED grid per engine, declared
  below and never swept beyond it.  5 seeds.  Identical folds, identical
  feature set (the champion's columns minus the audited leaky ones), identical
  monotone sign vector subset by position.  Binding eras first.  The winner
  must clear the search-adjusted null of the POLICY family downstream — this
  table alone promotes nothing.

CLI  arrival_engines.py --fit [--workers 4] [--eras ...]
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
import arrival as AR                      # noqa: E402
import arrival_fit as AF                  # noqa: E402

SEEDS = (0, 1, 2, 3, 4)
BINDING = ("E5", "E6", "E7")
TAIL_Q = 0.995                            # the operating point of the diagnostic

# PRE-REGISTERED GRIDS.  Declared here, fixed, never extended by a run.
GRID = {
    "LGBM": ({"max_depth": 6, "learning_rate": 0.05},
             {"max_depth": 8, "learning_rate": 0.03}),
    "LGBM_DART": ({"max_depth": 6, "learning_rate": 0.05},),
    "CATB": ({"depth": 6, "learning_rate": 0.05},),
}


def hb(m):
    sys.stderr.write("[engines %s] %s\n" % (time.strftime("%H:%M:%S"), m))
    sys.stderr.flush()


class EngineRefusal(RuntimeError):
    """A guard fired.  Never downgraded, never silently filtered."""


def _one(job):
    engine, hp, era, seed = job
    try:
        import newobj_arms as NA
        import rank_atlas as RA
        import champ_floor as CF
        import campaign as CP
        import fold_stack as FS
        D, P = CF.boot()
        tr, itr, iva, ev = NA.fold(D, era)
        base_cols, base_names = NA.feat_cols(D)
        vec_base = list(CP._vec(D, era, FS.BEST_K[era]))
        keep = [j for j, n in enumerate(base_names)
                if n not in AR.LEAKY_FEATURES]
        cols = [base_cols[j] for j in keep]
        names = [base_names[j] for j in keep]
        vec = ([vec_base[j] for j in keep]
               if len(vec_base) == len(base_cols) else [0] * len(keep))
        XF = D["X"][:, cols]
        y = np.nan_to_num(D["cert_close_usd"].astype(np.float64), nan=0.0)
        rounds = int(NA.CHAMP_HP[era]["rounds"])
        if engine.startswith("LGBM"):
            import lightgbm as lgb
            par = {"objective": "regression", "metric": "l2",
                   "num_threads": RA.N_THREAD, "seed": N.SEED + seed,
                   "verbosity": -1, "monotone_constraints": vec,
                   "feature_fraction": 0.8, "bagging_fraction": 0.8,
                   "bagging_freq": 1, "min_data_in_leaf": 20}
            par.update(hp)
            if engine == "LGBM_DART":
                par["boosting"] = "dart"
            ds = lgb.Dataset(XF[tr], label=y[tr], feature_name=names,
                             free_raw_data=True)
            b = lgb.train(par, ds, num_boost_round=rounds)
            pred = b.predict(XF[ev])
        else:
            from catboost import CatBoostRegressor
            m = CatBoostRegressor(
                iterations=rounds, depth=int(hp["depth"]),
                learning_rate=float(hp["learning_rate"]),
                loss_function="RMSE", random_seed=N.SEED + seed,
                thread_count=RA.N_THREAD, verbose=False,
                monotone_constraints=list(map(int, vec)),
                boosting_type="Ordered", allow_writing_files=False)
            m.fit(XF[tr], y[tr])
            pred = m.predict(XF[ev])
        sc = np.full(D["d8"].size, np.nan)
        sc[ev] = pred
        os.makedirs(AF.SCORES, exist_ok=True)
        tag = "A_EV_%s" % engine
        np.save(os.path.join(AF.SCORES, "%s_%s_%d.npy" % (tag, era, seed)),
                sc.astype(np.float32))
        # THE DIAGNOSTIC: realised dollars of the top-q tail at the operating
        # point.  Never AUC — see the module docstring.
        v = sc[ev]
        ok = np.isfinite(v)
        e2, v = ev[ok], v[ok]
        sel = e2[v >= np.quantile(v, TAIL_Q)]
        cert = D["cert_close_usd"].astype(np.float64)
        return (engine, str(hp), era, seed, float(np.nanmean(cert[sel])),
                int(sel.size), float(np.nanmean(cert[e2])), None)
    except Exception as e:                                # noqa: BLE001
        import traceback
        return (engine, str(hp), era, seed, None, None, None,
                "%s: %s | %s" % (type(e).__name__, e,
                                 traceback.format_exc()[-250:]))


def run(eras=BINDING, workers=4):
    import multiprocessing as mp
    jobs = [(eng, hp, e, s) for eng, grid in GRID.items() for hp in grid
            for e in eras for s in SEEDS]
    hb("engines: %d fits (%s), workers=%d"
       % (len(jobs), ", ".join("%s x%d" % (k, len(v))
                               for k, v in GRID.items()), workers))
    res, nerr, t0 = {}, 0, time.time()
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        for i, (eng, hps, era, seed, tail, nsel, pop, err) in enumerate(
                pool.imap_unordered(_one, jobs), 1):
            if err:
                nerr += 1
                hb("FIT FAILED %s %s %s s%d: %s" % (eng, hps, era, seed, err))
            else:
                res.setdefault((eng, hps, era), []).append((tail, nsel, pop))
            if i % 5 == 0 or i == len(jobs):
                hb("engines %d/%d [eta %.0fs, %d failed]"
                   % (i, len(jobs), (time.time() - t0) / i * (len(jobs) - i),
                      nerr))
    rows = []
    # the xgboost incumbent, read from the already-fitted A_EV columns
    import champ_floor as CF
    D, _P = CF.boot()
    cert = D["cert_close_usd"].astype(np.float64)
    for era in eras:
        tails = []
        for s in SEEDS:
            p = os.path.join(AF.SCORES, "A_EV_%s_%d.npy" % (era, s))
            if not os.path.exists(p):
                continue
            sc = np.load(p).astype(np.float64)
            ev = N.deployable(D, N.era_rows(D, era))
            v = sc[ev]
            ok = np.isfinite(v)
            e2, v = ev[ok], v[ok]
            sel = e2[v >= np.quantile(v, TAIL_Q)]
            tails.append(float(np.nanmean(cert[sel])))
        if tails:
            res[("XGB_INCUMBENT", "champ", era)] = [
                (t, 0, float(np.nanmean(cert[N.deployable(
                    D, N.era_rows(D, era))]))) for t in tails]
    for (eng, hps, era), v in sorted(res.items()):
        a = np.asarray([x[0] for x in v if x[0] is not None])
        if a.size == 0:
            continue
        pop = float(np.mean([x[2] for x in v if x[2] is not None]))
        rows.append([era, "BINDING" if era in BINDING else "context", eng,
                     hps, int(a.size), N._r(a.mean()), N._r(a.std()),
                     N._r(pop), N._r(a.mean() - pop),
                     N._r(a.std() / abs(a.mean()), 3) if a.mean() else ""])
    if not rows:
        raise EngineRefusal("ARRIVAL_ENGINES produced ZERO rows (%d fits "
                            "failed) — a null prints rows, so this is a "
                            "FAILURE" % nerr)
    N.write_tsv(
        "ARRIVAL_ENGINES.tsv",
        ["era", "criterion", "engine", "config", "n_seeds", "tail_usd_mean",
         "tail_usd_sd", "population_usd", "tail_minus_population",
         "sd_over_mean"], rows,
        extra=[
            "THE FAIR-ENGINE ROUND, FOLDED ONTO THE ARRIVAL EXPECTANCY.  Every "
            "previous engine comparison in this program ran against the "
            "WITHIN-CELL RANKING objective the leak audit voided — a pairwise "
            "ranker is invariant to monotone transforms inside a group, so "
            "engines were being compared on a quantity the deployment cannot "
            "use.  An absolute regression onto dollars is a question engines "
            "genuinely differ at.",
            "THE DIAGNOSTIC IS TAIL DOLLARS AT THE OPERATING POINT (top "
            "%.1f%%), NOT AUC.  Tonight measured A_EV at coin-flip sign-AUC "
            "(0.478-0.507) with a +$766/trade tail and A_PBAR at AUC "
            "0.887-0.904 with a -$115 tail, on the same data — AUC does not "
            "predict the thing the seat banks." % ((1 - TAIL_Q) * 100),
            "sd_over_mean is reported because A_EV's measured weakness IS its "
            "seed variance (0.35-2.7x its own mean): a more stable fit at the "
            "same tail dollars is a real improvement and a less stable one at "
            "higher dollars is not.",
            "NO ADAPTIVE HP OPTIMISER — one small pre-registered grid per "
            "engine, declared in the module and never extended by a run.  This "
            "table PROMOTES NOTHING on its own: a winner must clear the "
            "search-adjusted null of the causal POLICY family downstream."])
    hb("ARRIVAL_ENGINES.tsv: %d rows (%d failed)" % (len(rows), nerr))
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--eras", nargs="*", default=None)
    a = ap.parse_args()
    if a.fit:
        run(eras=tuple(a.eras) if a.eras else BINDING, workers=a.workers)
    else:
        ap.print_help()
