#!/usr/bin/python3
"""PORT M1 Track B-3 — LEVEL LEDGER (§4, D-050) + the touch/re-arm state machine.

Causal by construction: every level's price is known STRICTLY PRIOR to the
second it is active for.  Sources (a)-(f) of §4, plus the CC-M1-1(A) ladders:

  FVOL_BAND     (a) anchor +- k x sigma_hat, k in {0.5,1,1.5,2},
                    anchor in {prev settle, each phase open}
  FVOL_LADDER   (a)+CC-M1-1(A) anchor +- Q_q(range/sigma_hat) x sigma_hat,
  FVOL_LADDER_RS    q in {.10,.25,.50,.75,.90}; RS = regime-scaled calibration
  PRIOR_DAY     (b) prior-session H / L / settle
  PRIOR_WEEK    (b) prior ISO-week H / L
  NDAY          (b) N-session lookback H / L, N in {2,3,5,10,20}
  PHASE_HL      (c) per-segment H / L, segment in {OVERNIGHT,TOKYO,LONDON,NY},
                    lookback in {1,2,3,5} sessions
  VWAP          (d) causal session/phase VWAP and +-{1,2} x causal sigma_vwap
  PROFILE       (e) prior-session/phase POC, VAH, VAL, HVN, LVN, single-print
                    zone edges, poor high/low  (from §5)
  DEV_POC       (e) causal developing POC of the live session
  ROUND         (f) the pinned 1-2-5 grids

STATE MACHINE (§4, the first of the two red-first algorithms):
  tol      = max(2 x tick_$, 0.05 x ATR14_$) / mult          [price units]
  ARM      a level arms after >= 300 observed seconds with |mid - L| > 2 x tol,
           and re-arms at every phase boundary
  TOUCH    the first observed second with |mid - L| <= tol while ARMED; the
           level then disarms and must re-arm before it can be touched again
  VIRGIN   never within tol since creation (the strict D-050(d) reading, which
           does NOT depend on arming: a level traded through before it ever
           armed is not virgin)
  OUTCOME  per touch, resolved inside the 15-min window §6 names:
           REJECT  mid moves >= max(0.11 x ATR14_$, 6 ticks_$)/mult back to the
                   approach side
           BREAK   mid holds beyond the level by > tol for >= 60s
           RECLAIM after a BREAK, mid re-crosses and holds >= 120s on the
                   approach side (searched to session close - §6 states no
                   bound; the elapsed time is recorded so M1.B can pin one)
"""
import datetime as dt
import multiprocessing as mp
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m1_common as M
import common as C
import census_common as X
import b2_fvol as B2
import b4_profiles as B4

SECTION = "§4 level ledger"

# --- state machine constants (§4/§6)
ARM_SECONDS = 300
ARM_DISTANCE_MULT = 2.0
TOL_TICKS = 2                    # max(2 x tick_$, 0.05 x ATR14_$)
TOL_ATR_FRAC = 0.05
REJECT_ATR_FRAC = 0.11           # §6 max(0.11 x ATR14_$, 6 ticks_$)
REJECT_TICKS = 6
REJECT_WINDOW = 900              # §6 "within 15 min"
BREAK_HOLD = 60                  # §6 "stays beyond for >= 60s"
RECLAIM_HOLD = 120               # §6 "holds >= 120s"

# --- source parameters (§4)
FVOL_K = (0.5, 1.0, 1.5, 2.0)
NDAY_LOOKBACKS = (2, 3, 5, 10, 20)
PHASE_LOOKBACKS = (1, 2, 3, 5)
VWAP_BANDS = (0.0, 1.0, -1.0, 2.0, -2.0)
ROUND_GRIDS = {"SI": (0.25, 0.50, 1.00),      # §4(f) pinned constants
               "HG": (0.05, 0.10),
               "NKD": (100.0, 250.0, 500.0)}
ROUND_WINDOW_SIGMA = 2.0         # implementation bound (see SPEC GAPS)

OUTCOME_NONE, OUTCOME_REJECT, OUTCOME_BREAK, OUTCOME_RECLAIM = 0, 1, 2, 3
OUTCOME_NAMES = ("NONE", "REJECT", "BREAK", "RECLAIM")

FAMILIES = ("FVOL_BAND", "FVOL_LADDER", "FVOL_LADDER_RS", "PRIOR_DAY",
            "PRIOR_WEEK", "NDAY", "PHASE_HL", "VWAP", "PROFILE", "DEV_POC",
            "ROUND")

