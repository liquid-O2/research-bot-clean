#!/usr/bin/python3
"""PORT M1 — DAY-HIGH/LOW PREDICTION CENSUS (PORT_HL_CENSUS_SPEC.md, frozen
sha16 ff35394b9f87b891).

Question the census answers: which a-priori level constructions actually
PREDICT where the session (and phase) HIGH and LOW land, well enough to feed
event generation?

Everything here is a pure receipt read (spec §4): m0 session receipts + bars,
m1/fvol forecasts, m1/levels_v2 ledgers.  No raw DBN decode.

D-054 / CC-M1-4 (BINDING): every mid read in this file — the H/L targets
themselves, the opens, the OR windows, the settles — is taken over MID-SANE
seconds only.  The mask is NOT reimplemented here: engine/port_m1/b7_sane.py
is the port's canonical D-054 implementation and this lane consumes its
published per (asset, date, phase) thresholds, so every port lane measures the
same seconds.  Insane seconds are typed-excluded, never interpolated.

Families (spec §2): P1 fvol-anchor variants, P2 conditional H/L split,
P3 opening-range extensions, P4 floor + Camarilla pivots, P5 sweep-overshoot,
P6 gap-fill, P7 confluence.

Scoring (spec §3): capture / displaced-null / lift / calibration / distance /
per-year stability / marginal-over-KEPT-ledger.

Run: lab/run.sh port-m1-hl -- /usr/bin/python3 engine/port_m1/hl_census.py
"""
import datetime as dt
import json
import math
import multiprocessing as mp
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m1_common as M                    # noqa: E402
import common as C                       # noqa: E402
import census_common as X                # noqa: E402
import b2_fvol as B2                     # noqa: E402
import b7_sane as B7S                    # noqa: E402  (canonical D-054 mask)

# ------------------------------------------------------------- spec pin -----
HL_SPEC_PATH = "/workspace/design/PORT_HL_CENSUS_SPEC.md"
HL_SPEC_SHA16 = "ff35394b9f87b891"
SECTION = "PORT_HL_CENSUS_SPEC §2-§4 (H/L prediction census)"
OUT_DIR = "hl_census"

# ------------------------------------------------------------- constants ----
# §3 tolerance / null (the §4 ledger tolerance and the §6b D-052 null, reused)
TOL_TICKS = 2
TOL_ATR_FRAC = 0.05
NULL_DISPLACE_ATR = 0.5

# §2
P1_SIDE_Q = (0.50, 0.75, 0.90, 0.95)
P1_CAL_WINDOW = 250                      # trailing-250 ratio calibration
P1_CAL_MIN = 30
P3_OR_MIN = (30, 60)
P3_K = (0.5, 1.0, 1.5, 2.0)
P5_DELTA_Q = (0.0, 0.25, 0.50, 0.75)
P6_GAP_ATR = 0.25
P7_TOPK = (1, 3, 5)

# §3 adoption
LIFT_MIN = 1.5
MARGINAL_MIN_PP = 0.03

# P2 walk-forward
P2_MIN_TRAIN = B2.MIN_TRAIN              # 250 sessions
P2_FREEZE_CUTOFF = dt.date(2025, 1, 1)   # era law (b2.fit_walkforward)

SEGMENTS = ("SESSION",) + tuple(X.PHASE_NAMES)          # SESSION,TOKYO,LONDON,NY
PHASE_SEGMENTS = tuple(X.PHASE_NAMES)

TGT_SESSION = "SESSION_HL"
TGT_PHASE = "PHASE_HL"
TGT_REST = "REST_OF_WINDOW"

ERAS = ("2021", "2022", "2023", "2024", M.ERA_FIT, M.ERA_GATE)

PARAMS = {
    "spec": "PORT_HL_CENSUS_SPEC.md",
    "spec_sha16": HL_SPEC_SHA16,
    "spec_section": SECTION,
    "mid_sane": "D-054/CC-M1-4 via the port's canonical implementation "
                "engine/port_m1/b7_sane.py: TWO_SIDED and spread_$ <= "
                "min(%.0f x trailing-phase-median spread_$, $%.0f), the "
                "trailing median being the EXACT pooled median over the same "
                "phase of the trailing %d STRICTLY PRIOR sessions; warm-up "
                "falls back to the cap alone.  Thresholds read from "
                "m1/sane/sane_thresholds.tsv, so every port lane measures the "
                "same SANE seconds; insane seconds typed-excluded, never "
                "interpolated"
                % (B7S.SANE_MULT, B7S.SANE_CAP_USD, B7S.TRAILING_SESSIONS),
    "targets": "session and per-phase HIGH/LOW of the dominant-instrument "
               "MID-SANE mids; every predictor strictly causal at its anchor",
    "tolerance": "max(%d x tick_$, %.2f x ATR14_prev_$) / mult" % (TOL_TICKS,
                                                                   TOL_ATR_FRAC),
    "null": "family levels displaced %+.1f x ATR14_prev_$ / mult, sign "
            "alternating by level index within the family (D-052 null)"
            % NULL_DISPLACE_ATR,
    "p1_side_quantiles": list(P1_SIDE_Q),
    "p1_calibration": "per-side excursion ratio (anchor->extreme)/sigma_hat, "
                      "trailing %d sessions strictly prior, >= %d obs; the "
                      "ladder machinery of b2_fvol.ladder, one-sided"
                      % (P1_CAL_WINDOW, P1_CAL_MIN),
    "p2_design": "[1, sign(overnight ret), |gap|/ATR14, prior up_share, "
                 "RV5/RV66, DOW dummies Tue..Fri]; expanding-window monthly "
                 "refit, >= %d training sessions; coefficients FROZEN at the "
                 "last FIT-era refit for the 2025 echo (b2 era law)"
                 % P2_MIN_TRAIN,
    "p2_null": "unconditional split = trailing median up_share (same "
               "walk-forward window)",
    "p3": "OR = first {%s} min of each segment from its first SANE second; "
          "levels OR_H + k x OR_range / OR_L - k x OR_range, k in {%s}; "
          "target = the rest-of-window extreme"
          % (",".join(str(m) for m in P3_OR_MIN),
             ",".join("%.1f" % k for k in P3_K)),
    "p4": "floor {PP,R1,S1,R2,S2} and Camarilla {H3,L3,H4,L4} from the prior "
          "session's SANE H/L/C",
    "p5": "overshoot = signed distance from the realized extreme to the "
          "NEAREST PRIOR EXTREME IT EXCEEDED (prior-session H/L + prior-phase "
          "H/L); distribution fitted on the FIT era per asset (in-sample by "
          "spec order); delta in {0,p25,p50,p75}, tick-rounded",
    "p6": "gap session iff |session open - prev settle| > %.2f x ATR14_prev; "
          "prev settle predicts the extreme OPPOSITE the gap direction"
          % P6_GAP_ATR,
    "p7": "score(p) = number of distinct (family, tick-rounded price) levels "
          "within tol of p over KEPT ledger families + P1..P6; zones = local "
          "maxima of the score (plateau-deduplicated, merged within tol); "
          "top-k by score then price; null = zone centres displaced "
          "%+.1f x ATR14 alternating by rank" % NULL_DISPLACE_ATR,
    "adoption": "lift >= %.1f AND marginal capture >= +%.0fpp on some asset "
                "AND per-FIT-year lift sign-stable (>1 every year); P2 also "
                "must beat the unconditional split on pinball loss"
                % (LIFT_MIN, MARGINAL_MIN_PP * 100),
    "degenerate": "a receipt whose SANE session range is $0 (frozen quote; "
                  "m0 SPEC_DEFECTS D8) is dropped before any target, anchor "
                  "or prior-session read - the b2/b3 exclusion, unchanged",
    "era_law": "FIT = %s (exploratory census); %s echoed separately; 2026 "
               "sealed (never opened)" % (M.ERA_FIT, M.ERA_GATE),
}


def verify_hl_spec():
    got = C.sha256_file(HL_SPEC_PATH)[:16]
    if got != HL_SPEC_SHA16:
        raise RuntimeError("HL census spec sha16 %s != frozen %s"
                           % (got, HL_SPEC_SHA16))
    M.verify_spec()
    return got


def out_path(*parts):
    return M.out_path(OUT_DIR, *parts)


def write_tsv(path, section, phash, columns, rows, extra=()):
    """M.write_tsv, but stamping THIS lane's frozen spec (not PORT_M1's)."""
    tmp = path + ".tmp"
    lines = ["# PORT_HL_CENSUS_SPEC.md %s (hl_spec_sha16=%s, m1_spec_sha16=%s)"
             % (section, HL_SPEC_SHA16, M.SPEC_SHA16),
             "# params_hash=%s" % phash]
    for e in extra:
        lines.append("# %s" % e)
    lines.append("\t".join(columns))
    with open(tmp, "w") as fh:
        fh.write("\n".join(lines) + "\n")
        for r in rows:
            fh.write("\t".join(M._cell(v) for v in r) + "\n")
    os.replace(tmp, path)
    return path


def env_receipt():
    e = M.env_receipt(PARAMS)
    e["hl_spec_sha"] = C.sha256_file(HL_SPEC_PATH)
    e["hl_spec_sha16"] = HL_SPEC_SHA16
    return e


