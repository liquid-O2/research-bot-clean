#!/usr/bin/python3
"""PORT M1 §11 GENERATION TRUTH AUDIT — red-first self-tests (D-069).

The brief names exactly two red-first cases for this lane:

  (1) THE CEIL ENTRY SUPERSET.  The perfect-knowledge ceiling admits entries at
      ANY SANE second; the implementation only ever evaluates a superset.  A
      superset that is missing an optimal entry silently DEFLATES the ceiling
      and therefore deflates every forfeit number built on it — the exact bug
      class that would make this audit say "generation is fine".  The test
      brute-forces the DP over EVERY SANE second (synthetic paths AND three
      real small sessions) and demands equality.  MUTANT `superset_spine_only`
      = the fine-grain ZigZag spine WITHOUT the per-block extremum landmarks,
      i.e. the literal reading of "ZigZag extrema as the superset"; it must be
      caught, and it is (a block whose extremum never retraces before the block
      ends is never confirmed as a pivot).

  (2) THE LEG-PROGRESS DECILE BOUNDARY.  progress in [0,1] -> decile 0..9 is an
      off-by-one magnet at the tenth boundaries and at progress == 1.0 (the
      leg's own end second is a legitimate candidate second).  MUTANTS
      `decile_no_clamp` (int(10p), so p == 1.0 lands in a phantom decile 10)
      and `decile_round` (round instead of floor, so every boundary shifts half
      a decile) must both be caught.

RED-FIRST LAW: a mutant caught by NO case is a test FAILURE.

Run: /usr/bin/python3 engine/port_m1/test_genaudit.py
"""
import datetime as dt
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m1_common as M
import common as C
import census_common as X
import c_a_cost as CA
import b7_sane as B7
import gen_audit as GA

FAILS = []
MUTANT_HITS = []


def check(name, ok, detail=""):
    if not ok:
        FAILS.append("%s %s" % (name, detail))


# =================================================== synthetic session stub ==
class _S(object):
    """Exactly what SessionValues / phase_blocks / the DP read off a Session."""

    __slots__ = ("phase_tag", "mid", "valid", "vt", "vm", "n", "iid", "state",
                 "meta")

    def __init__(self, mids, phase_tag, valid=None, iid=7):
        self.n = len(mids)
        self.mid = np.array(mids, dtype=np.float64)
        self.phase_tag = np.array(phase_tag, dtype=np.int8)
        v = np.ones(self.n, dtype=bool) if valid is None \
            else np.array(valid, dtype=bool)
        self.valid = v
        self.vt = np.nonzero(v)[0].astype(np.int64)
        self.vm = self.mid[self.vt]
        self.iid = iid
        self.state = np.where(v, C.ST_TWO_SIDED, 0).astype(np.int8)
        self.meta = {"open_utc": 0}


def _blocks(n, cuts):
    """phase_tag with contiguous blocks at the given cut points."""
    tag = np.zeros(n, dtype=np.int8)
    for k, c in enumerate(cuts):
        tag[c:] = k + 1
    return tag


