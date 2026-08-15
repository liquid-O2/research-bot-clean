#!/usr/bin/python3
"""PORT M2 SEQTEST — THE ALL-YEARS CRITERION TABLE.

The user's criterion is not the pooled mean: **every (era, asset) cell must
clear $2,000/session** — or the D-043/D-045 thin-era floor of $1,500 where the
era's own ceiling is thin. This writes exactly that table for any score column,
so each iteration of the final front is judged on the thing that decides it.

`thin` is not asserted here, it is EVIDENCED: each row carries the cell's own
mean day-ceiling and the ratio of realised to ceiling, so "the era's ceiling is
thin" is a reading someone can check rather than a label this file invents.

Run:  st_eratable.py --tag LMART_HP_NOTF --eras E3,E4,E5,E6,E7
"""
import argparse
import json
import os

import numpy as np

import st_common as SC
import st_run as R
import m3_common as M3
import panel_score as PS

BAR = 2000.0
THIN_FLOOR = 1500.0


def committed_policy():
    with open(os.path.join(M3.WALK_DIR, "walk.summary.json")) as fh:
        s = json.load(fh)
    return {e["era"]: (e["policy_unit"], int(e["topn"]))
            for e in s["eras"] if e.get("status") == "OK"}


def table(tag, eras, policy=None, out=None):
    import m3_walk as W
    D, _p = W.load_matrix()
    ceil = R.ceilings_of(D)
    pol = policy or committed_policy()
    z = np.load(os.path.join(R.SCORE_DIR, "%s.npz" % tag))
    s = z["champ"]
    rows = []
    n_cells = n_bar = n_floor = 0
    for era in eras:
        ev = np.nonzero((D["era_idx"] == SC.ERA_IDX[era]) & np.isfinite(s))[0]
        if ev.size == 0:
            continue
        u, n = pol.get(era, ("cell", 1))
        take = W.topn_takes(D, s, ev, n, deployable=True, unit=u)
        rep = W.replay_rows(D, take)
        for asset in ("SI", "HG", "NKD"):
            sub = [r for r in rep if r["session"].startswith(asset + "|")]
            if not sub:
                continue
            y = [r["realised"] for r in sub]
            cl = [int(r["session"].split("|")[1]) for r in sub]
            cm = PS.cluster_mean(y, cl)
            cap = [ceil.get(r["session"], (0.0, 0, 0))[0] for r in sub]
            seats = [j for r in sub for j in r["seats"]]
            pt = W.per_trade_stats(D, seats)
            dd = W.daily_drawdown(D, sub)
            mean_ceil = float(np.mean(cap)) if cap else 0.0
            v = cm["mean"]
            n_cells += 1
            n_bar += int(v >= BAR)
            n_floor += int(v >= THIN_FLOOR)
            rows.append([era, asset, len(sub), R._r(v), R._r(cm["ci_lo"]),
                         R._r(cm["ci_hi"]), R._r(pt.get("expectancy_usd")),
                         R._r(pt.get("frac_ge_1000"), 4),
                         R._r(mean_ceil), R._r(v / mean_ceil, 4)
                         if mean_ceil > 0 else "",
                         int(v >= BAR), int(v >= THIN_FLOOR),
                         R._r(dd.get("p90_dd_usd")),
                         R._r(dd.get("frac_sessions_over_bar"), 4)])
    R.write_tsv(out or ("SEQTEST_ERATABLE_%s.tsv" % tag),
                ["era", "asset", "n_sessions", "usd_per_session", "ps_lo",
                 "ps_hi", "usd_per_trade", "frac_ge_1000", "mean_day_ceiling",
                 "realised_over_ceiling", "clears_2000", "clears_1500",
                 "p90_dd_usd", "frac_dd_over_1000"], rows,
                extra=["THE ALL-YEARS CRITERION: every (era, asset) cell must "
                       "clear $2,000/session, or the D-043/D-045 thin-era floor "
                       "of $1,500 where the era's own ceiling is thin.",
                       "`mean_day_ceiling` and `realised_over_ceiling` are "
                       "carried so 'thin' is evidenced, not asserted.",
                       "%d/%d cells clear $2,000; %d/%d clear $1,500."
                       % (n_bar, n_cells, n_floor, n_cells)])
    SC.hb("%s: %d/%d cells clear $2,000, %d/%d clear $1,500"
          % (tag, n_bar, n_cells, n_floor, n_cells))
    return n_bar, n_floor, n_cells


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--eras", default=",".join(SC.TEST_ERAS))
    ap.add_argument("--out", default=None)
    ap.add_argument("--policy", default=None,
                    help="JSON of {era: [unit, N]} — an INNER-SELECTED policy")
    a = ap.parse_args()
    pol = None
    if a.policy:
        with open(a.policy) as fh:
            pol = {k: (v[0], int(v[1])) for k, v in json.load(fh).items()}
        SC.hb("using inner-selected policy: %s" % pol)
    table(a.tag, tuple(a.eras.split(",")), policy=pol, out=a.out)


if __name__ == "__main__":
    main()
