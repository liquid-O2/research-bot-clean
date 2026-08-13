#!/usr/bin/python3
"""PORT M1.B S4 — the ATLAS SCREEN (fixed GBT, dual scoring, Holm, guards).

Spec §1 S4:
  * fixed GBT (xgboost, depth 6, eta 0.08, 50 rounds, subsample .8,
    colsample .6, min_child_weight 50, seed 20260813) - NO per-label tuning;
  * 25% candidate subsample, expanding 4-fold walk-forward inside FIT;
  * the PINNED probe features, identical for every label;
  * SCORING reported separately: (a) learnability rho_median vs own truth;
    (b) ECONOMIC ALIGNMENT = within-RANKING-UNIT Spearman vs net_phase-close
    AND dollar_recall@{3,10} vs walled certs; (c) era stability (per-FIT-year);
  * Holm multiplicity ledger over the full grid;
  * every occupancy/oracle-derived label carries a within-session-SHUFFLED twin
    at identical budget - the arm is VOIDED if the twin matches it.

EXPLORATORY_NONCERTIFYING, FIT era only. No promotion claims are made here.

Run: lab/run.sh port-m1b-s4-screen -- /usr/bin/python3 engine/port_m1b/s4_screen.py
"""
import json
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
import common as C                    # noqa: E402
import m1_common as M                 # noqa: E402

SECTION = "S4 atlas screen"

GBT = {"max_depth": 6, "eta": 0.08, "subsample": 0.8, "colsample_bytree": 0.6,
       "min_child_weight": 50, "seed": 20260813, "objective":
       "reg:squarederror", "tree_method": "hist", "nthread": 1}
ROUNDS = 50
N_FOLDS = 4
RECALL_K = (3, 10)
DEFAULT_UNIT = "session"             # scoring unit for unit-free labels

PARAMS = {
    "spec_section": SECTION,
    "gbt": dict(GBT, num_boost_round=ROUNDS),
    "folds": "expanding %d-fold walk-forward over FIT sessions" % N_FOLDS,
    "subsample": S.SUBSAMPLE,
    "features": "pinned probe set (m1/atlas/features_*.npz)",
    "learnability": "Spearman(pred, own truth) on each validation fold, median",
    "economic_alignment": "within-ranking-unit Spearman(pred, net_phase_close)"
                          " + dollar_recall@{3,10} vs the walled certificate",
    "era_stability": "per-FIT-year alignment sign and magnitude",
    "holm": "Holm step-down over the full enumerated grid, per asset, on the "
            "economic-alignment Spearman p-value",
    "guard": "occupancy/oracle-derived labels are VOIDED when their "
             "within-session-shuffled twin matches them",
    "status": "EXPLORATORY_NONCERTIFYING",
}

SCORE_COLUMNS = [
    "asset", "label", "family", "base", "kind", "horizon", "truncation",
    "penalty", "transform", "ranking_unit", "occupancy_derived",
    "shuffled_twin", "n_rows", "n_folds_scored",
    "rho_median_learnability", "rho_fold_min", "rho_fold_max",
    "align_spearman_unit", "align_p_value", "dollar_recall_at3",
    "dollar_recall_at10", "era_sign_consistency", "era_min_align",
    "era_max_align", "holm_rank", "holm_threshold", "holm_significant",
    "twin_align_spearman", "voided_by_twin", "fit_secs"]

# ---- process-global fit context (fork-shared, never pickled per task) -------
_CTX = {}


def rankdata(x):
    """Average ranks with ties, NaN-safe (NaN rows are excluded upstream)."""
    n = x.size
    order = np.argsort(x, kind="stable")
    r = np.empty(n, dtype=np.float64)
    sx = x[order]
    i = 0
    while i < n:
        j = i
        while j + 1 < n and sx[j + 1] == sx[i]:
            j += 1
        r[order[i:j + 1]] = 0.5 * (i + j) + 1.0
        i = j + 1
    return r


