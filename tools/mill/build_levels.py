#!/usr/bin/env python3
"""Level-memory cache for the side-resolution mill (the memory/location plane).

One uncompressed npz + json sidecar per EXPLORE ``(asset, d8)`` under
``artifacts/cache/mill_levels/``.  Each cell of the day - a
``(phase, phase_open_ts_ns)`` formation window - becomes, for each of its two
fade sides and each band multiplier, a ``(bars, NLEV)`` matrix of the level
features defined by ``levels.py``, plus one per-cell int64 array holding the max
source stamp behind each bar.

The day is read as ONE TAPE.  Same-session memory is explicitly "earlier in the
same day across all phases", so the three phase windows of an asset-day are
concatenated in phase-open order and every count runs over that tape, while the
rows written stay per cell and per lattice bar so the join key never changes.

The bar lattice is the MILL's: ``sweep1`` samples the cell at
``lat[j] = phase_open + 60 j``, and ``build_flow.py`` numbers the same closes
from zero, so flow bar ``j-1`` closes at mill bar ``j`` and mill bar 0 has no
flow behind it.  That shift is ``build_flow_zones.to_lattice``, imported here so
there is one definition of it.

Sources: the sweep-1 prep cache (``artifacts/cache/mill/`` via
``S1.load_cache``), the minute flow cache (``artifacts/cache/mill_flow/`` via
``flow.load_flow``), and the context store (``artifacts/cache/mill_context/``
via ``context.ContextStore``).  EXPLORE days only, per ``.audit/mill-split.json``.

The prior session is the prior EXPLORE session, not the immediately prior locked
day: under the split law EXPLORE is every third locked day, and the mill's
licence binds HOLD intraday paths as unread by every rule, so a minute-grain
prior-session plane may not open the day before.  The day-level prior-day levels
(high, low, close) DO come from the immediately prior locked day through the
context store, which is licensed to serve day-level OHLC strictly prior.  Both
stamps are written per cell; nothing here opens a HOLD day's intraday path, a
teacher or late label, or any outcome column.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import context as CTX
import flow as FLOW
import flow_zones as FZ
import levels as LV
import sweep1 as S1
import sweep3 as S3
from build_flow_zones import to_lattice

SPLIT_PATH = ROOT / ".audit/mill-split.json"
REPORT_PATH = ROOT / ".audit/mill-levels-build.json"
ASSETS = ("HG", "NKD", "SI")
DEFAULT_WORKERS = 10
VERIFY_ROWS = 20
VERIFY_SEED = 20260827

SOURCE_NAMES = ("mill_prep", "mill_flow", "mill_context")
VALUE_METHOD = (
    "narrowest contiguous price window holding >= 0.70 of the prior EXPLORE "
    "session's minute volume; bins one tick2 wide over that session's mid2 "
    "range, widened only if the range would need more than 4096 of them; ties "
    "to the lowest window; volume from the mill_flow cache mapped onto the mill "
    "lattice by to_lattice")


class BuildStop(RuntimeError):
    pass


# --------------------------------------------------------------------------
# Per-worker state.  A process loads the prep cache and the context store once.
# --------------------------------------------------------------------------

_STATE: dict[str, object] = {}


def _state() -> dict[str, object]:
    if "records" not in _STATE:
        records, _days = S1.load_cache()
        store = CTX.ContextStore()
        index: dict[tuple[str, int], list[int]] = {}
        for position, rec in enumerate(records):
            index.setdefault((rec.asset, int(rec.d8)), []).append(position)
        _STATE["records"] = records
        _STATE["index"] = index
        _STATE["store"] = store
        _STATE["ctxs"] = S3.contexts_for(records, store)
        _STATE["explore"] = S1._explore_days(ASSETS)
    return _STATE


# --------------------------------------------------------------------------
# The day tape: all phases of one asset-day on one time axis.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class DayTape:
    """One asset-day's phases concatenated in phase-open order."""

    asset: str
    d8: int
    ts: np.ndarray          # (n,) lattice close stamp of each bar
    mid: np.ndarray         # (n,) bar mid, mid2 units
    delta: np.ndarray       # (n,) net signed aggressor flow, mill lattice
    vol: np.ndarray         # (n,) traded volume, mill lattice
    src_ts: np.ndarray      # (n,) last raw event stamp strictly before ts
    sourced: np.ndarray     # (n,) a trusted row exists strictly before ts
    starts: tuple[int, ...]  # tape offset of each cell, in the same order
    positions: tuple[int, ...]   # prep-cache record index of each cell

    @property
    def n(self) -> int:
        return int(len(self.ts))


def day_tape(records: Sequence[S1.CellRec], positions: Sequence[int],
             flow_day: Mapping[tuple[str, int], Mapping[str, np.ndarray]],
             asset: str, d8: int) -> DayTape:
    """Concatenate the day's cells; flow is shifted onto the mill lattice."""

    ordered = sorted(positions,
                     key=lambda p: int(records[p].phase_open_ts_ns))
    ts_parts, mid_parts, delta_parts, vol_parts, src_parts = [], [], [], [], []
    sourced_parts: list[np.ndarray] = []
    starts: list[int] = []
    offset = 0
    for position in ordered:
        rec = records[position]
        key = (rec.phase, int(rec.phase_open_ts_ns))
        if key not in flow_day:
            raise BuildStop(f"flow shard lacks cell {key} for {asset}/{d8}")
        arrays = flow_day[key]
        bars = int(rec.n)
        if len(arrays["vol"]) != bars:
            raise BuildStop(
                f"flow cell has {len(arrays['vol'])} bars, mill cell has {bars}")
        lat = np.asarray(rec.lat, np.int64)
        # The last raw row that could have formed this bar's mid.  A bar with
        # ``raw_cut == 0`` has NO trusted row before its close: ``mill.
        # bar_series`` clamps those lattice points to row 0, so their mid is a
        # quote from AFTER the bar.  They are marked unsourced here and dropped
        # from the plane, both as a reading bar and as a counted prior bar.
        cut = np.asarray(rec.raw_cut, np.int64)
        src = np.where(cut > 0, np.asarray(rec.raw_last, np.int64), lat - 1)
        sourced_parts.append(cut > 0)
        starts.append(offset)
        ts_parts.append(lat)
        mid_parts.append(np.asarray(rec.mid, np.float64))
        delta_parts.append(to_lattice(arrays["delta"], bars))
        vol_parts.append(to_lattice(arrays["vol"], bars))
        src_parts.append(src)
        offset += bars
    ts = np.concatenate(ts_parts)
    if len(ts) > 1 and not bool(np.all(np.diff(ts) > 0)):
        raise BuildStop(f"day tape is not strictly increasing: {asset}/{d8}")
    tape = DayTape(asset, int(d8), ts, np.concatenate(mid_parts),
                   np.concatenate(delta_parts), np.concatenate(vol_parts),
                   np.concatenate(src_parts), np.concatenate(sourced_parts),
                   tuple(starts), tuple(ordered))
    if bool(np.any(tape.src_ts >= tape.ts)):
        raise BuildStop(f"day tape source stamp is not prior: {asset}/{d8}")
    return tape


