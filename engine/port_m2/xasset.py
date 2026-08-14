#!/usr/bin/python3
"""PORT M2 — THE CROSS-ASSET MARGINAL-INFORMATION MEASUREMENT.

THE QUESTION, IN ONE LINE
  The S11 CROSS-ASSET section was bugged to 100% refusal in EVERY sheet the
  D-090.6 information ceiling measured (journal 2026-08-15 ~15:40Z; the fix is
  `sections.py:1825` G-2, forward-only).  Cross-asset is therefore the one
  OWNED, NEVER-MEASURED information source.  Does it add capture?

WHAT THE CEILING ACTUALLY SAW — stated before any new number is quoted.
  The ceiling's SHEETS layer is "every matrix column that is not a digest
  column", and the M3 matrix already carries an `xasset` GROUP: 18 columns
  (`xa_{SI,HG,NKD}_{age_sec,rv1800,fuel_share_above,range_so_far,slope5m,
  sflow_phase}`, `m3_matrix.py:274`).  Those are CELL-GRAIN and
  AVAILABILITY-LAGGED — "that cell's LAST candidate row" of the other asset's
  most recent CLOSED cell, whose measured age has sd ~4.97e4 s on E6.  So the
  honest statement of the gap is NOT "no cross-asset number was ever in the
  fit"; it is:

      the ceiling saw a stale, cell-grain cross-asset read and NEVER saw the
      other assets' EPISODE-GRAIN state at the decision second.

  This module measures exactly that difference, and reports the 18 lagged
  columns as their own removable block so both readings are on the record.

NON-CAUSAL-BY-DESIGN, exactly as `info_ceiling` is: the universe is ALL of E6
(study + sealed blind), the fits are k-fold within the era, and nothing here is
a deployable policy.  The FEATURES, however, are strictly causal per row.

THE ACCESS RULE (the S11 fix, `sections.py:1825-1838`)
  All three assets are co-located on ONE session clock — `open_utc` is
  identical for SI/HG/NKD on every one of E6's 128 days (verified in
  `_verify_clock`, receipt field `n_days_clock_mismatch`).  The other asset's
  second therefore EQUALS the decision second, and the corrected guard admits
  the last SANE second STRICTLY BEFORE it.  Every window below is closed on the
  left and OPEN ON THE RIGHT at the decision second: [t-W, t).  No cross-asset
  read ever touches second t itself.

THE FEATURES — 15 kinds x 2 other assets = 30 columns.
  Role naming, not identity naming: `o1`/`o2` are the OTHER two assets in
  `MC.ASSET_ORDER` (SI, HG, NKD) with the own asset struck out, so
      SI -> (o1=HG, o2=NKD)   HG -> (o1=SI, o2=NKD)   NKD -> (o1=SI, o2=HG).
  Identity is already a feature (`asset_SI/asset_HG/asset_NKD`), so the model
  can recover it; role naming keeps all 30 columns populated instead of
  leaving a third of a 45-column identity-named block structurally NaN.
  Every column is DIMENSIONLESS or normalised by the OTHER asset's own ATR14,
  so one column may legitimately pool two assets.
  `_with` = multiplied by the OWN episode's side (+1 long / -1 short), the
  `f60_sflow_with` / `erosion_with_side` convention of `m3_matrix.py:1041`.

  ret60/ret300/ret1800_with  the other asset's SANE-mid return over [t-W, t)
                             in ITS OWN ATR14 units, x own side
  rv60 / rv1800              the other asset's realised vol over [t-W, t)
                             (`pattern_lib._rv_window`, the S9 nowcast
                             arithmetic verbatim) / its ATR14
  sflow60/300/1800_with      the other asset's signed AGGRESSOR flow over
                             [t-W, t) as a FRACTION of the window's traded
                             volume (scale-free), x own side.  Aggressor side
                             is the m0 trades tape's `side` — the schema audit
                             (journal 2026-08-15 ~14:30Z) confirmed
                             side-on-trades = aggressor from Databento
                             normative sources.
  erosion60_with             the other asset's L1 book-erosion ASYMMETRY:
                             imb(t-1) - imb(t-60) where
                             imb = (bid_sz - ask_sz)/(bid_sz + ask_sz) on the
                             m0 1s grid over TWO-SIDED seconds only, x own side
  evrate_z60                 the other asset's RAW MBP-1 EVENT RATE, z-scored:
                             (count over [t-60,t) minus the causal
                             session-to-date mean of fully-covered 60s counts)
                             / their sd.  THE ONLY FIELD THAT READS THE EVENT
                             CACHE, and the only one with a coverage hole (see
                             COVERAGE below).
  cov_phase                  the other asset's phase coverage state = its SANE
                             range so far in its own current phase segment /
                             its fvol `move_q50 x sigma_hat` for that segment
                             (`pattern_lib` cov_p verbatim)
  level_dist_atr             |nearest KEPT-family level BORN strictly before t
                             minus the other asset's mid(t-1)| / its ATR14,
                             inside the 1.5xATR band
                             (`pattern_lib._kept_levels` +
                             `_nearest_kept_level_atr` verbatim, run on the
                             OTHER asset's ledger)
  corr1s_60                  SAME-SECOND CO-MOVEMENT: Pearson r of the two
                             assets' 1s mid returns over [t-60, t)
  leadlag30m_peak            LEAD-LAG: the peak cross-correlation of 1s returns
                             over [t-1800, t) across lags in [-30, +30] s
  leadlag30m_lag             the signed lag at that peak, POSITIVE = THE OTHER
                             ASSET LEADS the own asset by that many seconds

COVERAGE (measured, not assumed).  The MBP-1 event cache is a per-candidate
union of [dec_sec-692, dec_sec+1] windows, so a cross-asset window lands in a
hole whenever the other asset had no candidate nearby: measured on E6, a 60s
cross-asset window is fully covered for 82% of episodes (300s: 75%, 1800s:
44%).  That is why 14 of the 15 kinds are built from the m0 SESSION GRID and
TRADES TAPE — full-session, no holes, and the SAME arithmetic `pattern_lib`
already commits to — and only `evrate_z60` (raw MBP-1 record rate, which
nothing else carries) reads the event cache and is REFUSED (NaN) where the
window is not fully covered.  Refusal, never a fabricated zero.

CLI
  xasset.py --build [--workers 8]   the 30-column episode-grain block
  xasset.py --fit                   ceiling arms (a) baseline (b) +xasset
                                    (c) xasset alone, marginal capture + CIs
  xasset.py --walls                 the wall-pair census with the new columns
  xasset.py --all --workers 8
"""
import argparse
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, "/workspace/engine/port_m0", "/workspace/engine/port_m1",
           "/workspace/engine/port_m1b", "/workspace/engine/port_m3",
           "/workspace/artifacts/cache/pylibs"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import m2_common as MC                    # noqa: E402
