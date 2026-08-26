"""Range and outcome indexes for confirmation labels."""

from __future__ import annotations

import math
from types import MappingProxyType
from typing import Mapping

import numpy as np

from .confirmation_types import (
    ConfirmationOutcome, ConfirmationRefusal, GOAL_USD, WALL_USD,
)
from .corpus_units import ASSET_MULTIPLIER


class _RangeIndex:
    """Segment-tree extrema and first-threshold queries over economic mids."""

    def __init__(self, values: np.ndarray) -> None:
        source = np.asarray(values, np.int64)
        size = 1
        while size < len(source):
            size *= 2
        self.length = len(source); self.size = size
        self.minimum = np.full(2 * size, np.iinfo(np.int64).max, np.int64)
        self.maximum = np.full(2 * size, np.iinfo(np.int64).min, np.int64)
        self.minimum[size:size + len(source)] = source
        self.maximum[size:size + len(source)] = source
        for node in range(size - 1, 0, -1):
            self.minimum[node] = min(self.minimum[2 * node], self.minimum[2 * node + 1])
            self.maximum[node] = max(self.maximum[2 * node], self.maximum[2 * node + 1])

    def extrema(self, left: int, right: int) -> tuple[int, int]:
        if not 0 <= left < right <= self.length:
            raise ConfirmationRefusal("range-extrema query is empty/outside")
        low = np.iinfo(np.int64).max; high = np.iinfo(np.int64).min
        a, b = left + self.size, right + self.size
        while a < b:
            if a & 1:
                low = min(low, int(self.minimum[a])); high = max(high, int(self.maximum[a])); a += 1
            if b & 1:
                b -= 1; low = min(low, int(self.minimum[b])); high = max(high, int(self.maximum[b]))
            a //= 2; b //= 2
        return int(low), int(high)

    def extrema_many(
        self, left: np.ndarray, right: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Vectorized half-open extrema for many independent ranges."""

        left = np.asarray(left, np.int64); right = np.asarray(right, np.int64)
        if (left.shape != right.shape or np.any(left < 0)
                or np.any(left >= right) or np.any(right > self.length)):
            raise ConfirmationRefusal("batched range-extrema query is invalid")
        a = left + self.size; b = right + self.size
        low = np.full(left.shape, np.iinfo(np.int64).max, np.int64)
        high = np.full(left.shape, np.iinfo(np.int64).min, np.int64)
        while np.any(a < b):
            take_a = (a < b) & ((a & 1) == 1)
            if np.any(take_a):
                low[take_a] = np.minimum(low[take_a], self.minimum[a[take_a]])
                high[take_a] = np.maximum(high[take_a], self.maximum[a[take_a]])
                a[take_a] += 1
            take_b = (a < b) & ((b & 1) == 1)
            if np.any(take_b):
                b[take_b] -= 1
                low[take_b] = np.minimum(low[take_b], self.minimum[b[take_b]])
                high[take_b] = np.maximum(high[take_b], self.maximum[b[take_b]])
            a //= 2; b //= 2
        return low, high

    def first_many(
        self, left: np.ndarray, right: np.ndarray, threshold: np.ndarray,
        *, use_min: bool,
    ) -> np.ndarray:
        """First dynamic threshold crossing for each half-open range."""

        left = np.asarray(left, np.int64); right = np.asarray(right, np.int64)
        threshold = np.asarray(threshold, np.int64)
        if left.shape != right.shape or left.shape != threshold.shape:
            raise ConfirmationRefusal("batched threshold query shapes differ")
        low_all, high_all = self.extrema_many(left, right)
        qualifies = (low_all <= threshold if use_min else high_all >= threshold)
        output = np.full(left.shape, -1, np.int64)
        if not np.any(qualifies):
            return output
        starts = left[qualifies]
        lo = starts.copy(); hi = right[qualifies] - 1
        limits = threshold[qualifies]
        while np.any(lo < hi):
            mid = (lo + hi) // 2
            lows, highs = self.extrema_many(starts, mid + 1)
            hit = lows <= limits if use_min else highs >= limits
            hi = np.where(hit, mid, hi)
            lo = np.where(hit, lo, mid + 1)
        output[qualifies] = lo
        return output

    def first_leq(self, left: int, right: int, threshold: int) -> int | None:
        return self._first(left, right, threshold, use_min=True)

    def first_geq(self, left: int, right: int, threshold: int) -> int | None:
        return self._first(left, right, threshold, use_min=False)

    def _first(self, left: int, right: int, threshold: int, *, use_min: bool) -> int | None:
        tree = self.minimum if use_min else self.maximum
        def qualifies(node: int) -> bool:
            return int(tree[node]) <= threshold if use_min else int(tree[node]) >= threshold
        def visit(node: int, lo: int, hi: int) -> int | None:
            if hi <= left or right <= lo or not qualifies(node):
                return None
            if node >= self.size:
                index = node - self.size
                return index if index < self.length else None
            mid = (lo + hi) // 2
            found = visit(node * 2, lo, mid)
            return found if found is not None else visit(node * 2 + 1, mid, hi)
        return visit(1, 0, self.size)


class _OutcomeIndex:
    def __init__(self, rows: np.ndarray, columns: Mapping[str, np.ndarray],
                 asset: str) -> None:
        economic = np.asarray(columns["trusted_economic"], bool)
        self.raw_rows = rows
        self.raw_ts = rows["ts_recv_ns"]
        self.raw_generation = np.asarray(columns["generation"], np.uint32)
        self.indices = np.flatnonzero(economic)
        self.ts = self.raw_ts[self.indices]
        self.mid2 = np.asarray(columns["mid2"], np.int64)[self.indices]
        self.generation = self.raw_generation[self.indices]
        self.multiplier = int(ASSET_MULTIPLIER[asset])
        self.factor = 0.5e-9 * self.multiplier
        self.range = _RangeIndex(self.mid2)
        self.generation_end = np.empty(len(self.generation), np.int64)
        boundaries = np.r_[0, np.flatnonzero(
            self.generation[1:] != self.generation[:-1]) + 1,
            len(self.generation)]
        for left, right in zip(boundaries[:-1], boundaries[1:]):
            self.generation_end[left:right] = right

    def current(self, snapshot_ts_ns: int) -> tuple[int, int, int, int, int] | None:
        position = int(np.searchsorted(
            self.ts, np.uint64(snapshot_ts_ns), side="left")) - 1
        if position < 0:
            return None
        raw_index = int(self.indices[position])
        row = self.raw_rows[raw_index]
        return (position, raw_index, int(row["bid_px"]), int(row["ask_px"]),
                int(self.mid2[position]))

    def generation_at_snapshot(self, snapshot_ts_ns: int) -> int | None:
        """Teacher generation at the strict raw cutoff.

        Events exactly at the snapshot are future.  The legacy teacher anchors
        generation from the first suffix row (``event_cutoff``), rather than
        silently carrying the last prefix generation through a reset.
        """

        cutoff = int(np.searchsorted(
            self.raw_ts, np.uint64(snapshot_ts_ns), side="left"))
        if cutoff < len(self.raw_generation):
            return int(self.raw_generation[cutoff])
        if cutoff:
            return int(self.raw_generation[cutoff - 1])
        return None

    def outcome(self, *, opportunity_id: str, snapshot_ts_ns: int,
                side: int, phase_close_ts_ns: int, entry_mid2: int,
                frozen_cost_usd: float, generation: int | None = None,
                ) -> ConfirmationOutcome | None:
        start = int(np.searchsorted(self.ts, np.uint64(snapshot_ts_ns), side="left"))
        end = int(np.searchsorted(self.ts, np.uint64(phase_close_ts_ns), side="right"))
        if start >= end:
            return None
        expected_generation = (int(self.generation[start]) if generation is None
                               else int(generation))
        local = np.flatnonzero(self.generation[start:end] != expected_generation)
        if len(local):
            end = start + int(local[0])
        if start >= end:
            return None

        # Find the first exact wall crossing without scanning the suffix.  Raw
        # mids are integer ticks; the derived boundary is widened by one raw
        # unit and the returned point is verified with the teacher arithmetic.
        if side > 0:
            boundary = math.floor(entry_mid2 + (-WALL_USD + frozen_cost_usd) / self.factor)
            wall = self.range.first_leq(start, end, boundary)
        else:
            boundary = math.ceil(entry_mid2 + (WALL_USD - frozen_cost_usd) / self.factor)
            wall = self.range.first_geq(start, end, boundary)
        exit_position = end - 1 if wall is None else int(wall)
        exit_mid = int(self.mid2[exit_position])
        cert = side * (exit_mid - entry_mid2) * self.factor - frozen_cost_usd
        if wall is not None and cert > -WALL_USD + 1e-9:
            raise ConfirmationRefusal("segment wall query did not reach exact wall")
        low, high = self.range.extrema(start, exit_position + 1)
        values = (
            side * (low - entry_mid2) * self.factor - frozen_cost_usd,
            side * (high - entry_mid2) * self.factor - frozen_cost_usd,
        )
        return ConfirmationOutcome(
            opportunity_id=opportunity_id,
            cert_close_usd=float(cert),
            mfe_usd=max(0.0, max(values)),
            mae_usd=max(0.0, -min(values)),
            wall_hit=wall is not None,
            exit_ts_ns=int(self.ts[exit_position]),
            goal_grade=bool(cert >= GOAL_USD),
        )

    def outcomes_many(
        self, *, snapshot_ts_ns: np.ndarray, side: int,
        phase_close_ts_ns: int, entry_mid2: np.ndarray,
        frozen_cost_usd: np.ndarray,
    ) -> Mapping[str, np.ndarray]:
        """Exact teacher outcomes for a batch of causal snapshot entries."""

        snapshots = np.asarray(snapshot_ts_ns, np.int64)
        entries = np.asarray(entry_mid2, np.int64)
        costs = np.asarray(frozen_cost_usd, np.float64)
        if (side not in (-1, 1) or snapshots.ndim != 1
                or entries.shape != snapshots.shape or costs.shape != snapshots.shape
                or not len(snapshots)):
            raise ConfirmationRefusal("batched outcome inputs are invalid")
        starts_all = np.searchsorted(
            self.ts, snapshots.astype(np.uint64), side="left")
        phase_end = int(np.searchsorted(
            self.ts, np.uint64(phase_close_ts_ns), side="right"))
        raw_cutoff_all = np.searchsorted(
            self.raw_ts, snapshots.astype(np.uint64), side="left")
        keep = np.flatnonzero(starts_all < phase_end)
        if not len(keep):
            raise ConfirmationRefusal("batched outcome has no certifiable suffix")
        starts = starts_all[keep]
        raw_generation_index = np.minimum(
            raw_cutoff_all[keep], len(self.raw_generation) - 1)
        expected_generation = self.raw_generation[raw_generation_index]
        ends = np.minimum(phase_end, self.generation_end[starts])
        valid = ((self.generation[starts] == expected_generation)
                 & (starts < ends))
        keep = keep[valid]; starts = starts[valid]; ends = ends[valid]
        if not len(keep):
            raise ConfirmationRefusal("batched outcome has no same-generation suffix")
        entries = entries[keep]; costs = costs[keep]
        if side > 0:
            threshold = np.floor(entries + (-WALL_USD + costs) / self.factor)
            wall = self.range.first_many(
                starts, ends, threshold.astype(np.int64), use_min=True)
        else:
            threshold = np.ceil(entries + (WALL_USD - costs) / self.factor)
            wall = self.range.first_many(
                starts, ends, threshold.astype(np.int64), use_min=False)
        exit_position = np.where(wall < 0, ends - 1, wall).astype(np.int64)
        exit_mid = self.mid2[exit_position]
        cert = side * (exit_mid - entries) * self.factor - costs
        if np.any((wall >= 0) & (cert > -WALL_USD + 1e-9)):
            raise ConfirmationRefusal("batched wall query did not reach exact wall")
        low, high = self.range.extrema_many(starts, exit_position + 1)
        low_value = side * (low - entries) * self.factor - costs
        high_value = side * (high - entries) * self.factor - costs
        return MappingProxyType({
            "input_index": keep.astype(np.int64),
            "cert_close_usd": cert.astype(np.float64),
            "mfe_usd": np.maximum(0.0, np.maximum(low_value, high_value)),
            "mae_usd": np.maximum(0.0, -np.minimum(low_value, high_value)),
            "wall_hit": wall >= 0,
            "exit_ts_ns": self.ts[exit_position].astype(np.int64),
        })
