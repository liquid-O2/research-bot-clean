#!/usr/bin/env python3
"""Select a path-state objective using exact FIT OOF economics only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from entry_v2 import common as C
from entry_v2.confirmation import ConfirmationDataset
from entry_v2.confirmation_path_state import build_path_state_landmark
from entry_v2.confirmation_path_state_ceiling import (
    run_path_state_acceptance_ceiling,
)
from entry_v2.confirmation_path_state_model import (
    PathStateRankConfig, fit_path_state_oof_scores,
)
from entry_v2.confirmation_stopping import OracleActionLedger
from entry_v2.contracts import SessionRef

from run_confirmation_dynamic_hurdle import (
    _learned_fit_gate, _load_rank_models, _verified_manifest,
)


OBJECTIVES = (
    "SIGNED_ORDER",
    "ORDINAL_POSITIVE_TOP3",
    "QUERY_SOFTMAX_POSITIVE_UTILITY",
)


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
            "e1r_path_state_fit_oof_objectives_v1.json"))
    parser.add_argument("--landmark-delay-sec", type=int, default=30)
    parser.add_argument("--iterations", type=int, default=120)
    parser.add_argument("--depth", type=int, default=5)
    parser.add_argument("--thread-count", type=int, default=16)
    return parser.parse_args()


def _load_fit_only(
    conditional_root: Path, capacity_root: Path,
) -> tuple[
    ConfirmationDataset, OracleActionLedger, ConfirmationDataset,
    tuple[SessionRef, ...], dict[str, object], dict[str, object],
]:
    conditional_manifest = _verified_manifest(
        conditional_root / "manifest.json", "QRE2CONFCONDITIONALCORPUSAUDIT1")
    capacity_manifest = _verified_manifest(
        capacity_root / "manifest.json", "QRE2CONFCAPACITYCORPUSAUDIT1")
    if (conditional_manifest["capacity_corpus_receipt_sha256"]
            != capacity_manifest["receipt_sha256"]
            or conditional_manifest.get("h2_open_count") != 0
            or capacity_manifest.get("h2_open_count") != 0):
        raise ValueError("FIT-only corpus ancestry differs")
    conditional_files = conditional_manifest["files"]["FIT"]
    fixed_files = capacity_manifest["files"]["FIT"]
    dataset_path = conditional_root / conditional_files["dataset"]
    ledger_path = conditional_root / conditional_files["ledger"]
    fixed_path = capacity_root / fixed_files["dataset"]
    for path, expected in (
        (dataset_path, conditional_files["dataset_file_sha256"]),
        (ledger_path, conditional_files["ledger_file_sha256"]),
        (fixed_path, fixed_files["dataset_file_sha256"]),
    ):
        if C.file_sha256(path) != expected:
            raise ValueError(f"FIT-only payload identity differs: {path}")
    conditional = ConfirmationDataset.load(dataset_path)
    ledger = OracleActionLedger.load(ledger_path)
    fixed = ConfirmationDataset.load(fixed_path)
    report = conditional_manifest["roles"]["FIT"]
    if (conditional.representation_sha256 != report["dataset_sha256"]
            or ledger.representation_sha256 != report["ledger_sha256"]
            or fixed.representation_sha256 != report["fixed_dataset_sha256"]):
        raise ValueError("FIT-only role receipt differs")
    sessions = tuple(SessionRef(
        str(row["asset"]), int(row["trading_day"]), str(row["session_id"]))
        for row in report["expected_sessions"])
    return (conditional, ledger, fixed, sessions,
            conditional_manifest, capacity_manifest)


def _days_roster(
    landmark, roster: tuple[str, ...], days: tuple[int, ...],
) -> tuple[str, ...]:
    mask = (np.isin(np.asarray(landmark.dataset.series_id, str), roster)
            & np.isin(np.asarray(landmark.dataset.day, np.int64), days))
    result = tuple(sorted(set(np.asarray(
        landmark.dataset.series_id, str)[mask].tolist())))
    if not result:
        raise ValueError("FIT OOF roster is empty")
    return result


def main() -> int:
    args = _arguments()
    if args.output.exists():
        raise FileExistsError(f"FIT OOF output exists: {args.output}")
    (conditional, ledger, fixed, sessions,
     conditional_manifest, capacity_manifest) = _load_fit_only(
         args.conditional_root, args.capacity_root)
    old_rank, _old_control, old_manifest = _load_rank_models(
        args.rank_model_dir, conditional_manifest)
    gated, _ = _learned_fit_gate(
        conditional, ledger, fixed, rank_model=old_rank, capacity=12)
    roster = tuple(sorted(set(np.asarray(gated.series_id, str).tolist())))
    landmark = build_path_state_landmark(
        conditional, ledger, landmark_delay_sec=args.landmark_delay_sec,
        horizon_sec=120, watch_age_sec=30)
    arms = {}
    for objective in OBJECTIVES:
        config = PathStateRankConfig(
            iterations=args.iterations, depth=args.depth,
            thread_count=args.thread_count, rolling_train_days=30,
            objective_variant=objective)
        scores, model_report = fit_path_state_oof_scores(
            landmark, fit_roster=roster, config=config)
        oof_days = tuple(sorted(set(np.asarray(
            landmark.dataset.day, np.int64)[scores.mask].tolist())))
        oof_sessions = tuple(
            row for row in sessions if row.trading_day in set(oof_days))
        oof_roster = _days_roster(landmark, roster, oof_days)
        aggregate = run_path_state_acceptance_ceiling(
            conditional, ledger, landmark, oof_sessions,
            roster=oof_roster, real_score=scores.real,
            control_score=scores.control,
            evaluation_scope="FIT_CHRONOLOGICAL_OOF")
        folds = []
        for fold in model_report["chronological_folds"]:
            days = tuple(map(int, fold["validation_days"]))
            fold_sessions = tuple(
                row for row in sessions if row.trading_day in set(days))
            fold_roster = _days_roster(landmark, roster, days)
            ceiling = run_path_state_acceptance_ceiling(
                conditional, ledger, landmark, fold_sessions,
                roster=fold_roster, real_score=scores.real,
                control_score=scores.control,
                evaluation_scope="FIT_CHRONOLOGICAL_OOF")
            folds.append({
                "fold": int(fold["fold"]), "validation_days": days,
                "ceiling": ceiling,
            })
        real_days = tuple(float(row["ceiling"]["arms"]["REAL"]["selected"]
                                ["evaluation"]["usd_per_portfolio_day"])
                          for row in folds)
        control_days = tuple(float(row["ceiling"]["arms"]["CONTROL"]
                                   ["selected"]["evaluation"]
                                   ["usd_per_portfolio_day"])
                             for row in folds)
        oracle_capture = tuple(
            float(row["ceiling"]["arms"]["ORACLE"]
                  ["capture_of_frozen_sparse_roster_ceiling"])
            for row in folds)
        real_capture = tuple(
            float(row["ceiling"]["real_capture"]) for row in folds)
        stable = bool(
            all(real > 0.0 and real > control
                for real, control in zip(real_days, control_days))
            and all(real >= .8 * oracle
                    for real, oracle in zip(real_capture, oracle_capture)))
        arm = {
            "objective": objective, "model_report": model_report,
            "aggregate_oof_ceiling": aggregate,
            "fold_oof_ceilings": tuple(folds),
            "worst_fold_usd_per_portfolio_day": min(real_days),
            "worst_fold_gain_over_control_usd_per_portfolio_day": min(
                real - control
                for real, control in zip(real_days, control_days)),
            "all_fold_positive_and_control_wins": all(
                real > 0.0 and real > control
                for real, control in zip(real_days, control_days)),
            "all_fold_80_percent_of_same_family_oracle": all(
                real >= .8 * oracle
                for real, oracle in zip(real_capture, oracle_capture)),
            "stable_oof_gate_pass": stable,
        }
        arms[objective] = {**arm, "receipt_sha256": C.object_sha256(arm)}
    selected = max(arms, key=lambda name: (
        bool(arms[name]["stable_oof_gate_pass"]),
        float(arms[name]["worst_fold_usd_per_portfolio_day"]),
        float(arms[name]["worst_fold_gain_over_control_usd_per_portfolio_day"]),
    ))
    core = {
        "schema": "QRE2CONFPATHSTATEFITOOFSELECTION1",
        "selection_role": "FIT_CHRONOLOGICAL_OOF_ONLY",
        "selection_law": (
            "STABLE_GATE_THEN_WORST_FOLD_ECONOMICS_THEN_WORST_CONTROL_GAIN"),
        "objectives": OBJECTIVES, "selected_objective": selected,
        "selected_ready_for_platt": bool(arms[selected]["stable_oof_gate_pass"]),
        "arms": arms,
        "conditional_corpus_receipt_sha256":
            conditional_manifest["receipt_sha256"],
        "capacity_corpus_receipt_sha256": capacity_manifest["receipt_sha256"],
        "old_rank_bundle_receipt_sha256": old_manifest["receipt_sha256"],
        "fit_landmark_representation_sha256": landmark.representation_sha256,
        "implementation_sha256": {
            "path_state": C.file_sha256(Path(
                "/workspace/engine/entry_v2/confirmation_path_state.py")),
            "model": C.file_sha256(Path(
                "/workspace/engine/entry_v2/confirmation_path_state_model.py")),
            "ceiling": C.file_sha256(Path(
                "/workspace/engine/entry_v2/confirmation_path_state_ceiling.py")),
            "tool": C.file_sha256(Path(__file__)),
        },
        "platt_open_count": 0, "threshold_open_count": 0,
        "forward_open_count": 0, "h2_open_count": 0,
    }
    artifact = {**core, "receipt_sha256": C.object_sha256(core)}
    C.atomic_json(args.output, artifact)
    reloaded = json.loads(args.output.read_text()); check = dict(reloaded)
    receipt = str(check.pop("receipt_sha256"))
    if receipt != artifact["receipt_sha256"] or C.object_sha256(check) != receipt:
        raise ValueError("FIT OOF strict reload differs")
    print(json.dumps({
        "receipt_sha256": receipt, "selected_objective": selected,
        "selected_ready_for_platt": core["selected_ready_for_platt"],
        "arms": {name: {
            "worst_fold_usd_per_portfolio_day":
                row["worst_fold_usd_per_portfolio_day"],
            "worst_fold_gain_over_control_usd_per_portfolio_day":
                row["worst_fold_gain_over_control_usd_per_portfolio_day"],
            "all_fold_positive_and_control_wins":
                row["all_fold_positive_and_control_wins"],
            "all_fold_80_percent_of_same_family_oracle":
                row["all_fold_80_percent_of_same_family_oracle"],
            "aggregate_real": row["aggregate_oof_ceiling"]["arms"]["REAL"]
                ["selected"],
            "aggregate_control": row["aggregate_oof_ceiling"]["arms"]
                ["CONTROL"]["selected"],
            "aggregate_oracle": row["aggregate_oof_ceiling"]["arms"]
                ["ORACLE"]["selected"],
        } for name, row in arms.items()},
        "platt_open_count": 0, "threshold_open_count": 0,
        "h2_open_count": 0,
    }, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({
            "event": "PATH_STATE_FIT_OOF_REFUSED",
            "type": type(exc).__name__, "reason": str(exc),
        }, sort_keys=True), flush=True)
        raise
