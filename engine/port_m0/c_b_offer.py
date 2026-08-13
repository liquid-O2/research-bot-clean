#!/usr/bin/python3
"""PORT M0 c_b_offer — spec §7.

Committed offer formulas on the program substrate, both windowing conventions:

  range    = (max(m) - min(m)) x mult
  best_leg = max( max(m - cummin(m)), max(cummax(m) - m) ) x mult
  legs     = number of disjoint monotonic mid legs >= $1,000 (greedy ZigZag at
             the $1,000/mult price threshold)

over the VALID mids of the session-dominant instrument.  Windows: full session,
fixed-RTH [14:30, 21:00) UTC (comparability), and each frozen phase.  The
committed UTC-day convention is computed separately from the day receipts for
the one-time comparability delta.

Never spanning an instrument change (§7): every session series is slot 0 of the
session receipt = ONE instrument for the whole session; the other instrument's
time on a roll session appears as non-two-sided seconds and is simply absent
from the valid-mid series.  The UTC-day convention picks one dominant outright
per UTC day for the same reason.
"""
import datetime as dt
import multiprocessing as mp
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import census_common as X
import c_c_roster as CC          # zigzag_scan (shared confirmation core)

SECTION = "§7 c_b_offer"

PARAMS = {
    "spec_section": SECTION,
    "range": "(max(mid) - min(mid)) x mult over valid two-sided seconds",
    "best_leg": "max(max(m - cummin m), max(cummax m - m)) x mult",
    "legs": "disjoint monotonic legs >= $1,000 via a greedy ZigZag at "
            "$1,000/mult price units; the anchor is the window's first valid "
            "mid, legs are anchor->pivot and pivot->pivot, the trailing "
            "unconfirmed segment is not counted",
    "windows": list(X.WINDOWS),
    "rth": [C.RTH_LO_SEC, C.RTH_HI_SEC],
    "utc_day_convention": "day receipts; dominant = update-count winner among "
                          "OUTRIGHTS (program variant of the s1-pinned R1)",
    "offer_gate_measure": "best_leg (the directional, one-position capturable "
                          "offer); range reported beside it",
    "correlations": "Pearson + Spearman on date-intersected sessions, "
                    "pairwise-complete; returns are within-instrument "
                    "close-to-close, NaN on instrument_change",
    "splits": "all; ex_roll_week (NKD only)",
}

COLUMNS = ["asset", "trade_date", "year", "convention", "window",
           "n_valid_seconds", "range_usd", "best_leg_usd", "legs_1k",
           "close_px", "dominant_id", "roll_window", "dying_book_week",
           "instrument_change"]


# ------------------------------------------------------------------ core ----
def offer_measures(mids, secs, mult, leg_thr_px):
    """(range_$, best_leg_$, n_legs>=$1,000) over one contiguous valid series."""
    if mids.size == 0:
        return float("nan"), float("nan"), 0
    if mids.size == 1:
        return 0.0, 0.0, 0
    lo = np.minimum.accumulate(mids)
    hi = np.maximum.accumulate(mids)
    up = float((mids - lo).max())
    dn = float((hi - mids).max())
    rng = float(mids.max() - mids.min()) * mult
    best = max(up, dn) * mult
    return rng, best, count_legs(secs, mids, mult, leg_thr_px)


def count_legs(secs, mids, mult, thr_px):
    """Disjoint monotonic legs >= the threshold, greedy causal ZigZag."""
    sl = secs.tolist() if hasattr(secs, "tolist") else list(secs)
    ml = mids.tolist() if hasattr(mids, "tolist") else list(mids)
    if len(ml) < 2:
        return 0
    piv = CC.zigzag_scan(sl, ml, [thr_px] * len(ml))
    n = 0
    prev_px = ml[0]
    for (px, _psec, _csec, _side) in piv:
        if abs(px - prev_px) * mult >= X.LEG_1K:
            n += 1
        prev_px = px
    return n


