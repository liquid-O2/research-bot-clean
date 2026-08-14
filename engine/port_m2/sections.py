#!/usr/bin/python3
"""PORT M2 — the 14 section renderers (design/PORT_M2_SHEETS_SPEC.md §1).

One function per section, each returning a list of already-formatted lines and
recording every number it prints into the sidecar through `put`.

Causality is not a convention here, it is a call: every session-clock read goes
through Case.guard.sec / Case.guard.at_decision, every wall-clock read through
AvailSeries.latest(guard).  A section that needs a datum it cannot lawfully see
prints the typed-missing glyph and says WHY — it never prints a zero.

REFUSED CONSISTENCY (V1.1, P-M2c defect D1).  The rule above extends down the
derivation chain: ANY derived field whose inputs are refused is itself REFUSED —
it prints the typed-missing glyph, it says which input was refused, and it is
COUNTED in the sheet's certificate through `put.refuse(key, reason)`.  A band, a
label, a flag or a ratio computed from a missing input is a fabricated number,
and the warm-up found one live (`S9 ladder_position` asserting `below_q10` while
every `move_ladder` quantile printed `.`).  Every site that turns numbers into a
categorical answer is listed in the V1.1 sweep: S2.day_type_so_far,
S3.COVERAGE(+exp_move_q50), S4.OR STATE, S9.move_ladder/ladder_position,
S10.in_VA, S11.coverage%.
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
import availability as AV                 # noqa: E402
import class_census as CLS                # noqa: E402
import session_close as SC                # noqa: E402

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

# S5 CLOCK-NORM SCALE FLOOR (V1.1, P-M2c defect D3).  The z column is
# median/MAD already, but an unfloored MAD explodes on a near-degenerate clock
# cell: the warm-up measured `trades/min z=+102.76` where the trailing
# same-half-hour cell is almost constant.  The scale is therefore floored per
# field at max(MAD, MAD_FLOOR_FRAC x |median|, field epsilon), where the field
# epsilon is HALF THE MEASUREMENT QUANTUM of the quantity (sizes and counts are
# integers; a spread cannot resolve below a tick).  A z whose scale came from
# the floor carries a '~' suffix and is ORDINAL ONLY — never a threshold.
MAD_FLOOR_FRAC = 0.05
MAD_FLOOR_EPS = {"bid_sz": 0.5, "ask_sz": 0.5, "trades_per_min": 0.5,
                 "abs_sflow_per_min": 0.5}   # spread_usd: half a tick, per case
MAD_SCALE = 1.4826                        # MAD -> sd-equivalent

# S7 REFILL-AFTER-TRADE (V1.1, P-M2c defect D2).  See _refill_after_trade.
REFILL_WINDOW_SEC = 5
REFILL_LOOKBACK_SEC = 300

TMINUS_MARKS = (1800, 900, 300, 60, 0)
FLOW_WINDOWS = (60, 300, 1800)          # THE flow windows; s8_flow
                                        # hardcoded the same tuple
                                        # inline (the D24 shape) and
                                        # now reads this one
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
    mult = float(C.ASSETS[asset]["mult"])
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
        # R99: spec §1 S5 names "RV nowcast" among the z-scored quantities and
        # the clock-norm digest carried no RV entry at all, so `rv300_$` could
        # never be z-scored.  The bin's realised volatility is computed on the
        # SANE mids of the bin, in dollars, on the same 300s scale the sheet
        # prints, so the two are comparable.
        mv = np.nonzero(m)[0]
        if mv.size >= 2:
            dm = np.diff(s.mid[mv].astype(np.float64))
            rvb = float(np.sqrt(np.sum(dm * dm)) * mult
                        * np.sqrt(300.0 / max(1.0, float(mv.size))))
        else:
            rvb = float("nan")
        out[bi] = {
            "spread_usd": float(np.median(s.spread_usd[m])),
            "bid_sz": float(np.median(s.bid_sz[m])),
            "ask_sz": float(np.median(s.ask_sz[m])),
            "trades_per_min": (t1 - t0) / span_min,
            "abs_sflow_per_min": abs(sf) / span_min,
            "rv300_usd": rvb,
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


def clock_pct(case, bin_idx, field, x):
    """PERCENTILE RANK of `x` among the trailing same-half-hour sessions.

    V1.2, queued at CC-M2-7.3 with the render bundle and never landed.  It is
    the reading a '~'-marked z is ORDINAL-ONLY for: well defined whether or not
    the MAD floor binds, and never a threshold on a degenerate scale.  Returns
    NaN below the same 10-session floor `clock_norm` uses.
    """
    if not np.isfinite(x):
        return float("nan")
    ds = sorted(A.session_index(case.asset))
    i = bisect.bisect_left(ds, case.d8)
    prev = ds[max(0, i - CLOCKNORM_SESSIONS):i]
    vals = []
    for p in prev:
        st = _session_bin_stats(case.asset, p)
        if st and bin_idx in st:
            v = st[bin_idx].get(field)
            if v is not None and np.isfinite(v):
                vals.append(float(v))
    if len(vals) < 10:
        return float("nan")
    a = np.asarray(vals, dtype=np.float64)
    # mid-rank convention: ties contribute half, so the statistic is the
    # standard empirical CDF at x and is deterministic.
    return float(100.0 * ((a < x).sum() + 0.5 * (a == x).sum()) / a.size)


def _mad_eps(case, field):
    """Half the measurement quantum of a clock-norm field, in the field's own
    units — the hard floor under the robust scale."""
    if field == "spread_usd":
        return 0.5 * case.tick_usd
    return MAD_FLOOR_EPS.get(field, 0.0)


def _z(x, med, mad, eps=0.0):
    """Robust z with a FLOORED scale.  Returns (z, floor_binds).

    scale = max(MAD, MAD_FLOOR_FRAC x |median|, eps); a near-degenerate clock
    cell can drive MAD to zero (or to one tick), which turns an ordinary
    observation into a z of +100 and invites exactly the threshold reading the
    quantity cannot support.  `floor_binds` marks the value '~' on the sheet.
    """
    if not np.isfinite(x) or not np.isfinite(med) or not np.isfinite(mad):
        return float("nan"), False
    scale = max(mad, MAD_FLOOR_FRAC * abs(med), float(eps))
    if scale <= 0:
        return float("nan"), False
    return (x - med) / (MAD_SCALE * scale), bool(scale > mad)


# ============================================================ S2 ============
def s2_regime(case, put):
    L = ["S2 ERA PRIMER REF + REGIME TAGS"]
    era = case.era
    L.append(MC.row("  era", MC.fstr(era, 16),
                    "primer=ERA_PRIMER_%s.md (spec S3, auto-generated per era "
                    "from committed censuses)" % era))
    put("S2.era", era, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "m2_common.py"), "ERAS")

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
    if np.isfinite(frac):
        put("S2.day_type_frac", frac, "derived", "range_so_far/range_hat")
    else:
        put.refuse("S2.day_type_frac",
                   "range_hat REFUSED in the fvol receipt: day_type_so_far "
                   "cannot be derived")

    # R94.  Four session-meta fields printed here were NOT knowable at the
    # decision and none was in KNOWN_TRAPS:
    #   dom_share            s3_sessions.py:335 — the dominant instrument's
    #                        share of the WHOLE session's two-sided seconds
    #   roll_window          s3_sessions.py:365 — an instrument change in the
    #                        NEXT 5 sessions
    #   dying_book_week      s3_sessions.py:366 — same, a pure FORWARD flag and
    #                        the sheet's one NKD-specific regime tag
    #   instrument_change    s3_sessions.py:361 — end-of-session
    # They sat immediately beside S2's correctly-causal insane-episode counters,
    # which made them read as causal too.  They are REFUSED here — declared and
    # counted in the S1 certificate, never silently dropped.  `iid` stays: the
    # dominant instrument's IDENTITY is known when the session opens.
    L.extend(_s2_forward_meta(case, put))

    # insane-book episodes SO FAR (causal): runs of two-sided-but-insane seconds
    ts = (case.s.state[:case.dec_sec] == C.ST_TWO_SIDED)
    ins = ts & (~case.s.valid[:case.dec_sec])
    n_ins = int(ins.sum())
    eps = int(np.sum(ins[1:] & ~ins[:-1])) + (1 if ins.size and ins[0] else 0)
    # R94 (fourth field): `session_insane_frac` is b7_sane's END-OF-SESSION
    # fraction over the full session.  The three counters beside it are causal
    # (they slice [:dec_sec]); this one was not.  The causal analogue — the
    # insane fraction SO FAR — is printed in its place.
    frac_sf = (float(n_ins) / float(ts.sum())) if int(ts.sum()) > 0 \
        else float("nan")
    L.append(MC.row("  insane_book", "episodes_so_far=" + str(eps),
                    " insane_sec_so_far=" + str(n_ins),
                    " two_sided_sec_so_far=" + str(int(ts.sum())),
                    " insane_frac_so_far=" + MC.fnum(frac_sf, 8, 6).strip()))
    put("S2.insane_episodes_so_far", eps, "derived(b7_sane mask)",
        "state==TWO_SIDED & ~valid, sec<dec")
    put("S2.insane_sec_so_far", n_ins, "derived(b7_sane mask)", "count")
    if np.isfinite(frac_sf):
        put("S2.insane_frac_so_far", frac_sf, "derived(b7_sane mask)",
            "insane_sec_so_far / two_sided_sec_so_far")
    else:
        put.refuse("S2.insane_frac_so_far",
                   "no two-sided second before the decision second")
    return L


# ============================================================ S3 ============
S2_FORWARD_META = (
    ("S2.dominant_share", "dom_share",
     "dominant_share is the WHOLE session's two-sided share "
     "(s3_sessions.py:335) — not knowable at the decision second"),
    ("S2.roll_window", "roll_window",
     "roll_window looks 5 sessions FORWARD (s3_sessions.py:365)"),
    ("S2.dying_book_week", "dying_book_week",
     "dying_book_week looks 5 sessions FORWARD (s3_sessions.py:366)"),
    ("S2.instrument_change", "instrument_change",
     "instrument_change is an end-of-session fact (s3_sessions.py:361)"),
)


def _s2_forward_meta(case, put):
    """R94, extracted so the fixture can drive it: the four whole-session /
    strictly-forward session-meta fields are REFUSED, and only `iid` — the
    dominant instrument's IDENTITY, known when the session opens — prints."""
    cells = ["  dominance", "iid=" + str(case.s.iid)]
    for key, label, why in S2_FORWARD_META:
        cells.append("  " + label + "=" + MC.NA)
        put.refuse(key, why)
    cells.append("  (whole-session/forward facts: REFUSED, D-057)")
    return [MC.row(*cells)]


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
    # D15 / V1.2 (queued at CC-M2-12.2, never landed).  The runway printed here
    # is the SCHEDULED one (c_c_roster.py:294 `sc_sec = s.n - 1`), and on an
    # early-close session it is wrong by HOURS — HG 2021-07-05's tape stops at
    # 71,354s while the sheet computes to 82,799s, so a 12,000s floor admits
    # seats that cannot reach their exit.  THIS session's observed close is an
    # end-of-session fact and may never be printed; the trailing shortfall over
    # this asset's STRICTLY PRIOR sessions is knowable, and is what the reader
    # gets.  `runway_to_seat` is the program's central conditioning object
    # (CC-M2-15.1), so the nominal number is now labelled as nominal.
    sf_med, sf_n = SC.trailing_shortfall(case.asset, case.d8)
    L.append(MC.row("  runway", "to_phase_close=" + str(case.phase_close_sec - case.dec_sec) + "s",
                    " (" + MC.fsec(case.phase_close_sec) + ", SCHEDULED)",
                    " to_sess_close=" + str(case.sess_close_sec - case.dec_sec) + "s",
                    " (" + MC.fsec(case.sess_close_sec) + ", SCHEDULED)"))
    L.append(MC.row("  runway_prior", "trailing_close_shortfall_med="
                    + (MC.fnum(sf_med, 1, 0).strip() if np.isfinite(sf_med)
                       else MC.NA) + "s",
                    " over n=" + str(sf_n) + " strictly-prior sessions",
                    " => expected_to_sess_close="
                    + (str(int(case.sess_close_sec - case.dec_sec
                               - round(sf_med))) + "s"
                       if np.isfinite(sf_med) else MC.NA)))
    put("S3.runway_phase_sec", case.phase_close_sec - case.dec_sec,
        case.roster_path, "phase_close_sec[%d]-dec_sec (SCHEDULED)" % case.i)
    if np.isfinite(sf_med):
        put("S3.trailing_close_shortfall_sec", sf_med, SC.path_for(case.asset),
            "median(scheduled-observed close) over the %d strictly-prior "
            "sessions" % sf_n)
    else:
        put.refuse("S3.trailing_close_shortfall_sec",
                   "fewer than %d strictly-prior sessions carry an observed "
                   "close for %s (n=%d): the scheduled runway stands "
                   "UNADJUSTED and is labelled SCHEDULED"
                   % (SC.MIN_TRAILING, case.asset, sf_n))

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
    # REFUSED CONSISTENCY (V1.1 / P-M2c D1): COVERAGE and unspent are DERIVED
    # from exp_move_q50.  When the fvol row carries no move_q50 the whole line
    # is refused, counted, and says so — a `.` with no reason is what sent the
    # warm-up reader looking for a band the receipt never had.
    for nm, sp, q in (("SESSION", spent_s, q50_s),
                      (X.PHASE_NAMES[case.phase_dec], spent_p, q50_p)):
        ok = np.isfinite(q) and q > 0
        cov = sp / q if ok else float("nan")
        L.append(MC.row("  COVERAGE", MC.fstr(nm, 8),
                        "range_so_far=$" + MC.fnum(sp, 1, 1).strip(),
                        " exp_move_q50=$" + MC.fnum(q, 1, 1).strip(),
                        " COVERAGE=" + MC.fnum(100.0 * cov, 1, 1).strip() + "%",
                        " unspent=$" + MC.fnum(q - sp, 1, 1).strip(),
                        "" if ok else
                        "  REFUSED: no move_q50_usd_per_sigma in the fvol "
                        "receipt (sigma_source=%s)" % src))
        if ok:
            put("S3.coverage_%s" % nm, cov, "derived",
                "SANE range so far / (move_q50_usd_per_sigma * sigma_hat_usd)")
        else:
            put.refuse("S3.coverage_%s" % nm,
                       "exp_move_q50 REFUSED in the fvol receipt "
                       "(sigma_source=%s)" % src)
    L.append(MC.row("  fvol_source", MC.fstr(src, 16),
                    "(ATR14_RAW_FILL = forecaster fell back to raw ATR14)"))
    if np.isfinite(q50_s):
        put("S3.exp_move_q50_session_usd", q50_s, case.fvol_path,
            "move_q50_usd_per_sigma*sigma_hat_usd [SESSION]")
    else:
        put.refuse("S3.exp_move_q50_session_usd",
                   "move_q50_usd_per_sigma REFUSED in the fvol receipt "
                   "(sigma_source=%s)" % src)

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
_OR_CACHE = {}


