#!/usr/bin/env python3
"""Run the bounded capacity-aligned confirmation objective comparison."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from entry_v2 import common as C
from entry_v2.confirmation import ConfirmationConfig
from entry_v2.confirmation_capacity_probe import (
    CapacityProbeConfig, run_capacity_probe,
)
from entry_v2.confirmation_experiment import (
    canonical_stage_specs, combine_feature_role, materialize_feature_cache,
)
from entry_v2.confirmation_stopping import OracleActionLedger
from entry_v2.diagnostic_inputs import fit_only_rehearsal_windows


DEFAULT_EXCLUSIONS = (
    "phase_remaining_sec",
    "disc_fvol_session_age_now_sec",
    "disc_fvol_session_scope_elapsed_sec",
    "disc_fvol_session_scope_remaining_sec",
    "disc_fvol_phase_age_now_sec",
    "disc_fvol_phase_scope_elapsed_sec",
    "disc_fvol_phase_scope_remaining_sec",
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-root", type=Path,
        default=Path("/workspace/artifacts/cache/port/entry_v2"))
    parser.add_argument(
        "--cache-root", type=Path,
        default=Path("/workspace/artifacts/cache/entry_v2_confirmation_v9"))
    parser.add_argument(
        "--ledger-root", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/e1r_action_audit"))
    parser.add_argument(
        "--output", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_capacity_probe_v1.json"))
    parser.add_argument("--stage", default="E1r")
    parser.add_argument("--watch-age-sec", type=int, default=30)
    parser.add_argument("--capacity", type=int, default=4)
    parser.add_argument("--iterations", type=int, default=80)
    parser.add_argument("--depth", type=int, default=5)
    parser.add_argument("--thread-count", type=int, default=16)
    parser.add_argument("--feature-set", default="MAX_W300")
    parser.add_argument(
        "--exclude-feature", action="append", default=None,
        help="Override the registered seven-clock destruction roster.")
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    roles = ("FIT", "PLATT", "THRESHOLD")
    windows = fit_only_rehearsal_windows(args.stage)
    specs = dict(canonical_stage_specs(
        args.stage, args.source_root, roles=roles))
    feature_config = ConfirmationConfig(
        max_delay_sec=300, snapshot_mode="TRAINING")
    corpora = {}
    ledgers = {}
    for role in roles:
        records = materialize_feature_cache(
            specs[role], feature_config, args.cache_root, workers=1)
        corpora[role] = combine_feature_role(
            role, windows[role], records)
        ledgers[role] = OracleActionLedger.load(
            args.ledger_root / f"{role.lower()}_action_ledger.npz")

    def progress(row: dict[str, object]) -> None:
        print(json.dumps(
            {"event": "CAPACITY_PROBE_PROGRESS", **row},
            sort_keys=True), file=sys.stderr, flush=True)

    exclusions = (DEFAULT_EXCLUSIONS if args.exclude_feature is None
                  else tuple(args.exclude_feature))
    result = run_capacity_probe(
        {role: corpora[role].dataset for role in roles}, ledgers,
        config=CapacityProbeConfig(
            watch_age_sec=args.watch_age_sec, capacity=args.capacity,
            feature_set=args.feature_set,
            excluded_feature_names=exclusions,
            iterations=args.iterations, depth=args.depth,
            thread_count=args.thread_count),
        progress=progress)
    core = {
        "schema": "QRE2CONFCAPACITYAUDIT1",
        "stage": args.stage.upper(),
        "role_receipts": {
            role: corpora[role].receipt_sha256 for role in roles},
        "probe": result,
        "tool_sha256": C.file_sha256(Path(__file__)),
        "economics_executed": False,
        "forward_open_count": 0,
        "h2_open_count": 0,
    }
    artifact = {**core, "receipt_sha256": C.object_sha256(core)}
    C.atomic_json(args.output, artifact)
    selected = next(row for row in result["family_results"]
                    if row["family"] == result["selected_family"])
    print(json.dumps({
        "receipt_sha256": artifact["receipt_sha256"],
        "probe_receipt_sha256": result["receipt_sha256"],
        "selected_family": result["selected_family"],
        "families": [{
            "family": row["family"],
            "tree_counts": row["tree_counts"],
            "platt": row["diagnostics"]["PLATT"]["overall"],
            "threshold": row["diagnostics"]["THRESHOLD"]["overall"],
        } for row in result["family_results"]],
        "selected_threshold": selected["diagnostics"]["THRESHOLD"]["overall"],
        "selected_threshold_control": result["selected_negative_control"]
            ["threshold_diagnostic"]["overall"],
        "economics_executed": False,
        "h2_open_count": 0,
    }, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({
            "event": "CAPACITY_PROBE_REFUSED",
            "type": type(exc).__name__, "reason": str(exc),
        }, sort_keys=True), file=sys.stderr, flush=True)
        raise
