#!/usr/bin/env python3
"""Judge sweep for the B2 receipt: independent re-selection of all five lines
from raw late-store bytes, frozen-ruler aggregation, byte comparison against
.audit/threshold-b2-price-picker.json and the B0/B1 control receipts.
Read-only. Never imports the B2 scorer."""

from __future__ import annotations

import calendar
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
RECEIPT_PATH = ROOT / ".audit/threshold-b2-price-picker.json"
B0_RECEIPT_PATH = ROOT / ".audit/threshold-b0-stage1.json"
B0_JUDGE_PATH = ROOT / ".audit/briefs/threshold-b0-stage1-judge-out.md"
B1_RECEIPT_PATH = ROOT / ".audit/threshold-b1-picker.json"
B1_JUDGE_PATH = ROOT / ".audit/briefs/threshold-b1-picker-judge-out.md"
COVERING_PATH = ROOT / ".audit/briefs/threshold-covering-after-b1-fable-out.md"
LATE_ROOT = ROOT / "artifacts/cache/port/entry_v2/g1/late"
MANIFEST_PATH = LATE_ROOT / "manifest.tsv"
CEILING_PATH = ROOT / ".audit/score_threshold_2022_2024_ceiling.py"

ASSETS = ("HG", "NKD", "SI")
PHASES = (0, 1, 2)
LATE_AGES = (600, 1200, 2400, 3600, 5400, 7200, 10800)
FULL_GRID = (0, 30, 60, 90, 120, 180, 240, 290, 300, 600, 1200, 2400, 3600, 5400, 7200, 10800)
LINE_NAMES = (
    "recside_effprice_all",
    "recside_lagrecord_all",
    "oracleside_effprice",
    "recordside_price_control",
    "cellbest_control",
)
PRIMARY_LINES = ("recside_effprice_all", "recside_lagrecord_all")
EXPECTED_DAYS = {"HG": 197, "NKD": 194, "SI": 191}
RUNGS_USD = {"HG": 2000.0, "NKD": 1500.0, "SI": 1500.0}
DRAWDOWN_LIMIT_USD = 1000.0
ENTRY_CAP = 12
NS = 1_000_000_000
QUARTER = Decimal("0.25")
ASSET_MULTIPLIER = {"HG": 25_000, "NKD": 5, "SI": 5_000}
EFFECTIVE_PRICE_SCALE = Decimal("0.0000000005")
SOL_WINDOW = (
    calendar.timegm((2026, 8, 27, 7, 31, 10, 0, 0, 0)),
    calendar.timegm((2026, 8, 27, 7, 50, 0, 0, 0, 0)),
)


