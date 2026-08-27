#!/usr/bin/env python3
"""Query library over the mill substrate.

Every number here comes from the frozen outcome law replayed on cached raw
suffixes: entry at the last trusted quote strictly before ``t``, cost =
spread x multiplier + fee, exit at the first exact -900 wall crossing or the
last same-generation row at/before phase close.  The wall search reuses the
engine segment tree; the generation always comes from the whole-pack raw
arrays under the strict raw cutoff, never from the reconstructed index.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from functools import cached_property
import json
import math
import os
from pathlib import Path
import sys
from types import MappingProxyType
from typing import Iterator, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.entry_v2.confirmation_index import _OutcomeIndex, _RangeIndex  # noqa: F401
from engine.entry_v2.confirmation_types import (
    ConfirmationOutcome, FEE_USD, GOAL_USD, NANOS_PER_SECOND, WALL_USD,
)
from engine.entry_v2.corpus_units import ASSET_MULTIPLIER

MILL_ROOT = ROOT / "artifacts/cache/mill"
SPLIT_PATH = ROOT / ".audit/mill-split.json"
MINIMAL_DTYPE = np.dtype([("ts_recv_ns", "<u8"), ("bid_px", "<i8"), ("ask_px", "<i8")])
# Sweep-tier mutants live beside the substrate mutants so one env var names
# every red case.  They are inert unless a sweep asks for ``bar_positions``
# (``sweep_uses_bar_at_t``) or fits a walk-forward model
# (``sweep2_train_includes_today``, read by ``sweep2.py`` alone) or tests a
# depth zone (``sweep3_zone_uses_close``, read by ``sweep3.py`` alone); the
# mill itself never branches on the sweep-2 or sweep-3 names.
SWEEP_MUTANTS = ("sweep_uses_bar_at_t", "sweep2_train_includes_today",
                 "sweep3_zone_uses_close")
MUTANTS = ("visibility_at_t", "wall_boundary_off_by_one",
           "generation_carryover") + SWEEP_MUTANTS


class MillRefusal(RuntimeError):
    pass


def _mutant() -> str:
    name = os.environ.get("QRE2_MILL_MUTANT", "")
    if name and name not in MUTANTS:
        raise MillRefusal(f"unknown mill mutant: {name}")
    return name


def frozen_cost_usd(bid: int, ask: int, asset: str) -> float:
    """The frozen entry cost.  Float is exact enough for mill sweeps."""

    return (int(ask) - int(bid)) * ASSET_MULTIPLIER[asset] / 1e9 + FEE_USD


def frozen_cost_usd_exact(bid: int, ask: int, asset: str) -> float:
    """The teacher's Decimal arithmetic, then one float rounding (B5 law)."""

    return float(Decimal(int(ask) - int(bid)) * Decimal(ASSET_MULTIPLIER[asset])
                 / Decimal(NANOS_PER_SECOND) + Decimal(str(FEE_USD)))


