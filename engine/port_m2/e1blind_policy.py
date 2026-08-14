#!/usr/bin/python3
"""THE E1 BLIND ROUND — THE READER'S EXECUTABLE POLICY (CC-M2-20.2 arm (a)).

This is the DISCRETIONARY READER's arm of the E1 blind round.  It is NOT the
frozen `e1_blind_declared_policy.py` (arm (b)) — it IMPORTS that module for
every shared term so that the difference between the two arms is exactly the
reader's registered increment and nothing else can drift.

    TAKE(r)  iff  CREATION_CLASS(r) and CORE(r) and not V2(r)

THE ONE REGISTERED INCREMENT OVER THE DECLARATION (committed before blind day
1 was opened, CC-M2-4.3 prospective registration):

  CREATION_CLASS = {NEWS-WINDOW, OPEN-DYNAMICS, **SHOCK-RESOLUTION**}

  The declaration's class set was chosen on the 9,026-row E1 STUDY pool, which
  contains ZERO SHOCK-RESOLUTION rows — the class could not be selected there
  even in principle.  Briefing item B1 (graded B: measured on THIS port data,
  committed receipts) carries it at ~$1,600 mean certificate against a
  REVERSAL baseline of ~$950, the highest class value in the briefing, and
  CC-M2-20.1 names the CREATION CLASSES as the convergence between the study
  reader's synthesis and the discovery census's oldest result.  SHOCK-
  RESOLUTION is a creation class by the same mechanism the declaration states:
  a move is being MADE (a shock is resolving) rather than a completed move
  being FADED.  It is 8 rows of the 12,418 in this round — the increment is
  registered for correctness, not for its size, and the arms file lets the
  scorer subtract it exactly.

THE A|B|C GRADE, REBUILT ON RULE-INDEPENDENT EVIDENCE (CC-M2-10.5 disqualified
the old grade; it was `sigma_to_exit = rv1800 * sqrt(runway)`, i.e. built from
T2's own field, and it is anti-calibrated with an empty top band).  The rebuilt
grade reads ONLY fields no term of the call reads:

    M_hat = q50                      (S9 fvol expected-move dollars) if present
          = K_asset * rv1800         otherwise, K = median(q50/rv1800) measured
                                     on the unblinded E1 STUDY indices
                                     (NKD 2.90, HG 4.70, pooled 3.95 for SI,
                                     whose fvol is REFUSED — defect D23)
    A: M_hat >= $1,500   B: $700 <= M_hat < $1,500   C: M_hat < $700

    The bands ARE the briefing's dollar classes (>=$1,500 / $700-1,500 /
    <$700), so the grade is a magnitude statement in the units it is scored in,
    not a confidence vibe.  CAVEAT ON RECORD: SI always takes the fallback
    branch, so SI grades inherit a cross-asset constant — declared, not hidden.

WHAT IS ABSENT AND WHY (all four receipts are the study round's):
  * NO SIDE TERM.  Stage 2 has ZERO validated hand instruments (CC-M2-21.2,
    final).  The reader's committed cell-side calls went 5/14 against a mirror
    at 9/14.  Side reads are still WRITTEN, per cell, in the cell ledger — they
    are knowledge the program wants — and they are never allowed to gate.
  * NO VOLATILITY GATE (P034: a concentrator inverts on the seat-spending
    sub-population; the gate costs $7,562.50) and NOT its inversion either.
  * NO CAPACITY TERM (anti-signal on expansion; defect D22 asset selector).
  * NO CELL ABSTENTION (P035 is a real feasibility fact and an unproven gate:
    -$1,614 walk-forward over the eight study sessions).  The would-abstain
    flag is recorded per cell so the scorer can price the counterfactual.

POLICY EVOLUTION (CC-M2-20.2 allows evolution BETWEEN days via committed
notes only).  `VERSIONS` below is the whole history: every entry names the
blind day it takes effect from and the BLIND_NOTES.md section that argued it.
A day is always sealed with the version pinned by `--day`.
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e1_blind_declared_policy as D                             # noqa: E402

READER = "opus-discretionary"

# ---------------------------------------------------------------- versions --
# day_from -> (version, {params}, note)
VERSIONS = [
    (1, "RV1", {"classes": ("NEWS-WINDOW", "OPEN-DYNAMICS",
                            "SHOCK-RESOLUTION"), "drop_cells": ()},
     "registered before blind day 1: the declaration + SHOCK-RESOLUTION as the "
     "third CREATION class (B1; zero such rows existed in the study pool)"),
    (6, "RV2", {"classes": ("NEWS-WINDOW", "OPEN-DYNAMICS"),
                "drop_cells": (("NKD", "OPEN-DYNAMICS"),)},
     "BLIND_NOTES 'AFTER DAY 5': THE CARD RULE. A creation class is traded only "
     "where the sheet's own committed era-E1 census card beats that asset's "
     "REVERSAL-CONFIRMATION bulk on BOTH win_frac and mean_cert. Ex ante, no "
     "outcome: SI NEWS +$26.63/0.1187, SI OPEN -$1.91/0.0826, HG NEWS "
     "-$23.35/0.0653, HG OPEN -$21.29/0.0772, NKD NEWS -$34.66/0.0800 all pass "
     "their bulks (SI -$29.54/0.0590, HG -$32.65/0.0463, NKD -$44.97/0.0467); "
     "**NKD/OPEN-DYNAMICS (-$58.49) and SHOCK-RESOLUTION (HG n=13, 0 winners, "
     "-$456.44) FAIL and are dropped.** The dropped increment is my own day-0 "
     "registration, contradicted by the port's own census before it traded"),
]

K_FALLBACK = {"NKD": 2.90, "HG": 4.70, "SI": 3.95}
GRADE_A, GRADE_B = 1500.0, 700.0


def version_for(day):
    v = VERSIONS[0]
    for e in VERSIONS:
        if e[0] <= day:
            v = e
    return v


def m_hat(r):
    """Rule-independent magnitude estimate in dollars."""
    q = D.F(r, "q50")
    if q is not None:
        return q, "q50"
    rv = D.F(r, "rv1800")
    if rv is None:
        return None, "none"
    return K_FALLBACK.get(r.get("asset"), 3.95) * rv, "rv1800*K"


def grade(r):
    m, src = m_hat(r)
    if m is None:
        return "C", "M_hat unavailable"
    g = "A" if m >= GRADE_A else ("B" if m >= GRADE_B else "C")
    return g, "M_hat=$%.0f via %s" % (m, src)


def klass(r, params):
    if (r.get("asset"), r.get("cls")) in params.get("drop_cells", ()):
        return False
    return r.get("cls") in params["classes"]


def call_day(rows, day=1):
    """The reader's day-complete calls, chronological."""
    _dfrom, ver, params, _note = version_for(day)
    out = []
    for r in sorted(rows, key=lambda x: (int(float(x["sec"])), x["cid"])):
        t = D.terms(r)
        cls_ok = klass(r, params)
        core_ok = all(t[k] for k in D.TERMS)
        vetoed = D.v2(r) if (cls_ok and core_ok) else False
        fire = cls_ok and core_ok and not vetoed
        g, gwhy = grade(r)
        prim = D.evidence(r, t, cls_ok, vetoed)
        if not cls_ok:
            prim = ("primary: S1/S13 candidate class = %s — not a CREATION "
                    "class {NEWS-WINDOW, OPEN-DYNAMICS, SHOCK-RESOLUTION}; the "
                    "faded-move bulk (REVERSAL-CONFIRMATION, 91%% of all "
                    "candidates) runs 5.36%% winners on a NEGATIVE pooled mean "
                    "certificate over 9,026 day-complete study rows"
                    % r.get("cls"))
        out.append({
            "cid": r["cid"], "call": "TAKE" if fire else "SKIP",
            "conf": g, "grade_why": gwhy,
            "n_terms": sum(1 for k in D.TERMS if t[k]),
            "cls_gate": int(cls_ok), "core": int(core_ok),
            "vetoes": "V2" if vetoed else "",
            "primary": prim, "against": D.against(r),
            "asset": r["asset"], "phase_dec": r["phase_dec"],
            "clock": r["clock"], "sec": int(float(r["sec"])),
            "side": r["side"], "cls": r["cls"], "version": ver,
            **{k: int(t[k]) for k in D.TERMS}})
    return out


