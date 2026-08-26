#!/usr/bin/env python3
"""Shared units and refusal for the one-load diagnostic boundary."""

from __future__ import annotations

from types import MappingProxyType


UNITS_PER_USD = 2_000_000_000
MULTIPLIER = MappingProxyType({"SI": 5_000, "HG": 25_000, "NKD": 5})
RAW_TICK = MappingProxyType({"SI": 5_000_000, "HG": 500_000,
                             "NKD": 5_000_000_000})
F_MAYBE_BAD_BOOK = 4
F_BAD_TS_RECV = 8
F_SNAPSHOT = 32
SENTINEL_HIGH = 1 << 62


class DiagnosticInputRefusal(ValueError):
    pass
