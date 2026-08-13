#!/usr/bin/python3
"""PORT M1.B S1.1/S1.2 — red-first self-tests for the two named algorithms.

The brief names exactly two red-first cases for this lane:

  (1) the OR_EXT LEVEL CONSTRUCTION IN THE LEDGER PATH.  The SEGMENT-SCOPE bug
      class is a named prior: `family_discovery` froze `mutant_ext_phase_blind`
      for the FEATURE path (a Tokyo opening range "explaining" a New York
      price).  This lane extends that mutant class to the LEDGER: a scoped
      level must be unable to be touched, to arm, or to resolve an outcome
      outside its own segment, and its identity must not cross sessions.

  (2) the NEWS-WINDOW CALENDAR JOIN.  Off-by-one day and timezone are the two
      failure modes: a Globex session opens the previous evening ET, so the
      08:30/10:00/14:00 ET slots of THREE calendar days can fall inside one
      session, and the ET offset changes twice a year.  A join on the session's
      own trade_date, or on a frozen UTC offset, is wrong in exactly the way
      this test catches.

RED-FIRST LAW: a test counts only if it FAILS on a broken implementation.
Every MUTANT below is a deliberately wrong version committed in this file, and
`run_group` asserts each one breaks at least one case the real implementation
passes.  A mutant nothing catches is a FAILURE.

Run: /usr/bin/python3 engine/port_m1/test_m1c.py
"""
import datetime as dt
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m1_common as M
import common as C
import census_common as X
import b3_levels as B3
import b10_levels_v4 as L4
import b10_generation_v3 as G3
import b11_relevance_v3 as R3
import family_discovery as FD

FAILURES = []
TZ_NY = ZoneInfo("America/New_York")


def check(name, got, want):
    if got != want:
        FAILURES.append("%s: got %r want %r" % (name, got, want))


# ===================================================================
# session stub: 3 phases, one second per index, a synthetic mid path
# ===================================================================
class _S(object):
    """Minimal session view carrying exactly what the level code reads."""

    __slots__ = ("phase_tag", "mid", "valid", "vt", "vm", "n", "state", "meta")

    def __init__(self, phase_runs, mid, valid=None):
        t = []
        for v, k in phase_runs:
            t.extend([v] * k)
        self.phase_tag = np.array(t, dtype=np.int8)
        self.n = len(t)
        self.mid = np.asarray(mid, dtype=np.float64)
        self.valid = (np.ones(self.n, dtype=bool) if valid is None
                      else np.asarray(valid, dtype=bool))
        self.vt = np.nonzero(self.valid)[0].astype(np.int64)
        self.vm = self.mid[self.vt]
        self.state = np.full(self.n, C.ST_TWO_SIDED, dtype=np.int8)
        self.meta = {}


# ===================================================================
# (1a) OR_EXT LEVEL CONSTRUCTION  (prices, activation second, scope)
# ===================================================================
# TOKYO = phase 0 for 600s, LONDON = phase 1 for 600s.  Inside the first 300s
# of TOKYO the mid ranges 100..110 (OR_H=110, OR_L=100, range=10); afterwards it
# drifts.  OR30 = 30 minutes = 1800s > the segment, so the cell is EMPTY; the
# test uses OR5 (300s) via a patched minutes argument.
_MID = np.concatenate([
    np.linspace(100.0, 110.0, 300),      # TOKYO opening range
    np.full(300, 105.0),                 # TOKYO rest-of-window
    np.full(600, 130.0)])                # LONDON
S_OR = _S(((0, 600), (1, 600)), _MID)


def _orext(minutes=5, cells=(("TOKYO", 5),)):
    old_cells, old_k = B3.OREXT_CELLS, B3.OREXT_K
    B3.OREXT_CELLS = {"SI": cells}
    try:
        return B3.orext_levels("SI", S_OR)
    finally:
        B3.OREXT_CELLS, B3.OREXT_K = old_cells, old_k


def case_or_range(f):
    return f(S_OR, "TOKYO", 5)


