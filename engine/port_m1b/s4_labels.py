#!/usr/bin/python3
"""PORT M1.B S4 — the compose() label grid, built ONLY from skeleton queries.

compose(base, horizon, truncation, penalty, transform, ranking_unit), ported
from LABEL_ATLAS_V2 §1B/§1C/§1D with every IWM-native constant re-derived per
asset (§4.5.3): the round-trip cost is the census_a session cost_rt, the wall
is m0's walls.json, the rungs are the S3 ATR ladder.

BASE FAMILIES (spec §1 S4 bullet 1)
  net_h            terminal $ at the mark, cost_rt-netted          [dollar]
  mfe_h            favorable excursion inside the mark              [dollar]
  retention        net_h / max(mfe_h, eps), eps in {1,5,15,30}x cost_rt,
                   plain and MOVER-GATED (NaN where mfe < eps)      [ratio]
  ratio axis       gbabs/gbshare/gbfrac/effpath/rrreal/mfeshare (§1C C2-C7)
  fp               time to first favorable passage of theta x ATR   [time]
  race             fp_race(theta_u, theta_d), tie -> -1 (§1B B7)     [ordinal]
  tb               triple-barrier CONTROL cells (the literature control,
                   priced at the recovered zero expectation)         [dollar]
  uw_share         time-underwater share                            [ratio]
  ttp              time to first +1 sigma-hat passage, censored      [time]
  cfa_wait_K       act-now vs wait regret, K in {60m, phase}, d1 anchor
  reclaim_dir      sign(net_h) conditioned on the G2-RECLAIM tag     [ordinal]
  cert_W           walled certificate, wall $900                     [dollar]
  maebudget_W      MAE-budget ladder {0.5,1,1.5,2} x wall            [dollar]
  path shapes      S3 landmarks as labels (monotonicity, ttp, giveback,
                   mae_unwalled, mfeshare)                          [various]
  shadow_value     occupancy-aware DP shadow at {60m, phase-close}; every
                   member gets a within-session-SHUFFLED twin (§1D guard)

F-PROX IS BARRED (§4.3 A13). `assert_no_fprox()` runs over the enumerated grid:
no base may be truth-set-relative, and this module never imports the oracle-leg
machinery (c_d_recall) - checked at runtime.
"""
import hashlib
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s4_common as S

# ------------------------------------------------------------------ axes ----
HORIZONS = ("h30", "h60", "h120", "phase_close", "sess_close")
TRUNCATIONS = (("tnone", None), ("t450", -450.0), ("t900", -900.0))
PENALTIES = (("p0", 0.0, 0.0),
             ("p05m150", 0.5, 150.0), ("p05m300", 0.5, 300.0),
             ("p05m900", 0.5, 900.0),
             ("p10m150", 1.0, 150.0), ("p10m300", 1.0, 300.0),
             ("p10m900", 1.0, 900.0))
TRANSFORMS = ("raw", "z", "rank", "winsor", "bin0")
UNIT_FREE = ("raw", "bin0")          # unit only matters for within-unit forms
RANKING_UNITS = ("phase", "session", "day")

EPS_MULT = (1.0, 5.0, 15.0, 30.0)    # x cost_rt (the re-derived eps grid)
EPS_DEFAULT = 5.0
THETA_ATR = (0.1, 0.2, 0.4)          # fp / race rungs
TB_PT = (0.4, 0.6, 1.0)
TB_SL = (0.15, 0.3)
WALL_LADDER = (0.5, 1.0, 1.5, 2.0)
CFA_K = (("60m", 3600), ("phase", -1))
SHADOW_MARKS = ("h60", "phase_close")

SHUFFLE_SEED = 20260813

# S1 family bit order, transcribed from engine/port_m1/b8_generation_v2.py
# FAMILIES = (G1, G1_FINE, G1_FAST_OPEN, G2_REJECT, G2_RECLAIM).  It is NOT
# imported: that module imports the oracle-leg machinery, and the F-PROX bar
# below is structural (the label builder's process must never hold it).
# test_s4.py asserts this constant against the real one, in its own process.
S1_FAMILIES = ("G1", "G1_FINE", "G1_FAST_OPEN", "G2_REJECT", "G2_RECLAIM")
FAM_BIT_G2_RECLAIM = 1 << S1_FAMILIES.index("G2_RECLAIM")

