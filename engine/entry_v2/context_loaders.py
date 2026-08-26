#!/usr/bin/env python3
"""Parsers for audited slow-context series."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import datetime as dt
import importlib.util
import math
from pathlib import Path
import sys
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

import numpy as np
import torch
from torch import Tensor

from . import common as C
from .context_pack import (
    ASSET_CONTEXT_SERIES,
    HISTORY_LENGTH,
    AvailableObservation,
    ContextSource,
    build_context_pack,
)
from .contracts import ContextPack, ContractError, VintageClass

from .context_roster import (
    LAG_TABLE, MAX_VALUE_WIDTH, NS, PORT_M2_AVAILABILITY, REFERENCE_ROOT,
)

_AVAILABILITY: Any | None = None


def _availability_module() -> Any:
    """Load the audited lag arithmetic under a collision-proof module name."""
    global _AVAILABILITY
    if _AVAILABILITY is not None:
        return _AVAILABILITY
    name = "_entry_v2_audited_port_m2_availability"
    spec = importlib.util.spec_from_file_location(name, PORT_M2_AVAILABILITY)
    if spec is None or spec.loader is None:
        raise C.EntryV2Refusal("cannot load audited context availability module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    _AVAILABILITY = module
    return module


def _date(value: str | None) -> dt.date | None:
    text = (value or "").strip().strip('"').replace("/", "-")
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        pass
    # MOF/JGB sheets switch to unpadded d/m parts (e.g. 2021-1-5); parse
    # the same three integer fields rather than dropping the row.
    parts = text.split("-")
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        try:
            return dt.date(int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError:
            return None
    return None


def _number(value: str | None) -> float | None:
    text = (value or "").strip().strip('"')
    if not text or text in {".", "-", "--", "n/a", "NA"}:
        return None
    try:
        out = float(text)
    except ValueError:
        return None
    return out if math.isfinite(out) else None


def _d8(date: dt.date) -> int:
    return date.year * 10_000 + date.month * 100 + date.day


def _source_paths(row: Mapping[str, str]) -> tuple[Path, ...]:
    names = [part.strip() for part in row["file"].split(" + ")]
    paths = tuple((REFERENCE_ROOT / name).resolve() for name in names)
    for path in paths:
        try:
            path.relative_to(REFERENCE_ROOT.resolve())
        except ValueError as exc:
            raise C.EntryV2Refusal(f"context source escapes reference root: {path}") from exc
        if not path.is_file():
            raise C.EntryV2Refusal(f"context source missing: {path}")
    return paths


@dataclass(frozen=True)
class _LoadedSeries:
    observations: tuple[AvailableObservation, ...]
    paths: tuple[str, ...]
    refused_dates: int = 0
    unproved_rows: int = 0
    status: str = "FIRST_PRINT"


def _available_ns(rule: str, stamp: dt.date) -> int | None:
    availability = _availability_module()
    value = availability.availability_ts(rule, stamp)
    if value is availability.CALENDAR_EXHAUSTED:
        return None
    return int(value) * NS


def _simple_csv(row: Mapping[str, str], end_d8_exclusive: int) -> _LoadedSeries:
    path, = _source_paths(row)
    value_columns = tuple(x for x in row["value_columns"].split(",") if x)
    if len(value_columns) > MAX_VALUE_WIDTH:
        raise C.EntryV2Refusal(
            f"{row['series_id']} width {len(value_columns)} exceeds tensor contract"
        )
    observations: list[AvailableObservation] = []
    refused = 0
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        for record in csv.DictReader(handle):
            stamp = _date(record.get(row["date_column"]))
            if stamp is None or _d8(stamp) >= end_d8_exclusive:
                continue
            values = tuple(_number(record.get(column)) for column in value_columns)
            if all(value is None for value in values):
                continue
            available = _available_ns(row["avail_rule"], stamp)
            if available is None:
                refused += 1
                continue
            observations.append(AvailableObservation(
                stamp.isoformat(), available, values
            ))
    return _LoadedSeries(tuple(observations), (str(path),), refused)


def _jgb_10y(row: Mapping[str, str], end_d8_exclusive: int) -> _LoadedSeries:
    path, = _source_paths(row)
    observations: list[AvailableObservation] = []
    refused = 0
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        header: list[str] | None = None
        for raw in csv.reader(handle):
            if not raw:
                continue
            if header is None:
                if raw[0].strip() == "Date":
                    header = [cell.strip() for cell in raw]
                continue
            stamp = _date(raw[0])
            if stamp is None or _d8(stamp) >= end_d8_exclusive:
                continue
            value = _number(dict(zip(header, raw)).get("10Y"))
            if value is None:
                continue
            available = _available_ns(row["avail_rule"], stamp)
            if available is None:
                refused += 1
                continue
            observations.append(AvailableObservation(
                stamp.isoformat(), available, (value,)
            ))
    return _LoadedSeries(tuple(observations), (str(path),), refused)


def _daily_close(path: Path, end_d8_exclusive: int) -> dict[dt.date, float]:
    out: dict[dt.date, float] = {}
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        for record in csv.DictReader(handle):
            stamp = _date(record.get("date"))
            if stamp is None or _d8(stamp) >= end_d8_exclusive:
                continue
            value = _number(record.get("close"))
            if value is not None:
                out[stamp] = value
    return out


def _gold_silver(row: Mapping[str, str], end_d8_exclusive: int) -> _LoadedSeries:
    gc_path, si_path = _source_paths(row)
    gc = _daily_close(gc_path, end_d8_exclusive)
    si = _daily_close(si_path, end_d8_exclusive)
    observations: list[AvailableObservation] = []
    refused = 0
    for stamp in sorted(set(gc).intersection(si)):
        if si[stamp] <= 0.0:
            continue
        available = _available_ns(row["avail_rule"], stamp)
        if available is None:
            refused += 1
            continue
        observations.append(AvailableObservation(
            stamp.isoformat(), available,
            (gc[stamp] / si[stamp], gc[stamp], si[stamp]),
        ))
    return _LoadedSeries(
        tuple(observations), (str(gc_path), str(si_path)), refused
    )


_COT_MARKET_NAMES = {
    "COT_DISAGG_SILVER": ("SILVER - COMMODITY EXCHANGE INC.",),
    # CFTC renamed the copper market ("COPPER-GRADE #1" -> "COPPER- #1")
    # during 2022; both names denote the same COMEX contract series.
    "COT_DISAGG_COPPER": ("COPPER-GRADE #1 - COMMODITY EXCHANGE INC.",
                          "COPPER- #1 - COMMODITY EXCHANGE INC."),
    # NKD is the USD-denominated CME contract; the YEN DENOM row is NIY and
    # is deliberately not consumed here (receipted choice).
    "COT_TFF_NIKKEI": ("NIKKEI STOCK AVERAGE - CHICAGO MERCANTILE EXCHANGE",),
}


def _cot(row: Mapping[str, str], end_d8_exclusive: int) -> _LoadedSeries:
    """CFTC yearly as-published archive: one weekly row per report date."""
    markets = _COT_MARKET_NAMES[row["series_id"]]
    value_columns = [c.strip() for c in row["value_columns"].split(",") if c.strip()]
    pattern = row["file"].split("/")[-1]
    first_year = 2021
    last_year = min(2025, (int(end_d8_exclusive) - 1) // 10000)
    observations: list[AvailableObservation] = []
    refused = 0
    paths: list[str] = []
    for year in range(first_year, last_year + 1):
        path = (REFERENCE_ROOT / "port_context" / "cot" /
                pattern.replace("YYYY", str(year))).resolve()
        if not path.is_file():
            raise C.EntryV2Refusal(f"cot archive missing: {path}")
        paths.append(str(path))
        with path.open(newline="", encoding="utf-8", errors="replace") as handle:
            for record in csv.DictReader(handle):
                name = (record.get("Market_and_Exchange_Names") or "").strip()
                if name not in markets:
                    continue
                stamp = _date(record.get("Report_Date_as_YYYY-MM-DD"))
                if stamp is None or _d8(stamp) >= end_d8_exclusive:
                    continue
                values = tuple(_number(record.get(column)) for column in value_columns)
                if any(value is None for value in values):
                    refused += 1
                    continue
                available = _available_ns(row["avail_rule"], stamp)
                if available is None:
                    refused += 1
                    continue
                observations.append(AvailableObservation(
                    stamp.isoformat(), available, values))
    stamps = [obs.stamp for obs in observations]
    if len(stamps) != len(set(stamps)):
        raise C.EntryV2Refusal(
            f"{row['series_id']} emits duplicate report dates across market names")
    return _LoadedSeries(tuple(observations), tuple(paths), refused)


def _first_print(row: Mapping[str, str], end_d8_exclusive: int) -> _LoadedSeries:
    series_id = row["series_id"]
    if series_id == "JGB_10Y":
        return _jgb_10y(row, end_d8_exclusive)
    if series_id == "GOLD_SILVER_RATIO":
        return _gold_silver(row, end_d8_exclusive)
    if series_id in _COT_MARKET_NAMES:
        return _cot(row, end_d8_exclusive)
    return _simple_csv(row, end_d8_exclusive)


_NY = ZoneInfo("America/New_York")
_MONTH = {name: index + 1 for index, name in enumerate(
    ("January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"))}


def _event_ns(stamp: dt.date, hour: int, minute: int, zone: ZoneInfo) -> int:
    return int(dt.datetime(stamp.year, stamp.month, stamp.day, hour, minute,
                           tzinfo=zone).timestamp()) * NS


def _bls_events(row: Mapping[str, str], end_d8_exclusive: int) -> _LoadedSeries:
    path, = _source_paths(row)
    observations: list[AvailableObservation] = []
    unproved = 0
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        for record in csv.DictReader(handle):
            stamp = _date(record.get("date"))
            if stamp is None or _d8(stamp) >= end_d8_exclusive:
                continue
            # Without an announcement timestamp, a schedule may not be shown
            # before it happens.  An `actual` row becomes knowable at the event
            # clock itself; scheduled-at-capture rows are not asserted.
            if (record.get("status") or "").strip() != "actual":
                unproved += 1
                continue
            try:
                hour, minute = map(int, (record.get("time_et") or "").split(":")[:2])
            except (TypeError, ValueError):
                unproved += 1
                continue
            name = (record.get("release_name") or "").strip()
            if name == "Employment Situation":
                values = (1.0, 0.0)
            elif name == "CPI":
                values = (0.0, 1.0)
            else:
                unproved += 1
                continue
            event = _event_ns(stamp, hour, minute, _NY)
            observations.append(AvailableObservation(stamp.isoformat(), event, values))
    return _LoadedSeries(
        tuple(observations), (str(path),), unproved_rows=unproved,
        status="PAST_ACTUAL_EVENT_ONLY",
    )


def _fomc_events(row: Mapping[str, str], end_d8_exclusive: int) -> _LoadedSeries:
    path, = _source_paths(row)
    observations: list[AvailableObservation] = []
    unproved = 0
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        for record in csv.DictReader(handle):
            year = (record.get("year") or "").strip()
            month = _MONTH.get((record.get("month") or "").strip())
            last = (record.get("days") or "").split("-")[-1].strip()
            if not year.isdigit() or month is None or not last.isdigit():
                unproved += 1
                continue
            try:
                stamp = dt.date(int(year), month, int(last))
            except ValueError:
                unproved += 1
                continue
            if _d8(stamp) >= end_d8_exclusive:
                continue
            # Same conservative rule as BLS: no forward schedule is inferred
            # from this file because it carries no announcement timestamp.
            event = _event_ns(stamp, 14, 0, _NY)
            observations.append(AvailableObservation(stamp.isoformat(), event, (1.0,)))
    return _LoadedSeries(
        tuple(observations), (str(path),), unproved_rows=unproved,
        status="PAST_EVENT_ONLY_NO_ANNOUNCEMENT_TS",
    )


_JST = ZoneInfo("Asia/Tokyo")


def _boj_events(row: Mapping[str, str], end_d8_exclusive: int) -> _LoadedSeries:
    """BOJ MPM decision days (second meeting day), BOJ-published history.

    Same conservative law as the FOMC file: no forward schedule is inferred;
    the event becomes knowable at a conservative post-announcement clock
    (15:00 JST on the decision day).  Rows at/after the development wall are
    never emitted, which keeps sealed-year dates unread by consumers.
    """
    path, = _source_paths(row)
    observations: list[AvailableObservation] = []
    unproved = 0
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        for record in csv.DictReader(handle):
            stamp = _date(record.get("mpm_date"))
            if stamp is None:
                unproved += 1
                continue
            if _d8(stamp) >= end_d8_exclusive:
                continue
            event = _event_ns(stamp, 15, 0, _JST)
            observations.append(AvailableObservation(stamp.isoformat(), event, (1.0,)))
    return _LoadedSeries(
        tuple(observations), (str(path),), unproved_rows=unproved,
        status="PAST_EVENT_ONLY_NO_ANNOUNCEMENT_TS",
    )


def _schedule(row: Mapping[str, str], end_d8_exclusive: int) -> _LoadedSeries:
    if row["series_id"] == "CAL_BLS":
        return _bls_events(row, end_d8_exclusive)
    if row["series_id"] == "CAL_FOMC":
        return _fomc_events(row, end_d8_exclusive)
    if row["series_id"] == "CAL_BOJ":
        return _boj_events(row, end_d8_exclusive)
    raise C.EntryV2Refusal(f"unsupported schedule source: {row['series_id']}")


def _receipt_observations(observations: Sequence[AvailableObservation]) -> str:
    return C.object_sha256([
        {
            "stamp": observation.stamp,
            "availability_ts_ns": observation.availability_ts_ns,
            "values": observation.values,
        }
        for observation in observations
    ])

