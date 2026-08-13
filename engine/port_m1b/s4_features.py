#!/usr/bin/python3
"""PORT M1.B S4 — the PINNED PROBE FEATURES (identical for every label).

Spec §1 S4: "PINNED PROBE FEATURES (~24 ...): rung/family one-hots, phase,
clock-norm activity z, spread_at_decision, ATR14, RV_5/RV_66 ratio,
distance-to-nearest-kept-level ladder (6), virgin flag, VWAP z, prior-leg
travel, confirmation speed, dominance share, day-of-week".

Every feature is CAUSAL at the decision second and every one is computed on the
D-054 MID-SANE view of the session (the same view the roster and the skeleton
were built on).  This is a STANDALONE PASS: it writes m1/atlas/features_*.npz
and the screen only ever reads that file, so the label/screen process never
imports the oracle-leg machinery and the F-PROX bar stays structural.

Sources, no reimplementation:
  roster            rung/family masks, phase, spread, ATR14, dominance, date
  b1_decay          the zigzag scan -> pivot second and prior-leg travel
  b3_levels         the causal VWAP series (b3's own function)
  m1/levels_v3      the D-053+D-054 level ledger: kept-family level prices and
                    the causal virgin flag (first_near_sec vs the decision)
  m1/fvol           RV_5/RV_66 (fvol_forecasts, SESSION segment)
  session trades    60s trade-rate, robust-z'd against the trailing-60-session
                    same-half-hour reference (the m1 clock-norm convention)

Run: lab/run.sh port-m1b-s4-features -- /usr/bin/python3 engine/port_m1b/s4_features.py
"""
import datetime as dt
import multiprocessing as mp
import os
import sys
from collections import deque

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, "/workspace/engine/port_m0", "/workspace/engine/port_m1"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import s4_common as S                # noqa: E402
import common as C                   # noqa: E402
import census_common as X            # noqa: E402
import c_a_cost as CA                # noqa: E402
import c_c_roster as CC              # noqa: E402
import m1_common as M                # noqa: E402
import b1_decay as B1                # noqa: E402
import b3_levels as B3               # noqa: E402
import b7_sane as B7                 # noqa: E402

SECTION = "S4 pinned probe features"
# S1.1: the enriched arm reads the OR_EXT ledger and carries OR_EXT in the
# distance-to-nearest-kept-level ladder.  Unset environment = the v2 probe set.
LEVELS_DIR = os.environ.get("S4_LEVELS_DIR", "levels_v3")
KEPT = ("FVOL_LADDER", "FVOL_BAND", "NDAY", "PRIOR_DAY", "PHASE_HL", "VWAP")
if os.environ.get("S4_FAMILY_SET") == "v3":
    KEPT = KEPT + ("OR_EXT",)
RUNGS_V2 = (0.05, 0.075, 0.11, 0.15)
HALFHOUR = 1800
RATE_WINDOW = 60
TRAILING_SESSIONS = 60
MAD_SCALE = 1.4826
RATE_FLOOR = 0.5

S1_FAMILIES = ("G1", "G1_FINE", "G1_FAST_OPEN", "G2_REJECT", "G2_RECLAIM")
if os.environ.get("S4_FAMILY_SET") == "v3":
    # S1.2: the four adopted discovery families get their own one-hots, else a
    # NEWS_WINDOW-only candidate would be indistinguishable from an untagged one
    S1_FAMILIES = S1_FAMILIES + ("NEWS_WINDOW", "MICRO_OPEN", "POST_SHOCK",
                                 "FIRST_TEST")

FEATURE_NAMES = (
    tuple("rung_%g" % r for r in RUNGS_V2)
    + tuple("fam_" + f for f in S1_FAMILIES)
    + ("phase_dec", "activity_z", "spread_at_decision", "atr14_usd",
       "rv5_over_rv66")
    + tuple("dist_" + f for f in KEPT)
    + ("virgin_near", "vwap_z", "prior_leg_travel_usd", "confirm_speed_secs",
       "dom_share", "day_of_week"))


def _hist_add(h, vals):
    v, c = np.unique(vals, return_counts=True)
    for a, b in zip(v.tolist(), c.tolist()):
        h[a] = h.get(a, 0) + b


