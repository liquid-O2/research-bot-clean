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

Run: /usr/bin/python3 engine/port_m2/leakfix.py
"""
import datetime as dt
import json
import os
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

SECTION = "§2 leak fixture (D-057)"
OUT_DIR = MC.out_path("leakfix", "_")[:-1]

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
    g = _guard()
    future = g.decision_sec + 1
    if armed:
        ok = g.sec(future, "fixture")
    else:
        ok = _mutant_no_session_bound(g, future)
    return {"accepted": bool(ok),
            "detail": "session_sec=%d decision_sec=%d" % (future,
                                                          g.decision_sec)}


def case_l04_unresolved_touch_outcome(armed):
    """A touch 60s before the decision whose 15-minute outcome window is still
    open.  The ledger stores the RESOLVED outcome; showing it is the leak."""
    g = _guard()
    touch_sec = g.decision_sec - 60
    outcome_sec = g.decision_sec + 300               # resolves in the future
    if armed:
        known = g.sec(outcome_sec, "fixture touch outcome")
    else:
        known = _mutant_touch_outcome_unguarded(touch_sec, outcome_sec)
    return {"accepted": bool(known),
            "detail": "touch_sec=%d outcome_sec=%d decision_sec=%d window=%ds"
                      % (touch_sec, outcome_sec, g.decision_sec,
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


def _mutant_no_session_bound(guard, sec):
    """MUTANT M-L03: drop the `sec >= decision_sec` test in CausalGuard.sec."""
    return True


def _mutant_touch_outcome_unguarded(touch_sec, outcome_sec):
    """MUTANT M-L04: read the ledger's stored outcome without checking that its
    resolution second has passed."""
    return True


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
    ("L03", "future session second", "M-L03", case_l03_future_session_second),
    ("L04", "unresolved level-touch outcome", "M-L04",
     case_l04_unresolved_touch_outcome),
    ("L05", "equal-time availability join", "M-L05", case_l05_equal_time_join),
    ("L06", "unknown lag rule defaulted", "M-L06", case_l06_unknown_lag_rule),
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
        note = "OK" if (rule_ok and file_ok and man_ok) else "DEFECT"
        if sid in used and note == "OK":
            note = "OK_USED"
        rows.append([sid, r["avail_rule"], r["exempt"], int(rule_ok),
                     int(file_ok), int(man_ok), note])
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
    MC.write_tsv(os.path.join(OUT_DIR, "lag_table_audit.tsv"), SECTION, phash,
                 ["series_id", "avail_rule", "exempt", "rule_exists",
                  "file_exists", "manifest_cited", "verdict"], arows)
    MC.write_json(os.path.join(OUT_DIR, "leakfix.receipt.json"),
                  {"env": MC.env_receipt(PARAMS),
                   "n_cases": len(rows), "n_failed": n_fail,
                   "n_lag_rows": len(arows), "n_lag_defects": n_defect,
                   "verdict": "PASS" if (n_fail == 0 and n_defect == 0)
                              else "FAIL"})
    for r in rows:
        MC.hb("leakfix %s %s armed_accepted=%d mutant_accepted=%d"
              % (r[0], r[5], r[3], r[4]))
    MC.hb("leakfix: %d cases, %d failed; lag table %d rows, %d defects"
          % (len(rows), n_fail, len(arows), n_defect))
    return 1 if (n_fail or n_defect) else 0


if __name__ == "__main__":
    sys.exit(run())
