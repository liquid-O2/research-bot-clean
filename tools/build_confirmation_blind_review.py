#!/usr/bin/env python3
"""Publish an outcome-blind real-data review roster and sealed Oracle reveal.

The safe manifest contains candidate identity and causal checkpoint locations
only.  The adjacent JSON dossier files contain the Oracle reveal and must not
be opened until manual decisions have been durably precommitted.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys

import numpy as np

from entry_v2 import common as C
from entry_v2.confirmation import ConfirmationConfig, ConfirmationRefusal
from entry_v2.confirmation_dossier import (
    materialize_raw_dossiers, select_blind_raw_dossiers,
)
from entry_v2.confirmation_experiment import (
    canonical_stage_specs, combine_feature_role, materialize_feature_cache,
)
from entry_v2.confirmation_model import ConfirmationPredictions
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
        "--ledger", type=Path,
        default=Path("/workspace/artifacts/entry_v2/confirmation/"
                     "action_audit_v1/threshold_action_ledger.npz"))
    parser.add_argument(
        "--output", type=Path,
        default=Path("/workspace/artifacts/entry_v2/confirmation/"
                     "blind_raw_review_v1"))
    parser.add_argument("--per-asset-side", type=int, default=2)
    parser.add_argument("--selection-seed", type=int, default=20260819)
    return parser.parse_args()


def _roster(dataset, selections) -> tuple[tuple[str, tuple[int, ...]], ...]:
    return tuple(
        (str(dataset.series_id[row.anchor_index]), row.decision_indices)
        for row in selections)


def main() -> int:
    args = _arguments()
    output = C.assert_workspace_output(args.output)
    if output.exists():
        raise ConfirmationRefusal("blind review output already exists")
    windows = fit_only_rehearsal_windows("E1r")
    specs = canonical_stage_specs(
        "E1r", args.source_root, roles=("THRESHOLD",))
    config = ConfirmationConfig(max_delay_sec=300, snapshot_mode="TRAINING")
    records = materialize_feature_cache(
        specs["THRESHOLD"], config, args.cache_root, workers=1)
    corpus = combine_feature_role(
        "THRESHOLD", windows["THRESHOLD"], records)
    dataset = corpus.dataset
    selections = select_blind_raw_dossiers(
        dataset, per_asset_side=args.per_asset_side,
        selection_seed=args.selection_seed)

    # Real-data blindness certificate: permute all terminal outcome columns
    # together and prove that the immutable roster does not move.
    permutation = np.roll(
        np.arange(len(dataset.features), dtype=np.int64), 137)
    counterfactual = replace(
        dataset,
        cert_close_usd=np.asarray(dataset.cert_close_usd)[permutation],
        mfe_usd=np.asarray(dataset.mfe_usd)[permutation],
        mae_usd=np.asarray(dataset.mae_usd)[permutation],
        wall_hit=np.asarray(dataset.wall_hit)[permutation],
    )
    counterfactual.validate()
    destroyed = select_blind_raw_dossiers(
        counterfactual, per_asset_side=args.per_asset_side,
        selection_seed=args.selection_seed)
    if _roster(dataset, selections) != _roster(counterfactual, destroyed):
        raise ConfirmationRefusal("blind roster changed after outcome destruction")

    ledger = OracleActionLedger.load(args.ledger)
    n = len(dataset.features)
    zeros = np.zeros(n, np.float64)
    predictions = ConfirmationPredictions(
        opportunity_id=np.asarray(dataset.opportunity_id, str).copy(),
        expected_pnl_usd=zeros.copy(), pnl_q20_usd=zeros.copy(),
        goal_probability=zeros.copy(), wall_probability=zeros.copy(),
        mae_q90_usd=zeros.copy(), model_hash="BLIND_REVIEW_NO_MODEL")
    sealed = output / "sealed"
    reports = materialize_raw_dossiers(
        dataset, dataset, predictions, ledger, selections,
        source_root=args.source_root, output_directory=sealed)
    by_series = {str(row["series_id"]): row for row in reports}

    cases = []
    for ordinal, selection in enumerate(selections, start=1):
        anchor = selection.anchor_index
        series_id = str(dataset.series_id[anchor])
        report = by_series[series_id]
        checkpoints = []
        formation_ts = int(report["formation_ts_ns"])
        for index in selection.decision_indices:
            timestamp = int(dataset.snapshot_ts_ns[index])
            checkpoints.append({
                "snapshot_ts_ns": timestamp,
                "watch_age_sec": (timestamp - formation_ts) / 1e9,
            })
        cases.append({
            "case_id": f"B{ordinal:02d}",
            "series_id": series_id,
            "candidate_id": str(dataset.candidate_id[anchor]),
            "asset": str(dataset.asset[anchor]),
            "trading_day": int(dataset.day[anchor]),
            "side": int(dataset.side[anchor]),
            "phase": str(dataset.phase[anchor]),
            "formation_ts_ns": formation_ts,
            "checkpoints": checkpoints,
            "causal_npz_path": str(report["npz_path"]),
            "causal_npz_sha256": str(report["npz_sha256"]),
            "raw_event_count": int(report["raw_event_count"]),
            "sealed_oracle_report_path": str(
                Path(str(report["npz_path"])).with_suffix(".json")),
        })
    safe_core = {
        "schema": "QRE2CONFBLINDREVIEW1",
        "stage": "E1R_THRESHOLD",
        "selection_method": "OUTCOME_BLIND_STABLE_HASH",
        "selection_seed": args.selection_seed,
        "per_asset_side": args.per_asset_side,
        "watch_ages_seconds": [0, 30, 60, 120, 180, 240],
        "outcome_destruction_roster_unchanged": True,
        "manual_precommit_required_before_oracle_reveal": True,
        "threshold_role_receipt_sha256": corpus.receipt_sha256,
        "ledger_representation_sha256": ledger.representation_sha256,
        "cases": cases,
        "forward_open_count": 0,
        "h2_open_count": 0,
    }
    safe = {**safe_core, "receipt_sha256": C.object_sha256(safe_core)}
    C.atomic_json(output / "blind_manifest.json", safe)
    print(json.dumps({
        "schema": safe["schema"], "case_count": len(cases),
        "cell_counts": {
            f"{asset}:{side}": sum(
                row["asset"] == asset and row["side"] == side for row in cases)
            for asset in C.ASSETS for side in (-1, 1)
        },
        "outcome_destruction_roster_unchanged": True,
        "manifest_path": str(output / "blind_manifest.json"),
        "receipt_sha256": safe["receipt_sha256"],
        "forward_open_count": 0, "h2_open_count": 0,
    }, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({
            "event": "BLIND_REVIEW_REFUSED", "type": type(exc).__name__,
            "reason": str(exc),
        }, sort_keys=True), file=sys.stderr, flush=True)
        raise