PARAMS = {
    "spec_section": SECTION,
    "tolerance": "max(2 x tick_$, %.2f x ATR14_$) / mult" % TOL_ATR_FRAC,
    "arm": "%ds observed (two-sided) seconds with |mid-L| > %.1f x tol; "
           "re-arms at every phase boundary" % (ARM_SECONDS, ARM_DISTANCE_MULT),
    "touch": "first observed second with |mid-L| <= tol while armed",
    "virgin": "never within tol since creation (arming-independent)",
    "outcome_window_sec": REJECT_WINDOW,
    "reject_move": "max(%.2f x ATR14_$, %d x tick_$) / mult"
                   % (REJECT_ATR_FRAC, REJECT_TICKS),
    "break_hold_sec": BREAK_HOLD,
    "reclaim_hold_sec": RECLAIM_HOLD,
    "reclaim_search": "to session close (§6 states no bound; elapsed recorded)",
    "families": list(FAMILIES),
    "fvol_k": list(FVOL_K),
    "ladder_q": list(B2.LADDER_Q),
    "nday_lookbacks": list(NDAY_LOOKBACKS),
    "phase_lookbacks": list(PHASE_LOOKBACKS),
    "vwap_bands": list(VWAP_BANDS),
    "round_grids": {k: list(v) for k, v in ROUND_GRIDS.items()},
    "round_window": "+-%.1f x sigma_hat(session) around the prior settle "
                    "(§4(f) states no window - implementation bound)"
                    % ROUND_WINDOW_SIGMA,
    "level_identity": "(level_key, price): a source that moves its price "
                      "creates a NEW level object (new created_ts, virgin "
                      "again); identity persists across sessions",
    "snapshots": "active set at the session open and at every phase boundary",
}


# =========================================================== history tables ==
def load_v1_history(asset):
    """{trade_date: {segment: {...}}} from the §3 V1 table (generated, causal
    use only: session d reads segments of sessions < d)."""
    path = M.out_path("fvol", "v1_realized.tsv")
    cols, hist = None, {}
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            if f[0] != asset:
                continue
            r = dict(zip(cols, f))
            d = dt.date.fromisoformat(r["trade_date"])
            hist.setdefault(d, {})[r["segment"]] = {
                k: (float(r[k]) if r[k] else float("nan"))
                for k in ("open_px", "high_px", "low_px", "close_px",
                          "range_usd", "sigma_usd", "rv_usd")}
            hist[d][r["segment"]]["first_sec"] = int(float(r["first_sec"])) \
                if r["first_sec"] else -1
    # Drop the stale-book receipts (b2_fvol.series_for): a session whose traded
    # range is exactly $0 is a frozen quote, not a session, and must never
    # supply a prior-day / N-day / per-phase level.
    for d in [k for k, v in hist.items()
              if not B2._pos(v.get("SESSION", {}).get("range_usd", 0.0))]:
        del hist[d]
    return hist


def load_forecasts(asset):
    """{(trade_date, segment): row} from the §3/CC-M1-1 forecast table."""
    path = M.out_path("fvol", "fvol_forecasts.tsv")
    cols, out = None, {}
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            if f[0] != asset:
                continue
            r = dict(zip(cols, f))
            out[(dt.date.fromisoformat(r["trade_date"]), r["segment"])] = r
    return out


def _fnum(r, k):
    v = r.get(k, "")
    return float(v) if v not in ("", None) else float("nan")


# ============================================================ level builder ==
class Level(object):
    __slots__ = ("key", "family", "price", "series", "active_from",
                 "created_d8", "dynamic")

    def __init__(self, key, family, price, active_from=0, series=None,
                 dynamic=False):
        self.key = key
        self.family = family
        self.price = price
        self.series = series
        self.active_from = active_from
        self.dynamic = dynamic
        self.created_d8 = 0


def _seg_open_sec(s, seg):
    """First session-second of a segment (phase open / session open)."""
    if seg == "SESSION":
        return 0
    if seg == "OVERNIGHT":
        return 0
    p = X.PHASE_NAMES.index(seg)
    w = np.nonzero(s.phase_tag == p)[0]
    return int(w[0]) if w.size else -1


