#!/usr/bin/env python3
"""Causal fitted name pick on stored live G1 columns. Throwaway. Cannot promote."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

REPO = Path(__file__).resolve().parents[1]
RECEIPT = REPO / ".audit/threshold-fit-name.json"
CHECK = "python3 .audit/score_threshold_fit_name.py"
SCHEMA = "QRE2THRESHOLDFITNAME1"
LABEL = (
    "causal expanding-window fitted name pick on stored live G1 columns. "
    "It can name a capture fix and cannot promote."
)
RULE = (
    "On every joinable 2022-03-09 through 2024-12-31 gated cell, score every "
    "CLEAR name with LogisticRegression trained only on gated joinable cells "
    "whose d8 is strictly before that day. Binary target is is_cell_best "
    "among CLEAR names, the READY cell-best. Features are live only: "
    "decision_ts_ns as rank-in-cell, frozen_cost_usd, entry_spread_usd, "
    "compliance_distance_sec, sane_ceiling_usd, atr14_prev_usd, entry_mid2, "
    "side. Standardized. Pick the max score, tie-break smallest "
    "candidate_id. No train or one class falls back to earliest CLEAR. One "
    "contract per cell. Cash is cert_close_usd on READY. The day gate is the "
    "freeze expanding median. Teacher-cash still cannot promote."
)
WORKERS = 14
FEATURE_NAMES = (
    "time_rank",
    "frozen_cost_usd",
    "entry_spread_usd",
    "compliance_distance_sec",
    "sane_ceiling_usd",
    "atr14_prev_usd",
    "entry_mid2",
    "side",
)
BANNED_FEATURES = ("cert_close_usd",)


def _load_module(name: str):
    path = Path(__file__).with_name(name)
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module


_rank = _load_module("score_threshold_rank_live.py")
_gap = _rank._gap
_killed = _rank._killed
_ceiling = _rank._ceiling

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
_assert_no_peek = _killed._assert_no_peek
PEEK_COLS = _killed.PEEK_COLS
TEACHER_COLS = _killed.TEACHER_COLS
RANK_COLS = _rank.RANK_COLS
pick_cell_best_ready = _ceiling.pick_cell_best_ready
_ready_rows = _ceiling._ready_rows
_join_picked = _gap._join_picked
summarize_line = _ceiling.summarize_line
_load_rank_names = _rank._load_rank_names
RankName = _rank.RankName
FORECAST = _killed.FORECAST
CANDIDATES = _killed.CANDIDATES
TEACHERS = _killed.TEACHERS
RECEIPTS = _killed.RECEIPTS
KILLED_READ = _ceiling.KILLED_READ
FREEZE = _killed.FREEZE

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    _SKLEARN = True
except ImportError:
    _SKLEARN = False


@dataclass(frozen=True, slots=True)
class FitCell:
    names: tuple[object, ...]
    matrix: object
    winner_id: str | None


@dataclass(frozen=True, slots=True)
class DayBundle:
    asset: str
    d8: int
    joinable: bool
    selected: bool
    cells: tuple[FitCell, ...]
    teacher: Mapping[str, tuple[str, float, int]]
    cand_path: str
    teacher_path: str
    cand_sha: str
    teacher_sha: str


@dataclass(frozen=True, slots=True)
class FittedModel:
    kind: str
    mean: object
    scale: object
    coef: object
    intercept: float


def _empty_bundle(asset: str, d8: int, selected: bool, joinable: bool) -> DayBundle:
    return DayBundle(asset, d8, joinable, selected, (), {}, "", "", "", "")


def cell_time_ranks(names: Sequence[object]) -> dict[str, float]:
    ordered = sorted(names, key=lambda row: (row.decision_ts_ns, row.candidate_id))
    return {row.candidate_id: float(index) for index, row in enumerate(ordered)}


def name_features(row: object, time_rank: float) -> np.ndarray | None:
    values = np.asarray(
        [
            time_rank,
            float(row.frozen_cost_usd),
            float(row.entry_spread_usd),
            float(row.compliance_distance_sec),
            float(row.sane_ceiling_usd),
            float(row.atr14_prev_usd),
            float(row.entry_mid2),
            float(row.side),
        ],
        dtype=np.float64,
    )
    if values.shape != (len(FEATURE_NAMES),) or not np.all(np.isfinite(values)):
        return None
    return values


def build_cells(names: Sequence[object], teacher: Mapping[str, tuple[str, float, int]]) -> tuple[FitCell, ...]:
    by_cell: dict[tuple[str, int, int], list[object]] = {}
    for row in names:
        if row.phase not in PHASES:
            continue
        by_cell.setdefault((row.asset, row.d8, row.phase), []).append(row)
    winners = {
        (row.asset, row.d8, row.phase): row.candidate_id
        for row in pick_cell_best_ready(_ready_rows(names, teacher, "fit-name"))
    }
    cells: list[FitCell] = []
    for key in sorted(by_cell):
        group = by_cell[key]
        ranks = cell_time_ranks(group)
        kept: list[object] = []
        rows: list[np.ndarray] = []
        for row in group:
            feats = name_features(row, ranks[row.candidate_id])
            if feats is None:
                continue
            kept.append(row)
            rows.append(feats)
        if not kept:
            continue
        cells.append(
            FitCell(
                names=tuple(kept),
                matrix=np.vstack(rows),
                winner_id=winners.get(key),
            )
        )
    return tuple(cells)


def _standardize(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = matrix.mean(axis=0)
    scale = matrix.std(axis=0)
    scale = np.where(scale == 0.0, 1.0, scale)
    return (matrix - mean) / scale, mean, scale


def fit_model(matrix: np.ndarray | None, target: np.ndarray | None) -> FittedModel | None:
    if matrix is None or target is None or len(target) < 2:
        return None
    if int(target.min()) == int(target.max()):
        return None
    scaled, mean, scale = _standardize(matrix)
    if _SKLEARN:
        scaler = StandardScaler()
        trained = scaler.fit_transform(matrix)
        model = LogisticRegression(max_iter=250, solver="lbfgs", random_state=0)
        model.fit(trained, target)
        return FittedModel(
            "sklearn.LogisticRegression",
            scaler.mean_,
            scaler.scale_,
            model.coef_.ravel(),
            float(model.intercept_.ravel()[0]),
        )
    beta, *_ = np.linalg.lstsq(
        np.column_stack([np.ones(len(scaled)), scaled]),
        target.astype(np.float64),
        rcond=None,
    )
    return FittedModel("numpy.lstsq", mean, scale, beta[1:], float(beta[0]))


def score_names(model: FittedModel, matrix: np.ndarray) -> np.ndarray:
    scale = np.where(model.scale == 0.0, 1.0, model.scale)
    scaled = (matrix - model.mean) / scale
    return scaled @ model.coef + model.intercept


def pick_cell(cell: FitCell, model: FittedModel | None) -> tuple[object | None, bool]:
    if not cell.names:
        return None, False
    if model is None:
        winner = min(cell.names, key=lambda row: (row.decision_ts_ns, row.candidate_id))
        return winner, True
    scores = score_names(model, cell.matrix)
    best = 0
    for index, row in enumerate(cell.names):
        score = float(scores[index])
        best_score = float(scores[best])
        better = score > best_score or (
            score == best_score and row.candidate_id < cell.names[best].candidate_id
        )
        if better:
            best = index
    return cell.names[best], False


def walk_fitted(bundles: Sequence[DayBundle]) -> tuple[dict[tuple[str, int], tuple[object, ...]], dict[str, object]]:
    by_d8: dict[int, list[DayBundle]] = {}
    for bundle in bundles:
        if not bundle.joinable or not bundle.selected:
            continue
        by_d8.setdefault(bundle.d8, []).append(bundle)
    train_x: list[np.ndarray] = []
    train_y: list[np.ndarray] = []
    picks: dict[tuple[str, int], tuple[object, ...]] = {}
    n_fallback = 0
    n_picked = 0
    n_have_winner = 0
    n_match = 0
    n_train_cells = 0
    learner = "sklearn.LogisticRegression" if _SKLEARN else "numpy.lstsq"
    for d8 in sorted(by_d8):
        matrix = np.vstack(train_x) if train_x else None
        target = np.concatenate(train_y) if train_y else None
        model = fit_model(matrix, target)
        if model is not None:
            learner = model.kind
        for bundle in by_d8[d8]:
            chosen: list[object] = []
            for cell in bundle.cells:
                name, fallback = pick_cell(cell, model)
                if name is None:
                    continue
                chosen.append(name)
                n_picked += 1
                n_fallback += int(fallback)
                if cell.winner_id is None:
                    continue
                n_have_winner += 1
                n_match += int(name.candidate_id == cell.winner_id)
            picks[(bundle.asset, bundle.d8)] = tuple(chosen)
        for bundle in by_d8[d8]:
            for cell in bundle.cells:
                if cell.winner_id is None:
                    continue
                labels = np.asarray(
                    [int(row.candidate_id == cell.winner_id) for row in cell.names],
                    dtype=np.int64,
                )
                if int(labels.max()) == 0:
                    continue
                train_x.append(cell.matrix)
                train_y.append(labels)
                n_train_cells += 1
    last_rows = int(sum(len(block) for block in train_y))
    match_rate = (n_match / n_have_winner) if n_have_winner else 0.0
    return picks, {
        "learner": learner,
        "n_train_rows_last": last_rows,
        "n_train_cells_last": n_train_cells,
        "n_fallback_cells": n_fallback,
        "n_picked_cells": n_picked,
        "n_match_cell_best": n_match,
        "n_cells_with_winner": n_have_winner,
        "match_rate": match_rate,
    }


def _score_asset_day(asset: str, day: object, selected: bool) -> DayBundle:
    n_rows, names, cand_path = _load_rank_names(asset, day.d8)
    if cand_path is None or n_rows == 0:
        return _empty_bundle(asset, day.d8, selected, False)
    if not names:
        return _empty_bundle(asset, day.d8, selected, True)
    wanted = [row.candidate_id for row in names]
    teacher, teacher_path = _load_teacher(asset, day.d8, wanted)
    cand_receipt = RECEIPTS / asset / f"{day.d8}.candidates.json"
    teacher_receipt = RECEIPTS / asset / f"{day.d8}.teacher.json"
    return DayBundle(
        asset,
        day.d8,
        True,
        selected,
        build_cells(names, teacher),
        teacher,
        _relative(cand_path),
        _relative(teacher_path),
        _receipt_output_sha256(cand_receipt),
        _receipt_output_sha256(teacher_receipt),
    )


def _score_job(item: tuple[str, object, bool]) -> DayBundle:
    return _score_asset_day(*item)


def dollar_stop(line: object) -> dict[str, object]:
    if line.clears_rungs:
        verdict = "CAPTURED"
        applied = (
            "Fitted name pick clears the rungs on the stored join. "
            "That rule is the capture fix. Teacher-cash still cannot promote."
        )
    else:
        verdict = "MISS"
        applied = (
            "Fitted name pick misses the rungs. Remaining unknown is whether "
            "corpus features (ticket 47) can rank the winner. Teacher-cash "
            "still cannot promote. 2025 stays unread."
        )
    return {
        "verdict": verdict,
        "captured_live_rules": ["fitted"] if line.clears_rungs else [],
        "rungs_usd": dict(RUNGS_USD),
        "usd_per_asset_day": dict(line.usd_per_asset_day),
        "applied": applied,
    }


def _assert_live_features() -> None:
    if any(name in RANK_COLS for name in PEEK_COLS):
        raise JoinUnavailable("candidates.usecols", "fit usecols include peek columns")
    if any(name in TEACHER_COLS for name in PEEK_COLS):
        raise JoinUnavailable("teacher.usecols", "teacher usecols include peek columns")
    if any(name in FEATURE_NAMES for name in PEEK_COLS):
        raise JoinUnavailable("features", f"features include peek columns {PEEK_COLS}")
    leaked = [name for name in FEATURE_NAMES if name in BANNED_FEATURES]
    if leaked:
        raise JoinUnavailable("features", f"features include banned columns {leaked}")
    if "cert_close_usd" in RANK_COLS:
        raise JoinUnavailable("candidates.usecols", "rank usecols include cert_close_usd")


def build_receipt(wall_clock_sec: float) -> dict[str, object]:
    from concurrent.futures import ThreadPoolExecutor

    _assert_live_features()
    forecast_rows, _window_days, n_read = load_window_forecast_rows(FORECAST)
    routed, _empty = route_catboost_daily(forecast_rows)
    selected_flags = select_expanding_median(routed)
    jobs = [
        (asset, day, True)
        for day, flag in zip(routed, selected_flags)
        if flag
        for asset in ASSETS
    ]
    bundles: list[DayBundle] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for bundle in pool.map(_score_job, jobs):
            bundles.append(bundle)
    picks, fit = walk_fitted(bundles)
    days = {asset: 0 for asset in ASSETS}
    entries: list[object] = []
    for bundle in bundles:
        if not bundle.joinable or not bundle.selected:
            continue
        days[bundle.asset] += 1
        chosen = picks.get((bundle.asset, bundle.d8), ())
        entries.extend(
            _join_picked(
                chosen,
                bundle.teacher,
                bundle.cand_path,
                bundle.teacher_path,
                bundle.cand_sha,
                bundle.teacher_sha,
            )
        )
    if days != EXPECTED_GATED_DAYS:
        raise JoinUnavailable(
            "gated.days",
            f"fit-name days {days} != {EXPECTED_GATED_DAYS}",
        )
    line = summarize_line(entries, days)
    stop = dollar_stop(line)
    return {
        "schema": SCHEMA,
        "status": stop["verdict"],
        "verdict": stop["verdict"],
        "label": LABEL,
        "window": [WINDOW_START, WINDOW_END],
        "rule": RULE,
        "check_command": CHECK,
        "features": list(FEATURE_NAMES),
        "learner": fit["learner"],
        "fit": fit,
        "lines": {"fitted": line.as_dict()},
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


def _name(
    candidate_id: str,
    d8: int,
    phase: int,
    ts: int,
    cost: float,
    side: int,
    spread: float,
    distance: float,
    ceiling: float,
    atr: float,
    mid: float,
) -> object:
    return RankName(
        candidate_id,
        "HG",
        d8,
        phase,
        ts,
        cost,
        side,
        spread,
        distance,
        ceiling,
        atr,
        mid,
    )


def _selftest() -> int:
    if any(name in RANK_COLS for name in PEEK_COLS):
        raise AssertionError("selftest rank usecols parse peek columns")
    if any(name in FEATURE_NAMES for name in PEEK_COLS):
        raise AssertionError("selftest features parse peek columns")
    if "cert_close_usd" in FEATURE_NAMES or "cert_close_usd" in RANK_COLS:
        raise AssertionError("selftest features include cert_close_usd")
    early = _name("a", 20220310, 0, 10, 1.0, 1, 1.0, 10.0, 50.0, 10.0, 1.0)
    win = _name("w", 20220310, 0, 20, 1.0, -1, 50.0, 10.0, 50.0, 10.0, 2.0)
    late = _name("c", 20220310, 0, 30, 1.0, 1, 1.0, 10.0, 50.0, 10.0, 3.0)
    ranks = cell_time_ranks((late, early, win))
    if ranks != {"a": 0.0, "w": 1.0, "c": 2.0}:
        raise AssertionError(f"selftest time ranks {ranks}")
    teacher_d1 = {
        "a": ("READY", 1.0, 11),
        "w": ("READY", 90.0, 21),
        "c": ("READY", 3.0, 31),
    }
    cells_d1 = build_cells((early, win, late), teacher_d1)
    if len(cells_d1) != 1 or cells_d1[0].winner_id != "w":
        raise AssertionError(f"selftest day1 winner {cells_d1}")
    fallback, used_fallback = pick_cell(cells_d1[0], None)
    if fallback is None or fallback.candidate_id != "a" or not used_fallback:
        raise AssertionError(f"selftest fallback {fallback} {used_fallback}")
    equal = FittedModel(
        "numpy.lstsq",
        np.zeros(len(FEATURE_NAMES)),
        np.ones(len(FEATURE_NAMES)),
        np.zeros(len(FEATURE_NAMES)),
        0.0,
    )
    tied_a = _name("b", 20220310, 0, 10, 1.0, 1, 1.0, 10.0, 50.0, 10.0, 1.0)
    tied_b = _name("a", 20220310, 0, 20, 1.0, 1, 1.0, 10.0, 50.0, 10.0, 1.0)
    tied_cells = build_cells(
        (tied_a, tied_b),
        {"a": ("READY", 2.0, 21), "b": ("READY", 1.0, 11)},
    )
    tied_pick, _fallback = pick_cell(tied_cells[0], equal)
    if tied_pick is None or tied_pick.candidate_id != "a":
        raise AssertionError(f"selftest tie-break {tied_pick}")
    d2_early = _name("e2", 20220311, 0, 10, 1.0, 1, 1.0, 10.0, 50.0, 10.0, 1.0)
    d2_mid = _name("m2", 20220311, 0, 20, 1.0, 1, 1.0, 10.0, 50.0, 10.0, 2.0)
    d2_high = _name("h2", 20220311, 0, 30, 1.0, -1, 50.0, 10.0, 50.0, 10.0, 3.0)
    teacher_d2 = {
        "e2": ("READY", 80.0, 41),
        "m2": ("READY", 2.0, 51),
        "h2": ("READY", 3.0, 61),
    }
    cells_d2 = build_cells((d2_early, d2_mid, d2_high), teacher_d2)
    if cells_d2[0].winner_id != "e2":
        raise AssertionError(f"selftest day2 hindsight winner {cells_d2[0].winner_id}")
    bundle1 = DayBundle(
        "HG", 20220310, True, True, cells_d1, teacher_d1, "", "", "", ""
    )
    bundle2 = DayBundle(
        "HG", 20220311, True, True, cells_d2, teacher_d2, "", "", "", ""
    )
    picks, fit = walk_fitted((bundle1, bundle2))
    day1 = picks[("HG", 20220310)]
    day2 = picks[("HG", 20220311)]
    if [row.candidate_id for row in day1] != ["a"]:
        raise AssertionError(f"selftest day1 must fallback earliest {day1}")
    if [row.candidate_id for row in day2] != ["h2"]:
        raise AssertionError(f"selftest day2 must follow prior spread {day2}")
    if fit["n_fallback_cells"] != 1 or fit["n_picked_cells"] != 2:
        raise AssertionError(f"selftest fit counts {fit}")
    later = DayBundle("HG", 20220312, True, False, cells_d2, teacher_d2, "", "", "", "")
    ignored, _fit = walk_fitted((bundle1, later))
    if ("HG", 20220312) in ignored:
        raise AssertionError("selftest used an ungated day")
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
    miss_stop = dollar_stop(empty)
    if miss_stop["verdict"] != "MISS" or miss_stop["captured_live_rules"]:
        raise AssertionError(f"selftest MISS {miss_stop}")
    hit = dollar_stop(clear)
    if hit["verdict"] != "CAPTURED" or hit["captured_live_rules"] != ["fitted"]:
        raise AssertionError(f"selftest CAPTURED {hit}")
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
        f"usd_per_asset_day={receipt['lines']['fitted']['usd_per_asset_day']} "
        f"match_rate={receipt['fit']['match_rate']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
