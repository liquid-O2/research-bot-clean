#!/usr/bin/python3
"""PORT M1 Track B-2 — vol layer V1/V2 (§3) + the CC-M1-1(A) expected-move ladder.

HONESTY LAW (§3): every quantity here is REALIZED or FORECAST.  Nothing is
implied volatility; the two external series (GVZ, Nikkei VI) enter only as
strictly-prior CONTEXT regressors and are never presented as this asset's IV.

V1 (realized, per asset x session x segment):
    segments = SESSION + the three FROZEN m0 phases + OVERNIGHT (the §4(c)
    pre-RTH-open segment; see m1_common.SEG_NAMES).
    rv/bv/jump from 5-min-subsampled mids, all in DOLLAR space (r = dmid x mult)
    because every downstream object (bands, gates, walls) is denominated in
    contract dollars; sigma_usd = sqrt(rv_usd); Parkinson/GK/RS from segment
    OHLC; vol-of-vol = 20-session rolling std of sigma_usd; clock-normed
    variants divide by the trailing-60-session same-segment median.

V2 (forecast): HAR-RV, OLS on log targets, expanding walk-forward refit
    MONTHLY.  Two target kinds per segment: RANGE_$ (the §3 named target, the
    one the benchmarks are judged on) and SIGMA_$ (what §4(a)'s bands need).
    Era law: the 2025 forecasts used downstream carry coefficients FROZEN at
    the last FIT-era refit; a continuing walk-forward is emitted beside them as
    a diagnostic only.

CC-M1-1(A): the expected-move ladder.  ratio_t = realized_range_t / sigma_hat_t;
    trailing-250-session (strictly prior) empirical quantiles Q_q for
    q in {0.10,0.25,0.50,0.75,0.90} give calibrated move sizes
    move_q(d) = Q_q x sigma_hat(d); levels (built in §4) are anchor +- move_q,
    q10 = MIN-expected-move, q90 = MAX-expected-move.  The REGIME-SCALED ladder
    takes the same quantiles inside the session's vol-regime bucket (terciles of
    RV_5/RV_66, cut points frozen on the FIT era).

D-054 (R80): every session is loaded through the CC-M1-4 MID-SANITY mask before
    a single estimator touches it.  The V1 block reads `s.valid`, so until this
    was wired the whole vol layer — sigma_hat, range_hat, rv/bv/jump, the move_q*
    ladder and the vol-regime terciles — was computed over the spread-collapse
    seconds b7_sane exists to delete, and the committed artifact stayed pinned
    two spec revisions before D-054 landed.  A session with no committed
    threshold is a REFUSAL (b7_sane.SaneThresholdRefusal), never the $500 cap.
"""
import datetime as dt
import math
import multiprocessing as mp
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m1_common as M
import common as C
import census_common as X
import b7_sane as B7

SECTION = "§3 vol layer V1/V2 + CC-M1-1(A) + D-054 SANE mids"

SUBSAMPLE_SEC = 300             # §3 "5-min-subsampled RV"
VOLOFVOL_WINDOW = 20            # §3 "20-session rolling std of session RV"
CLOCKNORM_WINDOW = 60           # §3 "trailing-60-session same-phase median"
HAR_LAGS = (1, 5, 22)           # §3 {RV_1, RV_5avg, RV_22avg}
REGIME_LONG = 66                # CC-M1-1(A) RV_5/RV_66
MIN_TRAIN = 250                 # sessions before the first walk-forward fit
REFIT = "monthly"
LADDER_Q = (0.10, 0.25, 0.50, 0.75, 0.90)
LADDER_WINDOW = 250             # CC-M1-1(A) trailing-250-session calibration
LADDER_MIN_REGIME_OBS = 30      # else fall back to the unscaled calibration

TARGET_SEGMENTS = ("SESSION", "TOKYO", "LONDON", "NY")   # §3 next-session/phase
TARGET_KINDS = ("RANGE", "SIGMA")

