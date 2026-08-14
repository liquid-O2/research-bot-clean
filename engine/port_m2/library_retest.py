#!/usr/bin/python3
"""PORT M2 — THE D-059 LIBRARY RE-TEST, RUN FROM THE CUMULATIVE CUE LEDGER.

D-059(2) is a duty, not a suggestion: "Each new era's STUDY opens with a
LIBRARY RE-TEST: re-score every prior pattern on the new era before new
discovery."  Round 1 never ran one mechanically — its patterns were re-argued
in prose.  R2-11 makes the duty cheap: the ledger already holds every named cue
with its predicate, so re-scoring the whole library on a new STUDY day is one
pass over that day's triage table.

STUDY DAYS ONLY.  It imports `e6_round.oracle`, which refuses every date in the
E6 BLIND block.  Nothing here can be pointed at a sealed day.

WHAT IT PRINTS
  1. per-cue: n, winners, rate, lift vs the day's own base rate, and the
     ROUND-1 verdict beside it — so a cue that has stopped working is visible
     as a disagreement, not as a number needing interpretation;
  2. the ledger-derived probability's BRIER against the constant base rate —
     the round-1 reader's probabilities lost to a constant, and this is the
     instrument that says whether round 2's do better;
  3. the day's capacity bands, because that is where round 1's whole measured
     edge lived.

CLI  library_retest.py --day 20240415 [--assets SI,HG,NKD]
"""
import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import cue_ledger as CL                   # noqa: E402
import e6_round as E6                     # noqa: E402


def _f(v, default=float("nan")):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def episode_rows(d8, assets=None):
    """(episode_id, asset, dict of delta col -> value) for every episode."""
    out = []
    for asset, epid, line in E6.deltas(d8, assets, traj=False):
        f = line.split("\t")
        d = dict(zip(E6.DELTA_COLS, f))
        out.append((epid, asset, d))
    return out


def cues(d):
    """Every ledger cue that is computable from the delta row, as a dict."""
    side = 1.0 if str(d.get("side", "L")).upper().startswith("L") else -1.0
    uns = _f(d.get("unspent_phase_usd"))
    run = _f(d.get("runway_phase"))
    cov = _f(d.get("cov_phase"))
    near_d = _f(d.get("near_d"))
    mtc = _f(d.get("min_tc_near"))
    f5 = _f(d.get("f5m_sflow"), 0.0)
    f60 = _f(d.get("f60_sflow"), 0.0)
    fph = _f(d.get("fph_sflow"), 0.0)
    ta, tb = _f(d.get("trap_ab"), 0.0), _f(d.get("trap_bl"), 0.0)
    tot = ta + tb
    fuel = (ta if side > 0 else tb) / tot if tot > 0 else float("nan")
    nev = _f(d.get("n_ev_60"), 0.0)
    rv60, rv1800 = _f(d.get("rv60")), _f(d.get("rv1800"))
    age = _f(d.get("extreme_age"))
    spr = _f(d.get("spread_dec"))
    tmz = _f(d.get("tm_z"))
    dpoc = _f(d.get("d_POC"))
    ref = _f(d.get("refill_frac"))
    lad = str(d.get("ladder_pos", ""))
    c = {
        "SEAT_LIVE": uns >= 700 and run >= 18000,
        "SEAT_DEAD_TIME": run < 4800,
        "PHASE_SPENT": cov >= 80,
        "COV_SWEET_20_60": 20 <= cov < 60,
        "cov_low": cov <= 40,
        "capacity_room": uns >= 400,
        "capacity_big": uns >= 1000,
        "capacity_spent": uns < 400,
        "runway_ok": run >= 2400,
        "LEVEL_VIRGIN": mtc == 0,
        "level_near": abs(near_d) <= 60,
        "level_at_price": abs(near_d) <= 10,
        "level_tested_held": abs(near_d) <= 60 and mtc >= 1,
        "fresh_extreme": age <= 900,
        "stale_extreme": age > 6000,
        "flow_agree_5m": f5 * side > 0,
        "flow_against_5m": f5 * side < 0,
        "one_sided_flow": f5 * side > 0 and fph * side > 0,
        "flow_strong": f5 * side > 0 and fph * side > 0 and abs(f5) >= 50,
        "flow_flip": f60 * side > 0 and f5 * side <= 0,
        "fuel_trapped": fuel >= 0.65,
        "fuel_extreme": fuel >= 0.90,          # R2 refinement, see journal
        "event_burst": nev >= 400 and rv60 > 0.4 * rv1800,
        "tmz_burst": tmz >= 3,
        "wide_spread": spr >= 50,
        "expanding": lad.startswith("at_or_above_q5") or
                     lad.startswith("at_or_above_q7") or
                     lad.startswith("at_or_above_q9") or
                     (rv60 == rv60 and rv1800 == rv1800 and rv60 > 0.9 * rv1800),
        "poc_magnet": dpoc * side > 0 and abs(dpoc) >= 200,
        "refill_book": ref >= 0.60,
    }
    c["NAMED_TRIAD_soft"] = (c["capacity_room"] and c["level_near"] and
                             c["flow_agree_5m"])
    return c


