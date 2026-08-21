#!/usr/bin/env python3
"""Run the no-model fixed-horizon confirmation mechanism audit."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import Mapping

from entry_v2 import common as C
from entry_v2.confirmation import ConfirmationDataset
from entry_v2.confirmation_fixed_horizon import (
    FixedHorizonConfig, run_fixed_horizon_audit,
)
from entry_v2.confirmation_stopping import OracleActionLedger
from entry_v2.contracts import SessionRef

from run_confirmation_dynamic_hurdle import (
    _learned_fit_gate, _load_capacity_selection, _load_rank_models,
    _verified_manifest,
)


ROLES = ("FIT", "PLATT")


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
        "--rank-model-dir", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_factorized_policy_v1_models"))
    parser.add_argument(
        "--capacity-stability", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_capacity_stability_v2.json"))
    parser.add_argument(
        "--output", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_fixed_horizon_mechanism_v1.json"))
    parser.add_argument("--capacity", type=int, default=12)
    parser.add_argument("--control-replicates", type=int, default=4)
    parser.add_argument("--stage", default="E1r")
    return parser.parse_args()


def _load_roles(
    conditional_root: Path, capacity_root: Path,
) -> tuple[
    Mapping[str, ConfirmationDataset], Mapping[str, OracleActionLedger],
    Mapping[str, ConfirmationDataset], Mapping[str, tuple[SessionRef, ...]],
    Mapping[str, object], Mapping[str, object],
]:
    conditional_manifest = _verified_manifest(
        conditional_root / "manifest.json",
        "QRE2CONFCONDITIONALCORPUSAUDIT1")
    capacity_manifest = _verified_manifest(
        capacity_root / "manifest.json", "QRE2CONFCAPACITYCORPUSAUDIT1")
    if (conditional_manifest["capacity_corpus_receipt_sha256"]
            != capacity_manifest["receipt_sha256"]
            or conditional_manifest.get("h2_open_count") != 0
            or capacity_manifest.get("h2_open_count") != 0):
        raise ValueError("fixed-horizon corpus ancestry differs")
    conditional = {}; ledgers = {}; fixed = {}; sessions = {}
    for role in ROLES:
        conditional_files = conditional_manifest["files"][role]
        dataset_path = conditional_root / conditional_files["dataset"]
        ledger_path = conditional_root / conditional_files["ledger"]
        fixed_files = capacity_manifest["files"][role]
        fixed_path = capacity_root / fixed_files["dataset"]
        for path, expected in (
            (dataset_path, conditional_files["dataset_file_sha256"]),
            (ledger_path, conditional_files["ledger_file_sha256"]),
            (fixed_path, fixed_files["dataset_file_sha256"]),
        ):
            if C.file_sha256(path) != expected:
                raise ValueError(f"fixed-horizon payload identity differs: {path}")
        conditional[role] = ConfirmationDataset.load(dataset_path)
        ledgers[role] = OracleActionLedger.load(ledger_path)
        fixed[role] = ConfirmationDataset.load(fixed_path)
        report = conditional_manifest["roles"][role]
        if (conditional[role].representation_sha256
                != report["dataset_sha256"]
                or ledgers[role].representation_sha256
                   != report["ledger_sha256"]
                or fixed[role].representation_sha256
                   != report["fixed_dataset_sha256"]):
            raise ValueError("fixed-horizon role receipt differs")
        sessions[role] = tuple(SessionRef(
            str(row["asset"]), int(row["trading_day"]), str(row["session_id"]))
            for row in report["expected_sessions"])
        if tuple({"asset": row.asset, "trading_day": row.trading_day,
                  "session_id": row.session_id} for row in sessions[role]) \
                != tuple(report["expected_sessions"]):
            raise ValueError("fixed-horizon session denominator differs")
    return (conditional, ledgers, fixed, sessions,
            conditional_manifest, capacity_manifest)


def main() -> int:
    args = _arguments()
    if args.output.exists():
        raise FileExistsError(f"fixed-horizon output exists: {args.output}")
    config = FixedHorizonConfig(
        capacity=args.capacity, control_replicates=args.control_replicates)
    (conditional, ledgers, fixed, sessions,
     conditional_manifest, capacity_manifest) = _load_roles(
         args.conditional_root, args.capacity_root)
    rank, _rank_control, rank_manifest = _load_rank_models(
        args.rank_model_dir, conditional_manifest)
    stability = _load_capacity_selection(args.capacity_stability)
    gated = {}; gated_ledgers = {}
    for role in ROLES:
        gated[role], gated_ledgers[role] = _learned_fit_gate(
            conditional[role], ledgers[role], fixed[role],
            rank_model=rank, capacity=config.capacity)
    result = run_fixed_horizon_audit(
        gated["FIT"], gated_ledgers["FIT"],
        gated["PLATT"], gated_ledgers["PLATT"], sessions["PLATT"],
        config=config)
    # These are immutable V9/QRF4 representation counts.  A changed count is
    # a new experiment, not an in-place continuation of this audit.
    if result["allowed_features"] != 1_022 \
            or result["dynamic_features"] != 942:
        raise ValueError("fixed-horizon V9 feature census differs")
    core = {
        "schema": "QRE2CONFFIXEDHORIZONAUDIT1",
        "stage": args.stage.upper(),
        "config": asdict(config),
        "config_sha256": config.receipt_sha256,
        "conditional_corpus_receipt_sha256":
            conditional_manifest["receipt_sha256"],
        "capacity_corpus_receipt_sha256":
            capacity_manifest["receipt_sha256"],
        "rank_model_bundle_receipt_sha256": rank_manifest["receipt_sha256"],
        "capacity_stability_receipt_sha256": stability["receipt_sha256"],
        "result": result,
        "implementation_sha256": {
            "module": C.file_sha256(Path(
                "/workspace/engine/entry_v2/confirmation_fixed_horizon.py")),
            "tool": C.file_sha256(Path(__file__)),
        },
        "models_executed": False,
        "learned_economics_executed": False,
        "oracle_mechanism_economics_executed": True,
        "threshold_open_count": 0,
        "forward_open_count": 0,
        "h2_open_count": 0,
    }
    artifact = {**core, "receipt_sha256": C.object_sha256(core)}
    C.atomic_json(args.output, artifact)
    reloaded = json.loads(args.output.read_text())
    reloaded_core = dict(reloaded)
    receipt = str(reloaded_core.pop("receipt_sha256"))
    if receipt != artifact["receipt_sha256"] \
            or C.object_sha256(reloaded_core) != receipt:
        raise ValueError("fixed-horizon artifact strict reload differs")
    concise = {
        "receipt_sha256": receipt,
        "result_receipt_sha256": result["receipt_sha256"],
        "mechanism_gate_pass": result["mechanism_gate_pass"],
        "allowed_features": result["allowed_features"],
        "dynamic_features": result["dynamic_features"],
        "horizons": {
            name: {
                "stable_feature_counts": row["stable_feature_counts"],
                "maximum_control_stable_feature_counts":
                    row["maximum_control_stable_feature_counts"],
                "selected_features": row["selected_features"],
                "platt_path_metrics": row["platt_path_metrics"]["overall"],
                "platt_global_stop_auc": row["platt_global_stop_auc"],
                "mechanism_gate_pass": row["mechanism_gate_pass"],
            } for name, row in result["horizons"].items()
        },
        "oracle_selected": result["oracle_policy_family"]["selected"],
        "models_executed": False,
        "learned_economics_executed": False,
        "threshold_open_count": 0,
        "h2_open_count": 0,
    }
    print(json.dumps(concise, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({
            "event": "FIXED_HORIZON_REFUSED",
            "type": type(exc).__name__, "reason": str(exc),
        }, sort_keys=True), flush=True)
        raise
