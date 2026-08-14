#!/usr/bin/python3
"""E1 STUDY DAY 2 — the reader's committed triage policy, made executable.

Successor to `e1d1_policy.py` (FROZEN as day 2's yesterday-policy baseline,
CC-M2-8.2).  It is NOT a mechanical baseline: it is the reader's own decision
rule for 2021-07-02, written down so 935 day-complete calls are reproducible
and so the RULE, not just the calls, is the object a census can attack.

STRICT CAUSALITY DISCIPLINE (new this day, and a protocol hazard worth naming):
the triage index is a table of the WHOLE day, so scanning it necessarily shows
rows from later decision seconds.  This policy is therefore written as a PURE
FUNCTION OF ONE ROW — no candidate's call may read another candidate's fields,
and the same rule is imposed on the discretionary deep reads (a deep read opens
that candidate's own BLIND sheet and nothing else).

WHAT CHANGED FROM e1d1_policy.py, AND WHY (every change is an E1D1 finding
made executable; ERA_NOTES_E1 §11-§14 + E1_POSTMORTEMS §2-§3)

  T1 PARTICIPATION   unchanged.   S8 60s n>=5 and vol>=10 (P004: blocked 341 of
                     1,039 on day 1, zero winners lost).
  T2 COST            unchanged.   S13 spread_at_decision <= 1.25x era median
                     (P005).
  T3 CAPACITY        unchanged.   P017 RANGE_EXTENSION_ARITHMETIC: the $1,000
                     bar needs <= $450 of NEW range beyond the phase extreme,
                     and the phase is >= 300s old.  Kept at 450 although its
                     day-1 sole-blocked pool was POSITIVE (+$1,217, 0 winners):
                     it is doing MAE work, which is what it was written for.
  T4 RUNWAY          unchanged.   S3 runway to the binding exit >= 20,000s
                     (P002/P003).
  T5 FLOW CONCORD    P015 + AN EXECUTABLE SCOPE EXCEPTION.  The concordance
                     requirement stands (day-1 blocked pool -$229.48, founding
                     case HG-20210701-049049-L a -$930 wall-out with perfect
                     geometry).  What is NEW is that day 1's single manual
                     override — SI-20210701-054339-S, +$1,682.50, the joint
                     best call of the day — is now a TERM instead of a mood:
                     concordance is WAIVED for a first test of a level that is
                     resisting the trade (P006 FIRST_TEST_CONFLUENCE).  The
                     waiver is deliberately tight (tc<=1, |d$|<=60 and on the
                     resisting side, >=2 families at that price, trade-side
                     phase extreme <= 300s old) because a loose form of it
                     (|d$|<=100, any family, age<=600) admits 7 candidates on
                     this day, five of them HG entries whose phase flow is
                     0.3% of phase volume — i.e. it would have re-opened
                     exactly the pool P015 was born to close.
  T6 ANTI-CHASE      REPLACES the day-1 momentum term, which was VALUE-
                     DESTROYING (17 sole-blocked candidates averaged +$1,438
                     with 8 D-021 winners; E1D1-F1).  The day-1 error was to
                     require the slope to be signed WITH the trade: at a fresh
                     extreme the slope MUST point the wrong way, because it is
                     measuring the spike INTO the extreme.  The finding was
                     "T6 and T7 are not independent"; the repair is therefore
                     not deletion but CONDITIONING.  The term now fires only
                     where the two are not entangled: if the trade-side phase
                     extreme is STALE (> 600s) AND the 5-minute drift is
                     against the trade by more than one 60-second realised-vol
                     unit (S5 mid_slope_$/min(T-1m) vs S9 rv_nowcast w60, same
                     $/min units — see the FIELD NOTE below), price is
                     travelling toward a stale extreme and the entry is a
                     chase into a level that is about to be re-made.
                     On this day it sole-blocks exactly ONE candidate, so it
                     is nearly free and its test is sharp.
  T7 FRESHNESS       WIDENED 900s -> 3,600s (E1D1-F2: all three candidates
                     sole-blocked by the 900s window were D-021 winners, mean
                     +$1,426; HG-20210701-057109-S at 1,321s paid +$1,545 with
                     mae $43.75).  Briefing D1 answered YES for continuation
                     shorts; 3,600s is the widening the day-1 evidence
                     supports, not an abolition — a phase extreme older than an
                     hour is no longer the object being traded.
  T8 VOL NOT DEAD    unchanged.   S9 rv1800/rv60 < 8 (P013 marker, demoted but
                     retained: it blocked 129 on day 1 and cost 4 winners,
                     roughly break-even, and it is two numbers).
  T9 TWO-STREAM      NEW.  P011/A3 in the only form P011 says is valid — as a
     OPPOSITION      REFUSAL, and at the horizon where it is measurable.  Refuse
                     when BOTH streams point against the trade at magnitude:
                     S8 60s sflow opposed with |sflow|/vol >= 10% on >= 20
                     contracts, AND S5 mid_slope(T-1m) opposed — the flow
                     window and the price window are deliberately matched.  Born on this
                     day's SI-20210702-052509-S, where S8 phase sflow is
                     concordant (-463/6505 = 7.1% sell) but the phase's
                     imbalance PREDATES the 12:30Z Employment Situation
                     (S8 30m sflow = -2 on 3,782 — flat; 60s = +70 on 424 =
                     16.5% BUY) while S5 slope is +100/min and accelerating:
                     P015's concordance is being satisfied by a market that no
                     longer exists.  DELIBERATELY NOT the simpler "last-minute
                     flow opposed" veto: that form was tested against day-1
                     history first and it would have REFUSED HG-20210701-
                     055858-S (60s sflow +31 on 181 = 17.1% against the short),
                     the joint-best call of day 1 at +$1,682.50 — the price
                     stream had already rolled over there (slope -87.5, accel
                     -92.5), so only one stream opposed.  Requiring BOTH costs
                     nothing on day 1 (it blocks 0 of that day's 10 eight-term
                     takes; over all 1,039 it blocks 146 with mean -$29.27 vs
                     the day's -$8.01 and 8 of 48 winners, i.e. neutral in the
                     population and free in the pool that matters).

DELIBERATELY *NOT* ENCODED: ERA_NOTES §10's "all 48 winners are NY SHORTS".
That is one session.  Hard-coding side/phase would make day 2 unable to
falsify it.  The rule stays direction-blind and phase-blind, and where it takes
is the test.

ONE-POSITION RULE (D-046): only the EARLIEST qualifying candidate of a cluster
(same asset+side within 900s) can be entered; later members are committed as
seats and forfeited by the replay, exactly as on day 1 (kept identical so the
two days' ledgers are comparable).

FIELD NOTE (CC-M2-9.3, mid-round correction).  S5 prints THREE slopes on one
line — sl_15, sl_5, sl_1 — and the V1 triage extractor took the LAST column and
called it `slope5m`; it was the ONE-MINUTE slope.  The extractor now names all
three (triage_index.py), and every slope term above reads `slope1m` EXPLICITLY.
The choice is not a patch of convenience, it was re-tested on day 1's 1,039
already-unblinded outcomes with the corrected fields:
  * marginal winner rate, slope signed WITH the trade vs AGAINST (base 4.62%):
    1m 7.1% vs 2.9%; 5m 4.4% vs 5.9%; 15m 3.3% vs 6.5%.  The ONE-MINUTE slope
    is the horizon that carries the sign; the 15-minute one carries it
    backwards.
  * T6 ANTI-CHASE blocks, day 1: on 1m, 101 candidates, mean -$45.90, winner
    rate 4.0% (below base) — mildly value-positive and winner-cheap; on the
    true 5m it blocks ONE candidate, i.e. it does not exist at that horizon.
  * T9 TWO-STREAM blocks, day 1: on 1m, 146 candidates, mean -$29.27, winner
    rate 5.5%; on the true 5m, 81 candidates, mean -$59.55 but winner rate
    8.6% — nearly double the base rate, i.e. the 5m arm buys its better mean
    by throwing away winners.  The 1m arm is the right one.
Day 1's own T6 finding is DOWNGRADED to unresolved by CC-M2-9.3.  What survives
the correction is that the day-1 term was `slope1m AND accel both signed with
the trade`, and its sole-blocking ablation (17 candidates, +$1,438, 8 winners)
was computed on exactly those fields, so the ablation itself still stands even
though its label was wrong.  It is carried as the `d1_T6` shadow column, and
the TRUE 5-minute forms are carried as `sl5_with` so day 2's unblinding can
settle the horizon question with two days instead of one.

CENSUS NOTE (CC-M2-9.1, arrived mid-round).  P001/P016 are now graded
CONCENTRATOR(feature): a winner concentrator with NO positive edge on the
deployed-exit adoption metric (P016 beta -$95, p=.07).  This rule shares terms
with P016 and must therefore be read as the reader's own conjunction standing
on the fields it names, never on P016's authority — and its expected outcome
should be read down accordingly.

SHADOW COLUMNS (not binding, for the post-mortem): `d1_T6` / `d1_T7` record
what YESTERDAY's frozen terms would have said, so the unblinding can measure
whether dropping/widening them was right on a second day.
"""
import argparse
import csv
import os
import sys

