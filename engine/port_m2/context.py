#!/usr/bin/python3
"""PORT M2 — S12 context series loaders (spec §1 S12, law D-057).

Every loader returns an availability.AvailSeries built through
availability.availability_ts(rule, stamp_date) with the rule taken from
AVAILABILITY_LAGS.tsv — a loader may never hard-code a lag.

Loaded lazily and cached per process: the 30-sheet pilot renders many sheets
per asset and the COT annual files are ~10-30 MB each.
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


# ------------------------------------------------------- simple CSV series --
def _csv_series(series_id, value_cols=None):
    """A one-row-per-date CSV whose first column is the stamp date."""
    r = _row(series_id)
    path = os.path.join(REF, r["file"])
    cols = value_cols or [c for c in r["value_columns"].split(",") if c]
    rule = r["avail_rule"]
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
            d = _iso(rowv[0])
            if d is None:
                continue                  # copyright footers / unit banners
            rec = dict(zip(header, rowv))
            vals = tuple(_fnum(rec.get(c)) for c in cols)
            if all(v is None for v in vals):
                continue
            triples.append((d, AV.availability_ts(rule, d), vals))
    return AV.AvailSeries(series_id, rule, triples,
                          unit=",".join(cols), source=r["file"])


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
            if d is None:
                continue
            rec = dict(zip(header, rowv))
            v = _fnum(rec.get("10Y"))
            if v is None:
                continue
            triples.append((d, AV.availability_ts(rule, d), (v,)))
    return AV.AvailSeries("JGB_10Y", rule, triples, unit="pct",
                          source=r["file"])


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
        if si[d] <= 0:
            continue
        triples.append((d, AV.availability_ts(rule, d),
                        (gc[d] / si[d], gc[d], si[d])))
    return AV.AvailSeries("GOLD_SILVER_RATIO", rule, triples,
                          unit="ratio,gc_close,si_close", source=r["file"])


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
    for y in years:
        path = os.path.join(REF, stem % y)
        if not os.path.exists(path):
            continue
        with open(path, newline="") as fh:
            for rec in csv.DictReader(fh):
                if rec.get("CFTC_Contract_Market_Code", "").strip() != code:
                    continue
                d = _iso(rec.get("Report_Date_as_YYYY-MM-DD"))
                if d is None:
                    continue
                lo = _fnum(rec.get(lcol))
                sh = _fnum(rec.get(scol))
                oi = _fnum(rec.get("Open_Interest_All"))
                if lo is None or sh is None:
                    continue
                triples.append((d, AV.availability_ts(rule, d),
                                (lo - sh, lo, sh, oi)))
    return AV.AvailSeries(series_id, rule, triples,
                          unit="net,long,short,open_interest",
                          source=r["file"])


# ------------------------------------------------------------- calendars ----
def _bls_calendar():
    """SCHEDULE_EXEMPT: (event_ts_utc, name, status) sorted by event time."""
    r = _row("CAL_BLS")
    out = []
    with open(os.path.join(REF, r["file"]), newline="") as fh:
        for rec in csv.DictReader(fh):
            d = _iso(rec.get("date"))
            if d is None:
                continue
            hh, mm = (rec.get("time_et") or "08:30").split(":")[:2]
            ts = AV._epoch(d, AV.NY, int(hh), int(mm))
            out.append((ts, rec.get("release_name", "").strip(),
                        rec.get("status", "").strip()))
    out.sort()
    return out


def _fomc_calendar():
    """SCHEDULE_EXEMPT: the 14:00 ET statement on each meeting's LAST day —
    exactly the join generation v3's NEWS_WINDOW family uses."""
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
            out.append((AV._epoch(d, AV.NY, 14, 0), "FOMC statement", "actual"))
    out.sort()
    return out


def next_release(guard, asset):
    """The next SCHEDULED release strictly after decision_ts, with countdown.

    Schedule-exempt per D-057 — the DATES are known months ahead, so showing
    the next one is not a leak.  Only the date/time is shown; no outcome.
    """
    cal = _get("CAL_BLS", _bls_calendar) + _get("CAL_FOMC", _fomc_calendar)
    cal = sorted(cal)
    for ts, name, status in cal:
        if ts > guard.decision_ts:
            return {"event_ts": ts, "name": name, "status": status,
                    "countdown_sec": ts - guard.decision_ts}
    return None


def recent_release(guard, asset, window_sec=86400):
    """The most recent scheduled release strictly BEFORE decision_ts inside
    `window_sec` (the "a number just printed" context)."""
    cal = sorted(_get("CAL_BLS", _bls_calendar) + _get("CAL_FOMC",
                                                       _fomc_calendar))
    best = None
    for ts, name, status in cal:
        if ts < guard.decision_ts and guard.decision_ts - ts <= window_sec:
            best = {"event_ts": ts, "name": name, "status": status,
                    "since_sec": guard.decision_ts - ts}
    return best


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

COT_YEARS = (2021, 2022, 2023, 2024, 2025)


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
    _get("CAL_BLS", _bls_calendar)
    _get("CAL_FOMC", _fomc_calendar)
