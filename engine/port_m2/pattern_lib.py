#!/usr/bin/python3
"""PORT M2 — the PATTERN SUBSTRATE: one causal per-session frame, read by both
the reference-class retrieval tool (retrieve.py, CC-M2-5 item 3) and the
name->count pattern censuses (p001_census.py, DISCRETIONARY_METHOD §4.2).

WHY ONE MODULE
  The sheet renderer (sections.py) computes a candidate's causal state ONE
  CANDIDATE AT A TIME, because a sheet is one candidate's view.  A census reads
  1.58M candidates and a retrieval reads ~25, so neither can afford (nor needs)
  the text path.  Formula fidelity (D-006) forbids a SECOND definition of the
  same quantity, so every field here is the vectorised form of exactly one
  sections.py line, and test_pattern.t01 pins the two together on the committed
  P-M2c warm-up sheets: a drift in either direction fails the test.

CAUSALITY
  Every field is computed from data STRICTLY at or before the candidate's
  decision second, using the same SANE (D-054) mid grid the sheets use:
    * `s.vt` / `s.vm` are the b7_sane-masked observed seconds;
    * any window read is a searchsorted on `s.vt` bounded at `dec_sec`;
    * the ZigZag pivot chain uses c_c_roster.zigzag_scan, which is an ONLINE
      scan: a pivot's (price, pivot_sec, confirmation_sec) never depends on
      data after its confirmation second, so scanning the whole session once
      and then keeping `conf_sec < dec_sec` is identical to (and much cheaper
      than) re-scanning the truncated prefix per candidate.  test_pattern.t02
      proves that identity against sections._pivots.
  Nothing in this module reads a forward field.  The KNOWN_TRAPS registry
  (m2_common) names the receipt columns that would leak if read directly; the
  only one this module touches is levels_v4, and only through the level-BIRTH
  guard (V1.1 defect D4) plus a strict `touch_sec < dec_sec` filter.

THE FRAME
  `frame(asset, d8, with_levels=False)` returns a dict of numpy arrays, one row
  per roster candidate of that (asset, session), in roster order.  Columns are
  documented in FRAME_FIELDS below and stamped into every consumer's receipt.

Run (self-check on one session):
  /usr/bin/python3 engine/port_m2/pattern_lib.py SI 20210701
"""
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import assemble as A                      # noqa: E402
import common as C                        # noqa: E402
import census_common as X                 # noqa: E402
import c_a_cost as CA                     # noqa: E402
import c_c_roster as CC                   # noqa: E402

# ------------------------------------------------------------- vocabulary ---
# S9 ladder bands, as sections.s9_vol names them, in ASCENDING order.  The
# integer code is the ORDINAL used by the retrieval distance; -1 = REFUSED
# (the fvol row carried no move_q* quantiles — the V1.1 D1 law).
LADDER_BANDS = ("below_q10", "at_or_above_q10", "at_or_above_q25",
                "at_or_above_q50", "at_or_above_q75", "at_or_above_q90")
LADDER_CODE = {b: i for i, b in enumerate(LADDER_BANDS)}
LADDER_REFUSED = -1

# S2 regime tag -> vol tercile ordinal (b2_fvol writes LOW/MID/HIGH)
REGIME_TERCILE = {"LOW": 0, "MID": 1, "HIGH": 2}

# the two S9 rv nowcast windows P013 names (rv1800 / rv60)
RV_SHORT_SEC = 60
RV_LONG_SEC = 1800

