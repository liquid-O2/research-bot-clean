#!/usr/bin/python3
"""E1 STUDY DAY 8 — the reader's committed triage policy, made executable.
THE FINAL STUDY DAY OF THE E1 ROUND.

Successor to `e1d1..e1d7_policy.py`, ALL SEVEN of which are FROZEN as mechanical
baselines for this day (CC-M2-8.2).  Draw: SI/HG/NKD **2021-07-12** (Monday),
949 day-complete candidates (SI 327, HG 304, NKD 318).  USED_CASE_LEDGER: 0
prior hits on 20210712.

=======================================================================
THE DAY RUNS THE THREE STAGES IN THEIR **CORRECTED** FORMS (CC-M2-19)
=======================================================================
CC-M2-19 corrected two things about day 7's stack and this policy is those
corrections made executable:

 (1) STAGE 1 IS A ROLLING PER-ROW STATE, NOT A PER-CELL CALL (CC-M2-19.1).
     Day 7 fixed the seat call at each cell's open and it INVERTED — NKD/TOKYO
     opened at `rv1800` 53.0 and paid 68 winners four to eight hours later at
     `rv1800` 278-602.  Here the feasibility state is evaluated AT EVERY
     CANDIDATE'S OWN ROW:
         R1  `rv1800` >= 250            (449 of 484 winners over seven
                                         day-complete sessions = 92.8% recall,
                                         7.37% win rate = 1.23x, and a 0.29x
                                         REFUSAL below it)
         R2b `unspent_bind` >= $1,000   (CC-M2-19.4's resurrection of the
                                         capacity term, in the ERA_NOTES §77
                                         BINDING-ROW form — the pooled 7-session
                                         sweep says the binding row beats the
                                         session row: 8.74% win rate at 1.46x
                                         lift and the ONLY arm of the whole
                                         sweep with a POSITIVE mean certificate,
                                         +$9.17/row over 2,540 rows)
     Both thresholds settled on the POOLED ROW POOL, never on a replay
     (ERA_NOTES §33/§41).  250 is P030's published top band edge; $1,000 is the
     D-021 bar itself.  Neither is new this day.

 (2) COMPOSITION ORDER IS SIDE > SEAT > MOMENT (CC-M2-19.2).  The side is the
     binding stage (+$2,030 oracle on day 7, +$2,542 over core); feasibility is
     second (-$268 oracle-seat alone); the moment is not free (40% capture on a
     right-cell-right-side).  The ledger commits the SIDE first, per cell,
     before that cell's first candidate row.

 (3) MOMENT = the day-6 core with the CC-M2-16.4 T5 repair, + V2.  **V3/P018 is
     ADVISORY TODAY, NOT APPLIED**: CC-M2-19.4 put V2/V3 under a pooled
     re-grade and V3 is net-negative on two consecutive sessions with a $0.00
     replay delta three times running.  Running a term whose grade is under
     revision would contaminate the last study day; it is COMPUTED AND LOGGED
     on every row so the re-grade gets this session's count.

 (4) P033 (runway x rv1800) is CENSUS-FIRST and IS NOT TRADED RAW (briefing
     law).  Its seven-session decile table is in the pre-registration.

THE GRADE (CC-M2-10.5 form, unchanged since day 3 so calibration accumulates):
sigma_to_exit = S9 rv1800 * sqrt(runway_to_binding_exit / 1800); A >= $2,500,
B $1,200-2,500, C < $1,200.  It gates nothing.  Its top band has been empty of
winners for four consecutive sessions (ERA_NOTES §69/§79).

TAINT.  Every row carries `CLEAN;AS-OF-PREFIX`.  No forecast_*.tsv or
truth_*.tsv is opened (the D19 exposure class avoided by construction); the
three forecaster columns are `.` on all 949 rows (CC-M2-17.2: the forecaster
has no 2021 output at all).
"""
import argparse
import csv
import math
import os
import sys

