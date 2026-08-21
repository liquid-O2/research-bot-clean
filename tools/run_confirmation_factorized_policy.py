#!/usr/bin/env python3
"""Run the bounded 30-second rank plus causal timing composition."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile

from catboost import CatBoostClassifier
import numpy as np

from entry_v2 import common as C
from entry_v2.confirmation import ConfirmationConfig, ConfirmationDataset
from entry_v2.confirmation_capacity_corpus import ROLES
from entry_v2.confirmation_experiment import (
    canonical_stage_specs, combine_feature_role, materialize_feature_cache,
)
from entry_v2.confirmation_factorized_policy import (
    FactorizedModels, FactorizedPolicyConfig, factorized_policy_preflight,
    fit_factorized_models, run_factorized_policy,
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
        "--capacity-stability", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_capacity_stability_v2.json"))
    parser.add_argument(
        "--output", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_factorized_policy_v1.json"))
    parser.add_argument(
        "--model-dir", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_factorized_policy_v1_models"))
    parser.add_argument("--stage", default="E1r")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--thread-count", type=int, default=16)
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def _load_capacity(root: Path) -> tuple[
        dict[str, ConfirmationDataset], dict[str, OracleActionLedger],
        dict[str, object]]:
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    core = dict(manifest); receipt = str(core.pop("receipt_sha256"))
    if (manifest.get("schema") != "QRE2CONFCAPACITYCORPUSAUDIT1"
            or C.object_sha256(core) != receipt
            or manifest.get("strict_reload") is not True
            or manifest.get("h2_open_count") != 0):
        raise ValueError("capacity corpus manifest identity differs")
    datasets = {}; ledgers = {}
    for role in ROLES:
        files = manifest["files"][role]
        dataset_path = root / files["dataset"]
        ledger_path = root / files["ledger"]
        if (C.file_sha256(dataset_path) != files["dataset_file_sha256"]
                or C.file_sha256(ledger_path) != files["ledger_file_sha256"]):
            raise ValueError("capacity corpus file identity differs")
        datasets[role] = ConfirmationDataset.load(dataset_path)
        ledgers[role] = OracleActionLedger.load(ledger_path)
    return datasets, ledgers, manifest


def _load_full(args: argparse.Namespace) -> tuple[
        dict[str, ConfirmationDataset], dict[str, OracleActionLedger],
        dict[str, tuple[object, ...]]]:
    windows = fit_only_rehearsal_windows(args.stage)
    specs = dict(canonical_stage_specs(
        args.stage, args.source_root, roles=ROLES))
    config = ConfirmationConfig(max_delay_sec=300, snapshot_mode="TRAINING")
    datasets = {}; ledgers = {}; sessions = {}
    for role in ROLES:
        records = materialize_feature_cache(
            specs[role], config, args.cache_root, workers=args.workers)
        corpus = combine_feature_role(role, windows[role], records)
        datasets[role] = corpus.dataset
        sessions[role] = tuple(corpus.expected_sessions)
        ledgers[role] = OracleActionLedger.load(
            args.ledger_root / f"{role.lower()}_action_ledger.npz")
    return datasets, ledgers, sessions


def _load_capacity_selection(path: Path) -> Mapping[str, object]:
    value = json.loads(path.read_text())
    core = dict(value); receipt = str(core.pop("receipt_sha256"))
    probe = value.get("probe", {})
    selected = next((row for row in probe.get("family_results", ())
                     if row.get("family") == probe.get("selected_family")), None)
    if (C.object_sha256(core) != receipt
            or probe.get("selected_family") != "BALANCED_TOPK"
            or selected is None
            or selected.get("final_tree_counts") != [40]
            or value.get("h2_open_count") != 0):
        raise ValueError("capacity stability selection identity differs")
    return value


def _persist_and_reload(
    models: FactorizedModels, target: Path,
    full: dict[str, ConfirmationDataset],
    fixed: dict[str, ConfirmationDataset],
    config: FactorizedPolicyConfig,
) -> tuple[FactorizedModels, Mapping[str, object]]:
    destination = C.assert_workspace_output(target)
    if destination.exists():
        raise FileExistsError(f"factorized model directory exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(
        prefix=f".{destination.name}.tmp.", dir=destination.parent))
    names = {
        "rank": models.rank,
        "rank_control": models.rank_control,
        "action": models.action,
        "action_control": models.action_control,
    }
    files = {}
    loaded = {}
    try:
        for name, model in names.items():
            path = staging / f"{name}.cbm"
            model.save_model(path, format="cbm")
            files[name] = {
                "path": path.name, "file_sha256": C.file_sha256(path),
                "tree_count": int(model.tree_count_),
            }
            restored = CatBoostClassifier()
            restored.load_model(path, format="cbm")
            loaded[name] = restored

        # Persistence is checked against every role.  Rank matrices are small;
        # action matrices use a deterministic 4,096-row adversary per role.
        verification = {}
        for role in ROLES:
            rank_x = fixed[role].features
            action_indices = np.unique(np.linspace(
                0, len(full[role].features) - 1,
                min(4_096, len(full[role].features))).astype(np.int64))
            action_x = np.asarray(
                full[role].features[action_indices][:, models.action_columns],
                np.float32)
            for name, matrix in (
                ("rank", rank_x), ("rank_control", rank_x),
                ("action", action_x), ("action_control", action_x),
            ):
                before = np.asarray(names[name].predict_proba(matrix), np.float64)
                after = np.asarray(loaded[name].predict_proba(matrix), np.float64)
                if not np.array_equal(before, after):
                    raise ValueError(f"strict model reload differs: {role}:{name}")
            verification[role] = {
                "rank_rows": len(rank_x),
                "action_adversary_rows": len(action_indices),
            }
        manifest_core = {
            "schema": "QRE2CONFFACTMODELBUNDLE1",
            "config_sha256": config.receipt_sha256,
            "model_identity": {
                "rank": models.rank_model_sha256,
                "rank_control": models.rank_control_model_sha256,
                "action": models.action_model_sha256,
                "action_control": models.action_control_model_sha256,
            },
            "files": files,
            "rank_feature_names": fixed["FIT"].feature_names,
            "action_feature_names": models.action_feature_names,
            "action_columns": tuple(int(value)
                                    for value in models.action_columns),
            "strict_reload_verification": verification,
            "strict_reload": True,
            "forward_open_count": 0,
            "h2_open_count": 0,
        }
        manifest = {**manifest_core,
                    "receipt_sha256": C.object_sha256(manifest_core)}
        C.atomic_json(staging / "manifest.json", manifest)
        os.replace(staging, destination)
    except Exception:
        # Leave the staged directory intact for forensic diagnosis.  It is
        # outside the publication path and cannot be mistaken for a bundle.
        raise
    restored_models = FactorizedModels(
        rank=loaded["rank"], rank_control=loaded["rank_control"],
        action=loaded["action"], action_control=loaded["action_control"],
        action_columns=models.action_columns.copy(),
        action_feature_names=models.action_feature_names,
        rank_model_sha256=models.rank_model_sha256,
        rank_control_model_sha256=models.rank_control_model_sha256,
        action_model_sha256=models.action_model_sha256,
        action_control_model_sha256=models.action_control_model_sha256,
    )
    return restored_models, manifest


def main() -> int:
    args = _arguments()
    config = FactorizedPolicyConfig(thread_count=args.thread_count)
    selection = _load_capacity_selection(args.capacity_stability)
    fixed, fixed_ledgers, capacity_manifest = _load_capacity(args.capacity_root)
    full, full_ledgers, sessions = _load_full(args)
    for role in ROLES:
        expected_source = capacity_manifest["preparation"]["roles"][role][
            "source_dataset_sha256"]
        if full[role].representation_sha256 != expected_source:
            raise ValueError("capacity/full source dataset identity differs")
    preflight = factorized_policy_preflight(
        full, full_ledgers, fixed, fixed_ledgers, sessions, config=config)
    if args.preflight_only:
        artifact_core = {
            "schema": "QRE2CONFFACTPOLPREFLIGHTAUDIT1",
            "stage": args.stage.upper(),
            "preflight": preflight,
            "capacity_corpus_receipt_sha256": capacity_manifest["receipt_sha256"],
            "capacity_stability_receipt_sha256": selection["receipt_sha256"],
            "tool_sha256": C.file_sha256(Path(__file__)),
            "models_executed": False,
            "economics_executed": False,
            "forward_open_count": 0,
            "h2_open_count": 0,
        }
        artifact = {**artifact_core,
                    "receipt_sha256": C.object_sha256(artifact_core)}
        C.atomic_json(args.output, artifact)
        print(json.dumps(artifact, sort_keys=True), flush=True)
        return 0

    models = fit_factorized_models(
        full, full_ledgers, fixed, fixed_ledgers, config=config)
    restored, bundle = _persist_and_reload(
        models, args.model_dir, full, fixed, config)
    result = run_factorized_policy(
        full, full_ledgers, fixed, fixed_ledgers, sessions,
        models=restored, config=config)
    artifact_core = {
        "schema": "QRE2CONFFACTPOLAUDIT1",
        "stage": args.stage.upper(),
        "capacity_corpus_receipt_sha256": capacity_manifest["receipt_sha256"],
        "capacity_stability_receipt_sha256": selection["receipt_sha256"],
        "model_bundle_receipt_sha256": bundle["receipt_sha256"],
        "model_bundle_path": str(args.model_dir.resolve()),
        "result": result,
        "tool_sha256": C.file_sha256(Path(__file__)),
        "economics_executed": True,
        "economics_scope": "E1R_SPARSE_TRAINING_GRID_DIAGNOSTIC",
        "exact_replay_ceiling_executed": False,
        "forward_open_count": 0,
        "h2_open_count": 0,
    }
    artifact = {**artifact_core,
                "receipt_sha256": C.object_sha256(artifact_core)}
    C.atomic_json(args.output, artifact)
    concise = {
        "receipt_sha256": artifact["receipt_sha256"],
        "result_receipt_sha256": result["receipt_sha256"],
        "rank_threshold": result["rank_diagnostics"]["LEARNED"]
            ["THRESHOLD"]["overall"],
        "arms": result["arms"],
        "decomposition": result["decomposition"],
        "economics_executed": True,
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
            "event": "FACTORIZED_POLICY_REFUSED",
            "type": type(exc).__name__, "reason": str(exc),
        }, sort_keys=True), flush=True)
        raise
