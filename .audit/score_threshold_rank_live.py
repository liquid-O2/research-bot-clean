#!/usr/bin/env python3
"""Rank live G1 columns against READY cell-best. Throwaway. Cannot promote."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
RECEIPT = REPO / ".audit/threshold-rank-live.json"
CHECK = "python3 .audit/score_threshold_rank_live.py"
SCHEMA = "QRE2THRESHOLDRANKLIVE1"
LABEL = (
    "live G1 column rank of READY cell-best on the stored join. "
    "It can name a frozen pick and cannot promote."
)
RULE = (
    "On every joinable 2022-03-09 through 2024-12-31 gated cell that has a "
    "READY teacher name, take the READY cell-best (maximum cert_close_usd, "
    "tie-break lexicographically smallest candidate_id). Rank every CLEAR "
    "name in that cell by each live G1 column, ascending and descending. "
    "Rank is the 0-based index after sorting by the column, then "
    "lexicographically smallest candidate_id. The day gate is the freeze "
    "expanding median. Teacher-cash still cannot promote."
)
WORKERS = 14
RANK_COLUMNS = (
    "decision_ts_ns",
    "frozen_cost_usd",
    "entry_spread_usd",
    "compliance_distance_sec",
    "sane_ceiling_usd",
    "atr14_prev_usd",
    "entry_mid2",
    "side",
)
DIRECTIONS = ("asc", "desc")
RANK_KEYS = tuple(
    f"{column}_{direction}" for column in RANK_COLUMNS for direction in DIRECTIONS
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


_gap = _load_module("score_threshold_capture_gap.py")
_live = _load_module("score_threshold_live_scalars.py")
_killed = _gap._killed
_ceiling = _gap._ceiling
RANK_EXTRA_COLS = _live.LIVE_EXTRA_COLS + ("entry_mid2",)

ASSETS = _killed.ASSETS
PHASES = _killed.PHASES
WINDOW_START = _killed.WINDOW_START
WINDOW_END = _killed.WINDOW_END
EXPECTED_GATED_DAYS = _ceiling.EXPECTED_GATED_DAYS
JoinUnavailable = _killed.JoinUnavailable
route_catboost_daily = _killed.route_catboost_daily
select_expanding_median = _killed.select_expanding_median
load_window_forecast_rows = _killed.load_window_forecast_rows
_load_teacher = _killed._load_teacher
_sha256_file = _killed._sha256_file
_relative = _killed._relative
_assert_no_peek = _killed._assert_no_peek
PEEK_COLS = _killed.PEEK_COLS
CANDIDATE_COLS = _killed.CANDIDATE_COLS
TEACHER_COLS = _killed.TEACHER_COLS
pick_cell_best_ready = _ceiling.pick_cell_best_ready
_ready_rows = _ceiling._ready_rows
FORECAST = _killed.FORECAST
CANDIDATES = _killed.CANDIDATES
TEACHERS = _killed.TEACHERS
RECEIPTS = _killed.RECEIPTS
KILLED_READ = _ceiling.KILLED_READ
FREEZE = _killed.FREEZE
RANK_COLS = CANDIDATE_COLS + RANK_EXTRA_COLS


@dataclass(frozen=True, slots=True)
class RankName:
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
    entry_mid2: float


@dataclass(frozen=True, slots=True)
class DayBundle:
    asset: str
    d8: int
    joinable: bool
    selected: bool
    ranks: Mapping[str, tuple[int, ...]]


def _empty_ranks() -> dict[str, tuple[int, ...]]:
    return {key: () for key in RANK_KEYS}


def _load_rank_names(
    asset: str, d8: int
) -> tuple[int, tuple[RankName, ...], Path | None]:
    path = CANDIDATES / asset / f"{d8}.tsv"
    if not path.is_file():
        return 0, (), None
    _assert_no_peek(RANK_COLS, "candidates")
    frame = pd.read_csv(
        path,
        sep="\t",
        skiprows=1,
        usecols=list(RANK_COLS),
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
            "entry_mid2": np.float64,
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
        RankName(
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
            entry_mid2=float(row.entry_mid2),
        )
        for row in clear.itertuples(index=False)
    )
    return n_rows, rows, path


def ordinal_rank(
    pairs: Sequence[tuple[str, float]], winner_id: str, descending: bool
) -> int:
    if descending:
        ordered = sorted(pairs, key=lambda item: (-item[1], item[0]))
    else:
        ordered = sorted(pairs, key=lambda item: (item[1], item[0]))
    for index, (candidate_id, _value) in enumerate(ordered):
        if candidate_id == winner_id:
            return index
    raise ValueError(
        f"winner {winner_id!r} missing from ranked pairs { [item[0] for item in pairs] }"
    )


def rank_cell(
    names: Sequence[RankName], winner_id: str
) -> dict[str, int] | None:
    by_id = {row.candidate_id: row for row in names}
    if winner_id not in by_id:
        return None
    out: dict[str, int] = {}
    for column in RANK_COLUMNS:
        pairs: list[tuple[str, float]] = []
        for row in names:
            value = float(getattr(row, column))
            if not np.isfinite(value):
                continue
            pairs.append((row.candidate_id, value))
        if winner_id not in {candidate_id for candidate_id, _value in pairs}:
            continue
        out[f"{column}_asc"] = ordinal_rank(pairs, winner_id, False)
        out[f"{column}_desc"] = ordinal_rank(pairs, winner_id, True)
    return out


def _score_asset_day(asset: str, day: object, selected: bool) -> DayBundle:
    n_rows, names, cand_path = _load_rank_names(asset, day.d8)
    if cand_path is None or n_rows == 0:
        return DayBundle(asset, day.d8, False, selected, _empty_ranks())
    if not names:
        return DayBundle(asset, day.d8, True, selected, _empty_ranks())
    wanted = [row.candidate_id for row in names]
    teacher, teacher_path = _load_teacher(asset, day.d8, wanted)
    ready = _ready_rows(names, teacher, _relative(teacher_path))
    winners = pick_cell_best_ready(ready)
    by_cell: dict[tuple[str, int, int], list[RankName]] = {}
    for row in names:
        if row.phase not in PHASES:
            continue
        by_cell.setdefault((row.asset, row.d8, row.phase), []).append(row)
    collected: dict[str, list[int]] = {key: [] for key in RANK_KEYS}
    for winner in winners:
        group = by_cell.get((winner.asset, winner.d8, winner.phase))
        if not group:
            continue
        ranked = rank_cell(group, winner.candidate_id)
        if ranked is None:
            continue
        for key, rank in ranked.items():
            collected[key].append(rank)
    return DayBundle(
        asset,
        day.d8,
        True,
        selected,
        {key: tuple(collected[key]) for key in RANK_KEYS},
    )


def _score_job(item: tuple[str, object, bool]) -> DayBundle:
    return _score_asset_day(*item)


def column_stats(ranks: Sequence[int]) -> dict[str, float | int]:
    n_cells = len(ranks)
    if n_cells == 0:
        return {
            "mean_winner_rank": 0.0,
            "median_winner_rank": 0.0,
            "n_cells": 0,
            "frac_rank0": 0.0,
            "frac_top5": 0.0,
        }
    arr = np.asarray(ranks, dtype=np.int64)
    return {
        "mean_winner_rank": float(arr.mean()),
        "median_winner_rank": float(np.median(arr)),
        "n_cells": int(n_cells),
        "frac_rank0": float(np.mean(arr == 0)),
        "frac_top5": float(np.mean(arr <= 4)),
    }


def dollar_stop(
    stats: Mapping[str, Mapping[str, float | int]],
) -> dict[str, object]:
    hits = [
        name
        for name in RANK_KEYS
        if float(stats[name]["mean_winner_rank"]) <= 2.0
        or float(stats[name]["frac_top5"]) >= 0.50
    ]
    if hits:
        verdict = "RANKS"
        applied = (
            f"Column-direction {hits} puts the READY cell-best near the top "
            "on the stored join. That column is the next frozen pick. "
            "Teacher-cash still cannot promote."
        )
    else:
        verdict = "MISS"
        applied = (
            "No live G1 column-direction puts mean_winner_rank at or under "
            "2.0 or frac_top5 at or above 0.50. Remaining unit is a fitted "
            "name instrument on stored join features, still one teacher-cash "
            "read, still cannot promote."
        )
    return {
        "verdict": verdict,
        "ranking_columns": hits,
        "applied": applied,
    }


def build_receipt(wall_clock_sec: float) -> dict[str, object]:
    if any(name in RANK_COLS for name in PEEK_COLS):
        raise JoinUnavailable("candidates.usecols", "rank usecols include peek columns")
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
    days = {asset: 0 for asset in ASSETS}
    collected: dict[str, list[int]] = {key: [] for key in RANK_KEYS}
    for bundle in bundles:
        if not bundle.joinable or not bundle.selected:
            continue
        days[bundle.asset] += 1
        for key in RANK_KEYS:
            collected[key].extend(bundle.ranks[key])
    if days != EXPECTED_GATED_DAYS:
        raise JoinUnavailable(
            "gated.days",
            f"rank-live days {days} != {EXPECTED_GATED_DAYS}",
        )
    stats = {key: column_stats(collected[key]) for key in RANK_KEYS}
    stop = dollar_stop(stats)
    return {
        "schema": SCHEMA,
        "status": stop["verdict"],
        "verdict": stop["verdict"],
        "label": LABEL,
        "window": [WINDOW_START, WINDOW_END],
        "rule": RULE,
        "check_command": CHECK,
        "ranks": stats,
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
    if any(name in RANK_COLS for name in PEEK_COLS):
        raise AssertionError("selftest rank usecols parse peek columns")
    low = RankName("a", "HG", 20220314, 0, 10, 1.0, 1, 5.0, 40.0, 50.0, 10.0, 1.0)
    mid = RankName("b", "HG", 20220314, 0, 20, 8.0, -1, 10.0, 20.0, 200.0, 80.0, 2.0)
    win = RankName("w", "HG", 20220314, 0, 30, 5.0, -1, 10.0, 10.0, 100.0, 40.0, 3.0)
    high = RankName("c", "HG", 20220314, 0, 40, 2.0, 1, 20.0, 5.0, 400.0, 20.0, 4.0)
    other = RankName("d", "HG", 20220314, 1, 15, 7.0, 1, 15.0, 5.0, 50.0, 10.0, 9.0)
    ranked = rank_cell((low, mid, win, high), "w")
    if ranked is None:
        raise AssertionError("selftest missing winner")
    expected = {
        "decision_ts_ns_asc": 2,
        "decision_ts_ns_desc": 1,
        "frozen_cost_usd_asc": 2,
        "frozen_cost_usd_desc": 1,
        "entry_spread_usd_asc": 2,
        "entry_spread_usd_desc": 2,
        "compliance_distance_sec_asc": 1,
        "compliance_distance_sec_desc": 2,
        "sane_ceiling_usd_asc": 1,
        "sane_ceiling_usd_desc": 2,
        "atr14_prev_usd_asc": 2,
        "atr14_prev_usd_desc": 1,
        "entry_mid2_asc": 2,
        "entry_mid2_desc": 1,
        "side_asc": 1,
        "side_desc": 3,
    }
    if ranked != expected:
        raise AssertionError(f"selftest ranks {ranked} != {expected}")
    if rank_cell((low, mid, high), "w") is not None:
        raise AssertionError("selftest winner absent from CLEAR set")
    constant_atr = rank_cell(
        (
            RankName("a", "HG", 20220314, 0, 10, 1.0, 1, 5.0, 40.0, 250.0, 10.0, 1.0),
            RankName("b", "HG", 20220314, 0, 20, 8.0, -1, 10.0, 20.0, 250.0, 10.0, 2.0),
            RankName("w", "HG", 20220314, 0, 30, 5.0, -1, 10.0, 10.0, 250.0, 10.0, 3.0),
        ),
        "w",
    )
    if constant_atr is None:
        raise AssertionError("selftest constant winner missing")
    if (
        constant_atr["atr14_prev_usd_asc"] != 2
        or constant_atr["atr14_prev_usd_desc"] != 2
        or constant_atr["sane_ceiling_usd_asc"] != 2
    ):
        raise AssertionError(f"selftest constant column {constant_atr}")
    teacher = {
        "a": ("READY", 1.0, 11),
        "b": ("READY", 2.0, 21),
        "w": ("READY", 9.0, 31),
        "c": ("READY", 3.0, 41),
        "d": ("READY", 8.0, 16),
    }
    ready = _ready_rows((low, mid, win, high, other), teacher, "selftest")
    winners = pick_cell_best_ready(ready)
    if [row.candidate_id for row in winners] != ["w", "d"]:
        raise AssertionError(f"selftest winners {[row.candidate_id for row in winners]}")
    stats = column_stats((0, 1, 2, 10))
    if stats["n_cells"] != 4 or stats["frac_rank0"] != 0.25 or stats["frac_top5"] != 0.75:
        raise AssertionError(f"selftest stats {stats}")
    if stats["mean_winner_rank"] != 3.25:
        raise AssertionError(f"selftest mean {stats['mean_winner_rank']}")
    miss = {key: column_stats((10, 20, 30)) for key in RANK_KEYS}
    miss_stop = dollar_stop(miss)
    if miss_stop["verdict"] != "MISS" or miss_stop["ranking_columns"]:
        raise AssertionError(f"selftest MISS {miss_stop}")
    ranks_hit = {key: column_stats((10, 20, 30)) for key in RANK_KEYS}
    ranks_hit["entry_spread_usd_asc"] = column_stats((0, 1, 2))
    hit = dollar_stop(ranks_hit)
    if hit["verdict"] != "RANKS" or hit["ranking_columns"] != ["entry_spread_usd_asc"]:
        raise AssertionError(f"selftest RANKS {hit}")
    top5 = {key: column_stats((10, 20, 30)) for key in RANK_KEYS}
    top5["side_desc"] = column_stats((0, 3, 4, 20))
    top5_stop = dollar_stop(top5)
    if top5_stop["verdict"] != "RANKS" or top5_stop["ranking_columns"] != ["side_desc"]:
        raise AssertionError(f"selftest frac_top5 {top5_stop}")
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
    print(
        f"receipt={_relative(RECEIPT)} verdict={receipt['verdict']} "
        f"ranking_columns={receipt['dollar_stop']['ranking_columns']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