PARAMS = {
    "spec_section": SECTION,
    "subsample_sec": SUBSAMPLE_SEC,
    "space": "dollar space: r = (mid_t - mid_{t-300s}) x mult",
    "segments": list(M.SEG_NAMES) + ["SESSION"],
    "estimators": ["rv", "bv (pi/2 sum |r_i||r_i-1|)", "jump = max(rv-bv,0)",
                   "parkinson", "gk", "rs", "volofvol_20", "clocknorm_60"],
    "har_lags": list(HAR_LAGS),
    "har_form": "OLS on log targets; x = [1, log RV_1, log RV_5, log RV_22, "
                "log parkinson_1, log gk_1, log rs_1, log1p(jump_1), "
                "log context (SI GVZ / NKD NIKKEI_VI, strictly prior), "
                "dow dummies Tue..Fri]",
    "walk_forward": "expanding window, refit %s, min train %d sessions"
                    % (REFIT, MIN_TRAIN),
    "era_law": "hyperparameters and the downstream-frozen coefficients come "
               "from FIT 2021-2024 only; 2025 forecasts used by §4 carry the "
               "coefficients frozen at 2024-12-31",
    "benchmarks": ["debiased persistence (log-space calibration)",
                   "ATR14 raw", "ATR14 calibrated (log-space, strengthened)"],
    "verdict_rule": "fvol must beat BOTH benchmarks on FIT-era walk-forward "
                    "MAE ($); ATR14 taken at its STRONGER of raw/calibrated",
    "ladder_q": list(LADDER_Q),
    "ladder_window": LADDER_WINDOW,
    "ladder_ratio": "realized_range / sigma_hat, trailing %d sessions, "
                    "strictly prior" % LADDER_WINDOW,
    "regime": "terciles of RV_5/RV_66, cut points frozen on FIT era",
    "mid_sanity": "D-054 / CC-M1-4: every session is masked by b7_sane.apply "
                  "before any estimator reads it; a session with no committed "
                  "threshold is REFUSED, never given the $500 cap alone (R89)",
}


# ================================================================ V1 =========
def segment_masks(s):
    """{name: boolean mask over session seconds} for the five §3/§4 segments."""
    o = int(s.meta["open_utc"])
    sod = (o + np.arange(s.n, dtype=np.int64)) % 86400
    out = {"SESSION": np.ones(s.n, dtype=bool),
           "OVERNIGHT": sod < M.OVERNIGHT_END_SOD}
    for p, name in enumerate(X.PHASE_NAMES):
        out[name] = s.phase_tag == p
    return out


def realized(s, mult, mask):
    """The §3 V1 estimator block for one segment.  Dollar space."""
    sel = mask & s.valid
    idx = np.nonzero(sel)[0]
    out = {"n_valid": int(idx.size)}
    if idx.size < 2:
        for k in ("open_px", "high_px", "low_px", "close_px", "range_usd",
                  "rv_usd", "bv_usd", "jump_usd", "sigma_usd",
                  "parkinson_usd", "gk_usd", "rs_usd"):
            out[k] = float("nan")
        out["first_sec"] = int(idx[0]) if idx.size else -1
        out["last_sec"] = int(idx[-1]) if idx.size else -1
        return out
    m = s.mid[idx]
    out["first_sec"] = int(idx[0])
    out["last_sec"] = int(idx[-1])
    o_, h_, l_, c_ = float(m[0]), float(m.max()), float(m.min()), float(m[-1])
    out["open_px"], out["high_px"] = o_, h_
    out["low_px"], out["close_px"] = l_, c_
    out["range_usd"] = (h_ - l_) * mult

    # 5-min subsample: last valid mid at or before each grid second
    g = np.arange(idx[0], idx[-1] + 1, SUBSAMPLE_SEC, dtype=np.int64)
    j = np.searchsorted(idx, g, side="right") - 1
    j = j[j >= 0]
    if j.size >= 2:
        r = np.diff(m[j]) * mult
        rv = float(np.sum(r * r))
        bv = float(np.pi / 2.0 * np.sum(np.abs(r[1:]) * np.abs(r[:-1]))) \
            if r.size >= 2 else 0.0
    else:
        rv, bv = float("nan"), float("nan")
    out["rv_usd"] = rv
    out["bv_usd"] = bv
    out["jump_usd"] = (max(rv - bv, 0.0) if np.isfinite(rv) and np.isfinite(bv)
                       else float("nan"))
    out["sigma_usd"] = math.sqrt(rv) if np.isfinite(rv) and rv >= 0 else float("nan")

    scale = c_ * mult
    hl = math.log(h_ / l_) if (h_ > 0 and l_ > 0) else float("nan")
    co = math.log(c_ / o_) if (c_ > 0 and o_ > 0) else float("nan")
    hc = math.log(h_ / c_) if (h_ > 0 and c_ > 0) else float("nan")
    ho = math.log(h_ / o_) if (h_ > 0 and o_ > 0) else float("nan")
    lc = math.log(l_ / c_) if (l_ > 0 and c_ > 0) else float("nan")
    lo = math.log(l_ / o_) if (l_ > 0 and o_ > 0) else float("nan")
    out["parkinson_usd"] = math.sqrt(hl * hl / (4.0 * math.log(2.0))) * scale \
        if np.isfinite(hl) else float("nan")
    gk = 0.5 * hl * hl - (2.0 * math.log(2.0) - 1.0) * co * co
    out["gk_usd"] = math.sqrt(max(gk, 0.0)) * scale if np.isfinite(gk) \
        else float("nan")
    rs = hc * ho + lc * lo
    out["rs_usd"] = math.sqrt(max(rs, 0.0)) * scale if np.isfinite(rs) \
        else float("nan")
    return out