def build_levels(asset, s, trade_date, hist, fc, prof_prev, prof_cur, atr_usd):
    """Every §4 level active in this session, with its creation second."""
    spec = C.ASSETS[asset]
    mult, tick_px = spec["mult"], spec["tick_px"]
    dates = sorted(hist)
    i = dates.index(trade_date) if trade_date in dates else -1
    prev = dates[i - 1] if i >= 1 else None
    out = []

    # ---------------------------------------------------- (a) fvol bands ----
    anchors = []
    if prev is not None:
        settle = hist[prev]["SESSION"]["close_px"]
        if np.isfinite(settle):
            anchors.append(("SETTLE", settle, 0, "SESSION"))
    for seg in ("TOKYO", "LONDON", "NY"):
        o = _seg_open_sec(s, seg)
        if o < 0:
            continue
        j = int(np.searchsorted(s.vt, o, side="left"))
        if j >= s.vt.size:
            continue
        anchors.append(("OPEN_" + seg, float(s.vm[j]), int(s.vt[j]), seg))
    for (aname, apx, asec, seg) in anchors:
        row = fc.get((trade_date, seg))
        if row is None:
            continue
        sig_usd = _fnum(row, "sigma_hat_usd")
        if not np.isfinite(sig_usd) or sig_usd <= 0:
            continue
        sig_px = sig_usd / mult
        for k in FVOL_K:
            for sgn in (1, -1):
                out.append(Level("FVOL_BAND|%s|k%.1f|%+d" % (aname, k, sgn),
                                 "FVOL_BAND", apx + sgn * k * sig_px, asec))
        for fam, pre in (("FVOL_LADDER", "move_%s_usd_per_sigma"),
                         ("FVOL_LADDER_RS", "move_rs_%s_usd_per_sigma")):
            for q in B2.LADDER_Q:
                qn = "q%02d" % int(q * 100)
                m_ = _fnum(row, pre % qn)
                if not np.isfinite(m_):
                    continue
                for sgn in (1, -1):
                    out.append(Level("%s|%s|%s|%+d" % (fam, aname, qn, sgn),
                                     fam, apx + sgn * m_ * sig_px, asec))

    # ------------------------------------- (b) prior day / week / N-day -----
    if prev is not None:
        ps = hist[prev]["SESSION"]
        for nm, v in (("H", ps["high_px"]), ("L", ps["low_px"]),
                      ("SETTLE", ps["close_px"])):
            if np.isfinite(v):
                out.append(Level("PRIOR_DAY|%s" % nm, "PRIOR_DAY", v, 0))
    wk = trade_date.isocalendar()[:2]
    pw = [d for d in dates[:max(i, 0)] if d.isocalendar()[:2] < wk]
    if pw:
        lastwk = pw[-1].isocalendar()[:2]
        sel = [d for d in pw if d.isocalendar()[:2] == lastwk]
        hs = [hist[d]["SESSION"]["high_px"] for d in sel]
        ls = [hist[d]["SESSION"]["low_px"] for d in sel]
        hs = [v for v in hs if np.isfinite(v)]
        ls = [v for v in ls if np.isfinite(v)]
        if hs:
            out.append(Level("PRIOR_WEEK|H", "PRIOR_WEEK", max(hs), 0))
        if ls:
            out.append(Level("PRIOR_WEEK|L", "PRIOR_WEEK", min(ls), 0))
    for n in NDAY_LOOKBACKS:
        sel = dates[max(0, i - n):i]
        if len(sel) < n:
            continue
        hs = [hist[d]["SESSION"]["high_px"] for d in sel]
        ls = [hist[d]["SESSION"]["low_px"] for d in sel]
        hs = [v for v in hs if np.isfinite(v)]
        ls = [v for v in ls if np.isfinite(v)]
        if hs:
            out.append(Level("NDAY|N%d|H" % n, "NDAY", max(hs), 0))
        if ls:
            out.append(Level("NDAY|N%d|L" % n, "NDAY", min(ls), 0))

    # --------------------------------------------- (c) per-phase H/L --------
    for seg in M.SEG_NAMES:
        for lb in PHASE_LOOKBACKS:
            sel = dates[max(0, i - lb):i]
            if len(sel) < lb:
                continue
            hs = [hist[d].get(seg, {}).get("high_px", float("nan")) for d in sel]
            ls = [hist[d].get(seg, {}).get("low_px", float("nan")) for d in sel]
            hs = [v for v in hs if np.isfinite(v)]
            ls = [v for v in ls if np.isfinite(v)]
            if hs:
                out.append(Level("PHASE_HL|%s|lb%d|H" % (seg, lb), "PHASE_HL",
                                 max(hs), 0))
            if ls:
                out.append(Level("PHASE_HL|%s|lb%d|L" % (seg, lb), "PHASE_HL",
                                 min(ls), 0))

    # ------------------------------------------------ (d) causal VWAP -------
    out.extend(_vwap_levels(asset, s))

    # ------------------------------------ (e) volume-profile objects --------
    if prof_prev is not None:
        for scope in B4.SCOPES:
            for obj in ("poc", "vah", "val"):
                t = int(prof_prev.get("%s_%s_tick" % (scope, obj), -1))
                if t >= 0:
                    out.append(Level("PROFILE|%s|%s" % (scope, obj.upper()),
                                     "PROFILE", t * tick_px, 0))
            if scope != "SESSION":
                continue
            for nm in ("hvn", "lvn"):
                ticks = prof_prev.get("%s_%s_ticks" % (scope, nm),
                                      np.zeros(0, np.int64))
                prom = prof_prev.get("%s_%s_prom" % (scope, nm),
                                     np.zeros(0, np.float64))
                order = np.argsort(-np.asarray(prom, dtype=np.float64),
                                   kind="stable")
                for rank, oi in enumerate(order.tolist()):
                    out.append(Level("PROFILE|%s|%s%d" % (scope, nm.upper(),
                                                          rank),
                                     "PROFILE",
                                     int(ticks[oi]) * tick_px, 0))
            sp = np.asarray(prof_prev.get("%s_single_print_ticks" % scope,
                                          np.zeros(0, np.int64)))
            for zi, (a, b) in enumerate(_zones(sp)):
                out.append(Level("PROFILE|%s|SPLO%d" % (scope, zi), "PROFILE",
                                 a * tick_px, 0))
                if b != a:
                    out.append(Level("PROFILE|%s|SPHI%d" % (scope, zi),
                                     "PROFILE", b * tick_px, 0))
            if int(prof_prev.get("%s_poor_high" % scope, 0)):
                t = int(prof_prev.get("%s_vah_tick" % scope, -1))
                ph = hist.get(prev, {}).get("SESSION", {}).get("high_px",
                                                               float("nan"))
                if np.isfinite(ph):
                    out.append(Level("PROFILE|%s|POOR_H" % scope, "PROFILE",
                                     ph, 0))
            if int(prof_prev.get("%s_poor_low" % scope, 0)):
                pl = hist.get(prev, {}).get("SESSION", {}).get("low_px",
                                                               float("nan"))
                if np.isfinite(pl):
                    out.append(Level("PROFILE|%s|POOR_L" % scope, "PROFILE",
                                     pl, 0))
    if prof_cur is not None:
        dsec = np.asarray(prof_cur.get("dev_sec", np.zeros(0, np.int32)))
        dpoc = np.asarray(prof_cur.get("dev_poc_tick", np.zeros(0, np.int64)))
        if dsec.size:
            ser = np.full(s.vt.size, np.nan)
            j = np.searchsorted(dsec, s.vt, side="right") - 1
            ok = j >= 0
            ser[ok] = dpoc[j[ok]] * tick_px
            first = int(np.searchsorted(s.vt, int(dsec[0]), side="left"))
            out.append(Level("DEV_POC|SESSION", "DEV_POC", float("nan"),
                             int(s.vt[first]) if first < s.vt.size else 0,
                             series=ser, dynamic=True))

    # ---------------------------------------------- (f) round numbers -------
    if prev is not None:
        settle = hist[prev]["SESSION"]["close_px"]
        row = fc.get((trade_date, "SESSION"))
        sig_px = float("nan")
        if row is not None:
            sv = _fnum(row, "sigma_hat_usd")
            sig_px = sv / mult if np.isfinite(sv) else float("nan")
        if not np.isfinite(sig_px):
            sig_px = (atr_usd / mult) if np.isfinite(atr_usd) else float("nan")
        if np.isfinite(settle) and np.isfinite(sig_px) and sig_px > 0:
            half = ROUND_WINDOW_SIGMA * sig_px
            for g in ROUND_GRIDS[asset]:
                k0 = int(np.ceil((settle - half) / g))
                k1 = int(np.floor((settle + half) / g))
                if k1 - k0 > 400:            # pathological guard, never hit
                    continue
                for k in range(k0, k1 + 1):
                    out.append(Level("ROUND|%g|%g" % (g, k * g), "ROUND",
                                     k * g, 0))
    return out


