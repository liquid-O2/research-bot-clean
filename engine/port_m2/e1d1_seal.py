#!/usr/bin/python3
"""E1 STUDY DAY 1 — seal the day ledger (CC-M2-3/4/5 annotations).

Takes the reader's executable policy output, applies the reader's DEEP-READ
OVERRIDES (the discretionary part — a mechanical rule is not a reader), and
emits the committed ledger with every CC-M2-4/5 annotation:
taint, pre-mortem per TAKE, minimal pair + flip threshold per deep-read TAKE,
per-call deep-read section log.

TAINT (this day's protocol defect, recorded not hidden): the deterministic
draw for E1 study day 1 (chronologically first STUDY session per asset) is
2021-07-01 for ALL THREE assets — the same three sessions the P-M2c warm-up
drew from.  WARMUP_POSTMORTEMS.md is mandated inherited memory, so the reader
carries explicit outcome knowledge into this day:
  DIRECT  — the 9 warm-up cids themselves (certificate, wall, MAE all known);
  WINDOW  — same asset, decision second at or after the earliest warm-up cid
            of that asset, because the warm-up post-mortems state peak times,
            wall times and leg directions inside those windows
            (HG >= 19514, SI >= 12312, NKD >= 27 — i.e. all of NKD);
  CLEAN   — everything earlier (HG < 19514, SI < 12312): 75 candidates.
Scores are reported on the full day AND on CLEAN; CLEAN is the honest one.
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import used_cases as UC                                        # noqa: E402

READER = "opus-discretionary"   # the E1 study reader (ledger header)

WARMUP = {
    "NKD-20210701-000027-L", "NKD-20210701-007741-L", "NKD-20210701-052433-L",
    "SI-20210701-012312-S", "SI-20210701-025274-L", "SI-20210701-052332-L",
    "HG-20210701-019514-L", "HG-20210701-052246-S", "HG-20210701-055858-S",
}
WINDOW_FROM = {"HG": 19514, "SI": 12312, "NKD": 27}

# ---- the reader's deep reads: cid -> sections actually read on the sheet ----
DEEP = {
    "HG-20210701-002106-S":  "S3,S4,S5,S7,S8",
    "HG-20210701-011157-L":  "S3,S4,S5,S7,S8,S9,S13",
    "SI-20210701-011096-L":  "S3,S4,S5",
    "SI-20210701-046816-L":  "S3,S4,S5",
    "NKD-20210701-047023-L": "S3,S4,S5,S7,S8,S9",
    "HG-20210701-048897-S":  "S7,S8",
    "HG-20210701-049049-L":  "S3,S4,S5,S7,S8,S9",
    "HG-20210701-052246-S":  "S7,S8",
    "SI-20210701-054339-S":  "S3,S4,S8",
    "HG-20210701-054648-S":  "S7,S8",
    "HG-20210701-057765-S":  "S3,S4,S8",
}

# ---- discretionary OVERRIDES of the executable policy ----------------------
# (call, conf, primary, against, novel)
OVERRIDE = {
 "SI-20210701-054339-S": (
   "TAKE", "B",
   "primary: S4 OR_EXT NY|OR30|k1.0|+1 = 26.5200 tc=1 test_m=2 PENDING — the "
   "NY phase high 26.5225@15:03:03 (S3, 156s old) printed on the FIRST test of "
   "the NY opening-range k1.0 extension and failed; S3 phase NY L=26.2950 "
   "leaves room=$987.50 inside the phase range so the $1,000 bar needs only "
   "$12.50 of new range; S3 runway to_phase_close=28460s (session close); "
   "S8 60s n=119 vol=248 is a live book. B2 + A5, the warm-up's confirmed "
   "winning object (#9).",
   "against: T5 fails — S8 phase sflow=-44 on 7752 contracts (0.6% imbalance) "
   "is no parent-order footprint at all, so P015 gives this trade no push; "
   "S4 stacked resistance 26.5000/26.5031/26.5106 sits only $37-90 above the "
   "entry, i.e. the stop side is dense and close; S9 rv1800/rv60=4.47.",
   "novel: the P015 flow-concordance term is formulated for a P001 rollover "
   "and does NOT generalise to a level-first-test entry — the mechanism there "
   "is a failed test of a calibrated level, not a continuing parent order. "
   "Overriding a term of my own rule on named mechanism grounds, before "
   "unblinding."),
}

PREMORTEM = {
 "HG-20210701-052246-S":
   "PRE-MORTEM: this loses if the 14:27 NY high was a pause in an UP leg — "
   "the phase sflow of -878 is only 12.3% of phase volume and S8 fuel has "
   "5738 of 7143 contracts BELOW the mid, so a squeeze of that inventory "
   "takes the $900 wall out before the session close 8.5h away.",
 "HG-20210701-054648-S":
   "PRE-MORTEM: this loses to the give-back mechanism of warm-up #17 — "
   "S8 through_book_600s thru_ask=24 vs thru_bid=9 says the last ten minutes "
   "were BUY-side aggression; if that is the start of a leg rather than a "
   "retracement I am short into it with 7.8h of hold and a $900 wall.",
 "HG-20210701-054652-S":
   "PRE-MORTEM: identical to 054648-S four seconds later with a weaker "
   "accel (-5.0 vs -21.3); it loses the same way and, under D-046, it cannot "
   "even be filled if 054648-S is held.",
 "HG-20210701-055858-S":
   "PRE-MORTEM: this loses if the 15:29:48 high is a breakout retest rather "
   "than a rollover — S3 COVERAGE NY is already 68.5% with unspent $488.2, so "
   "the phase's median move is nearly spent and a further $1,000 down needs "
   "the NY range to run past its own q50 ladder rung.",
 "HG-20210701-055938-S": "PRE-MORTEM: as 055858-S, 80s later and $62.50 worse "
   "on entry; it loses identically and forfeits under D-046 if 055858-S fills.",
 "HG-20210701-055955-S": "PRE-MORTEM: as 055858-S; the extra $125 of adverse "
   "entry is the whole difference and it is the difference that pays the wall.",
 "HG-20210701-055963-S": "PRE-MORTEM: as 055858-S; slope -175 is the steepest "
   "of the cluster, which is exactly when a short is chasing.",
 "HG-20210701-055979-S": "PRE-MORTEM: as 055858-S; entering 121s later into a "
   "move already 4 ticks lower is how a good thesis becomes a bad fill.",
 "HG-20210701-055997-S": "PRE-MORTEM: as 055858-S; by now S8 60s n=147 — the "
   "crowd is in, which is where warm-up #17's give-back started.",
 "HG-20210701-056493-S":
   "PRE-MORTEM: the phase extreme is 705s old here, so if the down-move has "
   "already found its buyer this is a mid-leg entry with no fresh rejection "
   "behind it — warm-up D1 is still an open question and this is the case "
   "that answers it against me.",
 "SI-20210701-054339-S":
   "PRE-MORTEM: this loses if 26.52 was a breakout rather than a failed first "
   "test — SI's session is +$1,225 on the day with S3 range_so_far $1,775 of "
   "range_hat $2,555.6 and NOTHING in S8 (phase sflow -44/7752) says the "
   "buyers are done; a continuation through 26.52 puts the $900 wall in play "
   "inside an hour.",
}

MINIMAL_PAIR = {
 "SI-20210701-054339-S":
   "MINIMAL PAIR: SI-20210701-054934-S (15:15:34, same asset/side/phase, "
   "10 minutes later) — SKIP. THE DIFFERENCE: S3 room inside the phase range "
   "collapses from $987.50 to $287.50 (ext_needed $12.50 -> $712.50) because "
   "price has already travelled toward the NY low; every other term is "
   "similar or better (slope -137.5 vs -12.5). Capacity-to-bar, not "
   "momentum, is what separates them.",
 "HG-20210701-055858-S":
   "MINIMAL PAIR: HG-20210701-057765-S (16:02:45, same asset/side/phase) — "
   "SKIP. THE DIFFERENCE: S3 phase-extreme age 70s vs 1977s; the flow, "
   "coverage, runway and spread terms are all within noise of each other. "
   "The freshness of the rejection is the only separating field.",
 "HG-20210701-052246-S":
   "MINIMAL PAIR: HG-20210701-049049-L (13:37:29, same asset/phase, 53 "
   "minutes earlier, LONG) — SKIP. THE DIFFERENCE: identical P001 geometry "
   "(cov below_q10, runway >30,000s, extreme <200s old, slope+accel signed) "
   "but S8 phase sflow=-638 points AGAINST the long and WITH this short. "
   "Direction, not geometry.",
 "HG-20210701-054648-S":
   "MINIMAL PAIR: HG-20210701-054957-S (15:15:57, 5 minutes later) — SKIP. "
   "THE DIFFERENCE: S5 mid_slope flips to +12.5 with accel +43.7 (the "
   "retracement is under way) while S3 ext_needed worsens $242.50 -> $400.",
}

FLIP = {
 "SI-20210701-054339-S":
   "FLIP THRESHOLD: S3 phase NY L. At the committed values the bar needs "
   "$12.50 of new range; the call flips to SKIP once S3 ext_needed exceeds "
   "$450 (i.e. once the entry is within $550 of the NY low, mid <= 26.4050 "
   "at this phase low), and flips regardless if S4 shows the 26.5200 "
   "OR-extension level with tc>=3 (no longer a first test).",
 "HG-20210701-052246-S":
   "FLIP THRESHOLD: S8 phase sflow. The call flips to SKIP at sflow >= 0 "
   "(concordance lost) or at |sflow|/phase_vol < 0.05 (5% of 7,143 = 357 "
   "contracts); it also flips at S3 COVERAGE NY >= 75% with S3 unspent "
   "<= $450 (P002's exit-second veto).",
 "HG-20210701-054648-S":
   "FLIP THRESHOLD: S5 mid_slope_$/min(T-5m). At -43.8 the call stands; at "
   "slope >= 0 or accel >= 0 it flips to SKIP (T6), which is exactly what "
   "happens 5 minutes later at 054957-S.",
 "HG-20210701-055858-S":
   "FLIP THRESHOLD: S3 phase-extreme age. At 70s the call stands; past 900s "
   "it flips to SKIP (T7). Second flip: S3 ext_needed past $450 — here it is "
   "$50, so the bar lives almost entirely inside the NY range already.",
}


def taint(cid, asset, sec):
    if cid in WARMUP:
        return "DIRECT"
    if sec >= WINDOW_FROM.get(asset, 0):
        return "WINDOW"
    return "CLEAN"


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
        # D-046 duplicates are TAKEs in the ledger: the thesis is "this is a
        # seat".  panel_score's one-position replay FORFEITS the ones that
        # cannot be filled and records the forfeit — pre-filtering them here
        # would hide the reader's real discrimination in the SKIP pool.
        if r["dup_of"]:
            call = "TAKE"
            primary = idx_primary(i)
            agst = ("against: D-046 one position at a time — if "
                    "%s is filled and held to its exit second this candidate "
                    "cannot be entered; it is committed as a seat, and the "
                    "replay forfeits it." % r["dup_of"])
        if r["cid"] in OVERRIDE:
            call, conf, primary, agst, novel = OVERRIDE[r["cid"]]
        out.append({
            "cid": r["cid"], "call": call, "conf": conf, "primary": primary,
            "against": agst, "interaction": "", "novel": novel,
            "premortem": PREMORTEM.get(r["cid"], "" if call == "SKIP" else "-"),
            "minimal_pair": MINIMAL_PAIR.get(r["cid"], ""),
            "flip_threshold": FLIP.get(r["cid"], ""),
            "sections_read": DEEP.get(r["cid"], "TRIAGE-INDEX-ONLY"),
            "depth": "DEEP" if r["cid"] in DEEP else "TRIAGE",
            "taint": taint(r["cid"], i["asset"], int(i["sec"])),
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
            fh.write("\t".join(str(r[c]).replace("\t", " ") for c in cols) + "\n")

    # ---- CC-M2-17.4: THE SEAL AUTO-RECORDS ITS OWN USED CASES -------------
    # The day-5 gap class: a seal appended a day-complete STUDY session to the
    # day ledger and the USED-CASE LEDGER never heard about it, so a session
    # that HAD been read stayed untainted and could have been drawn BLIND.
    # Recording is no longer a step a lane can forget — it is part of sealing.
    _new, _dup = UC.record_seal([r["cid"] for r in out], era="E1",
                                block="STUDY", mode=UC.MODE_STUDY,
                                rnd="E1D1", reader=READER,
                                path=a.used_case_ledger)
    sys.stderr.write("used-case ledger: +%d new, %d already recorded -> %s\n"
                     % (len(_new), _dup, a.used_case_ledger))

    n = sum(1 for r in out if r["call"] == "TAKE")
    sys.stderr.write("sealed %d rows (%d TAKE) -> %s\n" % (len(out), n, a.out))


def idx_primary(i):
    return ("primary: S3 COVERAGE %s=%s%% unspent=$%s + S9 ladder_position=%s "
            "+ S3 runway=%ss to a session-close exit + S8 phase sflow=%s on "
            "%s contracts (concordant, %.1f%% imbalance) + S5 mid_slope=%s "
            "accel=%s + S3 phase extreme %ss old; S3 room inside the phase "
            "range=$%s so the bar needs only $%s of extension"
            % (i["phase_dec"], i["cov_phase"], i["pct_unspent_phase"],
               i["ladder_pos"], i["runway_phase"], i["fph_sflow"],
               i["fph_vol"],
               100.0 * abs(float(i["fph_sflow"])) / float(i["fph_vol"]),
               i["slope5m"], i["accel"], i["extreme_age_trade_side"],
               i["room_phase"], i["ext_needed"]))


if __name__ == "__main__":
    main()
