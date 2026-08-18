#!/usr/bin/env python3
"""Focused adversarial checks for the D-077 point-in-time lane."""

from __future__ import annotations

import calendar
import datetime as dt
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo

from engine.entry_v2 import common as C
from engine.entry_v2.compliance_calendar import (
    NS,
    ComplianceRow,
    SourceSpec,
    build_compliance,
    classify_at,
    render_cpp_calendar,
)


NY = ZoneInfo("America/New_York")


def _ns(value: dt.datetime) -> int:
    return int(value.timestamp()) * NS


def _write(root: Path, name: str, text: str) -> tuple[str, str]:
    path = root / name
    path.write_text(text, encoding="utf-8")
    return name, C.file_sha256(path)


def _bls_html(program: str, year: int, *, clock: str = "08:30 AM",
              changes: dict[str, dt.date] | None = None,
              drop: str | None = None) -> str:
    title = "Consumer Price Index" if program == "CPI" else "Employment Situation"
    changes = changes or {}
    rows: list[str] = []
    references = [(12, year - 1)] + [(month, year) for month in range(1, 12)]
    for month, reference_year in references:
        reference = f"{calendar.month_name[month]} {reference_year}"
        if reference == drop:
            continue
        release_month = month % 12 + 1
        release_year = reference_year + (month == 12)
        day = changes.get(reference, dt.date(release_year, release_month, 10))
        rows.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                reference, day.strftime("%b. %d, %Y"), clock
            )
        )
    return (
        f"<html><title>Schedule of Releases for the {title}</title>"
        f"<h2>Schedule of Releases for the {title}</h2>"
        '<table class="release-list"><tbody>' + "".join(rows) +
        "</tbody></table></html>"
    )


def _fomc_html(year: int, published: dt.datetime) -> str:
    lines = (
        "January 30-31 (Tuesday-Wednesday)",
        "March 19-20 (Tuesday-Wednesday)",
        "April 30-May 1 (Tuesday-Wednesday)",
        "June 11-12 (Tuesday-Wednesday)",
        "July 30-31 (Tuesday-Wednesday)",
        "September 17-18 (Tuesday-Wednesday)",
        "November 6-7 (Wednesday-Thursday)",
        "December 17-18 (Tuesday-Wednesday)",
        f"January 28-29, {year + 1} (Tuesday-Wednesday)",
    )
    return (
        f"<html><title>FOMC meeting schedule for {year}</title>"
        f'<p class="article__time">{published:%B %d, %Y}</p>'
        f'<p class="releaseTime">For release at {published:%I:%M} '
        f'{published:%p}'.lower().replace("am", "a.m.").replace("pm", "p.m.")
        + f" {published.tzname()}</p>"
        f"<h3>Federal Open Market Committee announces tentative meeting schedule for {year}</h3>"
        + "".join(f"<p>{line}</p>" for line in lines) + "</html>"
    )


def _time_policy(hour: int = 2) -> str:
    return (
        "<html><p>Committee policy statements for all regularly scheduled meetings "
        f"will now be released at {hour} p.m. Eastern Time.</p></html>"
    )


def _spec(root: Path, source_id: str, kind: str, year: int | None,
          available: dt.datetime, text: str, program: str | None) -> SourceSpec:
    name, sha = _write(root, source_id + ".htm", text)
    return SourceSpec(source_id, kind, year, _ns(available), name, sha, program)


