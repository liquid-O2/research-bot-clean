#!/usr/bin/python3
"""PORT M1 §10 — red-first self-tests for the FAMILY DISCOVERY census.

The brief names two algorithms that must be red-first: the SLICE-MINER
MULTIPLICITY ACCOUNTING (§10B Holm control) and the F-D4 POST-SHOCK EVENT
DETECTOR.  Both are covered here with committed mutants, and the window
detectors (F-D1/2/3), the F-D6 extension test and the FOMC calendar parser ride
along because they are new algorithms too.

RED-FIRST LAW (repo): a test counts only if it FAILS on a broken
implementation.  Every MUTANT below is a deliberately wrong version, committed
in this file; `run_group` asserts each one breaks at least one case the real
implementation passes.  A mutant nothing catches is a FAILURE.

Run: /usr/bin/python3 engine/port_m1/test_fdisc.py
"""
import datetime as dt
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m1_common as M
import common as C
import family_discovery as F

FAILURES = []


def check(name, got, want):
    if got != want:
        FAILURES.append("%s: got %r want %r" % (name, got, want))


def approx(a, b, tol=1e-9):
    return abs(a - b) <= tol


class _S(object):
    """Minimal session stub for the window detectors."""

    def __init__(self, segs):
        t = []
        for v, n in segs:
            t.extend([v] * n)
        self.phase_tag = np.array(t, dtype=np.int8)
        self.n = len(t)


# ===================================================================
# (1) SLICE-MINER MULTIPLICITY ACCOUNTING  (§10B, the brief's named case)
# ===================================================================
# Holm step-down at alpha: sort p ascending, compare p_(k) with alpha/(m-k),
# reject while it holds and never reject past the first failure.  The adjusted
# form used by the miner is adj_(k) = min(1, running-max of (m-k) * p_(k)).

P_A = [0.001, 0.02, 0.03, 0.5]          # m=4: 0.001<0.0125 ok, 0.02>0.0166 stop
P_B = [0.004, 0.006, 0.5, 0.9]          # 0.004<0.0125, 0.006<0.0166 -> two
P_C = [0.02, 0.02, 0.02, 0.02]          # Bonferroni-equal: none at alpha .05
P_D = [0.001, 0.0001, 0.9]              # order must not matter to correctness
P_E = [0.01, float("nan"), 0.02]        # a NaN p is never rejected


def _rej(impl, pv, m=None):
    _adj, rej = impl(pv, 0.05, m if m is not None else len(pv))
    return tuple(rej)


def _adj(impl, pv, m=None):
    adj, _rej = impl(pv, 0.05, m if m is not None else len(pv))
    return tuple(None if not np.isfinite(x) else round(x, 12) for x in adj)


CASES_HOLM = (
    ("A/reject", lambda f: _rej(f, P_A), (True, False, False, False)),
    ("B/reject", lambda f: _rej(f, P_B), (True, True, False, False)),
    ("C/reject", lambda f: _rej(f, P_C), (False, False, False, False)),
    ("D/reject", lambda f: _rej(f, P_D), (True, True, False)),
    ("E/nan", lambda f: _rej(f, P_E), (True, False, True)),
    # the family size is an INPUT: the same p-vector tested inside a bigger
    # family must reject less (this is the multiplicity accounting itself)
    ("A/bigger_family", lambda f: _rej(f, P_A, m=400),
     (False, False, False, False)),
    ("A/adjusted", lambda f: _adj(f, P_A),
     (0.004, 0.06, 0.06, 0.5)),
    ("B/adjusted_monotone", lambda f: _adj(f, P_B),
     (0.016, 0.018, 1.0, 1.0)),
)


def mutant_holm_no_stepdown(pvals, alpha=0.05, m=None):
    """Missing the running max: adjusted p can DECREASE with p (illegal)."""
    n = len(pvals)
    m = n if m is None else int(m)
    order = sorted(range(n), key=lambda i: (
        float("inf") if not np.isfinite(pvals[i]) else pvals[i], i))
    adj = [float("nan")] * n
    k = 0
    for i in order:
        if not np.isfinite(pvals[i]):
            continue
        adj[i] = min(1.0, (m - k) * pvals[i])
        k += 1
    return adj, [bool(np.isfinite(adj[i]) and adj[i] <= alpha)
                 for i in range(n)]


