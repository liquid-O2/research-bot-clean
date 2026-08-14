#!/usr/bin/python3
"""PORT M1.B — D-054 / CC-M1-4 MID-SANITY mask.

USER CATCH, verified on raw books: wide-but-TWO_SIDED books (NKD 2022-09-08
secs 0-9: 25,650 x 28,870 = a 3,220-point spread) put the mid thousands of
dollars away from any tradeable price, and the "$2-5k in 10-35s" legs were
those spreads collapsing, not price travelling.

RULE (D-054): a session second is MID-SANE iff
    TWO_SIDED  AND  spread_$ <= min(10 x trailing-phase-median spread_$, $500)
Insane seconds are TYPED-EXCLUDED (never interpolated) from every mid consumer:
oracle legs, offer range/best_leg, the ZigZag spine, candidate entry mids,
certificate forward paths, and level touches.

PINNED READING (reported): "trailing-phase-median spread_$" is built causally -
the EXACT pooled median of two-sided spreads over the same phase of the
TRAILING 60 SESSIONS (integer tick histograms, the repo's trailing-60-session
clock-norm convention, D-054 says "trailing").  It is strictly prior: session d
never sees its own spreads.  Sessions before the first prior session (and
phases with no trailing observation) fall back to the $500 cap alone, which is
what actually kills the pathological books; the warm-up count is reported.

This module OWNS the mask.  Consumers call load_thresholds(asset) once and
apply(session, thr) per session, which rewrites the session's valid-second view
in place so every downstream m0/m1 routine sees SANE seconds and nothing else.

Run: lab/run.sh port-m1b-s1-sane -- /usr/bin/python3 engine/port_m1/b7_sane.py
"""
import multiprocessing as mp
import os
import sys
from collections import deque

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m1_common as M
import common as C
import census_common as X

SECTION = "CC-M1-4 mid-sanity mask (D-054)"
OUT_DIR = "sane"

TRAILING_SESSIONS = 60
SANE_MULT = 10.0
SANE_CAP_USD = 500.0

PARAMS = {
    "spec_section": SECTION,
    "rule": "SANE iff TWO_SIDED and spread_$ <= min(%.0f x trailing-phase-"
            "median spread_$, $%.0f)" % (SANE_MULT, SANE_CAP_USD),
    "trailing": "exact pooled median of two-sided spreads over the same phase "
                "of the trailing %d sessions (integer tick histograms), "
                "strictly prior" % TRAILING_SESSIONS,
    "warmup": "no trailing observation -> the $%.0f cap alone" % SANE_CAP_USD,
    "exclusion": "typed-excluded, never interpolated",
}

COLUMNS = ["asset", "trade_date", "year", "phase", "n_trailing_sessions",
           "trailing_median_spread_usd", "threshold_usd", "n_two_sided",
           "n_sane", "n_insane", "insane_frac"]


# ------------------------------------------------------------- histograms ---
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


def _merge(dq):
    """Merge per-session {phase: {ticks: count}} maps into one pooled map."""
    out = {}
    for hh in dq:
        for p, h in hh.items():
            t = out.setdefault(p, {})
            for k, v in h.items():
                t[k] = t.get(k, 0) + v
    return out


# ------------------------------------------------------------------ core ----
def session_phase_hists(s, tick_usd):
    """{phase: {spread_in_ticks: count}} over this session's TWO_SIDED secs."""
    out = {}
    ts = s.state == C.ST_TWO_SIDED
    for p in range(X.N_PHASES):
        sel = ts & (s.phase_tag == p)
        h = {}
        if sel.any():
            v = np.rint(s.spread_usd[sel] / tick_usd).astype(np.int64)
            _hist_add(h, v[v >= 0])
        out[p] = h
    return out


def thresholds_from(ref, tick_usd):
    """{phase: (n_obs, trailing_median_$, threshold_$)} from a merged hist."""
    out = {}
    for p in range(X.N_PHASES):
        h = ref.get(p, {})
        med_ticks = _hist_median(h)
        if not np.isfinite(med_ticks):
            out[p] = (0, float("nan"), SANE_CAP_USD)
            continue
        med = med_ticks * tick_usd
        out[p] = (int(sum(h.values())), med,
                  float(min(SANE_MULT * med, SANE_CAP_USD)))
    return out


def sane_mask(s, thr_usd):
    """Boolean per session second.  thr_usd: array over phases ($)."""
    thr = np.asarray(thr_usd, dtype=np.float64)[s.phase_tag]
    sp = s.spread_usd
    return (s.state == C.ST_TWO_SIDED) & np.isfinite(sp) & (sp <= thr)


