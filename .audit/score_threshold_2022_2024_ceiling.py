#!/usr/bin/env python3
"""Exploratory hindsight cell-best ceiling. Throwaway audit. Cannot promote."""

from __future__ import annotations

import importlib.util
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

REPO = Path(__file__).resolve().parents[1]
RECEIPT = REPO / ".audit/threshold-2022-2024-ceiling.json"
KILLED_READ = REPO / ".audit/threshold-2022-2024-read.json"
CHECK = "python3 .audit/score_threshold_2022_2024_ceiling.py"
SCHEMA = "QRE2THRESHOLD20222024CEILING1"
LABEL = (
    "exploratory hindsight teacher-cash. It can kill and cannot promote."
)
RULE = (
    "For each era asset-day in 2022-03-09 through 2024-12-31 that is joinable "
    "(nonzero candidates file plus a routed forecast day, the killed read's "
    "definition), in each cell (asset, d8, phase) take the READY teacher name "
    "with maximum `cert_close_usd`, tie-break lexicographically smallest "
    "`candidate_id`. Enter it only when that maximum is positive. One contract, "
    "at most 12 entries per portfolio day (9 natural). A joinable day whose "
    "cells all sit at or below zero stays in the denominator at zero cash."
)
KILL_VERBATIM = (
    "Both lines miss any rung (HG under 2000, or NKD under 1500, or SI under "
    "1500 `usd_per_asset_day`). Then no within-cell instrument, however good, "
    "reaches the rungs on this era under the caps. Ticket 47 as motivated is "
    "dead spend, and the covering answer is one line: nothing remaining covers "
    "the rungs."
)
PROCEED_VERBATIM = (
    "Either line clears all three rungs. Ticket 47 (shard build) becomes the "
    "next unit. Its downstream stop, written now. The fitted instrument gets "
    "one frozen-rule teacher-cash read on the era. It must post HG at or above "
    "2000, NKD at or above 1500, SI at or above 1500 per asset-day with "
    "`max_drawdown_usd` under 1000 and at most 12 entries, or the instrument "
    "family dies. A pass there still cannot promote. Promotion needs the one "
    "`QRE2TABPOLICYBLOCK2` block that exits "
    "`assert_threshold_replay_receipt.py` at 0. 2025H1 stays unread until that "
    "walk exists. 2025H2 stays sealed."
)
EXPECTED_GATED_DAYS = {"HG": 197, "NKD": 194, "SI": 191}
WORKERS = 14


def _load_killed_module():
    path = Path(__file__).with_name("score_threshold_2022_2024_read.py")
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import killed-read module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module


_killed = _load_killed_module()
ASSETS = _killed.ASSETS
PHASES = _killed.PHASES
WINDOW_START = _killed.WINDOW_START
WINDOW_END = _killed.WINDOW_END
RUNGS_USD = _killed.RUNGS_USD
ENTRY_CAP = _killed.ENTRY_CAP
CANDIDATE_COLS = _killed.CANDIDATE_COLS
TEACHER_COLS = _killed.TEACHER_COLS
PEEK_COLS = _killed.PEEK_COLS
FORECAST = _killed.FORECAST
FREEZE = _killed.FREEZE
CANDIDATES = _killed.CANDIDATES
TEACHERS = _killed.TEACHERS
RECEIPTS = _killed.RECEIPTS
JoinUnavailable = _killed.JoinUnavailable
Candidate = _killed.Candidate
RoutedDay = _killed.RoutedDay
SelectedName = _killed.SelectedName
route_catboost_daily = _killed.route_catboost_daily
refused_days_without_daily = _killed.refused_days_without_daily
select_expanding_median = _killed.select_expanding_median
load_window_forecast_rows = _killed.load_window_forecast_rows
_load_candidates = _killed._load_candidates
_load_teacher = _killed._load_teacher
_sha256_file = _killed._sha256_file
_relative = _killed._relative
_receipt_output_sha256 = _killed._receipt_output_sha256
max_drawdown_usd = _killed.max_drawdown_usd
max_entries_portfolio_day = _killed.max_entries_portfolio_day
overlap_violations = _killed.overlap_violations


