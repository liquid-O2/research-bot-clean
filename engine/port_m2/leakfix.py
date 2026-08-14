#!/usr/bin/python3
"""PORT M2 — the D-057 RED-FIRST LEAK FIXTURE (spec §2).

Spec §2, verbatim: "a fixture sheet with a deliberately future-joined COT row
and a same-day-later US close MUST be refused by the guard; mutants committed."

RED-FIRST means the fixture is only evidence if the guard would have PASSED the
poison without the rule.  Each case therefore runs twice:

    ARMED    the production guard is in place  -> the poison MUST be refused
    MUTANT   one named line of the rule is neutralised -> the poison MUST be
             ACCEPTED, proving the test actually exercises that line

A mutant that still refuses is a DEAD test and fails the fixture just as loudly
as an armed case that accepts.  Both directions are asserted, both are
reported, and the mutant table is committed to git as the red ledger.

The two named poisons plus the leaks the port's own receipts make reachable:

  L01 FUTURE COT ROW      a COT report stamped BEFORE the decision but
                          PUBLISHED after it (Tuesday stamp, Friday release) —
                          the exact D-057 example.
  L02 SAME-DAY-LATER US   a US daily close stamped on the decision's own date,
      CLOSE               struck at 16:15 ET, read by a Tokyo-phase decision
                          that happens hours EARLIER in wall-clock time.
  L03 FUTURE SESSION SEC  a session-clock read after the decision second.
  L04 UNRESOLVED TOUCH    a level touch whose 15-minute outcome window has not
      OUTCOME             closed by the decision second (the ledger stores the
                          RESOLVED outcome, so reading it naively is a leak).
  L05 EQUAL-TIME JOIN     an observation whose availability_ts EQUALS
                          decision_ts (D-057: "never equal-time").
  L06 UNKNOWN LAG RULE    a series with no AVAILABILITY_LAGS.tsv rule must be
                          refused, never silently defaulted.
  L07 REVISED VINTAGE     a revisable series' banked file holds the LATEST
      (R14)               vintage of every observation, so a decision that
                          joins it under a FIRST-PRINT availability rule reads
                          a value that was corrected weeks later.  D-057 is
                          satisfied in form and violated in substance.
  L08 FORECASTER JOIN     the CC-M2-14.2a leading-regime join must take the
      (R42)               newest anchor STRICTLY BEFORE the decision; an
                          anchor stamped AT the decision second is a
                          same-second read.
  L09 LEVEL BIRTH         a level whose SOURCE does not exist yet at the
      (R42/R93)           decision second must not be on the sheet.  The
                          fvol families (FVOL_BAND / FVOL_LADDER /
                          FVOL_LADDER_RS) are anchored at a phase's OPENING
                          MID, so a TOKYO decision was shown LONDON- and
                          NY-anchored bands built from prices hours in its
                          own future.

THE FIX PASS (M2_CONSOLIDATED_REVIEW R40/R41/R42/R14/R43) changed three things
about this fixture, all of which were the reason five upstream defects survived
a passing §2 gate:

  * R41 TWO MUTANTS WERE `return True` STUBS.  M-L03 and M-L04 neutralised
    NOTHING — they were constants that can never fail, so L03/L04 reported PASS
    regardless of the production code's state, and their armed halves called
    `MC.CausalGuard.sec` directly rather than exercising the renderer that
    consumes it.  Both now MONKEYPATCH the real `MC.CausalGuard.sec` (M-L04
    only its S4 touch-OUTCOME branch) and both halves render S4 on a live case,
    exactly as MT22 does for level birth in test_m2.
  * R42 TWO OF THE PROGRAM'S THREE REGISTERED LEAK CLASSES WERE NOT IN THE
    FIXTURE.  CC-M2-7.2 declared LEVEL-BIRTH CAUSALITY "a named fixture class
    alongside availability joins" and the case lived in test_m2 (MT22), not
    here; the CC-M2-14.2a strictly-prior forecaster join had its mutant in
    test_m2 t16 and no fixture case at all.  L08 and L09 are those classes,
    in the artefact spec §2 actually gates reader rounds on.
  * R40 THE LAG-TABLE AUDIT VALIDATED RULE NAMES, NEVER LAG VALUES.  A series
    whose rule is WRONG (too short) passed the audit clean — the D24
    un-censused-constant class applied to the availability layer, and the
    structural reason R79-R86 survived.  `lag_value_audit` now checks every
    rule's COMPUTED availability against the publication instant the row's own
    `publication_fact` prose CLAIMS, over the series' real stamp dates.

Run: /usr/bin/python3 engine/port_m2/leakfix.py
"""
import csv
import datetime as dt
import json
import os
import re
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import availability as AV                 # noqa: E402
import context as CTX                     # noqa: E402
import sections as SEC                    # noqa: E402
import b3_levels as B3                    # noqa: E402
import assemble as A                      # noqa: E402
import triage_index as TI                 # noqa: E402

