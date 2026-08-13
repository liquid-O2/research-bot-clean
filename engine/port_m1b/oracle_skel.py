#!/usr/bin/python3
"""PORT M1.B S3 — the INDEPENDENT brute-force label-skeleton oracle.

Written from design/PORT_M1B_S3_CONV.md ALONE.  It shares no code, no
constants file and no data path with engine/cpp/qr_skel:

  * different language, different expressions;
  * FIRST PASSAGE is a DIRECT per-rung scan of f (`argmax(f >= rung)`), never a
    prefix-maximum plus a binary search — the kernel under test is not reused
    to check itself;
  * the session tape comes from the m0 PYTHON receipts
    (artifacts/cache/port/m0/sessions/{ASSET}/{date}.npz) while the engine reads
    the C++ QRSESS1 receipts, so the two agree only if BOTH the substrate and
    the label arithmetic agree.

O(n) per query is deliberate here.  This file is never in the production path.
"""
import json
import os

import numpy as np

# --- CONV C5 geometry, transcribed from PORT_M0_CENSUS_SPEC §1 --------------
GEOM = {"SI": {"mult": 5000, "tick_px": 0.005},
        "HG": {"mult": 25000, "tick_px": 0.0005},
        "NKD": {"mult": 5, "tick_px": 5.0}}
RUNG_COUNT = 200
RUNG_STEP = 0.02
HORIZON_SECS = (1800, 3600, 7200)
ANCHOR_DELAYS = (0, 60)
ST_TWO_SIDED = 0
M0_SESSIONS = "/workspace/artifacts/cache/port/m0/sessions"
SANE_TSV = "/workspace/artifacts/cache/port/m1/sane/sane_thresholds.tsv"
PHASES = ("TOKYO", "LONDON", "NY")

_SANE = {}


def sane_thresholds(asset):
    """{date8: [thr_TOKYO, thr_LONDON, thr_NY]} (CC-M1-4 / D-054, CC-M1-5 D15).

    Read from b7_sane.py's own TSV, which is the single definition of the mask;
    the oracle does not recompute the trailing median any more than the engine
    does. Absent => the mask is off for that run."""
    if asset in _SANE:
        return _SANE[asset]
    out = {}
    if os.path.exists(SANE_TSV):
        cols = None
        with open(SANE_TSV) as fh:
            for line in fh:
                if line.startswith("#"):
                    continue
                f = line.rstrip("\n").split("\t")
                if cols is None:
                    cols = f
                    continue
                r = dict(zip(cols, f))
                if r["asset"] != asset:
                    continue
                d8 = int(r["trade_date"].replace("-", ""))
                out.setdefault(d8, [float("nan")] * 3)[PHASES.index(r["phase"])] = \
                    float(r["threshold_usd"])
    _SANE[asset] = out
    return out

FLOAT_FIELDS = ("entry_mid", "f_h30", "f_h60", "f_h120", "f_phase_close",
                "f_sess_close", "mfe_usd", "mae_before_argmax_usd",
                "mae_unwalled_usd", "f_terminal_usd", "giveback_post_peak_usd",
                "uw_share", "monotonicity")
INT_FIELDS = ("anchor_sec", "observed_secs", "phase_close_sec", "sess_close_sec",
              "mfe_argmax_sec", "time_to_peak_secs", "time_underwater_secs",
              "mono_steps")


def ladder(asset, atr14_usd):
    """CONV C5.  Returns None when the ladder is degenerate (engine refuses)."""
    g = GEOM[asset]
    mult, tick = float(g["mult"]), g["tick_px"]
    if not np.isfinite(atr14_usd) or atr14_usd <= 0.0:
        return None
    out = np.empty(RUNG_COUNT, dtype=np.float64)
    for i in range(RUNG_COUNT):
        k = float(i + 1)
        px = np.floor((k * RUNG_STEP * atr14_usd / mult) / tick + 0.5) * tick
        if i == 0 and not px > 0.0:
            return None
        out[i] = px * mult
    return out


def load_session(asset, date8, masked=True):
    """CONV C1 (+ CC-M1-4 when `masked`), from the m0 Python receipt."""
    p = os.path.join(M0_SESSIONS, asset, "%08d.npz" % date8)
    z = np.load(p, allow_pickle=False)
    mid = z["g0_mid"]
    ph = z["phase_tag"]
    n = int(min(len(mid), len(ph)))
    s = {"n": n, "mid": mid[:n], "state": z["g0_state"][:n], "phase": ph[:n],
         "spread": z["g0_spread_usd"][:n],
         "meta": json.loads(str(z["meta_json"]))}
    z.close()
    sane = s["state"] == ST_TWO_SIDED
    if masked:
        thr = sane_thresholds(asset).get(int(date8))
        if thr is None:
            raise ValueError("no mid-sanity thresholds for %s %d" % (asset, date8))
        lim = np.asarray(thr, dtype=np.float64)[s["phase"]]
        sp = s["spread"]
        sane = sane & np.isfinite(sp) & (sp <= lim)
    s["sane"] = sane
    vsec = np.nonzero(sane)[0].astype(np.int64)
    s["vt"] = vsec
    s["vm"] = s["mid"][vsec]
    return s


def next_phase_boundary(s, sec):
    p = s["phase"][sec]
    tail = s["phase"][sec + 1:]
    w = np.nonzero(tail != p)[0]
    return int(sec + 1 + w[0]) if w.size else s["n"] - 1


