#!/usr/bin/python3
"""PORT M1.B S4 — atlas screen substrate: skeleton queries + roster join.

NO TAPE RE-READS. Every label value in S4 comes from the S3 skeleton shards
(`m1/skel/shards/{ASSET}_{YYYYMM}.{bin,json}`, QRSKEL1) plus the S1-v2 union
roster row the skeleton's `cand_id` indexes. This module owns:

  * the shard reader + the per-anchor QUERY KERNEL (prefix-max records +
    binary search, the LABEL_ATLAS_V2 §3.3 kernel boundary, vectorised);
  * the roster join (cand_id = row ordinal in m1/generation_v2/union_roster_*);
  * the FIT-era universe and the deterministic 25% candidate subsample;
  * the ranking units {phase, session, day} as first-class group keys.

SIGN-OF-ZERO (S3_CONV C4): the skeleton normalises `-0.0` to `+0.0` on every
emitted field; the m0-derived roster arrays do NOT. Comparisons here are
numeric (`==`, which calls them equal); no byte comparison is ever made
against a roster array. `sanity_marks()` measures the agreement and reports
the -0.0 cells separately.
"""
import hashlib
import json
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, "/workspace/engine/port_m0", "/workspace/engine/port_m1"):
    if _p not in sys.path:
        sys.path.insert(0, _p)
_PYLIBS = "/workspace/artifacts/cache/pylibs"
if _PYLIBS not in sys.path:
    sys.path.insert(0, _PYLIBS)

import binpack                       # noqa: E402  (S3 receipt reader)
import common as C                   # noqa: E402  (m0 substrate)
import census_common as X            # noqa: E402
import m1_common as M                # noqa: E402

SPEC_PATH = "/workspace/design/PORT_M1B_SPEC.md"
SPEC_SHA16 = "d31f48b59877e44d"
ATLAS_PATH = "/workspace/design/LABEL_ATLAS_V2.md"

M1_ROOT = M.M1_ROOT
# S1.1/S1.2 (atlas v3): the same machinery re-pointed at the ENRICHED roster and
# its own skeleton/candidate/output trees.  Defaults are the S1-v2 atlas run, so
# an unset environment reproduces the committed m1/atlas/ exactly.
SKEL_DIR = os.environ.get("QR_SKEL_SHARD_DIR",
                          os.path.join(M1_ROOT, "skel", "shards"))
CAND_DIR = os.environ.get("QR_SKEL_CANDIDATE_DIR",
                          os.path.join(M1_ROOT, "skel", "candidates"))
ROSTER_DIR = os.environ.get("QR_SKEL_ROSTER_DIR",
                            os.path.join(M1_ROOT, "generation_v2"))
OUT_DIR = os.environ.get("S4_OUT_DIR", "atlas")

ASSETS = ("SI", "HG", "NKD")
ANCHORS = ("a0", "a1")
RUNG_COUNT = 200
RUNG_STEP = 0.02                     # rung_k = k x 0.02 x ATR14($)

# S4 is FIT-era only (era law: 2025 = GATE, evaluate never fit; 2026 sealed).
FIT_YEARS = tuple(X.WALL_FIT_YEARS)
SUBSAMPLE = 0.25                     # spec: 25% candidate subsample
SUBSAMPLE_SALT = "port-m1b-s4-20260813"

MARKS = ("h30", "h60", "h120", "phase_close", "sess_close")
MARK_SECS = {"h30": 1800, "h60": 3600, "h120": 7200}


def verify_spec():
    got = C.sha256_file(SPEC_PATH)[:16]
    if got != SPEC_SHA16:
        raise RuntimeError("M1B spec sha16 %s != pinned %s" % (got, SPEC_SHA16))
    return got


def out_path(*parts):
    return M.out_path(OUT_DIR, *parts)


# ============================================================ shard reading ==
def shard_months(asset):
    out = []
    for n in sorted(os.listdir(SKEL_DIR)):
        if not (n.startswith(asset + "_") and n.endswith(".json")):
            continue
        stem = n[:-5]
        tail = stem.split("_", 1)[1]
        if len(tail) == 6 and tail.isdigit():      # skip *_run.receipt.json
            out.append(stem)
    return out


