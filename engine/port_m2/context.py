#!/usr/bin/python3
"""PORT M2 — S12 context series loaders (spec §1 S12, law D-057).

Every loader returns an availability.AvailSeries built through
availability.availability_ts(rule, stamp_date) with the rule taken from
AVAILABILITY_LAGS.tsv — a loader may never hard-code a lag.

Loaded lazily and cached per process: the 30-sheet pilot renders many sheets
per asset and the COT annual files are ~10-30 MB each.

D-001 FIX PASS (2026-08-14) — the calendar layer, R15 / R36 / R56 / R127:
  R15 `_bls_calendar` dropped `wayback_snapshot_date` and never looked at
      `status`, so the two October-2025-reference rows — `scheduled_at_capture`
      and DISRUPTED in the shutdown — fired as events, and any retroactively
      corrected date was joined as if it had been known months ahead.  Both
      columns are now read and both are enforced, with the two questions split:
      a PAST release must be `actual` (it is knowable by observation), a FUTURE
      release must have been on a schedule page we already held
      (`wayback_snapshot_date < decision_date`).
  R36/R127 the calendar carried NO IMPACT LEVEL, so a D-077 "scheduled
      HIGH-IMPACT release" veto built on it could only be over- or
      under-inclusive; and the dated universe was three event types
      (Employment Situation / CPI / FOMC statement) containing ONE event across
      the whole 12-day E1 blind block.  `RELEASE_IMPACT` now gives every release
      name an explicit tier, `_derived_calendar` widens the dated universe with
      the releases whose schedule is a published standing RULE, and
      `calendar_coverage()` DECLARES the ones that are still undated.
  R36 `next_release` / `recent_release` took an `asset` and ignored it.  They
      now select the calendars in scope for that asset, and CAL_BOJ's 2026 start
      is declared per asset rather than left silent.
  R56 `recent_release`'s 86,400s default made S12's "last_scheduled ... Ns ago"
      VANISH at 24h+1s instead of reporting a larger age.  The window now
      defaults to unbounded.
"""
import csv
import datetime as dt
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import availability as AV                 # noqa: E402

REF = AV.REF_ROOT
_CACHE = {}
_TABLE = None


def table():
    global _TABLE
    if _TABLE is None:
        _TABLE = AV.lag_table_index()
    return _TABLE


def _row(series_id):
    t = table()
    if series_id not in t:
        raise MC.LeakRefusal("D-057: %s has no AVAILABILITY_LAGS.tsv row"
                             % series_id)
    return t[series_id]


