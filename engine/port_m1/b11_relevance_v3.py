#!/usr/bin/python3
"""PORT M1.B S1.1 — D-052 LEVEL RELEVANCE RE-VERIFICATION on the CURRENT ledger.

CC-M1-6.5 / H9: OR_EXT was adopted on the H/L census's own prediction metric
(marginal pp of rest-of-window extremes).  H9 accepted, as a residual, that its
relevance against the D-053 ledger would be re-verified by construction when
S1.1 landed.  This is that re-verification, and it is the §6b census of
CC-M1-1(B) re-run VERBATIM on the ENRICHED ledger (m1/levels_v4, seven
families):

  capture(family) = fraction of ORACLE top-2 leg ENDPOINTS with a family level
                    within tol at that price and second;
  null(family)    = the same statistic with that family's levels displaced by
                    +-0.5 x ATR14 (sign alternating by level index) — the
                    mechanism-destruction control;
  lift            = capture / null;
  entry side      = the conditional walled certificate value and the exclusive
                    union-DP $/day of the G2 candidates BORN at that family, on
                    the S1.1+S1.2 enriched roster (m1/generation_v3).

PRE-REGISTERED (CC-M1-1 B, unchanged): a family is RETIRED if lift < 1.5 AND
exclusive DP add < $150/day.  Union capture < 60% on any asset sends the level
program back to the drawing board.

SCOPE LAW (the reason this is not a copy of b6_relevance): OR_EXT levels are
SEGMENT-scoped and only exist once their opening range has closed, so a level
counts toward an extreme only when the extreme falls inside that level's own
phase, after its activation second.  Scoring it otherwise is the same
segment-scope bug the discovery lane froze a mutant for; here it is enforced in
`level_prices_at` and mutated in test_m1c.py.

Run: lab/run.sh port-m1-s11-relevance -- /usr/bin/python3 engine/port_m1/b11_relevance_v3.py
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
import b7_sane as B7
import b10_levels_v4 as L4
import b10_generation_v3 as G3

SECTION = "S1.1 D-052 relevance re-verification (CC-M1-1 B on levels_v4)"
OUT_DIR = G3.OUT_DIR

NULL_DISPLACE_ATR = 0.5
LIFT_MIN = 1.5
UNION_CAPTURE_FLOOR = 0.60
RETIRE_DP_ADD = 150.0

PARAMS = {
    "spec_section": SECTION,
    "ledger": "m1/%s — the CURRENT (D-053 + D-054 + CC-M1-6.1) ledger, seven "
              "families" % L4.OUT_DIR,
    "oracle": "c_d ANCHORED legs at 0.25 x ATR14, >= $1,500, top-2 by travel, "
              "on the D-054 SANE mids; endpoints = both ends of each kept leg",
    "tolerance": "the §4 ledger tolerance max(2 x tick_$, 0.05 x ATR14_$)/mult",
    "null": "family levels displaced %+.1f x ATR14 / mult, sign alternating by "
            "level index within the family (deterministic)" % NULL_DISPLACE_ATR,
    "scope": "a level counts only when it is ACTIVE (created_sec <= extreme "
             "second) and, if segment-scoped, when the extreme falls inside "
             "its own phase",
    "lift_min": LIFT_MIN,
    "union_capture_floor": UNION_CAPTURE_FLOOR,
    "retire": "lift < %.1f AND exclusive union-DP add < $%.0f/day"
              % (LIFT_MIN, RETIRE_DP_ADD),
}


def level_prices_at(levels, j, sec, phase):
    """{family: [price,...]} of the levels ACTIVE at (sec, phase).

    j = index of `sec` in the session's observed-second arrays (dynamic level
    series are sampled there).  The two exclusions are the whole point:
    active_from > sec is a level that does not exist yet (look-ahead), and a
    segment-scoped level outside its own phase does not exist at all.
    """
    out = {}
    for L in levels:
        if L.active_from > sec:
            continue
        if L.scope_phase is not None and int(phase) != int(L.scope_phase):
            continue
        p = float(L.series[j]) if L.dynamic else float(L.price)
        if not np.isfinite(p):
            continue
        out.setdefault(L.family, []).append(p)
    return out


def _task(args):
    asset, sess, hist, fc, sane_thr = args
    spec = C.ASSETS[asset]
    mult, tick_usd, tick_px = spec["mult"], spec["tick_usd"], spec["tick_px"]
    bars = X.load_bars(asset, M.M0_ROOT)
    dates = sorted(hist)
    acc, n_end, union_hit = {}, {}, {}
    for trade_date, path in sess:
        bar = bars.get(trade_date)
        atr = bar["ATR14_prev_usd"] if bar else float("nan")
        if not np.isfinite(atr) or trade_date not in hist:
            continue
        s = X.load_session(asset, trade_date, path)
        thr = sane_thr.get(M.d8(trade_date))
        B7.apply(s, thr if thr is not None
                 else [B7.SANE_CAP_USD] * X.N_PHASES)
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
        eps = []
        for lg in legs:
            eps.append((lg[0], lg[1]))
            eps.append((lg[2], lg[3]))
        year = trade_date.year
        for (sec, px) in eps:
            j = int(np.searchsorted(s.vt, sec, side="left"))
            if j >= s.vt.size:
                continue
            by_fam = level_prices_at(levels, j, sec, s.phase_tag[int(sec)])
            eras = [e for e in M.eras_of(year)]
            any_hit = False
            for era in eras:
                n_end[era] = n_end.get(era, 0) + 1
            for fam in B3.FAMILIES + (B3.OREXT_FAMILY,):
                ls = by_fam.get(fam, [])
                hit = nhit = 0
                for k, p in enumerate(ls):
                    if abs(p - px) <= tol:
                        hit = 1
                    sgn = 1.0 if (k % 2 == 0) else -1.0
                    if abs(p + sgn * disp - px) <= tol:
                        nhit = 1
                if not ls:
                    continue          # the family declares nothing here
                for era in eras:
                    a = acc.setdefault((fam, era), [0, 0, 0])
                    a[0] += 1
                    a[1] += hit
                    a[2] += nhit
                any_hit = any_hit or bool(hit)
            for era in eras:
                union_hit[era] = union_hit.get(era, 0) + int(any_hit)
    return asset, acc, n_end, union_hit


# ------------------------------------------------------------- entry side ----
def entry_side(assets):
    """Per LEVEL family on the ENRICHED roster: G2 births, conditional value,
    exclusive union-DP add."""
    with open(os.path.join(M.M0_ROOT, "walls.json")) as fh:
        walls = json.load(fh)["walls"]
    cost_map = CA.session_cost_rt(M.M0_ROOT)
    lvl_fams = list(G3.KEPT_LEVEL_FAMILIES)
    rows = []
    for asset in assets:
        z = np.load(M.out_path(G3.OUT_DIR, "union_roster_%s.npz" % asset),
                    allow_pickle=False)
        r = {k: z[k] for k in z.files}
        z.close()
        W = float(walls[asset]["wall_usd"])
        fm, lm = r["fam_mask"], r["level_fam_mask"]
        g2bits = G3.FAM_BIT["G2_REJECT"] | G3.FAM_BIT["G2_RECLAIM"]
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
            pos = [v for v in vals[f] if v > 0]
            rows.append([asset, f, ns[f], M.mean(vals[f]), M.med(vals[f]),
                         (M.mean(pos) if pos else float("nan")), len(pos),
                         M.med(adds[f]), M.mean(adds[f])])
        M.hb("b11 entry-side %s: done" % asset)
    return rows


def main():
    M.verify_spec_m1b()
    workers = int(os.environ.get("M1_WORKERS", "6"))
    assets = [a for a in sys.argv[1:] if a in M.ASSET_ORDER] or \
        list(M.ASSET_ORDER)
    phash = C.params_hash(PARAMS)
    B3.OREXT_CELLS = {a: L4.OREXT_ADOPTED[a] for a in assets}
    tasks = []
    for asset in assets:
        tasks.append((asset, X.session_paths(asset, M.M0_ROOT),
                      B3.load_v1_history(asset), B3.load_forecasts(asset),
                      B7.load_thresholds(asset)))
    M.hb("b11 relevance: %d asset tasks on %s" % (len(tasks), L4.OUT_DIR))
    if len(tasks) <= 1:
        res = [_task(t) for t in tasks]
    else:
        with mp.Pool(min(3, len(tasks))) as pool:
            res = list(pool.map(_task, tasks, chunksize=1))

    es = {(r[0], r[1]): r for r in entry_side(assets)}
    rows, union_rows = [], []
    for (asset, acc, n_end, union_hit) in res:
        for era in (M.ERA_FIT, M.ERA_GATE, M.ERA_ALL):
            n = n_end.get(era, 0)
            if not n:
                continue
            union_rows.append([asset, era, n, union_hit.get(era, 0),
                               union_hit.get(era, 0) / n,
                               "PASS" if union_hit.get(era, 0) / n
                               >= UNION_CAPTURE_FLOOR
                               else "DRAWING_BOARD_TRIGGER"])
        for (fam, era), a in sorted(acc.items()):
            cap = a[1] / a[0] if a[0] else float("nan")
            nul = a[2] / a[0] if a[0] else float("nan")
            lift = (cap / nul) if (np.isfinite(nul) and nul > 0) \
                else float("inf")
            e = es.get((asset, fam), [None] * 9)
            dpadd = e[7] if e[7] is not None else float("nan")
            decision = ""
            if era == M.ERA_FIT:
                decision = ("RETIRE" if (np.isfinite(lift) and lift < LIFT_MIN
                                         and (not np.isfinite(dpadd)
                                              or dpadd < RETIRE_DP_ADD))
                            else "KEEP")
            rows.append([asset, fam, era, a[0], a[1], cap, a[2], nul, lift,
                         e[2], e[5], e[6], dpadd, decision])
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    M.write_tsv(M.out_path(OUT_DIR, "level_relevance_v3.tsv"), SECTION, phash,
                ["asset", "level_family", "era", "n_scored_extremes", "n_hit",
                 "capture", "n_hit_null", "null_capture", "lift",
                 "n_g2_candidates", "conditional_value_usd", "n_positive",
                 "exclusive_dp_add_median_usd", "decision"], rows,
                spec="PORT_M1B",
                extra=[PARAMS["null"], PARAMS["scope"], PARAMS["retire"],
                       "DENOMINATOR LAW: an extreme is scored for a family "
                       "only where that family declares an ACTIVE, in-scope "
                       "level; capture and its displaced null share that "
                       "denominator"])
    M.write_tsv(M.out_path(OUT_DIR, "level_relevance_v3_union.tsv"), SECTION,
                phash, ["asset", "era", "n_oracle_extremes", "n_captured",
                        "union_capture", "gate_ge_60pct"], union_rows,
                spec="PORT_M1B",
                extra=["union capture < %.0f%% on any asset => the level "
                       "program returns to the drawing board (CC-M1-1 B)"
                       % (UNION_CAPTURE_FLOOR * 100)])
    for r in rows:
        if r[1] == B3.OREXT_FAMILY and r[2] == M.ERA_FIT:
            M.hb("b11 OR_EXT %s FIT: capture %.4f null %.4f lift %.2f "
                 "g2 %s cond $%s -> %s"
                 % (r[0], r[5], r[7], r[8], r[9], r[10], r[13]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
