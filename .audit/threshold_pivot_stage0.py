#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


ROOT = Path("/workspace")
CPP_ROOT = ROOT / "engine/cpp"
CANONICAL_ROOT = ROOT / "artifacts/cache/port/entry_v2"
SCRATCH_ROOT = ROOT / "artifacts/cache/cpp/threshold-cfit-stage0"
RECEIPT_PATH = ROOT / ".audit/threshold-cfit-stage0.json"
START_D8 = 20210101
EXISTING_TAG_END_D8_EXCLUSIVE = 20210807
ERA_START_D8 = 20220101
END_D8_EXCLUSIVE = 20250101
TRIPWIRE_SECONDS = 2 * 60 * 60
WORKER_BUDGET = 16
ASSETS = ("HG", "NKD", "SI")
RECEIPT_SCHEMA = "QRE2THRESHOLDCFITSTAGE01"
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
PIVOT_MANIFEST_COLUMNS = (
    "asset",
    "d8",
    "rows",
    "candidates",
    "pivot_file",
    "pivot_sha256",
)
SOURCE_FILES = (
    ROOT / ".audit/briefs/threshold-cfit-stage0.md",
    ROOT / ".audit/briefs/threshold-covering-after-pivot-kill-out.md",
    ROOT / ".audit/threshold_pivot_stage0.py",
    ROOT / ".audit/threshold-pivot-stage0.json",
    CPP_ROOT / "qr_entry_v2/src/g1.cpp",
    CPP_ROOT / "qr_entry_v2/tests/test_g1.cpp",
)
SYNTHETIC_TEST = (
    "EntryV2Candidates."
    "PivotBirthRowsUsePreFlipStateAndExcludeFutureRows"
)
REAL_TEST = (
    "EntryV2Candidates."
    "RealSessionFutureMutationLeavesPivotTagBytesUnchanged"
)


class Stage0Stop(RuntimeError):
    pass


def d8_after(d8: int) -> int:
    day = dt.datetime.strptime(str(d8), "%Y%m%d").date()
    return int((day + dt.timedelta(days=1)).strftime("%Y%m%d"))


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


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
        raise Stage0Stop(f"{path} has no schema line terminator")
    return payload[newline + 1:]


def source_sha256s() -> dict[str, str]:
    paths = list(SOURCE_FILES)
    for asset in ASSETS:
        paths.extend([
            CANONICAL_ROOT / "locks" / f"{asset}.tsv",
            CANONICAL_ROOT / "phases" / f"{asset}.tsv",
            CANONICAL_ROOT / "events" / asset / "manifest.tsv",
            CANONICAL_ROOT / "g1/candidates" / asset / "manifest.tsv",
        ])
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise Stage0Stop(f"source files are absent: {missing}")
    return {
        str(path.relative_to(ROOT)): sha256_file(path)
        for path in paths
    }


def pivot_day_files(directory: Path) -> dict[int, Path]:
    days: dict[int, Path] = {}
    for path in directory.iterdir():
        if path.name == "manifest.tsv":
            continue
        if (
            not path.is_file()
            or path.suffix != ".tsv"
            or len(path.stem) != 8
            or not path.stem.isdigit()
        ):
            raise Stage0Stop(f"unexpected pivot artifact {path}")
        d8 = int(path.stem)
        if d8 in days:
            raise Stage0Stop(f"duplicate pivot day {d8} under {directory}")
        days[d8] = path
    return days


