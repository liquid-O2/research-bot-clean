#!/usr/bin/env python3
"""Build the mill's context-source cache: three day-level tables, one manifest.

The mill's causal license (`.audit/briefs/mill-side-resolution.md`, "Context
sources license") admits exactly three context sources, all day-level:

1. **priors**   the ``QRE2G1PRIOR2`` row per locked asset-day, copied verbatim.
2. **forecast** the vol service's daily catboost forecast routed by the killed
   read's own functions, plus that day's intraday catboost heads.
3. **daily_levels** a one-time session OHLC summary per locked asset-day.

Only ``daily_levels`` touches raw bytes.  It opens the 582 locked event packs
(HOLD included, per the license) and writes ONE row per asset-day: session
open/high/low/close mid2, the session range, and per-phase closes.  No intraday
series, no per-cell data, no candidate data, no outcome is written, ever.
``context.py`` then refuses to serve any levels row dated on or after the
requesting day, so a same-day OHLC can only ever become a LATER day's feature.

Reads, and nothing else:
  * ``artifacts/cache/port/entry_v2/g1/priors/{asset}.tsv``
  * ``artifacts/runs/e6_vol_forecasts_v2/vol_service_forecasts.tsv``
  * ``artifacts/cache/port/entry_v2/events/{asset}/{d8}.qre2``
  * ``artifacts/cache/port/entry_v2/g1/candidates/{asset}/{d8}.tsv``, parsed for
    the three phase-window columns in ``CANDIDATE_LICENSED_COLS`` and no other.

Never opens ``g1/teacher``, ``g1/late``, ``g1/receipts``, any 2021 byte, or any
2025 byte; the locked day list is the 582 in ``.audit/mill-split.json`` and the
event pack's own ``guard_date`` refuses out-of-era basenames independently.

Trusted-plane law, mirroring ``tools/mill/build_substrate.py``: the pack opens
with ``EventPack(path, verify_hash=True)`` and the trusted-economic rows come
from ``engine.entry_v2.diagnostic_event_truth.build_event_truth_columns``, whose
default plane takes, per phase interval, the strictest registered sane ceiling.
The substrate reaches that plane through ``_index_by_quality`` over CLEAR
candidates, which needs the candidates' ``sane_ceiling_usd``.  This builder is
not licensed to parse that column, so it takes the identical ceiling from the
day's own priors row (``p{phase}_sane_ceiling_usd``), which is where the
candidate writer sourced it.  Same plane, fewer candidate fields read.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.entry_v2.confirmation_types import NANOS_PER_SECOND
from engine.entry_v2.corpus_units import ASSET_MULTIPLIER
from engine.entry_v2.diagnostic_event_truth import build_event_truth_columns
from engine.entry_v2.diagnostic_types import UNITS_PER_USD
from engine.entry_v2.event_pack import EVENT_DTYPE, EventPack

from tools.mill.context import (
    ContextStore, FORECAST_NAME, FORECAST_SCHEMA, LEVELS_NAME, LEVELS_SCHEMA,
    MANIFEST_NAME, MUTANT_ENV, MUTANT_SERVES_TODAY, PRIORS_NAME, PRIORS_SCHEMA,
    served_levels_days,
)

SPLIT_PATH = ROOT / ".audit/mill-split.json"
PRIORS_ROOT = ROOT / "artifacts/cache/port/entry_v2/g1/priors"
CANDIDATE_ROOT = ROOT / "artifacts/cache/port/entry_v2/g1/candidates"
EVENT_ROOT = ROOT / "artifacts/cache/port/entry_v2/events"
OUT_ROOT = ROOT / "artifacts/cache/mill_context"
KILLED_READ_PATH = ROOT / ".audit/score_threshold_2022_2024_read.py"
MANIFEST_SCHEMA = "QRE2MILLCTXMANIFEST1"
ASSETS = ("HG", "NKD", "SI")
PHASES = (0, 1, 2)
DEFAULT_WORKERS = 10

PRIOR_HEADER_STAMP = "QRE2G1PRIOR2"
PRIOR_COLUMNS = (
    "asset", "d8", "atr14_present", "atr14_prev_usd",
    "p0_spread_present", "p0_completed_sessions", "p0_observations",
    "p0_median_spread_usd", "p0_sane_ceiling_usd",
    "p1_spread_present", "p1_completed_sessions", "p1_observations",
    "p1_median_spread_usd", "p1_sane_ceiling_usd",
    "p2_spread_present", "p2_completed_sessions", "p2_observations",
    "p2_median_spread_usd", "p2_sane_ceiling_usd",
)

CANDIDATE_HEADER_STAMP = "QRE2G1CAND2"
# The only candidate columns this builder may parse.  Phase windows and the
# window's own phase ordinal; no price, cost, status, teacher, or outcome field.
CANDIDATE_LICENSED_COLS = ("phase", "phase_open_utc", "phase_close_utc")
CANDIDATE_FORBIDDEN_COLS = frozenset((
    "status", "ready", "cash", "cert_close_usd", "exit_ts_ns", "wall_hit",
    "mfe_usd", "mae_usd", "outcome", "entry_bid_px", "entry_ask_px",
    "entry_mid2", "entry_spread_usd", "frozen_cost_usd", "sane_ceiling_usd",
    "compliance_status", "decision_ts_ns", "side", "atr14_prev_usd",
))

LEVELS_COLUMNS = (
    "asset", "d8", "plane_source", "n_trusted_rows", "n_phase_windows",
    "session_open_ts_ns", "session_close_ts_ns",
    "session_open_mid2", "session_high_mid2", "session_low_mid2",
    "session_close_mid2", "session_range_mid2",
    "p0_close_mid2", "p1_close_mid2", "p2_close_mid2", "phase_windows",
)
BLANK = ""


class ContextStop(RuntimeError):
    """A source byte, schema, or invariant did not hold.  Build stops."""


# --------------------------------------------------------------------------
# killed-read routing, imported exactly as the ceiling scorer imports it
# --------------------------------------------------------------------------

def _load_killed_module():
    """Mirror ``.audit/score_threshold_2022_2024_ceiling.py`` lines 57-89."""

    spec = importlib.util.spec_from_file_location(
        KILLED_READ_PATH.stem, KILLED_READ_PATH)
    if spec is None or spec.loader is None:
        raise ContextStop(f"cannot import killed-read module from {KILLED_READ_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[KILLED_READ_PATH.stem] = module
    spec.loader.exec_module(module)
    return module


_killed = _load_killed_module()
FORECAST = _killed.FORECAST
WINDOW_START = _killed.WINDOW_START
WINDOW_END = _killed.WINDOW_END
ForecastRow = _killed.ForecastRow
RoutedDay = _killed.RoutedDay
JoinUnavailable = _killed.JoinUnavailable
load_window_forecast_rows = _killed.load_window_forecast_rows
route_catboost_daily = _killed.route_catboost_daily
select_expanding_median = _killed.select_expanding_median
refused_days_without_daily = _killed.refused_days_without_daily


# --------------------------------------------------------------------------
# shared helpers
# --------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def write_table(path: Path, schema: str, columns: Sequence[str],
                rows: Sequence[Sequence[object]]) -> dict[str, object]:
    """The one writer.  Real builds and the selftest fixtures share it."""

    width = len(columns)
    lines = [f"# {schema} rows={len(rows)}", "\t".join(columns)]
    for row in rows:
        if len(row) != width:
            raise ContextStop(
                f"{path.name} row has {len(row)} fields, header has {width}")
        fields = ["" if value is None else str(value) for value in row]
        for field in fields:
            if "\t" in field or "\n" in field:
                raise ContextStop(f"{path.name} field carries a TSV delimiter")
        lines.append("\t".join(fields))
    text = "\n".join(lines) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w", dir=str(path.parent), delete=False, suffix=".part")
    try:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    finally:
        handle.close()
    os.replace(handle.name, path)
    return {"path": path.name, "rows": len(rows), "sha256": sha256_text(text),
            "bytes": len(text.encode())}


def load_split(path: Path = SPLIT_PATH) -> tuple[tuple[tuple[str, int], ...], dict[str, object]]:
    """The frozen 582 locked asset-days, explore and hold, ascending."""

    raw = path.read_bytes()
    payload = json.loads(raw)
    if payload.get("schema") != "QRE2MILLSPLIT1":
        raise ContextStop(f"{path} is not a QRE2MILLSPLIT1 split")
    locked: list[tuple[str, int]] = []
    for group in ("explore", "hold"):
        block = payload.get(group)
        if not isinstance(block, dict):
            raise ContextStop(f"{path} lacks a {group} block")
        for asset in ASSETS:
            for d8 in block.get(asset, ()):
                locked.append((asset, int(d8)))
    locked.sort()
    if len(set(locked)) != len(locked):
        raise ContextStop("split lists an asset-day twice")
    meta = {
        "split_sha256": str(payload.get("split_sha256", "")),
        "split_file_sha256": hashlib.sha256(raw).hexdigest(),
        "counts": payload.get("counts"),
        "locked_asset_days": len(locked),
    }
    return tuple(locked), meta


def _era_guard(d8: int) -> None:
    year = d8 // 10000
    if year < 2022 or year > 2024:
        raise ContextStop(f"locked day {d8} sits outside the 2022-2024 era")


# --------------------------------------------------------------------------
# stage 1: priors
# --------------------------------------------------------------------------

def read_prior_rows(asset: str) -> dict[int, tuple[str, ...]]:
    """Every ``QRE2G1PRIOR2`` row for one asset, keyed by d8, fields verbatim."""

    path = PRIORS_ROOT / f"{asset}.tsv"
    if not path.is_file():
        raise ContextStop(f"priors store missing: {path}")
    lines = path.read_text().split("\n")
    if not lines or not lines[0].startswith(f"# {PRIOR_HEADER_STAMP} "):
        raise ContextStop(f"{path} is not a {PRIOR_HEADER_STAMP} store")
    header = tuple(lines[1].split("\t"))
    if header != PRIOR_COLUMNS:
        raise ContextStop(f"{path} header differs from the pinned prior schema")
    rows: dict[int, tuple[str, ...]] = {}
    for line in lines[2:]:
        if not line:
            continue
        fields = tuple(line.split("\t"))
        if len(fields) != len(PRIOR_COLUMNS):
            raise ContextStop(f"{path} row width differs from the prior schema")
        if fields[0] != asset:
            raise ContextStop(f"{path} carries a row for asset {fields[0]!r}")
        rows[int(fields[1])] = fields
    return rows


def phase_ceiling_units(row: Sequence[str]) -> dict[int, int]:
    """Per-phase sane ceiling in price units, from one verbatim priors row."""

    fields = dict(zip(PRIOR_COLUMNS, row))
    ceilings: dict[int, int] = {}
    for phase in PHASES:
        raw = fields[f"p{phase}_sane_ceiling_usd"]
        try:
            usd = Decimal(raw)
        except InvalidOperation as exc:
            raise ContextStop(f"prior sane ceiling {raw!r} is not a decimal") from exc
        units = usd * UNITS_PER_USD
        if units != units.to_integral_value() or units <= 0:
            raise ContextStop(f"prior sane ceiling {raw!r} is not a positive integer")
        ceilings[phase] = int(units)
    return ceilings


def build_priors(locked: Sequence[tuple[str, int]], out_root: Path) -> dict[str, object]:
    started = time.monotonic()
    stores = {asset: read_prior_rows(asset) for asset in ASSETS}
    rows: list[Sequence[object]] = []
    for asset, d8 in locked:
        _era_guard(d8)
        row = stores[asset].get(d8)
        if row is None:
            raise ContextStop(f"priors store has no row for {asset}/{d8}")
        rows.append(row)
    written = write_table(out_root / PRIORS_NAME, PRIORS_SCHEMA, PRIOR_COLUMNS, rows)
    written["wall_seconds"] = round(time.monotonic() - started, 3)
    written["sources"] = {
        f"priors/{asset}.tsv": sha256_file(PRIORS_ROOT / f"{asset}.tsv")
        for asset in ASSETS
    }
    return written


# --------------------------------------------------------------------------
# stage 2: forecast
# --------------------------------------------------------------------------

def _best_row(group: Sequence[Mapping[str, str]]) -> Mapping[str, str]:
    """``route_catboost_daily``'s own comparator, applied to raw TSV rows."""

    return max(group, key=lambda row: (int(row["train_sessions_n"]),
                                       -int(row["outer_fold"])))