V1_METRICS = ("n_valid", "first_sec", "last_sec", "open_px", "high_px",
              "low_px", "close_px", "range_usd", "rv_usd", "bv_usd",
              "jump_usd", "sigma_usd", "parkinson_usd", "gk_usd", "rs_usd")


def _v1_shard(args):
    asset, month, sess, thr_map = args
    mult = C.ASSETS[asset]["mult"]
    rows = []
    for trade_date, path in sess:
        s = X.load_session(asset, trade_date, path)
        # D-054 (R80): the SANE view is installed BEFORE any estimator reads
        # s.valid / s.vt / s.vm.  Refuses (never defaults) on a missing row.
        B7.apply_for(s, thr_map, asset,
                     trade_date.year * 10000 + trade_date.month * 100
                     + trade_date.day)
        masks = segment_masks(s)
        for seg in ("SESSION",) + M.SEG_NAMES:
            r = realized(s, mult, masks[seg])
            rows.append([asset, trade_date.isoformat(), trade_date.year, seg]
                        + [r[k] for k in V1_METRICS])
    return rows


V1_COLUMNS = ["asset", "trade_date", "year", "segment"] + list(V1_METRICS)
V1_DERIVED = ["volofvol_20_usd", "sigma_clocknorm", "rv_clocknorm",
              "range_clocknorm", "rv5_over_rv66", "regime_tag"]


def build_v1(assets, workers, months=None):
    tasks = []
    for asset in assets:
        thr_map = B7.load_thresholds(asset)      # D-054, once per asset
        by_month = {}
        for d, p in X.session_paths(asset, M.M0_ROOT):
            if months and X.month_key(d) not in months:
                continue
            by_month.setdefault(X.month_key(d), []).append((d, p))
        for mk in sorted(by_month):
            tasks.append((asset, mk, by_month[mk], thr_map))
    M.hb("b2 V1: %d (asset,month) tasks" % len(tasks))
    if workers <= 1 or len(tasks) <= 1:
        res = [_v1_shard(t) for t in tasks]
    else:
        with mp.Pool(min(workers, len(tasks))) as pool:
            res = list(pool.map(_v1_shard, tasks, chunksize=1))
    rows = []
    for r in res:
        rows.extend(r)
    rows.sort(key=lambda r: (r[0], r[3], r[1]))
    rows = _v1_derived(rows)
    return rows


def _v1_derived(rows):
    """volofvol, clock-norms and the CC-M1-1 regime tag — all trailing/causal."""
    ci = {c: i for i, c in enumerate(V1_COLUMNS)}
    cut = _regime_cuts(rows, ci)
    out = []
    groups = {}
    for r in rows:
        groups.setdefault((r[0], r[3]), []).append(r)
    for key in sorted(groups):
        g = groups[key]
        g.sort(key=lambda r: r[1])
        sig = np.array([r[ci["sigma_usd"]] for r in g], dtype=np.float64)
        rv = np.array([r[ci["rv_usd"]] for r in g], dtype=np.float64)
        rng = np.array([r[ci["range_usd"]] for r in g], dtype=np.float64)
        n = len(g)
        for i in range(n):
            lo20 = max(0, i - VOLOFVOL_WINDOW)
            w = sig[lo20:i]
            w = w[np.isfinite(w)]
            vov = float(w.std(ddof=1)) if w.size >= 2 else float("nan")
            lo60 = max(0, i - CLOCKNORM_WINDOW)
            cn = []
            for arr, val in ((sig, sig[i]), (rv, rv[i]), (rng, rng[i])):
                h = arr[lo60:i]
                h = h[np.isfinite(h)]
                m_ = float(np.median(h)) if h.size else float("nan")
                cn.append(val / m_ if (np.isfinite(m_) and m_ > 0) else float("nan"))
            h5 = rv[max(0, i - 5):i]
            h5 = h5[np.isfinite(h5)]
            h66 = rv[max(0, i - REGIME_LONG):i]
            h66 = h66[np.isfinite(h66)]
            ratio = (float(h5.mean()) / float(h66.mean())
                     if (h5.size and h66.size and h66.mean() > 0)
                     else float("nan"))
            tag = _regime_of(ratio, cut.get(key))
            out.append(g[i] + [vov, cn[0], cn[1], cn[2], ratio, tag])
    out.sort(key=lambda r: (r[0], r[3], r[1]))
    return out