import assemble as A                      # noqa: E402
import common as C                        # noqa: E402
import census_common as X                 # noqa: E402
import pattern_lib as PL                  # noqa: E402
import panel_score as PS                  # noqa: E402
import info_ceiling as IC                 # noqa: E402

SECTION = ("D-028 cross-asset marginal information (E6, hindsight-fit, "
           "NON-CAUSAL-BY-DESIGN)")
VERSION = "PORT-M2-XASSET-V1"

OUT_ROOT = IC.OUT_ROOT
PROV = IC.PROV
SEED = IC.SEED
KFOLDS = IC.KFOLDS

RET_WINDOWS = (60, 300, 1800)
RV_WINDOWS = (60, 1800)                   # the committed S9 pair (rv60/rv1800)
FLOW_WINDOWS = (60, 300, 1800)            # = 60s / FLOW_5M_SEC / FLOW_30M_SEC
EROSION_SEC = 60
EVRATE_SEC = 60
COMOVE_SEC = 60
LEADLAG_SEC = 1800
LEADLAG_MAX_LAG = 30
LEADLAG_MIN_SPAN = 600                    # refuse a lead-lag on < 10 min of grid
EVRATE_MIN_REF = 30                       # refuse a z on < 30 reference windows

ROLES = ("o1", "o2")

# The 15 feature KINDS, in column order, with the one-line definition that the
# report prints.  Nothing is emitted that is not declared here.
KINDS = (
    ("ret60_with", "other's SANE-mid return over [t-60,t) / its ATR14, x side"),
    ("ret300_with", "other's SANE-mid return over [t-300,t) / its ATR14, x side"),
    ("ret1800_with", "other's SANE-mid return over [t-1800,t) / its ATR14, x side"),
    ("rv60", "other's realised vol over [t-60,t) (S9 _rv_window) / its ATR14"),
    ("rv1800", "other's realised vol over [t-1800,t) / its ATR14"),
    ("sflow60_with", "other's signed aggressor flow / traded volume, [t-60,t), x side"),
    ("sflow300_with", "other's signed aggressor flow / traded volume, [t-300,t), x side"),
    ("sflow1800_with", "other's signed aggressor flow / traded volume, [t-1800,t), x side"),
    ("erosion60_with", "other's L1 (bid_sz-ask_sz)/(bid_sz+ask_sz) at t-1 minus "
                       "at t-60, x side"),
    ("evrate_z60", "other's MBP-1 event count over [t-60,t), z vs the causal "
                   "session-to-date distribution of fully-covered 60s counts"),
    ("cov_phase", "other's SANE range so far in its own phase segment / its "
                  "fvol move_q50 x sigma_hat"),
    ("level_dist_atr", "|nearest KEPT-family level born < t - other's mid(t-1)| "
                       "/ its ATR14, inside 1.5xATR"),
    ("corr1s_60", "Pearson r of the two assets' 1s mid returns over [t-60,t)"),
    ("leadlag30m_peak", "peak cross-corr of 1s returns over [t-1800,t), lags "
                        "[-30,+30]s"),
    ("leadlag30m_lag", "the lag at that peak; POSITIVE = the OTHER asset LEADS"),
)