def load_head_table(path: Path) -> tuple[dict[str, dict[str, Mapping[str, str]]], int]:
    """Route every ``(head, arm)`` in the window by the daily routing rule."""

    grouped: dict[tuple[str, str], dict[str, list[Mapping[str, str]]]] = {}
    n_read = 0
    import csv

    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        required = {"head", "arm", "outer_fold", "day", "forecast_variance",
                    "train_sessions_n", "gate_pass"}
        missing = required.difference(reader.fieldnames or ())
        if missing:
            raise ContextStop(f"{path} missing columns {sorted(missing)}")
        for raw in reader:
            n_read += 1
            day = str(raw["day"])
            if day < WINDOW_START or day > WINDOW_END:
                continue
            grouped.setdefault((str(raw["head"]), str(raw["arm"])), {}).setdefault(
                day, []).append(dict(raw))
    routed: dict[str, dict[str, Mapping[str, str]]] = {}
    for (head, arm), by_day in grouped.items():
        if arm != "catboost":
            continue
        routed[head] = {day: _best_row(rows) for day, rows in by_day.items()}
    return routed, n_read


def build_forecast(out_root: Path) -> dict[str, object]:
    started = time.monotonic()
    if not FORECAST.is_file():
        raise ContextStop(f"forecast TSV missing: {FORECAST}")
    # The killed read's own three calls, in its own order.
    forecast_rows, window_days, n_rows_read = load_window_forecast_rows(FORECAST)
    routed, _empty = route_catboost_daily(forecast_rows)
    selected_flags = select_expanding_median(routed)
    refused = refused_days_without_daily(window_days, [row.day for row in routed])
    if len(selected_flags) != len(routed):
        raise ContextStop("expanding-median flags do not align with routed days")

    heads, head_rows_read = load_head_table(FORECAST)
    if head_rows_read != n_rows_read:
        raise ContextStop("forecast row counts differ between the two passes")
    daily = heads.get("daily")
    if daily is None:
        raise ContextStop("forecast TSV carries no daily catboost arm")
    # Prove the re-derivation agrees with the killed routing on every day.
    for day_row in routed:
        mine = daily.get(day_row.day)
        if mine is None:
            raise ContextStop(f"re-derived routing lost routed day {day_row.day}")
        if (int(mine["outer_fold"]) != day_row.outer_fold
                or int(mine["train_sessions_n"]) != day_row.train_sessions_n
                or float(mine["forecast_variance"]) != day_row.forecast_variance):
            raise ContextStop(f"re-derived routing differs on {day_row.day}")

    intraday = tuple(sorted(
        (head for head in heads if head.startswith("intraday_")),
        key=lambda name: int(name.split("_")[1])))
    columns = ("day", "d8", "outer_fold", "train_sessions_n",
               "forecast_variance", "selected", "gate_pass",
               *(f"{head}_catboost" for head in intraday))
    rows: list[Sequence[object]] = []
    for day_row, flag in zip(routed, selected_flags):
        source = daily[day_row.day]
        values: list[object] = [
            day_row.day, day_row.d8, day_row.outer_fold, day_row.train_sessions_n,
            repr(day_row.forecast_variance), int(bool(flag)),
            str(source["gate_pass"]),
        ]
        for head in intraday:
            hit = heads[head].get(day_row.day)
            values.append(BLANK if hit is None else repr(float(hit["forecast_variance"])))
        rows.append(values)
    written = write_table(out_root / FORECAST_NAME, FORECAST_SCHEMA, columns, rows)
    written["wall_seconds"] = round(time.monotonic() - started, 3)
    written["n_rows_read"] = n_rows_read
    written["routed"] = len(routed)
    written["selected"] = int(sum(1 for flag in selected_flags if flag))
    written["window_days"] = len(window_days)
    written["refused_no_forecast"] = len(refused)
    written["intraday_catboost_heads"] = list(intraday)
    written["heads_without_catboost_arm"] = sorted(
        {head for head in _all_heads(FORECAST) if head not in heads})
    written["sources"] = {"vol_service_forecasts.tsv": sha256_file(FORECAST)}
    return written