# --------------------------------------------------------------- the cases --
def _paths():
    """Deterministic synthetic mid paths, each 60 seconds, 3 phase blocks.

    C1 is the one the ZigZag-only superset provably misses: block 0 falls to
    its minimum ON ITS LAST SECOND (no retrace follows inside the block, so no
    pivot is ever confirmed there) and block 1 opens with a jump up, which is
    exactly where the block's best long entry sits.
    """
    out = {}
    m = [100.0] * 60
    for i in range(0, 20):
        m[i] = 100.0 - i * 0.5            # monotone fall, min at sec 19
    for i in range(20, 40):
        m[i] = 112.0 + (i - 20) * 0.1     # block 1 opens 22 higher
    for i in range(40, 60):
        m[i] = 114.0 - (i - 40) * 0.3
    out["C1_block_min_at_block_end"] = (m, _blocks(60, [20, 40]))

    m = [100.0] * 60
    for i in range(60):
        m[i] = 100.0 + 3.0 * np.sin(i / 3.0) + 0.05 * i
    out["C2_oscillating"] = ([float(x) for x in m], _blocks(60, [20, 40]))

    m = [100.0 - 0.4 * i for i in range(60)]
    out["C3_monotone_fall"] = (m, _blocks(60, [20, 40]))

    m = [100.0] * 60
    for i in range(20):
        m[i] = 100.0 + 0.6 * i            # block 0 rises, max at its last sec
    for i in range(20, 40):
        m[i] = 100.0 - (i - 20) * 0.4     # block 1 falls away
    for i in range(40, 60):
        m[i] = 92.0 + (i - 40) * 0.2
    out["C4_block_max_at_block_end"] = (m, _blocks(60, [20, 40]))

    m = [100.0] * 60
    for i in range(60):
        m[i] = 100.0 + (6.0 if 25 <= i <= 27 else 0.0) - (5.0 if i >= 45
                                                          else 0.0)
    out["C5_step_shocks"] = (m, _blocks(60, [20, 40]))

    # gappy SANE mask: the phase-close second itself is INSANE, so the exit mid
    # is the last SANE second before the boundary — the off-by-one that would
    # break the value function if `je` were taken as the boundary index.
    m, tag = out["C2_oscillating"]
    valid = np.ones(60, dtype=bool)
    valid[[20, 21, 40, 41, 7, 8, 9]] = False
    out["C6_gappy_sane"] = (m, tag, valid)
    return out


def _mk(case):
    if len(case) == 3:
        return _S(case[0], case[1], case[2])
    return _S(case[0], case[1])


MULT = 100.0
WALL = 900.0
COST = 12.0
TICK = 0.005


def t_superset_completeness():
    """FULL superset DP == brute-force DP over EVERY SANE second."""
    for name, case in sorted(_paths().items()):
        s = _mk(case)
        sv = GA.SessionValues(s, MULT, WALL, COST)
        brute, bsel = sv.dp(superset=None, prune=False)
        full, fsel = sv.dp(sv.superset(TICK, "FULL"))
        check("superset FULL == brute [%s]" % name, abs(full - brute) < 1e-9,
              "%r vs %r" % (full, brute))
        check("superset FULL picks the same seats [%s]" % name,
              sorted(fsel) == sorted(bsel), "%r vs %r" % (fsel, bsel))
        lm, _ = sv.dp(sv.superset(TICK, "LANDMARKS_ONLY"))
        check("landmarks alone are already complete [%s]" % name,
              abs(lm - brute) < 1e-9, "%r vs %r" % (lm, brute))
        spine, _ = sv.dp(sv.superset(TICK, "SPINE_ONLY"))
        if abs(spine - brute) > 1e-9:
            MUTANT_HITS.append(("ceil_entry_superset", "superset_spine_only",
                                name))
        check("brute is never beaten by any superset [%s]" % name,
              full <= brute + 1e-9 and spine <= brute + 1e-9)


def t_prune_lossless():
    """prune_items() never changes the DP answer."""
    for name, case in sorted(_paths().items()):
        s = _mk(case)
        sv = GA.SessionValues(s, MULT, WALL, COST)
        it = sv.items(sv.superset(TICK, "FULL"))
        a, _ = C_dp(it)
        b, _ = C_dp(GA.prune_items(it))
        check("prune is lossless [%s]" % name, abs(a - b) < 1e-9,
              "%r vs %r" % (a, b))


def C_dp(items):
    import c_c_roster as CC
    return CC.dp_schedule(items)


