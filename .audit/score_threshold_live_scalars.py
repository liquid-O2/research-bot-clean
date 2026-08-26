#!/usr/bin/env python3
"""Live G1 scalar picks on the stored join. Throwaway. Cannot promote."""

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

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
RECEIPT = REPO / ".audit/threshold-live-scalars.json"
CHECK = "python3 .audit/score_threshold_live_scalars.py"
SCHEMA = "QRE2THRESHOLDLIVESCALARS1"
LABEL = (
    "one live G1 scalar pick per gated cell on the stored join. "
    "It can name a capture fix and cannot promote."
)
RULE = (
    "On every joinable 2022-03-09 through 2024-12-31 gated cell, pick among "
    "CLEAR names using one live G1 column at a time: min or max "
    "entry_spread_usd, min or max compliance_distance_sec, min "
    "sane_ceiling_usd, max atr14_prev_usd, or the earlier CLEAR on the "
    "majority side. Tie-break lexicographically smallest candidate_id. "
    "One contract per cell. Cash is cert_close_usd on READY. The day gate "
    "is the freeze expanding median. Teacher-cash still cannot promote."
)
WORKERS = 14
LIVE_EXTRA_COLS = (
    "side",
    "entry_spread_usd",
    "compliance_distance_sec",
    "sane_ceiling_usd",
    "atr14_prev_usd",
)
SCALAR_RULES = (
    ("min_entry_spread_usd", "entry_spread_usd", False),
    ("max_entry_spread_usd", "entry_spread_usd", True),
    ("min_compliance_distance_sec", "compliance_distance_sec", False),
    ("max_compliance_distance_sec", "compliance_distance_sec", True),
    ("min_sane_ceiling_usd", "sane_ceiling_usd", False),
    ("max_atr14_prev_usd", "atr14_prev_usd", True),
)
RULE_NAMES = tuple(name for name, _column, _want_max in SCALAR_RULES) + ("side",)


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
_gap = _load_module("score_threshold_capture_gap.py")

ASSETS = _killed.ASSETS
PHASES = _killed.PHASES
WINDOW_START = _killed.WINDOW_START
WINDOW_END = _killed.WINDOW_END
RUNGS_USD = _killed.RUNGS_USD
EXPECTED_GATED_DAYS = _ceiling.EXPECTED_GATED_DAYS
JoinUnavailable = _killed.JoinUnavailable
SelectedName = _killed.SelectedName
route_catboost_daily = _killed.route_catboost_daily
select_expanding_median = _killed.select_expanding_median
load_window_forecast_rows = _killed.load_window_forecast_rows
_load_teacher = _killed._load_teacher
_sha256_file = _killed._sha256_file
_relative = _killed._relative
_receipt_output_sha256 = _killed._receipt_output_sha256
cash_usd = _killed.cash_usd
_assert_no_peek = _killed._assert_no_peek
PEEK_COLS = _killed.PEEK_COLS
CANDIDATE_COLS = _killed.CANDIDATE_COLS
TEACHER_COLS = _killed.TEACHER_COLS
summarize_line = _ceiling.summarize_line
_join_picked = _gap._join_picked
FORECAST = _killed.FORECAST
CANDIDATES = _killed.CANDIDATES
TEACHERS = _killed.TEACHERS
RECEIPTS = _killed.RECEIPTS
KILLED_READ = _ceiling.KILLED_READ
FREEZE = _killed.FREEZE
LIVE_COLS = CANDIDATE_COLS + LIVE_EXTRA_COLS


@dataclass(frozen=True, slots=True)
class LiveName:
    candidate_id: str
    asset: str
    d8: int
    phase: int
    decision_ts_ns: int
    frozen_cost_usd: float
    side: int
    entry_spread_usd: float
    compliance_distance_sec: float
    sane_ceiling_usd: float
    atr14_prev_usd: float


@dataclass(frozen=True, slots=True)
class DayBundle:
    asset: str
    d8: int
    joinable: bool
    selected: bool
    picks: Mapping[str, tuple[object, ...]]


def _empty_picks() -> dict[str, tuple[object, ...]]:
    return {name: () for name in RULE_NAMES}


