#!/usr/bin/python3
"""E1 STUDY DAY 3 — seal the day ledger (CC-M2-3/4/5 annotations).

Takes the reader's executable policy output (e1d3_policy.py), applies the
reader's DEEP-READ OVERRIDES — the discretionary part, because a mechanical
rule is not a reader — and emits the committed ledger with every CC-M2-4/5
annotation: taint, pre-mortem per TAKE, minimal pair + flip threshold per
deep-read TAKE, per-call deep-read section log.

DRAW.  The next chronological STUDY session per asset strictly after
2021-07-02, warm-up sessions excluded (CC-M2-8.1): SI/HG/NKD 2021-07-05, 644
candidates.  No warm-up, day-1 or day-2 round has ever touched 2021-07-05, so
no row carries prior-round outcome knowledge.

TAINT, HONESTLY (and this day names a hazard the two prior days shared but did
not record at row level).  Two columns' worth of exposure exist:
  * CLEAN — no outcome of this session, or of any adjacent session, is known.
    True of all 644 rows in the CC-M2-8.1 sense.
  * SCAN-EXPOSED (this day's addition, applied to the 5 TAKE rows) — the
    triage index is DAY-COMPLETE by construction, so scanning it to find
    candidates necessarily shows rows from LATER decision seconds, and the
    `mid` column of those rows is the price path after the decision second I am
    calling.  On this session the exposure is unusually sharp: the tape ends
    early (last candidate 18:59 clock against a nominal 22:59:59 session
    close), so the LAST row's mid is effectively the session close that the
    exit rule will use.  The policy itself is a pure function of one row and is
    mechanically unexposed; the five discretionary TAKEs are not, and they are
    marked so the orchestrator can discount them.  Build item D14: a
    `--as-of SEC` prefix view for triage_index.py would remove the hazard from
    the reader's discipline and put it in the tool, exactly as D11 did for
    retrieval.

THE POLICY SAID SKIP 644 TIMES.  e1d3_policy.py fires on nothing: its binding
term is T4 ABSORPTION FUEL (opposed 5-minute aggression on >= 500 contracts),
and this is a US-holiday session whose 5-minute volumes are a fifth of the two
prior days' outside HG's NY phase.  The floor was tested against a scale-free
alternative before the day was called: replacing `5m vol >= 500` with
`5m vol / phase volume >= k` reproduces day 1 but destroys day 2 (replay
+$1,477 -> -$28), so the absolute floor is doing economic work — the $1,000 bar
is absolute too — and it stays.  Abstention is a result (day 1 proved it on
NKD, 0 winners in 310 candidates).

THE FIVE TAKES ARE A DISCRETIONARY OVERRIDE, NOT THE RULE.  They are one seat:
HG's NY phase, one thesis, five decision seconds.  The thesis is stated in full
in the primary evidence of HG-20210705-055113-S below.  What makes it an
override rather than a rule violation: T4 was derived from the ABSORPTION
family (aggression opposed at magnitude and being absorbed), and it is a
CONTINUATION-entry requirement.  The object here is not a continuation — it is
an A2 REFAIL at a multi-family fvol confluence, the family for which day 1
already recorded a scope exception (P006 waived P015's flow term for a
first-test rejection; this is the same move in the opposite direction — the
flow term is satisfied and the absorption term is waived).

WHAT ARGUES AGAINST THE OVERRIDE, ON RECORD BEFORE THE UNBLINDING.  The
override written as an executable rule (P024, in the ledger's novel field)
fires SIX times on 2021-07-02 and FIVE of those are -$930 wall-outs, and it
fires ZERO times on 2021-07-01.  That is a bad backtest and it is why only one
seat is spent and why every take carries the pre-mortem it does.  The
countervailing evidence, also on record: the lawful reference-class retrieval
(warm-up + day 1 + day 2, `--exclude-date8 20210705`) returns ten HG/NY/RECLAIM
analogs for HG-20210705-055113-S at distances 0.162-0.247, of which the seven
SHORTS closed +$1,438.75, -$136.25, -$148.75, +$1,338.75, +$1,388.75, +$57.50
and +$1,445.00 — mean +$769, no wall among them.

GRADES are the CC-M2-10.5 rebuild: sigma_to_exit = S9 rv1800 * sqrt(runway/1800),
two fields the decision rule never reads.  A >= $2,500 / B $1,200-2,500 / C
below.  On the 1,111 session-close rows of the two prior days it is monotone in
winner rate (A 19.7% / B 8.4% / C 0.9%) and in mean |certificate|.
"""
import argparse
import csv
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import e1d3_policy as POLICY                       # noqa: E402

