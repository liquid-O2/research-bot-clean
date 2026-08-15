#!/usr/bin/python3
"""PORT M2 NEWOBJ — THE HONEST READS on the three enlarged decision objects.

The ceilings (`newobj.stage_ceilings`) say what the enlarged act is WORTH with
the answer in hand.  This file asks the only question that can be banked: does a
model that never sees the answer move realised dollars?

Everything is the champion's own code path (`CHAMPION_FREEZE_CANDIDATE.md`):
the 184 non-`tf_` columns, `rank:ndcg` with the frozen base parameters, the
12-cell inner-block HP grid, the PRE_E1..E(k-1) -> E(k) whole-day ladder, the
D-077 veto applied BEFORE grouping, `m3_walk`'s committed per-era (unit, N), and
`replay_delayed` (= `m3_walk.replay_rows` at D=0, proved seat-for-seat).

E8 QUARANTINE: every fit, every threshold and every selection is made on E3-E7.
E8 is scored once, blind, and never feeds a choice.
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
import st_common as SC                    # noqa: E402

# ------------------------------------------------ the champion, verbatim -----
# `CHAMPION_FREEZE_CANDIDATE.md` §2.5.  BASE is frozen; the 12-cell grid is
# searched on inner-validation NDCG@3 and nothing else.
BASE = {"objective": "rank:ndcg", "eval_metric": "ndcg@3", "tree_method": "hist",
        "min_child_weight": 20, "subsample": 0.8, "colsample_bytree": 0.8,
        "lambdarank_pair_method": "topk", "lambdarank_normalization": True,
        "seed": N.SEED, "nthread": 8}
HP_GRID = tuple({"max_depth": d, "eta": e,
                 "lambdarank_num_pair_per_sample": p}
                for d in (4, 6, 8) for e in (0.05, 0.10) for p in (8, 16))
ROUNDS, EARLY = 300, 25

# The per-era selection the champion spec pins, used ONLY where a nested search
# would be a second HP search inside an inner block (OBJ-2/OBJ-3's inner-block
# champion scores).  It was itself chosen on an inner block and never saw an
# evaluation era.
CHAMP_HP = {
    "E3": {"max_depth": 4, "eta": 0.10, "lambdarank_num_pair_per_sample": 8,
           "rounds": 74},
    "E4": {"max_depth": 4, "eta": 0.05, "lambdarank_num_pair_per_sample": 8,
           "rounds": 178},
    "E5": {"max_depth": 4, "eta": 0.10, "lambdarank_num_pair_per_sample": 16,
           "rounds": 138},
    "E6": {"max_depth": 6, "eta": 0.05, "lambdarank_num_pair_per_sample": 16,
           "rounds": 82},
    "E7": {"max_depth": 6, "eta": 0.05, "lambdarank_num_pair_per_sample": 16,
           "rounds": 107},
    "E8": {"max_depth": 4, "eta": 0.05, "lambdarank_num_pair_per_sample": 8,
           "rounds": 228},
}

GRADE_EDGES = (0.0, 600.0, 1000.0, 2000.0)


def grades(v):
    """The D-021 dollar ladder — fixed, unfitted (`st_lmart.grades`)."""
    g = np.zeros(v.size, dtype=np.int32)
    for e in GRADE_EDGES:
        g += (v >= e).astype(np.int32)
    g[v <= 0] = 0
    return np.clip(g, 0, 4)


_F = {}


def feat_cols(D):
    """The champion's 184 non-`tf_` columns, in matrix order."""
    if "cols" not in _F:
        cols = [i for i, nm in enumerate(D["names"])
                if not str(nm).startswith("tf_")]
        _F["cols"] = cols
        _F["names"] = [str(D["names"][i]) for i in cols]
        h = __import__("hashlib").sha256(
            "\n".join(_F["names"]).encode()).hexdigest()[:32]
        N.hb("features: %d non-tf_ columns, list sha256[:32] = %s "
             "(champion spec pins a52b0ab529312c1424d59f981dc9024b)"
             % (len(cols), h))
        _F["sha"] = h
    return _F["cols"], _F["names"]