def case_or_range_no_rest(f):
    """OR longer than the segment: no rest-of-window => typed exclusion."""
    oh, ol, t1 = f(S_OR, "TOKYO", 20)
    return (np.isnan(oh), np.isnan(ol), t1)


def case_or_range_other_segment(f):
    """LONDON is flat at 130: a zero range, and the caller must drop it."""
    return f(S_OR, "LONDON", 5)


CASES_OR = (
    ("tokyo_or5", case_or_range, (110.0, 100.0, 300)),
    ("no_rest_of_window", case_or_range_no_rest, (True, True, -1)),
    ("london_flat", case_or_range_other_segment, (130.0, 130.0, 900)),
)


def mutant_or_range_whole_segment(s, seg, minutes):
    """The opening range taken over the WHOLE segment (look-ahead)."""
    p = X.PHASE_NAMES.index(seg)
    idx = np.nonzero((s.phase_tag == p) & s.valid)[0]
    if idx.size < 2:
        return (float("nan"), float("nan"), -1)
    t1 = int(idx[0]) + int(minutes) * 60
    m = s.mid[idx]
    return float(m.max()), float(m.min()), t1


def mutant_or_range_session_start(s, seg, minutes):
    """The OR anchored at the SESSION open instead of the SEGMENT open — the
    segment-scope bug in its construction form."""
    idx = np.nonzero(s.valid)[0]
    if idx.size < 2:
        return (float("nan"), float("nan"), -1)
    t1 = int(idx[0]) + int(minutes) * 60
    a = idx[idx < t1]
    b = idx[idx >= t1]
    if a.size == 0 or b.size == 0:
        return (float("nan"), float("nan"), -1)
    m = s.mid[a]
    return float(m.max()), float(m.min()), t1


def mutant_or_range_ignores_empty_rest(s, seg, minutes):
    """No rest-of-window check: emits a level nothing can ever test."""
    p = X.PHASE_NAMES.index(seg)
    idx = np.nonzero((s.phase_tag == p) & s.valid)[0]
    if idx.size < 2:
        return (float("nan"), float("nan"), -1)
    t1 = int(idx[0]) + int(minutes) * 60
    a = idx[idx < t1]
    if a.size == 0:
        return (float("nan"), float("nan"), -1)
    m = s.mid[a]
    return float(m.max()), float(m.min()), t1


MUTANTS_OR = (("or_over_whole_segment", mutant_or_range_whole_segment),
              ("or_from_session_open", mutant_or_range_session_start),
              ("or_ignores_empty_rest", mutant_or_range_ignores_empty_rest))


# ===================================================================
# (1b) THE LEDGER SCOPE ITSELF  —  scope_diff + touch_scan behaviour
# ===================================================================
# 1200 observed seconds; phase 0 for the first 600, phase 1 after.  The level
# sits at 130 and is scoped to phase 0.  The mid is far from it inside phase 0
# (arming distance) and lands exactly on it inside phase 1.
PHASE_V = np.concatenate([np.zeros(600, np.int8), np.ones(600, np.int8)])
DIFF_FAR_THEN_ON = np.concatenate([np.full(600, -30.0), np.full(600, 0.0)])
# the mirror case: the level IS touched inside its own segment (second 500)
DIFF_TOUCH_IN_SCOPE = np.concatenate([np.full(400, -30.0), np.full(200, 0.0),
                                      np.full(600, -30.0)])
TOL = 1.0
AF = 0            # active from the first observed second


def _touches(f, diff, scope):
    d = np.abs(f(np.asarray(diff, dtype=np.float64), PHASE_V, scope))
    tp, _fn = B3.touch_scan(d, PHASE_V, AF, TOL)
    return tuple(int(x) for x in tp.tolist())


def _first_near(f, diff, scope):
    d = np.abs(f(np.asarray(diff, dtype=np.float64), PHASE_V, scope))
    _tp, fn = B3.touch_scan(d, PHASE_V, AF, TOL)
    return int(fn)


