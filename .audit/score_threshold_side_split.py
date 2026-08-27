#!/usr/bin/env python3
"""Price the frozen S0 side-split ceiling on the stored era join."""

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
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
RECEIPT = REPO / ".audit/threshold-side-split.json"
BRIEF = REPO / ".audit/briefs/threshold-architect-after-c-fable-out.md"
CEILING_RECEIPT = REPO / ".audit/threshold-2022-2024-ceiling.json"
READ_SCRIPT = REPO / ".audit/score_threshold_2022_2024_read.py"
CEILING_SCRIPT = REPO / ".audit/score_threshold_2022_2024_ceiling.py"
CAPTURE_SCRIPT = REPO / ".audit/score_threshold_capture_gap.py"
FREEZE = REPO / ".audit/threshold-2022-2024-freeze.md"
CHECK = "python3 .audit/score_threshold_side_split.py"
SCHEMA = "QRE2THRESHOLDSIDESPLIT1"
WORKERS = 14
TRIPWIRE_SECONDS = 7200.0
PSTAR_LIMIT = 0.90
MUTANT = os.environ.get("QRE2_SIDESPLIT_MUTANT", "")
MUTANTS = (
    "wrong_side_pick_accepted",
    "ready_only_eligibility",
    "cert_in_price_pick",
    "positivity_gate_smuggled",
    "pstar_arithmetic_drift",
)
GUARD_MUTANT = "corrupt_candidate_id_accepted"
KNOWN_MUTANTS = frozenset((*MUTANTS, GUARD_MUTANT))
EXTRA_CANDIDATE_COLUMNS = (
    "candidate_id",
    "side",
    "entry_mid2",
    "compliance_status",
)
LABEL = (
    "Exploratory side-conditioned identity ceiling on stored teacher cash. "
    "It can kill or price S1 and cannot promote."
)
RULE = (
    "For each joinable cell, define the oracle side from the READY row with "
    "maximum cert_close_usd, tied by smallest candidate_id. Score the frozen "
    "six lines using either side-relative entry price or earliest decision. "
    "Reduction lines select from CLEAR rows without a positivity filter."
)
KILL_VERBATIM = (
    "On the locked gated denominators, sideoracle_price misses a rung, a price "
    "pair p_star exceeds 0.90, or W is not strictly greater than L. The side "
    "reduction at age 180 closes. B0 is the named successor and does not start "
    "inside S0."
)
LIVE_VERBATIM = (
    "sideoracle_price clears all three rungs and every price-pair p_star is at "
    "most 0.90 with W strictly greater than L. S1 is the named successor and "
    "does not start inside S0."
)

LineName = Literal[
    "cellbest_control",
    "sideoracle_price",
    "sideoracle_earliest",
    "wrongside_price",
    "wrongside_earliest",
    "sideoracle_price_ready",
]
LINE_NAMES: tuple[LineName, ...] = (
    "cellbest_control",
    "sideoracle_price",
    "sideoracle_earliest",
    "wrongside_price",
    "wrongside_earliest",
    "sideoracle_price_ready",
)
LINE_LABELS: Mapping[LineName, str] = {
    "cellbest_control": "oracle identity with the frozen enter-positive law",
    "sideoracle_price": "oracle side and roster hindsight within side",
    "sideoracle_earliest": "oracle side and causal earliest CLEAR within side",
    "wrongside_price": "opposite-side price-order control",
    "wrongside_earliest": "opposite-side earliest control",
    "sideoracle_price_ready": "oracle side and READY-only price-order control",
}


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_read = _load_module(READ_SCRIPT, "threshold_side_split_read")
_ceiling = _load_module(CEILING_SCRIPT, "threshold_side_split_ceiling")
JoinUnavailable = _read.JoinUnavailable
ASSETS = cast(tuple[str, ...], _read.ASSETS)
PHASES = cast(tuple[int, ...], _read.PHASES)
RUNGS_USD = cast(Mapping[str, float], _read.RUNGS_USD)
ENTRY_CAP = int(_read.ENTRY_CAP)
PEEK_COLS = cast(tuple[str, ...], _read.PEEK_COLS)
FORECAST = cast(Path, _read.FORECAST)
CANDIDATES = cast(Path, _read.CANDIDATES)
TEACHERS = cast(Path, _read.TEACHERS)
SOURCE_RECEIPTS = cast(Path, _read.RECEIPTS)
WINDOW_START = str(_read.WINDOW_START)
WINDOW_END = str(_read.WINDOW_END)
EXPECTED_GATED_DAYS = cast(Mapping[str, int], _ceiling.EXPECTED_GATED_DAYS)
SelectedName = _read.SelectedName
ReadyPick = _ceiling.ReadyPick
summarize_line = _ceiling.summarize_line


@dataclass(frozen=True, slots=True)
class SideCandidate:
    candidate_id: str
    asset: str
    d8: int
    phase: int
    decision_ts_ns: int
    frozen_cost_usd: float
    side: int
    entry_mid2: int


@dataclass(frozen=True, slots=True)
class CandidateOutcome:
    candidate: SideCandidate
    status: str
    cert_close_usd: float
    exit_ts_ns: int | None

    @property
    def ready(self) -> bool:
        return self.status == "READY"


@dataclass(frozen=True, slots=True)
class CellLine:
    selected: CandidateOutcome | None
    eligible_candidates: int


@dataclass(frozen=True, slots=True)
class CellScore:
    lines: Mapping[LineName, CellLine]
    has_ready: bool


