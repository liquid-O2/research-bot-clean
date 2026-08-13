#!/usr/bin/python3
"""PORT M0 c_d_recall — spec §9.  Needs c_c sub-pass 1 only.

Oracle: ZigZag at threshold 0.25 x ATR14_{d-1}($) (CC-M0-2.1; same algorithm as §8,
tick-rounded HALF-UP, NO spread floor) on session mids, within-instrument only.
Legs = consecutive pivot-to-pivot moves; keep the top-2 by |$ travel| per session
among legs >= $1,500.

CAPTURED(leg) iff a roster candidate exists with side == leg direction and
decision_sec in [leg_start_sec, leg_end_sec] and
(leg_end_price - mid(decision_sec)) x side x mult >= threshold (mid-to-mid,
gross; $1,000 primary, $900/$1,100 sensitivity rows).

Two leg variants are emitted (CC-M0-2.1): ANCHORED (adds the session-open
anchor and the final unconfirmed extreme as leg endpoints) is the GATE variant
-- the day's dominant legs often start at the open or run into the close;
PIVOT_TO_PIVOT (strict confirmed-pivot-to-pivot) is the diagnostic. The 0.25
rung is segmentation only; the >=$1,500 leg floor and top-2-by-travel do all
size selection.
"""
import multiprocessing as mp
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import census_common as X
import c_a_cost as CA
import c_c_roster as CC

SECTION = "§9 c_d_recall"

PARAMS = {
    "spec_section": SECTION,
    "oracle": "ZigZag at 0.25 x ATR14_{d-1}($) [CC-M0-2.1], tick-rounded HALF-UP, no spread "
              "floor, within-instrument (session slot 0), legs reset at "
              "session open",
    "leg_min_usd": X.ORACLE_LEG_MIN,
    "top_k": X.ORACLE_TOP_K,
    "capture": "side match AND decision_sec in [leg_start, leg_end] AND "
               "(leg_end_price - entry_mid) x side x mult >= threshold",
    "thresholds": list(X.RECALL_THRESHOLDS),
    "primary": X.RECALL_PRIMARY,
    "tradability_screen": "spread_at_decision <= %.1f x phase median spread "
                          "(phase of the decision second)" % X.TRADABLE_SPREAD_MULT,
    "variants": ["ANCHORED (gate, CC-M0-2.1)", "PIVOT_TO_PIVOT (diagnostic)"],
    "miss_tags": ["NO_CANDIDATE_IN_LEG", "WRONG_SIDE", "TOO_LATE",
                  "UNTRADEABLE_SPREAD", "STALE_BOOK"],
}

VARIANTS = ("PIVOT_TO_PIVOT", "ANCHORED")


# ------------------------------------------------------------------ oracle --
def oracle_legs(secs, mids, thr_px, mult, variant):
    """[(start_sec, start_px, end_sec, end_px, direction, travel_usd), ...]."""
    piv = CC.zigzag_scan(secs, mids, [thr_px] * len(mids))
    pts = [(p[1], p[0]) for p in piv]                 # (pivot_sec, pivot_px)
    if variant == "ANCHORED" and mids:
        pts = [(secs[0], mids[0])] + pts
        # the final unconfirmed extreme since the last pivot
        last = pts[-1][0]
        i0 = 0
        for i, s in enumerate(secs):
            if s > last:
                i0 = i
                break
        else:
            i0 = None
        if i0 is not None:
            tail = mids[i0:]
            ts = secs[i0:]
            hi_i = int(np.argmax(tail))
            lo_i = int(np.argmin(tail))
            j = hi_i if abs(tail[hi_i] - pts[-1][1]) >= abs(tail[lo_i] - pts[-1][1]) \
                else lo_i
            pts.append((ts[j], tail[j]))
    out = []
    for k in range(len(pts) - 1):
        s0, p0 = pts[k]
        s1, p1 = pts[k + 1]
        d = 1 if p1 > p0 else (-1 if p1 < p0 else 0)
        out.append((s0, p0, s1, p1, d, abs(p1 - p0) * mult))
    return out


