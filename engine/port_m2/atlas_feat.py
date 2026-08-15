#!/usr/bin/python3
"""PORT M2 RANKING ATLAS — THE FEATURE-SET AXIS.

THE GAP THE AXIS ATTACKS (coordinator, user-directed): the champion's 184
columns describe a candidate **in isolation**.  The act it is fitted for is a
comparison *between cell-mates*, and a tree can only compare two rows through
whatever each row carries on its own.  Nothing in the matrix tells a row how it
stands relative to the members it is competing against.  That is a structural
mismatch with the named dominant deficit (`SEL_WRONG_MEMBER` /
`RANKING_RESIDUAL`), and it is the one gap the feature review found that is
aligned with the deficit rather than with a general wish for more data.

FIVE FAMILIES.  Every one is STRICTLY CAUSAL at the decision second, and every
one carries a FUTURE-PEEKING MUTANT that the red-first stage must CATCH (the
mutant must score ABOVE the causal family — that is what proves the harness sees
information when it is there; a mutant that lands at chance would mean the
instrument is blind, not that the family is clean).

  BASE      the champion's 184 non-`tf_` columns.  The reference level.
  CELLREL   per-member position among the cell-mates VISIBLE SO FAR
            (`dec_sec <= this member's dec_sec`, the member itself included):
            prefix rank, prefix z, prefix gap-to-best for each of the 20
            committed top-importance base features, plus the cell's own
            so-far shape (count, dispersion, elapsed fraction, arrival gap).
            THE MARQUEE: this is the only family that puts the comparison the
            deployment makes inside the row the model reads.
  DAYSOFAR  the session's own resolved history at t: how many earlier
            candidates have already CLOSED (`exit_close_sec <= t`), what they
            paid, the same-class subset, and the running realised sum.  Only
            closed episodes are readable — an open one has not resolved.
  TABPFN    the walk-forward TabPFN winner probability as an INPUT COLUMN, not
            a score blend.  TabPFN is the program's best GLOBAL winner
            classifier (AUC 0.687) and it DAMAGES within-cell ordering when
            blended (rho -0.107); as a feature the ranker may use it where it
            helps and ignore it where it does not.
  DIP       predicted adverse excursion before the peak, from a small auxiliary
            regressor fitted on the training block only (fold-dependent).

Cache: `artifacts/cache/port/m2/newobj/feat_*.npz` (the fold-independent
families are computed once over all 1,399,374 candidates).
"""
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
import m2_common as MC                    # noqa: E402
import m3_common as M3                    # noqa: E402

OUT = N.OUT_ROOT
PEEK_SEC = 3600                           # the mutant's look-ahead window

# The 20 columns the COMMITTED m3 walk ranked most important at E3 — i.e. from a
# model that had seen PRE_E1..E2 and nothing later, so the choice is causal for
# every fold of the ladder.  Read, never re-derived.
IMPORTANCE_TSV = os.path.join(M3.WALK_DIR, "IMPORTANCE.tsv")


def cellrel_base(k=20):
    rows = [l.rstrip("\n").split("\t") for l in open(IMPORTANCE_TSV)
            if not l.startswith("#")]
    h = rows[0]
    ie, ir, iff = h.index("era"), h.index("rank"), h.index("feature")
    out = [r[iff] for r in rows[1:] if r[ie] == "E3"]
    out = sorted(set(out), key=lambda f: [int(r[ir]) for r in rows[1:]
                                          if r[ie] == "E3" and r[iff] == f][0])
    return out[:k]


# ================================================================ CELLREL =====
def _cellrel_one(job):
    """One (asset, day): prefix statistics inside every phase CELL."""
    rows, dec, phase, Xs = job
    n = rows.size
    nf = Xs.shape[1]
    R = np.full((n, 3 * nf + 4), np.nan, dtype=np.float32)
    for p in np.unique(phase):
        m = np.nonzero(phase == p)[0]
        o = m[np.argsort(dec[m], kind="stable")]
        x = Xs[o].astype(np.float64)
        t = dec[o].astype(np.float64)
        mm = o.size
        idx = np.arange(mm)
        # prefix count / mean / std, O(m) via cumulative sums
        cnt = (idx + 1).astype(np.float64)
        cs = np.cumsum(x, axis=0)
        cs2 = np.cumsum(x * x, axis=0)
        mu = cs / cnt[:, None]
        var = np.maximum(cs2 / cnt[:, None] - mu * mu, 0.0)
        sd = np.sqrt(var)
        run_max = np.maximum.accumulate(x, axis=0)
        # prefix rank: #{j <= i : x_j <= x_i} / (i+1); vectorised per cell
        ge = (x[:, None, :] >= x[None, :, :])
        tri = np.tril(np.ones((mm, mm), dtype=bool))
        rank = (ge & tri[:, :, None]).sum(axis=1) / cnt[:, None]
        # a NaN feature has NO prefix rank; leaving the 0.0 that the comparison
        # produces would fabricate "worst in the cell" out of a missing reading
        rank[~np.isfinite(x)] = np.nan
        R[o, 0:nf] = rank
        R[o, nf:2 * nf] = (x - mu) / (sd + 1e-9)
        R[o, 2 * nf:3 * nf] = x - run_max
        span = max(1.0, float(t[-1] - t[0]))
        R[o, 3 * nf + 0] = cnt
        R[o, 3 * nf + 1] = sd[:, 0]
        R[o, 3 * nf + 2] = (t - t[0]) / span
        R[o, 3 * nf + 3] = np.concatenate([[0.0], np.diff(t)])
    return rows, R