@dataclass(frozen=True, slots=True)
class ReadyPick:
    candidate_id: str
    asset: str
    d8: int
    phase: int
    decision_ts_ns: int
    frozen_cost_usd: float
    cert_close_usd: float
    exit_ts_ns: int


@dataclass(frozen=True, slots=True)
class AssetDayScore:
    asset: str
    d8: int
    joinable: bool
    selected: bool
    entries: tuple[object, ...]


@dataclass(frozen=True, slots=True)
class Line:
    days: dict[str, int]
    cash_total_usd: dict[str, float]
    usd_per_asset_day: dict[str, float]
    trades: int
    per_trade_mean_usd: float
    max_drawdown_usd: float
    max_entries_portfolio_day: int
    overlap_violations: int
    entry_cap_ok: bool
    clears_rungs: bool
    shortfall_usd: dict[str, float]

    def as_dict(self) -> dict[str, object]:
        return {
            "days": dict(self.days),
            "cash_total_usd": dict(self.cash_total_usd),
            "usd_per_asset_day": dict(self.usd_per_asset_day),
            "trades": self.trades,
            "per_trade_mean_usd": self.per_trade_mean_usd,
            "max_drawdown_usd": self.max_drawdown_usd,
            "max_entries_portfolio_day": self.max_entries_portfolio_day,
            "overlap_violations": self.overlap_violations,
            "entry_cap": ENTRY_CAP,
            "entry_cap_ok": self.entry_cap_ok,
            "clears_rungs": self.clears_rungs,
            "shortfall_usd": dict(self.shortfall_usd),
            "rungs_usd": dict(RUNGS_USD),
        }


def _better_ready(prior: ReadyPick | None, nxt: ReadyPick) -> bool:
    if prior is None:
        return True
    if nxt.cert_close_usd > prior.cert_close_usd:
        return True
    if nxt.cert_close_usd < prior.cert_close_usd:
        return False
    return nxt.candidate_id < prior.candidate_id


def pick_cell_best_ready(rows: Sequence[ReadyPick]) -> tuple[ReadyPick, ...]:
    best: dict[tuple[str, int, int], ReadyPick] = {}
    for row in rows:
        if row.phase not in PHASES:
            continue
        key = (row.asset, row.d8, row.phase)
        prior = best.get(key)
        if _better_ready(prior, row):
            best[key] = row
    return tuple(best[key] for key in sorted(best))


def enter_positive(picked: Sequence[ReadyPick]) -> tuple[ReadyPick, ...]:
    return tuple(row for row in picked if row.cert_close_usd > 0.0)


def line_clears(usd_per_asset_day: Mapping[str, float]) -> bool:
    return all(usd_per_asset_day[asset] >= floor for asset, floor in RUNGS_USD.items())


def shortfall_usd(usd_per_asset_day: Mapping[str, float]) -> dict[str, float]:
    return {
        asset: float(floor - usd_per_asset_day[asset])
        for asset, floor in RUNGS_USD.items()
        if usd_per_asset_day[asset] < floor
    }


def summarize_line(
    entries: Sequence[object],
    days: Mapping[str, int],
) -> Line:
    cash = {asset: 0.0 for asset in ASSETS}
    named = tuple(entries)
    for row in named:
        cash[row.asset] += float(row.cash_usd)
    usd = {
        asset: (cash[asset] / days[asset] if days[asset] else 0.0)
        for asset in ASSETS
    }
    trades = len(named)
    mean = (sum(cash.values()) / trades) if trades else 0.0
    drawdown = max_drawdown_usd(named)
    max_entries = max_entries_portfolio_day(named)
    overlaps = overlap_violations(named)
    return Line(
        days=dict(days),
        cash_total_usd=cash,
        usd_per_asset_day=usd,
        trades=trades,
        per_trade_mean_usd=mean,
        max_drawdown_usd=drawdown,
        max_entries_portfolio_day=max_entries,
        overlap_violations=overlaps,
        entry_cap_ok=max_entries <= ENTRY_CAP,
        clears_rungs=line_clears(usd),
        shortfall_usd=shortfall_usd(usd),
    )


