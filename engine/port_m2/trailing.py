#!/usr/bin/python3
"""PORT M2 — REAL TRAILING RULES ON THE FULL ARMOURED BOOK.

WHY THIS IS THE FLOOR-CLEARING QUESTION.  The bounds said exits carry several
times the entry headroom: on the armoured book (3/asset/day + first-wall stop)
E7 pays $1,278/session as traded, a half-the-peak give-back BOUND pays $2,319
and the clairvoyant exit oracle pays $3,971 (0.97 of the entire ENTRY foresight
ceiling).  Those are bounds -- they assume a trail is never hit early, which is
why their win rates are 0.985-0.997.  A REAL rule triggers on the way past, so
it exits early on paths that would have recovered.  The achievable fraction of
$2,319-2,880 is now the program's floor-clearing question.

THE ARITHMETIC IS THE ROSTER'S OWN.  Every trade's second-by-second P&L is
rebuilt with `m2_delay._leg` -- the same skeleton that reproduced the committed
certificate EXACTLY at D=0 on all 1,399,374 candidates -- so a trailing exit is
priced on the same path the certificate was priced on.  Nothing is interpolated
from summary columns.

CONTRACT INVARIANTS, ENFORCED IN CODE (not assumed):
  * 30-MINUTE MINIMUM HOLD -- no exit before dec_sec + 1800.  The prop ban on
    quick exits is structural here: a rule physically cannot fire earlier.
  * the $900 WALL is always live and always wins if it comes first.
  * the PHASE CLOSE is the hard right edge, exactly as the certificate uses it.
  * ARMING: a trail does nothing until the trade has first reached the arming
    profit.  Mid-run dips before arming ride as normal -- that is the whole
    point of arming and it is what separates a trail from a stop.

CONTROL: DISPLACED-TIME.  The identical rule is applied to the SAME trade's path
rotated in time (the tail spliced to the head).  A rule that pays as much on a
rotated path is reading path shape that is not there.
"""
import argparse
import json
import os
import sys
import time

import numpy as np