FRAME_FIELDS = {
    "i": "roster row index (union_roster_{ASSET}.npz)",
    "cid": "{ASSET}-{d8}-{dec_sec:06d}-{L|S}",
    "dec_sec": "decision second (session clock)",
    "side": "+1 LONG / -1 SHORT",
    "phase_dec": "roster phase_dec (the fvol segment key)",
    "phase_seg_start": "first second of the phase SEGMENT containing dec_sec",
    "phase_seg_end": "one past the last second of that segment",
    "klass": "m2_common.class_of(fam_mask)[0] (D-071, a partition)",
    "fam_mask": "generation-v3 family bitmask",
    "clock_sec": "(open_utc + dec_sec) % 86400 — clock-of-day, UTC",
    "coverage_phase": "sections.s3_path COVERAGE for the running phase = "
                      "SANE range so far in the phase / (move_q50_usd_per_"
                      "sigma * sigma_hat_usd) of that phase's fvol row; NaN "
                      "when the fvol row carries no q50 (REFUSED, V1.1 D1)",
    "coverage_session": "the same number on the SESSION clock/forecast",
    "ladder_band": "sections.s9_vol ladder_position as an ordinal (see "
                   "LADDER_BANDS); -1 = REFUSED (no move_q* in the fvol row)",
    "regime_tercile": "S2 regime_tag LOW/MID/HIGH -> 0/1/2; -1 = missing",
    "runway_phase_sec": "phase_close_sec - dec_sec (roster)",
    "runway_sess_sec": "sess_close_sec - dec_sec (roster)",
    "session_close_exit": "phase_close_sec == sess_close_sec — the S13 "
                          "exit_default IS the session close",
    "runway_frac": "runway_phase_sec / (phase_seg_end - phase_seg_start)",
    "phase_hi": "max SANE mid in [phase_seg_start, dec_sec)",
    "phase_hi_sec": "FIRST second at which phase_hi was reached",
    "phase_lo": "min SANE mid in [phase_seg_start, dec_sec)",
    "phase_lo_sec": "FIRST second at which phase_lo was reached",
    "extreme_age_sec": "dec_sec - phase_hi_sec (SHORT) or - phase_lo_sec "
                       "(LONG): the age of the phase extreme the trade fades",
    "pivot_age_sec": "dec_sec - pivot_sec of the most recent CAUSAL ZigZag "
                     "pivot of the faded type (HIGH for a SHORT, LOW for a "
                     "LONG), conf_sec < dec_sec; -1 = none yet",
    "mid_now": "SANE mid at dec_sec (last SANE second <= dec_sec)",
    "slope_1m_usd": "sections.s5_tminus mid_slope last-minute column = "
                    "(mid(dec) - mid(dec-60)) * mult",
    "slope_5m_usd": "(mid(dec) - mid(dec-300)) * mult / 5 — $ per minute",
    "accel_usd": "slope_1m_usd - slope_5m_usd  = S5 accel(1m-5m)",
    "rv60_usd": "S9 rv nowcast, 60s window",
    "rv1800_usd": "S9 rv nowcast, 1800s window",
    "rv_ratio": "rv1800_usd / rv60_usd (the P013 candidate marker)",
    "spread_dec_usd": "roster spread_at_decision",
    "spread_ratio": "spread_dec_usd / phase-median spread (c_a_cost, per "
                    "asset x year x phase) — the P005 'spread tax' state",
    "atr_usd": "roster atr14_usd (ATR14_prev)",
    "level_dist_atr": "|nearest KEPT-family level price - entry_mid| / ATR, "
                      "over levels alive at dec_sec (V1.1 birth guard) and "
                      "within +/-1.5xATR; NaN when there is none",
    "cert_close_usd": "c_c_roster.certificates(...)[1][0] — the walled "
                      "PHASE-CLOSE certificate (the CC-M1-8 adoption metric)",
    "cert_peak_usd": "c_c_roster.certificates(...)[0][0] — the walled "
                     "PEAK-EXIT companion (CC-M1-8 mandatory column)",
    "walled": "the $-wall was hit on the adverse skeleton",
    "mae_before_argmax": "roster mae_before_argmax (D-021 winner test)",
    "winner": "cert_close >= $1000 and mae <= $300 and not walled (D-021)",
}

PARAMS_FRAME = {
    "module": "engine/port_m2/pattern_lib.py",
    "sane_mask": "b7_sane (D-054) — installed by assemble.load_session",
    "causality": "every window is searchsorted on the SANE second grid and "
                 "bounded at dec_sec; ZigZag pivots kept only when "
                 "conf_sec < dec_sec",
    "fields": FRAME_FIELDS,
    "ladder_bands": list(LADDER_BANDS),
    "rv_windows_sec": [RV_SHORT_SEC, RV_LONG_SEC],
}