def split_lines(scores: Sequence[AssetDayScore]) -> tuple[Line, Line]:
    gated_days = {asset: 0 for asset in ASSETS}
    ungated_days = {asset: 0 for asset in ASSETS}
    gated_entries: list[object] = []
    ungated_entries: list[object] = []
    for score in scores:
        if not score.joinable:
            continue
        ungated_days[score.asset] += 1
        ungated_entries.extend(score.entries)
        if score.selected:
            gated_days[score.asset] += 1
            gated_entries.extend(score.entries)
    return summarize_line(gated_entries, gated_days), summarize_line(
        ungated_entries, ungated_days
    )


def dollar_stop(gated: Line, ungated: Line) -> dict[str, object]:
    proceed = gated.clears_rungs or ungated.clears_rungs
    verdict = "PROCEED" if proceed else "KILL"
    return {
        "verdict": verdict,
        "rungs_usd": dict(RUNGS_USD),
        "gated_clears_rungs": gated.clears_rungs,
        "ungated_clears_rungs": ungated.clears_rungs,
        "gated_shortfall_usd": dict(gated.shortfall_usd),
        "ungated_shortfall_usd": dict(ungated.shortfall_usd),
        "verbatim": {
            "KILL": KILL_VERBATIM,
            "PROCEED": PROCEED_VERBATIM,
        },
        "applied": PROCEED_VERBATIM if proceed else KILL_VERBATIM,
    }


def _ready_rows(
    candidates: Sequence[object],
    teacher: Mapping[str, tuple[str, float, int]],
    source: str,
) -> tuple[ReadyPick, ...]:
    rows: list[ReadyPick] = []
    for row in candidates:
        hit = teacher.get(row.candidate_id)
        if hit is None:
            continue
        status, cert, exit_ts = hit
        if status != "READY":
            continue
        if not np.isfinite(cert):
            raise JoinUnavailable(
                "teacher.cert_close_usd",
                f"{source} READY {row.candidate_id} has non-finite cert {cert!r}",
            )
        rows.append(
            ReadyPick(
                candidate_id=row.candidate_id,
                asset=row.asset,
                d8=row.d8,
                phase=row.phase,
                decision_ts_ns=row.decision_ts_ns,
                frozen_cost_usd=row.frozen_cost_usd,
                cert_close_usd=float(cert),
                exit_ts_ns=int(exit_ts),
            )
        )
    return tuple(rows)


def _as_selected(
    picks: Sequence[ReadyPick],
    cand_path: str,
    teacher_path: str,
    cand_sha: str,
    teacher_sha: str,
) -> tuple[object, ...]:
    return tuple(
        SelectedName(
            candidate_id=row.candidate_id,
            asset=row.asset,
            d8=row.d8,
            phase=row.phase,
            decision_ts_ns=row.decision_ts_ns,
            frozen_cost_usd=row.frozen_cost_usd,
            cash_usd=float(row.cert_close_usd),
            exit_ts_ns=row.exit_ts_ns,
            ready=True,
            source_candidates=cand_path,
            source_teacher=teacher_path,
            candidates_output_sha256=cand_sha,
            teacher_output_sha256=teacher_sha,
        )
        for row in picks
    )


def _score_asset_day(
    asset: str,
    day: object,
    selected: bool,
) -> AssetDayScore:
    n_rows, candidates, cand_path = _load_candidates(asset, day.d8)
    if cand_path is None or n_rows == 0:
        return AssetDayScore(asset, day.d8, False, selected, ())
    cand_receipt = RECEIPTS / asset / f"{day.d8}.candidates.json"
    cand_sha = _receipt_output_sha256(cand_receipt)
    if not candidates:
        return AssetDayScore(asset, day.d8, True, selected, ())
    wanted = [row.candidate_id for row in candidates]
    teacher, teacher_path = _load_teacher(asset, day.d8, wanted)
    teacher_receipt = RECEIPTS / asset / f"{day.d8}.teacher.json"
    teacher_sha = _receipt_output_sha256(teacher_receipt)
    ready = _ready_rows(candidates, teacher, _relative(teacher_path))
    entered = enter_positive(pick_cell_best_ready(ready))
    names = _as_selected(
        entered,
        _relative(cand_path),
        _relative(teacher_path),
        cand_sha,
        teacher_sha,
    )
    return AssetDayScore(asset, day.d8, True, selected, names)


