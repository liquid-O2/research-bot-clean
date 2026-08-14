#!/usr/bin/python3
"""E1 STUDY DAY 3 — the reader's committed triage policy, made executable.

Successor to `e1d1_policy.py` and `e1d2_policy.py`, both of which are FROZEN as
mechanical baselines for this day (CC-M2-8.2).  As on the previous two days this
is NOT a mechanical baseline: it is the reader's own decision rule for
2021-07-05, written down so 644 day-complete calls are reproducible and so the
RULE, not just the calls, is what a census can attack.

STRICT CAUSALITY: a pure function of ONE triage-index row.  No candidate's call
reads another candidate's fields.  The index is built from BLIND sheets only.

=======================================================================
WHY THIS RULE IS NOT THE PREVIOUS RULE (the day-1 vs day-2 disagreement)
=======================================================================
Day 1 (2021-07-01) and day 2 (2021-07-02) agree on almost nothing: day 1's 48
D-021 winners are all SHORTS, day 2's 38 are all LONGS; day 1's capacity
arithmetic was an MAE filter, day 2's was an anti-signal; day 1's phase-flow
concordance chose the right side, day 2's chose the wrong one.  The task set
for this day was to find the EX-ANTE FIELDS that separate the two.  What the
two already-unblinded sessions (n=1,974 rows, lawful under CC-M2-9.4) actually
say:

 (1) THE CANDIDATE SEPARATOR THAT IS REAL BUT UNUSABLE AS A COMPASS.  A
     scheduled release inside the session (S12 `last_scheduled` present, or
     `next_scheduled` countdown < S3 runway to session close) separates the two
     days perfectly: 0/1,039 rows on day 1, 935/935 on day 2.  Conditional on
     it, P015 PHASE_FLOW_CONCORDANCE flips sign exactly —
        event=0: flow WITH the trade  n=327  mean +$262  win 8.9%
                 flow AGAINST         n=331  mean -$262  win 0.0%
        event=1: flow WITH            n=232  mean -$552  win 0.0%
                 flow AGAINST         n=239  mean +$542  win 15.9%
     That is the cleanest single bit in the round.  It is ALSO perfectly
     collinear with the day, so it is one observation of a mechanism, not a
     measurement — and the natural repair ("on event days take the direction
     from the post-event 30m window") DOES NOT WORK: on day 2 every flow
     horizon was anti-predictive (30m WITH: mean -$387, 0 winners).  A rule
     built on it fires 31 times on day 2 and loses $737 a trade.  So the
     separator is recorded as a finding and is NOT the direction source.
 (2) WHY EVERY FLOW-CONCORDANCE RULE KEEPS INVERTING.  Pooled over both days
     the signed aggressive-flow imbalance is CONTRARIAN at every horizon:
     5m WITH the trade -> win 1.9%; 5m AGAINST -> win 8.4%.  Aggression is who
     is HITTING; it is not who is WINNING.  The stream that is directional is
     the one that measures who CLEARED LEVELS: S8 `through_book_600s` on the
     trade's side -> win 10.9% vs 2.2% against.
 (3) THE CONJUNCTION THAT SURVIVES BOTH DAYS.  Opposed 5-minute aggression AND
     through-book prints on the trade's side — i.e. the aggression is being
     ABSORBED (briefing P007's mechanism, promoted from a veto to an entry) —
     pays on BOTH days with opposite session directions:
        day 1: n=23 mean +$621 win 56.5%   day 2: n=45 mean +$615 win 57.8%
     against a 4.4% base rate, over 10 and 9 distinct 15-minute clusters.
     Neither component alone is stable (5m opposed alone: +$21 / +$504;
     through-book alone: +$331 / +$118).
 (4) THE SEAT FACT THAT IS MECHANICAL, NOT MYSTICAL.  All 86 winners of both
     days sit in rows whose S13 `exit_default` phase close EQUALS the session
     close; the other 863 rows produced ZERO winners.  ERA_NOTES §20's "86/86
     winners are NY" is that fact wearing a phase label: NY is simply the phase
     whose exit is the session close, i.e. the only phase that gives the hold
     enough runway to reach the $1,000 bar.  CC-M2-10.3 seats scoring at phase
     close, so TOKYO and LONDON seats are cheap — and on this evidence they are
     also worthless, so the rule declines them rather than spending them.
 (5) RANGE MATURITY.  No winner in either day arrives before the session has
     realised ~50% of `range_hat`: 0 winners in the 401 rows with S2
     `% of range_hat` < 45, versus 71 of 86 between 45% and 75%.

=======================================================================
THE RULE (9 terms; every threshold is measured on the two prior sessions)
=======================================================================
 T1 SEAT SCOPE      S13 exit_default: phase_close == session_close.
                    (86/86 winners; 0 winners in 863 rows without it.)
 T2 LIVE BOOK       S8 60s n >= 5 and 60s vol >= 10  (P004, unchanged).
 T3 RANGE MATURITY  S2 `% of range_hat` >= 45  (0/401 winners below).
 T4 ABSORPTION FUEL S8 5m sflow OPPOSED to the trade at >= 5% of 5m volume,
                    on >= 500 contracts.  The volume floor is the "at
                    magnitude" half of briefing A3 and it is what removes the
                    thin early shorts that cost day 2 its seat (5m vol 230-382
                    on every one of them).
 T5 THROUGH-BOOK    S8 through_book_600s n >= 5 with a strict majority of the
                    prints on the trade's side (>B for a SHORT, >A for a LONG).
 T6 MOMENT OF TURN  S8 60s sflow NOT opposed at >= 10% of 60s volume AND
                    S5 mid_slope_$/min(T-1m) signed WITH the trade.  This is
                    P018 TWO-STREAM OPPOSITION read as a confirmation instead
                    of a veto: the absorbed aggression must have STOPPED in the
                    last minute and the price stream must have turned.
 T7 FRESHNESS       S3 trade-side phase extreme <= 3,600s old (E1D1-F2's
                    widened window, unchanged from day 2).
 T8 VOL LIVE        S9 rv_nowcast w1800/w60 < 8 (P013 marker, unchanged).
 T9 SPREAD TAX      S13 spread_at_decision <= 1.25x the era median (P005).

DELIBERATELY DROPPED, each with its receipt:
  * P017 / T3-capacity (range-extension arithmetic).  ERA_NOTES §21: it is a
    mean-reversion prior wearing a capacity filter's clothes.  On the two days
    pooled its "PASS" pool has a WORSE mean than its "BLOCK" pool.
  * P015 / phase-flow concordance.  Sign-flips with the event flag (above); the
    5-minute horizon in T4 carries the same information with the sign that
    survives both days.
  * P019 ANTI-CHASE.  Inside this conjunction it sole-blocks WINNERS on both
    days (day 1: 2 winners at mean +$1,039; day 2: 1 winner at +$1,258).
  * The side and phase terms of ERA_NOTES §10/§20 — never encoded (§20 struck
    the side term itself one day after it was written).

BACKTEST OF THIS EXACT RULE ON THE TWO ALREADY-UNBLINDED DAYS (not a forecast;
the thresholds were chosen on these days, so this is in-sample and is quoted as
provenance, not as evidence):
    day 1: 7 takes, 7 winners, mean +$1,416, 0 walled, replay +$2,777 (0.488)
    day 2: 4 takes, 2 winners, mean +$601,   0 walled, replay +$1,477 (0.324)
  versus the reader's actual +$3,003 (day 1, window-tainted) and -$1,953
  (day 2), and versus the best mechanical baselines' +$623 and +$445.

THE GRADE (CC-M2-10.5: A|B|C rebuilt on RULE-INDEPENDENT evidence).
Day 1's and day 2's grades counted how many of the reader's own terms were at
their strong setting, which is why they were anti-calibrated: they measured the
rule's confidence, not the candidate's value.  This grade uses two fields the
rule never reads — S9 `rv_nowcast w1800` and S3 `runway` — to estimate how far
price can travel before the binding exit:
    sigma_to_exit = rv1800 * sqrt(runway_to_binding_exit / 1800)
    A >= $2,500 ; B $1,200-2,500 ; C < $1,200
On the 1,111 NY rows of the two prior days this is monotone in both directions:
A win 19.7% / mean|cert| $889, B 8.4% / $781, C 0.9% / $383.  It is a
magnitude-feasibility estimate, never a direction confidence.

THE DAY (2021-07-05) — what the blind table says before any call is made:
  * NO scheduled release anywhere: S12 `next_scheduled` is CPI, 7.8-8.6 DAYS
    out, on all 644 sheets, and no sheet carries a `last_scheduled` line.  This
    session is day-1-like on the separator of (1).
  * fvol is REFUSED on all 644 sheets (`fvol_source=ATR14_RAW_FILL`), so every
    COVERAGE / ladder_position form of A1 is structurally unevaluable — a
    whole-day repeat of ERA_NOTES §16, now on three assets at once.
  * The tape is THIN and ends early: the last candidate of the session is at
    18:59 clock (16:59Z) against a nominal 22:59:59 session close, and SI's NY
    60-second median volume is 21 contracts against 79 (day 1) and 135 (day 2).
    2021-07-05 is the US Independence Day observed holiday.  The sheet has no
    holiday field; the thinness is visible only in S8/S5 participation.
  * The regime flag is PER ASSET, not per day: SI is INSIDE for all 207 of its
    candidates (max 51.2% of range_hat), NKD is AT_RANGE, and HG is EXPANDED on
    162 of 240 (up to 133.6%).  One calendar day, three regimes.
"""
import argparse
import csv
import math
import os
import sys

