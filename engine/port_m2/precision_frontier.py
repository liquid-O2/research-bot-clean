#!/usr/bin/python3
"""PORT M2 — THE PRECISION FRONTIER (the measurement lane's closing instrument).

THE QUESTION, IN ONE LINE
  At the ORIGINAL full-value entries, what precision and what dollars does the
  model actually deliver at each level of confidence — and at what throughput?

Every prior number in this programme was reported at ONE operating point (a
top-N policy, a chosen tier, a single take-rate).  This module reports the
CURVE: precision, $/trade, $/day, $/week and $/traded-day as a function of
  (a) the score threshold,        the confidence tier
  (b) the day-abstention gate,    trade only on days the model likes
  (c) cross-score agreement,      2-of-3 / 3-of-3 between independent readers
and it reports them per era with day-clustered intervals, beside the D-021 /
D-048 bars and beside the user's WEEKLY THROUGHPUT FLOOR (3-4 portfolio takes
per week; 5 and 8 carried for shape).

WHERE EVERY NUMBER COMES FROM (D-006 — no second definition of anything)
  features/outcomes   the committed M3 matrix, WITH the D-078 teacher-evidence
                      group (m3_matrix.py, 202 columns, its own holdout and
                      forward-feature guards already fired)
  the fit             m3_walk.fit_one — the S4 pinned-HP discipline, the same
                      inner-split rule, the same seed
  the replay          m3_walk.replay_rows — one position per asset-session,
                      chronological, walled phase-close certificate, forfeits
                      counted, refusals refused
  the ceilings        m3_walk.dp_ceilings / m3_walk.oracle_ceiling
  the sequence cues   seq_cues.cues_from_window, tape from the certified event
                      cache — the identical arithmetic the E6R2 cue census ran
  intervals           panel_score.cluster_mean / cluster_ratio, CLUSTERED BY
                      CALENDAR DAY (the draw unit, D-036/D-073)

THE LADDER IS THE WALK-FORWARD LADDER.  Model_k is fitted only on eras strictly
before era k and scored on era k, exactly as m3_walk does it, so every number
below is out-of-sample by construction.  The reported eras are E3..E6 and E8
(= the GATE-2025H1 echo); E1/E2 are ladder warm-up and are not reported.

THE FOUR SCORES (all walk-forward, all on the D-021 walled-winner head)
  FULL_TF      every matrix column INCLUDING teacher_evidence — "the best model"
  FULL_NOTF    the same harness with the teacher group dropped (the D-078 control)
  TEACHER      the 18 teacher-evidence columns ALONE
  SEQ          the raw-event-stream cue block ALONE (seq_cues, 120s window)
  SHUFFLE      FULL_TF's own scores, permuted within era — THE RED-FIRST
               RECEIPT: a permuted score's frontier must be FLAT.

CLI
  precision_frontier.py --seq       [--workers 8]   the corpus-wide cue census
  precision_frontier.py --scores    [--nthread 8]   the walk-forward score ladder
  precision_frontier.py --daymodel  [--nthread 8]   the oracle-free pre-day gate
  precision_frontier.py --frontier                  every table + the report
"""
import argparse
import datetime as _dt
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, "/workspace/engine/port_m0", "/workspace/engine/port_m1",
           "/workspace/engine/port_m1b", "/workspace/engine/port_m3",
           "/workspace/artifacts/cache/pylibs"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import m2_common as MC                    # noqa: E402
import assemble as A                      # noqa: E402
import tape as TAPE                       # noqa: E402
import seq_cues as SQ                     # noqa: E402
import panel_score as PS                  # noqa: E402

SECTION = "THE PRECISION FRONTIER (threshold x day-abstention x agreement)"
VERSION = "PORT-M2-PRECISION-FRONTIER-V1"
OUT_ROOT = os.path.join(MC.M2_ROOT, "frontier")
PROV = "/workspace/provenance/port_m2"
MATRIX_NPZ = "/workspace/artifacts/cache/port/m3/matrix/matrix.npz"

SEED = 20260813
SEQ_WINDOW_SEC = 120                     # the round-2 reader window (R2-1)
ERAS_REPORTED = ("E3", "E4", "E5", "E6", "E8")
# The ladder is fitted one era wider than it is reported: E2 and E7 exist so
# that EVERY reported era has a PREVIOUS era's score distribution to calibrate
# a strictly-causal threshold from (see THRESHOLD_CALIBRATION below).
ERAS_FIT = ("E2", "E3", "E4", "E5", "E6", "E7", "E8")
ERA_LABEL = {"E8": "E8_GATE_2025H1"}

# THE CONFIDENCE TIERS: the top X% of the era's own deployable candidate
# scores.  100% is the no-threshold reference row.
#
# WHY THE GRID GOES DOWN TO 0.02%.  The user's throughput floor is 3-4 takes
# per WEEK across the whole portfolio.  An era carries ~150,000 deployable
# candidates over ~26 weeks, so 4 takes/week is ~104 takes = 0.07% of the
# population: every tier at or above 0.5% is an order of magnitude ABOVE the
# floor and none of them can answer the question that was asked.  The tight end
# of this grid is where the user's operating region actually lives.
TIERS_PCT = (0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 100.0)

# THE THRESHOLD-CALIBRATION CAVEAT, declared because it is a real one: a
# percentile of the EVAL era's own score distribution is not knowable in
# advance.  Every headline tier is therefore accompanied by a strictly-causal
# arm in which the SCORE CUT is the same percentile taken on the PREVIOUS
# era's out-of-sample scores and then applied unchanged to this era.

# THE USER'S THROUGHPUT FLOOR, binding on the verdict: portfolio takes per
# WEEK, summed across all three assets.  3-4/week is the floor; 5 and 8 are
# carried for the shape of the curve.
WEEK_FLOORS = (3.0, 4.0, 5.0, 8.0)

# D-021 / D-048 bars, imported rather than re-typed.
import m3_common as M3                    # noqa: E402
import m3_walk as MW                      # noqa: E402
import m3_matrix as MX                    # noqa: E402
import xgboost as xgb                     # noqa: E402


