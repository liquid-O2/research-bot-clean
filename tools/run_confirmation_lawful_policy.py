#!/usr/bin/env python3
"""Run the bounded action-aligned CatBoost PLATT ceiling."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from catboost import CatBoostRanker

from entry_v2 import common as C
from entry_v2.confirmation_lawful_policy import (
    LawfulPolicyConfig, fit_fixed_horizon_rankers,
    run_lawful_policy_ceiling,
)
from entry_v2.confirmation_lawful_value_model import (
    LawfulValueRankModels, lawful_value_rank_scores,
)

from run_confirmation_dynamic_hurdle import (
    _learned_fit_gate, _load_rank_models,
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
        "--rank-model-dir", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_factorized_policy_v1_models"))
    parser.add_argument(
        "--fixed-horizon-audit", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_fixed_horizon_mechanism_v2.json"))
    parser.add_argument(
        "--candidate-rank-audit", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_lawful_value_rank_v1.json"))
    parser.add_argument(
        "--candidate-model-dir", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_lawful_value_rank_v1_models"))
    parser.add_argument(
        "--output", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_lawful_policy_ceiling_v1.json"))
    parser.add_argument(
        "--stop-model-dir", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_lawful_policy_ceiling_v1_models"))
    return parser.parse_args()


def _verified_json(path: Path, schema: str) -> dict:
    value = json.loads(path.read_text()); core = dict(value)
    receipt = str(core.pop("receipt_sha256"))
    if value.get("schema") != schema or C.object_sha256(core) != receipt:
        raise ValueError(f"artifact identity differs: {path}")
    return value


def _load_candidate_models(artifact: dict, root: Path) -> LawfulValueRankModels:
    loaded = {}
    for name in ("real", "control"):
        row = artifact["models"][name]; path = root / row["path"]
        if C.file_sha256(path) != row["file_sha256"]:
            raise ValueError("lawful candidate model payload differs")
        model = CatBoostRanker(); model.load_model(path, format="cbm")
        loaded[name] = model
    names = tuple(artifact["result"]["feature_names"])
    # The persisted models were fitted from NumPy matrices, so CatBoost stores
    # positional names ("0", "1", ...).  The audited semantic tuple lives in
    # the artifact and is checked again when the transform is applied.
    if (len(loaded["real"].feature_names_) != len(names)
            or len(loaded["control"].feature_names_) != len(names)):
        raise ValueError("lawful candidate model schema differs")
    return LawfulValueRankModels(
        loaded["real"], loaded["control"], names)


def main() -> int:
    args = _arguments()
    if args.output.exists() or args.stop_model_dir.exists():
        raise FileExistsError("lawful-policy output already exists")
    fixed_audit = _verified_json(
        args.fixed_horizon_audit, "QRE2CONFFIXEDHORIZONAUDIT1")
    candidate_audit = _verified_json(
        args.candidate_rank_audit, "QRE2CONFLAWFULVALUERANKAUDIT1")
    if (not fixed_audit["result"]["mechanism_gate_pass"]
            or not candidate_audit["result"]["model_gate_pass"]
            or fixed_audit.get("h2_open_count") != 0
            or candidate_audit.get("h2_open_count") != 0):
        raise ValueError("lawful-policy upstream gate differs")
    (conditional, ledgers, fixed, sessions,
     conditional_manifest, capacity_manifest) = _load_roles(
         args.conditional_root, args.capacity_root)
    for artifact in (fixed_audit, candidate_audit):
        if (artifact["conditional_corpus_receipt_sha256"]
                != conditional_manifest["receipt_sha256"]
                or artifact["capacity_corpus_receipt_sha256"]
                != capacity_manifest["receipt_sha256"]):
            raise ValueError("lawful-policy corpus ancestry differs")
    candidate_models = _load_candidate_models(
        candidate_audit, args.candidate_model_dir)
    candidate_transform = candidate_audit["selected_feature_transform"]
    candidate_scores = {}
    for role in ("FIT", "PLATT"):
        real, control = lawful_value_rank_scores(
            candidate_models, fixed[role],
            selected_transform=candidate_transform)
        candidate_scores[role] = {"REAL": real, "CONTROL": control}
    old_rank, _old_control, old_manifest = _load_rank_models(
        args.rank_model_dir, conditional_manifest)
    gated = {}; gated_ledgers = {}
    for role in ("FIT", "PLATT"):
        gated[role], gated_ledgers[role] = _learned_fit_gate(
            conditional[role], ledgers[role], fixed[role],
            rank_model=old_rank, capacity=12)
    config = LawfulPolicyConfig()
    stop_transform = fixed_audit["result"]["horizons"][
        str(config.horizon_sec)]["selected_feature_transform"]
    (stop_models, stop_report, fit_target, platt_target,
     fit_real_stop, fit_control_stop) = fit_fixed_horizon_rankers(
        gated["FIT"], gated_ledgers["FIT"],
        gated["PLATT"], gated_ledgers["PLATT"],
        selected_transform=stop_transform, config=config)
    if not stop_report["model_gate_pass"]:
        raise ValueError("lawful-policy stopping model gate failed")
    base_roster = tuple(sorted(set(gated["PLATT"].series_id.tolist())))
    result = run_lawful_policy_ceiling(
        gated["FIT"], gated_ledgers["FIT"],
        gated["PLATT"], gated_ledgers["PLATT"], fixed["PLATT"],
        sessions["PLATT"], base_roster=base_roster,
        candidate_models=candidate_models,
        candidate_scores=candidate_scores["PLATT"],
        stop_models=stop_models,
        stop_targets={"FIT": fit_target, "PLATT": platt_target},
        fit_stop_scores={"REAL": fit_real_stop,
                         "CONTROL": fit_control_stop},
        selected_stop_transform=stop_transform, config=config)
    args.stop_model_dir.mkdir(parents=True, exist_ok=False)
    stop_files = {}
    for name, model in (("real", stop_models.real),
                        ("control", stop_models.control)):
        path = args.stop_model_dir / f"fixed_horizon_{name}.cbm"
        model.save_model(path, format="cbm")
        stop_files[name] = {
            "path": path.name, "file_sha256": C.file_sha256(path),
            "tree_count": int(model.tree_count_),
        }
    core = {
        "schema": "QRE2CONFLAWFULPOLICYCEILINGAUDIT1",
        "config": result["config"],
        "config_sha256": result["config_sha256"],
        "fixed_horizon_mechanism_receipt_sha256":
            fixed_audit["receipt_sha256"],
        "candidate_rank_receipt_sha256": candidate_audit["receipt_sha256"],
        "old_rank_bundle_receipt_sha256": old_manifest["receipt_sha256"],
        "conditional_corpus_receipt_sha256":
            conditional_manifest["receipt_sha256"],
        "capacity_corpus_receipt_sha256": capacity_manifest["receipt_sha256"],
        "stopping_models": stop_files,
        "stopping_model_report": stop_report,
        "result": result,
        "models_executed": True, "learned_economics_executed": True,
        "threshold_open_count": 0, "forward_open_count": 0,
        "h2_open_count": 0,
        "implementation_sha256": {
            "module": C.file_sha256(Path(
                "/workspace/engine/entry_v2/confirmation_lawful_policy.py")),
            "tool": C.file_sha256(Path(__file__)),
        },
    }
    artifact = {**core, "receipt_sha256": C.object_sha256(core)}
    C.atomic_json(args.output, artifact)
    reloaded = json.loads(args.output.read_text()); check = dict(reloaded)
    receipt = str(check.pop("receipt_sha256"))
    if receipt != artifact["receipt_sha256"] or C.object_sha256(check) != receipt:
        raise ValueError("lawful-policy artifact strict reload differs")
    print(json.dumps({
        "receipt_sha256": receipt,
        "result_receipt_sha256": result["receipt_sha256"],
        "stopping_model_gate_pass": stop_report["model_gate_pass"],
        "stopping_platt_real": stop_report["diagnostics"]["platt_real"]["overall"],
        "stopping_platt_control": stop_report["diagnostics"]["platt_control"]["overall"],
        "arm_selected": {name: row["selected_with_capture"]
                         for name, row in result["arms"].items()},
        "real_real_capture": result["real_real_capture"],
        "maximum_control_arm_capture": result["maximum_control_arm_capture"],
        "passes_80_percent": result["platt_model_ceiling_passes_80_percent"],
        "selection_is_deployable": False,
        "threshold_open_count": 0, "h2_open_count": 0,
    }, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({
            "event": "LAWFUL_POLICY_REFUSED", "type": type(exc).__name__,
            "reason": str(exc),
        }, sort_keys=True), flush=True)
        raise
