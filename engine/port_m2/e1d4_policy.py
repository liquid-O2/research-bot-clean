#!/usr/bin/python3
"""E1 STUDY DAY 4 — the reader's committed triage policy, made executable.

Successor to `e1d1_policy.py`, `e1d2_policy.py` and `e1d3_policy.py`, all three
of which are FROZEN as mechanical baselines for this day (CC-M2-8.2).  As on the
three previous days this is NOT a mechanical baseline: it is the reader's own
decision rule for 2021-07-06, written down so 1,268 day-complete calls are
reproducible and so the RULE, not just the calls, is what a census can attack.

STRICT CAUSALITY: a pure function of ONE triage-index row.  No candidate's call
reads another candidate's fields — which is also why the policy is immune to the
SCAN-EXPOSED hazard named on day 3 (ERA_NOTES §37).

=======================================================================
WHAT THREE DAY-COMPLETE SESSIONS ACTUALLY SAY (n=2,618, all unblinded,
lawful under CC-M2-9.4; 94 D-021 winners, base rate 3.6%)
=======================================================================
The round has spent three days discovering that almost every term flips.  The
day-4 rule is built ONLY from objects that are positive on all three sessions
measured on the POOLED CANDIDATE POOL (the day-3 method law: never settle a
threshold on the replay statistic).  Everything else is dropped with a receipt.

 (1) THE DIRECTION TERM THAT DOES NOT FLIP: AGGRESSION IS CONTRARIAN.
     S8 5m sflow OPPOSED to the trade at >= 5% of its own 5m volume, inside a
     live book with runway and a fresh extreme:
         day 1 mean +$34   16 winners / n=100
         day 2 mean +$414  26 winners / n=107
         day 3 mean +$68    4 winners / n=43
     Its mirror (5m flow WITH the trade) is +$427 / -$587 / +$232 — the flip
     that has cost this round two of its three days.  This is P007
     ABSORPTION_NO_RESPONSE in the form P007 always stated: the hitters are not
     the winners.  It is the ONLY direction object in the round with three
     same-signed day-complete readings.
 (2) THE MAGNITUDE FLOOR IS RELATIVE-OR-ABSOLUTE (the day-3 repair, ERA_NOTES
     §33).  92 of 94 winners have S8 5m volume >= 200 contracts; 80 of 94 have
     >= 500.  Day 3's absolute-only floor at 500 refused all 8 of that day's
     winners at 196-544 contracts (8.1-9.9% of phase volume).  The repaired
     form takes either.
 (3) RUNWAY, NOT PHASE (P025).  Every one of the 94 winners has at least
     13,146 seconds to its BINDING (phase-close, CC-M2-10.3) exit; 0 winners in
     the 513 rows below 10,800s.  The NY label of ERA_NOTES §20 was this fact
     wearing a clock (86 NY / 8 TOKYO of 94).  The term is written on the
     runway and reports the phase.
 (4) NEW — THE TAPE MUST BE CONTINUOUS, NOT JUMPY (S9 `jump_frac_1800s`, the
     bipower jump fraction (RV-BV)/RV over the last 30 minutes).  This is the
     first ex-ante field the round has found that speaks to the GIVE-BACK, the
     loss channel ERA_NOTES §35/§39.5 left open:
         jump_frac        n     keep (close/peak, rows with peak >= $600)   winners
         < 0.30          92          0.41                                   28.3%
         0.30-0.45      288          0.50                                   21.2%
         0.45-0.55      156          0.24                                    4.5%
         0.55-0.70      336          0.27                                    0.0%
         >= 0.70        180          0.20                                    0.0%
     87 of 94 winners sit below 0.45 and ZERO of 94 sit above 0.55 (n=1,464).
     Mechanism: a certificate is a multi-hour HOLD.  A tape whose variance
     arrives in discontinuous jumps gives the move back between the jumps; a
     tape whose variance arrives through continuous two-sided trading carries
     it to the exit.  Registered as P026 and censusable as one field.
 (5) IN-RANGE BAR, SCOPED INSIDE THE ABSORPTION FAMILY.  P017's extension
     arithmetic is a mean-reversion prior (ERA_NOTES §21) and it flips as a
     standalone term.  INSIDE the absorption family it does not: ext_needed
     <= $450 gives +$223 / +$157 / +$251 across the three sessions and cuts the
     walled fraction from 33% to 24%.  It is kept as a WALL term (its own
     receipt is the MAE column), never as the direction.

=======================================================================
THE RULE (7 terms).  Every threshold is settled on the pooled 3-day pool.
=======================================================================
 T1 LIVE BOOK       S8 60s n >= 5 and 60s vol >= 10  (P004; the cheapest veto
                    in the sheet and one of only two terms positive on all
                    three days).
 T2 RUNWAY          S3 runway to the BINDING exit (phase close) >= 12,000s
                    (P025; min winner 13,146s, 0 of 513 below 10,800s).
 T3 FRESH EXTREME   S3 trade-side phase extreme <= 3,600s old (the other
                    three-day survivor).
 T4 ABSORBED AGGR.  S8 5m sflow OPPOSED to the trade at >= 5% of 5m volume
                    (P007 as an entry object; (1) above).
 T5 MAGNITUDE       S8 5m vol >= 200 AND (5m vol >= 500 OR 5m vol >= 8% of the
                    phase's volume) — relative OR absolute (2).
 T6 IN-RANGE BAR    S3 phase extreme vs S13 entry mid x mult: ext_needed
                    <= $450 (5).
 T7 CONTINUOUS TAPE S9 jump_frac_1800s < 0.45 (4).

DELIBERATELY DROPPED, each with its receipt:
  * EVERY MOMENTUM / CONFIRMATION TERM.  Day 1 killed "slope signed with the
    trade" (17 sole-blocked candidates at +$1,438); day 2 rebuilt it as
    ANTI-CHASE; day 3 rebuilt it as MOMENT OF TURN and all three of that day's
    committed minimal pairs were refuted in the same direction.  ERA_NOTES §39
    asks whether the reader should stop building them entirely.  THIS RULE'S
    ANSWER IS YES, and the answer is pre-registered here: no S5 slope or accel
    field appears in any term.  Adding "60s flow WITH the trade" to the rule's
    take set pays +$377 / +$185 / -$214 — the same flip, one more disguise.
  * THROUGH-BOOK SIDE (day-3 T5).  Its sign contradicts the absorption term it
    sat next to (ERA_NOTES §33/E1D3-F4); inside this rule it costs day 3 its
    only winner (-$226 mean, 0 winners on that session).
  * THE SPREAD TAX (P005, day-3 T9).  Inside the absorption family it removes
    value: the family it blocks is +$95 mean with 4 D-021 winners, and day 2's
    single best candidate (SI-20210702-052246-L, +$1,995) is a wide-spread row
    one minute from the 12:30Z release.  P005's founding cases stay valid at
    the dead-book tail, which T1 already removes.
  * RANGE MATURITY (day-3 T3, S2 % of range_hat >= 45).  Struck on day 3: all
    8 winners arrived at 31.7-34.1%.
  * THE SEAT-SCOPE / PHASE TERMS (day-3 T1, ERA_NOTES §20).  Replaced by T2.

BACKTEST OF THIS EXACT RULE ON THE THREE ALREADY-UNBLINDED DAYS (in-sample by
construction — the thresholds were settled on these sessions — and quoted as
provenance, not as evidence):
    pooled   47 takes, 16 D-021 winners (34.0% vs a 3.6% base), mean +$301.91,
             walled 21.3%, mean peak +$993
    day 1    14 takes, mean +$616.88, 8 winners
    day 2    29 takes, mean +$156.85, 7 winners
    day 3     4 takes, mean +$251.25, 1 winner  <- the first rule in the round
             to admit a 2021-07-05 winner (HG-20210705-012045-L, +$1,138.75,
             the best certificate of that session, refused by every arm on the
             day-3 baseline table)
  EARLIEST-PER-SEAT replay (phase-close seating, CC-M2-10.3), informational
  only and NOT the statistic any threshold was chosen on:
    day 1 +$752.50   day 2 +$1,840.00   day 3 +$977.50
  It fires in 6 (day, asset, phase) seat cells over three sessions, i.e. ~2 per
  day, and its takes split 30 SHORT / 17 LONG — it is not a side bet.

PROSPECTIVE PATTERN REGISTRATION (CC-M2-4.3), committed before the day is
called: P004 (T1), P025 (T2), A5/freshness (T3), P007+P023-repaired (T4+T5),
P017-scoped (T6), and P026 CONTINUOUS_TAPE (T7, new this day).  Any pattern
claim not in this list is post-hoc and is marked as such.

THE GRADE (CC-M2-10.5, unchanged from day 3 so calibration accumulates across
rounds): sigma_to_exit = S9 rv_nowcast w1800 * sqrt(runway_to_binding_exit /
1800); A >= $2,500, B $1,200-2,500, C < $1,200.  Inside this rule's 3-day take
set it is monotone: C +$251 / 25% winners, B +$285 / 27.6%, A +$351 / 50.0%.
It is a magnitude-feasibility estimate, never a direction confidence.

WHAT THE DAY LOOKS LIKE BEFORE ANY OUTCOME IS OPENED.  2021-07-06 is the first
full trading session after the US Independence Day holiday; SI 541, HG 415,
NKD 312 = 1,268 candidates, the largest study day of the round.
"""
import argparse
import csv
import math
import os
import sys

