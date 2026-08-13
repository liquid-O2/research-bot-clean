#!/usr/bin/python3
"""PORT M0 c_c_roster_dp — spec §8, three sub-passes.

SUB-PASS 1  G1 roster + certificate skeletons   (parallel by (asset, month))
SUB-PASS 2  wall fit                            (pooled 2021-2024 winners)
SUB-PASS 3  walled certificates + one-position DP per session (skeleton queries)

The path skeleton is what makes sub-pass 1 answerable for a wall that is only
known after sub-pass 2: per candidate we store the PREFIX-MAXIMA SEQUENCES of
the favorable series f(t) and the adverse series a(t) = -f(t) — every (t, value)
at which the running maximum strictly improves.  For ANY wall W:

    t_wall(W)          = t of the first a-record with value >= W       (exact)
    MFE before t_wall  = value of the last f-record with t < t_wall     (exact)
    argmax of that MFE = t of that same f-record                        (exact)
    MAE before argmax  = value of the last a-record with t <= argmax    (exact)

which is precisely §8's "landmark arrays sufficient to answer MFE/MAE/t_wall for
ANY wall".  The horizon marks {30m, 60m, 120m, phase-close, session-close} are
stored as plain f values because they are wall-independent clocks known in
sub-pass 1; sub-pass 3's phase-close variant needs f AT a clock, which prefix
maxima cannot supply.
"""
import json
import multiprocessing as mp
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import census_common as X
import c_a_cost as CA

SECTION = "§8 c_c_roster_dp"

PARAMS = {
    "spec_section": SECTION,
    "rungs": list(X.RUNGS),
    "threshold": "round_half_up_to_tick(max(rung x ATR14_{d-1}($), "
                 "4 x tick_$, 2 x phase_median_spread_$(phase of the "
                 "confirmation second)) / mult)",
    "phase_median_source": "c_a census_a_cost_rollup.tsv "
                           "spread_med_usd_pooled (asset, year, phase)",
    "atr_source": "bars_{ASSET}.tsv ATR14_prev_usd (causal: session d uses "
                  "ATR14 through d-1)",
    "decision_lag_sec": X.DECISION_LAG,
    "dedup": "same (session, confirmation_sec, side) across rungs -> ONE "
             "candidate, rung_tags = union",
    "skip_reasons": {"PAST_CLOSE": 0, "NOT_TWO_SIDED": 1},
    "skeleton": "prefix-maxima sequences of f and a (strict improvements, "
                "positive only) + horizon marks",
    "horizons_sec": list(X.HORIZON_MARKS),
    "wall": "min(round_half_up_$25(pooled p99 of winners' MAE-before-peak, "
            "2021-2024), $900); winners = unwalled MFE >= $1,000",
    "cost_rt_subpass3": "session-scoped median two-sided spread + $5.00",
    "dp": "one-position weighted interval scheduling, values > 0 only; a new "
          "position may start strictly after the previous exit second; §1 "
          "tie-breaks: earlier decision-second first, then higher value, then "
          "lower instrument_id",
    "clock": "ts_event, session seconds",
}

RUNG_BITS = tuple(1 << i for i in range(len(X.RUNGS)))
SKIP_PAST_CLOSE = 0
SKIP_NOT_TWO_SIDED = 1

ROSTER_KEYS = ("date8", "side", "rung_mask", "conf_sec", "dec_sec",
               "phase_conf", "phase_dec", "entry_mid", "spread_at_decision",
               "atr14_usd", "dom_share", "iid", "mfe_unwalled",
               "mfe_argmax_sec", "mae_before_argmax", "f_h30", "f_h60",
               "f_h120", "f_phase_close", "f_sess_close", "phase_close_sec",
               "sess_close_sec", "f_off", "f_len", "a_off", "a_len")