class MillIndex:
    """Per (shard, truth_quality_key) replay of the frozen outcome law."""

    def __init__(self, asset: str, ts: np.ndarray, mid2: np.ndarray,
                 bid: np.ndarray, ask: np.ndarray, generation: np.ndarray,
                 raw_ts: np.ndarray, raw_generation: np.ndarray) -> None:
        self.asset = asset
        self.multiplier = int(ASSET_MULTIPLIER[asset])
        self.factor = 0.5e-9 * self.multiplier
        self.bid = np.asarray(bid, np.int64)
        self.ask = np.asarray(ask, np.int64)
        self.raw_ts = np.asarray(raw_ts, np.int64).view(np.uint64)
        self.raw_generation = np.asarray(raw_generation, np.uint32)
        rows = np.empty(len(ts), MINIMAL_DTYPE)
        rows["ts_recv_ns"] = np.asarray(ts, np.int64).view(np.uint64)
        rows["bid_px"] = self.bid
        rows["ask_px"] = self.ask
        columns = {"trusted_economic": np.ones(len(ts), bool),
                   "mid2": np.asarray(mid2, np.int64),
                   "generation": np.asarray(generation, np.uint32)}
        self._engine = _OutcomeIndex(rows, columns, asset)
        self.ts = self._engine.ts
        self.mid2 = self._engine.mid2
        self.generation = self._engine.generation
        self.range = self._engine.range
        self.mutant = _mutant()

    def __len__(self) -> int:
        return int(len(self.ts))

    def position(self, t_ns: int) -> int | None:
        """Index of the last trusted row strictly before ``t_ns``."""

        side = "right" if self.mutant == "visibility_at_t" else "left"
        found = int(np.searchsorted(self.ts, np.uint64(int(t_ns)), side=side)) - 1
        return None if found < 0 else found

    def positions(self, t_ns: np.ndarray) -> np.ndarray:
        side = "right" if self.mutant == "visibility_at_t" else "left"
        return np.searchsorted(
            self.ts, np.asarray(t_ns, np.int64).astype(np.uint64), side=side) - 1

    def current(self, t_ns: int) -> tuple[int, int, int] | None:
        found = self.position(t_ns)
        if found is None:
            return None
        return (int(self.bid[found]), int(self.ask[found]), int(self.mid2[found]))

    def generation_at_snapshot(self, t_ns: int) -> int | None:
        """Generation at the strict raw cutoff (confirmation_index:153-167)."""

        cutoff = int(np.searchsorted(self.raw_ts, np.uint64(int(t_ns)), side="left"))
        if cutoff < len(self.raw_generation):
            return int(self.raw_generation[cutoff])
        if cutoff:
            return int(self.raw_generation[cutoff - 1])
        return None

    def generations_at_snapshots(self, t_ns: np.ndarray) -> np.ndarray:
        cutoff = np.searchsorted(
            self.raw_ts, np.asarray(t_ns, np.int64).astype(np.uint64), side="left")
        return self.raw_generation[
            np.minimum(cutoff, len(self.raw_generation) - 1)]

    def cost_at(self, t_ns: int, *, exact: bool = False) -> float | None:
        quote = self.current(t_ns)
        if quote is None:
            return None
        maker = frozen_cost_usd_exact if exact else frozen_cost_usd
        return maker(quote[0], quote[1], self.asset)

    def outcome(self, t_ns: int, side: int, entry_mid2: int, cost_usd: float,
                phase_close_ts_ns: int, *, generation: int | None = None,
                opportunity_id: str = "MILL") -> ConfirmationOutcome | None:
        if generation is None:
            generation = self.generation_at_snapshot(t_ns)
        if self.mutant in {"wall_boundary_off_by_one", "generation_carryover"}:
            return self.outcome_mirror(t_ns, side, entry_mid2, cost_usd,
                                       phase_close_ts_ns, generation=generation,
                                       opportunity_id=opportunity_id)
        return self._engine.outcome(
            opportunity_id=opportunity_id, snapshot_ts_ns=int(t_ns), side=int(side),
            phase_close_ts_ns=int(phase_close_ts_ns), entry_mid2=int(entry_mid2),
            frozen_cost_usd=float(cost_usd), generation=generation)

    def outcome_mirror(self, t_ns: int, side: int, entry_mid2: int, cost_usd: float,
                       phase_close_ts_ns: int, *, generation: int | None = None,
                       opportunity_id: str = "MILL") -> ConfirmationOutcome | None:
        """Line-for-line mirror of ``_OutcomeIndex.outcome`` (169-212)."""

        if generation is None:
            generation = self.generation_at_snapshot(t_ns)
        start = int(np.searchsorted(self.ts, np.uint64(int(t_ns)), side="left"))
        end = int(np.searchsorted(
            self.ts, np.uint64(int(phase_close_ts_ns)), side="right"))
        if start >= end:
            return None
        expected = (int(self.generation[start]) if generation is None
                    else int(generation))
        if self.mutant != "generation_carryover":
            local = np.flatnonzero(self.generation[start:end] != expected)
            if len(local):
                end = start + int(local[0])
        if start >= end:
            return None
        entry_mid2 = int(entry_mid2)
        cost_usd = float(cost_usd)
        if side > 0:
            boundary = math.floor(entry_mid2 + (-WALL_USD + cost_usd) / self.factor)
            if self.mutant == "wall_boundary_off_by_one":
                boundary -= 1
            wall = self.range.first_leq(start, end, boundary)
        else:
            boundary = math.ceil(entry_mid2 + (WALL_USD - cost_usd) / self.factor)
            if self.mutant == "wall_boundary_off_by_one":
                boundary += 1
            wall = self.range.first_geq(start, end, boundary)
        exit_position = end - 1 if wall is None else int(wall)
        exit_mid = int(self.mid2[exit_position])
        cert = side * (exit_mid - entry_mid2) * self.factor - cost_usd
        low, high = self.range.extrema(start, exit_position + 1)
        values = (side * (low - entry_mid2) * self.factor - cost_usd,
                  side * (high - entry_mid2) * self.factor - cost_usd)
        return ConfirmationOutcome(
            opportunity_id=opportunity_id, cert_close_usd=float(cert),
            mfe_usd=max(0.0, max(values)), mae_usd=max(0.0, -min(values)),
            wall_hit=wall is not None, exit_ts_ns=int(self.ts[exit_position]),
            goal_grade=bool(cert >= GOAL_USD))

    def outcomes_grid(self, t_ns: np.ndarray, side: int, phase_close_ts_ns: int,
                      *, entry_mid2: np.ndarray | None = None,
                      cost_usd: np.ndarray | None = None,
                      ) -> Mapping[str, np.ndarray]:
        """Vectorized ``outcomes_many`` (214-271) with the raw generation law.

        Entries without a strictly-earlier trusted quote, without a suffix, or
        whose entry row sits in a stale generation are dropped, never raised;
        ``input_index`` names the survivors.
        """

        snapshots = np.asarray(t_ns, np.int64)
        if snapshots.ndim != 1 or int(side) not in (-1, 1):
            raise MillRefusal("grid inputs are invalid")
        empty = self._empty_grid()
        if not len(snapshots) or not len(self.ts):
            return empty
        quote_at = self.positions(snapshots)
        starts_all = np.searchsorted(
            self.ts, snapshots.astype(np.uint64), side="left")
        phase_end = int(np.searchsorted(
            self.ts, np.uint64(int(phase_close_ts_ns)), side="right"))
        keep = np.flatnonzero((starts_all < phase_end) & (quote_at >= 0))
        if not len(keep):
            return empty
        starts = starts_all[keep]
        entries = (self.mid2[quote_at[keep]] if entry_mid2 is None
                   else np.asarray(entry_mid2, np.int64)[keep])
        costs = ((self.ask[quote_at[keep]] - self.bid[quote_at[keep]])
                 * self.multiplier / 1e9 + FEE_USD if cost_usd is None
                 else np.asarray(cost_usd, np.float64)[keep])
        expected = self.generations_at_snapshots(snapshots[keep])
        ends = np.minimum(phase_end, self._engine.generation_end[starts])
        if self.mutant == "generation_carryover":
            ends = np.full(len(starts), phase_end, np.int64)
            valid = starts < ends
        else:
            valid = (self.generation[starts] == expected) & (starts < ends)
        keep = keep[valid]
        if not len(keep):
            return empty
        starts = starts[valid]
        ends = ends[valid]
        entries = np.asarray(entries, np.int64)[valid]
        costs = np.asarray(costs, np.float64)[valid]
        if side > 0:
            threshold = np.floor(entries + (-WALL_USD + costs) / self.factor)
            if self.mutant == "wall_boundary_off_by_one":
                threshold -= 1.0
            wall = self.range.first_many(
                starts, ends, threshold.astype(np.int64), use_min=True)
        else:
            threshold = np.ceil(entries + (WALL_USD - costs) / self.factor)
            if self.mutant == "wall_boundary_off_by_one":
                threshold += 1.0
            wall = self.range.first_many(
                starts, ends, threshold.astype(np.int64), use_min=False)
        exit_position = np.where(wall < 0, ends - 1, wall).astype(np.int64)
        exit_mid = self.mid2[exit_position]
        cert = side * (exit_mid - entries) * self.factor - costs
        low, high = self.range.extrema_many(starts, exit_position + 1)
        low_value = side * (low - entries) * self.factor - costs
        high_value = side * (high - entries) * self.factor - costs
        return MappingProxyType({
            "input_index": keep.astype(np.int64),
            "entry_mid2": entries,
            "frozen_cost_usd": costs,
            "cert_close_usd": cert.astype(np.float64),
            "mfe_usd": np.maximum(0.0, np.maximum(low_value, high_value)),
            "mae_usd": np.maximum(0.0, -np.minimum(low_value, high_value)),
            "wall_hit": wall >= 0,
            "exit_ts_ns": self.ts[exit_position].astype(np.int64),
        })

    @staticmethod
    def _empty_grid() -> Mapping[str, np.ndarray]:
        return MappingProxyType({
            "input_index": np.zeros(0, np.int64),
            "entry_mid2": np.zeros(0, np.int64),
            "frozen_cost_usd": np.zeros(0, np.float64),
            "cert_close_usd": np.zeros(0, np.float64),
            "mfe_usd": np.zeros(0, np.float64), "mae_usd": np.zeros(0, np.float64),
            "wall_hit": np.zeros(0, bool), "exit_ts_ns": np.zeros(0, np.int64),
        })