RUNWAY_MIN = 12000.0
FRESH_MAX = 3600.0
F5_FRAC = 0.05
F5_VOL_FLOOR = 200.0
F5_VOL_REL = 0.08
GRADE_A, GRADE_B = 2500.0, 1200.0

# --- the CORRECTED stage-1 rolling constants (pooled 7-session pre-reg) ------
RV_ROW_MIN = 250.0
UNSPENT_BIND_MIN = 1000.0

TERMS = ("T1", "T2", "T3", "T4", "T5")
ARMS = ("CORE", "CORE+SEAT", "CORE+SIDE", "CORE+SEAT+SIDE", "MIRROR",
        "CORE+ORACLE_NONE")

# ---------------------------------------------------------------------------
# THE COMMITTED PER-CELL SIDE TABLE (stage 2).  One call per (asset, phase)
# cell, each committed BEFORE that cell's first candidate row from the as-of
# stepper briefs (`e1d8_cellbrief.py`), transcribed here and FIXED.  Filled by
# the reader during the chronological cell walk; see
# provenance/port_m2/E1D8_CELL_LEDGER.md for the evidence behind each call.
# ---------------------------------------------------------------------------
READER_CELL = {
    ("HG", "TOKYO"): "LONG", ("NKD", "TOKYO"): "LONG", ("SI", "TOKYO"): "LONG",
    ("HG", "LONDON"): "SHORT", ("SI", "LONDON"): "SHORT",
    ("NKD", "LONDON"): "LONG",
    ("HG", "NY"): "SHORT", ("SI", "NY"): "SHORT", ("NKD", "NY"): "SHORT",
}
CELL_CONF = {
    ("HG", "TOKYO"): "LOW", ("NKD", "TOKYO"): "LOW-MED",
    ("SI", "TOKYO"): "LOW",
    ("HG", "LONDON"): "MED-HIGH", ("SI", "LONDON"): "MED",
    ("NKD", "LONDON"): "LOW",
    ("HG", "NY"): "MED", ("SI", "NY"): "MED-HIGH", ("NKD", "NY"): "MED",
}
# Cells the reader would ABSTAIN from spending a seat in, committed with the
# side call (ERA_NOTES §70.4: cell-level abstention has never been scored).
WOULD_ABSTAIN = {("HG", "TOKYO"), ("SI", "TOKYO"), ("NKD", "LONDON"),
                 ("NKD", "NY")}
CELL_EVIDENCE = {
    ("HG", "TOKYO"): "consensus SILENT (X7's -9 of 146 contracts dismissed on "
                     "size); the only evidence is OVERNIGHT CONTINUATION — all "
                     "three assets closed 2021-07-09 in the top fifth of their "
                     "ranges (HG +$1,650 at pos 0.80) and HG gapped UP $150",
    ("NKD", "TOKYO"): "consensus SILENT; overnight continuation at maximum "
                      "strength — NKD closed 2021-07-09 at pos 0.96 (the "
                      "session high) on +$3,800, vol_regime HIGH rv5/rv66 "
                      "1.218 says the move is live, and q50 $1,468 with "
                      "unspent_bind $1,281 says the phase can pay the bar",
    ("SI", "TOKYO"): "consensus SILENT; the weakest instance of the overnight "
                     "continuation (SI +$1,000 at pos 0.84) — and SI/TOKYO is "
                     "0-for-7 winner-bearing cells over the round, the "
                     "strongest structural abstention on the board",
    ("HG", "LONDON"): "CONSENSUS SHORT, load-bearing term X2: HG is -$700 on "
                      "the session at pos 0.12, printing its low into the "
                      "London open; X8 slope15m -5; S10's CONTINUATION form "
                      "agrees at d_POC -587.5 with in_VA=0",
    ("SI", "LONDON"): "CONSENSUS SHORT: SI at pos 0.00 (its session low) on "
                      "-$400, X8 -5, S10 continuation d_POC -662.5 outside VA "
                      "— AGAINST and named: SI/LONDON is 3-for-3 LONG over the "
                      "round and the 60s/5m books have turned BID at the low",
    ("NKD", "LONDON"): "consensus LONG on rounding-error magnitudes (a $650 "
                       "session range in 177 rows) — recorded as nominal; the "
                       "cell's decisive fact is stage 1, q50 $567 against a "
                       "$1,000 bar",
    ("HG", "NY"): "DECLARED OVERRIDE of the literal 2-of-3 consensus on the "
                  "rule stated at cell #3: X7 is noise at a cell's first "
                  "second, so the vote is 1-1 and judgment decides — HG "
                  "-$1,150 at pos 0.04, the whole complex at session lows, "
                  "HG/NY 0 LONG / 3 SHORT over the round, 5m and 30m selling",
    ("SI", "NY"): "both LONG votes fall under the magnitude standard applied "
                  "at cells #1/#3 (slope15m +0.8; fph_sflow +2 on an empty "
                  "phase window), so the only substantive vote is X2: SI "
                  "-$1,050 at pos 0.10 after three consecutive phases of "
                  "one-way selling; SI/NY is 4 SHORT / 2 LONG over the round",
    ("NKD", "NY"): "no consensus (X8 +5.8 LONG vs X2 SHORT); broken by S10's "
                   "CONTINUATION form firing SHORT at d_POC -487.5 with "
                   "in_VA=0, and by NKD's reversal from a flat TOKYO into a "
                   "-$550 LONDON closing at pos 0.06",
}
# The reader may ABSTAIN from a cell's side (value "NONE"): an abstained cell
# takes NO seat at all.  Day 6 spent a seat in all nine cells and four were
# empty; ERA_NOTES §70.4 registered cell-level abstention as a decision the
# ledger has never scored.  It is scorable this day.