def read_shard(stem):
    side, arr = binpack.read(os.path.join(SKEL_DIR, stem), "QRSKEL1")
    return side, arr


def load_asset(asset, years=FIT_YEARS):
    """Concatenate the asset's shards for `years` into one dict of arrays.

    Ragged skeleton record arrays are re-based so that offsets stay valid
    after concatenation.  Returns (arrays, sidecars).
    """
    keep = {}
    sides = []
    parts = []
    for stem in shard_months(asset):
        y = int(stem.split("_")[1][:4])
        if years and y not in years:
            continue
        side, arr = read_shard(stem)
        sides.append(side)
        parts.append(arr)
    if not parts:
        raise RuntimeError("no shards for %s" % asset)
    names = list(parts[0].keys())
    ragged = [n for n in names if n.endswith(("skel_f_t", "skel_f_v",
                                              "skel_a_t", "skel_a_v"))]
    for n in names:
        if n in ragged:
            continue
        keep[n] = np.concatenate([p[n] for p in parts])
    for a in ANCHORS:
        for kind in ("f", "a"):
            t = np.concatenate([p["%s_skel_%s_t" % (a, kind)] for p in parts])
            v = np.concatenate([p["%s_skel_%s_v" % (a, kind)] for p in parts])
            keep["%s_skel_%s_t" % (a, kind)] = t
            keep["%s_skel_%s_v" % (a, kind)] = v
            off = np.concatenate([
                p["%s_%s_off" % (a, kind)].astype(np.int64) + base
                for p, base in zip(parts, _bases(parts, a, kind))])
            keep["%s_%s_off" % (a, kind)] = off
    return keep, sides


def _bases(parts, anchor, kind):
    """Running offset of each shard's ragged block after concatenation."""
    out, acc = [], 0
    for p in parts:
        out.append(acc)
        acc += int(p["%s_skel_%s_t" % (anchor, kind)].size)
    return out


def tau_matrix(arr, anchor, side_kind):
    """(n, 200) view of the first-passage tensor (absolute seconds, -1 null)."""
    a = arr["%s_tau_%s" % (anchor, side_kind)]
    return a.reshape(-1, RUNG_COUNT)


# ====================================================== the query kernel =====
_BIG_T = np.int64(1 << 40)           # >> any session second
_BIG_V = np.int64(1 << 50)           # >> any cent value


def _global_keys(off, ln, n_rows):
    """Row index per ragged element, for the offset-shifted searchsorted."""
    idx = np.repeat(np.arange(n_rows, dtype=np.int64), ln)
    return idx


def last_le(off, ln, t, v, marks):
    """v of the LAST record with t <= mark, else 0.0 (vectorised, exact).

    Records are ascending in t within a row and rows are laid end-to-end, so
    shifting each row's keys by row_index * _BIG_T makes the whole array
    globally ascending and one searchsorted answers every row at once.
    """
    n = off.size
    ln = ln.astype(np.int64)
    off = off.astype(np.int64)
    idx = _global_keys(off, ln, n)
    keys = t.astype(np.int64) + idx * _BIG_T
    q = marks.astype(np.int64) + np.arange(n, dtype=np.int64) * _BIG_T
    pos = np.searchsorted(keys, q, side="right") - 1
    has = pos >= off
    out = np.zeros(n, dtype=np.float64)
    sel = has & (ln > 0)
    out[sel] = v[pos[sel]].astype(np.float64)
    return out


def first_ge_value(off, ln, t, v, thresh):
    """t of the FIRST record with v >= thresh, else -1 (v is non-decreasing).

    Values are quantised to integer cents for the shifted searchsorted so the
    key arithmetic is exact in int64.
    """
    n = off.size
    ln = ln.astype(np.int64)
    off = off.astype(np.int64)
    idx = _global_keys(off, ln, n)
    cents = np.rint(v.astype(np.float64) * 100.0).astype(np.int64)
    keys = cents + idx * _BIG_V
    q = np.rint(np.asarray(thresh, dtype=np.float64) * 100.0).astype(np.int64) \
        + np.arange(n, dtype=np.int64) * _BIG_V
    pos = np.searchsorted(keys, q, side="left")
    end = off + ln
    ok = (ln > 0) & (pos < end)
    out = np.full(n, -1, dtype=np.int64)
    out[ok] = t[pos[ok]].astype(np.int64)
    return out


