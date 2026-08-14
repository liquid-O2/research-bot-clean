#!/usr/bin/python3
"""E1 STUDY DAY 5 — the reader's committed triage policy, made executable.

Successor to `e1d1_policy.py`, `e1d2_policy.py`, `e1d3_policy.py` and
`e1d4_policy.py`, ALL FOUR of which are FROZEN as mechanical baselines for this
day (CC-M2-8.2).  This is NOT a mechanical baseline: it is the reader's own
decision rule for 2021-07-07, written down so 1,185 day-complete calls are
reproducible and so the RULE, not just the calls, is what a census can attack.

=======================================================================
THE DAY IS A DECLARED EXPERIMENT (CC-M2-13.4), NOT A FREE DESIGN
=======================================================================
The orchestrator fixed all three arms of this day BEFORE the reader saw the
session.  Nothing below is the reader's choice of terms; what the reader owes
is exact declaration, honest execution, and measurement of the delta:

  (a) POLICY = the day-4 report's INHERITED 5-TERM REFUSAL CORE + P025 runway
      conditioning, and NO new direction terms.
  (b) PRE-MORTEMS ARE VETOES.  The pre-mortem is written BEFORE the TAKE is
      finalised; if it names a mechanism that is MEASURABLE ON THE SHEET and
      PRESENT on this candidate's sheet, the TAKE becomes a SKIP.  Both the
      would-be take and the veto are logged so the delta of obeying is
      measurable (four-day pre-mortem record: 0/11, 5/6, 2/5, 3/3, ignored as
      a veto on every day it fired; ERA_NOTES §27/§47).
  (c) SIDE comes from the DECLARED FIRST-CONFIRMED-OUTCOME-SIGN ESTIMATOR
      (below), not from any candidate-level field.  Before the first
      confirmation exists, the reader ABSTAINS from takes.

=======================================================================
(a) THE REFUSAL CORE — FIVE TERMS, ALL INHERITED, NONE NEW
=======================================================================
E1_POSTMORTEMS §E1D4-F3 measured the day-4 rule minus the two terms that round
had fitted on its own pool: "the five terms inherited from days 1-3 (live book,
runway, freshness, opposed aggression, magnitude) — 80 takes, 8 winners, replay
+$4,277.50, capture 0.501".  Those five are the core, carried over unchanged
EXCEPT for the one edit the MIRROR LAW compels:

 T1 LIVE BOOK      S8 60s n >= 5 and 60s vol >= 10.  P004; the cheapest veto in
                   the sheet; four day-complete sessions of support (it passes
                   128 of day 4's 136 winners and refuses the dead tape that
                   carried none).  A refusal, side-blind, no mirror to fail.
 T2 RUNWAY         S3 runway to the BINDING (phase-close, CC-M2-10.3) exit
                   >= 12,000s.  P025 RUNWAY_TO_BINDING_EXIT: 230 of 230 D-021
                   winners over four day-complete sessions, zero exceptions,
                   minimum winner runway 13,146s.  Two roster fields and no
                   judgement; it is a SCHEDULING fact and has no mirror.
 T3 FRESH EXTREME  S3 trade-side phase extreme <= 3,600s old.  Side-conditional
                   but not a side SELECTOR: with the side fixed by (c) it is a
                   refusal ("there is no rejection object left to trade").
 T4 AGGRESSION AT  S8 |5m sflow| >= 5% of the 5m volume — **DE-SIGNED**.
    MAGNITUDE      Inherited term T4 required the aggression to be OPPOSED to
                   the trade.  CC-M2-13.1 adopted the MIRROR LAW program-wide
                   ("a direction term must beat its MIRROR on every session"),
                   and the opposed reading beats its mirror on ONE of four
                   sessions (+$223/+$427, +$157/-$587, +$251/+$232,
                   +$90/+$133 — ERA_NOTES §41, PATTERN_LEDGER P007/P023).
                   A binding law therefore FORBIDS its sign inside a reader
                   policy.  What survives is the half day 4 vindicated: an
                   ACTIVE aggressive stream at magnitude (P023's "magnitude
                   floor survives, the direction does not").  De-signing is not
                   a new term — it is the deletion of a term the law strikes,
                   and it is declared here, before the day.
 T5 MAGNITUDE      S8 5m vol >= 200 AND (>= 500 OR >= 8% of the phase's
                   volume) — the day-3 relative-OR-absolute repair; 92 of 94
                   winners of days 1-3 clear 200 contracts and T5 passes 107 of
                   day 4's 136.

NOT IN THE RULE, each with its receipt:
  * T6 ext_needed <= $450 and T7 jump_frac < 0.45 (P017-scoped, P026): the two
    terms day 4 added and the two that lost the day (-$7,231 of replay,
    E1D4-F3).  P026 is DEAD (falsified on its first outing).
  * EVERY momentum / confirmation term (four days, 3-for-3 value-destroying in
    three disguises, plus day 3's three refuted minimal pairs).
  * The spread tax (P005) and the through-book side term (struck on day 3).
  * ANY new direction term.  (a) forbids it and the round has earned it: every
    candidate-level direction object in the ledger now fails the mirror test on
    at least one session.

=======================================================================
(c) THE SIDE ESTIMATOR — DECLARED EXACTLY, BEFORE THE SESSION IS READ
=======================================================================
CC-M2-13.3 ordered the SESSION-SIDE STATE probe on the four-day meta-finding
that winners concentrate on ONE side per session (4/4 days) while every
candidate-level direction term has failed.  CC-M2-13.4(c) fixes the simplest
causal estimator as today's protocol.  Its exact form, declared here:

  DEFINITION (per ASSET-session; each asset is its own session and its own
  seat).  Walk the day's candidates of one asset in decision-second order.
  For a candidate c with decision second s_c, printed triage `mid` m_c,
  contract `mult` M_c, side sign d_c (+1 LONG, -1 SHORT) and `runway_phase`
  R_c, define its FAVOURABLE EXCURSION as of second S:
      exc_c(S) = max over candidate rows r of the SAME ASSET with
                 s_c < s_r <= min(S, s_c + R_c) of (m_r - m_c) * M_c * d_c
  i.e. the excursion is read from LATER ROWS' MID PATH — the only price path a
  chronological as-of reader can see — and it is bounded by c's OWN PHASE
  (phase-close seating, CC-M2-10.3: an excursion after c's phase close is not
  an outcome c could have banked).
  CONFIRMATION SECOND of c = the first s_r at which exc_c crosses $1,000
  (D-021 scale).  The SESSION SIDE STATE of an asset is UNSET until the
  earliest confirmation second over all its candidates; at that second it is
  set to that candidate's side d_c and it is FIXED FOR THE REST OF THE SESSION
  (CC-M2-13.4(c): "take only that side for the rest of the session").
  Every state change is logged (`side_state_log`).

  MEASUREMENT CONVENTIONS, declared so the number is reproducible and its
  error bar is known: the `mid` column is printed `%.4g` by the triage
  extractor, so the price grid is $50 (SI), $25 (HG), $50 (NKD) per step — the
  $1,000 threshold therefore carries up to ~5% quantisation error.  This is
  the instrument the reader actually has at the decision second; it is
  declared, not hidden.  STRICTLY CAUSAL: exc_c(S) reads only rows with
  s_r <= S, and the reader's own as-of prefix view (`e1d5_asof.py`) is the
  only view used for the discretionary half of the day.

  PRE-REGISTERED RECORD OF THIS ESTIMATOR ON THE FOUR UNBLINDED SESSIONS
  (lawful under CC-M2-9.4 — prior unblinded rounds only; run BEFORE the day-5
  index was scanned, and quoted here as the honest prior, not as a promise):

    session      asset  estimator side / confirmed at   realised winner side
    2021-07-01   HG     LONG  10:21:02                  SHORT   ** WRONG **
    2021-07-01   SI     LONG  15:03:02                  SHORT   ** WRONG **
    2021-07-01   NKD    SHORT 03:49:07                  (no winners)
    2021-07-02   HG     (never confirmed)               (no winners)
    2021-07-02   NKD    (never confirmed)               (no winners)
    2021-07-02   SI     LONG  14:35:29                  LONG    RIGHT, in time
    2021-07-05   HG     LONG  05:16:28                  LONG    RIGHT, TOO LATE
                                                        (all 8 winners entered
                                                         03:02:59-03:20:54)
    2021-07-05   SI/NKD (never confirmed)               (no winners)
    2021-07-06   HG     SHORT 15:05:14                  SHORT   RIGHT, in time
    2021-07-06   SI     SHORT 15:05:57                  SHORT   RIGHT, in time
    2021-07-06   NKD    SHORT 16:18:32                  SHORT   RIGHT, TOO LATE
                                                        (winners 15:07-15:33)

    SIGN: 5 right / 2 wrong on the seven asset-sessions that produced winners.
    TIMELINESS: 2 of the 5 right calls arrive after their session's winner
    window has closed.  The 2021-07-01 failure is the diagnostic one — the
    estimator confirms LONG at 15:03:02 and SI's 19 winners are NY SHORTS
    entered from 15:04 onward: it is a TREND-FOLLOWING estimator and it fires
    at the moment a trend is most likely to have just finished.

  MIRROR-LAW STATUS OF THE SIDE GATE, MEASURED BEFORE THE DAY (the test the
  round now applies to every direction claim).  Replay of the declared policy
  (core + side gate) against its own MIRROR (core + the OPPOSITE side gate),
  phase-close seating, on the four unblinded sessions:
      session     policy        mirror
      2021-07-01  -$3,568.75    +$2,815.00   <- the mirror wins
      2021-07-02  +$1,295.00      -$823.75
      2021-07-05    +$808.75    -$1,133.75
      2021-07-06  +$4,171.25    -$4,347.50
      pooled      +$2,706.25    -$3,488.75  (93 takes / 19 winners vs
                                             219 takes / 22 winners)
  **The side gate beats its mirror on THREE of four sessions, so by CC-M2-13.1
  it FAILS the mirror law and would not be admissible as a reader-minted term.
  It is traded today because CC-M2-13.4(c) declares it as the experiment, and
  this failure is registered BEFORE the day so the result cannot be re-read
  afterwards as a discovery.**  What today measures is whether the SIMPLEST
  causal day-side estimator earns its keep on a fifth, unseen session.

  PRE-REGISTERED COMPARISON ARMS (all reported at unblinding, all computable
  from this module: `--arm`):
      CORE        the five refusal terms, no side gate (both sides taken)
      CORE+SIDE   the declared policy (this day's committed calls, before the
                  pre-mortem vetoes)
      MIRROR      core + the opposite side gate
      CORE+SIGNED the five terms with T4's struck sign restored (what day 4
                  would have taken) — the mirror-law edit's own cost
      VETOED      the committed calls AFTER the pre-mortem vetoes (arm (b))

=======================================================================
(b) THE PRE-MORTEM VETO — THE PROTOCOL, DECLARED
=======================================================================
A pre-mortem is written for every candidate that would SPEND A SEAT (the first
surviving TAKE in an (asset, phase) cell — under CC-M2-10.3 every later TAKE in
that cell is forfeited, so the seat-spender is the only call that can change the
day's replay).  The pre-mortem must name the mechanism that would kill the
trade.  THE VETO TEST, applied as written and logged either way:
    is the named mechanism (i) MEASURABLE on the sheet (a field, a value, a
    threshold — not a mood), and (ii) ALREADY PRESENT at the decision second?
    If both: the TAKE becomes a SKIP with `premortem_veto=1`, and the seat
    passes to the next surviving TAKE of that cell, which gets its own
    pre-mortem.  If the mechanism is measurable but NOT yet present (a
    conditional "if X then Y"), the TAKE stands and the trigger is logged as a
    flip threshold.
Non-seat TAKEs inherit their cell's veto decision (they are forfeited either
way); the ledger records the inheritance rather than pretending to 112 separate
deep reads.

THE GRADE (CC-M2-10.5 form, unchanged from days 3-4 so calibration
accumulates): sigma_to_exit = S9 rv_nowcast w1800 * sqrt(runway_to_binding_exit
/ 1800); A >= $2,500, B $1,200-2,500, C < $1,200.  A magnitude-feasibility
scale, never a direction confidence, and it gates nothing.

PROSPECTIVE PATTERN REGISTRATION (CC-M2-4.3), committed before the day is
called: P004 (T1), P025 (T2), A5/freshness (T3), P023's magnitude floor
de-signed (T4+T5), and P027 SESSION_SIDE_FIRST_CONFIRMATION (new this day, the
declared estimator of (c)).  Any pattern claim not in this list is post-hoc and
is marked as such.

WHAT THE DAY LOOKS LIKE BEFORE ANY OUTCOME IS OPENED.  2021-07-07 is a normal
full session (`short_day=0`, observed close 82,799s on all three assets):
SI 391, HG 413, NKD 381 = 1,185 candidates.
"""
import argparse
import csv
import math
import os
import sys