def _or_window(case, seg, minutes):
    """(OR_high, OR_low, close_sec) of one (segment, OR-minutes) cell, rebuilt
    with b3_levels' OWN construction so the sheet and the ledger cannot drift.
    close_sec is the second the OR_EXT levels are BORN."""
    key = (case.asset, int(case.d8), seg, int(minutes))
    if key not in _OR_CACHE:
        if len(_OR_CACHE) > 600:
            for k in list(_OR_CACHE)[:200]:
                _OR_CACHE.pop(k, None)
        _OR_CACHE[key] = B3.or_range(case.s, seg, int(minutes))
    return _OR_CACHE[key]


def _phase_open_sec(s, name):
    w = np.nonzero(s.phase_tag == X.PHASE_NAMES.index(name))[0]
    return int(w[0]) if w.size else -1


def _anchor_birth_sec(s, aname):
    """Session second at which an fvol ANCHOR becomes knowable (-1 = never).

    R93.  `b3_levels.build_levels` anchors every FVOL_BAND / FVOL_LADDER /
    FVOL_LADDER_RS level at one of FOUR points — the prior settle and each of
    TOKYO / LONDON / NY's OPENING MID (`b3_levels.py:239-273`, the anchor
    second is `int(s.vt[j])` at `:248`) — and `levels_v4` persists no
    `active_from`.  These families are STATIC (`dynamic == 0`) and are not
    OR_EXT, so before this clause they fell through to `return 0` and printed
    as live rows on decisions HOURS BEFORE their anchor existed.

    The birth second is rebuilt with b3's own construction so sheet and ledger
    cannot drift.  `case.s` is B7-masked (D-054) while b3 read raw ticks, so
    where the two differ this returns a LATER second — the refusing direction.
    """
    if not str(aname).startswith("OPEN_"):
        return 0                       # SETTLE: a prior-session object
    seg = str(aname)[5:]
    o = _phase_open_sec(s, seg) if seg in X.PHASE_NAMES else -1
    if o < 0:
        return -1
    j = int(np.searchsorted(s.vt, o, side="left"))
    if j >= s.vt.size:
        return -1
    return int(s.vt[j])


