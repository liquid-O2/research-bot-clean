#!/usr/bin/python3
"""PORT M2 — D-057 availability-time join engine (spec §2).

One rule function per `avail_rule` in
artifacts/reference/port_context/AVAILABILITY_LAGS.tsv.  Nothing else in the
program is allowed to compute an availability timestamp: the leak fixture
attacks this module, so every join must come through it.

An AvailSeries is a strictly-sorted list of (stamp_date, availability_ts,
values) and answers exactly one question: "what is the newest observation whose
availability_ts is strictly before decision_ts?"  There is no `.value_at()`, no
`.latest()`, no accessor that could bypass the guard.

D-001 FIX PASS (2026-08-14) — five defects the review numbered R79/R82-R86:
  R85 the ONLY calendar here was `us_business_days()`, derived from FRED_DGS10 =
      a TREASURY calendar.  The CFTC and the Federal Reserve close on days the
      Treasury market trades (measured: 2021-01-20 Inauguration Day,
      2021-12-31 and 2023-11-10 observed holidays), so no agency rule could be
      fixed by routing through it.  `us_federal_business_days()` is now built,
      from data already in the repo, as the FEDERAL/agency calendar.
  R79/R39 `COT_FRI_1530ET` was `stamp + 3 calendar days` unconditionally: six
      computed 2021-2025 release dates were not US business days at all, ~55
      report weeks contain a federal holiday (the CFTC then slips one business
      day), and 508 MONDAY-stamped rows computed a THURSDAY release, a day
      before the earliest possible one.  It now takes the FRIDAY OF THE STAMP'S
      OWN WEEK and applies the CFTC holiday-week delay on the federal calendar.
  R82 `H10_NEXT_MONDAY` walked weekdays; 34 Mondays in 2021-2025 are federal
      holidays and the H.10 release slips.  It now lands on a federal business
      day.
  R83/R84 `NEXT_US_BD` returned 00:00 ET — 04:00/05:00 UTC, inside the m0 TOKYO
      and LONDON phases, ~10 hours before FRED had posted anything.  D-057's
      conservative default is the NEXT FULL TRADING DAY, so the instant is now
      17:00 ET (the CME close = the end of that day), and the calendar is the
      FEDERAL one because FRED is a Federal Reserve publication.
  R86 `_next_bd` past the end of the calendar returned None, which
      `AvailSeries.__init__` silently FILTERED AWAY, after which `latest()`
      served a stale observation.  Refusal is now a VALUE: `CALENDAR_EXHAUSTED`
      is carried through, counted, named, and makes `latest()` REFUSE rather
      than answer from behind the hole.
  R14 the banked files hold the LATEST vintage of revisable series joined under
      a first-print rule.  The lag table now carries `vintage_class`, every
      series is stamped FIRST_PRINT or REVISED_VALUE, and the flag rides on the
      series and on every `latest()` answer so S12 can DECLARE the limitation.
"""
import bisect
import csv
import datetime as dt
import os
from zoneinfo import ZoneInfo

class LeakRefusal(RuntimeError):
    """Raised by the D-057 guard. A refusal must reach the caller."""


REF_ROOT = "/workspace/artifacts/reference"
LAG_TABLE = os.path.join(REF_ROOT, "port_context", "AVAILABILITY_LAGS.tsv")


def abs_source(source):
    """REF_ROOT-relative source name(s) -> absolute path(s) (CC-M2-1.4).

    A source may name several files joined by ' + ' (the gold/silver ratio is
    built from two dailies); each part is absolutised independently.  An empty
    source stays empty and an already-absolute path is returned unchanged.
    """
    if not source:
        return source
    parts = [p.strip() for p in str(source).split(" + ")]
    out = [p if p.startswith("/") else os.path.join(REF_ROOT, p)
           for p in parts]
    return " + ".join(out)


NY = ZoneInfo("America/New_York")
TOKYO = ZoneInfo("Asia/Tokyo")
SHANGHAI = ZoneInfo("Asia/Shanghai")

# Calendar sources (named in the lag table's rule vocabulary).
US_BD_SOURCE = os.path.join(REF_ROOT, "port_context", "fred_refresh",
                            "FRED_DGS10.csv")
US_FED_BD_SOURCE = os.path.join(REF_ROOT, "port_context", "FRED_DTWEXBGS.csv")
JST_BD_SOURCE = os.path.join(REF_ROOT, "port_context", "JGB_yields_all.csv")

