#!/usr/bin/env python3
"""One authorized 2022-2024 teacher-cash read. Throwaway audit."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
FORECAST = REPO / "artifacts/runs/e6_vol_forecasts_v2/vol_service_forecasts.tsv"
CANDIDATES = REPO / "artifacts/cache/port/entry_v2/g1/candidates"
TEACHERS = REPO / "artifacts/cache/port/entry_v2/g1/teacher"
RECEIPTS = REPO / "artifacts/cache/port/entry_v2/g1/receipts"
FREEZE = REPO / ".audit/threshold-2022-2024-freeze.md"
RECEIPT = REPO / ".audit/threshold-2022-2024-read.json"
CHECK = "python3 .audit/score_threshold_2022_2024_read.py"
SCHEMA = "QRE2THRESHOLD20222024READ1"
WINDOW_START = "2022-03-09"
WINDOW_END = "2024-12-31"
ASSETS = ("HG", "NKD", "SI")
PHASES = (0, 1, 2)
WORKERS = 14
RUNGS_USD = {"HG": 2000.0, "NKD": 1500.0, "SI": 1500.0}
DRAWDOWN_LIMIT_USD = 1000.0
ENTRY_CAP = 12
CANDIDATE_COLS = (
    "candidate_id",
    "asset",
    "d8",
    "phase",
    "decision_ts_ns",
    "compliance_status",
    "frozen_cost_usd",
)
TEACHER_COLS = ("candidate_id", "status", "cert_close_usd", "exit_ts_ns")
PEEK_COLS = ("mfe_usd", "mae_usd", "payer", "take_target")
FROZEN_RULE = (
    "Enter one contract in every joinable cell (asset, d8, phase) on every "
    "selected day, taking each cell's earliest CLEAR candidate; a day is "
    "selected when its routed catboost `daily` `forecast_variance` is at or "
    "above the expanding median of all strictly prior routed days in the "
    "window; cash is `cert_close_usd` on `status == READY`. The forecast "
    "decides only this day-level cell set. It is day-level and assetless, so "
    "it cannot pick the name and cannot rank assets or phases."
)
ONE_SENTENCE_RULE = (
    "Enter one contract in every joinable cell (asset, d8, phase) on every "
    "selected day, taking each cell's earliest CLEAR candidate; a day is "
    "selected when its routed catboost `daily` `forecast_variance` is at or "
    "above the expanding median of all strictly prior routed days in the "
    "window; cash is `cert_close_usd` on `status == READY`."
)
PASS_MEANS = (
    "Teacher-cash can kill the forecast plane. Teacher-cash cannot promote. "
    "A RUNGS verdict here is not THRESHOLD. Promotion still needs one "
    "`QRE2TABPOLICYBLOCK2` that clears "
    "`python3 .audit/assert_threshold_replay_receipt.py`."
)
KILL_SENTENCE = (
    "forecast day-gate plus a skill-free name pick did not clear the rungs; "
    "the unmeasured lever is within-cell name selection, which has no "
    "instrument (T53/T54)"
)


class JoinUnavailable(RuntimeError):
    def __init__(self, missing_key: str, detail: str) -> None:
        super().__init__(detail)
        self.missing_key = missing_key
        self.detail = detail


@dataclass(frozen=True, slots=True)
class ForecastRow:
    day: str
    outer_fold: int
    train_sessions_n: int
    forecast_variance: float


@dataclass(frozen=True, slots=True)
class RoutedDay:
    day: str
    d8: int
    outer_fold: int
    train_sessions_n: int
    forecast_variance: float


@dataclass(frozen=True, slots=True)
class Candidate:
    candidate_id: str
    asset: str
    d8: int
    phase: int
    decision_ts_ns: int
    frozen_cost_usd: float


@dataclass(frozen=True, slots=True)
class SelectedName:
    candidate_id: str
    asset: str
    d8: int
    phase: int
    decision_ts_ns: int
    frozen_cost_usd: float
    cash_usd: float
    exit_ts_ns: int | None
    ready: bool
    source_candidates: str
    source_teacher: str | None
    candidates_output_sha256: str
    teacher_output_sha256: str | None


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iso_to_d8(day: str) -> int:
    if len(day) != 10 or day[4] != "-" or day[7] != "-":
        raise JoinUnavailable("forecast.day", f"expected ISO day YYYY-MM-DD, got {day!r}")
    return int(day[0:4] + day[5:7] + day[8:10])


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise JoinUnavailable("artifact_path", f"missing JSON artifact {path}")
    try:
        value = json.loads(path.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise JoinUnavailable("json_payload", f"cannot read JSON artifact {path}") from exc
    if not isinstance(value, dict):
        raise JoinUnavailable("json_object", f"{path} must contain a JSON object")
    return value


def _receipt_output_sha256(path: Path) -> str:
    payload = _read_json(path)
    value = payload.get("output_sha256")
    if not isinstance(value, str) or not value:
        raise JoinUnavailable(
            "output_sha256",
            f"{path} lacks output_sha256, got {value!r}",
        )
    return value


def _assert_no_peek(columns: Sequence[str], label: str) -> None:
    leaked = [name for name in columns if name in PEEK_COLS]
    if leaked:
        raise JoinUnavailable(
            f"{label}.usecols",
            f"{label} usecols parsed peek columns {leaked}",
        )


def route_catboost_daily(
    rows: Sequence[ForecastRow],
) -> tuple[tuple[RoutedDay, ...], tuple[str, ...]]:
    by_day: dict[str, list[ForecastRow]] = {}
    for row in rows:
        by_day.setdefault(row.day, []).append(row)
    routed: list[RoutedDay] = []
    refused: list[str] = []
    for day in sorted(by_day):
        group = by_day[day]
        best = max(group, key=lambda row: (row.train_sessions_n, -row.outer_fold))
        routed.append(
            RoutedDay(
                day=day,
                d8=_iso_to_d8(day),
                outer_fold=best.outer_fold,
                train_sessions_n=best.train_sessions_n,
                forecast_variance=best.forecast_variance,
            )
        )
    return tuple(routed), tuple(refused)


def refused_days_without_daily(
    window_days: Sequence[str],
    routed_days: Sequence[str],
) -> tuple[str, ...]:
    routed = set(routed_days)
    return tuple(day for day in window_days if day not in routed)


def select_expanding_median(routed: Sequence[RoutedDay]) -> tuple[bool, ...]:
    if not routed:
        return ()
    variances = np.asarray([row.forecast_variance for row in routed], np.float64)
    selected = np.zeros(len(routed), bool)
    for index in range(1, len(routed)):
        prior = variances[:index]
        selected[index] = bool(variances[index] >= float(np.median(prior)))
    return tuple(bool(flag) for flag in selected)


def pick_cell_names(rows: Sequence[Candidate]) -> tuple[Candidate, ...]:
    best: dict[tuple[str, int, int], Candidate] = {}
    for row in rows:
        if row.phase not in PHASES:
            continue
        key = (row.asset, row.d8, row.phase)
        prior = best.get(key)
        if prior is None or (row.decision_ts_ns, row.candidate_id) < (
            prior.decision_ts_ns,
            prior.candidate_id,
        ):
            best[key] = row
    return tuple(
        best[key]
        for key in sorted(best, key=lambda item: (item[0], item[1], item[2]))
    )


def cash_usd(status: str, cert_close_usd: float) -> float:
    if status == "READY":
        return float(cert_close_usd)
    return 0.0


def max_drawdown_usd(entries: Sequence[SelectedName]) -> float:
    ordered = sorted(
        entries,
        key=lambda row: (row.d8, row.decision_ts_ns, row.candidate_id),
    )
    running = 0.0
    peak = 0.0
    worst = 0.0
    for row in ordered:
        running += row.cash_usd
        if running > peak:
            peak = running
        drawdown = peak - running
        if drawdown > worst:
            worst = drawdown
    return float(worst)


def overlap_violations(entries: Sequence[SelectedName]) -> int:
    by_asset: dict[str, list[SelectedName]] = {asset: [] for asset in ASSETS}
    for row in entries:
        by_asset.setdefault(row.asset, []).append(row)
    violations = 0
    for rows in by_asset.values():
        ordered = sorted(rows, key=lambda row: (row.decision_ts_ns, row.candidate_id))
        for prior, nxt in zip(ordered, ordered[1:]):
            if prior.exit_ts_ns is None:
                continue
            if nxt.decision_ts_ns < prior.exit_ts_ns:
                violations += 1
    return violations


def max_entries_portfolio_day(entries: Sequence[SelectedName]) -> int:
    if not entries:
        return 0
    counts: dict[int, int] = {}
    for row in entries:
        counts[row.d8] = counts.get(row.d8, 0) + 1
    return max(counts.values())


def dollar_stop(
    usd_per_asset_day: Mapping[str, float],
    trades: int,
    drawdown: float,
    max_entries: int,
    overlaps: int,
) -> dict[str, object]:
    shortfall = {
        asset: float(floor - usd_per_asset_day[asset])
        for asset, floor in RUNGS_USD.items()
        if usd_per_asset_day[asset] < floor
    }
    blockers: list[str] = []
    if trades <= 0:
        blockers.append("trades == 0")
    for asset, gap in shortfall.items():
        blockers.append(
            f"{asset} usd_per_asset_day {usd_per_asset_day[asset]} short of "
            f"{RUNGS_USD[asset]} by {gap}"
        )
    if not (drawdown < DRAWDOWN_LIMIT_USD):
        blockers.append(
            f"max_drawdown_usd {drawdown} is not < {DRAWDOWN_LIMIT_USD}"
        )
    if max_entries > ENTRY_CAP:
        blockers.append(
            f"max_entries_portfolio_day {max_entries} exceeds {ENTRY_CAP}"
        )
    if overlaps != 0:
        blockers.append(f"overlap_violations {overlaps} != 0")
    killed = bool(blockers)
    return {
        "verdict": "KILL" if killed else "RUNGS",
        "rungs_usd": dict(RUNGS_USD),
        "drawdown_limit_usd": DRAWDOWN_LIMIT_USD,
        "entry_cap": ENTRY_CAP,
        "shortfall_usd": shortfall,
        "blockers": blockers,
        "kill_sentence": KILL_SENTENCE if killed else None,
        "trades": trades,
        "usd_per_asset_day": dict(usd_per_asset_day),
        "max_drawdown_usd": drawdown,
        "max_entries_portfolio_day": max_entries,
        "overlap_violations": overlaps,
    }


def load_window_forecast_rows(
    path: Path,
) -> tuple[tuple[ForecastRow, ...], tuple[str, ...], int]:
    if not path.is_file():
        raise JoinUnavailable("forecasts", f"missing forecast TSV {path}")
    kept: list[ForecastRow] = []
    window_days: set[str] = set()
    n_read = 0
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        required = {
            "head",
            "arm",
            "outer_fold",
            "day",
            "forecast_variance",
            "train_sessions_n",
        }
        missing = required.difference(reader.fieldnames or ())
        if missing:
            raise JoinUnavailable(
                "forecast.columns",
                f"{path} missing columns {sorted(missing)}, got {reader.fieldnames!r}",
            )
        for raw in reader:
            n_read += 1
            day = str(raw["day"])
            if day < WINDOW_START or day > WINDOW_END:
                continue
            window_days.add(day)
            if str(raw["arm"]) != "catboost" or str(raw["head"]) != "daily":
                continue
            variance = float(raw["forecast_variance"])
            if not np.isfinite(variance):
                raise JoinUnavailable(
                    "forecast.forecast_variance",
                    f"non-finite forecast_variance {raw['forecast_variance']!r} "
                    f"on {day}",
                )
            kept.append(
                ForecastRow(
                    day=day,
                    outer_fold=int(raw["outer_fold"]),
                    train_sessions_n=int(raw["train_sessions_n"]),
                    forecast_variance=variance,
                )
            )
    return tuple(kept), tuple(sorted(window_days)), n_read


def _load_candidates(
    asset: str, d8: int
) -> tuple[int, tuple[Candidate, ...], Path | None]:
    path = CANDIDATES / asset / f"{d8}.tsv"
    if not path.is_file():
        return 0, (), None
    _assert_no_peek(CANDIDATE_COLS, "candidates")
    frame = pd.read_csv(
        path,
        sep="\t",
        skiprows=1,
        usecols=list(CANDIDATE_COLS),
        dtype={
            "candidate_id": str,
            "asset": str,
            "d8": np.int64,
            "phase": np.int64,
            "decision_ts_ns": np.int64,
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
    rows = tuple(
        Candidate(
            candidate_id=str(row.candidate_id),
            asset=str(row.asset),
            d8=int(row.d8),
            phase=int(row.phase),
            decision_ts_ns=int(row.decision_ts_ns),
            frozen_cost_usd=float(row.frozen_cost_usd),
        )
        for row in clear.itertuples(index=False)
    )
    return n_rows, rows, path


def _load_teacher(
    asset: str,
    d8: int,
    wanted: Sequence[str],
) -> tuple[dict[str, tuple[str, float, int]], Path]:
    path = TEACHERS / asset / f"{d8}.tsv"
    if not path.is_file():
        raise JoinUnavailable(
            "teacher.path",
            f"selected {asset}/{d8} teacher missing {path}",
        )
    _assert_no_peek(TEACHER_COLS, "teacher")
    if any(name in TEACHER_COLS for name in PEEK_COLS):
        raise JoinUnavailable("teacher.usecols", "teacher usecols include peek columns")
    frame = pd.read_csv(
        path,
        sep="\t",
        skiprows=1,
        usecols=list(TEACHER_COLS),
        dtype={
            "candidate_id": str,
            "status": str,
            "cert_close_usd": np.float64,
            "exit_ts_ns": np.int64,
        },
    )
    if frame.columns.tolist() != list(TEACHER_COLS) and set(frame.columns) != set(
        TEACHER_COLS
    ):
        raise JoinUnavailable(
            "teacher.columns",
            f"{path} parsed columns {frame.columns.tolist()} != {list(TEACHER_COLS)}",
        )
    found: dict[str, tuple[str, float, int]] = {}
    if frame.empty:
        return found, path
    selected = frame[frame["candidate_id"].isin(list(wanted))]
    for row in selected.itertuples(index=False):
        cid = str(row.candidate_id)
        if cid in found:
            raise JoinUnavailable(
                "teacher.candidate_id",
                f"{path} repeats selected candidate_id {cid}",
            )
        found[cid] = (str(row.status), float(row.cert_close_usd), int(row.exit_ts_ns))
    return found, path


def _score_selected_asset_day(
    asset: str,
    day: RoutedDay,
) -> tuple[bool, tuple[SelectedName, ...], dict[str, object]]:
    n_rows, candidates, cand_path = _load_candidates(asset, day.d8)
    sources: dict[str, object] = {}
    if cand_path is None or n_rows == 0:
        return False, (), sources
    cand_receipt = RECEIPTS / asset / f"{day.d8}.candidates.json"
    cand_sha = _receipt_output_sha256(cand_receipt)
    sources["candidates"] = {
        "path": _relative(cand_path),
        "receipt": _relative(cand_receipt),
        "output_sha256": cand_sha,
    }
    picked = pick_cell_names(candidates)
    if not picked:
        return True, (), sources
    wanted = [row.candidate_id for row in picked]
    teacher, teacher_path = _load_teacher(asset, day.d8, wanted)
    teacher_receipt = RECEIPTS / asset / f"{day.d8}.teacher.json"
    teacher_sha = _receipt_output_sha256(teacher_receipt)
    sources["teacher"] = {
        "path": _relative(teacher_path),
        "receipt": _relative(teacher_receipt),
        "output_sha256": teacher_sha,
    }
    names: list[SelectedName] = []
    for row in picked:
        hit = teacher.get(row.candidate_id)
        if hit is None:
            names.append(
                SelectedName(
                    candidate_id=row.candidate_id,
                    asset=row.asset,
                    d8=row.d8,
                    phase=row.phase,
                    decision_ts_ns=row.decision_ts_ns,
                    frozen_cost_usd=row.frozen_cost_usd,
                    cash_usd=0.0,
                    exit_ts_ns=None,
                    ready=False,
                    source_candidates=_relative(cand_path),
                    source_teacher=_relative(teacher_path),
                    candidates_output_sha256=cand_sha,
                    teacher_output_sha256=teacher_sha,
                )
            )
            continue
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
                source_candidates=_relative(cand_path),
                source_teacher=_relative(teacher_path),
                candidates_output_sha256=cand_sha,
                teacher_output_sha256=teacher_sha,
            )
        )
    return True, tuple(names), sources


def _score_job(
    item: tuple[str, RoutedDay],
) -> tuple[str, int, bool, tuple[SelectedName, ...], dict[str, object]]:
    asset, day = item
    joinable, names, sources = _score_selected_asset_day(asset, day)
    return asset, day.d8, joinable, names, sources


def build_receipt(wall_clock_sec: float) -> dict[str, object]:
    if any(name in TEACHER_COLS for name in PEEK_COLS):
        raise JoinUnavailable("teacher.usecols", "teacher usecols include peek columns")
    forecast_rows, window_days, n_read = load_window_forecast_rows(FORECAST)
    routed, _empty = route_catboost_daily(forecast_rows)
    refused = refused_days_without_daily(window_days, [row.day for row in routed])
    selected_flags = select_expanding_median(routed)
    selected_days = tuple(
        day for day, flag in zip(routed, selected_flags) if flag
    )
    jobs = [(asset, day) for day in selected_days for asset in ASSETS]
    joinable_days = {asset: 0 for asset in ASSETS}
    entries: list[SelectedName] = []
    opened: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for asset, d8, joinable, names, sources in pool.map(_score_job, jobs):
            if joinable:
                joinable_days[asset] += 1
            entries.extend(names)
            if sources:
                opened.append({"asset": asset, "d8": d8, **sources})
    cash_total = {asset: 0.0 for asset in ASSETS}
    not_ready = 0
    cost_total = 0.0
    for row in entries:
        cash_total[row.asset] += row.cash_usd
        cost_total += row.frozen_cost_usd
        if not row.ready:
            not_ready += 1
    days = dict(joinable_days)
    usd = {
        asset: (cash_total[asset] / days[asset] if days[asset] else 0.0)
        for asset in ASSETS
    }
    trades = len(entries)
    drawdown = max_drawdown_usd(entries)
    max_entries = max_entries_portfolio_day(entries)
    overlaps = overlap_violations(entries)
    stop = dollar_stop(usd, trades, drawdown, max_entries, overlaps)
    verdict = str(stop["verdict"])
    return {
        "schema": SCHEMA,
        "status": verdict,
        "verdict": verdict,
        "window": [WINDOW_START, WINDOW_END],
        "frozen_rule": FROZEN_RULE,
        "one_sentence_rule": ONE_SENTENCE_RULE,
        "what_a_pass_means": PASS_MEANS,
        "check_command": CHECK,
        "routed": len(routed),
        "selected": len(selected_days),
        "refused_no_forecast": len(refused),
        "refused_no_forecast_days": list(refused),
        "cash_total_usd": cash_total,
        "days": days,
        "usd_per_asset_day": usd,
        "trades": trades,
        "per_trade_mean_usd": (sum(cash_total.values()) / trades) if trades else 0.0,
        "selected_not_ready": not_ready,
        "max_drawdown_usd": drawdown,
        "max_entries_portfolio_day": max_entries,
        "overlap_violations": overlaps,
        "selected_frozen_cost_usd_total": cost_total,
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
            "candidates_root": _relative(CANDIDATES),
            "teacher_root": _relative(TEACHERS),
            "receipts_root": _relative(RECEIPTS),
            "g1_opened": opened,
        },
    }


def _write_receipt(value: Mapping[str, object]) -> None:
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    temporary = RECEIPT.with_name(f"{RECEIPT.name}.tmp.{os.getpid()}")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, RECEIPT)


def _selftest() -> int:
    if any(name in TEACHER_COLS for name in PEEK_COLS):
        raise AssertionError("selftest teacher usecols parse peek columns")
    if any(name in CANDIDATE_COLS for name in PEEK_COLS):
        raise AssertionError("selftest candidate usecols parse peek columns")
    rows = (
        ForecastRow("2022-03-10", 5, 10, 0.10),
        ForecastRow("2022-03-10", 2, 10, 0.20),
        ForecastRow("2022-03-10", 1, 8, 0.90),
        ForecastRow("2022-03-11", 1, 12, 0.05),
        ForecastRow("2022-03-14", 7, 4, 0.40),
        ForecastRow("2022-03-15", 3, 6, 0.15),
    )
    routed, _ = route_catboost_daily(rows)
    if [row.day for row in routed] != [
        "2022-03-10",
        "2022-03-11",
        "2022-03-14",
        "2022-03-15",
    ]:
        raise AssertionError(f"selftest routed days { [row.day for row in routed] }")
    if routed[0].outer_fold != 2 or routed[0].forecast_variance != 0.20:
        raise AssertionError(f"selftest fold tie lost freshness {routed[0]!r}")
    window_days = (
        "2022-03-09",
        "2022-03-10",
        "2022-03-11",
        "2022-03-14",
        "2022-03-15",
    )
    refused = refused_days_without_daily(window_days, [row.day for row in routed])
    if refused != ("2022-03-09",):
        raise AssertionError(f"selftest refused_no_forecast {refused}")
    selected = select_expanding_median(routed)
    if selected[0]:
        raise AssertionError("selftest first routed day must stay unselected")
    if selected != (False, False, True, False):
        raise AssertionError(f"selftest expanding median {selected}")
    even = (
        RoutedDay("2022-03-10", 20220310, 1, 1, 1.0),
        RoutedDay("2022-03-11", 20220311, 1, 1, 3.0),
        RoutedDay("2022-03-14", 20220314, 1, 1, 2.0),
    )
    even_selected = select_expanding_median(even)
    if even_selected != (False, True, True):
        raise AssertionError(f"selftest even-count midpoint median {even_selected}")
    picked = pick_cell_names(
        (
            Candidate("b", "HG", 20220314, 0, 20, 5.0),
            Candidate("a", "HG", 20220314, 0, 20, 5.0),
            Candidate("late", "HG", 20220314, 1, 40, 5.0),
            Candidate("early", "HG", 20220314, 1, 10, 5.0),
            Candidate("p2", "HG", 20220314, 2, 15, 5.0),
        )
    )
    ids = [row.candidate_id for row in picked]
    if ids != ["a", "early", "p2"]:
        raise AssertionError(f"selftest name pick {ids}")
    if cash_usd("READY", 125.0) != 125.0:
        raise AssertionError("selftest subtracted frozen_cost_usd a second time")
    if cash_usd("NO_SANE_SUFFIX", 80.0) != 0.0:
        raise AssertionError("selftest non-READY scored cash")
    zero_day_entries: tuple[SelectedName, ...] = ()
    if max_drawdown_usd(zero_day_entries) != 0.0:
        raise AssertionError("selftest empty drawdown")
    named = (
        SelectedName(
            "e1", "HG", 20220314, 0, 10, 5.0, 10.0, 30, True, "", None, "", None
        ),
        SelectedName(
            "e2", "HG", 20220314, 1, 11, 5.0, -5.0, 40, True, "", None, "", None
        ),
        SelectedName(
            "e3", "NKD", 20220314, 0, 12, 5.0, -20.0, 50, True, "", None, "", None
        ),
        SelectedName(
            "e4", "SI", 20220315, 0, 13, 5.0, 3.0, 60, True, "", None, "", None
        ),
    )
    if max_drawdown_usd(named) != 25.0:
        raise AssertionError(f"selftest drawdown {max_drawdown_usd(named)}")
    overlap_rows = (
        SelectedName(
            "a1", "HG", 20220314, 0, 10, 5.0, 1.0, 30, True, "", None, "", None
        ),
        SelectedName(
            "a2", "HG", 20220314, 1, 20, 5.0, 1.0, 40, True, "", None, "", None
        ),
    )
    if overlap_violations(overlap_rows) != 1:
        raise AssertionError("selftest overlap miss")
    clear_overlap = (
        overlap_rows[0],
        SelectedName(
            "a3", "HG", 20220314, 1, 30, 5.0, 1.0, 50, True, "", None, "", None
        ),
    )
    if overlap_violations(clear_overlap) != 0:
        raise AssertionError("selftest overlap false positive")
    if max_entries_portfolio_day(named) != 3:
        raise AssertionError("selftest max entries")
    rungs = dollar_stop(
        {"HG": 2100.0, "NKD": 1600.0, "SI": 1600.0},
        3,
        100.0,
        3,
        0,
    )
    if rungs["verdict"] != "RUNGS" or rungs["kill_sentence"] is not None:
        raise AssertionError(f"selftest RUNGS {rungs}")
    killed = dollar_stop(
        {"HG": 500.0, "NKD": 1600.0, "SI": 100.0},
        3,
        100.0,
        3,
        0,
    )
    if killed["verdict"] != "KILL" or killed["kill_sentence"] != KILL_SENTENCE:
        raise AssertionError(f"selftest KILL sentence {killed}")
    if "HG" not in killed["shortfall_usd"] or "SI" not in killed["shortfall_usd"]:
        raise AssertionError(f"selftest shortfall {killed['shortfall_usd']}")
    if FROZEN_RULE[: len(ONE_SENTENCE_RULE)] != ONE_SENTENCE_RULE:
        raise AssertionError("selftest frozen_rule lost the one-sentence rule")
    if "day-level and assetless" not in FROZEN_RULE:
        raise AssertionError("selftest frozen_rule dropped the allocation sentence")
    print("selftest_ok")
    return 0


def _summarize(receipt: Mapping[str, object]) -> str:
    usd = receipt.get("usd_per_asset_day", {})
    return (
        f"receipt={_relative(RECEIPT)} verdict={receipt.get('verdict')} "
        f"usd_per_asset_day={usd} "
        f"max_drawdown_usd={receipt.get('max_drawdown_usd')} "
        f"trades={receipt.get('trades')} "
        f"max_entries_portfolio_day={receipt.get('max_entries_portfolio_day')} "
        f"overlap_violations={receipt.get('overlap_violations')} "
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
            "missing_key": exc.missing_key,
            "detail": exc.detail,
            "window": [WINDOW_START, WINDOW_END],
            "frozen_rule": FROZEN_RULE,
            "check_command": CHECK,
            "dollar_stop": {
                "verdict": "KILL",
                "blockers": [f"join_unavailable {exc.missing_key}: {exc.detail}"],
                "kill_sentence": KILL_SENTENCE,
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