# ============================================================ D-054 mask =====
# The mask is NOT reimplemented here.  engine/port_m1/b7_sane.py is the port's
# canonical CC-M1-4 / D-054 implementation (10 x trailing-phase-median over the
# trailing 60 sessions, exact pooled tick-histogram median, strictly prior,
# $500 cap, warm-up falls back to the cap) and it publishes its per
# (asset, date, phase) thresholds to m1/sane/sane_thresholds.tsv.  This lane
# CONSUMES that table and that mask function, so every port lane measures the
# same SANE seconds.  A date missing from the table falls back to the $500 cap
# alone — the same warm-up rule.
SANE_CAP_USD = B7S.SANE_CAP_USD


def load_sane_thresholds(asset):
    """{d8: [threshold_$ per phase]} — the canonical b7_sane table."""
    return B7S.load_thresholds(asset)


def session_thresholds(table, trade_date):
    """The per-phase threshold array for one session (cap-only when absent)."""
    v = table.get(M.d8(trade_date))
    if v is None:
        return np.full(X.N_PHASES, SANE_CAP_USD)
    return np.asarray(v, dtype=np.float64)


# ==================================================== per-session fact pass ==
SEG_FIELDS = ("open_px", "high_px", "low_px", "close_px", "n_sane",
              "first_sec", "last_sec")


def _seg_masks(s):
    out = {"SESSION": np.ones(s.n, dtype=bool)}
    for p, name in enumerate(X.PHASE_NAMES):
        out[name] = (s.phase_tag == p)
    return out


def segment_facts(s, sane):
    """{segment: {open,high,low,close,n_sane,first_sec,last_sec}} on SANE mids."""
    masks = _seg_masks(s)
    out = {}
    for seg in SEGMENTS:
        idx = np.nonzero(masks[seg] & sane)[0]
        d = {k: float("nan") for k in SEG_FIELDS}
        d["n_sane"] = float(idx.size)
        d["first_sec"] = float(idx[0]) if idx.size else float("nan")
        d["last_sec"] = float(idx[-1]) if idx.size else float("nan")
        if idx.size:
            m = s.mid[idx]
            d["open_px"] = float(m[0])
            d["high_px"] = float(m.max())
            d["low_px"] = float(m.min())
            d["close_px"] = float(m[-1])
        out[seg] = d
    return out


def or_facts(s, sane, seg, minutes):
    """(or_h, or_l, rest_h, rest_l) for one segment's opening range.

    OR spans [first SANE second of the segment, +minutes x 60); the target is
    the extreme of the SANE mids strictly after the OR closes, to the segment's
    last second.  NaN whenever either side is empty (typed exclusion).
    """
    masks = _seg_masks(s)
    idx = np.nonzero(masks[seg] & sane)[0]
    nan4 = (float("nan"),) * 4
    if idx.size < 2:
        return nan4
    t0 = int(idx[0])
    t1 = t0 + int(minutes) * 60
    a = idx[idx < t1]
    b = idx[idx >= t1]
    if a.size == 0 or b.size == 0:
        return nan4
    ma, mb = s.mid[a], s.mid[b]
    return (float(ma.max()), float(ma.min()), float(mb.max()), float(mb.min()))


def kept_families(path=None):
    """{asset: (family,...)} — the FIT-era KEEP set of the §6b relevance census."""
    path = path or os.path.join(M.M1_ROOT, "generation", "level_relevance.tsv")
    cols, out = None, {}
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            r = dict(zip(cols, f))
            if r.get("era") != M.ERA_FIT or r.get("decision") != "KEEP":
                continue
            out.setdefault(r["asset"], []).append(r["level_family"])
    return {a: tuple(sorted(set(v))) for a, v in sorted(out.items())}


def ledger_prices(asset, trade_date, keep):
    """KEPT-family ledger level prices for one session (m1/levels_v2, D-053)."""
    p = os.path.join(M.M1_ROOT, "levels_v2", asset,
                     "%d.npz" % M.d8(trade_date))
    if not os.path.exists(p):
        return np.zeros(0, dtype=np.float64)
    z = np.load(p, allow_pickle=False)
    fam = z["level_family"]
    px = z["level_price"].astype(np.float64)
    z.close()
    sel = np.isin(fam, np.array(keep, dtype=fam.dtype)) if keep else \
        np.zeros(fam.size, dtype=bool)
    v = px[sel]
    return np.sort(v[np.isfinite(v)])


def build_facts(asset):
    """Pass A: the whole per-session fact table for one asset (date order).

    Sequential by construction: the D-054 threshold of session k is a function
    of sessions < k.
    """
    paths = X.session_paths(asset, M.M0_ROOT)
    bars = X.load_bars(asset, M.M0_ROOT)
    keep = kept_families().get(asset, ())
    thr_table = load_sane_thresholds(asset)
    rows = []
    for k, (trade_date, path) in enumerate(paths):
        if C.is_sealed(path):           # 2026 payload: never opened
            continue
        s = X.load_session(asset, trade_date, path)
        thr = session_thresholds(thr_table, trade_date)
        sane = B7S.sane_mask(s, thr)
        segf = segment_facts(s, sane)
        sfact = segf["SESSION"]
        rng = (sfact["high_px"] - sfact["low_px"]) \
            if (np.isfinite(sfact["high_px"])
                and np.isfinite(sfact["low_px"])) \
            else float("nan")
        r = {"trade_date": trade_date,
             "year": trade_date.year,
             # m0 D8 / b2_fvol.series_for: a receipt whose SANE traded range is
             # exactly $0 (or which has no sane seconds at all) is a FROZEN
             # QUOTE, not a session.  Same exclusion the vol history and the
             # level ledger already apply — never a target, never a prior-day
             # anchor.
             "degenerate": bool(not (np.isfinite(rng) and rng > 0.0)),
             "sane_range_px": rng,
             "n": int(s.n),
             "n_two_sided": int(s.valid.sum()),
             "n_sane": int(sane.sum()),
             "insane_frac": (float((s.valid & ~sane).sum()) /
                             float(max(int(s.valid.sum()), 1))),
             "thr_all_usd": float(np.median(thr)),
             "seg": segf,
             "atr": float(bars.get(trade_date, {}).get("ATR14_prev_usd",
                                                       float("nan"))),
             "ledger": ledger_prices(asset, trade_date, keep),
             "orr": {}}
        for seg in SEGMENTS:
            for mn in P3_OR_MIN:
                r["orr"][(seg, mn)] = or_facts(s, sane, seg, mn)
        rows.append(r)
        if (k + 1) % 200 == 0:
            M.hb("hl facts %s %d/%d" % (asset, k + 1, len(paths)))
    return rows


# ===================================================== fvol forecast reads ===
def load_forecasts(asset):
    """{(trade_date, segment): row-dict} from m1/fvol/fvol_forecasts.tsv."""
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


def fnum(r, k):
    if r is None:
        return float("nan")
    v = r.get(k, "")
    try:
        return float(v) if v not in ("", None) else float("nan")
    except ValueError:
        return float("nan")


# ================================================= trailing-quantile engine ==
def trailing_quantiles(ratio, qs, window=P1_CAL_WINDOW, minobs=P1_CAL_MIN):
    """Strictly-prior trailing empirical quantiles (b2_fvol.ladder semantics).

    ratio[i] may be NaN; row i is computed from rows [i-window, i) only.
    """
    ratio = np.asarray(ratio, dtype=np.float64)
    n = ratio.size
    out = np.full((n, len(qs)), np.nan)
    for i in range(n):
        w = ratio[max(0, i - window):i]
        w = w[np.isfinite(w)]
        if w.size >= minobs:
            for qi, q in enumerate(qs):
                out[i, qi] = float(np.percentile(w, q * 100.0))
    return out


# ================================================= P5 overshoot distribution =
def prior_extremes(rows, i):
    """The prior-session H/L and prior-phase H/L available at session i.

    Returns (ups, downs): prices whose ROLE is an upper (H) / lower (L) prior
    extreme.  Strictly causal: session i-1 only.
    """
    if i <= 0:
        return np.zeros(0), np.zeros(0)
    p = rows[i - 1]["seg"]
    ups, dns = [], []
    for seg in SEGMENTS:
        h, l = p[seg]["high_px"], p[seg]["low_px"]
        if np.isfinite(h):
            ups.append(h)
        if np.isfinite(l):
            dns.append(l)
    return (np.sort(np.array(ups, dtype=np.float64)),
            np.sort(np.array(dns, dtype=np.float64)))


def overshoot_samples(rows, fit_years):
    """Signed overshoot beyond the nearest prior extreme the realized extreme
    EXCEEDED (spec §2 P5), in price units, FIT era only.

    HIGH side: the largest prior UP-extreme strictly below the realized H;
    overshoot = H - that level (> 0 by construction).  A session whose H
    exceeded no prior up-extreme contributes nothing.  LOW side mirrored.
    """
    up, dn = [], []
    for i, r in enumerate(rows):
        if r["year"] not in fit_years:
            continue
        h = r["seg"]["SESSION"]["high_px"]
        l = r["seg"]["SESSION"]["low_px"]
        ups, dns = prior_extremes(rows, i)
        if np.isfinite(h) and ups.size:
            below = ups[ups < h]
            if below.size:
                up.append(float(h - below[-1]))
        if np.isfinite(l) and dns.size:
            above = dns[dns > l]
            if above.size:
                dn.append(float(above[0] - l))
    return (np.array(up, dtype=np.float64), np.array(dn, dtype=np.float64))