# base kind -> which axes are legal (the P2/P3/P7 machinery)
DOLLAR, RATIO, ORDINAL, TIME, BINARY = "dollar", "ratio", "ordinal", "time", \
    "binary"


class Member(object):
    __slots__ = ("name", "family", "base", "kind", "horizon", "trunc", "pen",
                 "transform", "unit", "occupancy_derived", "shuffled",
                 "params")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    def row(self):
        return [self.name, self.family, self.base, self.kind, self.horizon,
                self.trunc or "", self.pen or "", self.transform,
                self.unit or "", int(bool(self.occupancy_derived)),
                int(bool(self.shuffled)), self.params or ""]


MEMBER_COLUMNS = ["label", "family", "base", "kind", "horizon", "truncation",
                  "penalty", "transform", "ranking_unit", "occupancy_derived",
                  "shuffled_twin", "params"]


# ======================================================== the atom cache =====
class Atoms(object):
    """Every quantity the grid composes, queried once per (asset, universe)."""

    def __init__(self, asset, arr, roster, cid, rows, cost_rt, wall,
                 sigma_hat):
        self.asset = asset
        self.arr = arr
        self.roster = roster
        self.cid = cid                     # roster row per skeleton row
        self.rows = rows                   # skeleton rows in the universe
        self.cost = cost_rt[rows]
        self.wall = wall
        self.n = rows.size
        self.f, self.mfe, self.mae = {}, {}, {}
        for h in HORIZONS:
            self.f[h] = S.f_mark(arr, "a0", h)[rows]
            self.mfe[h] = S.mfe_at(arr, "a0", h)[rows]
            self.mae[h] = S.mae_at(arr, "a0", h)[rows]
        self.f_d1 = {h: S.f_mark(arr, "a1", h)[rows] for h in HORIZONS}
        self.mark_sec = {h: S.mark_secs(arr, "a0", h)[rows] for h in HORIZONS}
        self.anchor_sec = arr["a0_anchor_sec"].astype(np.int64)[rows]
        self.obs = arr["a0_observed_secs"].astype(np.int64)[rows]
        # landmarks
        for f in ("mfe_usd", "mae_unwalled_usd", "mae_before_argmax_usd",
                  "giveback_post_peak_usd", "time_to_peak_secs",
                  "uw_share", "monotonicity", "f_terminal_usd"):
            setattr(self, f, arr["a0_" + f].astype(np.float64)[rows])
        # first-passage tensors at the theta rungs actually used
        self.tau = {}
        ks = set()
        for th in THETA_ATR:
            ks.add(S.rung_index(th))
        for th in TB_PT + TB_SL:
            ks.add(S.rung_index(th))
        for k in sorted(ks):
            self.tau[("up", k)] = S.tau_at_rung(arr, "a0", "up", k)[rows]
            self.tau[("dn", k)] = S.tau_at_rung(arr, "a0", "dn", k)[rows]
        self.atr = arr["atr14_usd"].astype(np.float64)[rows]
        self.sigma_hat = sigma_hat[rows]
        # walled certificates (skeleton queries, m0 semantics)
        self.cert = {}
        for w in WALL_LADDER:
            W = wall * w
            for h in HORIZONS:
                v, ex = S.walled_value(arr, "a0", h, W, 0.0)
                self.cert[(w, h)] = (v[rows] - self.cost, ex[rows])
        self.fam_mask = roster["fam_mask"][cid][rows]
        self.unit = {}
        for u in RANKING_UNITS:
            self.unit[u] = S.unit_keys(roster, cid, u)[rows]
        self.date8 = roster["date8"][cid][rows]
        self.dec_sec = roster["dec_sec"][cid][rows]

    def net(self, h):
        return self.f[h] - self.cost

    def net_d1(self, h):
        return self.f_d1[h] - self.cost