def _level_birth_sec(case, fam, lid, dyn):
    """Session second at which a ledger level BEGINS TO EXIST (-1 = never).

    P-M2c defect D4, root cause.  levels_v4 is written per SESSION and stores
    no `active_from`, so S4 was rendering EVERY row of the ledger regardless of
    when its source came into being.  Most families are born at second 0 (they
    are prior-session objects), but two are not:

      * OR_EXT  — born when its segment's opening range CLOSES.  A TOKYO-phase
        decision was therefore shown LONDON|OR30 and NY|OR30 prices built from
        ranges that had not happened yet: not "unlabelled prior-day values" as
        the warm-up reader charitably assumed, but same-session FORWARD data.
      * the dynamic families (VWAP, DEV_POC) — the stored price is the series
        value at the scope's first second, so a phase-scoped VWAP carries that
        phase's opening VWAP, again forward for an earlier-phase decision.

    The birth second is recomputed here from the session itself and every level
    goes through case.guard.sec, so the causality audit stays one grep.
    """
    parts = str(lid).split("|")
    if fam == "OR_EXT":
        if len(parts) == 5 and parts[2].startswith("OR"):
            return int(_or_window(case, parts[1], int(parts[2][2:]))[2])
        return -1
    if int(dyn):
        if fam == "DEV_POC":
            ds = None if case.profile is None else case.profile.get("dev_sec")
            return int(ds[0]) if ds is not None and len(ds) else -1
        if len(parts) >= 2 and parts[1] in X.PHASE_NAMES:
            return _phase_open_sec(case.s, parts[1])
    # R93: the STATIC fvol families are anchored at a phase OPENING MID.  This
    # clause is the D4 fall-through the original fix missed.
    if fam in ("FVOL_BAND", "FVOL_LADDER", "FVOL_LADDER_RS"):
        if len(parts) >= 2:
            return _anchor_birth_sec(case.s, parts[1])
        return -1
    return 0


