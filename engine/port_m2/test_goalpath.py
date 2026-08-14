#!/usr/bin/python3
"""RED-FIRST fixture proofs for the goal-path censuses (D-006).

Every test drives the SHIPPING code — `goalpath._cont_one` is fed a synthetic
session through the same `assemble.load_session` seam the production run uses,
so the arithmetic under test is the arithmetic that produced the census.

    /usr/bin/python3 engine/port_m2/test_goalpath.py
"""
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, "/workspace/engine/port_m0", "/workspace/engine/port_m1",
           "/workspace/engine/port_m3"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import assemble as A                      # noqa: E402
import common as C                        # noqa: E402
import goalpath as G                      # noqa: E402

FAILED = []


def check(name, cond, detail=""):
    if cond:
        print("  ok   %s" % name)
    else:
        print("  FAIL %s  %s" % (name, detail))
        FAILED.append(name)


class FakeSession(object):
    """The minimum session surface `_cont_one` touches."""

    def __init__(self, mids, phase_len):
        self.n = len(mids)
        self.vt = np.arange(self.n, dtype=np.int64)
        self.vm = np.asarray(mids, dtype=np.float64)
        self.mid = self.vm
        self.phase_tag = np.minimum(self.vt // phase_len, 2).astype(np.int8)
        self.spread_usd = np.full(self.n, 1.0)
        self.bid_sz = np.full(self.n, 10.0)
        self.ask_sz = np.full(self.n, 10.0)
        self.meta = {"ATR14_prev_px": 1.0}


def drive(mids, rows, asset="SI", phase_len=10 ** 6, shift=0):
    """Run `_cont_one` against a synthetic session."""
    s = FakeSession(mids, phase_len)
    saved = A.load_session
    A.load_session = lambda a, d: {"s": s, "trade_date": None}
    try:
        out = G._cont_one((asset, 20220103, rows, shift))
    finally:
        A.load_session = saved
    return out


def cell(out, name):
    return float(out[3][0, G.CELL_IDX[name]])


def risk(out, entry, stop):
    ei = G.ENTRIES.index(entry)
    si = G.STOPS.index(stop)
    return float(out[7][0, ei * len(G.STOPS) + si])


# ---------------------------------------------------------------------------
def t01_phase_close_and_stop():
    """A long that never touches the stop exits at the phase close; the same
    path with the stop moved above the low exits AT the stop, for exactly
    -(risk) - cost."""
    mult = float(C.ASSETS["SI"]["mult"])          # 5000
    tick = float(C.ASSETS["SI"]["tick_px"])       # 0.005
    # extreme at t=0 (px 100.00), confirmation at t=100 (px 100.10), then a
    # slow climb to 100.20 at t=400 and flat to the end
    mids = np.concatenate([
        np.full(100, 100.00),                     # the extreme
        np.full(100, 100.10),                     # the confirmation (t=100)
        np.linspace(100.10, 100.20, 200),         # onward
        np.full(200, 100.20)])
    rows = [(0, 160, 100, 0, 1, 5.0, 1000.0)]     # dec 160, conf 100, ext 0
    out = drive(mids, rows)
    ext_stop = 100.00 - 2 * tick
    ent_px = mids[160]
    exp = (100.20 - ent_px) * mult - 5.0
    got = cell(out, "DELAY_0|EXT|PHASE")
    check("t01 phase-close value", abs(got - exp) < 1e-6,
          "got %.6f want %.6f" % (got, exp))
    exp_r = (ent_px - ext_stop) * mult
    check("t01 EXT risk", abs(risk(out, "DELAY_0", "EXT") - exp_r) < 1e-6,
          "got %.4f want %.4f" % (risk(out, "DELAY_0", "EXT"), exp_r))
    # now a path that DIPS through the reclaim stop after entry
    mids2 = mids.copy()
    mids2[300:360] = 100.02                       # below the reclaim - 2 ticks
    out2 = drive(mids2, rows)
    rec_stop = mids[100] - 2 * tick               # 100.10 - 0.01 = 100.09
    exp2 = (rec_stop - ent_px) * mult - 5.0
    got2 = cell(out2, "DELAY_0|RECLAIM|PHASE")
    check("t01 stop fills AT the structural stop", abs(got2 - exp2) < 1e-6,
          "got %.6f want %.6f" % (got2, exp2))


def t02_trailing_exit():
    """The trail is floored at the initial stop and fires 1R below the running
    favourable extreme."""
    mult = float(C.ASSETS["SI"]["mult"])
    mids = np.concatenate([
        np.full(100, 100.00),
        np.full(60, 100.10),                      # conf at 100 -> reclaim 100.10
        np.full(1, 100.10),                       # entry second (dec=160)
        np.linspace(100.10, 100.50, 100),         # run up
        np.linspace(100.50, 100.20, 100),         # give back
        np.full(100, 100.20)])
    rows = [(0, 160, 100, 0, 1, 5.0, 1000.0)]
    out = drive(mids, rows)
    R_px = mids[160] - (100.00 - 2 * float(C.ASSETS["SI"]["tick_px"]))
    peak = 100.50
    trail = peak - 1.0 * R_px
    got = cell(out, "DELAY_0|EXT|TRAIL_1.0R")
    # the give-back leg reaches 100.20 < trail (100.50-0.11=100.39) so the exit
    # is AT the trail level as the running max stops improving
    exp = (trail - mids[160]) * mult - 5.0
    check("t02 trailing exit at 1R below the peak", abs(got - exp) < 1e-6,
          "got %.6f want %.6f" % (got, exp))
    check("t02 trail never looser than the stop",
          cell(out, "DELAY_0|EXT|TRAIL_1.0R") >= -(R_px * mult) - 5.0 - 1e-6)


def t03_swing_structure():
    """SWING = the adverse extreme since the last favourable extreme."""
    tick = float(C.ASSETS["SI"]["tick_px"])
    mult = float(C.ASSETS["SI"]["mult"])
    mids = np.concatenate([
        np.full(100, 100.00),                     # extreme
        np.full(20, 100.10),                      # confirmation (reclaim)
        np.full(60, 100.40),                      # a favourable extreme
        np.full(60, 100.25),                      # the retracement structure
        np.full(400, 100.35)])                    # entry at t=240 on 100.35
    rows = [(0, 240, 100, 0, 1, 5.0, 1000.0)]
    out = drive(mids, rows)
    got = risk(out, "DELAY_0", "SWING")
    exp = (100.35 - (100.25 - 2 * tick)) * mult
    check("t03 swing risk = last pullback low - 2 ticks",
          abs(got - exp) < 1e-6, "got %.4f want %.4f" % (got, exp))
    check("t03 swing risk << extreme risk",
          got < risk(out, "DELAY_0", "EXT"))


def t04_trend_gate_refuses_non_prevailing():
    """A trend entry only fires while price is still on the reversal side of
    the reclaim level at t+D."""
    mids = np.concatenate([
        np.full(100, 100.00),
        np.full(100, 100.10),                     # conf at 100
        np.full(3600, 100.05),                    # BELOW the reclaim at t+900
        np.full(2000, 100.30)])
    rows = [(0, 160, 100, 0, 1, 5.0, 1000.0)]
    out = drive(mids, rows)
    ei = G.ENTRIES.index("TREND_900")
    check("t04 TREND_900 refused when not prevailing",
          int(out[6][0, ei]) == -1 and
          G.REFUSALS[int(out[8][0, ei])] == "REBREAK_BEFORE_TRIGGER",
          "entry %d refusal %s" % (out[6][0, ei],
                                   G.REFUSALS[int(out[8][0, ei])]))
    mids2 = mids.copy()
    mids2[200:3800] = 100.20                      # prevailing
    out2 = drive(mids2, rows)
    check("t04 TREND_900 fires when prevailing",
          int(out2[6][0, ei]) == 1000, "entry %s" % out2[6][0, ei])


def t05_displacement_control():
    """The displaced-entry control moves the entry second and nothing else."""
    mids = np.concatenate([np.full(100, 100.00), np.full(100, 100.10),
                           np.linspace(100.10, 100.60, 2000),
                           np.full(500, 100.60)])
    rows = [(0, 160, 100, 0, 1, 5.0, 1000.0)]
    a = drive(mids, rows)
    b = drive(mids, rows, shift=600)
    ei = G.ENTRIES.index("DELAY_0")
    check("t05 displacement shifts the entry second",
          int(b[6][0, ei]) - int(a[6][0, ei]) == 600,
          "%s -> %s" % (a[6][0, ei], b[6][0, ei]))
    check("t05 displacement costs the travelled move",
          cell(b, "DELAY_0|EXT|PHASE") < cell(a, "DELAY_0|EXT|PHASE"))


def t06_leg_not_positive_refused():
    """A candidate whose reversal leg is not positive is REFUSED, never priced."""
    mids = np.concatenate([np.full(100, 100.20), np.full(400, 100.00)])
    rows = [(0, 160, 100, 0, 1, 5.0, 1000.0)]     # long, but conf BELOW extreme
    out = drive(mids, rows)
    check("t06 non-positive leg refused",
          G.REFUSALS[int(out[8][0, 0])] == "LEG_NOT_POSITIVE" and
          not np.isfinite(out[3][0]).any())


def t07_replay_one_position():
    """The replay seats one position per asset and forfeits the overlap."""
    ent = np.array([100, 150, 400])
    ex = np.array([300, 350, 500])
    val = np.array([10.0, 99.0, 7.0])
    sess = np.array(["SI|20220103"] * 3)
    rows, seats = G.replay(ent, ex, val, sess, np.arange(3))
    check("t07 one-position replay", rows[0]["n_seated"] == 2 and
          rows[0]["n_forfeited"] == 1 and abs(rows[0]["realised"] - 17.0) < 1e-9,
          str(rows[0]))


def t08_cluster_boot_point_estimate():
    v = np.array([1.0, 2.0, 3.0, 4.0])
    d = np.array([1, 1, 2, 2])
    m, lo, hi, nd = G.cluster_boot(v, d, n=200)
    check("t08 cluster_boot point estimate", abs(m - 2.5) < 1e-12 and nd == 2)
    check("t08 cluster_boot brackets", lo <= m <= hi)


def t09_d0_reproduces_the_committed_roster():
    """THE INSTRUMENT RECEIPT: on real E6 rows where neither the structural stop
    nor the $900 wall fired, DELAY_0|EXT|PHASE IS the committed certificate."""
    p = os.path.join(G.OUT_ROOT, "cont_E5.npz")
    if not os.path.exists(p):
        print("  skip t09 (no cont_E5.npz yet)")
        return
    z = np.load(p, allow_pickle=False)
    D = G.spine()
    idx = z["idx"]
    ci = G.CELL_IDX["DELAY_0|EXT|PHASE"]
    ei = G.ENTRIES.index("DELAY_0")
    si = G.STOPS.index("EXT")
    v = z["val"][:, ci]
    ex = z["exit_sec"][:, ci]
    mae = z["mae"][:, ci]
    r = z["r_usd"][:, ei * len(G.STOPS) + si]
    z.close()
    # the structural stop fills AT its level, so a stopped trade has
    # mae == risk exactly; the comparable set is the unstopped, unwalled rows
    # whose exit second IS the roster's phase close
    f = (np.isfinite(v) & (D["walled"][idx] == 0) &
         (ex == D["phase_close_sec"][idx]) & (mae < r - 1e-6))
    d = np.abs(v[f] - D["cert_close_usd"][idx][f])
    check("t09 D=0 reproduces the committed roster certificate",
          f.sum() > 1000 and float(d.max()) < 1e-6,
          "n=%d max_abs_diff=%.3g" % (int(f.sum()),
                                      float(d.max()) if d.size else -1))


def main():
    for fn in (t01_phase_close_and_stop, t02_trailing_exit, t03_swing_structure,
               t04_trend_gate_refuses_non_prevailing, t05_displacement_control,
               t06_leg_not_positive_refused, t07_replay_one_position,
               t08_cluster_boot_point_estimate,
               t09_d0_reproduces_the_committed_roster):
        print(fn.__name__)
        fn()
    if FAILED:
        print("\nFAILED: %s" % ", ".join(FAILED))
        return 1
    print("\nall green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