def fold(D, era):
    """PRE_E1..E(k-1) -> E(k), whole days, both guards firing."""
    import st_run as R
    tr, ev = R.fold_rows(D, era, from_era="PRE_E1")
    j = D["names"].index("in_news_window")
    tr = tr[D["X"][tr, j] < 0.5]        # the champion vetoes news on TRAIN too
    ev_r = N.deployable(D, ev)          # both vetoes on the seatable pool
    cut = SC.inner_split_days(D["d8"][tr])
    itr, iva = tr[D["d8"][tr] <= cut], tr[D["d8"][tr] > cut]
    SC.assert_disjoint_days(itr, iva, D["d8"], tag="%s inner" % era)
    return tr, itr, iva, ev_r


# ============================================ OBJ-1: THE JOINT (MEMBER x D) ===
def _joint_design(D, rows, delays, V, cols, with_delay):
    """The joint choice set as a design matrix.

    One row per (member, delay) that is FEASIBLE at that delay.  The features
    are the member's own 184 pre-t columns — identical across its delays,
    because nothing new is known at t — plus, when the set has more than one
    delay, the delay itself.  The group is the CELL, exactly as the champion
    groups, so all of a member's delays compete inside the same group as all of
    the other members' delays: that IS the enlarged decision object.
    """
    r = np.asarray(rows, dtype=np.int64)
    reps = len(delays)
    R = np.repeat(r, reps)
    Dl = np.tile(np.asarray(delays, dtype=np.int64), r.size)
    val = np.empty(R.size)
    for k, d in enumerate(delays):
        val[k::reps] = V[int(d)][r]
    keep = np.isfinite(val)
    R, Dl, val = R[keep], Dl[keep], val[keep]
    # group = cell; deterministic order inside it (member second, then delay)
    key = (D["asset_idx"][R].astype(np.int64) * 100000000
           + D["d8"][R].astype(np.int64)) * 100 + D["phase_dec"][R]
    order = np.lexsort((Dl, D["dec_sec"][R], key))
    R, Dl, val, key = R[order], Dl[order], val[order], key[order]
    _u, cnt = np.unique(key, return_counts=True)
    X = D["X"][:, cols][R]
    if with_delay:
        X = np.hstack([X, (Dl.astype(np.float32) / 600.0).reshape(-1, 1)])
    return R, Dl, val, X, cnt


def joint_arm(era, delays, tag, shuffle=False, search=True):
    """Refit the champion's ranker on the joint set and seat what it picks."""
    import xgboost as xgb
    D = N.matrix()
    P = N.load_paths()
    V = {int(d): N.delayed_value(P, d, D) for d in N.DELAYS}
    cols, names = feat_cols(D)
    wd = len(delays) > 1
    fn = list(names) + (["delay_frac"] if wd else [])
    tr, itr, iva, ev_r = fold(D, era)
    t0 = time.time()

    Vfit = V
    if shuffle:
        # THE RED-FIRST CONTROL: the value column is permuted WITHIN the
        # training block, keeping every member's five delayed values together so
        # only the LABEL->CANDIDATE link is destroyed, not the delay structure.
        rs = np.random.RandomState(N.SEED + SC.ERA_IDX[era])
        perm = np.empty(D["d8"].size, dtype=np.int64)
        perm[:] = np.arange(D["d8"].size)
        perm[tr] = tr[rs.permutation(tr.size)]
        Vfit = {int(d): V[int(d)][perm] for d in N.DELAYS}

    _r_i, _d_i, v_i, X_i, g_i = _joint_design(D, itr, delays, Vfit, cols, wd)
    _r_v, _d_v, v_v, X_v, g_v = _joint_design(D, iva, delays, Vfit, cols, wd)
    dtr = xgb.DMatrix(X_i, label=grades(v_i), feature_names=fn)
    dtr.set_group(g_i)
    dva = xgb.DMatrix(X_v, label=grades(v_v), feature_names=fn)
    dva.set_group(g_v)
    cfg, best_rounds, inner = None, ROUNDS, -np.inf
    grid = HP_GRID if search else ({k: CHAMP_HP[era][k] for k in
                                    ("max_depth", "eta",
                                     "lambdarank_num_pair_per_sample")},)
    for hp in grid:
        c = dict(BASE)
        c.update(hp)
        bb = xgb.train(c, dtr, ROUNDS, evals=[(dva, "inner")],
                       early_stopping_rounds=EARLY, verbose_eval=False)
        if float(bb.best_score) > inner:
            cfg, best_rounds, inner = c, int(bb.best_iteration) + 1, \
                float(bb.best_score)
    del dtr, dva, X_i, X_v
    N.hb("%s %s: HP %s rounds=%d inner_ndcg3=%.5f (%.0fs)"
         % (tag, era, {k: cfg.get(k) for k in
                       ("max_depth", "eta", "lambdarank_num_pair_per_sample")},
            best_rounds, inner, time.time() - t0))
    r_t, _d_t, v_t, X_t, g_t = _joint_design(D, tr, delays, Vfit, cols, wd)
    dall = xgb.DMatrix(X_t, label=grades(v_t), feature_names=fn)
    dall.set_group(g_t)
    b2 = xgb.train(cfg, dall, best_rounds)
    del dall, X_t
    r_e, d_e, _v_e, X_e, _g_e = _joint_design(D, ev_r, delays, V, cols, wd)
    s = b2.predict(xgb.DMatrix(X_e, feature_names=fn))
    del X_e
    S = {int(d): np.full(D["d8"].size, np.nan) for d in N.DELAYS}
    for d in delays:
        m = d_e == int(d)
        S[int(d)][r_e[m]] = s[m]
    pol = N.committed_policy()
    _u, n = pol.get(era, ("cell", 1))
    takes = N.top_per_cell_joint(D, ev_r, S, n, tuple(delays))
    rep = N.replay_delayed(D, takes, P)
    a = N._arm_rows(D, era, tag, rep)
    a.update({"inner_ndcg3": inner, "rounds": best_rounds,
              "hp": {k: cfg.get(k) for k in
                     ("max_depth", "eta", "lambdarank_num_pair_per_sample")},
              "fit_secs": round(time.time() - t0, 1),
              "n_joint_train_rows": int(r_t.size),
              "n_joint_eval_rows": int(r_e.size)})
    N.hb("%s %s: $%s/session [%s, %s] seats=%d mix=%s (%.0fs)"
         % (tag, era, N._r(a["usd_per_session"]), N._r(a["ps_lo"]),
            N._r(a["ps_hi"]), a["n_seated"], a["delay_mix"],
            time.time() - t0))
    return a, rep