LEDGER = "/workspace/provenance/port_m2/E1_STUDY_LEDGER.tsv"

# ---- the reader's deep reads: cid -> sections actually opened on the sheet --
DEEP = {
    "HG-20210705-055113-S":  "S2,S3,S4,S5,S7,S8,S9,S10,S11,S12",
    "HG-20210705-055482-S":  "S3,S4,S7,S8",
    "HG-20210705-056096-S":  "S3,S4,S7,S8",
    "HG-20210705-055036-S":  "S3,S8",
    "HG-20210705-058531-L":  "S3,S8",
    "HG-20210705-050248-S":  "S3,S8",
    "HG-20210705-054360-L":  "S3,S8",
    "SI-20210705-054737-L":  "S8",
    "SI-20210705-000045-S":  "S1,S2,S3,S4,S5,S6,S7,S8,S9,S10,S11,S12,S13",
    "NKD-20210705-000090-S": "S1,S8",
}

TAKES = ("HG-20210705-055113-S", "HG-20210705-055482-S",
         "HG-20210705-055488-S", "HG-20210705-056096-S",
         "HG-20210705-056106-S")

_THESIS = (
    "primary: S3 NY phase H=4.3578@15:16:21 is the SECOND failed push at one "
    "price — the ZigZag chain prints HIGH 4.3575@15:14:01, LOW 4.3520@15:15:21, "
    "HIGH 4.3578@15:16:21, i.e. two pushes $3 apart with a $137.5 dip between "
    "them (A2 REFAIL CLUSTERING), and the pair was made INTO a multi-family "
    "fvol confluence: S4 carries FVOL_BAND OPEN_TOKYO|k1.0|+1=4.3569, "
    "FVOL_LADDER_RS OPEN_LONDON|q50|+1=4.3569 and FVOL_LADDER SETTLE|q50|+1="
    "4.3584 straddling the high (B2: extremes form at fvol ladder levels at "
    "2.1-2.5x chance). The $1,000 bar needs NO new range: S3 phase L=4.3115 is "
    "$1,082.5 below the S13 entry mid=4.3548 at mult=25000, so ext_needed=$0 "
    "[P017 in the scope where it is a capacity fact rather than a "
    "mean-reversion prior — the session is at S2 day_type_so_far=EXPANDED, "
    "133.6%% of range_hat, so the next $1,000 is a give-back of today's own "
    "move, not a new expansion]. Every flow horizon is on the trade's side at "
    "magnitude: S8 60s sflow=-46 on 150 (30.7%%), 5m -77 on 752 (10.2%%), phase "
    "-512 on 8,602 (6.0%%) [P015, and S12 says the session contains NO "
    "scheduled release — next_scheduled CPI is 7d 23h away — so the phase "
    "window is not the fossil it was on 2021-07-02]. The price stream has "
    "turned with participation rising, not falling: S5 trades/min 27 -> 77 -> "
    "79 -> 37 -> 98 with sflow/min -46, mid_slope_$/min(T-1m)=-43.8 and "
    "accel(1m-5m)=-38.8. S7 resolves the book by side: dBsz/min=-4.00 against "
    "dAsz/min=+3.00 — the BID is thinning while the ASK restocks [A4], on a "
    "1-tick spread ($12.50 = 0.5x the HG era median) with refill frac=0.662. "
    "S8 through_book_600s n=15 splits 9 bid / 6 ask [T5]. Risk is asymmetric "
    "by arithmetic: the $900 wall sits at 4.3908, $825 above a session high "
    "that is already 133.6%% of range_hat, while the target sits inside the "
    "range the phase has already traded."
)

_AGAINST = (
    "against: my own T4 ABSORPTION FUEL says the opposite — the 5-minute "
    "aggression is WITH this short, so nobody is absorbing for me and I am the "
    "hitter; pooled over the two prior day-complete sessions, flow signed WITH "
    "the trade wins 1.9%% of the time and flow signed AGAINST it 8.4%%. S3 "
    "COVERAGE SESSION=125.6%% with unspent=-$514.8 — the session has already "
    "delivered more than its whole expected move, which is P002's veto shape "
    "read at the binding (session-close) exit. S10 puts the first magnet only "
    "$318.7 away (developing POC=4.3420) and the $1,000 target at 4.3148 is "
    "BELOW the developing VAL=4.3125's neighbourhood, i.e. the bar needs the "
    "whole value area traversed. And the honest backtest of this override "
    "written as a rule: 0 fires on 2021-07-01, 6 fires on 2021-07-02 of which "
    "5 closed at exactly -$930."
)