def F(r, k):
    try:
        return float(r[k])
    except Exception:
        return None


def side_of(r):
    return 1 if r["side"] == "LONG" else -1


def cell(r):
    return (r["asset"], r["phase_dec"])


# ------------------------------------------------------------ the core -----
def terms(r):
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
                   and abs(s5) / v5 >= F5_FRAC)
    vph = F(r, "fph_vol")
    t["T5"] = bool(v5 is not None
                   and (v5 >= F5_VOL_FLOOR
                        or (vph is not None and vph > 0
                            and v5 >= F5_VOL_REL * vph)))
    return t


# --------------------------------------- (1) the ROLLING stage-1 state ------
def rolling_seat(r):
    """CC-M2-19.1: feasibility evaluated at THIS row, not at the cell open."""
    rv = F(r, "rv1800")
    if rv is None or rv < RV_ROW_MIN:
        return False, ("rolling seat state CLOSED: S9 rv_nowcast w1800 = %s at "
                       "this row, under the %d floor that holds 449 of 484 "
                       "winners (92.8%%) over seven day-complete sessions and "
                       "refuses at 0.29x" % (r.get("rv1800"), int(RV_ROW_MIN)))
    b = F(r, "unspent_bind")
    if b is not None and b < UNSPENT_BIND_MIN:
        return False, ("rolling seat state CLOSED: S3 unspent on the BINDING "
                       "row = $%s against the $%d D-021 bar — the binding "
                       "phase cannot pay the bar from here (ERA_NOTES §77's "
                       "field, pooled 7-session win rate 8.74%% = 1.46x above "
                       "it and the only positive-mean arm of the sweep)"
                       % (r.get("unspent_bind"), int(UNSPENT_BIND_MIN)))
    return True, ("rolling seat state OPEN: rv1800 = %s >= %d and the binding "
                  "row has $%s of unspent expected move against a $1,000 bar"
                  % (r.get("rv1800"), int(RV_ROW_MIN), r.get("unspent_bind")))


