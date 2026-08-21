#!/usr/bin/env python3
"""Run independent within-asset CatBoost rankers at fixed watch ages."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from entry_v2 import common as C
from entry_v2.confirmation import ConfirmationConfig
from entry_v2.confirmation_candidate_rank import (
    CURRENT_TARGET_SCOPE, TARGET_SCOPES,
    CandidateRankConfig, run_candidate_age_rank_probe,
)
from entry_v2.confirmation_experiment import (
    canonical_stage_specs, combine_feature_role, materialize_feature_cache,
)
from entry_v2.confirmation_stopping import (
    OracleActionLedger, rebind_oracle_action_ledger,
)
from run_confirmation_candidate_rank import _ordered_roles
from entry_v2.diagnostic_inputs import fit_only_rehearsal_windows


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
        default=Path("/workspace/artifacts/entry_v2/confirmation/candidate_age_rank_probe_v1.json"))
    parser.add_argument("--stage", default="E1r")
    parser.add_argument("--iterations", type=int, default=80)
    parser.add_argument("--depth", type=int, default=5)
    parser.add_argument("--thread-count", type=int, default=16)
    parser.add_argument("--control-seed", type=int, default=20260819)
    parser.add_argument(
        "--feature-source", choices=("BASE", "ORDERED"), default="BASE")
    parser.add_argument("--feature-set", default="MAX_W300")
    parser.add_argument(
        "--target-scope", choices=TARGET_SCOPES,
        default=CURRENT_TARGET_SCOPE)
    parser.add_argument(
        "--exclude-feature", action="append", default=[],
        help="Remove a named feature from the registered feature set.")
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    roles = ("FIT", "PLATT", "THRESHOLD")
    specs = dict(canonical_stage_specs(args.stage, args.source_root, roles=roles))
    config = ConfirmationConfig(max_delay_sec=300, snapshot_mode="TRAINING")
    records = {role: materialize_feature_cache(
        specs[role], config, args.base_cache_root, workers=1) for role in roles}
    source_ledgers = {role: OracleActionLedger.load(
        args.ledger_root / f"{role.lower()}_action_ledger.npz") for role in roles}
    role_receipts = {}
    ordered_cache_audit_receipt = None
    if args.feature_source == "BASE":
        windows = fit_only_rehearsal_windows(args.stage)
        corpora = {role: combine_feature_role(
            role, windows[role], records[role]) for role in roles}
        datasets = {role: corpora[role].dataset for role in roles}
        ledgers = source_ledgers
        role_receipts = {
            role: corpora[role].receipt_sha256 for role in roles}
    else:
        datasets = _ordered_roles(
            specs=specs, records=records,
            ordered_cache_root=args.ordered_cache_root,
            control_seed=args.control_seed)
        ledgers = {role: rebind_oracle_action_ledger(
            source_ledgers[role], datasets[role]) for role in roles}
        cache_audit = json.loads(
            (args.ordered_cache_root / "audit_report.json").read_text())
        ordered_cache_audit_receipt = cache_audit["receipt_sha256"]

    def progress(row: dict[str, object]) -> None:
        print(json.dumps({"event": "CANDIDATE_AGE_RANK_PROGRESS", **row},
                         sort_keys=True), file=sys.stderr, flush=True)

    result = run_candidate_age_rank_probe(
        datasets, ledgers,
        config=CandidateRankConfig(
            capacity=4, iterations=args.iterations, depth=args.depth,
            thread_count=args.thread_count,
            feature_set=args.feature_set,
            target_scope=args.target_scope,
            excluded_feature_names=tuple(args.exclude_feature)),
        progress=progress)
    core = {
        "schema": "QRE2CONFAGECANDRANKAUDIT6",
        "stage": args.stage.upper(),
        "feature_source": args.feature_source,
        "role_receipts": role_receipts,
        "ordered_cache_audit_receipt": ordered_cache_audit_receipt,
        "probe": result,
        "tool_sha256": C.file_sha256(Path(__file__)),
        "economics_executed": False,
        "forward_open_count": 0,
        "h2_open_count": 0,
    }
    artifact = {**core, "receipt_sha256": C.object_sha256(core)}
    C.atomic_json(args.output, artifact)
    concise = {
        "receipt_sha256": artifact["receipt_sha256"],
        "selected_watch_age_sec": result["selected_watch_age_sec"],
        "ages": [{
            "watch_age_sec": row["watch_age_sec"],
            "tree_count": row["tree_count"],
            "top_features": row["top_feature_importance"][:10],
            "platt": row["diagnostics"]["PLATT"]["overall"],
            "threshold": row["diagnostics"]["THRESHOLD"]["overall"],
            "threshold_control": row["negative_control"]
                ["threshold_diagnostic"]["overall"],
        } for row in result["age_results"]],
        "economics_executed": False,
    }
    print(json.dumps(concise, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({
            "event": "CANDIDATE_AGE_RANK_REFUSED",
            "type": type(exc).__name__,
            "reason": str(exc),
        }, sort_keys=True), file=sys.stderr, flush=True)
        raise