def hb(msg):
    sys.stderr.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), msg))
    sys.stderr.flush()


def _iso_week(d8):
    d = MC.d8_to_date(int(d8))
    y, w, _ = d.isocalendar()
    return "%04d-W%02d" % (y, w)


# ======================================================= STAGE 1: SEQ CUES ===
SEQ_FIELDS = ("n_ev", "ev_per_s", "trade_frac", "med_gap_ms", "n_trades",
              "l1_ct_asym", "stack_asym", "ask_reload", "bid_reload",
              "hit_ask", "hit_bid", "cancel_retreat_up", "trade_retreat_up",
              "cancel_retreat_dn", "trade_retreat_dn", "pull_ratio_up",
              "pull_ratio_dn", "one_side_pull", "add_walk_up", "add_walk_dn")


def _seq_one(job):
    """Every DISTINCT decision second of one (asset, date8): tape opened ONCE."""
    asset, d8, decs = job
    try:
        sess = A.load_session(asset, int(d8))
        s = sess["s"]
        open_utc = int(s.meta["open_utc"])
        close_utc = int(s.meta["close_utc"])
        ranges = [(max(0, int(d) - SEQ_WINDOW_SEC - 2), int(d) + 1)
                  for d in decs]
        arrays, _m = TAPE.ensure(asset, sess["trade_date"], int(s.iid),
                                 open_utc, close_utc, TAPE._merge(ranges))
        out = np.full((len(decs), len(SEQ_FIELDS)), np.nan, dtype=np.float32)
        for i, d in enumerate(decs):
            lo = max(0, int(d) - SEQ_WINDOW_SEC)
            w, _a, _b = TAPE.window(arrays, open_utc, lo, int(d) + 1)
            c = SQ.cues_from_window(w)
            for j, f in enumerate(SEQ_FIELDS):
                out[i, j] = c[f]
        return (asset, int(d8), decs, out, None)
    except Exception as exc:               # noqa: BLE001 — surfaced, not hidden
        return (asset, int(d8), decs, None, "%s: %s" % (type(exc).__name__, exc))


def build_seq(workers=8):
    """The seq-cue block for EVERY candidate row of the matrix, in row order."""
    os.makedirs(OUT_ROOT, exist_ok=True)
    z = np.load(MATRIX_NPZ, allow_pickle=False)
    d8 = z["d8"]
    dec = z["dec_sec"]
    ai = z["asset_idx"]
    z.close()
    asset = np.array([M3.ASSET_ORDER[i] for i in ai.tolist()])
    key = np.array(["%s|%08d" % (a, d) for a, d in
                    zip(asset.tolist(), d8.tolist())])
    jobs = {}
    for a, d, s in zip(asset.tolist(), d8.tolist(), dec.tolist()):
        jobs.setdefault((a, int(d)), set()).add(int(s))
    joblist = [(a, d, sorted(v)) for (a, d), v in sorted(jobs.items())]
    hb("seq: %d sessions, %d rows, window=%ds" % (len(joblist), dec.size,
                                                  SEQ_WINDOW_SEC))
    lut = {}
    errs = []
    t0 = time.time()
    with mp.Pool(processes=int(workers)) as pool:
        for k, (a, d, decs, arr, err) in enumerate(
                pool.imap_unordered(_seq_one, joblist, chunksize=1), start=1):
            if err:
                errs.append("%s %d %s" % (a, d, err))
                continue
            for i, s in enumerate(decs):
                lut[(a, int(d), int(s))] = arr[i]
            if k % 100 == 0 or k == len(joblist):
                el = time.time() - t0
                hb("seq %d/%d %.0fs eta %.0fs errs=%d"
                   % (k, len(joblist), el, el / k * (len(joblist) - k),
                      len(errs)))
    S = np.full((dec.size, len(SEQ_FIELDS)), np.nan, dtype=np.float32)
    for i, (a, d, s) in enumerate(zip(asset.tolist(), d8.tolist(),
                                      dec.tolist())):
        v = lut.get((a, int(d), int(s)))
        if v is not None:
            S[i] = v
    np.savez(os.path.join(OUT_ROOT, "seq.npz"), S=S,
             cols=np.array(SEQ_FIELDS), d8=d8, dec_sec=dec, asset_idx=ai)
    rec = {"version": VERSION, "window_sec": SEQ_WINDOW_SEC,
           "n_rows": int(dec.size), "n_sessions": len(joblist),
           "n_covered": int(np.isfinite(S[:, 0]).sum()),
           "n_errors": len(errs), "errors": errs[:40],
           "secs": round(time.time() - t0, 1)}
    with open(os.path.join(OUT_ROOT, "seq.receipt.json"), "w") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True)
    hb("seq: %d/%d rows covered, %d errors, %.0fs"
       % (rec["n_covered"], rec["n_rows"], len(errs), rec["secs"]))
    return S


def seq_columns(D):
    """The SEQ arm's feature block: the raw cues + the side-signed readings the
    E6R2 census itself scored (`reload_with_side`, `pull_with_side`, the L1 and
    stack count asymmetries ahead of the trade)."""
    p = os.path.join(OUT_ROOT, "seq.npz")
    if not os.path.exists(p):
        raise SystemExit("seq.npz missing — run --seq first")
    Z = np.load(p, allow_pickle=False)
    if not (np.array_equal(Z["d8"], D["d8"])
            and np.array_equal(Z["dec_sec"], D["dec_sec"])):
        raise SystemExit("seq.npz row order differs from the matrix")
    S = Z["S"].astype(np.float32)
    cols = [str(c) for c in Z["cols"].tolist()]
    Z.close()
    side = D["side"].astype(np.float32)
    g = {c: S[:, i] for i, c in enumerate(cols)}
    extra = {
        "reload_with_side": (g["ask_reload"] - g["bid_reload"]) * side,
        "pull_with_side": g["one_side_pull"] * side,
        "l1_ct_asym_with_side": g["l1_ct_asym"] * side,
        "stack_asym_with_side": g["stack_asym"] * side,
        "add_walk_with_side": (g["add_walk_up"] - g["add_walk_dn"]) * side,
        "hit_with_side": (g["hit_ask"] - g["hit_bid"]) * side,
        "retreat_with_side": (g["cancel_retreat_up"] - g["cancel_retreat_dn"])
        * side,
        "seq_side": side,
    }
    names = cols + sorted(extra)
    X = np.column_stack([S] + [extra[k] for k in sorted(extra)])
    return X.astype(np.float32), names