SECTION = "§2 leak fixture (D-057)"
OUT_DIR = MC.out_path("leakfix", "_")[:-1]

# The live case the renderer-driven cases (L03/L04/L09) run on.  P-M2c's own
# warm-up fixture: it decides in TOKYO at 03:25:12 while the session's level
# ledger already holds this session's LONDON and NY opening ranges AND its
# LONDON/NY-anchored fvol bands, and its touch table is dominated by touches
# that happen hours after the decision.  Every poison below is therefore REAL
# session data, not a hand-built row.
FIXTURE_CID = "SI-20210701-012312-S"
_CASE = {}


def _case():
    """The fixture case, rebuilt per call site but memoised per process.

    `assemble.load_levels` returns a FRESH dict per Case, so a case may be
    mutated to inject a poison without contaminating any other reader.
    """
    if "case" not in _CASE:
        _CASE["case"] = A.Case(FIXTURE_CID, want_events=False)
    return _CASE["case"]


def _null_put(*_a, **_k):
    return None


_null_put.refuse = lambda *_a, **_k: None


def _s4(case):
    """Render S4 and return (text, n_touches, n_pending, n_not_yet_born)."""
    txt = "\n".join(SEC.s4_levels(case, _null_put))
    got = {}
    for k in ("n_touches", "n_pending", "n_not_yet_born"):
        m = re.search(r"%s=(\d+)" % k, txt)
        if m is None:
            raise RuntimeError("S4 header lost %s — the fixture cannot read "
                               "the renderer's own causal counts" % k)
        got[k] = int(m.group(1))
    return txt, got["n_touches"], got["n_pending"], got["n_not_yet_born"]

PARAMS = {
    "spec_section": SECTION,
    "law": "D-057 availability-time join; strict availability_ts < decision_ts",
    "lag_table": "artifacts/reference/port_context/AVAILABILITY_LAGS.tsv",
    "mode": "red-first: every case runs ARMED (must refuse) and MUTANT (must "
            "accept); a mutant that still refuses is a dead test and fails",
}

# A fixed, spec-shaped decision moment: a TOKYO-phase decision (02:00 UTC), so
# the same calendar day's US close is genuinely in the future.
FIXTURE_DECISION = dt.datetime(2022, 6, 15, 2, 0, 0,
                               tzinfo=dt.timezone.utc)


def _guard(ts=None):
    ts = int((ts or FIXTURE_DECISION).timestamp())
    return MC.CausalGuard(ts, 40000, FIXTURE_DECISION.date())


# ------------------------------------------------------------------ cases --
def case_l01_future_cot(armed):
    """A Tuesday-stamped COT report published the FOLLOWING Friday, read by a
    Wednesday decision.  Stamp < decision; availability > decision."""
    g = _guard()
    stamp = dt.date(2022, 6, 14)                     # the Tuesday before
    assert stamp < FIXTURE_DECISION.date()
    avail = AV.availability_ts("COT_FRI_1530ET", stamp)
    ser = AV.AvailSeries("FIXTURE_COT", "COT_FRI_1530ET",
                         [(stamp, avail, (12345.0,))], source="fixture")
    if armed:
        got = ser.latest(g)
    else:
        got = _mutant_naive_stamp_join(ser, g)       # MUTANT: join on the stamp
    return {"accepted": got is not None,
            "detail": "stamp=%s availability=%s decision=%s"
                      % (stamp, MC.futc(avail), MC.futc(g.decision_ts))}


def case_l02_same_day_us_close(armed):
    """A US daily close stamped on the decision's own date (struck 16:15 ET,
    i.e. 20:15 UTC) read by a 02:00 UTC Tokyo-phase decision."""
    g = _guard()
    stamp = FIXTURE_DECISION.date()
    avail = AV.availability_ts("NEXT_US_BD", stamp)
    ser = AV.AvailSeries("FIXTURE_US_CLOSE", "NEXT_US_BD",
                         [(stamp, avail, (99.0,))], source="fixture")
    if armed:
        got = ser.latest(g)
    else:
        got = _mutant_naive_stamp_join(ser, g)
    return {"accepted": got is not None,
            "detail": "stamp=%s availability=%s decision=%s"
                      % (stamp, MC.futc(avail), MC.futc(g.decision_ts))}