def mutant_holm_bonferroni(pvals, alpha=0.05, m=None):
    """Bonferroni instead of Holm: m*p for every hypothesis (over-conservative
    — it loses the second rejection of case B)."""
    n = len(pvals)
    m = n if m is None else int(m)
    adj = [min(1.0, m * p) if np.isfinite(p) else float("nan") for p in pvals]
    return adj, [bool(np.isfinite(a) and a <= alpha) for a in adj]


def mutant_holm_bh(pvals, alpha=0.05, m=None):
    """Benjamini-Hochberg (FDR) smuggled in where FWER was specified."""
    n = len(pvals)
    m = n if m is None else int(m)
    order = sorted(range(n), key=lambda i: (
        float("inf") if not np.isfinite(pvals[i]) else pvals[i], i))
    adj = [float("nan")] * n
    k = 0
    for i in order:
        if not np.isfinite(pvals[i]):
            continue
        adj[i] = min(1.0, m * pvals[i] / (k + 1))
        k += 1
    return adj, [bool(np.isfinite(adj[i]) and adj[i] <= alpha)
                 for i in range(n)]


def mutant_holm_ignores_m(pvals, alpha=0.05, m=None):
    """The multiplicity leak: the declared family size is ignored and only the
    tested vector's own length is used."""
    return F.holm(pvals, alpha, m=None)


def mutant_holm_nan_rejects(pvals, alpha=0.05, m=None):
    """A non-finite p treated as 0 (a cell with no complement 'passes')."""
    pv = [0.0 if not np.isfinite(p) else p for p in pvals]
    return F.holm(pv, alpha, m=(len(pvals) if m is None else m))


MUTANTS_HOLM = (("no_stepdown", mutant_holm_no_stepdown),
                ("bonferroni", mutant_holm_bonferroni),
                ("benjamini_hochberg", mutant_holm_bh),
                ("ignores_family_size", mutant_holm_ignores_m),
                ("nan_p_rejects", mutant_holm_nan_rejects))

# --- the family size itself: marginals AND 2-way cells, all of them ---------
CELLS_MARG = [(("phase",), ("NY",), None)] * 7
CELLS_TWO = [(("phase", "dow"), ("NY", "MON"), None)] * 93

CASES_M = (
    ("both_strata", lambda f: f(CELLS_MARG, CELLS_TWO), 100),
    ("marginals_only", lambda f: f(CELLS_MARG, []), 7),
    ("twoway_only", lambda f: f([], CELLS_TWO), 93),
    ("empty", lambda f: f([], []), 0),
)


def mutant_m_marginals_only(marg, two):
    return len(marg)


def mutant_m_twoway_only(marg, two):
    return len(two)


def mutant_m_max(marg, two):
    return max(len(marg), len(two))


MUTANTS_M = (("family_is_marginals_only", mutant_m_marginals_only),
             ("family_is_twoway_only", mutant_m_twoway_only),
             ("family_is_max_stratum", mutant_m_max))


# ===================================================================
# (2) THE F-D4 POST-SHOCK EVENT DETECTOR (the brief's second named case)
# ===================================================================
# A synthetic SANE mid series on a $1-per-point contract: flat, then a 400-point
# ramp inside 100s (a $400... no: mult=10 -> $4,000) then flat again.
MULT = 10.0
SPAN = 150
THR = 1000.0                      # $1,000 = 100 points at mult 10


def _series():
    """(vt, vm): 0..99 flat at 100.0, 100..119 ramping +10/s, 120..399 flat."""
    vt, vm = [], []
    px = 100.0
    for t in range(400):
        if 100 <= t < 120:
            px += 10.0
        vt.append(t)
        vm.append(px)
    return vt, vm