# ===================================================== the ZigZag (§8 s-p 1) ==
def zigzag_scan(secs, mids, thr):
    """Causal ZigZag confirmation scan.

    secs  : ascending session seconds of the VALID (two-sided) mids
    mids  : the mids at those seconds, price units
    thr   : per-second confirmation threshold in price units, same length
            (the threshold may vary by phase; the test at second t uses thr[t],
            so a confirmation second is always evaluated under ITS OWN phase's
            threshold — the self-consistent reading of §8's
            "phase of confirmation_sec")

    Returns a list of confirmed pivots in chronological order:
        (pivot_price, pivot_sec, confirmation_sec, side)
    side = +1 for a confirmed LOW  (new direction up   -> LONG candidate)
    side = -1 for a confirmed HIGH (new direction down -> SHORT candidate)

    The extreme-so-far keeps the FIRST second at which it was reached, and the
    confirmation second is the FIRST second at which the retrace from that
    extreme reaches the threshold (>=, not >).
    """
    out = []
    n = len(secs)
    if n < 2:
        return out
    hi = lo = mids[0]
    hi_s = lo_s = secs[0]
    d = 0
    for i in range(1, n):
        m = mids[i]
        s = secs[i]
        t = thr[i]
        if d == 1:
            if m > hi:
                hi = m
                hi_s = s
            elif (hi - m) >= t:
                out.append((hi, hi_s, s, -1))
                d = -1
                lo = m
                lo_s = s
        elif d == -1:
            if m < lo:
                lo = m
                lo_s = s
            elif (m - lo) >= t:
                out.append((lo, lo_s, s, 1))
                d = 1
                hi = m
                hi_s = s
        else:
            if m > hi:
                hi = m
                hi_s = s
            if m < lo:
                lo = m
                lo_s = s
            dn = (hi - m) >= t
            up = (m - lo) >= t
            if dn and up:
                # unreachable under a constant threshold; deterministic anyway:
                # the extreme that formed EARLIER is confirmed first, HIGH on a tie
                if hi_s <= lo_s:
                    up = False
                else:
                    dn = False
            if dn:
                out.append((hi, hi_s, s, -1))
                d = -1
                lo = m
                lo_s = s
            elif up:
                out.append((lo, lo_s, s, 1))
                d = 1
                hi = m
                hi_s = s
    return out