def joint_arm_screen(D, spec, era, fit_rows, iva, XF, FN, V, P, budget,
                     shuffled):
    """OBJ-1 at the atlas SCREEN budget: the {member x delay} choice set fitted
    on the inner-train days and read on the inner-validation days.

    The design matrix is built by `_joint_design` (the same function the honest
    OBJ-1 arm uses); only the budget and the block differ.
    """
    import xgboost as xgb
    import rank_atlas as RA
    delays = tuple(N.DELAYS)
    cols = list(range(XF.shape[1]))
    Vf = V
    if shuffled:
        rs = np.random.RandomState(N.SEED + 991 + SC.ERA_IDX[era])
        both = np.concatenate([fit_rows, iva])
        perm = np.arange(D["d8"].size)
        perm[both] = both[rs.permutation(both.size)]
        Vf = {int(d): V[int(d)][perm] for d in delays}
    r_f, d_f, v_f, X_f, g_f = _joint_design_X(D, fit_rows, delays, Vf, XF)
    base = {"objective": "rank:ndcg", "eval_metric": "ndcg@3",
            "tree_method": "hist", "min_child_weight": 20, "subsample": 0.8,
            "colsample_bytree": 0.8, "lambdarank_pair_method": "topk",
            "lambdarank_normalization": True, "seed": budget["seed"],
            "nthread": 8, "max_depth": budget["depth"], "eta": budget["eta"]}
    if spec["obj"] == "ndcg1":
        base["eval_metric"] = "ndcg@1"
    elif spec["obj"] == "dpairs":
        base["objective"] = "rank:pairwise"
    elif spec["obj"] == "q75":
        base = {k: v for k, v in base.items()
                if k not in ("objective", "eval_metric",
                             "lambdarank_pair_method",
                             "lambdarank_normalization")}
        base.update({"objective": "reg:quantileerror", "quantile_alpha": 0.75})
    d = xgb.DMatrix(X_f, label=(v_f if spec["obj"] == "q75"
                                else grades(v_f)), feature_names=FN + ["delay_frac"])
    if spec["obj"] != "q75":
        d.set_group(g_f)
    custom = None
    if spec["obj"] == "softmax1":
        base = {k: v for k, v in base.items()
                if k not in ("objective", "eval_metric",
                             "lambdarank_pair_method",
                             "lambdarank_normalization")}
        base["disable_default_eval_metric"] = 1
        custom = RA._softmax_top1_obj(
            v_f, np.concatenate([[0], np.cumsum(g_f.astype(np.int64))]))
    b = xgb.train(base, d, budget["rounds"], obj=custom)
    tr_pred = b.predict(d, output_margin=True)
    ev_r = N.deployable(D, iva)
    r_e, d_e, _v, X_e, g_e = _joint_design_X(D, ev_r, delays, V, XF)
    s = b.predict(xgb.DMatrix(X_e, feature_names=FN + ["delay_frac"]),
                  output_margin=True)
    S = {int(dl): np.full(D["d8"].size, np.nan) for dl in delays}
    for dl in delays:
        m = d_e == int(dl)
        S[int(dl)][r_e[m]] = s[m]
    _u, n_ = N.committed_policy().get(era, ("cell", 1))
    takes = N.top_per_cell_joint(D, ev_r, S, n_, delays)
    a = N.read_rows(D, N.replay_delayed(D, takes, P))
    a["train_p1"] = RA.train_dollar_p1(tr_pred, v_f, g_f)
    a["median_group"] = float(np.median(g_f))
    return a