@dataclass(frozen=True, slots=True)
class DayLevels:
    """The day-level context one plane needs, every field strictly prior."""

    atr_mid2: float
    tick2: float
    prior_d8: int
    pd_high: float
    pd_low: float
    pd_close: float
    pd_src_ts_ns: int
    prev_sess_d8: int
    prev_sess_last_ts_ns: int
    value_lo: float
    value_hi: float


# --------------------------------------------------------------------------
# The plane.  One function over whole-day tapes; the builder slices per cell
# and the selftest calls it on synthetic tapes.
# --------------------------------------------------------------------------

def day_planes(tape: DayTape, prev: DayTape | None, day: DayLevels
               ) -> tuple[dict[tuple[int, int], np.ndarray], np.ndarray]:
    """Every ``(side, mult index)`` plane over the whole tape, plus src stamps.

    Each plane is ``(n, NLEV)`` float64 in ``LEVEL_FEATURES`` order.  Bar 0 of
    the day has no prior bar at all, so its memory and location columns are NaN
    rather than a zero that would read as "nothing ever happened here".
    """

    n = tape.n
    atr = float(day.atr_mid2)
    if not (atr > 0.0):
        raise BuildStop(f"atr_mid2 must be positive, got {atr}")
    mid = np.asarray(tape.mid, np.float64)
    bar_index = np.arange(n)
    ts = np.asarray(tape.ts, np.int64)
    sourced = np.asarray(tape.sourced, bool)
    # A prior-day or prior-session column is served only where that source's own
    # last stamp is strictly before this bar.  Nine EXPLORE asset-days carry a
    # prior session that closed about half an hour AFTER the current session
    # opened, and the context store's day-level guard cannot see that.
    prior_day_ok = ts > int(day.pd_src_ts_ns)
    prior_sess_ok = ((ts > int(day.prev_sess_last_ts_ns)) if prev is not None
                     else np.zeros(n, bool))
    low, high, seen = LV.prior_extremes(mid)
    span = high - low
    with np.errstate(invalid="ignore", divide="ignore"):
        rank = np.where(seen & (span > 0.0), (mid - low) / span, np.nan)
    location = {
        "dist_day_high_atr": np.where(seen, (high - mid) / atr, np.nan),
        "dist_day_low_atr": np.where(seen, (mid - low) / atr, np.nan),
        "range_rank": rank,
        "dist_pd_high_atr": (mid - day.pd_high) / atr,
        "dist_pd_low_atr": (mid - day.pd_low) / atr,
        "dist_pd_close_atr": (mid - day.pd_close) / atr,
        "dist_value_hi_atr": (mid - day.value_hi) / atr,
        "dist_value_lo_atr": (mid - day.value_lo) / atr,
    }

    # Source stamps: the bar's own last raw row, the newest SOURCED bar before
    # it (every memory and location column reads bars strictly before the
    # reading bar), and the two prior-session stamps where they are served.
    src = np.where(sourced, np.asarray(tape.src_ts, np.int64), -1)
    if n > 1:
        prior_close = np.full(n, -1, np.int64)
        prior_close[1:] = np.maximum.accumulate(np.where(sourced, ts, -1))[:-1]
        src = np.maximum(src, prior_close)
    if int(day.pd_src_ts_ns) > 0:
        src = np.where(prior_day_ok, np.maximum(src, int(day.pd_src_ts_ns)), src)
    if prev is not None and int(day.prev_sess_last_ts_ns) > 0:
        src = np.where(prior_sess_ok,
                       np.maximum(src, int(day.prev_sess_last_ts_ns)), src)
    if bool(np.any(src >= ts)):
        raise BuildStop(f"source stamp is not strictly prior: {tape.asset}/{tape.d8}")

    planes: dict[tuple[int, int], np.ndarray] = {}
    for mult_index, mult in enumerate(LV.BAND_MULTS):
        width = float(mult) * atr
        # Band membership depends on the width alone, so one matrix serves both
        # sides: |mid_j - mid_k| <= w, masked to j < k.
        band = LV.touch_matrix(mid, mid, width, prior_only=True)
        band &= sourced[None, :]
        touches = band.sum(axis=1).astype(np.float64)
        last_touch = np.where(band, bar_index[None, :], -1).max(axis=1)
        with np.errstate(invalid="ignore"):
            gap = np.where(
                last_touch >= 0,
                (np.asarray(tape.ts, np.float64)
                 - np.asarray(tape.ts, np.float64)[np.maximum(last_touch, 0)])
                / float(LV.NANOS_PER_MINUTE), np.nan)
        touch_delta = band.astype(np.float64) @ np.asarray(tape.delta, np.float64)
        if prev is not None:
            band_prev = LV.touch_matrix(mid, prev.mid, width, prior_only=False)
            band_prev &= np.asarray(prev.sourced, bool)[None, :]
            prev_touches = band_prev.sum(axis=1).astype(np.float64)
        else:
            band_prev = None
            prev_touches = np.full(n, np.nan)

        for side in LV.SIDES:
            hold_bar, broke_bar = LV.outcome_bars(mid, width, side)
            held = hold_bar < broke_bar
            broke = broke_bar < hold_bar
            # An outcome counts only from the bar its verdict lands on, so the
            # verdict bar itself must be strictly before the reading bar.
            resolved_hold = hold_bar[None, :] < bar_index[:, None]
            resolved_broke = broke_bar[None, :] < bar_index[:, None]
            held_count = (band & held[None, :] & resolved_hold).sum(axis=1)
            broke_count = (band & broke[None, :] & resolved_broke).sum(axis=1)
            if band_prev is not None:
                prev_hold, prev_break = LV.outcome_bars(prev.mid, width, side)
                prev_held = (band_prev & (prev_hold < prev_break)[None, :]
                             ).sum(axis=1).astype(np.float64)
                prev_broke = (band_prev & (prev_break < prev_hold)[None, :]
                              ).sum(axis=1).astype(np.float64)
            else:
                prev_held = np.full(n, np.nan)
                prev_broke = np.full(n, np.nan)

            plane = np.empty((n, LV.NLEV), np.float64)
            column = {
                "band_mult": np.full(n, float(mult)),
                "band_center_mid2": mid,
                "band_w_mid2": np.full(n, width),
                "sd_touches": touches,
                "sd_held": held_count.astype(np.float64),
                "sd_broke": broke_count.astype(np.float64),
                "sd_mins_since_touch": gap,
                "sd_touch_delta": touch_delta,
                "ps_touches": prev_touches,
                "ps_held": prev_held,
                "ps_broke": prev_broke,
                "near_pd_high": _near(mid, day.pd_high, width),
                "near_pd_low": _near(mid, day.pd_low, width),
                "near_pd_close": _near(mid, day.pd_close, width),
                "near_value_hi": _near(mid, day.value_hi, width),
                "near_value_lo": _near(mid, day.value_lo, width),
                **location,
            }
            for name, values in column.items():
                plane[:, LV.LEVEL_INDEX[name]] = values
            for name in LV.PRIOR_DAY_COLUMNS:
                plane[~prior_day_ok, LV.LEVEL_INDEX[name]] = np.nan
            for name in LV.PRIOR_SESSION_COLUMNS:
                plane[~prior_sess_ok, LV.LEVEL_INDEX[name]] = np.nan
            # Bar 0 of the day has no prior bar: its same-day memory is
            # undefined, not empty.
            for name in LV.SAME_DAY_COLUMNS:
                plane[0, LV.LEVEL_INDEX[name]] = np.nan
            # An unsourced bar has no price of its own to centre a band on.
            plane[~sourced, :] = np.nan
            planes[(side, mult_index)] = plane
    return planes, src