def _all_heads(path: Path) -> set[str]:
    import csv

    found: set[str] = set()
    with path.open(newline="") as handle:
        for raw in csv.DictReader(handle, delimiter="\t"):
            found.add(str(raw["head"]))
    return found


# --------------------------------------------------------------------------
# stage 3: daily levels
# --------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class PhaseBinding:
    """The three attributes ``build_event_truth_columns`` reads off a binding."""

    asset: str
    phase: int
    phase_open_ts_ns: int
    phase_close_ts_ns: int
    sane_ceiling_units: int
    multiplier: int

    @property
    def truth_quality_key(self) -> tuple[int, int, int, int]:
        return (self.phase_open_ts_ns, self.phase_close_ts_ns,
                self.sane_ceiling_units, self.multiplier)


def read_phase_windows(asset: str, d8: int) -> tuple[tuple[int, int, int], ...]:
    """Distinct ``(phase, open_ns, close_ns)`` windows for one locked day.

    Parses ``CANDIDATE_LICENSED_COLS`` and refuses if any other column is
    touched.  Multi-instance phases stay distinct windows, the B4 law.
    """

    path = CANDIDATE_ROOT / asset / f"{d8}.tsv"
    if not path.is_file():
        raise ContextStop(f"candidates file missing: {path}")
    leaked = CANDIDATE_FORBIDDEN_COLS.intersection(CANDIDATE_LICENSED_COLS)
    if leaked:
        raise ContextStop(f"candidate usecols reach forbidden columns {sorted(leaked)}")
    with path.open() as handle:
        stamp = handle.readline()
        if not stamp.startswith(f"# {CANDIDATE_HEADER_STAMP} "):
            raise ContextStop(f"{path} is not a {CANDIDATE_HEADER_STAMP} table")
        header = handle.readline().rstrip("\n").split("\t")
        try:
            picks = {name: header.index(name) for name in CANDIDATE_LICENSED_COLS}
        except ValueError as exc:
            raise ContextStop(f"{path} lacks a licensed phase column") from exc
        found: set[tuple[int, int, int]] = set()
        for line in handle:
            if not line.strip():
                continue
            fields = line.rstrip("\n").split("\t")
            phase = int(fields[picks["phase"]])
            if phase not in PHASES:
                raise ContextStop(f"{path} carries phase {phase} outside {PHASES}")
            found.add((
                phase,
                int(fields[picks["phase_open_utc"]]) * NANOS_PER_SECOND,
                int(fields[picks["phase_close_utc"]]) * NANOS_PER_SECOND,
            ))
    return tuple(sorted(found, key=lambda item: (item[1], item[2], item[0])))