def _zones(ticks):
    """Contiguous runs of tick indices -> [(first, last), ...]."""
    if ticks.size == 0:
        return []
    out = []
    a = prev = int(ticks[0])
    for t in ticks[1:].tolist():
        if t == prev + 1:
            prev = t
            continue
        out.append((a, prev))
        a = prev = t
    out.append((a, prev))
    return out


def _vwap_levels(asset, s):
    """§4(d): causal running VWAP +- {1,2} x causal sigma_vwap, session + phase."""
    z = np.load(s.path, allow_pickle=False)
    tsec = z["trades_sec"].astype(np.int64)
    tpx = z["trades_px"].astype(np.int64)
    tsz = z["trades_size"].astype(np.float64)
    z.close()
    px_scale = C.ASSETS[asset]["px_scale"]
    good = (tpx > 0) & (tpx < C.SENT_HI) & (tsz > 0) & (tsec >= 0) & (tsec < s.n)
    tsec, tpx, tsz = tsec[good], tpx[good] * px_scale, tsz[good]
    out = []
    scopes = [("SESSION", np.ones(s.n, dtype=bool))]
    for p, nm in enumerate(X.PHASE_NAMES):
        scopes.append((nm, s.phase_tag == p))
    for nm, mask in scopes:
        secs = np.nonzero(mask)[0]
        if secs.size == 0:
            continue
        lo, hi = int(secs[0]), int(secs[-1])
        sel = (tsec >= lo) & (tsec <= hi)
        if sel.sum() < 2:
            continue
        v = np.zeros(s.n)
        vp = np.zeros(s.n)
        vp2 = np.zeros(s.n)
        np.add.at(v, tsec[sel], tsz[sel])
        np.add.at(vp, tsec[sel], tsz[sel] * tpx[sel])
        np.add.at(vp2, tsec[sel], tsz[sel] * tpx[sel] * tpx[sel])
        cv = np.cumsum(v)
        cvp = np.cumsum(vp)
        cvp2 = np.cumsum(vp2)
        with np.errstate(divide="ignore", invalid="ignore"):
            vwap = np.where(cv > 0, cvp / cv, np.nan)
            var = np.where(cv > 0, cvp2 / cv - vwap * vwap, np.nan)
        sd = np.sqrt(np.maximum(var, 0.0))
        vwap_v = vwap[s.vt]
        sd_v = sd[s.vt]
        for b in VWAP_BANDS:
            out.append(Level("VWAP|%s|%+g" % (nm, b), "VWAP", float("nan"),
                             lo, series=vwap_v + b * sd_v, dynamic=True))
    return out


