#!/usr/bin/env python3
"""Run the bounded learned-rank plus conditional two-head stopping test."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
from typing import Mapping

from catboost import CatBoostClassifier
import numpy as np

from entry_v2 import common as C
from entry_v2.confirmation import ConfirmationDataset
from entry_v2.confirmation_capacity_corpus import ROLES
from entry_v2.confirmation_conditional_corpus import asdict_session
from entry_v2.confirmation_dynamic_hurdle_policy import (
    DynamicHurdleConfig, DynamicHurdleModels, dynamic_hurdle_preflight,
    fit_dynamic_hurdle_models, run_dynamic_hurdle_policy,
)
from entry_v2.confirmation_factorized_policy import select_top_capacity_series
from entry_v2.confirmation_stopping import OracleActionLedger
from entry_v2.contracts import SessionRef


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--conditional-root", type=Path,
        default=Path(
            "/workspace/artifacts/cache/entry_v2_conditional_paths_v1"))
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
            "e1r_dynamic_hurdle_v1.json"))
    parser.add_argument(
        "--model-dir", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_dynamic_hurdle_v1_models"))
    parser.add_argument("--stage", default="E1r")
    parser.add_argument("--thread-count", type=int, default=16)
    parser.add_argument("--capacity", type=int, default=4)
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def _verified_manifest(path: Path, schema: str) -> Mapping[str, object]:
    value = json.loads(path.read_text())
    core = dict(value); receipt = str(core.pop("receipt_sha256"))
    if (value.get("schema") != schema
            or C.object_sha256(core) != receipt
            or value.get("strict_reload") is not True
            or value.get("h2_open_count") != 0):
        raise ValueError(f"manifest identity differs: {path}")
    return value


def _load_corpora(
    conditional_root: Path, capacity_root: Path,
) -> tuple[
    dict[str, ConfirmationDataset], dict[str, OracleActionLedger],
    dict[str, ConfirmationDataset], dict[str, OracleActionLedger],
    dict[str, tuple[SessionRef, ...]], Mapping[str, object],
    Mapping[str, object],
]:
    conditional_manifest = _verified_manifest(
        conditional_root / "manifest.json",
        "QRE2CONFCONDITIONALCORPUSAUDIT1")
    capacity_manifest = _verified_manifest(
        capacity_root / "manifest.json", "QRE2CONFCAPACITYCORPUSAUDIT1")
    if (conditional_manifest["capacity_corpus_receipt_sha256"]
            != capacity_manifest["receipt_sha256"]):
        raise ValueError("conditional/capacity ancestry differs")
    conditional = {}; ledgers = {}; fixed = {}; fixed_ledgers = {}; sessions = {}
    for role in ROLES:
        conditional_files = conditional_manifest["files"][role]
        dataset_path = conditional_root / conditional_files["dataset"]
        ledger_path = conditional_root / conditional_files["ledger"]
        if (C.file_sha256(dataset_path)
                != conditional_files["dataset_file_sha256"]
                or C.file_sha256(ledger_path)
                   != conditional_files["ledger_file_sha256"]):
            raise ValueError("conditional payload identity differs")
        conditional[role] = ConfirmationDataset.load(dataset_path)
        ledgers[role] = OracleActionLedger.load(ledger_path)
        fixed_files = capacity_manifest["files"][role]
        fixed_path = capacity_root / fixed_files["dataset"]
        fixed_ledger_path = capacity_root / fixed_files["ledger"]
        if (C.file_sha256(fixed_path) != fixed_files["dataset_file_sha256"]
                or C.file_sha256(fixed_ledger_path)
                   != fixed_files["ledger_file_sha256"]):
            raise ValueError("capacity payload identity differs")
        fixed[role] = ConfirmationDataset.load(fixed_path)
        fixed_ledgers[role] = OracleActionLedger.load(fixed_ledger_path)
        sessions[role] = tuple(SessionRef(
            str(row["asset"]), int(row["trading_day"]), str(row["session_id"]))
            for row in conditional_manifest["roles"][role]["expected_sessions"])
        if tuple(asdict_session(row) for row in sessions[role]) != tuple(
                conditional_manifest["roles"][role]["expected_sessions"]):
            raise ValueError("conditional session denominator differs")
        report = conditional_manifest["roles"][role]
        if (conditional[role].representation_sha256
                != report["dataset_sha256"]
                or ledgers[role].representation_sha256
                   != report["ledger_sha256"]
                or fixed[role].representation_sha256
                   != report["fixed_dataset_sha256"]
                or fixed_ledgers[role].representation_sha256
                   != report["fixed_ledger_sha256"]):
            raise ValueError("conditional role receipt differs")
    return (conditional, ledgers, fixed, fixed_ledgers, sessions,
            conditional_manifest, capacity_manifest)


def _load_rank_models(
    root: Path, conditional_manifest: Mapping[str, object],
) -> tuple[CatBoostClassifier, CatBoostClassifier, Mapping[str, object]]:
    manifest = _verified_manifest(
        root / "manifest.json", "QRE2CONFFACTMODELBUNDLE1")
    if manifest["receipt_sha256"] != conditional_manifest[
            "rank_model_bundle_receipt_sha256"]:
        raise ValueError("conditional/rank bundle ancestry differs")
    loaded = {}
    for name in ("rank", "rank_control"):
        path = root / manifest["files"][name]["path"]
        if C.file_sha256(path) != manifest["files"][name]["file_sha256"]:
            raise ValueError("rank model payload differs")
        model = CatBoostClassifier(); model.load_model(path, format="cbm")
        loaded[name] = model
    return loaded["rank"], loaded["rank_control"], manifest


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


def _learned_fit_gate(
    conditional: ConfirmationDataset, ledger: OracleActionLedger,
    fixed: ConfirmationDataset, *, rank_model: CatBoostClassifier,
    capacity: int,
) -> tuple[ConfirmationDataset, OracleActionLedger]:
    rank_score = np.asarray(
        rank_model.predict_proba(fixed.features)[:, 1], np.float64)
    selected = set(select_top_capacity_series(
        fixed, rank_score, capacity=capacity))
    watch_timestamp = {str(series): int(timestamp)
                       for series, timestamp in zip(
                           fixed.series_id, fixed.snapshot_ts_ns)
                       if str(series) in selected}
    series = np.asarray(conditional.series_id, str)
    timestamp = np.asarray(conditional.snapshot_ts_ns, np.int64)
    indices = np.flatnonzero(np.isin(series, tuple(selected)))
    if set(series[indices].tolist()) != selected:
        raise ValueError("learned FIT gate is absent from conditional corpus")
    for candidate in selected:
        local = indices[series[indices] == candidate]
        earliest = int(local[np.argmin(timestamp[local])])
        if int(timestamp[earliest]) != watch_timestamp[candidate]:
            raise ValueError("learned gate path does not start at fixed watch")
    subset = conditional.subset(np.isin(series, tuple(selected)))
    # Use the same immutable row projection as all published action ledgers.
    from entry_v2.confirmation_capacity_corpus import _take_ledger
    subset_ledger = _take_ledger(ledger, indices, subset)
    return subset, subset_ledger


def _persist_and_reload(
    models: DynamicHurdleModels, target: Path,
    conditional: Mapping[str, ConfirmationDataset],
    config: DynamicHurdleConfig, *,
    conditional_receipt: str, rank_bundle_receipt: str,
) -> tuple[DynamicHurdleModels, Mapping[str, object]]:
    destination = C.assert_workspace_output(target)
    if destination.exists():
        raise FileExistsError(
            f"dynamic-hurdle model directory exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(
        prefix=f".{destination.name}.tmp.", dir=destination.parent))
    named = {
        "timing": models.timing,
        "value": models.value,
        "timing_control": models.timing_control,
        "value_control": models.value_control,
    }
    identity = {
        "timing": models.timing_model_sha256,
        "value": models.value_model_sha256,
        "timing_control": models.timing_control_model_sha256,
        "value_control": models.value_control_model_sha256,
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
            restored = CatBoostClassifier(); restored.load_model(path, format="cbm")
            loaded[name] = restored
        verification = {}
        for role in ROLES:
            matrix = conditional[role].features
            for name in named:
                before = np.asarray(named[name].predict_proba(matrix), np.float64)
                after = np.asarray(loaded[name].predict_proba(matrix), np.float64)
                if not np.array_equal(before, after):
                    raise ValueError(
                        f"dynamic-hurdle strict reload differs: {role}:{name}")
            verification[role] = {"rows": len(matrix)}
        core = {
            "schema": "QRE2CONFDYNHURDLEMODELBUNDLE1",
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
    restored = DynamicHurdleModels(
        timing=loaded["timing"], value=loaded["value"],
        timing_control=loaded["timing_control"],
        value_control=loaded["value_control"],
        feature_names=models.feature_names,
        timing_model_sha256=models.timing_model_sha256,
        value_model_sha256=models.value_model_sha256,
        timing_control_model_sha256=models.timing_control_model_sha256,
        value_control_model_sha256=models.value_control_model_sha256,
    )
    return restored, manifest


def main() -> int:
    args = _arguments()
    config = DynamicHurdleConfig(
        capacity=args.capacity, thread_count=args.thread_count)
    (conditional, ledgers, fixed, fixed_ledgers, sessions,
     conditional_manifest, capacity_manifest) = _load_corpora(
        args.conditional_root, args.capacity_root)
    if int(conditional_manifest["config"]["capacity"]) < config.capacity:
        raise ValueError(
            "conditional corpus does not cover requested gate capacity")
    rank, rank_control, rank_manifest = _load_rank_models(
        args.rank_model_dir, conditional_manifest)
    stability = _load_capacity_selection(args.capacity_stability)
    if (stability["receipt_sha256"]
            != json.loads((args.capacity_stability).read_text())["receipt_sha256"]):
        raise ValueError("capacity stability receipt differs")
    preflight = dynamic_hurdle_preflight(
        conditional, ledgers, fixed, fixed_ledgers, sessions,
        rank_model=rank, rank_control_model=rank_control, config=config)
    if args.preflight_only:
        core = {
            "schema": "QRE2CONFDYNHURDLEPREFLIGHTAUDIT1",
            "stage": args.stage.upper(),
            "preflight": preflight,
            "conditional_corpus_receipt_sha256":
                conditional_manifest["receipt_sha256"],
            "capacity_corpus_receipt_sha256":
                capacity_manifest["receipt_sha256"],
            "rank_model_bundle_receipt_sha256": rank_manifest["receipt_sha256"],
            "capacity_stability_receipt_sha256": stability["receipt_sha256"],
            "tool_sha256": C.file_sha256(Path(__file__)),
            "models_executed": False,
            "economics_executed": False,
            "forward_open_count": 0,
            "h2_open_count": 0,
        }
        artifact = {**core, "receipt_sha256": C.object_sha256(core)}
        C.atomic_json(args.output, artifact)
        print(json.dumps(artifact, sort_keys=True), flush=True)
        return 0

    fit_dataset, fit_ledger = _learned_fit_gate(
        conditional["FIT"], ledgers["FIT"], fixed["FIT"],
        rank_model=rank, capacity=config.capacity)
    models = fit_dynamic_hurdle_models(
        fit_dataset, fit_ledger, config=config)
    restored, bundle = _persist_and_reload(
        models, args.model_dir, conditional, config,
        conditional_receipt=conditional_manifest["receipt_sha256"],
        rank_bundle_receipt=rank_manifest["receipt_sha256"])
    result = run_dynamic_hurdle_policy(
        conditional, ledgers, fixed, fixed_ledgers, sessions,
        rank_model=rank, rank_control_model=rank_control,
        rank_model_sha256=rank_manifest["model_identity"]["rank"],
        rank_control_model_sha256=rank_manifest["model_identity"]["rank_control"],
        models=restored, config=config)
    core = {
        "schema": "QRE2CONFDYNHURDLEAUDIT1",
        "stage": args.stage.upper(),
        "conditional_corpus_receipt_sha256":
            conditional_manifest["receipt_sha256"],
        "capacity_corpus_receipt_sha256": capacity_manifest["receipt_sha256"],
        "rank_model_bundle_receipt_sha256": rank_manifest["receipt_sha256"],
        "capacity_stability_receipt_sha256": stability["receipt_sha256"],
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
    artifact = {**core, "receipt_sha256": C.object_sha256(core)}
    C.atomic_json(args.output, artifact)
    concise = {
        "receipt_sha256": artifact["receipt_sha256"],
        "result_receipt_sha256": result["receipt_sha256"],
        "platt_selection": result["platt_selection"],
        "frozen_policy": result["frozen_policy"],
        "frozen_policy_basis": result["frozen_policy_basis"],
        "platt_fixed_policy_arms": result["platt_fixed_policy_arms"],
        "threshold_fixed_policy_arms": result[
            "threshold_fixed_policy_arms"],
        "decomposition": result["decomposition"],
        "threshold_economics_executed": result[
            "threshold_economics_executed"],
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
            "event": "DYNAMIC_HURDLE_REFUSED",
            "type": type(exc).__name__, "reason": str(exc),
        }, sort_keys=True), flush=True)
        raise