@dataclass(frozen=True, slots=True)
class VerifiedOutput:
    path: str
    receipt: str
    output_sha256: str
    receipt_sha256: str

    def as_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "receipt": self.receipt,
            "output_sha256": self.output_sha256,
            "receipt_sha256": self.receipt_sha256,
        }


@dataclass(frozen=True, slots=True)
class SourceDay:
    asset: str
    d8: int
    candidate_path: str
    candidate_rows: int
    candidate: VerifiedOutput | None
    teacher: VerifiedOutput | None

    def as_dict(self) -> dict[str, object]:
        return {
            "asset": self.asset,
            "d8": self.d8,
            "candidate_path": self.candidate_path,
            "candidate_rows": self.candidate_rows,
            "candidate": self.candidate.as_dict() if self.candidate else None,
            "teacher": self.teacher.as_dict() if self.teacher else None,
        }


@dataclass(frozen=True, slots=True)
class DayScore:
    asset: str
    d8: int
    joinable: bool
    selected: bool
    cells: tuple[CellScore, ...]
    source: SourceDay


def _relative(path: Path) -> str:
    return str(_read._relative(path))


def _sha256_file(path: Path) -> str:
    return str(_read._sha256_file(path))


def _source_file(path: Path) -> dict[str, str]:
    return {"path": _relative(path), "sha256": _sha256_file(path)}


def _read_json(path: Path) -> dict[str, object]:
    return cast(dict[str, object], _read._read_json(path))


def _verify_file_sha(path: Path, expected: str, label: str) -> str:
    actual = _sha256_file(path)
    if actual != expected and MUTANT != GUARD_MUTANT:
        raise JoinUnavailable(
            label,
            f"{path} sha256 {actual!r} expected {expected!r}",
        )
    return actual


def _verified_output(path: Path, receipt: Path, label: str) -> VerifiedOutput:
    payload = _read_json(receipt)
    expected = payload.get("output_sha256")
    if not isinstance(expected, str) or not expected:
        raise JoinUnavailable(
            f"{label}.output_sha256",
            f"{receipt} output_sha256 {expected!r} expected nonempty string",
        )
    actual = _verify_file_sha(path, expected, f"{label}.output_sha256")
    if actual != expected:
        raise JoinUnavailable(
            f"{label}.output_sha256",
            f"{path} sha256 {actual!r} expected {expected!r}",
        )
    return VerifiedOutput(
        path=_relative(path),
        receipt=_relative(receipt),
        output_sha256=expected,
        receipt_sha256=_sha256_file(receipt),
    )


def _assert_contract() -> None:
    if tuple(LINE_LABELS) != LINE_NAMES:
        raise JoinUnavailable(
            "line_names",
            f"line labels {tuple(LINE_LABELS)!r} differ from {LINE_NAMES!r}",
        )
    leaked = set(EXTRA_CANDIDATE_COLUMNS).intersection(PEEK_COLS)
    if leaked:
        raise JoinUnavailable(
            "candidates.usecols",
            f"candidate usecols include peek columns {sorted(leaked)}",
        )
    teacher_columns = tuple(_read.TEACHER_COLS)
    expected_teacher = ("candidate_id", "status", "cert_close_usd", "exit_ts_ns")
    if teacher_columns != expected_teacher:
        raise JoinUnavailable(
            "teacher.usecols",
            f"teacher columns {teacher_columns!r} differ from {expected_teacher!r}",
        )
    if set(teacher_columns).intersection(PEEK_COLS):
        raise JoinUnavailable("teacher.usecols", "teacher usecols include peek columns")


def _load_side_candidates(
    asset: str,
    d8: int,
) -> tuple[bool, tuple[SideCandidate, ...], SourceDay]:
    if d8 < 20220309 or d8 > 20241231:
        raise JoinUnavailable("window.d8", f"refuse candidate day {asset}/{d8}")
    expected_path = CANDIDATES / asset / f"{d8}.tsv"
    n_rows, base_rows, path = _read._load_candidates(asset, d8)
    if path is None:
        return (
            False,
            (),
            SourceDay(asset, d8, _relative(expected_path), 0, None, None),
        )
    candidate_receipt = SOURCE_RECEIPTS / asset / f"{d8}.candidates.json"
    if n_rows == 0:
        source = _verified_output(path, candidate_receipt, "candidates")
        return False, (), SourceDay(asset, d8, _relative(path), 0, source, None)
    frame = pd.read_csv(
        path,
        sep="\t",
        skiprows=1,
        usecols=list(EXTRA_CANDIDATE_COLUMNS),
        dtype={
            "candidate_id": str,
            "side": np.int64,
            "entry_mid2": np.int64,
            "compliance_status": str,
        },
    )
    candidate_source = _verified_output(path, candidate_receipt, "candidates")
    clear = frame[frame["compliance_status"] == "CLEAR"]
    if clear["candidate_id"].duplicated().any():
        duplicate = str(clear.loc[clear["candidate_id"].duplicated(), "candidate_id"].iloc[0])
        raise JoinUnavailable(
            "candidates.candidate_id",
            f"{path} repeats CLEAR candidate_id {duplicate!r}",
        )
    extras = {str(row.candidate_id): row for row in clear.itertuples(index=False)}
    base_ids = [str(row.candidate_id) for row in base_rows]
    if len(base_ids) != len(set(base_ids)):
        raise JoinUnavailable(
            "candidates.candidate_id",
            f"{path} repeats a CLEAR candidate_id in the base loader",
        )
    if set(extras) != set(base_ids):
        raise JoinUnavailable(
            "candidates.loader_parity",
            f"{path} side loader ids differ from the base loader",
        )
    rows: list[SideCandidate] = []
    for base in base_rows:
        extra = extras[str(base.candidate_id)]
        side = int(extra.side)
        if side not in (-1, 1):
            raise JoinUnavailable(
                "candidates.side",
                f"{path} candidate {base.candidate_id!r} side {side!r}",
            )
        entry_mid2 = int(extra.entry_mid2)
        rows.append(
            SideCandidate(
                candidate_id=str(base.candidate_id),
                asset=str(base.asset),
                d8=int(base.d8),
                phase=int(base.phase),
                decision_ts_ns=int(base.decision_ts_ns),
                frozen_cost_usd=float(base.frozen_cost_usd),
                side=side,
                entry_mid2=entry_mid2,
            )
        )
    source = SourceDay(
        asset,
        d8,
        _relative(path),
        int(n_rows),
        candidate_source,
        None,
    )
    return True, tuple(rows), source