def build_cellrel(workers=8, k=20):
    import multiprocessing as mp
    D = N.matrix()
    base = cellrel_base(k)
    cols = [D["names"].index(f) for f in base]
    names = (["cr_rank_%s" % f for f in base]
             + ["cr_z_%s" % f for f in base]
             + ["cr_gap_%s" % f for f in base]
             + ["cr_n_so_far", "cr_disp_top", "cr_elapsed_frac",
                "cr_since_prev_sec"])
    key = D["asset_idx"].astype(np.int64) * 100000000 + D["d8"].astype(np.int64)
    order = np.argsort(key, kind="stable")
    ko = key[order]
    starts = [0] + (np.flatnonzero(ko[1:] != ko[:-1]) + 1).tolist()
    stops = starts[1:] + [ko.size]
    Xc = D["X"][:, cols]
    jobs = [(order[a:b], D["dec_sec"][order[a:b]].astype(np.int64),
             D["phase_dec"][order[a:b]].astype(np.int64), Xc[order[a:b]])
            for a, b in zip(starts, stops)]
    out = np.full((D["d8"].size, len(names)), np.nan, dtype=np.float32)
    t0 = time.time()
    with mp.Pool(processes=workers) as pool:
        for i, (rr, R) in enumerate(pool.imap_unordered(_cellrel_one, jobs,
                                                        chunksize=4), start=1):
            out[rr] = R
            if i % 500 == 0 or i == len(jobs):
                N.hb("cellrel %d/%d sessions %.0fs" % (i, len(jobs),
                                                       time.time() - t0))
    np.savez(os.path.join(OUT, "feat_cellrel.npz"), X=out,
             names=np.array(names), base=np.array(base))
    N.hb("cellrel: %d columns over %d candidates (%.0fs)"
         % (len(names), out.shape[0], time.time() - t0))
    return out, names


# =============================================================== DAYSOFAR =====
def _daysofar_session(rows, dec, klass, exi, cert, peek=0):
    """Resolved-history columns for one (asset, day).  A prior candidate is
    READABLE only once it has CLOSED: `exit_close_sec <= t` (+ `peek` for the
    red-first mutant, which is a deliberate look-ahead)."""
    n = rows.size
    o = np.argsort(dec, kind="stable")
    t = dec[o].astype(np.float64)
    ex = exi[o].astype(np.float64)
    cv = np.nan_to_num(cert[o], nan=0.0)
    kl = klass[o]
    R = np.full((n, 8), np.nan, dtype=np.float32)
    span = max(1.0, float(t[-1] - t[0])) if n else 1.0
    for i in range(n):
        ti = t[i] + peek
        res = np.nonzero((ex <= ti) & (np.arange(n) != i) & (t < t[i] + 1))[0]
        prior = np.nonzero(t < t[i])[0]
        R[i, 0] = prior.size
        R[i, 1] = res.size
        if res.size:
            R[i, 2] = cv[res].mean()
            R[i, 3] = cv[res].sum()
            R[i, 4] = float((cv[res] > 0).mean())
            R[i, 7] = cv[res[np.argmax(ex[res])]]
        sc = res[kl[res] == kl[i]] if res.size else res
        R[i, 5] = sc.size
        R[i, 6] = cv[sc].mean() if sc.size else np.nan
    out = np.full((n, 8), np.nan, dtype=np.float32)
    out[o] = R
    el = np.full(n, np.nan, dtype=np.float32)
    el[o] = (t - t[0]) / span
    return out, el


def _daysofar_one(job):
    rows, dec, klass, exi, cert, peek = job
    R, el = _daysofar_session(rows, dec, klass, exi, cert, peek=peek)
    return rows, np.hstack([R, el.reshape(-1, 1)])


