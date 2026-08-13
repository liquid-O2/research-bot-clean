#!/usr/bin/python3
"""PORT M2 — the 14 section renderers (design/PORT_M2_SHEETS_SPEC.md §1).

One function per section, each returning a list of already-formatted lines and
recording every number it prints into the sidecar through `put`.

Causality is not a convention here, it is a call: every session-clock read goes
through Case.guard.sec / Case.guard.at_decision, every wall-clock read through
AvailSeries.latest(guard).  A section that needs a datum it cannot lawfully see
prints the typed-missing glyph and says WHY — it never prints a zero.
"""
import bisect
import datetime as dt
import math
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import common as C                        # noqa: E402
import census_common as X                 # noqa: E402
import c_a_cost as CA                     # noqa: E402
import c_c_roster as CC                   # noqa: E402
import b1_decay as B1                     # noqa: E402
import b3_levels as B3                    # noqa: E402
import assemble as A                      # noqa: E402
import tape as TAPE                       # noqa: E402
import context as CTX                     # noqa: E402

# S6 budget mechanics (spec §1: "section budget enforced (S6 is the largest);
# episode-digest compression keeps it bounded").
#
# THE RAW WINDOW IS BUDGET-FILLED, NOT COUNT-CAPPED.  Measured event density in
# a 90s pre-decision window runs 230..1,550 events (SI, probed 2026-08-13), so
# "EVERY event of the final 90s" and "~3-5k tokens per sheet" cannot both hold
# literally.  The spec names the reconciliation itself ("episode-digest
# compression keeps it bounded"), so S6 renders:
#   [T-690s, T-90s)      -> gap-clustered episode digests   (always)
#   [T-90s,  T_raw)      -> gap-clustered episode digests   (only the overflow)
#   [T_raw,  T]          -> EVERY event, raw
# with T_raw pushed back as far as the S6 token budget allows.  Quiet windows
# therefore get the full 90s raw; loud windows keep the newest seconds raw and
# summarise the rest losslessly.  Nothing is ever dropped, and no minimum-size
# filter exists anywhere.
S6_EPISODE_MAX_PRE = 10                   # digests over [T-690s, T-90s)
S6_EPISODE_MAX_IN = 4                     # digests over the 90s overflow
S6_GAP_SEC = 1.0                          # gap-cluster split threshold
S6_RAW_TOKEN_EST = 27                     # conservative per-raw-line estimate
S6_DIGEST_TOKEN_EST = 32                  # conservative per-digest-line estimate
S6_FIXED_TOKEN_EST = 120                  # headers + the window summary line
S6_SHRINK_STEP = 8                        # raw lines dropped per fit iteration
S6_MAX_FIT_PASSES = 12

CLOCKNORM_SESSIONS = 60                   # spec §1 S5 "trailing 60-session"
BIN_SECONDS = 1800                        # same-half-hour clock norm

TMINUS_MARKS = (1800, 900, 300, 60, 0)
FLOW_WINDOWS = (60, 300, 1800)
RV_WINDOWS = (60, 300, 900, 1800)


# ============================================================== helpers ======
def tk(case, px):
    return MC.ticks(px, case.anchor, case.tick_px)


def usd(case, dpx):
    """Price delta -> dollars on this asset's contract."""
    return dpx * case.mult


def _phase_bounds(s):
    """[(phase_code, start_sec, end_sec_exclusive)] over the session."""
    out = []
    ch = [0] + [int(x) + 1 for x in
                np.nonzero(s.phase_tag[1:] != s.phase_tag[:-1])[0].tolist()]
    for i, st in enumerate(ch):
        en = ch[i + 1] if i + 1 < len(ch) else s.n
        out.append((int(s.phase_tag[st]), st, en))
    return out


def _sane_slice(case, lo, hi):
    """Indices into s.vt for SANE seconds in [lo, hi)."""
    a = int(np.searchsorted(case.s.vt, lo, side="left"))
    b = int(np.searchsorted(case.s.vt, hi, side="left"))
    return a, b


def _hi_lo(case, lo, hi):
    a, b = _sane_slice(case, lo, hi)
    if b <= a:
        return None
    v = case.s.vm[a:b]
    t = case.s.vt[a:b]
    ih = int(np.argmax(v))
    il = int(np.argmin(v))
    return (float(v[ih]), int(t[ih]), float(v[il]), int(t[il]))


def _rv_usd(case, lo, hi):
    """Realized-vol nowcast over [lo, hi): sqrt of summed squared 1s SANE mid
    returns, in DOLLARS on the contract (no annualisation — the sheet is a
    decision view, not a model input)."""
    a, b = _sane_slice(case, lo, hi)
    if b - a < 3:
        return float("nan")
    v = case.s.vm[a:b].astype(np.float64)
    d = np.diff(v)
    return float(np.sqrt(np.sum(d * d)) * case.mult)


def _bipower(case, lo, hi):
    a, b = _sane_slice(case, lo, hi)
    if b - a < 4:
        return float("nan"), float("nan")
    v = case.s.vm[a:b].astype(np.float64)
    d = np.abs(np.diff(v))
    rv = float(np.sum(d * d))
    bv = float((math.pi / 2.0) * np.sum(d[1:] * d[:-1]))
    if rv <= 0:
        return float("nan"), float("nan")
    return (math.sqrt(max(bv, 0.0)) * case.mult,
            max(0.0, (rv - bv) / rv))


# ------------------------------------------------------- clock normalisation -
_CN_CACHE = {}