def _regime_cuts(rows, ci):
    """Terciles of RV_5/RV_66 with cut points FROZEN on the FIT era (CC-M1-1)."""
    acc = {}
    groups = {}
    for r in rows:
        groups.setdefault((r[0], r[3]), []).append(r)
    for key in sorted(groups):
        g = sorted(groups[key], key=lambda r: r[1])
        rv = np.array([r[ci["rv_usd"]] for r in g], dtype=np.float64)
        vals = []
        for i in range(len(g)):
            if not M.is_fit(int(g[i][ci["year"]])):
                continue
            h5 = rv[max(0, i - 5):i]
            h5 = h5[np.isfinite(h5)]
            h66 = rv[max(0, i - REGIME_LONG):i]
            h66 = h66[np.isfinite(h66)]
            if h5.size and h66.size and h66.mean() > 0:
                vals.append(float(h5.mean()) / float(h66.mean()))
        if len(vals) >= 30:
            acc[key] = (M.pct(vals, 100.0 / 3.0), M.pct(vals, 200.0 / 3.0))
    return acc


def _regime_of(ratio, cuts):
    if cuts is None or not np.isfinite(ratio):
        return "NA"
    return "LOW" if ratio < cuts[0] else ("MID" if ratio < cuts[1] else "HIGH")


# ================================================================ V2 =========
DOW_NAMES = ("dow_TUE", "dow_WED", "dow_THU", "dow_FRI")


def _design(hist, i, seg, ctx_val, trade_date):
    """The §3 feature row for session index i of a segment series (causal)."""
    rv = hist["rv_usd"]
    if i < max(HAR_LAGS):
        return None
    def _avg(k):
        # MISSING-DATA POLICY (§3 states none): average the finite, strictly
        # positive observations inside the window and require at least half of
        # them.  Needed because phase segments legitimately go unobserved on
        # short/stale sessions; a strict full-window rule emptied the LONDON
        # and TOKYO models entirely (measured: 0 fittable rows).
        w = rv[i - k:i]
        w = w[np.isfinite(w) & (w > 0)]
        need = 1 if k == 1 else (k + 1) // 2
        return float(w.mean()) if w.size >= need else float("nan")
    rv1, rv5, rv22 = _avg(1), _avg(5), _avg(22)
    jump1 = hist["jump_usd"][i - 1]
    park1 = hist["sess_parkinson"][i - 1]
    gk1 = hist["sess_gk"][i - 1]
    rs1 = hist["sess_rs"][i - 1]
    vals = [rv1, rv5, rv22, park1, gk1, rs1]
    if any((not np.isfinite(v)) or v <= 0 for v in vals):
        return None
    if not np.isfinite(jump1) or jump1 < 0:
        return None
    x = [1.0, math.log(rv1), math.log(rv5), math.log(rv22),
         math.log(park1), math.log(gk1), math.log(rs1),
         math.log1p(jump1)]
    if ctx_val is not None:
        if not np.isfinite(ctx_val) or ctx_val <= 0:
            return None
        x.append(math.log(ctx_val))
    wd = trade_date.weekday()
    for k in range(1, 5):
        x.append(1.0 if wd == k else 0.0)
    return x


BASE_FEATURES = ("const", "log_rv1", "log_rv5", "log_rv22", "log_parkinson1",
                 "log_gk1", "log_rs1", "log1p_jump1")
CANON_FEATURES = BASE_FEATURES + ("log_context",) + DOW_NAMES


CONTEXT_MIN_COVERAGE = 0.80


def feature_names(asset, use_ctx):
    n = list(BASE_FEATURES)
    if use_ctx:
        n.append("log_ctx_%s" % M.CONTEXT_FILES[asset][0])
    return n + list(DOW_NAMES)


def _canon_beta(use_ctx, beta):
    """Beta mapped onto the CANONICAL column set (context slot NaN if unused)."""
    b = [float(x) for x in beta]
    if not use_ctx:
        b = b[:len(BASE_FEATURES)] + [float("nan")] + b[len(BASE_FEATURES):]
    return b


def context_decision(asset, dates, ctx):
    """§3 names a context series per asset, but the OWNED history must cover the
    sessions the model is fitted on.  Coverage below %d%% -> the context column
    is dropped from the model and the gap is reported (never silently fitted on
    a truncated era).""" % int(CONTEXT_MIN_COVERAGE * 100)
    if ctx is None:
        return False, 0.0, None
    n = len(dates)
    have = sum(1 for d in dates if np.isfinite(ctx.value_before(d)))
    cov = have / n if n else 0.0
    return bool(cov >= CONTEXT_MIN_COVERAGE), cov, ctx.name


def _ols(Xm, y):
    beta, _res, rank, _sv = np.linalg.lstsq(Xm, y, rcond=None)
    return beta, int(rank)


