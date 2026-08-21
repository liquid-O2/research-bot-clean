#!/usr/bin/env python3
"""Run the all-candidate portfolio-aware watch-gate diagnostic."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile

from catboost import CatBoostClassifier
import numpy as np

from entry_v2 import common as C
from entry_v2.confirmation import ConfirmationDataset
from entry_v2.confirmation_capacity_corpus import ROLES
from entry_v2.confirmation_portfolio_gate_probe import (
    PortfolioGateConfig, PortfolioGateModels, fit_portfolio_gate_models,
    portfolio_gate_preflight, portfolio_schedule_target,
    run_portfolio_gate_probe,
)
from entry_v2.confirmation_stopping import OracleActionLedger
from entry_v2.contracts import SessionRef


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--path-root", type=Path,
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
        "--output", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_portfolio_gate_v1.json"))
    parser.add_argument(
        "--model-dir", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_portfolio_gate_v1_models"))
    parser.add_argument("--stage", default="E1r")
    parser.add_argument("--thread-count", type=int, default=16)
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def _manifest(path: Path, schema: str) -> dict[str, object]:
    value = json.loads(path.read_text()); core = dict(value)
    receipt = str(core.pop("receipt_sha256"))
    if (value.get("schema") != schema or C.object_sha256(core) != receipt
            or value.get("strict_reload") is not True
            or value.get("h2_open_count") != 0):
        raise ValueError(f"manifest identity differs: {path}")
    return value


def _load_inputs(args: argparse.Namespace):
    path_manifest = _manifest(
        args.path_root / "manifest.json",
        "QRE2CONFCONDITIONALCORPUSAUDIT1")
    capacity_manifest = _manifest(
        args.capacity_root / "manifest.json",
        "QRE2CONFCAPACITYCORPUSAUDIT1")
    rank_manifest = _manifest(
        args.rank_model_dir / "manifest.json",
        "QRE2CONFFACTMODELBUNDLE1")
    if (path_manifest["capacity_corpus_receipt_sha256"]
            != capacity_manifest["receipt_sha256"]
            or path_manifest["rank_model_bundle_receipt_sha256"]
               != rank_manifest["receipt_sha256"]
            or path_manifest["config"].get("include_all_watchable_series")
               is not True):
        raise ValueError("portfolio-gate input ancestry/mode differs")
    paths = {}; fixed = {}; sessions = {}
    for role in ROLES:
        pf = path_manifest["files"][role]
        pp = args.path_root / pf["dataset"]
        lp = args.path_root / pf["ledger"]
        if (C.file_sha256(pp) != pf["dataset_file_sha256"]
                or C.file_sha256(lp) != pf["ledger_file_sha256"]):
            raise ValueError("portfolio-gate path payload differs")
        paths[role] = ConfirmationDataset.load(pp)
        path_ledger = OracleActionLedger.load(lp)
        if path_ledger.source_representation_sha256 != paths[
                role].representation_sha256:
            raise ValueError("portfolio-gate path ledger differs")
        ff = capacity_manifest["files"][role]
        fp = args.capacity_root / ff["dataset"]
        flp = args.capacity_root / ff["ledger"]
        if (C.file_sha256(fp) != ff["dataset_file_sha256"]
                or C.file_sha256(flp) != ff["ledger_file_sha256"]):
            raise ValueError("portfolio-gate fixed payload differs")
        fixed[role] = ConfirmationDataset.load(fp)
        fixed_ledger = OracleActionLedger.load(flp)
        if fixed_ledger.source_representation_sha256 != fixed[
                role].representation_sha256:
            raise ValueError("portfolio-gate fixed ledger differs")
        sessions[role] = tuple(SessionRef(
            str(row["asset"]), int(row["trading_day"]), str(row["session_id"]))
            for row in path_manifest["roles"][role]["expected_sessions"])
    rank = {}
    for name in ("rank", "rank_control"):
        info = rank_manifest["files"][name]
        path = args.rank_model_dir / info["path"]
        if C.file_sha256(path) != info["file_sha256"]:
            raise ValueError("portfolio-gate rank payload differs")
        model = CatBoostClassifier(); model.load_model(path, format="cbm")
        rank[name] = model
    return (paths, fixed, sessions, rank, path_manifest,
            capacity_manifest, rank_manifest)


def _persist_and_reload(
    models: PortfolioGateModels, destination: Path,
    fixed: dict[str, ConfirmationDataset], config: PortfolioGateConfig, *,
    path_receipt: str, rank_receipt: str,
):
    target = C.assert_workspace_output(destination)
    if target.exists():
        raise FileExistsError(f"portfolio-gate model directory exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(
        prefix=f".{target.name}.tmp.", dir=target.parent))
    named = {"real": models.real, "control": models.control}
    loaded = {}; files = {}
    try:
        for name, model in named.items():
            path = staging / f"{name}.cbm"; model.save_model(path, format="cbm")
            files[name] = {"path": path.name,
                           "file_sha256": C.file_sha256(path),
                           "tree_count": int(model.tree_count_)}
            restored = CatBoostClassifier(); restored.load_model(path, format="cbm")
            loaded[name] = restored
        verification = {}
        for role in ROLES:
            for name in named:
                before = np.asarray(named[name].predict_proba(
                    fixed[role].features), np.float64)
                after = np.asarray(loaded[name].predict_proba(
                    fixed[role].features), np.float64)
                if not np.array_equal(before, after):
                    raise ValueError(
                        f"portfolio-gate strict reload differs: {role}:{name}")
            verification[role] = {"rows": len(fixed[role].features)}
        core = {
            "schema": "QRE2CONFPORTGATEMODELBUNDLE1",
            "config_sha256": config.receipt_sha256,
            "all_path_corpus_receipt_sha256": path_receipt,
            "rank_model_bundle_receipt_sha256": rank_receipt,
            "model_identity": {
                "real": models.real_model_sha256,
                "control": models.control_model_sha256,
            },
            "files": files, "feature_names": models.feature_names,
            "strict_reload_verification": verification,
            "strict_reload": True, "forward_open_count": 0,
            "h2_open_count": 0,
        }
        manifest = {**core, "receipt_sha256": C.object_sha256(core)}
        C.atomic_json(staging / "manifest.json", manifest)
        os.replace(staging, target)
    except Exception:
        raise
    restored = PortfolioGateModels(
        loaded["real"], loaded["control"], models.feature_names,
        models.real_model_sha256, models.control_model_sha256)
    return restored, manifest


def main() -> int:
    args = _arguments()
    config = PortfolioGateConfig(thread_count=args.thread_count)
    (paths, fixed, sessions, rank, path_manifest,
     capacity_manifest, rank_manifest) = _load_inputs(args)
    preflight = portfolio_gate_preflight(
        paths, fixed, sessions, rank_model=rank["rank"],
        rank_control_model=rank["rank_control"], config=config)
    if args.preflight_only:
        core = {
            "schema": "QRE2CONFPORTGATEPREFLIGHTAUDIT1",
            "stage": args.stage.upper(), "preflight": preflight,
            "all_path_corpus_receipt_sha256": path_manifest["receipt_sha256"],
            "capacity_corpus_receipt_sha256": capacity_manifest["receipt_sha256"],
            "rank_model_bundle_receipt_sha256": rank_manifest["receipt_sha256"],
            "tool_sha256": C.file_sha256(Path(__file__)),
            "models_executed": False, "economics_executed": False,
            "forward_open_count": 0, "h2_open_count": 0,
        }
        artifact = {**core, "receipt_sha256": C.object_sha256(core)}
        C.atomic_json(args.output, artifact)
        print(json.dumps(artifact, sort_keys=True), flush=True); return 0
    fit_target, target_report = portfolio_schedule_target(
        paths["FIT"], fixed["FIT"])
    models = fit_portfolio_gate_models(
        fixed["FIT"], fit_target, config=config)
    restored, bundle = _persist_and_reload(
        models, args.model_dir, fixed, config,
        path_receipt=path_manifest["receipt_sha256"],
        rank_receipt=rank_manifest["receipt_sha256"])
    result = run_portfolio_gate_probe(
        paths, fixed, sessions, rank_model=rank["rank"],
        rank_control_model=rank["rank_control"], models=restored,
        config=config)
    core = {
        "schema": "QRE2CONFPORTGATEAUDIT1", "stage": args.stage.upper(),
        "all_path_corpus_receipt_sha256": path_manifest["receipt_sha256"],
        "capacity_corpus_receipt_sha256": capacity_manifest["receipt_sha256"],
        "rank_model_bundle_receipt_sha256": rank_manifest["receipt_sha256"],
        "model_bundle_receipt_sha256": bundle["receipt_sha256"],
        "model_bundle_path": str(args.model_dir.resolve()),
        "fit_target": target_report, "result": result,
        "tool_sha256": C.file_sha256(Path(__file__)),
        "economics_executed": False,
        "candidate_gate_ceiling_diagnostic_executed": True,
        "exact_replay_ceiling_executed": False,
        "forward_open_count": 0, "h2_open_count": 0,
    }
    artifact = {**core, "receipt_sha256": C.object_sha256(core)}
    C.atomic_json(args.output, artifact)
    print(json.dumps({
        "receipt_sha256": artifact["receipt_sha256"],
        "result_receipt_sha256": result["receipt_sha256"],
        "fit_oof_capture": result["fit_oof_capture"],
        "platt": result["platt"],
        "progression_status": result["progression_status"],
        "progression_reasons": result["progression_reasons"],
        "threshold": result["threshold"],
        "economics_executed": False, "h2_open_count": 0,
    }, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"event": "PORTFOLIO_GATE_REFUSED",
                          "type": type(exc).__name__, "reason": str(exc)},
                         sort_keys=True), flush=True)
        raise
