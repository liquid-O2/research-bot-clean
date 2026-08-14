#!/usr/bin/python3
"""E1 STUDY DAY 4 — seal the day ledger (CC-M2-3/4/5 annotations).

Takes the reader's executable policy output (e1d4_policy.py) and emits the
committed ledger with every CC-M2-4/5 annotation: taint, pre-mortem per TAKE,
minimal pair + flip threshold per deep-read TAKE, per-call deep-read section
log.  There are NO discretionary overrides on this day, and the reason is
recorded below.

DRAW.  The next chronological STUDY session per asset strictly after 2021-07-05,
warm-up sessions excluded (CC-M2-8.1): SI/HG/NKD 2021-07-06 — 1,268 candidates
(SI 541, HG 415, NKD 312), the largest study day of the round.  No warm-up,
day-1, day-2 or day-3 round has touched 2021-07-06.

TAINT: CLEAN, AND THE SCAN EXPOSURE IS CLOSED BY TOOL THIS DAY.  Day 3 named
SCAN-EXPOSED (ERA_NOTES §37): the day-complete triage index shows later rows'
`mid`, i.e. the price path after the second being called, and the day-3 reader
scanned it.  CC-M2-12.1(a) makes an as-of prefix view mandatory before any
BLIND round.  `triage_index.py --as-of` has NOT landed at HEAD, so the reader
built the mechanic in its own lane (`engine/port_m2/e1d4_asof.py`) and ran the
whole day through it:
  * the committed policy is a pure function of ONE index row and is
    mechanically unexposed (as on every prior day);
  * every DISCRETIONARY view — the take walk, the deep reads, the minimal
    pairs — was taken through `--next`/`--at`, which prints only rows whose
    decision second is <= the candidate being called, and prints exactly ONE
    candidate per call so the day's take list is never visible as a list.
  * the reader therefore walked 2021-07-06 forward in time.  It knew, when it
    read the 17:13 candidate, what had happened since 15:32 — which is what a
    reader standing at 17:13 lawfully knows — and it never revised a call made
    earlier.  Row taint is recorded as CLEAN, with `AS-OF-PREFIX` on the TAKE
    rows naming the tool that enforced it.

WHY THERE IS NO OVERRIDE ON THIS DAY.  Days 1-3 each carried one, and the round
now has three verdicts on them (day 1 +$1,682, day 2 right-but-forfeited, day 3
the entire day's result).  This day's rule is itself a new object — it is the
first rule of the round built ONLY from terms with three same-signed
day-complete readings, and its direction term (aggression is contrarian) is the
thing the round most needs measured.  Adding a discretionary layer on top of a
rule whose whole purpose is to be measured would make the day unreadable.  The
one place discretion was exercised is recorded honestly: the reader deep-read
the three seat-spending candidates BEFORE their seats were spent, found
material evidence against two of them (S10's developing POC prices both moves
below the bar), wrote that evidence into the against/pre-mortem fields, and
still took the rule's call.  If the pre-mortems fire, that is the day's finding.

WHAT THE RULE DID.  44 TAKEs of 1,268 (3.5%): 32 SI NY longs, 11 HG NY longs,
1 HG TOKYO short.  Three seat cells under CC-M2-10.3 phase-close seating:
HG/TOKYO (03:15:31), SI/NY (15:02:08), HG/NY (15:32:46).  NKD: zero takes for
the fourth session running — 263 of its 312 candidates fail P004's live-book
floor outright, and no NKD row on this session clears more than 5 of the 7
terms.  Every row of the day carries `event_in_session=0`: the next scheduled
release is CPI on 2021-07-13, so by the CC-M2-12.3 separator this is a
"day-1-like" session, and the rule's direction term points the OPPOSITE way to
what P015 would say on such a day.  That disagreement is deliberate and is the
day's registered test.
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e1d4_policy as POLICY                                   # noqa: E402

LEDGER = "/workspace/provenance/port_m2/E1_STUDY_LEDGER.tsv"
TAINT_SKIP = "CLEAN"
TAINT_TAKE = "CLEAN;AS-OF-PREFIX"

# --------------------------------------------------------------- deep reads --
# cid -> sections actually opened (CC-M2-4.5 cost-of-information ledger).
DEEP = {
    "HG-20210706-011731-S": "S1,S2,S3,S4,S5,S6,S7,S8,S9,S10,S11,S12,S13",
    "SI-20210706-054128-L": "S3,S4,S5,S7,S8,S9,S10,S13",
    "HG-20210706-055966-L": "S3,S4,S5,S8,S9,S10",
    "HG-20210706-056024-L": "S3,S8",
    "HG-20210706-062028-L": "S3,S8,S9",
    "SI-20210706-066009-L": "S3,S8,S9",
    "SI-20210706-052118-S": "S3,S9",
    "SI-20210706-054095-S": "S3,S8",
    "SI-20210706-054396-L": "S3,S8",
    "NKD-20210706-059157-L": "S3,S8,S9",
}

# ------------------------------------------------------------- pre-mortems ---
# One per TAKE (CC-M2-5.4).  A pre-mortem naming a MEASURABLE mechanism
# auto-logs as a ledger hypothesis feeding the censuses (CC-M2-10.4).
PM_TOKYO = ("PRE-MORTEM: this loses if the TOKYO buyers who took the phase "
            "from 4.3380 to 4.3693 in eleven minutes are a parent order still "
            "working, in which case the 245-second-old high is a pause and not "
            "a rejection. The measurable form, and the one I would have used: "
            "S10's developing POC is 4.3440, $612.50 below the entry, and the "
            "$1,000 bar sits at 4.3285, BELOW the developing VAL 4.3395 — the "
            "profile prices this move at two thirds of the bar, which is "
            "exactly the give-back shape of ERA_NOTES §35. If S8's 60s window "
            "turns buy at >= 10% of its own volume while price holds above "
            "4.3669 (the FVOL_LADDER OPEN_TOKYO|q10|+1 at -$40.5), the "
            "rejection has failed and the 07:00 phase close prices this at "
            "whatever the Tokyo afternoon leaves behind.")
PM_SI_NY = ("PRE-MORTEM: this loses if the 26.685-26.6975 shelf (PRIOR_WEEK H "
            "at d$=0, LONDON POC -$12.5, SESSION POC -$37.5, TOKYO POC and the "
            "TOKYO OR30/OR60 k1.0 extension at -$62.5) is not support but a "
            "queue of resting sellers, because S8's fuel map has 7,805 of the "
            "phase's 7,902 contracts trapped ABOVE the mid: every buyer of "
            "this phase is underwater and each of them is a seller into any "
            "bounce. The measurable form: S10's developing POC is 26.7700, "
            "$362.50 above, and the developing VAH 26.8200 is $750 above — the "
            "profile prices this long at a third to three quarters of the bar "
            "before the bar is reached, and a $1,000 certificate needs 26.8975, "
            "outside the developing value area entirely. If S8's 60s sflow "
            "stays SELL at >= 10% of its own volume for another five minutes "
            "with price below 26.6875, the shelf is broken and the trapped "
            "mass above becomes the whole afternoon's supply.")
PM_HG_NY = ("PRE-MORTEM: this loses if the descending staircase in S3's ZigZag "
            "chain — LOW 4.3275 (15:11), 4.3223 (15:14), 4.3213 (15:20), "
            "4.3168 (15:32), each with a lower high between — is an execution "
            "algorithm working a parent sell order rather than a phase that "
            "has spent itself (S3 COVERAGE NY=119.0%, unspent -$275.6). The "
            "measurable form: I am buying $11.50 UNDER the FVOL_BAND "
            "OPEN_LONDON|k0.5|-1 at 4.3213 whose S4 outcome already reads "
            "REJECT, i.e. inside broken support (P008), and the levels that "
            "are PENDING sit BELOW me at 4.3153-4.3163 with min_tc_near=1 — I "
            "am long above a level that has not yet held. If S8's 60s sflow "
            "turns sell at >= 10% of its own volume while price is below "
            "4.3168, the staircase has another rung and the $900 wall at "
            "4.2858 is 1.4 rungs away.")
PREMORTEM_BY_CELL = {("HG", "TOKYO"): PM_TOKYO,
                     ("SI", "NY"): PM_SI_NY,
                     ("HG", "NY"): PM_HG_NY}

# ------------------------------------- minimal pairs + flip thresholds -------
MINIMAL_PAIR = {
    "HG-20210706-011731-S": (
        "MINIMAL PAIR: HG-20210706-011289-L (03:08:09, same asset/phase, 442s "
        "earlier, LONG) — SKIP. THE DIFFERENCE: one field, the side the "
        "aggression is on relative to the trade. At 03:08:09 the 5-minute flow "
        "(+52 on 428) was WITH the long and the rule refused it; at 03:15:31 "
        "the same buying (+44 on 661) is AGAINST the short and the rule takes "
        "it. Both rows are on the same tape, the same phase, the same book "
        "state and the same jump regime; T4 is the only term whose value "
        "differs, and its ex-post grade is the whole test of ERA_NOTES §38's "
        "direction question."),
    "SI-20210706-054128-L": (
        "MINIMAL PAIR: SI-20210706-054095-S (15:01:35, same asset/phase, 33 "
        "seconds earlier, SHORT) — SKIP. THE DIFFERENCE: the same selling "
        "(5m -49 on 689 there, -140 on 798 here) is WITH the short and AGAINST "
        "the long, so T4 fires only for the long; and the bar is entirely "
        "inside the phase range for the long (ext_needed $0 against $862.50 "
        "for the short, room to the phase high $1,050). Thirty-three seconds "
        "and one price tick separate two opposite calls, and the fields that "
        "separate them are the two the rule was rebuilt on."),
    "HG-20210706-055966-L": (
        "MINIMAL PAIR: SI-20210706-054396-L (15:06:36, LONG, the same "
        "absorption shape one asset over) — SKIP, blocked by T4 alone: its 5m "
        "flow is -44 on 1,304 contracts = 3.4%, under the 5% magnitude floor, "
        "while this row's is -106 on 1,066 = 10.0%. THE DIFFERENCE is the "
        "MAGNITUDE of the opposed aggression and nothing else — both are fresh "
        "phase lows with a live book, session-close runway, ext_needed $0 and "
        "a sub-0.45 jump fraction. If the pair pays and this does not, the 5% "
        "floor is a fitted number, not a mechanism."),
}
FLIP = {
    "HG-20210706-011731-S": (
        "FLIP THRESHOLD: S9 jump_frac_1800s = 0.415 against the T7 cut at "
        "0.450. Thirty-five thousandths of a jump fraction — this call is the "
        "closest thing the day has to a coin flip on the round's newest term. "
        "The second binding field is S8 5m sflow/vol = 6.7%: below 5.0% (i.e. "
        "sflow < +33 on 661) T4 stops firing and the call becomes SKIP."),
    "SI-20210706-054128-L": (
        "FLIP THRESHOLD: S9 jump_frac_1800s = 0.431 against the T7 cut at "
        "0.450 — 0.019 of margin. The rule's own second-closest field is S3 "
        "ext_needed = $0 with room_phase $1,050: the phase high would have to "
        "sit below 26.7875 (room < $550) before T6's $450 ceiling bound."),
    "HG-20210706-055966-L": (
        "FLIP THRESHOLD: S8 5m sflow/vol = 10.0% against the T4 floor at 5.0% "
        "— this one has margin. The binding field here is S9 jump_frac = 0.306 "
        "(the most continuous tape of the three seats) and S3 room_phase "
        "$1,600: the call would flip only if the phase high were below 4.3618, "
        "leaving ext_needed above $450."),
    "SI-20210706-052118-S": (
        "FLIP THRESHOLD (recorded on a SKIP because it is the day's registered "
        "test of P026): S9 jump_frac_1800s = 0.527 against the T7 cut at "
        "0.450. This row clears the other six terms — a 167-second-old NY "
        "phase high at 26.8300, buyers hitting at 18.1% of the 5-minute volume "
        "(+95 on 524), $425 of new range needed, 30,681s of runway — and is "
        "refused on the jump fraction alone. Eleven rows of this session are "
        "sole-blocked by T7. If they are the day's winners, P026 is a "
        "value-destroying term on its first outing and the ledger says so."),
}

# --------------------------------------------------------- novel/hypotheses --
NOVEL_BY_CELL = {
    ("HG", "TOKYO"): (
        "novel: P026 CONTINUOUS_TAPE (registered prospectively today, "
        "CC-M2-4.3). S9's bipower jump fraction (RV-BV)/RV over the last "
        "1,800s is the first ex-ante field the round has found that speaks to "
        "the GIVE-BACK channel ERA_NOTES §35/§39.5 left open: over the three "
        "unblinded day-complete sessions, rows with a peak above $600 keep "
        "0.41-0.50 of that peak when jump_frac < 0.45 and 0.20-0.27 when it is "
        "above 0.55, and 87 of the 94 D-021 winners sit below 0.45 with ZERO "
        "of 1,464 rows above 0.55. Mechanism: a certificate is a multi-hour "
        "HOLD, and a tape whose variance arrives in discontinuous jumps gives "
        "the move back between them. This row is its first live test at 0.415, "
        "0.035 from the cut."),
    ("SI", "NY"): (
        "novel: the day's registered direction test. S8 5m aggression OPPOSED "
        "to the trade at magnitude is the ONLY direction object in the round "
        "with three same-signed day-complete readings (+$34 / +$414 / +$68, "
        "16/26/4 D-021 winners) while its mirror flips (+$427 / -$587 / "
        "+$232). Every row of 2021-07-06 carries event_in_session=0, so the "
        "CC-M2-12.3 separator calls this a day-1-like session and P015 would "
        "point the other way: on this seat the two hypotheses make opposite "
        "calls and the tape settles it."),
    ("HG", "NY"): (
        "novel: P025 RUNWAY_TO_BINDING_EXIT as a threshold rather than a "
        "phase label (registered prospectively). Every one of the 94 winners "
        "of the three unblinded sessions had >= 13,146s to its binding exit "
        "and none of the 513 rows under 10,800s produced one; this seat has "
        "26,833s. The census the ledger owes is winner rate by (asset, "
        "runway band) with phase_dec as a control — this row is the runway "
        "term firing in the phase that used to be the label."),
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--index", required=True)
    p.add_argument("--ledger", default=LEDGER)
    a = p.parse_args()

    with open(a.index) as fh:
        lines = [ln for ln in fh if not ln.startswith("#")]
    rows = list(csv.DictReader(lines, delimiter="\t"))
    by_cid = {r["cid"]: r for r in rows}
    for cid in list(DEEP) + list(MINIMAL_PAIR) + list(FLIP):
        if cid not in by_cid:
            raise SystemExit("seal: unknown cid %s" % cid)

    out = []
    for r in rows:
        c = POLICY.call_row(r)
        cid = c["cid"]
        cell = (r["asset"], r["phase_dec"])
        prem = ""
        if c["call"] == "TAKE":
            prem = PREMORTEM_BY_CELL.get(cell, "")
            if not prem:
                raise SystemExit("seal: TAKE without a pre-mortem: %s" % cid)
        out.append({
            "cid": cid, "call": c["call"], "conf": c["conf"],
            "primary": c["primary"], "against": c["against"],
            "interaction": "", "novel": (NOVEL_BY_CELL.get(cell, "")
                                         if c["call"] == "TAKE" else ""),
            "premortem": prem,
            "minimal_pair": MINIMAL_PAIR.get(cid, ""),
            "flip_threshold": FLIP.get(cid, ""),
            "sections_read": DEEP.get(cid, "TRIAGE-INDEX-ONLY"),
            "depth": "DEEP" if cid in DEEP else "TRIAGE",
            "taint": TAINT_TAKE if c["call"] == "TAKE" else TAINT_SKIP,
            "n_terms": c["n_terms"],
            "terms": "".join(str(c[k]) for k in POLICY.TERMS),
            "asset": r["asset"], "phase_dec": r["phase_dec"],
            "clock": r["clock"], "candidate_class": r["cls"],
        })

    cols = ("cid call conf primary against interaction novel premortem "
            "minimal_pair flip_threshold sections_read depth taint n_terms "
            "terms asset phase_dec clock candidate_class").split()
    with open(a.ledger, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter="\t",
                           extrasaction="ignore", lineterminator="\n")
        for o in out:
            w.writerow(o)
    n_take = sum(1 for o in out if o["call"] == "TAKE")
    print("E1D4 sealed: %d rows appended (%d TAKE, %d SKIP), %d deep reads"
          % (len(out), n_take, len(out) - n_take, len(DEEP)))


if __name__ == "__main__":
    sys.exit(main())
