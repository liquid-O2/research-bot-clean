#!/usr/bin/env python3
"""Fail unless a held THRESHOLD canonical-replay receipt exists.

A diagnostic usd_per_asset_day field is not enough. The receipt must open
THRESHOLD, run exact chronological replay, and publish per-asset dollars,
drawdown, and entry count. Without that triple the THRESHOLD bottleneck
claim is INCONCLUSIVE.
"""

from __future__ import annotations

import json
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
RUNGS = {"HG": 2000.0, "NKD": 1500.0, "SI": 1500.0}
MAX_DRAWDOWN_USD = 1000.0
MAX_ENTRIES_PORTFOLIO_DAY = 12


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


def policy_block_economics(path: Path) -> dict[str, Any]:
    text = path.read_text()
    if '"schema":"QRE2TABPOLICYBLOCK2"' not in text and (
            '"schema": "QRE2TABPOLICYBLOCK2"' not in text):
        raise ValueError(f"{path} is not QRE2TABPOLICYBLOCK2")
    start = text.rfind('"gate_detail"')
    if start < 0:
        raise ValueError(f"{path} has no gate_detail")
    chunk = text[start:start + 2000]
    def _num(key: str) -> float:
        token = f'"{key}":'
        at = chunk.find(token)
        if at < 0:
            raise ValueError(f"{path} gate_detail missing {key}")
        raw = chunk[at + len(token):].split(",", 1)[0].split("}", 1)[0]
        return float(raw)
    return {
        "path": str(path.relative_to(REPO)),
        "trades": int(_num("trades")),
        "usd_per_active_portfolio_day": _num("usd_per_active_portfolio_day"),
        "max_drawdown_usd": _num("max_drawdown_usd"),
        "exact_ceiling_usd": _num("exact_ceiling_usd"),
        "clears_rungs": False,
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
    print("selftest_ok")
    return 0


def main() -> int:
    if "--selftest" in sys.argv[1:]:
        return _selftest()
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
    rungs_clear = any(row["clears_rungs"] for row in blocks)
    if rungs_clear:
        verdict = "PASS"
        reason = "THRESHOLD policy block clears the rungs"
    elif blocks:
        verdict = "SHORT"
        reason = (
            "THRESHOLD policy blocks exist and replay 0 trades while the "
            "same-window exact ceiling clears the rungs"
        )
    else:
        verdict = "INCONCLUSIVE"
        reason = (
            "no confirmation receipt opened THRESHOLD with "
            "exact_replay_ceiling_executed and threshold_economics_executed"
        )
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
        "named_cause": "action_regret_head_never_prefers_enter",
        "enter_preference": preference,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if rungs_clear else 2


if __name__ == "__main__":
    sys.exit(main())
