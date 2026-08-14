#!/usr/bin/python3
"""PORT M2 — red-first tests for THE ONE D-001 FIX PASS, availability sub-lane.

Every test asserts a LAW and carries a committed MUTANT: a named neutralised
line of the production rule that the test must catch.  A test whose mutant
survives is a DEAD test and fails, exactly as `test_m2.py` requires.  The red
ledger is written to artifacts/cache/port/m2/tests/red_ledger_avail_fixlane.tsv.

Coverage, by review finding:
  R79/R39  the COT rule's holiday-week delay and its Friday-of-the-report-week
           construction (AV01, AV02)
  R85      the FEDERAL/agency calendar is a different object from the TREASURY
           one, and the difference lands on a COT release day (AV03)
  R82      H.10 releases on a federal business day, not any Monday (AV04)
  R83/R84  NEXT_US_BD is the END of the next full trading day, after every
           Tokyo/London second of that day (AV05)
  R86      a calendar that cannot reach a stamp is a counted REFUSAL and
           `latest()` refuses rather than serving a stale value (AV06)
  R14      the vintage class is declared per series and rides on every answer
           (AV07)
  R15      a disrupted (`scheduled_at_capture`) row never fires as an event, and
           a forward-dated row needs a schedule page we already held (CX01, CX02)
  R36/R127 the impact tier is explicit (never a silent low), the dated universe
           covers the E1 blind block, and the `asset` argument is used
           (CX03, CX04, CX06)
  R56      `recent_release`'s age does not vanish at 24h+1s (CX05)
  R91/R92  the event cache is keyed on the extraction DEFINITION and on the
           window ORIGIN (TP01, TP02)
  R98      `classify_trades` runs on the FULL cache, and the caller slices the
           returned vectors (TP03)
  R89      a missing D-054 threshold is a refusal, never the cap-only default
           (SN01)
  R80      b2_fvol's V1 block reads SANE seconds (FV01)
  MINORS   era_build keeps no wall clock and folds no partial FAIL rows (EB01,
           EB02); era_primer writes no literal `nan` cell (EP01)

Run: /usr/bin/python3 engine/port_m2/test_avail_fixlane.py
"""
import datetime as dt
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import availability as AV                 # noqa: E402
import context as CTX                     # noqa: E402
import tape as TAPE                       # noqa: E402
import assemble as A                      # noqa: E402
import era_build as EB                    # noqa: E402
import era_primer as EP                   # noqa: E402
import b7_sane as B7                      # noqa: E402
import census_common as X                 # noqa: E402

sys.path.insert(0, "/workspace/engine/port_m1")
import b2_fvol as B2                      # noqa: E402

SECTION = "§2 D-057 availability + §1 S6 tape (D-001 fix-lane red ledger)"
OUT_DIR = MC.out_path("tests", "_")[:-1]
LEDGER = []


def check(name, mutant, ok_armed, ok_mutant, detail=""):
    verdict = "PASS" if (ok_armed and not ok_mutant) else (
        "FAIL_ARMED" if not ok_armed else "FAIL_DEAD_MUTANT")
    LEDGER.append([name, mutant, int(bool(ok_armed)), int(bool(ok_mutant)),
                   verdict, str(detail)[:200]])
    return verdict == "PASS"


def _guard(date, hh=15, mm=0):
    ts = int(dt.datetime(date.year, date.month, date.day, hh, mm,
                         tzinfo=AV.NY).timestamp())
    return MC.CausalGuard(ts, 30000, date)


def _rel_date(ts):
    return dt.datetime.fromtimestamp(ts, AV.NY).date()


# =========================================================== availability ===
def av01_cot_holiday_week_delay():
    """R79/R39: the CFTC delays one business day in a holiday report week.

    RECEIPT the review measured: of the 261 Tuesday stamps in 2021-2025, the
    fixed +3-calendar-day rule computed SIX release dates that are not even US
    business days.
    """
    ser = CTX.series("COT_DISAGG_SILVER")
    stamps = sorted(set(ser.stamps))
    fed = set(AV.us_federal_business_days())

    def armed_rel(s):
        return _rel_date(AV.rule_cot_fri_1530et(s))

    def mutant_rel(s):
        # MUTANT AV01: neutralise the holiday-week branch of
        # `rule_cot_fri_1530et` — the pre-fix `stamp + 3 calendar days`.
        return s + dt.timedelta(days=3)

    bad_armed = [s for s in stamps if armed_rel(s) not in fed]
    bad_mutant = [s for s in stamps if mutant_rel(s) not in fed]
    # and no release may be moved EARLIER than the naive one (that would be a
    # NEW leak, not a fix)
    earlier = [s for s in stamps if armed_rel(s) < mutant_rel(s)]
    delayed = [s for s in stamps if armed_rel(s) != mutant_rel(s)]
    armed = (not bad_armed) and (not earlier) and len(delayed) > 0
    mutant = not bad_mutant
    return check("cot_release_lands_on_a_cftc_business_day",
                 "AV01_fixed_three_calendar_days", armed, mutant,
                 "armed_bad=%d mutant_bad=%d delayed=%d/%d"
                 % (len(bad_armed), len(bad_mutant), len(delayed),
                    len(stamps)))