def case_l03_future_session_second(armed):
    """The session's OWN LATER TOUCHES, read through the S4 renderer.

    R41: the V1 case called `CausalGuard.sec` directly and its mutant was
    `return True` — a constant that neutralised nothing and could never fail.
    The poison here is real data: the fixture session's level ledger stores 270
    touches and all but a handful happen AFTER the decision second, so a guard
    that does not bound the session clock counts the whole day's touch history
    into a sheet rendered at 03:25.  The armed half renders S4 and reads the
    renderer's own `n_touches=` count; the mutant monkeypatches the real
    `MC.CausalGuard.sec`, dropping its `sec >= decision_sec` test.
    """
    case = _case()
    t = case.levels["touches"]
    dec = case.dec_sec
    n_past = int(np.sum(t[:, 0] < dec)) if t.size else 0
    n_future = int(np.sum(t[:, 0] >= dec)) if t.size else 0
    if not n_future:
        raise RuntimeError("FIXTURE VACUOUS: %s has no touch at or after its "
                           "decision second, so L03 tests nothing"
                           % FIXTURE_CID)
    if armed:
        _txt, n_touch, _p, _b = _s4(case)
    else:
        with _mutant_no_session_bound():
            _txt, n_touch, _p, _b = _s4(case)
    return {"accepted": bool(n_touch > n_past),
            "detail": "S4 n_touches=%d (causal=%d, later=%d) decision_sec=%d"
                      % (n_touch, n_past, n_future, dec)}


def case_l04_unresolved_touch_outcome(armed):
    """A touch before the decision whose 15-minute outcome window is STILL OPEN.

    The ledger stores the RESOLVED outcome (b3_levels resolves inside a forward
    REJECT_WINDOW), so reading it naively hands the sheet the answer to a
    question the market has not yet answered.  The poison is injected into a
    COPY of the fixture session's touch table and rendered through S4; the
    armed half must count it as PENDING, and the mutant — which monkeypatches
    the S4 touch-OUTCOME branch of the real `MC.CausalGuard.sec` — must show it
    as resolved (`n_pending` back to zero).
    """
    case = _case()
    dec = case.dec_sec
    touch_sec = dec - 60
    outcome_sec = dec + 300                          # resolves in the future
    base = case.levels["touches"]
    poison = np.array(base[0], dtype=np.float64, copy=True)
    poison[0] = touch_sec                            # touch: strictly prior
    poison[1] = 0.0                                  # level row 0
    poison[5] = float(B3.OUTCOME_REJECT)             # a RESOLVED outcome ...
    poison[6] = float(outcome_sec)                   # ... resolved in the future
    spiked = np.vstack([poison[None, :], base])
    spiked = spiked[np.argsort(spiked[:, 0], kind="stable")]
    saved = case.levels
    case.levels = dict(saved)
    case.levels["touches"] = spiked
    try:
        if armed:
            _txt, _n, n_pending, _b = _s4(case)
        else:
            with _mutant_touch_outcome_unguarded():
                _txt, _n, n_pending, _b = _s4(case)
    finally:
        case.levels = saved
    return {"accepted": bool(n_pending == 0),
            "detail": "S4 n_pending=%d touch_sec=%d outcome_sec=%d "
                      "decision_sec=%d window=%ds"
                      % (n_pending, touch_sec, outcome_sec, dec,
                         B3.REJECT_WINDOW)}


def case_l05_equal_time_join(armed):
    """availability_ts EXACTLY equal to decision_ts.  D-057: never equal-time."""
    g = _guard()
    stamp = dt.date(2022, 6, 14)
    ser = AV.AvailSeries("FIXTURE_EQUAL", "NEXT_US_BD",
                         [(stamp, g.decision_ts, (1.0,))], source="fixture")
    if armed:
        got = ser.latest(g)
    else:
        got = _mutant_non_strict_join(ser, g)
    return {"accepted": got is not None,
            "detail": "availability_ts == decision_ts == %d" % g.decision_ts}


def case_l06_unknown_lag_rule(armed):
    """A series with no lag-table rule must be refused, never defaulted."""
    try:
        if armed:
            AV.availability_ts("NO_SUCH_RULE", dt.date(2022, 6, 14))
        else:
            _mutant_default_rule("NO_SUCH_RULE", dt.date(2022, 6, 14))
        accepted = True
    except MC.LeakRefusal:
        accepted = False
    return {"accepted": accepted, "detail": "avail_rule='NO_SUCH_RULE'"}


# ------------------------------------------- L07 VINTAGE / point-in-time (R14)
# The lag table's `publication_fact` column documents FIRST-PRINT timing only,
# while the banked files hold the LATEST vintage of every series.  A decision on
# 2021-10-20 therefore joins the 2026-vintage value of a 2021-10-19 observation
# under a first-print rule: `availability_ts < decision_ts` holds and the value
# was still not knowable.  Affected on the record: COT_DISAGG_* and
# COT_TFF_NIKKEI (the CFTC publishes revisions), FRED_DTWEXBGS and FRED_T10YIE
# (H.10 and TIPS-derived series are revised), SLV_FLOW_OZ (NAV/share
# restatements), SHFE_INV_* (mirror corrections).  The LAW the fixture pins:
# THE AVAILABILITY OF A VALUE IS THE PUBLICATION OF THE VINTAGE YOU HOLD, not
# the first print of the observation it revises.
REVISABLE_SERIES = ("COT_DISAGG_SILVER", "COT_DISAGG_COPPER",
                    "COT_TFF_NIKKEI", "FRED_DTWEXBGS", "FRED_T10YIE",
                    "FRED_DGS10", "FRED_DFII10", "SLV_FLOW_OZ",
                    "SHFE_INV_SILVER", "SHFE_INV_COPPER")
