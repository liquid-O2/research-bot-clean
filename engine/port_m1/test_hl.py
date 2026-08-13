#!/usr/bin/python3
"""PORT M1 — red-first self-tests for the H/L prediction census.

Spec §4 names two algorithms that did not exist before this lane and therefore
must be proven: the P7 CONFLUENCE CLUSTERING and the P5 OVERSHOOT FIT.  The
D-054 MID-SANE mask is proven too — it is the mask every target in the census
is measured through, so a silent bug there would corrupt every number.

RED-FIRST LAW (repo): a test counts only if it is shown to FAIL on a broken
implementation.  Every MUTANT below is a deliberately wrong version, committed
in this file; `test_mutants_are_caught` asserts each one breaks at least one
case the real implementation passes.  A mutant nothing catches is a FAILURE.

Run: /usr/bin/python3 engine/port_m1/test_hl.py
"""
import datetime as dt
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hl_census as H                     # noqa: E402
import census_common as X                 # noqa: E402
import b7_sane as B7S                     # noqa: E402
import common as C                        # noqa: E402

FAILURES = []


def check(name, got, want):
    if got != want:
        FAILURES.append("%s: got %r want %r" % (name, got, want))


def approx(a, b, eps=1e-9):
    if a is None or b is None:
        return a is b
    return abs(float(a) - float(b)) <= eps


# ==================================================================== P7 =====
# A level book with a deliberate structure (tol = 1.0 throughout):
#   10.0 10.5 11.0  -> a 3-level cluster centred at 10.5
#   20.0            -> a lone level
#   30.0 30.4 30.8 31.2 -> a 4-level chain; no single point covers all four
#   41.0 42.0       -> exactly tol apart: the BOUNDARY case (<= tol counts)
BOOK_PX = [10.0, 10.5, 11.0, 20.0, 30.0, 30.4, 30.8, 31.2, 41.0, 42.0]
BOOK_FAM = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
TOL = 1.0


def zones(fn=None, px=None, fam=None, tol=TOL):
    fn = fn or H.confluence_zones
    c, s = fn(np.array(px if px is not None else BOOK_PX, dtype=float),
              np.array(fam if fam is not None else BOOK_FAM), tol)
    return [(round(float(a), 6), int(b)) for a, b in zip(c, s)]


def case_p7_ranking(fn):
    """Top zone = the 4-level chain window, then the 3-level cluster."""
    z = zones(fn)
    return z[:3]


def case_p7_boundary(fn):
    """41.0 and 42.0 are EXACTLY tol apart -> each sees the other (score 2)."""
    return zones(fn, px=[41.0, 42.0], fam=["I", "J"])


def case_p7_dedupe(fn):
    """Two levels of the SAME family at the SAME price count ONCE."""
    return zones(fn, px=[5.0, 5.0, 5.0], fam=["A", "A", "B"])


def case_p7_merge(fn):
    """Zone centres within tol of a kept centre are merged away."""
    return zones(fn, px=[100.0, 100.1, 100.2, 100.3], fam=list("ABCD"))


def case_p7_empty(fn):
    return zones(fn, px=[], fam=[])


P7_CASES = (("ranking", case_p7_ranking, [(30.6, 4), (10.5, 3), (41.5, 2)]),
            ("boundary", case_p7_boundary, [(41.5, 2)]),
            ("dedupe", case_p7_dedupe, [(5.0, 2)]),
            ("merge", case_p7_merge, [(100.15, 4)]),
            ("empty", case_p7_empty, []))


# -------------------------------------------------------------- mutants -----
def MUT_P7_strict(prices, fams, tol):
    """MUTANT: neighbourhood uses STRICT < tol (loses the boundary case)."""
    prices = np.asarray(prices, dtype=np.float64)
    if prices.size == 0:
        return np.zeros(0), np.zeros(0, dtype=np.int64)
    fams = np.asarray(fams)
    order = np.lexsort((fams, prices))
    prices, fams = prices[order], fams[order]
    keep = np.ones(prices.size, dtype=bool)
    keep[1:] = ~((fams[1:] == fams[:-1]) & (prices[1:] == prices[:-1]))
    prices, fams = prices[keep], fams[keep]
    o2 = np.argsort(prices, kind="stable")
    prices, fams = prices[o2], fams[o2]
    lo = np.searchsorted(prices, prices - tol, side="right")   # <- strict
    hi = np.searchsorted(prices, prices + tol, side="left")    # <- strict
    score = (hi - lo).astype(np.int64)
    return _finish(prices, score, lo, hi, tol)