# ------------------------------------------------------- (3) V2 / V3 --------
def v2(r):
    """FUEL-MAP OVERHANG with the adverse stream still running.  RETAINED by
    CC-M2-16.2 (net-positive sole-block on six sessions)."""
    side = side_of(r)
    ta, tb, pt = F(r, "trapped_above"), F(r, "trapped_below"), F(r, "phase_total")
    if ta is None or tb is None or not pt:
        return False
    frac = (ta / pt) if side > 0 else (tb / pt)
    if frac < 0.90:
        return False
    s5, v5 = F(r, "f5m_sflow"), F(r, "f5m_vol")
    flow = bool(s5 is not None and v5 and abs(s5) / v5 >= 0.10
                and ((s5 < 0) == (side > 0)))
    tn, tbid, task = F(r, "thru_n"), F(r, "thru_bid"), F(r, "thru_ask")
    book = bool(tn is not None and tn >= 10 and tbid is not None
                and task is not None
                and ((tbid >= 2 * task) if side > 0 else (task >= 2 * tbid)))
    return flow or book


def v3(r):
    """P018 TWO_STREAM_OPPOSITION — **ADVISORY ONLY TODAY** (CC-M2-19.4 pooled
    re-grade in flight; net-negative on 2021-07-08 and 2021-07-09)."""
    side = side_of(r)
    s60, v60 = F(r, "f60_sflow"), F(r, "f60_vol")
    sl = F(r, "slope1m")
    if s60 is None or not v60 or v60 < 20 or sl is None:
        return False
    return bool(abs(s60) / v60 >= 0.10 and ((s60 < 0) == (side > 0))
                and ((sl < 0) == (side > 0)))


def veto_list(r):
    """BINDING vetoes only.  V3 is logged separately (see `advisory`)."""
    return ["V2"] if v2(r) else []


def advisory(r):
    return ["V3"] if v3(r) else []


# ------------------------------------------------------------- the gates ----
def seat_gate(r, arm):
    if arm in ("CORE", "CORE+SIDE"):
        return True, "no rolling-seat gate on this arm"
    return rolling_seat(r)


def side_gate(r, arm):
    c = cell(r)
    if arm in ("CORE", "CORE+SEAT"):
        return True, "no side gate on this arm"
    want = READER_CELL.get(c, "NONE")
    if want == "NONE":
        return False, ("SIDE: the committed cell-side call is ABSTAIN on "
                       "%s/%s — %s" % (c[0], c[1],
                                       CELL_EVIDENCE.get(c, "(no call)")))
    if arm == "MIRROR":
        want = "LONG" if want == "SHORT" else "SHORT"
    why = ("COMMITTED CELL-SIDE CALL %s on %s/%s (%s confidence) — %s"
           % (want, c[0], c[1], CELL_CONF.get(c, "?"),
              CELL_EVIDENCE.get(c, "")))
    if r["side"] != want:
        return False, ("SIDE: %s and this candidate is a %s" % (why, r["side"]))
    return True, why


# ------------------------------------------------------------- the grade ----
def sigma_to_exit(r):
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
    la, nx, rw = (F(r, "sched_last_age"), F(r, "sched_next_in"),
                  F(r, "runway_sess"))
    if la is not None:
        return 1
    if nx is not None and rw is not None and nx < rw:
        return 1
    return 0


def _pct(r, num, den):
    a, b = F(r, num), F(r, den)
    if a is None or not b:
        return "."
    return "%.1f" % (100.0 * abs(a) / b)