# R83/R84: D-057's conservative default is the NEXT FULL TRADING DAY.  17:00
# America/New_York is the CME close — the instant that day is complete — and it
# is the LATEST instant inside it, i.e. the conservative end.  The pre-fix 00:00
# was the least conservative instant in the same day.
US_AVAIL_HH, US_AVAIL_MM = 17, 0

_CAL_CACHE = {}


class _CalendarExhausted(object):
    """R86: a refusal VALUE, never an absence.

    Returned by a rule whose calendar cannot reach past `stamp_date`.  It is
    carried into the series, COUNTED and NAMED there, and it makes `latest()`
    refuse rather than answer from behind the hole.  The module's doctrine
    ("Unknown rule = refusal, never a default") applies to an unknown DATE too.
    """

    __slots__ = ()

    def __repr__(self):
        return "CALENDAR_EXHAUSTED"

    def __bool__(self):
        return False


CALENDAR_EXHAUSTED = _CalendarExhausted()


def _epoch(date, tz, hh, mm):
    return int(dt.datetime(date.year, date.month, date.day, hh, mm,
                           tzinfo=tz).timestamp())


# ------------------------------------------------------------- calendars ----
def us_business_days():
    """US business days, read from the data: FRED_DGS10 observation dates that
    carry a numeric value (Treasury publication days).  Deterministic and
    auditable — no hand-maintained holiday list anywhere in the program."""
    if "US" in _CAL_CACHE:
        return _CAL_CACHE["US"]
    days = []
    with open(US_BD_SOURCE, newline="") as fh:
        rd = csv.reader(fh)
        next(rd)
        for r in rd:
            if len(r) < 2:
                continue
            v = r[1].strip()
            if not v or v == ".":
                continue
            try:
                days.append(dt.date.fromisoformat(r[0].strip()))
            except ValueError:
                continue
    days.sort()
    _CAL_CACHE["US"] = days
    return days


def us_federal_business_days():
    """US FEDERAL / AGENCY business days, read from the data (R85).

    SOURCE: the observation dates of `FRED_DTWEXBGS.csv` that carry a numeric
    value.  DTWEXBGS is the Federal Reserve Board's H.10 broad dollar index: a
    rate is struck only on a day the Board itself is open, so the blank
    observation dates ARE the federal-closure set.  Verified over 2021-2025: the
    55 weekday blanks are exactly the federal holidays PLUS the two cases a
    hand-written "10 federal holidays" list would miss — 2021-01-20
    (Inauguration Day, a DC federal holiday) and the observed-holiday closures
    2021-12-31 (New Year 2022 observed) and 2023-11-10 (Veterans Day observed).

    WHY IT IS NOT `us_business_days()`: three of those 55 dates are TREASURY
    BUSINESS DAYS (2021-01-20, 2021-12-31, 2023-11-10 all carry a DGS10 value),
    so the Treasury calendar asserts the CFTC and the Fed were open when they
    were shut.  2023-11-10 is a FRIDAY — a COT release day — which is precisely
    the R79 leak.

    This is a DERIVED calendar, not a named constant list: no holiday is spelled
    out anywhere in the program, and the calendar re-derives itself whenever the
    H.10 file is refreshed.
    """
    if "USFED" in _CAL_CACHE:
        return _CAL_CACHE["USFED"]
    days = []
    with open(US_FED_BD_SOURCE, newline="") as fh:
        rd = csv.reader(fh)
        next(rd)
        for r in rd:
            if len(r) < 2:
                continue
            v = r[1].strip()
            if not v or v == ".":
                continue
            try:
                days.append(dt.date.fromisoformat(r[0].strip()))
            except ValueError:
                continue
    days.sort()
    _CAL_CACHE["USFED"] = days
    return days


def is_us_federal_business_day(date):
    days = us_federal_business_days()
    i = bisect.bisect_left(days, date)
    return i < len(days) and days[i] == date


def jst_business_days():
    """JST business days from the MOF JGB curve's observation dates."""
    if "JST" in _CAL_CACHE:
        return _CAL_CACHE["JST"]
    days = []
    with open(JST_BD_SOURCE, newline="", encoding="utf-8",
              errors="replace") as fh:
        for r in csv.reader(fh):
            if not r:
                continue
            s = r[0].strip()
            p = s.replace("/", "-").split("-")
            if len(p) != 3 or not p[0].isdigit() or len(p[0]) != 4:
                continue
            try:
                days.append(dt.date(int(p[0]), int(p[1]), int(p[2])))
            except ValueError:
                continue
    days.sort()
    _CAL_CACHE["JST"] = days
    return days