def compute_levels(asset: str, raw_rows: np.ndarray,
                   bindings: Sequence[PhaseBinding]) -> dict[str, object]:
    """The one extraction path: real packs and the selftest fixture share it.

    Returns day-level values only.  Nothing finer than the session summary and
    the per-phase closes leaves this function.
    """

    if raw_rows.dtype != EVENT_DTYPE:
        raise ContextStop("levels extraction needs EVENT_DTYPE pack rows")
    if not bindings:
        raise ContextStop("levels extraction needs at least one phase binding")
    truth = build_event_truth_columns(raw_rows, asset, bindings)
    economic = np.asarray(truth["trusted_economic"], bool)
    keep = np.flatnonzero(economic)
    if not len(keep):
        raise ContextStop(f"no trusted-economic row survives for {asset}")
    ts = np.asarray(truth["ts_recv_ns"], np.uint64).astype(np.int64)[keep]
    mid2 = np.asarray(truth["mid2"], np.int64)[keep]
    if np.any(np.diff(ts) < 0):
        raise ContextStop(f"trusted timestamps are not ascending for {asset}")
    high = int(mid2.max())
    low = int(mid2.min())
    values: dict[str, object] = {
        "n_trusted_rows": int(len(keep)),
        "session_open_ts_ns": int(ts[0]),
        "session_close_ts_ns": int(ts[-1]),
        "session_open_mid2": int(mid2[0]),
        "session_high_mid2": high,
        "session_low_mid2": low,
        "session_close_mid2": int(mid2[-1]),
        "session_range_mid2": high - low,
    }
    # Per-phase close: the last trusted mid STRICTLY before the phase close.
    # A phase with several instances reports its first instance; the full
    # window table travels in ``phase_windows`` so the choice stays auditable.
    seen: set[int] = set()
    for binding in sorted(bindings, key=lambda item: (item.phase_open_ts_ns,)):
        if binding.phase not in PHASES or binding.phase in seen:
            continue
        seen.add(binding.phase)
        stop = int(np.searchsorted(ts, binding.phase_close_ts_ns, side="left"))
        values[f"p{binding.phase}_close_mid2"] = (
            int(mid2[stop - 1]) if stop > 0 else BLANK)
    for phase in PHASES:
        values.setdefault(f"p{phase}_close_mid2", BLANK)
    return values