# ================================================ sub-pass 1: roster shard ===
def _shard(args):
    asset, month, sess, phase_med, root = args
    spec = C.ASSETS[asset]
    mult = spec["mult"]
    tick_usd = spec["tick_usd"]
    tick_px = spec["tick_px"]
    bars = X.load_bars(asset, root)

    cols = {k: [] for k in ROSTER_KEYS}
    f_t, f_v, a_t, a_v = [], [], [], []
    skips = []
    per_session = []
    n_no_atr = 0

    for trade_date, path in sess:
        s = X.load_session(asset, trade_date, path)
        bar = bars.get(trade_date)
        atr = bar["ATR14_prev_usd"] if bar else float("nan")
        if not np.isfinite(atr):
            n_no_atr += 1
            per_session.append((trade_date.isoformat(), 0, 0, 0, 0, 0, 0,
                                "NO_ATR14"))
            continue
        if s.vt.size < 2:
            per_session.append((trade_date.isoformat(), 0, 0, 0, 0, 0, 0,
                                "NO_VALID_MIDS"))
            continue

        vt = s.vt
        vm = s.vm
        vt_l = vt.tolist()
        vm_l = vm.tolist()
        vphase = s.phase_tag[vt].tolist()

        # per-phase thresholds for each rung (price units, HALF-UP to the tick)
        rung_thr = []
        for r in X.RUNGS:
            per_phase = []
            for p in range(X.N_PHASES):
                pm = phase_med.get((asset, trade_date.year, X.PHASE_NAMES[p]),
                                   float("nan"))
                floor_spread = (X.RUNG_FLOOR_SPREAD_MULT * pm
                                if np.isfinite(pm) else 0.0)
                usd = max(r * atr, X.RUNG_FLOOR_TICKS * tick_usd, floor_spread)
                per_phase.append(X.round_half_up(usd / mult, tick_px))
            rung_thr.append(per_phase)

        # ---- confirmations per rung, deduped by (confirmation_sec, side) -----
        merged = {}
        rung_counts = [0] * len(X.RUNGS)
        for ri, per_phase in enumerate(rung_thr):
            thr_l = [per_phase[p] for p in vphase]
            piv = zigzag_scan(vt_l, vm_l, thr_l)
            rung_counts[ri] = len(piv)
            for (_px, _psec, conf_sec, side) in piv:
                k = (conf_sec, side)
                cur = merged.get(k)
                if cur is None:
                    merged[k] = RUNG_BITS[ri]
                else:
                    merged[k] = cur | RUNG_BITS[ri]

        n_skip_close = 0
        n_skip_state = 0
        n_cand = 0
        for (conf_sec, side) in sorted(merged):
            mask = merged[(conf_sec, side)]
            dec_sec = conf_sec + X.DECISION_LAG
            if dec_sec >= s.n:
                n_skip_close += 1
                skips.append((int(_d8(trade_date)), conf_sec, dec_sec, side,
                              SKIP_PAST_CLOSE, mask))
                continue
            if s.state[dec_sec] != C.ST_TWO_SIDED:
                n_skip_state += 1
                skips.append((int(_d8(trade_date)), conf_sec, dec_sec, side,
                              SKIP_NOT_TWO_SIDED, mask))
                continue
            n_cand += 1
            _emit_candidate(cols, f_t, f_v, a_t, a_v, s, trade_date, asset,
                            mult, side, mask, conf_sec, dec_sec, atr)
        per_session.append((trade_date.isoformat(), n_cand, n_skip_close,
                            n_skip_state, rung_counts[0], rung_counts[1],
                            rung_counts[2], ""))

    arrays = {}
    dtypes = {"date8": np.int32, "side": np.int8, "rung_mask": np.uint8,
              "conf_sec": np.int32, "dec_sec": np.int32, "phase_conf": np.int8,
              "phase_dec": np.int8, "mfe_argmax_sec": np.int32,
              "phase_close_sec": np.int32, "sess_close_sec": np.int32,
              "iid": np.int64, "f_off": np.int64, "f_len": np.int64,
              "a_off": np.int64, "a_len": np.int64}
    for k in ROSTER_KEYS:
        arrays[k] = np.array(cols[k], dtype=dtypes.get(k, np.float64))
    arrays["skel_f_t"] = np.array(f_t, dtype=np.int32)
    arrays["skel_f_v"] = np.array(f_v, dtype=np.float32)
    arrays["skel_a_t"] = np.array(a_t, dtype=np.int32)
    arrays["skel_a_v"] = np.array(a_v, dtype=np.float32)
    sk = np.array(skips, dtype=np.int64) if skips else np.zeros((0, 6), np.int64)
    arrays["skips"] = sk
    return asset, month, arrays, per_session, n_no_atr


def _d8(d):
    return d.year * 10000 + d.month * 100 + d.day


