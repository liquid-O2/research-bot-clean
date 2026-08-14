#!/usr/bin/python3
"""E1 STUDY DAY 6 — the reader's committed triage policy, made executable.

Successor to `e1d1..e1d5_policy.py`, ALL FIVE of which are FROZEN as mechanical
baselines for this day (CC-M2-8.2).  Draw: SI/HG/NKD **2021-07-08**, 1,618
day-complete candidates (SI 515, HG 389, NKD 714).

=======================================================================
THE DAY IS THE CC-M2-15.5 / CC-M2-16.1 SIDE-EVIDENCE STUDY
=======================================================================
The orchestrator's brief fixes the shape: the inherited refusal core with the
CC-M2-16.4 T5 repair, the CC-M2-16.2 veto granularity law (V2/V3 obeyed, V1
dead), P025's runway floor, and a DECLARED SIDE EXPERIMENT at the (asset,
phase) CELL grain.  Nothing here is a free design.

 (a) POLICY = day-4's inherited five-term refusal core, T5 REPAIRED, P025's
     runway floor at 12,000s, and NO candidate-level direction term.
 (b) VETOES = V2 (fuel-map overhang) and V3 (P018 two-stream opposition), the
     two pre-mortem veto families that are net-positive refusals on all five
     study sessions.  **V1 (P028 bar-outside-developing-VA) is DEAD** — pooled
     -$12,592.50 and 91 of 99 winners lost (CC-M2-16.2), and it is not run.
     The vetoes bind the SEAT and the population alike here because CC-M2-16.2
     graded them at family level on pooled multi-session counts, which is the
     grading the law requires.
 (c) SIDE comes from the COMMITTED CELL-SIDE LEDGER
     (`provenance/port_m2/E1D6_CELL_SIDE_LEDGER.md`): one ex-ante call per
     (asset, phase) cell, committed before that cell's first candidate row,
     from the as-of stepper's cell-open briefs.  The table is transcribed below
     and is FIXED — it is the day's declared experiment.

=======================================================================
(a) THE REFUSAL CORE — FIVE TERMS, FOUR UNCHANGED, ONE REPAIRED
=======================================================================
 T1 LIVE BOOK      S8 60s n >= 5 and 60s vol >= 10.  P004; five sessions.
 T2 RUNWAY         S3 runway to the BINDING (phase-close) exit >= 12,000s.
                   P025: 276 of 276 D-021 winners over five day-complete
                   sessions, minimum winner runway 19,653s (CC-M2-16.3), zero
                   winners in the 304 rows below 12,000s.  Census batch 3
                   graded it a winner CONCENTRATOR (3.70x) and not an edge —
                   lawful here because a REFUSAL is not an entry.
 T3 FRESH EXTREME  S3 trade-side phase extreme <= 3,600s old.
 T4 AGGRESSION AT  S8 |5m sflow| >= 5% of the 5m volume, DE-SIGNED (the mirror
    MAGNITUDE      law CC-M2-13.1 forbids the OPPOSED sign; P007/P023).
 T5 MAGNITUDE      **REPAIRED PER CC-M2-16.4**: `v5 >= 200 OR v5 >= 8% of the
    FLOOR          phase's volume`.  The day-5 form was
                   `v5 >= 200 AND (v5 >= 500 OR v5 >= 8% phase)`, whose
                   ABSOLUTE gate fired before the relative clause could rescue
                   anything: NKD's four 2021-07-07 TOKYO winners carried 5m
                   volumes of 118-140 contracts at **41.5%-45.0% of phase
                   volume** and were refused by it (ERA_NOTES §55).  One line;
                   approved by the orchestrator for this day.

NOT IN THE RULE, each with its receipt: T6 ext_needed (P017, 0-for-3 as a
refusal), T7 jump_frac (P026, DEAD), every momentum/confirmation term (3-for-3
value-destroying in three disguises), the spread tax (P005), the through-book
side term, V1/P028 (DEAD, CC-M2-16.2), and any candidate-level direction term.

=======================================================================
(c) THE COMMITTED CELL-SIDE TABLE — the day's declared side experiment
=======================================================================
Committed in `E1D6_CELL_SIDE_LEDGER.md` cell by cell, each before its own
cell's first candidate row, from as-of briefs.  Three side sources are scored
against each other and against their mirrors at unblinding:

  READER   the committed calls below (the reader's judgement)
  P029     PHASE_SIDE_PRIOR: TOKYO/LONDON -> LONG, NY -> SHORT.  11 of 12
           winner-bearing cells over five sessions; beats its mirror on 4 of 5
           sessions and LOSES on 2021-07-02 => **FAILS CC-M2-13.1**, registered
           before the day.
  E1D6-CS  the reader's own six-component composite; **4 right / 6 wrong on the
           five unblinded sessions against its mirror's 6/4 => INADMISSIBLE**,
           also registered before the day.

  cell            READER   P029    E1D6-CS
  HG/TOKYO        LONG     LONG    LONG
  NKD/TOKYO       LONG     LONG    LONG
  SI/TOKYO        LONG     LONG    LONG
  HG/LONDON       SHORT    LONG    NOCALL
  SI/LONDON       SHORT    LONG    SHORT
  NKD/LONDON      SHORT    LONG    SHORT
  NKD/NY          SHORT    SHORT   SHORT
  HG/NY           SHORT    SHORT   SHORT
  SI/NY           SHORT    SHORT   LONG

PRE-REGISTERED ARMS (`--arm`), all reported at unblinding:
  CORE          the five refusal terms, no side gate, no vetoes
  CORE+READER   core + the committed cell-side table  (the day's calls, pre-veto)
  CORE+P029     core + the phase prior
  CORE+CS       core + the composite
  MIRROR        core + the OPPOSITE of the committed cell-side table
  READER+VETO   CORE+READER after V2/V3  (**the committed ledger calls**)

THE GRADE (CC-M2-10.5 form, unchanged since day 3 so calibration accumulates):
sigma_to_exit = S9 rv_nowcast w1800 * sqrt(runway_to_binding_exit / 1800);
A >= $2,500, B $1,200-2,500, C < $1,200.  It gates nothing.

PROSPECTIVE PATTERN REGISTRATION (CC-M2-4.3): P004 (T1), P025 (T2), A5
freshness (T3), P023's de-signed magnitude floor (T4+T5 repaired), P018 (V3),
the V2 fuel-overhang family, and **P029 PHASE_SIDE_PRIOR (new this day)** plus
**E1D6-CS (new this day)**.  Any pattern claim not in this list is post-hoc.

TAINT.  Every row carries `CLEAN;AS-OF-PREFIX`; every TAKE additionally carries
**`FORECAST-TRUTH-EXPOSED`** (defect D19: the regime-forecast file the reader
was directed to read carries realised session range / day-type / phase-share
columns beside its empty predictions; unsigned magnitude facts, no side, no
candidate outcome — declared in the cell-side ledger).
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
ARMS = ("CORE", "CORE+READER", "CORE+P029", "CORE+CS", "MIRROR")

# ------------------------------------------------- (c) the committed table --
READER_CELL = {
    ("HG", "TOKYO"): "LONG", ("NKD", "TOKYO"): "LONG", ("SI", "TOKYO"): "LONG",
    ("HG", "LONDON"): "SHORT", ("SI", "LONDON"): "SHORT",
    ("NKD", "LONDON"): "SHORT",
    ("NKD", "NY"): "SHORT", ("HG", "NY"): "SHORT", ("SI", "NY"): "SHORT",
}
CS_CELL = {
    ("HG", "TOKYO"): "LONG", ("NKD", "TOKYO"): "LONG", ("SI", "TOKYO"): "LONG",
    ("HG", "LONDON"): None, ("SI", "LONDON"): "SHORT",
    ("NKD", "LONDON"): "SHORT",
    ("NKD", "NY"): "SHORT", ("HG", "NY"): "SHORT", ("SI", "NY"): "LONG",
}
CELL_CONF = {
    ("HG", "TOKYO"): "MED", ("NKD", "TOKYO"): "LOW-MED",
    ("SI", "TOKYO"): "LOW-MED", ("HG", "LONDON"): "LOW",
    ("SI", "LONDON"): "MED-HIGH", ("NKD", "LONDON"): "MED",
    ("NKD", "NY"): "MED", ("HG", "NY"): "MED-HIGH", ("SI", "NY"): "MED",
}
CELL_EVIDENCE = {
    ("HG", "TOKYO"): "P029 TOKYO->LONG (11-for-1 pooled) + prior-session net "
                     "+$1,700 + S4 NDAY nearest -$1,863 (price above all "
                     "multi-day levels); no prior rows exist at this cut",
    ("NKD", "TOKYO"): "P029 TOKYO->LONG + S4 NDAY nearest -$1,150; prior "
                      "session net -$150 is inside the dead zone",
    ("SI", "TOKYO"): "P029 TOKYO->LONG + S4 NDAY nearest -$900 + HG bid in "
                     "Asia (+$200, pos 0.89, 349/419 trapped BELOW)",
    ("HG", "LONDON"): "OVERRIDE of P029: SI -$1,450 at pos 0.03 with 7,424 of "
                      "8,635 TOKYO contracts trapped ABOVE (86%) and phase "
                      "sflow -665/8,635; HG mid $94 under its developing POC",
    ("SI", "LONDON"): "OVERRIDE of P029: own TOKYO fuel map 7,424/1,211/8,635 "
                      "= 86% trapped ABOVE with sflow -665 (the V2 "
                      "configuration), pos 0.033, session -$1,450, S10 d_POC "
                      "-$337.5, S4 NDAY nearest +$650 (through the multi-day "
                      "structure)",
    ("NKD", "LONDON"): "OVERRIDE of P029: -$1,000 at pos 0.09, TOKYO fuel "
                       "956/280/1,312 = 73% trapped ABOVE, sflow -127/1,312; "
                       "cov_sess 83.3% with $257.70 unspent is the feasibility "
                       "caveat, and the book is dead (60s 0/0)",
    ("NKD", "NY"): "P029 NY->SHORT + session -$3,550 + LONDON fuel "
                   "1,833/219/2,052 = 89% trapped ABOVE; AGAINST: EXPANDED at "
                   "246.7% of range_hat, cov_sess 254%, d_POC -$2,588, in_VA=0",
    ("HG", "NY"): "P029 NY->SHORT + LONDON fuel 20,213/2,844/23,057 = 88% "
                  "trapped ABOVE (the day's largest overhang) + pos 0.104 + "
                  "session -$1,650; AGAINST: prior session +$1,700, NDAY back "
                  "to -$269, 5m sflow +42",
    ("SI", "NY"): "P029 NY->SHORT + S10 d_POC +$1,362 with in_VA=0 (price "
                  "above the developing VAH, value left $1,300 behind) + 60s "
                  "sflow -19/51 and slope1m -62.5 at the boundary + HG "
                  "-$1,600; AGAINST: pos 0.906 and 94% of LONDON volume "
                  "trapped BELOW (the composite's LONG)",
}


def F(r, k):
    try:
        return float(r[k])
    except Exception:
        return None


def sgn(v):
    return 0 if v is None else (1 if v > 0 else (-1 if v < 0 else 0))


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
    # CC-M2-16.4 REPAIR: relative-OR-absolute at the FLOOR, not only above it.
    t["T5"] = bool(v5 is not None
                   and (v5 >= F5_VOL_FLOOR
                        or (vph is not None and vph > 0
                            and v5 >= F5_VOL_REL * vph)))
    return t


# ------------------------------------------------------- (b) V2/V3 vetoes ---
def v2(r):
    """FUEL-MAP OVERHANG with the adverse stream still running.  Net-positive
    refusal on all five study sessions (sole-block 52 rows at -$131.32 with 3
    winners); RETAINED by CC-M2-16.2."""
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
    """P018 TWO-STREAM OPPOSITION.  Sole-blocks 27 rows at -$447.36 over five
    sessions with ONE winner refused; RETAINED by CC-M2-16.2."""
    side = side_of(r)
    s60, v60 = F(r, "f60_sflow"), F(r, "f60_vol")
    sl = F(r, "slope1m")
    if s60 is None or not v60 or v60 < 20 or sl is None:
        return False
    return bool(abs(s60) / v60 >= 0.10 and ((s60 < 0) == (side > 0))
                and ((sl < 0) == (side > 0)))


VETOES = (("V2", v2), ("V3", v3))


def veto_list(r):
    return [n for n, f in VETOES if f(r)]


# ------------------------------------------------------------- the gate ----
def side_gate(r, arm):
    c = cell(r)
    if arm == "CORE":
        return True, "no side gate on this arm"
    if arm == "CORE+P029":
        want = "LONG" if r["phase_dec"] in ("TOKYO", "LONDON") else "SHORT"
        why = ("P029 PHASE_SIDE_PRIOR: a %s cell is a %s cell in E1 (11 of 12 "
               "winner-bearing cells over five sessions; mirror-law FAILURE on "
               "2021-07-02 registered before the day)"
               % (r["phase_dec"], want))
    elif arm == "CORE+CS":
        want = CS_CELL.get(c)
        if want is None:
            return False, ("E1D6-CS composite is NOCALL on %s/%s (component "
                           "sum 0)" % c)
        why = ("E1D6-CS composite = %s on %s/%s (the six-component vote; "
               "INADMISSIBLE under CC-M2-13.1, registered before the day)"
               % (want, c[0], c[1]))
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


def evidence(r, t, gate_ok, gate_why, vetoed):
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
        gate_ok, gate_why = side_gate(r, arm)
        vl = veto_list(r) if (vetoes_on and core_ok and gate_ok) else []
        fire = core_ok and gate_ok and not vl
        out.append({
            "cid": r["cid"], "call": "TAKE" if fire else "SKIP",
            "conf": grade(r), "n_terms": sum(1 for k in TERMS if t[k]),
            "side_gate": int(bool(gate_ok)), "vetoes": "+".join(vl),
            "primary": evidence(r, t, gate_ok, gate_why, vl),
            "against": against(r, t),
            "sigma_to_exit": round(sigma_to_exit(r) or 0.0, 1),
            "event_in_session": event_in_session(r),
            "asset": r["asset"], "phase_dec": r["phase_dec"],
            "clock": r["clock"], "sec": int(float(r["sec"])),
            "side": r["side"], "cls": r["cls"],
            "cell_call": READER_CELL[cell(r)],
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
            + ["side_gate", "vetoes", "sigma_to_exit", "event_in_session",
               "asset", "phase_dec", "clock", "sec", "side", "cls",
               "cell_call", "primary", "against"])
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter="\t",
                           extrasaction="ignore")
        w.writeheader()
        for o in out:
            w.writerow(o)
    n_take = sum(1 for o in out if o["call"] == "TAKE")
    print("e1d6_policy [%s%s]: %d rows, %d TAKE, %d SKIP -> %s"
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