def mark_secs(arr, anchor, mark):
    """Absolute session second of a horizon mark (-1 when past the close)."""
    a = arr["%s_anchor_sec" % anchor].astype(np.int64)
    obs = arr["%s_observed_secs" % anchor].astype(np.int64)
    if mark in MARK_SECS:
        mk = a + MARK_SECS[mark]
    elif mark == "phase_close":
        mk = arr["%s_phase_close_sec" % anchor].astype(np.int64)
    elif mark == "sess_close":
        mk = arr["%s_sess_close_sec" % anchor].astype(np.int64)
    else:
        raise KeyError(mark)
    bad = (obs == 0)
    mk = np.where(bad, -1, mk)
    return mk


def f_mark(arr, anchor, mark):
    """The stored terminal f($) at a mark (NaN past the close / unavailable)."""
    return arr["%s_f_%s" % (anchor, mark)].astype(np.float64)


def mfe_at(arr, anchor, mark):
    """MFE($) within [anchor, mark] from the favorable prefix-max records."""
    mk = mark_secs(arr, anchor, mark)
    out = last_le(arr["%s_f_off" % anchor], arr["%s_f_len" % anchor],
                  arr["%s_skel_f_t" % anchor], arr["%s_skel_f_v" % anchor],
                  np.maximum(mk, -1))
    out[mk < 0] = np.nan
    out[np.isnan(f_mark(arr, anchor, mark))] = np.nan
    return out


def mae_at(arr, anchor, mark):
    """MAE($, positive) within [anchor, mark] from the adverse records."""
    mk = mark_secs(arr, anchor, mark)
    out = last_le(arr["%s_a_off" % anchor], arr["%s_a_len" % anchor],
                  arr["%s_skel_a_t" % anchor], arr["%s_skel_a_v" % anchor],
                  np.maximum(mk, -1))
    out[mk < 0] = np.nan
    out[np.isnan(f_mark(arr, anchor, mark))] = np.nan
    return out


def wall_hit_sec(arr, anchor, wall_usd):
    """First second whose adverse excursion reaches `wall_usd` (-1 = never)."""
    n = arr["%s_anchor_sec" % anchor].size
    return first_ge_value(arr["%s_a_off" % anchor], arr["%s_a_len" % anchor],
                          arr["%s_skel_a_t" % anchor],
                          arr["%s_skel_a_v" % anchor],
                          np.full(n, float(wall_usd)))


def walled_value(arr, anchor, mark, wall_usd, cost_rt):
    """The m0 §8 walled certificate at a mark, from skeleton queries only."""
    mk = mark_secs(arr, anchor, mark)
    f = f_mark(arr, anchor, mark)
    tw = wall_hit_sec(arr, anchor, wall_usd)
    hit = (tw >= 0) & (tw <= mk) & (mk >= 0)
    val = np.where(hit, -float(wall_usd) - cost_rt, f - cost_rt)
    val[mk < 0] = np.nan
    exit_sec = np.where(hit, tw, mk)
    return val, exit_sec.astype(np.int64)


def tau_at_rung(arr, anchor, side_kind, k):
    """Absolute first-passage second at ladder index k (1-based), -1 = null."""
    return tau_matrix(arr, anchor, side_kind)[:, k - 1].astype(np.int64)


def rung_index(theta_atr):
    """Ladder index for a theta expressed in ATR units (round HALF-UP).

    The spec's theta grid is {0.1,0.2,0.4,0.6,1.0} x ATR (exact multiples of
    the 0.02 ladder step) plus 0.15 x ATR, which is NOT on the ladder: k=7.5.
    Rounding half-up gives k=8 (0.16 x ATR); the realised theta is reported
    beside every cell that uses it (S4 defect ledger).
    """
    k = int(np.floor(theta_atr / RUNG_STEP + 0.5))
    return max(1, min(RUNG_COUNT, k))