CASES_SCOPE = (
    # the whole point: a phase-0 level may NOT be touched in phase 1
    ("out_of_scope_no_touch", lambda f: _touches(f, DIFF_FAR_THEN_ON, 0), ()),
    ("out_of_scope_not_virgin_break",
     lambda f: _first_near(f, DIFF_FAR_THEN_ON, 0), -1),
    # an UNSCOPED level in the same geometry IS touched (the control)
    ("unscoped_touches", lambda f: _touches(f, DIFF_FAR_THEN_ON, None), (600,)),
    # in-scope touches still fire
    ("in_scope_touches", lambda f: _touches(f, DIFF_TOUCH_IN_SCOPE, 0), (400,)),
    ("in_scope_first_near",
     lambda f: _first_near(f, DIFF_TOUCH_IN_SCOPE, 0), 400),
    # a level scoped to the OTHER phase sees nothing of the in-scope episode
    ("other_scope_blind", lambda f: _touches(f, DIFF_TOUCH_IN_SCOPE, 1), ()),
    # TYPED EXCLUSION: an out-of-scope second is NaN, never a fabricated
    # distance (0 = "touched", 1e9 = "far enough to arm on time it never
    # lived through") — the arm/near/outcome scans all key on finiteness
    ("out_of_scope_is_nan",
     lambda f: bool(np.isnan(np.asarray(f(DIFF_FAR_THEN_ON, PHASE_V, 0))[700])),
     True),
    ("in_scope_value_preserved",
     lambda f: float(np.asarray(f(DIFF_FAR_THEN_ON, PHASE_V, 0))[100]), -30.0),
)


def mutant_scope_noop(diff, phase_v, scope_phase):
    """The segment scope dropped entirely (the named prior bug, ledger form)."""
    return diff


def mutant_scope_zero_fill(diff, phase_v, scope_phase):
    """Out-of-scope seconds set to distance 0 instead of typed-excluded: the
    level then reads as PERMANENTLY touched everywhere else."""
    if scope_phase is None:
        return diff
    return np.where(np.asarray(phase_v) == scope_phase, diff, 0.0)


def mutant_scope_inverted(diff, phase_v, scope_phase):
    """The mask inverted: the level exists everywhere EXCEPT its own segment."""
    if scope_phase is None:
        return diff
    return np.where(np.asarray(phase_v) != scope_phase, diff, np.nan)


def mutant_scope_far_fill(diff, phase_v, scope_phase):
    """Out-of-scope seconds pushed far away instead of excluded: the level then
    ARMS on time it never lived through."""
    if scope_phase is None:
        return diff
    return np.where(np.asarray(phase_v) == scope_phase, diff, 1e9)


MUTANTS_SCOPE = (("scope_dropped", mutant_scope_noop),
                 ("out_of_scope_is_a_touch", mutant_scope_zero_fill),
                 ("scope_inverted", mutant_scope_inverted),
                 ("out_of_scope_arms", mutant_scope_far_fill))


# ===================================================================
# (2) THE NEWS-WINDOW CALENDAR JOIN  (off-by-one day / timezone)
# ===================================================================
# A CME session opens 17:00 ET the previous evening and runs ~23h.  Two sessions
# are used: one in EST (January) and one in EDT (July), each carrying an FOMC
# day.  The banked FOMC dates below are read from the committed calendar.
FOMC = set(FD.fomc_release_dates())


def _open_utc(y, m, d, hh=17, mm=0):
    """Epoch of a Globex open at hh:mm ET on the PREVIOUS evening."""
    loc = dt.datetime(y, m, d, hh, mm, tzinfo=TZ_NY)
    return int(loc.timestamp())


# 2023-02-01 was an FOMC statement day (the "Jan/Feb 31-1" row: the LAST day).
SESS_EST = (_open_utc(2023, 1, 31), 23 * 3600)      # opens 2023-01-31 17:00 ET
# 2023-07-26 was an FOMC statement day (EDT).
SESS_EDT = (_open_utc(2023, 7, 25), 23 * 3600)      # opens 2023-07-25 17:00 ET
# a session with no FOMC day inside it at all
SESS_NONE = (_open_utc(2023, 3, 6), 23 * 3600)


