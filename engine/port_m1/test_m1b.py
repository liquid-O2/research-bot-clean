#!/usr/bin/python3
"""PORT M1.B S1 — red-first self-tests for the CC-M1-3 generation logic.

Covered (the algorithms that did not exist before this stage):
  (a) the G1-FAST-OPEN window + delay switching   (b8.in_fast_open,
      b8.g1_emissions)                             <- the brief's named case
  (b) the G2-RECLAIM 30-min completion bound      (b8.reclaim_within_bound)
  (c) the retired-level-source filter             (b8.KEPT_LEVEL_FAMILIES)
  (d) the NEWS_UNTRADEABLE leg class              (b8.is_news_untradeable)
  (e) the D-054 MID-SANITY mask                   (b7_sane.thresholds_from,
      b7_sane.sane_mask)

RED-FIRST LAW (repo): a test counts only if it is shown to FAIL on a broken
implementation.  Every MUTANT below is a deliberately wrong version, committed
in this file; `test_mutants_are_caught` asserts each one breaks at least one
case the real implementation passes.  A mutant nothing catches is a FAILURE.

Run: /usr/bin/python3 engine/port_m1/test_m1b.py
"""
import bisect
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m1_common as M
import b7_sane as SN
import b8_generation_v2 as G

FAILURES = []


def check(name, got, want):
    if got != want:
        FAILURES.append("%s: got %r want %r" % (name, got, want))


class _S(object):
    """Minimal session stub: only phase_tag is read by phase_open_secs."""

    def __init__(self, segs):
        t = []
        for v, n in segs:
            t.extend([v] * n)
        self.phase_tag = np.array(t, dtype=np.int8)


# ============================================ (a) the FAST-OPEN window ========
# A session of three phases: TOKYO [0,1000), LONDON [1000,2000), NY [2000,3000).
SESS = _S([(0, 1000), (1, 1000), (2, 1000)])
OPENS = [0, 1000, 2000]

# (conf_sec, expected in-window?) — the boundary cases are the point
CASES_W = ((0, True),         # the session/first-phase open itself
           (1, True),
           (299, True),       # last second of the window
           (300, False),      # exactly 300s after the open is OUTSIDE
           (301, False),
           (999, False),
           (1000, True),      # the LONDON open re-opens a window
           (1299, True),
           (1300, False),
           (2000, True),      # the NY open too
           (2299, True),
           (2300, False))


def test_phase_open_secs():
    check("phase_open_secs", G.phase_open_secs(SESS), OPENS)
    # a session that never changes phase still has its open at second 0
    check("phase_open_secs.single", G.phase_open_secs(_S([(1, 50)])), [0])


def test_in_fast_open():
    for (sec, want) in CASES_W:
        check("in_fast_open[%d]" % sec, G.in_fast_open(sec, OPENS), want)


# ---- delay switching: inside the window a confirmation emits BOTH candidates
CONFS = ((100, 1, 0b0001),      # inside TOKYO window, FINE rung only
         (100, -1, 0b1110),     # inside, coarse rungs only
         (500, 1, 0b0011),      # outside any window, fine + coarse
         (1000, 1, 0b1000),     # exactly at the LONDON open
         (1300, -1, 0b0001))    # 300s after the LONDON open -> outside

WANT_EMIT = [
    # (dec_sec, side, fam_bits, rung_mask, conf_sec)
    (100 + 120, 1, G.FAM_BIT["G1_FINE"], 0b0001, 100),
    (100 + 15, 1, G.FAM_BIT["G1_FAST_OPEN"], 0b0001, 100),
    (100 + 120, -1, G.FAM_BIT["G1"], 0b1110, 100),
    (100 + 15, -1, G.FAM_BIT["G1_FAST_OPEN"], 0b1110, 100),
    (500 + 120, 1, G.FAM_BIT["G1"] | G.FAM_BIT["G1_FINE"], 0b0011, 500),
    (1000 + 120, 1, G.FAM_BIT["G1"], 0b1000, 1000),
    (1000 + 15, 1, G.FAM_BIT["G1_FAST_OPEN"], 0b1000, 1000),
    (1300 + 120, -1, G.FAM_BIT["G1_FINE"], 0b0001, 1300),
]