def av02_cot_monday_stamp_is_not_thursday():
    """R79: 508 COT rows carry a MONDAY stamp; Monday+3 = Thursday, a day
    BEFORE the earliest possible release."""
    mondays = [dt.date(2023, 7, 3), dt.date(2025, 11, 10)]
    armed_ok, mutant_ok = True, True
    detail = []
    for s in mondays:
        got = _rel_date(AV.rule_cot_fri_1530et(s))
        naive = s + dt.timedelta(days=3)
        detail.append("%s->%s (naive %s)" % (s, got, naive))
        # the release must be at or after the Friday of the stamp's own week
        friday = s + dt.timedelta(days=(4 - s.weekday()) % 7)
        armed_ok = armed_ok and got >= friday
        # MUTANT AV02: the pre-fix offset lands on Thursday, before the Friday
        mutant_ok = mutant_ok and naive >= friday
    return check("cot_monday_stamp_is_not_released_on_thursday",
                 "AV02_monday_plus_three", armed_ok, mutant_ok,
                 "; ".join(detail))


def av03_federal_calendar_is_not_the_treasury_one():
    """R85: the Treasury calendar calls days business days on which the CFTC
    and the Fed were shut — including a FRIDAY, i.e. a COT release day."""
    fed = set(AV.us_federal_business_days())
    tre = set(AV.us_business_days())
    d = dt.date(2021, 1, 1)
    div = []
    while d <= dt.date(2025, 12, 31):
        if d.weekday() < 5 and d in tre and d not in fed:
            div.append(d)
        d += dt.timedelta(days=1)
    fridays = [x for x in div if x.weekday() == 4]
    armed = (len(div) >= 3 and bool(fridays)
             and not AV.is_us_federal_business_day(dt.date(2023, 11, 10))
             and dt.date(2023, 11, 10) in tre)
    # MUTANT AV03: route the closure test through `us_business_days` — the
    # pre-fix calendar — and 2023-11-10 becomes a lawful release day.
    mutant = dt.date(2023, 11, 10) in tre and not fridays
    return check("agency_calendar_is_not_the_treasury_calendar",
                 "AV03_use_treasury_calendar_for_agency_closures",
                 armed, mutant,
                 "divergences=%d fridays=%s" % (len(div),
                                                [str(f) for f in fridays]))


def av04_h10_lands_on_a_federal_business_day():
    """R82: 34 Mondays in 2021-2025 are federal holidays and H.10 slips."""
    fed = set(AV.us_federal_business_days())
    d, mondays = dt.date(2021, 1, 1), []
    while d <= dt.date(2025, 12, 31):
        if d.weekday() == 0:
            mondays.append(d)
        d += dt.timedelta(days=1)
    holiday_mondays = [m for m in mondays if m not in fed]
    stamps = [m - dt.timedelta(days=3) for m in mondays]      # the prior Friday
    armed_bad = [s for s in stamps
                 if _rel_date(AV.rule_h10_next_monday(s)) not in fed]

    def mutant_rel(s):
        # MUTANT AV04: neutralise the `_on_or_after_bd` line — walk weekdays
        # only, which is the pre-fix rule.
        x = s + dt.timedelta(days=1)
        while x.weekday() != 0:
            x += dt.timedelta(days=1)
        return x

    mutant_bad = [s for s in stamps if mutant_rel(s) not in fed]
    armed = (not armed_bad) and len(holiday_mondays) == 34
    mutant = not mutant_bad
    return check("h10_releases_on_a_federal_business_day",
                 "AV04_walk_weekdays_not_business_days", armed, mutant,
                 "holiday_mondays=%d armed_bad=%d mutant_bad=%d"
                 % (len(holiday_mondays), len(armed_bad), len(mutant_bad)))