def die(message: str) -> None:
    raise AssertionError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def object_sha256(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def load_ceiling() -> object:
    spec = importlib.util.spec_from_file_location("b2_sweep_ceiling", CEILING_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


CEILING = load_ceiling()

receipt = json.loads(RECEIPT_PATH.read_text())
b0 = json.loads(B0_RECEIPT_PATH.read_text())
b1 = json.loads(B1_RECEIPT_PATH.read_text())
covering = COVERING_PATH.read_text()

started = time.monotonic()

frame_expect = {
    "schema": "QRE2THRESHOLDB2PRICEPICKER1",
    "unit": "B2",
    "status": "LIVE",
    "verdict": "LIVE",
    "ages_seconds": list(LATE_AGES),
    "lines": list(LINE_NAMES),
    "primary_variants": list(PRIMARY_LINES),
    "decomposition_lines": ["oracleside_effprice"],
    "control_lines": ["recordside_price_control", "cellbest_control"],
    "mutants": [
        "oracle_leak_primary",
        "nonready_entered",
        "future_mid_in_pick",
        "control_mismatch_accepted",
    ],
    "locked_asset_days": dict(EXPECTED_DAYS),
    "worker_budget": 13,
    "workers_by_asset": {"HG": 5, "NKD": 4, "SI": 4},
    "asset_chain_workers": 3,
    "asset_multiplier": dict(ASSET_MULTIPLIER),
    "effective_price_scale": "5E-10",
    "tripwire_seconds": 3600.0,
    "dollar_line_reads": 1,
    "passes_over_late_store": 1,
    "age0_cert_close_usd_values_used": 0,
    "dollar_lines_below_age_600": 0,
    "stored_teacher_fields_parsed": [],
    "stored_teacher_open_guard": "PASS",
    "stored_tree_rewritten": False,
    "fit_started": False,
    "judge_started": False,
    "training_scale_relabel_started": False,
    "age180_teacher_join_reopened": False,
    "tickets_37_46_47_started": False,
    "lsp0_started": False,
    "sol_2400_current_price_cap_started": False,
    "touched_2025": False,
    "teacher_cash_can_promote": False,
    "same_variant_witness": "recside_effprice_all",
}
for key, expected in frame_expect.items():
    if receipt.get(key) != expected:
        die(f"receipt frame drifted at {key}: {receipt.get(key)!r} != {expected!r}")
if not 0.0 < float(receipt["wall_clock_seconds"]) < 3600.0:
    die(f"wall clock outside the tripwire: {receipt['wall_clock_seconds']}")
if set(receipt["line_rules"]) != set(LINE_NAMES):
    die("line_rules keys drifted from the frozen family")

bullets = {}
for line in covering.splitlines():
    for name, prefix in (
        ("STOP", "- **STOP, infrastructure.**"),
        ("KILL", "- **KILL.**"),
        ("LIVE", "- **LIVE.**"),
    ):
        if line.startswith(prefix):
            bullets[name] = line[2:]
if set(bullets) != {"STOP", "KILL", "LIVE"}:
    die("covering page stop bullets not found")
for name, text in bullets.items():
    if receipt["dollar_stop"]["verbatim"][name] != text:
        die(f"dollar stop {name} is not verbatim from the covering page")
if receipt["dollar_stop"]["applied"] != bullets["LIVE"]:
    die("applied stop bullet is not the LIVE bullet")
if (
    receipt["dollar_stop"]["verdict"] != "LIVE"
    or receipt["dollar_stop"]["rungs_usd"] != RUNGS_USD
    or receipt["dollar_stop"]["drawdown_limit_usd"] != DRAWDOWN_LIMIT_USD
    or receipt["dollar_stop"]["entry_cap"] != ENTRY_CAP
):
    die("dollar stop frame drifted")

for path_text, expected_sha in receipt["sources"].items():
    actual = sha256_file(ROOT / path_text)
    if actual != expected_sha:
        die(f"source sha drifted for {path_text}: {actual} != {expected_sha}")
if len(receipt["sources"]) != 13:
    die(f"source census drifted: {len(receipt['sources'])}")

precondition = receipt["prior_preconditions"]
expected_precondition = {
    "status": "PASS",
    "b0_receipt": ".audit/threshold-b0-stage1.json",
    "b0_receipt_sha256": sha256_file(B0_RECEIPT_PATH),
    "b0_judge": ".audit/briefs/threshold-b0-stage1-judge-out.md",
    "b0_judge_sha256": sha256_file(B0_JUDGE_PATH),
    "b1_receipt": ".audit/threshold-b1-picker.json",
    "b1_receipt_sha256": sha256_file(B1_RECEIPT_PATH),
    "b1_judge": ".audit/briefs/threshold-b1-picker-judge-out.md",
    "b1_judge_sha256": sha256_file(B1_JUDGE_PATH),
    "manifest_sha256": b0["publication"]["sha256"],
    "locked_asset_days": dict(EXPECTED_DAYS),
}
if precondition != expected_precondition:
    die("prior precondition binding drifted")
if (
    b0.get("schema") != "QRE2THRESHOLDB0STAGE11"
    or b0.get("status") != "LIVE"
    or b1.get("schema") != "QRE2THRESHOLDB1PICKER1"
    or b1.get("status") != "KILL"
    or b1["manifest"]["sha256"] != b0["publication"]["sha256"]
):
    die("B0/B1 receipt frame drifted")

manifest_sha = sha256_file(MANIFEST_PATH)
if manifest_sha != b0["publication"]["sha256"] or manifest_sha != receipt["manifest"]["sha256"]:
    die("manifest sha does not bind B0 publication and the B2 receipt")
manifest_expect = {
    "status": "PASS",
    "path": "artifacts/cache/port/entry_v2/g1/late/manifest.tsv",
    "schema": "QRE2G1LATEMANIFEST1",
    "sha256": manifest_sha,
    "shards": 582,
    "rows": 2_923_344,
    "ready_rows": 2_768_741,
    "clear_candidate_rows": 182_709,
    "asset_days": dict(EXPECTED_DAYS),
    "min_d8": 20220315,
    "max_d8": 20241231,
    "contains_2025": False,
}
if receipt["manifest"] != manifest_expect:
    die(f"manifest block drifted: {receipt['manifest']!r}")

manifest_lines = MANIFEST_PATH.read_text().splitlines()
shard_specs = []
for line in manifest_lines[2:]:
    if not line:
        continue
    fields = line.split("\t")
    if len(fields) != 14:
        die("manifest field count drifted")
    asset, d8_text = fields[0], fields[1]
    d8 = int(d8_text)
    if asset not in ASSETS or d8 >= 20250101 or not 20220309 <= d8:
        die(f"manifest shard outside the frozen store: {asset}/{d8}")
    shard_specs.append(
        {
            "asset": asset,
            "d8": d8,
            "path": ROOT / fields[2],
            "sha256": fields[3],
            "rows": int(fields[4]),
            "ready_rows": int(fields[5]),
            "clear_candidate_rows": int(fields[7]),
            "candidate_path": fields[9],
            "candidate_sha256": fields[10],
        }
    )
counts = {asset: sum(spec["asset"] == asset for spec in shard_specs) for asset in ASSETS}
if (
    len(shard_specs) != 582
    or counts != EXPECTED_DAYS
    or sum(spec["rows"] for spec in shard_specs) != 2_923_344
    or sum(spec["ready_rows"] for spec in shard_specs) != 2_768_741
    or sum(spec["clear_candidate_rows"] for spec in shard_specs) != 182_709
    or len({(spec["asset"], spec["d8"]) for spec in shard_specs}) != 582
    or min(spec["d8"] for spec in shard_specs) != 20220315
    or max(spec["d8"] for spec in shard_specs) != 20241231
):
    die(f"manifest census drifted: {len(shard_specs)} {counts}")
store_files = {path.resolve() for path in LATE_ROOT.rglob("*") if path.is_file()}
if store_files != {MANIFEST_PATH.resolve(), *(spec["path"].resolve() for spec in shard_specs)}:
    die("late tree holds files beyond the manifest census")
shard_bytes = sum(spec["path"].stat().st_size for spec in shard_specs)
if receipt["shard_hash_verification"]["bytes"] != shard_bytes:
    die(
        f"hashed byte count drifted: {receipt['shard_hash_verification']['bytes']} "
        f"!= {shard_bytes}"
    )
if (
    receipt["shard_hash_verification"]["status"] != "PASS"
    or receipt["shard_hash_verification"]["shards"] != 582
    or receipt["shard_hash_verification"]["verified_before_any_dollar"] is not True
):
    die("shard hash verification block drifted")

scoring = receipt["scoring"]
if (
    scoring["status"] != "PASS"
    or scoring["shards_read"] != 582
    or scoring["rows_read"] != 2_923_344
    or scoring["ready_rows"] != 2_768_741
    or scoring["passes_over_late_store"] != 1
    or scoring["age0_cert_close_usd_values_used"] != 0
    or scoring["three_asset_chains"] is not True
    or scoring["worker_budget"] != 13
    or not 0.0 < float(scoring["wall_seconds"]) < 3600.0
):
    die(f"scoring census drifted: {scoring!r}")

projection = receipt["hg_projection"]
b0_max = float(b0["scoring"]["max_shard_wall_seconds"])
expected_projection = math.ceil(197 / 5) * b0_max * 2.0
if (
    projection["status"] != "PASS"
    or projection["hg_shards"] != 197
    or projection["hg_workers"] != 5
    or projection["hg_waves"] != 40
    or projection["line_factor"] != 2.0
    or abs(float(projection["b0_max_shard_wall_seconds"]) - b0_max) > 1e-12
    or abs(float(projection["projected_wall_seconds"]) - expected_projection) > 1e-9
    or projection["tripwire_seconds"] != 3600.0
    or expected_projection >= 3600.0
):
    die(f"HG projection drifted: {projection!r}")

selftest = receipt["selftest"]
if (
    selftest["status"] != "PASS"
    or selftest["synthetic_era_bytes_read"] != 0
    or selftest["red_first_before_era_read"] is not True
    or selftest["checks"]["selftest"]["exit_code"] != 0
    or any(
        selftest["checks"][mutant]["exit_code"] != 1
        or selftest["checks"][mutant]["status"] != "KILLED"
        for mutant in frame_expect["mutants"]
    )
):
    die("selftest block drifted")


def sweep_shard(spec: dict) -> dict:
    if sha256_file(spec["path"]) != spec["sha256"]:
        die(f"shard sha drifted: {spec['asset']}/{spec['d8']}")
    scale = Decimal(ASSET_MULTIPLIER[spec["asset"]]) * EFFECTIVE_PRICE_SCALE
    bases = {}
    late_ready = {age: [] for age in LATE_AGES}
    ages_seen = {}
    rows_read = 0
    ready_rows = 0
    with spec["path"].open("r", encoding="utf-8", newline="") as source:
        source.readline()
        header = source.readline().rstrip("\r\n").split("\t")
        if (
            header[3] != "side"
            or header[11] != "entry_mid2"
            or header[12] != "frozen_cost_usd"
            or header[13] != "status"
            or header[14] != "cert_close_usd"
        ):
            die(f"late shard column order drifted: {spec['path']}")
        for raw in source:
            line = raw.rstrip("\r\n")
            if not line:
                continue
            fields = line.split("\t")
            if len(fields) != 16:
                die(f"late row field count drifted: {spec['path']}")
            rows_read += 1
            candidate_id = fields[0]
            side = int(fields[3])
            phase = int(fields[4])
            decision = int(fields[5])
            age = int(fields[6])
            snapshot = int(fields[7])
            close = int(fields[8])
            status = fields[13]
            if (
                fields[1] != spec["asset"]
                or int(fields[2]) != spec["d8"]
                or side not in (-1, 1)
                or phase not in PHASES
                or age not in FULL_GRID
                or snapshot != ((decision + NS - 1) // NS) * NS + age * NS
                or close <= decision
            ):
                die(f"late row identity drifted: {spec['path']} {candidate_id}")
            payload = (fields[9], fields[10], fields[11], fields[12], fields[14], fields[15])
            if status == "READY":
                if any(value == "" for value in payload):
                    die(f"READY row lacks payload: {candidate_id}")
                ready_rows += 1
            elif any(value != "" for value in payload):
                die(f"{status} row carries payload: {candidate_id}")
            ages_seen.setdefault(candidate_id, []).append(age)
            if age == 0:
                if status != "READY":
                    continue
                bid, ask, mid = int(fields[9]), int(fields[10]), int(fields[11])
                if bid + ask != mid or ask <= bid:
                    die(f"age-0 BBO drifted: {candidate_id}")
                if candidate_id in bases:
                    die(f"age-0 row repeats: {candidate_id}")
                bases[candidate_id] = (side, phase, decision, close, mid)
                continue
            if age not in LATE_AGES or status != "READY":
                continue
            bid, ask, mid = int(fields[9]), int(fields[10]), int(fields[11])
            cost = Decimal(fields[12])
            cash = Decimal(fields[14])
            exit_ts = int(fields[15])
            if bid + ask != mid or ask <= bid:
                die(f"late BBO drifted: {candidate_id}")
            if cash % QUARTER != 0:
                die(f"READY cash is not quarter-quantized: {candidate_id}")
            if cost < 0 or not snapshot <= exit_ts <= close:
                die(f"READY payload law drifted: {candidate_id}")
            late_ready[age].append(
                (candidate_id, side, phase, snapshot, close, decision, mid, cash, exit_ts, cost)
            )
    if rows_read != spec["rows"] or ready_rows != spec["ready_rows"]:
        die(f"shard census drifted: {spec['asset']}/{spec['d8']}")
    if len(ages_seen) != spec["clear_candidate_rows"] or any(
        tuple(ages) != FULL_GRID for ages in ages_seen.values()
    ):
        die(f"candidate grid drifted: {spec['path']}")

    eligible = {age: {name: 0 for name in LINE_NAMES} for age in LATE_AGES}
    agreements = {age: {"pick_agreement": [0, 0], "primary_agreement": [0, 0]} for age in LATE_AGES}
    entries = {age: {name: [] for name in LINE_NAMES} for age in LATE_AGES}
    for age in LATE_AGES:
        cells = {phase: [] for phase in PHASES}
        for row in late_ready[age]:
            candidate_id, side, phase, snapshot, close, decision, mid, cash, exit_ts, cost = row
            base = bases.get(candidate_id)
            if base is None:
                die(f"record base is absent: {candidate_id}")
            base_side, base_phase, base_decision, base_close, base_mid = base
            if (side, phase, decision, close) != (base_side, base_phase, base_decision, base_close):
                die(f"late record identity drifted from base: {candidate_id}")
            record = side * (mid - base_mid)
            effective_price = Decimal(side * mid) * scale + cost
            cells[phase].append(
                {
                    "candidate_id": candidate_id,
                    "side": side,
                    "phase": phase,
                    "snapshot": snapshot,
                    "record": record,
                    "effective_price": effective_price,
                    "cash": cash,
                    "exit_ts": exit_ts,
                    "cost": cost,
                }
            )
        for phase in PHASES:
            rows = cells[phase]
            if not rows:
                continue
            record_leader = min(rows, key=lambda r: (-r["record"], r["candidate_id"]))
            cellbest = min(rows, key=lambda r: (-r["cash"], r["candidate_id"]))
            record_pool = [r for r in rows if r["side"] == record_leader["side"]]
            oracle_pool = [r for r in rows if r["side"] == cellbest["side"]]
            effective = min(record_pool, key=lambda r: (r["effective_price"], r["candidate_id"]))
            lag_record = min(record_pool, key=lambda r: (r["record"], r["candidate_id"]))
            oracle_effective = min(
                oracle_pool, key=lambda r: (r["effective_price"], r["candidate_id"])
            )
            recordside_control = min(record_pool, key=lambda r: (-r["cash"], r["candidate_id"]))
            selected = {
                "recside_effprice_all": effective,
                "recside_lagrecord_all": lag_record,
                "oracleside_effprice": oracle_effective,
                "recordside_price_control": recordside_control,
                "cellbest_control": cellbest if cellbest["cash"] > 0 else None,
            }
            eligible[age]["recside_effprice_all"] += len(record_pool)
            eligible[age]["recside_lagrecord_all"] += len(record_pool)
            eligible[age]["oracleside_effprice"] += len(oracle_pool)
            eligible[age]["recordside_price_control"] += len(record_pool)
            eligible[age]["cellbest_control"] += len(rows)
            agreements[age]["pick_agreement"][0] += int(
                effective["candidate_id"] == recordside_control["candidate_id"]
            )
            agreements[age]["pick_agreement"][1] += 1
            agreements[age]["primary_agreement"][0] += int(
                effective["candidate_id"] == lag_record["candidate_id"]
            )
            agreements[age]["primary_agreement"][1] += 1
            if effective["cash"] > recordside_control["cash"]:
                die(f"bound violated: primary beats its own side maximum in a cell at age {age}")
            for name in LINE_NAMES:
                chosen = selected[name]
                if chosen is None:
                    continue
                entries[age][name].append(
                    CEILING.SelectedName(
                        candidate_id=chosen["candidate_id"],
                        asset=spec["asset"],
                        d8=spec["d8"],
                        phase=phase,
                        decision_ts_ns=chosen["snapshot"],
                        frozen_cost_usd=float(chosen["cost"]),
                        cash_usd=float(chosen["cash"]),
                        exit_ts_ns=chosen["exit_ts"],
                        ready=True,
                        source_candidates=spec["candidate_path"],
                        source_teacher=spec["path"].relative_to(ROOT).as_posix(),
                        candidates_output_sha256=spec["candidate_sha256"],
                        teacher_output_sha256=spec["sha256"],
                    )
                )
    return {
        "asset": spec["asset"],
        "d8": spec["d8"],
        "entries": entries,
        "eligible": eligible,
        "agreements": agreements,
        "rows_read": rows_read,
        "ready_rows": ready_rows,
    }


ordered_specs = sorted(shard_specs, key=lambda spec: (ASSETS.index(spec["asset"]), spec["d8"]))
with ThreadPoolExecutor(max_workers=13) as pool:
    shard_results = list(pool.map(sweep_shard, ordered_specs))
shard_results.sort(key=lambda result: (ASSETS.index(result["asset"]), result["d8"]))
if (
    sum(result["rows_read"] for result in shard_results) != 2_923_344
    or sum(result["ready_rows"] for result in shard_results) != 2_768_741
):
    die("sweep row census drifted from the manifest")
print(f"SWEEP parsed 582 shards wall={time.monotonic() - started:.1f}s", flush=True)


def asset_block(selected: tuple, asset: str) -> dict:
    rows = tuple(row for row in selected if row.asset == asset)
    line = CEILING.summarize_line(rows, EXPECTED_DAYS)
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
        "entry_cap": ENTRY_CAP,
        "entry_cap_ok": line.entry_cap_ok,
        "rung_usd": RUNGS_USD[asset],
        "clears_rung": usd >= RUNGS_USD[asset],
        "shortfall_usd": max(0.0, RUNGS_USD[asset] - usd),
        "drawdown_limit_usd": DRAWDOWN_LIMIT_USD,
        "drawdown_ok": line.max_drawdown_usd < DRAWDOWN_LIMIT_USD,
    }


b0_per_age = b0["per_age"]
b1_per_age = b1["per_age"]
entries_by_age = {
    age: {
        name: tuple(
            entry
            for result in shard_results
            for entry in result["entries"][age][name]
        )
        for name in LINE_NAMES
    }
    for age in LATE_AGES
}
my_per_age = {}
for age in LATE_AGES:
    line_blocks = {}
    for name in LINE_NAMES:
        selected = entries_by_age[age][name]
        line = CEILING.summarize_line(selected, EXPECTED_DAYS)
        decimal_totals = {asset: Decimal(0) for asset in ASSETS}
        for row in selected:
            decimal_totals[row.asset] += Decimal(str(row.cash_usd))
        for asset in ASSETS:
            drift = abs(float(decimal_totals[asset]) - float(line.cash_total_usd[asset]))
            if drift >= 0.005:
                die(f"order-free Decimal total drifted: {name} {age} {asset} {drift}")
        line_blocks[name] = {
            "portfolio_dollar_block": line.as_dict(),
            "assets": {
                asset: {
                    **asset_block(selected, asset),
                    "eligible_candidates": sum(
                        result["eligible"][age][name]
                        for result in shard_results
                        if result["asset"] == asset
                    ),
                    "entered_cells": sum(row.asset == asset for row in selected),
                }
                for asset in ASSETS
            },
        }
    my_cellbest = line_blocks["cellbest_control"]["portfolio_dollar_block"]
    my_recordside = line_blocks["recordside_price_control"]["portfolio_dollar_block"]
    expected_cellbest = b0_per_age[str(age)]["portfolio_dollar_block"]
    expected_recordside = b1_per_age[str(age)]["lines"]["recordside_price"][
        "portfolio_dollar_block"
    ]
    if canonical(my_cellbest) != canonical(expected_cellbest):
        die(f"my recomputed cellbest control differs from the B0 receipt at age {age}")
    if canonical(my_recordside) != canonical(expected_recordside):
        die(f"my recomputed recordside control differs from the B1 receipt at age {age}")
    for control_key, actual in (
        ("cellbest_control", my_cellbest),
        ("recordside_price_control", my_recordside),
    ):
        recorded = receipt[control_key][str(age)]
        if (
            recorded["status"] != "PASS"
            or recorded["byte_equal"] is not True
            or recorded["actual_sha256"] != object_sha256(actual)
            or recorded["expected_sha256"] != object_sha256(actual)
        ):
            die(f"receipt control sha block drifted: {control_key} age {age}")
    agreement_blocks = {}
    for agreement_name in ("pick_agreement", "primary_agreement"):
        agreement_assets = {}
        total_numerator = 0
        total_denominator = 0
        for asset in ASSETS:
            numerator = sum(
                result["agreements"][age][agreement_name][0]
                for result in shard_results
                if result["asset"] == asset
            )
            denominator = sum(
                result["agreements"][age][agreement_name][1]
                for result in shard_results
                if result["asset"] == asset
            )
            agreement_assets[asset] = {
                "numerator": numerator,
                "denominator": denominator,
                "fraction": numerator / denominator if denominator else None,
            }
            total_numerator += numerator
            total_denominator += denominator
        agreement_blocks[agreement_name] = {
            "numerator": total_numerator,
            "denominator": total_denominator,
            "fraction": total_numerator / total_denominator if total_denominator else None,
            "assets": agreement_assets,
            "dollar_attached": False,
        }
    depth_regret = {
        asset: (
            line_blocks["recordside_price_control"]["assets"][asset]["usd_per_asset_day"]
            - line_blocks["recside_effprice_all"]["assets"][asset]["usd_per_asset_day"]
        )
        for asset in ASSETS
    }
    my_per_age[str(age)] = {
        "lines": line_blocks,
        **agreement_blocks,
        "depth_regret_usd_per_day": {"assets": depth_regret, "dollar_attached": False},
    }

if canonical(my_per_age) != canonical(receipt["per_age"]):
    for age in map(str, LATE_AGES):
        for name in LINE_NAMES:
            mine = my_per_age[age]["lines"][name]
            theirs = receipt["per_age"][age]["lines"][name]
            if canonical(mine) != canonical(theirs):
                die(f"per_age mismatch at age {age} line {name}")
        for scalar in ("pick_agreement", "primary_agreement", "depth_regret_usd_per_day"):
            if canonical(my_per_age[age][scalar]) != canonical(receipt["per_age"][age][scalar]):
                die(f"{scalar} mismatch at age {age}")
    die("per_age mismatch not localized")
print("SWEEP per_age byte-equal to the receipt for all five lines and seven ages", flush=True)


def full_block_ok(block: dict) -> bool:
    return bool(
        block["trades"] > 0
        and block["clears_rung"]
        and block["drawdown_ok"]
        and block["entry_cap_ok"]
        and block["overlap_violations"] == 0
    )


def full_line_ok(line: object) -> bool:
    return bool(
        line.trades > 0
        and line.clears_rungs
        and line.max_drawdown_usd < DRAWDOWN_LIMIT_USD
        and line.entry_cap_ok
        and line.overlap_violations == 0
    )


qualifying = {}
for asset in ASSETS:
    ages = []
    for age in LATE_AGES:
        block = b0_per_age[str(age)]["assets"][asset]
        if (
            block["trades"] > 0
            and block["clears_rung"] is True
            and block["entry_cap_ok"] is True
            and block["overlap_violations"] == 0
            and block["drawdown_ok"] is True
        ):
            ages.append(age)
    qualifying[asset] = ages
if {asset: list(ages) for asset, ages in receipt["qualifying_ages_seconds"].items()} != qualifying:
    die("qualifying ages drifted from the B0 receipt derivation")

my_witnesses = {}
for variant in PRIMARY_LINES:
    eligible_ages = {
        asset: tuple(
            age
            for age in qualifying[asset]
            if full_block_ok(my_per_age[str(age)]["lines"][variant]["assets"][asset])
        )
        for asset in ASSETS
    }
    if any(not ages for ages in eligible_ages.values()):
        my_witnesses[variant] = {
            "status": "MISS",
            "variant": variant,
            "eligible_ages_seconds": {
                asset: list(ages) for asset, ages in eligible_ages.items()
            },
        }
        continue
    witness = None
    for combination in itertools.product(*(eligible_ages[asset] for asset in ASSETS)):
        ages = dict(zip(ASSETS, combination))
        selected = tuple(
            row
            for asset in ASSETS
            for row in entries_by_age[ages[asset]][variant]
            if row.asset == asset
        )
        line = CEILING.summarize_line(selected, EXPECTED_DAYS)
        if full_line_ok(line):
            witness = {
                "status": "PASS",
                "variant": variant,
                "ages_seconds": ages,
                "dollar_block": line.as_dict(),
                "eligible_ages_seconds": {
                    asset: list(values) for asset, values in eligible_ages.items()
                },
            }
            break
    if witness is None:
        witness = {
            "status": "MISS",
            "variant": variant,
            "eligible_ages_seconds": {
                asset: list(ages) for asset, ages in eligible_ages.items()
            },
            "combination_blocker": "portfolio full dollar block",
        }
    my_witnesses[variant] = witness

if canonical(my_witnesses) != canonical(receipt["variant_witnesses"]):
    die("variant witnesses drifted from my recomputation")
if my_witnesses["recside_effprice_all"]["status"] != "PASS":
    die("the LIVE witness did not reproduce")
if my_witnesses["recside_effprice_all"]["ages_seconds"] != {"HG": 600, "NKD": 600, "SI": 2400}:
    die(f"witness ages drifted: {my_witnesses['recside_effprice_all']['ages_seconds']!r}")
if my_witnesses["recside_lagrecord_all"]["status"] != "MISS" or any(
    my_witnesses["recside_lagrecord_all"]["eligible_ages_seconds"][asset]
    for asset in ASSETS
):
    die("recside_lagrecord_all should MISS with empty eligible sets")
winning = next(
    (variant for variant in PRIMARY_LINES if my_witnesses[variant]["status"] == "PASS"),
    None,
)
if winning != "recside_effprice_all" or receipt["same_variant_witness"] != winning:
    die(f"winning variant drifted: {winning!r}")
if receipt["verdict"] != "LIVE" or receipt["status"] != "LIVE":
    die("verdict is not LIVE while the witness passes")

mixed_found = None
for assignment in itertools.product(PRIMARY_LINES, repeat=3):
    if len(set(assignment)) == 1:
        continue
    variants = dict(zip(ASSETS, assignment))
    eligible = {
        asset: tuple(
            age
            for age in qualifying[asset]
            if full_block_ok(my_per_age[str(age)]["lines"][variants[asset]]["assets"][asset])
        )
        for asset in ASSETS
    }
    if any(not ages for ages in eligible.values()):
        continue
    for combination in itertools.product(*(eligible[asset] for asset in ASSETS)):
        ages = dict(zip(ASSETS, combination))
        selected = tuple(
            row
            for asset in ASSETS
            for row in entries_by_age[ages[asset]][variants[asset]]
            if row.asset == asset
        )
        if full_line_ok(CEILING.summarize_line(selected, EXPECTED_DAYS)):
            mixed_found = variants
            break
    if mixed_found:
        break
if mixed_found is not None:
    die(f"a mixed assignment clears: {mixed_found!r}")
if receipt["mixed_variant_assignment"] != {"found": False, "ignored_for_live": True}:
    die("mixed variant block drifted")

engine_touched = [
    str(path)
    for path in (ROOT / "engine").rglob("*")
    if path.is_file() and SOL_WINDOW[0] <= path.stat().st_mtime <= SOL_WINDOW[1]
]
if engine_touched:
    die(f"engine files modified during the B2 walk: {engine_touched}")
audit_touched = sorted(
    path.name
    for path in (ROOT / ".audit").rglob("*")
    if path.is_file()
    and "__pycache__" not in path.parts
    and SOL_WINDOW[0] <= path.stat().st_mtime <= SOL_WINDOW[1]
)
if audit_touched != ["score_threshold_b2_price_picker.py", "threshold-b2-price-picker.json"]:
    die(f".audit files beyond the authorized two changed in the walk window: {audit_touched}")


def tree_metadata(path: Path) -> dict:
    files = tuple(sorted(item for item in path.rglob("*") if item.is_file()))
    entries = tuple(
        (item.relative_to(path).as_posix(), item.stat().st_size, item.stat().st_mtime_ns)
        for item in files
    )
    return {
        "files": len(entries),
        "bytes": sum(entry[1] for entry in entries),
        "metadata_sha256": hashlib.sha256(canonical(entries)).hexdigest(),
    }


trees = {
    "late": LATE_ROOT,
    "candidates": ROOT / "artifacts/cache/port/entry_v2/g1/candidates",
    "teacher": ROOT / "artifacts/cache/port/entry_v2/g1/teacher",
    "pivot": ROOT / "artifacts/cache/port/entry_v2/g1/pivot",
    "receipts": ROOT / "artifacts/cache/port/entry_v2/g1/receipts",
}
for name, tree in trees.items():
    now = tree_metadata(tree)
    if now != receipt["protected_trees_after"][name]:
        die(f"protected tree {name} drifted since the receipt")
    if receipt["protected_trees_after"][name] != receipt["protected_trees_before"][name]:
        die(f"protected tree {name} changed during the run")

print(
    f"PASS all byte checks held wall={time.monotonic() - started:.1f}s "
    "verdict=LIVE reproduced from raw bytes",
    flush=True,
)