VINTAGE_DECLARED_TOKENS = ("REVISED-VALUE", "vintage", "VINTAGE",
                           "point-in-time")


def case_l07_revised_vintage(armed):
    """A COT report whose FIRST PRINT is available and whose HELD VALUE is a
    later revision published AFTER the decision."""
    g = _guard()
    stamp = dt.date(2022, 6, 7)                      # a Tuesday report date
    first_print = AV.availability_ts("COT_FRI_1530ET", stamp)
    # the CFTC's correction to that week's report, published the week AFTER the
    # fixture decision — and it is the corrected number the banked file holds.
    vintage_ts = int(dt.datetime(2022, 6, 24, 19, 30,
                                 tzinfo=dt.timezone.utc).timestamp())
    assert first_print < g.decision_ts < vintage_ts
    if armed:
        # the availability of the VALUE HELD is its own vintage's publication
        ok = g.avail(vintage_ts, "S12 COT (vintage of the held value)")
    else:
        ok = _mutant_first_print_join(g, first_print, vintage_ts)
    return {"accepted": bool(ok),
            "detail": "stamp=%s first_print=%s vintage=%s decision=%s"
                      % (stamp, MC.futc(first_print), MC.futc(vintage_ts),
                         MC.futc(g.decision_ts))}


def case_l08_forecaster_same_second(armed):
    """CC-M2-14.2a: the leading-regime join takes the newest anchor STRICTLY
    BEFORE the decision.  An anchor stamped AT the decision second is a
    same-second read of a forecast that was cut on that second's own state."""
    g = _guard()
    d8 = "20220615"
    prior = g.decision_ts - 600
    vals = {"predicted_day_type_prob": 0.5, "range_hat_vs_trailing": 1.0,
            "menu_hat": 1.0}
    TI._FCAST["FIXTURE_ASSET"] = {
        d8: [(prior, "PRIOR", dict(vals)),
             (g.decision_ts, "SAME_SECOND", dict(vals))]}
    try:
        if armed:
            hit = TI.regime_at("FIXTURE_ASSET", d8, g.decision_ts)
        else:
            hit = _mutant_same_second_anchor("FIXTURE_ASSET", d8,
                                             g.decision_ts)
    finally:
        TI._FCAST.pop("FIXTURE_ASSET", None)
    joined = None if hit is None else int(hit[0])
    return {"accepted": bool(joined is not None and joined >= g.decision_ts),
            "detail": "joined_anchor=%s (%s) prior=%d decision_ts=%d"
                      % (None if hit is None else hit[1], joined, prior,
                         g.decision_ts)}


def case_l09_unborn_fvol_level(armed):
    """R93/CC-M2-7.2: an FVOL band anchored at a LATER phase's opening mid.

    `_level_birth_sec` handled OR_EXT and the dynamic families and fell through
    to `return 0` for everything else, so FVOL_BAND / FVOL_LADDER /
    FVOL_LADDER_RS levels anchored at `OPEN_LONDON` / `OPEN_NY` printed as live
    rows on a TOKYO decision — same-session forward prices, sitting at the
    money, in a table S4 sorts by proximity to mid.  Measured before the fix:
    1,998 of 12,418 E1 BLIND sheets (16.1%), 6,892 rows.
    """
    case = _case()
    z = case.levels
    fam, lid, lpx = z["level_family"], z["level_id"], z["level_price"]
    band = 1.5 * case.atr / case.mult
    # the TRUE unborn set, taken from the production rule BEFORE any patch
    unborn_all, unborn_fvol = 0, []
    for r in range(int(lpx.size)):
        if not (np.isfinite(lpx[r])
                and abs(float(lpx[r]) - case.entry_mid) <= band):
            continue
        b = SEC._level_birth_sec(case, str(fam[r]), str(lid[r]),
                                 int(z["dynamic"][r]))
        if b < 0 or b >= case.dec_sec:
            unborn_all += 1
            if str(fam[r]).startswith("FVOL"):
                unborn_fvol.append(str(lid[r]))
    if not unborn_fvol:
        raise RuntimeError("FIXTURE VACUOUS: %s has no in-band fvol level "
                           "anchored after its decision second" % FIXTURE_CID)
    if armed:
        _txt, _n, _p, n_born_out = _s4(case)
    else:
        with _mutant_fvol_birth_zero():
            _txt, _n, _p, n_born_out = _s4(case)
    # S4 prints `n_not_yet_born` — the in-band levels it refused to show.  Fewer
    # than actually exist means the renderer blessed a level that does not exist
    # yet as live, which is the poison whatever the sort order then does with it.
    return {"accepted": bool(n_born_out < unborn_all),
            "detail": "S4 n_not_yet_born=%d, truly unborn in band=%d of which "
                      "fvol-anchored=%d (%s) decision_sec=%d"
                      % (n_born_out, unborn_all, len(unborn_fvol),
                         unborn_fvol[0], case.dec_sec)}