SPREAD_MED = {"SI": 25.0, "HG": 25.0, "NKD": 50.0}
CLUSTER_S = 900
EXT_MAX = 450.0            # T3
PHASE_AGE_MIN = 300        # T3
RUNWAY_MIN = 20000         # T4
SFLOW_FRAC = 0.05          # T5
PHASE_VOL_MIN = 200        # T5
FT_D_MAX = 60.0            # T5 waiver (P006)
FT_AGE_MAX = 300           # T5 waiver
STALE_S = 600              # T6
FRESH_MAX = 3600           # T7
RV_COLLAPSE = 8.0          # T8
OPP_FRAC = 0.10            # T9
OPP_VOL_MIN = 20           # T9


def F(r, k):
    try:
        return float(r[k])
    except Exception:
        return None


def terms(r):
    """{name: bool} for T1..T8 — a pure function of ONE index row."""
    side = 1 if r["side"] == "LONG" else -1
    t = {}

    f60n, f60v = F(r, "f60_n"), F(r, "f60_vol")
    t["T1"] = bool(f60n is not None and f60n >= 5 and f60v is not None
                   and f60v >= 10)

    sp = F(r, "spread_dec")
    t["T2"] = bool(sp is not None
                   and sp <= 1.25 * SPREAD_MED.get(r["asset"], 25.0))

    ext = F(r, "ext_needed")
    phs = [x for x in (F(r, "phase_H_sec"), F(r, "phase_L_sec"))
           if x is not None]
    ph_age = (F(r, "sec") or 0) - (min(phs) if phs else 0)
    t["T3"] = bool(ext is not None and ext <= EXT_MAX
                   and ph_age >= PHASE_AGE_MIN)

    runway = F(r, "runway_phase")
    t["T4"] = bool(runway is not None and runway >= RUNWAY_MIN)

    # T5: scale-neutral imbalance FRACTION (never a contract count — the three
    # assets' multipliers differ 5x), plus the P006 first-test waiver.
    fph, tot = F(r, "fph_sflow"), F(r, "fph_vol")
    conc = bool(fph is not None and tot and tot >= PHASE_VOL_MIN
                and fph * side > 0 and abs(fph) / tot >= SFLOW_FRAC)
    age = F(r, "extreme_age_trade_side")
    tc, nd, nc = F(r, "min_tc_near"), F(r, "near_d"), F(r, "n_conf_max")
    ft = bool(tc is not None and tc <= 1
              and nd is not None and abs(nd) <= FT_D_MAX and nd * side <= 0
              and nc is not None and nc >= 2
              and age is not None and 0 <= age <= FT_AGE_MAX)
    t["T5"] = bool(conc or ft)

    sl, rv60 = F(r, "slope1m"), F(r, "rv60")
    t["T6"] = not bool(age is not None and age > STALE_S and sl is not None
                       and rv60 and sl * side < -1.0 * rv60)

    t["T7"] = bool(age is not None and 0 <= age <= FRESH_MAX)

    rvc = F(r, "rv_collapse")
    t["T8"] = bool(rvc is not None and rvc < RV_COLLAPSE)

    s60, v60 = F(r, "f60_sflow"), F(r, "f60_vol")
    t["T9"] = not bool(s60 is not None and v60 and v60 >= OPP_VOL_MIN
                       and s60 * side < 0 and abs(s60) / v60 >= OPP_FRAC
                       and sl is not None and sl * side < 0)

    t["_conc"], t["_ft"] = conc, ft
    return t


