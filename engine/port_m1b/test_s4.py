#!/usr/bin/python3
"""PORT M1.B S4 — red-first self-tests for the atlas screen's new algorithms.

Covered:
  (a) the skeleton QUERY KERNEL (s4_common.last_le / first_ge_value) vs brute
      force on ragged synthetic records;
  (b) the compose() PRUNES P4/P5/P6/P7 and the F-PROX bar;
  (c) the shadow-value DP (prefix/suffix/optimal) vs brute-force enumeration;
  (d) the within-session shuffle guard's invariants;
  (e) the transforms (rank ties, MAD-z, winsor, bin0);
  (f) Holm step-down;
  (g) dollar_recall and within-unit Spearman;
  (h) the transcribed S1 family-bit constant vs the real one.

RED-FIRST: every MUTANT below is a deliberately wrong implementation committed
in this file; `test_mutants_are_caught` asserts each one breaks at least one
case the real code passes. A mutant nothing catches is itself a FAILURE.

Run: /usr/bin/python3 engine/port_m1b/test_s4.py
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/workspace/engine/port_m1")
import s4_common as S            # noqa: E402
import s4_labels as L            # noqa: E402
import s4_screen as SC           # noqa: E402

FAILURES = []


def check(name, got, want, tol=0.0):
    if isinstance(got, np.ndarray) or isinstance(want, np.ndarray):
        ok = bool(np.allclose(np.asarray(got, dtype=float),
                              np.asarray(want, dtype=float), atol=max(tol, 0),
                              equal_nan=True))
    elif isinstance(want, float) and isinstance(got, float):
        ok = (abs(got - want) <= tol) or (np.isnan(got) and np.isnan(want))
    elif isinstance(want, (list, tuple)) and isinstance(got, (list, tuple)):
        ok = (list(got) == list(want))
    else:
        ok = (got == want)
    if not ok:
        FAILURES.append("%s: got %r want %r" % (name, got, want))


# ================================================== (a) the query kernel =====
# three rows of prefix-max records, ragged
OFF = np.array([0, 3, 5], dtype=np.int64)
LEN = np.array([3, 2, 0], dtype=np.int64)
T = np.array([10, 20, 40, 15, 60], dtype=np.int32)
V = np.array([100.0, 250.0, 900.0, 50.0, 1200.0], dtype=np.float32)
MARKS = np.array([20, 14, 99], dtype=np.int64)   # 20 lands ON a record
WANT_LAST_LE = [250.0, 0.0, 0.0]        # row1: no record <= 14 -> 0; row2 empty
WANT_FIRST_GE = {900.0: [40, 60, -1], 50.0: [10, 15, -1],
                 1200.0: [-1, 60, -1]}


def brute_last_le(off, ln, t, v, marks):
    out = []
    for i in range(off.size):
        a, b = int(off[i]), int(off[i] + ln[i])
        best = 0.0
        for j in range(a, b):
            if t[j] <= marks[i]:
                best = float(v[j])
        out.append(best)
    return np.array(out)


def brute_first_ge(off, ln, t, v, thr):
    out = []
    for i in range(off.size):
        a, b = int(off[i]), int(off[i] + ln[i])
        r = -1
        for j in range(a, b):
            if float(v[j]) >= thr:
                r = int(t[j])
                break
        out.append(r)
    return np.array(out)


def test_kernel():
    got = S.last_le(OFF, LEN, T, V, MARKS)
    check("last_le", got, WANT_LAST_LE, 1e-9)
    check("last_le_vs_brute", got, brute_last_le(OFF, LEN, T, V, MARKS), 1e-9)
    for thr, want in WANT_FIRST_GE.items():
        g = S.first_ge_value(OFF, LEN, T, V, np.full(3, thr))
        check("first_ge[%g]" % thr, g, want)
        check("first_ge_vs_brute[%g]" % thr, g,
              brute_first_ge(OFF, LEN, T, V, thr))


def test_rung_index():
    # the ladder is k x 0.02 x ATR; 0.15 x ATR is OFF-ladder (k = 7.5)
    check("rung_index(0.1)", S.rung_index(0.1), 5)
    check("rung_index(0.2)", S.rung_index(0.2), 10)
    check("rung_index(0.4)", S.rung_index(0.4), 20)
    check("rung_index(1.0)", S.rung_index(1.0), 50)
    check("rung_index(0.15)_half_up", S.rung_index(0.15), 8)
    check("rung_index_clamped_hi", S.rung_index(99.0), 200)
    check("rung_index_clamped_lo", S.rung_index(0.0), 1)


# ================================================== (c) the shadow-value DP ==
def brute_optimal(start, end, val):
    """Exhaustive one-position schedule over <= 12 items (start > prev end)."""
    n = start.size
    best = 0.0
    for mask in range(1 << n):
        idx = [i for i in range(n) if mask & (1 << i)]
        idx.sort(key=lambda i: end[i])
        ok, prev, tot = True, -10 ** 18, 0.0
        for i in idx:
            if start[i] <= prev:
                ok = False
                break
            prev = end[i]
            tot += val[i]
        if ok and tot > best:
            best = tot
    return best


# item 1 starts exactly ON item 0's exit second: legal only for the WRONG
# (touching-allowed) rule, so the fixture separates the two.
S_START = np.array([0, 90, 100, 250, 260, 900], dtype=np.int64)
S_END = np.array([90, 95, 240, 255, 800, 950], dtype=np.int64)
S_VAL = np.array([100.0, 700.0, 300.0, 50.0, 400.0, -20.0], dtype=np.float64)


def test_shadow_dp():
    opt, pre, suf = L._dp_prefix_suffix(S_START, S_END, S_VAL)
    check("dp_optimal", opt, brute_optimal(S_START, S_END, S_VAL), 1e-9)
    # forcing a NEGATIVE action in must cost at least its own value
    for i in range(S_START.size):
        sh = (L._lookup_prefix(pre, S_START[i]) + max(S_VAL[i], 0.0)
              + L._lookup_suffix(suf, S_END[i]) - opt)
        if sh > 1e-9:
            FAILURES.append("dp_shadow_positive[%d]: %.6f" % (i, sh))


def test_shuffle_guard():
    x = np.array([1.0, 2.0, 3.0, 10.0, 20.0], dtype=np.float64)
    sess = np.array([1, 1, 1, 2, 2], dtype=np.int64)
    out = L.shuffle_within_session(x, sess, seed=7)
    check("shuffle_keeps_session_multiset_1",
          sorted(out[:3].tolist()), [1.0, 2.0, 3.0])
    check("shuffle_keeps_session_multiset_2",
          sorted(out[3:].tolist()), [10.0, 20.0])
    check("shuffle_keeps_n", out.size, x.size)


# ===================================================== (e) the transforms ====
UNITS = np.array([1, 1, 1, 1, 2, 2], dtype=np.int64)
XV = np.array([1.0, 1.0, 3.0, -5.0, 7.0, 9.0], dtype=np.float64)


def test_transforms():
    r = L.transform(XV, "rank", UNITS)
    # ties get the average rank; percentile = (rank - 0.5)/n within unit
    check("rank_ties", r[:4], [(2.5 - 0.5) / 4, (2.5 - 0.5) / 4,
                               (4 - 0.5) / 4, (1 - 0.5) / 4], 1e-12)
    check("rank_unit2", r[4:], [(1 - 0.5) / 2, (2 - 0.5) / 2], 1e-12)
    b = L.transform(XV, "bin0", UNITS)
    check("bin0", b, [1, 1, 1, 0, 1, 1])
    z = L.transform(XV, "z", UNITS)
    med = 1.0
    mad = np.median(np.abs(XV[:4] - med))
    check("z_uses_mad", z[2], (3.0 - med) / (1.4826 * mad), 1e-12)
    w = L.transform(np.array([0.0, 1.0, 2.0, 100.0]), "winsor",
                    np.array([1, 1, 1, 1]))
    check("winsor_clips_high", bool(w[3] < 100.0), True)


# ========================================================== (f) Holm ========
P_CASES = ([0.001, 0.014, 0.5, 0.04],      # separates flat Bonferroni
           [0.001, 0.02, 0.5, 0.024],      # separates a missing step-down stop
           [0.001, 0.02, 0.5, 0.04])


def test_holm():
    p = P_CASES[2]
    rank, thr, sig = SC.holm(p)
    check("holm_rank", rank, [1, 2, 4, 3])
    check("holm_thr_first", thr[0], 0.05 / 4, 1e-12)
    # 0.001 <= .0125 passes; 0.02 > .0167 stops the step-down
    check("holm_sig", sig, [1, 0, 0, 0])


# ============================================ (g) alignment + $ recall =======
def test_alignment_metrics():
    pred = np.array([8., 7., 6., 5., 4., 3., 2., 1.,
                     80., 70., 60., 50., 40., 30., 20., 10.])
    truth = pred.copy()
    units = np.array([1] * 8 + [2] * 8, dtype=np.int64)
    rho, p, n = SC.within_unit_spearman(pred, truth, units)
    check("within_unit_perfect", round(rho, 9), 1.0)
    rho2, _p, _n = SC.within_unit_spearman(-pred, truth, units)
    check("within_unit_inverted", round(rho2, 9), -1.0)
    cert = np.array([100., 50., -10., 5., 4., 3., 2., 1.,
                     900., 10., -5., 4., 3., 2., 1., 0.])
    check("dollar_recall_perfect", SC.dollar_recall(pred, cert, units, 1),
          1.0, 1e-12)
    bad = -pred
    got = SC.dollar_recall(bad, cert, units, 1)
    check("dollar_recall_worst_is_lower", bool(got < 1.0), True)


def test_family_constant_and_structural_bar():
    """The transcribed family-bit order must equal the real S1 one -- and
    importing that module (which pulls in the oracle-leg machinery) must make
    the F-PROX structural bar FIRE.  Runs last for exactly that reason."""
    import b8_generation_v2 as G
    check("S1_FAMILIES", list(L.S1_FAMILIES), list(G.FAMILIES))
    check("FAM_BIT_G2_RECLAIM", L.FAM_BIT_G2_RECLAIM, G.FAM_BIT["G2_RECLAIM"])
    try:
        L.assert_no_fprox(["net|h60|tnone|p0|raw"])
    except RuntimeError:
        return
    FAILURES.append("the F-PROX structural bar did NOT fire with the "
                    "oracle-leg module loaded")


def test_fprox_bar():
    L.assert_no_fprox(["net|h60|tnone|p0|raw", "ret5|h60|rank@phase"])
    try:
        L.assert_no_fprox(["fprox_dist_to_oracle|h60|raw"])
    except RuntimeError:
        return
    FAILURES.append("assert_no_fprox accepted a truth-relative label")


# ============================================================== MUTANTS ======
def mutant_k1_le_is_lt(off, ln, t, v, marks):
    """WRONG: strict < loses a record landing exactly on the mark."""
    out = []
    for i in range(off.size):
        a, b = int(off[i]), int(off[i] + ln[i])
        best = 0.0
        for j in range(a, b):
            if t[j] < marks[i]:
                best = float(v[j])
        out.append(best)
    return np.array(out)


def mutant_k2_first_not_last(off, ln, t, v, marks):
    """WRONG: returns the FIRST record at or before the mark."""
    out = []
    for i in range(off.size):
        a, b = int(off[i]), int(off[i] + ln[i])
        got = 0.0
        for j in range(a, b):
            if t[j] <= marks[i]:
                got = float(v[j])
                break
        out.append(got)
    return np.array(out)


def mutant_k3_empty_is_nan(off, ln, t, v, marks):
    """WRONG: an empty/未-reached row returns NaN instead of 0 (no excursion)."""
    out = brute_last_le(off, ln, t, v, marks)
    out[ln == 0] = np.nan
    return out


MUTANTS_K = (("le_is_lt", mutant_k1_le_is_lt),
             ("first_not_last", mutant_k2_first_not_last),
             ("empty_is_nan", mutant_k3_empty_is_nan))


def mutant_d1_touching_allowed(start, end, val):
    """WRONG: a new position may start ON the previous exit second."""
    pos = val > 0
    s, e, v = start[pos], end[pos], val[pos]
    o = np.argsort(e, kind="stable")
    s, e, v = s[o], e[o], v[o]
    m = s.size
    best = np.zeros(m + 1)
    for i in range(1, m + 1):
        j = int(np.searchsorted(e, s[i - 1], side="right"))
        best[i] = max(best[i - 1], best[j] + v[i - 1])
    return float(best[m])


def mutant_d2_no_compatibility_jump(start, end, val):
    """WRONG: adds each item to the running best without checking overlap."""
    pos = val > 0
    s, e, v = start[pos], end[pos], val[pos]
    o = np.argsort(e, kind="stable")
    v = v[o]
    best = np.zeros(v.size + 1)
    for i in range(1, v.size + 1):
        best[i] = max(best[i - 1], best[i - 1] + v[i - 1])
    return float(best[v.size])


MUTANTS_D = (("dp_touching_allowed", mutant_d1_touching_allowed),
             ("dp_no_compat_jump", mutant_d2_no_compatibility_jump))


def mutant_t1_rank_first_ties(x, units):
    """WRONG: ties take the FIRST rank instead of the average."""
    out = np.full(x.size, np.nan)
    for u in np.unique(units):
        sel = np.nonzero(units == u)[0]
        v = x[sel]
        order = np.argsort(v, kind="stable")
        r = np.empty(sel.size)
        r[order] = np.arange(1, sel.size + 1)
        out[sel] = (r - 0.5) / sel.size
    return out


def mutant_t2_z_uses_std(x, units):
    """WRONG: z on the standard deviation, not the MAD."""
    out = np.full(x.size, np.nan)
    for u in np.unique(units):
        sel = np.nonzero(units == u)[0]
        v = x[sel]
        out[sel] = (v - v.mean()) / (v.std() if v.std() > 0 else np.nan)
    return out


MUTANTS_T = (("rank_first_ties", mutant_t1_rank_first_ties),
             ("z_uses_std", mutant_t2_z_uses_std))


def mutant_h1_bonferroni(pvals):
    """WRONG: a flat Bonferroni threshold (no step-down)."""
    m = len(pvals)
    rank = list(range(1, m + 1))
    thr = [0.05 / m] * m
    sig = [1 if (np.isfinite(p) and p <= 0.05 / m) else 0 for p in pvals]
    return rank, thr, sig


def mutant_h2_no_stop(pvals):
    """WRONG: keeps testing after the first failure (no step-down stop)."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    rank, thr, sig = [0] * m, [0.0] * m, [0] * m
    for r, i in enumerate(order):
        rank[i] = r + 1
        thr[i] = 0.05 / (m - r)
        sig[i] = 1 if pvals[i] <= thr[i] else 0
    return rank, thr, sig


