#!/usr/bin/python3
"""PORT M1.B S4 — CONFIRM FITS for the screen's survivors.

Spec §1 S4 output clause: "top-25 by economic alignment + the champion-class
retention/ratio cells -> confirm fits (per-fold HP search 32 configs) -> M2
freeze consumes the survivors. NO promotion claims from this stage."

SELECTION (deterministic, from the committed screen ledger):
  * the top-25 per asset by economic alignment (within-unit Spearman), after
    dropping shuffled twins and any arm VOIDED by its twin;
  * plus every retention / ratio-axis member inside the top-10 of its own
    family class (the "champion-class retention/ratio cells").

PER-FOLD HP SEARCH, leakage-free: inside each walk-forward fold, the 32
configs are trained on the fold's training block minus its last 20% of
sessions, selected on that inner block, and the SELECTED config alone is
scored on the fold's untouched validation block.

Run: lab/run.sh port-m1b-s4-confirm -- /usr/bin/python3 engine/port_m1b/s4_confirm.py
"""
import multiprocessing as mp
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, "/workspace/engine/port_m0", "/workspace/engine/port_m1"):
    if _p not in sys.path:
        sys.path.insert(0, _p)
sys.path.insert(0, "/workspace/artifacts/cache/pylibs")

import xgboost as xgb                 # noqa: E402
import s4_common as S                 # noqa: E402
import s4_labels as L                 # noqa: E402
import s4_screen as SC                # noqa: E402
import common as C                    # noqa: E402
import m1_common as M                 # noqa: E402

SECTION = "S4 confirm fits"
TOP_N = 25
CHAMPION_CLASS = ("ratio", "ratio_axis")
CHAMPION_TOP = 10
ROUNDS_MAX = 200
INNER_FRACTION = 0.2

HP_GRID = tuple({"max_depth": d, "eta": e, "min_child_weight": mcw,
                 "colsample_bytree": cs, "subsample": 0.8,
                 "objective": "reg:squarederror", "tree_method": "hist",
                 "seed": 20260813, "nthread": 1}
                for d in (4, 6, 8, 10)
                for e in (0.04, 0.08)
                for mcw in (20, 50)
                for cs in (0.6, 0.9))

PARAMS = {"spec_section": SECTION, "top_n": TOP_N,
          "champion_class": list(CHAMPION_CLASS), "champion_top": CHAMPION_TOP,
          "n_hp_configs": len(HP_GRID), "rounds_max": ROUNDS_MAX,
          "inner_fraction": INNER_FRACTION,
          "selection": "per fold: train on the fold's training block minus its "
                       "last 20% of sessions, select on that inner block, "
                       "score the selected config on the untouched validation",
          "status": "EXPLORATORY_NONCERTIFYING"}

COLUMNS = ["asset", "label", "family", "selection_reason", "n_rows",
           "screen_align", "confirm_align", "confirm_rho_median",
           "confirm_dollar_recall_at3", "confirm_dollar_recall_at10",
           "delta_align_vs_screen", "configs_per_fold", "chosen_depths",
           "chosen_etas", "fit_secs"]

_CTX = {}


def read_ledger():
    rows, cols = [], None
    with open(S.out_path("screen_ledger.tsv")) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            rows.append(dict(zip(cols, f)))
    return rows


def _f(r, k):
    v = r.get(k, "")
    return float(v) if v not in ("", None) else float("nan")


def select(ledger, asset):
    """(label -> reason) for one asset, deterministic."""
    rs = [r for r in ledger if r["asset"] == asset
          and r["shuffled_twin"] == "0" and r["voided_by_twin"] == "0"
          and np.isfinite(_f(r, "align_spearman_unit"))]
    rs.sort(key=lambda r: (-_f(r, "align_spearman_unit"), r["label"]))
    out = {}
    for r in rs[:TOP_N]:
        out[r["label"]] = "top%d_economic_alignment" % TOP_N
    champs = [r for r in rs if r["family"] in CHAMPION_CLASS]
    for r in champs[:CHAMPION_TOP]:
        out.setdefault(r["label"], "champion_class_%s" % r["family"])
    return out


def _inner_split(dates, train_mask):
    u = np.unique(dates[train_mask])
    if u.size < 10:
        return train_mask, train_mask
    cut = u[int(round(u.size * (1.0 - INNER_FRACTION))) - 1]
    inner_tr = train_mask & (dates <= cut)
    inner_va = train_mask & (dates > cut)
    if inner_va.sum() < 100 or inner_tr.sum() < 500:
        return train_mask, train_mask
    return inner_tr, inner_va