def _task(args):
    asset, sess, phase_med, roster_by_date, skips_by_date, root = args
    spec = C.ASSETS[asset]
    mult = spec["mult"]
    tick_px = spec["tick_px"]
    bars = X.load_bars(asset, root)
    leg_rows = []
    for trade_date, path in sess:
        bar = bars.get(trade_date)
        atr = bar["ATR14_prev_usd"] if bar else float("nan")
        if not np.isfinite(atr):
            continue
        s = X.load_session(asset, trade_date, path)
        if s.vt.size < 2:
            continue
        thr_px = X.round_half_up(X.ORACLE_RUNG * atr / mult, tick_px)
        secs = s.vt.tolist()
        mids = s.vm.tolist()
        d8 = trade_date.year * 10000 + trade_date.month * 100 + trade_date.day
        cands = roster_by_date.get(d8, [])
        skips = skips_by_date.get(d8, [])
        for variant in VARIANTS:
            legs = oracle_legs(secs, mids, thr_px, mult, variant)
            legs = [lg for lg in legs if lg[5] >= X.ORACLE_LEG_MIN and lg[4] != 0]
            legs.sort(key=lambda lg: (-lg[5], lg[0], lg[2]))
            legs = legs[:X.ORACLE_TOP_K]
            legs.sort(key=lambda lg: (lg[0], lg[2]))
            for lg in legs:
                leg_rows.append(_score_leg(asset, trade_date, variant, lg,
                                           cands, skips, mult, phase_med, atr,
                                           thr_px))
    return leg_rows


def _score_leg(asset, trade_date, variant, lg, cands, skips, mult, phase_med,
               atr, thr_px):
    s0, p0, s1, p1, direction, travel = lg
    in_leg = [c for c in cands if s0 <= c["dec_sec"] <= s1]
    same_side = [c for c in in_leg if c["side"] == direction]
    res = {}
    for thr in X.RECALL_THRESHOLDS:
        cap_all, cap_screen = None, None
        for c in same_side:
            gain = (p1 - c["entry_mid"]) * direction * mult
            if gain + 1e-9 < thr:
                continue
            if cap_all is None or c["dec_sec"] < cap_all["dec_sec"]:
                cap_all = c
            pm = phase_med.get((asset, trade_date.year,
                                X.PHASE_NAMES[c["phase_dec"]]), float("nan"))
            ok = (np.isfinite(pm) and np.isfinite(c["spread"])
                  and c["spread"] <= X.TRADABLE_SPREAD_MULT * pm)
            if ok and (cap_screen is None or c["dec_sec"] < cap_screen["dec_sec"]):
                cap_screen = c
        res[thr] = (cap_all, cap_screen)

    cap_all, cap_screen = res[X.RECALL_PRIMARY]
    if cap_all is not None:
        tag = ""
    elif not in_leg:
        stale = [k for k in skips if s0 <= k[2] <= s1 and k[4] == CC.SKIP_NOT_TWO_SIDED]
        tag = "STALE_BOOK" if stale else "NO_CANDIDATE_IN_LEG"
    elif not same_side:
        tag = "WRONG_SIDE"
    else:
        tag = "TOO_LATE"
    tag_screen = tag
    if cap_all is not None and cap_screen is None:
        tag_screen = "UNTRADEABLE_SPREAD"

    return [asset, trade_date.isoformat(), trade_date.year, variant,
            s0, p0, s1, p1, direction, travel, atr, thr_px * mult,
            len(in_leg), len(same_side),
            int(res[900.0][0] is not None), int(res[1000.0][0] is not None),
            int(res[1100.0][0] is not None),
            int(res[1000.0][1] is not None),
            (cap_all["dec_sec"] if cap_all is not None else None),
            tag, tag_screen]


LEG_COLUMNS = ["asset", "trade_date", "year", "variant", "leg_start_sec",
               "leg_start_px", "leg_end_sec", "leg_end_px", "direction",
               "travel_usd", "atr14_prev_usd", "oracle_thr_usd",
               "n_candidates_in_leg", "n_same_side",
               "captured_900", "captured_1000", "captured_1100",
               "captured_1000_screened", "capture_dec_sec",
               "miss_tag", "miss_tag_screened"]