RUNWAY_MIN = 12000.0        # T2
FRESH_MAX = 3600.0          # T3
F5_FRAC = 0.05              # T4
F5_VOL_FLOOR = 200.0        # T5
F5_VOL_ABS = 500.0          # T5
F5_VOL_REL = 0.08           # T5
CONFIRM_USD = 1000.0        # (c) D-021 scale
GRADE_A, GRADE_B = 2500.0, 1200.0

TERMS = ("T1", "T2", "T3", "T4", "T5")
ARMS = ("CORE", "CORE+SIDE", "MIRROR", "CORE+SIGNED")


def F(r, k):
    try:
        return float(r[k])
    except Exception:
        return None


def sgn(v):
    return 0 if v is None else (1 if v > 0 else (-1 if v < 0 else 0))


def side_of(r):
    return 1 if r["side"] == "LONG" else -1


# ------------------------------------------------------------ the core -----
def terms(r, signed=False):
    """{name: bool} for T1..T5 — a pure function of ONE triage-index row.

    `signed=True` restores T4's struck OPPOSED sign (the CORE+SIGNED arm).
    """
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
    if signed:
        t["T4"] = bool(t["T4"] and sgn(s5) == -side_of(r))

    vph = F(r, "fph_vol")
    t["T5"] = bool(v5 is not None and v5 >= F5_VOL_FLOOR
                   and (v5 >= F5_VOL_ABS
                        or (vph is not None and vph > 0
                            and v5 >= F5_VOL_REL * vph)))
    return t


