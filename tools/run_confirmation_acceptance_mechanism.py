#!/usr/bin/env python3
"""Run fixed-watch cross-sectional candidate-acceptance audit."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from entry_v2 import common as C
from entry_v2.confirmation import ConfirmationDataset
from entry_v2.confirmation_acceptance_mechanism import (
    AcceptanceMechanismConfig, run_acceptance_mechanism_audit,
)
from entry_v2.confirmation_stopping import OracleActionLedger

from run_confirmation_dynamic_hurdle import _verified_manifest


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--corpus-root", type=Path,
        default=Path("/workspace/artifacts/cache/entry_v2_capacity_30s_v1"))
    parser.add_argument(
        "--output", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_acceptance_mechanism_v1.json"))
    parser.add_argument("--control-replicates", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    if args.output.exists():
        raise FileExistsError(f"acceptance output exists: {args.output}")
    manifest = _verified_manifest(
        args.corpus_root / "manifest.json", "QRE2CONFCAPACITYCORPUSAUDIT1")
    datasets = {}; ledgers = {}
    for role in ("FIT", "PLATT"):
        files = manifest["files"][role]
        dataset_path = args.corpus_root / files["dataset"]
        ledger_path = args.corpus_root / files["ledger"]
        if (C.file_sha256(dataset_path) != files["dataset_file_sha256"]
                or C.file_sha256(ledger_path)
                   != files["ledger_file_sha256"]):
            raise ValueError("acceptance payload identity differs")
        datasets[role] = ConfirmationDataset.load(dataset_path)
        ledgers[role] = OracleActionLedger.load(ledger_path)
        report = manifest["preparation"]["roles"][role]
        if (datasets[role].representation_sha256
                != report["dataset_sha256"]
                or ledgers[role].representation_sha256
                   != report["ledger_sha256"]):
            raise ValueError("acceptance role identity differs")
    config = AcceptanceMechanismConfig(
        control_replicates=args.control_replicates)
    result = run_acceptance_mechanism_audit(
        datasets["FIT"], ledgers["FIT"],
        datasets["PLATT"], ledgers["PLATT"], config=config)
    core = {
        "schema": "QRE2CONFACCEPTMECHANISMAUDIT1",
        "config": asdict(config), "config_sha256": config.receipt_sha256,
        "capacity_corpus_receipt_sha256": manifest["receipt_sha256"],
        "result": result,
        "implementation_sha256": {
            "module": C.file_sha256(Path(
                "/workspace/engine/entry_v2/"
                "confirmation_acceptance_mechanism.py")),
            "tool": C.file_sha256(Path(__file__)),
        },
        "models_executed": False, "economics_executed": False,
        "threshold_open_count": 0, "forward_open_count": 0,
        "h2_open_count": 0,
    }
    artifact = {**core, "receipt_sha256": C.object_sha256(core)}
    C.atomic_json(args.output, artifact)
    reloaded = json.loads(args.output.read_text()); check = dict(reloaded)
    receipt = str(check.pop("receipt_sha256"))
    if receipt != artifact["receipt_sha256"] \
            or C.object_sha256(check) != receipt:
        raise ValueError("acceptance artifact strict reload differs")
    print(json.dumps({
        "receipt_sha256": receipt,
        "result_receipt_sha256": result["receipt_sha256"],
        "mechanism_gate_pass": result["mechanism_gate_pass"],
        "allowed_features": result["allowed_features"],
        "dynamic_features": result["dynamic_features"],
        "stable_feature_counts": result["stable_feature_counts"],
        "maximum_control_stable_feature_counts":
            result["maximum_control_stable_feature_counts"],
        "selected_features": result["selected_features"],
        "platt_group_metrics": result["platt_group_metrics"]["overall"],
        "platt_topk_candidate_local_diagnostics":
            result["platt_topk_candidate_local_diagnostics"],
        "models_executed": False, "economics_executed": False,
        "threshold_open_count": 0, "h2_open_count": 0,
    }, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({
            "event": "ACCEPTANCE_MECHANISM_REFUSED",
            "type": type(exc).__name__, "reason": str(exc),
        }, sort_keys=True), flush=True)
        raise