def build_daysofar(workers=8, peek=0, tag="daysofar"):
    import multiprocessing as mp
    import st_rank as RK
    D = N.matrix()
    klass, _ = RK.class_index(D)
    names = ["ds_n_prior", "ds_n_resolved", "ds_resolved_mean_usd",
             "ds_resolved_sum_usd", "ds_resolved_win_frac",
             "ds_same_class_resolved_n", "ds_same_class_resolved_mean_usd",
             "ds_last_resolved_usd", "ds_sess_elapsed_frac"]
    if peek:
        names = [n_ + "_PEEK" for n_ in names]
    key = D["asset_idx"].astype(np.int64) * 100000000 + D["d8"].astype(np.int64)
    order = np.argsort(key, kind="stable")
    ko = key[order]
    starts = [0] + (np.flatnonzero(ko[1:] != ko[:-1]) + 1).tolist()
    stops = starts[1:] + [ko.size]
    cert = D["cert_close_usd"].astype(np.float64)
    exi = D["exit_close_sec"].astype(np.float64)
    jobs = [(order[a:b], D["dec_sec"][order[a:b]].astype(np.int64),
             klass[order[a:b]], exi[order[a:b]], cert[order[a:b]], peek)
            for a, b in zip(starts, stops)]
    out = np.full((D["d8"].size, len(names)), np.nan, dtype=np.float32)
    t0 = time.time()
    with mp.Pool(processes=workers) as pool:
        for i, (rr, R) in enumerate(pool.imap_unordered(_daysofar_one, jobs,
                                                        chunksize=4), start=1):
            out[rr] = R
            if i % 500 == 0 or i == len(jobs):
                N.hb("%s %d/%d sessions %.0fs" % (tag, i, len(jobs),
                                                  time.time() - t0))
    np.savez(os.path.join(OUT, "feat_%s.npz" % tag), X=out,
             names=np.array(names))
    N.hb("%s: %d columns (%.0fs)" % (tag, len(names), time.time() - t0))
    return out, names


# ================================================================= TABPFN =====
def build_tabpfn():
    """The committed walk-forward TabPFN winner score as a COLUMN.

    Each era's value was produced by a TabPFN fitted strictly earlier
    (`FM_TABPFN_WINNER`, final pass §20), so the column is causal for every fold
    by construction.  Rows before E3 have no walk-forward value and stay NaN —
    xgboost/lightgbm/catboost all take NaN natively, so the model simply has no
    reading there rather than a fabricated one.
    """
    D = N.matrix()
    p = os.path.join(MC.M2_ROOT, "seqtest", "scores", "FM_TABPFN_WINNER.npz")
    z = np.load(p, allow_pickle=False)
    s = z["champ"].astype(np.float32)
    z.close()
    out = s.reshape(-1, 1)
    np.savez(os.path.join(OUT, "feat_tabpfn.npz"), X=out,
             names=np.array(["fx_tabpfn_winner_p"]))
    N.hb("tabpfn feature: %d/%d rows carry a walk-forward value"
         % (int(np.isfinite(s).sum()), s.size))
    return out, ["fx_tabpfn_winner_p"]


# ==================================================================== DIP =====
def dip_column(D, cols, tr_rows, all_rows, rounds=60):
    """Predicted adverse excursion before the peak — an auxiliary regressor
    fitted on the TRAINING BLOCK ONLY, so the column is fold-dependent and
    strictly causal."""
    import xgboost as xgb
    y = D["mae_before_argmax"].astype(np.float64)
    fit = tr_rows[np.isfinite(y[tr_rows])]
    cfg = {"objective": "reg:squarederror", "tree_method": "hist",
           "max_depth": 4, "eta": 0.08, "min_child_weight": 20,
           "subsample": 0.8, "colsample_bytree": 0.6, "seed": N.SEED,
           "nthread": 8}
    b = xgb.train(cfg, xgb.DMatrix(D["X"][:, cols][fit], label=y[fit]), rounds)
    out = np.full(D["d8"].size, np.nan, dtype=np.float32)
    out[all_rows] = b.predict(xgb.DMatrix(D["X"][:, cols][all_rows]))
    return out.reshape(-1, 1), ["fx_dip_pred_mae_usd"]


# ================================================================== loader ===
_FC = {}


def family(name):
    """Cached fold-independent feature family -> (X, names)."""
    if name in _FC:
        return _FC[name]
    if name == "BASE":
        _FC[name] = (None, [])
        return _FC[name]
    fn = {"CELLREL": "feat_cellrel.npz", "DAYSOFAR": "feat_daysofar.npz",
          "DAYSOFAR_PEEK": "feat_daysofar_peek.npz",
          "TABPFN": "feat_tabpfn.npz"}[name]
    p = os.path.join(OUT, fn)
    if not os.path.exists(p):
        raise N.NewObjRefusal("feature family %s not built (%s)" % (name, p))
    z = np.load(p, allow_pickle=False)
    _FC[name] = (z["X"], [str(x) for x in z["names"].tolist()])
    z.close()
    return _FC[name]


def build_all(workers=8):
    os.makedirs(OUT, exist_ok=True)
    build_cellrel(workers=workers)
    build_daysofar(workers=workers, peek=0, tag="daysofar")
    build_daysofar(workers=workers, peek=PEEK_SEC, tag="daysofar_peek")
    build_tabpfn()
    with open(os.path.join(OUT, "features.receipt.json"), "w") as fh:
        json.dump({"version": N.VERSION, "cellrel_base": cellrel_base(),
                   "peek_sec": PEEK_SEC,
                   "causality": ("CELLREL/DAYSOFAR read only rows with "
                                 "dec_sec <= t (CELLREL) or exit_close_sec <= t "
                                 "(DAYSOFAR); DAYSOFAR_PEEK deliberately reads "
                                 "exit_close_sec <= t+%d and MUST score ABOVE "
                                 "the causal family" % PEEK_SEC)}, fh, indent=1)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    if a.build:
        build_all(workers=a.workers)
    else:
        ap.print_help()