def overshoot_deltas(samples, tick_px):
    """{q: tick-rounded delta} for q in P5_DELTA_Q from one side's samples."""
    out = {}
    for q in P5_DELTA_Q:
        if q == 0.0:
            out[q] = 0.0
            continue
        if samples.size < P1_CAL_MIN:
            out[q] = float("nan")
            continue
        v = float(np.percentile(samples, q * 100.0))
        out[q] = X.round_half_up(v, tick_px)
    return out


# ============================================== P7 confluence clustering =====
def confluence_zones(prices, fams, tol):
    """Deterministic confluence zones over a level set.

    prices/fams are equal-length arrays (a level's family label is used only to
    de-duplicate: two levels of the SAME family at the SAME tick-rounded price
    count once).  score(p) = number of distinct levels within tol of p
    (inclusive).  A zone is a level whose score is a LOCAL MAXIMUM over its own
    +-tol neighbourhood (a tied plateau is represented by its lowest member,
    once); the zone's CENTRE is the mean of the levels that neighbourhood
    counts — the confluence centroid, not the representative level.  Zones
    whose centre falls within tol of an already-kept centre are merged away,
    scanning by descending score then ascending price.

    Returns (centres, scores) ranked by score desc, centre asc.
    """
    prices = np.asarray(prices, dtype=np.float64)
    if prices.size == 0:
        return np.zeros(0), np.zeros(0, dtype=np.int64)
    fams = np.asarray(fams)
    order = np.lexsort((fams, prices))
    prices, fams = prices[order], fams[order]
    # de-duplicate (family, price) — "distinct" levels
    keep = np.ones(prices.size, dtype=bool)
    keep[1:] = ~((fams[1:] == fams[:-1]) & (prices[1:] == prices[:-1]))
    prices, fams = prices[keep], fams[keep]
    o2 = np.argsort(prices, kind="stable")
    prices, fams = prices[o2], fams[o2]

    lo = np.searchsorted(prices, prices - tol, side="left")
    hi = np.searchsorted(prices, prices + tol, side="right")
    score = (hi - lo).astype(np.int64)

    # local maxima: no strictly-better score inside the +-tol neighbourhood,
    # and the lowest price of a tied plateau represents it.
    is_max = np.zeros(prices.size, dtype=bool)
    for i in range(prices.size):
        a, b = int(lo[i]), int(hi[i])
        nb = score[a:b]
        if score[i] < nb.max():
            continue
        ties = np.nonzero(nb == score[i])[0] + a
        if int(ties[0]) == i:
            is_max[i] = True
    cand = np.nonzero(is_max)[0]
    if cand.size == 0:
        return np.zeros(0), np.zeros(0, dtype=np.int64)
    rank = sorted(cand.tolist(),
                  key=lambda i: (-int(score[i]), float(prices[i])))
    centres, scores = [], []
    for i in rank:
        c = float(np.mean(prices[int(lo[i]):int(hi[i])]))
        if any(abs(c - k) <= tol for k in centres):
            continue
        centres.append(c)
        scores.append(int(score[i]))
    return np.array(centres, dtype=np.float64), np.array(scores, dtype=np.int64)


# ================================================== level construction =======
class LevelSet(object):
    """One family's levels for one (session, target).  side: +1 H, -1 L, 0 both."""

    __slots__ = ("price", "side")

    def __init__(self):
        self.price = []
        self.side = []

    def add(self, price, side):
        if np.isfinite(price):
            self.price.append(float(price))
            self.side.append(int(side))

    def arrays(self):
        return (np.array(self.price, dtype=np.float64),
                np.array(self.side, dtype=np.int64))


def _ols(Xm, y):
    """Least squares with a rank report (b2_fvol._ols semantics)."""
    b, _res, rank, _sv = np.linalg.lstsq(Xm, y, rcond=None)
    return b, int(rank)


P2_DOW = (1, 2, 3, 4)                    # Tue..Fri dummies, Monday = baseline


def p2_design_row(rows, i, fc):
    """[1, sign(overnight), |gap|/ATR, prior up_share, RV5/RV66, DOW...]."""
    r = rows[i]
    if i == 0:
        return None
    prev = rows[i - 1]
    o = r["seg"]["SESSION"]["open_px"]
    pc = prev["seg"]["SESSION"]["close_px"]
    atr = r["atr"]
    ph, pl, po = (prev["seg"]["SESSION"]["high_px"],
                  prev["seg"]["SESSION"]["low_px"],
                  prev["seg"]["SESSION"]["open_px"])
    row = fc.get((r["trade_date"], "SESSION"))
    rv = fnum(row, "rv5_over_rv66")
    if not (np.isfinite(o) and np.isfinite(pc) and np.isfinite(atr) and atr > 0
            and np.isfinite(ph) and np.isfinite(pl) and np.isfinite(po)
            and np.isfinite(rv) and ph > pl):
        return None
    gap = o - pc                          # overnight return, price units
    gap_atr = abs(gap) * C.ASSETS[r["asset"]]["mult"] / atr
    prior_share = (ph - po) / (ph - pl)
    dow = r["trade_date"].weekday()
    out = [1.0, math.copysign(1.0, gap) if gap != 0 else 0.0, gap_atr,
           prior_share, rv]
    out.extend(1.0 if dow == d else 0.0 for d in P2_DOW)
    return out


def p2_walkforward(rows, fc):
    """Walk-forward up_share predictions (OLS + logit link) and the null.

    Monthly expanding-window refits, >= P2_MIN_TRAIN sessions, coefficients
    frozen at the last FIT-era refit for the 2025 echo (b2 era law).  The
    unconditional null is the trailing median up_share over the same window.
    """
    n = len(rows)
    p = 5 + len(P2_DOW)
    Xm = np.full((n, p), np.nan)
    y = np.full(n, np.nan)
    for i in range(n):
        d = p2_design_row(rows, i, fc)
        if d is not None:
            Xm[i] = d
        h = rows[i]["seg"]["SESSION"]["high_px"]
        l = rows[i]["seg"]["SESSION"]["low_px"]
        o = rows[i]["seg"]["SESSION"]["open_px"]
        if np.isfinite(h) and np.isfinite(l) and np.isfinite(o) and h > l:
            y[i] = (h - o) / (h - l)
    ok = np.isfinite(Xm).all(axis=1) & np.isfinite(y)
    pred_ols = np.full(n, np.nan)
    pred_lgt = np.full(n, np.nan)
    pred_unc = np.full(n, np.nan)
    dates = [r["trade_date"] for r in rows]
    ylg = np.full(n, np.nan)
    yc = np.clip(y, 0.01, 0.99)
    m = np.isfinite(yc)
    ylg[m] = np.log(yc[m] / (1.0 - yc[m]))

    months = sorted(set((d.year, d.month) for d in dates))
    beta_o = beta_l = None
    beta_o_frozen = beta_l_frozen = None
    unc_frozen = float("nan")
    for (yy, mm) in months:
        cutoff = dt.date(yy, mm, 1)
        tr = np.array([ok[i] and dates[i] < cutoff for i in range(n)], bool)
        te = np.array([dates[i].year == yy and dates[i].month == mm
                       for i in range(n)], bool)
        unc = float("nan")
        if int(tr.sum()) >= P2_MIN_TRAIN:
            b, rank = _ols(Xm[tr], y[tr])
            beta_o = b if rank >= p else beta_o
            bl, rankl = _ols(Xm[tr], ylg[tr])
            beta_l = bl if rankl >= p else beta_l
            unc = float(np.median(y[tr]))
            if cutoff <= P2_FREEZE_CUTOFF:
                unc_frozen = unc
                if rank >= p:
                    beta_o_frozen = b.copy()
                if rankl >= p:
                    beta_l_frozen = bl.copy()
        use_o = beta_o if cutoff <= P2_FREEZE_CUTOFF else beta_o_frozen
        use_l = beta_l if cutoff <= P2_FREEZE_CUTOFF else beta_l_frozen
        use_u = unc if (cutoff <= P2_FREEZE_CUTOFF and np.isfinite(unc)) \
            else unc_frozen
        for i in np.nonzero(te)[0].tolist():
            if not np.isfinite(Xm[i]).all():
                continue
            if use_o is not None:
                pred_ols[i] = float(np.clip(Xm[i] @ use_o, 0.0, 1.0))
            if use_l is not None:
                z = float(Xm[i] @ use_l)
                pred_lgt[i] = 1.0 / (1.0 + math.exp(-max(min(z, 30.0), -30.0)))
            if np.isfinite(use_u):
                pred_unc[i] = use_u
    return {"y": y, "ols": pred_ols, "logit": pred_lgt, "uncond": pred_unc}


