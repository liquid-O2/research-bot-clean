#!/usr/bin/env python3
"""Rank stored 2021 dense features against READY cell-best. Throwaway. Cannot promote."""

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

REPO = Path(__file__).resolve().parents[1]
RECEIPT = REPO / ".audit/threshold-feature-rank.json"
CHECK = "python3 .audit/score_threshold_feature_rank.py"
SCHEMA = "QRE2THRESHOLDFEATURERANK1"
LABEL = (
    "causal expanding-window fitted rank of READY cell-best on stored 2021 "
    "dense shards. 2021 can kill and cannot promote."
)
RULE = (
    "On every joinable 20210721-20210806 asset-day that already has a dense "
    "shard, join the first snapshot of each CLEAR name to G1. Target is the "
    "READY cell-best. Score names with LogisticRegression trained only on "
    "joinable cells whose d8 is strictly before that day. Rank is the "
    "0-based index after sorting by score descending, then smallest "
    "candidate_id. No train or one class falls back to earliest CLEAR. Pick "
    "argmax and price it with teacher cert_close_usd on READY. Do not "
    "rematerialize. Teacher-cash still cannot promote."
)
WORKERS = 14
WINDOW_START_D8 = 20210721
WINDOW_END_D8 = 20210806
FEATURE_COUNT = 3505
SHARD_SCHEMA = "QRE2TABFEATURESHARD2"
DENSE = REPO / "artifacts/entry_v2/tabular_recovery/dense_store"


def _load_module(name: str):
    path = Path(__file__).with_name(name)
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module


_fit = _load_module("score_threshold_fit_name.py")
_rank = _fit._rank
_killed = _fit._killed
_ceiling = _fit._ceiling
_gap = _fit._gap

ASSETS = _killed.ASSETS
PHASES = _killed.PHASES
JoinUnavailable = _killed.JoinUnavailable
Candidate = _killed.Candidate
SelectedName = _killed.SelectedName
_load_candidates = _killed._load_candidates
_load_teacher = _killed._load_teacher
_sha256_file = _killed._sha256_file
_relative = _killed._relative
_receipt_output_sha256 = _killed._receipt_output_sha256
_assert_no_peek = _killed._assert_no_peek
PEEK_COLS = _killed.PEEK_COLS
CANDIDATES = _killed.CANDIDATES
TEACHERS = _killed.TEACHERS
RECEIPTS = _killed.RECEIPTS
pick_cell_best_ready = _ceiling.pick_cell_best_ready
_ready_rows = _ceiling._ready_rows
summarize_line = _ceiling.summarize_line
_join_picked = _gap._join_picked
column_stats = _rank.column_stats
ordinal_rank = _rank.ordinal_rank
fit_model = _fit.fit_model
score_names = _fit.score_names
pick_cell = _fit.pick_cell
FitCell = _fit.FitCell
FittedModel = _fit.FittedModel
CANDIDATE_COLS = _killed.CANDIDATE_COLS
TEACHER_COLS = _killed.TEACHER_COLS


@dataclass(frozen=True, slots=True)
class DayKey:
    d8: int


@dataclass(frozen=True, slots=True)
class ShardRef:
    asset: str
    d8: int
    identity: str
    artifact: Path


@dataclass(frozen=True, slots=True)
class DayBundle:
    asset: str
    d8: int
    joinable: bool
    selected: bool
    cells: tuple[object, ...]
    teacher: Mapping[str, tuple[str, float, int]]
    cand_path: str
    teacher_path: str
    cand_sha: str
    teacher_sha: str
    shard_identity: str
    feature_names: tuple[str, ...]


def _empty_bundle(asset: str, d8: int, selected: bool, joinable: bool) -> DayBundle:
    return DayBundle(asset, d8, joinable, selected, (), {}, "", "", "", "", "", ())


