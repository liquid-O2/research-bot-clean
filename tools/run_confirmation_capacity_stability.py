#!/usr/bin/env python3
"""Run FIT-forward objective selection from the compact 30-second corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from entry_v2 import common as C
from entry_v2.confirmation import ConfirmationDataset
from entry_v2.confirmation_capacity_corpus import ROLES
from entry_v2.confirmation_capacity_stability import (
    CapacityStabilityConfig, capacity_stability_preflight,
    run_capacity_stability_probe,
)
from entry_v2.confirmation_stopping import OracleActionLedger


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--corpus-root", type=Path,
        default=Path("/workspace/artifacts/cache/entry_v2_capacity_30s_v1"))
    parser.add_argument(
        "--output", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_capacity_stability_v1.json"))
    parser.add_argument("--fold-iterations", type=int, default=30)
    parser.add_argument("--final-iterations", type=int, default=80)
    parser.add_argument("--depth", type=int, default=5)
    parser.add_argument("--thread-count", type=int, default=16)
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    manifest_path = args.corpus_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    expected = dict(manifest); receipt = str(expected.pop("receipt_sha256"))
    if (manifest.get("schema") != "QRE2CONFCAPACITYCORPUSAUDIT1"
            or C.object_sha256(expected) != receipt
            or manifest.get("strict_reload") is not True
            or manifest.get("h2_open_count") != 0):
        raise ValueError("capacity corpus manifest identity differs")
    datasets = {}
    ledgers = {}
    for role in ROLES:
        files = manifest["files"][role]
        dataset_path = args.corpus_root / files["dataset"]
        ledger_path = args.corpus_root / files["ledger"]
        if (C.file_sha256(dataset_path) != files["dataset_file_sha256"]
                or C.file_sha256(ledger_path)
                != files["ledger_file_sha256"]):
            raise ValueError("capacity corpus file identity differs")
        datasets[role] = ConfirmationDataset.load(dataset_path)
        ledgers[role] = OracleActionLedger.load(ledger_path)

    def progress(row: dict[str, object]) -> None:
        print(json.dumps(
            {"event": "CAPACITY_STABILITY_PROGRESS", **row},
            sort_keys=True), file=sys.stderr, flush=True)

    config = CapacityStabilityConfig(
        fold_iterations=args.fold_iterations,
        final_iterations=args.final_iterations,
        depth=args.depth, thread_count=args.thread_count)
    if args.preflight_only:
        result = capacity_stability_preflight(
            datasets, ledgers,
            capacity_corpus_receipt_sha256=receipt, config=config)
        core = {
            "schema": "QRE2CONFCAPACITYSTABILITYPREFLIGHTAUDIT1",
            "capacity_corpus_manifest_sha256": C.file_sha256(manifest_path),
            "capacity_corpus_receipt_sha256": receipt,
            "preflight": result,
            "tool_sha256": C.file_sha256(Path(__file__)),
            "economics_executed": False,
            "forward_open_count": 0,
            "h2_open_count": 0,
        }
        artifact = {**core, "receipt_sha256": C.object_sha256(core)}
        C.atomic_json(args.output, artifact)
        print(json.dumps(artifact, sort_keys=True), flush=True)
        return 0
    result = run_capacity_stability_probe(
        datasets, ledgers, capacity_corpus_receipt_sha256=receipt,
        config=config, progress=progress)
    core = {
        "schema": "QRE2CONFCAPACITYSTABILITYAUDIT2",
        "capacity_corpus_manifest_sha256": C.file_sha256(manifest_path),
        "capacity_corpus_receipt_sha256": receipt,
        "probe": result,
        "tool_sha256": C.file_sha256(Path(__file__)),
        "economics_executed": False,
        "forward_open_count": 0,
        "h2_open_count": 0,
    }
    artifact = {**core, "receipt_sha256": C.object_sha256(core)}
    C.atomic_json(args.output, artifact)
    print(json.dumps({
        "receipt_sha256": artifact["receipt_sha256"],
        "probe_receipt_sha256": result["receipt_sha256"],
        "selection_role": result["selection_role"],
        "selected_family": result["selected_family"],
        "families": [{
            "family": row["family"],
            "fit_oof": row["fit_oof_diagnostic"]["overall"],
            "platt": row["final_diagnostics"]["PLATT"]["overall"],
            "threshold": row["final_diagnostics"]["THRESHOLD"]["overall"],
        } for row in result["family_results"]],
        "selected_control_fit_oof": result["selected_negative_control"]
            ["fit_oof_diagnostic"]["overall"],
        "selected_control_threshold": result["selected_negative_control"]
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
            "event": "CAPACITY_STABILITY_REFUSED",
            "type": type(exc).__name__, "reason": str(exc),
        }, sort_keys=True), file=sys.stderr, flush=True)
        raise