# ======================================================= the state machine ===
def touch_scan(dist, phase_v, active_from, tol):
    """§4 arm/touch state machine.  Returns (touch_positions, first_near_pos).

    dist        |mid - L| at every OBSERVED (two-sided) second, price units
    phase_v     phase tag at those same seconds
    active_from index of the level's creation second in that array
    """
    n = dist.size
    if n == 0 or active_from >= n:
        return np.zeros(0, dtype=np.int64), -1
    near = np.isfinite(dist) & (dist <= tol)
    far = np.isfinite(dist) & (dist > ARM_DISTANCE_MULT * tol)
    idx = np.arange(n, dtype=np.int64)
    near[:active_from] = False
    far[:active_from] = False
    runlen = M.run_lengths(far)
    armable = runlen >= ARM_SECONDS
    if n > 1:
        pc = np.empty(n, dtype=bool)
        pc[0] = False
        pc[1:] = phase_v[1:] != phase_v[:-1]
        pc[:active_from] = False
        armable = armable | pc
    arm_pos = idx[armable]
    near_pos = idx[near]
    first_near = int(near_pos[0]) if near_pos.size else -1
    touches = []
    cur = active_from
    while True:
        ai = int(np.searchsorted(arm_pos, cur, side="left"))
        if ai >= arm_pos.size:
            break
        a = int(arm_pos[ai])
        ni = int(np.searchsorted(near_pos, a, side="left"))
        if ni >= near_pos.size:
            break
        t = int(near_pos[ni])
        touches.append(t)
        cur = t + 1
    return np.array(touches, dtype=np.int64), first_near