def _prior_snapshot_state(z, n, dec_sec):
    """(have_snap, virgin0, tc0) from the LATEST snapshot STRICTLY BEFORE
    `dec_sec` — R96's fix, extracted so the fixture can drive it directly.

    `have_snap[r]` False means the level's PRIOR STATE IS UNKNOWN.  It is a
    refusal at the print site; it is never a virgin level with zero touches,
    which is what the pre-fix `open_rows = np.nonzero(ss == 0)[0]` plus
    `np.ones/np.zeros` initialisation silently asserted.
    """
    virgin0 = np.ones(n, dtype=bool)
    tc0 = np.zeros(n, dtype=np.int64)
    have_snap = np.zeros(n, dtype=bool)
    best_snap = np.full(n, -1, dtype=np.int64)
    ss = np.asarray(z["snap_sec"])
    sr = np.asarray(z["snap_row"])
    prior_ok = np.nonzero(ss < int(dec_sec))[0]
    for k in prior_ok[np.argsort(ss[prior_ok], kind="stable")].tolist():
        r = int(sr[k])
        sec_k = int(ss[k])
        if sec_k >= best_snap[r]:
            best_snap[r] = sec_k
            have_snap[r] = True
            virgin0[r] = bool(z["snap_virgin"][k])
            tc0[r] = int(z["snap_touch_count"][k])
    return have_snap, virgin0, tc0


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
    # MINOR (R100 list): initialised to zeros, so an UNTOUCHED level
    # printed the outcome NONE rather than the typed-missing glyph —
    # 'never tested' read as 'tested, no reaction'.
    lto = np.full(n, -1, dtype=np.int64)
    pending = np.zeros(n, dtype=bool)
    # R96.  `open_rows = np.nonzero(ss == 0)[0]` read ONLY the session-open
    # snapshot, and `virgin0` / `tc0` were initialised to True / 0 — so every
    # level with no sec-0 snapshot had its PRIOR STATE FABRICATED rather than
    # refused.  Measured on levels_v4/SI/20210811.npz: 107 of 255 levels have
    # no sec-0 snapshot (all OR_EXT, all OPEN_*-anchored FVOL_*, phase-scoped
    # VWAP, DEV_POC), and five of them carry a NON-ZERO prior-session touch
    # count at their first real snapshot — so `V=1` was printed for a level
    # with four prior touches.  A fabricated flag is the one thing spec §1 says
    # a refusal must never become.
    #
    # The state is now taken from the LATEST snapshot STRICTLY BEFORE the
    # decision second (more causal information than sec-0 alone, and never
    # forward), and a level with no such snapshot is REFUSED and COUNTED.
    have_snap, virgin0, tc0 = _prior_snapshot_state(z, n, case.dec_sec)
    n_no_prior = 0
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

    # LEVEL BIRTH GUARD (V1.1 / P-M2c D4): a level that does not exist yet at
    # the decision second is not shown at all.
    dyn = z["dynamic"]
    born = np.array([_level_birth_sec(case, str(fam[r]), str(lid[r]),
                                      int(dyn[r])) for r in range(n)],
                    dtype=np.int64)
    alive = np.array([bool(born[r] >= 0
                           and case.guard.sec(int(born[r]), "S4 level birth"))
                      for r in range(n)], dtype=bool)
    dist = (lpx - mid)
    in_band = np.isfinite(lpx) & (np.abs(dist) <= band)
    n_unborn = int(np.sum(in_band & ~alive))
    sel = np.nonzero(in_band & alive)[0]
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
                    " n_not_yet_born=" + str(n_unborn),
                    " K=kept/r=retired family"))
    # R100: spec §1 S4 names "distance ($ AND ATR)" and "CREATED-WHEN"; the
    # table carried neither, and `created = z["created_d8"]` was read at :564
    # and never used.  Both columns are added here.
    L.append("   K family         level_id                price      d$ dxATR created  V  tc test_m outcome")
    for r in order[:n_show]:
        oc = ("PENDING" if pending[r] else
              MC.TOUCH_OUTCOMES[int(lto[r])] if lto[r] >= 0 else MC.NA)
        if have_snap[r]:
            v = MC.fint(1 if (virgin0[r] and tc[r] == 0) else 0, 2)
            tcs = MC.fint(int(tc0[r] + tc[r]), 3)
        else:
            n_no_prior += 1
            v = MC.fstr(MC.NA, 2)          # R96: REFUSED, never fabricated
            tcs = MC.fstr(MC.NA, 3)
        fname = str(fam[r])
        lidt = str(lid[r])
        if lidt.startswith(fname + "|"):
            lidt = lidt[len(fname) + 1:]
        cd8 = int(created[r])
        cstr = ("TODAY" if cd8 == int(case.d8)
                else (MC.NA if cd8 <= 0 else str(cd8)))
        datr = (usd(case, float(dist[r])) / case.atr
                if np.isfinite(case.atr) and case.atr > 0 else float("nan"))
        L.append(MC.row("  ",
                        "K" if fname in MC.KEPT_LEVEL_FAMILIES else "r",
                        MC.fstr(fname, 14),
                        MC.fstr(lidt, 22),
                        MC.fnum(float(lpx[r]), 9, 4),
                        MC.fnum(usd(case, float(dist[r])), 8, 1),
                        MC.fnum(datr, 5, 2),
                        MC.fstr(cstr, 8),
                        v,
                        tcs,
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
            if have_snap[r] and virgin0[r] and tc[r] == 0:
                e[2] += 1
            if not have_snap[r]:
                n_no_prior += 1
        L.append("    REMAINDER rolled up by family, n/nearest_d$/n_virgin "
                 "(counted, never dropped; n_virgin excludes levels whose "
                 "prior state is REFUSED):")
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
    if n_no_prior:
        put.refuse("S4.prior_state",
                   "%d in-band level(s) carry no ledger snapshot strictly "
                   "before the decision second: VIRGIN and touch_count are "
                   "REFUSED for them, never defaulted to virgin/0 (R96)"
                   % n_no_prior)
    put("S4.n_levels_prior_state_refused", n_no_prior, case.levels_path,
        "in-band levels with no snapshot at sec < dec_sec")

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
        # STATE PER CELL (V1.1 / P-M2c D4).  levels_v4 is SESSION-scoped, so
        # every OR cell in it belongs to TODAY — including the phases that have
        # not opened yet at the decision second.  Those cells are REFUSED (not
        # relabelled): their ranges are same-session forward data.  The state
        # column exists so no reader ever has to infer this from the clock.
        L.append("  OR STATE (opening range per adopted CC-M1-6.1 cell, THIS "
                 "session; state=TODAY once the OR window has closed before "
                 "the decision second, NOT_OPEN = REFUSED, never prior-day)")
        L.append("    cell            state     as_of         OR_H       OR_L"
                 "    range$   d$_to_H   d$_to_L  k_ladder")
        for cname in sorted(cells):
            seg, orm = cname.split("|")
            t1 = int(_or_window(case, seg, int(orm[2:]))[2]) \
                if orm.startswith("OR") else -1
            known = t1 >= 0 and case.guard.sec(t1, "S4 OR window close")
            up = cells[cname].get("+1", {})
            dn = cells[cname].get("-1", {})
            ks = sorted(set(list(up) + list(dn)))
            orh = orl = rng = float("nan")
            if known:
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
                            MC.fstr("TODAY" if known else "NOT_OPEN", 9),
                            MC.fsec(t1) if t1 >= 0 else MC.fstr(MC.NA, 8),
                            MC.fnum(orh, 10, 4), MC.fnum(orl, 10, 4),
                            MC.fnum(usd(case, rng), 9, 1),
                            MC.fnum(usd(case, mid - orh), 9, 1),
                            MC.fnum(usd(case, mid - orl), 9, 1),
                            MC.fstr(",".join("%g" % k for k in ks), 20)))
            key = "S4.or_%s_range_usd" % cname.replace("|", "_")
            if known and np.isfinite(rng):
                put(key, usd(case, rng), case.levels_path,
                    "recovered from the OR_EXT k-ladder level prices")
            elif known:
                # R96: with fewer than two k entries a side the range cannot be
                # recovered.  This recorded `value: null` with NO put.refuse,
                # so the typed-missing glyph never reached the S1 roster.
                put.refuse(key,
                           "the %s k-ladder carries fewer than two entries on "
                           "either side (%d up / %d down): OR_H/OR_L/range are "
                           "not recoverable from it" % (cname, len(up), len(dn)))
            else:
                put.refuse(key, "the %s opening range closes at %s, after the "
                                "decision second" % (cname, MC.fsec(t1).strip()))
    else:
        L.append("  OR STATE         none built for this asset/session "
                 "(CC-M1-6.1 adopted cells: SI 5, NKD 1, HG 0)")
    beyond = MC.bits_to_names(case.flags, MC.FLAG_NAMES)
    L.append(MC.row("  or_ext_flags", MC.fstr(",".join(beyond) if beyond
                                              else "none", 40)))
    return L