def _offsets(f, sess):
    return tuple(f(sess[0], sess[1], FOMC))


def _et(sess, off):
    return dt.datetime.fromtimestamp(sess[0] + off, TZ_NY).strftime(
        "%Y-%m-%d %H:%M")


def _labels(f, sess):
    return tuple(_et(sess, o) for o in f(sess[0], sess[1], FOMC))


CASES_NEWS = (
    # EST session: 08:30, 10:00 and the 14:00 FOMC of 2023-02-01
    ("est_labels", lambda f: _labels(f, SESS_EST),
     ("2023-02-01 08:30", "2023-02-01 10:00", "2023-02-01 14:00")),
    # EDT session: the same three slots on 2023-07-26, DST offset applied
    ("edt_labels", lambda f: _labels(f, SESS_EDT),
     ("2023-07-26 08:30", "2023-07-26 10:00", "2023-07-26 14:00")),
    # a non-FOMC session carries the two fixed slots and NOTHING else
    ("no_fomc_labels", lambda f: _labels(f, SESS_NONE),
     ("2023-03-07 08:30", "2023-03-07 10:00")),
    # the offsets are session seconds, and they are sorted and unique
    ("est_sorted", lambda f: _offsets(f, SESS_EST)
     == tuple(sorted(set(_offsets(f, SESS_EST)))), True),
    # 08:30 ET is 15.5h after a 17:00 ET open, in BOTH offsets - the wall clock
    # is what is fixed, never the UTC distance
    ("wall_clock_invariant",
     lambda f: (_offsets(f, SESS_EST)[0], _offsets(f, SESS_EDT)[0]),
     (int(15.5 * 3600), int(15.5 * 3600))),
)


def mutant_news_session_date_join(open_utc, n, fomc_dates):
    """The FOMC join made on the SESSION's own date instead of the calendar day
    the release second falls on — the off-by-one-day bug (a session that opens
    the evening BEFORE an FOMC day then carries no window, and the evening OF
    one carries a phantom)."""
    rel = []
    for (_nm, tz, hh, mm) in FD.NEWS_SLOTS:
        rel.extend(FD.local_epochs(open_utc, n, tz, hh, mm))
    d = dt.datetime.fromtimestamp(int(open_utc), TZ_NY).date()
    if d in fomc_dates:
        rel.extend(FD.local_epochs(open_utc, n, TZ_NY, FD.FOMC_HOUR,
                                   FD.FOMC_MIN))
    return sorted(set(int(x) for x in rel))


def mutant_news_day_plus_one(open_utc, n, fomc_dates):
    """The release matched one calendar day late."""
    rel = []
    for (_nm, tz, hh, mm) in FD.NEWS_SLOTS:
        rel.extend(FD.local_epochs(open_utc, n, tz, hh, mm))
    for off in FD.local_epochs(open_utc, n, FD.TZ_NY, FD.FOMC_HOUR,
                               FD.FOMC_MIN):
        d = dt.datetime.fromtimestamp(int(open_utc) + off, TZ_NY).date()
        if (d - dt.timedelta(days=1)) in fomc_dates:
            rel.append(off)
    return sorted(set(int(x) for x in rel))


def mutant_news_utc_slots(open_utc, n, fomc_dates):
    """The ET wall clock read as UTC (no timezone at all)."""
    rel = []
    for (_nm, _tz, hh, mm) in FD.NEWS_SLOTS:
        rel.extend(FD.local_epochs(open_utc, n, dt.timezone.utc, hh, mm))
    for off in FD.local_epochs(open_utc, n, dt.timezone.utc, FD.FOMC_HOUR,
                               FD.FOMC_MIN):
        d = dt.datetime.fromtimestamp(int(open_utc) + off,
                                      dt.timezone.utc).date()
        if d in fomc_dates:
            rel.append(off)
    return sorted(set(int(x) for x in rel))


