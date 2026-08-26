#!/usr/bin/env python3
"""Byte checks behind the Stage 1 judge verdict. Read-only. Rerunnable."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Mapping

REPO = Path(__file__).resolve().parents[1]
RECEIPT_PATH = REPO / ".audit/threshold-pivot-stage1.json"
COVERING_BRIEF = REPO / ".audit/briefs/threshold-covering-after-tape-kill-out.md"
DENSE_ROOT = REPO / "artifacts/entry_v2/tabular_recovery/dense_store"
ASSETS = ("HG", "NKD", "SI")
RUNGS_USD = {"HG": 2000.0, "NKD": 1500.0, "SI": 1500.0}
DRAWDOWN_LIMIT_USD = 1000.0
ENTRY_CAP = 12
CAUSAL_LINES = (
    "pivot_leg_with",
    "pivot_leg_against",
    "pivot_retrace_max",
    "pivot_retrace_min",
    "pivot_age_max",
    "pivot_age_min",
    "pivot_legdur_max",
    "pivot_legdur_min",
)
PEEK_COLUMNS = ("mfe_usd", "mae_usd", "payer", "take_target")
TEACHER_COLUMNS = ["candidate_id", "status", "cert_close_usd", "exit_ts_ns"]
SCAN_COMMAND = "python3 .audit/score_threshold_pivot_name_rules.py"
MUTANTS = (
    "post_flip_leg_used_as_feature",
    "missing_tag_accepted",
    "envelope_includes_non_positive_cell",
)
TOLERANCE = 1e-9

failures: list[str] = []


def check(ok: bool, label: str, detail: str) -> None:
    if not ok:
        failures.append(f"{label}: {detail}")


def close(actual: float, expected: float) -> bool:
    return abs(actual - expected) <= TOLERANCE * max(1.0, abs(expected))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise AssertionError(f"{path} payload {type(value).__name__} expected object")
    return value


def window_weekdays() -> list[int]:
    day = date(2021, 7, 21)
    out: list[int] = []
    while day <= date(2021, 8, 6):
        if day.weekday() < 5:
            out.append(int(day.strftime("%Y%m%d")))
        day += timedelta(days=1)
    return out


def check_dollar_block(
    label: str, block: Mapping[str, object], expected_days: Mapping[str, int]
) -> set[str]:
    for field in ("days", "cash_total_usd", "usd_per_asset_day", "rungs_usd"):
        check(
            set(block[field]) == set(ASSETS),
            f"{label}.{field}",
            f"assets {sorted(block[field])} expected {sorted(ASSETS)}",
        )
    check(
        block["days"] == dict(expected_days),
        f"{label}.days",
        f"{block['days']} expected {dict(expected_days)}",
    )
    check(
        block["rungs_usd"] == RUNGS_USD,
        f"{label}.rungs_usd",
        f"{block['rungs_usd']} expected {RUNGS_USD}",
    )
    check(
        block["entry_cap"] == ENTRY_CAP,
        f"{label}.entry_cap",
        f"{block['entry_cap']} expected {ENTRY_CAP}",
    )
    trades = int(block["trades"])
    check(trades >= 1, f"{label}.trades", f"{trades} expected >= 1")
    cash = {asset: float(block["cash_total_usd"][asset]) for asset in ASSETS}
    usd = {asset: float(block["usd_per_asset_day"][asset]) for asset in ASSETS}
    for asset in ASSETS:
        expected_usd = cash[asset] / int(block["days"][asset])
        check(
            close(usd[asset], expected_usd),
            f"{label}.usd_per_asset_day.{asset}",
            f"{usd[asset]!r} expected cash/days {expected_usd!r}",
        )
    expected_mean = sum(cash.values()) / trades
    check(
        close(float(block["per_trade_mean_usd"]), expected_mean),
        f"{label}.per_trade_mean_usd",
        f"{block['per_trade_mean_usd']!r} expected {expected_mean!r}",
    )
    expected_shortfall = {
        asset: RUNGS_USD[asset] - usd[asset]
        for asset in ASSETS
        if usd[asset] < RUNGS_USD[asset]
    }
    shortfall = {key: float(value) for key, value in block["shortfall_usd"].items()}
    check(
        set(shortfall) == set(expected_shortfall)
        and all(close(shortfall[k], expected_shortfall[k]) for k in expected_shortfall),
        f"{label}.shortfall_usd",
        f"{shortfall!r} expected {expected_shortfall!r}",
    )
    joint_clear = all(usd[asset] >= RUNGS_USD[asset] for asset in ASSETS)
    check(
        bool(block["clears_rungs"]) == joint_clear,
        f"{label}.clears_rungs",
        f"{block['clears_rungs']} expected joint recompute {joint_clear}",
    )
    check(
        not joint_clear,
        f"{label}.joint_gate",
        f"usd {usd!r} clears joint rungs {RUNGS_USD!r}; verdict cannot be KILL",
    )
    gate = trades > 0 and joint_clear
    check(
        bool(block["clears_stage1_dollar_gate"]) == gate,
        f"{label}.clears_stage1_dollar_gate",
        f"{block['clears_stage1_dollar_gate']} expected {gate}",
    )
    full = (
        gate
        and float(block["max_drawdown_usd"]) < DRAWDOWN_LIMIT_USD
        and bool(block["entry_cap_ok"])
        and int(block["overlap_violations"]) == 0
    )
    check(
        bool(block["clears_full_threshold"]) == full,
        f"{label}.clears_full_threshold",
        f"{block['clears_full_threshold']} expected {full}",
    )
    check(
        bool(block["entry_cap_ok"])
        == (int(block["max_entries_portfolio_day"]) <= ENTRY_CAP),
        f"{label}.entry_cap_ok",
        f"{block['entry_cap_ok']} vs max_entries {block['max_entries_portfolio_day']}",
    )
    check(
        int(block["overlap_violations"]) == 0,
        f"{label}.overlap_violations",
        f"{block['overlap_violations']} expected 0",
    )
    matches = int(block["entry_price_twin_matches"])
    cells = int(block["entry_price_twin_cells"])
    expected_rate = matches / cells if cells else 0.0
    check(
        close(float(block["entry_price_twin_match_rate"]), expected_rate),
        f"{label}.entry_price_twin_match_rate",
        f"{block['entry_price_twin_match_rate']!r} expected {expected_rate!r}",
    )
    return {asset for asset in ASSETS if usd[asset] >= RUNGS_USD[asset]}


def stage1_stop_text() -> str:
    text = COVERING_BRIEF.read_text()
    start = text.find("- **KILL at stage 1.**")
    end = text.find("\n- **RUNGS at stage 2.**", start)
    if start < 0 or end < 0:
        raise AssertionError(
            f"{COVERING_BRIEF} lacks stage 1 stop markers ({start}, {end})"
        )
    return text[start:end].strip()


def main() -> int:
    receipt = load_json(RECEIPT_PATH)
    check(
        receipt["schema"] == "QRE2THRESHOLDPIVOTSTAGE11",
        "schema",
        f"{receipt['schema']!r} expected QRE2THRESHOLDPIVOTSTAGE11",
    )
    check(
        receipt["status"] == "KILL" and receipt["verdict"] == "KILL",
        "verdict",
        f"status {receipt['status']!r} verdict {receipt['verdict']!r} expected KILL",
    )
    check(
        receipt["window"] == ["2021-07-21", "2021-08-06"],
        "window",
        f"{receipt['window']!r} expected 2021-07-21..2021-08-06",
    )
    check(
        receipt["block_tag"] == "E1R_raw_THRESHOLD",
        "block_tag",
        f"{receipt['block_tag']!r} expected E1R_raw_THRESHOLD",
    )
    check(
        list(receipt["causal_lines"]) == list(CAUSAL_LINES),
        "causal_lines",
        f"{receipt['causal_lines']!r} expected the frozen eight",
    )
    check(
        sorted(receipt["lines"]) == sorted(CAUSAL_LINES),
        "lines.keys",
        f"{sorted(receipt['lines'])!r} expected the frozen eight",
    )
    check(
        receipt["tie_break"] == ["max decision_ts_ns", "smallest candidate_id"],
        "tie_break",
        f"{receipt['tie_break']!r} changed",
    )
    check(
        receipt["teacher_columns"] == TEACHER_COLUMNS,
        "teacher_columns",
        f"{receipt['teacher_columns']!r} expected {TEACHER_COLUMNS!r}",
    )
    for group in ("candidate_columns", "teacher_columns", "pivot_columns"):
        leaked = [name for name in PEEK_COLUMNS if name in receipt[group]]
        check(not leaked, group, f"peek columns parsed {leaked!r}")
    for counter in (
        "n_dense_feature_bytes_read",
        "n_era_bytes_read",
        "n_forecast_rows_read",
    ):
        check(
            receipt[counter] == 0, counter, f"{receipt[counter]!r} expected 0"
        )

    sources = receipt["sources"]
    joined = sources["joined_artifacts"]
    day_sets: dict[str, set[int]] = {asset: set() for asset in ASSETS}
    hashed_files = 0
    for entry in joined:
        asset = str(entry["asset"])
        d8 = int(entry["d8"])
        day_sets[asset].add(d8)
        check(
            20210721 <= d8 <= 20210806,
            "joined.window",
            f"{asset}/{d8} outside the 2021 THRESHOLD block",
        )
        for part in ("candidates", "pivot", "teacher"):
            block = entry[part]
            path = REPO / str(block["path"])
            actual = sha256_file(path)
            hashed_files += 1
            check(
                actual == block["sha256"],
                f"joined.{part}.sha256",
                f"{path} {actual} expected {block['sha256']}",
            )
        for part in ("candidates", "teacher"):
            generation = load_json(REPO / str(entry[part]["receipt"]))
            check(
                generation["output_sha256"] == entry[part]["sha256"],
                f"joined.{part}.receipt",
                f"{entry[part]['receipt']} output {generation['output_sha256']} "
                f"expected {entry[part]['sha256']}",
            )
        metadata_path = REPO / str(entry["dense_store"]["metadata"]["path"])
        actual = sha256_file(metadata_path)
        hashed_files += 1
        check(
            actual == entry["dense_store"]["metadata"]["sha256"],
            "joined.dense_store.metadata",
            f"{metadata_path} {actual} expected recorded sha",
        )
        check(
            (REPO / str(entry["dense_store"]["artifact_path"])).is_file(),
            "joined.dense_store.artifact",
            f"{entry['dense_store']['artifact_path']} missing",
        )

    weekday_set = set(window_weekdays())
    check(
        day_sets["HG"] == weekday_set and day_sets["NKD"] == weekday_set,
        "roster.HG_NKD",
        f"HG {sorted(day_sets['HG'])} NKD {sorted(day_sets['NKD'])} "
        f"expected the 13 block weekdays",
    )
    check(
        day_sets["SI"] == weekday_set - {20210802},
        "roster.SI",
        f"{sorted(day_sets['SI'])} expected the block weekdays minus 20210802",
    )
    si_dense = sorted(DENSE_ROOT.glob("*/SI/20210802.npz"))
    check(
        not si_dense,
        "roster.SI.20210802",
        f"dense store unexpectedly holds {si_dense!r}",
    )
    expected_days = {asset: len(day_sets[asset]) for asset in ASSETS}
    check(
        expected_days == {"HG": 13, "NKD": 13, "SI": 12},
        "roster.days",
        f"{expected_days} expected HG 13 / NKD 13 / SI 12",
    )

    individual_clears: set[tuple[str, str]] = set()
    for name in CAUSAL_LINES:
        for asset in check_dollar_block(name, receipt["lines"][name], expected_days):
            individual_clears.add((name, asset))
    for asset in check_dollar_block(
        "envelope_pivot8", receipt["envelope_pivot8"], expected_days
    ):
        individual_clears.add(("envelope_pivot8", asset))
    check(
        individual_clears == {("envelope_pivot8", "SI")},
        "individual_rung_clears",
        f"{sorted(individual_clears)} expected only envelope_pivot8 SI",
    )

    stop = receipt["dollar_stop"]
    check(stop["verdict"] == "KILL", "dollar_stop.verdict", f"{stop['verdict']!r}")
    check(
        stop["causal_lines_clearing"] == [],
        "dollar_stop.causal_lines_clearing",
        f"{stop['causal_lines_clearing']!r} expected []",
    )
    check(
        stop["envelope_pivot8_clears"] is False,
        "dollar_stop.envelope_pivot8_clears",
        f"{stop['envelope_pivot8_clears']!r} expected False",
    )
    check(
        stop["rungs_usd"] == RUNGS_USD
        and stop["drawdown_limit_usd"] == DRAWDOWN_LIMIT_USD
        and stop["entry_cap"] == ENTRY_CAP
        and stop["required_trades_min"] == 1
        and stop["required_overlap_violations"] == 0,
        "dollar_stop.constants",
        f"{stop!r} drifted from the frozen charter numbers",
    )
    check(
        stop["verbatim"] == stage1_stop_text(),
        "dollar_stop.verbatim",
        "stage 1 stop text differs from the covering brief bytes",
    )

    expected_commands = {
        "selftest": f"{SCAN_COMMAND} --selftest",
        "mutants": [
            f"QRE2_PIVOT_MUTANT={name} {SCAN_COMMAND} --selftest"
            for name in MUTANTS
        ],
    }
    check(
        receipt["verification_commands"] == expected_commands,
        "verification_commands",
        f"{receipt['verification_commands']!r} expected {expected_commands!r}",
    )

    for label, expectations in {
        "script": {},
        "stage1_brief": {},
        "covering_brief": {},
        "stage0_receipt": {"schema": "QRE2G1PIVOTSTAGE01", "status": "PASS"},
        "feature_rank_receipt": {"schema": "QRE2THRESHOLDFEATURERANK1"},
        "threshold_block": {
            "schema": "QRE2TABPOLICYBLOCK2",
            "tag": "E1R_raw_THRESHOLD",
        },
    }.items():
        source = sources[label]
        path = REPO / str(source["path"])
        actual = sha256_file(path)
        hashed_files += 1
        check(
            actual == source["sha256"],
            f"sources.{label}.sha256",
            f"{path} {actual} expected {source['sha256']}",
        )
        for key, value in expectations.items():
            check(
                source.get(key) == value,
                f"sources.{label}.{key}",
                f"{source.get(key)!r} expected {value!r}",
            )

    stage0 = load_json(REPO / str(sources["stage0_receipt"]["path"]))
    check(
        stage0["schema"] == "QRE2G1PIVOTSTAGE01" and stage0["status"] == "PASS",
        "stage0.status",
        f"{stage0['schema']!r}/{stage0['status']!r} expected PASS receipt",
    )
    check(
        stage0["emitted_2022_2024_tags"] is False,
        "stage0.era_tags",
        f"{stage0['emitted_2022_2024_tags']!r} expected False",
    )
    for entry in joined:
        asset = str(entry["asset"])
        d8 = str(entry["d8"])
        stage0_hash = stage0["determinism_guard"]["per_asset"][asset][
            "threshold_tag_sha256s"
        ][d8]
        check(
            entry["pivot"]["sha256"] == stage0_hash,
            "stage0.tag_hash",
            f"{asset}/{d8} pivot {entry['pivot']['sha256']} expected "
            f"stage 0 {stage0_hash}",
        )

    feature_rank = load_json(REPO / str(sources["feature_rank_receipt"]["path"]))
    check(
        feature_rank["lines"]["argmax"]["days"] == expected_days,
        "feature_rank.days",
        f"{feature_rank['lines']['argmax']['days']!r} expected {expected_days!r}",
    )

    block = load_json(REPO / str(sources["threshold_block"]["path"]))
    check(
        block["schema"] == "QRE2TABPOLICYBLOCK2"
        and block["name"] == "E1R_raw_THRESHOLD"
        and block["bounds"] == [20210721, 20210806],
        "threshold_block",
        f"{block.get('schema')!r}/{block.get('name')!r}/{block.get('bounds')!r}",
    )
    session_keys = {
        (str(row["asset"]), int(row["trading_day"]))
        for row in block["expected_sessions"]
    }
    missing_sessions = [
        (asset, d8)
        for asset in ASSETS
        for d8 in sorted(day_sets[asset])
        if (asset, d8) not in session_keys
    ]
    check(
        not missing_sessions,
        "threshold_block.sessions",
        f"joined asset-days absent from the block: {missing_sessions!r}",
    )

    if failures:
        print(f"FAIL {len(failures)} byte checks broke")
        for line in failures:
            print(f"  {line}")
        return 1
    envelope_usd = receipt["envelope_pivot8"]["usd_per_asset_day"]
    print(
        "PASS all byte checks held: verdict KILL, joint gate recomputed on "
        f"{len(CAUSAL_LINES)} causal lines + envelope_pivot8, "
        f"days {expected_days}, {hashed_files} files rehashed, "
        f"envelope usd/day HG {envelope_usd['HG']:.2f} / "
        f"NKD {envelope_usd['NKD']:.2f} / SI {envelope_usd['SI']:.2f} "
        "(SI-only partial clear, joint rungs missed)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