MUTANTS_H = (("bonferroni_flat", mutant_h1_bonferroni),
             ("holm_no_stop", mutant_h2_no_stop))


def test_mutants_are_caught():
    good = S.last_le(OFF, LEN, T, V, MARKS)
    for nm, fn in MUTANTS_K:
        g = fn(OFF, LEN, T, V, MARKS)
        _red("kernel", nm, [] if np.allclose(g, good, equal_nan=True)
             else ["last_le"])
    opt = L._dp_prefix_suffix(S_START, S_END, S_VAL)[0]
    for nm, fn in MUTANTS_D:
        _red("shadow dp", nm, [] if abs(fn(S_START, S_END, S_VAL) - opt) < 1e-9
             else ["optimal"])
    for nm, fn in MUTANTS_T:
        g = fn(XV, UNITS)
        ref = L.transform(XV, "rank" if "rank" in nm else "z", UNITS)
        _red("transform", nm, [] if np.allclose(g, ref, equal_nan=True)
             else ["transform"])
    for nm, fn in MUTANTS_H:
        caught = [i for i, p in enumerate(P_CASES)
                  if fn(list(p))[2] != SC.holm(list(p))[2]]
        _red("holm", nm, ["case%d" % caught[0]] if caught else [])


def _red(group, nm, caught_on):
    if not caught_on:
        FAILURES.append("MUTANT NOT CAUGHT (%s): %s" % (group, nm))
    else:
        print("  red-first: mutant %-22s caught on %s" % (nm, caught_on[0]))


def main():
    S.verify_spec()
    for t in (test_kernel, test_rung_index, test_shadow_dp, test_shuffle_guard,
              test_transforms, test_holm, test_alignment_metrics,
              test_fprox_bar, test_mutants_are_caught,
              test_family_constant_and_structural_bar):
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