def test_g1_emissions():
    check("g1_emissions", G.g1_emissions(CONFS, OPENS), WANT_EMIT)
    # the fast-open candidate is ADDITIVE, never a replacement
    n120 = sum(1 for e in G.g1_emissions(CONFS, OPENS)
               if e[0] - e[4] == G.TAU_STAR)
    check("g1_emissions.n_tau_star", n120, len(CONFS))


# ================================== (b) the G2-RECLAIM 30-min bound ==========
CASES_R = ((1000, 1000 + 1799, True),
           (1000, 1000 + 1800, True),      # exactly 30 min: within
           (1000, 1000 + 1801, False),     # a second late: dropped
           (1000, -1, False),              # no reclaim at all
           (-1, 5000, False),              # reclaim without a break: impossible
           (5000, 6800, True),             # the clock runs from the BREAK,
           (5000, 6801, False))            # not from the session open


def test_reclaim_bound():
    for (b, r, want) in CASES_R:
        check("reclaim_within_bound[%d,%d]" % (b, r),
              G.reclaim_within_bound(b, r), want)


# ================================== (c) retired level sources ================
def test_level_family_filter():
    check("kept_six", sorted(G.KEPT_LEVEL_FAMILIES),
          ["FVOL_BAND", "FVOL_LADDER", "NDAY", "PHASE_HL", "PRIOR_DAY",
           "VWAP"])
    for f in G.RETIRED_LEVEL_FAMILIES:
        check("retired[%s]" % f, f in G.KEPT_LEVEL_FAMILIES, False)
    check("no_g3", [f for f in G.FAMILIES if f.startswith("G3")], [])


# ================================== (d) the NEWS_UNTRADEABLE leg class =======
CASES_S = ((0, True), (149, True), (150, False), (151, False), (3600, False))


def test_news_class():
    for (span, want) in CASES_S:
        check("is_news_untradeable[%d]" % span, G.is_news_untradeable(span),
              want)


# ================================== (e) the D-054 MID-SANITY mask ============
TICK = 5.0                      # $ per tick in this fixture
# trailing pooled spread histograms, in TICKS, per phase:
#   0: median 4 ticks = $20   -> 10x rule binds  -> $200
#   1: median 20 ticks = $100 -> the $500 cap binds
#   2: no trailing observation -> warm-up: the cap alone
HISTS = {0: {4: 100, 400: 20}, 1: {20: 100}, 2: {}}
WANT_MED = [20.0, 100.0, float("nan")]
WANT_THR = [200.0, 500.0, 500.0]


class _MS(object):
    """Session stub carrying only what the mask reads."""

    def __init__(self, state, spread, phase):
        self.state = np.array(state, dtype=np.int8)
        self.spread_usd = np.array(spread, dtype=np.float64)
        self.phase_tag = np.array(phase, dtype=np.int8)


import common as _C                                          # noqa: E402
TS = _C.ST_TWO_SIDED
NOT_TS = TS + 1                 # any other state code
MSESS = _MS(
    #   phase 0 (thr $200)                | phase 1 (thr $500) | phase 2
    state=[TS, TS, TS, TS, NOT_TS, TS] + [TS, TS, TS] + [TS, TS],
    spread=[10.0, 200.0, 200.01, 16100.0, 10.0, float("nan")]
           + [400.0, 500.0, 800.0] + [499.0, 501.0],
    phase=[0, 0, 0, 0, 0, 0] + [1, 1, 1] + [2, 2])
WANT_SANE = [True, True, False, False, False, False,
             True, True, False,
             True, False]


def test_sane_thresholds():
    got = SN.thresholds_from(HISTS, TICK)
    for p in range(3):
        check("sane_threshold[%d]" % p, got[p][2], WANT_THR[p])
    check("sane_trailing_median[0]", got[0][1], WANT_MED[0])
    check("sane_trailing_median[1]", got[1][1], WANT_MED[1])


def test_sane_mask():
    got = [bool(x) for x in SN.sane_mask(MSESS, WANT_THR)]
    check("sane_mask", got, WANT_SANE)


# ============================================================== MUTANTS ======
def mutant_w1_inclusive_end(sec, opens):
    """WRONG: treats open + 300 as still inside the window."""
    i = bisect.bisect_right(opens, sec) - 1
    return i >= 0 and (sec - opens[i]) <= G.FAST_OPEN_WINDOW


def mutant_w2_session_open_only(sec, opens):
    """WRONG: only the SESSION open opens a window (misses phase opens)."""
    return sec - opens[0] < G.FAST_OPEN_WINDOW


