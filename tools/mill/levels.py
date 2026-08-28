#!/usr/bin/env python3
"""The level-memory law and the one accessor over its cache.

The refill paper's decomposition says flow alone grades a touch at AUC 0.54 and
that memory plus location carries it to 0.63.  The mill has flow (``flow.py``)
and the zone-episode object (``flow_zones.py``); neither carries memory of a
PRICE, only of the running extreme inside one phase window.  This plane is that
missing object: per (cell, minute bar, fade side), what has happened at THIS
price before, today across all phases and in the prior session, and where this
price sits in the developing day.

Everything here is computed from data strictly prior to the reading bar's close.
The reading bar's own mid is licensed (the mill samples it at ``lat[b]`` from
rows with ``ts < lat[b]``, so its last source row is ``raw_last[b] < lat[b]``);
every count, outcome and flow sum reads bars strictly before ``b``.  The cache
carries the per-bar max source stamp so a consumer can prove that mechanically
rather than remember it, and the mutant ``QRE2_MILL_LEVELS_MUTANT=
touch_reads_current_bar`` folds the reading bar into its own touch count, which
is the proof the guard is load bearing.

Three decisions the numbers forced, recorded here because they are not
recoverable from the column names:

* **The band is centred on the reading bar's mid**, not on the running session
  extreme.  Centred on the extreme, a "broke" count is structurally zero: no
  prior bar lies beyond the running extreme, so no prior touch inside the band
  can ever have traded through its far side.  Centred on the bar's own price the
  memory is non-degenerate, and ``dist_day_low_atr`` / ``dist_day_high_atr``
  still tell a consumer when that price IS the fade candidate's extreme.
* **A touch's outcome is anchored on the touched price**, not on the reading
  bar's band.  Touch at ``P``, band width ``w``: for a low fade (side +1) the
  touch HELD when price reached ``P + w`` before any bar printed below
  ``P - w``, and BROKE when it printed below ``P - w`` first.  Side -1 is the
  mirror.  The outcome is counted only from the bar it RESOLVES on, so a touch
  whose verdict is not yet in contributes to the touch count and to neither
  outcome.
* **The prior session is the prior EXPLORE session**, three locked days back
  under the split law (`.audit/mill-split.json`: EXPLORE is rank % 3 == 0).  The
  mill's licence binds HOLD intraday paths as unread by every rule, so a
  minute-grain prior-day plane cannot use the immediately prior locked day.  The
  day-level prior-day levels (high, low, close) DO come from that immediately
  prior day, through the context store, which is licensed to serve day-level
  OHLC strictly prior.  Both day stamps are carried per cell.

``build_levels.py`` writes the cache; :func:`load_levels` is the only sanctioned
reader and :func:`build_level_join` is the only sanctioned join onto the sweep-14
occurrence stream.  Nothing here opens a HOLD day, a teacher or late label, or
any outcome column.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Mapping, Protocol, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
LEVELS_ROOT = ROOT / "artifacts/cache/mill_levels"
LEVELS_SCHEMA = "QRE2MILLLEVELS1"
MANIFEST_SCHEMA = "QRE2MILLLEVELSMANIFEST1"

# Band half-width multipliers, in prior-day ATR14 units.  The multiplier is a
# stored column, so a consuming unit reads the plane it wants rather than
# inheriting one width by accident.
BAND_MULTS = (0.10, 0.20, 0.40)
DEFAULT_MULT_INDEX = 1
# A touch resolves at whichever edge of its own band price crosses first: it
# HELD once price reversed one band width away from the touched price, it BROKE
# once price traded through the far side, one band width the other way.  Both
# legs are the SAME distance on purpose - an asymmetric pair (a hold at two band
# widths, a break at one) makes a random walk break about two times in three, so
# the broke count would measure elapsed volatility rather than defence.  A bar
# exactly on the hold edge counts as a hold; the breach leg needs a strict
# crossing, so a tie goes to the level.
HOLD_BANDS = 1.0
BREACH_BANDS = 1.0
# Value edges: the narrowest contiguous price window holding this share of the
# prior session's minute volume.  Bins are one tick2 wide, widened only if a day
# would otherwise need more than MAX_VALUE_BINS of them.
VALUE_AREA_FRACTION = 0.70
MAX_VALUE_BINS = 4096

SIDES = (1, -1)
SIDE_TAG = {1: "lo", -1: "hi"}

# Fixed column order of one (cell, side, band multiplier) plane.  The sidecar
# stores this roster and the reader refuses a shard whose roster drifted.
LEVEL_FEATURES = (
    # the band itself, raw
    "band_mult", "band_center_mid2", "band_w_mid2",
    # 1. same-session level memory, all phases of the day
    "sd_touches", "sd_held", "sd_broke", "sd_mins_since_touch", "sd_touch_delta",
    # 2a. prior-session level memory, minute grain
    "ps_touches", "ps_held", "ps_broke",
    # 2b. prior-day proximity flags, one band wide
    "near_pd_high", "near_pd_low", "near_pd_close", "near_value_hi",
    "near_value_lo",
    # 3. location
    "dist_day_high_atr", "dist_day_low_atr", "range_rank",
    "dist_pd_high_atr", "dist_pd_low_atr", "dist_pd_close_atr",
    "dist_value_hi_atr", "dist_value_lo_atr",
)
LEVEL_INDEX = {name: position for position, name in enumerate(LEVEL_FEATURES)}
NLEV = len(LEVEL_FEATURES)

# 4. Defence history is the held/broke pair above.  The band is per fade side
# and the outcome law is side-signed, so "the same side defended this price" is
# exactly "the touch held on this side": today it is (sd_held, sd_broke), in the
# prior session (ps_held, ps_broke).  Duplicating them under a second name would
# put two identical columns in every matrix.
DEFENCE_COLUMNS = {"today": ("sd_held", "sd_broke"),
                   "prior_session": ("ps_held", "ps_broke")}

# Columns sourced from the prior LOCKED day's day-level levels row, and columns
# sourced from the prior EXPLORE session's minute path.  Each group is served
# only at bars whose stamp is strictly after that source's own last stamp: the
# context store's day-level guard is ``row.d8 < d8``, which is not the same
# claim once a session boundary shifts and the prior session closes after this
# session opened.
PRIOR_DAY_COLUMNS = ("near_pd_high", "near_pd_low", "near_pd_close",
                     "dist_pd_high_atr", "dist_pd_low_atr", "dist_pd_close_atr")
PRIOR_SESSION_COLUMNS = ("ps_touches", "ps_held", "ps_broke", "near_value_hi",
                         "near_value_lo", "dist_value_hi_atr",
                         "dist_value_lo_atr")
SAME_DAY_COLUMNS = ("sd_touches", "sd_held", "sd_broke", "sd_mins_since_touch",
                    "sd_touch_delta")

MUTANT_ENV = "QRE2_MILL_LEVELS_MUTANT"
MUTANT_TOUCH_CURRENT = "touch_reads_current_bar"
LEVEL_MUTANTS = (MUTANT_TOUCH_CURRENT,)

NANOS_PER_MINUTE = 60_000_000_000


class LevelStop(RuntimeError):
    """The levels cache is absent, malformed, or asked for the impossible."""


def _mutant() -> str:
    name = os.environ.get(MUTANT_ENV, "")
    if name and name not in LEVEL_MUTANTS:
        raise LevelStop(f"unknown levels mutant: {name}")
    return name


# --------------------------------------------------------------------------
# The law.  Pure functions over one day's bar arrays; the builder and the
# selftest call exactly these.
# --------------------------------------------------------------------------

def touch_matrix(centers: np.ndarray, prices: np.ndarray, half_width: float,
                 *, prior_only: bool) -> np.ndarray:
    """``(k, j)`` mask: bar ``j``'s price sits inside the band read at bar ``k``.

    ``prior_only`` is the causal guard for a same-day tape: bar ``k`` may only
    see ``j < k``.  A prior-session tape is entirely before the reading day, so
    it is joined with ``prior_only=False``.  The mutant relaxes the guard to
    ``j <= k``, which lets the reading bar count itself - it always sits at
    distance zero from its own band centre, so every count gains exactly one.
    """

    band = np.abs(np.asarray(prices, np.float64)[None, :]
                  - np.asarray(centers, np.float64)[:, None]) <= float(half_width)
    if not prior_only:
        return band
    rows = np.arange(band.shape[0])[:, None]
    columns = np.arange(band.shape[1])[None, :]
    if _mutant() == MUTANT_TOUCH_CURRENT:
        return band & (columns <= rows)
    return band & (columns < rows)


def _first_after(hit: np.ndarray) -> np.ndarray:
    """Per row ``j``, the first column ``t > j`` where ``hit[j, t]``, else ``n``.

    ``hit`` is square and indexed ``(touch bar, later bar)``.
    """

    n = hit.shape[0]
    forward = hit & (np.arange(n)[None, :] > np.arange(n)[:, None])
    found = forward.any(axis=1)
    return np.where(found, forward.argmax(axis=1), n).astype(np.int64)


def outcome_bars(prices: np.ndarray, half_width: float, side: int
                 ) -> tuple[np.ndarray, np.ndarray]:
    """``(hold_bar, broke_bar)`` for a touch AT each bar, ``n`` when unresolved.

    Anchored on the touched price ``P`` with band width ``w``.  Side +1 fades a
    low, so the buyers holding it must lift price to ``P + w`` before it prints
    below ``P - w``; side -1 is the mirror.  Both arrays are the first LATER bar
    that satisfies the leg, so a caller counts an outcome only once the verdict
    bar is itself strictly prior.
    """

    values = np.asarray(prices, np.float64)
    width = float(half_width)
    hold_level = values + HOLD_BANDS * width * float(np.sign(side))
    breach_level = values - BREACH_BANDS * width * float(np.sign(side))
    if int(side) > 0:
        hold_hit = values[None, :] >= hold_level[:, None]
        breach_hit = values[None, :] < breach_level[:, None]
    else:
        hold_hit = values[None, :] <= hold_level[:, None]
        breach_hit = values[None, :] > breach_level[:, None]
    return _first_after(hold_hit), _first_after(breach_hit)


def prior_extremes(prices: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``(low, high, valid)`` of the developing day read AT each bar.

    The read at bar ``b`` covers bars ``0..b-1``: the bar printing a new extreme
    is never measured against the level it is setting.  Bar 0 has no prior bar,
    so it carries no developing range.
    """

    values = np.asarray(prices, np.float64)
    low = np.empty(len(values), np.float64)
    high = np.empty(len(values), np.float64)
    valid = np.zeros(len(values), bool)
    low[0] = high[0] = np.nan
    if len(values) > 1:
        low[1:] = np.minimum.accumulate(values)[:-1]
        high[1:] = np.maximum.accumulate(values)[:-1]
        valid[1:] = True
    return low, high, valid