# -------------------------------------------------- (c) the side estimator --
def side_state(rows, bar=CONFIRM_USD):
    """{asset: (confirm_sec, side, founder_cid, founder_sec)} or {asset: None}.

    STRICTLY CAUSAL by construction: a candidate's excursion is read only from
    rows at LATER decision seconds than its own and no later than its own phase
    close, and the state it sets is consumed only by rows at or after the
    confirmation second.  See the module docstring for the declared definition.
    """
    by = {}
    for r in rows:
        by.setdefault(r["asset"], []).append(r)
    out = {}
    for a, rs in by.items():
        rs = sorted(rs, key=lambda r: (int(float(r["sec"])), r["cid"]))
        best = None
        for i, c in enumerate(rs):
            mid, mult, rw = F(c, "mid"), F(c, "mult"), F(c, "runway_phase")
            if mid is None or mult is None or rw is None:
                continue
            d = side_of(c)
            s = int(float(c["sec"]))
            lim = s + rw
            for r2 in rs[i + 1:]:
                s2 = int(float(r2["sec"]))
                if s2 > lim:
                    break
                m2 = F(r2, "mid")
                if m2 is None:
                    continue
                if (m2 - mid) * mult * d >= bar:
                    if best is None or s2 < best[0]:
                        best = (s2, d, c["cid"], s)
                    break
        out[a] = best
    return out


