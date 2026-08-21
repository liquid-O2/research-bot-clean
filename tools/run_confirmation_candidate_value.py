#!/usr/bin/env python3
"""Run robust formation-time CatBoost candidate-value score families."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from entry_v2 import common as C
from entry_v2.confirmation import ConfirmationConfig
from entry_v2.confirmation_candidate_value import (
    CandidateValueConfig, run_candidate_value_probe,
)
from entry_v2.confirmation_experiment import (
    canonical_stage_specs, materialize_feature_cache,
)
from entry_v2.confirmation_stopping import (
    OracleActionLedger, rebind_oracle_action_ledger,
)
from run_confirmation_candidate_rank import _ordered_roles


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-root", type=Path,
        default=Path("/workspace/artifacts/cache/port/entry_v2"))
    parser.add_argument(
        "--base-cache-root", type=Path,
        default=Path("/workspace/artifacts/cache/entry_v2_confirmation_v1"))
    parser.add_argument(
        "--ordered-cache-root", type=Path,
        default=Path("/workspace/artifacts/cache/entry_v2_confirmation_ordered_v1"))
    parser.add_argument(
        "--ledger-root", type=Path,
        default=Path("/workspace/artifacts/entry_v2/confirmation/action_audit_v1"))
    parser.add_argument(
        "--output", type=Path,
        default=Path("/workspace/artifacts/entry_v2/confirmation/"
                     "candidate_value_probe_v1.json"))
    parser.add_argument("--stage", default="E1r")
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--depth", type=int, default=5)
    parser.add_argument("--thread-count", type=int, default=16)
    parser.add_argument("--control-seed", type=int, default=20260819)
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    roles = ("FIT", "PLATT", "THRESHOLD")
    specs = dict(canonical_stage_specs(args.stage, args.source_root, roles=roles))
    base_config = ConfirmationConfig(max_delay_sec=300, snapshot_mode="TRAINING")
    records = {role: materialize_feature_cache(
        specs[role], base_config, args.base_cache_root, workers=1)
        for role in roles}
    source_ledgers = {role: OracleActionLedger.load(
        args.ledger_root / f"{role.lower()}_action_ledger.npz") for role in roles}
    datasets = _ordered_roles(
        specs=specs, records=records,
        ordered_cache_root=args.ordered_cache_root,
        control_seed=args.control_seed)
    ledgers = {role: rebind_oracle_action_ledger(
        source_ledgers[role], datasets[role]) for role in roles}

    def progress(row: dict[str, object]) -> None:
        print(json.dumps({"event": "CANDIDATE_VALUE_PROGRESS", **row},
                         sort_keys=True), file=sys.stderr, flush=True)

    result = run_candidate_value_probe(
        datasets, ledgers,
        config=CandidateValueConfig(
            iterations=args.iterations, depth=args.depth,
            thread_count=args.thread_count),
        progress=progress)
    cache_audit = json.loads(
        (args.ordered_cache_root / "audit_report.json").read_text())
    core = {
        "schema": "QRE2CONFCANDVALUEAUDIT1", "stage": args.stage.upper(),
        "ordered_cache_audit_receipt": cache_audit["receipt_sha256"],
        "probe": result, "economics_executed": False,
        "forward_open_count": 0, "h2_open_count": 0,
    }
    artifact = {**core, "receipt_sha256": C.object_sha256(core)}
    C.atomic_json(args.output, artifact)
    print(json.dumps({
        "receipt_sha256": artifact["receipt_sha256"],
        "selected_family": result["selected_family"],
        "families": [{
            "family": row["family"],
            "trees": row["tree_counts"],
            "platt_capture": row["diagnostics"]["PLATT"]["overall"]
                ["top_capacity_opportunity_capture"],
            "threshold_capture": row["diagnostics"]["THRESHOLD"]["overall"]
                ["top_capacity_opportunity_capture"],
        } for row in result["family_results"]],
        "selected_threshold": result["selected_threshold_diagnostic"]["overall"],
        "selected_control_threshold": result["selected_negative_control"]
            ["threshold_diagnostic"]["overall"],
        "economics_executed": False,
        "forward_open_count": 0, "h2_open_count": 0,
    }, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({
            "event": "CANDIDATE_VALUE_REFUSED", "type": type(exc).__name__,
            "reason": str(exc),
        }, sort_keys=True), file=sys.stderr, flush=True)
        raise
