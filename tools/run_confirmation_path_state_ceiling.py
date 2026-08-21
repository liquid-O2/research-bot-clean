#!/usr/bin/env python3
"""Fit and exactly price the delayed path-state CatBoost acceptance ceiling."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from entry_v2 import common as C
from entry_v2.confirmation_path_state import build_path_state_landmark
from entry_v2.confirmation_path_state_ceiling import (
    run_path_state_acceptance_ceiling,
)
from entry_v2.confirmation_path_state_model import (
    PathStateRankConfig, fit_path_state_rankers, path_state_rank_scores,
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
        "--output", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_path_state_ceiling_v3.json"))
    parser.add_argument(
        "--model-dir", type=Path,
        default=Path(
            "/workspace/artifacts/entry_v2/confirmation/v9_qrf4/"
            "e1r_path_state_ceiling_v3_models"))
    parser.add_argument("--landmark-delay-sec", type=int, default=30)
    parser.add_argument("--iterations", type=int, default=120)
    parser.add_argument("--depth", type=int, default=5)
    parser.add_argument("--thread-count", type=int, default=16)
    parser.add_argument("--rolling-train-days", type=int, default=12)
    parser.add_argument(
        "--objective-variant",
        choices=("SIGNED_ORDER", "ORDINAL_POSITIVE_TOP3",
                 "QUERY_SOFTMAX_POSITIVE_UTILITY"),
        default="SIGNED_ORDER")
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    if args.output.exists() or args.model_dir.exists():
        raise FileExistsError("path-state ceiling output already exists")
    (conditional, ledgers, fixed, sessions,
     conditional_manifest, capacity_manifest) = _load_roles(
         args.conditional_root, args.capacity_root)
    old_rank, _old_control, old_manifest = _load_rank_models(
        args.rank_model_dir, conditional_manifest)
    rosters = {}
    for role in ("FIT", "PLATT"):
        gated, _ = _learned_fit_gate(
            conditional[role], ledgers[role], fixed[role],
            rank_model=old_rank, capacity=12)
        rosters[role] = tuple(sorted(set(np.asarray(
            gated.series_id, str).tolist())))
    landmarks = {
        role: build_path_state_landmark(
            conditional[role], ledgers[role],
            landmark_delay_sec=args.landmark_delay_sec,
            horizon_sec=120, watch_age_sec=30)
        for role in ("FIT", "PLATT")
    }
    config = PathStateRankConfig(
        iterations=args.iterations, depth=args.depth,
        thread_count=args.thread_count,
        rolling_train_days=args.rolling_train_days,
        objective_variant=args.objective_variant)
    models, model_report = fit_path_state_rankers(
        landmarks["FIT"], landmarks["PLATT"],
        fit_roster=rosters["FIT"], platt_roster=rosters["PLATT"],
        config=config)
    platt_real, platt_control = path_state_rank_scores(
        models, landmarks["PLATT"])
    ceiling = run_path_state_acceptance_ceiling(
        conditional["PLATT"], ledgers["PLATT"], landmarks["PLATT"],
        sessions["PLATT"], roster=rosters["PLATT"],
        real_score=platt_real, control_score=platt_control)
    args.model_dir.mkdir(parents=True, exist_ok=False)
    model_files = {}
    for name, model in (("real", models.real),
                        ("control", models.control)):
        path = args.model_dir / f"path_state_{name}.cbm"
        model.save_model(path, format="cbm")
        model_files[name] = {
            "path": path.name, "file_sha256": C.file_sha256(path),
            "tree_count": int(model.tree_count_),
        }
    core = {
        "schema": "QRE2CONFPATHSTATECEILINGAUDIT1",
        "conditional_corpus_receipt_sha256":
            conditional_manifest["receipt_sha256"],
        "capacity_corpus_receipt_sha256":
            capacity_manifest["receipt_sha256"],
        "old_rank_bundle_receipt_sha256": old_manifest["receipt_sha256"],
        "landmark_delay_sec": args.landmark_delay_sec,
        "fit_landmark_representation_sha256":
            landmarks["FIT"].representation_sha256,
        "platt_landmark_representation_sha256":
            landmarks["PLATT"].representation_sha256,
        "model_report": model_report,
        "model_files": model_files,
        "ceiling": ceiling,
        "models_executed": True,
        "model_ceiling_economics_executed": True,
        "deployable_thresholds_executed": False,
        "threshold_open_count": 0, "forward_open_count": 0,
        "h2_open_count": 0,
        "implementation_sha256": {
            name: C.file_sha256(path) for name, path in {
                "path_state": Path(
                    "/workspace/engine/entry_v2/confirmation_path_state.py"),
                "model": Path(
                    "/workspace/engine/entry_v2/confirmation_path_state_model.py"),
                "ceiling": Path(
                    "/workspace/engine/entry_v2/confirmation_path_state_ceiling.py"),
                "tool": Path(__file__),
            }.items()
        },
    }
    artifact = {**core, "receipt_sha256": C.object_sha256(core)}
    C.atomic_json(args.output, artifact)
    reloaded = json.loads(args.output.read_text()); check = dict(reloaded)
    receipt = str(check.pop("receipt_sha256"))
    if receipt != artifact["receipt_sha256"] or C.object_sha256(check) != receipt:
        raise ValueError("path-state ceiling strict reload differs")
    print(json.dumps({
        "receipt_sha256": receipt,
        "model_gate_pass": model_report["model_gate_pass"],
        "fit_oof_real_roster": model_report["fit_oof_real_roster"],
        "fit_oof_control_roster": model_report["fit_oof_control_roster"],
        "platt_real_roster": model_report["platt_real_roster"],
        "platt_control_roster": model_report["platt_control_roster"],
        "ceiling_real": ceiling["arms"]["REAL"]["selected"],
        "ceiling_control": ceiling["arms"]["CONTROL"]["selected"],
        "ceiling_oracle": ceiling["arms"]["ORACLE"]["selected"],
        "real_capture": ceiling["real_capture"],
        "control_capture": ceiling["control_capture"],
        "passes_80_percent": ceiling["passes_80_percent"],
        "threshold_open_count": 0, "h2_open_count": 0,
    }, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({
            "event": "PATH_STATE_CEILING_REFUSED",
            "type": type(exc).__name__, "reason": str(exc),
        }, sort_keys=True), flush=True)
        raise