# ================================================== STAGE 2: THE SCORE LADDER
ARMS = ("FULL_TF", "FULL_NOTF", "TEACHER", "SEQ")
HEAD = "y_winner"                        # precision is a WINNER-RATE estimand
HEAD2 = "y_retg_rank_phase"              # the atlas champion, for the composed


def load_D(with_seq=True):
    D, _p = MW.load_matrix()
    if with_seq:
        Xs, ns = seq_columns(D)
        D["Xseq"] = Xs
        D["seq_names"] = ns
    D["group"] = np.array([str(x) for x in D["feature_groups"].tolist()])
    D["is_tf"] = D["group"] == "teacher_evidence"
    return D


def deployable(D, idx):
    """The D-077-UPDATE reading, m3_walk's own veto, applied verbatim."""
    i = np.asarray(idx, dtype=np.int64)
    j = D["names"].index("in_news_window")
    i = i[D["X"][i, j] < 0.5]
    k = D["names"].index("nd_held_into_window")
    held = D["X"][i, k]
    return i[~(held > 0.5)]


def arm_matrix(D, arm):
    if arm == "FULL_TF":
        return D["X"], list(D["names"])
    if arm == "FULL_NOTF":
        m = ~D["is_tf"]
        return np.ascontiguousarray(D["X"][:, m]), [n for n, k in
                                                    zip(D["names"], m.tolist())
                                                    if k]
    if arm == "TEACHER":
        m = D["is_tf"]
        return np.ascontiguousarray(D["X"][:, m]), [n for n, k in
                                                    zip(D["names"], m.tolist())
                                                    if k]
    if arm == "SEQ":
        return D["Xseq"], list(D["seq_names"])
    raise SystemExit("unknown arm %s" % arm)


def fit_score(D, X, names, k, target, nthread):
    """m3_walk's own fit, on era k of the expanding ladder."""
    tr = np.nonzero((D["era_idx"] >= 0) & (D["era_idx"] < k))[0]
    ev = np.nonzero(D["era_idx"] == k)[0]
    y = D[target]
    fin = tr[np.isfinite(y[tr])]
    if fin.size < 5000 or ev.size == 0:
        return None, None
    cut = MW.inner_split(D["d8"][fin])
    if cut is None:
        itr = iva = fin
    else:
        itr = fin[D["d8"][fin] <= cut]
        iva = fin[D["d8"][fin] > cut]
    if itr.size < 500 or iva.size < 100:
        itr = iva = fin
    sel = MW.fit_one(X, y, itr, iva, nthread, feature_names=names)
    if sel is None:
        return None, None
    b = xgb.train(sel["cfg"], xgb.DMatrix(X[fin], label=y[fin],
                                          feature_names=names), sel["rounds"])
    s = np.full(D["d8"].size, np.nan)
    s[ev] = b.predict(xgb.DMatrix(X[ev], feature_names=names))
    return s, {"rounds": sel["rounds"], "inner_rho": sel["inner_rho"],
               "n_train": int(fin.size), "n_features": len(names),
               "hp": {kk: vv for kk, vv in sel["cfg"].items()
                      if kk in ("max_depth", "eta", "min_child_weight",
                                "colsample_bytree")}}


def build_scores(nthread=8):
    os.makedirs(OUT_ROOT, exist_ok=True)
    D = load_D()
    out, meta = {}, {}
    t0 = time.time()
    for k, era in enumerate(M3.ERA_NAMES):
        if era not in ERAS_FIT:
            continue
        for arm in ARMS:
            X, names = arm_matrix(D, arm)
            s, m = fit_score(D, X, names, k, HEAD, nthread)
            if s is None:
                hb("scores %s %s NO_MODEL" % (era, arm))
                continue
            out["%s|%s" % (era, arm)] = s.astype(np.float32)
            meta["%s|%s" % (era, arm)] = m
            hb("scores %s %-10s rho=%.4f rounds=%d nfeat=%d (%.0fs)"
               % (era, arm, m["inner_rho"], m["rounds"], m["n_features"],
                  time.time() - t0))
        # the atlas-champion head of the best arm, for the COMPOSED reading
        X, names = arm_matrix(D, "FULL_TF")
        s2, m2 = fit_score(D, X, names, k, HEAD2, nthread)
        if s2 is not None:
            out["%s|FULL_TF_RETG" % era] = s2.astype(np.float32)
            meta["%s|FULL_TF_RETG" % era] = m2
            hb("scores %s FULL_TF_RETG rho=%.4f (%.0fs)"
               % (era, m2["inner_rho"], time.time() - t0))
    np.savez(os.path.join(OUT_ROOT, "scores.npz"), **out)
    rec = {"version": VERSION, "head": HEAD, "head2": HEAD2,
           "arms": list(ARMS), "eras": list(ERAS_FIT),
           "eras_reported": list(ERAS_REPORTED), "meta": meta,
           "hp_discipline": "m3_walk.fit_one (s4_confirm.HP_GRID, inner split "
                            "= the training block's last 20%% of sessions)",
           "secs": round(time.time() - t0, 1)}
    with open(os.path.join(OUT_ROOT, "scores.receipt.json"), "w") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True)
    hb("scores: %d cells in %.0fs" % (len(out), time.time() - t0))
    return out