def _session_bin_stats(asset, d8):
    """Per-half-hour-UTC-bin medians of the S5 quantities for ONE session.

    Cached per (asset, session): the trailing-60 norm needs 60 of these and a
    full Session object each would be ~5 MB, so only the 48-bin digest is kept.
    """
    key = (asset, int(d8))
    if key in _CN_CACHE:
        return _CN_CACHE[key]
    try:
        sess = A.load_session(asset, d8)
    except RuntimeError:
        _CN_CACHE[key] = None
        return None
    s = sess["s"]
    open_utc = int(s.meta["open_utc"])
    sod = (open_utc + np.arange(s.n, dtype=np.int64)) % 86400
    b = (sod // BIN_SECONDS).astype(np.int64)
    valid = s.valid
    tr = sess["trades"]
    out = {}
    for bi in range(86400 // BIN_SECONDS):
        m = (b == bi) & valid
        n = int(m.sum())
        if n < 60:
            continue
        secs = np.nonzero(b == bi)[0]
        lo, hi = int(secs[0]), int(secs[-1]) + 1
        t0 = int(np.searchsorted(tr["sec"], lo, side="left"))
        t1 = int(np.searchsorted(tr["sec"], hi, side="left"))
        span_min = max(1.0, (hi - lo) / 60.0)
        sd = tr["side"][t0:t1]
        sz = tr["size"][t0:t1].astype(np.int64)
        sf = int(np.sum(np.where(sd == ord("B"), sz,
                                 np.where(sd == ord("A"), -sz, 0))))
        out[bi] = {
            "spread_usd": float(np.median(s.spread_usd[m])),
            "bid_sz": float(np.median(s.bid_sz[m])),
            "ask_sz": float(np.median(s.ask_sz[m])),
            "trades_per_min": (t1 - t0) / span_min,
            "abs_sflow_per_min": abs(sf) / span_min,
        }
    _CN_CACHE[key] = out
    if len(_CN_CACHE) > 900:
        for k in list(_CN_CACHE)[:300]:
            _CN_CACHE.pop(k, None)
    return out


def clock_norm(case, bin_idx, field):
    """(median, mad) of `field` at the same half-hour over the trailing
    CLOCKNORM_SESSIONS sessions, STRICTLY PRIOR to this one."""
    ds = sorted(A.session_index(case.asset))
    i = bisect.bisect_left(ds, case.d8)
    prev = ds[max(0, i - CLOCKNORM_SESSIONS):i]
    vals = []
    for p in prev:
        st = _session_bin_stats(case.asset, p)
        if st and bin_idx in st:
            vals.append(st[bin_idx][field])
    if len(vals) < 10:
        return float("nan"), float("nan"), len(vals)
    a = np.array(vals, dtype=np.float64)
    med = float(np.median(a))
    mad = float(np.median(np.abs(a - med)))
    return med, mad, len(vals)


def _z(x, med, mad):
    if not np.isfinite(x) or not np.isfinite(med) or not np.isfinite(mad) \
            or mad <= 0:
        return float("nan")
    return (x - med) / (1.4826 * mad)


# ============================================================ S2 ============
def s2_regime(case, put):
    L = ["S2 ERA PRIMER REF + REGIME TAGS"]
    era = case.era
    L.append(MC.row("  era", MC.fstr(era, 16),
                    "primer=ERA_PRIMER_%s.md (spec S3, auto-generated per era "
                    "from committed censuses)" % era))
    put("S2.era", era, "engine/port_m2/m2_common.py", "ERAS")

    fs = case.fvol_seg
    seg = X.PHASE_NAMES[case.phase_dec]
    if fs is None:
        L.append("  fvol             " + MC.NA
                 + "   NO fvol row for (%s, %s, %s)" %
                 (case.asset, case.trade_date.isoformat(), seg))
        sigma = rng_hat = float("nan")
        regime = MC.NA
        rv_ratio = float("nan")
    else:
        sigma = A._f(fs["sigma_hat_usd"])
        rng_hat = A._f(fs["range_hat_usd"])
        regime = fs.get("regime_tag", MC.NA)
        rv_ratio = A._f(fs.get("rv5_over_rv66"))
        L.append(MC.row("  vol_regime", MC.fstr(regime, 10),
                        "rv5/rv66=" + MC.fnum(rv_ratio, 7, 3).strip(),
                        " segment=" + seg,
                        " sigma_hat=$" + MC.fnum(sigma, 1, 1).strip(),
                        " range_hat=$" + MC.fnum(rng_hat, 1, 1).strip()))
        put("S2.regime_tag", regime, case.fvol_path, "regime_tag")
        put("S2.rv5_over_rv66", rv_ratio, case.fvol_path, "rv5_over_rv66")
        put("S2.sigma_hat_usd", sigma, case.fvol_path, "sigma_hat_usd")
        put("S2.range_hat_usd", rng_hat, case.fvol_path, "range_hat_usd")

    hl = _hi_lo(case, 0, case.dec_sec)
    spent = usd(case, hl[0] - hl[2]) if hl else float("nan")
    frac = spent / rng_hat if (hl and np.isfinite(rng_hat) and rng_hat > 0) \
        else float("nan")
    day_type = (MC.NA if not np.isfinite(frac)
                else "INSIDE" if frac < 0.60
                else "AT_RANGE" if frac < 1.00 else "EXPANDED")
    L.append(MC.row("  day_type_so_far", MC.fstr(day_type, 9),
                    "range_so_far=$" + MC.fnum(spent, 1, 1).strip(),
                    " = " + MC.fnum(100.0 * frac, 1, 1).strip()
                    + "% of range_hat"))
    put("S2.range_so_far_usd", spent, case.session_path, "g0_mid[SANE,<dec]")
    put("S2.day_type_frac", frac, "derived", "range_so_far/range_hat")

    m = case.s.meta
    L.append(MC.row("  dominance", "dom_share=" + MC.fnum(m.get("dominant_share"), 6, 4).strip(),
                    " roll_window=" + ("1" if m.get("roll_window") else "0"),
                    " dying_book_week=" + ("1" if m.get("dying_book_week") else "0"),
                    " instrument_change=" + ("1" if m.get("instrument_change") else "0"),
                    " iid=" + str(case.s.iid)))
    put("S2.dominant_share", m.get("dominant_share"), case.session_path,
        "meta_json.dominant_share")

    # insane-book episodes SO FAR (causal): runs of two-sided-but-insane seconds
    ts = (case.s.state[:case.dec_sec] == C.ST_TWO_SIDED)
    ins = ts & (~case.s.valid[:case.dec_sec])
    n_ins = int(ins.sum())
    eps = int(np.sum(ins[1:] & ~ins[:-1])) + (1 if ins.size and ins[0] else 0)
    L.append(MC.row("  insane_book", "episodes_so_far=" + str(eps),
                    " insane_sec_so_far=" + str(n_ins),
                    " two_sided_sec_so_far=" + str(int(ts.sum())),
                    " session_insane_frac=" + MC.fnum(case.insane_frac, 8, 6).strip()))
    put("S2.insane_episodes_so_far", eps, "derived(b7_sane mask)",
        "state==TWO_SIDED & ~valid, sec<dec")
    put("S2.insane_sec_so_far", n_ins, "derived(b7_sane mask)", "count")
    return L


# ============================================================ S3 ============
def s3_path(case, put):
    L = ["S3 SESSION PATH + SWING CHAIN"]
    s = case.s
    now = case.entry_mid
    a0, _ = _sane_slice(case, 0, case.dec_sec)
    first_mid = float(s.vm[a0]) if a0 < s.vm.size else float("nan")
    L.append(MC.row("  session_open ", MC.fsec(int(s.vt[a0]) if a0 < s.vt.size else 0),
                    " first_sane_mid=" + MC.fnum(first_mid, 10, 4).strip(),
                    " now=" + MC.fsec(case.dec_sec),
                    " mid=" + MC.fnum(now, 10, 4).strip(),
                    " sess_ret=$" + MC.fnum(usd(case, now - first_mid), 1, 1).strip()))
    put("S3.first_sane_mid", first_mid, case.session_path, "g0_mid[first SANE]")
    put("S3.entry_mid", now, case.roster_path, "entry_mid[%d]" % case.i)

    prior_c = case.prior_bar.get("C", float("nan"))
    gap = usd(case, first_mid - prior_c) if np.isfinite(prior_c) else float("nan")
    L.append(MC.row("  gap_vs_settle", "prior_C=" + MC.fnum(prior_c, 10, 4).strip(),
                    " gap=$" + MC.fnum(gap, 1, 1).strip(),
                    " = " + MC.fnum(gap / case.atr if case.atr else float("nan"), 1, 3).strip()
                    + "xATR",
                    " prior_session=" + (str(case.prior_d8) if case.prior_d8 else MC.NA)))
    put("S3.prior_settle_close", prior_c,
        os.path.join(MC.M0_ROOT, "bars_%s.tsv" % case.asset), "C[prior]")
    put("S3.gap_usd", gap, "derived", "(first_sane_mid - prior_C)*mult")

    # phase state
    pb = _phase_bounds(s)
    cur = [p for p in pb if p[1] <= case.dec_sec < p[2]]
    if cur:
        code, st, en = cur[0]
        hl = _hi_lo(case, st, case.dec_sec)
        L.append(MC.row("  phase", MC.fstr(X.PHASE_NAMES[code], 7),
                        "open=" + MC.fsec(st),
                        " H=" + (MC.fnum(hl[0], 10, 4).strip() + "@" + MC.fsec(hl[1]) if hl else MC.NA),
                        " L=" + (MC.fnum(hl[2], 10, 4).strip() + "@" + MC.fsec(hl[3]) if hl else MC.NA),
                        " range=$" + (MC.fnum(usd(case, hl[0] - hl[2]), 1, 1).strip() if hl else MC.NA)))
        if hl:
            put("S3.phase_H", hl[0], case.session_path, "max g0_mid[SANE, phase, <dec]")
            put("S3.phase_L", hl[2], case.session_path, "min g0_mid[SANE, phase, <dec]")
    L.append(MC.row("  runway", "to_phase_close=" + str(case.phase_close_sec - case.dec_sec) + "s",
                    " (" + MC.fsec(case.phase_close_sec) + ")",
                    " to_sess_close=" + str(case.sess_close_sec - case.dec_sec) + "s",
                    " (" + MC.fsec(case.sess_close_sec) + ")"))
    put("S3.runway_phase_sec", case.phase_close_sec - case.dec_sec,
        case.roster_path, "phase_close_sec[%d]-dec_sec" % case.i)

    # CAPACITY (the §1 S3 "COVERAGE" number), reported on BOTH clocks: the
    # session against the SESSION forecast, the running phase against its own.
    def _q50(rowd):
        if rowd is None:
            return float("nan")
        return (A._f(rowd.get("move_q50_usd_per_sigma"))
                * A._f(rowd.get("sigma_hat_usd")))
    hl_s = _hi_lo(case, 0, case.dec_sec)
    spent_s = usd(case, hl_s[0] - hl_s[2]) if hl_s else float("nan")
    q50_s = _q50(case.fvol_sess)
    ph_start = 0
    for code, st, en in _phase_bounds(s):
        if st <= case.dec_sec < en:
            ph_start = st
    hl_p = _hi_lo(case, ph_start, case.dec_sec)
    spent_p = usd(case, hl_p[0] - hl_p[2]) if hl_p else float("nan")
    q50_p = _q50(case.fvol_seg)
    src = (case.fvol_sess or {}).get("sigma_source", MC.NA)
    for nm, sp, q in (("SESSION", spent_s, q50_s),
                      (X.PHASE_NAMES[case.phase_dec], spent_p, q50_p)):
        cov = sp / q if (np.isfinite(q) and q > 0) else float("nan")
        L.append(MC.row("  COVERAGE", MC.fstr(nm, 8),
                        "range_so_far=$" + MC.fnum(sp, 1, 1).strip(),
                        " exp_move_q50=$" + MC.fnum(q, 1, 1).strip(),
                        " COVERAGE=" + MC.fnum(100.0 * cov, 1, 1).strip() + "%",
                        " unspent=$" + MC.fnum(q - sp, 1, 1).strip()))
        put("S3.coverage_%s" % nm, cov, "derived",
            "SANE range so far / (move_q50_usd_per_sigma * sigma_hat_usd)")
    L.append(MC.row("  fvol_source", MC.fstr(src, 16),
                    "(ATR14_RAW_FILL = forecaster fell back to raw ATR14)"))
    put("S3.exp_move_q50_session_usd", q50_s, case.fvol_path,
        "move_q50_usd_per_sigma*sigma_hat_usd [SESSION]")

    # causal ZigZag pivots, all four rungs, tagged
    piv = _pivots(case)
    L.append("  ZIGZAG PIVOTS (causal, SANE, rungs %s xATR=$%s)"
             % (",".join("%g" % r for r in MC.RUNGS),
                MC.fnum(case.atr, 1, 2).strip()))
    L.append("     #  type  pivot_sec       price   d$_prev   leg_s  conf_sec  rungs")
    first = max(0, len(piv) - 8)
    for n in range(first, len(piv)):
        psec, ppx, side, mask, csec, dprev = piv[n]
        leg = (psec - piv[n - 1][0]) if n > 0 else None
        L.append(MC.row("    ", MC.fint(n + 1, 3),
                        MC.fstr("HIGH" if side < 0 else "LOW", 5),
                        MC.fsec(psec),
                        MC.fnum(ppx, 11, 4),
                        MC.fnum(dprev, 9, 1),
                        MC.fint(leg, 7),
                        MC.fsec(csec),
                        MC.fstr(",".join(MC.rung_names(mask)), 20)))
    L.append(MC.row("    n_pivots_total", MC.fint(len(piv), 5),
                    " shown_last", MC.fint(len(piv) - first, 3)))
    put("S3.n_pivots", len(piv), "derived(c_c_roster.zigzag_scan)",
        "causal, sec<dec_sec")
    return L


def _pivots(case):
    """Causal ZigZag pivots strictly before the decision second, union over the
    generation-v3 rung ladder, tagged by the rungs that produced each."""
    s = case.s
    j = int(np.searchsorted(s.vt, case.dec_sec, side="left"))
    vt_l = s.vt[:j].tolist()
    vm_l = s.vm[:j].tolist()
    if len(vt_l) < 2:
        return []
    vphase = s.phase_tag[s.vt[:j]].tolist()
    phase_med = CA.phase_median_spreads(MC.M0_ROOT)
    merged = {}
    for ri, r in enumerate(MC.RUNGS):
        per_phase = []
        for p in range(X.N_PHASES):
            pm = phase_med.get((case.asset, case.trade_date.year,
                                X.PHASE_NAMES[p]), float("nan"))
            fl = X.RUNG_FLOOR_SPREAD_MULT * pm if np.isfinite(pm) else 0.0
            u = max(r * case.atr, X.RUNG_FLOOR_TICKS * case.tick_usd, fl)
            per_phase.append(X.round_half_up(u / case.mult, case.tick_px))
        thr_l = [per_phase[p] for p in vphase]
        for (px, psec, csec, side) in CC.zigzag_scan(vt_l, vm_l, thr_l):
            k = (int(psec), int(side))
            e = merged.get(k)
            if e is None:
                merged[k] = [float(px), 0, int(csec)]
                e = merged[k]
            e[1] |= (1 << ri)
            e[2] = min(e[2], int(csec))
    out = []
    prev = None
    for (psec, side) in sorted(merged):
        px, mask, csec = merged[(psec, side)]
        d = usd(case, px - prev) if prev is not None else float("nan")
        out.append((psec, px, side, mask, csec, d))
        prev = px
    return out


# ============================================================ S4 ============
def s4_levels(case, put):
    L = ["S4 LEVEL LEDGER VIEW"]
    if case.levels is None:
        L.append("  " + MC.NA + "  no level ledger receipt at %s"
                 % case.levels_path)
        return L
    z = case.levels
    mid = case.entry_mid
    band = 1.5 * case.atr / case.mult                # 1.5 x ATR in price units
    fam = z["level_family"]
    lid = z["level_id"]
    lpx = z["level_price"]
    created = z["created_d8"]
    tch = z["touches"]

    # causal per-level state: open snapshot + touches strictly before dec_sec
    n = int(lpx.size)
    tc = np.zeros(n, dtype=np.int64)
    lts = np.full(n, -1, dtype=np.int64)
    lto = np.zeros(n, dtype=np.int64)
    pending = np.zeros(n, dtype=bool)
    virgin0 = np.ones(n, dtype=bool)
    tc0 = np.zeros(n, dtype=np.int64)
    ss = z["snap_sec"]
    sr = z["snap_row"]
    open_rows = np.nonzero(ss == 0)[0]
    for k in open_rows.tolist():
        r = int(sr[k])
        virgin0[r] = bool(z["snap_virgin"][k])
        tc0[r] = int(z["snap_touch_count"][k])
    n_touch_causal = n_pending = 0
    if tch.size:
        for rrow in tch:
            tsec = int(rrow[0])
            row = int(rrow[1])
            if not case.guard.sec(tsec, "S4 touch"):
                continue
            n_touch_causal += 1
            tc[row] += 1
            lts[row] = tsec
            osec = int(rrow[6])
            oc = int(rrow[5])
            # A touch OUTCOME is resolved inside a FORWARD 15-minute window
            # (b3_levels REJECT_WINDOW), so it is knowable only once its own
            # resolution second has passed.  A NONE outcome carries no
            # resolution second: it is knowable only once the whole window has
            # elapsed.  Anything else is PENDING — never the ledger's
            # end-of-session value, which is the leak this guard exists for.
            if oc != B3.OUTCOME_NONE and osec >= 0:
                known = case.guard.sec(osec, "S4 touch outcome")
            else:
                known = case.guard.sec(tsec + B3.REJECT_WINDOW,
                                       "S4 touch outcome window")
            if known:
                lto[row] = oc
                pending[row] = False
            else:
                lto[row] = -1
                pending[row] = True
                n_pending += 1

    dist = (lpx - mid)
    sel = np.nonzero(np.isfinite(lpx) & (np.abs(dist) <= band))[0]
    order = sorted(sel.tolist(), key=lambda r: (abs(float(dist[r])),
                                                str(fam[r]), str(lid[r])))
    n_show = 12
    L.append(MC.row("  mid=" + MC.fnum(mid, 1, 4).strip(),
                    " ATR=$" + MC.fnum(case.atr, 1, 2).strip(),
                    " band=+/-1.5xATR=$" + MC.fnum(1.5 * case.atr, 1, 2).strip(),
                    " n_in_band=" + str(len(order)),
                    " n_levels=" + str(n),
                    " n_touches=" + str(n_touch_causal),
                    " n_pending=" + str(n_pending),
                    " K=kept/r=retired family"))
    L.append("    K family         level_id                        price      d$  V  tc  test_m outcome")
    for r in order[:n_show]:
        oc = ("PENDING" if pending[r] else
              MC.TOUCH_OUTCOMES[int(lto[r])] if lto[r] >= 0 else MC.NA)
        v = 1 if (virgin0[r] and tc[r] == 0) else 0
        fname = str(fam[r])
        lidt = str(lid[r])
        if lidt.startswith(fname + "|"):
            lidt = lidt[len(fname) + 1:]
        L.append(MC.row("   ",
                        "K" if fname in MC.KEPT_LEVEL_FAMILIES else "r",
                        MC.fstr(fname, 14),
                        MC.fstr(lidt, 26),
                        MC.fnum(float(lpx[r]), 9, 4),
                        MC.fnum(usd(case, float(dist[r])), 8, 1),
                        MC.fint(v, 2),
                        MC.fint(int(tc0[r] + tc[r]), 3),
                        MC.fint((case.dec_sec - int(lts[r])) // 60
                                if lts[r] >= 0 else None, 6),
                        MC.fstr(oc, 7)))
    if len(order) > n_show:
        # COMPLETENESS: the remaining in-band levels are not dropped, they are
        # rolled up per family so the count and the nearest distance survive.
        rest = order[n_show:]
        by = {}
        for r in rest:
            e = by.setdefault(str(fam[r]), [0, None, 0])
            e[0] += 1
            dd = usd(case, float(dist[r]))
            if e[1] is None or abs(dd) < abs(e[1]):
                e[1] = dd
            if virgin0[r] and tc[r] == 0:
                e[2] += 1
        L.append("    REMAINDER rolled up by family, n/nearest_d$/n_virgin "
                 "(counted, never dropped):")
        keys = sorted(by)
        L.append("     " + " ".join(
            "%s=%d/%s/%d" % (f, by[f][0], MC.fnum(by[f][1], 1, 0).strip(),
                             by[f][2]) for f in keys))
    put("S4.n_active_in_band", len(order), case.levels_path,
        "|level_price-mid| <= 1.5*ATR/mult")
    put("S4.n_touches_causal", n_touch_causal, case.levels_path,
        "touches[touch_sec < dec_sec]")
    put("S4.n_pending_outcome", n_pending, case.levels_path,
        "touches whose 15-min outcome window has not closed by dec_sec")

    # OR state (the CC-M1-6.1 opening-range object)
    # OR STATE (spec S4): OR H/L/range per adopted cell, recovered exactly from
    # the ledger's own k-ladder — L_up(k) = OR_H + k*range, L_dn(k) = OR_L -
    # k*range — so two k values on a side determine OR_H/OR_L and the range.
    cells = {}
    for r in range(n):
        if str(fam[r]) != "OR_EXT":
            continue
        p = str(lid[r]).split("|")
        if len(p) != 5:
            continue
        cells.setdefault(p[1] + "|" + p[2], {}).setdefault(
            p[4], {})[float(p[3][1:])] = float(lpx[r])
    if cells:
        L.append("  OR STATE (opening range per adopted CC-M1-6.1 cell; "
                 "k-extension ladder in the ledger above)")
        L.append("    cell            OR_H       OR_L    range$   d$_to_H   d$_to_L  k_ladder")
        for cname in sorted(cells):
            up = cells[cname].get("+1", {})
            dn = cells[cname].get("-1", {})
            ks = sorted(set(list(up) + list(dn)))
            orh = orl = rng = float("nan")
            if len(up) >= 2:
                k1, k2 = sorted(up)[:2]
                rng = (up[k2] - up[k1]) / (k2 - k1)
                orh = up[k1] - k1 * rng
            if len(dn) >= 2:
                k1, k2 = sorted(dn)[:2]
                r2 = (dn[k1] - dn[k2]) / (k2 - k1)
                orl = dn[k1] + k1 * r2
                if not np.isfinite(rng):
                    rng = r2
            L.append(MC.row("   ", MC.fstr(cname, 14),
                            MC.fnum(orh, 9, 4), MC.fnum(orl, 10, 4),
                            MC.fnum(usd(case, rng), 9, 1),
                            MC.fnum(usd(case, mid - orh), 9, 1),
                            MC.fnum(usd(case, mid - orl), 9, 1),
                            MC.fstr(",".join("%g" % k for k in ks), 20)))
            put("S4.or_%s_range_usd" % cname.replace("|", "_"),
                usd(case, rng), case.levels_path,
                "recovered from the OR_EXT k-ladder level prices")
    else:
        L.append("  OR STATE         none built for this asset/session "
                 "(CC-M1-6.1 adopted cells: SI 5, NKD 1, HG 0)")
    beyond = MC.bits_to_names(case.flags, MC.FLAG_NAMES)
    L.append(MC.row("  or_ext_flags", MC.fstr(",".join(beyond) if beyond
                                              else "none", 40)))
    return L


# ============================================================ S5 ============
def s5_tminus(case, put):
    L = ["S5 T-MINUS TRAJECTORY (z = vs trailing-%d-session same half-hour)"
         % CLOCKNORM_SESSIONS]
    s = case.s
    tr = case.trades
    marks = [case.dec_sec - m for m in TMINUS_MARKS]
    hdr = ["T-30m", "T-15m", "T-5m", "T-1m", "NOW"]

    def at(sec):
        if sec < 0:
            return None
        case.guard.at_decision(sec, "S5 mark")
        j = int(np.searchsorted(s.vt, sec, side="right")) - 1
        if j < 0:
            return None
        return j

    js = [at(m) for m in marks]
    bin_idx = ((case.open_utc + case.dec_sec) % 86400) // BIN_SECONDS

    def emit(name, vals, zfield=None, dec=4, width=10):
        cells = [MC.fstr(name, 16)]
        for v in vals:
            cells.append(MC.fnum(v, width, dec))
        zz = float("nan")
        nn = 0
        if zfield is not None and np.isfinite(vals[-1]):
            med, mad, nn = clock_norm(case, bin_idx, zfield)
            zz = _z(vals[-1], med, mad)
        cells.append(MC.fnum(zz, 8, 2))
        cells.append(MC.fint(nn, 4) if zfield else MC.NA.rjust(4))
        L.append(MC.row(*cells))

    L.append(MC.row(MC.fstr("  quantity", 16),
                    *([MC.fstr(h, 10) for h in hdr]
                      + [MC.fstr("z", 8), MC.fstr("n_ref", 4)])))
    mids = [float(s.vm[j]) if j is not None else float("nan") for j in js]
    emit("  mid", mids, None, 4, 10)
    spr = [float(s.spread_usd[m]) if (m >= 0 and s.valid[m]) else float("nan")
           for m in marks]
    emit("  spread_$", spr, "spread_usd", 2, 10)
    bs = [float(s.bid_sz[m]) if m >= 0 else float("nan") for m in marks]
    az = [float(s.ask_sz[m]) if m >= 0 else float("nan") for m in marks]
    emit("  bid_sz", bs, "bid_sz", 0, 10)
    emit("  ask_sz", az, "ask_sz", 0, 10)

    def rate(sec, win):
        if sec - win < 0:
            return float("nan"), float("nan")
        lo = int(np.searchsorted(tr["sec"], sec - win, side="left"))
        hi = int(np.searchsorted(tr["sec"], min(sec, case.dec_sec),
                                 side="left"))
        sz = tr["size"][lo:hi].astype(np.int64)
        sd = tr["side"][lo:hi]
        sf = int(np.sum(np.where(sd == ord("B"), sz,
                                 np.where(sd == ord("A"), -sz, 0))))
        return (hi - lo) * 60.0 / win, sf * 60.0 / win

    tpm = [rate(m, 60)[0] for m in marks]
    spm = [rate(m, 60)[1] for m in marks]
    emit("  trades/min", tpm, "trades_per_min", 2, 10)
    emit("  sflow/min", spm, None, 1, 10)
    rv = [_rv_usd(case, max(0, m - 300), m) if m >= 0 else float("nan")
          for m in marks]
    emit("  rv300_$", rv, None, 1, 10)

    # slope / accel on the mid, in $ per minute
    def d_usd(a, b):
        if a is None or b is None:
            return float("nan")
        return usd(case, float(s.vm[b]) - float(s.vm[a]))
    sl_1 = d_usd(js[3], js[4])                   # last minute
    sl_5 = d_usd(js[2], js[4]) / 5.0             # last 5 min, per minute
    sl_15 = d_usd(js[1], js[4]) / 15.0
    L.append(MC.row("  mid_slope_$/min", MC.fnum(sl_15, 10, 1),
                    MC.fnum(sl_5, 10, 1), MC.fnum(sl_1, 10, 1),
                    " accel(1m-5m)=", MC.fnum(sl_1 - sl_5, 10, 1)))
    put("S5.mid_now", mids[-1], case.session_path, "g0_mid[dec_sec]")
    put("S5.spread_now_usd", spr[-1], case.session_path, "g0_spread_usd[dec_sec]")
    put("S5.bid_sz_now", bs[-1], case.session_path, "g0_bid_sz[dec_sec]")
    put("S5.ask_sz_now", az[-1], case.session_path, "g0_ask_sz[dec_sec]")
    put("S5.trades_per_min_now", tpm[-1], case.session_path,
        "trades_sec in [dec-60, dec)")
    put("S5.sflow_per_min_now", spm[-1], case.session_path,
        "trades_side/size in [dec-60, dec)")
    put("S5.rv300_now_usd", rv[-1], "derived", "sqrt(sum d(mid)^2)*mult, 300s")
    return L


# ============================================================ S6 ============
def _episodes(ev, lo_i, hi_i, gap_sec, max_eps):
    """Gap-cluster [lo_i, hi_i) into at most max_eps episodes.

    Split wherever the inter-event gap >= gap_sec; if that yields more clusters
    than the budget, MERGE adjacent pairs in ascending gap order (deterministic,
    ties by earlier index) until the budget is met.  Every event lands in
    exactly one episode: the compression is lossless in membership and the
    digests carry no minimum-size filter (DISCRETIONARY_METHOD §2.3).
    """
    if hi_i <= lo_i:
        return []
    ts = ev["ts_ns"][lo_i:hi_i]
    n = ts.size
    gaps = np.diff(ts).astype(np.float64) / 1e9 if n > 1 else np.zeros(0)
    cut = [0] + [int(i) + 1 for i in np.nonzero(gaps >= gap_sec)[0].tolist()] \
        + [n]
    bounds = list(zip(cut[:-1], cut[1:]))
    while len(bounds) > max_eps:
        # gap between consecutive clusters b[k] and b[k+1]
        best_k, best_g = 0, None
        for k in range(len(bounds) - 1):
            g = float(ts[bounds[k + 1][0]] - ts[bounds[k][1] - 1]) / 1e9
            if best_g is None or g < best_g:
                best_g, best_k = g, k
        bounds[best_k] = (bounds[best_k][0], bounds[best_k + 1][1])
        del bounds[best_k + 1]
    return [(lo_i + a, lo_i + b) for a, b in bounds]


def s6_ribbon(case, put):
    ev = case.events
    head = ["S6 RAW EVENT RIBBON (MBP-1, dominant iid=%d, clock=ts_event)"
            % case.s.iid]
    if ev is None or ev["ts_ns"].size == 0:
        return head + ["  " + MC.NA + "  no event cache for this window"]
    tag, flow = case.trade_tag, case.trade_flow
    ts = ev["ts_ns"]
    dec_ns = (case.decision_ts + 1) * 10 ** 9      # end of the decision second
    raw_lo_ns = (case.decision_ts - TAPE.RIBBON_RAW_SEC) * 10 ** 9
    dig_lo_ns = (case.decision_ts - TAPE.RIBBON_RAW_SEC
                 - TAPE.RIBBON_DIGEST_SEC) * 10 ** 9
    i_dig = int(np.searchsorted(ts, dig_lo_ns, side="left"))
    i_raw = int(np.searchsorted(ts, raw_lo_ns, side="left"))
    i_end = int(np.searchsorted(ts, dec_ns, side="left"))
    n_raw_window = i_end - i_raw

    budget = MC.SECTION_BUDGET["S6"]
    reserve = ((S6_EPISODE_MAX_PRE + S6_EPISODE_MAX_IN) * S6_DIGEST_TOKEN_EST
               + S6_FIXED_TOKEN_EST)
    k = max(0, (budget - reserve) // S6_RAW_TOKEN_EST)
    lines = None
    for _ in range(S6_MAX_FIT_PASSES):
        lines = _s6_render(case, ev, tag, flow, i_dig, i_raw, i_end, int(k),
                           n_raw_window, put_sink=None)
        tok = MC.count_tokens("\n".join(lines) + "\n")
        if tok <= budget or k <= 0:
            break
        k = max(0, k - S6_SHRINK_STEP)
    # re-render once with the sidecar sink on the accepted configuration
    return _s6_render(case, ev, tag, flow, i_dig, i_raw, i_end, int(k),
                      n_raw_window, put_sink=put)


def _s6_render(case, ev, tag, flow, i_dig, i_raw, i_end, k, n_raw_window,
               put_sink):
    ts = ev["ts_ns"]
    dec_ns = (case.decision_ts + 1) * 10 ** 9
    i_rawstart = max(i_raw, i_end - k)
    raw_cover = (float(dec_ns - int(ts[i_rawstart])) / 1e9
                 if i_end > i_rawstart else 0.0)
    L = ["S6 RAW EVENT RIBBON (MBP-1, dominant iid=%d, clock=ts_event)"
         % case.s.iid]
    L.append(MC.row("  window", "pre=[T-%ds,T-%ds)" % (
        TAPE.RIBBON_RAW_SEC + TAPE.RIBBON_DIGEST_SEC, TAPE.RIBBON_RAW_SEC),
        " raw_window=[T-%ds,T]" % TAPE.RIBBON_RAW_SEC,
        " n_ev_pre=" + str(i_raw - i_dig),
        " n_ev_90s=" + str(n_raw_window),
        " n_raw=" + str(i_end - i_rawstart),
        " raw_cover=" + MC.fnum(raw_cover, 1, 2).strip() + "s",
        " n_digested_in_90s=" + str(i_rawstart - i_raw)))
    eps_pre = _episodes(ev, i_dig, i_raw, S6_GAP_SEC, S6_EPISODE_MAX_PRE)
    eps_in = _episodes(ev, i_raw, i_rawstart, S6_GAP_SEC, S6_EPISODE_MAX_IN)
    L.append("  EPISODE DIGESTS (gap>=%.1fs clusters; every event belongs to "
             "exactly one episode; NO minimum-size filter)" % S6_GAP_SEC)
    L.append("    t0     t1     n  nQ  nT  vol szmd szmx sflow  pxH  pxL trav$ thru")
    for (a, b) in eps_pre + eps_in:
        L.append(_digest_line(case, ev, tag, flow, a, b))
    L.append("  RAW EVENTS (EVERY event in [T-%ss, T]; newest last; prices as "
             "signed integer ticks vs anchor %s; ms = milliseconds before "
             "decision_ts, negative = inside the decision second itself, which "
             "IS the entry book)"
             % (MC.fnum(raw_cover, 1, 2).strip(),
                MC.fnum(case.anchor, 1, 4).strip()))
    L.append("        ms a s   pxT    sz  bidT  bsz  askT  asz    dsz st fl tag")
    pbsz = pasz = None
    for j in range(i_rawstart, i_end):
        L.append(_event_line(case, ev, tag, j, pbsz, pasz))
        pbsz, pasz = int(ev["bid_sz"][j]), int(ev["ask_sz"][j])
    if put_sink is not None:
        src = os.path.join(TAPE.EVENTS_DIR, case.asset, "%08d.npz" % case.d8)
        put_sink("S6.n_events_90s", n_raw_window, src, "ts_ns in [T-90s, T]")
        put_sink("S6.n_events_pre", i_raw - i_dig, src,
                 "ts_ns in [T-690s, T-90s)")
        put_sink("S6.n_events_raw_shown", i_end - i_rawstart, "derived",
                 "budget-filled raw window (S6 budget=%d tokens)"
                 % MC.SECTION_BUDGET["S6"])
        put_sink("S6.raw_cover_sec", raw_cover, "derived",
                 "T - ts_event[first raw line]")
        put_sink("S6.n_episodes", len(eps_pre) + len(eps_in), "derived",
                 "gap-clustered digests (pre=%d, in-90s=%d)"
                 % (len(eps_pre), len(eps_in)))
        put_sink("S6.events_index_range", [int(i_dig), int(i_end)], src,
                 "row indices into the cached event arrays covering this "
                 "sheet's whole S6 window")
    return L


def _px_t(case, raw):
    if raw is None or raw <= 0 or raw >= C.SENT_HI:
        return None
    return tk(case, float(raw) * case.spec["px_scale"])


def _event_line(case, ev, tag, k, pbsz, pasz):
    bsz = int(ev["bid_sz"][k])
    asz = int(ev["ask_sz"][k])
    st = TAPE.book_state(int(ev["bid_px"][k]), int(ev["ask_px"][k]))
    ms = int((case.decision_ts * 10 ** 9 - int(ev["ts_ns"][k])) // 10 ** 6)
    isT = int(ev["action"][k]) == ord("T")
    tg = TAPE.TRADE_TAGS[int(tag[k])] if int(tag[k]) != TAPE.TRADE_UNK else "-"
    # L1 size delta of whichever side moved (the §1 "sz deltas"), one field
    if pbsz is None:
        dsz = MC.NA
    else:
        db, da = bsz - pbsz, asz - pasz
        if db and da:
            dsz = "B%+d/A%+d" % (db, da)
        elif db:
            dsz = "B%+d" % db
        elif da:
            dsz = "A%+d" % da
        else:
            dsz = "0"
    return MC.row("     ", MC.fint(ms, 7),
                  chr(int(ev["action"][k])), chr(int(ev["side"][k])),
                  MC.fint(_px_t(case, int(ev["price"][k])) if isT else None, 6),
                  MC.fint(int(ev["size"][k]), 5),
                  MC.fint(_px_t(case, int(ev["bid_px"][k])), 5),
                  MC.fint(bsz, 4),
                  MC.fint(_px_t(case, int(ev["ask_px"][k])), 5),
                  MC.fint(asz, 4),
                  MC.fstr(dsz, 6),
                  MC.fstr(TAPE.STATE_TAG.get(st, "??"), 2),
                  MC.fstr(TAPE.flag_str(int(ev["flags"][k])), 2),
                  MC.fstr(tg, 3))


def _digest_line(case, ev, tag, flow, a, b):
    ts = ev["ts_ns"][a:b]
    act = ev["action"][a:b]
    sz = ev["size"][a:b].astype(np.int64)
    t0 = (int(ts[0]) - case.decision_ts * 10 ** 9) / 1e9
    t1 = (int(ts[-1]) - case.decision_ts * 10 ** 9) / 1e9
    isT = act == ord("T")
    tsz = sz[isT]
    vol = int(tsz.sum())
    szmd = int(np.median(tsz)) if tsz.size else None
    szmx = int(tsz.max()) if tsz.size else None
    sf = int(flow[a:b].sum())
    tg = tag[a:b]
    thru = int(np.sum((tg == TAPE.TRADE_THRU_B) | (tg == TAPE.TRADE_THRU_A)))
    bid = ev["bid_px"][a:b].astype(np.float64)
    ask = ev["ask_px"][a:b].astype(np.float64)
    ok = (bid > 0) & (bid < C.SENT_HI) & (ask > 0) & (ask < C.SENT_HI) \
        & (ask > bid)
    if ok.any():
        m = (bid[ok] + ask[ok]) / 2.0 * case.spec["px_scale"]
        ph, pl = float(m.max()), float(m.min())
        trav = usd(case, ph - pl)
    else:
        ph = pl = float("nan")
        trav = float("nan")
    return MC.row("   ", MC.fnum(t0, 7, 1), MC.fnum(t1, 7, 1),
                  MC.fint(b - a, 5), MC.fint(int((~isT).sum()), 4),
                  MC.fint(int(isT.sum()), 4),
                  MC.fint(vol, 5), MC.fint(szmd, 4), MC.fint(szmx, 4),
                  MC.fint(sf, 6),
                  MC.fint(tk(case, ph), 5), MC.fint(tk(case, pl), 5),
                  MC.fnum(trav, 6, 0), MC.fint(thru, 4))


# ============================================================ S7 ============
def s7_book(case, put):
    L = ["S7 BOOK/QUEUE STATE"]
    s = case.s
    d = case.dec_sec
    st = TAPE.STATE_TAG.get(int(s.state[d]), "??")
    L.append(MC.row("  L1_now", "bid=" + MC.fnum(float(s.mid[d]) - float(s.spread_usd[d]) / (2.0 * case.mult), 1, 4).strip(),
                    "x" + str(int(s.bid_sz[d])),
                    " ask=" + MC.fnum(float(s.mid[d]) + float(s.spread_usd[d]) / (2.0 * case.mult), 1, 4).strip(),
                    "x" + str(int(s.ask_sz[d])),
                    " spread=$" + MC.fnum(float(s.spread_usd[d]), 1, 2).strip(),
                    " (" + MC.fnum(float(s.spread_usd[d]) / case.tick_usd, 1, 1).strip() + " ticks)",
                    " state=" + st,
                    " SANE=" + ("1" if case.sane_at(d) else "0")))
    put("S7.bid_sz_now", int(s.bid_sz[d]), case.session_path, "g0_bid_sz[dec_sec]")
    put("S7.ask_sz_now", int(s.ask_sz[d]), case.session_path, "g0_ask_sz[dec_sec]")

    ev = case.events
    if ev is None or ev["ts_ns"].size == 0:
        L.append("  " + MC.NA + "  no event cache: churn/queue statistics "
                 "unavailable")
        return L
    ts = ev["ts_ns"]
    dec_ns = (case.decision_ts + 1) * 10 ** 9
    L.append("    window   n_ev   A    C    M    T   rev/s  L1life_ms  c2f   dBsz/min  dAsz/min")
    for w in (60, 300):
        lo = int(np.searchsorted(ts, (case.decision_ts - w) * 10 ** 9,
                                 side="left"))
        hi = int(np.searchsorted(ts, dec_ns, side="left"))
        act = ev["action"][lo:hi]
        nA = int(np.sum(act == ord("A")))
        nC = int(np.sum(act == ord("C")))
        nM = int(np.sum(act == ord("M")))
        nT = int(np.sum(act == ord("T")))
        n = hi - lo
        # L1 lifetime: mean time between consecutive TOP-OF-BOOK changes
        bp = ev["bid_px"][lo:hi]
        ap = ev["ask_px"][lo:hi]
        bs = ev["bid_sz"][lo:hi]
        asz = ev["ask_sz"][lo:hi]
        if n > 1:
            chg = ((bp[1:] != bp[:-1]) | (ap[1:] != ap[:-1])
                   | (bs[1:] != bs[:-1]) | (asz[1:] != asz[:-1]))
            ct = ts[lo + 1:hi][chg]
            life = (float(np.mean(np.diff(ct))) / 1e6 if ct.size > 1
                    else float("nan"))
        else:
            life = float("nan")
        fills = int(np.sum(ev["size"][lo:hi][act == ord("T")]))
        c2f = (float(nC) / fills) if fills else float("nan")
        db = ((float(bs[-1]) - float(bs[0])) * 60.0 / w) if n > 1 else float("nan")
        da = ((float(asz[-1]) - float(asz[0])) * 60.0 / w) if n > 1 else float("nan")
        L.append(MC.row("   ", MC.fint(w, 6), MC.fint(n, 6), MC.fint(nA, 4),
                        MC.fint(nC, 4), MC.fint(nM, 4), MC.fint(nT, 4),
                        MC.fnum(n / float(w), 7, 2), MC.fnum(life, 10, 1),
                        MC.fnum(c2f, 6, 2), MC.fnum(db, 9, 2),
                        MC.fnum(da, 9, 2)))
        if w == 60:
            put("S7.n_events_60s", n, "derived(events npz)", "count")
            put("S7.cancel_to_fill_60s", c2f, "derived", "n_cancel/traded_size")

    # refill-after-trade: does the traded side's size recover within 5s?
    lo = int(np.searchsorted(ts, (case.decision_ts - 300) * 10 ** 9,
                             side="left"))
    hi = int(np.searchsorted(ts, dec_ns, side="left"))
    n_tr = 0
    n_ref = 0
    rts = []
    for k in range(lo, hi):
        if ev["action"][k] != ord("T"):
            continue
        n_tr += 1
        sd = chr(int(ev["side"][k]))
        col = "bid_sz" if sd == "A" else "ask_sz"   # aggressor A hits the bid
        if k == lo:
            continue
        before = int(ev[col][k - 1])
        after = int(ev[col][k])
        if after >= before:
            continue
        lim = int(np.searchsorted(ts, int(ts[k]) + 5 * 10 ** 9, side="left"))
        w = ev[col][k + 1:min(lim, hi)]
        if w.size and int(w.max()) >= before:
            n_ref += 1
            j = k + 1 + int(np.argmax(w >= before))
            rts.append((int(ts[j]) - int(ts[k])) / 1e6)
    L.append(MC.row("  refill_after_trade", "n_trades_300s=" + str(n_tr),
                    " n_refilled_5s=" + str(n_ref),
                    " frac=" + MC.fnum(n_ref / float(n_tr) if n_tr else float("nan"), 1, 3).strip(),
                    " median_restore_ms=" + MC.fnum(float(np.median(rts)) if rts else float("nan"), 1, 1).strip()))
    put("S7.refill_frac_300s", n_ref / float(n_tr) if n_tr else float("nan"),
        "derived(events npz)", "size restored within 5s after a touch trade")
    return L


# ============================================================ S8 ============
def s8_flow(case, put):
    L = ["S8 FLOW STATE"]
    tr = case.trades
    d = case.dec_sec
    pb = _phase_bounds(case.s)
    cur = [p for p in pb if p[1] <= d < p[2]]
    ph_start = cur[0][1] if cur else 0
    L.append("    window      n     vol   sflow    buy   sell  buy/sell_vol")
    for name, lo in (("60s", d - 60), ("5m", d - 300), ("30m", d - 1800),
                     ("phase", ph_start), ("session", 0)):
        lo = max(0, lo)
        a = int(np.searchsorted(tr["sec"], lo, side="left"))
        b = int(np.searchsorted(tr["sec"], d, side="left"))
        sz = tr["size"][a:b].astype(np.int64)
        sd = tr["side"][a:b]
        buy = int(sz[sd == ord("B")].sum())
        sell = int(sz[sd == ord("A")].sum())
        L.append(MC.row("   ", MC.fstr(name, 8), MC.fint(b - a, 6),
                        MC.fint(int(sz.sum()), 7), MC.fint(buy - sell, 7),
                        MC.fint(int(np.sum(sd == ord("B"))), 6),
                        MC.fint(int(np.sum(sd == ord("A"))), 6),
                        MC.fstr("%d/%d" % (buy, sell), 14)))
        if name == "session":
            put("S8.session_signed_flow", buy - sell, case.session_path,
                "trades_side/size, sec<dec_sec")
        if name == "60s":
            put("S8.sflow_60s", buy - sell, case.session_path,
                "trades in [dec-60, dec)")

    # fuel map: traded volume by price band relative to the current mid, phase
    a = int(np.searchsorted(tr["sec"], ph_start, side="left"))
    b = int(np.searchsorted(tr["sec"], d, side="left"))
    px = tr["px_f"][a:b]
    sz = tr["size"][a:b].astype(np.int64)
    mid = case.entry_mid
    L.append("  FUEL MAP (phase volume by band vs current mid; ATR fractions)")
    L.append("    band            px_lo     px_hi      vol   share")
    edges = [-1e9, -1.0, -0.5, -0.25, -0.05, 0.05, 0.25, 0.5, 1.0, 1e9]
    tot = int(sz.sum())
    for i in range(len(edges) - 1):
        lo_p = mid + edges[i] * case.atr / case.mult
        hi_p = mid + edges[i + 1] * case.atr / case.mult
        m = (px >= lo_p) & (px < hi_p)
        v = int(sz[m].sum())
        if v == 0:
            continue
        L.append(MC.row("   ", MC.fstr("%+.2f..%+.2f ATR" % (edges[i], edges[i + 1])
                                       if abs(edges[i]) < 1e8 or abs(edges[i + 1]) < 1e8
                                       else "far", 15),
                        MC.fnum(lo_p if abs(edges[i]) < 1e8 else float("nan"), 9, 4),
                        MC.fnum(hi_p if abs(edges[i + 1]) < 1e8 else float("nan"), 9, 4),
                        MC.fint(v, 8),
                        MC.fnum(100.0 * v / tot if tot else float("nan"), 7, 1)))
    above = int(sz[px > mid].sum())
    below = int(sz[px < mid].sum())
    L.append(MC.row("    trapped", "above_mid=" + str(above),
                    " below_mid=" + str(below),
                    " at_mid=" + str(tot - above - below),
                    " phase_total=" + str(tot)))
    put("S8.fuel_above_mid", above, case.session_path,
        "trades_px>entry_mid, phase, sec<dec")
    put("S8.fuel_below_mid", below, case.session_path,
        "trades_px<entry_mid, phase, sec<dec")

    # through-book prints (event grain)
    ev = case.events
    if ev is not None and ev["ts_ns"].size:
        tag = case.trade_tag
        ts = ev["ts_ns"]
        lo = int(np.searchsorted(ts, (case.decision_ts - 600) * 10 ** 9,
                                 side="left"))
        hi = int(np.searchsorted(ts, (case.decision_ts + 1) * 10 ** 9,
                                 side="left"))
        w = [k for k in range(lo, hi)
             if int(tag[k]) in (TAPE.TRADE_THRU_B, TAPE.TRADE_THRU_A)]
        L.append(MC.row("  through_book_600s", "n=" + str(len(w)),
                        " thru_bid=" + str(sum(1 for k in w if int(tag[k]) == TAPE.TRADE_THRU_B)),
                        " thru_ask=" + str(sum(1 for k in w if int(tag[k]) == TAPE.TRADE_THRU_A))))
        for k in w[-6:]:
            L.append(MC.row("    ", MC.fint(int((int(ts[k]) - case.decision_ts * 10 ** 9) // 10 ** 6), 8) + "ms",
                            "pxT=" + str(_px_t(case, int(ev["price"][k]))),
                            " sz=" + str(int(ev["size"][k])),
                            " " + TAPE.TRADE_TAGS[int(tag[k])]))
        put("S8.n_through_book_600s", len(w), "derived(events npz)",
            "trade px outside the prevailing L1")
    return L


# ============================================================ S9 ============
def s9_vol(case, put):
    L = ["S9 VOL STATE"]
    d = case.dec_sec
    cells = []
    for w in RV_WINDOWS:
        cells.append(MC.fnum(_rv_usd(case, max(0, d - w), d), 10, 1))
    L.append(MC.row("  rv_nowcast_$ ", *([MC.fstr("w%d" % w, 10) for w in RV_WINDOWS])))
    L.append(MC.row("               ", *cells))
    put("S9.rv300_usd", _rv_usd(case, max(0, d - 300), d), "derived",
        "sqrt(sum d(mid)^2)*mult over SANE seconds")

    bv, jf = _bipower(case, max(0, d - 1800), d)
    L.append(MC.row("  bipower_1800s", MC.fnum(bv, 10, 1),
                    " jump_frac=", MC.fnum(jf, 6, 3)))
    put("S9.jump_frac_1800s", jf, "derived", "(RV-BV)/RV over 1800s")

    # vol-of-vol: dispersion of consecutive 300s rv nowcasts over the last 30m
    seq = [_rv_usd(case, max(0, d - k - 300), d - k) for k in
           (0, 300, 600, 900, 1200, 1500)]
    seq = [v for v in seq if np.isfinite(v)]
    vov = (float(np.std(seq)) / float(np.mean(seq))
           if len(seq) >= 3 and np.mean(seq) > 0 else float("nan"))
    L.append(MC.row("  vol_of_vol", MC.fnum(vov, 8, 3),
                    " (cv of six 300s rv nowcasts over the last 30m, n=" + str(len(seq)) + ")"))

    fs = case.fvol_seg
    if fs is None:
        L.append("  fvol            " + MC.NA + "  no forecast row")
        return L
    sig = A._f(fs["sigma_hat_usd"])
    seg_start = 0
    pb = _phase_bounds(case.s)
    for code, st, en in pb:
        if st <= d < en:
            seg_start = st
    hl = _hi_lo(case, seg_start, d)
    realized = usd(case, hl[0] - hl[2]) if hl else float("nan")
    L.append(MC.row("  fvol", "segment=" + X.PHASE_NAMES[case.phase_dec],
                    " sigma_hat=$" + MC.fnum(sig, 1, 1).strip(),
                    " range_hat=$" + MC.fnum(A._f(fs["range_hat_usd"]), 1, 1).strip(),
                    " realized_range_so_far=$" + MC.fnum(realized, 1, 1).strip(),
                    " surprise=" + MC.fnum(realized / A._f(fs["range_hat_usd"])
                                           if A._f(fs["range_hat_usd"]) else float("nan"), 1, 3).strip()))
    lad = [(q, A._f(fs.get("move_%s_usd_per_sigma" % q)) * sig)
           for q in ("q10", "q25", "q50", "q75", "q90")]
    L.append(MC.row("  move_ladder_$", *[MC.fstr("%s=%s" % (q, MC.fnum(v, 1, 0).strip()), 12)
                                         for q, v in lad]))
    band = "below_q10"
    for q, v in lad:
        if np.isfinite(realized) and realized >= v:
            band = "at_or_above_" + q
    L.append(MC.row("  ladder_position", MC.fstr(band, 18),
                    " (realized segment range vs the calibrated move ladder)"))
    put("S9.ladder_position", band, case.fvol_path, "move_q*_usd_per_sigma")
    for q, v in lad:
        put("S9.move_%s_usd" % q, v, case.fvol_path,
            "move_%s_usd_per_sigma*sigma_hat_usd" % q)

    ev = case.events
    if ev is not None and ev["ts_ns"].size:
        ts = ev["ts_ns"]
        rates = []
        for w in (60, 300):
            lo = int(np.searchsorted(ts, (case.decision_ts - w) * 10 ** 9,
                                     side="left"))
            hi = int(np.searchsorted(ts, (case.decision_ts + 1) * 10 ** 9,
                                     side="left"))
            rates.append((hi - lo) / float(w))
        L.append(MC.row("  event_intensity", "ev/s_60s=" + MC.fnum(rates[0], 1, 2).strip(),
                        " ev/s_300s=" + MC.fnum(rates[1], 1, 2).strip(),
                        " ratio=" + MC.fnum(rates[0] / rates[1] if rates[1] else float("nan"), 1, 2).strip()))
        put("S9.events_per_sec_60s", rates[0], "derived(events npz)", "count/60")
    return L


# ============================================================ S10 ===========
def s10_profile(case, put):
    L = ["S10 VOLUME PROFILE"]
    if case.profile is None:
        L.append("  " + MC.NA + "  no profile receipt at %s" % case.profile_path)
        return L
    z = case.profile
    d = case.dec_sec
    tick = case.tick_px

    def px_of(bin0, t):
        return (float(bin0) + float(t)) * tick if np.isfinite(t) else float("nan")

    ds = z["dev_sec"]
    j = int(np.searchsorted(ds, d, side="left")) - 1
    if j >= 0:
        case.guard.sec(int(ds[j]) + 1, "S10 developing profile")
        b0 = float(z["SESSION_bin0"])
        poc = (b0 + float(z["dev_poc_tick"][j])) * tick
        vah = (b0 + float(z["dev_vah_tick"][j])) * tick
        val = (b0 + float(z["dev_val_tick"][j])) * tick
        L.append(MC.row("  developing", "as_of=" + MC.fsec(int(ds[j])),
                        " POC=" + MC.fnum(poc, 1, 4).strip(),
                        " VAH=" + MC.fnum(vah, 1, 4).strip(),
                        " VAL=" + MC.fnum(val, 1, 4).strip(),
                        " d_POC=$" + MC.fnum(usd(case, case.entry_mid - poc), 1, 1).strip(),
                        " in_VA=" + ("1" if val <= case.entry_mid <= vah else "0")))
        put("S10.dev_poc", poc, case.profile_path, "dev_poc_tick[%d]" % j)
        put("S10.dev_vah", vah, case.profile_path, "dev_vah_tick[%d]" % j)
        put("S10.dev_val", val, case.profile_path, "dev_val_tick[%d]" % j)
        put("S10.dev_sec", int(ds[j]), case.profile_path, "dev_sec[%d]" % j)
    else:
        L.append("  developing      " + MC.NA + "  no causal developing-VA row "
                 "before the decision second")

    # completed phases of THIS session (a phase object is causal once its last
    # second has passed)
    for code, st, en in _phase_bounds(case.s):
        name = X.PHASE_NAMES[code]
        if en > d:
            continue
        b0 = float(z["%s_bin0" % name])
        L.append(MC.row("  phase_final", MC.fstr(name, 7),
                        "end=" + MC.fsec(en - 1),
                        " POC=" + MC.fnum(px_of(b0, float(z["%s_poc_tick" % name])), 1, 4).strip(),
                        " VAH=" + MC.fnum(px_of(b0, float(z["%s_vah_tick" % name])), 1, 4).strip(),
                        " VAL=" + MC.fnum(px_of(b0, float(z["%s_val_tick" % name])), 1, 4).strip(),
                        " poor_H=" + str(int(z["%s_poor_high" % name])),
                        " poor_L=" + str(int(z["%s_poor_low" % name]))))

    pz = case.prior_profile
    if pz is not None:
        b0 = float(pz["SESSION_bin0"])
        poc = px_of(b0, float(pz["SESSION_poc_tick"]))
        vah = px_of(b0, float(pz["SESSION_vah_tick"]))
        val = px_of(b0, float(pz["SESSION_val_tick"]))
        L.append(MC.row("  prior_session", str(case.prior_d8),
                        " POC=" + MC.fnum(poc, 1, 4).strip(),
                        " VAH=" + MC.fnum(vah, 1, 4).strip(),
                        " VAL=" + MC.fnum(val, 1, 4).strip(),
                        " d_POC=$" + MC.fnum(usd(case, case.entry_mid - poc), 1, 1).strip(),
                        " poor_H=" + str(int(pz["SESSION_poor_high"])),
                        " poor_L=" + str(int(pz["SESSION_poor_low"]))))
        put("S10.prior_session_poc", poc, case.prior_profile_path,
            "SESSION_poc_tick")
        hv = [(b0 + float(t)) * tick for t in pz["SESSION_hvn_ticks"].tolist()]
        lv = [(b0 + float(t)) * tick for t in pz["SESSION_lvn_ticks"].tolist()]
        sp = [(b0 + float(t)) * tick for t in
              pz["SESSION_single_print_ticks"].tolist()]
        L.append(MC.row("    HVN_d$", *[MC.fnum(usd(case, case.entry_mid - p), 9, 0)
                                        for p in hv[:6]]))
        L.append(MC.row("    LVN_d$", *[MC.fnum(usd(case, case.entry_mid - p), 9, 0)
                                        for p in lv[:6]]))
        L.append(MC.row("    single_prints", "n=" + str(len(sp)),
                        " nearest_d$=" + MC.fnum(
                            min((usd(case, case.entry_mid - p) for p in sp),
                                key=abs) if sp else float("nan"), 1, 0).strip()))
    else:
        L.append("  prior_session   " + MC.NA + "  no prior profile receipt")
    return L


# ============================================================ S11 ===========
def s11_cross(case, put):
    L = ["S11 CROSS-ASSET (concurrent, same UTC second, each asset's own SANE mid)"]
    L.append("    asset  own_sec       mid   ret_sess%  ret_phase%   range$  coverage%  first_move_sec")
    for a in MC.ASSET_ORDER:
        if a == case.asset:
            continue
        oth = case.cross.get(a)
        if oth is None:
            L.append(MC.row("   ", MC.fstr(a, 5), MC.fstr(MC.NA, 8),
                            " no session receipt for %s on %s"
                            % (a, case.trade_date.isoformat())))
            continue
        os_ = oth["s"]
        o_open = int(os_.meta["open_utc"])
        osec = case.decision_ts - o_open
        if osec < 0 or osec >= os_.n:
            L.append(MC.row("   ", MC.fstr(a, 5), MC.fint(osec, 8),
                            " decision_ts outside %s's session span" % a))
            continue
        jj = int(np.searchsorted(os_.vt, osec, side="right")) - 1
        if jj < 0:
            L.append(MC.row("   ", MC.fstr(a, 5), MC.fint(osec, 8),
                            " no SANE second yet"))
            continue
        mid = float(os_.vm[jj])
        first = float(os_.vm[0])
        pb = _phase_bounds(os_)
        ps = 0
        for code, st, en in pb:
            if st <= osec < en:
                ps = st
        k0 = int(np.searchsorted(os_.vt, ps, side="left"))
        pmid = float(os_.vm[k0]) if k0 < os_.vm.size else float("nan")
        k1 = int(np.searchsorted(os_.vt, osec, side="left"))
        seg = os_.vm[:k1]
        rng = (float(seg.max() - seg.min()) * C.ASSETS[a]["mult"]
               if seg.size else float("nan"))
        ofv = A.fvol_rows().get((a, case.trade_date.isoformat(),
                                 X.PHASE_NAMES[int(os_.phase_tag[osec])]))
        q50 = (A._f(ofv["move_q50_usd_per_sigma"]) * A._f(ofv["sigma_hat_usd"])
               if ofv else float("nan"))
        # who-moved-first: the second of each asset's largest 60s |move| inside
        # the last 300s (ties -> earlier second)
        fm = _first_move_sec(os_, osec)
        L.append(MC.row("   ", MC.fstr(a, 5), MC.fint(osec, 8),
                        MC.fnum(mid, 10, 4),
                        MC.fnum(100.0 * (mid / first - 1.0) if first else float("nan"), 10, 3),
                        MC.fnum(100.0 * (mid / pmid - 1.0) if pmid else float("nan"), 11, 3),
                        MC.fnum(rng, 8, 0),
                        MC.fnum(100.0 * rng / q50 if (np.isfinite(q50) and q50) else float("nan"), 10, 1),
                        MC.fsec(fm) if fm is not None else MC.NA.rjust(8)))
        put("S11.%s_mid" % a, mid, oth["path"], "g0_mid[%d]" % osec)
        put("S11.%s_coverage_pct" % a,
            100.0 * rng / q50 if (np.isfinite(q50) and q50) else float("nan"),
            "derived", "own range / own move_q50")
    own = _first_move_sec(case.s, case.dec_sec)
    L.append(MC.row("   ", MC.fstr(case.asset, 5), MC.fint(case.dec_sec, 8),
                    MC.fnum(case.entry_mid, 10, 4),
                    MC.fstr("(self)", 10), MC.fstr("", 11), MC.fstr("", 8),
                    MC.fstr("", 10),
                    MC.fsec(own) if own is not None else MC.NA.rjust(8)))
    return L


def _first_move_sec(s, sec):
    """Second of the largest 60s absolute mid move inside the last 300s."""
    lo = max(0, sec - 300)
    a = int(np.searchsorted(s.vt, lo, side="left"))
    b = int(np.searchsorted(s.vt, sec, side="left"))
    if b - a < 3:
        return None
    t = s.vt[a:b]
    v = s.vm[a:b]
    best_i, best_d = None, -1.0
    for i in range(t.size):
        j = int(np.searchsorted(t, int(t[i]) - 60, side="left"))
        if j >= i:
            continue
        dd = abs(float(v[i]) - float(v[j]))
        if dd > best_d:
            best_d, best_i = dd, i
    return int(t[best_i]) if best_i is not None else None


# ============================================================ S12 ===========
def s12_context(case, put):
    L = ["S12 CONTEXT (D-057 availability-lagged; strict availability_ts < "
         "decision_ts)"]
    L.append("  decision_ts = %s (%d); avail = availability_ts as "
             "YYYYMMDDTHHMM UTC; rules in AVAILABILITY_LAGS.tsv"
             % (MC.futc(case.decision_ts), case.decision_ts))
    L.append("    series                stamp        avail          age_d  value")
    g = case.guard
    n_ok = n_ref = 0
    for sid in CTX.ASSET_SERIES[case.asset]:
        ser = CTX.series(sid)
        rec = ser.latest(g)
        if rec is None:
            n_ref += 1
            L.append(MC.row("   ", MC.fstr(sid, 20), MC.fstr(MC.NA, 12),
                            MC.fstr("REFUSED", 14), MC.fstr(MC.NA, 6),
                            "no observation available at decision_ts under "
                            "%s (n_future=%d)" % (ser.rule, ser.n_future(g))))
            continue
        n_ok += 1
        age = (case.decision_ts - rec["availability_ts"]) / 86400.0
        vals = rec["values"]
        if sid.startswith("COT_"):
            prev = ser.latest(g, back=1)
            dnet = (vals[0] - prev["values"][0]) if prev else float("nan")
            txt = ("net=%s long=%s short=%s OI=%s d_net_wk=%s"
                   % (MC.fnum(vals[0], 1, 0).strip(),
                      MC.fnum(vals[1], 1, 0).strip(),
                      MC.fnum(vals[2], 1, 0).strip(),
                      MC.fnum(vals[3], 1, 0).strip(),
                      MC.fnum(dnet, 1, 0).strip()))
            put("S12.%s_net" % sid, vals[0], ser.source, "managed/leveraged net")
        elif sid == "GOLD_SILVER_RATIO":
            txt = ("ratio=%s gc=%s si=%s"
                   % (MC.fnum(vals[0], 1, 3).strip(),
                      MC.fnum(vals[1], 1, 2).strip(),
                      MC.fnum(vals[2], 1, 3).strip()))
            put("S12.gold_silver_ratio", vals[0], ser.source, "GC close/SI close")
        else:
            txt = " ".join(MC.fnum(v, 1, 4).strip() for v in vals)
            put("S12.%s" % sid, vals[0], ser.source, ser.unit)
        av = dt.datetime.utcfromtimestamp(rec["availability_ts"]).strftime(
            "%Y%m%dT%H%M")
        L.append(MC.row("   ", MC.fstr(sid, 20),
                        MC.fstr(rec["stamp_date"].isoformat(), 12),
                        MC.fstr(av, 14),
                        MC.fnum(age, 6, 1), txt))
    nxt = CTX.next_release(g, case.asset)
    if nxt:
        cd = nxt["countdown_sec"]
        L.append(MC.row("  next_scheduled", MC.fstr(nxt["name"], 22),
                        MC.futc(nxt["event_ts"]),
                        " in " + "%dd %02d:%02d:%02d" % (cd // 86400,
                                                         (cd // 3600) % 24,
                                                         (cd // 60) % 60,
                                                         cd % 60),
                        " status=" + nxt["status"],
                        " (SCHEDULE_EXEMPT)"))
        put("S12.next_release_countdown_sec", cd,
            "port_context/bls_calendar+calendar_fomc", "scheduled, exempt")
    rec = CTX.recent_release(g, case.asset)
    if rec:
        L.append(MC.row("  last_scheduled", MC.fstr(rec["name"], 22),
                        MC.futc(rec["event_ts"]),
                        " " + str(rec["since_sec"]) + "s ago",
                        " status=" + rec["status"]))
    L.append(MC.row("  availability_summary", "n_joined=" + str(n_ok),
                    " n_refused=" + str(n_ref),
                    " lag_table=artifacts/reference/port_context/"
                    "AVAILABILITY_LAGS.tsv"))
    put("S12.n_series_joined", n_ok, "derived", "count")
    put("S12.n_series_refused", n_ref, "derived", "count")
    return L


# ============================================================ S13 ===========
def s13_mechanics(case, put):
    L = ["S13 CANDIDATE MECHANICS"]
    L.append(MC.row("  entry", "mid=" + MC.fnum(case.entry_mid, 1, 4).strip(),
                    " side=" + ("LONG" if case.side > 0 else "SHORT"),
                    " spread_at_decision=$" + MC.fnum(case.spread_dec, 1, 2).strip(),
                    " cost_rt=$" + MC.fnum(case.cost_rt, 1, 2).strip(),
                    " tick=$" + MC.fnum(case.tick_usd, 1, 2).strip(),
                    " mult=" + str(case.mult)))
    put("S13.spread_at_decision", case.spread_dec, case.roster_path,
        "spread_at_decision[%d]" % case.i)
    put("S13.cost_rt", case.cost_rt,
        os.path.join(MC.M0_ROOT, "census_a_cost.tsv"), "cost_rt[phase=ALL]")
    L.append(MC.row("  exit_default", "phase_close@" + MC.fsec(case.phase_close_sec),
                    " (" + str(case.phase_close_sec - case.dec_sec) + "s)",
                    " session_close@" + MC.fsec(case.sess_close_sec),
                    " wall=$" + MC.fnum(case.wall, 1, 2).strip(),
                    " (min(round25(p99 winner MAE), $%.0f))" % MC.WALL_CAP))
    put("S13.wall_usd", case.wall, os.path.join(MC.M0_ROOT, "walls.json"),
        "walls.%s.wall_usd" % case.asset)
    L.append(MC.row("  generation", "families=" + ",".join(MC.fam_names(case.fam_mask)),
                    " rungs=" + ",".join(MC.rung_names(case.rung_mask)) + " xATR",
                    " level_families=" + (",".join(MC.level_fam_names(case.level_mask)) or "none"),
                    " conf_sec=" + MC.fsec(case.conf_sec),
                    " lag=" + str(case.dec_sec - case.conf_sec) + "s"))
    fc = A.family_census()
    L.append("  CENSUS CARD (committed censuses, generation_v3)")
    L.append("    family        era              n_cand  n_pos  cond_value$  mean_cert$  pos_frac  cond_peak$")
    yr = str(case.trade_date.year)
    blk = X.ERA_FIT if case.trade_date.year in X.WALL_FIT_YEARS else X.ERA_GATE
    for fam in MC.fam_names(case.fam_mask):
        for era in (yr, blk):
            r = fc.get((case.asset, fam, era))
            if r is None:
                continue
            L.append(MC.row("   ", MC.fstr(fam, 13), MC.fstr(era, 16),
                            MC.fint(r["n_candidates"], 7),
                            MC.fint(r["n_positive"], 6),
                            MC.fnum(A._f(r["conditional_value_usd"]), 12, 2),
                            MC.fnum(A._f(r["mean_cert_usd"]), 11, 2),
                            MC.fnum(A._f(r["positive_frac"]), 9, 4),
                            MC.fnum(A._f(r["conditional_value_peak_usd"]), 11, 2)))
            put("S13.census.%s.%s.cond_value" % (fam, era),
                A._f(r["conditional_value_usd"]), A.FAM_VALUE,
                "conditional_value_usd")
    return L


# ============================================================ S14 ===========
def s14_outcomes(case, put):
    """STUDY MODE ONLY.  Rendered into a SEPARATE appendix file that the
    protocol releases only after the call is committed (spec §1 S14 / §3)."""
    L = ["S14 OUTCOMES (STUDY MODE — released only after the call is committed)"]
    r = case.r
    i = case.i
    peak, close = CC.certificates(r, i, case.wall, case.cost_rt)
    L.append(MC.row("  certificates", "peak_exit=$" + MC.fnum(peak[0], 1, 2).strip(),
                    " exit@" + MC.fsec(peak[2]),
                    " seated=" + ("1" if peak[3] else "0"),
                    " | phase_close=$" + MC.fnum(close[0], 1, 2).strip(),
                    " exit@" + MC.fsec(close[2])))
    put("S14.cert_peak_usd", peak[0], case.roster_path,
        "c_c_roster.certificates(wall=%.2f, cost=%.2f)" % (case.wall, case.cost_rt))
    put("S14.cert_close_usd", close[0], case.roster_path,
        "c_c_roster.certificates(wall=%.2f, cost=%.2f)" % (case.wall, case.cost_rt))
    t_wall, mfe_w, argmax_sec, walled = CC._skel_query(r, i, case.wall)
    L.append(MC.row("  wall", "t_wall=" + (MC.fsec(t_wall) if t_wall is not None else MC.NA),
                    " mfe_before_wall=$" + MC.fnum(mfe_w, 1, 2).strip(),
                    " walled=" + ("1" if walled else "0")))
    L.append(MC.row("  unwalled", "mfe=$" + MC.fnum(float(r["mfe_unwalled"][i]), 1, 2).strip(),
                    " argmax@" + MC.fsec(int(r["mfe_argmax_sec"][i])),
                    " mae_before_peak=$" + MC.fnum(float(r["mae_before_argmax"][i]), 1, 2).strip()))
    put("S14.mfe_unwalled", float(r["mfe_unwalled"][i]), case.roster_path,
        "mfe_unwalled[%d]" % i)
    put("S14.mae_before_argmax", float(r["mae_before_argmax"][i]),
        case.roster_path, "mae_before_argmax[%d]" % i)
    L.append(MC.row("  horizons_$", "h30=" + MC.fnum(float(r["f_h30"][i]), 1, 2).strip(),
                    " h60=" + MC.fnum(float(r["f_h60"][i]), 1, 2).strip(),
                    " h120=" + MC.fnum(float(r["f_h120"][i]), 1, 2).strip(),
                    " phase_close=" + MC.fnum(float(r["f_phase_close"][i]), 1, 2).strip(),
                    " sess_close=" + MC.fnum(float(r["f_sess_close"][i]), 1, 2).strip()))
    fo, fl = int(r["f_off"][i]), int(r["f_len"][i])
    ao, al = int(r["a_off"][i]), int(r["a_len"][i])
    L.append("  PATH LANDMARKS (prefix-maxima skeleton; f = favourable, a = adverse)")
    ft = r["skel_f_t"][fo:fo + fl]
    fv = r["skel_f_v"][fo:fo + fl]
    at = r["skel_a_t"][ao:ao + al]
    av = r["skel_a_v"][ao:ao + al]
    L.append("    f: " + " ".join("%s=%s" % (MC.fsec(int(t)), MC.fnum(float(v), 1, 0).strip())
                                  for t, v in list(zip(ft.tolist(), fv.tolist()))[-10:]))
    L.append("    a: " + " ".join("%s=%s" % (MC.fsec(int(t)), MC.fnum(float(v), 1, 0).strip())
                                  for t, v in list(zip(at.tolist(), av.tolist()))[-10:]))
    L.append(MC.row("    n_f_records", MC.fint(fl, 5), " n_a_records", MC.fint(al, 5)))

    legs = A.oracle_legs(case.asset, case.d8)
    mine = [g for g in legs
            if int(g["leg_start_sec"]) <= case.dec_sec <= int(g["leg_end_sec"])]
    L.append("  ORACLE LEGS covering this decision second (ANCHORED variant)")
    if not mine:
        L.append("    none — this candidate sits outside every scored oracle leg")
    for g in mine:
        L.append(MC.row("   ", MC.fsec(int(g["leg_start_sec"])), "->",
                        MC.fsec(int(g["leg_end_sec"])),
                        " dir=" + g["direction"],
                        " travel=$" + MC.fnum(A._f(g["travel_usd"]), 1, 0).strip(),
                        " n_cand=" + g["n_candidates_in_leg"],
                        " same_side=" + g["n_same_side"],
                        " captured@1k=" + g["captured_1000"],
                        " capture_dec_sec=" + (g["capture_dec_sec"] or MC.NA),
                        " miss=" + (g["miss_tag"] or "-")))
        put("S14.oracle_leg_travel_usd", A._f(g["travel_usd"]), A.ORACLE_LEGS,
            "travel_usd")
    seated, dp_total, rank = _dp_seat(case)
    L.append(MC.row("  one_position_DP", "seated=" + ("1" if seated else "0"),
                    " session_dp_total=$" + MC.fnum(dp_total, 1, 2).strip(),
                    " seated_items=" + str(rank),
                    " (phase-close certificates, c_c_roster.dp_schedule)"))
    put("S14.dp_seated", 1 if seated else 0, case.roster_path,
        "c_c_roster.dp_schedule over the session's phase-close certificates")
    return L


def _dp_seat(case):
    """Was this candidate seated by the one-position DP over its session?"""
    r = case.r
    idx = np.nonzero(r["date8"] == case.d8)[0]
    items = []
    for i in idx.tolist():
        _, close = CC.certificates(r, i, case.wall, case.cost_rt)
        val, dec, exit_sec, _ = close
        items.append((dec, exit_sec, val, dec, int(r["iid"][i]), i))
    total, chosen = CC.dp_schedule(items)
    return (case.i in set(chosen)), total, len(chosen)


# ============================================================ registry ======
RENDERERS = {
    "S2": s2_regime, "S3": s3_path, "S4": s4_levels, "S5": s5_tminus,
    "S6": s6_ribbon, "S7": s7_book, "S8": s8_flow, "S9": s9_vol,
    "S10": s10_profile, "S11": s11_cross, "S12": s12_context,
    "S13": s13_mechanics, "S14": s14_outcomes,
}