def mutant_w3_bisect_left(sec, opens):
    """WRONG: bisect_left drops the open second itself out of its window."""
    i = bisect.bisect_left(opens, sec) - 1
    return i >= 0 and (sec - opens[i]) < G.FAST_OPEN_WINDOW


def mutant_w4_absolute_window(sec, opens):
    """WRONG: 'first 300s of the session' instead of per phase open."""
    return sec < G.FAST_OPEN_WINDOW


MUTANTS_W = (("inclusive_end", mutant_w1_inclusive_end),
             ("session_open_only", mutant_w2_session_open_only),
             ("bisect_left", mutant_w3_bisect_left),
             ("absolute_window", mutant_w4_absolute_window))


def mutant_e1_replacement(confs, opens):
    """WRONG: the fast-open candidate REPLACES the tau* one."""
    out = []
    for (conf, side, mask) in confs:
        if G.in_fast_open(conf, opens):
            out.append((conf + G.FAST_OPEN_DELAY, side,
                        G.FAM_BIT["G1_FAST_OPEN"], mask, conf))
            continue
        fam = 0
        if mask & G.COARSE_MASK:
            fam |= G.FAM_BIT["G1"]
        if mask & G.FINE_BIT:
            fam |= G.FAM_BIT["G1_FINE"]
        out.append((conf + G.TAU_STAR, side, fam, mask, conf))
    return out


def mutant_e2_fine_is_g1(confs, opens):
    """WRONG: the fine rung is folded into the G1 tag (no marginal visible)."""
    out = []
    for (conf, side, mask) in confs:
        out.append((conf + G.TAU_STAR, side, G.FAM_BIT["G1"], mask, conf))
        if G.in_fast_open(conf, opens):
            out.append((conf + G.FAST_OPEN_DELAY, side,
                        G.FAM_BIT["G1_FAST_OPEN"], mask, conf))
    return out


def mutant_e3_fast_open_tau(confs, opens):
    """WRONG: the fast-open family keeps the 120s delay (tag only)."""
    out = []
    for (conf, side, mask) in confs:
        fam = 0
        if mask & G.COARSE_MASK:
            fam |= G.FAM_BIT["G1"]
        if mask & G.FINE_BIT:
            fam |= G.FAM_BIT["G1_FINE"]
        if G.in_fast_open(conf, opens):
            fam |= G.FAM_BIT["G1_FAST_OPEN"]
        out.append((conf + G.TAU_STAR, side, fam, mask, conf))
    return out


def mutant_e4_fine_rung_only_fast(confs, opens):
    """WRONG: fast-open runs the coarse rungs only (spec: ALL rungs)."""
    out = []
    for (conf, side, mask) in confs:
        fam = 0
        if mask & G.COARSE_MASK:
            fam |= G.FAM_BIT["G1"]
        if mask & G.FINE_BIT:
            fam |= G.FAM_BIT["G1_FINE"]
        out.append((conf + G.TAU_STAR, side, fam, mask, conf))
        if G.in_fast_open(conf, opens) and (mask & G.COARSE_MASK):
            out.append((conf + G.FAST_OPEN_DELAY, side,
                        G.FAM_BIT["G1_FAST_OPEN"], mask, conf))
    return out


MUTANTS_E = (("replacement", mutant_e1_replacement),
             ("fine_is_g1", mutant_e2_fine_is_g1),
             ("fast_open_tau", mutant_e3_fast_open_tau),
             ("fast_open_coarse_only", mutant_e4_fine_rung_only_fast))


def mutant_r1_absolute_clock(break_sec, reclaim_sec):
    """WRONG: the 30 min is measured on the session clock, not from the break."""
    return 0 <= reclaim_sec <= G.RECLAIM_BOUND


def mutant_r2_strict(break_sec, reclaim_sec):
    """WRONG: strict inequality drops the exactly-30-min reclaim."""
    return reclaim_sec >= 0 and break_sec >= 0 and \
        (reclaim_sec - break_sec) < G.RECLAIM_BOUND


def mutant_r3_unbounded(break_sec, reclaim_sec):
    """WRONG: the M1.A behaviour — no bound at all."""
    return reclaim_sec >= 0


MUTANTS_R = (("absolute_clock", mutant_r1_absolute_clock),
             ("strict_bound", mutant_r2_strict),
             ("unbounded", mutant_r3_unbounded))


def mutant_s1_inclusive(span):
    """WRONG: a 150s leg counted as news-untradeable (spec: span < 150)."""
    return span <= G.NEWS_SPAN