def p_from_ledger(c, base):
    """The ledger's OWN forecast: base rate multiplied by the PROVEN lifts only.

    Deliberately crude and deliberately not fitted — the point is to test
    whether last round's PROVEN cues still carry information on a new day, not
    to build a model.  FALSIFIED/NULL cues contribute nothing, which is exactly
    what the ledger says they are worth.
    """
    p = base
    if c["SEAT_DEAD_TIME"]:
        return min(0.01, base * 0.05)
    if c["SEAT_LIVE"]:
        p *= 2.62
    if c["capacity_spent"]:
        p *= 0.50
    if c["PHASE_SPENT"]:
        p *= 0.55
    if c["COV_SWEET_20_60"]:
        p *= 1.40
    if c["LEVEL_VIRGIN"]:
        p *= 1.67
    return max(0.002, min(0.75, p))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", type=int, required=True)
    ap.add_argument("--assets", default=None)
    a = ap.parse_args(argv)
    assets = a.assets.split(",") if a.assets else None
    rows = episode_rows(a.day, assets)
    res = E6.oracle(a.day, assets)          # REFUSES any blind-block date
    win = {}
    for _asset, r in res.items():
        for eid, v in r["ep_out"].items():
            win[eid] = int(v["rep_win"])
    ep = [(eid, asset, d) for eid, asset, d in rows if eid in win]
    n = len(ep)
    base = sum(win[e] for e, _a, _d in ep) / float(n)
    print("LIBRARY RE-TEST (D-059.2) day=%d episodes=%d base=%.4f" %
          (a.day, n, base))
    led = {r["cue"]: r for r in CL.read_ledger()}
    names = sorted(cues(ep[0][2]).keys())
    print("%-18s %5s %5s %7s %7s  %-11s %s" %
          ("cue", "n", "win", "rate", "lift", "R1_verdict", "R1_lift"))
    out = []
    for nm in names:
        sel = [e for e, _a, d in ep if cues(d)[nm]]
        k = sum(win[e] for e in sel)
        if not sel:
            out.append((0.0, "%-18s %5d %5d %7s %7s  %-11s %s"
                        % (nm, 0, 0, ".", ".",
                           led.get(nm, {}).get("r1_verdict", "-"),
                           led.get(nm, {}).get("r1_blind_lift", "-"))))
            continue
        rate = k / float(len(sel))
        lift = rate / base if base else float("nan")
        out.append((lift, "%-18s %5d %5d %7.4f %7.2f  %-11s %s"
                    % (nm, len(sel), k, rate, lift,
                       led.get(nm, {}).get("r1_verdict", "-"),
                       led.get(nm, {}).get("r1_blind_lift", "-"))))
    for _l, s in sorted(out, key=lambda t: -t[0]):
        print(s)
    bl = bc = 0.0
    for e, _a, d in ep:
        p = p_from_ledger(cues(d), base)
        bl += (p - win[e]) ** 2
        bc += (base - win[e]) ** 2
    print("\nBRIER ledger-derived p = %.5f   constant base = %.5f   %s"
          % (bl / n, bc / n,
             "LEDGER BEATS CONSTANT" if bl < bc else "LEDGER LOSES TO CONSTANT"))
    bands = [("<0", -1e18, 0), ("0-400", 0, 400), ("400-700", 400, 700),
             ("700-1000", 700, 1000), ("1000-1500", 1000, 1500),
             (">=1500", 1500, 1e18)]
    print("\nunspent_phase_usd bands (round-1 break was at $700):")
    for nm, lo, hi in bands:
        sel = [e for e, _a, d in ep if lo <= _f(d.get("unspent_phase_usd"), -1e17) < hi]
        if sel:
            k = sum(win[e] for e in sel)
            print("  %-10s n=%-5d win=%-4d rate=%.4f lift=%.2f"
                  % (nm, len(sel), k, k / float(len(sel)),
                     (k / float(len(sel))) / base))
    rb = [("<4800", 0, 4800), ("4800-9000", 4800, 9000),
          ("9000-18000", 9000, 18000), ("18000-30000", 18000, 30000),
          (">=30000", 30000, 1e18)]
    print("runway_phase bands (round-1 cliff at 4,800s, payoff from 18,000s):")
    for nm, lo, hi in rb:
        sel = [e for e, _a, d in ep if lo <= _f(d.get("runway_phase"), -1) < hi]
        if sel:
            k = sum(win[e] for e in sel)
            print("  %-12s n=%-5d win=%-4d rate=%.4f lift=%.2f"
                  % (nm, len(sel), k, k / float(len(sel)),
                     (k / float(len(sel))) / base))
    print("\nper-asset / per-phase:")
    for key, fn in (("asset", lambda d: d["as"]),):
        vals = sorted({fn(d) for _e, _a, d in ep})
        for v in vals:
            sel = [e for e, _a, d in ep if fn(d) == v]
            k = sum(win[e] for e in sel)
            print("  %-6s n=%-5d win=%-4d rate=%.4f lift=%.2f"
                  % (v, len(sel), k, k / float(len(sel)),
                     (k / float(len(sel))) / base))
    return 0


if __name__ == "__main__":
    sys.exit(main())