def _joint_design_X(D, rows, delays, V, XF):
    """`_joint_design` on an ALREADY-BUILT feature matrix (the atlas supplies
    its own feature set), with the delay column appended."""
    r = np.asarray(rows, dtype=np.int64)
    reps = len(delays)
    R = np.repeat(r, reps)
    Dl = np.tile(np.asarray(delays, dtype=np.int64), r.size)
    val = np.empty(R.size)
    for k, d in enumerate(delays):
        val[k::reps] = V[int(d)][r]
    keep = np.isfinite(val)
    R, Dl, val = R[keep], Dl[keep], val[keep]
    key = (D["asset_idx"][R].astype(np.int64) * 100000000
           + D["d8"][R].astype(np.int64)) * 100 + D["phase_dec"][R]
    order = np.lexsort((Dl, D["dec_sec"][R], key))
    R, Dl, val, key = R[order], Dl[order], val[order], key[order]
    _u, cnt = np.unique(key, return_counts=True)
    X = np.hstack([XF[R], (Dl.astype(np.float32) / 600.0).reshape(-1, 1)])
    return R, Dl, val, X, cnt


def stage_obj1(eras=N.ALL_ERAS, search=True):
    D = N.matrix()
    arms = {
        "J_D0": dict(delays=(0,), shuffle=False),
        "J_JOINT": dict(delays=N.DELAYS, shuffle=False),
        "J_JOINT_SHUF": dict(delays=N.DELAYS, shuffle=True),
    }
    out, reps, rows = {}, {}, []
    for name, kw in arms.items():
        for era in eras:
            a, rep = joint_arm(era, kw["delays"], name,
                               shuffle=kw["shuffle"], search=search)
            out.setdefault(name, []).append(a)
            reps.setdefault(name, {})[era] = rep
            rows.append([name, era, a["n_takes"], a["n_seated"],
                         N._r(a["usd_per_session"]), N._r(a["ps_lo"]),
                         N._r(a["ps_hi"]), N._r(a["usd_per_trade"]),
                         N._r(a["frac_ge_1000"], 4),
                         N._r(a["capture_oracle"], 4),
                         a["inner_ndcg3"] and round(a["inner_ndcg3"], 5),
                         json.dumps(a["hp"]), json.dumps(a["delay_mix"])])
    dev_rows = []
    for name, parts in out.items():
        for lbl, sel in (("POOLED_E3-E7", N.DEV_ERAS),
                         ("BLIND_E8", (N.BLIND_ERA,))):
            q = N.pool_reads([a for a in parts if a["era"] in sel])
            if q.get("n_sessions"):
                rows.append([name, lbl, "", q["n_seated"],
                             N._r(q["usd_per_session"]), N._r(q["ps_lo"]),
                             N._r(q["ps_hi"]), N._r(q["usd_per_trade"]),
                             N._r(q["frac_ge_1000"], 4),
                             N._r(q["capture_oracle"], 4), "", "",
                             json.dumps(q["delay_mix"])])
    for era in eras:
        for x, y in (("J_JOINT", "J_D0"), ("J_JOINT_SHUF", "J_D0")):
            if x in reps and y in reps:
                pd = N.paired_sessions(reps[x][era], reps[y][era])
                dev_rows.append([era, x, y, pd.get("n"), N._r(pd.get("delta")),
                                 N._r(pd.get("lo")), N._r(pd.get("hi"))])
    N.write_tsv("NEWOBJ_OBJ1_JOINT.tsv",
                ["arm", "era", "n_takes", "n_seated", "usd_per_session",
                 "ps_lo", "ps_hi", "usd_per_trade", "frac_ge_1000",
                 "capture_oracle", "inner_ndcg3", "hp", "delay_mix"], rows,
                extra=["J_D0 = the champion's ranker refitted on the D=0 choice "
                       "set through THIS file's code path (the matched "
                       "baseline).  J_JOINT = the same ranker on the "
                       "{members} x {0,60,120,300,600s} joint set, a delay "
                       "feature added and the CELL group unchanged.",
                       "J_JOINT_SHUF is the red-first control: values permuted "
                       "within the training block, each member's five delayed "
                       "values kept together."])
    N.write_tsv("NEWOBJ_OBJ1_DELTAS.tsv",
                ["era", "arm", "vs", "n_sessions", "delta_usd_per_session",
                 "lo", "hi"], dev_rows)
    N.save_json("obj1.json",
                {k: [{kk: vv for kk, vv in a.items()
                      if not kk.startswith("_")} for a in v]
                 for k, v in out.items()})
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--obj1", action="store_true")
    ap.add_argument("--eras", default=",".join(N.ALL_ERAS))
    ap.add_argument("--no-search", action="store_true")
    a = ap.parse_args()
    if a.obj1:
        stage_obj1(eras=tuple(e for e in a.eras.split(",") if e),
                   search=not a.no_search)
    else:
        ap.print_help()