def t_wall_and_cost():
    """The value function IS the m0 phase-close certificate, wall included."""
    # a long entry whose price falls $900+ below the entry before the boundary
    m = [100.0] * 60
    m[5] = 100.0
    for i in range(6, 18):
        m[i] = 100.0 - (i - 5) * 1.0        # -$1,200 at mult 100 by sec 17
    for i in range(18, 20):
        m[i] = 130.0                        # then a huge rally
    s = _S(m, _blocks(60, [20, 40]))
    sv = GA.SessionValues(s, MULT, WALL, COST)
    check("wall kills the pre-wall long", sv.val[1][5] == -WALL - COST,
          "%r" % sv.val[1][5])
    check("the block minimum is never walled",
          sv.val[1][17] > 0 and sv.val[1][17] == (m[20] - m[17]) * MULT - COST,
          "%r" % sv.val[1][17])
    # sec 19 sits at the post-rally top: the drop back to the boundary mid is
    # $3,000 adverse, so it IS walled -- and the wall price is exactly -(W+cost)
    check("the walled value is exactly -(wall + cost)",
          sv.val[1][19] == -WALL - COST, "%r" % sv.val[1][19])
    # cost is charged once, on a path with no adverse excursion at all
    flat = _S([100.0 + 0.1 * i for i in range(60)], _blocks(60, [20, 40]))
    fv = GA.SessionValues(flat, MULT, WALL, COST)
    check("cost is charged once",
          abs(fv.val[1][0] - ((flat.mid[20] - flat.mid[0]) * MULT - COST))
          < 1e-9, "%r" % fv.val[1][0])


def t_decile_boundary():
    """§11.A decile: floor(10p), clamped, so p == 1.0 is decile 9."""
    cases = [(0.0, 0), (0.0999, 0), (0.1, 1), (0.2, 2), (0.25, 2),
             (0.5, 5), (0.9, 9), (0.99999, 9), (1.0, 9)]
    for p, want in cases:
        got = GA.decile_of(p)
        check("decile_of(%r)" % p, got == want, "got %r want %r" % (got, want))
        if _mut_no_clamp(p) != want:
            MUTANT_HITS.append(("leg_progress_decile", "decile_no_clamp",
                                "p=%r" % p))
        if _mut_round(p) != want:
            MUTANT_HITS.append(("leg_progress_decile", "decile_round",
                                "p=%r" % p))


def _mut_no_clamp(p):
    return int(np.floor(p * 10))


def _mut_round(p):
    return min(9, int(round(p * 10)))


def t_real_sessions():
    """The equivalence argument, brute-forced on 3 REAL small SI sessions."""
    dates = [dt.date(2021, 11, 28), dt.date(2021, 7, 25), dt.date(2022, 8, 21)]
    with open(os.path.join(M.M0_ROOT, "walls.json")) as fh:
        wall = float(json.load(fh)["walls"]["SI"]["wall_usd"])
    cost_map = CA.session_cost_rt(M.M0_ROOT)
    thr = B7.load_thresholds("SI")
    paths = dict(X.session_paths("SI", M.M0_ROOT))
    mult = C.ASSETS["SI"]["mult"]
    tick = C.ASSETS["SI"]["tick_px"]
    for d in dates:
        s = X.load_session("SI", d, paths[d])
        B7.apply(s, thr.get(M.d8(d), [B7.SANE_CAP_USD] * X.N_PHASES))
        cost = cost_map.get(("SI", d.isoformat()), C.FEES_RT)
        sv = GA.SessionValues(s, mult, wall, cost)
        brute, bsel = sv.dp(superset=None, prune=False)
        full, fsel = sv.dp(sv.superset(tick, "FULL"))
        check("real session CEIL == brute [%s]" % d, abs(full - brute) < 1e-6,
              "%r vs %r" % (full, brute))
        check("real session seats match [%s]" % d,
              sorted(fsel) == sorted(bsel))
        spine, _ = sv.dp(sv.superset(tick, "SPINE_ONLY"))
        if abs(spine - brute) > 1e-6:
            MUTANT_HITS.append(("ceil_entry_superset", "superset_spine_only",
                                "SI %s" % d))
        check("CEIL >= 0 [%s]" % d, brute >= 0.0)


