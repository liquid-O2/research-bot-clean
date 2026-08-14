#!/usr/bin/python3
"""Tests for the entry-delay decidability lane.

Five things have to hold or the delay curves mean nothing:
  1. the `combo_forced_choice` extraction is BEHAVIOUR-IDENTICAL to the
     arithmetic `info_ceiling.run_walls` used to run inline (there is still
     exactly one copy, and the committed WALL_COMBOS row reproduces);
  2. the delayed-entry certificate REPRODUCES the committed roster at D=0 —
     value, exit second and wall flag, exactly;
  3. the delay is FORWARD: entry_sec(D) is monotone in D and never earlier
     than the decision second;
  4. the post-window block is CAUSAL-AT-t+D: it is a function of [t, t+D]
     only, so it is empty at D=0 and its `pp_net` equals the leg's own
     mark-to-market at t+D;
  5. a SHUFFLED winner/loser assignment scores at chance — the red-first
     control for the pair census at the largest delay.

Run: /usr/bin/python3 engine/port_m2/test_m2_delay.py
"""
import json
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, "/workspace/engine/port_m0", "/workspace/engine/port_m1",
           "/workspace/engine/port_m3", "/workspace/artifacts/cache/pylibs"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy.random as _npr               # noqa: E402
import info_ceiling as IC                 # noqa: E402
import m2_delay as MD                     # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print("%-58s %s%s" % (name, "PASS" if ok else "FAIL",
                          ("  " + detail) if detail else ""))
    if not ok:
        FAILS.append(name)


def t1_combo_extraction_identical():
    """The extracted forced choice reproduces the COMMITTED WALL_COMBOS row."""
    E = IC.load()
    pairs, _m, _a = IC.build_pairs(E)
    P = [p for p in pairs if not np.isfinite(p["mid_gap_atr"])
         or p["mid_gap_atr"] <= IC.VICINITY_ATR]
    iw = np.array([p["i_win"] for p in P])
    il = np.array([p["i_lose"] for p in P])
    day = np.array([p["d8"] for p in P])
    Dd = E["X"][iw].astype(np.float64) - E["X"][il].astype(np.float64)
    folds = IC.folds_by_day(day)
    _ai, akf, _hd, _td = IC.combo_forced_choice(
        Dd, folds, list(range(len(E["cols"]))))
    want = None
    with open("/workspace/provenance/port_m2/WALL_COMBOS.tsv") as fh:
        for line in fh:
            if line.startswith("ALL view fields\t"):
                want = float(line.split("\t")[4])
                break
    # the committed cell is written at "%.6g" (info_ceiling._fmt), so the
    # tolerance is that table's own precision, not machine epsilon
    check("combo_forced_choice == committed WALL_COMBOS 'ALL view fields'",
          want is not None and abs(akf - want) < 1e-6,
          "got %.9f want %s" % (akf, want))


def t2_d0_reproduces_the_roster():
    p = os.path.join(MD.OUT_ROOT, "verify_d0.receipt.json")
    r = json.load(open(p))
    check("D=0 delayed certificate == committed roster (value/exit/wall)",
          r["n_cert_mismatch"] == 0 and r["n_exit_mismatch"] == 0
          and r["n_walled_mismatch"] == 0,
          "%d episodes compared" % r["n_compared"])


def t3_delay_is_forward_and_monotone():
    E = MD.load()
    dec = E["dec_sec"].astype(np.float64)
    prev = None
    ok_fwd, ok_mono = True, True
    for D in MD.DELAYS:
        es = MD._pcol(E, D, "entry_sec")
        f = MD._pcol(E, D, "feasible") == 1.0
        ok_fwd &= bool(np.all(es[f] >= dec[f] + D))
        if prev is not None:
            both = f & prevf
            ok_mono &= bool(np.all(es[both] >= prev[both]))
        prev, prevf = es, f
    check("entry_sec(D) >= dec_sec + D for every feasible leg", ok_fwd)
    check("entry_sec is monotone non-decreasing in D", ok_mono)


def t4_post_block_is_the_window():
    E = MD.load()
    X0, n0 = MD.post_block(E, 0)
    check("post block is EMPTY at D=0 (no post-confirmation window)",
          X0.shape[1] == 0 and not n0)
    for D in (60, 600):
        Xp, pn = MD.post_block(E, D)
        j = pn.index("pp_net_D%d" % D)
        f = MD._pcol(E, D, "f_at_D")
        m = np.isfinite(Xp[:, j]) & np.isfinite(f)
        check("pp_net(D=%d) == the leg's mark at t+D" % D,
              bool(np.allclose(Xp[m, j], f[m])),
              "%d legs" % int(m.sum()))


def t5_shuffled_label_scores_at_chance():
    E = MD.load()
    tight, _pops = MD.populations(E)
    Dd, names, _lay, day = MD.pair_matrix(E, tight, max(MD.DELAYS))
    folds = IC.folds_by_day(day)
    rng = _npr.default_rng(IC.SEED + 7)
    eps = rng.choice([-1.0, 1.0], size=Dd.shape[0])[:, None]
    sel = [names.index(c) for c in names[-10:]]
    _ai, akf, _h, _t = IC.combo_forced_choice(Dd * eps, folds, sel)
    check("shuffled winner/loser assignment scores at chance",
          abs(akf - 0.5) < 0.05, "%.4f" % akf)


def main():
    for t in (t1_combo_extraction_identical, t2_d0_reproduces_the_roster,
              t3_delay_is_forward_and_monotone, t4_post_block_is_the_window,
              t5_shuffled_label_scores_at_chance):
        t()
    print("\n%s (%d failure(s))" % ("ALL PASS" if not FAILS else "FAILED",
                                    len(FAILS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