def bar_positions(index: MillIndex, t_ns: np.ndarray) -> np.ndarray:
    """Rows a 60 s bar closing at ``t_ns`` may read.

    The bar covering ``(t-60s, t]`` closes at ``t`` and its value is the last
    trusted row with ``ts`` STRICTLY before ``t``; a row stamped exactly at the
    close is future.  ``-1`` means the cell has no trusted row before the
    close.  ``QRE2_MILL_MUTANT=sweep_uses_bar_at_t`` admits the row at ``t``
    and is the red case for every sweep built on this sampler.
    """

    side = "right" if _mutant() == "sweep_uses_bar_at_t" else "left"
    return np.searchsorted(
        index.ts, np.asarray(t_ns, np.int64).astype(np.uint64), side=side) - 1


def bar_series(index: MillIndex, t_ns: np.ndarray
               ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """``(positions, mid2, bid, ask)`` sampled by :func:`bar_positions`.

    Positions clamp at row 0 so a lattice point before the first trusted row
    still has a defined feature value; ``positions < 0`` names those points so
    a caller that needs a legal quote can drop them.
    """

    positions = bar_positions(index, t_ns)
    taken = np.maximum(positions, 0)
    if not len(index.ts):
        empty = np.zeros(len(taken), np.int64)
        return positions, empty, empty, empty
    return (positions, index.mid2[taken].astype(np.int64),
            index.bid[taken].astype(np.int64), index.ask[taken].astype(np.int64))


@dataclass(frozen=True, slots=True)
class Cell:
    """B4 cell identity: (asset, d8, phase, phase_open_ts_ns)."""

    asset: str
    d8: int
    phase: str
    phase_idx: int
    phase_open_ts_ns: int
    phase_close_ts_ns: int
    quality_idx: int
    rows: tuple[int, ...]
    anchor_candidate_id: str
    anchor_entry_mid2: int
    first_formation_ts_ns: int

    @property
    def text(self) -> str:
        return (f"{self.asset}/{self.d8}/{self.phase}/"
                f"{self.phase_open_ts_ns // NANOS_PER_SECOND}")


class Shard:
    """One EXPLORE asset-day of cached substrate."""

    def __init__(self, path: Path) -> None:
        self.npz_path = Path(path)
        self.json_path = self.npz_path.with_suffix(".json")
        self.meta = json.loads(self.json_path.read_text())
        if self.meta.get("schema") != "QRE2MILLSUBSTRATE1":
            raise MillRefusal(f"substrate schema differs: {self.npz_path}")
        self._data = np.load(self.npz_path)
        self.asset = str(self.meta["asset"])
        self.d8 = int(self.meta["d8"])
        self.locked_iid = int(self.meta["locked_iid"])
        self.open_utc = int(self.meta["open_utc"])
        self.close_utc = int(self.meta["close_utc"])
        self.multiplier = int(self.meta["multiplier"])
        self.phases = tuple(str(name) for name in self.meta["phases"])
        self.candidate_ids = tuple(str(name) for name in self.meta["candidate_ids"])
        self.quality_keys = tuple(tuple(int(v) for v in key)
                                  for key in self.meta["quality_keys"])
        self.decision_ts_ns = self._data["cand_decision_ts_ns"]
        self.side = self._data["cand_side"].astype(np.int64)
        self.phase_idx = self._data["cand_phase_idx"].astype(np.int64)
        self.phase_open_ts_ns = self._data["cand_phase_open_ts_ns"]
        self.phase_close_ts_ns = self._data["cand_phase_close_ts_ns"]
        self.entry_mid2 = self._data["cand_entry_mid2"]
        self.quality_idx = self._data["cand_quality_idx"].astype(np.int64)
        self.raw_ts = self._data["raw_ts"]
        self.raw_generation = self._data["raw_generation"]
        self._indices: dict[int, MillIndex] = {}
        self._cells = self._build_cells()
        self._by_key = {(cell.phase, cell.phase_open_ts_ns): cell
                        for cell in self._cells}

    def _build_cells(self) -> tuple[Cell, ...]:
        groups: dict[tuple[int, int], list[int]] = {}
        for row in range(len(self.candidate_ids)):
            groups.setdefault(
                (int(self.phase_idx[row]), int(self.phase_open_ts_ns[row])), []
            ).append(row)
        cells: list[Cell] = []
        for (phase_idx, open_ns), rows in sorted(groups.items()):
            ordered = sorted(rows, key=lambda row: (int(self.decision_ts_ns[row]),
                                                    self.candidate_ids[row]))
            anchor = ordered[0]
            close = {int(self.phase_close_ts_ns[row]) for row in ordered}
            if len(close) != 1:
                raise MillRefusal(f"phase instance identity differs: {self.asset}/{self.d8}")
            cells.append(Cell(
                self.asset, self.d8, self.phases[phase_idx], phase_idx, open_ns,
                close.pop(), int(self.quality_idx[anchor]), tuple(ordered),
                self.candidate_ids[anchor], int(self.entry_mid2[anchor]),
                int(self.decision_ts_ns[anchor])))
        return tuple(cells)

    @property
    def cells(self) -> tuple[Cell, ...]:
        return self._cells

    def cell(self, phase: str, phase_open_ts_ns: int) -> Cell:
        return self._by_key[(str(phase), int(phase_open_ts_ns))]

    def index(self, quality_idx: int) -> MillIndex:
        key = int(quality_idx)
        if key not in self._indices:
            self._indices[key] = MillIndex(
                self.asset, self._data[f"q{key}_ts"], self._data[f"q{key}_mid2"],
                self._data[f"q{key}_bid"], self._data[f"q{key}_ask"],
                self._data[f"q{key}_generation"], self.raw_ts, self.raw_generation)
        return self._indices[key]

    def cell_index(self, cell: Cell) -> MillIndex:
        return self.index(cell.quality_idx)

    def roster(self, cell: Cell, timer_ns: int) -> tuple[int, ...]:
        """CLEAR formations with decision_ts_ns <= timer (B5 ``_formed_roster``)."""

        return tuple(row for row in cell.rows
                     if int(self.decision_ts_ns[row]) <= int(timer_ns))

    def entry_valid(self, cell: Cell, t_ns: int) -> bool:
        if not cell.phase_open_ts_ns <= int(t_ns) < cell.phase_close_ts_ns:
            return False
        quote = self.cell_index(cell).current(int(t_ns))
        return quote is not None and 0 < quote[0] < quote[1]

    def outcome_at(self, cell: Cell, side: int, t_ns: int, *, exact_cost: bool = False,
                   ) -> ConfirmationOutcome | None:
        """Frozen-law cert for entering ``cell`` on ``side`` at ``t_ns``."""

        if not cell.phase_open_ts_ns <= int(t_ns) < cell.phase_close_ts_ns:
            return None
        index = self.cell_index(cell)
        quote = index.current(int(t_ns))
        if quote is None or not 0 < quote[0] < quote[1]:
            return None
        maker = frozen_cost_usd_exact if exact_cost else frozen_cost_usd
        return index.outcome(int(t_ns), int(side), quote[2],
                             maker(quote[0], quote[1], self.asset),
                             int(cell.phase_close_ts_ns))

    def outcomes_grid(self, cell: Cell, side: int, t_array: np.ndarray
                      ) -> Mapping[str, np.ndarray]:
        times = np.asarray(t_array, np.int64)
        inside = (times >= cell.phase_open_ts_ns) & (times < cell.phase_close_ts_ns)
        if not bool(np.all(inside)):
            times = times[inside]
            grid = self.cell_index(cell).outcomes_grid(
                times, int(side), int(cell.phase_close_ts_ns))
            mapped = np.flatnonzero(inside)[grid["input_index"]]
            return MappingProxyType({**grid, "input_index": mapped})
        return self.cell_index(cell).outcomes_grid(
            times, int(side), int(cell.phase_close_ts_ns))

    def close(self) -> None:
        self._data.close()


def load_shard(asset: str, d8: int, *, root: Path = MILL_ROOT) -> Shard:
    return Shard(Path(root) / str(asset) / f"{int(d8)}.npz")


class CellStore:
    """Lazy shard store over an explore roster."""

    def __init__(self, days: Sequence[tuple[str, int]], root: Path = MILL_ROOT) -> None:
        self.days = tuple(days)
        self.root = Path(root)

    def __len__(self) -> int:
        return len(self.days)

    @cached_property
    def assets(self) -> tuple[str, ...]:
        return tuple(sorted({asset for asset, _day in self.days}))

    def shards(self) -> Iterator[Shard]:
        for asset, d8 in self.days:
            shard = load_shard(asset, d8, root=self.root)
            try:
                yield shard
            finally:
                shard.close()


def load_store(split: Mapping[str, object] | str | Path = SPLIT_PATH,
               assets: Sequence[str] = ("HG", "NKD", "SI"),
               *, root: Path = MILL_ROOT) -> CellStore:
    if isinstance(split, (str, Path)):
        split = json.loads(Path(split).read_text())
    table = split["explore"]
    days = [(asset, int(day)) for asset in assets for day in sorted(table[asset])]
    return CellStore(tuple(days), root)


__all__ = ["Cell", "CellStore", "MillIndex", "MillRefusal", "Shard",
           "bar_positions", "bar_series", "frozen_cost_usd",
           "frozen_cost_usd_exact", "load_shard", "load_store"]