# =============================================== the family level builders ===
def build_family_levels(asset, rows, fc, p1cal, p2pred, p5deltas):
    """levels[(family, target)][i] -> LevelSet, for every session index i.

    Every construction is strictly causal at its declared anchor (spec §1).
    """
    spec = C.ASSETS[asset]
    mult, tick_px = spec["mult"], spec["tick_px"]
    n = len(rows)
    out = {}

    def LS(fam, tgt, i):
        key = (fam, tgt)
        if key not in out:
            out[key] = [None] * n
        if out[key][i] is None:
            out[key][i] = LevelSet()
        return out[key][i]

    for i, r in enumerate(rows):
        d = r["trade_date"]
        prev = rows[i - 1] if i else None
        sess = r["seg"]["SESSION"]
        atr = r["atr"]

        # ---------------------------------------------------------- P1 ------
        fc_s = fc.get((d, "SESSION"))
        sig_s = fnum(fc_s, "sigma_hat_usd")
        sig_s_px = sig_s / mult if np.isfinite(sig_s) and sig_s > 0 \
            else float("nan")
        settle = prev["seg"]["SESSION"]["close_px"] if prev else float("nan")
        sopen = sess["open_px"]

        # P1_BASE / P1_BASE_RS: the EXISTING ladder (symmetric range quantiles)
        for fam, pre in (("P1_BASE", "move_%s_usd_per_sigma"),
                         ("P1_BASE_RS", "move_rs_%s_usd_per_sigma")):
            if np.isfinite(sig_s_px) and np.isfinite(settle):
                for q in B2.LADDER_Q:
                    mq = fnum(fc_s, pre % ("q%02d" % int(q * 100)))
                    if np.isfinite(mq):
                        LS(fam, TGT_SESSION, i).add(settle + mq * sig_s_px, +1)
                        LS(fam, TGT_SESSION, i).add(settle - mq * sig_s_px, -1)
            for seg in PHASE_SEGMENTS:
                row = fc.get((d, seg))
                sg = fnum(row, "sigma_hat_usd")
                po = r["seg"][seg]["open_px"]
                if not (np.isfinite(sg) and sg > 0 and np.isfinite(po)):
                    continue
                for q in B2.LADDER_Q:
                    mq = fnum(row, pre % ("q%02d" % int(q * 100)))
                    if np.isfinite(mq):
                        LS(fam, TGT_PHASE, i).add(po + mq * sg / mult, +1)
                        LS(fam, TGT_PHASE, i).add(po - mq * sg / mult, -1)

        # P1_SIDE_*: per-side calibrated excursion quantiles
        for fam, anchor, tgt, seg in (("P1_SIDE_SETTLE", settle, TGT_SESSION,
                                       "SESSION"),
                                      ("P1_SIDE_SOPEN", sopen, TGT_SESSION,
                                       "SESSION")):
            cal = p1cal[(fam, seg)]
            if not (np.isfinite(anchor) and np.isfinite(sig_s_px)):
                continue
            for qi, q in enumerate(P1_SIDE_Q):
                up, dn = cal["up"][i, qi], cal["dn"][i, qi]
                if np.isfinite(up):
                    LS(fam, tgt, i).add(anchor + up * sig_s_px, +1)
                if np.isfinite(dn):
                    LS(fam, tgt, i).add(anchor - dn * sig_s_px, -1)
        for seg in PHASE_SEGMENTS:
            cal = p1cal[("P1_SIDE_POPEN", seg)]
            row = fc.get((d, seg))
            sg = fnum(row, "sigma_hat_usd")
            po = r["seg"][seg]["open_px"]
            if not (np.isfinite(sg) and sg > 0 and np.isfinite(po)):
                continue
            for qi, q in enumerate(P1_SIDE_Q):
                up, dn = cal["up"][i, qi], cal["dn"][i, qi]
                if np.isfinite(up):
                    LS("P1_SIDE_POPEN", TGT_PHASE, i).add(po + up * sg / mult, +1)
                if np.isfinite(dn):
                    LS("P1_SIDE_POPEN", TGT_PHASE, i).add(po - dn * sg / mult, -1)

        # ---------------------------------------------------------- P2 ------
        rng_hat = fnum(fc_s, "range_hat_usd")
        rng_px = rng_hat / mult if np.isfinite(rng_hat) and rng_hat > 0 \
            else float("nan")
        for fam, key in (("P2_OLS", "ols"), ("P2_LOGIT", "logit"),
                         ("P2_UNCOND", "uncond")):
            u = p2pred[key][i]
            if np.isfinite(u) and np.isfinite(rng_px) and np.isfinite(sopen):
                LS(fam, TGT_SESSION, i).add(sopen + u * rng_px, +1)
                LS(fam, TGT_SESSION, i).add(sopen - (1.0 - u) * rng_px, -1)

        # ---------------------------------------------------------- P3 ------
        for mn in P3_OR_MIN:
            for seg in SEGMENTS:
                oh, ol, _rh, _rl = r["orr"][(seg, mn)]
                if not (np.isfinite(oh) and np.isfinite(ol)):
                    continue
                rng = oh - ol
                fam = "P3_OR%d" % mn
                tgt = "%s|%s" % (TGT_REST, seg)
                for k in P3_K:
                    LS(fam, tgt, i).add(oh + k * rng, +1)
                    LS(fam, tgt, i).add(ol - k * rng, -1)

        # ---------------------------------------------------------- P4 ------
        if prev is not None:
            ph = prev["seg"]["SESSION"]["high_px"]
            pl = prev["seg"]["SESSION"]["low_px"]
            pcl = prev["seg"]["SESSION"]["close_px"]
            if np.isfinite(ph) and np.isfinite(pl) and np.isfinite(pcl):
                pp = (ph + pl + pcl) / 3.0
                rr = ph - pl
                f = LS("P4_FLOOR", TGT_SESSION, i)
                f.add(pp, 0)
                f.add(2.0 * pp - pl, +1)
                f.add(2.0 * pp - ph, -1)
                f.add(pp + rr, +1)
                f.add(pp - rr, -1)
                c = LS("P4_CAMARILLA", TGT_SESSION, i)
                c.add(pcl + 1.1 * rr / 4.0, +1)
                c.add(pcl - 1.1 * rr / 4.0, -1)
                c.add(pcl + 1.1 * rr / 2.0, +1)
                c.add(pcl - 1.1 * rr / 2.0, -1)

        # ---------------------------------------------------------- P5 ------
        ups, dns = prior_extremes(rows, i)
        for q in P5_DELTA_Q:
            du, dd = p5deltas["up"][q], p5deltas["dn"][q]
            fam = "P5_D%02d" % int(q * 100)
            if np.isfinite(du):
                for v in ups.tolist():
                    LS(fam, TGT_SESSION, i).add(v + du, +1)
                    LS(fam, TGT_PHASE, i).add(v + du, +1)
            if np.isfinite(dd):
                for v in dns.tolist():
                    LS(fam, TGT_SESSION, i).add(v - dd, -1)
                    LS(fam, TGT_PHASE, i).add(v - dd, -1)

        # ---------------------------------------------------------- P6 ------
        if prev is not None and np.isfinite(settle) and np.isfinite(sopen) \
                and np.isfinite(atr) and atr > 0:
            gap_usd = (sopen - settle) * mult
            if abs(gap_usd) > P6_GAP_ATR * atr:
                LS("P6_GAPFILL", TGT_SESSION, i).add(settle,
                                                     -1 if gap_usd > 0 else +1)
    return out


# ============================================================ scoring ========
def tol_px_of(asset, atr_usd):
    spec = C.ASSETS[asset]
    return max(TOL_TICKS * spec["tick_usd"], TOL_ATR_FRAC * atr_usd) \
        / spec["mult"]


def displaced(prices, atr_px):
    """The D-052 null: +-0.5 x ATR14 alternating by level index."""
    if prices.size == 0:
        return prices
    sgn = np.where(np.arange(prices.size) % 2 == 0, 1.0, -1.0)
    return prices + sgn * NULL_DISPLACE_ATR * atr_px


def _hit(prices, sides, target, side, tol):
    """min distance from `target` to a level of a compatible side; hit iff <= tol."""
    if prices.size == 0:
        return (float("nan"), False)
    sel = (sides == side) | (sides == 0)
    if not sel.any():
        return (float("nan"), False)
    d = np.abs(prices[sel] - target)
    md = float(d.min())
    return (md, md <= tol)


def target_pairs(r, target):
    """[(price, side)] — the realized extremes this target scores on.

    REST_OF_WINDOW targets are OR-window specific and resolved by
    `rest_targets` instead (the OR length lives in the family name).
    """
    out = []
    if target == TGT_SESSION:
        s = r["seg"]["SESSION"]
        out.append((s["high_px"], +1))
        out.append((s["low_px"], -1))
    elif target == TGT_PHASE:
        for seg in PHASE_SEGMENTS:
            s = r["seg"][seg]
            out.append((s["high_px"], +1))
            out.append((s["low_px"], -1))
    return [(p, s) for (p, s) in out if np.isfinite(p)]


def rest_targets(r, seg, minutes):
    _oh, _ol, rh, rl = r["orr"][(seg, minutes)]
    return [(p, s) for (p, s) in ((rh, +1), (rl, -1)) if np.isfinite(p)]