def bindings_for(asset: str, windows: Sequence[tuple[int, int, int]],
                 ceilings: Mapping[int, int], *,
                 session: tuple[int, int]) -> tuple[tuple[PhaseBinding, ...], str]:
    """Phase bindings from the day's windows, or the priors-only fallback."""

    multiplier = int(ASSET_MULTIPLIER[asset])
    if windows:
        return tuple(
            PhaseBinding(asset, phase, open_ns, close_ns, ceilings[phase], multiplier)
            for phase, open_ns, close_ns in windows
        ), "candidate_phase_windows"
    # No candidates that day: the sane-bounds law over the whole session with
    # the day's strictest prior sane ceiling.
    ceiling = min(ceilings[phase] for phase in PHASES)
    open_ns, close_ns = session
    return (PhaseBinding(asset, PHASES[0], open_ns, close_ns, ceiling, multiplier),), \
        "priors_session_window"


def build_one_levels(asset: str, d8: int, ceilings: Mapping[int, int]) -> dict[str, object]:
    _era_guard(d8)
    event_path = EVENT_ROOT / asset / f"{d8}.qre2"
    if not event_path.is_file():
        raise ContextStop(f"event pack missing: {event_path}")
    windows = read_phase_windows(asset, d8)
    with EventPack(event_path, verify_hash=True) as pack:
        if pack.header.asset != asset or pack.header.d8 != d8:
            raise ContextStop(f"event pack identity differs for {asset}/{d8}")
        pack_sha = str(pack.sidecar.get(
            "event_pack_sha256", pack.sidecar.get("output_sha256", "")))
        if len(pack_sha) != 64:
            raise ContextStop(f"event pack sidecar lacks a sha256 for {asset}/{d8}")
        bindings, plane_source = bindings_for(
            asset, windows, ceilings,
            session=(pack.header.open_ns, pack.header.close_ns))
        raw_rows = np.asarray(pack.rows)
        values = compute_levels(asset, raw_rows, bindings)
        event_rows = int(pack.header.n_events)
    spec = "|".join(f"{phase}:{open_ns}-{close_ns}"
                    for phase, open_ns, close_ns in windows)
    values.update({
        "asset": asset, "d8": d8, "plane_source": plane_source,
        "n_phase_windows": len(windows), "phase_windows": spec,
    })
    return {"row": values, "event_pack_sha256": pack_sha, "event_rows": event_rows}