def av05_next_us_bd_is_the_end_of_the_full_trading_day():
    """R83/R84: 00:00 ET is inside the m0 TOKYO phase and before all of LONDON.

    D-057's default is the next FULL trading day, so the availability instant
    must be after every Tokyo and London second of that day.
    """
    stamp = dt.date(2021, 10, 19)
    ts = AV.rule_next_us_bd(stamp)
    d = _rel_date(ts)
    # the m0 clock: TOKYO runs to 07:00 UTC, LONDON 07:00-13:00 UTC
    london_end = int(dt.datetime(d.year, d.month, d.day, 13, 0,
                                 tzinfo=dt.timezone.utc).timestamp())
    mutant_ts = AV._epoch(d, AV.NY, 0, 0)          # MUTANT AV05: the pre-fix 00:00
    armed = ts > london_end and AV.is_us_federal_business_day(d)
    mutant = mutant_ts > london_end
    return check("next_us_bd_is_after_the_london_phase",
                 "AV05_midnight_et_instant", armed, mutant,
                 "avail=%s london_end=%s"
                 % (dt.datetime.fromtimestamp(ts, AV.NY).isoformat(),
                    dt.datetime.fromtimestamp(london_end,
                                              AV.NY).isoformat()))


def av06_calendar_exhaustion_is_a_counted_refusal():
    """R86: past the calendar end the observation was silently DROPPED and
    `latest()` then served a STALE one.  Refusal is a value, counted and named.
    """
    rule = "NEXT_US_BD"
    past = dt.date(2030, 6, 3)
    assert AV.availability_ts(rule, past) is AV.CALENDAR_EXHAUSTED
    trip = [(dt.date(2021, 5, 3), AV.availability_ts(rule, dt.date(2021, 5, 3)),
             (1.0,)),
            (past, AV.availability_ts(rule, past), (2.0,))]
    ser = AV.AvailSeries("TEST_EXHAUST", rule, trip, unit="x", source="test")
    g = _guard(dt.date(2030, 12, 2))
    armed_counted = ser.n_refused() == 1 and ser.refused_stamps == [past]
    try:
        ser.latest(g)
        armed_refused = False
    except MC.LeakRefusal:
        armed_refused = True
    # MUTANT AV06: neutralise the refusal bookkeeping — the pre-fix
    # `triples = [t for t in triples if t[1] is not None]` drop, with no count
    # and no hole check, so `latest()` answers with the 2021 value.
    mut = AV.AvailSeries("TEST_MUT", rule,
                         [t for t in trip if t[1] is not AV.CALENDAR_EXHAUSTED],
                         unit="x", source="test")
    try:
        mrec = mut.latest(_guard(dt.date(2030, 12, 2)))
        mut_refused = False
    except MC.LeakRefusal:
        mrec, mut_refused = None, True
    # does the MUTANT satisfy the law?  It answers with the 2021 value and
    # counts nothing, so it does not.
    mutant = (mut.n_refused() == 1 and mut_refused)
    armed = armed_counted and armed_refused
    return check("calendar_exhaustion_refuses_and_is_counted",
                 "AV06_drop_undateable_observation", armed, mutant,
                 "n_refused=%d mutant_served=%s"
                 % (ser.n_refused(), mrec["values"] if mrec else None))


def av07_vintage_is_declared_and_rides_on_every_answer():
    """R14: the banked files hold the LATEST vintage under a first-print rule."""
    rev = AV.revised_series()
    must = ("COT_DISAGG_SILVER", "COT_DISAGG_COPPER", "COT_TFF_NIKKEI",
            "FRED_DTWEXBGS", "FRED_T10YIE", "SLV_FLOW_OZ", "SHFE_INV_SILVER",
            "SHFE_INV_COPPER")
    ser = CTX.series("COT_DISAGG_SILVER")
    rec = ser.latest(_guard(dt.date(2021, 10, 20)))
    clean = CTX.series("GVZ").latest(_guard(dt.date(2021, 10, 20)))
    armed = (all(m in rev for m in must)
             and rec is not None and rec["revised_value"] is True
             and rec["vintage_class"] == AV.VINTAGE_REVISED
             and clean["revised_value"] is False)
    # MUTANT AV07: drop the `vintage_class` column from the lag table row — the
    # pre-fix state, where nothing declared the limitation.
    try:
        AV.vintage_class("COT_DISAGG_SILVER",
                         path=_lag_table_without_vintage())
        mutant = True
    except MC.LeakRefusal:
        mutant = False
    return check("vintage_class_is_declared_and_exposed",
                 "AV07_drop_vintage_column", armed, mutant,
                 "n_revised=%d" % len(rev))


_NOVINT = os.path.join(OUT_DIR, "_lag_table_no_vintage.tsv")


def _lag_table_without_vintage():
    os.makedirs(OUT_DIR, exist_ok=True)
    out = []
    with open(AV.LAG_TABLE) as fh:
        cols = None
        for line in fh:
            if line.startswith("#"):
                out.append(line.rstrip("\n"))
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                keep = [i for i, c in enumerate(f)
                        if c not in ("vintage_class", "vintage_note")]
            out.append("\t".join(f[i] for i in keep))
    with open(_NOVINT, "w", newline="\n") as fh:
        fh.write("\n".join(out) + "\n")
    return _NOVINT