XCOLS = tuple("xs_%s_%s" % (r, k) for r in ROLES for k, _d in KINDS)
XLAYER = "XASSET"

# The 18 lagged, cell-grain cross-asset columns that were ALREADY inside the
# ceiling's SHEETS layer (m3_matrix.py:274) — declared so they can be struck
# out and the "no cross-asset information at all" baseline can be measured.
XA_CELLGRAIN_PREFIX = "xa_"


def other_roles(asset):
    """(o1, o2) = the other two assets in MC.ASSET_ORDER, own asset struck."""
    return tuple(a for a in MC.ASSET_ORDER if a != asset)


# ================================================ STAGE 1: THE FEATURES =====
def _verify_clock(d8):
    """The S11 co-location premise, re-tested per day rather than assumed."""
    opens = {}
    for a in MC.ASSET_ORDER:
        p = os.path.join(MC.M2_ROOT, "events", a, "%08d.json" % int(d8))
        if os.path.exists(p):
            with open(p) as fh:
                opens[a] = int(json.load(fh)["open_utc"])
    return len(set(opens.values())) <= 1, opens


def _event_rate_state(asset, d8, open_utc, n):
    """Per-second MBP-1 counts + the causal z-score scaffolding.

    Reads the committed event cache DIRECTLY (np.load on the npz), never
    `tape.ensure`: `ensure` RE-EXTRACTS from the raw payload when a requested
    range is outside the stored cover, which would rewrite the 12 GB corpus
    cache as a side effect of a measurement.  This module is read-only on it.
    """
    npz_p = os.path.join(MC.M2_ROOT, "events", asset, "%08d.npz" % int(d8))
    json_p = os.path.join(MC.M2_ROOT, "events", asset, "%08d.json" % int(d8))
    if not (os.path.exists(npz_p) and os.path.exists(json_p)):
        return None
    with open(json_p) as fh:
        meta = json.load(fh)
    if int(meta.get("open_utc", -1)) != int(open_utc):
        return None                        # a cover measured from another origin
    z = np.load(npz_p, allow_pickle=False)
    ts = z["ts_ns"]
    z.close()
    sec = (ts // 1_000_000_000) - int(open_utc)
    sec = sec[(sec >= 0) & (sec < n)]
    cnt = np.bincount(sec, minlength=n).astype(np.float64)
    cov = np.zeros(n, dtype=bool)
    for a, b in meta["cover"]:
        lo, hi = max(0, int(a)), min(n, int(b))
        if hi > lo:
            cov[lo:hi] = True
    W = EVRATE_SEC
    if n <= W:
        return None
    cs = np.concatenate(([0.0], np.cumsum(cnt)))
    cc = np.concatenate(([0], np.cumsum(cov.astype(np.int64))))
    # window ending EXCLUSIVE at u = [u-W, u); stored at index u, u in [W, n]
    Rw = np.full(n + 1, np.nan)
    Vw = np.zeros(n + 1, dtype=bool)
    Rw[W:] = cs[W:] - cs[:-W]
    Vw[W:] = (cc[W:] - cc[:-W]) == W
    v = Vw.astype(np.float64)
    r0 = np.where(Vw, Rw, 0.0)
    c_n = np.cumsum(v)
    c_s = np.cumsum(r0)
    c_s2 = np.cumsum(r0 * r0)
    return {"Rw": Rw, "Vw": Vw, "c_n": c_n, "c_s": c_s, "c_s2": c_s2}


def _asset_state(asset, d8):
    """Everything one asset contributes as the OTHER asset of a cross read."""
    sess = A.load_session(asset, int(d8))
    s = sess["s"]
    trade_date = sess["trade_date"]
    mult = float(C.ASSETS[asset]["mult"])
    n = int(s.n)
    open_utc = int(s.meta["open_utc"])

    # ATR14_prev: pattern_lib.py:954-964 verbatim (median over the session's
    # roster rows, REFUSE rather than broadcast a sentinel).
    r = A.roster(asset)
    sel = np.nonzero(r["date8"] == int(d8))[0]
    atr = float("nan")
    if sel.size:
        col = r["atr14_usd"][sel].astype(np.float64)
        ok = np.isfinite(col) & (col > 0)
        if ok.any():
            atr = float(np.median(col[ok]))
    if not (np.isfinite(atr) and atr > 0):
        b = A.bars(asset).get(trade_date, {})
        atr = float(b.get("ATR14_prev_usd", float("nan")))
    if not (np.isfinite(atr) and atr > 0):
        return None

    vt = s.vt
    vm = s.vm.astype(np.float64)
    pref = PL._prefix_sq(vm)

    # 1s ATR-normalised return series on the FULL second grid; a non-SANE
    # transition contributes 0 (no observed change), never a fabricated move.
    ret1s = np.zeros(n, dtype=np.float64)
    if n > 1:
        step = np.zeros(n, dtype=np.float64)
        good = s.valid[1:] & s.valid[:-1]
        step[1:] = np.where(good, np.diff(s.mid.astype(np.float64)), 0.0)
        ret1s = step * mult / atr

    # L1 depth imbalance on the 1s grid, TWO-SIDED seconds only, then the
    # index of the last second at or before u that carries one.
    tot = s.bid_sz.astype(np.float64) + s.ask_sz.astype(np.float64)
    have = s.valid & (tot > 0)
    imb = np.where(have,
                   (s.bid_sz.astype(np.float64) - s.ask_sz.astype(np.float64))
                   / np.where(tot > 0, tot, 1.0), np.nan)
    last_imb = np.maximum.accumulate(np.where(have, np.arange(n), -1))

    # trades tape prefix sums (pattern_lib.py:911-923 verbatim shape)
    tr = sess["trades"]
    t_sec = tr["sec"]
    t_sz = tr["size"].astype(np.int64)
    signed = np.where(tr["side"] == ord("B"), t_sz,
                      np.where(tr["side"] == ord("A"), -t_sz, 0))
    c_v = np.concatenate(([0], np.cumsum(t_sz)))
    c_s = np.concatenate(([0], np.cumsum(signed)))

    # per-phase-segment running SANE extremes, in vt-index space
    segs = PL._phase_segments(s)
    seg_start = np.array([g[1] for g in segs], dtype=np.int64)
    seg_end = np.array([g[2] for g in segs], dtype=np.int64)
    seg_code = np.array([g[0] for g in segs], dtype=np.int64)
    segmax = np.full(vt.size, np.nan)
    segmin = np.full(vt.size, np.nan)
    for st, en in zip(seg_start.tolist(), seg_end.tolist()):
        a0 = int(np.searchsorted(vt, st, side="left"))
        b0 = int(np.searchsorted(vt, en, side="left"))
        if b0 > a0:
            segmax[a0:b0] = np.maximum.accumulate(vm[a0:b0])
            segmin[a0:b0] = np.minimum.accumulate(vm[a0:b0])

    # fvol q50 per phase code (pattern_lib.py:820-846 verbatim)
    fv = A.fvol_rows()
    iso = trade_date.isoformat()
    q50 = {}
    for p in sorted(set(seg_code.tolist())):
        row = fv.get((asset, iso, X.PHASE_NAMES[int(p)]))
        if row:
            sig = A._f(row["sigma_hat_usd"])
            q50[int(p)] = A._f(row.get("move_q50_usd_per_sigma")) * sig
        else:
            q50[int(p)] = float("nan")

    lpx_k, lbn_k, _fam = PL._kept_levels(asset, int(d8), s, trade_date,
                                         A.load_profile(asset, int(d8))[0])

    return {"asset": asset, "n": n, "open_utc": open_utc, "mult": mult,
            "atr": atr, "vt": vt, "vm": vm, "pref": pref, "ret1s": ret1s,
            "imb": imb, "last_imb": last_imb, "t_sec": t_sec, "c_v": c_v,
            "c_s": c_s, "seg_start": seg_start, "seg_end": seg_end,
            "seg_code": seg_code, "segmax": segmax, "segmin": segmin,
            "q50": q50, "lpx": lpx_k, "lbn": lbn_k,
            "ev": _event_rate_state(asset, int(d8), open_utc, n)}


def _mid_at(st, sec):
    """Last SANE mid at or before `sec` (pattern_lib.mid_at)."""
    if sec < 0:
        return float("nan")
    j = int(np.searchsorted(st["vt"], sec, side="right")) - 1
    return float(st["vm"][j]) if j >= 0 else float("nan")


def _corr(a, b):
    if a.size < 8 or a.size != b.size:
        return float("nan")
    a = a - a.mean()
    b = b - b.mean()
    da = float(np.sqrt((a * a).sum()))
    db = float(np.sqrt((b * b).sum()))
    if not (da > 0 and db > 0):
        return float("nan")
    return float((a * b).sum() / (da * db))


def _leadlag(own_ret, oth_ret, t):
    """(peak cross-corr, lag) over [t-LEADLAG_SEC, t); lag > 0 = OTHER LEADS.

    Row i of the sliding view aligns own index k with other index k + (i - L0),
    so the fitted offset is L = i - L0 and "the other asset leads by m seconds"
    is L = -m.  The reported lag is therefore -L.  Every index touched is
    <= t-1: the widest read is other[t-LEADLAG_SEC + 2*L0 + span - 1] = t-1.
    """
    L0 = LEADLAG_MAX_LAG
    lo = max(0, t - LEADLAG_SEC)
    span = (t - lo) - 2 * L0
    if span < LEADLAG_MIN_SPAN:
        return float("nan"), float("nan")
    x = own_ret[lo + L0:t - L0]
    seg = oth_ret[lo:t]
    if x.size != span or seg.size != span + 2 * L0:
        return float("nan"), float("nan")
    Y = sliding_window_view(seg, span)          # (2*L0+1, span)
    xc = x - x.mean()
    dx = float(np.sqrt((xc * xc).sum()))
    if not dx > 0:
        return float("nan"), float("nan")
    Yc = Y - Y.mean(axis=1, keepdims=True)
    dy = np.sqrt((Yc * Yc).sum(axis=1))
    ok = dy > 0
    if not ok.any():
        return float("nan"), float("nan")
    num = Yc @ xc
    corr = np.full(Y.shape[0], np.nan)
    corr[ok] = num[ok] / (dy[ok] * dx)
    i = int(np.nanargmax(np.abs(corr)))
    return float(corr[i]), float(L0 - i)


def _cross_one(st, own_ret, t, side):
    """The 15 kinds for ONE other asset at own decision second `t`."""
    out = [float("nan")] * len(KINDS)
    n = st["n"]
    if t <= 1 or t > n:
        return out
    atr, mult = st["atr"], st["mult"]
    m_prev = _mid_at(st, t - 1)

    # --- returns -----------------------------------------------------------
    for k, W in enumerate(RET_WINDOWS):
        m0 = _mid_at(st, t - W)
        if np.isfinite(m_prev) and np.isfinite(m0):
            out[k] = (m_prev - m0) * mult / atr * side

    # --- realised vol ------------------------------------------------------
    base = len(RET_WINDOWS)
    for k, W in enumerate(RV_WINDOWS):
        rv = PL._rv_window(st["vt"], st["pref"],
                           np.array([max(0, t - W)]), np.array([t]), mult)[0]
        if np.isfinite(rv):
            out[base + k] = rv / atr

    # --- signed aggressor flow fraction ------------------------------------
    base += len(RV_WINDOWS)
    b_hi = int(np.searchsorted(st["t_sec"], t, side="left"))
    for k, W in enumerate(FLOW_WINDOWS):
        b_lo = int(np.searchsorted(st["t_sec"], max(0, t - W), side="left"))
        vol = float(st["c_v"][b_hi] - st["c_v"][b_lo])
        if vol > 0:
            out[base + k] = (float(st["c_s"][b_hi] - st["c_s"][b_lo])
                             / vol) * side

    # --- book erosion asymmetry -------------------------------------------
    base += len(FLOW_WINDOWS)
    j1 = int(st["last_imb"][min(t - 1, n - 1)])
    j0i = max(0, t - EROSION_SEC)
    j0 = int(st["last_imb"][min(j0i, n - 1)]) if j0i < n else -1
    if j1 >= 0 and j0 >= 0 and j1 != j0:
        out[base] = (float(st["imb"][j1]) - float(st["imb"][j0])) * side

    # --- event-rate z ------------------------------------------------------
    base += 1
    ev = st["ev"]
    if ev is not None and t <= n and ev["Vw"][t]:
        nn = float(ev["c_n"][t])
        if nn >= EVRATE_MIN_REF:
            m = float(ev["c_s"][t]) / nn
            var = float(ev["c_s2"][t]) / nn - m * m
            if var > 0:
                out[base] = (float(ev["Rw"][t]) - m) / float(np.sqrt(var))

    # --- phase coverage ----------------------------------------------------
    base += 1
    ks = int(np.searchsorted(st["seg_start"], t - 1, side="right")) - 1
    if 0 <= ks < st["seg_start"].size:
        j = int(np.searchsorted(st["vt"], t, side="left")) - 1
        j_ph = int(np.searchsorted(st["vt"], int(st["seg_start"][ks]),
                                   side="left"))
        q = st["q50"].get(int(st["seg_code"][ks]), float("nan"))
        if j >= j_ph and j >= 0 and np.isfinite(q) and q > 0:
            rng = (float(st["segmax"][j]) - float(st["segmin"][j])) * mult
            out[base] = rng / q

    # --- nearest kept level ------------------------------------------------
    base += 1
    if np.isfinite(m_prev) and st["lpx"].size:
        d = PL._nearest_kept_level_atr(st["lpx"], st["lbn"],
                                       np.array([t], dtype=np.int64),
                                       np.array([m_prev]), atr, mult)[0]
        out[base] = d

    # --- co-movement and lead-lag ------------------------------------------
    base += 1
    lo = max(0, t - COMOVE_SEC)
    if t - lo >= 8:
        out[base] = _corr(own_ret[lo:t], st["ret1s"][lo:t])
    base += 1
    pk, lg = _leadlag(own_ret, st["ret1s"], t)
    out[base] = pk
    out[base + 1] = lg
    return out


def _day_one(job):
    """All episodes of ONE date8, all three assets."""
    d8, eps = job                          # eps = [(asset, dec_sec, ep), ...]
    try:
        ok_clock, opens = _verify_clock(d8)
        states = {}
        for a in sorted({e[0] for e in eps} | set(MC.ASSET_ORDER)):
            if a not in MC.ASSET_ORDER:
                continue
            try:
                states[a] = _asset_state(a, d8)
            except Exception:              # noqa: BLE001  a missing session
                states[a] = None
        rows = []
        for asset, t, ep in eps:
            own = states.get(asset)
            vals = [float("nan")] * len(XCOLS)
            if own is not None:
                own_ret = own["ret1s"]
                for ri, o in enumerate(other_roles(asset)):
                    st = states.get(o)
                    if st is None:
                        continue
                    side = 1.0            # filled by the caller (see below)
                    v = _cross_one(st, own_ret, int(t), side)
                    vals[ri * len(KINDS):(ri + 1) * len(KINDS)] = v
            rows.append((int(ep), vals))
        return (int(d8), rows, bool(ok_clock), None)
    except Exception as exc:               # noqa: BLE001
        return (int(d8), [], True, "%s: %s" % (type(exc).__name__, exc))


# The side multiplication is applied in the parent so `_day_one` stays a pure
# function of (day, episodes) — the `_with` columns are the ones whose KIND
# name ends in `_with`.
WITH_MASK = np.array([k.endswith("_with") for _r in ROLES for k, _d in KINDS])


def build(workers=8, out_dir=None, limit_days=None):
    out_dir = out_dir or OUT_ROOT
    os.makedirs(out_dir, exist_ok=True)
    E = dict(np.load(os.path.join(out_dir, "episodes.npz"), allow_pickle=False))
    assets = np.array([MC.ASSET_ORDER[i] for i in E["asset_idx"].tolist()])
    jobs = {}
    for a, d, dec, ep in zip(assets.tolist(), E["d8"].tolist(),
                             E["dec_sec"].tolist(), E["ep"].tolist()):
        jobs.setdefault(int(d), []).append((a, int(dec), int(ep)))
    joblist = [(d, sorted(v)) for d, v in sorted(jobs.items())]
    if limit_days:
        joblist = joblist[:limit_days]
    t0 = time.time()
    got, errs, clock_bad = {}, [], []
    with mp.Pool(processes=int(workers)) as pool:
        for k, (d8, rows, ok_clock, err) in enumerate(
                pool.imap_unordered(_day_one, joblist, chunksize=1), start=1):
            if err:
                errs.append("%d %s" % (d8, err))
            if not ok_clock:
                clock_bad.append(d8)
            for ep, vals in rows:
                got[ep] = vals
            if k % 10 == 0 or k == len(joblist):
                el = time.time() - t0
                sys.stderr.write("xasset %d/%d days %.0fs eta %.0fs errs=%d\n"
                                 % (k, len(joblist), el,
                                    el / k * (len(joblist) - k), len(errs)))
                sys.stderr.flush()
    Xa = np.full((E["ep"].size, len(XCOLS)), np.nan, dtype=np.float32)
    for i, ep in enumerate(E["ep"].tolist()):
        v = got.get(int(ep))
        if v is not None:
            Xa[i, :] = v
    side = E["side"].astype(np.float32)
    Xa[:, WITH_MASK] *= side[:, None]
    np.savez_compressed(os.path.join(out_dir, "xasset.npz"), X=Xa,
                        cols=np.array(XCOLS), ep=E["ep"])
    fin = np.isfinite(Xa)
    rec = {"version": VERSION, "section": SECTION,
           "n_episodes": int(E["ep"].size), "n_days": len(joblist),
           "n_cols": len(XCOLS), "n_errors": len(errs), "errors": errs[:50],
           "n_days_clock_mismatch": len(clock_bad),
           "days_clock_mismatch": clock_bad[:20],
           "populated_frac_overall": float(fin.mean()),
           "populated_frac_by_col": {c: round(float(fin[:, j].mean()), 4)
                                     for j, c in enumerate(XCOLS)},
           "secs": round(time.time() - t0, 1)}
    with open(os.path.join(out_dir, "xasset.receipt.json"), "w") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True)
    sys.stderr.write("xasset: %d episodes x %d cols, populated %.3f, %d errs, "
                     "%.0fs\n" % (E["ep"].size, len(XCOLS),
                                  rec["populated_frac_overall"], len(errs),
                                  rec["secs"]))
    return Xa