def _hist_median(h):
    if not h:
        return float("nan")
    keys = sorted(h)
    counts = np.array([h[k] for k in keys], dtype=np.int64)
    n = int(counts.sum())
    cum = np.cumsum(counts)
    pos = (n - 1) / 2.0
    lo = keys[int(np.searchsorted(cum, int(np.floor(pos)), side="right"))]
    hi = keys[int(np.searchsorted(cum, int(np.ceil(pos)), side="right"))]
    return float(lo + (hi - lo) * (pos - np.floor(pos)))


def _hist_mad(h, med):
    d = {}
    for k, c in h.items():
        a = abs(k - med)
        d[a] = d.get(a, 0) + c
    return _hist_median(d)


def _merge(dq):
    out = {}
    for hh in dq:
        for b, h in hh.items():
            t = out.setdefault(b, {})
            for k, v in h.items():
                t[k] = t.get(k, 0) + v
    return out


def rate_series(asset, s):
    """60s rolling trade count over session seconds (D-054 view irrelevant:
    trades are events, not quotes)."""
    z = np.load(s.path, allow_pickle=False)
    tsec = z["trades_sec"].astype(np.int64)
    z.close()
    cnt = np.zeros(s.n, dtype=np.int64)
    good = (tsec >= 0) & (tsec < s.n)
    if good.any():
        np.add.at(cnt, tsec[good], 1)
    return np.convolve(cnt, np.ones(RATE_WINDOW, dtype=np.int64))[:s.n]


def load_rv(asset):
    """{(trade_date): rv5_over_rv66} from the SESSION-segment fvol forecasts."""
    out = {}
    cols = None
    with open(M.out_path("fvol", "fvol_forecasts.tsv")) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            r = dict(zip(cols, f))
            if r["asset"] != asset or r["segment"] != "SESSION":
                continue
            v = r.get("rv5_over_rv66", "")
            out[dt.date.fromisoformat(r["trade_date"])] = \
                float(v) if v not in ("", None) else float("nan")
    return out


def load_sigma(asset):
    out = {}
    cols = None
    with open(M.out_path("fvol", "fvol_forecasts.tsv")) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            r = dict(zip(cols, f))
            if r["asset"] != asset or r["segment"] != "SESSION":
                continue
            v = r.get("sigma_hat_usd", "")
            out[dt.date.fromisoformat(r["trade_date"])] = \
                float(v) if v not in ("", None) else float("nan")
    return out


def load_ledger(asset, trade_date):
    """Per-session kept-family level table, loaded ONCE: for each static kept
    family, prices sorted ascending with their first-approach seconds."""
    p = M.out_path(LEVELS_DIR, asset, "%s.npz" % trade_date.strftime("%Y%m%d"))
    if not os.path.exists(p):
        return {}
    z = np.load(p, allow_pickle=False)
    fam = z["level_family"]
    px = z["level_price"]
    first_near = z["first_near_sec"]
    ids = z["level_id"]
    z.close()
    out = {}
    for f in KEPT:
        if f == "VWAP":
            continue
        sel = (fam == f) & np.isfinite(px)
        if not sel.any():
            continue
        if f == "OR_EXT":
            # SEGMENT SCOPE (CC-M1-6.1): an OR_EXT level exists only inside its
            # own phase, so the distance feature must not measure a TOKYO
            # extension from a NEW YORK decision.  The segment is the second
            # field of the level id.
            for ph, nm in enumerate(X.PHASE_NAMES):
                s2 = sel & np.array([str(v).split("|")[1:2] == [nm]
                                     for v in ids], dtype=bool)
                if not s2.any():
                    continue
                pp = px[s2]
                fn = first_near[s2].astype(np.int64)
                o = np.argsort(pp, kind="stable")
                out[("OR_EXT", ph)] = (pp[o], fn[o])
            continue
        pp = px[sel]
        fn = first_near[sel].astype(np.int64)
        o = np.argsort(pp, kind="stable")
        out[f] = (pp[o], fn[o])
    return out


