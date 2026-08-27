#!/usr/bin/env python3
"""Judge sweep for the V0 Stage 0 STOP receipt. Read-only against the repo.

Never invoke the runner without --selftest. execute() always reaches
_atomic_json and would rewrite the receipt under judgment.
Mixed-window forecast files span 2025H1 per their own markers. This sweep
reads exactly two header lines of each and never streams them.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / ".audit/threshold-v0-stage0.json"
RUNNER = ROOT / ".audit/threshold_v0_stage0.py"
B0_RECEIPT = ROOT / ".audit/threshold-b0-stage0.json"
B2_RECEIPT = ROOT / ".audit/threshold-b2-price-picker.json"
KILLED_READ = ROOT / ".audit/score_threshold_2022_2024_read.py"
ENGINE_ROOT = ROOT / "engine/entry_v2"
LATE_ROOT = ROOT / "artifacts/cache/port/entry_v2/g1/late"
LATE2021_ROOT = ROOT / "artifacts/cache/port/entry_v2/g1/late2021"
QRF4_ROOT = ROOT / "artifacts/cache/port/entry_v2/forecast"
SERVICE = ROOT / "artifacts/runs/e6_vol_forecasts_v2/vol_service_forecasts.tsv"
PINNED_ENGINE_SHA256 = (
    "a50bd4986f7bb39a0abacb4728d0e7e21528995b50b8ddebb7c541daf013b813"
)
GATE_FIELDS = (
    "arm",
    "day",
    "forecast_variance",
    "head",
    "outer_fold",
    "train_sessions_n",
)
ASSETS = ("HG", "NKD", "SI")
WORKERS_BY_ASSET = {"HG": 5, "NKD": 4, "SI": 4}
EXPECTED_STOP_REASON = (
    "V0Stop: 2025H1 forecast bytes were read by pre-run diagnostic census "
    "commands; the frozen no-2025 guard fired"
)
EXPECTED_GATE_REASON = (
    "the pinned gate loader schema and the named QRE2FORECAST4 schema "
    "do not intersect on the frozen gate fields; choosing a QRE2FORECAST4 "
    "value as forecast_variance would amend the frozen rule"
)
EXPECTED_SCOPE_GUARD = {
    "status": "STOP",
    "occurred_before_guarded_runner": True,
    "year": 2025,
    "half": "H1",
    "paths": [
        "artifacts/runs/e6_vol_forecasts_v2/vol_service_forecasts.tsv",
        "artifacts/cache/port/entry_v2/forecast/HG.qrf4.tsv",
        "artifacts/cache/port/entry_v2/forecast/NKD.qrf4.tsv",
        "artifacts/cache/port/entry_v2/forecast/SI.qrf4.tsv",
    ],
    "data_rows_read": "UNKNOWN_POSITIVE",
    "writes": 0,
    "reason": "diagnostic census commands streamed mixed-window files through EOF",
}
EXPECTED_RECEIPT_KEYS = (
    "asset_chain_workers",
    "dollar_line_formed",
    "dollar_line_reads",
    "engine_tree_start",
    "exit_overlay_started",
    "fit_started",
    "gate_source_precondition",
    "late2021_shards_written",
    "late2021_tree_created",
    "locked_era_late_store_exists",
    "locked_era_late_store_opened",
    "locked_era_late_store_written",
    "manifest_published",
    "replay_freeze_started",
    "runner_year_2025_data_rows_read",
    "schema",
    "scope_guard",
    "selftest",
    "sources",
    "stage1_started",
    "status",
    "stop_reason",
    "tickets_37_46_47_started",
    "tripwire_seconds",
    "unit",
    "wall_clock_seconds",
    "window",
    "worker_budget",
    "workers_by_asset",
    "year_2025_data_rows_read",
)
EXPECTED_ENGINE_STATUS = (
    " M engine/entry_v2/confirmation.py",
    " M engine/entry_v2/confirmation_types.py",
    " M engine/entry_v2/test_confirmation.py",
    "?? engine/entry_v2/late_teacher.py",
    "?? engine/entry_v2/test_late_teacher.py",
)

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    if not ok:
        FAILURES.append(f"{name}: {detail}" if detail else name)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def two_header_lines(path: Path) -> tuple[bytes, bytes]:
    with path.open("rb") as source:
        return source.readline(), source.readline()


def engine_tree_sha256() -> str:
    paths = sorted(
        path
        for path in ENGINE_ROOT.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(b"\0")
        digest.update(sha256_file(path).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def git_lines(arguments: list[str]) -> list[str]:
    completed = subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, capture_output=True, text=True
    )
    return completed.stdout.rstrip("\n").splitlines()


def main() -> int:
    started = time.monotonic()
    receipt_sha_at_start = sha256_file(RECEIPT)
    receipt = json.loads(RECEIPT.read_text())

    check("receipt.keys", tuple(sorted(receipt)) == EXPECTED_RECEIPT_KEYS,
          f"got {sorted(receipt)!r}")
    check("schema", receipt["schema"] == "QRE2THRESHOLDV0STAGE01")
    check("unit", receipt["unit"] == "V0_STAGE0")
    check("status", receipt["status"] == "STOP")
    check("stop_reason", receipt["stop_reason"] == EXPECTED_STOP_REASON,
          repr(receipt["stop_reason"]))
    check("window", receipt["window"] == {"start_d8": 20210101,
                                          "end_d8_exclusive": 20220101})
    check("tripwire", receipt["tripwire_seconds"] == 7200)
    check("worker_budget", receipt["worker_budget"] == 13)
    check("workers_by_asset", receipt["workers_by_asset"] == WORKERS_BY_ASSET)
    check("asset_chain_workers", receipt["asset_chain_workers"] == 3)
    check("wall_under_tripwire",
          0 < receipt["wall_clock_seconds"] < receipt["tripwire_seconds"])
    for flag in (
        "stage1_started", "replay_freeze_started", "exit_overlay_started",
        "fit_started", "dollar_line_formed", "locked_era_late_store_opened",
        "locked_era_late_store_written", "late2021_tree_created",
        "manifest_published", "tickets_37_46_47_started",
    ):
        check(f"flag.{flag}", receipt[flag] is False, repr(receipt[flag]))
    check("dollar_line_reads", receipt["dollar_line_reads"] == 0)
    check("late2021_shards_written", receipt["late2021_shards_written"] == 0)
    check("runner_2025_rows", receipt["runner_year_2025_data_rows_read"] == 0)
    check("session_2025_rows",
          receipt["year_2025_data_rows_read"] == "UNKNOWN_POSITIVE")
    check("locked_store_exists", receipt["locked_era_late_store_exists"] is True)
    check("scope_guard", receipt["scope_guard"] == EXPECTED_SCOPE_GUARD,
          repr(receipt["scope_guard"]))

    sources = receipt["sources"]
    check("sources.count", len(sources) == 9, repr(sorted(sources)))
    for rel, recorded in sources.items():
        path = ROOT / rel
        check(f"source.exists.{rel}", path.is_file())
        if path.is_file():
            check(f"source.sha.{rel}", sha256_file(path) == recorded)

    engine_start = receipt["engine_tree_start"]
    live_engine = engine_tree_sha256()
    b0_end = json.loads(B0_RECEIPT.read_text())["engine_tree_end"]
    check("engine.status", engine_start["status"] == "PASS")
    check("engine.pin", engine_start["expected_engine_tree_sha256"]
          == PINNED_ENGINE_SHA256)
    check("engine.receipt", engine_start["engine_tree_sha256"]
          == PINNED_ENGINE_SHA256)
    check("engine.live", live_engine == PINNED_ENGINE_SHA256, live_engine)
    check("engine.b0_end", b0_end["engine_tree_sha256"] == PINNED_ENGINE_SHA256)
    check("engine.head", engine_start["head"] == git_lines(["rev-parse", "HEAD"])[0])
    check("engine.worktree",
          tuple(git_lines(["status", "--porcelain", "--", "engine/entry_v2"]))
          == EXPECTED_ENGINE_STATUS)

    killed_source = KILLED_READ.read_text()
    required_block = re.search(
        r"required = \{(.*?)\}", killed_source, flags=re.DOTALL
    )
    check("loader.required_block", required_block is not None)
    if required_block is not None:
        literal_fields = sorted(re.findall(r'"([a-z_]+)"', required_block.group(1)))
        check("loader.fields", literal_fields == sorted(GATE_FIELDS),
              repr(literal_fields))
    check("loader.source_path",
          'FORECAST = REPO / "artifacts/runs/e6_vol_forecasts_v2/'
          'vol_service_forecasts.tsv"' in killed_source)

    gate = receipt["gate_source_precondition"]
    check("gate.status", gate["status"] == "STOP")
    check("gate.reason", gate["reason"] == EXPECTED_GATE_REASON, repr(gate["reason"]))
    check("gate.required", gate["required_loader_fields"] == sorted(GATE_FIELDS))
    check("gate.pinned", gate["pinned_functions"] == [
        "load_window_forecast_rows", "route_catboost_daily",
        "select_expanding_median"])
    check("gate.compatible", gate["compatible_qre2forecast4_assets"] == [])
    check("gate.membership", gate["day_membership_formed"] is False)
    check("gate.window", gate["window"] == receipt["window"])
    for counts in ("routed_counts_by_asset", "selected_counts_by_asset"):
        check(f"gate.{counts}", gate[counts] == {asset: 0 for asset in ASSETS})

    for asset in ASSETS:
        block = gate["qre2forecast4"][asset]
        path = QRF4_ROOT / f"{asset}.qrf4.tsv"
        marker_raw, columns_raw = two_header_lines(path)
        marker = marker_raw.decode().rstrip("\n")
        columns = tuple(columns_raw.decode().rstrip("\n").split("\t"))
        matched = re.fullmatch(
            r"# QRE2FORECAST4 start_d8=(\d{8}) end_d8_exclusive=(\d{8}) "
            rf"asset={asset} law_sha256=[0-9a-f]{{64}}", marker)
        check(f"qrf4.{asset}.marker", matched is not None, marker[:80])
        if matched is None:
            continue
        check(f"qrf4.{asset}.start", int(matched.group(1)) == 20210101
              == block["start_d8"])
        check(f"qrf4.{asset}.end", int(matched.group(2)) == 20250701
              == block["end_d8_exclusive"])
        check(f"qrf4.{asset}.spans_2025", block["spans_2025"] is True)
        check(f"qrf4.{asset}.zero_field_intersection",
              not set(GATE_FIELDS).intersection(columns))
        check(f"qrf4.{asset}.missing", block["missing_gate_fields"]
              == sorted(GATE_FIELDS), repr(block["missing_gate_fields"]))
        check(f"qrf4.{asset}.compatible", block["gate_schema_compatible"] is False)
        check(f"qrf4.{asset}.columns_sha",
              hashlib.sha256("\t".join(columns).encode()).hexdigest()
              == block["columns_sha256"])
        check(f"qrf4.{asset}.header_bytes",
              len(marker_raw) + len(columns_raw) == block["header_bytes_read"])
        check(f"qrf4.{asset}.rows_read", block["data_rows_read"] == 0)
        check(f"qrf4.{asset}.path",
              block["path"] == path.relative_to(ROOT).as_posix())

    service = gate["era_gate_source"]
    columns_raw, first_row_raw = two_header_lines(SERVICE)
    service_columns = columns_raw.decode().rstrip("\n").split("\t")
    first_row = first_row_raw.decode().rstrip("\n").split("\t")
    check("service.schema", set(GATE_FIELDS).issubset(service_columns))
    check("service.compatible", service["gate_schema_compatible"] is True)
    check("service.first_day",
          first_row[service_columns.index("day")] == "2022-03-09"
          == service["first_data_day"])
    check("service.header_bytes",
          len(columns_raw) + len(first_row_raw) == service["header_bytes_read"])
    check("service.later_rows", service["later_rows_read"] == 0)
    check("service.not_qrf4", service["qre2forecast4"] is False)

    check("late2021.absent", not LATE2021_ROOT.exists())
    check("stage1.scorer_absent",
          not (ROOT / ".audit/score_threshold_v0_read.py").exists())
    check("stage1.receipt_absent",
          not (ROOT / ".audit/threshold-v0-read.json").exists())

    manifest = LATE_ROOT / "manifest.tsv"
    b2_manifest_sha = json.loads(B2_RECEIPT.read_text())[
        "prior_preconditions"]["manifest_sha256"]
    check("store.manifest_pin", sha256_file(manifest) == b2_manifest_sha)
    check("store.listing",
          sorted(entry.name for entry in LATE_ROOT.iterdir())
          == ["HG", "NKD", "SI", "manifest.tsv"])
    manifest_lines = manifest.read_text().rstrip("\n").split("\n")
    shard_rows = [line.split("\t") for line in manifest_lines[2:]]
    header = manifest_lines[1].split("\t")
    path_index, sha_index = header.index("path"), header.index("sha256")
    check("store.shard_count", len(shard_rows) == 582, str(len(shard_rows)))
    disk_shards = {
        shard.relative_to(ROOT).as_posix()
        for shard in LATE_ROOT.rglob("*.tsv")
        if shard.name != "manifest.tsv"
    }
    check("store.no_stray_shards",
          disk_shards == {row[path_index] for row in shard_rows})
    for row in shard_rows:
        if sha256_file(ROOT / row[path_index]) != row[sha_index]:
            check(f"store.shard.{row[path_index]}", False, "sha mismatch")

    environment = {
        key: value for key, value in os.environ.items() if key != "QRE2_V0_MUTANT"
    }
    baseline = subprocess.run(
        [sys.executable, str(RUNNER), "--selftest"],
        cwd=ROOT, capture_output=True, text=True, env=environment,
    )
    check("selftest.exit", baseline.returncode == 0, baseline.stderr[-200:])
    if baseline.returncode == 0:
        check("selftest.payload",
              json.loads(baseline.stdout) == receipt["selftest"],
              baseline.stdout[:200])
    mutant = subprocess.run(
        [sys.executable, str(RUNNER), "--selftest"],
        cwd=ROOT, capture_output=True, text=True,
        env={**environment, "QRE2_V0_MUTANT": "gate_schema_mismatch_accepted"},
    )
    check("mutant.red", mutant.returncode != 0)
    check("mutant.seam", "gate_schema_mismatch_accepted stayed green"
          in mutant.stderr, mutant.stderr[-200:])

    check("receipt.unchanged", sha256_file(RECEIPT) == receipt_sha_at_start)
    check("runner.unchanged",
          sha256_file(RUNNER) == sources[".audit/threshold_v0_stage0.py"])

    wall = time.monotonic() - started
    if FAILURES:
        for failure in FAILURES:
            print(f"FAIL {failure}", file=sys.stderr)
        print(f"FAIL {len(FAILURES)} checks broke wall={wall:.1f}s")
        return 1
    print(
        "PASS all byte checks held "
        f"wall={wall:.1f}s status=STOP upheld from raw bytes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