def shadow(r):
    """Yesterday's frozen T6/T7, recorded but NOT binding."""
    side = 1 if r["side"] == "LONG" else -1
    sl, ac = F(r, "slope1m"), F(r, "accel")
    age = F(r, "extreme_age_trade_side")
    sl5 = F(r, "slope5m")
    return {"d1_T6": int(bool(sl is not None and ac is not None
                              and sl * side > 0 and ac * side > 0)),
            "d1_T7": int(bool(age is not None and 0 <= age <= 900)),
            "sl5_with": int(bool(sl5 is not None and sl5 * side > 0))}


def grade(r, t):
    """VALUE band (A >= $1,500 / B $700-1,500 / C < $700).

    Day 1's grade was monotone TAKE-vs-SKIP but INVERTED inside the TAKEs
    (A $1,523 vs B $1,633, n=9/2 — ERA_NOTES §19.3).  This form drops the
    ladder/coverage markers, which are REFUSED on every SI sheet in this era
    and so could never grade an SI take at all, and uses five markers that
    exist on every sheet and are value-facing.
    """
    side = 1 if r["side"] == "LONG" else -1
    room, ext = F(r, "room_phase"), F(r, "ext_needed")
    fph, tot = F(r, "fph_sflow"), F(r, "fph_vol")
    age, rvc = F(r, "extreme_age_trade_side"), F(r, "rv_collapse")
    f60v = F(r, "f60_vol")
    strong = 0
    if ext is not None and ext <= 0.0:
        strong += 1                       # the bar lives entirely inside range
    if room is not None and room >= 1400:
        strong += 1                       # a $1,500 A-class target is in range
    if fph is not None and tot and fph * side > 0 and abs(fph) / tot >= 0.06:
        strong += 1
    if age is not None and age <= 300:
        strong += 1
    if rvc is not None and rvc <= 4.0 and f60v is not None and f60v >= 100:
        strong += 1                       # live vol AND a live minute
    n = sum(1 for k in ("T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9")
            if t[k])
    if n == 9:
        return "A" if strong >= 4 else ("B" if strong >= 2 else "C")
    return "B" if n >= 7 else "C"