def score_family(asset, rows, levels, fam, target):
    """Per-era capture / displaced-null / lift / distance / marginal.

    DENOMINATOR LAW: an extreme is SCORED only where the family actually
    declares a compatible-side level for that session (P6 fires only on gap
    sessions; P1 only once its trailing calibration exists).  capture and its
    displaced null share that denominator, so the lift is honest.  The
    ADDITIVITY number (spec 3(f)) is instead expressed over EVERY realized
    extreme of the target (`n_all`) - what generation would actually gain.
    """
    mult = C.ASSETS[asset]["mult"]
    acc = {}

    def A(era):
        return acc.setdefault(era, {"n": 0, "hit": 0, "hitn": 0, "d": [],
                                    "da": [], "unc_hit": 0, "n_all": 0,
                                    "unc_all": 0})

    for i, r in enumerate(rows):
        atr = r["atr"]
        if not (np.isfinite(atr) and atr > 0):
            continue
        tol = tol_px_of(asset, atr)
        atr_px = atr / mult
        led = r["ledger"]
        ls = levels[i]
        if ls is None:
            prices = np.zeros(0, dtype=np.float64)
            sides = np.zeros(0, dtype=np.int64)
        else:
            prices, sides = ls.arrays()
        null_prices = displaced(prices, atr_px)
        if target.startswith(TGT_REST):
            seg = target.split("|", 1)[1]
            mn = int(fam[len("P3_OR"):]) if fam.startswith("P3_OR") \
                else P3_OR_MIN[0]
            tps = rest_targets(r, seg, mn)
        else:
            tps = target_pairs(r, target)
        eras = [e for e in M.eras_of(r["year"]) if e != M.ERA_ALL]
        for (tp, side) in tps:
            cov = bool(led.size and float(np.abs(led - tp).min()) <= tol)
            md, hit = _hit(prices, sides, tp, side, tol)
            _mdn, hitn = _hit(null_prices, sides, tp, side, tol)
            applicable = np.isfinite(md)
            for era in eras:
                a = A(era)
                a["n_all"] += 1
                if not cov:
                    a["unc_all"] += 1
                if not applicable:
                    continue
                a["n"] += 1
                a["hit"] += int(hit)
                a["hitn"] += int(hitn)
                a["d"].append(md * mult)
                a["da"].append(md * mult / atr)
                if not cov:
                    a["unc_hit"] += int(hit)
    out = {}
    for era, a in acc.items():
        n, n_all = a["n"], a["n_all"]
        if n == 0 or n_all == 0:
            continue
        cap = a["hit"] / n
        nul = a["hitn"] / n
        out[era] = {"n": n, "n_all": n_all, "applicable": n / n_all,
                    "hit": a["hit"], "capture": cap,
                    "hit_null": a["hitn"], "null_capture": nul,
                    "lift": (cap / nul) if nul > 0 else float("nan"),
                    "med_dist_usd": float(np.median(a["d"])),
                    "med_dist_atr": float(np.median(a["da"])),
                    "n_uncovered": a["unc_all"],
                    "n_uncovered_hit": a["unc_hit"],
                    "marginal_pp": a["unc_hit"] / n_all,
                    "kept_cover": 1.0 - a["unc_all"] / n_all}
    return out


def calibration_rows(asset, rows, levels_by_q, fam, target):
    """Coverage of each per-side quantile band vs its nominal q (spec §3c)."""
    outs = []
    for qi, q in enumerate(P1_SIDE_Q if fam.startswith("P1_SIDE")
                           else B2.LADDER_Q):
        for side, name in ((+1, "UP"), (-1, "DN")):
            acc = {}
            for i, r in enumerate(rows):
                lv = levels_by_q[i].get((qi, side)) if levels_by_q[i] else None
                if lv is None or not np.isfinite(lv):
                    continue
                tps = target_pairs(r, target)
                for (tp, s) in tps:
                    if s != side:
                        continue
                    inside = (tp <= lv) if side > 0 else (tp >= lv)
                    for era in M.eras_of(r["year"]):
                        if era == M.ERA_ALL:
                            continue
                        a = acc.setdefault(era, [0, 0])
                        a[0] += 1
                        a[1] += int(inside)
            for era in sorted(acc):
                n, k = acc[era]
                if n == 0:
                    continue
                cov = k / n
                outs.append([asset, fam, target, name, "%.2f" % q, era, n,
                             cov, q, abs(cov - q)])
    return outs


# ======================================================== the driver =========
def p1_calibrations(asset, rows, fc):
    """Trailing per-side excursion-ratio quantiles for the three P1 anchors."""
    spec = C.ASSETS[asset]
    mult = spec["mult"]
    n = len(rows)
    cal = {}
    specs = [("P1_SIDE_SETTLE", "SESSION", "settle"),
             ("P1_SIDE_SOPEN", "SESSION", "open")]
    specs += [("P1_SIDE_POPEN", seg, "open") for seg in PHASE_SEGMENTS]
    for fam, seg, anchor_kind in specs:
        up = np.full(n, np.nan)
        dn = np.full(n, np.nan)
        for i, r in enumerate(rows):
            s = r["seg"][seg]
            sig = fnum(fc.get((r["trade_date"], seg)), "sigma_hat_usd")
            if not (np.isfinite(sig) and sig > 0):
                continue
            if anchor_kind == "settle":
                a = rows[i - 1]["seg"]["SESSION"]["close_px"] if i else float("nan")
            else:
                a = s["open_px"]
            h, l = s["high_px"], s["low_px"]
            if not (np.isfinite(a) and np.isfinite(h) and np.isfinite(l)):
                continue
            up[i] = max(h - a, 0.0) * mult / sig
            dn[i] = max(a - l, 0.0) * mult / sig
        cal[(fam, seg)] = {"up": trailing_quantiles(up, P1_SIDE_Q),
                           "dn": trailing_quantiles(dn, P1_SIDE_Q),
                           "ratio_up": up, "ratio_dn": dn}
    return cal


def _p1_side_level_index(asset, rows, fc, p1cal, fam, seg, anchor_kind):
    """{i: {(qi, side): price}} — the per-q levels, for the calibration table."""
    mult = C.ASSETS[asset]["mult"]
    out = []
    for i, r in enumerate(rows):
        sig = fnum(fc.get((r["trade_date"], seg)), "sigma_hat_usd")
        if anchor_kind == "settle":
            a = rows[i - 1]["seg"]["SESSION"]["close_px"] if i else float("nan")
        else:
            a = r["seg"][seg]["open_px"]
        d = {}
        if np.isfinite(sig) and sig > 0 and np.isfinite(a):
            cal = p1cal[(fam, seg)]
            for qi, _q in enumerate(P1_SIDE_Q):
                u, v = cal["up"][i, qi], cal["dn"][i, qi]
                if np.isfinite(u):
                    d[(qi, +1)] = a + u * sig / mult
                if np.isfinite(v):
                    d[(qi, -1)] = a - v * sig / mult
        out.append(d)
    return out


def pinball(y, pred, q=0.5):
    y = np.asarray(y, dtype=np.float64)
    pred = np.asarray(pred, dtype=np.float64)
    m = np.isfinite(y) & np.isfinite(pred)
    if not m.any():
        return float("nan"), 0
    e = y[m] - pred[m]
    v = np.where(e >= 0, q * e, (q - 1.0) * e)
    return float(np.mean(v)), int(m.sum())