def _score_job(
    item: tuple[str, object, bool],
) -> AssetDayScore:
    asset, day, selected = item
    return _score_asset_day(asset, day, selected)


def _cited_killed_read() -> dict[str, object]:
    if not KILLED_READ.is_file():
        raise JoinUnavailable("killed_read", f"missing cited receipt {KILLED_READ}")
    payload = _killed._read_json(KILLED_READ)
    usd = payload.get("usd_per_asset_day")
    if not isinstance(usd, dict):
        raise JoinUnavailable(
            "killed_read.usd_per_asset_day",
            f"{KILLED_READ} usd_per_asset_day {usd!r}",
        )
    return {
        "path": _relative(KILLED_READ),
        "sha256": _sha256_file(KILLED_READ),
        "verdict": payload.get("verdict"),
        "usd_per_asset_day": {
            asset: float(usd[asset]) for asset in ASSETS if asset in usd
        },
        "max_drawdown_usd": payload.get("max_drawdown_usd"),
        "trades": payload.get("trades"),
        "per_trade_mean_usd": payload.get("per_trade_mean_usd"),
        "days": payload.get("days"),
    }


def build_receipt(wall_clock_sec: float) -> dict[str, object]:
    if any(name in TEACHER_COLS for name in PEEK_COLS):
        raise JoinUnavailable("teacher.usecols", "teacher usecols include peek columns")
    if any(name in CANDIDATE_COLS for name in PEEK_COLS):
        raise JoinUnavailable(
            "candidates.usecols",
            "candidate usecols include peek columns",
        )
    forecast_rows, window_days, n_read = load_window_forecast_rows(FORECAST)
    routed, _empty = route_catboost_daily(forecast_rows)
    refused = refused_days_without_daily(window_days, [row.day for row in routed])
    selected_flags = select_expanding_median(routed)
    jobs = [
        (asset, day, bool(flag))
        for day, flag in zip(routed, selected_flags)
        for asset in ASSETS
    ]
    scores: list[AssetDayScore] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for score in pool.map(_score_job, jobs):
            scores.append(score)
    gated, ungated = split_lines(scores)
    if gated.days != EXPECTED_GATED_DAYS:
        raise JoinUnavailable(
            "gated.days",
            f"gated days {gated.days} != killed-read {EXPECTED_GATED_DAYS}",
        )
    stop = dollar_stop(gated, ungated)
    verdict = str(stop["verdict"])
    return {
        "schema": SCHEMA,
        "status": verdict,
        "verdict": verdict,
        "label": LABEL,
        "window": [WINDOW_START, WINDOW_END],
        "rule": RULE,
        "check_command": CHECK,
        "routed": len(routed),
        "selected": sum(1 for flag in selected_flags if flag),
        "refused_no_forecast": len(refused),
        "refused_no_forecast_days": list(refused),
        "gated": gated.as_dict(),
        "ungated": ungated.as_dict(),
        "dollar_stop": stop,
        "n_forecast_rows_read": n_read,
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
            "killed_read": _cited_killed_read(),
            "candidates_root": _relative(CANDIDATES),
            "teacher_root": _relative(TEACHERS),
            "receipts_root": _relative(RECEIPTS),
        },
    }


def _write_receipt(value: Mapping[str, object]) -> None:
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    temporary = RECEIPT.with_name(f"{RECEIPT.name}.tmp.{os.getpid()}")
    temporary.write_text(
        __import__("json").dumps(value, indent=2, sort_keys=True) + "\n"
    )
    os.replace(temporary, RECEIPT)


