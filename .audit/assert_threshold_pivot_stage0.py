#!/usr/bin/env python3
"""Byte-level judge checks for .audit/threshold-pivot-stage0.json.

Re-verifies the Stage 0 receipt against published pivot tags, stored
candidates, surviving scratch outputs, and the mutant seams in g1.cpp.
Read-only. Exit 0 means every check held.
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
SCRATCH_RUNS = ROOT / "artifacts/cache/cpp/threshold-pivot-stage0/runs"
RECEIPT_PATH = ROOT / ".audit/threshold-pivot-stage0.json"
G1_CPP = ROOT / "engine/cpp/qr_entry_v2/src/g1.cpp"
ASSETS = ("HG", "NKD", "SI")
START_D8 = 20210101
END_D8_EXCLUSIVE = 20210807
THRESHOLD_START_D8 = 20210721
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


def popcount(value: int) -> int:
    return bin(value).count("1")


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
        "schema": "QRE2G1PIVOTSTAGE01",
        "status": "PASS",
        "emitted_2022_2024_tags": False,
        "teacher_fields_parsed": [],
        "tickets_started": [],
        "stored_candidate_artifacts_rewritten": False,
        "stored_teacher_artifacts_rewritten": False,
        "stored_receipt_artifacts_rewritten": False,
        "pivot_root": str(PIVOT_ROOT),
        "window": {
            "start_d8": START_D8,
            "end_d8_exclusive": END_D8_EXCLUSIVE,
            "threshold_start_d8": THRESHOLD_START_D8,
            "threshold_end_d8_exclusive": END_D8_EXCLUSIVE,
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
            (row for row in rows if row[status_i] == "READY" and int(row[rows_i]) > 0),
            None,
        )
        if ready is None:
            fail(f"{asset} candidate manifest has no READY day with rows")
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
            f"choice {(asset, d8, raw_events)}"
        )


def check_asset(asset: str, receipt: dict[str, object]) -> None:
    guard = receipt["determinism_guard"]["per_asset"][asset]
    tag_block = receipt["tag_sha256s"][asset]
    if (
        guard["manifest_sha256"] != tag_block["manifest_sha256"]
        or guard["aggregate_tag_sha256"] != tag_block["aggregate_sha256"]
        or guard["threshold_tag_sha256s"] != tag_block["threshold_days"]
    ):
        fail(f"{asset} receipt guard block and tag_sha256s block disagree")
    counts = receipt["per_asset_day_counts"][asset]
    if (
        counts["days"] != guard["days"]
        or counts["threshold_days"] != guard["threshold_days"]
        or counts["threshold_tags"] != guard["threshold_tags"]
    ):
        fail(f"{asset} per_asset_day_counts disagree with the guard block")

    locks = lock_days(asset)
    events = event_days(asset)
    if locks != events:
        fail(f"{asset} lock days differ from event manifest days in the prefix")
    threshold_expected = [d8 for d8 in locks if d8 >= THRESHOLD_START_D8]

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
            f"{asset} tag days on disk ({len(disk_days)}, "
            f"{disk_days[:2]}..{disk_days[-2:]}) differ from lock prefix days "
            f"({len(locks)})"
        )
    out_of_window = [d8 for d8 in disk_days if not START_D8 <= d8 < END_D8_EXCLUSIVE]
    if out_of_window:
        fail(f"{asset} tag days escape the window: {out_of_window}")
    era_days = [d8 for d8 in disk_days if 20220101 <= d8 < 20250101]
    if era_days:
        fail(f"{asset} emitted 2022-2024 tag days: {era_days}")
    if guard["days"] != len(disk_days) or guard["max_d8"] != max(disk_days):
        fail(
            f"{asset} receipt days/max_d8 {guard['days']}/{guard['max_d8']} differ "
            f"from disk {len(disk_days)}/{max(disk_days)}"
        )
    recorded_threshold = sorted(int(d8) for d8 in guard["threshold_tag_sha256s"])
    if recorded_threshold != threshold_expected or len(threshold_expected) != 15:
        fail(
            f"{asset} threshold tag days {recorded_threshold} differ from the "
            f"15 lock-calendar days {threshold_expected}"
        )

    day_hashes: dict[str, str] = {}
    pivot_row_total = 0
    candidate_total = 0
    per_day_rows: dict[int, int] = {}
    for d8 in disk_days:
        path = asset_dir / f"{d8}.tsv"
        digest = sha256_file(path)
        day_hashes[str(d8)] = digest
        schema, columns, rows = parse_table(path)
        expected_schema = (
            f"# QRE2G1PIVOT1 start_d8={START_D8} "
            f"end_d8_exclusive={END_D8_EXCLUSIVE} d8={d8}"
        )
        if schema != expected_schema:
            fail(f"{path} schema line is {schema!r}")
        if columns != PIVOT_COLUMNS:
            fail(
                f"{path} has {len(columns)} columns {columns}, expected the "
                f"13 closed QRE2G1PIVOT1 fields"
            )
        stored = stored_candidates(asset, d8)
        by_id = {row["candidate_id"]: row for row in stored}
        expected_rows = sum(popcount(int(row["rung_mask"])) for row in stored)
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

        generated = (
            SCRATCH_RUNS / asset / "g1/candidates" / asset / f"{d8}.tsv"
        )
        if candidate_projection(generated) != [
            (row["candidate_id"], row["prefix_sha256"], row["rung_mask"])
            for row in stored
        ]:
            fail(
                f"{asset}/{d8} scratch candidate projection differs from the "
                f"stored TSV"
            )
        scratch_pivot = SCRATCH_RUNS / asset / "g1/pivot" / asset / f"{d8}.tsv"
        if scratch_pivot.read_bytes() != path.read_bytes():
            fail(f"{path} differs from the guarded scratch bytes")

    if guard["candidates"] != candidate_total or guard["pivot_rows"] != pivot_row_total:
        fail(
            f"{asset} receipt candidates/pivot_rows {guard['candidates']}/"
            f"{guard['pivot_rows']} differ from disk {candidate_total}/"
            f"{pivot_row_total}"
        )
    for d8, digest in guard["threshold_tag_sha256s"].items():
        if day_hashes.get(d8) != digest:
            fail(
                f"{asset}/{d8} tag sha {day_hashes.get(d8)} differs from receipt "
                f"{digest}"
            )
    aggregate = hashlib.sha256(
        "".join(
            f"{d8}\t{digest}\n" for d8, digest in sorted(day_hashes.items())
        ).encode()
    ).hexdigest()
    if aggregate != guard["aggregate_tag_sha256"]:
        fail(
            f"{asset} aggregate {aggregate} differs from receipt "
            f"{guard['aggregate_tag_sha256']}"
        )

    manifest_path = asset_dir / "manifest.tsv"
    if sha256_file(manifest_path) != guard["manifest_sha256"]:
        fail(f"{manifest_path} sha differs from receipt {guard['manifest_sha256']}")
    schema, columns, manifest_rows = parse_table(manifest_path)
    if schema != (
        f"# QRE2G1PIVOTMAN1 start_d8={START_D8} "
        f"end_d8_exclusive={END_D8_EXCLUSIVE}"
    ) or columns != MANIFEST_COLUMNS:
        fail(f"{manifest_path} schema or columns differ from QRE2G1PIVOTMAN1")
    if len(manifest_rows) != len(disk_days):
        fail(
            f"{manifest_path} has {len(manifest_rows)} rows, expected "
            f"{len(disk_days)}"
        )
    manifest_row_sum = 0
    manifest_candidate_sum = 0
    for fields in manifest_rows:
        row = dict(zip(MANIFEST_COLUMNS, fields, strict=True))
        manifest_row_sum += int(row["rows"])
        manifest_candidate_sum += int(row["candidates"])
        if (
            row["asset"] != asset
            or row["pivot_sha256"] != day_hashes.get(row["d8"])
            or row["pivot_file"] != f"g1/pivot/{asset}/{row['d8']}.tsv"
            or int(row["rows"]) != per_day_rows.get(int(row["d8"]))
        ):
            fail(f"{manifest_path} row for {row['d8']} disagrees with disk bytes")
    if (
        manifest_row_sum != pivot_row_total
        or manifest_candidate_sum != candidate_total
    ):
        fail(
            f"{manifest_path} sums rows={manifest_row_sum} "
            f"candidates={manifest_candidate_sum}, disk has "
            f"{pivot_row_total}/{candidate_total}"
        )


def check_sunday_identity() -> None:
    for d8 in (20210725, 20210801):
        payloads = {
            asset: (PIVOT_ROOT / asset / f"{d8}.tsv").read_bytes()
            for asset in ASSETS
        }
        if len(set(payloads.values())) != 1:
            fail(f"{d8} tag bytes differ across assets, shared receipt sha is wrong")
        lines = payloads["HG"].decode().splitlines()
        if len(lines) != 2:
            fail(
                f"{d8} shared tag has {len(lines) - 2} rows, expected the "
                f"header-only Sunday file"
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
    unexpected = [
        path for path in touched if not path.startswith("g1/pivot/")
    ]
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
    receipt_stat = RECEIPT_PATH.stat()
    run_end = receipt_stat.st_mtime
    run_start = run_end - float(receipt["wall_clock_seconds"]) - 10.0

    check_receipt_flags(receipt)
    check_projection(receipt)
    check_real_session_choice(receipt)
    for asset in ASSETS:
        check_asset(asset, receipt)
    check_sunday_identity()
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