VT, VM = _series()


def _eps(impl):
    return tuple(impl(VT, VM, MULT, SPAN, THR))


# px(t) = 100 + 10*(t-99) on the ramp, so the trailing range first reaches
# 100pt = $1,000 at t=109 (start) and last reaches it at t=258, where the
# window [109,258] still holds the pre-ramp-adjacent price 200.0 (end).
CASES_FD4 = (
    ("episodes", _eps, ((109, 258),)),
    ("no_shock_before", lambda f: min(a for a, _b in f(VT, VM, MULT, SPAN,
                                                       THR)), 109),
    ("release_after_span", lambda f: max(b for _a, b in f(VT, VM, MULT, SPAN,
                                                          THR)), 258),
    ("empty_series", lambda f: tuple(f([], [], MULT, SPAN, THR)), ()),
    # a move of 90 points ($900) never reaches the $1,000 class
    ("below_threshold",
     lambda f: tuple(f(list(range(200)),
                       [100.0 + (9.0 * min(t - 100, 10) if t >= 100 else 0.0)
                        for t in range(200)], MULT, SPAN, THR)), ()),
)


def mutant_fd4_forward_window(vt, vm, mult, span=SPAN, thr_usd=THR):
    """NON-CAUSAL: the window looks FORWARD from t (the generator would be
    reading the future — the classic leak)."""
    vt = np.asarray(vt, dtype=np.int64)
    vm = np.asarray(vm, dtype=np.float64)
    if vt.size == 0:
        return []
    hot = np.zeros(vt.size, dtype=bool)
    for i in range(vt.size):
        j = int(np.searchsorted(vt, vt[i] + span, side="right"))
        w = vm[i:j]
        hot[i] = ((w.max() - w.min()) * mult) >= thr_usd
    return F._runs(vt, hot)


def mutant_fd4_no_mult(vt, vm, mult, span=SPAN, thr_usd=THR):
    """Dollars vs price units confused (the repo's oldest class of bug)."""
    return F.shock_episodes(vt, vm, 1.0, span, thr_usd)


def mutant_fd4_strict_threshold(vt, vm, mult, span=SPAN, thr_usd=THR):
    """`>` instead of `>=`: the boundary second is dropped."""
    if len(vt) == 0:
        return []
    rng = F.rolling_range_usd(vt, vm, mult, span)
    return F._runs(np.asarray(vt, dtype=np.int64), rng > thr_usd)


def mutant_fd4_whole_session_window(vt, vm, mult, span=SPAN, thr_usd=THR):
    """Expanding (not trailing) window: once shocked, shocked forever."""
    vt = np.asarray(vt, dtype=np.int64)
    vm = np.asarray(vm, dtype=np.float64)
    if vt.size == 0:
        return []
    hi = np.maximum.accumulate(vm)
    lo = np.minimum.accumulate(vm)
    return F._runs(vt, ((hi - lo) * mult) >= thr_usd)


MUTANTS_FD4 = (("forward_window", mutant_fd4_forward_window),
               ("dollars_not_applied", mutant_fd4_no_mult),
               ("strict_threshold", mutant_fd4_strict_threshold),
               ("expanding_window", mutant_fd4_whole_session_window))

# --- the trigger: first confirmation STRICTLY after the episode ends --------
CONFS = [10, 100, 269, 270, 270, 400]

CASES_TRIG = (
    ("strictly_after", lambda f: tuple(f(CONFS, 269)), (3, 4)),
    ("both_sides_same_sec", lambda f: len(f(CONFS, 269)), 2),
    ("earliest_only", lambda f: tuple(f(CONFS, 9)), (0,)),
    ("none_after", lambda f: tuple(f(CONFS, 400)), ()),
    ("empty", lambda f: tuple(f([], 5)), ()),
)


def mutant_trig_inclusive(conf_secs, end_sec):
    """`>=`: the confirmation that fired DURING the shock is taken."""
    cand = [i for i, cs in enumerate(conf_secs) if cs >= end_sec]
    if not cand:
        return []
    first = min(conf_secs[i] for i in cand)
    return [i for i in cand if conf_secs[i] == first]