def _fnum(s):
    s = (s or "").strip().strip('"')
    if not s or s in (".", "-", "--", "n/a"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _iso(s):
    s = (s or "").strip().strip('"').replace("/", "-")
    p = s.split("-")
    if len(p) != 3 or len(p[0]) != 4 or not p[0].isdigit():
        return None
    try:
        return dt.date(int(p[0]), int(p[1]), int(p[2]))
    except ValueError:
        return None


# MINOR (review 3.2): `m1_common.load_context:223` explicitly drops `year >=
# 2026` and `_csv_series` had no seal filter, so the two context loaders
# disagreed on policy.  `m2_common.era_of` refuses a 2026 session outright, so
# 2026 stamps can never be joined by any lawful decision; dropping them here
# makes the two loaders agree and keeps every series inside the seal.
SEAL_YEAR = 2026


def _sealed(d):
    return d is None or d.year >= SEAL_YEAR


# ------------------------------------------------------- simple CSV series --
def _csv_series(series_id, value_cols=None):
    """A one-row-per-date CSV, stamped on the table's declared `date_column`."""
    r = _row(series_id)
    path = os.path.join(REF, r["file"])
    cols = value_cols or [c for c in r["value_columns"].split(",") if c]
    rule = r["avail_rule"]
    vint = AV.vintage_class(series_id)
    dcol = (r.get("date_column") or "").strip()
    triples = []
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        rd = csv.reader(fh)
        header = None
        for rowv in rd:
            if not rowv:
                continue
            if header is None:
                header = [c.strip().strip('"') for c in rowv]
                continue
            rec = dict(zip(header, rowv))
            # MINOR (review 3.2): the stamp was keyed on rowv[0] and the lag
            # table's declared `date_column` was ignored, so a column reorder
            # in a refreshed source would silently restamp the whole series.
            d = _iso(rec[dcol]) if dcol in rec else _iso(rowv[0])
            if _sealed(d):
                continue                  # copyright footers / unit banners
            vals = tuple(_fnum(rec.get(c)) for c in cols)
            if all(v is None for v in vals):
                continue
            triples.append((d, AV.availability_ts(rule, d), vals))
    return AV.AvailSeries(series_id, rule, triples,
                          unit=",".join(cols), source=r["file"], vintage=vint)


def _jgb_10y():
    """The MOF curve file: two banner lines, then Date,1Y..40Y."""
    r = _row("JGB_10Y")
    path = os.path.join(REF, r["file"])
    rule = r["avail_rule"]
    triples = []
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        header = None
        for rowv in csv.reader(fh):
            if not rowv:
                continue
            if header is None:
                if rowv[0].strip() == "Date":
                    header = [c.strip() for c in rowv]
                continue
            d = _iso(rowv[0])
            if _sealed(d):
                continue
            rec = dict(zip(header, rowv))
            v = _fnum(rec.get("10Y"))
            if v is None:
                continue
            triples.append((d, AV.availability_ts(rule, d), (v,)))
    return AV.AvailSeries("JGB_10Y", rule, triples, unit="pct",
                          source=r["file"],
                          vintage=AV.vintage_class("JGB_10Y"))


def _gold_silver_ratio():
    r = _row("GOLD_SILVER_RATIO")
    rule = r["avail_rule"]
    gc, si = {}, {}
    for tgt, name in ((gc, "yahoo_GC_daily.csv"), (si, "yahoo_SI_daily.csv")):
        with open(os.path.join(REF, "port_context", name), newline="") as fh:
            rd = csv.DictReader(fh)
            for rec in rd:
                d = _iso(rec.get("date"))
                v = _fnum(rec.get("close"))
                if d is not None and v:
                    tgt[d] = v
    triples = []
    for d in sorted(set(gc) & set(si)):
        if si[d] <= 0 or _sealed(d):
            continue
        triples.append((d, AV.availability_ts(rule, d),
                        (gc[d] / si[d], gc[d], si[d])))
    return AV.AvailSeries("GOLD_SILVER_RATIO", rule, triples,
                          unit="ratio,gc_close,si_close", source=r["file"],
                          vintage=AV.vintage_class("GOLD_SILVER_RATIO"))


# ------------------------------------------------------------------- COT ----
COT_CODES = {"COT_DISAGG_SILVER": ("084691", "M_Money"),
             "COT_DISAGG_COPPER": ("085692", "M_Money"),
             "COT_TFF_NIKKEI": ("240741", "Lev_Money")}


def _cot(series_id, years):
    r = _row(series_id)
    code, prefix = COT_CODES[series_id]
    rule = r["avail_rule"]
    stem = r["file"].replace("YYYY", "%d")
    lcol = "%s_Positions_Long_All" % prefix
    scol = "%s_Positions_Short_All" % prefix
    triples = []
    used = []
    for y in years:
        path = os.path.join(REF, stem % y)
        if not os.path.exists(path):
            continue
        used.append(path)
        with open(path, newline="") as fh:
            for rec in csv.DictReader(fh):
                if rec.get("CFTC_Contract_Market_Code", "").strip() != code:
                    continue
                d = _iso(rec.get("Report_Date_as_YYYY-MM-DD"))
                if _sealed(d):
                    continue
                lo = _fnum(rec.get(lcol))
                sh = _fnum(rec.get(scol))
                oi = _fnum(rec.get("Open_Interest_All"))
                if lo is None or sh is None:
                    continue
                triples.append((d, AV.availability_ts(rule, d),
                                (lo - sh, lo, sh, oi)))
    # CC-M2-1.4: the lag table names a YYYY TEMPLATE; the sidecar must name the
    # concrete year files this series was actually built from.
    return AV.AvailSeries(series_id, rule, triples,
                          unit="net,long,short,open_interest",
                          source=" + ".join(used) if used else r["file"],
                          vintage=AV.vintage_class(series_id))


# ------------------------------------------------------------- calendars ----
# R36 / R127: D-077 restricts "scheduled HIGH-IMPACT releases" and nothing in
# the calendar layer classified impact, so any veto built on it was over- or
# under-inclusive and could not be tuned to a firm's rulebook.  This is the
# explicit tier table.  It is a NAMED CONSTANT, declared as one, with its
# source; `impact_of` returns IMPACT_UNCLASSIFIED for anything not listed and
# never a silent default, so a new release name shows up as unclassified rather
# than quietly scoring as low-impact.
#
# SOURCE OF THE TIERING: the standing news-restriction lists prop firms publish
# (the tier-1 set every rulebook names — NFP/Employment Situation, CPI, the
# FOMC statement, and the home-market central-bank statement for the index
# book), with the second tier being the releases those rulebooks list as
# restricted-but-shorter-window: weekly claims, the two ISM PMIs, ADP, and the
# BEA/Census monthly majors.  D-077 itself names no list, which is exactly why
# the tier must be explicit and sourced HERE rather than implied by whatever
# happens to be dated.
IMPACT_HIGH = "HIGH"
IMPACT_MEDIUM = "MEDIUM"
IMPACT_LOW = "LOW"
IMPACT_UNCLASSIFIED = "UNCLASSIFIED"
IMPACT_TIERS = (IMPACT_HIGH, IMPACT_MEDIUM, IMPACT_LOW, IMPACT_UNCLASSIFIED)
_IMPACT_RANK = {IMPACT_HIGH: 3, IMPACT_MEDIUM: 2, IMPACT_LOW: 1,
                IMPACT_UNCLASSIFIED: 0}

RELEASE_IMPACT = {
    # tier 1 — every prop rulebook's named set
    "Employment Situation": IMPACT_HIGH,
    "CPI": IMPACT_HIGH,
    "FOMC statement": IMPACT_HIGH,
    "BOJ policy statement": IMPACT_HIGH,
    # tier 2 — restricted with a shorter window in the same rulebooks
    "Initial Jobless Claims": IMPACT_MEDIUM,
    "ISM Manufacturing PMI": IMPACT_MEDIUM,
    "ISM Services PMI": IMPACT_MEDIUM,
    "ADP Employment": IMPACT_MEDIUM,
    "GDP advance": IMPACT_MEDIUM,
    "PCE Price Index": IMPACT_MEDIUM,
    "Durable Goods Orders": IMPACT_MEDIUM,
    "Retail Sales": IMPACT_MEDIUM,
    "PPI": IMPACT_MEDIUM,
}


def impact_of(name):
    """The D-077 impact tier of a release NAME.  Never a silent default."""
    return RELEASE_IMPACT.get(str(name).strip(), IMPACT_UNCLASSIFIED)


def impact_at_least(tier, floor):
    return _IMPACT_RANK.get(tier, 0) >= _IMPACT_RANK.get(floor, 0)


# An EVENT row is (event_ts, name, status, snapshot_iso, impact, date_source,
# date_certainty).  Positions 0 and 1 are frozen: `pattern_lib.release_calendar`
# and `news_census` read c[0]/c[1] and must keep working unchanged.
DATE_BANKED = "BANKED"            # a date read from a captured calendar file
DATE_RULE = "RULE_DERIVED"        # a date computed from a published standing rule
CERT_FIXED = "FIXED"
CERT_SHIFT_POSSIBLE = "HOLIDAY_WEEK_SHIFT_POSSIBLE"


def _bls_calendar():
    """SCHEDULE_EXEMPT: the banked BLS release dates, with their PROVENANCE.

    R15: `status` and `wayback_snapshot_date` were both dropped on the floor.
    They are the only two columns that say whether a row is a fact or a
    forecast: `actual` = the page we captured recorded the release as having
    happened on that date; `scheduled_at_capture` = it was still in the future
    when we captured the page, which is exactly what the two October-2025
    reference rows are, and both of those were DISRUPTED in the shutdown.
    """
    r = _row("CAL_BLS")
    out = []
    with open(os.path.join(REF, r["file"]), newline="") as fh:
        for rec in csv.DictReader(fh):
            d = _iso(rec.get("date"))
            if d is None:
                continue
            hh, mm = (rec.get("time_et") or "08:30").split(":")[:2]
            ts = AV._epoch(d, AV.NY, int(hh), int(mm))
            snap = _iso(rec.get("wayback_snapshot_date"))
            name = rec.get("release_name", "").strip()
            out.append((ts, name, rec.get("status", "").strip(),
                        snap.isoformat() if snap else "", impact_of(name),
                        DATE_BANKED, CERT_FIXED))
    out.sort(key=lambda c: (c[0], c[1]))
    return out


def _fomc_calendar():
    """SCHEDULE_EXEMPT: the 14:00 ET statement on each meeting's LAST day —
    exactly the join generation v3's NEWS_WINDOW family uses.

    No snapshot column: this is a static banked calendar of meetings announced
    roughly a year ahead, so the DATE was knowable ex ante and its joinability
    does not rest on when we captured a page (`snapshot_iso` is empty and
    `_joinable_future` treats an empty snapshot on an announced-ahead calendar
    as satisfied — see its docstring).
    """
    r = _row("CAL_FOMC")
    months = {m: i + 1 for i, m in enumerate(
        ("January", "February", "March", "April", "May", "June", "July",
         "August", "September", "October", "November", "December"))}
    out = []
    with open(os.path.join(REF, r["file"]), newline="") as fh:
        for rec in csv.DictReader(fh):
            y = rec.get("year", "").strip()
            mo = months.get(rec.get("month", "").strip())
            days = (rec.get("days") or "").strip()
            if not y.isdigit() or mo is None or not days:
                continue
            last = days.split("-")[-1].strip()
            if not last.isdigit():
                continue
            try:
                d = dt.date(int(y), mo, int(last))
            except ValueError:
                continue
            out.append((AV._epoch(d, AV.NY, 14, 0), "FOMC statement", "actual",
                        "", IMPACT_HIGH, DATE_BANKED, CERT_FIXED))
    out.sort(key=lambda c: (c[0], c[1]))
    return out


def _boj_calendar():
    """SCHEDULE_EXEMPT: BOJ Monetary Policy Meeting statement days.

    R36: the banked file STARTS IN 2026 and is therefore unusable inside the
    2021-2025 protocol window.  The loader is written so the row is real when
    the history is backfilled, and `calendar_coverage` DECLARES the gap for NKD
    rather than leaving "NKD sheets show US releases only" as an unexplained
    fact.  The statement clock is 12:00 JST (the MPM decision is released around
    midday on the meeting's final day).
    """
    r = _row("CAL_BOJ")
    out = []
    p = os.path.join(REF, r["file"])
    if not os.path.exists(p):
        return out
    with open(p, newline="") as fh:
        for rec in csv.DictReader(fh):
            d = _iso(rec.get("mpm_date"))
            if d is None:
                continue
            out.append((AV._epoch(d, AV.TOKYO, 12, 0), "BOJ policy statement",
                        "actual", "", IMPACT_HIGH, DATE_BANKED, CERT_FIXED))
    out.sort(key=lambda c: (c[0], c[1]))
    return out


# ------------------------------------------------- the RULE-DERIVED widening --
# R127 measured the DEPLOYABLE gate running against a three-event universe that
# contains ONE event across the whole 12-day E1 blind block.  These are the
# releases whose schedule is a PUBLISHED STANDING RULE, so their dates need no
# captured calendar and no invented data: each is generated from the rule, with
# the rule stated here, and each row carries date_source=RULE_DERIVED so a
# consumer can drop them if it wants banked dates only.  Releases whose dates
# are NOT rule-derivable stay UNDATED and are declared in `calendar_coverage`.
DERIVED_RULES = {
    "Initial Jobless Claims":
        "DOL standing rule: released every Thursday at 08:30 ET.  In a week "
        "containing a federal holiday the release can shift by a day; those "
        "rows carry date_certainty=HOLIDAY_WEEK_SHIFT_POSSIBLE and are still "
        "emitted, which is the conservative direction for a veto.",
    "ISM Manufacturing PMI":
        "ISM standing rule: released on the FIRST business day of the month at "
        "10:00 ET.",
    "ISM Services PMI":
        "ISM standing rule: released on the THIRD business day of the month at "
        "10:00 ET.",
}

# Releases R127 names that have neither a banked date nor a rule this program
# can state without inventing one.  Declared, never silently absent.
UNDATED_HIGH_IMPACT = (
    "ADP Employment",          # the Wednesday before the jobs report — depends
                               # on the BLS date, which is not joinable ex ante
    "GDP advance",             # BEA schedule, no standing rule
    "PCE Price Index",         # BEA schedule, no standing rule
    "Durable Goods Orders",    # Census schedule, no standing rule
    "Retail Sales",            # Census schedule, no standing rule
    "PPI",                     # BLS, not in the banked capture
)


def _nth_business_day(year, month, n):
    """The n-th US FEDERAL business day of a month (1-based), or None."""
    d = dt.date(year, month, 1)
    seen = 0
    while d.month == month:
        if AV.is_us_federal_business_day(d):
            seen += 1
            if seen == n:
                return d
        d += dt.timedelta(days=1)
    return None


def _holiday_week(d):
    """True if any weekday of d's Mon-Fri week is a federal closure."""
    mon = d - dt.timedelta(days=d.weekday())
    return not all(AV.is_us_federal_business_day(mon + dt.timedelta(days=k))
                   for k in range(5))


def _derived_calendar():
    """The RULE_DERIVED release rows, over the banked calendars' own span.

    The span is taken from the banked BLS + FOMC calendars so nothing is
    generated outside the window the program already carries dates for — the
    generator invents a SCHEDULE, never a RANGE.
    """
    banked = _get("CAL_BLS", _bls_calendar) + _get("CAL_FOMC", _fomc_calendar)
    if not banked:
        return []
    lo = dt.datetime.fromtimestamp(min(c[0] for c in banked), AV.NY).date()
    hi = dt.datetime.fromtimestamp(max(c[0] for c in banked), AV.NY).date()
    out = []
    # weekly claims — every Thursday 08:30 ET
    d = lo + dt.timedelta(days=(3 - lo.weekday()) % 7)
    while d <= hi:
        out.append((AV._epoch(d, AV.NY, 8, 30), "Initial Jobless Claims",
                    "actual", "", IMPACT_MEDIUM, DATE_RULE,
                    CERT_SHIFT_POSSIBLE if _holiday_week(d) else CERT_FIXED))
        d += dt.timedelta(days=7)
    # the two ISM PMIs — 1st and 3rd business day of the month, 10:00 ET
    y, m = lo.year, lo.month
    while (y, m) <= (hi.year, hi.month):
        for nth, name in ((1, "ISM Manufacturing PMI"),
                          (3, "ISM Services PMI")):
            bd = _nth_business_day(y, m, nth)
            if bd is not None and lo <= bd <= hi:
                out.append((AV._epoch(bd, AV.NY, 10, 0), name, "actual", "",
                            IMPACT_MEDIUM, DATE_RULE, CERT_FIXED))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    out.sort(key=lambda c: (c[0], c[1]))
    return out


# ------------------------------------------------------- the asset selector --
# R36: `next_release` / `recent_release` took an `asset` argument and ignored
# it.  This is the mapping they now use.
ASSET_CALENDARS = {
    "SI": ("CAL_BLS", "CAL_FOMC", "CAL_DERIVED"),
    "HG": ("CAL_BLS", "CAL_FOMC", "CAL_DERIVED"),
    "NKD": ("CAL_BLS", "CAL_FOMC", "CAL_DERIVED", "CAL_BOJ"),
}
_CAL_BUILDERS = {"CAL_BLS": _bls_calendar, "CAL_FOMC": _fomc_calendar,
                 "CAL_BOJ": _boj_calendar, "CAL_DERIVED": _derived_calendar}


def calendar_for(asset):
    if asset not in ASSET_CALENDARS:
        raise MC.LeakRefusal("R36: no calendar scope declared for asset %r"
                             % asset)
    cal = []
    for key in ASSET_CALENDARS[asset]:
        cal += _get(key, _CAL_BUILDERS[key])
    cal.sort(key=lambda c: (c[0], c[1]))
    return cal


def calendar_coverage(asset):
    """What the D-077 veto surface for `asset` DOES and DOES NOT contain.

    R127's finding was that the DEPLOYABLE reading ran against three event types
    and nobody could see that from the artefacts.  This is the declaration a
    scoring lane prints beside its verdict.
    """
    cal = calendar_for(asset)
    names = {}
    for c in cal:
        names.setdefault(c[1], {"n": 0, "impact": c[4], "date_source": c[5]})
        names[c[1]]["n"] += 1
    boj = [c for c in cal if c[1] == "BOJ policy statement"]
    return {
        "asset": asset,
        "calendars": list(ASSET_CALENDARS[asset]),
        "dated_release_names": {k: v for k, v in sorted(names.items())},
        "n_events": len(cal),
        "undated_declared": list(UNDATED_HIGH_IMPACT),
        "derived_rules": dict(DERIVED_RULES),
        "boj_first_event": (dt.datetime.fromtimestamp(boj[0][0],
                                                      AV.TOKYO).date()
                            .isoformat() if boj else None),
        "boj_gap_declared":
            "CAL_BOJ's banked history starts 2026, so no BOJ statement is "
            "dated inside the 2021-2025 protocol window; the NKD book's "
            "home-market central bank is MISSING from the veto surface for "
            "every protocol era (R36/R127, lag-table row CAL_BOJ)."
            if asset == "NKD" else None,
    }


def _row_dict(c, guard, kind):
    d = {"event_ts": c[0], "name": c[1], "status": c[2],
         "snapshot_date": c[3], "impact": c[4], "date_source": c[5],
         "date_certainty": c[6]}
    if kind == "next":
        d["countdown_sec"] = c[0] - guard.decision_ts
    else:
        d["since_sec"] = guard.decision_ts - c[0]
    return d


def _joinable_future(c, guard):
    """R15: may a FUTURE-dated calendar row be shown at this decision?

    A forward-looking row is a claim about a schedule the trader HELD at
    decision time, so its provenance has to predate the decision:
      * a BANKED BLS row must carry `wayback_snapshot_date < decision_date` —
        the page we read it off must already have existed.  Without this a date
        that was retroactively corrected joins as if it had been known months
        ahead, which is the one thing SCHEDULE_EXEMPT does not cover.
      * a row with no snapshot column (FOMC / BOJ / RULE_DERIVED) is announced
        or computable a year ahead and carries no capture provenance, so it is
        joinable on its own terms.
    """
    if not c[3]:
        return True
    return _iso(c[3]) < guard.trade_date


def next_release(guard, asset, min_impact=None, include_rule_derived=True):
    """The next SCHEDULED release strictly after decision_ts, with countdown.

    Schedule-exempt per D-057 — the DATES are known months ahead, so showing
    the next one is not a leak.  Only the date/time is shown; no outcome.
    `min_impact` (R36/D-077) restricts to a tier floor, e.g. IMPACT_HIGH.
    """
    for c in calendar_for(asset):
        if c[0] <= guard.decision_ts:
            continue
        if not include_rule_derived and c[5] == DATE_RULE:
            continue
        if min_impact is not None and not impact_at_least(c[4], min_impact):
            continue
        if not _joinable_future(c, guard):
            continue
        guard.checks += 1
        return _row_dict(c, guard, "next")
    return None


def recent_release(guard, asset, window_sec=None, min_impact=None,
                   include_rule_derived=True):
    """The most recent scheduled release strictly BEFORE decision_ts.

    R56: `window_sec` defaulted to 86,400, so S12's "last_scheduled ... Ns ago"
    silently DISAPPEARED at 24h+1s instead of reporting a larger age, and a
    consumer computing a D-077 distance got a typed-missing where it should have
    got a large number.  It now defaults to UNBOUNDED; a caller that wants the
    "a number just printed" framing passes its own window explicitly.

    R15: a PAST release must be `actual`.  A `scheduled_at_capture` row is a
    date that had not happened when the page was captured — the two
    October-2025 reference rows are exactly that and both were disrupted in the
    shutdown — so it is never asserted as an event that fired.
    """
    best = None
    for c in calendar_for(asset):
        if c[0] >= guard.decision_ts:
            break
        if window_sec is not None and guard.decision_ts - c[0] > window_sec:
            continue
        if c[2] != "actual":
            continue
        if not include_rule_derived and c[5] == DATE_RULE:
            continue
        if min_impact is not None and not impact_at_least(c[4], min_impact):
            continue
        best = c
    if best is None:
        return None
    guard.checks += 1
    return _row_dict(best, guard, "recent")


# ---------------------------------------------------------------- registry --
def _get(key, builder):
    if key not in _CACHE:
        _CACHE[key] = builder()
    return _CACHE[key]


# spec §1 S12 roster, per asset.  Order is the render order and is fixed.
ASSET_SERIES = {
    "SI": ("GVZ", "VIX", "RVX", "COT_DISAGG_SILVER", "SLV_FLOW_OZ",
           "SHFE_INV_SILVER", "FRED_DGS10", "FRED_T10YIE", "FRED_DFII10",
           "FRED_DTWEXBGS", "FRED_DEXJPUS", "JGB_10Y", "GOLD_SILVER_RATIO"),
    "HG": ("GVZ", "VIX", "RVX", "COT_DISAGG_COPPER", "SHFE_INV_COPPER",
           "FRED_DGS10", "FRED_DTWEXBGS", "FRED_DEXCHUS", "FRED_DEXJPUS",
           "JGB_10Y", "GOLD_SILVER_RATIO"),
    "NKD": ("NIKKEI_VI", "GVZ", "VIX", "RVX", "COT_TFF_NIKKEI", "FRED_DGS10",
            "FRED_DTWEXBGS", "FRED_DEXJPUS", "JGB_10Y", "GOLD_SILVER_RATIO"),
}

# MINOR (review 3.2): starting at 2021 left every early-2021 decision without a
# `back=1` predecessor for the week-over-week COT delta, so `d_net_wk` was
# typed-missing for the first report of the corpus.  2020 is loaded when the
# file is present and is skipped silently when it is not (`_cot` checks
# os.path.exists), so this never turns into a hard dependency on a file the
# repo may not carry.
COT_YEARS = (2020, 2021, 2022, 2023, 2024, 2025)


def series(series_id):
    if series_id in ("COT_DISAGG_SILVER", "COT_DISAGG_COPPER",
                     "COT_TFF_NIKKEI"):
        return _get(series_id, lambda: _cot(series_id, COT_YEARS))
    if series_id == "JGB_10Y":
        return _get(series_id, _jgb_10y)
    if series_id == "GOLD_SILVER_RATIO":
        return _get(series_id, _gold_silver_ratio)
    if series_id == "NIKKEI_VI":
        return _get(series_id, lambda: _csv_series("NIKKEI_VI", ["Close"]))
    return _get(series_id, lambda: _csv_series(series_id))


def preload(assets):
    for a in assets:
        for s in ASSET_SERIES[a]:
            series(s)
        for key in ASSET_CALENDARS.get(a, ()):
            _get(key, _CAL_BUILDERS[key])