def _emit_candidate(cols, f_t, f_v, a_t, a_v, s, trade_date, asset, mult,
                    side, mask, conf_sec, dec_sec, atr):
    entry = float(s.mid[dec_sec])
    j0 = int(np.searchsorted(s.vt, dec_sec, side="left"))
    vt = s.vt[j0:]
    f = (s.vm[j0:] - entry) * side * mult

    run_f = np.maximum.accumulate(f)
    run_a = np.maximum.accumulate(-f)
    nf = np.empty(run_f.size, dtype=bool)
    na = np.empty(run_a.size, dtype=bool)
    nf[0] = False                     # f(dec_sec) == 0 is never a positive record
    na[0] = False
    if run_f.size > 1:
        nf[1:] = run_f[1:] > run_f[:-1]
        na[1:] = run_a[1:] > run_a[:-1]
    ft = vt[nf]
    fv = run_f[nf]
    at = vt[na]
    av = run_a[na]

    mfe = float(fv[-1]) if fv.size else 0.0
    argmax_sec = int(ft[-1]) if ft.size else int(dec_sec)
    if av.size:
        w = np.searchsorted(at, argmax_sec, side="right")
        mae_before = float(av[w - 1]) if w > 0 else 0.0
    else:
        mae_before = 0.0

    pc_sec = X.next_phase_boundary(s, dec_sec)
    sc_sec = s.n - 1
    marks = [dec_sec + h for h in X.HORIZON_MARKS] + [pc_sec, sc_sec]
    fm = []
    for mk in marks:
        if mk >= s.n:
            fm.append(float("nan"))
            continue
        j = int(np.searchsorted(vt, mk, side="right")) - 1
        fm.append(float(f[j]) if j >= 0 else float("nan"))

    cols["date8"].append(_d8(trade_date))
    cols["side"].append(side)
    cols["rung_mask"].append(mask)
    cols["conf_sec"].append(conf_sec)
    cols["dec_sec"].append(dec_sec)
    cols["phase_conf"].append(int(s.phase_tag[conf_sec]))
    cols["phase_dec"].append(int(s.phase_tag[dec_sec]))
    cols["entry_mid"].append(entry)
    cols["spread_at_decision"].append(float(s.spread_usd[dec_sec]))
    cols["atr14_usd"].append(float(atr))
    cols["dom_share"].append(s.dominant_share)
    cols["iid"].append(s.iid)
    cols["mfe_unwalled"].append(mfe)
    cols["mfe_argmax_sec"].append(argmax_sec)
    cols["mae_before_argmax"].append(mae_before)
    cols["f_h30"].append(fm[0])
    cols["f_h60"].append(fm[1])
    cols["f_h120"].append(fm[2])
    cols["f_phase_close"].append(fm[3])
    cols["f_sess_close"].append(fm[4])
    cols["phase_close_sec"].append(pc_sec)
    cols["sess_close_sec"].append(sc_sec)
    cols["f_off"].append(len(f_t))
    cols["f_len"].append(int(ft.size))
    cols["a_off"].append(len(a_t))
    cols["a_len"].append(int(at.size))
    f_t.extend(ft.tolist())
    f_v.extend(fv.tolist())
    a_t.extend(at.tolist())
    a_v.extend(av.tolist())


def subpass1(assets, root, out_root, months, workers, phase_med):
    tasks = []
    for asset in assets:
        by_month = {}
        for d, p in X.session_paths(asset, root):
            if months and X.month_key(d) not in months:
                continue
            by_month.setdefault(X.month_key(d), []).append((d, p))
        for mk in sorted(by_month):
            tasks.append((asset, mk, by_month[mk], phase_med, root))
    C.hb("c_c sub-pass 1: %d (asset,month) tasks" % len(tasks))
    if workers <= 1 or len(tasks) <= 1:
        results = [_shard(t) for t in tasks]
    else:
        with mp.Pool(min(workers, len(tasks))) as pool:
            results = list(pool.map(_shard, tasks, chunksize=1))

    phash = C.params_hash(PARAMS)
    summary_rows = []
    for asset in assets:
        parts = [(m, arr, ps, na) for (a, m, arr, ps, na) in results if a == asset]
        parts.sort(key=lambda t: t[0])
        merged = _merge_shards(parts)
        C.savez_det(X.out_path(out_root, "roster_%s.npz" % asset), **merged)
        n_no_atr = sum(p[3] for p in parts)
        for m, _arr, ps, _na in parts:
            for row in ps:
                summary_rows.append([asset, row[0], row[1], row[2], row[3],
                                     row[4], row[5], row[6], row[7]])
        C.hb("c_c sub-pass 1 %s: %d candidates, %d skips, %d sessions w/o ATR14"
             % (asset, len(merged["date8"]), len(merged["skips"]), n_no_atr))
    summary_rows.sort(key=lambda r: (r[0], r[1]))
    X.write_tsv(X.out_path(out_root, "census_c_roster_summary.tsv"), SECTION,
                phash,
                ["asset", "trade_date", "n_candidates", "n_skip_past_close",
                 "n_skip_not_two_sided", "n_pivots_r075", "n_pivots_r11",
                 "n_pivots_r15", "note"], summary_rows)
    return summary_rows