# ----------------------------------------------------------------- helpers --
def _running_extremes(v):
    """(running max, index of its FIRST occurrence, running min, first index).

    np.argmax on a prefix returns the FIRST occurrence, which is what
    sections._hi_lo does, so the accumulate form has to reproduce that: a new
    record is a value STRICTLY beyond the previous running extreme.
    """
    n = v.size
    idx = np.arange(n)
    rmax = np.maximum.accumulate(v)
    new_hi = np.empty(n, dtype=bool)
    new_hi[0] = True
    new_hi[1:] = v[1:] > rmax[:-1]
    imax = np.maximum.accumulate(np.where(new_hi, idx, 0))
    rmin = np.minimum.accumulate(v)
    new_lo = np.empty(n, dtype=bool)
    new_lo[0] = True
    new_lo[1:] = v[1:] < rmin[:-1]
    imin = np.maximum.accumulate(np.where(new_lo, idx, 0))
    return rmax, imax, rmin, imin


def _phase_segments(s):
    """[(phase_code, start_sec, end_sec_exclusive)] — sections._phase_bounds."""
    out = []
    ch = [0] + [int(x) + 1 for x in
                np.nonzero(s.phase_tag[1:] != s.phase_tag[:-1])[0].tolist()]
    for i, st in enumerate(ch):
        en = ch[i + 1] if i + 1 < len(ch) else s.n
        out.append((int(s.phase_tag[st]), st, en))
    return out


def _pivot_chain(asset, s, trade_date, atr, tick_px, tick_usd, mult):
    """The causal ZigZag chain over the WHOLE session (sections._pivots, run
    once): [(pivot_sec, side, conf_sec)] sorted by pivot_sec."""
    vt_l = s.vt.tolist()
    vm_l = s.vm.tolist()
    if len(vt_l) < 2:
        return np.zeros(0, np.int64), np.zeros(0, np.int64), np.zeros(0, np.int64)
    vphase = s.phase_tag[s.vt].tolist()
    phase_med = CA.phase_median_spreads(MC.M0_ROOT)
    merged = {}
    for r in MC.RUNGS:
        per_phase = []
        for p in range(X.N_PHASES):
            pm = phase_med.get((asset, trade_date.year, X.PHASE_NAMES[p]),
                               float("nan"))
            fl = X.RUNG_FLOOR_SPREAD_MULT * pm if np.isfinite(pm) else 0.0
            u = max(r * atr, X.RUNG_FLOOR_TICKS * tick_usd, fl)
            per_phase.append(X.round_half_up(u / mult, tick_px))
        thr_l = [per_phase[p] for p in vphase]
        for (_px, psec, csec, side) in CC.zigzag_scan(vt_l, vm_l, thr_l):
            k = (int(psec), int(side))
            e = merged.get(k)
            if e is None:
                merged[k] = int(csec)
            else:
                merged[k] = min(e, int(csec))
    keys = sorted(merged)
    psec = np.array([k[0] for k in keys], dtype=np.int64)
    pside = np.array([k[1] for k in keys], dtype=np.int64)
    pconf = np.array([merged[k] for k in keys], dtype=np.int64)
    return psec, pside, pconf


def _last_pivot_age(psec, pside, pconf, dec_sec, want_side):
    """Age of the most recent pivot of `want_side` CONFIRMED before dec_sec.

    want_side = -1 (a confirmed HIGH, what a SHORT fades) / +1 (a LOW).
    Vectorised over dec_sec: the chain is sorted by pivot_sec, but the causal
    filter is on conf_sec, so the running "latest usable pivot_sec" is taken
    over the chain sorted by CONF second.
    """
    out = np.full(dec_sec.size, -1, dtype=np.int64)
    m = (pside == want_side)
    if not m.any():
        return out
    ps, pc = psec[m], pconf[m]
    o = np.argsort(pc, kind="stable")
    ps, pc = ps[o], pc[o]
    best = np.maximum.accumulate(ps)                # latest pivot_sec so far
    j = np.searchsorted(pc, dec_sec, side="left") - 1
    ok = j >= 0
    out[ok] = dec_sec[ok] - best[j[ok]]
    return out


def _prefix_sq(vm):
    """Prefix sums of squared consecutive SANE-mid increments (S9 _rv_usd)."""
    d = np.diff(vm.astype(np.float64))
    p = np.zeros(vm.size, dtype=np.float64)
    if d.size:
        p[1:] = np.cumsum(d * d)
    return p