def _levels_job(payload: tuple[str, int, dict[int, int]]) -> dict[str, object]:
    asset, d8, ceilings = payload
    return build_one_levels(asset, d8, ceilings)


def build_levels(locked: Sequence[tuple[str, int]], out_root: Path,
                 workers: int) -> dict[str, object]:
    started = time.monotonic()
    stores = {asset: read_prior_rows(asset) for asset in ASSETS}
    jobs: list[tuple[str, int, dict[int, int]]] = []
    for asset, d8 in locked:
        row = stores[asset].get(d8)
        if row is None:
            raise ContextStop(f"priors store has no ceiling row for {asset}/{d8}")
        jobs.append((asset, d8, phase_ceiling_units(row)))
    results: list[dict[str, object]] = []
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for result in pool.map(_levels_job, jobs):
                results.append(result)
    else:
        results = [_levels_job(job) for job in jobs]
    rows: list[Sequence[object]] = []
    pack_lines: list[str] = []
    event_rows = 0
    plane_sources: dict[str, int] = {}
    for (asset, d8, _), result in zip(jobs, results):
        values = result["row"]
        rows.append(tuple(values[name] for name in LEVELS_COLUMNS))
        pack_lines.append(f"{asset}\t{d8}\t{result['event_pack_sha256']}")
        event_rows += int(result["event_rows"])
        source = str(values["plane_source"])
        plane_sources[source] = plane_sources.get(source, 0) + 1
    written = write_table(out_root / LEVELS_NAME, LEVELS_SCHEMA, LEVELS_COLUMNS, rows)
    written["wall_seconds"] = round(time.monotonic() - started, 3)
    written["workers"] = workers
    written["event_rows_scanned"] = event_rows
    written["plane_sources"] = plane_sources
    written["sources"] = {
        "event_packs_digest": sha256_text("\n".join(pack_lines) + "\n"),
        "event_packs": len(pack_lines),
    }
    return written


# --------------------------------------------------------------------------
# manifest
# --------------------------------------------------------------------------