def mutant_news_fixed_offset(open_utc, n, fomc_dates):
    """ET frozen at UTC-5: correct in winter, one hour wrong all summer."""
    tz = dt.timezone(dt.timedelta(hours=-5))
    rel = []
    for (_nm, _t, hh, mm) in FD.NEWS_SLOTS:
        rel.extend(FD.local_epochs(open_utc, n, tz, hh, mm))
    for off in FD.local_epochs(open_utc, n, tz, FD.FOMC_HOUR, FD.FOMC_MIN):
        if dt.datetime.fromtimestamp(int(open_utc) + off, tz).date() \
                in fomc_dates:
            rel.append(off)
    return sorted(set(int(x) for x in rel))


def mutant_news_same_day_only(open_utc, n, fomc_dates):
    """Only the session-open calendar day scanned: the morning slots of the
    NEXT day (where every US release actually lands) disappear."""
    rel = []
    for (_nm, tz, hh, mm) in FD.NEWS_SLOTS:
        rel.extend(FD.local_epochs(open_utc, n, tz, hh, mm, days=(0,)))
    for off in FD.local_epochs(open_utc, n, FD.TZ_NY, FD.FOMC_HOUR,
                               FD.FOMC_MIN, days=(0,)):
        if dt.datetime.fromtimestamp(int(open_utc) + off, TZ_NY).date() \
                in fomc_dates:
            rel.append(off)
    return sorted(set(int(x) for x in rel))


MUTANTS_NEWS = (("session_date_join", mutant_news_session_date_join),
                ("release_day_plus_one", mutant_news_day_plus_one),
                ("et_slots_read_as_utc", mutant_news_utc_slots),
                ("frozen_utc_minus_5", mutant_news_fixed_offset),
                ("same_calendar_day_only", mutant_news_same_day_only))


# ===================================================================
# (3) the relevance scope guard (same bug class, scoring form)
# ===================================================================
LV = [B3.Level("A|1", "OR_EXT", 110.0, 300, scope_phase=0,
               session_scoped=True),
      B3.Level("A|2", "OR_EXT", 120.0, 300, scope_phase=1,
               session_scoped=True),
      B3.Level("B|1", "NDAY", 115.0, 0)]


def _fams(f, sec, phase):
    out = f(LV, 0, sec, phase)
    return tuple(sorted((k, tuple(sorted(v))) for k, v in out.items()))


CASES_RSCOPE = (
    ("phase0_after_activation", lambda f: _fams(f, 400, 0),
     (("NDAY", (115.0,)), ("OR_EXT", (110.0,)))),
    ("phase1_after_activation", lambda f: _fams(f, 400, 1),
     (("NDAY", (115.0,)), ("OR_EXT", (120.0,)))),
    ("before_activation", lambda f: _fams(f, 100, 0), (("NDAY", (115.0,)),)),
)


def mutant_rscope_phase_blind(levels, j, sec, phase):
    out = {}
    for L in levels:
        if L.active_from > sec:
            continue
        p = float(L.series[j]) if L.dynamic else float(L.price)
        if np.isfinite(p):
            out.setdefault(L.family, []).append(p)
    return out


def mutant_rscope_lookahead(levels, j, sec, phase):
    out = {}
    for L in levels:
        if L.scope_phase is not None and int(phase) != int(L.scope_phase):
            continue
        p = float(L.series[j]) if L.dynamic else float(L.price)
        if np.isfinite(p):
            out.setdefault(L.family, []).append(p)
    return out


MUTANTS_RSCOPE = (("relevance_phase_blind", mutant_rscope_phase_blind),
                  ("relevance_lookahead", mutant_rscope_lookahead))


# ===================================================================
# green-only assertions
# ===================================================================
def test_spec_pin():
    check("spec/m1", M.spec_sha()[:16], M.SPEC_SHA16)
    check("spec/m1b", M.spec_m1b_sha()[:16], M.SPEC_M1B_SHA16)