def classify_touch(diff, secs, ti, app, tol, reject_move):
    """Resolve one touch.  `diff` = (mid - L) at observed seconds, `app` = the
    approach side (+1 approached from above, -1 from below).

    Returns (outcome, outcome_sec, reject_sec, break_sec, reclaim_sec).
    """
    t_sec = int(secs[ti])
    hi = int(np.searchsorted(secs, t_sec + REJECT_WINDOW, side="right"))
    win = slice(ti + 1, hi)
    reject_sec = break_sec = reclaim_sec = -1
    w = diff[win] * app
    ws = secs[win]
    if w.size:
        r = np.nonzero(w >= reject_move)[0]
        if r.size:
            reject_sec = int(ws[int(r[0])])
        beyond = w < -tol
        rl = M.run_lengths(beyond)
        b = np.nonzero(rl >= BREAK_HOLD)[0]
        if b.size:
            break_sec = int(ws[int(b[0])])
    if break_sec >= 0:
        j = int(np.searchsorted(secs, break_sec, side="left"))
        back = diff[j + 1:] * app >= -tol
        rl2 = M.run_lengths(back)
        c = np.nonzero(rl2 >= RECLAIM_HOLD)[0]
        if c.size:
            reclaim_sec = int(secs[j + 1 + int(c[0])])
    cands = []
    if reject_sec >= 0:
        cands.append((reject_sec, OUTCOME_REJECT))
    if break_sec >= 0:
        cands.append((break_sec, OUTCOME_BREAK))
    if not cands:
        return OUTCOME_NONE, -1, reject_sec, break_sec, reclaim_sec
    cands.sort()
    return cands[0][1], cands[0][0], reject_sec, break_sec, reclaim_sec


# ================================================================= driver ====
LEVEL_COLS = ("level_id", "family", "price", "created_d8", "dynamic")
TOUCH_COLS = ("touch_sec", "level_row", "level_price", "mid", "approach_side",
              "outcome", "outcome_sec", "reject_sec", "break_sec",
              "reclaim_sec", "virgin_at_touch", "touch_index")


