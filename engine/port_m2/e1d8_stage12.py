#!/usr/bin/python3
"""E1 STUDY DAY 8 — THE PRE-REGISTRATION OF THE *CORRECTED* THREE STAGES
(CC-M2-19.1/19.2: stage 1 is a ROLLING ROW-LEVEL STATE; composition order is
SIDE > SEAT > MOMENT).

Day 7 ran stage 1 as ONE CALL PER CELL fixed at the cell open and it inverted:
seat precision 0.500 against a 0.556 "seat everything" base, winner recall
0.146 against a pre-registered 0.884, because NKD/TOKYO opened at `rv1800`
53.0 and produced 68 winners four to eight hours later at `rv1800` 278-602.
CC-M2-19.1 rules the FORM corrected: **seat state is a rolling per-row object**
(row-level `rv1800 >= 250` holds 92.8% of seven sessions' winners), and
CC-M2-19.4 resurrects `unspent_sess`, the term day 7 dropped as a non-signal
which would have refused both of that day's grossly over-extended empty cells.

THIS MODULE IS THE PRE-REGISTRATION OF THAT CORRECTED FORM, scored on the
POOLED ROW POOL of the seven unblinded study sessions (ERA_NOTES §33/§41 method
law: thresholds are settled on the pooled pool, never on a replay), BEFORE any
day-8 row is called.

=======================================================================
STAGE 1 — ROLLING FEASIBILITY (a refusal object; no mirror to fail)
=======================================================================
 R1  ROLLING VOL   `rv1800` AT THE CANDIDATE'S OWN ROW >= T   (CC-M2-19.1)
 R2  SESSION CAP   `unspent_sess` >= T, PASS when '.' (SI's fvol is REFUSED on
                   four of seven study sessions, so a refusal here would delete
                   SI from the round)                          (CC-M2-19.4)
 R2b BINDING CAP   `unspent_bind` >= T — the ERA_NOTES §77 alternative: the
                   BINDING row (phase row when the exit is a phase close), the
                   field the day-7 flip-threshold named and never tested
 R3  P025 RUNWAY   `runway_phase` >= 12,000s — BROKEN on day 7 (54 of 123
                   winners below it), carried only as the control
 R4  P033 PRODUCT  `runway_phase * rv1800` (== `sigma_to_exit^2 * 1800`), the
                   object P025's break minted.  CENSUS-FIRST, NEVER TRADED RAW
                   (briefing law) — measured here, not gated on.

=======================================================================
STAGE 2 — CELL SIDE: S10 GEOMETRY IS THE ONLY HAND INSTRUMENT LEFT
=======================================================================
CC-M2-18.3 killed P031 FINAL (mirror fails all 16 legs; destruction inverted);
P009 own-asset fuel is dead twice over; P029 is dead as a rule (era-period
trend).  What remains uncensused is S10's developing-profile GEOMETRY:
 S2c  `d_POC` with `in_VA` at the cell open — price OUTSIDE developing value
      by >= T dollars calls the side BACK TOWARD VALUE.
 S2e  STRUCK — UNIMPLEMENTABLE (R19).  S2e was "the same field read at the
      cell's MEDIAN row", offered as day 7's stale-anchor lesson applied to
      stage 2.  It is not an estimator at all: the median row sits HOURS after
      the cell open, and at the cell open you cannot know which row will turn
      out to be the median.  It was nevertheless scored in the same
      pre-registration table, on the same truth, as the causal `@open`
      variants — one verdict away from adoption on the strength of a number no
      instrument could ever have produced.  It is now EXCLUDED FROM THE TABLE
      and reported as a refusal; the row that used to carry it prints the
      reason.  (Harmless in outcome — CC-M2-21.2 ruled S10 side DEAD at all
      grains — and a defect in the instrument regardless.)
      THE CAUSAL FORM, if the stale-anchor question is ever re-opened: read the
      SAME field at a fixed OFFSET after the open (e.g. open+1800s) and score
      only cells whose phase still has that much runway, which is knowable at
      the moment it is read.  Not run here; registered, not implemented.
Every side estimator is reported WITH ITS MIRROR on the winner-bearing cells
(CC-M2-13.1) and with the count of SESSIONS LOST.

USAGE
  --backtest   score both stages on days 1-7 (the pre-registration)
  --cell K     emit day-8 cell K's stage-2 values at its own open (the reader
               consumes cells in chronological order; the caller is
               `e1d8_cellbrief.py`, which enforces the as-of cut)
"""
import argparse
import csv
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TRIAGE = "/workspace/artifacts/cache/port/m2/triage"
DAYS = [("E1D1", "20210701"), ("E1D2", "20210702"), ("E1D3", "20210705"),
        ("E1D4", "20210706"), ("E1D5", "20210707"), ("E1D6", "20210708"),
        ("E1D7", "20210709")]
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