def test_adopted_cells():
    """CC-M1-6.1 verbatim: six cells, HG none."""
    check("cells/SI", tuple(L4.OREXT_ADOPTED["SI"]),
          (("TOKYO", 30), ("LONDON", 30), ("NY", 30),
           ("TOKYO", 60), ("LONDON", 60)))
    check("cells/NKD", tuple(L4.OREXT_ADOPTED["NKD"]), (("LONDON", 30),))
    check("cells/HG", tuple(L4.OREXT_ADOPTED["HG"]), ())
    check("cells/n", sum(len(v) for v in L4.OREXT_ADOPTED.values()), 6)
    # the ladder is the censused one
    import hl_census as HL
    check("ladder", tuple(B3.OREXT_K), tuple(HL.P3_K))
    # HG builds NO OR_EXT level at all
    B3.OREXT_CELLS = {a: L4.OREXT_ADOPTED[a] for a in ("SI", "HG", "NKD")}
    check("hg/empty", B3.orext_levels("HG", S_OR), [])


def test_orext_level_objects():
    """Prices, activation, scope and identity of the built levels."""
    B3.OREXT_CELLS = {"SI": (("TOKYO", 5),)}
    ls = B3.orext_levels("SI", S_OR)
    check("levels/n", len(ls), 2 * len(B3.OREXT_K))
    up = sorted(L.price for L in ls if L.key.endswith("+1"))
    dn = sorted(L.price for L in ls if L.key.endswith("-1"))
    # OR_H 110, OR_L 100, range 10 -> up 115/120/125/130, down 95/90/85/80
    check("levels/up", up, [115.0, 120.0, 125.0, 130.0])
    check("levels/dn", dn, [80.0, 85.0, 90.0, 95.0])
    check("levels/active_from", sorted(set(L.active_from for L in ls)), [300])
    check("levels/scope", sorted(set(L.scope_phase for L in ls)), [0])
    check("levels/session_scoped", all(L.session_scoped for L in ls), True)
    check("levels/family", sorted(set(L.family for L in ls)), ["OR_EXT"])
    check("levels/id_fits_dtype", max(len(L.key) for L in ls) <= 40, True)
    # a flat opening range produces NOTHING (no degenerate stack of levels)
    B3.OREXT_CELLS = {"SI": (("LONDON", 5),)}
    check("levels/flat_or", B3.orext_levels("SI", S_OR), [])
    B3.OREXT_CELLS = None


def test_or_range_matches_hl_census():
    """The ledger's OR must be the census's OR — one construction, not two."""
    import hl_census as HL
    for minutes in (5, 20):
        oh, ol, _t1 = B3.or_range(S_OR, "TOKYO", minutes)
        h_oh, h_ol, _rh, _rl = HL.or_facts(S_OR, S_OR.valid, "TOKYO", minutes)
        check("or_vs_hl/%d/h" % minutes,
              (np.isnan(oh) and np.isnan(h_oh)) or oh == h_oh, True)
        check("or_vs_hl/%d/l" % minutes,
              (np.isnan(ol) and np.isnan(h_ol)) or ol == h_ol, True)


def test_family_bits():
    """Nine families, disjoint bits, uint16-safe; FIRST_TEST is NKD-only."""
    check("fam/n", len(G3.FAMILIES), 9)
    check("fam/bits", sorted(G3.FAM_BIT.values()),
          [1 << i for i in range(9)])
    check("fam/uint16", max(G3.FAM_BIT.values()) < (1 << 16), True)
    check("fam/first_test_assets", G3.FIRST_TEST_ASSETS, ("NKD",))
    check("fam/no_fast_close",
          any("CLOSE" in f for f in G3.FAMILIES), False)
    check("fam/kept_levels", G3.KEPT_LEVEL_FAMILIES[-1], "OR_EXT")
    check("fam/kept_levels_n", len(G3.KEPT_LEVEL_FAMILIES), 7)
    check("flags/disjoint",
          sorted((G3.FLAG_OREXT_BEYOND, G3.FLAG_OREXT_BEYOND_ANY,
                  G3.FLAG_FIRST_TEST_VIRGIN)), [1, 2, 4])