# ----------------------------------------------------------- the mutants ---
# Each mutant neutralises ONE named line of the production rule.  They live
# here, committed, so the red ledger is auditable — they are never importable
# into the builder.
def _mutant_naive_stamp_join(ser, guard):
    """MUTANT M-L01/M-L02: join on the STAMP DATE instead of availability_ts —
    the pre-D-057 behaviour."""
    d = dt.datetime.utcfromtimestamp(guard.decision_ts).date()
    for i in range(len(ser.stamps) - 1, -1, -1):
        if ser.stamps[i] <= d:
            return {"stamp_date": ser.stamps[i],
                    "availability_ts": ser.avail[i],
                    "values": ser.values[i], "series_id": ser.series_id,
                    "source": ser.source}
    return None


class _patch_guard_sec(object):
    """Context manager: replace the REAL `MC.CausalGuard.sec` for one render.

    R41.  A mutant that is a `return True` stub neutralises nothing and can
    never fail — it is a dead test wearing a red ledger's clothes.  These
    mutants monkeypatch the production method itself, so the armed half's
    renderer (`sections.s4_levels`) is what changes behaviour, exactly as
    test_m2's MT22 does for level birth.
    """

    def __init__(self, replacement):
        self.replacement = replacement
        self.original = None

    def __enter__(self):
        self.original = MC.CausalGuard.sec
        MC.CausalGuard.sec = self.replacement
        return self

    def __exit__(self, *_exc):
        MC.CausalGuard.sec = self.original
        return False


def _mutant_no_session_bound():
    """MUTANT M-L03: drop the `sec >= decision_sec` test in CausalGuard.sec —
    the whole session clock becomes readable from any decision second."""
    def sec(self, sec, what):              # noqa: A002 — mirrors the signature
        self.checks += 1
        return sec is not None
    return _patch_guard_sec(sec)


def _mutant_touch_outcome_unguarded():
    """MUTANT M-L04: neutralise the S4 touch-OUTCOME branch only — the stored
    resolution is read without checking that its resolution second has passed,
    while every other session-clock read stays guarded."""
    original = MC.CausalGuard.sec

    def sec(self, sec, what):              # noqa: A002 — mirrors the signature
        if "touch outcome" in str(what):
            self.checks += 1
            return True
        return original(self, sec, what)
    return _patch_guard_sec(sec)


class _patch_level_birth(object):
    """MUTANT M-L09 machinery: restore the pre-R93 fall-through."""

    def __init__(self, replacement):
        self.replacement = replacement
        self.original = None

    def __enter__(self):
        self.original = SEC._level_birth_sec
        SEC._level_birth_sec = self.replacement
        return self

    def __exit__(self, *_exc):
        SEC._level_birth_sec = self.original
        return False


def _mutant_fvol_birth_zero():
    """MUTANT M-L09: restore `_level_birth_sec`'s `return 0` fall-through for
    the STATIC fvol families — the exact V1.1 line R93 names."""
    original = SEC._level_birth_sec

    def birth(case, fam, lid, dyn):
        if fam in ("FVOL_BAND", "FVOL_LADDER", "FVOL_LADDER_RS"):
            return 0
        return original(case, fam, lid, dyn)
    return _patch_level_birth(birth)


def _mutant_first_print_join(guard, first_print_ts, _vintage_ts):
    """MUTANT M-L07: join a revisable series on the FIRST PRINT of the
    observation instead of on the publication of the vintage actually held."""
    return guard.avail(first_print_ts, "S12 COT (first print)")


def _mutant_same_second_anchor(asset, date8, dec_ts):
    """MUTANT M-L08: `<=` instead of `<` in the CC-M2-14.2a forecaster join."""
    rows = TI.forecast_rows(asset).get(str(date8), [])
    best = None
    for ats, anchor, vals in rows:
        if ats <= dec_ts:
            best = (ats, anchor, vals)
        else:
            break
    return best


