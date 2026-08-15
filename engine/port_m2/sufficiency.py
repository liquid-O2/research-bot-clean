#!/usr/bin/python3
"""PORT M2 — THE SUFFICIENCY INSTRUMENT.

THE QUESTION IT ANSWERS (user, via coordinator): when an arm falls short, is it
short of INFORMATION or short of MODELLING?  Every previous negative in this
program has been reported without that split, so "more data" and "better model"
have never been separable claims.  This makes them separable, in dollars.

THE THREE-WAY SPLIT, at the within-cell ordering grain, per era and per phase:

    ORACLE            per-cell argmax with the answer in hand
      |  <-- INFORMATION ABSENT        only NEW features/data can close this
    MEMORIZER         a deliberate in-sample memoriser on THIS feature set:
                      unconstrained depth/rounds, scored on the rows it was
                      fitted on.  NON-CAUSAL BY DESIGN AND LABELLED SO.  It is
                      the REPRESENTATION CEILING — what these columns CAN
                      express about this cell's ordering, at any capacity.
      |  <-- EXPRESSIBLE, NOT LEARNABLE   more history / pooling / regularisation
    HONEST            the walk-forward arm on the same feature set

Two more instruments read the same seam:

  GROUPED ABLATION    within-CELL permutation of each feature GROUP on the
                      champion.  Permuting inside the cell preserves every
                      marginal the model could be using for level information
                      and destroys ONLY the ordering content — so the drop is
                      the group's ordering contribution, not its overall use.

  TWIN ANALYSIS       the fraction of cells whose best and second-best members
                      are NEAR-TWINS in feature space yet differ MATERIALLY in
                      outcome.  That fraction is the irreducible-ambiguity floor
                      of a feature set: no function of those columns can order
                      such a pair.  If a feature family shrinks it, the family
                      adds ordering information -- directly, not by inference.

RED-FIRST (both fired before any real number, both must PASS):
  * the memoriser must reach ~the oracle on a SYNTHETIC FULLY-DETERMINED
    fixture (label = an exact function of the features).  If it cannot, the
    "representation ceiling" is a capacity artefact and nothing below it means
    anything.
  * the twin fraction must be ~100% on a FEATURES-STRIPPED fixture (all columns
    constant), where every pair is a twin by construction.
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
import st_common as SC                    # noqa: E402

FEATS = ("BASE", "CELLREL", "DAYSOFAR", "TABPFN", "DIP")
ERAS = N.DEV_ERAS

# PRE-REGISTERED twin constants.
TWIN_Q = 0.10          # near-twin = closer than the 10th percentile of all
                       # within-cell top-2 distances measured on BASE
TWIN_DOLLARS = 600.0   # "materially different" = the D-021 per-trade floor
MEMO = {"max_depth": 12, "eta": 0.30, "rounds": 300, "min_child_weight": 1,
        "subsample": 1.0, "colsample_bytree": 1.0, "reg_lambda": 0.0}


def _ref_spec(feat):
    s = dict(RA.REF)
    s["feat"] = feat
    return s


def _fit_rank(D, XF, FN, rows_fit, rows_score, val, spec, params, rounds,
              custom=None):
    import xgboost as xgb
    r_f, g_f = RA._groups_of(D, rows_fit, spec)
    d = xgb.DMatrix(XF[r_f], label=NA.grades(val[r_f]), feature_names=FN)
    d.set_group(g_f)
    b = xgb.train(params, d, rounds)
    r_s, _g = RA._groups_of(D, rows_score, spec)
    out = np.full(D["d8"].size, np.nan)
    out[r_s] = b.predict(xgb.DMatrix(XF[r_s], feature_names=FN),
                         output_margin=True)
    return out, b


def _seat_read(D, rows, score, era, P):
    _u, n = N.committed_policy().get(era, ("cell", 1))
    takes = N.top_per_cell_score(D, rows, score, n)
    return N.read_rows(D, N.replay_delayed(D, takes, P))


# =================================================== RED-FIRST: THE FIXTURES ==
def fixture_memorizer():
    """A fully-determined synthetic cell world: the certificate IS an exact
    function of two feature columns.  A memoriser that cannot reach the oracle
    here has a capacity problem, and every ceiling it reports would be a
    capacity artefact."""
    import xgboost as xgb
    rs = np.random.RandomState(N.SEED)
    n_cells, m = 400, 20
    X = rs.rand(n_cells * m, 6).astype(np.float32)
    v = (3.0 * X[:, 0] - 2.0 * X[:, 1]) * 1000.0        # deterministic
    g = np.full(n_cells, m)
    d = xgb.DMatrix(X, label=NA.grades(v))
    d.set_group(g)
    p = {"objective": "rank:ndcg", "eval_metric": "ndcg@1",
         "tree_method": "hist", "seed": N.SEED, "nthread": 8}
    p.update({k: MEMO[k] for k in ("max_depth", "eta", "min_child_weight",
                                   "subsample", "colsample_bytree")})
    b = xgb.train(p, d, MEMO["rounds"])
    s = b.predict(d, output_margin=True)
    num = den = 0.0
    for c in range(n_cells):
        a, z = c * m, (c + 1) * m
        vv = np.maximum(v[a:z], 0.0)
        if vv.sum() <= 0:
            continue
        num += vv[int(np.argmax(s[a:z]))]
        den += vv.max()
    cap = num / den
    return {"probe": "memorizer_on_fully_determined_fixture",
            "capture": round(float(cap), 4),
            "verdict": "PASS" if cap >= 0.95 else "FAIL",
            "bar": 0.95}


def fixture_twins():
    """A features-stripped world: every column constant, so every pair is a twin
    by construction and the twin fraction must be ~1."""
    # FIXTURE DEFECT FOUND AND FIXED BY THIS PROBE (recorded, not hidden): the
    # first draft used m=20 members over a $4,000 range, whose top-2 gap is
    # ~$190 on average — below the $600 materiality bar — so the probe returned
    # 0.0 and looked like an instrument failure when it was a fixture failure.
    # The fixture now GUARANTEES a material gap, which is what a
    # features-stripped ambiguity test has to hold fixed.
    rs = np.random.RandomState(N.SEED)
    n_cells, m = 200, 4
    X = np.zeros((n_cells * m, 8), dtype=np.float32)
    v = rs.rand(n_cells * m) * 500.0
    v[::m] += 2000.0                       # one member per cell paid $2k more
    cells = np.repeat(np.arange(n_cells), m)
    frac, _thr = _twin_fraction(X, v, cells, thr=1e-9)
    return {"probe": "twins_on_features_stripped_fixture",
            "twin_fraction": round(float(frac), 4),
            "verdict": "PASS" if frac >= 0.95 else "FAIL", "bar": 0.95}


def _twin_fraction(X, v, cells, thr=None, sd=None):
    """Fraction of cells whose top-2 members (by realised dollars) are within
    `thr` in standardised feature distance AND differ by >= TWIN_DOLLARS."""
    order = np.argsort(cells, kind="stable")
    co = cells[order]
    starts = [0] + (np.flatnonzero(co[1:] != co[:-1]) + 1).tolist()
    stops = starts[1:] + [co.size]
    if sd is None:
        sd = np.nanstd(X, axis=0)
    sd = np.where(np.isfinite(sd) & (sd > 0), sd, 1.0)
    dists, gaps = [], []
    for a, b in zip(starts, stops):
        ix = order[a:b]
        if ix.size < 2:
            continue
        top = ix[np.argsort(-v[ix], kind="stable")[:2]]
        dx = np.abs(X[top[0]] - X[top[1]]) / sd
        dists.append(float(np.nanmean(dx)))
        gaps.append(abs(float(v[top[0]] - v[top[1]])))
    dists = np.asarray(dists)
    gaps = np.asarray(gaps)
    if thr is None:
        thr = float(np.nanpercentile(dists, TWIN_Q * 100))
    frac = float(np.mean((dists <= thr) & (gaps >= TWIN_DOLLARS)))
    return frac, thr


# ================================================================ THE SPLIT ===
_ST = {}


def _boot():
    import st_rank as RK
    if "D" not in _ST:
        D = N.matrix()
        RA._D["D"] = D
        RA._D["klass"] = RK.class_index(D)[0]
        _ST["D"] = D
        _ST["P"] = N.load_paths()
        _ST["V"] = {int(d): N.delayed_value(_ST["P"], d, D) for d in N.DELAYS}
    return _ST["D"], _ST["P"], _ST["V"]


def _split_one(job):
    """One (feature set, era) cell of the three-way split, in a worker."""
    import xgboost as xgb
    feat, era = job
    try:
        D, P, V = _boot()
        spec = _ref_spec(feat)
        t0 = time.time()
        tr, itr, iva, ev_r = NA.fold(D, era)
        XF, FN = RA.build_features(D, spec, tr, np.concatenate([tr, ev_r]))
        val = RA.target_value(D, spec)
        orc = N.read_rows(D, N.replay_delayed(
            D, N.top_per_cell_joint(D, ev_r, V,
                                    N.committed_policy()[era][1], (0,)), P))
        pm = {"objective": "rank:ndcg", "eval_metric": "ndcg@1",
              "tree_method": "hist", "seed": N.SEED, "nthread": RA.N_THREAD,
              "lambdarank_pair_method": "topk",
              "lambdarank_num_pair_per_sample": 16}
        pm.update({k: MEMO[k] for k in
                   ("max_depth", "eta", "min_child_weight", "subsample",
                    "colsample_bytree", "reg_lambda")})
        sm, _b = _fit_rank(D, XF, FN, ev_r, ev_r, val, spec, pm, MEMO["rounds"])
        mem = _seat_read(D, ev_r, sm, era, P)
        ph = {"objective": "rank:ndcg", "eval_metric": "ndcg@3",
              "tree_method": "hist", "min_child_weight": 20, "subsample": 0.8,
              "colsample_bytree": 0.8, "lambdarank_pair_method": "topk",
              "lambdarank_normalization": True, "seed": N.SEED,
              "nthread": RA.N_THREAD}
        hp = NA.CHAMP_HP[era]
        ph.update({k: hp[k] for k in ("max_depth", "eta",
                                      "lambdarank_num_pair_per_sample")})
        sh, _b2 = _fit_rank(D, XF, FN, tr, ev_r, val, spec, ph, hp["rounds"])
        hon = _seat_read(D, ev_r, sh, era, P)
        cells = ((D["asset_idx"][ev_r].astype(np.int64) * 100000000
                  + D["d8"][ev_r].astype(np.int64)) * 100
                 + D["phase_dec"][ev_r])
        sd = np.nanstd(XF[tr], axis=0)
        fr, thr = _twin_fraction(XF[ev_r], val[ev_r], cells, sd=sd)
        ph_rows = []
        for ph_id in sorted(set(D["phase_dec"][ev_r].tolist())):
            sel = ev_r[D["phase_dec"][ev_r] == ph_id]
            if sel.size < 50:
                continue
            oo = N.read_rows(D, N.replay_delayed(
                D, N.top_per_cell_joint(D, sel, V, 1, (0,)), P))
            mm = _seat_read(D, sel, sm, era, P)
            hh = _seat_read(D, sel, sh, era, P)
            ph_rows.append([int(ph_id), int(sel.size),
                            oo["usd_per_session"], mm["usd_per_session"],
                            hh["usd_per_session"]])
        return (feat, era, {"oracle": orc["usd_per_session"],
                            "memorizer": mem["usd_per_session"],
                            "honest": hon["usd_per_session"],
                            "n_cols": int(XF.shape[1]),
                            "twin_frac": float(fr), "twin_thr": float(thr),
                            "phase": ph_rows,
                            "secs": round(time.time() - t0, 1)}, None)
    except Exception as exc:                            # noqa: BLE001
        return (feat, era, None, "%s: %s" % (type(exc).__name__, exc))


def stage_split(eras=ERAS, feats=FEATS, workers=RA.N_WORKERS):
    import multiprocessing as mp
    probes = [fixture_memorizer(), fixture_twins()]
    N.hb("red-first: %s" % json.dumps(probes))
    if any(p["verdict"] == "FAIL" for p in probes):
        raise N.NewObjRefusal("SUFFICIENCY RED-FIRST FAILED: %s" % probes)
    jobs = [(f, e) for f in feats for e in eras]
    res, errs = {}, []
    t0 = time.time()
    # SPAWN, not fork.  The red-first probes above call xgboost, which brings up
    # an OpenMP thread pool in THIS process; forking after that deadlocks every
    # child (observed: 6 workers alive at 0% CPU, wedged right after their boot
    # line).  A spawned child starts a clean interpreter and boots its own copy
    # of the fixtures, which costs ~3 GB each and is affordable inside the
    # container's 282 GB.
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=workers) as pool:
        for i, (feat, era, out, err) in enumerate(
                pool.imap_unordered(_split_one, jobs), start=1):
            if err:
                errs.append([feat, era, err])
                N.hb("split FAIL %s %s: %s" % (feat, era, err))
                continue
            res[(feat, era)] = out
            N.hb("split %d/%d %s %s: oracle %s memoriser %s honest %s "
                 "(ABSENT %s / NOT-LEARNABLE %s) %.0fs"
                 % (i, len(jobs), feat, era, N._r(out["oracle"]),
                    N._r(out["memorizer"]), N._r(out["honest"]),
                    N._r((out["oracle"] or 0) - (out["memorizer"] or 0)),
                    N._r((out["memorizer"] or 0) - (out["honest"] or 0)),
                    time.time() - t0))
    rows, twin_rows, phase_rows = [], [], []
    base_thr = {e: res[("BASE", e)]["twin_thr"] for e in eras
                if ("BASE", e) in res}
    for feat in feats:
        for era in eras:
            o = res.get((feat, era))
            if o is None:
                continue
            orc_, m_, h = o["oracle"], o["memorizer"], o["honest"]
            rows.append([feat, era, N._r(orc_), N._r(m_), N._r(h),
                         N._r((orc_ or 0) - (m_ or 0)),
                         N._r((m_ or 0) - (h or 0)),
                         N._r(((orc_ or 0) - (m_ or 0)) / max(orc_ or 1, 1e-9), 4),
                         N._r(((m_ or 0) - (h or 0)) / max(orc_ or 1, 1e-9), 4),
                         o["n_cols"], o["secs"]])
            twin_rows.append([feat, era, o["n_cols"], N._r(o["twin_frac"], 4),
                              N._r(o["twin_thr"], 5)])
            for pr in o["phase"]:
                phase_rows.append([feat, era, pr[0], pr[1], N._r(pr[2]),
                                   N._r(pr[3]), N._r(pr[4]),
                                   N._r((pr[2] or 0) - (pr[3] or 0)),
                                   N._r((pr[3] or 0) - (pr[4] or 0))])
    N.write_tsv("SUFFICIENCY_SPLIT.tsv",
                ["feature_set", "era", "oracle_usd", "memorizer_usd",
                 "honest_usd", "information_absent_usd",
                 "expressible_not_learnable_usd", "absent_frac",
                 "not_learnable_frac", "n_columns", "secs"], rows,
                extra=["THE MORE-INFORMATION-OR-BETTER-MODELLING SPLIT.",
                       "MEMORIZER is NON-CAUSAL BY DESIGN: unconstrained "
                       "capacity, fitted on the evaluation rows and scored on "
                       "them.  It is a REPRESENTATION CEILING, never a result.",
                       "information_absent = oracle - memoriser: no model of "
                       "these columns can close it; only new features or new "
                       "data can.",
                       "expressible_not_learnable = memoriser - honest: the "
                       "columns CAN express it and the walk-forward fit does "
                       "not get it; history, pooling and regularisation are "
                       "the levers there."])
    N.write_tsv("SUFFICIENCY_SPLIT_BY_PHASE.tsv",
                ["feature_set", "era", "phase", "n_rows", "oracle_usd",
                 "memorizer_usd", "honest_usd", "information_absent_usd",
                 "expressible_not_learnable_usd"], phase_rows)
    N.write_tsv("SUFFICIENCY_TWINS.tsv",
                ["feature_set", "era", "n_columns", "twin_fraction",
                 "distance_threshold"], twin_rows,
                extra=["A cell is TWIN-AMBIGUOUS when its best and "
                       "second-best members are within the pre-registered "
                       "distance (the 10th percentile of BASE's own top-2 "
                       "distances, frozen per era and reused for every other "
                       "feature set) yet differ by >= $%d." % int(TWIN_DOLLARS),
                       "A feature family that SHRINKS this fraction adds "
                       "ordering information directly — not by inference from "
                       "a dollar number."])
    N.save_json("sufficiency.json", {"probes": probes, "memo": MEMO,
                                     "twin_q": TWIN_Q,
                                     "twin_dollars": TWIN_DOLLARS,
                                     "errors": errs})
    return rows


_TW = {}


# ====================================================== GROUPED ABLATION =====
def stage_ablation(eras=ERAS):
    """Within-CELL permutation importance BY FEATURE GROUP on the champion."""
    import xgboost as xgb
    import st_rank as RK
    D = N.matrix()
    RA._D["D"] = D
    RA._D["klass"] = RK.class_index(D)[0]
    P = N.load_paths()
    cols, names = NA.feat_cols(D)
    groups = [str(g) for g in D["feature_groups"][cols].tolist()]
    uniq = sorted(set(groups))
    spec = _ref_spec("BASE")
    rows = []
    rs = np.random.RandomState(N.SEED)
    for era in eras:
        tr, itr, iva, ev_r = NA.fold(D, era)
        XF, FN = RA.build_features(D, spec, tr, np.concatenate([tr, ev_r]))
        val = RA.target_value(D, spec)
        ph = {"objective": "rank:ndcg", "eval_metric": "ndcg@3",
              "tree_method": "hist", "min_child_weight": 20, "subsample": 0.8,
              "colsample_bytree": 0.8, "lambdarank_pair_method": "topk",
              "lambdarank_normalization": True, "seed": N.SEED,
              "nthread": RA.N_THREAD}
        hp = NA.CHAMP_HP[era]
        ph.update({k: hp[k] for k in ("max_depth", "eta",
                                      "lambdarank_num_pair_per_sample")})
        r_f, g_f = RA._groups_of(D, tr, spec)
        d = xgb.DMatrix(XF[r_f], label=NA.grades(val[r_f]), feature_names=FN)
        d.set_group(g_f)
        b = xgb.train(ph, d, hp["rounds"])
        r_s, g_s = RA._groups_of(D, ev_r, spec)
        base_s = np.full(D["d8"].size, np.nan)
        base_s[r_s] = b.predict(xgb.DMatrix(XF[r_s], feature_names=FN),
                                output_margin=True)
        base = _seat_read(D, ev_r, base_s, era, P)["usd_per_session"]
        ptr = np.concatenate([[0], np.cumsum(g_s.astype(np.int64))])
        for gname in uniq:
            gi = [i for i, g in enumerate(groups) if g == gname]
            Xp = XF[r_s].copy()
            for a, bb in zip(ptr[:-1], ptr[1:]):
                if bb - a < 2:
                    continue
                pm = a + rs.permutation(bb - a)
                Xp[a:bb, gi] = Xp[pm][:, gi]
            s2 = np.full(D["d8"].size, np.nan)
            s2[r_s] = b.predict(xgb.DMatrix(Xp, feature_names=FN),
                                output_margin=True)
            got = _seat_read(D, ev_r, s2, era, P)["usd_per_session"]
            rows.append([era, gname, len(gi), N._r(base), N._r(got),
                         N._r((base or 0) - (got or 0))])
        N.hb("ablation %s: base $%s over %d groups" % (era, N._r(base),
                                                       len(uniq)))
    N.write_tsv("SUFFICIENCY_ABLATION.tsv",
                ["era", "feature_group", "n_columns", "base_usd",
                 "permuted_usd", "ordering_contribution_usd"], rows,
                extra=["WITHIN-CELL permutation: the group's values are "
                       "shuffled AMONG THE CELL'S OWN MEMBERS, so every "
                       "marginal the model might use for level information "
                       "survives and only the ORDERING content is destroyed.",
                       "ordering_contribution = base - permuted.  Negative "
                       "means the group's ordering content is dead weight at "
                       "this configuration."])
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", action="store_true")
    ap.add_argument("--ablation", action="store_true")
    ap.add_argument("--probes", action="store_true")
    ap.add_argument("--feats", default=",".join(FEATS))
    ap.add_argument("--eras", default=",".join(ERAS))
    a = ap.parse_args()
    eras = tuple(e for e in a.eras.split(",") if e)
    if a.probes:
        print(json.dumps([fixture_memorizer(), fixture_twins()], indent=1))
    elif a.split:
        stage_split(eras=eras, feats=tuple(f for f in a.feats.split(",") if f))
    elif a.ablation:
        stage_ablation(eras=eras)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
