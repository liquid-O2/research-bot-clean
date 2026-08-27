#!/usr/bin/env python3
"""Judge sweep for .audit/threshold-b0-stage1.json.

Re-derives every Stage 1 receipt claim from disk bytes: the frame, the
stage-0 binding, all pinned sources, the git and engine state, the
protected trees (metadata now, content against the stage-0 receipt), the
manifest and all 582 shards, the gate, the label-law invariants on every
row, and the dollar lines. Selection is recomputed independently from raw
TSV bytes; aggregation reuses the frozen family ruler
(.audit/score_threshold_2022_2024_ceiling.py summarize_line) where
algorithm identity matters, and an order-free Decimal sum cross-checks it.
The scorer module is imported for constants and validate_rows only;
execute() is never called, so no shard and no receipt byte is rewritten.
Read-only outside /tmp.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
import csv
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
RECEIPT_PATH = ROOT / ".audit/threshold-b0-stage1.json"
STAGE0_RECEIPT_PATH = ROOT / ".audit/threshold-b0-stage0.json"
STAGE0_JUDGE_PATH = ROOT / ".audit/briefs/threshold-b0-stage0-judge-out.md"
RULING_PATH = ROOT / ".audit/briefs/threshold-covering-after-cfit-kill-out.md"
SCORER_PATH = ROOT / ".audit/score_threshold_b0_stage1.py"
RUNNER0_PATH = ROOT / ".audit/threshold_b0_stage0.py"
LATE_ROOT = ROOT / "artifacts/cache/port/entry_v2/g1/late"
RECEIPTS_ROOT = ROOT / "artifacts/cache/port/entry_v2/g1/receipts"
GRID = (0, 30, 60, 90, 120, 180, 240, 290, 300, 600, 1200, 2400, 3600, 5400, 7200, 10800)
LATE_AGES = tuple(age for age in GRID if age >= 600)
ASSETS = ("HG", "NKD", "SI")
EXPECTED_DAYS = {"HG": 197, "NKD": 194, "SI": 191}
RUNGS_USD = {"HG": 2000.0, "NKD": 1500.0, "SI": 1500.0}
EXPECTED_HEAD = "1559c0cf063c298c4c861d2b7852c88a6df88958"
NANOS = 1_000_000_000
FORBIDDEN_COLUMNS = {"mfe_usd", "mae_usd", "payer", "take_target"}
LATE_COLUMNS = (
    "candidate_id", "asset", "d8", "side", "phase",
    "decision_ts_ns", "age_offset_sec", "snapshot_ts_ns",
    "phase_close_ts_ns", "entry_bid_px", "entry_ask_px", "entry_mid2",
    "frozen_cost_usd", "status", "cert_close_usd", "exit_ts_ns",
)
LATE_STATUSES = {"READY", "PHASE_CLOSED", "NO_SNAPSHOT_BBO", "NO_CERTIFIABLE_SUFFIX"}
MARKER_PREFIX = "# QRE2G1LATETEACH1 start_d8=20220309 end_d8_exclusive=20250101 d8="
MARKER_SUFFIX = (
    " resolved_grid_seconds=" + ",".join(map(str, GRID))
    + " anchor=ceil_second(decision_ts_ns)+age_offset_sec*1000000000"
)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"STOP {message}")


def note(message: str) -> None:
    print(message, flush=True)


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def git(arguments: list[str]) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.rstrip()


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


@dataclass(frozen=True, slots=True)
class Entry:
    candidate_id: str
    asset: str
    d8: int
    phase: int
    decision_ts_ns: int
    frozen_cost_usd: float
    cash_usd: float
    exit_ts_ns: int
    cash_text: str


@dataclass(frozen=True, slots=True)
class ShardSweep:
    asset: str
    d8: int
    shard_sha256: str
    candidate_sha256: str
    rows: int
    ready_rows: int
    clear_candidates: int
    entries_by_age: dict[int, tuple[Entry, ...]]
    eligible_by_age: dict[int, int]
    envelope_entries: tuple[Entry, ...]
    envelope_eligible_rows: int
    late_nonpositive_best: dict[int, tuple[int, str]]
    quarter_ok: bool


def _better(prior, nxt) -> bool:
    # (cash desc, candidate_id asc, age asc): the preregistered tie-break.
    if prior is None:
        return True
    if nxt[0] != prior[0]:
        return nxt[0] > prior[0]
    if nxt[1] != prior[1]:
        return nxt[1] < prior[1]
    return nxt[2] < prior[2]


def sweep_shard(job: tuple[str, int, str, str, str, int, int, int]) -> ShardSweep:
    asset, d8, shard_rel, shard_sha, cand_rel, cand_sha, rows_expected, ready_expected = (
        job[0], job[1], job[2], job[3], job[4], job[5], job[6], job[7],
    )
    shard_path = ROOT / shard_rel
    if sha256_path(shard_path) != shard_sha:
        raise SystemExit(f"STOP shard sha drifted: {shard_rel}")
    candidate_sha = sha256_path(ROOT / cand_rel)
    if candidate_sha != cand_sha:
        raise SystemExit(f"STOP candidate sha drifted: {cand_rel}")
    text = shard_path.read_text()
    lines = text.splitlines()
    if not lines[0].startswith(MARKER_PREFIX) or not lines[0].endswith(MARKER_SUFFIX):
        raise SystemExit(f"STOP shard marker drifted: {shard_rel}")
    if int(lines[0][len(MARKER_PREFIX):].split(" ", 1)[0]) != d8:
        raise SystemExit(f"STOP shard marker d8 drifted: {shard_rel}")
    reader = csv.reader(lines[1:], delimiter="\t")
    header = tuple(next(reader))
    if header != LATE_COLUMNS or FORBIDDEN_COLUMNS & set(header):
        raise SystemExit(f"STOP shard columns drifted: {shard_rel}")
    ready_rows = 0
    total_rows = 0
    ages_by_candidate: dict[str, set[int]] = {}
    best_by_cell: dict[tuple[int, int], tuple[float, str, int, Entry]] = {}
    best_envelope: dict[int, tuple[float, str, int, Entry]] = {}
    eligible = {age: 0 for age in GRID}
    envelope_eligible = 0
    quarter_ok = True
    for record in reader:
        if len(record) != len(LATE_COLUMNS):
            raise SystemExit(f"STOP ragged shard row: {shard_rel}")
        row = dict(zip(LATE_COLUMNS, record))
        total_rows += 1
        candidate_id = row["candidate_id"]
        age = int(row["age_offset_sec"])
        decision = int(row["decision_ts_ns"])
        snapshot = int(row["snapshot_ts_ns"])
        phase_close = int(row["phase_close_ts_ns"])
        phase = int(row["phase"])
        status = row["status"]
        if row["asset"] != asset or int(row["d8"]) != d8:
            raise SystemExit(f"STOP shard identity drifted: {shard_rel}")
        if age not in GRID:
            raise SystemExit(f"STOP off-schedule age {age}: {shard_rel}")
        expected_snapshot = ((decision + NANOS - 1) // NANOS) * NANOS + age * NANOS
        if snapshot != expected_snapshot:
            raise SystemExit(f"STOP anchor drifted for {candidate_id}: {shard_rel}")
        if decision > snapshot:
            raise SystemExit(f"STOP pre-decision entry for {candidate_id}: {shard_rel}")
        if status not in LATE_STATUSES:
            raise SystemExit(f"STOP unknown status {status}: {shard_rel}")
        ages_by_candidate.setdefault(candidate_id, set()).add(age)
        payload = (row["frozen_cost_usd"], row["cert_close_usd"], row["exit_ts_ns"])
        if status == "READY":
            if any(value == "" for value in payload):
                raise SystemExit(f"STOP READY row lacks cash fields: {shard_rel}")
            exit_ts = int(row["exit_ts_ns"])
            if not snapshot <= exit_ts <= phase_close:
                raise SystemExit(f"STOP READY exit escapes the law: {shard_rel}")
            cash_decimal = Decimal(row["cert_close_usd"])
            if (cash_decimal * 4) != (cash_decimal * 4).to_integral_value():
                quarter_ok = False
            cash = float(cash_decimal)
            ready_rows += 1
            eligible[age] += 1
            entry = Entry(
                candidate_id=candidate_id,
                asset=asset,
                d8=d8,
                phase=phase,
                decision_ts_ns=snapshot,
                frozen_cost_usd=float(Decimal(row["frozen_cost_usd"])),
                cash_usd=cash,
                exit_ts_ns=exit_ts,
                cash_text=row["cert_close_usd"],
            )
            key = (cash, candidate_id, age)
            cell = (age, phase)
            prior_cell = best_by_cell.get(cell)
            if _better(prior_cell[:3] if prior_cell else None, key):
                best_by_cell[cell] = (cash, candidate_id, age, entry)
            if age >= 600:
                envelope_eligible += 1
                prior = best_envelope.get(phase)
                if _better(prior[:3] if prior else None, key):
                    best_envelope[phase] = (cash, candidate_id, age, entry)
        elif any(value != "" for value in payload):
            raise SystemExit(f"STOP unavailable row carries cash: {shard_rel}")
    if any(tuple(sorted(ages)) != GRID for ages in ages_by_candidate.values()):
        raise SystemExit(f"STOP candidate lacks one row per grid age: {shard_rel}")
    if total_rows != rows_expected or ready_rows != ready_expected:
        raise SystemExit(f"STOP row counts differ from the manifest: {shard_rel}")
    if len(ages_by_candidate) * len(GRID) != total_rows:
        raise SystemExit(f"STOP shard is not one row per candidate and age: {shard_rel}")
    entries_by_age = {
        age: tuple(
            best_by_cell[(age, phase)][3]
            for phase in sorted(p for (a, p) in best_by_cell if a == age)
            if best_by_cell[(age, phase)][0] > 0
        )
        for age in GRID
    }
    late_nonpositive: dict[int, tuple[int, str]] = {}
    for age in LATE_AGES:
        skipped = [
            best_by_cell[(age, phase)][0]
            for phase in sorted(p for (a, p) in best_by_cell if a == age)
            if best_by_cell[(age, phase)][0] <= 0
        ]
        late_nonpositive[age] = (len(skipped), str(sum(map(Decimal, map(str, skipped)))))
    envelope_entries = tuple(
        best_envelope[phase][3]
        for phase in sorted(best_envelope)
        if best_envelope[phase][0] > 0
    )
    return ShardSweep(
        asset=asset,
        d8=d8,
        shard_sha256=shard_sha,
        candidate_sha256=candidate_sha,
        rows=total_rows,
        ready_rows=ready_rows,
        clear_candidates=len(ages_by_candidate),
        entries_by_age=entries_by_age,
        eligible_by_age=eligible,
        envelope_entries=envelope_entries,
        envelope_eligible_rows=envelope_eligible,
        late_nonpositive_best=late_nonpositive,
        quarter_ok=quarter_ok,
    )


def asset_block(entries, asset: str, ceiling, eligible: int) -> dict[str, object]:
    selected = tuple(row for row in entries if row.asset == asset)
    line = ceiling.summarize_line(selected, EXPECTED_DAYS)
    usd = float(line.usd_per_asset_day[asset])
    return {
        "days": EXPECTED_DAYS[asset],
        "cash_total_usd": float(line.cash_total_usd[asset]),
        "usd_per_asset_day": usd,
        "trades": line.trades,
        "per_trade_mean_usd": line.per_trade_mean_usd,
        "max_drawdown_usd": line.max_drawdown_usd,
        "max_entries_portfolio_day": line.max_entries_portfolio_day,
        "overlap_violations": line.overlap_violations,
        "entry_cap": 12,
        "entry_cap_ok": line.entry_cap_ok,
        "rung_usd": RUNGS_USD[asset],
        "clears_rung": usd >= RUNGS_USD[asset],
        "shortfall_usd": max(0.0, RUNGS_USD[asset] - usd),
        "drawdown_limit_usd": 1000.0,
        "drawdown_ok": line.max_drawdown_usd < 1000.0,
        "eligible": eligible,
        "entered_cells": len(selected),
    }


def main() -> int:
    started = time.monotonic()
    receipt = json.loads(RECEIPT_PATH.read_text())

    # 1. Receipt frame.
    check(receipt["schema"] == "QRE2THRESHOLDB0STAGE11", "receipt schema drifted")
    check(receipt["unit"] == "B0_STAGE1", "receipt unit drifted")
    check(receipt["status"] == "LIVE" and receipt["verdict"] == "LIVE", "verdict is not LIVE")
    check("stop_reason" not in receipt, "a LIVE receipt carries a stop_reason")
    check(tuple(receipt["resolved_grid_seconds"]) == GRID, "resolved grid drifted")
    check(
        receipt["anchor_definition"]
        == "ceil_second(decision_ts_ns)+age_offset_sec*1000000000",
        "anchor definition drifted")
    check(receipt["locked_asset_days"] == EXPECTED_DAYS, "locked denominators drifted")
    check(receipt["worker_budget"] == 13, "worker budget is not 13")
    check(receipt["workers_by_asset"] == {"HG": 5, "NKD": 4, "SI": 4}, "worker split drifted")
    check(receipt["tripwire_seconds"] == 7200, "tripwire drifted")
    check(0 < receipt["wall_clock_seconds"] < 7200, "wall clock escapes the tripwire")
    check(receipt["stored_teacher_fields_parsed"] == [], "a stored teacher field was parsed")
    check(receipt["stored_teacher_open_guard"] == "PASS", "teacher open guard did not pass")
    for tree in ("candidate", "teacher", "pivot", "receipts"):
        check(receipt[f"stored_{tree}_tree_rewritten"] is False, f"{tree} tree rewritten")
    for flag in (
        "picker_started", "feature_plane_started",
        "ticket_46_at_scale_started", "tickets_37_47_started",
    ):
        check(receipt[flag] is False, f"{flag} is not false")
    check(receipt["dollar_line_reads"] == 1, "dollar line reads is not exactly 1")
    check(receipt["build_started"] is True and receipt["build"]["status"] == "PASS",
          "build block drifted")
    check(receipt["scoring"]["status"] == "PASS", "scoring status drifted")
    check(receipt["scoring"]["passes_over_late_store"] == 1, "more than one scoring pass")
    check(receipt["scoring"]["shards_read"] == 582, "scoring shard count drifted")
    check(receipt["rule"].startswith("At each preregistered grid age"), "rule text drifted")
    note("PASS receipt frame")

    # 2. Stage-0 precondition, bound by sha to the judged bytes.
    precondition = receipt["stage0_precondition"]
    check(precondition["status"] == "PASS", "stage-0 precondition not PASS")
    check(precondition["receipt_sha256"] == sha256_path(STAGE0_RECEIPT_PATH),
          "stage-0 receipt sha drifted")
    check(precondition["judge_sha256"] == sha256_path(STAGE0_JUDGE_PATH),
          "stage-0 judge sha drifted")
    check(STAGE0_JUDGE_PATH.read_text().startswith(
        "# B0 Stage 0 judge verdict. Fable.\n\n**PASS.**"),
        "stage-0 judge verdict is not the PASS page")
    stage0 = json.loads(STAGE0_RECEIPT_PATH.read_text())
    check(stage0["status"] == "PASS" and stage0["stage1_started"] is False,
          "stage-0 receipt state drifted")
    check(tuple(precondition["resolved_grid_seconds"]) == GRID, "precondition grid drifted")
    check(precondition["locked_asset_days"] == EXPECTED_DAYS, "precondition days drifted")
    note("PASS stage-0 precondition bound")

    # 3. Pinned sources, byte for byte.
    for rel, sha in receipt["sources"].items():
        check(sha256_path(ROOT / rel) == sha, f"pinned source drifted: {rel}")
    check(len(receipt["sources"]) == 13, "source count drifted")
    check(".audit/score_threshold_b0_stage1.py" in receipt["sources"],
          "the scorer does not hash itself")
    note("PASS 13 pinned sources rehashed")

    # 4. Git and engine state, anchored to the stage-0 judged tree.
    check(git(["rev-parse", "HEAD"]) == EXPECTED_HEAD, "HEAD moved")
    status_lines = git([
        "status", "--porcelain", "--untracked-files=all", "--", "engine/entry_v2",
    ]).splitlines()
    live_diff = sorted(line[3:] for line in status_lines if len(line) >= 4)
    check(live_diff == sorted(stage0["authorized_engine_diff_paths"]),
          f"engine diff escaped the stage-0 authorization: {live_diff}")
    runner0 = load_module("threshold_b0_stage0_judged", RUNNER0_PATH)
    check(runner0._engine_tree_sha256()
          == stage0["engine_tree_end"]["engine_tree_sha256"],
          "engine tree differs from the stage-0 judged end state")
    note("PASS git state, engine tree equals the stage-0 judged sha")

    # 5. Protected trees: metadata now, content against the stage-0 receipt.
    scorer = load_module("threshold_b0_stage1_scorer", SCORER_PATH)
    metadata = scorer._protected_metadata()
    check(metadata == receipt["protected_trees_before"],
          "protected metadata differs from the receipt before block")
    check(metadata == receipt["protected_trees_after"],
          "protected metadata differs from the receipt after block")
    fingerprints = runner0._protected_fingerprints()
    check(fingerprints == stage0["protected_trees_before"],
          "protected tree content differs from the stage-0 before fingerprints")
    check(fingerprints == stage0["protected_trees_after"],
          "protected tree content differs from the stage-0 after fingerprints")
    note("PASS protected trees: metadata equal now, content equal to stage-0 judgment")

    # 6. Manifest, census, and candidate receipts.
    publication = receipt["publication"]
    check(sha256_path(LATE_ROOT / "manifest.tsv") == publication["sha256"],
          "manifest sha drifted")
    manifest_lines = (LATE_ROOT / "manifest.tsv").read_text().splitlines()
    check(manifest_lines[0] == (
        "# QRE2G1LATEMANIFEST1 start_d8=20220309 end_d8_exclusive=20250101 "
        "resolved_grid_seconds=" + ",".join(map(str, GRID))
        + " anchor=ceil_second(decision_ts_ns)+age_offset_sec*1000000000"),
        "manifest marker drifted")
    manifest_rows = [line.split("\t") for line in manifest_lines[2:]]
    check(len(manifest_rows) == 582 == publication["shards"], "manifest shard count drifted")
    census = {(row[0], int(row[1])) for row in manifest_rows}
    check(len(census) == 582, "manifest carries a duplicate asset-day")
    per_asset = {asset: sum(1 for a, _ in census if a == asset) for asset in ASSETS}
    check(per_asset == EXPECTED_DAYS, f"manifest per-asset counts drifted: {per_asset}")
    gate = receipt["gate"]
    check(min(d8 for _, d8 in census) == gate["min_d8"] == 20220315, "min d8 drifted")
    check(max(d8 for _, d8 in census) == gate["max_d8"] == 20241231, "max d8 drifted")
    late_files = sorted(
        path.relative_to(LATE_ROOT).as_posix()
        for path in LATE_ROOT.rglob("*") if path.is_file())
    expected_files = sorted(
        [f"{asset}/{d8}.tsv" for asset, d8 in census] + ["manifest.tsv"])
    check(late_files == expected_files, "late tree carries unexpected files")
    empties = gate["empty_selected_asset_days"]
    check(len(empties) == 12, "empty asset-day count drifted")
    for token in empties:
        asset, d8_text = token.split("/")
        check((asset, int(d8_text)) not in census, f"empty day carries a shard: {token}")
        empty_receipt = json.loads(
            (RECEIPTS_ROOT / asset / f"{d8_text}.candidates.json").read_text())
        check(empty_receipt["rows"] == 0, f"empty day has candidate rows: {token}")
    pilot_row = next(row for row in manifest_rows if row[0] == "HG" and row[1] == "20221003")
    check(pilot_row[3] == stage0["pilot"]["output_sha256"],
          "HG/20221003 shard is not the stage-0 pilot bytes")
    for row in manifest_rows:
        gen = json.loads((ROOT / row[11]).read_text())
        check(gen["output_sha256"] == row[10], f"candidate receipt sha differs: {row[11]}")
        check(int(gen["rows"]) == int(row[6]), f"candidate receipt rows differ: {row[11]}")
        check(gen["source_hashes"]["event_pack_sha256"] == row[13],
              f"event hash differs: {row[11]}")
    note("PASS manifest census, empties, pilot anchor, 582 candidate receipts")

    # 7. Gate re-derivation from the pinned forecast bytes.
    ceiling = scorer.CEILING
    rows, window_days, n_read = ceiling.load_window_forecast_rows(scorer.FORECAST_PATH)
    routed, refused = ceiling.route_catboost_daily(rows)
    selected_flags = ceiling.select_expanding_median(routed)
    check(n_read == gate["forecast_rows_read"], "forecast rows read drifted")
    check(len(window_days) == gate["forecast_window_days"] == 708, "window days drifted")
    check(len(routed) == gate["routed_days"] == 708, "routed days drifted")
    check(list(refused) == gate["refused_days"] == [], "refused days drifted")
    check(int(sum(selected_flags)) == gate["selected_days"] == 198, "selected days drifted")
    selected_d8s = {int(day.d8) for day, flag in zip(routed, selected_flags) if flag}
    expected_census = {
        (asset, d8) for asset in ASSETS for d8 in selected_d8s
    } - {(token.split("/")[0], int(token.split("/")[1])) for token in empties}
    check(expected_census == census, "gate selection differs from the manifest census")
    check(gate["locked_asset_day_total"] == 582 and gate["locked_asset_days"] == EXPECTED_DAYS,
          "gate denominators drifted")
    note("PASS gate re-derived from the forecast: 708 routed, 198 selected, 582 locked")

    # 8. Every shard: hashes, label law, independent selection.
    jobs = [
        (row[0], int(row[1]), row[2], row[3], row[9], row[10], int(row[4]), int(row[5]))
        for row in manifest_rows
    ]
    with ProcessPoolExecutor(max_workers=13) as executor:
        sweeps = list(executor.map(sweep_shard, jobs, chunksize=8))
    order = {asset: index for index, asset in enumerate(ASSETS)}
    sweeps.sort(key=lambda sweep: (order[sweep.asset], sweep.d8))
    check(sum(sweep.rows for sweep in sweeps) == publication["rows"]
          == receipt["build"]["rows"] == 2923344, "total rows drifted")
    check(sum(sweep.ready_rows for sweep in sweeps) == publication["ready_rows"]
          == receipt["build"]["ready_rows"] == 2768741, "ready rows drifted")
    check(sum(sweep.clear_candidates for sweep in sweeps)
          == publication["clear_candidate_rows"]
          == receipt["build"]["clear_candidate_rows"] == 182709,
          "clear candidate rows drifted")
    check(all(sweep.quarter_ok for sweep in sweeps),
          "a READY cash value is not quarter-dollar quantized")
    note("PASS 582 shards rehashed, label law held on all 2,923,344 rows")

    # 9. Dollar lines: independent selection, frozen-ruler aggregation.
    per_age_entries = {
        age: tuple(entry for sweep in sweeps for entry in sweep.entries_by_age[age])
        for age in GRID
    }
    eligible_by_age = {
        age: {
            asset: sum(
                sweep.eligible_by_age[age] for sweep in sweeps if sweep.asset == asset)
            for asset in ASSETS
        }
        for age in GRID
    }
    for age in GRID:
        block = receipt["per_age"][str(age)]
        entries = per_age_entries[age]
        line = ceiling.summarize_line(entries, EXPECTED_DAYS)
        check(line.as_dict() == block["portfolio_dollar_block"],
              f"portfolio dollar block differs at age {age}")
        for asset in ASSETS:
            mine = asset_block(entries, asset, ceiling, eligible_by_age[age][asset])
            theirs = dict(block["assets"][asset])
            check(mine.pop("eligible") == theirs.pop("eligible_candidates"),
                  f"eligible candidates differ at age {age} {asset}")
            check(mine.pop("entered_cells") == theirs.pop("entered_cells"),
                  f"entered cells differ at age {age} {asset}")
            check(mine == theirs, f"asset block differs at age {age} {asset}")
        exact = {
            asset: sum(
                (Decimal(entry.cash_text) for entry in entries if entry.asset == asset),
                Decimal(0))
            for asset in ASSETS
        }
        for asset in ASSETS:
            drift = abs(
                exact[asset]
                - Decimal(str(block["assets"][asset]["cash_total_usd"])))
            check(drift < Decimal("0.005"), f"decimal cash drifted at age {age} {asset}")
    envelope_entries = tuple(
        entry for sweep in sweeps for entry in sweep.envelope_entries)
    envelope_line = ceiling.summarize_line(envelope_entries, EXPECTED_DAYS)
    check(envelope_line.as_dict()
          == receipt["late_envelope"]["portfolio_dollar_block"],
          "envelope portfolio block differs")
    for asset in ASSETS:
        mine = asset_block(
            envelope_entries, asset, ceiling,
            sum(s.envelope_eligible_rows for s in sweeps if s.asset == asset))
        theirs = dict(receipt["late_envelope"]["assets"][asset])
        check(mine.pop("eligible") == theirs.pop("eligible_candidate_age_rows"),
              f"envelope eligible rows differ for {asset}")
        check(mine.pop("entered_cells") == theirs.pop("entered_cells"),
              f"envelope entered cells differ for {asset}")
        check(mine == theirs, f"envelope asset block differs for {asset}")
        for age in LATE_AGES:
            check(mine["cash_total_usd"]
                  >= receipt["per_age"][str(age)]["assets"][asset]["cash_total_usd"],
                  f"envelope does not dominate age {age} for {asset}")
    note("PASS per-age lines, envelope, and dominance recomputed from independent selection")

    # 10. Anchor controls at or under 300.
    stored = json.loads(
        (ROOT / ".audit/threshold-2022-2024-ceiling.json").read_text())
    stored_anchor = stored["gated"]["usd_per_asset_day"]
    for age in GRID:
        if age > 300:
            continue
        for asset in ASSETS:
            control = receipt["anchor_controls_at_or_under_300"][str(age)][asset]
            late = receipt["per_age"][str(age)]["assets"][asset]["usd_per_asset_day"]
            check(control["late_repriced_usd_per_asset_day"] == late,
                  f"control late line differs at age {age} {asset}")
            check(control["stored_ceiling_usd_per_asset_day"]
                  == float(stored_anchor[asset]),
                  f"control stored line differs at age {age} {asset}")
            check(control["drift_usd_per_asset_day"]
                  == late - float(stored_anchor[asset]),
                  f"control drift differs at age {age} {asset}")
    note("PASS anchor controls recomputed against the stored ceiling")

    # 11. Witness, verdict logic, and the stop verbatim.
    def qualifies(age: int, asset: str) -> bool:
        block = receipt["per_age"][str(age)]["assets"][asset]
        return bool(
            block["trades"] > 0 and block["clears_rung"]
            and block["entry_cap_ok"] and block["overlap_violations"] == 0)
    qualifying = {
        asset: tuple(age for age in LATE_AGES if qualifies(age, asset))
        for asset in ASSETS
    }
    check(all(qualifying.values()), "an asset lacks a qualifying fixed late age")
    witness = None
    for combination in itertools.product(*(qualifying[asset] for asset in ASSETS)):
        ages = dict(zip(ASSETS, combination))
        entries = tuple(
            entry
            for asset in ASSETS
            for entry in per_age_entries[ages[asset]]
            if entry.asset == asset)
        line = ceiling.summarize_line(entries, EXPECTED_DAYS)
        if (line.trades > 0 and line.clears_rungs and line.max_drawdown_usd < 1000.0
                and line.entry_cap_ok and line.overlap_violations == 0):
            witness = {"ages_seconds": ages, "dollar_block": line.as_dict()}
            break
    check(witness is not None, "no fixed-policy witness re-derives")
    check(receipt["fixed_policy_witness"]["status"] == "PASS", "witness status drifted")
    check(receipt["fixed_policy_witness"]["ages_seconds"] == witness["ages_seconds"]
          == {"HG": 600, "NKD": 600, "SI": 600}, "witness ages drifted")
    check(receipt["fixed_policy_witness"]["dollar_block"] == witness["dollar_block"],
          "witness dollar block differs")
    check(witness["dollar_block"]
          == receipt["per_age"]["600"]["portfolio_dollar_block"],
          "witness block is not the age-600 portfolio block")
    envelope_misses = {
        asset: receipt["late_envelope"]["assets"][asset]["shortfall_usd"]
        for asset in ASSETS
        if not receipt["late_envelope"]["assets"][asset]["clears_rung"]
    }
    check(envelope_misses == {} == receipt["dollar_stop"]["envelope_shortfall_usd"],
          "envelope shortfall drifted")
    check(receipt["dollar_stop"]["verdict"] == "LIVE", "dollar stop verdict drifted")
    check(receipt["dollar_stop"]["rungs_usd"] == RUNGS_USD
          and receipt["dollar_stop"]["drawdown_limit_usd"] == 1000.0
          and receipt["dollar_stop"]["entry_cap"] == 12, "dollar stop constants drifted")
    ruling = RULING_PATH.read_text()
    for verdict_name in ("KILL", "LIVE", "ENVELOPE-ONLY"):
        text = receipt["dollar_stop"]["verbatim"][verdict_name]
        check(normalize(text) in normalize(ruling),
              f"{verdict_name} verbatim is not the ruling bullet")
    check(receipt["dollar_stop"]["applied"]
          == receipt["dollar_stop"]["verbatim"]["LIVE"],
          "applied stop is not the LIVE bullet")
    note("PASS witness at 600/600/600 re-derived, verdict logic LIVE, stop verbatim bound")

    # 12. Positive-cash clause, quantified at the late ages. Wherever the
    # receipt claims a rung clears, it must still clear with the skipped
    # non-positive cell-bests added back, so the clause never decides a rung.
    for age in LATE_AGES:
        for asset in ASSETS:
            block = receipt["per_age"][str(age)]["assets"][asset]
            skipped_cells = sum(
                sweep.late_nonpositive_best[age][0]
                for sweep in sweeps if sweep.asset == asset)
            skipped_cash = sum(
                Decimal(sweep.late_nonpositive_best[age][1])
                for sweep in sweeps if sweep.asset == asset)
            unfiltered_usd = float(
                (Decimal(str(block["cash_total_usd"])) + skipped_cash)
                / EXPECTED_DAYS[asset])
            if block["clears_rung"]:
                check(unfiltered_usd >= RUNGS_USD[asset],
                      f"unfiltered line misses the rung at age {age} {asset}")
            if age == 600:
                note(
                    f"positive-cash clause age 600 {asset}: {skipped_cells} cells "
                    f"skipped, {skipped_cash} usd, unfiltered "
                    f"{unfiltered_usd:.2f} vs rung {RUNGS_USD[asset]:.0f}")
    note("PASS positive-cash clause never decides a claimed rung clear")

    # 13. Selftest rerun and named-seam mutants.
    selftest = subprocess.run(
        [sys.executable, str(SCORER_PATH), "--selftest"],
        cwd=ROOT, capture_output=True, text=True)
    check(selftest.returncode == 0, f"selftest rerun failed: {selftest.stderr}")
    payload = json.loads(selftest.stdout)
    check(payload["status"] == "PASS" and payload["synthetic_era_bytes_read"] == 0,
          "selftest payload drifted")
    check(payload["mutants"] == {name: "RED" for name in (
        "off_schedule_age_accepted", "pre_decision_entry_accepted",
        "missing_age_row_covered", "candidate_id_guard")},
        "selftest mutants are not all RED")
    check(receipt["selftest"]["mutants"] == payload["mutants"],
          "receipt selftest mutants drifted")
    base = tuple(
        scorer._synthetic_row("a", age) for age in GRID
    ) + tuple(
        scorer._synthetic_row("b", age) for age in GRID
    )
    expected_ids = frozenset({"a", "b"})
    named_seams = (
        ((*base, scorer._synthetic_row("a", 601)), "off-schedule late age"),
        ((scorer._replace_snapshot(base[0], base[0].decision_ts_ns - 1), *base[1:]),
         "late entry precedes its stored decision"),
        (base[:-1], "late candidate lacks one row per grid age"),
        (tuple(
            scorer.ScoreRow(
                candidate_id="corrupted" if row.candidate_id == "a" else row.candidate_id,
                asset=row.asset, d8=row.d8, phase=row.phase,
                decision_ts_ns=row.decision_ts_ns, age=row.age,
                snapshot_ts_ns=row.snapshot_ts_ns,
                phase_close_ts_ns=row.phase_close_ts_ns, status=row.status,
                frozen_cost_usd=row.frozen_cost_usd, cash_usd=row.cash_usd,
                exit_ts_ns=row.exit_ts_ns,
            ) for row in base),
         "late candidate identity differs from the source table"),
    )
    for mutant_rows, seam in named_seams:
        try:
            scorer.validate_rows(mutant_rows, expected_ids, "HG", 20220103)
        except scorer.Stage1Stop as error:
            check(seam in str(error), f"mutant died off-seam: {error}")
        else:
            check(False, f"mutant stayed green for seam: {seam}")
    note("PASS selftest rerun green, four mutants die on their named seams")

    note(f"PASS all byte checks held wall={time.monotonic() - started:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