# ================================== OBJ-2: RANK-THEN-GATE-VERIFY (a POLICY) ===
GATE_POST = ("f_at_D", "mae_to_D", "mfe_to_D", "walled_by_D") + \
    tuple(__import__("m2_delay").PP_FIELDS)


def gate_block(P, dl):
    """The [t, t+D] post-window block as a design matrix — the DELAY census's
    own `pp_*` fields plus the four path markers.  §3 of DELAY_DECIDABILITY
    measured that the post-window ORDER-FLOW cues carry nothing over this
    price-path block, which is why the block is the whole gate input."""
    cols = [N.FIDX[f] for f in GATE_POST]
    return P[int(dl)][:, cols], list(GATE_POST)


def fit_gate(D, P, dl, itr, iva, tr, ev, XF, FN, V, full=True, shuffle=False):
    """P(this delayed seat pays) from the post-window tape, fitted walk-forward.

    Target = the DELAYED certificate at D, so the gate is trained on the value
    of the act it is actually verifying.  `full=True` reproduces the DELAY
    census's own gate shape (pre-t features + the [t, t+D] block); `full=False`
    is the post-window block alone.
    """
    import xgboost as xgb
    G, GN = gate_block(P, dl)
    if full:
        Xg = np.hstack([XF, G.astype(np.float32)])
        Ng = list(FN) + GN
    else:
        Xg, Ng = G.astype(np.float32), list(GN)
    y = V[int(dl)]
    cfg = {"objective": "reg:squarederror", "tree_method": "hist",
           "max_depth": 5, "eta": 0.06, "min_child_weight": 20,
           "subsample": 0.8, "colsample_bytree": 0.7, "seed": N.SEED,
           "nthread": 8}

    def _fit(rows, va, rounds=None):
        r = rows[np.isfinite(y[rows])]
        yy = y
        if shuffle:
            rs = np.random.RandomState(N.SEED + 313)
            yy = y.copy()
            yy[r] = yy[r][rs.permutation(r.size)]
        d = xgb.DMatrix(Xg[r], label=yy[r], feature_names=Ng)
        if va is None:
            return xgb.train(cfg, d, rounds or 200), rounds or 200
        v = va[np.isfinite(y[va])]
        dv = xgb.DMatrix(Xg[v], label=yy[v], feature_names=Ng)
        b = xgb.train(cfg, d, 300, evals=[(dv, "inner")],
                      early_stopping_rounds=25, verbose_eval=False)
        return b, int(b.best_iteration) + 1

    b_in, rounds = _fit(itr, iva)
    g_iva = np.full(D["d8"].size, np.nan)
    g_iva[iva] = b_in.predict(xgb.DMatrix(Xg[iva], feature_names=Ng))
    b_out, _ = _fit(tr, None, rounds=rounds)
    g_ev = np.full(D["d8"].size, np.nan)
    g_ev[ev] = b_out.predict(xgb.DMatrix(Xg[ev], feature_names=Ng))
    return g_iva, g_ev, rounds