def _rv_window(vt, prefix, lo_sec, hi_sec, mult):
    """sections._rv_usd, vectorised over (lo_sec, hi_sec) pairs."""
    a = np.searchsorted(vt, lo_sec, side="left")
    b = np.searchsorted(vt, hi_sec, side="left")
    out = np.full(a.size, np.nan)
    ok = (b - a) >= 3
    if ok.any():
        out[ok] = np.sqrt(np.maximum(prefix[b[ok] - 1] - prefix[a[ok]], 0.0)) * mult
    return out


def _f(v):
    return A._f(v)


# ------------------------------------------------------------ roster (lazy) -
# assemble.roster() eagerly materialises EVERY array of a 50-70MB npz and then
# builds a 500k-entry Python dedup index.  A census worker never needs the
# index, and a retrieval never needs the skeleton arrays, so this loader pulls
# members on demand (NpzFile decompresses per key) and memoises what it pulled.
# Measured on union_roster_HG.npz: the light key set costs 0.04s, the skeleton
# key set 0.66s, the assemble.roster() path 1.02s + the index.
_LIGHT_KEYS = ("date8", "dec_sec", "side", "phase_dec", "phase_close_sec",
               "sess_close_sec", "entry_mid", "atr14_usd",
               "spread_at_decision", "fam_mask", "mae_before_argmax")
_CERT_KEYS = ("a_off", "a_len", "f_off", "f_len", "skel_a_t", "skel_a_v",
              "skel_f_t", "skel_f_v", "f_phase_close", "f_sess_close")
_ROSTER = {}


def roster(asset, with_certs=True):
    """The frozen v3 roster arrays for `asset`, loaded lazily and memoised."""
    cur = _ROSTER.setdefault(asset, {})
    want = list(_LIGHT_KEYS) + (list(_CERT_KEYS) if with_certs else [])
    missing = [k for k in want if k not in cur]
    if missing:
        path = os.path.join(A.GEN_DIR, "union_roster_%s.npz" % asset)
        z = np.load(path, allow_pickle=False)
        for k in missing:
            cur[k] = z[k]
        z.close()
    return cur


# ------------------------------------------------------------- level state --
def _nearest_kept_level_atr(asset, d8, s, trade_date, profile, dec_sec,
                            entry_mid, atr, mult):
    """|nearest KEPT-family level - mid| / ATR at each decision second.

    Reuses sections._level_birth_sec verbatim (the V1.1 D4 guard) through a
    duck-typed shim, so there is exactly one birth rule in the codebase.
    """
    import sections as SEC                # local: sections imports are heavy

    z, _p = A.load_levels(asset, d8)
    out = np.full(dec_sec.size, np.nan)
    if z is None or not int(z["level_price"].size):
        return out
    fam = z["level_family"]
    lid = z["level_id"]
    lpx = z["level_price"].astype(np.float64)
    dyn = z["dynamic"]

    class _Shim(object):                   # what _level_birth_sec/_or_window read
        pass

    shim = _Shim()
    shim.asset = asset
    shim.d8 = int(d8)
    shim.s = s
    shim.trade_date = trade_date
    shim.profile = profile

    keep = np.array([str(f) in MC.KEPT_LEVEL_FAMILIES for f in fam.tolist()],
                    dtype=bool)
    born = np.array([SEC._level_birth_sec(shim, str(fam[r]), str(lid[r]),
                                          int(dyn[r]))
                     for r in range(int(lpx.size))], dtype=np.int64)
    ok = keep & np.isfinite(lpx) & (born >= 0)
    if not ok.any():
        return out
    px = lpx[ok]
    bn = born[ok]
    band_px = 1.5 * atr / mult
    for k in range(dec_sec.size):
        alive = bn < dec_sec[k]            # STRICTLY before (CausalGuard.sec)
        if not alive.any():
            continue
        d = np.abs(px[alive] - entry_mid[k])
        d = d[d <= band_px]
        if d.size:
            out[k] = float(d.min()) * mult / atr
    return out