def spearman(a, b):
    ok = np.isfinite(a) & np.isfinite(b)
    if int(ok.sum()) < 10:
        return float("nan"), float("nan"), 0
    ra, rb = rankdata(a[ok]), rankdata(b[ok])
    ra = ra - ra.mean()
    rb = rb - rb.mean()
    d = np.sqrt((ra * ra).sum() * (rb * rb).sum())
    if d <= 0:
        return float("nan"), float("nan"), int(ok.sum())
    rho = float((ra * rb).sum() / d)
    n = int(ok.sum())
    p = _rho_p(rho, n)
    return rho, p, n


def _rho_p(rho, n):
    """Two-sided p for Spearman rho via the t approximation (n >> 30 here)."""
    if not np.isfinite(rho) or n < 10 or abs(rho) >= 1.0:
        return float("nan")
    from math import erfc, sqrt
    t = rho * sqrt((n - 2) / max(1e-12, 1.0 - rho * rho))
    # normal approximation of the t tail (n is in the tens of thousands)
    return float(erfc(abs(t) / sqrt(2.0)))


def within_unit_spearman(pred, truth, units):
    """Spearman inside each ranking unit, pooled by rank-averaging.

    Ranks are taken WITHIN unit and then correlated across the pooled rows, so
    every unit contributes on its own scale (the recovered convention: the
    ranking unit is the comparison frame, not a filter)."""
    ok = np.isfinite(pred) & np.isfinite(truth)
    if int(ok.sum()) < 10:
        return float("nan"), float("nan"), 0
    p = np.full(pred.size, np.nan)
    t = np.full(pred.size, np.nan)
    u = units
    order = np.argsort(u, kind="stable")
    uu = u[order]
    edges = np.flatnonzero(np.diff(uu)) + 1
    for a, b in zip(np.concatenate(([0], edges)).tolist(),
                    np.concatenate((edges, [uu.size])).tolist()):
        idx = order[a:b]
        sel = idx[ok[idx]]
        if sel.size < 3:
            continue
        p[sel] = (rankdata(pred[sel]) - 0.5) / sel.size
        t[sel] = (rankdata(truth[sel]) - 0.5) / sel.size
    return spearman(p, t)


def dollar_recall(pred, cert, units, k):
    """Sum of walled-cert $ of the top-k by prediction / top-k by truth."""
    ok = np.isfinite(pred) & np.isfinite(cert)
    if not ok.any():
        return float("nan")
    got = ideal = 0.0
    order = np.argsort(units, kind="stable")
    uu = units[order]
    edges = np.flatnonzero(np.diff(uu)) + 1
    for a, b in zip(np.concatenate(([0], edges)).tolist(),
                    np.concatenate((edges, [uu.size])).tolist()):
        idx = order[a:b]
        sel = idx[ok[idx]]
        if sel.size == 0:
            continue
        kk = min(k, sel.size)
        pi = sel[np.argsort(-pred[sel], kind="stable")[:kk]]
        ti = sel[np.argsort(-cert[sel], kind="stable")[:kk]]
        got += float(cert[pi].sum())
        ideal += float(cert[ti].sum())
    return (got / ideal) if ideal > 0 else float("nan")


def fold_slices(dates, n_folds=N_FOLDS):
    """Expanding walk-forward: n_folds+1 contiguous session blocks."""
    u = np.unique(dates)
    if u.size < (n_folds + 1) * 5:
        return []
    cuts = np.array_split(u, n_folds + 1)
    out = []
    for i in range(n_folds):
        tr = np.isin(dates, np.concatenate(cuts[:i + 1]))
        va = np.isin(dates, cuts[i + 1])
        out.append((tr, va))
    return out