def _near(mid: np.ndarray, level: float, width: float) -> np.ndarray:
    """1.0 inside one band of ``level``, 0.0 outside, NaN when it is unknown."""

    if not np.isfinite(level):
        return np.full(len(mid), np.nan)
    return (np.abs(mid - float(level)) <= float(width)).astype(np.float64)


# --------------------------------------------------------------------------
# Shard build.
# --------------------------------------------------------------------------

def _prev_explore_day(explore: Sequence[int], d8: int) -> int:
    earlier = [int(day) for day in explore if int(day) < int(d8)]
    return max(earlier) if earlier else -1


def _tape_for(state: Mapping[str, object], asset: str, d8: int) -> DayTape:
    records = state["records"]
    positions = state["index"].get((asset, int(d8)), [])
    if not positions:
        raise BuildStop(f"prep cache has no cell for {asset}/{d8}")
    return day_tape(records, positions, FLOW.load_flow(asset, int(d8)),
                    asset, int(d8))


def day_context(state: Mapping[str, object], asset: str, d8: int,
                ctx: S3.Ctx, prev: DayTape | None, prev_d8: int) -> DayLevels:
    """The day-level context row plus the prior session's value edges."""

    payload = state["store"].context_for(asset, int(d8))
    row = payload.get("levels_prev")
    if row is None:
        raise BuildStop(f"context served no prior levels row for {asset}/{d8}")
    if int(row["d8"]) != int(ctx.prior_d8):
        raise BuildStop(
            f"levels row {row['d8']} differs from ctx prior {ctx.prior_d8}")
    tick2 = 2.0 * float(S1.ASSET_RAW_TICK[asset])
    area = (LV.value_area(prev.mid, prev.vol, tick2) if prev is not None
            else {"value_lo": float("nan"), "value_hi": float("nan")})
    return DayLevels(
        atr_mid2=float(ctx.atr_mid2), tick2=tick2, prior_d8=int(ctx.prior_d8),
        pd_high=float(ctx.prior_high), pd_low=float(ctx.prior_low),
        pd_close=float(ctx.prior_close),
        pd_src_ts_ns=int(row["session_close_ts_ns"]),
        prev_sess_d8=int(prev_d8),
        prev_sess_last_ts_ns=int(prev.ts[-1]) if prev is not None else -1,
        value_lo=float(area["value_lo"]), value_hi=float(area["value_hi"]))