def _guard_window_day(d8: int, label: str) -> None:
    if d8 < WINDOW_START_D8 or d8 > WINDOW_END_D8:
        raise JoinUnavailable(
            "window.d8",
            f"{label} d8 {d8} is outside {WINDOW_START_D8}-{WINDOW_END_D8}",
        )


def discover_window_shards() -> dict[tuple[str, int], ShardRef]:
    found: dict[tuple[str, int], ShardRef] = {}
    if not DENSE.is_dir():
        raise JoinUnavailable("dense_store", f"missing dense store {DENSE}")
    for meta_path in DENSE.glob("*/*/*.json"):
        identity, asset, name = meta_path.relative_to(DENSE).parts
        if asset not in ASSETS or not name.endswith(".json"):
            continue
        day = name[: -len(".json")]
        if not day.isdigit():
            continue
        d8 = int(day)
        if d8 < WINDOW_START_D8 or d8 > WINDOW_END_D8:
            continue
        _guard_window_day(d8, "dense_store")
        meta = json.loads(meta_path.read_text())
        artifact = Path(str(meta["artifact_path"]))
        try:
            artifact.resolve().relative_to(DENSE.resolve())
        except ValueError as exc:
            raise JoinUnavailable(
                "dense_store.artifact",
                f"{artifact} is not under {DENSE}",
            ) from exc
        if not artifact.is_file():
            continue
        key = (asset, d8)
        prior = found.get(key)
        if prior is None or identity < prior.identity:
            found[key] = ShardRef(asset, d8, identity, artifact)
    return found


def first_indices(candidate_id: Sequence[str], snapshot_ts_ns: np.ndarray) -> dict[str, int]:
    chosen: dict[str, int] = {}
    best_ts: dict[str, int] = {}
    for index, cid in enumerate(candidate_id):
        ts = int(snapshot_ts_ns[index])
        prior = best_ts.get(cid)
        if prior is None or ts < prior:
            best_ts[cid] = ts
            chosen[cid] = index
    return chosen


def load_first_rows(path: Path) -> tuple[tuple[str, ...], dict[str, np.ndarray]]:
    with np.load(path, allow_pickle=False) as stored:
        if str(stored["schema"][0]) != SHARD_SCHEMA:
            raise JoinUnavailable(
                "dense_store.schema",
                f"{path} schema {stored['schema'][0]!r} != {SHARD_SCHEMA}",
            )
        names = tuple(stored["feature_names"].astype(str).tolist())
        if len(names) != FEATURE_COUNT:
            raise JoinUnavailable(
                "dense_store.feature_count",
                f"{path} feature_count {len(names)} != {FEATURE_COUNT}",
            )
        leaked = [name for name in names if name in PEEK_COLS]
        if leaked:
            raise JoinUnavailable("dense_store.features", f"{path} peek columns {leaked}")
        cids = stored["candidate_id"].astype(str)
        snaps = np.asarray(stored["snapshot_ts_ns"], np.int64)
        feats = stored["features"]
        chosen = first_indices(cids.tolist(), snaps)
        rows = {
            cid: np.asarray(feats[index], dtype=np.float64) for cid, index in chosen.items()
        }
    return names, rows


def build_cells(
    names: Sequence[object],
    teacher: Mapping[str, tuple[str, float, int]],
    features: Mapping[str, np.ndarray],
    feature_width: int,
) -> tuple[object, ...]:
    by_cell: dict[tuple[str, int, int], list[object]] = {}
    for row in names:
        if row.phase not in PHASES:
            continue
        by_cell.setdefault((row.asset, row.d8, row.phase), []).append(row)
    winners = {
        (row.asset, row.d8, row.phase): row.candidate_id
        for row in pick_cell_best_ready(_ready_rows(names, teacher, "feature-rank"))
    }
    cells: list[object] = []
    for key in sorted(by_cell):
        group = by_cell[key]
        kept: list[object] = []
        rows: list[np.ndarray] = []
        for row in group:
            feats = features.get(row.candidate_id)
            if feats is None or feats.shape != (feature_width,) or not np.all(np.isfinite(feats)):
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


