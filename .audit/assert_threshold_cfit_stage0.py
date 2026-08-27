#!/usr/bin/env python3
"""Byte-level judge checks for .audit/threshold-cfit-stage0.json.

Re-verifies the unit C Stage 0 receipt against the published pivot tags,
the stored candidates, the surviving scratch outputs under
artifacts/cache/cpp/threshold-cfit-stage0/runs, the staged event trees
(no 2025 pack linked), the pivot Stage 0 receipt anchors for the 433
protected 2021 files, and the mutant seams in g1.cpp. Read-only.
Exit 0 means every check held.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

ROOT = Path("/workspace")
CANONICAL = ROOT / "artifacts/cache/port/entry_v2"
PIVOT_ROOT = CANONICAL / "g1/pivot"
SCRATCH_RUNS = ROOT / "artifacts/cache/cpp/threshold-cfit-stage0/runs"
RECEIPT_PATH = ROOT / ".audit/threshold-cfit-stage0.json"
PIVOT_STAGE0_RECEIPT = ROOT / ".audit/threshold-pivot-stage0.json"
G1_CPP = ROOT / "engine/cpp/qr_entry_v2/src/g1.cpp"
ASSETS = ("HG", "NKD", "SI")
START_D8 = 20210101
PROTECTED_END_D8_EXCLUSIVE = 20210807
ERA_START_D8 = 20220101
END_D8_EXCLUSIVE = 20250101
PROTECTED_COUNTS = {"HG": 187, "NKD": 187, "SI": 59}
PIVOT_COLUMNS = (
    "candidate_id",
    "asset",
    "d8",
    "rung_index",
    "side",
    "pivot_mid2",
    "pivot_ts_recv_ns",
    "pivot_ordinal",
    "leg_start_mid2",
    "leg_start_ts_recv_ns",
    "leg_start_ordinal",
    "conf_mid2",
    "threshold_mid2_raw",
)
MANIFEST_COLUMNS = (
    "asset",
    "d8",
    "rows",
    "candidates",
    "pivot_file",
    "pivot_sha256",
)
EXPECTED_SOURCE_KEYS = tuple(
    [
        ".audit/briefs/threshold-cfit-stage0.md",
        ".audit/briefs/threshold-covering-after-pivot-kill-out.md",
        ".audit/threshold_pivot_stage0.py",
        ".audit/threshold-pivot-stage0.json",
        "engine/cpp/qr_entry_v2/src/g1.cpp",
        "engine/cpp/qr_entry_v2/tests/test_g1.cpp",
    ]
    + [
        f"artifacts/cache/port/entry_v2/{stem}"
        for asset in ASSETS
        for stem in (
            f"locks/{asset}.tsv",
            f"phases/{asset}.tsv",
            f"events/{asset}/manifest.tsv",
            f"g1/candidates/{asset}/manifest.tsv",
        )
    ]
)
# (label, baseline string, expected baseline count, mutated remnant string)
MUTANT_SEAMS = (
    (
        "post_cutoff_event_leaks_into_tag",
        "      pivot.conf_mid2 = birth.conf_mid2;\n",
        1,
        "candidate.event_cutoff < pack.rows.size()",
    ),
    (
        "leg_start_captured_after_flip",
        "        const PivotBirth birth{\n"
        "            -1, high, high_key, low, low_key, mid2, threshold};\n",
        1,
        "-1, high, high_key, mid2, key, mid2, threshold};",
    ),
    (
        "side_swapped_in_record",
        "      pivot.side = birth.side;\n",
        1,
        "pivot.side = static_cast<std::int8_t>(-birth.side);",
    ),
)
UNTOUCHED_TREES = (
    "g1/candidates",
    "g1/teacher",
    "g1/receipts",
    "receipts",
    "locks",
    "phases",
    "events",
)

failures: list[str] = []


def fail(message: str) -> None:
    failures.append(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def bytes_below_schema(path: Path) -> bytes:
    payload = path.read_bytes()
    newline = payload.find(b"\n")
    if newline < 0:
        raise AssertionError(f"{path} has no schema line terminator")
    return payload[newline + 1 :]


def parse_table(path: Path) -> tuple[str, tuple[str, ...], list[list[str]]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 2 or not lines[0].startswith("# "):
        raise AssertionError(f"{path} lacks a schema line and header")
    columns = tuple(lines[1].split("\t"))
    rows: list[list[str]] = []
    for number, line in enumerate(lines[2:], start=3):
        fields = line.split("\t")
        if line == "" or len(fields) != len(columns):
            raise AssertionError(
                f"{path}:{number} has {len(fields)} fields, "
                f"expected {len(columns)} per the closed header"
            )
        rows.append(fields)
    return lines[0], columns, rows


def lock_days(asset: str) -> list[int]:
    _, columns, rows = parse_table(CANONICAL / "locks" / f"{asset}.tsv")
    d8_index = columns.index("d8")
    return [
        int(row[d8_index])
        for row in rows
        if START_D8 <= int(row[d8_index]) < END_D8_EXCLUSIVE
    ]


def event_days(asset: str) -> list[int]:
    _, columns, rows = parse_table(CANONICAL / "events" / asset / "manifest.tsv")
    d8_index = columns.index("d8")
    return [
        int(row[d8_index])
        for row in rows
        if START_D8 <= int(row[d8_index]) < END_D8_EXCLUSIVE
    ]


def prefix_event_total(asset: str) -> int:
    _, columns, rows = parse_table(CANONICAL / "events" / asset / "manifest.tsv")
    d8_index = columns.index("d8")
    raw_index = columns.index("raw_records")
    return sum(
        int(row[raw_index])
        for row in rows
        if START_D8 <= int(row[d8_index]) < END_D8_EXCLUSIVE
    )


def candidate_projection(path: Path) -> list[tuple[str, str, str]]:
    _, columns, rows = parse_table(path)
    picks = tuple(
        columns.index(name)
        for name in ("candidate_id", "prefix_sha256", "rung_mask")
    )
    return [(row[picks[0]], row[picks[1]], row[picks[2]]) for row in rows]


def stored_candidates(asset: str, d8: int) -> list[dict[str, str]]:
    path = CANONICAL / "g1/candidates" / asset / f"{d8}.tsv"
    _, columns, rows = parse_table(path)
    return [dict(zip(columns, row, strict=True)) for row in rows]


def check_receipt_flags(receipt: dict[str, object]) -> None:
    literals = {
        "schema": "QRE2THRESHOLDCFITSTAGE01",
        "status": "PASS",
        "emitted_2022_2024_tags": True,
        "fit_started": False,
        "stage1_started": False,
        "pivot_lines_scored": False,
        "tag_can_promote": False,
        "teacher_fields_parsed": [],
        "tickets_started": [],
        "units_started": ["C_STAGE0"],
        "stored_candidate_artifacts_rewritten": False,
        "stored_teacher_artifacts_rewritten": False,
        "stored_receipt_artifacts_rewritten": False,
        "stored_2021_pivot_day_files_rewritten": False,
        "pivot_root": str(PIVOT_ROOT),
        "asset_chain_workers": 3,
        "worker_budget": 16,
        "tripwire_seconds": 7200,
        "window": {
            "start_d8": START_D8,
            "existing_tag_end_d8_exclusive": PROTECTED_END_D8_EXCLUSIVE,
            "new_tag_start_d8": PROTECTED_END_D8_EXCLUSIVE,
            "era_start_d8": ERA_START_D8,
            "end_d8_exclusive": END_D8_EXCLUSIVE,
        },
    }
    for key, expected in literals.items():
        if receipt.get(key) != expected:
            fail(f"receipt[{key!r}] is {receipt.get(key)!r}, expected {expected!r}")
    selftest = receipt.get("selftest", {})
    if selftest.get("cpp", {}).get("test") != (
        "EntryV2Candidates.PivotBirthRowsUsePreFlipStateAndExcludeFutureRows"
    ) or selftest.get("cpp", {}).get("status") != "PASS":
        fail(f"receipt selftest.cpp is {selftest.get('cpp')!r}")
    if selftest.get("candidate_guard", {}).get("status") != "PASS":
        fail(f"receipt selftest.candidate_guard is {selftest.get('candidate_guard')!r}")
    mutants = receipt.get("mutants", {})
    expected_mutants = {seam[0] for seam in MUTANT_SEAMS}
    if set(mutants) != expected_mutants:
        fail(f"receipt mutants are {sorted(mutants)}, expected {sorted(expected_mutants)}")
    for name, record in mutants.items():
        if record.get("status") != "KILLED" or record.get("test_exit_code") == 0:
            fail(f"receipt mutant {name} is {record!r}, expected KILLED with nonzero exit")
    guard = receipt.get("guard_mutant", {})
    if guard.get("status") != "KILLED" or guard.get("refused") is not True:
        fail(f"receipt guard_mutant is {guard!r}, expected KILLED and refused")
    build = receipt.get("build", {})
    if build.get("status") != "PASS":
        fail(f"receipt build is {build!r}")
    for asset in ASSETS:
        chain = receipt.get("chains", {}).get(asset, {})
        if chain.get("status") != "PASS" or not (
            0 < float(chain.get("wall_seconds", -1)) < 7200
        ):
            fail(f"receipt chains[{asset}] is {chain!r}")
    if not 0 < float(receipt.get("wall_clock_seconds", -1)) < 7200:
        fail(f"receipt wall_clock_seconds is {receipt.get('wall_clock_seconds')!r}")


def check_sources(receipt: dict[str, object]) -> None:
    sources = receipt.get("sources", {})
    if sorted(sources) != sorted(EXPECTED_SOURCE_KEYS):
        fail(
            f"receipt sources keys differ from the 18 expected: "
            f"{sorted(set(sources).symmetric_difference(EXPECTED_SOURCE_KEYS))}"
        )
        return
    for relative, recorded in sources.items():
        live = sha256_file(ROOT / relative)
        if live != recorded:
            fail(
                f"source {relative} live sha {live} differs from receipt "
                f"{recorded}; the file changed after the run"
            )


def check_prior_pivot_anchors(
    receipt: dict[str, object],
    pivot_receipt: dict[str, object],
) -> None:
    for asset in ASSETS:
        prior = receipt.get("prior_pivot_manifest_sha256s", {}).get(asset)
        anchored = pivot_receipt["tag_sha256s"][asset]["manifest_sha256"]
        if prior != anchored:
            fail(
                f"{asset} prior_pivot_manifest_sha256 {prior} differs from the "
                f"pivot Stage 0 receipt {anchored}"
            )
        publication = receipt.get("publication", {}).get(asset, {})
        if publication.get("prior_manifest_sha256") != anchored:
            fail(
                f"{asset} publication prior_manifest_sha256 "
                f"{publication.get('prior_manifest_sha256')} differs from the "
                f"pivot Stage 0 receipt {anchored}"
            )


def check_projection(receipt: dict[str, object]) -> None:
    projection = receipt.get("projection", {})
    differential = receipt.get("future_mutation_differential", {})
    if differential.get("status") != "PASS" or differential.get(
        "tag_bytes_identical"
    ) is not True:
        fail(f"receipt differential is {differential!r}")
    if (
        projection.get("status") != "PASS"
        or projection.get("holds") is not True
        or projection.get("sample_asset") != differential.get("asset")
        or projection.get("sample_d8") != differential.get("d8")
        or projection.get("sample_raw_events") != differential.get("raw_events")
    ):
        fail(f"receipt projection is inconsistent with the differential: {projection!r}")
    sample_seconds = float(projection.get("sample_wall_seconds", 0.0))
    sample_events = int(projection.get("sample_raw_events", 0))
    if sample_events <= 0 or sample_seconds <= 0.0:
        fail(f"projection sample is degenerate: {projection!r}")
        return
    per_event = sample_seconds / sample_events
    if not math.isclose(per_event, float(projection["seconds_per_event"]), rel_tol=1e-9):
        fail(
            f"seconds_per_event {projection['seconds_per_event']} differs from "
            f"{per_event} recomputed"
        )
    for asset in ASSETS:
        expected = per_event * prefix_event_total(asset)
        recorded = float(projection["projected_chain_seconds"][asset])
        if not math.isclose(expected, recorded, rel_tol=1e-9):
            fail(
                f"projected_chain_seconds[{asset}] {recorded} differs from "
                f"{expected} recomputed from the events manifest"
            )
        if recorded > 7200:
            fail(f"projected_chain_seconds[{asset}] {recorded} crosses the tripwire")


def check_real_session_choice(receipt: dict[str, object]) -> None:
    choices: list[tuple[int, str, int]] = []
    for asset in ASSETS:
        _, columns, rows = parse_table(
            CANONICAL / "g1/candidates" / asset / "manifest.tsv"
        )
        status_i = columns.index("status")
        rows_i = columns.index("rows")
        raw_i = columns.index("raw_events")
        d8_i = columns.index("d8")
        ready = next(
            (
                row
                for row in rows
                if (
                    ERA_START_D8 <= int(row[d8_i]) < END_D8_EXCLUSIVE
                    and row[status_i] == "READY"
                    and int(row[rows_i]) > 0
                )
            ),
            None,
        )
        if ready is None:
            fail(f"{asset} candidate manifest has no first READY era day with rows")
            return
        choices.append((int(ready[raw_i]), asset, int(ready[d8_i])))
    raw_events, asset, d8 = max(choices)
    differential = receipt.get("future_mutation_differential", {})
    recorded = (
        differential.get("asset"),
        differential.get("d8"),
        differential.get("raw_events"),
    )
    if recorded != (asset, d8, raw_events):
        fail(
            f"differential session {recorded} differs from the manifest-derived "
            f"max-raw_events first-READY era choice {(asset, d8, raw_events)}"
        )


def check_staged_inputs(asset: str) -> None:
    staged_root = SCRATCH_RUNS / asset
    lock_path = staged_root / "locks" / f"{asset}.tsv"
    manifest_path = staged_root / "events" / asset / "manifest.tsv"
    if not lock_path.is_file() or not manifest_path.is_file():
        fail(f"{asset} staged inputs are absent under {staged_root}")
        return
    _, lock_columns, lock_rows = parse_table(lock_path)
    lock_i = lock_columns.index("d8")
    staged_lock_days = [int(row[lock_i]) for row in lock_rows]
    if staged_lock_days != lock_days(asset):
        fail(f"{asset} staged lock days differ from the canonical window filter")
    schema, columns, rows = parse_table(manifest_path)
    if f"end_d8_exclusive={END_D8_EXCLUSIVE}" not in schema:
        fail(f"{manifest_path} schema line lacks the Stage 0 window: {schema!r}")
    d8_i = columns.index("d8")
    sidecar_i = columns.index("sidecar_file")
    binary_i = columns.index("binary_file")
    staged_days = [int(row[d8_i]) for row in rows]
    escaped = [d8 for d8 in staged_days if not START_D8 <= d8 < END_D8_EXCLUSIVE]
    if escaped:
        fail(f"{asset} staged event days escape the window: {escaped[:5]}")
    if staged_days != staged_lock_days:
        fail(f"{asset} staged event days differ from staged lock days")
    expected_links: set[str] = set()
    for row in rows:
        expected_links.add(row[sidecar_i])
        if row[binary_i] != "-":
            expected_links.add(row[binary_i])
    on_disk: set[str] = set()
    events_root = staged_root / "events"
    for directory, _, names in os.walk(events_root):
        for name in names:
            path = Path(directory) / name
            relative = str(path.relative_to(staged_root))
            if relative == f"events/{asset}/manifest.tsv":
                continue
            on_disk.add(relative)
            if path.is_symlink():
                target = Path(os.readlink(path))
                if not str(target).startswith(str(CANONICAL)):
                    fail(f"{path} links outside the canonical tree: {target}")
    if on_disk != expected_links:
        difference = sorted(on_disk.symmetric_difference(expected_links))
        fail(
            f"{asset} staged event packs differ from the windowed manifest: "
            f"{difference[:5]}"
        )


def check_asset(
    asset: str,
    receipt: dict[str, object],
    pivot_receipt: dict[str, object],
) -> None:
    guard = receipt["determinism_guard"]["per_asset"][asset]
    publication = receipt["publication"][asset]
    counts = receipt["per_asset_day_counts"][asset]
    for key in (
        ("days", guard["days"]),
        ("era_days", guard["era_days"]),
        ("new_tag_days", guard["new_tag_days"]),
        ("stored_candidate_days_checked", guard["stored_candidate_days_checked"]),
    ):
        if counts[key[0]] != key[1]:
            fail(f"{asset} per_asset_day_counts[{key[0]}] disagrees with the guard")
    if publication.get("status") != "PASS" or guard.get("status") != "PASS":
        fail(f"{asset} guard or publication status is not PASS")
    if (
        publication.get("protected_2021_files_rewritten") is not False
        or publication.get("protected_2021_rows_identical") is not True
        or publication.get("manifest_regenerated_over_full_tree") is not True
        or publication.get("protected_2021_day_files") != PROTECTED_COUNTS[asset]
        or publication.get("existing_new_files_matched") != 0
    ):
        fail(f"{asset} publication flags are {publication!r}")

    locks = lock_days(asset)
    events = event_days(asset)
    if locks != events:
        fail(f"{asset} lock days differ from event manifest days in the window")

    asset_dir = PIVOT_ROOT / asset
    names = sorted(path.name for path in asset_dir.iterdir())
    day_files = [name for name in names if name != "manifest.tsv"]
    extras = [
        name
        for name in day_files
        if not (name.endswith(".tsv") and name[:-4].isdigit() and len(name) == 12)
    ]
    if extras or "manifest.tsv" not in names:
        fail(f"{asset} pivot dir has unexpected entries {extras or names}")
    disk_days = sorted(int(name[:-4]) for name in day_files if name not in extras)
    if disk_days != sorted(locks):
        fail(
            f"{asset} tag days on disk ({len(disk_days)}) differ from lock "
            f"window days ({len(locks)})"
        )
    out_of_window = [d8 for d8 in disk_days if not START_D8 <= d8 < END_D8_EXCLUSIVE]
    if out_of_window:
        fail(f"{asset} tag days escape the window: {out_of_window[:5]}")
    protected_days = [d8 for d8 in disk_days if d8 < PROTECTED_END_D8_EXCLUSIVE]
    new_days = [d8 for d8 in disk_days if d8 >= PROTECTED_END_D8_EXCLUSIVE]
    era_days = [d8 for d8 in disk_days if ERA_START_D8 <= d8 < END_D8_EXCLUSIVE]
    if len(protected_days) != PROTECTED_COUNTS[asset]:
        fail(
            f"{asset} has {len(protected_days)} protected 2021 files, "
            f"expected {PROTECTED_COUNTS[asset]}"
        )
    if (
        guard["days"] != len(disk_days)
        or guard["max_d8"] != max(disk_days)
        or guard["new_tag_days"] != len(new_days)
        or guard["era_days"] != len(era_days)
        or publication["new_files_created"] != len(new_days)
        or guard["stored_candidate_days_checked"] != len(disk_days)
    ):
        fail(
            f"{asset} receipt counts days={guard['days']} max_d8={guard['max_d8']} "
            f"new={guard['new_tag_days']} era={guard['era_days']} differ from disk "
            f"{len(disk_days)}/{max(disk_days)}/{len(new_days)}/{len(era_days)}"
        )
    if max(disk_days) != 20241231:
        fail(f"{asset} max tag day is {max(disk_days)}, expected 20241231")

    published_hashes: dict[str, str] = {}
    scratch_hashes: dict[str, str] = {}
    pivot_row_total = 0
    candidate_total = 0
    per_day_rows: dict[int, int] = {}
    for d8 in disk_days:
        path = asset_dir / f"{d8}.tsv"
        digest = sha256_file(path)
        published_hashes[str(d8)] = digest
        schema, columns, rows = parse_table(path)
        window_end = (
            PROTECTED_END_D8_EXCLUSIVE
            if d8 < PROTECTED_END_D8_EXCLUSIVE
            else END_D8_EXCLUSIVE
        )
        expected_schema = (
            f"# QRE2G1PIVOT1 start_d8={START_D8} "
            f"end_d8_exclusive={window_end} d8={d8}"
        )
        if schema != expected_schema:
            fail(f"{path} schema line is {schema!r}, expected {expected_schema!r}")
        if columns != PIVOT_COLUMNS:
            fail(
                f"{path} has {len(columns)} columns, expected the 13 closed "
                f"QRE2G1PIVOT1 fields"
            )
        stored = stored_candidates(asset, d8)
        by_id = {row["candidate_id"]: row for row in stored}
        expected_rows = sum(int(row["rung_mask"]).bit_count() for row in stored)
        seen: set[tuple[str, int]] = set()
        for fields in rows:
            row = dict(zip(PIVOT_COLUMNS, fields, strict=True))
            key = (row["candidate_id"], int(row["rung_index"]))
            candidate = by_id.get(row["candidate_id"])
            if (
                candidate is None
                or row["asset"] != asset
                or int(row["d8"]) != d8
                or int(row["side"]) != int(candidate["side"])
                or not 0 <= key[1] < 4
                or not int(candidate["rung_mask"]) & (1 << key[1])
                or key in seen
            ):
                fail(f"{path} row {key} fails the stored-candidate join")
                break
            seen.add(key)
        if len(rows) != expected_rows:
            fail(
                f"{path} has {len(rows)} pivot rows, expected {expected_rows} "
                f"from stored rung_mask popcounts"
            )
        per_day_rows[d8] = len(rows)
        pivot_row_total += len(rows)
        candidate_total += len(stored)

        generated = SCRATCH_RUNS / asset / "g1/candidates" / asset / f"{d8}.tsv"
        if candidate_projection(generated) != [
            (row["candidate_id"], row["prefix_sha256"], row["rung_mask"])
            for row in stored
        ]:
            fail(
                f"{asset}/{d8} scratch candidate projection differs from the "
                f"stored TSV"
            )
        scratch_pivot = SCRATCH_RUNS / asset / "g1/pivot" / asset / f"{d8}.tsv"
        scratch_hashes[str(d8)] = sha256_file(scratch_pivot)
        if d8 < PROTECTED_END_D8_EXCLUSIVE:
            if bytes_below_schema(scratch_pivot) != bytes_below_schema(path):
                fail(
                    f"{asset}/{d8} replayed 2021 rows differ from the protected "
                    f"published rows"
                )
        elif scratch_pivot.read_bytes() != path.read_bytes():
            fail(f"{path} differs from the guarded scratch bytes")

    if guard["candidates"] != candidate_total or guard["pivot_rows"] != pivot_row_total:
        fail(
            f"{asset} receipt candidates/pivot_rows {guard['candidates']}/"
            f"{guard['pivot_rows']} differ from disk {candidate_total}/"
            f"{pivot_row_total}"
        )

    if receipt["tag_sha256_manifest"][asset] != published_hashes:
        fail(f"{asset} tag_sha256_manifest differs from the published day hashes")
    if publication["day_tag_sha256s"] != published_hashes:
        fail(f"{asset} publication day_tag_sha256s differ from the published bytes")
    era_expected = {
        d8: digest
        for d8, digest in published_hashes.items()
        if ERA_START_D8 <= int(d8) < END_D8_EXCLUSIVE
    }
    if guard["era_tag_sha256s"] != era_expected:
        fail(f"{asset} guard era_tag_sha256s differ from the published era bytes")
    if guard.get("generated_day_tag_sha256s") != scratch_hashes:
        fail(f"{asset} guard generated_day_tag_sha256s differ from scratch bytes")
    scratch_aggregate = hashlib.sha256(
        "".join(
            f"{d8}\t{digest}\n" for d8, digest in sorted(scratch_hashes.items())
        ).encode()
    ).hexdigest()
    if scratch_aggregate != guard["aggregate_tag_sha256"]:
        fail(
            f"{asset} scratch aggregate {scratch_aggregate} differs from receipt "
            f"{guard['aggregate_tag_sha256']}"
        )
    protected_aggregate = hashlib.sha256(
        "".join(
            f"{d8}\t{published_hashes[str(d8)]}\n" for d8 in sorted(protected_days)
        ).encode()
    ).hexdigest()
    pivot_anchor = pivot_receipt["tag_sha256s"][asset]["aggregate_sha256"]
    if protected_aggregate != pivot_anchor:
        fail(
            f"{asset} protected 2021 aggregate {protected_aggregate} differs from "
            f"the pivot Stage 0 anchor {pivot_anchor}; a 2021 byte changed"
        )

    manifest_path = asset_dir / "manifest.tsv"
    manifest_sha = sha256_file(manifest_path)
    if (
        manifest_sha != receipt["manifest_sha256s"][asset]
        or manifest_sha != publication["manifest_sha256"]
    ):
        fail(f"{manifest_path} sha differs from the receipt")
    schema, columns, manifest_rows = parse_table(manifest_path)
    if schema != (
        f"# QRE2G1PIVOTMAN1 start_d8={START_D8} "
        f"end_d8_exclusive={END_D8_EXCLUSIVE}"
    ) or columns != MANIFEST_COLUMNS:
        fail(f"{manifest_path} schema or columns differ from QRE2G1PIVOTMAN1")
    if len(manifest_rows) != len(disk_days):
        fail(
            f"{manifest_path} has {len(manifest_rows)} rows, expected "
            f"{len(disk_days)}; the manifest must cover the full tree"
        )
    for fields in manifest_rows:
        row = dict(zip(MANIFEST_COLUMNS, fields, strict=True))
        if (
            row["asset"] != asset
            or row["pivot_sha256"] != published_hashes.get(row["d8"])
            or row["pivot_file"] != f"g1/pivot/{asset}/{row['d8']}.tsv"
            or int(row["rows"]) != per_day_rows.get(int(row["d8"]))
        ):
            fail(f"{manifest_path} row for {row['d8']} disagrees with disk bytes")

    era_candidate_days: list[int] = []
    _, m_columns, m_rows = parse_table(
        CANONICAL / "g1/candidates" / asset / "manifest.tsv"
    )
    d8_i = m_columns.index("d8")
    file_i = m_columns.index("candidate_file")
    for fields in m_rows:
        d8 = int(fields[d8_i])
        if not ERA_START_D8 <= d8 < END_D8_EXCLUSIVE:
            continue
        if not (CANONICAL / fields[file_i]).is_file():
            fail(f"{asset}/{d8} stored era candidate TSV is absent")
        era_candidate_days.append(d8)
    coverage = receipt["gated_era_tag_coverage"]["per_asset"][asset]
    missing = sorted(set(era_candidate_days).difference(disk_days))
    if missing:
        fail(f"{asset} stored era candidate days lack tags: {missing[:5]}")
    if (
        coverage.get("status") != "PASS"
        or coverage.get("stored_candidate_days") != len(era_candidate_days)
        or coverage.get("stored_candidate_days_with_tags") != len(era_candidate_days)
        or coverage.get("era_tag_days") != len(era_days)
        or coverage.get("missing_days") != []
        or coverage.get("max_d8") != max(disk_days)
    ):
        fail(f"{asset} gated_era_tag_coverage {coverage!r} disagrees with disk")


def check_protected_mtimes(run_start: float) -> None:
    for asset in ASSETS:
        for path in (PIVOT_ROOT / asset).iterdir():
            if path.name == "manifest.tsv":
                continue
            if int(path.stem) < PROTECTED_END_D8_EXCLUSIVE:
                stamp = path.stat().st_mtime
                if stamp >= run_start:
                    fail(
                        f"{path} protected 2021 file mtime {stamp} is inside the "
                        f"run window; it should predate the run"
                    )


def check_untouched_trees(run_start: float, run_end: float) -> None:
    for tree in UNTOUCHED_TREES:
        newest = 0.0
        newest_path = ""
        for directory, _, names in os.walk(CANONICAL / tree):
            for name in names:
                stamp = os.stat(Path(directory) / name).st_mtime
                if stamp > newest:
                    newest = stamp
                    newest_path = str(Path(directory) / name)
        if newest >= run_start:
            fail(
                f"{tree} was written during or after the run: {newest_path} "
                f"mtime {newest} >= run start {run_start}"
            )
    touched: list[str] = []
    for directory, _, names in os.walk(CANONICAL):
        for name in names:
            path = Path(directory) / name
            if run_start <= os.stat(path).st_mtime <= run_end + 5:
                touched.append(str(path.relative_to(CANONICAL)))
    unexpected = [path for path in touched if not path.startswith("g1/pivot/")]
    if unexpected:
        fail(
            f"files outside g1/pivot changed during the run window: "
            f"{unexpected[:10]}"
        )


def check_mutant_seams() -> None:
    source = G1_CPP.read_text(encoding="utf-8")
    for label, baseline, expected_count, remnant in MUTANT_SEAMS:
        count = source.count(baseline)
        if count != expected_count:
            fail(
                f"mutant seam {label} appears {count} times in g1.cpp, "
                f"expected {expected_count}"
            )
        if remnant in source:
            fail(f"mutated code for {label} is still present in g1.cpp")


def main() -> int:
    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
    pivot_receipt = json.loads(PIVOT_STAGE0_RECEIPT.read_text(encoding="utf-8"))
    receipt_stat = RECEIPT_PATH.stat()
    run_end = receipt_stat.st_mtime
    run_start = run_end - float(receipt["wall_clock_seconds"]) - 10.0

    if sorted(path.name for path in PIVOT_ROOT.iterdir()) != sorted(ASSETS):
        fail(f"{PIVOT_ROOT} holds entries beyond the three asset dirs")
    check_receipt_flags(receipt)
    check_sources(receipt)
    check_prior_pivot_anchors(receipt, pivot_receipt)
    check_projection(receipt)
    check_real_session_choice(receipt)
    for asset in ASSETS:
        check_staged_inputs(asset)
        check_asset(asset, receipt, pivot_receipt)
    check_protected_mtimes(run_start)
    check_untouched_trees(run_start, run_end)
    check_mutant_seams()

    if failures:
        print(f"REJECT {len(failures)} findings")
        for finding in failures:
            print(f"- {finding}")
        return 1
    days = [receipt["per_asset_day_counts"][asset]["days"] for asset in ASSETS]
    print("PASS all byte checks held")
    print(f"run window {run_start:.0f}..{run_end:.0f}, days per asset {days}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