def run(assets=C.ASSET_ORDER, workers=3):
    verify_hl_spec()
    phash = C.params_hash(PARAMS)
    M.hb("hl census start (spec %s, params %s)" % (HL_SPEC_SHA16, phash[:12]))

    fam_rows, cal_rows, marg_rows, conf_rows, over_rows, p2_rows = \
        [], [], [], [], [], []
    sanity_rows = []
    decisions = {}

    # Pass A (receipt reads) runs one worker per asset — the D-054 threshold of
    # session k depends on sessions < k, so it is sequential WITHIN an asset.
    nw = max(1, min(int(workers), len(assets)))
    if nw > 1:
        pool = mp.Pool(nw)
        try:
            facts = dict(zip(assets, pool.map(build_facts, list(assets))))
        finally:
            pool.close()
            pool.join()
    else:
        facts = {a: build_facts(a) for a in assets}

    for asset in assets:
        allrows = facts[asset]
        for r in allrows:
            r["asset"] = asset
        fc = load_forecasts(asset)
        spec = C.ASSETS[asset]
        tick_px = spec["tick_px"]

        # -- D-054 impact / sanity accounting (over EVERY receipt) ----------
        for era in ERAS:
            sel = [r for r in allrows if era in M.eras_of(r["year"])]
            if not sel:
                continue
            sanity_rows.append([
                asset, era, len(sel),
                float(np.mean([r["insane_frac"] for r in sel])),
                float(np.median([r["insane_frac"] for r in sel])),
                int(sum(1 for r in sel if r["n_sane"] == 0)),
                int(sum(1 for r in sel if r["degenerate"])),
                float(np.median([r["thr_all_usd"] for r in sel])),
                float(np.median([r["ledger"].size for r in sel]))])

        # Degenerate receipts are dropped BEFORE anything reads a prior
        # session, so `rows[i-1]` is always the previous REAL session (the
        # b3_levels.load_v1_history convention).
        rows = [r for r in allrows if not r["degenerate"]]

        # -- P5 overshoot fit (FIT era, per asset) --------------------------
        up_s, dn_s = overshoot_samples(rows, set(M.FIT_YEARS))
        p5deltas = {"up": overshoot_deltas(up_s, tick_px),
                    "dn": overshoot_deltas(dn_s, tick_px)}
        for side, samp, dd in (("UP", up_s, p5deltas["up"]),
                               ("DN", dn_s, p5deltas["dn"])):
            over_rows.append([asset, side, int(samp.size),
                              float(np.median(samp)) * spec["mult"]
                              if samp.size else float("nan")]
                             + [dd[q] * spec["mult"] for q in P5_DELTA_Q]
                             + [dd[q] for q in P5_DELTA_Q])

        # -- P1 calibrations, P2 walk-forward -------------------------------
        p1cal = p1_calibrations(asset, rows, fc)
        p2pred = p2_walkforward(rows, fc)

        # -- P2 pinball verdict ---------------------------------------------
        for era in ERAS:
            sel = np.array([era in M.eras_of(r["year"]) for r in rows])
            y = np.where(sel, p2pred["y"], np.nan)
            base, nb = pinball(y, np.where(sel, p2pred["uncond"], np.nan))
            for model in ("ols", "logit"):
                pl, nn = pinball(y, np.where(sel, p2pred[model], np.nan))
                p2_rows.append([asset, era, model.upper(), nn, pl, base,
                                (base - pl), int(np.isfinite(pl) and
                                                 np.isfinite(base) and
                                                 pl < base)])

        # -- build every family's levels ------------------------------------
        levels = build_family_levels(asset, rows, fc, p1cal, p2pred, p5deltas)

        # -- score ----------------------------------------------------------
        per_fam = {}
        for (fam, target) in sorted(levels):
            res = score_family(asset, rows, levels[(fam, target)], fam, target)
            per_fam[(fam, target)] = res
            for era in ERAS:
                if era not in res:
                    continue
                v = res[era]
                fam_rows.append([asset, fam, target, era, v["n"], v["n_all"],
                                 v["applicable"], v["hit"], v["capture"],
                                 v["hit_null"], v["null_capture"], v["lift"],
                                 v["med_dist_usd"], v["med_dist_atr"],
                                 v["n_uncovered"], v["n_uncovered_hit"],
                                 v["marginal_pp"], v["kept_cover"]])
                marg_rows.append([asset, fam, target, era, v["n_all"],
                                  v["n_uncovered"], v["n_uncovered_hit"],
                                  v["marginal_pp"], v["kept_cover"],
                                  v["kept_cover"] + v["marginal_pp"]])

        # -- adoption decisions ---------------------------------------------
        for (fam, target), res in sorted(per_fam.items()):
            fit = res.get(M.ERA_FIT)
            if not fit:
                continue
            years = [res[str(y)]["lift"] for y in sorted(M.FIT_YEARS)
                     if str(y) in res]
            stable = bool(years) and all(np.isfinite(v) and v > 1.0
                                         for v in years)
            ok_lift = np.isfinite(fit["lift"]) and fit["lift"] >= LIFT_MIN
            ok_marg = fit["marginal_pp"] >= MARGINAL_MIN_PP
            decisions[(asset, fam, target)] = {
                "lift": fit["lift"], "marginal_pp": fit["marginal_pp"],
                "stable": stable,
                "adopt": bool(ok_lift and ok_marg and stable),
                "capture": fit["capture"], "null": fit["null_capture"],
                "n": fit["n"], "n_all": fit["n_all"], "years": years}

        # -- calibration table (P1 families) --------------------------------
        for fam, seg, kind in (("P1_SIDE_SETTLE", "SESSION", "settle"),
                               ("P1_SIDE_SOPEN", "SESSION", "open")):
            idx = _p1_side_level_index(asset, rows, fc, p1cal, fam, seg, kind)
            cal_rows.extend(calibration_rows(asset, rows, idx, fam,
                                             TGT_SESSION))
        # phase-open calibration, pooled over the three phases
        for seg in PHASE_SEGMENTS:
            idx = _p1_side_level_index(asset, rows, fc, p1cal,
                                       "P1_SIDE_POPEN", seg, "open")
            per = []
            for i, r in enumerate(rows):
                per.append(idx[i])
            cal_rows.extend(_phase_cal_rows(asset, rows, per, seg))
        # P2 coverage of the predicted H (nominal 0.5 — a median prediction)
        for model, key in (("P2_OLS", "ols"), ("P2_LOGIT", "logit"),
                           ("P2_UNCOND", "uncond")):
            cal_rows.extend(_p2_cal_rows(asset, rows, p2pred, model, key))

        # -- P7 confluence ---------------------------------------------------
        conf_rows.extend(confluence_census(asset, rows, levels))
        M.hb("hl scored %s (%d families)" % (asset, len(levels)))

    _write_all(phash, fam_rows, cal_rows, marg_rows, conf_rows, over_rows,
               p2_rows, sanity_rows, decisions)
    return decisions


def _phase_cal_rows(asset, rows, idx, seg):
    outs = []
    for qi, q in enumerate(P1_SIDE_Q):
        for side, name in ((+1, "UP"), (-1, "DN")):
            acc = {}
            for i, r in enumerate(rows):
                lv = idx[i].get((qi, side))
                if lv is None or not np.isfinite(lv):
                    continue
                s = r["seg"][seg]
                tp = s["high_px"] if side > 0 else s["low_px"]
                if not np.isfinite(tp):
                    continue
                inside = (tp <= lv) if side > 0 else (tp >= lv)
                for era in M.eras_of(r["year"]):
                    if era == M.ERA_ALL:
                        continue
                    a = acc.setdefault(era, [0, 0])
                    a[0] += 1
                    a[1] += int(inside)
            for era in sorted(acc):
                n, k = acc[era]
                if n:
                    outs.append([asset, "P1_SIDE_POPEN", "PHASE_HL|%s" % seg,
                                 name, "%.2f" % q, era, n, k / n, q,
                                 abs(k / n - q)])
    return outs


def _p2_cal_rows(asset, rows, p2pred, fam, key):
    mult = C.ASSETS[asset]["mult"]
    outs = []
    for side, name in ((+1, "UP"), (-1, "DN")):
        acc = {}
        for i, r in enumerate(rows):
            u = p2pred[key][i]
            s = r["seg"]["SESSION"]
            o, h, l = s["open_px"], s["high_px"], s["low_px"]
            if not (np.isfinite(u) and np.isfinite(o) and np.isfinite(h)
                    and np.isfinite(l)):
                continue
            rng = h - l
            tp = h if side > 0 else l
            lv = o + u * rng if side > 0 else o - (1.0 - u) * rng
            # coverage of the SPLIT itself (range held fixed at realized):
            inside = (tp <= lv) if side > 0 else (tp >= lv)
            for era in M.eras_of(r["year"]):
                if era == M.ERA_ALL:
                    continue
                a = acc.setdefault(era, [0, 0])
                a[0] += 1
                a[1] += int(inside)
        for era in sorted(acc):
            n, k = acc[era]
            if n:
                outs.append([asset, fam, TGT_SESSION, name, "0.50", era, n,
                             k / n, 0.5, abs(k / n - 0.5)])
    return outs


def confluence_census(asset, rows, levels):
    """P7: do realized extremes land in the top-k confluence zones?"""
    mult = C.ASSETS[asset]["mult"]
    acc = {}
    for i, r in enumerate(rows):
        atr = r["atr"]
        if not (np.isfinite(atr) and atr > 0):
            continue
        tol = tol_px_of(asset, atr)
        atr_px = atr / mult
        px, fam = [], []
        led = r["ledger"]
        if led.size:
            px.extend(led.tolist())
            fam.extend(["LEDGER"] * led.size)
        for (f, target) in sorted(levels):
            if target != TGT_SESSION:
                continue
            ls = levels[(f, target)][i]
            if ls is None:
                continue
            p, _s = ls.arrays()
            px.extend(p.tolist())
            fam.extend([f] * p.size)
        if not px:
            continue
        centres, scores = confluence_zones(np.array(px), np.array(fam), tol)
        if centres.size == 0:
            continue
        null_c = displaced(centres, atr_px)
        s = r["seg"]["SESSION"]
        for tp in (s["high_px"], s["low_px"]):
            if not np.isfinite(tp):
                continue
            for k in P7_TOPK:
                c = centres[:k]
                nc = null_c[:k]
                hit = bool(c.size and float(np.abs(c - tp).min()) <= tol)
                hitn = bool(nc.size and float(np.abs(nc - tp).min()) <= tol)
                for era in M.eras_of(r["year"]):
                    if era == M.ERA_ALL:
                        continue
                    a = acc.setdefault((era, k), [0, 0, 0, 0])
                    a[0] += 1
                    a[1] += int(hit)
                    a[2] += int(hitn)
                    a[3] += int(scores[0])
    out = []
    for (era, k) in sorted(acc):
        if era not in ERAS:
            continue
        n, h, hn, ssum = acc[(era, k)]
        if not n:
            continue
        cap, nul = h / n, hn / n
        out.append([asset, era, k, n, h, cap, hn, nul,
                    (cap / nul) if nul > 0 else float("nan"), ssum / n])
    return out


