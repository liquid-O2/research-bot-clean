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
"""
import bisect
import csv
import datetime as dt
import os
import sys
from zoneinfo import ZoneInfo

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402

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
JST_BD_SOURCE = os.path.join(REF_ROOT, "port_context", "JGB_yields_all.csv")

_CAL_CACHE = {}


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
    i = bisect.bisect_right(days, date)
    return days[i] if i < len(days) else None


def _next_weekday(date):
    d = date + dt.timedelta(days=1)
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d


# ----------------------------------------------------------- rule functions --
def rule_next_us_bd(stamp):
    d = _next_bd(us_business_days(), stamp)
    return None if d is None else _epoch(d, NY, 0, 0)


def rule_h10_next_monday(stamp):
    d = stamp + dt.timedelta(days=1)
    while d.weekday() != 0:                      # 0 = Monday
        d += dt.timedelta(days=1)
    return _epoch(d, NY, 16, 15)


def rule_cot_fri_1530et(stamp):
    return _epoch(stamp + dt.timedelta(days=3), NY, 15, 30)


def rule_next_jst_bd_1500(stamp):
    d = _next_bd(jst_business_days(), stamp)
    return None if d is None else _epoch(d, TOKYO, 15, 0)


def rule_next_jst_bd_0000(stamp):
    d = _next_bd(jst_business_days(), stamp)
    return None if d is None else _epoch(d, TOKYO, 0, 0)


def rule_next_cn_bd_0000(stamp):
    return _epoch(_next_weekday(stamp), SHANGHAI, 0, 0)


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
        raise MC.LeakRefusal("D-057: unknown avail_rule %r" % rule)
    fn = RULES[rule]
    if fn is None:
        raise MC.LeakRefusal(
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


# ------------------------------------------------------------- the series ---
class AvailSeries(object):
    """A context series that can ONLY be read through the D-057 guard."""

    __slots__ = ("series_id", "rule", "stamps", "avail", "values", "unit",
                 "source")

    def __init__(self, series_id, rule, triples, unit="", source=""):
        # triples: (stamp_date, availability_ts, value_tuple)
        triples = [t for t in triples if t[1] is not None]
        triples.sort(key=lambda t: (t[1], t[0]))
        self.series_id = series_id
        self.rule = rule
        self.stamps = [t[0] for t in triples]
        self.avail = [t[1] for t in triples]
        self.values = [t[2] for t in triples]
        self.unit = unit
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

    def latest(self, guard, back=0):
        """The `back`-th most recent AVAILABLE observation, or None.

        back=0 is the newest available, back=1 the one before it (needed for
        week-over-week deltas, which must use two AVAILABLE reports, never one
        available and one future).
        """
        i = self._cut(guard) - 1 - int(back)
        if i < 0:
            return None
        guard.checks += 1
        return {"stamp_date": self.stamps[i],
                "availability_ts": self.avail[i],
                "values": self.values[i],
                "series_id": self.series_id,
                "source": self.source}

    def n_available(self, guard):
        return self._cut(guard)

    def n_future(self, guard):
        return len(self.avail) - self._cut(guard)
