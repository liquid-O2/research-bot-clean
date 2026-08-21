#!/usr/bin/env python3
"""Run the resumable pre-forward CatBoost confirmation experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from entry_v2.confirmation import ConfirmationConfig
from entry_v2.confirmation_experiment import (
    canonical_stage_specs, combine_feature_role, materialize_feature_cache,
    run_threshold_experiment,
)
from entry_v2.confirmation_model import ConfirmationModelConfig
from entry_v2.diagnostic_inputs import fit_only_rehearsal_windows


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", default="E1r", choices=("E1r", "E2r"))
    parser.add_argument(
        "--source-root", type=Path,
        default=Path("/workspace/artifacts/cache/port/entry_v2"))
    parser.add_argument(
        "--cache-root", type=Path,
        default=Path("/workspace/artifacts/cache/entry_v2_confirmation_v1"))
    parser.add_argument(
        "--output", type=Path,
        default=Path("/workspace/artifacts/entry_v2/confirmation/e1r_diagnostic"))
    parser.add_argument("--model-directory", type=Path)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--depth", type=int, default=6)
    parser.add_argument("--learning-rate", type=float, default=.04)
    parser.add_argument("--l2-leaf-reg", type=float, default=10.0)
    parser.add_argument("--thread-count", type=int, default=16)
    parser.add_argument(
        "--feature-sets", nargs="+",
        default=("PLUS_CURRENT_BOOK", "PLUS_RECLAIM", "MAX_W300"))
    parser.add_argument("--materialize-only", action="store_true")
    parser.add_argument("--no-shuffled-control", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    roles = ("FIT", "PLATT", "THRESHOLD")
    specs = canonical_stage_specs(
        args.stage, args.source_root, roles=roles)
    windows = fit_only_rehearsal_windows(args.stage)
    feature_config = ConfirmationConfig(
        max_delay_sec=300, snapshot_mode="TRAINING")
    corpora = {}
    for role in roles:
        print(json.dumps({
            "event": "ROLE_CACHE_START", "role": role,
            "sessions": len(specs[role]), "window": windows[role],
        }), flush=True)
        records = materialize_feature_cache(
            specs[role], feature_config, args.cache_root,
            workers=args.workers)
        corpora[role] = combine_feature_role(role, windows[role], records)
        print(json.dumps({
            "event": "ROLE_CACHE_READY", "role": role,
            "rows": len(corpora[role].dataset.features),
            "series": len(set(corpora[role].dataset.series_id)),
            "expected_sessions": len(corpora[role].expected_sessions),
            "empty_sessions": len(corpora[role].empty_sessions),
            "receipt_sha256": corpora[role].receipt_sha256,
        }), flush=True)
    if args.materialize_only:
        return 0
    config = ConfirmationModelConfig(
        iterations=args.iterations, depth=args.depth,
        learning_rate=args.learning_rate, l2_leaf_reg=args.l2_leaf_reg,
        thread_count=args.thread_count)
    result = run_threshold_experiment(
        corpora, feature_sets=args.feature_sets, model_config=config,
        output_directory=args.output, stage=args.stage,
        model_directory=args.model_directory,
        run_shuffled_control=not args.no_shuffled_control)
    summary = {
        "status": result.status,
        "stage": result.stage,
        "selected_feature_set": result.selected_feature_set,
        "selected_model_path": result.selected_model_path,
        "selected_policy_receipt_sha256":
            result.selected_policy_receipt_sha256,
        "receipt_sha256": result.receipt_sha256,
        "features": [{
            "feature_set": row.feature_set,
            "feature_count": row.feature_count,
            "goal_auc": row.threshold_diagnostic.goal_auc,
            "wall_auc": row.threshold_diagnostic.wall_auc,
            "pnl_correlation": row.threshold_diagnostic.pnl_correlation,
            "policy_status": row.policy_grid.status,
            "feasible_policies": len(row.policy_grid.feasible_scorecards),
        } for row in result.feature_results],
        "shuffled_control": (None if result.shuffled_control is None else {
            "feature_set": result.shuffled_control.feature_set,
            "goal_auc": result.shuffled_control.threshold_diagnostic.goal_auc,
            "wall_auc": result.shuffled_control.threshold_diagnostic.wall_auc,
            "pnl_correlation":
                result.shuffled_control.threshold_diagnostic.pnl_correlation,
            "policy_status": result.shuffled_control.policy_grid.status,
            "feasible_policies": len(
                result.shuffled_control.policy_grid.feasible_scorecards),
            "receipt_sha256": result.shuffled_control.receipt_sha256,
        }),
    }
    print(json.dumps(summary, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({
            "event": "CONFIRMATION_EXPERIMENT_REFUSED",
            "type": type(exc).__name__, "reason": str(exc),
        }, sort_keys=True), file=sys.stderr, flush=True)
        raise
