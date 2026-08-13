#!/usr/bin/python3
"""PORT M1 — §6b LEVEL RELEVANCE CENSUS (CC-M1-1 B).

Question: do our level families actually sit where the day's money is made?

For every ORACLE top-2 leg ENDPOINT (the extreme price/second of the legs the
§9 c_d oracle keeps — the same oracle the recall gate uses), we ask which level
families had a level within tol of that price at that second.

  capture(family)  = fraction of oracle extremes with a family level within tol
  null(family)     = the SAME statistic with that family's levels displaced by
                     +-0.5 x ATR14 (sign alternating by level index -
                     deterministic).  This is the mechanism-destruction control:
                     a family that "captures" only because it sprays many levels
                     across the range captures its displaced twin just as often.
  lift             = capture / null
  entry side       = conditional walled certificate value and exclusive union-DP
                     $/day of the G2 candidates BORN at that family (§6 census)

PRE-REGISTERED (CC-M1-1 B): family RETIRED if lift < 1.5 AND exclusive DP add
< $150/day.  If the UNION of all families captures < 60% of oracle extremes on
any asset, the level program returns to the orchestrator's drawing board before
M1.B freezes.
"""
import json
import multiprocessing as mp
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m1_common as M
import common as C
import census_common as X
import c_a_cost as CA
import c_c_roster as CC
import c_d_recall as CD
import b3_levels as B3
import b4_profiles as B4
import b5_generation as B5

SECTION = "§6b level relevance (CC-M1-1 B)"

NULL_DISPLACE_ATR = 0.5
LIFT_MIN = 1.5
UNION_CAPTURE_FLOOR = 0.60
RETIRE_DP_ADD = B5.RETIRE_DP_ADD

PARAMS = {
    "spec_section": SECTION,
    "oracle": "c_d ANCHORED legs at 0.25 x ATR14, >= $1,500, top-2 by travel "
              "(CC-M0-2.1); endpoints = both ends of each kept leg",
    "tolerance": "the §4 ledger tolerance",
    "null": "family levels displaced by %+.1f x ATR14 / mult, sign alternating "
            "by level index within the family (deterministic)"
            % NULL_DISPLACE_ATR,
    "lift_min": LIFT_MIN,
    "union_capture_floor": UNION_CAPTURE_FLOOR,
    "retire": "lift < %.1f AND exclusive union-DP add < $%.0f/day"
              % (LIFT_MIN, RETIRE_DP_ADD),
}


def _task(args):
    asset, sess, hist, fc = args
    spec = C.ASSETS[asset]
    mult, tick_usd, tick_px = spec["mult"], spec["tick_usd"], spec["tick_px"]
    bars = X.load_bars(asset, M.M0_ROOT)
    dates = sorted(hist)
    acc = {}
    n_end = {}
    union_hit = {}
    for trade_date, path in sess:
        bar = bars.get(trade_date)
        atr = bar["ATR14_prev_usd"] if bar else float("nan")
        if not np.isfinite(atr) or trade_date not in hist:
            continue
        s = X.load_session(asset, trade_date, path)
        if s.vt.size < 2:
            continue
        tol = max(B3.TOL_TICKS * tick_usd, B3.TOL_ATR_FRAC * atr) / mult
        disp = NULL_DISPLACE_ATR * atr / mult
        thr_px = X.round_half_up(X.ORACLE_RUNG * atr / mult, tick_px)
        legs = CD.oracle_legs(s.vt.tolist(), s.vm.tolist(), thr_px, mult,
                              "ANCHORED")
        legs = [lg for lg in legs if lg[5] >= X.ORACLE_LEG_MIN and lg[4] != 0]
        legs.sort(key=lambda lg: (-lg[5], lg[0], lg[2]))
        legs = legs[:X.ORACLE_TOP_K]
        if not legs:
            continue
        i = dates.index(trade_date)
        prev = dates[i - 1] if i >= 1 else None
        levels = B3.build_levels(asset, s, trade_date, hist, fc,
                                 B4.load_profile(asset, prev) if prev else None,
                                 B4.load_profile(asset, trade_date), atr)
        by_fam = {}
        for L in levels:
            by_fam.setdefault(L.family, []).append(L)
        eps = []
        for lg in legs:
            eps.append((lg[0], lg[1]))
            eps.append((lg[2], lg[3]))
        year = trade_date.year
        for (sec, px) in eps:
            j = int(np.searchsorted(s.vt, sec, side="left"))
            if j >= s.vt.size:
                continue
            for era in (M.ERA_FIT, M.ERA_GATE, M.ERA_ALL):
                if era == M.ERA_FIT and not M.is_fit(year):
                    continue
                if era == M.ERA_GATE and year != 2025:
                    continue
                n_end[(era,)] = n_end.get((era,), 0) + 1
                any_hit = False
                for fam, ls in by_fam.items():
                    hit = nhit = 0
                    for k, L in enumerate(ls):
                        if L.active_from > sec:
                            continue
                        p = (float(L.series[j]) if L.dynamic
                             else float(L.price))
                        if not np.isfinite(p):
                            continue
                        if abs(p - px) <= tol:
                            hit = 1
                        sgn = 1.0 if (k % 2 == 0) else -1.0
                        if abs(p + sgn * disp - px) <= tol:
                            nhit = 1
                    a = acc.setdefault((fam, era), [0, 0, 0])
                    a[0] += 1
                    a[1] += hit
                    a[2] += nhit
                    any_hit = any_hit or bool(hit)
                union_hit[(era,)] = union_hit.get((era,), 0) + int(any_hit)
    return asset, acc, n_end, union_hit