# ------------------------------------------------------------------- main ---
def run(assets=C.ASSET_ORDER, root=None, out_root=None, months=None, workers=10):
    root = root or C.OUT_ROOT
    out_root = out_root or C.OUT_ROOT
    phash = C.params_hash(PARAMS)
    phase_med = CA.phase_median_spreads(out_root)

    tasks = []
    for asset in assets:
        r = CC.load_roster(asset, out_root)
        by_date = {}
        for i in range(int(r["date8"].size)):
            by_date.setdefault(int(r["date8"][i]), []).append({
                "dec_sec": int(r["dec_sec"][i]),
                "side": int(r["side"][i]),
                "entry_mid": float(r["entry_mid"][i]),
                "spread": float(r["spread_at_decision"][i]),
                "phase_dec": int(r["phase_dec"][i])})
        sk = r["skips"]
        skips_by_date = {}
        for row in sk.tolist():
            skips_by_date.setdefault(int(row[0]), []).append(row)
        bm = {}
        for d, p in X.session_paths(asset, root):
            if months and X.month_key(d) not in months:
                continue
            bm.setdefault(X.month_key(d), []).append((d, p))
        for mk in sorted(bm):
            tasks.append((asset, bm[mk], phase_med, by_date, skips_by_date,
                          root))
    C.hb("c_d: %d (asset,month) tasks" % len(tasks))

    if workers <= 1 or len(tasks) <= 1:
        res = [_task(t) for t in tasks]
    else:
        with mp.Pool(min(workers, len(tasks))) as pool:
            res = list(pool.map(_task, tasks, chunksize=1))
    legs = []
    for r in res:
        legs.extend(r)
    legs.sort(key=lambda r: (r[0], r[3], r[1], r[4], r[6]))

    X.write_tsv(X.out_path(out_root, "census_d_missed_legs.tsv"), SECTION, phash,
                LEG_COLUMNS, legs,
                extra=["every oracle leg with its capture verdicts; rows with "
                       "captured_1000 == 0 are the misses that feed M1 G2/G3"])

    rollup = _rollup(legs)
    X.write_tsv(X.out_path(out_root, "census_d_recall.tsv"), SECTION, phash,
                ["asset", "era", "variant", "n_legs", "recall_900",
                 "recall_1000", "recall_1100", "recall_1000_screened",
                 "gate_recall_ge_0.95",
                 "miss_NO_CANDIDATE_IN_LEG", "miss_WRONG_SIDE", "miss_TOO_LATE",
                 "miss_STALE_BOOK", "miss_UNTRADEABLE_SPREAD_screened"],
                rollup,
                extra=["recall gate (§1) = >= %.2f, ANCHORED variant (CC-M0-2.1) at "
                       "$%.0f" % (X.GATE_RECALL, X.RECALL_PRIMARY)])
    C.hb("c_d: %d oracle legs, %d recall rows" % (len(legs), len(rollup)))
    return legs, rollup


def _rollup(legs):
    agg = {}
    for r in legs:
        asset, year, variant = r[0], int(r[2]), r[3]
        for era in X.eras_of(year):
            a = agg.setdefault((asset, era, variant),
                               {"n": 0, "c9": 0, "c10": 0, "c11": 0, "cs": 0,
                                "tags": {}, "tags_s": {}})
            a["n"] += 1
            a["c9"] += int(r[14])
            a["c10"] += int(r[15])
            a["c11"] += int(r[16])
            a["cs"] += int(r[17])
            if r[19]:
                a["tags"][r[19]] = a["tags"].get(r[19], 0) + 1
            if r[20]:
                a["tags_s"][r[20]] = a["tags_s"].get(r[20], 0) + 1
    out = []
    for k in sorted(agg):
        a = agg[k]
        n = a["n"]
        r10 = a["c10"] / n if n else float("nan")
        gate = ""
        if k[2] == "PIVOT_TO_PIVOT":
            gate = "PASS" if (n and r10 >= X.GATE_RECALL) else "FAIL"
        out.append([k[0], k[1], k[2], n,
                    a["c9"] / n if n else float("nan"), r10,
                    a["c11"] / n if n else float("nan"),
                    a["cs"] / n if n else float("nan"), gate,
                    a["tags"].get("NO_CANDIDATE_IN_LEG", 0),
                    a["tags"].get("WRONG_SIDE", 0),
                    a["tags"].get("TOO_LATE", 0),
                    a["tags"].get("STALE_BOOK", 0),
                    a["tags_s"].get("UNTRADEABLE_SPREAD", 0)])
    return out


def main():
    X.verify_spec()
    run(assets=sys.argv[1:] or list(C.ASSET_ORDER))
    return 0


if __name__ == "__main__":
    sys.exit(main())