def side_state_log(state):
    lines = []
    for a in sorted(state):
        b = state[a]
        if b is None:
            lines.append("%s: UNSET all session — no candidate's favourable "
                         "excursion reached $1,000 inside its own phase; the "
                         "estimator abstains and every %s row is a SKIP."
                         % (a, a))
        else:
            sec = b[0]
            lines.append("%s: UNSET -> %s at sec=%d (%02d:%02d:%02d), set by "
                         "%s (decision sec=%d): the first candidate of the "
                         "session whose favourable excursion crossed $1,000 "
                         "inside its own phase, read from later rows' mid path."
                         % (a, "LONG" if b[1] > 0 else "SHORT", sec,
                            sec // 3600, (sec % 3600) // 60, sec % 60,
                            b[2], b[3]))
    return lines


def side_gate(r, state, mirror=False):
    """(passes, reason).  Before confirmation: ABSTAIN (CC-M2-13.4(c))."""
    b = state.get(r["asset"])
    s = int(float(r["sec"]))
    if b is None:
        return False, ("SIDE-STATE UNSET: no D-021-scale move has completed on "
                       "%s this session, so no side is confirmed and the "
                       "declared estimator abstains" % r["asset"])
    if s < b[0]:
        return False, ("SIDE-STATE UNSET AT THIS SECOND: %s's first confirmed "
                       "$1,000 excursion completes at sec=%d, %ds after this "
                       "decision — before the first outcome exists the "
                       "declared protocol abstains from takes"
                       % (r["asset"], b[0], b[0] - s))
    want = -b[1] if mirror else b[1]
    if side_of(r) != want:
        return False, ("SIDE STATE = %s on %s (confirmed at sec=%d by %s) and "
                       "this candidate is a %s: the session-side experiment "
                       "takes one side only for the rest of the session"
                       % ("LONG" if want > 0 else "SHORT", r["asset"], b[0],
                          b[2], r["side"]))
    return True, ("SIDE STATE = %s on %s, confirmed at sec=%d by %s (the "
                  "session's first completed $1,000 excursion)"
                  % ("LONG" if want > 0 else "SHORT", r["asset"], b[0], b[2]))


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
    """S12 separator (CC-M2-12.3): recorded on every row, binding on none."""
    la, nx, rw = (F(r, "sched_last_age"), F(r, "sched_next_in"),
                  F(r, "runway_sess"))
    if la is not None:
        return 1
    if nx is not None and rw is not None and nx < rw:
        return 1
    return 0


