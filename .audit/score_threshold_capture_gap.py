#!/usr/bin/env python3
"""Why earliest CLEAR misses cell-best cash. Throwaway. Cannot promote."""

from __future__ import annotations

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

REPO = Path(__file__).resolve().parents[1]
RECEIPT = REPO / ".audit/threshold-capture-gap.json"
CHECK = "python3 .audit/score_threshold_capture_gap.py"
SCHEMA = "QRE2THRESHOLDCAPTUREGAP1"
LABEL = (
    "live name pick versus cell-best on the stored join. "
    "It can name the miss and cannot promote."
)
RULE = (
    "On every joinable 2022-03-09 through 2024-12-31 cell, compare the killed "
    "read's earliest CLEAR to the latest CLEAR, the cheapest frozen_cost CLEAR, "
    "and the READY teacher with maximum cert_close_usd. Score each live rule "
    "the same way as the killed read: one contract per cell, cash is "
    "cert_close_usd on READY. Cell-best enters only when that maximum is "
    "positive. The day gate is the freeze expanding median."
)


def _load_module(name: str):
    path = Path(__file__).with_name(name)
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module


_killed = _load_module("score_threshold_2022_2024_read.py")
_ceiling = _load_module("score_threshold_2022_2024_ceiling.py")

ASSETS = _killed.ASSETS
PHASES = _killed.PHASES
WORKERS = _killed.WORKERS
WINDOW_START = _killed.WINDOW_START
WINDOW_END = _killed.WINDOW_END
RUNGS_USD = _killed.RUNGS_USD
EXPECTED_GATED_DAYS = _ceiling.EXPECTED_GATED_DAYS
Candidate = _killed.Candidate
SelectedName = _killed.SelectedName
ReadyPick = _ceiling.ReadyPick
JoinUnavailable = _killed.JoinUnavailable
route_catboost_daily = _killed.route_catboost_daily
select_expanding_median = _killed.select_expanding_median
load_window_forecast_rows = _killed.load_window_forecast_rows
_load_candidates = _killed._load_candidates
_load_teacher = _killed._load_teacher
_sha256_file = _killed._sha256_file
_relative = _killed._relative
_receipt_output_sha256 = _killed._receipt_output_sha256
cash_usd = _killed.cash_usd
summarize_line = _ceiling.summarize_line
enter_positive = _ceiling.enter_positive
pick_cell_best_ready = _ceiling.pick_cell_best_ready
_ready_rows = _ceiling._ready_rows
_as_selected = _ceiling._as_selected
FORECAST = _killed.FORECAST
CANDIDATES = _killed.CANDIDATES
TEACHERS = _killed.TEACHERS
RECEIPTS = _killed.RECEIPTS
KILLED_READ = _ceiling.KILLED_READ
FREEZE = _killed.FREEZE


@dataclass(frozen=True, slots=True)
class CellMiss:
    asset: str
    d8: int
    phase: int
    n_clear: int
    best_time_rank: int
    earliest_id: str
    best_id: str
    earliest_is_best: bool
    earliest_cash: float
    best_cash: float


@dataclass(frozen=True, slots=True)
class DayBundle:
    asset: str
    d8: int
    joinable: bool
    selected: bool
    earliest: tuple[object, ...]
    latest: tuple[object, ...]
    cheapest: tuple[object, ...]
    best: tuple[object, ...]
    misses: tuple[CellMiss, ...]


def pick_latest_clear(rows: Sequence[Candidate]) -> tuple[Candidate, ...]:
    best: dict[tuple[str, int, int], Candidate] = {}
    for row in rows:
        if row.phase not in PHASES:
            continue
        key = (row.asset, row.d8, row.phase)
        prior = best.get(key)
        if prior is None or (row.decision_ts_ns, row.candidate_id) > (
            prior.decision_ts_ns,
            prior.candidate_id,
        ):
            best[key] = row
    return tuple(best[key] for key in sorted(best))


def pick_cheapest_clear(rows: Sequence[Candidate]) -> tuple[Candidate, ...]:
    best: dict[tuple[str, int, int], Candidate] = {}
    for row in rows:
        if row.phase not in PHASES:
            continue
        key = (row.asset, row.d8, row.phase)
        prior = best.get(key)
        if prior is None or (row.frozen_cost_usd, row.candidate_id) < (
            prior.frozen_cost_usd,
            prior.candidate_id,
        ):
            best[key] = row
    return tuple(best[key] for key in sorted(best))


