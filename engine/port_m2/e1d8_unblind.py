#!/usr/bin/python3
"""E1 STUDY DAY 8 — the unblinding report (run ONLY after the seal commit)."""
import csv
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e1d8_policy as P                                        # noqa: E402
import e1d8_stage12 as S                                       # noqa: E402
import panel_score as PS                                       # noqa: E402

TRIAGE = "/workspace/artifacts/cache/port/m2/triage"
IDX = os.path.join(TRIAGE, "E1D8_TRIAGE_INDEX.tsv")
COMPAT = os.path.join(TRIAGE, "E1D8_TRIAGE_INDEX_COMPAT.tsv")


def rd(p):
    return list(csv.DictReader([l for l in open(p) if not l.startswith("#")],
                               delimiter="\t"))


def recs(rows, callmap):
    return [{"call": callmap.get(r["cid"], "SKIP"),
             "outcome": PS.outcome(r["cid"]), "cid": r["cid"]} for r in rows]


def show(nm, rows, callmap):
    rr = recs(rows, callmap)
    tk = [x for x in rr if x["call"] == "TAKE"]
    wn = sum(x["outcome"]["winner_close"] for x in tk)
    mt = (sum(x["outcome"]["cert_close_usd"] for x in tk) / len(tk)) if tk else 0
    sk = [x for x in rr if x["call"] == "SKIP"]
    ms = (sum(x["outcome"]["cert_close_usd"] for x in sk) / len(sk)) if sk else 0
    _r, tot = PS.replay(rr)
    print("%-46s %5d %7.3f %+9.1f %+8.1f %+11.2f %8.3f"
          % (nm, len(tk), (wn / len(tk)) if tk else 0, mt, ms,
             tot["realised_usd"], tot["capture"] or 0.0))
    return tot["realised_usd"]