def seats(calls):
    """(asset, phase) -> cid of the seat spender (earliest TAKE), CC-M2-10.3."""
    held = {}
    for c in calls:
        if c["call"] != "TAKE":
            continue
        k = (c["asset"], c["phase_dec"])
        if k not in held:
            held[k] = c["cid"]
    return held


def minimal_pair(cid, calls, rows):
    """Nearest non-TAKE in the same cell + the exact fields that differ."""
    by = {r["cid"]: r for r in rows}
    me = next(c for c in calls if c["cid"] == cid)
    pool = [c for c in calls
            if c["asset"] == me["asset"] and c["phase_dec"] == me["phase_dec"]
            and c["call"] == "SKIP"]
    if not pool:
        return ""
    near = min(pool, key=lambda c: (abs(c["sec"] - me["sec"]), c["cid"]))
    a, b = by[cid], by[near["cid"]]
    diffs = []
    if near["cls_gate"] != me["cls_gate"]:
        diffs.append("candidate class %s vs %s (the CLASS gate)"
                     % (b.get("cls"), a.get("cls")))
    for k in D.TERMS:
        if near[k] != me[k]:
            diffs.append("%s (%s)" % (k, {
                "T1": "S8 60s book life n=%s/%s vol=%s/%s",
                "T2": "S3 runway to the binding close %s/%s s",
                "T3": "S3 trade-side extreme age %s/%s s",
                "T4": "S8 5m sflow %s/%s on vol %s/%s",
                "T5": "S8 5m vol %s/%s"}[k] % (
                    (b.get("f60_n"), a.get("f60_n"), b.get("f60_vol"),
                     a.get("f60_vol")) if k == "T1" else
                    (b.get("runway_phase"), a.get("runway_phase")) if k == "T2"
                    else (b.get("extreme_age_trade_side"),
                          a.get("extreme_age_trade_side")) if k == "T3"
                    else (b.get("f5m_sflow"), a.get("f5m_sflow"),
                          b.get("f5m_vol"), a.get("f5m_vol")) if k == "T4"
                    else (b.get("f5m_vol"), a.get("f5m_vol")))))
    if near["vetoes"] and not me["vetoes"]:
        diffs.append("V2 fuel-map veto fires on the pair and not on the seat")
    if not diffs:
        diffs.append("NOTHING IN THE RULE — the pair is admitted-equivalent; "
                     "the difference is %d seconds and the side (%s vs %s), "
                     "and under CC-M2-10.3 seating the earlier row spends the "
                     "seat however much better the later one looks"
                     % (abs(near["sec"] - me["sec"]), near["side"], me["side"]))
    return ("MINIMAL PAIR: %s (%s, same asset+phase, %+ds, %s) — SKIP. "
            "EXACT DIFFERENCE: %s."
            % (near["cid"], near["clock"], near["sec"] - me["sec"],
               near["side"], "; ".join(diffs)))


