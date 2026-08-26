#!/usr/bin/env python3
"""Frozen slow-context roster and tensor width."""

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