def MUT_P7_nodedupe(prices, fams, tol):
    """MUTANT: no (family, price) de-duplication — duplicates inflate scores."""
    prices = np.sort(np.asarray(prices, dtype=np.float64))
    if prices.size == 0:
        return np.zeros(0), np.zeros(0, dtype=np.int64)
    lo = np.searchsorted(prices, prices - tol, side="left")
    hi = np.searchsorted(prices, prices + tol, side="right")
    score = (hi - lo).astype(np.int64)
    return _finish(prices, score, lo, hi, tol)


def MUT_P7_nomerge(prices, fams, tol):
    """MUTANT: local maxima kept without merging neighbours within tol."""
    prices = np.asarray(prices, dtype=np.float64)
    if prices.size == 0:
        return np.zeros(0), np.zeros(0, dtype=np.int64)
    fams = np.asarray(fams)
    order = np.lexsort((fams, prices))
    prices, fams = prices[order], fams[order]
    keep = np.ones(prices.size, dtype=bool)
    keep[1:] = ~((fams[1:] == fams[:-1]) & (prices[1:] == prices[:-1]))
    prices = np.sort(prices[keep])
    lo = np.searchsorted(prices, prices - tol, side="left")
    hi = np.searchsorted(prices, prices + tol, side="right")
    score = (hi - lo).astype(np.int64)
    is_max = np.array([score[i] >= score[lo[i]:hi[i]].max()
                       for i in range(prices.size)])
    idx = np.nonzero(is_max)[0]
    rank = sorted(idx.tolist(), key=lambda i: (-int(score[i]),
                                               float(prices[i])))
    return (np.array([float(np.mean(prices[int(lo[i]):int(hi[i])]))
                      for i in rank]),
            np.array([score[i] for i in rank], dtype=np.int64))


def MUT_P7_priceorder(prices, fams, tol):
    """MUTANT: zones ranked by PRICE, not by score (top-k becomes arbitrary)."""
    c, s = H.confluence_zones(prices, fams, tol)
    o = np.argsort(c, kind="stable")
    return c[o], s[o]


def _finish(prices, score, lo, hi, tol):
    is_max = np.zeros(prices.size, dtype=bool)
    for i in range(prices.size):
        a, b = int(lo[i]), int(hi[i])
        if b <= a:
            is_max[i] = True
            continue
        nb = score[a:b]
        if score[i] < nb.max():
            continue
        ties = np.nonzero(nb == score[i])[0] + a
        if int(ties[0]) == i:
            is_max[i] = True
    cand = np.nonzero(is_max)[0]
    rank = sorted(cand.tolist(), key=lambda i: (-int(score[i]),
                                                float(prices[i])))
    centres, scores = [], []
    for i in rank:
        c = float(np.mean(prices[int(lo[i]):int(hi[i])])) if hi[i] > lo[i] \
            else float(prices[i])
        if any(abs(c - k) <= tol for k in centres):
            continue
        centres.append(c)
        scores.append(int(score[i]))
    return np.array(centres, dtype=np.float64), np.array(scores,
                                                         dtype=np.int64)


P7_MUTANTS = (("strict_tolerance", MUT_P7_strict),
              ("no_family_price_dedupe", MUT_P7_nodedupe),
              ("no_zone_merge", MUT_P7_nomerge),
              ("rank_by_price", MUT_P7_priceorder))


# ==================================================================== P5 =====
# Three sessions.  Session 1 supplies the prior extremes for session 2, etc.
# Only the SESSION segment is populated (the phase segments are NaN) so the
# expected overshoots are hand-checkable.
def _seg(h, l, o=None, c=None):
    d = {}
    for name in H.SEGMENTS:
        d[name] = {"open_px": float("nan"), "high_px": float("nan"),
                   "low_px": float("nan"), "close_px": float("nan"),
                   "n_sane": 0.0, "first_sec": float("nan"),
                   "last_sec": float("nan")}
    d["SESSION"]["high_px"] = h
    d["SESSION"]["low_px"] = l
    d["SESSION"]["open_px"] = o if o is not None else (h + l) / 2.0
    d["SESSION"]["close_px"] = c if c is not None else (h + l) / 2.0
    return d


#   s0: H=100, L=90
#   s1: H=104, L=88   -> up overshoot 104-100 = 4 ; dn overshoot 90-88 = 2
#   s2: H=103, L=89   -> H=103 does NOT exceed 104 -> NO up sample;
#                        L=89 does NOT go below 88 -> NO dn sample
#   s3: H=110, L=80   -> up 110-103 = 7 ; dn 89-80 = 9
P5_ROWS = [{"year": 2021, "seg": _seg(100.0, 90.0)},
           {"year": 2021, "seg": _seg(104.0, 88.0)},
           {"year": 2022, "seg": _seg(103.0, 89.0)},
           {"year": 2022, "seg": _seg(110.0, 80.0)}]