# ============================================================== transforms ===
def _group_apply(x, units, fn):
    """Apply fn per ranking unit, deterministically (sorted group order)."""
    out = np.full(x.size, np.nan)
    order = np.argsort(units, kind="stable")
    u = units[order]
    xs = x[order]
    edges = np.flatnonzero(np.diff(u)) + 1
    starts = np.concatenate(([0], edges))
    ends = np.concatenate((edges, [u.size]))
    for a, b in zip(starts.tolist(), ends.tolist()):
        out[order[a:b]] = fn(xs[a:b])
    return out


def _z(v):
    ok = np.isfinite(v)
    if ok.sum() < 2:
        return np.full(v.size, np.nan)
    med = np.median(v[ok])
    mad = np.median(np.abs(v[ok] - med))
    scale = 1.4826 * mad
    if not np.isfinite(scale) or scale <= 0:
        return np.full(v.size, np.nan)
    out = np.full(v.size, np.nan)
    out[ok] = (v[ok] - med) / scale
    return out


def _rank(v):
    ok = np.isfinite(v)
    out = np.full(v.size, np.nan)
    n = int(ok.sum())
    if n < 2:
        return out
    x = v[ok]
    order = np.argsort(x, kind="stable")
    r = np.empty(n, dtype=np.float64)
    sx = x[order]
    i = 0
    while i < n:
        j = i
        while j + 1 < n and sx[j + 1] == sx[i]:
            j += 1
        r[order[i:j + 1]] = 0.5 * (i + j) + 1.0        # average rank, ties
        i = j + 1
    out[ok] = (r - 0.5) / n                             # within-unit pctile
    return out


def _winsor(v):
    ok = np.isfinite(v)
    out = np.array(v, dtype=np.float64, copy=True)
    if ok.sum() < 3:
        return out
    lo = np.percentile(v[ok], 0.5)
    hi = np.percentile(v[ok], 99.5)
    out[ok] = np.clip(v[ok], lo, hi)
    return out


def transform(x, kind, units):
    if kind == "raw":
        return x
    if kind == "bin0":
        out = np.where(np.isfinite(x), (x > 0).astype(np.float64), np.nan)
        return out
    if kind == "z":
        return _group_apply(x, units, _z)
    if kind == "rank":
        return _group_apply(x, units, _rank)
    if kind == "winsor":
        return _group_apply(x, units, _winsor)
    raise KeyError(kind)


def shape(x, mae, trunc, lam, m):
    """Truncation XOR penalty (P4), both dollar-space (P2/P3)."""
    if trunc is not None:
        return np.maximum(x, trunc)
    if lam > 0.0:
        return x - lam * np.maximum(0.0, mae - m)
    return x


# ========================================================= shadow values =====
def shadow_value(atoms, mark):
    """§1D D1: the $ cost of FORCING each action into the optimal uncapped
    one-position schedule, per SESSION.

        shadow(a) = prefix[start(a)] + w(a) + suffix[end(a)] - optimal   (<= 0)

    Intervals are [decision_sec, exit_sec] of the walled certificate at this
    mark (the same object the occupancy DP seats); only w > 0 actions can be
    seated, exactly as in the m0 DP.
    """
    val, ex = atoms.cert[(1.0, mark)]
    start = atoms.dec_sec.astype(np.int64)
    end = np.where(ex >= 0, ex, start).astype(np.int64)
    out = np.full(atoms.n, np.nan)
    occ = np.full(atoms.n, np.nan)
    sess = atoms.date8
    order = np.argsort(sess, kind="stable")
    u = sess[order]
    edges = np.flatnonzero(np.diff(u)) + 1
    for a, b in zip(np.concatenate(([0], edges)).tolist(),
                    np.concatenate((edges, [u.size])).tolist()):
        idx = order[a:b]
        v = val[idx]
        s = start[idx]
        e = end[idx]
        ok = np.isfinite(v)
        if not ok.any():
            continue
        opt, pre, suf = _dp_prefix_suffix(s[ok], e[ok], v[ok])
        sub = idx[ok]
        sh = np.empty(sub.size)
        for i in range(sub.size):
            sh[i] = (_lookup_prefix(pre, s[ok][i]) + max(v[ok][i], 0.0)
                     + _lookup_suffix(suf, e[ok][i]) - opt)
        out[sub] = np.minimum(sh, 0.0)
        span = float(np.max(e[ok]) - np.min(s[ok])) if sub.size else np.nan
        occ[sub] = span
    return out, occ