def top2_by_score(D, rows, s):
    return N._top2_by_score(D, rows, s)


def gate_takes(top2, gate, tau, dl, V):
    """THE TWO-STAGE ACT: the ranker nominates, the post-window tape verifies,
    a failed verification falls through to member #2, and a second failure means
    NO SEAT."""
    out = []
    n1 = n2 = n0 = 0
    for m1, m2 in top2:
        got = None
        for m, which in ((m1, 1), (m2, 2)):
            if m is None:
                continue
            if np.isfinite(gate[m]) and gate[m] >= tau \
                    and np.isfinite(V[int(dl)][m]):
                got = (m, which)
                break
        if got is None:
            n0 += 1
            continue
        out.append((got[0], int(dl)))
        if got[1] == 1:
            n1 += 1
        else:
            n2 += 1
    return out, {"pass_1": n1, "fall_to_2": n2, "no_seat": n0}


# ==================================== OBJ-3: OPTIMAL STOPPING (a POLICY) =====
STOP_DT = 30.0            # backward-induction step, seconds
STOP_BINS = 20            # score->dollars calibration bins


def fit_stopping(D, P, rows, score, val):
    """BACKWARD INDUCTION ON THE HISTORICAL ARRIVAL PROCESS.

    A cell's members ARRIVE in time order.  `top-1 per cell` needs the whole
    cell in hand before it can pick; a stopping rule decides at each arrival
    with only the past.  Fitted on the training block:

      u(q)   the calibration score-percentile -> realised dollars
      p_b    P(at least one arrival in the next `STOP_DT` seconds | remaining
             time in bucket b), from the training cells' own arrivals
      W(b)   W(0) = 0;  W(b) = (1-p_b) W(b-1) + p_b E_q[max(u(q), W(b-1))]

    and the rule is TAKE iff `u(q) >= W(b-1)` — the continuation value of the
    time that is left.  Everything is estimated on `rows`; nothing here sees an
    evaluation era.
    """
    r = np.asarray(rows, dtype=np.int64)
    s = score[r]
    ok = np.isfinite(s)
    r, s = r[ok], s[ok]
    v = val[r]
    cdf = np.sort(s)
    q = np.searchsorted(cdf, s, side="right") / max(cdf.size, 1)
    edges = np.linspace(0.0, 1.0, STOP_BINS + 1)
    ib = np.clip(np.digitize(q, edges[1:-1]), 0, STOP_BINS - 1)
    u_tab = np.array([np.mean(v[ib == k]) if np.any(ib == k) else 0.0
                      for k in range(STOP_BINS)])
    rem = P[0][r, N.FIDX["pc_sec"]] - D["dec_sec"][r].astype(np.float64)
    rem = np.clip(rem, 0.0, None)
    nb = int(np.ceil(np.nanpercentile(rem, 99.5) / STOP_DT)) + 1
    cell = ((D["asset_idx"][r].astype(np.int64) * 100000000
             + D["d8"][r].astype(np.int64)) * 100 + D["phase_dec"][r])
    # p_b: over all (cell, bucket) pairs the cell's window covers
    bidx = np.clip((rem / STOP_DT).astype(np.int64), 0, nb - 1)
    hit = np.zeros(nb)
    tot = np.zeros(nb)
    order = np.argsort(cell, kind="stable")
    co = cell[order]
    starts = [0] + (np.flatnonzero(co[1:] != co[:-1]) + 1).tolist()
    for a, b in zip(starts, starts[1:] + [co.size]):
        ix = order[a:b]
        bb = bidx[ix]
        hi = int(bb.max())
        tot[:hi + 1] += 1
        hit[np.unique(bb)] += 1
    p_b = np.where(tot > 0, hit / np.maximum(tot, 1), 0.0)
    u_sample = u_tab[ib]
    W = np.zeros(nb)
    for b in range(1, nb):
        cont = W[b - 1]
        W[b] = (1 - p_b[b]) * cont + p_b[b] * float(
            np.mean(np.maximum(u_sample, cont)))
    return {"cdf": cdf, "edges": edges, "u_tab": u_tab, "W": W, "nb": nb,
            "p_b": p_b}


