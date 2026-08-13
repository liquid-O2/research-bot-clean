#!/usr/bin/python3
"""PORT M0 census self-tests — deterministic, payload-free, no RNG.

Covers the two nontrivial algorithms of the census lane, red-first:

  (a) the causal ZigZag confirmation logic (spec §8 sub-pass 1)
      on a synthetic mid path with hand-derived pivots — pivot prices,
      confirmation seconds, sides, first-occurrence extremes, and the law that
      confirmation happens at the FIRST second the retrace REACHES the
      threshold (>=, not >), including under a per-second (phase-varying)
      threshold.

  (b) the weighted-interval DP (spec §8 sub-pass 3) on a hand-computed
      5-candidate case plus each level of the §1 tie-break order
      (earlier decision-second, then higher value, then lower instrument_id).

  (c) the path-skeleton claim itself: prefix-maxima sequences answer
      MFE / MAE / t_wall for ANY wall, checked against brute force.

Each of (a) and (b) carries a committed MUTANT — a copy of the production
function with exactly one documented defect — and the suite asserts the mutant
FAILS the same assertions.  A test that cannot fail proves nothing.

Run:  /usr/bin/python3 engine/port_m0/test_census.py
"""
import datetime as dt
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import census_common as X
import c_c_roster as CC

FAILS = []


def check(name, got, want):
    if got != want:
        FAILS.append("%s\n     got  %r\n     want %r" % (name, got, want))
        print("  FAIL %s" % name)
        return False
    print("  ok   %s" % name)
    return True


def check_close(name, got, want, tol=1e-9):
    ok = (abs(got - want) <= tol)
    if not ok:
        FAILS.append("%s: got %r want %r" % (name, got, want))
        print("  FAIL %s (got %r want %r)" % (name, got, want))
    else:
        print("  ok   %s" % name)
    return ok


def expect_fail(name, fn):
    """The mutant must break at least one assertion."""
    global FAILS
    hidden = []
    saved, FAILS = FAILS, hidden
    try:
        fn()
    except Exception as e:                                  # noqa: BLE001
        hidden.append("raised %r" % (e,))
    finally:
        broke = len(FAILS) > 0
        FAILS = saved
    if broke:
        print("  ok   %s (mutant caught: %d assertion(s) broke)" % (name, len(hidden)))
        return True
    FAILS.append("%s: MUTANT NOT CAUGHT — the test cannot fail" % name)
    print("  FAIL %s: MUTANT NOT CAUGHT" % name)
    return False


# ============================================================ (a) ZigZag =====
# Hand-built path.  thr = 3.0 price units throughout.
#  sec : 0    1    2    3    4    5    6    7    8    9   10   11   12
#  px  : 100  101  102  103  104  105  105  104  103  102  101  100   99
#  sec : 13   14   15   16   17   18   19   20   21   22   23
#  px  : 100  101  102  103  104  105  106  105  104  103  102
#
# Derivation (thr = 3):
#   sec 3  price 103 is 3 above the running low 100@0  -> confirm LOW  (100, sec 0)
#   sec 9  price 102 is 3 below the running high 105@5 -> confirm HIGH (105, sec 5)
#          the high is stamped at sec 5, the FIRST second 105 was reached,
#          not sec 6 where it was merely equalled
#   sec 15 price 102 is 3 above the running low  99@12 -> confirm LOW  (99, sec 12)
#   sec 22 price 103 is 3 below the running high 106@19-> confirm HIGH (106, sec 19)
PATH_PX = [100, 101, 102, 103, 104, 105, 105, 104, 103, 102, 101, 100, 99,
           100, 101, 102, 103, 104, 105, 106, 105, 104, 103, 102]
PATH_SECS = list(range(len(PATH_PX)))
PATH_MIDS = [float(p) for p in PATH_PX]
THR = 3.0

WANT_PIVOTS = [(100.0, 0, 3, 1),
               (105.0, 5, 9, -1),
               (99.0, 12, 15, 1),
               (106.0, 19, 22, -1)]