def _next_bd(days, date):
    """The first calendar day in `days` STRICTLY AFTER `date`.

    R86: past the end of the calendar this returned None and the caller's None
    was filtered out of the series without a word.  It now returns the
    CALENDAR_EXHAUSTED refusal value, which survives all the way to `latest()`.
    """
    i = bisect.bisect_right(days, date)
    return days[i] if i < len(days) else CALENDAR_EXHAUSTED


def _on_or_after_bd(days, date):
    """The first calendar day in `days` at or after `date` (refusal past end)."""
    i = bisect.bisect_left(days, date)
    return days[i] if i < len(days) else CALENDAR_EXHAUSTED


def _next_weekday(date):
    d = date + dt.timedelta(days=1)
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d


# ----------------------------------------------------------- rule functions --
def rule_next_us_bd(stamp):
    """D-057's conservative default: the END of the next FULL US trading day.

    R83/R84.  Two changes from the pre-fix rule, both forced by D-057:
      * the CALENDAR is the FEDERAL one (R85).  Every series carrying this rule
        except GOLD_SILVER_RATIO is published BY FRED, a Federal Reserve
        publication, which does not post on a federal holiday even when the
        Treasury market trades that day.  For GOLD_SILVER_RATIO (CME
        settlements via Yahoo) the federal calendar is the more conservative of
        the two, so one rule serves both.
      * the INSTANT is 17:00 ET, not 00:00 ET.  00:00 ET is 04:00/05:00 UTC —
        inside the m0 TOKYO phase (to 07:00 UTC) and before all of LONDON
        (07:00-13:00 UTC) — so a d+1 London decision read a value FRED had not
        posted, ~10 hours per series per day.  D-057's default is the next FULL
        trading day; 17:00 ET is the instant that day is complete.
    """
    d = _next_bd(us_federal_business_days(), stamp)
    return d if d is CALENDAR_EXHAUSTED else _epoch(d, NY, US_AVAIL_HH,
                                                    US_AVAIL_MM)


def rule_h10_next_monday(stamp):
    """H.10 releases Monday ~16:15 ET — on a FEDERAL business day (R82).

    34 Mondays in 2021-2025 are federal holidays (2022-01-17, 02-21, 05-30,
    06-20, 07-04 sit inside E2 alone); the Board is shut and H.10 slips to the
    next business day.  The pre-fix rule walked weekdays and asserted a release
    on every one of them.
    """
    d = stamp + dt.timedelta(days=1)
    while d.weekday() != 0:                      # 0 = Monday
        d += dt.timedelta(days=1)
    d = _on_or_after_bd(us_federal_business_days(), d)
    return d if d is CALENDAR_EXHAUSTED else _epoch(d, NY, 16, 15)


COT_RELEASE_HH, COT_RELEASE_MM = 15, 30


def rule_cot_fri_1530et(stamp):
    """The CFTC COT release, 15:30 ET on the FRIDAY OF THE REPORT WEEK, delayed
    one business day when that week contains a federal holiday (R79/R39).

    THE RULE, as the CFTC states it: the Commitments of Traders report covering
    Tuesday's positions is released the following Friday at 3:30 p.m. Eastern;
    "if a federal holiday falls during the report week the release is delayed by
    one business day".

    THE PRE-FIX RULE was `stamp + 3 calendar days`, which:
      * asserted publication on six 2021-2025 dates that are not US business
        days at all (2021-12-24, 2022-04-15, 2022-11-11, 2024-03-29,
        2025-04-18, 2025-07-04);
      * ignored the holiday-week delay in ~55 report weeks, 5 of them in E2;
      * computed a THURSDAY release for the 508 MONDAY-stamped rows (report
        dates 2023-07-03 and 2025-11-10) — a day before the earliest possible
        release.
    Taking the Friday of the stamp's OWN week fixes the Monday-stamp class by
    construction, and the closure test runs on the FEDERAL calendar (R85): the
    Treasury calendar calls 2023-11-10 — a Friday, a release day — a business
    day, and the CFTC was closed.
    """
    fri = stamp + dt.timedelta(days=(4 - stamp.weekday()) % 7)
    cal = us_federal_business_days()
    week = [fri - dt.timedelta(days=k) for k in range(5)]   # Mon..Fri
    if all(is_us_federal_business_day(d) for d in week):
        rel = fri
    else:
        rel = _next_bd(cal, fri)
        if rel is CALENDAR_EXHAUSTED:
            return CALENDAR_EXHAUSTED
    return _epoch(rel, NY, COT_RELEASE_HH, COT_RELEASE_MM)