def _complete_specs(root: Path, year: int, *, cpi_text: str | None = None,
                    clock: str = "08:30 AM") -> list[SourceSpec]:
    old = dt.datetime(2013, 3, 14, tzinfo=dt.timezone.utc)
    archived = dt.datetime(year - 1, 10, 20, tzinfo=dt.timezone.utc)
    fomc_published = dt.datetime(year - 1, 10, 20, 10, tzinfo=NY)
    return [
        _spec(root, "fomc_time", "FOMC_TIME_POLICY_HTML", None, old,
              _time_policy(), None),
        _spec(root, f"cpi_{year}", "BLS_SCHEDULE_HTML", year, archived,
              cpi_text or _bls_html("CPI", year, clock=clock), "CPI"),
        _spec(root, f"empsit_{year}", "BLS_SCHEDULE_HTML", year, archived,
              _bls_html("EMPLOYMENT_SITUATION", year, clock=clock),
              "EMPLOYMENT_SITUATION"),
        _spec(root, f"fomc_{year}", "FOMC_SCHEDULE_HTML", year, fomc_published,
              _fomc_html(year, fomc_published), "FOMC"),
    ]


class ComplianceCalendarAdversarialTests(unittest.TestCase):
    def test_complete_2021_archives_cover_from_january_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build = build_compliance(_complete_specs(root, 2021), base=root)
            coverage = [row for row in build.rows if row.kind == "COVERAGE"]
            self.assertEqual(len(coverage), 1)
            self.assertEqual(
                coverage[0].start_ts_ns,
                _ns(dt.datetime(2021, 1, 1, tzinfo=dt.timezone.utc)),
            )
            early_events = [
                row for row in build.rows
                if row.kind == "PROHIBITED"
                and row.start_ts_ns < _ns(dt.datetime(
                    2021, 5, 31, tzinfo=dt.timezone.utc
                ))
            ]
            self.assertTrue(early_events)

    def test_reschedule_is_additive_and_keeps_its_later_availability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            specs = _complete_specs(root, 2024)
            later = dt.datetime(2024, 5, 20, 12, tzinfo=dt.timezone.utc)
            revised = _bls_html(
                "CPI", 2024,
                changes={"May 2024": dt.date(2024, 6, 11)},
            )
            specs.append(_spec(
                root, "cpi_2024_revised", "BLS_SCHEDULE_HTML", 2024,
                later, revised, "CPI",
            ))
            build = build_compliance(specs, base=root)
            cpi_june = [
                row for row in build.rows
                if row.kind == "PROHIBITED" and row.interval_id.startswith("CPI_May_2024")
            ]
            self.assertEqual(len(cpi_june), 2)
            self.assertEqual(
                sorted(row.availability_ts_ns for row in cpi_june),
                [_ns(dt.datetime(2023, 10, 20, tzinfo=dt.timezone.utc)), _ns(later)],
            )
            self.assertNotEqual(cpi_june[0].start_ts_ns, cpi_june[1].start_ts_ns)

    def test_incomplete_calendar_never_implies_clear(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            specs = _complete_specs(root, 2024)
            specs[2] = _spec(
                root, "empsit_incomplete", "BLS_SCHEDULE_HTML", 2024,
                dt.datetime(2023, 10, 20, tzinfo=dt.timezone.utc),
                _bls_html("EMPLOYMENT_SITUATION", 2024, drop="May 2024"),
                "EMPLOYMENT_SITUATION",
            )
            build = build_compliance(specs, base=root)
            self.assertFalse(any(row.kind == "COVERAGE" for row in build.rows))
            self.assertEqual(
                build.receipt["coverage_gaps"][3]["missing_complete_calendars"],
                ["EMPLOYMENT_SITUATION"],
            )
            decision = _ns(dt.datetime(2024, 6, 20, tzinfo=dt.timezone.utc))
            self.assertEqual(classify_at(build.rows, decision), "COMPLIANCE_UNKNOWN")

    def test_availability_is_strictly_prior_not_equal_time(self) -> None:
        coverage = ComplianceRow(
            "COVERAGE", "equal_time_fixture", 100, 200, 150, "0" * 64
        )
        self.assertEqual(classify_at((coverage,), 150), "COMPLIANCE_UNKNOWN")
        self.assertEqual(classify_at((coverage,), 151), "CLEAR")

    def test_bls_clock_is_parsed_and_dst_is_not_a_fixed_proxy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build = build_compliance(
                _complete_specs(root, 2024, clock="09:17 AM"), base=root
            )
            starts = {
                row.start_ts_ns + 10 * 60 * NS for row in build.rows
                if row.kind == "PROHIBITED" and row.interval_id.startswith("CPI_")
            }
            self.assertIn(
                _ns(dt.datetime(2024, 1, 10, 9, 17, tzinfo=NY)), starts
            )
            self.assertIn(
                _ns(dt.datetime(2024, 7, 10, 9, 17, tzinfo=NY)), starts
            )
            jan_utc = dt.datetime.fromtimestamp(
                _ns(dt.datetime(2024, 1, 10, 9, 17, tzinfo=NY)) / NS,
                tz=dt.timezone.utc,
            )
            jul_utc = dt.datetime.fromtimestamp(
                _ns(dt.datetime(2024, 7, 10, 9, 17, tzinfo=NY)) / NS,
                tz=dt.timezone.utc,
            )
            self.assertEqual((jan_utc.hour, jul_utc.hour), (14, 13))

    def test_h2_and_2026_are_walled_before_output_or_source_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build = build_compliance(_complete_specs(root, 2025), base=root)
            wall = _ns(dt.datetime(2025, 7, 1, tzinfo=dt.timezone.utc))
            self.assertTrue(build.rows)
            self.assertTrue(all(row.start_ts_ns < wall and row.end_ts_ns < wall
                                for row in build.rows))
            specs = _complete_specs(root, 2024)
            specs.append(SourceSpec(
                "sealed_missing", "BLS_SCHEDULE_HTML", 2026, 1,
                "this-path-must-not-be-opened.htm", "0" * 64, "CPI",
            ))
            with self.assertRaisesRegex(C.EntryV2Refusal, "2026 SEALED"):
                build_compliance(specs, base=root)

    def test_source_mutation_and_time_policy_mutation_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            specs = _complete_specs(root, 2024)
            (root / specs[1].path).write_text("mutated", encoding="utf-8")
            with self.assertRaisesRegex(C.EntryV2Refusal, "source hash mismatch"):
                build_compliance(specs, base=root)

            specs = _complete_specs(root, 2024)
            specs[0] = _spec(
                root, "wrong_time_policy", "FOMC_TIME_POLICY_HTML", None,
                dt.datetime(2013, 3, 14, tzinfo=dt.timezone.utc),
                _time_policy(3), None,
            )
            with self.assertRaisesRegex(C.EntryV2Refusal, "does not prove"):
                build_compliance(specs, base=root)

    def test_duplicate_capture_uses_actual_earliest_archived_clock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            specs = _complete_specs(root, 2024)
            specs.append(_spec(
                root, "cpi_duplicate_later", "BLS_SCHEDULE_HTML", 2024,
                dt.datetime(2024, 1, 5, tzinfo=dt.timezone.utc),
                _bls_html("CPI", 2024), "CPI",
            ))
            build = build_compliance(specs, base=root)
            cpi_rows = [row for row in build.rows
                        if row.kind == "PROHIBITED" and row.interval_id.startswith("CPI_")]
            self.assertEqual(len(cpi_rows), 12)
            self.assertTrue(all(
                row.availability_ts_ns == _ns(dt.datetime(
                    2023, 10, 20, tzinfo=dt.timezone.utc
                )) for row in cpi_rows
            ))

    def test_cpp_schema_and_exact_inclusive_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build = build_compliance(_complete_specs(root, 2024), base=root)
            raw = render_cpp_calendar(build)
            self.assertTrue(raw.startswith(
                b"# QRE2COMPLIANCE1\nkind\tinterval_id\tstart_ts_ns"
            ))
            self.assertTrue(all(
                row.end_ts_ns - row.start_ts_ns == 20 * 60 * NS
                for row in build.rows if row.kind == "PROHIBITED"
            ))


if __name__ == "__main__":
    unittest.main()