def _confirm_one(j):
    t0 = time.time()
    ctx = _CTX
    y = ctx["Y"][:, j].astype(np.float64)
    meta = ctx["meta"][j]
    units = ctx["units"][meta.unit or SC.DEFAULT_UNIT]
    dates = ctx["dates"]
    pred_all = np.full(y.size, np.nan)
    rhos, depths, etas = [], [], []
    for (tr, va) in ctx["folds"]:
        trm = tr & np.isfinite(y)
        vam = va & np.isfinite(y)
        if int(trm.sum()) < 500 or int(vam.sum()) < 100:
            continue
        itr, iva = _inner_split(dates, trm)
        din = xgb.DMatrix(ctx["X"][itr], label=y[itr])
        dva = xgb.DMatrix(ctx["X"][iva], label=y[iva])
        best, best_cfg, best_rounds = -np.inf, None, ROUNDS_MAX
        for cfg in HP_GRID:
            b = xgb.train(cfg, din, ROUNDS_MAX,
                          evals=[(dva, "inner")], early_stopping_rounds=20,
                          verbose_eval=False)
            p = b.predict(dva, iteration_range=(0, b.best_iteration + 1))
            r, _p, _n = SC.spearman(p, y[iva])
            if np.isfinite(r) and r > best:
                best, best_cfg, best_rounds = r, cfg, b.best_iteration + 1
        if best_cfg is None:
            continue
        d = xgb.DMatrix(ctx["X"][trm], label=y[trm])
        b = xgb.train(best_cfg, d, best_rounds)
        p = b.predict(xgb.DMatrix(ctx["X"][vam]))
        pred_all[vam] = p
        r, _p, _n = SC.spearman(p, y[vam])
        if np.isfinite(r):
            rhos.append(r)
        depths.append(best_cfg["max_depth"])
        etas.append(best_cfg["eta"])
    if not rhos:
        return None
    align, _p, _n = SC.within_unit_spearman(pred_all, ctx["net_pc"], units)
    return {"j": j, "align": align,
            "rho_median": float(np.median(rhos)),
            "dr3": SC.dollar_recall(pred_all, ctx["cert"], units, 3),
            "dr10": SC.dollar_recall(pred_all, ctx["cert"], units, 10),
            "n_rows": int(np.isfinite(y).sum()),
            "depths": ",".join(str(x) for x in depths),
            "etas": ",".join("%g" % x for x in etas),
            "secs": time.time() - t0}


def main():
    S.verify_spec()
    workers = int(os.environ.get("M1_WORKERS", "5"))
    assets = [a for a in sys.argv[1:] if a in S.ASSETS] or list(S.ASSETS)
    ledger = read_ledger()
    phash = C.params_hash(PARAMS)
    rows = []
    for asset in assets:
        chosen = select(ledger, asset)
        if not chosen:
            continue
        arr, roster, cid, urows, Xf, fnames, atoms = SC.build_asset(asset)
        metas, cols = [], []
        for item in L.enumerate_grid(atoms):
            if item[0] == "__PRUNES__":
                break
            m, v = item
            if m.name in chosen:
                metas.append(m)
                cols.append(np.asarray(v, dtype=np.float32))
        Y = np.column_stack(cols)
        dates = atoms.date8
        _CTX.clear()
        _CTX.update({"X": Xf, "Y": Y, "meta": metas, "dates": dates,
                     "net_pc": atoms.net("phase_close"),
                     "cert": atoms.cert[(1.0, "phase_close")][0],
                     "units": {u: atoms.unit[u] for u in L.RANKING_UNITS},
                     "folds": SC.fold_slices(dates)})
        M.hb("s4 confirm %s: %d labels x %d HP configs x %d folds"
             % (asset, len(metas), len(HP_GRID), len(_CTX["folds"])))
        idx = list(range(len(metas)))
        t0 = time.time()
        if workers <= 1:
            res = [_confirm_one(j) for j in idx]
        else:
            with mp.Pool(workers) as pool:
                res = list(pool.imap(_confirm_one, idx, chunksize=1))
        screen_align = {r["label"]: _f(r, "align_spearman_unit")
                        for r in ledger if r["asset"] == asset}
        for r in res:
            if r is None:
                continue
            m = metas[r["j"]]
            sa = screen_align.get(m.name, float("nan"))
            rows.append([asset, m.name, m.family, chosen[m.name], r["n_rows"],
                         sa, r["align"], r["rho_median"], r["dr3"], r["dr10"],
                         r["align"] - sa, len(HP_GRID), r["depths"],
                         r["etas"], r["secs"]])
        M.hb("s4 confirm %s: %d labels in %.0fs" % (asset, len(res),
                                                    time.time() - t0))
    M.write_tsv(S.out_path("confirm_fits.tsv"), SECTION, phash, COLUMNS, rows,
                spec="PORT_M1B",
                extra=["per-fold HP search over %d configs, selected on an "
                       "inner 20%% split of each training block and scored on "
                       "the untouched validation block" % len(HP_GRID),
                       "EXPLORATORY_NONCERTIFYING - no promotion claims"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