def _selftest() -> int:
    if any(name in TEACHER_COLS for name in PEEK_COLS):
        raise AssertionError("selftest teacher usecols parse peek columns")
    if any(name in CANDIDATE_COLS for name in PEEK_COLS):
        raise AssertionError("selftest candidate usecols parse peek columns")
    rows = (
        _killed.ForecastRow("2022-03-10", 5, 10, 0.10),
        _killed.ForecastRow("2022-03-10", 2, 10, 0.20),
        _killed.ForecastRow("2022-03-11", 1, 12, 0.05),
        _killed.ForecastRow("2022-03-14", 7, 4, 0.40),
        _killed.ForecastRow("2022-03-15", 3, 6, 0.15),
    )
    routed, _ = route_catboost_daily(rows)
    selected = select_expanding_median(routed)
    if selected[0]:
        raise AssertionError("selftest first routed day must stay unselected")
    if selected != (False, False, True, False):
        raise AssertionError(f"selftest expanding median {selected}")
    picked = pick_cell_best_ready(
        (
            ReadyPick("late", "HG", 20220314, 0, 40, 5.0, 100.0, 50),
            ReadyPick("early", "HG", 20220314, 0, 10, 5.0, 10.0, 20),
            ReadyPick("b", "HG", 20220314, 1, 20, 5.0, 50.0, 30),
            ReadyPick("a", "HG", 20220314, 1, 21, 5.0, 50.0, 31),
            ReadyPick("neg", "HG", 20220314, 2, 15, 5.0, -5.0, 25),
        )
    )
    ids = [row.candidate_id for row in picked]
    if ids != ["late", "a", "neg"]:
        raise AssertionError(f"selftest cell-best pick {ids}")
    entered = enter_positive(picked)
    entered_ids = [row.candidate_id for row in entered]
    if entered_ids != ["late", "a"]:
        raise AssertionError(f"selftest negative cell entered {entered_ids}")
    zero_cell = enter_positive(
        pick_cell_best_ready(
            (ReadyPick("z", "SI", 20220314, 0, 10, 5.0, 0.0, 20),)
        )
    )
    if zero_cell:
        raise AssertionError(f"selftest zero cell entered {zero_cell}")
    if _killed.pick_cell_names is pick_cell_best_ready:
        raise AssertionError("selftest reused killed earliest-CLEAR pick")
    earliest = _killed.pick_cell_names(
        (
            Candidate("early", "HG", 20220314, 0, 10, 5.0),
            Candidate("late", "HG", 20220314, 0, 40, 5.0),
        )
    )
    if [row.candidate_id for row in earliest] != ["early"]:
        raise AssertionError("selftest killed earliest-CLEAR fixture drifted")
    if pick_cell_best_ready(
        (
            ReadyPick("early", "HG", 20220314, 0, 10, 5.0, 10.0, 20),
            ReadyPick("late", "HG", 20220314, 0, 40, 5.0, 100.0, 50),
        )
    )[0].candidate_id != "late":
        raise AssertionError("selftest cell-best collapsed onto earliest CLEAR")
    unselected = SelectedName(
        "u1", "HG", 20220311, 0, 10, 5.0, 4000.0, 20, True, "", None, "", None
    )
    selected_pos = SelectedName(
        "s1", "HG", 20220314, 0, 11, 5.0, 500.0, 21, True, "", None, "", None
    )
    selected_zero_day = AssetDayScore("NKD", 20220314, True, True, ())
    scores = (
        AssetDayScore("HG", 20220311, True, False, (unselected,)),
        AssetDayScore("HG", 20220314, True, True, (selected_pos,)),
        selected_zero_day,
        AssetDayScore("SI", 20220314, True, True, ()),
        AssetDayScore("HG", 20220315, False, True, ()),
    )
    gated, ungated = split_lines(scores)
    if gated.days != {"HG": 1, "NKD": 1, "SI": 1}:
        raise AssertionError(f"selftest gated days {gated.days}")
    if ungated.days != {"HG": 2, "NKD": 1, "SI": 1}:
        raise AssertionError(f"selftest ungated days {ungated.days}")
    if gated.cash_total_usd["HG"] != 500.0:
        raise AssertionError(
            f"selftest unselected cash leaked into gated {gated.cash_total_usd}"
        )
    if ungated.cash_total_usd["HG"] != 4500.0:
        raise AssertionError(f"selftest ungated cash {ungated.cash_total_usd}")
    if gated.trades != 1 or ungated.trades != 2:
        raise AssertionError(
            f"selftest trades gated={gated.trades} ungated={ungated.trades}"
        )
    if not gated.entry_cap_ok or gated.max_entries_portfolio_day > ENTRY_CAP:
        raise AssertionError(f"selftest entry cap {gated.max_entries_portfolio_day}")
    miss = summarize_line((), {"HG": 1, "NKD": 1, "SI": 1})
    if miss.clears_rungs:
        raise AssertionError("selftest empty line cleared rungs")
    kill = dollar_stop(miss, miss)
    if kill["verdict"] != "KILL" or kill["applied"] != KILL_VERBATIM:
        raise AssertionError(f"selftest KILL stop {kill}")
    clear_entries = (
        SelectedName(
            "h", "HG", 20220314, 0, 10, 5.0, 2000.0, 20, True, "", None, "", None
        ),
        SelectedName(
            "n", "NKD", 20220314, 0, 11, 5.0, 1500.0, 21, True, "", None, "", None
        ),
        SelectedName(
            "s", "SI", 20220314, 0, 12, 5.0, 1500.0, 22, True, "", None, "", None
        ),
    )
    clear = summarize_line(clear_entries, {"HG": 1, "NKD": 1, "SI": 1})
    if not clear.clears_rungs:
        raise AssertionError(f"selftest exact rungs failed {clear.usd_per_asset_day}")
    proceed = dollar_stop(miss, clear)
    if proceed["verdict"] != "PROCEED" or proceed["applied"] != PROCEED_VERBATIM:
        raise AssertionError(f"selftest PROCEED stop {proceed}")
    if LABEL != (
        "exploratory hindsight teacher-cash. It can kill and cannot promote."
    ):
        raise AssertionError(f"selftest label {LABEL!r}")
    print("selftest_ok")
    return 0


