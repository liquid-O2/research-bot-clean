#!/usr/bin/env python3
"""Stored-join name rules on the unscanned live plane. Throwaway."""

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
RECEIPT = REPO / ".audit/threshold-stored-name-rules.json"
COVERING_BRIEF = REPO / ".audit/briefs/threshold-covering-after-stored-kill-out.md"
SPECIFICATION_BRIEF = REPO / ".audit/briefs/threshold-stored-name-rules.md"
FULL_ROSTER_CEILING = REPO / ".audit/threshold-2022-2024-ceiling.json"
RANK_LIVE_SCRIPT = REPO / ".audit/score_threshold_rank_live.py"
LIVE_SCALARS_SCRIPT = REPO / ".audit/score_threshold_live_scalars.py"
CHECK = "python3 .audit/score_threshold_stored_name_rules.py"
SCHEMA = "QRE2THRESHOLDSTOREDNAMERULES1"
LABEL = (
    "eight causal stored-join name rules on the unscanned live plane, plus an "
    "exploratory hindsight setter ceiling. Teacher-cash can kill and cannot promote."
)
RULE = (
    "On every joinable 2022-03-09 through 2024-12-31 gated cell, order CLEAR "
    "names by (decision_ts_ns, candidate_id), derive ordinal recency and strict "
    "same-side running-extreme setters, and apply each of the eight preregistered "
    "causal name rules. Pick one contract per cell. Cash is cert_close_usd on "
    "READY. The day gate is the freeze expanding median."
)
PEEK_NOTE = (
    "candidate-side columns widen; teacher-side license is unchanged from "
    "rank-live and capture-gap; kill instrument, cannot promote."
)
WORKERS = 14
RULES = {
    "ordinal_freshest": (
        "Min recency. Tie max decision_ts_ns. Tie smallest candidate_id."
    ),
    "ordinal_stalest": (
        "Max recency. Tie max decision_ts_ns. Tie smallest candidate_id."
    ),
    "ordinal_latest_event": (
        "Max confirmation_event_ordinal. Tie smallest candidate_id."
    ),
    "extreme_last_setter": "Setter with max decision_ts_ns.",
    "extreme_deepest_setter": (
        "Setter with max excess. Tie max decision_ts_ns."
    ),
    "extreme_first_nontrivial_setter": (
        "Earliest setter with excess > 0. Fallback earliest CLEAR."
    ),
    "spread_prior_max": (
        "Max spread_prior_usd among spread_prior_present == 1. "
        "Fallback earliest CLEAR."
    ),
    "spread_prior_min": (
        "Min spread_prior_usd among spread_prior_present == 1. "
        "Fallback earliest CLEAR."
    ),
}
RULE_NAMES = tuple(RULES)
CANDIDATE_EXTRA_COLS = (
    "confirmation_event_ordinal",
    "prefix_last_event_ordinal",
    "spread_prior_usd",
    "spread_prior_present",
    "entry_mid2",
    "side",
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


_live = _load_module("score_threshold_live_scalars.py")
_killed = _live._killed
_ceiling = _live._ceiling
_gap = _live._gap

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
summarize_line = _ceiling.summarize_line
pick_cell_best_ready = _ceiling.pick_cell_best_ready
enter_positive = _ceiling.enter_positive
_ready_rows = _ceiling._ready_rows
_as_selected = _ceiling._as_selected
_join_picked = _gap._join_picked
FORECAST = _killed.FORECAST
CANDIDATES = _killed.CANDIDATES
TEACHERS = _killed.TEACHERS
RECEIPTS = _killed.RECEIPTS
KILLED_READ = _ceiling.KILLED_READ
FREEZE = _killed.FREEZE
STORED_COLS = CANDIDATE_COLS + CANDIDATE_EXTRA_COLS


@dataclass(frozen=True, slots=True)
class StoredName:
    candidate_id: str
    asset: str
    d8: int
    phase: int
    decision_ts_ns: int
    frozen_cost_usd: float
    confirmation_event_ordinal: int
    prefix_last_event_ordinal: int
    spread_prior_usd: float
    spread_prior_present: int
    entry_mid2: float
    side: int


@dataclass(frozen=True, slots=True)
class SetterMark:
    row: StoredName
    excess: float | None


@dataclass(frozen=True, slots=True)
class RulePicks:
    causal: Mapping[str, tuple[StoredName, ...]]
    setters: tuple[StoredName, ...]


@dataclass(frozen=True, slots=True)
class DayBundle:
    asset: str
    d8: int
    joinable: bool
    selected: bool
    picks: Mapping[str, tuple[object, ...]]
    ceiling_setters: tuple[object, ...]


def _empty_picks() -> dict[str, tuple[object, ...]]:
    return {name: () for name in RULE_NAMES}


def _validate_candidate(row: object, path: Path) -> None:
    candidate_id = str(row.candidate_id)
    side = int(row.side)
    entry_mid2 = float(row.entry_mid2)
    present = int(row.spread_prior_present)
    spread = float(row.spread_prior_usd)
    if side not in (-1, 1):
        raise JoinUnavailable(
            "candidates.side",
            f"{path} candidate {candidate_id!r} side {side!r} expected -1 or 1",
        )
    if not np.isfinite(entry_mid2):
        raise JoinUnavailable(
            "candidates.entry_mid2",
            f"{path} candidate {candidate_id!r} entry_mid2 {entry_mid2!r} "
            "expected finite",
        )
    if present not in (0, 1):
        raise JoinUnavailable(
            "candidates.spread_prior_present",
            f"{path} candidate {candidate_id!r} spread_prior_present {present!r} "
            "expected 0 or 1",
        )
    if present == 1 and not np.isfinite(spread):
        raise JoinUnavailable(
            "candidates.spread_prior_usd",
            f"{path} candidate {candidate_id!r} spread_prior_usd {spread!r} "
            "expected finite when present",
        )


def _load_stored_names(
    asset: str, d8: int
) -> tuple[int, tuple[StoredName, ...], Path | None]:
    path = CANDIDATES / asset / f"{d8}.tsv"
    if not path.is_file():
        return 0, (), None
    _assert_no_peek(STORED_COLS, "candidates")
    frame = pd.read_csv(
        path,
        sep="\t",
        skiprows=1,
        usecols=list(STORED_COLS),
        dtype={
            "candidate_id": str,
            "asset": str,
            "d8": np.int64,
            "phase": np.int64,
            "decision_ts_ns": np.int64,
            "compliance_status": str,
            "frozen_cost_usd": np.float64,
            "confirmation_event_ordinal": np.int64,
            "prefix_last_event_ordinal": np.int64,
            "spread_prior_usd": np.float64,
            "spread_prior_present": np.int64,
            "entry_mid2": np.float64,
            "side": np.int64,
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
    for row in clear.itertuples(index=False):
        _validate_candidate(row, path)
    rows = tuple(
        StoredName(
            candidate_id=str(row.candidate_id),
            asset=str(row.asset),
            d8=int(row.d8),
            phase=int(row.phase),
            decision_ts_ns=int(row.decision_ts_ns),
            frozen_cost_usd=float(row.frozen_cost_usd),
            confirmation_event_ordinal=int(row.confirmation_event_ordinal),
            prefix_last_event_ordinal=int(row.prefix_last_event_ordinal),
            spread_prior_usd=float(row.spread_prior_usd),
            spread_prior_present=int(row.spread_prior_present),
            entry_mid2=float(row.entry_mid2),
            side=int(row.side),
        )
        for row in clear.itertuples(index=False)
    )
    return n_rows, rows, path


def _recency(row: StoredName) -> int:
    return row.prefix_last_event_ordinal - row.confirmation_event_ordinal


def _mark_setters(rows: Sequence[StoredName]) -> tuple[SetterMark, ...]:
    extremes: dict[int, float] = {}
    marked: list[SetterMark] = []
    for row in rows:
        prior = extremes.get(row.side)
        if prior is None:
            marked.append(SetterMark(row, 0.0))
            extremes[row.side] = row.entry_mid2
            continue
        if row.side == 1:
            is_setter = row.entry_mid2 > prior
            excess = row.entry_mid2 - prior
        else:
            is_setter = row.entry_mid2 < prior
            excess = prior - row.entry_mid2
        if is_setter:
            marked.append(SetterMark(row, excess))
            extremes[row.side] = row.entry_mid2
        else:
            marked.append(SetterMark(row, None))
    return tuple(marked)


def _pick_rule_names(rows: Sequence[StoredName]) -> RulePicks:
    by_cell: dict[tuple[str, int, int], list[StoredName]] = {}
    for row in rows:
        if row.phase not in PHASES:
            continue
        by_cell.setdefault((row.asset, row.d8, row.phase), []).append(row)
    picked: dict[str, list[StoredName]] = {name: [] for name in RULE_NAMES}
    all_setters: list[StoredName] = []
    for key in sorted(by_cell):
        ordered = sorted(
            by_cell[key],
            key=lambda row: (row.decision_ts_ns, row.candidate_id),
        )
        earliest = ordered[0]
        marked = _mark_setters(ordered)
        setters = [item for item in marked if item.excess is not None]
        setter_rows = [item.row for item in setters]
        all_setters.extend(setter_rows)
        picked["ordinal_freshest"].append(
            min(
                ordered,
                key=lambda row: (
                    _recency(row),
                    -row.decision_ts_ns,
                    row.candidate_id,
                ),
            )
        )
        picked["ordinal_stalest"].append(
            min(
                ordered,
                key=lambda row: (
                    -_recency(row),
                    -row.decision_ts_ns,
                    row.candidate_id,
                ),
            )
        )
        picked["ordinal_latest_event"].append(
            min(
                ordered,
                key=lambda row: (
                    -row.confirmation_event_ordinal,
                    row.candidate_id,
                ),
            )
        )
        picked["extreme_last_setter"].append(
            max(setters, key=lambda item: item.row.decision_ts_ns).row
        )
        picked["extreme_deepest_setter"].append(
            max(
                setters,
                key=lambda item: (float(item.excess), item.row.decision_ts_ns),
            ).row
        )
        first_nontrivial = next(
            (item.row for item in setters if float(item.excess) > 0.0),
            earliest,
        )
        picked["extreme_first_nontrivial_setter"].append(first_nontrivial)
        spread_rows = [row for row in ordered if row.spread_prior_present == 1]
        picked["spread_prior_max"].append(
            max(spread_rows, key=lambda row: row.spread_prior_usd)
            if spread_rows
            else earliest
        )
        picked["spread_prior_min"].append(
            min(spread_rows, key=lambda row: row.spread_prior_usd)
            if spread_rows
            else earliest
        )
    return RulePicks(
        causal={name: tuple(picked[name]) for name in RULE_NAMES},
        setters=tuple(all_setters),
    )


def _score_asset_day(asset: str, day: object, selected: bool) -> DayBundle:
    n_rows, names, cand_path = _load_stored_names(asset, day.d8)
    if cand_path is None or n_rows == 0:
        return DayBundle(asset, day.d8, False, selected, _empty_picks(), ())
    cand_receipt = RECEIPTS / asset / f"{day.d8}.candidates.json"
    cand_sha = _receipt_output_sha256(cand_receipt)
    if not names:
        return DayBundle(asset, day.d8, True, selected, _empty_picks(), ())
    wanted = [row.candidate_id for row in names]
    teacher, teacher_path = _load_teacher(asset, day.d8, wanted)
    teacher_receipt = RECEIPTS / asset / f"{day.d8}.teacher.json"
    teacher_sha = _receipt_output_sha256(teacher_receipt)
    rel_c = _relative(cand_path)
    rel_t = _relative(teacher_path)
    selected_names = _pick_rule_names(names)
    picks = {
        name: _join_picked(
            selected_names.causal[name],
            teacher,
            rel_c,
            rel_t,
            cand_sha,
            teacher_sha,
        )
        for name in RULE_NAMES
    }
    ready_setters = _ready_rows(selected_names.setters, teacher, rel_t)
    ceiling_setters = _as_selected(
        enter_positive(pick_cell_best_ready(ready_setters)),
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
        picks,
        ceiling_setters,
    )


def _score_job(item: tuple[str, object, bool]) -> DayBundle:
    return _score_asset_day(*item)


def _gated_line(bundles: Sequence[DayBundle], name: str) -> Line:
    days = {asset: 0 for asset in ASSETS}
    entries: list[object] = []
    for bundle in bundles:
        if not bundle.joinable or not bundle.selected:
            continue
        days[bundle.asset] += 1
        if name == "ceiling_setters":
            entries.extend(bundle.ceiling_setters)
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


def dollar_stop(lines: Mapping[str, Line]) -> dict[str, object]:
    hits = [name for name in RULE_NAMES if _line_reaches_stop(lines[name])]
    verdict = "RUNGS" if hits else "KILL"
    return {
        "verdict": verdict,
        "causal_lines_clearing": hits,
        "rungs_usd": dict(RUNGS_USD),
        "drawdown_limit_usd": DRAWDOWN_LIMIT_USD,
        "entry_cap": ENTRY_CAP,
        "required_trades_min": 1,
        "required_overlap_violations": 0,
        "applied": (
            f"RUNGS fired for causal lines {hits}."
            if hits
            else "KILL fired because all eight causal lines miss."
        ),
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


def _cited_full_roster_ceiling() -> dict[str, object]:
    payload = _killed._read_json(FULL_ROSTER_CEILING)
    if payload.get("schema") != "QRE2THRESHOLD20222024CEILING1":
        raise JoinUnavailable(
            "full_roster_ceiling.schema",
            f"{FULL_ROSTER_CEILING} schema {payload.get('schema')!r} "
            "expected QRE2THRESHOLD20222024CEILING1",
        )
    gated = payload.get("gated")
    if not isinstance(gated, dict):
        raise JoinUnavailable(
            "full_roster_ceiling.gated",
            f"{FULL_ROSTER_CEILING} gated {gated!r} expected object",
        )
    return {
        "path": _relative(FULL_ROSTER_CEILING),
        "sha256": _sha256_file(FULL_ROSTER_CEILING),
        "schema": payload.get("schema"),
        "verdict": payload.get("verdict"),
        "usd_per_asset_day": gated.get("usd_per_asset_day"),
        "trades": gated.get("trades"),
        "per_trade_mean_usd": gated.get("per_trade_mean_usd"),
        "max_drawdown_usd": gated.get("max_drawdown_usd"),
        "days": gated.get("days"),
    }


def build_receipt(wall_clock_sec: float) -> dict[str, object]:
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
    if any(name in STORED_COLS for name in PEEK_COLS):
        raise JoinUnavailable(
            "candidates.usecols",
            "stored-name usecols include peek columns",
        )
    if any(name in TEACHER_COLS for name in PEEK_COLS):
        raise JoinUnavailable(
            "teacher.usecols",
            "teacher usecols include peek columns",
        )
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
    lines = {name: _gated_line(bundles, name) for name in RULE_NAMES}
    ceiling_setters = _gated_line(bundles, "ceiling_setters")
    days = lines[RULE_NAMES[0]].days
    if days != EXPECTED_GATED_DAYS:
        raise JoinUnavailable(
            "gated.days",
            f"stored-name days {days} != {EXPECTED_GATED_DAYS}",
        )
    if ceiling_setters.days != EXPECTED_GATED_DAYS:
        raise JoinUnavailable(
            "ceiling_setters.days",
            f"setter-ceiling days {ceiling_setters.days} != {EXPECTED_GATED_DAYS}",
        )
    stop = dollar_stop(lines)
    stop["verbatim"] = _bound_stop_text()
    verdict = str(stop["verdict"])
    return {
        "schema": SCHEMA,
        "status": verdict,
        "verdict": verdict,
        "label": LABEL,
        "window": [WINDOW_START, WINDOW_END],
        "rule": RULE,
        "rules": dict(RULES),
        "causal_lines": list(RULE_NAMES),
        "peek_note": PEEK_NOTE,
        "candidate_columns": list(STORED_COLS),
        "teacher_columns": list(TEACHER_COLS),
        "check_command": CHECK,
        "lines": {name: _line_dict(line) for name, line in lines.items()},
        "ceiling_setters": _line_dict(ceiling_setters),
        "dollar_stop": stop,
        "n_forecast_rows_read": n_read,
        "routed": len(routed),
        "selected": sum(1 for flag in selected_flags if flag),
        "workers": WORKERS,
        "wall_clock_sec": wall_clock_sec,
        "sources": {
            "forecasts": {
                "path": _relative(FORECAST),
                "sha256": _sha256_file(FORECAST),
            },
            "freeze": {
                "path": _relative(FREEZE),
                "sha256": _sha256_file(FREEZE),
            },
            "killed_read": {
                "path": _relative(KILLED_READ),
                "sha256": _sha256_file(KILLED_READ),
            },
            "full_roster_ceiling": _cited_full_roster_ceiling(),
            "covering_brief": {
                "path": _relative(COVERING_BRIEF),
                "sha256": _sha256_file(COVERING_BRIEF),
            },
            "specification_brief": {
                "path": _relative(SPECIFICATION_BRIEF),
                "sha256": _sha256_file(SPECIFICATION_BRIEF),
            },
            "sibling_loaders": {
                "rank_live": {
                    "path": _relative(RANK_LIVE_SCRIPT),
                    "sha256": _sha256_file(RANK_LIVE_SCRIPT),
                },
                "live_scalars": {
                    "path": _relative(LIVE_SCALARS_SCRIPT),
                    "sha256": _sha256_file(LIVE_SCALARS_SCRIPT),
                },
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


def _fixture_name(
    candidate_id: str,
    phase: int,
    decision_ts_ns: int,
    entry_mid2: float,
    side: int,
    confirmation_event_ordinal: int,
    prefix_last_event_ordinal: int,
    spread_prior_usd: float,
    spread_prior_present: int,
) -> StoredName:
    return StoredName(
        candidate_id=candidate_id,
        asset="HG",
        d8=20220314,
        phase=phase,
        decision_ts_ns=decision_ts_ns,
        frozen_cost_usd=5.0,
        confirmation_event_ordinal=confirmation_event_ordinal,
        prefix_last_event_ordinal=prefix_last_event_ordinal,
        spread_prior_usd=spread_prior_usd,
        spread_prior_present=spread_prior_present,
        entry_mid2=entry_mid2,
        side=side,
    )


def _selftest() -> int:
    if len(RULE_NAMES) != 8:
        raise AssertionError(f"selftest causal line count {len(RULE_NAMES)} != 8")
    if tuple(TEACHER_COLS) != (
        "candidate_id",
        "status",
        "cert_close_usd",
        "exit_ts_ns",
    ):
        raise AssertionError(f"selftest teacher columns {TEACHER_COLS!r}")
    if any(name in STORED_COLS for name in PEEK_COLS):
        raise AssertionError("selftest candidate usecols parse peek columns")
    if any(name in TEACHER_COLS for name in PEEK_COLS):
        raise AssertionError("selftest teacher usecols parse peek columns")
    a = _fixture_name("a", 0, 10, 100.0, 1, 10, 15, 8.0, 1)
    b = _fixture_name("b", 0, 20, 100.0, 1, 20, 25, 5.0, 1)
    c = _fixture_name("c", 0, 30, 103.0, 1, 30, 40, np.nan, 0)
    d = _fixture_name("d", 0, 40, 98.0, -1, 40, 90, 2.0, 1)
    e = _fixture_name("e", 0, 50, 99.0, -1, 50, 150, 4.0, 1)
    f = _fixture_name("f", 0, 60, 95.0, -1, 60, 140, 6.0, 1)
    g = _fixture_name("g", 1, 15, 200.0, 1, 5, 8, np.nan, 0)
    h = _fixture_name("h", 1, 25, 199.0, 1, 8, 12, np.nan, 0)
    picks = _pick_rule_names((f, b, h, d, a, g, e, c))
    phase_zero = {
        name: next(row.candidate_id for row in rows if row.phase == 0)
        for name, rows in picks.causal.items()
    }
    expected = {
        "ordinal_freshest": "b",
        "ordinal_stalest": "e",
        "ordinal_latest_event": "f",
        "extreme_last_setter": "f",
        "extreme_deepest_setter": "f",
        "extreme_first_nontrivial_setter": "c",
        "spread_prior_max": "a",
        "spread_prior_min": "d",
    }
    if phase_zero != expected:
        raise AssertionError(f"selftest phase-zero picks {phase_zero} != {expected}")
    setter_ids = [row.candidate_id for row in picks.setters if row.phase == 0]
    if setter_ids != ["a", "c", "d", "f"]:
        raise AssertionError(f"selftest strict setters {setter_ids}")
    for name in (
        "extreme_first_nontrivial_setter",
        "spread_prior_max",
        "spread_prior_min",
    ):
        phase_one = next(row.candidate_id for row in picks.causal[name] if row.phase == 1)
        if phase_one != "g":
            raise AssertionError(f"selftest {name} fallback {phase_one!r} != 'g'")
    empty = summarize_line((), {"HG": 1, "NKD": 1, "SI": 1})
    miss_lines = {name: empty for name in RULE_NAMES}
    killed = dollar_stop(miss_lines)
    if killed["verdict"] != "KILL" or killed["causal_lines_clearing"]:
        raise AssertionError(f"selftest KILL {killed}")
    clear = summarize_line(
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
    hit_lines = {name: empty for name in RULE_NAMES}
    hit_lines["ordinal_freshest"] = clear
    hit = dollar_stop(hit_lines)
    if hit["verdict"] != "RUNGS" or hit["causal_lines_clearing"] != [
        "ordinal_freshest"
    ]:
        raise AssertionError(f"selftest RUNGS {hit}")
    high_drawdown = summarize_line(
        (
            SelectedName(
                "loss", "HG", 20220314, 0, 1, 5.0, -1100.0, None, True, "", None, "", None
            ),
            SelectedName(
                "gain", "HG", 20220314, 1, 2, 5.0, 3100.0, None, True, "", None, "", None
            ),
            SelectedName(
                "n", "NKD", 20220314, 0, 3, 5.0, 1500.0, None, True, "", None, "", None
            ),
            SelectedName(
                "s", "SI", 20220314, 0, 4, 5.0, 1500.0, None, True, "", None, "", None
            ),
        ),
        {"HG": 1, "NKD": 1, "SI": 1},
    )
    if not high_drawdown.clears_rungs or _line_reaches_stop(high_drawdown):
        raise AssertionError(
            f"selftest drawdown gate {high_drawdown.max_drawdown_usd}"
        )
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