# ============================================== the shared load path =========
def load(out_dir=None):
    """`info_ceiling.load()` (185 view + 40 seq = the committed 225) plus the
    30 XASSET columns as their own layer."""
    out_dir = out_dir or OUT_ROOT
    E = IC.load(out_dir=out_dir, with_seq=True)
    p = os.path.join(out_dir, "xasset.npz")
    if not os.path.exists(p):
        raise SystemExit("xasset.npz missing — run --build first")
    Z = np.load(p, allow_pickle=False)
    if not np.array_equal(Z["ep"], E["ep"]):
        raise SystemExit("xasset.npz episode order differs from episodes.npz")
    xc = [str(x) for x in Z["cols"]]
    E["X"] = np.column_stack([E["X"], Z["X"]]).astype(np.float32)
    E["cols"] = E["cols"] + xc
    E["layer"] = np.concatenate([E["layer"], np.array([XLAYER] * len(xc))])
    E["group"] = np.concatenate([E["group"], np.array(["xasset_ep"] * len(xc))])
    return E


def _cols_for(E, layers, drop_prefix=None):
    """`info_ceiling._cols_for` with an optional column-name strike-out."""
    sel = np.isin(E["layer"], list(layers))
    if drop_prefix:
        sel = sel & ~np.array([c.startswith(drop_prefix) for c in E["cols"]])
    j = np.nonzero(sel)[0]
    Xs = E["X"][:, j]
    return j[np.array([np.nanstd(Xs[:, k].astype(np.float64)) > 0
                       for k in range(j.size)])]