P5_FIT = {2021, 2022}


def case_p5_samples(fn):
    up, dn = fn(P5_ROWS, P5_FIT)
    return (sorted(round(float(v), 6) for v in up),
            sorted(round(float(v), 6) for v in dn))


def case_p5_era(fn):
    """FIT-era filter: restricting to 2022 keeps only the last two sessions."""
    up, dn = fn(P5_ROWS, {2022})
    return (sorted(round(float(v), 6) for v in up),
            sorted(round(float(v), 6) for v in dn))


P5_CASES = (("samples", case_p5_samples, ([4.0, 7.0], [2.0, 9.0])),
            ("era_filter", case_p5_era, ([7.0], [9.0])))


def MUT_P5_nearest_any(rows, fit_years):
    """MUTANT: nearest prior extreme by |distance|, exceeded or not."""
    up, dn = [], []
    for i, r in enumerate(rows):
        if r["year"] not in fit_years:
            continue
        h = r["seg"]["SESSION"]["high_px"]
        l = r["seg"]["SESSION"]["low_px"]
        ups, dns = H.prior_extremes(rows, i)
        if np.isfinite(h) and ups.size:
            up.append(float(h - ups[np.argmin(np.abs(ups - h))]))
        if np.isfinite(l) and dns.size:
            dn.append(float(dns[np.argmin(np.abs(dns - l))] - l))
    return np.array(up), np.array(dn)


def MUT_P5_unsigned(rows, fit_years):
    """MUTANT: absolute distance to the nearest prior extreme (sign dropped)."""
    up, dn = MUT_P5_nearest_any(rows, fit_years)
    return np.abs(up), np.abs(dn)


def MUT_P5_noncausal(rows, fit_years):
    """MUTANT: reads the CURRENT session's own extremes as 'prior' extremes."""
    up, dn = [], []
    for i, r in enumerate(rows):
        if r["year"] not in fit_years:
            continue
        h = r["seg"]["SESSION"]["high_px"]
        l = r["seg"]["SESSION"]["low_px"]
        ups = np.array([r["seg"][s]["high_px"] for s in H.SEGMENTS
                        if np.isfinite(r["seg"][s]["high_px"])])
        dns = np.array([r["seg"][s]["low_px"] for s in H.SEGMENTS
                        if np.isfinite(r["seg"][s]["low_px"])])
        if np.isfinite(h) and ups.size:
            b = np.sort(ups)
            b = b[b < h]
            if b.size:
                up.append(float(h - b[-1]))
        if np.isfinite(l) and dns.size:
            a = np.sort(dns)
            a = a[a > l]
            if a.size:
                dn.append(float(a[0] - l))
    return np.array(up), np.array(dn)


P5_MUTANTS = (("nearest_regardless_of_exceedance", MUT_P5_nearest_any),
              ("unsigned_distance", MUT_P5_unsigned),
              ("noncausal_same_session", MUT_P5_noncausal))


# ---- the delta quantiser (tick rounding) -----------------------------------
DELTA_SAMPLES = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0,
                          11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0,
                          19.0, 20.0, 21.0, 22.0, 23.0, 24.0, 25.0, 26.0,
                          27.0, 28.0, 29.0, 30.0])
DELTA_TICK = 0.5


def case_delta(fn):
    d = fn(DELTA_SAMPLES, DELTA_TICK)
    return [round(d[q], 6) for q in H.P5_DELTA_Q]


def case_delta_thin(fn):
    """Below the minimum observation count every non-zero delta is NaN."""
    d = fn(DELTA_SAMPLES[:5], DELTA_TICK)
    return [(0.0 if q == 0.0 else (None if not np.isfinite(d[q])
                                   else d[q])) for q in H.P5_DELTA_Q]


# percentiles of 1..30: p25 = 8.25 -> 8.5 half-up on a 0.5 grid;
# p50 = 15.5 -> 15.5 ; p75 = 22.75 -> 23.0
DELTA_CASES = (("quantiles", case_delta, [0.0, 8.5, 15.5, 23.0]),
               ("thin", case_delta_thin, [0.0, None, None, None]))


def MUT_DELTA_notick(samples, tick_px):
    """MUTANT: no tick rounding — deltas land off the price grid."""
    out = {}
    for q in H.P5_DELTA_Q:
        if q == 0.0:
            out[q] = 0.0
        elif samples.size < H.P1_CAL_MIN:
            out[q] = float("nan")
        else:
            out[q] = float(np.percentile(samples, q * 100.0))
    return out


