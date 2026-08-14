#!/usr/bin/python3
"""E1 STUDY DAY 5 — AS-OF PREFIX VIEW of the day-complete triage index (D14).

Day 3 named SCAN-EXPOSED (ERA_NOTES §37): the triage index is DAY-COMPLETE, so
scanning it to find candidates necessarily shows rows from LATER decision
seconds, and those rows' `mid` column is the price path AFTER the second being
called.  CC-M2-12.1(a) makes an as-of prefix view MANDATORY before any BLIND
round.  `triage_index.py --as-of` EXISTS in the working tree of the tooling
lane but has NOT LANDED AT HEAD (it is not in any commit as of this day's
draw), so the reader continues to use its own lane's mechanic — day 4's
`e1d4_asof.py`, carried forward here for the day-5 term set and for the one
thing day 5 adds: the SIDE STATE, which is itself a prefix quantity.

WHAT IT ENFORCES.  Every view this module prints for candidate C at decision
second S contains ONLY rows with sec <= S (C's own row included).  There is no
mode that prints a later row.  The side state shown is recomputed FROM THE
PREFIX ONLY, so a candidate never sees a confirmation that has not yet
happened.  The reader walks the day forward:

    e1d5_asof.py --index IDX --policy POL --next            # first TAKE
    e1d5_asof.py --index IDX --policy POL --next --after N  # the one after N
    e1d5_asof.py --index IDX --policy POL --at CID          # one row, as of it
    e1d5_asof.py --index IDX --policy POL --at CID --context 12 --asset HG

`--next` prints exactly ONE candidate, so the reader never sees the day's take
list as a list: the second take is invisible until the first is committed.
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e1d5_policy as POLICY                                   # noqa: E402

SHOW = ("cid asset date8 side sec clock phase_dec cls vol_regime "
        "day_type_so_far range_vs_hat_pct cov_phase cov_sess runway_phase "
        "runway_sess exit_is_sess phase_H phase_H_sec phase_L phase_L_sec "
        "extreme_age_trade_side n_pivots near_fam near_d n_conf_max min_tc_near "
        "or_state trades_min slope1m slope5m spread_dec cost_rt rev_s_60 "
        "c2f_300 dBsz_min dAsz_min f60_n f60_vol f60_sflow f5m_n f5m_vol "
        "f5m_sflow f30m_vol f30m_sflow fph_sflow fph_vol sched_last_age "
        "sched_next_in trapped_above trapped_below thru_n thru_bid thru_ask "
        "rv60 rv1800 rv_collapse jump_frac vol_of_vol q50 ladder_pos surprise "
        "mid mult room_phase ext_needed").split()


def load(index, policy):
    with open(index) as fh:
        rows = list(csv.DictReader(
            [ln for ln in fh if not ln.startswith("#")], delimiter="\t"))
    pol = {}
    if policy:
        with open(policy) as fh:
            for p in csv.DictReader(fh, delimiter="\t"):
                pol[p["cid"]] = p
    for r in rows:
        r["_sec"] = int(float(r["sec"]))
    rows.sort(key=lambda r: (r["_sec"], r["cid"]))
    return rows, pol


def prefix(rows, sec):
    return [r for r in rows if r["_sec"] <= sec]


def show_row(r, pol):
    print("=" * 78)
    print("CANDIDATE %s  (%s %s %s %s)"
          % (r["cid"], r["asset"], r["clock"], r["phase_dec"], r["cls"]))
    p = pol.get(r["cid"])
    if p:
        print("  policy: %s grade %s  n_terms %s  terms %s  side_gate %s"
              % (p["call"], p["conf"], p["n_terms"],
                 "".join(p[k] for k in POLICY.TERMS), p.get("side_gate", "?")))
    for k in SHOW:
        if k in r and r[k] not in ("", "."):
            print("    %-24s %s" % (k, r[k]))
    if p:
        print("  PRIMARY: %s" % p["primary"])
        print("  AGAINST: %s" % p["against"])


def prefix_state(rows, r, asset=None, context=0):
    """Session state AS OF this candidate's second — prefix rows only."""
    pre = prefix(rows, r["_sec"])
    a = asset or r["asset"]
    mine = [x for x in pre if x["asset"] == a]
    print("-" * 78)
    print("PREFIX STATE as of sec=%d (%s): %d rows in the day so far, %d on %s"
          % (r["_sec"], r["clock"], len(pre), len(mine), a))
    # the side estimator recomputed on the PREFIX ONLY (day-5's own hazard:
    # the state must never be read from a confirmation that has not happened)
    st = POLICY.side_state(pre)
    for ln in POLICY.side_state_log(st):
        print("  SIDE-STATE(prefix) %s" % ln)
    if context and mine:
        print("  last %d %s rows before/at this second:" % (context, a))
        for x in mine[-context:]:
            print("    %-28s %s %-6s %-7s mid=%-9s f60=%s/%s f5m=%s/%s "
                  "ext=%s"
                  % (x["cid"], x["clock"], x["phase_dec"], x["side"],
                     x["mid"], x["f60_n"], x["f60_vol"], x["f5m_sflow"],
                     x["f5m_vol"], x["ext_needed"]))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--index", required=True)
    p.add_argument("--policy", default="")
    p.add_argument("--next", action="store_true")
    p.add_argument("--after", type=int, default=-1)
    p.add_argument("--at", default="")
    p.add_argument("--asset", default="")
    p.add_argument("--context", type=int, default=0)
    p.add_argument("--call", default="TAKE")
    a = p.parse_args()
    rows, pol = load(a.index, a.policy)
    if a.at:
        r = [x for x in rows if x["cid"] == a.at]
        if not r:
            raise SystemExit("no such cid: %s" % a.at)
        show_row(r[0], pol)
        prefix_state(rows, r[0], a.asset, a.context)
        return 0
    if a.next:
        for r in rows:
            if r["_sec"] <= a.after:
                continue
            if a.asset and r["asset"] != a.asset:
                continue
            p_ = pol.get(r["cid"])
            if a.call and (not p_ or p_["call"] != a.call):
                continue
            show_row(r, pol)
            prefix_state(rows, r, a.asset, a.context)
            print("NEXT: --next --after %d" % r["_sec"])
            return 0
        print("no further %s rows after sec=%d%s"
              % (a.call, a.after, (" on " + a.asset) if a.asset else ""))
        return 0
    raise SystemExit("use --next or --at CID")


if __name__ == "__main__":
    sys.exit(main())