def build_one(asset: str, d8: int, out_root: Path) -> dict[str, object]:
    started = time.monotonic()
    state = _state()
    records = state["records"]
    ctxs = state["ctxs"]
    positions = state["index"].get((asset, int(d8)), [])
    if not positions:
        raise BuildStop(f"prep cache has no cell for {asset}/{d8}")
    kept_positions = [p for p in positions if ctxs[p] is not None]
    skipped = [records[p].phase for p in positions if ctxs[p] is None]
    payload: dict[str, np.ndarray] = {}
    sidecar_cells: list[dict[str, object]] = []
    counts = {"cells": 0, "skipped": len(skipped), "bars": 0,
              "rows": 0, "nonfinite_cells": 0,
              "cells_with_prior_session": 0, "cells_with_prior_day": 0}
    if kept_positions:
        atrs = {round(float(ctxs[p].atr_mid2), 6) for p in kept_positions}
        if len(atrs) != 1:
            raise BuildStop(f"{asset}/{d8} carries {len(atrs)} ATR values")
        prev_d8 = _prev_explore_day(state["explore"][asset], int(d8))
        prev = _tape_for(state, asset, prev_d8) if prev_d8 > 0 else None
        tape = _tape_for(state, asset, int(d8))
        if prev is not None and int(prev.ts[-1]) >= int(tape.ts[0]):
            raise BuildStop(
                f"prior session {prev_d8} overlaps {asset}/{d8}")
        ctx = ctxs[kept_positions[0]]
        day = day_context(state, asset, int(d8), ctx, prev, prev_d8)
        if int(day.prior_d8) >= int(d8) or (prev_d8 > 0 and prev_d8 >= int(d8)):
            raise BuildStop(f"prior day is not prior for {asset}/{d8}")
        planes, src = day_planes(tape, prev, day)
        slot = 0
        for start, position in zip(tape.starts, tape.positions, strict=True):
            if ctxs[position] is None:
                continue
            rec = records[position]
            bars = int(rec.n)
            window = slice(start, start + bars)
            for (side, mult_index), plane in planes.items():
                block = np.asarray(plane[window], np.float32)
                payload[f"c{slot}_{LV.SIDE_TAG[side]}_m{mult_index}"] = block
                counts["rows"] += bars
                counts["nonfinite_cells"] += int(
                    (~np.isfinite(block)).sum())
            payload[f"c{slot}_src_ts_ns"] = np.asarray(src[window], np.int64)
            sidecar_cells.append({
                "phase": rec.phase, "phase_open_ts_ns": int(rec.phase_open_ts_ns),
                "phase_close_ts_ns": int(rec.phase_close_ts_ns), "bars": bars,
                "tape_start": int(start), "tape_bars": int(tape.n),
                "atr_mid2": float(day.atr_mid2), "tick2": float(day.tick2),
                "prior_d8": int(day.prior_d8), "prev_sess_d8": int(day.prev_sess_d8),
                "value_lo": float(day.value_lo), "value_hi": float(day.value_hi),
                "pd_high": float(day.pd_high), "pd_low": float(day.pd_low),
                "pd_close": float(day.pd_close),
                "src_max_minus_stamp_ns": int(
                    (src[window] - np.asarray(tape.ts, np.int64)[window]).max())})
            counts["cells"] += 1
            counts["bars"] += bars
            counts["cells_with_prior_day"] += 1
            counts["cells_with_prior_session"] += int(prev is not None)
            slot += 1
    sidecar = {
        "schema": LV.LEVELS_SCHEMA, "asset": asset, "d8": int(d8),
        "columns": list(LV.LEVEL_FEATURES),
        "band_mults": list(LV.BAND_MULTS),
        "hold_bands": LV.HOLD_BANDS, "breach_bands": LV.BREACH_BANDS,
        "value_area_fraction": LV.VALUE_AREA_FRACTION,
        "value_area_method": VALUE_METHOD,
        "cells": sidecar_cells, "skipped_phases": skipped, "counts": counts}
    directory = out_root / asset
    directory.mkdir(parents=True, exist_ok=True)
    npz_path = directory / f"{int(d8)}.npz"
    with npz_path.open("wb") as handle:
        np.savez(handle, **payload)
    npz_sha = hashlib.sha256(npz_path.read_bytes()).hexdigest()
    (directory / f"{int(d8)}.json").write_text(
        json.dumps({**sidecar, "npz_sha256": npz_sha}, sort_keys=True, indent=1)
        + "\n")
    return {"asset": asset, "d8": int(d8), "npz_sha256": npz_sha,
            "npz_bytes": int(npz_path.stat().st_size),
            "counts": dict(counts),
            # The worst cell is the one whose newest source sits closest to its
            # bar stamp, so the shard's figure is the MAX of the negatives.  A
            # shard with no cell has no stamp to report, and must not put a
            # placeholder into the total.
            "max_src_minus_stamp_ns": (
                max(int(cell["src_max_minus_stamp_ns"]) for cell in sidecar_cells)
                if sidecar_cells else None),
            "wall_seconds": round(time.monotonic() - started, 3)}


def _job(job: tuple[str, int, str]) -> dict[str, object]:
    asset, d8, out_root = job
    return build_one(asset, int(d8), Path(out_root))


def build_all(assets: Sequence[str], workers: int,
              out_root: Path = LV.LEVELS_ROOT) -> dict[str, object]:
    days = S1._explore_days(assets)
    jobs = [(asset, int(day), str(out_root)) for asset in assets
            for day in days[asset]]
    out_root.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    shards: list[dict[str, object]] = []
    failures: list[str] = []
    if workers <= 1:
        for job in jobs:
            shards.append(_job(job))
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_job, job): job for job in jobs}
            done = 0
            for future in as_completed(futures):
                asset, day, _root = futures[future]
                try:
                    shards.append(future.result())
                except Exception as error:  # noqa: BLE001 - reported, not swallowed
                    failures.append(f"{asset}/{day}: {type(error).__name__}: {error}")
                done += 1
                if done % 40 == 0:
                    print(f"  built {done}/{len(jobs)} "
                          f"elapsed={time.monotonic() - started:.1f}s", flush=True)
    if failures:
        raise BuildStop("levels shard build failed:\n  " + "\n  ".join(failures[:10]))
    shards.sort(key=lambda row: (ASSETS.index(str(row["asset"])), int(row["d8"])))
    split = json.loads(SPLIT_PATH.read_text())
    def _sum(name: str) -> int:
        return sum(int(row["counts"][name]) for row in shards)
    totals = {
        "shards": len(shards),
        "npz_bytes": sum(int(row["npz_bytes"]) for row in shards),
        "cells": _sum("cells"), "skipped_cells": _sum("skipped"),
        "bars": _sum("bars"), "rows": _sum("rows"),
        "nonfinite_cells": _sum("nonfinite_cells"),
        "cells_with_prior_day": _sum("cells_with_prior_day"),
        "cells_with_prior_session": _sum("cells_with_prior_session"),
        "shards_by_asset": {asset: sum(row["asset"] == asset for row in shards)
                            for asset in assets},
        "cells_by_asset": {
            asset: sum(int(row["counts"]["cells"]) for row in shards
                       if row["asset"] == asset) for asset in assets},
        "prior_session_cells_by_asset": {
            asset: sum(int(row["counts"]["cells_with_prior_session"])
                       for row in shards if row["asset"] == asset)
            for asset in assets},
        "prior_day_cells_by_asset": {
            asset: sum(int(row["counts"]["cells_with_prior_day"])
                       for row in shards if row["asset"] == asset)
            for asset in assets},
        "max_src_minus_stamp_ns": max(
            [int(row["max_src_minus_stamp_ns"]) for row in shards
             if row["max_src_minus_stamp_ns"] is not None] or [0]),
        "empty_shards": sum(1 for row in shards
                            if row["max_src_minus_stamp_ns"] is None),
        "wall_seconds": round(time.monotonic() - started, 2)}
    manifest = {
        "schema": LV.MANIFEST_SCHEMA, "tier": "exploratory",
        "split_sha256": str(split["split_sha256"]),
        "assets": list(assets), "workers": int(workers),
        "columns": list(LV.LEVEL_FEATURES), "band_mults": list(LV.BAND_MULTS),
        "hold_bands": LV.HOLD_BANDS, "breach_bands": LV.BREACH_BANDS,
        "value_area_fraction": LV.VALUE_AREA_FRACTION,
        "value_area_method": VALUE_METHOD,
        "sources": list(SOURCE_NAMES), "built_unix": int(time.time()),
        "totals": totals, "shards": shards}
    (out_root / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=1) + "\n")
    return manifest


