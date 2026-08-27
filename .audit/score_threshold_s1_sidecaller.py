#!/usr/bin/env python3
"""Score the frozen S1 walk-forward side caller and causal turn rule."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Literal, Mapping, Sequence, cast

import numpy as np

REPO = Path(__file__).resolve().parents[1]
RECEIPT = REPO / ".audit/threshold-s1-sidecaller.json"
BRIEF = REPO / ".audit/briefs/threshold-s1-after-s0-fable-out.md"
SIDE_SPLIT_SCRIPT = REPO / ".audit/score_threshold_side_split.py"
SIDE_SPLIT_RECEIPT = REPO / ".audit/threshold-side-split.json"
CEILING_SCRIPT = REPO / ".audit/score_threshold_2022_2024_ceiling.py"
CEILING_RECEIPT = REPO / ".audit/threshold-2022-2024-ceiling.json"
READ_SCRIPT = REPO / ".audit/score_threshold_2022_2024_read.py"
CHECK = "python3 .audit/score_threshold_s1_sidecaller.py"
SCHEMA = "QRE2THRESHOLDS1SIDECALLER1"
WORKERS = 14
TRIPWIRE_SECONDS = 7200.0
PREFIX_ROWS = 8
MIN_TRAIN = 50
L2_LAMBDA = 1.0
IRLS_ITERATIONS = 100
CALL_THRESHOLD = 0.5
SIGMA_FLOOR = 1e-9
MUTANT = os.environ.get("QRE2_S1SIDECALLER_MUTANT", "")
MUTANTS = (
    "same_day_train_leak",
    "teacher_bytes_in_features",
    "prefix_row_entered",
    "record_row_reentered",
    "wrong_side_entry_accepted",
    "pstar_eff_arithmetic_drift",
    "train_order_dependence",
)
GUARD_MUTANT = "corrupt_candidate_id_accepted"
KNOWN_MUTANTS = frozenset((*MUTANTS, GUARD_MUTANT))
FEATURE_NAMES = (
    "drift",
    "range",
    "range_pos",
    "flow",
    "first_side",
    "last_side",
    "dur",
    "phase_0",
    "phase_1",
    "phase_2",
)
LINE_NAMES = (
    "cellbest_control",
    "sideoracle_price_control",
    "turncap_oracle_side",
    "turncap_wrong_side",
    "recordcap_oracle_side",
    "recordcap_wrong_side",
    "policy_walkforward",
)
LINE_LABELS = {
    "cellbest_control": "frozen cell-best ceiling control",
    "sideoracle_price_control": "frozen S0 oracle-side price control",
    "turncap_oracle_side": "sigma-star side with the frozen turn rule",
    "turncap_wrong_side": "opposite sigma-star side with the frozen turn rule",
    "recordcap_oracle_side": "sigma-star side with the reported record rule",
    "recordcap_wrong_side": "opposite sigma-star side with the reported record rule",
    "policy_walkforward": "walk-forward side call with the frozen turn rule",
}
LABEL = (
    "Fitted causal S1 side caller against the frozen k=8 turn rule. "
    "Teacher cash can kill and cannot promote."
)
RULE = (
    "Fit one deterministic ridge-logistic IRLS model per asset-day from strictly "
    "prior labeled cells, call a side from the first eight CLEAR rows, and enter "
    "the first called-side row after arming that fails to improve the running "
    "side-relative record."
)
KILL_VERBATIM = (
    "On the locked gated denominators, the turn cap or policy misses a rung, "
    "breaches max_drawdown_usd 1000, breaks the entry cap or overlap law, an "
    "asset accuracy misses its pinned S0 price-pair floor, or W_turn is not "
    "strictly greater than L_turn. The fitted causal side-caller family closes "
    "at age 180. B0 is named and does not start inside S1."
)
LIVE_VERBATIM = (
    "The walk-forward policy clears all three rungs on the locked gated "
    "denominators with max_drawdown_usd at most 1000 and clean caps, every "
    "asset accuracy meets its pinned floor, and W_turn is strictly greater "
    "than L_turn. S2 is named and does not start inside S1."
)

CellKey = tuple[str, int, int]
PickerState = Literal["short_prefix", "never_armed", "armed_no_entry", "entered", "no_record_entry"]


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_s0 = _load_module(SIDE_SPLIT_SCRIPT, "threshold_s1_side_split")
_read = _s0._read
_ceiling = _s0._ceiling
JoinUnavailable = _s0.JoinUnavailable
ASSETS = cast(tuple[str, ...], _s0.ASSETS)
PHASES = cast(tuple[int, ...], _s0.PHASES)
RUNGS_USD = cast(Mapping[str, float], _s0.RUNGS_USD)
ENTRY_CAP = int(_s0.ENTRY_CAP)
PEEK_COLS = cast(tuple[str, ...], _s0.PEEK_COLS)
FORECAST = cast(Path, _s0.FORECAST)
CANDIDATES = cast(Path, _s0.CANDIDATES)
TEACHERS = cast(Path, _s0.TEACHERS)
SOURCE_RECEIPTS = cast(Path, _s0.SOURCE_RECEIPTS)
WINDOW_START = str(_s0.WINDOW_START)
WINDOW_END = str(_s0.WINDOW_END)
EXPECTED_GATED_DAYS = cast(Mapping[str, int], _s0.EXPECTED_GATED_DAYS)
CandidateOutcome = _s0.CandidateOutcome
SourceDay = _s0.SourceDay
SelectedName = _s0.SelectedName
summarize_line = _s0.summarize_line


@dataclass(frozen=True, slots=True)
class CellRecord:
    asset: str
    d8: int
    phase: int
    selected: bool
    stream: tuple[object, ...]
    source: object
    s0_score: object
    features: np.ndarray | None
    sigma_star: int | None

    @property
    def key(self) -> CellKey:
        return (self.asset, self.d8, self.phase)


@dataclass(frozen=True, slots=True)
class ModelCell:
    asset: str
    d8: int
    phase: int
    candidate_id: str
    features: np.ndarray | None
    sigma_star: int | None

    @property
    def key(self) -> CellKey:
        return (self.asset, self.d8, self.phase)


@dataclass(frozen=True, slots=True)
class DayRecord:
    asset: str
    d8: int
    joinable: bool
    selected: bool
    cells: tuple[CellRecord, ...]
    source: object
    s0_day: object


@dataclass(frozen=True, slots=True)
class LogisticFit:
    asset: str
    d8: int
    beta: np.ndarray
    mean: np.ndarray
    sigma: np.ndarray
    train_size: int


@dataclass(frozen=True, slots=True)
class PickerResult:
    selected: object | None
    state: PickerState


@dataclass(frozen=True, slots=True)
class PolicySelection:
    cell: CellRecord
    selected: object
    call_side: int


def _relative(path: Path) -> str:
    return str(_s0._relative(path))


def _sha256_file(path: Path) -> str:
    return str(_s0._sha256_file(path))


def _source_file(path: Path) -> dict[str, str]:
    return {"path": _relative(path), "sha256": _sha256_file(path)}


def _read_json(path: Path) -> dict[str, object]:
    return cast(dict[str, object], _s0._read_json(path))


def _verify_file_sha(path: Path, expected: str, label: str) -> None:
    actual = _sha256_file(path)
    if actual != expected and MUTANT != GUARD_MUTANT:
        raise JoinUnavailable(label, f"{path} sha256 {actual!r} expected {expected!r}")


def _canonical_sha(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _stable_probability(values: np.ndarray) -> np.ndarray:
    positive = values >= 0.0
    result = np.empty_like(values, dtype=np.float64)
    result[positive] = 1.0 / (1.0 + np.exp(-values[positive]))
    exponent = np.exp(values[~positive])
    result[~positive] = exponent / (1.0 + exponent)
    return result


def _side_improves(side: int, mid: int, record: int) -> bool:
    return side * mid < side * record


def _sigma_star(score: object) -> int | None:
    if not bool(score.has_ready):
        return None
    selected = score.lines["sideoracle_price"].selected
    if selected is None:
        raise AssertionError("S0 oracle-side price line lacks a sigma-star row")
    return int(selected.candidate.side)


def _prefix_features(rows: Sequence[object], phase: int) -> np.ndarray | None:
    if len(rows) < PREFIX_ROWS:
        return None
    prefix = rows[:PREFIX_ROWS]
    mids = np.asarray([int(row.candidate.entry_mid2) for row in prefix], dtype=np.float64)
    sides = np.asarray([int(row.candidate.side) for row in prefix], dtype=np.float64)
    timestamps = np.asarray(
        [int(row.candidate.decision_ts_ns) for row in prefix], dtype=np.int64
    )
    width = float(np.max(mids) - np.min(mids))
    values = np.asarray(
        [
            float(mids[-1] - mids[0]),
            width,
            float((mids[-1] - np.min(mids)) / (width + 1e-9)),
            float(np.sum(sides) / PREFIX_ROWS),
            float(sides[0]),
            float(sides[-1]),
            float(np.log1p((timestamps[-1] - timestamps[0]) / 1e9)),
            float(phase == 0),
            float(phase == 1),
            float(phase == 2),
        ],
        dtype=np.float64,
    )
    if MUTANT == "teacher_bytes_in_features":
        values[0] += sum(float(row.cert_close_usd) for row in prefix)
    return values


def _pick_turn(rows: Sequence[object], side: int) -> PickerResult:
    if len(rows) < PREFIX_ROWS + 1:
        return PickerResult(None, "short_prefix")
    if MUTANT == "prefix_row_entered":
        for row in rows[:PREFIX_ROWS]:
            if int(row.candidate.side) == side:
                return PickerResult(row, "entered")
    prefix = rows[:PREFIX_ROWS]
    record = min((int(row.candidate.entry_mid2) for row in prefix), key=lambda mid: side * mid)
    armed = False
    for row in rows[PREFIX_ROWS:]:
        mid = int(row.candidate.entry_mid2)
        improves = _side_improves(side, mid, record)
        if improves:
            record = mid
            if not armed:
                armed = True
            if MUTANT == "record_row_reentered" and int(row.candidate.side) == side:
                return PickerResult(row, "entered")
            continue
        if armed and (
            int(row.candidate.side) == side
            or MUTANT == "wrong_side_entry_accepted"
        ):
            return PickerResult(row, "entered")
    return PickerResult(None, "armed_no_entry" if armed else "never_armed")


def _pick_record(rows: Sequence[object], side: int) -> PickerResult:
    if len(rows) < PREFIX_ROWS + 1:
        return PickerResult(None, "short_prefix")
    prefix = rows[:PREFIX_ROWS]
    record = min((int(row.candidate.entry_mid2) for row in prefix), key=lambda mid: side * mid)
    for row in rows[PREFIX_ROWS:]:
        mid = int(row.candidate.entry_mid2)
        if not _side_improves(side, mid, record):
            continue
        record = mid
        if int(row.candidate.side) == side:
            return PickerResult(row, "entered")
    return PickerResult(None, "no_record_entry")


def _standardize_training(features: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = np.mean(features, axis=0, dtype=np.float64)
    raw_sigma = np.std(features, axis=0, ddof=0, dtype=np.float64)
    sigma = np.maximum(raw_sigma, SIGMA_FLOOR)
    return (features - mean) / sigma, mean, sigma


def _fit_irls(features: np.ndarray, labels: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    standardized, mean, sigma = _standardize_training(features)
    design = np.column_stack(
        (np.ones(standardized.shape[0], dtype=np.float64), standardized)
    )
    penalty = np.diag(
        np.asarray([0.0, *([L2_LAMBDA] * standardized.shape[1])], dtype=np.float64)
    )
    beta = np.zeros(design.shape[1], dtype=np.float64)
    for _ in range(IRLS_ITERATIONS):
        probability = _stable_probability(design @ beta)
        weighted_probability = np.clip(probability, 1e-12, 1.0 - 1e-12)
        weight = weighted_probability * (1.0 - weighted_probability)
        hessian = design.T @ (weight[:, None] * design) + penalty
        gradient = design.T @ (labels - probability) - penalty @ beta
        beta += np.linalg.solve(hessian, gradient)
    return beta, mean, sigma


def _predict_long(fit: LogisticFit, features: np.ndarray) -> tuple[int, float]:
    standardized = (features - fit.mean) / fit.sigma
    design = np.concatenate((np.ones(1, dtype=np.float64), standardized))
    probability = float(_stable_probability(np.asarray([design @ fit.beta]))[0])
    return (1 if probability >= CALL_THRESHOLD else -1), probability


def _model_sort_key(cell: ModelCell) -> tuple[str, int, int, str]:
    return (cell.asset, cell.d8, cell.phase, cell.candidate_id)


def _fit_asset_walkforward(
    asset: str,
    cells: Sequence[ModelCell],
    parallel: bool,
) -> tuple[dict[CellKey, int], tuple[LogisticFit, ...], frozenset[int]]:
    ordered = list(cells)
    if MUTANT != "train_order_dependence":
        ordered.sort(key=_model_sort_key)
    days = list(dict.fromkeys(cell.d8 for cell in ordered if cell.asset == asset))
    if MUTANT != "train_order_dependence":
        days.sort()
    labeled = tuple(
        cell
        for cell in ordered
        if cell.asset == asset and cell.features is not None and cell.sigma_star is not None
    )
    current_by_day = {
        day: tuple(
            cell
            for cell in ordered
            if cell.asset == asset and cell.d8 == day and cell.features is not None
        )
        for day in days
    }

    def fit_day(day: int) -> tuple[int, LogisticFit | None, tuple[tuple[CellKey, int], ...]]:
        training = tuple(
            cell
            for cell in labeled
            if cell.d8 < day
            or (MUTANT == "same_day_train_leak" and cell.d8 == day)
        )
        classes = {cell.sigma_star for cell in training}
        if len(training) < MIN_TRAIN or classes != {-1, 1}:
            return day, None, ()
        matrix = np.vstack([cast(np.ndarray, cell.features) for cell in training])
        labels = np.asarray(
            [1.0 if cell.sigma_star == 1 else 0.0 for cell in training],
            dtype=np.float64,
        )
        beta, mean, sigma = _fit_irls(matrix, labels)
        fit = LogisticFit(asset, day, beta, mean, sigma, len(training))
        calls = tuple(
            (cell.key, _predict_long(fit, cast(np.ndarray, cell.features))[0])
            for cell in current_by_day[day]
        )
        return day, fit, calls

    if parallel and len(days) > 1:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            results = tuple(pool.map(fit_day, days))
    else:
        results = tuple(fit_day(day) for day in days)
    calls: dict[CellKey, int] = {}
    fits: list[LogisticFit] = []
    untrained: set[int] = set()
    for day, fit, day_calls in results:
        if fit is None:
            untrained.add(day)
            continue
        fits.append(fit)
        calls.update(day_calls)
    return calls, tuple(fits), frozenset(untrained)


def _fit_digest(fits: Sequence[LogisticFit]) -> str:
    ordered = list(fits)
    if MUTANT != "train_order_dependence":
        ordered.sort(key=lambda fit: (fit.asset, fit.d8))
    digest = hashlib.sha256()
    for fit in ordered:
        digest.update(np.asarray(fit.beta, dtype="<f8").tobytes(order="C"))
    return digest.hexdigest()


def _load_day(asset: str, day: object, selected: bool) -> DayRecord:
    d8 = int(day.d8)
    joinable, candidates, source = _s0._load_side_candidates(asset, d8)
    if not joinable:
        s0_day = _s0.DayScore(asset, d8, False, selected, (), source)
        return DayRecord(asset, d8, False, selected, (), source, s0_day)
    outcomes, source = _s0._load_outcomes(asset, d8, candidates, source)
    by_phase: dict[int, list[object]] = {phase: [] for phase in PHASES}
    for row in outcomes:
        if int(row.candidate.phase) in by_phase:
            by_phase[int(row.candidate.phase)].append(row)
    cells: list[CellRecord] = []
    s0_cells: list[object] = []
    for phase in PHASES:
        stream = tuple(
            sorted(
                by_phase[phase],
                key=lambda row: (
                    int(row.candidate.decision_ts_ns),
                    str(row.candidate.candidate_id),
                ),
            )
        )
        s0_score = _s0._score_cell(stream)
        s0_cells.append(s0_score)
        cells.append(
            CellRecord(
                asset=asset,
                d8=d8,
                phase=phase,
                selected=selected,
                stream=stream,
                source=source,
                s0_score=s0_score,
                features=_prefix_features(stream, phase),
                sigma_star=_sigma_star(s0_score),
            )
        )
    s0_day = _s0.DayScore(asset, d8, True, selected, tuple(s0_cells), source)
    return DayRecord(asset, d8, True, selected, tuple(cells), source, s0_day)


def _load_jobs(jobs: Sequence[tuple[str, object, bool]]) -> tuple[DayRecord, ...]:
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        return tuple(pool.map(lambda item: _load_day(*item), jobs))


def _model_cells(days: Sequence[DayRecord]) -> tuple[ModelCell, ...]:
    result: list[ModelCell] = []
    for day in days:
        for cell in day.cells:
            anchor = min(
                (str(row.candidate.candidate_id) for row in cell.stream),
                default="",
            )
            result.append(
                ModelCell(
                    cell.asset,
                    cell.d8,
                    cell.phase,
                    anchor,
                    cell.features,
                    cell.sigma_star,
                )
            )
    return tuple(result)


def _days_for_scope(days: Sequence[DayRecord], gated: bool) -> dict[str, int]:
    result = {asset: 0 for asset in ASSETS}
    for day in days:
        if day.joinable and (not gated or day.selected):
            result[day.asset] += 1
    return result


def _select_lines(
    cells: Sequence[CellRecord],
    calls: Mapping[CellKey, int],
) -> tuple[
    dict[str, dict[CellKey, object]],
    dict[tuple[str, CellKey], PickerState],
    dict[CellKey, PolicySelection],
]:
    selections: dict[str, dict[CellKey, object]] = {
        name: {} for name in LINE_NAMES[2:]
    }
    states: dict[tuple[str, CellKey], PickerState] = {}
    policy: dict[CellKey, PolicySelection] = {}
    for cell in cells:
        if cell.sigma_star is not None:
            for name, side, picker in (
                ("turncap_oracle_side", cell.sigma_star, _pick_turn),
                ("turncap_wrong_side", -cell.sigma_star, _pick_turn),
                ("recordcap_oracle_side", cell.sigma_star, _pick_record),
                ("recordcap_wrong_side", -cell.sigma_star, _pick_record),
            ):
                picked = picker(cell.stream, side)
                states[(name, cell.key)] = picked.state
                if picked.selected is not None:
                    selections[name][cell.key] = picked.selected
        call = calls.get(cell.key)
        if call is None:
            continue
        picked = _pick_turn(cell.stream, call)
        states[("policy_walkforward", cell.key)] = picked.state
        if picked.selected is not None:
            selections["policy_walkforward"][cell.key] = picked.selected
            policy[cell.key] = PolicySelection(cell, picked.selected, call)
    return selections, states, policy


def _selected_name(cell: CellRecord, outcome: object) -> object:
    return _s0._selected_name(outcome, cell.source)


def _new_line_scope(
    days: Sequence[DayRecord],
    cells: Sequence[CellRecord],
    selected: Mapping[CellKey, object],
    gated: bool,
) -> dict[str, object]:
    scoped_cells = {
        cell.key: cell for cell in cells if not gated or cell.selected
    }
    entries = [
        _selected_name(scoped_cells[key], outcome)
        for key, outcome in selected.items()
        if key in scoped_cells
    ]
    value = summarize_line(entries, _days_for_scope(days, gated)).as_dict()
    value["selected_not_ready"] = sum(1 for entry in entries if not bool(entry.ready))
    return cast(dict[str, object], value)


def _control_lines(days: Sequence[DayRecord]) -> dict[str, dict[str, object]]:
    s0_lines = _s0._summarize_lines(tuple(day.s0_day for day in days))
    ceiling = _read_json(CEILING_RECEIPT)
    side_split = _read_json(SIDE_SPLIT_RECEIPT)
    pinned_lines = side_split.get("lines")
    if not isinstance(pinned_lines, dict):
        raise JoinUnavailable("side_split.lines", "pinned S0 lines expected object")
    side_price = pinned_lines.get("sideoracle_price")
    if not isinstance(side_price, dict):
        raise JoinUnavailable("side_split.sideoracle_price", "pinned line expected object")
    computed = s0_lines["sideoracle_price"]
    for scope in ("gated", "ungated"):
        if s0_lines["cellbest_control"][scope] is None:
            raise JoinUnavailable("cellbest_control", f"missing {scope} control")
        actual_cellbest = dict(s0_lines["cellbest_control"][scope])
        for name in (
            "entered_cells",
            "eligible_candidates",
            "eligible_cells",
            "cells_without_ready",
            "selected_not_ready",
        ):
            actual_cellbest.pop(name, None)
        if actual_cellbest != ceiling.get(scope):
            raise JoinUnavailable("cellbest_control", f"{scope} control drift")
        if computed[scope] != side_price.get(scope):
            raise JoinUnavailable("sideoracle_price_control", f"{scope} control drift")
    return {
        "cellbest_control": {
            "causal_status": LINE_LABELS["cellbest_control"],
            "gated": cast(dict[str, object], ceiling["gated"]),
            "ungated": cast(dict[str, object], ceiling["ungated"]),
        },
        "sideoracle_price_control": {
            "causal_status": LINE_LABELS["sideoracle_price_control"],
            "gated": cast(dict[str, object], computed["gated"]),
            "ungated": cast(dict[str, object], computed["ungated"]),
        },
    }


def _summarize_new_lines(
    days: Sequence[DayRecord],
    cells: Sequence[CellRecord],
    selections: Mapping[str, Mapping[CellKey, object]],
) -> dict[str, dict[str, object]]:
    return {
        name: {
            "causal_status": LINE_LABELS[name],
            "gated": _new_line_scope(days, cells, selections[name], True),
            "ungated": _new_line_scope(days, cells, selections[name], False),
        }
        for name in LINE_NAMES[2:]
    }


def _asset_counts(cells: Sequence[CellRecord], predicate: object) -> dict[str, int]:
    check = cast(object, predicate)
    return {
        asset: sum(1 for cell in cells if cell.asset == asset and check(cell))
        for asset in ASSETS
    }


def _scope_cells(cells: Sequence[CellRecord], gated: bool) -> tuple[CellRecord, ...]:
    return tuple(cell for cell in cells if not gated or cell.selected)


def _counters(
    cells: Sequence[CellRecord],
    lines: Mapping[str, Mapping[str, object]],
    states: Mapping[tuple[str, CellKey], PickerState],
    fits: Sequence[LogisticFit],
    untrained_days: Mapping[str, frozenset[int]],
) -> dict[str, object]:
    scopes = {name: _scope_cells(cells, name == "gated") for name in ("gated", "ungated")}
    short_prefix = {
        scope: _asset_counts(rows, lambda cell: len(cell.stream) < PREFIX_ROWS + 1)
        for scope, rows in scopes.items()
    }
    without_ready = {
        scope: _asset_counts(rows, lambda cell: cell.sigma_star is None)
        for scope, rows in scopes.items()
    }
    untrained = {
        scope: _asset_counts(
            rows,
            lambda cell: cell.d8 in untrained_days[cell.asset],
        )
        for scope, rows in scopes.items()
    }
    state_counts: dict[str, object] = {}
    for state_name in ("never_armed", "armed_no_entry"):
        state_counts[state_name] = {
            name: {
                scope: _asset_counts(
                    rows,
                    lambda cell, line=name, state=state_name: states.get((line, cell.key)) == state,
                )
                for scope, rows in scopes.items()
            }
            for name in (
                "turncap_oracle_side",
                "turncap_wrong_side",
                "policy_walkforward",
            )
        }
    selected_not_ready = {
        name: {
            scope: int(cast(Mapping[str, object], lines[name][scope])["selected_not_ready"])
            if "selected_not_ready" in cast(Mapping[str, object], lines[name][scope])
            else 0
            for scope in ("gated", "ungated")
        }
        for name in LINE_NAMES
    }
    fits_by_asset = {
        asset: tuple(fit.train_size for fit in fits if fit.asset == asset)
        for asset in ASSETS
    }
    train_size = {
        asset: {
            "min": min(sizes) if sizes else None,
            "median": float(np.median(np.asarray(sizes, dtype=np.float64))) if sizes else None,
            "max": max(sizes) if sizes else None,
        }
        for asset, sizes in fits_by_asset.items()
    }
    return {
        "cells_short_prefix": short_prefix,
        "cells_untrained": untrained,
        "cells_never_armed": state_counts["never_armed"],
        "cells_armed_no_entry": state_counts["armed_no_entry"],
        "cells_without_ready": without_ready,
        "selected_not_ready": selected_not_ready,
        "fits_run": {
            **{asset: len(fits_by_asset[asset]) for asset in ASSETS},
            "total": len(fits),
        },
        "train_size": train_size,
    }


def _accuracy_scope(
    cells: Sequence[CellRecord],
    calls: Mapping[CellKey, int],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for asset in ASSETS:
        asset_cells = tuple(cell for cell in cells if cell.asset == asset)
        labeled = tuple(cell for cell in asset_cells if cell.sigma_star is not None)
        called = tuple(cell for cell in asset_cells if cell.key in calls)
        called_labeled = tuple(cell for cell in labeled if cell.key in calls)
        confusion = {
            "true_long_called_long": sum(
                1 for cell in called_labeled if cell.sigma_star == 1 and calls[cell.key] == 1
            ),
            "true_long_called_short": sum(
                1 for cell in called_labeled if cell.sigma_star == 1 and calls[cell.key] == -1
            ),
            "true_short_called_long": sum(
                1 for cell in called_labeled if cell.sigma_star == -1 and calls[cell.key] == 1
            ),
            "true_short_called_short": sum(
                1 for cell in called_labeled if cell.sigma_star == -1 and calls[cell.key] == -1
            ),
        }
        correct = confusion["true_long_called_long"] + confusion["true_short_called_short"]
        denominator = len(called_labeled)
        result[asset] = {
            "accuracy": float(correct / denominator) if denominator else None,
            "correct": correct,
            "called_labeled": denominator,
            "called_total": len(called),
            "labeled_total": len(labeled),
            "confusion": confusion,
        }
    return result


def _side_accuracy_s1(
    cells: Sequence[CellRecord],
    calls: Mapping[CellKey, int],
) -> dict[str, object]:
    return {
        "gated": _accuracy_scope(_scope_cells(cells, True), calls),
        "ungated": _accuracy_scope(_scope_cells(cells, False), calls),
    }


def _pstar(rung: float, winner: float, loser: float) -> float | None:
    if winner <= loser:
        return None
    denominator = winner - loser
    if MUTANT == "pstar_eff_arithmetic_drift":
        denominator = winner + loser
    return float((rung - loser) / denominator)


def _line_usd(
    lines: Mapping[str, Mapping[str, object]], name: str, scope: str = "gated"
) -> Mapping[str, float]:
    block = cast(Mapping[str, object], lines[name][scope])
    return cast(Mapping[str, float], block["usd_per_asset_day"])


def _pstar_eff(lines: Mapping[str, Mapping[str, object]]) -> dict[str, object]:
    pairs = {
        "turn": ("turncap_oracle_side", "turncap_wrong_side"),
        "record": ("recordcap_oracle_side", "recordcap_wrong_side"),
    }
    result: dict[str, object] = {}
    for pair, (winner_name, loser_name) in pairs.items():
        winner = _line_usd(lines, winner_name)
        loser = _line_usd(lines, loser_name)
        result[pair] = {
            asset: {
                "W_usd_per_asset_day": float(winner[asset]),
                "L_usd_per_asset_day": float(loser[asset]),
                "rung_usd_per_asset_day": float(RUNGS_USD[asset]),
                "p_star": _pstar(
                    float(RUNGS_USD[asset]),
                    float(winner[asset]),
                    float(loser[asset]),
                ),
            }
            for asset in ASSETS
        }
    return {
        "assumption": (
            "First-order linear bound. Caller errors are assumed to distribute "
            "like the matching wrong-side rule line."
        ),
        "pairs": result,
    }


def _floors(accuracy: Mapping[str, object]) -> dict[str, object]:
    side_split = _read_json(SIDE_SPLIT_RECEIPT)
    side_accuracy = cast(Mapping[str, object], side_split["side_accuracy"])
    pairs = cast(Mapping[str, object], side_accuracy["pairs"])
    price = cast(Mapping[str, Mapping[str, object]], pairs["price"])
    gated = cast(Mapping[str, Mapping[str, object]], accuracy["gated"])
    return {
        asset: {
            "pinned_s0_price_pair_p_star": float(price[asset]["p_star"]),
            "realized_accuracy": gated[asset]["accuracy"],
            "accuracy_minus_floor": (
                float(cast(float, gated[asset]["accuracy"])) - float(price[asset]["p_star"])
                if gated[asset]["accuracy"] is not None
                else None
            ),
        }
        for asset in ASSETS
    }


def _rule_forfeit(lines: Mapping[str, Mapping[str, object]]) -> dict[str, float]:
    pinned = _line_usd(lines, "sideoracle_price_control")
    turn = _line_usd(lines, "turncap_oracle_side")
    return {asset: float(pinned[asset] - turn[asset]) for asset in ASSETS}


def _group_metrics(selections: Sequence[PolicySelection]) -> dict[str, object]:
    cash = {asset: 0.0 for asset in ASSETS}
    trades = {asset: 0 for asset in ASSETS}
    for item in selections:
        asset = item.cell.asset
        cash[asset] += float(_read.cash_usd(item.selected.status, item.selected.cert_close_usd))
        trades[asset] += 1
    total_trades = sum(trades.values())
    total_cash = sum(cash.values())
    return {
        "cash_total_usd": cash,
        "trades": trades,
        "per_trade_mean_usd": {
            asset: (cash[asset] / trades[asset] if trades[asset] else 0.0)
            for asset in ASSETS
        },
        "portfolio_trades": total_trades,
        "portfolio_per_trade_mean_usd": total_cash / total_trades if total_trades else 0.0,
    }


def _policy_decomposition(
    policy: Mapping[CellKey, PolicySelection],
) -> dict[str, object]:
    gated = tuple(item for item in policy.values() if item.cell.selected)
    right = tuple(
        item
        for item in gated
        if item.cell.sigma_star is not None and item.call_side == item.cell.sigma_star
    )
    wrong = tuple(
        item
        for item in gated
        if item.cell.sigma_star is not None and item.call_side != item.cell.sigma_star
    )
    unlabeled = tuple(item for item in gated if item.cell.sigma_star is None)
    return {
        "right_called": _group_metrics(right),
        "wrong_called": _group_metrics(wrong),
        "selected_not_ready": _group_metrics(unlabeled),
    }


def _warmup_view(
    days: Sequence[DayRecord],
    lines: Mapping[str, Mapping[str, object]],
    untrained_days: Mapping[str, frozenset[int]],
) -> dict[str, object]:
    policy = cast(Mapping[str, object], lines["policy_walkforward"]["gated"])
    original_days = cast(Mapping[str, int], policy["days"])
    cash = cast(Mapping[str, float], policy["cash_total_usd"])
    removed = {
        asset: sum(
            1
            for day in days
            if day.asset == asset
            and day.joinable
            and day.selected
            and day.d8 in untrained_days[asset]
        )
        for asset in ASSETS
    }
    after = {asset: int(original_days[asset]) - removed[asset] for asset in ASSETS}
    return {
        "reported_not_gated": True,
        "removed_untrained_days": removed,
        "days_after_warmup": after,
        "cash_total_usd": dict(cash),
        "usd_per_asset_day": {
            asset: float(cash[asset] / after[asset]) if after[asset] else 0.0
            for asset in ASSETS
        },
    }


def _dollar_stop(
    lines: Mapping[str, Mapping[str, object]],
    accuracy: Mapping[str, object],
    floors: Mapping[str, object],
) -> dict[str, object]:
    blockers: list[str] = []
    turn = cast(Mapping[str, object], lines["turncap_oracle_side"]["gated"])
    wrong = _line_usd(lines, "turncap_wrong_side")
    policy = cast(Mapping[str, object], lines["policy_walkforward"]["gated"])
    for name, block in (("turncap_oracle_side", turn), ("policy_walkforward", policy)):
        usd = cast(Mapping[str, float], block["usd_per_asset_day"])
        for asset in ASSETS:
            if float(usd[asset]) < float(RUNGS_USD[asset]):
                blockers.append(f"{asset} {name} {usd[asset]} misses {RUNGS_USD[asset]}")
        if float(block["max_drawdown_usd"]) > 1000.0:
            blockers.append(f"{name} max_drawdown_usd {block['max_drawdown_usd']} exceeds 1000")
    if not bool(policy["entry_cap_ok"]):
        blockers.append("policy_walkforward entry cap broke")
    if int(policy["overlap_violations"]) != 0:
        blockers.append(
            f"policy_walkforward overlap_violations {policy['overlap_violations']}"
        )
    turn_usd = cast(Mapping[str, float], turn["usd_per_asset_day"])
    for asset in ASSETS:
        if float(turn_usd[asset]) <= float(wrong[asset]):
            blockers.append(
                f"{asset} W_turn {turn_usd[asset]} is not greater than L_turn {wrong[asset]}"
            )
        floor = cast(Mapping[str, object], floors[asset])
        realized = floor["realized_accuracy"]
        required = float(floor["pinned_s0_price_pair_p_star"])
        if realized is None or float(realized) < required:
            blockers.append(f"{asset} accuracy {realized!r} misses {required}")
    verdict = "KILL" if blockers else "LIVE"
    return {
        "verdict": verdict,
        "rungs_usd": dict(RUNGS_USD),
        "max_drawdown_limit_usd": 1000.0,
        "entry_cap": ENTRY_CAP,
        "blockers": blockers,
        "verbatim": {"KILL": KILL_VERBATIM, "LIVE": LIVE_VERBATIM},
        "applied": KILL_VERBATIM if blockers else LIVE_VERBATIM,
        "named_successor": "B0" if blockers else "S2",
        "successor_started": False,
        "accuracy_scope": "gated",
    }


def _source_files() -> dict[str, dict[str, str]]:
    return {
        "script": _source_file(Path(__file__).resolve()),
        "brief": _source_file(BRIEF),
        "side_split_receipt": _source_file(SIDE_SPLIT_RECEIPT),
        "side_split_script": _source_file(SIDE_SPLIT_SCRIPT),
        "ceiling_receipt": _source_file(CEILING_RECEIPT),
        "read_script": _source_file(READ_SCRIPT),
        "ceiling_script": _source_file(CEILING_SCRIPT),
        "forecast": _source_file(FORECAST),
    }


def _build_receipt(verification: Mapping[str, object]) -> dict[str, object]:
    _assert_contract()
    forecast_rows, window_days, n_read = _read.load_window_forecast_rows(FORECAST)
    routed, _empty = _read.route_catboost_daily(forecast_rows)
    refused = _read.refused_days_without_daily(window_days, [row.day for row in routed])
    selected_flags = _read.select_expanding_median(routed)
    jobs_by_asset = {
        asset: [(asset, day, bool(flag)) for day, flag in zip(routed, selected_flags)]
        for asset in ASSETS
    }
    started_scoring = time.perf_counter()
    first_asset = ASSETS[0]
    first_started = time.perf_counter()
    day_records = list(_load_jobs(jobs_by_asset[first_asset]))
    first_models = _model_cells(day_records)
    first_calls, first_fits, first_untrained = _fit_asset_walkforward(
        first_asset, first_models, True
    )
    first_asset_sec = time.perf_counter() - first_started
    projected_sec = first_asset_sec * len(ASSETS)
    if projected_sec > TRIPWIRE_SECONDS:
        raise JoinUnavailable(
            "projection.wall_clock_sec",
            f"first asset projects {projected_sec:.3f}s over {TRIPWIRE_SECONDS:.1f}s",
        )
    calls = dict(first_calls)
    fits = list(first_fits)
    untrained_days: dict[str, frozenset[int]] = {first_asset: first_untrained}
    for asset in ASSETS[1:]:
        asset_days = _load_jobs(jobs_by_asset[asset])
        day_records.extend(asset_days)
        asset_calls, asset_fits, asset_untrained = _fit_asset_walkforward(
            asset, _model_cells(asset_days), True
        )
        calls.update(asset_calls)
        fits.extend(asset_fits)
        untrained_days[asset] = asset_untrained
    day_records.sort(key=lambda day: (day.asset, day.d8))
    cells = tuple(cell for day in day_records for cell in day.cells)
    selections, states, policy = _select_lines(cells, calls)
    lines = _control_lines(day_records)
    lines.update(_summarize_new_lines(day_records, cells, selections))
    _assert_denominators(lines)
    accuracy = _side_accuracy_s1(cells, calls)
    pstar_eff = _pstar_eff(lines)
    floors = _floors(accuracy)
    stop = _dollar_stop(lines, accuracy, floors)
    source_days = [day.source.as_dict() for day in day_records]
    opened_candidate = sum(1 for day in day_records if day.source.candidate is not None)
    opened_teacher = sum(1 for day in day_records if day.source.teacher is not None)
    opened_2025 = sum(1 for day in day_records if day.d8 >= 20250101)
    if opened_2025:
        raise JoinUnavailable("opened_2025_files", f"opened {opened_2025} 2025 day records")
    verdict = str(stop["verdict"])
    return {
        "schema": SCHEMA,
        "status": verdict,
        "verdict": verdict,
        "label": LABEL,
        "rule": RULE,
        "window": [WINDOW_START, WINDOW_END],
        "check_command": CHECK,
        "workers": WORKERS,
        "routed": len(routed),
        "selected": sum(1 for flag in selected_flags if flag),
        "refused_no_forecast": len(refused),
        "refused_no_forecast_days": list(refused),
        "n_forecast_rows_read": n_read,
        "line_names": list(LINE_NAMES),
        "lines": lines,
        "side_accuracy_s1": accuracy,
        "p_star_eff": pstar_eff,
        "floors": floors,
        "rule_forfeit": _rule_forfeit(lines),
        "policy_decomposition": _policy_decomposition(policy),
        "warmup_view": _warmup_view(day_records, lines, untrained_days),
        "counters": _counters(cells, lines, states, fits, untrained_days),
        "fit_digest": _fit_digest(fits),
        "dollar_stop": stop,
        "verification": dict(verification),
        "projection": {
            "first_asset": first_asset,
            "first_asset_wall_clock_sec": round(first_asset_sec, 3),
            "projected_full_wall_clock_sec": round(projected_sec, 3),
            "tripwire_wall_clock_sec": TRIPWIRE_SECONDS,
            "scoring_wall_clock_sec": round(time.perf_counter() - started_scoring, 3),
        },
        "guardrails": {
            "one_teacher_cash_scoring_read": True,
            "candidate_columns": [
                "candidate_id",
                "side",
                "entry_mid2",
                "decision_ts_ns",
                "compliance_status",
            ],
            "teacher_columns": list(_read.TEACHER_COLS),
            "peek_columns_parsed": [],
            "opened_2025_candidate_or_teacher_files": opened_2025,
            "fitted_read": True,
            "first_legitimate_fitted_read_flip_since_c": True,
            "engine_files_touched": [],
            "units_started": ["S1"],
            "tickets_started": [],
            "successor_started": False,
        },
        "sources": {
            "files": _source_files(),
            "candidates_root": _relative(CANDIDATES),
            "teacher_root": _relative(TEACHERS),
            "receipts_root": _relative(SOURCE_RECEIPTS),
            "opened_candidate_files": opened_candidate,
            "opened_teacher_files": opened_teacher,
            "g1_days_sha256": _canonical_sha(source_days),
            "g1_days": source_days,
        },
    }


def _assert_contract() -> None:
    if tuple(LINE_LABELS) != LINE_NAMES:
        raise JoinUnavailable("line_names", f"line labels {tuple(LINE_LABELS)!r}")
    if len(FEATURE_NAMES) != 10:
        raise JoinUnavailable("features", f"feature names {FEATURE_NAMES!r}")
    if tuple(_read.TEACHER_COLS) != (
        "candidate_id",
        "status",
        "cert_close_usd",
        "exit_ts_ns",
    ):
        raise JoinUnavailable("teacher.usecols", f"teacher columns {_read.TEACHER_COLS!r}")
    if set(_read.TEACHER_COLS).intersection(PEEK_COLS):
        raise JoinUnavailable("teacher.usecols", "teacher usecols include peek columns")
    if PREFIX_ROWS != 8 or MIN_TRAIN != 50 or L2_LAMBDA != 1.0:
        raise JoinUnavailable("frozen_config", "S1 frozen constants drifted")
    if IRLS_ITERATIONS != 100 or CALL_THRESHOLD != 0.5:
        raise JoinUnavailable("frozen_config", "S1 fit constants drifted")


def _assert_denominators(lines: Mapping[str, Mapping[str, object]]) -> None:
    ceiling = _read_json(CEILING_RECEIPT)
    expected_ungated = cast(Mapping[str, object], ceiling["ungated"])["days"]
    for name in LINE_NAMES:
        gated = cast(Mapping[str, object], lines[name]["gated"])
        ungated = cast(Mapping[str, object], lines[name]["ungated"])
        if gated.get("days") != dict(EXPECTED_GATED_DAYS):
            raise JoinUnavailable("denominator.gated", f"{name} days {gated.get('days')!r}")
        if ungated.get("days") != expected_ungated:
            raise JoinUnavailable("denominator.ungated", f"{name} days {ungated.get('days')!r}")


def _repo_path(relative: str) -> Path:
    path = (REPO / relative).resolve()
    try:
        path.relative_to(REPO.resolve())
    except ValueError as exc:
        raise JoinUnavailable("receipt.source_path", f"path escapes repo {relative!r}") from exc
    return path


def _verify_source_pin(value: object, label: str) -> None:
    if not isinstance(value, dict):
        raise JoinUnavailable(label, f"source pin {value!r} expected object")
    path = value.get("path")
    expected = value.get("sha256")
    if not isinstance(path, str) or not isinstance(expected, str):
        raise JoinUnavailable(label, f"source pin {value!r} lacks path or sha256")
    _verify_file_sha(_repo_path(path), expected, label)


def _verify_sources(receipt: Mapping[str, object]) -> None:
    sources = receipt.get("sources")
    if not isinstance(sources, dict):
        raise JoinUnavailable("receipt.sources", "sources expected object")
    files = sources.get("files")
    expected_files = {
        "script",
        "brief",
        "side_split_receipt",
        "side_split_script",
        "ceiling_receipt",
        "read_script",
        "ceiling_script",
        "forecast",
    }
    if not isinstance(files, dict) or set(files) != expected_files:
        raise JoinUnavailable("receipt.sources.files", f"unexpected source files {files!r}")
    for name, value in files.items():
        _verify_source_pin(value, f"sources.files.{name}")
    source_days = sources.get("g1_days")
    if not isinstance(source_days, list):
        raise JoinUnavailable("sources.g1_days", "g1_days expected list")
    if _canonical_sha(source_days) != sources.get("g1_days_sha256"):
        raise JoinUnavailable("sources.g1_days_sha256", "g1 day source digest drift")
    opened_candidate = 0
    opened_teacher = 0
    for index, item in enumerate(source_days):
        if not isinstance(item, dict):
            raise JoinUnavailable("sources.g1_days", f"row {index} expected object")
        d8 = item.get("d8")
        if not isinstance(d8, int) or d8 < 20220309 or d8 > 20241231:
            raise JoinUnavailable("sources.g1_days.d8", f"row {index} d8 {d8!r}")
        candidate = item.get("candidate")
        if candidate is not None:
            _s0._verify_output_pin(candidate, f"sources.g1_days[{index}].candidate")
            opened_candidate += 1
        teacher = item.get("teacher")
        if teacher is not None:
            _s0._verify_output_pin(teacher, f"sources.g1_days[{index}].teacher")
            opened_teacher += 1
    if opened_candidate != sources.get("opened_candidate_files"):
        raise JoinUnavailable("sources.opened_candidate_files", "candidate count drift")
    if opened_teacher != sources.get("opened_teacher_files"):
        raise JoinUnavailable("sources.opened_teacher_files", "teacher count drift")


def _verify_controls(receipt: Mapping[str, object]) -> None:
    lines = receipt.get("lines")
    if not isinstance(lines, dict) or set(lines) != set(LINE_NAMES):
        raise JoinUnavailable("receipt.lines", f"line names {lines!r}")
    ceiling = _read_json(CEILING_RECEIPT)
    side_split = _read_json(SIDE_SPLIT_RECEIPT)
    pinned_lines = cast(Mapping[str, Mapping[str, object]], side_split["lines"])
    for scope in ("gated", "ungated"):
        cellbest = cast(Mapping[str, object], lines["cellbest_control"])
        if cellbest.get(scope) != ceiling.get(scope):
            raise JoinUnavailable("receipt.cellbest_control", f"{scope} control drift")
        side_price = cast(Mapping[str, object], lines["sideoracle_price_control"])
        if side_price.get(scope) != pinned_lines["sideoracle_price"].get(scope):
            raise JoinUnavailable("receipt.sideoracle_price_control", f"{scope} control drift")


def _verify_derived(receipt: Mapping[str, object]) -> None:
    if receipt.get("schema") != SCHEMA:
        raise JoinUnavailable("receipt.schema", f"schema {receipt.get('schema')!r}")
    if receipt.get("line_names") != list(LINE_NAMES):
        raise JoinUnavailable("receipt.line_names", f"line names {receipt.get('line_names')!r}")
    _verify_controls(receipt)
    lines = cast(Mapping[str, Mapping[str, object]], receipt["lines"])
    _assert_denominators(lines)
    accuracy = cast(Mapping[str, object], receipt["side_accuracy_s1"])
    floors = cast(Mapping[str, object], receipt["floors"])
    expected_stop = _dollar_stop(lines, accuracy, floors)
    if receipt.get("dollar_stop") != expected_stop:
        raise JoinUnavailable("receipt.dollar_stop", "dollar stop drift")
    if receipt.get("verdict") != expected_stop["verdict"]:
        raise JoinUnavailable("receipt.verdict", f"verdict {receipt.get('verdict')!r}")
    guardrails = receipt.get("guardrails")
    if not isinstance(guardrails, dict):
        raise JoinUnavailable("receipt.guardrails", "guardrails expected object")
    required = {
        "fitted_read": True,
        "first_legitimate_fitted_read_flip_since_c": True,
        "engine_files_touched": [],
        "units_started": ["S1"],
        "peek_columns_parsed": [],
        "opened_2025_candidate_or_teacher_files": 0,
        "successor_started": False,
    }
    for name, expected in required.items():
        if guardrails.get(name) != expected:
            raise JoinUnavailable("receipt.guardrails", f"{name} {guardrails.get(name)!r}")
    digest = receipt.get("fit_digest")
    if not isinstance(digest, str) or len(digest) != 64:
        raise JoinUnavailable("receipt.fit_digest", f"fit digest {digest!r}")


def _verify_existing_receipt() -> dict[str, object]:
    receipt = _read_json(RECEIPT)
    _verify_sources(receipt)
    _verify_derived(receipt)
    return receipt


def _write_receipt(value: Mapping[str, object]) -> None:
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    temporary = RECEIPT.with_name(f"{RECEIPT.name}.tmp.{os.getpid()}")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, RECEIPT)


def _fixture_row(
    candidate_id: str,
    index: int,
    side: int,
    mid: int,
    status: str = "READY",
    cert: float = 1.0,
) -> object:
    return _s0._outcome(candidate_id, index * 10, side, mid, status, cert)


def _picker_fixture() -> tuple[object, ...]:
    prefix = tuple(
        _fixture_row(f"p{index}", index, 1 if index % 2 else -1, 100)
        for index in range(1, PREFIX_ROWS + 1)
    )
    return (
        *prefix,
        _fixture_row("arm", 9, 1, 90),
        _fixture_row("wrong_pause", 10, -1, 95),
        _fixture_row("called_pause", 11, 1, 96),
    )


def _model_fixture_cell(
    d8: int,
    phase: int,
    label: int,
    value: float = 0.0,
) -> ModelCell:
    features = np.zeros(len(FEATURE_NAMES), dtype=np.float64)
    features[0] = value
    return ModelCell("HG", d8, phase, f"c{d8}-{phase}", features, label)


def _selftest_guard() -> None:
    with tempfile.TemporaryDirectory(prefix="threshold-s1-sidecaller-selftest-") as directory:
        path = Path(directory) / "candidates.tsv"
        path.write_text("candidate_id\noriginal\n")
        expected = _sha256_file(path)
        path.write_text("candidate_id\ncorrupted\n")
        try:
            _verify_file_sha(path, expected, "selftest.candidate_id")
        except JoinUnavailable:
            return
        raise AssertionError("selftest accepted a corrupted synthetic candidate_id")


def _selftest_pickers() -> None:
    fixture = _picker_fixture()
    picked = _pick_turn(fixture, 1)
    if picked.selected is None or picked.selected.candidate.candidate_id != "called_pause":
        raise AssertionError(f"turn entry {picked!r}")
    equal_fixture = (
        *fixture[:PREFIX_ROWS],
        _fixture_row("equal_arm", 9, 1, 90),
        _fixture_row("equal_trigger", 10, 1, 90),
    )
    equal = _pick_turn(equal_fixture, 1)
    if equal.selected is None or equal.selected.candidate.candidate_id != "equal_trigger":
        raise AssertionError(f"equal-mid trigger {equal!r}")
    never = _pick_turn(
        (*fixture[:PREFIX_ROWS], _fixture_row("no_arm", 9, 1, 110)), 1
    )
    if never.state != "never_armed" or never.selected is not None:
        raise AssertionError(f"never-armed state {never!r}")
    armed = _pick_turn(
        (
            *fixture[:PREFIX_ROWS],
            _fixture_row("only_arm", 9, 1, 90),
            _fixture_row("still_improves", 10, 1, 80),
        ),
        1,
    )
    if armed.state != "armed_no_entry" or armed.selected is not None:
        raise AssertionError(f"armed-no-entry state {armed!r}")
    record = _pick_record(fixture, 1)
    if record.selected is None or record.selected.candidate.candidate_id != "arm":
        raise AssertionError(f"record twin {record!r}")
    nonready = tuple(
        _fixture_row(
            str(row.candidate.candidate_id),
            index,
            int(row.candidate.side),
            int(row.candidate.entry_mid2),
            "NO_SANE_SUFFIX",
            99.0,
        )
        for index, row in enumerate(fixture, start=1)
    )
    policy = _pick_turn(nonready, 1)
    if policy.selected is None:
        raise AssertionError("no-READY policy fixture did not enter")
    if _read.cash_usd(policy.selected.status, policy.selected.cert_close_usd) != 0.0:
        raise AssertionError("no-READY policy entry did not cash zero")


def _selftest_features_and_fit() -> None:
    fixture = _picker_fixture()
    changed_teacher = tuple(
        _fixture_row(
            str(row.candidate.candidate_id),
            index,
            int(row.candidate.side),
            int(row.candidate.entry_mid2),
            "READY",
            float(index * 1000),
        )
        for index, row in enumerate(fixture, start=1)
    )
    first = _prefix_features(fixture, 0)
    second = _prefix_features(changed_teacher, 0)
    if first is None or second is None or not np.array_equal(first, second):
        raise AssertionError("teacher bytes changed caller features")
    features = np.zeros((8, len(FEATURE_NAMES)), dtype=np.float64)
    features[:, 0] = np.asarray([-4, -3, -2, -1, 1, 2, 3, 4], dtype=np.float64)
    labels = np.asarray([0, 0, 0, 0, 1, 1, 1, 1], dtype=np.float64)
    beta, _mean, sigma = _fit_irls(features, labels)
    if beta[1] <= 0.0:
        raise AssertionError(f"IRLS sign recovery beta {beta!r}")
    if not np.all(sigma[1:] == SIGMA_FLOOR):
        raise AssertionError(f"sigma floor {sigma!r}")


def _selftest_walkforward() -> None:
    prior = tuple(
        _model_fixture_cell(20220310, phase, -1 if phase < 26 else 1)
        for phase in range(50)
    )
    current = tuple(
        _model_fixture_cell(20220311, 100 + phase, 1) for phase in range(3)
    )
    calls, fits, _untrained = _fit_asset_walkforward("HG", (*prior, *current), False)
    if not fits or any(calls[cell.key] != -1 for cell in current):
        raise AssertionError(f"same-day boundary calls {calls!r}")
    beta_a = np.arange(len(FEATURE_NAMES) + 1, dtype=np.float64)
    beta_b = beta_a + 3.0
    zero = np.zeros(len(FEATURE_NAMES), dtype=np.float64)
    one = np.ones(len(FEATURE_NAMES), dtype=np.float64)
    digest_fits = (
        LogisticFit("HG", 20220310, beta_a, zero, one, 50),
        LogisticFit("HG", 20220311, beta_b, zero, one, 53),
    )
    if _fit_digest(digest_fits) != _fit_digest(tuple(reversed(digest_fits))):
        raise AssertionError("fit digest depends on input order")


def _selftest() -> int:
    if MUTANT and MUTANT not in KNOWN_MUTANTS:
        raise ValueError(f"unknown QRE2_S1SIDECALLER_MUTANT {MUTANT!r}")
    _assert_contract()
    _selftest_guard()
    _selftest_pickers()
    _selftest_features_and_fit()
    _selftest_walkforward()
    if _pstar(2000.0, 2500.0, 500.0) != 0.75:
        raise AssertionError("p_star_eff arithmetic drift")
    print("selftest_ok")
    return 0


def _verification_command(mutant: str | None) -> str:
    if mutant is None:
        return f"{CHECK} --selftest"
    return f"QRE2_S1SIDECALLER_MUTANT={mutant} {CHECK} --selftest"


def _run_red_first_checks() -> dict[str, object]:
    checks: list[tuple[str, str | None]] = [("selftest", None)]
    checks.extend((name, name) for name in MUTANTS)
    checks.append(("guard_mutant", GUARD_MUTANT))
    results: dict[str, object] = {}
    for label, mutant in checks:
        env = dict(os.environ)
        env.pop("QRE2_S1SIDECALLER_MUTANT", None)
        if mutant is not None:
            env["QRE2_S1SIDECALLER_MUTANT"] = mutant
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--selftest"],
            cwd=REPO,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        expected_red = mutant is not None
        if expected_red and completed.returncode == 0:
            raise JoinUnavailable("verification.mutant", f"mutant {mutant!r} stayed green")
        if not expected_red and completed.returncode != 0:
            tail = (completed.stderr or completed.stdout).strip().splitlines()[-1:]
            raise JoinUnavailable(
                "verification.selftest",
                f"baseline selftest failed with {completed.returncode}: {tail}",
            )
        results[label] = {
            "command": _verification_command(mutant),
            "exit_code": completed.returncode,
            "status": "KILLED" if expected_red else "PASS",
        }
    return {"red_first_before_era_read": True, "checks": results}


def _summary(receipt: Mapping[str, object]) -> str:
    lines = cast(Mapping[str, Mapping[str, object]], receipt["lines"])
    policy = cast(Mapping[str, object], lines["policy_walkforward"]["gated"])
    return (
        f"receipt={_relative(RECEIPT)} verdict={receipt.get('verdict')} "
        f"policy_walkforward={policy.get('usd_per_asset_day')} "
        f"max_drawdown_usd={policy.get('max_drawdown_usd')} "
        f"fit_digest={receipt.get('fit_digest')} "
        f"wall_clock_sec={receipt.get('wall_clock_sec')}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if args == ["--selftest"]:
        return _selftest()
    if args:
        raise ValueError(f"unsupported arguments {args}")
    if MUTANT:
        raise ValueError("QRE2_S1SIDECALLER_MUTANT is allowed only with --selftest")
    if RECEIPT.exists():
        receipt = _verify_existing_receipt()
        print(_summary(receipt))
        return 0
    started = time.perf_counter()
    verification = _run_red_first_checks()
    receipt = _build_receipt(verification)
    receipt["wall_clock_sec"] = round(time.perf_counter() - started, 3)
    _verify_derived(receipt)
    _write_receipt(receipt)
    print(_summary(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
