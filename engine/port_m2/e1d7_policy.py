#!/usr/bin/python3
"""E1 STUDY DAY 7 — the reader's committed triage policy, made executable.

Successor to `e1d1..e1d6_policy.py`, ALL SIX of which are FROZEN as mechanical
baselines for this day (CC-M2-8.2).  Draw: SI/HG/NKD **2021-07-09**, 1,388
day-complete candidates (SI 315, HG 407, NKD 666).

=======================================================================
THE DAY IS THE CC-M2-17.1 THREE-STAGE DECOMPOSITION
=======================================================================
CC-M2-17.1 decomposes the decision into (1) SEAT EXISTENCE, (2) CELL SIDE,
(3) MOMENT.  Day 6 ran stages 2+3 only and lost the replay at 0.600 side
accuracy because four of its nine cells held no winner on either side.  This
policy runs all three, and takes ONLY in cells the reader called seat=YES AND
only on the called side.

 (a) MOMENT CORE = day-4's inherited five-term refusal core with the
     CC-M2-16.4 T5 repair and P025's 12,000s runway floor.  No candidate-level
     direction term (the mirror law killed them all).
 (b) VETOES = V2 (fuel-map overhang) and V3 (P018 two-stream opposition), the
     two families CC-M2-16.2 retains on pooled multi-session grading.  V1
     (P028) is DEAD and is not run.
 (c) STAGE 1 + STAGE 2 come from the COMMITTED PER-CELL LEDGER
     (`provenance/port_m2/E1D7_CELL_LEDGER.md`): one SEAT call and one SIDE
     call per (asset, phase) cell, each committed BEFORE that cell's first
     candidate row from the as-of stepper briefs
     (`e1d7_cellbrief.py` / `e1d7_stage12.py`).  Both tables are transcribed
     below and are FIXED.

THE DECLARED STAGE-1 RULE (pre-registered on the 54 cells of days 1-6):
     S1* = rv1800 >= 250  OR  (rv1800 >= 150 AND prior-cell $range >= 1000)
     -> 16 of 54 cells, 11 with >=1 D-021 winner (precision 0.688 against a
     0.315 base rate), winner recall 0.884.  Both thresholds are P030's own
     published band edges and the D-021 bar; neither was settled on a replay.
THE DECLARED STAGE-2 PRIMARY (same pre-registration):
     S2a P031 CROSS-ASSET FUEL OVERHANG >= 0.75 -> 10 right / 2 wrong / 5
     silent over six sessions (0.833), MIRROR 0.167, and it LOSES ONE SESSION
     (2021-07-02, the release session) => it FAILS CC-M2-13.1 as a standing
     term.  Registered before the day exactly as P029 was on day 6.
     Secondary S2c (S10 outside-VA side reading) scores 2/2 at $500 over six
     sessions and is demoted to the tie-break slot.
     P009's OWN-asset reading scores 0.417 vs its mirror's 0.583 over 54 cells
     — the six-session confirmation of the day-6 sign inversion.

PRE-REGISTERED ARMS (`--arm`), all reported at unblinding, so the composition
can be priced against its parts (the report CC-M2-17.1 asks for):
  CORE           the five refusal terms alone
  CORE+SEAT      + stage 1 only (cells called seat=YES, either side)
  CORE+SIDE      + stage 2 only (the day-6 arm: every cell, called side)
  CORE+SEAT+SIDE + both = the READER's committed calls (pre-veto)
  MIRROR         core + stage 1 + the OPPOSITE of every side call
  CORE+P029      core + the phase prior (reference)
  READER+VETO    CORE+SEAT+SIDE after V2/V3 = **the committed ledger calls**

THE GRADE (CC-M2-10.5 form, unchanged since day 3 so calibration accumulates):
sigma_to_exit = S9 rv1800 * sqrt(runway_to_binding_exit / 1800); A >= $2,500,
B $1,200-2,500, C < $1,200.  It gates nothing.  Its top band has now been empty
for three sessions (ERA_NOTES §69).

TAINT.  Every row carries `CLEAN;AS-OF-PREFIX`.  **No forecast_*.tsv or
truth_*.tsv was opened today (CC-M2-17.2/D19), so the day-6
`FORECAST-TRUTH-EXPOSED` stamp does NOT recur.**  The three forecaster columns
are `.` on all 1,388 rows, as CC-M2-17.2 ruled they would be.
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

TERMS = ("T1", "T2", "T3", "T4", "T5")
ARMS = ("CORE", "CORE+SEAT", "CORE+SIDE", "CORE+SEAT+SIDE", "MIRROR",
        "CORE+P029")

# ------------------------------- (c) the committed stage-1 / stage-2 tables --
# SEAT: the declared S1* rule as the reader committed it, cell by cell, before
# each cell's first candidate row.
SEAT_CELL = {
    ("HG", "TOKYO"): False, ("NKD", "TOKYO"): False, ("SI", "TOKYO"): False,
    ("HG", "LONDON"): False, ("SI", "LONDON"): False,
    ("NKD", "LONDON"): True,
    ("HG", "NY"): True, ("NKD", "NY"): True, ("SI", "NY"): True,
}
READER_CELL = {
    ("HG", "TOKYO"): "SHORT", ("NKD", "TOKYO"): "SHORT",
    ("SI", "TOKYO"): "SHORT",
    ("HG", "LONDON"): "SHORT", ("SI", "LONDON"): "LONG",
    ("NKD", "LONDON"): "SHORT",
    ("HG", "NY"): "LONG", ("NKD", "NY"): "LONG", ("SI", "NY"): "LONG",
}
CELL_CONF = {
    ("HG", "TOKYO"): "LOW", ("NKD", "TOKYO"): "LOW", ("SI", "TOKYO"): "LOW-MED",
    ("HG", "LONDON"): "MED", ("SI", "LONDON"): "MED-HIGH",
    ("NKD", "LONDON"): "MED-HIGH",
    ("HG", "NY"): "MED", ("NKD", "NY"): "MED", ("SI", "NY"): "LOW-MED",
}
SEAT_EVIDENCE = {
    ("HG", "TOKYO"): "SEAT=NO: rv1800 144.2 (P030 band 100-150, 5.5% of the "
                     "round's winners), session's first cell so no prior-cell "
                     "travel exists",
    ("NKD", "TOKYO"): "SEAT=NO: rv1800 53.0 (P030 BOTTOM band <100, 3.3%), "
                      "book dead at the open (60s 1/1), vol_regime LOW",
    ("SI", "TOKYO"): "SEAT=NO: rv1800 119.2 collapsing to rv60 25.0 (band "
                     "100-150), no prior cell, 60s 0/0",
    ("HG", "LONDON"): "SEAT=NO: rv1800 112.7 with a prior cell that travelled "
                      "$975 — the E1D6 HG/LONDON configuration the "
                      "pre-registration named as S1*'s known cost, refused as "
                      "written",
    ("SI", "LONDON"): "SEAT=NO by 31 points of rv: rv1800 218.7 (band 150-250) "
                      "but the prior cell travelled only $450, so S1*'s second "
                      "clause fails on the tape's own evidence",
    ("NKD", "LONDON"): "SEAT=YES on both clauses: rv1800 532.8 (P030 TOP band "
                       ">=250, 60.4% of winners) and a prior cell that "
                       "travelled $4,150 (net +$2,200); AGAINST: EXPANDED at "
                       "238.1% of range_hat with unspent_sess -$2,497",
    ("HG", "NY"): "SEAT=YES on clause 2: rv1800 231.0 (band 150-250) and a "
                  "prior cell that travelled $2,125 (net +$1,300); runway "
                  "35,981s to a session-close exit",
    ("NKD", "NY"): "SEAT=YES on clause 2: rv1800 223.6 and a prior cell that "
                   "travelled $1,400; AGAINST: 283% of range_hat, "
                   "unspent_sess -$3,209, and a dead book at the open",
    ("SI", "NY"): "SEAT=YES on both clauses: rv1800 290.5 (TOP band) and a "
                  "prior cell that travelled $1,600 (net +$1,000); the only "
                  "seat cell with capacity left (AT_RANGE, 69.2% of range_hat)",
}
CELL_EVIDENCE = {
    ("HG", "TOKYO"): "prior-session P031 (extension): SI's 07-08 NY carries "
                     "0.73 of 33,947 = ~24,800 trapped longs, the board's "
                     "largest overhang, against NKD's ~1,960 trapped shorts",
    ("NKD", "TOKYO"): "same prior-session SI overhang; S2a's intraday fire is "
                      "NOMINAL (HG/TOKYO 0.67 of 121 contracts)",
    ("SI", "TOKYO"): "S2a fires above 0.85: HG/TOKYO 312 above / 5 below / 317",
    ("HG", "LONDON"): "S2a P031 at size: SI/TOKYO 4,971 above / 110 below / "
                      "5,081 (0.978) with SI -$350 at pos 0.00; tie-break over "
                      "NKD's 1,826 trapped shorts by contract count 2.7:1",
    ("SI", "LONDON"): "S2a P031, both cross-assets agreeing: HG/TOKYO 0.86 "
                      "BELOW (11,452) and NKD/TOKYO 0.91 BELOW (1,826) — "
                      "13,278 cross-asset contracts short into a market that "
                      "has not broken; P009's own-asset 0.978-above reading "
                      "(the day-6 disaster field) is INVERTED, not followed",
    ("NKD", "LONDON"): "S2a HG/LONDON 3,566 above / 737 below / 4,419 (0.807) "
                       "+ S2c S10 d_POC +$2,600 with in_VA=0 (the largest "
                       "price-vs-value gap available); AGAINST: +$2,200 on the "
                       "session at pos 0.94",
    ("HG", "NY"): "S2a SI/LONDON 0.894 BELOW (10,455 trapped shorts) and "
                  "NKD/LONDON 0.842 BELOW, agreeing — the primary instrument "
                  "OVERRULES the secondary (S2c d_POC +$1,656 outside VA says "
                  "SHORT) by the declared procedure",
    ("NKD", "NY"): "the same SI/LONDON 0.894-BELOW overhang plus HG/LONDON "
                   "0.696 BELOW (20,281 contracts); S2c silent (in_VA=1)",
    ("SI", "NY"): "DECLARED OVERRIDE of S2a's literal form (which fires SHORT "
                  "on HG's 80-contract-old NY block): the size-aware form "
                  "(200-contract floor, 6/1 = 0.857 over six sessions) fires "
                  "LONG on NKD/LONDON 0.842 BELOW, and the board's real "
                  "overhang is HG/LONDON's 20,281 trapped shorts",
}


def F(r, k):
    """The typed read.  None = REFUSED, never a zero and never a NaN.

    R73: this returned `float(r[k])` unguarded, so a value that was ALREADY a
    NaN float came back as NaN rather than None — and every comparison against
    a NaN is False, so a veto's `frac < 0.90` guard passed the row through a
    SECOND branch that also evaluated False.  "Does not fire" is the pass
    direction for a veto, so a NaN input silently turned the veto off twice
    over.  The consumers that feed this module dicts of floats (the batch-5
    re-grade, `batch5_census._row_dict`) are exactly where NaN arrives.
    """
    try:
        v = float(r[k])
    except Exception:
        return None
    return None if (v != v or v in (float("inf"), float("-inf"))) else v


# R72: `-1` is the EVENT-CACHE REFUSAL SENTINEL for the through-book triple
# (`batch5_census._pack:409-411` writes it when the event cache is absent or
# `--no-events` is set; `batch5_census.event_rows:1691-1693` correctly maps
# `-1 -> NaN` for the same fields).  `_row_dict:1526-1527` passes it RAW, and
# `v2` then evaluated `tn >= 10` on `-1.0` as if it were data — so under
# `--no-events` V2's book clause can never fire and the pooled re-grade
# silently measures a different veto than the one being graded.  A count is
# never negative: the sentinel (and any negative) is a REFUSAL here.
THRU_FIELDS = ("thru_n", "thru_bid", "thru_ask")
THRU_REFUSAL_SENTINEL = -1.0


def FT(r, k):
    """`F` for the through-book triple, with the -1 refusal sentinel refused."""
    v = F(r, k)
    if v is None or v <= THRU_REFUSAL_SENTINEL or v < 0:
        return None
    return v


def sgn(v):
    return 0 if v is None else (1 if v > 0 else (-1 if v < 0 else 0))


SIDES = {"LONG": 1, "SHORT": -1}


def side_of(r):
    """+1 LONG / -1 SHORT / None REFUSED.

    R45: `1 if r["side"] == "LONG" else -1` mapped EVERY unrecognised token to
    SHORT, which INVERTS the fuel-overhang veto rather than refusing it.
    Verified on the bytes: every `side` cell of every committed E1 triage index
    is LONG or SHORT, so no call changes — but the failure mode was silent
    inversion, not an error.
    """
    return SIDES.get(str(r.get("side")))


# ------------------------------------------- the declared veto semantics ----
REFUSED = "R"            # = m2_common.REFUSED_TOKEN

PARAMS = {
    "spec_section": "CC-M2-17.1 three-stage decomposition (E1 STUDY day 7)",
    "core_terms": "T1..T5, all REFUSING on a missing input (missing -> the "
                  "term is False -> SKIP): the conservative direction",
    "veto_refusal_law": "R73 — for a VETO, 'does not fire' is the PASS "
                        "direction, so a refused input must not be spelled the "
                        "same way as a measured absence of overhang. `v2`/`v3` "
                        "keep their frozen BOOLEAN fire set exactly "
                        "(CC-M2-8.2: this file is a mechanical baseline); "
                        "`v2_state`/`v3_state` are three-valued (True / False "
                        "/ 'R') and every call row carries "
                        "`v2_state`/`v3_state`/`veto_inputs_refused` so the "
                        "population split is recoverable",
    "veto_pass_on_refused_selector": "DECLARED: a veto whose inputs are "
                                     "refused makes NO STATEMENT about that "
                                     "row; the row is then decided by CORE + "
                                     "the stage gates alone. V2 selects the "
                                     "sub-population whose S8 fuel map AND "
                                     "through-book are readable; V3 selects "
                                     "the sub-population whose 60s flow and "
                                     "1m slope are readable",
    "thru_refusal_sentinel": "R72 — `thru_n`/`thru_bid`/`thru_ask` == -1 is "
                             "the event-cache REFUSAL SENTINEL, not a count. "
                             "It is refused here rather than compared against "
                             "the >= 10 threshold as a number, so a "
                             "`--no-events` re-grade is now visibly a "
                             "different (refused) population instead of a "
                             "silently never-firing book clause",
    "nan_is_refused": "R73 — `F()` returns None on a non-finite value; a NaN "
                      "used to survive `frac < 0.90` and pass through a second "
                      "branch that also evaluated False",
}


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
    # CC-M2-16.4 REPAIR: relative-OR-absolute at the FLOOR, not only above it.
    t["T5"] = bool(v5 is not None
                   and (v5 >= F5_VOL_FLOOR
                        or (vph is not None and vph > 0
                            and v5 >= F5_VOL_REL * vph)))
    return t


# ------------------------------------------------------- (b) V2/V3 vetoes ---
def v2_state(r):
    """THREE-VALUED V2 (R72/R73).  True = the veto FIRES, False = it does not
    fire on READABLE inputs, "R" = its inputs are refused and V2 makes no
    statement about this row.

    The FIRE set is bit-identical to the frozen boolean rule: every branch that
    returned True still returns True and every branch that returned False on
    readable inputs still returns False.  What changes is that the branches
    which returned False because an input was ABSENT (or was the `-1` sentinel,
    or was a NaN) now say REFUSED instead of pretending the fuel map was
    measured and found flat.

    FUEL-MAP OVERHANG with the adverse stream still running.  Net-positive
    refusal on all five study sessions (sole-block 52 rows at -$131.32 with 3
    winners); RETAINED by CC-M2-16.2.
    """
    side = side_of(r)
    if side is None:                                   # R45
        return REFUSED
    ta, tb, pt = F(r, "trapped_above"), F(r, "trapped_below"), F(r, "phase_total")
    if ta is None or tb is None or not pt:
        return REFUSED
    frac = (ta / pt) if side > 0 else (tb / pt)
    if frac < 0.90:
        return False                                   # a measured pass
    s5, v5 = F(r, "f5m_sflow"), F(r, "f5m_vol")
    flow = bool(s5 is not None and v5 and abs(s5) / v5 >= 0.10
                and ((s5 < 0) == (side > 0)))
    if flow:
        return True
    tn, tbid, task = FT(r, "thru_n"), FT(r, "thru_bid"), FT(r, "thru_ask")
    if tn is None or tbid is None or task is None:
        return REFUSED            # R72: the book clause could not be read
    if tn >= 10 and ((tbid >= 2 * task) if side > 0 else (task >= 2 * tbid)):
        return True
    return False if (s5 is not None and v5) else REFUSED


def v3_state(r):
    """THREE-VALUED V3, same law as `v2_state`.

    P018 TWO-STREAM OPPOSITION.  Sole-blocks 27 rows at -$447.36 over five
    sessions with ONE winner refused; RETAINED by CC-M2-16.2.
    """
    side = side_of(r)
    if side is None:                                   # R45
        return REFUSED
    s60, v60 = F(r, "f60_sflow"), F(r, "f60_vol")
    sl = F(r, "slope1m")
    if s60 is None or v60 is None or sl is None:
        return REFUSED                                 # R73: refused, not pass
    if not v60 or v60 < 20:
        return False                                   # a measured pass
    return bool(abs(s60) / v60 >= 0.10 and ((s60 < 0) == (side > 0))
                and ((sl < 0) == (side > 0)))


def v2(r):
    """The frozen boolean: the veto FIRES.  CC-M2-8.2 — unchanged behaviour."""
    return v2_state(r) is True


def v3(r):
    """The frozen boolean: the veto FIRES.  CC-M2-8.2 — unchanged behaviour."""
    return v3_state(r) is True


VETOES = (("V2", v2), ("V3", v3))
VETO_STATES = (("V2", v2_state), ("V3", v3_state))


def veto_list(r):
    return [n for n, f in VETOES if f(r)]


def veto_refusals(r):
    """The vetoes that made NO STATEMENT about this row because their inputs
    were refused — the counted half of the declared pass-on-refused selector."""
    return [n for n, f in VETO_STATES if f(r) == REFUSED]


def _tok(state):
    return REFUSED if state == REFUSED else ("1" if state is True else "0")


# ------------------------------------------------------------- the gate ----
def seat_gate(r, arm):
    """STAGE 1 (CC-M2-17.1): does the reader's committed SEAT call admit this
    cell at all?  A seat=NO cell is refused however good the candidate is —
    the term day 6 did not have."""
    c = cell(r)
    if arm in ("CORE", "CORE+SIDE", "CORE+P029"):
        return True, "no seat gate on this arm"
    if SEAT_CELL[c]:
        return True, ("SEAT=YES on %s/%s — %s" % (c[0], c[1], SEAT_EVIDENCE[c]))
    return False, ("SEAT: the committed stage-1 call refuses this cell — %s"
                   % SEAT_EVIDENCE[c])


def side_gate(r, arm):
    """STAGE 2: the committed cell-side call."""
    c = cell(r)
    if arm in ("CORE", "CORE+SEAT"):
        return True, "no side gate on this arm"
    if arm == "CORE+P029":
        want = "LONG" if r["phase_dec"] in ("TOKYO", "LONDON") else "SHORT"
        why = ("P029 PHASE_SIDE_PRIOR: a %s cell is a %s cell in E1 (13 of 17 "
               "winner-bearing cells over six sessions; mirror-law FAILURES on "
               "2021-07-02 and 2021-07-08 registered before the day)"
               % (r["phase_dec"], want))
    else:
        want = READER_CELL[c]
        if arm == "MIRROR":
            want = "LONG" if want == "SHORT" else "SHORT"
        why = ("COMMITTED CELL-SIDE CALL %s on %s/%s (%s confidence) — %s"
               % (want, c[0], c[1], CELL_CONF[c], CELL_EVIDENCE[c]))
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


def evidence(r, t, seat_ok, seat_why, gate_ok, gate_why, vetoed):
    if not t["T1"]:
        return ("primary: S8 60s n=%s vol=%s — no transacting counterparty in "
                "the last minute (T1, P004 DEAD_BOOK_VETO, five day-complete "
                "sessions)" % (r["f60_n"], r["f60_vol"]))
    if not t["T2"]:
        return ("primary: S3 runway to the binding %s phase close = %ss "
                "against the 12,000s floor — P025 is 276-for-276 over five "
                "day-complete sessions with a minimum winner runway of "
                "19,653s and ZERO winners below 12,000s (T2)"
                % (r["phase_dec"], r["runway_phase"]))
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
                "REPAIRED per CC-M2-16.4: relative-OR-absolute at the floor, "
                "the one-line fix for the NKD seat the day-5 form hid)"
                % (r["f5m_vol"], r["fph_vol"]))
    if not seat_ok:
        return ("primary: %s [STAGE 1 of the CC-M2-17.1 decomposition: the "
                "five refusal terms all pass and this SKIP is the committed "
                "SEAT call — day 6's missing object]" % seat_why)
    if not gate_ok:
        return ("primary: %s [the declared CC-M2-16.1 cell-side experiment — "
                "the five refusal terms all pass, so this SKIP is the "
                "committed cell-side call and nothing else]" % gate_why)
    if vetoed:
        return ("primary: %s VETO on a row the core and the cell-side call "
                "both admit — %s (CC-M2-16.2 retains V2/V3 as the two veto "
                "families that are net-positive refusals on all five study "
                "sessions; V1/P028 is DEAD and is not run)"
                % ("+".join(vetoed),
                   "S8 FUEL MAP trapped-against >= 90%% of phase total with "
                   "the adverse stream still running" if "V2" in vetoed
                   else "S8 60s |sflow| >= 10%% of 60s volume with S5 "
                        "mid_slope(T-1m) opposed (P018)"))
    return ("primary: the five inherited refusal terms all pass — S8 60s n=%s "
            "vol=%s is a live book [T1, P004]; S3 gives %ss of runway to the "
            "binding %s phase close [T2, P025 276-for-276]; the trade-side %s "
            "extreme is %ss old [T3]; S8 5m sflow=%s on %s is an aggressive "
            "stream at %s%% of its own volume [T4, de-signed] and clears the "
            "REPAIRED magnitude floor against a phase volume of %s [T5, "
            "CC-M2-16.4]; no V2/V3 veto fires — and %s"
            % (r["f60_n"], r["f60_vol"], r["runway_phase"], r["phase_dec"],
               r["phase_dec"], r["extreme_age_trade_side"], r["f5m_sflow"],
               r["f5m_vol"], _pct(r, "f5m_sflow", "f5m_vol"), r["fph_vol"],
               gate_why))


def against(r, t):
    bits = []
    fph, vph = F(r, "fph_sflow"), F(r, "fph_vol")
    if fph is not None and vph:
        bits.append("S8 phase sflow=%s on %s (%.1f%%) — P015 reads this as the "
                    "direction and it is 1-1 across five sessions"
                    % (r["fph_sflow"], r["fph_vol"], 100.0 * abs(fph) / vph))
    ext = F(r, "ext_needed")
    if ext is not None:
        bits.append("S3 ext_needed=$%s of BRAND-NEW range for the bar (P017, "
                    "0-for-3 as a refusal — recorded, not traded)"
                    % r["ext_needed"])
    dp = F(r, "d_POC")
    if dp is not None:
        bits.append("S10 d_POC=%s in_VA=%s (P028 is DEAD as a magnitude veto; "
                    "the SIDE reading of this field is untested and is what "
                    "cell SI/NY turns on)" % (r["d_POC"], r["in_VA"]))
    ta, tb, pt = F(r, "trapped_above"), F(r, "trapped_below"), F(r, "phase_total")
    if pt:
        bits.append("S8 FUEL MAP %s above / %s below / %s total"
                    % (r["trapped_above"], r["trapped_below"], r["phase_total"]))
    sl = F(r, "slope1m")
    if sl is not None:
        bits.append("S5 mid_slope_$/min(T-1m)=%s, the field every momentum term "
                    "of days 1-5 was built on and which this rule does not read"
                    % r["slope1m"])
    return "; ".join(bits) if bits else "no field of the sheet opposes."


# ------------------------------------------------------------------ calls ---
def call_day(rows, arm="CORE+READER", vetoes_on=True):
    out = []
    for r in sorted(rows, key=lambda x: (int(float(x["sec"])), x["cid"])):
        t = terms(r)
        core_ok = all(t[k] for k in TERMS)
        seat_ok, seat_why = seat_gate(r, arm)
        gate_ok, gate_why = side_gate(r, arm)
        asked = bool(vetoes_on and core_ok and seat_ok and gate_ok)
        vl = veto_list(r) if asked else []
        vrf = veto_refusals(r) if asked else []
        fire = core_ok and seat_ok and gate_ok and not vl
        out.append({
            # R72/R73: the declared pass-on-refused selector, made countable.
            # "-" = the veto was never asked (CORE or a stage gate already
            # refused the row), which is not a veto refusal.
            "v2_state": ("-" if not asked else _tok(v2_state(r))),
            "v3_state": ("-" if not asked else _tok(v3_state(r))),
            "veto_inputs_refused": "+".join(vrf),
            "n_veto_inputs_refused": len(vrf),
            "cid": r["cid"], "call": "TAKE" if fire else "SKIP",
            "conf": grade(r), "n_terms": sum(1 for k in TERMS if t[k]),
            "seat_gate": int(bool(seat_ok)),
            "side_gate": int(bool(gate_ok)), "vetoes": "+".join(vl),
            "primary": evidence(r, t, seat_ok, seat_why, gate_ok, gate_why, vl),
            "against": against(r, t),
            "sigma_to_exit": round(sigma_to_exit(r) or 0.0, 1),
            "event_in_session": event_in_session(r),
            "asset": r["asset"], "phase_dec": r["phase_dec"],
            "clock": r["clock"], "sec": int(float(r["sec"])),
            "side": r["side"], "cls": r["cls"],
            "cell_call": READER_CELL[cell(r)],
            "cell_seat": int(SEAT_CELL[cell(r)]),
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
    p.add_argument("--arm", default="CORE+READER", choices=list(ARMS))
    p.add_argument("--no-vetoes", action="store_true")
    p.add_argument("--quiet", action="store_true")
    a = p.parse_args()
    with open(a.index) as fh:
        lines = [ln for ln in fh if not ln.startswith("#")]
    rows = list(csv.DictReader(lines, delimiter="\t"))
    out = call_day(rows, arm=a.arm, vetoes_on=not a.no_vetoes)
    cols = (["cid", "call", "conf", "n_terms"] + list(TERMS)
            + ["seat_gate", "side_gate", "vetoes", "v2_state", "v3_state",
               "veto_inputs_refused", "n_veto_inputs_refused",
               "sigma_to_exit",
               "event_in_session", "asset", "phase_dec", "clock", "sec",
               "side", "cls", "cell_call", "cell_seat", "primary", "against"])
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter="\t",
                           extrasaction="ignore")
        w.writeheader()
        for o in out:
            w.writerow(o)
    n_take = sum(1 for o in out if o["call"] == "TAKE")
    print("e1d7_policy [%s%s]: %d rows, %d TAKE, %d SKIP -> %s"
          % (a.arm, "" if not a.no_vetoes else " NO-VETO", len(out), n_take,
             len(out) - n_take, a.out))
    asked = [o for o in out if o["v2_state"] != "-"]
    print("  VETO REFUSAL ACCOUNTING (R72/R73, declared in PARAMS): vetoes "
          "asked on %d rows; V2 inputs refused on %d, V3 on %d"
          % (len(asked),
             sum(1 for o in asked if o["v2_state"] == REFUSED),
             sum(1 for o in asked if o["v3_state"] == REFUSED)))
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