SPREAD_MED = {"SI": 25.0, "HG": 25.0, "NKD": 50.0}
PCT_RANGE_MIN = 45.0        # T3
F5_FRAC = 0.05              # T4
F5_VOL_MIN = 500            # T4
THRU_N_MIN = 5              # T5
F60_OPP_FRAC = 0.10         # T6
F60_VOL_MIN = 20            # T6
FRESH_MAX = 3600            # T7
RV_COLLAPSE = 8.0           # T8
SPREAD_MULT = 1.25          # T9
GRADE_A, GRADE_B = 2500.0, 1200.0

TERMS = ("T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9")


def F(r, k):
    try:
        return float(r[k])
    except Exception:
        return None


def sgn(v):
    return 0 if v is None else (1 if v > 0 else (-1 if v < 0 else 0))


def terms(r):
    """{name: bool} for T1..T9 — a pure function of ONE index row."""
    side = 1 if r["side"] == "LONG" else -1
    t = {}

    t["T1"] = r.get("exit_is_sess") == "1"

    f60n, f60v = F(r, "f60_n"), F(r, "f60_vol")
    t["T2"] = bool(f60n is not None and f60n >= 5
                   and f60v is not None and f60v >= 10)

    pct = F(r, "pct_range_hat")
    t["T3"] = bool(pct is not None and pct >= PCT_RANGE_MIN)

    s5, v5 = F(r, "f5m_sflow"), F(r, "f5m_vol")
    t["T4"] = bool(s5 is not None and v5 and v5 >= F5_VOL_MIN
                   and abs(s5) / v5 >= F5_FRAC and sgn(s5) == -side)

    tb, ta, tn = F(r, "thru_bid"), F(r, "thru_ask"), F(r, "thru_n")
    t["T5"] = bool(tb is not None and ta is not None and tn and tn >= THRU_N_MIN
                   and (ta + tb) > 0
                   and ((ta if side > 0 else tb) / (ta + tb)) > 0.5)

    s60, sl = F(r, "f60_sflow"), F(r, "slope1m")
    still_opposed = bool(s60 is not None and f60v and f60v >= F60_VOL_MIN
                         and sgn(s60) == -side
                         and abs(s60) / f60v >= F60_OPP_FRAC)
    t["T6"] = bool((not still_opposed) and sl is not None and sl * side > 0)

    age = F(r, "extreme_age_trade_side")
    t["T7"] = bool(age is not None and 0 <= age <= FRESH_MAX)

    rvc = F(r, "rv_collapse")
    t["T8"] = bool(rvc is not None and rvc < RV_COLLAPSE)

    sp = F(r, "spread_dec")
    t["T9"] = bool(sp is not None
                   and sp <= SPREAD_MULT * SPREAD_MED.get(r["asset"], 25.0))
    return t