# ---------------------------------------------------------------- workers ---
def _task_sessions(args):
    asset, sess = args
    mult = C.ASSETS[asset]["mult"]
    thr_px = X.LEG_1K / mult
    rows = []
    closes = []
    for trade_date, path in sess:
        s = X.load_session(asset, trade_date, path)
        close_px = float(s.vm[-1]) if s.vm.size else float("nan")
        closes.append((trade_date.isoformat(), close_px, s.instrument_change,
                       s.iid))
        for w in X.WINDOWS:
            wm = X.window_mask(s, w) & s.valid
            idx = np.nonzero(wm)[0]
            m = s.mid[idx]
            rng, best, legs = offer_measures(m, idx, mult, thr_px)
            rows.append([asset, trade_date.isoformat(), trade_date.year,
                         "SESSION", w, int(idx.size), rng, best, legs,
                         close_px, s.iid, s.roll_window, s.dying_book_week,
                         s.instrument_change])
    return rows, closes


def _task_days(args):
    asset, days = args
    mult = C.ASSETS[asset]["mult"]
    thr_px = X.LEG_1K / mult
    rows = []
    for date, path in days:
        iid, mid, flag = X.load_day_dominant(asset, path)
        if iid is None:
            continue
        valid = np.isfinite(mid)
        for w in ("FULL", "RTH"):
            if w == "FULL":
                wm = valid
            else:
                sod = np.arange(86400)
                wm = valid & (sod >= C.RTH_LO_SEC) & (sod < C.RTH_HI_SEC)
            idx = np.nonzero(wm)[0]
            rng, best, legs = offer_measures(mid[idx], idx, mult, thr_px)
            rows.append([asset, date.isoformat(), date.year, "UTC_DAY", w,
                         int(idx.size), rng, best, legs,
                         (float(mid[idx][-1]) if idx.size else float("nan")),
                         iid, None, None, None])
    return rows


# ------------------------------------------------------------------- main ---
def run(assets=C.ASSET_ORDER, root=None, out_root=None, months=None, workers=10):
    root = root or C.OUT_ROOT
    out_root = out_root or C.OUT_ROOT
    phash = C.params_hash(PARAMS)

    stasks, dtasks = [], []
    for asset in assets:
        bm = {}
        for d, p in X.session_paths(asset, root):
            if months and X.month_key(d) not in months:
                continue
            bm.setdefault(X.month_key(d), []).append((d, p))
        for mk in sorted(bm):
            stasks.append((asset, bm[mk]))
        bd = {}
        for d, p in X.day_paths(asset, root):
            if months and X.month_key(d) not in months:
                continue
            bd.setdefault(X.month_key(d), []).append((d, p))
        for mk in sorted(bd):
            dtasks.append((asset, bd[mk]))
    C.hb("c_b: %d session tasks, %d utc-day tasks" % (len(stasks), len(dtasks)))

    if workers <= 1:
        sres = [_task_sessions(t) for t in stasks]
        dres = [_task_days(t) for t in dtasks]
    else:
        with mp.Pool(min(workers, max(len(stasks), 1))) as pool:
            sres = list(pool.map(_task_sessions, stasks, chunksize=1))
        with mp.Pool(min(workers, max(len(dtasks), 1))) as pool:
            dres = list(pool.map(_task_days, dtasks, chunksize=1))

    rows = []
    closes = {}
    for (asset, _s), (r, cl) in zip(stasks, sres):
        rows.extend(r)
        for iso, px, ic, iid in cl:
            closes[(asset, iso)] = (px, ic, iid)
    for r in dres:
        rows.extend(r)
    rows.sort(key=lambda r: (r[0], r[3], r[1], X.WINDOWS.index(r[4])))
    X.write_tsv(X.out_path(out_root, "census_b_offer.tsv"), SECTION, phash,
                COLUMNS, rows,
                extra=["convention SESSION = Globex trade date (§5); "
                       "convention UTC_DAY = the committed §3 windowing, "
                       "emitted only for the comparability delta"])

    rollup = _rollup(assets, rows)
    X.write_tsv(X.out_path(out_root, "census_b_rollup.tsv"), SECTION, phash,
                ["asset", "convention", "window", "era", "split", "measure",
                 "n_sessions", "mean", "median", "p25", "p75",
                 "gate_median_ge_2500"], rollup,
                extra=["offer floor gate (§1) = median full-session best_leg "
                       ">= $%.0f; the range row is the companion"
                       % X.GATE_OFFER_FLOOR])

    corr = _correlations(assets, rows, closes)
    X.write_tsv(X.out_path(out_root, "census_b_correlations.tsv"), SECTION,
                phash,
                ["pair", "series", "n", "pearson", "spearman"], corr,
                extra=["date-intersected sessions, pairwise-complete; SI starts "
                       "2021-05-31"])
    C.hb("c_b: %d offer rows, %d rollup rows, %d correlation rows"
         % (len(rows), len(rollup), len(corr)))
    return rows, rollup, corr


