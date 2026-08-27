#!/usr/bin/env python3
"""Build and verify the preregistered B0 Stage 0 pilot."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
from types import MappingProxyType
import subprocess
import sys
import tempfile
import time
from typing import Mapping, Sequence
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.entry_v2 import common as C
from engine.entry_v2 import confirmation
from engine.entry_v2.confirmation_types import ConfirmationConfig, ConfirmationRefusal
from engine.entry_v2.corpus_units import ASSET_RAW_TICK
from engine.entry_v2.event_pack import EventPack, UNDEF_PRICE
from engine.entry_v2.late_teacher import (
    ANCHOR_DEFINITION,
    CANDIDATE_FIELDS_PARSED,
    LATE_SCHEMA,
    READY,
    TEACHER_FIELDS_PARSED,
    LateCandidate,
    LateLabelRow,
    _index_by_quality,
    _label_at_age,
    build_late_teacher_session,
    load_late_teacher_tsv,
    read_late_candidates,
    render_late_teacher_tsv,
)


RECEIPT_PATH = ROOT / ".audit/threshold-b0-stage0.json"
ENGINE_ROOT = ROOT / "engine/entry_v2"
ENGINE_START_MARKER = Path("/tmp/qre2-threshold-b0-engine-start.json")
LATE_ROOT = ROOT / "artifacts/cache/port/entry_v2/g1/late"
PILOT_ASSET = "HG"
PILOT_D8 = 20221003
WINDOW_START_D8 = 20220309
WINDOW_END_D8_EXCLUSIVE = 20250101
WORKERS = 13
TRIPWIRE_SECONDS = 2 * 60 * 60
RECEIPT_SCHEMA = "QRE2THRESHOLDB0STAGE01"
PILOT_EVENT = ROOT / f"artifacts/cache/port/entry_v2/events/{PILOT_ASSET}/{PILOT_D8}.qre2"
PILOT_CANDIDATE = ROOT / f"artifacts/cache/port/entry_v2/g1/candidates/{PILOT_ASSET}/{PILOT_D8}.tsv"
PILOT_TEACHER = ROOT / f"artifacts/cache/port/entry_v2/g1/teacher/{PILOT_ASSET}/{PILOT_D8}.tsv"
PILOT_OUTPUT = LATE_ROOT / PILOT_ASSET / f"{PILOT_D8}.tsv"
AUTHORIZED_ENGINE_DIFF = frozenset({
    "engine/entry_v2/confirmation.py",
    "engine/entry_v2/confirmation_types.py",
    "engine/entry_v2/late_teacher.py",
    "engine/entry_v2/test_confirmation.py",
    "engine/entry_v2/test_late_teacher.py",
})
PROTECTED_TREES = MappingProxyType({
    "candidates": ROOT / "artifacts/cache/port/entry_v2/g1/candidates",
    "teacher": ROOT / "artifacts/cache/port/entry_v2/g1/teacher",
    "pivot": ROOT / "artifacts/cache/port/entry_v2/g1/pivot",
    "receipts": ROOT / "artifacts/cache/port/entry_v2/g1/receipts",
})
SOURCE_FILES = (
    ROOT / ".audit/threshold_b0_stage0.py",
    ROOT / ".audit/briefs/threshold-covering-after-cfit-kill-out.md",
    ROOT / ".audit/briefs/threshold-covering-after-s1-fable-out.md",
    ROOT / ".audit/ticket45-HG-20221003-cache.json",
    ROOT / ".audit/score_threshold_2022_2024_ceiling.py",
    ROOT / ".audit/threshold-2022-2024-ceiling.json",
    ROOT / ".audit/threshold_pivot_stage0.py",
    ROOT / ".audit/score_h5_top2.py",
    ROOT / "design/entry_reset/tickets/46-extended-age-grid.md",
    ROOT / "engine/entry_v2/confirmation.py",
    ROOT / "engine/entry_v2/confirmation_types.py",
    ROOT / "engine/entry_v2/late_teacher.py",
    ROOT / "engine/entry_v2/test_confirmation.py",
    ROOT / "engine/entry_v2/test_late_teacher.py",
    PILOT_EVENT,
    PILOT_EVENT.with_suffix(".qre2.json"),
    PILOT_CANDIDATE,
    PILOT_TEACHER,
)


class Stage0Stop(RuntimeError):
    pass


def _run_git(arguments: Sequence[str]) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.rstrip()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def _atomic_json(path: Path, value: object) -> None:
    _atomic_write(
        path,
        (json.dumps(value, indent=2, sort_keys=True) + "\n").encode(),
    )


def _engine_tree_sha256() -> str:
    paths = tuple(sorted(
        path for path in ENGINE_ROOT.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    ))
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(b"\0")
        digest.update(_sha256_file(path).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def record_engine_start() -> int:
    status = _run_git([
        "status", "--porcelain", "--untracked-files=all", "--", "engine/entry_v2",
    ])
    if status:
        raise Stage0Stop(f"engine tree is not clean at dispatch: {status}")
    marker = {
        "head": _run_git(["rev-parse", "HEAD"]),
        "engine_tree_sha256": _engine_tree_sha256(),
        "status": "PASS",
        "dirty_paths": [],
    }
    _atomic_json(ENGINE_START_MARKER, marker)
    print(json.dumps(marker, sort_keys=True))
    return 0


def _load_engine_start() -> dict[str, object]:
    if not ENGINE_START_MARKER.is_file():
        raise Stage0Stop("engine-start marker is absent")
    marker = json.loads(ENGINE_START_MARKER.read_text())
    if (
        marker.get("status") != "PASS"
        or marker.get("dirty_paths") != []
        or marker.get("head") != _run_git(["rev-parse", "HEAD"])
    ):
        raise Stage0Stop("engine-start marker does not bind the current HEAD")
    return marker


def _engine_diff_paths() -> tuple[str, ...]:
    lines = _run_git([
        "status", "--porcelain", "--untracked-files=all", "--", "engine/entry_v2",
    ]).splitlines()
    paths = tuple(sorted(line[3:] for line in lines if len(line) >= 4))
    if set(paths) != AUTHORIZED_ENGINE_DIFF:
        raise Stage0Stop(
            f"engine diff escaped the ticket-46 checklist: {paths}")
    return paths


def _source_sha256s() -> dict[str, str]:
    missing = [str(path) for path in SOURCE_FILES if not path.is_file()]
    if missing:
        raise Stage0Stop(f"Stage 0 sources are absent: {missing}")
    return {
        path.relative_to(ROOT).as_posix(): _sha256_file(path)
        for path in SOURCE_FILES
    }


def _tree_fingerprint(path: Path) -> dict[str, object]:
    if not path.is_dir():
        raise Stage0Stop(f"protected tree is absent: {path}")
    files = tuple(sorted(item for item in path.rglob("*") if item.is_file()))
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        hashes = tuple(executor.map(_sha256_file, files))
    entries = tuple(
        (file.relative_to(path).as_posix(), sha256)
        for file, sha256 in zip(files, hashes, strict=True)
    )
    return {
        "files": len(files),
        "bytes": sum(file.stat().st_size for file in files),
        "tree_sha256": C.object_sha256(entries),
    }


def _protected_fingerprints() -> dict[str, dict[str, object]]:
    return {
        name: _tree_fingerprint(path)
        for name, path in PROTECTED_TREES.items()
    }


def _run_command(arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(arguments),
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _selftest() -> dict[str, object]:
    command = [
        sys.executable,
        "-m",
        "unittest",
        "engine.entry_v2.test_late_teacher",
        "engine.entry_v2.test_confirmation.CorpusAgeGrid",
    ]
    completed = _run_command(command)
    if completed.returncode != 0:
        raise Stage0Stop(
            f"late-label selftest failed: {completed.stdout}{completed.stderr}")
    mutated_grid = (*confirmation.LATE_AGE_GRID_SECONDS, 10830)
    with mock.patch.object(confirmation, "LATE_AGE_GRID_SECONDS", mutated_grid):
        try:
            _ = ConfirmationConfig(max_delay_sec=10800, age_grid="LATE").offsets
        except ConfirmationRefusal as error:
            if "does not contain" not in str(error):
                raise Stage0Stop(
                    f"off-schedule mutant refused for the wrong reason: {error}") from error
        else:
            raise Stage0Stop("off_schedule_age_accepted mutant stayed green")
    return {
        "status": "PASS",
        "command": " ".join(command),
        "stdout_sha256": _sha256_bytes(completed.stdout.encode()),
        "stderr_sha256": _sha256_bytes(completed.stderr.encode()),
        "mutants": {
            "off_schedule_age_accepted": "RED",
        },
    }


def selftest_main() -> int:
    print(json.dumps(_selftest(), sort_keys=True))
    return 0


def _build_once(
    candidates: Sequence[LateCandidate],
) -> tuple[object, bytes, float]:
    started = time.monotonic()
    with EventPack(PILOT_EVENT, verify_hash=True) as pack:
        session = build_late_teacher_session(pack, candidates)
    payload = render_late_teacher_tsv(
        session.rows,
        start_d8=WINDOW_START_D8,
        end_d8_exclusive=WINDOW_END_D8_EXCLUSIVE,
    )
    return session, payload, time.monotonic() - started


def _strict_reload(payload: bytes) -> object:
    with tempfile.TemporaryDirectory(prefix="qre2-b0-stage0-") as directory:
        path = Path(directory) / f"{PILOT_D8}.tsv"
        path.write_bytes(payload)
        loaded = load_late_teacher_tsv(path)
        reloaded = render_late_teacher_tsv(
            loaded.rows,
            start_d8=loaded.start_d8,
            end_d8_exclusive=loaded.end_d8_exclusive,
        )
    if reloaded != payload:
        raise Stage0Stop("late-label strict reload changed shard bytes")
    return loaded


def _entry_identity(row: LateLabelRow) -> tuple[object, ...]:
    return (
        row.candidate_id,
        row.age_offset_sec,
        row.snapshot_ts_ns,
        row.status,
        row.entry_bid_px,
        row.entry_ask_px,
        row.entry_mid2,
        row.frozen_cost_usd,
    )


def _mutatable_exit_positions(
    raw: np.ndarray,
    row: LateLabelRow,
    tick: int,
) -> tuple[int, ...]:
    if row.exit_ts_ns is None or row.exit_ts_ns <= row.snapshot_ts_ns:
        return ()
    same_timestamp = np.flatnonzero(
        raw["ts_recv_ns"] == np.uint64(row.exit_ts_ns))
    maximum = np.iinfo(np.int64).max - tick
    positions: list[int] = []
    for raw_index in same_timestamp:
        index = int(raw_index)
        bid = int(raw["bid_px"][index])
        ask = int(raw["ask_px"][index])
        if 0 < bid < ask <= maximum:
            positions.append(index)
    return tuple(positions)


def _future_mutation_differential(
    candidates: Sequence[LateCandidate],
    baseline_rows: Sequence[LateLabelRow],
) -> dict[str, object]:
    candidate_by_id = {candidate.candidate_id: candidate for candidate in candidates}
    with EventPack(PILOT_EVENT, verify_hash=True) as pack:
        baseline_raw = np.asarray(pack.rows)
        relevant = tuple(candidates)
        for row in baseline_rows:
            if row.status != READY or row.age_offset_sec <= 600:
                continue
            candidate = candidate_by_id[row.candidate_id]
            tick = ASSET_RAW_TICK[row.asset]
            positions = _mutatable_exit_positions(baseline_raw, row, tick)
            if not positions:
                continue
            mutated_raw = np.array(baseline_raw, copy=True)
            before: list[tuple[int, int, int]] = []
            after: list[tuple[int, int, int]] = []
            for position in positions:
                before.append((
                    int(mutated_raw["bid_px"][position]),
                    int(mutated_raw["ask_px"][position]),
                    int(mutated_raw["price"][position]),
                ))
                mutated_raw["bid_px"][position] += tick
                mutated_raw["ask_px"][position] += tick
                if int(mutated_raw["price"][position]) != UNDEF_PRICE:
                    mutated_raw["price"][position] += tick
                after.append((
                    int(mutated_raw["bid_px"][position]),
                    int(mutated_raw["ask_px"][position]),
                    int(mutated_raw["price"][position]),
                ))
            mutated_indices = _index_by_quality(mutated_raw, relevant)
            mutated = _label_at_age(
                candidate,
                mutated_indices[candidate.truth_quality_key],
                row.age_offset_sec,
            )
            if _entry_identity(row) != _entry_identity(mutated):
                raise Stage0Stop("a future event changed the age-A entry bytes")
            if row.cert_close_usd == mutated.cert_close_usd:
                continue
            mutation_ts_ns = int(mutated_raw["ts_recv_ns"][positions[0]])
            return {
                "status": "PASS",
                "asset": candidate.asset,
                "d8": candidate.d8,
                "candidate_id": candidate.candidate_id,
                "age_offset_sec": row.age_offset_sec,
                "snapshot_ts_ns": row.snapshot_ts_ns,
                "mutated_event_ordinals": list(positions),
                "mutated_event_ts_ns": mutation_ts_ns,
                "mutation_is_future": mutation_ts_ns > row.snapshot_ts_ns,
                "entry_bytes_identical": True,
                "outcome_changed": True,
                "mutation_sha256": C.object_sha256({
                    "before": before,
                    "after": after,
                }),
            }
    raise Stage0Stop(
        "pilot has no outcome-sensitive future mutation with stable entry bytes")


def _pilot() -> tuple[dict[str, object], bytes, float]:
    candidates = read_late_candidates(PILOT_CANDIDATE, PILOT_TEACHER)
    first, first_payload, first_seconds = _build_once(candidates)
    second, second_payload, second_seconds = _build_once(candidates)
    if first_payload != second_payload:
        raise Stage0Stop("two pilot builder runs produced different bytes")
    if (
        first.formation_teacher_equality_sha256
        != second.formation_teacher_equality_sha256
    ):
        raise Stage0Stop("two pilot builder runs changed teacher equality")
    loaded = _strict_reload(first_payload)
    if tuple(loaded.rows) != tuple(first.rows):
        raise Stage0Stop("strict reload changed typed late rows")
    ready_by_age = Counter(
        row.age_offset_sec for row in loaded.rows if row.status == READY)
    if not any(age > 600 and count > 0 for age, count in ready_by_age.items()):
        raise Stage0Stop("pilot atlas priced no snapshot past 600 seconds")
    if ready_by_age[10800] <= 0:
        raise Stage0Stop("pilot shard has no READY 10800-second row")
    future = _future_mutation_differential(candidates, first.rows)
    details = {
        "status": "PASS",
        "asset": PILOT_ASSET,
        "d8": PILOT_D8,
        "candidate_rows": len(candidates),
        "label_rows": len(first.rows),
        "resolved_grid_seconds": list(first.resolved_grid_seconds),
        "anchor_definition": first.anchor_definition,
        "ready_rows_by_age": {
            str(age): ready_by_age[age]
            for age in first.resolved_grid_seconds
        },
        "snapshots_past_600_emitted_and_priced": True,
        "age_10800_ready_rows": ready_by_age[10800],
        "age_10800_strict_reloaded": True,
        "strict_reload_rows": len(loaded.rows),
        "formation_teacher_rows_checked": first.formation_teacher_rows_checked,
        "formation_teacher_cert_close_byte_equality": True,
        "formation_teacher_equality_sha256": (
            first.formation_teacher_equality_sha256
        ),
        "builder_runs_byte_identical": True,
        "builder_run_seconds": [first_seconds, second_seconds],
        "output_sha256": _sha256_bytes(first_payload),
        "future_mutation_differential": future,
    }
    return details, first_payload, max(first_seconds, second_seconds)


def _projection(pilot_seconds: float) -> dict[str, object]:
    ceiling = json.loads(
        (ROOT / ".audit/threshold-2022-2024-ceiling.json").read_text())
    locked_days = dict(ceiling["gated"]["days"])
    if locked_days != {"HG": 197, "NKD": 194, "SI": 191}:
        raise Stage0Stop(f"locked denominators drifted: {locked_days}")
    total_days = sum(int(value) for value in locked_days.values())
    measured_projection = pilot_seconds * total_days / WORKERS
    ticket45 = json.loads(
        (ROOT / ".audit/ticket45-HG-20221003-cache.json").read_text())
    ticket45_seconds = float(ticket45["total_wall_seconds"])
    ticket46_projection = (
        ticket45_seconds * (16.0 / 9.0) * total_days / WORKERS
    )
    projected_seconds = max(measured_projection, ticket46_projection)
    holds = projected_seconds <= TRIPWIRE_SECONDS
    result = {
        "status": "PASS" if holds else "STOP",
        "worker_budget": WORKERS,
        "locked_asset_days": locked_days,
        "locked_asset_day_total": total_days,
        "measured_full_grid_pilot_seconds": pilot_seconds,
        "measured_projection_seconds": measured_projection,
        "ticket45_reference_seconds": ticket45_seconds,
        "ticket46_age_multiplier": 16.0 / 9.0,
        "ticket46_reference_projection_seconds": ticket46_projection,
        "projected_seconds": projected_seconds,
        "tripwire_seconds": TRIPWIRE_SECONDS,
        "holds": holds,
    }
    if not holds:
        raise Stage0Stop(
            f"582-day projection crossed {TRIPWIRE_SECONDS} seconds")
    return result


def _manifest_payload(output_sha256: str, rows: Sequence[LateLabelRow]) -> bytes:
    relative = PILOT_OUTPUT.relative_to(ROOT).as_posix()
    marker = (
        f"# QRE2G1LATEMANIFEST1 start_d8={WINDOW_START_D8} "
        f"end_d8_exclusive={WINDOW_END_D8_EXCLUSIVE} "
        f"resolved_grid_seconds={','.join(map(str, confirmation.LATE_AGE_GRID_SECONDS))}"
    )
    columns = "asset\td8\tpath\tsha256\trows\tready_rows"
    values = (
        f"{PILOT_ASSET}\t{PILOT_D8}\t{relative}\t{output_sha256}\t"
        f"{len(rows)}\t{sum(row.status == READY for row in rows)}"
    )
    return f"{marker}\n{columns}\n{values}\n".encode()


def _publish(payload: bytes) -> dict[str, object]:
    if LATE_ROOT.exists():
        unexpected = tuple(sorted(
            path.relative_to(LATE_ROOT).as_posix()
            for path in LATE_ROOT.rglob("*")
            if path.is_file()
            and path not in {PILOT_OUTPUT, LATE_ROOT / "manifest.tsv"}
        ))
        if unexpected:
            raise Stage0Stop(f"late tree contains non-pilot files: {unexpected}")
    _atomic_write(PILOT_OUTPUT, payload)
    loaded = load_late_teacher_tsv(PILOT_OUTPUT)
    if render_late_teacher_tsv(
        loaded.rows,
        start_d8=loaded.start_d8,
        end_d8_exclusive=loaded.end_d8_exclusive,
    ) != payload:
        raise Stage0Stop("published late shard did not strict-reload")
    output_sha256 = _sha256_file(PILOT_OUTPUT)
    manifest = _manifest_payload(output_sha256, loaded.rows)
    manifest_path = LATE_ROOT / "manifest.tsv"
    _atomic_write(manifest_path, manifest)
    return {
        "status": "PASS",
        "root": LATE_ROOT.relative_to(ROOT).as_posix(),
        "shard": PILOT_OUTPUT.relative_to(ROOT).as_posix(),
        "shard_sha256": output_sha256,
        "manifest": manifest_path.relative_to(ROOT).as_posix(),
        "manifest_sha256": _sha256_file(manifest_path),
        "strict_reloaded": True,
        "schema": LATE_SCHEMA,
        "rows": len(loaded.rows),
    }


def _base_receipt(started: float) -> dict[str, object]:
    return {
        "schema": RECEIPT_SCHEMA,
        "status": "STOP",
        "unit": "B0_STAGE0",
        "stage1_started": False,
        "dollar_line_formed": False,
        "worker_budget": WORKERS,
        "tripwire_seconds": TRIPWIRE_SECONDS,
        "ticket_46_scope": "amendment_and_one_session_pilot_only",
        "ticket_46_at_scale_started": False,
        "tickets_37_47_started": False,
        "teacher_fields_parsed": list(TEACHER_FIELDS_PARSED),
        "candidate_fields_parsed": list(CANDIDATE_FIELDS_PARSED),
        "stored_candidate_tree_rewritten": False,
        "stored_teacher_tree_rewritten": False,
        "stored_pivot_tree_rewritten": False,
        "stored_receipts_tree_rewritten": False,
        "wall_clock_seconds": time.monotonic() - started,
    }


def execute() -> int:
    started = time.monotonic()
    receipt = _base_receipt(started)
    try:
        receipt["engine_tree_start"] = _load_engine_start()
        receipt["authorized_engine_diff_paths"] = list(_engine_diff_paths())
        receipt["sources"] = _source_sha256s()
        protected_before = _protected_fingerprints()
        receipt["protected_trees_before"] = protected_before
        receipt["red_first"] = {
            "status": "PASS",
            "observed_before_implementation": True,
            "command": (
                "python3 -m unittest "
                "engine.entry_v2.test_confirmation.CorpusAgeGrid."
                "test_late_grid_resolves_the_preregistered_schedule "
                "engine.entry_v2.test_confirmation.CorpusAgeGrid."
                "test_late_grid_refuses_an_off_schedule_age"
            ),
            "exit_code": 1,
            "failure": "ConfirmationRefusal: max_delay_sec must be 300 or 600",
        }
        receipt["selftest"] = _selftest()
        config = ConfirmationConfig(max_delay_sec=10800, age_grid="LATE")
        receipt["amendment"] = {
            "status": "PASS",
            "resolved_grid_seconds": list(config.offsets),
            "anchor_definition": ANCHOR_DEFINITION,
            "config_receipt_sha256": config.receipt_sha256,
            "off_schedule_age_refused": True,
            "ruling": ".audit/briefs/threshold-covering-after-cfit-kill-out.md",
        }
        pilot, payload, pilot_seconds = _pilot()
        receipt["pilot"] = pilot
        receipt["projection"] = _projection(pilot_seconds)
        receipt["publication"] = _publish(payload)
        protected_after = _protected_fingerprints()
        if protected_after != protected_before:
            raise Stage0Stop("a protected stored tree changed during Stage 0")
        receipt["protected_trees_after"] = protected_after
        receipt["stored_candidate_tree_rewritten"] = False
        receipt["stored_teacher_tree_rewritten"] = False
        receipt["stored_pivot_tree_rewritten"] = False
        receipt["stored_receipts_tree_rewritten"] = False
        receipt["engine_tree_end"] = {
            "head": _run_git(["rev-parse", "HEAD"]),
            "authorized_diff_paths": list(_engine_diff_paths()),
            "engine_tree_sha256": _engine_tree_sha256(),
        }
        receipt["status"] = "PASS"
        receipt["wall_clock_seconds"] = time.monotonic() - started
        _atomic_json(RECEIPT_PATH, receipt)
        print(f"{RECEIPT_SCHEMA} PASS", flush=True)
        return 0
    except Exception as error:
        receipt["status"] = "STOP"
        receipt["stop_reason"] = f"{type(error).__name__}: {error}"
        receipt["wall_clock_seconds"] = time.monotonic() - started
        _atomic_json(RECEIPT_PATH, receipt)
        print(
            f"{RECEIPT_SCHEMA} STOP {type(error).__name__}: {error}",
            file=sys.stderr,
            flush=True,
        )
        return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record-engine-start", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    arguments = parser.parse_args()
    if arguments.record_engine_start:
        return record_engine_start()
    if arguments.selftest:
        return selftest_main()
    return execute()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Stage0Stop as error:
        print(f"{RECEIPT_SCHEMA} STOP {error}", file=sys.stderr)
        sys.exit(1)