_H = os.path.dirname(os.path.abspath(__file__))
for _p in (_H, "/workspace/engine/port_m2/seqtest", "/workspace/engine/port_m0",
           "/workspace/engine/port_m1", "/workspace/engine/port_m3",
           "/workspace/artifacts/cache/pylibs"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import newobj as N                        # noqa: E402
import champ_floor as CF                  # noqa: E402
import stacked_final as SF                # noqa: E402
import confidence as CO                   # noqa: E402
import m2_delay as MD                     # noqa: E402
import assemble as A                      # noqa: E402
import census_common as X                 # noqa: E402
import common as C                        # noqa: E402
import m2_common as MC                    # noqa: E402

ERAS = N.DEV_ERAS
MIN_HOLD = 1800                # 30 minutes, hard
ARMS = (600.0, 900.0, 1200.0)
GIVEBACKS = (0.30, 0.50)
SWINGS = (1800, 3600)
LOCKS = (0.0, 300.0)           # breakeven + X after arming


def _rules():
    r = [("CLOSE", None)]
    for a in ARMS:
        for g in GIVEBACKS:
            r.append(("PCT_arm%d_give%d" % (int(a), int(g * 100)),
                      ("pct", a, g)))
        for w in SWINGS:
            r.append(("SWING_arm%d_w%dm" % (int(a), w // 60), ("swing", a, w)))
        for lk in LOCKS:
            r.append(("LOCK_arm%d_plus%d" % (int(a), int(lk)),
                      ("lock", a, lk)))
    return r


RULES = _rules()


def _apply(vt, f, t0, pc, wall_t, cost, rule, displaced=False):
    """Walk the trade's own path and return (realised_usd, exit_sec).

    The wall and the phase close bound everything; the rule may only exit
    EARLIER, and never before the 30-minute minimum hold.
    """
    hard = pc if wall_t is None else min(pc, wall_t)
    if wall_t is not None and wall_t <= pc:
        wall_val = -MD.WALL_USD - cost
    else:
        wall_val = None
    a = int(np.searchsorted(vt, t0, side="left"))
    b = int(np.searchsorted(vt, hard, side="right"))
    if b <= a:
        return (wall_val if wall_val is not None else -cost), int(hard)
    seg_t, seg_f = vt[a:b], f[a:b]
    if displaced:
        # DISPLACED-TIME CONTROL: same path, rotated (tail spliced to head).
        k = seg_f.size // 2
        seg_f = np.concatenate([seg_f[k:], seg_f[:k]])
    if rule is None:
        return (wall_val if wall_val is not None else
                float(seg_f[-1]) - cost), int(hard)
    kind, arm, par = rule
    run_max = np.maximum.accumulate(seg_f)
    armed = run_max >= arm
    if not armed.any():
        return (wall_val if wall_val is not None else
                float(seg_f[-1]) - cost), int(hard)
    ok = armed & (seg_t >= t0 + MIN_HOLD)
    if kind == "pct":
        trig = ok & (seg_f <= run_max * (1.0 - par))
    elif kind == "lock":
        trig = ok & (seg_f <= par)
    else:                                   # rolling-swing structure stop
        lo = np.full(seg_f.size, -np.inf)
        for i in range(seg_f.size):
            j = int(np.searchsorted(seg_t, seg_t[i] - par, side="left"))
            lo[i] = seg_f[j:i + 1].min() if i >= j else seg_f[i]
        trig = ok & (seg_f <= lo)
    w = np.flatnonzero(trig)
    if w.size == 0:
        return (wall_val if wall_val is not None else
                float(seg_f[-1]) - cost), int(hard)
    i = int(w[0])
    ex = int(seg_t[i])
    if wall_t is not None and wall_t <= ex:
        return wall_val, int(wall_t)
    return float(seg_f[i]) - cost, ex


def _session_job(job):
    asset, d8, seats = job
    try:
        sess = A.load_session(asset, int(d8))
        s = sess["s"]
        mult = float(C.ASSETS[asset]["mult"])
        out = []
        for (row, t0, side, cost) in seats:
            vt, f, at, av = MD._leg(s, t0, float(s.mid[t0]), side, mult)
            pc = X.next_phase_boundary(s, t0)
            wt = MD._wall_sec(at, av)
            rec = {}
            for name, rule in RULES:
                v, ex = _apply(vt, f, t0, pc, wt, cost, rule)
                vd, _e = _apply(vt, f, t0, pc, wt, cost, rule, displaced=True)
                rec[name] = (v, ex - t0, vd)
            out.append((row, rec))
        return (asset, int(d8), out, None)
    except Exception as e:                              # noqa: BLE001
        return (asset, int(d8), [], "%s: %s" % (type(e).__name__, e))


def run(eras=ERAS, workers=6):
    import multiprocessing as mp
    D, P = CF.boot()
    ceil = CO.ceilings(eras)
    SDIR = os.path.join(N.OUT_ROOT, "curriculum_scores")
    rows = []
    for era in eras:
        # the armoured book's seats, per member seed -> 5-seed bars
        seedsets = []
        for sd in range(5):
            fp = os.path.join(SDIR, "CONTOP50_%s_%d.npy" % (era, sd))
            if not os.path.exists(fp):
                continue
            sc = np.load(fp).astype(np.float64)
            ev = N.deployable(D, N.era_rows(D, era))
            n_ = N.committed_policy()[era][1]
            raw = N.replay_delayed(D, N.top_per_cell_score(D, ev, sc, n_), P)
            armed = SF.apply_stop(D, raw, "STOP_WALL1")
            seedsets.append(armed)
        if not seedsets:
            continue
        allrows = sorted({s[0] for rep in seedsets for r in rep
                          for s in r["seats"]})
        jobs = {}
        for i in allrows:
            jobs.setdefault((str(D["asset"][i]), int(D["d8"][i])), []).append(
                (int(i), int(D["dec_sec"][i]), int(D["side"][i]),
                 float(D["cost_rt"][i])))
        jl = [(a, d, sorted(v)) for (a, d), v in sorted(jobs.items())]
        N.hb("trailing %s: %d seats over %d sessions, %d rules"
             % (era, len(allrows), len(jl), len(RULES)))
        book, errs = {}, 0
        t0 = time.time()
        with mp.Pool(processes=workers) as pool:
            for k, (a_, d_, res, err) in enumerate(
                    pool.imap_unordered(_session_job, jl, chunksize=4), 1):
                if err:
                    errs += 1
                    continue
                for row, rec in res:
                    book[row] = rec
                if k % 100 == 0:
                    N.hb("trailing %s %d/%d sessions (%.0fs)"
                         % (era, k, len(jl), time.time() - t0))
        for name, _r in RULES:
            per_seed, per_seed_d, holds, wins = [], [], [], []
            for rep in seedsets:
                tot = totd = 0.0
                n = 0
                for r in rep:
                    for (i, _dl, _v) in r["seats"]:
                        if i not in book:
                            continue
                        v, hold, vd = book[i][name]
                        tot += v
                        totd += vd
                        holds.append(hold)
                        wins.append(1.0 if v > 0 else 0.0)
                        n += 1
                per_seed.append(tot / max(len(rep), 1))
                per_seed_d.append(totd / max(len(rep), 1))
            ps = np.asarray(per_seed)
            psd = np.asarray(per_seed_d)
            c = ceil.get("%s|ALL" % era)
            rows.append([era, name, len(ps), N._r(ps.mean()), N._r(ps.std()),
                         N._r(ps.mean() / c, 4) if c else "",
                         N._r(float(np.mean(wins)), 4),
                         N._r(float(np.median(holds))),
                         N._r(psd.mean()),
                         N._r(ps.mean() - psd.mean()),
                         "FLOOR_OK" if ps.mean() >= 2000 else ""])
        N.hb("trailing %s done (%d session errors)" % (era, errs))
    N.write_tsv("TRAILING_REAL_RULES.tsv",
                ["era", "rule", "n_seeds", "mean_usd_per_session", "sd_usd",
                 "capture_of_entry_ceiling", "win_rate", "median_hold_sec",
                 "displaced_control_usd", "delta_vs_displaced", "floor_2000"],
                rows,
                extra=["REAL TRAILING RULES on the FULL ARMOURED BOOK "
                       "(3/asset/day + first-wall stop), priced on each trade's "
                       "OWN second-by-second path rebuilt with "
                       "`m2_delay._leg` -- the skeleton that reproduced the "
                       "committed certificate exactly at D=0.",
                       "ENFORCED IN CODE: 30-minute minimum hold (the prop ban "
                       "on quick exits is structural -- a rule cannot fire "
                       "earlier), the $900 wall always live and winning if it "
                       "comes first, the phase close as the hard right edge, "
                       "and ARMING so mid-run dips before the arming profit "
                       "ride as normal.",
                       "displaced_control_usd applies the IDENTICAL rule to the "
                       "same trade's path ROTATED IN TIME.  A rule that pays as "
                       "much there is reading path shape that is not there; "
                       "delta_vs_displaced is the real edge.",
                       "5-seed bars come from the five CONTOP50 member take-"
                       "sets, so the schedule varies as it would in deployment.",
                       "CLOSE is the as-traded row (no trail) and is the "
                       "reference every rule must beat."])
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--eras", default="E5,E6,E7")
    a = ap.parse_args()
    if a.run:
        run(eras=tuple(e for e in a.eras.split(",") if e))
    else:
        ap.print_help()