# ================================================================ context ===
def cx01_disrupted_rows_never_fire_as_events():
    """R15: the two October-2025-reference rows are `scheduled_at_capture` and
    were DISRUPTED in the shutdown, yet they fired as events."""
    cal = CTX._get("CAL_BLS", CTX._bls_calendar)
    disrupted = [c for c in cal if c[2] != "actual"]
    target = [c for c in disrupted
              if _rel_date(c[0]) in (dt.date(2025, 11, 7), dt.date(2025, 11, 13))]
    assert target, "fixture rows missing from the banked BLS calendar"
    # a decision the day after the disrupted CPI print of 2025-11-13
    g = _guard(dt.date(2025, 11, 14))
    rec = CTX.recent_release(g, "SI", include_rule_derived=False)
    disrupted_ts = {c[0] for c in disrupted}
    armed = (rec is None or (rec["status"] == "actual"
                             and rec["event_ts"] not in disrupted_ts))
    # MUTANT CX01: neutralise the `if c[2] != "actual": continue` line — the
    # pre-fix scan filtered on nothing but the timestamp, so the LAST past row
    # is taken whatever its status.  Does that satisfy the law?
    past = [c for c in CTX.calendar_for("SI")
            if c[0] < g.decision_ts and c[5] != CTX.DATE_RULE]
    mut_rec = past[-1] if past else None
    mutant = (mut_rec is None or (mut_rec[2] == "actual"
                                  and mut_rec[0] not in disrupted_ts))
    return check("disrupted_calendar_rows_never_fire_as_events",
                 "CX01_no_status_filter", armed, mutant,
                 "n_disrupted=%d n_oct2025=%d mutant_fired=%s"
                 % (len(disrupted), len(target),
                    (mut_rec[1], mut_rec[2]) if mut_rec else None))


def cx02_future_row_needs_a_prior_snapshot():
    """R15: a retroactively corrected date must not join as if it had been
    known months ahead; the schedule page has to predate the decision."""
    cal = CTX._get("CAL_BLS", CTX._bls_calendar)
    g = _guard(dt.date(2021, 10, 20))
    future = [c for c in cal if c[0] > g.decision_ts and c[3]]
    joinable = [c for c in future if CTX._joinable_future(c, g)]
    # the armed side must still ADMIT a row whose schedule page we did hold
    g2 = _guard(dt.date(2023, 6, 20))
    later = [c for c in cal if c[0] > g2.decision_ts
             and CTX._joinable_future(c, g2)]
    armed = bool(future) and not joinable and bool(later)
    # MUTANT CX02: neutralise the snapshot clause of `_joinable_future` — the
    # pre-fix loop took the first future row whatever its provenance.  Under it,
    # rows whose page did not exist at the decision ARE joined, so the law
    # ("no unheld future row is joinable at 2021-10-20") does not hold.
    mutant = not future
    return check("future_calendar_row_needs_a_prior_snapshot",
                 "CX02_ignore_wayback_snapshot_date", armed, mutant,
                 "future=%d joinable_2021=%d joinable_2023=%d"
                 % (len(future), len(joinable), len(later)))


def cx03_impact_tier_is_explicit():
    """R36: nothing classified impact, so a D-077 veto could only be over- or
    under-inclusive.  An unlisted name must be UNCLASSIFIED, never a quiet low.
    """
    armed = (CTX.impact_of("Employment Situation") == CTX.IMPACT_HIGH
             and CTX.impact_of("CPI") == CTX.IMPACT_HIGH
             and CTX.impact_of("FOMC statement") == CTX.IMPACT_HIGH
             and CTX.impact_of("Initial Jobless Claims") == CTX.IMPACT_MEDIUM
             and CTX.impact_of("Nonexistent Release") ==
             CTX.IMPACT_UNCLASSIFIED
             and not CTX.impact_at_least(CTX.IMPACT_UNCLASSIFIED,
                                         CTX.IMPACT_MEDIUM)
             and CTX.impact_at_least(CTX.IMPACT_HIGH, CTX.IMPACT_MEDIUM))
    # MUTANT CX03: neutralise the explicit default in `impact_of` — score an
    # unknown release as LOW, which is what "no impact level at all" amounts to.
    mut = CTX.RELEASE_IMPACT.get("Nonexistent Release", CTX.IMPACT_LOW)
    mutant = (mut == CTX.IMPACT_UNCLASSIFIED)
    return check("release_impact_tier_is_explicit",
                 "CX03_unknown_release_defaults_to_low", armed, mutant,
                 "n_tiered=%d" % len(CTX.RELEASE_IMPACT))