def premortem(cid, calls, rows, cell_pm=None):
    """Auto-logged pre-mortem per TAKE (CC-M2-5.4), naming measurable fields."""
    by = {r["cid"]: r for r in rows}
    c = next(x for x in calls if x["cid"] == cid)
    r = by[cid]
    m, src = m_hat(r)
    bits = []
    bits.append("PRE-MORTEM (auto-logged before any outcome exists, CC-M2-5.4)")
    bits.append("THE DEATH MECHANISM I EXPECT: the %s seat is entered %s on a "
                "%s row whose magnitude reading is %s and whose runway to the "
                "binding %s close is %ss."
                % ("/".join((c["asset"], c["phase_dec"])), c["side"], c["cls"],
                   ("$%.0f (%s)" % (m, src)) if m else "unavailable",
                   c["phase_dec"], r.get("runway_phase")))
    rv = D.F(r, "rv1800")
    q = D.F(r, "q50")
    if rv is not None and q:
        bits.append("MEASURABLE NOW: S9 rv1800=%s against q50=$%s — if the "
                    "realised vol that made this candidate has already been "
                    "spent, the $1,000 bar has to come from range that does "
                    "not exist (P034: rv is high AFTER a move, not before)."
                    % (r.get("rv1800"), r.get("q50")))
    elif rv is not None:
        bits.append("MEASURABLE NOW: S9 rv1800=%s with fvol REFUSED on this "
                    "asset (D23), so the expected-move ladder cannot be read "
                    "at all — the feasibility half of this call is blind."
                    % r.get("rv1800"))
    en, rp = r.get("ext_needed"), r.get("room_phase")
    if en not in (None, "", "."):
        bits.append("THE ARITHMETIC I AM DELIBERATELY NOT TRADING: S3 "
                    "ext_needed=$%s against room_phase=$%s — read and not "
                    "traded, because the capacity family is an anti-signal "
                    "exactly when the range expands (P017/P014, defect D22)."
                    % (en, rp))
    ta, tb, pt = r.get("trapped_above"), r.get("trapped_below"), r.get("phase_total")
    bits.append("THE TRIGGER THAT WOULD SAY I WAS WRONG: a print through the "
                "%s-phase %s (%s, %ss old at decision) with S8's fuel map "
                "still %s above / %s below on %s — that is the fuel-map "
                "overhang V2 refuses, arriving after the fact."
                % (c["phase_dec"],
                   "low" if c["side"] == "LONG" else "high",
                   r.get("phase_L") if c["side"] == "LONG" else r.get("phase_H"),
                   r.get("extreme_age_trade_side"), ta, tb, pt))
    if cell_pm:
        bits.append(cell_pm)
    return " ".join(bits)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--index", required=True)
    p.add_argument("--day", type=int, required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    with open(a.index) as fh:
        rows = list(csv.DictReader([ln for ln in fh if not ln.startswith("#")],
                                   delimiter="\t"))
    calls = call_day(rows, a.day)
    cols = (["cid", "call", "conf", "grade_why", "n_terms"] + list(D.TERMS)
            + ["cls_gate", "core", "vetoes", "asset", "phase_dec", "clock",
               "sec", "side", "cls", "version", "primary", "against"])
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter="\t",
                           extrasaction="ignore")
        w.writeheader()
        for c in calls:
            w.writerow(c)
    n = sum(1 for c in calls if c["call"] == "TAKE")
    print("e1blind_policy day %d (%s): %d rows, %d TAKE -> %s"
          % (a.day, version_for(a.day)[1], len(calls), n, a.out))
    for k, cid in sorted(seats(calls).items()):
        print("   SEAT %-12s %s" % ("/".join(k), cid))


if __name__ == "__main__":
    sys.exit(main())