def _empty_anchor(anchor_sec):
    """CONV C3 UNAVAILABLE fill."""
    a = {k: np.nan for k in FLOAT_FIELDS}
    a.update({k: -1 for k in INT_FIELDS})
    a["anchor_sec"] = int(anchor_sec)
    a["observed_secs"] = 0
    a["tau_up"] = np.full(RUNG_COUNT, -1, dtype=np.int32)
    a["tau_dn"] = np.full(RUNG_COUNT, -1, dtype=np.int32)
    a["rec_f_t"] = np.zeros(0, dtype=np.int32)
    a["rec_f_v"] = np.zeros(0, dtype=np.float32)
    a["rec_a_t"] = np.zeros(0, dtype=np.int32)
    a["rec_a_v"] = np.zeros(0, dtype=np.float32)
    return a


def anchor_skeleton(s, asset, side, anchor_sec, rungs):
    n = s["n"]
    if not (0 <= anchor_sec < n) or not s["sane"][anchor_sec]:
        return _empty_anchor(anchor_sec)
    mult = float(GEOM[asset]["mult"])
    entry = float(s["mid"][anchor_sec])
    vt = s["vt"]
    j0 = int(np.searchsorted(vt, anchor_sec, side="left"))
    t = vt[j0:]
    # CONV C4, including the negative-zero normalization.
    f = (s["vm"][j0:] - entry) * int(side) * mult + 0.0
    # The ADVERSE series is the negation, which re-creates -0.0 wherever f is
    # zero; CONV C4's normalization applies to it too, or the adverse landmarks
    # come back sign-flipped-zero and byte comparison is undefined.
    negf = -f + 0.0
    m = f.size

    a = {"anchor_sec": int(anchor_sec), "observed_secs": int(m),
         "entry_mid": entry}

    # ---- FIRST PASSAGE: a direct scan per rung, no prefix maxima -----------
    tau_up = np.full(RUNG_COUNT, -1, dtype=np.int32)
    tau_dn = np.full(RUNG_COUNT, -1, dtype=np.int32)
    for k in range(RUNG_COUNT):
        x = rungs[k]
        hit = f >= x
        if hit.any():
            tau_up[k] = t[int(np.argmax(hit))]
        hit = negf >= x
        if hit.any():
            tau_dn[k] = t[int(np.argmax(hit))]
    a["tau_up"] = tau_up
    a["tau_dn"] = tau_dn

    # ---- landmarks (CONV C8) ------------------------------------------------
    mfe = float(f.max())
    argmax_i = int(np.argmax(f))          # first attainment
    a["mfe_usd"] = mfe
    a["mfe_argmax_sec"] = int(t[argmax_i])
    a["time_to_peak_secs"] = int(t[argmax_i]) - int(anchor_sec)
    a["mae_before_argmax_usd"] = float(negf[:argmax_i + 1].max())
    a["mae_unwalled_usd"] = float(negf.max())
    a["f_terminal_usd"] = float(f[-1])
    a["giveback_post_peak_usd"] = (float(mfe - f[argmax_i + 1:].min())
                                   if argmax_i + 1 < m else 0.0)
    uw = int((f < 0.0).sum())
    a["time_underwater_secs"] = uw
    a["uw_share"] = float(uw) / float(m)

    # ---- prefix-maxima record sequences (CONV C7) --------------------------
    # A record at i >= 1 is f[i] > max(f[0..i-1]); its stored value IS f[i].
    prior_f = np.maximum.accumulate(f)[:-1]
    prior_a = np.maximum.accumulate(negf)[:-1]
    mask_f = np.zeros(m, dtype=bool)
    mask_a = np.zeros(m, dtype=bool)
    if m > 1:
        mask_f[1:] = f[1:] > prior_f
        mask_a[1:] = negf[1:] > prior_a
    a["rec_f_t"] = t[mask_f].astype(np.int32)
    a["rec_f_v"] = f[mask_f].astype(np.float32)
    a["rec_a_t"] = t[mask_a].astype(np.int32)
    a["rec_a_v"] = negf[mask_a].astype(np.float32)

    # ---- horizon marks (CONV C9) -------------------------------------------
    pc = next_phase_boundary(s, anchor_sec)
    scl = n - 1
    a["phase_close_sec"] = int(pc)
    a["sess_close_sec"] = int(scl)
    marks = [anchor_sec + HORIZON_SECS[0], anchor_sec + HORIZON_SECS[1],
             anchor_sec + HORIZON_SECS[2], pc, scl]
    names = ("f_h30", "f_h60", "f_h120", "f_phase_close", "f_sess_close")
    for name, mk in zip(names, marks):
        if mk >= n:
            a[name] = float("nan")
        else:
            j = int(np.searchsorted(t, mk, side="right")) - 1
            a[name] = float(f[j])

    # ---- monotonicity (CONV C8) --------------------------------------------
    steps = (int(t[-1]) - int(anchor_sec)) // 60
    a["mono_steps"] = int(steps)
    if steps <= 0:
        a["monotonicity"] = float("nan")
    else:
        mk = anchor_sec + 60 * np.arange(steps + 1, dtype=np.int64)
        j = np.searchsorted(t, mk, side="right") - 1
        g = f[j]
        a["monotonicity"] = float(int((g[1:] > g[:-1]).sum())) / float(steps)
    return a


def oracle_session(asset, date8, dec_sec, side, atr14_usd, masked=True):
    """Per-candidate list of ANCHOR_DELAYS-long anchor dicts; None = refused."""
    s = load_session(asset, date8, masked=masked)
    out = []
    for i in range(len(dec_sec)):
        rungs = ladder(asset, float(atr14_usd[i]))
        if rungs is None:
            out.append(None)
            continue
        out.append([anchor_skeleton(s, asset, int(side[i]),
                                    int(dec_sec[i]) + d, rungs)
                    for d in ANCHOR_DELAYS])
    return out