_NOVEL = (
    "novel: P024 REFAIL_REVERSION, proposed as a censusable object and used "
    "here as a named probe. A session at S2 day_type_so_far=EXPANDED with "
    "%%range_hat >= 100, a trade-side phase extreme that is the SECOND failed "
    "push at one price inside 5 minutes, the $1,000 bar entirely inside the "
    "phase range (ext_needed <= $450), phase AND 5m flow concordant at >= 5%% "
    "of their own volume, S8 through_book_600s majority on the trade's side "
    "with n >= 5, and S5 mid_slope(T-1m) signed with the trade. The claim it "
    "tests is the one the round most needs settled: on a session with NO "
    "scheduled release (S12 next_scheduled countdown > S3 runway to session "
    "close), is cumulative phase flow a live parent order rather than a "
    "fossil? On 2021-07-01 (no release) flow-concordant NY rows returned "
    "+$744 and 21.6%% winners; on 2021-07-02 (Employment Situation inside the "
    "NY phase) the same rows returned -$552 and 0%%. Today is the third draw "
    "of that coin and it is a no-release day."
)

OVERRIDE = {
    "HG-20210705-055113-S": ("TAKE", "B", _THESIS, _AGAINST, _NOVEL),
    "HG-20210705-055482-S": (
        "TAKE", "B",
        "primary: the same seat as HG-20210705-055113-S, six minutes later and "
        "$162.5 lower, with the evidence STRONGER on the two streams that "
        "matter: S8 60s sflow=-71 on 165 (43.0%% sell, against 30.7%% at "
        "15:18:33) and S5 mid_slope_$/min(T-1m)=-143.7 (against -43.8), while "
        "S8 through_book_600s is now 5 bid / 0 ask. S3's ZigZag has confirmed "
        "the 15:16:21 high at three rung scales (0.05,0.075,0.11) instead of "
        "one. S3 phase L=4.3115 leaves ext_needed=$80 from mid=4.3483. S7 "
        "dBsz/min=-6.00 with dAsz/min=-9.00 — both sides thinning now, which "
        "is the one term that is worse than at 15:18:33.",
        "against: " + _AGAINST[len("against: "):],
        "novel: P024 as above; this row is the magnitude test of the same "
        "thesis — if the refail is real, the entry six minutes into the "
        "rollover with twice the 60-second sell imbalance should not be worse "
        "than the entry at the extreme."),
    "HG-20210705-055488-S": (
        "TAKE", "B",
        "primary: same seat and same second-order evidence as "
        "HG-20210705-055482-S six seconds earlier (S8 60s sflow=-78 on 184 = "
        "42.4%%, 5m -83 on 416, phase -598 on 9,161; S8 through_book_600s 5 "
        "bid / 0 ask; S5 mid_slope(T-1m)=-125.0; S3 ext_needed=$92.5 against "
        "phase L=4.3115).",
        "against: " + _AGAINST[len("against: "):],
        "novel: P024 as above."),
    "HG-20210705-056096-S": (
        "TAKE", "B",
        "primary: the rollover has now printed its own lower high — S3's "
        "ZigZag adds LOW 4.3440@15:29:21 and HIGH 4.3518@15:30:45 beneath the "
        "4.3578 refail, so the structure is a completed lower-high sequence "
        "rather than a single rejection; S5 mid_slope_$/min(T-1m)=-106.2, S8 "
        "60s sflow=-29 on 75 (38.7%%), 5m -26 on 393, phase -662 on 10,126 "
        "(6.5%%), through_book_600s 6 bid / 2 ask; S3 ext_needed=$155 from "
        "mid=4.3453 against phase L=4.3115; S4 shows the entry sitting ON the "
        "FVOL_BAND OPEN_LONDON|k0.5|+1=4.3451 that was RECLAIMED earlier, with "
        "NDAY N10|H=4.3420 REJECTED $81 below — the two objects that frame the "
        "next $1,000.",
        "against: " + _AGAINST[len("against: "):]
        + " Additionally S7 refill frac has fallen to 0.486 and dBsz/min has "
        "turned POSITIVE (+5.00) — the bid is restocking, which is the exact "
        "field that carried the 15:18:33 entry and it has flipped.",
        "novel: P024 as above."),
    "HG-20210705-056106-S": (
        "TAKE", "B",
        "primary: same second as HG-20210705-056096-S plus ten seconds (S8 60s "
        "sflow=-25 on 79, 5m -13 on 365, phase -659 on 10,133; through_book "
        "6 bid / 2 ask; S5 mid_slope(T-1m)=-81.3; S3 ext_needed=$137.5).",
        "against: " + _AGAINST[len("against: "):],
        "novel: P024 as above."),
}

