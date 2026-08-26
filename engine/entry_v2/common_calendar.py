"""Pinned QRE2 calendar, closures, and replay-denominator dispositions."""

from __future__ import annotations

import datetime as dt
import functools
import hashlib
import re

from .common import (
    ASSETS, EntryV2Refusal, QRE2_CALENDAR_PATH, QRE2_CALENDAR_SHA256, guard_date,
)


def is_globex_trading_day(d8: int) -> bool:
    """Return whether ``d8`` is a Monday-Friday Globex calendar row.

    The native calendar currently carries synthetic Sunday windows so prior-
    session locks remain auditable. This weekday primitive deliberately does
    not classify exchange closures; use :func:`is_denominator_day` for an
    asset-day performance denominator.
    """
    d8 = int(d8)
    guard_date(d8)
    try:
        day = dt.date(d8 // 10_000, (d8 // 100) % 100, d8 % 100)
    except ValueError as exc:
        raise EntryV2Refusal(f"invalid calendar date: {d8}") from exc
    return day.weekday() < 5


@functools.cache
def _qre2_calendar_authority(
) -> tuple[tuple[tuple[str, int], ...], frozenset[tuple[str, int]]]:
    """Load the sole byte-pinned QRE2 asset-coverage/closure authority."""
    try:
        raw = QRE2_CALENDAR_PATH.read_bytes()
    except OSError as exc:
        raise EntryV2Refusal("QRE2CAL1 authority is unavailable") from exc
    if hashlib.sha256(raw).hexdigest() != QRE2_CALENDAR_SHA256:
        raise EntryV2Refusal("QRE2CAL1 authority hash mismatch")
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise EntryV2Refusal("QRE2CAL1 authority is not UTF-8") from exc
    header = re.fullmatch(
        r"# QRE2CAL1 coverage_start_d8=(\d{8}) coverage_end_d8=(\d{8}) "
        r"audited_as_of_utc=2026-08-16T00:00:00Z "
        r"source_manifest_sha256=([0-9a-f]{64})",
        lines[0] if lines else "",
    )
    if header is None or (int(header.group(1)), int(header.group(2))) != (
            20210101, 20250630):
        raise EntryV2Refusal("QRE2CAL1 schema/coverage header mismatch")
    coverage: list[tuple[str, int]] = []
    cursor = 1
    while cursor < len(lines) and lines[cursor].startswith("# asset_coverage "):
        match = re.fullmatch(
            r"# asset_coverage (HG|NKD|SI) start_d8=(\d{8})",
            lines[cursor],
        )
        if match is None:
            raise EntryV2Refusal("QRE2CAL1 asset coverage is malformed")
        coverage.append((match.group(1), int(match.group(2))))
        cursor += 1
    if tuple(coverage) != (
        ("HG", 20210101), ("NKD", 20210101), ("SI", 20210531)
    ):
        raise EntryV2Refusal("QRE2CAL1 asset coverage differs from source manifest")
    sources: set[str] = set()
    while cursor < len(lines) and lines[cursor].startswith("# source "):
        fields = lines[cursor].split(" ", 3)
        if (len(fields) != 4 or not fields[2]
                or not fields[3].startswith("https://www.cmegroup.com/")):
            raise EntryV2Refusal("QRE2CAL1 source locator is invalid")
        if fields[2] in sources:
            raise EntryV2Refusal("QRE2CAL1 source ids are duplicated")
        sources.add(fields[2])
        cursor += 1
    columns = ("asset", "d8", "disposition", "holiday", "source_id")
    if cursor >= len(lines) or tuple(lines[cursor].split("\t")) != columns:
        raise EntryV2Refusal("QRE2CAL1 columns mismatch")
    cursor += 1
    closures: list[tuple[str, int]] = []
    previous: tuple[int, str] | None = None
    for line in lines[cursor:]:
        fields = line.split("\t")
        if len(fields) != len(columns):
            raise EntryV2Refusal("QRE2CAL1 row width mismatch")
        asset, d8_text, disposition, holiday, source_id = fields
        try:
            d8 = int(d8_text)
        except ValueError as exc:
            raise EntryV2Refusal("QRE2CAL1 date is malformed") from exc
        if (asset not in ASSETS or disposition != "FULL_CLOSE" or not holiday
                or source_id not in sources or not 20210101 <= d8 <= 20250630
                or not is_globex_trading_day(d8)):
            raise EntryV2Refusal("QRE2CAL1 row violates the frozen contract")
        order_key = (d8, asset)
        if previous is not None and order_key <= previous:
            raise EntryV2Refusal("QRE2CAL1 rows are duplicated or unsorted")
        previous = order_key
        closures.append((asset, d8))
    if not closures:
        raise EntryV2Refusal("QRE2CAL1 has no closure rows")
    return tuple(coverage), frozenset(closures)


def qre2_asset_coverage_start_d8(asset: str) -> int:
    """Return the first authenticated source date for an Entry V2 asset."""
    name = str(asset).upper()
    if name not in ASSETS:
        raise EntryV2Refusal(f"unsupported denominator asset: {asset!r}")
    return dict(_qre2_calendar_authority()[0])[name]


def qre2_full_closures() -> frozenset[tuple[str, int]]:
    """Return the frozen asset/date exchange full-closure set."""
    return _qre2_calendar_authority()[1]


def denominator_disposition(asset: str, d8: int) -> str:
    """Classify one asset/date without consulting market-data availability."""
    name = str(asset).upper()
    if name not in ASSETS:
        raise EntryV2Refusal(f"unsupported denominator asset: {asset!r}")
    d8 = int(d8)
    guard_date(d8)
    if d8 < qre2_asset_coverage_start_d8(name):
        return "OUTSIDE_ASSET_COVERAGE"
    if not is_globex_trading_day(d8):
        return "WEEKEND"
    if (name, d8) in qre2_full_closures():
        return "FULL_CLOSE"
    if d8 == _first_lockable_denominator_day(name):
        # The lock-law (recovery plan §2) binds each session to the dominant
        # contract of the immediately preceding completed session; the FIRST
        # covered session has no prior and is structurally untradeable, so it
        # is excluded from every replay denominator as a typed disposition.
        return "FIRST_SESSION_NO_LOCK"
    return "INCLUDE"


@functools.lru_cache(maxsize=None)
def _first_lockable_denominator_day(asset: str) -> int:
    """The asset's first trading day is lock-less ONLY when coverage opens
    directly on it: the calendar carries synthetic Sunday windows precisely
    so prior-session locks stay auditable, so any coverage gap before the
    first trading day supplies a lock donor (HG/NKD lock off the Sunday
    window; SI's coverage opens on a tradeable Monday with no prior row).
    Returns the coverage start when it is itself a tradeable day, else a
    sentinel that matches no real date."""
    d8 = qre2_asset_coverage_start_d8(asset)
    if is_globex_trading_day(d8) and (asset, d8) not in qre2_full_closures():
        return d8
    return -1


def is_denominator_day(asset: str, d8: int) -> bool:
    """True only for an included QRE2 asset trading day."""
    return denominator_disposition(asset, d8) == "INCLUDE"
