#!/usr/bin/python3
"""E1 STUDY DAY 6 — THE CELL-SIDE ESTIMATOR `E1D6-CS`, DECLARED AND
PRE-REGISTERED (CC-M2-16.1 / CC-M2-15.5).

WHAT THIS IS.  CC-M2-16.1 made the (ASSET, PHASE) CELL the invariant unit and
defined M3 model #1 as the PHASE-SIDE CLASSIFIER anchored at each phase open.
The day-6 brief orders an explicit ex-ante SIDE CALL with named evidence for
EVERY cell, committed before that cell's first candidate row.  A reader making
nine free-hand calls produces nine anecdotes; a reader making nine calls from a
DECLARED, COMPONENT-WISE estimator produces a labelled feature table the
classifier lane can score component by component.  This module is that
estimator: six leading components, each a named field, each scored separately,
plus the composite.

THE READER'S JUDGEMENT IS NOT REPLACED BY IT.  The committed cell call may
override the composite; every override is logged with its reason, so the
ledger separates "the estimator was wrong" from "the reader was wrong".

=======================================================================
THE SIX COMPONENTS (all strictly prior to the cell's first candidate)
=======================================================================
 C1 PRIOR-PHASE CLOSE POSITION.  Where the last mid before the cell open sits
    inside the PREVIOUS phase's own mid range: pos >= 0.65 -> LONG, <= 0.35 ->
    SHORT, else 0.  The phase-grain analogue of the best naive estimator the
    CC-M2-15.2 side probe measured (session-return-at-phase-open, 0.64
    agreement, p=.063).  Fields: triage `mid` path of the prior phase.
 C2 SESSION NET SO FAR.  sign of (last prior mid - session's first mid) * mult,
    dead-zoned at +/-$150.  The session-return term itself.  Fields: `mid`,
    `mult`.
 C3 OVERNIGHT CONTINUATION.  sign of the PRIOR SESSION's net move (its own
    first->last candidate mid), dead-zoned at +/-$300.  Strictly prior: the
    prior study session is fully unblinded (CC-M2-9.4 permits prior unblinded
    rounds).  Fields: prior session's triage index `mid`, `mult`.
 C4 FUEL OVERHANG.  S8 FUEL MAP at the boundary: the trapped side must
    transact.  trapped_above/phase_total >= 0.65 -> SHORT (every buyer of the
    prior phase is underwater and sells into bounces); trapped_below >= 0.65 ->
    LONG.  This is V2's SUPPLY claim (net-positive refusal on all five
    sessions, CC-M2-16.2), used here for the first time as a SIDE source —
    which is the claim P009 FUEL_POLARITY died for, so it is declared as the
    component most likely to fail and is scored alone.
 C5 CROSS-ASSET METALS COHERENCE.  SI and HG are one trade; the OTHER metal's
    session net so far (dead-zoned at +/-$300) votes on this metal's cell.
    NKD abstains from this component (it is not a metal).  Fields: S11 /
    the other asset's `mid` path.
 C6 MULTI-DAY LEVEL POSITION.  S4's NDAY family: nearest N-day level distance
    d$ from the mid on the cell's first sheet is a PRIOR-SESSION fact (N-day
    highs/lows are born before the session).  All N-day levels far BELOW the
    mid = price at multi-day highs = uptrend -> LONG; far above -> SHORT.
    Read from the day's own first sheet ONLY through prior-session-born level
    families (declared as PRIOR-SESSION CONTEXT below).

COMPOSITE: sum of the six votes; sign of the sum is the call; a zero sum is
NO-CALL (the honest abstention, logged as such and scored as a miss for
accuracy purposes so abstention is not free).

DECLARED READING RULE FOR A CELL WITH NO PRIOR ROWS (the session's first cell
per asset): the only lawful evidence is PRIOR-SESSION CONTEXT — C3, C6, and
the prior session's phase-close positions.  C1/C2/C4/C5 abstain.  This is
declared here rather than improvised per cell.

MIRROR LAW (CC-M2-13.1, binding): the pre-registration below scores E1D6-CS
and its MIRROR on every (asset, phase) cell of the five unblinded study
sessions BEFORE the day-6 cells are called.  The result is printed by
`--backtest` and is quoted in the committed policy whatever it says.
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TRIAGE = "/workspace/artifacts/cache/port/m2/triage"
DAYS = [("E1D1", "20210701"), ("E1D2", "20210702"), ("E1D3", "20210705"),
        ("E1D4", "20210706"), ("E1D5", "20210707")]
PHASES = ("TOKYO", "LONDON", "NY")
PRIOR_SESSION = {"20210701": None, "20210702": "20210701",
                 "20210705": "20210702", "20210706": "20210705",
                 "20210707": "20210706", "20210708": "20210707"}
DEAD_SESS = 150.0
DEAD_ON = 300.0
DEAD_X = 300.0
POS_HI, POS_LO = 0.65, 0.35
FUEL_FRAC = 0.65


def F(r, k):
    try:
        return float(r[k])
    except Exception:
        return None


def index_path(tag):
    for c in ("%s_TRIAGE_INDEX.tsv" % tag, "%s_TRIAGE_INDEX_V2R.tsv" % tag):
        p = os.path.join(TRIAGE, c)
        if os.path.exists(p):
            return p
    raise SystemExit("no index for %s" % tag)


_IDX = {}


def load(tag):
    if tag in _IDX:
        return _IDX[tag]
    rows = list(csv.DictReader(
        [l for l in open(index_path(tag)) if not l.startswith("#")],
        delimiter="\t"))
    for r in rows:
        r["_sec"] = int(float(r["sec"]))
        r["_mid"] = F(r, "mid")
    rows.sort(key=lambda r: (r["_sec"], r["cid"]))
    _IDX[tag] = rows
    return rows


def sess_net(rows, asset):
    rs = [r for r in rows if r["asset"] == asset and r["_mid"] is not None]
    if len(rs) < 2:
        return None
    return (rs[-1]["_mid"] - rs[0]["_mid"]) * (F(rs[-1], "mult") or 1.0)


def cells_of(rows):
    seen = {}
    for r in rows:
        k = (r["asset"], r["phase_dec"])
        if k not in seen:
            seen[k] = r["_sec"]
    return sorted((v, k[0], k[1]) for k, v in seen.items())


# ------------------------------------------------------------- components ---
def components(rows, asset, phase, cut, prior_net, nday_d):
    """The six votes at a cell open.  `rows` is the WHOLE day; only rows with
    _sec < cut are ever read (asserted)."""
    pre = [r for r in rows if r["_sec"] < cut]
    for r in pre:
        assert r["_sec"] < cut
    mine = [r for r in pre if r["asset"] == asset and r["_mid"] is not None]
    v = {}

    # C1 prior-phase close position
    v["C1"] = 0
    v["C1_val"] = None
    if mine:
        pph = mine[-1]["phase_dec"]
        q = [r for r in mine if r["phase_dec"] == pph]
        mids = [r["_mid"] for r in q]
        if len(mids) >= 3 and max(mids) > min(mids):
            pos = (mids[-1] - min(mids)) / (max(mids) - min(mids))
            v["C1_val"] = round(pos, 3)
            v["C1"] = 1 if pos >= POS_HI else (-1 if pos <= POS_LO else 0)

    # C2 session net so far
    v["C2"] = 0
    v["C2_val"] = None
    if len(mine) >= 2:
        net = (mine[-1]["_mid"] - mine[0]["_mid"]) * (F(mine[-1], "mult") or 1)
        v["C2_val"] = round(net, 1)
        v["C2"] = 1 if net > DEAD_SESS else (-1 if net < -DEAD_SESS else 0)

    # C3 overnight continuation (prior session net)
    v["C3_val"] = None if prior_net is None else round(prior_net, 1)
    v["C3"] = 0 if prior_net is None else (
        1 if prior_net > DEAD_ON else (-1 if prior_net < -DEAD_ON else 0))

    # C4 fuel overhang at the boundary
    v["C4"] = 0
    v["C4_val"] = None
    if mine:
        L = mine[-1]
        ta, tb, pt = F(L, "trapped_above"), F(L, "trapped_below"), F(L, "phase_total")
        if pt:
            fa, fb = (ta or 0) / pt, (tb or 0) / pt
            v["C4_val"] = "above %.2f below %.2f" % (fa, fb)
            if fa >= FUEL_FRAC:
                v["C4"] = -1
            elif fb >= FUEL_FRAC:
                v["C4"] = 1

    # C5 cross-asset metals coherence
    v["C5"] = 0
    v["C5_val"] = None
    other = {"SI": "HG", "HG": "SI"}.get(asset)
    if other:
        o = [r for r in pre if r["asset"] == other and r["_mid"] is not None]
        if len(o) >= 2:
            net = (o[-1]["_mid"] - o[0]["_mid"]) * (F(o[-1], "mult") or 1.0)
            v["C5_val"] = round(net, 1)
            v["C5"] = 1 if net > DEAD_X else (-1 if net < -DEAD_X else 0)

    # C6 multi-day level position
    v["C6_val"] = nday_d
    v["C6"] = 0
    if nday_d is not None:
        v["C6"] = 1 if nday_d < -500 else (-1 if nday_d > 500 else 0)

    v["sum"] = sum(v[k] for k in ("C1", "C2", "C3", "C4", "C5", "C6"))
    v["call"] = "LONG" if v["sum"] > 0 else ("SHORT" if v["sum"] < 0 else "NOCALL")
    return v


# --------------------------------------------------------------- S4 NDAY ----
SHEETS = "/workspace/artifacts/cache/port/m2/era/E1/STUDY"


def nday_nearest(asset, date8, cid):
    """Nearest N-day-family level distance d$ on `cid`'s sheet.

    PRIOR-SESSION CONTEXT: the NDAY family's levels are N-day highs/lows, born
    before this session opened, so their distance from the open mid is a fact
    the reader could hold before the cell existed.  Read from the cell's first
    sheet because that is where the roll-up is printed.
    """
    p = os.path.join(SHEETS, asset, str(date8), "%s.BLIND.sheet.txt" % cid)
    if not os.path.exists(p):
        return None
    for ln in open(p):
        if "REMAINDER rolled up by family" in ln:
            continue
        if " NDAY=" in ln or ln.strip().startswith("NDAY="):
            for tok in ln.split():
                if tok.startswith("NDAY="):
                    try:
                        return float(tok.split("=")[1].split("/")[1])
                    except Exception:
                        return None
    return None


# ----------------------------------------------------------------- truth ----
def cell_truth(tag, date8):
    """{(asset, phase): (side, n_win, n_long, n_short)} from the FROZEN roster.

    LAWFUL ONLY FOR UNBLINDED SESSIONS (days 1-5).  Never called for day 6
    before the seal.
    """
    import panel_score as PS
    rows = load(tag)
    out = {}
    for r in rows:
        o = PS.outcome(r["cid"])
        if not o["winner_close"]:
            continue
        k = (r["asset"], r["phase_dec"])
        a = out.setdefault(k, [0, 0])
        if r["side"] == "LONG":
            a[0] += 1
        else:
            a[1] += 1
    return {k: ("LONG" if v[0] > v[1] else "SHORT", v[0] + v[1], v[0], v[1])
            for k, v in out.items()}


# -------------------------------------------------------------- backtest ----
def run_day(tag, date8, with_truth=True):
    rows = load(tag)
    prior = PRIOR_SESSION[date8]
    pnet = {}
    if prior:
        ptag = dict((d, t) for t, d in DAYS).get(prior)
        if ptag:
            prows = load(ptag)
            for a in ("SI", "HG", "NKD"):
                pnet[a] = sess_net(prows, a)
    truth = cell_truth(tag, date8) if with_truth else {}
    out = []
    for cut, asset, phase in cells_of(rows):
        first = [r for r in rows
                 if r["asset"] == asset and r["phase_dec"] == phase][0]
        nd = nday_nearest(asset, date8, first["cid"]) if phase == first["phase_dec"] else None
        v = components(rows, asset, phase, cut, pnet.get(asset), nd)
        t = truth.get((asset, phase))
        out.append(dict(day=tag, date8=date8, asset=asset, phase=phase,
                        open_sec=cut, truth=(t[0] if t else "NONE"),
                        n_win=(t[1] if t else 0), **v))
    return out


def day6_cell(k):
    """Components for ONE day-6 cell, computed from rows strictly before its
    open.  ONE CELL AT A TIME by construction: the reader must commit cell k's
    call before asking for k+1, because cell k+1's components are computed
    from tape cell k could not see."""
    rows = load("E1D6")
    prows = load("E1D5")
    pnet = {a: sess_net(prows, a) for a in ("SI", "HG", "NKD")}
    cl = cells_of(rows)
    cut, asset, phase = cl[k]
    first = [r for r in rows
             if r["asset"] == asset and r["phase_dec"] == phase][0]
    nd = nday_nearest(asset, "20210708", first["cid"])
    v = components(rows, asset, phase, cut, pnet.get(asset), nd)
    print("CELL #%d  %s %s  open=%d  (E1D6-CS components, cut < %d)"
          % (k, asset, phase, cut, cut))
    for c in ("C1", "C2", "C3", "C4", "C5", "C6"):
        print("   %s = %+d   [%s]" % (c, v[c], v[c + "_val"]))
    print("   SUM = %+d  ->  E1D6-CS composite call = %s" % (v["sum"], v["call"]))
    print("   PHASE_PRIOR (P029, pre-registered): %s"
          % ("LONG" if phase in ("TOKYO", "LONDON") else "SHORT"))
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backtest", action="store_true")
    ap.add_argument("--day6-cell", type=int, default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.day6_cell is not None:
        day6_cell(a.day6_cell)
        return 0
    if not a.backtest:
        raise SystemExit("--backtest")
    allr = []
    for tag, d8 in DAYS:
        allr += run_day(tag, d8)
    cols = ["day", "date8", "asset", "phase", "open_sec", "truth", "n_win",
            "C1", "C1_val", "C2", "C2_val", "C3", "C3_val", "C4", "C4_val",
            "C5", "C5_val", "C6", "C6_val", "sum", "call"]
    if a.out:
        with open(a.out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, delimiter="\t",
                               extrasaction="ignore")
            w.writeheader()
            for r in allr:
                w.writerow(r)
    live = [r for r in allr if r["truth"] != "NONE"]
    print("CELLS: %d total, %d with D-021 winners (the scorable cells)"
          % (len(allr), len(live)))
    for comp in ("C1", "C2", "C3", "C4", "C5", "C6", "call"):
        if comp == "call":
            hit = sum(1 for r in live if r["call"] == r["truth"])
            miss = sum(1 for r in live if r["call"] != r["truth"]
                       and r["call"] != "NOCALL")
            no = sum(1 for r in live if r["call"] == "NOCALL")
            print("COMPOSITE E1D6-CS: %d right / %d wrong / %d nocall  "
                  "accuracy(all live)=%.3f  accuracy(decided)=%s"
                  % (hit, miss, no, hit / len(live),
                     "%.3f" % (hit / (hit + miss)) if hit + miss else "NA"))
            print("  MIRROR: %d right / %d wrong (mirror accuracy(decided)=%s)"
                  % (miss, hit,
                     "%.3f" % (miss / (hit + miss)) if hit + miss else "NA"))
        else:
            hit = sum(1 for r in live
                      if r[comp] != 0
                      and ("LONG" if r[comp] > 0 else "SHORT") == r["truth"])
            wrong = sum(1 for r in live
                        if r[comp] != 0
                        and ("LONG" if r[comp] > 0 else "SHORT") != r["truth"])
            print("  %s: %d right / %d wrong / %d silent  acc=%s"
                  % (comp, hit, wrong, len(live) - hit - wrong,
                     "%.3f" % (hit / (hit + wrong)) if hit + wrong else "NA"))
    print("\nPER-CELL (live cells only):")
    print("%-6s %-4s %-6s %-6s %4s  %s" % ("day", "ast", "phase", "truth",
                                           "nwin", "C1 C2 C3 C4 C5 C6 sum call"))
    for r in live:
        print("%-6s %-4s %-6s %-6s %4d  %+d %+d %+d %+d %+d %+d %+3d %s"
              % (r["day"], r["asset"], r["phase"], r["truth"], r["n_win"],
                 r["C1"], r["C2"], r["C3"], r["C4"], r["C5"], r["C6"],
                 r["sum"], r["call"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