PREMORTEM = {
    "HG-20210705-055113-S":
        "PRE-MORTEM: this loses if the buyer who absorbed 512 contracts of net "
        "selling on the way from 4.3115 to 4.3578 is still working — that is "
        "the mechanism my own T4 term is built to detect and it says SKIP "
        "here, because the aggression is mine, not theirs. The measurable "
        "form: if S8's 30m window (now -60 on 3,696, i.e. FLAT) turns buy at "
        ">= 5%% while price holds above 4.3520, the refail was a pause in an "
        "absorption leg and the $900 wall at 4.3908 is one more 133%%-of-"
        "range_hat expansion away. The identical configuration written as a "
        "rule fired six times on 2021-07-02 and five of them closed at exactly "
        "-$930; the reason I believe today is different is S12 (no scheduled "
        "release in this session) and S3 (a two-push refail at a fvol "
        "confluence), and if the trade dies it will have died proving that "
        "the release flag was never the separator.",
    "HG-20210705-055482-S":
        "PRE-MORTEM: the thin holiday tape is the risk here — S7 shows BOTH "
        "sides of the book thinning (dBsz/min=-6.00, dAsz/min=-9.00) and S8's "
        "5m volume is 393 contracts against 752 six minutes ago. A "
        "session-close hold on 2021-07-05 needs someone to keep selling into a "
        "US holiday afternoon; if participation keeps halving, the certificate "
        "is decided by wherever the last print of a dying book leaves the mid, "
        "not by my thesis.",
    "HG-20210705-055488-S":
        "PRE-MORTEM: same seat as HG-20210705-055482-S, six seconds later — it "
        "fails the same way, through a book that is thinning on both sides "
        "into a holiday close, and under D-046 it cannot even be entered while "
        "that position is held to its session-close exit.",
    "HG-20210705-056096-S":
        "PRE-MORTEM: S7's dBsz/min has turned POSITIVE (+5.00 against -4.00 at "
        "15:18:33) while refill frac fell to 0.486 — the bid is restocking "
        "under a falling price, which is what a passive buyer does when it is "
        "working a size order rather than stepping away. If that bid is real, "
        "4.3420 (S4 NDAY N10|H, already REJECTED once) holds, the lower-high "
        "sequence becomes a range, and a session-close hold on an $81 edge "
        "gives it all back.",
    "HG-20210705-056106-S":
        "PRE-MORTEM: same seat as HG-20210705-056096-S ten seconds later — it "
        "fails the same way (a restocking bid at 4.3420) and under D-046 it "
        "cannot be entered while that position is open.",
}

MINIMAL_PAIR = {
    "HG-20210705-055113-S":
        "MINIMAL PAIR: HG-20210705-055036-S (15:17:16, same asset/side/phase, "
        "77 seconds earlier, 55s after the same 4.3578 high) — SKIP. THE "
        "DIFFERENCE is two fields and they are the two the thesis rests on: "
        "S5 mid_slope_$/min(T-1m)=+6.2 there against -43.8 here (the price "
        "stream had not yet turned), and S8 60s sflow=+10 on 86 (BUYING) "
        "against -46 on 150 (30.7%% selling) here. Everything else is "
        "equivalent or better on the pair: it is 55s fresher off the extreme, "
        "its ext_needed is $0 too, its phase sflow is the same -464/8,440, and "
        "its through_book is 7/7 rather than 9/6. If 055036-S pays as well as "
        "055113-S, the refail alone is the object and the turn of the price "
        "stream adds nothing.",
    "HG-20210705-055482-S":
        "MINIMAL PAIR: HG-20210705-055228-S (15:20:28, same asset/side/phase, "
        "four minutes earlier) — SKIP. THE DIFFERENCE: S5 "
        "mid_slope_$/min(T-1m)=+12.5 there (the rollover paused and ticked "
        "back up) against -143.7 here, and S8 60s sflow=+28 on 116 (buying) "
        "against -71 on 165. The pair is BETTER on capacity (room $1,050 / "
        "ext_needed $0 against $920 / $80 here) and fresher off the extreme "
        "(247s against 501s), so the only fields it loses on are the two the "
        "thesis names. The pair isolates the SAME field as the 055113-S pair, "
        "one rollover later.",
    "HG-20210705-056096-S":
        "MINIMAL PAIR: HG-20210705-056201-S (15:36:41, same asset/side/phase, "
        "105 seconds later) — SKIP. THE DIFFERENCE: S5 "
        "mid_slope_$/min(T-1m)=0.0 there against -106.2 here, with S8 60s "
        "sflow=-10 on 44 against -29 on 75. If 056201-S pays and 056096-S does "
        "not, the one-minute slope is noise at this horizon and the seat "
        "should be spent on the level structure alone.",
}