def snapshot_existing_pivots() -> dict[str, dict[str, object]]:
    snapshots: dict[str, dict[str, object]] = {}
    protected_total = 0
    for asset in ASSETS:
        directory = CANONICAL_ROOT / "g1/pivot" / asset
        manifest = directory / "manifest.tsv"
        if not directory.is_dir() or not manifest.is_file():
            raise Stage0Stop(f"existing pivot tree is absent for {asset}")
        day_files = pivot_day_files(directory)
        escaped = [
            d8
            for d8 in day_files
            if d8 < START_D8 or d8 >= END_D8_EXCLUSIVE
        ]
        if escaped:
            raise Stage0Stop(
                f"{asset} existing pivot days escape Stage 0: {escaped[:5]}"
            )
        protected = {
            str(d8): sha256_file(path)
            for d8, path in sorted(day_files.items())
            if d8 < EXISTING_TAG_END_D8_EXCLUSIVE
        }
        protected_total += len(protected)
        snapshots[asset] = {
            "prior_manifest_sha256": sha256_file(manifest),
            "protected_day_sha256s": protected,
        }
    if protected_total != 433:
        raise Stage0Stop(
            f"protected 2021 pivot files total {protected_total}, expected 433"
        )
    return snapshots


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def table(path: Path) -> tuple[str, tuple[str, ...], list[dict[str, str]]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 2 or not lines[0].startswith("# "):
        raise Stage0Stop(f"{path} has no schema and header")
    columns = tuple(lines[1].split("\t"))
    rows: list[dict[str, str]] = []
    for line_number, line in enumerate(lines[2:], start=3):
        if not line:
            continue
        fields = line.split("\t")
        if len(fields) != len(columns):
            raise Stage0Stop(
                f"{path}:{line_number} has {len(fields)} fields, "
                f"expected {len(columns)}"
            )
        rows.append(dict(zip(columns, fields, strict=True)))
    return lines[0], columns, rows


def render_table(
    schema: str,
    columns: tuple[str, ...],
    rows: list[dict[str, str]],
) -> bytes:
    output = [schema, "\t".join(columns)]
    output.extend("\t".join(row[column] for column in columns) for row in rows)
    return ("\n".join(output) + "\n").encode()


def stage_table(
    source: Path,
    destination: Path,
    rows: list[dict[str, str]],
) -> None:
    schema, columns, _ = table(source)
    schema_name = schema.split()[1]
    staged_schema = (
        f"# {schema_name} start_d8={START_D8} "
        f"end_d8_exclusive={END_D8_EXCLUSIVE}"
    )
    atomic_write(destination, render_table(staged_schema, columns, rows))


def link_input(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise Stage0Stop(f"required input {source} is absent")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.symlink_to(source)


def prepare_root(asset: str) -> Path:
    output_root = SCRATCH_ROOT / "runs" / asset
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    lock_source = CANONICAL_ROOT / "locks" / f"{asset}.tsv"
    _, _, lock_rows_all = table(lock_source)
    lock_rows = [
        row
        for row in lock_rows_all
        if START_D8 <= int(row["d8"]) < END_D8_EXCLUSIVE
    ]
    if not lock_rows:
        raise Stage0Stop(f"{asset} has no lock rows in the Stage 0 prefix")
    stage_table(
        lock_source,
        output_root / "locks" / f"{asset}.tsv",
        lock_rows,
    )

    months = {int(row["d8"]) // 100 for row in lock_rows}
    phase_source = CANONICAL_ROOT / "phases" / f"{asset}.tsv"
    _, _, phase_rows_all = table(phase_source)
    phase_rows = [
        row for row in phase_rows_all if int(row["month"]) in months
    ]
    if {int(row["month"]) for row in phase_rows} != months:
        raise Stage0Stop(
            f"{asset} phase months differ from required months {sorted(months)}"
        )
    stage_table(
        phase_source,
        output_root / "phases" / f"{asset}.tsv",
        phase_rows,
    )

    event_source = CANONICAL_ROOT / "events" / asset / "manifest.tsv"
    _, _, event_rows_all = table(event_source)
    event_rows = [
        row
        for row in event_rows_all
        if START_D8 <= int(row["d8"]) < END_D8_EXCLUSIVE
    ]
    if [row["d8"] for row in event_rows] != [
        row["d8"] for row in lock_rows
    ]:
        raise Stage0Stop(
            f"{asset} event and lock day sequences differ in the prefix"
        )
    stage_table(
        event_source,
        output_root / "events" / asset / "manifest.tsv",
        event_rows,
    )
    for row in event_rows:
        sidecar = row["sidecar_file"]
        link_input(
            CANONICAL_ROOT / sidecar,
            output_root / sidecar,
        )
        if row["binary_file"] != "-":
            binary = row["binary_file"]
            link_input(
                CANONICAL_ROOT / binary,
                output_root / binary,
            )
    return output_root


def run_command(
    command: list[str],
    cwd: Path,
    *,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    return completed


def require_success(
    completed: subprocess.CompletedProcess[str],
    label: str,
) -> None:
    if completed.returncode != 0:
        excerpt = completed.stdout[-4000:]
        raise Stage0Stop(
            f"{label} exited {completed.returncode}, expected 0\n{excerpt}"
        )


def configure_and_build() -> dict[str, object]:
    ninja = shutil.which("ninja")
    if ninja is None:
        raise Stage0Stop("release preset requires Ninja, but Ninja is absent")
    configured = run_command(
        [
            "cmake",
            "--preset",
            "release",
            f"-DCMAKE_MAKE_PROGRAM={ninja}",
        ],
        CPP_ROOT,
        timeout=15 * 60,
    )
    require_success(configured, "release configure")
    started = time.monotonic()
    built = run_command(
        [
            "cmake",
            "--build",
            "--preset",
            "release",
            "--target",
            "qr_entry_v2_g1",
            "qr_entry_v2_g1_tests",
            "--parallel",
            str(WORKER_BUDGET),
        ],
        CPP_ROOT,
        timeout=30 * 60,
    )
    require_success(built, "release build")
    return {
        "status": "PASS",
        "wall_seconds": time.monotonic() - started,
        "workers": WORKER_BUDGET,
    }


def g1_test_binary() -> Path:
    binary = ROOT / "artifacts/cache/cpp/release/bin/qr_entry_v2_g1_tests"
    if not binary.is_file():
        raise Stage0Stop(f"G1 test binary {binary} is absent after build")
    return binary


def g1_binary() -> Path:
    binary = ROOT / "artifacts/cache/cpp/release/bin/qr_entry_v2_g1"
    if not binary.is_file():
        raise Stage0Stop(f"G1 binary {binary} is absent after build")
    return binary


def run_synthetic_cpp_selftest() -> dict[str, object]:
    completed = run_command(
        [str(g1_test_binary()), f"--gtest_filter={SYNTHETIC_TEST}"],
        ROOT,
        timeout=5 * 60,
    )
    require_success(completed, "pivot synthetic selftest")
    return {"status": "PASS", "test": SYNTHETIC_TEST}


def candidate_projection(path: Path) -> list[tuple[str, str, str]]:
    _, columns, rows = table(path)
    required = {"candidate_id", "prefix_sha256", "rung_mask"}
    missing = required.difference(columns)
    if missing:
        raise Stage0Stop(
            f"{path} lacks candidate guard columns {sorted(missing)}"
        )
    return [
        (
            row["candidate_id"],
            row["prefix_sha256"],
            row["rung_mask"],
        )
        for row in rows
    ]


def compare_candidates(generated: Path, stored: Path) -> int:
    generated_rows = candidate_projection(generated)
    stored_rows = candidate_projection(stored)
    if generated_rows != stored_rows:
        mismatch = next(
            (
                index
                for index, pair in enumerate(
                    zip(generated_rows, stored_rows, strict=False)
                )
                if pair[0] != pair[1]
            ),
            min(len(generated_rows), len(stored_rows)),
        )
        raise Stage0Stop(
            f"candidate drift at row {mismatch} for {generated}; "
            f"generated rows {len(generated_rows)}, "
            f"stored rows {len(stored_rows)}"
        )
    return len(generated_rows)


def guard_mutant_selftest() -> dict[str, object]:
    scratch = SCRATCH_ROOT / "guard-selftest"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    schema = "# QRE2G1CAND2 start_d8=20210101 end_d8_exclusive=20210102 d8=20210101"
    columns = ("candidate_id", "prefix_sha256", "rung_mask")
    generated_rows = [{
        "candidate_id": "QRE2V2-GOOD",
        "prefix_sha256": "a" * 64,
        "rung_mask": "3",
    }]
    generated = scratch / "generated.tsv"
    stored = scratch / "stored.tsv"
    atomic_write(generated, render_table(schema, columns, generated_rows))
    atomic_write(stored, render_table(schema, columns, generated_rows))
    compare_candidates(generated, stored)
    corrupt_rows = [dict(generated_rows[0])]
    corrupt_rows[0]["candidate_id"] = "QRE2V2-CORRUPTED"
    atomic_write(stored, render_table(schema, columns, corrupt_rows))
    refused = False
    try:
        compare_candidates(generated, stored)
    except Stage0Stop:
        refused = True
    if not refused:
        raise Stage0Stop(
            "guard mutant was accepted, expected candidate_id refusal"
        )
    return {
        "status": "KILLED",
        "mutation": "one stored candidate_id corrupted on a synthetic day",
        "refused": True,
    }


def mutant_replacements() -> tuple[tuple[str, str, str, int], ...]:
    return (
        (
            "post_cutoff_event_leaks_into_tag",
            "      pivot.conf_mid2 = birth.conf_mid2;\n",
            "      pivot.conf_mid2 =\n"
            "          candidate.event_cutoff < pack.rows.size()\n"
            "              ? pack.rows[static_cast<std::size_t>(\n"
            "                    candidate.event_cutoff)].bid_px +\n"
            "                    pack.rows[static_cast<std::size_t>(\n"
            "                    candidate.event_cutoff)].ask_px\n"
            "              : birth.conf_mid2;\n",
            1,
        ),
        (
            "leg_start_captured_after_flip",
            "        const PivotBirth birth{\n"
            "            -1, high, high_key, low, low_key, mid2, threshold};\n",
            "        const PivotBirth birth{\n"
            "            -1, high, high_key, mid2, key, mid2, threshold};\n",
            1,
        ),
        (
            "side_swapped_in_record",
            "      pivot.side = birth.side;\n",
            "      pivot.side = static_cast<std::int8_t>(-birth.side);\n",
            1,
        ),
    )


def build_g1_tests() -> subprocess.CompletedProcess[str]:
    return run_command(
        [
            "cmake",
            "--build",
            "--preset",
            "release",
            "--target",
            "qr_entry_v2_g1_tests",
            "--parallel",
            str(WORKER_BUDGET),
        ],
        CPP_ROOT,
        timeout=15 * 60,
    )


def kill_cpp_mutants() -> dict[str, object]:
    source_path = CPP_ROOT / "qr_entry_v2/src/g1.cpp"
    baseline = source_path.read_text(encoding="utf-8")
    results: dict[str, object] = {}
    try:
        for name, old, new, expected_count in mutant_replacements():
            count = baseline.count(old)
            if count != expected_count:
                raise Stage0Stop(
                    f"mutant {name} found {count} seams, "
                    f"expected {expected_count}"
                )
            source_path.write_text(
                baseline.replace(old, new, expected_count),
                encoding="utf-8",
            )
            built = build_g1_tests()
            require_success(built, f"{name} mutant build")
            tested = run_command(
                [
                    str(g1_test_binary()),
                    f"--gtest_filter={SYNTHETIC_TEST}",
                ],
                ROOT,
                timeout=5 * 60,
            )
            if tested.returncode == 0:
                raise Stage0Stop(
                    f"mutant {name} stayed green, expected the selftest to fail"
                )
            results[name] = {
                "status": "KILLED",
                "test_exit_code": tested.returncode,
            }
    finally:
        source_path.write_text(baseline, encoding="utf-8")
    restored = build_g1_tests()
    require_success(restored, "baseline rebuild after mutants")
    run_synthetic_cpp_selftest()
    return results


def candidate_manifests() -> dict[str, list[dict[str, str]]]:
    manifests: dict[str, list[dict[str, str]]] = {}
    for asset in ASSETS:
        _, _, rows = table(
            CANONICAL_ROOT / "g1/candidates" / asset / "manifest.tsv"
        )
        manifests[asset] = rows
    return manifests


def choose_real_session() -> tuple[str, int, int]:
    choices: list[tuple[int, str, int]] = []
    for asset, rows in candidate_manifests().items():
        ready = next(
            (
                row for row in rows
                if (
                    ERA_START_D8
                    <= int(row["d8"])
                    < END_D8_EXCLUSIVE
                    and row["status"] == "READY"
                    and int(row["rows"]) > 0
                )
            ),
            None,
        )
        if ready is None:
            raise Stage0Stop(
                f"{asset} has no first READY era candidate day with rows"
            )
        choices.append((int(ready["raw_events"]), asset, int(ready["d8"])))
    raw_events, asset, d8 = max(choices)
    return asset, d8, raw_events


def real_differential() -> dict[str, object]:
    asset, d8, expected_raw_events = choose_real_session()
    env = dict(os.environ)
    env.update({
        "QRE2_G1_REAL_ROOT": str(CANONICAL_ROOT),
        "QRE2_G1_REAL_ASSET": asset,
        "QRE2_G1_REAL_D8": str(d8),
    })
    completed = run_command(
        [str(g1_test_binary()), f"--gtest_filter={REAL_TEST}"],
        ROOT,
        env=env,
        timeout=30 * 60,
    )
    require_success(completed, "real-session future differential")
    marker = re.search(
        r"^QRE2_PIVOT_REAL_SESSION"
        r"\tasset=(?P<asset>[A-Z]+)"
        r"\td8=(?P<d8>\d+)"
        r"\traw_events=(?P<raw_events>\d+)"
        r"\twall_ns=(?P<wall_ns>\d+)$",
        completed.stdout,
        flags=re.MULTILINE,
    )
    if marker is None:
        raise Stage0Stop(
            "real-session differential emitted no timing marker"
        )
    raw_events = int(marker.group("raw_events"))
    if (
        marker.group("asset") != asset
        or int(marker.group("d8")) != d8
        or raw_events != expected_raw_events
    ):
        raise Stage0Stop(
            f"real-session marker {marker.group(0)!r} differs from "
            f"expected {asset}/{d8}/{expected_raw_events}"
        )
    return {
        "status": "PASS",
        "tag_bytes_identical": True,
        "asset": asset,
        "d8": d8,
        "raw_events": raw_events,
        "wall_seconds": int(marker.group("wall_ns")) / 1_000_000_000,
    }


def prefix_event_counts() -> dict[str, int]:
    totals: dict[str, int] = {}
    for asset in ASSETS:
        _, _, rows = table(
            CANONICAL_ROOT / "events" / asset / "manifest.tsv"
        )
        totals[asset] = sum(
            int(row["raw_records"])
            for row in rows
            if START_D8 <= int(row["d8"]) < END_D8_EXCLUSIVE
        )
    return totals


def project_chains(
    differential: dict[str, object],
) -> dict[str, object]:
    raw_events = int(differential["raw_events"])
    sample_seconds = float(differential["wall_seconds"])
    if raw_events <= 0 or sample_seconds <= 0.0:
        raise Stage0Stop(
            f"invalid projection sample seconds={sample_seconds}, "
            f"raw_events={raw_events}"
        )
    seconds_per_event = sample_seconds / raw_events
    projected = {
        asset: seconds_per_event * count
        for asset, count in prefix_event_counts().items()
    }
    holds = all(seconds <= TRIPWIRE_SECONDS for seconds in projected.values())
    return {
        "status": "PASS" if holds else "STOP",
        "method": "one real read-plus-generate session scaled by raw event count",
        "sample_asset": differential["asset"],
        "sample_d8": differential["d8"],
        "sample_raw_events": raw_events,
        "sample_wall_seconds": sample_seconds,
        "seconds_per_event": seconds_per_event,
        "projected_chain_seconds": projected,
        "tripwire_seconds": TRIPWIRE_SECONDS,
        "holds": holds,
    }


def run_chain(asset: str, output_root: Path) -> dict[str, object]:
    started = time.monotonic()
    try:
        completed = run_command(
            [
                str(g1_binary()),
                "--stage",
                "candidates",
                "--asset",
                asset,
                "--output-root",
                str(output_root),
                "--start-d8",
                str(START_D8),
                "--end-d8-exclusive",
                str(END_D8_EXCLUSIVE),
            ],
            ROOT,
            timeout=TRIPWIRE_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise Stage0Stop(
            f"{asset} chain crossed {TRIPWIRE_SECONDS} seconds"
        ) from error
    require_success(completed, f"{asset} candidate chain")
    return {
        "status": "PASS",
        "wall_seconds": time.monotonic() - started,
        "stdout_sha256": sha256_bytes(completed.stdout.encode()),
    }


def run_parallel_chains(
    roots: dict[str, Path],
) -> dict[str, dict[str, object]]:
    results: dict[str, dict[str, object]] = {}
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=len(ASSETS)
    ) as executor:
        futures = {
            executor.submit(run_chain, asset, roots[asset]): asset
            for asset in ASSETS
        }
        for future in concurrent.futures.as_completed(futures):
            asset = futures[future]
            results[asset] = future.result()
    return {asset: results[asset] for asset in ASSETS}


def validate_pivots(
    path: Path,
    asset: str,
    d8: int,
    candidate_rows: list[dict[str, str]],
) -> int:
    schema, columns, pivots = table(path)
    expected_schema = (
        f"# QRE2G1PIVOT1 start_d8={START_D8} "
        f"end_d8_exclusive={END_D8_EXCLUSIVE} d8={d8}"
    )
    if schema != expected_schema or columns != PIVOT_COLUMNS:
        raise Stage0Stop(
            f"{path} schema or fields differ from QRE2G1PIVOT1"
        )
    candidates = {row["candidate_id"]: row for row in candidate_rows}
    expected_rows = sum(
        int(row["rung_mask"]).bit_count() for row in candidate_rows
    )
    keys: set[tuple[str, int]] = set()
    for pivot in pivots:
        candidate = candidates.get(pivot["candidate_id"])
        rung = int(pivot["rung_index"])
        key = (pivot["candidate_id"], rung)
        if (
            candidate is None
            or pivot["asset"] != asset
            or int(pivot["d8"]) != d8
            or int(pivot["side"]) != int(candidate["side"])
            or rung < 0
            or rung >= 4
            or not (int(candidate["rung_mask"]) & (1 << rung))
            or key in keys
        ):
            raise Stage0Stop(
                f"{path} has invalid pivot key {key}"
            )
        keys.add(key)
    if len(pivots) != expected_rows:
        raise Stage0Stop(
            f"{path} has {len(pivots)} pivot rows, "
            f"expected {expected_rows}"
        )
    return len(pivots)


def guard_asset(
    asset: str,
    output_root: Path,
) -> dict[str, object]:
    _, _, lock_rows = table(output_root / "locks" / f"{asset}.tsv")
    day_hashes: dict[str, str] = {}
    era_hashes: dict[str, str] = {}
    day_candidate_counts: dict[str, int] = {}
    day_pivot_counts: dict[str, int] = {}
    candidate_count = 0
    pivot_count = 0
    stored_candidate_days_checked = 0
    new_tag_days = 0
    for lock in lock_rows:
        d8 = int(lock["d8"])
        generated_path = (
            output_root / "g1/candidates" / asset / f"{d8}.tsv"
        )
        stored_path = (
            CANONICAL_ROOT / "g1/candidates" / asset / f"{d8}.tsv"
        )
        _, _, generated_candidates = table(generated_path)
        generated_count = len(generated_candidates)
        if stored_path.is_file():
            compared_count = compare_candidates(generated_path, stored_path)
            if compared_count != generated_count:
                raise Stage0Stop(
                    f"{asset}/{d8} compared candidate count changed"
                )
            stored_candidate_days_checked += 1
        candidate_count += generated_count
        day_candidate_counts[str(d8)] = generated_count
        pivot_path = output_root / "g1/pivot" / asset / f"{d8}.tsv"
        day_pivots = validate_pivots(
            pivot_path,
            asset,
            d8,
            generated_candidates,
        )
        pivot_count += day_pivots
        day_pivot_counts[str(d8)] = day_pivots
        digest = sha256_file(pivot_path)
        day_hashes[str(d8)] = digest
        if d8 >= EXISTING_TAG_END_D8_EXCLUSIVE:
            new_tag_days += 1
        if ERA_START_D8 <= d8 < END_D8_EXCLUSIVE:
            era_hashes[str(d8)] = digest
    manifest_path = output_root / "g1/pivot" / asset / "manifest.tsv"
    schema, columns, manifest_rows = table(manifest_path)
    expected_schema = (
        f"# QRE2G1PIVOTMAN1 start_d8={START_D8} "
        f"end_d8_exclusive={END_D8_EXCLUSIVE}"
    )
    if (
        schema != expected_schema
        or columns != PIVOT_MANIFEST_COLUMNS
        or len(manifest_rows) != len(lock_rows)
    ):
        raise Stage0Stop(
            f"{manifest_path} differs from the closed pivot manifest"
        )
    for row in manifest_rows:
        d8 = row["d8"]
        if (
            row["asset"] != asset
            or row["pivot_sha256"] != day_hashes.get(d8)
            or row["pivot_file"]
            != f"g1/pivot/{asset}/{d8}.tsv"
            or int(row["rows"]) != day_pivot_counts.get(d8)
            or int(row["candidates"]) != day_candidate_counts.get(d8)
        ):
            raise Stage0Stop(
                f"{manifest_path} has an invalid row for {asset}/{d8}"
            )
    if not era_hashes:
        raise Stage0Stop(
            f"{asset} generated no {ERA_START_D8} through 2024 pivot tags"
        )
    aggregate = sha256_bytes(
        "".join(
            f"{d8}\t{digest}\n"
            for d8, digest in sorted(day_hashes.items())
        ).encode()
    )
    return {
        "status": "PASS",
        "days": len(lock_rows),
        "candidates": candidate_count,
        "pivot_rows": pivot_count,
        "stored_candidate_days_checked": stored_candidate_days_checked,
        "new_tag_days": new_tag_days,
        "era_days": len(era_hashes),
        "manifest_sha256": sha256_file(manifest_path),
        "aggregate_tag_sha256": aggregate,
        "generated_day_tag_sha256s": day_hashes,
        "era_tag_sha256s": era_hashes,
        "max_d8": max(int(row["d8"]) for row in lock_rows),
    }


def publish_asset_pivots(
    asset: str,
    output_root: Path,
    snapshot: dict[str, object],
) -> dict[str, object]:
    source_directory = output_root / "g1/pivot" / asset
    destination_directory = CANONICAL_ROOT / "g1/pivot" / asset
    source_manifest = source_directory / "manifest.tsv"
    schema, columns, source_rows = table(source_manifest)
    expected_schema = (
        f"# QRE2G1PIVOTMAN1 start_d8={START_D8} "
        f"end_d8_exclusive={END_D8_EXCLUSIVE}"
    )
    if schema != expected_schema or columns != PIVOT_MANIFEST_COLUMNS:
        raise Stage0Stop(
            f"{source_manifest} cannot regenerate the full manifest"
        )

    protected = dict(snapshot["protected_day_sha256s"])
    final_hashes: dict[str, str] = {}
    final_rows: list[dict[str, str]] = []
    protected_checked = 0
    new_files_created = 0
    existing_new_files_matched = 0
    for source_row in source_rows:
        row = dict(source_row)
        d8 = int(row["d8"])
        if not START_D8 <= d8 < END_D8_EXCLUSIVE:
            raise Stage0Stop(
                f"{asset} generated pivot day {d8} outside Stage 0"
            )
        source = source_directory / f"{d8}.tsv"
        destination = destination_directory / f"{d8}.tsv"
        if d8 < EXISTING_TAG_END_D8_EXCLUSIVE:
            expected_hash = protected.get(str(d8))
            if expected_hash is None or not destination.is_file():
                raise Stage0Stop(
                    f"{asset}/{d8} protected 2021 pivot file is absent"
                )
            if sha256_file(destination) != expected_hash:
                raise Stage0Stop(
                    f"{asset}/{d8} protected 2021 pivot bytes changed"
                )
            if bytes_below_schema(source) != bytes_below_schema(destination):
                raise Stage0Stop(
                    f"{asset}/{d8} replayed rows differ from stored rows"
                )
            protected_checked += 1
        elif destination.is_file():
            if source.read_bytes() != destination.read_bytes():
                raise Stage0Stop(
                    f"{asset}/{d8} existing era pivot bytes differ"
                )
            existing_new_files_matched += 1
        else:
            atomic_write(destination, source.read_bytes())
            new_files_created += 1
        digest = sha256_file(destination)
        final_hashes[str(d8)] = digest
        row["pivot_sha256"] = digest
        final_rows.append(row)

    destination_days = pivot_day_files(destination_directory)
    generated_days = {int(row["d8"]) for row in source_rows}
    if set(destination_days) != generated_days:
        missing = sorted(generated_days.difference(destination_days))
        extra = sorted(set(destination_days).difference(generated_days))
        raise Stage0Stop(
            f"{asset} published pivot days differ, "
            f"missing={missing[:5]} extra={extra[:5]}"
        )
    if protected_checked != len(protected):
        raise Stage0Stop(
            f"{asset} checked {protected_checked} protected files, "
            f"expected {len(protected)}"
        )

    destination_manifest = destination_directory / "manifest.tsv"
    atomic_write(
        destination_manifest,
        render_table(expected_schema, PIVOT_MANIFEST_COLUMNS, final_rows),
    )
    return {
        "status": "PASS",
        "prior_manifest_sha256": snapshot["prior_manifest_sha256"],
        "manifest_sha256": sha256_file(destination_manifest),
        "manifest_regenerated_over_full_tree": True,
        "protected_2021_day_files": protected_checked,
        "protected_2021_rows_identical": True,
        "protected_2021_files_rewritten": False,
        "new_files_created": new_files_created,
        "existing_new_files_matched": existing_new_files_matched,
        "day_tag_sha256s": final_hashes,
    }


def publish_pivots(
    roots: dict[str, Path],
    snapshots: dict[str, dict[str, object]],
) -> dict[str, dict[str, object]]:
    return {
        asset: publish_asset_pivots(
            asset,
            roots[asset],
            snapshots[asset],
        )
        for asset in ASSETS
    }


def stored_era_candidate_days(asset: str) -> list[int]:
    _, _, rows = table(
        CANONICAL_ROOT / "g1/candidates" / asset / "manifest.tsv"
    )
    days: list[int] = []
    for row in rows:
        d8 = int(row["d8"])
        if not ERA_START_D8 <= d8 < END_D8_EXCLUSIVE:
            continue
        path = CANONICAL_ROOT / row["candidate_file"]
        if not path.is_file():
            raise Stage0Stop(
                f"stored candidate TSV is absent for {asset}/{d8}"
            )
        days.append(d8)
    return days


def verify_published_pivots(
    publications: dict[str, dict[str, object]],
    snapshots: dict[str, dict[str, object]],
) -> dict[str, object]:
    per_asset: dict[str, dict[str, object]] = {}
    for asset in ASSETS:
        directory = CANONICAL_ROOT / "g1/pivot" / asset
        day_files = pivot_day_files(directory)
        escaped = [
            d8
            for d8 in day_files
            if d8 < START_D8 or d8 >= END_D8_EXCLUSIVE
        ]
        if escaped:
            raise Stage0Stop(
                f"{asset} published tag days escape Stage 0: {escaped[:5]}"
            )
        hashes = {
            str(d8): sha256_file(path)
            for d8, path in sorted(day_files.items())
        }
        if hashes != publications[asset]["day_tag_sha256s"]:
            raise Stage0Stop(
                f"{asset} published day hashes differ from publication"
            )
        protected = dict(snapshots[asset]["protected_day_sha256s"])
        current_protected = {
            d8: hashes[d8]
            for d8 in protected
            if d8 in hashes
        }
        if current_protected != protected:
            raise Stage0Stop(
                f"{asset} protected 2021 files changed during publication"
            )

        manifest_path = directory / "manifest.tsv"
        schema, columns, rows = table(manifest_path)
        expected_schema = (
            f"# QRE2G1PIVOTMAN1 start_d8={START_D8} "
            f"end_d8_exclusive={END_D8_EXCLUSIVE}"
        )
        if (
            schema != expected_schema
            or columns != PIVOT_MANIFEST_COLUMNS
            or len(rows) != len(day_files)
        ):
            raise Stage0Stop(
                f"{manifest_path} is not the full published manifest"
            )
        for row in rows:
            if row["pivot_sha256"] != hashes.get(row["d8"]):
                raise Stage0Stop(
                    f"{manifest_path} hash differs for {row['d8']}"
                )

        stored_days = stored_era_candidate_days(asset)
        missing = sorted(set(stored_days).difference(day_files))
        if missing:
            raise Stage0Stop(
                f"{asset} stored era candidates lack tags: {missing[:5]}"
            )
        era_tag_days = [
            d8 for d8 in day_files
            if ERA_START_D8 <= d8 < END_D8_EXCLUSIVE
        ]
        if not stored_days or not era_tag_days:
            raise Stage0Stop(f"{asset} has no gated-era tag coverage")
        per_asset[asset] = {
            "status": "PASS",
            "stored_candidate_days": len(stored_days),
            "stored_candidate_days_with_tags": len(stored_days),
            "era_tag_days": len(era_tag_days),
            "missing_days": [],
            "max_d8": max(day_files),
        }
    return {
        "status": "PASS",
        "scope": (
            "all stored 2022-2024 candidate TSV days, "
            "a superset of gated days"
        ),
        "per_asset": per_asset,
    }


def base_receipt(started: float) -> dict[str, object]:
    return {
        "schema": RECEIPT_SCHEMA,
        "status": "STOP",
        "window": {
            "start_d8": START_D8,
            "existing_tag_end_d8_exclusive": (
                EXISTING_TAG_END_D8_EXCLUSIVE
            ),
            "new_tag_start_d8": EXISTING_TAG_END_D8_EXCLUSIVE,
            "era_start_d8": ERA_START_D8,
            "end_d8_exclusive": END_D8_EXCLUSIVE,
        },
        "worker_budget": WORKER_BUDGET,
        "asset_chain_workers": len(ASSETS),
        "tripwire_seconds": TRIPWIRE_SECONDS,
        "peek_note": (
            "Candidate-side inputs widen to G1's own pre-decision "
            "confirmation state. No teacher artifact is parsed in Stage 0. "
            "This is a kill instrument and cannot promote."
        ),
        "teacher_fields_parsed": [],
        "stored_candidate_artifacts_rewritten": False,
        "stored_teacher_artifacts_rewritten": False,
        "stored_receipt_artifacts_rewritten": False,
        "stored_2021_pivot_day_files_rewritten": False,
        "pivot_lines_scored": False,
        "emitted_2022_2024_tags": False,
        "fit_started": False,
        "stage1_started": False,
        "units_started": ["C_STAGE0"],
        "tickets_started": [],
        "tag_can_promote": False,
        "wall_clock_seconds": time.monotonic() - started,
    }


def write_receipt(receipt: dict[str, object]) -> None:
    atomic_write(
        RECEIPT_PATH,
        (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode(),
    )


def execute() -> int:
    started = time.monotonic()
    receipt = base_receipt(started)
    try:
        if END_D8_EXCLUSIVE != 20250101:
            raise Stage0Stop(
                f"end_d8_exclusive={END_D8_EXCLUSIVE}, expected 20250101"
            )
        if not SCRATCH_ROOT.parent.is_dir():
            raise Stage0Stop(
                f"scratch parent {SCRATCH_ROOT.parent} is absent"
            )
        snapshots = snapshot_existing_pivots()
        receipt["prior_pivot_manifest_sha256s"] = {
            asset: snapshots[asset]["prior_manifest_sha256"]
            for asset in ASSETS
        }
        sources = source_sha256s()
        receipt["sources"] = sources
        SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
        receipt["build"] = configure_and_build()
        receipt["selftest"] = {
            "cpp": run_synthetic_cpp_selftest(),
            "candidate_guard": {"status": "PASS"},
        }
        receipt["mutants"] = kill_cpp_mutants()
        receipt["guard_mutant"] = guard_mutant_selftest()
        differential = real_differential()
        receipt["future_mutation_differential"] = differential
        projection = project_chains(differential)
        receipt["projection"] = projection
        if not bool(projection["holds"]):
            raise Stage0Stop(
                f"one-session projection crossed {TRIPWIRE_SECONDS} seconds"
            )
        roots = {asset: prepare_root(asset) for asset in ASSETS}
        receipt["chains"] = run_parallel_chains(roots)
        guards = {
            asset: guard_asset(asset, roots[asset])
            for asset in ASSETS
        }
        receipt["determinism_guard"] = {
            "status": "PASS",
            "fields": [
                "candidate_id sequence",
                "prefix_sha256",
                "rung_mask",
                "row count",
            ],
            "per_asset": guards,
        }
        receipt["per_asset_day_counts"] = {
            asset: {
                "days": guards[asset]["days"],
                "new_tag_days": guards[asset]["new_tag_days"],
                "era_days": guards[asset]["era_days"],
                "stored_candidate_days_checked": guards[asset][
                    "stored_candidate_days_checked"
                ],
            }
            for asset in ASSETS
        }
        if any(
            int(guards[asset]["max_d8"]) >= END_D8_EXCLUSIVE
            for asset in ASSETS
        ):
            raise Stage0Stop("a pivot tag escaped the exclusive prefix")
        publications = publish_pivots(roots, snapshots)
        coverage = verify_published_pivots(publications, snapshots)
        receipt["publication"] = publications
        receipt["gated_era_tag_coverage"] = coverage
        receipt["tag_sha256_manifest"] = {
            asset: publications[asset]["day_tag_sha256s"]
            for asset in ASSETS
        }
        receipt["manifest_sha256s"] = {
            asset: publications[asset]["manifest_sha256"]
            for asset in ASSETS
        }
        post_run_sources = source_sha256s()
        if post_run_sources != sources:
            raise Stage0Stop("a source file changed during Stage 0")
        receipt["pivot_root"] = str(CANONICAL_ROOT / "g1/pivot")
        receipt["emitted_2022_2024_tags"] = True
        receipt["status"] = "PASS"
        receipt["wall_clock_seconds"] = time.monotonic() - started
        write_receipt(receipt)
        print(f"{RECEIPT_SCHEMA} PASS", flush=True)
        return 0
    except (Stage0Stop, subprocess.TimeoutExpired) as error:
        receipt["status"] = "STOP"
        receipt["stop_reason"] = str(error)
        receipt["wall_clock_seconds"] = time.monotonic() - started
        write_receipt(receipt)
        print(f"{RECEIPT_SCHEMA} STOP {error}", flush=True)
        return 1
    except Exception as error:
        receipt["status"] = "STOP"
        receipt["stop_reason"] = (
            f"{type(error).__name__}: {error}"
        )
        receipt["wall_clock_seconds"] = time.monotonic() - started
        write_receipt(receipt)
        print(
            f"{RECEIPT_SCHEMA} STOP "
            f"{type(error).__name__}: {error}",
            flush=True,
        )
        return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    arguments = parser.parse_args()
    if arguments.selftest:
        SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
        result = guard_mutant_selftest()
        print(json.dumps(result, sort_keys=True))
        return 0
    return execute()


if __name__ == "__main__":
    sys.exit(main())