def rule_next_jst_bd_1500(stamp):
    d = _next_bd(jst_business_days(), stamp)
    return d if d is CALENDAR_EXHAUSTED else _epoch(d, TOKYO, 15, 0)


def rule_next_jst_bd_0000(stamp):
    d = _next_bd(jst_business_days(), stamp)
    return d if d is CALENDAR_EXHAUSTED else _epoch(d, TOKYO, 0, 0)


def rule_next_cn_bd_0000(stamp):
    """00:00 Asia/Shanghai of the first weekday after the stamp's REPORT WEEK.

    R40 (the sibling lane's lag-VALUE audit) measured this rule 3.6 days SHORT
    on 17 of 112 SHFE stamps: the mirror's stamps are Friday-dated 670 times but
    Mon/Tue/Wed/Thu 111 times (Chinese holiday weeks move the report), and the
    pre-fix `next weekday after the stamp` made a Wednesday-stamped report
    available Thursday 00:00 CST while the row's own publication_fact says SHFE
    posts the weekly stock report Friday ~15:30 CST.  Anchoring on the FRIDAY OF
    THE STAMP'S WEEK makes the rule conservative for every stamp weekday and
    leaves the Friday-stamped majority unchanged.
    """
    fri = stamp + dt.timedelta(days=(4 - stamp.weekday()) % 7)
    return _epoch(_next_weekday(fri), SHANGHAI, 0, 0)


RULES = {
    "NEXT_US_BD": rule_next_us_bd,
    "H10_NEXT_MONDAY": rule_h10_next_monday,
    "COT_FRI_1530ET": rule_cot_fri_1530et,
    "NEXT_JST_BD_1500": rule_next_jst_bd_1500,
    "NEXT_JST_BD_0000": rule_next_jst_bd_0000,
    "NEXT_CN_BD_0000": rule_next_cn_bd_0000,
    "SCHEDULE_EXEMPT": None,             # never lag-joined; see calendars.py use
}


def availability_ts(rule, stamp_date):
    """The single entry point.  Unknown rule = refusal, never a default."""
    if rule not in RULES:
        raise LeakRefusal("D-057: unknown avail_rule %r" % rule)
    fn = RULES[rule]
    if fn is None:
        raise LeakRefusal(
            "D-057: %s series are schedule-exempt and must not be lag-joined"
            % rule)
    return fn(stamp_date)


# --------------------------------------------------------------- lag table --
def load_lag_table(path=LAG_TABLE):
    """[{column: value}] in file order, comments stripped."""
    rows = []
    with open(path, newline="") as fh:
        cols = None
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            rows.append(dict(zip(cols, f)))
    return rows


def lag_table_index(path=LAG_TABLE):
    return {r["series_id"]: r for r in load_lag_table(path)}


# ------------------------------------------------------------- vintage (R14) --
VINTAGE_FIRST_PRINT = "FIRST_PRINT"
VINTAGE_REVISED = "REVISED_VALUE"
VINTAGE_SCHEDULE = "SCHEDULE"
VINTAGE_CLASSES = (VINTAGE_FIRST_PRINT, VINTAGE_REVISED, VINTAGE_SCHEDULE)


def vintage_class(series_id, path=LAG_TABLE):
    """R14: is the banked value the one that was PUBLISHED at availability_ts?

    The lag table's `publication_fact` documents FIRST-PRINT timing only, while
    the banked files hold the LATEST vintage of every series.  A series with no
    vintage archive is therefore joined, in form legally (availability_ts <
    decision_ts) and in substance falsely (the value was not knowable then).
    D-057 cannot be satisfied for those without a vintage archive we do not
    have, so the limitation is DECLARED per series rather than left silent:
    REVISED_VALUE means "this row's value may be a later correction of what was
    published at its availability_ts".  Unknown class = refusal, never a
    default.
    """
    t = lag_table_index(path)
    if series_id not in t:
        raise LeakRefusal("D-057: %s has no AVAILABILITY_LAGS.tsv row"
                             % series_id)
    v = (t[series_id].get("vintage_class") or "").strip()
    if v not in VINTAGE_CLASSES:
        raise LeakRefusal(
            "R14: %s carries no declared vintage_class (got %r); the lag table "
            "must state FIRST_PRINT / REVISED_VALUE / SCHEDULE explicitly"
            % (series_id, v))
    return v


