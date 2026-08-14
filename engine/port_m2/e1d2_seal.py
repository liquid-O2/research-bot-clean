#!/usr/bin/python3
"""E1 STUDY DAY 2 — seal the day ledger (CC-M2-3/4/5 annotations).

Takes the reader's executable policy output (e1d2_policy.py), applies the
reader's DEEP-READ OVERRIDES — the discretionary part, because a mechanical
rule is not a reader — and emits the committed ledger with every CC-M2-4/5
annotation: taint, pre-mortem per TAKE, minimal pair + flip threshold per
deep-read TAKE, per-call deep-read section log.

FIELD CORRECTION (CC-M2-9.3) applied before sealing: the triage extractor's
`slope5m` was the ONE-MINUTE slope; the extractor now names sl_15/sl_5/sl_1
separately and every slope term in e1d2_policy.py reads `slope1m` explicitly.
The seat set is unchanged by the correction (the decision fields were the same
numbers under a wrong label); the evidence strings now name the right field.

TAINT.  CC-M2-8.1 removed the P-M2c warm-up sessions (SI 20210701/20210831,
HG 20210701/20210929, NKD 20210701/20210818) from every future draw, and this
day's deterministic draw — the next chronological STUDY session per asset
strictly after 2021-07-01 — is SI/HG/NKD 2021-07-02, which no warm-up and no
prior study day has touched.  Every row is therefore CLEAN.  The one honest
qualification, recorded rather than hidden: the reader carries day 1's
outcomes for the IMMEDIATELY PRECEDING session (2021-07-01) as mandated
memory.  That is adjacent-session knowledge, not this session's outcomes, and
the sheets themselves carry the prior session forward (S3 gap_vs_settle
prior_C, the PRIOR_DAY/PRIOR_WEEK level families, S10 prior_session profile),
so it is not a channel the protocol can or should close.
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import used_cases as UC                                        # noqa: E402

READER = "opus-discretionary"   # the E1 study reader (ledger header)

# ---- the reader's deep reads: cid -> sections actually opened on the sheet --
DEEP = {
    "SI-20210702-052340-S":  "S3,S4,S5,S8,S9",
    "NKD-20210702-052434-S": "S3,S4,S5,S8,S9",
    "SI-20210702-052509-S":  "S3,S4,S5,S7,S8,S9,S13",
    "SI-20210702-052564-S":  "S1,S2,S3,S4,S5,S7,S8,S9,S12,S13",
    "HG-20210702-052565-S":  "S3,S4,S5,S7,S8,S9,S13",
    "SI-20210702-052941-S":  "S3,S4,S8,S9",
    "SI-20210702-054267-S":  "S3,S4,S7,S8,S9,S13",
    "HG-20210702-055212-S":  "S3,S4,S8",
    "SI-20210702-057049-S":  "S3,S4,S5,S8,S9",
    "SI-20210702-058053-S":  "S3,S4,S5,S8,S9",
    "HG-20210702-058378-L":  "S3,S4,S5,S8,S9",
    "SI-20210702-058695-S":  "S3,S4,S8,S9",
}

# ---- discretionary OVERRIDES of the executable policy ----------------------
# cid -> (call, conf, primary, against, novel)
OVERRIDE = {
 "HG-20210702-058378-L": (
   "TAKE", "B",
   "primary: S3 phase NY L=4.2473@16:10:09 (169s old) vs S13 entry mid=4.2520 "
   "with mult=25000 — room to the phase high 4.2903 is $957.5, so the $1,000 "
   "bar needs only $42.5 of NEW range [P017], the smallest extension any LONG "
   "on this day asks for; S3 COVERAGE NY=68.5% unspent=$494.0 with S9 "
   "ladder_position=at_or_above_q10 (HG's fvol row is NOT refused, so the A1 "
   "ladder form is evaluable here and it agrees with the arithmetic); S3 "
   "runway to_phase_close=24421s to a session-close exit; S8 60s n=66 vol=102 "
   "is a live book and S8 30m sflow=+131 on 3130 (+4.2%) is buying.",
   "against: T5 fails at the phase horizon — S8 phase sflow=-113 on 19637 is "
   "0.6%, i.e. the NY phase's cumulative flow is BALANCED, not concordant, so "
   "P015 gives this trade no push; S4 shows PHASE_HL LONDON|lb1|L and "
   "OVERNIGHT|lb1|L stacked at 4.2555, $87.5 above the entry with outcome "
   "RECLAIM (P008 BROKEN_SUPPORT_OVERHEAD: an L-family level with positive d$ "
   "is the densest resistance object on the sheet, and the bar has to clear "
   "it); ERA_NOTES §10 says every one of day 1's 48 D-021 winners was a NY "
   "SHORT and none was a long.",
   "novel: this is a DELIBERATE, NAMED PROBE of ERA_NOTES §19 open question 1 "
   "(does the all-shorts/all-NY concentration of day 1 survive a second "
   "session?).  A hypothesis that is never given a chance to fire cannot be "
   "falsified, and the era's largest open question deserves the one candidate "
   "of the day that fails only the balanced-flow term.  P015 was measured as "
   "a requirement against OPPOSED flow; here the flow is balanced (0.6%) and "
   "the 30-minute window is concordant, which is the exact gap in P015's "
   "scope statement.  The probe costs one committed TAKE and, under D-046, no "
   "replay dollars: HG's seat was already spent at 14:36:05."),
}

# ---- discretionary GRADE overrides (the A|B|C value estimate only) ---------
# CC-M2-4.4 scores A|B|C for monotone calibration, so the grade has to be the
# reader's honest value estimate and not a by-product of the term count.  The
# policy grades SI-20210702-058053-S a B on its capacity and flow markers; the
# deep read says otherwise (S5 trades/min 79->261->41->46->32, S8 60s vol=45,
# S8 through_book_600s n=5), so it is graded C — a TAKE I expect to earn less
# than $700.
CONF_OVERRIDE = {"SI-20210702-058053-S": "C"}


# ---- pre-mortems (CC-M2-5.4: one committed sentence per TAKE) --------------
PREMORTEM = {
 "SI-20210702-052564-S":
   "PRE-MORTEM: this loses if the 12:30Z Employment Situation started a trend "
   "rather than a spike — S3 shows the NY phase high 26.4675 printed 2s ago "
   "at the end of a $737.5 impulse in 73s, and S8's fuel map has 7,330 of "
   "7,417 phase contracts BELOW the mid, so every one of those longs is in "
   "profit and none of them has to sell; if the next minute takes 26.4675 "
   "out, the $900 wall is $180 of silver away and 8.4h of hold time is "
   "against me.",
 "HG-20210702-052565-S":
   "PRE-MORTEM: HG is not the asset the news moved — S8 5m sflow=+145 on "
   "1,097 and 30m=+23 say the buying is current and the -425 phase imbalance "
   "is inherited; every one of the last six S8 through_book prints is >A "
   "(buying through the ask).  If 4.2785 (27s old) is a launch rather than a "
   "rejection, this is short into a copper trend day with S7 refill "
   "frac=0.667 (a book that is NOT restocking) and the wall $900 above.",
 "SI-20210702-054267-S":
   "PRE-MORTEM: the level is the whole thesis here — S4 FVOL_BAND "
   "OPEN_NY|k0.5|+1=26.5518 (tc=1, +$46.3) and NDAY N10|H=26.5550 (tc=1, "
   "+$62.5) are $46-63 above the entry on their FIRST test.  If they fail, "
   "there is nothing above until N2/N3/N5|H at 26.5225 is far below and the "
   "session is already 96.4% of range_hat with S9 surprise=0.836, i.e. a day "
   "that has kept expanding all session expands through me.",
 "SI-20210702-057049-S":
   "PRE-MORTEM: this is a mid-leg continuation (S3 phase H 26.6675@15:16:26, "
   "2,063s old) and it loses if 26.4925 is the base rather than a waypoint — "
   "S8's fuel map is nearly symmetric now (11,720 above / 14,230 below), the "
   "asymmetry that carried the first leg has been spent, and S2 day_type is "
   "EXPANDED at 112.1% of range_hat with S9 surprise=0.993, so the day has "
   "already delivered more range than a typical one and the next $1,000 is "
   "borrowed from tomorrow.",
 "SI-20210702-058053-S":
   "PRE-MORTEM: the book is leaving — S5 trades/min runs 79 -> 261 -> 41 -> "
   "46 -> 32 (z=-0.95), S8 60s vol=45 against a phase that has traded 28,688, "
   "and S8 through_book_600s n=5.  A phase-close hold needs someone to keep "
   "selling for 6.9 hours; P004's floor (n>=5, vol>=10) is a floor, not a "
   "quorum, and this is how a correct thesis dies of participation decay "
   "rather than of being wrong.",
 "HG-20210702-058378-L":
   "PRE-MORTEM: this loses exactly the way P008 says it should — the stacked "
   "LONDON/OVERNIGHT lb1|L at 4.2555 ($87.5 above, outcome RECLAIM) is "
   "overhead supply that a $1,000 long must eat through, and with S8 phase "
   "sflow at -113 there is no parent order behind me to eat it.  If ERA_NOTES "
   "§10 is a standing property of this port rather than a one-session "
   "artefact, this is the trade that proves it, and it proves it at -$930.",
}
DUP_PREMORTEM = ("PRE-MORTEM: same seat as %s — it fails the same way, and "
                 "under D-046 it cannot even be entered while that position "
                 "is held to its session-close exit.")

MINIMAL_PAIR = {
 "SI-20210702-052564-S":
   "MINIMAL PAIR: SI-20210702-052509-S (14:35:09, same asset/side/phase, 55s "
   "earlier, also a fresh phase high 6s old) — SKIP.  THE DIFFERENCE: S8 60s "
   "sflow=+70 on 424 (16.5% BUYING) with S5 mid_slope(T-1m)=+100 and accel=+32.5 "
   "there, versus 60s sflow=+8 on 940 (0.9%, balanced) here.  Both streams "
   "opposed the trade at 14:35:09; by 14:36:04 the flow stream has gone flat "
   "at four times the participation and the last S8 through-print is >B.  "
   "Two-stream opposition (T9), not the level and not the capacity "
   "arithmetic, is the only field that separates them.",
 "HG-20210702-052565-S":
   "MINIMAL PAIR: HG-20210702-052507-S (14:35:07, same asset/side/phase, 58s "
   "earlier) — SKIP.  THE DIFFERENCE: S5 mid_slope(T-1m)=+68.7 (against the short) "
   "with S8 60s sflow=+29 on 169 (17.2%) there; here the 1-minute slope has turned to -12.5.  "
   "Same phase high, same coverage, same runway: the price stream turning is "
   "the separator.",
 "SI-20210702-054267-S":
   "MINIMAL PAIR: SI-20210702-054009-S (15:00:09, same asset/side/phase, 258s "
   "earlier) — SKIP (T9: S8 60s sflow=+76 on 367 = 20.7% with S5 mid_slope(T-1m)=+125, "
   "both against).  THE DIFFERENCE: by 15:04:27 the 60s flow is -9 on 489 and the "
   "last three S8 through_book prints are all >B; the entry is also $87.5 "
   "higher against the same NY low.",
 "SI-20210702-057049-S":
   "MINIMAL PAIR: SI-20210702-056625-S (15:43:45, same asset/side/phase, 7 "
   "minutes earlier) — SKIP.  THE DIFFERENCE: exactly one field, and it is my "
   "own threshold — S8 phase |sflow|/vol is 1,106/24,883 = 4.44% there and "
   "1,319/25,950 = 5.08% here.  Room ($1,700 vs $1,650), runway, spread, "
   "book and freshness are all equivalent or better on the pair.  If 056625-S "
   "pays like 057049-S, P015's 5% bar is a line drawn in noise.",
 "SI-20210702-058053-S":
   "MINIMAL PAIR: SI-20210702-058695-S (16:18:15, same asset/side/phase, 10 "
   "minutes later) — SKIP.  THE DIFFERENCE: S3 phase-extreme age crosses my "
   "3,600s window (3,067s vs 3,709s) while every flow term gets BETTER "
   "(S8 30m sflow -819 on 4,984 = 16.4% sell vs -807 on 5,346 here).  If "
   "058695-S pays, my T7 window is arbitrary and the freshness term should be "
   "dropped outright rather than widened.",
 "HG-20210702-058378-L":
   "MINIMAL PAIR: HG-20210702-057367-L (15:56:07, same asset/side/phase, 17 "
   "minutes earlier) — SKIP.  THE DIFFERENCE: S3 room $882.5 (ext_needed "
   "$117.5) against $957.5 (ext $42.5) here, and S8 30m sflow -55 on 18,017 "
   "there against +131 on 3,130 here — the 30-minute buying that makes "
   "058378-L a probe rather than a guess had not started at 15:56.",
}

FLIP = {
 "SI-20210702-052564-S":
   "FLIP THRESHOLD: S8 60s sflow / 60s vol.  At +8/940 (0.9%) the call "
   "stands; it flips to SKIP once the 60s imbalance is >= +10% of 60s volume "
   "(i.e. sflow >= +94 here) while S5 mid_slope is still positive — that is "
   "exactly the state 55s earlier.  Second flip: S3 room inside the phase "
   "range below $550 (ext_needed > $450), i.e. mid below 26.3775.",
 "HG-20210702-052565-S":
   "FLIP THRESHOLD: S3 ext_needed.  At $357.5 the call stands; past $450 "
   "(mid below 4.2680 against this phase low) it flips to SKIP.  Second "
   "flip: S5 mid_slope(T-1m) back above 0 with S8 60s sflow still >= +10% (T9).",
 "SI-20210702-054267-S":
   "FLIP THRESHOLD: S4 tc on FVOL_BAND OPEN_NY|k0.5|+1 = 26.5518.  At tc=1 "
   "the P006 waiver of P015 applies; at tc>=2 the level is no longer a first "
   "test, the waiver lapses, and with S8 phase sflow at 4.5% (below the 5% "
   "bar) the call flips to SKIP.",
 "SI-20210702-057049-S":
   "FLIP THRESHOLD: S8 30m sflow / 30m vol.  At -693/5,464 (12.7% sell) the "
   "call stands; it flips to SKIP if the 30m imbalance falls below 5% of 30m "
   "volume, because a 2,063s-old extreme leaves the flow as the only live "
   "evidence.  Second flip: S9 rv1800/rv60 >= 8 (here 5.71).",
 "SI-20210702-058053-S":
   "FLIP THRESHOLD: S8 60s vol.  At 45 contracts the call stands only "
   "marginally (grade forced to C); below P004's floor (60s n < 5 or vol < "
   "10) it is a SKIP, and I would in fact flip it at 60s vol < 30 with S5 "
   "trades/min z < -1.0 — a threshold this sheet is $15 of volume away from.",
 "HG-20210702-058378-L":
   "FLIP THRESHOLD: S8 phase sflow.  At -113/19,637 (0.6% — balanced) the "
   "probe stands; at |phase sflow| >= 5% of phase volume AGAINST the long "
   "(i.e. sflow <= -982) it is a straight SKIP under P015, and at >= +5% FOR "
   "it, it would be a routine TAKE needing no override at all.  Second flip: "
   "S3 ext_needed past $450 (mid below 4.2500).",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True)
    ap.add_argument("--index", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--used-case-ledger", default=UC.LEDGER,
                    help="D-035.2 used-case ledger the seal records into "
                         "(CC-M2-17.4); tests point it elsewhere")
    a = ap.parse_args()
    idx = {r["cid"]: r for r in
           csv.DictReader(open(a.index).readlines()[1:], delimiter="\t")}
    rows = list(csv.DictReader(open(a.policy), delimiter="\t"))
    rows.sort(key=lambda r: (int(idx[r["cid"]]["sec"]), r["cid"]))

    cols = ["cid", "call", "conf", "primary", "against", "interaction", "novel",
            "premortem", "minimal_pair", "flip_threshold", "sections_read",
            "depth", "taint", "n_terms", "terms", "asset", "phase_dec",
            "clock", "candidate_class"]
    out = []
    for r in rows:
        i = idx[r["cid"]]
        call, conf = r["call"], r["conf"]
        primary, agst, novel = r["primary"], r["against"], ""
        if r["dup_of"]:
            # D-046 duplicates are TAKEs in the ledger: the thesis is "this is
            # a seat".  panel_score's one-position replay forfeits the ones
            # that cannot be filled and RECORDS the forfeit; pre-filtering them
            # here would hide the reader's real discrimination in the SKIP
            # pool.  (Identical to day 1, so the two ledgers are comparable.)
            call = "TAKE"
            agst = ("against: D-046 one position at a time — while %s is held "
                    "to its session-close exit this candidate cannot be "
                    "entered; it is committed as a seat and the replay "
                    "forfeits it. %s" % (r["dup_of"], r["against"][9:]))
        if r["cid"] in CONF_OVERRIDE:
            conf = CONF_OVERRIDE[r["cid"]]
        if r["cid"] in OVERRIDE:
            call, conf, primary, agst, novel = OVERRIDE[r["cid"]]
        pm = PREMORTEM.get(r["cid"], "")
        if not pm and call == "TAKE":
            pm = (DUP_PREMORTEM % r["dup_of"]) if r["dup_of"] else "-"
        out.append({
            "cid": r["cid"], "call": call, "conf": conf, "primary": primary,
            "against": agst, "interaction": "", "novel": novel,
            "premortem": pm,
            "minimal_pair": MINIMAL_PAIR.get(r["cid"], ""),
            "flip_threshold": FLIP.get(r["cid"], ""),
            "sections_read": DEEP.get(r["cid"], "TRIAGE-INDEX-ONLY"),
            "depth": "DEEP" if r["cid"] in DEEP else "TRIAGE",
            "taint": "CLEAN",
            "n_terms": r["n_terms"], "terms": r["terms"], "asset": i["asset"],
            "phase_dec": i["phase_dec"], "clock": i["clock"],
            "candidate_class": i["cls"]})

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    new = not os.path.exists(a.out)
    with open(a.out, "a") as fh:
        if new:
            fh.write("# E1 STUDY LEDGER — reader=opus-discretionary, era=E1, "
                     "block=STUDY, sheets_version=PORT-SHEETS-V1.1\n")
            fh.write("# Format: PORT_M2_SHEETS_SPEC §3 / READER_BRIEFING §1, "
                     "+ CC-M2-4/5 annotation columns. Rows appended per day.\n")
            fh.write("\t".join(cols) + "\n")
        for r in out:
            fh.write("\t".join(str(r[c]).replace("\t", " ") for c in cols)
                     + "\n")

    # ---- CC-M2-17.4: THE SEAL AUTO-RECORDS ITS OWN USED CASES -------------
    # The day-5 gap class: a seal appended a day-complete STUDY session to the
    # day ledger and the USED-CASE LEDGER never heard about it, so a session
    # that HAD been read stayed untainted and could have been drawn BLIND.
    # Recording is no longer a step a lane can forget — it is part of sealing.
    _new, _dup = UC.record_seal([r["cid"] for r in out], era="E1",
                                block="STUDY", mode=UC.MODE_STUDY,
                                rnd="E1D2", reader=READER,
                                path=a.used_case_ledger)
    sys.stderr.write("used-case ledger: +%d new, %d already recorded -> %s\n"
                     % (len(_new), _dup, a.used_case_ledger))

    n = sum(1 for r in out if r["call"] == "TAKE")
    sys.stderr.write("sealed %d rows (%d TAKE) -> %s\n" % (len(out), n, a.out))


if __name__ == "__main__":
    main()