def _merge_shards(parts):
    out = {}
    keys = [k for k in ROSTER_KEYS]
    for k in keys:
        out[k] = np.concatenate([p[1][k] for p in parts]) if parts else np.array([])
    # skeleton offsets must be rebased as shards concatenate
    f_off = []
    a_off = []
    fbase = 0
    abase = 0
    for p in parts:
        f_off.append(p[1]["f_off"] + fbase)
        a_off.append(p[1]["a_off"] + abase)
        fbase += int(p[1]["skel_f_t"].size)
        abase += int(p[1]["skel_a_t"].size)
    out["f_off"] = np.concatenate(f_off) if f_off else np.array([], np.int64)
    out["a_off"] = np.concatenate(a_off) if a_off else np.array([], np.int64)
    for k in ("skel_f_t", "skel_f_v", "skel_a_t", "skel_a_v"):
        out[k] = (np.concatenate([p[1][k] for p in parts]) if parts
                  else np.array([]))
    sk = [p[1]["skips"] for p in parts if p[1]["skips"].size]
    out["skips"] = np.concatenate(sk) if sk else np.zeros((0, 6), np.int64)
    return out


def load_roster(asset, out_root=None):
    out_root = out_root or C.OUT_ROOT
    z = np.load(os.path.join(out_root, "roster_%s.npz" % asset),
                allow_pickle=False)
    r = {k: z[k] for k in z.files}
    z.close()
    return r