def _mutant_zigzag_strict(secs, mids, thr):
    """MUTANT of zigzag_scan: confirms on `>` instead of `>=`, i.e. it misses
    the FIRST second at which the retrace exactly REACHES the threshold and
    fires one or more seconds late."""
    out = []
    n = len(secs)
    if n < 2:
        return out
    hi = lo = mids[0]
    hi_s = lo_s = secs[0]
    d = 0
    for i in range(1, n):
        m, s, t = mids[i], secs[i], thr[i]
        if d == 1:
            if m > hi:
                hi, hi_s = m, s
            elif (hi - m) > t:                       # <-- the single defect
                out.append((hi, hi_s, s, -1)); d = -1; lo, lo_s = m, s
        elif d == -1:
            if m < lo:
                lo, lo_s = m, s
            elif (m - lo) > t:                       # <-- the single defect
                out.append((lo, lo_s, s, 1)); d = 1; hi, hi_s = m, s
        else:
            if m > hi:
                hi, hi_s = m, s
            if m < lo:
                lo, lo_s = m, s
            dn, up = (hi - m) > t, (m - lo) > t      # <-- the single defect
            if dn and up:
                if hi_s <= lo_s:
                    up = False
                else:
                    dn = False
            if dn:
                out.append((hi, hi_s, s, -1)); d = -1; lo, lo_s = m, s
            elif up:
                out.append((lo, lo_s, s, 1)); d = 1; hi, hi_s = m, s
    return out


def _zigzag_assertions(scan):
    piv = scan(PATH_SECS, PATH_MIDS, [THR] * len(PATH_MIDS))
    check("a1 pivot count", len(piv), len(WANT_PIVOTS))
    check("a2 pivots (price, pivot_sec, confirmation_sec, side)",
          [(p[0], p[1], p[2], p[3]) for p in piv], WANT_PIVOTS)
    if len(piv) >= 2:
        check("a3 extreme keeps the FIRST second it was reached (105 @ sec 5, "
              "not sec 6)", piv[1][1], 5)
        check("a4 confirmation is the FIRST second the retrace REACHES thr "
              "(sec 9, where 105-102 == 3 exactly)", piv[1][2], 9)


def test_zigzag():
    print("(a) causal ZigZag confirmation logic — spec §8 sub-pass 1")
    _zigzag_assertions(CC.zigzag_scan)

    # the retrace at the second BEFORE confirmation is strictly under thr
    check_close("a5 retrace at sec 8 is 2.0 (< thr)", 105.0 - PATH_MIDS[8], 2.0)
    check_close("a6 retrace at sec 9 is 3.0 (== thr)", 105.0 - PATH_MIDS[9], 3.0)

    # per-second (phase-varying) threshold: the test at second t uses thr[t], so
    # raising the threshold from sec 9 onward must push the confirmation later.
    thr = [3.0] * len(PATH_MIDS)
    for i in range(9, len(thr)):
        thr[i] = 5.0
    piv = CC.zigzag_scan(PATH_SECS, PATH_MIDS, thr)
    check("a7 phase-varying thr: first pivot unchanged (confirmed at sec 3 "
          "under thr=3)", piv[0][:4], (100.0, 0, 3, 1))
    check("a8 phase-varying thr: the HIGH now confirms at sec 11 (105-100 == 5)",
          piv[1][:4], (105.0, 5, 11, -1))

    # gaps in the valid-second series must not shift the confirmation second
    keep = [i for i in range(len(PATH_MIDS)) if i not in (6, 7, 8)]
    piv = CC.zigzag_scan([PATH_SECS[i] for i in keep],
                         [PATH_MIDS[i] for i in keep],
                         [THR] * len(keep))
    check("a9 gapped valid seconds: HIGH still (105, sec 5) confirmed at sec 9",
          piv[1][:4], (105.0, 5, 9, -1))

    # a monotone path confirms exactly one pivot (the opening extreme)
    up = [float(100 + i) for i in range(20)]
    piv = CC.zigzag_scan(list(range(20)), up, [THR] * 20)
    check("a10 monotone rise confirms exactly one LOW pivot at the anchor",
          [(p[0], p[1], p[2], p[3]) for p in piv], [(100.0, 0, 3, 1)])

    expect_fail("a11 RED: mutant (`>` instead of `>=`) is caught",
                lambda: _zigzag_assertions(_mutant_zigzag_strict))
    print("")


