#!/usr/bin/python3
"""PORT M1 Track B — red-first self-tests for the two NEW nontrivial algorithms.

  (a) the §4 level touch / re-arm / virgin state machine   (b3_levels.touch_scan
      + b3_levels.classify_touch)
  (b) the §5 volume-profile value-area growth              (b4_profiles.poc_index
      + b4_profiles.value_area)

RED-FIRST LAW (repo): a test only counts if it is shown to FAIL on a broken
implementation.  Every MUTANT below is a deliberately wrong version of the
algorithm, committed in this file; `test_mutants_are_caught` asserts that each
one breaks at least one of the synthetic cases the real implementation passes.
A mutant that nothing catches is itself a test failure (the suite refuses to
pass on toothless assertions).

Run: /usr/bin/python3 engine/port_m1/test_m1.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import b3_levels as B3
import b4_profiles as B4
import m1_common as M

FAILURES = []


def check(name, got, want):
    ok = (got == want)
    if isinstance(want, (list, tuple)) and isinstance(got, np.ndarray):
        ok = list(got) == list(want)
    if not ok:
        FAILURES.append("%s: got %r want %r" % (name, got, want))
    return ok


# ============================================ (a) touch / re-arm / virgin =====
TOL = 1.0
PH_FLAT = None          # built per case


def _mk(dist_segments, phase_segments=None):
    """dist_segments = [(value, n_seconds), ...] -> (dist, phase) arrays."""
    d = []
    for v, n in dist_segments:
        d.extend([v] * n)
    d = np.array(d, dtype=np.float64)
    if phase_segments is None:
        ph = np.zeros(d.size, dtype=np.int8)
    else:
        p = []
        for v, n in phase_segments:
            p.extend([v] * n)
        ph = np.array(p, dtype=np.int8)
    return d, ph


# CASE A1  300 far seconds then a near second -> exactly one touch at 300
A1_dist, A1_ph = _mk([(5.0, 300), (0.5, 10), (5.0, 100)])
A1_touches, A1_first = [300], 300

# CASE A2  price sits ON the level from the start: never armed -> NO touch,
#          but the level is NOT virgin (D-050(d) is arming-independent)
A2_dist, A2_ph = _mk([(0.5, 100), (5.0, 100), (0.5, 100)])
A2_touches, A2_first = [], 0

# CASE A3  a second touch needs a FRESH 300s away run: 50s away is not enough,
#          another 300s away is
A3_dist, A3_ph = _mk([(5.0, 300), (0.5, 5), (5.0, 50), (0.5, 5), (5.0, 300),
                      (0.5, 5)])
A3_touches, A3_first = [300, 660], 300

# CASE A4  phase change re-arms immediately (only 10s away since the touch)
A4_dist, A4_ph = _mk([(5.0, 300), (0.5, 5), (5.0, 10), (0.5, 20)],
                     [(0, 300), (0, 5), (0, 10), (1, 20)])
A4_touches, A4_first = [300, 315], 300

# CASE A5  the tol..2*tol band is NOT "away": 400s at 1.5*tol never arms
A5_dist, A5_ph = _mk([(1.5, 400), (0.5, 10)])
A5_touches, A5_first = [], 400

# CASE A6  300 far seconds that are never CONSECUTIVE (far/near-band alternating)
#          must not arm: the rule is a 300s RUN, not 300 seconds in total
A6_dist = np.array(([5.0, 1.5] * 300) + [0.5] * 5, dtype=np.float64)
A6_ph = np.zeros(A6_dist.size, dtype=np.int8)
A6_touches, A6_first = [], 600

CASES_A = (("A1", A1_dist, A1_ph, A1_touches, A1_first),
           ("A2", A2_dist, A2_ph, A2_touches, A2_first),
           ("A3", A3_dist, A3_ph, A3_touches, A3_first),
           ("A4", A4_dist, A4_ph, A4_touches, A4_first),
           ("A5", A5_dist, A5_ph, A5_touches, A5_first),
           ("A6", A6_dist, A6_ph, A6_touches, A6_first))


def run_cases_a(fn):
    out = []
    for (nm, d, ph, _wt, _wf) in CASES_A:
        t, f = fn(d, ph, 0, TOL)
        out.append((nm, list(int(x) for x in t), int(f)))
    return out


def test_touch_state_machine():
    for (nm, d, ph, want_t, want_f) in CASES_A:
        t, f = B3.touch_scan(d, ph, 0, TOL)
        check("touch_scan[%s].touches" % nm, list(int(x) for x in t), want_t)
        check("touch_scan[%s].first_near" % nm, int(f), want_f)


# ---- classify_touch: REJECT / BREAK / RECLAIM ------------------------------
def test_classify_touch():
    secs = np.arange(2000, dtype=np.int64)
    # approached from ABOVE (app=+1); after the touch the mid runs back up by
    # 3.0 >= reject_move 2.0 -> REJECT at second 1005
    diff = np.concatenate([np.full(1000, 5.0), np.full(1, 0.5),
                           np.full(4, 0.5), np.full(995, 3.0)])
    oc, osec, rs, bs, cs = B3.classify_touch(diff, secs, 1000, 1, TOL, 2.0)
    check("classify.REJECT.outcome", oc, B3.OUTCOME_REJECT)
    check("classify.REJECT.sec", osec, 1005)
    check("classify.REJECT.break", bs, -1)

    # break: holds 60s beyond -tol, then reclaims and holds 120s back inside
    diff = np.concatenate([np.full(1000, 5.0), np.full(1, 0.5),
                           np.full(100, -3.0), np.full(899, 0.0)])
    oc, osec, rs, bs, cs = B3.classify_touch(diff, secs, 1000, 1, TOL, 2.0)
    check("classify.BREAK.outcome", oc, B3.OUTCOME_BREAK)
    check("classify.BREAK.sec", osec, 1060)
    check("classify.RECLAIM.sec", cs, 1220)

    # a 59s excursion beyond the level is NOT a break
    diff = np.concatenate([np.full(1000, 5.0), np.full(1, 0.5),
                           np.full(59, -3.0), np.full(940, 0.0)])
    oc, osec, rs, bs, cs = B3.classify_touch(diff, secs, 1000, 1, TOL, 2.0)
    check("classify.NOBREAK.break_sec", bs, -1)
    check("classify.NOBREAK.outcome", oc, B3.OUTCOME_NONE)


# ---------------------------------------------------------------- MUTANTS ---
def mutant_a1_arm_at_tol(dist, phase_v, active_from, tol):
    """WRONG: arms while merely outside tol (spec: > 2 x tol)."""
    return _generic_scan(dist, phase_v, active_from, tol, arm_mult=1.0,
                         disarm=True, phase_rearm=True, cumulative=False)


def mutant_a2_no_disarm(dist, phase_v, active_from, tol):
    """WRONG: every near second is a touch (no disarm after a touch)."""
    return _generic_scan(dist, phase_v, active_from, tol, arm_mult=2.0,
                         disarm=False, phase_rearm=True, cumulative=False)


def mutant_a3_cumulative_arm(dist, phase_v, active_from, tol):
    """WRONG: counts CUMULATIVE seconds away instead of a consecutive run."""
    return _generic_scan(dist, phase_v, active_from, tol, arm_mult=2.0,
                         disarm=True, phase_rearm=True, cumulative=True)


def mutant_a4_no_phase_rearm(dist, phase_v, active_from, tol):
    """WRONG: ignores the phase-boundary re-arm."""
    return _generic_scan(dist, phase_v, active_from, tol, arm_mult=2.0,
                         disarm=True, phase_rearm=False, cumulative=False)


def mutant_a5_virgin_from_touches(dist, phase_v, active_from, tol):
    """WRONG: virginity taken from ARMED touches, not from any approach."""
    t, _f = B3.touch_scan(dist, phase_v, active_from, tol)
    return t, (int(t[0]) if len(t) else -1)


def _generic_scan(dist, phase_v, active_from, tol, arm_mult, disarm,
                  phase_rearm, cumulative):
    n = dist.size
    near = np.isfinite(dist) & (dist <= tol)
    far = np.isfinite(dist) & (dist > arm_mult * tol)
    near[:active_from] = False
    far[:active_from] = False
    armed = False
    run = 0
    cum = 0
    touches = []
    first = -1
    for i in range(active_from, n):
        if phase_rearm and i > 0 and phase_v[i] != phase_v[i - 1]:
            armed = True
        if far[i]:
            run += 1
            cum += 1
        else:
            run = 0
        if (cum if cumulative else run) >= B3.ARM_SECONDS:
            armed = True
        if near[i]:
            if first < 0:
                first = i
            if armed or not disarm:
                touches.append(i)
                if disarm:
                    armed = False
                    run = 0
                    cum = 0
    return np.array(touches, dtype=np.int64), first


MUTANTS_A = (("arm_at_tol", mutant_a1_arm_at_tol),
             ("no_disarm", mutant_a2_no_disarm),
             ("cumulative_arm", mutant_a3_cumulative_arm),
             ("no_phase_rearm", mutant_a4_no_phase_rearm),
             ("virgin_from_touches", mutant_a5_virgin_from_touches))


# ============================================ (b) value-area growth ==========
# CASE B1  symmetric, tie between the two neighbours -> LEFTMOST wins
P1 = np.array([1.0, 2.0, 10.0, 2.0, 1.0])          # total 16, need 11.2
P1_poc, P1_va = 2, (1, 2)
# CASE B2  asymmetric -> the higher neighbour is taken first
P2 = np.array([1.0, 5.0, 10.0, 3.0, 1.0])          # total 20, need 14.0
P2_poc, P2_va = 2, (1, 2)
# CASE B3  exact tie again, but the low side is the SMALLER price -> leftmost
P3 = np.array([0.0, 4.0, 10.0, 4.0, 0.0])         # total 18, need 12.6
P3_poc, P3_va = 2, (1, 2)
# CASE B4  two equal maxima -> POC is the LEFTMOST
P4 = np.array([5.0, 10.0, 3.0, 10.0, 1.0])
P4_poc = 1
# CASE P5  multi-step growth, both steps resolved LEFT on ties
#          total 12, need 8.4: 7 -> 8 (lo=1) -> 9 (lo=0) >= 8.4
P5 = np.array([1.0, 1.0, 7.0, 1.0, 1.0, 1.0])
P5_poc, P5_va = 2, (0, 2)
# CASE P6  the 70% test is >=, not >: acc lands EXACTLY on the threshold and
#          growth must stop there (total 20, need 14.0, 10 -> 14 -> stop)
P6 = np.array([1.0, 4.0, 10.0, 4.0, 1.0])
P6_poc, P6_va = 2, (1, 2)

CASES_B = (("P1", P1, P1_poc, P1_va), ("P2", P2, P2_poc, P2_va),
           ("P3", P3, P3_poc, P3_va), ("P5", P5, P5_poc, P5_va),
           ("P6", P6, P6_poc, P6_va))


def test_value_area():
    for (nm, sm, want_poc, want_va) in CASES_B:
        p = B4.poc_index(sm)
        check("poc[%s]" % nm, p, want_poc)
        check("value_area[%s]" % nm, B4.value_area(sm, p), want_va)
    check("poc[P4]", B4.poc_index(P4), P4_poc)


def test_kernel_mass():
    """The 5-tick triangular kernel must preserve mass on a padded profile."""
    raw = np.array([0, 0, 3, 9, 4, 1, 0, 0], dtype=np.int64)
    sm = B4.smooth(raw)
    check("kernel_mass", round(float(sm.sum()), 9), round(float(raw.sum()), 9))
    check("kernel_shape", sm.size, raw.size)


def test_profile_objects_vs_bruteforce():
    """profile_objects on a hand-made tape vs an independently written
    unsmoothed histogram (the §7-B4 brute-force check, in miniature)."""
    ticks = np.array([100, 101, 101, 102, 102, 102, 103, 108], dtype=np.int64)
    sizes = np.array([1, 2, 3, 10, 10, 10, 2, 1], dtype=np.int64)
    b0, raw = B4.build_profile(ticks, sizes)
    brute = {}
    for t, s in zip(ticks.tolist(), sizes.tolist()):
        brute[t] = brute.get(t, 0) + s
    for t, v in brute.items():
        check("brute[%d]" % t, int(raw[t - b0]), v)
    check("brute.total", int(raw.sum()), int(sizes.sum()))
    o = B4.profile_objects(b0, raw, 1.0)
    check("brute.poc", o["poc_tick"], 102)          # 30 is the modal bin
    # inside the traded range 100..108 the mean bin volume is 39/9 = 4.333;
    # 1% of that is 0.0433, so the four EMPTY bins 104..107 are single prints
    # and every traded bin (incl. the lone print at 108, volume 1) is not.
    sp = set(o["single_print_ticks"].tolist())
    check("brute.single_prints", sorted(sp), [104, 105, 106, 107])


# ---------------------------------------------------------------- MUTANTS ---
def mutant_b1_tie_rightmost(sm, poc, fraction=B4.VA_FRACTION):
    """WRONG: ties resolved to the RIGHT neighbour."""
    n, total = sm.size, float(sm.sum())
    need = fraction * total
    lo = hi = poc
    acc = float(sm[poc])
    while acc < need and (lo > 0 or hi < n - 1):
        vlo = float(sm[lo - 1]) if lo > 0 else float("-inf")
        vhi = float(sm[hi + 1]) if hi < n - 1 else float("-inf")
        if vlo > vhi:
            lo -= 1
            acc += vlo
        else:
            hi += 1
            acc += vhi
    return lo, hi


def mutant_b2_pair_growth(sm, poc, fraction=B4.VA_FRACTION):
    """WRONG: grows BOTH neighbours every step (a common VA implementation)."""
    n, total = sm.size, float(sm.sum())
    need = fraction * total
    lo = hi = poc
    acc = float(sm[poc])
    while acc < need and (lo > 0 or hi < n - 1):
        if lo > 0:
            lo -= 1
            acc += float(sm[lo])
        if hi < n - 1:
            hi += 1
            acc += float(sm[hi])
    return lo, hi


def mutant_b3_overshoot(sm, poc, fraction=B4.VA_FRACTION):
    """WRONG: uses > instead of >= when testing the 70% stop (adds one bin)."""
    n, total = sm.size, float(sm.sum())
    need = fraction * total
    lo = hi = poc
    acc = float(sm[poc])
    while acc <= need and (lo > 0 or hi < n - 1):
        vlo = float(sm[lo - 1]) if lo > 0 else float("-inf")
        vhi = float(sm[hi + 1]) if hi < n - 1 else float("-inf")
        if vlo > vhi or (vlo == vhi and lo > 0):
            lo -= 1
            acc += vlo
        else:
            hi += 1
            acc += vhi
    return lo, hi


def mutant_b4_poc_rightmost(sm):
    """WRONG: argmax resolved to the RIGHTMOST bin on ties."""
    return int(sm.size - 1 - np.argmax(sm[::-1]))


MUTANTS_B_VA = (("tie_rightmost", mutant_b1_tie_rightmost),
                ("pair_growth", mutant_b2_pair_growth),
                ("overshoot", mutant_b3_overshoot))
MUTANTS_B_POC = (("poc_rightmost", mutant_b4_poc_rightmost),)


# =============================================== the red-first assertions ====
def test_mutants_are_caught():
    """Each mutant must DIFFER from the expected answer on >= 1 synthetic case."""
    good_a = run_cases_a(B3.touch_scan)
    for (nm, fn) in MUTANTS_A:
        got = run_cases_a(fn)
        diffs = [g[0] for g, w in zip(got, good_a) if g != w]
        if not diffs:
            FAILURES.append("MUTANT NOT CAUGHT (state machine): %s" % nm)
        else:
            print("  red-first: mutant %-22s caught on case(s) %s"
                  % (nm, ",".join(diffs)))

    for (nm, fn) in MUTANTS_B_VA:
        diffs = []
        for (cn, sm, want_poc, want_va) in CASES_B:
            if fn(sm, B4.poc_index(sm)) != want_va:
                diffs.append(cn)
        if not diffs:
            FAILURES.append("MUTANT NOT CAUGHT (value area): %s" % nm)
        else:
            print("  red-first: mutant %-22s caught on case(s) %s"
                  % (nm, ",".join(diffs)))
    for (nm, fn) in MUTANTS_B_POC:
        if fn(P4) == P4_poc:
            FAILURES.append("MUTANT NOT CAUGHT (poc): %s" % nm)
        else:
            print("  red-first: mutant %-22s caught on case P4" % nm)


def main():
    M.verify_spec()
    for t in (test_touch_state_machine, test_classify_touch, test_value_area,
              test_kernel_mass, test_profile_objects_vs_bruteforce,
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