RUNWAY_MIN = 12000.0        # T2
FRESH_MAX = 3600.0          # T3
F5_FRAC = 0.05              # T4
F5_VOL_FLOOR = 200.0        # T5
F5_VOL_ABS = 500.0          # T5
F5_VOL_REL = 0.08           # T5
EXT_MAX = 450.0             # T6
JUMP_MAX = 0.45             # T7
GRADE_A, GRADE_B = 2500.0, 1200.0

TERMS = ("T1", "T2", "T3", "T4", "T5", "T6", "T7")


def F(r, k):
    try:
        return float(r[k])
    except Exception:
        return None


def sgn(v):
    return 0 if v is None else (1 if v > 0 else (-1 if v < 0 else 0))


def terms(r):
    """{name: bool} for T1..T7 — a pure function of ONE index row."""
    side = 1 if r["side"] == "LONG" else -1
    t = {}

    f60n, f60v = F(r, "f60_n"), F(r, "f60_vol")
    t["T1"] = bool(f60n is not None and f60n >= 5
                   and f60v is not None and f60v >= 10)

    rw = F(r, "runway_phase")
    t["T2"] = bool(rw is not None and rw >= RUNWAY_MIN)

    age = F(r, "extreme_age_trade_side")
    t["T3"] = bool(age is not None and 0 <= age <= FRESH_MAX)

    s5, v5 = F(r, "f5m_sflow"), F(r, "f5m_vol")
    t["T4"] = bool(s5 is not None and v5 and v5 > 0
                   and abs(s5) / v5 >= F5_FRAC and sgn(s5) == -side)

    vph = F(r, "fph_vol")
    t["T5"] = bool(v5 is not None and v5 >= F5_VOL_FLOOR
                   and (v5 >= F5_VOL_ABS
                        or (vph is not None and vph > 0
                            and v5 >= F5_VOL_REL * vph)))

    ext = F(r, "ext_needed")
    t["T6"] = bool(ext is not None and ext <= EXT_MAX)

    jf = F(r, "jump_frac")
    t["T7"] = bool(jf is not None and jf < JUMP_MAX)
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
    day-2 separator, CC-M2-12.3 — recorded on every row, binding on none: it is
    a fact about which patterns apply, not a direction compass)."""
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
        return ("primary: S8 60s n=%s vol=%s — no transacting counterparty in "
                "the last minute (P004 DEAD_BOOK_VETO, positive on all three "
                "day-complete sessions)" % (r["f60_n"], r["f60_vol"]))
    if not t["T2"]:
        return ("primary: S3 runway to the binding exit (%s phase close) = %ss "
                "— every one of the 94 D-021 winners of the three unblinded "
                "sessions had at least 13,146s and none of the 513 rows below "
                "10,800s produced one (T2 RUNWAY, P025 RUNWAY_TO_BINDING_EXIT)"
                % (r["phase_dec"], r["runway_phase"]))
    if not t["T3"]:
        return ("primary: S3 %s-phase extreme on the trade's side is %ss old — "
                "past the 3,600s window there is no rejection object left to "
                "trade (A5 early-in-sequence; the second of the two terms "
                "positive on all three sessions)"
                % (r["phase_dec"], r["extreme_age_trade_side"]))
    if not t["T4"]:
        return ("primary: S8 5m sflow=%s on %s contracts — there is no opposed "
                "aggression for this %s to absorb, and aggression signed WITH "
                "the trade is the term that flipped sign on every one of the "
                "three unblinded sessions (+$427/-$587/+$232) while opposed "
                "aggression did not (+$34/+$414/+$68) (T4, P007 as an entry "
                "object)" % (r["f5m_sflow"], r["f5m_vol"], side))
    if not t["T5"]:
        return ("primary: S8 5m vol=%s against phase vol=%s — the opposed "
                "aggression is not AT MAGNITUDE on either the absolute (>=500) "
                "or the relative (>=8%% of phase volume) reading; 92 of 94 "
                "winners clear 200 contracts (T5 MAGNITUDE, the day-3 repair "
                "of the absolute-only floor)" % (r["f5m_vol"], r["fph_vol"]))
    if not t["T6"]:
        return ("primary: S3 room inside the phase range=$%s, so the $1,000 "
                "bar needs $%s of BRAND-NEW range beyond the phase extreme "
                "(T6 IN-RANGE BAR, P017 scoped inside the absorption family, "
                "where it cuts the walled fraction from 33%% to 24%%)"
                % (r["room_phase"], r["ext_needed"]))
    if not t["T7"]:
        return ("primary: S9 bipower jump_frac_1800s=%s — the last half hour's "
                "variance arrived in JUMPS, not in continuous trading; 0 of "
                "1,464 such rows over three day-complete sessions produced a "
                "D-021 winner and their certificates keep only 0.20-0.27 of "
                "their peak against 0.41-0.50 below 0.45 (T7 CONTINUOUS TAPE, "
                "P026, new this day)" % r["jump_frac"])
    return ("primary: S8 5m sflow=%s on %s contracts is aggression OPPOSED to "
            "this %s at %s%% of its own 5m volume, at magnitude against a "
            "phase volume of %s [T4+T5 = P007 ABSORPTION_NO_RESPONSE as an "
            "entry object: the hitters are not the winners, the only "
            "direction reading that holds its sign across all three unblinded "
            "sessions]; S9 jump_frac_1800s=%s says the tape is trading "
            "continuously rather than gapping, which is what a multi-hour "
            "hold needs to keep its peak [T7, P026]; S3 gives %ss of runway to "
            "the binding %s phase close [T2, P025] with the trade-side phase "
            "extreme %ss old [T3] and the $1,000 bar $%s inside the range the "
            "phase has already traded [T6]; S8 60s n=%s vol=%s is a live book "
            "[T1, P004]"
            % (r["f5m_sflow"], r["f5m_vol"], side,
               _pct(r, "f5m_sflow", "f5m_vol"), r["fph_vol"], r["jump_frac"],
               r["runway_phase"], r["phase_dec"], r["extreme_age_trade_side"],
               r["ext_needed"], r["f60_n"], r["f60_vol"]))


def _pct(r, num, den):
    a, b = F(r, num), F(r, den)
    if a is None or not b:
        return "."
    return "%.1f" % (100.0 * abs(a) / b)


def against(r, t):
    """The strongest field pointing the other way — always named."""
    bits = []
    fph, vph = F(r, "fph_sflow"), F(r, "fph_vol")
    if fph is not None and vph:
        bits.append("S8 phase sflow=%s on %s (%.1f%%) — P015 PHASE_FLOW_"
                    "CONCORDANCE reads this as the direction and it is 1-1 "
                    "across the three unblinded sessions"
                    % (r["fph_sflow"], r["fph_vol"], 100.0 * abs(fph) / vph))
    sl = F(r, "slope1m")
    if sl is not None:
        bits.append("S5 mid_slope_$/min(T-1m)=%s, the field every momentum "
                    "term of days 1-3 was built on and which this rule "
                    "deliberately does not read" % r["slope1m"])
    if F(r, "rv_collapse") is not None and F(r, "rv_collapse") >= 8:
        bits.append("S9 rv1800/rv60=%s — P013's collapse marker fires"
                    % r["rv_collapse"])
    if r["asset"] == "NKD":
        bits.append("NKD has produced 0 D-021 winners in 711 candidates over "
                    "three day-complete sessions")
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
    p.add_argument("--quiet", action="store_true")
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
    print("e1d4_policy: %d rows, %d TAKE, %d SKIP -> %s"
          % (len(out), n_take, len(out) - n_take, a.out))
    if not a.quiet:
        for o in out:
            if o["call"] == "TAKE":
                print("   TAKE %-28s %s" % (o["cid"], o["conf"]))


if __name__ == "__main__":
    sys.exit(main())