def fit_walkforward(asset, seg, kind, series, ctx, bars, use_ctx):
    """Expanding-window monthly-refit walk-forward for one (segment, kind).

    Returns a dict of per-session arrays: pred (walk-forward), pred_frozen
    (coefficients frozen at the last FIT-era refit — what §4 consumes in 2025),
    bench_persistence, bench_atr_raw, bench_atr_cal, plus the fit ledger.
    """
    dates = series["dates"]
    n = len(dates)
    tgt_col = "range_usd" if kind == "RANGE" else "sigma_usd"
    y_all = series[tgt_col]
    rows = []
    for i in range(n):
        ctx_val = ctx.value_before(dates[i]) if use_ctx else None
        rows.append(_design(series, i, seg, ctx_val, dates[i]))
    ok_y = np.array([np.isfinite(y_all[i]) and y_all[i] > 0
                     for i in range(n)], dtype=bool)
    ok = np.array([rows[i] is not None and ok_y[i] for i in range(n)],
                  dtype=bool)
    p = len(feature_names(asset, use_ctx))
    Xm = np.full((n, p), np.nan)
    for i in range(n):
        if rows[i] is not None:
            Xm[i] = rows[i]
    logy = np.where(ok_y, np.log(np.where(y_all > 0, y_all, 1.0)), np.nan)

    pred = np.full(n, np.nan)
    pred_frozen = np.full(n, np.nan)
    bench_p = np.full(n, np.nan)
    bench_a_raw = np.full(n, np.nan)
    bench_a_cal = np.full(n, np.nan)
    atr = np.array([bars.get(d, {}).get("ATR14_prev_usd", float("nan"))
                    for d in dates], dtype=np.float64)
    ledger = []

    months = sorted(set((d.year, d.month) for d in dates))
    beta_frozen = None
    cal_frozen = [float("nan"), float("nan")]      # last computed (persist, atr)
    prev = np.array([logy[i - 1] if (i > 0 and ok_y[i] and ok_y[i - 1])
                     else np.nan for i in range(n)])
    FREEZE_CUTOFF = dt.date(2025, 1, 1)            # era law: FIT ends 2024-12-31
    for (yy, mm) in months:
        cutoff = dt.date(yy, mm, 1)
        tr = np.array([ok[i] and dates[i] < cutoff for i in range(n)], bool)
        try_y = np.array([ok_y[i] and dates[i] < cutoff for i in range(n)], bool)
        te = np.array([dates[i].year == yy and dates[i].month == mm
                       for i in range(n)], bool)
        ntr = int(tr.sum())
        beta = None
        if int(try_y.sum()) >= MIN_TRAIN:
            b, rank = (_ols(Xm[tr], logy[tr]) if ntr >= MIN_TRAIN
                       else (None, -1))
            if rank >= p:
                beta = b
            # log-space debias calibrations for the two benchmarks
            dsel = try_y & np.isfinite(prev)
            cp = float(np.mean(logy[dsel] - prev[dsel])) if dsel.any() \
                else float("nan")
            asel = try_y & np.isfinite(atr) & (atr > 0)
            ca = float(np.mean(logy[asel] - np.log(atr[asel]))) \
                if asel.any() else float("nan")
            if cutoff <= FREEZE_CUTOFF:
                cal_frozen = [cp, ca]      # era law: no GATE-era calibration
            if beta is not None:
                if cutoff <= FREEZE_CUTOFF:
                    beta_frozen = beta.copy()
                ledger.append([asset, seg, kind, "%04d-%02d" % (yy, mm), ntr,
                               int(te.sum()), float(np.mean(logy[tr])), cp, ca,
                               bool(cutoff <= FREEZE_CUTOFF)]
                              + _canon_beta(use_ctx, beta))
        cp, ca = cal_frozen
        for i in np.nonzero(te)[0].tolist():
            if not ok_y[i]:
                continue
            if beta is not None and ok[i]:
                pred[i] = math.exp(float(Xm[i] @ beta))
            if beta_frozen is not None and ok[i]:
                pred_frozen[i] = math.exp(float(Xm[i] @ beta_frozen))
            if np.isfinite(prev[i]) and np.isfinite(cp):
                bench_p[i] = math.exp(float(prev[i]) + cp)
            if np.isfinite(atr[i]) and atr[i] > 0:
                bench_a_raw[i] = atr[i]
                if np.isfinite(ca):
                    bench_a_cal[i] = math.exp(math.log(atr[i]) + ca)
    return {"pred": pred, "pred_frozen": pred_frozen, "bench_p": bench_p,
            "bench_a_raw": bench_a_raw, "bench_a_cal": bench_a_cal,
            "y": y_all, "ok": ok, "ledger": ledger, "atr": atr}