def level_distances(ledger, mid, dec_sec, mult, vwap_line, phase=-1):
    """(6 $-distances to the nearest kept-family level, causal virgin flag).

    Static kept families come from the D-053+D-054 ledger; VWAP comes from the
    causal series recomputed here (the ledger stores only its creation-second
    price).  A level is VIRGIN at `dec_sec` when the ledger's first
    within-tolerance approach is absent or later.
    """
    dist = np.full(len(KEPT), np.nan)
    best_d, best_v = np.inf, np.nan
    for i, f in enumerate(KEPT):
        if f == "VWAP":
            if np.isfinite(vwap_line):
                dist[i] = abs(mid - vwap_line) * mult
            continue
        e = ledger.get(("OR_EXT", int(phase)) if f == "OR_EXT" else f)
        if e is None:
            continue
        pp, fn = e
        j = int(np.searchsorted(pp, mid))
        cands = [k for k in (j - 1, j) if 0 <= k < pp.size]
        if not cands:
            continue
        k = min(cands, key=lambda k: abs(pp[k] - mid))
        d = abs(float(pp[k]) - mid) * mult
        dist[i] = d
        if d < best_d:
            best_d = d
            best_v = 1.0 if (fn[k] < 0 or fn[k] > dec_sec) else 0.0
    return dist, best_v