def evidence(r, t):
    """One line naming a SHEET LINE (section+field+value) — never a vibe."""
    side = r["side"]
    if not t["T1"]:
        return ("primary: S8 60s n=%s vol=%s — no transacting counterparty in "
                "the last minute (P004 DEAD_BOOK_VETO)"
                % (r["f60_n"], r["f60_vol"]))
    if not t["T2"]:
        return ("primary: S13 spread_at_decision=$%s vs %s era spread_med $%.0f "
                "— the entrant pays a liquidity fact, not a transient quote "
                "(P005 ENTRY_SPREAD_TAX)"
                % (r["spread_dec"], r["asset"], SPREAD_MED.get(r["asset"], 25.)))
    if not t["T3"]:
        return ("primary: S3 phase %s H=%s L=%s vs S13 entry mid=%s — room "
                "inside the phase range is $%s so the $1,000 bar needs $%s of "
                "NEW range beyond the phase extreme (P017 RANGE_EXTENSION)"
                % (r["phase_dec"], r["phase_H"], r["phase_L"], r["mid"],
                   r["room_phase"], r["ext_needed"]))
    if not t["T4"]:
        return ("primary: S3 runway to_phase_close=%ss — too little time to "
                "the binding exit second (P002 A1_EXIT_SECOND_VETO)"
                % r["runway_phase"])
    if not t["T5"]:
        return ("primary: S8 phase sflow=%s on %s contracts vs side=%s — the "
                "phase's cumulative order flow is not on this trade's side at "
                "magnitude, and S4 shows no first test of a resisting level "
                "(min_tc_near=%s d$=%s n_fam=%s) to waive it "
                "(P015 PHASE_FLOW_CONCORDANCE fails)"
                % (r["fph_sflow"], r["fph_vol"], side, r["min_tc_near"],
                   r["near_d"], r["n_conf_max"]))
    if not t["T6"]:
        return ("primary: S3 phase extreme on the trade's side is %ss old "
                "while S5 mid_slope_$/min(T-5m)=%s runs AGAINST the trade at "
                "more than one S9 rv_nowcast w60 unit ($%s/min) — price is "
                "travelling toward a stale extreme, so this entry is a chase "
                "into a level that is about to be re-made (T6 ANTI-CHASE)"
                % (r["extreme_age_trade_side"], r["slope1m"], r["rv60"]))
    if not t["T7"]:
        return ("primary: S3 phase %s extreme on the trade's side is %ss old — "
                "past the 3,600s window there is no rejection object left to "
                "trade (A5 early-in-sequence; widened from 900s by E1D1-F2)"
                % (r["phase_dec"], r["extreme_age_trade_side"]))
    if not t["T9"]:
        return ("primary: S8 60s sflow=%s on %s contracts AND S5 "
                "mid_slope_$/min(T-1m)=%s BOTH point against this %s — two "
                "streams agreeing at magnitude against the trade, while S8's "
                "concordant phase sflow=%s/%s is inherited from before the "
                "current impulse (T9 TWO-STREAM OPPOSITION, P011 as a refusal)"
                % (r["f60_sflow"], r["f60_vol"], r["slope1m"], side,
                   r["fph_sflow"], r["fph_vol"]))
    if not t["T8"]:
        return ("primary: S9 rv_nowcast w1800/w60=%s — the vol that produced "
                "the move has already collapsed; the leg is ending "
                "(P013 WALL_BINDS_ON_PORT marker)" % r["rv_collapse"])
    tag = ("P006 first-test waiver of P015" if (t["_ft"] and not t["_conc"])
           else "P015 concordant")
    return ("primary: S3 room inside the phase %s range=$%s (H=%s L=%s vs S13 "
            "entry mid=%s) so the $1,000 bar needs only $%s of new range "
            "[P017]; S3 runway=%ss to a %s exit; S8 60s n=%s vol=%s is a live "
            "book [P004]; S8 phase sflow=%s on %s contracts (%s); S3 "
            "trade-side extreme %ss old; S9 rv1800/rv60=%s"
            % (r["phase_dec"], r["room_phase"], r["phase_H"], r["phase_L"],
               r["mid"], r["ext_needed"], r["runway_phase"],
               "session-close" if r["exit_is_sess"] == "1" else "phase-close",
               r["f60_n"], r["f60_vol"], r["fph_sflow"], r["fph_vol"], tag,
               r["extreme_age_trade_side"], r["rv_collapse"]))