def _fit_one(j):
    """Fit + score one label (runs in a forked worker; ctx is shared)."""
    t0 = time.time()
    ctx = _CTX
    y = ctx["Y"][:, j].astype(np.float64)
    meta = ctx["meta"][j]
    unit_name = meta.unit or DEFAULT_UNIT
    units = ctx["units"][unit_name]
    rhos, pred_all = [], np.full(y.size, np.nan)
    for (tr, va) in ctx["folds"]:
        trm = tr & np.isfinite(y)
        vam = va & np.isfinite(y)
        if int(trm.sum()) < 500 or int(vam.sum()) < 100:
            continue
        d = xgb.DMatrix(ctx["X"][trm], label=y[trm])
        b = xgb.train(GBT, d, ROUNDS)
        p = b.predict(xgb.DMatrix(ctx["X"][vam]))
        pred_all[vam] = p
        r, _p, _n = spearman(p, y[vam])
        if np.isfinite(r):
            rhos.append(r)
    if not rhos:
        return None
    align, ap, _n = within_unit_spearman(pred_all, ctx["net_pc"], units)
    dr3 = dollar_recall(pred_all, ctx["cert"], units, 3)
    dr10 = dollar_recall(pred_all, ctx["cert"], units, 10)
    eras = []
    for yy in sorted(set(ctx["year"].tolist())):
        sel = ctx["year"] == yy
        if int(sel.sum()) < 200:
            continue
        a, _, _ = within_unit_spearman(pred_all[sel], ctx["net_pc"][sel],
                                       units[sel])
        if np.isfinite(a):
            eras.append(a)
    sign_ok = (float(np.mean(np.sign(eras) == np.sign(align)))
               if eras and np.isfinite(align) else float("nan"))
    return {"j": j, "n_rows": int(np.isfinite(y).sum()), "n_folds": len(rhos),
            "rho_median": float(np.median(rhos)), "rho_min": float(min(rhos)),
            "rho_max": float(max(rhos)), "align": align, "align_p": ap,
            "dr3": dr3, "dr10": dr10, "era_sign": sign_ok,
            "era_min": float(min(eras)) if eras else float("nan"),
            "era_max": float(max(eras)) if eras else float("nan"),
            "secs": time.time() - t0}