# ---------------------------------------------------------------- evidence --
def _pct(r, num, den):
    a, b = F(r, num), F(r, den)
    if a is None or not b:
        return "."
    return "%.1f" % (100.0 * abs(a) / b)


def evidence(r, t, gate_ok, gate_why):
    """One line naming SHEET LINES (section+field+value) — never a vibe."""
    if not t["T1"]:
        return ("primary: S8 60s n=%s vol=%s — no transacting counterparty in "
                "the last minute (T1, P004 DEAD_BOOK_VETO; four day-complete "
                "sessions of support, 128 of day 4's 136 winners retained)"
                % (r["f60_n"], r["f60_vol"]))
    if not t["T2"]:
        return ("primary: S3 runway to the binding exit (%s phase close) = %ss "
                "against the 12,000s floor — P025 RUNWAY_TO_BINDING_EXIT is "
                "230-for-230 over four day-complete sessions (minimum winner "
                "runway 13,146s) and it is the only object of the round with "
                "no mirror to fail (T2)"
                % (r["phase_dec"], r["runway_phase"]))
    if not t["T3"]:
        return ("primary: S3 %s-phase extreme on the trade's side is %ss old — "
                "past the 3,600s window there is no rejection object left to "
                "trade (T3, A5 early-in-sequence)"
                % (r["phase_dec"], r["extreme_age_trade_side"]))
    if not t["T4"]:
        return ("primary: S8 5m sflow=%s on %s contracts = %s%% of its own "
                "volume, under the 5%% magnitude floor — there is no "
                "aggressive stream at magnitude here for either side to "
                "absorb (T4, the DE-SIGNED survivor of P023: the magnitude "
                "floor is vindicated, the direction is struck by the mirror "
                "law CC-M2-13.1)"
                % (r["f5m_sflow"], r["f5m_vol"], _pct(r, "f5m_sflow",
                                                      "f5m_vol")))
    if not t["T5"]:
        return ("primary: S8 5m vol=%s against phase vol=%s — not at magnitude "
                "on either the absolute (>=500) or the relative (>=8%% of "
                "phase volume) reading; 92 of the 94 winners of days 1-3 clear "
                "200 contracts (T5, the day-3 relative-OR-absolute repair)"
                % (r["f5m_vol"], r["fph_vol"]))
    if not gate_ok:
        return ("primary: %s [the declared day-5 side experiment, CC-M2-13.4(c) "
                "— the five refusal terms all pass on this row, so this SKIP "
                "is the side estimator's call and nothing else]" % gate_why)
    return ("primary: the five inherited refusal terms all pass — S8 60s n=%s "
            "vol=%s is a live book [T1, P004]; S3 gives %ss of runway to the "
            "binding %s phase close [T2, P025, 230-for-230]; the trade-side "
            "%s extreme is %ss old [T3]; S8 5m sflow=%s on %s contracts is an "
            "aggressive stream at %s%% of its own volume [T4, de-signed] and "
            "at magnitude against a phase volume of %s [T5] — and %s [the "
            "declared side estimator, CC-M2-13.4(c); NO candidate-level "
            "direction term is read on this day]"
            % (r["f60_n"], r["f60_vol"], r["runway_phase"], r["phase_dec"],
               r["phase_dec"], r["extreme_age_trade_side"], r["f5m_sflow"],
               r["f5m_vol"], _pct(r, "f5m_sflow", "f5m_vol"), r["fph_vol"],
               gate_why))


