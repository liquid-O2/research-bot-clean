#!/usr/bin/env python3
"""Score the frozen B1 observable-record picker on the late store."""

from __future__ import annotations

import argparse
import builtins
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import importlib.util
import itertools
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Callable, Iterator, Mapping, Sequence, TypeVar
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
RECEIPT_PATH = ROOT / ".audit/threshold-b1-picker.json"
B0_RECEIPT_PATH = ROOT / ".audit/threshold-b0-stage1.json"
B0_JUDGE_PATH = ROOT / ".audit/briefs/threshold-b0-stage1-judge-out.md"
COVERING_PATH = ROOT / ".audit/briefs/threshold-covering-after-b0-fable-out.md"
B1_BRIEF_PATH = ROOT / ".audit/briefs/threshold-b1-picker.md"
LATE_ROOT = ROOT / "artifacts/cache/port/entry_v2/g1/late"
MANIFEST_PATH = LATE_ROOT / "manifest.tsv"
CANDIDATE_ROOT = ROOT / "artifacts/cache/port/entry_v2/g1/candidates"
TEACHER_ROOT = ROOT / "artifacts/cache/port/entry_v2/g1/teacher"
PIVOT_ROOT = ROOT / "artifacts/cache/port/entry_v2/g1/pivot"
SOURCE_RECEIPTS_ROOT = ROOT / "artifacts/cache/port/entry_v2/g1/receipts"
CEILING_PATH = ROOT / ".audit/score_threshold_2022_2024_ceiling.py"
READ_PATH = ROOT / ".audit/score_threshold_2022_2024_read.py"