def MUT_DELTA_nomin(samples, tick_px):
    """MUTANT: no minimum-observation guard — fits deltas off 5 points."""
    out = {}
    for q in H.P5_DELTA_Q:
        out[q] = 0.0 if q == 0.0 else X.round_half_up(
            float(np.percentile(samples, q * 100.0)), tick_px)
    return out


DELTA_MUTANTS = (("no_tick_rounding", MUT_DELTA_notick),
                 ("no_min_observations", MUT_DELTA_nomin))


# ================================================================ D-054 ======
# The mask itself belongs to engine/port_m1/b7_sane.py (the port's canonical
# D-054 implementation).  This lane does not reimplement it — but every number
# in the census is measured through it, so it is mutant-tested HERE too, from
# an independent set of cases.  What this lane DOES own is the threshold
# adapter (`H.session_thresholds`): the per-session lookup and the warm-up
# fallback to the $500 cap.
class _Sess(object):
    """Minimal session stub carrying only what the mask reads."""

    def __init__(self, spreads, phases, states=None):
        self.spread_usd = np.array(spreads, dtype=np.float64)
        self.phase_tag = np.array(phases, dtype=np.int8)
        self.n = self.spread_usd.size
        st = np.zeros(self.n, dtype=np.int8) if states is None \
            else np.array(states, dtype=np.int8)
        self.valid = (st == 0)
        self.mid = np.zeros(self.n)
        self.state = st


# phase 0 threshold $100 (10 x a $10 trailing median)
# phase 1 threshold $500 (the cap, which an $80 trailing median would exceed)
# phase 2 threshold $500 (warm-up: no trailing observation)
SANE_SESS = _Sess(spreads=[10.0, 99.0, 100.0, 101.0,
                           80.0, 499.0, 500.0, 501.0,
                           10.0, 400.0, 600.0, 20.0],
                  phases=[0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2],
                  states=[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1])
SANE_THR = np.array([100.0, 500.0, 500.0])


def case_sane(fn):
    return [int(v) for v in fn(SANE_SESS, SANE_THR)]


SANE_CASES = (("mask", case_sane,
               [1, 1, 1, 0,      # <= $100 sane, $101 insane
                1, 1, 1, 0,      # the cap is inclusive
                1, 1, 0, 0]),)   # $600 insane; last second not TWO_SIDED


def MUT_SANE_nocap(s, thr):
    """MUTANT: 10x the trailing median with NO $500 cap (phase 1 = $800)."""
    t = np.array([100.0, 800.0, 1e18])
    return (s.state == 0) & (s.spread_usd <= t[s.phase_tag])


def MUT_SANE_notwosided(s, thr):
    """MUTANT: spread test only — a one-sided book slips through."""
    t = np.asarray(thr, dtype=np.float64)[s.phase_tag]
    return np.isfinite(s.spread_usd) & (s.spread_usd <= t)


def MUT_SANE_strict(s, thr):
    """MUTANT: strict < instead of <= (drops the exact-threshold second)."""
    t = np.asarray(thr, dtype=np.float64)[s.phase_tag]
    return (s.state == 0) & np.isfinite(s.spread_usd) & (s.spread_usd < t)


SANE_MUTANTS = (("no_500_cap", MUT_SANE_nocap),
                ("two_sided_dropped", MUT_SANE_notwosided),
                ("strict_inequality", MUT_SANE_strict))


# ---- the threshold adapter this lane owns ---------------------------------
THR_TABLE = {20230601: [250.0, 300.0, 125.0]}


def case_thr_known(fn):
    return [float(v) for v in fn(THR_TABLE, dt.date(2023, 6, 1))]


def case_thr_missing(fn):
    """A date absent from the canonical table falls back to the cap alone."""
    return [float(v) for v in fn(THR_TABLE, dt.date(1999, 1, 1))]


THR_CASES = (("known_date", case_thr_known, [250.0, 300.0, 125.0]),
             ("warmup_fallback", case_thr_missing, [500.0, 500.0, 500.0]))


def MUT_THR_zero_default(table, trade_date):
    """MUTANT: missing date defaults to 0 — masks the whole session away."""
    v = table.get(M_d8(trade_date))
    return np.zeros(X.N_PHASES) if v is None else np.asarray(v, float)


def MUT_THR_inf_default(table, trade_date):
    """MUTANT: missing date defaults to no limit — the mask stops masking."""
    v = table.get(M_d8(trade_date))
    return np.full(X.N_PHASES, 1e18) if v is None else np.asarray(v, float)


def M_d8(d):
    return d.year * 10000 + d.month * 100 + d.day