# ==================================================== STAGE 2: THE FITS ======
VIEWS = ("DIGEST", "SHEETS", "SEQ")

FEATURE_SETS = (
    ("a_BASE_225", VIEWS, None,
     "the committed information-ceiling feature set, reproduced byte-for-byte "
     "(185 view + 40 seq); INCLUDES the 18 lagged cell-grain xa_* columns"),
    ("a0_BASE_207_no_xa", VIEWS, XA_CELLGRAIN_PREFIX,
     "the same set with the 18 lagged cell-grain xa_* columns STRUCK — the "
     "only genuinely cross-asset-free baseline"),
    ("b_BASE_plus_XASSET", VIEWS + (XLAYER,), None,
     "baseline + the 30 episode-grain cross-asset columns"),
    ("b0_BASE_no_xa_plus_XASSET", VIEWS + (XLAYER,), XA_CELLGRAIN_PREFIX,
     "the cross-asset-free baseline + the 30 episode-grain columns"),
    ("c_XASSET_only", (XLAYER,), None,
     "the 30 episode-grain cross-asset columns ALONE"),
)

REGIMES = ("HONEST_KFOLD_DAY", "HONEST_KFOLD_RANDOM", "SOFT_IN_SAMPLE")

FIT_COLS = IC.FIT_COLS