# ============================================ STAGE 3: THE ORACLE-FREE DAY ===
PREDAY_COLS = ("fc_available", "fc_p_expansion", "fc_range_hat_usd",
               "fc_range_hat_q10", "fc_range_hat_q90", "fc_range_vs_trailing",
               "fc_share_TOKYO", "fc_share_LONDON", "fc_share_NY",
               "fc_menu_hat", "fc_bench_base_rate", "fc_bench_persistence",
               "fc_bench_range_trailmed", "pre_cell_range_usd", "atr_usd",
               "range_hat_usd", "regime_tercile", "spread_ratio", "dow",
               "is_monday", "is_friday", "asset_SI", "asset_HG", "asset_NKD",
               "prev_phase_range_usd", "rv1800_usd", "rv60_usd")


def preday_frame(D):
    """One row per (asset, session): the state as of the day's FIRST candidate.

    Everything here is knowable at that first decision second — the forecaster
    anchor the row itself read, the overnight window that preceded the first
    cell, the prior-session ATR and the trailing-median benchmarks.  It is a
    PRE-DAY gate in the only sense that survives a causality audit: it uses no
    score of any candidate and nothing from after the day's first candidate.
    """
    names = D["names"]
    ix = [names.index(c) for c in PREDAY_COLS]
    sess = D["session"]
    order = np.lexsort((D["dec_sec"], sess))
    so = sess[order]
    starts = [0] + (np.flatnonzero(so[1:] != so[:-1]) + 1).tolist()
    first = order[np.array(starts, dtype=np.int64)]
    return first, D["X"][np.ix_(first, ix)].astype(np.float32), list(PREDAY_COLS)


def build_daymodel(nthread=8):
    """A walk-forward day-value model: predict the asset-day's realised dollars
    under the reference policy from pre-day state alone."""
    os.makedirs(OUT_ROOT, exist_ok=True)
    D = load_D(with_seq=False)
    first, Xd, cols = preday_frame(D)
    sess = D["session"][first]
    d8 = D["d8"][first]
    era = D["era_idx"][first]
    # the reference target: the day's realised dollars under a fixed,
    # score-free schedule — the one-position DP over the day's EARLIEST
    # episode members (BASE_EARLIEST), the frozen mechanical arm.
    base = MW.baseline_takes(D, np.arange(D["d8"].size), deployable=True)
    rows = MW.replay_rows(D, base)
    got = {r["session"]: r["realised"] for r in rows}
    y = np.array([got.get(str(s), 0.0) for s in sess.tolist()])
    out, meta = {}, {}
    for k, name in enumerate(M3.ERA_NAMES):
        if name not in ERAS_REPORTED:
            continue
        tr = np.nonzero((era >= 0) & (era < k))[0]
        ev = np.nonzero(era == k)[0]
        cut = MW.inner_split(d8[tr])
        itr = tr[d8[tr] <= cut]
        iva = tr[d8[tr] > cut]
        if itr.size < 100 or iva.size < 30:
            itr = iva = tr
        sel = MW.fit_one(Xd, y, itr, iva, nthread, feature_names=cols)
        if sel is None:
            continue
        b = xgb.train(sel["cfg"], xgb.DMatrix(Xd[tr], label=y[tr],
                                              feature_names=cols),
                      sel["rounds"])
        s = np.full(sess.size, np.nan)
        s[ev] = b.predict(xgb.DMatrix(Xd[ev], feature_names=cols))
        out[name] = s.astype(np.float32)
        meta[name] = {"inner_rho": sel["inner_rho"], "rounds": sel["rounds"],
                      "n_train_days": int(tr.size), "n_eval_days": int(ev.size)}
        hb("daymodel %s rho=%.4f n_eval=%d" % (name, sel["inner_rho"], ev.size))
    np.savez(os.path.join(OUT_ROOT, "dayscore.npz"),
             session=sess, d8=d8, era=era, y=y,
             **{("s_" + k): v for k, v in out.items()})
    with open(os.path.join(OUT_ROOT, "dayscore.receipt.json"), "w") as fh:
        json.dump({"version": VERSION, "cols": list(cols), "meta": meta,
                   "target": "the asset-day's realised $ under BASE_EARLIEST "
                             "(a score-free mechanical schedule)"},
                  fh, indent=1, sort_keys=True)
    return out