def _join_picked(
    picked: Sequence[Candidate],
    teacher: Mapping[str, tuple[str, float, int]],
    cand_path: str,
    teacher_path: str,
    cand_sha: str,
    teacher_sha: str,
) -> tuple[object, ...]:
    names: list[object] = []
    for row in picked:
        hit = teacher.get(row.candidate_id)
        if hit is None:
            status, cert, exit_ts = "MISSING", 0.0, None
        else:
            status, cert, exit_ts = hit
        names.append(
            SelectedName(
                candidate_id=row.candidate_id,
                asset=row.asset,
                d8=row.d8,
                phase=row.phase,
                decision_ts_ns=row.decision_ts_ns,
                frozen_cost_usd=row.frozen_cost_usd,
                cash_usd=cash_usd(status, cert),
                exit_ts_ns=exit_ts,
                ready=status == "READY",
                source_candidates=cand_path,
                source_teacher=teacher_path,
                candidates_output_sha256=cand_sha,
                teacher_output_sha256=teacher_sha,
            )
        )
    return tuple(names)


def _cell_misses(
    clear: Sequence[Candidate],
    teacher: Mapping[str, tuple[str, float, int]],
) -> tuple[CellMiss, ...]:
    by_cell: dict[tuple[str, int, int], list[Candidate]] = {}
    for row in clear:
        if row.phase not in PHASES:
            continue
        by_cell.setdefault((row.asset, row.d8, row.phase), []).append(row)
    misses: list[CellMiss] = []
    for key in sorted(by_cell):
        ordered = sorted(
            by_cell[key],
            key=lambda row: (row.decision_ts_ns, row.candidate_id),
        )
        earliest = ordered[0]
        ready = []
        for row in ordered:
            hit = teacher.get(row.candidate_id)
            if hit is None or hit[0] != "READY":
                continue
            ready.append((row, float(hit[1])))
        if not ready:
            continue
        winner = ready[0]
        for item in ready[1:]:
            if item[1] > winner[1] or (
                item[1] == winner[1] and item[0].candidate_id < winner[0].candidate_id
            ):
                winner = item
        best_row, best_cash = winner
        rank = next(
            index
            for index, row in enumerate(ordered)
            if row.candidate_id == best_row.candidate_id
        )
        earliest_hit = teacher.get(earliest.candidate_id)
        earliest_cash = (
            cash_usd(earliest_hit[0], earliest_hit[1]) if earliest_hit else 0.0
        )
        misses.append(
            CellMiss(
                asset=key[0],
                d8=key[1],
                phase=key[2],
                n_clear=len(ordered),
                best_time_rank=rank,
                earliest_id=earliest.candidate_id,
                best_id=best_row.candidate_id,
                earliest_is_best=earliest.candidate_id == best_row.candidate_id,
                earliest_cash=earliest_cash,
                best_cash=best_cash,
            )
        )
    return tuple(misses)


def _score_asset_day(asset: str, day: object, selected: bool) -> DayBundle:
    n_rows, candidates, cand_path = _load_candidates(asset, day.d8)
    if cand_path is None or n_rows == 0:
        return DayBundle(asset, day.d8, False, selected, (), (), (), (), ())
    cand_receipt = RECEIPTS / asset / f"{day.d8}.candidates.json"
    cand_sha = _receipt_output_sha256(cand_receipt)
    if not candidates:
        return DayBundle(asset, day.d8, True, selected, (), (), (), (), ())
    wanted = [row.candidate_id for row in candidates]
    teacher, teacher_path = _load_teacher(asset, day.d8, wanted)
    teacher_receipt = RECEIPTS / asset / f"{day.d8}.teacher.json"
    teacher_sha = _receipt_output_sha256(teacher_receipt)
    rel_c = _relative(cand_path)
    rel_t = _relative(teacher_path)
    earliest = _join_picked(
        _killed.pick_cell_names(candidates),
        teacher,
        rel_c,
        rel_t,
        cand_sha,
        teacher_sha,
    )
    latest = _join_picked(
        pick_latest_clear(candidates),
        teacher,
        rel_c,
        rel_t,
        cand_sha,
        teacher_sha,
    )
    cheapest = _join_picked(
        pick_cheapest_clear(candidates),
        teacher,
        rel_c,
        rel_t,
        cand_sha,
        teacher_sha,
    )
    ready = _ready_rows(candidates, teacher, rel_t)
    best = _as_selected(
        enter_positive(pick_cell_best_ready(ready)),
        rel_c,
        rel_t,
        cand_sha,
        teacher_sha,
    )
    return DayBundle(
        asset,
        day.d8,
        True,
        selected,
        earliest,
        latest,
        cheapest,
        best,
        _cell_misses(candidates, teacher),
    )