def _asset(args):
    asset, years = args
    spec = C.ASSETS[asset]
    mult = spec["mult"]
    roster = S.load_roster(asset)
    _side, cand = S.load_candidates(asset)
    cid = cand["cand_id"].astype(np.int64)
    d8_all = roster["date8"][cid]
    yr = (d8_all // 10000).astype(np.int64)
    keep = np.isin(yr, np.array(years, dtype=np.int64))
    rows = np.nonzero(keep)[0]
    n = rows.size
    F = np.full((n, len(FEATURE_NAMES)), np.nan, dtype=np.float32)
    idx_of = {}
    for i, r in enumerate(rows.tolist()):
        idx_of.setdefault(int(d8_all[r]), []).append((i, r))

    phase_med = CA.phase_median_spreads(M.M0_ROOT)
    bars = X.load_bars(asset, M.M0_ROOT)
    rv = load_rv(asset)
    sane = B7.load_thresholds(asset)
    dq = deque(maxlen=TRAILING_SESSIONS)
    fi = {nm: i for i, nm in enumerate(FEATURE_NAMES)}

    for trade_date, path in X.session_paths(asset, M.M0_ROOT):
        d8 = M.d8(trade_date)
        want = idx_of.get(d8)
        s = X.load_session(asset, trade_date, path)
        thr = sane.get(d8)
        B7.apply(s, thr if thr is not None else [B7.SANE_CAP_USD] * X.N_PHASES)
        rate = rate_series(asset, s)
        o = int(s.meta["open_utc"])
        binid = ((o + np.arange(s.n, dtype=np.int64)) % 86400) // HALFHOUR
        if want:
            ref = _merge(dq)
            bar = bars.get(trade_date)
            atr = bar["ATR14_prev_usd"] if bar else float("nan")
            confs = {}
            if np.isfinite(atr) and s.vt.size >= 2:
                confs = _pivots(s, asset, atr, phase_med, trade_date, mult)
            vwap_line, vwap_sd = _vwap(asset, s)
            ledger = load_ledger(asset, trade_date)
            rvv = rv.get(trade_date, float("nan"))
            dow = float(trade_date.weekday())
            for (i, r) in want:
                dec = int(roster["dec_sec"][cid[r]])
                mid = float(roster["entry_mid"][cid[r]])
                rm = int(roster["rung_mask"][cid[r]])
                fm = int(roster["fam_mask"][cid[r]])
                for b in range(len(RUNGS_V2)):
                    F[i, fi["rung_%g" % RUNGS_V2[b]]] = 1.0 if (rm >> b) & 1 \
                        else 0.0
                for b, f in enumerate(S1_FAMILIES):
                    F[i, fi["fam_" + f]] = 1.0 if (fm >> b) & 1 else 0.0
                F[i, fi["phase_dec"]] = float(roster["phase_dec"][cid[r]])
                F[i, fi["spread_at_decision"]] = \
                    float(roster["spread_at_decision"][cid[r]])
                F[i, fi["atr14_usd"]] = float(roster["atr14_usd"][cid[r]])
                F[i, fi["rv5_over_rv66"]] = rvv
                F[i, fi["dom_share"]] = float(roster["dom_share"][cid[r]])
                F[i, fi["day_of_week"]] = dow
                if 0 <= dec < s.n:
                    b_ = int(binid[dec])
                    h = ref.get(b_)
                    if h:
                        med = _hist_median(h)
                        sc = max(MAD_SCALE * _hist_mad(h, med), RATE_FLOOR)
                        F[i, fi["activity_z"]] = (rate[dec] - med) / sc
                    vl = vwap_line[dec] if dec < vwap_line.size else np.nan
                    vs = vwap_sd[dec] if dec < vwap_sd.size else np.nan
                    if np.isfinite(vl) and np.isfinite(vs) and vs > 0:
                        F[i, fi["vwap_z"]] = (mid - vl) / vs
                    d, vg = level_distances(
                        ledger, mid, dec, mult, vl,
                        int(roster["phase_dec"][cid[r]]))
                    a = float(roster["atr14_usd"][cid[r]])
                    for b2, f2 in enumerate(KEPT):
                        F[i, fi["dist_" + f2]] = (d[b2] / a) if (a > 0) else \
                            np.nan
                    F[i, fi["virgin_near"]] = vg
                cinfo = confs.get((int(roster["conf_sec"][cid[r]]),
                                   int(roster["side"][cid[r]])))
                if cinfo is not None:
                    F[i, fi["confirm_speed_secs"]] = float(cinfo[0])
                    F[i, fi["prior_leg_travel_usd"]] = float(cinfo[1])
        # trailing clock-norm reference gets THIS session only after use
        hh = {}
        for b in np.unique(binid).tolist():
            h = {}
            _hist_add(h, rate[binid == b])
            hh[int(b)] = h
        dq.append(hh)
    M.hb("s4 features %s: %d rows" % (asset, n))
    return asset, rows, F


def _pivots(s, asset, atr, phase_med, trade_date, mult):
    """{(conf_sec, side): (confirm_speed, prior_leg_travel_usd)}.

    The zigzag is m0's own scan (c_c_roster.zigzag_scan) over the S1 4-rung
    ladder; a confirmation reached by several rungs takes the FINEST rung's
    pivot (ladder order), which is the earliest extreme the roster could have
    been describing.
    """
    spec = C.ASSETS[asset]
    tick_px, tick_usd = spec["tick_px"], spec["tick_usd"]
    vt_l = s.vt.tolist()
    vm_l = s.vm.tolist()
    vphase = s.phase_tag[s.vt].tolist()
    out = {}
    for r in RUNGS_V2:
        per_phase = []
        for p in range(X.N_PHASES):
            pm = phase_med.get((asset, trade_date.year, X.PHASE_NAMES[p]),
                               float("nan"))
            fl = X.RUNG_FLOOR_SPREAD_MULT * pm if np.isfinite(pm) else 0.0
            usd = max(r * atr, X.RUNG_FLOOR_TICKS * tick_usd, fl)
            per_phase.append(X.round_half_up(usd / mult, tick_px))
        thr_l = [per_phase[p] for p in vphase]
        prev_px = None
        for (px, psec, csec, side) in CC.zigzag_scan(vt_l, vm_l, thr_l):
            k = (int(csec), int(side))
            if k not in out:
                travel = abs(px - prev_px) * mult if prev_px is not None \
                    else float("nan")
                out[k] = (int(csec) - int(psec), travel)
            prev_px = px
    return out


def _vwap(asset, s):
    """Causal session VWAP line and sigma over session seconds (b3's own)."""
    line = np.full(s.n, np.nan)
    sd = np.full(s.n, np.nan)
    for L in B3._vwap_levels(asset, s):
        if not L.key.startswith("VWAP|SESSION|"):
            continue
        band = L.key.rsplit("|", 1)[1]
        ser = np.full(s.n, np.nan)
        ser[s.vt] = L.series
        if band == "+0":
            line = ser
        elif band == "+2":
            sd = ser
    with np.errstate(invalid="ignore"):
        sigma = (sd - line) / 2.0
    return line, sigma


def main():
    S.verify_spec()
    workers = int(os.environ.get("M1_WORKERS", "3"))
    assets = [a for a in sys.argv[1:] if a in S.ASSETS] or list(S.ASSETS)
    tasks = [(a, S.FIT_YEARS) for a in assets]
    if len(tasks) <= 1:
        res = [_asset(t) for t in tasks]
    else:
        with mp.Pool(min(workers, len(tasks))) as pool:
            res = list(pool.map(_asset, tasks, chunksize=1))
    for (asset, rows, F) in res:
        C.savez_det(S.out_path("features_%s.npz" % asset),
                    rows=rows.astype(np.int64), features=F,
                    names=np.array(FEATURE_NAMES, dtype="<U32"))
        M.hb("s4 features %s: %s" % (asset, F.shape))
    return 0


if __name__ == "__main__":
    sys.exit(main())