# ================================================== STAGE 4: THE FRONTIER ====
def replay_metrics(D, idx, ctx, label):
    """Replay `idx` and read every number the frontier reports off ONE replay."""
    era_days, era_weeks, n_sess_era = ctx
    take = np.sort(np.asarray(idx, dtype=np.int64))
    rows = MW.replay_rows(D, take)
    seats = np.array([j for r in rows for j in r["seats"]], dtype=np.int64)
    n_days = len(era_days)
    n_weeks = len(era_weeks)
    out = {"tier": label, "n_candidates": int(take.size),
           "n_seated": int(seats.size),
           "n_forfeited": int(sum(r["n_forfeited"] for r in rows)),
           "n_sessions_traded": int(sum(1 for r in rows if r["n_seated"])),
           "n_days_traded": 0, "n_days": n_days, "n_weeks": n_weeks}
    if seats.size == 0:
        out.update({"precision": float("nan"), "usd_per_trade": float("nan"),
                    "usd_per_day": 0.0, "usd_per_traded_day": float("nan"),
                    "usd_per_week": 0.0, "takes_per_day": 0.0,
                    "takes_per_week": 0.0, "frac_days_traded": 0.0,
                    "usd_total": 0.0, "usd_per_session_all": 0.0,
                    "usd_per_session_traded": float("nan"),
                    "usd_week_p10": 0.0, "usd_week_median": 0.0,
                    "frac_losing_weeks": 0.0, "mean_mae_usd": float("nan"),
                    "walled_rate": float("nan"), "frac_ge_600": float("nan")})
        return out, {}
    cert = D["cert_close_usd"][seats]
    win = np.nan_to_num(D["y_winner"][seats], nan=0.0)
    mae = D["mae_before_argmax"][seats]
    day = np.array([int(x) for x in D["d8"][seats].tolist()])
    # per-calendar-day dollars over EVERY day of the era (a day with no take
    # contributes a real zero — abstention is not a missing value)
    by_day = {int(d): 0.0 for d in era_days}
    by_day_n = {int(d): 0 for d in era_days}
    for d, v in zip(day.tolist(), cert.tolist()):
        by_day[d] = by_day.get(d, 0.0) + float(v)
        by_day_n[d] = by_day_n.get(d, 0) + 1
    dv = np.array([by_day[int(d)] for d in era_days])
    dn = np.array([by_day_n[int(d)] for d in era_days])
    by_week = {}
    for d, v, n in zip(era_days, dv.tolist(), dn.tolist()):
        w = _iso_week(d)
        e = by_week.setdefault(w, [0.0, 0])
        e[0] += v
        e[1] += n
    wk = sorted(by_week)
    wv = np.array([by_week[w][0] for w in wk])
    wn = np.array([by_week[w][1] for w in wk])
    cl_day = [str(d) for d in day.tolist()]
    prec = PS.cluster_mean(win, cl_day)
    per_tr = PS.cluster_mean(cert, cl_day)
    per_day = PS.cluster_mean(dv, [str(d) for d in era_days])
    traded = dn > 0
    per_td = (PS.cluster_mean(dv[traded], [str(d) for d, t in
                                           zip(era_days, traded.tolist()) if t])
              if traded.any() else None)
    per_wk = PS.cluster_mean(wv, wk)
    out.update({
        "n_days_traded": int(traded.sum()),
        "precision": float(win.mean()),
        "precision_lo": (prec or {}).get("ci_lo"),
        "precision_hi": (prec or {}).get("ci_hi"),
        "usd_per_trade": float(cert.mean()),
        "usd_per_trade_lo": (per_tr or {}).get("ci_lo"),
        "usd_per_trade_hi": (per_tr or {}).get("ci_hi"),
        "usd_per_day": float(dv.mean()),
        "usd_per_day_lo": (per_day or {}).get("ci_lo"),
        "usd_per_day_hi": (per_day or {}).get("ci_hi"),
        "usd_per_traded_day": (float(dv[traded].mean()) if traded.any()
                               else float("nan")),
        "usd_per_traded_day_lo": (per_td or {}).get("ci_lo"),
        "usd_per_week": float(wv.mean()),
        "usd_per_week_lo": (per_wk or {}).get("ci_lo"),
        "usd_per_week_hi": (per_wk or {}).get("ci_hi"),
        "usd_week_p10": float(np.percentile(wv, 10)),
        "usd_week_median": float(np.median(wv)),
        "frac_losing_weeks": float((wv < 0).mean()),
        "takes_per_day": float(dn.mean()),
        "takes_per_week": float(wn.mean()),
        "frac_days_traded": float(traded.mean()),
        "usd_total": float(cert.sum()),
        "mean_mae_usd": float(np.nanmean(mae)),
        "walled_rate": float(np.nanmean(D["walled"][seats] > 0)),
        "frac_ge_600": float((cert >= 600.0).mean()),
        "usd_per_session_traded": float(cert.sum()
                                        / max(out["n_sessions_traded"], 1)),
        # THE D-048 DENOMINATOR: every asset-session of the era, traded or not.
        # This is the ERA_CURVE's own convention and the only one the $2,000
        # bar was ever written against.
        "usd_per_session_all": float(cert.sum() / max(n_sess_era, 1)),
    })
    return out, {"weeks": wk, "week_usd": wv.tolist(),
                 "day_usd": dv.tolist(), "day_n": dn.tolist()}


def era_context(D, ev):
    days = sorted(set(int(x) for x in D["d8"][ev].tolist()))
    weeks = sorted(set(_iso_week(d) for d in days))
    n_sess = int(np.unique(D["session"][ev]).size)
    return days, weeks, n_sess


def tier_index(score, idx, pct):
    """The top `pct`% of `idx` by `score` (ties broken by the earlier second)."""
    i = np.asarray(idx, dtype=np.int64)
    s = score[i]
    ok = np.isfinite(s)
    i, s = i[ok], s[ok]
    if i.size == 0:
        return i
    n = max(1, int(round(i.size * float(pct) / 100.0)))
    order = np.argsort(-s, kind="stable")
    return np.sort(i[order[:n]])


def calibration(D, score, idx, pct):
    """Predicted vs realised winner rate inside the tier — over CANDIDATES, not
    over seats: a calibration statement is about the score, not the schedule."""
    sel = tier_index(score, idx, pct)
    if sel.size == 0:
        return None
    y = D["y_winner"][sel]
    ok = np.isfinite(y)
    if not ok.any():
        return None
    cl = [str(int(d)) for d in D["d8"][sel][ok].tolist()]
    st = PS.cluster_mean(y[ok], cl)
    return {"n": int(ok.sum()), "predicted": float(np.nanmean(score[sel])),
            "realised": float(np.nanmean(y[ok])),
            "ci_lo": (st or {}).get("ci_lo"), "ci_hi": (st or {}).get("ci_hi"),
            "score_min": float(np.nanmin(score[sel])),
            "score_max": float(np.nanmax(score[sel]))}


def day_qualification(D, score, ev, thresholds, top_k=3):
    """CAUSAL day-quality gate: a (asset, day) qualifies the instant its running
    top-`top_k` mean of arrived candidate scores crosses the threshold.

    The rule reads only scores of candidates that have already fired, so the
    qualifying candidate is itself seatable at its own decision second; every
    later candidate of the day is seatable too.  Nothing after the second is
    read, which is the whole point — a day-end score would be an oracle.
    """
    i = np.asarray(ev, dtype=np.int64)
    s = score[i]
    ok = np.isfinite(s)
    i, s = i[ok], s[ok]
    sess = D["session"][i]
    order = np.lexsort((D["dec_sec"][i], sess))
    i, s, sess = i[order], s[order], sess[order]
    starts = [0] + (np.flatnonzero(sess[1:] != sess[:-1]) + 1).tolist()
    stops = starts[1:] + [sess.size]
    qual = {t: [] for t in thresholds}
    for a, b in zip(starts, stops):
        ss = s[a:b]
        run = []
        best = np.full(ss.size, -np.inf)
        for j, v in enumerate(ss.tolist()):
            run.append(v)
            run.sort(reverse=True)
            del run[top_k:]
            if len(run) >= min(top_k, ss.size):
                best[j] = sum(run) / len(run)
        # the running top-k mean is not monotone; the day qualifies at the
        # FIRST second it crosses and stays qualified (an entry permission,
        # once granted by information already on the tape, is not revoked)
        for t in thresholds:
            hit = np.nonzero(best >= t)[0]
            if hit.size:
                qual[t].extend(i[a + hit[0]:b].tolist())
    return {t: np.sort(np.asarray(v, dtype=np.int64)) for t, v in qual.items()}