def _sess_realised(E, take_idx):
    import m3_walk as MW
    D = IC.as_D(E)
    rows = MW.replay_rows(D, take_idx)
    return {r["session"]: r["realised"] for r in rows}


def _marginal(E, orc, real_a, real_b, tag_a, tag_b):
    """Paired, DAY-CLUSTERED interval for capture(b) - capture(a).

    `PS.cluster_ratio` verbatim on the PER-SESSION DIFFERENCE numerator over the
    SAME oracle denominator: sum(realised_b - realised_a) / sum(oracle) is
    exactly capture(b) - capture(a), and the CR1 sandwich is then the interval
    of the difference rather than of two separately-estimated ratios.
    """
    sess = sorted(orc)
    num = [real_b.get(s, 0.0) - real_a.get(s, 0.0) for s in sess]
    den = [orc[s] for s in sess]
    cl = [s.split("|")[1] for s in sess]
    st = PS.cluster_ratio(num, den, cl)
    return {"comparison": "%s MINUS %s" % (tag_b, tag_a),
            "delta_capture": st["ratio"] if st else float("nan"),
            "ci_lo": st.get("ci_lo") if st else None,
            "ci_hi": st.get("ci_hi") if st else None,
            "n_clusters": st.get("n_clusters") if st else 0,
            "delta_usd": float(sum(num)), "oracle_usd": float(sum(den))}