def t_ceil_dominates_roster():
    """A roster candidate is an entry at a SANE second => CEIL >= ROSTER."""
    import c_c_roster as CC
    fr = GA.verify_freeze(["SI"])
    z = np.load(fr["SI"]["path"], allow_pickle=False)
    r = {k: z[k] for k in z.files}
    z.close()
    with open(os.path.join(M.M0_ROOT, "walls.json")) as fh:
        wall = float(json.load(fh)["walls"]["SI"]["wall_usd"])
    cost_map = CA.session_cost_rt(M.M0_ROOT)
    thr = B7.load_thresholds("SI")
    paths = dict(X.session_paths("SI", M.M0_ROOT))
    mult = C.ASSETS["SI"]["mult"]
    tick = C.ASSETS["SI"]["tick_px"]
    by_date = {}
    for i in range(int(r["date8"].size)):
        by_date.setdefault(int(r["date8"][i]), []).append(i)
    n = 0
    for d in sorted(paths)[300:312]:
        idx = by_date.get(M.d8(d))
        if not idx:
            continue
        s = X.load_session("SI", d, paths[d])
        B7.apply(s, thr.get(M.d8(d), [B7.SANE_CAP_USD] * X.N_PHASES))
        cost = cost_map.get(("SI", d.isoformat()), C.FEES_RT)
        sv = GA.SessionValues(s, mult, wall, cost)
        ceil, _ = sv.dp(sv.superset(tick, "FULL"))
        items = []
        for i in idx:
            _pk, cl = CC.certificates(r, i, wall, cost)
            items.append((cl[1], cl[2], cl[0], int(r["dec_sec"][i]),
                          int(r["iid"][i]), i))
        roster, _ = CC.dp_schedule(items)
        check("CEIL >= ROSTER [%s]" % d, ceil >= roster - 1e-6,
              "%r < %r" % (ceil, roster))
        # every roster certificate value must equal the CEIL value function at
        # that same (second, side) — the two machineries must agree exactly
        for i in idx[:40]:
            j = int(np.searchsorted(s.vt, int(r["dec_sec"][i]), side="left"))
            if j >= sv.n or int(s.vt[j]) != int(r["dec_sec"][i]):
                continue
            _pk, cl = CC.certificates(r, i, wall, cost)
            got = float(sv.val[int(r["side"][i])][j])
            check("value function == m0 certificate [%s #%d]" % (d, i),
                  abs(got - cl[0]) < 1e-6, "%r vs %r" % (got, cl[0]))
        n += 1
    check("ceil/roster comparison ran", n >= 5, "n=%d" % n)


def write_receipt():
    algos = {}
    for (alg, mut, case) in MUTANT_HITS:
        algos.setdefault((alg, mut), []).append(case)
    rows = [[a, m, len(cs), ",".join(sorted(set(cs))[:6])]
            for (a, m), cs in sorted(algos.items())]
    M.write_tsv(M.out_path(GA.OUT_DIR, "redfirst.tsv"), GA.SECTION,
                C.params_hash(GA.PARAMS),
                ["algorithm", "mutant", "n_cases_broken", "cases_broken"],
                rows,
                extra=["a mutant caught by NO case is a test FAILURE "
                       "(red-first law); the real implementation is green on "
                       "every case listed",
                       "superset_spine_only: the fine-grain ZigZag spine "
                       "WITHOUT the per-phase-block extremum landmarks",
                       "decile_no_clamp: int(10 x progress), so progress==1.0 "
                       "lands in a phantom decile 10",
                       "decile_round: round() instead of floor() on the "
                       "decile boundaries"])
    return rows


def main():
    M.verify_spec()
    for t in (t_superset_completeness, t_prune_lossless, t_wall_and_cost,
              t_decile_boundary, t_real_sessions, t_ceil_dominates_roster):
        t()
    rows = write_receipt()
    for r in rows:
        if not r[2]:
            check("mutant %s/%s is DEAD (caught by nothing)" % (r[0], r[1]),
                  False)
    for want in ("superset_spine_only", "decile_no_clamp", "decile_round"):
        if not any(r[1] == want for r in rows):
            check("mutant %s was caught by NOTHING" % want, False)
    for f in FAILS:
        print("FAIL " + f)
    print("%d failures" % len(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