def evidence(r, t, seat_ok, seat_why, gate_ok, gate_why, vetoed, adv):
    if not t["T1"]:
        return ("primary: S8 60s n=%s vol=%s — no transacting counterparty in "
                "the last minute (T1, P004 DEAD_BOOK_VETO, seven day-complete "
                "sessions)" % (r["f60_n"], r["f60_vol"]))
    if not t["T2"]:
        return ("primary: S3 runway to the binding %s phase close = %ss "
                "against the 12,000s floor (T2 = P025, which CC-M2-19.3 BROKE "
                "on 2021-07-09 — 54 of 123 winners sat below it — and which is "
                "retained here only so the moment core stays identical to its "
                "six frozen predecessors; the feasibility work is now done by "
                "the ROLLING state)" % (r["phase_dec"], r["runway_phase"]))
    if not t["T3"]:
        return ("primary: S3 %s-phase extreme on the trade's side is %ss old — "
                "past the 3,600s window there is no rejection object left to "
                "trade (T3, A5)" % (r["phase_dec"], r["extreme_age_trade_side"]))
    if not t["T4"]:
        return ("primary: S8 5m sflow=%s on %s contracts = %s%% of its own "
                "volume, under the 5%% floor — no aggressive stream at "
                "magnitude for either side to absorb (T4, de-signed P023)"
                % (r["f5m_sflow"], r["f5m_vol"], _pct(r, "f5m_sflow",
                                                      "f5m_vol")))
    if not t["T5"]:
        return ("primary: S8 5m vol=%s against phase vol=%s — under 200 "
                "contracts AND under 8%% of the phase's own volume (T5 as "
                "REPAIRED per CC-M2-16.4)" % (r["f5m_vol"], r["fph_vol"]))
    if not gate_ok:
        return ("primary: %s [STAGE 2, the BINDING stage under CC-M2-19.2's "
                "measured composition order: the moment core passes and this "
                "SKIP is the committed cell-side call and nothing else]"
                % gate_why)
    if not seat_ok:
        return ("primary: %s [STAGE 1 in its CC-M2-19.1 CORRECTED ROLLING "
                "form — the state is read at THIS row, not at the cell open "
                "that broke day 7]" % seat_why)
    if vetoed:
        return ("primary: V2 VETO on a row the core, the cell side and the "
                "rolling seat state all admit — S8's FUEL MAP puts >= 90%% of "
                "the phase's transacted volume against this trade with the "
                "adverse stream still running (CC-M2-16.2 retains V2; V3 is "
                "ADVISORY today under the CC-M2-19.4 pooled re-grade and is "
                "logged, not applied)")
    return ("primary: the moment core passes — S8 60s n=%s vol=%s is a live "
            "book [T1, P004]; %ss of runway to the binding %s close [T2]; the "
            "trade-side extreme is %ss old [T3]; S8 5m sflow=%s on %s = %s%% "
            "of its own volume [T4] over the repaired magnitude floor against "
            "a phase volume of %s [T5]; the ROLLING seat state is OPEN "
            "(rv1800=%s >= 250, unspent_bind=$%s >= $1,000) [CC-M2-19.1/19.4]; "
            "no V2 veto%s — and %s"
            % (r["f60_n"], r["f60_vol"], r["runway_phase"], r["phase_dec"],
               r["extreme_age_trade_side"], r["f5m_sflow"], r["f5m_vol"],
               _pct(r, "f5m_sflow", "f5m_vol"), r["fph_vol"], r["rv1800"],
               r["unspent_bind"],
               (" [ADVISORY V3 fires and is NOT applied today]" if adv else ""),
               gate_why))


def against(r, t):
    bits = []
    fph, vph = F(r, "fph_sflow"), F(r, "fph_vol")
    if fph is not None and vph:
        bits.append("S8 phase sflow=%s on %s (%.1f%%) — P015 reads this as the "
                    "direction and it is 1-1 across seven sessions"
                    % (r["fph_sflow"], r["fph_vol"], 100.0 * abs(fph) / vph))
    ext = F(r, "ext_needed")
    if ext is not None:
        bits.append("S3 ext_needed=$%s of BRAND-NEW range for the bar (P017, "
                    "0-for-4 as a refusal — recorded, not traded)"
                    % r["ext_needed"])
    dp = F(r, "d_POC")
    if dp is not None:
        bits.append("S10 d_POC=%s in_VA=%s (the SIDE reading of this field is "
                    "the only hand instrument CC-M2-18.3 left standing and the "
                    "day-8 pre-registration measures its literal "
                    "back-to-value form at 2 right / 6 wrong over seven "
                    "sessions)" % (r["d_POC"], r["in_VA"]))
    ta, tb, pt = F(r, "trapped_above"), F(r, "trapped_below"), F(r, "phase_total")
    if pt:
        bits.append("S8 FUEL MAP %s above / %s below / %s total (P031 DEAD "
                    "FINAL per CC-M2-18.3; P009 dead twice over)"
                    % (r["trapped_above"], r["trapped_below"],
                       r["phase_total"]))
    sl = F(r, "slope15m")
    if sl is not None:
        bits.append("S5 mid_slope_$/min(15m)=%s — the field the day-8 stage-2 "
                    "sweep found best-of-twelve at the CELL grain (12/5) and "
                    "which is 3-for-3 value-destroying at the CANDIDATE grain"
                    % r["slope15m"])
    return "; ".join(bits) if bits else "no field of the sheet opposes."


