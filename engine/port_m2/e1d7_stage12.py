#!/usr/bin/python3
"""E1 STUDY DAY 7 — THE THREE-STAGE PRE-REGISTRATION (CC-M2-17.1 stages 1+2).

CC-M2-17.1 decomposes the decision into SEAT EXISTENCE -> CELL SIDE -> MOMENT.
Day 6 answered stage 2 by hand at 0.600 accuracy and still lost the replay,
because it had no stage-1 object and spent a seat in all nine cells while four
held no D-021 winner on either side (ERA_NOTES §62-§64).  This module is the
PRE-REGISTRATION of both stages: every estimator the reader intends to use on
day 7 is scored HERE, on the 54 (asset, phase) cells of the six unblinded
study sessions, BEFORE any day-7 cell is called, and quoted in the committed
ledger whatever it says (the discipline days 5 and 6 used for P027/P029).

=======================================================================
STAGE 1 — SEAT EXISTENCE ESTIMATORS (no mirror: a feasibility object)
=======================================================================
 S1a  P030 CELL_VOL_CONCENTRATION: `rv1800` on the cell's FIRST candidate row
      >= T.  Born day 6, monotone in four bands over 54 cells / 361 winners,
      THRESHOLD EXPLICITLY UNSETTLED (a floor at 150 refuses HG/LONDON, day
      6's best seat).  Swept here on the POOLED CELL POOL — never on the
      replay (ERA_NOTES §33/§41 method law).
 S1b  PRIOR-CELL TRAVEL: did this asset's previous phase actually traverse a
      $1,000 certificate ($ range of its candidate mids >= 1000)?  A cell whose
      predecessor could not pay the bar is a cell in a tape that is not moving.
 S1c  SESSION CAPACITY: S3 `unspent_sess` >= $500 at the cell open (the A1
      arithmetic at cell grain; P002/P003's family, which is a REFUSAL family
      and therefore lawful here).
 S1d  P025 RUNWAY: `runway_phase` at the cell open >= 12,000s — 361/361
      winners clear it and no row below it has ever won in six sessions.
 Combinations are scored as conjunctions.  The reported statistics are
 PRECISION (of the cells called YES, the fraction holding >= 1 D-021 winner),
 RECALL (of winner-bearing cells) and WINNER RECALL (of the 361 winners).

=======================================================================
STAGE 2 — CELL-SIDE ESTIMATORS (mirror-law tested, CC-M2-13.1)
=======================================================================
 S2a  P031 CROSS_ASSET_FUEL_OVERHANG (day-6's winning evidence, n=2 right /
      1 wrong): the STRONGEST completed-phase fuel overhang among the OTHER
      two assets at this cell's open.  trapped_above/phase_total >= X on
      another asset -> SHORT this cell (that asset's trapped longs are supply
      to the complex); trapped_below >= X -> LONG.
 S2b  P009 OWN-ASSET FUEL POLARITY (DEAD twice — warm-up and day 6 at maximum
      cost).  Scored here only so the P031-vs-P009 sign inversion is measured
      on six sessions instead of one hour.
 S2c  S10 PROFILE SIDE: `d_POC` with `in_VA` at the cell open.  When price is
      OUTSIDE the developing value area (in_VA=0) by >= T dollars, the side is
      BACK TOWARD VALUE (d_POC > 0 -> SHORT, d_POC < 0 -> LONG).  This is the
      SIDE reading of the field whose MAGNITUDE reading (P028) is dead; day 6
      is its only support (SI/NY d_POC +$1,362 -> 29 SHORT winners).
 S2d  P029 PHASE_SIDE_PRIOR, carried for reference (dead as a rule, CC-M2-17.6).
 Every estimator is reported WITH ITS MIRROR on the winner-bearing cells.

USAGE
  --backtest            score both stages on days 1-6 (the pre-registration)
  --cell K              emit day-7 cell K's estimator values (chronological;
                        rows with sec < open for history, the cell's own
                        first-second row for the at-open fields)
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TRIAGE = "/workspace/artifacts/cache/port/m2/triage"
DAYS = [("E1D1", "20210701"), ("E1D2", "20210702"), ("E1D3", "20210705"),
        ("E1D4", "20210706"), ("E1D5", "20210707"), ("E1D6", "20210708")]
PHASES = ("TOKYO", "LONDON", "NY")


ALIAS = {"day_type_so_far": ("day_type_so_far", "day_type"),
         "range_vs_hat_pct": ("range_vs_hat_pct", "pct_range_hat")}


def G(r, k, default=None):
    for kk in ALIAS.get(k, (k,)):
        if kk in r:
            return r[kk]
    return default


def F(r, k):
    try:
        return float(G(r, k))
    except Exception:
        return None


_IDX, _S10 = {}, {}


def load(tag):
    if tag in _IDX:
        return _IDX[tag]
    p = os.path.join(TRIAGE, "%s_TRIAGE_INDEX.tsv" % tag)
    rows = list(csv.DictReader(
        [l for l in open(p) if not l.startswith("#")], delimiter="\t"))
    s10 = {}
    sp = os.path.join(TRIAGE, "%s_S10.tsv" % tag)
    if os.path.exists(sp):
        for r in csv.DictReader(
                [l for l in open(sp) if not l.startswith("#")],
                delimiter="\t"):
            s10[r["cid"]] = r
    for r in rows:
        r["_sec"] = int(float(r["sec"]))
        r["_mid"] = F(r, "mid")
        if "d_POC" not in r or r.get("d_POC") in (None, "", "."):
            s = s10.get(r["cid"])
            r["d_POC"] = s["d_POC_usd"] if s else "."
            r["in_VA"] = s["in_VA"] if s else "."
    rows.sort(key=lambda r: (r["_sec"], r["cid"]))
    _IDX[tag] = rows
    return rows


def cells_of(rows):
    seen = {}
    for r in rows:
        k = (r["asset"], r["phase_dec"])
        if k not in seen:
            seen[k] = r["_sec"]
    return sorted((v, k[0], k[1]) for k, v in seen.items())


def phase_blocks(rows, asset, cut):
    """Completed/partial phase blocks of `asset` strictly before `cut`."""
    rs = [r for r in rows if r["asset"] == asset and r["_sec"] < cut
          and r["_mid"] is not None]
    out = []
    for p in PHASES:
        q = [r for r in rs if r["phase_dec"] == p]
        if not q:
            continue
        mids = [r["_mid"] for r in q]
        mult = F(q[-1], "mult") or 1.0
        L = q[-1]
        ta, tb, pt = (F(L, "trapped_above"), F(L, "trapped_below"),
                      F(L, "phase_total"))
        out.append(dict(
            phase=p, n=len(q), last_sec=q[-1]["_sec"], mult=mult,
            net=(mids[-1] - mids[0]) * mult,
            rng=(max(mids) - min(mids)) * mult,
            pos=((mids[-1] - min(mids)) / (max(mids) - min(mids))
                 if max(mids) > min(mids) else None),
            fa=(ta / pt if pt else None), fb=(tb / pt if pt else None),
            pt=pt, sflow=F(L, "fph_sflow"), vol=F(L, "fph_vol")))
    out.sort(key=lambda b: b["last_sec"])
    return out


def cell_features(rows, asset, phase, cut):
    """Everything both stages read, strictly causal at the cell open."""
    first = [r for r in rows if r["_sec"] == cut and r["asset"] == asset
             and r["phase_dec"] == phase]
    assert first, "no at-open row for %s/%s @ %d" % (asset, phase, cut)
    r0 = first[0]
    mine = phase_blocks(rows, asset, cut)
    f = dict(asset=asset, phase=phase, open_sec=cut, cid0=r0["cid"],
             rv1800=F(r0, "rv1800"), rv60=F(r0, "rv60"),
             runway_phase=F(r0, "runway_phase"),
             unspent_sess=F(r0, "unspent_sess"), cov_sess=F(r0, "cov_sess"),
             day_type=G(r0, "day_type_so_far", "."),
             range_vs_hat=F(r0, "range_vs_hat_pct"),
             d_POC=F(r0, "d_POC"), in_VA=F(r0, "in_VA"),
             f60_n=F(r0, "f60_n"), f60_vol=F(r0, "f60_vol"),
             sched_next_in=F(r0, "sched_next_in"),
             sched_last_age=F(r0, "sched_last_age"),
             runway_sess=F(r0, "runway_sess"),
             prior_rng=None, prior_net=None, prior_pos=None,
             own_fa=None, own_fb=None, own_pt=None,
             x_fa=None, x_fb=None, x_src=None, x_pt=None)
    if mine:
        b = mine[-1]
        f.update(prior_rng=b["rng"], prior_net=b["net"], prior_pos=b["pos"],
                 own_fa=b["fa"], own_fb=b["fb"], own_pt=b["pt"])
    best = None
    for a in ("SI", "HG", "NKD"):
        if a == asset:
            continue
        bl = phase_blocks(rows, a, cut)
        if not bl:
            continue
        b = bl[-1]
        if b["fa"] is None or not b["pt"]:
            continue
        strength = max(b["fa"], b["fb"])
        if best is None or strength > best[0]:
            best = (strength, a, b)
    if best:
        _, a, b = best
        f.update(x_fa=b["fa"], x_fb=b["fb"], x_pt=b["pt"],
                 x_src="%s/%s" % (a, b["phase"]))
    return f


# ------------------------------------------------------------ estimators ----
def seat_calls(f, rv_t=150.0, cap_t=500.0):
    o = {}
    o["S1a_rv%d" % int(rv_t)] = (f["rv1800"] is not None
                                 and f["rv1800"] >= rv_t)
    o["S1b_prior1000"] = (f["prior_rng"] is None or f["prior_rng"] >= 1000.0)
    o["S1c_cap"] = (f["unspent_sess"] is None
                    or f["unspent_sess"] >= cap_t)
    o["S1d_runway"] = (f["runway_phase"] is not None
                       and f["runway_phase"] >= 12000.0)
    return o


def side_calls(f, x_t=0.65, own_t=0.65, poc_t=500.0):
    o = {}
    if f["x_fa"] is not None:
        o["S2a_xfuel"] = ("SHORT" if f["x_fa"] >= x_t else
                          ("LONG" if f["x_fb"] >= x_t else None))
    else:
        o["S2a_xfuel"] = None
    if f["own_fa"] is not None:
        o["S2b_ownfuel"] = ("SHORT" if f["own_fa"] >= own_t else
                            ("LONG" if f["own_fb"] >= own_t else None))
    else:
        o["S2b_ownfuel"] = None
    if (f["d_POC"] is not None and f["in_VA"] is not None
            and f["in_VA"] == 0 and abs(f["d_POC"]) >= poc_t):
        o["S2c_poc"] = "SHORT" if f["d_POC"] > 0 else "LONG"
    else:
        o["S2c_poc"] = None
    o["S2d_p029"] = "LONG" if f["phase"] in ("TOKYO", "LONDON") else "SHORT"
    return o


# ----------------------------------------------------------------- truth ----
def cell_truth(tag):
    import panel_score as PS
    out = {}
    for r in load(tag):
        o = PS.outcome(r["cid"])
        if not o["winner_close"]:
            continue
        a = out.setdefault((r["asset"], r["phase_dec"]), [0, 0])
        a[0 if r["side"] == "LONG" else 1] += 1
    return {k: ("LONG" if v[0] > v[1] else "SHORT", v[0] + v[1])
            for k, v in out.items()}


def build(tag):
    rows = load(tag)
    truth = cell_truth(tag)
    out = []
    for cut, asset, phase in cells_of(rows):
        f = cell_features(rows, asset, phase, cut)
        t = truth.get((asset, phase))
        f["day"] = tag
        f["truth"] = t[0] if t else "NONE"
        f["n_win"] = t[1] if t else 0
        out.append(f)
    return out


def backtest(out_path=None):
    allc = []
    for tag, _ in DAYS:
        allc += build(tag)
    live = [c for c in allc if c["n_win"] > 0]
    W = sum(c["n_win"] for c in allc)
    print("PRE-REGISTRATION over %d (asset, phase) cells of %d unblinded "
          "sessions; %d winner-bearing cells, %d D-021 winners"
          % (len(allc), len(DAYS), len(live), W))

    print("\n== STAGE 1: SEAT EXISTENCE ==")
    print("%-28s %5s %6s %6s %8s %8s" % ("estimator", "YES", "hit", "miss",
                                         "prec", "win_recall"))
    variants = []
    for t in (100.0, 150.0, 200.0, 250.0):
        variants.append(("S1a rv1800>=%d" % t,
                         lambda c, t=t: seat_calls(c, t)["S1a_rv%d" % int(t)]))
    variants.append(("S1b prior-cell range>=1000",
                     lambda c: seat_calls(c)["S1b_prior1000"]))
    variants.append(("S1c unspent_sess>=500",
                     lambda c: seat_calls(c)["S1c_cap"]))
    variants.append(("S1d runway_phase>=12000",
                     lambda c: seat_calls(c)["S1d_runway"]))
    variants.append(("rv>=150 AND prior>=1000",
                     lambda c: (seat_calls(c, 150.0)["S1a_rv150"]
                                and seat_calls(c)["S1b_prior1000"])))
    variants.append(("rv>=150 AND runway",
                     lambda c: (seat_calls(c, 150.0)["S1a_rv150"]
                                and seat_calls(c)["S1d_runway"])))
    variants.append(("rv>=100 AND prior>=1000 AND runway",
                     lambda c: (seat_calls(c, 100.0)["S1a_rv100"]
                                and seat_calls(c)["S1b_prior1000"]
                                and seat_calls(c)["S1d_runway"])))
    variants.append(("rv>=150 AND prior>=1000 AND runway",
                     lambda c: (seat_calls(c, 150.0)["S1a_rv150"]
                                and seat_calls(c)["S1b_prior1000"]
                                and seat_calls(c)["S1d_runway"])))
    variants.append(("ALL CELLS (day-6 behaviour)", lambda c: True))
    for name, fn in variants:
        yes = [c for c in allc if fn(c)]
        hit = [c for c in yes if c["n_win"] > 0]
        wr = sum(c["n_win"] for c in hit)
        print("%-28s %5d %6d %6d %8s %8s"
              % (name, len(yes), len(hit), len(yes) - len(hit),
                 "%.3f" % (len(hit) / len(yes)) if yes else "NA",
                 "%.3f" % (wr / W) if W else "NA"))

    print("\n== STAGE 2: CELL SIDE (winner-bearing cells only) ==")
    print("%-28s %5s %6s %7s %8s %8s" % ("estimator", "right", "wrong",
                                         "silent", "acc", "mirror"))
    for key, label, kw in (
            ("S2a_xfuel", "S2a cross-asset fuel .65", dict(x_t=0.65)),
            ("S2a_xfuel", "S2a cross-asset fuel .75", dict(x_t=0.75)),
            ("S2a_xfuel", "S2a cross-asset fuel .85", dict(x_t=0.85)),
            ("S2b_ownfuel", "S2b OWN fuel .65 (P009)", dict(own_t=0.65)),
            ("S2b_ownfuel", "S2b OWN fuel .85 (P009)", dict(own_t=0.85)),
            ("S2c_poc", "S2c S10 outside-VA >=0", dict(poc_t=0.0)),
            ("S2c_poc", "S2c S10 outside-VA >=500", dict(poc_t=500.0)),
            ("S2c_poc", "S2c S10 outside-VA >=1000", dict(poc_t=1000.0)),
            ("S2d_p029", "S2d P029 phase prior", dict())):
        r = w = s = 0
        for c in live:
            call = side_calls(c, **kw)[key]
            if call is None:
                s += 1
            elif call == c["truth"]:
                r += 1
            else:
                w += 1
        print("%-28s %5d %6d %7d %8s %8s"
              % (label, r, w, s, "%.3f" % (r / (r + w)) if r + w else "NA",
                 "%.3f" % (w / (r + w)) if r + w else "NA"))

    print("\n== MIRROR LAW BY SESSION (CC-M2-13.1: must beat its mirror on "
          "EVERY session) ==")
    for key, label, kw in (
            ("S2a_xfuel", "S2a cross-asset fuel .65", dict(x_t=0.65)),
            ("S2a_xfuel", "S2a cross-asset fuel .75", dict(x_t=0.75)),
            ("S2a_xfuel", "S2a cross-asset fuel .85", dict(x_t=0.85)),
            ("S2b_ownfuel", "S2b OWN fuel .65 (P009)", dict(own_t=0.65)),
            ("S2c_poc", "S2c S10 outside-VA >=500", dict(poc_t=500.0)),
            ("S2d_p029", "S2d P029 phase prior", dict())):
        per, fails = [], 0
        for tag, _ in DAYS:
            sub = [c for c in live if c["day"] == tag]
            r = sum(1 for c in sub if side_calls(c, **kw)[key] == c["truth"])
            w = sum(1 for c in sub
                    if side_calls(c, **kw)[key] not in (None, c["truth"]))
            per.append("%s %d/%d" % (tag[-2:], r, w))
            if r + w and w > r:
                fails += 1
            elif r + w == 0:
                pass
        print("  %-26s %s   sessions LOST: %d %s"
              % (label, "  ".join(per), fails,
                 "=> FAILS the mirror law" if fails else "=> PASSES"))

    print("\nPER-CELL TABLE (all %d cells):" % len(allc))
    print("%-5s %-4s %-6s %-5s %4s %7s %8s %8s %7s %6s %6s %6s"
          % ("day", "ast", "phase", "truth", "nwin", "rv1800", "prior_rng",
             "unspent", "runway", "d_POC", "in_VA", "xfuel"))
    for c in allc:
        print("%-5s %-4s %-6s %-5s %4d %7s %8s %8s %7s %6s %6s %6s"
              % (c["day"], c["asset"], c["phase"], c["truth"], c["n_win"],
                 "%.1f" % c["rv1800"] if c["rv1800"] is not None else ".",
                 "%.0f" % c["prior_rng"] if c["prior_rng"] is not None else ".",
                 "%.0f" % c["unspent_sess"]
                 if c["unspent_sess"] is not None else ".",
                 "%.0f" % c["runway_phase"]
                 if c["runway_phase"] is not None else ".",
                 "%.0f" % c["d_POC"] if c["d_POC"] is not None else ".",
                 "%.0f" % c["in_VA"] if c["in_VA"] is not None else ".",
                 ("%.2f/%.2f" % (c["x_fa"], c["x_fb"]))
                 if c["x_fa"] is not None else "."))
    if out_path:
        cols = ["day", "asset", "phase", "open_sec", "truth", "n_win",
                "rv1800", "rv60", "runway_phase", "unspent_sess", "cov_sess",
                "day_type", "range_vs_hat", "d_POC", "in_VA", "prior_rng",
                "prior_net", "prior_pos", "own_fa", "own_fb", "x_fa", "x_fb",
                "x_src", "f60_n", "f60_vol", "cid0"]
        with open(out_path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, delimiter="\t",
                               extrasaction="ignore")
            w.writeheader()
            for c in allc:
                w.writerow(c)
        print("\nwrote %s" % out_path)
    return 0


def day7_cell(k, index=None):
    """Day-7 cell K's stage-1/stage-2 estimator values.  ONE CELL AT A TIME:
    every field is computed from rows strictly before the cell open plus the
    cell's own first-second row."""
    p = index or os.path.join(TRIAGE, "E1D7_TRIAGE_INDEX.tsv")
    rows = list(csv.DictReader(
        [l for l in open(p) if not l.startswith("#")], delimiter="\t"))
    for r in rows:
        r["_sec"] = int(float(r["sec"]))
        r["_mid"] = F(r, "mid")
    rows.sort(key=lambda r: (r["_sec"], r["cid"]))
    cl = cells_of(rows)
    cut, asset, phase = cl[k]
    f = cell_features(rows, asset, phase, cut)
    print("CELL #%d  %s/%s  open=%d  (all fields causal at the open)"
          % (k, asset, phase, cut))
    print("  STAGE 1: rv1800=%s [P030 band]  prior_cell_range=%s  "
          "unspent_sess=%s  runway_phase=%s  day_type=%s  cov_sess=%s"
          % (f["rv1800"], f["prior_rng"], f["unspent_sess"],
             f["runway_phase"], f["day_type"], f["cov_sess"]))
    for t in (100.0, 150.0, 250.0):
        print("     S1a rv>=%d: %s" % (t, seat_calls(f, t)["S1a_rv%d" % int(t)]))
    sc = seat_calls(f)
    print("     S1b prior>=1000: %s   S1c cap: %s   S1d runway: %s"
          % (sc["S1b_prior1000"], sc["S1c_cap"], sc["S1d_runway"]))
    print("  STAGE 2: own fuel a/b=%s/%s  cross fuel %s a/b=%s/%s  "
          "d_POC=%s in_VA=%s"
          % (f["own_fa"], f["own_fb"], f["x_src"], f["x_fa"], f["x_fb"],
             f["d_POC"], f["in_VA"]))
    for kw in (dict(x_t=0.65), dict(x_t=0.85)):
        print("     S2a(x>=%.2f)=%s" % (kw["x_t"],
                                        side_calls(f, **kw)["S2a_xfuel"]))
    print("     S2b OWN(dead)=%s  S2c S10=%s  S2d P029=%s"
          % (side_calls(f)["S2b_ownfuel"], side_calls(f)["S2c_poc"],
             side_calls(f)["S2d_p029"]))
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backtest", action="store_true")
    ap.add_argument("--out", default=None)
    ap.add_argument("--cell", type=int, default=None)
    a = ap.parse_args()
    if a.cell is not None:
        day7_cell(a.cell)
        return 0
    if not a.backtest:
        raise SystemExit("--backtest or --cell K")
    return backtest(a.out)


if __name__ == "__main__":
    sys.exit(main())
