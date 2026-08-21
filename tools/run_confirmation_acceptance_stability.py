#!/usr/bin/env python3
"""Run FIT-forward conditional candidate-value acceptance on the 30s corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from catboost import CatBoostClassifier

from entry_v2 import common as C
from entry_v2.confirmation import ConfirmationDataset
from entry_v2.confirmation_acceptance_stability import (
    AcceptanceStabilityConfig, acceptance_stability_preflight,
    run_acceptance_stability_probe,
)
from entry_v2.confirmation_capacity_corpus import ROLES
from entry_v2.confirmation_stopping import OracleActionLedger


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--corpus-root", type=Path,
        default=Path("/workspace/artifacts/cache/entry_v2_capacity_30s_v1"))
    parser.add_argument(
        "--rank-model-dir", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_factorized_policy_v1_models"))
    parser.add_argument(
        "--output", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_acceptance_stability_v1.json"))
    parser.add_argument("--thread-count", type=int, default=16)
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    corpus_manifest_path = args.corpus_root / "manifest.json"
    corpus_manifest = json.loads(corpus_manifest_path.read_text())
    corpus_core = dict(corpus_manifest)
    corpus_receipt = str(corpus_core.pop("receipt_sha256"))
    if (corpus_manifest.get("schema") != "QRE2CONFCAPACITYCORPUSAUDIT1"
            or C.object_sha256(corpus_core) != corpus_receipt
            or corpus_manifest.get("strict_reload") is not True
            or corpus_manifest.get("h2_open_count") != 0):
        raise ValueError("acceptance corpus manifest identity differs")
    datasets = {}; ledgers = {}
    for role in ROLES:
        files = corpus_manifest["files"][role]
        dataset_path = args.corpus_root / files["dataset"]
        ledger_path = args.corpus_root / files["ledger"]
        if (C.file_sha256(dataset_path) != files["dataset_file_sha256"]
                or C.file_sha256(ledger_path) != files["ledger_file_sha256"]):
            raise ValueError("acceptance corpus payload identity differs")
        datasets[role] = ConfirmationDataset.load(dataset_path)
        ledgers[role] = OracleActionLedger.load(ledger_path)

    rank_manifest_path = args.rank_model_dir / "manifest.json"
    rank_manifest = json.loads(rank_manifest_path.read_text())
    rank_core = dict(rank_manifest)
    rank_receipt = str(rank_core.pop("receipt_sha256"))
    rank_file = args.rank_model_dir / rank_manifest["files"]["rank"]["path"]
    if (rank_manifest.get("schema") != "QRE2CONFFACTMODELBUNDLE1"
            or C.object_sha256(rank_core) != rank_receipt
            or rank_manifest.get("strict_reload") is not True
            or C.file_sha256(rank_file)
               != rank_manifest["files"]["rank"]["file_sha256"]
            or tuple(rank_manifest["rank_feature_names"])
               != datasets["FIT"].feature_names
            or rank_manifest.get("h2_open_count") != 0):
        raise ValueError("acceptance rank bundle identity differs")
    rank_model = CatBoostClassifier(); rank_model.load_model(rank_file)
    config = AcceptanceStabilityConfig(thread_count=args.thread_count)
    preflight = acceptance_stability_preflight(
        datasets, ledgers,
        capacity_corpus_receipt_sha256=corpus_receipt, config=config)
    if args.preflight_only:
        result = preflight
        schema = "QRE2CONFACCEPTSTABILITYPREFLIGHTAUDIT1"
    else:
        result = run_acceptance_stability_probe(
            datasets, ledgers,
            capacity_corpus_receipt_sha256=corpus_receipt,
            final_rank_model=rank_model,
            final_rank_model_sha256=rank_manifest["model_identity"]["rank"],
            config=config,
            progress=lambda row: print(json.dumps(
                {"event": "ACCEPTANCE_STABILITY_PROGRESS", **row},
                sort_keys=True), flush=True))
        schema = "QRE2CONFACCEPTSTABILITYAUDIT1"
    core = {
        "schema": schema,
        "capacity_corpus_receipt_sha256": corpus_receipt,
        "rank_model_bundle_receipt_sha256": rank_receipt,
        "result": result,
        "tool_sha256": C.file_sha256(Path(__file__)),
        "economics_executed": False,
        "forward_open_count": 0,
        "h2_open_count": 0,
    }
    artifact = {**core, "receipt_sha256": C.object_sha256(core)}
    C.atomic_json(args.output, artifact)
    print(json.dumps(artifact, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({
            "event": "ACCEPTANCE_STABILITY_REFUSED",
            "type": type(exc).__name__, "reason": str(exc),
        }, sort_keys=True), flush=True)
        raise