def run_fits(out_dir=None):
    out_dir = out_dir or OUT_ROOT
    os.makedirs(out_dir, exist_ok=True)
    t0 = time.time()
    E = load(out_dir=out_dir)
    orc, _rep = IC.denominators(E)
    d8 = E["d8"]
    rows, takes = [], {}
    for name, layers, drop, _doc in FEATURE_SETS:
        j = _cols_for(E, layers, drop_prefix=drop)
        Xf = np.ascontiguousarray(E["X"][:, j], dtype=np.float32)
        for arm in REGIMES:
            r = IC._arm(E, Xf, name, arm, orc, d8, rows)
            takes[(name, arm)] = r["_take_idx"]
            sys.stderr.write("%-26s %-20s n=%-4d capture=%.4f  (%.0fs)\n"
                             % (name, arm, Xf.shape[1], r["capture"],
                                time.time() - t0))
            sys.stderr.flush()
    _w(os.path.join(PROV, "XASSET_FITS.tsv"), FIT_COLS, rows,
       ["THE SAME INSTRUMENT AS INFO_CEILING_FITS.tsv: same episodes.npz, same "
        "seed %d, same %d folds of whole DAYS, same top-3-per-asset-day "
        "schedule with the D-077 veto ON, same oracle denominator "
        "(m3_walk.topn_takes / replay_rows / oracle_ceiling verbatim)"
        % (SEED, KFOLDS),
        "a_BASE_225 REPRODUCES the committed L1L2L3_all_views row; any drift "
        "from it is an instrument defect, not a finding"])

    # ---- the marginal table ------------------------------------------------
    real = {k: _sess_realised(E, v) for k, v in takes.items()}
    marg = []
    pairs = (("a_BASE_225", "b_BASE_plus_XASSET"),
             ("a0_BASE_207_no_xa", "b0_BASE_no_xa_plus_XASSET"),
             ("a0_BASE_207_no_xa", "a_BASE_225"),
             ("a_BASE_225", "c_XASSET_only"))
    by = {r["arm"]: r for r in rows if r.get("kind") == "fit"}
    for arm in REGIMES:
        for a_, b_ in pairs:
            if (a_, arm) not in real or (b_, arm) not in real:
                continue
            m = _marginal(E, orc, real[(a_, arm)], real[(b_, arm)], a_, b_)
            ra = by["%s|%s" % (a_, arm)]
            rb = by["%s|%s" % (b_, arm)]
            m.update({"regime": arm,
                      "capture_a": ra["capture"], "capture_b": rb["capture"],
                      "n_feat_a": ra["n_features"], "n_feat_b": rb["n_features"],
                      "rho_a": ra["rho_champion"], "rho_b": rb["rho_champion"],
                      "auc_a": ra["auc_winner"], "auc_b": rb["auc_winner"],
                      "exp_a": ra["expectancy_usd"], "exp_b": rb["expectancy_usd"]})
            marg.append(m)
    _w(os.path.join(PROV, "XASSET_MARGINAL.tsv"),
       ("regime", "comparison", "capture_a", "capture_b", "delta_capture",
        "ci_lo", "ci_hi", "n_clusters", "delta_usd", "oracle_usd",
        "n_feat_a", "n_feat_b", "rho_a", "rho_b", "auc_a", "auc_b",
        "exp_a", "exp_b"), marg,
       ["delta_capture = capture(b) - capture(a) as ONE clustered ratio: "
        "sum over sessions of (realised_b - realised_a) / sum(oracle), CR1 "
        "interval CLUSTERED BY DAY (the D-036/D-073 draw unit).  This is a "
        "PAIRED interval — the two arms share every session and the whole "
        "denominator — so it is far tighter than differencing two separate "
        "arm CIs",
        "rho = out-of-fold Spearman of the champion head; auc = the winner "
        "head's ROC AUC.  Both are SCHEDULE-FREE readings and move before "
        "capture does"])
    rec = {"version": VERSION, "secs": round(time.time() - t0, 1),
           "n_episodes": int(E["dec_sec"].size), "n_sessions": len(orc),
           "n_days": int(np.unique(d8).size), "seed": SEED, "kfolds": KFOLDS,
           "oracle_usd_total": float(sum(orc.values()))}
    with open(os.path.join(out_dir, "xasset_fits.receipt.json"), "w") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True)
    return rows, marg