def _score_job(item: tuple[str, object, bool]) -> DayBundle:
    return _score_asset_day(*item)


def _gated_line(bundles: Sequence[DayBundle], attr: str):
    days = {asset: 0 for asset in ASSETS}
    entries: list[object] = []
    for bundle in bundles:
        if not bundle.joinable or not bundle.selected:
            continue
        days[bundle.asset] += 1
        entries.extend(getattr(bundle, attr))
    return summarize_line(entries, days)


def _capture_stats(misses: Sequence[CellMiss]) -> dict[str, object]:
    if not misses:
        return {
            "n_cells": 0,
            "n_earliest_is_best": 0,
            "match_rate": 0.0,
            "mean_best_time_rank": 0.0,
            "mean_cell_n_clear": 0.0,
            "cash_left_on_table_usd": 0.0,
            "best_time_rank_hist": {},
        }
    matched = sum(1 for row in misses if row.earliest_is_best)
    cash_left = sum(row.best_cash - row.earliest_cash for row in misses)
    hist = Counter(row.best_time_rank for row in misses)
    return {
        "n_cells": len(misses),
        "n_earliest_is_best": matched,
        "match_rate": matched / len(misses),
        "mean_best_time_rank": sum(row.best_time_rank for row in misses) / len(misses),
        "mean_cell_n_clear": sum(row.n_clear for row in misses) / len(misses),
        "cash_left_on_table_usd": cash_left,
        "best_time_rank_hist": {str(key): hist[key] for key in sorted(hist)},
    }


def _live_clears(lines: Mapping[str, object]) -> list[str]:
    hits = []
    for name in ("earliest", "latest", "cheapest"):
        line = lines[name]
        if line.clears_rungs:
            hits.append(name)
    return hits


def dollar_stop(lines: Mapping[str, object], stats: Mapping[str, object]) -> dict[str, object]:
    captured = _live_clears(lines)
    if captured:
        verdict = "CAPTURED"
        applied = (
            f"Live rule {captured} clears the rungs on the stored join. "
            "That rule is the capture fix. Teacher-cash still cannot promote."
        )
    else:
        verdict = "MISS"
        applied = (
            "Earliest, latest, and cheapest CLEAR all miss the rungs. "
            f"Earliest matches cell-best in {stats['n_earliest_is_best']} of "
            f"{stats['n_cells']} cells (match_rate {stats['match_rate']:.4f}). "
            f"Mean time rank of the winner is {stats['mean_best_time_rank']:.2f} "
            f"in a mean cell of {stats['mean_cell_n_clear']:.1f} CLEAR names. "
            "The miss is within-cell identity, not a missing ceiling, and not "
            "first-versus-last or frozen_cost. Next unit is one live G1 scalar "
            "that is not time or cost, or one fitted name instrument. "
            "Teacher-cash still cannot promote."
        )
    return {
        "verdict": verdict,
        "captured_live_rules": captured,
        "rungs_usd": dict(RUNGS_USD),
        "applied": applied,
    }