def _load_outcomes(
    asset: str,
    d8: int,
    candidates: Sequence[SideCandidate],
    source: SourceDay,
) -> tuple[tuple[CandidateOutcome, ...], SourceDay]:
    if not candidates:
        return (), source
    wanted = [row.candidate_id for row in candidates]
    teacher, teacher_path = _read._load_teacher(asset, d8, wanted)
    teacher_receipt = SOURCE_RECEIPTS / asset / f"{d8}.teacher.json"
    teacher_source = _verified_output(teacher_path, teacher_receipt, "teacher")
    outcomes: list[CandidateOutcome] = []
    for row in candidates:
        hit = teacher.get(row.candidate_id)
        if hit is None:
            status, cert, exit_ts = "MISSING", 0.0, None
        else:
            status, cert, raw_exit = hit
            exit_ts = int(raw_exit)
        if status == "READY" and not np.isfinite(cert):
            raise JoinUnavailable(
                "teacher.cert_close_usd",
                f"{teacher_path} READY {row.candidate_id} cert {cert!r}",
            )
        outcomes.append(
            CandidateOutcome(
                candidate=row,
                status=str(status),
                cert_close_usd=float(cert),
                exit_ts_ns=exit_ts,
            )
        )
    return (
        tuple(outcomes),
        SourceDay(
            source.asset,
            source.d8,
            source.candidate_path,
            source.candidate_rows,
            source.candidate,
            teacher_source,
        ),
    )


def _on_side(
    rows: Sequence[CandidateOutcome],
    side: int,
) -> tuple[CandidateOutcome, ...]:
    if MUTANT == "wrong_side_pick_accepted":
        return tuple(rows)
    return tuple(row for row in rows if row.candidate.side == side)


def _pick_price(
    rows: Sequence[CandidateOutcome],
    side: int,
) -> CandidateOutcome | None:
    eligible = _on_side(rows, side)
    if not eligible:
        return None
    if MUTANT == "cert_in_price_pick":
        return min(
            eligible,
            key=lambda row: (-row.cert_close_usd, row.candidate.candidate_id),
        )
    return min(
        eligible,
        key=lambda row: (
            side * row.candidate.entry_mid2,
            row.candidate.candidate_id,
        ),
    )


def _pick_earliest(
    rows: Sequence[CandidateOutcome],
    side: int,
) -> CandidateOutcome | None:
    eligible = _on_side(rows, side)
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda row: (
            row.candidate.decision_ts_ns,
            row.candidate.candidate_id,
        ),
    )


def _cellbest_control(rows: Sequence[CandidateOutcome]) -> CandidateOutcome | None:
    ready = tuple(row for row in rows if row.ready)
    by_id = {row.candidate.candidate_id: row for row in ready}
    picks = tuple(
        ReadyPick(
            candidate_id=row.candidate.candidate_id,
            asset=row.candidate.asset,
            d8=row.candidate.d8,
            phase=row.candidate.phase,
            decision_ts_ns=row.candidate.decision_ts_ns,
            frozen_cost_usd=row.candidate.frozen_cost_usd,
            cert_close_usd=row.cert_close_usd,
            exit_ts_ns=cast(int, row.exit_ts_ns),
        )
        for row in ready
    )
    entered = _ceiling.enter_positive(_ceiling.pick_cell_best_ready(picks))
    if not entered:
        return None
    return by_id[str(entered[0].candidate_id)]


def _empty_cell_score() -> CellScore:
    return CellScore(
        lines={name: CellLine(None, 0) for name in LINE_NAMES},
        has_ready=False,
    )


def _score_cell(rows: Sequence[CandidateOutcome]) -> CellScore:
    ready = tuple(row for row in rows if row.ready)
    if not ready:
        return _empty_cell_score()
    sigma = min(
        ready,
        key=lambda row: (-row.cert_close_usd, row.candidate.candidate_id),
    ).candidate.side
    oracle_clear = _on_side(rows, sigma)
    wrong_clear = _on_side(rows, -sigma)
    oracle_ready = tuple(row for row in oracle_clear if row.ready)
    price_pool: Sequence[CandidateOutcome] = oracle_clear
    if MUTANT == "ready_only_eligibility":
        price_pool = oracle_ready
    price = _pick_price(price_pool, sigma)
    earliest = _pick_earliest(oracle_clear, sigma)
    wrong_price = _pick_price(wrong_clear, -sigma)
    wrong_earliest = _pick_earliest(wrong_clear, -sigma)
    ready_price = _pick_price(oracle_ready, sigma)
    if MUTANT == "positivity_gate_smuggled" and sigma is not None:
        sigma_best = max(row.cert_close_usd for row in ready if row.candidate.side == sigma)
        if sigma_best <= 0.0:
            price = None
            earliest = None
    lines: dict[LineName, CellLine] = {
        "cellbest_control": CellLine(_cellbest_control(rows), len(ready)),
        "sideoracle_price": CellLine(price, len(price_pool)),
        "sideoracle_earliest": CellLine(earliest, len(oracle_clear)),
        "wrongside_price": CellLine(wrong_price, len(wrong_clear)),
        "wrongside_earliest": CellLine(wrong_earliest, len(wrong_clear)),
        "sideoracle_price_ready": CellLine(ready_price, len(oracle_ready)),
    }
    return CellScore(lines=lines, has_ready=True)


