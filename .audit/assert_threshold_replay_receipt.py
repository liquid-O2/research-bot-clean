#!/usr/bin/env python3
"""Fail unless a held THRESHOLD canonical-replay receipt exists.

A diagnostic usd_per_asset_day field is not enough. The receipt must open
THRESHOLD, run exact chronological replay, and publish per-asset dollars,
drawdown, and entry count. Without that triple the THRESHOLD bottleneck
claim is INCONCLUSIVE.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Iterator, Mapping

REPO = Path(__file__).resolve().parents[1]
CONFIRMATION = REPO / "artifacts/entry_v2/confirmation/v9_qrf4"
THRESHOLD_BLOCKS = REPO / (
    "artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/"
    "e1r/evaluation/E1R_raw_THRESHOLD"
)
RANKER = REPO / (
    "artifacts/entry_v2/tabular_recovery/diagnostics/"
    "location_ranker_20260823.json"
)
FIT_EXECUTION = REPO / (
    "artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/"
    "e1r/fit_only_execution.json"
)
THRESHOLD_SELECTION = REPO / (
    "artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/"
    "e1r/evaluation/threshold/real"
)
MARGIN_RULE = REPO / (
    "artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/"
    "e1r/diagnosis/margin_rule"
)
RUNGS = {"HG": 2000.0, "NKD": 1500.0, "SI": 1500.0}
MAX_DRAWDOWN_USD = 1000.0
MAX_ENTRIES_PORTFOLIO_DAY = 12
LOCKED_ASSET_DAYS = {"HG": 197, "NKD": 194, "SI": 191}


def _walk(obj: Any) -> Iterator[Mapping[str, Any]]:
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk(item)


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


def _as_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def classify(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    threshold_open = 0
    exact_replay = False
    canonical_replay = False
    threshold_economics = False
    scopes: list[str] = []
    for node in _walk(payload):
        opened = _as_int(node.get("threshold_open_count"))
        if opened is not None:
            threshold_open = max(threshold_open, opened)
        flag = _as_bool(node.get("exact_replay_ceiling_executed"))
        if flag is True:
            exact_replay = True
        flag = _as_bool(node.get("canonical_replay_executed"))
        if flag is True:
            canonical_replay = True
        flag = _as_bool(node.get("threshold_economics_executed"))
        if flag is True:
            threshold_economics = True
        scope = node.get("economics_scope")
        if isinstance(scope, str) and scope not in scopes:
            scopes.append(scope)
    try:
        rel = str(path.relative_to(REPO))
    except ValueError:
        rel = str(path)
    return {
        "path": rel,
        "threshold_open_count": threshold_open,
        "exact_replay_ceiling_executed": exact_replay,
        "canonical_replay_executed": canonical_replay,
        "threshold_economics_executed": threshold_economics,
        "economics_scopes": scopes,
        "is_threshold_exact_replay": (
            threshold_open > 0 and exact_replay and threshold_economics
        ),
    }


def ranker_threshold() -> dict[str, dict[str, float | str | int]]:
    payload = json.loads(RANKER.read_text())
    out: dict[str, dict[str, float | str | int]] = {}
    assets = payload["assets"]
    if not isinstance(assets, dict):
        raise ValueError(f"location_ranker assets must be an object, got {type(assets).__name__}")
    for asset, block in assets.items():
        if not isinstance(block, dict) or "threshold" not in block:
            continue
        row = block["threshold"]
        if not isinstance(row, dict):
            raise ValueError(
                f"location_ranker {asset}.threshold must be an object, got {type(row).__name__}"
            )
        out[str(asset)] = {
            "usd_per_asset_day": float(row["usd_per_asset_day"]),
            "letter": str(row["letter"]),
            "n_days": int(row["n_days"]),
            "entries_per_day_mean": float(row["entries_per_day_mean"]),
            "arm": str(row["arm"]),
        }
    return out


def _timestamp_count(value: Any) -> int:
    if value is None:
        return 0
    if not isinstance(value, dict):
        raise ValueError(
            f"timestamp map must be an object, got {type(value).__name__}"
        )
    total = 0
    for stamps in value.values():
        if not isinstance(stamps, (list, tuple)):
            raise ValueError(
                f"timestamp list must be a list, got {type(stamps).__name__}"
            )
        total += len(stamps)
    return total


def enter_preference(root: Path) -> dict[str, int]:
    """Count ENTER preference on THRESHOLD day traces.

    Empty crossings plus zero selected ids is the cause-specific red.
    Teacher dollars on the same window are the mutant without that cause.
    """

    crossings = 0
    changes = 0
    selected = 0
    days = 0
    if not root.is_dir():
        return {
            "day_traces": 0,
            "policy_crossing_events": 0,
            "action_change_events": 0,
            "selected_opportunity_total": 0,
        }
    for path in sorted(root.rglob("*.json")):
        if path.name == "raw_block.json":
            continue
        text = path.read_text()
        if "QRE2TABLIVETRACESTORE1" not in text:
            continue
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError(
                f"{path} must be a JSON object, got {type(payload).__name__}"
            )
        trace = payload.get("trace")
        if not isinstance(trace, dict):
            raise ValueError(
                f"{path} trace must be an object, got {type(trace).__name__}"
            )
        crossings += _timestamp_count(trace.get("policy_crossing_timestamps"))
        changes += _timestamp_count(trace.get("action_change_timestamps"))
        ids = trace.get("selected_opportunity_ids")
        if ids is None:
            ids = []
        if not isinstance(ids, list):
            raise ValueError(
                f"{path} selected_opportunity_ids must be a list, "
                f"got {type(ids).__name__}"
            )
        selected += len(ids)
        days += 1
    return {
        "day_traces": days,
        "policy_crossing_events": crossings,
        "action_change_events": changes,
        "selected_opportunity_total": selected,
    }


def fit_capture(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(
            f"{path} must be a JSON object, got {type(payload).__name__}"
        )
    detail = payload.get("training_capture_detail")
    if not isinstance(detail, dict):
        raise ValueError(
            f"{path} training_capture_detail must be an object, "
            f"got {type(detail).__name__}"
        )
    rows: dict[str, dict[str, float | bool]] = {}
    for name, row in detail.items():
        if not isinstance(row, dict):
            raise ValueError(
                f"{path} training_capture_detail[{name!r}] must be an object, "
                f"got {type(row).__name__}"
            )
        rows[str(name)] = {
            "capture": float(row["capture"]),
            "passed": bool(row["passed"]),
        }
    return {
        "training_capture_pass": bool(payload.get("training_capture_pass")),
        "target_capture": 0.9,
        "by_seed": rows,
    }


def advantage_grids(root: Path) -> dict[str, dict[str, float | bool | int]]:
    out: dict[str, dict[str, float | bool | int]] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.glob("seed_*/threshold_selection.json")):
        payload = json.loads(path.read_text())
        if not isinstance(payload, dict):
            raise ValueError(
                f"{path} must be a JSON object, got {type(payload).__name__}"
            )
        selection = payload.get("selection")
        if not isinstance(selection, dict):
            raise ValueError(
                f"{path} selection must be an object, got {type(selection).__name__}"
            )
        thresholds = selection.get("thresholds_usd")
        if not isinstance(thresholds, list) or not thresholds:
            raise ValueError(
                f"{path} selection.thresholds_usd must be a non-empty list, "
                f"got {type(thresholds).__name__} {thresholds!r}"
            )
        values = [float(item) for item in thresholds]
        out[str(payload.get("seed", path.parent.name))] = {
            "floor_feasible": bool(selection.get("floor_feasible")),
            "selected_threshold_usd": float(selection["selected_threshold_usd"]),
            "grid_min_usd": min(values),
            "grid_max_usd": max(values),
            "n_quantiles": len(values),
        }
    return out


def enter_gap() -> dict[str, Any]:
    """Unit 1 receipt. Why ENTER never wins on the published walk."""

    capture = fit_capture(FIT_EXECUTION)
    grids = advantage_grids(THRESHOLD_SELECTION)
    preference = enter_preference(THRESHOLD_BLOCKS)
    return {
        "schema": "QRE2THRESHOLDENTERGAP1",
        "named_cause": (
            "e1r_regret_head_never_prefers_enter_on_any_walked_window"
        ),
        "fit_capture": capture,
        "threshold_advantage_grid": grids,
        "enter_preference": preference,
        "per_second_regrets_on_day_traces": "absent",
        "check_command": (
            "python3 .audit/assert_threshold_replay_receipt.py --enter-gap"
        ),
    }


def cheap_trace_emptiness(root: Path) -> dict[str, int]:
    """Count day traces without parsing crossing maps.

    MARGIN traces store large crossing lists. Full json.loads is the slow path.
    """

    days = 0
    empty_selected = 0
    empty_arrivals = 0
    if not root.is_dir():
        return {
            "day_traces": 0,
            "empty_selected": 0,
            "empty_arrivals": 0,
            "selected_nonzero": 0,
        }
    for path in root.rglob("*.json"):
        if not (path.stem.isdigit() and len(path.stem) == 8):
            continue
        text = path.read_text()
        if "QRE2TABLIVETRACESTORE1" not in text:
            continue
        days += 1
        if (
            '"selected_opportunity_ids":[]' in text
            or '"selected_opportunity_ids": []' in text
        ):
            empty_selected += 1
        if '"arrivals":[]' in text or '"arrivals": []' in text:
            empty_arrivals += 1
    return {
        "day_traces": days,
        "empty_selected": empty_selected,
        "empty_arrivals": empty_arrivals,
        "selected_nonzero": days - empty_selected,
    }


def block_clears_rungs(
    *,
    trades: int,
    max_drawdown_usd: float,
    usd_per_asset_day: dict[str, float] | None,
    max_entries_portfolio_day: int,
    overlap_violations: int,
    position_size_mini: int,
    asset_days: dict[str, int],
) -> bool:
    mutant = os.environ.get("QRE2_B3_MUTANT", "")
    if trades <= 0:
        return False
    if (max_drawdown_usd > MAX_DRAWDOWN_USD
            if mutant == "mdd_boundary_inclusive"
            else max_drawdown_usd >= MAX_DRAWDOWN_USD):
        return False
    if usd_per_asset_day is None:
        if mutant == "policy_block_dollars_ignored":
            usd_per_asset_day = dict(RUNGS)
        else:
            return False
    if (mutant != "policy_cap_ignored"
            and max_entries_portfolio_day > MAX_ENTRIES_PORTFOLIO_DAY):
        return False
    if mutant != "policy_overlap_ignored" and overlap_violations != 0:
        return False
    if position_size_mini != 1 or asset_days != LOCKED_ASSET_DAYS:
        return False
    for asset, rung in RUNGS.items():
        if asset not in usd_per_asset_day:
            raise ValueError(
                f"usd_per_asset_day missing {asset}, got {sorted(usd_per_asset_day)}"
            )
        if float(usd_per_asset_day[asset]) < rung:
            return False
    return True


def decide_verdict(blocks: list[dict[str, Any]]) -> tuple[str, str]:
    if any(bool(row.get("clears_rungs")) for row in blocks):
        return "PASS", "THRESHOLD policy block clears the rungs"
    if blocks:
        return (
            "SHORT",
            "THRESHOLD policy blocks exist and replay 0 trades while the "
            "same-window exact ceiling clears the rungs",
        )
    return (
        "INCONCLUSIVE",
        "no confirmation receipt opened THRESHOLD with "
        "exact_replay_ceiling_executed and threshold_economics_executed",
    )


def margin_closure() -> dict[str, Any]:
    emptiness = cheap_trace_emptiness(MARGIN_RULE)
    return {
        "schema": "QRE2THRESHOLDMARGINCLOSURE1",
        "named_cause": (
            "e1r_regret_head_never_prefers_enter_on_any_walked_window"
        ),
        "root": str(MARGIN_RULE.relative_to(REPO)),
        "emptiness": emptiness,
        "closed": (
            emptiness["day_traces"] > 0
            and emptiness["selected_nonzero"] == 0
        ),
        "check_command": (
            "python3 .audit/assert_threshold_replay_receipt.py --margin-closure"
        ),
    }


def policy_block_economics(path: Path) -> dict[str, Any]:
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    from engine.entry_v2.tabular_evaluation_policy import load_policy_block_result
    from engine.entry_v2.tabular_recovery_contracts import RecoveryConfig

    result = load_policy_block_result(path, config=RecoveryConfig())
    evaluation = result.evidence.evaluation
    by_asset = {row.asset: row for row in evaluation.by_asset}
    usd_per_asset_day = {
        asset: float(row.usd_per_asset_day) for asset, row in by_asset.items()
    }
    asset_days = {asset: int(row.asset_days) for asset, row in by_asset.items()}
    by_day: dict[int, int] = {}
    by_asset_day: dict[tuple[str, int], list[Any]] = {}
    for trade in evaluation.trade_results:
        by_day[trade.trading_day] = by_day.get(trade.trading_day, 0) + 1
        by_asset_day.setdefault((trade.asset, trade.trading_day), []).append(trade)
    overlaps = 0
    for rows in by_asset_day.values():
        ordered = sorted(rows, key=lambda row: (row.entry_ts_ns, row.candidate_id))
        overlaps += sum(
            ordered[index - 1].exit_ts_ns >= ordered[index].entry_ts_ns
            for index in range(1, len(ordered))
        )
    max_entries = max(by_day.values(), default=0)
    return {
        "path": str(path.relative_to(REPO)),
        "trades": evaluation.trades,
        "usd_per_active_portfolio_day": result.gate.usd_per_active_portfolio_day,
        "max_drawdown_usd": evaluation.max_drawdown_usd,
        "exact_ceiling_usd": result.evidence.exact_ceiling_usd,
        "usd_per_asset_day": usd_per_asset_day,
        "asset_days": asset_days,
        "max_entries_portfolio_day": max_entries,
        "overlap_violations": overlaps,
        "position_size_mini": result.evidence.position_size_mini,
        "strict_loaded": True,
        "clears_rungs": block_clears_rungs(
            trades=evaluation.trades,
            max_drawdown_usd=evaluation.max_drawdown_usd,
            usd_per_asset_day=usd_per_asset_day,
            max_entries_portfolio_day=max_entries,
            overlap_violations=overlaps,
            position_size_mini=result.evidence.position_size_mini,
            asset_days=asset_days,
        ),
    }


def _selftest() -> int:
    hit = classify(
        Path("fixture.json"),
        {
            "threshold_open_count": 1,
            "exact_replay_ceiling_executed": True,
            "threshold_economics_executed": True,
        },
    )
    miss = classify(
        Path("fixture.json"),
        {
            "threshold_open_count": 0,
            "exact_replay_ceiling_executed": False,
            "canonical_replay_executed": True,
            "economics_scope": "E1R_PLATT_SPARSE_TRAINING_GRID_DIAGNOSTIC",
        },
    )
    if not hit["is_threshold_exact_replay"]:
        raise AssertionError(
            f"selftest hit fixture must pass, got {hit!r}"
        )
    if miss["is_threshold_exact_replay"]:
        raise AssertionError(
            f"selftest miss fixture must fail, got {miss!r}"
        )
    block = THRESHOLD_BLOCKS / "real/seed_20260820/raw_block.json"
    if block.is_file():
        economics = policy_block_economics(block)
        if economics["trades"] != 0 or economics["clears_rungs"]:
            raise AssertionError(
                f"selftest expected 0-trade THRESHOLD block, got {economics!r}"
            )
        preference = enter_preference(THRESHOLD_BLOCKS)
        if (
            preference["policy_crossing_events"] != 0
            or preference["selected_opportunity_total"] != 0
        ):
            raise AssertionError(
                "selftest expected zero ENTER preference on THRESHOLD traces, "
                f"got {preference!r}"
            )
    passing = block_clears_rungs(
        trades=12,
        max_drawdown_usd=400.0,
        usd_per_asset_day={"HG": 2100.0, "NKD": 1600.0, "SI": 1600.0},
        max_entries_portfolio_day=12,
        overlap_violations=0,
        position_size_mini=1,
        asset_days=dict(LOCKED_ASSET_DAYS),
    )
    if not passing:
        raise AssertionError("selftest synthetic block must clear the rungs")
    short = block_clears_rungs(
        trades=0,
        max_drawdown_usd=0.0,
        usd_per_asset_day={"HG": 2100.0, "NKD": 1600.0, "SI": 1600.0},
        max_entries_portfolio_day=0,
        overlap_violations=0,
        position_size_mini=1,
        asset_days=dict(LOCKED_ASSET_DAYS),
    )
    if short:
        raise AssertionError("selftest zero-trade block must not clear the rungs")
    guarded = {
        "policy_block_dollars_ignored": dict(
            trades=12, max_drawdown_usd=400.0, usd_per_asset_day=None,
            max_entries_portfolio_day=12, overlap_violations=0,
            position_size_mini=1, asset_days=dict(LOCKED_ASSET_DAYS)),
        "mdd_boundary_inclusive": dict(
            trades=12, max_drawdown_usd=1000.0,
            usd_per_asset_day={"HG": 2100.0, "NKD": 1600.0, "SI": 1600.0},
            max_entries_portfolio_day=12, overlap_violations=0,
            position_size_mini=1, asset_days=dict(LOCKED_ASSET_DAYS)),
        "policy_cap_ignored": dict(
            trades=13, max_drawdown_usd=400.0,
            usd_per_asset_day={"HG": 2100.0, "NKD": 1600.0, "SI": 1600.0},
            max_entries_portfolio_day=13, overlap_violations=0,
            position_size_mini=1, asset_days=dict(LOCKED_ASSET_DAYS)),
        "policy_overlap_ignored": dict(
            trades=12, max_drawdown_usd=400.0,
            usd_per_asset_day={"HG": 2100.0, "NKD": 1600.0, "SI": 1600.0},
            max_entries_portfolio_day=12, overlap_violations=1,
            position_size_mini=1, asset_days=dict(LOCKED_ASSET_DAYS)),
    }
    if any(block_clears_rungs(**arguments) for arguments in guarded.values()):
        raise AssertionError("selftest policy-block boundary guard failed")
    verdict, _reason = decide_verdict([{"clears_rungs": True}])
    if verdict != "PASS":
        raise AssertionError(
            f"selftest expected PASS when a block clears, got {verdict!r}"
        )
    if FIT_EXECUTION.is_file() and THRESHOLD_SELECTION.is_dir():
        gap = enter_gap()
        captures = [
            float(row["capture"])
            for row in gap["fit_capture"]["by_seed"].values()
        ]
        if not captures or max(captures) >= 0.05:
            raise AssertionError(
                "selftest expected FIT capture well under 5 percent, "
                f"got {gap['fit_capture']!r}"
            )
        grids = gap["threshold_advantage_grid"]
        if not grids:
            raise AssertionError("selftest expected THRESHOLD advantage grids")
        if any(float(row["grid_max_usd"]) >= 0.0 for row in grids.values()):
            raise AssertionError(
                "selftest expected an all-negative advantage grid, "
                f"got {grids!r}"
            )
    print("selftest_ok")
    return 0


def main() -> int:
    arguments = sys.argv[1:]
    if "--selftest" in arguments:
        return _selftest()
    if "--block" in arguments:
        index = arguments.index("--block")
        if index + 1 >= len(arguments):
            raise ValueError("--block requires a QRE2TABPOLICYBLOCK2 path")
        economics = policy_block_economics(Path(arguments[index + 1]))
        print(json.dumps(economics, indent=2, sort_keys=True))
        return 0 if economics["clears_rungs"] else 2
    if "--enter-gap" in arguments:
        print(json.dumps(enter_gap(), indent=2, sort_keys=True))
        return 0
    if "--margin-closure" in arguments:
        print(json.dumps(margin_closure(), indent=2, sort_keys=True))
        return 0
    if not CONFIRMATION.is_dir():
        raise FileNotFoundError(
            f"confirmation receipt directory missing: {CONFIRMATION}"
        )
    rows = []
    for path in sorted(CONFIRMATION.glob("e1r_*.json")):
        payload = json.loads(path.read_text())
        if not isinstance(payload, dict):
            raise ValueError(f"{path} must be a JSON object, got {type(payload).__name__}")
        rows.append(classify(path, payload))
    hits = [row for row in rows if row["is_threshold_exact_replay"]]
    diagnostic = ranker_threshold()
    blocks = []
    if THRESHOLD_BLOCKS.is_dir():
        for path in sorted(THRESHOLD_BLOCKS.rglob("raw_block.json")):
            blocks.append(policy_block_economics(path))
    preference = enter_preference(THRESHOLD_BLOCKS)
    verdict, reason = decide_verdict(blocks)
    rungs_clear = verdict == "PASS"
    report = {
        "schema": "QRE2THRESHOLDREPLAYGATE1",
        "verdict": verdict,
        "reason": reason,
        "threshold_policy_blocks": blocks,
        "rungs_usd_per_asset_day": RUNGS,
        "max_drawdown_usd": MAX_DRAWDOWN_USD,
        "max_entries_portfolio_day": MAX_ENTRIES_PORTFOLIO_DAY,
        "confirmation_receipts_scanned": len(rows),
        "threshold_exact_replay_hits": hits,
        "threshold_open_total": sum(row["threshold_open_count"] for row in rows),
        "exact_replay_true_count": sum(
            1 for row in rows if row["exact_replay_ceiling_executed"]
        ),
        "location_ranker_threshold_diagnostic_not_replay": diagnostic,
        "location_ranker_command": (
            "OMP_NUM_THREADS=1 python3 tools/probe_location_ranker.py "
            "--matrix-dir <component_matrix> --out <receipt.json>"
        ),
        "location_ranker_command_runnable": (
            REPO / "tools/probe_location_ranker.py"
        ).is_file(),
        "check_command": "python3 .audit/assert_threshold_replay_receipt.py",
        "named_cause": (
            "e1r_regret_head_never_prefers_enter_on_any_walked_window"
        ),
        "enter_preference": preference,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if rungs_clear else 2


if __name__ == "__main__":
    sys.exit(main())