_IDX = {}


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


def winners(tag):
    """The day's D-021 winner cids (S14 — lawful only for UNBLINDED days)."""
    import panel_score as PS
    out = set()
    for r in load(tag):
        if PS.outcome(r["cid"])["winner_close"]:
            out.add(r["cid"])
    return out


def certs(tag):
    import panel_score as PS
    return {r["cid"]: (PS.outcome(r["cid"])["cert_close_usd"] or 0.0)
            for r in load(tag)}


# ==================================================================== stage 1
def r_state(r, rv_t=250.0, cap_t=500.0, bind_t=None, runway_t=None):
    """The ROLLING seat state, evaluated at THIS row (CC-M2-19.1/19.4)."""
    rv = F(r, "rv1800")
    if rv is None or rv < rv_t:
        return False
    if cap_t is not None:
        u = F(r, "unspent_sess")
        if u is not None and u < cap_t:
            return False
    if bind_t is not None:
        b = F(r, "unspent_bind")
        if b is not None and b < bind_t:
            return False
    if runway_t is not None:
        rw = F(r, "runway_phase")
        if rw is None or rw < runway_t:
            return False
    return True


def stage1_backtest():
    pool, win, cert = [], set(), {}
    for tag, _ in DAYS:
        pool += load(tag)
        win |= winners(tag)
        cert.update(certs(tag))
    n, nw = len(pool), len(win)
    print("STAGE 1 — ROLLING ROW-LEVEL FEASIBILITY, pooled over %d sessions: "
          "%d rows, %d D-021 winners (base %.2f%%)"
          % (len(DAYS), n, nw, 100.0 * nw / n))
    print("%-46s %7s %7s %7s %7s %7s %9s" % (
        "rolling state", "rows", "win", "recall", "win%", "lift", "mean $"))
    arms = []
    for rv_t in (100.0, 150.0, 200.0, 250.0, 300.0, 400.0):
        arms.append(("R1 rv1800(row) >= %d" % rv_t,
                     dict(rv_t=rv_t, cap_t=None)))
    for cap_t in (0.0, 500.0, 1000.0):
        arms.append(("R1(250) + R2 unspent_sess >= %d" % cap_t,
                     dict(rv_t=250.0, cap_t=cap_t)))
    for bind_t in (0.0, 500.0, 1000.0):
        arms.append(("R1(250) + R2b unspent_bind >= %d" % bind_t,
                     dict(rv_t=250.0, cap_t=None, bind_t=bind_t)))
    arms.append(("R1(250)+R2(500)+R2b(500)",
                 dict(rv_t=250.0, cap_t=500.0, bind_t=500.0)))
    arms.append(("R1(250)+R2(500)+R3 P025 runway>=12000",
                 dict(rv_t=250.0, cap_t=500.0, runway_t=12000.0)))
    arms.append(("R1(200)+R2(500)", dict(rv_t=200.0, cap_t=500.0)))
    arms.append(("R1(150)+R2(500)", dict(rv_t=150.0, cap_t=500.0)))
    out = []
    for name, kw in arms:
        keep = [r for r in pool if r_state(r, **kw)]
        kw_ = len([r for r in keep if r["cid"] in win])
        m = (sum(cert[r["cid"]] for r in keep) / len(keep)) if keep else 0.0
        rate = (kw_ / len(keep)) if keep else 0.0
        print("%-46s %7d %7d %7.3f %6.2f%% %7.2fx %+9.2f"
              % (name, len(keep), kw_, kw_ / nw if nw else 0,
                 100.0 * rate, rate / (nw / n) if nw else 0, m))
        out.append((name, len(keep), kw_, kw_ / nw, rate, m))
    # P033 deciles — CENSUS ONLY, never a gate (briefing law)
    print("\nR4 P033 = runway_phase * rv1800 (census-only, NEVER traded raw):")
    vals = []
    for r in pool:
        rw, rv = F(r, "runway_phase"), F(r, "rv1800")
        if rw is None or rv is None:
            continue
        vals.append((math.sqrt(max(rw, 1.0) / 1800.0) * rv, r["cid"]))
    vals.sort()
    B = 10
    print("%-8s %8s %8s %8s %9s" % ("decile", "rows", "win", "win%", "mean $"))
    for i in range(B):
        seg = vals[i * len(vals) // B:(i + 1) * len(vals) // B]
        w = sum(1 for _, c in seg if c in win)
        m = sum(cert[c] for _, c in seg) / len(seg)
        print("%-8s %8d %8d %7.2f%% %+9.2f"
              % ("%d [%.0f-%.0f]" % (i + 1, seg[0][0], seg[-1][0]),
                 len(seg), w, 100.0 * w / len(seg), m))
    return out


# ==================================================================== stage 2
def cells_of(rows):
    seen = {}
    for r in rows:
        k = (r["asset"], r["phase_dec"])
        if k not in seen:
            seen[k] = r["_sec"]
    return sorted((v, k[0], k[1]) for k, v in seen.items())


def cell_rows(rows, asset, phase):
    return [r for r in rows if r["asset"] == asset and r["phase_dec"] == phase]


# -------------------------------------------------- R19: causal anchors -----
# The ROW of a cell a side estimator is allowed to read.  An anchor is legal
# only if the row it selects can be IDENTIFIED AT THE CELL OPEN.  `open` can;
# the struck S2e anchor (`cr[len(cr) // 2]`, the cell's MEDIAN row) cannot —
# it sits hours later and you cannot know at the open which row will turn out
# to be the median.  Estimators iterate this registry, so an unimplementable
# anchor cannot be scored beside a causal one without being registered here
# and failing `assert_anchor_causal`.
ANCHORS = (("open", "0", lambda cr: cr[0]),)


def assert_anchor_causal(cr, name, row):
    """REFUSE an anchor whose row is not identifiable at the cell open."""
    if int(float(row["_sec"])) != int(float(cr[0]["_sec"])):
        raise SystemExit(
            "R19 ANCHOR REFUSAL: estimator anchor %r selects a row at sec=%s "
            "in a cell that opens at sec=%s. At the cell open you cannot know "
            "which row that will be, so this is not an estimator — it is a "
            "post-hoc reading, and it must not be scored in the same "
            "pre-registration table as the @open variants."
            % (name, row["_sec"], cr[0]["_sec"]))
    return True


def s10_side(d_poc, in_va, t):
    if d_poc is None or in_va is None or in_va != 0 or abs(d_poc) < t:
        return None
    return "SHORT" if d_poc > 0 else "LONG"


def stage2_backtest():
    import panel_score as PS
    rec = []
    for tag, _ in DAYS:
        rows = load(tag)
        truth = {}
        for r in rows:
            if PS.outcome(r["cid"])["winner_close"]:
                a = truth.setdefault((r["asset"], r["phase_dec"]), [0, 0])
                a[0 if r["side"] == "LONG" else 1] += 1
        for cut, asset, phase in cells_of(rows):
            t = truth.get((asset, phase))
            if not t:
                continue
            cr = cell_rows(rows, asset, phase)
            # R19: the cell's MEDIAN row (`cr[len(cr) // 2]`) used to be read
            # here and scored as estimator S2e.  It sits hours after the cell
            # open and cannot be identified AT the open, so it is not computed
            # at all any more — an unimplementable estimator must not be in a
            # pre-registration table beside the causal ones.  Every anchor now
            # comes from the registry and is checked.
            e = dict(day=tag, asset=asset, phase=phase,
                     truth="LONG" if t[0] > t[1] else "SHORT",
                     n_win=t[0] + t[1], n_rows=len(cr),
                     open_sec=int(float(cr[0]["_sec"])))
            for _nm, _key, _pick in ANCHORS:
                _r = _pick(cr)
                assert_anchor_causal(cr, _nm, _r)
                e["d" + _key] = F(_r, "d_POC")
                e["v" + _key] = F(_r, "in_VA")
            rec.append(e)
    print("\nSTAGE 2 — S10 GEOMETRY (the only hand side-instrument CC-M2-18.3 "
          "leaves standing), %d winner-bearing cells over %d sessions"
          % (len(rec), len(DAYS)))
    print("%-34s %5s %5s %6s %8s %7s %8s" % (
        "estimator", "right", "wrong", "silent", "accuracy", "mirror",
        "sess.lost"))
    for label, key, t in [("S2c d_POC@open   |d|>=$250", "0", 250.0),
                          ("S2c d_POC@open   |d|>=$500", "0", 500.0),
                          ("S2c d_POC@open   |d|>=$1000", "0", 1000.0)]:
        ri = wr = si = 0
        per = {}
        for c in rec:
            s = s10_side(c["d" + key], c["v" + key], t)
            if s is None:
                si += 1
                continue
            ok = (s == c["truth"])
            ri += ok
            wr += (not ok)
            p = per.setdefault(c["day"], [0, 0])
            p[0 if ok else 1] += 1
        dec = ri + wr
        lost = sum(1 for v in per.values() if v[1] > v[0])
        print("%-34s %5d %5d %6d %8s %7s %8d"
              % (label, ri, wr, si,
                 "%.3f" % (ri / dec) if dec else "-",
                 "%.3f" % (wr / dec) if dec else "-", lost))
    print("%-34s %5s %5s %6s %8s %7s %8s   <- R19"
          % ("S2e d_POC@median |d|>=any", "R", "R", "R", "REFUSED", "R", "R"))
    print("  S2e IS STRUCK FROM THIS TABLE AND NOT COMPUTED: the cell's median "
          "row sits hours after the cell open and cannot be identified AT the "
          "open, so no instrument could ever produce this column. It was "
          "scored here beside the causal @open variants on the same truth. "
          "The causal replacement, if the stale-anchor question is re-opened, "
          "is the SAME field at a FIXED OFFSET after the open on cells with "
          "that much runway left — registered, not implemented.")
    return rec


def _sess_state(rows, asset, cut):
    """Strictly-prior session state for `asset` at `cut`: net $, position in
    the session range so far, and the prior completed phase's net $."""
    rs = [r for r in rows if r["asset"] == asset and r["_sec"] < cut
          and r["_mid"] is not None]
    if not rs:
        return None
    mult = F(rs[-1], "mult") or 1.0
    mids = [r["_mid"] for r in rs]
    net = (mids[-1] - mids[0]) * mult
    rng = (max(mids) - min(mids))
    pos = ((mids[-1] - min(mids)) / rng) if rng > 0 else None
    ph, last = None, rs[-1]["phase_dec"]
    q = [r for r in rs if r["phase_dec"] == last]
    if q:
        m2 = [r["_mid"] for r in q]
        ph = (m2[-1] - m2[0]) * mult
    return dict(net=net, pos=pos, prior_phase_net=ph, mult=mult)


def stage2_extended():
    """LEADING side estimators, mirror-law tested on the winner-bearing cells
    of the seven unblinded sessions.  Everything here is strictly prior to the
    cell's own open; nothing reads an outcome of the cell it calls."""
    import panel_score as PS
    rec = []
    for tag, _ in DAYS:
        rows = load(tag)
        truth = {}
        for r in rows:
            if PS.outcome(r["cid"])["winner_close"]:
                a = truth.setdefault((r["asset"], r["phase_dec"]), [0, 0])
                a[0 if r["side"] == "LONG" else 1] += 1
        for cut, asset, phase in cells_of(rows):
            t = truth.get((asset, phase))
            if not t:
                continue
            r0 = [r for r in rows if r["_sec"] == cut and r["asset"] == asset
                  and r["phase_dec"] == phase][0]
            own = _sess_state(rows, asset, cut)
            others = [_sess_state(rows, a, cut) for a in ("SI", "HG", "NKD")
                      if a != asset]
            others = [o for o in others if o]
            rec.append(dict(
                day=tag, asset=asset, phase=phase,
                truth="LONG" if t[0] > t[1] else "SHORT", n_win=t[0] + t[1],
                d_poc=F(r0, "d_POC"), in_va=F(r0, "in_VA"),
                own=own, xnet=sum(o["net"] for o in others) if others else None,
                slope15=F(r0, "slope15m"), fph=F(r0, "fph_sflow"),
                f30=F(r0, "f30m_sflow")))

    def score(label, fn):
        ri = wr = si = 0
        per = {}
        for c in rec:
            s = fn(c)
            if s is None:
                si += 1
                continue
            ok = (s == c["truth"])
            ri += ok
            wr += (not ok)
            p = per.setdefault(c["day"], [0, 0])
            p[0 if ok else 1] += 1
        dec = ri + wr
        lost = sum(1 for v in per.values() if v[1] > v[0])
        print("%-44s %5d %5d %6d %8s %7s %8d"
              % (label, ri, wr, si, "%.3f" % (ri / dec) if dec else "-",
                 "%.3f" % (wr / dec) if dec else "-", lost))

    def L(x):
        return "LONG" if x > 0 else "SHORT"

    print("\nSTAGE 2 — LEADING SIDE ESTIMATORS, mirror-law tested on the same "
          "%d winner-bearing cells" % len(rec))
    print("%-44s %5s %5s %6s %8s %7s %8s" % (
        "estimator", "right", "wrong", "silent", "accuracy", "mirror",
        "sess.lost"))
    score("X1 prior-phase net sign (CONTINUATION)",
          lambda c: None if not c["own"] or c["own"]["prior_phase_net"] in
          (None, 0) else L(c["own"]["prior_phase_net"]))
    score("X1m prior-phase net sign (REVERSAL)",
          lambda c: None if not c["own"] or c["own"]["prior_phase_net"] in
          (None, 0) else L(-c["own"]["prior_phase_net"]))
    score("X2 session net sign (CONTINUATION)",
          lambda c: None if not c["own"] or c["own"]["net"] == 0
          else L(c["own"]["net"]))
    score("X3 session pos >=0.7 LONG / <=0.3 SHORT (trend)",
          lambda c: None if not c["own"] or c["own"]["pos"] is None else
          ("LONG" if c["own"]["pos"] >= 0.7 else
           ("SHORT" if c["own"]["pos"] <= 0.3 else None)))
    score("X4 COMPLEX net sign (other two assets, trend)",
          lambda c: None if c["xnet"] in (None, 0) else L(c["xnet"]))
    score("X5 S10 CONTINUATION away from value |d|>=$250",
          lambda c: None if s10_side(c["d_poc"], c["in_va"], 250.0) is None
          else ("LONG" if c["d_poc"] > 0 else "SHORT"))
    score("X5b S10 CONTINUATION away from value |d|>=$500",
          lambda c: None if s10_side(c["d_poc"], c["in_va"], 500.0) is None
          else ("LONG" if c["d_poc"] > 0 else "SHORT"))
    score("X6 30m sflow sign at the cell open (CONTINUATION)",
          lambda c: None if c["f30"] in (None, 0) else L(c["f30"]))
    score("X7 phase sflow sign at the cell open (CONTINUATION)",
          lambda c: None if c["fph"] in (None, 0) else L(c["fph"]))
    score("X8 slope15m sign at the cell open (CONTINUATION)",
          lambda c: None if c["slope15"] in (None, 0) else L(c["slope15"]))
    score("X9 X2 and X4 AGREEING (complex + own trend)",
          lambda c: None if (not c["own"] or c["xnet"] in (None, 0)
                             or c["own"]["net"] == 0
                             or L(c["own"]["net"]) != L(c["xnet"]))
          else L(c["own"]["net"]))
    score("X9m X2 and X4 AGREEING, MIRRORED",
          lambda c: None if (not c["own"] or c["xnet"] in (None, 0)
                             or c["own"]["net"] == 0
                             or L(c["own"]["net"]) != L(c["xnet"]))
          else L(-c["own"]["net"]))
    return rec


def cell_report(tag, k, index=None):
    rows = load(tag) if index is None else index
    cells = cells_of(rows)
    cut, asset, phase = cells[k]
    cr = [r for r in rows if r["_sec"] == cut and r["asset"] == asset
          and r["phase_dec"] == phase]
    r0 = cr[0]
    print("CELL #%d %s/%s open sec=%d (%s)  at-open row %s"
          % (k, asset, phase, cut, r0["clock"], r0["cid"]))
    print("  S10 GEOMETRY  dev_poc=%s dev_vah=%s dev_val=%s  d_POC=%s "
          "d_VAH=%s d_VAL=%s in_VA=%s"
          % (r0.get("dev_poc"), r0.get("dev_vah"), r0.get("dev_val"),
             r0.get("d_POC"), r0.get("d_VAH"), r0.get("d_VAL"),
             r0.get("in_VA")))
    for t in (250.0, 500.0, 1000.0):
        print("     S2c @ $%-5d -> %s" % (t, s10_side(F(r0, "d_POC"),
                                                      F(r0, "in_VA"), t)))
    print("  ROLLING SEAT STATE AT THE OPEN  rv1800=%s rv900=%s rv300=%s "
          "rv60=%s | unspent_sess=%s unspent_bind=%s | runway_phase=%s"
          % (r0.get("rv1800"), r0.get("rv900"), r0.get("rv300"),
             r0.get("rv60"), r0.get("unspent_sess"), r0.get("unspent_bind"),
             r0.get("runway_phase")))
    print("     R1(250)=%s  R1+R2(500)=%s"
          % (r_state(r0, 250.0, None), r_state(r0, 250.0, 500.0)))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--backtest", action="store_true")
    p.add_argument("--cell", type=int)
    p.add_argument("--index")
    a = p.parse_args()
    if a.backtest:
        stage1_backtest()
        stage2_backtest()
        stage2_extended()
    if a.cell is not None:
        idx = None
        if a.index:
            rows = list(csv.DictReader(
                [l for l in open(a.index) if not l.startswith("#")],
                delimiter="\t"))
            for r in rows:
                r["_sec"] = int(float(r["sec"]))
                r["_mid"] = F(r, "mid")
            rows.sort(key=lambda r: (r["_sec"], r["cid"]))
            idx = rows
        cell_report("E1D8", a.cell, index=idx)


if __name__ == "__main__":
    sys.exit(main())
