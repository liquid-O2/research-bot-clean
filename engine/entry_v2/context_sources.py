#!/usr/bin/env python3
"""Audited slow-context adapter and fixed-width tensorizer for entry-v2.

Only values declared ``FIRST_PRINT`` in ``AVAILABILITY_LAGS.tsv`` may enter a
student tensor.  ``REVISED_VALUE`` files are deliberately not opened: their
lag-table declarations are receipted and their series remain typed-missing.
Calendar rows are represented only after the historical event clock itself;
this module never invents an announcement timestamp or exposes a future
countdown.  A calendar without a proved development-period event stays
typed-missing.

The availability arithmetic is reused from the already adversarially audited
``port_m2/availability.py`` module.  Parsing, sealing, receipts, packing and
tensorization are isolated here and under :mod:`engine.entry_v2`.
"""

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


NS = 1_000_000_000
REFERENCE_ROOT = C.REPO_ROOT / "artifacts" / "reference"
LAG_TABLE = C.CONTEXT_ROOT / "AVAILABILITY_LAGS.tsv"
PORT_M2_AVAILABILITY = C.REPO_ROOT / "engine" / "port_m2" / "availability.py"

MAX_VALUE_WIDTH = 4
VALUE_OFFSET = 0
DELTA_OFFSET = VALUE_OFFSET + MAX_VALUE_WIDTH
LOG_AGE_OFFSET = DELTA_OFFSET + MAX_VALUE_WIDTH
VALUE_PRESENT_OFFSET = LOG_AGE_OFFSET + 1
DELTA_PRESENT_OFFSET = VALUE_PRESENT_OFFSET + MAX_VALUE_WIDTH
CONTEXT_TENSOR_WIDTH = DELTA_PRESENT_OFFSET + MAX_VALUE_WIDTH

CONTEXT_FEATURE_NAMES = tuple(
    [f"value_{i}" for i in range(MAX_VALUE_WIDTH)]
    + [f"delta_{i}" for i in range(MAX_VALUE_WIDTH)]
    + ["log1p_age_seconds"]
    + [f"value_{i}_present" for i in range(MAX_VALUE_WIDTH)]
    + [f"delta_{i}_present" for i in range(MAX_VALUE_WIDTH)]
)

TABULAR_CONTEXT_STATISTICS = ("last", "mean", "std", "min", "max")


def _union_roster() -> tuple[str, ...]:
    out: list[str] = []
    for asset in C.ASSETS:
        for series_id in ASSET_CONTEXT_SERIES[asset]:
            if series_id not in out:
                out.append(series_id)
    return tuple(out)


GLOBAL_CONTEXT_SERIES = _union_roster()
CONTEXT_TYPE_ID = MappingProxyType(
    {series_id: index for index, series_id in enumerate(GLOBAL_CONTEXT_SERIES)}
)

