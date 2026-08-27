#!/usr/bin/env python3
"""The zone-episode law and the one accessor over its cache.

The flow audit's finding 1b made absorption a ZONE-EPISODE object rather than a
bar-at-the-extreme read: absorption builds over long stretches near (not at) the
extreme, across several touches, and the confirmation that it was real arrives
after price has left the zone.  This module holds the frozen geometry of that
object and nothing else:

* a bar is IN ZONE when its bar mid sits within ``0.15 * ATR14_prev`` of the
  running session extreme on that side.  The running extreme obeys the mill's
  strictly-before law - the value read at bar ``b`` is the extreme of bars
  ``0..b-1``, so a bar can never be tested against the level it is setting.  The
  mutant ``QRE2_MILL_ZONES_MUTANT=zone_uses_own_bar`` moves that one boundary and
  is the proof the law is load bearing.
* an EPISODE is a maximal run of in-zone bars, with two runs merged when fewer
  than five out-of-zone bars separate them.  Absorption that pauses for a minute
  or two is one event, not two.
* a TOUCH is an in-zone bar whose mid sits inside the two-tick core band of the
  extreme.  A touch HELD when no new extreme on that direction printed in the
  five bars after it.

Every statistic is stored twice: once per episode (the distribution tables) and
once as a bar-resolution running series truncated at each bar (what a rule may
read at that bar without seeing the rest of the episode).

``build_flow_zones.py`` writes the cache; :func:`load_zones` is the only
sanctioned reader.  Nothing here opens a HOLD day, a teacher or late label, or
any file outside ``.audit/mill-split.json``.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ZONES_ROOT = ROOT / "artifacts/cache/mill_flow_zones"
ZONES_SCHEMA = "QRE2MILLZONES1"
MANIFEST_SCHEMA = "QRE2MILLZONESMANIFEST1"

# The frozen zone geometry.  Every number is a SHAPE constant of our own bytes
# (audit finding 3: no tick or dollar constant imported from any PDF survives),
# so the width scales with the asset's own ATR and the core band with its own
# tick.
ZONE_W_ATR = 0.15
MERGE_GAP_BARS = 5
CORE_TICKS = 2
HELD_BARS = 5
POST_BARS = 30

SIDE_TAG = {1: "lo", -1: "hi"}
SIDES = (1, -1)

# Column order of the per-episode table.  Stored in the sidecar so a reader can
# never drift from the writer.
EPISODE_COLUMNS = (
    "start", "end", "first_touch", "touches", "cum_attack", "cum_adelta",
    "cum_ext_ticks", "cum_opp_vol", "post_mfe_ticks", "post_mfe_atr",
    "dip_ticks", "dip_atr", "terminal",
)
EPISODE_INDEX = {name: position for position, name in enumerate(EPISODE_COLUMNS)}

# Bar-resolution series, per (cell, side).
SIDE_SERIES = (
    "in_zone", "touch", "run_ext_mid2", "run_ext_valid", "epi_open",
    "epi_start", "cum_attack", "cum_adelta", "cum_ext_ticks", "cum_opp_vol",
    "last_touch_bar", "touches_so_far", "held_so_far", "episodes_so_far",
    "attack", "reload",
)
# Bar-resolution series shared by both sides of one cell.
CELL_SERIES = ("delta", "vol", "twoside")

MUTANT_ENV = "QRE2_MILL_ZONES_MUTANT"
MUTANT_OWN_BAR = "zone_uses_own_bar"
ZONE_MUTANTS = (MUTANT_OWN_BAR,)


class ZoneStop(RuntimeError):
    """The zones cache is absent, malformed, or asked for the impossible."""


def _mutant() -> str:
    name = os.environ.get(MUTANT_ENV, "")
    if name and name not in ZONE_MUTANTS:
        raise ZoneStop(f"unknown zones mutant: {name}")
    return name


def running_extreme(mid: np.ndarray, side: int) -> tuple[np.ndarray, np.ndarray]:
    """``(value, valid)`` of the running session extreme read AT each bar close.

    ``side > 0`` fades a low, so its extreme is the running minimum.  The read at
    bar ``b`` covers bars ``0..b-1``: bar ``b`` has closed but it cannot be the
    level it is being measured against.  The mutant folds bar ``b`` into its own
    level, which makes every new extreme a zero-distance touch of itself.
    """

    values = np.asarray(mid, np.float64)
    accumulate = np.minimum.accumulate if int(side) > 0 else np.maximum.accumulate
    running = accumulate(values)
    out = np.empty(len(values), np.float64)
    valid = np.zeros(len(values), bool)
    if _mutant() == MUTANT_OWN_BAR:
        out[:] = running
        valid[:] = True
        return out, valid
    out[0] = values[0]
    valid[0] = False
    if len(values) > 1:
        out[1:] = running[:-1]
        valid[1:] = True
    return out, valid


def episode_spans(in_zone: np.ndarray, gap: int = MERGE_GAP_BARS
                  ) -> list[tuple[int, int]]:
    """Maximal in-zone runs, merged across gaps shorter than ``gap`` bars."""

    flags = np.asarray(in_zone, bool)
    marks = np.flatnonzero(flags)
    if not len(marks):
        return []
    breaks = np.flatnonzero(np.diff(marks) > 1)
    starts = np.concatenate(([marks[0]], marks[breaks + 1]))
    ends = np.concatenate((marks[breaks], [marks[-1]]))
    spans: list[tuple[int, int]] = []
    for start, end in zip(starts, ends, strict=True):
        if spans and int(start) - spans[-1][1] - 1 < int(gap):
            spans[-1] = (spans[-1][0], int(end))
            continue
        spans.append((int(start), int(end)))
    return spans


@dataclass(slots=True)
class ZoneSide:
    """One cell, one side: the bar series, the episode table, the units."""

    side: int
    tick2: float
    atr_mid2: float
    series: dict[str, np.ndarray]
    episodes: np.ndarray            # (n_episodes, len(EPISODE_COLUMNS))

    def column(self, name: str) -> np.ndarray:
        return self.episodes[:, EPISODE_INDEX[name]]


def _slope(values: np.ndarray) -> float:
    """Least-squares slope of ``values`` against bar ordinal, 0.0 when flat."""

    y = np.asarray(values, np.float64)
    if len(y) < 2:
        return 0.0
    x = np.arange(len(y), dtype=np.float64)
    x = x - x.mean()
    denominator = float((x * x).sum())
    return 0.0 if denominator <= 0.0 else float((x * (y - y.mean())).sum() / denominator)


def cell_side_zones(mid: np.ndarray, new_extreme: np.ndarray, attack: np.ndarray,
                    reload_volume: np.ndarray, delta: np.ndarray, vol: np.ndarray,
                    side: int, *, tick2: float, atr_mid2: float) -> ZoneSide:
    """The whole zone-episode law for one cell on one side.

    ``attack``, ``reload_volume``, ``delta`` and ``vol`` arrive already mapped
    onto the mill's 60 s bar lattice.  Everything the caller may read at bar
    ``b`` is truncated at ``b``; the per-episode table carries the completed
    figures the distributions are built from.
    """

    values = np.asarray(mid, np.float64)
    bars = len(values)
    direction = 1 if int(side) > 0 else -1
    extreme, valid = running_extreme(values, side)
    distance = np.abs(values - extreme)
    width = ZONE_W_ATR * float(atr_mid2)
    core = CORE_TICKS * float(tick2)
    in_zone = valid & (distance <= width)
    touch = in_zone & (distance <= core)

    # Attacking flow is the aggression pushing the extreme further out: sells at
    # a low, buys at a high.  Its opposite is the side that has to be POSITIVELY
    # present for absorption to mean anything (audit finding 1).
    signed = np.asarray(delta, np.float64)
    traded = np.asarray(vol, np.float64)
    attacking_delta = -signed if direction > 0 else signed
    # ``delta = buys - sells`` and ``vol = buys + sells``, so the side opposite
    # the attack is ``(vol + delta)/2`` at a low and ``(vol - delta)/2`` at a
    # high.  Clipped at zero because a bar can carry delta from trades the
    # trusted-message filter dropped from vol.
    opposite_volume = np.maximum(
        (traded + signed) / 2.0 if direction > 0 else (traded - signed) / 2.0,
        0.0)

    spans = episode_spans(in_zone)
    series: dict[str, np.ndarray] = {
        "in_zone": in_zone,
        "touch": touch,
        "run_ext_mid2": extreme,
        "run_ext_valid": valid,
        "epi_open": np.full(bars, -1, np.int64),
        "epi_start": np.full(bars, -1, np.int64),
        "cum_attack": np.zeros(bars, np.float64),
        "cum_adelta": np.zeros(bars, np.float64),
        "cum_ext_ticks": np.zeros(bars, np.float64),
        "cum_opp_vol": np.zeros(bars, np.float64),
        "last_touch_bar": np.full(bars, -1, np.int64),
        "touches_so_far": np.zeros(bars, np.int64),
        "held_so_far": np.zeros(bars, np.int64),
        "episodes_so_far": np.zeros(bars, np.int64),
        "attack": np.asarray(attack, np.float64),
        "reload": np.asarray(reload_volume, np.float64),
    }

    rows: list[list[float]] = []
    for number, (start, end) in enumerate(spans):
        window = slice(start, bars)
        anchor = float(extreme[start])
        # Running extreme INCLUDING the episode's own bars, so the extension is
        # the fresh ground the attack actually bought.
        inside = (np.minimum.accumulate(values[window]) if direction > 0
                  else np.maximum.accumulate(values[window]))
        pushed = ((anchor - inside) if direction > 0 else (inside - anchor))
        ext_ticks = np.maximum(pushed, 0.0) / float(tick2)
        span = slice(start, end + 1)
        series["epi_open"][span] = number
        series["epi_start"][span] = start
        series["cum_attack"][span] = np.cumsum(series["attack"][span])
        series["cum_adelta"][span] = np.cumsum(attacking_delta[span])
        series["cum_ext_ticks"][span] = ext_ticks[: end + 1 - start]
        series["cum_opp_vol"][span] = np.cumsum(opposite_volume[span])
        # After the episode ends its figures stay readable until the next one
        # opens: the confirmation of an absorption arrives once price has left.
        stop = spans[number + 1][0] if number + 1 < len(spans) else bars
        tail = slice(end + 1, stop)
        series["epi_open"][tail] = number
        series["epi_start"][tail] = start
        series["cum_attack"][tail] = series["cum_attack"][end]
        series["cum_adelta"][tail] = series["cum_adelta"][end]
        series["cum_ext_ticks"][tail] = series["cum_ext_ticks"][end]
        series["cum_opp_vol"][tail] = series["cum_opp_vol"][end]

        touches = np.flatnonzero(touch[span]) + start
        first_touch = int(touches[0]) if len(touches) else -1
        post = slice(end + 1, min(end + 1 + POST_BARS, bars))
        forward = values[post]
        if len(forward):
            move = (float(forward.max()) - values[end] if direction > 0
                    else values[end] - float(forward.min()))
        else:
            move = 0.0
        if first_touch >= 0:
            inner = values[first_touch: end + 1]
            dip = (values[first_touch] - float(inner.min()) if direction > 0
                   else float(inner.max()) - values[first_touch])
            dip = max(dip, 0.0)
        else:
            dip = float("nan")
        # The episode's own extreme: the level it opened on, or whatever deeper
        # level its bars printed.
        level = (min(anchor, float(inside[end - start])) if direction > 0
                 else max(anchor, float(inside[end - start])))
        after = values[end + 1:]
        terminal = (True if not len(after)
                    else bool(float(after.min()) >= level if direction > 0
                              else float(after.max()) <= level))
        rows.append([
            float(start), float(end), float(first_touch), float(len(touches)),
            float(series["cum_attack"][end]), float(series["cum_adelta"][end]),
            float(series["cum_ext_ticks"][end]), float(series["cum_opp_vol"][end]),
            move / float(tick2), move / float(atr_mid2),
            dip / float(tick2), dip / float(atr_mid2), float(terminal),
        ])

    marks = np.flatnonzero(touch)
    if len(marks):
        # ``last_touch_bar`` is a forward fill of the touch positions: at bar b
        # the most recent touch at or before b, -1 before the first.
        filled = np.maximum.accumulate(np.where(touch, np.arange(bars), -1))
        series["last_touch_bar"] = filled.astype(np.int64)
        series["touches_so_far"] = np.cumsum(touch).astype(np.int64)
        # A touch HELD only once its five-bar window has elapsed, so the count is
        # credited at the bar the verdict is known, never at the touch itself.
        held_at = np.zeros(bars, np.int64)
        flags = np.asarray(new_extreme, bool)
        for position in marks:
            resolve = min(int(position) + HELD_BARS, bars - 1)
            window = flags[int(position) + 1: resolve + 1]
            if not bool(window.any()):
                held_at[resolve] += 1
        series["held_so_far"] = np.cumsum(held_at).astype(np.int64)
    if spans:
        opened = np.zeros(bars, np.int64)
        for start, _end in spans:
            opened[start] += 1
        series["episodes_so_far"] = np.cumsum(opened).astype(np.int64)

    table = (np.asarray(rows, np.float64) if rows
             else np.zeros((0, len(EPISODE_COLUMNS)), np.float64))
    return ZoneSide(int(side), float(tick2), float(atr_mid2), series, table)


# --------------------------------------------------------------------------
# Read side.
# --------------------------------------------------------------------------

@dataclass(slots=True)
class ZoneCell:
    """One formation window's zone object: both sides plus the shared flow."""

    asset: str
    d8: int
    phase: str
    phase_open_ts_ns: int
    phase_close_ts_ns: int
    bars: int
    tick2: float
    atr_mid2: float
    shared: dict[str, np.ndarray]
    sides: dict[int, ZoneSide]