FLIP = {
    "HG-20210705-055113-S":
        "FLIP THRESHOLD: S8 30m sflow / 30m volume. At -60/3,696 (1.6%%, flat) "
        "the call stands; it flips to SKIP at >= +5%% BUY on the 30-minute "
        "window (i.e. sflow >= +185 here), because that is the absorption leg "
        "restarting and it is the mechanism the pre-mortem names. Second flip: "
        "S3 ext_needed above $450 (mid below 4.3448 against this phase low) — "
        "past that the trade stops being a give-back of today's own range and "
        "becomes a new expansion, which is the P017 configuration that lost on "
        "2021-07-02.",
    "HG-20210705-055482-S":
        "FLIP THRESHOLD: S8 5m volume. At 393 contracts the call stands; below "
        "~200 (with S7 dBsz/min and dAsz/min both negative, as they are) I "
        "would not spend a session-close seat on this tape at all — that is "
        "the holiday-thinness floor the pre-mortem names, and it is the same "
        "quantity as my policy's T4 volume floor, applied to participation "
        "rather than to absorption.",
    "HG-20210705-056096-S":
        "FLIP THRESHOLD: S7 dBsz/min. At +5.00 the call is already marginal "
        "and it is the reason this row is graded no higher than B; at "
        "dBsz/min >= +10 with S7 refill frac >= 0.6 (a bid restocking fast "
        "under a falling price) it flips to SKIP. Second flip: S4 NDAY "
        "N10|H=4.3420 changing from REJECT to RECLAIM on a later test.",
}

TAINT_TAKE = "CLEAN;SCAN-EXPOSED"
TAINT_SKIP = "CLEAN"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--index", required=True)
    p.add_argument("--ledger", default=LEDGER)
    a = p.parse_args()

    with open(a.index) as fh:
        lines = [ln for ln in fh if not ln.startswith("#")]
    rows = list(csv.DictReader(lines, delimiter="\t"))
    by_cid = {r["cid"]: r for r in rows}

    for cid in list(TAKES) + list(DEEP):
        if cid not in by_cid:
            raise SystemExit("seal: unknown cid %s" % cid)

    out = []
    for r in rows:
        c = POLICY.call_row(r)
        cid = c["cid"]
        prem = pair = flip = ""
        if cid in OVERRIDE:
            call, conf, prim, agn, nov = OVERRIDE[cid]
            c["call"], c["conf"] = call, conf
            c["primary"], c["against"] = prim, agn
            c["novel"] = nov
        else:
            c["novel"] = ""
        if c["call"] == "TAKE":
            prem = PREMORTEM.get(cid, "")
            if not prem:
                raise SystemExit("seal: TAKE without a pre-mortem: %s" % cid)
        pair = MINIMAL_PAIR.get(cid, "")
        flip = FLIP.get(cid, "")
        sections = DEEP.get(cid, "TRIAGE-INDEX-ONLY")
        depth = "DEEP" if cid in DEEP else "TRIAGE"
        out.append({
            "cid": cid, "call": c["call"], "conf": c["conf"],
            "primary": c["primary"], "against": c["against"],
            "interaction": "", "novel": c["novel"],
            "premortem": prem, "minimal_pair": pair, "flip_threshold": flip,
            "sections_read": sections, "depth": depth,
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
    print("E1D3 sealed: %d rows appended (%d TAKE, %d SKIP), %d deep reads"
          % (len(out), n_take, len(out) - n_take, len(DEEP)))


if __name__ == "__main__":
    sys.exit(main())
