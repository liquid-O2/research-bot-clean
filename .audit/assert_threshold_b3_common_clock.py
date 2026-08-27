#!/usr/bin/env python3
"""Judge sweep for the B3 STOP receipt. Read-only. Never runs the B3 scorer
without --selftest, never opens a late-label or stored-teacher data row, and
proves the receipt under judgment is byte-identical before and after."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RECEIPT = ROOT / ".audit/threshold-b3-common-clock.json"
SCORER = ROOT / ".audit/score_threshold_b3_common_clock.py"
BRIEF = ROOT / ".audit/briefs/threshold-b3-common-clock.md"
JUDGE_PAGE = ROOT / ".audit/briefs/threshold-b3-common-clock-judge-out.md"
OUTPUT_ROOT = ROOT / "artifacts/entry_v2/tabular_recovery/threshold/b3_common_clock_2400"
CANDIDATE_ROOT = ROOT / "artifacts/cache/port/entry_v2/g1/candidates"
EVENT_ROOT = ROOT / "artifacts/cache/port/entry_v2/events"
RECEIPTS_ROOT = ROOT / "artifacts/cache/port/entry_v2/g1/receipts"
TEACHER_ROOT = ROOT / "artifacts/cache/port/entry_v2/g1/teacher"
PIVOT_ROOT = ROOT / "artifacts/cache/port/entry_v2/g1/pivot"
LATE_ROOT = ROOT / "artifacts/cache/port/entry_v2/g1/late"
LEARNED_BLOCK = ROOT / (
    "artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/evaluation/"
    "E1R_raw_THRESHOLD/real/seed_20260820/raw_block.json"
)

ASSETS = ("HG", "NKD", "SI")
LOCKED_ASSET_DAYS = {"HG": 197, "NKD": 194, "SI": 191}
WINDOW = (20220309, 20250101)
STOP_CELL = ("HG", 20221107, "0")
STOP_REASON = "cell identity differs: HG/20221107/0"
CONFLICT_COUNTS = {"HG": 22, "NKD": 10, "SI": 20}
STOP_DAY_WINDOWS = {(1667770200, 1667804400): 124, (1667856600, 1667858400): 1}
PINNED_ENGINE_START_SHA256 = (
    "a50bd4986f7bb39a0abacb4728d0e7e21528995b50b8ddebb7c541daf013b813"
)
START_FILE_SHA256S = {
    "engine/entry_v2/tabular_live_replay.py":
        "929cf0218f0c2ba58616aa437a657bcaeb35292b26601f7e96b94c0d945f57bd",
    "engine/entry_v2/tabular_evaluation_policy.py":
        "793f8a843ebf932189e58c68a77974a3df2c83c398448b42775d6ad835c573b1",
    ".audit/assert_threshold_replay_receipt.py":
        "2d7692c991180d6c0085ce450afec7cff39ede0b1a2b72769b2af00417c62ae1",
}
TEACHER_SHA256S = {
    "engine/entry_v2/late_teacher.py":
        "0b9d7ca0098ec05bae5f5aeb7ced486535c2be7b3388dc8ca7a4cce5478657a7",
    "engine/entry_v2/confirmation_index.py":
        "64df3f7006ae02445de56f13ddd1f563a0db50f96eaec60e6a7a760e9901a720",
}
LATE_MANIFEST_SHA256 = (
    "9974d40605d4bc710f803678f9b99739d9c5d17d23269b934b38c4789967d46f"
)
LEARNED_BLOCK_FILE_SHA256 = (
    "ce3662c22247bfc988d87a24154b6c2d703a4aa52bd8d69dfb59f9186a7e4f72"
)
LEARNED_BLOCK_RECEIPT_SHA256 = (
    "7aacd05aa0daf1602eaea0178b0517e58f41983abcbe19af4666f3c00c477eea"
)
LEARNED_EVIDENCE_SHA256 = (
    "6646e5e9cb9c5185b37e58e95105510c10804dcc332e8ab23352bf5097716e3c"
)
B2_AGE_2400 = {
    "HG": {"usd_per_asset_day": 2171.738578680203, "max_drawdown_usd": 905.0},
    "NKD": {"usd_per_asset_day": 2700.3994845360826, "max_drawdown_usd": 967.5},
    "SI": {"usd_per_asset_day": 2987.0549738219897, "max_drawdown_usd": 967.5},
}
MUTANTS = (
    "future_candidate_in_roster", "event_at_decision_visible",
    "per_candidate_snapshot_reprice", "ready_filters_roster",
    "outcome_changes_selection", "repeat_phase_opportunity",
    "schema_alias_without_frozen_source", "policy_block_dollars_ignored",
    "mdd_boundary_inclusive", "policy_cap_ignored", "policy_overlap_ignored",
)
WALK_START = datetime(2026, 8, 27, 9, 55, 0, tzinfo=timezone.utc).timestamp()
WALK_END = datetime(2026, 8, 27, 10, 44, 0, tzinfo=timezone.utc).timestamp()
WALK_WINDOW_WRITES = {
    ".audit/briefs/threshold-b3-common-clock.md",
    ".audit/score_threshold_b3_common_clock.py",
    ".audit/threshold-b3-common-clock.json",
    ".audit/assert_threshold_replay_receipt.py",
    "engine/entry_v2/tabular_live_replay.py",
    "engine/entry_v2/tabular_evaluation_policy.py",
    ".audit/overnight-c-decisions.tsv",
}
EXPECTED_RECEIPT = {
    "schema": "QRE2THRESHOLDB3COMMONCLOCK1", "unit": "B3_COMMON_CLOCK_2400",
    "status": "STOP", "verdict": "STOP", "stop_reason": STOP_REASON,
    "age_seconds": 2400, "locked_asset_days": LOCKED_ASSET_DAYS,
    "worker_budget": 13, "workers_by_asset": {"HG": 5, "NKD": 4, "SI": 4},
    "expected_wall_seconds": 600.0, "tripwire_seconds": 1800.0,
    "late_label_shard_opens": 0, "stored_teacher_opens": 0,
    "fit_started": False, "judge_started": False, "year_2021_started": False,
    "exit_overlay_started": False, "touched_2025": False,
    "wall_clock_seconds": 1134.5472412090749,
}


def fail(message: str) -> None:
    print(f"FAIL {message}", file=sys.stderr, flush=True)
    raise SystemExit(1)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_receipt_frame() -> str:
    receipt_sha = sha256_file(RECEIPT)
    value = json.loads(RECEIPT.read_text())
    if value != EXPECTED_RECEIPT:
        extra = sorted(set(value) ^ set(EXPECTED_RECEIPT))
        drift = {k: (value.get(k), EXPECTED_RECEIPT.get(k))
                 for k in EXPECTED_RECEIPT if value.get(k) != EXPECTED_RECEIPT.get(k)}
        fail(f"receipt frame drifted: key-diff={extra} value-diff={drift}")
    if not value["wall_clock_seconds"] < value["tripwire_seconds"]:
        fail(f"wall {value['wall_clock_seconds']} not under tripwire")
    return receipt_sha


def check_no_outputs() -> None:
    if OUTPUT_ROOT.exists():
        fail(f"B3 output tree exists on a STOP: {OUTPUT_ROOT}")
    stray = sorted((ROOT / ".audit/briefs").glob("threshold-covering-after-b3*"))
    if stray:
        fail(f"a covering page started from the stopped unit: {stray}")


def locked_days(asset: str) -> tuple[int, ...]:
    directory = LATE_ROOT / asset
    days = tuple(sorted(int(path.stem) for path in directory.iterdir()
                        if path.is_file() and path.suffix == ".tsv"
                        and len(path.stem) == 8 and path.stem.isdigit()))
    if len(days) != LOCKED_ASSET_DAYS[asset]:
        fail(f"locked roster drifted for {asset}: {len(days)}")
    if any(not WINDOW[0] <= day < WINDOW[1] for day in days):
        fail(f"locked roster leaves the era window for {asset}")
    return days


def phase_windows(asset: str, day: int) -> dict[str, dict[tuple[int, int], int]]:
    path = CANDIDATE_ROOT / asset / f"{day}.tsv"
    lines = path.read_bytes().decode("utf-8").splitlines()
    if not lines[0].startswith("# QRE2G1CAND2 "):
        fail(f"candidate marker differs: {path}")
    columns = lines[1].split("\t")
    select = {name: columns.index(name) for name in
              ("phase", "phase_open_utc", "phase_close_utc", "compliance_status")}
    windows: dict[str, dict[tuple[int, int], int]] = {}
    for line in lines[2:]:
        if not line:
            continue
        values = line.split("\t")
        if values[select["compliance_status"]] != "CLEAR":
            continue
        key = (int(values[select["phase_open_utc"]]),
               int(values[select["phase_close_utc"]]))
        windows.setdefault(values[select["phase"]], {})
        windows[values[select["phase"]]][key] = (
            windows[values[select["phase"]]].get(key, 0) + 1)
    return windows


def check_stop_ground_and_census() -> dict[str, list[int]]:
    conflicted: dict[str, list[int]] = {asset: [] for asset in ASSETS}
    for asset in ASSETS:
        for day in locked_days(asset):
            for path in ((CANDIDATE_ROOT / asset / f"{day}.tsv"),
                         (RECEIPTS_ROOT / asset / f"{day}.candidates.json"),
                         (EVENT_ROOT / asset / f"{day}.qre2")):
                if not path.is_file():
                    fail(f"locked raw source is absent: {path}")
            windows = phase_windows(asset, day)
            bad_phases = tuple(phase for phase, rows in windows.items()
                               if len({close for _open, close in rows}) > 1)
            if bad_phases:
                if bad_phases != ("0",):
                    fail(f"conflict outside phase 0 at {asset}/{day}: {bad_phases}")
                conflicted[asset].append(day)
    counts = {asset: len(days) for asset, days in conflicted.items()}
    if counts != CONFLICT_COUNTS:
        fail(f"conflicted-cell census drifted: {counts} != {CONFLICT_COUNTS}")
    if STOP_CELL[1] not in conflicted[STOP_CELL[0]]:
        fail(f"receipt stop cell is not conflicted in raw bytes: {STOP_CELL}")
    stop_windows = phase_windows(STOP_CELL[0], STOP_CELL[1])[STOP_CELL[2]]
    if stop_windows != STOP_DAY_WINDOWS:
        fail(f"stop-cell windows drifted: {stop_windows} != {STOP_DAY_WINDOWS}")
    (main_open, main_close), (stray_open, stray_close) = sorted(stop_windows)
    if stray_open - main_open != 86400 or stray_close - stray_open != 1800:
        fail(f"stop-cell stray shape drifted: {sorted(stop_windows)}")
    return conflicted


def engine_tree_sha256(substitute_start: bool) -> str:
    paths = tuple(sorted(path for path in (ROOT / "engine/entry_v2").rglob("*")
                         if path.is_file() and "__pycache__" not in path.parts))
    digest = hashlib.sha256()
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        sha = (START_FILE_SHA256S[relative]
               if substitute_start and relative in START_FILE_SHA256S
               else sha256_file(path))
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(sha.encode())
        digest.update(b"\n")
    return digest.hexdigest()


def check_engine_scope() -> None:
    reconstructed = engine_tree_sha256(substitute_start=True)
    if reconstructed != PINNED_ENGINE_START_SHA256:
        fail(f"engine tree beyond licensed paths drifted from the start pin: "
             f"{reconstructed}")
    for relative, start_sha in START_FILE_SHA256S.items():
        if sha256_file(ROOT / relative) == start_sha:
            fail(f"licensed B3 path did not change: {relative}")
    for relative, pinned in TEACHER_SHA256S.items():
        live = sha256_file(ROOT / relative)
        if live != pinned:
            fail(f"teacher semantic source drifted: {relative} {live}")
    manifest_sha = sha256_file(LATE_ROOT / "manifest.tsv")
    if manifest_sha != LATE_MANIFEST_SHA256:
        fail(f"late store manifest drifted from the B2 pin: {manifest_sha}")


def check_learned_block() -> None:
    from dataclasses import asdict
    from engine.entry_v2 import common as C
    from engine.entry_v2.tabular_evaluation_io import (
        _evidence_from_trace_payload, _strict_payload,
    )
    if sha256_file(LEARNED_BLOCK) != LEARNED_BLOCK_FILE_SHA256:
        fail("named learned block bytes drifted")
    _source, value = _strict_payload(LEARNED_BLOCK, "QRE2TABPOLICYBLOCK2")
    if value["receipt_sha256"] != LEARNED_BLOCK_RECEIPT_SHA256:
        fail(f"learned block receipt sha drifted: {value['receipt_sha256']}")
    evidence_sha = C.object_sha256(asdict(_evidence_from_trace_payload(value)))
    if evidence_sha != LEARNED_EVIDENCE_SHA256:
        fail(f"learned block evidence reconstruction drifted: {evidence_sha}")


def check_preconditions() -> None:
    b2 = json.loads((ROOT / ".audit/threshold-b2-price-picker.json").read_text())
    b0 = json.loads((ROOT / ".audit/threshold-b0-stage0.json").read_text())
    stage1 = json.loads((ROOT / ".audit/threshold-b0-stage1.json").read_text())
    if (b2.get("status") != "LIVE" or b0.get("status") != "PASS"
            or stage1.get("status") != "LIVE"):
        fail("B0/B2 precondition status drifted")
    age = dict(b2["per_age"])["2400"]["lines"]["recside_effprice_all"]["assets"]
    for asset, expected in B2_AGE_2400.items():
        for key, value in expected.items():
            if abs(float(age[asset][key]) - value) > 1e-9:
                fail(f"B2 age-2400 provenance drifted for {asset}/{key}")
    projection = float(dict(b0["projection"])["projected_seconds"])
    if projection >= 1800.0:
        fail(f"B0 projection crosses the tripwire: {projection}")


def check_selftest_and_mutants() -> None:
    baseline = subprocess.run([sys.executable, str(SCORER), "--selftest"],
                              cwd=ROOT, capture_output=True, text=True, check=False)
    if baseline.returncode != 0:
        fail(f"baseline selftest failed: {baseline.stderr[-500:]}")
    payload = json.loads(baseline.stdout)
    if payload.get("status") != "PASS" or payload.get("era_bytes_read") != 0:
        fail(f"baseline selftest payload differs: {payload}")
    for name in MUTANTS:
        environment = dict(os.environ)
        environment["QRE2_B3_MUTANT"] = name
        completed = subprocess.run([sys.executable, str(SCORER), "--selftest"],
                                   cwd=ROOT, env=environment, capture_output=True,
                                   text=True, check=False)
        if completed.returncode == 0:
            fail(f"mutant stayed green under the judge rerun: {name}")


def check_walk_window_writes() -> None:
    skip_parts = {".git", "__pycache__", ".pytest_cache", "node_modules"}
    in_window: list[str] = []
    bytecode = 0
    for base, directories, files in os.walk(ROOT):
        directories[:] = [d for d in directories if d not in skip_parts]
        relative_base = Path(base).relative_to(ROOT).as_posix()
        if relative_base.startswith("artifacts/cache/overnight-c"):
            directories[:] = []
            continue
        for name in files:
            path = Path(base) / name
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if WALK_START <= mtime <= WALK_END:
                in_window.append(path.relative_to(ROOT).as_posix())
    protected = tuple(sorted(
        path for path in in_window
        if path.startswith("artifacts/cache/port/entry_v2/")))
    if protected:
        fail(f"protected store bytes changed in the walk window: {protected}")
    unexpected = tuple(sorted(set(in_window) - WALK_WINDOW_WRITES))
    if unexpected:
        fail(f"unexpected walk-window writes: {unexpected}")
    missing = tuple(sorted(WALK_WINDOW_WRITES - set(in_window)))
    if missing:
        fail(f"expected walk-window writes not found: {missing}")


def main() -> int:
    started = time.monotonic()
    receipt_sha_before = check_receipt_frame()
    check_no_outputs()
    if JUDGE_PAGE.exists():
        print("note: judge page already exists; sweep is a re-run", flush=True)
    conflicted = check_stop_ground_and_census()
    check_engine_scope()
    check_learned_block()
    check_preconditions()
    check_selftest_and_mutants()
    check_walk_window_writes()
    if sha256_file(RECEIPT) != receipt_sha_before:
        fail("receipt bytes changed during the judge sweep")
    wall = time.monotonic() - started
    census = {asset: len(days) for asset, days in conflicted.items()}
    print(f"PASS all byte checks held wall={wall:.1f}s status=STOP upheld "
          f"from raw bytes conflicted_cells={census}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
