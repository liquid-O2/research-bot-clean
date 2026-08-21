#!/usr/bin/env python3
"""Run the fixed-watch continuous lawful-candidate-value audit."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from entry_v2 import common as C
from entry_v2.confirmation_lawful_value import (
    LawfulValueConfig, run_lawful_value_audit,
)

from run_confirmation_fixed_horizon import _load_roles


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--conditional-root", type=Path,
        default=Path(
            "/workspace/artifacts/cache/entry_v2_conditional_paths_all_v1"))
    parser.add_argument(
        "--capacity-root", type=Path,
        default=Path("/workspace/artifacts/cache/entry_v2_capacity_30s_v1"))
    parser.add_argument(
        "--output", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_lawful_value_mechanism_v1.json"))
    parser.add_argument("--control-replicates", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    if args.output.exists():
        raise FileExistsError(f"lawful-value output exists: {args.output}")
    (conditional, ledgers, fixed, _sessions,
     conditional_manifest, capacity_manifest) = _load_roles(
         args.conditional_root, args.capacity_root)
    config = LawfulValueConfig(control_replicates=args.control_replicates)
    result = run_lawful_value_audit(
        conditional["FIT"], ledgers["FIT"], fixed["FIT"],
        conditional["PLATT"], ledgers["PLATT"], fixed["PLATT"],
        config=config)
    core = {
        "schema": "QRE2CONFLAWFULVALUEAUDIT1",
        "config": asdict(config), "config_sha256": config.receipt_sha256,
        "conditional_corpus_receipt_sha256":
            conditional_manifest["receipt_sha256"],
        "capacity_corpus_receipt_sha256": capacity_manifest["receipt_sha256"],
        "result": result,
        "implementation_sha256": {
            "module": C.file_sha256(Path(
                "/workspace/engine/entry_v2/confirmation_lawful_value.py")),
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
    if (receipt != artifact["receipt_sha256"]
            or C.object_sha256(check) != receipt):
        raise ValueError("lawful-value artifact strict reload differs")
    print(json.dumps({
        "receipt_sha256": receipt,
        "result_receipt_sha256": result["receipt_sha256"],
        "mechanism_gate_pass": result["mechanism_gate_pass"],
        "target_summaries": result["target_summaries"],
        "stable_feature_counts": result["stable_feature_counts"],
        "maximum_control_stable_feature_counts":
            result["maximum_control_stable_feature_counts"],
        "selected_features": result["selected_features"],
        "platt_group_metrics": result["platt_group_metrics"]["overall"],
        "platt_topk_lawful_value_diagnostics":
            result["platt_topk_lawful_value_diagnostics"],
        "models_executed": False, "economics_executed": False,
        "threshold_open_count": 0, "h2_open_count": 0,
    }, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({
            "event": "LAWFUL_VALUE_REFUSED", "type": type(exc).__name__,
            "reason": str(exc),
        }, sort_keys=True), flush=True)
        raise