def mutant_trig_one_only(conf_secs, end_sec):
    """Keeps a single side: the mirrored confirmation is silently lost."""
    out = F.first_confirmations_after(conf_secs, end_sec)
    return out[:1]


def mutant_trig_last(conf_secs, end_sec):
    """Last instead of first ('after the episode' read as 'the next one')."""
    cand = [i for i, cs in enumerate(conf_secs) if cs > end_sec]
    return cand[-1:] if cand else []


MUTANTS_TRIG = (("inclusive_end", mutant_trig_inclusive),
                ("single_side", mutant_trig_one_only),
                ("last_not_first", mutant_trig_last))

# --- insane-book episodes ---------------------------------------------------
TS = np.ones(60, dtype=bool)
SANE = np.ones(60, dtype=bool)
SANE[10:25] = False            # 15s wide-book episode
SANE[30:35] = False            # 5s flicker (below the 10s floor)
TS2 = TS.copy()
TS2[40:55] = False             # not two-sided: a book OUTAGE, not a wide book
SANE2 = SANE.copy()
SANE2[40:55] = False

CASES_INS = (
    ("episode_and_flicker", lambda f: tuple(f(TS, SANE, 10)), ((10, 24),)),
    ("flicker_at_5s_floor", lambda f: tuple(f(TS, SANE, 5)),
     ((10, 24), (30, 34))),
    ("outage_is_not_wide_book", lambda f: tuple(f(TS2, SANE2, 10)),
     ((10, 24),)),
    ("all_sane", lambda f: tuple(f(TS, np.ones(60, dtype=bool), 10)), ()),
)


def mutant_ins_no_min_len(two_sided, sane, min_len=10):
    """The flicker is promoted to an episode (no sustain requirement)."""
    return F.insane_episodes(two_sided, sane, 1)


def mutant_ins_counts_outages(two_sided, sane, min_len=10):
    """Book outages counted as wide-book episodes (D-054 confuses the two)."""
    bad = ~np.asarray(sane, dtype=bool)
    return [(a, b) for (a, b) in
            F._runs(np.arange(bad.size, dtype=np.int64), bad)
            if (b - a + 1) >= min_len]


MUTANTS_INS = (("no_min_length", mutant_ins_no_min_len),
               ("outages_count", mutant_ins_counts_outages))


# ===================================================================
# (3) the window detectors (F-D1 / F-D2 / F-D3) and F-D6
# ===================================================================
SESS = _S([(0, 1000), (1, 1000), (2, 1000)])

CASES_CLOSE = (
    ("phase_closes", lambda f: tuple(f(SESS)), (999, 1999, 2999)),
)


def mutant_close_boundaries_are_opens(s):
    ch = np.nonzero(s.phase_tag[1:] != s.phase_tag[:-1])[0] + 1
    return sorted(set([int(x) for x in ch.tolist()] + [int(s.n - 1)]))


def mutant_close_no_session_end(s):
    ch = np.nonzero(s.phase_tag[1:] != s.phase_tag[:-1])[0]
    return sorted(set(int(x) for x in ch.tolist()))


MUTANTS_CLOSE = (("boundary_is_open", mutant_close_boundaries_are_opens),
                 ("session_end_missing", mutant_close_no_session_end))

IV = ((100, 199), (500, 599))
CASES_IV = (
    ("before", lambda f: f(99, IV), False),
    ("first_second", lambda f: f(100, IV), True),
    ("last_second", lambda f: f(199, IV), True),
    ("just_after", lambda f: f(200, IV), False),
    ("between", lambda f: f(300, IV), False),
    ("second_window", lambda f: f(550, IV), True),
    ("empty", lambda f: f(550, ()), False),
)


def mutant_iv_exclusive_start(sec, iv):
    return any(a < sec <= b for a, b in iv)


def mutant_iv_first_only(sec, iv):
    return bool(iv) and iv[0][0] <= sec <= iv[0][1]


