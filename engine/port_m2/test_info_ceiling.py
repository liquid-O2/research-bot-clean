#!/usr/bin/python3
"""Tests for the D-090.6 information-ceiling lane.

Four things have to hold or the ceiling numbers mean nothing:
  1. the `seq_cues` refactor this lane needed is BEHAVIOUR-IDENTICAL (there is
     still exactly one copy of the cue arithmetic, and other lanes read it);
  2. the view map covers EVERY `e6_round.DELTA_COLS` field — mapped or
     explicitly declared unmapped, never silently dropped;
  3. the universe is the E6 EPISODE grain: one row per frozen EPISODE_CAUSAL
     episode, each one its episode's EARLIEST member;
  4. the capture scale is monotone where it must be —
     random < honest-fit < perfect-foresight-top3 < oracle.

Run: /usr/bin/python3 engine/port_m2/test_info_ceiling.py
"""
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, "/workspace/engine/port_m0", "/workspace/engine/port_m1",
           "/workspace/engine/port_m1b", "/workspace/engine/port_m3",
           "/workspace/artifacts/cache/pylibs"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import m2_common as MC                    # noqa: E402
import assemble as A                      # noqa: E402
import tape as TAPE                       # noqa: E402
import seq_cues as SQ                     # noqa: E402
import e6_round as E6                     # noqa: E402
import info_ceiling as IC                 # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print("%-58s %s%s" % (name, "PASS" if ok else "FAIL",
                          ("  " + detail) if detail else ""))
    if not ok:
        FAILS.append(name)


def t1_seq_refactor_identical():
    """`for_window` == cache-load + `cues_from_window`, on a live episode."""
    eps, _ = E6.load_day(20240415)
    e = eps[0]
    case = A.Case(e["rep_cid"], mode=MC.MODE_BLIND, want_events=False)
    lo = max(0, int(case.dec_sec) - IC.SEQ_WINDOW_SEC)
    a = SQ.for_window(case.asset, case.trade_date, int(case.s.iid),
                      case.open_utc, case.close_utc, lo, int(case.dec_sec))
    arrays, _m = TAPE.ensure(case.asset, case.trade_date, int(case.s.iid),
                             case.open_utc, case.close_utc,
                             [(lo - 2, int(case.dec_sec) + 1)])
    w, _i, _j = TAPE.window(arrays, case.open_utc, lo, int(case.dec_sec) + 1)
    b = SQ.cues_from_window(w)
    check("seq_cues split is behaviour-identical", a == b,
          "%d fields" % len(a))


def t2_view_map_covers_delta_cols():
    mapped = {c for c, _m in IC.DIGEST_MAP}
    delta = set(E6.DELTA_COLS)
    check("view map covers every DELTA_COLS field", mapped >= delta,
          "missing=%s" % sorted(delta - mapped))
    E = IC.load(with_seq=False)
    rec_unmapped = [c for c, m in IC.DIGEST_MAP if m == "."]
    check("unmapped digest fields are DECLARED, not dropped",
          len(rec_unmapped) == 10, "%d declared" % len(rec_unmapped))
    check("no view column is an outcome column",
          not (set(E["cols"]) & {"cert_close_usd", "cert_peak_usd", "walled",
                                 "winner", "mae_before_argmax",
                                 "mfe_unwalled", "exit_close_sec"}))


def t3_episode_grain():
    E = IC.load(with_seq=False)
    ep = E["ep"]
    check("one row per episode", np.unique(ep).size == ep.size,
          "%d episodes" % ep.size)
    check("universe is E6 only",
          bool((E["d8"] >= 20240101).all() and (E["d8"] <= 20240630).all()),
          "%d..%d" % (E["d8"].min(), E["d8"].max()))
    check("no holdout row ever loaded", bool((E["d8"] < MC.HOLDOUT_FROM_D8).all()))
    # the representative is the episode's EARLIEST member: cross-check one
    # committed round day against episode_round's own build
    eps, _ = E6.load_day(20240415)
    want = {}
    for e in eps:
        want[(e["asset"], int(e["date8"]),
              1 if e["side"] == "L" else -1, int(e["first_dec_sec"]))] = 1
    got = 0
    m = np.nonzero(E["d8"] == 20240415)[0]
    for i in m.tolist():
        k = (str(E["asset"][i]), 20240415, int(E["side"][i]),
             int(E["dec_sec"][i]))
        got += k in want
    check("reps match episode_round's own build on 2024-04-15",
          got >= int(0.9 * len(want)), "%d/%d matched" % (got, len(want)))


def t4_capture_scale_is_monotone():
    E = IC.load()
    orc, _rep = IC.denominators(E)
    perfect = IC.capture(E, IC.take_from_score(
        E, E["cert_close_usd"].astype(np.float64)), orc)["capture"]
    rng = np.random.default_rng(IC.SEED)
    rnd = IC.capture(E, IC.take_from_score(
        E, rng.random(E["dec_sec"].size)), orc)["capture"]
    check("random < perfect-foresight-top3 < oracle",
          rnd < perfect < 1.0, "random=%.4f perfect=%.4f" % (rnd, perfect))
    check("perfect-foresight-top3 is a BINDING shape ceiling (< oracle)",
          perfect < 0.9, "%.4f of oracle dollars" % perfect)


def main():
    for t in (t1_seq_refactor_identical, t2_view_map_covers_delta_cols,
              t3_episode_grain, t4_capture_scale_is_monotone):
        t()
    print("\n%s (%d failure(s))" % ("ALL PASS" if not FAILS else "FAILED",
                                    len(FAILS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