def main():
    rows = rd(IDX)
    print("=" * 100)
    print("E1D8 UNBLIND — 2021-07-12, SI 327 / HG 304 / NKD 318 = 949")
    print("=" * 100)

    # --- the day's truth -------------------------------------------------
    win = defaultdict(lambda: [0, 0])
    per_asset = defaultdict(lambda: [0, 0, 0.0, 0])
    nwin = 0
    for r in rows:
        o = PS.outcome(r["cid"])
        a = per_asset[r["asset"]]
        a[0] += 1
        a[2] += o["cert_close_usd"]
        a[3] += o["walled"]
        if o["winner_close"]:
            nwin += 1
            a[1] += 1
            win[(r["asset"], r["phase_dec"])][0 if r["side"] == "LONG" else 1] += 1
    print("\nTHE DAY: %d D-021 winners in %d candidates (%.1f%%)"
          % (nwin, len(rows), 100.0 * nwin / len(rows)))
    for a in ("SI", "HG", "NKD"):
        v = per_asset[a]
        print("  %-4s n=%-4d winners=%-4d mean cert=%+8.2f walled=%.3f  "
              "DP ceiling=%.2f"
              % (a, v[0], v[1], v[2] / v[0], v[3] / v[0],
                 PS.dp_ceiling(a, 20210712)[0]))
    ceil = sum(PS.dp_ceiling(a, 20210712)[0] for a in ("SI", "HG", "NKD"))
    print("  DAY DP CEILING = $%.2f" % ceil)

    print("\nCELL TRUTH vs the committed SIDE calls "
          "(seat state at each cell's open in brackets)")
    print("%-14s %-8s %7s | %-6s %-8s | %s"
          % ("cell", "truth", "winners", "call", "correct?", "conf"))
    cells = sorted(set((r["asset"], r["phase_dec"]) for r in rows),
                   key=lambda k: min(int(float(r["sec"])) for r in rows
                                     if (r["asset"], r["phase_dec"]) == k))
    right = wrong = 0
    for k in cells:
        w = win.get(k)
        truth = ("LONG" if w[0] > w[1] else "SHORT") if w else "NONE"
        call = P.READER_CELL[k]
        ok = "-"
        if w:
            ok = "YES" if call == truth else "NO"
            right += (call == truth)
            wrong += (call != truth)
        print("%-14s %-8s %7s | %-6s %-8s | %s%s"
              % ("/".join(k), truth, sum(w) if w else 0, call, ok,
                 P.CELL_CONF[k],
                 "  [would-abstain]" if k in P.WOULD_ABSTAIN else ""))
    dec = right + wrong
    print("SIDE-CALL ACCURACY: %d of %d = %.3f (mirror %.3f)"
          % (right, dec, right / dec if dec else 0,
             wrong / dec if dec else 0))

    # --- arms -------------------------------------------------------------
    print("\nARMS (one-position phase-close replay, CC-M2-10.3)")
    print("%-46s %5s %7s %9s %8s %11s %8s"
          % ("arm", "takes", "winprec", "meanTAKE", "meanSKIP", "replay $",
             "capture"))
    truthmap = {}
    for k in cells:
        w = win.get(k)
        truthmap[k] = ("LONG" if w[0] > w[1] else "SHORT") if w else None
    out = {}
    for nm in ("CORE", "CORE+SEAT", "CORE+SIDE", "CORE+SEAT+SIDE", "MIRROR"):
        cm = {x["cid"]: x["call"] for x in P.call_day(rows, arm=nm)}
        out[nm] = show(nm + ("  <= READER" if nm == "CORE+SEAT" else ""),
                       rows, cm)
    cm = {x["cid"]: x["call"] for x in P.call_day(rows, arm="CORE+SEAT",
                                                  vetoes_on=False)}
    out["READER_NOVETO"] = show("READER without V2", rows, cm)
    base = {x["cid"]: x["call"] for x in P.call_day(rows, arm="CORE+SEAT")}
    out["ABSTAIN"] = show("READER + would-abstain cells removed", rows,
                          {c: ("SKIP" if (c.split("-")[0],
                                          [r for r in rows
                                           if r["cid"] == c][0]["phase_dec"])
                               in P.WOULD_ABSTAIN else v)
                           for c, v in base.items()})
    core = {r["cid"]: ("TAKE" if all(P.terms(r)[k] for k in P.TERMS)
                       else "SKIP") for r in rows}
    out["CORE+R1"] = show("CORE + R1 rv1800>=250 (pre-reg, NOT traded)", rows,
                          {r["cid"]: ("TAKE" if (core[r["cid"]] == "TAKE"
                                                 and S.r_state(r, rv_t=250.0,
                                                               cap_t=None))
                                      else "SKIP") for r in rows})
    out["CORE+INVR1"] = show("CORE + INVERTED R1 rv1800<250 (NOT traded)",
                             rows,
                             {r["cid"]: ("TAKE" if (core[r["cid"]] == "TAKE"
                                                    and (P.F(r, "rv1800") or 0)
                                                    < 250) else "SKIP")
                              for r in rows})
    out["V3"] = show("READER + V3 applied (advisory arm)", rows,
                     {r["cid"]: ("TAKE" if (base[r["cid"]] == "TAKE"
                                            and not P.v3(r)) else "SKIP")
                      for r in rows})
    out["ORACLE_SIDE"] = show("CORE + ORACLE cell side", rows,
                              {r["cid"]: ("TAKE" if (core[r["cid"]] == "TAKE"
                                                     and truthmap.get(
                                  (r["asset"], r["phase_dec"])) == r["side"])
                                  else "SKIP") for r in rows})
    out["ORACLE_BOTH"] = show("READER + ORACLE cell side", rows,
                              {r["cid"]: ("TAKE" if (base[r["cid"]] == "TAKE"
                                                     and truthmap.get(
                                  (r["asset"], r["phase_dec"])) == r["side"])
                                  else "SKIP") for r in rows})

    # --- baselines --------------------------------------------------------
    print("\nMECHANICAL BASELINES")
    print("%-46s %5s %7s %9s %8s %11s %8s"
          % ("arm", "takes", "winprec", "meanTAKE", "meanSKIP", "replay $",
             "capture"))
    bl = {}
    bdir = os.path.join(TRIAGE, "E1D8_BASE")
    for f in sorted(os.listdir(bdir)):
        cm = {r["cid"]: r["call"] for r in rd(os.path.join(bdir, f))}
        bl[f] = show("EARLIEST " + f.replace("BASE_EARLIEST_", "")
                     .replace(".tsv", ""), rows, cm)
    crows = rd(COMPAT)
    for d in range(1, 8):
        mod = "e1d%d_policy" % d
        try:
            m = __import__(mod)
            cm = {x["cid"]: x["call"] for x in m.call_day(crows)}
            bl[mod] = show("YESTERDAY %s (frozen)" % mod, rows, cm)
        except Exception as e:
            print("%-46s  (unrunnable: %s)" % ("YESTERDAY " + mod, e))
    bestb = max(bl.values()) if bl else 0.0
    bestn = [k for k, v in bl.items() if v == bestb]
    print("\nREADER margin over the BEST mechanical baseline (%s, %+.2f): "
          "%+.2f" % (bestn, bestb, out["CORE+SEAT"] - bestb))
    for k, v in bl.items():
        print("   vs %-28s %+10.2f" % (k, out["CORE+SEAT"] - v))

    # --- per-asset pairing ------------------------------------------------
    print("\nPER-ASSET (reader vs best baseline)")
    rr = recs(rows, base)
    prow, _ = PS.replay(rr)
    for x in prow:
        print("  %-4s reader replay %+9.2f  seats=%d  DP ceiling %.2f"
              % (x["asset"], x["realised_usd"], x["n_seated"],
                 x["dp_ceiling_usd"]))

    # --- grade calibration ------------------------------------------------
    print("\nGRADE CALIBRATION (CC-M2-4.4)")
    g = defaultdict(lambda: [0, 0.0, 0])
    for r in rows:
        o = PS.outcome(r["cid"])
        k = (base[r["cid"]], P.grade(r))
        g[k][0] += 1
        g[k][1] += o["cert_close_usd"]
        g[k][2] += o["winner_close"]
    for call in ("TAKE", "SKIP"):
        print("  %-5s %s" % (call, "  ".join(
            "%s: %+8.2f (n=%d, w=%d)" % (gr, g[(call, gr)][1] / g[(call, gr)][0],
                                         g[(call, gr)][0], g[(call, gr)][2])
            if g[(call, gr)][0] else "%s: -" % gr for gr in "ABC")))

    # --- V2 / V3 veto census ---------------------------------------------
    print("\nVETO FAMILIES")
    pre = {x["cid"]: x for x in P.call_day(rows, arm="CORE+SEAT",
                                           vetoes_on=False)}
    for nm, fn in (("V2 (applied)", P.v2), ("V3 (advisory, NOT applied)",
                                            P.v3)):
        pool = [r for r in rows if pre[r["cid"]]["call"] == "TAKE" and fn(r)]
        if not pool:
            print("  %-28s 0 rows on admitted candidates" % nm)
            continue
        m = sum(PS.outcome(r["cid"])["cert_close_usd"] for r in pool) / len(pool)
        w = sum(PS.outcome(r["cid"])["winner_close"] for r in pool)
        print("  %-28s %d rows on admitted candidates, mean %+8.2f, "
              "%d winners refused" % (nm, len(pool), m, w))

    # --- the three seats --------------------------------------------------
    print("\nTHE THREE SEATS")
    seat_cids = PS.replay_seat_cids(rr)
    for r in sorted(rows, key=lambda r: int(float(r["sec"]))):
        if r["cid"] not in seat_cids:
            continue
        o = PS.outcome(r["cid"])
        print("  %-28s %s %-5s close %+9.2f peak %+9.2f mae %8.2f walled=%d"
              % (r["cid"], r["clock"], r["side"], o["cert_close_usd"],
                 o["cert_peak_usd"], o["mae_before_argmax"], o["walled"]))

    # --- winner anatomy ---------------------------------------------------
    print("\nWINNER ANATOMY (what the day's winners looked like)")
    wr = [r for r in rows if PS.outcome(r["cid"])["winner_close"]]
    if wr:
        t = defaultdict(int)
        for r in wr:
            for k in P.TERMS:
                t[k] += P.terms(r)[k]
            t["R1"] += (P.F(r, "rv1800") or 0) >= 250
            ub = P.F(r, "unspent_bind")
            t["R2b"] += (ub is None or ub >= 1000)
            t["side_" + r["side"]] += 1
        print("  n=%d  " % len(wr) + "  ".join(
            "%s %d/%d" % (k, t[k], len(wr))
            for k in ("T1", "T2", "T3", "T4", "T5", "R1", "R2b")))
        print("  sides: LONG %d / SHORT %d" % (t["side_LONG"], t["side_SHORT"]))
        rv = sorted(P.F(r, "rv1800") or 0 for r in wr)
        rw = sorted(P.F(r, "runway_phase") or 0 for r in wr)
        print("  winner rv1800 min/med/max %.1f / %.1f / %.1f ; "
              "runway_phase min %.0f" % (rv[0], rv[len(rv) // 2], rv[-1], rw[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