# ------------------------------------------------------------------ frame ---
def frame(asset, d8, with_levels=False, with_certs=True):
    """Causal per-candidate state for every roster row of (asset, d8)."""
    d8 = int(d8)
    r = roster(asset, with_certs=with_certs)
    sel = np.nonzero(r["date8"] == d8)[0]
    spec = C.ASSETS[asset]
    mult = float(spec["mult"])
    out = {"asset": asset, "d8": d8, "n": int(sel.size)}
    if sel.size == 0:
        return None
    sess = A.load_session(asset, d8)
    s = sess["s"]
    trade_date = sess["trade_date"]

    dec = r["dec_sec"][sel].astype(np.int64)
    side = r["side"][sel].astype(np.int64)
    # the generation-v3 dedup key is (session, dec_sec, side); assemble.roster
    # asserts it globally, and this loader skips that index, so the property is
    # re-asserted here at session scope (a collision is a roster defect).
    if np.unique(np.stack([dec, side], 1), axis=0).shape[0] != dec.size:
        raise RuntimeError("roster %s %d: duplicate (dec_sec, side)"
                           % (asset, d8))
    order = np.argsort(dec, kind="stable")   # deterministic, dec-ascending work
    inv = np.empty(order.size, dtype=np.int64)
    inv[order] = np.arange(order.size)
    dec_s = dec[order]

    # --- phase segment containing dec_sec ---------------------------------
    segs = _phase_segments(s)
    seg_start = np.array([g[1] for g in segs], dtype=np.int64)
    seg_end = np.array([g[2] for g in segs], dtype=np.int64)
    k = np.searchsorted(seg_start, dec_s, side="right") - 1
    k = np.clip(k, 0, seg_start.size - 1)
    ph_start = seg_start[k]
    ph_end = seg_end[k]

    # --- running SANE extremes, per phase segment and per session ---------
    vt = s.vt
    vm = s.vm.astype(np.float64)
    rmax, imax, rmin, imin = _running_extremes(vm)
    j_dec = np.searchsorted(vt, dec_s, side="left") - 1     # last SANE sec < dec
    j_ph = np.searchsorted(vt, ph_start, side="left")       # first SANE in phase
    have_ph = (j_dec >= j_ph) & (j_dec >= 0)

    phase_hi = np.full(dec_s.size, np.nan)
    phase_lo = np.full(dec_s.size, np.nan)
    phase_hi_sec = np.full(dec_s.size, -1, dtype=np.int64)
    phase_lo_sec = np.full(dec_s.size, -1, dtype=np.int64)
    if have_ph.any():
        idx = np.nonzero(have_ph)[0]
        for t in idx.tolist():             # per-segment window, segments are few
            a, b = int(j_ph[t]), int(j_dec[t]) + 1
            w = vm[a:b]
            ih = int(np.argmax(w))
            il = int(np.argmin(w))
            phase_hi[t] = w[ih]
            phase_lo[t] = w[il]
            phase_hi_sec[t] = int(vt[a + ih])
            phase_lo_sec[t] = int(vt[a + il])

    sess_hi = np.where(j_dec >= 0, rmax[np.maximum(j_dec, 0)], np.nan)
    sess_lo = np.where(j_dec >= 0, rmin[np.maximum(j_dec, 0)], np.nan)

    # --- fvol rows (per phase segment + SESSION) --------------------------
    fv = A.fvol_rows()
    iso = trade_date.isoformat()
    phase_dec = r["phase_dec"][sel][order].astype(np.int64)
    q50_p = np.full(dec_s.size, np.nan)
    lad = np.full((dec_s.size, len(LADDER_BANDS) - 1), np.nan)
    terc = np.full(dec_s.size, -1, dtype=np.int64)
    seg_cache = {}
    for p in sorted(set(phase_dec.tolist())):
        row = fv.get((asset, iso, X.PHASE_NAMES[p]))
        sig = _f(row["sigma_hat_usd"]) if row else float("nan")
        qs = ([_f(row.get("move_%s_usd_per_sigma" % q)) * sig
               for q in ("q10", "q25", "q50", "q75", "q90")] if row
              else [float("nan")] * 5)
        seg_cache[p] = (qs, (row or {}).get("regime_tag", ""))
    for p, (qs, tag) in seg_cache.items():
        m = phase_dec == p
        q50_p[m] = qs[2]
        lad[m, :] = np.array(qs)
        terc[m] = REGIME_TERCILE.get(str(tag), -1)
    row_s = fv.get((asset, iso, "SESSION"))
    sig_s = _f(row_s["sigma_hat_usd"]) if row_s else float("nan")
    q50_s = (_f(row_s.get("move_q50_usd_per_sigma")) * sig_s if row_s
             else float("nan"))

    range_phase = (phase_hi - phase_lo) * mult
    range_sess = (sess_hi - sess_lo) * mult
    with np.errstate(invalid="ignore", divide="ignore"):
        cov_p = np.where(np.isfinite(q50_p) & (q50_p > 0),
                         range_phase / q50_p, np.nan)
        cov_s = (range_sess / q50_s if np.isfinite(q50_s) and q50_s > 0
                 else np.full(dec_s.size, np.nan))

    # ladder_position: the HIGHEST band the realized segment range reaches.
    # REFUSED (-1) whenever any quantile is missing or the range is undefined.
    band = np.full(dec_s.size, LADDER_REFUSED, dtype=np.int64)
    lad_ok = np.all(np.isfinite(lad), axis=1) & np.isfinite(range_phase)
    if lad_ok.any():
        b = np.zeros(dec_s.size, dtype=np.int64)
        for q in range(lad.shape[1]):
            b = np.where(lad_ok & (range_phase >= lad[:, q]), q + 1, b)
        band = np.where(lad_ok, b, LADDER_REFUSED)

    # --- S5 slope / accel --------------------------------------------------
    def mid_at(secs):
        j = np.searchsorted(vt, secs, side="right") - 1
        v = np.where(j >= 0, vm[np.maximum(j, 0)], np.nan)
        return np.where(secs < 0, np.nan, v)

    m_now = mid_at(dec_s)
    m_1 = mid_at(dec_s - 60)
    m_5 = mid_at(dec_s - 300)
    slope_1 = (m_now - m_1) * mult
    slope_5 = (m_now - m_5) * mult / 5.0
    accel = slope_1 - slope_5

    # --- S9 rv nowcasts ----------------------------------------------------
    pref = _prefix_sq(vm)
    rv60 = _rv_window(vt, pref, np.maximum(dec_s - RV_SHORT_SEC, 0), dec_s, mult)
    rv1800 = _rv_window(vt, pref, np.maximum(dec_s - RV_LONG_SEC, 0), dec_s, mult)
    with np.errstate(invalid="ignore", divide="ignore"):
        rv_ratio = np.where(rv60 > 0, rv1800 / rv60, np.nan)

    # --- pivots ------------------------------------------------------------
    atr = float(r["atr14_usd"][sel[0]])
    psec, pside, pconf = _pivot_chain(asset, s, trade_date, atr,
                                      float(spec["tick_px"]),
                                      float(spec["tick_usd"]), mult)
    want = np.where(side[order] < 0, -1, 1)
    pivot_age = np.full(dec_s.size, -1, dtype=np.int64)
    for w in (-1, 1):
        m = want == w
        if m.any():
            pivot_age[m] = _last_pivot_age(psec, pside, pconf, dec_s[m], w)

    # --- certificates (c_c_roster, verbatim) -------------------------------
    wall = float(A.walls()[asset]["wall_usd"])
    cost = A.cost_map().get((asset, iso), float("nan"))
    if not np.isfinite(cost):
        cost = C.FEES_RT
    cert_close = np.full(sel.size, np.nan)
    cert_peak = np.full(sel.size, np.nan)
    walled = np.zeros(sel.size, dtype=bool)
    if with_certs:
        for t in range(sel.size):
            i = int(sel[t])
            pk, cl = CC.certificates(r, i, wall, cost)
            cert_peak[t] = pk[0]
            cert_close[t] = cl[0]
            walled[t] = CC._skel_query(r, i, wall)[3]

    # --- spread state ------------------------------------------------------
    phase_med = CA.phase_median_spreads(MC.M0_ROOT)
    med = np.array([phase_med.get((asset, trade_date.year,
                                   X.PHASE_NAMES[int(p)]), float("nan"))
                    for p in phase_dec])
    spread = r["spread_at_decision"][sel][order].astype(np.float64)
    with np.errstate(invalid="ignore", divide="ignore"):
        spread_ratio = np.where(med > 0, spread / med, np.nan)

    entry_mid = r["entry_mid"][sel][order].astype(np.float64)
    lvl = np.full(dec_s.size, np.nan)
    if with_levels:
        lvl = _nearest_kept_level_atr(asset, d8, s, trade_date,
                                      A.load_profile(asset, d8)[0],
                                      dec_s, entry_mid, atr, mult)

    # --- assemble (back in roster order) -----------------------------------
    def un(a):
        return np.asarray(a)[inv]

    phase_close = r["phase_close_sec"][sel].astype(np.int64)
    sess_close = r["sess_close_sec"][sel].astype(np.int64)
    fam_mask = r["fam_mask"][sel].astype(np.int64)
    open_utc = int(s.meta["open_utc"])
    extreme_age = np.where(side[order] < 0,
                           np.where(phase_hi_sec >= 0, dec_s - phase_hi_sec, -1),
                           np.where(phase_lo_sec >= 0, dec_s - phase_lo_sec, -1))
    mae = r["mae_before_argmax"][sel].astype(np.float64)

    f = {
        "asset": asset, "d8": d8, "n": int(sel.size),
        "i": sel.astype(np.int64),
        "cid": np.array([MC.make_cid(asset, d8, int(dec[t]), int(side[t]))
                         for t in range(sel.size)]),
        "dec_sec": dec, "side": side,
        "phase_dec": r["phase_dec"][sel].astype(np.int64),
        "phase_seg_start": un(ph_start), "phase_seg_end": un(ph_end),
        "klass": np.array([MC.class_of(int(m))[0] for m in fam_mask]),
        "fam_mask": fam_mask,
        "clock_sec": (open_utc + dec) % 86400,
        "coverage_phase": un(cov_p), "coverage_session": un(cov_s),
        "ladder_band": un(band), "regime_tercile": un(terc),
        "runway_phase_sec": phase_close - dec,
        "runway_sess_sec": sess_close - dec,
        "session_close_exit": phase_close == sess_close,
        "runway_frac": un((phase_close[order] - dec_s).astype(np.float64)
                          / np.maximum(ph_end - ph_start, 1)),
        "phase_hi": un(phase_hi), "phase_hi_sec": un(phase_hi_sec),
        "phase_lo": un(phase_lo), "phase_lo_sec": un(phase_lo_sec),
        "extreme_age_sec": un(extreme_age), "pivot_age_sec": un(pivot_age),
        "mid_now": un(m_now),
        "slope_1m_usd": un(slope_1), "slope_5m_usd": un(slope_5),
        "accel_usd": un(accel),
        "rv60_usd": un(rv60), "rv1800_usd": un(rv1800),
        "rv_ratio": un(rv_ratio),
        "spread_dec_usd": r["spread_at_decision"][sel].astype(np.float64),
        "spread_ratio": un(spread_ratio),
        "atr_usd": np.full(sel.size, atr),
        "level_dist_atr": un(lvl),
        "cert_close_usd": cert_close, "cert_peak_usd": cert_peak,
        "walled": walled, "mae_before_argmax": mae,
        "winner": (cert_close >= 1000.0) & (mae <= 300.0) & (~walled),
        "range_phase_usd": un(range_phase), "range_sess_usd": un(range_sess),
        "exp_move_q50_phase_usd": un(q50_p),
    }
    return f


# --------------------------------------------------------------- sessions ---
def sessions(asset, years=None):
    """Sorted [d8] of every roster session for `asset`, optionally year-filtered."""
    r = roster(asset, with_certs=False)
    ds = sorted({int(x) for x in r["date8"].tolist()})
    if years is not None:
        ds = [d for d in ds if (d // 10000) in years]
    return ds


def main():
    MC.verify_spec(force=True)
    asset = sys.argv[1] if len(sys.argv) > 1 else "SI"
    d8 = int(sys.argv[2]) if len(sys.argv) > 2 else sessions(asset)[0]
    f = frame(asset, d8, with_levels=True)
    sys.stdout.write("%s %d: %d candidates\n" % (asset, d8, f["n"]))
    for k in sorted(FRAME_FIELDS):
        v = f.get(k)
        if v is None or np.isscalar(v):
            continue
        sys.stdout.write("  %-22s %s\n" % (k, str(v[:3])[:96]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