# ============================================================ S5 ============
def s5_tminus(case, put):
    L = ["S5 T-MINUS TRAJECTORY (z = (NOW-med)/(%g*MAD) vs the trailing-%d-"
         "session same half-hour; MAD floored at max(%d%% of med, half a "
         "quantum); '~' = floor binds, ORDINAL ONLY)"
         % (MAD_SCALE, CLOCKNORM_SESSIONS, int(100 * MAD_FLOOR_FRAC))]
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

    def emit(name, vals, zfield=None, dec=4, width=10, zval=None):
        cells = [MC.fstr(name, 16)]
        for v in vals:
            cells.append(MC.fnum(v, width, dec))
        zz = float("nan")
        nn = 0
        floored = False
        pct = float("nan")
        # R96: a NON-FINITE now-value skipped clock_norm entirely so NO refusal
        # was recorded, and when clock_norm found ZERO trailing sessions in the
        # bin the refusal branch was skipped too.  Both are refusals now.  And
        # the z VALUE was never put() on success, so S5.z_* existed in the
        # sidecar only as a refusal — a key with no positive counterpart.
        x = vals[-1] if zval is None else zval
        if zfield is not None:
            if not np.isfinite(x):
                put.refuse("S5.z_%s" % zfield,
                           "the NOW value of %s is refused, so its clock-norm "
                           "z cannot be computed" % zfield)
            else:
                med, mad, nn = clock_norm(case, bin_idx, zfield)
                zz, floored = _z(x, med, mad, _mad_eps(case, zfield))
                pct = clock_pct(case, bin_idx, zfield, x)
                if not np.isfinite(zz):
                    put.refuse("S5.z_%s" % zfield,
                               "clock-norm scale REFUSED (median/MAD undefined "
                               "on %d trailing same-half-hour sessions)" % nn)
                else:
                    put("S5.z_%s" % zfield, zz, "derived(clock_norm)",
                        "(NOW-med)/(%g*floored_MAD) over %d trailing "
                        "same-half-hour sessions" % (MAD_SCALE, nn))
                if np.isfinite(pct):
                    # V1.2 (CC-M2-7.3, queued and never landed): the
                    # PERCENTILE-RANK form, which is well defined whether or
                    # not the MAD floor binds and is the reading a '~'-marked
                    # z is only allowed to be used as.
                    put("S5.pct_%s" % zfield, pct, "derived(clock_norm)",
                        "percentile rank of NOW among %d trailing "
                        "same-half-hour sessions" % nn)
        # 7 digits + the marker column keeps the z cell 8 wide either way
        cells.append(MC.fnum(zz, 7, 2) + ("~" if floored else " "))
        cells.append(MC.fnum(pct, 6, 2))
        cells.append(MC.fint(nn, 4) if zfield else MC.NA.rjust(4))
        if zfield is not None and floored:
            put("S5.z_floor_binds.%s" % zfield, 1, "derived",
                "scale = max(MAD, %g*|med|, half-quantum) > MAD"
                % MAD_FLOOR_FRAC)
        L.append(MC.row(*cells))

    L.append(MC.row(MC.fstr("  quantity", 16),
                    *([MC.fstr(h, 10) for h in hdr]
                      + [MC.fstr("z", 8), MC.fstr("pct", 6),
                         MC.fstr("n_ref", 4)])))
    mids = [float(s.vm[j]) if j is not None else float("nan") for j in js]
    emit("  mid", mids, None, 4, 10)
    # R99 / spec §1 S5 names `mid` among the z-scored quantities.  A price
    # LEVEL has no session-comparable clock norm — the trailing-60-session
    # same-half-hour distribution of the mid is a distribution of PRICE LEVELS,
    # so a z over it measures drift, not the current tape.  Declared as a
    # refusal rather than left as a silent blank.
    put.refuse("S5.z_mid",
               "a price LEVEL has no session-comparable clock norm: the "
               "trailing same-half-hour distribution of `mid` is a "
               "distribution of price levels, so its z measures drift. The "
               "mid's tape reading is the slope/accel row below.")
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
    # R99: `abs_sflow_per_min` IS computed into the clock-norm digest and given
    # a MAD floor, and was then never consumed by any emit call.  The digest is
    # the ABSOLUTE flow rate (a magnitude has a session-comparable norm; a
    # signed one does not), so the z is taken on |sflow| and the printed row
    # keeps the signed value.
    emit("  sflow/min", spm, "abs_sflow_per_min", 1, 10,
         zval=abs(spm[-1]) if np.isfinite(spm[-1]) else float("nan"))
    rv = [_rv_usd(case, max(0, m - 300), m) if m >= 0 else float("nan")
          for m in marks]
    emit("  rv300_$", rv, "rv300_usd", 1, 10)

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

    # S6 is the elastic section (spec §1: "S6 fits itself to its budget", and
    # the sheet cap is "binding, not the sum of the parts").  V1.1 lets the
    # builder hand it the WHOLE-SHEET allowance when that is the tighter of the
    # two: without it, a sheet whose other sections run long can only fail
    # certification, which is what the V1.1 field additions did to 8 dense SI
    # sheets (8502-8538 against the 8500 cap).  A sheet with headroom gets the
    # full section budget and renders byte-identically.
    budget = s6_binding_budget(case)
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


