#!/usr/bin/python3
"""E1 STUDY DAY 8 — THE POLICY PRE-REGISTRATION: replay the CORRECTED stack
over the seven unblinded sessions BEFORE calling a single day-8 row.

The thresholds were settled on the POOLED ROW POOL in `e1d8_stage12.py`
(ERA_NOTES §33/§41 method law).  THIS module does not choose them; it REPORTS
what the resulting fixed policies bank in one-position phase-close replay
(CC-M2-10.3) over days 1-7, so the day-8 arm is chosen with its own historical
record in front of the reader and on the record — the thing days 1-7 never had.

ARMS
  CORE            T1..T5, the inherited moment core with the CC-M2-16.4 T5 repair
  CORE-T2         the same WITHOUT P025's 12,000s runway floor (CC-M2-19.3
                  BROKE P025: 54 of day 7's 123 winners sit below it)
  +R1             rolling `rv1800 >= 250` at the CANDIDATE'S OWN ROW
  +R2             rolling `unspent_sess >= $500` (PASS when REFUSED)
  +R2b            rolling `unspent_bind >= $1,000` (the ERA_NOTES §77 field)
  +V2             the fuel-overhang veto
  +V3             P018 two-stream opposition (ADVISORY today, pooled re-grade
                  pending — reported, not run)
  +ORACLE SIDE    the (asset,phase)-cell winner-majority side: the ceiling the
                  side stage is worth, restated on seven sessions
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e1d8_stage12 as S                                       # noqa: E402
import e1d8_policy as P                                        # noqa: E402
import panel_score as PS                                       # noqa: E402


def cell_truth(tag):
    t = {}
    for r in S.load(tag):
        if PS.outcome(r["cid"])["winner_close"]:
            a = t.setdefault((r["asset"], r["phase_dec"]), [0, 0])
            a[0 if r["side"] == "LONG" else 1] += 1
    return {k: ("LONG" if v[0] > v[1] else "SHORT") for k, v in t.items()}


def arm_records(tag, fn):
    recs = []
    for r in S.load(tag):
        recs.append({"call": "TAKE" if fn(r, tag) else "SKIP",
                     "outcome": PS.outcome(r["cid"]), "cid": r["cid"]})
    return recs


def run_persession(name, fn):
    print("\nPER-SESSION (%s) — the mirror law applied at REPLAY grain" % name)
    print("%-8s %10s %10s %10s" % ("day", "replay $", "CORE $", "delta"))
    tot = 0.0
    for tag, _ in S.DAYS:
        recs = arm_records(tag, fn)
        _r, t1 = PS.replay(recs)
        base = arm_records(tag, lambda r, _t: all(
            P.terms(r)[k] for k in P.TERMS))
        _r2, t2 = PS.replay(base)
        d = t1["realised_usd"] - t2["realised_usd"]
        tot += d
        print("%-8s %+10.2f %+10.2f %+10.2f"
              % (tag, t1["realised_usd"], t2["realised_usd"], d))
    print("%-8s %10s %10s %+10.2f" % ("TOTAL", "", "", tot))


def run(arms):
    print("%-52s %6s %6s %7s %10s %8s" % (
        "arm (days 1-7, one-position phase-close replay)", "takes", "win",
        "prec", "replay $", "capture"))
    out = {}
    for name, fn in arms:
        recs, tk, wn = [], 0, 0
        for tag, _ in S.DAYS:
            rr = arm_records(tag, fn)
            recs += rr
        for x in recs:
            if x["call"] == "TAKE":
                tk += 1
                wn += x["outcome"]["winner_close"]
        _rows, tot = PS.replay(recs)
        print("%-52s %6d %6d %7.3f %+10.2f %8.3f"
              % (name, tk, wn, (wn / tk) if tk else 0.0,
                 tot["realised_usd"], tot["capture"] or 0.0))
        out[name] = tot["realised_usd"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--oracle", action="store_true")
    ap.parse_args()
    TR = {tag: cell_truth(tag) for tag, _ in S.DAYS}

    def core(r, _t, t2=True):
        x = P.terms(r)
        ks = P.TERMS if t2 else tuple(k for k in P.TERMS if k != "T2")
        return all(x[k] for k in ks)

    def R(r, **kw):
        return S.r_state(r, **kw)

    arms = [
        ("CORE (T1..T5)", lambda r, t: core(r, t)),
        ("CORE - T2 (P025 floor dropped)", lambda r, t: core(r, t, False)),
        ("CORE + R1 rv1800(row)>=250",
         lambda r, t: core(r, t) and R(r, rv_t=250.0, cap_t=None)),
        ("CORE + R1 + R2 unspent_sess>=500",
         lambda r, t: core(r, t) and R(r, rv_t=250.0, cap_t=500.0)),
        ("CORE + R1 + R2b unspent_bind>=1000",
         lambda r, t: core(r, t) and R(r, rv_t=250.0, cap_t=None,
                                       bind_t=1000.0)),
        ("CORE + R1 + R2 + R2b",
         lambda r, t: core(r, t) and R(r, rv_t=250.0, cap_t=500.0,
                                       bind_t=1000.0)),
        ("CORE-T2 + R1 + R2b",
         lambda r, t: core(r, t, False) and R(r, rv_t=250.0, cap_t=None,
                                              bind_t=1000.0)),
        ("CORE + R1 + R2b + V2",
         lambda r, t: core(r, t) and R(r, rv_t=250.0, cap_t=None,
                                       bind_t=1000.0) and not P.v2(r)),
        ("CORE + R1 + R2b + V2 + V3 (V3 advisory today)",
         lambda r, t: core(r, t) and R(r, rv_t=250.0, cap_t=None,
                                       bind_t=1000.0) and not P.v2(r)
         and not P.v3(r)),
        ("CORE + R1 + R2b + V2 + ORACLE CELL SIDE",
         lambda r, t: core(r, t) and R(r, rv_t=250.0, cap_t=None,
                                       bind_t=1000.0) and not P.v2(r)
         and TR[t].get((r["asset"], r["phase_dec"])) == r["side"]),
        ("CORE + ORACLE CELL SIDE (no stage 1)",
         lambda r, t: core(r, t)
         and TR[t].get((r["asset"], r["phase_dec"])) == r["side"]),
        ("CORE + R1 + R2b + ORACLE SIDE (no V2)",
         lambda r, t: core(r, t) and R(r, rv_t=250.0, cap_t=None,
                                       bind_t=1000.0)
         and TR[t].get((r["asset"], r["phase_dec"])) == r["side"]),
        ("CORE + V2 only", lambda r, t: core(r, t) and not P.v2(r)),
        ("CORE + ANTI-ORACLE SIDE (always wrong) = the floor",
         lambda r, t: core(r, t)
         and TR[t].get((r["asset"], r["phase_dec"])) not in
         (None, r["side"])),
    ]
    # --- the hand side estimators, run as WHOLE POLICIES ------------------
    CE = {}
    for tag, _ in S.DAYS:
        rows = S.load(tag)
        for cut, asset, phase in S.cells_of(rows):
            r0 = [x for x in rows if x["_sec"] == cut and x["asset"] == asset
                  and x["phase_dec"] == phase][0]
            sl = S.F(r0, "slope15m")
            dp, iv = S.F(r0, "d_POC"), S.F(r0, "in_VA")
            CE[(tag, asset, phase)] = dict(
                x8=(None if sl in (None, 0)
                    else ("LONG" if sl > 0 else "SHORT")),
                x5=(None if (dp is None or iv is None or iv != 0
                             or abs(dp) < 250.0)
                    else ("LONG" if dp > 0 else "SHORT")),
                s2c=(None if (dp is None or iv is None or iv != 0
                              or abs(dp) < 250.0)
                     else ("SHORT" if dp > 0 else "LONG")))

    def hand(key):
        def f(r, t):
            c = CE.get((t, r["asset"], r["phase_dec"]), {})
            w = c.get(key)
            return core(r, t) and w is not None and w == r["side"]
        return f
    arms += [
        ("CORE + X8 slope15m@open CONTINUATION side", hand("x8")),
        ("CORE + X5 S10 away-from-value CONTINUATION side", hand("x5")),
        ("CORE + S2c S10 back-to-value (literal) side", hand("s2c")),
    ]
    run(arms)
    run_persession("CORE + X8 slope15m CONTINUATION side", hand("x8"))
    run_persession("CORE + R1 + R2b (rolling stage 1, no side)",
                   lambda r, t: all(P.terms(r)[k] for k in P.TERMS)
                   and S.r_state(r, rv_t=250.0, cap_t=None, bind_t=1000.0))


if __name__ == "__main__":
    sys.exit(main())
