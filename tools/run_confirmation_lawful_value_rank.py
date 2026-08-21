#!/usr/bin/env python3
"""Fit the one registered continuous lawful-value CatBoost ranker."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from entry_v2 import common as C
from entry_v2.confirmation_lawful_value import (
    LawfulValueConfig, candidate_lawful_value_target,
)
from entry_v2.confirmation_lawful_value_model import (
    LawfulValueRankConfig, fit_lawful_value_rankers,
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
        "--mechanism-audit", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_lawful_value_mechanism_v1.json"))
    parser.add_argument(
        "--output", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_lawful_value_rank_v1.json"))
    parser.add_argument(
        "--model-dir", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_lawful_value_rank_v1_models"))
    return parser.parse_args()


def _load_audit(path: Path) -> dict:
    value = json.loads(path.read_text()); core = dict(value)
    receipt = str(core.pop("receipt_sha256"))
    if (value.get("schema") != "QRE2CONFLAWFULVALUEAUDIT1"
            or C.object_sha256(core) != receipt
            or not value["result"]["mechanism_gate_pass"]
            or value.get("threshold_open_count") != 0
            or value.get("h2_open_count") != 0):
        raise ValueError("lawful-value mechanism audit differs")
    result = dict(value["result"]); result_receipt = result.pop("receipt_sha256")
    if C.object_sha256(result) != result_receipt:
        raise ValueError("lawful-value mechanism result receipt differs")
    return value


def main() -> int:
    args = _arguments()
    if args.output.exists() or args.model_dir.exists():
        raise FileExistsError("lawful-value rank output already exists")
    audit = _load_audit(args.mechanism_audit)
    (conditional, ledgers, fixed, _sessions,
     conditional_manifest, capacity_manifest) = _load_roles(
         args.conditional_root, args.capacity_root)
    if (audit["conditional_corpus_receipt_sha256"]
            != conditional_manifest["receipt_sha256"]
            or audit["capacity_corpus_receipt_sha256"]
            != capacity_manifest["receipt_sha256"]):
        raise ValueError("lawful-value rank corpus ancestry differs")
    target_config = LawfulValueConfig(**audit["config"])
    targets = {role: candidate_lawful_value_target(
        conditional[role], ledgers[role], fixed[role],
        horizon_sec=target_config.horizon_sec,
        maximum_stop_regret_usd=target_config.maximum_stop_regret_usd,
        watch_age_sec=target_config.watch_age_sec)
        for role in ("FIT", "PLATT")}
    selected_transform = audit["result"]["selected_feature_transform"]
    config = LawfulValueRankConfig()
    models, result = fit_lawful_value_rankers(
        fixed["FIT"], targets["FIT"], fixed["PLATT"], targets["PLATT"],
        selected_transform=selected_transform,
        audit_receipt_sha256=audit["receipt_sha256"], config=config)
    args.model_dir.mkdir(parents=True, exist_ok=False)
    model_files = {}
    for name, model in (("real", models.real), ("control", models.control)):
        path = args.model_dir / f"lawful_value_{name}.cbm"
        model.save_model(path, format="cbm")
        model_files[name] = {
            "path": path.name, "file_sha256": C.file_sha256(path),
            "tree_count": int(model.tree_count_),
        }
    core = {
        "schema": "QRE2CONFLAWFULVALUERANKAUDIT1",
        "config": result["config"],
        "config_sha256": result["config_sha256"],
        "lawful_value_mechanism_receipt_sha256": audit["receipt_sha256"],
        "conditional_corpus_receipt_sha256":
            conditional_manifest["receipt_sha256"],
        "capacity_corpus_receipt_sha256": capacity_manifest["receipt_sha256"],
        "selected_feature_transform": selected_transform,
        "models": model_files, "result": result,
        "models_executed": True, "economics_executed": False,
        "threshold_open_count": 0, "forward_open_count": 0,
        "h2_open_count": 0,
        "implementation_sha256": {
            "module": C.file_sha256(Path(
                "/workspace/engine/entry_v2/"
                "confirmation_lawful_value_model.py")),
            "tool": C.file_sha256(Path(__file__)),
        },
    }
    artifact = {**core, "receipt_sha256": C.object_sha256(core)}
    C.atomic_json(args.output, artifact)
    reloaded = json.loads(args.output.read_text()); check = dict(reloaded)
    receipt = str(check.pop("receipt_sha256"))
    if receipt != artifact["receipt_sha256"] or C.object_sha256(check) != receipt:
        raise ValueError("lawful-value rank artifact strict reload differs")
    print(json.dumps({
        "receipt_sha256": receipt,
        "result_receipt_sha256": result["receipt_sha256"],
        "model_gate_pass": result["model_gate_pass"],
        "fit_oof_real": result["fit_oof_real"],
        "fit_oof_control": result["fit_oof_control"],
        "platt_real": result["platt_real"],
        "platt_control": result["platt_control"],
        "models": model_files,
        "economics_executed": False,
        "threshold_open_count": 0, "h2_open_count": 0,
    }, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({
            "event": "LAWFUL_VALUE_RANK_REFUSED",
            "type": type(exc).__name__, "reason": str(exc),
        }, sort_keys=True), flush=True)
        raise