def test_news_delay_single():
    """CC-M1-7.1: a SINGLE 15s news delay (the {15,60} discovery pair is gone)."""
    check("news/delay", G3.NEWS_DELAY, 15)
    check("news/window", G3.NEWS_WINDOW, 600)
    check("micro/delay", G3.MICRO_DELAY, 15)
    check("micro/window", G3.MICRO_WINDOW, 300)
    check("micro/opens", tuple(m[0] for m in FD.MICRO_OPENS),
          ("TOKYO_LUNCH_REOPEN", "NY_CASH_OPEN"))


def test_fomc_calendar_last_day():
    """The statement lands on the meeting's LAST day (the '31-1' span case)."""
    check("fomc/jan_feb_2023", dt.date(2023, 2, 1) in FOMC, True)
    check("fomc/not_first_day", dt.date(2023, 1, 31) in FOMC, False)
    check("fomc/jul_2023", dt.date(2023, 7, 26) in FOMC, True)
    check("fomc/n_ge_50", len(FOMC) >= 50, True)


# ===================================================================
def run_group(title, cases, impl, mutants):
    """Green on the real implementation, and every mutant caught."""
    green = {}
    for (cname, fn, want) in cases:
        try:
            got = fn(impl)
        except Exception as e:                       # noqa: BLE001
            got = "EXC:%s" % e
        green[cname] = got
        if got != want:
            FAILURES.append("%s/%s: got %r want %r" % (title, cname, got, want))
    caught = {}
    for (mname, mimpl) in mutants:
        broke = []
        for (cname, fn, want) in cases:
            try:
                got = fn(mimpl)
            except Exception as e:                   # noqa: BLE001
                got = "EXC:%s" % e
            if got != want:
                broke.append(cname)
        caught[mname] = broke
        if not broke:
            FAILURES.append("%s: MUTANT %s caught by NOTHING (red-first law)"
                            % (title, mname))
    return caught


def main():
    red = {}
    test_spec_pin()
    test_adopted_cells()
    test_orext_level_objects()
    test_or_range_matches_hl_census()
    test_family_bits()
    test_news_delay_single()
    test_fomc_calendar_last_day()

    red["orext_or_range"] = run_group("OR", CASES_OR, B3.or_range, MUTANTS_OR)
    red["ledger_segment_scope"] = run_group("SCOPE", CASES_SCOPE,
                                            B3.scope_diff, MUTANTS_SCOPE)
    red["news_calendar_join"] = run_group("NEWS", CASES_NEWS,
                                          G3.news_release_offsets,
                                          MUTANTS_NEWS)
    red["relevance_scope"] = run_group("RSCOPE", CASES_RSCOPE,
                                       R3.level_prices_at, MUTANTS_RSCOPE)

    print("RED-FIRST EVIDENCE (mutant -> cases it breaks):")
    rows = []
    for group in sorted(red):
        for mname in sorted(red[group]):
            broke = red[group][mname]
            print("  %-22s %-24s %s" % (group, mname,
                                        ",".join(broke) or "NONE"))
            rows.append([group, mname, len(broke), ",".join(broke) or "NONE"])
    if not FAILURES:
        M.write_tsv(M.out_path(G3.OUT_DIR, "s1v3_redfirst.tsv"),
                    SECTION_RED, C.params_hash(
                        {"tests": "engine/port_m1/test_m1c.py"}),
                    ["algorithm", "mutant", "n_cases_broken", "cases_broken"],
                    rows, spec="PORT_M1B",
                    extra=["a mutant caught by NO case is a test FAILURE "
                           "(red-first law); the real implementation is green "
                           "on every case listed"])
    if FAILURES:
        print("\nFAILURES (%d):" % len(FAILURES))
        for f in FAILURES:
            print("  " + f)
        return 1
    print("\nALL PASS (%d mutants, all caught)"
          % sum(len(v) for v in red.values()))
    return 0


SECTION_RED = "S1.1/S1.2 red-first mutant evidence"


if __name__ == "__main__":
    sys.exit(main())