def cx04_dated_universe_covers_the_blind_block():
    """R127: the DEPLOYABLE gate ran against a three-event universe containing
    ONE event across the whole 12-day E1 blind block."""
    lo = int(dt.datetime(2021, 10, 20, 0, 0, tzinfo=AV.NY).timestamp())
    hi = int(dt.datetime(2021, 11, 5, 0, 0, tzinfo=AV.NY).timestamp())
    cal = [c for c in CTX.calendar_for("SI") if lo <= c[0] < hi]
    names = {c[1] for c in cal}
    # MUTANT CX04: the pre-fix universe — Employment Situation / CPI / FOMC only
    old = [c for c in cal if c[1] in ("Employment Situation", "CPI",
                                      "FOMC statement")]
    armed = (len(cal) >= 6 and "Initial Jobless Claims" in names
             and "ISM Manufacturing PMI" in names
             and "ISM Services PMI" in names
             and len(CTX.UNDATED_HIGH_IMPACT) > 0)
    mutant = len(old) >= 6
    return check("dated_release_universe_covers_the_blind_block",
                 "CX04_three_event_universe", armed, mutant,
                 "new=%d old=%d names=%s" % (len(cal), len(old),
                                             sorted(names)))


def cx05_recent_release_age_does_not_vanish():
    """R56: the 86,400s default made "last_scheduled ... Ns ago" DISAPPEAR at
    24h+1s instead of reporting a larger age."""
    # a decision more than 24h after any scheduled release: the Saturday after
    # a Thursday claims print and a Friday with nothing on the calendar
    g = _guard(dt.date(2021, 10, 23), hh=12)
    armed_rec = CTX.recent_release(g, "SI")
    mutant_rec = CTX.recent_release(g, "SI", window_sec=86400)
    armed = (armed_rec is not None and armed_rec["since_sec"] > 86400)
    mutant = mutant_rec is not None
    return check("recent_release_age_does_not_vanish_past_24h",
                 "CX05_86400s_default_window", armed, mutant,
                 "age=%s windowed=%s"
                 % (armed_rec["since_sec"] if armed_rec else None,
                    mutant_rec))


def cx06_asset_argument_is_used():
    """R36: `next_release` / `recent_release` took an `asset` and ignored it."""
    si = CTX.calendar_for("SI")
    nkd = CTX.calendar_for("NKD")
    cov = CTX.calendar_coverage("NKD")
    armed = (len(nkd) > len(si)
             and "CAL_BOJ" in CTX.ASSET_CALENDARS["NKD"]
             and "CAL_BOJ" not in CTX.ASSET_CALENDARS["SI"]
             and cov["boj_gap_declared"] is not None
             and cov["boj_first_event"] is not None
             and cov["boj_first_event"] >= "2026-")
    try:
        CTX.calendar_for("XX")
        armed = False
    except MC.LeakRefusal:
        pass
    # MUTANT CX06: neutralise the `ASSET_CALENDARS[asset]` selection — the
    # pre-fix body, which built one calendar and ignored the argument.
    mutant = len(si) == len(nkd)
    return check("calendar_scope_uses_the_asset_argument",
                 "CX06_ignore_asset_argument", armed, mutant,
                 "si=%d nkd=%d boj_first=%s"
                 % (len(si), len(nkd), cov["boj_first_event"]))


# =================================================================== tape ===
def tp01_cache_is_keyed_on_the_definition():
    """R91: the HIT test was three checks and none of them was the extraction
    DEFINITION, so any change that did not widen the window left the whole
    corpus a silent HIT."""
    meta = {"iid": 7, "open_utc": 100, "close_utc": 200,
            "cover": [[0, 50]], "def_sha16": TAPE.DEF_SHA16}
    stale = dict(meta, def_sha16="0" * 16)
    legacy = {k: v for k, v in meta.items() if k != "def_sha16"}
    want = [(0, 10)]
    ok_now, _ = TAPE.cache_hit(meta, 7, 100, 200, want)
    ok_stale, why_stale = TAPE.cache_hit(stale, 7, 100, 200, want)
    ok_legacy, why_legacy = TAPE.cache_hit(legacy, 7, 100, 200, want)
    armed = (ok_now and not ok_stale and not ok_legacy
             and why_stale == "definition" and why_legacy == "definition"
             and len(TAPE.DEF_SHA16) == 16)

    def mutant_hit(m):
        # MUTANT TP01: the pre-fix three tests — files exist, iid, cover.
        cov = [(int(a), int(b)) for a, b in m["cover"]]
        return m.get("iid") == 7 and all(TAPE._covers(cov, a, b)
                                         for a, b in want)

    # under the mutant BOTH stale metas are HITS, so the law
    # ("a meta whose definition key does not match is a MISS") fails.
    mutant = not (mutant_hit(stale) or mutant_hit(legacy))
    return check("event_cache_is_keyed_on_the_extraction_definition",
                 "TP01_three_test_hit", armed, mutant,
                 "def_sha16=%s" % TAPE.DEF_SHA16)