def _mutant_non_strict_join(ser, guard):
    """MUTANT M-L05: use `<=` instead of `<` in the availability cut."""
    import bisect
    i = bisect.bisect_right(ser.avail, guard.decision_ts) - 1
    if i < 0:
        return None
    return {"stamp_date": ser.stamps[i], "availability_ts": ser.avail[i],
            "values": ser.values[i], "series_id": ser.series_id,
            "source": ser.source}


def _mutant_default_rule(rule, stamp):
    """MUTANT M-L06: silently default an unknown rule to NEXT_US_BD."""
    return AV.rule_next_us_bd(stamp)


CASES = (
    ("L01", "future-joined COT row (spec §2 named poison)", "M-L01",
     case_l01_future_cot),
    ("L02", "same-day-later US close (spec §2 named poison)", "M-L02",
     case_l02_same_day_us_close),
    ("L03", "future session second, through the S4 renderer", "M-L03",
     case_l03_future_session_second),
    ("L04", "unresolved level-touch outcome, through the S4 renderer", "M-L04",
     case_l04_unresolved_touch_outcome),
    ("L05", "equal-time availability join", "M-L05", case_l05_equal_time_join),
    ("L06", "unknown lag rule defaulted", "M-L06", case_l06_unknown_lag_rule),
    ("L07", "revised VINTAGE joined on its first print (R14)", "M-L07",
     case_l07_revised_vintage),
    ("L08", "same-second forecaster anchor (CC-M2-14.2a)", "M-L08",
     case_l08_forecaster_same_second),
    ("L09", "unborn fvol-anchored level on the sheet (R93)", "M-L09",
     case_l09_unborn_fvol_level),
)


# --------------------------------------------------------- lag-table audit --
def audit_lag_table():
    """Every S12 series the builder can render must have a lag-table row whose
    rule exists, whose file exists, and whose manifest citation exists."""
    rows = []
    tab = AV.lag_table_index()
    used = set()
    for a in MC.ASSET_ORDER:
        used |= set(CTX.ASSET_SERIES[a])
    used |= {"CAL_BLS", "CAL_FOMC"}
    for sid in sorted(set(list(tab) + list(used))):
        r = tab.get(sid)
        if r is None:
            rows.append([sid, "", "", 0, 0, 0, "NO_LAG_TABLE_ROW"])
            continue
        rule_ok = r["avail_rule"] in AV.RULES
        f = r["file"].replace("YYYY", "2022")
        pieces = [p.strip() for p in f.split("+")]
        file_ok = all(os.path.exists(os.path.join(AV.REF_ROOT, p))
                      for p in pieces)
        msrc = r["manifest_source"].split(":")[0].split(" ")[0]
        man_ok = (os.path.exists(os.path.join(AV.REF_ROOT, msrc))
                  or os.path.exists(os.path.join("/workspace", msrc))
                  or msrc.startswith("D-057") or msrc.startswith("DATA_INVENTORY"))
        # R14: a revisable series must DECLARE its vintage handling somewhere
        # in the row, or the sheet shows a corrected number as if it had been
        # knowable.  Reported (and counted) here; the declaration itself lives
        # in the lag table and in S12, which this fixture does not own.
        vint = ("EXEMPT" if sid not in REVISABLE_SERIES else
                ("DECLARED" if any(t in (r.get("caveat") or "")
                                   + (r.get("publication_fact") or "")
                                   for t in VINTAGE_DECLARED_TOKENS)
                 else "UNDECLARED"))
        note = "OK" if (rule_ok and file_ok and man_ok) else "DEFECT"
        if sid in used and note == "OK":
            note = "OK_USED"
        rows.append([sid, r["avail_rule"], r["exempt"], int(rule_ok),
                     int(file_ok), int(man_ok), vint, note])
    return rows


# ---------------------------------------------------- R40 the LAG-VALUE audit
# `audit_lag_table` checks that the rule NAME exists, the file exists and a
# manifest is cited.  A series whose rule is WRONG — too short for the
# publication it claims — passes it clean, which is the D24 un-censused-constant
# class applied to the availability layer and the structural reason a 21-row
# table carried five defects through a passing fixture (R79-R86).
#
# The check below is a CONSISTENCY test between two committed artefacts: the
# row's own `publication_fact` prose (what the table CLAIMS about when the datum
# exists) and the rule's COMPUTED availability_ts over the series' REAL stamp
# dates.  An availability earlier than the claimed publication instant is a lag
# that cannot be right.  Prose that carries no checkable claim is reported as
# UNCHECKABLE and counted — never silently blessed.
_TZ_TOKENS = (("ET", AV.NY), ("EST", AV.NY), ("EDT", AV.NY),
              ("JST", AV.TOKYO), ("CST", AV.SHANGHAI))
_WEEKDAYS = (("Monday", 0), ("Tuesday", 1), ("Wednesday", 2),
             ("Thursday", 3), ("Friday", 4))