def holm(pvals):
    """Holm step-down: returns (rank, threshold, significant) per index."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: (np.inf if not np.isfinite(pvals[i])
                                            else pvals[i]))
    rank = [0] * m
    thr = [float("nan")] * m
    sig = [0] * m
    still = True
    for r, i in enumerate(order):
        rank[i] = r + 1
        thr[i] = 0.05 / (m - r)
        p = pvals[i]
        if still and np.isfinite(p) and p <= thr[i]:
            sig[i] = 1
        else:
            still = False
    return rank, thr, sig


def build_asset(asset):
    """Universe, atoms, features, label matrix (one pass, deterministic)."""
    arr, sides = S.load_asset(asset)
    roster = S.load_roster(asset)
    cid, bad = S.check_join(arr, roster)
    if bad:
        raise RuntimeError("%s: skeleton/roster join mismatch %r" % (asset, bad))
    fit = S.era_mask(roster, cid)
    sub = S.subsample_mask(arr["cand_id"])
    rows = np.nonzero(fit & sub)[0]
    fz = np.load(S.out_path("features_%s.npz" % asset), allow_pickle=False)
    frows = fz["rows"].astype(np.int64)
    F = fz["features"]
    fnames = [str(x) for x in fz["names"]]
    fz.close()
    pos = {int(r): i for i, r in enumerate(frows.tolist())}
    take = np.array([pos[int(r)] for r in rows.tolist()], dtype=np.int64)
    Xf = np.ascontiguousarray(F[take])
    cost = S.cost_rt_per_row(asset, roster, cid)
    wall = S.wall_usd(asset)
    sigma = _sigma_per_row(asset, roster, cid)
    atoms = L.Atoms(asset, arr, roster, cid, rows, cost, wall, sigma)
    return arr, roster, cid, rows, Xf, fnames, atoms


def _sigma_per_row(asset, roster, cid):
    import datetime as dt
    out = np.full(cid.size, np.nan)
    cols = None
    lut = {}
    with open(M.out_path("fvol", "fvol_forecasts.tsv")) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            r = dict(zip(cols, f))
            if r["asset"] != asset or r["segment"] != "SESSION":
                continue
            d = dt.date.fromisoformat(r["trade_date"])
            v = r.get("sigma_hat_usd", "")
            lut[d.year * 10000 + d.month * 100 + d.day] = \
                float(v) if v not in ("", None) else float("nan")
    d8 = roster["date8"][cid].astype(np.int64)
    for i, d in enumerate(d8.tolist()):
        out[i] = lut.get(d, np.nan)
    return out


def screen_asset(asset, workers):
    arr, roster, cid, rows, Xf, fnames, atoms = build_asset(asset)
    M.hb("s4 screen %s: universe %d rows x %d features"
         % (asset, rows.size, Xf.shape[1]))
    metas, cols, prunes = [], [], None
    for item in L.enumerate_grid(atoms):
        if item[0] == "__PRUNES__":
            prunes = item[1]
            break
        m, v = item
        metas.append(m)
        cols.append(np.asarray(v, dtype=np.float32))
    Y = np.column_stack(cols) if cols else np.zeros((rows.size, 0), np.float32)
    del cols
    L.assert_no_fprox([m.name for m in metas])
    M.hb("s4 screen %s: %d labels kept, prunes %s" % (asset, len(metas),
                                                      prunes))

    net_pc = atoms.net("phase_close")
    cert = atoms.cert[(1.0, "phase_close")][0]
    dates = atoms.date8
    _CTX.clear()
    _CTX.update({"X": Xf, "Y": Y, "meta": metas, "net_pc": net_pc,
                 "cert": cert, "year": (dates // 10000).astype(np.int64),
                 "units": {u: atoms.unit[u] for u in L.RANKING_UNITS},
                 "folds": fold_slices(dates)})
    if not _CTX["folds"]:
        raise RuntimeError("%s: not enough FIT sessions for %d folds"
                           % (asset, N_FOLDS))
    idx = list(range(len(metas)))
    t0 = time.time()
    if workers <= 1:
        res = [_fit_one(j) for j in idx]
    else:
        with mp.Pool(workers) as pool:
            res = list(pool.imap(_fit_one, idx, chunksize=8))
    res = [r for r in res if r is not None]
    M.hb("s4 screen %s: %d labels fitted in %.0fs" % (asset, len(res),
                                                      time.time() - t0))

    by_j = {r["j"]: r for r in res}
    pv = [by_j[j]["align_p"] if j in by_j else float("nan")
          for j in range(len(metas))]
    hr, ht, hs = holm(pv)
    twin_align = {}
    for j, m in enumerate(metas):
        if m.shuffled and j in by_j:
            twin_align[m.name.replace("_SHUF", "")] = by_j[j]["align"]
    out = []
    for j, m in enumerate(metas):
        r = by_j.get(j)
        if r is None:
            continue
        ta = twin_align.get(m.name, float("nan"))
        void = int(bool(m.occupancy_derived and not m.shuffled
                        and np.isfinite(ta) and np.isfinite(r["align"])
                        and abs(ta) >= abs(r["align"])))
        out.append([asset] + m.row()[:11]
                   + [r["n_rows"], r["n_folds"], r["rho_median"], r["rho_min"],
                      r["rho_max"], r["align"], r["align_p"], r["dr3"],
                      r["dr10"], r["era_sign"], r["era_min"], r["era_max"],
                      hr[j], ht[j], hs[j], ta, void, r["secs"]])
    return out, metas, prunes, len(rows), fnames, degeneracy_check(asset,
                                                                   atoms)


def degeneracy_check(asset, atoms):
    """LABEL_ATLAS_V2 4.2b: the shadow channel collapses to rank(net) when one
    fill fits the mark's window, and the occupancy ratio is a property of the
    MARK, not of the label - so every mark is checked separately (§4.2)."""
    rows = []
    sess_span = {}
    for d in np.unique(atoms.date8).tolist():
        sel = atoms.date8 == d
        sess_span[d] = float(np.nanmax(atoms.mark_sec["sess_close"][sel])
                             - np.nanmin(atoms.anchor_sec[sel])) \
            if sel.any() else np.nan
    for h in L.SHADOW_MARKS:
        sv, _occ = L.shadow_value(atoms, h)
        net = atoms.net(h)
        rho, p, n = within_unit_spearman(sv, net, atoms.unit["session"])
        span = atoms.mark_sec[h] - atoms.anchor_sec
        ratios = []
        for d in np.unique(atoms.date8).tolist():
            sel = atoms.date8 == d
            sp = sess_span.get(d, np.nan)
            if np.isfinite(sp) and sp > 0:
                ratios.append(float(np.nanmedian(span[sel])) / sp)
        rows.append([asset, h, float(np.median(ratios)) if ratios else np.nan,
                     rho, p, n, int(np.isfinite(sv).sum()),
                     "DEGENERATE (collapses to rank(net))"
                     if (np.isfinite(rho) and abs(rho) >= 0.99) else ""])
    return rows


def main():
    S.verify_spec()
    workers = int(os.environ.get("M1_WORKERS", "5"))
    assets = [a for a in sys.argv[1:] if a in S.ASSETS] or list(S.ASSETS)
    phash = C.params_hash(PARAMS)
    rows_all, member_rows, prune_rows, deg_rows = [], [], [], []
    for asset in assets:
        out, metas, prunes, n, fnames, deg = screen_asset(asset, workers)
        deg_rows.extend(deg)
        rows_all.extend(out)
        for m in metas:
            member_rows.append([asset] + m.row())
        for k in sorted(prunes):
            prune_rows.append([asset, k, prunes[k]])
        prune_rows.append([asset, "KEPT", len(metas)])
        prune_rows.append([asset, "UNIVERSE_ROWS", n])
    M.write_tsv(S.out_path("screen_ledger.tsv"), SECTION, phash,
                SCORE_COLUMNS, rows_all, spec="PORT_M1B",
                extra=["EXPLORATORY_NONCERTIFYING; FIT era only; no promotion "
                       "claims", "scoring is reported separately: learnability "
                       "(rho vs own truth) vs economic alignment (within-unit "
                       "Spearman vs net_phase_close, dollar_recall@k)"])
    M.write_tsv(S.out_path("grid_members.tsv"), SECTION, phash,
                ["asset"] + L.MEMBER_COLUMNS, member_rows, spec="PORT_M1B",
                extra=["the enumerated compose() grid after prunes P1-P10"])
    M.write_tsv(S.out_path("grid_prunes.tsv"), SECTION, phash,
                ["asset", "prune", "n"], prune_rows, spec="PORT_M1B",
                extra=["P1-P8 structural (LABEL_ATLAS_V2 §1B), P9 degenerate, "
                       "P10 byte-identical collapse"])
    M.write_tsv(S.out_path("shadow_degeneracy.tsv"), SECTION, phash,
                ["asset", "mark", "occupancy_ratio_median",
                 "spearman_shadow_vs_net", "p_value", "n_scored",
                 "n_shadow_finite", "verdict"], deg_rows, spec="PORT_M1B",
                extra=["LABEL_ATLAS_V2 4.2b degeneracy check, run per MARK "
                       "(the ratio is a property of the mark, not the label)"])
    M.write_json(S.out_path("screen_env.json"),
                 {"spec_section": SECTION, "env": M.env_receipt(PARAMS),
                  "params_hash": phash, "assets": assets})
    return 0


if __name__ == "__main__":
    sys.exit(main())