def _fmt(v, nd=4):
    if v is None:
        return "."
    if isinstance(v, float) and not np.isfinite(v):
        return "."
    if isinstance(v, float):
        return ("%%.%df" % nd) % v
    return str(v)


def W(name, cols, rows, extra=()):
    path = os.path.join(PROV, name)
    lines = ["# PORT M2 %s (%s)" % (SECTION, VERSION)]
    for e in extra:
        lines.append("# %s" % e)
    lines.append("\t".join(cols))
    with open(path + ".tmp", "w", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
        for r in rows:
            fh.write("\t".join(_fmt(v) for v in r) + "\n")
    os.replace(path + ".tmp", path)
    hb("wrote %s (%d rows)" % (path, len(rows)))
    return path


MET_COLS = ("n_candidates", "n_seated", "n_forfeited", "precision",
            "precision_lo", "precision_hi", "usd_per_trade",
            "usd_per_trade_lo", "usd_per_trade_hi", "takes_per_day",
            "takes_per_week", "usd_per_day", "usd_per_day_lo",
            "usd_per_day_hi", "usd_per_traded_day", "usd_per_week",
            "usd_per_week_lo", "usd_week_p10", "usd_week_median",
            "frac_losing_weeks", "frac_days_traded", "n_days_traded",
            "usd_per_session_all", "usd_per_session_traded", "mean_mae_usd",
            "walled_rate", "frac_ge_600", "usd_total")


def _row(era, grain, arm, m, extra_head=()):
    return [era, grain, arm, m["tier"]] + list(extra_head) \
        + [m.get(c) for c in MET_COLS]


def main_frontier():
    D = load_D()
    S = dict(np.load(os.path.join(OUT_ROOT, "scores.npz"), allow_pickle=False))
    rng = np.random.RandomState(SEED)
    thr_rows, cal_rows, day_rows, agr_rows = [], [], [], []
    plane = []                       # every operating point, for the verdict
    detail = {}

    def point(era, family, name, m):
        plane.append(dict(m, era=era, family=family, point=name))

    for era in ERAS_REPORTED:
        k = M3.ERA_NAMES.index(era)
        ev_all = np.nonzero(D["era_idx"] == k)[0]
        ev = deployable(D, ev_all)
        ev = ev[D["cert_refused"][ev] == 0]
        ctx = era_context(D, ev_all)
        days, weeks, _ns = ctx
        ep_rank = D["X"][:, D["names"].index("ep_rank")]
        ev_ep = ev[ep_rank[ev] == 0]
        lbl = ERA_LABEL.get(era, era)

        scores = {}
        for arm in ARMS:
            key = "%s|%s" % (era, arm)
            if key in S:
                scores[arm] = S[key].astype(np.float64)
        if "FULL_TF" not in scores:
            continue
        # the red-first control: FULL_TF's own scores, permuted within the era
        sh = scores["FULL_TF"].copy()
        v = sh[ev]
        sh[ev] = v[rng.permutation(v.size)]
        scores["SHUFFLE"] = sh
        # the COMPOSED reading (the walk's own composition), if the retg head
        # of this era was fitted
        if "%s|FULL_TF_RETG" % era in S:
            r2 = S["%s|FULL_TF_RETG" % era].astype(np.float64)
            comp = np.full(D["d8"].size, np.nan)
            comp[ev] = (MX._rank_pct(scores["FULL_TF"][ev])
                        + MX._rank_pct(r2[ev]))
            scores["COMPOSED"] = comp

        # ---------------- 2. THE THRESHOLD FRONTIER ------------------------
        for grain, pool in (("candidate", ev), ("episode", ev_ep)):
            for arm in list(scores):
                for p in TIERS_PCT:
                    sel = tier_index(scores[arm], pool, p)
                    m, det = replay_metrics(D, sel, ctx, "top_%g%%" % p)
                    thr_rows.append(_row(lbl, grain, arm, m))
                    if arm in ("FULL_TF", "SHUFFLE") and grain == "candidate":
                        detail["%s|%s|%g" % (lbl, arm, p)] = det
                    if arm in ("FULL_TF", "COMPOSED"):
                        point(lbl, "threshold_%s_%s" % (grain, arm),
                              "top_%g%%" % p, m)
            # THE STRICTLY-CAUSAL THRESHOLD ARM: the score CUT is the same
            # percentile of the PREVIOUS era's out-of-sample scores, applied
            # unchanged here.  Nothing about this era's own distribution is
            # read, so it is a threshold a deployed system could actually hold.
            prev = M3.ERA_NAMES[k - 1] if k > 0 else None
            pk = "%s|FULL_TF" % prev if prev else None
            if pk and pk in S:
                pev = deployable(D, np.nonzero(D["era_idx"] == k - 1)[0])
                pev = pev[D["cert_refused"][pev] == 0]
                if grain == "episode":     # the cut must be a percentile of
                    pev = pev[ep_rank[pev] == 0]   # the SAME population
                pv = S[pk].astype(np.float64)[pev]
                pv = pv[np.isfinite(pv)]
                for p in TIERS_PCT:
                    if pv.size == 0:
                        continue
                    cut = float(np.percentile(pv, 100.0 - p))
                    s_here = scores["FULL_TF"][pool]
                    sel = pool[np.isfinite(s_here) & (s_here >= cut)]
                    m, _d = replay_metrics(D, sel, ctx, "top_%g%%_prev_cut" % p)
                    thr_rows.append(_row(lbl, grain, "FULL_TF_PREVCUT", m))
                    point(lbl, "threshold_%s_prevcut" % grain,
                          "top_%g%%" % p, m)
            # calibration, on the best model only
            if grain == "candidate":
                for p in TIERS_PCT:
                    c = calibration(D, scores["FULL_TF"], pool, p)
                    if c:
                        cal_rows.append([lbl, grain, "FULL_TF", "top_%g%%" % p,
                                         c["n"], c["predicted"], c["realised"],
                                         c["ci_lo"], c["ci_hi"],
                                         c["score_min"], c["score_max"],
                                         c["realised"] - c["predicted"]])
                    c2 = calibration(D, scores["SHUFFLE"], pool, p)
                    if c2:
                        cal_rows.append([lbl, grain, "SHUFFLE", "top_%g%%" % p,
                                         c2["n"], c2["predicted"],
                                         c2["realised"], c2["ci_lo"],
                                         c2["ci_hi"], c2["score_min"],
                                         c2["score_max"],
                                         c2["realised"] - c2["predicted"]])

        # ---------------- 3. THE DAY-ABSTENTION FRONTIER -------------------
        sc = scores["FULL_TF"]
        qv = sc[ev]
        qv = qv[np.isfinite(qv)]
        gates = [float(np.percentile(qv, q)) for q in
                 (0, 50, 70, 80, 90, 95, 97.5, 99)]
        qual = day_qualification(D, sc, ev, gates)
        for q, t in zip((0, 50, 70, 80, 90, 95, 97.5, 99), gates):
            pool = qual[t]
            n_sess = int(np.unique(D["session"][pool]).size) if pool.size else 0
            for p in (0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 100.0):
                sel = tier_index(sc, pool, p) if pool.size else pool
                m, _d = replay_metrics(D, sel, ctx, "top_%g%%" % p)
                day_rows.append([lbl, "causal_top3_running", "q%.1f" % q,
                                 round(t, 6), n_sess, "top_%g%%" % p]
                                + [m.get(c) for c in MET_COLS])
                point(lbl, "daygate_causal_q%.1f" % q, "top_%g%%" % p, m)

        # the ORACLE-FREE variant: the pre-day model, if it was built
        pth = os.path.join(OUT_ROOT, "dayscore.npz")
        if os.path.exists(pth):
            Z = np.load(pth, allow_pickle=False)
            if ("s_" + era) in Z.files:
                dsc = Z["s_" + era]
                dses = np.array([str(x) for x in Z["session"].tolist()])
                keep = np.isfinite(dsc)
                pcts = (0, 50, 70, 80, 90, 95)
                cuts = [float(np.percentile(dsc[keep], q)) for q in pcts]
                for q, t in zip(pcts, cuts):
                    good = set(dses[keep & (dsc >= t)].tolist())
                    pool = ev[np.isin(D["session"][ev], list(good))]
                    for p in (0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 100.0):
                        sel = tier_index(sc, pool, p) if pool.size else pool
                        m, _d = replay_metrics(D, sel, ctx, "top_%g%%" % p)
                        day_rows.append([lbl, "preday_forecaster", "q%.1f" % q,
                                         round(t, 2), len(good),
                                         "top_%g%%" % p]
                                        + [m.get(c) for c in MET_COLS])
                        point(lbl, "daygate_preday_q%.1f" % q,
                              "top_%g%%" % p, m)
            Z.close()

        # ---------------- 4. THE AGREEMENT TIERS ---------------------------
        trio = [a for a in ("FULL_TF", "TEACHER", "SEQ") if a in scores]
        joint_gate = {}
        if len(trio) == 3:
            jq = [float(np.percentile(qv, q)) for q in (80, 90, 95)]
            jd = day_qualification(D, sc, ev, jq)
            for q, t in zip((80, 90, 95), jq):
                joint_gate[q] = np.isin(ev, jd[t])
        if len(trio) == 3:
            pct = {a: np.full(D["d8"].size, np.nan) for a in trio}
            for a in trio:
                pct[a][ev] = MX._rank_pct(scores[a][ev])
            for p in (0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0):
                cutoff = 1.0 - p / 100.0
                inn = {a: (pct[a][ev] >= cutoff) for a in trio}
                nagree = sum(inn[a].astype(int) for a in trio)
                for label, mask in (("1of3_any", nagree >= 1),
                                    ("2of3", nagree >= 2),
                                    ("3of3", nagree == 3)):
                    sel = ev[mask]
                    m, _d = replay_metrics(D, sel, ctx, "top_%g%%" % p)
                    agr_rows.append([lbl, label, "top_%g%%" % p]
                                    + [m.get(c) for c in MET_COLS])
                    point(lbl, "agreement_" + label, "top_%g%%" % p, m)
                for a in trio:
                    sel = ev[inn[a]]
                    m, _d = replay_metrics(D, sel, ctx, "top_%g%%" % p)
                    agr_rows.append([lbl, "alone_" + a, "top_%g%%" % p]
                                    + [m.get(c) for c in MET_COLS])
                    point(lbl, "agreement_alone_" + a, "top_%g%%" % p, m)
                # THE JOINT PLANE the verdict is read off: the day gate AND the
                # agreement rule AND the threshold, together.
                for q in (80, 90, 95):
                    keepm = joint_gate.get(q)
                    if keepm is None or not keepm.any():
                        continue
                    for label, mask in (("2of3", nagree >= 2),
                                        ("3of3", nagree == 3)):
                        sel = ev[mask & keepm]
                        m, _d = replay_metrics(D, sel, ctx, "top_%g%%" % p)
                        point(lbl, "joint_daygate_q%d_%s" % (q, label),
                              "top_%g%%" % p, m)

    # ------------------------------------------------------------ writing --
    head = ["era", "grain", "score", "tier"] + list(MET_COLS)
    W("PRECISION_FRONTIER_THRESHOLD.tsv", head, thr_rows,
      ["THE threshold frontier: every tier of every score, per era, "
       "out-of-sample (walk-forward: model_k sees only eras < k)",
       "precision = D-021 walled-winner rate among SEATED trades; CIs are "
       "CR1 clustered by CALENDAR DAY (the draw unit, D-036/D-073)",
       "takes_per_week / usd_per_week are PORTFOLIO totals across SI+HG+NKD "
       "(the user's throughput floor is 3-4 takes per week, total)",
       "SHUFFLE = FULL_TF's own scores permuted within the era: the red-first "
       "receipt.  Its frontier must be FLAT."])
    W("PRECISION_FRONTIER_CALIBRATION.tsv",
      ["era", "grain", "score", "tier", "n_candidates", "predicted_rate",
       "realised_rate", "realised_ci_lo", "realised_ci_hi", "score_min",
       "score_max", "realised_minus_predicted"], cal_rows,
      ["predicted vs realised winner rate INSIDE each tier, over CANDIDATES "
       "(a calibration statement is about the score, not the schedule)",
       "the head is fitted with reg:squarederror on the 0/1 winner label, so "
       "its output is a predicted RATE and is directly comparable"])
    W("PRECISION_FRONTIER_DAYGATE.tsv",
      ["era", "gate", "gate_pct", "gate_value", "n_sessions_qualified",
       "tier"] + list(MET_COLS), day_rows,
      ["THE DAY-ABSTENTION FRONTIER.  causal_top3_running: an (asset, day) "
       "qualifies the instant its RUNNING top-3 mean of arrived candidate "
       "scores crosses the gate — no day-end quantity is read anywhere",
       "preday_forecaster: the oracle-free variant — a walk-forward day-value "
       "model on the forecaster + overnight state as of the day's FIRST "
       "candidate second, no candidate score in it at all"])
    W("PRECISION_FRONTIER_AGREEMENT.tsv",
      ["era", "rule", "tier"] + list(MET_COLS), agr_rows,
      ["three INDEPENDENT readers of the same second: the full model (with "
       "teacher features), the teacher-evidence block alone, and the raw "
       "event-stream cue block alone",
       "2of3 / 3of3 = the candidate is inside the tier for at least two / all "
       "three scores; alone_* is the same tier for one score by itself"])
    # ---------------- 5. THE VERDICT: the best point on the whole plane -----
    ver_rows = []
    for era in ERAS_REPORTED:
        lbl = ERA_LABEL.get(era, era)
        pts = [p for p in plane if p["era"] == lbl and p["n_seated"] > 0]
        for floor in WEEK_FLOORS:
            elig = [p for p in pts if p["takes_per_week"] >= floor]
            if not elig:
                ver_rows.append([lbl, floor, "NONE", "", 0] + [None] *
                                (len(MET_COLS) + 4))
                continue
            for crit, keyf in (("max_usd_per_week",
                                lambda p: p["usd_per_week"]),
                               ("max_precision",
                                lambda p: (p["precision"], p["usd_per_week"])),
                               ("max_usd_per_trade",
                                lambda p: (p["usd_per_trade"],
                                           p["usd_per_week"]))):
                b = max(elig, key=keyf)
                ver_rows.append(
                    [lbl, floor, crit, "%s|%s" % (b["family"], b["point"]),
                     b["n_seated"]]
                    + [b.get(c) for c in MET_COLS]
                    + [b["usd_per_session_all"] - M3.BAR_PER_SESSION_USD,
                       int(b["usd_per_trade"] >= M3.BAR_TRADE_MIN_USD),
                       int(b["usd_per_trade"] >= M3.BAR_TRADE_TARGET_USD),
                       int(b["usd_per_session_all"]
                           >= M3.BAR_THIN_FLOOR_USD)])
    W("PRECISION_FRONTIER_VERDICT.tsv",
      ["era", "week_floor_takes", "criterion", "operating_point", "n_seated"]
      + list(MET_COLS) + ["vs_D048_2000", "clears_D021_600",
                          "clears_D021_1000", "clears_thin_floor_1500"],
      ver_rows,
      ["THE VERDICT PLANE: every (threshold x day-abstention x agreement) "
       "operating point measured above, filtered to the user's WEEKLY "
       "THROUGHPUT FLOOR (portfolio takes per week across all three assets), "
       "then maximised three ways",
       "D-021: $600 minimum / $1,000 target per trade.  D-048: $2,000 per "
       "session per asset, $1,500 thin-era floor — usd_per_session_all is the "
       "ERA_CURVE denominator (every asset-session of the era, traded or not)"])

    with open(os.path.join(OUT_ROOT, "frontier_detail.json"), "w") as fh:
        json.dump(detail, fh, indent=1, sort_keys=True)
    with open(os.path.join(OUT_ROOT, "plane.json"), "w") as fh:
        json.dump(plane, fh, indent=1, sort_keys=True, default=float)
    rec = {"version": VERSION, "section": SECTION,
           "eras": list(ERAS_REPORTED), "tiers_pct": list(TIERS_PCT),
           "week_floors": list(WEEK_FLOORS), "seed": SEED,
           "n_threshold_rows": len(thr_rows), "n_daygate_rows": len(day_rows),
           "n_agreement_rows": len(agr_rows), "n_plane_points": len(plane),
           "n_verdict_rows": len(ver_rows)}
    with open(os.path.join(OUT_ROOT, "frontier.receipt.json"), "w") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True)
    return thr_rows, cal_rows, day_rows, agr_rows, ver_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq", action="store_true")
    ap.add_argument("--scores", action="store_true")
    ap.add_argument("--daymodel", action="store_true")
    ap.add_argument("--frontier", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--nthread", type=int, default=8)
    a = ap.parse_args()
    MC.verify_spec(force=True)
    if a.seq:
        build_seq(workers=a.workers)
    if a.scores:
        build_scores(nthread=a.nthread)
    if a.daymodel:
        build_daymodel(nthread=a.nthread)
    if a.frontier:
        main_frontier()
    if not any((a.seq, a.scores, a.daymodel, a.frontier)):
        ap.print_help()
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