def _score_asset_day(asset: str, day: object, selected: bool) -> DayScore:
    joinable, candidates, source = _load_side_candidates(asset, int(day.d8))
    if not joinable:
        return DayScore(asset, int(day.d8), False, selected, (), source)
    outcomes, source = _load_outcomes(asset, int(day.d8), candidates, source)
    by_phase: dict[int, list[CandidateOutcome]] = {phase: [] for phase in PHASES}
    for row in outcomes:
        if row.candidate.phase in by_phase:
            by_phase[row.candidate.phase].append(row)
    cells = tuple(_score_cell(by_phase[phase]) for phase in PHASES)
    return DayScore(asset, int(day.d8), True, selected, cells, source)


def _score_job(item: tuple[str, object, bool]) -> DayScore:
    return _score_asset_day(*item)


def _score_jobs(jobs: Sequence[tuple[str, object, bool]]) -> tuple[DayScore, ...]:
    scores: list[DayScore] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for score in pool.map(_score_job, jobs):
            scores.append(score)
    return tuple(scores)


def _selected_name(
    outcome: CandidateOutcome,
    source: SourceDay,
) -> object:
    if source.candidate is None or source.teacher is None:
        raise JoinUnavailable(
            "selected.sources",
            f"selected {outcome.candidate.candidate_id} lacks source pins",
        )
    cash = float(_read.cash_usd(outcome.status, outcome.cert_close_usd))
    return SelectedName(
        candidate_id=outcome.candidate.candidate_id,
        asset=outcome.candidate.asset,
        d8=outcome.candidate.d8,
        phase=outcome.candidate.phase,
        decision_ts_ns=outcome.candidate.decision_ts_ns,
        frozen_cost_usd=outcome.candidate.frozen_cost_usd,
        cash_usd=cash,
        exit_ts_ns=outcome.exit_ts_ns,
        ready=outcome.ready,
        source_candidates=source.candidate.path,
        source_teacher=source.teacher.path,
        candidates_output_sha256=source.candidate.output_sha256,
        teacher_output_sha256=source.teacher.output_sha256,
    )


def _scope_line(
    scores: Sequence[DayScore],
    name: LineName,
    gated: bool,
) -> dict[str, object]:
    days = {asset: 0 for asset in ASSETS}
    entries: list[object] = []
    eligible_candidates = 0
    eligible_cells = 0
    cells_without_ready = 0
    for score in scores:
        if not score.joinable or (gated and not score.selected):
            continue
        days[score.asset] += 1
        for cell in score.cells:
            if not cell.has_ready:
                cells_without_ready += 1
            line = cell.lines[name]
            eligible_candidates += line.eligible_candidates
            if line.eligible_candidates:
                eligible_cells += 1
            if line.selected is not None:
                entries.append(_selected_name(line.selected, score.source))
    dollar = summarize_line(entries, days).as_dict()
    selected_not_ready = sum(1 for row in entries if not bool(row.ready))
    dollar.update(
        {
            "entered_cells": len(entries),
            "eligible_candidates": eligible_candidates,
            "eligible_cells": eligible_cells,
            "cells_without_ready": cells_without_ready,
            "selected_not_ready": selected_not_ready,
        }
    )
    if int(dollar["trades"]) != len(entries):
        raise JoinUnavailable(
            f"lines.{name}.trades",
            f"trades {dollar['trades']} differ from entered cells {len(entries)}",
        )
    return dollar


def _summarize_lines(
    scores: Sequence[DayScore],
) -> dict[str, dict[str, object]]:
    return {
        name: {
            "causal_status": LINE_LABELS[name],
            "gated": _scope_line(scores, name, True),
            "ungated": _scope_line(scores, name, False),
        }
        for name in LINE_NAMES
    }


def _pstar(rung: float, winner: float, loser: float) -> float | None:
    if winner <= loser:
        return None
    value = (rung - loser) / (winner - loser)
    if MUTANT == "pstar_arithmetic_drift":
        value = (rung - loser) / (winner + loser)
    return float(value)