def revised_series(path=LAG_TABLE):
    """The declared REVISED_VALUE set, for an S12 limitation block."""
    return tuple(sorted(r["series_id"] for r in load_lag_table(path)
                        if (r.get("vintage_class") or "").strip()
                        == VINTAGE_REVISED))


# ------------------------------------------------------------- the series ---
class AvailSeries(object):
    """A context series that can ONLY be read through the D-057 guard."""

    __slots__ = ("series_id", "rule", "stamps", "avail", "values", "unit",
                 "source", "vintage", "refused_stamps")

    def __init__(self, series_id, rule, triples, unit="", source="",
                 vintage=VINTAGE_FIRST_PRINT):
        # triples: (stamp_date, availability_ts, value_tuple)
        # R86: an observation whose availability DATE could not be computed is
        # a REFUSAL, kept and named here, never a silent drop.  `None` is still
        # accepted from a caller for compatibility and is treated identically.
        refused = sorted(t[0] for t in triples
                         if t[1] is None or t[1] is CALENDAR_EXHAUSTED)
        triples = [t for t in triples
                   if t[1] is not None and t[1] is not CALENDAR_EXHAUSTED]
        triples.sort(key=lambda t: (t[1], t[0]))
        self.series_id = series_id
        self.rule = rule
        self.refused_stamps = refused
        self.stamps = [t[0] for t in triples]
        self.avail = [t[1] for t in triples]
        self.values = [t[2] for t in triples]
        self.unit = unit
        self.vintage = vintage
        # CC-M2-1.4: a series names its source file as an ABSOLUTE path.  The
        # lag table stores REF_ROOT-relative file names (its own convention),
        # so the join happens once, here, rather than in every consumer.
        self.source = abs_source(source)

    def __len__(self):
        return len(self.avail)

    def _cut(self, guard):
        """Index one past the last observation available at decision_ts."""
        # bisect_left on decision_ts gives the first avail >= decision_ts, which
        # is exactly the strict "< decision_ts" cut of CausalGuard.avail.
        return bisect.bisect_left(self.avail, guard.decision_ts)

    def n_refused(self):
        """R86: observations this series could not date.  A counted value."""
        return len(self.refused_stamps)

    def _assert_no_hole(self, guard):
        """R86: refuse rather than answer from BEHIND a calendar hole.

        `latest()` used to serve the newest DATEABLE observation while a NEWER
        one had been dropped for want of a calendar — a stale value presented as
        current, with no refusal and no count.  If any undateable stamp is at or
        before the decision date, this series cannot answer at all.
        """
        if not self.refused_stamps:
            return
        dd = guard.trade_date
        bad = [s for s in self.refused_stamps if s <= dd]
        if bad:
            guard.refusals.append((self.series_id, "calendar_exhausted",
                                   str(bad[-1]), str(dd)))
            raise LeakRefusal(
                "D-057/R86: %s has %d observation(s) whose availability date "
                "cannot be computed (calendar ends before stamp %s); serving "
                "an older value at decision date %s would be a stale answer"
                % (self.series_id, len(bad), bad[-1], dd))

    def latest(self, guard, back=0):
        """The `back`-th most recent AVAILABLE observation, or None.

        back=0 is the newest available, back=1 the one before it (needed for
        week-over-week deltas, which must use two AVAILABLE reports, never one
        available and one future).
        """
        self._assert_no_hole(guard)
        i = self._cut(guard) - 1 - int(back)
        if i < 0:
            return None
        guard.checks += 1
        return {"stamp_date": self.stamps[i],
                "availability_ts": self.avail[i],
                "values": self.values[i],
                "series_id": self.series_id,
                "source": self.source,
                # R14: every answer carries its own vintage honesty flag, so a
                # consumer cannot read a revised value as a first print.
                "vintage_class": self.vintage,
                "revised_value": self.vintage == VINTAGE_REVISED}

    def n_available(self, guard):
        # MINOR (review 3.2): these are interrogations of a context series and
        # must appear in the certificate's audit count like every other read.
        guard.checks += 1
        return self._cut(guard)

    def n_future(self, guard):
        guard.checks += 1
        return len(self.avail) - self._cut(guard)