def value_area(prices: np.ndarray, volumes: np.ndarray, bin_width: float,
               *, fraction: float = VALUE_AREA_FRACTION,
               max_bins: int = MAX_VALUE_BINS) -> dict[str, float]:
    """The narrowest contiguous price window holding ``fraction`` of volume.

    A settlement area has no definition in our own bytes, so this approximates
    the value edges as the tightest price window that the session actually
    traded ``fraction`` of its minute volume inside.  Ties go to the lowest such
    window, which makes the answer unique.  Returns NaN edges when the session
    carries no volume.
    """

    price = np.asarray(prices, np.float64)
    weight = np.asarray(volumes, np.float64)
    if len(price) != len(weight):
        raise LevelStop(
            f"value area got {len(price)} prices and {len(weight)} volumes")
    keep = np.isfinite(price) & np.isfinite(weight) & (weight > 0.0)
    total = float(weight[keep].sum())
    blank = {"value_lo": float("nan"), "value_hi": float("nan"),
             "bin_width": float(bin_width), "bins": 0.0, "volume": total}
    if not keep.any() or total <= 0.0:
        return blank
    price = price[keep]
    weight = weight[keep]
    low = float(price.min())
    span = float(price.max()) - low
    width = float(bin_width)
    count = int(span // width) + 1
    if count > int(max_bins):
        # A computational guard, not a feature constant: the widened bin is
        # reported so the method stays reproducible.
        width = width * float(np.ceil(count / float(max_bins)))
        count = int(span // width) + 1
    index = np.minimum(((price - low) / width).astype(np.int64), count - 1)
    histogram = np.bincount(index, weights=weight, minlength=count)
    need = float(fraction) * total
    cumulative = np.concatenate(([0.0], np.cumsum(histogram)))
    best_start, best_stop, best_width = -1, -1, count + 1
    stop = 0
    for start in range(count):
        if stop < start:
            stop = start
        while stop < count and cumulative[stop + 1] - cumulative[start] < need:
            stop += 1
        if stop >= count:
            break
        if stop - start + 1 < best_width:
            best_width = stop - start + 1
            best_start, best_stop = start, stop
    if best_start < 0:
        return blank
    return {"value_lo": low + best_start * width,
            "value_hi": low + (best_stop + 1) * width,
            "bin_width": width, "bins": float(count), "volume": total}


# --------------------------------------------------------------------------
# Read side.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class LevelCell:
    """One formation window's level plane: both sides, every band multiplier."""

    asset: str
    d8: int
    phase: str
    phase_open_ts_ns: int
    phase_close_ts_ns: int
    bars: int
    atr_mid2: float
    tick2: float
    prior_d8: int
    prev_sess_d8: int
    value_lo: float
    value_hi: float
    src_ts_ns: np.ndarray                          # (bars,) max source stamp
    planes: dict[tuple[int, int], np.ndarray]      # (side, mult index) -> matrix

    def matrix(self, side: int, mult_index: int = DEFAULT_MULT_INDEX
               ) -> np.ndarray:
        """The ``(bars, NLEV)`` plane for one side at one band multiplier."""

        key = (int(side), int(mult_index))
        if key not in self.planes:
            raise LevelStop(f"levels cell has no plane {key}: {self.asset}/{self.d8}")
        return self.planes[key]

    def column(self, name: str, side: int,
               mult_index: int = DEFAULT_MULT_INDEX) -> np.ndarray:
        return self.matrix(side, mult_index)[:, LEVEL_INDEX[name]]


def load_levels(asset: str, d8: int, *, root: Path = LEVELS_ROOT
                ) -> dict[tuple[str, int], LevelCell]:
    """The day's level cells keyed by ``(phase, phase_open_ts_ns)``."""

    directory = Path(root) / str(asset)
    npz_path = directory / f"{int(d8)}.npz"
    sidecar_path = directory / f"{int(d8)}.json"
    if not npz_path.is_file() or not sidecar_path.is_file():
        raise LevelStop(f"levels shard is absent: {npz_path}")
    sidecar: Mapping[str, object] = json.loads(sidecar_path.read_text())
    if (sidecar.get("schema") != LEVELS_SCHEMA or sidecar.get("asset") != asset
            or int(sidecar.get("d8", -1)) != int(d8)):
        raise LevelStop(f"levels sidecar identity differs: {sidecar_path}")
    if tuple(sidecar.get("columns", ())) != LEVEL_FEATURES:
        raise LevelStop(f"levels columns drifted: {sidecar_path}")
    mults = tuple(float(value) for value in sidecar.get("band_mults", ()))
    if mults != BAND_MULTS:
        raise LevelStop(f"levels band multipliers drifted: {sidecar_path}")
    out: dict[tuple[str, int], LevelCell] = {}
    with np.load(npz_path) as store:
        for position, cell in enumerate(sidecar["cells"]):
            bars = int(cell["bars"])
            planes: dict[tuple[int, int], np.ndarray] = {}
            for side in SIDES:
                for mult_index in range(len(mults)):
                    plane = np.asarray(
                        store[f"c{position}_{SIDE_TAG[side]}_m{mult_index}"])
                    if plane.shape != (bars, NLEV):
                        raise LevelStop(
                            f"levels plane {position}/{side}/{mult_index} of "
                            f"{asset}/{d8} is {plane.shape}, want {(bars, NLEV)}")
                    planes[(side, mult_index)] = plane
            key = (str(cell["phase"]), int(cell["phase_open_ts_ns"]))
            if key in out:
                raise LevelStop(f"levels cell key repeats in {asset}/{d8}: {key}")
            out[key] = LevelCell(
                asset, int(d8), str(cell["phase"]),
                int(cell["phase_open_ts_ns"]), int(cell["phase_close_ts_ns"]),
                bars, float(cell["atr_mid2"]), float(cell["tick2"]),
                int(cell["prior_d8"]), int(cell["prev_sess_d8"]),
                float(cell["value_lo"]), float(cell["value_hi"]),
                np.asarray(store[f"c{position}_src_ts_ns"]), planes)
    return out


def load_manifest(root: Path = LEVELS_ROOT) -> Mapping[str, object]:
    path = Path(root) / "manifest.json"
    if not path.is_file():
        raise LevelStop(f"levels manifest is absent: {path}")
    payload = json.loads(path.read_text())
    if payload.get("schema") != MANIFEST_SCHEMA:
        raise LevelStop(f"levels manifest schema differs: {path}")
    return payload


# --------------------------------------------------------------------------
# The join onto the sweep-14 occurrence stream.
# --------------------------------------------------------------------------

class OccLike(Protocol):
    """One sweep-14 occurrence: the plane row, its side and its lattice bar."""

    row: int
    side: int
    bar: int


class RecLike(Protocol):
    phase: str
    phase_open_ts_ns: int
    lat: np.ndarray


class CellLike(Protocol):
    """One sweep-8 cell: the position the stream keys on plus its record."""

    position: int
    asset: str
    d8: int
    rec: RecLike


class StreamLike(Protocol):
    cell: int
    asset: str
    d8: int
    occs: Sequence[OccLike]


@dataclass(slots=True)
class LevelJoin:
    """The per-occurrence level features and the causality evidence."""

    values: dict[int, np.ndarray]          # plane row -> (NLEV,)
    columns: tuple[str, ...]
    band_mult: float
    counters: dict[str, int]
    max_src_minus_stamp_ns: int
    worst_row: int

    def matrix(self, occs: Sequence[OccLike]) -> tuple[np.ndarray, tuple[str, ...]]:
        """``(len(occs), NLEV)`` in the caller's order, plus the column names."""

        if not len(occs):
            return np.zeros((0, NLEV), np.float64), self.columns
        rows = []
        for occ in occs:
            key = int(occ.row)
            if key not in self.values:
                raise LevelStop(f"level join has no row {key}")
            rows.append(self.values[key])
        return np.vstack(rows), self.columns


def build_level_join(streams: Sequence[StreamLike], cells: Sequence[CellLike],
                     *, mult_index: int = DEFAULT_MULT_INDEX,
                     root: Path = LEVELS_ROOT) -> LevelJoin:
    """One pass over the day shards, joining the level plane onto every occurrence.

    Keyed exactly as ``sweep17.build_absorption`` keys the flow and zone caches:
    ``occ.cell`` names a sweep-8 cell whose record carries
    ``(phase, phase_open_ts_ns)``, and the lattice bar indexes the plane
    directly.  Every occurrence gets a row - an undefined one is NaN, never a
    sentinel - so ``values`` is total over the stream and the caller's
    train-fold imputation stays the only place a NaN becomes a number.
    """

    by_position = {int(cell.position): cell for cell in cells}
    values: dict[int, np.ndarray] = {}
    counters = {"rows": 0, "joined": 0, "missing_cell": 0, "short_arrays": 0,
                "nonfinite_rows": 0, "nonfinite_cells": 0, "defined_rows": 0}
    worst = -(1 << 62)
    worst_row = -1
    cache: dict[tuple[str, int], dict[tuple[str, int], LevelCell]] = {}
    blank = np.full(NLEV, np.nan, np.float64)
    for stream in sorted(streams, key=lambda s: (s.asset, s.d8, s.cell)):
        cell = by_position[int(stream.cell)]
        rec = cell.rec
        key = (str(cell.asset), int(cell.d8))
        if key not in cache:
            cache.clear()               # one day resident at a time
            try:
                cache[key] = load_levels(cell.asset, int(cell.d8), root=root)
            except LevelStop:
                cache[key] = {}
        day = cache[key]
        lcell = day.get((rec.phase, int(rec.phase_open_ts_ns)))
        for occ in stream.occs:
            counters["rows"] += 1
            bar = int(occ.bar)
            if lcell is None:
                counters["missing_cell"] += 1
                values[int(occ.row)] = blank
                continue
            if not 0 <= bar < lcell.bars:
                counters["short_arrays"] += 1
                values[int(occ.row)] = blank
                continue
            # The causal receipt: the max source stamp behind this bar's row
            # against the bar's own lattice stamp.  Strictly negative or the
            # gate fails.
            gap = int(lcell.src_ts_ns[bar]) - int(rec.lat[bar])
            if gap > worst:
                worst = gap
                worst_row = int(occ.row)
            vector = np.asarray(
                lcell.matrix(int(occ.side), mult_index)[bar], np.float64)
            finite = np.isfinite(vector)
            counters["nonfinite_cells"] += int(NLEV - int(finite.sum()))
            if not bool(finite.all()):
                counters["nonfinite_rows"] += 1
            else:
                counters["defined_rows"] += 1
            values[int(occ.row)] = vector
            counters["joined"] += 1
    return LevelJoin(values=values, columns=LEVEL_FEATURES,
                     band_mult=float(BAND_MULTS[int(mult_index)]),
                     counters=counters, max_src_minus_stamp_ns=int(worst),
                     worst_row=int(worst_row))
