#!/usr/bin/env python3
"""Run continuous direct-utility CatBoost on the frozen learned roster."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
from typing import Mapping

from catboost import CatBoostRegressor

from entry_v2 import common as C
from entry_v2.confirmation import ConfirmationDataset
from entry_v2.confirmation_direct_utility_policy import (
    DirectUtilityConfig, DirectUtilityModels, direct_utility_preflight,
    fit_direct_utility_models, run_direct_utility_policy,
)
from entry_v2.confirmation_stopping import OracleActionLedger

# These loaders are the already exercised ancestry/schema implementation used
# by the dynamic policy.  Reusing them prevents a second, subtly different
# interpretation of the same immutable cache and rank-model receipts.
from run_confirmation_dynamic_hurdle import (
    _learned_fit_gate, _load_capacity_selection, _load_corpora,
    _load_rank_models,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--conditional-root", type=Path,
        default=Path(
            "/workspace/artifacts/cache/entry_v2_conditional_paths_top12_v1"))
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
            "e1r_direct_utility_v1.json"))
    parser.add_argument(
        "--model-dir", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_direct_utility_v1_models"))
    parser.add_argument("--stage", default="E1r")
    parser.add_argument("--thread-count", type=int, default=16)
    parser.add_argument("--capacity", type=int, default=12)
    parser.add_argument("--iterations", type=int, default=80)
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def _persist_and_reload(
    models: DirectUtilityModels, target: Path,
    conditional: Mapping[str, ConfirmationDataset],
    config: DirectUtilityConfig, *, conditional_receipt: str,
    rank_bundle_receipt: str,
) -> tuple[DirectUtilityModels, Mapping[str, object]]:
    destination = C.assert_workspace_output(target)
    if destination.exists():
        raise FileExistsError(
            f"direct-utility model directory exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(
        prefix=f".{destination.name}.tmp.", dir=destination.parent))
    named = {"real": models.real, "control": models.control}
    identity = {
        "real": models.real_model_sha256,
        "control": models.control_model_sha256,
    }
    files = {}; loaded = {}
    try:
        for name, model in named.items():
            path = staging / f"{name}.cbm"
            model.save_model(path, format="cbm")
            files[name] = {
                "path": path.name, "file_sha256": C.file_sha256(path),
                "tree_count": int(model.tree_count_),
            }
            restored = CatBoostRegressor()
            restored.load_model(path, format="cbm"); loaded[name] = restored
        verification = {}
        for role, dataset in conditional.items():
            for name in named:
                before = named[name].predict(dataset.features)
                after = loaded[name].predict(dataset.features)
                if not (before == after).all():
                    raise ValueError(
                        f"direct-utility strict reload differs: {role}:{name}")
            verification[role] = {"rows": len(dataset.features)}
        core = {
            "schema": "QRE2CONFDIRECTUTILITYMODELBUNDLE1",
            "config_sha256": config.receipt_sha256,
            "conditional_corpus_receipt_sha256": conditional_receipt,
            "rank_model_bundle_receipt_sha256": rank_bundle_receipt,
            "model_identity": identity,
            "files": files,
            "feature_names": models.feature_names,
            "strict_reload_verification": verification,
            "strict_reload": True,
            "forward_open_count": 0,
            "h2_open_count": 0,
        }
        manifest = {**core, "receipt_sha256": C.object_sha256(core)}
        C.atomic_json(staging / "manifest.json", manifest)
        os.replace(staging, destination)
    except Exception:
        raise
    restored_models = DirectUtilityModels(
        real=loaded["real"], control=loaded["control"],
        feature_names=models.feature_names,
        real_model_sha256=models.real_model_sha256,
        control_model_sha256=models.control_model_sha256,
    )
    return restored_models, manifest


def main() -> int:
    args = _arguments()
    config = DirectUtilityConfig(
        capacity=args.capacity, iterations=args.iterations,
        thread_count=args.thread_count)
    (conditional, ledgers, fixed, fixed_ledgers, sessions,
     conditional_manifest, capacity_manifest) = _load_corpora(
         args.conditional_root, args.capacity_root)
    if int(conditional_manifest["config"]["capacity"]) < config.capacity:
        raise ValueError(
            "conditional corpus does not cover requested gate capacity")
    rank, rank_control, rank_manifest = _load_rank_models(
        args.rank_model_dir, conditional_manifest)
    stability = _load_capacity_selection(args.capacity_stability)
    preflight = direct_utility_preflight(
        conditional, ledgers, fixed, fixed_ledgers, sessions,
        rank_model=rank, rank_control_model=rank_control, config=config)
    if args.preflight_only:
        core = {
            "schema": "QRE2CONFDIRECTUTILITYPREFLIGHTAUDIT1",
            "stage": args.stage.upper(), "preflight": preflight,
            "conditional_corpus_receipt_sha256":
                conditional_manifest["receipt_sha256"],
            "capacity_corpus_receipt_sha256":
                capacity_manifest["receipt_sha256"],
            "rank_model_bundle_receipt_sha256":
                rank_manifest["receipt_sha256"],
            "capacity_stability_receipt_sha256": stability["receipt_sha256"],
            "tool_sha256": C.file_sha256(Path(__file__)),
            "models_executed": False, "economics_executed": False,
            "forward_open_count": 0, "h2_open_count": 0,
        }
        artifact = {**core, "receipt_sha256": C.object_sha256(core)}
        C.atomic_json(args.output, artifact)
        print(json.dumps(artifact, sort_keys=True), flush=True)
        return 0

    fit_dataset, fit_ledger = _learned_fit_gate(
        conditional["FIT"], ledgers["FIT"], fixed["FIT"],
        rank_model=rank, capacity=config.capacity)
    models = fit_direct_utility_models(
        fit_dataset, fit_ledger, config=config)
    restored, bundle = _persist_and_reload(
        models, args.model_dir, conditional, config,
        conditional_receipt=conditional_manifest["receipt_sha256"],
        rank_bundle_receipt=rank_manifest["receipt_sha256"])
    result = run_direct_utility_policy(
        conditional, ledgers, fixed, fixed_ledgers, sessions,
        rank_model=rank, rank_control_model=rank_control,
        models=restored, config=config)
    core = {
        "schema": "QRE2CONFDIRECTUTILITYAUDIT1",
        "stage": args.stage.upper(),
        "conditional_corpus_receipt_sha256":
            conditional_manifest["receipt_sha256"],
        "capacity_corpus_receipt_sha256":
            capacity_manifest["receipt_sha256"],
        "rank_model_bundle_receipt_sha256": rank_manifest["receipt_sha256"],
        "capacity_stability_receipt_sha256": stability["receipt_sha256"],
        "model_bundle_receipt_sha256": bundle["receipt_sha256"],
        "model_bundle_path": str(args.model_dir.resolve()),
        "result": result, "tool_sha256": C.file_sha256(Path(__file__)),
        "economics_executed": True,
        "economics_scope": "E1R_PLATT_SPARSE_TRAINING_GRID_DIAGNOSTIC",
        "threshold_economics_executed": False,
        "exact_replay_ceiling_executed": False,
        "forward_open_count": 0, "h2_open_count": 0,
    }
    artifact = {**core, "receipt_sha256": C.object_sha256(core)}
    C.atomic_json(args.output, artifact)
    concise = {
        "receipt_sha256": artifact["receipt_sha256"],
        "result_receipt_sha256": result["receipt_sha256"],
        "platt_selection_status": result["platt_selection"]["status"],
        "frozen_policy": result["frozen_policy"],
        "platt_fixed_policy_arms": result["platt_fixed_policy_arms"],
        "platt_capture": result["platt_capture"],
        "progression_status": result["progression_status"],
        "progression_reasons": result["progression_reasons"],
        "threshold_economics_executed": False,
        "exact_replay_ceiling_executed": False,
        "h2_open_count": 0,
    }
    print(json.dumps(concise, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({
            "event": "DIRECT_UTILITY_REFUSED",
            "type": type(exc).__name__, "reason": str(exc),
        }, sort_keys=True), flush=True)
        raise
