#!/usr/bin/env python3
"""Day-complete expanding/prequential folds for entry-v2."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, Sequence

import numpy as np

from . import common as C


DEVELOPMENT_FOLDS = tuple(f"E{index}" for index in range(3, 9))


@dataclass(frozen=True)
class FoldSpec:
    test_era: str
    train_start_d8: int
    train_end_d8: int
    test_start_d8: int
    test_end_d8: int
    fit_days: tuple[int, ...]
    inner_days: tuple[int, ...]
    test_days: tuple[int, ...]
    prequential_blocks: tuple[tuple[int, ...], ...]

    def validate(self) -> None:
        if self.test_era.startswith("E") and self.test_era not in DEVELOPMENT_FOLDS:
            raise C.EntryV2Refusal(
                f"{self.test_era}: entry-v2 development is fixed to E3-E8"
            )
        f, i, t = map(set, (self.fit_days, self.inner_days, self.test_days))
        if not self.fit_days or not self.inner_days or not self.test_days:
            raise C.EntryV2Refusal(f"{self.test_era}: empty fit/inner/test stage")
        if f & i or f & t or i & t:
            raise C.EntryV2Refusal(f"{self.test_era}: day overlap")
        if max(f) >= min(i) or max(i) >= min(t):
            raise C.EntryV2Refusal(f"{self.test_era}: non-causal day ordering")
        if any(d >= C.HOLDOUT_START_D8 for d in f | i | t):
            raise C.EntryV2Refusal(f"{self.test_era}: holdout reached development fold")
        if len(self.prequential_blocks) < 2:
            raise C.EntryV2Refusal(
                f"{self.test_era}: at least two prequential blocks are required"
            )
        prior: set[int] = set()
        for block in self.prequential_blocks:
            if not block:
                raise C.EntryV2Refusal(
                    f"{self.test_era}: empty prequential block"
                )
            b = set(block)
            if prior and max(prior) >= min(b):
                raise C.EntryV2Refusal(f"{self.test_era}: prequential block order")
            prior |= b
        if prior != i or sum(len(block) for block in self.prequential_blocks) != len(i):
            raise C.EntryV2Refusal(
                f"{self.test_era}: prequential blocks must partition inner_days exactly"
            )


def _split_contiguous(days: Sequence[int], n: int) -> tuple[tuple[int, ...], ...]:
    arr = np.asarray(sorted(set(int(x) for x in days)), dtype=np.int64)
    return tuple(tuple(int(x) for x in part.tolist())
                 for part in np.array_split(arr, n) if part.size)


def build_fold(test_era: str, available_days: Iterable[int],
               inner_fraction: float = 0.20,
               prequential_parts: int = 5) -> FoldSpec:
    era = {name: (lo, hi) for name, lo, hi in C.ERAS}
    if test_era not in DEVELOPMENT_FOLDS:
        raise C.EntryV2Refusal("test era must be E3..E8")
    lo, hi = era[test_era]
    days = np.asarray(sorted(set(int(x) for x in available_days)), dtype=np.int64)
    # Pre-E1 2021 days are the honest bootstrap history.  In production the
    # supplied days are the union of eligible asset-session calendars, so E1
    # is OOF without dropping a valid asset-session merely because another
    # asset lacked a lock on that date.
    train = days[days < lo]
    test = days[(days >= lo) & (days <= hi)]
    if train.size < 20 or test.size == 0:
        raise C.EntryV2Refusal(f"{test_era}: insufficient days")
    cut = int(np.floor(train.size * (1.0 - float(inner_fraction))))
    cut = min(max(cut, 10), train.size - 5)
    fit, inner = train[:cut], train[cut:]
    # The prequential calibration path starts with the fit block as history;
    # its ordered blocks cover the inner days without ever fitting on a future
    # day.  A caller trains on fit + all preceding blocks and scores the next.
    blocks = _split_contiguous(inner, min(prequential_parts, inner.size))
    spec = FoldSpec(test_era, int(train.min()), int(train.max()), lo, hi,
                    tuple(map(int, fit)), tuple(map(int, inner)),
                    tuple(map(int, test)), blocks)
    spec.validate()
    return spec


def build_ladder(available_days: Iterable[int]) -> tuple[FoldSpec, ...]:
    days = tuple(sorted(set(int(x) for x in available_days)))
    out = tuple(build_fold(name, days) for name in DEVELOPMENT_FOLDS)
    # A development day is test exactly once in the ladder.
    seen: set[int] = set()
    for spec in out:
        overlap = seen & set(spec.test_days)
        if overlap:
            raise C.EntryV2Refusal(f"test day reused: {sorted(overlap)[:3]}")
        seen |= set(spec.test_days)
    return out


def write_ladder(path, folds: Sequence[FoldSpec]) -> str:
    for f in folds:
        f.validate()
    return C.atomic_json(path, {"schema": "entry-v2-fold-ladder-v2",
                                "created_at_utc": C.utc_now(),
                                "folds": [asdict(f) for f in folds]})