def _shard(args):
    asset, sess, hist, fc = args
    spec = C.ASSETS[asset]
    mult, tick_usd, tick_px = spec["mult"], spec["tick_usd"], spec["tick_px"]
    bars = X.load_bars(asset, M.M0_ROOT)
    dates = sorted(hist)
    # The ledger registry is the cross-session memory of §4: a level object is
    # (level_key, price-on-the-tick-grid) and it keeps its creation date, touch
    # count, virginity and last test as long as the source keeps producing that
    # price.  Dynamic levels (VWAP, developing POC) are born at their scope
    # start, so their identity carries the session date.
    reg = {}
    stat_rows = []
    fam_rows = {}
    for trade_date, path in sess:
        bar = bars.get(trade_date)
        atr = bar["ATR14_prev_usd"] if bar else float("nan")
        if trade_date not in hist:
            continue        # stale-book receipt: not a session (see §defects)
        s = X.load_session(asset, trade_date, path)
        if s.vt.size < 2 or not np.isfinite(atr):
            continue
        tol = max(TOL_TICKS * tick_usd, TOL_ATR_FRAC * atr) / mult
        reject_move = max(REJECT_ATR_FRAC * atr, REJECT_TICKS * tick_usd) / mult
        i = dates.index(trade_date)
        prev = dates[i - 1] if i >= 1 else None
        prof_prev = B4.load_profile(asset, prev) if prev else None
        prof_cur = B4.load_profile(asset, trade_date)
        levels = build_levels(asset, s, trade_date, hist, fc, prof_prev,
                              prof_cur, atr)
        d8 = M.d8(trade_date)
        vm = s.vm
        vt = s.vt
        phase_v = s.phase_tag[vt]

        kept = []
        lv_id, lv_fam, lv_px, lv_cd, lv_dyn = [], [], [], [], []
        lv_virgin, lv_tc, lv_lts, lv_lto = [], [], [], []
        lv_first_near = []
        per_level_touch_secs = []
        touches = []
        for L in levels:
            if L.dynamic:
                series = L.series
                diff = vm - series
            else:
                if not np.isfinite(L.price):
                    continue
                series = None
                diff = vm - L.price
            dist = np.abs(diff)
            af = int(np.searchsorted(vt, L.active_from, side="left"))
            if af >= vt.size:
                continue
            rk = ((L.key, "DYN", d8) if L.dynamic
                  else (L.key, round(float(L.price) / tick_px)))
            st = reg.get(rk)
            if st is None:
                st = {"created": d8, "tc": 0, "virgin": True, "lts": -1,
                      "lto": OUTCOME_NONE}
                reg[rk] = st
            virgin_at_open = bool(st["virgin"])
            tc_at_open = int(st["tc"])
            tp, first_near = touch_scan(dist, phase_v, af, tol)
            if first_near >= 0 and st["virgin"]:
                st["virgin"] = False
            row = len(lv_id)
            kept.append(L)
            lv_id.append(L.key)
            lv_fam.append(L.family)
            lv_px.append(float(L.price) if not L.dynamic
                         else float(series[af]))
            lv_cd.append(st["created"])
            lv_dyn.append(1 if L.dynamic else 0)
            lv_first_near.append(int(vt[first_near]) if first_near >= 0 else -1)

            outside = np.isfinite(dist) & (dist > tol)
            idx = np.arange(dist.size, dtype=np.int64)
            last_outside = np.maximum.accumulate(np.where(outside, idx, -1))
            tsecs = []
            for ti in tp.tolist():
                jj = int(last_outside[ti - 1]) if ti > 0 else -1
                if jj < af:
                    continue
                app = 1 if diff[jj] > 0 else -1
                oc, osec, rs_, bs_, cs_ = classify_touch(diff, vt, ti, app,
                                                         tol, reject_move)
                st["tc"] += 1
                st["lts"] = int(vt[ti])
                st["lto"] = oc
                lpx = float(series[ti]) if L.dynamic else float(L.price)
                touches.append([int(vt[ti]), row, lpx, float(vm[ti]), app, oc,
                                osec, rs_, bs_, cs_,
                                1 if st["tc"] == 1 else 0, st["tc"]])
                tsecs.append(int(vt[ti]))
                key = (L.family, OUTCOME_NAMES[oc])
                fam_rows[key] = fam_rows.get(key, 0) + 1
            per_level_touch_secs.append((virgin_at_open, tc_at_open, tsecs))
            lv_virgin.append(1 if st["virgin"] else 0)
            lv_tc.append(int(st["tc"]))
            lv_lts.append(int(st["lts"]))
            lv_lto.append(int(st["lto"]))

        # ---------------- snapshots at the session open and every phase open,
        # each carrying the level state AS OF that second (causal, §4).
        snap_secs = [0]
        pc = np.nonzero(s.phase_tag[1:] != s.phase_tag[:-1])[0] + 1
        snap_secs.extend(int(x) for x in pc.tolist())
        snap_sec, snap_row, snap_price, snap_dist = [], [], [], []
        snap_virgin, snap_tc, snap_lts, snap_lto = [], [], [], []
        for sec in snap_secs:
            j = int(np.searchsorted(vt, sec, side="left"))
            if j >= vt.size:
                continue
            m_ = float(vm[j])
            for row, L in enumerate(kept):
                if L.active_from > sec:
                    continue
                p_ = (float(L.series[j]) if L.dynamic else float(L.price))
                if not np.isfinite(p_):
                    continue
                v0, tc0, tsecs = per_level_touch_secs[row]
                done = [t for t in tsecs if t <= sec]
                fn = lv_first_near[row]
                snap_sec.append(sec)
                snap_row.append(row)
                snap_price.append(p_)
                snap_dist.append((p_ - m_) * mult)
                snap_virgin.append(1 if (v0 and (fn < 0 or fn > sec)) else 0)
                snap_tc.append(tc0 + len(done))
                snap_lts.append(done[-1] if done else -1)
                snap_lto.append(int(touches[0][5]) if False else
                                _outcome_at(touches, row, done))

        C.savez_det(M.out_path("levels", asset,
                               "%s.npz" % trade_date.strftime("%Y%m%d")),
                    level_id=np.array(lv_id, dtype="<U40"),
                    level_family=np.array(lv_fam, dtype="<U16"),
                    level_price=np.array(lv_px, dtype=np.float64),
                    created_d8=np.array(lv_cd, dtype=np.int32),
                    dynamic=np.array(lv_dyn, dtype=np.int8),
                    virgin=np.array(lv_virgin, dtype=np.int8),
                    touch_count=np.array(lv_tc, dtype=np.int32),
                    last_test_sec=np.array(lv_lts, dtype=np.int32),
                    last_test_outcome=np.array(lv_lto, dtype=np.int8),
                    first_near_sec=np.array(lv_first_near, dtype=np.int32),
                    touches=np.array(touches, dtype=np.float64)
                    if touches else np.zeros((0, len(TOUCH_COLS))),
                    snap_sec=np.array(snap_sec, dtype=np.int32),
                    snap_row=np.array(snap_row, dtype=np.int32),
                    snap_price=np.array(snap_price, dtype=np.float64),
                    snap_dist_usd=np.array(snap_dist, dtype=np.float64),
                    snap_virgin=np.array(snap_virgin, dtype=np.int8),
                    snap_touch_count=np.array(snap_tc, dtype=np.int32),
                    snap_last_test_sec=np.array(snap_lts, dtype=np.int32),
                    snap_last_test_outcome=np.array(snap_lto, dtype=np.int8),
                    tol_px=np.float64(tol),
                    reject_move_px=np.float64(reject_move),
                    atr14_usd=np.float64(atr))
        nv = int(np.sum(np.array(lv_virgin, dtype=np.int8))) if lv_virgin else 0
        stat_rows.append([asset, trade_date.isoformat(), trade_date.year,
                          len(lv_id), nv, len(touches), len(snap_sec),
                          tol * mult, reject_move * mult, atr])
    return asset, stat_rows, fam_rows


