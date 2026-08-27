#!/usr/bin/env python3
"""Run the frozen V0 Stage 0 preconditions and publish its receipt."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
RECEIPT_PATH = ROOT / ".audit/threshold-v0-stage0.json"
ENGINE_ROOT = ROOT / "engine/entry_v2"
LATE_ROOT = ROOT / "artifacts/cache/port/entry_v2/g1/late2021"
LOCKED_LATE_ROOT = ROOT / "artifacts/cache/port/entry_v2/g1/late"
QRF4_ROOT = ROOT / "artifacts/cache/port/entry_v2/forecast"
SERVICE_FORECAST = (
    ROOT / "artifacts/runs/e6_vol_forecasts_v2/vol_service_forecasts.tsv"
)
WINDOW_START_D8 = 20210101
WINDOW_END_D8_EXCLUSIVE = 20220101
WORKERS_BY_ASSET = {"HG": 5, "NKD": 4, "SI": 4}
WORKER_BUDGET = sum(WORKERS_BY_ASSET.values())
TRIPWIRE_SECONDS = 2 * 60 * 60
RECEIPT_SCHEMA = "QRE2THRESHOLDV0STAGE01"
PINNED_ENGINE_SHA256 = (
    "a50bd4986f7bb39a0abacb4728d0e7e21528995b50b8ddebb7c541daf013b813"
)
PREFLIGHT_2025_SCOPE_BREACH = {
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
GATE_REQUIRED_FIELDS = frozenset(
    {
        "head",
        "arm",
        "outer_fold",
        "day",
        "forecast_variance",
        "train_sessions_n",
    }
)
SOURCE_FILES = (
    ROOT / ".audit/threshold_v0_stage0.py",
    ROOT / ".audit/briefs/threshold-covering-after-b2-fable-out.md",
    ROOT / ".audit/briefs/threshold-v0-stage0.md",
    ROOT / ".audit/threshold-b0-stage0.json",
    ROOT / ".audit/threshold_b0_stage0.py",
    ROOT / ".audit/threshold-b2-price-picker.json",
    ROOT / ".audit/briefs/threshold-b2-price-picker-judge-out.md",
    ROOT / ".audit/score_threshold_2022_2024_ceiling.py",
    ROOT / ".audit/score_threshold_2022_2024_read.py",
)


class V0Stop(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ForecastContract:
    asset: str
    path: Path
    start_d8: int
    end_d8_exclusive: int
    columns: tuple[str, ...]
    header_bytes_read: int

    @property
    def missing_gate_fields(self) -> tuple[str, ...]:
        return tuple(sorted(GATE_REQUIRED_FIELDS.difference(self.columns)))

    @property
    def spans_2025(self) -> bool:
        return self.end_d8_exclusive > 20250101

    def as_dict(self) -> dict[str, object]:
        return {
            "asset": self.asset,
            "path": _relative(self.path),
            "start_d8": self.start_d8,
            "end_d8_exclusive": self.end_d8_exclusive,
            "columns_sha256": _sha256_bytes("\t".join(self.columns).encode()),
            "missing_gate_fields": list(self.missing_gate_fields),
            "gate_schema_compatible": _gate_schema_compatible(self.columns),
            "spans_2025": self.spans_2025,
            "header_bytes_read": self.header_bytes_read,
            "data_rows_read": 0,
        }


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


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
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_json(path: Path, value: object) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    _atomic_write(path, payload)


def _run_git(arguments: Sequence[str]) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.rstrip()


def _engine_tree_sha256() -> str:
    paths = tuple(
        sorted(
            path
            for path in ENGINE_ROOT.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        )
    )
    digest = hashlib.sha256()
    for path in paths:
        digest.update(_relative(path).encode())
        digest.update(b"\0")
        digest.update(_sha256_file(path).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def _source_sha256s() -> dict[str, str]:
    missing = tuple(_relative(path) for path in SOURCE_FILES if not path.is_file())
    if missing:
        raise V0Stop(f"Stage 0 sources are absent: {missing}")
    return {_relative(path): _sha256_file(path) for path in SOURCE_FILES}


def _gate_schema_compatible(columns: Sequence[str]) -> bool:
    if os.environ.get("QRE2_V0_MUTANT") == "gate_schema_mismatch_accepted":
        return True
    return GATE_REQUIRED_FIELDS.issubset(columns)


def _forecast_contract(asset: str) -> ForecastContract:
    path = QRF4_ROOT / f"{asset}.qrf4.tsv"
    if not path.is_file():
        raise V0Stop(f"QRE2FORECAST4 artifact is absent: {path}")
    with path.open("rb") as source:
        marker_raw = source.readline()
        columns_raw = source.readline()
    try:
        marker = marker_raw.decode("utf-8").rstrip("\n")
        columns_text = columns_raw.decode("utf-8").rstrip("\n")
    except UnicodeDecodeError as error:
        raise V0Stop(f"QRE2FORECAST4 header is not UTF-8: {path}") from error
    match = re.fullmatch(
        r"# QRE2FORECAST4 start_d8=(\d{8}) end_d8_exclusive=(\d{8}) "
        r"asset=(SI|HG|NKD) law_sha256=([0-9a-f]{64})",
        marker,
    )
    if match is None or match.group(3) != asset:
        raise V0Stop(f"QRE2FORECAST4 marker differs: {path}")
    columns = tuple(columns_text.split("\t"))
    if not columns or columns[0] != "asset":
        raise V0Stop(f"QRE2FORECAST4 columns differ: {path}")
    return ForecastContract(
        asset=asset,
        path=path,
        start_d8=int(match.group(1)),
        end_d8_exclusive=int(match.group(2)),
        columns=columns,
        header_bytes_read=len(marker_raw) + len(columns_raw),
    )


def _service_forecast_contract() -> dict[str, object]:
    if not SERVICE_FORECAST.is_file():
        raise V0Stop(f"era gate forecast is absent: {SERVICE_FORECAST}")
    with SERVICE_FORECAST.open("rb") as source:
        columns_raw = source.readline()
        first_row_raw = source.readline()
    try:
        columns = tuple(columns_raw.decode("utf-8").rstrip("\n").split("\t"))
        first_row = tuple(first_row_raw.decode("utf-8").rstrip("\n").split("\t"))
    except UnicodeDecodeError as error:
        raise V0Stop("era gate forecast header is not UTF-8") from error
    if not _gate_schema_compatible(columns):
        raise V0Stop("era gate forecast no longer matches the pinned loader schema")
    day_index = columns.index("day")
    if len(first_row) != len(columns):
        raise V0Stop("era gate forecast first row width differs")
    return {
        "path": _relative(SERVICE_FORECAST),
        "gate_schema_compatible": True,
        "first_data_day": first_row[day_index],
        "header_bytes_read": len(columns_raw) + len(first_row_raw),
        "later_rows_read": 0,
        "qre2forecast4": False,
    }


def _selftest() -> dict[str, object]:
    contracts = tuple(_forecast_contract(asset) for asset in WORKERS_BY_ASSET)
    compatible = tuple(
        contract.asset
        for contract in contracts
        if _gate_schema_compatible(contract.columns)
    )
    if compatible:
        raise V0Stop(
            f"gate_schema_mismatch_accepted stayed green for assets {compatible}"
        )
    if any(contract.start_d8 != WINDOW_START_D8 for contract in contracts):
        raise V0Stop("QRE2FORECAST4 start window differs")
    if any(not contract.spans_2025 for contract in contracts):
        raise V0Stop("QRE2FORECAST4 end window differs")
    return {
        "status": "PASS",
        "mutants": {"gate_schema_mismatch_accepted": "RED"},
        "qre2forecast4_assets": [contract.asset for contract in contracts],
        "qre2forecast4_data_rows_read": 0,
    }


def _gate_source_precondition() -> dict[str, object]:
    contracts = tuple(_forecast_contract(asset) for asset in WORKERS_BY_ASSET)
    service = _service_forecast_contract()
    compatible = tuple(
        contract.asset
        for contract in contracts
        if _gate_schema_compatible(contract.columns)
    )
    holds = bool(compatible) and len(compatible) == len(contracts)
    return {
        "status": "PASS" if holds else "STOP",
        "window": {
            "start_d8": WINDOW_START_D8,
            "end_d8_exclusive": WINDOW_END_D8_EXCLUSIVE,
        },
        "pinned_functions": [
            "load_window_forecast_rows",
            "route_catboost_daily",
            "select_expanding_median",
        ],
        "required_loader_fields": sorted(GATE_REQUIRED_FIELDS),
        "qre2forecast4": {
            contract.asset: contract.as_dict() for contract in contracts
        },
        "era_gate_source": service,
        "compatible_qre2forecast4_assets": list(compatible),
        "day_membership_formed": False,
        "routed_counts_by_asset": {asset: 0 for asset in WORKERS_BY_ASSET},
        "selected_counts_by_asset": {asset: 0 for asset in WORKERS_BY_ASSET},
        "reason": (
            "the pinned gate loader schema and the named QRE2FORECAST4 schema "
            "do not intersect on the frozen gate fields; choosing a QRE2FORECAST4 "
            "value as forecast_variance would amend the frozen rule"
        ),
    }


def _base_receipt(started: float) -> dict[str, object]:
    return {
        "schema": RECEIPT_SCHEMA,
        "unit": "V0_STAGE0",
        "status": "STOP",
        "window": {
            "start_d8": WINDOW_START_D8,
            "end_d8_exclusive": WINDOW_END_D8_EXCLUSIVE,
        },
        "worker_budget": WORKER_BUDGET,
        "workers_by_asset": dict(WORKERS_BY_ASSET),
        "asset_chain_workers": len(WORKERS_BY_ASSET),
        "tripwire_seconds": TRIPWIRE_SECONDS,
        "stage1_started": False,
        "replay_freeze_started": False,
        "exit_overlay_started": False,
        "fit_started": False,
        "dollar_line_formed": False,
        "dollar_line_reads": 0,
        "locked_era_late_store_opened": False,
        "locked_era_late_store_written": False,
        "late2021_tree_created": False,
        "late2021_shards_written": 0,
        "manifest_published": False,
        "runner_year_2025_data_rows_read": 0,
        "year_2025_data_rows_read": "UNKNOWN_POSITIVE",
        "scope_guard": dict(PREFLIGHT_2025_SCOPE_BREACH),
        "tickets_37_46_47_started": False,
        "wall_clock_seconds": time.monotonic() - started,
    }


def execute() -> int:
    started = time.monotonic()
    receipt = _base_receipt(started)
    try:
        if LATE_ROOT.exists():
            raise V0Stop(f"V0 output root already exists: {LATE_ROOT}")
        engine_sha256 = _engine_tree_sha256()
        receipt["engine_tree_start"] = {
            "status": "PASS" if engine_sha256 == PINNED_ENGINE_SHA256 else "STOP",
            "head": _run_git(["rev-parse", "HEAD"]),
            "engine_tree_sha256": engine_sha256,
            "expected_engine_tree_sha256": PINNED_ENGINE_SHA256,
        }
        if engine_sha256 != PINNED_ENGINE_SHA256:
            raise V0Stop(
                f"engine tree fingerprint differs: {engine_sha256}"
            )
        receipt["sources"] = _source_sha256s()
        receipt["selftest"] = _selftest()
        gate = _gate_source_precondition()
        receipt["gate_source_precondition"] = gate
        if PREFLIGHT_2025_SCOPE_BREACH["status"] == "STOP":
            raise V0Stop(
                "2025H1 forecast bytes were read by pre-run diagnostic census "
                "commands; the frozen no-2025 guard fired"
            )
        if gate["status"] != "PASS":
            raise V0Stop(str(gate["reason"]))
        raise V0Stop("gate source changed after dispatch; no frozen build path exists")
    except Exception as error:
        receipt["status"] = "STOP"
        receipt["stop_reason"] = f"{type(error).__name__}: {error}"
        receipt["locked_era_late_store_exists"] = LOCKED_LATE_ROOT.is_dir()
        receipt["late2021_tree_created"] = LATE_ROOT.exists()
        receipt["wall_clock_seconds"] = time.monotonic() - started
        _atomic_json(RECEIPT_PATH, receipt)
        print(
            f"{RECEIPT_SCHEMA} STOP {type(error).__name__}: {error}",
            file=sys.stderr,
            flush=True,
        )
        return 1


def selftest_main() -> int:
    print(json.dumps(_selftest(), sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    arguments = parser.parse_args()
    if arguments.selftest:
        return selftest_main()
    return execute()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V0Stop as error:
        print(f"{RECEIPT_SCHEMA} STOP {error}", file=sys.stderr)
        raise SystemExit(1) from error