# --------------------------------------------------------------------------
# Verification: an independent recount, the causality receipt, the join.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class _Occ:
    """The occurrence shape ``build_level_join`` reads (sweep-14's ``Occ``)."""

    row: int
    side: int
    bar: int


@dataclass(slots=True)
class _Cell:
    """The sweep-8 cell shape ``build_level_join`` reads."""

    position: int
    asset: str
    d8: int
    rec: S1.CellRec


@dataclass(slots=True)
class _Stream:
    cell: int
    asset: str
    d8: int
    occs: list[_Occ]


def _recount(tape: DayTape, prev: DayTape | None, width: float, side: int,
             bar: int, *, prev_ok: bool) -> dict[str, float]:
    """A plain-loop recount of one bar's memory columns, for the audit.

    Deliberately written the long way: the build is one vectorized pass over
    matrices, so a second implementation that walks bars one at a time is the
    only recount worth having.
    """

    blank = {name: float("nan") for name in
             LV.SAME_DAY_COLUMNS + ("ps_touches", "ps_held", "ps_broke")}
    if not bool(tape.sourced[bar]):
        return blank
    centre = float(tape.mid[bar])
    hold = LV.HOLD_BANDS * width * (1.0 if side > 0 else -1.0)
    breach = LV.BREACH_BANDS * width * (1.0 if side > 0 else -1.0)
    touches = held = broke = 0
    delta = 0.0
    last = -1
    for j in range(bar):
        if not bool(tape.sourced[j]):
            continue
        if abs(float(tape.mid[j]) - centre) > width:
            continue
        touches += 1
        last = j
        delta += float(tape.delta[j])
        price = float(tape.mid[j])
        hold_bar, broke_bar = -1, -1
        for t in range(j + 1, tape.n):
            value = float(tape.mid[t])
            if hold_bar < 0 and (value >= price + hold if side > 0
                                 else value <= price + hold):
                hold_bar = t
            if broke_bar < 0 and (value < price - breach if side > 0
                                  else value > price - breach):
                broke_bar = t
            if hold_bar >= 0 and broke_bar >= 0:
                break
        if 0 <= hold_bar < bar and (broke_bar < 0 or hold_bar < broke_bar):
            held += 1
        if 0 <= broke_bar < bar and (hold_bar < 0 or broke_bar < hold_bar):
            broke += 1
    out = {"sd_touches": float(touches), "sd_held": float(held),
           "sd_broke": float(broke), "sd_touch_delta": delta,
           "sd_mins_since_touch": (float(tape.ts[bar] - tape.ts[last])
                                   / LV.NANOS_PER_MINUTE if last >= 0
                                   else float("nan"))}
    if prev is None or not prev_ok:
        out.update({"ps_touches": float("nan"), "ps_held": float("nan"),
                    "ps_broke": float("nan")})
        return out
    ptouch = pheld = pbroke = 0
    for j in range(prev.n):
        if not bool(prev.sourced[j]):
            continue
        if abs(float(prev.mid[j]) - centre) > width:
            continue
        ptouch += 1
        price = float(prev.mid[j])
        hold_bar, broke_bar = -1, -1
        for t in range(j + 1, prev.n):
            value = float(prev.mid[t])
            if hold_bar < 0 and (value >= price + hold if side > 0
                                 else value <= price + hold):
                hold_bar = t
            if broke_bar < 0 and (value < price - breach if side > 0
                                  else value > price - breach):
                broke_bar = t
            if hold_bar >= 0 and broke_bar >= 0:
                break
        if hold_bar >= 0 and (broke_bar < 0 or hold_bar < broke_bar):
            pheld += 1
        if broke_bar >= 0 and (hold_bar < 0 or broke_bar < hold_bar):
            pbroke += 1
    out.update({"ps_touches": float(ptouch), "ps_held": float(pheld),
                "ps_broke": float(pbroke)})
    return out


