#!/usr/bin/python3
"""E1 STUDY DAY 8 — seal the day ledger (CC-M2-3/4/5 annotations).
THE FINAL STUDY DAY OF THE E1 ROUND.

Takes `e1d8_policy.py` arm CORE+SEAT — the moment core (T1..T5, T5 repaired) +
V2 + the CORRECTED ROLLING stage-1 state (`unspent_bind >= $1,000` read at
every row) — and emits the committed ledger rows with every CC-M2-4/5
annotation: taint, a pre-mortem per seat, minimal pairs and flip thresholds on
the deep reads, and the per-call section log.

DRAW.  The next chronological STUDY session per asset strictly after
2021-07-09, warm-ups excluded (CC-M2-8.1): SI/HG/NKD **2021-07-12** (Monday) —
949 candidates (SI 327, HG 304, NKD 318).  USED_CASE_LEDGER: 0 prior hits.

THE DAY RUNS THE CC-M2-19 CORRECTED STACK.  The primary object is the PER-CELL
LEDGER (`provenance/port_m2/E1D8_CELL_LEDGER.md`): nine SIDE calls with named
evidence, each committed BEFORE that cell's first candidate row (composition
order SIDE > SEAT > MOMENT, CC-M2-19.2), on top of a stage-1/stage-2
PRE-REGISTRATION run over the seven unblinded sessions.

THE DECLARED OVERRIDE (CC-M2-12.6, with the backtest on record pre-seal): the
policy does NOT gate on the reader's own side calls and does NOT gate on
`rv1800 >= 250`.  Both were pre-registered and both are measured to destroy
value in one-position phase-close replay over seven sessions — the rv1800 gate
by $7,562.50, with its mechanism isolated (of the 64 seats CORE spends, the 41
whose rolling state is CLOSED average +$201.86 against +/-$111.52 for the 23
that are OPEN).  All gated arms are reported at unblinding so the override is
scored against the thing it overrode.

AS-OF DISCIPLINE (D18b).  `triage_index.py --drive-step 300 --drive-out
E1D8_DRIVE` (277 verified prefixes) drove the cell panels and the row walk;
`e1d8_asofwalk.py` proves PREFIX-IDENTITY (949 rows, 0 mismatches) and
re-derives the 3-cell seat chain chronologically.  No day-complete table was
scanned to choose a deep read.

TAINT.  `CLEAN;AS-OF-PREFIX` on every row.  No forecast_*.tsv / truth_*.tsv was
opened, so the day-6 FORECAST-TRUTH-EXPOSED stamp does not recur.
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import e1d8_policy as POLICY                                   # noqa: E402
import used_cases as UC                                        # noqa: E402
import warmup_draw as WD                                       # noqa: E402

LEDGER = "/workspace/provenance/port_m2/E1_STUDY_LEDGER.tsv"
READER = "opus-discretionary"
TAINT = "CLEAN;AS-OF-PREFIX"

SEATS = {
    ("SI", "TOKYO"): "SI-20210712-010922-L",
    ("SI", "LONDON"): "SI-20210712-027269-L",
    ("SI", "NY"): "SI-20210712-046931-L",
}
DEEP = {c: "S1,S2,S3,S4,S5,S7,S8,S9,S10,S13" for c in SEATS.values()}
THINKALOUD = "SI-20210712-027269-L"

PM = {}
PM["SI-20210712-010922-L"] = (
    "PRE-MORTEM (written before the call): this is a LONG entered AT the phase "
    "high and it dies to the CLOCK and the ARITHMETIC, not to the side. S3 "
    "gives room_phase $50 and ext_needed $962-950 — the mid is 26.23 against a "
    "phase_H of 26.24, so essentially the ENTIRE $1,000 bar has to come from "
    "brand-new range — and the binding exit is the 07:00 TOKYO close, 14,278s "
    "away, on an INSIDE day that has travelled $400. The freshness term is "
    "nominal here: `extreme_age_trade_side = 3,580s` sits TWENTY SECONDS "
    "inside T3's 3,600s ceiling, so this is a mid-leg continuation entry "
    "wearing a rejection's clothes (the day-1 T7 widening is what created it). "
    "MEASURABLE AND ALREADY PRESENT: SI/TOKYO is 0-for-7 winner-bearing cells "
    "across this round — no SI TOKYO cell has ever held a D-021 winner. THE "
    "TRIGGER: if the mid is still inside 26.20-26.26 at 04:30 the TOKYO phase "
    "will close before the move exists, and the $50 of room means every dollar "
    "of the certificate is new range that never came.")
PM["SI-20210712-027269-L"] = (
    "PRE-MORTEM (written before the call; the day's think-aloud row): I CALLED "
    "THIS CELL SHORT AND THE SEAT IS A LONG — and my own flip threshold, "
    "committed at cell #4 before this cell's first candidate row, IS "
    "SATISFIED AT THIS ROW: I wrote that the SHORT flips to LONG if 5m sflow "
    "holds >= +10% of its own volume, and here it is `+33 on 297 = 11.1%` "
    "with `60s +26 on 42 = 62%`. The long's content is real: a phase low "
    "printed 147 seconds ago, NINE of thirteen through-book prints clearing "
    "the BID while price refuses to extend that low (P007 ABSORPTION_NO_"
    "RESPONSE exactly as stated — whose DIRECTION was falsified on E1D4 and "
    "whose magnitude floor survives), and S10 putting the mid $662.50 BELOW "
    "the developing POC with in_VA=0. THE DEATH MECHANISM: the medium streams "
    "are still selling — `30m -28 on 610`, `phase -32 on 622` — and SI has "
    "been a one-way tape all session (-$400 at pos 0.00 into this open). "
    "Absorption that is only a pause in a one-way tape is a $900 wall with "
    "extra steps. THE TRIGGER, measurable and not yet present: a print below "
    "26.06 — the 147-second-old phase low — says the absorption failed and "
    "the seller was never done.")
PM["SI-20210712-046931-L"] = (
    "PRE-MORTEM (written before the call): this is the OPEN-DYNAMICS class at "
    "the NY open on a session that has ALREADY SPENT 96.4% of its expected "
    "range (`day_type AT_RANGE`, `range_so_far $2,150`), entered LONG against "
    "my own committed cell-side call, needing `ext_needed $962.50` of "
    "brand-new range out of `room_phase $37.50`. The field that frightens me "
    "is `rv_collapse = rv1800/rv60 = 7.41`: ERA_NOTES §3 flagged exactly this "
    "ratio above 8 on BOTH of the warm-up's zero-MAE wall stop-outs — the "
    "vol that produced the move has already collapsed at the decision second "
    "— and 7.41 is inside a rounding error of it. The book agrees: "
    "`trades_min 12`, `60s 12/28 sflow -4`, `5m -10 on 194`; only the 30m is "
    "bid (+28 on 689). THE TRIGGER: if the mid loses 25.99 (the 130-second-old "
    "phase low) the open-dynamics thesis is dead and the $900 wall is the only "
    "thing between here and the session close 35,868 seconds away.")

MINIMAL_PAIR = {
    "SI-20210712-010922-L": (
        "MINIMAL PAIR: SI-20210712-011129-S (03:05:29, same asset, same phase, "
        "207 seconds LATER, SHORT) — SKIP, and it passes ALL FIVE core terms, "
        "R2b, and both vetoes, exactly as my seat does. **THE EXACT "
        "DIFFERENCE IS 207 SECONDS AND THE SIDE**, and nothing else: its "
        "trade-side extreme is 19 seconds old against my row's 3,580, and its "
        "ext_needed is $637.50 against my $950. Under CC-M2-10.3 seating the "
        "earlier row spends the seat however much better the later one looks. "
        "If SI/TOKYO is a SHORT cell this pair prices the whole seat at 207 "
        "seconds — and it is the cleanest statement this round has of why the "
        "mechanical EARLIEST baseline is so hard to beat."),
    "SI-20210712-027269-L": (
        "MINIMAL PAIR: SI-20210712-027549-S (07:39:09, same asset and phase, "
        "280 seconds later, SHORT) — SKIP, and it too passes all five core "
        "terms, R2b and both vetoes. **THE EXACT DIFFERENCE IS THE SIDE AND "
        "280 SECONDS**, and the SHORT is the side I committed for this cell. "
        "The one field that separates them on quality is the rejection object: "
        "my long's trade-side extreme is 147 seconds old, the short's is "
        "2,263 seconds old — the long has a fresh low to lean on and the short "
        "has a 38-minute-old high. If SI/LONDON is a SHORT cell, this pair "
        "prices my committed side call at 280 seconds and the entire seat."),
    "SI-20210712-046931-L": (
        "MINIMAL PAIR: SI-20210712-047528-S (13:12:08, same asset and phase, "
        "597 seconds later, SHORT) — SKIP, all five terms, R2b and both vetoes "
        "passing. **THE EXACT DIFFERENCE IS THE SIDE AND ~10 MINUTES**, and "
        "again the SHORT is my committed cell call. Both need ~$975 of "
        "brand-new range; both sit inside developing value (in_VA=1). This is "
        "the third pair of the day with the same shape: on every one of the "
        "three seats the reader's own side call had an equally-admitted "
        "candidate available within ten minutes and the seat went to the "
        "earliest row regardless."),
}

FLIP = {
    "SI-20210712-010922-L": (
        "FLIP THRESHOLD (CC-M2-5.8): the binding number is T3's FRESHNESS "
        "CEILING. `extreme_age_trade_side = 3,580s` against T3's 3,600s — "
        "**twenty seconds of margin**. Any freshness ceiling in [148s, 3,579s] "
        "refuses this row and hands the SI/TOKYO seat to "
        "SI-20210712-011129-S (SHORT, +207s, extreme 19s old). The 3,600s "
        "ceiling is itself a day-2 widening of the original 900s window, "
        "adopted because three blocked rows were winners — so this seat exists "
        "because of a threshold change made six sessions ago on n=3. Secondary "
        "number: `ext_needed $950` — an ext_needed ceiling anywhere below $950 "
        "also refuses it, and P017's ceiling is 0-for-4 as a refusal."),
    "SI-20210712-027269-L": (
        "FLIP THRESHOLD / THE DAY'S ELICITED NUMBER, AND IT FIRED: at cell #4, "
        "before this cell's first candidate row existed, I committed 'this "
        "SHORT call flips to LONG if f5m_sflow holds >= +10% of its own "
        "5-minute volume while the mid stays above the TOKYO low'. **At the "
        "seat row f5m_sflow is +33 on 297 = 11.1%.** The threshold I elicited "
        "from myself is met at the exact row the policy seats, on the side the "
        "policy takes and against the side I called. Whatever the outcome, "
        "this is the round's first case of an elicited flip threshold being "
        "satisfied inside the same session it was written in, and it is on "
        "record before S14. Second number: at an R2b implementation that "
        "REFUSED rather than PASSED on a '.' `unspent_bind`, SI would be "
        "deleted from this entire day and this seat would not exist "
        "(defect D22, below)."),
    "SI-20210712-046931-L": (
        "FLIP THRESHOLD: `rv_collapse = rv1800/rv60 = 7.41`. ERA_NOTES §3 "
        "named the >= 8.0 band as the marker of the warm-up's two zero-MAE "
        "wall stop-outs (price ran straight to its peak and was stopped on the "
        "give-back). **A wall-risk refusal at rv_collapse >= 7.0 refuses this "
        "row; at >= 8.0 it stands.** The 0.59 between those two numbers is the "
        "whole seat, and the band has never been censused — it is one ratio "
        "over the whole population and ERA_NOTES §8.3 has carried it as an "
        "open question since the warm-up. Third number: `ext_needed $962.50` "
        "against `room_phase $37.50` on a session at 96.4% of range_hat."),
}

NOVEL = {
    "SI-20210712-010922-L": (
        "novel: **R2b — `unspent_bind >= $1,000` evaluated at EVERY ROW** — is "
        "the CC-M2-19.1 rolling stage-1 state in the ERA_NOTES §77 BINDING-ROW "
        "form, and it is the FIRST COUNT EVER TAKEN OF P014 CAPACITY_TO_BAR, "
        "which the pattern ledger has carried as DEAD at n_support=0 / "
        "n_against=0 since the warm-up — i.e. killed without ever being "
        "counted. Pooled over seven day-complete sessions (8,077 rows, 484 "
        "winners): 2,540 rows, 222 winners, 8.74% win rate = 1.46x lift, and "
        "the ONLY arm of the entire stage-1 sweep with a POSITIVE mean "
        "certificate (+$9.17/row). In one-position phase-close replay it is "
        "worth +$2,471.25 over CORE across the same seven sessions and lifts "
        "capture 0.096 -> 0.199."),
    "SI-20210712-027269-L": (
        "novel: **THE SEAT-SPENDER SPLIT OF A CONCENTRATOR** — CC-M2-17.4 "
        "ordered veto censuses to report the seat-spender sub-population "
        "separately; this day generalises the instrument to CONCENTRATORS and "
        "the result inverts the round's best-supported object. `rv1800 >= 250` "
        "at the row holds 449 of 484 winners (92.8%) and refuses at 0.29x, and "
        "**of the 64 seats the moment core actually spends over seven "
        "sessions, the 41 whose rolling state is CLOSED average +$201.86 while "
        "the 23 that are OPEN average -$111.52**; as a gate it costs "
        "-$7,562.50. A winner-density concentrator can be strongly real over "
        "the POOL and anti-predictive on the sub-population that spends the "
        "seat, because the seat goes to the earliest admitted row of a seating "
        "window and `rv1800` is high only after a move has happened. This is "
        "the same diagnosis ERA_NOTES §69/§79 gave the dead A grade, now with "
        "a receipt at the seat."),
    "SI-20210712-046931-L": (
        "novel: **DEFECT D22 — a capacity term with a PASS-ON-REFUSED clause "
        "is silently an ASSET SELECTOR.** `unspent_bind` is populated on "
        "304/304 HG rows and 318/318 NKD rows of this session and on 0/327 SI "
        "rows (SI's fvol is REFUSED for the fifth study session, ERA_NOTES "
        "§16). R2b therefore refuses ~99% of HG and ~96% of NKD rows and 0% of "
        "SI rows, and the day's three seats are all SI by construction rather "
        "than by judgement. The pre-registration's +$7,782.50 already embeds "
        "this asymmetry (SI's fvol is refused on five of the seven study "
        "sessions), so the number is honest — but any capacity term shipped to "
        "the model must carry an explicit REFUSED policy and a fvol-"
        "availability feature beside it, or it will encode 'trade the asset "
        "whose capacity we cannot measure'."),
}

VETO_SHORT = {
    "V2": ("VETO V2 (fuel-map overhang, RETAINED by CC-M2-16.2; the only veto "
           "family with a positive seven-session replay record, +$937.50 over "
           "CORE): S8's FUEL MAP puts >= 90% of the phase's transacted volume "
           "against this trade AND the adverse stream is still running (5m "
           "sflow opposed at >= 10% of its own volume, or through_book_600s "
           "with the adverse side >= 2x on n >= 10). Measurable and present => "
           "the would-be TAKE is a SKIP."),
}
V3_NOTE = ("ADVISORY V3 (P018 TWO_STREAM_OPPOSITION) fires on this row and is "
           "NOT APPLIED: CC-M2-19.4 put the V2/V3 families under a pooled "
           "re-grade and V3 is net-negative on two consecutive sessions with a "
           "$0.00 replay delta three times running; on the seven-session "
           "pre-registration it costs a further $250. It is computed and "
           "logged on every row so the re-grade gets this session's count.")


# The write loop indexes no per-cell table bare (`SEATS` is read through
# `.get(cell, "-")`, R49's original fix), so only the veto vocabulary is
# checked here.
TABLES = ()


def assert_cell_tables(calls):
    """R49: REFUSE BEFORE THE WRITE, never KeyError mid-write.

    The per-cell tables in this file and in the policy are hand-written.  A
    cell they do not list used to kill the seal with a `KeyError` in the middle
    of the row loop, after every row had been buffered — a half-built seal with
    a traceback instead of a refusal.  Every table the write loop indexes is
    checked here, once, against the cells the day actually produced.
    """
    cells = sorted({(c["asset"], c["phase_dec"]) for c in calls})
    missing = []
    for name, table in TABLES:
        for k in cells:
            if k not in table:
                missing.append("%s missing %s/%s" % (name, k[0], k[1]))
    vets = sorted({v for c in calls for v in c["vetoes"].split("+") if v})
    for v in vets:
        if v not in VETO_SHORT:
            missing.append("VETO_SHORT missing %s" % v)
    if missing:
        raise SystemExit("seal REFUSED before writing anything (R49): %s"
                         % "; ".join(missing))
    return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--index", required=True)
    p.add_argument("--ledger", default=LEDGER)
    p.add_argument("--arms", default="")
    p.add_argument("--used-case-ledger", default=UC.LEDGER)
    a = p.parse_args()

    with open(a.index) as fh:
        rows = list(csv.DictReader([ln for ln in fh if not ln.startswith("#")],
                                   delimiter="\t"))
    calls = POLICY.call_day(rows, arm="CORE+SEAT")
    assert_cell_tables(calls)
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
                    % (cell[0], cell[1], SEATS.get(cell, "-")))
        inter = ("cell_side_call=%s (%s conf); would_abstain=%s; "
                 "rolling_seat R1(rv1800>=250)=%s R2b(unspent_bind>=1000)=%s; "
                 "advisory=%s; veto=%s; cell=%s/%s; seat_holder=%s"
                 % (POLICY.READER_CELL.get(cell, "NONE"),
                    POLICY.CELL_CONF.get(cell, "?"),
                    "YES" if cell in POLICY.WOULD_ABSTAIN else "no",
                    "OPEN" if (POLICY.F(by_cid[cid], "rv1800") or 0) >= 250
                    else "CLOSED",
                    "OPEN" if c["seat_gate"] else "CLOSED",
                    c["advisory"] or "none", c["vetoes"] or "none",
                    cell[0], cell[1], seat_taken.get(cell, "-")))
        if c["advisory"] and c["call"] == "TAKE":
            prem = prem + " " + V3_NOTE
        out.append({
            "cid": cid, "call": c["call"], "conf": c["conf"],
            "primary": c["primary"], "against": c["against"],
            "interaction": inter, "novel": NOVEL.get(cid, ""),
            "premortem": prem,
            "minimal_pair": MINIMAL_PAIR.get(cid, ""),
            "flip_threshold": FLIP.get(cid, ""),
            "sections_read": DEEP.get(cid, "TRIAGE-INDEX-ONLY"),
            "depth": "DEEP" if cid in DEEP else "TRIAGE",
            "taint": TAINT,
            "n_terms": c["n_terms"],
            "terms": "%s|seat%d|side%d|veto:%s|adv:%s" % (
                "".join(str(c[k]) for k in POLICY.TERMS), c["seat_gate"],
                c["side_gate"], c["vetoes"] or "-", c["advisory"] or "-"),
            "asset": c["asset"], "phase_dec": c["phase_dec"],
            "clock": c["clock"], "candidate_class": c["cls"]})

    cols = ("cid call conf primary against interaction novel premortem "
            "minimal_pair flip_threshold sections_read depth taint n_terms "
            "terms asset phase_dec clock candidate_class").split()
    # ---- R34: THE CC-M2-8.1 WARM-UP EXCLUSION, ON THE DRAW SIDE ----------
    # Guards run BEFORE any write.  The law ("warm-ups excluded from every
    # future draw") was stated in this file's own docstring and enforced
    # nowhere on the draw side — the only enforcement was `used_cases.
    # check_blind`, which is a ledger-side rule that happens to hold because
    # all six warm-up sessions are on the ledger as STUDY.
    WD.assert_draw_lawful([r["cid"] for r in out], mode=WD.MODE_STUDY,
                          declared=False, who="E1D8")

    with open(a.ledger, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter="\t",
                           extrasaction="ignore", lineterminator="\n")
        for o in out:
            w.writerow(o)

    _new, _dup = UC.record_seal([r["cid"] for r in out], era="E1",
                                block="STUDY", mode=UC.MODE_STUDY,
                                rnd="E1D8", reader=READER,
                                path=a.used_case_ledger)
    sys.stderr.write("used-case ledger: +%d new, %d already recorded -> %s\n"
                     % (len(_new), _dup, a.used_case_ledger))

    n_take = sum(1 for o in out if o["call"] == "TAKE")
    n_v2 = sum(1 for o in calls if o["vetoes"])
    n_v3 = sum(1 for o in calls if o["advisory"])
    print("E1D8 sealed: %d rows appended (%d TAKE, %d SKIP), %d V2 vetoes, "
          "%d advisory V3 fires, %d deep reads"
          % (len(out), n_take, len(out) - n_take, n_v2, n_v3, len(DEEP)))
    for cell, cid in sorted(seat_taken.items()):
        print("   SEAT %-12s %s" % ("/".join(cell), cid))

    if a.arms:
        import e1d8_stage12 as S
        names = ["CORE", "CORE+SEAT", "CORE+SIDE", "CORE+SEAT+SIDE", "MIRROR"]
        arms = {n: {x["cid"]: x["call"] for x in POLICY.call_day(rows, arm=n)}
                for n in names}
        arms["READER_NOVETO"] = {
            x["cid"]: x["call"]
            for x in POLICY.call_day(rows, arm="CORE+SEAT", vetoes_on=False)}
        arms["CORE+R1"] = {
            r["cid"]: ("TAKE" if (all(POLICY.terms(r)[k] for k in POLICY.TERMS)
                                  and S.r_state(r, rv_t=250.0, cap_t=None))
                       else "SKIP") for r in rows}
        arms["ABSTAIN"] = {
            x["cid"]: ("SKIP" if (x["asset"], x["phase_dec"])
                       in POLICY.WOULD_ABSTAIN else x["call"])
            for x in POLICY.call_day(rows, arm="CORE+SEAT")}
        allnames = names + ["READER_NOVETO", "CORE+R1", "ABSTAIN"]
        with open(a.arms, "w", newline="") as fh:
            w = csv.writer(fh, delimiter="\t")
            w.writerow(["cid", "asset", "phase_dec", "clock", "side"]
                       + allnames + ["veto", "advisory", "final"])
            for c in calls:
                cid = c["cid"]
                w.writerow([cid, c["asset"], c["phase_dec"], c["clock"],
                            c["side"]] + [arms[n][cid] for n in allnames]
                           + [c["vetoes"] or "-", c["advisory"] or "-",
                              c["call"]])
        print("wrote %s" % a.arms)


if __name__ == "__main__":
    sys.exit(main())