def _rollup(assets, rows):
    agg = {}
    for r in rows:
        asset, conv, window, year = r[0], r[3], r[4], int(r[2])
        splits = ["all"]
        if asset == "NKD" and conv == "SESSION" and not r[12]:
            splits.append("ex_roll_week")
        for era in X.eras_of(year):
            for split in splits:
                for mi, measure in ((6, "range"), (7, "best_leg"), (8, "legs_1k")):
                    a = agg.setdefault((asset, conv, window, era, split, measure), [])
                    a.append(float(r[mi]) if r[mi] is not None else float("nan"))
    out = []
    for k in sorted(agg):
        v = agg[k]
        m = X.med(v)
        gate = ""
        if (k[1] == "SESSION" and k[2] == "FULL" and k[5] in ("best_leg", "range")):
            gate = "PASS" if (np.isfinite(m) and m >= X.GATE_OFFER_FLOOR) else "FAIL"
        out.append([k[0], k[1], k[2], k[3], k[4], k[5], len(v), X.mean(v), m,
                    X.pct(v, 25), X.pct(v, 75), gate])
    return out


def _correlations(assets, rows, closes):
    # daily full-session best_leg per asset
    off = {}
    for r in rows:
        if r[3] != "SESSION" or r[4] != "FULL":
            continue
        off.setdefault(r[0], {})[r[1]] = float(r[7])
    # within-instrument close-to-close returns
    ret = {}
    for asset in assets:
        dates = sorted(d for (a, d) in closes if a == asset)
        prev = None
        for d in dates:
            px, ic, iid = closes[(asset, d)]
            v = float("nan")
            if prev is not None and not ic and np.isfinite(px) \
                    and np.isfinite(prev[0]) and prev[0] != 0 and iid == prev[1]:
                v = (px - prev[0]) / prev[0]
            ret.setdefault(asset, {})[d] = v
            prev = (px, iid)
    out = []
    al = [a for a in assets]
    for i in range(len(al)):
        for j in range(i + 1, len(al)):
            a, b = al[i], al[j]
            for name, src in (("best_leg_full_session", off), ("close_to_close_return", ret)):
                da = src.get(a, {})
                db = src.get(b, {})
                common = sorted(set(da) & set(db))
                if not common:
                    out.append(["%s-%s" % (a, b), name, 0, float("nan"),
                                float("nan")])
                    continue
                xa = np.array([da[d] for d in common], dtype=np.float64)
                xb = np.array([db[d] for d in common], dtype=np.float64)
                pr, n = X.pearson(xa, xb)
                sp, _ = X.spearman(xa, xb)
                out.append(["%s-%s" % (a, b), name, n, pr, sp])
    return out


def main():
    X.verify_spec()
    run(assets=sys.argv[1:] or list(C.ASSET_ORDER))
    return 0


if __name__ == "__main__":
    sys.exit(main())