TABULAR_CONTEXT_FEATURE_NAMES = tuple(
    name
    for series_id in GLOBAL_CONTEXT_SERIES
    for name in (
        *(
            f"ctx_{series_id}_{stat}_{feature_name}"
            for stat in TABULAR_CONTEXT_STATISTICS
            for feature_name in CONTEXT_FEATURE_NAMES
        ),
        f"ctx_{series_id}_history_coverage",
    )
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


@dataclass(frozen=True)
class ContextTensor:
    """One candidate's exact model input for the slow-context branch."""

    values: Tensor
    type_ids: Tensor
    valid: Tensor
    series_ids: tuple[str, ...]
    feature_names: tuple[str, ...] = CONTEXT_FEATURE_NAMES

    def validate(self) -> None:
        expected = (len(self.series_ids), HISTORY_LENGTH, CONTEXT_TENSOR_WIDTH)
        if tuple(self.values.shape) != expected or self.values.dtype != torch.float32:
            raise C.EntryV2Refusal(f"invalid context value tensor: {self.values.shape}")
        if tuple(self.valid.shape) != expected[:-1] or self.valid.dtype != torch.bool:
            raise C.EntryV2Refusal("invalid context validity tensor")
        if tuple(self.type_ids.shape) != (len(self.series_ids),):
            raise C.EntryV2Refusal("invalid context type-id tensor")
        if self.type_ids.dtype != torch.int64:
            raise C.EntryV2Refusal("context type ids must be int64")
        if not bool(torch.isfinite(self.values).all()):
            raise C.EntryV2Refusal("context tensor contains a non-finite value")


def tensorize_context_pack(pack: ContextPack) -> ContextTensor:
    """Right-align last-64 points into a stable typed tensor.

    Each observation carries raw values, raw deltas, log age and explicit
    per-component presence masks.  The separate ``valid`` mask distinguishes
    an absent history slot or entirely masked series from a real observation.
    """
    expected_ids = tuple(ASSET_CONTEXT_SERIES[pack.asset])
    actual_ids = tuple(item.series_id for item in pack.series)
    if actual_ids != expected_ids:
        raise C.EntryV2Refusal(
            f"context roster mismatch for {pack.asset}: {actual_ids} != {expected_ids}"
        )
    values = torch.zeros(
        (len(actual_ids), HISTORY_LENGTH, CONTEXT_TENSOR_WIDTH), dtype=torch.float32
    )
    valid = torch.zeros((len(actual_ids), HISTORY_LENGTH), dtype=torch.bool)
    type_ids = torch.tensor(
        [CONTEXT_TYPE_ID[series_id] for series_id in actual_ids], dtype=torch.int64
    )
    for series_index, series in enumerate(pack.series):
        if not series.mask:
            continue
        if len(series.points) > HISTORY_LENGTH:
            raise C.EntryV2Refusal("context pack exceeds fixed history")
        start = HISTORY_LENGTH - len(series.points)
        for offset, point in enumerate(series.points):
            row = start + offset
            if len(point.values) > MAX_VALUE_WIDTH:
                raise C.EntryV2Refusal(
                    f"{series.series_id} exceeds fixed context value width"
                )
            valid[series_index, row] = True
            for column, value in enumerate(point.values):
                if value is not None:
                    values[series_index, row, VALUE_OFFSET + column] = float(value)
                    values[series_index, row, VALUE_PRESENT_OFFSET + column] = 1.0
            for column, delta in enumerate(point.deltas):
                if delta is not None:
                    values[series_index, row, DELTA_OFFSET + column] = float(delta)
                    values[series_index, row, DELTA_PRESENT_OFFSET + column] = 1.0
            values[series_index, row, LOG_AGE_OFFSET] = math.log1p(
                point.age_ns / NS
            )
    tensor = ContextTensor(values, type_ids, valid, actual_ids)
    tensor.validate()
    return tensor


def stack_context_tensors(items: Iterable[ContextTensor]) -> tuple[Tensor, Tensor, Tensor]:
    tensors = tuple(items)
    if not tensors:
        raise C.EntryV2Refusal("cannot stack an empty context tensor sequence")
    for item in tensors:
        item.validate()
        if item.series_ids != tensors[0].series_ids or not torch.equal(
            item.type_ids, tensors[0].type_ids
        ):
            raise C.EntryV2Refusal("context tensors do not share a fixed roster")
    return (
        torch.stack([item.values for item in tensors]),
        tensors[0].type_ids.clone(),
        torch.stack([item.valid for item in tensors]),
    )


@dataclass(frozen=True)
class _TensorSource:
    availability_ts_ns: np.ndarray
    values: np.ndarray
    deltas: np.ndarray
    value_present: np.ndarray
    delta_present: np.ndarray


def _tensor_source(source: ContextSource | None) -> _TensorSource | None:
    if (source is None or source.vintage_class is VintageClass.REVISED_VALUE
            or not source.observations):
        return None
    rows = len(source.observations)
    availability = np.asarray(
        [row.availability_ts_ns for row in source.observations], dtype=np.int64
    )
    values = np.zeros((rows, MAX_VALUE_WIDTH), dtype=np.float32)
    deltas = np.zeros_like(values)
    value_present = np.zeros_like(values)
    delta_present = np.zeros_like(values)
    previous: tuple[object, ...] | None = None
    for index, observation in enumerate(source.observations):
        current = tuple(observation.values)
        for column, value in enumerate(current):
            if value is not None:
                values[index, column] = float(value)
                value_present[index, column] = 1.0
            if previous is None or column >= len(previous):
                continue
            old = previous[column]
            if (value is None or old is None or isinstance(value, bool)
                    or isinstance(old, bool)):
                continue
            deltas[index, column] = float(value) - float(old)
            delta_present[index, column] = 1.0
        previous = current
    for array in (availability, values, deltas, value_present, delta_present):
        array.setflags(write=False)
    return _TensorSource(
        availability, values, deltas, value_present, delta_present
    )


@dataclass(frozen=True)
class CausalContextRepository:
    asset: str
    sources: Mapping[str, ContextSource]
    receipt: Mapping[str, Any]

    def __post_init__(self) -> None:
        asset = str(self.asset).upper()
        if asset not in ASSET_CONTEXT_SERIES:
            raise C.EntryV2Refusal(f"unsupported context asset: {self.asset}")
        object.__setattr__(self, "asset", asset)
        index = {
            series_id: _tensor_source(self.sources.get(series_id))
            for series_id in ASSET_CONTEXT_SERIES[asset]
        }
        object.__setattr__(self, "_tensor_sources", MappingProxyType(index))

    def pack(
        self,
        trading_day: int,
        decision_ts_ns: int,
        *,
        permit: C.FinalExamPermit | None = None,
    ) -> ContextPack:
        return build_context_pack(
            self.asset,
            decision_ts_ns,
            self.sources,
            trading_day=trading_day,
            permit=permit,
        )

    def tensor(
        self,
        trading_day: int,
        decision_ts_ns: int,
        *,
        permit: C.FinalExamPermit | None = None,
    ) -> ContextTensor:
        values, type_ids, valid = self.tensor_batch(
            trading_day, (decision_ts_ns,), permit=permit
        )
        tensor = ContextTensor(
            values[0], type_ids, valid[0], tuple(ASSET_CONTEXT_SERIES[self.asset])
        )
        tensor.validate()
        return tensor

    def tensor_batch(
        self,
        trading_day: int,
        decision_ts_ns: Iterable[int],
        *,
        permit: C.FinalExamPermit | None = None,
    ) -> tuple[Tensor, Tensor, Tensor]:
        """Vectorize strict-prior last-64 context for one candidate batch."""
        C.guard_date(int(trading_day), permit)
        decisions = np.asarray(tuple(int(value) for value in decision_ts_ns),
                               dtype=np.int64)
        if decisions.ndim != 1 or not len(decisions) or np.any(decisions <= 0):
            raise C.EntryV2Refusal("context batch needs positive decision timestamps")
        series_ids = tuple(ASSET_CONTEXT_SERIES[self.asset])
        output = np.zeros(
            (len(decisions), len(series_ids), HISTORY_LENGTH,
             CONTEXT_TENSOR_WIDTH),
            dtype=np.float32,
        )
        valid = np.zeros(output.shape[:-1], dtype=np.bool_)
        offsets = np.arange(-HISTORY_LENGTH, 0, dtype=np.int64)
        for series_index, series_id in enumerate(series_ids):
            source = self._tensor_sources[series_id]
            if source is None:
                continue
            end = np.searchsorted(
                source.availability_ts_ns, decisions, side="left"
            ).astype(np.int64, copy=False)
            indexes = end[:, None] + offsets[None, :]
            present = indexes >= 0
            safe = np.maximum(indexes, 0)
            present3 = present[..., None]
            output[:, series_index, :, VALUE_OFFSET:DELTA_OFFSET] = np.where(
                present3, source.values[safe], 0.0
            )
            output[:, series_index, :, DELTA_OFFSET:LOG_AGE_OFFSET] = np.where(
                present3, source.deltas[safe], 0.0
            )
            age_ns = np.where(
                present,
                decisions[:, None] - source.availability_ts_ns[safe],
                0,
            )
            ages = np.log1p(age_ns / NS).astype(np.float32, copy=False)
            output[:, series_index, :, LOG_AGE_OFFSET] = np.where(
                present, ages, 0.0
            )
            output[:, series_index, :,
                   VALUE_PRESENT_OFFSET:DELTA_PRESENT_OFFSET] = np.where(
                present3, source.value_present[safe], 0.0
            )
            output[:, series_index, :, DELTA_PRESENT_OFFSET:] = np.where(
                present3, source.delta_present[safe], 0.0
            )
            valid[:, series_index, :] = present
        values_tensor = torch.from_numpy(output)
        valid_tensor = torch.from_numpy(valid)
        type_ids = torch.tensor(
            [CONTEXT_TYPE_ID[series_id] for series_id in series_ids],
            dtype=torch.int64,
        )
        if not bool(torch.isfinite(values_tensor).all()):
            raise C.EntryV2Refusal("context batch contains a non-finite value")
        return values_tensor, type_ids, valid_tensor


def tabular_context_summary(
    repository: CausalContextRepository,
    trading_day: int,
    decision_ts_ns: Iterable[int],
    *,
    permit: C.FinalExamPermit | None = None,
) -> np.ndarray:
    """Return the fixed-schema strict-prior context summary for CatBoost.

    Asset-specific series are scattered into the frozen global series roster,
    so SI/HG/NKD always expose the same ordered columns.  Every channel uses
    the same last/mean/std/min/max/coverage contract as the existing classical
    control.  Missing and deliberately masked revised-vintage sources remain
    typed zero with zero coverage; this function never opens another source.
    """

    timestamps = tuple(int(value) for value in decision_ts_ns)
    values, type_ids, valid = repository.tensor_batch(
        int(trading_day), timestamps, permit=permit)
    values = values.detach().cpu().to(torch.float64)
    valid = valid.detach().cpu().to(torch.bool)
    type_ids = type_ids.detach().cpu().to(torch.int64)
    rows, series, history, width = values.shape
    if (valid.shape != values.shape[:-1]
            or type_ids.shape != (series,)
            or width != CONTEXT_TENSOR_WIDTH
            or history != HISTORY_LENGTH):
        raise C.EntryV2Refusal(
            "tabular context summary received misaligned tensors")
    slots = len(CONTEXT_TYPE_ID)
    if any(int(item) < 0 or int(item) >= slots for item in type_ids):
        raise C.EntryV2Refusal(
            "tabular context type id is outside the frozen roster")

    stats = torch.zeros(
        (rows, slots, width * len(TABULAR_CONTEXT_STATISTICS) + 1),
        dtype=torch.float64,
    )
    positions = torch.arange(history, dtype=torch.int64)[None, :]
    row_index = torch.arange(rows, dtype=torch.int64)
    for series_index, type_id_tensor in enumerate(type_ids):
        type_id = int(type_id_tensor)
        mask = valid[:, series_index, :]
        x = values[:, series_index, :, :]
        expanded = mask[..., None]
        count = mask.sum(dim=1).to(torch.float64)
        denom = count.clamp_min(1.0)[:, None]
        safe = torch.where(expanded, x, torch.zeros_like(x))
        mean = safe.sum(dim=1) / denom
        variance = torch.where(
            expanded, (x - mean[:, None, :]).square(),
            torch.zeros_like(x)).sum(dim=1) / denom
        high = torch.where(
            expanded, x, torch.full_like(x, -torch.inf)).amax(dim=1)
        low = torch.where(
            expanded, x, torch.full_like(x, torch.inf)).amin(dim=1)
        present = count > 0
        high = torch.where(present[:, None], high, torch.zeros_like(high))
        low = torch.where(present[:, None], low, torch.zeros_like(low))
        last_position = torch.where(mask, positions, -1).amax(dim=1)
        last = torch.zeros((rows, width), dtype=torch.float64)
        if bool(present.any()):
            last[present] = x[row_index[present], last_position[present]]
        stats[:, type_id, :] = torch.cat((
            last, mean, variance.sqrt(), low, high,
            (count / history)[:, None],
        ), dim=1)
    result = stats.flatten(1)
    if (result.shape != (rows, len(TABULAR_CONTEXT_FEATURE_NAMES))
            or not bool(torch.isfinite(result).all())):
        raise C.EntryV2Refusal(
            "tabular context summary is non-finite or has schema drift")
    return result.numpy().astype(np.float32, copy=False)


def load_context_repository(
    asset: str,
    access_trading_day: int,
    *,
    permit: C.FinalExamPermit | None = None,
) -> CausalContextRepository:
    """Load one asset repository after the wall fires, never before it."""
    # This is intentionally the first executable read guard.  In particular,
    # LAG_TABLE and every value source remain unopened on refusal.
    C.guard_date(int(access_trading_day), permit)
    asset = str(asset).upper()
    if asset not in ASSET_CONTEXT_SERIES:
        raise C.EntryV2Refusal(f"unsupported context asset: {asset}")
    end_d8_exclusive = (
        C.SEALED_START_D8 if permit is not None else C.HOLDOUT_START_D8
    )
    availability = _availability_module()
    rows = availability.load_lag_table(str(LAG_TABLE))
    index = {row["series_id"]: row for row in rows}
    roster = tuple(ASSET_CONTEXT_SERIES[asset])
    missing = [series_id for series_id in roster if series_id not in index]
    if missing:
        raise C.EntryV2Refusal(f"context roster absent from lag table: {missing}")

    sources: dict[str, ContextSource] = {}
    receipt_rows: list[dict[str, Any]] = []
    for series_id in roster:
        row = index[series_id]
        try:
            vintage = VintageClass((row.get("vintage_class") or "").strip())
        except ValueError as exc:
            raise C.EntryV2Refusal(
                f"{series_id} has no valid declared vintage class"
            ) from exc
        if vintage is VintageClass.REVISED_VALUE:
            # Poison firewall: latest-vintage value files are never opened.
            loaded = _LoadedSeries((), (), status="REVISED_VALUE_FILE_NOT_OPENED")
        elif vintage is VintageClass.FIRST_PRINT:
            loaded = _first_print(row, end_d8_exclusive)
        elif vintage is VintageClass.SCHEDULE:
            loaded = _schedule(row, end_d8_exclusive)
        else:  # pragma: no cover - enum exhaustiveness
            raise C.EntryV2Refusal(f"unhandled vintage class: {vintage}")
        source = ContextSource(series_id, vintage, loaded.observations)
        sources[series_id] = source
        widths = sorted({len(obs.values) for obs in loaded.observations})
        receipt_rows.append({
            "series_id": series_id,
            "vintage_class": vintage.value,
            "declared_file": row["file"],
            "declared_avail_rule": row["avail_rule"],
            "lag_declaration_sha256": C.object_sha256(dict(sorted(row.items()))),
            "consumed_paths": list(loaded.paths),
            "consumed_observation_count": len(loaded.observations),
            "consumed_observations_sha256": _receipt_observations(
                loaded.observations
            ),
            "value_widths": widths,
            "refused_date_count": loaded.refused_dates,
            "unproved_row_count": loaded.unproved_rows,
            "status": loaded.status,
        })

    payload: dict[str, Any] = {
        "schema": "entry-v2-context-source-receipt-v1",
        "asset": asset,
        "access_trading_day": int(access_trading_day),
        "source_end_exclusive_d8": end_d8_exclusive,
        "lag_table": str(LAG_TABLE),
        "lag_table_sha256": C.file_sha256(LAG_TABLE),
        "availability_code_sha256": C.file_sha256(PORT_M2_AVAILABILITY),
        "adapter_code_sha256": C.file_sha256(Path(__file__)),
        "packer_code_sha256": C.file_sha256(
            C.REPO_ROOT / "engine" / "entry_v2" / "context_pack.py"
        ),
        "roster": list(roster),
        "global_type_ids": dict(CONTEXT_TYPE_ID),
        "tensor_feature_names": list(CONTEXT_FEATURE_NAMES),
        "series": receipt_rows,
        "masked_latest_vintage_files_opened": False,
    }
    payload["receipt_sha256"] = C.object_sha256(payload)
    return CausalContextRepository(
        asset,
        MappingProxyType(sources),
        MappingProxyType(payload),
    )


def write_context_receipt(
    repository: CausalContextRepository, path: str | Path
) -> str:
    return C.atomic_json(path, dict(repository.receipt))