# =================================================== sub-pass 2: wall fit ====
def subpass2(assets, out_root):
    walls = {}
    rows = []
    for asset in assets:
        r = load_roster(asset, out_root)
        year = (r["date8"] // 10000).astype(np.int64)
        win = r["mfe_unwalled"] >= X.WINNER_MFE
        per_year = {}
        for y in sorted(set(year.tolist())):
            sel = win & (year == y)
            per_year[int(y)] = (int(sel.sum()),
                                X.pct(r["mae_before_argmax"][sel], 95),
                                X.pct(r["mae_before_argmax"][sel], 99))
        fit = win & np.isin(year, np.array(X.WALL_FIT_YEARS))
        mae = r["mae_before_argmax"][fit]
        p95 = X.pct(mae, 95)
        p99 = X.pct(mae, 99)
        wall = min(X.round_half_up(p99, X.WALL_ROUND), X.WALL_CAP) if np.isfinite(p99) \
            else X.WALL_CAP
        walls[asset] = {
            "wall_usd": float(wall),
            "pooled_p95": p95, "pooled_p99": p99,
            "pooled_p99_rounded_25": (X.round_half_up(p99, X.WALL_ROUND)
                                      if np.isfinite(p99) else None),
            "n_winners_fit": int(fit.sum()),
            "n_candidates": int(r["date8"].size),
            "fit_years": list(X.WALL_FIT_YEARS),
            "per_year": {str(k): {"n_winners": v[0], "p95": v[1], "p99": v[2]}
                         for k, v in sorted(per_year.items())},
        }
        for y, v in sorted(per_year.items()):
            rows.append([asset, y, v[0], v[1], v[2],
                         "" if y not in X.WALL_FIT_YEARS else "FIT"])
        rows.append([asset, "POOLED_%d_%d" % (X.WALL_FIT_YEARS[0],
                                              X.WALL_FIT_YEARS[-1]),
                     int(fit.sum()), p95, p99, "WALL=%.2f" % wall])
        C.hb("c_c sub-pass 2 %s: %d winners, p99=%.2f -> wall $%.2f"
             % (asset, int(fit.sum()), p99 if np.isfinite(p99) else -1, wall))
    C.write_json(X.out_path(out_root, "walls.json"),
                 {"spec_section": "§8 sub-pass 2 / §1 wall",
                  "env": C.env_receipt(PARAMS), "walls": walls})
    X.write_tsv(X.out_path(out_root, "census_c_wall_stability.tsv"), SECTION,
                C.params_hash(PARAMS),
                ["asset", "year", "n_winners", "mae_before_peak_p95",
                 "mae_before_peak_p99", "note"], rows,
                extra=["winners = unwalled MFE >= $%.0f; 2025 excluded from the "
                       "fit (§8 sub-pass 2)" % X.WINNER_MFE])
    return walls


# ============================== sub-pass 3: walled certificates + the DP ======
def _skel_query(r, i, W):
    """Answer (t_wall, mfe_before_wall, argmax_sec, walled) for candidate i."""
    fo, fl = int(r["f_off"][i]), int(r["f_len"][i])
    ao, al = int(r["a_off"][i]), int(r["a_len"][i])
    t_wall = None
    if al:
        av = r["skel_a_v"][ao:ao + al]
        w = int(np.searchsorted(av, W, side="left"))
        if w < al:
            t_wall = int(r["skel_a_t"][ao + w])
    if fl == 0:
        return t_wall, 0.0, int(r["dec_sec"][i]), (t_wall is not None)
    ft = r["skel_f_t"][fo:fo + fl]
    fv = r["skel_f_v"][fo:fo + fl]
    if t_wall is None:
        return None, float(fv[-1]), int(ft[-1]), False
    j = int(np.searchsorted(ft, t_wall, side="left"))     # records with t < t_wall
    if j == 0:
        return t_wall, 0.0, int(r["dec_sec"][i]), True
    return t_wall, float(fv[j - 1]), int(ft[j - 1]), True


def certificates(r, i, W, cost_rt):
    """(peak-exit, phase-close) certificates for candidate i (§8 sub-pass 3)."""
    dec = int(r["dec_sec"][i])
    t_wall, mfe_w, argmax_sec, _ = _skel_query(r, i, W)
    if t_wall is not None and mfe_w <= 0.0:
        peak = (-W - cost_rt, dec, dec, False)            # never seated
    else:
        peak = (mfe_w - cost_rt, dec, argmax_sec, True)

    pc = int(r["phase_close_sec"][i])
    if t_wall is not None and t_wall <= pc:
        val_c = -W - cost_rt
        exit_sec = t_wall
    else:
        f_pc = float(r["f_phase_close"][i])
        if not np.isfinite(f_pc):
            f_pc = float(r["f_sess_close"][i])
        val_c = (f_pc if np.isfinite(f_pc) else 0.0) - cost_rt
        exit_sec = pc
    close = (val_c, dec, exit_sec, True)
    return peak, close


def dp_schedule(items):
    """One-position weighted interval scheduling (§8 sub-pass 3, §1 tie-breaks).

    items: list of (start_sec, end_sec, value, decision_sec, iid, ident).
           Only values > 0 are scheduled; a new position may start STRICTLY
           after the previous position's exit second.

    Returns (total_value, [ident, ...] in chronological order).  Ties in total
    value are broken by the §1 order: the schedule whose (decision_sec, -value,
    iid) sequence is lexicographically smallest wins — i.e. earlier decision
    second first, then higher value, then lower instrument_id.
    """
    items = [it for it in items if it[2] > 0]
    items.sort(key=lambda it: (it[1], it[0], it[3], -it[2], it[4], it[5]))
    n = len(items)
    if n == 0:
        return 0.0, []
    ends = [it[1] for it in items]
    # p[i] = index of the last item that ends strictly before items[i] starts
    p = []
    for i in range(n):
        s = items[i][0]
        lo, hi = 0, i
        while lo < hi:
            mid = (lo + hi) // 2
            if ends[mid] < s:
                lo = mid + 1
            else:
                hi = mid
        p.append(lo - 1)

    best = [(0.0, ())] * (n + 1)          # (total, tie-key tuple)
    pick = [None] * (n + 1)
    for i in range(1, n + 1):
        it = items[i - 1]
        prev_total, prev_key = best[p[i - 1] + 1]
        take_total = prev_total + it[2]
        take_key = prev_key + ((it[3], -it[2], it[4]),)
        skip_total, skip_key = best[i - 1]
        if _better((take_total, take_key), (skip_total, skip_key)):
            best[i] = (take_total, take_key)
            pick[i] = i - 1
        else:
            best[i] = (skip_total, skip_key)
            pick[i] = None

    chosen = []
    i = n
    while i > 0:
        if pick[i] is not None:
            chosen.append(items[i - 1][5])
            i = p[i - 1] + 1
        else:
            i -= 1
    chosen.reverse()
    return best[n][0], chosen


def _better(a, b):
    """True when solution a beats b: higher total, then §1 lexicographic key."""
    if a[0] != b[0]:
        return a[0] > b[0]
    return a[1] < b[1]


def subpass3(assets, out_root, walls, cost_map, flags):
    phash = C.params_hash(PARAMS)
    rows = []
    phase_value = {}
    for asset in assets:
        r = load_roster(asset, out_root)
        W = float(walls[asset]["wall_usd"])
        date8 = r["date8"]
        order = np.argsort(date8, kind="stable")
        uniq = sorted(set(date8.tolist()))
        by_date = {}
        for i in order.tolist():
            by_date.setdefault(int(date8[i]), []).append(i)
        for d8 in uniq:
            iso = "%04d-%02d-%02d" % (d8 // 10000, (d8 // 100) % 100, d8 % 100)
            cost_rt = cost_map.get((asset, iso), float("nan"))
            if not np.isfinite(cost_rt):
                cost_rt = C.FEES_RT
            idx = by_date[d8]
            peak_items, close_items = [], []
            n_1k = 0
            for i in idx:
                if float(r["mfe_unwalled"][i]) - cost_rt >= X.LEG_1K:
                    n_1k += 1
                pk, cl = certificates(r, i, W, cost_rt)
                peak_items.append((pk[1], pk[2], pk[0], int(r["dec_sec"][i]),
                                   int(r["iid"][i]), i))
                close_items.append((cl[1], cl[2], cl[0], int(r["dec_sec"][i]),
                                    int(r["iid"][i]), i))
            tp, sel_p = dp_schedule(peak_items)
            tc, sel_c = dp_schedule(close_items)
            sp, sc = set(sel_p), set(sel_c)
            vals_p = [it[2] for it in peak_items if it[5] in sp]
            vals_c = [it[2] for it in close_items if it[5] in sc]
            ph_c = [0.0] * X.N_PHASES
            for it in close_items:
                if it[5] in sc:
                    ph_c[int(r["phase_dec"][it[5]])] += it[2]
            year = d8 // 10000
            dbw = flags.get((asset, iso), {}).get("dying_book_week", False)
            for era in X.eras_of(year):
                for p in range(X.N_PHASES):
                    k = (asset, X.PHASE_NAMES[p], era)
                    phase_value[k] = phase_value.get(k, 0.0) + ph_c[p]
            rows.append([asset, iso, year, len(idx), n_1k, cost_rt, W,
                         tp, len(sel_p), (X.mean(vals_p) if vals_p else float("nan")),
                         tc, len(sel_c), (X.mean(vals_c) if vals_c else float("nan")),
                         ph_c[0], ph_c[1], ph_c[2], dbw])
        C.hb("c_c sub-pass 3 %s: %d sessions certified (wall $%.0f)"
             % (asset, len(uniq), W))

    X.write_tsv(X.out_path(out_root, "census_c_seatable.tsv"), SECTION, phash,
                ["asset", "trade_date", "year", "n_candidates", "n_1k_class",
                 "cost_rt_session", "wall_usd",
                 "seatable_peak_usd", "n_seated_peak", "seated_mean_peak_usd",
                 "seatable_close_usd", "n_seated_close", "seated_mean_close_usd",
                 "seated_close_TOKYO", "seated_close_LONDON", "seated_close_NY",
                 "dying_book_week"],
                rows,
                extra=["$1k-class = unwalled MFE - session cost_rt >= $%.0f "
                       "(the throughput number)" % X.LEG_1K])

    rollup = _rollup3(assets, rows)
    X.write_tsv(X.out_path(out_root, "census_c_rollup.tsv"), SECTION, phash,
                ["asset", "era", "split", "n_sessions",
                 "seatable_peak_median", "seatable_peak_mean",
                 "seatable_close_median", "seatable_close_mean",
                 "gate_seatable_close_median_ge_2500",
                 "candidates_per_day_median", "one_k_class_per_day_median",
                 "seated_per_trade_mean_close", "seated_per_trade_mean_peak",
                 "n_seated_per_day_median_close"], rollup,
                extra=["seatable floor gate = median >= $%.0f (§1)"
                       % X.GATE_SEATABLE_FLOOR])

    pv = []
    for k in sorted(phase_value):
        pv.append([k[0], k[1], k[2], phase_value[k]])
    tot = {}
    for k in sorted(phase_value):
        tot[(k[0], k[2])] = tot.get((k[0], k[2]), 0.0) + max(phase_value[k], 0.0)
    pv2 = []
    for row in pv:
        t = tot.get((row[0], row[2]), 0.0)
        pv2.append(row + [(max(row[3], 0.0) / t) if t > 0 else float("nan")])
    X.write_tsv(X.out_path(out_root, "census_c_phase_value.tsv"), SECTION, phash,
                ["asset", "phase", "era", "seated_close_usd", "share"], pv2,
                extra=["phase-close DP seated value attributed to the phase of "
                       "the decision second; s5 takes the smallest phase set "
                       "reaching >=80% share"])
    return rows, rollup


def _rollup3(assets, rows):
    agg = {}
    for r in rows:
        asset, year = r[0], int(r[2])
        splits = ["all"]
        if asset == "NKD" and not r[16]:      # r[16] = dying_book_week
            splits.append("ex_roll_week")
        for era in X.eras_of(year):
            for split in splits:
                a = agg.setdefault((asset, era, split),
                                   {"p": [], "c": [], "nc": [], "k": [],
                                    "sp": [], "sc": [], "ns": []})
                a["p"].append(r[7])
                a["c"].append(r[10])
                a["nc"].append(r[3])
                a["k"].append(r[4])
                a["sp"].append(r[9])
                a["sc"].append(r[12])
                a["ns"].append(r[11])
    out = []
    for k in sorted(agg):
        a = agg[k]
        cm = X.med(a["c"])
        out.append([k[0], k[1], k[2], len(a["p"]),
                    X.med(a["p"]), X.mean(a["p"]), cm, X.mean(a["c"]),
                    ("PASS" if (np.isfinite(cm) and cm >= X.GATE_SEATABLE_FLOOR)
                     else "FAIL"),
                    X.med(a["nc"]), X.med(a["k"]),
                    X.mean(a["sc"]), X.mean(a["sp"]), X.med(a["ns"])])
    return out


# -------------------------------------------------------------------- main --
def run(assets=C.ASSET_ORDER, root=None, out_root=None, months=None,
        workers=10, walls=None):
    root = root or C.OUT_ROOT
    out_root = out_root or C.OUT_ROOT
    phase_med = CA.phase_median_spreads(out_root)
    subpass1(assets, root, out_root, months, workers, phase_med)
    w = walls if walls is not None else subpass2(assets, out_root)
    if walls is not None:
        C.write_json(X.out_path(out_root, "walls.json"),
                     {"spec_section": "§8 sub-pass 2 / §1 wall (pinned)",
                      "env": C.env_receipt(PARAMS), "walls": w})
    cost_map = CA.session_cost_rt(out_root)
    flags = CA.session_flags(out_root)
    return subpass3(assets, out_root, w, cost_map, flags)


def main():
    X.verify_spec()
    run(assets=sys.argv[1:] or list(C.ASSET_ORDER))
    return 0


if __name__ == "__main__":
    sys.exit(main())