# ============================================================ roster join ====
ROSTER_FIELDS = ("date8", "side", "rung_mask", "conf_sec", "dec_sec",
                 "phase_conf", "phase_dec", "entry_mid", "spread_at_decision",
                 "atr14_usd", "dom_share", "iid", "mfe_unwalled",
                 "mfe_argmax_sec", "mae_before_argmax", "f_h30", "f_h60",
                 "f_h120", "f_phase_close", "f_sess_close", "phase_close_sec",
                 "sess_close_sec", "fam_mask", "level_fam_mask")


def load_roster(asset):
    z = np.load(os.path.join(ROSTER_DIR, "union_roster_%s.npz" % asset),
                allow_pickle=False)
    out = {k: z[k] for k in ROSTER_FIELDS}
    z.close()
    return out


def load_candidates(asset):
    side, arr = binpack.read(os.path.join(CAND_DIR, asset), "QRCAND1")
    return side, arr


def check_join(arr, roster):
    """cand_id indexes the roster; every joined field must agree exactly."""
    cid = arr["cand_id"].astype(np.int64)
    bad = {}
    for f, g in (("date8", "date8"), ("dec_sec", "dec_sec"), ("side", "side")):
        d = int(np.sum(arr[f].astype(np.int64) != roster[g][cid].astype(np.int64)))
        if d:
            bad[f] = d
    a = arr["atr14_usd"].astype(np.float64)
    b = roster["atr14_usd"][cid].astype(np.float64)
    d = int(np.sum(~(np.isclose(a, b, rtol=0, atol=0) | (np.isnan(a) & np.isnan(b)))))
    if d:
        bad["atr14_usd"] = d
    return cid, bad


# ================================================== universe / era / units ===
def subsample_mask(cand_id, rate=SUBSAMPLE, salt=SUBSAMPLE_SALT):
    """Deterministic, roster-order-independent 25% draw (sha256 of the id)."""
    out = np.zeros(cand_id.size, dtype=bool)
    thr = int(rate * (1 << 32))
    for i, c in enumerate(cand_id.tolist()):
        h = hashlib.sha256(("%s|%d" % (salt, c)).encode()).digest()
        out[i] = int.from_bytes(h[:4], "big") < thr
    return out


def unit_keys(roster, cid, unit):
    """Ranking-unit group id per row: phase / session / day (first-class axis).

    'session' and 'day' differ in this corpus only where a session spans two
    UTC days; the roster's date8 IS the session key, so 'day' is the UTC day of
    the decision second, computed from the session date plus the day rollover.
    """
    d8 = roster["date8"][cid].astype(np.int64)
    if unit == "session":
        return d8
    if unit == "phase":
        return d8 * 10 + roster["phase_dec"][cid].astype(np.int64)
    if unit == "day":
        # session seconds run from the session open; a decision second past
        # 86400 belongs to the next UTC day.
        roll = (roster["dec_sec"][cid].astype(np.int64) // 86400)
        return d8 * 10 + roll
    raise KeyError(unit)


def era_mask(roster, cid, years=FIT_YEARS):
    y = (roster["date8"][cid] // 10000).astype(np.int64)
    return np.isin(y, np.array(years, dtype=np.int64))


def cost_rt_per_row(asset, roster, cid):
    """Session-scoped round-trip cost ($) per candidate (census_a medians)."""
    import c_a_cost as CA
    cm = CA.session_cost_rt(M.M0_ROOT)
    d8 = roster["date8"][cid].astype(np.int64)
    uniq = np.unique(d8)
    lut = {}
    for d in uniq.tolist():
        iso = "%04d-%02d-%02d" % (d // 10000, (d // 100) % 100, d % 100)
        v = cm.get((asset, iso), float("nan"))
        lut[d] = v if np.isfinite(v) else C.FEES_RT
    return np.array([lut[d] for d in d8.tolist()], dtype=np.float64)


def wall_usd(asset):
    with open(os.path.join(M.M0_ROOT, "walls.json")) as fh:
        return float(json.load(fh)["walls"][asset]["wall_usd"])