def apply(s, thr_usd):
    """Rewrite the session's observed-second view to the SANE seconds.

    Every m0/m1 consumer reads s.vt / s.vm / s.valid, so masking here masks the
    oracle, the ZigZag spine, the certificate paths and the level touches at
    once.  Returns insane_frac (of two-sided seconds)."""
    sane = sane_mask(s, thr_usd)
    n_ts = int((s.state == C.ST_TWO_SIDED).sum())
    # Session carries __slots__; `valid` IS the observed-second flag every
    # consumer reads, so the mask is installed there (no new attribute).
    s.valid = sane
    s.vt = np.nonzero(sane)[0].astype(np.int64)
    s.vm = s.mid[s.vt]
    return (1.0 - float(s.vt.size) / n_ts) if n_ts else float("nan")


# -------------------------------------------------------------- the pass ----
def _asset(args):
    asset, sess = args
    tick_usd = C.ASSETS[asset]["tick_usd"]
    dq = deque(maxlen=TRAILING_SESSIONS)
    rows = []
    for trade_date, path in sess:
        s = X.load_session(asset, trade_date, path)
        ref = _merge(dq)
        thr = thresholds_from(ref, tick_usd)
        thr_v = [thr[p][2] for p in range(X.N_PHASES)]
        sane = sane_mask(s, thr_v)
        ts = s.state == C.ST_TWO_SIDED
        for p in range(X.N_PHASES):
            ph = s.phase_tag == p
            n_ts = int((ts & ph).sum())
            n_sn = int((sane & ph).sum())
            rows.append([asset, trade_date.isoformat(), trade_date.year,
                         X.PHASE_NAMES[p], thr[p][0], thr[p][1], thr[p][2],
                         n_ts, n_sn, n_ts - n_sn,
                         (1.0 - n_sn / n_ts) if n_ts else float("nan")])
        dq.append(session_phase_hists(s, tick_usd))
    M.hb("sane %s: %d sessions" % (asset, len(sess)))
    return rows


class SaneThresholdRefusal(RuntimeError):
    """D-054 TYPED EXCLUSION applied to the threshold itself (R89).

    The pre-fix reader filled a missing (asset, session) with `[SANE_CAP_USD] *
    N_PHASES`, i.e. the $500 cap alone.  The committed table shows SI/HG
    thresholds run $125-$250 (the 10x clause binds), so that default is a mask
    2-4x TOO PERMISSIVE and it fired silently.  D-054's doctrine is typed
    exclusion, so a session the mask cannot be computed for is a REFUSAL that is
    named and counted, never a permissive default.
    """


def load_thresholds(asset):
    """{date8: [thr_$ per phase]} from the committed table.

    A session is present ONLY when the table carries all N_PHASES rows for it
    (R89): a partially written session is dropped from the map so that
    `thresholds_for` refuses on it rather than silently completing it with the
    cap.  Return type is unchanged for existing consumers.
    """
    path = M.out_path(OUT_DIR, "sane_thresholds.tsv")
    partial, cols = {}, None
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
            d = f[1]
            d8 = int(d[0:4]) * 10000 + int(d[5:7]) * 100 + int(d[8:10])
            partial.setdefault(d8, {})[X.PHASE_NAMES.index(f[3])] = float(f[6])
    return {d8: [m[p] for p in range(X.N_PHASES)]
            for d8, m in partial.items() if len(m) == X.N_PHASES}


def thresholds_for(thr_map, asset, d8):
    """The D-054 threshold vector for one session, or a REFUSAL (R89)."""
    v = thr_map.get(int(d8))
    if v is None:
        raise SaneThresholdRefusal(
            "D-054/R89: %s %08d has no complete sane_thresholds.tsv row; the "
            "$%.0f cap-only default is 2-4x too permissive and is refused"
            % (asset, int(d8), SANE_CAP_USD))
    return v


def apply_for(s, thr_map, asset, d8):
    """load_session -> D-054 SANE view, refusing (never defaulting) on a gap."""
    return apply(s, thresholds_for(thr_map, asset, d8))


def main():
    M.verify_spec_m1b()
    assets = [a for a in sys.argv[1:] if a in M.ASSET_ORDER] or \
        list(M.ASSET_ORDER)
    tasks = [(a, X.session_paths(a, M.M0_ROOT)) for a in assets]
    if len(tasks) <= 1:
        res = [_asset(t) for t in tasks]
    else:
        with mp.Pool(min(3, len(tasks))) as pool:
            res = list(pool.map(_asset, tasks, chunksize=1))
    rows = []
    for r in res:
        rows.extend(r)
    M.write_tsv(M.out_path(OUT_DIR, "sane_thresholds.tsv"), SECTION,
                C.params_hash(PARAMS), COLUMNS, rows, spec="PORT_M1B",
                extra=["threshold_usd = min(%.0f x trailing-phase-median "
                       "spread, $%.0f); warm-up phases fall back to the cap"
                       % (SANE_MULT, SANE_CAP_USD)])
    ins = [r[10] for r in rows if np.isfinite(r[10])]
    M.hb("sane: %d (session,phase) rows, pooled insane_frac mean %.5f"
         % (len(rows), M.mean(ins)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