def _side_accuracy(
    lines: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    pairs = {
        "price": ("sideoracle_price", "wrongside_price"),
        "earliest": ("sideoracle_earliest", "wrongside_earliest"),
    }
    result: dict[str, object] = {}
    for pair_name, (winner_name, loser_name) in pairs.items():
        winner_line = cast(Mapping[str, object], lines[winner_name]["gated"])
        loser_line = cast(Mapping[str, object], lines[loser_name]["gated"])
        winner_usd = cast(Mapping[str, float], winner_line["usd_per_asset_day"])
        loser_usd = cast(Mapping[str, float], loser_line["usd_per_asset_day"])
        result[pair_name] = {
            asset: {
                "W_usd_per_asset_day": float(winner_usd[asset]),
                "L_usd_per_asset_day": float(loser_usd[asset]),
                "rung_usd_per_asset_day": float(RUNGS_USD[asset]),
                "p_star": _pstar(
                    float(RUNGS_USD[asset]),
                    float(winner_usd[asset]),
                    float(loser_usd[asset]),
                ),
            }
            for asset in ASSETS
        }
    return {
        "assumption": (
            "First-order linear bound. Side-caller errors are assumed to "
            "distribute like the matching wrong-side line."
        ),
        "pairs": result,
    }


def _path_residual(
    lines: Mapping[str, Mapping[str, object]],
) -> dict[str, float]:
    control = cast(
        Mapping[str, float],
        cast(Mapping[str, object], lines["cellbest_control"]["gated"])[
            "usd_per_asset_day"
        ],
    )
    side_price = cast(
        Mapping[str, float],
        cast(Mapping[str, object], lines["sideoracle_price"]["gated"])[
            "usd_per_asset_day"
        ],
    )
    return {asset: float(control[asset] - side_price[asset]) for asset in ASSETS}


def _control_blockers(lines: Mapping[str, Mapping[str, object]]) -> list[str]:
    ceiling = _read_json(CEILING_RECEIPT)
    blockers: list[str] = []
    control = lines["cellbest_control"]
    for scope in ("gated", "ungated"):
        actual = cast(dict[str, object], control[scope]).copy()
        for count_name in (
            "entered_cells",
            "eligible_candidates",
            "eligible_cells",
            "cells_without_ready",
            "selected_not_ready",
        ):
            actual.pop(count_name, None)
        expected = ceiling.get(scope)
        if actual != expected:
            blockers.append(f"cellbest_control {scope} differs from ceiling receipt")
    return blockers


def _denominator_blockers(
    lines: Mapping[str, Mapping[str, object]],
) -> list[str]:
    ceiling = _read_json(CEILING_RECEIPT)
    expected_ungated = cast(Mapping[str, object], ceiling["ungated"])["days"]
    blockers: list[str] = []
    for name in LINE_NAMES:
        gated_days = cast(Mapping[str, object], lines[name]["gated"])["days"]
        ungated_days = cast(Mapping[str, object], lines[name]["ungated"])["days"]
        if gated_days != dict(EXPECTED_GATED_DAYS):
            blockers.append(f"{name} gated days {gated_days!r}")
        if ungated_days != expected_ungated:
            blockers.append(f"{name} ungated days {ungated_days!r}")
    return blockers


def _dollar_stop(
    lines: Mapping[str, Mapping[str, object]],
    side_accuracy: Mapping[str, object],
) -> dict[str, object]:
    price_line = cast(Mapping[str, object], lines["sideoracle_price"]["gated"])
    price_usd = cast(Mapping[str, float], price_line["usd_per_asset_day"])
    price_pairs = cast(
        Mapping[str, Mapping[str, object]],
        cast(Mapping[str, object], side_accuracy["pairs"])["price"],
    )
    blockers: list[str] = []
    for asset in ASSETS:
        winner = float(price_pairs[asset]["W_usd_per_asset_day"])
        loser = float(price_pairs[asset]["L_usd_per_asset_day"])
        pstar = price_pairs[asset]["p_star"]
        if float(price_usd[asset]) < float(RUNGS_USD[asset]):
            blockers.append(
                f"{asset} sideoracle_price {price_usd[asset]} misses {RUNGS_USD[asset]}"
            )
        if winner <= loser:
            blockers.append(f"{asset} W {winner} is not greater than L {loser}")
        if pstar is None or float(pstar) > PSTAR_LIMIT:
            blockers.append(f"{asset} p_star {pstar!r} exceeds {PSTAR_LIMIT}")
    verdict = "KILL" if blockers else "LIVE"
    return {
        "verdict": verdict,
        "p_star_limit": PSTAR_LIMIT,
        "rungs_usd": dict(RUNGS_USD),
        "blockers": blockers,
        "verbatim": {"KILL": KILL_VERBATIM, "LIVE": LIVE_VERBATIM},
        "applied": KILL_VERBATIM if blockers else LIVE_VERBATIM,
        "named_successor": "B0" if blockers else "S1",
        "successor_started": False,
    }


def _source_files() -> dict[str, dict[str, str]]:
    return {
        "script": _source_file(Path(__file__).resolve()),
        "brief": _source_file(BRIEF),
        "ceiling_receipt": _source_file(CEILING_RECEIPT),
        "read_script": _source_file(READ_SCRIPT),
        "ceiling_script": _source_file(CEILING_SCRIPT),
        "capture_gap_script": _source_file(CAPTURE_SCRIPT),
        "freeze": _source_file(FREEZE),
        "forecast": _source_file(FORECAST),
    }


def _canonical_sha(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _build_receipt(verification: Mapping[str, object]) -> dict[str, object]:
    _assert_contract()
    forecast_rows, window_days, n_read = _read.load_window_forecast_rows(FORECAST)
    routed, _empty = _read.route_catboost_daily(forecast_rows)
    refused = _read.refused_days_without_daily(window_days, [row.day for row in routed])
    selected_flags = _read.select_expanding_median(routed)
    jobs_by_asset = {
        asset: [
            (asset, day, bool(flag))
            for day, flag in zip(routed, selected_flags)
        ]
        for asset in ASSETS
    }
    scoring_started = time.perf_counter()
    first_asset = ASSETS[0]
    first_started = time.perf_counter()
    scores = list(_score_jobs(jobs_by_asset[first_asset]))
    first_asset_sec = time.perf_counter() - first_started
    projected_sec = first_asset_sec * len(ASSETS)
    if projected_sec > TRIPWIRE_SECONDS:
        raise JoinUnavailable(
            "projection.wall_clock_sec",
            f"first asset projects {projected_sec:.3f}s over {TRIPWIRE_SECONDS:.1f}s",
        )
    for asset in ASSETS[1:]:
        scores.extend(_score_jobs(jobs_by_asset[asset]))
    scoring_sec = time.perf_counter() - scoring_started
    lines = _summarize_lines(scores)
    infrastructure_blockers = [
        *_control_blockers(lines),
        *_denominator_blockers(lines),
    ]
    if infrastructure_blockers:
        raise JoinUnavailable(
            "infrastructure_stop",
            "; ".join(infrastructure_blockers),
        )
    accuracy = _side_accuracy(lines)
    residual = _path_residual(lines)
    stop = _dollar_stop(lines, accuracy)
    source_days = [score.source.as_dict() for score in scores]
    opened_teacher = sum(1 for score in scores if score.source.teacher is not None)
    opened_candidate = sum(1 for score in scores if score.source.candidate is not None)
    opened_2025 = sum(1 for score in scores if score.d8 >= 20250101)
    if opened_2025:
        raise JoinUnavailable(
            "opened_2025_files",
            f"opened {opened_2025} candidate or teacher day records in 2025",
        )
    verdict = str(stop["verdict"])
    receipt: dict[str, object] = {
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
        "side_accuracy": accuracy,
        "path_residual_usd_per_asset_day": residual,
        "dollar_stop": stop,
        "verification": dict(verification),
        "projection": {
            "first_asset": first_asset,
            "first_asset_wall_clock_sec": round(first_asset_sec, 3),
            "projected_full_wall_clock_sec": round(projected_sec, 3),
            "tripwire_wall_clock_sec": TRIPWIRE_SECONDS,
            "scoring_wall_clock_sec": round(scoring_sec, 3),
        },
        "guardrails": {
            "one_teacher_cash_scoring_read": True,
            "teacher_columns": list(_read.TEACHER_COLS),
            "peek_columns_parsed": [],
            "opened_2025_candidate_or_teacher_files": opened_2025,
            "fitted_read": False,
            "engine_files_touched": [],
            "units_started": ["S0"],
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
    return receipt


def _repo_path(relative: str) -> Path:
    path = (REPO / relative).resolve()
    try:
        path.relative_to(REPO.resolve())
    except ValueError as exc:
        raise JoinUnavailable("receipt.source_path", f"path escapes repo {relative!r}") from exc
    return path


def _verify_source_file(value: object, label: str) -> None:
    if not isinstance(value, dict):
        raise JoinUnavailable(label, f"source pin {value!r} expected object")
    path_value = value.get("path")
    expected = value.get("sha256")
    if not isinstance(path_value, str) or not isinstance(expected, str):
        raise JoinUnavailable(label, f"source pin {value!r} lacks path or sha256")
    _verify_file_sha(_repo_path(path_value), expected, label)


def _verify_output_pin(value: object, label: str) -> None:
    if not isinstance(value, dict):
        raise JoinUnavailable(label, f"output pin {value!r} expected object")
    required = ("path", "receipt", "output_sha256", "receipt_sha256")
    if any(not isinstance(value.get(key), str) for key in required):
        raise JoinUnavailable(label, f"output pin {value!r} lacks required strings")
    path = _repo_path(str(value["path"]))
    receipt = _repo_path(str(value["receipt"]))
    _verify_file_sha(path, str(value["output_sha256"]), f"{label}.output")
    _verify_file_sha(receipt, str(value["receipt_sha256"]), f"{label}.receipt")


def _verify_sources(receipt: Mapping[str, object]) -> None:
    sources = receipt.get("sources")
    if not isinstance(sources, dict):
        raise JoinUnavailable("receipt.sources", "sources expected object")
    files = sources.get("files")
    if not isinstance(files, dict) or set(files) != {
        "script",
        "brief",
        "ceiling_receipt",
        "read_script",
        "ceiling_script",
        "capture_gap_script",
        "freeze",
        "forecast",
    }:
        raise JoinUnavailable("receipt.sources.files", f"unexpected source files {files!r}")
    for name, value in files.items():
        _verify_source_file(value, f"sources.files.{name}")
    source_days = sources.get("g1_days")
    if not isinstance(source_days, list):
        raise JoinUnavailable("sources.g1_days", "g1_days expected list")
    expected_digest = sources.get("g1_days_sha256")
    if _canonical_sha(source_days) != expected_digest:
        raise JoinUnavailable("sources.g1_days_sha256", "g1 day source digest drift")
    opened_candidates = 0
    opened_teachers = 0
    for index, item in enumerate(source_days):
        if not isinstance(item, dict):
            raise JoinUnavailable("sources.g1_days", f"row {index} expected object")
        d8 = item.get("d8")
        if not isinstance(d8, int) or d8 < 20220309 or d8 > 20241231:
            raise JoinUnavailable("sources.g1_days.d8", f"row {index} d8 {d8!r}")
        candidate_path = item.get("candidate_path")
        if not isinstance(candidate_path, str):
            raise JoinUnavailable(
                "sources.g1_days.candidate_path",
                f"row {index} candidate_path {candidate_path!r}",
            )
        candidate = item.get("candidate")
        if candidate is None:
            if _repo_path(candidate_path).exists():
                raise JoinUnavailable(
                    "sources.g1_days.candidate",
                    f"previously missing candidate now exists {candidate_path}",
                )
        else:
            _verify_output_pin(candidate, f"sources.g1_days[{index}].candidate")
            opened_candidates += 1
        teacher = item.get("teacher")
        if teacher is not None:
            _verify_output_pin(teacher, f"sources.g1_days[{index}].teacher")
            opened_teachers += 1
    if opened_candidates != sources.get("opened_candidate_files"):
        raise JoinUnavailable("sources.opened_candidate_files", "candidate count drift")
    if opened_teachers != sources.get("opened_teacher_files"):
        raise JoinUnavailable("sources.opened_teacher_files", "teacher count drift")


def _line_scope(
    receipt: Mapping[str, object],
    line: str,
    scope: str,
) -> Mapping[str, object]:
    lines = receipt.get("lines")
    if not isinstance(lines, dict) or set(lines) != set(LINE_NAMES):
        raise JoinUnavailable("receipt.lines", f"line names {list(lines) if isinstance(lines, dict) else lines!r}")
    line_value = lines.get(line)
    if not isinstance(line_value, dict):
        raise JoinUnavailable(f"receipt.lines.{line}", "line expected object")
    scope_value = line_value.get(scope)
    if not isinstance(scope_value, dict):
        raise JoinUnavailable(f"receipt.lines.{line}.{scope}", "scope expected object")
    return scope_value


def _expected_pstar(rung: float, winner: float, loser: float) -> float | None:
    if winner <= loser:
        return None
    return float((rung - loser) / (winner - loser))


def _verify_derived(receipt: Mapping[str, object]) -> None:
    if receipt.get("schema") != SCHEMA:
        raise JoinUnavailable("receipt.schema", f"schema {receipt.get('schema')!r}")
    if receipt.get("line_names") != list(LINE_NAMES):
        raise JoinUnavailable("receipt.line_names", f"line names {receipt.get('line_names')!r}")
    ceiling = _read_json(CEILING_RECEIPT)
    for scope in ("gated", "ungated"):
        actual = dict(_line_scope(receipt, "cellbest_control", scope))
        for key in (
            "entered_cells",
            "eligible_candidates",
            "eligible_cells",
            "cells_without_ready",
            "selected_not_ready",
        ):
            actual.pop(key, None)
        if actual != ceiling.get(scope):
            raise JoinUnavailable("receipt.cellbest_control", f"{scope} control drift")
    accuracy = receipt.get("side_accuracy")
    if not isinstance(accuracy, dict) or not isinstance(accuracy.get("pairs"), dict):
        raise JoinUnavailable("receipt.side_accuracy", "side_accuracy expected object")
    pairs = cast(Mapping[str, object], accuracy["pairs"])
    pair_lines = {
        "price": ("sideoracle_price", "wrongside_price"),
        "earliest": ("sideoracle_earliest", "wrongside_earliest"),
    }
    for pair, (winner_name, loser_name) in pair_lines.items():
        values = pairs.get(pair)
        if not isinstance(values, dict):
            raise JoinUnavailable("receipt.side_accuracy", f"pair {pair} missing")
        winner_usd = cast(
            Mapping[str, float],
            _line_scope(receipt, winner_name, "gated")["usd_per_asset_day"],
        )
        loser_usd = cast(
            Mapping[str, float],
            _line_scope(receipt, loser_name, "gated")["usd_per_asset_day"],
        )
        for asset in ASSETS:
            actual = values.get(asset)
            if not isinstance(actual, dict):
                raise JoinUnavailable("receipt.side_accuracy", f"{pair}/{asset} missing")
            expected = _expected_pstar(
                float(RUNGS_USD[asset]),
                float(winner_usd[asset]),
                float(loser_usd[asset]),
            )
            if actual.get("p_star") != expected:
                raise JoinUnavailable(
                    "receipt.side_accuracy.p_star",
                    f"{pair}/{asset} {actual.get('p_star')!r} expected {expected!r}",
                )
    residual = receipt.get("path_residual_usd_per_asset_day")
    if not isinstance(residual, dict):
        raise JoinUnavailable("receipt.path_residual", "path residual expected object")
    control_usd = cast(
        Mapping[str, float],
        _line_scope(receipt, "cellbest_control", "gated")["usd_per_asset_day"],
    )
    price_usd = cast(
        Mapping[str, float],
        _line_scope(receipt, "sideoracle_price", "gated")["usd_per_asset_day"],
    )
    for asset in ASSETS:
        expected = float(control_usd[asset] - price_usd[asset])
        if residual.get(asset) != expected:
            raise JoinUnavailable("receipt.path_residual", f"{asset} residual drift")
    price_values = cast(Mapping[str, Mapping[str, object]], pairs["price"])
    blockers = []
    for asset in ASSETS:
        winner = float(price_values[asset]["W_usd_per_asset_day"])
        loser = float(price_values[asset]["L_usd_per_asset_day"])
        pstar = price_values[asset]["p_star"]
        if winner < float(RUNGS_USD[asset]) or winner <= loser:
            blockers.append(asset)
        if pstar is None or float(pstar) > PSTAR_LIMIT:
            blockers.append(asset)
    expected_verdict = "KILL" if blockers else "LIVE"
    if receipt.get("verdict") != expected_verdict:
        raise JoinUnavailable(
            "receipt.verdict",
            f"verdict {receipt.get('verdict')!r} expected {expected_verdict}",
        )


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


def _candidate(
    candidate_id: str,
    decision_ts_ns: int,
    side: int,
    entry_mid2: int,
) -> SideCandidate:
    return SideCandidate(
        candidate_id,
        "HG",
        20220310,
        0,
        decision_ts_ns,
        5.0,
        side,
        entry_mid2,
    )


def _outcome(
    candidate_id: str,
    decision_ts_ns: int,
    side: int,
    entry_mid2: int,
    status: str,
    cert_close_usd: float,
) -> CandidateOutcome:
    return CandidateOutcome(
        _candidate(candidate_id, decision_ts_ns, side, entry_mid2),
        status,
        cert_close_usd,
        decision_ts_ns + 100 if status == "READY" else None,
    )


def _selftest_guard() -> None:
    with tempfile.TemporaryDirectory(prefix="threshold-side-split-selftest-") as directory:
        path = Path(directory) / "candidates.tsv"
        path.write_text("candidate_id\noriginal\n")
        expected = _sha256_file(path)
        path.write_text("candidate_id\ncorrupted\n")
        try:
            _verify_file_sha(path, expected, "selftest.candidate_id")
        except JoinUnavailable:
            return
        raise AssertionError("selftest accepted a corrupted synthetic candidate_id")


def _selftest() -> int:
    if MUTANT and MUTANT not in KNOWN_MUTANTS:
        raise ValueError(f"unknown QRE2_SIDESPLIT_MUTANT {MUTANT!r}")
    _assert_contract()
    _selftest_guard()
    wrong_side_fixture = (
        _outcome("long", 20, 1, 100, "READY", 10.0),
        _outcome("short_max_cert", 10, -1, 200, "READY", 1000.0),
    )
    side_pick = _pick_price(wrong_side_fixture, 1)
    if side_pick is None or side_pick.candidate.candidate_id != "long":
        raise AssertionError(f"selftest wrong-side price pick {side_pick!r}")
    rows = (
        _outcome("long_nonready_price", 30, 1, 80, "NO_SANE_SUFFIX", 0.0),
        _outcome("long_ready_early", 10, 1, 100, "READY", -20.0),
        _outcome("long_ready_cert", 20, 1, 110, "READY", -10.0),
        _outcome("short_price", 40, -1, 130, "NO_SANE_SUFFIX", 0.0),
        _outcome("short_early", 5, -1, 120, "NO_SANE_SUFFIX", 0.0),
    )
    scored = _score_cell(rows)
    if tuple(scored.lines) != LINE_NAMES:
        raise AssertionError(f"selftest line names {tuple(scored.lines)!r}")
    price = scored.lines["sideoracle_price"].selected
    if price is None or price.candidate.candidate_id != "long_nonready_price":
        raise AssertionError(f"selftest CLEAR price eligibility {price!r}")
    if price.ready:
        raise AssertionError("selftest price control lost selected_not_ready fixture")
    earliest = scored.lines["sideoracle_earliest"].selected
    if earliest is None or earliest.candidate.candidate_id != "long_ready_early":
        raise AssertionError(f"selftest earliest oracle pick {earliest!r}")
    wrong_price = scored.lines["wrongside_price"].selected
    if wrong_price is None or wrong_price.candidate.candidate_id != "short_price":
        raise AssertionError(f"selftest wrong-side price control {wrong_price!r}")
    wrong_earliest = scored.lines["wrongside_earliest"].selected
    if wrong_earliest is None or wrong_earliest.candidate.candidate_id != "short_early":
        raise AssertionError(f"selftest wrong-side earliest control {wrong_earliest!r}")
    ready_price = scored.lines["sideoracle_price_ready"].selected
    if ready_price is None or ready_price.candidate.candidate_id != "long_ready_early":
        raise AssertionError(f"selftest READY price control {ready_price!r}")
    if scored.lines["cellbest_control"].selected is not None:
        raise AssertionError("selftest cellbest entered an all-negative cell")
    if _pstar(2000.0, 2500.0, 500.0) != 0.75:
        raise AssertionError("selftest p_star arithmetic drift")
    no_ready = _score_cell(
        (_outcome("missing", 1, 1, 10, "NO_SANE_SUFFIX", 0.0),)
    )
    if no_ready.has_ready or any(line.selected for line in no_ready.lines.values()):
        raise AssertionError(f"selftest no-READY cell entered {no_ready!r}")
    print("selftest_ok")
    return 0


def _verification_command(mutant: str | None) -> str:
    if mutant is None:
        return f"{CHECK} --selftest"
    return f"QRE2_SIDESPLIT_MUTANT={mutant} {CHECK} --selftest"


def _run_red_first_checks() -> dict[str, object]:
    checks: list[tuple[str, str | None]] = [("selftest", None)]
    checks.extend((name, name) for name in MUTANTS)
    checks.append(("guard_mutant", GUARD_MUTANT))
    results: dict[str, object] = {}
    for label, mutant in checks:
        env = dict(os.environ)
        env.pop("QRE2_SIDESPLIT_MUTANT", None)
        if mutant is not None:
            env["QRE2_SIDESPLIT_MUTANT"] = mutant
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
            raise JoinUnavailable(
                "verification.mutant",
                f"mutant {mutant!r} stayed green",
            )
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
    line = _line_scope(receipt, "sideoracle_price", "gated")
    accuracy = cast(Mapping[str, object], receipt["side_accuracy"])
    pairs = cast(Mapping[str, object], accuracy["pairs"])
    price = cast(Mapping[str, object], pairs["price"])
    pstars = {
        asset: cast(Mapping[str, object], price[asset])["p_star"] for asset in ASSETS
    }
    return (
        f"receipt={_relative(RECEIPT)} verdict={receipt.get('verdict')} "
        f"sideoracle_price={line.get('usd_per_asset_day')} "
        f"p_star={pstars} wall_clock_sec={receipt.get('wall_clock_sec')}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if args == ["--selftest"]:
        return _selftest()
    if args:
        raise ValueError(f"unsupported arguments {args}")
    if MUTANT:
        raise ValueError("QRE2_SIDESPLIT_MUTANT is allowed only with --selftest")
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