def _summarize(receipt: Mapping[str, object]) -> str:
    gated = receipt.get("gated", {})
    ungated = receipt.get("ungated", {})
    return (
        f"receipt={_relative(RECEIPT)} verdict={receipt.get('verdict')} "
        f"gated_usd={gated.get('usd_per_asset_day')} "
        f"ungated_usd={ungated.get('usd_per_asset_day')} "
        f"gated_trades={gated.get('trades')} "
        f"ungated_trades={ungated.get('trades')} "
        f"wall_clock_sec={receipt.get('wall_clock_sec')}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv if argv is not None else __import__("sys").argv[1:])
    if "--selftest" in args:
        if args != ["--selftest"]:
            raise ValueError(f"--selftest must be the only argument, got {args}")
        return _selftest()
    if args:
        raise ValueError(f"unsupported arguments {args}")
    started = time.perf_counter()
    try:
        receipt = build_receipt(0.0)
    except JoinUnavailable as exc:
        receipt = {
            "schema": SCHEMA,
            "status": "JOIN_UNAVAILABLE",
            "verdict": "JOIN_UNAVAILABLE",
            "label": LABEL,
            "missing_key": exc.missing_key,
            "detail": exc.detail,
            "window": [WINDOW_START, WINDOW_END],
            "rule": RULE,
            "check_command": CHECK,
            "dollar_stop": {
                "verdict": "KILL",
                "verbatim": {
                    "KILL": KILL_VERBATIM,
                    "PROCEED": PROCEED_VERBATIM,
                },
                "applied": KILL_VERBATIM,
                "blockers": [f"join_unavailable {exc.missing_key}: {exc.detail}"],
            },
            "wall_clock_sec": round(time.perf_counter() - started, 3),
        }
        _write_receipt(receipt)
        print(_summarize(receipt))
        return 2
    receipt["wall_clock_sec"] = round(time.perf_counter() - started, 3)
    _write_receipt(receipt)
    print(_summarize(receipt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