# ------------------------------------------------------------------ calls ---
def call_day(rows, arm="CORE+SEAT+SIDE", vetoes_on=True):
    out = []
    for r in sorted(rows, key=lambda x: (int(float(x["sec"])), x["cid"])):
        t = terms(r)
        core_ok = all(t[k] for k in TERMS)
        gate_ok, gate_why = side_gate(r, arm)
        seat_ok, seat_why = seat_gate(r, arm)
        adv = advisory(r)
        vl = (veto_list(r) if (vetoes_on and core_ok and seat_ok and gate_ok)
              else [])
        fire = core_ok and seat_ok and gate_ok and not vl
        out.append({
            "cid": r["cid"], "call": "TAKE" if fire else "SKIP",
            "conf": grade(r), "n_terms": sum(1 for k in TERMS if t[k]),
            "seat_gate": int(bool(seat_ok)),
            "side_gate": int(bool(gate_ok)), "vetoes": "+".join(vl),
            "advisory": "+".join(adv),
            "primary": evidence(r, t, seat_ok, seat_why, gate_ok, gate_why,
                                vl, adv),
            "against": against(r, t),
            "sigma_to_exit": round(sigma_to_exit(r) or 0.0, 1),
            "event_in_session": event_in_session(r),
            "asset": r["asset"], "phase_dec": r["phase_dec"],
            "clock": r["clock"], "sec": int(float(r["sec"])),
            "side": r["side"], "cls": r["cls"],
            "rv1800": r.get("rv1800"), "unspent_bind": r.get("unspent_bind"),
            "cell_call": READER_CELL.get(cell(r), "NONE"),
            **{k: int(t[k]) for k in TERMS}})
    return out


def seat_cells(calls):
    cells = {}
    for c in calls:
        if c["call"] == "TAKE":
            cells.setdefault((c["asset"], c["phase_dec"]), []).append(c["cid"])
    return cells


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--index", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--arm", default="CORE+SEAT+SIDE")
    p.add_argument("--no-vetoes", action="store_true")
    p.add_argument("--quiet", action="store_true")
    a = p.parse_args()
    with open(a.index) as fh:
        lines = [ln for ln in fh if not ln.startswith("#")]
    rows = list(csv.DictReader(lines, delimiter="\t"))
    out = call_day(rows, arm=a.arm, vetoes_on=not a.no_vetoes)
    cols = (["cid", "call", "conf", "n_terms"] + list(TERMS)
            + ["seat_gate", "side_gate", "vetoes", "advisory",
               "sigma_to_exit", "event_in_session", "asset", "phase_dec",
               "clock", "sec", "side", "cls", "rv1800", "unspent_bind",
               "cell_call", "primary", "against"])
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter="\t",
                           extrasaction="ignore")
        w.writeheader()
        for o in out:
            w.writerow(o)
    n_take = sum(1 for o in out if o["call"] == "TAKE")
    print("e1d8_policy [%s%s]: %d rows, %d TAKE, %d SKIP -> %s"
          % (a.arm, "" if not a.no_vetoes else " NO-VETO", len(out), n_take,
             len(out) - n_take, a.out))
    for cellk, cids in sorted(seat_cells(out).items()):
        print("   SEAT CELL %-12s %3d takes, first = %s"
              % ("/".join(cellk), len(cids), cids[0]))
    if not a.quiet:
        for o in out:
            if o["call"] == "TAKE":
                print("   TAKE %-28s %s %s %s"
                      % (o["cid"], o["clock"], o["side"], o["conf"]))


if __name__ == "__main__":
    sys.exit(main())