def _outcome_at(touches, row, done):
    """last_test_outcome of level `row` as of the last touch in `done`."""
    if not done:
        return OUTCOME_NONE
    last = done[-1]
    for t in reversed(touches):
        if int(t[1]) == row and int(t[0]) == last:
            return int(t[5])
    return OUTCOME_NONE


def run(assets, workers, months=None):
    """One task per ASSET: the ledger's cross-session memory (creation dates,
    virginity, touch counts) makes the session loop inherently sequential, so
    the parallelism is across assets (<= 3 workers, well inside the lane cap)."""
    stat_rows, fam_counts = [], {}
    tasks = []
    for asset in assets:
        hist = load_v1_history(asset)
        fc = load_forecasts(asset)
        sess = [(d, p) for d, p in X.session_paths(asset, M.M0_ROOT)
                if not months or X.month_key(d) in months]
        tasks.append((asset, sess, hist, fc))
    M.hb("b3 levels: %d asset tasks (%d sessions)"
         % (len(tasks), sum(len(t[1]) for t in tasks)))
    if workers <= 1 or len(tasks) <= 1:
        res = [_shard(t) for t in tasks]
    else:
        with mp.Pool(min(workers, len(tasks))) as pool:
            res = list(pool.map(_shard, tasks, chunksize=1))
    for (asset, sr, fr) in res:
        stat_rows.extend(sr)
        for k, v in fr.items():
            fam_counts[(asset,) + k] = fam_counts.get((asset,) + k, 0) + v
    stat_rows.sort(key=lambda r: (r[0], r[1]))
    phash = C.params_hash(PARAMS)
    M.write_tsv(M.out_path("levels", "ledger_build.tsv"), SECTION, phash,
                ["asset", "trade_date", "year", "n_levels", "n_virgin",
                 "n_touches", "n_snapshot_rows", "tol_usd", "reject_move_usd",
                 "atr14_prev_usd"], stat_rows,
                extra=["per-session ledger build statistics; arrays in "
                       "m1/levels/{ASSET}/{YYYYMMDD}.npz"])
    fr = [[k[0], k[1], k[2], v] for k, v in sorted(fam_counts.items())]
    M.write_tsv(M.out_path("levels", "ledger_family_outcomes.tsv"), SECTION,
                phash, ["asset", "family", "outcome", "n_touches"], fr,
                extra=["touch outcomes per level family (§4 last_test_outcome)"])
    M.hb("b3 levels: %d session rows" % len(stat_rows))
    return stat_rows


def main():
    M.verify_spec()
    workers = int(os.environ.get("M1_WORKERS", "6"))
    assets = [a for a in sys.argv[1:] if a in M.ASSET_ORDER] or list(M.ASSET_ORDER)
    run(assets, workers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