LAG_SAMPLE_MAX = 120                      # deterministic stride over the stamps


def _claim(prose):
    """The publication instant the row's own prose CLAIMS, as a spec:
    (weekday | None, hh, mm, tz, next_bd) — or None when nothing is claimed."""
    tz = None
    for tok, zone in _TZ_TOKENS:
        if re.search(r"\b%s\b" % tok, prose):
            tz = zone
            break
    wd = None
    for name, idx in _WEEKDAYS:
        if re.search(r"\b%s\b" % name, prose):
            wd = idx
            break
    m = re.search(r"\b(\d{1,2}):(\d{2})\b", prose)
    hh, mm = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    nxt = bool(re.search(r"next[\s-]business[\s-]day|next\s+\S+\s+"
                         r"(?:business\s+day|afternoon)|next\s+business",
                         prose, re.I))
    if tz is None or (wd is None and hh is None and not nxt):
        return None
    return {"weekday": wd, "hh": hh or 0, "mm": mm or 0, "tz": tz, "next": nxt}


def _claim_ts(claim, stamp):
    """The claimed earliest publication instant for one stamp date."""
    d = stamp
    if claim["weekday"] is not None:
        while d.weekday() != claim["weekday"]:
            d += dt.timedelta(days=1)
    elif claim["next"]:
        if claim["tz"] is AV.TOKYO:
            d = AV._next_bd(AV.jst_business_days(), d) or (d
                                                           + dt.timedelta(1))
        elif claim["tz"] is AV.SHANGHAI:
            d = AV._next_weekday(d)
        else:
            d = AV._next_bd(AV.us_business_days(), d) or (d + dt.timedelta(1))
    return AV._epoch(d, claim["tz"], claim["hh"], claim["mm"])


def _stamp_dates(row):
    """The series' REAL stamp dates, deterministically subsampled."""
    out = []
    for part in [p.strip() for p in row["file"].replace("YYYY", "2022")
                 .split("+")]:
        p = os.path.join(AV.REF_ROOT, part)
        if not os.path.exists(p):
            continue
        try:
            with open(p, newline="", errors="strict") as fh:
                for rec in csv.DictReader(fh):
                    v = (rec.get(row["date_column"]) or "").strip()
                    if re.match(r"^\d{4}-\d{2}-\d{2}$", v):
                        out.append(dt.date.fromisoformat(v))
        except (OSError, UnicodeDecodeError, csv.Error):
            return []
    out = sorted(set(out))
    if len(out) > LAG_SAMPLE_MAX:
        step = len(out) // LAG_SAMPLE_MAX + 1
        out = out[::step]
    return out


def lag_value_audit():
    """Per series: does the rule's COMPUTED availability cover the publication
    its own row CLAIMS, on the series' own stamp dates?"""
    rows = []
    tab = AV.lag_table_index()
    for sid in sorted(tab):
        r = tab[sid]
        rule = r["avail_rule"]
        if str(r.get("exempt")) == "1" or rule not in AV.RULES \
                or AV.RULES.get(rule) is None:
            rows.append([sid, rule, "-", 0, 0, 0, "EXEMPT_OR_NO_RULE"])
            continue
        claim = _claim(r.get("publication_fact") or "")
        stamps = _stamp_dates(r)
        if claim is None:
            rows.append([sid, rule, "no machine-checkable publication claim",
                         len(stamps), 0, 0, "UNCHECKABLE_PROSE"])
            continue
        if not stamps:
            rows.append([sid, rule, "no readable stamp column", 0, 0, 0,
                         "UNCHECKABLE_STAMPS"])
            continue
        n_early = 0
        worst = 0
        for s in stamps:
            avail = AV.availability_ts(rule, s)
            want = _claim_ts(claim, s)
            if avail is None or want is None:
                continue
            if avail < want:
                n_early += 1
                worst = max(worst, want - avail)
        desc = "%s%02d:%02d %s%s" % (
            ("" if claim["weekday"] is None
             else _WEEKDAYS[claim["weekday"]][0] + " "),
            claim["hh"], claim["mm"], str(claim["tz"]),
            " next_bd" if claim["next"] else "")
        rows.append([sid, rule, desc, len(stamps), n_early, worst,
                     "OK" if n_early == 0 else "LAG_TOO_SHORT"])
    return rows