def _dp_prefix_suffix(start, end, val):
    """Uncapped one-position weighted-interval DP, both directions.

    Returns (optimal, prefix, suffix) where prefix = (times, best) with
    best[i] = optimum using only items ending <= times[i], and suffix likewise
    for items starting >= times[i].  A new position may start STRICTLY after
    the previous exit (the m0 rule).
    """
    n = start.size
    pos = val > 0
    s, e, v = start[pos], end[pos], val[pos]
    if s.size == 0:
        return 0.0, (np.array([-1]), np.array([0.0])), \
            (np.array([1 << 60]), np.array([0.0]))
    o = np.argsort(e, kind="stable")
    s, e, v = s[o], e[o], v[o]
    m = s.size
    best = np.zeros(m + 1)
    for i in range(1, m + 1):
        j = int(np.searchsorted(e, s[i - 1], side="left"))   # e[j-1] < s[i-1]
        best[i] = max(best[i - 1], best[j] + v[i - 1])
    optimal = best[m]
    pre_t = np.concatenate(([-1], e))
    pre_v = best.copy()
    # suffix: items starting >= t, symmetric recursion on reversed axis
    o2 = np.argsort(-s, kind="stable")
    s2, e2, v2 = s[o2], e[o2], v[o2]
    bestr = np.zeros(m + 1)
    for i in range(1, m + 1):
        j = int(np.searchsorted(-s2, -e2[i - 1], side="left"))
        bestr[i] = max(bestr[i - 1], bestr[j] + v2[i - 1])
    suf_t = np.concatenate(([1 << 60], s2))
    suf_v = bestr.copy()
    return float(optimal), (pre_t, pre_v), (suf_t, suf_v)


def _lookup_prefix(pre, t):
    tt, vv = pre
    i = int(np.searchsorted(tt, t, side="left")) - 1
    return float(vv[max(i, 0)]) if i >= 0 else 0.0


def _lookup_suffix(suf, t):
    tt, vv = suf
    i = int(np.searchsorted(-tt, -t, side="left")) - 1
    return float(vv[max(i, 0)]) if i >= 0 else 0.0


def shuffle_within_session(x, sess, seed=SHUFFLE_SEED):
    """§1D GUARD: destroy only the row<->label association, keeping every
    per-session marginal and the row count identical."""
    rs = np.random.RandomState(seed)
    out = np.array(x, copy=True)
    order = np.argsort(sess, kind="stable")
    u = sess[order]
    edges = np.flatnonzero(np.diff(u)) + 1
    for a, b in zip(np.concatenate(([0], edges)).tolist(),
                    np.concatenate((edges, [u.size])).tolist()):
        idx = order[a:b]
        perm = rs.permutation(idx.size)
        out[idx] = x[idx][perm]
    return out


# ============================================================ the grid =======
def enumerate_grid(atoms):
    """Yield (Member, values) in a deterministic order, prunes applied."""
    prunes = {k: 0 for k in ("P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8",
                             "P9", "P10")}
    seen = {}

    def emit(m, v):
        """P9 (degenerate) + P10 (byte-identical) measured prunes."""
        ok = np.isfinite(v)
        n_ok = int(ok.sum())
        if n_ok == 0 or np.unique(v[ok]).size < 2:
            prunes["P9"] += 1
            return None
        u = np.unique(v[ok])
        if u.size == 2:
            share = min((v[ok] == u[0]).mean(), (v[ok] == u[1]).mean())
            if share < 0.01:
                prunes["P9"] += 1
                return None
        h = hashlib.sha256(np.ascontiguousarray(v, dtype=np.float64).tobytes()
                           + ok.tobytes()).hexdigest()[:32]
        if h in seen:
            prunes["P10"] += 1
            return None
        seen[h] = m.name
        return m, v

    for item in _enumerate_raw(atoms, prunes):
        m, v = item
        r = emit(m, v)
        if r is not None:
            yield r
    yield ("__PRUNES__", prunes)