def winner_rank(cell: object, model: object | None) -> int | None:
    if cell.winner_id is None:
        return None
    ids = [row.candidate_id for row in cell.names]
    if cell.winner_id not in ids:
        return None
    if model is None:
        pairs = [(row.candidate_id, float(row.decision_ts_ns)) for row in cell.names]
        return ordinal_rank(pairs, cell.winner_id, False)
    scores = score_names(model, cell.matrix)
    pairs = [(row.candidate_id, float(scores[index])) for index, row in enumerate(cell.names)]
    return ordinal_rank(pairs, cell.winner_id, True)


def walk_ranked(
    bundles: Sequence[DayBundle],
) -> tuple[dict[tuple[str, int], tuple[object, ...]], list[int], dict[str, object]]:
    by_d8: dict[int, list[DayBundle]] = {}
    for bundle in bundles:
        if not bundle.joinable or not bundle.selected:
            continue
        by_d8.setdefault(bundle.d8, []).append(bundle)
    train_x: list[np.ndarray] = []
    train_y: list[np.ndarray] = []
    picks: dict[tuple[str, int], tuple[object, ...]] = {}
    ranks: list[int] = []
    n_fallback = 0
    n_picked = 0
    n_have_winner = 0
    n_match = 0
    n_train_cells = 0
    learner = "sklearn.LogisticRegression" if _fit._SKLEARN else "numpy.lstsq"
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
                ranked = winner_rank(cell, model)
                if ranked is None:
                    continue
                ranks.append(ranked)
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
    return picks, ranks, {
        "learner": learner,
        "n_train_rows_last": last_rows,
        "n_train_cells_last": n_train_cells,
        "n_fallback_cells": n_fallback,
        "n_picked_cells": n_picked,
        "n_match_cell_best": n_match,
        "n_cells_with_winner": n_have_winner,
        "match_rate": match_rate,
    }


def _score_asset_day(asset: str, d8: int, shard: ShardRef | None) -> DayBundle:
    _guard_window_day(d8, "score")
    n_rows, names, cand_path = _load_candidates(asset, d8)
    if cand_path is None or n_rows == 0 or shard is None:
        return _empty_bundle(asset, d8, True, False)
    if not names:
        return _empty_bundle(asset, d8, True, True)
    feature_names, features = load_first_rows(shard.artifact)
    wanted = [row.candidate_id for row in names]
    teacher, teacher_path = _load_teacher(asset, d8, wanted)
    cand_receipt = RECEIPTS / asset / f"{d8}.candidates.json"
    teacher_receipt = RECEIPTS / asset / f"{d8}.teacher.json"
    return DayBundle(
        asset,
        d8,
        True,
        True,
        build_cells(names, teacher, features, len(feature_names)),
        teacher,
        _relative(cand_path),
        _relative(teacher_path),
        _receipt_output_sha256(cand_receipt),
        _receipt_output_sha256(teacher_receipt),
        shard.identity,
        feature_names,
    )


def _score_job(item: tuple[str, int, ShardRef | None]) -> DayBundle:
    return _score_asset_day(*item)


def dollar_stop(
    stats: Mapping[str, float | int],
    usd_per_asset_day: Mapping[str, float],
) -> dict[str, object]:
    mean_rank = float(stats["mean_winner_rank"])
    top5 = float(stats["frac_top5"])
    if mean_rank <= 2.0 or top5 >= 0.50:
        verdict = "RANKS"
        applied = (
            "Stored 2021 corpus features put the READY cell-best near the top. "
            "Ticket 47 is licensed as the 2022-2024 copy of a signal that "
            "already exists. Teacher-cash still cannot promote."
        )
    else:
        verdict = "MISS"
        applied = (
            "Stored 2021 corpus features do not put mean_winner_rank at or "
            "under 2.0 or frac_top5 at or above 0.50. Ticket 47 as motivated "
            "is dead spend, and the covering answer is that no remaining "
            "stored instrument recovers identity. Teacher-cash still cannot "
            "promote."
        )
    return {
        "verdict": verdict,
        "mean_winner_rank": mean_rank,
        "frac_top5": top5,
        "usd_per_asset_day": dict(usd_per_asset_day),
        "applied": applied,
    }


