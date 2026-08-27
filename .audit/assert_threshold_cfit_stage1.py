#!/usr/bin/env python3
"""Read-only byte sweep for the C Stage 1 fitted-read receipt.

Authored by the Fable Stage 1 judge after the receipt existed. Verifies the
published receipt against disk, the covering map, the stage-0 receipt, and the
frozen scorer constants. Never re-runs the fit (that would be a second era
teacher read); the scorer's own selftest and mutants are rerun separately.
Crashes loud on the first broken check.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parents[1]
RECEIPT_PATH = REPO / ".audit/threshold-cfit-stage1.json"
COVERING_PATH = REPO / ".audit/briefs/threshold-covering-after-pivot-kill-out.md"
STAGE0_PATH = REPO / ".audit/threshold-cfit-stage0.json"
SCORER_PATH = REPO / ".audit/score_threshold_cfit_stage1.py"
RULER_MODULES = (
    ".audit/score_threshold_2022_2024_ceiling.py",
    ".audit/score_threshold_2022_2024_read.py",
)
HASH_WORKERS = 13
ASSETS = ("HG", "NKD", "SI")
LOCKED_DAYS = {"HG": 197, "NKD": 194, "SI": 191}
RUNGS = {"HG": 2000.0, "NKD": 1500.0, "SI": 1500.0}


class SweepFailure(AssertionError):
    pass


def _fail(label: str, message: str) -> None:
    raise SweepFailure(f"{label}: {message}")


def _check(condition: bool, label: str, message: str) -> None:
    if not condition:
        _fail(label, message)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict:
    value = json.loads(path.read_text())
    _check(isinstance(value, dict), "json", f"{path} is not an object")
    return value


def _import_scorer() -> ModuleType:
    spec = importlib.util.spec_from_file_location("cfit_stage1_scorer", SCORER_PATH)
    _check(spec is not None and spec.loader is not None, "scorer.import", str(SCORER_PATH))
    module = importlib.util.module_from_spec(spec)
    sys.modules["cfit_stage1_scorer"] = module
    spec.loader.exec_module(module)
    return module


def _covering_bullet(text: str, marker: str) -> str:
    lines = [line for line in text.splitlines() if line.startswith(marker)]
    _check(len(lines) == 1, "covering.bullet", f"{marker!r} found {len(lines)} times")
    return lines[0]


def check_schema_and_constants(receipt: dict, scorer: ModuleType) -> None:
    _check(receipt["schema"] == "QRE2THRESHOLDCFITSTAGE11", "schema", repr(receipt["schema"]))
    _check(receipt["status"] == "KILL" and receipt["verdict"] == "KILL", "verdict",
           f"status {receipt['status']!r} verdict {receipt['verdict']!r}")
    _check(receipt["window"] == ["2022-03-09", "2024-12-31"], "window", repr(receipt["window"]))
    _check(receipt["workers"] == 13, "workers", repr(receipt["workers"]))
    _check(receipt["training_gate_states"] == "both", "gate_states",
           repr(receipt["training_gate_states"]))
    _check(receipt["rule"] == scorer.RULE, "rule", "receipt rule differs from scorer RULE")
    _check(receipt["peek_note"] == scorer.PEEK_NOTE, "peek_note", "differs from scorer")
    _check(receipt["check_command"] == scorer.CHECK, "check_command", repr(receipt["check_command"]))
    _check(receipt["one_read"] is True, "one_read", repr(receipt["one_read"]))
    _check(receipt["tag_can_promote"] is False and receipt["teacher_cash_can_promote"] is False,
           "cannot_promote", "a promote flag is not False")
    _check(receipt["tickets_started"] == [] and receipt["units_started"] == ["C_STAGE1"],
           "units", f"{receipt['tickets_started']!r} {receipt['units_started']!r}")
    _check(receipt["candidate_columns"] == list(scorer.CANDIDATE_COLUMNS), "candidate_columns",
           "differ from scorer")
    _check(receipt["pivot_columns"] == list(scorer.PIVOT_COLUMNS), "pivot_columns",
           "differ from scorer")
    _check(receipt["teacher_columns"] == ["candidate_id", "status", "cert_close_usd", "exit_ts_ns"],
           "teacher_columns", repr(receipt["teacher_columns"]))
    features = receipt["features"]
    _check(features["numeric"] == list(scorer.NUMERIC_FEATURES), "features.numeric",
           "differ from scorer frozen list")
    _check(features["categorical_native"] == ["rung_mask", "delay"], "features.categorical",
           repr(features["categorical_native"]))
    _check(len(scorer.NUMERIC_FEATURES) == 22, "features.count", str(len(scorer.NUMERIC_FEATURES)))
    banned = set(scorer.BANNED_FEATURES).intersection(scorer.FEATURES)
    _check(not banned, "features.banned", f"outcome columns in features {sorted(banned)}")
    expected_learner = {
        "name": "CatBoostClassifier", "version": "1.2.10", "loss_function": "Logloss",
        "depth": 6, "iterations": 500, "learning_rate": 0.05, "random_seed": 20260826,
        "early_stopping": False, "class_weights": None, "tuning": False,
        "cross_validation": False, "per_asset_models": True, "thread_count_per_model": 1,
    }
    _check(receipt["learner"] == expected_learner, "learner",
           f"{receipt['learner']!r} != frozen config")


def check_dollar_block(receipt: dict) -> None:
    line = receipt["lines"]["fitted"]
    stop = receipt["dollar_stop"]
    _check(line["days"] == LOCKED_DAYS, "days", repr(line["days"]))
    _check(line["rungs_usd"] == RUNGS and stop["rungs_usd"] == RUNGS, "rungs",
           f"{line['rungs_usd']!r} {stop['rungs_usd']!r}")
    cash = line["cash_total_usd"]
    usd = line["usd_per_asset_day"]
    shortfall = line["shortfall_usd"]
    for asset in ASSETS:
        recomputed = cash[asset] / LOCKED_DAYS[asset]
        _check(usd[asset] == recomputed, f"usd.{asset}",
               f"{usd[asset]!r} != {cash[asset]!r}/{LOCKED_DAYS[asset]}")
        _check(shortfall[asset] == RUNGS[asset] - usd[asset], f"shortfall.{asset}",
               f"{shortfall[asset]!r} != {RUNGS[asset]} - {usd[asset]!r}")
        _check(stop["shortfall_usd"][asset] == shortfall[asset], f"stop.shortfall.{asset}",
               repr(stop["shortfall_usd"][asset]))
        _check(usd[asset] < RUNGS[asset], f"miss.{asset}", f"{usd[asset]!r} clears {RUNGS[asset]}")
    trades = line["trades"]
    _check(trades == 1734 and trades > 0, "trades", repr(trades))
    total_cash = sum(cash.values())
    _check(line["per_trade_mean_usd"] == total_cash / trades, "per_trade_mean",
           f"{line['per_trade_mean_usd']!r} != {total_cash!r}/{trades}")
    _check(line["max_drawdown_usd"] == 75608.75, "max_drawdown", repr(line["max_drawdown_usd"]))
    _check(not (line["max_drawdown_usd"] < stop["drawdown_limit_usd"]), "drawdown_breach",
           "drawdown under the limit would contradict the blocker")
    _check(line["max_entries_portfolio_day"] == 9 and line["entry_cap"] == 12
           and line["entry_cap_ok"] is True, "entry_cap",
           f"{line['max_entries_portfolio_day']!r} of {line['entry_cap']!r}")
    _check(line["overlap_violations"] == 0, "overlap", repr(line["overlap_violations"]))
    _check(line["one_contract"] is True and line["dollars_per_trade"] is True, "contract_flags",
           "one_contract or dollars_per_trade is not True")
    _check(line["clears_rungs"] is False, "clears_rungs", repr(line["clears_rungs"]))
    _check(int(line["selected_not_ready"]) >= 0, "selected_not_ready",
           repr(line["selected_not_ready"]))
    expected_blockers = []
    if trades <= 0:
        expected_blockers.append("trades == 0")
    for asset in ASSETS:
        if usd[asset] < RUNGS[asset]:
            expected_blockers.append(
                f"{asset} usd_per_asset_day {usd[asset]} short of {RUNGS[asset]} "
                f"by {RUNGS[asset] - usd[asset]}"
            )
    if not (line["max_drawdown_usd"] < stop["drawdown_limit_usd"]):
        expected_blockers.append(
            f"max_drawdown_usd {line['max_drawdown_usd']} is not < {stop['drawdown_limit_usd']}"
        )
    if line["max_entries_portfolio_day"] > line["entry_cap"]:
        expected_blockers.append("entry cap breach missing from expectation")
    if line["overlap_violations"] != 0:
        expected_blockers.append("overlap breach missing from expectation")
    _check(stop["blockers"] == expected_blockers, "blockers",
           f"{stop['blockers']!r} != re-derived {expected_blockers!r}")
    _check(stop["verdict"] == ("KILL" if expected_blockers else "RUNGS"), "stop.verdict",
           repr(stop["verdict"]))
    _check(stop["drawdown_limit_usd"] == 1000.0 and stop["entry_cap"] == 12
           and stop["required_overlap_violations"] == 0 and stop["required_trades_min"] == 1,
           "stop.constants", repr({k: stop[k] for k in ("drawdown_limit_usd", "entry_cap")}))


def check_verbatim_stop(receipt: dict, scorer: ModuleType) -> None:
    stop = receipt["dollar_stop"]
    covering = COVERING_PATH.read_text()
    kill_bullet = _covering_bullet(covering, "- **KILL at stage 1.**")
    rungs_bullet = _covering_bullet(covering, "- **RUNGS at stage 1.**")
    for label, receipt_text, covering_text, scorer_text in (
        ("KILL", stop["verbatim"]["KILL"], kill_bullet, scorer.KILL_VERBATIM),
        ("RUNGS", stop["verbatim"]["RUNGS"], rungs_bullet, scorer.RUNGS_VERBATIM),
    ):
        _check(receipt_text == covering_text, f"verbatim.{label}.covering",
               "receipt text is not byte-equal to the covering map bullet")
        _check(receipt_text == scorer_text, f"verbatim.{label}.scorer",
               "receipt text is not byte-equal to the scorer constant")
    _check(stop["applied"] == stop["verbatim"]["KILL"], "applied",
           "applied stop is not the KILL bullet")


def check_fit_block(receipt: dict) -> None:
    fit = receipt["fit"]
    _check(fit["models"] == sum(LOCKED_DAYS.values()) == 582, "models", repr(fit["models"]))
    _check(fit["fallback_no_train"]["total"] == 0
           and fit["fallback_no_train"]["per_asset"] == {asset: 0 for asset in ASSETS},
           "fallback", repr(fit["fallback_no_train"]))
    twin = fit["entry_price_twin_control"]
    _check(twin["gates_verdict"] is False, "twin.gates_verdict", repr(twin["gates_verdict"]))
    total_cells = 0
    total_matches = 0
    first_day_rows = {}
    for asset in ASSETS:
        days = fit["training_rows_per_day"][asset]
        _check(len(days) == LOCKED_DAYS[asset], f"fit.days.{asset}",
               f"{len(days)} != {LOCKED_DAYS[asset]}")
        previous_d8 = 0
        previous_rows = -1
        asset_cells = 0
        for row in days:
            _check(row["d8"] > previous_d8, f"fit.d8_order.{asset}",
                   f"{row['d8']} after {previous_d8}")
            _check(row["training_rows"] >= previous_rows, f"fit.rows_monotone.{asset}",
                   f"{row['training_rows']} after {previous_rows} at {row['d8']}")
            _check(row["training_positive_rows"] == row["training_cells"],
                   f"fit.one_winner_per_cell.{asset}",
                   f"d8 {row['d8']} positives {row['training_positive_rows']} "
                   f"cells {row['training_cells']}")
            _check(row["fallback_no_train"] is False, f"fit.fallback.{asset}",
                   f"fallback fired at {row['d8']}")
            _check(row["evaluation_cells"] >= 1, f"fit.eval_cells.{asset}",
                   f"{row['evaluation_cells']} at {row['d8']}")
            previous_d8 = row["d8"]
            previous_rows = row["training_rows"]
            asset_cells += row["evaluation_cells"]
        first_day_rows[asset] = days[0]["training_rows"]
        asset_twin = twin["per_asset"][asset]
        _check(asset_twin["cells"] == asset_cells, f"twin.cells.{asset}",
               f"{asset_twin['cells']} != summed {asset_cells}")
        _check(asset_twin["match_rate"] == asset_twin["matches"] / asset_twin["cells"],
               f"twin.rate.{asset}", repr(asset_twin))
        total_cells += asset_cells
        total_matches += asset_twin["matches"]
    _check(total_cells == receipt["lines"]["fitted"]["trades"], "cells_vs_trades",
           f"{total_cells} != {receipt['lines']['fitted']['trades']}")
    _check(twin["cells"] == total_cells and twin["matches"] == total_matches,
           "twin.totals", repr({"cells": twin["cells"], "matches": twin["matches"]}))
    _check(twin["match_rate"] == total_matches / total_cells, "twin.total_rate",
           repr(twin["match_rate"]))
    _check(receipt["lines"]["fitted"]["entry_price_twin_match_rate"] == twin["match_rate"],
           "twin.line_rate", "line rate differs from control rate")
    for asset in ASSETS:
        _check(first_day_rows[asset] > 0, f"fit.both_gate_states.{asset}",
               "first evaluated day has zero training rows, so unselected routed days "
               "cannot have trained and the both-gate-states clause is unproven")
    fit_cpu_seconds = sum(
        row["fit_seconds"] for asset in ASSETS for row in fit["training_rows_per_day"][asset]
    )
    _check(fit_cpu_seconds >= receipt["timing_seconds"]["fit"], "fit.cpu_seconds",
           f"summed {fit_cpu_seconds} under wall {receipt['timing_seconds']['fit']}")
    projection = receipt["projection"]
    _check(projection["models"] == 582 and projection["workers"] == 13, "projection",
           repr({k: projection[k] for k in ("models", "workers")}))
    _check(projection["projected_seconds"] < projection["tripwire_seconds"] == 7200.0,
           "projection.tripwire", repr(projection["projected_seconds"]))
    _check(receipt["timing_seconds"]["wall"] < 7200.0, "wall", repr(receipt["timing_seconds"]))


def check_day_counts_and_verification(receipt: dict) -> None:
    counts = receipt["day_counts"]
    _check(counts["locked_gated_denominators"] == LOCKED_DAYS, "locked_days",
           repr(counts["locked_gated_denominators"]))
    _check(counts["routed"] == 708 and counts["refused_no_forecast"] == 0, "routed",
           repr(counts))
    _check(counts["selected_gate_days"] == 198 >= max(LOCKED_DAYS.values()), "selected_days",
           repr(counts["selected_gate_days"]))
    verification = receipt["verification"]
    _check(verification["red_first_before_era_read"] is True, "red_first",
           repr(verification["red_first_before_era_read"]))
    checks = verification["checks"]
    expected = {
        "selftest": (0, "PASS", "python3 .audit/score_threshold_cfit_stage1.py --selftest"),
        "future_train_leak": (1, "KILLED",
            "QRE2_CFIT_MUTANT=future_train_leak python3 .audit/score_threshold_cfit_stage1.py --selftest"),
        "day_outcome_as_feature": (1, "KILLED",
            "QRE2_CFIT_MUTANT=day_outcome_as_feature python3 .audit/score_threshold_cfit_stage1.py --selftest"),
        "missing_tag_accepted": (1, "KILLED",
            "QRE2_CFIT_MUTANT=missing_tag_accepted python3 .audit/score_threshold_cfit_stage1.py --selftest"),
        "guard_mutant": (1, "KILLED",
            "QRE2_CFIT_MUTANT=corrupt_candidate_id_accepted python3 .audit/score_threshold_cfit_stage1.py --selftest"),
    }
    _check(set(checks) == set(expected), "verification.names", repr(sorted(checks)))
    for name, (exit_code, status, command) in expected.items():
        entry = checks[name]
        _check(entry["exit_code"] == exit_code and entry["status"] == status
               and entry["command"] == command, f"verification.{name}", repr(entry))


def check_forbidden_reads(receipt: dict, opened: list[dict]) -> None:
    forbidden = receipt["forbidden_reads"]
    _check(forbidden["teacher_fields_unparsed"] == ["mfe_usd", "mae_usd", "payer", "take_target"],
           "peek_fields", repr(forbidden["teacher_fields_unparsed"]))
    _check(forbidden["opened_2025_candidate_teacher_or_pivot_files"] == 0
           and forbidden["pivot_lines_scored"] is False, "forbidden_flags", repr(forbidden))
    max_d8 = max(int(row["d8"]) for row in opened)
    min_d8 = min(int(row["d8"]) for row in opened)
    _check(20220309 <= min_d8 and max_d8 <= 20241231, "opened.window",
           f"opened days span {min_d8}..{max_d8}")
    _check(forbidden["max_candidate_d8_opened"] == max_d8 == 20241231, "opened.max",
           repr(forbidden["max_candidate_d8_opened"]))
    _check(forbidden["max_pivot_d8_opened"] == 20241231
           and forbidden["max_teacher_d8_opened"] == 20241231, "opened.max_kinds",
           repr(forbidden))


def check_opened_structure(receipt: dict, opened: list[dict], stage0: dict) -> None:
    _check(len(opened) == 3 * receipt["day_counts"]["routed"] == 2124, "opened.count",
           str(len(opened)))
    tag_manifest = stage0["tag_sha256_manifest"]
    per_asset = {asset: 0 for asset in ASSETS}
    joinable_days = {asset: set() for asset in ASSETS}
    for row in opened:
        asset = row["asset"]
        d8 = int(row["d8"])
        per_asset[asset] += 1
        candidates = row["candidates"]
        _check(candidates["sha256"] == candidates["output_sha256"], "opened.candidates.sha",
               f"{asset}/{d8} disk sha differs from generation output_sha256")
        if row["joinable"]:
            joinable_days[asset].add(d8)
            pivot = row["pivot"]
            expected_tag = tag_manifest[asset].get(str(d8), tag_manifest[asset].get(d8))
            _check(expected_tag == pivot["sha256"], "opened.pivot.stage0",
                   f"{asset}/{d8} pivot sha {pivot['sha256']!r} not the stage-0 tag "
                   f"manifest entry {expected_tag!r}")
        teacher = row.get("teacher")
        if isinstance(teacher, dict):
            _check(teacher["sha256"] == teacher["output_sha256"], "opened.teacher.sha",
                   f"{asset}/{d8} disk sha differs from generation output_sha256")
    _check(per_asset == {asset: 708 for asset in ASSETS}, "opened.per_asset", repr(per_asset))
    for asset in ASSETS:
        evaluated = {row["d8"] for row in receipt["fit"]["training_rows_per_day"][asset]}
        stray = evaluated - joinable_days[asset]
        _check(not stray, f"opened.evaluated_subset.{asset}",
               f"evaluated days missing from joinable opened set: {sorted(stray)[:3]}")


def check_top_level_sources(receipt: dict, stage0: dict) -> None:
    sources = receipt["sources"]
    flat = [sources["script"], sources["covering_brief"], sources["stage0_judge"],
            sources["freeze"], sources["forecast"],
            sources["templates"]["pivot_join_and_dollar_block"],
            sources["templates"]["loaders_gate_denominators"],
            sources["templates"]["selftest_receipt"]]
    for entry in flat:
        path = REPO / entry["path"]
        actual = _sha256(path)
        _check(actual == entry["sha256"], "sources.sha",
               f"{entry['path']} rehashes to {actual!r} recorded {entry['sha256']!r}")
    stage0_entry = sources["stage0_receipt"]
    actual = _sha256(REPO / stage0_entry["path"])
    _check(actual == stage0_entry["sha256"], "sources.stage0",
           f"stage-0 receipt rehashes to {actual!r} recorded {stage0_entry['sha256']!r}")
    _check(stage0_entry["schema"] == "QRE2THRESHOLDCFITSTAGE01"
           and stage0_entry["status"] == "PASS", "stage0.header", repr(stage0_entry["schema"]))
    _check(stage0["schema"] == "QRE2THRESHOLDCFITSTAGE01" and stage0["status"] == "PASS",
           "stage0.disk", f"{stage0['schema']!r} {stage0['status']!r}")
    covering_sha = sources["covering_brief"]["sha256"]
    anchored = stage0_entry["verified_source_sha256s"][
        ".audit/briefs/threshold-covering-after-pivot-kill-out.md"]
    _check(covering_sha == anchored, "covering.anchor",
           f"stage-1 covering sha {covering_sha!r} differs from stage-0 anchor {anchored!r}")
    for asset in ASSETS:
        manifest = stage0_entry["pivot_manifests"][asset]
        disk = _sha256(REPO / manifest["path"])
        _check(disk == manifest["sha256"], f"pivot_manifest.{asset}",
               f"disk {disk!r} recorded {manifest['sha256']!r}")
        stage0_manifest_sha = stage0["manifest_sha256s"][asset]
        _check(disk == stage0_manifest_sha, f"pivot_manifest.stage0.{asset}",
               f"disk {disk!r} stage-0 recorded {stage0_manifest_sha!r}")
    scorer_disk = _sha256(SCORER_PATH)
    _check(scorer_disk == sources["script"]["sha256"], "scorer.pinned",
           f"scorer on disk {scorer_disk!r} receipt pinned {sources['script']['sha256']!r}")


def check_ruler_chain_pinned() -> dict[str, str]:
    tracked = subprocess.run(
        ["git", "ls-files", "--", *RULER_MODULES],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout.split()
    _check(sorted(tracked) == sorted(RULER_MODULES), "ruler.tracked", repr(tracked))
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", *RULER_MODULES],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout.strip()
    _check(dirty == "", "ruler.unmodified", f"working tree changes: {dirty!r}")
    return {module: _sha256(REPO / module) for module in RULER_MODULES}


def _hash_job(item: tuple[str, str, str]) -> tuple[str, str, str, str]:
    label, path, expected = item
    return label, path, expected, _sha256(REPO / path)


def check_opened_bytes(opened: list[dict]) -> int:
    jobs: list[tuple[str, str, str]] = []
    for row in opened:
        key = f"{row['asset']}/{row['d8']}"
        candidates = row["candidates"]
        jobs.append((f"candidates.{key}", candidates["path"], candidates["sha256"]))
        jobs.append((f"candidates_receipt.{key}", candidates["receipt"],
                     candidates["receipt_sha256"]))
        if row["joinable"]:
            pivot = row["pivot"]
            jobs.append((f"pivot.{key}", pivot["path"], pivot["sha256"]))
        teacher = row.get("teacher")
        if isinstance(teacher, dict):
            jobs.append((f"teacher.{key}", teacher["path"], teacher["sha256"]))
            jobs.append((f"teacher_receipt.{key}", teacher["receipt"],
                         teacher["receipt_sha256"]))
    sample = jobs[:50]
    started = time.perf_counter()
    for item in sample:
        label, path, expected, actual = _hash_job(item)
        _check(actual == expected, label, f"{path} rehashes to {actual!r}")
    per_file = (time.perf_counter() - started) / len(sample)
    projected = per_file * (len(jobs) - len(sample)) / HASH_WORKERS
    print(f"rehashing {len(jobs)} opened files, projected {projected:.0f}s "
          f"at {HASH_WORKERS} workers", flush=True)
    completed = len(sample)
    with ThreadPoolExecutor(max_workers=HASH_WORKERS) as pool:
        for label, path, expected, actual in pool.map(_hash_job, jobs[len(sample):]):
            _check(actual == expected, label, f"{path} rehashes to {actual!r}")
            completed += 1
            if completed % 2000 == 0:
                print(f"rehashed {completed}/{len(jobs)}", flush=True)
    return len(jobs)


def check_generation_receipts(opened: list[dict]) -> int:
    def _payload_job(item: tuple[str, str, str]) -> tuple[str, str, str, str]:
        label, receipt_path, expected_output = item
        payload = _load_json(REPO / receipt_path)
        return label, receipt_path, expected_output, str(payload.get("output_sha256"))

    jobs = []
    for row in opened:
        key = f"{row['asset']}/{row['d8']}"
        candidates = row["candidates"]
        jobs.append((f"candidates_output.{key}", candidates["receipt"],
                     candidates["output_sha256"]))
        teacher = row.get("teacher")
        if isinstance(teacher, dict):
            jobs.append((f"teacher_output.{key}", teacher["receipt"],
                         teacher["output_sha256"]))
    with ThreadPoolExecutor(max_workers=HASH_WORKERS) as pool:
        for label, path, expected, actual in pool.map(_payload_job, jobs):
            _check(actual == expected, label,
                   f"{path} output_sha256 {actual!r} receipt recorded {expected!r}")
    return len(jobs)


def main() -> int:
    started = time.perf_counter()
    receipt = _load_json(RECEIPT_PATH)
    stage0 = _load_json(STAGE0_PATH)
    scorer = _import_scorer()
    opened = receipt["sources"]["opened_artifacts"]
    check_schema_and_constants(receipt, scorer)
    check_dollar_block(receipt)
    check_verbatim_stop(receipt, scorer)
    check_fit_block(receipt)
    check_day_counts_and_verification(receipt)
    check_forbidden_reads(receipt, opened)
    check_opened_structure(receipt, opened, stage0)
    check_top_level_sources(receipt, stage0)
    ruler_shas = check_ruler_chain_pinned()
    for module, sha in ruler_shas.items():
        print(f"ruler pinned {module} sha256 {sha}", flush=True)
    hashed = check_opened_bytes(opened)
    payloads = check_generation_receipts(opened)
    wall = time.perf_counter() - started
    print(f"rehashed {hashed} files, checked {payloads} generation receipts, "
          f"wall {wall:.1f}s", flush=True)
    print("PASS all byte checks held", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