# ================================================================= (b) DP ====
# start, end, value, decision_sec, iid, ident
CASE_5 = [
    (0, 10, 100.0, 0, 1, "A"),
    (5, 20, 150.0, 5, 1, "B"),
    (11, 25, 120.0, 11, 1, "C"),
    (26, 40, 90.0, 26, 1, "D"),
    (0, 40, 210.0, 0, 1, "E"),
]
# Hand computation (a new position may start STRICTLY after the previous exit):
#   E alone .................. 210   (E overlaps every other item)
#   B then D ................. 240   (B ends 20, D starts 26)
#   A then C ................. 220
#   A then C then D .......... 310   (10 < 11, 25 < 26)   <-- maximum, unique
#   C then D ................. 210 ; A then D .. 190 ; A .. 100 ; C .. 120
WANT_5_TOTAL = 310.0
WANT_5_PICK = ["A", "C", "D"]

# §1 tie-break 1: equal totals -> earlier decision-second first
CASE_TB_DEC = [
    (0, 10, 100.0, 0, 1, "X"),
    (2, 10, 100.0, 2, 1, "Y"),
    (11, 20, 50.0, 11, 1, "Z"),
]
# §1 tie-break 2: equal totals, equal decision-second -> higher value
CASE_TB_VAL = [
    (0, 10, 100.0, 0, 1, "P"),
    (11, 20, 50.0, 11, 1, "Z1"),
    (0, 15, 120.0, 0, 1, "Q"),
    (16, 20, 30.0, 16, 1, "Z2"),
]
# §1 tie-break 3: equal totals, equal decision-second, equal value -> lower iid
CASE_TB_IID = [
    (0, 10, 100.0, 0, 7, "M"),
    (0, 10, 100.0, 0, 3, "N"),
]
# one position at a time: touching intervals are NOT compatible
CASE_TOUCH = [
    (0, 10, 100.0, 0, 1, "S1"),
    (10, 20, 100.0, 10, 1, "S2"),
]
# values <= 0 are never scheduled (§8 sub-pass 3 "values>0 only")
CASE_NEG = [
    (0, 10, -50.0, 0, 1, "NEG"),
    (11, 20, 40.0, 11, 1, "POS"),
]


def _dp_assertions():
    t, p = CC.dp_schedule(list(CASE_5))
    check_close("b1 five-candidate total", t, WANT_5_TOTAL)
    check("b2 five-candidate schedule", p, WANT_5_PICK)

    t, p = CC.dp_schedule(list(CASE_TB_DEC))
    check_close("b3 tie-break total (decision-second case)", t, 150.0)
    check("b4 tie-break 1: earlier decision-second wins", p, ["X", "Z"])

    t, p = CC.dp_schedule(list(CASE_TB_VAL))
    check_close("b5 tie-break total (value case)", t, 150.0)
    check("b6 tie-break 2: higher value wins at equal decision-second",
          p, ["Q", "Z2"])

    t, p = CC.dp_schedule(list(CASE_TB_IID))
    check_close("b7 tie-break total (iid case)", t, 100.0)
    check("b8 tie-break 3: lower instrument_id wins", p, ["N"])


def test_dp():
    print("(b) weighted-interval DP — spec §8 sub-pass 3, §1 tie-breaks")
    _dp_assertions()

    t, p = CC.dp_schedule(list(CASE_TOUCH))
    check_close("b9 touching intervals: only one position seatable", t, 100.0)
    check("b10 touching intervals: earlier decision-second taken", p, ["S1"])

    t, p = CC.dp_schedule(list(CASE_NEG))
    check_close("b11 non-positive values are not scheduled", t, 40.0)
    check("b12 non-positive values are not scheduled", p, ["POS"])

    check("b13 empty input", CC.dp_schedule([]), (0.0, []))

    # MUTANT: invert the §1 tie-break order (prefer the LATER decision second).
    real = CC._better
    def mutant(a, b):
        if a[0] != b[0]:
            return a[0] > b[0]
        return a[1] > b[1]                          # <-- the single defect
    CC._better = mutant
    try:
        expect_fail("b14 RED: mutant tie-break comparator is caught",
                    _dp_assertions)
    finally:
        CC._better = real
    print("")


