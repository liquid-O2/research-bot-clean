#!/usr/bin/env python3
"""Build durable real-data ENTER/WAIT/PASS label ledgers without fitting."""

from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path
import sys

from entry_v2 import common as C
from entry_v2.confirmation import ConfirmationConfig
from entry_v2.confirmation_experiment import (
    canonical_stage_specs, combine_feature_role, materialize_feature_cache,
)
from entry_v2.confirmation_stopping import (
    derive_oracle_action_ledger, oracle_action_census,
)
from entry_v2.diagnostic_inputs import fit_only_rehearsal_windows


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", default="E1r", choices=("E1r", "E2r"))
    parser.add_argument(
        "--roles", nargs="+", default=("FIT", "PLATT", "THRESHOLD"),
        choices=("FIT", "PLATT", "THRESHOLD"))
    parser.add_argument(
        "--source-root", type=Path,
        default=Path("/workspace/artifacts/cache/port/entry_v2"))
    parser.add_argument(
        "--cache-root", type=Path,
        default=Path("/workspace/artifacts/cache/entry_v2_confirmation_v1"))
    parser.add_argument(
        "--output", type=Path,
        default=Path("/workspace/artifacts/entry_v2/confirmation/action_audit_v1"))
    parser.add_argument("--workers", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    roles = tuple(str(value).upper() for value in args.roles)
    specs = canonical_stage_specs(args.stage, args.source_root, roles=roles)
    windows = fit_only_rehearsal_windows(args.stage)
    config = ConfirmationConfig(max_delay_sec=300, snapshot_mode="TRAINING")
    output = C.assert_workspace_output(args.output)
    output.mkdir(parents=True, exist_ok=True)
    reports = {}
    for role in roles:
        records = materialize_feature_cache(
            specs[role], config, args.cache_root, workers=args.workers)
        corpus = combine_feature_role(role, windows[role], records)
        ledger = derive_oracle_action_ledger(corpus.dataset)
        ledger_path = output / f"{role.lower()}_action_ledger.npz"
        ledger_file_sha256 = ledger.save(ledger_path)
        census = dict(oracle_action_census(corpus.dataset, ledger))
        report = {
            "role": role, "window": windows[role],
            "role_receipt_sha256": corpus.receipt_sha256,
            "expected_sessions": len(corpus.expected_sessions),
            "empty_sessions": len(corpus.empty_sessions),
            "ledger_path": str(ledger_path),
            "ledger_file_sha256": ledger_file_sha256,
            **census,
        }
        C.atomic_json(output / f"{role.lower()}_action_census.json", report)
        reports[role] = report
        print(json.dumps({
            "event": "ACTION_LEDGER_READY", "role": role,
            "rows": report["overall"]["rows"],
            "series": report["overall"]["series"],
            "actions": report["overall"]["action_row_count"],
            "goal_rate": report["overall"]["goal_label_series_balanced_rate"],
            "goal_but_not_enter_rate":
                report["overall"]["goal_but_not_enter_series_balanced_rate"],
            "receipt_sha256": report["receipt_sha256"],
        }, sort_keys=True), flush=True)
        del corpus, ledger
        gc.collect()
    core = {
        "schema": "QRE2CONFACTIONAUDIT1", "stage": args.stage,
        "config_sha256": config.receipt_sha256,
        "roles": {role: reports[role]["receipt_sha256"] for role in roles},
        "h2_open_count": 0,
    }
    final = {**core, "receipt_sha256": C.object_sha256(core)}
    C.atomic_json(output / "audit_receipt.json", final)
    print(json.dumps(final, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({
            "event": "ACTION_AUDIT_REFUSED", "type": type(exc).__name__,
            "reason": str(exc),
        }, sort_keys=True), file=sys.stderr, flush=True)
        raise
