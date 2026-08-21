#!/usr/bin/env python3
"""Reproduce the failed policy and publish matched full-event dossiers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from entry_v2 import common as C
from entry_v2.confirmation import ConfirmationConfig
from entry_v2.confirmation_dossier import (
    materialize_raw_dossiers, select_raw_dossiers,
)
from entry_v2.confirmation_experiment import (
    canonical_stage_specs, combine_feature_role, materialize_feature_cache,
    project_feature_set,
)
from entry_v2.confirmation_model import ConfirmationModel
from entry_v2.confirmation_policy import ConfirmationPolicy
from entry_v2.confirmation_stopping import OracleActionLedger
from entry_v2.diagnostic_inputs import fit_only_rehearsal_windows


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-root", type=Path,
        default=Path("/workspace/artifacts/cache/port/entry_v2"))
    parser.add_argument(
        "--cache-root", type=Path,
        default=Path("/workspace/artifacts/cache/entry_v2_confirmation_v1"))
    parser.add_argument(
        "--threshold-result", type=Path,
        default=Path("/workspace/artifacts/entry_v2/confirmation/e1r_age_v1/threshold_result.json"))
    parser.add_argument(
        "--ledger", type=Path,
        default=Path("/workspace/artifacts/entry_v2/confirmation/action_audit_v1/threshold_action_ledger.npz"))
    parser.add_argument(
        "--output", type=Path,
        default=Path("/workspace/artifacts/entry_v2/confirmation/raw_dossiers_v2"))
    parser.add_argument("--feature-set", default="PLUS_RECLAIM")
    parser.add_argument("--per-category", type=int, default=2)
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    try:
        threshold_result = json.loads(args.threshold_result.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("cannot read failed threshold result") from exc
    feature_row = next(
        row for row in threshold_result["feature_results"]
        if row["feature_set"] == args.feature_set)
    scorecards = [row for row in feature_row["policy_grid"]["all_scorecards"]
                  if row["total_pnl_usd"] is not None]
    if not scorecards:
        raise RuntimeError("failed threshold result has no measurable policy")
    scorecard = max(scorecards, key=lambda row: float(row["total_pnl_usd"]))
    policy = ConfirmationPolicy(**scorecard["policy"])
    windows = fit_only_rehearsal_windows("E1r")
    specs = canonical_stage_specs(
        "E1r", args.source_root, roles=("THRESHOLD",))
    config = ConfirmationConfig(max_delay_sec=300, snapshot_mode="TRAINING")
    records = materialize_feature_cache(
        specs["THRESHOLD"], config, args.cache_root, workers=1)
    corpus = combine_feature_role("THRESHOLD", windows["THRESHOLD"], records)
    ledger = OracleActionLedger.load(args.ledger)
    model_dataset = project_feature_set(corpus.dataset, args.feature_set)
    model = ConfirmationModel.load(feature_row["model_path"])
    predictions = model.predict(model_dataset)
    selections, evaluation, accepted = select_raw_dossiers(
        corpus.dataset, predictions, ledger, policy,
        expected_sessions=corpus.expected_sessions,
        per_category=args.per_category)
    if (evaluation.trades != int(scorecard["trades"])
            or abs(evaluation.total_pnl_usd
                   - float(scorecard["total_pnl_usd"])) > 1e-7):
        raise RuntimeError("failed policy did not reproduce canonical economics")
    reports = materialize_raw_dossiers(
        corpus.dataset, model_dataset, predictions, ledger, selections,
        source_root=args.source_root, output_directory=args.output)
    core = {
        "schema": "QRE2CONFRAWDOSSIERAUDIT1",
        "feature_set": args.feature_set, "model_hash": model.model_hash,
        "policy": scorecard["policy"], "policy_receipt_sha256":
            policy.receipt_sha256,
        "reproduced_economics": {
            "trades": evaluation.trades,
            "total_pnl_usd": evaluation.total_pnl_usd,
            "usd_per_trade": evaluation.usd_per_trade,
            "max_drawdown_usd": evaluation.max_drawdown_usd,
        },
        "accepted_trigger_count": len(accepted),
        "dossier_count": len(reports),
        "dossier_receipts": tuple(row["receipt_sha256"] for row in reports),
        "threshold_role_receipt_sha256": corpus.receipt_sha256,
        "ledger_representation_sha256": ledger.representation_sha256,
        "h2_open_count": 0,
    }
    final = {**core, "receipt_sha256": C.object_sha256(core)}
    C.atomic_json(args.output / "audit_report.json", final)
    print(json.dumps(final, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({
            "event": "RAW_DOSSIER_AUDIT_REFUSED", "type": type(exc).__name__,
            "reason": str(exc),
        }, sort_keys=True), file=sys.stderr, flush=True)
        raise