def sigma_to_exit(r):
    """RULE-INDEPENDENT value scale: how far price can travel before the exit."""
    rv, rw = F(r, "rv1800"), F(r, "runway_phase")
    if rv is None or rw is None:
        return None
    return rv * math.sqrt(max(rw, 1.0) / 1800.0)


def grade(r):
    s = sigma_to_exit(r)
    if s is None:
        return "C"
    return "A" if s >= GRADE_A else ("B" if s >= GRADE_B else "C")


def event_in_session(r):
    """S12: does a scheduled release fall inside THIS session? (the day-1 vs
    day-2 separator; recorded on every row, binding on none)."""
    la, nx, rw = F(r, "sched_last_age"), F(r, "sched_next_in"), F(r, "runway_sess")
    if la is not None:
        return 1
    if nx is not None and rw is not None and nx < rw:
        return 1
    return 0


def evidence(r, t):
    """One line naming SHEET LINES (section+field+value) — never a vibe."""
    side = r["side"]
    if not t["T1"]:
        return ("primary: S13 exit_default phase_close != session_close — the "
                "hold is truncated at the %s phase close, and across the two "
                "already-unblinded day-complete sessions ZERO of 863 such rows "
                "produced a D-021 winner while all 86 winners sat in "
                "session-close rows (T1 SEAT SCOPE; ERA_NOTES §20 restated as "
                "the exit fact it actually is)" % r["phase_dec"])
    if not t["T2"]:
        return ("primary: S8 60s n=%s vol=%s — no transacting counterparty in "
                "the last minute (P004 DEAD_BOOK_VETO)"
                % (r["f60_n"], r["f60_vol"]))
    if not t["T3"]:
        return ("primary: S2 range_so_far=$%s = %s%% of range_hat — the session "
                "has not yet delivered half of its own expected range, and 0 of "
                "401 such rows over the two prior day-complete sessions "
                "produced a D-021 winner (T3 RANGE MATURITY)"
                % (r["range_so_far"], r["pct_range_hat"]))
    if not t["T4"]:
        return ("primary: S8 5m sflow=%s on %s contracts — there is no opposed "
                "aggression at magnitude for this %s to absorb; the pooled "
                "two-day reading is that flow signed WITH the trade wins 1.9%% "
                "of the time and flow signed AGAINST it 8.4%% "
                "(T4 ABSORPTION FUEL, P007 promoted from veto to entry)"
                % (r["f5m_sflow"], r["f5m_vol"], side))
    if not t["T5"]:
        return ("primary: S8 through_book_600s n=%s thru_bid=%s thru_ask=%s — "
                "the prints that actually cleared levels are not on this "
                "trade's side; through-book direction is the only flow object "
                "that is directional on both prior days (win 10.9%% with vs "
                "2.2%% against) (T5 THROUGH-BOOK SIDE)"
                % (r["thru_n"], r["thru_bid"], r["thru_ask"]))
    if not t["T6"]:
        return ("primary: S8 60s sflow=%s on %s contracts with S5 "
                "mid_slope_$/min(T-1m)=%s — the opposed aggression has not "
                "stopped and/or the price stream has not turned, so the "
                "absorption is not complete at the decision second "
                "(T6 MOMENT OF TURN, P018 read as a confirmation)"
                % (r["f60_sflow"], r["f60_vol"], r["slope1m"]))
    if not t["T7"]:
        return ("primary: S3 phase %s extreme on the trade's side is %ss old — "
                "past the 3,600s window there is no rejection object left to "
                "trade (A5 early-in-sequence; E1D1-F2's widened form)"
                % (r["phase_dec"], r["extreme_age_trade_side"]))
    if not t["T8"]:
        return ("primary: S9 rv_nowcast w1800/w60=%s — the vol that produced "
                "the move has already collapsed (P013 marker)"
                % r["rv_collapse"])
    if not t["T9"]:
        return ("primary: S13 spread_at_decision=$%s vs %s era spread_med $%.0f "
                "— the entrant pays a liquidity fact, not a transient quote "
                "(P005 ENTRY_SPREAD_TAX)"
                % (r["spread_dec"], r["asset"],
                   SPREAD_MED.get(r["asset"], 25.0)))
    return ("primary: S8 5m sflow=%s on %s contracts is aggression OPPOSED to "
            "this %s at magnitude while S8 through_book_600s n=%s splits "
            "bid=%s/ask=%s on the trade's side — the hitters are being "
            "absorbed and the prints that cleared levels are mine [T4+T5, "
            "P007+A4]; S8 60s sflow=%s and S5 mid_slope(T-1m)=%s say the "
            "opposed aggression has stopped and the price stream has turned "
            "[T6]; S3 trade-side phase extreme %ss old [T7]; S8 60s n=%s "
            "vol=%s is a live book [P004]; S2 %s%% of range_hat [T3]; S9 "
            "rv1800/rv60=%s [T8]; S13 exit_default runs to the session close "
            "[T1]"
            % (r["f5m_sflow"], r["f5m_vol"], side, r["thru_n"], r["thru_bid"],
               r["thru_ask"], r["f60_sflow"], r["slope1m"],
               r["extreme_age_trade_side"], r["f60_n"], r["f60_vol"],
               r["pct_range_hat"], r["rv_collapse"]))


