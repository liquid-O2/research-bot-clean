#!/usr/bin/env python3
"""Point-in-time D-077 calendar builder.

The C++ candidate lane deliberately understands only two facts: a decision is
inside a proven coverage interval, and/or it is inside a prohibited interval.
This module is the provenance boundary that is allowed to construct those
facts.  It never treats absence from an event list as proof of coverage.
"""

from __future__ import annotations

import argparse
import calendar
from dataclasses import asdict, dataclass
import datetime as dt
import gzip
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

from engine.entry_v2 import common as C


NS = 1_000_000_000
WINDOW_NS = 10 * 60 * NS
NY = ZoneInfo("America/New_York")
UTC = dt.timezone.utc
SCHEMA = "entry-v2-compliance-source-manifest-v1"
CPP_SCHEMA = "QRE2COMPLIANCE1"
DEVELOPMENT_START_D8 = 20210101
DEVELOPMENT_END_EXCLUSIVE_D8 = C.HOLDOUT_START_D8

_SHA256 = re.compile(r"[0-9a-f]{64}")
_MONTHS = {name: number for number, name in enumerate(calendar.month_name) if name}
_MONTH_TOKEN = "|".join(calendar.month_name[1:])


@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    kind: str
    coverage_year: int | None
    availability_ts_ns: int
    path: str
    sha256: str
    program: str | None = None


@dataclass(frozen=True)
class ParsedEvent:
    calendar_id: str
    event_key: str
    event_ts_ns: int
    availability_ts_ns: int
    provenance_sha256: str


@dataclass(frozen=True)
class ComplianceRow:
    kind: str
    interval_id: str
    start_ts_ns: int
    end_ts_ns: int
    availability_ts_ns: int
    provenance_sha256: str

    def validate(self) -> None:
        if self.kind not in ("COVERAGE", "PROHIBITED"):
            raise C.EntryV2Refusal(f"invalid compliance row kind: {self.kind}")
        if not self.interval_id or any(ch in self.interval_id for ch in "\t\r\n"):
            raise C.EntryV2Refusal("invalid compliance interval id")
        if not (0 < self.availability_ts_ns and self.start_ts_ns <= self.end_ts_ns):
            raise C.EntryV2Refusal("invalid compliance interval clocks")
        if not _SHA256.fullmatch(self.provenance_sha256):
            raise C.EntryV2Refusal("invalid compliance provenance hash")
        if self.kind == "PROHIBITED" and self.end_ts_ns - self.start_ts_ns != 2 * WINDOW_NS:
            raise C.EntryV2Refusal("D-077 interval is not exactly [-10,+10] minutes")
        if self.start_ts_ns >= _wall_ns() or self.end_ts_ns >= _wall_ns():
            raise C.EntryV2Refusal("compliance row crosses the sealed 2025H2 wall")


@dataclass(frozen=True)
class ComplianceBuild:
    rows: tuple[ComplianceRow, ...]
    receipt: Mapping[str, Any]


@dataclass(frozen=True)
class _Snapshot:
    spec: SourceSpec
    sha256: str
    parsed_events: tuple[ParsedEvent, ...]
    complete: bool
    completeness_keys: tuple[str, ...]


