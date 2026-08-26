#!/usr/bin/env python3
"""Fixed-width context tensors."""

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
    CONTEXT_FEATURE_NAMES, CONTEXT_TENSOR_WIDTH, CONTEXT_TYPE_ID,
    DELTA_OFFSET, DELTA_PRESENT_OFFSET, LOG_AGE_OFFSET, MAX_VALUE_WIDTH,
    NS, VALUE_OFFSET, VALUE_PRESENT_OFFSET,
)

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

