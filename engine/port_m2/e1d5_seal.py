#!/usr/bin/python3
"""E1 STUDY DAY 5 — seal the day ledger (CC-M2-3/4/5 annotations).

Takes the reader's executable policy output (`e1d5_policy.py`, arm CORE+SIDE)
and the executable pre-mortem vetoes (`e1d5_veto.py`) and emits the committed
ledger with every CC-M2-4/5 annotation: taint, pre-mortem per TAKE and per
VETO, minimal pair + flip threshold per deep-read TAKE, per-call deep-read
section log.

DRAW.  The next chronological STUDY session per asset strictly after
2021-07-06, warm-up sessions excluded (CC-M2-8.1): SI/HG/NKD 2021-07-07 —
1,185 candidates (SI 391, HG 413, NKD 381).  No warm-up, day-1, day-2, day-3 or
day-4 round has touched 2021-07-07 (USED_CASE_LEDGER: 0 hits).

THE DAY IS THE DECLARED EXPERIMENT OF CC-M2-13.4, in all three of its arms:
 (a) the inherited 5-term refusal core + P025, no new direction terms;
 (b) pre-mortems as VETOES, with both the would-be take and the veto logged;
 (c) side from the declared first-confirmed-outcome-sign estimator, abstaining
     until the session's first confirmed $1,000 excursion exists.
`e1d5_policy.py`'s docstring declares all three BEFORE the session was scanned,
including the estimator's pre-registered 5-right/2-wrong record on the four
unblinded sessions and its FAILURE of the mirror law (it beats its mirror on
three of four, not four of four).

WHAT THE DAY DID.  The side estimator confirmed LONG on HG at 09:01:35 and on
SI at 08:50:56, and SHORT on NKD at 02:01:14.  The refusal core passes 157 rows;
the side gate cuts them to 112 TAKEs (67 HG NY longs, 45 SI NY longs, 0 NKD —
the fifth consecutive NKD abstention, this one on the MAGNITUDE floor rather
than the live-book floor).  The pre-mortem vetoes then refuse 97 of the 112 and
move BOTH seats: HG/NY from 13:34:42 to 16:19:25, SI/NY from 14:05:20 to
16:38:54.

TAINT.  CLEAN, with two honest qualifications recorded at row level:
 * `AS-OF-PREFIX` on every TAKE — the discretionary half of the day was walked
   through `e1d5_asof.py --next/--at`, which prints only rows whose decision
   second is <= the candidate being called and exactly ONE candidate per call.
   `triage_index.py --as-of` (D14) exists in the tooling lane's working tree but
   has NOT landed at HEAD, so the reader again used its own lane's mechanic.
 * `VETO-TABLE-SCANNED` on the two standing seat TAKEs — NEW DEFECT D18,
   named here rather than discovered later.  The veto-inheritance mechanic
   (CC-M2-13.4(b) applied to 112 takes rather than to 2) required grading the
   whole day's take list against the three triggers, and that table was read as
   a table.  Every trigger is a PURE FUNCTION OF ONE ROW (`e1d5_veto.py`), so a
   prefix-driven walk returns the identical seat chain — the calls are
   mechanically unexposed — but what the reader SAW while choosing which rows
   to deep-read was day-complete, and rows' own `mid`-derived fields (`bar_px`)
   were in it.  The fix belongs upstream with D14: the veto walk must be driven
   by the same as-of stepper as the index.
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import used_cases as UC                                        # noqa: E402

READER = "opus-discretionary"   # the E1 study reader (ledger header)
import e1d5_policy as POLICY                                   # noqa: E402

LEDGER = "/workspace/provenance/port_m2/E1_STUDY_LEDGER.tsv"
TAINT_SKIP = "CLEAN"
TAINT_TAKE = "CLEAN;AS-OF-PREFIX"
TAINT_SEAT = "CLEAN;AS-OF-PREFIX;VETO-TABLE-SCANNED"

# --------------------------------------------------------------- deep reads --
# cid -> sections actually opened (CC-M2-4.5 cost-of-information ledger).
DEEP = {
    "HG-20210707-048882-L": "S1,S2,S3,S4,S5,S6,S7,S8,S9,S10,S11,S12,S13",
    "SI-20210707-050720-L": "S1,S2,S3,S4,S5,S7,S8,S9,S10,S11,S12,S13",
    "HG-20210707-058061-L": "S2,S3,S4,S5,S7,S8,S9,S10,S11",
    "SI-20210707-058372-L": "S2,S3,S4,S5,S7,S8,S9,S10",
    "SI-20210707-059369-L": "S3,S4,S5,S7,S8,S9,S10",
    "HG-20210707-058765-L": "S3,S4,S5,S7,S8,S9,S10",
    "SI-20210707-059934-L": "S3,S4,S5,S7,S8,S10",
    "NKD-20210707-060823-L": "S3,S4,S5,S7",
    "HG-20210707-058836-S": "S3,S8",
    "SI-20210707-059930-L": "S3,S8",
}
THINKALOUD = "HG-20210707-058765-L"

# ------------------------------------------------------------- pre-mortems ---
PM = {}
PM["HG-20210707-048882-L"] = (
    "PRE-MORTEM (written before the call, CC-M2-13.4(b)): this loses because "
    "the target is not where this market is trading. Entry 4.3385; a $1,000 "
    "certificate on one contract needs 4.3785. S10's developing profile at "
    "13:30 is POC 4.3370, VAH 4.3475, VAL 4.2820 — the bar sits $762.50 "
    "ABOVE the top of the developing value area, and S10 has priced the "
    "magnitude correctly on 2 of the 2 days it has been read (E1D3 §11, E1D4 "
    "§6) after being written into the against-field and ignored both times. "
    "S3 says it twice more: COVERAGE SESSION 110.5% with unspent -$235.0 (the "
    "session has already spent its whole forecast move and the exit is the "
    "session close, so P003's session row binds) and ext_needed $962.50 "
    "against $37.50 of room inside the phase range. MEASURABLE AND PRESENT at "
    "the decision second => VETO (trigger V1). Would-be call: TAKE grade C, "
    "5 of 5 terms, side gate LONG.")
PM["SI-20210707-050720-L"] = (
    "PRE-MORTEM (written before the call): the same mechanism one asset over. "
    "Entry 26.5350; the $1,000 bar needs 26.7350. S10's developing profile at "
    "14:05 is POC 26.4600, VAH 26.5500, VAL 26.2650 — the bar is $950 above "
    "the developing VAH, i.e. outside the value area entirely, and the nearest "
    "objects above the entry are the NY OR30 k0.5 extension at 26.5488 (+$68.8, "
    "PENDING, tc=1) and the k1.0 at 26.5700 (+$175). The profile prices this "
    "long at $75 and the level ledger at $175; the bar needs $1,000. S3's "
    "COVERAGE row is REFUSED for the whole SI session (fvol_source="
    "ATR14_RAW_FILL, the day-1 SI defect ERA_NOTES §16 again), so the "
    "extension arithmetic is the only A1 form available and it says $937.50 of "
    "brand-new range. MEASURABLE AND PRESENT => VETO (trigger V1). Would-be "
    "call: TAKE grade B, 5 of 5 terms, side gate LONG.")
PM["HG-20210707-058061-L"] = (
    "PRE-MORTEM (written before the call): this loses because I would be "
    "buying the first tick of a phase whose entire inventory is above me and "
    "still being sold. S8's FUEL MAP reads trapped above_mid=20,626, "
    "below_mid=13, phase_total=20,639 — 99.94% of everything transacted in "
    "this NY phase sits ABOVE the mid, so every buyer of the phase is "
    "underwater and each of them is supply into any bounce. That is the day-4 "
    "SI pre-mortem verbatim, and it fired. The second stream agrees: "
    "through_book_600s n=69 with 62 prints through the BID against 7 through "
    "the ask (8.9:1), and 30m sflow -355 on 4,546. The NY low 4.3060 printed "
    "25 seconds ago and the phase has fallen $1,387.50. MEASURABLE AND PRESENT "
    "=> VETO (trigger V2). Would-be call: TAKE grade B, 5 of 5 terms, side "
    "gate LONG. ON RECORD AGAINST THIS VETO: P009 FUEL_POLARITY is DEAD as a "
    "direction source; V2 is a SUPPLY claim conditioned on the adverse stream "
    "still transacting, and the census must separate the two.")
PM["SI-20210707-058372-L"] = (
    "PRE-MORTEM (written before the call): same object, same minute band, "
    "other asset. S8 FUEL MAP trapped above_mid=10,723 of phase_total=11,399 "
    "(94.1%); 5m sflow -177 on 871 = 20.3% of its own volume, selling; "
    "through_book 14 bid vs 6 ask. S4 says the shelf under me has already "
    "broken: SESSION|VAL 26.3450 carries outcome=BREAK and or_ext_flags reads "
    "OREXT_BEYOND,OREXT_BEYOND_ANY — price is below every opening-range "
    "extension it has made today. The NY low 26.2600 is 140 seconds old and "
    "the phase has fallen $1,437.50. MEASURABLE AND PRESENT => VETO (trigger "
    "V2). Would-be call: TAKE grade A, 5 of 5 terms, side gate LONG.")
PM["SI-20210707-059369-L"] = (
    "PRE-MORTEM (written before the call): this is a catch of a falling knife "
    "29 seconds after a new phase low, and BOTH streams say the impulse is "
    "still running. S8 60s sflow -290 on 2,230 contracts = 13.0% opposed with "
    "volume far over the 20-contract floor, and S5 mid_slope_$/min(T-1m) = "
    "-$400.00 opposed: that is P018 TWO_STREAM_OPPOSITION, ACTIVE and 5-0 in "
    "the ledger and validated on day-1 history before it was ever used. The "
    "tape confirms the regime it was written for: trades/min 938 (z=+25.75), "
    "rv300 $521.70, event-intensity ratio 2.76, through_book 72 bid vs 21 ask "
    "in 600 seconds. S10's developing POC is $1,412.50 above the mid — the "
    "profile has not moved, the price has. MEASURABLE AND PRESENT => VETO "
    "(trigger V3). Would-be call: TAKE grade A, 5 of 5 terms, side gate LONG.")
PM["HG-20210707-058765-L"] = (
    "PRE-MORTEM (written before the call; the mechanism is measurable but NOT "
    "yet present, so the protocol's conditional branch applies and this is "
    "logged as a flip threshold, not a veto): this loses if the 91.9% of NY "
    "phase volume trapped above the mid (20,677 of 22,498) is real supply that "
    "simply paused. What has changed since the 16:07:41 row I vetoed is the "
    "side of two streams, not the overhang: S8 5m sflow is +63 on 601 (10.5%, "
    "BUYING) where it was -92 on 1,749, and through_book_600s is 8 bid vs 15 "
    "ask where it was 62 vs 7. S10's in_VA has flipped 0 -> 1: price left the "
    "developing value area under VAL 4.3090 and has come back inside it. THE "
    "TRIGGER I AM WATCHING: if S8's 5-minute sflow turns SELL at >= 10% of its "
    "own volume while price is back below 4.3090, the bounce has failed, the "
    "overhang is real and the 4.3033 low is re-made. THE SECOND RESERVATION, "
    "on the record because it is the round's unexplained loss channel: the "
    "$1,000 bar is 4.3533 and S10's developing VAH is 4.3535 — the profile "
    "prices this move at exactly the bar and not a dollar beyond, so there is "
    "no room in the target for a give-back (ERA_NOTES §35/§39.5, and P026 died "
    "trying to predict it).")
PM["SI-20210707-059934-L"] = (
    "PRE-MORTEM (written before the call; measurable but not present => flip "
    "threshold, not a veto): this loses if the 16:37:17 high at 26.1975 was "
    "the whole bounce. S3's ZigZag chain since 16:30 is six pivots in eight "
    "minutes (26.0975, 26.1225, 26.0825, 26.1125, 26.0825, 26.1325, 26.1975) — "
    "a $525 pop in 125 seconds and a $212.50 give-back into this decision "
    "second, which is exactly the shape of a short-covering spike inside a "
    "downtrend. The longer horizons have not turned: S8 30m sflow -438 on "
    "7,209 and phase sflow -439 on 17,773. What lets it stand is that the "
    "PRESENT-tense streams do not oppose at magnitude — 60s sflow -7 on 165 "
    "(4.2%, under P018's floor) and 5m sflow +63 on 1,052 (6.1%, buying) — and "
    "that S4 puts the entry exactly on a VIRGIN OR_EXT level (LONDON|OR60|"
    "k0.5|-1 at 26.1550, d$=0.0, V=1, tc=0) with the NY|VAL 26.1100 already "
    "REJECTed below. THE TRIGGER I AM WATCHING: if 60s sflow goes below -10% "
    "of its own volume while price is under 26.1275 (the 16:29 low), the "
    "bounce is a lower high and the $900 wall at 25.9750 is one leg away.")

# how a veto propagates: the trigger's founding sentence, in one clause
VETO_SHORT = {
    "V1": ("INHERITED VETO V1 (minted on HG-20210707-048882-L / "
           "SI-20210707-050720-L): S10's developing value area prices this "
           "move short of the bar — the price a $1,000 certificate requires "
           "lies OUTSIDE the developing VAH (long) / VAL (short) at this "
           "decision second. Measurable and present => the would-be TAKE is a "
           "SKIP."),
    "V2": ("INHERITED VETO V2 (minted on HG-20210707-058061-L, confirmed on "
           "SI-20210707-058372-L): S8's FUEL MAP puts >= 90% of the phase's "
           "transacted volume against this trade AND the adverse stream is "
           "still running (5m sflow opposed at >= 10% of its own volume, or "
           "through_book_600s with the adverse side >= 2x and n >= 10). "
           "Measurable and present => the would-be TAKE is a SKIP."),
    "V3": ("INHERITED VETO V3 (minted on SI-20210707-059369-L): P018 "
           "TWO_STREAM_OPPOSITION fires — S8 60s |sflow| >= 10% of a >= 20 "
           "contract 60s volume opposed to the trade AND S5 mid_slope_$/min"
           "(T-1m) opposed. ACTIVE and 5-0 in the ledger. Measurable and "
           "present => the would-be TAKE is a SKIP."),
}
PM_INHERIT_TAKE = {
    ("HG", "NY"): ("PRE-MORTEM INHERITED from the HG/NY seat "
                   "HG-20210707-058765-L (16:19:25): the overhang is the "
                   "mechanism and it is conditional, not present — the trigger "
                   "is 5m sflow turning SELL at >= 10% below the developing "
                   "VAL 4.3090. This row is a TAKE that the CC-M2-10.3 seat "
                   "rule forfeits: the HG/NY seat was spent at 16:19:25 and "
                   "does not free again before the phase close."),
    ("SI", "NY"): ("PRE-MORTEM INHERITED from the SI/NY seat "
                   "SI-20210707-059934-L (16:38:54): the bounce-is-a-lower-"
                   "high mechanism, conditional on 60s sflow going below -10% "
                   "under 26.1275. This row is a TAKE that the CC-M2-10.3 seat "
                   "rule forfeits: the SI/NY seat was spent at 16:38:54."),
}

# ------------------------------------- minimal pairs + flip thresholds -------
MINIMAL_PAIR = {
    "HG-20210707-058765-L": (
        "MINIMAL PAIR: HG-20210707-058836-S (16:20:36, same asset, same phase, "
        "71 seconds later, SHORT) — SKIP. THE EXACT DIFFERENCE is the SIDE, "
        "and everything the side drags with it: the trade-side phase extreme "
        "is the 16:09:14 LOW at 611s for my long and the 14:11:51 HIGH at "
        "7,725s for the short (T3 fails on the short), and the bar needs $0 of "
        "new range for the long against $845 for the short. The side gate is "
        "the term that refuses it — the session state is LONG — but note that "
        "the freshness and capacity terms refuse it too, on the same tape, in "
        "the same minute. If the day's winners are NY SHORTS, this pair is the "
        "cheapest possible statement of what the side experiment cost: one "
        "row, 71 seconds, three terms."),
    "SI-20210707-059934-L": (
        "MINIMAL PAIR: SI-20210707-059930-L (16:38:50, same asset, same phase, "
        "same side, FOUR SECONDS earlier) — SKIP, blocked by T4 alone. THE "
        "EXACT DIFFERENCE is one field and one tenth of one percent: 5m sflow "
        "+55 on 1,119 contracts = 4.9%, under the 5.0% magnitude floor, "
        "against +64 on 1,052 = 6.1% here. Identical book, identical level, "
        "identical runway, identical grade. If the pair pays and this does "
        "not, or vice versa, the 5% floor is a fitted number and not a "
        "mechanism — which is the same question day 4 asked of it and could "
        "not answer."),
}
FLIP = {
    "HG-20210707-058765-L": (
        "FLIP THRESHOLD: the binding field is S10's developing VAH at 4.3535 "
        "against the $1,000 bar price 4.3533 — the take clears veto trigger V1 "
        "by $2.50 of a $1,000 target, the narrowest margin the day produced. "
        "A VAH $12.50 lower (4.3510, one tick) and this seat is vetoed and the "
        "HG/NY seat moves again. Second binding field: S8 5m sflow +63 on 601 "
        "= 10.5%; below 5.0% (sflow < +30) T4 stops firing and the row is a "
        "SKIP on the core."),
    "SI-20210707-059934-L": (
        "FLIP THRESHOLD: S8 5m sflow/vol = 6.1% (+64 on 1,052) against the T4 "
        "floor at 5.0% — sflow below +53 and this is a SKIP, which is exactly "
        "what happened to the row four seconds earlier. Veto side: V2 needs "
        "the trapped-against share at 90% and it stands at 76.5% (13,592 of "
        "17,773); V3 needs 60s |sflow|/vol at 10% and it stands at 4.2% "
        "(-7 on 165). Both vetoes are within one minute's flow of firing."),
    "SI-20210707-050720-L": (
        "FLIP THRESHOLD (recorded on a VETOED row because it is the day's "
        "registered test of the pre-mortem-as-veto experiment): the veto turns "
        "on S10's developing VAH 26.5500 against a bar price of 26.7350, a gap "
        "of $950. For this take to stand, the developing value area would have "
        "to reach 26.7350 — i.e. the profile would have to price the move the "
        "trade needs. If the rows V1 refuses on this session turn out to be "
        "the day's winners, then S10's developing value area is a "
        "value-destroying veto on its first outing as one, and the ledger says "
        "so — the same pre-registration that killed P026 in one day."),
    "SI-20210707-059369-L": (
        "FLIP THRESHOLD: V3/P018 turns on S8 60s sflow -290 on 2,230 = 13.0% "
        "against the 10% floor, with S5 slope1m -$400/min. A 60s sflow above "
        "-223 (i.e. under 10%) and this row stands as the SI seat at 16:29:29 "
        "instead of 16:38:54 — nine minutes and $170 of SI price earlier. That "
        "is the whole measurable content of trigger V3 on this day."),
}

# --------------------------------------------------------- novel/hypotheses --
NOVEL = {
    "HG-20210707-058765-L": (
        "novel: P027 SESSION_SIDE_FIRST_CONFIRMATION (registered prospectively, "
        "CC-M2-4.3, and declared in full in e1d5_policy.py before the session "
        "was scanned). The day-side is estimated by the FIRST candidate of the "
        "asset-session whose favourable excursion completes $1,000 inside its "
        "own phase, read from later rows' mid path; the side it implies is "
        "then fixed for the rest of the session. On HG it fired at 09:01:35 "
        "off HG-20210707-025356-L. Pre-registered record: 5 right / 2 wrong on "
        "the seven asset-sessions of days 1-4 that produced winners, 2 of the "
        "5 arriving after their winner window closed, and it FAILS the "
        "CC-M2-13.1 mirror law (it beats its mirror on 3 of 4 sessions, not "
        "4 of 4). It is traded today because CC-M2-13.4(c) declares it."),
    "SI-20210707-059934-L": (
        "novel: P028 BAR_OUTSIDE_DEVELOPING_VALUE (registered prospectively). "
        "The reader's first ex-ante MAGNITUDE object since P026 died: compare "
        "the price a $1,000 certificate requires (entry +/- 1000/mult) with "
        "S10's developing VAH/VAL at the decision second; when the bar lies "
        "outside the developing value area on the trade's side, the profile "
        "has priced the move short of the bar before the trade is taken. S10 "
        "is 2-for-2 on the two days it has been read and it is still not in "
        "the triage index (defect D17), so day 5 extracted it in-lane "
        "(e1d5_s10.py). It is trigger V1 of the veto experiment and it refuses "
        "76 of this day's 112 policy TAKEs — its cost or its saving is "
        "measured today either way."),
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--index", required=True)
    p.add_argument("--veto", required=True)
    p.add_argument("--ledger", default=LEDGER)
    p.add_argument("--arms", default="")
    p.add_argument("--used-case-ledger", default=UC.LEDGER,
                   help="D-035.2 used-case ledger the seal records into "
                        "(CC-M2-17.4); tests point it elsewhere")
    a = p.parse_args()

    with open(a.index) as fh:
        rows = list(csv.DictReader([ln for ln in fh if not ln.startswith("#")],
                                   delimiter="\t"))
    veto = {r["cid"]: r for r in csv.DictReader(open(a.veto), delimiter="\t")}
    calls, state = POLICY.call_day(rows, arm="CORE+SIDE")
    by_cid = {r["cid"]: r for r in rows}
    for cid in list(DEEP) + list(MINIMAL_PAIR) + list(FLIP) + list(PM):
        if cid not in by_cid:
            raise SystemExit("seal: unknown cid %s" % cid)

    # the seat chain, chronological, per (asset, phase) cell
    seat_taken = {}
    out = []
    for c in calls:
        cid = c["cid"]
        cell = (c["asset"], c["phase_dec"])
        v = veto.get(cid, {}).get("veto", "")
        final = "SKIP" if (c["call"] == "TAKE" and v) else c["call"]
        prem = ""
        if c["call"] == "TAKE":
            if cid in PM:
                prem = PM[cid]
            elif v:
                prem = " ".join(VETO_SHORT[t] for t in v.split(";"))
            else:
                prem = PM_INHERIT_TAKE[cell]
        if final == "TAKE" and cell not in seat_taken:
            seat_taken[cell] = cid
        inter = ("side_state=%s; policy_call=%s; premortem_veto=%s; "
                 "seat_cell=%s/%s; seat_holder=%s"
                 % ("LONG" if (state.get(c["asset"]) or (0, 0))[1] > 0
                    else ("SHORT" if state.get(c["asset"]) else "UNSET"),
                    c["call"], v or "none", cell[0], cell[1],
                    seat_taken.get(cell, "-")))
        taint = TAINT_SKIP
        if final == "TAKE":
            taint = TAINT_SEAT if cid in PM else TAINT_TAKE
        out.append({
            "cid": cid, "call": final, "conf": c["conf"],
            "primary": c["primary"], "against": c["against"],
            "interaction": inter, "novel": NOVEL.get(cid, ""),
            "premortem": prem,
            "minimal_pair": MINIMAL_PAIR.get(cid, ""),
            "flip_threshold": FLIP.get(cid, ""),
            "sections_read": DEEP.get(cid, "TRIAGE-INDEX-ONLY"),
            "depth": "DEEP" if cid in DEEP else "TRIAGE",
            "taint": taint,
            "n_terms": c["n_terms"],
            "terms": "%s|gate%d|veto:%s" % (
                "".join(str(c[k]) for k in POLICY.TERMS), c["side_gate"],
                v or "-"),
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
                                rnd="E1D5", reader=READER,
                                path=a.used_case_ledger)
    sys.stderr.write("used-case ledger: +%d new, %d already recorded -> %s\n"
                     % (len(_new), _dup, a.used_case_ledger))

    n_take = sum(1 for o in out if o["call"] == "TAKE")
    n_veto = sum(1 for o in out if veto.get(o["cid"], {}).get("veto"))
    print("E1D5 sealed: %d rows appended (%d TAKE, %d SKIP), %d pre-mortem "
          "vetoes, %d deep reads" % (len(out), n_take, len(out) - n_take,
                                     n_veto, len(DEEP)))
    for cell, cid in sorted(seat_taken.items()):
        print("   SEAT %-10s %s" % ("/".join(cell), cid))
    for ln in POLICY.side_state_log(state):
        print("   SIDE-STATE %s" % ln)

    if a.arms:
        with open(a.arms, "w", newline="") as fh:
            w = csv.writer(fh, delimiter="\t")
            w.writerow(["cid", "asset", "phase_dec", "clock", "side",
                        "core", "core_side", "mirror", "core_signed",
                        "veto", "final"])
            arms = {}
            for nm in ("CORE", "CORE+SIDE", "MIRROR", "CORE+SIGNED"):
                arms[nm] = {x["cid"]: x["call"]
                            for x in POLICY.call_day(rows, arm=nm)[0]}
            for c in calls:
                cid = c["cid"]
                v = veto.get(cid, {}).get("veto", "")
                w.writerow([cid, c["asset"], c["phase_dec"], c["clock"],
                            c["side"], arms["CORE"][cid], arms["CORE+SIDE"][cid],
                            arms["MIRROR"][cid], arms["CORE+SIGNED"][cid],
                            v or "-",
                            "SKIP" if (c["call"] == "TAKE" and v) else c["call"]])
        print("   arms -> %s" % a.arms)


if __name__ == "__main__":
    sys.exit(main())