class _ReleaseTableParser(HTMLParser):
    """Extract only cells from BLS' ``table.release-list``."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.table_depth = 0
        self.in_target = False
        self.in_cell = False
        self.cell_parts: list[str] = []
        self.row: list[str] = []
        self.rows: list[tuple[str, ...]] = []
        self.all_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "table":
            if self.in_target:
                self.table_depth += 1
            elif "release-list" in (values.get("class") or "").split():
                self.in_target = True
                self.table_depth = 1
        elif self.in_target and tag == "tr":
            self.row = []
        elif self.in_target and tag == "td":
            self.in_cell = True
            self.cell_parts = []

    def handle_endtag(self, tag: str) -> None:
        if self.in_target and tag == "td" and self.in_cell:
            self.row.append(" ".join(" ".join(self.cell_parts).split()))
            self.in_cell = False
        elif self.in_target and tag == "tr":
            if self.row:
                self.rows.append(tuple(self.row))
            self.row = []
        elif self.in_target and tag == "table":
            self.table_depth -= 1
            if self.table_depth == 0:
                self.in_target = False

    def handle_data(self, data: str) -> None:
        clean = " ".join(data.split())
        if clean:
            self.all_text.append(clean)
            if self.in_target and self.in_cell:
                self.cell_parts.append(clean)


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        clean = " ".join(data.split())
        if clean:
            self.parts.append(clean)


def _d8(value: dt.date) -> int:
    return value.year * 10_000 + value.month * 100 + value.day


def _utc_ns(value: dt.datetime) -> int:
    if value.tzinfo is None:
        raise C.EntryV2Refusal("naive datetime at compliance boundary")
    return int(value.timestamp()) * NS


def _wall_ns() -> int:
    return _utc_ns(dt.datetime(2025, 7, 1, tzinfo=UTC))


def _development_start_ns() -> int:
    return _utc_ns(dt.datetime(2021, 1, 1, tzinfo=UTC))


def _parse_release_date(value: str) -> dt.date:
    normalized = re.sub(r"\bSept\.", "Sep.", value.strip())
    for fmt in ("%b. %d, %Y", "%b %d, %Y", "%B %d, %Y"):
        try:
            return dt.datetime.strptime(normalized, fmt).date()
        except ValueError:
            pass
    raise C.EntryV2Refusal(f"unparseable release date: {value!r}")


def _parse_clock(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*([AaPp][Mm])\s*", value)
    if match is None:
        raise C.EntryV2Refusal(f"unparseable release clock: {value!r}")
    hour, minute = int(match.group(1)), int(match.group(2))
    if not (1 <= hour <= 12 and 0 <= minute < 60):
        raise C.EntryV2Refusal(f"invalid release clock: {value!r}")
    if match.group(3).upper() == "PM" and hour != 12:
        hour += 12
    if match.group(3).upper() == "AM" and hour == 12:
        hour = 0
    return hour, minute


def _event_ns(day: dt.date, hour: int, minute: int) -> int:
    return _utc_ns(dt.datetime(day.year, day.month, day.day, hour, minute, tzinfo=NY))


def _expected_bls_keys(year: int) -> tuple[str, ...]:
    keys = [f"December {year - 1}"]
    keys.extend(f"{calendar.month_name[month]} {year}" for month in range(1, 12))
    return tuple(keys)


def _parse_bls(spec: SourceSpec, raw: bytes, sha256: str) -> _Snapshot:
    if spec.program not in ("CPI", "EMPLOYMENT_SITUATION") or spec.coverage_year is None:
        raise C.EntryV2Refusal("BLS source needs an exact program and coverage year")
    parser = _ReleaseTableParser()
    parser.feed(raw.decode("utf-8", errors="strict"))
    expected_title = (
        "Consumer Price Index" if spec.program == "CPI" else "Employment Situation"
    )
    if expected_title not in " ".join(parser.all_text):
        raise C.EntryV2Refusal(f"BLS source is not the declared {spec.program} page")
    events: list[ParsedEvent] = []
    keys: list[str] = []
    for row in parser.rows:
        if len(row) != 3:
            raise C.EntryV2Refusal("BLS release row width changed")
        reference, release_text, clock_text = row
        day = _parse_release_date(release_text)
        if day.year != spec.coverage_year:
            continue
        hour, minute = _parse_clock(clock_text)
        key = f"{spec.program}:{reference}"
        keys.append(reference)
        events.append(ParsedEvent(
            spec.program,
            key,
            _event_ns(day, hour, minute),
            spec.availability_ts_ns,
            sha256,
        ))
    expected = _expected_bls_keys(spec.coverage_year)
    complete = len(keys) == 12 and set(keys) == set(expected)
    return _Snapshot(spec, sha256, tuple(events), complete, tuple(sorted(keys)))


def _parse_fomc_time_policy(spec: SourceSpec, raw: bytes, sha256: str) -> _Snapshot:
    parser = _TextParser()
    parser.feed(raw.decode("utf-8", errors="strict"))
    text = " ".join(parser.parts)
    law = re.search(
        r"Committee policy statements for all regularly scheduled meetings will now be "
        r"released at\s+2\s+p\.m\.\s+Eastern Time",
        text,
        flags=re.IGNORECASE,
    )
    if law is None:
        raise C.EntryV2Refusal("FOMC time-policy source does not prove the 2 p.m. law")
    return _Snapshot(spec, sha256, (), True, ("14:00 America/New_York",))


def _fomc_publication_ns(raw: bytes) -> int:
    html = raw.decode("utf-8", errors="strict")
    date_match = re.search(
        r'class="article__time"[^>]*>\s*([^<]+?)\s*</p>', html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    time_match = re.search(
        r'class="releaseTime"[^>]*>\s*For release at\s*'
        r'(\d{1,2}):(\d{2})\s*([ap])\.m\.\s*(EDT|EST)',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if date_match is None or time_match is None:
        raise C.EntryV2Refusal("FOMC schedule lacks an exact printed publication clock")
    try:
        day = dt.datetime.strptime(
            " ".join(date_match.group(1).split()), "%B %d, %Y"
        ).date()
    except ValueError as exc:
        raise C.EntryV2Refusal("invalid FOMC publication date") from exc
    hour, minute = int(time_match.group(1)), int(time_match.group(2))
    if not (1 <= hour <= 12 and 0 <= minute < 60):
        raise C.EntryV2Refusal("invalid FOMC publication time")
    if time_match.group(3).lower() == "p" and hour != 12:
        hour += 12
    if time_match.group(3).lower() == "a" and hour == 12:
        hour = 0
    value = dt.datetime(day.year, day.month, day.day, hour, minute, tzinfo=NY)
    if value.tzname() != time_match.group(4).upper():
        raise C.EntryV2Refusal("FOMC printed timezone disagrees with America/New_York")
    return _utc_ns(value)


_OLD_FOMC = re.compile(
    rf"\b({_MONTH_TOKEN})\s+(\d{{1,2}})-(?:(?:({_MONTH_TOKEN})\s+))?"
    r"(\d{1,2})(?:,\s*(\d{4}))?\s*\((?:Monday|Tuesday|Wednesday|Thursday|Friday)"
    r"-(?:Monday|Tuesday|Wednesday|Thursday|Friday)\)"
)
_NEW_FOMC = re.compile(
    rf"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday),\s*({_MONTH_TOKEN})\s+"
    rf"(\d{{1,2}}),\s*and\s*(?:Monday|Tuesday|Wednesday|Thursday|Friday),\s*"
    rf"({_MONTH_TOKEN})\s+(\d{{1,2}})"
)


def _parse_fomc_schedule(spec: SourceSpec, raw: bytes, sha256: str,
                         time_policy_sha256: str) -> _Snapshot:
    if spec.coverage_year is None or spec.program != "FOMC":
        raise C.EntryV2Refusal("FOMC schedule needs program=FOMC and a coverage year")
    if _fomc_publication_ns(raw) != spec.availability_ts_ns:
        raise C.EntryV2Refusal("FOMC declared availability differs from printed clock")
    parser = _TextParser()
    parser.feed(raw.decode("utf-8", errors="strict"))
    text = " ".join(parser.parts)
    if not re.search(rf"meeting schedule for .*\b{spec.coverage_year}\b", text,
                     flags=re.IGNORECASE):
        raise C.EntryV2Refusal("FOMC source does not name the declared schedule year")

    dates: list[dt.date] = []
    target_dates: list[dt.date] = []
    for match in _OLD_FOMC.finditer(text):
        end_month = _MONTHS[match.group(3) or match.group(1)]
        explicit_year = int(match.group(5)) if match.group(5) else spec.coverage_year
        day = dt.date(explicit_year, end_month, int(match.group(4)))
        dates.append(day)
        if explicit_year == spec.coverage_year:
            target_dates.append(day)
    if not target_dates:
        section_match = re.search(
            rf"\bFor\s+{spec.coverage_year}:\s*(.*?)"
            rf"(?=\bFor\s+{spec.coverage_year + 1}:|\bThe Committee releases\b)",
            text,
            flags=re.IGNORECASE,
        )
        section = section_match.group(1) if section_match else text
        for match in _NEW_FOMC.finditer(section):
            day = dt.date(
                spec.coverage_year, _MONTHS[match.group(3)], int(match.group(4))
            )
            dates.append(day)
            target_dates.append(day)
    dates = sorted(set(dates))
    target_dates = sorted(set(target_dates))
    complete = len(target_dates) == 8
    combined_provenance = C.object_sha256({
        "schema": "entry-v2-fomc-datetime-proof-v1",
        "schedule_sha256": sha256,
        "time_policy_sha256": time_policy_sha256,
    })
    events = tuple(ParsedEvent(
        "FOMC",
        f"FOMC:{day.isoformat()}",
        _event_ns(day, 14, 0),
        spec.availability_ts_ns,
        combined_provenance,
    ) for day in dates)
    return _Snapshot(
        spec, sha256, events, complete,
        tuple(day.isoformat() for day in target_dates)
    )


def _source_path(spec: SourceSpec, base: Path) -> Path:
    path = Path(spec.path)
    resolved = path.resolve() if path.is_absolute() else (base / path).resolve()
    try:
        resolved.relative_to(C.REPO_ROOT)
    except ValueError:
        # Unit fixtures may live in a system temporary directory.  Production
        # manifests are separately confined to /workspace by load_manifest.
        pass
    return resolved


def _verify_and_read(spec: SourceSpec, base: Path) -> tuple[bytes, str]:
    if not _SHA256.fullmatch(spec.sha256):
        raise C.EntryV2Refusal(f"invalid source SHA-256: {spec.source_id}")
    path = _source_path(spec, base)
    actual = C.file_sha256(path)
    if actual != spec.sha256:
        raise C.EntryV2Refusal(f"source hash mismatch: {spec.source_id}")
    raw = path.read_bytes()
    # Wayback's ``id_`` endpoint sometimes returns the archived entity body
    # still content-encoded.  The hash always pins the bytes on disk; only the
    # parser view is decompressed, deterministically and fail-closed.
    if raw.startswith(b"\x1f\x8b"):
        try:
            raw = gzip.decompress(raw)
        except (OSError, EOFError) as exc:
            raise C.EntryV2Refusal(
                f"invalid gzip-encoded source: {spec.source_id}"
            ) from exc
    return raw, actual


def _validate_specs(specs: Sequence[SourceSpec], start_d8: int,
                    end_exclusive_d8: int) -> None:
    # This must happen before the first source path is touched.
    if (start_d8, end_exclusive_d8) != (
        DEVELOPMENT_START_D8, DEVELOPMENT_END_EXCLUSIVE_D8
    ):
        raise C.EntryV2Refusal("compliance build must use the frozen pre-H2 window")
    C.guard_decode_window(start_d8, end_exclusive_d8)
    ids: set[str] = set()
    allowed = {"BLS_SCHEDULE_HTML", "FOMC_SCHEDULE_HTML", "FOMC_TIME_POLICY_HTML"}
    for spec in specs:
        if not spec.source_id or spec.source_id in ids:
            raise C.EntryV2Refusal("duplicate/empty compliance source id")
        ids.add(spec.source_id)
        if spec.kind not in allowed:
            raise C.EntryV2Refusal(f"unknown compliance source kind: {spec.kind}")
        if spec.availability_ts_ns <= 0:
            raise C.EntryV2Refusal("source has no exact availability timestamp")
        if spec.coverage_year is not None and spec.coverage_year >= 2026:
            raise C.EntryV2Refusal("2026 SEALED: refusing compliance source before read")
        if spec.coverage_year is not None and spec.coverage_year > 2025:
            raise C.EntryV2Refusal("source crosses the 2025H2 wall")


def _coverage_bounds(year: int) -> tuple[int, int] | None:
    start = max(
        _development_start_ns(), _utc_ns(dt.datetime(year, 1, 1, tzinfo=UTC))
    )
    end_exclusive = min(
        _wall_ns(), _utc_ns(dt.datetime(year + 1, 1, 1, tzinfo=UTC))
    )
    if start >= end_exclusive:
        return None
    return start, end_exclusive - 1


def _event_interval(event: ParsedEvent) -> ComplianceRow | None:
    start, end = event.event_ts_ns - WINDOW_NS, event.event_ts_ns + WINDOW_NS
    if start < _development_start_ns() or end >= _wall_ns():
        return None
    when = dt.datetime.fromtimestamp(event.event_ts_ns / NS, tz=UTC)
    safe_key = re.sub(r"[^A-Za-z0-9]+", "_", event.event_key).strip("_")
    row = ComplianceRow(
        "PROHIBITED",
        f"{safe_key}_{when:%Y%m%dT%H%M%SZ}_{event.availability_ts_ns}",
        start,
        end,
        event.availability_ts_ns,
        event.provenance_sha256,
    )
    row.validate()
    return row


def build_compliance(specs: Sequence[SourceSpec], *, base: str | Path = ".",
                     start_d8: int = DEVELOPMENT_START_D8,
                     end_exclusive_d8: int = DEVELOPMENT_END_EXCLUSIVE_D8,
                     manifest_sha256: str | None = None) -> ComplianceBuild:
    """Build exact event and coverage rows from already-acquired sources."""
    _validate_specs(specs, start_d8, end_exclusive_d8)
    base_path = Path(base).resolve()

    time_specs = [s for s in specs if s.kind == "FOMC_TIME_POLICY_HTML"]
    if len(time_specs) != 1:
        raise C.EntryV2Refusal("exactly one hash-pinned FOMC time policy is required")
    time_raw, time_sha = _verify_and_read(time_specs[0], base_path)
    time_snapshot = _parse_fomc_time_policy(time_specs[0], time_raw, time_sha)

    snapshots: list[_Snapshot] = [time_snapshot]
    for spec in specs:
        if spec.kind == "FOMC_TIME_POLICY_HTML":
            continue
        raw, sha256 = _verify_and_read(spec, base_path)
        if spec.kind == "BLS_SCHEDULE_HTML":
            snapshots.append(_parse_bls(spec, raw, sha256))
        else:
            snapshots.append(_parse_fomc_schedule(spec, raw, sha256, time_sha))

    # A rescheduled event is a new dated event with its own first-seen clock.
    # The earlier scheduled interval stays prohibited, which is conservative
    # and prevents a later page from rewriting history.
    earliest: dict[tuple[str, str, int], ParsedEvent] = {}
    for snapshot in snapshots:
        if not snapshot.complete:
            continue
        for event in snapshot.parsed_events:
            key = (event.calendar_id, event.event_key, event.event_ts_ns)
            current = earliest.get(key)
            if current is None or event.availability_ts_ns < current.availability_ts_ns:
                earliest[key] = event

    rows = [row for event in earliest.values() if (row := _event_interval(event))]
    coverage_proofs: list[dict[str, Any]] = []
    coverage_gaps: list[dict[str, Any]] = []
    for year in range(2021, 2026):
        bounds = _coverage_bounds(year)
        if bounds is None:
            continue
        selected: dict[str, _Snapshot] = {}
        for program in ("CPI", "EMPLOYMENT_SITUATION", "FOMC"):
            eligible = [
                snap for snap in snapshots
                if snap.complete and snap.spec.coverage_year == year
                and snap.spec.program == program
            ]
            if eligible:
                selected[program] = min(
                    eligible, key=lambda snap: snap.spec.availability_ts_ns
                )
        if set(selected) != {"CPI", "EMPLOYMENT_SITUATION", "FOMC"}:
            coverage_gaps.append({
                "year": year,
                "missing_complete_calendars": sorted(
                    {"CPI", "EMPLOYMENT_SITUATION", "FOMC"} - set(selected)
                ),
            })
            continue
        proof = {
            "schema": "entry-v2-compliance-coverage-proof-v1",
            "year": year,
            "start_ts_ns": bounds[0],
            "end_ts_ns": bounds[1],
            "sources": [{
                "program": name,
                "source_id": selected[name].spec.source_id,
                "source_sha256": selected[name].sha256,
                "availability_ts_ns": selected[name].spec.availability_ts_ns,
                "completeness_keys": list(selected[name].completeness_keys),
            } for name in ("CPI", "EMPLOYMENT_SITUATION", "FOMC")],
            "fomc_time_policy_source_id": time_snapshot.spec.source_id,
            "fomc_time_policy_sha256": time_snapshot.sha256,
        }
        proof_sha = C.object_sha256(proof)
        availability = max(
            time_snapshot.spec.availability_ts_ns,
            *(snap.spec.availability_ts_ns for snap in selected.values()),
        )
        coverage = ComplianceRow(
            "COVERAGE", f"COVERAGE_ALL_{year}", bounds[0], bounds[1],
            availability, proof_sha,
        )
        coverage.validate()
        rows.append(coverage)
        coverage_proofs.append({**proof, "provenance_sha256": proof_sha})

    rows.sort(key=lambda row: (
        row.start_ts_ns, row.end_ts_ns, row.kind, row.interval_id
    ))
    ids = [row.interval_id for row in rows]
    if len(ids) != len(set(ids)):
        raise C.EntryV2Refusal("duplicate compliance interval id")
    source_receipts = [{
        "source_id": snap.spec.source_id,
        "kind": snap.spec.kind,
        "program": snap.spec.program,
        "coverage_year": snap.spec.coverage_year,
        "availability_ts_ns": snap.spec.availability_ts_ns,
        "path": snap.spec.path,
        "sha256": snap.sha256,
        "complete": snap.complete,
        "parsed_event_count_pre_wall": sum(
            event.event_ts_ns < _wall_ns() for event in snap.parsed_events
        ),
        "completeness_key_count": len(snap.completeness_keys),
    } for snap in snapshots]
    receipt: dict[str, Any] = {
        "schema": "entry-v2-compliance-build-receipt-v1",
        "cpp_schema": CPP_SCHEMA,
        "builder_code_sha256": C.file_sha256(Path(__file__)),
        "development_start_d8": start_d8,
        "development_end_exclusive_d8": end_exclusive_d8,
        "manifest_sha256": manifest_sha256,
        "source_receipts": source_receipts,
        "coverage_proofs": coverage_proofs,
        "coverage_gaps": coverage_gaps,
        "coverage_years": [proof["year"] for proof in coverage_proofs],
        "prohibited_row_count": sum(row.kind == "PROHIBITED" for row in rows),
        "coverage_row_count": sum(row.kind == "COVERAGE" for row in rows),
        "all_output_timestamps_strictly_pre_h2": all(
            row.start_ts_ns < _wall_ns() and row.end_ts_ns < _wall_ns()
            for row in rows
        ),
    }
    receipt["build_sha256"] = C.object_sha256(receipt)
    return ComplianceBuild(tuple(rows), receipt)


def render_cpp_calendar(build: ComplianceBuild) -> bytes:
    lines = [
        f"# {CPP_SCHEMA}",
        "kind\tinterval_id\tstart_ts_ns\tend_ts_ns\tavailability_ts_ns"
        "\tprovenance_sha256",
    ]
    for row in build.rows:
        row.validate()
        lines.append(
            f"{row.kind}\t{row.interval_id}\t{row.start_ts_ns}\t{row.end_ts_ns}"
            f"\t{row.availability_ts_ns}\t{row.provenance_sha256}"
        )
    return ("\n".join(lines) + "\n").encode("ascii")


def classify_at(rows: Iterable[ComplianceRow], decision_ts_ns: int) -> str:
    """Reference semantics for adversarial checks; C++ remains authoritative."""
    covered = False
    prohibited = False
    for row in rows:
        if row.availability_ts_ns >= decision_ts_ns:
            continue
        inside = row.start_ts_ns <= decision_ts_ns <= row.end_ts_ns
        if row.kind == "COVERAGE":
            covered = covered or inside
        elif inside:
            prohibited = True
    if prohibited:
        return "PROHIBITED"
    return "CLEAR" if covered else "COMPLIANCE_UNKNOWN"


def _archive_timestamp_ns(timestamp: str) -> int:
    if not re.fullmatch(r"\d{14}", timestamp):
        raise C.EntryV2Refusal("invalid Wayback capture timestamp")
    try:
        value = dt.datetime.strptime(timestamp, "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    except ValueError as exc:
        raise C.EntryV2Refusal("invalid Wayback capture timestamp") from exc
    return _utc_ns(value)


def _manifest_child(base: Path, relative: str) -> Path:
    path = (base / relative).resolve()
    try:
        path.relative_to(C.REPO_ROOT)
    except ValueError as exc:
        raise C.EntryV2Refusal(f"manifest child leaves workspace: {relative}") from exc
    return path


def _verify_archive_audit(value: Mapping[str, Any], base: Path) -> None:
    indices: dict[str, list[str]] = {}
    for item in value.get("archive_indices", []):
        relative = str(item.get("path", ""))
        expected = str(item.get("sha256", ""))
        if not relative or not _SHA256.fullmatch(expected):
            raise C.EntryV2Refusal("invalid archive-index declaration")
        path = _manifest_child(base, relative)
        if C.file_sha256(path) != expected:
            raise C.EntryV2Refusal(f"archive-index hash mismatch: {relative}")
        try:
            rows = json.loads(path.read_bytes())
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise C.EntryV2Refusal(f"invalid archive-index JSON: {relative}") from exc
        if not rows or rows[0] != ["timestamp", "original", "statuscode", "digest"]:
            raise C.EntryV2Refusal(f"archive-index schema mismatch: {relative}")
        timestamps = [str(row[0]) for row in rows[1:]]
        if any(not re.fullmatch(r"\d{14}", stamp) for stamp in timestamps):
            raise C.EntryV2Refusal(f"archive-index timestamp mismatch: {relative}")
        indices[relative] = timestamps

    expected_pairs = {
        (program, year)
        for program in ("CPI", "EMPLOYMENT_SITUATION")
        for year in range(2021, 2026)
    }
    audits = value.get("earliest_capture_audit", [])
    actual_pairs = {(str(item.get("program")), int(item.get("year", 0)))
                    for item in audits}
    if actual_pairs != expected_pairs or len(audits) != len(expected_pairs):
        raise C.EntryV2Refusal("earliest-capture audit is not exactly 2x5 calendars")
    source_items = value.get("sources", [])
    for item in audits:
        relative = str(item.get("index_path", ""))
        before = str(item.get("predecessor_ts", ""))
        selected = str(item.get("selected_ts", ""))
        timestamps = indices.get(relative)
        if timestamps is None or before not in timestamps or selected not in timestamps:
            raise C.EntryV2Refusal("capture audit references an absent CDX timestamp")
        if timestamps.index(selected) != timestamps.index(before) + 1:
            raise C.EntryV2Refusal(
                "selected BLS body is not immediately after its distinct predecessor"
            )
        program, year = str(item["program"]), int(item["year"])
        for stamp in (before, selected):
            matches = [source for source in source_items
                       if source.get("program") == program
                       and source.get("coverage_year") == year
                       and stamp in str(source.get("path", ""))]
            if len(matches) != 1:
                raise C.EntryV2Refusal("capture audit does not map one exact source")
            if int(matches[0].get("availability_ts_ns", 0)) != _archive_timestamp_ns(stamp):
                raise C.EntryV2Refusal("BLS availability is not its exact capture clock")


def load_manifest(path: str | Path) -> tuple[list[SourceSpec], Path, str]:
    manifest_path = Path(path).resolve()
    raw = manifest_path.read_bytes()
    sha256 = C.file_sha256(manifest_path)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise C.EntryV2Refusal("invalid compliance source manifest JSON") from exc
    if value.get("schema") != SCHEMA:
        raise C.EntryV2Refusal("invalid compliance source manifest schema")
    if value.get("development_start_d8") != DEVELOPMENT_START_D8 or value.get(
        "development_end_exclusive_d8"
    ) != DEVELOPMENT_END_EXCLUSIVE_D8:
        raise C.EntryV2Refusal("manifest does not name the frozen pre-H2 window")
    _verify_archive_audit(value, manifest_path.parent)
    specs = [SourceSpec(**item) for item in value.get("sources", [])]
    # Production manifests cannot redirect reads outside the shared workspace.
    for spec in specs:
        resolved = _source_path(spec, manifest_path.parent)
        try:
            resolved.relative_to(C.REPO_ROOT)
        except ValueError as exc:
            raise C.EntryV2Refusal(f"source leaves workspace: {spec.source_id}") from exc
    return specs, manifest_path.parent, sha256


def _atomic_bytes(path: str | Path, raw: bytes) -> str:
    output = C.assert_workspace_output(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_name(output.name + f".tmp.{os.getpid()}")
    with open(tmp, "xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, output)
    return C.file_sha256(output)


def write_build(build: ComplianceBuild, artifact_path: str | Path,
                receipt_path: str | Path) -> tuple[str, str]:
    artifact_sha = _atomic_bytes(artifact_path, render_cpp_calendar(build))
    receipt = dict(build.receipt)
    receipt.update({
        "artifact_path": str(Path(artifact_path).resolve()),
        "artifact_sha256": artifact_sha,
    })
    receipt_sha = C.atomic_json(receipt_path, receipt)
    return artifact_sha, receipt_sha


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--receipt", required=True)
    args = parser.parse_args(argv)
    specs, base, manifest_sha = load_manifest(args.manifest)
    build = build_compliance(specs, base=base, manifest_sha256=manifest_sha)
    artifact_sha, receipt_sha = write_build(build, args.output, args.receipt)
    print(json.dumps({
        "artifact_sha256": artifact_sha,
        "receipt_sha256": receipt_sha,
        "coverage_years": build.receipt["coverage_years"],
        "coverage_gaps": build.receipt["coverage_gaps"],
        "prohibited_row_count": build.receipt["prohibited_row_count"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