def _load_live_names(
    asset: str, d8: int
) -> tuple[int, tuple[LiveName, ...], Path | None]:
    path = CANDIDATES / asset / f"{d8}.tsv"
    if not path.is_file():
        return 0, (), None
    _assert_no_peek(LIVE_COLS, "candidates")
    frame = pd.read_csv(
        path,
        sep="\t",
        skiprows=1,
        usecols=list(LIVE_COLS),
        dtype={
            "candidate_id": str,
            "asset": str,
            "d8": np.int64,
            "phase": np.int64,
            "decision_ts_ns": np.int64,
            "compliance_status": str,
            "frozen_cost_usd": np.float64,
            "side": np.int64,
            "entry_spread_usd": np.float64,
            "compliance_distance_sec": np.float64,
            "sane_ceiling_usd": np.float64,
            "atr14_prev_usd": np.float64,
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
    rows = tuple(
        LiveName(
            candidate_id=str(row.candidate_id),
            asset=str(row.asset),
            d8=int(row.d8),
            phase=int(row.phase),
            decision_ts_ns=int(row.decision_ts_ns),
            frozen_cost_usd=float(row.frozen_cost_usd),
            side=int(row.side),
            entry_spread_usd=float(row.entry_spread_usd),
            compliance_distance_sec=float(row.compliance_distance_sec),
            sane_ceiling_usd=float(row.sane_ceiling_usd),
            atr14_prev_usd=float(row.atr14_prev_usd),
        )
        for row in clear.itertuples(index=False)
    )
    return n_rows, rows, path


def pick_scalar(
    rows: Sequence[LiveName], column: str, want_max: bool
) -> tuple[LiveName, ...]:
    best: dict[tuple[str, int, int], LiveName] = {}
    best_val: dict[tuple[str, int, int], float] = {}
    for row in rows:
        if row.phase not in PHASES:
            continue
        value = float(getattr(row, column))
        if not np.isfinite(value):
            continue
        key = (row.asset, row.d8, row.phase)
        prior = best.get(key)
        if prior is None:
            best[key] = row
            best_val[key] = value
            continue
        tied = value == best_val[key] and row.candidate_id < prior.candidate_id
        better = (value > best_val[key] if want_max else value < best_val[key]) or tied
        if better:
            best[key] = row
            best_val[key] = value
    return tuple(best[key] for key in sorted(best))


def pick_majority_side(rows: Sequence[LiveName]) -> tuple[LiveName, ...]:
    by_cell: dict[tuple[str, int, int], list[LiveName]] = {}
    for row in rows:
        if row.phase not in PHASES:
            continue
        by_cell.setdefault((row.asset, row.d8, row.phase), []).append(row)
    picked: list[LiveName] = []
    for key in sorted(by_cell):
        group = by_cell[key]
        counts = Counter(row.side for row in group)
        top = max(counts.values())
        majority = {side for side, n in counts.items() if n == top}
        eligible = [row for row in group if row.side in majority]
        winner = min(eligible, key=lambda row: (row.decision_ts_ns, row.candidate_id))
        picked.append(winner)
    return tuple(picked)


def _score_asset_day(asset: str, day: object, selected: bool) -> DayBundle:
    n_rows, names, cand_path = _load_live_names(asset, day.d8)
    if cand_path is None or n_rows == 0:
        return DayBundle(asset, day.d8, False, selected, _empty_picks())
    cand_receipt = RECEIPTS / asset / f"{day.d8}.candidates.json"
    cand_sha = _receipt_output_sha256(cand_receipt)
    if not names:
        return DayBundle(asset, day.d8, True, selected, _empty_picks())
    wanted = [row.candidate_id for row in names]
    teacher, teacher_path = _load_teacher(asset, day.d8, wanted)
    teacher_receipt = RECEIPTS / asset / f"{day.d8}.teacher.json"
    teacher_sha = _receipt_output_sha256(teacher_receipt)
    rel_c = _relative(cand_path)
    rel_t = _relative(teacher_path)
    picks: dict[str, tuple[object, ...]] = {}
    for name, column, want_max in SCALAR_RULES:
        picks[name] = _join_picked(
            pick_scalar(names, column, want_max),
            teacher,
            rel_c,
            rel_t,
            cand_sha,
            teacher_sha,
        )
    picks["side"] = _join_picked(
        pick_majority_side(names),
        teacher,
        rel_c,
        rel_t,
        cand_sha,
        teacher_sha,
    )
    return DayBundle(asset, day.d8, True, selected, picks)


def _score_job(item: tuple[str, object, bool]) -> DayBundle:
    return _score_asset_day(*item)


def _gated_rule(bundles: Sequence[DayBundle], name: str):
    days = {asset: 0 for asset in ASSETS}
    entries: list[object] = []
    for bundle in bundles:
        if not bundle.joinable or not bundle.selected:
            continue
        days[bundle.asset] += 1
        entries.extend(bundle.picks[name])
    return summarize_line(entries, days)


def _live_clears(lines: Mapping[str, object]) -> list[str]:
    return [name for name in RULE_NAMES if lines[name].clears_rungs]


def dollar_stop(lines: Mapping[str, object]) -> dict[str, object]:
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
            "Every named live G1 scalar misses the rungs. Remaining unit is "
            "a fitted name instrument, still one frozen-rule teacher-cash "
            "read, still cannot promote."
        )
    return {
        "verdict": verdict,
        "captured_live_rules": captured,
        "rungs_usd": dict(RUNGS_USD),
        "applied": applied,
    }


def build_receipt(wall_clock_sec: float) -> dict[str, object]:
    if any(name in LIVE_COLS for name in PEEK_COLS):
        raise JoinUnavailable("candidates.usecols", "live usecols include peek columns")
    if any(name in TEACHER_COLS for name in PEEK_COLS):
        raise JoinUnavailable("teacher.usecols", "teacher usecols include peek columns")
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
    lines = {name: _gated_rule(bundles, name) for name in RULE_NAMES}
    days = lines[RULE_NAMES[0]].days
    if days != EXPECTED_GATED_DAYS:
        raise JoinUnavailable(
            "gated.days",
            f"live-scalar days {days} != {EXPECTED_GATED_DAYS}",
        )
    stop = dollar_stop(lines)
    return {
        "schema": SCHEMA,
        "status": stop["verdict"],
        "verdict": stop["verdict"],
        "label": LABEL,
        "window": [WINDOW_START, WINDOW_END],
        "rule": RULE,
        "check_command": CHECK,
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
    if any(name in LIVE_COLS for name in PEEK_COLS):
        raise AssertionError("selftest live usecols parse peek columns")
    tight = LiveName("a", "HG", 20220314, 0, 30, 8.0, -1, 5.0, 10.0, 100.0, 20.0)
    wide = LiveName("b", "HG", 20220314, 0, 10, 4.0, 1, 25.0, 40.0, 400.0, 80.0)
    mid = LiveName("c", "HG", 20220314, 0, 20, 6.0, -1, 5.0, 10.0, 100.0, 80.0)
    other = LiveName("d", "HG", 20220314, 1, 15, 7.0, 1, 15.0, 5.0, 50.0, 10.0)
    rows = (tight, wide, mid, other)
    if [row.candidate_id for row in pick_scalar(rows, "entry_spread_usd", False)] != [
        "a",
        "d",
    ]:
        raise AssertionError("selftest min spread")
    if [row.candidate_id for row in pick_scalar(rows, "entry_spread_usd", True)] != [
        "b",
        "d",
    ]:
        raise AssertionError("selftest max spread")
    if [
        row.candidate_id for row in pick_scalar(rows, "compliance_distance_sec", False)
    ] != ["a", "d"]:
        raise AssertionError("selftest min distance")
    if [row.candidate_id for row in pick_scalar(rows, "atr14_prev_usd", True)] != [
        "b",
        "d",
    ]:
        raise AssertionError("selftest max atr")
    mixed = pick_majority_side((tight, wide, mid))
    if [row.candidate_id for row in mixed] != ["c"]:
        raise AssertionError(f"selftest majority side {mixed}")
    tied = pick_majority_side((tight, wide))
    if [row.candidate_id for row in tied] != ["b"]:
        raise AssertionError(f"selftest tied-side earliest {tied}")
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
    miss_lines = {name: empty for name in RULE_NAMES}
    miss_stop = dollar_stop(miss_lines)
    if miss_stop["verdict"] != "MISS":
        raise AssertionError(f"selftest MISS {miss_stop}")
    captured_lines = {name: empty for name in RULE_NAMES}
    captured_lines["min_entry_spread_usd"] = clear
    captured = dollar_stop(captured_lines)
    if captured["verdict"] != "CAPTURED" or captured["captured_live_rules"] != [
        "min_entry_spread_usd"
    ]:
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
    usd = {
        name: receipt["lines"][name]["usd_per_asset_day"] for name in RULE_NAMES
    }
    print(
        f"receipt={_relative(RECEIPT)} verdict={receipt['verdict']} "
        f"captured={receipt['dollar_stop']['captured_live_rules']} "
        f"usd_per_asset_day={usd}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