# ==================================================== (c) path skeleton ======
class _FakeSession(object):
    pass


def _fake_session(mids_by_sec, n, phase_boundary):
    s = _FakeSession()
    s.n = n
    s.mid = np.full(n, np.nan)
    for sec, px in mids_by_sec:
        s.mid[sec] = px
    s.vt = np.array([sec for sec, _ in mids_by_sec], dtype=np.int64)
    s.vm = np.array([px for _, px in mids_by_sec], dtype=np.float64)
    s.spread_usd = np.full(n, 2.0)
    s.phase_tag = np.zeros(n, dtype=np.int8)
    s.phase_tag[phase_boundary:] = 1
    s.state = np.full(n, C.ST_TWO_SIDED, dtype=np.int8)
    s.iid = 42
    s.dominant_share = 1.0
    return s


def test_skeleton():
    print("(c) path skeleton answers MFE / MAE / t_wall for ANY wall — §8")
    # mult and the price step are chosen so every f value is EXACT in binary
    # (0.25 x 4), otherwise the float32 skeleton and the float64 brute force
    # would disagree on ties like "a(t) >= W" purely by representation.
    mult = 4.0
    # a deliberately jagged path so prefix maxima are non-trivial
    seq = [0, 3, -2, 5, -6, 9, -4, 12, -11, 7, 15, -3, 2]
    mids = [(i * 10, 100.0 + v * 0.25) for i, v in enumerate(seq)]
    n = 200
    s = _fake_session(mids, n, phase_boundary=70)

    cols = {k: [] for k in CC.ROSTER_KEYS}
    ft, fv, at, av = [], [], [], []
    CC._emit_candidate(cols, ft, fv, at, av, s, dt.date(2024, 6, 3), "SI",
                       mult, 1, 1, 0, 0, 3000.0)
    r = {k: np.array(v) for k, v in cols.items()}
    r["skel_f_t"] = np.array(ft, dtype=np.int32)
    r["skel_f_v"] = np.array(fv, dtype=np.float32)
    r["skel_a_t"] = np.array(at, dtype=np.int32)
    r["skel_a_v"] = np.array(av, dtype=np.float32)

    f = [(px - 100.0) * mult for _, px in mids]
    secs = [sec for sec, _ in mids]
    check_close("c1 unwalled MFE", float(r["mfe_unwalled"][0]), max(max(f), 0.0))
    check_close("c2 argmax second", float(r["mfe_argmax_sec"][0]),
                float(secs[f.index(max(f))]))

    for W in (1.0, 2.0, 3.0, 4.0, 6.0, 10.0, 11.0, 12.0, 900.0):
        t_wall = None
        for k in range(len(f)):
            if -f[k] >= W:
                t_wall = secs[k]
                break
        want_mfe = 0.0
        want_arg = 0
        for k in range(len(f)):
            if t_wall is not None and secs[k] >= t_wall:
                break
            if f[k] > want_mfe:
                want_mfe = f[k]
                want_arg = secs[k]
        gt, gm, ga, _w = CC._skel_query(r, 0, W)
        check("c3 W=%g t_wall" % W, gt, t_wall)
        check_close("c4 W=%g MFE before wall" % W, gm, want_mfe)
        check("c5 W=%g argmax before wall" % W, ga, want_arg if want_mfe > 0 else 0)

    # phase-close certificate: exit at the first second of the next phase
    pc = int(r["phase_close_sec"][0])
    check("c6 phase-close second is the first second of the next phase", pc, 70)
    j = max(k for k in range(len(secs)) if secs[k] <= pc)
    check_close("c7 f at the phase-close clock", float(r["f_phase_close"][0]), f[j])
    print("")


# =================================================================== main ====
def main():
    print("PORT M0 census self-tests (spec sha16 %s)" % X.SPEC_SHA16)
    print("")
    test_zigzag()
    test_dp()
    test_skeleton()
    if FAILS:
        print("FAILED (%d):" % len(FAILS))
        for f in FAILS:
            print("  - %s" % f)
        return 1
    print("ALL TESTS PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