def _pos(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return False
    return np.isfinite(v) and v > 0


def series_for(rows, asset, seg):
    """Ordered per-session arrays for one (asset, segment) + prior-session
    SESSION range estimators (the §3 'yesterday's range estimators').

    DEGENERATE SEGMENTS ARE DROPPED: the m0 substrate carries one stale-book
    receipt per week (Sunday-dated, thousands of "valid" seconds but a frozen
    quote -> range exactly $0).  Measured 231/1417 SI session rows.  They are
    not trading sessions; leaving them in poisons every HAR window that spans
    them and silently deletes the model (measured).
    """
    ci = {c: i for i, c in enumerate(V1_COLUMNS + V1_DERIVED)}
    ri = ci["range_usd"]
    sel = [r for r in rows if r[0] == asset and r[3] == seg
           and _pos(r[ri])]
    sel.sort(key=lambda r: r[1])
    sess = {r[1]: r for r in rows if r[0] == asset and r[3] == "SESSION"}
    dates = [dt.date.fromisoformat(r[1]) for r in sel]
    out = {"dates": dates}
    for k in ("rv_usd", "bv_usd", "jump_usd", "sigma_usd", "range_usd",
              "parkinson_usd", "gk_usd", "rs_usd", "rv5_over_rv66"):
        out[k] = np.array([float(r[ci[k]]) if r[ci[k]] not in ("", None)
                           else np.nan for r in sel], dtype=np.float64)
    out["regime_tag"] = [str(r[ci["regime_tag"]]) for r in sel]
    for k, src in (("sess_parkinson", "parkinson_usd"), ("sess_gk", "gk_usd"),
                   ("sess_rs", "rs_usd")):
        out[k] = np.array([float(sess[r[1]][ci[src]]) if r[1] in sess
                           else np.nan for r in sel], dtype=np.float64)
    out["years"] = np.array([d.year for d in dates], dtype=np.int64)
    return out


# ------------------------------------------------- CC-M1-1(A) ladder --------
def ladder(series, sigma_hat):
    """Trailing-250-session calibrated move quantiles, unscaled + regime-scaled.

    Both are strictly-prior: the ratio at session i uses only sessions < i.
    """
    y = series["range_usd"]
    n = len(series["dates"])
    ratio = np.full(n, np.nan)
    good = np.isfinite(y) & np.isfinite(sigma_hat) & (sigma_hat > 0)
    ratio[good] = y[good] / sigma_hat[good]
    tags = series["regime_tag"]
    uns = np.full((n, len(LADDER_Q)), np.nan)
    reg = np.full((n, len(LADDER_Q)), np.nan)
    src = ["NONE"] * n
    for i in range(n):
        lo = max(0, i - LADDER_WINDOW)
        w = ratio[lo:i]
        w = w[np.isfinite(w)]
        if w.size >= 30:
            for qi, q in enumerate(LADDER_Q):
                uns[i, qi] = np.percentile(w, q * 100.0)
        wr = np.array([ratio[j] for j in range(lo, i)
                       if np.isfinite(ratio[j]) and tags[j] == tags[i]
                       and tags[i] != "NA"], dtype=np.float64)
        if wr.size >= LADDER_MIN_REGIME_OBS:
            for qi, q in enumerate(LADDER_Q):
                reg[i, qi] = np.percentile(wr, q * 100.0)
            src[i] = "REGIME"
        elif w.size >= 30:
            reg[i] = uns[i]
            src[i] = "UNSCALED_FALLBACK"
    return uns, reg, src, ratio


# ------------------------------------------------- benchmark substitution ---
SOURCES = ("FVOL", "PERSISTENCE", "ATR14_CAL", "ATR14_RAW")


def _source_series(f, series):
    years = series["years"]
    return {"FVOL": np.where(years >= 2025, f["pred_frozen"], f["pred"]),
            "PERSISTENCE": f["bench_p"],
            "ATR14_CAL": f["bench_a_cal"],
            "ATR14_RAW": f["bench_a_raw"]}


def _fit_maes(f, series):
    y = f["y"]
    fit = np.isin(series["years"], np.array(M.FIT_YEARS))
    ss = _source_series(f, series)
    return {k: mae(v, y, fit)[0] for k, v in ss.items()}, ss


def _select(asset, seg, kind, f, series):
    m_, ss = _fit_maes(f, series)
    order = sorted(SOURCES, key=lambda k: (not np.isfinite(m_[k]), m_[k],
                                           SOURCES.index(k)))
    n = len(series["dates"])
    out = np.full(n, np.nan)
    src = np.array(["NONE"] * n, dtype="<U16")
    for k in order:
        need = ~np.isfinite(out) & np.isfinite(ss[k])
        out[need] = ss[k][need]
        src[need] = k if k == order[0] else (k + "_FILL")
    return out, src


def _sel_evidence(f, series):
    m_, _ = _fit_maes(f, series)
    order = sorted(SOURCES, key=lambda k: (not np.isfinite(m_[k]), m_[k],
                                           SOURCES.index(k)))
    return [order[0]] + [m_[k] for k in SOURCES] + [
        "fvol" if order[0] == "FVOL" else "BENCHMARK SUBSTITUTION (§3)"]


# ------------------------------------------------------------- verdict ------
def mae(pred, y, sel):
    s = sel & np.isfinite(pred) & np.isfinite(y)
    if not s.any():
        return float("nan"), 0
    return float(np.mean(np.abs(pred[s] - y[s]))), int(s.sum())


def main():
    M.verify_spec()
    workers = int(os.environ.get("M1_WORKERS", "6"))
    assets = [a for a in sys.argv[1:] if a in M.ASSET_ORDER] or list(M.ASSET_ORDER)
    phash = C.params_hash(PARAMS)

    v1 = build_v1(assets, workers)
    M.write_tsv(M.out_path("fvol", "v1_realized.tsv"), SECTION, phash,
                V1_COLUMNS + V1_DERIVED, v1,
                extra=["D-054 (R80): every session masked by b7_sane.apply "
                       "before any estimator; n_valid = SANE seconds",
                       "dollar space; OVERNIGHT = session seconds before the "
                       "committed RTH open (m0 §3 RTH_LO_SEC=52200)",
                       "clocknorm = value / trailing-%d-session same-segment "
                       "median (strictly prior)" % CLOCKNORM_WINDOW])
    M.hb("b2 V1: %d rows" % len(v1))

    fc_rows, mae_rows, ledger_rows, sel_rows = [], [], [], []
    frozen = {}
    ctx_rows = []
    for asset in assets:
        ctx = M.load_context(asset)
        bars = X.load_bars(asset, M.M0_ROOT)
        sess_series = series_for(v1, asset, "SESSION")
        use_ctx, cov, cname = context_decision(asset, sess_series["dates"], ctx)
        cr = float("nan")
        if ctx is not None:
            lx, ly = [], []
            for i, d in enumerate(sess_series["dates"]):
                v = ctx.value_before(d)
                y = sess_series["range_usd"][i]
                if np.isfinite(v) and v > 0 and np.isfinite(y) and y > 0:
                    lx.append(math.log(v))
                    ly.append(math.log(y))
            if len(lx) > 30:
                cr = float(np.corrcoef(lx, ly)[0, 1])
        ctx_rows.append([asset, cname or "NONE", cov,
                         len(sess_series["dates"]), bool(use_ctx), cr,
                         ctx.dates[0].isoformat() if ctx else "",
                         "used" if use_ctx else
                         ("no series" if ctx is None else
                          "DROPPED: coverage %.2f < %.2f"
                          % (cov, CONTEXT_MIN_COVERAGE))])
        M.hb("b2 context %s: %s coverage %.3f use=%s corr(log)=%.3f"
             % (asset, cname, cov, use_ctx, cr))
        for seg in TARGET_SEGMENTS:
            series = series_for(v1, asset, seg)
            fits = {}
            for kind in TARGET_KINDS:
                f = fit_walkforward(asset, seg, kind, series, ctx, bars,
                                    use_ctx)
                fits[kind] = f
                ledger_rows.extend(f["ledger"])
                y = f["y"]
                years = series["years"]
                for era, esel in (("FIT_2021_2024", np.isin(years, np.array(M.FIT_YEARS))),
                                  ("GATE_2025", years == 2025),
                                  ("ALL", np.ones(years.size, bool))):
                    cols = [("fvol", f["pred"]), ("fvol_frozen2024", f["pred_frozen"]),
                            ("persistence", f["bench_p"]),
                            ("atr14_raw", f["bench_a_raw"]),
                            ("atr14_cal", f["bench_a_cal"])]
                    got = {}
                    for nm, pr in cols:
                        mv, nn = mae(pr, y, esel)
                        got[nm] = (mv, nn)
                    best_atr = min([got["atr14_raw"][0], got["atr14_cal"][0]],
                                   key=lambda v: (not np.isfinite(v), v))
                    beat_p = (np.isfinite(got["fvol"][0])
                              and np.isfinite(got["persistence"][0])
                              and got["fvol"][0] < got["persistence"][0])
                    beat_a = (np.isfinite(got["fvol"][0])
                              and np.isfinite(best_atr)
                              and got["fvol"][0] < best_atr)
                    mae_rows.append(
                        [asset, seg, kind, era, got["fvol"][1],
                         got["fvol"][0], got["fvol_frozen2024"][0],
                         got["persistence"][0], got["atr14_raw"][0],
                         got["atr14_cal"][0], best_atr,
                         (got["persistence"][0] - got["fvol"][0])
                         / got["persistence"][0] if got["persistence"][0] else float("nan"),
                         (best_atr - got["fvol"][0]) / best_atr
                         if best_atr else float("nan"),
                         bool(beat_p), bool(beat_a),
                         "PASS" if (beat_p and beat_a) else "FAIL"])
            # --- forecasts consumed by §4.  §3 pre-registers the substitution
            # rule: "must beat both benchmarks ... else fvol levels are built
            # from the benchmark instead".  The winner is chosen on FIT-era
            # walk-forward MAE ONLY (never on 2025), per (asset, segment,
            # target); where the winner has no forecast the next-best source
            # fills in, so the level layer is never left without a sigma_hat.
            years = series["years"]
            sig, ssrc = _select(asset, seg, "SIGMA", fits["SIGMA"], series)
            rng, rsrc = _select(asset, seg, "RANGE", fits["RANGE"], series)
            src = ssrc
            sel_rows.append([asset, seg, "SIGMA"] + _sel_evidence(fits["SIGMA"],
                                                                  series))
            sel_rows.append([asset, seg, "RANGE"] + _sel_evidence(fits["RANGE"],
                                                                  series))
            uns, reg, lsrc, ratio = ladder(series, sig)
            for i, d in enumerate(series["dates"]):
                fc_rows.append([asset, d.isoformat(), d.year, seg,
                                sig[i], rng[i], str(src[i]),
                                series["regime_tag"][i],
                                series["rv5_over_rv66"][i], ratio[i],
                                lsrc[i]]
                               + [uns[i, q] for q in range(len(LADDER_Q))]
                               + [reg[i, q] for q in range(len(LADDER_Q))])
            frozen[(asset, seg)] = True
        M.hb("b2 V2 %s: done" % asset)

    qn = ["q%02d" % int(q * 100) for q in LADDER_Q]
    M.write_tsv(M.out_path("fvol", "fvol_forecasts.tsv"), SECTION, phash,
                ["asset", "trade_date", "year", "segment", "sigma_hat_usd",
                 "range_hat_usd", "sigma_source", "regime_tag",
                 "rv5_over_rv66", "ratio_range_over_sigmahat", "ladder_source"]
                + ["move_%s_usd_per_sigma" % q for q in qn]
                + ["move_rs_%s_usd_per_sigma" % q for q in qn], fc_rows,
                extra=["D-054 (R80): built on SANE mids (b7_sane / CC-M1-4); "
                       "supersedes the m1_spec_sha16=ce0a8ca16e342cd7 build",
                       "ladder columns are MULTIPLIERS on sigma_hat_usd "
                       "(CC-M1-1 A): move_q($) = column x sigma_hat_usd",
                       "2025 rows carry coefficients frozen at 2024-12-31 "
                       "(era law)"])
    M.write_tsv(M.out_path("fvol", "fvol_walkforward_mae.tsv"), SECTION, phash,
                ["asset", "segment", "target", "era", "n_forecasts",
                 "mae_fvol", "mae_fvol_frozen2024", "mae_persistence",
                 "mae_atr14_raw", "mae_atr14_cal", "mae_atr14_best",
                 "gain_vs_persistence", "gain_vs_atr14_best",
                 "beats_persistence", "beats_atr14", "verdict"], mae_rows,
                extra=["§7-B2 gate: fvol must beat BOTH benchmarks on FIT-era "
                       "walk-forward MAE; ATR14 taken at its stronger variant"])
    M.write_tsv(M.out_path("fvol", "fvol_selection.tsv"), SECTION, phash,
                ["asset", "segment", "target", "selected_source"]
                + ["fit_mae_%s" % k for k in SOURCES] + ["note"], sel_rows,
                extra=["§3 substitution rule: the level layer consumes the "
                       "source with the lowest FIT-era walk-forward MAE"])
    M.write_tsv(M.out_path("fvol", "fvol_context.tsv"), SECTION, phash,
                ["asset", "context_series", "coverage", "n_sessions",
                 "used_in_model", "corr_log_ctx_vs_log_range",
                 "series_first_date", "note"], ctx_rows,
                extra=["§3 names a context series per asset; a series that "
                       "does not cover the FIT era is a DATA GAP, reported "
                       "here and excluded from the model rather than fitted "
                       "on a truncated era"])
    M.write_tsv(M.out_path("fvol", "fvol_coefficients.tsv"), SECTION, phash,
                ["asset", "segment", "target", "refit_month", "n_train",
                 "n_predict", "mean_log_target", "cal_persistence_log",
                 "cal_atr_log", "is_frozen_candidate"]
                + ["beta_%s" % f for f in CANON_FEATURES], ledger_rows,
                extra=["the LAST row with is_frozen_candidate=1 per "
                       "(asset,segment,target) is the FROZEN coefficient "
                       "vector exported to M1.B (fit through 2024-12-31)",
                       "beta_log_context is empty for HG (no context series)"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
