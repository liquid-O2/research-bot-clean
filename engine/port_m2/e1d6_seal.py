#!/usr/bin/python3
"""E1 STUDY DAY 6 — seal the day ledger (CC-M2-3/4/5 annotations).

Takes `e1d6_policy.py` arm CORE+READER (core + the committed cell-side table +
the V2/V3 vetoes) and emits the committed ledger rows with every CC-M2-4/5
annotation: taint, a pre-mortem per SEAT, minimal pairs and flip thresholds on
the deep reads, and the per-call section log.

DRAW.  The next chronological STUDY session per asset strictly after
2021-07-07, warm-ups excluded (CC-M2-8.1): SI/HG/NKD **2021-07-08** — 1,618
candidates (SI 515, HG 389, NKD 714).  USED_CASE_LEDGER: 0 prior hits.

THE DAY IS THE CC-M2-15.5/16.1 SIDE-EVIDENCE STUDY.  The primary object is the
CELL-SIDE LEDGER (`provenance/port_m2/E1D6_CELL_SIDE_LEDGER.md`): nine ex-ante
(asset, phase) side calls with named evidence, each committed BEFORE its cell's
first candidate row, from as-of stepper briefs, with two competing declared
estimators (P029 PHASE_SIDE_PRIOR and the reader's own E1D6-CS composite) whose
mirror-law failures are registered before the day.

AS-OF DISCIPLINE (defect D18b, CC-M2-16.4).  Everything ran through HEAD's
stepper: `triage_index.py --drive-step 300 --drive-out E1D6_DRIVE` (275 verified
prefixes) drove the cell briefs AND the veto walk, and `e1d6_asofwalk.py` proves
PREFIX-IDENTITY (1,618 rows, 0 mismatches between the call at a row's own reveal
cut and the day-complete call) and re-derives the 9-cell seat chain
chronologically.  No day-complete table was scanned to choose a deep read.

TAINT.  `CLEAN;AS-OF-PREFIX` on every row; every TAKE additionally carries
`FORECAST-TRUTH-EXPOSED` (defect D19 — see the cell-side ledger §(iv)).
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e1d6_policy as POLICY                                   # noqa: E402

LEDGER = "/workspace/provenance/port_m2/E1_STUDY_LEDGER.tsv"
TAINT_SKIP = "CLEAN;AS-OF-PREFIX"
TAINT_TAKE = "CLEAN;AS-OF-PREFIX;FORECAST-TRUTH-EXPOSED"

SEATS = {
    ("HG", "TOKYO"): "HG-20210708-000681-L",
    ("NKD", "TOKYO"): "NKD-20210708-007320-L",
    ("SI", "TOKYO"): "SI-20210708-010937-L",
    ("HG", "LONDON"): "HG-20210708-025226-S",
    ("SI", "LONDON"): "SI-20210708-025234-S",
    ("NKD", "LONDON"): "NKD-20210708-033333-S",
    ("SI", "NY"): "SI-20210708-046843-S",
    ("HG", "NY"): "HG-20210708-046953-S",
    ("NKD", "NY"): "NKD-20210708-048737-S",
}

DEEP = {
    "SI-20210708-046843-S": "S1,S3,S4,S7,S8,S10,S13",
    "HG-20210708-046953-S": "S1,S3,S4,S7,S8,S10,S13",
    "SI-20210708-025234-S": "S3,S8,S10",
    "HG-20210708-000681-L": "S2,S3,S4,S8,S10,S11,S12",
    "NKD-20210708-048737-S": "S3,S8,S10",
}
THINKALOUD = "SI-20210708-046843-S"

PM = {}
PM["HG-20210708-000681-L"] = (
    "PRE-MORTEM (written before the call): this loses because 184 contracts is "
    "not a market. S8's 5m sflow is +48 on 70 (69% buy) and the 60s is +11 on "
    "13 — an imbalance made of six traders at 00:11 — and the whole session's "
    "volume so far IS the phase's 184. S3 says the bar needs $987.50 of "
    "BRAND-NEW range (phase H 4.3098, entry 4.3093) on a session at 5.8% of "
    "range_hat in a LOW vol regime (rv5/rv66 0.530). MEASURABLE BUT NOT YET "
    "PRESENT => flip threshold, not a veto (CC-M2-16.2 leaves only V2/V3 "
    "binding and neither fires: fuel is 165 of 184 trapped BELOW, i.e. WITH "
    "the long, and through_book is 9 of 9 clearing the ASK). THE TRIGGER I AM "
    "WATCHING: S10's developing VAH is 4.3090 with in_VA=0 — the mid is ABOVE "
    "the developing value on ten minutes of volume; if price re-enters the "
    "value area (mid < 4.3090) the long is buying a one-tick spike in an empty "
    "book.")
PM["NKD-20210708-007320-L"] = (
    "PRE-MORTEM (written before the call): this loses to the book, not to the "
    "thesis. S7's c2f_300 is 14.71 on a 5-minute volume of 35 contracts — the "
    "algos are quoting and cancelling, not trading — and cost_rt is $55 with a "
    "$25 one-tick spread, the worst cost/spread pair on the board. NKD's "
    "five-session record is 12 D-021 winners in 1,404 candidates, every one "
    "inside a cluster of 4-8 candidates spanning 30s-30min (ERA_NOTES §56); "
    "outside such a cluster this is a 6.5-hour hold that cannot pay. The "
    "opposing stream is already present but under both veto floors: 60s sflow "
    "-5 on 10 (50% opposed, but volume 10 < the 20-contract floor P018 "
    "requires). THE TRIGGER: if the 60-second volume clears 20 contracts while "
    "sflow stays <= -10% and slope1m turns negative, V3 fires and the seat "
    "moves.")
PM["SI-20210708-010937-L"] = (
    "PRE-MORTEM (written before the call): THIS IS THE V2 CONFIGURATION AND "
    "THE VETO MISSES IT BY 4.6 POINTS OF PHASE VOLUME. S8's fuel map reads "
    "trapped above_mid=1,497 of phase_total=1,769 = 84.6% AGAINST this long, "
    "against V2's 90% floor; the adverse stream is running on every horizon "
    "(phase sflow -237 on 1,769, 5m -107 on 525 = 20.4% opposed, 60s -9 on "
    "85) and through_book_600s is 7 prints through the BID against 1 through "
    "the ask. S10 puts the mid $175 below the developing POC with in_VA=0 "
    "(below VAL). Every fact I would need for the veto is present; the FAMILY "
    "THRESHOLD is what stands between this row and a SKIP, and CC-M2-16.2 "
    "forbids me from moving a graded family's threshold mid-day on one row. "
    "So the take stands and the threshold is elicited instead (see "
    "flip_threshold). If this loses, the V2 floor is the number to census.")
PM["HG-20210708-025226-S"] = (
    "PRE-MORTEM (written before the call): this loses because there is no "
    "phase yet. The LONDON phase is 26 SECONDS old with 10 contracts in it; "
    "S3's phase H 4.3010 and L 4.3000 are one tick apart, so ext_needed reads "
    "$1,000 for the trivial reason that the range is $25. The short's whole "
    "content is the cross-asset read committed at the cell open (SI -$1,450 "
    "with 86% of its Asian volume trapped above). THE TRIGGER I AM WATCHING: "
    "S10's developing VAL is 4.2950, $125 below the entry — if price holds "
    "above it through the first hour of London, the sellers have no room and "
    "this becomes the day-3 give-back (a directionally correct short that "
    "closes at a third of its peak). MEASURABLE BUT NOT PRESENT => flip "
    "threshold.")
PM["SI-20210708-025234-S"] = (
    "PRE-MORTEM (written before the call): the 30-minute stream is against me. "
    "S8 reads 30m sflow +69 on 410 contracts — BUYING — while I sell the "
    "London open at the session low, and the shorter horizons are only "
    "mildly negative (60s -9 on 65, 5m -11 on 93, both under the 10% P018 "
    "floor). SI has already fallen $1,537.50 on the session and sits $437.50 "
    "BELOW its developing POC (26.0400) with in_VA=1: a mean-reversion bounce "
    "to value costs $437.50 against a $900 wall, so the wall is one bounce "
    "away and the certificate needs the low to break instead. MEASURABLE BUT "
    "NOT PRESENT => flip threshold: if 5m sflow turns positive at >= 5% of its "
    "own volume while price holds 25.9525, the Asian sellers are done and this "
    "short is the one being absorbed (P007, read against me for once).")
PM["NKD-20210708-033333-S"] = (
    "PRE-MORTEM (written before the call): I am selling an exhausted move. "
    "S3's COVERAGE LONDON is 304.6% and the session is EXPANDED at 152.4% of "
    "range_hat; S10 puts the mid $1,250 below the developing POC with in_VA=0. "
    "The trade-side extreme is 2,733 SECONDS old (T3 passes at 3,600s but "
    "barely), so this is a chase, not a rejection — and the momentum family is "
    "3-for-3 value-destroying (ERA_NOTES §34). The book is 8 events and 13 "
    "contracts in the last minute on a $55 cost_rt. THE TRIGGER: the "
    "FVOL_LADDER_RS level $7.90 above the mid — if it holds as support on the "
    "first test rather than breaking, the short is late and the $900 wall sits "
    "one squeeze away.")
PM["SI-20210708-046843-S"] = (
    "PRE-MORTEM (written before the call; the day's think-aloud row): this "
    "loses if the London buyers are still there. The NY phase is 43 seconds "
    "old, its LOW (26.2225) is 4 seconds old, and ext_needed is $975 — the "
    "whole bar is brand-new range. The thesis is that value was left $1,288 "
    "below (S10 developing POC 25.9700, VAH 26.1500, d_POC +$1,287.50, "
    "in_VA=0) after a $1,450 London rally, and that the NY session sells what "
    "London bought (P029). S8 supports it on every horizon (60s -30 on 149, "
    "5m -40 on 345, 30m -29 on 1,109, session -541 on 21,453) and "
    "through_book_600s is 6 bid vs 3 ask with the three newest prints all "
    "through the BID. WHAT KILLS IT, and it is measurable and NOT yet present: "
    "S4 puts a four-object shelf 6 to 13 dollars UNDER the entry — OR_EXT "
    "TOKYO|OR30|k0.5|-1 at 26.2263 (VIRGIN, V=1), OR_EXT LONDON|OR60|k2.0|+1 "
    "at 26.2250 (PENDING, tc=2), OR_EXT TOKYO|OR60|k0.5|-1 at 26.2250 "
    "(VIRGIN) and PRIOR_DAY SETTLE at 26.2250 — n_conf_max=3 at one price. "
    "THE TRIGGER: if that shelf holds its FIRST test (S4 outcome flips to "
    "REJECT rather than BREAK), I am selling into support that four families "
    "agree on, and the day-3 give-back is the best case.")
PM["HG-20210708-046953-S"] = (
    "PRE-MORTEM (written before the call): I AM SELLING INTO A BUYING STREAM "
    "and saying so before the outcome. S8 reads 5m sflow +115 on 303 (buy "
    "209 / sell 94) and 30m +220 on 1,559, and all 8 through_book_600s prints "
    "clear the ASK. The only reason this is a short is P007 "
    "ABSORPTION_NO_RESPONSE in its ORIGINAL form: that aggression has NOT "
    "extended the phase high (4.2468 printed at 13:00:14, 139 seconds ago, and "
    "the mid is 4.2430 below it). P007 is a COUNTERWEIGHT in the ledger and "
    "was FALSIFIED as an entry object on day 4, so this is the weakest "
    "evidential footing of the day's three NY seats. THE TRIGGER, measurable "
    "and not present: any print above 4.2468. If the buyers extend the high, "
    "the absorption read is wrong and the 88% of LONDON volume trapped above "
    "the mid was simply where the volume was, not supply.")
PM["NKD-20210708-048737-S"] = (
    "PRE-MORTEM (written before the call): the capacity arithmetic says do not "
    "do this. S3's COVERAGE SESSION is 254.0% with unspent -$2,379.80 — NKD "
    "has spent two and a half times its expected session move — and I am "
    "selling $362.50 off the NY low with the trade-side extreme 1,740 seconds "
    "old. S10 puts the mid $2,837.50 below the developing POC and $937.50 "
    "below VAL with in_VA=0. The bar needs $1,000 of further new range from a "
    "book that traded 11 contracts in the last minute at $55 round-trip cost. "
    "P002/P003/P014/P017 all point LONG here and all four are 0-for-3 as "
    "refusals, which is why the committed cell call stands — but this is the "
    "row where the mean-reversion family gets its cleanest test of the round. "
    "THE TRIGGER: a 5-minute buy imbalance >= 10% with price back above the NY "
    "high 27,670.")

VETO_SHORT = {
    "V2": ("VETO V2 (fuel-map overhang, RETAINED by CC-M2-16.2 as one of the "
           "two veto families that are net-positive refusals on all five study "
           "sessions): S8's FUEL MAP puts >= 90% of the phase's transacted "
           "volume against this trade AND the adverse stream is still running "
           "(5m sflow opposed at >= 10% of its own volume, or through_book_600s "
           "with the adverse side >= 2x on n >= 10). Measurable and present "
           "=> the would-be TAKE is a SKIP."),
    "V3": ("VETO V3 (P018 TWO_STREAM_OPPOSITION, RETAINED by CC-M2-16.2): S8 "
           "60s |sflow| >= 10% of a >= 20-contract 60s volume opposed to the "
           "trade AND S5 mid_slope_$/min(T-1m) opposed. Measurable and present "
           "=> the would-be TAKE is a SKIP."),
}

MINIMAL_PAIR = {
    "SI-20210708-046843-S": (
        "MINIMAL PAIR: SI-20210708-047304-L (13:08:24, same asset, same phase, "
        "461 seconds later, LONG) — SKIP. THE EXACT DIFFERENCE IS THE SIDE and "
        "what the side drags with it: the long's trade-side extreme is the NY "
        "LOW at 164s (T3 passes on both), its 5m sflow is +18 on 312 = 5.8% "
        "(T4 passes on both), its runway is 35,495s (T2 passes on both) and "
        "its ext_needed is $900 against my $975 — i.e. the CORE ADMITS THE "
        "LONG TOO and only the committed cell-side call refuses it. That is "
        "exactly what CC-M2-16.1 asked the day to measure: once the refusal "
        "core is saturated, the cell-side call IS the decision."),
    "HG-20210708-046953-S": (
        "MINIMAL PAIR: HG-20210708-046828-L (13:00:28, same asset, same phase, "
        "125 seconds EARLIER, LONG) — SKIP, and it is the row the HG/NY cell "
        "opened on. THE EXACT DIFFERENCE is the side; its runway is 35,971s "
        "and its trade-side extreme is the 14-second-old NY LOW, so the core "
        "reaches it as readily as it reaches my short. If HG/NY turns out to "
        "be a LONG cell, this pair prices the cell-side error at 125 seconds "
        "and zero core evidence."),
}

FLIP = {
    "SI-20210708-010937-L": (
        "FLIP THRESHOLD / V2 THRESHOLD ELICITATION (CC-M2-5.8): the binding "
        "number is S8's trapped-against share, 1,497 of 1,769 = 84.6% against "
        "V2's 90.0% floor. **A V2 floor at 0.84 vetoes this row**; at 0.85 it "
        "does not. Every other V2 clause is already satisfied (5m sflow -107 "
        "on 525 = 20.4% opposed, well over the 10% arm, and through_book 7 bid "
        "vs 1 ask). This is the day's single most valuable elicited number "
        "because V2 is one of only two surviving veto families and its "
        "threshold has never been censused — it was minted at 99.94% and "
        "94.1% on day 5 and has never been tested near its floor."),
    "SI-20210708-046843-S": (
        "FLIP THRESHOLD: the take turns on the OR_EXT/PRIOR_DAY shelf at "
        "26.2250-26.2263, $6.30-$12.50 under the entry with n_conf_max=3. If "
        "the nearest virgin OR_EXT sat $75 lower instead of $6.30 lower, the "
        "short would have a clear $75 before its first test and I would grade "
        "it B rather than the C the sigma_to_exit scale gives it. Core side: "
        "T4 is 5m |sflow|/vol = 40/345 = 11.6% against the 5% floor — sflow "
        "above -17 and this row is a SKIP on the core."),
    "HG-20210708-046953-S": (
        "FLIP THRESHOLD: one price. The absorption read dies on any print "
        "above the NY high 4.2468 ($95 above the entry). Core side: T5 as "
        "REPAIRED (CC-M2-16.4) passes on the ABSOLUTE arm (5m vol 303 >= 200); "
        "under the DAY-5 form it would also have passed (303 >= 200 and "
        "303 >= 8% of the 110-contract phase volume), so the repair is not "
        "what admits this row — the repair's effect is measured on NKD, where "
        "the day-5 form refused 5m volumes of 118-140 at 41-45% of phase "
        "volume."),
    "NKD-20210708-048737-S": (
        "FLIP THRESHOLD: T5's REPAIR is what admits this row and it is the "
        "clean test CC-M2-16.4 ordered. 5m vol = 26 contracts against a phase "
        "volume of 149 = 17.4%, i.e. over the 8% relative clause and far under "
        "the 200 absolute floor. **Under the day-5 form (`>=200 AND (...)`) "
        "this row is a SKIP and NKD has no NY seat at all.** If it pays, the "
        "repair is worth its own line in the ledger; if it loses, the absolute "
        "floor was doing real work on NKD and ERA_NOTES §55 needs qualifying."),
}

NOVEL = {
    "SI-20210708-046843-S": (
        "novel: P029 PHASE_SIDE_PRIOR (registered prospectively, CC-M2-4.3, "
        "and declared with its full backtest in the cell-side ledger before "
        "any day-6 cell was called). In E1, a cell's winner side is predicted "
        "by its PHASE: TOKYO/LONDON -> LONG, NY -> SHORT, 11 of the 12 "
        "winner-bearing (asset, phase) cells of the five unblinded study "
        "sessions. It is ONE FIELD (S1 phase_dec). Its mirror-law status is "
        "registered as FAILING (it beats its mirror on 4 of 5 sessions and "
        "loses on 2021-07-02, the only session containing a scheduled "
        "release). The conditional repair that would make it 12/12 is NOT "
        "traded — that is the P014/P026/P028 error and the round has three "
        "corpses for it."),
    "SI-20210708-025234-S": (
        "novel: E1D6-CS (registered prospectively), the reader's own "
        "six-component ex-ante cell-side composite — prior-phase close "
        "position, session net so far, overnight continuation, fuel overhang, "
        "cross-asset metals coherence, multi-day level position. Backtested "
        "before the day on all 45 cells of the five unblinded sessions: 4 "
        "right / 6 wrong against its own mirror's 6/4, i.e. INADMISSIBLE under "
        "CC-M2-13.1 and registered as such. It is logged per cell anyway "
        "because its COMPONENTS, with their labels, are the phase-side "
        "classifier's training-evidence seed (CC-M2-16.1)."),
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--index", required=True)
    p.add_argument("--ledger", default=LEDGER)
    p.add_argument("--arms", default="")
    a = p.parse_args()

    with open(a.index) as fh:
        rows = list(csv.DictReader([ln for ln in fh if not ln.startswith("#")],
                                   delimiter="\t"))
    calls = POLICY.call_day(rows, arm="CORE+READER")
    by_cid = {r["cid"]: r for r in rows}
    for cid in list(DEEP) + list(MINIMAL_PAIR) + list(FLIP) + list(PM):
        if cid not in by_cid:
            raise SystemExit("seal: unknown cid %s" % cid)

    seat_taken, out = {}, []
    for c in calls:
        cid = c["cid"]
        cell = (c["asset"], c["phase_dec"])
        if c["call"] == "TAKE" and cell not in seat_taken:
            seat_taken[cell] = cid
        prem = ""
        if cid in PM:
            prem = PM[cid]
        elif c["vetoes"]:
            prem = " ".join(VETO_SHORT[t] for t in c["vetoes"].split("+"))
        elif c["call"] == "TAKE":
            prem = ("PRE-MORTEM INHERITED from the %s/%s seat %s: under "
                    "CC-M2-10.3 phase-close seating the seat was spent at that "
                    "row and every later TAKE of this cell is forfeited, so "
                    "this row inherits its cell's pre-mortem rather than "
                    "pretending to a separate deep read."
                    % (cell[0], cell[1], SEATS[cell]))
        inter = ("cell_side_call=%s; P029=%s; E1D6-CS=%s; veto=%s; "
                 "seat_cell=%s/%s; seat_holder=%s"
                 % (c["cell_call"],
                    "LONG" if cell[1] in ("TOKYO", "LONDON") else "SHORT",
                    POLICY.CS_CELL[cell] or "NOCALL", c["vetoes"] or "none",
                    cell[0], cell[1], seat_taken.get(cell, "-")))
        out.append({
            "cid": cid, "call": c["call"], "conf": c["conf"],
            "primary": c["primary"], "against": c["against"],
            "interaction": inter, "novel": NOVEL.get(cid, ""),
            "premortem": prem,
            "minimal_pair": MINIMAL_PAIR.get(cid, ""),
            "flip_threshold": FLIP.get(cid, ""),
            "sections_read": DEEP.get(cid, "TRIAGE-INDEX-ONLY"),
            "depth": "DEEP" if cid in DEEP else "TRIAGE",
            "taint": TAINT_TAKE if c["call"] == "TAKE" else TAINT_SKIP,
            "n_terms": c["n_terms"],
            "terms": "%s|gate%d|veto:%s" % (
                "".join(str(c[k]) for k in POLICY.TERMS), c["side_gate"],
                c["vetoes"] or "-"),
            "asset": c["asset"], "phase_dec": c["phase_dec"],
            "clock": c["clock"], "candidate_class": c["cls"]})

    cols = ("cid call conf primary against interaction novel premortem "
            "minimal_pair flip_threshold sections_read depth taint n_terms "
            "terms asset phase_dec clock candidate_class").split()
    with open(a.ledger, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter="\t",
                           extrasaction="ignore", lineterminator="\n")
        for o in out:
            w.writerow(o)
    n_take = sum(1 for o in out if o["call"] == "TAKE")
    n_veto = sum(1 for o in calls if o["vetoes"])
    print("E1D6 sealed: %d rows appended (%d TAKE, %d SKIP), %d V2/V3 vetoes, "
          "%d deep reads" % (len(out), n_take, len(out) - n_take, n_veto,
                             len(DEEP)))
    for cell, cid in sorted(seat_taken.items()):
        print("   SEAT %-12s %s" % ("/".join(cell), cid))

    if a.arms:
        arms = {}
        for nm in POLICY.ARMS:
            arms[nm] = {x["cid"]: x["call"]
                        for x in POLICY.call_day(rows, arm=nm)}
        arms["READER_NOVETO"] = {
            x["cid"]: x["call"]
            for x in POLICY.call_day(rows, arm="CORE+READER",
                                     vetoes_on=False)}
        names = list(POLICY.ARMS) + ["READER_NOVETO"]
        with open(a.arms, "w", newline="") as fh:
            w = csv.writer(fh, delimiter="\t")
            w.writerow(["cid", "asset", "phase_dec", "clock", "side"]
                       + names + ["veto", "final"])
            for c in calls:
                cid = c["cid"]
                w.writerow([cid, c["asset"], c["phase_dec"], c["clock"],
                            c["side"]] + [arms[n][cid] for n in names]
                           + [c["vetoes"] or "-", c["call"]])
        print("wrote %s" % a.arms)


if __name__ == "__main__":
    sys.exit(main())