def run():
    MC.verify_spec()
    phash = MC.params_hash(PARAMS)
    rows = []
    n_fail = 0
    for cid, name, mut, fn in CASES:
        armed = fn(True)
        mutant = fn(False)
        armed_ok = (armed["accepted"] is False)          # ARMED must refuse
        mutant_ok = (mutant["accepted"] is True)         # MUTANT must accept
        verdict = "PASS" if (armed_ok and mutant_ok) else (
            "FAIL_ARMED_ACCEPTED" if not armed_ok else "FAIL_DEAD_MUTANT")
        if verdict != "PASS":
            n_fail += 1
        rows.append([cid, name, mut, int(armed["accepted"]),
                     int(mutant["accepted"]), verdict, armed["detail"]])
    MC.write_tsv(os.path.join(OUT_DIR, "leak_fixture.tsv"), SECTION, phash,
                 ["case", "poison", "mutant", "armed_accepted",
                  "mutant_accepted", "verdict", "detail"], rows,
                 extra=["RED-FIRST: armed_accepted MUST be 0 and "
                        "mutant_accepted MUST be 1 on every row",
                        "decision moment = %s (Tokyo phase, so the same "
                        "calendar day's US close is genuinely future)"
                        % MC.futc(int(FIXTURE_DECISION.timestamp()))])
    arows = audit_lag_table()
    n_defect = sum(1 for r in arows if r[-1] == "DEFECT" or
                   r[-1] == "NO_LAG_TABLE_ROW")
    n_vintage = sum(1 for r in arows if r[-2] == "UNDECLARED")
    MC.write_tsv(os.path.join(OUT_DIR, "lag_table_audit.tsv"), SECTION, phash,
                 ["series_id", "avail_rule", "exempt", "rule_exists",
                  "file_exists", "manifest_cited", "vintage_declared",
                  "verdict"], arows,
                 extra=["vintage_declared: R14 — a REVISABLE series whose row "
                        "declares no vintage/point-in-time fact is UNDECLARED; "
                        "the banked file holds the LATEST vintage while the "
                        "rule times the FIRST PRINT"])
    vrows = lag_value_audit()
    n_short = sum(1 for r in vrows if r[-1] == "LAG_TOO_SHORT")
    n_unchecked = sum(1 for r in vrows if str(r[-1]).startswith("UNCHECKABLE"))
    MC.write_tsv(os.path.join(OUT_DIR, "lag_value_audit.tsv"), SECTION, phash,
                 ["series_id", "avail_rule", "claimed_publication",
                  "n_stamps", "n_availability_before_claim",
                  "worst_shortfall_sec", "verdict"], vrows,
                 extra=["R40 — the NAME audit beside it never checked a lag "
                        "VALUE.  Here every rule's COMPUTED availability_ts is "
                        "compared against the publication instant the row's "
                        "own publication_fact prose claims, over the series' "
                        "REAL stamp dates.",
                        "LAG_TOO_SHORT = the rule says the datum is available "
                        "BEFORE the row's own prose says it is published. The "
                        "fix is in AVAILABILITY_LAGS.tsv / availability.py, "
                        "not in this fixture."])
    MC.write_json(os.path.join(OUT_DIR, "leakfix.receipt.json"),
                  {"env": MC.env_receipt(PARAMS),
                   "n_cases": len(rows), "n_failed": n_fail,
                   "n_lag_rows": len(arows), "n_lag_defects": n_defect,
                   "n_vintage_undeclared": n_vintage,
                   "n_lag_value_rows": len(vrows),
                   "n_lag_value_too_short": n_short,
                   "n_lag_value_uncheckable": n_unchecked,
                   "lag_value_findings": [r[0] for r in vrows
                                          if r[-1] == "LAG_TOO_SHORT"],
                   "vintage_undeclared": [r[0] for r in arows
                                          if r[-2] == "UNDECLARED"],
                   "verdict": "PASS" if (n_fail == 0 and n_defect == 0)
                              else "FAIL",
                   "availability_layer_findings":
                       "n_lag_value_too_short and n_vintage_undeclared are "
                       "REPORTED, not folded into this fixture's exit code: "
                       "both are defects of AVAILABILITY_LAGS.tsv and "
                       "availability.py, which the §2 gate does not own, and "
                       "the gate must stay runnable while they are open "
                       "(R40/R14/R79-R86)."})
    for r in rows:
        MC.hb("leakfix %s %s armed_accepted=%d mutant_accepted=%d"
              % (r[0], r[5], r[3], r[4]))
    MC.hb("leakfix: %d cases, %d failed; lag table %d rows, %d defects"
          % (len(rows), n_fail, len(arows), n_defect))
    MC.hb("leakfix LAG VALUES (R40): %d series, %d LAG_TOO_SHORT %s, "
          "%d UNCHECKABLE; VINTAGE (R14): %d UNDECLARED %s"
          % (len(vrows), n_short,
             sorted(r[0] for r in vrows if r[-1] == "LAG_TOO_SHORT"),
             n_unchecked, n_vintage,
             sorted(r[0] for r in arows if r[-2] == "UNDECLARED")))
    return 1 if (n_fail or n_defect) else 0


if __name__ == "__main__":
    sys.exit(run())