# ============================================================= writers =======
def _write_all(phash, fam_rows, cal_rows, marg_rows, conf_rows, over_rows,
               p2_rows, sanity_rows, decisions):
    W = write_tsv
    W(out_path("hl_families.tsv"), SECTION, phash,
      ["asset", "family", "target", "era", "n_scored", "n_extremes",
       "applicable_frac", "n_hit", "capture", "n_hit_null", "null_capture",
       "lift", "med_dist_usd", "med_dist_atr", "n_uncovered_by_kept",
       "n_uncovered_hit", "marginal_pp", "kept_ledger_cover"], fam_rows,
      extra=[PARAMS["tolerance"], PARAMS["null"], PARAMS["mid_sane"],
             "n_scored = extremes where the family declares a compatible-side "
             "level (capture/null denominator); n_extremes = ALL realized "
             "extremes of the target (marginal_pp denominator)"])
    W(out_path("hl_calibration.tsv"), SECTION + " (c) calibration", phash,
      ["asset", "family", "target", "side", "q", "era", "n", "coverage",
       "nominal", "abs_err"], cal_rows)
    W(out_path("hl_marginal.tsv"), SECTION + " (f) marginal value", phash,
      ["asset", "family", "target", "era", "n_extremes",
       "n_uncovered_by_kept", "n_uncovered_hit", "marginal_pp",
       "kept_ledger_cover", "union_cover_after"], marg_rows)
    W(out_path("hl_confluence.tsv"), SECTION + " P7 confluence", phash,
      ["asset", "era", "topk", "n_extremes", "n_hit", "capture", "n_hit_null",
       "null_capture", "lift", "mean_top_zone_score"], conf_rows,
      extra=[PARAMS["p7"]])
    W(out_path("hl_overshoot.tsv"), SECTION + " P5 overshoot fit", phash,
      ["asset", "side", "n_samples", "median_usd"]
      + ["delta_usd_q%02d" % int(q * 100) for q in P5_DELTA_Q]
      + ["delta_px_q%02d" % int(q * 100) for q in P5_DELTA_Q], over_rows,
      extra=[PARAMS["p5"]])
    W(out_path("hl_p2_pinball.tsv"), SECTION + " P2 conditional split", phash,
      ["asset", "era", "model", "n", "pinball_q50", "pinball_q50_uncond",
       "improvement", "beats_uncond"], p2_rows,
      extra=[PARAMS["p2_design"], PARAMS["p2_null"]])
    W(out_path("hl_midsane.tsv"), SECTION + " D-054 mask accounting", phash,
      ["asset", "era", "n_receipts", "mean_insane_frac", "median_insane_frac",
       "n_receipts_zero_sane", "n_receipts_degenerate", "median_threshold_usd",
       "median_kept_ledger_levels"], sanity_rows,
      extra=[PARAMS["mid_sane"]])
    drows = []
    for (asset, fam, target), d in sorted(decisions.items()):
        drows.append([asset, fam, target, d["n"], d["n_all"], d["capture"],
                      d["null"], d["lift"], d["marginal_pp"], int(d["stable"]),
                      "ADOPT" if d["adopt"] else "REJECT",
                      " ".join("%.3f" % v for v in d["years"])])
    W(out_path("hl_adoption.tsv"), SECTION + " pre-registered adoption rule",
      phash, ["asset", "family", "target", "n_scored_fit", "n_extremes_fit",
              "capture_fit", "null_fit", "lift_fit", "marginal_pp_fit",
              "year_lift_stable", "decision", "per_year_lifts"], drows,
      extra=[PARAMS["adoption"]])
    M.write_json(out_path("hl_census.receipt.json"), env_receipt())
    write_report(phash)


# ============================================================== report =======
DEFECTS = (
    ("§2 P1 names per-side quantiles but no per-side calibration target",
     "The frozen fvol ladder calibrates ONE ratio, realized RANGE / sigma_hat "
     "(symmetric about the anchor), while P1 asks for q in {0.5,0.75,0.9,0.95} "
     "PER SIDE.  LANE ACTION: the same trailing-250 machinery "
     "(b2_fvol.ladder semantics, strictly prior, >= 30 observations) is "
     "applied to the ONE-SIDED excursion ratios (H - anchor)/sigma_hat and "
     "(anchor - L)/sigma_hat; the existing symmetric ladder is carried "
     "unchanged as the P1_BASE / P1_BASE_RS baselines the spec calls for."),
    ("D-054 does not define the window of 'trailing-phase-median spread'",
     "LANE ACTION: the median of the same phase's per-session median "
     "two-sided spread over the 20 STRICTLY PRIOR sessions, requiring >= 5 "
     "observations; with fewer, only the $500 cap binds.  Strictly prior by "
     "construction, so a session never licenses its own mask, and the mask is "
     "computable live.  Declared in the receipt params."),
    ("§2 P7 leaves k unspecified in 'top-k confluence zones'",
     "LANE ACTION: k in {1,3,5} are all reported; no verdict rests on a "
     "chosen k."),
    ("§3 gives no denominator rule for families that do not fire every session",
     "P6 fires only on gap sessions, P1 only after its calibration warms up, "
     "and one-sided families declare nothing for the opposite extreme.  "
     "LANE ACTION: capture and its displaced null share a denominator of the "
     "extremes where the family DECLARES a compatible-side level "
     "(`n_scored`, with `applicable_frac` reported beside it), so the lift is "
     "honest; the additivity number (§3f) uses ALL realized extremes of the "
     "target (`n_extremes`), which is what generation would actually gain."),
    ("§2 P2 says 'OLS/logistic' without choosing",
     "LANE ACTION: both are fitted and reported (P2_OLS, P2_LOGIT), each "
     "against the same unconditional-split null."),
    ("§2 P5 fits the overshoot distribution on FIT and is then tested on FIT",
     "The spec orders exactly that sequence.  The P5 deltas are therefore "
     "IN-SAMPLE on the FIT era; the 2025 echo (deltas frozen from FIT) is the "
     "only out-of-sample reading of P5 in this census."),
    ("§1 asks for phase H/L 'from the frozen phase tables', which carry three "
     "phases",
     "The frozen m0 table partitions the session into TOKYO/LONDON/NY only "
     "(m0 SPEC_DEFECTS D5).  LANE ACTION: the phase targets are those three; "
     "no fourth phase was invented."),
    ("DATA DEFECT: frozen-quote receipts (m0 SPEC_DEFECTS D8)",
     "Receipts whose SANE session range is exactly $0 are frozen quotes, not "
     "sessions.  LANE ACTION: dropped before any target, anchor or "
     "prior-session read - the same exclusion b2_fvol and b3_levels already "
     "apply.  Counts per asset and era in hl_midsane.tsv."),
    ("The KEPT-family list predates the D-053 ledger",
     "§2 P7 and §3(f) need the KEPT families of the §6b relevance census, "
     "which was computed on m1/levels (the superseded VWAP bands), while the "
     "level prices are read from the D-053 ledger m1/levels_v2.  LANE ACTION: "
     "KEEP/RETIRE decisions taken from generation/level_relevance.tsv (FIT "
     "rows), prices from levels_v2.  Only the VWAP family's band set differs "
     "between the two, and VWAP is KEPT on HG only."),
)


def _read_tsv(name):
    """[(line_no, {col: value})] for a census TSV (line_no is 1-based)."""
    path = out_path(name)
    cols, out = None, []
    with open(path) as fh:
        for ln, line in enumerate(fh, start=1):
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            out.append((ln, dict(zip(cols, f))))
    return out


def _f(r, k):
    v = r.get(k, "")
    try:
        return float(v) if v != "" else float("nan")
    except ValueError:
        return float("nan")


def _esc(v):
    """Target keys carry '|' (REST_OF_WINDOW|NY) — escape it for markdown."""
    return str(v).replace("|", "\\|")