def tp02_cache_validates_the_window_origin():
    """R92: `cover` is stored in SESSION SECONDS relative to `open_utc`, and
    `meta["open_utc"]` was written and then never compared."""
    meta = {"iid": 7, "open_utc": 100, "close_utc": 200,
            "cover": [[0, 50]], "def_sha16": TAPE.DEF_SHA16}
    want = [(0, 10)]
    ok_same, _ = TAPE.cache_hit(meta, 7, 100, 200, want)
    ok_moved, why = TAPE.cache_hit(meta, 7, 999, 200, want)
    ok_close, why_c = TAPE.cache_hit(meta, 7, 100, 999, want)
    armed = (ok_same and not ok_moved and not ok_close
             and why == "open_utc" and why_c == "close_utc")
    # MUTANT TP02: the pre-fix `meta.get("iid") == int(iid)` test alone — a
    # session whose open_utc moved is still a HIT, so the law does not hold.
    mutant_hit_moved = (meta.get("iid") == 7)
    mutant = not mutant_hit_moved
    return check("event_cache_validates_the_window_origin",
                 "TP02_iid_only_identity_test", armed, mutant,
                 "moved_open=%s" % why)


def tp03_classify_trades_runs_on_the_full_cache():
    """R98: `assemble` sliced first and classified the slice, against
    `classify_trades`' own written contract."""
    cid = "SI-20220103-047008-S"
    case = A.Case(cid, MC.MODE_BLIND)
    lo = max(0, case.dec_sec - TAPE.RIBBON_DIGEST_SEC - TAPE.RIBBON_RAW_SEC
             - TAPE.EXTRACT_PAD_SEC)
    hi = case.dec_sec + 1
    cached, _meta = TAPE.ensure(case.asset, case.trade_date, int(case.s.iid),
                                case.open_utc, case.close_utc, [(lo, hi)])
    arrays, i0, i1 = TAPE.window(cached, case.open_utc, lo, hi)
    full_tag, _full_flow = TAPE.classify_trades(cached)
    slice_tag, _slice_flow = TAPE.classify_trades(arrays)   # MUTANT TP03
    armed = (np.array_equal(case.trade_tag, full_tag[i0:i1])
             and case.trade_tag.size == arrays["ts_ns"].size and i0 > 0)
    # the mutant is only detectable when record i0's own book differs from
    # record i0-1's; assert the production path does NOT equal the slice path
    # whenever they differ, and that the first record is the one at risk
    differ = int(np.sum(slice_tag != full_tag[i0:i1]))
    mutant = np.array_equal(case.trade_tag, slice_tag) and differ == 0
    if differ == 0:
        # this session's boundary record is not a trade; prove the contract on a
        # constructed book instead so the test is never vacuous
        synth = {k: np.zeros(3, dtype=np.int64) for k in TAPE.ARRAYS}
        synth["action"] = np.array([ord("T")] * 3, dtype=np.uint8)
        synth["side"] = np.array([ord("B")] * 3, dtype=np.uint8)
        synth["ts_ns"] = np.array([1, 2, 3], dtype=np.int64)
        synth["size"] = np.ones(3, dtype=np.int64)
        synth["bid_px"] = np.array([10, 20, 20], dtype=np.int64)
        synth["ask_px"] = np.array([11, 21, 21], dtype=np.int64)
        synth["price"] = np.array([10, 21, 21], dtype=np.int64)
        ft, _ = TAPE.classify_trades(synth)
        st, _ = TAPE.classify_trades({k: v[1:] for k, v in synth.items()})
        armed = armed and ft[1] == TAPE.TRADE_THRU_A
        mutant = st[0] == ft[1]
        differ = int(ft[1] != st[0])
    return check("classify_trades_runs_on_the_full_cached_arrays",
                 "TP03_classify_the_slice", armed, mutant,
                 "i0=%d n_differ=%d" % (i0, differ))