def _members_for(base_name, family, kind, values, horizon, params="",
                 occupancy=False, transforms=TRANSFORMS, prunes=None):
    """Expand one base column over transform x ranking-unit, P7 applied."""
    out = []
    for t in transforms:
        if kind in (ORDINAL, BINARY) and t in ("z", "rank", "winsor"):
            if prunes is not None:
                prunes["P7"] += 1
            continue
        units = [None] if t in UNIT_FREE else list(RANKING_UNITS)
        for u in units:
            name = "%s|%s|%s%s" % (base_name, horizon, t,
                                   "" if u is None else "@" + u)
            out.append(Member(name=name, family=family, base=base_name,
                              kind=kind, horizon=horizon, trunc=None, pen=None,
                              transform=t, unit=u, occupancy_derived=occupancy,
                              shuffled=False, params=params))
    return out


def _enumerate_raw(atoms, prunes):
    eps_grid = [(("e%d" % int(e)), e * atoms.cost) for e in EPS_MULT]

    # -- B1 dollar / net_h with the truncation x penalty shaping ------------
    for h in HORIZONS:
        base = atoms.net(h)
        mae = atoms.mae[h]
        for (tname, tv) in TRUNCATIONS:
            for (pname, lam, m_) in PENALTIES:
                if tv is not None and lam > 0.0:
                    prunes["P4"] += 1
                    continue
                v0 = shape(base, mae, tv, lam, m_)
                shaped = (tv is not None) or (lam > 0.0)
                for t in TRANSFORMS:
                    if t == "rank" and tv is not None:
                        prunes["P5"] += 1          # rank(truncate(x))==rank(x)
                        continue
                    if t == "bin0" and shaped:
                        prunes["P6"] += 1
                        continue
                    units = [None] if t in UNIT_FREE else list(RANKING_UNITS)
                    for u in units:
                        nm = "net|%s|%s|%s|%s%s" % (h, tname, pname, t,
                                                    "" if u is None
                                                    else "@" + u)
                        yield (Member(name=nm, family="dollar", base="net",
                                      kind=DOLLAR, horizon=h, trunc=tname,
                                      pen=pname, transform=t, unit=u,
                                      occupancy_derived=False, shuffled=False,
                                      params=""),
                               transform(v0, t, atoms.unit[u] if u else None))

    # -- B2 gain / mfe -------------------------------------------------------
    for h in HORIZONS:
        v = atoms.mfe[h] - atoms.cost
        for m in _members_for("mfe", "gain", DOLLAR, v, h, prunes=prunes):
            yield (m, transform(v, m.transform,
                                atoms.unit[m.unit] if m.unit else None))

    # -- B3 retention (plain + MOVER-GATED) ---------------------------------
    for h in HORIZONS:
        net = atoms.net(h)
        mfe = atoms.mfe[h]
        for (ename, eps) in eps_grid:
            for gated in (False, True):
                den = np.maximum(mfe, eps)
                v = net / den
                if gated:
                    v = np.where(mfe < eps, np.nan, v)
                nm = "ret%s|%s" % ("g" if gated else "", ename)
                for m in _members_for(nm, "ratio", RATIO, v, h,
                                      params="eps=%s" % ename,
                                      transforms=("raw", "z", "rank",
                                                  "winsor"), prunes=prunes):
                    yield (m, transform(v, m.transform,
                                        atoms.unit[m.unit] if m.unit else None))

    # -- §1C C2-C7 ratio axis (eps fixed at the champion-class 5x cost) ------
    for h in HORIZONS:
        net = atoms.net(h)
        mfe = atoms.mfe[h]
        mae = atoms.mae[h]
        eps = EPS_DEFAULT * atoms.cost
        gb = mfe - net
        cells = (("gbabs", -(mfe - net)),
                 ("gbshare", -(atoms.giveback_post_peak_usd
                               / np.maximum(mfe, eps))),
                 ("gbfrac", -(gb / np.maximum(mfe, eps))),
                 ("effpath", net / np.maximum(mfe + mae, eps)),
                 ("rrreal", net / np.maximum(mae, eps)),
                 ("mfeshare", mfe / np.maximum(mfe + mae, eps)))
        for (nm, v) in cells:
            for m in _members_for(nm, "ratio_axis", RATIO, v, h,
                                  transforms=("raw", "rank"), prunes=prunes):
                yield (m, transform(v, m.transform,
                                    atoms.unit[m.unit] if m.unit else None))

    # -- B4 first passage ----------------------------------------------------
    for th in THETA_ATR:
        k = S.rung_index(th)
        tau = atoms.tau[("up", k)]
        for h in HORIZONS:
            mk = atoms.mark_sec[h]
            hit = (tau >= 0) & (tau <= mk) & (mk >= 0)
            # right-censored at the mark; higher = better => negate the time
            v = np.where(hit, -(tau - atoms.anchor_sec).astype(np.float64),
                         np.nan)
            v = np.where(~hit & (mk >= 0),
                         -(mk - atoms.anchor_sec).astype(np.float64), v)
            for m in _members_for("fp%02d" % int(th * 100), "first_passage",
                                  TIME, v, h,
                                  params="theta=%.2fxATR k=%d" % (th, k),
                                  transforms=("raw", "rank"), prunes=prunes):
                yield (m, transform(v, m.transform,
                                    atoms.unit[m.unit] if m.unit else None))

    # -- B7 race (tie -> -1, the recorded rule) ------------------------------
    for thu in THETA_ATR:
        for thd in THETA_ATR:
            ku, kd = S.rung_index(thu), S.rung_index(thd)
            tu, td = atoms.tau[("up", ku)], atoms.tau[("dn", kd)]
            for h in HORIZONS:
                mk = atoms.mark_sec[h]
                uh = (tu >= 0) & (tu <= mk) & (mk >= 0)
                dh = (td >= 0) & (td <= mk) & (mk >= 0)
                v = np.zeros(atoms.n)
                v[uh & (~dh)] = 1.0
                v[dh & (~uh)] = -1.0
                both = uh & dh
                v[both] = np.where(tu[both] < td[both], 1.0, -1.0)
                v[mk < 0] = np.nan
                nm = "race%02d_%02d" % (int(thu * 100), int(thd * 100))
                for m in _members_for(nm, "race", ORDINAL, v, h,
                                      params="tie=-1", prunes=prunes):
                    yield (m, transform(v, m.transform, None))

    # -- B8 triple-barrier CONTROL ------------------------------------------
    for pt in TB_PT:
        for sl in TB_SL:
            kp, ks = S.rung_index(pt), S.rung_index(sl)
            tu, td = atoms.tau[("up", kp)], atoms.tau[("dn", ks)]
            pt_usd = kp * S.RUNG_STEP * atoms.atr
            sl_usd = ks * S.RUNG_STEP * atoms.atr
            for h in HORIZONS:
                mk = atoms.mark_sec[h]
                uh = (tu >= 0) & (tu <= mk) & (mk >= 0)
                dh = (td >= 0) & (td <= mk) & (mk >= 0)
                first_up = uh & (~dh | (tu < td))
                first_dn = dh & (~uh | (td <= tu))
                v = atoms.net(h).copy()                 # vertical barrier
                v = np.where(first_up, pt_usd - atoms.cost, v)
                v = np.where(first_dn & ~first_up, -sl_usd - atoms.cost, v)
                v[mk < 0] = np.nan
                nm = "tb%02d_%02d" % (int(pt * 100), int(sl * 100))
                for m in _members_for(nm, "triple_barrier_control", DOLLAR, v,
                                      h, params="pt_k=%d sl_k=%d" % (kp, ks),
                                      transforms=("raw", "rank"),
                                      prunes=prunes):
                    yield (m, transform(v, m.transform,
                                        atoms.unit[m.unit] if m.unit else None))

    # -- B9/B10/path shapes --------------------------------------------------
    shapes = (("uw_share", atoms.uw_share, RATIO),
              ("monotonicity", atoms.monotonicity, RATIO),
              ("time_to_peak", -atoms.time_to_peak_secs.astype(np.float64),
               TIME),
              ("giveback", -atoms.giveback_post_peak_usd, DOLLAR),
              ("mae_unwalled", -atoms.mae_unwalled_usd, DOLLAR))
    for (nm, v, kind) in shapes:
        for m in _members_for(nm, "path_shape", kind, v, "sess_close",
                              transforms=("raw", "rank"), prunes=prunes):
            yield (m, transform(v, m.transform,
                                atoms.unit[m.unit] if m.unit else None))

    # ttp(sigma-hat): seconds to the first +1 sigma passage inside 60m
    k_sig = np.clip(np.rint(atoms.sigma_hat
                            / (S.RUNG_STEP * atoms.atr)).astype(np.int64),
                    1, S.RUNG_COUNT)
    tau_sig = np.full(atoms.n, -1, dtype=np.int64)
    for k in np.unique(k_sig).tolist():
        sel = k_sig == k
        if ("up", k) not in atoms.tau:
            atoms.tau[("up", k)] = S.tau_at_rung(atoms.arr, "a0", "up",
                                                 int(k))[atoms.rows]
        tau_sig[sel] = atoms.tau[("up", k)][sel]
    mk60 = atoms.mark_sec["h60"]
    hit = (tau_sig >= 0) & (tau_sig <= mk60) & (mk60 >= 0)
    v = np.where(hit, -(tau_sig - atoms.anchor_sec).astype(np.float64),
                 np.where(mk60 >= 0, -3600.0, np.nan))
    for m in _members_for("ttp_sigma", "ttp", TIME, v, "h60",
                          params="censored at 60m", transforms=("raw", "rank"),
                          prunes=prunes):
        yield (m, transform(v, m.transform,
                            atoms.unit[m.unit] if m.unit else None))

    # -- B6 cfa: act-now vs wait --------------------------------------------
    for h in HORIZONS:
        v = atoms.net(h) - atoms.net_d1(h)          # the d1 WAIT probe
        for m in _members_for("cfa_d1", "cfa", DOLLAR, v, h,
                              params="anchor d1 = dec+60s",
                              transforms=("raw", "z", "rank", "winsor",
                                          "bin0"), prunes=prunes):
            yield (m, transform(v, m.transform,
                                atoms.unit[m.unit] if m.unit else None))
    for (kn, ksec) in CFA_K:
        best = _best_later_net(atoms, ksec)
        for h in ("h60", "phase_close"):
            v = atoms.net(h) - best[h]
            for m in _members_for("cfa_wait_%s" % kn, "cfa", DOLLAR, v, h,
                                  params="K=%s" % kn,
                                  transforms=("raw", "z", "rank", "winsor",
                                              "bin0"), prunes=prunes):
                yield (m, transform(v, m.transform,
                                    atoms.unit[m.unit] if m.unit else None))

    # -- B11 reclaim-conditioned direction -----------------------------------
    is_rec = (atoms.fam_mask & FAM_BIT_G2_RECLAIM) > 0
    for h in HORIZONS:
        v = np.where(is_rec, np.sign(atoms.net(h)), np.nan)
        for m in _members_for("reclaim_dir", "reclaim", ORDINAL, v, h,
                              params="conditioned on the G2-RECLAIM tag",
                              transforms=("raw",), prunes=prunes):
            yield (m, transform(v, m.transform, None))

    # -- walled certificate + the MAE-budget ladder --------------------------
    for h in HORIZONS:
        v = atoms.cert[(1.0, h)][0]
        for m in _members_for("cert_w1", "certificate", DOLLAR, v, h,
                              params="wall=$%.0f" % atoms.wall,
                              transforms=("raw", "z", "rank"), prunes=prunes):
            yield (m, transform(v, m.transform,
                                atoms.unit[m.unit] if m.unit else None))
    for w in WALL_LADDER:
        for h in ("h60", "phase_close"):
            v = atoms.cert[(w, h)][0]
            for m in _members_for("maebudget_w%02d" % int(w * 100),
                                  "mae_budget", DOLLAR, v, h,
                                  params="wall=%.1fx" % w,
                                  transforms=("raw",), prunes=prunes):
                yield (m, transform(v, m.transform, None))

    # -- §1D shadow values + the mandatory shuffled twins --------------------
    for h in SHADOW_MARKS:
        sv, _occ = shadow_value(atoms, h)
        for m in _members_for("shadow", "shadow_value", DOLLAR, sv, h,
                              occupancy=True,
                              transforms=("raw", "rank", "z"), prunes=prunes):
            yield (m, transform(sv, m.transform,
                                atoms.unit[m.unit] if m.unit else None))
        twin = shuffle_within_session(sv, atoms.date8)
        for m in _members_for("shadow_SHUF", "shadow_value", DOLLAR, twin, h,
                              occupancy=True,
                              transforms=("raw", "rank", "z"), prunes=prunes):
            mm = m
            mm.shuffled = True
            yield (mm, transform(twin, m.transform,
                                 atoms.unit[m.unit] if m.unit else None))