def _w(path, cols, rows, extra=()):
    with open(path, "w") as fh:
        fh.write("# PORT M2 %s (%s)\n" % (SECTION, VERSION))
        fh.write("# NON-CAUSAL-BY-DESIGN: hindsight-fit upper bound over ALL "
                 "E6 sessions (study + sealed blind). NOT a deployable result.\n")
        for e in extra:
            fh.write("# %s\n" % e)
        fh.write("\t".join(cols) + "\n")
        for r in rows:
            fh.write("\t".join(IC._fmt(r.get(c, "")) for c in cols) + "\n")
    sys.stderr.write("wrote %s (%d rows)\n" % (path, len(rows)))


# ============================================ STAGE 3: THE WALL PAIRS ========
def _xasset_combos(ranked):
    """The cross-asset block's OWN paired separation power, on top of the
    committed combination ladder: the 30 columns alone, and their best 5 by the
    same in-sample ranking the ladder uses."""
    rx = [f for f in ranked if f in set(XCOLS)]
    return [(len(rx), rx, "XASSET-ONLY all %d fields"),
            (5, rx, "XASSET-ONLY top%d fields"),
            (1, rx, "XASSET-ONLY top%d field")]


def run_walls(out_dir=None):
    """`info_ceiling.run_walls` verbatim, on the 255-column matrix."""
    E = load(out_dir=out_dir)
    return IC.run_walls(out_dir=out_dir, E=E, prefix="XASSET_",
                        extra_combos=_xasset_combos)


# ------------------------------------------------------------- the report ---
def feature_doc():
    L = []
    for r in ROLES:
        for k, d in KINDS:
            L.append(("xs_%s_%s" % (r, k), r, k, d))
    return L


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--fit", action="store_true")
    ap.add_argument("--walls", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit-days", dest="limit_days", type=int, default=None)
    a = ap.parse_args(argv)
    if a.build or a.all:
        build(workers=a.workers, limit_days=a.limit_days)
    if a.fit or a.all:
        run_fits()
    if a.walls or a.all:
        run_walls()
    return 0


if __name__ == "__main__":
    sys.exit(main())