THR_MUTANTS = (("missing_date_defaults_to_zero", MUT_THR_zero_default),
               ("missing_date_defaults_to_unbounded", MUT_THR_inf_default))


# ============================================================ trailing =======
def test_quantiles_are_strictly_prior():
    r = np.arange(1.0, 61.0)
    q = H.trailing_quantiles(r, (0.5,), window=1000, minobs=30)
    check("trailing_q/warmup_nan", bool(np.isnan(q[29, 0])), True)
    # row 30 sees rows 0..29 = values 1..30 -> median 15.5
    check("trailing_q/prior_only", approx(q[30, 0], 15.5), True)


def test_displaced_null():
    p = np.array([10.0, 20.0, 30.0])
    d = H.displaced(p, 2.0)
    check("null/alternating", [round(float(v), 6) for v in d],
          [11.0, 19.0, 31.0])


def test_hit_sides():
    px = np.array([100.0, 90.0])
    sd = np.array([1, -1])
    check("hit/side_up", H._hit(px, sd, 100.4, +1, 0.5)[1], True)
    check("hit/wrong_side_ignored", H._hit(px, sd, 90.1, +1, 0.5)[1], False)
    check("hit/side_dn", H._hit(px, sd, 90.1, -1, 0.5)[1], True)
    agn = np.array([0, 0])
    check("hit/agnostic_matches_both", H._hit(px, agn, 90.1, +1, 0.5)[1], True)
    check("hit/no_compatible_level",
          bool(np.isnan(H._hit(px, sd, 100.0, 0, 0.5)[0])), True)


def test_pinball():
    y = np.array([1.0, 2.0, 3.0])
    p = np.array([1.0, 1.0, 1.0])
    v, n = H.pinball(y, p, 0.5)
    check("pinball/value", approx(v, (0.0 + 0.5 + 1.0) / 3.0), True)
    check("pinball/n", n, 3)


def test_spec_pin():
    check("spec/sha16", H.verify_hl_spec(), H.HL_SPEC_SHA16)


# ========================================================== the runner =======
def run_group(title, cases, impl, mutants):
    """Green on the real implementation, then every mutant must break."""
    for (name, fn, want) in cases:
        got = fn(impl)
        check("%s/%s" % (title, name), got, want)
    caught = {}
    for (mname, mimpl) in mutants:
        broke = []
        for (name, fn, want) in cases:
            try:
                got = fn(mimpl)
            except Exception as exc:                        # noqa: BLE001
                broke.append("%s(raised %s)" % (name, type(exc).__name__))
                continue
            if got != want:
                broke.append(name)
        caught[mname] = broke
        if not broke:
            FAILURES.append("%s: MUTANT %s caught by NOTHING (red-first law)"
                            % (title, mname))
    return caught


def main():
    test_spec_pin()
    test_quantiles_are_strictly_prior()
    test_displaced_null()
    test_hit_sides()
    test_pinball()

    red = {}
    red["P7_confluence"] = run_group("P7", P7_CASES, H.confluence_zones,
                                     P7_MUTANTS)
    red["P5_overshoot"] = run_group("P5", P5_CASES, H.overshoot_samples,
                                    P5_MUTANTS)
    red["P5_delta_fit"] = run_group("P5delta", DELTA_CASES,
                                    H.overshoot_deltas, DELTA_MUTANTS)
    red["D054_mid_sane"] = run_group("D054", SANE_CASES, B7S.sane_mask,
                                     SANE_MUTANTS)
    red["D054_threshold_adapter"] = run_group("THR", THR_CASES,
                                              H.session_thresholds,
                                              THR_MUTANTS)

    print("RED-FIRST EVIDENCE (mutant -> cases it breaks):")
    rows = []
    for group in sorted(red):
        for mname in sorted(red[group]):
            broke = red[group][mname]
            print("  %-14s %-34s %s" % (group, mname,
                                        ",".join(broke) or "NONE"))
            rows.append([group, mname, len(broke), ",".join(broke) or "NONE"])
    if not FAILURES:
        H.write_tsv(H.out_path("hl_redfirst.tsv"),
                    "§4 red-first mutant evidence",
                    C.params_hash({"tests": "engine/port_m1/test_hl.py"}),
                    ["algorithm", "mutant", "n_cases_broken", "cases_broken"],
                    rows,
                    extra=["a mutant caught by NO case is a test FAILURE "
                           "(red-first law); the real implementation is green "
                           "on every case listed"])
    if FAILURES:
        print("\nFAILURES (%d):" % len(FAILURES))
        for f in FAILURES:
            print("  " + f)
        return 1
    print("\nALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