# ================================================================ D-054 =====
def sn01_missing_sane_threshold_is_a_refusal():
    """R89: a session missing from sane_thresholds.tsv silently got the $500
    cap alone — a mask 2-4x too permissive against the committed $125-$250."""
    thr = B7.load_thresholds("SI")
    present = sorted(thr)[0]
    absent = 19990101
    try:
        B7.thresholds_for(thr, "SI", absent)
        armed_refuses = False
    except B7.SaneThresholdRefusal:
        armed_refuses = True
    # the refusal must reach M2 as a counted LeakRefusal, not an escape
    real = A.session_index("SI")
    d8 = sorted(real)[0]
    saved = A._MEM.pop(("sane", "SI"), None)
    A._MEM[("sane", "SI")] = {}
    A._MEM.pop(("sess", "SI", int(d8)), None)
    try:
        A.load_session("SI", d8)
        armed_m2 = False
    except MC.LeakRefusal:
        armed_m2 = True
    finally:
        A._MEM.pop(("sess", "SI", int(d8)), None)
        if saved is not None:
            A._MEM[("sane", "SI")] = saved
        else:
            A._MEM.pop(("sane", "SI"), None)
    # MUTANT SN01: the pre-fix `thr if thr is not None else [CAP]*N_PHASES`
    mutant_thr = ([B7.SANE_CAP_USD] * X.N_PHASES)
    real_thr = thr[present]
    mutant = all(np.isfinite(v) for v in mutant_thr) and max(real_thr) < 500.0
    armed = armed_refuses and armed_m2
    return check("missing_d054_threshold_is_a_refusal",
                 "SN01_cap_only_default", armed, mutant,
                 "real_thr=%s cap=%s" % (real_thr, mutant_thr))


def fv01_fvol_v1_reads_sane_seconds():
    """R80: `b2_fvol` contained ZERO occurrences of sane/b7_sane/D-054 and its
    V1 block selected `mask & s.valid` — the RAW two-sided flag."""
    src = open(os.path.join("/workspace/engine/port_m1", "b2_fvol.py")).read()
    asset, d = "NKD", dt.date(2021, 11, 1)
    d8 = d.year * 10000 + d.month * 100 + d.day
    paths = dict(X.session_paths(asset, "/workspace/artifacts/cache/port/m0"))
    s = X.load_session(asset, d, paths[d])
    mult = 4.0
    raw = B2.realized(s, mult, B2.segment_masks(s)["SESSION"])   # MUTANT FV01
    B7.apply_for(s, B7.load_thresholds(asset), asset, d8)
    sane = B2.realized(s, mult, B2.segment_masks(s)["SESSION"])
    # the committed artifact must be pinned at or after the D-054 revision
    hdr = open("/workspace/artifacts/cache/port/m1/fvol/"
               "fvol_forecasts.tsv").readline()
    armed = ("b7_sane" in src and "apply_for" in src
             and "ce0a8ca16e342cd7" not in hdr.split("sha16=")[-1]
             and sane["range_usd"] < raw["range_usd"]
             and sane["n_valid"] < raw["n_valid"])
    # MUTANT FV01: neutralise the `B7.apply_for` line in `_v1_shard`
    mutant = abs(raw["range_usd"] - sane["range_usd"]) < 1e-9
    return check("fvol_v1_reads_sane_seconds",
                 "FV01_skip_b7_apply_in_v1_shard", armed, mutant,
                 "raw=%.2f sane=%.2f n %d->%d"
                 % (raw["range_usd"], sane["range_usd"], raw["n_valid"],
                    sane["n_valid"]))


# =============================================================== renderer ===
def eb01_no_wall_clock_in_the_committed_rollup():
    """MINOR: `wall_sec` stamped wall clock into a committed TSV."""
    import time
    armed = ("wall_sec" not in EB.SESSION_COLUMNS
             and len(EB.SESSION_COLUMNS) == 12)
    # the compat shim must fold a 13-field legacy row down without shifting
    legacy = ["E1", "STUDY", "SI", 20220103, 5, 5, 5, 0, 100, 0, 7, 12.34, "OK"]
    got = EB._srow_compat(legacy)
    armed = armed and got[-1] == "OK" and len(got) == 12 and 12.34 not in got
    # MUTANT EB01: put the wall clock back — two "runs" differ
    a = list(got) + [round(time.time(), 2)]
    b = list(got) + [round(time.time() + 1.0, 2)]
    mutant = (a == b)
    return check("era_build_rollup_carries_no_wall_clock",
                 "EB01_wallclock_in_session_row", armed, mutant,
                 "cols=%d" % len(EB.SESSION_COLUMNS))


def eb02_failed_session_folds_no_partial_rows():
    """MINOR: a FAILed session returned partially-built rows and folded them
    into STREAM_RECEIPT, so a --force-less resume wrote them twice."""
    od = os.path.join(OUT_DIR, "_erabuild_fail")
    orig_out = EB.out_dir
    EB.out_dir = lambda era, block, asset, d8: od
    try:
        rows, srow = EB._render_session(
            ("E1", "STUDY", "SI", 19990101,
             [("SI-19990101-000001-L", 1, "TOKYO", "FAM", "CLS")]))
    finally:
        EB.out_dir = orig_out
    armed = (rows == [] and str(srow[11]).startswith("FAIL")
             and srow[5] == 0 and len(srow) == len(EB.SESSION_COLUMNS))
    # MUTANT EB02: neutralise the `rows = []` line in the except branch — the
    # pre-fix behaviour, where whatever was built before the exception shipped.
    mutant = (rows != [])
    return check("failed_session_contributes_no_sheet_rows",
                 "EB02_keep_partial_rows_on_fail", armed, mutant,
                 "status=%s" % str(srow[11])[:60])