def entry_side(assets):
    """Per LEVEL family: G2 candidate count, conditional walled cert value and
    EXCLUSIVE union-DP add (the §6 machinery, restricted to G2 births)."""
    with open(os.path.join(M.M0_ROOT, "walls.json")) as fh:
        walls = json.load(fh)["walls"]
    cost_map = CA.session_cost_rt(M.M0_ROOT)
    lvl_fams = list(B3.FAMILIES)
    rows = []
    for asset in assets:
        z = np.load(M.out_path("generation", "union_roster_%s.npz" % asset),
                    allow_pickle=False)
        r = {k: z[k] for k in z.files}
        z.close()
        W = float(walls[asset]["wall_usd"])
        fm = r["fam_mask"]
        lm = r["level_fam_mask"]
        g2bits = B5.FAM_BIT["G2_REJECT"] | B5.FAM_BIT["G2_RECLAIM"]
        by_date = {}
        for i in range(int(r["date8"].size)):
            by_date.setdefault(int(r["date8"][i]), []).append(i)
        vals = {f: [] for f in lvl_fams}
        adds = {f: [] for f in lvl_fams}
        ns = {f: 0 for f in lvl_fams}
        for d in sorted(by_date):
            iso = "%04d-%02d-%02d" % (d // 10000, (d // 100) % 100, d % 100)
            cost = cost_map.get((asset, iso), float("nan"))
            if not np.isfinite(cost):
                cost = C.FEES_RT
            idx = by_date[d]
            items, cert = [], {}
            for i in idx:
                _pk, cl = CC.certificates(r, i, W, cost)
                cert[i] = cl[0]
                items.append((cl[1], cl[2], cl[0], int(r["dec_sec"][i]),
                              int(r["iid"][i]), i))
            tot, _ = CC.dp_schedule(items)
            for fi, f in enumerate(lvl_fams):
                bit = 1 << fi
                born = [i for i in idx if (int(lm[i]) & bit)
                        and (int(fm[i]) & g2bits)]
                for i in born:
                    vals[f].append(cert[i])
                ns[f] += len(born)
                exc = set(i for i in idx
                          if int(lm[i]) == bit and (int(fm[i]) & ~g2bits) == 0)
                if exc:
                    rtot, _ = CC.dp_schedule([it for it in items
                                              if it[5] not in exc])
                    adds[f].append(tot - rtot)
                else:
                    adds[f].append(0.0)
        for f in lvl_fams:
            rows.append([asset, f, ns[f], M.mean(vals[f]), M.med(vals[f]),
                         M.med(adds[f]), M.mean(adds[f]),
                         sum(1 for v in vals[f] if v > 0)])
        M.hb("b6 entry-side %s: done" % asset)
    return rows


def main():
    M.verify_spec()
    workers = int(os.environ.get("M1_WORKERS", "6"))
    assets = [a for a in sys.argv[1:] if a in M.ASSET_ORDER] or list(M.ASSET_ORDER)
    phash = C.params_hash(PARAMS)
    tasks = []
    for asset in assets:
        tasks.append((asset, X.session_paths(asset, M.M0_ROOT),
                      B3.load_v1_history(asset), B3.load_forecasts(asset)))
    M.hb("b6: %d asset tasks" % len(tasks))
    if len(tasks) <= 1:
        res = [_task(t) for t in tasks]
    else:
        with mp.Pool(min(3, len(tasks))) as pool:
            res = list(pool.map(_task, tasks, chunksize=1))

    es = {(r[0], r[1]): r for r in entry_side(assets)}
    rows, union_rows = [], []
    for (asset, acc, n_end, union_hit) in res:
        for era in (M.ERA_FIT, M.ERA_GATE, M.ERA_ALL):
            n = n_end.get((era,), 0)
            if not n:
                continue
            union_rows.append([asset, era, n, union_hit.get((era,), 0),
                               union_hit.get((era,), 0) / n,
                               "PASS" if union_hit.get((era,), 0) / n
                               >= UNION_CAPTURE_FLOOR else
                               "DRAWING_BOARD_TRIGGER"])
        for (fam, era), a in sorted(acc.items()):
            cap = a[1] / a[0] if a[0] else float("nan")
            nul = a[2] / a[0] if a[0] else float("nan")
            lift = (cap / nul) if (np.isfinite(nul) and nul > 0) else float("inf")
            e = es.get((asset, fam), [None] * 8)
            dpadd = e[5] if e[5] is not None else float("nan")
            retire = ""
            if era == M.ERA_FIT:
                retire = ("RETIRE" if (np.isfinite(lift) and lift < LIFT_MIN
                                       and (not np.isfinite(dpadd)
                                            or dpadd < RETIRE_DP_ADD))
                          else "KEEP")
            rows.append([asset, fam, era, a[0], a[1], cap, a[2], nul, lift,
                         e[2], e[3], e[4], dpadd, retire])
    M.write_tsv(M.out_path("generation", "level_relevance.tsv"), SECTION,
                phash, ["asset", "level_family", "era", "n_oracle_extremes",
                        "n_hit", "capture", "n_hit_null", "null_capture",
                        "lift", "n_g2_candidates", "mean_cert_usd",
                        "median_cert_usd", "exclusive_dp_add_median_usd",
                        "decision"], rows,
                extra=[PARAMS["null"], PARAMS["retire"]])
    M.write_tsv(M.out_path("generation", "level_relevance_union.tsv"), SECTION,
                phash, ["asset", "era", "n_oracle_extremes", "n_captured",
                        "union_capture", "gate_ge_60pct"], union_rows,
                extra=["union capture < %.0f%% on any asset => the level "
                       "program returns to the drawing board (CC-M1-1 B)"
                       % (UNION_CAPTURE_FLOOR * 100)])
    return 0


if __name__ == "__main__":
    sys.exit(main())