def against(r, t):
    """The strongest field pointing the other way — always named."""
    bits = []
    fph, vph = F(r, "fph_sflow"), F(r, "fph_vol")
    if fph is not None and vph:
        bits.append("S8 phase sflow=%s on %s (%.1f%%) — P015 would read this "
                    "as the direction and it is 1-1 across the two prior days"
                    % (r["fph_sflow"], r["fph_vol"], 100.0 * abs(fph) / vph))
    ext = F(r, "ext_needed")
    if ext is not None:
        bits.append("S3 room inside the phase range=$%s so the bar needs $%s of "
                    "NEW range (P017, deliberately not a term here)"
                    % (r["room_phase"], r["ext_needed"]))
    if r["asset"] == "NKD":
        bits.append("NKD has produced 0 D-021 winners in 514 candidates over "
                    "two day-complete sessions")
    return "; ".join(bits) if bits else "no field of the sheet opposes."


def call_row(r):
    t = terms(r)
    fire = all(t[k] for k in TERMS)
    return {"cid": r["cid"], "call": "TAKE" if fire else "SKIP",
            "conf": grade(r), "n_terms": sum(1 for k in TERMS if t[k]),
            "primary": evidence(r, t), "against": against(r, t),
            "sigma_to_exit": round(sigma_to_exit(r) or 0.0, 1),
            "event_in_session": event_in_session(r),
            **{k: int(t[k]) for k in TERMS}}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--index", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    with open(a.index) as fh:
        lines = [ln for ln in fh if not ln.startswith("#")]
    rows = list(csv.DictReader(lines, delimiter="\t"))
    out = [call_row(r) for r in rows]
    cols = (["cid", "call", "conf", "n_terms"] + list(TERMS)
            + ["sigma_to_exit", "event_in_session", "primary", "against"])
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter="\t",
                           extrasaction="ignore")
        w.writeheader()
        for o in out:
            w.writerow(o)
    n_take = sum(1 for o in out if o["call"] == "TAKE")
    print("e1d3_policy: %d rows, %d TAKE, %d SKIP -> %s"
          % (len(out), n_take, len(out) - n_take, a.out))
    for o in out:
        if o["call"] == "TAKE":
            print("   TAKE %-28s %s" % (o["cid"], o["conf"]))


if __name__ == "__main__":
    sys.exit(main())