def s6_binding_budget(case):
    """The budget S6 actually renders against — the section constant OR the
    whole-sheet allowance the builder handed it, whichever is tighter."""
    return min(MC.SECTION_BUDGET["S6"],
               getattr(case, "s6_budget", None) or MC.SECTION_BUDGET["S6"])


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
        # MINOR (R100 list): this stamped SECTION_BUDGET["S6"] (always 3000)
        # even when the BINDING budget was `case.s6_budget`, so the sidecar
        # asserted a budget the render did not use.
        put_sink("S6.n_events_raw_shown", i_end - i_rawstart, "derived",
                 "budget-filled raw window (S6 binding budget=%d tokens)"
                 % s6_binding_budget(case))
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
def _refill_after_trade(ev, lo, hi, window_ns=REFILL_WINDOW_SEC * 10 ** 9):
    """L1 REFILL AFTER A TRADE, measured on the MBP-1 event grain.

    WHY THIS IS NOT THE OBVIOUS THING (P-M2c defect D2).  The V1 constructor
    compared the traded side's L1 size at the trade record against the record
    before it and required a DROP.  On this tape that condition is never true:
    a DBN/MDP-3 `T` record is the trade PRINT and does not itself apply the
    book update — the resting size comes off on the FOLLOWING `C`/`M` record.
    Measured on SI 20210701: 24,258 of 24,259 trades show an unchanged L1 size
    at their own record (the one exception is -5), which is exactly why
    `n_refilled_5s` was identically 0 on all 24 warm-up sheets, at every trade
    density, on all three assets.

    THE DEFINITION (V1.1).  A trade EVENT is a maximal run of consecutive `T`
    records sharing one timestamp and one aggressor side (a sweep is one
    event).  Let P = the traded side's L1 price and pre = its L1 size at the
    record BEFORE the run.  The event is MEASURABLE once the book actually
    reacts inside the window: either the L1 size at P falls below pre, or the
    L1 price leaves P (the queue was consumed).  It REFILLED if, within
    `window_ns` of the trade and after that reaction, a record shows the traded
    side back at price P with size >= pre.  Trades that never move the book
    (implied/other-book fills) are NOT measurable and are excluded from the
    denominator rather than counted as failures to refill.

    MBP-1 LIMIT, ON RECORD: this measures the L1 QUEUE at a price, not orders.
    A refill by a new participant and a re-post by the same one are
    indistinguishable at this depth, and nothing behind the top of book is
    visible at all.  The quantity is a defense-of-the-level statistic.
    """
    out = {"n_events": 0, "n_measurable": 0, "n_refilled": 0, "n_no_react": 0,
           "n_swept": 0, "restore_ms": [], "frac": float("nan"),
           "median_restore_ms": float("nan")}
    if hi <= lo:
        return out
    ts = ev["ts_ns"]
    act = ev["action"]
    side = ev["side"]
    k = lo
    while k < hi:
        if act[k] != ord("T"):
            k += 1
            continue
        sd = chr(int(side[k]))
        j = k + 1                          # the run: same ts, same side
        while j < hi and act[j] == ord("T") and ts[j] == ts[k] \
                and side[j] == side[k]:
            j += 1
        k0, k1 = k, j - 1
        k = j
        if sd not in ("A", "B") or k0 == lo:
            continue                       # no aggressor side / no pre-record
        out["n_events"] += 1
        pxcol, szcol = (("bid_px", "bid_sz") if sd == "A"
                        else ("ask_px", "ask_sz"))   # aggressor A hits the bid
        P = int(ev[pxcol][k0 - 1])
        pre = int(ev[szcol][k0 - 1])
        if pre <= 0:
            continue
        end = int(np.searchsorted(ts, int(ts[k1]) + window_ns, side="left"))
        end = min(end, hi)
        seg_px = ev[pxcol][k1 + 1:end]
        seg_sz = ev[szcol][k1 + 1:end]
        if seg_px.size == 0:
            continue                       # window empty: nothing observable
        at_p = seg_px == P
        react = np.nonzero((at_p & (seg_sz < pre)) | (~at_p))[0]
        if react.size == 0:
            out["n_no_react"] += 1         # the book never moved: not a trade
            continue                       # this constructor can speak about
        out["n_measurable"] += 1
        i0 = int(react[0])
        if not at_p[i0]:
            out["n_swept"] += 1
        back = np.nonzero(at_p[i0 + 1:] & (seg_sz[i0 + 1:] >= pre))[0]
        if back.size:
            m = k1 + 1 + i0 + 1 + int(back[0])
            out["n_refilled"] += 1
            out["restore_ms"].append((int(ts[m]) - int(ts[k1])) / 1e6)
    if out["n_measurable"]:
        out["frac"] = out["n_refilled"] / float(out["n_measurable"])
    if out["restore_ms"]:
        out["median_restore_ms"] = float(np.median(out["restore_ms"]))
    return out


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

    # refill-after-trade (V1.1 constructor — see _refill_after_trade)
    lo = int(np.searchsorted(ts, (case.decision_ts - REFILL_LOOKBACK_SEC)
                             * 10 ** 9, side="left"))
    hi = int(np.searchsorted(ts, dec_ns, side="left"))
    rf = _refill_after_trade(ev, lo, hi)
    L.append(MC.row("  refill_after_trade",
                    "n_trade_events_%ds=" % REFILL_LOOKBACK_SEC
                    + str(rf["n_events"]),
                    " n_measurable=" + str(rf["n_measurable"]),
                    " n_refilled_%ds=" % REFILL_WINDOW_SEC
                    + str(rf["n_refilled"]),
                    " frac=" + MC.fnum(rf["frac"], 1, 3).strip(),
                    " median_restore_ms="
                    + MC.fnum(rf["median_restore_ms"], 1, 1).strip(),
                    " (swept=" + str(rf["n_swept"])
                    + " no_book_reaction=" + str(rf["n_no_react"]) + ")"))
    L.append("    def: L1 size at the traded price back to its pre-trade level "
             "within %ds; denominator = trades the book reacted to"
             % REFILL_WINDOW_SEC)
    if rf["n_measurable"]:
        put("S7.refill_frac_%ds" % REFILL_LOOKBACK_SEC, rf["frac"],
            "derived(events npz)",
            "L1 size at the traded price restored within %ds / trade events "
            "the book reacted to" % REFILL_WINDOW_SEC)
    else:
        put.refuse("S7.refill_frac_%ds" % REFILL_LOOKBACK_SEC,
                   "no measurable trade event in the last %ds (n_events=%d, "
                   "no book reaction at L1)"
                   % (REFILL_LOOKBACK_SEC, rf["n_events"]))
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
    _wins = [("%ds" % w if w < 300 else "%dm" % (w // 60), d - w)
             for w in FLOW_WINDOWS]
    for name, lo in (_wins + [("phase", ph_start), ("session", 0)]):
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
    # R96: `if A._f(fs["range_hat_usd"])` — A._f returns NaN when the forecaster
    # carried no range_hat, and a NaN is TRUTHY in Python, so the guard never
    # fired, the division produced NaN, and `surprise` was never put() at all.
    rh = A._f(fs["range_hat_usd"])
    rh_ok = bool(np.isfinite(rh)) and float(rh) > 0.0
    surprise = (realized / float(rh)) if (rh_ok and np.isfinite(realized)) \
        else float("nan")
    L.append(MC.row("  fvol", "segment=" + X.PHASE_NAMES[case.phase_dec],
                    " sigma_hat=$" + MC.fnum(sig, 1, 1).strip(),
                    " range_hat=$" + MC.fnum(rh, 1, 1).strip(),
                    " realized_range_so_far=$" + MC.fnum(realized, 1, 1).strip(),
                    " surprise=" + MC.fnum(surprise, 1, 3).strip()))
    if np.isfinite(surprise):
        put("S9.surprise", surprise, "derived",
            "realized_range_so_far / range_hat_usd")
    else:
        put.refuse("S9.surprise",
                   "range_hat_usd is refused or non-positive in the fvol "
                   "receipt (or no sane range so far): the surprise ratio "
                   "cannot be derived")
    lad = [(q, A._f(fs.get("move_%s_usd_per_sigma" % q)) * sig)
           for q in ("q10", "q25", "q50", "q75", "q90")]
    L.append(MC.row("  move_ladder_$", *[MC.fstr("%s=%s" % (q, MC.fnum(v, 1, 0).strip()), 12)
                                         for q, v in lad]))
    # REFUSED CONSISTENCY (V1.1 / P-M2c D1): ladder_position is DERIVED from
    # the ladder.  When the forecaster carried no quantiles for this row (the
    # ATR14_RAW_FILL fallback publishes sigma_hat but no move_q*), the ladder is
    # refused and so is every band read off it — the warm-up caught this field
    # printing `below_q10` beside five `.` quantiles, and it is a term of P001.
    ladder_ok = all(np.isfinite(v) for _q, v in lad) and np.isfinite(realized)
    why = ("move_q*_usd_per_sigma REFUSED in the fvol receipt "
           "(sigma_source=%s)" % (fs.get("sigma_source", MC.NA))
           if not all(np.isfinite(v) for _q, v in lad)
           else "realized segment range REFUSED (no SANE second in the segment)")
    if ladder_ok:
        band = "below_q10"
        for q, v in lad:
            if realized >= v:
                band = "at_or_above_" + q
        L.append(MC.row("  ladder_position", MC.fstr(band, 18),
                        " (realized segment range vs the calibrated move ladder)"))
        put("S9.ladder_position", band, case.fvol_path, "move_q*_usd_per_sigma")
    else:
        L.append(MC.row("  ladder_position", MC.fstr(MC.NA, 18),
                        " REFUSED: " + why))
        put.refuse("S9.ladder_position", why)
    for q, v in lad:
        if np.isfinite(v):
            put("S9.move_%s_usd" % q, v, case.fvol_path,
                "move_%s_usd_per_sigma*sigma_hat_usd" % q)
        else:
            put.refuse("S9.move_%s_usd" % q, why)

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

    # TICK CONVENTION (V1.1 bug fix, defect D6 found while sweeping S10 for
    # REFUSED consistency).  Every *_tick array b4_profiles writes is an
    # ABSOLUTE tick index — profile_objects returns `bin0 + offset` and the
    # developing arrays store `b0 + p` — so the price is tick_index x tick_px
    # and nothing else.  V1 added bin0 a SECOND time, which put every S10 price
    # at roughly twice the market (SI mid 26.28 rendered POC 52.24) and made
    # every S10 distance a five-figure absurdity.  b3_levels' PROFILE family has
    # always used the correct form (`t * tick_px`), so the S4 level rows were
    # right and only S10's own lines were wrong.
    def px_of(t):
        return float(t) * tick if np.isfinite(t) else float("nan")

    ds = z["dev_sec"]
    j = int(np.searchsorted(ds, d, side="left")) - 1
    # MINOR (R100 list): this guard call's return was DISCARDED — S10's only
    # guard call was a no-op that inflated `guard.checks` and could not refuse
    # anything.  It is checked now.
    if j >= 0 and case.guard.sec(int(ds[j]) + 1, "S10 developing profile"):
        poc = px_of(float(z["dev_poc_tick"][j]))
        vah = px_of(float(z["dev_vah_tick"][j]))
        val = px_of(float(z["dev_val_tick"][j]))
        L.append(MC.row("  developing", "as_of=" + MC.fsec(int(ds[j])),
                        " POC=" + MC.fnum(poc, 1, 4).strip(),
                        " VAH=" + MC.fnum(vah, 1, 4).strip(),
                        " VAL=" + MC.fnum(val, 1, 4).strip(),
                        " d_POC=$" + MC.fnum(usd(case, case.entry_mid - poc), 1, 1).strip(),
                        # REFUSED CONSISTENCY (V1.1): in_VA is derived from the
                        # VA edges — a missing edge is not "outside the area".
                        " in_VA=" + ("1" if val <= case.entry_mid <= vah
                                     else "0" if (np.isfinite(val)
                                                  and np.isfinite(vah))
                                     else MC.NA)))
        if not (np.isfinite(val) and np.isfinite(vah)):
            put.refuse("S10.in_value_area",
                       "developing VAH/VAL REFUSED in the profile receipt")
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
        L.append(MC.row("  phase_final", MC.fstr(name, 7),
                        "end=" + MC.fsec(en - 1),
                        " POC=" + MC.fnum(px_of(float(z["%s_poc_tick" % name])), 1, 4).strip(),
                        " VAH=" + MC.fnum(px_of(float(z["%s_vah_tick" % name])), 1, 4).strip(),
                        " VAL=" + MC.fnum(px_of(float(z["%s_val_tick" % name])), 1, 4).strip(),
                        " poor_H=" + str(int(z["%s_poor_high" % name])),
                        " poor_L=" + str(int(z["%s_poor_low" % name]))))

    pz = case.prior_profile
    if pz is not None:
        poc = px_of(float(pz["SESSION_poc_tick"]))
        vah = px_of(float(pz["SESSION_vah_tick"]))
        val = px_of(float(pz["SESSION_val_tick"]))
        L.append(MC.row("  prior_session", str(case.prior_d8),
                        " POC=" + MC.fnum(poc, 1, 4).strip(),
                        " VAH=" + MC.fnum(vah, 1, 4).strip(),
                        " VAL=" + MC.fnum(val, 1, 4).strip(),
                        " d_POC=$" + MC.fnum(usd(case, case.entry_mid - poc), 1, 1).strip(),
                        " poor_H=" + str(int(pz["SESSION_poor_high"])),
                        " poor_L=" + str(int(pz["SESSION_poor_low"]))))
        put("S10.prior_session_poc", poc, case.prior_profile_path,
            "SESSION_poc_tick")
        hv = [px_of(t) for t in pz["SESSION_hvn_ticks"].tolist()]
        lv = [px_of(t) for t in pz["SESSION_lvn_ticks"].tolist()]
        sp = [px_of(t) for t in pz["SESSION_single_print_ticks"].tolist()]
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
        # MINOR (R100 list): S11 made ZERO guard calls, and read `mid` with
        # side="right" while `range$` below used side="left" on the SAME
        # second.  Both are routed through the guard now and both use the
        # strictly-prior convention ("left"), so the two cannot disagree.
        if not case.guard.sec(int(osec), "S11 cross-asset read"):
            L.append(MC.row("   ", MC.fstr(a, 5), MC.fint(osec, 8),
                            " cross-asset second is not strictly prior"))
            continue
        jj = int(np.searchsorted(os_.vt, osec, side="left")) - 1
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
        if np.isfinite(q50) and q50:
            put("S11.%s_coverage_pct" % a, 100.0 * rng / q50, "derived",
                "own range / own move_q50")
        else:
            put.refuse("S11.%s_coverage_pct" % a,
                       "%s move_q50 REFUSED in the fvol receipt" % a)
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
            # R96: S12 refusals were counted ONLY in S12.n_series_refused and
            # never reached put.refuse, so the S1 "REFUSED DERIVED FIELDS"
            # roster was NOT the complete list of the sheet's typed-missing
            # glyphs — which is exactly what the reader protocol treats it as.
            put.refuse("S12.%s" % sid,
                       "no observation available at decision_ts under rule %s "
                       "(n_future=%d)" % (ser.rule, ser.n_future(g)))
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
            AV.abs_source(CTX._row("CAL_BLS")["file"] + " + "
                          + CTX._row("CAL_FOMC")["file"]),
            "scheduled, exempt")
    rec = CTX.recent_release(g, case.asset)
    if rec:
        L.append(MC.row("  last_scheduled", MC.fstr(rec["name"], 22),
                        MC.futc(rec["event_ts"]),
                        " " + str(rec["since_sec"]) + "s ago",
                        " status=" + rec["status"]))
    L.append(MC.row("  availability_summary", "n_joined=" + str(n_ok),
                    " n_refused=" + str(n_ref),
                    " lag_table=" + AV.LAG_TABLE))
    put("S12.n_series_joined", n_ok, "derived", "count")
    put("S12.n_series_refused", n_ref, "derived", "count")
    return L


# ============================================================ S13 ===========
def _prior_card_eras(case):
    """R01: the era labels a BLIND sheet's census cards may be computed over.

    S13 rendered its class card over `case.era` and the decision's own calendar
    year, and its family card over the year plus `FIT_2021_2024`.  Every one of
    those spans contains sessions AFTER the decision, and every number in the
    cards is a mean of REALISED walled certificates — so each blind sheet
    carried the era-wide realised win-rate and conditional value of its own
    class, including the block being scored.  A card is admissible only if its
    whole span ENDED strictly before the decision date.

    Returns (prior_eras, prior_years, prior_blocks), each newest-first.
    """
    d8 = int(case.d8)
    yr = d8 // 10000
    eras = [n for (n, _lo, hi) in MC.ERAS if hi < d8]
    if MC.ERA_HOLDOUT[2] < d8:
        eras.append(MC.ERA_HOLDOUT[0])
    years = [str(y) for y in range(yr - 1, yr - 4, -1)]
    blocks = []
    if yr > max(X.WALL_FIT_YEARS):
        blocks.append(X.ERA_FIT)
    if yr > 2025:
        blocks.append(X.ERA_GATE)          # unreachable under the 2026 seal
    return list(reversed(eras)), years, blocks


def _cost_rt_so_far(case):
    """R95: the CAUSAL round-trip cost estimate.

    `case.cost_rt` is `c_a_cost`'s per-(asset, session) `cost_rt` at
    `phase=ALL` — the median two-sided spread over the WHOLE session plus
    FEES_RT — so the number every "is this a $1,000 trade after cost"
    judgement divides by embedded the POST-decision spread distribution, on a
    BLIND section, registered in no trap list.  The same statistic computed
    over the sane two-sided seconds STRICTLY BEFORE the decision is knowable
    and is what the sheet prints now.
    """
    d = int(case.dec_sec)
    if d <= 0:
        return float("nan")
    sel = (case.s.state[:d] == C.ST_TWO_SIDED) & case.s.valid[:d]
    sp = np.asarray(case.s.spread_usd[:d])[sel]
    sp = sp[np.isfinite(sp)]
    if sp.size == 0:
        return float("nan")
    return float(np.median(sp)) + float(C.FEES_RT)


def s13_mechanics(case, put):
    L = ["S13 CANDIDATE MECHANICS"]
    cost_sf = _cost_rt_so_far(case)
    L.append(MC.row("  entry", "mid=" + MC.fnum(case.entry_mid, 1, 4).strip(),
                    " side=" + ("LONG" if case.side > 0 else "SHORT"),
                    " spread_at_decision=$" + MC.fnum(case.spread_dec, 1, 2).strip(),
                    " cost_rt=$" + MC.fnum(cost_sf, 1, 2).strip(),
                    " (median sane two-sided spread SO FAR + fees; R95)",
                    " tick=$" + MC.fnum(case.tick_usd, 1, 2).strip(),
                    " mult=" + str(case.mult)))
    put("S13.spread_at_decision", case.spread_dec, case.roster_path,
        "spread_at_decision[%d]" % case.i)
    if np.isfinite(cost_sf):
        put("S13.cost_rt", cost_sf, case.session_path,
            "median(spread_usd[SANE TWO_SIDED, sec < dec]) + FEES_RT")
    else:
        put.refuse("S13.cost_rt",
                   "no sane two-sided second before the decision second: the "
                   "causal round-trip cost cannot be estimated (the "
                   "whole-session c_a_cost value is NOT substituted — R95)")
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
    # D-071: the CLASS card comes first — the class is what the candidate IS;
    # the family rows below it are the mechanism detail.
    cls, driver, others = MC.class_of(case.fam_mask)
    p_eras, p_years, p_blocks = _prior_card_eras(case)
    L.append(MC.row("  CLASS", MC.fstr(cls, 22),
                    " driver_family=" + str(driver),
                    " (D-071 census card, STRICTLY-PRIOR eras only — R01)"))
    L.append("    class                  era        n_cand  n_pos  cond_value$"
             "  mean_cert$  pos_frac  fires/sess  win_frac")
    cc = CLS.cards()
    n_class_cards = 0
    for era in (p_eras[:1] + p_years[:1]):
        card = cc.get((case.asset, cls, era))
        if card is None:
            continue
        n_class_cards += 1
        L.append(MC.row("   ", MC.fstr(cls, 22), MC.fstr(era, 10),
                        MC.fint(card["n_candidates"], 7),
                        MC.fint(card["n_positive"], 6),
                        MC.fnum(A._f(card["conditional_value_usd"]), 12, 2),
                        MC.fnum(A._f(card["mean_cert_usd"]), 11, 2),
                        MC.fnum(A._f(card["positive_frac"]), 9, 4),
                        MC.fnum(A._f(card["fires_per_session"]), 11, 2),
                        MC.fnum(A._f(card["winner_frac"]), 9, 4)))
        put("S13.class_census.%s.%s.cond_value" % (cls, era),
            A._f(card["conditional_value_usd"]), CLS.OUT,
            "conditional_value_usd")
    if n_class_cards == 0:
        L.append("    " + MC.NA + "  no census era ENDED before this decision "
                 "(R01: a card over the decision's own era/year/block is a "
                 "mean of realised outcomes over its own future)")
        put.refuse("S13.class_census.%s" % cls,
                   "no strictly-prior era exists for a %s decision: the class "
                   "card would be computed over the decision's own future"
                   % case.era)
    fc = A.family_census()
    L.append("  CENSUS CARD (committed censuses, generation_v3; "
             "STRICTLY-PRIOR eras only — R01)")
    L.append("    family        era              n_cand  n_pos  cond_value$  mean_cert$  pos_frac  cond_peak$")
    n_fam_cards = 0
    for fam in MC.fam_names(case.fam_mask):
        for era in (p_years[:1] + p_blocks[:1]):
            r = fc.get((case.asset, fam, era))
            if r is None:
                continue
            n_fam_cards += 1
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
    if n_fam_cards == 0:
        L.append("    " + MC.NA + "  no committed census block ENDED before "
                 "this decision (R01)")
        put.refuse("S13.census.family_cards",
                   "no strictly-prior calendar year or protocol block exists "
                   "for a %s decision" % case.era)
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