def build_receipt(wall_clock_sec: float) -> dict[str, object]:
    if any(name in CANDIDATE_COLS for name in PEEK_COLS):
        raise JoinUnavailable("candidates.usecols", "feature-rank usecols include peek columns")
    if any(name in TEACHER_COLS for name in PEEK_COLS):
        raise JoinUnavailable("teacher.usecols", "teacher usecols include peek columns")
    shards = discover_window_shards()
    jobs = [(ref.asset, ref.d8, ref) for ref in shards.values()]
    jobs.sort(key=lambda item: (item[1], item[0]))
    bundles: list[DayBundle] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for bundle in pool.map(_score_job, jobs):
            bundles.append(bundle)
    name_sets = {bundle.feature_names for bundle in bundles if bundle.feature_names}
    if len(name_sets) != 1:
        raise JoinUnavailable(
            "dense_store.feature_names",
            f"window shards do not share one 3505-name order, got {len(name_sets)} sets",
        )
    feature_names = next(iter(name_sets))
    picks, ranks, fit = walk_ranked(bundles)
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
    line = summarize_line(entries, days)
    stats = column_stats(ranks)
    stop = dollar_stop(stats, line.usd_per_asset_day)
    return {
        "schema": SCHEMA,
        "status": stop["verdict"],
        "verdict": stop["verdict"],
        "label": LABEL,
        "window": ["2021-07-21", "2021-08-06"],
        "rule": RULE,
        "check_command": CHECK,
        "feature_count": FEATURE_COUNT,
        "features_head": list(feature_names[:8]),
        "learner": fit["learner"],
        "fit": fit,
        "ranks": stats,
        "lines": {"argmax": line.as_dict()},
        "dollar_stop": stop,
        "n_shards": len(shards),
        "n_forecast_rows_read": 0,
        "workers": WORKERS,
        "wall_clock_sec": wall_clock_sec,
        "sources": {
            "dense_store": _relative(DENSE),
            "shards": [
                {
                    "asset": ref.asset,
                    "d8": ref.d8,
                    "identity": ref.identity,
                    "path": _relative(ref.artifact),
                }
                for ref in sorted(shards.values(), key=lambda row: (row.d8, row.asset))
            ],
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


def _name(candidate_id: str, d8: int, phase: int, ts: int, cost: float) -> object:
    return Candidate(candidate_id, "HG", d8, phase, ts, cost)


def _selftest() -> int:
    if any(name in CANDIDATE_COLS for name in PEEK_COLS):
        raise AssertionError("selftest candidate usecols parse peek columns")
    if any(name in TEACHER_COLS for name in PEEK_COLS):
        raise AssertionError("selftest teacher usecols parse peek columns")
    try:
        _guard_window_day(20220309, "selftest")
    except JoinUnavailable:
        pass
    else:
        raise AssertionError("selftest allowed a 2022 day")
    cids = ["a", "a", "b", "b"]
    snaps = np.asarray([30, 10, 40, 20], dtype=np.int64)
    if first_indices(cids, snaps) != {"a": 1, "b": 3}:
        raise AssertionError(f"selftest first_indices {first_indices(cids, snaps)}")
    early = _name("a", 20210721, 0, 10, 1.0)
    win = _name("w", 20210721, 0, 20, 1.0)
    late = _name("c", 20210721, 0, 30, 1.0)
    teacher_d1 = {
        "a": ("READY", 1.0, 11),
        "w": ("READY", 90.0, 21),
        "c": ("READY", 3.0, 31),
    }
    feats_d1 = {
        "a": np.asarray([0.0, 1.0], dtype=np.float64),
        "w": np.asarray([9.0, 1.0], dtype=np.float64),
        "c": np.asarray([1.0, 1.0], dtype=np.float64),
    }
    cells_d1 = build_cells((early, win, late), teacher_d1, feats_d1, 2)
    if len(cells_d1) != 1 or cells_d1[0].winner_id != "w":
        raise AssertionError(f"selftest day1 winner {cells_d1}")
    if winner_rank(cells_d1[0], None) != 1:
        raise AssertionError(f"selftest fallback rank {winner_rank(cells_d1[0], None)}")
    d2_early = _name("e2", 20210722, 0, 10, 1.0)
    d2_mid = _name("m2", 20210722, 0, 20, 1.0)
    d2_high = _name("h2", 20210722, 0, 30, 1.0)
    teacher_d2 = {
        "e2": ("READY", 2.0, 41),
        "m2": ("READY", 3.0, 51),
        "h2": ("READY", 80.0, 61),
    }
    feats_d2 = {
        "e2": np.asarray([0.0, 1.0], dtype=np.float64),
        "m2": np.asarray([1.0, 1.0], dtype=np.float64),
        "h2": np.asarray([9.0, 1.0], dtype=np.float64),
    }
    cells_d2 = build_cells((d2_early, d2_mid, d2_high), teacher_d2, feats_d2, 2)
    bundle1 = DayBundle(
        "HG", 20210721, True, True, cells_d1, teacher_d1, "", "", "", "", "", ()
    )
    bundle2 = DayBundle(
        "HG", 20210722, True, True, cells_d2, teacher_d2, "", "", "", "", "", ()
    )
    picks, ranks, fit = walk_ranked((bundle1, bundle2))
    day1 = picks[("HG", 20210721)]
    day2 = picks[("HG", 20210722)]
    if [row.candidate_id for row in day1] != ["a"]:
        raise AssertionError(f"selftest day1 must fallback earliest {day1}")
    if [row.candidate_id for row in day2] != ["h2"]:
        raise AssertionError(f"selftest day2 must follow prior high feature {day2}")
    if ranks != [1, 0]:
        raise AssertionError(f"selftest ranks {ranks}")
    if fit["n_fallback_cells"] != 1 or fit["n_match_cell_best"] != 1:
        raise AssertionError(f"selftest fit {fit}")
    stats = column_stats((0, 1, 2, 10))
    if stats["n_cells"] != 4 or stats["frac_rank0"] != 0.25 or stats["frac_top5"] != 0.75:
        raise AssertionError(f"selftest stats {stats}")
    if stats["mean_winner_rank"] != 3.25:
        raise AssertionError(f"selftest mean {stats['mean_winner_rank']}")
    miss = dollar_stop(column_stats((10, 20, 30)), {"HG": 0.0, "NKD": 0.0, "SI": 0.0})
    if miss["verdict"] != "MISS":
        raise AssertionError(f"selftest MISS {miss}")
    hit_mean = dollar_stop(column_stats((0, 1, 2)), {"HG": 1.0, "NKD": 1.0, "SI": 1.0})
    if hit_mean["verdict"] != "RANKS":
        raise AssertionError(f"selftest RANKS mean {hit_mean}")
    hit_top5 = dollar_stop(column_stats((0, 3, 4, 20)), {"HG": 1.0, "NKD": 1.0, "SI": 1.0})
    if hit_top5["verdict"] != "RANKS":
        raise AssertionError(f"selftest RANKS top5 {hit_top5}")
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
        f"mean_winner_rank={receipt['ranks']['mean_winner_rank']} "
        f"frac_top5={receipt['ranks']['frac_top5']} "
        f"usd_per_asset_day={receipt['lines']['argmax']['usd_per_asset_day']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