MUTANTS_S = (("news_inclusive", mutant_s1_inclusive),)


def mutant_t1_no_cap(hists, tick):
    """WRONG: drops the $500 absolute cap (a wide-book phase stays 'sane')."""
    out = {}
    for p, h in hists.items():
        med = SN._hist_median(h)
        out[p] = (0, med * tick, (SN.SANE_MULT * med * tick
                                  if np.isfinite(med) else SN.SANE_CAP_USD))
    return out


def mutant_t2_cap_only(hists, tick):
    """WRONG: cap only — ignores the 10 x trailing-median rule."""
    return {p: (0, float("nan"), SN.SANE_CAP_USD) for p in hists}


def mutant_t3_mean(hists, tick):
    """WRONG: mean instead of median — the artifacts inflate their own bound."""
    out = {}
    for p, h in hists.items():
        n = sum(h.values())
        m = (sum(k * v for k, v in h.items()) / n) if n else float("nan")
        out[p] = (n, m * tick, (min(SN.SANE_MULT * m * tick, SN.SANE_CAP_USD)
                                if np.isfinite(m) else SN.SANE_CAP_USD))
    return out


MUTANTS_T = (("sane_no_cap", mutant_t1_no_cap),
             ("sane_cap_only", mutant_t2_cap_only),
             ("sane_mean_not_median", mutant_t3_mean))


def mutant_m1_strict(s, thr):
    """WRONG: strict < drops a second sitting exactly on the threshold."""
    t = np.asarray(thr, dtype=np.float64)[s.phase_tag]
    return (s.state == TS) & np.isfinite(s.spread_usd) & (s.spread_usd < t)


def mutant_m2_ignores_two_sided(s, thr):
    """WRONG: spread test only — a one-sided book passes."""
    t = np.asarray(thr, dtype=np.float64)[s.phase_tag]
    return np.isfinite(s.spread_usd) & (s.spread_usd <= t)


def mutant_m3_global_threshold(s, thr):
    """WRONG: one threshold for the whole session (no per-phase clock)."""
    t = float(np.max(thr))
    return (s.state == TS) & np.isfinite(s.spread_usd) & (s.spread_usd <= t)


MUTANTS_M = (("sane_strict", mutant_m1_strict),
             ("sane_ignores_two_sided", mutant_m2_ignores_two_sided),
             ("sane_global_threshold", mutant_m3_global_threshold))


def test_mutants_are_caught():
    for (nm, fn) in MUTANTS_W:
        bad = [sec for (sec, want) in CASES_W if fn(sec, OPENS) != want]
        _red("window", nm, bad)
    for (nm, fn) in MUTANTS_E:
        got = fn(CONFS, OPENS)
        _red("emission", nm, ["g1_emissions"] if got != WANT_EMIT else [])
    for (nm, fn) in MUTANTS_R:
        bad = [b for (b, r, want) in CASES_R if fn(b, r) != want]
        _red("reclaim bound", nm, bad)
    for (nm, fn) in MUTANTS_S:
        bad = [s for (s, want) in CASES_S if fn(s) != want]
        _red("news class", nm, bad)
    for (nm, fn) in MUTANTS_T:
        bad = [p for p in range(3)
               if fn(HISTS, TICK)[p][2] != WANT_THR[p]]
        _red("sane thresholds", nm, bad)
    for (nm, fn) in MUTANTS_M:
        got = [bool(x) for x in fn(MSESS, WANT_THR)]
        _red("sane mask", nm, [i for i, (a, b) in
                               enumerate(zip(got, WANT_SANE)) if a != b])


def _red(group, nm, caught_on):
    if not caught_on:
        FAILURES.append("MUTANT NOT CAUGHT (%s): %s" % (group, nm))
    else:
        print("  red-first: mutant %-24s caught on %s"
              % (nm, ",".join(str(c) for c in caught_on)))


def main():
    M.verify_spec_m1b()
    for t in (test_phase_open_secs, test_in_fast_open, test_g1_emissions,
              test_reclaim_bound, test_level_family_filter,
              test_news_class, test_sane_thresholds, test_sane_mask,
              test_mutants_are_caught):
        print("== %s" % t.__name__)
        t()
    if FAILURES:
        print("\nFAILURES (%d):" % len(FAILURES))
        for f in FAILURES:
            print("  " + f)
        return 1
    print("\nALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