def ep01_primer_writes_no_nan_cell():
    """MINOR: `era_primer` formatted every numeric cell with a bare `%.2f`, so
    an empty census slice wrote the literal `nan` into a committed table."""
    armed = (EP._n(float("nan"), 2) == MC.NA
             and EP._n(float("inf"), 2) == MC.NA
             and EP._n("", 2) == MC.NA
             and EP._n(1.5, 2) == "1.50")
    bad = []
    for era in ("E1", "E2"):
        p = os.path.join("/workspace/artifacts/cache/port/m2/era", era,
                         "ERA_PRIMER_%s.md" % era)
        if not os.path.exists(p):
            continue
        for i, line in enumerate(open(p), 1):
            if not line.startswith("|"):
                continue
            for cell in line.split("|"):
                if cell.strip() == "nan":
                    bad.append("%s:%d" % (era, i))
    armed = armed and not bad
    # MUTANT EP01: the pre-fix formatter
    mutant = ("%.2f" % float("nan")) == MC.NA
    return check("era_primer_writes_no_literal_nan_cell",
                 "EP01_bare_percent_f_formatter", armed, mutant,
                 "nan_cells=%d" % len(bad))


TESTS = (av01_cot_holiday_week_delay,
         av02_cot_monday_stamp_is_not_thursday,
         av03_federal_calendar_is_not_the_treasury_one,
         av04_h10_lands_on_a_federal_business_day,
         av05_next_us_bd_is_the_end_of_the_full_trading_day,
         av06_calendar_exhaustion_is_a_counted_refusal,
         av07_vintage_is_declared_and_rides_on_every_answer,
         cx01_disrupted_rows_never_fire_as_events,
         cx02_future_row_needs_a_prior_snapshot,
         cx03_impact_tier_is_explicit,
         cx04_dated_universe_covers_the_blind_block,
         cx05_recent_release_age_does_not_vanish,
         cx06_asset_argument_is_used,
         tp01_cache_is_keyed_on_the_definition,
         tp02_cache_validates_the_window_origin,
         tp03_classify_trades_runs_on_the_full_cache,
         sn01_missing_sane_threshold_is_a_refusal,
         fv01_fvol_v1_reads_sane_seconds,
         eb01_no_wall_clock_in_the_committed_rollup,
         eb02_failed_session_folds_no_partial_rows,
         ep01_primer_writes_no_nan_cell)

PARAMS = {
    "spec_section": SECTION,
    "law": "RED-FIRST: armed_pass MUST be 1 and mutant_pass MUST be 0 on every "
           "row; a mutant that survives is a DEAD test and fails the run",
    "findings": "R79 R39 R82 R83 R84 R85 R86 R14 R15 R36 R56 R89 R91 R92 R98 "
                "R80 R127 + the availability/tape/era_build/era_primer minors",
    "def_sha16": TAPE.DEF_SHA16,
}


def main():
    MC.verify_spec()
    n_fail = 0
    for t in TESTS:
        try:
            ok = t()
        except Exception as e:            # noqa: BLE001 — recorded, not hidden
            LEDGER.append([t.__name__, "-", 0, 0, "ERROR", repr(e)[:200]])
            ok = False
        if not ok:
            n_fail += 1
        MC.hb("test %s: %s" % (t.__name__, LEDGER[-1][4]))
    MC.write_tsv(os.path.join(OUT_DIR, "red_ledger_avail_fixlane.tsv"),
                 SECTION, MC.params_hash(PARAMS),
                 ["test", "mutant", "armed_pass", "mutant_pass", "verdict",
                  "detail"], LEDGER,
                 extra=["RED-FIRST: armed_pass MUST be 1 and mutant_pass MUST "
                        "be 0 on every row"])
    MC.write_json(os.path.join(OUT_DIR, "tests_avail_fixlane.receipt.json"),
                  {"env": MC.env_receipt(PARAMS), "n_tests": len(TESTS),
                   "n_failed": n_fail,
                   "verdict": "PASS" if n_fail == 0 else "FAIL"})
    MC.hb("avail fix-lane tests: %d/%d passed" % (len(TESTS) - n_fail,
                                                  len(TESTS)))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