def _best_later_net(atoms, ksec):
    """Best net among the SAME session's LATER actions within K (or phase)."""
    out = {}
    for h in ("h60", "phase_close"):
        net = atoms.net(h)
        best = np.full(atoms.n, np.nan)
        order = np.argsort(atoms.date8 * (1 << 20) + atoms.dec_sec,
                           kind="stable")
        u = atoms.date8[order]
        edges = np.flatnonzero(np.diff(u)) + 1
        for a, b in zip(np.concatenate(([0], edges)).tolist(),
                        np.concatenate((edges, [u.size])).tolist()):
            idx = order[a:b]
            t = atoms.dec_sec[idx].astype(np.int64)
            v = net[idx]
            # suffix maximum over later actions
            sm = np.full(idx.size + 1, -np.inf)
            for i in range(idx.size - 1, -1, -1):
                sm[i] = max(sm[i + 1], v[i] if np.isfinite(v[i]) else -np.inf)
            if ksec < 0:
                lim = atoms.mark_sec["phase_close"][idx]
            else:
                lim = t + ksec
            hi = np.searchsorted(t, lim, side="right")
            res = np.full(idx.size, np.nan)
            for i in range(idx.size):
                j0, j1 = i + 1, int(hi[i])
                if j1 > j0:
                    seg = v[j0:j1]
                    seg = seg[np.isfinite(seg)]
                    if seg.size:
                        res[i] = seg.max()
            best[idx] = np.where(np.isfinite(res), res, 0.0)
        out[h] = best
    return out


# ============================================================= F-PROX bar ====
FPROX_PATTERNS = ("fprox", "prox_to_truth", "truth_dist", "oracle_dist",
                  "leg_prox", "dist_to_oracle")
TRUTH_RELATIVE_BASES = ()            # deliberately EMPTY: none may exist


def assert_no_fprox(names):
    """§4.3 A13 — port the BAR. Truth-set-relative labels may not exist.

    Structural: this module never imports the oracle-leg machinery, so no
    label CAN be truth-relative; the name scan is the second lock.
    """
    if "c_d_recall" in sys.modules and \
            getattr(sys.modules["c_d_recall"], "__name__", "") == "c_d_recall":
        raise RuntimeError("assert_no_fprox: the oracle-leg module is loaded "
                           "in the label builder's process")
    bad = [n for n in names
           if any(p in n.lower() for p in FPROX_PATTERNS)]
    if bad or TRUTH_RELATIVE_BASES:
        raise RuntimeError("assert_no_fprox: %d truth-relative members: %s"
                           % (len(bad), bad[:5]))
    return len(names)