def against(r, t):
    bits = []
    for k in ("T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9"):
        if not t[k]:
            bits.append(k)
    side = 1 if r["side"] == "LONG" else -1
    thru_n, tb, ta = F(r, "thru_n"), F(r, "thru_bid"), F(r, "thru_ask")
    if thru_n and tb is not None and ta is not None:
        adverse, withit = (ta, tb) if side < 0 else (tb, ta)
        if adverse > 1.5 * max(withit, 1):
            bits.append("S8 through_book_600s adverse side %d vs %d (recent "
                        "aggression is against this trade)" % (adverse, withit))
    if r["P013"] == "1":
        bits.append("S9 rv1800/rv60=%s (P013 marker)" % r["rv_collapse"])
    if r["ladder_pos"] == ".":
        bits.append("S9 ladder_position REFUSED (fvol %s) — no ladder or "
                    "COVERAGE term is evaluable on this sheet, the A1 test is "
                    "P017 arithmetic only" % r["fvol_source"])
    d = shadow(r)
    if not d["d1_T6"]:
        bits.append("yesterday's frozen T6 (S5 slope+accel signed with the "
                    "trade: %s/%s) would have REFUSED this — dropped by "
                    "E1D1-F1, recorded as a shadow test"
                    % (r["slope1m"], r["accel"]))
    if not d["d1_T7"]:
        bits.append("yesterday's frozen T7 (extreme <= 900s: %ss) would have "
                    "REFUSED this — widened by E1D1-F2"
                    % r["extreme_age_trade_side"])
    return "against: " + ("; ".join(bits) if bits else "none named")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    # R26: the CANONICAL reader, never `readlines()[1:]`.
    # This file skipped exactly ONE comment line.  The V1 indices it was
    # written against carry 1; every current-format index carries 2
    # (`triage_index.py:788-790`) and an as-of prefix view carries 3
    # (`:792-794`), so re-running it against a HEAD-format index consumed the
    # version stamp as the header row and died at `r["cid"]` — which is why
    # the committed E1 study rows were not re-runnable from HEAD.
    # `read_index` skips every `#` line however many there are, returns the
    # header stamps, and fills BOTH spellings of every renamed column.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import triage_index as TI                                     # noqa: E402
    rows, _stamps = TI.read_index(a.index)
    if not rows or "cid" not in rows[0]:
        raise SystemExit("index %s: no `cid` column after the canonical read — "
                         "refusing rather than parsing a stamp as a header "
                         "(R26)" % a.index)
    rows.sort(key=lambda r: (int(r["sec"]), r["asset"], r["cid"]))

    held, out = {}, []
    for r in rows:
        t = terms(r)
        ok = all(t[k] for k in ("T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8",
                                "T9"))
        call, dup = ("TAKE" if ok else "SKIP"), None
        if ok:
            key = (r["asset"], r["side"])
            prev = held.get(key)
            if prev and int(r["sec"]) - prev[1] <= CLUSTER_S:
                call, dup = "SKIP", prev[0]
            else:
                held[key] = (r["cid"], int(r["sec"]))
        d = shadow(r)
        out.append(dict(r, call=call, conf=grade(r, t), primary=evidence(r, t),
                        against=against(r, t),
                        terms="".join(k[1] for k in
                                      ("T1", "T2", "T3", "T4", "T5", "T6",
                                       "T7", "T8", "T9") if t[k]),
                        n_terms=sum(1 for k in ("T1", "T2", "T3", "T4", "T5",
                                                "T6", "T7", "T8", "T9")
                                    if t[k]),
                        dup_of=dup or "", waiver=int(t["_ft"] and not t["_conc"]),
                        d1_T6=d["d1_T6"], d1_T7=d["d1_T7"],
                        sl5_with=d["sl5_with"]))

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    cols = ["cid", "call", "conf", "primary", "against", "terms", "n_terms",
            "dup_of", "waiver", "d1_T6", "d1_T7", "sl5_with", "asset", "phase_dec", "clock",
            "cls", "seat_score"]
    with open(a.out, "w") as fh:
        fh.write("\t".join(cols) + "\n")
        for r in out:
            fh.write("\t".join(str(r[c]) for c in cols) + "\n")
    n_take = sum(1 for r in out if r["call"] == "TAKE")
    sys.stderr.write("%d rows, %d TAKE seats (%s)\n" % (len(out), n_take, a.out))
    for r in out:
        if r["call"] == "TAKE":
            sys.stderr.write("  TAKE %s %s %s %s %s waiver=%d\n"
                             % (r["conf"], r["cid"], r["phase_dec"], r["clock"],
                                r["cls"], r["waiver"]))


if __name__ == "__main__":
    main()