MUTANTS_IV = (("exclusive_start", mutant_iv_exclusive_start),
              ("first_window_only", mutant_iv_first_only))

# F-D6: beyond an extension level (side +1 = up-extension, phase 2 = NY).
# The phase field is load-bearing: a TOKYO opening range says nothing about a
# NY price (the H/L census's P3 target is REST_OF_WINDOW|segment).
CELLS = ((100, 120.0, +1, 2), (100, 80.0, -1, 2))
CASES_EXT = (
    ("inside", lambda f: f(100.0, 150, 2, CELLS), False),
    ("at_up_level", lambda f: f(120.0, 150, 2, CELLS), True),
    ("above_up_level", lambda f: f(130.0, 150, 2, CELLS), True),
    ("at_down_level", lambda f: f(80.0, 150, 2, CELLS), True),
    ("before_or_closes", lambda f: f(130.0, 99, 2, CELLS), False),
    ("other_segment", lambda f: f(130.0, 150, 1, CELLS), False),
    ("no_cells", lambda f: f(130.0, 150, 2, ()), False),
)


def mutant_ext_ignores_validity(mid, sec, phase, cells):
    """The level is used before its opening range has closed (look-ahead)."""
    for (_t1, px, side, p) in cells:
        if int(phase) != int(p):
            continue
        if side > 0 and mid >= px:
            return True
        if side < 0 and mid <= px:
            return True
    return False


def mutant_ext_side_blind(mid, sec, phase, cells):
    """Distance without direction: 'beyond' becomes 'anywhere below the up
    level' as well."""
    for (t1, px, _side, p) in cells:
        if sec >= t1 and int(phase) == int(p) and mid <= px:
            return True
    return False


def mutant_ext_phase_blind(mid, sec, phase, cells):
    """The segment scope dropped: a Tokyo opening range then 'explains' a NY
    price — the bug the first SI smoke run exposed (nearly every candidate
    tagged)."""
    for (t1, px, side, _p) in cells:
        if sec < t1:
            continue
        if side > 0 and mid >= px:
            return True
        if side < 0 and mid <= px:
            return True
    return False


MUTANTS_EXT = (("ignores_or_validity", mutant_ext_ignores_validity),
               ("side_blind", mutant_ext_side_blind),
               ("segment_blind", mutant_ext_phase_blind))


# ===================================================================
# green-only checks (no mutants needed: they are assertions on the data)
# ===================================================================
def test_spec_pin():
    # §10 is a PORT_M1_SPEC.md section, so that pin is the binding one.  The
    # M1.B pin is stale in the repo (defect FD-7) and is NOT asserted here.
    check("spec/m1_sha16", M.verify_spec(), M.SPEC_SHA16)


def test_fomc_calendar():
    d = F.fomc_release_dates()
    check("fomc/n_2021_2024", sum(1 for x in d if 2021 <= x.year <= 2024), 32)
    # "2023,Jan/Feb,31-1" -> the statement lands on the SECOND day, 2023-02-01
    check("fomc/split_month", dt.date(2023, 2, 1) in d, True)
    check("fomc/no_first_day", dt.date(2023, 1, 31) in d, False)
    check("fomc/plain", dt.date(2024, 12, 18) in d, True)


def test_welch():
    a = [10.0] * 100 + [20.0] * 100
    b = [10.0] * 100 + [12.0] * 100
    z, p = F.welch_p(a, b)
    check("welch/positive_z", z > 0, True)
    check("welch/p_small", p < 0.01, True)
    z2, p2 = F.welch_p(b, a)
    check("welch/symmetry", approx(z2, -z), True)
    check("welch/tail", approx(p2, 1.0 - p, 1e-9), True)
    check("welch/degenerate", math.isnan(F.welch_p([1.0], [2.0])[1]), True)