def build_receipt(wall_clock_sec: float) -> dict[str, object]:
    forecast_rows, _window_days, n_read = load_window_forecast_rows(FORECAST)
    routed, _empty = route_catboost_daily(forecast_rows)
    selected_flags = select_expanding_median(routed)
    jobs = [
        (asset, day, bool(flag))
        for day, flag in zip(routed, selected_flags)
        for asset in ASSETS
    ]
    bundles: list[DayBundle] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for bundle in pool.map(_score_job, jobs):
            bundles.append(bundle)
    lines = {
        "earliest": _gated_line(bundles, "earliest"),
        "latest": _gated_line(bundles, "latest"),
        "cheapest": _gated_line(bundles, "cheapest"),
        "cell_best": _gated_line(bundles, "best"),
    }
    if lines["earliest"].days != EXPECTED_GATED_DAYS:
        raise JoinUnavailable(
            "gated.days",
            f"earliest days {lines['earliest'].days} != {EXPECTED_GATED_DAYS}",
        )
    misses = tuple(
        miss
        for bundle in bundles
        if bundle.joinable and bundle.selected
        for miss in bundle.misses
    )
    stats = _capture_stats(misses)
    stop = dollar_stop(lines, stats)
    return {
        "schema": SCHEMA,
        "status": stop["verdict"],
        "verdict": stop["verdict"],
        "label": LABEL,
        "window": [WINDOW_START, WINDOW_END],
        "rule": RULE,
        "check_command": CHECK,
        "capture": stats,
        "lines": {name: line.as_dict() for name, line in lines.items()},
        "dollar_stop": stop,
        "n_forecast_rows_read": n_read,
        "workers": WORKERS,
        "wall_clock_sec": wall_clock_sec,
        "sources": {
            "forecasts": {
                "path": _relative(FORECAST),
                "sha256": _sha256_file(FORECAST),
            },
            "freeze": {"path": _relative(FREEZE), "sha256": _sha256_file(FREEZE)},
            "killed_read": {
                "path": _relative(KILLED_READ),
                "sha256": _sha256_file(KILLED_READ),
            },
            "candidates_root": _relative(CANDIDATES),
            "teacher_root": _relative(TEACHERS),
            "receipts_root": _relative(RECEIPTS),
        },
    }


def _write_receipt(value: Mapping[str, object]) -> None:
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    temporary = RECEIPT.with_name(f"{RECEIPT.name}.tmp.{os.getpid()}")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, RECEIPT)


def _selftest() -> int:
    early = Candidate("early", "HG", 20220314, 0, 10, 30.0)
    late = Candidate("late", "HG", 20220314, 0, 40, 5.0)
    mid = Candidate("mid", "HG", 20220314, 0, 20, 10.0)
    if [row.candidate_id for row in pick_latest_clear((early, late, mid))] != ["late"]:
        raise AssertionError("selftest latest")
    if [row.candidate_id for row in pick_cheapest_clear((early, late, mid))] != ["late"]:
        raise AssertionError("selftest cheapest")
    teacher = {
        "early": ("READY", -50.0, 20),
        "mid": ("READY", 10.0, 30),
        "late": ("READY", 100.0, 50),
    }
    misses = _cell_misses((early, mid, late), teacher)
    if len(misses) != 1 or misses[0].best_id != "late" or misses[0].best_time_rank != 2:
        raise AssertionError(f"selftest miss {misses}")
    if misses[0].earliest_is_best:
        raise AssertionError("selftest earliest should miss the winner")
    stats = _capture_stats(misses)
    if stats["match_rate"] != 0.0 or stats["n_cells"] != 1:
        raise AssertionError(f"selftest stats {stats}")
    empty = summarize_line((), {"HG": 1, "NKD": 1, "SI": 1})
    clear = summarize_line(
        (
            SelectedName(
                "h", "HG", 20220314, 0, 10, 5.0, 2000.0, 20, True, "", None, "", None
            ),
            SelectedName(
                "n", "NKD", 20220314, 0, 11, 5.0, 1500.0, 21, True, "", None, "", None
            ),
            SelectedName(
                "s", "SI", 20220314, 0, 12, 5.0, 1500.0, 22, True, "", None, "", None
            ),
        ),
        {"HG": 1, "NKD": 1, "SI": 1},
    )
    miss_stop = dollar_stop(
        {"earliest": empty, "latest": empty, "cheapest": empty, "cell_best": clear},
        stats,
    )
    if miss_stop["verdict"] != "MISS":
        raise AssertionError(f"selftest MISS {miss_stop}")
    captured = dollar_stop(
        {"earliest": empty, "latest": clear, "cheapest": empty, "cell_best": clear},
        stats,
    )
    if captured["verdict"] != "CAPTURED" or captured["captured_live_rules"] != ["latest"]:
        raise AssertionError(f"selftest CAPTURED {captured}")
    print("selftest_ok")
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
    capture = receipt["capture"]
    print(
        f"receipt={_relative(RECEIPT)} verdict={receipt['verdict']} "
        f"match_rate={capture['match_rate']} "
        f"mean_best_time_rank={capture['mean_best_time_rank']} "
        f"latest={receipt['lines']['latest']['usd_per_asset_day']} "
        f"cheapest={receipt['lines']['cheapest']['usd_per_asset_day']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