def verify(assets: Sequence[str], rows: int = VERIFY_ROWS) -> dict[str, object]:
    """Hand-check ``rows`` real rows: recount, causality stamp, prior-day law."""

    state = _state()
    records = state["records"]
    rng = np.random.default_rng(VERIFY_SEED)
    days = S1._explore_days(assets)
    picks: list[tuple[str, int]] = []
    for asset in assets:
        # The first EXPLORE day of an asset has no prior session, so pick from
        # the rest; the missing-prior case is covered by the coverage totals.
        pool = [int(day) for day in days[asset][1:]]
        for day in rng.choice(pool, size=max(1, rows // len(assets) + 1),
                              replace=False):
            picks.append((asset, int(day)))
    checked: list[dict[str, object]] = []
    worst_gap = -(1 << 62)
    mismatches: list[str] = []
    for asset, d8 in picks:
        if len(checked) >= rows:
            break
        day_cells = LV.load_levels(asset, d8)
        tape = _tape_for(state, asset, d8)
        prev_d8 = _prev_explore_day(state["explore"][asset], d8)
        prev = _tape_for(state, asset, prev_d8) if prev_d8 > 0 else None
        by_key = {(records[p].phase, int(records[p].phase_open_ts_ns)): (p, start)
                  for p, start in zip(tape.positions, tape.starts, strict=True)}
        for key, cell in sorted(day_cells.items()):
            if len(checked) >= rows:
                break
            position, start = by_key[key]
            rec = records[position]
            side = int(rng.choice(LV.SIDES))
            mult_index = int(rng.integers(0, len(LV.BAND_MULTS)))
            bar = int(rng.integers(max(1, rec.n // 2), rec.n))
            width = float(LV.BAND_MULTS[mult_index]) * float(cell.atr_mid2)
            plane = cell.matrix(side, mult_index)
            prev_ok = (prev is not None
                       and int(prev.ts[-1]) < int(tape.ts[start + bar]))
            expect = _recount(tape, prev, width, side, start + bar,
                              prev_ok=prev_ok)
            row = {name: float(plane[bar, LV.LEVEL_INDEX[name]])
                   for name in expect}
            for name, value in expect.items():
                got = row[name]
                same = (abs(got - value) <= 1e-6 * max(1.0, abs(value))
                        if np.isfinite(value) and np.isfinite(got)
                        else np.isnan(value) and np.isnan(got))
                if not same:
                    mismatches.append(
                        f"{asset}/{d8}/{key[0]} bar={bar} side={side} "
                        f"m={mult_index} {name}: cache={got} recount={value}")
            gap = int(cell.src_ts_ns[bar]) - int(rec.lat[bar])
            worst_gap = max(worst_gap, gap)
            checked.append({
                "asset": asset, "d8": d8, "phase": key[0], "bar": bar,
                "side": side, "mult_index": mult_index,
                "band_mult": float(LV.BAND_MULTS[mult_index]),
                "src_minus_stamp_ns": gap,
                "prior_d8": int(cell.prior_d8),
                "prev_sess_d8": int(cell.prev_sess_d8),
                "prev_sess_prior": bool(int(cell.prev_sess_d8) < d8),
                "prior_day_prior": bool(int(cell.prior_d8) < d8),
                "recount": expect, "cache": row})
    prior_ok = all(bool(row["prior_day_prior"]) and bool(row["prev_sess_prior"])
                   for row in checked)
    return {"rows": len(checked), "mismatches": mismatches,
            "max_src_minus_stamp_ns": int(worst_gap),
            "strictly_prior": bool(worst_gap < 0),
            "prior_days_never_current": bool(prior_ok),
            "checked": checked}


def coverage(assets: Sequence[str]) -> dict[str, object]:
    """Per asset: cells carrying at least one finite value of each family.

    The NaN masks are the same on every side and multiplier except
    ``sd_mins_since_touch``, whose definedness depends on the band width, so the
    family census reads the default plane and the finite fractions are summed
    over all six.
    """

    days = S1._explore_days(assets)
    out: dict[str, object] = {}
    families = {"same_day": LV.SAME_DAY_COLUMNS,
                "prior_day": LV.PRIOR_DAY_COLUMNS,
                "prior_session": LV.PRIOR_SESSION_COLUMNS}
    for asset in assets:
        stat = {"shards": 0, "cells": 0, "bars": 0, "planes": 0,
                **{f"cells_with_{name}": 0 for name in families}}
        finite = {name: 0 for name in LV.LEVEL_FEATURES}
        plane_rows = 0
        for d8 in days[asset]:
            try:
                day = LV.load_levels(asset, int(d8))
            except LV.LevelStop:
                continue
            stat["shards"] += 1
            for cell in day.values():
                stat["cells"] += 1
                stat["bars"] += int(cell.bars)
                for key, plane in cell.planes.items():
                    ok = np.isfinite(plane)
                    plane_rows += int(plane.shape[0])
                    stat["planes"] += 1
                    for position, name in enumerate(LV.LEVEL_FEATURES):
                        finite[name] += int(ok[:, position].sum())
                    if key != (1, LV.DEFAULT_MULT_INDEX):
                        continue
                    for name, columns in families.items():
                        index = [LV.LEVEL_INDEX[column] for column in columns]
                        if bool(ok[:, index].any()):
                            stat[f"cells_with_{name}"] += 1
        out[asset] = {**stat, "plane_rows": plane_rows,
                      "finite_fraction": {
                          name: round(finite[name] / max(1, plane_rows), 6)
                          for name in LV.LEVEL_FEATURES}}
    return out


def sample_join(assets: Sequence[str], per_asset: int = 1,
                bars: int = 3) -> dict[str, object]:
    """Run ``build_level_join`` over a small synthetic occurrence stream."""

    state = _state()
    records = state["records"]
    days = S1._explore_days(assets)
    streams: list[_Stream] = []
    cells: list[_Cell] = []
    row = 0
    for asset in assets:
        for d8 in days[asset][-per_asset:]:
            for position in state["index"][(asset, int(d8))]:
                rec = records[position]
                cells.append(_Cell(position, asset, int(d8), rec))
                occs = [_Occ(row + step, 1 if step % 2 == 0 else -1,
                             int(rec.n) - 1 - step * 7)
                        for step in range(bars)]
                row += bars
                streams.append(_Stream(position, asset, int(d8), occs))
    join = LV.build_level_join(streams, cells)
    order = [occ for stream in streams for occ in stream.occs]
    matrix, columns = join.matrix(order)
    return {"counters": dict(join.counters), "columns": list(columns),
            "band_mult": join.band_mult,
            "max_src_minus_stamp_ns": int(join.max_src_minus_stamp_ns),
            "strictly_prior": bool(join.max_src_minus_stamp_ns < 0),
            "matrix_shape": list(matrix.shape),
            "nonfinite_cells": int((~np.isfinite(matrix)).sum()),
            "sample_rows": [
                {"row": int(order[position].row),
                 "side": int(order[position].side),
                 "bar": int(order[position].bar),
                 "values": [None if not np.isfinite(value) else round(float(value), 6)
                            for value in matrix[position]]}
                for position in range(min(3, matrix.shape[0]))]}


# --------------------------------------------------------------------------
# Selftest: synthetic bars only.  Zero era bytes.
# --------------------------------------------------------------------------

SELFTEST_ATR = 100.0
SELFTEST_TICK2 = 2.0
SELFTEST_MULT_INDEX = 0        # BAND_MULTS[0] = 0.10 -> half-width 10.0
SELFTEST_OPEN_NS = 1_700_000_000_000_000_000


def _tape(asset: str, d8: int, mid: Sequence[float], volume: Sequence[float],
          open_ns: int) -> DayTape:
    values = np.asarray(mid, np.float64)
    bars = len(values)
    ts = open_ns + LV.NANOS_PER_MINUTE * np.arange(1, bars + 1, dtype=np.int64)
    return DayTape(asset, d8, ts, values, np.arange(1.0, bars + 1.0),
                   np.asarray(volume, np.float64), ts - 1,
                   np.ones(bars, bool), (0,), (0,))


def _synthetic() -> tuple[DayTape, DayTape, DayLevels]:
    """A two-day fixture laid out so every count is hand-countable.

    Half-width is ``0.10 * 100 = 10``.  Read at TODAY's bar 11 (mid 104) the
    band is ``[94, 114]``.  Prior bars inside it are 2 (100), 3 (105), 5 (100),
    8 (103) and 9 (96); bars 4 (130), 6 (88), 7 (121) and 10 (300) are outside.
    Side +1 resolves a touch at ``P`` when price reaches ``P + 10`` (held) or
    prints below ``P - 10`` (broke), whichever comes first; side -1 mirrors it.
    """

    today = _tape("HG", 20220318,
                  [500, 300, 100, 105, 130, 100, 88, 121, 103, 96, 300, 104],
                  [1] * 12, SELFTEST_OPEN_NS)
    prior = _tape("HG", 20220315, [300, 105, 130, 100, 85, 300],
                  [5, 30, 5, 40, 15, 5],
                  SELFTEST_OPEN_NS - 86_400 * LV.NANOS_PER_MINUTE)
    area = LV.value_area(prior.mid, prior.vol, SELFTEST_TICK2)
    day = DayLevels(
        atr_mid2=SELFTEST_ATR, tick2=SELFTEST_TICK2, prior_d8=20220317,
        pd_high=130.0, pd_low=85.0, pd_close=300.0,
        pd_src_ts_ns=int(prior.ts[-1]) + 60, prev_sess_d8=20220315,
        prev_sess_last_ts_ns=int(prior.ts[-1]),
        value_lo=float(area["value_lo"]), value_hi=float(area["value_hi"]))
    return today, prior, day


def selftest() -> int:
    mutant = LV._mutant()
    today, prior, day = _synthetic()
    planes, src = day_planes(today, prior, day)
    check_bar = 11
    failures: list[str] = []

    def _check(name: str, body) -> None:
        try:
            body()
        except Exception as error:  # noqa: BLE001 - a red case is the signal
            failures.append(f"{name}: {type(error).__name__}: {error}")

    def value(name: str, side: int, bar: int = check_bar) -> float:
        return float(planes[(side, SELFTEST_MULT_INDEX)][bar, LV.LEVEL_INDEX[name]])

    def same_day_counts() -> None:
        # Five prior bars sit inside [94, 114].  Side +1: bar 2 (100) reaches
        # 110 at bar 4, bar 3 (105) reaches 115 at bar 4, bar 8 (103) and bar 9
        # (96) reach their targets at bar 10 - four holds.  Bar 5 (100) prints
        # 88 at bar 6 before 110 at bar 7, the one break.
        assert value("sd_touches", 1) == 5.0, f"touches {value('sd_touches', 1)}"
        assert value("sd_held", 1) == 4.0, f"held {value('sd_held', 1)}"
        assert value("sd_broke", 1) == 1.0, f"broke {value('sd_broke', 1)}"
        # Side -1 mirrors the legs: four of the five were exceeded to the upside
        # first and broke, and bar 5 (100) fell to 88 at bar 6 before 110 at bar
        # 7, so a high fade reads that one as held.
        assert value("sd_touches", -1) == 5.0, f"touches- {value('sd_touches', -1)}"
        assert value("sd_held", -1) == 1.0, f"held- {value('sd_held', -1)}"
        assert value("sd_broke", -1) == 4.0, f"broke- {value('sd_broke', -1)}"
        # The last touch was bar 9, two bars back, and the touched bars carry
        # delta 3, 4, 6, 9 and 10 (the fixture's delta is bar ordinal + 1).
        assert value("sd_mins_since_touch", 1) == 2.0, (
            f"gap {value('sd_mins_since_touch', 1)}")
        assert value("sd_touch_delta", 1) == 32.0, (
            f"delta {value('sd_touch_delta', 1)}")

    def unresolved_is_not_an_outcome() -> None:
        # Read at bar 9 (mid 96) the band is [86, 106]: bars 2, 3, 5, 6 and 8
        # are inside it.  Bar 8's verdict does not land until bar 10, so it is a
        # touch with no outcome yet - three holds, one break, one open.
        assert value("sd_touches", 1, 9) == 5.0, (
            f"touches@9 {value('sd_touches', 1, 9)}")
        assert value("sd_held", 1, 9) == 3.0, f"held@9 {value('sd_held', 1, 9)}"
        assert value("sd_broke", 1, 9) == 1.0, f"broke@9 {value('sd_broke', 1, 9)}"

    def prior_session() -> None:
        # Prior day bars inside [94, 114]: 105 at bar 1 and 100 at bar 3.  Bar 1
        # reaches 115 at bar 2 (held); bar 3 prints 85 at bar 4 before reaching
        # 110 at bar 5 (broke).
        assert value("ps_touches", 1) == 2.0, f"ps touches {value('ps_touches', 1)}"
        assert value("ps_held", 1) == 1.0, f"ps held {value('ps_held', 1)}"
        assert value("ps_broke", 1) == 1.0, f"ps broke {value('ps_broke', 1)}"

    def value_band() -> None:
        # Volumes 15 at 85, 40 at 100, 30 at 105, 5 at 130, 10 at 300, total
        # 100.  Two-tick bins from 85: bin 7 holds 40, bin 10 holds 30, so bins
        # 7..10 are the narrowest window with 70, i.e. [99, 107).
        assert day.value_lo == 99.0, f"value_lo {day.value_lo}"
        assert day.value_hi == 107.0, f"value_hi {day.value_hi}"
        assert value("near_value_lo", 1) == 1.0, "104 is not within a band of 99"
        assert value("near_value_hi", 1) == 1.0, "104 is not within a band of 107"
        assert value("near_pd_high", 1) == 0.0, "104 read as near the 130 high"
        assert abs(value("dist_value_hi_atr", 1) + 0.03) < 1e-9, (
            f"value_hi distance {value('dist_value_hi_atr', 1)}")

    def location() -> None:
        # Bars 0..10 run 500 down to 88, so at bar 11 the developing range is
        # [88, 500] and 104 sits 16/412 of the way up it.
        assert abs(value("dist_day_high_atr", 1) - 3.96) < 1e-9, (
            f"to high {value('dist_day_high_atr', 1)}")
        assert abs(value("dist_day_low_atr", 1) - 0.16) < 1e-9, (
            f"to low {value('dist_day_low_atr', 1)}")
        assert abs(value("range_rank", 1) - 16.0 / 412.0) < 1e-12, (
            f"rank {value('range_rank', 1)}")
        assert abs(value("dist_pd_low_atr", 1) - 0.19) < 1e-9, (
            f"to prior low {value('dist_pd_low_atr', 1)}")
        # Bar 0 has no prior bar, so its memory and location are undefined.
        assert np.isnan(value("sd_touches", 1, 0)), "bar 0 counted a touch"
        assert np.isnan(value("range_rank", 1, 0)), "bar 0 carried a range rank"

    def strictly_prior() -> None:
        gaps = src - np.asarray(today.ts, np.int64)
        assert bool(np.all(gaps < 0)), f"max src minus stamp {int(gaps.max())}"
        # The reading bar sees its own last raw row (the fixture stamps it one
        # ns before the close) and the previous bar's close, never its own.
        assert int(src[check_bar]) == int(today.ts[check_bar]) - 1, (
            f"src at {check_bar} is {int(src[check_bar])}")
        assert int(src[check_bar]) >= int(today.ts[check_bar - 1]), (
            "src dropped below the previous bar close")

    def touch_excludes_current_bar() -> None:
        # Bar 11 sits at distance zero from its own band centre, so a plane that
        # read its own bar would count six touches, not five.
        assert value("sd_touches", 1) == 5.0, (
            f"current bar counted: {value('sd_touches', 1)}")
        band = LV.touch_matrix(today.mid, today.mid, 10.0, prior_only=True)
        assert not bool(band[check_bar, check_bar]), "band reads its own bar"

    _check("same_day_counts", same_day_counts)
    _check("unresolved_is_not_an_outcome", unresolved_is_not_an_outcome)
    _check("prior_session", prior_session)
    _check("value_band", value_band)
    _check("location", location)
    _check("strictly_prior", strictly_prior)
    _check("touch_excludes_current_bar", touch_excludes_current_bar)

    expected_red = {LV.MUTANT_TOUCH_CURRENT: "touch_excludes_current_bar"}
    if mutant:
        died = {line.split(":", 1)[0] for line in failures}
        target = expected_red.get(mutant)
        if target is None:
            print(f"levels_selftest_unknown_mutant {mutant}")
            return 1
        if target not in died:
            print(f"levels_selftest_mutant_survived mutant={mutant} case={target}")
            return 1
        print(f"levels_selftest_red mutant={mutant} died={sorted(died)}")
        for line in failures:
            print(f"  {line}")
        return 1
    if failures:
        print("levels_selftest_red died="
              f"{sorted(line.split(':', 1)[0] for line in failures)}")
        for line in failures:
            print(f"  {line}")
        return 1
    print("levels_selftest_ok cases=7")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", nargs="?", default="all",
                        choices=("build", "verify", "all"))
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--assets", default=",".join(ASSETS))
    parser.add_argument("--rows", type=int, default=VERIFY_ROWS)
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if os.environ.get(LV.MUTANT_ENV, "") or os.environ.get(FZ.MUTANT_ENV, ""):
        raise BuildStop("refusing to write a cache under a mutant")
    assets = tuple(name.strip().upper() for name in args.assets.split(",")
                   if name.strip())
    if any(asset not in ASSETS for asset in assets):
        raise BuildStop(f"unknown asset in {args.assets!r}")
    report: dict[str, object] = {}
    if args.stage in ("build", "all"):
        manifest = build_all(assets, max(1, int(args.workers)))
        totals = manifest["totals"]
        print(f"shards={totals['shards']} by_asset={totals['shards_by_asset']}")
        print(f"cells={totals['cells']} by_asset={totals['cells_by_asset']} "
              f"skipped={totals['skipped_cells']} bars={totals['bars']}")
        print(f"rows={totals['rows']} nonfinite_cells={totals['nonfinite_cells']}")
        print(f"prior_session_cells={totals['prior_session_cells_by_asset']} "
              f"prior_day_cells={totals['prior_day_cells_by_asset']}")
        print(f"max_src_minus_stamp_ns={totals['max_src_minus_stamp_ns']}")
        print(f"npz_bytes={totals['npz_bytes']} "
              f"wall_seconds={totals['wall_seconds']} workers={args.workers}")
        print(f"manifest={LV.LEVELS_ROOT / 'manifest.json'}")
        report["manifest"] = {key: value for key, value in manifest.items()
                              if key != "shards"}
        report["shards"] = len(manifest["shards"])
    if args.stage in ("verify", "all"):
        audit = verify(assets, rows=int(args.rows))
        join = sample_join(assets)
        print(f"verify_rows={audit['rows']} mismatches={len(audit['mismatches'])} "
              f"max_src_minus_stamp_ns={audit['max_src_minus_stamp_ns']} "
              f"strictly_prior={audit['strictly_prior']} "
              f"prior_days_never_current={audit['prior_days_never_current']}")
        for line in audit["mismatches"][:10]:
            print(f"  {line}")
        print(f"join counters={join['counters']} "
              f"shape={join['matrix_shape']} "
              f"max_src_minus_stamp_ns={join['max_src_minus_stamp_ns']}")
        census = coverage(assets)
        for asset, block in census.items():
            print(f"{asset:4s} shards={block['shards']:3d} cells={block['cells']:3d} "
                  f"bars={block['bars']:6d} same_day={block['cells_with_same_day']:3d} "
                  f"prior_day={block['cells_with_prior_day']:3d} "
                  f"prior_session={block['cells_with_prior_session']:3d}")
        report["causality_audit"] = audit
        report["join"] = join
        report["coverage"] = census
    if report:
        report["written_unix"] = int(time.time())
        REPORT_PATH.write_text(json.dumps(report, sort_keys=True, indent=1) + "\n")
        print(f"report={REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
