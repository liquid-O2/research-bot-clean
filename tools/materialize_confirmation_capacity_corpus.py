#!/usr/bin/env python3
"""Publish a strict, compact fixed-watch confirmation corpus."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from entry_v2 import common as C
from entry_v2.confirmation import ConfirmationConfig, ConfirmationDataset
from entry_v2.confirmation_capacity_corpus import (
    ROLES, CapacityCorpusConfig, prepare_capacity_corpora,
)
from entry_v2.confirmation_experiment import (
    canonical_stage_specs, combine_feature_role, materialize_feature_cache,
)
from entry_v2.confirmation_stopping import OracleActionLedger
from entry_v2.diagnostic_inputs import fit_only_rehearsal_windows
from run_confirmation_capacity_probe import DEFAULT_EXCLUSIONS


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
        "--output-dir", type=Path,
        default=Path(
            "/workspace/artifacts/cache/entry_v2_capacity_30s_v1"))
    parser.add_argument("--stage", default="E1r")
    parser.add_argument("--watch-age-sec", type=int, default=30)
    parser.add_argument("--capacity", type=int, default=4)
    parser.add_argument("--feature-set", default="MAX_W300")
    parser.add_argument(
        "--exclude-feature", action="append", default=None,
        help="Override the registered seven-clock destruction roster.")
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    target = C.assert_workspace_output(args.output_dir)
    if target.exists():
        raise FileExistsError(f"capacity corpus already exists: {target}")
    windows = fit_only_rehearsal_windows(args.stage)
    specs = dict(canonical_stage_specs(
        args.stage, args.source_root, roles=ROLES))
    feature_config = ConfirmationConfig(
        max_delay_sec=300, snapshot_mode="TRAINING")
    corpora = {}
    ledgers = {}
    for role in ROLES:
        records = materialize_feature_cache(
            specs[role], feature_config, args.cache_root, workers=1)
        corpora[role] = combine_feature_role(role, windows[role], records)
        ledgers[role] = OracleActionLedger.load(
            args.ledger_root / f"{role.lower()}_action_ledger.npz")
    exclusions = (DEFAULT_EXCLUSIONS if args.exclude_feature is None
                  else tuple(args.exclude_feature))
    datasets, reduced_ledgers, preparation = prepare_capacity_corpora(
        {role: corpora[role].dataset for role in ROLES}, ledgers,
        config=CapacityCorpusConfig(
            watch_age_sec=args.watch_age_sec, capacity=args.capacity,
            feature_set=args.feature_set,
            excluded_feature_names=exclusions))

    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(
        prefix=f".{target.name}.tmp.", dir=target.parent))
    try:
        files = {}
        for role in ROLES:
            dataset_path = staging / f"{role.lower()}_dataset.npz"
            ledger_path = staging / f"{role.lower()}_ledger.npz"
            dataset_file = datasets[role].save(dataset_path)
            ledger_file = reduced_ledgers[role].save(ledger_path)
            loaded_dataset = ConfirmationDataset.load(dataset_path)
            loaded_ledger = OracleActionLedger.load(ledger_path)
            if (loaded_dataset.representation_sha256
                    != datasets[role].representation_sha256
                    or loaded_ledger.representation_sha256
                    != reduced_ledgers[role].representation_sha256
                    or loaded_ledger.source_representation_sha256
                    != loaded_dataset.representation_sha256):
                raise ValueError("capacity corpus strict reload differs")
            files[role] = {
                "dataset": dataset_path.name,
                "dataset_file_sha256": dataset_file,
                "ledger": ledger_path.name,
                "ledger_file_sha256": ledger_file,
            }
        core = {
            "schema": "QRE2CONFCAPACITYCORPUSAUDIT1",
            "stage": args.stage.upper(),
            "preparation": preparation,
            "role_receipts": {
                role: corpora[role].receipt_sha256 for role in ROLES},
            "files": files,
            "tool_sha256": C.file_sha256(Path(__file__)),
            "strict_reload": True,
            "economics_executed": False,
            "forward_open_count": 0,
            "h2_open_count": 0,
        }
        manifest = {**core, "receipt_sha256": C.object_sha256(core)}
        C.atomic_json(staging / "manifest.json", manifest)
        os.replace(staging, target)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    print(json.dumps({
        "receipt_sha256": manifest["receipt_sha256"],
        "preparation_receipt_sha256": preparation["receipt_sha256"],
        "roles": preparation["roles"],
        "path_selector": preparation["path_selector"],
        "fixed_watch_selector": preparation["fixed_watch_selector"],
        "strict_reload": True,
        "economics_executed": False,
        "h2_open_count": 0,
    }, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({
            "event": "CAPACITY_CORPUS_REFUSED",
            "type": type(exc).__name__, "reason": str(exc),
        }, sort_keys=True), file=sys.stderr, flush=True)
        raise
