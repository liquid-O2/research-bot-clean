#!/usr/bin/env python3
"""Run bounded dollar-value and within-candidate ranking probes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from entry_v2 import common as C
from entry_v2.confirmation import ConfirmationConfig
from entry_v2.confirmation_experiment import (
    canonical_stage_specs, combine_feature_role, materialize_feature_cache,
)
from entry_v2.confirmation_stopping import OracleActionLedger
from entry_v2.confirmation_value_probe import (
    ValueProbeConfig, run_value_probe_matrix,
)
from entry_v2.diagnostic_inputs import fit_only_rehearsal_windows


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-root", type=Path,
        default=Path("/workspace/artifacts/cache/port/entry_v2"))
    parser.add_argument(
        "--cache-root", type=Path,
        default=Path("/workspace/artifacts/cache/entry_v2_confirmation_v1"))
    parser.add_argument(
        "--ledger-root", type=Path,
        default=Path("/workspace/artifacts/entry_v2/confirmation/action_audit_v1"))
    parser.add_argument(
        "--output", type=Path,
        default=Path("/workspace/artifacts/entry_v2/confirmation/value_probes_v1.json"))
    parser.add_argument("--iterations", type=int, default=60)
    parser.add_argument("--depth", type=int, default=5)
    parser.add_argument("--thread-count", type=int, default=16)
    parser.add_argument(
        "--feature-sets", nargs="+", default=("PLUS_RECLAIM", "MAX_W300"))
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    roles = ("FIT", "PLATT", "THRESHOLD")
    windows = fit_only_rehearsal_windows("E1r")
    specs = canonical_stage_specs("E1r", args.source_root, roles=roles)
    feature_config = ConfirmationConfig(max_delay_sec=300, snapshot_mode="TRAINING")
    corpora = {}; ledgers = {}
    for role in roles:
        records = materialize_feature_cache(
            specs[role], feature_config, args.cache_root, workers=1)
        corpora[role] = combine_feature_role(role, windows[role], records)
        ledgers[role] = OracleActionLedger.load(
            args.ledger_root / f"{role.lower()}_action_ledger.npz")

    def progress(row: dict[str, object]) -> None:
        print(json.dumps({"event": "VALUE_PROBE_PROGRESS", **row},
                         sort_keys=True), file=sys.stderr, flush=True)

    result = run_value_probe_matrix(
        {role: corpora[role].dataset for role in roles}, ledgers,
        feature_sets=args.feature_sets,
        config=ValueProbeConfig(
            iterations=args.iterations, depth=args.depth,
            thread_count=args.thread_count),
        progress=progress)
    C.atomic_json(args.output, result)
    concise = {
        "receipt_sha256": result["receipt_sha256"],
        "results": [{
            "feature_set": row["feature_set"],
            "control": row.get("control"),
            "threshold": (
                row["threshold_diagnostic"] if "control" in row else {
                    "opportunity_q_optimal_correlation":
                        row["diagnostics"]["THRESHOLD"]
                        ["opportunity_q_optimal_correlation"],
                    "advantage_correlation":
                        row["diagnostics"]["THRESHOLD"]["advantage_correlation"],
                    "selected_opportunity_monotone_steps":
                        row["diagnostics"]["THRESHOLD"]
                        ["selected_opportunity_monotone_steps"],
                    "timing": row["diagnostics"]["THRESHOLD"]["timing"],
                }),
        } for row in result["results"]],
    }
    print(json.dumps(concise, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({
            "event": "VALUE_PROBE_REFUSED", "type": type(exc).__name__,
            "reason": str(exc),
        }, sort_keys=True), file=sys.stderr, flush=True)
        raise