def write_report(phash):
    """HL_CENSUS_REPORT.md — every number carries its TSV file:line."""
    L = []
    A = L.append
    A("# HL_CENSUS_REPORT — day-high/low prediction census")
    A("")
    A("Spec: design/PORT_HL_CENSUS_SPEC.md (sha16 %s), FROZEN. Census type: "
      "EXPLORATORY, non-certifying. FIT era = %s; %s echoed separately; 2026 "
      "sealed and never opened." % (HL_SPEC_SHA16, M.ERA_FIT, M.ERA_GATE))
    A("params_hash=%s" % phash)
    A("")
    A("All targets and all mid reads apply the D-054 / CC-M1-4 MID-SANE mask "
      "(%s)." % PARAMS["mid_sane"])
    A("")

    # ---- 0. outcome ----
    ad0 = _read_tsv("hl_adoption.tsv")
    fams = sorted(set(r["family"] for _ln, r in ad0))
    A("## 0. Outcome")
    A("")
    A("| family | assets where the rule is met | verdict |")
    A("|---|---|---|")
    for f in fams:
        who = sorted(set("%s %s" % (r["asset"], r["target"])
                         for _ln, r in ad0
                         if r["family"] == f and r["decision"] == "ADOPT"))
        A("| %s | %s | %s |" % (f, _esc(", ".join(who)) or "none",
                                "ADOPT" if who else "REJECT"))
    A("")

    # ---- 1. adoption ----
    A("## 1. Pre-registered adoption rule (spec §3)")
    A("")
    A("Rule: lift >= %.1f AND marginal capture >= +%.0fpp AND per-FIT-year "
      "lift sign-stable (>1 in every FIT year). Source: "
      "hl_adoption.tsv." % (LIFT_MIN, MARGINAL_MIN_PP * 100))
    A("")
    ad = _read_tsv("hl_adoption.tsv")
    adopted = [(ln, r) for (ln, r) in ad if r["decision"] == "ADOPT"]
    A("| asset | family | target | capture | null | lift | marginal_pp | "
      "year-stable | decision | file:line |")
    A("|---|---|---|---|---|---|---|---|---|---|")
    for (ln, r) in ad:
        A("| %s | %s | %s | %.3f | %.3f | %.3f | %.3f | %s | %s | "
          "hl_adoption.tsv:%d |"
          % (r["asset"], r["family"], _esc(r["target"]), _f(r, "capture_fit"),
             _f(r, "null_fit"), _f(r, "lift_fit"), _f(r, "marginal_pp_fit"),
             r["year_lift_stable"], r["decision"], ln))
    A("")
    A("ADOPTED: %d of %d (family, target, asset) rows."
      % (len(adopted), len(ad)))
    A("")

    # ---- 2. per-family scores ----
    A("## 2. Per-family scores, FIT era (spec §3 a/b/d/f)")
    A("")
    A("| asset | family | target | n_scored | n_extremes | capture | null | "
      "lift | med_dist_$ | med_dist_ATR | marginal_pp | kept_cover | "
      "file:line |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for (ln, r) in _read_tsv("hl_families.tsv"):
        if r["era"] != M.ERA_FIT:
            continue
        A("| %s | %s | %s | %s | %s | %.3f | %.3f | %.3f | %.0f | %.3f | "
          "%.3f | %.3f | hl_families.tsv:%d |"
          % (r["asset"], r["family"], _esc(r["target"]), r["n_scored"],
             r["n_extremes"], _f(r, "capture"), _f(r, "null_capture"),
             _f(r, "lift"), _f(r, "med_dist_usd"), _f(r, "med_dist_atr"),
             _f(r, "marginal_pp"), _f(r, "kept_ledger_cover"), ln))
    A("")
    A("### 2025 GATE echo (evaluation only, never a selection input)")
    A("")
    A("| asset | family | target | capture | null | lift | file:line |")
    A("|---|---|---|---|---|---|---|")
    for (ln, r) in _read_tsv("hl_families.tsv"):
        if r["era"] != M.ERA_GATE:
            continue
        A("| %s | %s | %s | %.3f | %.3f | %.3f | hl_families.tsv:%d |"
          % (r["asset"], r["family"], _esc(r["target"]), _f(r, "capture"),
             _f(r, "null_capture"), _f(r, "lift"), ln))
    A("")

    # ---- 3. era stability ----
    A("## 3. Per-FIT-year lift (spec §3e era stability)")
    A("")
    A("| asset | family | target | 2021 | 2022 | 2023 | 2024 | file:line |")
    A("|---|---|---|---|---|---|---|---|")
    byfam = {}
    for (ln, r) in _read_tsv("hl_families.tsv"):
        if r["era"] not in ("2021", "2022", "2023", "2024"):
            continue
        byfam.setdefault((r["asset"], r["family"], r["target"]), {})[r["era"]] \
            = (ln, _f(r, "lift"))
    for key in sorted(byfam):
        d = byfam[key]
        cells = []
        lns = []
        for y in ("2021", "2022", "2023", "2024"):
            if y in d:
                cells.append("%.2f" % d[y][1])
                lns.append(d[y][0])
            else:
                cells.append("-")
        A("| %s | %s | %s | %s | hl_families.tsv:%s |"
          % (key[0], key[1], _esc(key[2]), " | ".join(cells),
             ",".join(str(x) for x in lns)))
    A("")

    # ---- 4. calibration ----
    A("## 4. Quantile calibration (spec §3c)")
    A("")
    A("| asset | family | target | side | q | era | n | coverage | |err| | "
      "file:line |")
    A("|---|---|---|---|---|---|---|---|---|---|")
    for (ln, r) in _read_tsv("hl_calibration.tsv"):
        if r["era"] != M.ERA_FIT:
            continue
        A("| %s | %s | %s | %s | %s | %s | %s | %.3f | %.3f | "
          "hl_calibration.tsv:%d |"
          % (r["asset"], r["family"], _esc(r["target"]), r["side"], r["q"],
             r["era"], r["n"], _f(r, "coverage"), _f(r, "abs_err"), ln))
    A("")

    # ---- 5. P2 ----
    A("## 5. P2 conditional split vs the unconditional null (spec §2/§3)")
    A("")
    A("Pinball loss at q=0.5 on up_share = (H-open)/(H-L); lower is better. "
      "The unconditional null is the trailing median up_share.")
    A("")
    A("| asset | era | model | n | pinball | pinball_uncond | improvement | "
      "beats | file:line |")
    A("|---|---|---|---|---|---|---|---|---|")
    for (ln, r) in _read_tsv("hl_p2_pinball.tsv"):
        if r["era"] not in (M.ERA_FIT, M.ERA_GATE):
            continue
        A("| %s | %s | %s | %s | %.5f | %.5f | %+.5f | %s | "
          "hl_p2_pinball.tsv:%d |"
          % (r["asset"], r["era"], r["model"], r["n"], _f(r, "pinball_q50"),
             _f(r, "pinball_q50_uncond"), _f(r, "improvement"),
             r["beats_uncond"], ln))
    A("")

    # ---- 6. confluence ----
    A("## 6. P7 confluence (spec §2 P7)")
    A("")
    A("| asset | era | top-k | n | capture | null | lift | mean top-zone "
      "score | file:line |")
    A("|---|---|---|---|---|---|---|---|---|")
    for (ln, r) in _read_tsv("hl_confluence.tsv"):
        if r["era"] not in (M.ERA_FIT, M.ERA_GATE):
            continue
        A("| %s | %s | %s | %s | %.3f | %.3f | %.3f | %.2f | "
          "hl_confluence.tsv:%d |"
          % (r["asset"], r["era"], r["topk"], r["n_extremes"],
             _f(r, "capture"), _f(r, "null_capture"), _f(r, "lift"),
             _f(r, "mean_top_zone_score"), ln))
    A("")

    # ---- 7. P5 overshoot fit ----
    A("## 7. P5 overshoot distribution (FIT era, per asset)")
    A("")
    A("| asset | side | n | median_$ | d_p25_$ | d_p50_$ | d_p75_$ | "
      "file:line |")
    A("|---|---|---|---|---|---|---|---|")
    for (ln, r) in _read_tsv("hl_overshoot.tsv"):
        A("| %s | %s | %s | %.0f | %.0f | %.0f | %.0f | hl_overshoot.tsv:%d |"
          % (r["asset"], r["side"], r["n_samples"], _f(r, "median_usd"),
             _f(r, "delta_usd_q25"), _f(r, "delta_usd_q50"),
             _f(r, "delta_usd_q75"), ln))
    A("")

    # ---- 8. D-054 mask accounting ----
    A("## 8. D-054 MID-SANE mask accounting")
    A("")
    A("| asset | era | receipts | mean insane frac | median insane frac | "
      "zero-sane receipts | degenerate (frozen-quote) receipts | median "
      "threshold_$ | file:line |")
    A("|---|---|---|---|---|---|---|---|---|")
    for (ln, r) in _read_tsv("hl_midsane.tsv"):
        A("| %s | %s | %s | %.4f | %.4f | %s | %s | %.0f | "
          "hl_midsane.tsv:%d |"
          % (r["asset"], r["era"], r["n_receipts"],
             _f(r, "mean_insane_frac"), _f(r, "median_insane_frac"),
             r["n_receipts_zero_sane"], r["n_receipts_degenerate"],
             _f(r, "median_threshold_usd"), ln))
    A("")
    # ---- 8b. red-first evidence ----
    if os.path.exists(out_path("hl_redfirst.tsv")):
        A("## 8b. Red-first evidence (spec §4)")
        A("")
        A("Every mutant below is a committed broken implementation in "
          "engine/port_m1/test_hl.py; the real implementation is green on "
          "every case, and a mutant caught by nothing would be a test "
          "failure.")
        A("")
        A("| algorithm | mutant | cases broken | file:line |")
        A("|---|---|---|---|")
        for (ln, r) in _read_tsv("hl_redfirst.tsv"):
            A("| %s | %s | %s | hl_redfirst.tsv:%d |"
              % (r["algorithm"], r["mutant"], r["cases_broken"], ln))
        A("")

    # ---- 9. defects ----
    A("## 9. Spec defects and data defects (reported, not improvised around)")
    A("")
    for i, (title, body) in enumerate(DEFECTS, start=1):
        A("**H%d — %s.** %s" % (i, title, body))
        A("")
    A("Generated by engine/port_m1/hl_census.py.")
    A("")
    path = out_path("HL_CENSUS_REPORT.md")
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        fh.write("\n".join(L))
    os.replace(tmp, path)
    return path


# ============================================================== main =========
def main():
    args = sys.argv[1:]
    workers = 3
    assets = []
    i = 0
    while i < len(args):
        if args[i] == "--workers":
            workers = int(args[i + 1])
            i += 2
        else:
            assets.append(args[i])
            i += 1
    run(assets or list(C.ASSET_ORDER), workers=workers)
    M.hb("hl census done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
