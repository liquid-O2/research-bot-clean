#!/usr/bin/python3
"""PORT M2 SEQTEST — RE-SCORE EVERY ARM ON THE HARNESS'S OWN SCHEDULE.

WHY THIS FILE EXISTS (a defect in this lane's own reporting, found by looking at
the seat counts).  The first pass scored every arm through a FIXED
top-3-per-asset-DAY schedule because the brief named it.  That schedule forfeits
**63-65% of its own takes**: only one position can be open per asset-session, so
three takes chosen inside one session mostly land on top of each other.  The
committed M3 harness never uses it — it selects the (unit, N) pair on the
training block's inner validation and lands on the (asset, PHASE) CELL with
N in {1,2}, which spreads the takes across the day by construction and banks
$296-441/session on the same model class.

So every capture number in the first pass was measured through a schedule that
was throwing away two thirds of its takes before any model was involved.  That
is a scoring defect, not a model result, and this module repairs it:

  DEPLOYABLE reading   the per-era (unit, N) that `m3_walk` ITSELF selected on
                       the inner validation block, read out of the committed
                       `walk.summary.json`.  It was chosen without ever seeing
                       an evaluation era, so applying it here leaks nothing.
  SENSITIVITY curve    all ten (unit x N) cells for every arm, printed, so the
                       choice can never again be doing invisible work.

Nothing is refitted.  These are the same out-of-sample score columns, re-seated.

Run:  st_sched.py --all
"""
import argparse
import json
import os
import time

import numpy as np

import st_common as SC
import st_run as R
import m3_common as M3

UNITS = ("session", "cell")
OUT_NAME = "SEQTEST_SCHEDULE"
NS = (1, 2, 3, 5, 8)


def committed_policy():
    """The (unit, N) m3_walk selected per era on its own inner block."""
    with open(os.path.join(M3.WALK_DIR, "walk.summary.json")) as fh:
        s = json.load(fh)
    out = {}
    for e in s["eras"]:
        if e.get("status") == "OK":
            out[e["era"]] = (e["policy_unit"], int(e["topn"]))
    return out


def score_of(D, tag, ev):
    z = np.load(os.path.join(R.SCORE_DIR, "%s.npz" % tag))
    champ, win = z["champ"], z["win"]
    if np.array_equal(np.nan_to_num(champ[ev]), np.nan_to_num(win[ev])):
        return champ
    s = np.full(D["d8"].size, np.nan)
    s[ev] = R.composed(D, champ, win, ev)[ev]
    return s


def run(tags=None, eras=SC.TEST_ERAS):
    import m3_walk as W
    D, _p = W.load_matrix()
    ceil = R.ceilings_of(D)
    pol = committed_policy()
    if tags is None:
        tags = sorted(f[:-4] for f in os.listdir(R.SCORE_DIR)
                      if f.endswith(".npz"))
    dep_rows, sens_rows = [], []
    for tag in tags:
        t0 = time.time()
        parts_dep = []
        curve = {}
        for era in eras:
            ev = np.nonzero(D["era_idx"] == SC.ERA_IDX[era])[0]
            try:
                s = score_of(D, tag, ev)
            except Exception as e:                      # noqa: BLE001
                SC.hb("skip %s (%s)" % (tag, e))
                break
            ev = ev[np.isfinite(s[ev])]
            if ev.size == 0:
                continue
            u, n = pol.get(era, ("cell", 1))
            a = R.score_arm(D, s, ev, ceil, unit=u, n=n)
            a["era"] = era
            parts_dep.append(a)
            dep_rows.append([tag, era, "%s/%d" % (u, n), a["n_takes"],
                             a["n_seated"],
                             round(100.0 * (1 - a["n_seated"]
                                            / max(a["n_takes"], 1)), 1),
                             R._r(a["usd_per_session"]), R._r(a["ps_lo"]),
                             R._r(a["ps_hi"]), R._r(a["usd_per_trade"]),
                             R._r(a["frac_ge_1000"], 4),
                             R._r(a["capture_day"], 4),
                             R._r(a["capture_oracle"], 4),
                             R._r(a["co_lo"], 4), R._r(a["co_hi"], 4)])
            for u2 in UNITS:
                for n2 in NS:
                    b = R.score_arm(D, s, ev, ceil, unit=u2, n=n2)
                    curve.setdefault((u2, n2), []).append(b)
        if not parts_dep:
            continue
        p = R.pooled(parts_dep)
        dep_rows.append([tag, "POOLED_%s-%s" % (eras[0], eras[-1]),
                         "m3_committed", "", "", "",
                         R._r(p["usd_per_session"]), R._r(p["ps_lo"]),
                         R._r(p["ps_hi"]), "", "",
                         R._r(p["capture_day"], 4),
                         R._r(p["capture_oracle"], 4), R._r(p["co_lo"], 4),
                         R._r(p["co_hi"], 4)])
        for (u2, n2), parts in sorted(curve.items()):
            q = R.pooled(parts)
            sens_rows.append([tag, u2, n2,
                              sum(x["n_takes"] for x in parts),
                              sum(x["n_seated"] for x in parts),
                              round(100.0 * (1 - sum(x["n_seated"] for x in parts)
                                             / max(sum(x["n_takes"]
                                                       for x in parts), 1)), 1),
                              R._r(q["usd_per_session"]),
                              R._r(q["capture_oracle"], 4),
                              R._r(q["co_lo"], 4), R._r(q["co_hi"], 4)])
        SC.hb("%s: deployable %s $/session (%.0fs)"
              % (tag, R._r(p["usd_per_session"]), time.time() - t0))
    R.write_tsv("%s.tsv" % OUT_NAME,
                ["arm", "era", "policy", "n_takes", "n_seated",
                 "forfeit_pct", "usd_per_session", "ps_lo", "ps_hi",
                 "usd_per_trade", "frac_ge_1000", "capture_day",
                 "capture_oracle", "co_lo", "co_hi"], dep_rows,
                extra=["THE DEPLOYABLE READING, on the schedule the HARNESS "
                       "itself selects: the per-era (unit, N) that m3_walk "
                       "chose on its own inner validation block, read out of "
                       "the committed walk.summary.json.  It never saw an "
                       "evaluation era, so applying it here leaks nothing.",
                       "The first pass used a fixed top-3-per-asset-DAY "
                       "schedule that forfeits 63-65% of its takes (one "
                       "position per asset-session).  That was a scoring "
                       "defect of this lane and these rows replace those "
                       "numbers.  Nothing is refitted: the same out-of-sample "
                       "score columns are re-seated."])
    R.write_tsv("%s_SENSITIVITY.tsv" % OUT_NAME,
                ["arm", "unit", "topn", "n_takes", "n_seated", "forfeit_pct",
                 "usd_per_session", "capture_oracle", "co_lo", "co_hi"],
                sens_rows,
                extra=["ALL TEN (unit x N) cells for every arm, pooled E3-E8, "
                       "so the selection-unit choice can never again do "
                       "invisible work in this lane."])
    return dep_rows, sens_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--tags", default="")
    ap.add_argument("--eras", default=",".join(SC.TEST_ERAS))
    ap.add_argument("--out", default="SEQTEST_SCHEDULE")
    a = ap.parse_args()
    global OUT_NAME
    OUT_NAME = a.out
    run(tags=([t for t in a.tags.split(",") if t] or None),
        eras=tuple(a.eras.split(",")))


if __name__ == "__main__":
    main()
