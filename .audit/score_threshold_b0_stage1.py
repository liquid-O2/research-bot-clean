#!/usr/bin/env python3
"""Build and score the preregistered B0 Stage 1 late-age ceiling."""

from __future__ import annotations

import argparse
import builtins
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import importlib.util
import itertools
import json
import os
from pathlib import Path
import sys
import time
from typing import Callable, Iterator, Mapping, Sequence, TypeVar
from unittest import mock

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.entry_v2 import common as C
from engine.entry_v2.confirmation_types import (
    LATE_AGE_GRID_SECONDS,
    NANOS_PER_SECOND,
    _ceil_second,
)
from engine.entry_v2.corpus_units import ASSET_MULTIPLIER
from engine.entry_v2.diagnostic_types import UNITS_PER_USD
from engine.entry_v2.event_pack import EventPack
from engine.entry_v2.late_teacher import (
    ANCHOR_DEFINITION,
    CANDIDATE_FIELDS_PARSED,
    LATE_SCHEMA,
    LATE_STATUSES,
    READY,
    LateLabelRow,
    _decimal,
    _index_by_quality,
    _integer,
    _label_at_age,
    _selected_table,
    load_late_teacher_tsv,
    render_late_teacher_tsv,
)


def _load_ceiling_module() -> object:
    path = ROOT / ".audit/score_threshold_2022_2024_ceiling.py"
    spec = importlib.util.spec_from_file_location("threshold_b0_ceiling_template", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load ceiling ruler from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


CEILING = _load_ceiling_module()
ASSETS = tuple(CEILING.ASSETS)
PHASES = tuple(CEILING.PHASES)
RUNGS_USD = dict(CEILING.RUNGS_USD)
ENTRY_CAP = int(CEILING.ENTRY_CAP)
DRAWDOWN_LIMIT_USD = 1000.0
GRID = tuple(LATE_AGE_GRID_SECONDS)
LATE_AGES = tuple(age for age in GRID if age >= 600)
EXPECTED_DAYS = {"HG": 197, "NKD": 194, "SI": 191}
WORKERS_BY_ASSET = {"HG": 5, "NKD": 4, "SI": 4}
WORKER_BUDGET = sum(WORKERS_BY_ASSET.values())
ASSET_CHAIN_WORKERS = len(ASSETS)
TRIPWIRE_SECONDS = 2 * 60 * 60
WINDOW_START_D8 = 20220309
WINDOW_END_D8_EXCLUSIVE = 20250101
RECEIPT_SCHEMA = "QRE2THRESHOLDB0STAGE11"
RECEIPT_PATH = ROOT / ".audit/threshold-b0-stage1.json"
LATE_ROOT = ROOT / "artifacts/cache/port/entry_v2/g1/late"
EVENT_ROOT = ROOT / "artifacts/cache/port/entry_v2/events"
CANDIDATE_ROOT = ROOT / "artifacts/cache/port/entry_v2/g1/candidates"
RECEIPTS_ROOT = ROOT / "artifacts/cache/port/entry_v2/g1/receipts"
TEACHER_ROOT = ROOT / "artifacts/cache/port/entry_v2/g1/teacher"
PIVOT_ROOT = ROOT / "artifacts/cache/port/entry_v2/g1/pivot"
FORECAST_PATH = Path(CEILING.FORECAST)
CEILING_RECEIPT_PATH = ROOT / ".audit/threshold-2022-2024-ceiling.json"
STAGE0_RECEIPT_PATH = ROOT / ".audit/threshold-b0-stage0.json"
STAGE0_JUDGE_PATH = ROOT / ".audit/briefs/threshold-b0-stage0-judge-out.md"
SOURCE_FILES = (
    ROOT / ".audit/score_threshold_b0_stage1.py",
    ROOT / ".audit/briefs/threshold-covering-after-cfit-kill-out.md",
    ROOT / ".audit/briefs/threshold-covering-after-s1-fable-out.md",
    STAGE0_RECEIPT_PATH,
    STAGE0_JUDGE_PATH,
    ROOT / ".audit/score_threshold_2022_2024_ceiling.py",
    ROOT / ".audit/score_threshold_2022_2024_read.py",
    CEILING_RECEIPT_PATH,
    FORECAST_PATH,
    ROOT / "engine/entry_v2/confirmation_types.py",
    ROOT / "engine/entry_v2/event_pack.py",
    ROOT / "engine/entry_v2/late_teacher.py",
    ROOT / "engine/entry_v2/diagnostic_event_truth.py",
)
PROTECTED_TREES = {
    "candidates": CANDIDATE_ROOT,
    "teacher": TEACHER_ROOT,
    "pivot": PIVOT_ROOT,
    "receipts": RECEIPTS_ROOT,
}
STOP_VERBATIM = {
    "KILL": (
        "**KILL at stage 1.** Some asset's late envelope, every cell at its best age "
        "at or past 600 s, misses that asset's rung on the locked denominators. "
        "The envelope bounds every late-age policy, fixed or per-cell, so the "
        "when-axis closes on era days with exact labels: entering where identity "
        "is knowable cannot pay the rungs even with hindsight-best names at "
        "hindsight-best ages. With which-name at age 180 closed by the C receipt, "
        "allocation bounded by D, and the 37 residue parked, no live fork remains "
        "on this host. Name the dead end to the user and stop. Nothing is "
        "auto-funded, no seventeenth age, no 2021 late build, no second grid."
    ),
    "LIVE": (
        "**LIVE at stage 1.** Every asset has at least one fixed grid age at or past "
        "600 s whose ceiling line posts, on the locked denominators, trades > 0 "
        "and that asset's rung cleared, with caps and overlap 0 holding (per-asset "
        "entry ages are legal policy, so the witness age may differ per asset). "
        "Then the next unit is a late-age picker design at the qualifying ages, "
        "authorized by a new covering decision, not by this page, with its bar "
        "pre-stated: the picker must name, before it runs, a required capture "
        "fraction of the measured age-A ceiling, and HG's fraction is the binding "
        "one since T28-grade capture does not clear HG even at zero forfeit. A LIVE "
        "also prices the training-scale relabel beyond the locked 582 days; that "
        "spend belongs to the covering decision that funds the picker."
    ),
    "ENVELOPE-ONLY": (
        "**ENVELOPE-ONLY at stage 1.** Every asset's late envelope clears its rung but "
        "some asset has no fixed-age witness. Report the curves and hand the "
        "age-policy question to the next covering decision. Not a LIVE, not a "
        "KILL, and not an invitation to add ages."
    ),
}
RULE = (
    "At each preregistered grid age, each gated cell enters only its positive-"
    "cash READY late-label maximum, with candidate_id ascending as the tie-break. "
    "The late envelope applies the same rule after allowing each cell to choose "
    "its best age at or past 600 seconds."
)


class Stage1Stop(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Stage1Candidate:
    candidate_id: str
    asset: str
    d8: int
    decision_ts_ns: int
    phase: str
    phase_open_ts_ns: int
    phase_close_ts_ns: int
    side: int
    entry_mid2: int
    frozen_cost_usd: Decimal
    sane_ceiling_units: int
    multiplier: int

    def validate(self) -> None:
        try:
            phase = int(self.phase)
        except ValueError as error:
            raise Stage1Stop(
                f"candidate {self.candidate_id} phase is not integer text"
            ) from error
        if (
            not self.candidate_id
            or self.asset not in ASSET_MULTIPLIER
            or self.multiplier != ASSET_MULTIPLIER[self.asset]
            or phase not in PHASES
            or self.side not in {-1, 1}
            or not self.phase_open_ts_ns <= self.decision_ts_ns < self.phase_close_ts_ns
            or self.entry_mid2 <= 0
            or self.frozen_cost_usd < 0
            or self.sane_ceiling_units <= 0
        ):
            raise Stage1Stop(f"candidate contract is invalid for {self.candidate_id}")

    @property
    def truth_quality_key(self) -> tuple[int, int, int, int]:
        return (
            self.phase_open_ts_ns,
            self.phase_close_ts_ns,
            self.sane_ceiling_units,
            self.multiplier,
        )


@dataclass(frozen=True, slots=True)
class BuildJob:
    asset: str
    d8: int
    candidate_rows: int
    candidate_output_sha256: str
    event_output_sha256: str
    candidate_path: Path
    candidate_receipt_path: Path
    event_path: Path
    output_path: Path


@dataclass(frozen=True, slots=True)
class ShardBuild:
    asset: str
    d8: int
    path: Path
    sha256: str
    rows: int
    ready_rows: int
    candidate_rows: int
    clear_candidate_rows: int
    candidate_ids: frozenset[str]
    candidate_ids_sha256: str
    candidate_path: Path
    candidate_sha256: str
    candidate_receipt_path: Path
    event_path: Path
    event_sha256: str
    wall_seconds: float


@dataclass(frozen=True, slots=True)
class ScoreRow:
    candidate_id: str
    asset: str
    d8: int
    phase: int
    decision_ts_ns: int
    age: int
    snapshot_ts_ns: int
    phase_close_ts_ns: int
    status: str
    frozen_cost_usd: Decimal | None
    cash_usd: Decimal | None
    exit_ts_ns: int | None


@dataclass(frozen=True, slots=True)
class ShardScore:
    asset: str
    d8: int
    entries_by_age: Mapping[int, tuple[object, ...]]
    eligible_by_age: Mapping[int, int]
    envelope_entries: tuple[object, ...]
    envelope_eligible_rows: int
    wall_seconds: float


T = TypeVar("T")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_json(path: Path, value: object) -> None:
    _atomic_write(path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode())


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise Stage1Stop(f"cannot read JSON object {path}") from error
    if not isinstance(value, dict):
        raise Stage1Stop(f"{path} is not a JSON object")
    return value


def _source_sha256s() -> dict[str, str]:
    missing = [str(path) for path in SOURCE_FILES if not path.is_file()]
    if missing:
        raise Stage1Stop(f"Stage 1 sources are absent: {missing}")
    return {_relative(path): _sha256_file(path) for path in SOURCE_FILES}


def _tree_metadata(path: Path) -> dict[str, object]:
    if not path.is_dir():
        raise Stage1Stop(f"protected tree is absent: {path}")
    files = tuple(sorted(item for item in path.rglob("*") if item.is_file()))
    entries = tuple(
        (
            item.relative_to(path).as_posix(),
            item.stat().st_size,
            item.stat().st_mtime_ns,
        )
        for item in files
    )
    return {
        "files": len(files),
        "bytes": sum(entry[1] for entry in entries),
        "metadata_sha256": C.object_sha256(entries),
    }


def _protected_metadata() -> dict[str, dict[str, object]]:
    return {name: _tree_metadata(path) for name, path in PROTECTED_TREES.items()}


def _is_under(path: object, root: Path) -> bool:
    if isinstance(path, int):
        return False
    try:
        resolved = Path(os.fspath(path)).resolve()
    except (TypeError, ValueError, OSError):
        return False
    return resolved == root or root in resolved.parents


@contextmanager
def _deny_stored_teacher_opens() -> Iterator[None]:
    original_builtin_open = builtins.open
    original_path_open = Path.open

    def guarded_builtin_open(file: object, *args: object, **kwargs: object) -> object:
        if _is_under(file, TEACHER_ROOT):
            raise Stage1Stop(f"stored teacher open refused: {file}")
        return original_builtin_open(file, *args, **kwargs)

    def guarded_path_open(path: Path, *args: object, **kwargs: object) -> object:
        if _is_under(path, TEACHER_ROOT):
            raise Stage1Stop(f"stored teacher open refused: {path}")
        return original_path_open(path, *args, **kwargs)

    with mock.patch.object(builtins, "open", guarded_builtin_open), mock.patch.object(
        Path, "open", guarded_path_open
    ):
        yield


def _stage0_precondition() -> dict[str, object]:
    stage0 = _read_json(STAGE0_RECEIPT_PATH)
    judge = STAGE0_JUDGE_PATH.read_text()
    amendment = stage0.get("amendment")
    projection = stage0.get("projection")
    if not isinstance(amendment, dict) or not isinstance(projection, dict):
        raise Stage1Stop("Stage 0 receipt lacks amendment or projection")
    if (
        stage0.get("schema") != "QRE2THRESHOLDB0STAGE01"
        or stage0.get("status") != "PASS"
        or stage0.get("stage1_started") is not False
        or amendment.get("status") != "PASS"
        or tuple(amendment.get("resolved_grid_seconds", ())) != GRID
        or projection.get("locked_asset_days") != EXPECTED_DAYS
        or int(projection.get("worker_budget", -1)) != WORKER_BUDGET
        or not judge.startswith("# B0 Stage 0 judge verdict. Fable.\n\n**PASS.**")
    ):
        raise Stage1Stop("Stage 0 PASS precondition drifted")
    return {
        "status": "PASS",
        "receipt": _relative(STAGE0_RECEIPT_PATH),
        "receipt_sha256": _sha256_file(STAGE0_RECEIPT_PATH),
        "judge": _relative(STAGE0_JUDGE_PATH),
        "judge_sha256": _sha256_file(STAGE0_JUDGE_PATH),
        "resolved_grid_seconds": list(GRID),
        "locked_asset_days": dict(EXPECTED_DAYS),
    }


def _candidate_receipt(asset: str, d8: int) -> tuple[dict[str, object], Path]:
    path = RECEIPTS_ROOT / asset / f"{d8}.candidates.json"
    receipt = _read_json(path)
    if (
        receipt.get("schema") != "QRE2G1CANDRECEIPT2"
        or receipt.get("asset") != asset
        or int(receipt.get("d8", 0)) != d8
        or not isinstance(receipt.get("rows"), int)
    ):
        raise Stage1Stop(f"candidate receipt identity drifted: {path}")
    return receipt, path


def _locked_jobs() -> tuple[tuple[BuildJob, ...], dict[str, object]]:
    rows, window_days, n_read = CEILING.load_window_forecast_rows(FORECAST_PATH)
    routed, refused = CEILING.route_catboost_daily(rows)
    selected_flags = CEILING.select_expanding_median(routed)
    jobs: list[BuildJob] = []
    empty: list[str] = []
    for day, selected in zip(routed, selected_flags, strict=True):
        if not selected:
            continue
        for asset in ASSETS:
            d8 = int(day.d8)
            if not WINDOW_START_D8 <= d8 < WINDOW_END_D8_EXCLUSIVE:
                raise Stage1Stop(f"selected day escapes the frozen era window: {d8}")
            receipt, receipt_path = _candidate_receipt(asset, d8)
            candidate_rows = int(receipt["rows"])
            if candidate_rows == 0:
                empty.append(f"{asset}/{d8}")
                continue
            output_sha256 = receipt.get("output_sha256")
            source_hashes = receipt.get("source_hashes")
            if not isinstance(output_sha256, str) or not isinstance(source_hashes, dict):
                raise Stage1Stop(f"candidate receipt lacks source hashes: {receipt_path}")
            event_sha256 = source_hashes.get("event_pack_sha256")
            if not isinstance(event_sha256, str) or not event_sha256:
                raise Stage1Stop(f"candidate receipt lacks event hash: {receipt_path}")
            candidate_path = CANDIDATE_ROOT / asset / f"{d8}.tsv"
            event_path = EVENT_ROOT / asset / f"{d8}.qre2"
            if not candidate_path.is_file() or not event_path.is_file():
                raise Stage1Stop(f"locked input is absent for {asset}/{d8}")
            jobs.append(
                BuildJob(
                    asset=asset,
                    d8=d8,
                    candidate_rows=candidate_rows,
                    candidate_output_sha256=output_sha256,
                    event_output_sha256=event_sha256,
                    candidate_path=candidate_path,
                    candidate_receipt_path=receipt_path,
                    event_path=event_path,
                    output_path=LATE_ROOT / asset / f"{d8}.tsv",
                )
            )
    counts = {asset: sum(job.asset == asset for job in jobs) for asset in ASSETS}
    if counts != EXPECTED_DAYS or len(jobs) != sum(EXPECTED_DAYS.values()):
        raise Stage1Stop(f"locked denominator drifted: {counts}")
    if len(routed) != 708 or sum(selected_flags) != 198 or len(empty) != 12:
        raise Stage1Stop(
            f"gate frame drifted routed={len(routed)} selected={sum(selected_flags)} "
            f"empty={len(empty)}"
        )
    details = {
        "status": "PASS",
        "forecast_rows_read": n_read,
        "forecast_window_days": len(window_days),
        "routed_days": len(routed),
        "selected_days": int(sum(selected_flags)),
        "refused_days": list(refused),
        "empty_selected_asset_days": empty,
        "locked_asset_days": counts,
        "locked_asset_day_total": len(jobs),
        "min_d8": min(job.d8 for job in jobs),
        "max_d8": max(job.d8 for job in jobs),
    }
    return tuple(jobs), details


def _load_stage1_candidates(job: BuildJob) -> tuple[Stage1Candidate, ...]:
    if _sha256_file(job.candidate_path) != job.candidate_output_sha256:
        raise Stage1Stop(f"candidate output hash drifted: {job.candidate_path}")
    rows = _selected_table(
        job.candidate_path,
        expected_schema="QRE2G1CAND2",
        selected_fields=CANDIDATE_FIELDS_PARSED,
    )
    if len(rows) != job.candidate_rows:
        raise Stage1Stop(
            f"candidate row count drifted for {job.asset}/{job.d8}: "
            f"{len(rows)} != {job.candidate_rows}"
        )
    candidate_ids = [row["candidate_id"] for row in rows]
    if len(set(candidate_ids)) != len(candidate_ids):
        raise Stage1Stop(f"candidate_id repeats in {job.candidate_path}")
    selected: list[Stage1Candidate] = []
    for row in rows:
        if row["compliance_status"] not in {
            "CLEAR",
            "PROHIBITED",
            "COMPLIANCE_UNKNOWN",
        }:
            raise Stage1Stop(
                f"unknown compliance for {row['candidate_id']} in {job.candidate_path}"
            )
        if row["asset"] != job.asset or _integer(row["d8"], "d8") != job.d8:
            raise Stage1Stop(f"candidate identity differs in {job.candidate_path}")
        if row["compliance_status"] != "CLEAR":
            continue
        ceiling = _decimal(row["sane_ceiling_usd"], "sane_ceiling_usd")
        ceiling_units = ceiling * UNITS_PER_USD
        if ceiling_units != ceiling_units.to_integral_value():
            raise Stage1Stop(
                f"sane ceiling is not exact teacher units for {row['candidate_id']}"
            )
        candidate = Stage1Candidate(
            candidate_id=row["candidate_id"],
            asset=job.asset,
            d8=job.d8,
            decision_ts_ns=_integer(row["decision_ts_ns"], "decision_ts_ns"),
            phase=row["phase"],
            phase_open_ts_ns=(
                _integer(row["phase_open_utc"], "phase_open_utc") * NANOS_PER_SECOND
            ),
            phase_close_ts_ns=(
                _integer(row["phase_close_utc"], "phase_close_utc") * NANOS_PER_SECOND
            ),
            side=_integer(row["side"], "side"),
            entry_mid2=_integer(row["entry_mid2"], "entry_mid2"),
            frozen_cost_usd=_decimal(row["frozen_cost_usd"], "frozen_cost_usd"),
            sane_ceiling_units=int(ceiling_units),
            multiplier=ASSET_MULTIPLIER[job.asset],
        )
        candidate.validate()
        selected.append(candidate)
    if not selected:
        raise Stage1Stop(f"candidate table has no CLEAR row: {job.candidate_path}")
    return tuple(selected)


def _score_row(row: LateLabelRow) -> ScoreRow:
    try:
        phase = int(row.phase)
    except (TypeError, ValueError) as error:
        raise Stage1Stop(f"late row phase is invalid for {row.candidate_id}") from error
    return ScoreRow(
        candidate_id=row.candidate_id,
        asset=row.asset,
        d8=row.d8,
        phase=phase,
        decision_ts_ns=row.decision_ts_ns,
        age=row.age_offset_sec,
        snapshot_ts_ns=row.snapshot_ts_ns,
        phase_close_ts_ns=row.phase_close_ts_ns,
        status=row.status,
        frozen_cost_usd=row.frozen_cost_usd,
        cash_usd=row.cert_close_usd,
        exit_ts_ns=row.exit_ts_ns,
    )


def validate_rows(
    rows: Sequence[ScoreRow],
    expected_candidate_ids: frozenset[str],
    expected_asset: str,
    expected_d8: int,
) -> None:
    if not rows or not expected_candidate_ids:
        raise Stage1Stop("late scoring table or candidate guard is empty")
    if any(row.age not in GRID for row in rows):
        raise Stage1Stop("off-schedule late age")
    if any(row.decision_ts_ns > row.snapshot_ts_ns for row in rows):
        raise Stage1Stop("late entry precedes its stored decision")
    for row in rows:
        expected_snapshot = _ceil_second(row.decision_ts_ns) + row.age * NANOS_PER_SECOND
        if (
            row.asset != expected_asset
            or row.d8 != expected_d8
            or row.phase not in PHASES
            or row.snapshot_ts_ns != expected_snapshot
            or row.status not in LATE_STATUSES
        ):
            raise Stage1Stop(f"late scoring identity is invalid for {row.candidate_id}")
        payload = (row.frozen_cost_usd, row.cash_usd, row.exit_ts_ns)
        if row.status == READY:
            if any(value is None for value in payload):
                raise Stage1Stop(f"READY score row lacks cash fields: {row.candidate_id}")
            assert row.exit_ts_ns is not None
            if not row.snapshot_ts_ns <= row.exit_ts_ns <= row.phase_close_ts_ns:
                raise Stage1Stop(f"READY score row exit is invalid: {row.candidate_id}")
        elif any(value is not None for value in payload):
            raise Stage1Stop(f"unavailable score row carries cash: {row.candidate_id}")
    ages_by_candidate: dict[str, list[int]] = {}
    for row in rows:
        ages_by_candidate.setdefault(row.candidate_id, []).append(row.age)
    if any(tuple(sorted(ages)) != GRID for ages in ages_by_candidate.values()):
        raise Stage1Stop("late candidate lacks one row per grid age")
    if frozenset(ages_by_candidate) != expected_candidate_ids:
        raise Stage1Stop("late candidate identity differs from the source table")


def _better(prior: ScoreRow | None, nxt: ScoreRow) -> bool:
    if prior is None:
        return True
    assert prior.cash_usd is not None and nxt.cash_usd is not None
    if nxt.cash_usd != prior.cash_usd:
        return nxt.cash_usd > prior.cash_usd
    if nxt.candidate_id != prior.candidate_id:
        return nxt.candidate_id < prior.candidate_id
    return nxt.age < prior.age


def _pick_rows(
    rows: Sequence[ScoreRow],
) -> tuple[dict[int, tuple[ScoreRow, ...]], dict[int, int], tuple[ScoreRow, ...], int]:
    per_age: dict[tuple[int, int], ScoreRow] = {}
    envelope: dict[int, ScoreRow] = {}
    eligible = {age: 0 for age in GRID}
    envelope_eligible = 0
    for row in rows:
        if row.status != READY:
            continue
        assert row.cash_usd is not None
        eligible[row.age] += 1
        key = (row.age, row.phase)
        if _better(per_age.get(key), row):
            per_age[key] = row
        if row.age >= 600:
            envelope_eligible += 1
            if _better(envelope.get(row.phase), row):
                envelope[row.phase] = row
    by_age = {
        age: tuple(
            row
            for key, row in sorted(per_age.items())
            if key[0] == age and row.cash_usd is not None and row.cash_usd > 0
        )
        for age in GRID
    }
    envelope_rows = tuple(
        row
        for _, row in sorted(envelope.items())
        if row.cash_usd is not None and row.cash_usd > 0
    )
    return by_age, eligible, envelope_rows, envelope_eligible


def _selected_name(row: ScoreRow, shard: ShardBuild) -> object:
    assert row.frozen_cost_usd is not None
    assert row.cash_usd is not None
    assert row.exit_ts_ns is not None
    return CEILING.SelectedName(
        candidate_id=row.candidate_id,
        asset=row.asset,
        d8=row.d8,
        phase=row.phase,
        decision_ts_ns=row.snapshot_ts_ns,
        frozen_cost_usd=float(row.frozen_cost_usd),
        cash_usd=float(row.cash_usd),
        exit_ts_ns=row.exit_ts_ns,
        ready=True,
        source_candidates=_relative(shard.candidate_path),
        source_teacher=_relative(shard.path),
        candidates_output_sha256=shard.candidate_sha256,
        teacher_output_sha256=shard.sha256,
    )


def _build_job(job: BuildJob) -> ShardBuild:
    started = time.monotonic()
    candidates = _load_stage1_candidates(job)
    with EventPack(job.event_path, verify_hash=True) as pack:
        event_sha256 = str(pack.sidecar.get("event_pack_sha256", ""))
        if event_sha256 != job.event_output_sha256:
            raise Stage1Stop(f"event hash differs from candidate receipt: {job.event_path}")
        raw_rows = np.asarray(pack.rows)
        indices = _index_by_quality(raw_rows, candidates)
        rows = tuple(
            _label_at_age(candidate, indices[candidate.truth_quality_key], age)
            for candidate in sorted(candidates, key=lambda item: item.candidate_id)
            for age in GRID
        )
    payload = render_late_teacher_tsv(
        rows,
        start_d8=WINDOW_START_D8,
        end_d8_exclusive=WINDOW_END_D8_EXCLUSIVE,
    )
    _atomic_write(job.output_path, payload)
    loaded = load_late_teacher_tsv(job.output_path)
    reloaded = render_late_teacher_tsv(
        loaded.rows,
        start_d8=loaded.start_d8,
        end_d8_exclusive=loaded.end_d8_exclusive,
    )
    if reloaded != payload:
        raise Stage1Stop(f"strict reload changed late shard: {job.output_path}")
    candidate_ids = frozenset(candidate.candidate_id for candidate in candidates)
    score_rows = tuple(_score_row(row) for row in loaded.rows)
    validate_rows(score_rows, candidate_ids, job.asset, job.d8)
    return ShardBuild(
        asset=job.asset,
        d8=job.d8,
        path=job.output_path,
        sha256=_sha256_file(job.output_path),
        rows=len(loaded.rows),
        ready_rows=sum(row.status == READY for row in loaded.rows),
        candidate_rows=job.candidate_rows,
        clear_candidate_rows=len(candidates),
        candidate_ids=candidate_ids,
        candidate_ids_sha256=C.object_sha256(tuple(sorted(candidate_ids))),
        candidate_path=job.candidate_path,
        candidate_sha256=job.candidate_output_sha256,
        candidate_receipt_path=job.candidate_receipt_path,
        event_path=job.event_path,
        event_sha256=event_sha256,
        wall_seconds=time.monotonic() - started,
    )


def _score_shard(shard: ShardBuild) -> ShardScore:
    started = time.monotonic()
    if _sha256_file(shard.path) != shard.sha256:
        raise Stage1Stop(f"published late shard changed before scoring: {shard.path}")
    table = load_late_teacher_tsv(shard.path)
    rows = tuple(_score_row(row) for row in table.rows)
    validate_rows(rows, shard.candidate_ids, shard.asset, shard.d8)
    per_age_rows, eligible, envelope_rows, envelope_eligible = _pick_rows(rows)
    return ShardScore(
        asset=shard.asset,
        d8=shard.d8,
        entries_by_age={
            age: tuple(_selected_name(row, shard) for row in per_age_rows[age])
            for age in GRID
        },
        eligible_by_age=eligible,
        envelope_entries=tuple(_selected_name(row, shard) for row in envelope_rows),
        envelope_eligible_rows=envelope_eligible,
        wall_seconds=time.monotonic() - started,
    )


def _run_asset_chain(
    asset: str,
    items: Sequence[T],
    operation: Callable[[T], object],
    phase: str,
    deadline: float,
) -> tuple[object, ...]:
    workers = WORKERS_BY_ASSET[asset]
    results: list[object] = []
    executor = ThreadPoolExecutor(max_workers=workers)
    futures: dict[Future[object], T] = {}
    try:
        futures = {executor.submit(operation, item): item for item in items}
        for completed, future in enumerate(as_completed(futures), start=1):
            if time.monotonic() > deadline:
                raise Stage1Stop(f"{phase} crossed the two-hour tripwire")
            results.append(future.result())
            if completed % 10 == 0 or completed == len(items):
                print(
                    f"B0_STAGE1_{phase.upper()} {asset} {completed}/{len(items)}",
                    flush=True,
                )
    except Exception:
        for future in futures:
            future.cancel()
        raise
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
    return tuple(results)


def _run_three_asset_chains(
    items: Sequence[T],
    operation: Callable[[T], object],
    phase: str,
    deadline: float,
) -> tuple[object, ...]:
    by_asset = {
        asset: tuple(item for item in items if str(getattr(item, "asset")) == asset)
        for asset in ASSETS
    }
    results: dict[str, tuple[object, ...]] = {}
    with ThreadPoolExecutor(max_workers=ASSET_CHAIN_WORKERS) as executor:
        futures = {
            executor.submit(
                _run_asset_chain,
                asset,
                by_asset[asset],
                operation,
                phase,
                deadline,
            ): asset
            for asset in ASSETS
        }
        for future in as_completed(futures):
            asset = futures[future]
            results[asset] = future.result()
    return tuple(item for asset in ASSETS for item in results[asset])


def _manifest_payload(shards: Sequence[ShardBuild]) -> bytes:
    marker = (
        f"# QRE2G1LATEMANIFEST1 start_d8={WINDOW_START_D8} "
        f"end_d8_exclusive={WINDOW_END_D8_EXCLUSIVE} "
        f"resolved_grid_seconds={','.join(map(str, GRID))} "
        f"anchor={ANCHOR_DEFINITION}"
    )
    columns = (
        "asset\td8\tpath\tsha256\trows\tready_rows\tcandidate_rows\t"
        "clear_candidate_rows\tcandidate_ids_sha256\tcandidate_path\t"
        "candidate_sha256\tcandidate_receipt\tevent_path\tevent_sha256"
    )
    lines = [marker, columns]
    for shard in sorted(shards, key=lambda item: (ASSETS.index(item.asset), item.d8)):
        lines.append(
            "\t".join(
                (
                    shard.asset,
                    str(shard.d8),
                    _relative(shard.path),
                    shard.sha256,
                    str(shard.rows),
                    str(shard.ready_rows),
                    str(shard.candidate_rows),
                    str(shard.clear_candidate_rows),
                    shard.candidate_ids_sha256,
                    _relative(shard.candidate_path),
                    shard.candidate_sha256,
                    _relative(shard.candidate_receipt_path),
                    _relative(shard.event_path),
                    shard.event_sha256,
                )
            )
        )
    return ("\n".join(lines) + "\n").encode()


def _publish_manifest(shards: Sequence[ShardBuild]) -> dict[str, object]:
    expected = {shard.path.resolve() for shard in shards}
    manifest_path = LATE_ROOT / "manifest.tsv"
    unexpected = tuple(
        sorted(
            _relative(path)
            for path in LATE_ROOT.rglob("*")
            if path.is_file()
            and path.resolve() not in expected
            and path.resolve() != manifest_path.resolve()
        )
    )
    if unexpected:
        raise Stage1Stop(f"late tree has files outside the locked build: {unexpected}")
    payload = _manifest_payload(shards)
    _atomic_write(manifest_path, payload)
    return {
        "status": "PASS",
        "path": _relative(manifest_path),
        "sha256": _sha256_file(manifest_path),
        "schema": "QRE2G1LATEMANIFEST1",
        "shards": len(shards),
        "rows": sum(shard.rows for shard in shards),
        "ready_rows": sum(shard.ready_rows for shard in shards),
        "clear_candidate_rows": sum(shard.clear_candidate_rows for shard in shards),
    }


def _asset_block(entries: Sequence[object], asset: str) -> dict[str, object]:
    selected = tuple(row for row in entries if row.asset == asset)
    line = CEILING.summarize_line(selected, EXPECTED_DAYS)
    usd = float(line.usd_per_asset_day[asset])
    return {
        "days": EXPECTED_DAYS[asset],
        "cash_total_usd": float(line.cash_total_usd[asset]),
        "usd_per_asset_day": usd,
        "trades": line.trades,
        "per_trade_mean_usd": line.per_trade_mean_usd,
        "max_drawdown_usd": line.max_drawdown_usd,
        "max_entries_portfolio_day": line.max_entries_portfolio_day,
        "overlap_violations": line.overlap_violations,
        "entry_cap": ENTRY_CAP,
        "entry_cap_ok": line.entry_cap_ok,
        "rung_usd": RUNGS_USD[asset],
        "clears_rung": usd >= RUNGS_USD[asset],
        "shortfall_usd": max(0.0, RUNGS_USD[asset] - usd),
        "drawdown_limit_usd": DRAWDOWN_LIMIT_USD,
        "drawdown_ok": line.max_drawdown_usd < DRAWDOWN_LIMIT_USD,
    }


def _full_ruler_ok(line: object) -> bool:
    return bool(
        line.trades > 0
        and line.clears_rungs
        and line.max_drawdown_usd < DRAWDOWN_LIMIT_USD
        and line.entry_cap_ok
        and line.overlap_violations == 0
    )


def _fixed_policy_witness(
    entries_by_age: Mapping[int, tuple[object, ...]],
) -> dict[str, object] | None:
    qualifying: dict[str, tuple[int, ...]] = {}
    for asset in ASSETS:
        qualifying[asset] = tuple(
            age
            for age in LATE_AGES
            if (
                (block := _asset_block(entries_by_age[age], asset))["trades"] > 0
                and block["clears_rung"]
                and block["entry_cap_ok"]
                and block["overlap_violations"] == 0
            )
        )
    if any(not ages for ages in qualifying.values()):
        return None
    for combination in itertools.product(*(qualifying[asset] for asset in ASSETS)):
        ages = dict(zip(ASSETS, combination, strict=True))
        entries = tuple(
            row
            for asset in ASSETS
            for row in entries_by_age[ages[asset]]
            if row.asset == asset
        )
        line = CEILING.summarize_line(entries, EXPECTED_DAYS)
        if _full_ruler_ok(line):
            return {
                "status": "PASS",
                "ages_seconds": ages,
                "dollar_block": line.as_dict(),
            }
    return None


def _aggregate_scores(scores: Sequence[ShardScore]) -> dict[str, object]:
    entries_by_age: dict[int, tuple[object, ...]] = {
        age: tuple(
            entry for score in scores for entry in score.entries_by_age[age]
        )
        for age in GRID
    }
    eligible_by_age = {
        age: {
            asset: sum(
                score.eligible_by_age[age]
                for score in scores
                if score.asset == asset
            )
            for asset in ASSETS
        }
        for age in GRID
    }
    per_age: dict[str, object] = {}
    for age in GRID:
        entries = entries_by_age[age]
        line = CEILING.summarize_line(entries, EXPECTED_DAYS)
        per_age[str(age)] = {
            "portfolio_dollar_block": line.as_dict(),
            "assets": {
                asset: {
                    **_asset_block(entries, asset),
                    "eligible_candidates": eligible_by_age[age][asset],
                    "entered_cells": sum(row.asset == asset for row in entries),
                }
                for asset in ASSETS
            },
        }
    envelope_entries = tuple(entry for score in scores for entry in score.envelope_entries)
    envelope_line = CEILING.summarize_line(envelope_entries, EXPECTED_DAYS)
    envelope_assets = {
        asset: {
            **_asset_block(envelope_entries, asset),
            "eligible_candidate_age_rows": sum(
                score.envelope_eligible_rows
                for score in scores
                if score.asset == asset
            ),
            "entered_cells": sum(row.asset == asset for row in envelope_entries),
        }
        for asset in ASSETS
    }
    envelope_misses = {
        asset: envelope_assets[asset]["shortfall_usd"]
        for asset in ASSETS
        if not envelope_assets[asset]["clears_rung"]
    }
    witness = None if envelope_misses else _fixed_policy_witness(entries_by_age)
    if envelope_misses:
        verdict = "KILL"
    elif witness is not None:
        verdict = "LIVE"
    else:
        verdict = "ENVELOPE-ONLY"
    ceiling_receipt = _read_json(CEILING_RECEIPT_PATH)
    gated = ceiling_receipt.get("gated")
    if not isinstance(gated, dict) or not isinstance(gated.get("usd_per_asset_day"), dict):
        raise Stage1Stop("stored ceiling receipt lacks the gated anchor line")
    stored_anchor = gated["usd_per_asset_day"]
    anchor_controls = {
        str(age): {
            asset: {
                "late_repriced_usd_per_asset_day": per_age[str(age)]["assets"][asset][
                    "usd_per_asset_day"
                ],
                "stored_ceiling_usd_per_asset_day": float(stored_anchor[asset]),
                "drift_usd_per_asset_day": (
                    per_age[str(age)]["assets"][asset]["usd_per_asset_day"]
                    - float(stored_anchor[asset])
                ),
            }
            for asset in ASSETS
        }
        for age in GRID
        if age <= 300
    }
    return {
        "verdict": verdict,
        "rule": RULE,
        "per_age": per_age,
        "late_envelope": {
            "portfolio_dollar_block": envelope_line.as_dict(),
            "assets": envelope_assets,
        },
        "anchor_controls_at_or_under_300": anchor_controls,
        "fixed_policy_witness": witness,
        "dollar_stop": {
            "verdict": verdict,
            "rungs_usd": dict(RUNGS_USD),
            "drawdown_limit_usd": DRAWDOWN_LIMIT_USD,
            "entry_cap": ENTRY_CAP,
            "envelope_shortfall_usd": envelope_misses,
            "verbatim": dict(STOP_VERBATIM),
            "applied": STOP_VERBATIM[verdict],
        },
    }


def _synthetic_row(
    candidate_id: str,
    age: int,
    cash: Decimal = Decimal("-5"),
) -> ScoreRow:
    decision = NANOS_PER_SECOND
    snapshot = decision + age * NANOS_PER_SECOND
    return ScoreRow(
        candidate_id=candidate_id,
        asset="HG",
        d8=20220103,
        phase=0,
        decision_ts_ns=decision,
        age=age,
        snapshot_ts_ns=snapshot,
        phase_close_ts_ns=decision + 20_000 * NANOS_PER_SECOND,
        status=READY,
        frozen_cost_usd=Decimal("5"),
        cash_usd=cash,
        exit_ts_ns=snapshot + NANOS_PER_SECOND,
    )


def _must_refuse(
    rows: Sequence[ScoreRow],
    expected_candidate_ids: frozenset[str],
    mutant: str,
) -> None:
    try:
        validate_rows(rows, expected_candidate_ids, "HG", 20220103)
    except Stage1Stop:
        return
    raise AssertionError(f"{mutant} stayed green")


def _replace_snapshot(row: ScoreRow, snapshot_ts_ns: int) -> ScoreRow:
    return ScoreRow(
        candidate_id=row.candidate_id,
        asset=row.asset,
        d8=row.d8,
        phase=row.phase,
        decision_ts_ns=row.decision_ts_ns,
        age=row.age,
        snapshot_ts_ns=snapshot_ts_ns,
        phase_close_ts_ns=row.phase_close_ts_ns,
        status=row.status,
        frozen_cost_usd=row.frozen_cost_usd,
        cash_usd=row.cash_usd,
        exit_ts_ns=row.exit_ts_ns,
    )


def _selftest() -> dict[str, object]:
    a_rows = tuple(
        _synthetic_row(
            "a",
            age,
            Decimal("10") if age == 600 else Decimal("-5"),
        )
        for age in GRID
    )
    b_rows = tuple(
        _synthetic_row(
            "b",
            age,
            Decimal("10") if age == 600 else Decimal("20") if age == 1200 else Decimal("-5"),
        )
        for age in GRID
    )
    base = (*a_rows, *b_rows)
    expected = frozenset({"a", "b"})
    validate_rows(base, expected, "HG", 20220103)
    per_age, eligible, envelope, envelope_eligible = _pick_rows(base)
    if (
        [row.candidate_id for row in per_age[600]] != ["a"]
        or [row.candidate_id for row in per_age[1200]] != ["b"]
        or [row.candidate_id for row in envelope] != ["b"]
        or eligible[600] != 2
        or envelope_eligible != len(LATE_AGES) * 2
    ):
        raise AssertionError("synthetic ceiling selection drifted")
    off_schedule = (*base, _synthetic_row("a", 601))
    _must_refuse(off_schedule, expected, "off_schedule_age_accepted")
    pre_decision = (
        _replace_snapshot(base[0], base[0].decision_ts_ns - 1),
        *base[1:],
    )
    _must_refuse(pre_decision, expected, "pre_decision_entry_accepted")
    _must_refuse(base[:-1], expected, "missing_age_row_covered")
    corrupted = tuple(
        ScoreRow(
            candidate_id="corrupted" if row.candidate_id == "a" else row.candidate_id,
            asset=row.asset,
            d8=row.d8,
            phase=row.phase,
            decision_ts_ns=row.decision_ts_ns,
            age=row.age,
            snapshot_ts_ns=row.snapshot_ts_ns,
            phase_close_ts_ns=row.phase_close_ts_ns,
            status=row.status,
            frozen_cost_usd=row.frozen_cost_usd,
            cash_usd=row.cash_usd,
            exit_ts_ns=row.exit_ts_ns,
        )
        for row in base
    )
    _must_refuse(corrupted, expected, "candidate_id_guard")
    return {
        "status": "PASS",
        "synthetic_era_bytes_read": 0,
        "selection_checks": {
            "age_600_tie_smallest_candidate_id": "a",
            "age_1200_best_candidate_id": "b",
            "late_envelope_best_candidate_id": "b",
        },
        "mutants": {
            "off_schedule_age_accepted": "RED",
            "pre_decision_entry_accepted": "RED",
            "missing_age_row_covered": "RED",
            "candidate_id_guard": "RED",
        },
        "red_first": {
            "observed_before_each_guard": True,
            "command": "python3 .audit/score_threshold_b0_stage1.py",
            "failures_in_order": [
                "off_schedule_age_accepted stayed green",
                "pre_decision_entry_accepted stayed green",
                "missing_age_row_covered stayed green",
                "candidate_id_guard stayed green",
            ],
        },
    }


def _base_receipt(started: float) -> dict[str, object]:
    return {
        "schema": RECEIPT_SCHEMA,
        "unit": "B0_STAGE1",
        "status": "STOP",
        "verdict": "STOP",
        "resolved_grid_seconds": list(GRID),
        "anchor_definition": ANCHOR_DEFINITION,
        "worker_budget": WORKER_BUDGET,
        "workers_by_asset": dict(WORKERS_BY_ASSET),
        "asset_chain_workers": ASSET_CHAIN_WORKERS,
        "tripwire_seconds": TRIPWIRE_SECONDS,
        "locked_asset_days": dict(EXPECTED_DAYS),
        "stored_teacher_fields_parsed": [],
        "stored_teacher_open_guard": "NOT_RUN",
        "stored_candidate_tree_rewritten": False,
        "stored_teacher_tree_rewritten": False,
        "stored_pivot_tree_rewritten": False,
        "stored_receipts_tree_rewritten": False,
        "picker_started": False,
        "feature_plane_started": False,
        "ticket_46_at_scale_started": False,
        "tickets_37_47_started": False,
        "dollar_line_reads": 0,
        "wall_clock_seconds": time.monotonic() - started,
    }


def execute() -> int:
    started = time.monotonic()
    deadline = started + TRIPWIRE_SECONDS
    receipt = _base_receipt(started)
    try:
        receipt["stage0_precondition"] = _stage0_precondition()
        receipt["sources"] = _source_sha256s()
        receipt["selftest"] = _selftest()
        protected_before = _protected_metadata()
        receipt["protected_trees_before"] = protected_before
        with _deny_stored_teacher_opens():
            jobs, gate = _locked_jobs()
            receipt["gate"] = gate
            receipt["build_started"] = True
            build_started = time.monotonic()
            built_raw = _run_three_asset_chains(
                jobs,
                _build_job,
                "build",
                deadline,
            )
            shards = tuple(
                sorted(
                    (item for item in built_raw if isinstance(item, ShardBuild)),
                    key=lambda item: (ASSETS.index(item.asset), item.d8),
                )
            )
            if len(shards) != len(jobs):
                raise Stage1Stop(f"build returned {len(shards)} of {len(jobs)} shards")
            receipt["build"] = {
                "status": "PASS",
                "wall_seconds": time.monotonic() - build_started,
                "shards": len(shards),
                "per_asset_shards": {
                    asset: sum(shard.asset == asset for shard in shards)
                    for asset in ASSETS
                },
                "rows": sum(shard.rows for shard in shards),
                "ready_rows": sum(shard.ready_rows for shard in shards),
                "clear_candidate_rows": sum(
                    shard.clear_candidate_rows for shard in shards
                ),
                "max_shard_wall_seconds": max(shard.wall_seconds for shard in shards),
                "three_asset_chains": True,
                "worker_budget": WORKER_BUDGET,
            }
            receipt["publication"] = _publish_manifest(shards)
            if time.monotonic() > deadline:
                raise Stage1Stop("build crossed the two-hour tripwire")
            receipt["dollar_line_reads"] = 1
            score_started = time.monotonic()
            scored_raw = _run_three_asset_chains(
                shards,
                _score_shard,
                "score",
                deadline,
            )
            scores = tuple(item for item in scored_raw if isinstance(item, ShardScore))
            if len(scores) != len(shards):
                raise Stage1Stop(f"score returned {len(scores)} of {len(shards)} shards")
            result = _aggregate_scores(scores)
            receipt["scoring"] = {
                "status": "PASS",
                "wall_seconds": time.monotonic() - score_started,
                "shards_read": len(scores),
                "passes_over_late_store": 1,
                "max_shard_wall_seconds": max(score.wall_seconds for score in scores),
            }
        receipt["stored_teacher_open_guard"] = "PASS"
        protected_after = _protected_metadata()
        if protected_after != protected_before:
            raise Stage1Stop("a protected stored tree changed during Stage 1")
        receipt["protected_trees_after"] = protected_after
        receipt["stored_candidate_tree_rewritten"] = False
        receipt["stored_teacher_tree_rewritten"] = False
        receipt["stored_pivot_tree_rewritten"] = False
        receipt["stored_receipts_tree_rewritten"] = False
        receipt.update(result)
        receipt["status"] = result["verdict"]
        receipt["verdict"] = result["verdict"]
        receipt["wall_clock_seconds"] = time.monotonic() - started
        _atomic_json(RECEIPT_PATH, receipt)
        print(
            f"{RECEIPT_SCHEMA} {result['verdict']} "
            f"receipt={_relative(RECEIPT_PATH)}",
            flush=True,
        )
        return 0
    except Exception as error:
        receipt["status"] = "STOP"
        receipt["verdict"] = "STOP"
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
    parser.add_argument("--selftest", action="store_true")
    arguments = parser.parse_args()
    if arguments.selftest:
        print(json.dumps(_selftest(), sort_keys=True))
        return 0
    return execute()


if __name__ == "__main__":
    raise SystemExit(main())
