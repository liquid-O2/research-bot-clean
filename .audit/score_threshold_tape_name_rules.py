#!/usr/bin/env python3
"""Causal tape name rules on stored QRSESS1 sessions. Throwaway."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
RECEIPT = REPO / ".audit/threshold-tape-name-rules.json"
COVERING_BRIEF = (
    REPO / ".audit/briefs/threshold-covering-after-name-rules-kill-out.md"
)
SPECIFICATION_BRIEF = REPO / ".audit/briefs/threshold-tape-name-rules.md"
FULL_ROSTER_CEILING = REPO / ".audit/threshold-2022-2024-ceiling.json"
STORED_NAME_RECEIPT = REPO / ".audit/threshold-stored-name-rules.json"
SESSION_ROOT = REPO / "artifacts/cache/corpus_2022_2024/sessions"
STORED_NAME_SCRIPT = REPO / ".audit/score_threshold_stored_name_rules.py"
LIVE_SCALARS_SCRIPT = REPO / ".audit/score_threshold_live_scalars.py"
TICKET45_SCRIPT = REPO / ".audit/run_ticket45_pilot.py"
CHECK = "python3 .audit/score_threshold_tape_name_rules.py"
SCHEMA = "QRE2THRESHOLDTAPENAMERULES1"
LABEL = (
    "eight causal tape-derived name rules on stored QRSESS1 sessions, plus "
    "the exploratory hindsight envelope_tape8 family bound. Teacher-cash "
    "can kill and cannot promote."
)
RULE = (
    "On every joinable 2022-03-09 through 2024-12-31 gated cell, score CLEAR "
    "names on the trailing 180 seconds before their own decision second. "
    "Apply the eight preregistered flow, imbalance, drift, and churn rules. "
    "Pick one contract per cell. Cash is cert_close_usd on READY. The day "
    "gate is the freeze expanding median."
)
PEEK_NOTE = (
    "candidate-side inputs widen to pre-decision market bytes from QRSESS1 "
    "sessions; teacher-side license is unchanged; kill instrument, cannot promote."
)
WORKERS = 14
WINDOW_SECONDS = 180
ALLOWED_TRADE_SIDES = frozenset((65, 66, 78))
MUTANT = os.environ.get("QRE2_TAPE_MUTANT", "")
MUTANTS = ("include_decision_second", "drop_side_alignment", "swap_buy_sell")
RULES = {
    "tape_flow_with": "Argmax of side times trailing-window signed-flow sum.",
    "tape_flow_against": "Argmin of side times trailing-window signed-flow sum.",
    "tape_imbalance_with": (
        "Argmax of side times mean valid trailing-window book imbalance."
    ),
    "tape_imbalance_against": (
        "Argmin of side times mean valid trailing-window book imbalance."
    ),
    "tape_drift_with": "Argmax of side times trailing-window valid-mid drift.",
    "tape_drift_against": "Argmin of side times trailing-window valid-mid drift.",
    "tape_churn_max": "Argmax of trailing-window g0_upd_count sum.",
    "tape_churn_min": "Argmin of trailing-window g0_upd_count sum.",
}
RULE_SPECS = (
    ("tape_flow_with", "flow_aligned", True),
    ("tape_flow_against", "flow_aligned", False),
    ("tape_imbalance_with", "imbalance_aligned", True),
    ("tape_imbalance_against", "imbalance_aligned", False),
    ("tape_drift_with", "drift_aligned", True),
    ("tape_drift_against", "drift_aligned", False),
    ("tape_churn_max", "churn", True),
    ("tape_churn_min", "churn", False),
)
RULE_NAMES = tuple(name for name, _field, _want_max in RULE_SPECS)
BOOK_RULE_NAMES = frozenset(
    (
        "tape_imbalance_with",
        "tape_imbalance_against",
        "tape_drift_with",
        "tape_drift_against",
    )
)
REQUIRED_ARRAYS = (
    "g0_bid_sz",
    "g0_ask_sz",
    "g0_state",
    "g0_upd_count",
    "g0_mid",
    "trades_sec",
    "trades_size",
    "trades_side",
)
CANDIDATE_EXTRA_COLS = ("decision_sec", "side")


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module


_stored = _load_module(STORED_NAME_SCRIPT)
_killed = _stored._killed
_ceiling = _stored._ceiling
_gap = _stored._gap

ASSETS = _killed.ASSETS
PHASES = _killed.PHASES
WINDOW_START = _killed.WINDOW_START
WINDOW_END = _killed.WINDOW_END
RUNGS_USD = _killed.RUNGS_USD
DRAWDOWN_LIMIT_USD = _killed.DRAWDOWN_LIMIT_USD
ENTRY_CAP = _killed.ENTRY_CAP
EXPECTED_GATED_DAYS = _ceiling.EXPECTED_GATED_DAYS
JoinUnavailable = _killed.JoinUnavailable
SelectedName = _killed.SelectedName
Line = _ceiling.Line
route_catboost_daily = _killed.route_catboost_daily
select_expanding_median = _killed.select_expanding_median
load_window_forecast_rows = _killed.load_window_forecast_rows
_load_teacher = _killed._load_teacher
_sha256_file = _killed._sha256_file
_relative = _killed._relative
_receipt_output_sha256 = _killed._receipt_output_sha256
_assert_no_peek = _killed._assert_no_peek
PEEK_COLS = _killed.PEEK_COLS
CANDIDATE_COLS = _killed.CANDIDATE_COLS
TEACHER_COLS = _killed.TEACHER_COLS
FORECAST = _killed.FORECAST
CANDIDATES = _killed.CANDIDATES
TEACHERS = _killed.TEACHERS
RECEIPTS = _killed.RECEIPTS
KILLED_READ = _ceiling.KILLED_READ
FREEZE = _killed.FREEZE
summarize_line = _ceiling.summarize_line
pick_cell_best_ready = _ceiling.pick_cell_best_ready
enter_positive = _ceiling.enter_positive
_ready_rows = _ceiling._ready_rows
_as_selected = _ceiling._as_selected
_join_picked = _gap._join_picked
TAPE_CANDIDATE_COLS = CANDIDATE_COLS + CANDIDATE_EXTRA_COLS


@dataclass(frozen=True, slots=True)
class TapeName:
    candidate_id: str
    asset: str
    d8: int
    phase: int
    decision_ts_ns: int
    decision_sec: int
    side: int
    frozen_cost_usd: float


@dataclass(frozen=True, slots=True)
class PreparedTape:
    n_seconds: int
    flow_prefix: np.ndarray
    imbalance_prefix: np.ndarray
    valid_count_prefix: np.ndarray
    churn_prefix: np.ndarray
    mid: np.ndarray
    next_valid: np.ndarray
    previous_valid: np.ndarray
    identity: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class TapeScore:
    row: TapeName
    flow_aligned: float
    imbalance_aligned: float | None
    drift_aligned: float | None
    churn: float


@dataclass(frozen=True, slots=True)
class RulePicks:
    causal: Mapping[str, tuple[TapeName, ...]]
    fallbacks: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class DayBundle:
    asset: str
    d8: int
    joinable: bool
    picks: Mapping[str, tuple[object, ...]]
    envelope: tuple[object, ...]
    fallbacks: Mapping[str, int]
    source_identity: Mapping[str, object] | None
    session_identity: Mapping[str, object] | None
    missing_session: Mapping[str, object] | None


def _empty_picks() -> dict[str, tuple[object, ...]]:
    return {name: () for name in RULE_NAMES}


def _load_tape_names(
    asset: str, d8: int
) -> tuple[int, tuple[TapeName, ...], Path | None]:
    path = CANDIDATES / asset / f"{d8}.tsv"
    if not path.is_file():
        return 0, (), None
    _assert_no_peek(TAPE_CANDIDATE_COLS, "candidates")
    frame = pd.read_csv(
        path,
        sep="\t",
        skiprows=1,
        usecols=list(TAPE_CANDIDATE_COLS),
        dtype={
            "candidate_id": str,
            "asset": str,
            "d8": np.int64,
            "phase": np.int64,
            "decision_ts_ns": np.int64,
            "decision_sec": np.int64,
            "side": np.int64,
            "compliance_status": str,
            "frozen_cost_usd": np.float64,
        },
    )
    n_rows = int(len(frame))
    if n_rows == 0:
        return 0, (), path
    if set(frame["asset"].unique()) - {asset}:
        raise JoinUnavailable(
            "candidates.asset",
            f"{path} asset values {sorted(frame['asset'].unique())} != {asset}",
        )
    if set(frame["d8"].unique()) - {d8}:
        raise JoinUnavailable(
            "candidates.d8",
            f"{path} d8 values {sorted(int(v) for v in frame['d8'].unique())} != {d8}",
        )
    clear = frame[frame["compliance_status"] == "CLEAR"]
    rows: list[TapeName] = []
    for row in clear.itertuples(index=False):
        candidate_id = str(row.candidate_id)
        side = int(row.side)
        decision_sec = int(row.decision_sec)
        if side not in (-1, 1):
            raise JoinUnavailable(
                "candidates.side",
                f"{path} candidate {candidate_id!r} side {side!r} expected -1 or 1",
            )
        if decision_sec < 0:
            raise JoinUnavailable(
                "candidates.decision_sec",
                f"{path} candidate {candidate_id!r} decision_sec {decision_sec!r} "
                "expected nonnegative",
            )
        rows.append(
            TapeName(
                candidate_id=candidate_id,
                asset=str(row.asset),
                d8=int(row.d8),
                phase=int(row.phase),
                decision_ts_ns=int(row.decision_ts_ns),
                decision_sec=decision_sec,
                side=side,
                frozen_cost_usd=float(row.frozen_cost_usd),
            )
        )
    return n_rows, tuple(rows), path


def _stored_array_bytes(metadata: Mapping[str, object]) -> int:
    arrays = metadata.get("arrays")
    if not isinstance(arrays, list):
        raise JoinUnavailable(
            "session.arrays",
            f"QRSESS1 arrays must be a list, got {type(arrays).__name__}",
        )
    end = 0
    for descriptor_index, raw in enumerate(arrays):
        if not isinstance(raw, dict):
            raise JoinUnavailable(
                "session.arrays",
                "QRSESS1 array descriptor must be an object, "
                f"got index={descriptor_index} type={type(raw).__name__}",
            )
        dtype = np.dtype(str(raw["dtype"]))
        end = max(end, int(raw["offset"]) + int(raw["count"]) * dtype.itemsize)
    return end


def _array_descriptors(
    metadata: Mapping[str, object], source: Path
) -> dict[str, Mapping[str, object]]:
    raw_arrays = metadata.get("arrays")
    if not isinstance(raw_arrays, list):
        raise JoinUnavailable(
            "session.arrays",
            f"{source} arrays {type(raw_arrays).__name__} expected list",
        )
    descriptors: dict[str, Mapping[str, object]] = {}
    for index, raw in enumerate(raw_arrays):
        if not isinstance(raw, dict):
            raise JoinUnavailable(
                "session.arrays",
                f"{source} descriptor {index} type {type(raw).__name__} expected object",
            )
        name = str(raw.get("name"))
        if name in descriptors:
            raise JoinUnavailable(
                "session.arrays",
                f"{source} repeats array name {name!r}",
            )
        descriptors[name] = raw
    missing = [name for name in REQUIRED_ARRAYS if name not in descriptors]
    if missing:
        raise JoinUnavailable(
            "session.arrays",
            f"{source} missing required QRSESS1 arrays {missing}",
        )
    return descriptors


def _array_view(
    payload: bytes,
    descriptor: Mapping[str, object],
    source: Path,
) -> np.ndarray:
    name = str(descriptor.get("name"))
    try:
        dtype = np.dtype(str(descriptor["dtype"]))
        count = int(descriptor["count"])
        offset = int(descriptor["offset"])
    except (KeyError, TypeError, ValueError) as exc:
        raise JoinUnavailable(
            "session.array_descriptor",
            f"{source} array {name!r} descriptor {dict(descriptor)!r} is invalid",
        ) from exc
    if count < 0 or offset < 0:
        raise JoinUnavailable(
            "session.array_descriptor",
            f"{source} array {name!r} count {count!r} offset {offset!r} expected nonnegative",
        )
    end = offset + count * dtype.itemsize
    if end > len(payload):
        raise JoinUnavailable(
            "session.array_descriptor",
            f"{source} array {name!r} ends at {end} beyond {len(payload)} bytes",
        )
    return np.frombuffer(payload, dtype=dtype, count=count, offset=offset)


def _prefix_sum(values: np.ndarray, dtype: np.dtype) -> np.ndarray:
    result = np.empty(len(values) + 1, dtype=dtype)
    result[0] = 0
    np.cumsum(values, dtype=dtype, out=result[1:])
    return result


def _prepare_tape(
    g0_bid_sz: np.ndarray,
    g0_ask_sz: np.ndarray,
    g0_state: np.ndarray,
    g0_upd_count: np.ndarray,
    g0_mid: np.ndarray,
    trades_sec: np.ndarray,
    trades_size: np.ndarray,
    trades_side: np.ndarray,
    identity: Mapping[str, object],
) -> PreparedTape:
    n_seconds = len(g0_state)
    book_lengths = {
        len(g0_bid_sz),
        len(g0_ask_sz),
        len(g0_state),
        len(g0_upd_count),
        len(g0_mid),
    }
    if book_lengths != {n_seconds}:
        raise JoinUnavailable(
            "session.book_lengths",
            f"QRSESS1 book array lengths {sorted(book_lengths)} expected one value",
        )
    trade_lengths = {len(trades_sec), len(trades_size), len(trades_side)}
    if len(trade_lengths) != 1:
        raise JoinUnavailable(
            "session.trade_lengths",
            f"QRSESS1 trade array lengths {sorted(trade_lengths)} expected one value",
        )
    unique_sides = {int(value) for value in np.unique(trades_side)}
    unexpected_sides = unique_sides - ALLOWED_TRADE_SIDES
    if unexpected_sides:
        raise JoinUnavailable(
            "session.trades_side",
            f"QRSESS1 trades_side uniques {sorted(unique_sides)} exceed "
            f"{sorted(ALLOWED_TRADE_SIDES)}",
        )
    seconds = trades_sec.astype(np.int64, copy=False)
    if len(seconds) and (
        int(np.min(seconds)) < 0 or int(np.max(seconds)) >= n_seconds
    ):
        raise JoinUnavailable(
            "session.trades_sec",
            f"QRSESS1 trades_sec range "
            f"{(int(np.min(seconds)), int(np.max(seconds)))} outside "
            f"[0, {n_seconds})",
        )
    signs = np.zeros(len(trades_side), dtype=np.float64)
    signs[trades_side == 66] = 1.0
    signs[trades_side == 65] = -1.0
    if MUTANT == "swap_buy_sell":
        signs *= -1.0
    weights = trades_size.astype(np.float64, copy=False) * signs
    flow = np.bincount(seconds, weights=weights, minlength=n_seconds).astype(
        np.float64, copy=False
    )
    valid = g0_state == 0
    bid = g0_bid_sz.astype(np.float64, copy=False)
    ask = g0_ask_sz.astype(np.float64, copy=False)
    denominator = bid + ask
    bad_book = valid & (
        (denominator <= 0.0) | ~np.isfinite(denominator) | ~np.isfinite(g0_mid)
    )
    if np.any(bad_book):
        first_bad = int(np.flatnonzero(bad_book)[0])
        raise JoinUnavailable(
            "session.valid_book",
            f"QRSESS1 valid book second {first_bad} has denominator "
            f"{denominator[first_bad]!r} and mid {g0_mid[first_bad]!r}",
        )
    imbalance = np.zeros(n_seconds, dtype=np.float64)
    np.divide(bid - ask, denominator, out=imbalance, where=valid)
    indexes = np.arange(n_seconds, dtype=np.int64)
    previous_valid = np.maximum.accumulate(np.where(valid, indexes, -1))
    next_valid = np.minimum.accumulate(
        np.where(valid, indexes, n_seconds)[::-1]
    )[::-1]
    return PreparedTape(
        n_seconds=n_seconds,
        flow_prefix=_prefix_sum(flow, np.dtype(np.float64)),
        imbalance_prefix=_prefix_sum(imbalance, np.dtype(np.float64)),
        valid_count_prefix=_prefix_sum(valid, np.dtype(np.int64)),
        churn_prefix=_prefix_sum(g0_upd_count, np.dtype(np.int64)),
        mid=g0_mid,
        next_valid=next_valid,
        previous_valid=previous_valid,
        identity=identity,
    )


def _read_json_bytes(path: Path) -> tuple[dict[str, object], bytes]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise JoinUnavailable(
            "session.metadata",
            f"cannot read QRSESS1 metadata {path}",
        ) from exc
    if not isinstance(value, dict):
        raise JoinUnavailable(
            "session.metadata",
            f"{path} payload type {type(value).__name__} expected object",
        )
    return value, raw


def _load_session(
    asset: str, d8: int
) -> tuple[PreparedTape | None, Mapping[str, object] | None]:
    metadata_path = SESSION_ROOT / asset / f"{d8}.json"
    bin_path = SESSION_ROOT / asset / f"{d8}.bin"
    if not metadata_path.is_file() or not bin_path.is_file():
        return None, {
            "asset": asset,
            "d8": d8,
            "metadata_path": _relative(metadata_path),
            "metadata_exists": metadata_path.is_file(),
            "bin_path": _relative(bin_path),
            "bin_exists": bin_path.is_file(),
        }
    metadata, metadata_bytes = _read_json_bytes(metadata_path)
    if metadata.get("format") != "QRSESS1":
        raise JoinUnavailable(
            "session.format",
            f"{metadata_path} format {metadata.get('format')!r} expected QRSESS1",
        )
    if metadata.get("bin") != bin_path.name:
        raise JoinUnavailable(
            "session.bin",
            f"{metadata_path} bin {metadata.get('bin')!r} expected {bin_path.name!r}",
        )
    meta = metadata.get("meta")
    if not isinstance(meta, dict):
        raise JoinUnavailable(
            "session.meta",
            f"{metadata_path} meta type {type(meta).__name__} expected object",
        )
    expected_date = f"{d8:08d}"
    expected_date = (
        f"{expected_date[0:4]}-{expected_date[4:6]}-{expected_date[6:8]}"
    )
    if meta.get("asset") != asset:
        raise JoinUnavailable(
            "session.asset",
            f"{metadata_path} session asset {meta.get('asset')!r} expected {asset!r}",
        )
    if meta.get("trade_date") != expected_date:
        raise JoinUnavailable(
            "session.trade_date",
            f"{metadata_path} trade_date {meta.get('trade_date')!r} "
            f"expected {expected_date!r}",
        )
    expected_bytes = _stored_array_bytes(metadata)
    actual_bytes = bin_path.stat().st_size
    if actual_bytes != expected_bytes:
        raise JoinUnavailable(
            "session.bin_bytes",
            f"{bin_path} bytes {actual_bytes} differ from manifest {expected_bytes}",
        )
    try:
        payload = bin_path.read_bytes()
    except OSError as exc:
        raise JoinUnavailable(
            "session.bin",
            f"cannot read QRSESS1 binary {bin_path}",
        ) from exc
    if len(payload) != expected_bytes:
        raise JoinUnavailable(
            "session.bin_bytes",
            f"{bin_path} loaded bytes {len(payload)} differ from manifest {expected_bytes}",
        )
    descriptors = _array_descriptors(metadata, metadata_path)
    arrays = {
        name: _array_view(payload, descriptors[name], bin_path)
        for name in REQUIRED_ARRAYS
    }
    identity = {
        "schema": "QRSESS1IDENTITY1",
        "asset": asset,
        "d8": d8,
        "format": "QRSESS1",
        "trade_date": expected_date,
        "g0_iid": metadata.get("g0_iid"),
        "params_hash": meta.get("params_hash"),
        "metadata_path": _relative(metadata_path),
        "metadata_sha256": hashlib.sha256(metadata_bytes).hexdigest(),
        "bin_path": _relative(bin_path),
        "bin_sha256": hashlib.sha256(payload).hexdigest(),
        "bin_bytes": len(payload),
    }
    tape = _prepare_tape(
        arrays["g0_bid_sz"],
        arrays["g0_ask_sz"],
        arrays["g0_state"],
        arrays["g0_upd_count"],
        arrays["g0_mid"],
        arrays["trades_sec"],
        arrays["trades_size"],
        arrays["trades_side"],
        identity,
    )
    return tape, None


def _score_name(row: TapeName, tape: PreparedTape) -> TapeScore | None:
    end = row.decision_sec
    if MUTANT == "include_decision_second":
        end += 1
    if end > tape.n_seconds:
        raise JoinUnavailable(
            "candidate.window",
            f"candidate {row.candidate_id!r} decision window end {end} exceeds "
            f"session seconds {tape.n_seconds}",
        )
    start = max(0, row.decision_sec - WINDOW_SECONDS)
    if end <= start:
        return None
    flow = float(tape.flow_prefix[end] - tape.flow_prefix[start])
    churn = float(tape.churn_prefix[end] - tape.churn_prefix[start])
    valid_count = int(
        tape.valid_count_prefix[end] - tape.valid_count_prefix[start]
    )
    alignment = 1 if MUTANT == "drop_side_alignment" else row.side
    imbalance: float | None = None
    drift: float | None = None
    if valid_count > 0:
        imbalance = float(
            (tape.imbalance_prefix[end] - tape.imbalance_prefix[start])
            / valid_count
        )
        first = int(tape.next_valid[start])
        last = int(tape.previous_valid[end - 1])
        if first >= end or last < start:
            raise AssertionError(
                f"valid-count index mismatch for candidate {row.candidate_id!r}"
            )
        drift = float(tape.mid[last] - tape.mid[first])
    return TapeScore(
        row=row,
        flow_aligned=float(alignment * flow),
        imbalance_aligned=(
            None if imbalance is None else float(alignment * imbalance)
        ),
        drift_aligned=None if drift is None else float(alignment * drift),
        churn=churn,
    )


def _pick_score(
    rows: Sequence[TapeScore], field: str, want_max: bool
) -> TapeName | None:
    eligible = [row for row in rows if getattr(row, field) is not None]
    if not eligible:
        return None

    def key(row: TapeScore) -> tuple[float, int, str]:
        value = float(getattr(row, field))
        primary = -value if want_max else value
        return primary, -row.row.decision_ts_ns, row.row.candidate_id

    return min(eligible, key=key).row


def _pick_tape_names(
    rows: Sequence[TapeName], tape: PreparedTape | None
) -> RulePicks:
    by_cell: dict[tuple[str, int, int], list[TapeName]] = {}
    for row in rows:
        if row.phase not in PHASES:
            continue
        by_cell.setdefault((row.asset, row.d8, row.phase), []).append(row)
    picked: dict[str, list[TapeName]] = {name: [] for name in RULE_NAMES}
    fallbacks = Counter(
        {
            "fallback_no_valid_book": 0,
            "fallback_empty_window": 0,
            "fallback_no_session": 0,
        }
    )
    for cell in sorted(by_cell):
        ordered = sorted(
            by_cell[cell],
            key=lambda row: (row.decision_ts_ns, row.candidate_id),
        )
        earliest = ordered[0]
        if tape is None:
            for name in RULE_NAMES:
                picked[name].append(earliest)
            fallbacks["fallback_no_session"] += 1
            continue
        scored = tuple(
            score
            for row in ordered
            if (score := _score_name(row, tape)) is not None
        )
        if not scored:
            for name in RULE_NAMES:
                picked[name].append(earliest)
            fallbacks["fallback_empty_window"] += 1
            continue
        missing_book = False
        for name, field, want_max in RULE_SPECS:
            winner = _pick_score(scored, field, want_max)
            if winner is None:
                winner = earliest
                if name in BOOK_RULE_NAMES:
                    missing_book = True
            picked[name].append(winner)
        if missing_book:
            fallbacks["fallback_no_valid_book"] += 1
    return RulePicks(
        causal={name: tuple(picked[name]) for name in RULE_NAMES},
        fallbacks=dict(fallbacks),
    )


def _verified_output(path: Path, receipt: Path) -> str:
    expected = _receipt_output_sha256(receipt)
    actual = _sha256_file(path)
    if actual != expected:
        raise JoinUnavailable(
            "source.output_sha256",
            f"{path} sha256 {actual!r} differs from {receipt} output_sha256 "
            f"{expected!r}",
        )
    return actual


def _score_asset_day(asset: str, day: object) -> DayBundle:
    n_rows, names, candidate_path = _load_tape_names(asset, day.d8)
    if candidate_path is None or n_rows == 0:
        return DayBundle(
            asset,
            day.d8,
            False,
            _empty_picks(),
            (),
            {},
            None,
            None,
            None,
        )
    candidate_receipt = RECEIPTS / asset / f"{day.d8}.candidates.json"
    candidate_sha = _verified_output(candidate_path, candidate_receipt)
    source_identity: dict[str, object] = {
        "asset": asset,
        "d8": day.d8,
        "candidates": {
            "path": _relative(candidate_path),
            "receipt": _relative(candidate_receipt),
            "sha256": candidate_sha,
        },
    }
    if not names:
        return DayBundle(
            asset,
            day.d8,
            True,
            _empty_picks(),
            (),
            {},
            source_identity,
            None,
            None,
        )
    wanted = [row.candidate_id for row in names]
    teacher, teacher_path = _load_teacher(asset, day.d8, wanted)
    teacher_receipt = RECEIPTS / asset / f"{day.d8}.teacher.json"
    teacher_sha = _verified_output(teacher_path, teacher_receipt)
    source_identity["teacher"] = {
        "path": _relative(teacher_path),
        "receipt": _relative(teacher_receipt),
        "sha256": teacher_sha,
    }
    tape, missing_session = _load_session(asset, day.d8)
    selected = _pick_tape_names(names, tape)
    relative_candidates = _relative(candidate_path)
    relative_teacher = _relative(teacher_path)
    picks = {
        name: _join_picked(
            selected.causal[name],
            teacher,
            relative_candidates,
            relative_teacher,
            candidate_sha,
            teacher_sha,
        )
        for name in RULE_NAMES
    }
    unique_picks = {
        row.candidate_id: row
        for line_picks in selected.causal.values()
        for row in line_picks
    }
    ready = _ready_rows(
        tuple(unique_picks[key] for key in sorted(unique_picks)),
        teacher,
        relative_teacher,
    )
    envelope = _as_selected(
        enter_positive(pick_cell_best_ready(ready)),
        relative_candidates,
        relative_teacher,
        candidate_sha,
        teacher_sha,
    )
    return DayBundle(
        asset=asset,
        d8=day.d8,
        joinable=True,
        picks=picks,
        envelope=envelope,
        fallbacks=selected.fallbacks,
        source_identity=source_identity,
        session_identity=None if tape is None else tape.identity,
        missing_session=missing_session,
    )


def _score_job(item: tuple[str, object]) -> DayBundle:
    return _score_asset_day(*item)


def _gated_line(bundles: Sequence[DayBundle], name: str) -> Line:
    days = {asset: 0 for asset in ASSETS}
    entries: list[object] = []
    for bundle in bundles:
        if not bundle.joinable:
            continue
        days[bundle.asset] += 1
        if name == "envelope_tape8":
            entries.extend(bundle.envelope)
        else:
            entries.extend(bundle.picks[name])
    return summarize_line(entries, days)


def _line_reaches_stop(line: Line) -> bool:
    return (
        line.trades > 0
        and line.clears_rungs
        and line.max_drawdown_usd < DRAWDOWN_LIMIT_USD
        and line.entry_cap_ok
        and line.overlap_violations == 0
    )


def _line_dict(line: Line) -> dict[str, object]:
    value = line.as_dict()
    value["clears_stop"] = _line_reaches_stop(line)
    return value


def dollar_stop(
    lines: Mapping[str, Line], envelope: Line
) -> dict[str, object]:
    hits = [name for name in RULE_NAMES if _line_reaches_stop(lines[name])]
    verdict = "RUNGS" if hits else "KILL"
    envelope_clears = _line_reaches_stop(envelope)
    if hits:
        applied = f"RUNGS fired for causal lines {hits}."
    elif envelope_clears:
        applied = (
            "KILL fired because all eight causal lines miss. envelope_tape8 "
            "clears, so identity in this tape family is mixture-shaped."
        )
    else:
        applied = (
            "KILL fired because all eight causal lines miss. envelope_tape8 "
            "also misses, so the unfitted single-feature tape family is closed."
        )
    return {
        "verdict": verdict,
        "causal_lines_clearing": hits,
        "envelope_tape8_clears": envelope_clears,
        "rungs_usd": dict(RUNGS_USD),
        "drawdown_limit_usd": DRAWDOWN_LIMIT_USD,
        "entry_cap": ENTRY_CAP,
        "required_trades_min": 1,
        "required_overlap_violations": 0,
        "applied": applied,
    }


def _bound_stop_text() -> str:
    text = COVERING_BRIEF.read_text()
    start_marker = "## Dollar stop. Bound now, fires on the receipt."
    end_marker = "\nForbidden inside this unit:"
    start = text.find(start_marker)
    end = text.find(end_marker, start)
    if start < 0 or end < 0:
        raise JoinUnavailable(
            "covering_stop",
            f"{COVERING_BRIEF} lacks bound stop markers {start!r}, {end!r}",
        )
    return text[start:end].strip()


def _source_file(path: Path) -> dict[str, object]:
    return {"path": _relative(path), "sha256": _sha256_file(path)}


def _cited_stored_name_receipt() -> dict[str, object]:
    payload = _killed._read_json(STORED_NAME_RECEIPT)
    expected = "QRE2THRESHOLDSTOREDNAMERULES1"
    if payload.get("schema") != expected:
        raise JoinUnavailable(
            "stored_name_receipt.schema",
            f"{STORED_NAME_RECEIPT} schema {payload.get('schema')!r} "
            f"expected {expected}",
        )
    return {
        **_source_file(STORED_NAME_RECEIPT),
        "schema": payload.get("schema"),
        "verdict": payload.get("verdict"),
    }


def _aggregate_fallbacks(
    bundles: Sequence[DayBundle],
) -> dict[str, object]:
    total = Counter(
        {
            "fallback_no_valid_book": 0,
            "fallback_empty_window": 0,
            "fallback_no_session": 0,
        }
    )
    by_asset = {
        asset: Counter(
            {
                "fallback_no_valid_book": 0,
                "fallback_empty_window": 0,
                "fallback_no_session": 0,
            }
        )
        for asset in ASSETS
    }
    for bundle in bundles:
        total.update(bundle.fallbacks)
        by_asset[bundle.asset].update(bundle.fallbacks)
    return {
        "total": dict(total),
        "by_asset": {asset: dict(by_asset[asset]) for asset in ASSETS},
    }


def build_receipt(wall_clock_sec: float) -> dict[str, object]:
    if MUTANT:
        raise JoinUnavailable(
            "mutant",
            f"era run refuses QRE2_TAPE_MUTANT={MUTANT!r}",
        )
    if tuple(TEACHER_COLS) != (
        "candidate_id",
        "status",
        "cert_close_usd",
        "exit_ts_ns",
    ):
        raise JoinUnavailable(
            "teacher.usecols",
            f"teacher usecols {TEACHER_COLS!r} changed from the frozen four columns",
        )
    if any(name in TAPE_CANDIDATE_COLS for name in PEEK_COLS):
        raise JoinUnavailable(
            "candidates.usecols",
            "tape-name candidate usecols include peek columns",
        )
    if any(name in TEACHER_COLS for name in PEEK_COLS):
        raise JoinUnavailable(
            "teacher.usecols",
            "tape-name teacher usecols include peek columns",
        )
    forecast_rows, _window_days, n_read = load_window_forecast_rows(FORECAST)
    routed, _empty = route_catboost_daily(forecast_rows)
    selected_flags = select_expanding_median(routed)
    selected_days = tuple(
        day for day, flag in zip(routed, selected_flags) if flag
    )
    jobs = [(asset, day) for day in selected_days for asset in ASSETS]
    bundles: list[DayBundle] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for bundle in pool.map(_score_job, jobs):
            bundles.append(bundle)
    lines = {name: _gated_line(bundles, name) for name in RULE_NAMES}
    envelope = _gated_line(bundles, "envelope_tape8")
    days = lines[RULE_NAMES[0]].days
    if days != EXPECTED_GATED_DAYS:
        raise JoinUnavailable(
            "gated.days",
            f"tape-name days {days} != {EXPECTED_GATED_DAYS}",
        )
    if any(line.days != EXPECTED_GATED_DAYS for line in lines.values()):
        raise JoinUnavailable(
            "gated.days",
            "tape-name causal lines disagree on gated denominators",
        )
    if envelope.days != EXPECTED_GATED_DAYS:
        raise JoinUnavailable(
            "envelope_tape8.days",
            f"envelope days {envelope.days} != {EXPECTED_GATED_DAYS}",
        )
    stop = dollar_stop(lines, envelope)
    stop["verbatim"] = _bound_stop_text()
    verdict = str(stop["verdict"])
    session_identities = sorted(
        (
            dict(bundle.session_identity)
            for bundle in bundles
            if bundle.session_identity is not None
        ),
        key=lambda value: (str(value["asset"]), int(value["d8"])),
    )
    missing_sessions = sorted(
        (
            dict(bundle.missing_session)
            for bundle in bundles
            if bundle.missing_session is not None
        ),
        key=lambda value: (str(value["asset"]), int(value["d8"])),
    )
    joined_sources = sorted(
        (
            dict(bundle.source_identity)
            for bundle in bundles
            if bundle.source_identity is not None
        ),
        key=lambda value: (str(value["asset"]), int(value["d8"])),
    )
    return {
        "schema": SCHEMA,
        "status": verdict,
        "verdict": verdict,
        "label": LABEL,
        "window": [WINDOW_START, WINDOW_END],
        "tape_window": {
            "seconds": WINDOW_SECONDS,
            "bounds": "[max(0, decision_sec - 180), decision_sec - 1]",
            "decision_second_included": False,
        },
        "rule": RULE,
        "rules": dict(RULES),
        "causal_lines": list(RULE_NAMES),
        "peek_note": PEEK_NOTE,
        "candidate_columns": list(TAPE_CANDIDATE_COLS),
        "teacher_columns": list(TEACHER_COLS),
        "session_arrays": list(REQUIRED_ARRAYS),
        "check_command": CHECK,
        "lines": {name: _line_dict(line) for name, line in lines.items()},
        "envelope_tape8": _line_dict(envelope),
        "fallback_counts": _aggregate_fallbacks(bundles),
        "dollar_stop": stop,
        "n_forecast_rows_read": n_read,
        "routed": len(routed),
        "selected": len(selected_days),
        "workers": WORKERS,
        "wall_clock_sec": wall_clock_sec,
        "verification_commands": {
            "selftest": f"{CHECK} --selftest",
            "mutants": [
                f"QRE2_TAPE_MUTANT={name} {CHECK} --selftest"
                for name in MUTANTS
            ],
        },
        "sources": {
            "script": _source_file(Path(__file__)),
            "forecasts": _source_file(FORECAST),
            "freeze": _source_file(FREEZE),
            "killed_read": _source_file(KILLED_READ),
            "full_roster_ceiling": _stored._cited_full_roster_ceiling(),
            "stored_name_rules": _cited_stored_name_receipt(),
            "covering_brief": _source_file(COVERING_BRIEF),
            "specification_brief": _source_file(SPECIFICATION_BRIEF),
            "sibling_loaders": {
                "stored_name_rules": _source_file(STORED_NAME_SCRIPT),
                "live_scalars": _source_file(LIVE_SCALARS_SCRIPT),
                "ticket45_qrsess1": _source_file(TICKET45_SCRIPT),
            },
            "candidates_root": _relative(CANDIDATES),
            "teacher_root": _relative(TEACHERS),
            "receipts_root": _relative(RECEIPTS),
            "sessions_root": _relative(SESSION_ROOT),
            "joined_artifacts": joined_sources,
            "qrsess1_identities": session_identities,
            "qrsess1_missing": missing_sessions,
        },
    }


def _write_receipt(value: Mapping[str, object]) -> None:
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    temporary = RECEIPT.with_name(f"{RECEIPT.name}.tmp.{os.getpid()}")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, RECEIPT)


def _fixture_name(
    candidate_id: str,
    decision_ts_ns: int,
    decision_sec: int,
    side: int,
    phase: int = 0,
) -> TapeName:
    return TapeName(
        candidate_id=candidate_id,
        asset="HG",
        d8=20220314,
        phase=phase,
        decision_ts_ns=decision_ts_ns,
        decision_sec=decision_sec,
        side=side,
        frozen_cost_usd=5.0,
    )


def _synthetic_tape(state: np.ndarray | None = None) -> PreparedTape:
    return _prepare_tape(
        g0_bid_sz=np.asarray([3, 3, 3, 3, 3, 3], dtype=np.int64),
        g0_ask_sz=np.asarray([1, 1, 1, 1, 1, 1], dtype=np.int64),
        g0_state=(
            np.zeros(6, dtype=np.int8)
            if state is None
            else np.asarray(state, dtype=np.int8)
        ),
        g0_upd_count=np.asarray([1, 1, 1, 100, 1, 1], dtype=np.int32),
        g0_mid=np.asarray([1, 2, 3, 50, 51, 52], dtype=np.float64),
        trades_sec=np.asarray([0, 1, 2], dtype=np.int64),
        trades_size=np.asarray([5, 2, 100], dtype=np.int64),
        trades_side=np.asarray([66, 65, 78], dtype=np.uint8),
        identity={},
    )


def _selftest() -> int:
    if MUTANT not in ("", *MUTANTS):
        raise AssertionError(f"selftest unknown mutant {MUTANT!r}")
    if len(RULE_NAMES) != 8:
        raise AssertionError(f"selftest causal line count {len(RULE_NAMES)} != 8")
    if tuple(TEACHER_COLS) != (
        "candidate_id",
        "status",
        "cert_close_usd",
        "exit_ts_ns",
    ):
        raise AssertionError(f"selftest teacher columns {TEACHER_COLS!r}")
    if any(name in TAPE_CANDIDATE_COLS for name in PEEK_COLS):
        raise AssertionError("selftest candidate usecols parse peek columns")
    if any(name in TEACHER_COLS for name in PEEK_COLS):
        raise AssertionError("selftest teacher usecols parse peek columns")
    metadata = {
        "arrays": [
            {"name": "a", "dtype": "int64", "count": 2, "offset": 0},
            {"name": "b", "dtype": "uint8", "count": 3, "offset": 16},
        ]
    }
    if _stored_array_bytes(metadata) != 19:
        raise AssertionError("selftest QRSESS1 stored byte count")
    tape = _synthetic_tape()
    window_score = _score_name(_fixture_name("window", 10, 3, 1), tape)
    if window_score is None or window_score.churn != 3.0:
        raise AssertionError(
            f"selftest decision-second exclusion churn "
            f"{None if window_score is None else window_score.churn!r} != 3.0"
        )
    aligned_score = _score_name(_fixture_name("aligned", 20, 3, -1), tape)
    if aligned_score is None or aligned_score.imbalance_aligned != -0.5:
        raise AssertionError(
            f"selftest side alignment "
            f"{None if aligned_score is None else aligned_score.imbalance_aligned!r} "
            "!= -0.5"
        )
    flow_score = _score_name(_fixture_name("flow", 30, 3, 1), tape)
    if flow_score is None or flow_score.flow_aligned != 3.0:
        raise AssertionError(
            f"selftest signed flow "
            f"{None if flow_score is None else flow_score.flow_aligned!r} != 3.0"
        )
    earlier = _fixture_name("a", 10, 3, 1)
    later_b = _fixture_name("b", 20, 3, 1)
    later_a = _fixture_name("a", 20, 3, 1)
    tied_scores = (
        TapeScore(earlier, 7.0, 0.0, 0.0, 4.0),
        TapeScore(later_b, 7.0, 0.0, 0.0, 4.0),
        TapeScore(later_a, 7.0, 0.0, 0.0, 4.0),
    )
    tie_pick = _pick_score(tied_scores, "flow_aligned", True)
    if tie_pick != later_a:
        raise AssertionError(f"selftest tie chain picked {tie_pick!r}")
    no_session = _pick_tape_names((earlier, later_b), None)
    if no_session.fallbacks["fallback_no_session"] != 1:
        raise AssertionError(f"selftest no-session fallback {no_session.fallbacks}")
    empty_window = _pick_tape_names(
        (_fixture_name("empty", 1, 0, 1),), tape
    )
    if empty_window.fallbacks["fallback_empty_window"] != 1:
        raise AssertionError(
            f"selftest empty-window fallback {empty_window.fallbacks}"
        )
    no_book_tape = _synthetic_tape(np.ones(6, dtype=np.int8))
    no_book = _pick_tape_names((earlier, later_b), no_book_tape)
    if no_book.fallbacks["fallback_no_valid_book"] != 1:
        raise AssertionError(f"selftest no-book fallback {no_book.fallbacks}")
    empty_line = summarize_line((), {"HG": 1, "NKD": 1, "SI": 1})
    miss_lines = {name: empty_line for name in RULE_NAMES}
    killed = dollar_stop(miss_lines, empty_line)
    if killed["verdict"] != "KILL" or killed["causal_lines_clearing"]:
        raise AssertionError(f"selftest KILL {killed}")
    clear_line = summarize_line(
        (
            SelectedName(
                "hg", "HG", 20220314, 0, 10, 5.0, 2000.0, 20, True, "", None, "", None
            ),
            SelectedName(
                "nkd", "NKD", 20220314, 0, 11, 5.0, 1500.0, 21, True, "", None, "", None
            ),
            SelectedName(
                "si", "SI", 20220314, 0, 12, 5.0, 1500.0, 22, True, "", None, "", None
            ),
        ),
        {"HG": 1, "NKD": 1, "SI": 1},
    )
    hit_lines = {name: empty_line for name in RULE_NAMES}
    hit_lines["tape_flow_with"] = clear_line
    hit = dollar_stop(hit_lines, empty_line)
    if hit["verdict"] != "RUNGS" or hit["causal_lines_clearing"] != [
        "tape_flow_with"
    ]:
        raise AssertionError(f"selftest RUNGS {hit}")
    print("selftest_ok zero_era_bytes=1")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if "--selftest" in args:
        if args != ["--selftest"]:
            raise ValueError(f"--selftest must be the only argument, got {args}")
        return _selftest()
    if args:
        raise ValueError(f"unsupported arguments {args}")
    started = time.perf_counter()
    receipt = build_receipt(0.0)
    receipt["wall_clock_sec"] = round(time.perf_counter() - started, 3)
    _write_receipt(receipt)
    usd = {
        name: receipt["lines"][name]["usd_per_asset_day"] for name in RULE_NAMES
    }
    print(
        f"receipt={_relative(RECEIPT)} verdict={receipt['verdict']} "
        f"causal_lines_clearing={receipt['dollar_stop']['causal_lines_clearing']} "
        f"usd_per_asset_day={usd}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
