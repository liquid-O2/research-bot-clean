#!/usr/bin/env python3
"""Publish strict reduced post-watch paths for factorized action learning."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import gc
import json
import os
from pathlib import Path
import tempfile

from catboost import CatBoostClassifier

from entry_v2 import common as C
from entry_v2.confirmation import ConfirmationConfig, ConfirmationDataset
from entry_v2.confirmation_capacity_corpus import ROLES
from entry_v2.confirmation_conditional_corpus import (
    ConditionalCorpusConfig, prepare_conditional_role,
)
from entry_v2.confirmation_experiment import (
    canonical_stage_specs, combine_feature_role, materialize_feature_cache,
)
from entry_v2.confirmation_stopping import OracleActionLedger
from entry_v2.diagnostic_inputs import fit_only_rehearsal_windows


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
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_action_audit"))
    parser.add_argument(
        "--capacity-root", type=Path,
        default=Path("/workspace/artifacts/cache/entry_v2_capacity_30s_v1"))
    parser.add_argument(
        "--rank-model-dir", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_factorized_policy_v1_models"))
    parser.add_argument(
        "--output-dir", type=Path,
        default=Path(
            "/workspace/artifacts/cache/entry_v2_conditional_paths_v1"))
    parser.add_argument("--stage", default="E1r")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--capacity", type=int, default=4)
    parser.add_argument("--all-watchable-series", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    destination = C.assert_workspace_output(args.output_dir)
    if destination.exists():
        raise FileExistsError(f"conditional corpus exists: {destination}")
    capacity_manifest_path = args.capacity_root / "manifest.json"
    capacity_manifest = json.loads(capacity_manifest_path.read_text())
    capacity_core = dict(capacity_manifest)
    capacity_receipt = str(capacity_core.pop("receipt_sha256"))
    if (capacity_manifest.get("schema") != "QRE2CONFCAPACITYCORPUSAUDIT1"
            or C.object_sha256(capacity_core) != capacity_receipt
            or capacity_manifest.get("strict_reload") is not True
            or capacity_manifest.get("h2_open_count") != 0):
        raise ValueError("conditional capacity manifest identity differs")
    fixed = {}; fixed_ledgers = {}
    for role in ROLES:
        files = capacity_manifest["files"][role]
        dataset_path = args.capacity_root / files["dataset"]
        ledger_path = args.capacity_root / files["ledger"]
        if (C.file_sha256(dataset_path) != files["dataset_file_sha256"]
                or C.file_sha256(ledger_path) != files["ledger_file_sha256"]):
            raise ValueError("conditional capacity payload differs")
        fixed[role] = ConfirmationDataset.load(dataset_path)
        fixed_ledgers[role] = OracleActionLedger.load(ledger_path)

    rank_manifest_path = args.rank_model_dir / "manifest.json"
    rank_manifest = json.loads(rank_manifest_path.read_text())
    rank_core = dict(rank_manifest)
    rank_receipt = str(rank_core.pop("receipt_sha256"))
    if (rank_manifest.get("schema") != "QRE2CONFFACTMODELBUNDLE1"
            or C.object_sha256(rank_core) != rank_receipt
            or rank_manifest.get("strict_reload") is not True
            or rank_manifest.get("h2_open_count") != 0):
        raise ValueError("conditional rank bundle identity differs")
    models = {}
    for name in ("rank", "rank_control"):
        path = args.rank_model_dir / rank_manifest["files"][name]["path"]
        if C.file_sha256(path) != rank_manifest["files"][name]["file_sha256"]:
            raise ValueError("conditional rank model payload differs")
        model = CatBoostClassifier(); model.load_model(path)
        models[name] = model

    specs = dict(canonical_stage_specs(
        args.stage, args.source_root, roles=ROLES))
    windows = fit_only_rehearsal_windows(args.stage)
    feature_config = ConfirmationConfig(
        max_delay_sec=300, snapshot_mode="TRAINING")
    config = ConditionalCorpusConfig(
        capacity=args.capacity,
        include_all_watchable_series=args.all_watchable_series)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(
        prefix=f".{destination.name}.tmp.", dir=destination.parent))
    files = {}; role_reports = {}
    try:
        for role in ROLES:
            records = materialize_feature_cache(
                specs[role], feature_config, args.cache_root,
                workers=args.workers)
            corpus = combine_feature_role(role, windows[role], records)
            full = corpus.dataset
            expected_source = capacity_manifest["preparation"]["roles"][role][
                "source_dataset_sha256"]
            if full.representation_sha256 != expected_source:
                raise ValueError("conditional full/capacity source differs")
            full_ledger = OracleActionLedger.load(
                args.ledger_root / f"{role.lower()}_action_ledger.npz")
            dataset, ledger, report = prepare_conditional_role(
                role, full, full_ledger, fixed[role], fixed_ledgers[role],
                rank_model=models["rank"],
                rank_control_model=models["rank_control"],
                expected_sessions=corpus.expected_sessions, config=config)
            dataset_path = staging / f"{role.lower()}_dataset.npz"
            ledger_path = staging / f"{role.lower()}_ledger.npz"
            dataset_file = dataset.save(dataset_path)
            ledger_file = ledger.save(ledger_path)
            reloaded_dataset = ConfirmationDataset.load(dataset_path)
            reloaded_ledger = OracleActionLedger.load(ledger_path)
            if (reloaded_dataset.representation_sha256
                    != dataset.representation_sha256
                    or reloaded_ledger.representation_sha256
                    != ledger.representation_sha256
                    or reloaded_ledger.source_representation_sha256
                    != reloaded_dataset.representation_sha256):
                raise ValueError("conditional strict reload differs")
            files[role] = {
                "dataset": dataset_path.name,
                "dataset_file_sha256": dataset_file,
                "ledger": ledger_path.name,
                "ledger_file_sha256": ledger_file,
            }
            role_reports[role] = report
            del corpus, full, full_ledger, dataset, ledger
            del reloaded_dataset, reloaded_ledger
            gc.collect()
        core = {
            "schema": "QRE2CONFCONDITIONALCORPUSAUDIT1",
            "stage": args.stage.upper(), "config": asdict(config),
            "config_sha256": config.receipt_sha256,
            "capacity_corpus_receipt_sha256": capacity_receipt,
            "rank_model_bundle_receipt_sha256": rank_receipt,
            "roles": role_reports, "files": files,
            "strict_reload": True,
            "implementation_sha256": {
                "conditional_corpus": C.file_sha256(Path(__file__).resolve()
                    .parents[1] / "engine/entry_v2/confirmation_conditional_corpus.py"),
                "tool": C.file_sha256(Path(__file__)),
            },
            "economics_executed": False,
            "forward_open_count": 0,
            "h2_open_count": 0,
        }
        manifest = {**core, "receipt_sha256": C.object_sha256(core)}
        C.atomic_json(staging / "manifest.json", manifest)
        os.replace(staging, destination)
    except Exception:
        raise
    print(json.dumps(manifest, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({
            "event": "CONDITIONAL_CORPUS_REFUSED",
            "type": type(exc).__name__, "reason": str(exc),
        }, sort_keys=True), flush=True)
        raise