def load_zones(asset: str, d8: int, *, root: Path = ZONES_ROOT
               ) -> dict[tuple[str, int], ZoneCell]:
    """The day's zone cells keyed by ``(phase, phase_open_ts_ns)``."""

    directory = Path(root) / str(asset)
    npz_path = directory / f"{int(d8)}.npz"
    sidecar_path = directory / f"{int(d8)}.json"
    if not npz_path.is_file() or not sidecar_path.is_file():
        raise ZoneStop(f"zones shard is absent: {npz_path}")
    sidecar: Mapping[str, object] = json.loads(sidecar_path.read_text())
    if (sidecar.get("schema") != ZONES_SCHEMA or sidecar.get("asset") != asset
            or int(sidecar.get("d8", -1)) != int(d8)):
        raise ZoneStop(f"zones sidecar identity differs: {sidecar_path}")
    if tuple(sidecar.get("episode_columns", ())) != EPISODE_COLUMNS:
        raise ZoneStop(f"zones episode columns drifted: {sidecar_path}")
    out: dict[tuple[str, int], ZoneCell] = {}
    with np.load(npz_path) as store:
        for position, cell in enumerate(sidecar["cells"]):
            bars = int(cell["bars"])
            shared = {name: np.asarray(store[f"c{position}_{name}"])
                      for name in CELL_SERIES}
            sides: dict[int, ZoneSide] = {}
            for side in SIDES:
                tag = SIDE_TAG[side]
                series = {name: np.asarray(store[f"c{position}_{tag}_{name}"])
                          for name in SIDE_SERIES}
                if any(len(array) != bars for array in series.values()):
                    raise ZoneStop(
                        f"zones cell {position} of {asset}/{d8} is ragged")
                sides[side] = ZoneSide(
                    side, float(cell["tick2"]), float(cell["atr_mid2"]), series,
                    np.asarray(store[f"c{position}_{tag}_episodes"]))
            key = (str(cell["phase"]), int(cell["phase_open_ts_ns"]))
            if key in out:
                raise ZoneStop(f"zones cell key repeats in {asset}/{d8}: {key}")
            out[key] = ZoneCell(
                asset, int(d8), str(cell["phase"]),
                int(cell["phase_open_ts_ns"]), int(cell["phase_close_ts_ns"]),
                bars, float(cell["tick2"]), float(cell["atr_mid2"]), shared, sides)
    return out


def load_manifest(root: Path = ZONES_ROOT) -> Mapping[str, object]:
    path = Path(root) / "manifest.json"
    if not path.is_file():
        raise ZoneStop(f"zones manifest is absent: {path}")
    payload = json.loads(path.read_text())
    if payload.get("schema") != MANIFEST_SCHEMA:
        raise ZoneStop(f"zones manifest schema differs: {path}")
    return payload


def quantiles(values: Sequence[float], points: Sequence[float] = (25, 50, 75, 90)
              ) -> list[float | None]:
    """Linear-interpolation quantiles, ``None`` per point when there is no data."""

    array = np.asarray([float(value) for value in values], np.float64)
    array = array[np.isfinite(array)]
    if not len(array):
        return [None for _ in points]
    return [float(np.percentile(array, float(point))) for point in points]