def _load_ceiling_module() -> object:
    spec = importlib.util.spec_from_file_location("threshold_b1_ceiling", CEILING_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load ceiling ruler from {CEILING_PATH}")
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
FULL_GRID = (
    0,
    30,
    60,
    90,
    120,
    180,
    240,
    290,
    300,
    600,
    1200,
    2400,
    3600,
    5400,
    7200,
    10800,
)
LATE_AGES = (600, 1200, 2400, 3600, 5400, 7200, 10800)
LINE_NAMES = (
    "record_top1_all",
    "record_top1_pos",
    "sideoracle_record",
    "recordside_price",
    "cellbest_control",
)
PRIMARY_LINES = ("record_top1_all", "record_top1_pos")
DECOMPOSITION_LINES = ("sideoracle_record", "recordside_price")
MUTANTS = (
    "future_mid_in_record",
    "nonready_entered",
    "oracle_leak_primary",
    "control_mismatch_accepted",
)
MUTANT = os.environ.get("QRE2_B1_MUTANT", "")
EXPECTED_DAYS = {"HG": 197, "NKD": 194, "SI": 191}
EXPECTED_SHARDS = 582
EXPECTED_ROWS = 2_923_344
EXPECTED_READY_ROWS = 2_768_741
EXPECTED_CLEAR_CANDIDATES = 182_709
WORKERS_BY_ASSET = {"HG": 5, "NKD": 4, "SI": 4}
WORKER_BUDGET = sum(WORKERS_BY_ASSET.values())
ASSET_CHAIN_WORKERS = len(ASSETS)
TRIPWIRE_SECONDS = 3600.0
NANOS_PER_SECOND = 1_000_000_000
WINDOW_START_D8 = 20220309
WINDOW_END_D8_EXCLUSIVE = 20250101
SCHEMA = "QRE2THRESHOLDB1PICKER1"
LATE_SCHEMA = "QRE2G1LATETEACH1"
MANIFEST_SCHEMA = "QRE2G1LATEMANIFEST1"
ANCHOR_DEFINITION = "ceil_second(decision_ts_ns)+age_offset_sec*1000000000"
READY = "READY"
LATE_STATUSES = frozenset(
    {"READY", "PHASE_CLOSED", "NO_SNAPSHOT_BBO", "NO_CERTIFIABLE_SUFFIX"}
)
LATE_COLUMNS = (
    "candidate_id",
    "asset",
    "d8",
    "side",
    "phase",
    "decision_ts_ns",
    "age_offset_sec",
    "snapshot_ts_ns",
    "phase_close_ts_ns",
    "entry_bid_px",
    "entry_ask_px",
    "entry_mid2",
    "frozen_cost_usd",
    "status",
    "cert_close_usd",
    "exit_ts_ns",
)
MANIFEST_COLUMNS = (
    "asset",
    "d8",
    "path",
    "sha256",
    "rows",
    "ready_rows",
    "candidate_rows",
    "clear_candidate_rows",
    "candidate_ids_sha256",
    "candidate_path",
    "candidate_sha256",
    "candidate_receipt",
    "event_path",
    "event_sha256",
)
SOURCE_FILES = (
    Path(__file__).resolve(),
    COVERING_PATH,
    B1_BRIEF_PATH,
    B0_RECEIPT_PATH,
    B0_JUDGE_PATH,
    ROOT / ".audit/score_threshold_b0_stage1.py",
    ROOT / ".audit/score_threshold_side_split.py",
    CEILING_PATH,
    READ_PATH,
    ROOT / ".audit/score_h5_top2.py",
)
PROTECTED_TREES = {
    "late": LATE_ROOT,
    "candidates": CANDIDATE_ROOT,
    "teacher": TEACHER_ROOT,
    "pivot": PIVOT_ROOT,
    "receipts": SOURCE_RECEIPTS_ROOT,
}
LINE_RULES = {
    "record_top1_all": (
        "Per gated cell, among READY age-A rows, enter the candidate with maximal "
        "r(X, A), ties smallest candidate_id, unconditionally. Cash is the entered "
        "row's cert_close_usd. The pick is blind to every cash column."
    ),
    "record_top1_pos": (
        "Use the record_top1_all pick and enter only when maximal r(X, A) is "
        "strictly positive. Cells failing the clause remain in the denominator "
        "at zero cash."
    ),
    "sideoracle_record": (
        "Restrict READY age-A rows to the stored side of the cell's age-A cell-best "
        "row, then enter the maximal-r candidate, ties smallest candidate_id. This "
        "decomposition cannot promote or witness."
    ),
    "recordside_price": (
        "Restrict READY age-A rows to the stored side of the cell's maximal-r "
        "candidate, then enter the maximal-cert_close_usd row, ties smallest "
        "candidate_id. This decomposition cannot promote or witness."
    ),
    "cellbest_control": (
        "Recompute B0's positive-cash age-A cell-best ceiling line. Every per-age "
        "portfolio dollar block must be byte-equal to the B0 receipt."
    ),
}
STOP_VERBATIM = {
    "STOP": (
        "**STOP, infrastructure.** The selftest fails, any mutant is not red-first "
        "or survives, `cellbest_control` mismatches the B0 receipt at any age, the "
        "manifest or any shard sha mismatches, denominators drift, any stored tree "
        "is touched, `dollar_line_reads` exceeds 1, or wall clock passes 3600 s. "
        "Report and wait. No dollar conclusion is drawn from a stopped run."
    ),
    "KILL": (
        "**KILL.** For some asset, both primary variants miss the full dollar block "
        "at every qualifying age, or no single variant carries all three assets. "
        "The frozen observable-record family closes at late ages on era labels, by "
        "receipt. A miss on the pre-stated bar is a KILL, not a near-miss, including "
        "a rung cleared with MDD above 1000. The per-age curves, the decomposition "
        "lines, and `side_agreement` hand the gap's shape to the next covering, "
        "which decides fitted-or-dead against those numbers. Nothing is auto-funded: "
        "no fitted picker, no training-scale relabel, no third read, no new variant."
    ),
    "LIVE": (
        "**LIVE.** One pre-named variant, the same for all three assets, posts the "
        "full dollar block at some qualifying age per asset, caps and overlap "
        "holding, MDD at most 1000, on the locked denominators. A causal entry rule "
        "on the stored-teacher exit law pays every rung on era labels. Teacher-cash "
        "cannot promote, so nothing ships from a LIVE. The successor questions are "
        "the exit leg, whose law is stored hindsight, and validation scale, "
        "authorized by the next covering, which also owns the training-scale "
        "relabel priced against this receipt. Nothing else is funded."
    ),
}


class B1Stop(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ManifestShard:
    asset: str
    d8: int
    path: Path
    sha256: str
    rows: int
    ready_rows: int
    candidate_rows: int
    clear_candidate_rows: int
    candidate_ids_sha256: str
    candidate_path: str
    candidate_sha256: str
    candidate_receipt: str
    event_path: str
    event_sha256: str


@dataclass(frozen=True, slots=True)
class VerifiedShard:
    shard: ManifestShard
    bytes: int
    wall_seconds: float

    @property
    def asset(self) -> str:
        return self.shard.asset

    @property
    def d8(self) -> int:
        return self.shard.d8


@dataclass(frozen=True, slots=True)
class BaseObservation:
    candidate_id: str
    asset: str
    d8: int
    side: int
    phase: int
    decision_ts_ns: int
    snapshot_ts_ns: int
    phase_close_ts_ns: int
    entry_mid2: int


@dataclass(frozen=True, slots=True)
class StoredAgeRow:
    candidate_id: str
    asset: str
    d8: int
    side: int
    phase: int
    decision_ts_ns: int
    age: int
    snapshot_ts_ns: int
    phase_close_ts_ns: int
    entry_mid2: int | None
    frozen_cost_usd: Decimal | None
    status: str
    cash_usd: Decimal | None
    exit_ts_ns: int | None


@dataclass(frozen=True, slots=True)
class CandidateAtAge:
    candidate_id: str
    asset: str
    d8: int
    side: int
    phase: int
    decision_ts_ns: int
    age: int
    snapshot_ts_ns: int
    phase_close_ts_ns: int
    record_units: int
    frozen_cost_usd: Decimal
    status: str
    cash_usd: Decimal
    exit_ts_ns: int


@dataclass(frozen=True, slots=True)
class CellScore:
    selected: Mapping[str, CandidateAtAge | None]
    eligible_candidates: Mapping[str, int]
    side_agreement_numerator: int
    side_agreement_denominator: int


@dataclass(frozen=True, slots=True)
class ShardScore:
    asset: str
    d8: int
    entries_by_age: Mapping[int, Mapping[str, tuple[object, ...]]]
    eligible_by_age: Mapping[int, Mapping[str, int]]
    agreement_by_age: Mapping[int, tuple[int, int]]
    rows_read: int
    ready_rows: int
    age0_cert_close_values_used: int
    wall_seconds: float


T = TypeVar("T")
R = TypeVar("R")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _object_sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    try:
        temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise B1Stop(f"cannot read JSON object {path}") from error
    if not isinstance(value, dict):
        raise B1Stop(f"{path} is not a JSON object")
    return value


def _integer(text: str, name: str) -> int:
    if not text or any(character in text for character in ".eE"):
        raise B1Stop(f"{name} is not exact integer text: {text!r}")
    try:
        return int(text)
    except ValueError as error:
        raise B1Stop(f"{name} is not exact integer text: {text!r}") from error


def _decimal(text: str, name: str) -> Decimal:
    try:
        value = Decimal(text)
    except InvalidOperation as error:
        raise B1Stop(f"{name} is not decimal text: {text!r}") from error
    if not value.is_finite():
        raise B1Stop(f"{name} must be finite: {text!r}")
    return value


def _ceil_second(timestamp_ns: int) -> int:
    return ((timestamp_ns + NANOS_PER_SECOND - 1) // NANOS_PER_SECOND) * NANOS_PER_SECOND


def _source_sha256s() -> dict[str, str]:
    missing = [str(path) for path in SOURCE_FILES if not path.is_file()]
    if missing:
        raise B1Stop(f"B1 sources are absent: {missing}")
    return {_relative(path): _sha256_file(path) for path in SOURCE_FILES}


def _tree_metadata(path: Path) -> dict[str, object]:
    if not path.is_dir():
        raise B1Stop(f"protected tree is absent: {path}")
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
        "files": len(entries),
        "bytes": sum(entry[1] for entry in entries),
        "metadata_sha256": _object_sha256(entries),
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
            raise B1Stop(f"stored teacher open refused: {file}")
        return original_builtin_open(file, *args, **kwargs)

    def guarded_path_open(path: Path, *args: object, **kwargs: object) -> object:
        if _is_under(path, TEACHER_ROOT):
            raise B1Stop(f"stored teacher open refused: {path}")
        return original_path_open(path, *args, **kwargs)

    with mock.patch.object(builtins, "open", guarded_builtin_open), mock.patch.object(
        Path, "open", guarded_path_open
    ):
        yield


def _assert_contract() -> None:
    if ASSETS != ("HG", "NKD", "SI"):
        raise B1Stop(f"asset order drifted: {ASSETS!r}")
    if PHASES != (0, 1, 2):
        raise B1Stop(f"phase set drifted: {PHASES!r}")
    if LINE_NAMES != (
        "record_top1_all",
        "record_top1_pos",
        "sideoracle_record",
        "recordside_price",
        "cellbest_control",
    ):
        raise B1Stop(f"line family drifted: {LINE_NAMES!r}")
    if LATE_AGES != (600, 1200, 2400, 3600, 5400, 7200, 10800):
        raise B1Stop(f"late ages drifted: {LATE_AGES!r}")
    if WORKERS_BY_ASSET != {"HG": 5, "NKD": 4, "SI": 4} or WORKER_BUDGET != 13:
        raise B1Stop(f"worker budget drifted: {WORKERS_BY_ASSET!r}")
    if MUTANT and MUTANT not in MUTANTS:
        raise B1Stop(f"unknown QRE2_B1_MUTANT {MUTANT!r}")


def _b0_precondition() -> tuple[dict[str, object], dict[str, object]]:
    b0 = _read_json(B0_RECEIPT_PATH)
    judge = B0_JUDGE_PATH.read_text()
    publication = b0.get("publication")
    scoring = b0.get("scoring")
    sources = b0.get("sources")
    per_age = b0.get("per_age")
    if not all(
        isinstance(value, dict)
        for value in (publication, scoring, sources, per_age)
    ):
        raise B1Stop("B0 receipt lacks publication, scoring, sources, or per_age")
    assert isinstance(publication, dict)
    assert isinstance(scoring, dict)
    assert isinstance(sources, dict)
    assert isinstance(per_age, dict)
    current_b0_scorer = _sha256_file(ROOT / ".audit/score_threshold_b0_stage1.py")
    current_ceiling = _sha256_file(CEILING_PATH)
    current_read = _sha256_file(READ_PATH)
    if (
        b0.get("schema") != "QRE2THRESHOLDB0STAGE11"
        or b0.get("status") != "LIVE"
        or b0.get("verdict") != "LIVE"
        or b0.get("picker_started") is not False
        or b0.get("locked_asset_days") != EXPECTED_DAYS
        or int(b0.get("dollar_line_reads", -1)) != 1
        or int(publication.get("shards", -1)) != EXPECTED_SHARDS
        or int(publication.get("rows", -1)) != EXPECTED_ROWS
        or int(publication.get("ready_rows", -1)) != EXPECTED_READY_ROWS
        or int(publication.get("clear_candidate_rows", -1))
        != EXPECTED_CLEAR_CANDIDATES
        or publication.get("path") != _relative(MANIFEST_PATH)
        or sources.get(".audit/score_threshold_b0_stage1.py") != current_b0_scorer
        or sources.get(".audit/score_threshold_2022_2024_ceiling.py")
        != current_ceiling
        or sources.get(".audit/score_threshold_2022_2024_read.py") != current_read
        or not judge.startswith("# B0 Stage 1 judge verdict. Fable.\n\n**LIVE.**")
        or set(per_age).intersection(map(str, LATE_AGES))
        != set(map(str, LATE_AGES))
    ):
        raise B1Stop("B0 LIVE precondition drifted")
    return b0, {
        "status": "PASS",
        "receipt": _relative(B0_RECEIPT_PATH),
        "receipt_sha256": _sha256_file(B0_RECEIPT_PATH),
        "judge": _relative(B0_JUDGE_PATH),
        "judge_sha256": _sha256_file(B0_JUDGE_PATH),
        "manifest_sha256": publication["sha256"],
        "locked_asset_days": dict(EXPECTED_DAYS),
    }


def _manifest_metadata(line: str, schema: str, path: Path) -> dict[str, str]:
    if not line.startswith(f"# {schema} "):
        raise B1Stop(f"{path} lacks the {schema} marker")
    tokens = line[2:].split()
    metadata = {
        key: value
        for token in tokens[1:]
        for key, separator, value in (token.partition("="),)
        if separator
    }
    if tokens[0] != schema:
        raise B1Stop(f"{path} marker schema drifted")
    return metadata


def _manifest_shards(b0: Mapping[str, object]) -> tuple[tuple[ManifestShard, ...], dict[str, object]]:
    publication = b0["publication"]
    if not isinstance(publication, dict):
        raise B1Stop("B0 publication is not an object")
    expected_sha = publication.get("sha256")
    if not isinstance(expected_sha, str) or not expected_sha:
        raise B1Stop("B0 publication lacks manifest sha256")
    actual_sha = _sha256_file(MANIFEST_PATH)
    if actual_sha != expected_sha:
        raise B1Stop(f"manifest sha mismatch: {actual_sha} != {expected_sha}")
    lines = MANIFEST_PATH.read_text(encoding="utf-8").splitlines()
    if len(lines) < 3 or tuple(lines[1].split("\t")) != MANIFEST_COLUMNS:
        raise B1Stop("late manifest header drifted")
    metadata = _manifest_metadata(lines[0], MANIFEST_SCHEMA, MANIFEST_PATH)
    if (
        _integer(metadata.get("start_d8", ""), "manifest.start_d8")
        != WINDOW_START_D8
        or _integer(
            metadata.get("end_d8_exclusive", ""),
            "manifest.end_d8_exclusive",
        )
        != WINDOW_END_D8_EXCLUSIVE
        or tuple(
            _integer(value, "manifest.resolved_grid_seconds")
            for value in metadata.get("resolved_grid_seconds", "").split(",")
        )
        != FULL_GRID
        or metadata.get("anchor") != ANCHOR_DEFINITION
    ):
        raise B1Stop("late manifest marker drifted")
    shards: list[ManifestShard] = []
    for line_number, line in enumerate(lines[2:], start=3):
        if not line:
            continue
        fields = tuple(line.split("\t"))
        if len(fields) != len(MANIFEST_COLUMNS):
            raise B1Stop(
                f"{MANIFEST_PATH}:{line_number} has {len(fields)} fields, "
                f"expected {len(MANIFEST_COLUMNS)}"
            )
        values = dict(zip(MANIFEST_COLUMNS, fields, strict=True))
        asset = values["asset"]
        d8 = _integer(values["d8"], "manifest.d8")
        relative_path = Path(values["path"])
        path = (ROOT / relative_path).resolve()
        expected_parent = (LATE_ROOT / asset).resolve()
        if (
            asset not in ASSETS
            or not WINDOW_START_D8 <= d8 < WINDOW_END_D8_EXCLUSIVE
            or d8 >= 20250101
            or path.parent != expected_parent
            or path.name != f"{d8}.tsv"
            or not path.is_file()
        ):
            raise B1Stop(f"manifest shard escapes the frozen store: {asset}/{d8}")
        shard = ManifestShard(
            asset=asset,
            d8=d8,
            path=path,
            sha256=values["sha256"],
            rows=_integer(values["rows"], "manifest.rows"),
            ready_rows=_integer(values["ready_rows"], "manifest.ready_rows"),
            candidate_rows=_integer(
                values["candidate_rows"], "manifest.candidate_rows"
            ),
            clear_candidate_rows=_integer(
                values["clear_candidate_rows"], "manifest.clear_candidate_rows"
            ),
            candidate_ids_sha256=values["candidate_ids_sha256"],
            candidate_path=values["candidate_path"],
            candidate_sha256=values["candidate_sha256"],
            candidate_receipt=values["candidate_receipt"],
            event_path=values["event_path"],
            event_sha256=values["event_sha256"],
        )
        if shard.rows != shard.clear_candidate_rows * len(FULL_GRID):
            raise B1Stop(f"manifest row multiple drifted: {asset}/{d8}")
        shards.append(shard)
    ordered = tuple(sorted(shards, key=lambda row: (ASSETS.index(row.asset), row.d8)))
    counts = {asset: sum(row.asset == asset for row in ordered) for asset in ASSETS}
    identities = {(row.asset, row.d8) for row in ordered}
    actual_files = {
        path.resolve() for path in LATE_ROOT.rglob("*") if path.is_file()
    }
    expected_files = {MANIFEST_PATH.resolve(), *(row.path for row in ordered)}
    if (
        len(ordered) != EXPECTED_SHARDS
        or len(identities) != len(ordered)
        or counts != EXPECTED_DAYS
        or sum(row.rows for row in ordered) != EXPECTED_ROWS
        or sum(row.ready_rows for row in ordered) != EXPECTED_READY_ROWS
        or sum(row.clear_candidate_rows for row in ordered)
        != EXPECTED_CLEAR_CANDIDATES
        or actual_files != expected_files
    ):
        raise B1Stop(
            f"manifest census drifted: shards={len(ordered)} counts={counts}"
        )
    return ordered, {
        "status": "PASS",
        "path": _relative(MANIFEST_PATH),
        "sha256": actual_sha,
        "schema": MANIFEST_SCHEMA,
        "shards": len(ordered),
        "rows": sum(row.rows for row in ordered),
        "ready_rows": sum(row.ready_rows for row in ordered),
        "clear_candidate_rows": sum(row.clear_candidate_rows for row in ordered),
        "asset_days": counts,
        "min_d8": min(row.d8 for row in ordered),
        "max_d8": max(row.d8 for row in ordered),
        "contains_2025": False,
    }


def _verify_shard_hash(shard: ManifestShard) -> VerifiedShard:
    started = time.monotonic()
    actual = _sha256_file(shard.path)
    if actual != shard.sha256:
        raise B1Stop(
            f"late shard sha mismatch for {shard.asset}/{shard.d8}: "
            f"{actual} != {shard.sha256}"
        )
    return VerifiedShard(
        shard=shard,
        bytes=shard.path.stat().st_size,
        wall_seconds=time.monotonic() - started,
    )


def _run_asset_chain(
    asset: str,
    items: Sequence[T],
    operation: Callable[[T], R],
    phase: str,
    deadline: float,
) -> tuple[R, ...]:
    executor = ThreadPoolExecutor(max_workers=WORKERS_BY_ASSET[asset])
    futures: dict[Future[R], T] = {}
    results: list[R] = []
    try:
        futures = {executor.submit(operation, item): item for item in items}
        for completed, future in enumerate(as_completed(futures), start=1):
            if time.monotonic() > deadline:
                raise B1Stop(f"{phase} crossed the 3600-second tripwire")
            results.append(future.result())
            if completed % 25 == 0 or completed == len(items):
                print(
                    f"B1_{phase.upper()} {asset} {completed}/{len(items)}",
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
    operation: Callable[[T], R],
    phase: str,
    deadline: float,
) -> tuple[R, ...]:
    by_asset = {
        asset: tuple(
            item for item in items if str(getattr(item, "asset", "")) == asset
        )
        for asset in ASSETS
    }
    results: dict[str, tuple[R, ...]] = {}
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


def _projection_from_hg(
    b0: Mapping[str, object],
    verified: Sequence[VerifiedShard],
) -> dict[str, object]:
    scoring = b0.get("scoring")
    if not isinstance(scoring, dict):
        raise B1Stop("B0 receipt lacks scoring timing")
    max_shard_wall = float(scoring.get("max_shard_wall_seconds", 0.0))
    if max_shard_wall <= 0.0:
        raise B1Stop("B0 max shard timing is invalid")
    hg_shards = sum(row.shard.asset == "HG" for row in verified)
    hg_waves = math.ceil(hg_shards / WORKERS_BY_ASSET["HG"])
    line_factor = 2.0
    projected_wall = hg_waves * max_shard_wall * line_factor
    if projected_wall >= TRIPWIRE_SECONDS:
        raise B1Stop(
            f"HG projection {projected_wall:.3f}s crosses the tripwire"
        )
    return {
        "status": "PASS",
        "method": (
            "ceil(HG shards / 5 workers) times B0 same-store maximum shard "
            "seconds times a 2x five-line allowance"
        ),
        "hg_shards": hg_shards,
        "hg_workers": WORKERS_BY_ASSET["HG"],
        "hg_waves": hg_waves,
        "b0_max_shard_wall_seconds": max_shard_wall,
        "line_factor": line_factor,
        "projected_wall_seconds": projected_wall,
        "tripwire_seconds": TRIPWIRE_SECONDS,
    }


def _parse_shard_marker(line: str, shard: ManifestShard) -> None:
    metadata = _manifest_metadata(line, LATE_SCHEMA, shard.path)
    if (
        _integer(metadata.get("start_d8", ""), "late.start_d8")
        != WINDOW_START_D8
        or _integer(
            metadata.get("end_d8_exclusive", ""),
            "late.end_d8_exclusive",
        )
        != WINDOW_END_D8_EXCLUSIVE
        or _integer(metadata.get("d8", ""), "late.d8") != shard.d8
        or tuple(
            _integer(value, "late.resolved_grid_seconds")
            for value in metadata.get("resolved_grid_seconds", "").split(",")
        )
        != FULL_GRID
        or metadata.get("anchor") != ANCHOR_DEFINITION
    ):
        raise B1Stop(f"late shard marker drifted: {shard.path}")


def _record_units(
    base: BaseObservation,
    current: StoredAgeRow,
) -> int:
    expected_snapshot = _ceil_second(base.decision_ts_ns) + (
        current.age * NANOS_PER_SECOND
    )
    if (
        MUTANT != "future_mid_in_record"
        and current.snapshot_ts_ns > expected_snapshot
    ):
        raise B1Stop(
            f"record mid is later than age {current.age}: "
            f"{current.candidate_id}"
        )
    if current.entry_mid2 is None:
        raise B1Stop(f"record row lacks entry_mid2: {current.candidate_id}")
    return base.side * (current.entry_mid2 - base.entry_mid2)


def _ensure_ready_entry(row: StoredAgeRow) -> None:
    if MUTANT != "nonready_entered" and row.status != READY:
        raise B1Stop(f"entry row is not READY: {row.candidate_id}")


def _candidate_at_age(
    base: BaseObservation,
    current: StoredAgeRow,
) -> CandidateAtAge:
    _ensure_ready_entry(current)
    if (
        current.candidate_id != base.candidate_id
        or current.asset != base.asset
        or current.d8 != base.d8
        or current.side != base.side
        or current.phase != base.phase
        or current.decision_ts_ns != base.decision_ts_ns
        or current.phase_close_ts_ns != base.phase_close_ts_ns
        or current.frozen_cost_usd is None
        or current.cash_usd is None
        or current.exit_ts_ns is None
    ):
        raise B1Stop(f"late record identity drifted: {current.candidate_id}")
    return CandidateAtAge(
        candidate_id=current.candidate_id,
        asset=current.asset,
        d8=current.d8,
        side=current.side,
        phase=current.phase,
        decision_ts_ns=current.snapshot_ts_ns,
        age=current.age,
        snapshot_ts_ns=current.snapshot_ts_ns,
        phase_close_ts_ns=current.phase_close_ts_ns,
        record_units=_record_units(base, current),
        frozen_cost_usd=current.frozen_cost_usd,
        status=current.status,
        cash_usd=current.cash_usd,
        exit_ts_ns=current.exit_ts_ns,
    )


def _pick_record(rows: Sequence[CandidateAtAge]) -> CandidateAtAge | None:
    if not rows:
        return None
    return min(rows, key=lambda row: (-row.record_units, row.candidate_id))


def _validate_primary_pick(
    picked: CandidateAtAge | None,
    rows: Sequence[CandidateAtAge],
) -> None:
    if MUTANT == "oracle_leak_primary":
        return
    expected = _pick_record(rows)
    picked_id = None if picked is None else picked.candidate_id
    expected_id = None if expected is None else expected.candidate_id
    if picked_id != expected_id:
        raise B1Stop(
            f"primary pick consulted a non-observable field: "
            f"{picked_id!r} != {expected_id!r}"
        )


def _pick_primary(rows: Sequence[CandidateAtAge]) -> CandidateAtAge | None:
    picked = _pick_record(rows)
    _validate_primary_pick(picked, rows)
    return picked


def _pick_cash(rows: Sequence[CandidateAtAge]) -> CandidateAtAge | None:
    if not rows:
        return None
    return min(rows, key=lambda row: (-row.cash_usd, row.candidate_id))


def _score_cell(rows: Sequence[CandidateAtAge]) -> CellScore:
    if not rows:
        return CellScore(
            selected={name: None for name in LINE_NAMES},
            eligible_candidates={name: 0 for name in LINE_NAMES},
            side_agreement_numerator=0,
            side_agreement_denominator=0,
        )
    primary = _pick_primary(rows)
    cellbest = _pick_cash(rows)
    if primary is None or cellbest is None:
        raise B1Stop("nonempty cell produced no primary or cell-best row")
    oracle_side_pool = tuple(row for row in rows if row.side == cellbest.side)
    record_side_pool = tuple(row for row in rows if row.side == primary.side)
    sideoracle = _pick_record(oracle_side_pool)
    recordside = _pick_cash(record_side_pool)
    control = cellbest if cellbest.cash_usd > 0 else None
    selected = {
        "record_top1_all": primary,
        "record_top1_pos": primary if primary.record_units > 0 else None,
        "sideoracle_record": sideoracle,
        "recordside_price": recordside,
        "cellbest_control": control,
    }
    eligible = {
        "record_top1_all": len(rows),
        "record_top1_pos": len(rows),
        "sideoracle_record": len(oracle_side_pool),
        "recordside_price": len(record_side_pool),
        "cellbest_control": len(rows),
    }
    return CellScore(
        selected=selected,
        eligible_candidates=eligible,
        side_agreement_numerator=int(primary.side == cellbest.side),
        side_agreement_denominator=1,
    )


def _selected_name(row: CandidateAtAge, shard: ManifestShard) -> object:
    if row.status != READY:
        raise B1Stop(f"non-READY row reached entry conversion: {row.candidate_id}")
    return CEILING.SelectedName(
        candidate_id=row.candidate_id,
        asset=row.asset,
        d8=row.d8,
        phase=row.phase,
        decision_ts_ns=row.decision_ts_ns,
        frozen_cost_usd=float(row.frozen_cost_usd),
        cash_usd=float(row.cash_usd),
        exit_ts_ns=row.exit_ts_ns,
        ready=True,
        source_candidates=shard.candidate_path,
        source_teacher=_relative(shard.path),
        candidates_output_sha256=shard.candidate_sha256,
        teacher_output_sha256=shard.sha256,
    )


def _load_shard_rows(
    shard: ManifestShard,
) -> tuple[
    dict[str, BaseObservation],
    dict[int, tuple[StoredAgeRow, ...]],
    int,
    int,
]:
    bases: dict[str, BaseObservation] = {}
    late_rows: dict[int, list[StoredAgeRow]] = {age: [] for age in LATE_AGES}
    ages_by_candidate: dict[str, list[int]] = {}
    rows_read = 0
    ready_rows = 0
    with shard.path.open("r", encoding="utf-8", newline="") as source:
        marker = source.readline().rstrip("\r\n")
        header = tuple(source.readline().rstrip("\r\n").split("\t"))
        _parse_shard_marker(marker, shard)
        if header != LATE_COLUMNS:
            raise B1Stop(f"late shard columns drifted: {shard.path}")
        for line_number, raw_line in enumerate(source, start=3):
            line = raw_line.rstrip("\r\n")
            if not line:
                continue
            fields = tuple(line.split("\t"))
            if len(fields) != len(LATE_COLUMNS):
                raise B1Stop(
                    f"{shard.path}:{line_number} has {len(fields)} fields, "
                    f"expected {len(LATE_COLUMNS)}"
                )
            (
                candidate_id,
                asset,
                d8_text,
                side_text,
                phase_text,
                decision_text,
                age_text,
                snapshot_text,
                close_text,
                bid_text,
                ask_text,
                mid_text,
                cost_text,
                status,
                cash_text,
                exit_text,
            ) = fields
            d8 = _integer(d8_text, "late.d8")
            side = _integer(side_text, "late.side")
            phase = _integer(phase_text, "late.phase")
            decision = _integer(decision_text, "late.decision_ts_ns")
            age = _integer(age_text, "late.age_offset_sec")
            snapshot = _integer(snapshot_text, "late.snapshot_ts_ns")
            close = _integer(close_text, "late.phase_close_ts_ns")
            expected_snapshot = _ceil_second(decision) + age * NANOS_PER_SECOND
            if (
                not candidate_id
                or asset != shard.asset
                or d8 != shard.d8
                or side not in {-1, 1}
                or phase not in PHASES
                or age not in FULL_GRID
                or snapshot != expected_snapshot
                or close <= decision
                or status not in LATE_STATUSES
            ):
                raise B1Stop(
                    f"late row identity drifted at {shard.path}:{line_number}"
                )
            payload = (bid_text, ask_text, mid_text, cost_text, cash_text, exit_text)
            if status == READY:
                if any(value == "" for value in payload):
                    raise B1Stop(
                        f"READY late row lacks payload at {shard.path}:{line_number}"
                    )
                ready_rows += 1
            elif any(value != "" for value in payload):
                raise B1Stop(
                    f"{status} late row carries payload at "
                    f"{shard.path}:{line_number}"
                )
            rows_read += 1
            ages_by_candidate.setdefault(candidate_id, []).append(age)
            if age == 0:
                if status != READY:
                    continue
                bid = _integer(bid_text, "late.entry_bid_px")
                ask = _integer(ask_text, "late.entry_ask_px")
                mid = _integer(mid_text, "late.entry_mid2")
                if bid + ask != mid or ask <= bid:
                    raise B1Stop(f"age-0 BBO drifted: {candidate_id}")
                if candidate_id in bases:
                    raise B1Stop(f"age-0 row repeats: {candidate_id}")
                bases[candidate_id] = BaseObservation(
                    candidate_id,
                    asset,
                    d8,
                    side,
                    phase,
                    decision,
                    snapshot,
                    close,
                    mid,
                )
                continue
            if age not in LATE_AGES:
                continue
            if status == READY:
                bid = _integer(bid_text, "late.entry_bid_px")
                ask = _integer(ask_text, "late.entry_ask_px")
                mid = _integer(mid_text, "late.entry_mid2")
                cost = _decimal(cost_text, "late.frozen_cost_usd")
                cash = _decimal(cash_text, "late.cert_close_usd")
                exit_ts = _integer(exit_text, "late.exit_ts_ns")
                if (
                    bid + ask != mid
                    or ask <= bid
                    or cost < 0
                    or not snapshot <= exit_ts <= close
                ):
                    raise B1Stop(f"READY late payload drifted: {candidate_id}")
            else:
                mid = None
                cost = None
                cash = None
                exit_ts = None
            late_rows[age].append(
                StoredAgeRow(
                    candidate_id,
                    asset,
                    d8,
                    side,
                    phase,
                    decision,
                    age,
                    snapshot,
                    close,
                    mid,
                    cost,
                    status,
                    cash,
                    exit_ts,
                )
            )
    if rows_read != shard.rows or ready_rows != shard.ready_rows:
        raise B1Stop(
            f"late shard census drifted for {shard.asset}/{shard.d8}: "
            f"rows={rows_read}/{shard.rows} ready={ready_rows}/{shard.ready_rows}"
        )
    if (
        not set(bases).issubset(ages_by_candidate)
        or len(ages_by_candidate) != shard.clear_candidate_rows
        or any(tuple(ages) != FULL_GRID for ages in ages_by_candidate.values())
    ):
        raise B1Stop(f"late candidate grid drifted: {shard.path}")
    return (
        bases,
        {age: tuple(rows) for age, rows in late_rows.items()},
        rows_read,
        ready_rows,
    )


def _score_shard(verified: VerifiedShard) -> ShardScore:
    started = time.monotonic()
    shard = verified.shard
    bases, rows_by_age, rows_read, ready_rows = _load_shard_rows(shard)
    entries_by_age: dict[int, dict[str, tuple[object, ...]]] = {}
    eligible_by_age: dict[int, dict[str, int]] = {}
    agreement_by_age: dict[int, tuple[int, int]] = {}
    for age in LATE_AGES:
        by_phase: dict[int, list[CandidateAtAge]] = {phase: [] for phase in PHASES}
        for stored in rows_by_age[age]:
            if stored.status != READY:
                continue
            base = bases.get(stored.candidate_id)
            if base is None:
                raise B1Stop(f"record base is absent: {stored.candidate_id}")
            candidate = _candidate_at_age(base, stored)
            by_phase[candidate.phase].append(candidate)
        line_entries: dict[str, list[object]] = {name: [] for name in LINE_NAMES}
        eligible = {name: 0 for name in LINE_NAMES}
        agreement_numerator = 0
        agreement_denominator = 0
        for phase in PHASES:
            cell = _score_cell(tuple(by_phase[phase]))
            for name in LINE_NAMES:
                eligible[name] += cell.eligible_candidates[name]
                selected = cell.selected[name]
                if selected is not None:
                    line_entries[name].append(_selected_name(selected, shard))
            agreement_numerator += cell.side_agreement_numerator
            agreement_denominator += cell.side_agreement_denominator
        entries_by_age[age] = {
            name: tuple(line_entries[name]) for name in LINE_NAMES
        }
        eligible_by_age[age] = eligible
        agreement_by_age[age] = (
            agreement_numerator,
            agreement_denominator,
        )
    return ShardScore(
        asset=shard.asset,
        d8=shard.d8,
        entries_by_age=entries_by_age,
        eligible_by_age=eligible_by_age,
        agreement_by_age=agreement_by_age,
        rows_read=rows_read,
        ready_rows=ready_rows,
        age0_cert_close_values_used=0,
        wall_seconds=time.monotonic() - started,
    )


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


def _assert_control_match(actual: object, expected: object) -> None:
    if MUTANT == "control_mismatch_accepted":
        return
    if _canonical_bytes(actual) != _canonical_bytes(expected):
        raise B1Stop("cellbest_control differs from the B0 dollar block")


def _asset_full_ok(block: Mapping[str, object]) -> bool:
    return bool(
        int(block["trades"]) > 0
        and block["clears_rung"]
        and block["drawdown_ok"]
        and block["entry_cap_ok"]
        and int(block["overlap_violations"]) == 0
    )


def _full_line_ok(line: object) -> bool:
    return bool(
        line.trades > 0
        and line.clears_rungs
        and line.max_drawdown_usd < DRAWDOWN_LIMIT_USD
        and line.entry_cap_ok
        and line.overlap_violations == 0
    )


def _qualifying_ages(b0: Mapping[str, object]) -> dict[str, tuple[int, ...]]:
    per_age = b0["per_age"]
    if not isinstance(per_age, dict):
        raise B1Stop("B0 per_age is not an object")
    result: dict[str, tuple[int, ...]] = {}
    for asset in ASSETS:
        ages: list[int] = []
        for age in LATE_AGES:
            age_block = per_age.get(str(age))
            if not isinstance(age_block, dict):
                raise B1Stop(f"B0 lacks age {age}")
            assets = age_block.get("assets")
            if not isinstance(assets, dict) or not isinstance(assets.get(asset), dict):
                raise B1Stop(f"B0 lacks {asset} age {age} block")
            block = assets[asset]
            assert isinstance(block, dict)
            if (
                int(block.get("trades", 0)) > 0
                and block.get("clears_rung") is True
                and block.get("entry_cap_ok") is True
                and int(block.get("overlap_violations", -1)) == 0
                and block.get("drawdown_ok") is True
            ):
                ages.append(age)
        result[asset] = tuple(ages)
    return result


def _variant_witness(
    variant: str,
    entries: Mapping[int, Mapping[str, tuple[object, ...]]],
    per_age: Mapping[str, object],
    qualifying: Mapping[str, tuple[int, ...]],
) -> dict[str, object]:
    eligible: dict[str, tuple[int, ...]] = {}
    for asset in ASSETS:
        eligible[asset] = tuple(
            age
            for age in qualifying[asset]
            if _asset_full_ok(
                per_age[str(age)]["lines"][variant]["assets"][asset]
            )
        )
    if any(not ages for ages in eligible.values()):
        return {
            "status": "MISS",
            "variant": variant,
            "eligible_ages_seconds": {
                asset: list(ages) for asset, ages in eligible.items()
            },
        }
    for combination in itertools.product(*(eligible[asset] for asset in ASSETS)):
        ages = dict(zip(ASSETS, combination, strict=True))
        selected = tuple(
            row
            for asset in ASSETS
            for row in entries[ages[asset]][variant]
            if row.asset == asset
        )
        line = CEILING.summarize_line(selected, EXPECTED_DAYS)
        if _full_line_ok(line):
            return {
                "status": "PASS",
                "variant": variant,
                "ages_seconds": ages,
                "dollar_block": line.as_dict(),
                "eligible_ages_seconds": {
                    asset: list(values) for asset, values in eligible.items()
                },
            }
    return {
        "status": "MISS",
        "variant": variant,
        "eligible_ages_seconds": {
            asset: list(ages) for asset, ages in eligible.items()
        },
        "combination_blocker": "portfolio full dollar block",
    }


def _mixed_variant_witness(
    entries: Mapping[int, Mapping[str, tuple[object, ...]]],
    per_age: Mapping[str, object],
    qualifying: Mapping[str, tuple[int, ...]],
) -> dict[str, object]:
    for assignment in itertools.product(PRIMARY_LINES, repeat=len(ASSETS)):
        if len(set(assignment)) == 1:
            continue
        variants = dict(zip(ASSETS, assignment, strict=True))
        eligible = {
            asset: tuple(
                age
                for age in qualifying[asset]
                if _asset_full_ok(
                    per_age[str(age)]["lines"][variants[asset]]["assets"][asset]
                )
            )
            for asset in ASSETS
        }
        if any(not ages for ages in eligible.values()):
            continue
        for combination in itertools.product(*(eligible[asset] for asset in ASSETS)):
            ages = dict(zip(ASSETS, combination, strict=True))
            selected = tuple(
                row
                for asset in ASSETS
                for row in entries[ages[asset]][variants[asset]]
                if row.asset == asset
            )
            line = CEILING.summarize_line(selected, EXPECTED_DAYS)
            if _full_line_ok(line):
                return {
                    "found": True,
                    "ignored_for_live": True,
                    "variants_by_asset": variants,
                    "ages_seconds": ages,
                    "dollar_block": line.as_dict(),
                }
    return {"found": False, "ignored_for_live": True}


def _aggregate_scores(
    scores: Sequence[ShardScore],
    b0: Mapping[str, object],
) -> dict[str, object]:
    ordered = tuple(
        sorted(scores, key=lambda row: (ASSETS.index(row.asset), row.d8))
    )
    entries: dict[int, dict[str, tuple[object, ...]]] = {
        age: {
            name: tuple(
                entry
                for score in ordered
                for entry in score.entries_by_age[age][name]
            )
            for name in LINE_NAMES
        }
        for age in LATE_AGES
    }
    per_age: dict[str, object] = {}
    controls: dict[str, object] = {}
    b0_per_age = b0["per_age"]
    if not isinstance(b0_per_age, dict):
        raise B1Stop("B0 per_age is not an object")
    for age in LATE_AGES:
        line_blocks: dict[str, object] = {}
        for name in LINE_NAMES:
            selected = entries[age][name]
            line = CEILING.summarize_line(selected, EXPECTED_DAYS)
            line_blocks[name] = {
                "portfolio_dollar_block": line.as_dict(),
                "assets": {
                    asset: {
                        **_asset_block(selected, asset),
                        "eligible_candidates": sum(
                            score.eligible_by_age[age][name]
                            for score in ordered
                            if score.asset == asset
                        ),
                        "entered_cells": sum(
                            row.asset == asset for row in selected
                        ),
                    }
                    for asset in ASSETS
                },
            }
        expected_age = b0_per_age.get(str(age))
        if not isinstance(expected_age, dict):
            raise B1Stop(f"B0 lacks control age {age}")
        expected_control = expected_age.get("portfolio_dollar_block")
        actual_control = line_blocks["cellbest_control"]["portfolio_dollar_block"]
        _assert_control_match(actual_control, expected_control)
        controls[str(age)] = {
            "status": "PASS",
            "actual_sha256": _object_sha256(actual_control),
            "expected_sha256": _object_sha256(expected_control),
            "byte_equal": True,
        }
        agreement_assets: dict[str, object] = {}
        total_numerator = 0
        total_denominator = 0
        for asset in ASSETS:
            numerator = sum(
                score.agreement_by_age[age][0]
                for score in ordered
                if score.asset == asset
            )
            denominator = sum(
                score.agreement_by_age[age][1]
                for score in ordered
                if score.asset == asset
            )
            agreement_assets[asset] = {
                "numerator": numerator,
                "denominator": denominator,
                "fraction": numerator / denominator if denominator else None,
            }
            total_numerator += numerator
            total_denominator += denominator
        per_age[str(age)] = {
            "lines": line_blocks,
            "side_agreement": {
                "numerator": total_numerator,
                "denominator": total_denominator,
                "fraction": (
                    total_numerator / total_denominator
                    if total_denominator
                    else None
                ),
                "assets": agreement_assets,
                "dollar_attached": False,
            },
        }
    qualifying = _qualifying_ages(b0)
    witnesses = {
        variant: _variant_witness(
            variant,
            entries,
            per_age,
            qualifying,
        )
        for variant in PRIMARY_LINES
    }
    winning_variant = next(
        (
            variant
            for variant in PRIMARY_LINES
            if witnesses[variant]["status"] == "PASS"
        ),
        None,
    )
    mixed = _mixed_variant_witness(entries, per_age, qualifying)
    verdict = "LIVE" if winning_variant is not None else "KILL"
    return {
        "status": verdict,
        "verdict": verdict,
        "per_age": per_age,
        "cellbest_control": controls,
        "qualifying_ages_seconds": {
            asset: list(ages) for asset, ages in qualifying.items()
        },
        "variant_witnesses": witnesses,
        "same_variant_witness": winning_variant,
        "mixed_variant_assignment": mixed,
        "dollar_stop": {
            "verdict": verdict,
            "rungs_usd": dict(RUNGS_USD),
            "drawdown_limit_usd": DRAWDOWN_LIMIT_USD,
            "entry_cap": ENTRY_CAP,
            "verbatim": dict(STOP_VERBATIM),
            "applied": STOP_VERBATIM[verdict],
        },
    }


def _synthetic_base(
    candidate_id: str,
    side: int,
    entry_mid2: int,
) -> BaseObservation:
    decision = NANOS_PER_SECOND
    return BaseObservation(
        candidate_id,
        "HG",
        20220315,
        side,
        0,
        decision,
        _ceil_second(decision),
        20_000 * NANOS_PER_SECOND,
        entry_mid2,
    )


def _synthetic_stored(
    candidate_id: str,
    side: int,
    entry_mid2: int,
    cash_usd: Decimal,
    *,
    status: str = READY,
    snapshot_shift_seconds: int = 0,
) -> StoredAgeRow:
    decision = NANOS_PER_SECOND
    age = 600
    snapshot = (
        _ceil_second(decision)
        + age * NANOS_PER_SECOND
        + snapshot_shift_seconds * NANOS_PER_SECOND
    )
    return StoredAgeRow(
        candidate_id,
        "HG",
        20220315,
        side,
        0,
        decision,
        age,
        snapshot,
        20_000 * NANOS_PER_SECOND,
        entry_mid2,
        Decimal("5"),
        status,
        cash_usd,
        snapshot + NANOS_PER_SECOND,
    )


def _must_refuse(action: Callable[[], object], mutant: str) -> None:
    try:
        action()
    except B1Stop:
        return
    raise AssertionError(f"{mutant} stayed green")


def _selftest() -> dict[str, object]:
    _assert_contract()
    long_base = _synthetic_base("long", 1, 100)
    short_base = _synthetic_base("short", -1, 100)
    long_row = _synthetic_stored("long", 1, 120, Decimal("-10"))
    short_row = _synthetic_stored("short", -1, 90, Decimal("100"))
    long = _candidate_at_age(long_base, long_row)
    short = _candidate_at_age(short_base, short_row)
    if long.record_units != 20 or short.record_units != 10:
        raise AssertionError(
            f"record sign drifted: long={long.record_units} short={short.record_units}"
        )
    if _pick_primary((long, short)) != long:
        raise AssertionError("primary record pick drifted")
    cell = _score_cell((long, short))
    if (
        cell.selected["record_top1_all"] != long
        or cell.selected["record_top1_pos"] != long
        or cell.selected["sideoracle_record"] != short
        or cell.selected["recordside_price"] != long
        or cell.selected["cellbest_control"] != short
        or cell.side_agreement_numerator != 0
        or cell.side_agreement_denominator != 1
    ):
        raise AssertionError(f"five-line synthetic selection drifted: {cell!r}")
    tie_a = _candidate_at_age(
        _synthetic_base("a", 1, 100),
        _synthetic_stored("a", 1, 110, Decimal("1")),
    )
    tie_b = _candidate_at_age(
        _synthetic_base("b", 1, 100),
        _synthetic_stored("b", 1, 110, Decimal("2")),
    )
    if _pick_record((tie_b, tie_a)) != tie_a:
        raise AssertionError("record tie-break drifted")
    zero_record = _candidate_at_age(
        _synthetic_base("zero", 1, 100),
        _synthetic_stored("zero", 1, 100, Decimal("10")),
    )
    if _score_cell((zero_record,)).selected["record_top1_pos"] is not None:
        raise AssertionError("record_top1_pos accepted a zero record")
    future = _synthetic_stored(
        "long",
        1,
        120,
        Decimal("-10"),
        snapshot_shift_seconds=30,
    )
    _must_refuse(
        lambda: _record_units(long_base, future),
        "future_mid_in_record",
    )
    nonready = _synthetic_stored(
        "long",
        1,
        120,
        Decimal("-10"),
        status="PHASE_CLOSED",
    )
    _must_refuse(
        lambda: _ensure_ready_entry(nonready),
        "nonready_entered",
    )
    _must_refuse(
        lambda: _validate_primary_pick(short, (long, short)),
        "oracle_leak_primary",
    )
    _must_refuse(
        lambda: _assert_control_match({"cash": 1}, {"cash": 2}),
        "control_mismatch_accepted",
    )
    return {
        "status": "PASS",
        "synthetic_era_bytes_read": 0,
        "line_names": list(LINE_NAMES),
        "ages_seconds": list(LATE_AGES),
        "mutants": {name: "RED" for name in MUTANTS},
    }


def _verification_command(mutant: str | None) -> str:
    if mutant is None:
        return "python3 .audit/score_threshold_b1_picker.py --selftest"
    return (
        f"QRE2_B1_MUTANT={mutant} "
        "python3 .audit/score_threshold_b1_picker.py --selftest"
    )


def _run_red_first_checks() -> dict[str, object]:
    checks: list[tuple[str, str | None]] = [("selftest", None)]
    checks.extend((name, name) for name in MUTANTS)
    results: dict[str, object] = {}
    for label, mutant in checks:
        environment = dict(os.environ)
        environment.pop("QRE2_B1_MUTANT", None)
        if mutant is not None:
            environment["QRE2_B1_MUTANT"] = mutant
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--selftest"],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        combined = "\n".join(
            part for part in (completed.stdout, completed.stderr) if part
        )
        if mutant is None:
            if completed.returncode != 0:
                raise B1Stop(
                    f"baseline selftest failed with {completed.returncode}: "
                    f"{combined.strip().splitlines()[-1:]}"
                )
            status = "PASS"
        else:
            expected = f"{mutant} stayed green"
            if completed.returncode == 0 or expected not in combined:
                raise B1Stop(
                    f"mutant {mutant} did not die on its named seam"
                )
            status = "KILLED"
        results[label] = {
            "command": _verification_command(mutant),
            "exit_code": completed.returncode,
            "status": status,
            "failure": (
                f"{mutant} stayed green" if mutant is not None else None
            ),
        }
    return {
        "status": "PASS",
        "synthetic_era_bytes_read": 0,
        "red_first_before_era_read": True,
        "failures_in_order": [f"{name} stayed green" for name in MUTANTS],
        "checks": results,
    }


def _base_receipt(started: float) -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "unit": "B1",
        "status": "STOP",
        "verdict": "STOP",
        "ages_seconds": list(LATE_AGES),
        "lines": list(LINE_NAMES),
        "line_rules": dict(LINE_RULES),
        "primary_variants": list(PRIMARY_LINES),
        "decomposition_lines": list(DECOMPOSITION_LINES),
        "mutants": list(MUTANTS),
        "locked_asset_days": dict(EXPECTED_DAYS),
        "worker_budget": WORKER_BUDGET,
        "workers_by_asset": dict(WORKERS_BY_ASSET),
        "asset_chain_workers": ASSET_CHAIN_WORKERS,
        "tripwire_seconds": TRIPWIRE_SECONDS,
        "dollar_line_reads": 0,
        "passes_over_late_store": 0,
        "age0_cert_close_usd_values_used": 0,
        "dollar_lines_below_age_600": 0,
        "stored_teacher_fields_parsed": [],
        "stored_teacher_open_guard": "NOT_RUN",
        "stored_tree_rewritten": False,
        "fit_started": False,
        "judge_started": False,
        "training_scale_relabel_started": False,
        "age180_teacher_join_reopened": False,
        "tickets_37_46_47_started": False,
        "lsp0_started": False,
        "touched_2025": False,
        "teacher_cash_can_promote": False,
        "wall_clock_seconds": time.monotonic() - started,
    }


def _verify_existing_receipt() -> dict[str, object]:
    receipt = _read_json(RECEIPT_PATH)
    if (
        receipt.get("schema") != SCHEMA
        or receipt.get("status") not in {"LIVE", "KILL", "STOP"}
        or receipt.get("verdict") != receipt.get("status")
    ):
        raise B1Stop("existing B1 receipt contract drifted")
    if receipt.get("status") in {"LIVE", "KILL"}:
        sources = receipt.get("sources")
        if not isinstance(sources, dict) or sources != _source_sha256s():
            raise B1Stop("existing B1 source hashes drifted")
        if int(receipt.get("dollar_line_reads", -1)) != 1:
            raise B1Stop("existing B1 dollar-line read count drifted")
    return receipt


def _summary(receipt: Mapping[str, object]) -> str:
    return (
        f"{SCHEMA} {receipt.get('verdict')} "
        f"receipt={_relative(RECEIPT_PATH)} "
        f"wall_clock_seconds={receipt.get('wall_clock_seconds')}"
    )


def execute() -> int:
    if RECEIPT_PATH.exists():
        receipt = _verify_existing_receipt()
        print(_summary(receipt), flush=True)
        return 0 if receipt.get("status") in {"LIVE", "KILL"} else 1
    started = time.monotonic()
    deadline = started + TRIPWIRE_SECONDS
    receipt = _base_receipt(started)
    try:
        _assert_contract()
        b0, b0_precondition = _b0_precondition()
        receipt["b0_precondition"] = b0_precondition
        receipt["sources"] = _source_sha256s()
        receipt["selftest"] = _run_red_first_checks()
        protected_before = _protected_metadata()
        receipt["protected_trees_before"] = protected_before
        shards, manifest = _manifest_shards(b0)
        receipt["manifest"] = manifest
        with _deny_stored_teacher_opens():
            hash_started = time.monotonic()
            verified = _run_three_asset_chains(
                shards,
                _verify_shard_hash,
                "hash",
                deadline,
            )
            if len(verified) != len(shards):
                raise B1Stop(
                    f"hash verification returned {len(verified)} of {len(shards)} shards"
                )
            receipt["shard_hash_verification"] = {
                "status": "PASS",
                "verified_before_any_dollar": True,
                "shards": len(verified),
                "bytes": sum(row.bytes for row in verified),
                "wall_seconds": time.monotonic() - hash_started,
                "max_shard_wall_seconds": max(
                    row.wall_seconds for row in verified
                ),
            }
            receipt["hg_projection"] = _projection_from_hg(b0, verified)
            if time.monotonic() > deadline:
                raise B1Stop("pre-dollar guards crossed the 3600-second tripwire")
            receipt["dollar_line_reads"] = 1
            receipt["passes_over_late_store"] = 1
            score_started = time.monotonic()
            scores = _run_three_asset_chains(
                verified,
                _score_shard,
                "score",
                deadline,
            )
            if len(scores) != len(shards):
                raise B1Stop(
                    f"scoring returned {len(scores)} of {len(shards)} shards"
                )
            receipt["scoring"] = {
                "status": "PASS",
                "shards_read": len(scores),
                "rows_read": sum(row.rows_read for row in scores),
                "ready_rows": sum(row.ready_rows for row in scores),
                "passes_over_late_store": 1,
                "age0_cert_close_usd_values_used": sum(
                    row.age0_cert_close_values_used for row in scores
                ),
                "wall_seconds": time.monotonic() - score_started,
                "max_shard_wall_seconds": max(
                    row.wall_seconds for row in scores
                ),
                "three_asset_chains": True,
                "worker_budget": WORKER_BUDGET,
            }
        receipt["stored_teacher_open_guard"] = "PASS"
        protected_after = _protected_metadata()
        if protected_after != protected_before:
            raise B1Stop("a protected stored tree changed during B1")
        receipt["protected_trees_after"] = protected_after
        receipt["stored_tree_rewritten"] = False
        result = _aggregate_scores(scores, b0)
        if time.monotonic() > deadline:
            raise B1Stop("B1 crossed the 3600-second tripwire")
        if int(receipt["dollar_line_reads"]) != 1:
            raise B1Stop("dollar_line_reads is not exactly 1")
        receipt.update(result)
        receipt["wall_clock_seconds"] = time.monotonic() - started
        _atomic_json(RECEIPT_PATH, receipt)
        print(_summary(receipt), flush=True)
        return 0
    except Exception as error:
        receipt["status"] = "STOP"
        receipt["verdict"] = "STOP"
        receipt["stop_reason"] = f"{type(error).__name__}: {error}"
        receipt["dollar_stop"] = {
            "verdict": "STOP",
            "verbatim": dict(STOP_VERBATIM),
            "applied": STOP_VERBATIM["STOP"],
        }
        receipt["wall_clock_seconds"] = time.monotonic() - started
        _atomic_json(RECEIPT_PATH, receipt)
        print(
            f"{SCHEMA} STOP {type(error).__name__}: {error}",
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
    if MUTANT:
        raise B1Stop("QRE2_B1_MUTANT is allowed only with --selftest")
    return execute()


if __name__ == "__main__":
    raise SystemExit(main())