def stopping_takes(D, P, rows, score, fit, n_per_cell=1, oracle_val=None):
    """Apply the fitted stopping rule forward: inside each cell take the first
    arrival whose value beats the continuation value of the time remaining."""
    ro, blocks = N.cell_blocks(D, rows)
    s = np.asarray(score)[ro]
    cdf, edges, u_tab, W, nb = (fit["cdf"], fit["edges"], fit["u_tab"],
                                fit["W"], fit["nb"])
    rem = (P[0][ro, N.FIDX["pc_sec"]]
           - D["dec_sec"][ro].astype(np.float64))
    bidx = np.clip((np.clip(rem, 0, None) / STOP_DT).astype(np.int64), 0, nb - 1)
    q = np.searchsorted(cdf, s, side="right") / max(cdf.size, 1)
    ib = np.clip(np.digitize(q, edges[1:-1]), 0, STOP_BINS - 1)
    u = u_tab[ib] if oracle_val is None else np.asarray(oracle_val)[ro]
    out, n_take, n_pass = [], 0, 0
    for a, b in blocks:
        taken = 0
        for j in range(a, b):
            if not np.isfinite(s[j]):
                continue
            thr = W[max(bidx[j] - 1, 0)]
            if u[j] >= thr:
                out.append((int(ro[j]), 0))
                taken += 1
                n_take += 1
                if taken >= n_per_cell:
                    break
            else:
                n_pass += 1
    return out, {"n_take": n_take, "n_declined": n_pass}


def joint_confirm(D, spec, era, ifit, iva, fit_rows, ev_r, XF, FN, V, P):
    """OBJ-1 at CONFIRM budget: the {member x delay} ranker with the champion's
    inner-block HP discipline, seated through `replay_delayed`."""
    import xgboost as xgb
    import rank_atlas as RA
    delays = tuple(N.DELAYS)
    fn = list(FN) + ["delay_frac"]
    r_i, d_i, v_i, X_i, g_i = _joint_design_X(D, ifit, delays, V, XF)
    r_v, d_v, v_v, X_v, g_v = _joint_design_X(D, iva, delays, V, XF)
    dtr = xgb.DMatrix(X_i, label=grades(v_i), feature_names=fn)
    dtr.set_group(g_i)
    dva = xgb.DMatrix(X_v, label=grades(v_v), feature_names=fn)
    dva.set_group(g_v)
    cfg, best_rounds, inner = None, ROUNDS, -np.inf
    for hp in HP_GRID:
        c = dict(BASE)
        c.update(hp)
        if spec["obj"] == "ndcg1":
            c["eval_metric"] = "ndcg@1"
        elif spec["obj"] == "dpairs":
            c["objective"] = "rank:pairwise"
        bb = xgb.train(c, dtr, ROUNDS, evals=[(dva, "inner")],
                       early_stopping_rounds=EARLY, verbose_eval=False)
        if float(bb.best_score) > inner:
            cfg, best_rounds, inner = c, int(bb.best_iteration) + 1, \
                float(bb.best_score)
    del dtr, dva, X_i, X_v
    r_t, d_t, v_t, X_t, g_t = _joint_design_X(D, fit_rows, delays, V, XF)
    dall = xgb.DMatrix(X_t, label=grades(v_t), feature_names=fn)
    dall.set_group(g_t)
    b2 = xgb.train(cfg, dall, best_rounds)
    del dall, X_t
    r_e, d_e, _v, X_e, _g = _joint_design_X(D, ev_r, delays, V, XF)
    s = b2.predict(xgb.DMatrix(X_e, feature_names=fn), output_margin=True)
    S = {int(dl): np.full(D["d8"].size, np.nan) for dl in delays}
    for dl in delays:
        m = d_e == int(dl)
        S[int(dl)][r_e[m]] = s[m]
    _u, n_ = N.committed_policy().get(era, ("cell", 1))
    takes = N.top_per_cell_joint(D, ev_r, S, n_, delays)
    a = N.read_rows(D, N.replay_delayed(D, takes, P))
    # the joint arm's "score column" for downstream policies is its D=0 slice
    return a, S[0], {"hp": {k: cfg.get(k) for k in
                            ("max_depth", "eta",
                             "lambdarank_num_pair_per_sample")},
                     "inner_ndcg": inner, "rounds": best_rounds,
                     "n_joint_rows": int(r_t.size),
                     "delay_mix": a["delay_mix"]}