def test_rolling_range_gap():
    """A gap of insane seconds must SHORTEN the trailing window, never let it
    reach further back in observation count."""
    vt = [0, 1, 2, 500, 501]
    vm = [100.0, 100.0, 100.0, 200.0, 200.0]
    r = F.rolling_range_usd(vt, vm, 1.0, 150)
    check("roll/gap_forgets", approx(float(r[3]), 0.0), True)
    r2 = F.rolling_range_usd([0, 1, 2, 100], [100.0, 100.0, 100.0, 200.0],
                             1.0, 150)
    check("roll/in_window", approx(float(r2[3]), 100.0), True)


def test_conditional():
    v, n = F.conditional([-100.0, 0.0, 100.0, 300.0, float("nan")])
    check("conditional/mean", approx(v, 200.0), True)
    check("conditional/n", n, 2)


def test_merge_intervals():
    check("merge/adjacent", F.merge_intervals([(0, 9), (10, 19)]), [(0, 19)])
    check("merge/overlap", F.merge_intervals([(0, 15), (10, 19)]), [(0, 19)])
    check("merge/disjoint", F.merge_intervals([(30, 39), (0, 9)]),
          [(0, 9), (30, 39)])


def test_designed_family_bits():
    check("bits/unique", len(set(F.DISC_BIT.values())), len(F.DESIGNED))
    check("bits/fit_uint32", max(F.DISC_BIT.values()) < (1 << 32), True)
    check("bits/adding_disjoint",
          sorted(set(F.ADDING) & set(F.TAGGING)), [])


# ========================================================== the runner =======
def run_group(title, cases, impl, mutants):
    for (name, fn, want) in cases:
        try:
            got = fn(impl)
        except Exception as exc:                          # noqa: BLE001
            FAILURES.append("%s/%s: real implementation raised %s: %s"
                            % (title, name, type(exc).__name__, exc))
            continue
        check("%s/%s" % (title, name), got, want)
    caught = {}
    for (mname, mimpl) in mutants:
        broke = []
        for (name, fn, want) in cases:
            try:
                got = fn(mimpl)
            except Exception as exc:                      # noqa: BLE001
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
    test_fomc_calendar()
    test_welch()
    test_rolling_range_gap()
    test_conditional()
    test_merge_intervals()
    test_designed_family_bits()

    red = {}
    red["miner_holm"] = run_group("HOLM", CASES_HOLM, F.holm, MUTANTS_HOLM)
    red["miner_family_size"] = run_group("MULT", CASES_M, F.multiplicity_m,
                                         MUTANTS_M)
    red["fd4_shock_episodes"] = run_group("FD4", CASES_FD4, F.shock_episodes,
                                          MUTANTS_FD4)
    red["fd4_trigger"] = run_group("TRIG", CASES_TRIG,
                                   F.first_confirmations_after, MUTANTS_TRIG)
    red["fd4_insane_episodes"] = run_group("INS", CASES_INS,
                                           F.insane_episodes, MUTANTS_INS)
    red["fd1_phase_closes"] = run_group("CLOSE", CASES_CLOSE,
                                        F.phase_close_secs, MUTANTS_CLOSE)
    red["window_membership"] = run_group("IV", CASES_IV, F.in_intervals,
                                         MUTANTS_IV)
    red["fd6_extension"] = run_group("EXT", CASES_EXT, F.beyond_extension,
                                     MUTANTS_EXT)

    print("RED-FIRST EVIDENCE (mutant -> cases it breaks):")
    rows = []
    for group in sorted(red):
        for mname in sorted(red[group]):
            broke = red[group][mname]
            print("  %-22s %-24s %s" % (group, mname,
                                        ",".join(broke) or "NONE"))
            rows.append([group, mname, len(broke), ",".join(broke) or "NONE"])
    if not FAILURES:
        M.write_tsv(M.out_path(F.OUT_DIR, "fdisc_redfirst.tsv"),
                    F.SECTION + " red-first mutant evidence",
                    C.params_hash({"tests": "engine/port_m1/test_fdisc.py"}),
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
    print("\nALL PASS (%d mutants, all caught)"
          % sum(len(v) for v in red.values()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
