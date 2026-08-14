#!/usr/bin/python3
"""E1 STUDY DAY 7 — seal the day ledger (CC-M2-3/4/5 annotations).

Takes `e1d7_policy.py` arm CORE+SEAT+SIDE (the moment core + the committed
STAGE-1 SEAT calls + the committed STAGE-2 SIDE calls + the V2/V3 vetoes) and
emits the committed ledger rows with every CC-M2-4/5 annotation: taint, a
pre-mortem per SEAT, minimal pairs and flip thresholds on the deep reads, and
the per-call section log.

DRAW.  The next chronological STUDY session per asset strictly after
2021-07-08, warm-ups excluded (CC-M2-8.1): SI/HG/NKD **2021-07-09** — 1,388
candidates (SI 315, HG 407, NKD 666).  USED_CASE_LEDGER: 0 prior hits.

THE DAY IS THE CC-M2-17.1 THREE-STAGE DECOMPOSITION.  The primary object is the
PER-CELL LEDGER (`provenance/port_m2/E1D7_CELL_LEDGER.md`): for each of the
day's nine cells a SEAT call and a SIDE call with named ex-ante evidence,
committed BEFORE that cell's first candidate row from as-of stepper briefs,
with the stage-1 rule (S1*) and the stage-2 primary (S2a/P031) PRE-REGISTERED
on the 54 cells of the six unblinded sessions — including S2a's mirror-law
FAILURE on 2021-07-02 and S1*'s named cost (it refuses the day-6 HG/LONDON
seat).  Four cells are called seat=YES; five are refused outright.

AS-OF DISCIPLINE (D18b).  Everything ran through HEAD's stepper:
`triage_index.py --drive-step 300 --drive-out E1D7_DRIVE` (277 verified
prefixes) drove the cell briefs, the seat/side calls and the veto walk, and
`e1d7_asofwalk.py` proves PREFIX-IDENTITY (1,388 rows, 0 mismatches between the
call at a row's own reveal cut and the day-complete call) and re-derives the
4-cell seat chain chronologically.  No day-complete table was scanned to choose
a deep read.

TAINT.  `CLEAN;AS-OF-PREFIX` on every row.  **No forecast_*.tsv / truth_*.tsv
was opened (CC-M2-17.2 + the D19 exposure class), so the day-6
FORECAST-TRUTH-EXPOSED stamp does not recur.**
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e1d7_policy as POLICY                                   # noqa: E402
import used_cases as UC                                        # noqa: E402

LEDGER = "/workspace/provenance/port_m2/E1_STUDY_LEDGER.tsv"
READER = "opus-discretionary"
TAINT_SKIP = "CLEAN;AS-OF-PREFIX"
TAINT_TAKE = "CLEAN;AS-OF-PREFIX"

SEATS = {
    ("NKD", "LONDON"): "NKD-20210709-032018-S",
    ("HG", "NY"): "HG-20210709-046818-L",
    ("SI", "NY"): "SI-20210709-047362-L",
    ("NKD", "NY"): "NKD-20210709-049879-L",
}

DEEP = {
    "NKD-20210709-032018-S": "S1,S2,S3,S7,S8,S9,S10,S13",
    "HG-20210709-046818-L": "S1,S2,S3,S7,S8,S9,S10,S13",
    "SI-20210709-047362-L": "S1,S2,S3,S7,S8,S9,S10,S13",
    "NKD-20210709-049879-L": "S1,S2,S3,S7,S8,S9,S10,S13",
}
THINKALOUD = "HG-20210709-046818-L"

PM = {}
PM["NKD-20210709-032018-S"] = (
    "PRE-MORTEM (written before the call): this loses to the EXIT CLOCK, not "
    "to the side. S13's exit_default is phase_close@13:00:00 with 14,782s of "
    "runway, and S3's COVERAGE LONDON says the LONDON phase's whole expected "
    "move is $516.50 with $291.50 unspent — I need $1,000 out of a phase the "
    "forecaster prices at half that, from a book that traded 45 contracts in "
    "the last minute at a $50 spread and $55 round trip. The cell-side "
    "evidence (HG/LONDON 0.807 trapped above; S10 d_POC +$2,425 with in_VA=0) "
    "is about DIRECTION and says nothing about whether a NKD LONDON phase can "
    "pay the bar. MEASURABLE AND ALREADY PRESENT, and it is a stage-1 miss "
    "the declared rule does not carry: S1* seats a cell on rv1800 and "
    "prior-cell travel and never asks what the BINDING EXIT allows. THE "
    "TRIGGER: if the mid is still inside 28,150-28,225 at 10:30, the phase "
    "will close before the move exists.")
PM["HG-20210709-046818-L"] = (
    "PRE-MORTEM (written before the call; the day's think-aloud row): I AM "
    "BUYING INTO A SELLING STREAM AND SAYING SO FIRST. S8 reads 60s sflow -55 "
    "on 250 (sell 151 / buy 96), 5m -104 on 437 and 30m -36 on 2,068; S7's "
    "60-second window is 1,182 events with c2f 1.87 and 19.7 reversals/s — "
    "this is a live, fast book and it is offered. The long's entire content is "
    "the committed cell-side call: SI/LONDON 10,455 of 11,699 contracts "
    "trapped BELOW and NKD/LONDON 0.842 BELOW, i.e. a cross-asset short base "
    "that must buy back (P031, 0.833 over six sessions, mirror-law FAILURE "
    "registered). Against it, S10 puts the mid $1,656 ABOVE the developing POC "
    "with in_VA=0 — the secondary instrument says SHORT and the declared "
    "procedure overrules it. THE TRIGGER, measurable and not yet present: if "
    "HG prints below the developing VAH 4.3180 ($682 under the entry, i.e. "
    "re-entering value) the 'trapped shorts must buy' reading is dead and what "
    "I called fuel was the footprint of a move that is over — P027's failure "
    "mode in P031's clothes.")
PM["SI-20210709-047362-L"] = (
    "PRE-MORTEM (written before the call): every flow horizon on this sheet is "
    "against me and I am taking it anyway. S8: 60s -12 on 18, 5m -35 on 159, "
    "30m -161 on 773, phase -113 on 427 — four horizons, all selling, the "
    "configuration P018/V3 was written for (it does not fire only because "
    "slope1m is "
    "not opposed at this second). S10 puts the mid $362.50 above the "
    "developing POC with in_VA=0, i.e. the secondary instrument leans SHORT "
    "here too. The long is the DECLARED OVERRIDE of S2a's literal form (which "
    "fired SHORT off HG's 80-contract-old NY block) in favour of its "
    "size-aware form (NKD/LONDON 0.842 trapped BELOW; HG/LONDON's 20,281 "
    "trapped shorts). THE TRIGGER: a print below the LONDON POC 25.8700 "
    "($1,088 under the entry) says the London buyers are gone and the "
    "'trapped shorts' were sellers all along; nearer term, if 5m sflow stays "
    "under -20% of its own volume for the next 15 minutes the absorption I am "
    "assuming is not happening.")
PM["NKD-20210709-049879-L"] = (
    "PRE-MORTEM (written before the call): this is a $55-round-trip trade in a "
    "book that traded 14 contracts in the last minute, and the capacity "
    "arithmetic is the worst on the board — S3's COVERAGE SESSION is 283% "
    "with unspent -$3,209 and the session has already travelled $4,962 = "
    "278% of range_hat. NKD's six-session record is 12 D-021 winners in 2,070 "
    "candidates, all inside tight clusters. The long rests on the same "
    "cross-asset short-base reading as HG/NY and SI/NY, so it is ONE BET "
    "TAKEN THREE TIMES. THE TRIGGER: S10 has the mid $412.50 above a "
    "developing POC of 28,350 with in_VA=1 — if price loses 28,350 the profile "
    "says the NY balance broke downward and the long is on the wrong side of "
    "a 283%-extended session.")


MINIMAL_PAIR = {
    "SI-20210709-047362-L": (
        "MINIMAL PAIR: SI-20210709-047052-S (13:04:12, same asset, same phase, "
        "310 seconds EARLIER, SHORT) — SKIP, and it is the row the SI/NY cell "
        "OPENED on. THE EXACT DIFFERENCE IS THE SIDE: the core admits both "
        "(the short's runway is 35,747s, its trade-side extreme is fresh, its "
        "5m sflow -88 on 284 = 31% clears T4/T5 more comfortably than my "
        "long's -35 on 159 = 22%), so the ONLY thing between them is the "
        "committed cell-side call. If SI/NY is a SHORT cell this pair prices "
        "the override at 310 seconds and the whole seat."),
    "HG-20210709-046818-L": (
        "MINIMAL PAIR: HG-20210709-046923-L (13:02:03, same asset, same phase, "
        "same SIDE, 105 seconds later) — SKIP, and the difference is neither "
        "side nor core: **V2+V3 both fire on it and neither fires on my seat "
        "row**. In 105 seconds the fuel map went from 14 above / 12 below of "
        "26 phase contracts to >= 90% against the long with the adverse stream "
        "running. The pair prices the day's veto families at 105 seconds of "
        "phase age: on the seat-spending row they are silent, on its immediate "
        "successor they are decisive — which is the ERA_NOTES §67 problem "
        "(a veto that cannot move a seat cannot move the replay) seen from the "
        "other side."),
    "NKD-20210709-032018-S": (
        "MINIMAL PAIR: NKD-20210709-032097-S (08:54:57, same asset, phase and "
        "SIDE, 79 seconds later) — SKIP on T1 alone (60s n=2 vol=4 against my "
        "row's n=9 vol=45). THE EXACT DIFFERENCE IS 79 SECONDS OF BOOK: NKD's "
        "LONDON tape is a sequence of dead minutes with occasional bursts, and "
        "the seat exists only in the bursts. This is why a cell-level seat "
        "call cannot be an entry rule on NKD."),
}

FLIP = {
    "NKD-20210709-032018-S": (
        "FLIP THRESHOLD (CC-M2-5.8): the binding number is the BINDING EXIT, "
        "not any term of the rule. This row's exit is the 13:00 LONDON phase "
        "close (14,782s) and S3 prices the whole LONDON phase at $516.50 of "
        "expected move with $291.50 unspent. **A stage-1 clause of the form "
        "'unspent on the BINDING PHASE row >= $1,000' refuses this seat**; "
        "S1c as pre-registered reads the SESSION row (-$2,497 on an EXPANDED "
        "day) and was measured as a non-signal (precision 0.293), so the "
        "phase-row form is a DIFFERENT and untested object. This is the "
        "number the post-mortem should census first if the cell is empty."),
    "HG-20210709-046818-L": (
        "FLIP THRESHOLD: the side call flips on one number — the cross-asset "
        "trapped-BELOW share. SI/LONDON is 0.894 and NKD/LONDON 0.842 against "
        "S2a's declared 0.75 floor; **at a floor of 0.90 S2a is SILENT on this "
        "cell and the seat is never taken**, because SI/LONDON alone would "
        "then have to carry it. Core side: T4 is 5m |sflow|/vol = 104/437 = "
        "23.8% against the 5% floor and T5 passes on the absolute arm (437 >= "
        "200), so the core is nowhere near binding here."),
    "SI-20210709-047362-L": (
        "FLIP THRESHOLD / THE DAY'S ELICITED NUMBER: the SI/NY side call turns "
        "on a MINIMUM SIZE for a cross-asset overhang block. HG's NY block was "
        "80 contracts old and 0.9125 trapped ABOVE (fires SHORT); NKD/LONDON "
        "was 1,613 contracts and 0.842 trapped BELOW (fires LONG). **Any size "
        "floor between 81 and 1,612 contracts gives the cell to LONG; a floor "
        "of 0 gives it to SHORT.** I measured the 200-contract floor form on "
        "the six unblinded sessions before calling the cell (6 right / 1 wrong "
        "= 0.857 with zero sessions lost, against the literal form's 10/2 = "
        "0.833 with one session lost) and took the size-aware reading. If "
        "SI/NY is a SHORT cell, the size floor is what lost it and the "
        "as-backtested form should be restored."),
}

NOVEL = {
    "NKD-20210709-032018-S": (
        "novel: S1* CELL-SEAT RULE (registered prospectively, CC-M2-4.3), the "
        "first executable form of CC-M2-17.1's stage 1 — `rv1800 >= 250 OR "
        "(rv1800 >= 150 AND the prior cell of this asset travelled >= $1,000 "
        "of range)`, both thresholds taken from P030's published band edges "
        "and the D-021 bar, settled on the POOLED 54-cell pool of the six "
        "unblinded sessions (16 cells YES, 11 with winners, precision 0.688 "
        "against a 0.315 base rate, winner recall 0.884) and never on a "
        "replay. The PRIOR-CELL TRAVEL term (S1b) is new this day: it asks "
        "whether this asset's previous phase actually paid a $1,000 "
        "certificate."),
    "HG-20210709-046818-L": (
        "novel: P031 CROSS_ASSET_FUEL_OVERHANG promoted from a one-session "
        "anecdote (2 right / 1 wrong on 2021-07-08) to the day's PRIMARY side "
        "instrument on a six-session pre-registration — 10 right / 2 wrong / 5 "
        "silent (0.833) against its mirror's 0.167, with its MIRROR-LAW "
        "FAILURE (it loses 2021-07-02, the release session) registered before "
        "any cell was called. Its companion measurement is the six-session "
        "confirmation that P009's OWN-asset reading of the SAME field is "
        "anti-predictive (0.417 vs its mirror's 0.583) — the population-scale "
        "version of the day-6 sign inversion."),
}

VETO_SHORT = {
    "V2": ("VETO V2 (fuel-map overhang, RETAINED by CC-M2-16.2 as one of the "
           "two veto families that are net-positive refusals on all five study "
           "sessions; sole-block a sixth on 2021-07-08): S8's FUEL MAP puts "
           ">= 90% of the phase's transacted volume against this trade AND the "
           "adverse stream is still running (5m sflow opposed at >= 10% of its "
           "own volume, or through_book_600s with the adverse side >= 2x on "
           "n >= 10). Measurable and present => the would-be TAKE is a SKIP."),
    "V3": ("VETO V3 (P018 TWO_STREAM_OPPOSITION, RETAINED by CC-M2-16.2 on "
           "pooled counts — and 2021-07-08 was its worst session, 170 "
           "sole-blocks at -$104.15 with TEN winners refused): S8 60s |sflow| "
           ">= 10% of a >= 20-contract 60s volume opposed to the trade AND S5 "
           "mid_slope_$/min(T-1m) opposed. Measurable and present => the "
           "would-be TAKE is a SKIP."),
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--index", required=True)
    p.add_argument("--ledger", default=LEDGER)
    p.add_argument("--arms", default="")
    p.add_argument("--used-case-ledger", default=UC.LEDGER,
                   help="D-035.2 used-case ledger the seal records into "
                        "(CC-M2-17.4); tests point it elsewhere")
    a = p.parse_args()

    with open(a.index) as fh:
        rows = list(csv.DictReader([ln for ln in fh if not ln.startswith("#")],
                                   delimiter="\t"))
    calls = POLICY.call_day(rows, arm="CORE+SEAT+SIDE")
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
        inter = ("cell_seat_call=%s; cell_side_call=%s; P029=%s; veto=%s; "
                 "cell=%s/%s; seat_holder=%s"
                 % ("YES" if POLICY.SEAT_CELL[cell] else "NO",
                    c["cell_call"],
                    "LONG" if cell[1] in ("TOKYO", "LONDON") else "SHORT",
                    c["vetoes"] or "none",
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

    # ---- CC-M2-17.4: THE SEAL AUTO-RECORDS ITS OWN USED CASES -------------
    # The day-5 gap class: a seal appended a day-complete STUDY session to the
    # day ledger and the USED-CASE LEDGER never heard about it, so a session
    # that HAD been read stayed untainted and could have been drawn BLIND.
    # Recording is no longer a step a lane can forget — it is part of sealing.
    _new, _dup = UC.record_seal([r["cid"] for r in out], era="E1",
                                block="STUDY", mode=UC.MODE_STUDY,
                                rnd="E1D7", reader=READER,
                                path=a.used_case_ledger)
    sys.stderr.write("used-case ledger: +%d new, %d already recorded -> %s\n"
                     % (len(_new), _dup, a.used_case_ledger))

    n_take = sum(1 for o in out if o["call"] == "TAKE")
    n_veto = sum(1 for o in calls if o["vetoes"])
    print("E1D7 sealed: %d rows appended (%d TAKE, %d SKIP), %d V2/V3 vetoes, "
          "%d deep reads" % (len(out), n_take, len(out) - n_take, n_veto,
                             len(DEEP)))
    for cell, cid in sorted(seat_taken.items()):
        print("   SEAT %-12s %s" % ("/".join(cell), cid))

    if a.arms:
        arms = {}
        for nm in list(POLICY.ARMS) + ["CORE+SEAT+SIDE"]:
            arms[nm] = {x["cid"]: x["call"]
                        for x in POLICY.call_day(rows, arm=nm)}
        arms["READER_NOVETO"] = {
            x["cid"]: x["call"]
            for x in POLICY.call_day(rows, arm="CORE+SEAT+SIDE",
                                     vetoes_on=False)}
        names = list(POLICY.ARMS) + ["CORE+SEAT+SIDE",
                                        "READER_NOVETO"]
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