def write_manifest(out_root: Path, stages: Mapping[str, object],
                   split_meta: Mapping[str, object], wall_seconds: float) -> Path:
    path = out_root / MANIFEST_NAME
    payload: dict[str, object] = {}
    if path.is_file():
        try:
            existing = json.loads(path.read_text())
            if isinstance(existing, dict):
                payload = existing
        except (OSError, json.JSONDecodeError):
            payload = {}
    files = dict(payload.get("files") or {})
    sources = dict(payload.get("sources") or {})
    counts = dict(payload.get("row_counts") or {})
    stage_meta = dict(payload.get("stages") or {})
    for name, block in stages.items():
        block = dict(block)  # type: ignore[arg-type]
        file_name = str(block.pop("path"))
        counts[name] = block.pop("rows")
        files[file_name] = {"sha256": block.pop("sha256"), "bytes": block.pop("bytes")}
        sources.update(block.pop("sources", {}))
        stage_meta[name] = block
    payload.update({
        "schema": MANIFEST_SCHEMA,
        "row_counts": counts,
        "files": files,
        "sources": sources,
        "stages": stage_meta,
        "split_sha256": split_meta["split_sha256"],
        "split_file_sha256": split_meta["split_file_sha256"],
        "split_counts": split_meta["counts"],
        "locked_asset_days": split_meta["locked_asset_days"],
        "candidate_columns_read": list(CANDIDATE_LICENSED_COLS),
        "build_wall_seconds": round(float(wall_seconds), 3),
    })
    text = json.dumps(payload, indent=1, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


# --------------------------------------------------------------------------
# selftest: zero real bytes
# --------------------------------------------------------------------------

SELFTEST_ASSET = "HG"
SELFTEST_TICK = 500_000
SELFTEST_BASE_S = 1_600_000_000
SELFTEST_BASE_NS = SELFTEST_BASE_S * NANOS_PER_SECOND
SELFTEST_BID = 4_500_000_000
SELFTEST_STEPS = (0, 3, 7, 2, 5, 4, 9, 1, 6, 8, 20, 21)
SELFTEST_INSANE_ROW = 6
SELFTEST_CEILING_UNITS = int(Decimal("250") * UNITS_PER_USD)


def _selftest_rows() -> np.ndarray:
    """A synthetic pack-rows array.  Twelve seconds, one deliberate wide book."""

    n = len(SELFTEST_STEPS)
    rows = np.zeros(n, dtype=EVENT_DTYPE)
    rows["ts_recv_ns"] = (SELFTEST_BASE_NS
                          + np.arange(n, dtype=np.int64) * NANOS_PER_SECOND)
    rows["ts_event_ns"] = rows["ts_recv_ns"]
    bid = SELFTEST_BID + np.asarray(SELFTEST_STEPS, np.int64) * SELFTEST_TICK
    spread = np.full(n, SELFTEST_TICK, np.int64)
    spread[SELFTEST_INSANE_ROW] = 40 * SELFTEST_TICK  # over the 250 USD ceiling
    rows["bid_px"] = bid
    rows["ask_px"] = bid + spread
    rows["price"] = bid
    rows["size"] = 1
    rows["bid_sz"] = 1
    rows["ask_sz"] = 1
    rows["bid_ct"] = 1
    rows["ask_ct"] = 1
    rows["sequence"] = np.arange(n, dtype=np.uint32)
    return rows


def _selftest_bindings() -> tuple[PhaseBinding, ...]:
    multiplier = int(ASSET_MULTIPLIER[SELFTEST_ASSET])
    return (
        PhaseBinding(SELFTEST_ASSET, 0, SELFTEST_BASE_NS,
                     SELFTEST_BASE_NS + 4 * NANOS_PER_SECOND,
                     SELFTEST_CEILING_UNITS, multiplier),
        PhaseBinding(SELFTEST_ASSET, 1, SELFTEST_BASE_NS + 5 * NANOS_PER_SECOND,
                     SELFTEST_BASE_NS + 9 * NANOS_PER_SECOND,
                     SELFTEST_CEILING_UNITS, multiplier),
    )


def _mid2(step: int) -> int:
    return 2 * SELFTEST_BID + (2 * step + 1) * SELFTEST_TICK


def _case_levels_arithmetic(failures: list[str]) -> dict[str, object]:
    """Hand-computed expectation over the synthetic pack rows.

    Trusted set: rows 0-5 and 7-9.  Row 6 is over the sane ceiling; rows 10-11
    sit outside every phase window.  Steps kept: 0,3,7,2,5,4,1,6,8.
    """

    values = compute_levels(SELFTEST_ASSET, _selftest_rows(), _selftest_bindings())
    expected = {
        "n_trusted_rows": 9,
        "session_open_mid2": _mid2(0),
        "session_high_mid2": _mid2(8),
        "session_low_mid2": _mid2(0),
        "session_close_mid2": _mid2(8),
        "session_range_mid2": _mid2(8) - _mid2(0),
        "session_open_ts_ns": SELFTEST_BASE_NS,
        "session_close_ts_ns": SELFTEST_BASE_NS + 9 * NANOS_PER_SECOND,
        # phase 0 closes at +4s: last trusted row strictly before is row 3.
        "p0_close_mid2": _mid2(2),
        # phase 1 closes at +9s: row 9 sits AT the close, so row 8 is the last.
        "p1_close_mid2": _mid2(6),
        "p2_close_mid2": BLANK,
    }
    for name, want in expected.items():
        got = values.get(name)
        if got != want:
            failures.append(f"levels.{name} expected {want!r}, got {got!r}")
    return values


def _case_forecast_routing(failures: list[str]) -> None:
    """The ceiling scorer's routing shape, on a fixture: day one is unselected."""

    rows = (
        ForecastRow(day="2022-03-09", outer_fold=1, train_sessions_n=45,
                    forecast_variance=0.0002),
        ForecastRow(day="2022-03-09", outer_fold=2, train_sessions_n=60,
                    forecast_variance=0.0009),
        ForecastRow(day="2022-03-10", outer_fold=1, train_sessions_n=46,
                    forecast_variance=0.0001),
        ForecastRow(day="2022-03-11", outer_fold=1, train_sessions_n=47,
                    forecast_variance=0.0011),
    )
    routed, _empty = route_catboost_daily(rows)
    flags = select_expanding_median(routed)
    if len(routed) != 3 or len(flags) != 3:
        failures.append(f"forecast routed/flags shape {len(routed)}/{len(flags)}, want 3/3")
        return
    if routed[0].train_sessions_n != 60 or routed[0].outer_fold != 2:
        failures.append("forecast routing did not take the deepest train_sessions_n")
    if routed[0].d8 != 20220309:
        failures.append(f"forecast d8 conversion gave {routed[0].d8}")
    if flags[0] is not False:
        failures.append("first routed day must be unselected under expanding median")
    if flags[1] is not False:
        failures.append("day below the expanding median must be unselected")
    if flags[2] is not True:
        failures.append("day at or above the expanding median must be selected")
    # The same comparator, re-derived off raw rows, must agree.
    raw = [{"train_sessions_n": "45", "outer_fold": "1"},
           {"train_sessions_n": "60", "outer_fold": "2"}]
    if _best_row(raw)["train_sessions_n"] != "60":
        failures.append("_best_row comparator differs from route_catboost_daily")


def _case_strictly_prior(failures: list[str], levels_row: Mapping[str, object],
                         root: Path) -> None:
    """Fixtures through the real writer, then the real loader, then the guard."""

    priors: list[Sequence[object]] = []
    levels: list[Sequence[object]] = []
    days = (20220301, 20220302, 20220303)
    for day in days:
        fields = {name: "0" for name in PRIOR_COLUMNS}
        fields["asset"] = SELFTEST_ASSET
        fields["d8"] = str(day)
        fields["p0_sane_ceiling_usd"] = "250"
        priors.append(tuple(fields[name] for name in PRIOR_COLUMNS))
        values = dict(levels_row)
        values.update({"asset": SELFTEST_ASSET, "d8": day,
                       "plane_source": "selftest", "n_phase_windows": 2,
                       "phase_windows": "0:0-1|1:2-3"})
        levels.append(tuple(values[name] for name in LEVELS_COLUMNS))
    forecast_columns = ("day", "d8", "outer_fold", "train_sessions_n",
                        "forecast_variance", "selected", "gate_pass",
                        "intraday_30_catboost")
    forecast = [("2022-03-0%d" % (index + 1), day, 1, 40, "0.0001",
                 index % 2, "true", "0.0002")
                for index, day in enumerate(days)]
    write_table(root / PRIORS_NAME, PRIORS_SCHEMA, PRIOR_COLUMNS, priors)
    write_table(root / LEVELS_NAME, LEVELS_SCHEMA, LEVELS_COLUMNS, levels)
    write_table(root / FORECAST_NAME, FORECAST_SCHEMA, forecast_columns, forecast)

    store = ContextStore(root, lookback=5)
    context = store.context_for(SELFTEST_ASSET, 20220303)
    served = sorted(set(served_levels_days(context)))
    if any(day >= 20220303 for day in served):
        failures.append(
            f"strictly-prior guard leaked levels {served} at d8=20220303")
    if served != [20220301, 20220302]:
        failures.append(f"levels lookback served {served}, want [20220301, 20220302]")
    previous = context["levels_prev"]
    if previous is None or int(previous["d8"]) != 20220302:
        failures.append("levels_prev is not the most recent strictly-prior day")
    # Prior-derived sources are servable AT the requesting day.
    if context["priors"] is None or int(context["priors"]["d8"]) != 20220303:
        failures.append("priors row dated d8 must be served at d8")
    if context["forecast"] is None or int(context["forecast"]["d8"]) != 20220303:
        failures.append("forecast row dated d8 must be served at d8")
    # The earliest day has no prior levels at all.
    first = store.context_for(SELFTEST_ASSET, 20220301)
    if list(served_levels_days(first)):
        failures.append("the earliest day must be served no levels")


def selftest() -> int:
    failures: list[str] = []
    levels_row = _case_levels_arithmetic(failures)
    _case_forecast_routing(failures)
    with tempfile.TemporaryDirectory() as tmp:
        _case_strictly_prior(failures, levels_row, Path(tmp))
    mutant = os.environ.get(MUTANT_ENV, "")
    if failures:
        for line in failures:
            print(f"context_selftest_dead_case {line}")
        print(f"context_selftest_red cases={len(failures)} mutant={mutant or 'none'}")
        return 1
    if mutant:
        print(f"context_selftest_red mutant={mutant} did not flip any case")
        return 1
    print("context_selftest_ok")
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--stage", default="all",
                        choices=("priors", "forecast", "levels", "all"))
    parser.add_argument("--out", default=str(OUT_ROOT))
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if os.environ.get(MUTANT_ENV):
        raise ContextStop("refusing to build the cache under a mutant environment")

    started = time.monotonic()
    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    locked, split_meta = load_split()
    stages: dict[str, object] = {}
    if args.stage in ("priors", "all"):
        stages["priors"] = build_priors(locked, out_root)
    if args.stage in ("forecast", "all"):
        stages["forecast"] = build_forecast(out_root)
    if args.stage in ("levels", "all"):
        stages["levels"] = build_levels(locked, out_root, max(1, int(args.workers)))
    wall = time.monotonic() - started
    path = write_manifest(out_root, stages, split_meta, wall)
    for name, block in stages.items():
        print(f"{name} rows={block['rows']} "  # type: ignore[index]
              f"wall={block['wall_seconds']}s")  # type: ignore[index]
    print(f"manifest {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
