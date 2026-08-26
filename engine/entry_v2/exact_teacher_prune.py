"""Series-local dominance prune for the exact delayed teacher."""

from __future__ import annotations

import numpy as np

from .exact_teacher_types import DayOptionUniverse
from .tabular_recovery_contracts import RecoveryRefusal


class _FenwickMaximum:
    def __init__(self, size: int) -> None:
        self.values = np.full(size + 1, np.iinfo(np.int64).min, np.int64)

    def update(self, index: int, value: int) -> None:
        point = int(index) + 1
        while point < len(self.values):
            self.values[point] = max(int(self.values[point]), int(value))
            point += point & -point

    def prefix_max(self, index: int) -> int:
        point = int(index) + 1
        value = np.iinfo(np.int64).min
        while point > 0:
            value = max(value, int(self.values[point]))
            point -= point & -point
        return int(value)


def _dominance_pruned_arrays(
    series: np.ndarray, start: np.ndarray, end: np.ndarray,
    cents: np.ndarray, ids: np.ndarray,
) -> np.ndarray:
    """Return positions surviving exact series-local dominance."""

    series = np.asarray(series, str)
    start = np.asarray(start, np.int64)
    end = np.asarray(end, np.int64)
    cents = np.asarray(cents, np.int64)
    ids = np.asarray(ids, str)
    n = len(series)
    if any(len(value) != n for value in (start, end, cents, ids)):
        raise RecoveryRefusal("dominance inputs have different row counts")
    output: list[int] = []
    for key in sorted(set(series.tolist())):
        local = np.flatnonzero((series == key) & (cents > 0))
        if not len(local):
            continue
        end_values = np.asarray(sorted(set(end[local].tolist())), np.int64)
        end_rank = {int(value): index for index, value in enumerate(end_values)}
        tree = _FenwickMaximum(len(end_values))
        # Canonical order makes retained output invariant to source row order.
        order = local[np.lexsort((ids[local], end[local], -start[local]))]
        positions = 0
        while positions < len(order):
            batch_end = positions + 1
            while (batch_end < len(order)
                   and start[order[batch_end]] == start[order[positions]]):
                batch_end += 1
            batch = order[positions:batch_end]
            batch = batch[np.lexsort((ids[batch], -cents[batch], end[batch]))]
            same_start_best = np.iinfo(np.int64).min
            same_start_end = None
            kept: list[int] = []
            for index in batch:
                rank = end_rank[int(end[index])]
                later_best = tree.prefix_max(rank)
                same_dominates = (
                    same_start_best >= cents[index]
                    and (same_start_end is not None)
                    and (same_start_end < end[index]
                         or same_start_best > cents[index]))
                if later_best < cents[index] and not same_dominates:
                    kept.append(int(index))
                if cents[index] > same_start_best:
                    same_start_best = int(cents[index])
                    same_start_end = int(end[index])
                elif cents[index] == same_start_best:
                    same_start_end = min(int(end[index]), int(same_start_end))
            for index in kept:
                tree.update(end_rank[int(end[index])], int(cents[index]))
                output.append(index)
            positions = batch_end
    return np.asarray(sorted(output), np.int64)


def dominance_pruned_indices(universe: DayOptionUniverse) -> np.ndarray:
    """O(n log n) exact series-local dominance pruning.

    Option j dominates i only when it starts no earlier, exits no later, pays
    no less, and improves at least one of those three dimensions.  Zero and
    negative options are excluded from an unconstrained optimum but remain in
    the dense outcome shard for forced ENTER action values.
    """

    universe.validate()
    return _dominance_pruned_arrays(
        np.asarray(universe.series_id, str),
        np.asarray(universe.snapshot_ts_ns, np.int64),
        np.asarray(universe.exit_ts_ns, np.int64),
        np.asarray(universe.signed_pnl_cents, np.int64),
        np.asarray(universe.opportunity_id, str))


__all__ = ["dominance_pruned_indices"]
