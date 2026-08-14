#!/usr/bin/python3
"""E1 STUDY DAY 8 — THE CELL-OPEN PANEL, in the CC-M2-19 corrected forms.

Successor to `e1d6/e1d7_cellbrief.py`.  It prints, for one (asset, phase) cell
and strictly from rows with `sec < cell_open_sec` PLUS the cell's own
first-second row (the row being called), exactly the panel the day-8
pre-registration declared:

  STAGE 2 (SIDE — committed FIRST, CC-M2-19.2's measured composition order)
    X8  `slope15m` at the cell open, CONTINUATION reading
    X7  `fph_sflow` at the cell open, CONTINUATION reading
    X2  the asset's session net so far, CONTINUATION reading
    2-of-3 CONSENSUS of the above (pre-registered: 10 right / 7 wrong = 0.588
        on the 22 winner-bearing cells of seven sessions, mirror 0.412,
        one session lost)
    S2c S10 `d_POC`/`in_VA` LITERAL back-to-value reading (pre-registered
        ANTI-predictive: 2 right / 6 wrong at $250 over seven sessions)
    X5  the same field's CONTINUATION reading (6 right / 2 wrong at $250, n=8)
    DEAD REFERENCES, scored not traded: P031 cross-asset fuel, P009 own-asset
        fuel, P029 phase prior.

  STAGE 1 (ROLLING SEAT STATE — read at every row, logged, not fixed at open)
    R1  `rv1800` >= 250   — PRE-REGISTERED AND NOT TRADED: as a gate it costs
        -$7,562.50 over seven sessions and its seat-spender split is 41 seats
        with the state CLOSED at +$201.86 against 23 OPEN at -$111.52.
    R2b `unspent_bind` >= $1,000 — TRADED: the ERA_NOTES §77 binding-row field,
        pooled 7-session win rate 8.74% (1.46x) and +$2,471.25 of replay over
        CORE at capture 0.096 -> 0.199.

  OVERNIGHT CONTEXT for a session's first cell (no intra-session tape exists):
    the prior STUDY session's per-asset net, close position in its own range,
    and the gap into this session's first mid.
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TRIAGE = "/workspace/artifacts/cache/port/m2/triage"
IDX = os.path.join(TRIAGE, "E1D8_TRIAGE_INDEX.tsv")
PRIOR = os.path.join(TRIAGE, "E1D7_TRIAGE_INDEX.tsv")
PHASES = ("TOKYO", "LONDON", "NY")


def F(r, k):
    try:
        return float(r[k])
    except Exception:
        return None


def load(path):
    rows = list(csv.DictReader(
        [l for l in open(path) if not l.startswith("#")], delimiter="\t"))
    for r in rows:
        r["_sec"] = int(float(r["sec"]))
        r["_mid"] = F(r, "mid")
    rows.sort(key=lambda r: (r["_sec"], r["cid"]))
    return rows


def cells_of(rows):
    seen = {}
    for r in rows:
        k = (r["asset"], r["phase_dec"])
        if k not in seen:
            seen[k] = r["_sec"]
    return sorted((v, k[0], k[1]) for k, v in seen.items())


def L(v):
    return None if v in (None, 0) else ("LONG" if v > 0 else "SHORT")


def blocks(rows, asset, cut):
    rs = [r for r in rows if r["asset"] == asset and r["_sec"] < cut
          and r["_mid"] is not None]
    out = []
    for p in PHASES:
        q = [r for r in rs if r["phase_dec"] == p]
        if not q:
            continue
        m = [r["_mid"] for r in q]
        mult = F(q[-1], "mult") or 1.0
        ta, tb, pt = (F(q[-1], "trapped_above"), F(q[-1], "trapped_below"),
                      F(q[-1], "phase_total"))
        out.append(dict(phase=p, n=len(q), last=q[-1]["_sec"],
                        net=(m[-1] - m[0]) * mult,
                        rng=(max(m) - min(m)) * mult,
                        pos=((m[-1] - min(m)) / (max(m) - min(m))
                             if max(m) > min(m) else None),
                        fa=(ta / pt if pt else None),
                        fb=(tb / pt if pt else None), pt=pt,
                        sflow=F(q[-1], "fph_sflow")))
    out.sort(key=lambda b: b["last"])
    return out


def sess(rows, asset, cut):
    rs = [r for r in rows if r["asset"] == asset and r["_sec"] < cut
          and r["_mid"] is not None]
    if not rs:
        return None
    m = [r["_mid"] for r in rs]
    mult = F(rs[-1], "mult") or 1.0
    rng = max(m) - min(m)
    return dict(n=len(rs), net=(m[-1] - m[0]) * mult, last=m[-1],
                rng=rng * mult,
                pos=((m[-1] - min(m)) / rng) if rng > 0 else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default=IDX)
    ap.add_argument("--prior", default=PRIOR)
    ap.add_argument("--cell", type=int)
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    rows = load(a.index)
    cells = cells_of(rows)
    if a.list or a.cell is None:
        for i, (c, asset, ph) in enumerate(cells):
            n = sum(1 for r in rows if r["asset"] == asset
                    and r["phase_dec"] == ph)
            print("%2d %-4s %-6s open sec=%6d  %s  n=%d"
                  % (i, asset, ph, c, [r for r in rows if r["_sec"] == c
                                       and r["asset"] == asset
                                       and r["phase_dec"] == ph][0]["clock"],
                     n))
        return 0
    cut, asset, phase = cells[a.cell]
    at = [r for r in rows if r["_sec"] == cut and r["asset"] == asset
          and r["phase_dec"] == phase]
    assert at, "no at-open row"
    r0 = at[0]
    # --- the as-of assertion: nothing at or after the cut may inform the call
    for r in rows:
        if r["_sec"] > cut:
            continue
        if r["_sec"] == cut and (r["asset"], r["phase_dec"]) != (asset, phase):
            raise SystemExit("as-of violation: foreign row at the cut")
    print("=" * 78)
    print("E1D8 CELL PANEL #%d/%d  %s/%s  opens sec=%d (%s)  n_cand=%d"
          % (a.cell, len(cells) - 1, asset, phase, cut, r0["clock"],
             sum(1 for r in rows if r["asset"] == asset
                 and r["phase_dec"] == phase)))
    print("CUT: strictly rows with sec < %d, plus this cell's own first-second "
          "row %s" % (cut, r0["cid"]))
    print("=" * 78)

    s = sess(rows, asset, cut)
    bl = blocks(rows, asset, cut)
    x8, x7 = L(F(r0, "slope15m")), L(F(r0, "fph_sflow"))
    x2 = L(s["net"]) if s else None
    votes = [v for v in (x8, x7, x2) if v]
    cons = None
    if votes:
        nl, ns = votes.count("LONG"), votes.count("SHORT")
        cons = "LONG" if nl >= 2 else ("SHORT" if ns >= 2 else None)
    dp, iv = F(r0, "d_POC"), F(r0, "in_VA")
    s2c = x5 = None
    if dp is not None and iv is not None and iv == 0 and abs(dp) >= 250.0:
        s2c = "SHORT" if dp > 0 else "LONG"
        x5 = "LONG" if dp > 0 else "SHORT"

    print("\nSTAGE 2 — SIDE PANEL (committed first)")
    print("  X8 slope15m=%-8s -> %s   [12/5 = 0.706 at cell grain, 1 session "
          "lost; +$3,495 replay of which +$3,579 is ONE session]"
          % (r0.get("slope15m"), x8))
    print("  X7 fph_sflow=%-8s -> %s   [12/9 = 0.571, 2 sessions lost]"
          % (r0.get("fph_sflow"), x7))
    print("  X2 session net=%-9s -> %s   [10/8 = 0.556, 2 sessions lost]"
          % ("$%.0f" % s["net"] if s else ".", x2))
    print("  >>> 2-of-3 CONTINUATION CONSENSUS = %s   [10/7 = 0.588, mirror "
          "0.412, 1 session lost; replay-neutral vs CORE]" % cons)
    print("  S2c S10 d_POC=%s in_VA=%s -> LITERAL back-to-value %s "
          "[ANTI-predictive 2/6]; CONTINUATION form %s [6/2, n=8]"
          % (r0.get("d_POC"), r0.get("in_VA"), s2c, x5))
    print("  dev POC/VAH/VAL = %s / %s / %s"
          % (r0.get("dev_poc"), r0.get("dev_vah"), r0.get("dev_val")))
    print("  session so far: net=%s pos=%s range=%s (n=%s rows)"
          % (("$%.0f" % s["net"]) if s else ".",
             ("%.2f" % s["pos"]) if s and s["pos"] is not None else ".",
             ("$%.0f" % s["rng"]) if s else ".", s["n"] if s else 0))
    for b in bl:
        print("   own %-6s n=%-4d net=%+8.0f range=%8.0f pos=%s fuel %s/%s "
              "of %s sflow=%s"
              % (b["phase"], b["n"], b["net"], b["rng"],
                 ("%.2f" % b["pos"]) if b["pos"] is not None else ".",
                 ("%.2f" % b["fa"]) if b["fa"] is not None else ".",
                 ("%.2f" % b["fb"]) if b["fb"] is not None else ".",
                 b["pt"], b["sflow"]))
    for oa in ("SI", "HG", "NKD"):
        if oa == asset:
            continue
        os_ = sess(rows, oa, cut)
        ob = blocks(rows, oa, cut)
        print("   X-ASSET %-4s %s" % (oa, ("net=$%.0f pos=%s | " % (
            os_["net"], ("%.2f" % os_["pos"]) if os_["pos"] is not None
            else ".")) if os_ else "(no prior rows) "), end="")
        if ob:
            b = ob[-1]
            print("last %s n=%d net=%+.0f fuel %s/%s of %s [P031 DEAD FINAL]"
                  % (b["phase"], b["n"], b["net"],
                     ("%.2f" % b["fa"]) if b["fa"] is not None else ".",
                     ("%.2f" % b["fb"]) if b["fb"] is not None else ".",
                     b["pt"]))
        else:
            print("")
    print("  P029 phase prior (DEAD as a rule): %s -> %s"
          % (phase, "LONG" if phase in ("TOKYO", "LONDON") else "SHORT"))

    if not bl:
        print("\n  OVERNIGHT CONTEXT (this is the session's first cell for %s "
              "— no intra-session tape exists)" % asset)
        pr = load(a.prior)
        for oa in ("SI", "HG", "NKD"):
            ps = sess(pr, oa, 10 ** 9)
            if not ps:
                continue
            gap = None
            mine = [r for r in rows if r["asset"] == oa]
            if mine:
                mult = F(mine[0], "mult") or 1.0
                gap = (mine[0]["_mid"] - ps["last"]) * mult
            print("    %-4s prior-session net=%+9.0f pos=%.2f range=%8.0f | "
                  "gap into this session = %s"
                  % (oa, ps["net"], ps["pos"] or 0.0, ps["rng"],
                     ("%+.0f" % gap) if gap is not None else "."))

    print("\nSTAGE 1 — ROLLING SEAT STATE at this cell's own first row "
          "(logged at EVERY row, not fixed here)")
    print("  R1 rv1800=%s (rv900 %s / rv300 %s / rv60 %s) -> %s   "
          "[PRE-REGISTERED AND NOT TRADED: -$7,562 as a gate]"
          % (r0.get("rv1800"), r0.get("rv900"), r0.get("rv300"),
             r0.get("rv60"),
             "OPEN" if (F(r0, "rv1800") or 0) >= 250 else "CLOSED"))
    ub = F(r0, "unspent_bind")
    print("  R2b unspent_bind=%s (exit_is_sess=%s cov_phase=%s cov_sess=%s "
          "unspent_sess=%s) -> %s   [TRADED]"
          % (r0.get("unspent_bind"), r0.get("exit_is_sess"),
             r0.get("cov_phase"), r0.get("cov_sess"), r0.get("unspent_sess"),
             "OPEN" if (ub is None or ub >= 1000.0) else "CLOSED"))
    print("  P025 runway_phase=%s runway_sess=%s | S2 day_type=%s "
          "range_vs_hat=%s%% | S9 vol_regime=%s rv5/rv66=%s surprise=%s "
          "ladder=%s q50=%s"
          % (r0.get("runway_phase"), r0.get("runway_sess"),
             r0.get("day_type_so_far"), r0.get("range_vs_hat_pct"),
             r0.get("vol_regime"), r0.get("rv5_rv66"), r0.get("surprise"),
             r0.get("ladder_pos"), r0.get("q50")))
    print("  S8 book at open: 60s %s/%s sflow %s | 5m %s/%s sflow %s | "
          "30m %s/%s sflow %s | S13 spread=%s cost_rt=%s"
          % (r0.get("f60_n"), r0.get("f60_vol"), r0.get("f60_sflow"),
             r0.get("f5m_n"), r0.get("f5m_vol"), r0.get("f5m_sflow"),
             r0.get("f30m_n"), r0.get("f30m_vol"), r0.get("f30m_sflow"),
             r0.get("spread_dec"), r0.get("cost_rt")))
    print("  S12 sched_last_age=%s sched_next_in=%s (release inside session?) "
          "| short_day=%s observed_close=%s | fvol_source=%s"
          % (r0.get("sched_last_age"), r0.get("sched_next_in"),
             r0.get("short_day"), r0.get("observed_close"),
             r0.get("fvol_source")))
    print("  FORECASTER: predicted_day_type_prob=%s range_hat_vs_trailing=%s "
          "menu_hat=%s  (CC-M2-17.2: VOID in E1)"
          % (r0.get("predicted_day_type_prob"),
             r0.get("range_hat_vs_trailing"), r0.get("menu_hat")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