def against(r, t):
    """The strongest field pointing the other way — always named."""
    bits = []
    fph, vph = F(r, "fph_sflow"), F(r, "fph_vol")
    if fph is not None and vph:
        bits.append("S8 phase sflow=%s on %s (%.1f%%) — P015 reads this as the "
                    "direction and it is 1-1 across four sessions"
                    % (r["fph_sflow"], r["fph_vol"], 100.0 * abs(fph) / vph))
    ext = F(r, "ext_needed")
    if ext is not None:
        bits.append("S3 ext_needed=$%s — the bar needs that much BRAND-NEW "
                    "range beyond the phase extreme (P017; day 4's winners "
                    "needed a median $750, so this is recorded and not traded)"
                    % r["ext_needed"])
    jf = F(r, "jump_frac")
    if jf is not None:
        bits.append("S9 jump_frac_1800s=%s (P026, DEAD since E1D4 — recorded "
                    "for the census, binding on nothing)" % r["jump_frac"])
    sl = F(r, "slope1m")
    if sl is not None:
        bits.append("S5 mid_slope_$/min(T-1m)=%s, the field every momentum "
                    "term of days 1-4 was built on and which this rule "
                    "deliberately does not read" % r["slope1m"])
    if r["asset"] == "NKD":
        bits.append("NKD: 8 D-021 winners in 1,023 candidates over four "
                    "day-complete sessions (ERA_NOTES §45)")
    return "; ".join(bits) if bits else "no field of the sheet opposes."


# ------------------------------------------------------------------ calls ---
def call_day(rows, arm="CORE+SIDE"):
    """The day's calls.  NOT a pure function of one row: the SIDE STATE is a
    session-state variable computed causally over the prefix (CC-M2-13.3)."""
    state = side_state(rows)
    signed = (arm == "CORE+SIGNED")
    out = []
    for r in sorted(rows, key=lambda x: (int(float(x["sec"])), x["cid"])):
        t = terms(r, signed=signed)
        core_ok = all(t[k] for k in TERMS)
        if arm == "CORE" or arm == "CORE+SIGNED":
            gate_ok, gate_why = True, "no side gate on this arm"
        else:
            gate_ok, gate_why = side_gate(r, state, mirror=(arm == "MIRROR"))
        fire = core_ok and gate_ok
        out.append({
            "cid": r["cid"], "call": "TAKE" if fire else "SKIP",
            "conf": grade(r), "n_terms": sum(1 for k in TERMS if t[k]),
            "side_gate": int(bool(gate_ok)),
            "primary": evidence(r, t, gate_ok, gate_why),
            "against": against(r, t),
            "sigma_to_exit": round(sigma_to_exit(r) or 0.0, 1),
            "event_in_session": event_in_session(r),
            "asset": r["asset"], "phase_dec": r["phase_dec"],
            "clock": r["clock"], "sec": int(float(r["sec"])),
            "side": r["side"], "cls": r["cls"],
            **{k: int(t[k]) for k in TERMS}})
    return out, state


def seat_cells(calls):
    """(asset, phase) -> [cids of TAKEs in decision order].  Under CC-M2-10.3
    the FIRST take of a cell holds the seat to the phase close and every later
    take in that cell is forfeited, so the first is the only one that can move
    the day's replay — and the only one that needs its own pre-mortem."""
    cells = {}
    for c in calls:
        if c["call"] == "TAKE":
            cells.setdefault((c["asset"], c["phase_dec"]), []).append(c["cid"])
    return cells


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--index", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--arm", default="CORE+SIDE", choices=list(ARMS))
    p.add_argument("--quiet", action="store_true")
    a = p.parse_args()
    with open(a.index) as fh:
        lines = [ln for ln in fh if not ln.startswith("#")]
    rows = list(csv.DictReader(lines, delimiter="\t"))
    out, state = call_day(rows, arm=a.arm)
    cols = (["cid", "call", "conf", "n_terms"] + list(TERMS)
            + ["side_gate", "sigma_to_exit", "event_in_session", "asset",
               "phase_dec", "clock", "sec", "side", "cls", "primary",
               "against"])
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter="\t",
                           extrasaction="ignore")
        w.writeheader()
        for o in out:
            w.writerow(o)
    n_take = sum(1 for o in out if o["call"] == "TAKE")
    print("e1d5_policy [%s]: %d rows, %d TAKE, %d SKIP -> %s"
          % (a.arm, len(out), n_take, len(out) - n_take, a.out))
    for ln in side_state_log(state):
        print("   SIDE-STATE  %s" % ln)
    for cell, cids in sorted(seat_cells(out).items()):
        print("   SEAT CELL %-12s %3d takes, first = %s"
              % ("/".join(cell), len(cids), cids[0]))
    if not a.quiet:
        for o in out:
            if o["call"] == "TAKE":
                print("   TAKE %-28s %s %s" % (o["cid"], o["clock"], o["conf"]))


if __name__ == "__main__":
    sys.exit(main())
